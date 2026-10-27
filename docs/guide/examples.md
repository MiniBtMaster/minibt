# Examples

Runnable examples live in the **repository** under `examples/` - the wheel ships
only the package - and each folder is self-contained, with its own CSV data:

```bash
pip install -e .                      # or: pip install pylightcharts
python examples/1_setting_data/setting_data.py
```

They resolve their data files relative to their own location, so they can be run
from anywhere.

!!! note "Running straight out of the repository"
    You do not have to install anything. Put the repository root on `PYTHONPATH`:

    ```bash
    PYTHONPATH=. python examples/1_setting_data/setting_data.py          # bash
    ```

    ```bat
    set PYTHONPATH=%CD%
    python examples\1_setting_data\setting_data.py
    ```

    Running an example **without** either of those fails on the import:
    `python examples/1_setting_data/setting_data.py` puts the *script's* directory
    on `sys.path`, not the current one, so `pylightcharts` is only importable when
    it is installed.

!!! tip "Stopping the live examples"
    `2_live_data` and `3_tick_data` push data until it runs out. Close the chart
    window and the loop ends by itself - `chart.is_alive` turns `False` as soon as
    the window is closed - then the webview process shuts down. `Ctrl+C` works too
    (`chart.exit()` runs in a `finally`).

| Example | Shows | Key calls |
|---|---|---|
| `1_setting_data` | getting OHLCV into a chart | `Chart()`, `set(df)`, `show(block=True)` |
| `2_live_data` | pushing new bars | `set()`, then `update(bar)` in a loop |
| `3_tick_data` | updating the last bar from ticks | `update_from_tick(tick)` |
| `4_line_indicators` | overlay lines in their own pane | `create_line()`, `legend()` |
| `5_styling` | colours, grid, crosshair, watermark | `layout()`, `candle_style()`, `crosshair()`, `grid()`, `legend()` |
| `6_callbacks` | reacting to the user | `chart.events.`, `horizontal_line()`, `legend()` |
| `7_indicators` | built-in indicators and multi-pane | `add_sma()`, `add_macd()`, `add_bollinger()`, `add_rsi()`, `add_adx()`, `add_obv()`, `add_keltner()` |
| `8_headless` | rendering a PNG without a window | `HeadlessChart()`, `render('report.png')`, `save_html('chart.html')` |
| `9_custom_series` | declarative custom series | `add_custom_series(..., shapes=...)` |
| `10_qt_migration` | embedding in a PyQt6 window | `install_alias()`, `QtChart`, `get_webview()` |
| `11_api_tour` | a runnable walk through the whole public API (27 scripts) | every documented call - see `examples/11_api_tour/README.md` |
| `12_browser` | a chart in a normal browser tab - one static page, one live stream, each with a main-pane (SMA 20) and a sub-pane (RSI 14) indicator | `BrowserChart(live=False/True)`, `show()`, `save_html()`, `update()` streaming |
| `13_panels` | the TradingView-style panel family, including **0.1.6** `QuoteBoard` / `SymbolSearch` / `AlertDialog` / `IndicatorPicker` / `TemplatePicker` | `DataGrid`, `MarketData`, `Heatmap`, `Ticker`, `QuoteBoard`, `OrderTicket`, `Screener`, ... |

Each folder holds the data it needs (`ohlcv.csv`, `ticks.csv`, …) plus a
screenshot of the result.

## What each one is really demonstrating

### `1_setting_data`

The minimum: a `DataFrame` with `time, open, high, low, close, volume` becomes a
candlestick chart. Column names are detected case-insensitively, and `time` may be
a timestamp or `datetime64`.

### `2_live_data` / `3_tick_data`

Two different notions of "live". `2_live_data` calls `update()` with a new bar,
which appends (or replaces, if the timestamp is the last one). `3_tick_data` calls
`update_from_tick()`, which folds a trade into the bar that is still forming -
useful for anything faster than the bar interval.

### `4_line_indicators` / `7_indicators`

`4_line_indicators` puts lines you computed yourself on the chart.
`7_indicators` uses `pylightcharts.indicators`, where the maths is done in pandas
and a line added with `add_macd()` keeps recalculating itself when the data
changes. `7_indicators` also shows the v5 multi-pane layout.

### `5_styling` / `6_callbacks`

`5_styling` is the "make it look right" tour: layout, colours, grid, crosshair,
watermark. `6_callbacks` is the other direction - click and crosshair events
coming back from the chart into Python through `chart.events`.

### `8_headless`

`HeadlessChart` never opens a window: it records the calls it would send to a
webview, replays them in a headless Chromium and writes a PNG. Needs Playwright
(`pip install "pylightcharts[e2e]" && playwright install chromium`) or a local
Chrome/Edge. See [Headless rendering](../advanced/headless.md).

### `9_custom_series`

Custom series are described **declaratively**: Python describes *what* to draw as
shape descriptors and the shipped JS renders them per frame. See
[Custom series](custom-series.md).

### `10_qt_migration`

The desktop path: a real PyQt6 window with the chart inside a layout, drawing
tools, screenshot. It also demonstrates the compatibility shim, so it is the
closest thing to "how do I put this in my existing application". See
[Qt integration](qt.md) and [Migrating](migration.md).

### `11_api_tour`

A runnable reference for the public API: each numbered script focuses on one
area (series types, scales, formatters, panes, drawings, custom series, …).
Most scripts can run headless, so they double as smoke tests.

### `12_browser`

The browser / notebook path. `BrowserChart(live=False)` saves a single static
HTML page; `BrowserChart(live=True)` starts a small SSE stream and keeps
appending bars. Both use the same Python API as the desktop chart.

### `13_panels`

The TradingView-style widget family. Start with `01_data_grid.py` for the
primitive, then `03_market_data.py` / `07_screener.py` for composed widgets.
The 0.1.6 additions are:

- `12_quote_board.py` - quote page (type/exchange chips, loading/empty states);
- `13_symbol_search.py` - local / remote symbol picker with keyboard navigation;
- `14_indicator_picker.py` - indicator browser with ★ favorites, plus
  `--templates` for the indicator-template dialog;
- `15_alert_dialog.py` - price-alert dialog (cross / expiry / action / qty).

All four support `--check` (no window needed) and `--snapshot output.png`.
See [`examples/13_panels/README.md`](https://github.com/MiniBtMaster/pylightcharts/blob/main/examples/13_panels/README.md)
for the full run list and panel matrix.
