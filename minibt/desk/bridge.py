# coding: utf-8
"""desk 的「本机桥」：让 MCP / 外部程序操控**正在运行的 desk**（v1.3.7-28，M5）。

`--embedded` 的 MCP 是另一份离屏 desk（动不到你看的界面）。这个桥解决那件事：

```
外部客户端 ──stdio MCP──► mcp.py ──HTTP(127.0.0.1, token)──► bridge.py ──► Desk
```

安全：

* 只绑 **127.0.0.1**（不监听外网）；
* 每次启动生成一次性 **token**（写 `~/.minibt/ai/bridge.json`，权限 0600-ish）；
* 所有 `desk_*` 调用仍然过 `tools.call()` → **开关 / confirm / 审计** 一个都不少 ✓。
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

#: 桥的信息文件（端口 + token；desk 退出时删掉 ✓）
INFO_FILE = os.path.join(os.path.expanduser('~'), '.minibt', 'ai',
                         'bridge.json')

#: 服务实例（单例；重复启动直接复用 ✓）
_SERVER: Optional[ThreadingHTTPServer] = None
_INFO: Dict[str, Any] = {}
_LOCK = threading.Lock()


def info() -> Dict[str, Any]:
    """桥的信息（没启动 → 空 dict）"""
    with _LOCK:
        if _SERVER is None:
            return {}
        return dict(_INFO)


def read_info() -> Dict[str, Any]:
    """读 `bridge.json`（外部程序用；进程已经死了就当没有 ✓）"""
    try:
        with open(INFO_FILE, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or not data.get('port'):
        return {}
    if not _alive(int(data.get('port') or 0)):
        return {}
    return data


def _alive(port: int) -> bool:
    import socket
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.4):
            return True
    except OSError:
        return False


class _Handler(BaseHTTPRequestHandler):
    desk = None                    # 由 `start()` 注入
    token = ''

    # 别在 stderr 刷访问日志 ✓
    def log_message(self, *args: Any) -> None:                # noqa: D102
        pass

    def _send(self, payload: Dict[str, Any], code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        token = str(self.headers.get('X-Minibt-Token') or '')
        return bool(_Handler.token) and secrets.compare_digest(
            token, _Handler.token)

    def do_GET(self) -> None:                                 # noqa: N802
        if self.path.startswith('/health'):
            self._send({'ok': True, 'pid': os.getpid(),
                        'version': _version(), 'port': info().get('port')})
            return
        self._send({'ok': False, 'error': 'not found'}, 404)

    def do_POST(self) -> None:                                # noqa: N802
        if not self._authorized():
            self._send({'ok': False, 'error': 'bad token'}, 401)
            return
        try:
            size = int(self.headers.get('Content-Length') or 0)
            payload = json.loads(self.rfile.read(size) or b'{}')
        except (ValueError, OSError):
            self._send({'ok': False, 'error': 'bad json'}, 400)
            return
        if not isinstance(payload, dict):
            self._send({'ok': False, 'error': 'bad payload'}, 400)
            return
        from . import tools as _tools

        if self.path.startswith('/tools'):
            self._send({'ok': True, 'tools': list(_tools.NAMES)})
            return
        if self.path.startswith('/call'):
            name = str(payload.get('name') or '')
            args = payload.get('arguments') or payload.get('args') or {}
            if not isinstance(args, dict):
                args = {}
            text = _tools.call(name, args, _Handler.desk,
                               str(payload.get('session') or 'mcp'))
            self._send({'ok': True, 'text': text})
            return
        self._send({'ok': False, 'error': 'not found'}, 404)


def _version() -> str:
    try:
        import minibt as _minibt
        return str(getattr(_minibt, '__version__', '?'))
    except Exception:                                        # noqa: BLE001
        return '?'


def start(desk, port: int = 0) -> Dict[str, Any]:
    """启动桥（幂等）；返回 `{port, token, file}` ✓"""
    global _SERVER
    with _LOCK:
        if _SERVER is not None:
            return dict(_INFO)
        token = secrets.token_hex(16)
        _Handler.desk = desk
        _Handler.token = token
        try:
            server = ThreadingHTTPServer(('127.0.0.1', int(port or 0)),
                                        _Handler)
        except OSError:
            return {}
        server.daemon_threads = True
        _SERVER = server
        _INFO.clear()
        _INFO.update({'port': int(server.server_address[1]), 'token': token,
                      'pid': os.getpid(), 'file': INFO_FILE,
                      'started': time.time()})
        threading.Thread(target=server.serve_forever, daemon=True,
                         name='desk-bridge').start()
        try:
            os.makedirs(os.path.dirname(INFO_FILE), exist_ok=True)
            with open(INFO_FILE, 'w', encoding='utf-8') as handle:
                json.dump({k: _INFO[k] for k in ('port', 'token', 'pid')},
                          handle, ensure_ascii=False)
        except OSError:
            pass
        return dict(_INFO)


def stop() -> None:
    """关桥 + 删信息文件（desk 退出时调 ✓）"""
    global _SERVER
    with _LOCK:
        server, _SERVER = _SERVER, None
        _INFO.clear()
    if server is not None:
        try:
            server.shutdown()
            server.server_close()
        except Exception:                                    # noqa: BLE001
            pass
    try:
        os.remove(INFO_FILE)
    except OSError:
        pass


# ---------------------------------------------------------------- 客户端
def call(name: str, args: Dict[str, Any], session: str = 'mcp',
         timeout: float = 120.0) -> str:
    """外部程序侧：把调用转给正在跑的 desk（失败返回文字 ✓）"""
    import urllib.error
    import urllib.request

    data = read_info()
    if not data:
        return ('没有连上正在运行的 minibt desk（桥未启动）：'
                '先用 python -m minibt desk 打开桌面端')
    port = int(data.get('port') or 0)
    body = json.dumps({'name': name, 'arguments': args or {},
                       'session': session}, ensure_ascii=False).encode()
    request = urllib.request.Request(
        f'http://127.0.0.1:{port}/call', data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'X-Minibt-Token': str(data.get('token') or '')})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read() or b'{}')
    except urllib.error.HTTPError as error:
        return f'desk 桥返回 HTTP {error.code}（token 不对 / 已退出？）'
    except Exception as error:                               # noqa: BLE001
        return f'连不上 desk 桥：{error!r}'
    if not isinstance(payload, dict):
        return 'desk 桥返回了异常数据'
    return str(payload.get('text') or '（空结果）')
