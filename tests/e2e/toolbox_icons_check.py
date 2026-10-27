"""Every drawing-tool button must render a visible icon.

The icons are inline SVG that the toolbox paints by setting `fill` on the group.
An icon whose paths are all `fill="none"` therefore renders **completely blank**
unless it also asks for `stroke` - which is exactly what happened to the Gann fan
(and to the Fibonacci-extension polyline). The tool was there and clickable, it
just had no picture.

This drives the real toolbox offscreen and asks the browser which shapes are
actually painted, so a blank icon fails instead of being noticed by eye.

    python tests/e2e/toolbox_icons_check.py
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

#: the Gann fan is 9 rays from one point, plus the origin dot
GANN_SHAPES = 10


def watchdog():
    time.sleep(120)
    print('WATCHDOG: timeout', flush=True)
    os._exit(2)


def make_frame(rows=ROWS) -> pd.DataFrame:
    rng = np.random.default_rng(41)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': rng.integers(1_000, 6_000, rows),
    })


# Ask the browser for each button's shapes and whether each one is painted.
# `getComputedStyle` resolves `stroke="currentColor"`, so a shape that only looks
# coloured because of inheritance still reports a real colour here.
PROBE = '''
(function () {
    const buttons = Array.from(document.querySelectorAll('.toolbox-button'));
    return JSON.stringify(buttons.map(function (button, index) {
        const svg = button.querySelector('svg');
        const shapes = svg ? Array.from(svg.querySelectorAll('path,rect,circle,polygon,line')) : [];
        let painted = 0;
        let inked = 0;
        shapes.forEach(function (shape) {
            const style = getComputedStyle(shape);
            // a resolved colour can still be fully transparent - don't count that
            const visible = (colour) => !!colour && colour !== 'none' &&
                colour !== 'transparent' && !/rgba\(0, 0, 0, 0\)/.test(colour);
            const hasPaint = visible(style.fill) || visible(style.stroke);
            let box = {width: 0, height: 0};
            try { box = shape.getBBox(); } catch (error) { /* detached */ }
            if (hasPaint && box.width + box.height > 0) painted += 1;
            if (box.width + box.height > 0) inked += 1;
        });
        return {
            index: index,
            title: button.getAttribute('title') || '',
            shapes: shapes.length,
            painted: painted,
            inked: inked,
            fill: svg ? getComputedStyle(svg.querySelector('g')).fill : null,
            stroke: shapes.length ? getComputedStyle(shapes[shapes.length - 1]).stroke : null,
        };
    }));
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

    chart = QtChart(None, 1.0, 1.0, False, True)              # toolbox=True
    view = chart.get_webview()
    view.resize(1000, 700)
    chart.set(make_frame())

    failures = []

    def check(raw):
        buttons = json.loads(raw)
        print(f'drawing tools: {len(buttons)}')
        for button in buttons:
            flag = '' if button['painted'] else '   <<< NO VISIBLE ICON'
            detail = f"  stroke={button['stroke']}" if button['index'] == len(buttons) - 1 else ''
            print(f"  {button['index']:>2} shapes={button['shapes']:>2} "
                  f"painted={button['painted']:>2} inked={button['inked']:>2}{flag}{detail}")
            if button['painted'] == 0:
                failures.append(f"tool #{button['index']} has no painted shape")

        if not buttons:
            failures.append('the toolbox rendered no buttons')

        # the last tool is the Gann fan: 9 rays plus the origin dot
        last = buttons[-1] if buttons else None
        if last is not None and last['shapes'] != GANN_SHAPES:
            failures.append(f'expected the Gann fan to have {GANN_SHAPES} shapes, '
                            f"got {last['shapes']}")

        if failures:
            print('RESULT_ERROR: ' + '; '.join(failures))
            app.quit()
            return
        print('RESULT_OK')
        app.quit()

    def on_loaded(_=None):
        # `toolbox=True` already creates the toolbox in JS; creating a second
        # ToolBox here would render two toolbars and double the button list.
        QTimer.singleShot(1500, lambda: view.page().runJavaScript(PROBE, check))

    view.page().loadFinished.connect(on_loaded)
    QTimer.singleShot(60_000, app.quit)
    app.exec()
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
