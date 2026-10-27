"""Drawing persistence, part 2: the JS toolbox must restore every drawing type.

`ToolBox.loadDrawings()` used to handle only 5 of the 13 drawing types the toolbox
offers (Box/TrendLine/HorizontalLine/RayLine/VerticalLine); Fibonacci, Measure,
Channel, Position, Pitchfork, Triangle, FibExtension and GannFan were silently
dropped. It now builds all of them and warns on unknown types.

This drives the real pylightcharts toolbox offscreen and round-trips a drawing of
every type through `loadDrawings` -> `_drawingTool.drawings`.

    python tests/e2e/miniqt_drawings_check.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np                                        # noqa: E402
import pandas as pd                                       # noqa: E402

ROWS = 120

#: 工具箱支持的全部画线类型：(type, 点数)
TWO_POINT = ('TrendLine', 'Box', 'HorizontalLine', 'RayLine', 'VerticalLine',
             'FibonacciRetracement', 'Measure', 'ParallelChannel', 'Position',
             'GannFan')
ONE_POINT = ('HorizontalLine', 'RayLine', 'VerticalLine')
THREE_POINT = ('AndrewsPitchfork', 'Triangle', 'FibonacciExtension')
ALL_TYPES = TWO_POINT + THREE_POINT


def watchdog():
    time.sleep(120)
    print('WATCHDOG: timeout', flush=True)
    os._exit(2)


def make_frame(rows=ROWS) -> pd.DataFrame:
    rng = np.random.default_rng(31)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': rng.integers(1_000, 6_000, rows),
    })


def make_drawings(df: pd.DataFrame) -> list:
    t0 = int(df['time'].iloc[10].timestamp())
    t1 = int(df['time'].iloc[20].timestamp())
    t2 = int(df['time'].iloc[30].timestamp())
    p = lambda t, price: {'time': t, 'logical': 1, 'price': price}
    drawings = []
    for name in ALL_TYPES:
        if name in ONE_POINT:
            points = [p(t0, 100)]
        elif name in THREE_POINT:
            points = [p(t0, 100), p(t1, 110), p(t2, 95)]
        else:
            points = [p(t0, 100), p(t1, 110)]
        drawings.append({'type': name, 'points': points,
                         'options': {'lineColor': '#1E80F0'}})
    return drawings


PROBE = '''
(function () {
    const h = %(id)s;
    const tool = h.toolBox && h.toolBox._drawingTool;
    const types = tool ? tool.drawings.map((d) => d._type) : [];
    return JSON.stringify({hasToolbox: !!h.toolBox, count: types.length, types: types});
})()
'''


def main() -> int:
    threading.Thread(target=watchdog, daemon=True).start()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineWidgets import QWebEngineView      # noqa: F401 - before QApplication

    from pylightcharts.qt import prepare_qt
    from pylightcharts.widgets import QtChart

    prepare_qt()
    app = QApplication(sys.argv)

    chart = QtChart(None, 1.0, 1.0, False, True)              # toolbox=True
    view = chart.get_webview()
    view.resize(1000, 700)
    df = make_frame()
    chart.set(df)

    drawings = make_drawings(df)
    results = {}
    failures = []

    def probe():
        view.page().runJavaScript(PROBE % {'id': chart.id}, after_probe)

    def after_probe(raw):
        state = json.loads(raw)
        print('  hasToolbox:', state['hasToolbox'], '| types restored:',
              len(state['types']), '/', len(ALL_TYPES), flush=True)
        missing = [t for t in ALL_TYPES if t not in state['types']]
        if missing:
            failures.append(f'missing drawing types: {missing}')
        if state['count'] != len(ALL_TYPES):
            failures.append(f"expected {len(ALL_TYPES)} drawings, got {state['count']}")

        if failures:
            print('RESULT_ERROR: ' + '; '.join(failures))
        else:
            print('RESULT_OK')
        app.quit()

    def inject():
        view.page().runJavaScript(
            f'{chart.id}.toolBox.loadDrawings({json.dumps(drawings)}); undefined')
        QTimer.singleShot(1200, probe)

    def on_loaded(_=None):
        # 等 toolbox 的 createToolBox 脚本先跑完，再注入全部 13 种画线
        # （等价于重新打开图表时的 loadDrawings）
        QTimer.singleShot(800, inject)

    view.page().loadFinished.connect(on_loaded)
    QTimer.singleShot(60_000, app.quit)
    app.exec()
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
