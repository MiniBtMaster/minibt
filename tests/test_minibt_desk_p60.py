"""P60：首次加载 K 线 / 原生选目录 / 日志 / 面板高度+最大化 / 合并按钮 / 回放 ✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(path):
    return (ROOT / path).read_text(encoding='utf-8')


# ------------------------------------------------------- ① 首次加载只有几根 K 线
def test_first_load_fits_after_resize():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    assert 'private needsFit = true;' in page
    assert 'private _fitIfNeeded(): void' in page
    # mount 里下一帧再量一次并 fit（页面刚建时宽度是 0 ✗）
    mount = page.split('mount(): void {', 1)[1].split('\n    }', 1)[0]
    assert 'requestAnimationFrame' in mount
    assert '_fitIfNeeded()' in mount
    # resize 每次都尝试 fit（一次之后清标记 ✓）
    assert 'this._sizeCells(box);\n        this._fitIfNeeded();' in page
    assert 'this.needsFit = false;' in page


# ------------------------------------------------------- ② 系统目录对话框
def test_native_folder_dialog_preferred():
    app = _read('minibt/desk/app.py')
    body = app.split('def _on_explorer_pick', 1)[1][:1400]
    # P78：统一走 `choose_directory`（Qt 原生 → tkinter 兜底 ✓）
    assert "self.choose_directory('选择要打开的文件夹')" in body
    assert '已取消选择目录' in body
    body2 = app.split('def _on_pick_personal', 1)[1][:1400]
    assert 'self.choose_directory(' in body2
    # Qt 侧确实提供原生对话框 ✓
    window = _read('minibt/desk/app_window.py')
    assert 'QFileDialog.getExistingDirectory' in window


# ------------------------------------------------------- ③ 失败写运行日志
def test_add_indicator_and_dir_failures_are_logged():
    app = _read('minibt/desk/app.py')
    for key in ("self.push_log(f'导入目录失败：", 'self.push_log(message, \'error\')',
                '不在「我的脚本」里', '扫到 '):
        assert key in app, key


# ------------------------------------------------------- ④ 面板 1/3 + 最大化
def test_dock_height_one_third_and_maximize():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    body = page.split('toggleDock(visible?: boolean): boolean {', 1)[1][:1400]
    assert 'this.dockRatio = 1 / 3' in body          # 初始高度 = 页面 1/3 ✓
    assert '_applyDockRatio(total)' in body           # 窗口缩放按比例 ✓
    assert 'toggleDockMaximize(force?: boolean): boolean' in page
    assert 'desk-chart-body' in page                 # 最大化时隐藏图表 ✓
    dock = (DESK_TS / 'account-dock.ts').read_text(encoding='utf-8')
    assert 'desk-dock-maximize' in dock
    assert "maximize.textContent = '⤢'" in dock      # 初始「最大化」✓
    assert 'setMaximized(maximized: boolean)' in dock
    assert "button.textContent = maximized ? '⤡' : '⤢'" in dock


# ------------------------------------------------------- ⑤ 合并按钮
def test_merge_editor_and_trade_buttons():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    assert "'交易/编辑器'" in page
    assert "const editorButton = tradeButton;" in page
    assert "const tradeButton = this._toolButton(\n            '编辑器'" not in page


# ------------------------------------------------------- ⑥ 回放不贴右边
def test_replay_does_not_pin_to_right_edge():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    assert 'export const REPLAY_WINDOW' in page
    assert 'export const REPLAY_PADDING' in page
    block = page.split('private _syncReplayViewport', 1)[1].split(
        'private _applyReplayIndicators', 1)[0]
    # 只在首次 / seek 摆窗口；播放阶段不 setVisibleLogicalRange ✓
    assert 'if (reset || prev === 0 || Math.abs(current - prev) > 1)' in block
    assert 'to: current - 1 + REPLAY_PADDING' in block
    # 进入回放时关掉「首次 fit」，避免抢视窗 ✓
    assert 'this.needsFit = false;' in page
