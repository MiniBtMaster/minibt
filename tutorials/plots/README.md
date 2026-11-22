# plots —— 图表模式示例

MiniBT 的三个图表引擎 **Bokeh / 纯 pylightcharts / pylightcharts_web** 都支持
**回测 / 回放 / 实时**三种场景，共 **九种模式**。本目录每个模式一个可直接运行的
示例（见 [1.29 图表引擎与九种运行模式](../../minibt_docs/docs/minibt_basic/1.29minibt_chart_modes.md)），
另附一个**无需天勤账号**的本地 mock 实时演示。

从 **v1.3.4** 起多了一个**界面模式**：`gui=Gui.Desk`（miniqt desk 行情终端），
覆盖 **btplot / 回测 / 回放 / 实时** 四个入口，见下面的 `12` ~ `15`
（说明文档：[1.33 Gui.Desk](../../minibt_docs/docs/minibt_basic/1.33minibt_desk_gui.md)，
完整示例：[tutorials/desk/gui](../desk/gui/README.md)）。
`Gui.Desk` 在 **Jupyter 里会自动用浏览器壳 + iframe 内嵌**（不阻塞 kernel ✓）。

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

## 12~15：`Gui.Desk`（第四种界面）

`Gui.Desk` 不是图表引擎，而是把结果交给 **minibt desk 界面**（本地图表 /
策略回测页 / 实时图表）。四个入口各一个最小例子，**每个都有 `.py` + `.ipynb`**：

| # | 文件 | 入口 | 在 desk 里看到 | Jupyter |
| --- | --- | --- | --- | --- |
| 12 | `12_desk_btplot.py` | `ind.btplot(gui=Gui.Desk)` | 本地图表 + 指标（样式 / 主副图照旧） | ✅ iframe |
| 13 | `13_desk_backtest.py` | `bt.run(gui=Gui.Desk, desk_mode='backtest')` | 本地图表 +「策略回测」页（权益 / 回撤 / 交易记录） | ✅ iframe |
| 14 | `14_desk_replay.py` | `Bt(replay=True).run(gui=Gui.Desk, desk_mode='replay')` | 本地图表 + 策略；**在 desk 里点 ▶ 回放** | ✅ iframe |
| 15 | `15_desk_live.py` | `Bt(live=True).run(gui=Gui.Desk)` | 实时图表「加到图表」= 真下单（快期模拟） | ✅ iframe（需账号） |

> 需要完整特性（多布局 / 参数优化 / 配对交易 / 多策略实时）请看
> [`tutorials/desk/gui/`](../desk/gui/README.md)（8 个脚本示例）。
>
> **回放**：desk 的回放是**界面里**的 ▶ / ▶▶（默认截取末尾 30%），
> 不是独立回放窗口；Python 只负责把策略挂到图上。

## 运行

每个模式都提供 **`.py` 脚本** 与 **`.ipynb` 笔记本** 两份（内容一致）；
`11_all_nine_modes_cci.py` 是例外 —— 它是**九合一**的说明性示例（注释为主），
只有 `.py`，默认跑「纯 pylightcharts + 回放」，其它 8 行注释着供你切换：

```bash
# 仓库根目录 —— 脚本
python tutorials/plots/01_backtest_bokeh.py
python tutorials/plots/04_backtest_pylightcharts.py
...

# Gui.Desk（会弹 desk 窗口；实时需 --user / --password）
python tutorials/plots/12_desk_btplot.py
python tutorials/plots/13_desk_backtest.py
python tutorials/plots/14_desk_replay.py
python tutorials/plots/15_desk_live.py --user 账号 --password 密码
```

```text
# 笔记本：仓库根目录打开 Jupyter，逐格运行
jupyter lab tutorials/plots/01_backtest_bokeh.ipynb
jupyter lab tutorials/plots/12_desk_btplot.ipynb
```

笔记本已按「说明(Markdown) → 准备 → 指标 → 策略 → 运行」分好单元格；
其 `sys.path` 引导用 `os.getcwd()`（脚本里用 `__file__`），所以两种形式都可用。

### `Gui.Desk` 在 Jupyter 里怎么显示

* notebook 里 **不会**弹 Qt 窗口：desk 走**浏览器壳**（`127.0.0.1` 随机端口）
  + `display(IFrame)` 内嵌，单元格**立即返回**、不阻塞 kernel ✓；
* 一个格子里开一个 desk 实例；想多看几个就多跑几个格子（各自独立 iframe）；
  kernel 退出时自动关闭 desk / 天勤连接；
* desk 的日志只进它自己的「运行日志」页（不刷单元格）✓；
* 如果 iframe 空白：Jupyter 若是 **https**，浏览器会拦掉 `http://127.0.0.1`
  （mixed content）—— 把单元格里打印的地址贴到新浏览器标签即可；
* 笔记本里的策略类会被拷到 `~/.minibt/desk/generated/`（desk 只能按 `.py`
  路径导入），拷的是**整个单元格**，所以指标类和策略写在同一格就行 ✓。

* **回测 / 回放**用本地数据（`LocalDatas.test` / `LocalDatas.l2609_60`），无需联网；
* **实时**示例：`03` / `06` / `09` / `15` 需要天勤（`tqsdk`）账号（把文件里的
  `TqAuth("用户名", "密码")` 换成自己的再取消注释），`10` 是**本地 mock**、无需账号；
* 每个文件顶部都有一段 `切换提示`，说明同一策略怎样换引擎 / 换场景。
