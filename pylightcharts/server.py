"""A tiny stdlib HTTP + SSE server: live charts in a normal browser tab.

`BrowserChart(live=True)` uses this. There is deliberately **no dependency**:
`http.server` serves the page, a Server-Sent-Events stream carries the scripts
Python would otherwise send to a webview, and widget callbacks come back as a
`POST`. The page evaluates each streamed script with `eval`, so the same
`Window`/bridge code drives it unchanged:

    Python                        browser
    ------                        -------
    chart.update(row)  --push-->  eval("Lib.invoke(...)")
    window.handlers    <-POST---  window.callbackFunction("id_~_value")

Only *write* calls work: a browser tab has no synchronous reply channel, so the
readback APIs (`chart_options()`, `screenshot()`, `constants.verify()`, ...)
are
unavailable - exactly like `HeadlessChart`.
"""
from __future__ import annotations

import json
import queue
import secrets
import threading
import time
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

__all__ = ['LiveServer']

#: how long an idle SSE connection waits before sending a keep-alive comment
KEEPALIVE_SECONDS = 15.0

#: scripts a slow tab may fall behind by before it is dropped
CLIENT_QUEUE_SIZE = 2000

#: how long one `/poll` request waits for something to send
POLL_WAIT_SECONDS = 20.0

#: at most this many long-polling clients (the idlest one is dropped)
MAX_POLL_CLIENTS = 32

#: hosts that are only reachable from this machine
LOCAL_HOSTS = ('127.0.0.1', 'localhost', '::1')


class _Client:
    """One connected browser tab."""

    def __init__(self, client_id: str = '') -> None:
        self.id = client_id or secrets.token_hex(4)
        self.queue: 'queue.Queue[str]' = queue.Queue(CLIENT_QUEUE_SIZE)
        self.dropped = False
        self.last_seen = 0.0

    def touch(self) -> None:
        self.last_seen = time.monotonic()

    def drain(self, timeout: float) -> List[str]:
        """Everything queued so far, waiting up to `timeout` for the first."""
        try:
            first = self.queue.get(timeout=timeout)
        except queue.Empty:
            return []
        scripts = [first]
        while True:
            try:
                scripts.append(self.queue.get_nowait())
            except queue.Empty:
                return scripts

    def send(self, script: str) -> None:
        if self.dropped:
            return
        try:
            self.queue.put_nowait(script)
        except queue.Full:
            # the tab stopped reading (backgrounded, paused): don't block the
            # chart's producer, just stop feeding it
            self.dropped = True


class LiveServer:
    """Serve one chart page and stream its scripts to every open tab.

    :param page: returns the HTML for `GET /` (the chart's `to_html()`, so a
        manual refresh shows the chart as built).
    :param on_callback: receives the raw `name_~_args` message posted by the page
        (dispatch it with `pylightcharts.util.parse_event_message`).
    :param on_connect: called for every new tab; its scripts are pushed to
        that tab, which is how a refresh gets the current data again.
    """

    def __init__(self, page: Callable[[], str],
                 on_callback: Callable[[str], None],
                 on_connect: Optional[Callable[[], List[str]]] = None,
                 host: str = '127.0.0.1', port: int = 0,
                 fallback: bool = True, run: str = '',
                 token: Optional[str] = None) -> None:
        self._page = page
        self._on_callback = on_callback
        self._on_connect = on_connect
        self._host = host
        self._port = port
        #: when a *fixed* port is busy, take a free one instead of failing
        self._fallback = fallback
        #: identifies this server instance: a page from an older run (same fixed
        #: port, stale handle names) must not apply its scripts
        self.run = run
        #: when set, every request has to carry it (`?token=` or `X-Auth-Token`)
        self.token = token
        if token is None and host not in LOCAL_HOSTS:
            warnings.warn(
                f'serving the live chart on {host} without a token: whoever can '
                'reach the port can watch it and run its widget callbacks in '
                'this process. Pass token=... (or keep host=127.0.0.1).',
                stacklevel=2)
        self._poll_clients: Dict[str, _Client] = {}
        self._clients: List[_Client] = []
        self._lock = threading.Lock()
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ state
    @property
    def url(self) -> str:
        """The URL the page is served at (empty before :meth:`start`)."""
        if self._httpd is None:
            return ''
        host = self._httpd.server_address[0]
        if host in ('0.0.0.0', ''):
            host = '127.0.0.1'
        return f'http://{host}:{self._httpd.server_address[1]}/'

    @property
    def clients(self) -> int:
        """How many tabs are connected right now."""
        with self._lock:
            return len(self._clients)

    @property
    def running(self) -> bool:
        return self._httpd is not None

    # ---------------------------------------------------------------- control
    def start(self) -> str:
        """Bind the socket and serve in a background thread; returns the URL.

        A busy *fixed* port falls back to a free one (with a warning) when
        `fallback` is set - `port=0` always picks a free port anyway.
        """
        if self._httpd is not None:
            return self.url
        try:
            server = self._make_server(self._port)
        except OSError as error:
            if not self._fallback or self._port == 0:
                raise
            warnings.warn(
                f'port {self._port} is busy ({error.strerror or error}); '
                'serving on a free port instead - use `chart.url`',
                stacklevel=2)
            server = self._make_server(0)
        self._httpd = server
        self._thread = threading.Thread(target=server.serve_forever,
                                        name='pylightcharts-live',
                                        daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        """Shut the server down (connected tabs see the stream end)."""
        server, self._httpd = self._httpd, None
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        with self._lock:
            self._clients.clear()

    def push(self, script: str) -> None:
        """Stream one JS statement to every connected tab (both transports)."""
        with self._lock:
            clients = list(self._clients) + list(self._poll_clients.values())
        for client in clients:
            client.send(script)

    # ------------------------------------------------------------------ auth
    def authorized(self, path: str, headers) -> bool:
        """True when the request may proceed (no token configured = open)."""
        if not self.token:
            return True
        query = parse_qs(urlparse(path).query)
        if self.token in query.get('token', []):
            return True
        return (headers.get('X-Auth-Token') or '') == self.token

    # ------------------------------------------------------- poll transport
    def client(self, client_id: str = '') -> _Client:
        """The long-polling client for `client_id`, created (and greeted) once.

        A browser that cannot use Server-Sent Events polls `/poll`; the scripts
        are buffered per client, so nothing is lost between two requests.
        """
        if client_id and client_id in self._poll_clients:
            client = self._poll_clients[client_id]
            client.touch()
            return client
        if len(self._poll_clients) >= MAX_POLL_CLIENTS:
            idle = min(self._poll_clients.values(), key=lambda c: c.last_seen)
            self._poll_clients.pop(idle.id, None)
        client = _Client()
        client.touch()
        self._poll_clients[client.id] = client
        for script in self._greeting():
            client.send(script)
        return client

    # ----------------------------------------------------------------- server
    def _make_server(self, port: int) -> ThreadingHTTPServer:
        handler = _make_handler(self)
        server = ThreadingHTTPServer((self._host, port), handler)
        server.daemon_threads = True
        return server

    # used by the request handler
    def _register(self) -> _Client:
        client = _Client()
        with self._lock:
            self._clients.append(client)
        return client

    def _unregister(self, client: _Client) -> None:
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)

    def _greeting(self) -> List[str]:
        if self._on_connect is None:
            return []
        try:
            return list(self._on_connect())
        except Exception:                       # a broken resync must not kill
            return []                           # the tab


