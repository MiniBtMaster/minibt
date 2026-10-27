"""浏览器壳：复用 pylightcharts 的传输思路（SSE 下发 + POST 上报），
但只服务 desk 页面，不依赖 Qt。

``desk.run(browser=True)`` 会：

1. 在 ``127.0.0.1:<port>`` 起一个 ``ThreadingHTTPServer``；
2. ``GET /`` → ``pylightcharts/js/desk.html``（注入 transport 配置）
3. ``GET /static/<file>`` → 同目录静态资源（desk.js / desk.css / bundle.js …）
4. ``GET /events`` → **SSE**：Python 每次 ``push`` 就是一条 ``data: <script>``
5. ``POST /callback`` → ``desk_~_<json>``（与 Qt 完全同一条协议 ✓）
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import queue
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from .app import DESK_HTML
from . import protocol as _protocol

#: WebSocket 握手用的固定 GUID（RFC 6455）
WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


def ws_accept(key: str) -> str:
    """``Sec-WebSocket-Key`` → ``Sec-WebSocket-Accept``（纯函数，方便测试）"""
    digest = hashlib.sha1((str(key or '') + WS_GUID).encode('utf-8')).digest()
    return base64.b64encode(digest).decode('ascii')


STATIC_DIR = os.path.dirname(DESK_HTML)
#: 找不到 desk.html 时给一句人话提示（而不是只有 500 ✓）
DESK_HTML_EXISTS = os.path.isfile(DESK_HTML)
_INDEX = 'desk.html'


def _read(path: str) -> bytes:
    with open(path, 'rb') as handle:
        return handle.read()


def _page_bytes(desk) -> bytes:
    """把 transport 配置塞进页面（`window.__deskConfig`）"""
    html = _read(DESK_HTML).decode('utf-8')
    config = json.dumps({'transport': 'sse', 'theme': desk.theme,
                         'title': desk.title,
                         'token': str(getattr(desk, '_web_token', '') or '')},
                        ensure_ascii=False)
    script = f'<script>window.__deskConfig = {config};</script>'
    if '</head>' in html:
        html = html.replace('</head>', script + '</head>', 1)
    else:
        html = script + html
    return html.encode('utf-8')


class _Server(ThreadingHTTPServer):
    """容错版 HTTP 服务：**浏览器关掉 / 刷新**时不要刷 traceback ✓

    `socketserver` 默认把 handler 的异常原样打出来：
    ``ConnectionAbortedError: [WinError 10053] 你的主机中的软件中止了一个
    已建立的连接`` —— 这是**正常现象**（用户关了页面 / SSE 被掐断），
    以前会刷一大段堆栈（用户实测 ✗）。这里静音掉这类连接级异常 ✓
    """

    daemon_threads = True

    #: 这些异常都是「对端没了」，不是 bug
    QUIET = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError,
             ConnectionError, TimeoutError, OSError)

    def handle_error(self, request, client_address) -> None:      # noqa: D401
        import sys as _sys
        error = _sys.exc_info()[1]
        if isinstance(error, self.QUIET):
            return
        super().handle_error(request, client_address)


class _Hub:
    """一条 SSE 连接 = 一个队列（多标签页各自收补丁 ✓）"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: list = []
        self._connected = False

    def add(self) -> 'queue.Queue':
        channel: queue.Queue = queue.Queue(maxsize=2000)
        with self._lock:
            self._clients.append(channel)
            self._connected = True
        return channel

    def count(self) -> int:
        """当前有多少个页面连着（SSE 连接数 ✓）"""
        with self._lock:
            return len(self._clients)

    def ever_connected(self) -> bool:
        """有没有页面连过（免得刚启动就被误判为「已关闭」✗）"""
        with self._lock:
            return self._connected

    def drop(self, channel) -> None:
        with self._lock:
            if channel in self._clients:
                self._clients.remove(channel)

    def broadcast(self, script: str) -> None:
        with self._lock:
            clients = list(self._clients)
        for channel in clients:
            try:
                channel.put_nowait(script)
            except queue.Full:
                pass


