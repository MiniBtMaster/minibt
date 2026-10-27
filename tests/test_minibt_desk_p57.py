"""P57：关页面即退出 / BtIndicator 可加图 / 资源管理器 / 编辑器右键 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(path):
    return (ROOT / path).read_text(encoding='utf-8')


# ------------------------------------------------------- ① 关页面不报错 + 退出
def test_web_tolerates_aborted_connections():
    web = _read('minibt/desk/web.py')
    # 浏览器关页面时的 WinError 10053 不再刷 traceback ✓
    assert 'class _Server(ThreadingHTTPServer)' in web
    assert 'ConnectionAbortedError' in web and 'handle_error' in web
    assert "_Server((str(host or '127.0.0.1')" in web
    # 页面全关 → 自动退出（用户要求 ✓）
    assert 'def ever_connected' in web and 'def count' in web
    assert 'CLOSE_GRACE' in web and '页面已关闭' in web
    assert 'import time' in web


# ------------------------------------------------------- ② BtIndicator 直接加图
def _frame(rows: int = 120):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    close = 100 + np.arange(rows, dtype=float)
    return pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close - 1, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': np.ones(rows),
        'symbol': 'SHFE.demo01', 'duration': 60,
    })


def test_scan_and_compute_bt_indicator_class(tmp_path, monkeypatch):
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    made = pi.create_file('indicator', 'demo_ma')
    assert 'def next(self):' in made['text']      # 模板用 next()（BtIndicator ✓）

    items = pi.scan('indicator')
    names = {item['name']: item for item in items}
    assert 'demo_ma' in names and 'demo_ma_indicator' in names
    assert names['demo_ma_indicator'].get('cls') is True

    frame = _frame()
    func_items = pi.compute(frame, names['demo_ma']['key'])
    assert func_items and func_items[0]['kind'] == 'line'
    cls_items = pi.compute(frame, names['demo_ma_indicator']['key'])
    assert cls_items, 'BtIndicator 类没算出线条'
    assert cls_items[0]['overlay'] is True        # 类上 overlap=True ✓
    assert len(cls_items[0]['data']) > 50


def test_editor_add_indicator_uses_path(tmp_path, monkeypatch):
    """按**文件路径**加指标（分类自动算，不靠前端猜 ✓）"""
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    made = pi.create_file('indicator', 'demo_ma')

    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.tabs['SHFE.demo01'] = {'feed': None, 'cycle': 60, 'indicators': []}
    desk._on_editor_add_indicator({'path': made['path']})
    keys = [item['key'] for item in desk.tabs['SHFE.demo01']['indicators']]
    assert keys and all(key.startswith('pi:') for key in keys)
    assert any('demo_ma_indicator' in key for key in keys)


# ------------------------------------------------------- ③ 资源管理器
def test_explorer_operations(tmp_path, monkeypatch):
    from minibt.desk import explorer as fs
    from minibt.desk import personal as pi

    root = tmp_path / 'root'
    root.mkdir()
    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(root))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    monkeypatch.setattr(fs, 'DEFAULT_ROOT', str(root))

    assert fs.operate('new_file', {'path': str(root), 'name': 'a.py'},
                      str(root))['ok']
    assert fs.operate('new_folder', {'path': str(root), 'name': 'sub'},
                      str(root))['ok']
    listed = fs.entries(str(root), str(root))
    names = [item['name'] for item in listed['items']]
    # 目录在前、文件在后（默认根目录还会自动建 indicators/strategies ✓）
    assert names.index('sub') < names.index('a.py')
    assert 'indicators' in names and 'strategies' in names
    assert fs.operate('rename', {'path': str(root / 'a.py'), 'name': 'b.py'},
                      str(root))['ok']
    assert fs.operate('copy', {'path': str(root / 'b.py')}, str(root))['ok']
    assert fs.operate('paste', {'path': str(root / 'sub')}, str(root))['ok']
    assert (root / 'sub' / 'b.py').is_file()
    assert fs.operate('delete', {'path': str(root / 'b.py')}, str(root))['ok']
    # 越界 / 非法名字一律拒绝 ✓
    assert fs.entries(str(tmp_path), str(root))['ok'] is False
    assert fs.operate('new_file', {'path': str(root), 'name': '../x.py'},
                      str(root))['ok'] is False


def test_explorer_format_python():
    from minibt.desk import explorer as fs

    result = fs.format_python('x=1   \n\tif x:\n\t\tpass   ')
    assert result['ok'] and result['text'].endswith('\n')
    assert '\t' not in result['text']
    assert result['text'].splitlines()[0] == 'x=1'


def test_explorer_commands_registered():
    app = _read('minibt/desk/app.py')
    for cmd in ('explorer_list', 'explorer_pick', 'explorer_op',
                'explorer_check_personal', 'editor_format',
                'editor_add_indicator', 'explorer_system_dir',
                'explorer_set_root', 'personal_add_dir'):
        assert f"'{cmd}': self._on_{cmd}" in app, cmd
    # `_open_path` 是模块函数（以前写成 self._open_path 会 AttributeError ✗）
    assert 'error = _open_path(url)' in app
    assert 'error = _open_path(folder)' in app
    assert 'self._open_path(' not in app
    prefs = _read('minibt/desk/user_prefs.py')
    assert "'explorer_root'" in prefs


# ------------------------------------------------------- ④ 前端
def test_editor_toolbar_and_menus():
    panel = (DESK_TS / 'editor-panel.ts').read_text(encoding='utf-8')
    # P58：「打开目录」改名「系统目录 ▾」（两个系统目录）且仍在最左边 ✓
    assert "'系统目录 ▾'" in panel
    first = panel.split('toolbar.append(', 1)[1]
    assert first.index('folderButton') < first.index('newButton')
    # P58：用户确认「刷新指标策略」没用 → 按钮已删 ✓
    assert "'刷新指标策略'" not in panel
    # 资源管理器的右键菜单（新建文件 / 文件夹 / 剪切 / 复制 / 粘贴 / 重命名 / 删除）
    for text in ('新建文件…', '新建文件夹…', '剪切', '复制', '粘贴',
                 '重命名…', '删除'):
        assert text in panel, text
    # 编辑器右键菜单（添加到图表 / 格式化 / 语法检测 / 剪切 / 复制 / 粘贴）
    for text in ('添加到图表', '格式化', '语法检测', '全选'):
        assert text in panel, text
    assert "'editor_add_indicator'" in panel


def test_explorer_tree_is_folder_based():
    panel = (DESK_TS / 'editor-panel.ts').read_text(encoding='utf-8')
    assert 'setExplorer(' in panel
    assert "onCommand('explorer_list'" in panel
    assert '_toggleDir(' in panel
    assert 'desk-editor-sidehead' in panel      # 资源管理器顶部（vscode 样式 ✓）
    app = (DESK_TS / 'app.ts').read_text(encoding='utf-8')
    for case in ("case 'explorer':", "case 'explorer_personal':",
                 "case 'editor_formatted':"):
        assert case in app, case
