# elegantrl 样本外改造计划

> 结论：当前样本内强、样本外弱，优先怀疑**全样本特征处理**、
> **训练/验证同环境**、**无成本 reward**、**状态缺少仓位/风险**。
> 本文件是改造计划与验收清单；结论正文见
> `minibt_docs/docs/minibt_reinforcement_learning/4.8_elegantrl_parameter_optimization.md`。
>
> **详细代码原理与逐项目录见 [`REFACTOR_DETAILS.md`](REFACTOR_DETAILS.md)。**

## 0. 现状结论

| 问题 | 代码位置 | 影响 |
|---|---|---|
| RobustScaler / MinMaxScaler 全样本 fit | `minibt/strategy/base.py::_process_quant_features` | 测试集统计量泄漏到训练特征 |
| `handle_outliers='clip'` 全样本分位数 | 同上 | 同样泄漏 |
| PCA / target_returns 全样本 fit | 同上 | 特征选择 / 降维泄漏 |
| `eval_env_class` / `eval_env_args` 字段存在但未使用 | `minibt/elegantrl/train/run.py` | Evaluator 用训练集；最佳 checkpoint 在样本内选 |
| 旧示例 reward 常用未来价格差且手续费=0 | 旧 `77_*` / `tutorials/elegantrl/05` | 学会高频交易，样本外被成本击穿 |
| 状态只有指标窗口，没有仓位 / 持仓天数 / 浮盈 / 回撤 | 旧 `77_3` 等 | 不是完整 MDP，空仓/满仓同状态 |
| 训练 reset 固定 `min_start_length` | 旧 `77_*` | 只适配一个起始位置 |

## 1. 改造目标

1. 消除特征处理对验证/测试区间的泄漏。
2. Evaluator 默认使用独立验证环境；最佳模型按验证集选。
3. 提供时间序列切分 / walk-forward 工具，禁止随机切分。
4. reward 纳入手续费、滑点、换手与风险惩罚。
5. 状态加入仓位、持仓天数、浮盈、回撤。
6. 小样本优先离散动作 / 小网络 / 多随机种子 / 集成。

## 2. 分阶段实施

### P0-1：特征处理支持训练区间 fit

- 给 `set_process_quant_features()` 增加 `fit_range=(start, end)`。
- `_process_quant_features()`：
  - Standard/Robust/MinMax scaler 只在 `fit_range` 内 `fit`，再 transform 全量；
  - `handle_outliers` 的分位数只用 `fit_range`；
  - `target_returns` 相关性 / PCA 也只用 `fit_range`；
  - `fit_range=None` 保持现有行为，避免破坏旧代码。
- 示例：训练集 0..N，验证集 N+purge..，测试集 ...

### P0-2：独立验证环境

- 在 `minibt/elegantrl/train/config.py` 增加 `resolve_eval_env(args)`：
  - `args.eval_env_class` 为实例 → 直接使用；
  - 为类 → `build_env(...)`；
  - 未提供 → 回退 `args.env_class`（保持兼容）。
- `train_agent_single_process` 与 `EvaluatorProc.run` 使用该函数。
- `Strategy.set_model_params(eval_env_class=val_strategy)` 已经存在，补上真正生效。
- 验证环境必须是**不同 KLine/DataFrame**，且 `train=False` / 不参与训练。

### P0-3：时间切分 / walk-forward 工具

- 新增 `minibt/elegantrl/train/splits.py`：
  - `split_dataframe(df, train=0.6, val=0.2, purge=0)`；
  - `walk_forward_windows(n_samples, train_size, val_size, test_size, step, purge)`；
- 约束：`purge >= window_size + reward_horizon`。

### P0-4：reward 成本化

- 训练 reward 至少：
  ```text
  prev_pos * next_return
  - commission * turnover
  - slippage * turnover
  - risk_penalty(drawdown / volatility)
  ```
- `KLine.fixed_commission` 不能替代 reward 成本。

### P1-1：状态补全

- `_obs()` 追加：
  - 当前仓位 / 方向；
  - 持仓天数；
  - 浮盈 / 回撤；
  - 可选：账户杠杆 / 保证金占用。

### P1-2：小样本训练策略

- 网络 `(32,32)` / `(64,32)`，`dropout_rate=0.1`；
- 优先 `AgentDiscretePPO` / `AgentD3QN` / `AgentDoubleDQN` /
  `AgentEnsembleDQN`；
- 连续动作只在数据量足够时用 PPO/SAC/DDPG/TD3；
- 多随机种子 + 验证集选模；
- 训练 reset 支持 `min_start_mode='random'/'incremental'`。

### P2：评估与诊断

- 验证 / 测试只看净收益、Sharpe、Sortino、最大回撤、换手率；
- 与买入持有、随机策略、静态参数策略对比；
- 做泄漏检查：打乱测试集、去掉未来特征、检查特征 IC；
- 分品种 / 分波动 regime 做压力测试。

## 3. 验收清单

- [x] `fit_range` 生效，且不影响 `fit_range=None` 旧行为
- [x] `eval_env_class` 真正被 `Evaluator` 使用
- [x] 单进程训练可用独立验证集
- [x] 新增 split / walk-forward 工具与测试
- [x] 示例 `03/05/06` 的 reward 扣成本
- [x] 示例 `03/05/06` 的 state 加入仓位/持仓/风险
- [x] `pytest` 相关测试通过
- [x] `mkdocs build -f minibt_docs/mkdocs.yml --strict` 通过

## 4. 暂不做

- 不重写 ElegantRL 算法；
- 不改旧 `77_*` 原始文件（保留参照）；
- 不强制所有示例用 walk-forward（先提供工具与推荐路径）。

## 5. 实施状态（2026-10-28）

| 项 | 状态 | 落地位置 |
|---|---|---|
| P0-1 特征训练区间 fit | ✅ | `Strategy.set_process_quant_features(fit_range=...)` / `_process_quant_features` |
| P0-2 独立验证环境 | ✅ | `train/config.py::resolve_eval_env` + `train/run.py` 两处 |
| P0-3 时间切分 / walk-forward | ✅ | `train/splits.py` + `train/walk_forward.py`（`make_folds` / `run_walk_forward`） |
| P0-4 成本化 reward | ✅ 核心 + 示例 | `train/reward.py`；03/05/06 接入手续费 / 滑点 / 回撤惩罚 |
| P1-1 状态补全 | ✅ 核心 + 示例 | `train/state.py`；03/05/06 接入仓位 / 持仓天数 / 浮盈 / 回撤 |
| P1-2 小样本训练策略 | ✅ 核心 + 示例 | `train/small.py`；03/05/06 小网络 / 离散动作 / 随机起点；`train/ensemble.py` 多 seed 编排 + 动作聚合 |
| P2 walk-forward 执行器 | ✅ | `train/walk_forward.py`（回调式训练 + 测试 fold；`run_walk_forward_ensemble` 组合多 seed；`summarize_runs` / `best_seed` / `save_runs_csv` / `save_walk_forward_report` / `save_walk_forward_html` 汇总导出） |
| P2 评估诊断 | ✅ 基础工具 | `train/metrics.py`：净收益 / Sharpe / Sortino / 回撤 / Calmar；`eval_score(env)` 支持按验证净指标选 checkpoint |
| P2 最优模型恢复 | ✅ | `Evaluator.best_actor_path` + `restore_best_actor()`；训练结束把验证最优 actor 覆盖为 `act.pth` |

### 新增测试

```text
tests/test_minibt_elegantrl_refactor.py   # split / reward / state / resolve_eval_env
tests/test_minibt_elegantrl_examples.py   # 01–11 --check
```
