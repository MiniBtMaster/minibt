# tutorials/desk

minibt desk 教程配套示例。文档入口：

* [13.17 指标规则与“加到图表”](../../minibt_docs/docs/minibt_desk/manual/13.17_local_chart_add.md)
* [13.18 回放与本地模拟账户](../../minibt_docs/docs/minibt_desk/manual/13.18_local_chart_replay.md)
* [13.19 本地图表：策略回测](../../minibt_docs/docs/minibt_desk/manual/13.19_local_chart_backtest.md)
* [13.20 本地图表：参数优化](../../minibt_docs/docs/minibt_desk/manual/13.20_local_chart_optimize.md)
* [13.21 本地指标样式示例](../../minibt_docs/docs/minibt_desk/manual/13.21_local_chart_indicator_styles.md)

**v1.3.6 建议先读**（账户 / 交易相关全在这里）：

* [13.10 交易账户面板](../../minibt_docs/docs/minibt_desk/manual/13.10_trading.md)
  —— 快期式四按钮、**全部限价（对手价）**、锁仓拆平今 / 平昨、修改当前委托单、
  实盘二次确认；三个统一账户（快期模拟 / 富途模拟 / TqAccount）与
  **账户按页面 / 按格独立**、登录信息持久化；
* [13.25 二级报价 / 买卖盘](../../minibt_docs/docs/minibt_desk/manual/13.25_watch_book_ticket.md)
  —— 每格一条买卖盘、工具栏单开关（**默认关闭**）、三条线（持仓线 / 挂单线 / 平仓线）；
* [13.4 首页](../../minibt_docs/docs/minibt_desk/manual/13.4_home.md)
  —— 首页账户概览的账户下拉与权益曲线（首页账户只影响首页）。

## 目录

| 目录 | 内容 |
| --- | --- |
| [`local_chart/`](local_chart/README.md) | 指标样式、单合约 / 配对策略、回测、参数优化 |
| [`gui/`](gui/README.md) | **`Gui.Desk` 入口**：btplot / BtIndicator / 策略 / 回测 / 优化 / 实时（单合约 / 配对 / 多策略） |
| [`indicators/style_zoo/`](indicators/style_zoo/README.md) | 8 个 Style Zoo 指标样式示例 |

想让 minibt 的 `run()` / `btplot()` 直接用 **desk 当界面**：
见 [`gui/README.md`](gui/README.md)（`gui=Gui.Desk`）。

> **Jupyter / Notebook**：`Gui.Desk` 在 notebook 里自动用浏览器壳 + iframe 内嵌
> （不阻塞 kernel ✓）。最小示例（`.py` + `.ipynb`）在
> [`../plots/`](../plots/README.md)：`12_desk_btplot` / `13_desk_backtest` /
> `14_desk_replay` / `15_desk_live`。

## 数据

示例使用 minibt 内置 `LocalDatas`：

* `l2609_60`（DCE.l2609）
* `pp2609_60`（DCE.pp2609）

在 desk 本地图表里可以直接选择这两个 CSV；在「加到图表」时，策略里的
`get_kline(LocalDatas.xxx)` 会自动加载它们。
