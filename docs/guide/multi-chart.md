# Multiple charts and the page top bar

Two pylightcharts extensions make a multi-chart workspace possible. Neither
exists in Lightweight Charts™ or in upstream `lightweight-charts-python`:
the engine has no notion of several charts sharing a page, and its `topbar`
belongs to a single chart.

- **`chart.win.page_topbar()`** – one bar that spans the whole window and stays
  above every chart. It is the place for global controls (timeframe, indicators,
  layout, settings).
- **`chart.win.layout`** – a `pylightcharts.layout.Layout` that tiles the window
  between charts: one row (左右) or one column (上下).

The full example is
[`examples/11_api_tour/14_multi_chart_layout.py`](https://github.com/MiniBtMaster/pylightcharts/blob/main/examples/11_api_tour/14_multi_chart_layout.py).

## Chart bar vs. page bar

| | `chart.topbar` | `chart.win.page_topbar()` |
|---|---|---|
| lives in | the chart's own container | the window container |
| width | the chart's width | the window's width |
| height taken from | that chart's canvas | every chart's canvas |
| callback argument | the chart | the window (`chart.win`) |
| survives a split | no (it stays inside its chart) | yes |

```python
chart = Chart(width=1200, height=760)
chart.set(df)

bar = chart.win.page_topbar()                 # spans the window
bar.switcher('timeframe', ('15m', '1H', '4H'), default='15m', func=on_timeframe)
bar.button('indicators', '指标', func=on_indicators)
bar.menu('layout', ('上下布局', '左右布局'), default='布局',
         align='right', func=on_layout)
bar.button('settings', '设置', align='right', separator=True, func=on_settings)
```

`bar` is created lazily on first use and memoised on the window, so every call
returns the same bar. The widgets are the usual ones (`textbox`, `switcher`,
`menu`, `button`), and `TopBar.menu` is the button menu upstream does not have:
it opens a dropdown, updates its label with the selected item and fires a single
callback.

`default='布局'` keeps the label at *布局 ↓* until an item is picked, which is
what a "layout" menu wants (the items are actions, not states).

Because a page bar is shared, its callbacks receive the **window**:

```python
def on_layout(win):                 # win is chart.win
    choice = win.page_topbar()['layout'].value
    if choice == '上下布局':
        win.layout.vertical()
    elif choice == '左右布局':
        win.layout.horizontal()
```

## Laying charts out

`chart.win.layout` holds every chart of the window in creation order; the first
one is the anchor new charts are attached to.

```python
chart.win.layout.vertical()            # 上下布局：add one below, both 50% tall
chart.win.layout.horizontal()          # 左右布局：add one to the right, both 50% wide
chart.win.layout.arrange('horizontal', 3)   # three in a row (1/3 each)
chart.win.layout.single()              # back to one full-size chart
```

| method / property | meaning |
|---|---|
| `arrange(kind='horizontal'\|'vertical', count=2, sync=False, on_create=None, **subchart_kwargs)` | tile `count` charts, creating/hiding as needed, and return them; `sync` = independent (default) / `True` / `'crosshair'` |
| `sync_mode` | the link in place: `None`, `'full'` or `'crosshair'` |
| `divider` / `divider_size` / `divider_color` / `divider_hover_color` | the draggable separators between the charts (on by default) |
| `set_divider(enabled=None, size=None, color=None, hover_color=None)` | restyle / show / hide the separators and redraw them |
| `horizontal(count=2, **kw)` / `vertical(count=2, **kw)` | the two common cases (right / below) |
| `single(kind=None)` | collapse to the anchor chart; the rest are hidden |
| `charts` / `hidden_charts` | the visible charts in layout order / the parked ones |
| `anchor` | the chart new ones are attached to |
| `kind` | `'horizontal'`, `'vertical'` or `None` before the first `arrange` |
| `on_create` | called with every chart the layout creates |
| `register(chart)` / `unregister(chart)` | control the layout's membership by hand |

**The charts are independent by default.** A layout is normally a
multi-timeframe or multi-symbol workspace, so each chart keeps its own time
scale, price scale and crosshair:

```python
win.layout.horizontal()                   # two periods, nothing linked
win.layout.horizontal(sync=True)          # pan / zoom / crosshair together
win.layout.horizontal(sync='crosshair')   # only the crosshair together
win.layout.horizontal()                   # independent again
```

`sync` accepts `True` / `'full'` / `'both'`, `'crosshair'` / `'crosshairs_only'`,
and `False` / `None` / `'none'`. It is applied to the charts that already exist
as well as to the ones the call creates, so a layout can be linked and unlinked
at any time - the engine link is replaced, never stacked (see `chart.sync` /
`chart.unsync` for the single-chart version).

Charts are sized as fractions of the space left by the page bar. Hiding a chart
parks it at 0×0 instead of destroying it, so `arrange(..., 3)` after
`arrange(..., 2)` brings the same chart (with its data) back.

## Draggable dividers

Like the separators between panes, but between the charts: the layout floats a
`divider_size` wide separator between every pair of neighbours, and dragging it
hands those pixels from one chart to the other.

```python
win.layout.horizontal()                      # divider on by default
win.layout.horizontal(divider=False)         # no separators
win.layout.set_divider(size=8, color='#2a2e39', hover_color='#2962FF')
win.layout.set_divider(enabled=False)        # remove them again
```

- The charts are sized so that `charts + dividers` fill the page exactly; the
  separators keep their pixel size when the window is resized.
- The drag is clamped at 40px per side, the cursor changes (`col-resize` /
  `row-resize`) and the hover colour highlights the grab area.
- After a drag the layout adopts the new shares, so
  `chart._width` / `chart._height` (and `report`-style introspection) stay
  truthful; the next `arrange()` re-splits the page evenly.
- With a page-level top bar the dividers (and the charts) use the space *below*
  the bar.

`on_create` is the hook that gives the new charts their own data:

```python
def prepare(sub):
    sub.set(df)
    sub.legend(visible=True, ohlc=False, percent=True, text='SUB')

chart.win.layout.on_create = prepare
```

## Notes

- **It is all floats and fractions.** Every chart is a floated container whose
  width/height is a fraction of the window, so `count` charts of `1/count` tile
  the page exactly. Mixing your own `create_subchart(position=..., width=...)`
  with a layout is allowed, but `arrange()` will re-size and (when shrinking)
  hide whatever is registered - pass `count` accordingly.
- **Charts after `create_subchart` register themselves**, because the layout is
  the window's. `layout.unregister(sub)` if a chart should be left alone.
- **`sync` is off on purpose**: a multi-period / multi-symbol workspace must not
  move every chart when one is panned. Pass `sync=True` - or `sync='crosshair'`
  when only the crosshair should line up, which never touches the time scales -
  or call `chart.sync(other)` yourself when the charts really are the same
  instrument. `chart.unsync(other)` removes that link again.
- **`chart.layout(...)` is still the Lightweight Charts layout options call**
  (background/text colour). The tiling lives on the window - `chart.win.layout` -
  which is also where the page-level root styles live (`chart.win.style(...)`).
- **Static renderers**: page bars and layouts emit the same scripts in
  `HeadlessChart` / `JupyterChart` / `StreamlitChart`; the page bar is a normal
  DOM element, so it is included in `HeadlessChart.render()` screenshots
  (`chart.screenshot()` only captures the chart canvas).
- **Not done yet**: dragging is mouse-only (no touch / pen), the layout is a
  single row or column (no grids), and a hidden chart cannot be destroyed.
  These and the rest of the parked work are listed in
  [Deferred features and known gaps](../advanced/deferred.md).
