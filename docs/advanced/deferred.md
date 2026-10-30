# Deferred features and known gaps

Everything here is **deliberately unfinished**: work that is possible, was
noticed while building something else, and was parked because it is not needed
yet. Nothing on this page is a surprise bug - each entry says what it is, where
the code lives and what implementing it would take, so a later session can pick
it up without re-discovering it.

**中文说明**：本页记录"能做但暂时不做"的功能、已知的粗糙边界和来源注释里
的旧 TODO。以后发现类似情况都往这里加一条；需要完善时按条目里的
"Where / How" 直接找代码即可。

## How to add an entry

1. Put it under the closest area heading (or add a heading).
2. Keep the same four lines: **What** (the user-visible gap), **Why deferred**,
   **Where** (file / function), **How** (the implementation sketch) and
   **Verify** (how to prove it works).
3. If the entry is fixed, delete it from here instead of marking it done; the
   tests and the guides are the record of what works.

---

## Multi-chart layouts and the page top bar

### 1. Touch / pen dragging for layout dividers

- **What**: a `Layout` divider can be dragged with a mouse only. On a touch
  screen the separator is drawn and splits the page, but the finger does
  nothing.
- **Why deferred**: every bundled backend is a desktop webview; no touch target
  is in use yet.
- **Where**: `jslib/src/general/layout.ts::LayoutSplitter._bindDrag` binds
  `mousedown` on the divider and `mousemove` / `mouseup` on `document`.
- **How**: switch to Pointer Events (`pointerdown` / `pointermove` /
  `pointerup` + `setPointerCapture`) or add the `touch*` twins, and give
  `.layout-divider` `touch-action: none`.
- **Verify**: dispatch a `PointerEvent` drag in `tests/e2e/smoke.html`
  (`layoutDivider` check) and try an emulated touch device.

### 2. Grid / nested layouts

- **What**: `Layout` tiles exactly one row *or* one column. A real workspace
  wants 2x2, "two rows on the left + one column on the right", etc.
- **Why deferred**: the top bar layout menu only offers 上下 / 左右, which the
  single-axis model covers.
- **Where**: `pylightcharts/layout.py::Layout.arrange` computes one `share`;
  `jslib/src/general/layout.ts::LayoutSplitter` assumes one axis for all
  dividers.
- **How**: keep a small split tree (`{axis, children[]}`) instead of a flat
  chart list; each internal node owns one divider group, and `LayoutSplitter`
  already handles "a list of charts along one axis", so it can be applied per
  node. `Layout.charts` would walk the leaves in order.
- **Verify**: unit tests for the tree-to-(axis, share) maths, plus a smoke
  check that a 2x2 page has three dividers whose drags are independent.

### 3. Persisting dragged shares

- **What**: after dragging a divider, the next `arrange()` splits evenly again;
  there is no way to save / restore a user's split, and no
  `arrange(shares=[0.6, 0.4])`.
- **Why deferred**: the example re-splits on every menu click, which is fine
  for a demo.
- **Where**: `Layout._on_drag` already adopts the shares the JS side reports
  (`chart._width` / `chart._height`), but `arrange` ignores them.
- **How**: keep the reported shares in `self._shares`, let `arrange` reuse them
  when `count` is unchanged, and add an explicit `shares=` argument.
- **Verify**: assert the emitted `resize` values in `tests/test_layout.py`.

### 4. Divider ergonomics: reset on double-click, keyboard access

- **What**: no double-click "make these two equal" (most IDEs' splitters have
  it) and no keyboard / screen-reader access.
- **Why deferred**: cosmetic niceties.
- **Where**: `LayoutSplitter._bindDrag` (no `dblclick` listener),
  `LayoutSplitter._makeDivider` (no `tabindex` / ARIA).
- **How**: `dblclick` -> `LayoutSplitter._fit` for that group; `tabindex="0"`,
  `role="separator"`, `aria-orientation` and arrow keys moving the divider by a
  fixed step.
- **Verify**: smoke check for the double-click reset; a keyboard drag assertion.

### 5. Destroying a chart

- **What**: hiding a chart parks it at 0x0 (`Layout._hide`), but the `Handler`,
  its Lightweight Charts instance, canvas, legend and listeners stay in the DOM
  and in `Handler._instances` forever. There is no `chart.close()` /
  `layout.remove(chart)`.
