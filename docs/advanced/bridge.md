# Bridge architecture

`pylightcharts` does not re-implement the charting engine. It embeds
`lightweight-charts` in a WebView and drives it from Python.

```
┌─ Python ────────────────────────────┐        ┌─ Browser ──────────────────────────┐
│ Chart / series / drawings / events  │        │ Lib.Handler (TypeScript)           │
│                                     │        │   registry of live objects         │
│ Window.invoke(handle, method, args) │ ─────► │ Lib.invoke(handle, method, args)   │
│ Window.invoke_get(...)              │ ◄───── │ lightweight-charts v5              │
└─────────────────────────────────────┘        └────────────────────────────────────┘
```

## Handles

Every live object is addressed by a string handle:

- `window.abcdefgh` — the chart handler (see `IDGen`), a window path
- a registered name — `Lib.register('myPrimitive', obj)`
- `handle.subPath` — a property path, resolved against the registry first

```python
chart.win.invoke(f'{chart.id}.timeScale', 'applyOptions', {'rightOffset': 5})
chart.win.invoke(f'{series.id}.series', 'applyOptions', {'lineWidth': 3})
```

## Passing objects

JSON cannot carry live objects, so `{$ref: handle}` is resolved on the JS side:

```python
series.attach_primitive('myPrimitive')     # -> attachPrimitive({"$ref": "myPrimitive"})
```

This is what makes `attachPrimitive`, `removePriceLine`, `moveToPane` and
friends callable from Python.

## Rules for contributors

- **Fire-and-forget calls go through `Window.invoke`.** The transport appends
  `;undefined`, because pywebview serialises the result of `evaluate_js` and a
  live chart/pane/series object explodes into hundreds of MB of circular data.
- **Methods returning an object must use `store_as=...`**; only JSON-serialisable
  primitives may go through `invoke_get`.
- **Round-trips are serialised and correlated by request id**, so a stale reply
  can never reach the wrong caller. JS errors raise
  `pylightcharts.util.BridgeError`.
- **Chart and series share method names** (`apply_options`); keep them apart
  (`series_options`, `data_points`) to avoid MRO shadowing.
- **Event handlers must be attached to `window`**, not declared with `let`:
  `let` bindings do not persist between `evaluate_js` calls, which breaks
  `unsubscribe()`.

## Extending the JS side

Add a module under `jslib/src/`, export it from `jslib/src/index.ts`, then
`cd jslib && npm run build`. The build copies `bundle.js`, `styles.css` and the
vendored engine into `pylightcharts/js/`; commit those artifacts so
`pip install` works without Node.

## Upgrading lightweight-charts

```bash
cd jslib
npm install lightweight-charts@<new>
npm run build
cd .. && python -m pytest && python tests/e2e/smoke.py
```

Check the upstream migration guide for breaking changes — v5 moved series
creation to `addSeries(LineSeries, ...)`, markers to `createSeriesMarkers`, and
watermarks to `createTextWatermark`.
