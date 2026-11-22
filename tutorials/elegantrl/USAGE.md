# ElegantRL 在 minibt 中的具体用法

本文只讨论 **minibt 当前内置的 ElegantRL 集成**：从训练、验证、模型再训练
（同数据微调 / 新数据微调），到部署和实盘接入。

> 结论先记住：**静态参数优化用 Optuna / Cython，动态动作策略用 ElegantRL。**
> 相关背景见 [4.8 ElegantRL、参数优化与交易扩展](../../minibt_docs/docs/minibt_reinforcement_learning/4.8_elegantrl_parameter_optimization.md)。

---

## 0. 目录与最小依赖

```text
minibt/elegantrl/
├── agents/          # AgentPPO / DQN / SAC / TD3 / EnsembleDQN ...
├── envs/            # StockTradingEnv / 示例环境
└── train/           # train_agent / Evaluator / Config
```

```python
from minibt import Agents, BestAgents, Bt, Gui, LocalDatas, Strategy
```

RL 依赖：

```bash
pip install torch gymnasium
```

---

## 1. 环境契约：Strategy 就是 RL 环境

### 1.1 必须实现

```python
class MyRLStrategy(Strategy):
    rl = True

    def reset(self):
        """返回 (observation, info)"""
        self.current_step = self.rl_reset_index()
        return self._obs(), {}

    def step(self, action):
        """返回 (obs, reward, terminated, truncated, info)"""
        ...
        return self._obs(), reward, done, False, {}
```

### 1.2 关键规则

| 项 | 说明 |
|---|---|
| `reset()` | 每个 episode 开始调用；返回 `(obs, info)` |
| `step(action)` | RL 训练时**不会调用 `next()`** |
| `state` / `next_state` | 默认从 `signal_features` 切片；也可自定义 `_obs()` |
| `min_start_length` | 指标预热，避免 NaN / 未来数据 |
| `rl_reset_index()` | 支持 `fixed / random / incremental` 起点 |
| `if_discrete` | 离散动作 → DQN / DiscretePPO；连续 → PPO / SAC / DDPG / TD3 |
| `action_dim` | 离散=动作个数；连续=动作维度 |

### 1.3 训练环境与普通回测分离

同一个策略类可以：

```python
rl = True    # RL 环境
rl = False   # 普通 next() 回测
```

但**不要**同时依赖 `next()` 和 `step(action)` 的同一套逻辑。  
建议写成两个类，或把决策逻辑抽成共享 helper。

---

## 2. 训练

### 2.1 最小训练流程

```python
from minibt import Agents, Bt, LocalDatas, Strategy


class Policy(Strategy):
    rl = True

    def __init__(self):
        self.data = self.get_kline(LocalDatas.test, data_length=1200)
        self.ma = self.data.close.sma(20)
        self.rsi = self.data.close.rsi(14)

        self.min_start_length = 120
        self.current_step = self.min_start_length

        self.set_model_params(
            agent=Agents.AgentDiscretePPO,
            train=True,
            window_size=10,
            if_discrete=True,
            action_dim=3,
            break_step=100_000,
            batch_size=128,
            horizon_len=512,
            repeat_times=4.0,
            net_dims=(64, 32),
            learning_rate=6e-5,
            gamma=0.985,
            gpu_id=0,
            cwd='./models/policy',
            if_remove=True,
            random_seed=42,
        )

    def _obs(self):
        end = self.current_step + 1
        return self.signal_features[end - self.window_size:end].flatten()

    def reset(self):
        self.current_step = self.rl_reset_index()
        self._btindex = self.current_step
        return self._obs(), {}

    def step(self, action):
        # 动作 → 目标仓位 / 买卖
        ...
        self.current_step += 1
        return self._obs(), reward, self.current_step >= self.max_step, False, {}
```

启动训练：

```python
if __name__ == '__main__':
    Bt(auto=False).addstrategy(Policy).run(isplot=False)
```

`Bt.run()` 内部会：

```text
_prepare_before_strategy_start()
    → train_agent()
    → load_agent()
    → _execute_core_trading_loop()
```

也可以手动：

```python
strategy = Policy()
strategy._prepare_before_strategy_start()
strategy.train_agent()
strategy.load_agent()
```

