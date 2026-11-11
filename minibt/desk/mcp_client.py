# coding: utf-8
"""desk 当 **MCP 客户端**：把外部 MCP server 的工具接进 PI 对话（v1.3.7-28，M5 反向）。

`~/.minibt/ai/mcp.json` 里除了我们自己的 `minibt-desk`，还可以放别的 server：

```json
{"mcpServers": {
  "sqlite": {"command": "python", "args": ["my_mcp_sqlite.py"]},
  "browser": {"command": "npx", "args": ["-y", "@modelcontextprotocol/x"]}
}}
```

desk 会（**懒启动**，第一次用到才拉起子进程）：

1. 逐个 spawn + `initialize`，再 `tools/list`；
2. 把它们包装成 `mcp__<server>__<tool>` 的工具定义，注册进 `agent.TOOLS`；
3. 对话里调用时转发 `tools/call`，结果原样回给模型。

零 npm：客户端就是「一行 JSON-RPC + 一把锁」，不依赖任何 Node 包 ✓
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

#: 配置（和 `--config` 生成的同一份 ✓）
CONFIG_FILE = os.path.join(os.path.expanduser('~'), '.minibt', 'ai',
                           'mcp.json')

#: 我们自己的服务名（不当下游，避免自我递归 ✓）
SELF_NAME = 'minibt-desk'

#: 工具名前缀：`mcp__<server>__<tool>`
PREFIX = 'mcp__'

#: 单次请求超时（秒）
TIMEOUT = 30.0

# `specs()` 里会再调 `client_for()`（同一把锁）→ 必须可重入 ✓
_LOCK = threading.RLock()
_CLIENTS: Dict[str, 'McpClient'] = {}
_SPECS: Optional[List[Dict[str, Any]]] = None
_SPECS_AT = 0.0
#: 缓存多久重查一次（新加 server 不用重启 desk ✓）
SPECS_TTL = 60.0


def servers() -> Dict[str, Dict[str, Any]]:
    """读配置里的外部 server（跳过自己 ✓）"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    rows = data.get('mcpServers') if isinstance(data, dict) else None
    if not isinstance(rows, dict):
        return {}
    return {str(name): dict(value) for name, value in rows.items()
            if name != SELF_NAME and isinstance(value, dict)}


class McpClient:
    """一个外部 server（stdio JSON-RPC 2.0 ✓）"""

    def __init__(self, name: str, command: str, args: Optional[List[str]] = None,
                 env: Optional[Dict[str, str]] = None) -> None:
        self.name = str(name)
        self.command = str(command)
        self.args = [str(item) for item in (args or [])]
        self.env = {str(k): str(v) for k, v in (env or {}).items()}
        self.proc: Optional[subprocess.Popen] = None
        self.tools: List[Dict[str, Any]] = []
        self._id = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------ 生命周期
    def start(self) -> bool:
        if self.proc is not None and self.proc.poll() is None:
            return True
        if not self.command:
            return False
        env = dict(os.environ)
        env.update(self.env)
        try:
            self.proc = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=env, text=True,
                encoding='utf-8', errors='replace', bufsize=1)
        except OSError:
            self.proc = None
            return False
        reply = self._request('initialize', {
            'protocolVersion': '2024-11-05',
            'capabilities': {}, 'clientInfo': {'name': 'minibt-desk',
                                               'version': '1.3.7'}})
        if reply is None:
            self.stop()
            return False
        self._notify('notifications/initialized', {})
        listing = self._request('tools/list', {}) or {}
        # JSON-RPC 包了一层 `result`（别直接 `.get('tools')` ✓）
        result = listing.get('result')
        if not isinstance(result, dict):
            result = listing
        rows = result.get('tools') or []
        self.tools = [row for row in rows if isinstance(row, dict)]
        return True

    def stop(self) -> None:
        proc, self.proc = self.proc, None
        self.tools = []
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:                                    # noqa: BLE001
            try:
                proc.kill()
            except Exception:                                # noqa: BLE001
                pass

    # ------------------------------------------------------------ 协议
    def _send(self, payload: Dict[str, Any]) -> bool:
        proc = self.proc
        if proc is None or proc.stdin is None:
            return False
        try:
            proc.stdin.write(json.dumps(payload, ensure_ascii=False) + '\n')
            proc.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    def _notify(self, method: str, params: Dict[str, Any]) -> None:
        self._send({'jsonrpc': '2.0', 'method': method, 'params': params})

    def _request(self, method: str, params: Dict[str, Any],
                 timeout: float = TIMEOUT) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._send({'jsonrpc': '2.0', 'id': self._next_id(),
                               'method': method, 'params': params}):
                return None
            return self._read_reply(float(timeout))

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _read_reply(self, timeout: float) -> Optional[Dict[str, Any]]:
        """读到「有 result / error 的那条」为止（通知直接跳过 ✓）"""
        proc = self.proc
        if proc is None or proc.stdout is None:
            return None
        deadline = time.time() + max(1.0, timeout)
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                return None
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except ValueError:
                continue
            if not isinstance(payload, dict):
                continue
            if 'result' in payload or 'error' in payload:
                return payload
        return None

    # ------------------------------------------------------------ 调用
    def call(self, tool: str, arguments: Dict[str, Any]) -> str:
        if not self.start():
            return f'外部 MCP server `{self.name}` 起不来（命令：{self.command}）'
        reply = self._request('tools/call', {'name': tool,
                                            'arguments': arguments or {}})
        if reply is None:
            return f'外部 MCP server `{self.name}` 没有响应'
        if isinstance(reply.get('error'), dict):
            return (f'外部 MCP 调用失败：'
                    f"{reply['error'].get('message') or reply['error']}")
        result = reply.get('result') or {}
        content = result.get('content') if isinstance(result, dict) else None
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    parts.append(str(item.get('text') or ''))
            if parts:
                return '\n'.join(parts)
        return json.dumps(result, ensure_ascii=False)[:4000]


