"""The live browser bridge: `pylightcharts.server.LiveServer` + `BrowserChart`.

Everything is stdlib: `http.server` serves the page, Server-Sent Events carry
the scripts Python would send to a webview, and a POST brings widget callbacks
back. No browser is needed for these tests - they talk to the server directly.
"""
import json
import threading
import time
import urllib.request

import pandas as pd
import pytest

from pylightcharts.server import LiveServer


def BrowserChart(**kwargs):
    """Import lazily: `pylightcharts.widgets` binds a Qt binding on import, and
    a PySide6-first process breaks the miniqt (PyQt6) tests collected after
    it."""
    from pylightcharts.widgets import BrowserChart as chart_class
    return chart_class(**kwargs)

ROWS = 40


def _frame(rows: int = ROWS) -> pd.DataFrame:
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5, 'volume': 10,
    })


class StreamReader:
    """Reads `data:` frames from the SSE endpoint in a background thread."""

    def __init__(self, url: str, timeout: float = 8.0):
        self.frames: list = []                  # the scripts, in order
        self.runs: list = []                    # the run token of each frame
        self.error = None
        self._thread = threading.Thread(target=self._read, args=(url, timeout),
                                        daemon=True)
        self._thread.start()

    def _read(self, url: str, timeout: float) -> None:
        try:
            request = urllib.request.Request(url + 'events')
            with urllib.request.urlopen(request, timeout=timeout) as response:
                while True:
                    line = response.readline().decode('utf-8', 'replace').strip()
                    if line.startswith('data: '):
                        payload = json.loads(line[6:])
                        self.runs.append(payload['run'])
                        self.frames.append(payload['script'])
        except Exception as error:              # the test asserts instead
            self.error = error

    def wait_for(self, count: int, timeout: float = 8.0) -> list:
        deadline = time.time() + timeout
        while time.time() < deadline and len(self.frames) < count:
            time.sleep(0.05)
        return self.frames


# --------------------------------------------------------------------------
# the server
# --------------------------------------------------------------------------

def test_live_server_serves_the_page_streams_and_takes_callbacks():
    callbacks = []
    server = LiveServer(lambda: '<html>page</html>', callbacks.append,
                        on_connect=lambda: ['Lib.noop()'], run='test-run')
    url = server.start()
    try:
        assert server.running and server.url == url
        assert url.startswith('http://127.0.0.1:')
        assert urllib.request.urlopen(url, timeout=5).read() == b'<html>page</html>'

        reader = StreamReader(url)
        time.sleep(0.4)                          # let the tab register
        assert server.clients == 1
        server.push('Lib.invoke(1)')
        server.push('Lib.invoke(2)')
        frames = reader.wait_for(3)

        assert frames == ['Lib.noop()', 'Lib.invoke(1)', 'Lib.invoke(2)']
        # every frame is tagged with the run, so a stale tab can detect it
        assert set(reader.runs) == {server.run} and server.run

        request = urllib.request.Request(url + 'callback', data=b'name_~_value',
                                         method='POST')
        assert urllib.request.urlopen(request, timeout=5).status == 204
        time.sleep(0.2)
        assert callbacks == ['name_~_value']
    finally:
        server.stop()
    assert not server.running


def test_live_server_404s_and_survives_disconnects():
    server = LiveServer(lambda: 'page', lambda message: None)
    url = server.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(url + 'nope', timeout=5)
        assert error.value.code == 404

        # a tab that disconnects is dropped, pushing to it stays harmless
        reader = StreamReader(url)
        time.sleep(0.3)
        server.push('a')
        reader.wait_for(1)
        assert server.clients == 1
        server.push('b')
        time.sleep(0.2)
    finally:
        server.stop()


def test_live_server_falls_back_when_the_port_is_busy():
    """A fixed port that is taken must not kill the chart (it warns instead)."""
    import socket
    import warnings

    busy = socket.socket()
    busy.bind(('127.0.0.1', 0))
    busy.listen(1)
    port = busy.getsockname()[1]
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            server = LiveServer(lambda: 'page', lambda message: None, port=port)
            url = server.start()
        try:
            assert str(port) not in url            # a free port was taken
            assert any('busy' in str(w.message) for w in caught)
            assert urllib.request.urlopen(url, timeout=5).status == 200
        finally:
            server.stop()

        strict = LiveServer(lambda: 'page', lambda message: None, port=port,
                            fallback=False)
        with pytest.raises(OSError):
            strict.start()
    finally:
        busy.close()