### 2.2 训练前先处理特征

```python
self.set_process_quant_features(
    normalize_method='robust',
    use_log_transform=True,
    handle_outliers='clip',
    fit_range=(0, n_train),   # ★ 只用训练区间 fit
)
```

- `fit_range=None`：旧行为，全样本 fit（会泄漏测试集）
- 推荐 `fit_range=(0, n_train)` 或 `normalize_method='rolling'`
- 不要用 `shift(-n)` 的列做**特征**；未来收益只能做 **reward**

### 2.3 离散 / 连续动作

```python
# 离散：空 / 平 / 多
set_model_params(Agents.AgentDiscretePPO, if_discrete=True, action_dim=3)

# 连续：目标仓位
set_model_params(Agents.AgentPPO, if_discrete=False, action_dim=1)
```

小样本优先：

```text
AgentDiscretePPO / AgentD3QN / AgentDoubleDQN / AgentEnsembleDQN
```

数据量足够再考虑 SAC / DDPG / TD3。

### 2.4 训练 reward 至少包含

```text
prev_position * next_return
- commission * turnover
- slippage * turnover
- risk_penalty(drawdown / volatility)
```

不要只看“未来价格差”；旧示例里 `fixed_commission=0` 时训练出的策略，
实盘加成本后很容易失效。

---

## 3. 验证

### 3.1 不要用训练集做验证

最差的做法：

```text
train 8000 根 → test 还是这 8000 根
```

推荐：

```python
from minibt.elegantrl.train import split_dataframe

train_df, val_df, test_df = split_dataframe(
    df, train=0.6, val=0.2, purge=60,
)
```

`purge >= window_size + reward_horizon`，否则相邻窗口共享未来信息。

### 3.2 独立 validation + 验证评分

```python
train_strategy.set_model_params(
    Agents.AgentDiscretePPO,
    eval_env_class=val_strategy,
    eval_score=lambda env: __import__(
        'minibt.elegantrl.train', fromlist=['equity_metrics']
    ).equity_metrics(env._account.get_profits())['sharpe'],
    ...
)
```

或更清晰：

```python
from minibt.elegantrl.train import equity_metrics


def val_score(env):
    return equity_metrics(env._account.get_profits())['sharpe']


train_strategy.set_model_params(
    ...,
    eval_env_class=val_strategy,
    eval_score=val_score,
)
```

`Evaluator` 会：

- 在 `val_strategy` 上 `avgR`
- 用 `eval_score` 选最佳 checkpoint
- 把最佳模型保存为 `actor__<step>_<score>.pt`

### 3.3 Walk-forward

```python
from minibt.elegantrl.train import make_folds, run_walk_forward

folds = list(make_folds(
    df, train_size=1200, val_size=300, test_size=300,
    step=300, purge=60,
))

for fold in folds:
    train = make_policy(fold.train, fit_range=fold.local_fit_range)
    val = make_policy(fold.val)
    test = make_policy(fold.test)
    ...
```

高层编排：

```python
from minibt.elegantrl.train import run_walk_forward_ensemble

runs = list(run_walk_forward_ensemble(
    df,
    make_strategy,       # (frame, seed) -> Strategy
    train_one,          # (train, val, test, seed) -> result
    seeds=(42, 43, 44),
    train_size=1200, val_size=300, test_size=300,
    step=300, purge=60,
))
```

### 3.4 报告 / 选优

```python
from minibt.elegantrl.train import (
    best_runs, best_seed, save_runs_csv,
    save_walk_forward_report, save_walk_forward_html, summarize_runs,
)

print(summarize_runs(runs))
print('best seed:', best_seed(runs))
print('best run:', best_runs(runs, n=1))
save_runs_csv(runs, './results/wf.csv')
save_walk_forward_report(runs, './results/wf.md')
save_walk_forward_html(runs, './results/wf.html')
```

---

## 4. 模型再训练

这里要区分两种“继续”：

| 目标 | 做法 |
|---|---|
| 同一数据继续训练 | `continue_train=True`，从原 `cwd` 加载 |
| 新数据微调 | 新建策略 + 复制模型到新 `cwd` + `continue_train=True` |
| 只加载模型推理 | `train=False` + `actor_path=...` + `load_agent()` |