- **Why deferred**: the demo only ever grows the layout; nothing leaks visibly.
- **Where**: JS has no destroy path at all (`grep dispose|remove
  jslib/src/general/handler.ts`), python `AbstractChart` has none either.
- **How**: `Handler.destroy()` -> remove the sync link
  (`Handler.unsyncCharts`), drop the instance from `_instances`, `this.chart.remove()`
  (a Lightweight Charts API), remove `wrapper` from the container; python
  `AbstractChart.close()` and `Layout.remove(chart)` / `Layout.unregister`.
- **Verify**: `document.querySelectorAll('.handler').length` and
  `Handler._instances.length` after closing a chart.

### 6. Opting a chart out of the layout

- **What**: every `AbstractChart` registers itself with `chart.win.layout`
  (`AbstractChart.__init__`), so a chart created for an unrelated purpose -
  e.g. `create_subchart(position='right', width=0.4, height=0.4)` - joins the
  layout and is re-tiled (or hidden) by the next `arrange()`.
- **Why deferred**: auto-registration is convenient for the common case.
- **Where**: `pylightcharts/abstract.py::AbstractChart.__init__` (`self.win.layout.register(self)`).
- **How**: a `register=False` flag on `create_subchart` / `AbstractChart`, or a
  `Layout.auto` switch, or document `layout.unregister(chart)` more loudly (it
  exists today, it is just easy to miss).
- **Verify**: create a standalone subchart, arrange the layout, assert its size
  did not change.

### 7. More than one page-level bar

- **What**: `Window.page_topbar()` is a single bar at the top. A status bar at
  the bottom, side tool rails, or one bar per chart group all need more.
- **Why deferred**: no such UI is in use.
- **Where**: `Window.page_topbar` caches one `TopBar`;
  `Handler.reSize()` subtracts the *sum* of the page bars
  (`TopBar.pageHeight()`) and the chart wrappers are floats that flow below
  them - which only works because they are all at the top.
- **How**: a page bar needs a slot ("top" / "bottom" / "left" / "right"); the
  chart area should become a flex column (bar, charts, bar) and the charts
  should be sized against that area instead of `window.innerHeight - pageBars`.
- **Verify**: geometry assertions in a real window (bar + charts fill the page
  exactly, with no scrollbar).

### 8. Page-bar height changes outside the widget API

