# ElegantRL 样本外改造：代码、原理与落地状态

> 本文是 `REFACTOR_PLAN.md` 的详细说明版。
> `REFACTOR_PLAN.md` 记录“要做什么”；本文记录“改了哪些代码、为什么这样改、
> 数据如何流动、目前还缺什么”。

## 0. 一句话总结

这次改造把 RL 训练从：

```text
一份数据 → 全样本特征处理 → 训练集当验证集 → 样本内指标
```

改成：

```text
时间切分 / walk-forward
    ↓
只用 train 拟合特征统计量
    ↓
独立 validation 选 checkpoint
    ↓
test 只做最终评估
    ↓
成本化 reward + 完整持仓状态 + 多 seed / ensemble
```

原则：

```text
特征统计量只看 train
模型选择只看 val
test 只评估一次
reward 要扣真实成本
state 要能区分空仓 / 多仓 / 空仓 / 持仓风险
```

---

## 1. 数据流

```text
原始 df
  │
  ├─ splits.py
  │     split_dataframe() / walk_forward_windows()
  │
  ├─ walk_forward.py
  │     make_folds()
  │       fold.train ──┐
  │       fold.val   ──┤
  │       fold.test  ──┘
  │
  ├─ Strategy.set_process_quant_features(fit_range=...)
  │     scaler / clip / PCA / 特征选择只在 fold.train 上 fit
  │
  ├─ Strategy.set_model_params(eval_env_class=val, eval_score=...)
  │     Evaluator 在 val 上评分并保存最佳 actor
  │
  ├─ test
  │     load_agent() + 回测 → equity_metrics()
  │
  └─ WalkForwardRun
        metrics / equity
          ├─ CSV
          ├─ Markdown
          ├─ HTML
          └─ deploy/config.json
```

---

## 2. 目标 1：消除特征处理泄漏

### 2.1 原来的问题

`_process_quant_features()` 原来对全部 `X` 做：

```python
scaler.fit(X)
q1, q3 = np.percentile(X[:, col], [25, 75])
pca.fit(X)
corr = corrcoef(X[:, col], target_returns)
```

如果 `X` 中包含验证 / 测试区间，那么：

- 均值、标准差、四分位数、PCA 主成分、特征相关性
  都使用了未来数据；
- 训练集特征已经被测试集分布“校准”过；
- 回测指标会虚高，样本外容易失效。

### 2.2 核心改动

#### `minibt/strategy/base.py::_process_quant_features`

新增参数：

```python
fit_range: tuple[int, int] | int | None = None
```

语义：

```text
None          旧行为，全样本 fit（兼容旧代码，但仍可能泄漏）
(a, b)        只用 [a, b) 拟合
n             等价于 (0, n)
```

边界处理：

```python
fit_start = max(0, min(n_samples - 1, fit_start))
fit_end = max(fit_start + 1, min(n_samples, fit_end))
```

原因：`fit_range` 可能来自原始 df，但当前 `X` 是局部 `fold.train`，
直接用原区间会切片越界或得到空切片。

各步骤改动：

| 步骤 | 原逻辑 | 新逻辑 |
|---|---|---|
| 缺失值 | 全序列插值 | 不变 |
| `clip` 异常值 | 全样本 Q1/Q3 | `X[fit_start:fit_end]` 的 Q1/Q3 |
| `mark` 异常值 | 全样本 Q1/Q3 | 训练区间 Q1/Q3 |
| log 变换 | 全样本判断非负 | 训练区间判断非负 |
| `target_returns` 特征选择 | 全样本相关 | 训练区间相关 |
| StandardScaler | 全样本 fit | 训练区间 fit |
| RobustScaler | 全样本 fit | 训练区间 fit |
| MinMaxScaler | 全样本 fit | 训练区间 fit |
| PCA | 全样本 fit | 训练区间 fit |

#### `minibt/strategy/strategy.py::set_process_quant_features`

新增同名参数，并通过 `partial` 传给底层：

```python
self.__process_quant_features = partial(
    self._process_quant_features,
    ...,
    fit_range=fit_range,
)
```

#### `minibt/elegantrl/train/walk_forward.py::Fold`

新增：

```python
@property
def fit_range(self):
    return self.window.train_start, self.window.train_end

@property
def local_fit_range(self):
    return 0, self.window.train_end - self.window.train_start
```