def _make_handler(desk, hub: _Hub):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_args) -> None:                    # noqa: D401
            pass                                                  # 静音

        # ------------------------------------------------------ GET
        def do_GET(self) -> None:                                 # noqa: N802
            path = self.path.split('?', 1)[0]
            if path in ('/', '/index.html', '/desk.html'):
                self._send(200, _page_bytes(desk), 'text/html; charset=utf-8')
                return
            if path in ('/api/status', '/api/snapshot'):
                if not self._api_token_ok('read'):
                    self._send(403, b'{"error":"invalid token"}',
                               'application/json')
                    return
                try:
                    payload = (desk.api_snapshot() if path.endswith('snapshot')
                               else desk.status())
                except Exception as error:                       # noqa: BLE001
                    payload = {'ok': False, 'error': repr(error)}
                self._send(200, json.dumps(
                    {'ok': True, 'data': payload},
                    ensure_ascii=False, default=str).encode('utf-8'),
                    'application/json; charset=utf-8')
                return
            if path == '/ws':
                self._websocket()
                return
            if path == '/events':
                if not self._token_ok():
                    self._send(403, b'{"error":"invalid token"}',
                               'application/json')
                    return
                self._stream()
                return
            if path == '/health':
                self._send(200, b'ok', 'text/plain; charset=utf-8')
                return
            if path == '/strategy_chart':
                # 策略回测 / 参数优化：直接返回 MiniQT 生成的图表 HTML
                # （iframe 装载；同一份 pylightcharts 代码画出来的 ✓）
                from urllib.parse import parse_qs, urlparse
                query = parse_qs(urlparse(self.path).query)
                session_id = (query.get('id') or [''])[0]
                key = (query.get('key') or [''])[0]
                theme = (query.get('theme') or ['dark'])[0]
                try:
                    html = desk.strategy_chart_html(session_id, key, theme)
                except Exception as error:                       # noqa: BLE001
                    html = (f'<!doctype html><meta charset="utf-8">'
                            f'<body style="background:#111;color:#ddd;'
                            f'font:13px sans-serif;padding:16px">'
                            f'图表生成失败：{type(error).__name__}: {error}</body>')
                    self._send(500, html.encode('utf-8'),
                               'text/html; charset=utf-8')
                    return
                self._send(200, html.encode('utf-8'),
                           'text/html; charset=utf-8')
                return
            if path == '/healthz':
                # VS Code 扩展用它判断「服务起来了没有 + 连上了什么」
                # （比只看 stdout 可靠：日志被缓冲也不会卡在“正在启动” ✓）
                try:
                    payload = desk.status()
                except Exception as error:                       # noqa: BLE001
                    payload = {'ready': True, 'error': repr(error)}
                payload['url'] = f'http://127.0.0.1:{desk.port or 0}/'
                self._send(200,
                           json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                           'application/json; charset=utf-8')
                return
            # 静态资源：`/static/x.js` 和 `/x.js` **都认**
            # （desk.html 里用的是相对路径 `./desk.js` → 实际请求 `/desk.js` ✗
            #  以前只认 `/static/`，于是页面白屏：HTML 有、JS/CSS 全 404）
            name = os.path.basename(path)
            if name:
                target = os.path.join(STATIC_DIR, name)
                if os.path.isfile(target):
                    self._send(200, _read(target), _content_type(name))
                    return
            self._send(404, b'not found', 'text/plain; charset=utf-8')

        # ----------------------------------------------------- POST
        def do_POST(self) -> None:                                # noqa: N802
            path = self.path.split('?', 1)[0]
            if path == '/api/rpc':
                self._rpc()
                return
            if path != '/callback':
                self._send(404, b'not found', 'text/plain; charset=utf-8')
                return
            if not self._token_ok():
                self._send(403, b'{"error":"invalid token"}',
                           'application/json')
                return
            size = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(size) if size else b'{}'
            try:
                payload = json.loads(body.decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                payload = {}
            if isinstance(payload, dict) and payload.get('cmd'):
                try:
                    desk.handle(_protocol.encode_command(payload))
                except Exception as error:                        # noqa: BLE001
                    print(f'[desk] 命令失败: {error!r}')
            self._send(200, b'{"ok":true}', 'application/json')

        def do_OPTIONS(self) -> None:                             # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        # ---------------------------------------------------- helper
        def _supplied_token(self) -> str:
            supplied = str(self.headers.get('X-Desk-Token') or '')
            if not supplied:
                auth = str(self.headers.get('Authorization') or '')
                if auth.lower().startswith('bearer '):
                    supplied = auth[7:].strip()
            if not supplied:
                try:
                    from urllib.parse import parse_qs, urlparse
                    supplied = (parse_qs(urlparse(self.path).query)
                                .get('token') or [''])[0]
                except Exception:                            # noqa: BLE001
                    supplied = ''
            return supplied

        def _api_token_ok(self, scope: str = 'read') -> bool:
            """API token：web 会话 token 或 ops 签发的持久 token ✓"""
            supplied = self._supplied_token()
            expected = str(getattr(desk, '_web_token', '') or '')
            if expected and supplied and hmac.compare_digest(
                    supplied, expected):
                return True
            getter = getattr(desk, 'ops_view', None)
            if callable(getter):
                try:
                    service = getter()
                    if service is not None and service.check_token(
                            supplied, scope):
                        return True
                except Exception:                            # noqa: BLE001
                    pass
            return not expected          # 兼容旧 shell / 测试

        @staticmethod
        def _scope_of(cmd: str) -> str:
            text = str(cmd or '')
            if text.startswith('workbench'):
                return 'trade'
            if text.startswith('research'):
                return 'research'
            if text.startswith('datahub'):
                return 'data'
            if text.startswith('ops'):
                return 'ops'
            return 'read'

        def _rpc(self) -> None:
            """``POST /api/rpc``：headless / 远程调用（**带 token**）✓"""
            size = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(size) if size else b'{}'
            try:
                payload = json.loads(body.decode('utf-8') or '{}')
            except (ValueError, UnicodeDecodeError):
                payload = {}
            cmd = str((payload or {}).get('cmd') or '')
            scope = self._scope_of(cmd)
            if not self._api_token_ok(scope):
                self._send(403, b'{"ok":false,"error":"invalid token"}',
                           'application/json; charset=utf-8')
                return
            allowed = ('workbench', 'research', 'datahub', 'ops',
                       'strategy_', 'local_', 'quote_', 'home', 'alerts',
                       'symbol_search', 'table_row_at', 'visible',
                       'ui_state', 'layout', 'settings', 'tickets')
            if not cmd or not any(cmd == name or cmd.startswith(name)
                                  for name in allowed):
                self._send(400, b'{"ok":false,"error":"command not allowed"}',
                           'application/json; charset=utf-8')
                return
            result: Any = None
            error = ''
            try:
                direct = {
                    'workbench': lambda: desk.workbench_view().snapshot(),
                    'research': lambda: desk.research_view().snapshot(),
                    'datahub': lambda: desk.datahub_view().snapshot(),
                    'ops': lambda: desk.ops_view().snapshot(),
                }.get(cmd)
                if direct is not None:
                    result = direct()
                else:
                    result = desk.handle(_protocol.encode_command(
                        {'cmd': cmd, 'payload': (payload or {}).get('payload')
                         or {}}))
            except Exception as exc:                             # noqa: BLE001
                error = f'{type(exc).__name__}: {exc}'
            reply = {'ok': not error, 'data': result}
            if error:
                reply['error'] = error
            self._send(200, json.dumps(reply, ensure_ascii=False,
                                       default=str).encode('utf-8'),
                       'application/json; charset=utf-8')

        # ------------------------------------------------ WebSocket（请求/响应）
        def _ws_read(self):
            """读一帧 → ``(opcode, payload)``；连接断开 → ``None``"""
            head = self.rfile.read(2)
            if not head or len(head) < 2:
                return None
            first, second = head[0], head[1]
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = int.from_bytes(self.rfile.read(2), 'big')
            elif length == 127:
                length = int.from_bytes(self.rfile.read(8), 'big')
            mask = self.rfile.read(4) if masked else b''
            payload = self.rfile.read(length) if length else b''
            if masked and mask:
                payload = bytes(byte ^ mask[index % 4]
                                for index, byte in enumerate(payload))
            return opcode, payload

        def _ws_write(self, opcode: int, payload: bytes = b'') -> None:
            header = bytearray([0x80 | int(opcode)])
            size = len(payload)
            if size < 126:
                header.append(size)
            elif size < 65536:
                header.append(126)
                header.extend(size.to_bytes(2, 'big'))
            else:
                header.append(127)
                header.extend(size.to_bytes(8, 'big'))
            self.wfile.write(bytes(header) + payload)
            self.wfile.flush()

        def _websocket(self) -> None:
            """最小的 WebSocket 请求/响应通道（**必须带 token**）✓

            浏览器 / 脚本连 ``ws://host:port/ws?token=...``，发
            ``{"cmd": "workbench", "payload": {}}``，回一条 JSON。
            批量推送仍走 SSE ``/events``（页面用）。
            """
            key = str(self.headers.get('Sec-WebSocket-Key') or '')
            if not key:
                self._send(400, b'{"ok":false,"error":"not a websocket"}',
                           'application/json; charset=utf-8')
                return
            if not self._api_token_ok('read'):
                self._send(403, b'{"ok":false,"error":"invalid token"}',
                           'application/json; charset=utf-8')
                return
            self.send_response(101, 'Switching Protocols')
            self.send_header('Upgrade', 'websocket')
            self.send_header('Connection', 'Upgrade')
            self.send_header('Sec-WebSocket-Accept', ws_accept(key))
            self.end_headers()
            try:
                while True:
                    frame = self._ws_read()
                    if frame is None:
                        break
                    opcode, payload = frame
                    if opcode == 0x8:                     # close
                        self._ws_write(0x8)
                        break
                    if opcode == 0x9:                     # ping
                        self._ws_write(0xA, payload)
                        continue
                    if opcode != 0x1:                     # 只处理 text
                        continue
                    try:
                        message = json.loads(payload.decode('utf-8') or '{}')
                    except (ValueError, UnicodeDecodeError):
                        message = {}
                    scope = self._scope_of(str(message.get('cmd') or ''))
                    if not self._api_token_ok(scope):
                        reply = {'ok': False, 'error': 'invalid token'}
                    else:
                        reply = self._rpc_reply(message)
                    self._ws_write(0x1, json.dumps(
                        reply, ensure_ascii=False, default=str).encode('utf-8'))
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        def _rpc_reply(self, payload: Dict[str, Any]) -> Dict[str, Any]:
            """REST / WS 共用的命令分发（返回 JSON 可序列化结果）"""
            cmd = str((payload or {}).get('cmd') or '')
            allowed = ('workbench', 'research', 'datahub', 'ops',
                       'strategy_', 'local_', 'quote_', 'home', 'alerts',
                       'symbol_search', 'table_row_at', 'visible',
                       'ui_state', 'layout', 'settings', 'tickets')
            if not cmd or not any(cmd == name or cmd.startswith(name)
                                  for name in allowed):
                return {'ok': False, 'error': 'command not allowed'}
            try:
                direct = {
                    'workbench': lambda: desk.workbench_view().snapshot(),
                    'research': lambda: desk.research_view().snapshot(),
                    'datahub': lambda: desk.datahub_view().snapshot(),
                    'ops': lambda: desk.ops_view().snapshot(),
                }.get(cmd)
                if direct is not None:
                    data = direct()
                else:
                    data = desk.handle(_protocol.encode_command(
                        {'cmd': cmd, 'payload': (payload or {}).get('payload')
                         or {}}))
                return {'ok': True, 'data': data}
            except Exception as exc:                             # noqa: BLE001
                return {'ok': False,
                        'error': f'{type(exc).__name__}: {exc}'}

        def _token_ok(self) -> bool:
            """浏览器壳的令牌校验（SSE / POST 都必须带 ✓）"""
            expected = str(getattr(desk, '_web_token', '') or '')
            if not expected:
                return True                       # 兼容旧 shell / 测试
            supplied = self._supplied_token()
            return bool(supplied) and hmac.compare_digest(
                str(supplied), expected)

        def _origin_allowed(self, origin: str) -> bool:
            if not origin:
                return False
            if origin == 'null':
                return True                       # file:// 页面
            port = int(getattr(desk, 'port', 0) or 0)
            return origin in {
                f'http://127.0.0.1:{port}', f'http://localhost:{port}',
                'http://127.0.0.1', 'http://localhost',
            }

        def _cors(self) -> None:
            # ★ 不再 `*`：只允许 desk 自己的 origin；命令还有 token 兜底 ✓
            origin = str(self.headers.get('Origin') or '')
            if self._origin_allowed(origin):
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Vary', 'Origin')
            self.send_header('Access-Control-Allow-Headers',
                             'Content-Type, X-Desk-Token')
            self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self._cors()
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _stream(self) -> None:
            channel = hub.add()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'keep-alive')
            self._cors()
            self.end_headers()
            try:
                self.wfile.write(b'retry: 1000\n\n')
                self.wfile.flush()
                while True:
                    try:
                        script = channel.get(timeout=5.0)
                    except queue.Empty:
                        self.wfile.write(b': ping\n\n')           # 心跳
                        self.wfile.flush()
                        continue
                    data = script.replace('\n', '\\n')
                    self.wfile.write(f'data: {data}\n\n'.encode('utf-8'))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.drop(channel)

    return Handler


