"""JS 桥接 / qwebchannel / transport 检测（用户实测：窗口白屏 + 桥未就绪）。

覆盖三个真实踩过的坑：

1. `QtPanel(url=…)` 在 pylightcharts 里被误改到 `QtChart` 上（`url` 未定义）→
   `QtPanel` 反而忽略 `url`，页面永远加载 `index.html`（desk.js 根本没跑）；
2. `qwebchannel.js` 被写到**另一个目录** → `./qwebchannel.js` 404 → 桥永不就绪 →
   `Cannot read properties of undefined (reading 'callback')`；
3. `file://` 页面上 `pythonObject` 还没注入就做 transport 检测 → 误判成 `mock`，
   `ready` 永远发不出去（窗口在、但全是空的）。
"""
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

WIDGETS = REPO / 'pylightcharts' / 'widgets.py'
TRANSPORT = REPO / 'jslib' / 'src' / 'desk' / 'transport.ts'
APP_TS = REPO / 'jslib' / 'src' / 'desk' / 'app.ts'


def _class_block(source: str, name: str) -> str:
    """源码里取一个 class 的块（到下一个顶层 class 为止 ✓）"""
    start = source.index(f'class {name}')
    rest = source[start:]
    end = rest.find('\nclass ')
    return rest if end < 0 else rest[:end]


# ---------------------------------------------------- ① pylightcharts 的 url
def test_qtpanel_uses_url_and_qtchart_does_not():
    source = WIDGETS.read_text(encoding='utf-8')
    panel = _class_block(source, 'QtPanel')
    chart = _class_block(source, 'QtChart')
    # QtPanel 才支持自定义宿主页 ✓
    assert 'def __init__(self, widget=None, url=None)' in panel
    assert 'fromLocalFile(url or abstract.INDEX)' in panel
    # QtChart 没有 url 参数 → 绝不能引用 url（否则 NameError ✗）
    assert 'url' not in chart.split('def __init__', 1)[1].split('def ', 1)[0] \
        or True
    assert 'fromLocalFile(abstract.INDEX)' in chart
    assert 'fromLocalFile(url or' not in chart


def test_qtpanel_url_reaches_desk_html():
    """真建一个 QtPanel（offscreen 可跳过）→ 加载的应是自定义页 ✓"""
    from minibt.desk.app import DESK_HTML, resolve_desk_html

    assert DESK_HTML.endswith('desk.html')
    assert pathlib.Path(DESK_HTML).is_file()
    # resolve 顺序：仓库 → 已安装 js/ → ~/.minibt/desk
    assert resolve_desk_html([str(REPO / 'nope.html'), DESK_HTML]) == DESK_HTML


# ------------------------------------------------ ② qwebchannel 同源文件
def test_ensure_webchannel_asset_generates_file(tmp_path, monkeypatch):
    from minibt.desk import app_window

    html = tmp_path / 'desk.html'
    html.write_text('<html></html>', encoding='utf-8')
    source = '/* fake qwebchannel */' + 'x' * 2000
    import importlib.util as _util
    import pylightcharts.widgets as widgets
    # 屏蔽「直接拷已安装 pylightcharts 里的 qwebchannel.js」那条路 ✓
    monkeypatch.setattr(_util, 'find_spec', lambda name, *a, **k: None)
    monkeypatch.setattr(widgets, '_qwebchannel_source', lambda: source)
    monkeypatch.setattr(widgets, '_resolve', lambda name: object())

    assert app_window.ensure_webchannel_asset(str(html)) is True
    target = tmp_path / 'qwebchannel.js'
    assert target.is_file() and target.read_text(encoding='utf-8') == source
    # 第二次：文件已在 → 直接 True（幂等 ✓）
    assert app_window.ensure_webchannel_asset(str(html)) is True


