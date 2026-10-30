"""看盘窗口「代码编辑器」页的行为测试 ✓。

编辑器是**懒启动**的（没 ``showEvent`` 就不起服务），所以可以离屏构造页面、
把 ``_editor`` / ``_bridge`` 换成假的，直接验行为：活动标签反查、跨目录打开、
保存到当前目录 ✓。
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

pytest.importorskip('PyQt6')

page_mod = pytest.importorskip('miniqt.app.windows.qtvscode_page')


class _FakePage:
    """假的 ``QWebEnginePage``：``runJavaScript(js, cb)`` 把「活动标签」回调回去 ✓。"""

    def __init__(self, name='', tip='', raw=False):
        self.name = name
        self.tip = tip
        self.raw = raw
        self.scripts = []

    def runJavaScript(self, js, callback=None):              # noqa: N802
        self.scripts.append(js)
        if callable(callback):
            callback(self.name if self.raw else
                     {'name': self.name, 'tip': self.tip})


class _FakeView:
    def __init__(self, page):
        self._page = page

    def page(self):
        return self._page


class _FakeEditor:
    def __init__(self, name='', tip='', raw=False):
        self.view = _FakeView(_FakePage(name, tip, raw))
        self.triggered = []

    def trigger(self, method, params=None):
        self.triggered.append((method, params))


class _FakeBridge:
    has_client = True

    def __init__(self):
        self.notified = []
        self.requested = []

    def invoke(self, method, params=None):                   # pragma: no cover
        raise KeyError(method)

    def notify(self, method, params=None):
        self.notified.append((method, (params or {}).get('command')))

    def request(self, method, params=None, on_result=None,
                on_error=None, timeout_ms=30000):
        self.requested.append((method, (params or {}).get('command')))
        if on_result is not None:
            on_result({'ok': True})       # 扩展回 {ok:true} → 保存完成回调 ✓
        return 1


@pytest.fixture()
def state_file(tmp_path, monkeypatch):
    """把编辑器 state 文件指到临时目录（别动用户真实的 ✓）。"""
    path = tmp_path / 'state.json'
    monkeypatch.setattr(page_mod, 'STATE_FILE', str(path), raising=False)
    return path


def _make_page(tmp_path, workspace='', file_path='', mode='edit'):
    """建页并把 ``_started`` 置真 —— 不碰 QTimer，不会真去起 VS Code ✓。"""
    page = page_mod.QtvscodePage(workspace=workspace or str(tmp_path),
                                 file_path=file_path, mode=mode)
    page._started = True
    return page


# ---- 工作区 ---------------------------------------------------------------
def test_workspace_never_points_at_the_temp_dir():
    temp = page_mod.TEMP_DIR
    assert os.path.samefile(page_mod._sanitize_workspace(temp),
                            os.path.expanduser('~')) or \
        page_mod._sanitize_workspace(temp) == os.path.expanduser('~')


def test_workspace_keeps_a_normal_folder(tmp_path):
    folder = str(tmp_path / 'ws')
    os.makedirs(folder)
    assert page_mod._sanitize_workspace(folder) == os.path.abspath(folder)


# ---- 打开文件 -------------------------------------------------------------
def test_open_path_keeps_workspace_and_does_not_remember_temp(state_file,
                                                              tmp_path):
    ws = tmp_path / 'ws'
    ws.mkdir()
    temp = tmp_path / 't'
    temp.mkdir()
    src = temp / 'MyInd.py'
    src.write_text('x = 1\n', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws))
    page.open_path(str(src), remember=False)

    assert page.file_path == str(src)
    assert page.workspace == os.path.abspath(str(ws))
    assert not hasattr(page, 'pathLabel')      # 顶栏左边的文本框已删 ✓
    state = page_mod.load_state()
    assert state.get('workspace') == os.path.abspath(str(ws))
    assert not state.get('file')          # 临时文件不记 ✓


def test_open_path_remembers_a_real_file(state_file, tmp_path):
    ws = tmp_path / 'ws'
    ws.mkdir()
    src = ws / 'Real.py'
    src.write_text('x = 1\n', encoding='utf-8')
    page = _make_page(tmp_path, workspace=str(ws))
    page.open_path(str(src))
    assert page_mod.load_state().get('file') == str(src)


def test_stale_remembered_file_is_not_used(state_file, tmp_path):
    """记住的文件**已被删除** → 不能拿它当默认 ``file_path``。

    否则后面点「参数优化 / 回测」会拿到一个不存在的路径 → 误报
    “请先选择策略”（用户现场：``qtvscode_dock.json`` 里记的
    ``teststrategy_2.py`` 已删 ✗）。
    """
    ws = tmp_path / 'ws'
    ws.mkdir()
    gone = ws / 'gone.py'
    page_mod.save_state({'workspace': str(ws), 'file': str(gone)})
    page = _make_page(tmp_path, workspace=str(ws))
    assert page.file_path == ''

    real = ws / 'Real.py'
    real.write_text('x = 1\n', encoding='utf-8')
    page_mod.save_state({'workspace': str(ws), 'file': str(real)})
    page2 = _make_page(tmp_path, workspace=str(ws))
    assert page2.file_path == str(real)


# ---- 活动标签反查 ---------------------------------------------------------
def test_match_active_file_prefers_the_current_file(tmp_path):
    ws = tmp_path / 'ws'
    ws.mkdir()
    here = ws / 'Here.py'
    here.write_text('x = 1\n', encoding='utf-8')
    page = _make_page(tmp_path, workspace=str(ws), file_path=str(here))
    assert page._match_active_file('Here.py') == str(here)
    assert page._match_active_file('● Here.py') == str(here)


def test_match_active_file_searches_subfolders_and_temp(tmp_path, monkeypatch):
    ws = tmp_path / 'ws'
    (ws / 'sub').mkdir(parents=True)
    other = ws / 'sub' / 'Other.py'
    other.write_text('x = 1\n', encoding='utf-8')
    temp = tmp_path / 'temp'
    temp.mkdir()
    ind = temp / 'Ind.py'
    ind.write_text('x = 1\n', encoding='utf-8')
    monkeypatch.setattr(page_mod, 'TEMP_DIR', str(temp), raising=False)

    page = _make_page(tmp_path, workspace=str(ws))
    assert page._match_active_file('Other.py') == str(other)
    assert page._match_active_file('Ind.py') == str(ind)
    assert page._match_active_file('Nope.py') == ''
    assert page._match_active_file('') == ''
    assert page._match_active_file('noext') == ''


def test_active_files_lists_same_name_candidates(state_file, tmp_path):
    ws = tmp_path / 'ws'
    ws.mkdir()
    (ws / 'test.py').write_text('x = 1\n', encoding='utf-8')
    sub = ws / 'sub'
    sub.mkdir()
    (sub / 'test.py').write_text('y = 2\n', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws),
                      file_path=str(ws / 'test.py'))
    assert page._file_from_tip('test.py') == ''      # 裸文件名不凭它定位 ✓
    files = page._match_active_files('test.py')
    assert str(ws / 'test.py') in files
    assert str(sub / 'test.py') in files             # 同名候选都要列出来 ✓


def test_path_from_crumbs(state_file, tmp_path):
    ws = tmp_path / 'ws'
    ws.mkdir()
    sub = ws / 'strategy'
    sub.mkdir()
    (sub / 'aroon.py').write_text('x = 1\n', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws))
    # 面包屑（strategy > aroon.py）+ workspace → 真实路径 ✓
    assert page._path_from_crumbs(['strategy', 'aroon.py']) == \
        str(sub / 'aroon.py')
    # 面包屑带了 workspace 根名 → 去掉 ✓
    assert page._path_from_crumbs(['ws', 'strategy', 'aroon.py']) == \
        str(sub / 'aroon.py')
    assert page._path_from_crumbs([]) == ''
    # 面包屑优先于部分搜索
    files = page._match_active_files('aroon.py', '', ['strategy', 'aroon.py'])
    assert files and files[0] == str(sub / 'aroon.py')


def test_request_add_to_chart_follows_the_active_tab(state_file, tmp_path):
    from PyQt6.QtTest import QTest

    ws = tmp_path / 'ws'
    ws.mkdir()
    first = ws / 'First.py'
    first.write_text('x = 1\n', encoding='utf-8')
    second = ws / 'Second.py'
    second.write_text('y = 2\n', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws), file_path=str(first))
    page._editor = _FakeEditor('Second.py')        # 用户在 VS Code 里切了标签 ✓
    page._bridge = _FakeBridge()
    seen = []
    page.addToChartRequested.connect(seen.append)

    page.request_add_to_chart()
    assert page.file_path == str(second)           # 反查对齐到第二个标签 ✓
    assert ('invokeCommand', 'workbench.action.files.save') in \
        page._bridge.requested
    # 保存**完成**后才发信号（扩展 request 回调同步触发 ✓）
    assert seen == [str(second)]


def test_write_text_exact_preserves_crlf(state_file, tmp_path):
    """写回 buffer 时必须**原样**（不能把 ``\r\n`` 变成 ``\r\r\n`` ✓）。"""
    page = _make_page(tmp_path)
    target = tmp_path / 'x.py'
    assert page._write_text_exact(str(target), 'a\r\nb\r\n') is True
    assert target.read_bytes() == b'a\r\nb\r\n'      # 不出现 \r\r\n ✓
    # 内容没变 → 不写（避免多余保存 / 重载 ✓）
    assert page._write_text_exact(str(target), 'a\r\nb\r\n') is False


def test_deliver_active_keeps_line_endings(state_file, tmp_path):
    """通过 buffer 文本交付时，文件换行保持原样（用户报的“多空行”✓）。"""
    src = tmp_path / 'S.py'
    src.write_bytes(b'x = 1\r\ny = 2\r\n')
    page = _make_page(tmp_path, file_path=str(src))

    class _Bridge:
        has_client = True

        def request(self, method, params=None, on_result=None,
                    on_error=None, timeout_ms=30000):
            if method == 'getActiveText' and on_result is not None:
                on_result({'path': str(src), 'text': 'x = 1\r\ny = 2\r\n'})
            return 1

    page._editor = object()
    page._bridge = _Bridge()
    page._deliver_active(str(src), 'x = 1\r\ny = 2\r\n', lambda _p: None)
    assert src.read_bytes() == b'x = 1\r\ny = 2\r\n'


def test_prepare_active_file_uses_buffer_text(state_file, tmp_path):
    """有 buffer 文本时，直接用**编辑器内容**（未保存也算）✓。"""
    src = tmp_path / 'S.py'
    src.write_text('old', encoding='utf-8')
    page = _make_page(tmp_path, file_path=str(src))
    page._editor = object()                          # 只要有非 None 就行 ✓

    class _Bridge:
        has_client = True

        def __init__(self):
            self.calls = []

        def request(self, method, params=None, on_result=None,
                    on_error=None, timeout_ms=30000):
            self.calls.append(method)
            if method == 'getActiveText' and on_result is not None:
                on_result({'path': str(src), 'text': 'NEW CONTENT'})
            return 1

    page._bridge = _Bridge()
    seen = []
    page.addToChartRequested.connect(seen.append)
    page.request_add_to_chart()
    assert seen == [str(src)]
    assert src.read_text(encoding='utf-8') == 'NEW CONTENT'   # buffer 已写回 ✓


def test_request_add_to_chart_without_editor_emits_at_once(state_file,
                                                           tmp_path):
    src = tmp_path / 'Only.py'
    src.write_text('x = 1\n', encoding='utf-8')
    page = _make_page(tmp_path, file_path=str(src))
    seen = []
    page.addToChartRequested.connect(seen.append)
    page.request_add_to_chart()
    assert seen == [str(src)]


# ---- 保存文件 -------------------------------------------------------------
def test_save_file_copies_into_the_workspace(state_file, tmp_path):
    from PyQt6.QtTest import QTest

    ws = tmp_path / 'ws'
    ws.mkdir()
    temp = tmp_path / 't'
    temp.mkdir()
    src = temp / 'MyInd.py'
    src.write_text('x = 1\n', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws))
    page._editor = _FakeEditor('')
    page._bridge = _FakeBridge()
    page.set_current_file(str(src), remember=False)
    page.save_file()

    saved = ws / 'MyInd.py'
    assert saved.read_text(encoding='utf-8') == 'x = 1\n'
    assert page.file_path == str(saved)            # 切到刚保存的文件 ✓
    assert page._bridge.requested[0] == (
        'invokeCommand', 'workbench.action.files.save')


def test_save_file_does_not_overwrite(state_file, tmp_path):
    ws = tmp_path / 'ws'
    ws.mkdir()
    (ws / 'Same.py').write_text('old', encoding='utf-8')
    temp = tmp_path / 't'
    temp.mkdir()
    src = temp / 'Same.py'
    src.write_text('new', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws))
    page._editor = _FakeEditor('')
    page.set_current_file(str(src), remember=False)
    page._save_to_workspace()

    assert (ws / 'Same.py').read_text(encoding='utf-8') == 'old'
    assert (ws / 'Same_1.py').read_text(encoding='utf-8') == 'new'


# ---- tooltip 里的路径（同名文件时最准 ✓）----------------------------------
def test_active_tab_tip_wins_over_same_basename(tmp_path):
    ws = tmp_path / 'ws'
    ws.mkdir()
    temp = tmp_path / 't'
    temp.mkdir()
    in_temp = temp / 'MyInd.py'
    in_temp.write_text('temp', encoding='utf-8')
    in_ws = ws / 'MyInd.py'
    in_ws.write_text('ws', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws), file_path=str(in_temp))
    # 文件名一样，但 tooltip 带了真实路径 → 听 tooltip 的 ✓
    assert page._match_active_file('MyInd.py', str(in_ws)) == str(in_ws)
    # tooltip 对不上 → 回退到同名匹配（也就是当前文件 ✓）
    assert page._match_active_file('MyInd.py', str(temp / 'x.py')) == str(in_temp)


def test_active_tab_tip_handles_relative_paths(tmp_path):
    ws = tmp_path / 'ws'
    (ws / 'sub').mkdir(parents=True)
    target = ws / 'sub' / 'Other.py'
    target.write_text('x = 1', encoding='utf-8')
    page = _make_page(tmp_path, workspace=str(ws))
    relative = os.path.join('sub', 'Other.py')
    assert page._match_active_file('Other.py', relative) == str(target)
    # aria-label 里的 “name, 2 of 3” 尾巴要能剥掉 ✓
    assert page._match_active_file('Other.py', 'Other.py, 2 of 3') == str(target)
    assert page._match_active_file('Other.py', 'Other.py') == str(target)


def test_active_file_result_may_be_a_plain_string(state_file, tmp_path):
    """``runJavaScript`` 万一回的是字符串（旧版 JS）也要能认 ✓。"""
    ws = tmp_path / 'ws'
    ws.mkdir()
    target = ws / 'Plain.py'
    target.write_text('x = 1', encoding='utf-8')
    page = _make_page(tmp_path, workspace=str(ws))
    page._editor = _FakeEditor('Plain.py', raw=True)
    seen = []
    page.sync_active_file(seen.append)
    assert seen == [str(target)]


# ---- 过期的「补开」请求不能把编辑器抢回去（回归 ✓）----------------------
def test_stale_open_request_is_dropped(tmp_path):
    ws = tmp_path / 'ws'
    ws.mkdir()
    a = ws / 'A.py'
    a.write_text('a', encoding='utf-8')
    b = ws / 'B.py'
    b.write_text('b', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws), file_path=str(b))
    page._editor = _FakeEditor('')
    page._bridge = _FakeBridge()
    page._open_file_retry(str(a))          # 过期（当前文件已经是 B ✓）
    page._trigger_open(str(a))
    assert page._editor.triggered == []
    assert page._bridge.notified == []


def test_open_a_then_b_does_not_switch_back_to_a(state_file, tmp_path):
    """打开 A 后马上又打开 B：A 那一轮的定时确认必须作废 ✓。

    这就是「添加的指标是上一次的」的根因：A 的 2.5s 补开把 VS Code 拉回 A ✗。
    """
    from PyQt6.QtTest import QTest

    ws = tmp_path / 'ws'
    ws.mkdir()
    a = ws / 'A.py'
    a.write_text('a', encoding='utf-8')
    b = ws / 'B.py'
    b.write_text('b', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws))
    page._editor = _FakeEditor('')
    page._bridge = _FakeBridge()
    page.open_path(str(a))
    QTest.qWait(30)
    page.open_path(str(b))
    QTest.qWait(1500)                       # 让 A 的确认定时器到点 ✓

    paths = [params.get('path') for _, params in page._editor.triggered]
    assert paths and paths[-1] == str(b)
    assert paths.count(str(a)) == 1         # A 只在它还是当前文件时点过一次 ✓


def test_verify_open_retriggers_while_the_tab_is_wrong(state_file, tmp_path):
    from PyQt6.QtTest import QTest

    ws = tmp_path / 'ws'
    ws.mkdir()
    target = ws / 'Target.py'
    target.write_text('t', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws), file_path=str(target))
    page._bridge = _FakeBridge()
    page._editor = _FakeEditor('Other.py')  # DOM 一直说活动的是别的文件 ✗
    page._verify_open(str(target))
    QTest.qWait(4000)

    paths = [params.get('path') for _, params in page._editor.triggered]
    assert len(paths) >= 2                  # 反复推，直到上限 ✓
    assert set(paths) == {str(target)}


def test_verify_open_stops_when_the_tab_matches(state_file, tmp_path):
    from PyQt6.QtTest import QTest

    ws = tmp_path / 'ws'
    ws.mkdir()
    target = ws / 'Target.py'
    target.write_text('t', encoding='utf-8')

    page = _make_page(tmp_path, workspace=str(ws), file_path=str(target))
    page._bridge = _FakeBridge()
    page._editor = _FakeEditor('Target.py')  # DOM 说就是它 ✓
    page._verify_open(str(target))
    QTest.qWait(1200)
    assert page._editor.triggered == []      # 确认一次就够了，别乱点 ✓


# ---- 「指标 / 策略使用指南」按钮 -----------------------------------------
def test_usage_guide_button_opens_dialog(tmp_path, monkeypatch):
    page = _make_page(tmp_path)
    # 顶栏有「使用指南」按钮（在 显示/隐藏侧栏 旁边 ✓）
    assert hasattr(page, 'guideButton')
    assert '使用指南' in page.guideButton.toolTip()
    # 点击 → 弹指南（换掉对话框，别真建窗口 ✓）
    from miniqt.app.windows import usage_guide_dialog as guide_mod
    seen = {}

    class _FakeDialog:
        def __init__(self, parent=None):
            seen['parent'] = parent

        def exec(self):
            seen['exec'] = True
            return 1

    monkeypatch.setattr(guide_mod, 'UsageGuideDialog', _FakeDialog)
    page.show_usage_guide()
    assert seen.get('exec') is True
    # 正文覆盖用户要的规则 ✓
    text = guide_mod.GUIDE_TEXT
    for token in ('指标', '策略', 'self.kline', 'self.get_kline',
                  '第一个图表', '多合约策略', '替换'):
        assert token in text, token


def test_last_active_file_uses_bridge_cache(state_file, tmp_path):
    """窗口失焦时 ``activeTextEditor``/DOM 都不响应，只能靠 bridge 缓存的推送路径 ✓。

    扩展推送的 ``setActiveEditor`` 缓存在 ``QtvscodeBridge.last_active_editor``；
    :meth:`QtvscodePage.last_active_file` 要能用它兜底（**存在**才算）✓。
    """
    ws = tmp_path / 'ws'
    ws.mkdir()
    real = ws / 'Real.py'
    real.write_text('x = 1\n', encoding='utf-8')
    page = _make_page(tmp_path, workspace=str(ws))

    class _Bridge:
        last_active_editor = str(real)

    page._bridge = _Bridge()
    page._active_path = ''
    page.file_path = str(ws / 'gone.py')          # 过期且不存在 ✗

    assert page.last_active_file() == str(real)
    assert page._valid_strategy_path('') == str(real)

    page._bridge = _Bridge()
    page._bridge.last_active_editor = ''
    assert page.last_active_file() == ''


def test_active_document_resolves_cached_file_and_reads_text(state_file,
                                                             tmp_path):
    """``active_document`` / ``current_file`` / ``current_code``：拿不到扩展时读缓存+读盘 ✓。"""
    ws = tmp_path / 'ws'
    ws.mkdir()
    real = ws / 'S.py'
    real.write_text('print(1)\n', encoding='utf-8')
    page = _make_page(tmp_path, workspace=str(ws))

    class _Bridge:
        last_active_editor = str(real)
        has_client = False

    page._bridge = _Bridge()
    page._editor = None

    doc = page.active_document()
    assert doc['path'] == str(real)
    assert doc['text'] == 'print(1)\n'
    assert doc['dirty'] is False
    assert page.current_file() == str(real)
    assert page.current_code() == 'print(1)\n'

    got = {}
    page.request_active_document(lambda data: got.update(data))
    assert got['path'] == str(real)
    assert got['text'] == 'print(1)\n'


def test_sanitize_workspace_rejects_missing_dir(tmp_path):
    """不存在的目录（如被测试写进状态的 ``NEW_DIR``）不算工作区 ✓。"""
    missing = str(tmp_path / 'NEW_DIR')
    assert page_mod._sanitize_workspace(missing) == os.path.expanduser('~')
    assert page_mod._sanitize_workspace(str(tmp_path)) == str(tmp_path)


def test_stale_workspace_falls_back_to_file_dir(state_file, tmp_path):
    """记住的工作区不存在 → 回退到「记住的文件所在目录」✓。"""
    ws = tmp_path / 'tutorials'
    ws.mkdir()
    real = ws / 'S.py'
    real.write_text('x = 1\n', encoding='utf-8')
    page_mod.save_state({'workspace': str(tmp_path / 'NEW_DIR'),
                         'file': str(real)})
    page = page_mod.QtvscodePage(mode='edit', workspace='')
    page._started = True
    assert page.workspace == str(ws)
    assert page.file_path == str(real)


def test_editor_shows_left_sidebar_by_default():
    """代码编辑器初始化时**左侧栏（资源管理器）默认打开** ✓。

    * ``DOCK_SETTINGS`` 不再把活动栏设成 ``hidden``（改 ``default``）；
    * 就绪后发 ``workbench.view.explorer`` 展开侧栏；
    * 「显示/隐藏左侧栏」按钮切的是 **Side Bar**（``toggleSidebarVisibility``）✓。
    """
    import inspect
    from miniqt.app.common import qtvscode_shared as shared

    assert shared.DOCK_SETTINGS.get(
        'workbench.activityBar.location') == 'default'
    source = inspect.getsource(page_mod.QtvscodePage)
    assert 'workbench.view.explorer' in source
    assert 'workbench.action.toggleSidebarVisibility' in source


def test_editor_opens_explorer_when_sidebar_closed(state_file, tmp_path):
    """侧栏没展开 → 就绪后发 ``workbench.view.explorer``；活动栏可见时不切它 ✓。"""
    import json

    class _Page:
        def __init__(self, state):
            self._state = state

        def runJavaScript(self, js, callback=None):          # noqa: N802
            if callable(callback):
                callback(json.dumps(self._state))

    class _View:
        def __init__(self, state):
            self._page = _Page(state)

        def page(self):
            return self._page

    class _Editor:
        def __init__(self, state):
            self.view = _View(state)

    class _Bridge:
        has_client = True

        def __init__(self):
            self.commands = []

        def request(self, method, params=None, **kwargs):
            if method == 'invokeCommand' and params:
                self.commands.append(params.get('command'))

    page = _make_page(tmp_path)
    page._editor = _Editor({'a': False, 's': True, 'x': False})
    bridge = _Bridge()
    page._bridge = bridge
    page._activity_shown = False
    page._status_toggle_sent = False
    page._sidebar_opened = False
    page._ensure_parts_hidden()
    assert 'workbench.view.explorer' in bridge.commands
    # 活动栏已可见（a=False）→ 不该再发 toggle（会把它切走 ✗）
    assert 'workbench.action.toggleActivityBarVisibility' not in bridge.commands
    assert page._hide_done is True
