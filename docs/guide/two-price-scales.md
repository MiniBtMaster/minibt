# Two symbols on two price scales

A chart can show **two** price scales at once: one on the right (the default) and
one on the left. The official
[Two Price Scales](https://tradingview.github.io/lightweight-charts/tutorials/how_to/two-price-scales)
tutorial puts the second series on the left axis; this package keeps the main
candles on the **right** one (the usual habit) and gives the overlay the **left**
one, in a single call:

```python
chart.set(btc)                                      # main candles, right axis
chart.add_symbol('ETHUSDT', eth, kind='candles')     # candles on the left axis
chart.add_symbol('BTC/GLD', ratio, kind='line')      # or a line / area / bar
```

`chart.add_symbol(name, data, ...)` is a pylightcharts extension. It

1. makes the target scale visible (`priceScale(id).applyOptions({visible: true})`,
   which is what the tutorial does through the chart options),
2. creates the series on that scale (`price_scale_id` on the series options),
3. names it on the price line label, so it is obvious which axis belongs to which
   symbol,
4. optionally sets the scale's vertical share (`margins=`).

## Options

```python
eth = chart.add_symbol(
    'ETHUSDT',
    eth,                      # DataFrame (time + OHLC for a bar, time + value
                              # otherwise), Series with a time index, or None
                              # to fill it later with eth.set(...)
    kind='candles',           # 'candles' | 'bars' | 'line' | 'area'
                              # | 'baseline' | 'histogram'
    scale='left',             # 'left' (default) or 'right'
    margins=(0.55, 0.0),      # keep it in the lower 45% of the pane
    up_color='#26A69A', down_color='#EF5350',   # candles: borders/wicks follow
    color='#2962FF', line_width=2,              # lines / areas
    price_line=True, price_label=True,          # the last-value label shows name
    legend_toggle=True,       # False: legend row without its eye icon
    value_column='close',     # when a single-value frame is ambiguous
)
```

`scale=` accepts any id; anything other than `left` / `right` becomes an
*overlay* scale with no axis of its own - that is how the volume series works -
so only `'left'` and `'right'` give you a visible scale (Lightweight Charts has
no third one, see `docs/advanced/deferred.md` #27).

## Overlapping or split

Both scales autoscale their own series over the whole pane, so by default the two
symbols overlap - that is the tutorial's look, and it is the right one for a
ratio or a spread. To stack them instead, hand out vertical shares:

```python
chart.add_symbol('ETHUSDT', eth, margins=(0.55, 0.0))   # lower 45% of the pane
chart.scale_margins(right=(0.0, 0.55))                   # the main one on top
# or both at once:
chart.scale_margins(right=(0.0, 0.55), left=(0.55, 0.0))
```

`(top, bottom)` is the **empty** space at the top / bottom of that scale, so
`top=0.55` leaves the data in the lower 45%.

## Things worth knowing

* **The crosshair magnet**: by default it snaps to the first series' data points;
  the tutorial suggests `CrosshairMode.Normal` when two symbols share the pane -
  `chart.crosshair(mode='normal')`.
* **Data columns**: a bar overlay keeps its OHLC columns and uses the symbol only
  as its legend label; a single-value overlay has its value column renamed to the
  symbol, so both can be created with the same `add_symbol(...)` call. If a frame
  has several numeric columns and none is called `value` / `close` / `price`, pass
  `value_column=`.
* **Layout, panes and resizes** need no special handling: the overlay lives in the
  same pane as the main series, so `chart.fit()`, panes and the page top bar all
  treat it as just another series.
* **Overlays that know about the left scale**: the legend and the crosshair
  tooltips measure the pane's *drawing area* (the pane element itself spans the
  price scales), so a legend that used to sit on top of the left scale's labels
  now starts to the right of it, and a magnifier band or tracking box is not
  shifted by the scale's width. A floating `TopBar` / `Table` is positioned
  against the window or the chart container, so an explicitly left-anchored table
  can still overlap the axis - anchor tables right or give them an offset.
* **A third symbol** can share one of the two scales (`scale='left'` again) or use
  a separate pane (`chart.add_series(..., pane_index=1)`); a third *visible* axis
  is not something the engine supports.