def _content_type(name: str) -> str:
    if name.endswith('.js'):
        return 'text/javascript; charset=utf-8'
    if name.endswith('.css'):
        return 'text/css; charset=utf-8'
    if name.endswith('.html'):
        return 'text/html; charset=utf-8'
    return 'application/octet-stream'


#: 页面全部关掉后，等多久没有新连接就退出（秒）✓
CLOSE_GRACE = 2.5


def serve(desk, *, open_browser: bool = True, as_json: bool = False,
          keep_alive: bool = False, host: str = '127.0.0.1') -> None:
    """起服务并打开浏览器（阻塞；Ctrl+C 结束 ✓）

    ``keep_alive=True``：页面全关也不退出（headless / 远程访问用 ✓）
    ``host='0.0.0.0'``：允许局域网 / 远程访问（**必须配 API token**）✓
    """
    if not os.path.isfile(DESK_HTML):
        raise FileNotFoundError(
            f'找不到 desk 宿主页：{DESK_HTML}\n'
            '请先在 jslib 目录执行 `npm run build`（会产出 '
            'pylightcharts/js/desk.html + desk.js）')

    hub = _Hub()
    #: 浏览器壳的本地命令 / SSE 令牌（写入页面 __deskConfig；Qt 不用 ✓）
    if not getattr(desk, '_web_token', ''):
        desk._web_token = secrets.token_urlsafe(24)
    desk.sender = hub.broadcast
    handler = _make_handler(desk, hub)
    server = _Server((str(host or '127.0.0.1'), int(desk.port or 0)), handler)
    server.daemon_threads = True
    server.request_queue_size = 64
    port = server.server_address[1]
    url = f'http://127.0.0.1:{port}/'
    # 供调用方/测试读取（`port=0` 时真实端口只有这里知道 ✓）
    desk.port = port
    desk.url = url
    if as_json:
        # 一行 JSON（`minibt desk --browser --json`）：扩展读它拿端口/状态 ✓
        print(json.dumps({'ready': True, 'url': url, 'port': port,
                          'shell': 'browser', 'title': desk.title,
                          'theme': desk.theme}, ensure_ascii=False),
              flush=True)
    else:
        print(f'[desk] serving {url}  (Ctrl+C 结束)')

    # 浏览器壳没有 Qt 事件循环 → 自己起一个节拍线程 ✓
    stop = threading.Event()

    def ticker() -> None:
        while not stop.wait(0.5):
            try:
                desk.tick()
            except Exception as error:                            # noqa: BLE001
                print(f'[desk] tick 失败: {error!r}')

    thread = threading.Thread(target=ticker, daemon=True)
    thread.start()

    # ★ 关闭页面就退出：所有 SSE 客户端都断开后等 `CLOSE_GRACE` 秒还没人回来
    #   就停服务（用户要求：关掉浏览器 = 结束 desk，不留后台进程 ✓）
    def watchdog() -> None:
        if keep_alive:
            return
        empty_since: Optional[float] = None
        while not stop.wait(0.5):
            alive = hub.count()
            if alive:
                empty_since = None
                continue
            if not hub.ever_connected():
                continue                       # 还没人打开过页面 → 不动
            if empty_since is None:
                empty_since = time.monotonic()
            elif time.monotonic() - empty_since >= CLOSE_GRACE:
                print(f'[desk] 页面已关闭（{CLOSE_GRACE:.0f}s 无连接）→ 退出')
                stop.set()
                server.shutdown()
                return

    watcher = threading.Thread(target=watchdog, daemon=True)
    watcher.start()
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as error:                                # noqa: BLE001
            print(f'[desk] 打开浏览器失败：{error!r}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[desk] stopped')
    finally:
        stop.set()
        try:
            server.server_close()
        except Exception:                                         # noqa: BLE001
            pass
        server.server_close()

