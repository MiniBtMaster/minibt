"""Drawings must stay anchored to the same *time* when the timeframe changes.

The renderer places a point with `timeScale().logicalToCoordinate(point.logical)`,
and `logical` is a bar index - it is only valid for the timeframe it was saved in.
Storage keeps both (`{time, logical, price}`), so the fix is to recompute `logical`
from `time` for the current bars. `timeToCoordinate()` alone is not enough: it only
resolves times that are exactly a bar, and an intraday time never matches a daily
bar. The old code fell back to `|| 0`, which threw those points to the far left -
hence "the drawing jumps when I switch timeframe".

`timeToLogical()` now interpolates between the neighbouring bars instead.

    python tests/e2e/drawing_timeframe_check.py
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

DAYS = 600
HOURS = DAYS * 24

#: an hourly bar in the middle of the range, at 13:00 - deliberately *not* a daily
#: bar time, so restoring it on the daily chart has to interpolate
HOURLY_INDEX = 300 * 24 + 13
EXPECTED_DAILY_LOGICAL = 300 + 13 / 24


def watchdog():
    time.sleep(180)
    print('WATCHDOG: timeout', flush=True)
    os._exit(2)


def make_frame(times) -> pd.DataFrame:
    rows = len(times)
    rng = np.random.default_rng(53)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': times, 'open': close, 'high': close + 1,
        'low': close - 1, 'close': close,
        'volume': rng.integers(1_000, 6_000, rows),
    })


# --- JS steps -----------------------------------------------------------------

CAPTURE_POINT = '''
(function () {
    const chartObj = %(id)s;
    const series = chartObj.series;
    const index = %(index)s;
    const time = series.dataByIndex(index).time;
    const end = series.dataByIndex(index + 40).time;
    window.__saved_drawing = [
        {
            type: 'TrendLine',
            points: [{time: time, logical: index, price: 100},
                     {time: end, logical: index + 40, price: 110}],
            options: {},
        },
        {
            // a box drawn with clicks that landed *between* bars: Lightweight Charts
            // gives param.time === undefined there, so the saved points have no time
            // anchor and their bar indices are only meaningful on the hourly chart
            type: 'Box',
            points: [{time: null, logical: 2000, price: 100},
                     {time: null, logical: 2100, price: 105}],
            options: {},
        },
    ];
    return JSON.stringify({times: series.data().length, grabbedTime: time,
                           logical: index});
})()
'''

RESTORE_AND_MEASURE = '''
(function () {
    const chartObj = %(id)s;
    const series = chartObj.series;
    chartObj.toolBox.loadDrawings(window.__saved_drawing);
    const tool = chartObj.toolBox._drawingTool;
    const point = tool.drawings[0].points[0];
    const near = series.dataByIndex(Math.round(point.logical));
    const box = tool.drawings[1];
    return JSON.stringify({
        bars: series.data().length,
        logical: point.logical,
        time: point.time,
        barAtLogical: near ? near.time : null,
        drawings: tool.drawings.length,
        boxLogicals: box ? box.points.map((p) => p.logical) : null,
    });
})()
'''


def main() -> int:
    threading.Thread(target=watchdog, daemon=True).start()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineWidgets import QWebEngineView       # noqa: F401 - before QApplication

    from pylightcharts.qt import prepare_qt
    from pylightcharts.widgets import QtChart

    prepare_qt()
    app = QApplication(sys.argv)

    hourly = make_frame(pd.date_range('2024-01-01', periods=HOURS, freq='h'))
    daily = make_frame(pd.date_range('2024-01-01', periods=DAYS, freq='D'))

    chart = QtChart(None, 1.0, 1.0, False, True)              # toolbox=True
    view = chart.get_webview()
    view.resize(1100, 700)
    chart.set(hourly)

    state = {}
    failures = []

    def run(script, then):
        view.page().runJavaScript(script, then)

    # --- 1) on the hourly chart, remember the time of an intraday bar ---------
    def step_capture(_=None):
        script = CAPTURE_POINT % {'id': chart.id, 'index': HOURLY_INDEX}
        QTimer.singleShot(1200, lambda: run(script, after_capture))

    def after_capture(raw):
        state['captured'] = json.loads(raw)
        print(f"  hourly chart        : {state['captured']['times']} bars, "
              f"grabbed index {state['captured']['logical']} -> {state['captured']['grabbedTime']}")
        chart.set(daily)                                      # switch timeframe
        QTimer.singleShot(1500, lambda: run(RESTORE_AND_MEASURE % {'id': chart.id},
                                            after_restore_daily))

    # --- 2) restore on the daily chart: the point must land on the same date --
    def after_restore_daily(raw):
        result = json.loads(raw)
        state['daily'] = result
        print(f"  after daily switch  : {result['bars']} bars, logical="
              f"{result['logical']:.4f}, time={result['time']}, "
              f"barAtLogical={result['barAtLogical']}")

        chart.set(hourly)
        QTimer.singleShot(1500, lambda: run(RESTORE_AND_MEASURE % {'id': chart.id},
                                            after_restore_hourly))

    # --- 3) and back on the hourly chart it lands on the same bar -------------
    def after_restore_hourly(raw):
        result = json.loads(raw)
        state['hourly'] = result
        print(f"  back to hourly      : {result['bars']} bars, logical="
              f"{result['logical']:.4f}, time={result['time']}")
        check_and_finish()

    def check_and_finish():
        captured = state['captured']
        daily_result = state['daily']
        hourly_result = state['hourly']

        # both drawings survived both switches
        for label, result in (('daily', daily_result), ('hourly', hourly_result)):
            if result['drawings'] != 2:
                failures.append(f'{label}: a drawing was lost while switching')

        # the box has no time anchor, so its bar indices come from the hourly chart:
        # they must be brought back into view, and must keep their shape instead of
        # collapsing onto one bar
        for label, result in (('daily', daily_result), ('hourly', hourly_result)):
            logicals = result.get('boxLogicals') or []
            if len(logicals) != 2:
                failures.append(f'{label}: the box is missing')
                continue
            bars = result['bars']
            if not all(0 <= value <= bars - 1 for value in logicals):
                failures.append(
                    f'{label}: the box is outside the chart (logical={logicals}, '
                    f'bars={bars}) - this is the "drawing disappears" case')
            if round(logicals[1] - logicals[0]) != 100:
                failures.append(
                    f'{label}: the box lost its shape (width={logicals[1] - logicals[0]}, '
                    f'expected 100)')

        # daily: an intraday time must interpolate to the matching day, not jump to 0
        if abs(daily_result['logical'] - EXPECTED_DAILY_LOGICAL) > 0.05:
            failures.append(
                f"daily logical should be ~{EXPECTED_DAILY_LOGICAL:.4f} "
                f"(the same date), got {daily_result['logical']:.4f}")
        if daily_result['logical'] < 1:
            failures.append('the drawing jumped to the start of the chart')
        if abs(daily_result['barAtLogical'] - captured['grabbedTime']) > 86400:
            failures.append('the restored point is not on the same day')

        # hourly: the exact bar is back
        if abs(hourly_result['logical'] - HOURLY_INDEX) > 1:
            failures.append(
                f"hourly logical should be ~{HOURLY_INDEX}, got {hourly_result['logical']:.4f}")

        print('RESULT_ERROR: ' + '; '.join(failures) if failures else 'RESULT_OK')
        app.quit()

    view.page().loadFinished.connect(step_capture)
    QTimer.singleShot(90_000, app.quit)
    app.exec()
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
