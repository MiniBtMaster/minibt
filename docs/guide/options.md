# Options and styling

There are two ways to style things: dedicated helpers for the common cases, and
`apply_options` for everything else.

## Escape hatch: `apply_options`

Any option of the underlying API can be passed with `snake_case` keys — they are
converted to `camelCase` automatically:

```python
chart.apply_options(auto_size=True, localization={'price_format': {'precision': 4}})
chart.time_scale_options(right_offset=5, bar_spacing=8)
chart.series_options(price_line_width=2, base_line_visible=False)   # main series

series.apply_options(line_width=3, crosshair_marker_visible=False)
scale.apply_options(mode=1, invert_scale=True)
```

## Common helpers

```python
chart.layout(background_color='#0b0e14', text_color='#d1d4dc', font_size=12)
chart.grid(vert_enabled=True, horz_enabled=True, color='rgba(42,46,57,0.5)')
# the python form of chart.applyOptions({crosshair: {...}})
chart.crosshair(
    mode='normal',                      # 'normal' | 'magnet' | 'hidden'
    vert_width=8,                       # vertical line
    vert_color='#C3BCDB44',
    vert_style='solid',                 # 'solid' | 'dotted' | 'dashed' | ...
    vert_label_background_color='#9B7DFF',
    horz_color='#9B7DFF',               # horizontal line (+ its label)
    horz_label_background_color='#9B7DFF',
)
chart.time_scale(time_visible=True, seconds_visible=False, right_offset=5)
chart.set_visible_range('2024-01-01', '2024-03-01')

chart.candle_style(up_color='#26a69a', down_color='#ef5350', border_visible=False)
chart.price_scale(auto_scale=True, mode='logarithmic', scale_margin_top=0.1)
chart.volume_config(scale_margin_top=0.8, up_color='rgba(38,166,154,0.5)')
chart.precision(4)
chart.price_line(label_visible=True, line_visible=True, title='price')
chart.watermark('ACME', font_size=48, color='rgba(255,255,255,0.06)')
```

## Legend and the series visibility toggle

The legend is **off by default** (same as `lightweight-charts-python`), so a new
chart shows no labels at all - call `chart.legend(visible=True, ...)` to turn it
on. The mode flags gate the parts of it: `ohlc` / `percent` for the block in the
top-left, `lines` for the per-series rows (an indicator with an empty name or
`lines=False` never gets a row):

```python
chart.legend(visible=True, ohlc=True, percent=True, lines=True)
```

Indicator names are generated for you (`add_sma(length=20)` -> `SMA 20`,
`add_macd()` -> `MACD 12,26` / `MACD signal 9` / `MACD histogram`), so
`chart.legend(True)` is enough to label every indicator on the chart.

This is the `lightweight-charts-python` legend behaviour: the OHLC/percent/volume
block in the top-left appears while the crosshair is over a bar and is hidden
again when the pointer leaves the chart, while the series rows keep their last
value. The series rows behave the same way: they are only shown while the
crosshair is over a bar and disappear with the block. While the pointer sits on a
legend row everything is kept as it is - the row takes the pointer away from the
chart, and hiding/showing on every such transition made the labels flash. Each row carries an **eye icon** that hides/shows the series (drawn by
`pylightcharts`, upstream Lightweight Charts has no such control). The eye is
shown by default; pass `legend_toggle=False` when visibility is handled somewhere
else (e.g. an indicator settings window that calls `series.hide_data()`):

