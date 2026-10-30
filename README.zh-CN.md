# pylightcharts

[![PyPI](https://img.shields.io/pypi/v/pylightcharts.svg)](https://pypi.org/project/pylightcharts/)
[![Python versions](https://img.shields.io/pypi/pyversions/pylightcharts.svg)](https://pypi.org/project/pylightcharts/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/MiniBtMaster/pylightcharts/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue.svg)](https://github.com/MiniBtMaster/pylightcharts/tree/main/docs)

[English](README.md) | **简体中文**

[TradingView Lightweight Charts™](https://github.com/tradingview/lightweight-charts)
的 Python 绑定，目标是**近乎完整的 API 覆盖**与 Pythonic 的调用体验。

> 状态：**Lightweight Charts v5.2.1 API 全覆盖（150/150 个接口方法）** ——
> 17 个指标、13 种画线、数值轴、格式化器、v5 插件、声明式 primitive、自定义序列、
> 自定义水平轴，CI 覆盖 JS + Python 测试与文档。
> 逐方法对照表：[`API_IMPLEMENTATION_REPORT.md`](https://github.com/MiniBtMaster/pylightcharts/blob/main/docs/advanced/api-implementation-report.md)。
>
> 另有一层 **金融插件（financial panels）** —— TradingView 风格的行情插件（行情表、
> 自选、筛选器、热力图、跑马灯、报价头、技术分析、季节性、新闻、日历、品种详情…），
> 渲染在同一个宿主页上、由 Python 驱动。见[金融插件](#金融插件tradingview-风格插件)。
>
> 更新日志：[`docs/changelog.md`](docs/changelog.md) —— 当前 **0.1.7**。

## 工作原理

这**不是**在 Python 里重新实现图表引擎，而是把官方、经过实战检验的 JavaScript
渲染器嵌进 WebView（pywebview / Qt WebEngine / wx / Jupyter / Streamlit），由 Python 驱动。

```
Python API  ──►  JSON / JS 桥  ──►  Lib.Handler (TypeScript)  ──►  Lightweight Charts v5
```

因为像素与交互都来自上游库，视觉保真度与性能与 JS 版一致。

## API 覆盖

pylightcharts 直接驱动上游引擎，因此 Lightweight Charts v5.2.1 的**每个公开方法**都能触达。
覆盖率由 `scripts/check_api_coverage.py`（解析上游 `typings.d.ts`）度量：

| 分组 | 覆盖率 |
|---|---|
| `IChartApi` / `ISeriesApi` / `ITimeScaleApi` / `IPriceScaleApi` / `IPaneApi` / `IPriceLine` | 100% |
| v5 插件（序列标记、涨跌标记、文字与图片水印） | 100% |
| `ISeriesPrimitive` / `IPanePrimitive`（Python 侧声明式） | 100% |
| `ICustomSeriesPaneView` / `ICustomSeriesPaneRenderer` | 100% |
| `IHorzScaleBehavior`（自定义水平轴） | 100% |
| 选项 / 类型别名（约 120 个） | 100% 透传 |
| 11 个枚举 + 全部顶层函数 | 已导出（`Lib.*` + `pylightcharts.constants`） |

```bash
python scripts/check_api_coverage.py          # 打印覆盖矩阵
python scripts/check_api_coverage.py --check  # 覆盖率回退时让 CI 失败
```

逐方法对照表与有意为之的差异清单：
[`API_IMPLEMENTATION_REPORT.md`](https://github.com/MiniBtMaster/pylightcharts/blob/main/docs/advanced/api-implementation-report.md)。

## 金融插件（TradingView 风格插件）

在图表引擎之上，pylightcharts 还带一层 **panels（插件）**（`pylightcharts.panels`），
把 TradingView 那一批 widget 用**同一个宿主页上的 DOM 组件**实现 —— 不额外起图表实例，
所以几百行表格、几百块热力瓦片都很便宜。插件建在 `Window` 上（图表的 `win`，或
无图表的 `QtPanel`），由 Python 驱动：

```python
from pylightcharts import QtPanel
from pylightcharts.panels import Column, DataGrid, Heatmap, MarketData, TickerTape

panel = QtPanel()
MarketData(panel.win, groups, columns=[Column('symbol', '代码'), ...])
Heatmap(panel.win, [{'symbol': '聚乙烯', 'value': 9, 'chg_pct': 1.2}, ...],
        color_scheme='cn')
TickerTape(panel.win, items, speed=70)
panel.get_webview().show()
```

| 插件 | 对应的 TradingView widget |
|---|---|
| `QuoteBoard` | 行情报价页：类型/交易所 chips + 报价表 + Ticker + 加载/空态 |
| `SymbolSearch` / `AlertDialog` | 商品搜索 / 预警对话框 |
| `IndicatorPicker` / `TemplatePicker` | 指标选择器（★ 收藏）/ 指标模板 |
| `DataGrid` / `Column` | 行情表基础原语 |
| `MarketData`、`Watchlist` | Market Data / Market Overview / Market Summary / Watchlist |
| `Screener` + `FilterBar` | Screener（条件、命名预设、JSON 持久化） |
| `Heatmap`（`StockHeatmap` / `CryptoHeatmap` / `EtfHeatmap` / `ForexHeatmap`） | Stock / Crypto / ETF / Forex Heatmap |
| `Ticker`（`TickerTape` / `TickerTag` / `SingleTicker` / `Tickers`） | Ticker Tape / Tag / Single Ticker / Tickers |
| `OrderTicket` | 买入 / 点差 / 卖出报价块（下单票据） |
| `QuoteHeader` / `SymbolInfo` / `SymbolOverview` / `MiniChart` | Symbol Info / Symbol Overview / Mini Chart |
| `TechnicalAnalysis`（+ `ta_summary`） | Technical Analysis（仪表盘 + 振荡器 / 均线表） |
| `SeasonalChart`（+ `seasonal_monthly`） | Seasonal Chart |
| `EconomicCalendar` / `FundamentalData` / `CompanyProfile` / `BrokerRating` / `BrokerReviews` | 品种详情壳 |
| `NewsFeed` / `TopStories` / `TextBlock` | Top Stories / 新闻 |

- **主题**：每个插件都跟随窗口主题 —— `chart.win.theme('light')`（或默认的 `'dark'`）；
  之后创建的插件会自动继承。深浅两套样式都完整。
- **数据**：库**不带行情数据** —— 由宿主喂 rows / items / quotes（minibt、tqapi、CSV…）。
  新闻 / 基本面 / 日历 / 券商这几个是 UI + 数据契约的**壳**。
- **示例**：`examples/13_panels/01_data_grid.py` … `15_alert_dialog.py`
  （0.1.6 新增 `12_quote_board` / `13_symbol_search` / `14_indicator_picker` /
  `15_alert_dialog`，均支持 `--check`，部分支持 `--snapshot`）。`10_gallery.py` 是全部插件的总览。
  指南：
  [`docs/guide/panels.md`](docs/guide/panels.md)。

## 致谢 / 许可

- Python 层、GUI 后端与画线插件派生自
  [lightweight-charts-python](https://github.com/louisnw01/lightweight-charts-python)（MIT）。
- 图表引擎是
  [TradingView Lightweight Charts™](https://github.com/tradingview/lightweight-charts)
  （Apache-2.0），见 `NOTICE`。

## 从 lightweight-charts-python 迁移

pylightcharts 保留了原包的每个类、方法与模块级名字（由 `tests/test_lwc_compat.py` 保证），
因此现有代码加一行 shim 即可运行：

```python
from pylightcharts.compat import install_alias
install_alias()                     # 必须在任何 `import lightweight_charts` 之前

import lightweight_charts            # -> pylightcharts
lightweight_charts.widgets.QWebEngineView = MyPyQt6WebEngineView   # 猴子补丁依然可用
```

或者直接改导入：

```diff
- from lightweight_charts.util import Events, JSEmitter
- from lightweight_charts.widgets import QtChart
+ from pylightcharts.util import Events, JSEmitter
+ from pylightcharts.widgets import QtChart
```

## Qt 集成

在桌面应用里，`QtChart` 把图表嵌入一个 `QWebEngineView`：

```python
from PyQt6.QtWidgets import QApplication
from pylightcharts.qt import prepare_qt

prepare_qt('PyQt6')          # 必须在 QApplication 之前选定绑定
app = QApplication([])

from pylightcharts.widgets import QtChart
chart = QtChart(toolbox=True)
chart.set(df)
chart.get_webview().show()
app.exec()
```

`QtWebEngineWidgets` 必须在 `QApplication` 存在**之前**导入，所以 `prepare_qt()` 要放最前；
也可以设 `$PYLIGHTCHARTS_QT` 来选绑定。完整细节 —— 多图 `sync()`、截图、Chromium 网络噪音 ——
见 `docs/guide/qt.md`。

## 示例

### 完整 API 巡览（`examples/11_api_tour/`）

可运行、可视化的脚本，逐一走遍**每个公开 API**。每个文件都暴露 `build(chart)`
（可在测试里用无头方式驱动）与打开窗口的 `main()`：

| 文件 | 覆盖内容 |
|---|---|
| `01_chart_and_data.py` | `set` / `update` / `update_from_tick` / `batch`、布局、网格、十字线、图例、水印、蜡烛与成交量样式、精度、选项 |
| `02_series_types.py` | Line/Area/Bar/Baseline/Histogram/Candlestick、价格线、标记、数据回读、坐标换算、排序、pane |
| `03_scales_and_queries.py` | 时间轴（滚动 / 范围 / 换算 / 格式化器）、价格轴、pane 查询、`chart_options`、`chart_element`、`version` |
| `04_events.py` | click / dblclick / crosshair / range / visible-time / size / data-changed / new-bar / search / 热键 |
| `05_drawings.py` | 全部 13 种画线 + `vertical_span`，以及 `update` / `delete` / `options` |
| `06_panes.py` | pane、stretch / height / preserve、pane primitive、pane 级序列 |
| `07_indicators.py` | 全部 17 个指标、`add_indicator`、`add_computed_series` |
| `08_custom_series.py` | 每种形状 + 预设 + 自定义 pane-view spec |
| `09_plugins.py` | 标记 / 涨跌标记 / 文字与图片水印的生命周期 |
| `10_primitives.py` | 声明式 series 与 pane primitive，全部扩展点 |
| `11_callbacks.py` | 格式化器、刻度、价格格式、autoscale、常量 |
| `12_numeric_and_scale.py` | YieldCurve / Options 图，自定义水平轴 |
| `13_workspace.py` | 表格、顶栏控件、工具箱、子图、sync、截图 |
| `14_multi_chart_layout.py` … `23_fill_between_gaps.py` | 页面顶栏、整站主题、tooltip、双品种、无限历史、指标副图、stem/scatter、多行文本、NaN 断线与色带断点 —— 见 `examples/11_api_tour/README.md` |
| `24_layouts_and_legend_settings.py` | 迁移期加的扩展：2D `arrange_tiles(dividers=True)` 布局、图例齿轮（`enable_legend_settings`）与常显图例行（`pin_legend_row`），以及指标线样式助手（`set_line_*` / `set_price_visible` / `is_visible`）+ `chart.remove()` |
| `25_live_value_table.py` … `27_volume_profile_live.py` | 十字光标驱动的指标数值表格 + 实时刷新（`25`），以及**成交量分布图（Volume Profile）**配方（`26` 静态 / `27` 实时）—— 跟随鼠标、贴在可视范围最右端的横向成交量分布 —— 见 `examples/11_api_tour/README.md` |

### 金融插件示例（`examples/13_panels/`）

十一个脚本覆盖插件层（模拟数据、支持 `--snapshot`、`PYLIGHTCHARTS_QT=` 切换绑定）：
`01_data_grid`、`02_sparkline`、`03_market_data`、`04_ticker_and_quote`、`05_heatmap`、
`06_seasonal`、`07_screener`、`08_details`、`09_technical`，以及 `10_gallery.py` ——
最后一个把所有插件铺成可滚动网格，一屏看全 —— 再加 `11_sim_account_shell.py`
（整页模拟账号壳：表格 + 下单窗口）。见
[`examples/13_panels/README.md`](examples/13_panels/README.md)。

### 早期十个专题示例

`examples/1_setting_data` … `examples/12_browser` 每个只讲一个主题、自带数据：
加载 OHLCV、实时 K 线、tick 更新、指标线、样式、回调、内置指标、无头 PNG 渲染、
浏览器标签页里的图表（`examples/12_browser/static.py` 与 `live.py`，都带主图 SMA 和副图 RSI）、
自定义序列与 PyQt6 窗口。从 `examples/1_setting_data/setting_data.py` 开始看。

## 开发

```bash
# 构建 JS 桥 + 把引擎 vendored 进 pylightcharts/js/
cd jslib && npm install && npm run build

# 可编辑模式安装 Python 包
cd .. && pip install -e .

# ...或用需求文件（pyproject.toml 始终是唯一的真源）
pip install -r requirements.txt        # 仅运行时
pip install -r requirements-dev.txt    # + 测试、e2e、文档、构建
```

### 测试

```bash
# 单元测试：断言 Python 桥生成的 JS（无需浏览器）
python -m pytest -m "not slow"

# e2e：在无头 Chromium 里跑构建产物并检查渲染像素
python tests/e2e/smoke.py

# 无头渲染测试（Playwright 或本地 Chrome/Edge）
python -m pytest tests/test_headless.py

# 全栈：真实 pywebview 窗口 + 真实图表引擎（需要桌面会话）
python tests/e2e/full_stack.py

# 性能：JSON 与大块二进制数据传输对比
python tests/e2e/benchmark.py 100000
```

CI（`.github/workflows/ci.yml`）会构建 bundle、校验提交的产物是否最新、在
Linux/Windows/macOS 上跑单元测试、在无头 Chromium 里渲染，并验证 wheel 里带了 JS 资源。

### 待办（刻意未做）

那些"能做但暂时不做"的功能 —— 布局分割条的触摸拖动、网格布局、销毁图表、
色带 primitive 的 `zOrder` 等 —— 都收集在
[`docs/advanced/deferred.md`](https://github.com/MiniBtMaster/pylightcharts/blob/main/docs/advanced/deferred.md)，
每条都写了所在文件与实现思路。以后发现类似情况往那里加，而不是在源码里留一个裸 `TODO`。

### 打包

```bash
cd jslib && npm run build      # 重新生成 pylightcharts/js/*
cd .. && python -m build       # sdist + wheel（JS 资源是 package-data）
twine upload dist/*
```

构建好的 `pylightcharts/js/` 文件是**故意提交**的，这样 `pip install` 无需 Node。
提交前务必先跑 `npm run build`。

### 桥的规则

- 即发即弃的调用走 `Window.invoke`（传输层会追加 `;undefined`，避免 pywebview
  序列化一个活的 chart 对象）。
- **返回对象**的方法必须用 `store_as=...`；只有基本类型才可以走 `invoke_get`。
  用 `invoke_get` 返回活对象会炸。
- 往返调用按请求 id 串行化并配对；JS 报错会抛 `pylightcharts.util.BridgeError`，而不是返回 `None`。
- Chart 与 series 有同名方法（`apply_options`）；它们被刻意区分（`series_options`、`data_points`）
  以避免 MRO 遮蔽。
- 升级 lightweight-charts：`npm pack lightweight-charts@X`，迁移破坏性变更，`npm run build`，
  再跑 e2e 套件。

### 通用桥

新功能不应需要改 TypeScript。任意活对象上的任意方法都能从 Python 调用：

```python
chart._invoke('addSeries', 'Area', 'my area', {'lineWidth': 2}, handle)
chart.win.invoke(f'{series.id}.series', 'applyOptions', {'lineWidth': 3})
```

handle 要么通过 `Lib.register(...)` 注册，要么是点号窗口路径（`window.abcdefgh.chart`）。
`{'$ref': handle}` 参数会被解析成活对象，所以接收对象的 API 也能用：

```python
series.attach_primitive('myPrimitive')   # -> attachPrimitive({"$ref": "myPrimitive"})
```

见 `jslib/src/general/rpc.ts`。

### 全量选项

`apply_options(**kwargs)` 接受底层 API 的任意选项，并自动把 `snake_case`
键转成 `camelCase`：

```python
chart.apply_options(auto_size=True, localization={'price_format': {'precision': 4}})
chart.time_scale_options(right_offset=5, bar_spacing=8)   # 时间轴
series.apply_options(line_width=3, crosshair_marker_visible=False)
get = chart.get_price_scale('left'); get.set_mode('logarithmic')
```

### 指标

纯 pandas 实现，无额外依赖。主图叠加型画在价格 pane，振荡型自动建自己的 pane：

```python
chart.add_sma('close', 20)
chart.add_ema('close', 50, color='#2196F3')
chart.add_bollinger('close', 20, 2)      # -> (upper, middle, lower)
chart.add_donchian(20)
chart.add_vwap()

chart.add_rsi(14)                        # 独立 pane + 70/30 参考线
chart.add_macd()                         # 独立 pane -> (macd, signal, histogram)
chart.add_stochastic()                   # 独立 pane -> (%K, %D)
chart.add_atr(14)
chart.add_adx(14)                        # 独立 pane -> (adx, +DI, -DI)
chart.add_obv()                          # 独立 pane（需要成交量）
chart.add_cci(20)
chart.add_williams_r(14)
chart.add_mfi(14)
chart.add_roc(12)
chart.add_keltner(20, 2.0)               # 叠加 -> (upper, middle, lower)
```

原始值：`from pylightcharts import indicators; indicators.rsi(close, 14)`。
RSI、OBV、CCI、%R、ROC、MFI 与 Bollinger 与 TA-Lib 达到浮点精度一致；ATR 与 ADX
分别在约 1e-4 与约 0.1 内一致（Wilder 累积的舍入）。

#### 指标跟随数据

每个指标都会自动重算：`chart.set()` 时全量重发，`chart.update(bar)` 时单点更新
（从预热窗口重算，使递归指标与全量运行的数值完全一致）。`add_computed_series(compute, name, ...)`
可以加你自己的指标。

#### 批量 tick

每次桥调用都是一次 webview 往返，所以把连续调用包进 `chart.batch()`：

```python
with chart.batch():
    for tick in ticks:
        chart.update(tick)      # 作为一个脚本一次性下发
```

#### 合并（超大数据）

合并（conflation）是普通序列选项，桥已经暴露：

```python
chart.apply_options(enable_conflation=True, precompute_conflation_on_init=True)
series.apply_options(enable_conflation=True)
```

### 自定义序列（声明式渲染）

自定义序列最难的是 `draw()` —— 每帧同步执行，Python 无法参与。所以协议把工作拆开：
**Python 每次数据更新算一次形状，一个通用 JS 渲染器每帧把它们画出来。**

```python
from pylightcharts import shapes

series = chart.add_custom_series('range bars', pane_index='new')
series.set(df, shapes=lambda row: shapes.range_bar(row['low'], row['high']))
```

形状构造器：`rect` `band` `line` `circle` `marker` `text` `polyline`，以及预设
`range_bar` `box_plot` `error_bar` `stem`。

`shapes.stem(price, baseline=0.0, style='dashed', cap=False)` 从 `baseline` 到 `price`
画一根竖棒 —— 用来展示逐笔盈亏、相对均值的偏离，或挂在公共轴上的量价分布很方便：

```python
series.set(df, shapes=lambda row: shapes.stem(row['pnl'], color=row['color'],
                                              cap=True))
```
竖向锚点是价格，水平偏移以 bar 为单位（`-0.4..0.4` 跨一根 bar）—— 除了
`shapes.marker`，它的 `offset`/`size` 是**像素**（缩放不变的图形；`marker=` 接受
minibt 的 `Markers` 名：`triangle` `inverted_triangle` `arrow_up` `arrow_down` `circle`
`circle_cross` `circle_dot` `circle_x` `circle_y` `square` `dot` `dash` `cross`
`asterisk` `triangle_dot`）。

```python
shapes.box_plot(low, q1, median, q3, high)
shapes.polyline([(0.0, 1.0), (0.4, 2.0)], fill_color='rgba(0,0,0,0.2)')
shapes.text(price, 'label\nsecond line',   # 多行文本（同 bokeh LabelSet）
            offset_x=6, font_weight='bold',              # 像素偏移 / 粗体
            background_color='#222', padding=4)         # 文本底色 + 内边距
```

每条数据项可以带 `value`、`low`、`high`（autoscale + 最后值）、`color` 与 `shapes`。

### v5 插件（标记 / 涨跌标记 / 水印）

v5 把标记与水印改成了 *primitive*；每个都有完整的 Python 封装：

```python
m = series.markers_plugin()          # SeriesMarkersPlugin (ISeriesMarkersPluginApi)
m.markers(); m.apply_options(z_index=1); m.detach(); m.get_series()

up = series.up_down_markers_plugin(positive_color='#26a69a')
up.set_data(df); up.update(point); up.markers(); up.set_markers([...])
up.clear_markers(); up.apply_options(negative_color='#ef5350'); up.detach()

text = chart.text_watermark_plugin('pylightcharts', 48, 'rgba(180,180,220,0.4)')
text.apply_options(horz_align='left'); text.get_pane(); text.detach()

img = chart.image_watermark_plugin('logo.png', max_width=120)
```

### 函数型选项（格式化器与 provider）

回调在渲染循环里同步执行，所以注册一小段 JS 函数体，注入到任意选项路径：

```python
chart.register_js_callback('vol', ['price'], "return (price/1e6).toFixed(1)+'M'")
chart.set_tick_mark_formatter('vol')            # timeScale.tickMarkFormatter

series.set_price_format_formatter('vol')        # 合并安全的 priceFormat.formatter
series.set_autoscale_info_provider('vol')       # series.autoscaleInfoProvider

chart.set_option_callback(f'{chart.id}.chart', 'applyOptions',
                          'localization.priceFormatter', 'vol')
chart.set_price_formatter_callback('vol'); chart.set_time_formatter_callback('vol')
```

### 声明式 primitive

```python
chart.register_js_callback(
    'draw', ['target', 'pc', 'view', 'prim'],
    "const y = prim.series.priceToCoordinate(100); /* 用 target.useBitmapCoordinateSpace 绘制 */")
prim = chart.create_series_primitive({
    'paneViews': [{'draw': 'draw', 'zOrder': 'top'}],
    'priceAxisViews': [{'coordinate': 'coord', 'text': 'label'}],
    'hitTest': 'hit', 'autoscaleInfo': 'scale',
})
prim.attach_to(series)

pane_prim = chart.create_pane_primitive({'paneViews': [{'draw': 'draw'}]})
pane_prim.attach_to(chart, 0)
```

### 自定义水平轴

```python
class MonthChart(Chart):
    _horz_scale_name = 'month'
    _horz_scale = {
        'formatTickmark': (['tickMark', 'loc'], "return 'M' + tickMark"),
        'formatHorzItem': (['item'], "return 'M' + item"),
    }
```

### 常量与仿真校验

```python
from pylightcharts.constants import LineStyle, PriceScaleMode, CrosshairMode, verify
chart.apply_options(crosshair={'mode': CrosshairMode.Magnet})
chart.price_scale(mode=PriceScaleMode.Logarithmic)
series.apply_options(line_style=LineStyle.Dashed)
verify(chart)          # [] 表示 Python 常量与内嵌引擎一致
```

### 价格线、数据读取、事件

```python
line = series.create_price_line(105.0, color='#00e676', title='entry')
line.apply_options(line_visible=False)
line.remove()

series.price_to_coordinate(105)        # <-> series.coordinate_to_price(y)
series.data_by_index(10)               # 单根 bar
series.data_points()                   # 图表持有的全部数据
series.pop(2); series.last_value_data(); series.bars_in_logical_range(0, 50)
series.series_type(); series.get_pane_index()
series.move_to_pane(2); series.series_order(); series.set_series_order(3)

chart.scroll_to_real_time(); chart.scroll_to_position(3, animated=False)
chart.reset_time_scale(); chart.set_visible_logical_range(0, 60)
chart.get_visible_range(); chart.get_visible_logical_range()
chart.time_to_coordinate(t); chart.coordinate_to_time(x)
chart.logical_to_coordinate(l); chart.coordinate_to_logical(x)
chart.pane_height(0); chart.set_pane_height(300, 0)
chart.pane_stretch_factor(0); chart.pane_size(); chart.pane_series_count(0)
chart.version(); chart.auto_size_active(); chart.remove()
chart.set_crosshair_position(100.0, some_time); chart.clear_crosshair_position()

chart.get_price_scale('right').get_visible_range()
chart.get_price_scale('right').set_auto_scale(False)
chart.pane_price_scale(0, 'left')

chart.events.crosshair_move += handler      # handler(chart, time, price)
chart.events.dblclick += handler
chart.events.click.unsubscribe()
```

### 多图同步

```python
price = Chart(); volume = Chart()
price.sync(volume)                       # volume 跟随 price 平移/缩放
price.sync(volume, crosshairs_only=True)
```

### 原生 pane（lightweight-charts v5）

```python
chart.add_pane()
chart.create_area(name='close', pane_index=1)
chart.add_series('Line', 'ma20', pane_index=1, color='#0ff')
chart.set_pane_stretch(1, 1.5)
chart.pane_count()
```

`pane_index='new'` 会新建一个 pane；传入超过当前 pane 数的索引会自动补齐中间的 pane。

### 画线工具

趋势线 / 水平线 / 垂直线 / 射线 / 箱体，以及：

```python
chart.fibonacci(t1, p1, t2, p2, levels=(0, 0.382, 0.5, 0.618, 1))
chart.measure(t1, p1, t2, p2)                       # 价格 %、bar 数
chart.parallel_channel(t1, p1, t2, p2, offset=5)    # 第二条线距 5 个价格单位
chart.position(t1, entry, t2, target, risk_ratio=1.5)   # 盈利 + 止损区间
chart.long_position(t1, entry, t2, target)          # 别名
chart.short_position(t1, entry, t2, target)

chart.andrews_pitchfork(t1, p1, t2, p2, t3, p3)     # 3 点
chart.triangle(t1, p1, t2, p2, t3, p3)              # 3 点
chart.fibonacci_extension(t1, p1, t2, p2, t3, p3)   # 脉冲 + 回撤
chart.gann_fan(t1, p1, t2, p2)                      # 1x1 加更陡/更缓的射线
```

开 `toolbox=True` 时这些也能交互式使用（Alt+F / M / C / P / A / G / X / N）。

### 数值轴与格式化器

```python
from pylightcharts import YieldCurveChart, OptionsChart

curve = YieldCurveChart()                 # x 轴 = 期限（月）
series = curve.add_series('Line', 'rate')
series.set(pd.DataFrame({'time': [1, 3, 12], 'rate': [4.2, 4.0, 3.6]}))

surface = OptionsChart()                  # x 轴 = 行权价

chart.set_price_formatter(decimals=2, thousands=True, prefix='$')
chart.set_time_formatter('YYYY-MM-DD HH:mm')
chart.register_js_formatter('eur', "value => '\u20ac' + value.toFixed(2)")
chart.set_price_formatter(name='eur')
```

### 大数据

2000 行以上的 DataFrame 会以 base64 的列主序 Float64 buffer 传输，并在浏览器里
重建（`Lib.decodeData`），而不是作为 JavaScript 源码下发。实测 10 万根 bar：
**1.56s -> 0.54s（约 3 倍）**；50 万根：**8.9s -> 3.2s**。用
`pylightcharts.util.BINARY_DATA_THRESHOLD` 调整阈值。

### 无头 / 服务端渲染

```python
from pylightcharts.headless import HeadlessChart

chart = HeadlessChart(width=1200, height=700)
chart.set(df)
chart.add_sma('close', 20)
chart.add_rsi(14)
chart.render('report.png')        # PNG 字节，无需窗口
chart.to_html()                   # 或拿到独立 HTML
```

装了 Playwright 就用它，否则用本地 Chrome/Edge 的无头模式
（`PYLIGHTCHARTS_CHROME` 可覆盖浏览器路径）。


## pylightcharts 扩展

这些是 pylightcharts 在上游 Lightweight Charts / lightweight-charts-python 之外**新增**的 API。
这里简单列出，详细文档在 `docs/` 下。

| API | 作用 |
|---|---|
| 每个序列工厂与指标上的 `legend_toggle=` / `legend=` | 是否画图例行、及其眼睛图标，或两者都不画 |
| `chart.horizontal_span(low, high, color=, opacity=, filled=, pane_index=)` | 价格色带（支撑/阻力）；`pane_index=` 可放到副图 |
| `chart.fill_between(upper, lower, color=, opacity=)` / `upper.fill_between(lower)` | 在两条线之间填色（通道带） |
| `horizontal_span` / `fill_between` / `vertical_span` 的 `opacity=` | 任意颜色格式的填充透明度，描边保持清晰 |
| `chart.pane_separator(color=, hover_color=, enable_resize=)` | 重新着色 / 隐藏 pane 之间 1px 的分隔条 |
| `chart.pane_height()` / `set_pane_height(px, i)`（封装 `IPaneApi`） | 读取 / 设置 pane 的绝对高度 |
| `chart.mark_swings(...)` + `indicators.swing_points` | `length` 根分形摆动高低点，并把价格作为标记文字（Lightweight Charts 本身只画标记） |
| `chart.add_zigzag(threshold=)` + `indicators.zigzag` | 波段线：最小回撤百分比之后的交替枢轴，画成折线并像指标一样保持同步（`include_unconfirmed` 显示未确认段；`inverted=` 用于价格倒挂） |
| `BrowserChart` + `to_html()` / `save_html()` / `open_in_browser()` | 一个自包含 HTML 页（引擎 + 桥 + 样式全内联）—— `BrowserChart(...).show()` 写出并打开：无服务器、无 Node、无额外依赖的浏览器视图 |
| `BrowserChart(live=True)` + `LiveServer` | 浏览器标签页里的实时图表：标准库 HTTP + SSE 流（长轮询兜底，可选 `token=` 供局域网/手机查看）把每次 `set`/`update`/`apply_options` 推到页面，widget 回调再回传给 Python —— 依旧零依赖、不落盘 |
| `color_by(...)` / `series.color_by(...)` / `chart.color_by(...)` | 逐点 / 条件着色：填充引擎的 `color` / `wickColor` / `borderColor` 键，适用于任意序列（含指标线）与主图蜡烛（`docs/guide/charts.md#conditional-colours`） |
| `Chart(..., keyboard=True, keyboard_step=0.1)` + 方向键 | 内置导航：方向键平移可见窗口 / 缩放（最新 bar 在屏上后再缩小时右边缘保持固定），`Shift` 大步、`Ctrl`+方向键与 `PageUp/Down` 整页、`Home`/`End`、`Ctrl+0` 适配；用户 `hotkey()` 优先，输入文本时忽略 |
| `chart.win.page_topbar()` | 横跨窗口、始终在每张图上方的顶栏（`chart.topbar` 在单张图内、会随图缩小） |
| `chart.win.layout`（`Layout`） | 用图表铺满窗口：`vertical()` / `horizontal()` / `arrange(kind, count)` / `single()`，默认相互独立（`sync=True` 联动平移/缩放/十字线，`sync='crosshair'` 只联动十字线），还有 `on_create=` 给新图喂数据；图之间有可拖的分隔条（`divider_size=` / `set_divider(...)`） |
| `Layout.arrange_tiles(tiles, dividers=True)` + `Lib.clearLayoutTiles` | **2D 瓦片布局**（TradingView 风格"上 1 下 2"）：`tiles` 是 `(宽, 高)` 分数的有序列表 —— `[(1.0, 0.5), (0.5, 0.5), (0.5, 0.5)]`。单行/单列与行流（2D）布局都带**可拖分隔条**（行间、行内列间）；切回浮动布局（`arrange()` / `single()`）会发 `clearLayoutTiles` 恢复正常浮动几何（`examples/11_api_tour/24_layouts_and_legend_settings.py`） |
| `series.enable_legend_settings(callback)` | 给序列图例行加一个**设置（齿轮）按钮**；点击回调 `callback(series, x, y)`（webview 内的点击位置，方便在齿轮旁弹出设置卡）。把"监听图例上每次鼠标移动"换成一次点击往返 |
| `series.pin_legend_row(True)` | 让某序列的图例行**始终显示**（默认只有十字线在该 bar 上时才出现），使指标名 + 眼睛 + 齿轮常驻屏幕 |
| `series.enable_legend_menu(config, callback)` | `enable_legend_settings` 的**无 Qt** 版本：齿轮按钮打开页面自带的 JS 菜单（`参数` / `线型` / `线宽` / `线颜色` / `其它设置`），每次改动回调 `callback(series, kind, payload)` —— minibt / btplot 这类没有 Qt 的宿主也能拿到同一套设置面板 |
| `series.remove_legend_row()` | 直接摘掉某序列的图例行（幂等）—— `legend=False` 内部就是调它（JS 侧现在**每条序列都会建行**，空名字不再能“跳过”） |
| `chart.enable_legend_collapse()` | TradingView 风格的指标行折叠按钮（`∧` / `∨ N`），没有指标行时自动隐藏；画在 JS 图例里，Qt / 浏览器宿主都生效 |
| `chart.horizontal_line(..., text=, label_visible=, label_background_color=, label_text_color=, label_font=)` | 把标签画在 **pane 内**（钉在可视范围左沿）；`axis_label_visible=False` 现在也真的不再让隐藏徽标撑宽价格轴 |
| `series.remove_markers(ids)` + `marker(..., size=)` | 一次性删除多个标记（只重绘一次），并把 v5 的 `size` 透传下去 |
| `series.skip_gap_segments()` / `prefer_single_gap()` / `repaint_gaps()` | 调 NaN 断点渲染：隐藏的 `fill_between` 承载体不再拆分、实时指标线固定走单序列透明缺口、改色后重发一次让逐点颜色跟上 |
| `series.set_line_width` / `set_line_color` / `set_line_style` / `set_price_visible` / `is_visible` | 指标线的运行时样式/可见性助手：线宽、颜色、虚线样式（`solid` / `dashed` / …）、价格线 / 价格标签标志（LWC `priceLineVisible` / `lastValueVisible`）以及 Python 侧最后设置的可见性 |
| `chart.remove()` | 销毁图表时也移除它的 `.handler` DOM wrapper（`Handler.destroy`）；以前只销毁引擎，残留的盒子保持旧尺寸/位置，会盖住之后创建的图表 |
| `series.delete()` + `chart.remove_pane(index)` | 删除一个序列，若它是所在 pane 的最后一个则连 pane 一起删：图例行（标签 + 眼睛）消失，后面的 pane（及其 `series.pane_index`）上移 —— 于是指标副图能在运行时切换（`examples/11_api_tour/19_indicator_panes.py`） |
| `chart.win.theme('light'\|'dark')` + `pylightcharts.themes` | 一次调用切换整站主题：根 CSS 变量（顶栏、图例、菜单）、图例文字色与眼睛图标，以及每张图的背景 / 网格 / 十字线 / 蜡烛 / 成交量 / 分隔条 / 坐标轴色 —— 之后创建的图继承它，已存在的表格也会重染，任何单个 setter 仍可覆盖它（`docs/guide/options.md#themes-whole-ui-light-dark`） |
| `chart.infinite_history(loader, page=, threshold=)` + `pylightcharts.history` | 官方无限历史 demo：图表自身的 `events.range_change`（`barsInLogicalRange().barsBefore`）向 `loader(count[, before])` 要更早的 bar，前插后视口保持不动 —— 指标（主图与副图）跟着延长，成交量重发，画线保留（`docs/guide/infinite-history.md`） |
| `chart.add_symbol(name, data, kind=, scale=, margins=, ...)` + `chart.scale_margins(right=, left=)` | 官方教程的双价格轴（主蜡烛留在右轴）：把第二个标的以 蜡烛 / 柱 / 线 / 面 / baseline / 直方图 叠加在左轴（或用 margins 上下分割叠放），标的名显示在价格线标签上（`docs/guide/two-price-scales.md`） |
| `series.tracking_tooltip(...)` / `series.magnifier_tooltip(...)`（主序列还可用 `chart.`）| 官方教程的两种十字线 tooltip 一次搞定 —— 跟随光标的盒子（靠边时翻转）或钉在 pane 顶部的半透明带；`title=` / `fields='auto'`（OHLC）/ `field_labels=` / `decimals=` / `time_format=` / `color_by_candle=` / 尺寸与配色选项，`hide()`/`show()`/`set_mode()`/`remove()`；背景/文字跟随主题 CSS 变量，标题与边框用序列色（`docs/guide/tooltips.md`） |
| `Table.set_colors(background_color=, border_color=, text_color=, section_color=)` | 表格建好后重新着色（构造函数把颜色烤进 DOM，所以 `Window.theme` 用它来重染已有表格） |
| `Table.set_position(position='top-right', margin_x=, margin_y=)` | 把浮动表格锚到四个角中的任意一个，并可离最近两条边留出像素间距 —— `create_table(...)` / `chart.create_table(...)` 接受同样的两个参数（`docs/guide/table.md`） |
| `Chart(..., attribution_logo=True)` | 每窗口的 TradingView logo（默认关） |
| `pylightcharts.compat.install_alias()` | 让 `lightweight_charts` 代码原样运行 |
| `chart.register_js_callback` + `create_series_primitive` / `create_pane_primitive` | 从 Python 写声明式 v5 primitive |
| `chart.set_price_formatter` / `set_time_formatter` | 声明式刻度格式化器（`Lib.resolveFormatter`） |
| `add_custom_series(spec={...})` + `view.visibleBars()` / `scope.mediaSize.width` —— **成交量分布图（Volume Profile）配方** | 用声明式自定义序列画**横向成交量分布**：0 刻度**固定在可视范围最右端**（`scope.mediaSize.width`，与主图成交量柱的最右边缘对齐），数值跟随十字线（按 `bar.x` 挑最近那根），并用 `series.applyOptions({})` 强制重绘 —— 实测十字线移动**不会**自己重新调用 `rendererDraw`。可叠加在主图（价格档中心）或单独副图（档位序号分层直方图）—— `examples/11_api_tour/26_volume_profile.py`（静态）与 `27_volume_profile_live.py`（实时，且遵循*实时更新优先于鼠标跟随*） |

逐点 / 条件着色（按任意条件给 bar、蜡烛或直方图值上色）是 Lightweight Charts 的功能，
由数据驱动 —— 见
[Charts and data](https://github.com/MiniBtMaster/pylightcharts/blob/main/docs/guide/charts.md#conditional-colours)。
