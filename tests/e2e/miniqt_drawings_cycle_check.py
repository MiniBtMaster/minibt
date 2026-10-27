"""Drawings are stored per contract **and** cycle, and a cycle switch must not
carry the old cycle's drawings over.

The storage key was already ``"合约|周期"``, but switching a cycle kept the drawings
on the canvas (`set(df, keep_drawings=True)`). Everything the user then did on the
new cycle - drag, recolour, delete, or even just finishing a new line - was saved
under the *new* cycle's key, so the two sets merged. A switch has to clear the
canvas (without touching what is stored) and then load the set that belongs to the
cycle being switched to.

    python tests/e2e/miniqt_drawings_cycle_check.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import threading
import time
import types

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np                                        # noqa: E402
import pandas as pd                                       # noqa: E402

ROWS = 120
MINUTE = 60
FIVE_MINUTES = 300

DRAWING_A = [{'type': 'TrendLine', 'options': {},
              'points': [{'time': 1704067200, 'logical': 10, 'price': 100},
                         {'time': 1704153600, 'logical': 20, 'price': 110}]}]
DRAWING_B = [{'type': 'Box', 'options': {},
              'points': [{'time': 1704067200, 'logical': 30, 'price': 100},
                         {'time': 1704153600, 'logical': 40, 'price': 105}]}]

LOAD_AND_COUNT = '''
(function () {
    const chartObj = %(id)s;
    const box = chartObj.toolBox;
    window.__saves = [];
    if (!window.__hooked) {
        window.__hooked = true;
        const original = window.callbackFunction;
        window.__originalCallback = original;
        window.callbackFunction = (message) => {
            if (message.startsWith('save_drawings')) window.__saves.push(message);
            return original(message);
        };
    }
    window.__saves.length = 0;
    box.loadDrawings(%(drawings)s);
    return JSON.stringify({count: box._drawingTool.drawings.length,
                           saves: window.__saves.length});
})()
'''

SET_DATA_WITHOUT_KEEPING = '''
(function () {
    const chartObj = %(id)s;
    return JSON.stringify({
        count: chartObj.toolBox._drawingTool.drawings.length,
        saves: window.__saves.length,
    });
})()
'''


def watchdog():
    time.sleep(120)
    print('WATCHDOG: timeout', flush=True)
    os._exit(2)


def make_frame(times) -> pd.DataFrame:
    rng = np.random.default_rng(67)
    close = 100 + np.cumsum(rng.standard_normal(len(times)))
    return pd.DataFrame({'time': times, 'open': close, 'high': close + 1,
                         'low': close - 1, 'close': close,
                         'volume': rng.integers(100, 900, len(times))})


# --------------------------------------------------------------------------
# the storage contract, no Qt needed
# --------------------------------------------------------------------------

def check_storage_contract(failures):
    from miniqt.app.common.chart_data import ChartDataManager, drawing_key

    with tempfile.TemporaryDirectory() as folder:
        store = ChartDataManager(str(pathlib.Path(folder) / 'chart_data.json'))

        # one contract, two cycles: separate keys, separate contents
        store.set_drawings(drawing_key('DEMO', MINUTE), DRAWING_A)
        store.set_drawings(drawing_key('DEMO', FIVE_MINUTES), DRAWING_B)

        assert store.get_drawings('DEMO|60') == DRAWING_A
        assert store.get_drawings('DEMO|300') == DRAWING_B
        # a cycle with nothing saved must not fall back to another cycle's set
        assert store.get_drawings('DEMO|900') == []

        # closing and reopening the app restores both sets
        reopened = ChartDataManager(str(pathlib.Path(folder) / 'chart_data.json'))
        if reopened.get_drawings('DEMO|60') != DRAWING_A:
            failures.append('the 1 minute set did not survive a restart')
        if reopened.get_drawings('DEMO|300') != DRAWING_B:
            failures.append('the 5 minute set did not survive a restart')

        # clearing one cycle must leave the other alone
        reopened.clear_drawings('DEMO|60')
        if reopened.get_drawings('DEMO|300') != DRAWING_B:
            failures.append('clearing one cycle wiped another cycle')
    print('  storage keys      : DEMO|60 and DEMO|300 are independent')


def check_tag_and_keep_flag(failures):
    """`_drawing_tag()` follows the chart's cycle and a switch must not keep them."""
    chart_interface = _chart_interface_or_skip()
    Chart = chart_interface.Chart

    holder = types.SimpleNamespace(chart=types.SimpleNamespace(symbol='DEMO', cycle=300))
    tag = chart_interface.CustomToolBox._drawing_tag(holder)
    if tag != 'DEMO|300':
        failures.append(f'_drawing_tag() returned {tag!r}, expected "DEMO|300"')

    # keep_drawings is True normally (same cycle refresh) and False while switching
    holder = types.SimpleNamespace(_switching_cycle=False)
    if Chart._keep_drawings_on_set.__get__(holder) is not True:
        failures.append('a same-cycle reload should keep the drawings')
    holder._switching_cycle = True
    if Chart._keep_drawings_on_set.__get__(holder) is not False:
        failures.append('a cycle switch must not keep the previous cycle drawings')
    print('  tag / keep flag   : DEMO|300, switch clears the canvas')


def _chart_interface_or_skip():
    import pytest

    return pytest.importorskip('miniqt.app.windows.chart_interface')


def check_canvas_cleared_on_switch(failures):
    """The real toolbox: `set(..., keep_drawings=False)` empties the canvas without
    writing anything to storage (that is what makes the switch safe)."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineWidgets import QWebEngineView    # noqa: F401 - before QApplication

    from pylightcharts.qt import prepare_qt
    from pylightcharts.widgets import QtChart

    prepare_qt()
    app = QApplication.instance() or QApplication(sys.argv)

    chart = QtChart(None, 1.0, 1.0, False, True)
    view = chart.get_webview()
    view.resize(900, 600)
    chart.set(make_frame(pd.date_range('2024-01-01', periods=ROWS, freq='min')))

    state = {}

    def step_load():
        view.page().runJavaScript(
            LOAD_AND_COUNT % {'id': chart.id, 'drawings': json.dumps(DRAWING_A)},
            after_load)

    def after_load(raw):
        state['loaded'] = json.loads(raw)
        # switching a cycle: replace the data and drop the canvas drawings
        chart.set(make_frame(pd.date_range('2024-01-01', periods=ROWS, freq='5min')),
                  keep_drawings=False)
        QTimer.singleShot(1200, lambda: view.page().runJavaScript(
            SET_DATA_WITHOUT_KEEPING % {'id': chart.id}, after_switch))

    def after_switch(raw):
        state['after'] = json.loads(raw)
        print(f"  canvas            : {state['loaded']['count']} drawing(s) loaded, "
              f"{state['after']['count']} after switching, "
              f"{state['after']['saves']} save(s) emitted")
        if state['loaded']['count'] != 1:
            failures.append('the drawing was not loaded onto the canvas')
        if state['after']['count'] != 0:
            failures.append('the previous cycle drawings were carried over')
        if state['after']['saves'] != 0:
            failures.append('switching a cycle must not write to storage')
        app.quit()

    view.page().loadFinished.connect(lambda _: QTimer.singleShot(1200, step_load))
    QTimer.singleShot(45_000, app.quit)
    app.exec()


def main() -> int:
    threading.Thread(target=watchdog, daemon=True).start()
    failures = []

    check_storage_contract(failures)
    check_tag_and_keep_flag(failures)
    check_canvas_cleared_on_switch(failures)

    print('RESULT_ERROR: ' + '; '.join(failures) if failures else 'RESULT_OK')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
