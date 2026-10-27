# Infinite history

The official
[infinite history demo](https://tradingview.github.io/lightweight-charts/tutorials/demos/infinite-history)
subscribes to the visible logical range and prepends another chunk of bars every
time the viewport gets close to the left edge - the engine keeps the view where
it is, so the chart feels endless. This package does the same, with the chunk
coming from Python:

```python
def load(count, before=None):
    return db.read_bars(end=before, limit=count)      # older than `before`

history = chart.infinite_history(load, page=300, threshold=80)
```

`chart.infinite_history(loader, ...)` subscribes to the chart's own
`events.range_change` - which is `barsInLogicalRange().barsBefore`, already
debounced - and calls `check(bars_before)`. When fewer than `threshold` bars are
left of the viewport it asks the loader for at least `page` bars, puts them in
front of the data and re-sends the series. Scrolling past the first bar loads
more again (`barsBefore` goes negative).

| option | meaning |
| --- | --- |
| `page=` | how many bars one request asks for (default 200) |
| `threshold=` | load once fewer than this many bars are left of the view (default 50) |
| `spinner=True` | show the chart's loading spinner while the loader runs |
| `on_load=`, `on_exhausted=` | callbacks `(history, added)` / `(history,)` |
| `max_requests=` | stop after N chunks |
| `autostart=False` | do not subscribe to the range (call `start()` yourself) |

## The loader

It is called as `loader(count)`, `loader(count, before)` or
`loader(count, before=...)` and returns anything `set()` accepts:

* a DataFrame with a `time` column plus OHLC / value (and volume for the main
  chart) - `date` / `datetime` / `timestamp` and a datetime index work too,
* a Series with a time index,
* `None` or an empty frame to say "that was all" (the controller then sets
  `exhausted` and stops asking).

`before` is a `pd.Timestamp` of the oldest bar currently loaded - exactly where
the loader should continue backwards. Epoch numbers are read by magnitude
(seconds / ms / µs / ns), so a loader that hands back raw epoch seconds does not
land in 1970.

Bars that are already on the chart win over the incoming copy, and the combined
frame is sorted by time, so an overlapping or unsorted loader is fine.

## Indicators follow the history

**Yes** - every indicator on the chart extends with the older bars, on the main
pane *and* in sub-panes, without anything extra:

```python
sma = chart.add_sma(length=50)                 # main pane
rsi = chart.add_rsi(length=14, pane_index=1)   # its own pane
history = chart.infinite_history(load, page=250, threshold=60)
```

Prepending goes through `chart.set(frame, keep_drawings=True)`, and that
recomputes every registered indicator over the *whole* frame and re-sends it
(`_refresh_indicators(full=True)`). Two consequences worth knowing:

* the indicator lines keep extending to the left exactly like the candles, and
  their pane assignment never changes;
* because the indicator is recomputed with the newly available older bars, the
  values near the old left edge become *more* correct: an SMA that used to start
  with a half-empty window now has its full window (the test
  `test_a_main_pane_indicator_extends_with_the_history` checks that the value at
  the join equals the full-window mean).

Volume is re-sent as well, and the toolbox drawings are kept
(`keep_drawings=True`).

## Driving it

```python
history.loaded          # bars currently on the chart
history.earliest        # pd.Timestamp of the oldest bar (what a loader continues from)
history.latest          # ... and the newest
history.exhausted       # the loader returned nothing (or max_requests was hit)
history.requests        # how many chunks were asked for
history.loading         # a loader call is in flight
history.data            # the loaded frame, as the engine holds it
history.load()          # pull a chunk by hand
history.check(12)       # run the trigger yourself (e.g. from your own scroll logic)
history.stop()          # stop following the visible range
```

## Things worth knowing

* **Events need the running window loop.** `events.range_change` is delivered
  through the webview's Python channel, so it fires while the window's event loop
  runs - `chart.show(block=True)` in a script, or your GUI's main loop in an app
  (a `QTimer` callback can drive it too). Nothing loads while the loop is not
  running.
* **The loader runs on that same thread**, so a slow database query blocks the
  UI. Keep a chunk small enough to answer quickly, or fetch in a worker thread
  and push the frame with `history.prepend(frame)` from the main thread
  (`docs/advanced/deferred.md` #28).
* **Tuning**: `threshold` decides how eagerly it loads (bigger = fewer, larger
  requests), `page` how much each request brings. `max_requests` is handy in
  tests.
* **The viewport stays put** because the engine anchors the visible *time* range,
  not the logical indices - the same behaviour the official demo relies on.
* It works on an overlay series too: `overlay.infinite_history(load)` (e.g. a
  second symbol on the left price scale, see
  [Two symbols on two price scales](two-price-scales.md)).
