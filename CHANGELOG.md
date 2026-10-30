# minibt 更新日志

本文件记录 **minibt Python 包** 的发布信息；完整的产品更新（含 desk / miniqt /
VS Code 扩展）请同时参考：

- 官网更新日志：<https://www.minibt.cn/changelog/>
- 仓库完整记录：`minibt_docs/docs/changelog.md`

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.3.4] - 2026-10-30

### 亮点

- **`Gui.Desk` 进 Jupyter / Notebook**：notebook 里不再弹 Qt（那会卡死 kernel），
  自动改成**浏览器壳 + iframe** 内嵌；`tutorials/plots/12~15` 四个最小示例
  （btplot / 回测 / 回放 / 实时）随包提供；
- **本地图表多开 + 副本独立**：顶栏「＋ → 本地图表」/ 首页-图表工作台
  「新建本地图表」/ 命令面板都能新建副本（本地图表1 / 2 / 3…），
  指标 / 策略按**页面**存，同一份 CSV 开两页也互不影响；
- **一个页面只放一个策略**（换策略 = 先清上一个，布局 / 指标保留）；
  需要多策略时用**多开页面**、「策略实盘」（可同时多个子进程）或
  **只读叠加**（只画线、不交易）；
- **多布局真正可用**：格 2..N 的 K 线 / 指标增量更新、持仓线 / 挂单线按格
  路由、换合约只换鼠标最后点击的那一格；加载策略时「合约数 ≤ 现有格数」
  就**保持当前布局**（多余格不关），格数不足才自动加格；
- **计算搬到后台线程**：重策略（如 `KalmanFilterStrategy` 的 Python 循环）
  不再卡界面 —— 先推 K 线、后台算线、算完自动上图；收盘后自动挂起；
- **图表右键增强**：新「我的模板 ▸ / 保存当前指标模板」；画线共用左侧
  竖排导航条，按「合约|周期」本地持久化。

### 新增

- `Desk._strategy_lives`：**策略实盘支持多策略**（一个文件一个子进程），
  重复启动同一文件被拒；按钮显示 `运行中 ×N`，`停止实盘` = 停止并删除全部；
  「策略管理」里每行可改两个开关（新 K 线 next / 运行 next）/ 看 PID / 删除；
- **只读叠加（display-only strategy）**：`run_overlay(replay=False)` 只跑
  `__init__` 画线，**不跑 next、不碰账户**，同一页可叠多个；
  身份 =（文件绝对路径, 类名），同一个再点 = 重新加载；
  「🗑」菜单与「策略管理」里可单条删除，两个运行开关置灰；
- **本地图表多开**：独立页签 `local:1/2/3…`、页面级指标与策略、
  「复制当前页面」、页签显示当前策略名（`本地图表1 · test`）；
- **多布局画线**：左侧竖排导航条（46px，带 `趋势线 · TrendLine（Alt+T）`
  tooltip），存 `~/.minibt/desk/drawings.json`，键 = `合约|周期`；
- **图表右键「我的模板 / 保存当前指标模板」**（本地图表 + 实时图表，
  作用在鼠标最后点击的那一格）；
- **指标 / 策略后台计算**：`_strategy_results` 队列 + `_heavy_jobs` 门控
  （后台任务期间主线程不碰 tqsdk）、格 2..N 的完整库指标延后补推；
- 编辑器工具栏「策略管理」按钮（紧跟「加到图表」）、图表工作台两栏
  （左列本地图表 / 右列新建）、回放实验室「弹菜单选本地图表页」；
- `pylightcharts>=0.1.7`（desk 前端资源重建，见 pylightcharts CHANGELOG）。

### 变更

- **加载数据只加载 K 线**（本地图表）：重新打开本地数据不再带出上次的指标，
  指标请重新「加到图表」或用指标模板；
- **布局规则（加载策略后）**：格数 < 策略合约数的布局**禁用**；相等可切
  （合约按格对上）；更大可切（多出来的格子没有策略线、保留原样）；
- 命令面板快捷键 `Ctrl/⌘+K` → **`Ctrl/⌘+P`**（`Ctrl+K` 让给编辑器的注释）；
- 本地 / 实时布局按 `scope` 分开保存；保存同名布局需「确认替换」；
- 指标增量更新与 K 线一致（同根 1 点 / 新 K 线至少 2 点 / 断线按时间补缺口）；
- 编辑器「帮助」页补充：一个页面只支持一个策略、重载会先清理、
  指标失败不加载、`next()` 运行时出错不影响图表。

### 修复

- **指标缺口被连成直线**（`Chandelier_Exit` / `SuperTrend_STRATEGY` 等一半
  `up` 一半 `dn` 的指标）：首尾空点裁掉、中间缺口补透明点，效果与
  TradingView `plot.style_linebr` 一致；
- **`ADX_and_DI` 每次计算都刷 `RuntimeWarning`**（`invalid value in
  less_equal` / `divide`）：numpy 的 errstate 是**线程局部**的，desk 后台线程
  拿不到主线程的 `np.seterr` → 改为 `astype('float64') + fillna` 比较、
  除法包 `np.errstate`；
