# tutorials/desk

minibt desk 教程配套示例。文档入口：

* [13.17 指标规则与“加到图表”](../../minibt_docs/docs/minibt_desk/manual/13.17_local_chart_add.md)
* [13.18 回放与本地模拟账户](../../minibt_docs/docs/minibt_desk/manual/13.18_local_chart_replay.md)
* [13.19 本地图表：策略回测](../../minibt_docs/docs/minibt_desk/manual/13.19_local_chart_backtest.md)
* [13.20 本地图表：参数优化](../../minibt_docs/docs/minibt_desk/manual/13.20_local_chart_optimize.md)
* [13.21 本地指标样式示例](../../minibt_docs/docs/minibt_desk/manual/13.21_local_chart_indicator_styles.md)

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
