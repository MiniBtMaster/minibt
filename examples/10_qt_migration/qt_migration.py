"""Minimal PyQt6 demo — embedding a chart in a desktop application.

This is the shape of a real integration, and what `miniqt`'s
`get_chart_class()` does now that it is on pylightcharts:

1. ``prepare_qt('PyQt6')`` picks the Qt binding **and** imports
   QtWebEngineWidgets, both of which have to happen before the QApplication
   exists (Qt refuses the import afterwards)
2. optionally ``install_alias()`` keeps ``import lightweight_charts`` working,
   for code that still spells it the old way
3. a real chart is drawn: candles, two MA lines, watermark, horizontal line,
   trend line, markers
4. a screenshot is taken through the chart's own ``takeScreenshot()`` and saved

The thing that is *not* here any more is the old "force PyQt6 by replacing
``lightweight_charts.widgets`` globals" dance — pylightcharts chooses its binding
by itself, so there is nothing to patch. (Patching still works if you have it.)

Run it and look at the window; it closes itself and writes ``qt_demo.png``.

    python examples/10_qt_migration/qt_migration.py
"""
import base64
import os
import sys

import numpy as np
import pandas as pd

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

# --- 1. binding + QtWebEngineWidgets, before any QApplication ----------------
from pylightcharts.qt import prepare_qt
prepare_qt('PyQt6')

# --- 1b. optional: let code that still says `lightweight_charts` work -------
from pylightcharts.compat import install_alias
install_alias()
import lightweight_charts                                   # noqa: E402  (== pylightcharts)

from pylightcharts.widgets import QtChart                   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qt_demo.png')


def make_data(rows=300):
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    open_ = np.empty(rows)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    open_ = open_ + rng.standard_normal(rows) * 0.4      # so open != close
    high = np.maximum(close, open_) + np.abs(rng.standard_normal(rows)) * 0.8
    low = np.minimum(close, open_) - np.abs(rng.standard_normal(rows)) * 0.8
    df = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': rng.integers(1_000, 8_000, rows),
    })
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    return df


def main():
    app = QApplication(sys.argv)

    chart = QtChart(None, 1.0, 1.0, False, False)
    view = chart.get_webview()
    view.resize(1200, 700)
    view.setWindowTitle('pylightcharts - QtChart migration demo')
    view.show()

    df = make_data()
    chart.set(df)
    chart.layout(background_color='#0b0e14', text_color='#d1d4dc')
    chart.candle_style(up_color='#26a69a', down_color='#ef5350', border_visible=False)
    chart.grid(color='rgba(42,46,57,0.6)')
    chart.precision(2)

    ma20 = chart.create_line('ma20', color='#FF9800', width=2)
    ma20.set(df[['time', 'ma20']])
    ma60 = chart.create_line('ma60', color='#2196F3', width=2)
    ma60.set(df[['time', 'ma60']])

    chart.watermark('pylightcharts', font_size=44)
    chart.horizontal_line(float(df['close'].iloc[-1]), color='#00e676',
                          style='dashed', text='last')
    chart.trend_line(df['time'].iloc[40], float(df['low'].iloc[40]),
                     df['time'].iloc[120], float(df['high'].iloc[120]))
    chart.marker(df['time'].iloc[60], position='below', shape='arrow_up',
                 color='#26a69a', text='BUY')
    chart.marker(df['time'].iloc[150], position='above', shape='arrow_down',
                 color='#ef5350', text='SELL')

    def save_png(data_url):
        if data_url and ',' in data_url:
            with open(OUT, 'wb') as handle:
                handle.write(base64.b64decode(data_url.split(',', 1)[1]))
            print(f'screenshot     : {OUT}')
        print('RESULT_OK')
        app.quit()

    def on_loaded(_=None):
        def probe():
            print('alias package  :', lightweight_charts.__name__)
            print('QtChart module :', QtChart.__module__)
            print('chart id       :', chart.id)
            view.page().runJavaScript('document.querySelectorAll("canvas").length',
                                      lambda n: print('canvases       :', n))
            view.page().runJavaScript(
                f'{chart.id}.chart.takeScreenshot().toDataURL()', save_png)
        QTimer.singleShot(2500, probe)

    view.page().loadFinished.connect(on_loaded)
    QTimer.singleShot(40_000, app.quit)          # watchdog
    app.exec()


if __name__ == '__main__':
    main()
