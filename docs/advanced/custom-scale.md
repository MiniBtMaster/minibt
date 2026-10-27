# Formatters and custom axes

## Declarative formatters

`localization.priceFormatter` and `timeFormatter` are **synchronous JS
callbacks**, so Python cannot supply a function. Instead you supply a spec which
is turned into a real JS function.

```python
chart.set_price_formatter(decimals=2, thousands=True, prefix='$', suffix='')
chart.set_price_formatter(compact=True)                  # 1.2K / 3.4M / 5.6B

chart.set_time_formatter('YYYY-MM-DD HH:mm')
chart.set_time_formatter('MMM DD', utc=False)
```

Time template tokens: `YYYY YY MMM MM DD HH mm ss`.

### Custom JS formatter

Write the function in JS and reference it by name:

```python
chart.register_js_formatter('eur', "value => '\u20ac' + value.toFixed(2)")
chart.set_price_formatter(name='eur')
```

The registration is a plain bridge call, so it can also be done directly:

```python
chart.win.run_script("Lib.registerFormatter('eur', value => '€' + value.toFixed(2))")
```

`Lib.makeNumberFormatter(spec)` / `Lib.makeTimeFormatter(spec)` are exported too,
if you want to call them from JS yourself.

### Which formatter wins

Every one of these writes the same two options
(`localization.priceFormatter` / `timeFormatter`), so:

- **`name=` replaces the declarative options** - `set_price_formatter(name='eur',
  prefix='$')` is an error (a `ValueError`), not a merge: a named formatter is
  used as-is.
- **The last call wins.** A later `set_price_formatter(...)`,
  `set_price_formatter_callback(...)` or a generic
  `set_option_callback(chart, 'applyOptions', 'localization.priceFormatter', ...)`
  silently overrides the earlier ones - only the final one reaches the axis.
- **`chart.format_price(value)`** (a readback, needs a loaded chart) formats a
  value with whatever is in effect, which is the quickest way to see which call
  won:

  ```python
  chart.set_price_formatter(decimals=2, thousands=True, prefix='$')
  print(chart.format_price(1234.5))        # '$1,234.50'
  chart.register_js_formatter('eur', "value => '€' + value.toFixed(2)")
  chart.set_price_formatter(name='eur')
  print(chart.format_price(1234.5))        # '€1234.50' (no thousands, no prefix)
  ```

## Numeric horizontal axes

Two built-in chart types put a number (not a time) on the x axis:

```python
from pylightcharts import YieldCurveChart, OptionsChart

curve = YieldCurveChart()
series = curve.add_series('Line', 'rate')
series.set(pd.DataFrame({'time': [1, 3, 12, 60], 'rate': [4.4, 4.1, 3.8, 3.5]}))
curve.show()

surface = OptionsChart()          # x axis is the strike
iv = surface.add_series('Line', 'iv')
iv.set(pd.DataFrame({'time': [90, 100, 110], 'iv': [0.32, 0.24, 0.35]}))
```

- The yield-curve chart only supports `Line` and `Area` (upstream restriction).
- `chart.set(df)` is not available (there is no candlestick series) — call
  `add_series(...)` and `series.set(...)` instead.
- Everything else (panes, options, drawings, custom series, formatters) works.

## Fully custom horizontal scale behavior

`createChartEx(container, horzScaleBehavior, options)` accepts any
`IHorzScaleBehavior` instance. Python cannot construct one, so register a JS
instance by name and ask for it when the chart is created.

```python
class MyChart(AbstractChart):
    _chart_kind = 'custom:myScale'

chart = MyChart(window)
chart.win.preload("Lib.registerHorzScaleBehavior('myScale', new MyBehavior())")
```

`Window.preload(script)` queues JavaScript that runs **before** the handler is
created (it must be called before the webview loads).

!!! warning
    A horizontal scale behavior is a substantial interface
    (`convertHorzItemToInternal`, `formatHorzItem`, `formatTickMark`,
    `maxTickMarkWeight`, `fillWeightsForPoints`, `setPoints`, `timeScale`, ...).
    Upstream's `HorzScaleBehaviorPrice` is a good reference implementation —
    copy it into your page and register an instance.

The handler accepts `'time'` (default), `'yield-curve'`, `'options'` or
`'custom:<name>'`.
