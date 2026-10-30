# Headless rendering

`HeadlessChart` is an `AbstractChart` that never opens a window. It records
everything it would send to a webview, then replays it inside a headless
Chromium and returns a PNG. Useful for reports, backtests and CI.

```python
from pylightcharts.headless import HeadlessChart

chart = HeadlessChart(width=1200, height=700)
chart.set(df)
chart.add_sma('close', 20)
chart.add_bollinger('close', 20, 2)
chart.add_rsi(14)
chart.add_macd()

png = chart.render('report.png')     # also returns the PNG bytes
```

## View it in a browser (static HTML)

`to_html()` returns the whole page - the engine, the bridge bundle, the styles
and the chart's own scripts are **inlined** - so a single `.html` file is all a
browser needs. No server, no Node/npm, no extra dependency:

```python
html = chart.to_html()                    # a string
chart.save_html('chart.html')             # ... written to disk
chart.open_in_browser('chart.html')       # ... and opened (stdlib webbrowser)
```

`BrowserChart` is the same thing as a *backend* - construct it, build the chart,
call `show()` (the `Chart.show()` spelling), and it writes the file and opens it:

```python
from pylightcharts import BrowserChart

chart = BrowserChart(width=1200, height=700, path='report.html')
chart.set(df)
chart.mark_swings(length=5)
chart.show()                     # writes report.html + opens the browser
chart.add_sma('close', 20)
chart.show(open_browser=False)   # rewrite the file after more changes
```

The same works for [`StaticLWC`](../api.md) (the Jupyter / Streamlit base class),
which is what `JupyterChart` uses:

```python
from pylightcharts.widgets import StaticLWC
chart = StaticLWC(width=1200, height=700)
chart.set(df)
chart.save_html('chart.html')
```

| what | requirement |
|---|---|
| `to_html()` / `save_html()` / `open_in_browser()` | **nothing new** - the assets ship with the package |
| the exported page (pan, zoom, crosshair, toolbox, legend) | any browser, `file://` works |
| **Python callbacks** (topbar widgets, table clicks, `chart.events`) | **not available** - there is no bridge in a static page. The page dispatches them as `pylightcharts-callback` DOM events instead, so host JavaScript can react: `window.addEventListener('pylightcharts-callback', e => console.log(e.detail))` |
| live Python ↔ browser (reactive updates, callbacks) | **`BrowserChart(live=True)`** - stdlib HTTP + SSE, still zero dependencies; or a desktop webview (default `Chart`, `QtChart`, `WxChart`), `Streamlit`, Jupyter |

Runnable versions of both live here: `examples/12_browser/static.py` (a static
report page) and `examples/12_browser/live.py` (a live stream). Both build the
same chart - an SMA 20 on the price pane and an RSI 14 in a sub-pane.

### Live chart (`live=True`)

`BrowserChart(live=True)` serves the same page from a tiny stdlib server and
streams everything you do afterwards to every open tab:

```python
chart = BrowserChart(width=1200, height=700, live=True)
chart.set(history)                  # warm-up data
chart.add_sma('close', 20)
chart.mark_swings(length=10)
chart.show(block=False)             # serves + opens a tab, returns the URL
while True:
    chart.update(next_bar())        # streams as you go
    time.sleep(1)
```

- **nothing is written to disk** - the data stays in memory (`candle_data`,
  `series.data`), exactly where the chart keeps it anyway;
- a tab that connects (or reloads) is sent the current data once
  (`resync=True` by default, `resync=False` to skip it) and then only the
  changes, so the page never accumulates the stream;
- widget callbacks work: the page `POST`s them back and they run in your process
  (`chart.topbar[...]`, table clicks, `chart.events`);
- `chart.clients` counts the open tabs, `chart.url` is the address,
  `chart.stop()` shuts it down (`show(block=True)` serves until Ctrl+C);
- the page keeps a hidden counter (`#pylightcharts-live`, or
  `window.pylightchartsLiveCount`) with the number of applied updates - handy as
  a "live" badge;
- **you can see it working**: the page shows a small `live · N` badge
  (bottom-right) that counts applied updates, turns green while connected and
  red - with the reason - if the stream stops or a script fails
  (`status=False` hides it). `window.pylightchartsLiveCount` holds the same
  number;
- **`show()` opens a fresh tab** (the URL gets a per-run `?run=...` so the
  browser cannot reuse a tab that still shows an older page); the *printed* URL
  is the clean one - keep a tab on it and press F5 to reload the current page;
- **the port**: `port=0` (default) picks a free port, so the URL changes every
  run; pass a fixed `port=` (e.g. `port=8123`) to keep one address and just press
  F5 - a busy port falls back to a free one with a warning, and `chart.url`
  always holds the real address (`port_fallback=False` raises instead);
- **build first, then `show()`**: the page a new tab receives is the layout as
  of `show()` (series, panes, indicators, top bar), and the stream after it
  carries data updates - a series created later only appears in tabs that were
  open at that moment. A tab whose stream ended (python stopped, or the port
  changed) shows a red "disconnected" banner instead of freezing silently;
- **watching from another device**: `host='0.0.0.0'` exposes the server on the
  LAN (a phone on the same Wi-Fi works). Do set `token=...` then - every request
  has to carry it (`?token=` in the URL, `X-Auth-Token` for callbacks), otherwise
  anyone who can reach the port could watch the chart *and* run its widget
  callbacks in your process. Without a token a non-local `host` only warns;
- **if a proxy/antivirus cuts Server-Sent Events** the page falls back to
  long-polling by itself (`/poll`, plain request/response - nothing to install).
  `?transport=poll` in the URL forces that transport for debugging;
- **readbacks are unavailable** (`chart_options()`, `screenshot()`,
  `constants.verify()`, ...): a browser tab has no synchronous reply channel,
  same as `HeadlessChart`.

Screenshot-style rendering (`render()`) needs a Chromium-family browser:

## Backends

`render()` uses [Playwright](https://playwright.dev/python/) when installed,
otherwise a local Chrome/Edge in headless mode.

```bash
pip install "pylightcharts[e2e]"
playwright install chromium
```

Or point at a browser manually:

```bash
export PYLIGHTCHARTS_CHROME="/usr/bin/chromium"
```

```python
from pylightcharts.headless import find_browser
find_browser()          # -> path or None
```

## Options

```python
chart.render(
    path='chart.png',
    width=1600,                  # defaults to the constructor size
    height=900,
    wait_ms=1500,                # time for layout/fonts
    device_scale_factor=2.0,     # retina output (Playwright only)
)
```

## Getting the HTML instead

```python
html = chart.to_html()           # self-contained page (engine + bundle inline)
script = chart.to_scripts()      # just the recorded bridge statements
```

That is handy if you want to render with your own browser automation, embed the
chart in an email, or diff the generated program in tests.

## Notes

- Every normal API works: series, panes, indicators, drawings, custom series.
- Query methods that need a live webview (`version()`, `pane_size()`,
  `get_visible_range()`, ...) are not available — `pane_count()` falls back to
  the Python-side counter.
- Drawing tools are rendered; interactive editing is not.