def test_live_chart_exposes_the_port_options():
    chart = BrowserChart(width=600, height=300, live=True, port=8123,
                         port_fallback=False)
    chart.set(_frame(10))
    try:
        assert chart.port == 8123 and chart.port_fallback is False
        url = chart.show(block=False, open_browser=False)
        assert url.startswith('http://127.0.0.1:')
    finally:
        chart.stop()


def test_live_server_run_token_defaults_to_empty():
    server = LiveServer(lambda: 'page', lambda message: None)
    assert server.run == ''


def test_live_server_requires_its_token():
    """With token=... every request must carry it (`?token=` or the header)."""
    callbacks = []
    server = LiveServer(lambda: 'page', callbacks.append, token='s3cret')
    url = server.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(url, timeout=5)
        assert error.value.code == 403
        assert urllib.request.urlopen(url + '?token=s3cret', timeout=5).status == 200

        request = urllib.request.Request(url + '?token=wrong')
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=5)
        assert error.value.code == 403

        # the header works too (that is what the page uses for callbacks)
        request = urllib.request.Request(
            url + 'callback', data=b'name_~_value', method='POST',
            headers={'X-Auth-Token': 's3cret'})
        assert urllib.request.urlopen(request, timeout=5).status == 204
        time.sleep(0.2)
        assert callbacks == ['name_~_value']

        # ... and a callback without it is refused and never runs
        request = urllib.request.Request(url + 'callback', data=b'nope_~_x',
                                         method='POST')
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=5)
        assert error.value.code == 403
        time.sleep(0.2)
        assert callbacks == ['name_~_value']
    finally:
        server.stop()


def test_live_server_warns_when_exposed_without_a_token():
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        LiveServer(lambda: 'page', lambda message: None, host='0.0.0.0')
    assert any('without a token' in str(w.message) for w in caught)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        LiveServer(lambda: 'page', lambda message: None, host='0.0.0.0',
                   token='s3cret')
    assert not caught


def test_live_server_poll_transport_buffers_scripts():
    """`/poll` is the fallback for environments that cut Server-Sent Events."""
    server = LiveServer(lambda: 'page', lambda message: None,
                        on_connect=lambda: ['Lib.greeting()'], run='r1')
    url = server.start()
    try:
        first = json.loads(urllib.request.urlopen(url + 'poll', timeout=10).read())
        assert first['client'] and first['scripts'] == [
            {'run': 'r1', 'script': 'Lib.greeting()'}]

        # nothing new: the call waits and then returns an empty list
        empty = json.loads(urllib.request.urlopen(
            f"{url}poll?client={first['client']}", timeout=30).read())
        assert empty['scripts'] == []

        # a script queued in the meantime is delivered to that client
        server.push('Lib.update()')
        client = server.client(first['client'])
        scripts = client.drain(5.0)
        assert scripts == ['Lib.update()']
    finally:
        server.stop()


def test_live_page_supports_polling_and_tokens(live):
    page = live._live_page()
    assert 'pylightchartsPoll' in page and "'/poll'" in page
    # the transport can be forced with `?transport=poll` for debugging
    assert "get('transport')" in page and "'poll'" in page
    assert 'X-Auth-Token' in page

    with_token = BrowserChart(width=600, height=300, live=True, token='abc123')
    with_token.set(_frame(10))
    try:
        secured = with_token._live_page()
        assert 'abc123' in secured
        assert 'token=' in secured
    finally:
        with_token.stop()


def test_show_opens_the_page_with_the_token(live, monkeypatch):
    live.token = 'abc123'
    opened = []
    monkeypatch.setattr('webbrowser.open',
                        lambda url, new=0: opened.append(url) or True)

    url = live.show(block=False)

    assert opened[0].startswith(url) and 'token=abc123' in opened[0]
    live.stop()


def test_live_server_url_is_empty_before_start():
    server = LiveServer(lambda: 'page', lambda message: None)
    assert server.url == '' and not server.running and server.clients == 0


# --------------------------------------------------------------------------
# the chart
# --------------------------------------------------------------------------

@pytest.fixture()
def live():
    chart = BrowserChart(width=800, height=420, live=True)
    chart.set(_frame())
    yield chart
    chart.stop()


def test_live_chart_streams_updates(live):
    url = live.show(block=False, open_browser=False)
    assert url.startswith('http://127.0.0.1:')

    reader = StreamReader(url)
    frames = reader.wait_for(2)                  # resync: candles + volume
    assert any('.series.setData(' in script for script in frames)
    assert any('volumeSeries.setData(' in script for script in frames)

    live.create_line(name='close')
    live.update(_frame().iloc[-1])
    # wait for the *content*: frame counts race with the streaming thread
    deadline = time.time() + 8.0
    joined = ''
    while time.time() < deadline:
        joined = '\n'.join(reader.frames)
        if 'createLineSeries' in joined and '.series.update(' in joined:
            break
        time.sleep(0.05)
    assert 'createLineSeries' in joined
    assert '.series.update(' in joined
    live.stop()
    assert live.clients == 0