`local_fit_range` 用于局部 `fold.train`，避免把原始 df 的绝对 index
传到已经切片的策略数据里。

### 2.3 示例接入

`08_walk_forward.py`：

```python
policy(
    'train', fold.train,
    fit_range=fold.local_fit_range,
)
```

`05_rl_hold_days.py` 通过 `FIT_RANGE` 传入；`03` / `06` 目前仍需按需接入。

### 2.4 注意事项

- `fit_range=None` 仍然保留全样本 fit，这是为了兼容旧代码；
- 如果用户把 `target_returns` 做成未来收益特征，即使 `fit_range` 正确，
  仍然会泄漏；未来收益只能用于 reward，不能做输入特征；
- `rolling` 归一化本身就是“只用过去窗口”，不需要 `fit_range`。

---

## 3. 目标 2：独立验证环境 + 验证集选模

### 3.1 配置解析

#### `minibt/elegantrl/train/config.py::resolve_eval_env`

```python
def resolve_eval_env(args):
    env = getattr(args, 'eval_env_class', None) or getattr(
        args, 'env_class', None)
    if env is None:
        return None
    if isinstance(env, type):
        env_args = (getattr(args, 'eval_env_args', None)
                    or getattr(args, 'env_args', None) or {})
        env = build_env(env, dict(env_args), getattr(args, 'gpu_id', -1))
    return env
```

优先级：

```text
eval_env_class 是实例 → 直接使用
eval_env_class 是类   → 用 eval_env_args / env_args 构造
没有 eval_env_class   → 回退 env_class
```

### 3.2 训练入口

`minibt/elegantrl/train/run.py` 两处：

```python
eval_env = resolve_eval_env(args)
evaluator = Evaluator(cwd=args.cwd, env=eval_env, args=args, ...)
```

覆盖：

- `train_agent_single_process`
- `EvaluatorProc`（多进程）

### 3.3 Evaluator 选模

`minibt/elegantrl/train/evaluator.py`：

```python
self.eval_score = getattr(args, 'eval_score', None)
self.max_score = -np.inf
```

评分：

```python
score = avg_r
if callable(self.eval_score):
    try:
        score = float(self.eval_score(self.env))
    except Exception:
        score = avg_r

self.max_score = max(self.max_score, score)
```

保存最佳 checkpoint：

```python
if_save = score > prev_max_score
```

所以可以这样用净 Sharpe 选模：

```python
train._rl_config.eval_env_class = val
train._rl_config.eval_score = lambda env: equity_metrics(
    env._account.get_profits()
)['sharpe']
```

### 3.4 局限性

- **不是强制默认**：没有传 `eval_env_class` 时仍然回退训练环境；
- `eval_score` 默认仍是累计 reward，不是净 Sharpe；
- 验证环境的数据必须与训练环境不同，否则仍然是样本内选模。

### 3.5 训练结束自动恢复验证最优模型

原逻辑是：

```text
中途验证更优 → 保存 actor__*.pt
训练结束      → 再保存最终 act.pth
```

问题：`Strategy._get_actor()` 原来用 `find_pth_files(cwd)[0]`，
不保证选中验证最优 checkpoint；`save_best_model` 也默认复制 `act.pth`。

现在新增：

```text
minibt/elegantrl/train/evaluator.py
    best_actor_path()
    restore_best_actor()

minibt/elegantrl/train/run.py
    train_agent_single_process()
    Learner.run()
```

行为：

```text
Evaluator 验证更优
    ↓
保存 actor__*.pt
    ↓
写 cwd/best_actor.txt
    ↓
训练结束 save_or_load_agent(cwd) 保存最终模型
    ↓
restore_best_actor(cwd)
    ↓
把 best_actor.txt 指向的最优 actor 复制为 act.pth
```

所以最终：

```text
act.pth          = 验证最优 actor
actor__*.pt      = 历史最优 checkpoint（保留）
best_actor.txt   = 最优 checkpoint 路径
```

没有中途评估时，`best_actor.txt` 不存在，`act.pth` 仍是最终模型。

`Strategy._get_actor()` 也改为优先使用 `cwd/act.pth`，避免
`find_pth_files()` 遍历顺序导致误加载旧 checkpoint。

