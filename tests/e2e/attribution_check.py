"""The TradingView attribution logo is hidden by default and can be opted back in.

Lightweight Charts renders `<a title="Charting by TradingView">` in the bottom-left
of every chart. It reads `layout.attributionLogo` **only while creating a chart**
(its source says the widget "doesn't support dynamically responding to options
changes"), so the switch is creation-time: `pylightcharts.set_attribution_logo`
affects charts made afterwards, subcharts included.

    python tests/e2e/attribution_check.py
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

import numpy as np                                       # noqa: E402
import pandas as pd                                      # noqa: E402

ROWS = 100
COUNT_LOGOS = 'document.querySelectorAll(\'a[title="Charting by TradingView"]\').length'


def watchdog():
    time.sleep(180)
    print('WATCHDOG: timeout', flush=True)
    os._exit(2)


def make_frame(rows=ROWS) -> pd.DataFrame:
    rng = np.random.default_rng(43)
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

    import pylightcharts
    from pylightcharts.qt import prepare_qt
    from pylightcharts.widgets import QtChart

    prepare_qt()
    app = QApplication(sys.argv)
    frame = make_frame()

    counts = {}
    failures = []

    def new_chart() -> QtChart:
        chart = QtChart(None, 1.0, 1.0, False, False)
        view = chart.get_webview()
        view.resize(900, 560)
        chart.set(frame)
        return chart

    def count(view, label, then):
        view.page().runJavaScript(
            COUNT_LOGOS,
            lambda value: (counts.__setitem__(label, value),
                           print(f'  {label:<34} logos={value}'), then()))

    def expect(label, wanted):
        got = counts.get(label)
        if got != wanted:
            failures.append(f'{label}: expected {wanted} logo(s), got {got}')

    # --- default: hidden, main chart and subchart -------------------------
    first = new_chart()

    def phase_default(_=None):
        def with_subchart():
            expect('default (main chart)', 0)
            first.create_subchart(position='bottom', sync=True)
            QTimer.singleShot(900, lambda: count(
                first.get_webview(), 'default (main + subchart)', phase_optin))

        QTimer.singleShot(1200, lambda: count(
            first.get_webview(), 'default (main chart)', with_subchart))

    first.get_webview().page().loadFinished.connect(phase_default)

    # --- opted in: a chart created afterwards shows it --------------------
    def phase_optin():
        expect('default (main + subchart)', 0)
        pylightcharts.set_attribution_logo(True)
        print('  set_attribution_logo(True)')
        second = new_chart()

        def second_ready(_=None):
            def add_subchart():
                expect('opted in (main chart)', 1)
                second.create_subchart(position='bottom', sync=True)
                QTimer.singleShot(900, lambda: count(
                    second.get_webview(), 'opted in (main + subchart)', phase_back_off))

            QTimer.singleShot(1200, lambda: count(
                second.get_webview(), 'opted in (main chart)', add_subchart))

        second.get_webview().page().loadFinished.connect(second_ready)

    # --- turned off again -------------------------------------------------
    def phase_back_off():
        expect('opted in (main + subchart)', 2)
        pylightcharts.set_attribution_logo(False)
        print('  set_attribution_logo(False)')
        third = new_chart()

        def third_ready(_=None):
            QTimer.singleShot(1200, lambda: count(
                third.get_webview(), 'hidden again (main chart)', finish))

        third.get_webview().page().loadFinished.connect(third_ready)

    def finish():
        expect('hidden again (main chart)', 0)
        if failures:
            print('RESULT_ERROR: ' + '; '.join(failures))
        else:
            print('RESULT_OK')
        app.quit()

    QTimer.singleShot(90_000, app.quit)
    app.exec()
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