def test_live_chart_callbacks_reach_python(live):
    seen = []
    live.topbar.button('go', 'Go', func=seen.append)
    url = live.show(block=False, open_browser=False)

    handler_id = live.topbar['go'].id
    request = urllib.request.Request(
        url + 'callback', data=f'{handler_id}_~_clicked'.encode(), method='POST')
    urllib.request.urlopen(request, timeout=5)
    time.sleep(0.3)

    assert seen == [live]                        # the window is the callback arg
    assert live.topbar['go'].value == 'clicked'
    live.stop()


def test_live_chart_does_not_accumulate_scripts(live):
    """Streaming must not grow the page: only the setup is kept in memory."""
    live.show(block=False, open_browser=False)
    before = len(live._html)
    for _ in range(50):
        live.update(_frame().iloc[-1])
    assert len(live._html) == before
    live.stop()


def test_live_chart_resync_can_be_disabled():
    chart = BrowserChart(width=600, height=300, live=True, resync=False)
    chart.set(_frame(10))
    try:
        url = chart.show(block=False, open_browser=False)
        reader = StreamReader(url)
        deadline = time.time() + 5.0              # wait for the tab to register
        while chart.clients == 0 and time.time() < deadline:
            time.sleep(0.05)
        chart.update(_frame(10).iloc[-1])
        frames = reader.wait_for(1)
        # without a resync the very first frame is the live update itself
        assert frames and 'setData' not in frames[0]
    finally:
        chart.stop()


def test_live_page_has_the_bridge_adapter(live):
    page = live._live_page()
    assert 'EventSource' in page and '/callback' in page
    assert 'pylightcharts-live' in page          # the hidden update counter
    assert 'pylightcharts-callback' in page      # the static shim stays
    # a dropped stream must be visible instead of a silently frozen chart
    assert 'pylightcharts-live-lost' in page
    assert 'onerror' in page and 'onopen' in page


def test_live_resync_replays_the_current_data(live):
    """A tab that connects after updates gets the *current* numbers."""
    url = live.show(block=False, open_browser=False)
    reader = StreamReader(url)
    reader.wait_for(2)                          # the first tab's greeting
    live.update(_frame().iloc[-1])

    # a second tab reconnecting is told about the data, not just the shape
    reader2 = StreamReader(url)
    frames = reader2.wait_for(2)
    joined = '\n'.join(frames)
    assert '.series.setData(' in joined and 'volumeSeries.setData(' in joined
    live.stop()


def test_live_page_rejects_frames_from_another_run(live):
    """A tab left over from an earlier run must not apply the new scripts."""
    page = live._live_page()
    assert 'window.pylightchartsRun = ' in page
    assert '%RUN%' not in page                   # substituted
    assert 'payload.run !== window.pylightchartsRun' in page
    assert 'stale tab' in page and 'pylightchartsLive.close()' in page


def test_live_page_shows_a_status_badge(live):
    """The badge is how a stuck tab explains itself (and how you see it live)."""
    page = live._live_page()
    assert 'pylightcharts-live' in page
    assert 'pylightchartsStatus' in page
    for token in ('connected', 'disconnected', 'error'):
        assert token in page
    assert '%STATUS%' not in page                 # the literal was substituted

    hidden = BrowserChart(width=600, height=300, live=True, status=False)
    hidden.set(_frame(10))
    try:
        assert 'display: none' in hidden._live_page()
    finally:
        hidden.stop()


def test_show_opens_a_fresh_tab_but_returns_the_clean_url(live, monkeypatch):
    """A per-run query stops the browser from reusing a tab with an older page."""
    opened = []
    monkeypatch.setattr('webbrowser.open',
                        lambda url, new=0: opened.append(url) or True)

    url = live.show(block=False)

    assert opened and opened[0].startswith(url)
    assert '?run=' in opened[0] and len(opened[0]) > len(url) + 10
    assert url == live.url and '?' not in url
    # the server ignores the query string
    assert urllib.request.urlopen(opened[0], timeout=5).status == 200
    live.stop()


def test_static_browser_chart_never_starts_a_server(tmp_path):
    chart = BrowserChart(width=600, height=300, path=str(tmp_path / 'c.html'))
    chart.set(_frame(10))
    written = chart.show(open_browser=False)
    assert written.endswith('c.html')
    assert chart.url == '' and chart.clients == 0
