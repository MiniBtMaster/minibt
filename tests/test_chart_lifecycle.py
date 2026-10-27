"""Closing the chart window must be noticed.

`pywebview` destroys the WebView2 when the window is closed, and every later
`evaluate_js` on it fails inside pywebview's own error handler:

    [pywebview] Error occurred in script
    System.ObjectDisposedException: 无法访问已释放的对象。对象名:"WebView2"。

The webview lives in a child process, so the parent only learns about the close
through a shared event. These tests drive the real dispatch loop with a fake
`webview` module and assert that:

* the close handler flips `is_alive` and sets the shared event,
* `Chart.is_alive` (a property) follows that event, so ``while chart.is_alive:``
  ends by itself,
* no script is *sent* to a closed window (the fake raises like the real one),
* a round-trip that is already in flight gets an answer instead of waiting.
"""
import queue
import threading
import time
from types import SimpleNamespace

import pytest

from pylightcharts import chart as chart_module


class FakeSignal:
    """pywebview's ``window.events.closed``, which is used as ``+= handler``."""

    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def fire(self):
        for handler in list(self.handlers):
            handler()


class FakeWindow:
    """Raises like WebView2 does once it has been disposed."""

    def __init__(self):
        self.events = SimpleNamespace(loaded=FakeSignal(), closed=FakeSignal())
        self.attempts = []          # every evaluate_js call, successful or not
        self.scripts = []           # the ones that got through
        self.disposed = False

    def evaluate_js(self, script):
        self.attempts.append(script)
        if self.disposed:
            raise RuntimeError(
                'ObjectDisposedException: 无法访问已释放的对象。对象名:"WebView2"。')
        self.scripts.append(script)

    def show(self):
        pass

    def hide(self):
        pass


class FakeWebview:
    def __init__(self):
        self.windows = []

    def create_window(self, *args, **kwargs):
        window = FakeWindow()
        self.windows.append(window)
        return window

    screens = [SimpleNamespace(width=800, height=600)]


@pytest.fixture()
def pywv(monkeypatch):
    """A live PyWV dispatch loop with a fake webview module, run in a thread."""
    fake = FakeWebview()
    monkeypatch.setattr(chart_module, 'webview', fake)

    wv = object.__new__(chart_module.PyWV)          # skip __init__: it runs loop()
    wv.queue = queue.Queue()
    wv.emit_queue = queue.Queue()
    wv.return_queue = queue.Queue()
    wv.loaded_event = threading.Event()
    wv.closed_event = threading.Event()
    wv.is_alive = True
    wv.callback_api = object()
    wv.windows = []

    thread = threading.Thread(target=wv.loop, daemon=True)
    thread.start()
    wv.queue.put(('create_window', (800, 600, None, None, None, False, False, '')))

    deadline = time.time() + 5
    while not wv.windows and time.time() < deadline:
        time.sleep(0.01)
    assert wv.windows, 'the fake window was never created'

    window = fake.windows[0]
    # the real WebView2 is disposed when the window closes
    window.events.closed += lambda: setattr(window, 'disposed', True)
    return wv, window


def wait_for(predicate, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def sent(window):
    """The first line of every script that reached the window.

    The dispatch loop appends ``\n;undefined`` on purpose, so that pywebview
    never serialises a live chart object as the result of the call.
    """
    return [script.split('\n', 1)[0] for script in window.scripts]


def attempted(window):
    return [script.split('\n', 1)[0] for script in window.attempts]


def test_scripts_are_sent_while_the_window_is_open(pywv):
    wv, window = pywv
    wv.queue.put((0, 'chart.update()'))
    assert wait_for(lambda: sent(window) == ['chart.update()'])
    assert wv.is_alive


def test_closing_the_window_stops_the_loop_and_sets_the_event(pywv):
    wv, window = pywv
    assert not wv.closed_event.is_set()

    window.events.closed.fire()

    assert wv.closed_event.is_set(), 'the parent has no other way to notice'
    assert wait_for(lambda: not wv.is_alive)
    assert wv.emit_queue.get(timeout=5) == 'exit'


def test_nothing_is_sent_to_a_closed_window(pywv):
    wv, window = pywv
    wv.queue.put((0, 'before'))
    assert wait_for(lambda: sent(window) == ['before'])

    window.events.closed.fire()
    wv.queue.put((0, 'after-close'))

    # let the loop drain, then check it never even tried
    assert wait_for(lambda: not wv.is_alive)
    time.sleep(0.2)
    assert attempted(window) == ['before'], \
        'evaluate_js on a destroyed WebView2 raises ObjectDisposedException'


def test_a_pending_round_trip_is_answered_after_close(pywv):
    wv, window = pywv
    window.events.closed.fire()
    wv.queue.put((0, '_~_~RETURN~_~_request-1~|~chart.win.someValue'))

    request_id, ok, payload = wv.return_queue.get(timeout=5)
    assert request_id == 'request-1'
    assert ok is False
    assert 'closed' in str(payload)


def test_chart_is_alive_follows_the_shared_event():
    """``while chart.is_alive:`` is how a live loop ends cleanly."""
    chart = object.__new__(chart_module.Chart)
    chart.is_alive = True
    try:
        assert chart.is_alive
        chart_module.Chart.WV.closed_event.set()
        assert not chart.is_alive
        chart_module.Chart.WV.closed_event.clear()
        assert chart.is_alive
        chart.is_alive = False
        assert not chart.is_alive
    finally:
        chart_module.Chart.WV.closed_event.clear()
