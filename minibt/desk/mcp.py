# coding: utf-8
"""minibt desk 的 MCP 服务端（v1.3.7-27，方案 M4）。

`MCP`（Model Context Protocol）=「JSON-RPC 2.0 over stdio」的一套约定：

```
客户端 ──request──►  mcp.py ──► tools.call()  ──► Desk 的方法
        ◄─response──
```

这里只做**传输 + 协议**，工具表和执行都用 `minibt/desk/tools.py`
（M1/M2 已经写好，`SPECS` 直接转成 MCP 的 `tools/list`）✓

用法::

    # 1) 一次性生成配置（给 pi CLI / Claude Desktop / Cursor 用）
    python -m minibt.desk.mcp --config

    # 2) 当 stdio 服务端跑（客户端会自己拉起来）
    python -m minibt.desk.mcp --embedded

    # 3) 手工试一下
    echo {"jsonrpc":"2.0","id":1,"method":"tools/list"} | python -m minibt.desk.mcp

零 npm：JSON-RPC 就手写这 200 行，不引入任何 Node 依赖 ✓
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

from . import tools as _tools

#: 协议版本（和官方 2024-11-05 对齐；客户端给别的版本我们也照这个回 ✓）
PROTOCOL = '2024-11-05'

#: 服务名 / 版本
SERVER_NAME = 'minibt-desk'
SERVER_VERSION = '1.3.7'

#: MCP 客户端配置（pi CLI / Claude Desktop / Cursor 都吃这个格式 ✓）
CONFIG_FILE = os.path.join(os.path.expanduser('~'), '.minibt', 'ai',
                           'mcp.json')


# ---------------------------------------------------------------- 配置
def config_payload() -> Dict[str, Any]:
    """生成 `mcp.json` 的内容（`--embedded`：自己起一个离屏 desk ✓）"""
    return {
        'mcpServers': {
            SERVER_NAME: {
                'command': sys.executable or 'python',
                'args': ['-m', 'minibt.desk.mcp'],
                'env': {'MINIBT_DESK_MCP': '1'},
            },
        },
    }


def write_config(path: str = '') -> str:
    """写 `~/.minibt/ai/mcp.json`（返回路径；已有内容会合并 ✓）"""
    target = str(path or CONFIG_FILE)
    data: Dict[str, Any] = {}
    try:
        with open(target, 'r', encoding='utf-8') as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            data = loaded
    except (OSError, ValueError):
        data = {}
    servers = data.get('mcpServers')
    if not isinstance(servers, dict):
        servers = {}
    servers.update(config_payload()['mcpServers'])
    data['mcpServers'] = servers
    os.makedirs(os.path.dirname(target) or '.', exist_ok=True)
    with open(target, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    return target


# ---------------------------------------------------------------- 工具表
def tools_list() -> List[Dict[str, Any]]:
    """`tools.SPECS`（OpenAI 格式）→ MCP 的 `tools/list` 格式 ✓"""
    rows: List[Dict[str, Any]] = []
    for spec in _tools.SPECS:
        function = spec.get('function') or {}
        rows.append({
            'name': str(function.get('name') or ''),
            'description': str(function.get('description') or ''),
            'inputSchema': function.get('parameters') or {'type': 'object'},
        })
    return rows


# ---------------------------------------------------------------- 服务端
class McpServer:
    """stdio JSON-RPC 2.0 服务端（一行一条消息 ✓）

    `desk=None` 且本机桥活着 → **转发给正在运行的 desk**（M5 ✓）；
    没有桥就用 `--embedded` 的离屏实例。
    """

    def __init__(self, desk=None) -> None:
        self.desk = desk

    # ---- 单条消息 → 单条响应（`None` = 不响应，例如通知 ✓）
    def handle(self, message: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(message, dict):
            return _error(None, -32600, 'Invalid Request')
        method = str(message.get('method') or '')
        request_id = message.get('id')
        is_notification = 'id' not in message
        if not method:
            return None if is_notification else _error(
                request_id, -32600, 'Invalid Request')
        if is_notification:
            # `notifications/initialized` 之类：不需要回包 ✓
            return None
        params = message.get('params') or {}
        if not isinstance(params, dict):
            params = {}
        if method == 'initialize':
            return _ok(request_id, {
                'protocolVersion': PROTOCOL,
                'capabilities': {'tools': {'listChanged': False}},
                'serverInfo': {'name': SERVER_NAME,
                               'version': SERVER_VERSION},
            })
        if method == 'ping':
            return _ok(request_id, {})
        if method == 'tools/list':
            return _ok(request_id, {'tools': tools_list()})
        if method == 'tools/call':
            return _call(request_id, params, self.desk)
        return _error(request_id, -32601, f'Method not found: {method}')

    def serve(self, reader=None, writer=None) -> int:
        """从 `reader` 逐行读请求、往 `writer` 写响应（默认 stdin/stdout ✓）"""
        source = reader or sys.stdin
        sink = writer or sys.stdout
        for line in source:
            text = str(line or '').strip()
            if not text:
                continue
            try:
                message = json.loads(text)
            except ValueError:
                _write(sink, _error(None, -32700, 'Parse error'))
                continue
            reply = self.handle(message)
            if reply is None:
                continue
            _write(sink, reply)
        return 0


def _call(request_id: Any, params: Dict[str, Any], desk) -> Dict[str, Any]:
    name = str(params.get('name') or '')
    arguments = params.get('arguments')
    if not isinstance(arguments, dict):
        arguments = {}
    if name not in _tools.NAMES:
        return _ok(request_id, {
            'content': [{'type': 'text',
                         'text': f'未知工具：{name}（可用：'
                                 f'{", ".join(_tools.NAMES)}）'}],
            'isError': True,
        })
    # ★ 没有本地 desk 实例 → 走本机桥（操控用户正在看的那个 desk ✓）
    if desk is None:
        try:
            from . import bridge as _bridge
            remote = _bridge.call(name, arguments)
        except Exception as error:                            # noqa: BLE001
            remote = f'转发失败：{type(error).__name__}: {error}'
        if remote:
            failed = remote.lstrip().startswith(('{', '['))
            try:
                data = json.loads(remote)
                if isinstance(data, dict):
                    failed = data.get('ok') is False
                else:
                    failed = False
            except ValueError:
                failed = remote.startswith(('没有连上', '连不上', '转发失败',
                                            'desk 桥'))
            return _ok(request_id, {
                'content': [{'type': 'text', 'text': remote}],
                'isError': bool(failed),
            })
    text = _tools.call(name, arguments, desk)
    failed = False
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            failed = data.get('ok') is False
    except ValueError:
        failed = text.startswith(('未知', '当前没有')) or '失败' in text[:20]
    return _ok(request_id, {
        'content': [{'type': 'text', 'text': text}],
        'isError': bool(failed),
    })


def _ok(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {'jsonrpc': '2.0', 'id': request_id,
            'error': {'code': code, 'message': message}}


def _write(sink, payload: Dict[str, Any]) -> None:
    sink.write(json.dumps(payload, ensure_ascii=False) + '\n')
    try:
        sink.flush()
    except Exception:                                        # noqa: BLE001
        pass


# ---------------------------------------------------------------- 入口
def embedded_desk():
    """离屏 desk（没有界面；读本地数据 / 模拟账户都能用 ✓）"""
    from .app import Desk

    desk = Desk(offline=True)
    desk.sent = []                    # 丢掉推送（没人看界面）
    desk.sender = desk.sent.append
    desk._booted = True
    return desk


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if '--config' in args:
        path = write_config()
        print(f'已写入 MCP 配置：{path}')
        print(json.dumps(config_payload(), ensure_ascii=False, indent=2))
        return 0
    if '--list' in args:
        print(json.dumps({'tools': tools_list()}, ensure_ascii=False,
                         indent=2))
        return 0
    desk = None
    if '--embedded' in args:
        desk = embedded_desk()
    else:
        # 默认：有本机桥就连它（操控当前界面），没有就退离屏实例 ✓
        try:
            from . import bridge as _bridge
            if not _bridge.read_info():
                desk = embedded_desk()
        except Exception:                                     # noqa: BLE001
            desk = embedded_desk()
    return McpServer(desk).serve()


if __name__ == '__main__':                                   # pragma: no cover
    raise SystemExit(main())
