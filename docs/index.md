# pylightcharts

Python bindings for [TradingView Lightweight Charts™](https://github.com/tradingview/lightweight-charts),
aiming at near-full API coverage with a pythonic interface.

This is **not** a re-implementation of the charting engine in Python. It embeds
the official, battle-tested JavaScript renderer in a WebView and drives it from
Python, so visual fidelity and performance match the JS version.

```python
import pandas as pd
from pylightcharts import Chart

chart = Chart()
chart.set(pd.read_csv('ohlcv.csv'))       # columns: time, open, high, low, close, volume
chart.add_sma('close', 20)
chart.add_rsi(14)
chart.show(block=True)
```

## What you get

| | |
|---|---|
| **Series** | line, area, bar, baseline, candlestick, histogram, plus declarative **custom series** |
| **Indicators** | 17 built in (SMA/EMA/WMA/RSI/MACD/Bollinger/Stochastic/ATR/VWAP/Donchian/OBV/CCI/%R/ADX/Keltner/ROC/MFI), auto-refreshed on data changes |
| **Drawing tools** | trend line, horizontal, vertical, ray, box, fibonacci, measure, parallel channel, position, pitchfork, triangle, fibonacci extension, gann fan |
| **Axes** | time, numeric-x **yield curve** / **options** charts, declarative price & time formatters, custom `IHorzScaleBehavior` hook |
| **Panes** | native lightweight-charts v5 multi-pane |
| **Data** | pandas in, automatic binary transfer for large frames, tick updates and batching |
| **Rendering** | pywebview / Qt (PyQt6, PySide6) / wx / Jupyter / Streamlit / **browser (`BrowserChart`: static HTML or a live SSE stream)**, plus **headless server-side PNG** |
| **Extras** | top bar, toolbox, tables, **panels (`DataGrid` / `Sparkline` / `OrderTicket`)**, multi-chart sync, screenshots |

## Design

```
Python API  ──►  generic JSON/JS bridge  ──►  Lib.Handler (TypeScript)  ──►  Lightweight Charts v5
```

The Python layer is a thin, generic bridge: `Window.invoke(handle, method, *args)`
calls any method on any live chart object, so new features rarely need
TypeScript. See [Bridge architecture](advanced/bridge.md).

## Where to go next

- [Installation](installation.md)
- [Charts and data](guide/charts.md)
- [Indicators](guide/indicators.md)
- [Floating tables](guide/table.md)
- [Panels (`DataGrid` / `OrderTicket`)](guide/panels.md)
- [Qt integration](guide/qt.md)
- [Examples](guide/examples.md)
- [Headless rendering](advanced/headless.md)
- [Deferred features and known gaps](advanced/deferred.md)
- [Migrating from lightweight-charts-python](guide/migration.md)
- [Changelog](changelog.md)
- [API reference](api.md)

## Acknowledgements

- Python layer, GUI backends and the drawing framework are derived from
  [lightweight-charts-python](https://github.com/louisnw01/lightweight-charts-python) (MIT).
- The charting engine is
  [TradingView Lightweight Charts™](https://github.com/tradingview/lightweight-charts) (Apache-2.0), see `NOTICE`.