# ------------------------------------------------------------------ 网页代理
#: 抓取网页用的 UA（有些站点没有 UA 直接 403 ✓）
WEB_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/122.0 Safari/537.36')

#: 单页大小上限（文档站点一般 < 1MB；超过就不代理 ✓）
WEB_MAX_BYTES = 4 * 1024 * 1024


def fetch_page(url: str, timeout: float = 12.0) -> Dict[str, Any]:
    """抓一个网页的 HTML（给 desk 的「网页 tab」用 ✓）

    为什么要后端抓？官网 / 文档站点常带 `X-Frame-Options` 或 CDN 的
    「禁止 iframe 嵌入」策略 → 直接 `<iframe src>` 会被拦（用户实测：
    首页能开、点进文档页就被拦 ✗）。后端抓成 HTML 再用 `srcdoc` 塞进去，
    就能绕开 `X-Frame-Options` / `frame-ancestors` ✓（MkDocs 这类静态文档
    完全够用；SPA 站点会退化成静态快照，仍可用「系统浏览器」打开）
    """
    import urllib.error
    import urllib.request

    real = str(url or '').strip()
    if not real.lower().startswith(('http://', 'https://')):
        return {'ok': False, 'error': '只支持 http(s) 网址', 'url': real}
    request = urllib.request.Request(real, headers={
        'User-Agent': WEB_UA,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(WEB_MAX_BYTES + 1)
            final_url = response.geturl() or real
            charset = ''
            try:
                charset = response.headers.get_content_charset() or ''
            except Exception:                                # noqa: BLE001
                charset = ''
            encoding = str((response.headers.get('Content-Encoding') or '')
                           ).lower()
    except urllib.error.HTTPError as error:
        return {'ok': False, 'url': real,
                'error': f'HTTP {error.code} {error.reason}'}
    except Exception as error:                               # noqa: BLE001
        return {'ok': False, 'url': real, 'error': repr(error)}
    if len(raw) > WEB_MAX_BYTES:
        return {'ok': False, 'url': real, 'error': '页面太大（> 4MB）'}
    if encoding == 'gzip':
        try:
            import gzip
            raw = gzip.decompress(raw)
        except Exception:                                    # noqa: BLE001
            pass
    elif encoding == 'deflate':
        try:
            import zlib
            raw = zlib.decompress(raw)
        except Exception:                                    # noqa: BLE001
            pass
    for guess in (charset, 'utf-8', 'gb18030'):
        if not guess:
            continue
        try:
            html = raw.decode(guess, 'replace')
            break
        except LookupError:
            continue
    else:
        html = raw.decode('utf-8', 'replace')
    return {'ok': True, 'url': final_url, 'html': html}


#: 抓取后的页面里补的小东西：**回到顶部**圆按钮（原站的按钮是 Material 的 JS
#: 做的，我们为了消掉 `__md_get` 报错把脚本全删了 → 按钮也没了 ✗，这里自己补一个 ✓）
WEB_TOPBUTTON = """
<style>
.__desk_top_btn {
  position: fixed; right: 22px; bottom: 22px; z-index: 2147483000;
  width: 48px; height: 48px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: #6b46c1; color: #fff; line-height: 1;
  box-shadow: 0 8px 22px rgba(0, 0, 0, .32);
  cursor: pointer; opacity: 0; visibility: hidden;
  transition: opacity .18s ease, transform .18s ease;
  transform: translateY(6px); user-select: none;
}
.__desk_top_btn.on { opacity: .92; visibility: visible; transform: none; }
.__desk_top_btn:hover { opacity: 1; }
</style>
<div class="__desk_top_btn" title="回到顶部" aria-label="回到顶部"><svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg></div>
<script>
(function () {
  var btn = document.querySelector('.__desk_top_btn');
  if (!btn) return;
  function sync() {
    var top = window.pageYOffset || document.documentElement.scrollTop || 0;
    if (top > 320) btn.classList.add('on');
    else btn.classList.remove('on');
  }
  window.addEventListener('scroll', sync, { passive: true });
  document.addEventListener('scroll', sync, { passive: true });
  btn.addEventListener('click', function () {
    try { window.scrollTo({ top: 0, behavior: 'smooth' }); }
    catch (err) { window.scrollTo(0, 0); }
  });
  sync();
})();
</script>
"""


def wrap_page(html: str, base_url: str) -> str:
    """把抓到的 HTML 处理一下：补 `<base>` + **拦截站内链接**（交给父页面代理 ✓）"""
    import html as _html

    base = ('<base href="%s">' % _html.escape(str(base_url or ''),
                                             quote=True))
    hook = """
<script>
(function () {
  document.addEventListener('click', function (event) {
    var node = event.target;
    while (node && node.tagName !== 'A') node = node.parentElement;
    if (!node) return;
    var href = node.getAttribute('href') || '';
    if (!href || href.charAt(0) === '#') return;
    var abs;
    try { abs = new URL(href, document.baseURI).href; } catch (err) { return; }
    if (!/^https?:/i.test(abs)) return;
    event.preventDefault();
    parent.postMessage({ __deskWebNav: abs }, '*');
  }, true);
  // 站内 form / target=_blank 也别把 iframe 带跑
  document.addEventListener('submit', function (event) { event.preventDefault(); }, true);
})();
</script>
"""
    text = str(html or '')
    lowered = text.lower()
    # 原站的「回到顶部」是 JS 按钮，脚本被我们删了 → 自己补一个 ✓
    hook = hook + WEB_TOPBUTTON
    if '<head' in lowered:
        index = lowered.index('<head') + 5
        end = text.find('>', index)
        if end != -1:
            return text[:end + 1] + base + text[end + 1:] + hook
    return base + text + hook

#: 内联资源的上限（避免一个页面拖几十秒 ✓）
WEB_MAX_CSS = 8
WEB_MAX_IMAGES = 30
WEB_ASSET_BYTES = 1 * 1024 * 1024
#: 所有资源（CSS / 图片）的**总时限**（秒）——超时的不等，页面先出来 ✓
WEB_ASSET_DEADLINE = 1.5


def inline_assets(html: str, base_url: str) -> str:
    """把外链 CSS / 图片**内联**进 HTML（资源**并发**抓取 + 总时限，快 ✓）

    * 为什么内联：`srcdoc` 的源是 `file://`，远端 `<link>` / `<img>` 会被当
      跨源子资源拦掉 → 页面会"没样式" ✗
    * 为什么并发 + 时限：个别 CDN（font-awesome / 字体站）单个就要 5 秒，
      串行抓要 4~6 秒（用户实测「太慢」）→ 12 路并发 + `WEB_ASSET_DEADLINE`
      秒到点就收，页面先出来（缺的那点图标/字体不影响阅读 ✓）
    """
    import base64
    import re
    from urllib.parse import urljoin

    text = str(html or '')
    base = str(base_url or '')

    # ---- 1. 先扫出所有资源 URL（CSS 优先，图片随后）----
    css_urls = []
    for tag in re.findall(r'<link\b[^>]*>', text, flags=re.I):
        if 'stylesheet' not in tag.lower():
            continue
        href = _attr(tag, 'href')
        if not href:
            continue
        target = urljoin(base, href)
        if target.lower().startswith(('http://', 'https://')):
            css_urls.append(target)
        if len(css_urls) >= WEB_MAX_CSS:
            break
    img_urls = []
    for tag in re.findall(r'<img\b[^>]*>', text, flags=re.I):
        src = _attr(tag, 'src')
        if not src or src.startswith('data:'):
            continue
        target = urljoin(base, src)
        if target.lower().startswith(('http://', 'https://')):
            img_urls.append(target)
        if len(img_urls) >= WEB_MAX_IMAGES:
            break

    # ---- 2. 并发抓（总时限到点就收 ✓）----
    unique = list(dict.fromkeys(css_urls + img_urls))
    blobs = {}
    if unique:
        from concurrent.futures import ThreadPoolExecutor, wait

        pool = ThreadPoolExecutor(max_workers=12)
        futures = {pool.submit(_fetch_bytes, url): url for url in unique}
        done, pending = wait(futures, timeout=WEB_ASSET_DEADLINE)
        for future in done:
            url = futures[future]
            try:
                data = future.result()
            except Exception:                                # noqa: BLE001
                data = None
            if data:
                blobs[url] = data
        for future in pending:
            future.cancel()
        pool.shutdown(wait=False)

    # ---- 3. CSS → <style>（`url(...)` 绝对化 ✓）----
    css_done = set()

    def css_tag(match):
        tag = match.group(0)
        if 'stylesheet' not in tag.lower():
            return tag
        href = _attr(tag, 'href')
        target = urljoin(base, href) if href else ''
        data = blobs.get(target)
        if not data or len(css_done) >= WEB_MAX_CSS:
            return ''
        css_done.add(target)
        css = data.decode('utf-8', 'replace')

        def abs_url(inner):
            raw = inner.group(1).strip().strip('"').strip("'")
            if raw.startswith(('data:', 'http://', 'https://', '#')):
                return inner.group(0)
            return 'url("%s")' % urljoin(target, raw)

        css = re.sub(r'url\(([^)]+)\)', abs_url, css)
        return '<style>' + chr(10) + css + chr(10) + '</style>'

    text = re.sub(r'<link\b[^>]*>', css_tag, text, flags=re.I)

    # ---- 4. 去掉**所有**脚本（内联脚本依赖被删的外链 → 报 `__md_get` ✗）----
    text = re.sub(r'<script\b[^>]*>.*?</script>', '', text, flags=re.I | re.S)
    text = re.sub(r'<script\b[^>]*/?>', '', text, flags=re.I)

    # ---- 5. 图片 → data URI（只转抓到的 ✓）----
    used = {'n': 0}

    def img_tag(match):
        tag = match.group(0)
        src = _attr(tag, 'src')
        if not src or src.startswith('data:'):
            return tag
        target = urljoin(base, src)
        data = blobs.get(target)
        if not data or used['n'] >= WEB_MAX_IMAGES:
            return tag
        lowered = target.lower().split('?')[0]
        guess = 'png'
        for ext in ('svg', 'gif', 'jpg', 'jpeg', 'webp', 'png', 'ico'):
            if lowered.endswith('.' + ext):
                guess = {'svg': 'svg+xml', 'jpg': 'jpeg',
                         'ico': 'x-icon'}.get(ext, ext)
                break
        used['n'] += 1
        encoded = base64.b64encode(data).decode('ascii')
        return tag.replace(src, 'data:image/%s;base64,%s' % (guess, encoded))

    text = re.sub(r'<img\b[^>]*>', img_tag, text, flags=re.I)

    # ---- 6. 剩下的外链样式（没抓到 / 超上限）去掉，避免半套样式 ✓ ----
    text = re.sub(r'<link\b[^>]*stylesheet[^>]*>', '', text, flags=re.I)
    return text


def _fetch_bytes(url: str, timeout: float = 4.0) -> Optional[bytes]:
    """抓二进制资源（CSS / 图片）；失败返回 None ✓"""
    import urllib.request
    try:
        request = urllib.request.Request(url, headers={
            'User-Agent': WEB_UA,
            'Referer': url,
        })
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(WEB_ASSET_BYTES + 1)
    except Exception:                                        # noqa: BLE001
        return None
    if len(data) > WEB_ASSET_BYTES:
        return None
    return data


def _attr(tag: str, name: str) -> str:
    """从 HTML 标签里取属性（**带引号 / 不带引号都支持** ✓）

    MkDocs Material 压缩后的 HTML 是 `<link rel=stylesheet href=../../a.css>`
    这种**无引号**写法，只认引号的 regex 会全部漏掉 ✗
    """
    import re

    pattern = name + r"\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)"
    match = re.search(pattern, tag, re.I)
    if not match:
        return ''
    raw = match.group(1).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        raw = raw[1:-1]
    return raw.strip()


#: 页面缓存（同一 URL 10 分钟内直接给 HTML → 秒开 ✓）
_PAGE_CACHE: Dict[str, tuple] = {}   # {url: (时间戳, html)}
PAGE_CACHE_TTL = 600.0
PAGE_CACHE_MAX = 12


def _cache_get(url: str) -> str:
    import time
    entry = _PAGE_CACHE.get(url)
    if not entry:
        return ''
    stamp, html = entry
    if time.time() - stamp > PAGE_CACHE_TTL:
        _PAGE_CACHE.pop(url, None)
        return ''
    return html


def _cache_put(url: str, html: str) -> None:
    import time
    global _PAGE_CACHE
    _PAGE_CACHE[url] = (time.time(), html)
    if len(_PAGE_CACHE) > PAGE_CACHE_MAX:
        oldest = min(_PAGE_CACHE, key=lambda key: _PAGE_CACHE[key][0])
        _PAGE_CACHE.pop(oldest, None)


def page_html(url: str, timeout: float = 12.0) -> Dict[str, Any]:
    """抓网页 → 内联 CSS / 图片 → 补 `<base>` + 链接钩子（**带缓存，秒开** ✓）

    * 同一 URL 10 分钟内直接命中缓存（`cached=True`）；
    * 资源**并发**抓取（线程池 12 路）——串行要 4 秒，并发约 0.3~0.8 秒 ✓
    """
    cached = _cache_get(str(url or ''))
    if cached:
        return {'ok': True, 'url': url, 'html': cached, 'cached': True}
    result = fetch_page(url, timeout=timeout)
    if not result.get('ok'):
        return result
    final = str(result.get('url') or url)
    html = wrap_page(inline_assets(str(result.get('html') or ''), final), final)
    _cache_put(str(url or ''), html)
    _cache_put(final, html)
    return {'ok': True, 'url': final, 'html': html, 'cached': False}


