# Indicators

Indicators are computed in pure pandas (no extra dependency) and **refresh
automatically**: a full re-send on `chart.set()`, a single-point update on
`chart.update(bar)` — recomputed from a warm-up window so recursive indicators
stay numerically identical to a full run.

## Overlays (price pane)

```python
chart.add_sma('close', 20)
chart.add_ema('close', 50, color='#2196F3')
chart.add_wma('close', 20)
chart.add_bollinger('close', 20, 2)     # -> (upper, middle, lower)
chart.add_keltner(20, 2.0)              # -> (upper, middle, lower)
chart.add_donchian(20)                  # -> (upper, middle, lower)
chart.add_vwap()
```

## Oscillators (own pane by default)

```python
chart.add_rsi(14)                       # own pane + 70/30 guide lines
chart.add_macd()                        # -> (macd, signal, histogram)
chart.add_stochastic()                  # -> (%K, %D)
chart.add_atr(14)
chart.add_adx(14)                       # -> (adx, +DI, -DI)
chart.add_obv()                         # needs volume
chart.add_cci(20)
chart.add_williams_r(14)
chart.add_mfi(14)
chart.add_roc(12)
```

Put an oscillator on the price pane with `pane_index=None`, or into a specific
pane with an integer.

## Raw values

```python
from pylightcharts import indicators

indicators.sma(close, 20)
indicators.rsi(close, 14)
indicators.macd(close)['histogram']
```

## Accuracy

Cross-checked against TA-Lib:

| Indicator | Max difference |
|---|---|
| RSI, Bollinger, OBV, CCI, %R, ROC, MFI | 0 (floating point) |
| ATR | ~1e-4 |
| ADX / +DI / −DI | ~0.1 (Wilder accumulation rounding; first value index matches) |

## Custom indicators

`add_computed_series` registers any `compute(frame) -> pd.Series`:

```python
def spread(frame):
    return frame['high'] - frame['low']

chart.add_computed_series(spread, 'High-Low', pane_index='new')
```

`extra(frame) -> {column: values}` adds extra columns (e.g. per-bar colour).
`full_only=True` disables the incremental path (needed for cumulative
indicators like VWAP).