注意：`restore_best_actor()` 只复制 **actor**；critic / optimizer 仍然
是最终训练状态。如果要做“继续训练”，应使用 `continue_train` 的完整状态，
而不是只恢复 `act.pth`。

### 3.6 `fold.train` / `fold.val` / `fold.test` 三个环境的区别

很多说明会写成：

```text
训练：fold.train
中途评估：fold.val
最终测试：fold.test
```

这句话对，但容易误解成“同一个策略对象换了三份 DataFrame”。
实际不是。

#### 3.6.1 相同点：同一套策略代码

三个环境都是同一个策略类，例如 `08_walk_forward.py` 里都是：

```python
RLHoldDays
```

所以以下逻辑完全相同：

```python
__init__()
reset()
step(action)
_obs()
_hold_days()
```

它们不是三个不同的策略实现，也不是三套不同的交易逻辑。

#### 3.6.2 不同点：三个独立的 Strategy 实例

`08_walk_forward.py` 当前是：

```python
TrainPolicy = policy('train', fold.train, train=True, ...)
train = TrainPolicy()

feature_state = train.get_quant_feature_state()

ValPolicy = policy(
    'val', fold.val, train=True,
    feature_state=feature_state,
)
val = ValPolicy()

metrics, equity = run_test(
    [train.actor], fold, steps, ...,
    feature_state=feature_state,
)
```

`run_test()` 内部又会创建：

```python
TestPolicy = policy(
    'test', fold.test, train=False,
    feature_state=feature_state,
)
test = TestPolicy()
```

所以：

```text
train / val / test
    = 同一个策略类
    + 三个不同 Strategy 实例
    + 三份不同时间切片
    + 三个不同 KLine / 账户
    + 三个不同 CWD
    + 不同 TRAIN 模式
```

不是：

```text
一个 Strategy 实例
    + 三份 DataFrame
```

#### 3.6.3 对比表

| 项 | train | val | test |
|---|---|---|---|
| 策略类 | `RLHoldDays` | `RLHoldDays` | `RLHoldDays` |
| 实例 | `train` | `val` | `test` |
| 数据 | `fold.train` | `fold.val` | `fold.test` |
| `TRAIN` | `True` | `True` | `False` |
| 是否更新网络 | 是 | 否 | 否 |
| 是否真正下单 | 训练分支不下单 | 不下单 | 真正 `buy/sell` |
| 是否用于选模 | 否 | 是 | 否 |
| 是否参与训练 | 是 | 否 | 否 |
| 账户 | 独立 | 独立 | 独立 |
| KLine | 独立 | 独立 | 独立 |
| CWD | `rl_train_*` | `rl_val_*` | `rl_test_*` |
| 预处理 | fit `fold.train` | transform，复用 train state | transform，复用 train state |
| 调用者 | `train_agent()` | `Evaluator` | `run_test()` |

#### 3.6.4 数据只是时间切片

`fold.train / fold.val / fold.test` 来自同一份原始 df：

```text
原始 df
  ├─ train:  [train_start, train_end)
  ├─ purge:  丢弃若干根
  ├─ val:    [val_start, val_end)
  ├─ purge:  丢弃若干根
  └─ test:   [test_start, test_end)
```

`purge` 的作用是避免训练 / 验证 / 测试边界共享未来信息。

所以“只是数据集不同”这句话只对了一半：

```text
数据不同：✓
但运行模式、实例、账户、预处理状态也不同：✓
```

#### 3.6.5 为什么 val 也是 `TRAIN=True`

`RLHoldDays.step()` 里：

```python
if self.train:
    # 只计算 reward，不真正 buy/sell
else:
    # 推理：真正调用 data.buy() / data.sell()
```

验证需要的是：

```text
用同一个策略逻辑
    ↓
在 fold.val 上算 reward / 指标
    ↓
给 Evaluator 选 checkpoint
```

它不需要更新网络，也不需要真实成交，所以：

```text
val.TRAIN = True
```

但 val 不会调用：

```python
train_agent()
```

因此它不是训练环境，只是一个“按训练分支运行的评估环境”。

test 则相反：

```text
test.TRAIN = False
```

因为它要模拟真实持仓、真实买卖和最终权益曲线。

#### 3.6.6 预处理状态如何复用

