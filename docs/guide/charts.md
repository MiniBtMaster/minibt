# Charts and data

## Creating a chart

```python
from pylightcharts import Chart

chart = Chart(width=1000, height=700, title='My chart')
chart.show(block=True)          # block=False keeps control
```

`Chart` is an `AbstractChart`, which is itself the main candlestick series. Any
method available on a series is available on the chart.

## Setting data

The DataFrame needs a `time` column (or a datetime index) plus `open`, `high`,
`low`, `close` and optionally `volume`.

```python
chart.set(df)
```

Column names are matched case-insensitively for the OHLC set, and `date` is
accepted as an alias of `time`.

### NaN gaps break the line

A `nan` in the value column is a **gap**: `[1, 2, 3, nan, nan, 6, 7, 8]` is
drawn as **two** segments. (lightweight-charts v5 treats a whitespace item as
"a time scale point only" and would connect the two sides, so `pylightcharts`
draws the break itself - see below.)

Only `Line` series do this; `Area` / `Baseline` fills would also have to be
split, which is not implemented yet.

Up to `Line.MAX_GAP_SEGMENTS` (64) segments the main line is hidden and each
segment is drawn by an extra, legend-less series (clean tooltips). Above that -
a line that alternates `nan` every other bar, or a colour-split line with
hundreds of runs - hundreds of series would mean hundreds of `addSeries` +
`setData` round-trips and repaints (the indicator then looks like it is drawing
in stages, and loads slowly). Those switch to a **single series with transparent
gaps**: gap points are filled with the previous value and get a transparent
`color`, and the engine (which colours each segment from its starting point)
skips them. Visually the same break, but `macd_up` / `macd_dn` from MACD
Bollinger Bands went from 743 internal series to 0. Bands created with
`fill_between` still break at those points (the `LineFill` view treats a
transparent point as a gap). Raise `Line.MAX_GAP_SEGMENTS` if a fragmented line
really must be split into separate series.

Two per-series switches tune this for hosts that know their data better:

```python
fill = chart.create_line('fill_up', color='rgba(0,0,0,0)')
fill.skip_gap_segments()      # hidden fill_between carrier: never split
live = chart.create_line('supertrend', color='#26a69a')
live.prefer_single_gap()      # realtime line: always the 1-series path
live.apply_options(color='#ef5350')
live.repaint_gaps()           # re-send so the per-point gap colours follow
```

`skip_gap_segments()` keeps the (usually invisible) upper/lower lines of a
`fill_between` band from being split into hundreds of series;
`prefer_single_gap()` forces the transparent-gap path below
`MAX_GAP_SEGMENTS` too (a line that is re-set every tick would otherwise
`delete` + `addSeries` + `setData` on each frame). Because the single-series path
bakes the line colour into the data, `repaint_gaps()` re-sends it after
`apply_options(color=...)`.

### Time column units

The `time` column may hold datetimes, ISO strings, or epoch **numbers**; numbers
are interpreted by magnitude (seconds / milliseconds / microseconds /
nanoseconds), so all of these describe the same instant:

```python
chart.set(pd.DataFrame({'time': ['2024-01-01', '2024-01-02'], ...}))
chart.set(df.assign(time=pd.date_range('2024-01-01', periods=len(df))))
chart.set(df.assign(time=1704067200))            # epoch seconds
```

That matters because **every chart keeps its own `time` in epoch seconds**
(`chart.candle_data['time']`, `series.data['time']`), so feeding that column back
in - the natural thing to do for an indicator frame that shares the candles'
axis - works:

```python
times = chart.candle_data['time']                       # epoch seconds
pane = chart.add_pane()
rsi = chart.pane_add_series(pane, 'Line', name='RSI 14')
rsi.set(pd.DataFrame({'time': times, 'RSI 14': compute(chart.candle_data)}))
```

Before the unit inference this landed in 1970 (pandas reads a bare number as
nanoseconds), which looked like "the indicator is drawn left of the first
candle"; `pylightcharts.util.infer_time_unit` is the helper behind it.

## Conditional colours

Lightweight Charts accepts a `color` (and, for candles, `borderColor` /
`wickColor`) on every data point, so any condition can drive the colours. Add the
column to the frame you pass to `set()` / `update()` - the engine's exact key
names are used, so camelCase them yourself:

`color_by()` does the mapping for you (and is the pylightcharts equivalent of
the JavaScript `.map()` in the upstream docs):

```python
from pylightcharts import color_by

ma20 = df['close'].rolling(20, min_periods=1).mean()
chart.set(color_by(df, df['close'] > ma20, 'orange'))       # whole candle

color_by(df, cond, 'orange', wick_color=False)              # body only
color_by(df, cond, '#26a69a', else_color='#ef5350')         # both branches
color_by(df, cond, df['tone'])                              # one colour per row
```

It fills `color` (body) plus `wickColor` / `borderColor`, and leaves the rows
outside the condition untouched - their keys are omitted, so they keep the
series style.

There is also a shortcut that colours data a series *already holds* - including
the lines an indicator computed for you, and the main candles:

```python
sma = chart.add_sma(source='close', length=20)
sma.color_by(sma.data['value'].diff() > 0, '#26a69a', else_color='#ef5350')

chart.color_by(chart.candle_data['close'] > 205, 'orange')     # main candles
```

`series.color_by(...)` re-sends that series' frame with the colour columns
added and returns it; `condition` may be a boolean `Series` / array /
`callable(frame)` (a shorter `Series` is aligned on `time`). A later full
refresh (`chart.set()`, an indicator recompute) sends the computed data again,
so re-apply it afterwards.

The columns can also be written by hand (the engine's exact camelCase names):

```python
up = df['close'] > ma20
df['color'] = np.where(up, '#26a69a', '#ef5350')          # candle body
df['borderColor'] = np.where(up, '#26a69a', '#ef5350')    # candle edge
df['wickColor'] = np.where(up, '#26a69a', '#ef5350')      # candle wick
chart.set(df)                                             # main candles

line = chart.create_line(name='close')
line.set(df[['time', 'close', 'color']])                  # line / bar / area
hist.set(df[['time', 'volume', 'color']])                 # histogram bars
```

* per-point `color` alone repaints the candle **body**; the wick and the border
  keep the series style unless `wickColor` / `borderColor` are supplied too;
* works for `Line`, `Area`, `Bar` and `Histogram` series as well as the main
  candle series, and with both encodings (JSON, and the base64 binary path used
  from 2000 rows up - string columns travel as a small JSON side-table);
* `update(row)` takes the same keys, so live bars can be coloured per tick;
* for colouring a **range** rather than a point, use `vertical_span(t1, t2,
  color=)` (time range), `horizontal_span(low, high, color=, opacity=)` (price
  range), `shapes.*` inside a custom series, or your own primitive;
* the v5 up/down plugin recolours a line by direction:
  `series.create_up_down_markers(positive_color=..., negative_color=...)`.

## Live updates

```python
chart.update(next_bar)                       # one bar; replaces the last if time matches
chart.update_from_tick(tick, cumulative_volume=True)
```

Indicators and drawings follow automatically — see [Indicators](indicators.md).

### Batching ticks

Every bridge call is a webview round-trip, so wrap bursts:

```python
with chart.batch():
    for tick in ticks:
        chart.update(tick)      # flushed as one script
```

## Multiple series

```python
chart.create_line('close', color='#FF9800')          # a line from a column
chart.create_histogram('volume')
chart.create_area('close')
chart.create_bar('close')
chart.create_baseline('close', base_value=100)
chart.add_series('Line', 'ma20', color='#0ff')       # any built-in type by name
```

`add_series(kind, name, pane_index=None, **options)` accepts every option of the
underlying series with `snake_case` keys.

## Multi-chart sync

```python
price = Chart(); volume = Chart()
price.sync(volume)                        # volume follows price pan/zoom
price.sync(volume, crosshairs_only=True)
```

## Reading state back

```python
chart.price_to_coordinate(105)            # and coordinate_to_price()
chart.data_by_index(10); chart.data_points(); chart.last_value_data()
chart.bars_in_logical_range(0, 50)
chart.get_visible_range(); chart.get_visible_logical_range()
chart.time_to_coordinate(t); chart.coordinate_to_time(x)
```

## Screenshots

```python
png = chart.screenshot()                  # live window only
```

For server-side rendering see [Headless rendering](../advanced/headless.md).