def _make_handler(server: LiveServer):
    """Build the request handler class bound to one :class:`LiveServer`."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        server_version = 'pylightcharts'

        # ------------------------------------------------------------ routes
        def do_GET(self) -> None:                       # noqa: N802
            path = self.path.split('?', 1)[0]
            if not server.authorized(self.path, self.headers):
                self._deny()
            elif path in ('/', '/index.html'):
                self._page()
            elif path == '/events':
                self._events()
            elif path == '/poll':
                self._poll()
            else:
                self.send_error(404, 'not found')

        def do_POST(self) -> None:                      # noqa: N802
            if not server.authorized(self.path, self.headers):
                self._deny()
                return
            if self.path.split('?', 1)[0] != '/callback':
                self.send_error(404, 'not found')
                return
            length = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(length).decode('utf-8', 'replace')
            try:
                server._on_callback(body)
            finally:
                self.send_response(204)
                self._cors()
                self.send_header('Content-Length', '0')
                self.end_headers()

        def do_OPTIONS(self) -> None:                   # noqa: N802
            self.send_response(204)
            self._cors()
            self.send_header('Content-Length', '0')
            self.end_headers()

        # ----------------------------------------------------------- helpers
        def _cors(self) -> None:
            # the page may be embedded in a sandboxed/opaque-origin iframe
            # (e.g. a Jupyter output frame): allow the callbacks/SSE through
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.send_header('Access-Control-Allow-Methods',
                             'GET, POST, OPTIONS')

        def _page(self) -> None:
            body = server._page().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            # a live page must never be cached: it is regenerated per request
            self.send_header('Cache-Control', 'no-store')
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _deny(self) -> None:
            body = b'missing or wrong token\n'
            self.send_response(403)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _poll(self) -> None:
            """Long-polling: this client's queued scripts, or an empty list."""
            query = parse_qs(urlparse(self.path).query)
            client = server.client((query.get('client') or [''])[0])
            scripts = client.drain(POLL_WAIT_SECONDS)
            payload = {'client': client.id, 'scripts': [
                {'run': server.run, 'script': script} for script in scripts]}
            body = json.dumps(payload).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type',
                             'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _events(self) -> None:
            client = server._register()
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Connection', 'keep-alive')
                self._cors()
                self.end_headers()
                for script in server._greeting():
                    if not self._event(script):
                        return
                while True:
                    try:
                        script = client.queue.get(timeout=KEEPALIVE_SECONDS)
                    except queue.Empty:
                        if not self._comment('keep-alive'):
                            return
                        continue
                    if not self._event(script):
                        return
            except (BrokenPipeError, ConnectionResetError,
                    ConnectionAbortedError, ValueError):
                return
            finally:
                server._unregister(client)

        def _event(self, script: str) -> bool:
            # multi-line scripts are fine in SSE: the payload is JSON encoded,
            # tagged with the run so a stale tab can notice and stop
            payload = {'run': server.run, 'script': script}
            return self._write(f'data: {json.dumps(payload)}\n\n')

        def _comment(self, text: str) -> bool:
            return self._write(f': {text}\n\n')

        def _write(self, payload: str) -> bool:
            try:
                self.wfile.write(payload.encode('utf-8'))
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError,
                    ConnectionAbortedError, ValueError):
                return False

        def log_message(self, *args) -> None:           # keep the console clean
            pass

        def log_error(self, *args) -> None:             # e.g. a tab that went away
            pass

    return Handler
