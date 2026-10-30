# pylightcharts

[![PyPI](https://img.shields.io/pypi/v/pylightcharts.svg)](https://pypi.org/project/pylightcharts/)
[![Python versions](https://img.shields.io/pypi/pyversions/pylightcharts.svg)](https://pypi.org/project/pylightcharts/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/MiniBtMaster/pylightcharts/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue.svg)](https://github.com/MiniBtMaster/pylightcharts/tree/main/docs)

**English** | [简体中文](README.zh-CN.md)

Python bindings for [TradingView Lightweight Charts™](https://github.com/tradingview/lightweight-charts),
aiming at **near-full API coverage** with a pythonic interface.

> Status: **Lightweight Charts v5.2.1 API fully covered (150/150 interface methods)** —
> 17 indicators, 13 drawing tools, numeric axes, formatters, v5 plugins, declarative
> primitives, custom series, custom horizontal scales, CI with JS + Python tests and docs.
> Method-by-method table: [`API_IMPLEMENTATION_REPORT.md`](https://github.com/MiniBtMaster/pylightcharts/blob/main/docs/advanced/api-implementation-report.md).
>
> Plus a **financial-panels layer** — TradingView-style market widgets (market tables,
> watchlists, screeners, heatmaps, tickers, quote headers, technical analysis, seasonal,
> news, calendar, symbol details, …) rendered on the same host page and driven from Python.
> See [Financial panels](#financial-panels-tradingview-style-widgets).
>
> Release notes: [`docs/changelog.md`](docs/changelog.md) — latest **0.1.7**.

## How it works

This is **not** a re-implementation of the charting engine in Python.
It embeds the official, battle-tested JavaScript renderer in a WebView
(pywebview / Qt WebEngine / wx / Jupyter / Streamlit) and drives it from Python.

```
Python API  ──►  JSON / JS bridge  ──►  Lib.Handler (TypeScript)  ──►  Lightweight Charts v5
```

Because the pixels and interactions are produced by the upstream library,
visual fidelity and performance match the JS version.

## API coverage

pylightcharts drives the upstream engine directly, so **every public method** of
Lightweight Charts v5.2.1 is reachable. Coverage is measured by
`scripts/check_api_coverage.py`, which parses the upstream `typings.d.ts`:

| Group | Coverage |
|---|---|
| `IChartApi` / `ISeriesApi` / `ITimeScaleApi` / `IPriceScaleApi` / `IPaneApi` / `IPriceLine` | 100% |
| v5 plugins (series markers, up/down markers, text & image watermarks) | 100% |
| `ISeriesPrimitive` / `IPanePrimitive` (declarative, from Python) | 100% |
| `ICustomSeriesPaneView` / `ICustomSeriesPaneRenderer` | 100% |
| `IHorzScaleBehavior` (custom horizontal scale) | 100% |
| options / type aliases (~120) | 100% passthrough |
| 11 enums + all top-level functions | exported (`Lib.*` + `pylightcharts.constants`) |

```bash
python scripts/check_api_coverage.py          # print the matrix
python scripts/check_api_coverage.py --check  # fail CI if coverage regresses
```

Full method-by-method table and the list of intentional differences:
[`API_IMPLEMENTATION_REPORT.md`](https://github.com/MiniBtMaster/pylightcharts/blob/main/docs/advanced/api-implementation-report.md).

## Financial panels (TradingView-style widgets)

On top of the chart engine, `pylightcharts` ships a **panels layer**
(`pylightcharts.panels`) that reimplements the TradingView widget family as DOM
components on the **same host page** — no extra chart instance, so hundreds of
table rows and heatmap tiles stay cheap. A panel is created on a `Window` (a
chart's `win`, or a chart-less `QtPanel`) and driven from Python:

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

| Panel | TradingView widget |
|---|---|
| `QuoteBoard` | quote page: type/exchange chips + grid + ticker + loading/empty states |
| `SymbolSearch` / `AlertDialog` | symbol picker / price-alert dialog |
| `IndicatorPicker` / `TemplatePicker` | indicator browser (with ★ favorites) / indicator templates |
| `DataGrid` / `Column` | the market-table primitive |
| `MarketData`, `Watchlist` | Market Data / Market Overview / Market Summary / Watchlist |
| `Screener` + `FilterBar` | Screener (conditions, named presets, JSON persistence) |
| `Heatmap` (`StockHeatmap` / `CryptoHeatmap` / `EtfHeatmap` / `ForexHeatmap`) | Stock / Crypto / ETF / Forex Heatmap |
| `Ticker` (`TickerTape` / `TickerTag` / `SingleTicker` / `Tickers`) | Ticker Tape / Tag / Single ticker / Tickers |
| `OrderTicket` | the buy / spread / sell ticket |
| `QuoteHeader` / `SymbolInfo` / `SymbolOverview` / `MiniChart` | Symbol Info / Symbol Overview / Mini Chart |
| `TechnicalAnalysis` (+ `ta_summary`) | Technical Analysis (gauge + oscillator / MA tables) |
| `SeasonalChart` (+ `seasonal_monthly`) | Seasonal Chart |
| `EconomicCalendar` / `FundamentalData` / `CompanyProfile` / `BrokerRating` / `BrokerReviews` | symbol-detail shells |
| `NewsFeed` / `TopStories` / `TextBlock` | Top Stories / news |

- **Themes**: every panel follows the window theme — `chart.win.theme('light')`
  (or `'dark'`, the default); panels created afterwards inherit it. Both skins are styled.
- **Data**: the library ships **no market data** — the host feeds rows / items /
  quotes (minibt, tqapi, CSV, …). The news / fundamentals / calendar / broker panels
  are UI + data-contract shells.
- **Examples**: `examples/13_panels/01_data_grid.py` … `15_alert_dialog.py`
  (the 0.1.6 additions are `12_quote_board`, `13_symbol_search`,
  `14_indicator_picker` and `15_alert_dialog`; each supports `--check` and
  some `--snapshot`).
  `10_gallery.py` is a scrollable gallery of every widget. Guide:
  [`docs/guide/panels.md`](docs/guide/panels.md).

## Acknowledgements / License

- Python layer, GUI backends and drawing plugins are derived from
  [lightweight-charts-python](https://github.com/louisnw01/lightweight-charts-python) (MIT).
- The charting engine is
  [TradingView Lightweight Charts™](https://github.com/tradingview/lightweight-charts) (Apache-2.0),
  see `NOTICE`.

## Migrating from lightweight-charts-python
`pylightcharts` keeps every class, method and module-level name of the original
package (enforced by `tests/test_lwc_compat.py`), so existing code runs with a
one-line shim:

```python
from pylightcharts.compat import install_alias
install_alias()                     # before any `import lightweight_charts`

import lightweight_charts            # -> pylightcharts
lightweight_charts.widgets.QWebEngineView = MyPyQt6WebEngineView   # patching still works
```

Or change the imports directly:

```diff
- from lightweight_charts.util import Events, JSEmitter
- from lightweight_charts.widgets import QtChart
+ from pylightcharts.util import Events, JSEmitter
+ from pylightcharts.widgets import QtChart
```

## Qt integration

Inside a desktop application, `QtChart` embeds the chart in a `QWebEngineView`:

```python
from PyQt6.QtWidgets import QApplication
from pylightcharts.qt import prepare_qt

prepare_qt('PyQt6')          # pick the binding *before* QApplication
app = QApplication([])

from pylightcharts.widgets import QtChart
chart = QtChart(toolbox=True)
chart.set(df)
chart.get_webview().show()
app.exec()
```

`QtWebEngineWidgets` must be imported before the `QApplication` exists, which is
why `prepare_qt()` comes first; `$PYLIGHTCHARTS_QT` chooses the binding without it.
Full details - multi-chart `sync()`, screenshots, the Chromium network noise -
are in `docs/guide/qt.md`.

## Examples

### Full API tour (`examples/11_api_tour/`)

Runnable, visual scripts that walk **every public API**. Each file exposes
`build(chart)` (so it can be driven headlessly in tests) and a `main()` that opens
a window:

| File | Covers |
|---|---|
| `01_chart_and_data.py` | `set` / `update` / `update_from_tick` / `batch`, layout, grid, crosshair, legend, watermark, candle & volume style, precision, options |
| `02_series_types.py` | Line/Area/Bar/Baseline/Histogram/Candlestick, price lines, markers, data readback, coordinate conversion, order, panes |
| `03_scales_and_queries.py` | time scale (scroll / range / convert / formatters), price scale, pane queries, `chart_options`, `chart_element`, `version` |
| `04_events.py` | click / dblclick / crosshair / range / visible-time / size / data-changed / new-bar / search / hotkeys |
| `05_drawings.py` | all 13 drawing tools + `vertical_span`, plus `update` / `delete` / `options` |
| `06_panes.py` | panes, stretch / height / preserve, pane primitives, pane-level series |
| `07_indicators.py` | all 17 indicators, `add_indicator`, `add_computed_series` |
| `08_custom_series.py` | every shape + presets + custom pane-view spec |
| `09_plugins.py` | markers / up-down / text & image watermark lifecycles |
| `10_primitives.py` | declarative series & pane primitives, all extension points |
| `11_callbacks.py` | formatters, tick marks, price format, autoscale, constants |
| `12_numeric_and_scale.py` | YieldCurve / Options charts, custom horizontal scale |
| `13_workspace.py` | table, topbar widgets, toolbox, subcharts, sync, screenshot |
| `14_multi_chart_layout.py` … `23_fill_between_gaps.py` | page top bar, whole-UI themes, tooltips, two symbols, infinite history, indicator panes, stem/scatter, multi-line text, NaN line & fill-between gaps - see `examples/11_api_tour/README.md` |
| `24_layouts_and_legend_settings.py` | the migration extensions: 2D `arrange_tiles(dividers=True)` layouts, the legend gear (`enable_legend_settings`) and pinned legend rows (`pin_legend_row`), and the series style helpers (`set_line_*` / `set_price_visible` / `is_visible`) + `chart.remove()` |
| `25_live_value_table.py` … `27_volume_profile_live.py` | crosshair-driven value table + live updates (`25`), and the Volume Profile recipe (`26` static, `27` live) - a mouse-following volume distribution pinned to the right edge of the visible range - see `examples/11_api_tour/README.md` |

### Financial panels (`examples/13_panels/`)

Ten scripts covering the panels layer (mock data, `--snapshot`, `PYLIGHTCHARTS_QT=`
switchable): `01_data_grid`, `02_sparkline`, `03_market_data`, `04_ticker_and_quote`,
`05_heatmap`, `06_seasonal`, `07_screener`, `08_details`, `09_technical`, and
`10_gallery.py` — the last one lays every widget out in a scrollable grid so you can
see them all at once — plus `11_sim_account_shell.py` (a full-page simulated-account
shell with an order ticket). See [`examples/13_panels/README.md`](examples/13_panels/README.md).

### Focused examples (original ten)

`examples/1_setting_data` … `examples/12_browser` each keep a single topic with
its own data: loading OHLCV, live bars, tick updates, indicator lines, styling,
callbacks, built-in indicators, headless PNG rendering, charts in a browser tab
(`examples/12_browser/static.py` and `live.py`, both with a main-pane SMA and a
sub-pane RSI), custom series and the PyQt6 window. Start with
`examples/1_setting_data/setting_data.py`.

## Development

```bash
# build the JS bridge + vendor the engine into pylightcharts/js/
cd jslib && npm install && npm run build

# install the python package in editable mode
cd .. && pip install -e .

# ...or use the requirement files (pyproject.toml stays the source of truth)
pip install -r requirements.txt        # runtime only
pip install -r requirements-dev.txt    # + tests, e2e, docs, build
```

### Testing

```bash
# unit tests: assert on the JS generated by the python bridge (no browser)
python -m pytest -m "not slow"

# e2e: run the built bundle in headless Chromium and check rendered pixels
python tests/e2e/smoke.py

# headless rendering tests (Playwright or a local Chrome/Edge)
python -m pytest tests/test_headless.py

# full stack: real pywebview window + real chart engine (needs a desktop session)
python tests/e2e/full_stack.py

# performance: JSON vs binary bulk data transfer
python tests/e2e/benchmark.py 100000
```

CI (`.github/workflows/ci.yml`) builds the bundle, checks the committed artifacts
are up to date, runs the unit tests on Linux/Windows/macOS, renders in headless
Chromium and verifies the wheel ships the JS assets.

### Deferred work

Features that are possible but deliberately not implemented yet - touch drag
for the layout dividers, grid layouts, destroying a chart, `zOrder` for the
span primitives, ... - are collected in
[`docs/advanced/deferred.md`](https://github.com/MiniBtMaster/pylightcharts/blob/main/docs/advanced/deferred.md) together with the file
and the sketch for each one. Add an entry there instead of leaving a bare
`TODO` in the source.

### Packaging

```bash
cd jslib && npm run build      # regenerate pylightcharts/js/*
cd .. && python -m build       # sdist + wheel (JS assets are package-data)
twine upload dist/*
```

The built `pylightcharts/js/` files are committed on purpose so that
`pip install` works without Node. Always run `npm run build` before committing.

### Bridge rules

- Fire-and-forget calls go through `Window.invoke` (the transport appends
  `;undefined` so pywebview never serialises a live chart object).
- Methods that **return an object** must use `store_as=...` or, for primitives,
  `invoke_get`. Returning a live object through `invoke_get` would explode.
- Round-trips are serialised and correlated by request id; JS errors raise
  `pylightcharts.util.BridgeError` instead of returning `None`.
- Chart and series share method names (`apply_options`); they are deliberately
  kept apart (`series_options`, `data_points`) to avoid MRO shadowing.
- Upgrading lightweight-charts: `npm pack lightweight-charts@X`, migrate the
  breaking changes, `npm run build`, then run the e2e suite.

### The generic bridge

New features should not require touching TypeScript. Any method on any live
chart object can be called from Python:

```python
chart._invoke('addSeries', 'Area', 'my area', {'lineWidth': 2}, handle)
chart.win.invoke(f'{series.id}.series', 'applyOptions', {'lineWidth': 3})
```

Handles are either registered via `Lib.register(...)` or dotted window paths
(`window.abcdefgh.chart`). A `{'$ref': handle}` argument is resolved to the live
JS object, so object-taking APIs work too:

```python
series.attach_primitive('myPrimitive')   # -> attachPrimitive({"$ref": "myPrimitive"})
```

See `jslib/src/general/rpc.ts`.

### Full option coverage

`apply_options(**kwargs)` accepts any option of the underlying API and converts
`snake_case` keys to `camelCase` automatically:

```python
chart.apply_options(auto_size=True, localization={'price_format': {'precision': 4}})
chart.time_scale_options(right_offset=5, bar_spacing=8)   # time scale
series.apply_options(line_width=3, crosshair_marker_visible=False)
get = chart.get_price_scale('left'); get.set_mode('logarithmic')
```

### Indicators

Pure-pandas implementations, no extra dependencies. Overlays go on the price
pane, oscillators get their own pane automatically:

```python
chart.add_sma('close', 20)
chart.add_ema('close', 50, color='#2196F3')
chart.add_bollinger('close', 20, 2)      # -> (upper, middle, lower)
chart.add_donchian(20)
chart.add_vwap()

chart.add_rsi(14)                        # own pane + 70/30 guide lines
chart.add_macd()                         # own pane -> (macd, signal, histogram)
chart.add_stochastic()                   # own pane -> (%K, %D)
chart.add_atr(14)
chart.add_adx(14)                        # own pane -> (adx, +DI, -DI)
chart.add_obv()                          # own pane (needs volume)
chart.add_cci(20)
chart.add_williams_r(14)
chart.add_mfi(14)
chart.add_roc(12)
chart.add_keltner(20, 2.0)               # overlay -> (upper, middle, lower)
```

Raw values: `from pylightcharts import indicators; indicators.rsi(close, 14)`.
RSI, OBV, CCI, %R, ROC, MFI and Bollinger match TA-Lib to floating-point
precision; ATR and ADX match within ~1e-4 and ~0.1 respectively (Wilder
accumulation rounding).

#### Indicators follow the data

Every indicator is recomputed automatically: a full re-send on `chart.set()`,
and a single-point update on `chart.update(bar)` (recomputed from a warm-up
window so recursive indicators stay numerically identical to a full run).
`add_computed_series(compute, name, ...)` adds your own.

#### Batching ticks

Each bridge call is one webview round-trip, so wrap bursts in `chart.batch()`:

```python
with chart.batch():
    for tick in ticks:
        chart.update(tick)      # flushed as a single script
```

#### Conflation (very large data)

Conflation is a plain series option, so the bridge already exposes it:

```python
chart.apply_options(enable_conflation=True, precompute_conflation_on_init=True)
series.apply_options(enable_conflation=True)
```

### Custom series (declarative rendering)

The tricky part of a custom series is `draw()`, which runs synchronously every
frame - python cannot take part in that. So the protocol splits the work:
**python computes the shapes once per data update, one generic JS renderer draws
them every frame.**

```python
from pylightcharts import shapes

series = chart.add_custom_series('range bars', pane_index='new')
series.set(df, shapes=lambda row: shapes.range_bar(row['low'], row['high']))
```

Shape builders: `rect` `band` `line` `circle` `marker` `text` `polyline`, plus
presets `range_bar` `box_plot` `error_bar` `stem`.

`shapes.stem(price, baseline=0.0, style='dashed', cap=False)` draws a vertical
stick from `baseline` to `price` - the easy way to show per-trade PnL, deviation
from a mean, or volume-at-price as bars hanging off a common axis:

```python
series.set(df, shapes=lambda row: shapes.stem(row['pnl'], color=row['color'],
                                              cap=True))
``` Vertical anchors are prices,
horizontal offsets are in bar units (`-0.4..0.4` spans a bar) - except
`shapes.marker`, whose `offset`/`size` are **pixels** (zoom-invariant glyphs;
`marker=` takes a minibt `Markers` name: `triangle` `inverted_triangle`
`arrow_up` `arrow_down` `circle` `circle_cross` `circle_dot` `circle_x`
`circle_y` `square` `dot` `dash` `cross` `asterisk` `triangle_dot`).

```python
shapes.box_plot(low, q1, median, q3, high)
shapes.polyline([(0.0, 1.0), (0.4, 2.0)], fill_color='rgba(0,0,0,0.2)')
shapes.text(price, 'label\nsecond line',   # multi-line (like bokeh's LabelSet)
            offset_x=6, font_weight='bold',              # pixel offset / bold
            background_color='#222', padding=4)         # label box + padding
```

Each data item may carry `value`, `low`, `high` (autoscale + last value),
`color`, and `shapes`.

### v5 plugins (markers / up-down markers / watermarks)

v5 moved markers and watermarks to *primitives*; each has a full Python wrapper:

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

### Function-valued options (formatters & providers)

Callbacks run synchronously inside the render loop, so register a small JS body
and inject it at any option path:

```python
chart.register_js_callback('vol', ['price'], "return (price/1e6).toFixed(1)+'M'")
chart.set_tick_mark_formatter('vol')            # timeScale.tickMarkFormatter

series.set_price_format_formatter('vol')        # merge-safe priceFormat.formatter
series.set_autoscale_info_provider('vol')       # series.autoscaleInfoProvider

chart.set_option_callback(f'{chart.id}.chart', 'applyOptions',
                          'localization.priceFormatter', 'vol')
chart.set_price_formatter_callback('vol'); chart.set_time_formatter_callback('vol')
```

### Declarative primitives

```python
chart.register_js_callback(
    'draw', ['target', 'pc', 'view', 'prim'],
    "const y = prim.series.priceToCoordinate(100); /* draw with target.useBitmapCoordinateSpace */")
prim = chart.create_series_primitive({
    'paneViews': [{'draw': 'draw', 'zOrder': 'top'}],
    'priceAxisViews': [{'coordinate': 'coord', 'text': 'label'}],
    'hitTest': 'hit', 'autoscaleInfo': 'scale',
})
prim.attach_to(series)

pane_prim = chart.create_pane_primitive({'paneViews': [{'draw': 'draw'}]})
pane_prim.attach_to(chart, 0)
```

### Custom horizontal scale

```python
class MonthChart(Chart):
    _horz_scale_name = 'month'
    _horz_scale = {
        'formatTickmark': (['tickMark', 'loc'], "return 'M' + tickMark"),
        'formatHorzItem': (['item'], "return 'M' + item"),
    }
```

### Constants & emulation checks

```python
from pylightcharts.constants import LineStyle, PriceScaleMode, CrosshairMode, verify
chart.apply_options(crosshair={'mode': CrosshairMode.Magnet})
chart.price_scale(mode=PriceScaleMode.Logarithmic)
series.apply_options(line_style=LineStyle.Dashed)
verify(chart)          # [] when the Python constants match the embedded engine
```

### Price lines, data readback, events

```python
line = series.create_price_line(105.0, color='#00e676', title='entry')
line.apply_options(line_visible=False)
line.remove()

series.price_to_coordinate(105)        # <-> series.coordinate_to_price(y)
series.data_by_index(10)               # individual bar
series.data_points()                   # everything the chart holds
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

### Multi-chart sync

```python
price = Chart(); volume = Chart()
price.sync(volume)                       # volume follows price pan/zoom
price.sync(volume, crosshairs_only=True)
```

### Native panes (lightweight-charts v5)

```python
chart.add_pane()
chart.create_area(name='close', pane_index=1)
chart.add_series('Line', 'ma20', pane_index=1, color='#0ff')
chart.set_pane_stretch(1, 1.5)
chart.pane_count()
```

`pane_index='new'` creates a fresh pane, and passing an index beyond the
current pane count creates the panes in between.

### Drawing tools

Trend line / horizontal line / vertical line / ray / box, plus:

```python
chart.fibonacci(t1, p1, t2, p2, levels=(0, 0.382, 0.5, 0.618, 1))
chart.measure(t1, p1, t2, p2)                       # price %, bar count
chart.parallel_channel(t1, p1, t2, p2, offset=5)    # second line 5 price units away
chart.position(t1, entry, t2, target, risk_ratio=1.5)   # profit + stop zones
chart.long_position(t1, entry, t2, target)          # aliases
chart.short_position(t1, entry, t2, target)

chart.andrews_pitchfork(t1, p1, t2, p2, t3, p3)     # 3 points
chart.triangle(t1, p1, t2, p2, t3, p3)              # 3 points
chart.fibonacci_extension(t1, p1, t2, p2, t3, p3)   # impulse + retracement
chart.gann_fan(t1, p1, t2, p2)                      # 1x1 plus steeper/shallower rays
```

With `toolbox=True` these are also available interactively
(Alt+F / M / C / P / A / G / X / N).

### Numeric axes and formatters

```python
from pylightcharts import YieldCurveChart, OptionsChart

curve = YieldCurveChart()                 # x axis = duration in months
series = curve.add_series('Line', 'rate')
series.set(pd.DataFrame({'time': [1, 3, 12], 'rate': [4.2, 4.0, 3.6]}))

surface = OptionsChart()                  # x axis = strike

chart.set_price_formatter(decimals=2, thousands=True, prefix='$')
chart.set_time_formatter('YYYY-MM-DD HH:mm')
chart.register_js_formatter('eur', "value => '\u20ac' + value.toFixed(2)")
chart.set_price_formatter(name='eur')
```

### Large data

DataFrames with 2000+ rows are transferred as a base64 column-major Float64
buffer and rebuilt in the browser (`Lib.decodeData`) instead of being shipped as
JavaScript source. Measured 100k bars: **1.56s -> 0.54s (~3x)**;
500k bars: **8.9s -> 3.2s**. Tune with `pylightcharts.util.BINARY_DATA_THRESHOLD`.

### Headless / server-side rendering

```python
from pylightcharts.headless import HeadlessChart

chart = HeadlessChart(width=1200, height=700)
chart.set(df)
chart.add_sma('close', 20)
chart.add_rsi(14)
chart.render('report.png')        # PNG bytes, no window required
chart.to_html()                   # or grab the standalone HTML
```

Uses Playwright when installed, otherwise a local Chrome/Edge in headless mode
(`PYLIGHTCHARTS_CHROME` overrides the browser path).


## pylightcharts extensions

APIs that `pylightcharts` adds on top of the upstream Lightweight Charts /
lightweight-charts-python surface. New additions are listed here (briefly) and
documented in detail under `docs/`.

| API | what it does |
|---|---|
| `legend_toggle=` / `legend=` on every series factory & indicator | draw the legend row, and its eye icon, or neither |
| `chart.horizontal_span(low, high, color=, opacity=, filled=, pane_index=)` | shaded price band (support / resistance); `pane_index=` puts it in a sub-pane |
| `chart.fill_between(upper, lower, color=, opacity=)` / `upper.fill_between(lower)` | fill the area between two series lines (band body) |
| `opacity=` on `horizontal_span` / `fill_between` / `vertical_span` | fill alpha for any colour format, outline stays crisp |
| `chart.pane_separator(color=, hover_color=, enable_resize=)` | restyle / hide the 1px divider between panes |
| `chart.pane_height()` / `set_pane_height(px, i)` (wraps `IPaneApi`) | read / set a pane's absolute height |
| `chart.mark_swings(...)` + `indicators.swing_points` | `length`-bar fractal swing highs / lows with their price as the marker text (Lightweight Charts itself only draws the markers) |
| `chart.add_zigzag(threshold=)` + `indicators.zigzag` | 波段线: alternating pivots after a minimum percentage retracement, drawn as a line and kept in sync like an indicator (`include_unconfirmed` shows the still-open leg; `inverted=` for a flipped price scale) |
| `BrowserChart` + `to_html()` / `save_html()` / `open_in_browser()` | one self-contained HTML page (engine + bridge + styles inlined) - `BrowserChart(...).show()` writes and opens it: browser view with no server, Node or extra dependency |
| `BrowserChart(live=True)` + `LiveServer` | live chart in a browser tab: a stdlib HTTP + Server-Sent-Events stream (long-polling fallback, optional `token=` for LAN/phone viewing) carries every `set`/`update`/`apply_options` to the page and widget callbacks are posted back into Python - still zero dependencies, nothing written to disk |
| `color_by(...)` / `series.color_by(...)` / `chart.color_by(...)` | per-point / conditional colours: fills the engine's `color` / `wickColor` / `borderColor` keys, for any series (indicator lines included) and the main candles (`docs/guide/charts.md#conditional-colours`) |
| `Chart(..., keyboard=True, keyboard_step=0.1)` + arrow keys | built-in navigation: arrows move the visible window / zoom (zooming out keeps the right edge pinned once the newest bar is on screen), `Shift` big step, `Ctrl`+arrows & `PageUp/Down` a full page, `Home`/`End`, `Ctrl+0` to fit; user `hotkey()`s take precedence and typing is ignored |
| `chart.win.page_topbar()` | a top bar that spans the window and stays above every chart (a `chart.topbar` lives inside one chart and shrinks with it) |
| `chart.win.layout` (`Layout`) | tile the window with charts: `vertical()` / `horizontal()` / `arrange(kind, count)` / `single()`, independent by default (`sync=True` links pan/zoom/crosshair, `sync='crosshair'` only the crosshair), plus `on_create=` to feed new charts; draggable separators between the charts (`divider_size=` / `set_divider(...)`) |
| `Layout.arrange_tiles(tiles, dividers=True)` + `Lib.clearLayoutTiles` | **2D tile layouts** (TradingView-style "top 1 / bottom 2"): `tiles` is an ordered list of `(width, height)` fractions - `[(1.0, 0.5), (0.5, 0.5), (0.5, 0.5)]`. A single column/row and a row-flow (2D) layout both get **draggable separators** between rows and between the columns of a row; switching back to a float layout (`arrange()` / `single()`) emits `clearLayoutTiles` and restores the normal float geometry (`examples/11_api_tour/24_layouts_and_legend_settings.py`) |
| `series.enable_legend_settings(callback)` | add a **settings (gear) button** to a series' legend row; clicking it calls `callback(series, x, y)` (the click position inside the webview, so a settings card can pop up next to the legend). Replaces "watch every mouse move over the legend" with a single click round-trip |
| `series.pin_legend_row(True)` | keep a series' legend row **always visible** (by default rows only appear while the crosshair is over a bar), so an indicator's name + eye + gear stay on screen |
| `series.enable_legend_menu(config, callback)` | the **Qt-free** counterpart of `enable_legend_settings`: a self-contained JS menu on the gear button (`参数` / `线型` / `线宽` / `线颜色` / `其它设置`); each change calls `callback(series, kind, payload)` |
| `series.remove_legend_row()` | remove a series' legend row outright (idempotent) — what `legend=False` now uses internally, since the JS side builds a row for every series |
| `chart.enable_legend_collapse()` | the TradingView-style `∧` / `∨ N` collapse button below the indicator legend rows (hides itself when there are none) |
| `chart.horizontal_line(..., text=, label_visible=, label_background_color=, label_text_color=, label_font=)` | draw the label **inside the pane** (pinned to the visible range's left edge); `axis_label_visible=False` now also stops the hidden badge from widening the price scale |
| `series.remove_markers(ids)` + `marker(..., size=)` | remove many markers with one re-render, and pass the v5 marker `size` through |
| `series.skip_gap_segments()` / `prefer_single_gap()` / `repaint_gaps()` | tune the NaN-break renderer: never split hidden `fill_between` carriers, prefer the single-series transparent-gap path for realtime lines, and re-send after a colour change |
| `series.set_line_width` / `set_line_color` / `set_line_style` / `set_price_visible` / `is_visible` | runtime style/visibility helpers for indicator lines: line width, colour, dash style (`solid` / `dashed` / ...), the price line / price label flags (LWC `priceLineVisible` / `lastValueVisible`) and the last visibility set from Python |
| `chart.remove()` | destroying a chart now also removes its `.handler` DOM wrapper (`Handler.destroy`); previously only the engine was disposed and the leftover box kept its old size / position and covered the charts created next |
| `series.delete()` + `chart.remove_pane(index)` | remove a series and, when it was the last one in its pane, the pane with it: the legend row (label + eye) goes away and the later panes (and their `series.pane_index`) shift up - so an indicator sub-chart can be swapped at runtime (`examples/11_api_tour/19_indicator_panes.py`) |
| `chart.win.theme('light'\|'dark')` + `pylightcharts.themes` | whole-UI theme in one call: root CSS variables (top bar, legend, menus), the legend text colour and its eye icon and, on every chart, background / grid / crosshair / candles / volume / separator / scale colours - later charts inherit it, existing tables are recoloured too and any single setter still overrides it (`docs/guide/options.md#themes-whole-ui-light-dark`) |
| `chart.infinite_history(loader, page=, threshold=)` + `pylightcharts.history` | the official infinite-history demo: the chart's own `events.range_change` (`barsInLogicalRange().barsBefore`) asks `loader(count[, before])` for older bars, which are prepended so the viewport stays put - indicators (main pane and sub-panes) extend with them, volume is re-sent and the drawings are kept (`docs/guide/infinite-history.md`) |
| `chart.add_symbol(name, data, kind=, scale=, margins=, ...)` + `chart.scale_margins(right=, left=)` | the official tutorial's two price scales with the main candles kept on the right axis: overlay a second symbol as candles / bars / line / area / baseline / histogram on the left one (or overlap-stack them with margins), with the symbol on the price line label (`docs/guide/two-price-scales.md`) |
| `series.tracking_tooltip(...)` / `series.magnifier_tooltip(...)` (+ `chart.` for the main series) | the official tutorial's two crosshair tooltips in one call - a box that follows the cursor (flipping near the edges) or a translucent band pinned to the top of the pane; `title=` / `fields='auto'` (OHLC) / `field_labels=` / `decimals=` / `time_format=` / `color_by_candle=` / size and colour options, `hide()`/`show()`/`set_mode()`/`remove()`; background/text follow the theme's CSS variables while the title and frame use the series colour (`docs/guide/tooltips.md`) |
| `Table.set_colors(background_color=, border_color=, text_color=, section_color=)` | restyle a floating table after it was built (the constructor paints the colours into the DOM, so this is what `Window.theme` uses on existing tables) |
| `Table.set_position(position='top-right', margin_x=, margin_y=)` | anchor a floating table to any of the four corners and inset it from the nearest two edges - the same two keywords are accepted by `create_table(...)`/`chart.create_table(...)` (`docs/guide/table.md`) |
| `Chart(..., attribution_logo=True)` | per-window TradingView logo (off by default) |
| `pylightcharts.compat.install_alias()` | run `lightweight_charts` code unchanged |
| `chart.register_js_callback` + `create_series_primitive` / `create_pane_primitive` | declarative v5 primitives from Python |
| `chart.set_price_formatter` / `set_time_formatter` | declarative tick formatters (`Lib.resolveFormatter`) |
| `add_custom_series(spec={...})` + `view.visibleBars()` / `scope.mediaSize.width` - **Volume Profile recipe** | build a horizontal volume distribution on the declarative custom-series API: the 0-line is pinned to the **right edge of the visible pane** (`scope.mediaSize.width`, flush with the volume bars), the values follow the crosshair (nearest `bar.x`), and `series.applyOptions({})` forces the repaint - a crosshair move does **not** re-run `rendererDraw` on its own. Works overlaid on the main pane (price bins) or in its own pane (bin indices, layered histogram) - `examples/11_api_tour/26_volume_profile.py` (static) and `27_volume_profile_live.py` (live, with *realtime update beats mouse-follow* ordering) |

Per-point / conditional colours (colour a bar, candle or histogram value by any
condition) are a Lightweight Charts feature driven from the data - see
[Charts and data](https://github.com/MiniBtMaster/pylightcharts/blob/main/docs/guide/charts.md#conditional-colours).
