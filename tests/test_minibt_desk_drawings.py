"""多布局画线：**共用一个工具** + 按「合约|周期」本地持久化 ✓

用户 2026-10-29 需求：

1. 多图表布局里所有图共用一个画线工具，统一由工具栏「画线」按钮显隐；
2. 画线本地持久化，键 = `合约|周期`（同品种不同周期各画各的，
   **不能**把同品种所有周期的画线混到一个周期里显示 ✗）。
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / 'jslib' / 'src' / 'desk' / name).read_text(encoding='utf-8')


@pytest.fixture()
def store(tmp_path, monkeypatch):
    from minibt.desk import drawings
    target = tmp_path / 'drawings.json'
    monkeypatch.setattr(drawings, 'drawings_file', lambda: str(target))
    monkeypatch.setattr(drawings, '_CACHE', {})
    monkeypatch.setattr(drawings, '_LOADED', False)
    yield drawings, target
    monkeypatch.setattr(drawings, '_CACHE', {})
    monkeypatch.setattr(drawings, '_LOADED', False)


def _line(name='TrendLine'):
    return {'type': name, 'points': [{'time': 1, 'logical': 0}],
            'options': {'lineColor': '#2962FF'}}


# ---------------------------------------------------------------- 存储
def test_key_is_symbol_and_cycle(store):
    drawings, _ = store
    assert drawings.drawing_key('SHFE.ag2612', 60) == 'SHFE.ag2612|60'
    assert drawings.drawing_key('SHFE.ag2612', 300) == 'SHFE.ag2612|300'
    # 本地图表用数据名当合约，周期一样要分开 ✓
    assert drawings.drawing_key('l2609_60', '60') == 'l2609_60|60'
    assert drawings.drawing_key('SHFE.ag2612', None) == 'SHFE.ag2612'


def test_save_is_per_cycle_and_persisted(store):
    drawings, target = store
    drawings.save('SHFE.ag2612|60', [_line()])
    drawings.save('SHFE.ag2612|300', [_line('Box')])

    # 同品种不同周期互不影响 ✓（用户特意强调：不能混在一起）
    assert len(drawings.get('SHFE.ag2612|60')) == 1
    assert drawings.get('SHFE.ag2612|60')[0]['type'] == 'TrendLine'
    assert drawings.get('SHFE.ag2612|300')[0]['type'] == 'Box'
    assert drawings.get('SHFE.ag2612') == []
    # 真的落盘了 ✓
    saved = json.loads(target.read_text(encoding='utf-8'))
    assert set(saved) == {'SHFE.ag2612|60', 'SHFE.ag2612|300'}
    # 空列表 = 删除该键 ✓
    drawings.save('SHFE.ag2612|60', [])
    assert drawings.get('SHFE.ag2612|60') == []
    assert 'SHFE.ag2612|60' not in json.loads(
        target.read_text(encoding='utf-8'))


def test_clear_one_key_keeps_others(store):
    drawings, _ = store
    drawings.save('A|60', [_line()])
    drawings.save('A|300', [_line()])
    drawings.clear('A|60')
    assert drawings.get('A|60') == []
    assert len(drawings.get('A|300')) == 1
    drawings.clear()
    assert drawings.all_drawings() == {}


# ---------------------------------------------------------------- 命令
def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.log_to_stdout = False
    desk.log_to_ui = False
    return desk


def test_desk_push_and_clear_drawings(store, tmp_path, monkeypatch):
    drawings, _ = store
    desk = _desk(tmp_path, monkeypatch)
    desk._on_save_drawings({'key': 'SHFE.ag2612|60', 'items': [_line()]})
    assert len(drawings.get('SHFE.ag2612|60')) == 1

    desk._on_drawings({'key': 'SHFE.ag2612|60'})
    pushed = ' '.join(str(item) for item in desk.sent)
    assert 'drawings' in pushed and 'TrendLine' in pushed

    desk._on_clear_drawings({'key': 'SHFE.ag2612|60'})
    assert drawings.get('SHFE.ag2612|60') == []
    assert 'drawings' in ' '.join(str(item) for item in desk.sent)


def test_desk_drawings_ignores_empty_key(store, tmp_path, monkeypatch):
    drawings, _ = store
    desk = _desk(tmp_path, monkeypatch)
    desk._on_save_drawings({'items': [_line()]})       # 没 key → 不落盘 ✓
    assert drawings.all_drawings() == {}


# ---------------------------------------------------------------- 前端
def test_shared_toolbox_and_hook():
    sync = _read('drawings-sync.ts')
    # hook 住 pylightcharts 的 save_drawings 回调 ✓
    assert "text.startsWith('save_drawings')" in sync
    assert "rest.indexOf('_~_')" in sync
    assert 'SAVERS' in sync
    # 多布局共用一个工具：只显示当前格 ✓
    assert 'showToolBox(visible: boolean, activeId: string): void {' in sync
    assert "cell.id === activeId" in sync
    # 同键的多格拿同一份画线 ✓
    assert 'this.cache.set(key, items)' in sync


def test_pages_wire_drawings_sync():
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = _read(name)
        assert "from './drawings-sync'" in page
        assert 'private _drawings(): DrawingsSync {' in page
        assert "save: (key, items) => this.options.onCommand?.(" in page
        assert "'save_drawings', { key, items }" in page
        assert "'drawings', { key }" in page
        assert 'applyDrawings(payload: { key?: string; items?: unknown[] }): void {' in page
        # ★ 键 = 合约|周期（同品种不同周期分开 ✓）
        assert 'return `${symbol}|${Number(this.cycle) || 0}`;' in page
        # 画线工具箱 = 共用一个（只显示当前格 ✓）
        assert 'sync.showToolBox(this.toolBoxOn, this._activeHandlerId());' in page
        # 换周期 / 换合约 / 换布局 / 清空 都要刷新 ✓
        assert 'this._refreshDrawings();' in page
        assert 'this._drawings().clear(this._drawingKey());' in page
    app = _read('app.ts')
    assert "case 'drawings': {" in app
    assert 'page.applyDrawings(patch as never);' in app


# ------------------------------------------------- 左侧导航栏（对称二级报价）
def test_toolbox_lives_in_left_rail():
    """画线工具做成**整块图表区左侧**的导航条（对称右侧二级报价）✓"""
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = _read(name)
        # rail 插在 body 最左边（`main` 之前，book 在右边）✓
        assert "this.drawRail.className = 'desk-draw-rail';" in page
        assert 'body.append(this.drawRail, main, this.book.element);' in page
        # 工具栏按钮 → 显隐 + 搬进/搬出当前格的工具箱 ✓
        assert 'private _applyToolBoxMode(): void {' in page
        assert 'private _attachToolBoxToRail(): void {' in page
        assert 'private _detachToolBoxFromRail(): void {' in page
        assert "if (this.drawRail) this.drawRail.style.display = '';" in page
        assert "if (this.drawRail) this.drawRail.style.display = 'none';" in page
        # 换格 / 换布局 / 重画都要跟着搬 ✓
        assert 'if (this.toolBoxOn) this._applyToolBoxMode();' in page
        assert 'this._detachToolBoxFromRail();' in page
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(
        encoding='utf-8')
    assert '.desk-draw-rail {' in css
    assert 'flex: 0 0 46px;' in css                # 窄于右侧 210px 的二级报价 ✓
    assert '.desk-draw-rail-box {' in css
    assert 'position: static !important;' in css   # 原本绝对定位 → 改成流式 ✓


def test_drawing_target_follows_last_clicked_cell():
    """多布局：画线工具作用于**鼠标最后点击的那一格** ✓

    网格里每格 `pointerdown` → `_activateCell(index)` → 若「画线」开着就把
    **该格**的工具箱搬进左侧导航条（每个 `Handler` 自带一个 `ToolBox`，
    里面的 `DrawingTool` 绑的是该格自己的 series）→ 画线落在那一格上。
    """
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = _read(name)
        # ① 点哪一格就激活哪一格 ✓
        assert "this._activateCell(index);" in page
        # ② 激活时把工具箱切到那一格（否则会一直画在第一格 ✗）
        assert 'if (this.toolBoxOn) this._applyToolBoxMode();' in page
        # ③ 搬进导航条的是**活动格**的 handler ✓
        assert 'const handler = this.cells[this.activeCell] as unknown as {' in page
        # ④ 换格时旧工具箱放回原格、再搬新的 ✓
        assert 'this._detachToolBoxFromRail();\n        this.railBox = {' in page


def test_rail_uses_original_icons_and_2px_gaps():
    """导航条：图标**保持原大小**，工具箱距导航条 上 / 左 / 右 各 2px ✓"""
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(
        encoding='utf-8')
    rail = css.split('.desk-draw-rail {', 1)[1].split('}', 1)[0]
    box = css.split('.desk-draw-rail-box {', 1)[1].split('}', 1)[0]
    # 导航条四边各 2px（左/右/上给工具箱留 2px ✓）
    assert 'padding: 2px;' in rail
    assert 'align-items: stretch;' in rail
    # 工具箱铺满导航条内容宽度 → 左右正好各 2px ✓
    assert 'width: 100%;' in box
    assert 'margin: 0;' in box
    # 图标不再缩放（29px 原样）✓
    assert 'toolbox-button svg' not in css


def test_toolbox_buttons_have_tooltips():
    """画线图标要有**工具名称 tooltip**（中文 · 英文 · 快捷键）✓"""
    src = (ROOT / 'jslib' / 'src' / 'general' / 'toolbox.ts').read_text(
        encoding='utf-8')
    for label in ('趋势线 · TrendLine', '水平线 · Horizontal Line',
                  '射线 · Ray', '矩形 · Box', '垂直线 · Vertical Line',
                  '斐波那契回撤 · Fibonacci', '测量 · Measure',
                  '平行通道 · Parallel Channel', '仓位（多/空） · Position',
                  '安德鲁斯干草叉 · Andrews Pitchfork',
                  '三角形 · Triangle', '斐波那契扩展 · Fibonacci Extension',
                  '江恩扇形 · Gann Fan'):
        assert label in src, label
    # 原生 title：`趋势线 · TrendLine（Alt+T）` ✓
    assert 'elem.title = shortcut ? `${label}（${shortcut}）` : label;' in src
    assert "const shortcut = keyCmd.startsWith('Key') ? `Alt+${keyCmd.slice(3)}` : '';" in src