- **What**: if the bar's height changes without going through `appendWidget`
  (host CSS, a widget's text wrapping to two lines, a font loading late), the
  charts keep the old reserved space until the window is resized.
- **Why deferred**: the python widgets always go through `appendWidget`, which
  calls `TopBar.reLayout()`.
- **Where**: `jslib/src/general/topbar.ts::TopBar.reLayout` ->
  `Handler.reLayoutAll()`.
- **How**: a `ResizeObserver` on the bar element calling `Handler.reLayoutAll()`.
- **Verify**: change the font size from the console and check the charts
  re-fit.

### 9. Sync picks the "active" chart with `mouseover` (mouse only)

- **What**: `Lib.Handler.syncCharts` decides which chart drives the crosshair /
  visible range from a `mouseover` listener on the chart wrapper. Touch devices
  never fire it, so the link stays parent -> child in one direction.
- **Why deferred**: same as entry 1 - desktop only for now.
- **Where**: `jslib/src/general/handler.ts::Handler.syncCharts`
  (`addMouseOverListener`).
- **How**: also listen to `pointerdown` / `touchstart`; keep the same
  add/remove listener logic.
- **Verify**: fire a `pointerdown` on the second chart and assert it becomes the
  driver.

### 10. Crosshair alignment across different timeframes

- **What**: with `sync='crosshair'` between charts on different periods, the
  crosshair is placed at the same *time*; when the coarser chart has no bar at
  that time the crosshair is not shown there (it is not snapped to the nearest
  bar).
- **Why deferred**: not obviously desirable - snapping can be misleading.
- **Where**: `jslib/src/general/handler.ts::syncCharts` -> `crosshairHandler`
  (passes `point.time` straight to `setCrosshairPosition`).
- **How**: look up the nearest bar of the target series (`series.dataByIndex` /
  `timeScale.coordinateToLogical`) and place the crosshair there.
- **Verify**: two charts with different intervals, move the crosshair, assert
  the far chart shows one at all times.

---

## Bridge and code health

### 11. `hide_data()` still emits a hand-written JS snippet

- **What**: `tests/test_phase2.py::test_precision_and_hide_data` fails (the
  only failing test in the suite). `chart.hide_data()` routes the series
  through the bridge but appends a raw guard for the volume series, and the
  test asserts the bridged JSON form.
- **Why deferred**: the behaviour is correct, only the assertion and the style
  disagree.
- **Where**: `pylightcharts/abstract.py::AbstractChart._toggle_data`.
- **How**: add `Lib.invokeOptional` (entry 12) and use it for the volume
  series, or update the test to expect the raw snippet.
- **Verify**: `python -m pytest tests/test_phase2.py -q` goes green.

### 12. `Lib.invokeOptional` (guarded lookups)

- **What**: the bridge's `invoke` throws when the handle or the method does not
  exist, so every optional sub-object (`volumeSeries`, a pane's
  `priceScale`, ...) needs a hand-written `if (window.x.y)` snippet.
- **Why deferred**: few places need it, and they are guarded already.
- **Where**: `jslib/src/general/rpc.ts::invoke` (and
  `resolveRefs` / `lookup`).
- **How**: `invokeOptional(handle, method, args)` returning `undefined` instead
  of throwing, exposed as `Window.invoke_optional` in python.
- **Verify**: unit test for a missing handle (returns `None`, no exception)
  plus entry 11 using it.

### 13. Stale TODO comments in the source

- **What**: comments that no longer describe reality. The known one:
  `pylightcharts/topbar.py::MenuWidget.set` says
  `# TODO this will probably need to be fixed`, but the path is verified
  working (the JS `_clickHandler` fires the python callback).
- **Why deferred**: cosmetic.
- **Where**: `grep -rn "TODO" pylightcharts jslib/src`.
- **How**: verify the claim, then delete or replace the comment. Do not leave a
  TODO that means "unverified" - move it to this page instead.
- **Verify**: `pytest tests/test_layout.py -q` (menu label + click tests) and a
  quick grep.

### 14. `Window.handlers` is a class attribute shared by every window

- **What**: `Window.handlers` is defined on the class, so every `Chart` /
  `StaticLWC` / `QtChart` instance shares one callback registry. The ids are
  random (`Window._id_gen`) so a collision has not happened, but a callback
  could in principle be dispatched to another window's object.
- **Why deferred**: purely latent, and fixing it touches every widget's
  registration path.
- **Where**: `pylightcharts/abstract.py::Window` (`handlers = {}`), written by
  `pylightcharts/topbar.py::Widget.__init__`,
  `pylightcharts/layout.py::Layout.__init__` and friends.
- **How**: make it an instance attribute created in `Window.__init__`
  (`self.handlers = {}`) and make sure the multi-window reuse path in
  `pylightcharts/chart.py` (`Chart._main_window_handlers`) still shares it
  between charts of the *same* window.
- **Verify**: two windows, same widget name, assert each callback lands on its
  own chart.

### 15. ~~`pylightcharts.widgets` binds a Qt binding at import time~~ (done)

*Importing `pylightcharts.widgets` no longer imports a GUI toolkit: the Qt
binding is loaded on the first `QtChart` (and `wx` inside `WxChart`), while
`widgets.QWebEngineView` & co. still resolve lazily through a module
`__getattr__`. An explicitly set module global still wins, so the downstream
monkey-patching contract (`miniqt`, `compat.py`) is unchanged - a subprocess test
and the old failing test order both guard it.*

<details><summary>original entry</summary>

### `pylightcharts.widgets` binds a Qt binding at import time

- **What**: importing `pylightcharts.widgets` (for `BrowserChart`, `StaticLWC`,
  `JupyterChart`, ...) probes and imports a Qt binding eagerly. In a process that
  later imports a *different* binding (the `miniqt` app is PyQt6-based), the
  second import fails with confusing DLL/`qfluentwidgets` errors - the same
  hazard `pylightcharts/qt.py` documents.
- **Why deferred**: `import pylightcharts` itself stays cheap (PEP 562 lazy
  attributes); only the explicit `widgets` submodule binds Qt, and the Qt block
  is what implements "the first binding loaded wins".
- **Where**: `pylightcharts/widgets.py` (the binding-selection block) - the
  `tests/test_miniqt_*.py` files must therefore be imported *before* anything
  that pulls in `widgets` (that is why `tests/test_live_browser.py` imports
  `BrowserChart` inside its helper instead of at module level).
- **How**: move the Qt probe into the `QtChart`/`_QtBackend` class body and
  import `pylightcharts.widgets` lazily everywhere, or expose the export helpers
  (`PageExport`) from a Qt-free module so `BrowserChart` does not need `widgets`.
- **Verify**: `python -c "import pylightcharts.widgets; import qfluentwidgets"`
  in one process.

</details>

### 16. Other engines / backends not verified for the newest features

- **What**: `page_topbar`, `layout` and the dividers were verified in pywebview
  and in the headless browser render. `QtChart`, `WxChart`, `JupyterChart` and
  `StreamlitChart` share the same bundle, so they should work, but nothing
  exercises them.
- **Why deferred**: no CI entry point runs those backends.
- **Where**: `pylightcharts/widgets.py` (the static/Jupyter/Streamlit
  backends), `pylightcharts/qt.py`.
- **How**: a Qt smoke run of example 14 (or a small script) that asserts the
  page bar spans the widget and a divider is draggable.
- **Verify**: manual run against each backend; record the result in the commit
  message.

---

## Engine limits (cannot be fixed from the wrapper)

### 17. Pane separators are 1px

- **What**: the divider *between panes* of one chart is 1px wide, always.
- **Why**: engine constant - `SeparatorConstants.SeparatorHeight = 1` in the
  vendored Lightweight Charts source. Only `separatorColor`,
  `separatorHoverColor` and `enableResize` are options
  (`chart.pane_separator(...)`).
- **Where**: `lightweight-charts/src/...` (vendored), exposed by
  `pylightcharts/abstract.py::AbstractChart.pane_separator`.
- **How**: patch the constant in the vendored engine (and keep the patch
  documented) or accept 1px. The *layout* dividers between charts are ours and
  already have a `divider_size`.
- **Verify**: pixel measurement of a rendered pane separator, like the one used
  for the table borders.

### 18. Up/down markers cannot be resized

- **What**: `UpDownMarkersPlugin` draws a 4px dot plus a 4.7px arrow, always.
  Classic markers have `size=`, the up/down plugin has no equivalent, so its
  markers stay tiny on a dense chart.
- **Why deferred**: the numbers are engine constants and the workaround (use a
  classic marker for the visible one) is good enough.
- **Where**: `lightweight-charts/src/plugins/up-down-markers-plugin/renderer.ts`
  (`Constants.Radius = 4`, `ArrowSize = 4.7`, `ArrowOffset = 7`).
- **How**: patch the constants in the vendored engine (and document the patch),
  or add a `size` passthrough in `pylightcharts/plugins.py` plus a patched
  renderer.
- **Verify**: pixel measurement of a marker at two sizes, like the one used for
  the classic `size=3` (37px -> 349px in `_diag_size_curve`).

### 19. `zOrder` for the span / fill primitives

- **What**: `horizontal_span`, `vertical_span` and `fill_between` use the
  default pane-view z-order, so overlapping bands stack by attach order and
  cannot be ordered explicitly (a small span under a big one is hidden).
- **Why deferred**: no overlap is in use.
- **Where**: `jslib/src/horizontal-span/*`, `jslib/src/line-fill/*`,
  `jslib/src/vertical-span/*` (the pane views), python
  `pylightcharts/drawings.py`.
- **How**: expose `zOrder` as a primitive option (the engine supports it per
  pane view) and pass it from the python constructors.
- **Verify**: two overlapping spans with opposite z-orders and a pixel check of
  which colour wins.

---

## Keyboard navigation

### 20. Zoom anchored on the crosshair / the mouse

- **What**: the built-in arrow-key zoom is anchored on the **middle** of the
  visible window (both edges move symmetrically, like the mouse wheel). Zooming
  around the crosshair, or around the pointer, is not implemented.
- **Why deferred**: the centred anchor is what the current host expects and it
  keeps the keyboard behaviour predictable (`chart.keyboard_step` covers coarse
  vs fine grids).
- **Where**: `jslib/src/general/handler.ts::_handleArrowKey` (the `else` branch
  builds `{from: centre - bars / 2, to: centre + bars / 2}`).
- **How**: read the anchor from the chart instead of the range centre -
  `timeScale.coordinateToLogical(x)` for the pointer position, or the stored
  crosshair point (`chart.set_crosshair_position` keeps none; the handler would
  have to remember the last `crosshairMove` param). Then spread `bars` around
  that anchor, clamped to the data range.
- **Verify**: pixel-level - place the crosshair off-centre, press `ArrowUp`
  twice and assert the crosshair's coordinate stays put while the visible range
  shrinks (`tests/e2e/smoke.html` already spies on the range calls, so the
  assertion can be added there).

### 21. More keyboard conveniences

- **What**: no `+` / `-` zoom aliases, no explicit wheel/keyboard consistency
  check, and no "step by a fixed number of bars" mode (the step is a fraction of
  the visible window, `Chart(keyboard_step=...)`).
- **Why deferred**: the arrow keys cover the day-to-day use.
- **Where**: `jslib/src/general/handler.ts::_handleArrowKey` (key list and the
  `jump()` / factor maths).
- **How**: add the keys to the dispatch table; for a bar-count mode, translate
  the count into a logical-range delta (the fraction path already does
  `Math.round(visible * fraction)`).
- **Verify**: extend the `arrowKeys` check in `tests/e2e/smoke.html`.

## Charts, data and rendering

### 22. ZigZag-style swing detection

- **What**: `indicators.swing_points` / `mark_swings()` find `length`-bar
  fractals (deterministic, non-repainting, but a pivot is only confirmed
  `length` bars later). A ZigZag that alternates highs and lows after a minimum
  percentage move is not implemented.
- **Why deferred**: fractals cover "show the price at the swing highs/lows";
  ZigZag repaints its last leg, which needs a policy decision.
- **Where**: `pylightcharts/indicators.py::swing_points` (fractal maths) and
  `pylightcharts/abstract.py::SeriesCommon.mark_swings` (marker pushing).
- **How**: a second detector (`zigzag(high, low, threshold=0.03)`) returning the
  same `time` / `price` / `kind` frame would plug straight into `mark_swings`;
  the leg could also be drawn as a line (`shapes.polyline` in a custom series).
- **Verify**: unit tests for the alternation/threshold behaviour, plus a
  rendered pixel check like the marker ones in `tests/test_swings.py`.

### 23. ~~A live browser <-> Python bridge~~ (done: stdlib SSE)

*Implemented as `BrowserChart(live=True)` + `pylightcharts.server.LiveServer`
(stdlib HTTP + Server-Sent Events, zero dependencies). Auth (`token=...`) and a
long-polling fallback (`/poll`, for environments that cut SSE) are in as well.
Remaining gaps kept for reference: no synchronous readbacks in a tab, and no
*WebSocket* transport - it would need an extra dependency and (with
`http.server`) a second port, while long-polling covers the same "SSE is
blocked" case with no dependency.*

<details><summary>original entry</summary>

### A live browser <-> Python bridge (original entry)

- **What**: a page served to a normal browser that keeps talking to a running
  Python process (reactive `set`/`update`, widget callbacks, `chart.events`)
  instead of the bundled desktop webviews.
- **Why deferred**: it is a server, not a chart feature - and the static export
  (`to_html` / `save_html` / `open_in_browser`, plus the `BrowserChart` backend
  whose `show()` writes and opens the page) already covers "look at it in a
  browser" with **zero** extra dependencies.
- **Where**: `pylightcharts/abstract.py::Window` (already transport-agnostic:
  `script_func` + `handlers`), `pylightcharts/widgets.py` (the
  `StaticLWC`/`Streamlit` targets).
- **How**: a tiny HTTP/WebSocket server (`websockets` or FastAPI + uvicorn,
  ~1 dependency each) that serves `to_html()` and forwards
  `window.callbackFunction` messages both ways; `Window` already serialises
  callbacks as `name_~_args` strings. Jupyter (`JupyterChart`) and Streamlit
  (`StreamlitChart`, display-only) remain the low-effort alternatives.
- **Verify**: run the server, open the page, drive a `set()`/`update()` from
  Python and a widget callback back into Python.

</details>

## Test suite

### 24. Known failing test

- **What**: `tests/test_phase2.py::test_precision_and_hide_data` - see entry 11.
- **Why deferred**: pre-existing, unrelated to the current work, and the test
  (not the behaviour) is arguably the stale part.
- **Where**: `tests/test_phase2.py:200`.
- **How**: entry 11.
- **Verify**: `python -m pytest tests -q` reports no failures.

## Crosshair tooltips

### 25. The floating tooltip (box parked on the data point)

- **What**: the tutorial's third tooltip - the box is positioned at the data
  point (`series.priceToCoordinate(price)`) instead of next to the cursor, so it
  jumps vertically whenever the crosshair moves between a high and a low. The
  tracking and magnifier ones are implemented (`docs/guide/tooltips.md`).
- **Why deferred**: it is the tracking tooltip with a different y anchor, and it
  was explicitly found to be the jumpy / redundant one of the three.
- **Where**: `jslib/src/general/tooltip.ts::Tooltip._place` (the tracking branch
  uses `point.y`).
- **How**: add `mode: 'floating'` and, in `_place`, use
  `this._series.priceToCoordinate(this._mainValue(this._last.data))` for the y
  and `point.x` for the x, keeping the same flip logic.
- **Verify**: extend the `tooltipTracking` check in `tests/e2e/smoke.html` with a
  floating tooltip whose y follows the price, and assert it stays put when the
  hovered bar's close is unchanged.

### 26. A long title is clipped instead of wrapped

- **What**: the tooltip sets `white-space: nowrap` (from the tutorial) and
  `overflow: hidden`, so a title longer than `width=` is cut off mid-word
  instead of wrapping or getting an ellipsis.
- **Why deferred**: the tutorial looks the same, every example uses short
  titles, and `fields` (the OHLC line) already wraps because it is a flex
  container.
- **Where**: `jslib/src/general/tooltip.ts` (`this.div.style.whiteSpace` /
  `overflow`; the width comes from `TooltipOptions.width`).
- **How**: either drop `nowrap` on `_title` (let it wrap like the fields) or add
  `text-overflow: ellipsis` plus a `title` attribute with the full text; a
  `maxWidth` option would pair with it.
- **Verify**: create a tooltip with a 60-character title at `width=96` in
  `tests/e2e/smoke.html` and assert `div.scrollWidth <= div.clientWidth`.

### 27. A third visible price scale

- **What**: only the left and the right price scale can be drawn, so a chart can
  show at most two axes of its own (`chart.add_symbol(..., scale='left'/'right')`).
  Any other id becomes an *overlay* scale - auto-scaled, but not drawn, which is
  how the volume series works (`price-scale.ts`: "Indicates if this price scale
  visible. Ignored by overlay price scales.").
- **Why deferred**: an engine limit, not a wrapper one; two scales plus panes
  cover the usual multi-symbol layouts, and a third axis would have nowhere to go
  without a new layout pass.
- **Where**: `lightweight-charts/src/model/price-scale.ts` (`_isOverlay`),
  `pylightcharts/overlay.py::add_symbol`.
- **How**: a third symbol can share one of the two scales, or get its own pane
  (`chart.add_series(..., pane_index=1)` / `chart.add_pane()`), which draws its
  own left+right pair. A real third axis would need an upstream change.
- **Verify**: `_diag_two_scales.py`-style render: the left and right strips both
  carry tick labels while a third symbol on `scale='left'` shares the left axis.

### 28. The infinite-history loader runs on the callback thread

- **What**: `InfiniteHistory` calls the loader from the `range_change` handler,
  which is dispatched on the window's UI thread (the QWebChannel slot / the
  webview callback). A slow loader - a database round trip, a network fetch -
  therefore blocks the window until it returns, and the chunk is only pushed
  afterwards.
- **Why deferred**: it is correct and simple for the common case (a local file /
  an in-memory slice, see `examples/11_api_tour/18_infinite_history.py`), and
  making it asynchronous needs a thread-safe way back into the bridge
  (`win.run_script` from another thread is not guaranteed to be safe today).
- **Where**: `pylightcharts/history.py::InfiniteHistory.load` (called from
  `_on_range`); `pylightcharts/widgets.py::emit_callback`.
- **How**: fetch in a `threading.Thread` / an executor, then hand the frame back
  with `history.prepend(frame)` from the main thread (it only touches the bridge
  there). A queued variant would need `Window` to serialise script execution with
  a lock and the host loops to drain the queue.
- **Verify**: add a test that starts a load with a slow loader, keeps interacting
  with the chart, and asserts the chunk arrives once the worker finishes.