# ---------------------------------------------------------------- 注册表
def client_for(name: str) -> Optional[McpClient]:
    key = str(name or '')
    config = servers()
    entry = config.get(key)
    if not entry:
        return None
    with _LOCK:
        known = _CLIENTS.get(key)
        if known is not None:
            return known
        client = McpClient(key, str(entry.get('command') or ''),
                           entry.get('args') or [], entry.get('env') or {})
        _CLIENTS[key] = client
        return client


def specs(force: bool = False) -> List[Dict[str, Any]]:
    """外部 server 的工具 → OpenAI function 定义（启动失败就跳过 ✓）"""
    global _SPECS, _SPECS_AT
    with _LOCK:
        fresh = (_SPECS is not None
                 and time.time() - float(_SPECS_AT or 0.0) < SPECS_TTL)
        if fresh and not force:
            return list(_SPECS)
        rows: List[Dict[str, Any]] = []
        for name in servers():
            client = client_for(name)
            if client is None or not client.start():
                continue
            for tool in client.tools:
                tool_name = str(tool.get('name') or '')
                if not tool_name:
                    continue
                rows.append({
                    'type': 'function',
                    'function': {
                        'name': f'{PREFIX}{name}__{tool_name}',
                        'description': f"[MCP:{name}] "
                                       f"{tool.get('description') or tool_name}",
                        'parameters': tool.get('inputSchema')
                        or {'type': 'object', 'properties': {}},
                    },
                })
        _SPECS = rows
        _SPECS_AT = time.time()
        return list(rows)


def names() -> List[str]:
    return [spec['function']['name'] for spec in specs()]


def call_tool(full_name: str, arguments: Dict[str, Any]) -> str:
    """`mcp__<server>__<tool>` → 转发给对应的外部 server ✓"""
    text = str(full_name or '')
    if not text.startswith(PREFIX):
        return f'不是外部 MCP 工具：{text}'
    rest = text[len(PREFIX):]
    if '__' not in rest:
        return f'工具名不合法：{text}'
    server, tool = rest.split('__', 1)
    client = client_for(server)
    if client is None:
        return f'没有配置外部 MCP server：{server}（在 mcp.json 里加）'
    return client.call(tool, arguments or {})


def stop_all() -> None:
    """关掉所有外部 server 子进程（desk 退出时 ✓）"""
    global _SPECS, _SPECS_AT
    with _LOCK:
        clients = list(_CLIENTS.values())
        _CLIENTS.clear()
        _SPECS = None
        _SPECS_AT = 0.0
    for client in clients:
        client.stop()
