"""Regression: the drawing toolbox must survive the host subscribing to events.

The chart keeps a *single* slot per event (`chart.subscribeClick` /
`chart.subscribeCrosshairMove`), and four parties wanted it: the legend, the
drawing tool, the subchart sync and the host application. Whoever subscribed last
won, so miniqt re-registering its own handlers (``events.click += ...``, which
happens after a chart loads and again when an indicator is removed) evicted the
drawing tool: clicks and mouse moves stopped reaching it, and drawing silently
broke.

``Handler`` now owns both slots and fans out. This check drives the real chart
offscreen and asserts the drawing tool is still registered after a host
subscribes.

    python tests/e2e/drawing_events_check.py
"""
from __future__ import annotations

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


PROBE = '''
(function () {
    const h = %(id)s;
    const tool = h.toolBox && h.toolBox._drawingTool;
    return JSON.stringify({
        click: h._clickListeners ? h._clickListeners.length : -1,
        crosshair: h._crosshairListeners ? h._crosshairListeners.length : -1,
        toolClickBound: !!(tool && h._clickListeners &&
                           h._clickListeners.includes(tool._clickHandler)),
        toolMoveBound: !!(tool && h._crosshairListeners &&
                          h._crosshairListeners.includes(tool._moveHandler)),
    });
})()
'''


def main() -> int:
    threading.Thread(target=watchdog, daemon=True).start()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineWidgets import QWebEngineView      # noqa: F401 - before QApplication

    from pylightcharts.qt import prepare_qt
    from pylightcharts.toolbox import ToolBox
    from pylightcharts.widgets import QtChart

    prepare_qt()
    app = QApplication(sys.argv)

    chart = QtChart(None, 1.0, 1.0, False, True)             # toolbox=True
    view = chart.get_webview()
    view.resize(900, 600)
    chart.set(make_frame())

    results = {}
    failures = []

    def record(label, raw):
        results[label] = raw
        print(f'  {label:22} {raw}')

    def probe(label, then=None):
        view.page().runJavaScript(PROBE % {'id': chart.id},
                                  lambda raw: (record(label, raw), then and then()))

    def after_toolbox():
        import json
        state = json.loads(results['with toolbox'])
        if not (state['toolClickBound'] and state['toolMoveBound']):
            failures.append('the drawing tool is not listening to the chart')

        # this is exactly what miniqt does after a chart loads / after an
        # indicator is removed; it used to evict the drawing tool
        chart.events.click += lambda *_: None
        chart.events.crosshair_move += lambda *_: None

        def after_host_subscribe():
            import json
            after = json.loads(results['after host subscribe'])
            if not (after['toolClickBound'] and after['toolMoveBound']):
                failures.append('subscribing the host evicted the drawing tool')
            if after['click'] < state['click'] or after['crosshair'] < state['crosshair']:
                failures.append('the listener count went down')

            # unsubscribing must not remove the drawing tool either
            chart.events.click.unsubscribe()
            chart.events.crosshair_move.unsubscribe()
            probe('after unsubscribe', finish)

        probe('after host subscribe', after_host_subscribe)

    def finish():
        import json
        final = json.loads(results['after unsubscribe'])
        if not (final['toolClickBound'] and final['toolMoveBound']):
            failures.append('unsubscribing the host evicted the drawing tool')
        print('toolbox instance      :', ToolBox.__name__)
        if failures:
            print('RESULT_ERROR: ' + '; '.join(failures))
            app.quit()
            return
        print('RESULT_OK')
        app.quit()

    def on_loaded(_=None):
        ToolBox(chart)                                       # createToolBox() in JS
        QTimer.singleShot(1500, lambda: probe('with toolbox', after_toolbox))

    view.page().loadFinished.connect(on_loaded)
    QTimer.singleShot(60_000, app.quit)
    app.exec()
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
