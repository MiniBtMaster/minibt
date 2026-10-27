"""Integration check: minibt's chart windows, rendered through pylightcharts.

`minibt/strategy/light_chart.py` (live charts) and
`minibt/strategy/light_chart_replay.py` (replay **and** the static backtest
display) used to import `lightweight_charts` and monkey-patch its Qt globals to
force PyQt6.  They now import `pylightcharts` and let `prepare_qt('PyQt6')` pick
the binding, so this check drives the **real entry points** - `Bt().run()` with
``gui=Gui.LightChart``, exactly like the tutorials - and asserts the windows
really end up drawing candles and indicator series.

======================================  ==========================================
``tutorials/strategies/cci.py``           static backtest -> ``light_chart_replay``
``tutorials/basic/strategy_replay.py``        replay          -> ``light_chart_replay``
``tutorials/basic/live_chart.py``             live            -> ``light_chart`` (see below)
======================================  ==========================================

Only ``MainWindow.show`` is wrapped, so the windows are built by minibt's own
code with minibt's own data; the check then screenshots each one, asserts the
chart holds candles plus indicator series, and quits the event loop that
``main()`` started.

The live chart cannot be driven without a tqsdk account: ``Bt(live=True).run()``
asserts on ``Bt._api``, the strategy asks that api for its account and position,
and the window reads the ``tq_object`` that only a live TqApi keeps updating in
place.  The ``live`` mode here therefore checks what can be checked without one -
that ``minibt/strategy/light_chart.py`` imported pylightcharts and that its chart
class is pylightcharts' ``QtChart`` - and the window itself is verified against a
real account.

    python tests/e2e/minibt_charts.py                 # all three, one per process
    python tests/e2e/minibt_charts.py --mode replay   # just one (easier to debug)

The repository's own minibt must be the one that gets imported::

    PYTHONPATH=/path/to/pylightcharts python tests/e2e/minibt_charts.py

otherwise a minibt installed in site-packages answers instead.  Writes
``minibt_<mode>.png`` next to this file and prints ``RESULT_OK``.  The
screenshots are best effort - in the static window the web view holding the
chart is not the one on top, so it photographs as a sliver - the verdict comes
from the candles/series/canvas counts.
"""
from __future__ import annotations

import argparse
import base64
import os
import pathlib
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
MODES = ('static', 'live', 'replay')

# QtWebEngine needs a platform plugin even when nobody is watching.
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def watchdog(seconds: int = 150):
    time.sleep(seconds)
    print('WATCHDOG: timeout', flush=True)
    os._exit(2)


class StubApi:
    """Just enough of tqsdk's ``TqApi``

    Kept for reference: driving the *live* window from this check would need a
    stub like this one plus a ``tq_object`` fixture, which is a lot of scaffolding
    to exercise a window that a real account covers properly.  The live mode below
    therefore stops at the import boundary and the window is verified against a
    real tqsdk account.
    """

    def wait_update(self, deadline=None):
        return False

    def close(self):
        pass


def first_chart(window):
    """The chart object inside whichever main window minibt built."""
    for attribute in ('light_chart_window', 'replay_window'):
        holder = getattr(window, attribute, None)
        if holder is None:
            continue
        if getattr(holder, 'chart_window', None) is not None:
            return holder.chart_window
        charts = getattr(holder, 'all_charts', None)
        if charts:
            return list(charts.values())[0]
    raise AssertionError('no chart found on the window')