现在 `08` 的顺序是：

```text
1. train 实例 __init__
2. train._prepare_before_strategy_start()
3. train 在 fold.train 上 fit scaler / PCA / 异常值阈值 / 保留列
4. train.get_quant_feature_state()
5. val 实例构造时注入该 state
6. test 实例构造时注入该 state
7. val / test 只 transform，不再 fit
```

对应代码：

```python
feature_state = train.get_quant_feature_state()

ValPolicy = policy(
    'val', fold.val, train=True,
    feature_state=feature_state,
)

metrics, equity = run_test(
    [train.actor], fold, steps, ...,
    feature_state=feature_state,
)
```

`05_rl_hold_days.py` 里：

```python
FEATURE_STATE = None

self.set_process_quant_features(...)
if self.FEATURE_STATE is not None:
    self.set_quant_feature_state(self.FEATURE_STATE)
```

`set_quant_feature_state()` 会把 train 的：

```text
scaler
PCA
outlier_lower / outlier_upper
log_cols
keep_cols
normalize_method
feature_range
```

带到 val / test，`_process_quant_features()` 只做 transform：

```python
if feature_state is not None:
    scaler.transform(X)
    pca.transform(X)
```

不再执行：

```python
scaler.fit(X[fit_start:fit_end])
pca.fit(X[fit_start:fit_end])
```

这样才真正做到：

```text
val / test 不参与 train 的统计量计算
val / test 使用与 train 完全相同的预处理参数
```

#### 3.6.7 Evaluator 用的是哪一个环境

`Evaluator` 构造时：

```python
eval_env = resolve_eval_env(args)
evaluator = Evaluator(cwd=args.cwd, env=eval_env, args=args)
```

`resolve_eval_env` 的优先级：

```text
eval_env_class 是实例 → 使用 val 实例
eval_env_class 是类   → 构造
没有设置              → 回退训练环境
```

`08` 明确设置：

```python
train._rl_config.eval_env_class = val
```

所以：

```text
训练 env     = train
Evaluator env = val
最终 test env = test
```

如果没有设置 `eval_env_class`，例如直接运行 `05_rl_hold_days.py`：

```text
训练 env     = train
Evaluator env = train
```

这时中途评估仍然在训练集上，不是独立验证集。

#### 3.6.8 一句话总结

```text
train / val / test
    = 同一套策略代码
    + 三个独立 Strategy 实例
    + 三段按时间切分的数据
    + 不同的 TRAIN 模式 / 账户 / CWD
    + val/test 复用 train 的预处理状态
```

---


## 4. 目标 3：时间序列切分 / walk-forward

### 4.1 `minibt/elegantrl/train/splits.py`

提供：

```python
TimeWindow
split_indices()
split_dataframe()
walk_forward_windows()
```

`TimeWindow` 使用半开区间：

```python
window.train  # slice
window.val    # slice
window.test   # slice
```

`split_dataframe`：

```python
train_df, val_df, test_df = split_dataframe(
    df, train=0.6, val=0.2, purge=60)
```

`purge` 的作用：

```text
train_end + purge → val_start
val_end   + purge → test_start
```

防止相邻窗口共享未来信息。

### 4.2 `minibt/elegantrl/train/walk_forward.py`

提供：

```python
Fold
make_folds()
run_walk_forward()
WalkForwardRun
run_walk_forward_ensemble()
runs_to_frame()
summarize_runs()
save_runs_csv()
```

`make_folds`：

```python
for fold in make_folds(
        df,
        train_size=1200, val_size=300, test_size=300,
        step=300, purge=60):
    ...
```

`run_walk_forward` 是回调式执行器：

```python
def make_strategy(frame):
    return MyPolicy(DATA=frame)()

def train_one(train, val, test):
    train._rl_config.eval_env_class = val
    train.train_agent()
    return train

for fold, result in run_walk_forward(
        df, make_strategy, train_one,
        train_size=1200, val_size=300, test_size=300,
        step=300, purge=60):
    ...
```

`run_walk_forward_ensemble` 在 fold 上增加多 seed：

```python
runs = run_walk_forward_ensemble(
    df, make_strategy, train_one,
    seeds=(42, 43, 44),
    train_size=1200, val_size=300, test_size=300,
    step=300, purge=60,
)
```

