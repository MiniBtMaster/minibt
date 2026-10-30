"""LSP（jedi）服务测试：WebSocket 握手 / JSON-RPC / 诊断 / 补全 ✓"""
from __future__ import annotations

import base64
import json
import os
import socket
import struct
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from minibt.desk import lsp as L  # noqa: E402


def _send(sock, obj):
    data = json.dumps(obj).encode()
    header = bytearray([0x81])
    size = len(data)
    if size < 126:
        header.append(0x80 | size)
    elif size < 65536:
        header.append(0x80 | 126)
        header += struct.pack('>H', size)
    else:
        header.append(0x80 | 127)
        header += struct.pack('>Q', size)
    mask = os.urandom(4)
    header += mask
    sock.sendall(bytes(header) + bytes(
        value ^ mask[i % 4] for i, value in enumerate(data)))


def _recv(sock):
    head = sock.recv(2)
    if len(head) < 2:
        return None
    length = head[1] & 0x7F
    if length == 126:
        length = struct.unpack('>H', sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack('>Q', sock.recv(8))[0]
    body = b''
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk:
            return None
        body += chunk
    return json.loads(body.decode())


def _call(sock, method, params, mid):
    _send(sock, {'jsonrpc': '2.0', 'id': mid, 'method': method,
                 'params': params})
    for _ in range(30):
        message = _recv(sock)
        if message is None:
            return None
        if message.get('id') == mid:
            return message
    return None


def _wait_notification(sock, method, tries=20):
    for _ in range(tries):
        message = _recv(sock)
        if message and message.get('method') == method:
            return message
    return None


def test_uri_helpers():
    converted = L._uri_to_path('file:///C:/a/b.py')
    assert converted.replace(os.sep, '/').endswith('a/b.py')
    assert 'C:' in converted
    uri = L._path_to_uri(os.path.join(ROOT, 'minibt', 'desk', 'lsp.py'))
    assert uri.startswith('file:///') and uri.endswith('lsp.py')
    text = 'x = 1\ny = 中文\n'
    # jedi（1 基行 / 字符列）↔ LSP（0 基行 / UTF-16 列）
    assert L._from_lsp(text, 1, 0) == (2, 0)
    assert L._to_lsp(text, 2, 4) == (1, 4)


def test_language_engine_diagnostics():
    engine = L._LanguageEngine(str(ROOT))
    assert engine.diagnostics('x = 1\n', 'a.py') == []
    problems = engine.diagnostics('class A(Strategy)\n    pass\n', 'a.py')
    assert problems and problems[0]['severity'] == 1
    assert problems[0]['message']
    # end 不能超过行尾（否则客户端会丢弃 ✓）
    start = problems[0]['range']['start']
    end = problems[0]['range']['end']
    line = 'class A(Strategy)'
    assert end['character'] <= len(line)
    assert start['line'] == 0 == end['line']


def test_language_engine_completion_and_hover():
    pytest.importorskip('jedi')
    engine = L._LanguageEngine(str(ROOT))
    source = ('import numpy as np\n\n\ndef add(a, b):\n'
              '    """加法"""\n    return a + b\n\n'
              'x = add(1, 2)\nnp.\n')
    items = engine.completion(source, 'a.py', 8, 3)
    assert len(items) > 10
    assert {'abs', 'add'} <= {item['label'] for item in items}
    hover = engine.hover(source, 'a.py', 7, 5)
    assert hover and 'add' in hover['contents']['value']
    locations = engine.definition(source, 'a.py', 7, 5)
    assert locations and locations[0]['range']['start']['line'] == 3


def test_websocket_end_to_end(tmp_path):
    pytest.importorskip('jedi')
    service = L.serve_once(str(tmp_path))
    try:
        assert service.status == 'ready', service.error
        sock = socket.create_connection(('127.0.0.1', service.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall((
            'GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nUpgrade: websocket\r\n'
            'Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n'
            'Sec-WebSocket-Version: 13\r\n\r\n' % key).encode())
        head = sock.recv(4096).decode('latin-1')
        assert '101' in head.split('\r\n')[0]

        reply = _call(sock, 'initialize', {'rootUri': None,
                                           'capabilities': {}}, 1)
        caps = reply['result']['capabilities']
        assert caps['hoverProvider'] is True
        assert caps['definitionProvider'] is True
        assert 'completionProvider' in caps
        _send(sock, {'jsonrpc': '2.0', 'method': 'initialized',
                     'params': {}})

        uri = 'file:///' + str(tmp_path / 'sample.py').replace(os.sep, '/')
        _send(sock, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen',
                     'params': {'textDocument': {
                         'uri': uri, 'languageId': 'python', 'version': 1,
                         'text': 'import numpy as np\nnp.\n'}}})
        note = _wait_notification(sock, 'textDocument/publishDiagnostics')
        assert note and note['params']['uri'] == uri

        reply = _call(sock, 'textDocument/completion', {
            'textDocument': {'uri': uri},
            'position': {'line': 1, 'character': 3}}, 2)
        items = reply['result']['items']
        assert len(items) > 10

        # 语法错 → 一帧诊断里带 severity=1
        _send(sock, {'jsonrpc': '2.0', 'method': 'textDocument/didChange',
                     'params': {'textDocument': {'uri': uri, 'version': 2},
                                'contentChanges': [
                                    {'text': 'class A(Strategy)\n    pass\n'}]}})
        note = _wait_notification(sock, 'textDocument/publishDiagnostics')
        assert note
        assert note['params']['diagnostics'][0]['severity'] == 1
        sock.close()
    finally:
        service.stop()
        assert service.status == 'stopped'
        time.sleep(0.05)


def test_desk_lsp_command():
    from minibt.desk.app import Desk

    class _Desk(Desk):
        def __init__(self):                       # 不连行情，只用 LSP ✓
            super().__init__(offline=True)
            self.patches = []
            self.push = lambda patch: self.patches.append(patch)
            self.push_log = lambda *a, **k: None

    desk = _Desk()
    desk._on_lsp_start({})
    patches = [p for p in desk.patches if p.get('type') == 'lsp']
    assert patches, '应该推一个 lsp 补丁'
    info = patches[-1]
    if info['status'] == 'ready':
        assert info['url'].startswith('ws://127.0.0.1:')
        assert info['port'] > 0
    else:                                          # 没装 jedi → 明确说明原因
        assert info['status'] in ('missing', 'error')
        assert info['error']
    desk.close()


def test_frontend_editor_wiring():
    """编辑器：LSP 地址 / 诊断 gutter / 状态徽标 / 用 withTransport ✓"""
    bundle = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-bundle.ts').read_text(
        encoding='utf-8')
    assert 'languageServerWithTransport' in bundle
    assert 'new LanguageServerClient' in bundle and 'WebSocketTransport' in bundle
    assert 'lintGutter()' in bundle
    assert 'onCapabilities' in bundle and 'onClose' in bundle
    assert "languageId: 'python'" in bundle
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert 'lsp?: () => { url: string; root: string } | undefined;' in panel
    assert 'data-lsp' in panel
    app = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    assert "this.send('lsp_start', {});" in app
    assert "case 'lsp': {" in app
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'lsp_start': self._on_lsp_start" in backend
    assert "'lsp_stop': self._on_lsp_stop" in backend


# --------------------------------------------------------------- P126
def test_engine_symbols_folding_format_rename():
    """文档符号 / 折叠范围 / 格式化（ruff）/ 重命名（同文件）✓"""
    engine = L._LanguageEngine(str(ROOT))
    source = ('import numpy as np\n\n\nclass Foo:\n'
              '    def method(self, a):\n        return a + 1\n\n\n'
              'def bar(x):\n    #region 说明\n    return Foo().method(x)\n'
              '    #endregion\n\n\nvalue = bar(1)\nprint(value)\n')
    symbols = engine.symbols(source)
    names = [item['name'] for item in symbols]
    assert 'Foo' in names and 'method' in names and 'bar' in names
    assert {item['kind'] for item in symbols} & {5, 6, 12}

    folds = engine.folding(source)
    assert folds and all(item['endLine'] > item['startLine'] for item in folds)
    assert any(item.get('kind') == 'region' for item in folds)

    edits = engine.formatting('x=1\nprint( x )\n')
    if edits:                                  # 没装 ruff / black 就跳过
        assert 'x = 1' in edits[0]['newText']

    prepared = engine.prepare_rename(source, 'a.py', 14, 1)
    assert prepared and prepared['placeholder'] == 'value'
    renamed = engine.rename(source, 'a.py', 14, 1, 'new_value')
    assert renamed and renamed['changes']
    located = list(renamed['changes'].values())[0]
    assert len(located) >= 2
    assert all(edit['newText'] == 'new_value' for edit in located)


def test_lsp_websocket_new_capabilities(tmp_path):
    """新能力：documentSymbol / foldingRange / formatting / rename ✓"""
    pytest.importorskip('jedi')
    service = L.serve_once(str(tmp_path))
    try:
        sock = socket.create_connection(('127.0.0.1', service.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall((
            'GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nUpgrade: websocket\r\n'
            'Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n'
            'Sec-WebSocket-Version: 13\r\n\r\n' % key).encode())
        sock.recv(4096)
        reply = _call(sock, 'initialize', {'rootUri': None,
                                           'capabilities': {}}, 1)
        caps = reply['result']['capabilities']
        assert caps['documentSymbolProvider'] is True
        assert caps['foldingRangeProvider'] is True
        assert caps['documentFormattingProvider'] is True
        assert caps['renameProvider'] == {'prepareProvider': True}
        _send(sock, {'jsonrpc': '2.0', 'method': 'initialized',
                     'params': {}})

        uri = 'file:///' + str(tmp_path / 'demo.py').replace(os.sep, '/')
        text = ('class Foo:\n    def method(self):\n        pass\n'
                '\n\nvalue = 1\nprint(value)\n')
        _send(sock, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen',
                     'params': {'textDocument': {
                         'uri': uri, 'languageId': 'python', 'version': 1,
                         'text': text}}})
        _wait_notification(sock, 'textDocument/publishDiagnostics')

        symbols = _call(sock, 'textDocument/documentSymbol',
                        {'textDocument': {'uri': uri}}, 2)
        assert [item['name'] for item in symbols['result']][:2] == ['Foo',
                                                                    'method']

        folds = _call(sock, 'textDocument/foldingRange',
                      {'textDocument': {'uri': uri}}, 3)
        assert folds['result']

        prepared = _call(sock, 'textDocument/prepareRename', {
            'textDocument': {'uri': uri},
            'position': {'line': 5, 'character': 1}}, 4)
        assert prepared['result']['placeholder'] == 'value'

        renamed = _call(sock, 'textDocument/rename', {
            'textDocument': {'uri': uri},
            'position': {'line': 5, 'character': 1},
            'newName': 'count'}, 5)
        edits = list(renamed['result']['changes'].values())[0]
        assert len(edits) == 2 and all(edit['newText'] == 'count'
                                       for edit in edits)
        sock.close()
    finally:
        service.stop()


def test_editor_multi_language_and_outline():
    """编辑器支持 md / json / txt + 左侧「大纲」+ Shift+Alt+F 格式化 ✓"""
    bundle = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-bundle.ts').read_text(
        encoding='utf-8')
    assert '@codemirror/lang-markdown' in bundle
    assert '@codemirror/lang-json' in bundle
    assert 'function languageOf(' in bundle
    assert "name.endsWith('.md')" in bundle
    assert 'foldService.of(foldProvider)' in bundle
    assert "'Shift-Alt-f'" in bundle
    assert 'documentSymbol' in bundle and 'foldingRange' in bundle
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert "this.outlineHead.textContent = '大纲';" in panel
    assert 'private _refreshOutline(): void {' in panel
    assert 'data-outline-line' in panel
    assert 'jumpToLine' in panel


def test_personal_supports_text_files_and_quiet_import(tmp_path):
    """非 .py 也能编辑（md / txt）+ 坏文件只提示一次 ✓"""
    from minibt.desk import personal

    assert personal.is_text_file('a.md')
    assert personal.is_text_file('notes.txt')
    assert personal.is_text_file('data.json')
    assert not personal.is_text_file('image.png')

    md = tmp_path / 'notes.md'
    saved = personal.write_file(str(md), '# 标题\n正文\n', root=str(tmp_path))
    assert saved['ok']
    loaded = personal.read_file(str(md))
    assert loaded['ok'] and loaded['kind'] == 'text'

    bad = tmp_path / 'broken.py'
    bad.write_text('class A(\n', encoding='utf-8')
    saved = personal.write_file(str(bad), 'class A(\n', root=str(tmp_path))
    assert not saved['ok'] and 'SyntaxError' in saved['error']

    source = (ROOT / 'minibt' / 'desk' / 'personal.py').read_text(
        encoding='utf-8')
    assert '_BROKEN_FILES' in source          # 坏文件只报一次 ✓
    assert '跳过 ' in source


# --------------------------------------------------------------- P127
def test_ruff_diagnostics():
    """语法错 + **ruff 检查**（未使用导入 / 未定义名 / 行长…）✓"""
    engine = L._LanguageEngine(str(ROOT))
    assert engine.diagnostics('x = 1\nprint(x)\n', 'a.py') == []

    unused = engine.diagnostics('import os\nx = 1\n', 'a.py')
    codes = {item.get('code') for item in unused}
    assert 'F401' in codes
    assert all(item['severity'] in (1, 2) for item in unused)

    undefined = engine.diagnostics('print(nope)\n', 'a.py')
    assert any(item.get('code') == 'F821' and item['severity'] == 1
               for item in undefined)

    syntax = engine.diagnostics('class A(\n', 'a.py')
    assert syntax and syntax[0]['source'] == 'python'


def test_workspace_symbols():
    """跨文件符号搜索（`workspace/symbol`，递归扫 root ✓）"""
    from minibt.desk import personal
    personal.ensure_directories()
    engine = L._LanguageEngine(personal.PERSONAL_ROOT)
    items = engine.workspace_symbols('stylezoo')
    names = {item['name'] for item in items}
    if not names:
        # 个人目录里没有 StyleZoo 示例（用户数据目录在仓库外，可能被清空）
        # → 不算失败（有示例文件时下面照旧逐条校验 ✓）
        pytest.skip('个人指标目录里没有 StyleZoo 示例')
    assert {'StyleZoo_Main', 'StyleZoo_Osc'} <= names
    assert all(item['location']['uri'].startswith('file:///')
               for item in items)
    assert all(item['location']['range']['start']['line'] >= 0
               for item in items)
    source = (ROOT / 'minibt' / 'desk' / 'lsp.py').read_text(encoding='utf-8')
    assert "'workspaceSymbolProvider': True" in source
    assert "if method == 'workspace/symbol':" in source


def test_editor_markdown_preview_and_symbols_ui():
    """Markdown 预览 + 跨文件符号搜索 UI ✓"""
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert 'function renderMarkdown(' in panel
    assert "this.previewButton = this._button('预览'" in panel
    assert 'desk-editor-preview' in panel
    assert 'private _syncPreview(): void {' in panel
    assert "this._button('符号'" in panel
    assert 'private _searchSymbols(query: string): void {' in panel
    assert 'data-symbol-path' in panel
    bundle = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-bundle.ts').read_text(
        encoding='utf-8')
    assert 'searchSymbols(query: string): Promise<Array<' in bundle
    assert "'workspace/symbol'" in bundle
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-editor-preview {' in css
    assert '.desk-editor-symbol-item {' in css


def test_save_with_auto_format(tmp_path):
    """设置「保存时自动格式化」→ 后端保存前先格式化并回推文本 ✓"""
    from minibt.desk import personal
    from minibt.desk.app import Desk

    class _Desk(Desk):
        def __init__(self):
            super().__init__(offline=True)
            self.patches = []
            self.push = lambda patch: self.patches.append(patch)
            self.push_log = lambda *a, **k: None
            self._refresh_personal = lambda *a, **k: None
            self._push_explorer = lambda *a, **k: None

    personal.ensure_directories()
    desk = _Desk()
    desk.explorer_root = lambda: str(tmp_path)
    target = tmp_path / 'fmt_save.py'
    desk._on_editor_save({'path': str(target), 'text': 'x=1\nprint( x )\n',
                          'format': True})
    saved = [p for p in desk.patches if p.get('type') == 'editor_saved']
    assert saved, '应该推 editor_saved'
    text = saved[-1]['text']
    if 'x = 1' in text:                    # 有 ruff / black 才会变
        assert target.read_text(encoding='utf-8').strip() == 'x = 1\nprint(x)'.strip()
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "if payload.get('format') and path.lower().endswith" in backend
    settings = (ROOT / 'jslib' / 'src' / 'desk' / 'settings-page.ts').read_text(
        encoding='utf-8')
    assert "this._row('editor_format_on_save', '保存时自动格式化'," in settings
    prefs = (ROOT / 'minibt' / 'desk' / 'user_prefs.py').read_text(encoding='utf-8')
    assert "'editor_format_on_save'," in prefs


# --------------------------------------------------------------- P128
def test_editor_help_text_is_user_spec():
    """编辑器「帮助」= 指标 / 策略 / 回测 / 参数优化 的说明（用户给定）✓"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    block = backend.split('EDITOR_HELP = """', 1)[1].split('"""', 1)[0]
    for title in ('【指标】', '【策略】', '【策略回测 / 参数优化】',
                  '一、单合约策略', '二、多合约策略', '三、参数优化（指标信号）'):
        assert title in block, title
    assert 'op_config = OpConfig(' in block
    assert 'data = LocalDatas.test' in block
    # 不再是 MiniQT 的 Pi Agent 说明 ✓
    assert 'Pi Agent' not in block
    app = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    assert "head.innerHTML = '<span>帮助</span>';" in app


def test_cross_file_definition_and_status_meta():
    """跨文件 F12 / Ctrl+点击 跳转 + 状态栏 行/列/换行/编码 ✓"""
    bundle = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-bundle.ts').read_text(
        encoding='utf-8')
    assert 'onOpenLocation?: (path: string, line: number) => void;' in bundle
    assert "key: 'F12'" in bundle
    assert 'mousedown: (event) => {' in bundle and 'event.ctrlKey' in bundle
    assert 'spec.onOpenLocation?.(path, target);' in bundle
    assert 'onCursor?: (line: number, column: number) => void;' in bundle
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert 'private _openAt(path: string, line: number): void {' in panel
    assert "node.textContent = `行 ${line}，列 ${column}`;" in panel
    assert "cursor.textContent = '行 1，列 1';" in panel
    assert 'UTF-8' in panel and 'LF' in panel


def test_editor_diff_view():
    """「对比」= 和磁盘版本 diff（@codemirror/merge 懒加载 ✓）"""
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert "this._button('对比'" in panel
    assert "import('@codemirror/merge')" in panel
    assert 'new MergeView({' in panel
    assert 'a: { doc: tab.saved' in panel and 'b: { doc: tab.text' in panel
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-editor-diff {' in css
    pkg = (ROOT / 'jslib' / 'package.json').read_text(encoding='utf-8')
    assert '"@codemirror/merge"' in pkg


# --------------------------------------------------------------- P129
def test_ruff_rules_are_not_noisy():
    """ruff 只报**真问题**：`dict(...)` 这种正常写法不能报（C408/RUF012 ✗）✓"""
    engine = L._LanguageEngine(str(ROOT))
    # 1) 正常的 dict 写法（minibt 指标里的 params / overlap）→ 无诊断
    snippet = ('from minibt import *\n\n\nclass Demo(BtIndicator):\n'
               '    params = dict(a=6, b=4, c=2)\n'
               '    overlap = dict(sma=True, cmo=False)\n\n'
               '    def next(self):\n'
               '        return self.close.cmo(self.params.a)\n')
    assert engine.diagnostics(snippet, 'a.py') == []
    # 2) 真问题照报
    codes = {item.get('code') for item in
             engine.diagnostics('import os\nx = 1\n', 'a.py')}
    assert 'F401' in codes
    codes = {item.get('code') for item in
             engine.diagnostics('print(nope)\n', 'a.py')}
    assert 'F821' in codes
    # 3) `from minibt import *` 不会被 F403/F405 误报（教程里都是这个写法 ✓）
    star = ('from minibt import *\n\n\nclass A(Strategy):\n'
            '    def next(self):\n        self.buy()\n')
    assert engine.diagnostics(star, 'a.py') == []
    source = (ROOT / 'minibt' / 'desk' / 'lsp.py').read_text(encoding='utf-8')
    assert "'E4,E7,E9,F'" in source
    assert "'E402,F403,F405'" in source


def test_status_bar_keeps_meta_and_badge():
    """状态栏：正文 + 「行/列 · LF · UTF-8 · 缩进」+ LSP 徽标 同时都在 ✓"""
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    block = panel.split('private _writeStatus(text: string): void {', 1)[1] \
        .split('}', 1)[0]
    assert "querySelector('[data-meta]')" in block
    assert "querySelector('[data-lsp]')" in block
    assert 'this.status.appendChild(meta);' in block
    assert 'this.status.appendChild(badge);' in block


# --------------------------------------------------------------- P130
def test_hover_tooltip_is_vscode_like_and_scrollable():
    """悬停提示像 VS Code：限宽限高 + **内容可滚动**（长文档能翻到底 ✓）"""
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    block = panel.split('.desk-editor-host .cm-tooltip {', 1)[1].split('}', 1)[0]
    assert 'max-width: min(680px, 62vw)' in block
    hover = panel.split('.desk-editor-host .cm-tooltip-hover {', 1)[1] \
        .split('}', 1)[0]
    assert 'max-height: min(420px, 52vh)' in hover
    assert 'overflow-y: auto' in hover          # ★ 可以滚轮翻看完整文档 ✓
    doc = panel.split('.desk-editor-host .cm-tooltip .documentation {', 1)[1] \
        .split('}', 1)[0]
    assert 'font-size: 11.5px' in doc
    assert "font-family: Consolas" in doc
    # markdown 按 HTML 渲染（jedi docstring 的标题 / 代码块才好看 ✓）
    bundle = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-bundle.ts').read_text(
        encoding='utf-8')
    assert 'allowHTMLContent: true' in bundle


def test_editor_scroller_can_scroll():
    """编辑器本身能滚动（长注释 / 长文件不会只看到上半截 ✓）"""
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert '.desk-editor-host .cm-scroller { overflow: auto; }' in panel
    assert '.desk-editor-host { flex: 1 1 auto; min-height: 0; overflow: hidden;' \
        in panel


# --------------------------------------------------------------- P131
def test_links_open_in_desk_tab_not_navigate():
    """悬停里的网址 / 外链 → 顶栏新 tab（不会把 desk 页面导航走）✓"""
    app = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    assert 'private _installLinkGuard(): void {' in app
    assert "document.addEventListener('click', (event) => {" in app
    assert "closest?.('a[href]')" in app
    assert 'event.preventDefault();' in app
    assert 'this.openWebPage(' in app
    assert 'this._installLinkGuard();' in app
    # 中键 / Ctrl+点击 也不导航 ✓
    assert "event.button === 1 || event.ctrlKey || event.metaKey" in app
    # 网页 tab 有兜底按钮（禁止被嵌入时用系统浏览器 ✓）
    assert "title=\"用系统浏览器打开（网页禁止被嵌入时用 ✓）\"" in app
    assert "this.send('open_url', { url })" in app
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-web-page {' in css
    assert '.desk-web-frame {' in css


def test_site_has_exactly_one_tab():
    """官网**有且只有一个 tab**：再点只是把地址换过去 ✓"""
    app = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    assert "private static readonly SITE_TAB_ID = 'web:site';" in app
    assert "private static readonly SITE_HOSTS = ['minibt.cn', 'www.minibt.cn'];" in app
    site = app.split('openWebPage(rawUrl: string): string {', 1)[1] \
        .split('private _createWebTab(', 1)[0]
    assert 'id = DeskApp.SITE_TAB_ID;' in site
    assert 'if (!this.tabs.has(id)) this._createWebTab(url, host, id);' in site
    assert 'this._loadWebPage(id, url);' in site      # 已开过 → 就地换页 ✓
    assert 'const existing = this.webTabs.get(url);' in site   # 其它网址按 URL 去重
    # 顶栏 🌐 走的是同一个入口（不再是 open_url 甩给系统浏览器 ✓）
    assert 'site.addEventListener(\'click\', () => this.openWebPage(' in app


# --------------------------------------------------------------- P133
def test_web_page_proxy_fetch_and_inline(tmp_path):
    """网页 tab：后端抓 HTML + **内联 CSS / 图片**（绕开 X-Frame-Options ✓）"""
    import http.server
    import threading

    from minibt.desk import web as _web

    css = 'body { color: rgb(1, 2, 3); } .logo { background: url(./logo.png); }'
    png = b'\x89PNG\r\n\x1a\n' + b'0' * 32
    page = ('<html><head><link rel=stylesheet href="/a.css">'
            '<link rel=stylesheet href="/missing.css"></head>'
            '<body><img src="/logo.png" alt=logo>'
            '<script src="/app.js"></script></body></html>')

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):                                    # noqa: N802
            routes = {'/': (page, 'text/html; charset=utf-8'),
                      '/a.css': (css, 'text/css'),
                      '/logo.png': (png, 'image/png')}
            if self.path not in routes:
                self.send_error(404)
                return
            body, kind = routes[self.path]
            raw = body.encode() if isinstance(body, str) else body
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):                        # noqa: D401
            return

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_address[1]}/'
        result = _web.fetch_page(base, timeout=5)
        assert result['ok'], result
        assert 'rel=stylesheet' in result['html']

        out = _web.inline_assets(result['html'], result['url'])
        assert out.count('<style>') == 1              # 只内联成功的那个 ✓
        assert 'rgb(1, 2, 3)' in out
        assert 'data:image/png;base64,' in out        # 图片转 data URI ✓
        # 脚本**全部**去掉（外链被去掉后内联脚本必然报 __md_get ✗）
        assert '<script src' not in out
        assert 'alert(' not in out
        assert 'stylesheet' not in out.lower()         # 失败的外链样式也去掉 ✓
        assert 'url("http' in out                     # CSS 里的相对 url 已绝对化 ✓

        wrapped = _web.wrap_page(out, result['url'])
        assert '<base href=' in wrapped
        assert '__deskWebNav' in wrapped               # 站内链接交给父页面代理 ✓
    finally:
        server.shutdown()
        server.server_close()

    assert _web.fetch_page('ftp://x')['ok'] is False     # 非 http(s) 拒绝 ✓


def test_web_tab_frontend_wiring():
    """顶栏网页 tab：代理内容塞 srcdoc / 站内跳转不新开 tab ✓"""
    app = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    assert "this.send('web_page', { url, id });" in app
    assert 'private _loadWebPage(id: string, url: string): void {' in app
    assert 'frame.srcdoc = String(patch.html || \'\');' in app
    assert 'private _installWebNav(): void {' in app
    assert 'this.openWebPage(target);' in app      # 站内链接 → 同一 tab 代理 ✓
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-web-hint {' in css
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'web_page': self._on_web_page" in backend
    # 后端现在走 `page_html`（内部 fetch + inline + wrap + 缓存 ✓）
    assert '_web.page_html(url)' in backend


# --------------------------------------------------------------- P134
def test_web_page_strips_all_scripts():
    """网页 tab 抓取后**去掉所有脚本**（否则控制台报 __md_get / Invalid URL ✗）"""
    from minibt.desk import web as _web
    html = ('<html><head><style>x</style>'
            '<script id="cfg" type="application/json">{}</script>'
            '<script>window.__md_get = function () {};</script>'
            '<script src="/a.js"></script></head>'
            '<body><p>正文</p></body></html>')
    out = _web.inline_assets(html, 'https://x.test/')
    assert '<p>正文</p>' in out
    assert '__md_get' not in out
    assert '<script src' not in out


def test_deskweb_scheme_module_exists():
    """`deskweb://` 代理模块保留（Qt 里 iframe 加载自定义 scheme 会被拦 → 默认不用）"""
    proxy = (ROOT / 'minibt' / 'desk' / 'web_proxy.py').read_text(encoding='utf-8')
    assert "SCHEME = b'deskweb'" in proxy
    assert 'def register_scheme()' in proxy and 'def install(profile)' in proxy
    window = (ROOT / 'minibt' / 'desk' / 'app_window.py').read_text(
        encoding='utf-8')
    assert "_web_proxy.register_scheme()" in window
    # 前端统一走后端抓取（`__deskWebProxy = false`）
    assert "run_script('window.__deskWebProxy = false;')" in window


# --------------------------------------------------------------- P135
def test_web_page_is_fast_and_cached():
    """网页 tab：资源**并发 + 总时限**，同一 URL **秒开**（缓存 ✓）"""
    import time

    from minibt.desk import web as _web

    assert _web.WEB_ASSET_DEADLINE <= 2.0        # 资源最多等 1.5 秒 ✓
    source = (ROOT / 'minibt' / 'desk' / 'web.py').read_text(encoding='utf-8')
    assert 'ThreadPoolExecutor' in source and 'wait(futures' in source
    assert 'def page_html(' in source and '_PAGE_CACHE' in source
    # 缓存命中直接返回（不联网）→ 第二个调用必须极快 ✓
    _web._PAGE_CACHE.clear()
    _web._cache_put('https://cache.test/x', '<html>cached</html>')
    result = _web.page_html('https://cache.test/x')
    assert result['ok'] and result['cached'] is True
    assert result['html'] == '<html>cached</html>'
    started = time.time()
    for _ in range(20):
        _web.page_html('https://cache.test/x')
    assert time.time() - started < 1.0

    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'result = _web.page_html(url)' in backend    # 走缓存 ✓
    assert 'def _warm_web_cache(self) -> None:' in backend   # 启动预热官网 ✓
    assert "self._warm_web_cache()" in backend


# --------------------------------------------------------------- P136
def test_web_page_back_to_top_and_no_duplicate_defs():
    """抓取页补「回到顶部」圆按钮（原站是 JS，脚本被删了）+ 去掉重复定义 ✓"""
    from minibt.desk import web as _web

    wrapped = _web.wrap_page('<html><head></head><body>x</body></html>',
                             'https://a.test/')
    assert '__desk_top_btn' in wrapped
    assert '回到顶部' in wrapped
    assert 'scrollTo' in wrapped
    # 圆 48px，**箭头是 SVG 30px**（用户说"箭头太小"→ 换 SVG 放大 ✓）
    assert 'width: 48px; height: 48px' in wrapped
    assert 'width="30" height="30"' in wrapped
    assert '<path d="M12 19V5"/>' in wrapped

    source = (ROOT / 'minibt' / 'desk' / 'web.py').read_text(encoding='utf-8')
    for name in ('wrap_page', 'inline_assets', 'page_html', '_attr',
                 '_fetch_bytes', '_cache_get', '_cache_put'):
        assert source.count('def %s(' % name) == 1, name      # 不能有重复定义 ✗