- **多布局**：第 2..N 格没有持仓线、切合约整页跳走、工具栏切布局后端不知道、
  指标总加到格 1、右键关闭格 2 关成格 1、切换主题其余格仍是深色；
- **策略线串格 / 策略管理删不掉**：`_local_indicator_payload()` 末尾又
  `strategy['items'] + items` 把全部线加一遍 → 只用本格那一组；
  策略管理按行 `key`（页签 id / 绝对路径|类名）删除，关页清理幽灵记录；
- **策略 `next()` 运行时报错不再影响图表**：首次弹窗、之后只写日志，
  图表 / 指标不动；指标算不出来时回滚 + 弹窗（不加载上图表）；
- **本地图表「初始加载」策略线串格**：后端推的布局不再用前端过期的每格
  合约回写；格 3 加第一个指标不显示（占位 K 线）→ 数据到了自动补推；
- **收盘后还在空转**：行情指纹没变直接 return，末根超过
  `max(10 分钟, 5 个周期)` 判定已收盘并挂起，日志只记一次；
- 首页下方预览图严格按「K线」开关显示（空数据自动重试，不再永远迷你折线）；
- `AdaptiveTrendTrail` 预热期 `RuntimeWarning`、`Twin_Range_Filter` 短数据
  越界、富途/天勤行情与订阅、主题与主副图分隔线等零星问题。

### 测试

- 新增 / 扩充 desk 回归：`test_minibt_desk_async.py`、
  `test_minibt_desk_cell_indicators.py`、`test_minibt_desk_local_pages.py`、
  `test_minibt_desk_layout_strategy.py`、`test_minibt_desk_overlay_page.py`、
  `test_minibt_desk_one_strategy.py`、`test_minibt_desk_runtime_errors.py`、
  `test_minibt_desk_cell_switch.py`、`test_minibt_desk_drawings.py`、
  `test_minibt_desk_context_templates.py`、`test_minibt_desk_home_preview_kline.py`
  等（本机 `pytest -k desk` 1120+ 项通过）；
- 前端 `jslib` 侧 `vitest` 102 项通过，`tsc --noEmit` 干净。

### 依赖

- `pylightcharts>=0.1.7`（0.1.6 → 0.1.7：desk 前端资源重建，
  多布局增量指标 / 右键指标模板 / 画线持久化 / 首页预览 K 线开关等）。

> 1.3.4 的逐项记录（含每个 P 编号修复）见
> `minibt_docs/docs/changelog.md` 的 `[v1.3.4]` 一节。

## [1.3.3] - 2026-10-27

### 亮点

- **纯指标策略不再多出「回测结果 / 指标记录」两页**：没有 `next()`、
  不产生交易的指标策略（例如 `vp.py` 的 `RollingVolumeProfile` 系列）
  只画指标，不会因为“权益是一条恒定平线”被误判成有回测数据。
- **本地图表 / 实时图表策略链路**：本地 CSV 策略、配对策略、实时多合约策略
  的指标、信号、持仓线、停止线、回测结果和参数优化入口统一。
- **图表与指标样式**：`PlotInfo` 的线型、线宽、图例、`bandstyle`、
  `signalstyle`、`tablestyle`、水印、逐点信号文字等能力在 desk 中落地。
- **行情与账户**：期货 / 股票数据源分流、天勤与富途账户切换、模拟账户、
  持仓线、预警线、二级报价和多布局状态同步继续完善。
- **文档**：VS Code 扩展更新到 **minibt-charts 0.3.11**：新增 desk 终端入口、
  天勤密码加密存储、连接体检与离线演示；安装命令和解释器自动探测保持可用。

### Changed

- `pylightcharts` 继续作为图表渲染依赖，最低要求保持 `>=0.1.5`
  （推荐安装最新 0.1.6，包含 panels / desk 资源更新）。
- 纯指标策略的输出按“是否真正发生交易”判断，不再按权益曲线是否水平判断。

### Fixed

- 修复本地图表 / 实时图表切换合约后旧指标、旧策略线、旧预警线残留。
- 修复本地策略回放时停止线越界、持仓线与成交次数统计不一致。
- 修复部分策略回测结果页 / 交易记录页为空但仍生成页签的问题。
- 修复富途股票行情订阅、账户切换与下单数量单位相关问题。
- 修复图表主题、副图分隔线、图例齿轮、指标 NaN 断点等显示问题。
- 修复 RL 特征预处理对 pandas 只读数组赋值失败（`assignment destination is read-only`）。
- 修复 RL 推理回测中收益曲线与时间索引长度不一致（`Length mismatch`）。
- 新增 RL 样本外改造基础设施：`fit_range` 训练区间归一化、独立 `eval_env`、
  `train/splits.py` 时间切分 / walk-forward。
- 新增 `train/metrics.py`：从权益曲线 / 收益率计算净收益、Sharpe、Sortino、
  最大回撤、Calmar 等验证指标。
- 新增验证集评分回调 `eval_score(env)`：可按净 Sharpe / 回撤选择最佳 checkpoint，
  默认仍使用累计 reward。