### 4.3 `RlExperiment`

`minibt/elegantrl/train/experiment.py`：

```python
exp = RlExperiment(
    df, make_strategy, train_one,
    seeds=(42, 43, 44),
    train_size=1200, val_size=300, test_size=300,
    step=300, purge=60,
)
runs = exp.walk_forward()
exp.save_csv('results/wf.csv')
exp.save_report('results/wf.md')
exp.save_html('results/wf.html')
exp.deploy('results/deploy')
```

`Bt` 薄门面：

```python
exp = Bt(auto=False).rl_experiment(
    df, make_strategy, train_one,
    seeds=(42, 43), train_size=1200,
    val_size=300, test_size=300, purge=60,
)
```

分层：

```text
Strategy        单模型
RlExperiment    多 fold / 多 seed / 报告 / 部署
Bt              用户入口
```

### 4.4 说明

框架没有提供随机切分函数，也没有强制禁止调用者自己随机切分；
工具层只保证 **按时间顺序** 切分。

---

## 5. 目标 4：成本化 reward

### 5.1 新增 `minibt/elegantrl/train/reward.py`

#### `RewardConfig`

```python
@dataclass
class RewardConfig:
    commission_rate: float = 0.0   # 每单位换手手续费
    slippage_rate: float = 0.0     # 每单位换手滑点
    risk_penalty: float = 0.0      # 回撤惩罚系数
    reward_scale: float = 1.0
    min_equity: float = 1e-9
```

#### `compute_reward`

```python
net = gross
      - commission_rate * turnover
      - slippage_rate * turnover
      - risk_penalty * abs(drawdown)
```

其中：

```python
turnover = abs(position - prev_position)
gross = position * next_return          # 默认
gross = gross_return                    # 已自行算好价差收益时
drawdown = min(0, equity / peak_equity - 1)
```

#### `RewardBreakdown`

返回：

```python
gross / commission / slippage / risk / net / turnover / drawdown
```

用于回答：

```text
这步到底是行情赚的，还是成本亏的？
风险惩罚占了多少？
```

#### `RewardModel`

维护：

```python
equity
peak_equity
drawdown
```

每步先算净奖励，再更新权益：

```python
equity = equity * (1 + net)
peak_equity = max(peak_equity, equity)
```

适合奖励本身是“收益率”的场景。

### 5.2 示例接入

#### `03_rl_position.py`

```python
self._reward = RewardModel(RewardConfig(
    commission_rate=0.0002,
    slippage_rate=0.0001,
    risk_penalty=0.05,
))

reward = self._reward.step(
    prev_position, target, next_return)
```

奖励：

```text
下一根收益
- 手续费
- 滑点
- 回撤惩罚
```

#### `05_rl_hold_days.py`

`long_prices` 从“价格差”改为“收益率”：

```python
close.pct_change().shift(-i)
```

这样 reward、手续费、滑点、回撤惩罚都使用同一比例口径。

```python
reward = self._reward.step(prev_position, self._target, gross)
```

#### `06_rl_pair.py`

价差收益已经自己算好，所以使用：

```python
reward = compute_reward(
    prev_pos, self.pos,
    gross_return=raw_reward,
    equity=self._equity,
    peak_equity=self._peak_equity,
    config=self._reward_config,
)
```

成本按两条腿换手计算，风险按价差权益回撤计算。

### 5.3 还需注意

- `KLine.fixed_commission` 是回测账户成本，不等于 reward 里的成本；
- 训练 reward 的成本必须和实盘 / 回测成本口径一致；
- 当前没有把“波动率惩罚”单独建模，只用了回撤惩罚；
- 成本参数应通过回测 / 实盘成交数据校准，而不是拍脑袋。

---

## 6. 目标 5：完整持仓状态

### 6.1 新增 `minibt/elegantrl/train/state.py`

#### `PositionState`

```python
@dataclass
class PositionState:
    position: float = 0.0
    holding_days: int = 0
    unrealized_pnl: float = 0.0
    drawdown: float = 0.0
```

`features()` 输出固定 4 维：

```text
[position, holding_days, unrealized_pnl, drawdown]
```

默认归一化：

```text
position      / max_abs_position  → [-1, 1]
holding_days  / max_holding_days  → [0, 1]
unrealized    clip [-1, 1]
drawdown      clip [-1, 0]
```

