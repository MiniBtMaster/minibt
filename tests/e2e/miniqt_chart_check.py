"""Integration check: render a chart through miniqt's own code path.

Unlike `examples/10_qt_migration`, this imports
`miniqt.app.windows.chart_interface` and calls **their** `get_chart_class()` —
so it exercises the real thing, including the patches that module applies:

* the PyQt6 forcing of ``lightweight_charts.widgets`` globals
* ``setattr(Line, 'delete', ...)``
* ``setattr(Events, 'watch_cursor_change', ...)``

It needs miniqt + minibt next to this repository and a Qt-capable session.

    python tests/e2e/miniqt_chart_check.py
"""
from __future__ import annotations

import base64
import os
import pathlib
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pylightcharts.compat import install_alias      # noqa: E402

install_alias()                                     # before miniqt imports the library

import numpy as np                                   # noqa: E402
import pandas as pd                                  # noqa: E402

OUT = pathlib.Path(__file__).with_suffix('.png')


def watchdog():
    time.sleep(120)
    print('WATCHDOG: timeout', flush=True)
    os._exit(2)


def make_data(rows=300):
    rng = np.random.default_rng(11)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    open_ = np.empty(rows)
    open_[0], open_[1:] = close[0], close[:-1]
    open_ = open_ + rng.standard_normal(rows) * 0.4
    df = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': open_,
        'high': np.maximum(close, open_) + np.abs(rng.standard_normal(rows)) * 0.8,
        'low': np.minimum(close, open_) - np.abs(rng.standard_normal(rows)) * 0.8,
        'close': close,
        'volume': rng.integers(1_000, 8_000, rows),
    })
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma20'] = df['ma20'].where(df.index % 97 != 0)      # a NaN gap, exercises their patches
    return df


def main():
    threading.Thread(target=watchdog, daemon=True).start()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    # QtWebEngineWidgets must be imported (or AA_ShareOpenGLContexts set) before the
    # QApplication exists; miniqt gets this for free from another module, we do it here.
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

    app = QApplication(sys.argv)

    # miniqt/app/common/config.py loads 'app/config/config.json' with a *relative*
    # path; import it from miniqt/ so it does not litter the repository root.
    _cwd = os.getcwd()
    os.chdir(ROOT / 'miniqt')
    try:
        import miniqt.app.common.config      # noqa: F401  (initialises chart_cfg)
    finally:
        os.chdir(_cwd)
    from minibt.indicators.core import BtIndicator  # noqa: F401  (minibt is importable)
    import miniqt.app.windows.chart_interface as ci
    print('chart_interface module :', ci.__name__)
    print('Line.delete patched?   :', ci.Line.delete.__name__)
    print('SeriesCommon.set orig? :', getattr(ci, '_original_series_set', None) is not None)

    ChartClass = ci.get_chart_class()        # <-- their monkey-patch, now on pylightcharts
    print('ChartClass module      :', ChartClass.__module__)

    chart = ChartClass(None, 1.0, 1.0, False, False)
    view = chart.get_webview()
    view.resize(1200, 700)
    view.setWindowTitle('miniqt chart_interface.py via pylightcharts')
    view.show()

    df = make_data()
    chart.set(df)
    chart.layout(background_color='#0b0e14', text_color='#d1d4dc')
    chart.candle_style(up_color='#26a69a', down_color='#ef5350', border_visible=False)
    chart.grid(color='rgba(42,46,57,0.6)')
    chart.precision(2)

    ma20 = chart.create_line('ma20', color='#FF9800', width=2)
    ma20.set(df[['time', 'ma20']])

    doomed = chart.create_line('ma20', color='#888888', width=1)
    doomed.set(df[['time', 'ma20']])
    doomed.delete()                          # exercises their setattr(Line, 'delete', ...)

    chart.watermark('miniqt + pylightcharts')
    chart.horizontal_line(float(df['close'].iloc[-1]), color='#00e676',
                          style='dashed', text='last')
    chart.marker(df['time'].iloc[60], position='below', shape='arrow_up',
                 color='#26a69a', text='BUY')

    chart.events.watch_cursor_change()       # their setattr(Events, ...) + our JSEmitter
    print('events patch           : ok')

    def save_png(data_url):
        if data_url and ',' in data_url:
            OUT.write_bytes(base64.b64decode(data_url.split(',', 1)[1]))
            print('screenshot             :', OUT)
        print('RESULT_OK')
        app.quit()

    def on_loaded(_=None):
        def probe():
            view.page().runJavaScript('document.querySelectorAll("canvas").length',
                                      lambda n: print('canvases               :', n))
            view.page().runJavaScript(
                f'{chart.id}.chart.takeScreenshot().toDataURL()', save_png)
        QTimer.singleShot(2500, probe)

    view.page().loadFinished.connect(on_loaded)
    QTimer.singleShot(45_000, app.quit)
    app.exec()


if __name__ == '__main__':
    main()
