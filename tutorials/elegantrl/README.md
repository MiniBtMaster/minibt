# tutorials/elegantrl —— 参数优化与强化学习

> 完整用法（训练 / 验证 / 再训练 / 实盘部署）：[`USAGE.md`](USAGE.md)

结论先看这里：**ElegantRL 不是静态参数优化器**。

| 例子 | 演示 | 引擎 | 默认运行时间 |
| --- | --- | --- | --- |
| [`01_next_optuna.py`](01_next_optuna.py) | 含 `next()` 的 Strategy 参数优化 | Optuna / Strategy 回测 | 几秒～几十秒 |
| [`02_signal_cython_optimize.py`](02_signal_cython_optimize.py) | `BtIndicator` 信号参数优化 | Cython `from_signals` | 几秒 |
| [`03_rl_position.py`](03_rl_position.py) | ElegantRL 动态仓位（离散动作） | AgentDiscretePPO | 约几秒（64 步） |
| [`04_parameter_bandit.py`](04_parameter_bandit.py) | 参数 preset bandit（UCB 原型） | Cython 评估 + UCB | 几秒 |
| [`05_rl_hold_days.py`](05_rl_hold_days.py) | 旧 `77_*` 整理：持仓天数 + 多指标特征，支持 DQN/PPO/DDPG/SAC/TD3 | ElegantRL | 默认 `STEPS=5e4`；演示用 `--steps 64` |
| [`06_rl_pair.py`](06_rl_pair.py) | 旧 `77_31 / 78_1` 整理：配对价差 RL | AgentDiscretePPO | 约几秒（64 步） |
| [`07_rl_load_actor.py`](07_rl_load_actor.py) | 旧 `77_1 / 700005` 整理：加载 actor 推理 | 已训练模型 | 约几秒 |
| [`08_walk_forward.py`](08_walk_forward.py) | 一折 walk-forward：train / val / test 独立环境 | ElegantRL | 约几秒（64 步） |
| [`09_rl_ensemble.py`](09_rl_ensemble.py) | 多 seed actor：单 actor / ensemble 对比、最佳 seed 选择 | ElegantRL + aggregate_actions | 约几秒（32 步） |
| [`10_deploy_inference.py`](10_deploy_inference.py) | 从 08 的部署目录加载 actor，复现 test 推理 | `load_best_actor` | 约几秒 |
| [`11_rl_experiment.py`](11_rl_experiment.py) | `RlExperiment` / `Bt.rl_experiment` 高层入口 | walk-forward / 报告 / deploy | 8 fold × 步数 |

## 运行

```bash
# 只检查配置，不训练 / 不优化
python tutorials/elegantrl/01_next_optuna.py --check
python tutorials/elegantrl/02_signal_cython_optimize.py --check
python tutorials/elegantrl/03_rl_position.py --check
python tutorials/elegantrl/04_parameter_bandit.py --check
python tutorials/elegantrl/05_rl_hold_days.py --check
python tutorials/elegantrl/06_rl_pair.py --check
python tutorials/elegantrl/07_rl_load_actor.py --check   # 需要先训练 05
python tutorials/elegantrl/08_walk_forward.py --check
python tutorials/elegantrl/09_rl_ensemble.py --check
python tutorials/elegantrl/10_deploy_inference.py --check   # 先运行 08 --deploy
python tutorials/elegantrl/11_rl_experiment.py --check

# 小规模真实运行
python tutorials/elegantrl/01_next_optuna.py                 # 6 trials
python tutorials/elegantrl/02_signal_cython_optimize.py      # 9 组网格
python tutorials/elegantrl/03_rl_position.py --steps 64      # 64 步训练
python tutorials/elegantrl/04_parameter_bandit.py            # UCB 选择
python tutorials/elegantrl/05_rl_hold_days.py --agent d3qn --steps 64
# 不传 --steps 时使用文件里的 STEPS（当前 5e4）
python tutorials/elegantrl/06_rl_pair.py --steps 64
python tutorials/elegantrl/08_walk_forward.py --steps 64
python tutorials/elegantrl/08_walk_forward.py --all-folds --steps 64 \
    --csv results/wf.csv --report results/wf.md \
    --html results/wf.html \
    --deploy results/deploy
python tutorials/elegantrl/09_rl_ensemble.py --steps 32 --seeds 2 \
    --csv results/ens.csv --report results/ens.md --html results/ens.html
python tutorials/elegantrl/10_deploy_inference.py \
    --config results/deploy/config.json
python tutorials/elegantrl/11_rl_experiment.py --steps 32 --bt

# 更大规模（会慢一些）
python tutorials/elegantrl/01_next_optuna.py --full
python tutorials/elegantrl/02_signal_cython_optimize.py --full
python tutorials/elegantrl/03_rl_position.py --steps 512
```

## 三条路线

```text
Strategy.next() 静态参数
    → Bt.optstrategy(target=..., op_method='optuna', **参数范围)

BtIndicator 信号参数
    → signal_backtest(optimize=OptimizeConfig(...))
    → Cython from_signals

动态买卖 / 仓位 / 止损
    → Strategy.rl = True
    → reset() / step(action)
    → ElegantRL Agents
```

## 重要限制

- `btplot` / `signal_backtest` 的 Cython 引擎只适合**信号型**逻辑；
  复杂 `buy/sell` 动态仓位请用 `Strategy.next()`。