`append_state_features()`：

```python
return np.hstack([obs.flatten(), state.features()])
```

### 6.2 示例接入

#### `03_rl_position.py`

状态：

```text
指标窗口 + 仓位 + 持仓天数 + 浮盈 + 回撤
```

训练和推理都更新：

```python
self._position
self._holding_days
self._entry_price
self._unrealized
self._drawdown
```

#### `05_rl_hold_days.py`

状态从原来的：

```text
指标窗口 + [pos, hold]
```

升级为：

```text
指标窗口 + [pos, hold, unrealized_pnl, drawdown]
```

训练分支用 `RewardModel.drawdown`，推理分支用真实持仓和入场价计算浮盈。

#### `06_rl_pair.py`

价差状态：

```text
价差指标窗口 + 价差仓位 + 持仓天数 + 价差浮盈 + 价差权益回撤
```

### 6.3 为什么不用原始价格做 state

不建议把“当前价格绝对值”直接塞进状态：

- 不同品种价格量级不同；
- 同一品种不同年份价格中枢不同；
- 网络会把“价格高低”误当成信号。

所以这里统一使用：

```text
仓位方向
持仓天数比例
浮盈收益率
回撤比例
```

---

## 7. 目标 6：小样本训练策略

### 7.1 新增 `minibt/elegantrl/train/small.py`

```python
SMALL_NET_DIMS = (64, 32)
TINY_NET_DIMS = (32, 32)

SMALL_DISCRETE_AGENTS = (
    'discrete-ppo', 'd3qn', 'double-dqn',
    'dueling-dqn', 'ensemble-dqn',
)
```

`small_model_kwargs()` 默认：

```python
net_dims=(64, 32)
batch_size=64
horizon_len=128
repeat_times=2.0
eval_per_step=5e3
eval_times=1
gpu_id=-1
num_workers=1
num_threads=1
dropout_rate=0.1
random_seed=42
min_start_mode='random'
```

`apply_small_model_params(strategy, agent, **kwargs)` 是便捷封装。

### 7.2 示例接入

- `03_rl_position.py`：`AgentDiscretePPO` + `(64, 32)` + 随机起点；
- `05_rl_hold_days.py`：默认 `discrete-ppo` + `(64, 32)` + 随机起点；
- `06_rl_pair.py`：`AgentDiscretePPO` + `(64, 32)` + 随机起点。

### 7.3 多 seed / ensemble

`minibt/elegantrl/train/ensemble.py`：

```python
seed_list(3)          # (42, 43, 44)
seed_dir(base, seed)  # base_seed42
train_seed_ensemble() # 每个 seed 独立训练
aggregate_actions()   # 离散多数投票 / 连续平均
```

`08_walk_forward.py`：

```text
fold × seed
```

`09_rl_ensemble.py`：

```text
多个 actor 分别在 test 上评估
    ↓
aggregate_actions(if_discrete=True)
    ↓
ensemble 指标 + 最佳单 actor
```

`11_rl_experiment.py`：

```text
RlExperiment / Bt.rl_experiment 高层入口
```

### 7.4 随机起点

`minibt/strategy/base.py::rl_reset_index()`：

```text
fixed        固定 min_start_length
random       [base, min(2*base, max_step-1)] 随机
incremental  从 base 开始逐次 +1，直到 max_step//2
```

示例 `03 / 05 / 06` 的 `reset()` 已改为：

```python
self.current_step = self.rl_reset_index()
```

这样训练不会只适配一个固定起点。

---

## 8. 新增 / 修改文件清单

### 新增

```text
minibt/elegantrl/train/splits.py          时间切分
minibt/elegantrl/train/walk_forward.py    fold / walk-forward 执行器
minibt/elegantrl/train/metrics.py         净收益 / Sharpe / 回撤
minibt/elegantrl/train/reward.py          成本化 reward
minibt/elegantrl/train/state.py           持仓状态
minibt/elegantrl/train/small.py           小样本默认参数
minibt/elegantrl/train/ensemble.py        多 seed / 动作聚合
minibt/elegantrl/train/report.py          Markdown / HTML 报告
minibt/elegantrl/train/deploy.py          最佳模型部署
minibt/elegantrl/train/experiment.py      RlExperiment 门面
```

