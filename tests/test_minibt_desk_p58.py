"""P58：缩放铺满 / 系统目录 / 打开兜底 / 配色 / 滚动 / 个人目录管理 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(path):
    return (ROOT / path).read_text(encoding='utf-8')


# ------------------------------------------------------- ① 缩放铺满
def test_zoom_uses_transform_and_fills():
    """`zoom:` 在 QtWebEngine 里缩 125% 会右侧 / 底部留白 ✗ → 改 transform ✓"""
    app = (DESK_TS / 'app.ts').read_text(encoding='utf-8')
    body = app.split('private _applyZoom(zoom: number): void {', 1)[1][:1600]
    assert 'transformOrigin' in body
    assert 'scale(${value})' in body
    assert "root.style.inset = 'auto'" in body
    assert 'root.style.zoom = \'\'' in body


# ------------------------------------------------------- ② 系统目录
def test_system_dir_menu():
    panel = (DESK_TS / 'editor-panel.ts').read_text(encoding='utf-8')
    assert "'系统目录 ▾'" in panel
    assert "'系统个人指标（personal/indicators）'" in panel
    assert "'系统个人策略（personal/strategies）'" in panel
    assert "'explorer_system_dir'" in panel
    app = _read('minibt/desk/app.py')
    assert "'explorer_system_dir': self._on_explorer_system_dir" in app
    body = app.split('def _on_explorer_system_dir', 1)[1][:900]
    assert '_pi.ensure_directories()' in body
    assert "if kind == 'all'" in body


# ------------------------------------------------------- ③ 打开兜底
def test_open_folder_uses_system_dialog():
    """P78：选目录一律走系统对话框（Qt 原生 → tkinter 兜底），不再手输 ✓"""
    app = _read('minibt/desk/app.py')
    assert 'def choose_directory(' in app
    assert 'def _tk_choose_directory(' in app
    assert "'ask_folder'" not in app                  # 不再让前端弹输入框 ✓
    assert "'explorer_set_root': self._on_explorer_set_root" in app
    assert "'personal_add_dir': self._on_personal_add_dir" in app
    ts = (DESK_TS / 'app.ts').read_text(encoding='utf-8')
    assert "case 'ask_folder':" in ts                 # 极端情况只提示 ✓
    assert "this.send('explorer_set_root', { path })" not in ts


# ------------------------------------------------------- ④ VS Code 配色
def test_vscode_syntax_colors():
    bundle = (DESK_TS / 'editor-bundle.ts').read_text(encoding='utf-8')
    assert 'VSCODE_DARK' in bundle and 'VSCODE_LIGHT' in bundle
    assert '#DCDCAA' in bundle          # 函数黄色（用户要求 ✓）
    assert '#569CD6' in bundle          # True/False/None 蓝色 ✓
    assert 'tags.bool' in bundle and 'tags.function(tags.variableName)' in bundle
    # 不再用默认配色（函数是紫的 ✗）
    assert 'defaultHighlightStyle' not in bundle


# ------------------------------------------------------- ⑤ 编辑器可滚动
def test_editor_scrolls():
    panel = (DESK_TS / 'editor-panel.ts').read_text(encoding='utf-8')
    assert '.desk-editor-host .cm-scroller { overflow: auto; }' in panel
    assert '.desk-editor-host .cm-editor { height: 100%; flex: 1 1 auto;' in panel
    css = (DESK_TS / 'desk.css').read_text(encoding='utf-8')
    body = css.split('.desk-dock-editor {', 1)[1].split('}', 1)[0]
    assert 'min-height: 0' in body and 'height: 100%' in body


# ------------------------------------------------------- ⑥ 个人目录管理
def test_personal_menu_entries():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    body = page.split('openIndicatorMenu(anchor: HTMLElement): void {', 1)[1]
    for text in ('添加个人指标…', '添加个人策略…', '个人指标策略管理…'):
        assert text in body, text
    # 「管理」在「添加个人策略」之后 ✓
    assert body.index('添加个人策略…') < body.index('个人指标策略管理…')
    assert "'personal_menu'" in body

    menu = (DESK_TS / 'indicator-menu.ts').read_text(encoding='utf-8')
    assert "'添加个人指标'" in menu and "'添加个人策略'" in menu
    assert "'个人指标策略管理'" in menu
    # 管理对话框隐藏默认目录 ✓
    assert 'const custom = items.filter((item) => !item.default);' in menu
    assert "personal/indicators" in menu


def test_personal_dirs_persist_and_defaults(tmp_path, monkeypatch):
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    dirs = pi.ensure_directories()
    assert set(dirs) == {'indicator', 'strategy'}
    assert dirs['indicator'].endswith('indicators')
    assert dirs['strategy'].endswith('strategies')
    # 默认目录登记一次，第二次不会重复 ✓
    before = len(pi.directories())
    pi.ensure_directories()
    assert len(pi.directories()) == before == 2
    # 再收录一个外部目录 → 持久化（重新读配置还在 ✓）
    extra = tmp_path / 'my_ind'
    extra.mkdir()
    assert pi.add_directory(str(extra), 'indicator')['ok']
    assert any(item['path'].endswith('my_ind') for item in pi.directories())


# ------------------------------------------------------- ⑦ 按钮已删除
def test_refresh_button_removed():
    panel = (DESK_TS / 'editor-panel.ts').read_text(encoding='utf-8')
    assert "'刷新指标策略'" not in panel
    app = _read('minibt/desk/app.py')
    assert "'personal_refresh'" not in app
    assert '_on_personal_refresh' not in app
