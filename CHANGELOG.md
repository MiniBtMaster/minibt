# minibt 更新日志

本文件记录 **minibt Python 包** 的发布信息；完整的产品更新（含 desk / miniqt /
VS Code 扩展）请同时参考：

- 官网更新日志：<https://www.minibt.cn/changelog/>
- 仓库完整记录：`minibt_docs/docs/changelog.md`

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