### 修改

```text
minibt/strategy/base.py                   fit_range / rl_reset_index
minibt/strategy/strategy.py               set_process_quant_features / eval_score
minibt/elegantrl/train/config.py          resolve_eval_env / eval 配置
minibt/elegantrl/train/run.py             独立 eval_env 接入
minibt/elegantrl/train/evaluator.py       eval_score / max_score 选模
minibt/bt.py                              rl_experiment 薄门面
minibt/elegantrl/train/__init__.py        导出新工具
```

### 示例

```text
tutorials/elegantrl/03_rl_position.py
tutorials/elegantrl/05_rl_hold_days.py
tutorials/elegantrl/06_rl_pair.py
tutorials/elegantrl/08_walk_forward.py
tutorials/elegantrl/09_rl_ensemble.py
tutorials/elegantrl/10_deploy_inference.py
tutorials/elegantrl/11_rl_experiment.py
tutorials/elegantrl/_rl_common.py
```

### 测试

```text
tests/test_minibt_elegantrl_refactor.py
tests/test_minibt_elegantrl_examples.py
```

---

## 9. 落地状态

| 目标 | 状态 | 说明 |
|---|---|---|
| 1. 特征处理不泄漏 | ✅ 核心 | `fit_range` 贯穿 scaler / 异常值 / PCA / 特征选择；`None` 保持旧行为 |
| 2. 独立验证 + 验证选模 | ✅ 机制 | `resolve_eval_env` + `eval_score`；未配置时回退训练环境 |
| 3. 时间切分 / walk-forward | ✅ | `splits` + `walk_forward` + `RlExperiment` |
| 4. 成本化 reward | ✅ | `RewardConfig` / `compute_reward` / `RewardModel`；03/05/06 已接入 |
| 5. 完整持仓状态 | ✅ | `PositionState`；03/05/06 已接入 |
| 6. 小样本训练 | ✅ 基础 | 小网络 / 离散动作 / 随机起点 / 多 seed / ensemble |

仍然建议继续做：

1. 用真实成交数据校准 `commission_rate` / `slippage_rate`；
2. 增加波动率惩罚 / 保证金占用状态；
3. 对 `test` 做泄漏检查：打乱 test、去掉未来特征、检查特征 IC；
4. 把 `08/09` 的编排逐步统一到 `RlExperiment`；
5. 给 `03/05/06` 增加 `fit_range` 的显式示例（目前核心 API 已有，
   但 03/06 单跑时仍可全样本 fit）；
6. `11_rl_experiment.py` 的 role-aware 工厂目前还可以进一步把 train 的
   `feature_state` 自动传给 val / test；`08/09` 已显式复用。

---

## 10. 最小使用示例

```python
from minibt.elegantrl.train import (
    PositionState, RewardConfig, RewardModel,
    append_state_features, compute_reward,
    make_folds, split_dataframe, small_model_kwargs,
)

# 1) 时间切分
train_df, val_df, test_df = split_dataframe(
    df, train=0.6, val=0.2, purge=60)

# 2) 特征只拟合 train
self.set_process_quant_features(
    normalize_method='robust',
    fit_range=(0, len(train_df)),
)

# 3) 成本化 reward
reward_model = RewardModel(RewardConfig(
    commission_rate=0.0002,
    slippage_rate=0.0001,
    risk_penalty=0.05,
))
reward = reward_model.step(prev_pos, pos, next_return)

# 4) 状态补全
state = PositionState(
    position=pos,
    holding_days=hold,
    unrealized_pnl=unrealized,
    drawdown=reward_model.drawdown,
)
obs = append_state_features(indicator_window, state)

# 5) 小样本配置
self.set_model_params(
    AgentDiscretePPO,
    **small_model_kwargs(
        if_discrete=True,
        action_dim=3,
        min_start_mode='random',
    ),
)

# 6) walk-forward × 多 seed
from minibt.elegantrl.train import RlExperiment

exp = RlExperiment(
    df, make_strategy, train_one,
    seeds=(42, 43, 44),
    train_size=1200, val_size=300, test_size=300,
    step=300, purge=60,
)
runs = exp.walk_forward()
exp.save_report('results/wf.md')
exp.deploy('results/deploy')
```
