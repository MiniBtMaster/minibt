"""Reproduce (and now verify) miniqt displaying minibt 1.2.8 indicators.

minibt 1.2.8 added a 14th return value to `IndicatorsBase._get_plot_datas()`
(`bandstyle`). miniqt's `Chart.add_indicator` still unpacked 13, so every
indicator failed with

    显示指标时出错: too many values to unpack (expected 13)

and `_retry_add_indicator` retried it forever. This drives the real miniqt
`Chart.add_indicator` for a spread of indicator shapes.

    python tests/e2e/miniqt_indicator_check.py
"""
from __future__ import annotations

import os
import pathlib
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np                                   # noqa: E402
import pandas as pd                                  # noqa: E402

ROWS = 300

#: (class, method, kwargs) - every output shape minibt can produce
INDICATORS = (
    ('PandasTa', 'macd', {}),                  # 2 lines + a vbar histogram in one pane
    ('PandasTa', 'sma', {'length': 20}),       # IndSeries, overlays the price
    ('PandasTa', 'rsi', {'length': 14}),       # IndSeries, own pane
    ('TradingView', 'ADX_and_DI', {}),         # 3-line pane
    ('TradingView', 'SuperTrend', {}),         # overlays + pane + signal markers
    ('PandasTa', 'bbands', {}),                # mixed overlap -> the `doubles` path
)


def watchdog():
    import time

    time.sleep(180)
    print('WATCHDOG: timeout', flush=True)
    os._exit(2)


def make_frames():
    """minibt wants `datetime`; the chart wants epoch `time`."""
    rng = np.random.default_rng(23)
    close = 100 + np.cumsum(rng.standard_normal(ROWS))
    open_ = np.concatenate(([close[0]], close[:-1])) + rng.standard_normal(ROWS) * 0.3
    minibt_frame = pd.DataFrame({
        'datetime': pd.date_range('2024-01-01', periods=ROWS, freq='D'),
        'open': open_,
        'high': np.maximum(close, open_) + np.abs(rng.standard_normal(ROWS)) * 0.8,
        'low': np.minimum(close, open_) - np.abs(rng.standard_normal(ROWS)) * 0.8,
        'close': close,
        'volume': rng.integers(1_000, 8_000, ROWS),
    })
    chart_frame = minibt_frame.rename(columns={'datetime': 'time'})
    chart_frame['time'] = chart_frame['time'].astype('int64') // 10 ** 9
    return minibt_frame, chart_frame


def main() -> int:
    threading.Thread(target=watchdog, daemon=True).start()

    from PyQt6.QtWebEngineWidgets import QWebEngineView        # noqa: F401 - before QApplication
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    import minibt
    # miniqt's config loads 'app/config/config.json' with a relative path
    cwd = os.getcwd()
    os.chdir(ROOT / 'miniqt')
    try:
        import miniqt.app.common.config                     # noqa: F401
        # The real entry point imports the main window before building any chart.
        # That chain pulls in qtpy, which promotes Qt's enum members onto the real
        # PyQt6 classes (restoring the PySide6-style flat access miniqt still uses).
        import miniqt.app.view.main_window                  # noqa: F401
    finally:
        os.chdir(cwd)
    import miniqt.app.windows.chart_interface as ci

    print('minibt version         :', getattr(minibt, '__version__', '?'))
    print('chart_interface        :', ci.__name__)
    print('flat Qt enums          :', hasattr(ci.Qt, 'CustomContextMenu'))

    minibt_frame, chart_frame = make_frames()
    kline = minibt.KLine(minibt_frame)

    chart = ci.Chart(None, 1.0, 1.0, False, 'DEMO', 86400, True)
    chart.set(chart_frame)
    print('chart data             :', len(chart.chart.candle_data), 'rows')

    failures = []
    for index, (class_name, method, kwargs) in enumerate(INDICATORS, start=1):
        container = getattr(minibt, class_name)
        if class_name == 'TradingView':
            container = minibt.indicators.tradingview.TradingView
        indicator = getattr(container(kline), method)(**kwargs)
        try:
            chart.add_indicator(index, indicator, chart_frame)
        except Exception as error:                          # noqa: BLE001 - this is the check
            failures.append(f'{class_name}.{method}: {type(error).__name__}: {error}')
            print(f'  FAIL {class_name}.{method:12} {type(error).__name__}: {error}')
            continue
        subcharts = len(chart.subcharts)
        series = sum(len(v) for v in chart.chart_indicators.values())
        print(f'  ok   {class_name}.{method:12} subcharts={subcharts} series={series}')

    print('indicators added       :', len(chart.chart_indicators))
    print('subcharts              :', len(chart.subcharts))

    if failures:
        print('RESULT_ERROR: ' + '; '.join(failures))
        return 1
    if not chart.chart_indicators:
        print('RESULT_ERROR: no indicator was registered')
        return 1
    print('RESULT_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