def run_mode(mode: str) -> int:
    """Run one real minibt entry point and assert the window rendered."""
    threading.Thread(target=watchdog, daemon=True).start()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'tutorials'))
    sys.path.insert(0, str(ROOT / 'tutorials' / 'strategy'))

    import minibt
    assert pathlib.Path(minibt.__file__).resolve().parent == ROOT / 'minibt', (
        f'imported minibt from {minibt.__file__}; put the repository on '
        f'PYTHONPATH so the edited copy is the one under test')

    # The whole point of the migration: this runs *before* QApplication and it
    # makes pylightcharts - not lightweight_charts - the loaded library.
    from pylightcharts.qt import prepare_qt
    prepare_qt('PyQt6')

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    from minibt import Bt, Gui
    from minibt.strategy import light_chart, light_chart_replay

    print(f'mode                : {mode}')
    print(f'library             : {light_chart.util.__name__}')
    print(f'abstract            : {light_chart.AbstractChart.__module__}')
    assert light_chart.util.__name__.startswith('pylightcharts'), \
        'minibt is still importing lightweight_charts'
    assert light_chart_replay.util.__name__.startswith('pylightcharts')

    if mode == 'live':
        # ``light_chart`` builds the live window, and driving that window needs a
        # tqsdk account: ``Bt(live=True).run()`` asserts on ``Bt._api``, asks it
        # for the account/position, and the chart reads the ``tq_object`` that
        # only a live TqApi keeps updating in place.  Without an account this
        # mode checks everything up to the feed - that the module imported
        # pylightcharts and that its chart class is pylightcharts' one - and the
        # window itself is verified against a real account.
        ChartClass = light_chart.get_chart_class()
        print(f'chart class         : {ChartClass.__name__}')
        print(f'chart module        : {ChartClass.__module__}')
        ok = ChartClass.__module__.startswith('pylightcharts')
        print('RESULT_OK' if ok else 'RESULT_FAIL', flush=True)
        return 0 if ok else 1

    from cci import CCIStrategy
    window_module = light_chart_replay

    def on_window_ready(window):
        """Called once the real ``MainWindow`` has been shown, from the event loop."""
        chart = first_chart(window)
        view = chart.get_webview()
        print(f'chart class         : {type(chart).__name__}')
        state = {'canvases': 0, 'attempts': 0}

        def finish():
            inner = chart.chart                      # the pylightcharts QtChart
            candles = len(getattr(inner, 'candle_data', []))
            lines = len(getattr(inner, '_lines', []))
            print(f'candles             : {candles}')
            print(f'indicator series    : {lines}')
            print(f'canvases            : {state["canvases"]}')
            ok = state['canvases'] > 0 and candles > 0 and lines > 0
            print('RESULT_OK' if ok else 'RESULT_FAIL', flush=True)
            # Leave through the front door so ``main()`` unwinds normally, then
            # hard-exit: minibt's own teardown (api.close + Qt destruction of
            # three web views) can abort natively, and that must not decide this
            # check's verdict now that everything has been asserted.
            app.quit()
            QTimer.singleShot(1500, lambda: os._exit(0 if ok else 1))

        def on_screenshot(data_url):
            raw = b''
            if data_url and ',' in data_url:
                raw = base64.b64decode(data_url.split(',', 1)[1])
            # A chart that has not been laid out yet photographs as a few dozen
            # pixels of background; keep asking until it is worth saving.  The
            # display-only window in particular stacks its web views, so the
            # first frame can arrive before the stack gives it a size.
            state['attempts'] += 1
            if len(raw) < 5000 and state['attempts'] < 10:
                QTimer.singleShot(1000, lambda: view.page().runJavaScript(
                    'document.querySelectorAll("canvas").length', probe))
                return
            if raw and len(raw) >= 5000:
                out = HERE / f'minibt_{mode}.png'
                out.write_bytes(raw)
                print(f'screenshot          : {out} ({len(raw)} bytes)')
            elif raw:
                print(f'screenshot          : skipped ({len(raw)} bytes - the chart web '
                      f'view is not the one on top in this mode)')
            QTimer.singleShot(200, finish)

        def probe(canvases):
            state['canvases'] = max(state['canvases'], canvases or 0)
            view.page().runJavaScript(
                f'{chart.id}.chart.takeScreenshot().toDataURL()', on_screenshot)

        def on_loaded(_=None):
            print(f'view visible/size   : {view.isVisible()} '
                  f'{view.width()}x{view.height()}')
            QTimer.singleShot(4000 if mode == 'live' else 2500, lambda: view.page(
            ).runJavaScript('document.querySelectorAll("canvas").length', probe))

        view.page().loadFinished.connect(on_loaded)

    original_show = window_module.MainWindow.show
    captured = {}

    def show_and_capture(self):
        original_show(self)
        captured['window'] = self

    window_module.MainWindow.show = show_and_capture

    def poll_for_window():
        """Wait for minibt to show its window, then probe it from the event loop.

        Calling ``app.exit()`` from inside ``show()`` (i.e. while MainWindow is
        still being constructed) makes Qt tear the window down underneath the
        constructor and the process dies; polling keeps the probe off that
        stack.
        """
        window = captured.get('window')
        if window is None:
            QTimer.singleShot(200, poll_for_window)
            return
        try:
            on_window_ready(window)
        except Exception as error:                    # pragma: no cover - diagnostics
            print(f'PROBE_FAILED: {error!r}')
            os._exit(3)

    QTimer.singleShot(0, poll_for_window)

    if mode == 'static':
        Bt().run(gui=Gui.LightChart)                  # == tutorials/strategies/cci.py
    else:
        Bt(replay=True).run(period_milliseconds=200, gui=Gui.LightChart)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=MODES, default=None)
    args = parser.parse_args()

    if args.mode:
        return run_mode(args.mode)

    # One process per mode: three QWebEngineViews and three sets of timers in a
    # single event loop is asking for flakiness, and a crash in one mode would
    # hide the others.
    settings = ROOT / 'minibt' / 'strategy' / 'setting.json'
    backup = settings.read_bytes() if settings.exists() else None
    results = {}
    try:
        for mode in MODES:
            print(f'===== {mode} =====', flush=True)
            proc = subprocess.run(
                [sys.executable, str(pathlib.Path(__file__).resolve()), '--mode', mode],
                env=os.environ.copy(), capture_output=True, text=True, timeout=200)
            wanted = ('mode', 'library', 'abstract', 'chart class', 'candles',
                      'indicator series', 'canvases', 'screenshot', 'RESULT',
                      'WATCHDOG', 'PROBE_FAILED')
            tail = [line for line in proc.stdout.splitlines()
                    if line.startswith(wanted)]
            print('\n'.join(tail) or proc.stdout[-2000:], flush=True)
            if proc.returncode:
                print(proc.stderr[-2000:], file=sys.stderr)
            results[mode] = proc.returncode == 0 and 'RESULT_OK' in proc.stdout
    finally:
        # the windows save their layout on close; the check should not leave the
        # user's setting.json rearranged
        if backup is not None and settings.read_bytes() != backup:
            settings.write_bytes(backup)
            print('setting.json restored (the window had rewritten it)')

    print()
    for mode, ok in results.items():
        print(f'  {mode:8} {"OK" if ok else "FAILED"}')
    print('ALL_MODES_OK' if all(results.values()) else 'SOME_MODES_FAILED')
    return 0 if all(results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
