# Panes

`pylightcharts` uses the native lightweight-charts v5 multi-pane support.

```python
chart.add_pane()                                   # -> index
chart.create_area('close', pane_index=1)
chart.add_series('Line', 'ma20', pane_index=1)
chart.add_sma('close', 20, pane_index='new')       # convenience: creates a pane
```

`pane_index='new'` always creates a fresh pane; passing an integer beyond the
current count creates the panes in between.

## Removing an indicator (series, legend row and pane)

An indicator sub-chart is one series in one pane, so removing it is one call:

```python
pane = chart.add_pane()                                  # -> index 1
rsi = chart.pane_add_series(pane, 'Line', name='RSI 14', color='#7E57C2')
rsi.set(pd.DataFrame({'time': frame['time'], 'RSI 14': compute(frame)}))

rsi.delete()          # the line, its legend row (label + eye icon) and the pane
```

* `series.delete()` sends `removeSeries` with the series' **handle** - that is
  what makes the JS side drop its legend row as well (a plain id there is
  ignored). It works for indicator lines, histograms and any series added
  through `add_series` / `pane_add_series`.
* An emptied pane is removed by the engine, so `pane_count()` drops and every
  later pane moves up one slot; `series.pane_index` follows, so a
  "remove the old indicator, add the new one" cycle keeps its indices right.
  (A pane created with `add_pane(preserve_empty=True)` survives instead - call
  `chart.remove_pane(index)` when you are done with it.)
* `chart.remove_pane(index)` removes a pane explicitly (its series go with it).

`examples/11_api_tour/19_indicator_panes.py` is a runnable version of this: a
topbar switcher swaps the indicator sub-chart (RSI / MACD / CCI / none), one
button compares the preserved-empty-pane behaviour and another one
("删除最后一个副图") drops the last sub pane:

```python
def remove_last_pane(chart) -> bool:
    index = chart.pane_count() - 1
    if index <= 0:
        return False
    for series in [item for item in chart._lines if item.pane_index == index]:
        series.delete()                     # the emptied pane goes with the last
    if chart.pane_count() > index:          # a preserve_empty pane stayed
        chart.remove_pane(index)
    return True
``` The engine side of it is
covered by the `paneLifecycle` check in `tests/e2e/smoke.py`.

## Layout

```python
chart.pane_count()
chart.set_pane_stretch(1, 1.5)                     # relative height
chart.pane_height(1); chart.set_pane_height(250, 1)
chart.pane_size(1)                                 # {'height': .., 'width': ..}
chart.pane_stretch_factor(1)
chart.swap_panes(0, 1)
chart.remove_pane(1)
chart.set_pane_preserve_empty(True, 1)
```

### Separator style

The 1px line between panes comes from Lightweight Charts and defaults to
`'#E0E3EB'` (near-white). `pane_separator()` restyles it:

```python
chart.pane_separator(color='#2A2E39',            # the line
                     hover_color='#363A45',      # shown while dragging it
                     enable_resize=True)         # False drops the drag handle

chart.pane_separator(color='transparent')        # hide the line completely
chart.apply_options(layout={'panes': {'separator_color': '#2A2E39'}})  # same thing
```

Only the colours and the resize behaviour can be changed - the thickness is a
1px constant inside the engine, so make it invisible if a thicker gap is wanted.

## Per-pane price scales

```python
scale = chart.pane_price_scale(1, 'right')
scale.set_mode('logarithmic')
scale.set_auto_scale(False)
scale.get_visible_range()
```

## Moving series between panes

```python
series.move_to_pane(2)
series.get_pane_index()
```

## Chart-level price scales

```python
right = chart.get_price_scale('right')
right.set_mode('percentage'); right.invert(); right.set_visible_range(90, 110)
```

Modes: `normal`, `logarithmic`, `percentage`, `index100`.

## Series ordering

```python
series.series_order()          # drawing order within the pane
series.set_series_order(3)
```