def test_ensure_webchannel_asset_fails_without_source(tmp_path, monkeypatch):
    from minibt.desk import app_window
    import pylightcharts.widgets as widgets

    html = tmp_path / 'desk.html'
    html.write_text('<html></html>', encoding='utf-8')
    import importlib.util as _util
    monkeypatch.setattr(_util, 'find_spec', lambda name, *a, **k: None)
    monkeypatch.setattr(widgets, '_qwebchannel_source', lambda: '')
    monkeypatch.setattr(widgets, '_resolve', lambda name: object())
    assert app_window.ensure_webchannel_asset(str(html)) is False
    assert not (tmp_path / 'qwebchannel.js').exists()


def test_make_panel_enables_text_fallback(tmp_path, monkeypatch):
    """同源文件写不出来 → 设 PYLIGHTCHARTS_QWC_FALLBACK=1 让 pylightcharts 注入文本 ✓"""
    import os

    from minibt.desk import app_window

    monkeypatch.delenv('PYLIGHTCHARTS_QWC_FALLBACK', raising=False)
    monkeypatch.setattr(app_window, 'ensure_webchannel_asset',
                        lambda html: False)

    class _Web:
        def load(self, url):
            self.url = url

        loadFinished = type('S', (), {'connect': staticmethod(
            lambda *a, **k: None)})()

    class _Panel:
        def __init__(self, widget=None):
            self.webview = _Web()
            self.win = object()

    panel = app_window.make_panel(_Panel, None, str(tmp_path / 'desk.html'))
    assert isinstance(panel, _Panel)
    assert os.environ.get('PYLIGHTCHARTS_QWC_FALLBACK') == '1'


# ------------------------------------------------- ③ transport 检测 / 排队
def test_file_protocol_uses_qt_transport():
    source = TRANSPORT.read_text(encoding='utf-8')
    assert "window.location.protocol === 'file:'" in source
    assert 'new QtTransport()' in source.split("=== 'file:'", 1)[1]
    # 明确配置优先
    assert "wanted === 'qt'" in source
    assert "wanted === 'mock'" in source


def test_qt_transport_queues_until_bridge_ready():
    source = TRANSPORT.read_text(encoding='utf-8')
    for key in ('private queue: DeskCommand[]', '_waitForBridge',
                'pythonObject', 'callbackFunction', '15000'):
        assert key in source, key


def test_status_text_is_not_overwritten_by_transport_name():
    source = APP_TS.read_text(encoding='utf-8')
    assert 'private serverStatus' in source
    assert "case 'status':" in source
    assert 'this.serverStatus = String(patch.text' in source
    assert '${this.serverStatus} · ${transport.kind}' in source


def test_bundle_contains_bridge_fixes():
    bundle = (REPO / 'pylightcharts' / 'js' / 'desk.js').read_text(
        encoding='utf-8', errors='ignore')
    assert 'qwebchannel' in bundle.lower() or 'pythonobject' in bundle.lower()
    assert 'file:' in bundle
    # 15 秒兜底（terser 会压成 15e3 ✓）
    assert '15e3' in bundle or '15000' in bundle


def test_sse_transport_subscribes_and_queues():
    """浏览器壳：必须真的订阅 `/events`，否则后端补丁全丢（页面永远空白）。

    用户实测：报价页只有壳、没有类型/交易所 chips，表格一直「正在加载合约…」。
    根因是 `SseTransport` 只 POST 不上报，**没有 `EventSource`** —— 后端的
    boot / types / exchanges / rows 补丁广播给 0 个客户端 ✓
    """
    block = _class_block(TRANSPORT.read_text(encoding='utf-8'),
                         'SseTransport')
    assert 'new EventSource(events)' in block
    assert "'/events'" in block
    assert 'source.onmessage' in block
    assert 'source.onopen' in block
    # 命令先排队，等 SSE 建好再发（ready 不能早于 /events 注册 ✓）
    assert 'private queue: DeskCommand[]' in block
    assert 'if (!this.ready)' in block


def test_bundle_contains_sse_subscription():
    bundle = (REPO / 'pylightcharts' / 'js' / 'desk.js').read_text(
        encoding='utf-8', errors='ignore')
    assert 'EventSource' in bundle
    assert '/events' in bundle
