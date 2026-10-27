"""P45/P46：代码编辑器（个人指标 / 策略）+ 可拖底部面板 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(path):
    return (ROOT / path).read_text(encoding='utf-8')


# ------------------------------------------------------- 后端：编辑器 API
def test_personal_editor_api(tmp_path, monkeypatch):
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    assert set(pi.ensure_directories()) == {'indicator', 'strategy'}

    made = pi.create_file('indicator', 'demo_ma')
    assert made['ok'] and made['name'] == 'demo_ma.py'
    assert 'BtIndicator' in made['text']          # 模板 ✓

    checked = pi.check_source(made['text'])
    assert checked['ok'] and checked['defines']

    # 语法错误 → 不写盘 ✓
    bad = pi.write_file(made['path'], 'def f(:')
    assert bad['ok'] is False and bad.get('line')

    files = pi.list_files()
    assert [item['name'] for item in files['indicators']] == ['demo_ma.py']
    assert pi.read_file(made['path'])['ok'] is True
    assert pi.delete_file(made['path'])['ok'] is True
    assert pi.read_file(made['path'])['ok'] is False


def test_strategy_template_and_paths(tmp_path, monkeypatch):
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    made = pi.create_file('strategy', 'demo_st')
    assert made['ok'] and 'Strategy' in made['text']
    # 目录穿越 / 非法名字一律拒绝 ✓
    assert pi.create_file('indicator', '../evil')['ok'] is False
    assert pi.write_file(str(tmp_path / 'x.txt'), 'x')['ok'] is False


def test_editor_commands_registered():
    app = _read('minibt/desk/app.py')
    for cmd in ('editor_list', 'editor_open', 'editor_save', 'editor_check',
                'editor_new', 'editor_delete'):
        assert f"'{cmd}': self._on_{cmd}" in app, cmd
    # 保存后重扫个人目录（指标立即可用 ✓）
    assert 'def _refresh_personal(self) -> None:' in app
    assert "'personal': True" in app
    prefs = _read('minibt/desk/user_prefs.py')
    assert "'dock_height'" in prefs


# ------------------------------------------------------- 前端：懒加载 / 面板
def test_editor_is_lazy_loaded():
    editor = (DESK_TS / 'code-editor.ts').read_text(encoding='utf-8')
    assert 'desk-editor.js' in editor
    assert 'window.DeskCodeEditor' in editor
    # desk.js 里不能再有 @codemirror（否则首屏白胖 ✗）
    built = (ROOT / 'pylightcharts' / 'js' / 'desk.js').read_text(
        encoding='utf-8', errors='ignore')
    assert "import('@codemirror/merge')" in built or 'desk-editor.js' in built
    assert (ROOT / 'pylightcharts' / 'js' / 'desk-editor.js').is_file()
    bundle = (DESK_TS / 'editor-bundle.ts').read_text(encoding='utf-8')
    assert 'DeskCodeEditor' in bundle and 'EditorView' in bundle


def test_editor_panel_sections():
    panel = (DESK_TS / 'editor-panel.ts').read_text(encoding='utf-8')
    # P57 起文件树改成「资源管理器」（不再分个人指标 / 策略两栏 ✓）
    for text in ('新建 ▾', '保存', '语法检查', '格式化', '加到图表', '刷新',
                 '刷新指标策略', '打开目录'):
        assert text in panel, text
    assert "'editor_save'" in panel and "'editor_check'" in panel
    assert 'onSave: () => this._save()' in panel      # Ctrl+S ✓


def test_editor_button_before_trade():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    # P60：两个按钮合并成「交易/编辑器」一个 ✓
    assert "'交易/编辑器'" in page
    assert "const editorButton = tradeButton;" in page
    assert 'openEditor(): void' in page
    tail = page.split('toolbar.append(', 1)[1].split(');', 1)[0]
    assert tail.index('editorButton') < tail.index('bookButton')


def test_dock_splitter_draggable():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    assert 'private _ensureDockSplitter(): void' in page
    assert 'desk-dock-splitter' in page
    assert "key: 'dock_height'" in page
    assert 'dblclick' in page                          # 双击复位 ✓
    css = (DESK_TS / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-dock-splitter' in css and 'row-resize' in css


def test_dock_has_code_tab():
    dock = (DESK_TS / 'account-dock.ts').read_text(encoding='utf-8')
    assert "['code', '编辑器']" in dock   # P63：标签改成「编辑器」✓
    assert "export type DockTab = 'account' | 'log' | 'code';" in dock
    assert 'public onEditorOpen' in dock
    # 面板补丁路由到当前看盘页 ✓
    app = (DESK_TS / 'app.ts').read_text(encoding='utf-8')
    assert "case 'editor_files':" in app
    assert "case 'editor_saved':" in app
