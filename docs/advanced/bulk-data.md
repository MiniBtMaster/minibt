# Bulk data

Sending large arrays as JavaScript source is slow: the payload is serialised to
decimal strings, shipped, parsed and re-evaluated.

Above `BINARY_DATA_THRESHOLD` (default 2000 rows) `chart.set()` instead sends a
**base64 column-major Float64 buffer**, rebuilt in the browser by
`Lib.decodeData(base64, columns, strings)`:

```
floats[columnIndex * rowCount + rowIndex]
```

NaN values are omitted, becoming whitespace points exactly like the JSON path.
String columns (such as per-bar `color`) travel as a small JSON object.

## Measured

| rows | JSON source | binary | speed-up |
|---|---|---|---|
| 100,000 | 1.556 s | **0.544 s** | 2.9× |
| 500,000 | 8.880 s | **3.154 s** | 2.8× |

Reproduce:

```bash
python tests/e2e/benchmark.py 100000
```

## Tuning

```python
from pylightcharts import util

util.BINARY_DATA_THRESHOLD = 10_000      # raise to keep small frames on JSON
```

## Conflation

For datasets where the bar spacing gets very small, let the library conflate
instead of rendering every point:

```python
chart.apply_options(enable_conflation=True, precompute_conflation_on_init=True)
series.apply_options(enable_conflation=True, conflation_threshold_factor=6)
```

Custom series can supply a reducer through the JS pane view; the declarative
custom series does not do this yet.

## Tick updates

`chart.update(bar)` sends one small JSON object. For bursts, batch them:

```python
with chart.batch():
    for tick in ticks:
        chart.update(tick)
```

## Indicators

Indicators are recomputed on every update. The incremental path only pushes the
last point and works from a warm-up window (`tail_window`, default 1000), so
cost stays flat regardless of the total number of bars. Cumulative indicators
(`VWAP`) are marked `full_only=True` and are re-sent in full.
