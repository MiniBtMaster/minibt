# plots —— 图表模式示例

MiniBT 的三个图表引擎 **Bokeh / 纯 pylightcharts / pylightcharts_web** 都支持
**回测 / 回放 / 实时**三种场景，共 **九种模式**。本目录每个模式一个可直接运行的
示例（见 [1.29 图表引擎与九种运行模式](../../minibt_docs/docs/minibt_basic/1.29minibt_chart_modes.md)），
另附一个**无需天勤账号**的本地 mock 实时演示。

## 示例一览

| # | 文件 | 引擎 | 场景 | 策略（各不相同） | 重点演示的新功能 |
| --- | --- | --- | --- | --- | --- |
| 01 | `01_backtest_bokeh.py` | Bokeh | 回测 | EMA 通道突破 | `BandStyle` 色带、`SpanStyle`、`signalstyle`+`set_label`、`color_by`、`Config(grid/toolbox/volume_mode/bokeh_fullscreen)` |
| 02 | `02_replay_bokeh.py` | Bokeh | 回放 | RSI 均值回归 | bokeh 回放控件、`volume_mode='sub'`（半高成交量副图）、`theme='light'`、`plot_width` |
| 03 | `03_live_bokeh.py` | Bokeh | 实时 | 唐奇安突破 + `ThreeCommasStop` | 实时图、`history_length` 无限历史、`in_cooldown` 冷却、账户信息 |
| 04 | `04_backtest_pylightcharts.py` | 原生 | 回测 | 内置 `SingleEMACross` | `IndFrame.backtest()` 一行回测（1.2.8）、`reverse=True` 反手 |
| 05 | `05_replay_pylightcharts.py` | 原生 | 回放 | MACD 柱状 | `LineDash.vbar` + `LineStyle.vbar_base`（围绕中轴的柱）、`BandStyle` |
| 06 | `06_live_pylightcharts.py` | 原生 | 实时 | Pine `ta.*` 双均线 + ATR | `pine` 57 个函数、`history_length`、断开/重连、`color_by` |
| 07 | `07_backtest_pylightcharts_web.py` | 网页 | 回测 | 布林带信号 | `signal_text()` 钩子 + `SignalText` 多行文本（1.2.8）、`candlestyle`、`watermark` |
| 08 | `08_replay_pylightcharts_web.py` | 网页 | 回放 | SuperTrend + 双蜡烛叠加 | `overlap=True` 蜡烛型指标叠加主图（1.2.8）、`volume_mode='both'`、`set_stop_lines_style` |
| 09 | `09_live_pylightcharts_web.py` | 网页 | 实时 | 突破回踩 + 挂单 | `insert_order`（1.2.7）、`in_cooldown`（1.2.7）、`reverse=True`、`Strategy.copy()` 深合并 |
| 10 | `10_live_bokeh_mock.py` | Bokeh | 实时（**本地 mock**） | 唐奇安突破 | `MockLiveFeed` 本地逐根揭开、`feed_factory` 接口——**无需天勤账号**即可看实时图效果 |
| 11 | `11_all_nine_modes_cci.py` | **三个引擎** | **全部三种** | CCI 均值回归（天勤示例策略） | **九合一**：一个文件把 9 行入口按引擎分 3 组列出来，只留一行 python 回放；策略里顺带演示 `Config.watermark`、`LineStyle.vbar_*` 柱体配色、`run(y_margin=...)`、`data_length`+`history_length` 无限历史。只提供 `.py`（注释为主，不配 notebook） |

> `10` 不是「九种模式」之一，而是 bokeh 实时在**没有天勤账号**时的演示 / 自测方式：
> 策略先用全量本地数据把指标 / 交易 / 权益算好，`MockLiveFeed` 再每隔 `period_ms`
> 逐根「揭开」一根（`bokeh_plot.reveal_sources`）并把视口右移，顶部的「账户信息」
> 按当前 bar 的盈亏更新 —— 看上去就和真实盘一样一根一根往右长。

## 运行

每个模式都提供 **`.py` 脚本** 与 **`.ipynb` 笔记本** 两份（内容一致）；
`11_all_nine_modes_cci.py` 是例外 —— 它是**九合一**的说明性示例（注释为主），
只有 `.py`，默认跑「纯 pylightcharts + 回放」，其它 8 行注释着供你切换：

```bash
# 仓库根目录 —— 脚本
python tutorials/plots/01_backtest_bokeh.py
python tutorials/plots/04_backtest_pylightcharts.py
...
```

```text
# 笔记本：仓库根目录打开 Jupyter，逐格运行
jupyter lab tutorials/plots/01_backtest_bokeh.ipynb
```

笔记本已按「说明(Markdown) → 准备 → 指标 → 策略 → 运行」分好单元格；
其 `sys.path` 引导用 `os.getcwd()`（脚本里用 `__file__`），所以两种形式都可用。

* **回测 / 回放**用本地数据（`LocalDatas.test` / `LocalDatas.test`），无需联网；
* **实时**示例：`03` / `06` / `09` 需要天勤（`tqsdk`）账号（把文件里的
  `TqAuth("用户名", "密码")` 换成自己的再取消注释），`10` 是**本地 mock**、无需账号；
* 每个文件顶部都有一段 `切换提示`，说明同一策略怎样换引擎 / 换场景。