### 4.1 同数据继续训练

`train_agent_single_process` 在：

```python
if args.continue_train and args.train:
    agent.save_or_load_agent(args.cwd, if_save=False)
```

会从 **`cwd`** 读取：

```text
act.pth / cri.pth / act_optimizer.pth / ...
```

所以：

```python
strategy.set_model_params(
    Agents.AgentDiscretePPO,
    train=True,
    continue_train=True,   # ★
    if_remove=False,       # ★ 千万不要删 cwd
    cwd='./models/policy', # 原来的模型目录
    actor_path='',         # 这里不是继续训练的入口
    ...
)
strategy.train_agent()
```

注意：

- `if_remove=True` 会先删除 `cwd`，把要继续训练的模型删掉。
- `continue_train` 不读取 `actor_path`；`actor_path` 是 `load_agent()` 推理用的。
- 最好用 `train_agent_single_process` 语义 / `train_agent` 默认单进程，排查更直接。

### 4.2 新数据微调

新数据（新品种 / 新时间段 / 新频率）通常建议：

```text
旧模型 → 复制到新 cwd → 新策略使用新数据 → continue_train=True → 小学习率
```

示例：

```bash
cp -r models/policy models/policy_ft_newdata
```

```python
class FineTunePolicy(Policy):
    # 用新数据的 get_kline / DATA
    ...

policy = FineTunePolicy()
policy.set_model_params(
    Agents.AgentDiscretePPO,
    train=True,
    continue_train=True,
    if_remove=False,
    cwd='./models/policy_ft_newdata',
    learning_rate=2e-5,     # 比原训练小
    break_step=20_000,      # 少量微调
    ...
)
policy.train_agent()
```

必须保证：

- `state_dim` / `action_dim` / 特征顺序完全一致
- 网络结构 `net_dims` 完全一致
- 特征归一化参数尽量固定（最好保存训练期 scaler）

### 4.3 只加载模型推理

```python
policy.set_model_params(
    Agents.AgentDiscretePPO,
    train=False,
    if_remove=False,
    cwd='./models/policy',
    actor_path='./models/policy/act.pth',
    ...
)
policy.load_agent()
```

`load_agent()` 会：

- `train=False`
- `if_remove=False`
- 初始化 actor
- 加载 `actor_path`
- `actor.eval()`

### 4.4 新数据不能直接微调的情况

如果出现以下变化，不要 `continue_train`，应重新训练：

- 特征列数量 / 顺序变化
- `state_dim` / `action_dim` 变化
- 从离散动作换成连续动作
- 合约乘数 / tick / 交易规则变化导致 reward 含义变化
- 市场微观结构发生根本性变化

---

## 5. 部署

### 5.1 部署目录

推荐由 `08_walk_forward.py --deploy` 生成：

```text
results/deploy/
├── actor.pth
└── config.json
```

`config.json` 包含：

```text
seed / metric / score / fit_range
agent / net_dims / state_dim / action_dim / if_discrete
actor_path / metrics / fold
```

### 5.2 独立验证 / 回测

```bash
python tutorials/elegantrl/10_deploy_inference.py \
    --config results/deploy/config.json --check

python tutorials/elegantrl/10_deploy_inference.py \
    --config results/deploy/config.json
```

或代码：

```python
from minibt.elegantrl.train import load_best_actor

actor, config = load_best_actor('results/deploy', device='cpu')
print(config['seed'], config['metrics'])
```

### 5.3 实盘接入（天勤）

实盘策略仍使用 `Strategy.rl = True` + `step(action)`，只是：

```text
train=False
actor_path=部署 actor
KLine 来自实盘 get_kline
step 里 set_target_size / buy / sell
```

骨架：