The icon is drawn with `stroke: currentColor`, so it uses the legend's text
colour (`legend(color=...)`, or the theme's text colour) - on a light theme you
get a dark eye on white instead of an invisible white one. The hover background
comes from the root `--hover-bg-color`, so it follows the theme too.

```python
chart.legend(visible=True, ohlc=True, percent=True, lines=True)

chart.create_line('sma', legend_toggle=False)        # no eye on this row
chart.create_histogram('volume', legend_toggle=False)
chart.create_area('close', legend_toggle=False)
chart.add_series('Line', 'vwap', legend_toggle=False)
chart.add_sma(length=20, legend_toggle=False)        # every indicator accepts it
```

It also works on `create_bar`, `create_baseline`, `add_custom_series` and — through
their `**options` — on `add_ema`, `add_wma`, `add_indicator`,
`add_computed_series`, plus every named indicator (`add_rsi`, `add_macd`, ...).

Pass `legend=False` to leave out the **whole row** (not just the eye) - useful for
overlay/reference series that should not take part in the legend:

```python
chart.create_baseline('base', base_value=100)                 # no row by default
chart.create_baseline('base', base_value=100, legend=True)    # ask for the row
chart.add_series('Line', 'vwap', legend=False)                # hide a row
```

Every series type (including baselines) adds a legend row by default; pass
`legend=False` when a reference line should stay out of the legend.

A row always shows its swatch and its name, and appends the value of the bar
under the crosshair when the series has one at that time. The swatch colour is
read from the series options (`color`, or `lineColor` / `topColor` for an area),
so a **custom series**, whose colours live inside its shapes, has no colour of
its own - pass one for the swatch:

```python
chart.add_custom_series('range', color='#2962FF')     # legend swatch colour
```

A custom series built from range shapes carries `low`/`high` instead of `value`,
so its row shows the range (`range : 1.50 - 3.50`). Note that a
**baseline is not a horizontal line**: it is a regular line drawn through the data whose colour
(and fill gradient) switches at `base_value`. For an actual horizontal reference
line use `series.horizontal_line(price)` or `series.create_price_line(price)`
(see *Price lines* above).

`base_value` may be a plain number (`create_baseline('base', base_value=100)` or
`add_series('Baseline', 'base', base_value=100)`); the engine's
`{type: 'price', price: 100}` shape is filled in for you (and also for a later
`apply_options(base_value=...)`). A bare number would otherwise leave
`baseValue.price` undefined - the gradient stops become non-finite and the line is
silently never drawn even though the series exists.

### Legend buttons

Three optional controls can be attached to a legend row (all off by default):

```python
# a settings (gear) button that calls a Python callback with the click position
series.enable_legend_settings(lambda series, x, y: open_settings(series, x, y))

# ...or a self-contained JS menu (params / line style / width / colour / other)
# for hosts without Qt; every change calls func(series, kind, payload)
series.enable_legend_menu({
    'title': 'MACD指标参数',
    'params': [{'name': 'fast', 'value': 12, 'type': 'int'}],
    'lineStyle': 'solid', 'lineWidth': 2, 'lineColor': '#2196f3',
}, lambda series, kind, payload: save(series, kind, payload))

series.pin_legend_row(True)      # keep the row visible without a crosshair

chart.enable_legend_collapse()   # the `∧` / `∨ N` collapse button
```

`series.remove_legend_row()` removes a row outright (it is what `legend=False`
calls internally, and it is idempotent), and `chart.legend(...,
text_visible=False)` hides the free `text` line above the OHLC readout.

## Price lines

```python
line = series.create_price_line(105.0, color='#00e676', title='entry')
line.apply_options(line_visible=False)
line.options()
line.remove()
series.price_lines()
```

## Price bands (horizontal spans)

`horizontal_span(low, high)` shades the area between two prices across the whole
pane - the usual "support/resistance zone" look. It is a v5 series primitive, so
it works on the chart itself (`chart.horizontal_span(...)`) or on any series
(`series.horizontal_span(...)`), and can be deployed per price scale/pane:

```python
band = chart.horizontal_span(98.0, 102.0,       # low, high (plain prices)
                             color='#7E57C2',   # any CSS colour
                             opacity=0.25,      # fill alpha (None → colour's own)
                             line_color='rgba(126, 87, 194, 0.9)',
                             line_width=1, line_style='solid',
                             autoscale=False)   # True keeps it in view
band.set_prices(95.0, 105.0)                   # move/resize
band.apply_options(fill_color='rgba(239, 83, 80, 0.25)')
band.delete()

# a single price (or a list of prices) draws one full-width line each
chart.horizontal_span(100.0, line_color='rgba(255, 255, 255, 0.4)')
chart.horizontal_span([100.0, 110.0])

# filled= forces one of the two forms: False → lines only, True → fill between
# the outermost prices (handy for a list of three or more levels)
chart.horizontal_span(98.0, 108.0, filled=False)
chart.horizontal_span([95.0, 100.0, 105.0], filled=True)

# pane_index= drops the same band into a sub-pane: it anchors to the first series
# created there (a pane needs at least one series to convert prices into pixels)
chart.horizontal_span(2.0, 6.0, pane_index=2, color='#FF5252', opacity=0.25)
```

### Filling between two lines

`fill_between(upper, lower)` shades the area between two series - the band body of
Bollinger/Keltner channels, a spread, an envelope, ... Both lines have to be on
the same pane and price scale:

```python
upper, middle, lower = chart.add_bollinger(source='close', length=20, std=2)
band = chart.fill_between(upper, lower,
                          color='#2962FF',                   # fill colour
                          opacity=0.15,                      # fill alpha
                          line_color=None,                   # optional outline
                          line_width=1, line_style='solid')
band.apply_options(color='rgba(38, 166, 154, 0.18)')
band.delete()

upper.fill_between(lower, color=...).    # the same thing from the series itself
```

The band follows the two lines while panning/zooming and is repainted when either
line's data changes; only the time stamps both lines share are filled.

`opacity` is applied to the fill (via `globalAlpha`), so any colour format works
(`'#7E57C2'`, `'rgb(...)'`, named colours) and the outline stays crisp;
`opacity=None` keeps whatever alpha the colour already carries. The same knob is
available on `vertical_span(..., opacity=...)`.

`pane_index=` is what makes constant support/resistance levels usable in a
**sub-pane**: without it the band lands where the method was called (the chart =
main pane, a series = that series' pane). An empty pane has no price scale, so
`pane_index=` raises a `ValueError` until you add a series there.

The vertical counterpart is `chart.vertical_span(start_time, end_time, color=...)`
(a time range), and `shapes.band(...)` draws a per-bar band inside a custom series.

## Annotations

```python
series.marker(time, position='below', shape='arrow_up', color='#2196F3', text='buy',
              size=2)
series.marker_list([...]); series.remove_marker(id); series.remove_markers([ids])
series.clear_markers()

series.create_up_down_markers(positive_color='#26a69a', negative_color='#ef5350')
chart.create_image_watermark('logo.png', max_width=200)
```

### Swing highs and lows

Lightweight Charts has no swing detection of its own - it can only *draw* the
markers - so pylightcharts computes `length`-bar fractals and marks them with
their price:

```python
chart.mark_swings(length=5, size=2)          # candles: high / low
chart.mark_swings(length=5, label=False)     # no price text
series.mark_swings(length=5)                 # a line: its own peaks / troughs
```

An `arrow_down` above the swing high carries the high price, an `arrow_up` below
the swing low the low price (`decimals=`, `high_color=`, `low_color=`, `size=`,
`clear=`). The pivots are also available on their own - it is a plain function,
so it works outside the chart too:

```python
from pylightcharts.indicators import swing_points

swings = swing_points(df['high'], df['low'], length=5, time=df['time'])
#   time | price | kind ('high' | 'low')
```

A pivot is only *confirmed* `length` bars later, and the markers live in the
series' marker primitive (so `markers_plugin().set_markers(...)` replaces them).

**ZigZag** (波段线) is the other detector: from the running extreme, a retracement
of more than a percentage confirms the pivot and flips the direction, so the
pivots always alternate and small wiggles are ignored:

```python
chart.add_zigzag(threshold=0.03)            # a Line through the pivots + markers
chart.add_zigzag(0.05, markers=False)       # only the line

from pylightcharts.indicators import zigzag
swings = zigzag(df['high'], df['low'], threshold=0.03, time=df['time'],
                include_unconfirmed=True)   # time / price / kind / confirmed
```

`add_zigzag` registers itself like an indicator, so the line is recomputed on
every `chart.set()` / `chart.update()` - it works on a live chart. The last leg
is not confirmed yet (`include_unconfirmed=True` draws it anyway): it **moves**
until a reversal of the threshold closes it, which is the usual ZigZag
behaviour.

### Marker gotchas

- **The classic API and the v5 markers plugin share one primitive.** After
  `series.markers_plugin().set_markers([...])` the markers added earlier with
  `series.marker(...)` / `marker_list(...)` are gone - `set_markers` *replaces*
  the whole list.
- **Up/down markers need a Line or Area series** - the engine throws
  `UpDownMarkersPrimitive is only supported for Area and Line series types`
  otherwise. `chart.up_down_markers_plugin()` is the *chart's own candlestick*
  series, so it raises immediately with that hint; create a line first:

  ```python
  line = chart.create_line(name='close', color='#42A5F5')
  line.set(df[['time', 'close']])
  updown = line.up_down_markers_plugin(positive_color='#26a69a')
  ```
- **A marker needs its time on the chart's time scale.** Markers can be added
  before `chart.set(df)` (they are emitted right away and appear once the data
  arrives), but with a chart that never gets data - or a time outside the data
  range - nothing is drawn. The same goes for the visible range: a marker
  outside the current zoom is not painted (see below).
- **`text` is drawn on top of the marker shape**, so a long label covers the
  fill and a filled square/circle looks much smaller than it is: at `size=3` a
  square shows ~260px of fill without text and ~60px with a two-character label.
- **Up/down markers use the plugin's own format**, which is not the classic one:

  ```python
  updown.set_markers([{'time': t, 'value': 100.5, 'sign': 1}])   # right
  updown.set_markers([{'time': t, 'position': 'aboveBar'}])      # ignored!
  ```

  `value` is the price the marker is drawn at, `sign` picks the arrow
  (`1` up / `0` neutral / `-1` down, default `0`). A marker without `value` has
  no price to draw at and the engine silently paints nothing, so pylightcharts
  raises a `ValueError` instead (use `series.marker(...)` for
  `position`/`shape`/`color`/`text`).
- **Markers outside the visible time range are not drawn at all.** The engine
  only paints a marker whose time is in view, so a marker on an early bar
  disappears when the chart opens showing the last ~170 bars - it looks like the
  marker (or the whole plugin) failed. Call `chart.fit()` / `chart.set_visible_range(...)`
  or place the markers inside the initial window.
- **Marker size is `size` (default `1`), and the base shape is 12-30px** driven
  by the bar spacing, so a dense view shrinks them: `size=3` is ~21px on a fitted
  320-bar chart (9x the area of `size=1`) and reads well. The **up/down plugin's
  markers have no size option** - the engine hard-codes a 4px dot and a 4.7px
  arrow, so use their colours (set at creation) or a classic marker if you need
  something bigger.
- **Up/down marker colours are read when the pane view is built.** Changing
  `positive_color` / `negative_color` with `apply_options` after the plugin was
  attached does not repaint existing markers - pass them to
  `up_down_markers_plugin(...)`. Behaviour options such as
  `update_visibility_duration` (how long the automatic markers stay visible
  after `update()`) do apply at any time.

### Image watermark gotchas

`image_watermark_plugin(...)` paints the image's **pixels** on the pane canvas:

- a **transparent** image (the classic 1x1 all-transparent PNG) draws nothing;
- a **broken data URI** (a mis-split base64 string, a wrong path) fails to load
  and also draws nothing - with no error in the console.

Both look exactly like a plugin that does not work. The engine offers
`max_width` / `max_height` / `padding` / `alpha` only: the image is centred in
its pane, and `alpha` blends it with the background, so the colours are lighter
than the source image. Use `pane_index=` to place it in another pane, and note
that the *text* watermark (`text_watermark_plugin`, with
`horz_align` / `vert_align`) is centred too - move one of them if they overlap.

## Plugins / primitives

`attach_primitive` takes the handle of any JS primitive:

```python
series.attach_primitive('myPrimitive')     # primitive registered via Lib.register
series.detach_primitive('myPrimitive')
chart.attach_pane_primitive('myPrimitive', pane_index=0)
```

## Loading older bars as you scroll

`chart.infinite_history(loader, ...)` extends the chart to the left on demand -
see [Infinite history](infinite-history.md).

## A second symbol / price scale

`chart.add_symbol(...)` overlays another symbol on the other price scale - see
[Two symbols on two price scales](two-price-scales.md).

## Crosshair tooltips

`series.tracking_tooltip(...)` / `series.magnifier_tooltip(...)` put the official
tutorial's two crosshair tooltips on the chart - see
[Crosshair tooltips](tooltips.md).

## Themes (whole UI, light / dark)

A *theme* here is not a chart option — the widgets of this package are styled
through root CSS variables (top bar, legend, menus, hover states) **plus** the
chart options, so a usable light theme has to touch about twenty colours.
`Window.theme` does exactly that in one call; it is a pylightcharts extension.

```python
chart.win.theme('light')                    # whole window, now and later
chart.theme('light')                        # same thing, from a chart
chart.win.theme('light', up='#0a7d5a')      # tweak one colour
chart.win.theme({'background': '#111'})     # dark + override
chart.win.theme('dark')
```

What it styles: the root CSS variables, and on **every** chart the background,
text colour, grid, crosshair (lines + label backgrounds), candles (body, border
and wick up/down), volume up/down, pane separator, price/time scale text and
borders, and the legend's text colour (the eye icon that hides a series follows
it too - it is drawn with `currentColor`, so a light theme gives you a dark eye
on white instead of a white one). Charts created **after** the call inherit
the theme, and floating tables follow it too - both tables created later (their
default colours come from the theme) and tables that already exist
(`Window.theme` calls `Table.set_colors` on them). A table where you passed an
explicit `background_color=` / `border_color=` opts out and keeps your colours.

```python
from pylightcharts.themes import DARK, LIGHT, resolve

resolve('light')['grid']        # '#f0f3fa'
sorted(DARK) == sorted(LIGHT)   # both palettes cover the same names
```

A theme is a **starting point, not a lock**: it is just a batch of normal setter
calls, so anything you set afterwards wins. Toggle it at runtime with a topbar
switch (example 15 does this):

```python
def on_theme(chart):
    chart.theme(chart.topbar['theme'].value)

chart.topbar.switcher('theme', ('dark', 'light'), func=on_theme)
```

`Table.set_colors(background_color=, border_color=, text_color=,
section_color=)` is the same restyle for one table, on its own.

`theme()` only knows the colours listed by `resolve()` — a typo raises
`ValueError` listing the valid names instead of silently doing nothing.

## Conflation (very large data)

Conflation is a plain series option:

```python
chart.apply_options(enable_conflation=True, precompute_conflation_on_init=True)
```

## Attribution logo

Every chart would normally show a small **"Charting by TradingView"** mark in the
bottom-left. `pylightcharts` hides it by default, for the main chart and for
subcharts:

```python
import pylightcharts

pylightcharts.set_attribution_logo(True)    # show it on charts created after this
chart = Chart()                             # or QtChart(...), Workspace, ...
```

A single chart can also ask for it (or opt out) without touching the global
default, on the window classes (`Chart`, `QtChart`, `WxChart`, `JupyterChart`,
`StreamlitChart`):

```python
chart = Chart(attribution_logo=True)    # just this window shows the logo
chart = Chart(attribution_logo=False)   # just this window hides it (default)
```

Lightweight Charts reads `layout.attributionLogo` while a chart is being built and
never re-renders it afterwards, so this is a **creation-time** switch: a chart that
is already on screen keeps whatever it was created with.

> Lightweight Charts is Apache-2.0, and its notice asks for attribution. Keeping
the logo is enough to satisfy that. If you hide it in an application other people
use, credit TradingView and link to <https://www.tradingview.com/> somewhere they
can see it.

## Enums

| helper | values |
|---|---|
| `LINE_STYLE` | `solid`, `dotted`, `dashed`, `large_dashed`, `sparse_dotted` |
| `CROSSHAIR_MODE` | `normal`, `magnet`, `hidden` |
| `PRICE_SCALE_MODE` | `normal`, `logarithmic`, `percentage`, `index100` |
| `MARKER_POSITION` | `above`, `below`, `inside` |
| `MARKER_SHAPE` | `arrow_up`, `arrow_down`, `circle`, `square` |
