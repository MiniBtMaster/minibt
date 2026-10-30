"""Every drawing change must be reported to the host so it can persist it.

The toolbox serialises `{type, points, options}` and hands it to the host through
`window.callbackFunction('save_drawings<id>_~_<json>')`. Deletion used to skip that
call: the right-click menu's "Delete Drawing" only removed the primitive, so the
saved copy still had it and the drawing came back the next time the toolbox was
loaded.

Rather than patch each caller, `DrawingTool.delete()` now notifies its owner, so
the context menu, Ctrl+Z and anything added later all persist by construction.

    python tests/e2e/toolbox_drawings_check.py
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

import numpy as np                                       # noqa: E402
import pandas as pd                                      # noqa: E402

ROWS = 120

POINT_A = {'time': 1704067200, 'logical': 1, 'price': 100}
POINT_B = {'time': 1704153600, 'logical': 2, 'price': 110}

PROBE = '''
(function () {
    const box = %(id)s.toolBox;
    const tool = box._drawingTool;
    const captured = [];
    const original = window.callbackFunction;
    window.callbackFunction = (message) => { captured.push(message); };
    const lastPayload = () => {
        const message = captured[captured.length - 1] || '';
        const separator = message.indexOf('_~_');
        return separator === -1 ? null : JSON.parse(message.slice(separator + 3));
    };
    try {
        // restoring is what the host does on startup; it must not echo a save back
        box.loadDrawings(%(drawings)s);
        const result = {
            restoredCount: tool.drawings.length,
            savesAfterLoad: captured.length,
        };

        // 1) changing line colour / style must be reported with the new values
        tool.drawings[0].applyOptions({lineColor: '#123456', lineStyle: 2});
        box.saveDrawings();
        result.optionsPayload = lastPayload();

        // 2) deleting one drawing must be reported (this used to not happen)
        const savesBefore = captured.length;
        tool.delete(tool.drawings[1]);
        result.savesOnDelete = captured.length - savesBefore;
        result.deletePayload = lastPayload();

        // 3) deleting the last one must report an empty list
        tool.delete(tool.drawings[0]);
        result.emptyPayload = lastPayload();
        result.remaining = tool.drawings.length;

        // 4) Ctrl+Z takes the same path
        box.loadDrawings(%(drawings)s);
        const before = captured.length;
        document.dispatchEvent(new KeyboardEvent('keydown',
            {code: 'KeyZ', ctrlKey: true, bubbles: true}));
        result.savesOnUndo = captured.length - before;
        result.countAfterUndo = tool.drawings.length;

        return JSON.stringify(result);
    } finally {
        window.callbackFunction = original;
    }
})()
'''


def watchdog():
    time.sleep(120)
    print('WATCHDOG: timeout', flush=True)
    os._exit(2)


def make_frame(rows=ROWS) -> pd.DataFrame:
    rng = np.random.default_rng(47)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': rng.integers(1_000, 6_000, rows),
    })


def main() -> int:
    threading.Thread(target=watchdog, daemon=True).start()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineWidgets import QWebEngineView       # noqa: F401 - before QApplication

    from pylightcharts.qt import prepare_qt
    from pylightcharts.widgets import QtChart

    prepare_qt()
    app = QApplication(sys.argv)

    chart = QtChart(None, 1.0, 1.0, False, True)              # toolbox=True
    view = chart.get_webview()
    view.resize(1000, 700)
    chart.set(make_frame())

    failures = []

    def check(raw):
        result = json.loads(raw)
        print(f"  restored            : {result['restoredCount']}")
        print(f"  saves while loading : {result['savesAfterLoad']}")
        print(f"  options payload     : {json.dumps(result.get('optionsPayload'))}")
        print(f"  saves on delete     : {result['savesOnDelete']}")
        print(f"  after one delete    : {json.dumps(result.get('deletePayload'))}")
        print(f"  after last delete   : {json.dumps(result.get('emptyPayload'))}")
        print(f"  remaining           : {result['remaining']}")
        print(f"  saves on Ctrl+Z     : {result['savesOnUndo']} -> {result['countAfterUndo']} left")

        if result['restoredCount'] != 2:
            failures.append('the two drawings were not restored')
        if result['savesAfterLoad'] != 0:
            failures.append('loading drawings must not trigger a save')

        options = (result.get('optionsPayload') or [{}])[0].get('options', {})
        if options.get('lineColor') != '#123456':
            failures.append(f"line colour was not reported: {options.get('lineColor')!r}")
        if options.get('lineStyle') != 2:
            failures.append(f"line style was not reported: {options.get('lineStyle')!r}")

        if result['savesOnDelete'] != 1:
            failures.append('deleting a drawing must save exactly once')
        delete_payload = result.get('deletePayload') or []
        if len(delete_payload) != 1:
            failures.append(f'deleting one of two should persist one, got {len(delete_payload)}')
        if any(item.get('type') == 'HorizontalLine' for item in delete_payload):
            failures.append('the deleted drawing is still in the saved payload')

        if result.get('emptyPayload') != []:
            failures.append(f'deleting the last drawing should persist [], '
                            f"got {result.get('emptyPayload')!r}")
        if result['remaining'] != 0:
            failures.append('the toolbox still tracks a deleted drawing')

        if result['savesOnUndo'] != 1 or result['countAfterUndo'] != 1:
            failures.append(f"Ctrl+Z should delete one and save once, got "
                            f"{result['savesOnUndo']} save(s) and "
                            f"{result['countAfterUndo']} left")

        print('RESULT_ERROR: ' + '; '.join(failures) if failures else 'RESULT_OK')
        app.quit()

    def on_loaded(_=None):
        drawings = json.dumps([
            {'type': 'TrendLine', 'points': [POINT_A, POINT_B],
             'options': {'lineColor': '#1E80F0', 'lineStyle': 0}},
            {'type': 'HorizontalLine', 'points': [POINT_A],
             'options': {'lineColor': '#FF0000', 'textColor': '#00FF00'}},
        ])
        script = PROBE % {'id': chart.id, 'drawings': drawings}
        QTimer.singleShot(1500, lambda: view.page().runJavaScript(script, check))

    view.page().loadFinished.connect(on_loaded)
    QTimer.singleShot(60_000, app.quit)
    app.exec()
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
