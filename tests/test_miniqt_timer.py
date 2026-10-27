"""`TqApiQTimer` must survive a TqApi whose internal loop is already running.

tqsdk refuses `wait_update()` when the TqApi's own event loop is running:

    Exception: 不能在协程中调用 wait_update, 如需在协程中等待业务数据更新请使用 register_update_notify

That happens when a worker thread drives the loop (`get_kline_serial` calls
`wait_update` for a not-yet-initialised serial).  The main-thread QTimer then
raised every 50 ms, flooded `~/.miniqt/crash.log` with thousands of identical
tracebacks and left `update_status_changed` stuck, so quotes/indicators stopped
updating.

`TqApiQTimer` now skips a tick when the loop is running and swallows any other
`wait_update` error instead of letting it escape the Qt slot.

    pytest tests/test_miniqt_timer.py
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--ignore-certificate-errors')

pytest.importorskip('PyQt6')
from PyQt6.QtCore import Qt, QCoreApplication, QObject   # noqa: E402
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
pytest.importorskip('PyQt6.QtWebEngineWidgets')
pytest.importorskip('qfluentwidgets')

try:                                                       # pragma: no cover
    from miniqt.app.view.main_window import TqApiQTimer
except Exception as error:                                 # noqa: BLE001
    pytest.skip(f'main_window needs a working QtWebEngine: {error}',
                allow_module_level=True)

from PyQt6.QtWidgets import QApplication                    # noqa: E402


@pytest.fixture(scope='module')
def app():
    yield QApplication.instance() or QApplication([])


class _Loop:
    def __init__(self):
        self.running = False

    def is_running(self):
        return self.running


class _Api:
    def __init__(self):
        self._loop = _Loop()
        self.calls = 0
        self.raise_error = False

    def wait_update(self, timeout):
        if self.raise_error:
            raise Exception('不能在协程中调用 wait_update, ...')
        self.calls += 1
        return True


class _Main(QObject):
    def __init__(self, api):
        super().__init__()
        self.tq_api = api


def _make_timer(app, api):
    return TqApiQTimer(_Main(api))


def test_skips_tick_while_api_loop_is_running(app):
    api = _Api()
    timer = _make_timer(app, api)
    assert timer.is_update is True

    api._loop.running = True
    before = api.calls
    timer.wait_update()               # used to raise every 50 ms
    assert api.calls == before        # skipped, didn't touch the busy loop
    timer.stop()


def test_swallows_wait_update_errors(app):
    api = _Api()
    timer = _make_timer(app, api)

    api.raise_error = True
    timer.wait_update()               # must not escape the Qt slot
    timer.stop()