```python
from tqsdk import TqApi, TqAuth, TqKq
from minibt import Agents, Bt, Gui, Strategy


class LivePolicy(Strategy):
    rl = True

    def __init__(self):
        self.data = self.get_kline(
            'SHFE.ag2612', duration_seconds=60, data_length=1000)
        self.min_start_length = 120
        self.set_model_params(
            Agents.AgentDiscretePPO,
            train=False,
            actor_path='./results/deploy/actor.pth',
            cwd='./results/deploy',
            if_remove=False,
            window_size=10,
            if_discrete=True,
            action_dim=3,
            ...
        )

    def reset(self):
        self.current_step = self.min_start_length
        return self._obs(), {}

    def step(self, action):
        # 只做推理：动作 → set_target_size
        # 不要在这里重新 train_agent
        ...


api = TqApi(TqKq(), auth=TqAuth('账号', '密码'))
bt = Bt(live=True, auto=False)
bt.addTqapi(api=api)
bt.addstrategy(LivePolicy)
bt.run(gui=Gui.Desk)   # 或 Gui.Pylightcharts
```

实盘前必须：

- 先用 `10_deploy_inference.py` 复现 test 指标
- 先跑快期模拟（`TqKq`）或 desk 模拟账户
- 设置 `allow_trading` / 手数上限 / 最大回撤 / 手动 kill switch
- 监控滑点、成交、拒单和模型漂移

### 5.4 部署检查清单

- [ ] `config.json` 的 `seed / fold / fit_range` 可追溯
- [ ] `state_dim / action_dim / if_discrete` 与实盘策略一致
- [ ] 特征 scaler / 指标顺序与训练一致
- [ ] 独立 test 指标已复现
- [ ] 模拟盘至少跑过一个完整交易时段
- [ ] 手续费 / 滑点 / 涨跌停 / 保证金已纳入
- [ ] 有最大仓位、最大回撤、停止交易开关
- [ ] 定期用新数据做 walk-forward，不用单次样本内结果直接上线

---

## 6. 日常迭代流程

```text
1. 更新数据
2. 用训练区间 fit 特征
3. walk-forward 训练 / 验证
4. 多 seed + ensemble
5. 选 best run / best seed
6. 生成 deploy/actor.pth + config.json
7. 10_deploy_inference 复现 test
8. 模拟盘 / 小资金验证
9. 监控漂移，定期微调或重训
```

不要跳过第 3、7、8 步。

---

## 7. 相关示例

```text
tutorials/elegantrl/03_rl_position.py       # 最小 RL 环境
tutorials/elegantrl/05_rl_hold_days.py      # 多指标 / 持仓天数
tutorials/elegantrl/06_rl_pair.py           # 配对价差
tutorials/elegantrl/07_rl_load_actor.py     # 加载 actor 推理
tutorials/elegantrl/08_walk_forward.py      # walk-forward + 报告 + deploy
tutorials/elegantrl/09_rl_ensemble.py       # 多 seed ensemble
tutorials/elegantrl/10_deploy_inference.py  # 部署目录复现 test
```

相关文档：

- [4.1 RL 使用指南](../../minibt_docs/docs/minibt_reinforcement_learning/4.1reinforcement_learning_for_quantitative_trading_with_minibt.md)
- [4.2 RL 参数配置](../../minibt_docs/docs/minibt_reinforcement_learning/4.2the_complete_parameter_tuning_guide.md)
- [4.7 Agent 速查](../../minibt_docs/docs/minibt_reinforcement_learning/4.7agent_selection_cheatsheet.md)
- [4.8 参数优化与交易扩展](../../minibt_docs/docs/minibt_reinforcement_learning/4.8_elegantrl_parameter_optimization.md)
- [`minibt/elegantrl/REFACTOR_PLAN.md`](../../minibt/elegantrl/REFACTOR_PLAN.md)

## 训练结束自动恢复最优模型

有中途验证时，`Evaluator` 会把验证评分最高的 actor 保存为：

```text
cwd/actor__<step>_<score>.pt
```

并写入 `cwd/best_actor.txt`。训练结束保存最终模型后，
`restore_best_actor(cwd)` 会把验证最优 actor 复制为 `cwd/act.pth`：

```text
act.pth          = 验证最优 actor
actor__*.pt      = 历史最优 checkpoint
best_actor.txt   = 最优 checkpoint 路径
```

没有中途评估时不会生成 `best_actor.txt`，`act.pth` 仍是最终模型。

因此 `load_agent()` / `save_best_model()` 默认拿到的 `act.pth` 就是验证最优。