- RL 训练时**不会调用 `next()`**；`next()` 只用于普通回测。
- 指标预热用 `min_start_length` 跳过；特征应做滚动归一化，避免未来数据。
- 参数优化、信号优化、RL 都必须做**样本外 / walk-forward** 验证。
- `03_rl_position.py` 只训练几十到几百步用于演示；真实研究需要更长训练、
  多随机种子、手续费 / 滑点 / 持仓限制。

## 相关文档

- [1.5 策略参数优化](../../minibt_docs/docs/minibt_basic/1.5minibt_strategy_param_optimization.md)
- [1.23 signal_backtest 参数优化](../../minibt_docs/docs/minibt_basic/1.23minibt_signal_backtest_optimize.md)
- [4.1 RL 使用指南](../../minibt_docs/docs/minibt_reinforcement_learning/4.1reinforcement_learning_for_quantitative_trading_with_minibt.md)
- [4.8 ElegantRL、参数优化与交易扩展](../../minibt_docs/docs/minibt_reinforcement_learning/4.8_elegantrl_parameter_optimization.md)

## 旧 `rl = True` 文件怎么对应

| 旧文件 | 新示例 | 说明 |
| --- | --- | --- |
| `77_3 / 77_5 / 77_7 / 77_8 / 77_9 / 77_10` | `05_rl_hold_days.py --agent d3qn` 等 | 离散动作：DQN / D3QN / EnsembleDQN / DiscretePPO |
| `77_4 / 77_6 / 77_11 / 77_12 / 77_13 / 700005` | `05_rl_hold_days.py --agent ppo` 等 | 连续动作：PPO / DDPG / TD3 / SAC / ModSAC |
| `77_31 / 78_1` | `06_rl_pair.py` | 配对价差：0=观望、1=多价差、2=空价差 |
| `77_1 / 700005` | `07_rl_load_actor.py` | 训练后加载 actor 推理 |
| `77_2` | 未照搬 | 早期自定义 Gym 环境实验；当前 `Strategy` 本身就是 RL 环境 |
| `77.py` | 未照搬 | 主要是被注释的非 RL 调试代码 |


## 样本外 / 多 seed 组合

```python
from minibt.elegantrl.train import (
    equity_metrics, run_walk_forward_ensemble, runs_to_frame,
    seed_list,
)

runs = list(run_walk_forward_ensemble(
    df,
    make_strategy,          # (train/val/test frame, seed) -> Strategy
    train_one,              # (train, val, test, seed) -> result
    seeds=seed_list(3),
    train_size=1200, val_size=300, test_size=300,
    step=300, purge=60,
    metrics_fn=lambda fold, seed, result, train, test: equity_metrics(
        result.profits),
))
print(runs_to_frame(runs).groupby('seed').mean(numeric_only=True))
```

`train_one` 里把 `train._rl_config.eval_env_class = val`，
并可用 `eval_score(env)` 按验证净 Sharpe / 回撤选模。


## 加载部署模型

```python
from minibt.elegantrl.train import load_best_actor

actor, config = load_best_actor('results/deploy', device='cpu')
# actor.eval()
print(config['seed'], config['metrics'])
```


## 成本化 reward 与完整状态

新增两个通用模块，03 / 05 / 06 已经接入：

```python
from minibt.elegantrl.train import (
    RewardConfig, RewardModel, PositionState, append_state_features,
)

reward_model = RewardModel(RewardConfig(
    commission_rate=0.0002,
    slippage_rate=0.0001,
    risk_penalty=0.05,
))
reward = reward_model.step(prev_pos, pos, next_return)

state = PositionState(
    position=pos,
    holding_days=hold,
    unrealized_pnl=unrealized,
    drawdown=reward_model.drawdown,
)
obs = append_state_features(indicator_window, state)
```

小样本默认参数：

```python
from minibt.elegantrl.train import small_model_kwargs

self.set_model_params(
    Agents.AgentDiscretePPO,
    **small_model_kwargs(
        if_discrete=True, action_dim=3,
        min_start_mode='random',
    ),
)
```

详细原理见 [`minibt/elegantrl/REFACTOR_DETAILS.md`](../../minibt/elegantrl/REFACTOR_DETAILS.md)。

## 高层实验入口：RlExperiment / Bt 门面

`RlExperiment` 把 walk-forward、多 seed、报告和部署串起来；单模型训练仍然由
`Strategy.set_model_params / train_agent / load_agent` 完成。

```python
from minibt.elegantrl.train import RlExperiment

exp = RlExperiment(
    df,
    make_strategy,      # (frame, seed, role) -> Strategy
    train_one,          # (train, val, test, seed) -> result
    seeds=(42, 43, 44),
    train_size=1200, val_size=300, test_size=300,
    step=300, purge=60,
)
runs = exp.walk_forward()
print(exp.summary())
print('best seed:', exp.best_seed())
exp.save_csv('results/wf.csv')
exp.save_report('results/wf.md')
exp.save_html('results/wf.html')
exp.deploy('results/deploy')
```

也可以从 `Bt` 入口创建：

```python
from minibt import Bt

exp = Bt(auto=False).rl_experiment(
    df, make_strategy, train_one,
    seeds=(42, 43), train_size=1200,
    val_size=300, test_size=300, purge=60,
)
runs = exp.walk_forward()
```

分工：

```text
Strategy        单模型：训练 / 推理 / continue_train
RlExperiment    walk-forward / 多 seed / 报告 / 部署
Bt.rl_experiment  统一入口的薄门面
```
