# Crosshair tooltips

Lightweight Charts has **no** tooltip of its own — the official
[tooltips tutorial](https://tradingview.github.io/lightweight-charts/tutorials/how_to/tooltips)
builds one from an `html` element plus `chart.subscribeCrosshairMove`. The
package ships two of those three as one call, drawn *inside* the chart:

| mode | what it does |
| --- | --- |
| `'tracking'` | an opaque box next to the cursor (the tutorial's tracking tooltip); it flips to the other side near the right / bottom edge |
| `'magnifier'` | a translucent band pinned to the top of the pane that only slides along the time axis (the tutorial's magnifying glass) |

The third variant, the *floating* tooltip, parks the box at the **data point**
instead of the cursor, so it jumps every time the crosshair moves between highs
and lows - the tracking box only follows the pointer. It is deliberately not
included; if you want it, `chart.events.crosshair_move(...)` hands you the same
`param` in Python and `series.price_to_coordinate(price)` gives you the y.

They are created from the series they read their data from:

```python
tip = series.tracking_tooltip(title='ABC Inc.')
tip = chart.magnifier_tooltip()          # chart = its main candle series
```

Everything is optional; the defaults are the tutorial's minimal look (a big
price and the time):

```python
candles = chart.tracking_tooltip(
    title='BTCUSDT',
    fields=('open', 'high', 'low', 'close'),
    width=120,
    time_format='MMM DD HH:mm',
)
```

```python
line.tracking_tooltip(
    title='SMA 20',          # '' or show_title=False hides the first line
    fields='auto',           # every numeric field of the hovered point
    field_labels=('O', 'H', 'L', 'C'),
    color_by_candle=True,    # tint values with the series' up/down colours
    decimals=2,              # default: the series' own price format
    width=96, margin=15, padding=8,
    # height: the tracking box hugs its content by default (pass a number for a
    # fixed box); the magnifier band is as tall as the pane unless told otherwise
    height=None,
    font_size=12, big_font_size=24,
    # background / value text default to the root CSS variables, i.e. the
    # current theme; the title and the frame default to the series' colour
    # (the tutorial's look) - all of them can be overridden
    background='var(--bg-color)', background_opacity=1,
    text_color='var(--color)', border_color='#2962FF',
    border_width=1, border_radius=2, shadow=False,  # frame: the series colour
    show_title=True, show_value=True, show_time=True,
    flip=True,               # tracking: flip near the pane edges
    z_index=1000,
)
```

## Why no data round-trip

The tooltip lives in the bundle and subscribes to the crosshair itself, so it
follows the pointer at browser speed — nothing is sent to Python while the mouse
moves. It is placed inside the chart's own element, so the position is correct
with a left/right price scale, a top bar, several panes (the band is as tall as
the pane it is in) and after a resize.

The background and the value text are CSS variables by default, so a tooltip
follows `chart.win.theme('light')`; the title and the 1px frame take the
series' own colour (exactly like the tutorial, and it tells you which series a
box belongs to when several are on screen). The translucent magnifier band is a
separate layer, so its text stays fully opaque.

## Driving it after creation

```python
tip.apply_options(width=120, background='#101418')   # any creation option
tip.set_title('AAPL')
tip.set_fields('open', 'close')     # set_fields('auto') / set_fields()
tip.set_mode('magnifier')           # switch between the two
tip.hide(); tip.show(); tip.visible()
tip.options()                       # what the JS side holds
tip.remove()                        # take it off the page, drop the handle
```

`hide()` also survives crosshair moves (the box stays hidden until `show()`).

## Related

* `chart.crosshair(...)` styles the crosshair itself. The tutorial hides the
  horizontal line and the labels while a tooltip is on screen, which needs the
  raw option because label visibility has no keyword yet:

  ```python
  chart.apply_options(crosshair={
      'horz_line': {'visible': False, 'label_visible': False},
      'vert_line': {'label_visible': False},
  })
  ```
* `chart.legend(visible=True)` is the other crosshair-driven overlay: it follows
  the pointer *and* lets you toggle each series with its eye icon.
* `chart.events.crosshair_move(...)` gives you the same `param` in Python when
  you need to build something the two modes cannot express.
