# Custom series

A custom series normally means implementing a renderer whose `draw()` runs
synchronously every frame — Python cannot take part in that. `pylightcharts`
splits the work:

```
py: compute shape descriptors, once per data update
js: one generic renderer maps them to pixels every frame
```

## Usage

```python
from pylightcharts import shapes

series = chart.add_custom_series('range bars', pane_index='new')
series.set(df, shapes=lambda row: shapes.range_bar(row['low'], row['high']))
```

Each data item may carry:

| field | meaning |
|---|---|
| `time` | required |
| `value` | last value / crosshair price |
| `low`, `high` | auto-scale range |
| `color` | bar colour for the price line and label |
| `shapes` | list of shape descriptors |

## Shape builders

Vertical anchors are **prices**, horizontal anchors are offsets in **bar-spacing
units** (`-0.4 .. 0.4` spans one bar).

```python
shapes.rect(from_price, to_price, left=-0.4, right=0.4,
            fill_color=None, border_color=None, border_width=1)
shapes.band(from_price, to_price, fill_color=...)
shapes.line(price, left=-0.4, right=0.4, color=None, width=1, style='solid')
shapes.circle(price, offset=0.0, radius=3, color=None, border_color=None)
shapes.marker(price, marker='circle', offset=0.0, size=10, color=None,
              border_color=None)
shapes.text(price, text, offset=0.0, color=None, font_size=12,
            align='center', baseline='middle', line_height=1.2,
            offset_x=0.0, offset_y=0.0, font_family=None, font_weight=None,
            font_style=None, background_color=None, background_alpha=None,
            border_color=None, border_alpha=None, border_width=1.0, padding=4.0)
shapes.polyline([(offset, price), ...], color=None, width=1, fill_color=None)
```

`shapes.text` renders **multi-line labels**: a newline (`\n`) inside
`text` is split into several lines (same convention as bokeh's `LabelSet`),
spaced `line_height` x `font_size` apart and anchored on `baseline`
(`'top'` grows downwards, `'bottom'` upwards, `'middle'` keeps the block
centred on `price`):

```python
series.set(df, shapes=lambda row: shapes.text(row['price'], 'BUY\nCCI\nRSI'))
```

`shapes.text` also draws an optional **label box** (`background_color` +
  `border_color`, sized with `padding`) and takes **pixel** offsets
  (`offset_x` / `offset_y`), a font family / weight / style, and
  `text_align` (`'left'` / `'center'` / `'right'`) - everything is optional.

  `shapes.marker` is the odd one out: its `offset` is a **pixel** vertical shift
(positive = down) and `size` a **pixel** half-extent, so the glyph stays the same
size at every zoom level (`polyline`/`circle` anchors are prices, so they stretch
with the price scale). `marker` takes a minibt ``Markers`` name: `triangle`,
`inverted_triangle`, `arrow_up`, `arrow_down`, `circle`, `circle_cross`,
`circle_dot`, `circle_x`, `circle_y`, `square`, `dot`, `dash`, `cross`,
`asterisk`, `triangle_dot`. For `triangle`/`inverted_triangle`/`arrow_*` the
anchor is the glyph's **tip** (place it right against a bar's high/low); for the
rest it is the centre. Signal markers in `minibt.strategy.realtime` are drawn
this way - LWC v5's marker primitive does not take part in the autoscale, so a
`belowBar` marker is clipped away as soon as you zoom in.

Presets:

```python
shapes.range_bar(low, high)
shapes.box_plot(low, q1, median, q3, high)
shapes.error_bar(value, lower, upper)
shapes.stem(price, baseline=0.0, color=None, width=1, style='dashed',
            cap=False, cap_radius=3)
```

`shapes.stem` is a vertical stick from `baseline` to `price` (a "lollipop"). It
is what you want when per-bar values read better as bars hanging off a common
axis - per-trade PnL, deviation from a moving average, volume at price. The
`style` defaults to dashed, and `cap=True` adds a small circle on the tip so a
near-zero value is still visible:

```python
series.set(df, shapes=lambda row: shapes.stem(row['pnl'],
                                              color=row['color'], cap=True))
```

(LWC has no "vertical dashed line" primitive; this is a `polyline` whose two
points share the same bar offset, so it needs no JS of its own.)

## Worked example

```python
def box_row(row):
    return shapes.box_plot(row['low'], row['q1'], row['median'], row['q3'], row['high'])

df['q1'] = df['close'].rolling(20).quantile(0.25)
df['median'] = df['close'].rolling(20).median()
df['q3'] = df['close'].rolling(20).quantile(0.75)

box = chart.add_custom_series('box plot', pane_index='new')
box.set(df, shapes=box_row)
```

`shapes` may also be a column name in the DataFrame, or a list (one entry per
row).

## Custom pane view (`spec=`)

`add_custom_series(spec={...})` replaces the built-in shape renderer with JS
callbacks registered through `chart.register_js_callback` (`rendererDraw`,
`rendererHitTest`, `priceValueBuilder`, `isWhitespace`, `defaultOptions`,
`destroy`, `conflationReducer`).

`rendererDraw` receives `(target, priceConverter, view)` and runs on every frame,
so it must **only draw bars that are currently visible**: the chart only computes
coordinates for the visible slice, and the rest keep a stale or `NaN` `x`. Use
`view.visibleBars()` instead of the raw `view._bars` array, otherwise the
off-screen shapes are re-drawn on top of the visible data (they pile up along the
pane edges as you zoom):

```python
chart.register_js_callback(
    'draw_dots', ['target', 'priceConverter', 'view'],
    "target.useBitmapCoordinateSpace(scope => {"
    "  const ctx = scope.context;"
    "  const h = scope.horizontalPixelRatio;"
    "  const v = scope.verticalPixelRatio;"
    "  ctx.fillStyle = '#7E57C2';"
    "  for (const bar of view.visibleBars()) {"
    "    const y = priceConverter(bar.originalData.value);"
    "    if (y === null || y === undefined) continue;"
    "    ctx.beginPath();"
    "    ctx.arc(bar.x * h, y * v, 2.5 * h, 0, Math.PI * 2);"
    "    ctx.fill();"
    "  }"
    "});")

series = chart.add_custom_series('dots', spec={'rendererDraw': 'draw_dots'})
```

## Notes

- The series is not refreshed automatically on `chart.update()`; call
  `series.set(...)` again (custom data goes through JSON, not the binary path).
- `series.update({...})` pushes a single item.
- Rendering stays in JS, so pan/zoom remains smooth.