- 新增 `train/walk_forward.py`：`make_folds` / `run_walk_forward` 回调式 walk-forward 执行器。
- 新增 `train/ensemble.py`（多 seed 编排 / 动作聚合）与 `Strategy.rl_reset_index()`
  （fixed / random / incremental 起点）。
- 新增 `run_walk_forward_ensemble` / `runs_to_frame`：walk-forward × 多 seed 高层编排
  与结果表。
- 新增 `summarize_runs` / `save_runs_csv`：按 seed 汇总 walk-forward 指标并导出 CSV。
- 新增 `tutorials/elegantrl/08_walk_forward.py`：train / val / test 独立环境的一折示例；
  支持 `--all-folds` + `--seeds` + CSV 汇总。
- 新增 `tutorials/elegantrl/09_rl_ensemble.py`：多 seed actor 集成推理，
  同时评估单 actor / ensemble / 最佳 seed。
- 09 支持 `--csv` / `--report` / `--html`，导出单 actor 评估结果。
- 新增 `train/report.py`：Markdown walk-forward 报告；08 支持 `--report`。
- 报告新增 `best_seed` / `save_walk_forward_html`；08 支持 `--html`。
- `08_walk_forward.py` 支持全 fold / 多 seed / CSV / Markdown 报告。
- 08 会按 `--metric` 自动输出最佳 run / 最佳模型目录。
- 新增 `best_model_config` / `save_best_model`；08 支持 `--deploy` 复制最佳 actor。
- 新增 `load_best_actor`：从 `config.json` 恢复 actor / 架构并 eval。
- 新增 `tutorials/elegantrl/10_deploy_inference.py`：从部署目录复现 test 推理。
- 新增 `tutorials/elegantrl/11_rl_experiment.py`：RlExperiment / Bt 门面示例。
- 新增 `train/reward.py`：手续费 / 滑点 / 换手 / 回撤惩罚，03/05/06 已接入。
- 新增 `train/state.py`：仓位 / 持仓天数 / 浮盈 / 回撤 4 维状态，03/05/06 已接入。
- 新增 `train/small.py`：小样本小网络 / 离散动作 / 随机起点默认参数。
- 指标绘图设置审计：修正 `overlay` 拼写、TuLip/FinTa/TqTa/TA-Lib/BtInd
  等主图指标的 `overlap`，并隐藏 `thermo_long/short`、`signals` 等交易信号线。
- 修复 desk 布局管理：本地 / 实时布局按 `scope` 分开，布局行只显示布局 /
  合约 / 周期；应用多格布局时显式带上 `count`，避免只恢复成单图。
- 保存布局增加同名确认：同名布局需再次点击「确认替换」才覆盖，
  同一作用域内布局名称保持唯一。
- 修复本地布局恢复指标：布局里保存的 `pta_sma:sma` / `tv:X:trend`
  线条 key 先还原成目录基础 key 再计算，指标不再闪一下被清空。
- 修复实时图表多布局指标总加到格 1：工具栏 / 收藏 / 右键 / 键盘精灵
  统一按 `activeCell` 发送 `cell`，右键也先激活鼠标所在格。
- 修复 `AdaptiveTrendTrail` 等 TradingView 指标在 NaN 预热期的
  `RuntimeWarning`，并检查其它指标无同类警告；`Twin_Range_Filter`
  短数据不再越界。
- 指标全量推送只在历史未变时 `update(last)`，避免实时色带整段重绘闪烁。
- 指标增量更新与 K 线一致：同根只推 1 点；新 K 线至少推最后 2 点；
  断线重连按周期 / 时间差补缺口，缺口过大再全量重算。
- 新增 `minibt/elegantrl/REFACTOR_DETAILS.md`：样本外改造逐项原理与代码说明。
- 新增 `best_actor_path` / `restore_best_actor`：训练结束自动把验证最优 actor 覆盖为 `act.pth`。
- `Strategy._get_actor()` 优先加载 `act.pth`，避免 `find_pth_files()` 误选旧 checkpoint。
- 新增 `get_quant_feature_state` / `set_quant_feature_state`：08/09 的 val/test 复用 train 的 scaler / PCA / 异常值阈值 / 保留列。

### Packaging

- `pyproject.toml`、`minibt/__init__.py`、`README.md` 版本统一为 **1.3.3**。
- 新增包内发布资料：`CHANGELOG.md`、`RELEASE_NOTES.md`、`RELEASING.md`。
- `MANIFEST.in` 将上述资料纳入 sdist；wheel 仍只包含运行时包、数据与扩展模块。

> 1.3.3 的逐项修复（P44–P185、10-19 / 10-21 / 10-22 / 10-23 / 10-25 补充）
> 记录在 `minibt_docs/docs/changelog.md` 的 `[v1.3.3]` 一节。

## [1.3.2] - 2026-10-16

- `signal_backtest(gui=...)`、多策略权益 / 回撤对齐、`from_signals` 报表口径
  修复、`KLine.run` 的 `.ta` 竞态修复。

更早版本见 `minibt_docs/docs/changelog.md`。
