"""极简 LSP 服务（**自研，零第三方依赖**）：jedi 提供智能 + 手写 WebSocket。

为什么不用 `jedi-language-server` / `pylsp`？
  * 它们要额外装包（`pygls` 等），desk 是**离线可用**的产品，不能指望用户联网装；
  * 我们只要 LSP 里很小的一个子集：**补全 / 悬停 / 跳转定义 / 引用 / 签名 / 诊断**，
    这些 jedi + `compile()` 就能给，自己实现反而更可控 ✓

结构：

```
CM6 (codemirror-languageserver)
   │  ws://127.0.0.1:<port>
   ▼
LspService（本文件）
   ├─ _WSConnection  手写 WebSocket（握手 / 掩码 / 分片 / ping-pong）
   └─ _LanguageEngine  jedi 补全 / 悬停 / 定义 / 引用 / 签名 + compile 诊断
```

设计要点：
  * **只监听 127.0.0.1**，随机端口，`allow_reuse_address`；
  * 一个连接一个线程（编辑器只开一个连接）；
  * 文档内容保存在内存里（`didOpen` / `didChange` 全量同步），
    jedi 每次请求现建 `Script`（几毫秒），不做常驻缓存，避免脏数据；
  * 诊断用 `compile()`：语法错误 → `severity=1`，带行列 ✓
  * 位置换算：LSP 是 0 基 + **UTF-16 code unit**，jedi 是 1 基行 + 0 基字符，
    这里统一走 `_to_lsp` / `_from_lsp`（中文注释也不会错位 ✓）。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import socketserver
import struct
import threading
import traceback
from typing import Any, Dict, List, Optional, Tuple

try:                                                     # jedi 是可选依赖
    import jedi
except Exception:                                        # noqa: BLE001
    jedi = None

#: WebSocket 握手用的固定 GUID（RFC 6455）
_WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

#: jedi 的 `name.type` → LSP `CompletionItemKind`
_KIND = {
    'module': 9, 'class': 7, 'function': 3, 'method': 2, 'instance': 6,
    'param': 6, 'property': 10, 'statement': 15, 'keyword': 14, 'path': 17,
}

#: 最多返回多少条补全（jedi 有时给几百条）
MAX_COMPLETIONS = 200

#: ruff 可执行文件路径缓存（找不到就是 None，只探一次 ✓）
_RUFF_EXE: Optional[str] = None
_RUFF_PROBED = False


def _ruff_exe() -> Optional[str]:
    """找 `ruff`（PATH / 同目录）；没有就返回 None ✓"""
    global _RUFF_EXE, _RUFF_PROBED
    if _RUFF_PROBED:
        return _RUFF_EXE
    _RUFF_PROBED = True
    import shutil
    try:
        _RUFF_EXE = shutil.which('ruff')
    except Exception:                                        # noqa: BLE001
        _RUFF_EXE = None
    return _RUFF_EXE


# --------------------------------------------------------------------- 工具
def _to_lsp(text: str, line: int, column: int) -> Tuple[int, int]:
    """jedi 位置（1 基行 / 0 基字符）→ LSP 位置（0 基行 / UTF-16 列）"""
    lines = text.splitlines() or ['']
    index = max(0, min(len(lines) - 1, int(line) - 1))
    raw = lines[index] if lines else ''
    col = max(0, min(len(raw), int(column)))
    return index, len(raw[:col].encode('utf-16-le')) // 2


def _from_lsp(text: str, line: int, character: int) -> Tuple[int, int]:
    """LSP 位置 → jedi 位置（1 基行 / 0 基字符）"""
    lines = text.splitlines() or ['']
    index = max(0, min(len(lines) - 1, int(line)))
    raw = lines[index] if lines else ''
    # UTF-16 列 → 字符列
    count = 0
    col = 0
    for char in raw:
        if count >= character:
            break
        count += 2 if len(char.encode('utf-16-le')) > 2 else 1
        col += 1
    return index + 1, col


def _symbol(name: str, kind: int, node, depth: int) -> Dict[str, Any]:
    """ast 节点 → LSP DocumentSymbol（带 range / selectionRange ✓）"""
    start = max(0, int(getattr(node, 'lineno', 1)) - 1)
    end = max(start, int(getattr(node, 'end_lineno', start + 1)) - 1)
    col = int(getattr(node, 'col_offset', 0))
    return {
        'name': str(name),
        'kind': kind,
        'depth': depth,
        'range': {'start': {'line': start, 'character': col},
                  'end': {'line': end, 'character': 0}},
        'selectionRange': {'start': {'line': start, 'character': col},
                           'end': {'line': start,
                                   'character': col + len(str(name))}},
    }


def _uri_to_path(uri: str) -> str:
    text = str(uri or '')
    if text.startswith('file://'):
        text = text[7:]
    if text.startswith('/') and len(text) > 2 and text[2] == ':':
        text = text[1:]                        # /C:/xxx → C:/xxx
    return os.path.normpath(text)


def _path_to_uri(path: str) -> str:
    real = os.path.abspath(path)
    if os.name == 'nt':
        return 'file:///' + real.replace('\\', '/')
    return 'file://' + real.replace('\\', '/')


def available() -> Dict[str, Any]:
    """jedi 在不在？给前端显示状态用 ✓"""
    version = getattr(jedi, '__version__', '') if jedi is not None else ''
    return {'ok': jedi is not None, 'jedi': version,
            'reason': '' if jedi is not None
            else '缺少 jedi（pip install jedi）'}


# ------------------------------------------------------------------ WebSocket
class _WSConnection:
    """一条 WebSocket 连接（只支持文本帧 + 分片 + ping/pong ✓）"""

    def __init__(self, sock: socket.socket, rfile):
        self.sock = sock
        self.rfile = rfile
        self.closed = False
        self._lock = threading.Lock()

    # ---- 握手
    def handshake(self) -> bool:
        try:
            data = b''
            while b'\r\n\r\n' not in data:
                chunk = self.rfile.read(1)
                if not chunk:
                    return False
                data += chunk
                if len(data) > 65536:
                    return False
            text = data.decode('latin-1')
            key = ''
            for line in text.split('\r\n'):
                if line.lower().startswith('sec-websocket-key:'):
                    key = line.split(':', 1)[1].strip()
                    break
            if not key:
                return False
            accept = base64.b64encode(hashlib.sha1(
                (key + _WS_GUID).encode('latin-1')).digest()).decode('latin-1')
            self.sock.sendall(
                ('HTTP/1.1 101 Switching Protocols\r\n'
                 'Upgrade: websocket\r\n'
                 'Connection: Upgrade\r\n'
                 f'Sec-WebSocket-Accept: {accept}\r\n\r\n').encode('latin-1'))
            return True
        except OSError:
            return False

    # ---- 读
    def _read_exact(self, count: int) -> bytes:
        data = b''
        while len(data) < count:
            chunk = self.rfile.read(count - len(data))
            if not chunk:
                raise ConnectionError('closed')
            data += chunk
        return data

    def read_message(self) -> Optional[str]:
        """读到一条完整文本消息；连接关闭返回 None"""
        buffer = b''
        while True:
            head = self._read_exact(2)
            first, second = head[0], head[1]
            opcode = first & 0x0F
            fin = bool(first & 0x80)
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack('>H', self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack('>Q', self._read_exact(8))[0]
            mask = self._read_exact(4) if masked else b''
            payload = self._read_exact(length) if length else b''
            if mask:
                payload = bytes(value ^ mask[i % 4]
                                for i, value in enumerate(payload))
            if opcode == 0x8:                       # close
                return None
            if opcode == 0x9:                       # ping → pong
                self.send_frame(payload, opcode=0xA)
                continue
            if opcode == 0xA:                       # pong
                continue
            buffer += payload
            if fin:
                try:
                    return buffer.decode('utf-8')
                except UnicodeDecodeError:
                    return buffer.decode('utf-8', 'replace')

    # ---- 写
    def send_frame(self, payload: bytes, opcode: int = 0x1) -> None:
        if self.closed:
            return
        header = bytearray([0x80 | opcode])
        size = len(payload)
        if size < 126:
            header.append(size)
        elif size < 65536:
            header.append(126)
            header += struct.pack('>H', size)
        else:
            header.append(127)
            header += struct.pack('>Q', size)
        try:
            with self._lock:
                self.sock.sendall(bytes(header) + payload)
        except OSError:
            self.closed = True

    def send_json(self, payload: Dict[str, Any]) -> None:
        self.send_frame(json.dumps(payload, ensure_ascii=False).encode('utf-8'))

    def close(self) -> None:
        self.closed = True
        try:
            self.send_frame(b'', opcode=0x8)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


# --------------------------------------------------------------------- 引擎
class _LanguageEngine:
    """jedi + compile 提供 LSP 的几项能力 ✓"""

    def __init__(self, root: str = ''):
        self.root = root or os.getcwd()
        try:
            self.project = jedi.Project(self.root) if jedi else None
        except Exception:                                    # noqa: BLE001
            self.project = None

    def _script(self, text: str, path: str):
        if jedi is None:
            return None
        # 文件还没落盘（新建 / 未保存）→ 不传 path，jedi 直接吃内存里的代码 ✓
        use_path = path if (path and os.path.isfile(path)) else None
        try:
            return jedi.Script(code=text, path=use_path,
                               project=self.project)
        except Exception:                                    # noqa: BLE001
            return None

    # ---- 诊断
    def diagnostics(self, text: str, path: str) -> List[Dict[str, Any]]:
        """语法错（compile）+ **ruff 检查**（未使用导入 / 未定义名 / 行长…）✓"""
        errors = self._syntax_diagnostics(text, path)
        if errors:                          # 语法都不对就别跑 ruff 了 ✓
            return errors
        return self._ruff_diagnostics(text, path)

    def _syntax_diagnostics(self, text: str,
                            path: str) -> List[Dict[str, Any]]:
        try:
            compile(text, path or '<editor>', 'exec')
            return []
        except SyntaxError as error:
            lines = text.splitlines() or ['']
            line = max(0, (error.lineno or 1) - 1)
            line = min(line, len(lines) - 1)
            raw = lines[line] if lines else ''
            col = max(0, min(len(raw), (error.offset or 1) - 1))
            # LSP 的 end **不能超过行尾**，否则客户端会丢弃这条诊断 ✓
            span = 1 if col < len(raw) else 0
            return [{
                'range': {'start': {'line': line, 'character': col},
                          'end': {'line': line, 'character': col + span}},
                'severity': 1, 'source': 'python',
                'message': str(error.msg or 'syntax error'),
            }]
        except (ValueError, RecursionError) as error:        # 空字节等
            return [{
                'range': {'start': {'line': 0, 'character': 0},
                          'end': {'line': 0, 'character': 1}},
                'severity': 1, 'source': 'python',
                'message': str(error)[:200],
            }]

    def _ruff_diagnostics(self, text: str,
                          path: str) -> List[Dict[str, Any]]:
        """`ruff check --output-format=json` → LSP 诊断（warning / error）✓

        没有 ruff 就返回空（只保留语法检查），完全静默降级 ✓
        """
        exe = _ruff_exe()
        if not exe or not str(text or '').strip():
            return []
        # 规则集：只报**真问题**（语法 / 未定义名 / 未使用导入 / 语句与导入位置）。
        # 风格类（C4「dict() 改字面量」、RUF012「可变类属性」、E501 行长…）
        # 默认**不报** —— 它们会把 `params = dict(...)` 这种正常写法标成问题 ✗
        rules = os.environ.get('MINIBT_DESK_RUFF_SELECT') or 'E4,E7,E9,F'
        # `from minibt import *` 是 minibt 脚本的常规写法 →
        # F403/F405（星号导入）和 E402（导入不在文件顶部）都是**误报**，屏蔽 ✓
        ignores = os.environ.get('MINIBT_DESK_RUFF_IGNORE') or 'E402,F403,F405'
        import json as _json
        import subprocess
        filename = path or 'editor.py'
        try:
            completed = subprocess.run(
                [exe, 'check', '--output-format=json', '--isolated',
                 '--select', rules, '--ignore', ignores,
                 '--stdin-filename', filename, '-'],
                input=text, capture_output=True, text=True, timeout=12,
                encoding='utf-8', errors='replace',
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, subprocess.SubprocessError):
            return []
        payload = (completed.stdout or '').strip()
        if not payload:
            return []
        try:
            items = _json.loads(payload)
        except ValueError:
            return []
        lines = text.splitlines() or ['']
        out: List[Dict[str, Any]] = []
        for item in items if isinstance(items, list) else []:
            try:
                location = item.get('location') or {}
                start_line = int(location.get('row') or 1) - 1
                start_col = int(location.get('column') or 1) - 1
                end = item.get('end_location') or {}
                end_line = int(end.get('row') or (start_line + 1)) - 1
                end_col = int(end.get('column') or (start_col + 1)) - 1
            except (TypeError, ValueError):
                continue
            start_line = max(0, min(start_line, len(lines) - 1))
            end_line = max(0, min(end_line, len(lines) - 1))
            if end_line < start_line:
                end_line = start_line
            code = str(item.get('code') or '')
            # `F8xx`（语法 / 未定义名）算错误，其余算警告 ✓
            severity = 1 if code.startswith(('F8', 'E9')) else 2
            message = str(item.get('message') or '')
            if code:
                message = f'{message}（{code}）'
            out.append({
                'range': {'start': {'line': start_line,
                                    'character': max(0, start_col)},
                          'end': {'line': end_line,
                                  'character': max(0, end_col)}},
                'severity': severity,
                'source': 'ruff',
                'code': code,
                'message': message,
            })
            if len(out) >= 200:
                break
        return out

    # ---- 补全
    def completion(self, text: str, path: str,
                   line: int, character: int) -> List[Dict[str, Any]]:
        script = self._script(text, path)
        if script is None:
            return []
        row, col = _from_lsp(text, line, character)
        try:
            names = script.complete(row, col)
        except Exception:                                    # noqa: BLE001
            return []
        items: List[Dict[str, Any]] = []
        for name in names[:MAX_COMPLETIONS]:
            item: Dict[str, Any] = {
                'label': getattr(name, 'name', ''),
                'kind': _KIND.get(str(getattr(name, 'type', '')),
                                  15),
            }
            sig = ''
            try:
                sig = str(name.name)
                if getattr(name, 'type', '') in ('function', 'method', 'class'):
                    sig = f'{name.name}(…)'
                detail = getattr(name, 'description', '') or ''
                if detail:
                    item['detail'] = detail
            except Exception:                                # noqa: BLE001
                pass
            doc = ''
            try:
                doc = name.docstring(raw=False) or ''
            except Exception:                                # noqa: BLE001
                doc = ''
            if doc:
                item['documentation'] = {'kind': 'markdown',
                                         'value': doc[:4000]}
            try:                                             # 插入文本带括号
                if getattr(name, 'type', '') in ('function', 'class'):
                    item['insertText'] = f'{name.name}()'
                    item['insertTextFormat'] = 2             # snippet
            except Exception:                                # noqa: BLE001
                pass
            items.append(item)
        return items

    # ---- 悬停
    def hover(self, text: str, path: str, line: int,
              character: int) -> Optional[Dict[str, Any]]:
        script = self._script(text, path)
        if script is None:
            return None
        row, col = _from_lsp(text, line, character)
        docs: List[str] = []
        try:
            helps = script.help(row, col)
        except Exception:                                    # noqa: BLE001
            helps = []
        if not isinstance(helps, list):
            helps = [helps] if helps else []
        for help_item in helps:
            try:
                signature = help_item.full_name or help_item.name or ''
            except Exception:                                # noqa: BLE001
                signature = ''
            try:
                body = help_item.docstring(raw=False) or ''
            except Exception:                                # noqa: BLE001
                body = ''
            if signature or body:
                docs.append(f'```python\n{signature}\n```\n\n{body}'.strip())
        if not docs:
            try:
                inferred = script.infer(row, col)
            except Exception:                                # noqa: BLE001
                inferred = []
            for item in inferred or []:
                sig = f'{item.name}: {item.type}'
                body = ''
                try:
                    body = item.docstring(raw=False) or ''
                except Exception:                            # noqa: BLE001
                    body = ''
                docs.append(f'```python\n{sig}\n```\n\n{body}'.strip())
        if not docs:
            return None
        return {'contents': {'kind': 'markdown', 'value': '\n\n---\n\n'.join(docs)}}

    # ---- 跳转定义 / 引用
    def _locations(self, results, text: str,
                   fallback: str = '') -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for item in results or []:
            try:
                # 同一文件里的定义 `module_path` 是 None → 用当前文件 ✓
                path = str(item.module_path or fallback or '')
                if not path:
                    continue
                line = int(item.line or 1) - 1
                col = int(item.column or 0)
                name = str(getattr(item, 'name', '') or '')
                out.append({
                    'uri': _path_to_uri(path),
                    'range': {'start': {'line': line, 'character': col},
                              'end': {'line': line,
                                      'character': col + max(1, len(name))}},
                })
            except Exception:                                # noqa: BLE001
                continue
        return out

    def definition(self, text: str, path: str, line: int,
                   character: int) -> List[Dict[str, Any]]:
        script = self._script(text, path)
        if script is None:
            return []
        row, col = _from_lsp(text, line, character)
        try:
            return self._locations(script.goto(row, col), text, path)
        except Exception:                                    # noqa: BLE001
            return []

    def references(self, text: str, path: str, line: int,
                   character: int) -> List[Dict[str, Any]]:
        script = self._script(text, path)
        if script is None:
            return []
        row, col = _from_lsp(text, line, character)
        try:
            return self._locations(script.get_references(row, col), text, path)
        except Exception:                                    # noqa: BLE001
            return []

    # ---- 文档符号（大纲 ✓）
    def symbols(self, text: str) -> List[Dict[str, Any]]:
        """`textDocument/documentSymbol`：用 `ast` 给出 类 / 函数 / 方法 ✓"""
        import ast

        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []
        kinds = {'class': 5, 'function': 12, 'method': 6}     # LSP SymbolKind
        out: List[Dict[str, Any]] = []

        def walk(node, depth: int, method: bool = False) -> None:
            for child in getattr(node, 'body', []):
                name = getattr(child, 'name', None)
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))                         and name:
                    kind = kinds['method'] if method else kinds['function']
                    out.append(_symbol(name, kind, child, depth))
                    walk(child, depth + 1, method=False)
                elif isinstance(child, ast.ClassDef) and name:
                    out.append(_symbol(name, kinds['class'], child, depth))
                    walk(child, depth + 1, method=True)
                elif isinstance(child, (ast.If, ast.For, ast.While, ast.With,
                                        ast.Try)):
                    walk(child, depth, method)     # 块里的定义也算 ✓
                for handler in getattr(child, 'handlers', []) or []:
                    walk(handler, depth, method)

        walk(tree, 0)
        return out

    # ---- 工作区符号（跨文件 class / def 搜索 ✓）
    def workspace_symbols(self, query: str = '') -> List[Dict[str, Any]]:
        """扫 `root` 下的 .py，按名字模糊匹配（最多 300 条）✓

        结果带 `location`（uri + range），前端点一下就能打开并跳行 ✓
        """
        import ast

        folder = self.root or os.getcwd()
        text = str(query or '').strip().lower()
        out: List[Dict[str, Any]] = []
        # 递归扫（跳过 __pycache__ / 隐藏目录；最多 400 个文件 ✓）
        files: List[str] = []
        for current, dirs, names in os.walk(folder):
            dirs[:] = [item for item in dirs
                       if not item.startswith(('.', '__'))]
            for name in sorted(names):
                if name.lower().endswith(('.py', '.pyi')):
                    files.append(os.path.join(current, name))
            if len(files) >= 400:
                break
        for path in files[:400]:
            try:
                with open(path, encoding='utf-8') as handle:
                    source = handle.read()
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    kind = 5
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    kind = 12
                else:
                    continue
                label = node.name
                if text and text not in label.lower():
                    continue
                start = max(0, int(getattr(node, 'lineno', 1)) - 1)
                out.append({
                    'name': label,
                    'kind': kind,
                    'location': {
                        'uri': _path_to_uri(path),
                        'range': {'start': {'line': start,
                                            'character': 0},
                                  'end': {'line': start,
                                          'character': len(label)}},
                    },
                    'containerName': os.path.basename(path),
                })
                if len(out) >= 300:
                    return out
        return out

    # ---- 折叠范围（类 / 函数 / 多行块 ✓）
    def folding(self, text: str) -> List[Dict[str, Any]]:
        """`textDocument/foldingRange`：按 `ast` 给块范围，另加 `#region` ✓"""
        import ast

        out: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                start = getattr(node, 'lineno', None)
                end = getattr(node, 'end_lineno', None)
                if not start or not end or end <= start:
                    continue
                if not isinstance(node, (ast.ClassDef, ast.FunctionDef,
                                         ast.AsyncFunctionDef, ast.If, ast.For,
                                         ast.While, ast.With, ast.Try,
                                         ast.Import, ast.ImportFrom,
                                         ast.Assign, ast.AnnAssign,
                                         ast.List, ast.Dict, ast.Tuple)):
                    continue
                out.append({'startLine': start - 1, 'endLine': end - 1})
        # `#region` / `#endregion`（VS Code 风格 ✓）
        stack: List[int] = []
        for index, line in enumerate(text.splitlines()):
            if line.strip().startswith('#region') or line.strip().startswith('# region'):
                stack.append(index)
            elif (line.strip().startswith('#endregion')
                  or line.strip().startswith('# endregion')) and stack:
                begin = stack.pop()
                out.append({'startLine': begin, 'endLine': index,
                            'kind': 'region'})
        # 去重（同一范围只留一份）
        unique: Dict[tuple, Dict[str, Any]] = {}
        for item in out:
            key = (item['startLine'], item['endLine'])
            if key[1] > key[0]:
                unique[key] = item
        return list(unique.values())

    # ---- 格式化（black / yapf / 保守清理 ✓）
    def formatting(self, text: str) -> List[Dict[str, Any]]:
        """`textDocument/formatting`：整篇替换（和「格式化」按钮同一套工具 ✓）"""
        from . import explorer as _fs
        result = _fs.format_python(text)
        formatted = str(result.get('text') or '')
        if not result.get('ok') or formatted == text:
            return []
        lines = (text.splitlines() or [''])
        return [{
            'range': {'start': {'line': 0, 'character': 0},
                      'end': {'line': len(lines) - 1,
                              'character': len(lines[-1])}},
            'newText': formatted,
        }]

    # ---- 重命名（jedi 引用 → 同文件 TextEdits ✓）
    def rename(self, text: str, path: str, line: int, character: int,
               new_name: str) -> Optional[Dict[str, Any]]:
        script = self._script(text, path)
        if script is None or not str(new_name or '').strip():
            return None
        row, col = _from_lsp(text, line, character)
        try:
            # `scope='file'`：只在当前文件里找引用（跨文件重命名要改磁盘，
            # 风险太大；而且全项目搜一次要几百毫秒 ✗）
            references = script.get_references(row, col, scope='file')
        except TypeError:                                    # 老版本 jedi
            references = script.get_references(row, col)
        except Exception:                                    # noqa: BLE001
            return None
        edits: List[Dict[str, Any]] = []
        lines = text.splitlines() or ['']
        for item in references or []:
            try:
                item_line = int(item.line or 1) - 1
                item_col = int(item.column or 0)
                old = str(getattr(item, 'name', '') or '')
            except Exception:                                # noqa: BLE001
                continue
            if not old or item_line < 0 or item_line >= len(lines):
                continue
            if len(edits) >= 500:                            # 兜底上限
                break
            # 只在**当前文件**里改（跨文件重命名要动磁盘，风险太大 ✗）
            if str(item.module_path or '') and path and                     os.path.abspath(str(item.module_path)) !=                     os.path.abspath(path):
                continue
            edits.append({
                'range': {'start': {'line': item_line,
                                    'character': item_col},
                          'end': {'line': item_line,
                                  'character': item_col + len(old)}},
                'newText': str(new_name),
            })
        if not edits:
            return None
        uri = _path_to_uri(path) if path else ''
        return {'changes': {uri: edits} if uri else {}}

    def prepare_rename(self, text: str, path: str, line: int,
                       character: int) -> Optional[Dict[str, Any]]:
        """把光标处的标识符回给客户端（预填输入框 ✓）"""
        lines = text.splitlines() or ['']
        if line < 0 or line >= len(lines):
            return None
        raw = lines[line]
        index = min(len(raw), max(0, character))
        start = index
        while start > 0 and (raw[start - 1].isalnum() or raw[start - 1] == '_'):
            start -= 1
        end = index
        while end < len(raw) and (raw[end].isalnum() or raw[end] == '_'):
            end += 1
        word = raw[start:end]
        if not word or word[0].isdigit():
            return None
        return {'range': {'start': {'line': line, 'character': start},
                          'end': {'line': line, 'character': end}},
                'placeholder': word}

    # ---- 签名帮助
    def signature(self, text: str, path: str, line: int,
                  character: int) -> Optional[Dict[str, Any]]:
        script = self._script(text, path)
        if script is None:
            return None
        row, col = _from_lsp(text, line, character)
        try:
            signatures = script.get_signatures(row, col)
        except Exception:                                    # noqa: BLE001
            return None
        if not signatures:
            return None
        items = []
        for sig in signatures[:10]:
            try:
                params = [{'label': str(param.name)}
                          for param in (sig.params or [])]
            except Exception:                                # noqa: BLE001
                params = []
            items.append({
                'label': str(getattr(sig, 'name', '') or '') + '(...)',
                'parameters': params,
                'documentation': {'kind': 'markdown',
                                  'value': (sig.docstring(raw=False) or '')[:2000]},
            })
        return {'signatures': items, 'activeSignature': 0,
                'activeParameter': 0}


# ---------------------------------------------------------------- 服务主体
class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:                            # noqa: D401
        service: 'LspService' = self.server.service       # type: ignore[attr-defined]
        conn = _WSConnection(self.request, self.request.makefile('rb'))
        if not conn.handshake():
            return
        service._serve(conn)


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class LspService:
    """LSP 服务：`start()` 后拿到 `ws://127.0.0.1:<port>` ✓"""

    def __init__(self, root: str = ''):
        self.root = root
        self._server: Optional[_Server] = None
        self._thread: Optional[threading.Thread] = None
        self.port = 0
        self.engine = _LanguageEngine(root)
        self._documents: Dict[str, Dict[str, str]] = {}
        self._lock = threading.Lock()
        self._connection: Optional[_WSConnection] = None
        #: 每个文档一个诊断防抖定时器 ✓
        self._diag_timers: Dict[str, threading.Timer] = {}
        self.status = 'idle'
        self.error = ''

    # ---- 生命周期
    def start(self) -> Dict[str, Any]:
        if self._server is not None:
            return self.info()
        if jedi is None:
            self.status = 'missing'
            self.error = available()['reason']
            return self.info()
        try:
            self._server = _Server(('127.0.0.1', 0), _Handler)
            self._server.service = self                    # type: ignore[attr-defined]
            self.port = int(self._server.server_address[1])
            self._thread = threading.Thread(
                target=self._server.serve_forever, name='desk-lsp',
                daemon=True)
            self._thread.start()
            self.status = 'ready'
        except OSError as error:
            self.status = 'error'
            self.error = f'LSP 端口占用：{error!r}'
        return self.info()

    def stop(self) -> None:
        with self._lock:
            for timer in self._diag_timers.values():
                try:
                    timer.cancel()
                except Exception:                            # noqa: BLE001
                    pass
            self._diag_timers.clear()
        try:
            if self._connection is not None:
                self._connection.close()
        except Exception:                                    # noqa: BLE001
            pass
        self._connection = None
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:                                # noqa: BLE001
                pass
        self._server = None
        self.status = 'stopped'

    def info(self) -> Dict[str, Any]:
        return {
            'type': 'lsp', 'status': self.status,
            'port': self.port, 'root': self.root,
            'url': f'ws://127.0.0.1:{self.port}' if self.port else '',
            'jedi': (getattr(jedi, '__version__', '') if jedi else ''),
            'error': self.error,
        }

    # ---- 连接循环
    def _serve(self, conn: _WSConnection) -> None:
        self._connection = conn
        try:
            while True:
                raw = conn.read_message()
                if raw is None:
                    break
                try:
                    message = json.loads(raw)
                except ValueError:
                    continue
                self._handle(conn, message)
        except (ConnectionError, OSError):
            pass
        finally:
            conn.close()
            if self._connection is conn:
                self._connection = None

    # ---- JSON-RPC
    def _reply(self, conn: _WSConnection, request: Dict[str, Any],
               result: Any) -> None:
        conn.send_json({'jsonrpc': '2.0', 'id': request.get('id'),
                        'result': result})

    def _error(self, conn: _WSConnection, request: Dict[str, Any],
               message: str) -> None:
        conn.send_json({'jsonrpc': '2.0', 'id': request.get('id'),
                        'error': {'code': -32603, 'message': message}})

    def _notify(self, conn: _WSConnection, method: str,
                params: Dict[str, Any]) -> None:
        conn.send_json({'jsonrpc': '2.0', 'method': method, 'params': params})

    def _document(self, uri: str) -> Tuple[str, str]:
        with self._lock:
            item = self._documents.get(uri) or {'text': '', 'path': ''}
        return item['text'], item['path']

    def _publish_diagnostics(self, conn: _WSConnection, uri: str,
                             delay: float = 0.3) -> None:
        """算诊断并推给客户端（**防抖**：最后一次改动 300ms 后才跑 ruff ✓）"""
        with self._lock:
            timer = self._diag_timers.pop(uri, None)
        if timer is not None:
            try:
                timer.cancel()
            except Exception:                                # noqa: BLE001
                pass

        def run() -> None:
            text, path = self._document(uri)
            try:
                problems = self.engine.diagnostics(text, path)
            except Exception:                                # noqa: BLE001
                return
            try:
                self._notify(conn, 'textDocument/publishDiagnostics', {
                    'uri': uri, 'diagnostics': problems,
                })
            except Exception:                                # noqa: BLE001
                pass

        if delay <= 0:
            run()
            return
        timer = threading.Timer(delay, run)
        timer.daemon = True
        with self._lock:
            self._diag_timers[uri] = timer
        timer.start()

    def _handle(self, conn: _WSConnection, message: Dict[str, Any]) -> None:
        method = str(message.get('method') or '')
        params = message.get('params') or {}
        has_id = 'id' in message
        try:
            if method == 'initialize':
                root = str((params.get('rootUri') or '')).replace('file://', '')
                if not self.root and root:
                    self.root = _uri_to_path(root)
                    self.engine = _LanguageEngine(self.root)
                self._reply(conn, message, {
                    'capabilities': {
                        'textDocumentSync': 1,          # 全量同步
                        'completionProvider': {
                            'triggerCharacters': ['.', '(', ' ', ':'],
                            'resolveProvider': False,
                        },
                        'hoverProvider': True,
                        'definitionProvider': True,
                        'referencesProvider': True,
                        'signatureHelpProvider': {
                            'triggerCharacters': ['(', ','],
                        },
                        'documentSymbolProvider': True,
                        'workspaceSymbolProvider': True,
                        'foldingRangeProvider': True,
                        'documentFormattingProvider': True,
                        'renameProvider': {'prepareProvider': True},
                    },
                    'serverInfo': {
                        'name': 'minibt-desk-jedi',
                        'version': getattr(jedi, '__version__', '?')
                        if jedi else '?',
                    },
                })
                self.status = 'connected'
                return
            if method in ('initialized', 'workspace/didChangeConfiguration',
                          'textDocument/didSave', '$/cancelRequest',
                          'workspace/didChangeWatchedFiles'):
                return
            if method == 'shutdown':
                if has_id:
                    self._reply(conn, message, None)
                return
            if method == 'exit':
                conn.close()
                return
            if method == 'textDocument/didOpen':
                doc = params.get('textDocument') or {}
                uri = str(doc.get('uri') or '')
                with self._lock:
                    self._documents[uri] = {
                        'text': str(doc.get('text') or ''),
                        'path': _uri_to_path(uri),
                    }
                self._publish_diagnostics(conn, uri)
                return
            if method == 'textDocument/didChange':
                doc = params.get('textDocument') or {}
                uri = str(doc.get('uri') or '')
                changes = params.get('contentChanges') or []
                text = ''
                if changes:
                    text = str((changes[-1] or {}).get('text') or '')
                with self._lock:
                    previous = self._documents.get(uri) or {}
                    self._documents[uri] = {
                        'text': text,
                        'path': previous.get('path') or _uri_to_path(uri),
                    }
                self._publish_diagnostics(conn, uri)
                return
            if method == 'textDocument/didClose':
                doc = params.get('textDocument') or {}
                uri = str(doc.get('uri') or '')
                with self._lock:
                    self._documents.pop(uri, None)
                self._notify(conn, 'textDocument/publishDiagnostics',
                             {'uri': uri, 'diagnostics': []})
                return
            # ---- 智能功能：都要 (uri, position)
            if method.startswith('textDocument/'):
                doc = params.get('textDocument') or {}
                uri = str(doc.get('uri') or '')
                position = params.get('position') or {}
                text, path = self._document(uri)
                line = int(position.get('line') or 0)
                character = int(position.get('character') or 0)
                if method == 'textDocument/completion':
                    items = self.engine.completion(text, path, line, character)
                    self._reply(conn, message,
                                {'isIncomplete': False, 'items': items})
                    return
                if method == 'textDocument/hover':
                    self._reply(conn, message,
                                self.engine.hover(text, path, line, character))
                    return
                if method == 'textDocument/definition':
                    self._reply(conn, message,
                                self.engine.definition(text, path, line,
                                                       character))
                    return
                if method == 'textDocument/references':
                    self._reply(conn, message,
                                self.engine.references(text, path, line,
                                                       character))
                    return
                if method == 'textDocument/signatureHelp':
                    self._reply(conn, message,
                                self.engine.signature(text, path, line,
                                                      character))
                    return
                if method == 'textDocument/documentSymbol':
                    self._reply(conn, message, self.engine.symbols(text))
                    return
                if method == 'textDocument/foldingRange':
                    self._reply(conn, message, self.engine.folding(text))
                    return
                if method == 'textDocument/formatting':
                    self._reply(conn, message,
                                self.engine.formatting(text))
                    return
                if method == 'textDocument/prepareRename':
                    self._reply(conn, message,
                                self.engine.prepare_rename(text, path, line,
                                                           character))
                    return
                if method == 'textDocument/rename':
                    new_name = str((params.get('newName') or ''))
                    self._reply(conn, message,
                                self.engine.rename(text, path, line, character,
                                                   new_name))
                    return
            if method == 'workspace/symbol':
                query = str((params or {}).get('query') or '')
                if has_id:
                    self._reply(conn, message,
                                self.engine.workspace_symbols(query))
                return
            if has_id:                     # 其它请求一律回 null，避免客户端挂住
                self._reply(conn, message, None)
        except Exception as error:                           # noqa: BLE001
            traceback.print_exc()
            if has_id:
                self._error(conn, message, f'{error!r}')


# ------------------------------------------------------------------ 便捷入口
def serve_once(root: str = '') -> LspService:
    """给脚本 / 测试用：起一个服务并返回 ✓"""
    service = LspService(root)
    service.start()
    return service


if __name__ == '__main__':                               # 手测用
    import time
    item = serve_once(os.getcwd())
    print(json.dumps(item.info(), ensure_ascii=False))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        item.stop()
