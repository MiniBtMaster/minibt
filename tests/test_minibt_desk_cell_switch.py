"""多布局：商品搜索 / 键盘精灵换合约 **只换鼠标最后点击的那一格** ✓

用户 2026-10-29 反馈：实时图表左右两图，用工具栏「商品搜索」或键盘精灵选一个合约
→ **两个格子都换了**（左图也跳走），而不是只换最后点击的右图。

原因：`chart-page.ts` 发的 `switch_symbol` 只带 tab 的主合约、不带格子号 →
后端把整页当成“切合约”重开（`_on_switch_symbol` 直接 pop 掉 tab、清掉 layout）。

现在：前端带 `cell`（+ `prev` / `multi`），后端 `_switch_layout_cell()` 只改那一格
（symbols / cells / 该格指标 / 该格 K 线 / 持仓线 / 挂单线），tab 名不变 ✓
"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / 'jslib' / 'src' / 'desk' / name).read_text(encoding='utf-8')


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


def _two_cell_desk(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    tab = 'DCE.a2701'
    info = {
        'cycle': 60,
        'indicators': [{'key': 'ma'}],
        'layout': {
            'cols': 2, 'rows': 1,
            'symbols': [tab, 'DCE.m2701'],
            'cells': [
                {'symbol': tab, 'indicators': [{'key': 'ma'}]},
                {'symbol': 'DCE.m2701', 'indicators': [{'key': 'rsi'}]},
            ],
        },
    }
    desk.tabs[tab] = info
    return desk, tab


def _patches(desk):
    return [str(item) for item in desk.sent]


# ------------------------------------------------------------------ 后端
def test_switch_only_target_cell(tmp_path, monkeypatch):
    desk, tab = _two_cell_desk(tmp_path, monkeypatch)

    desk._on_switch_symbol({'from': tab, 'to': 'DCE.c2701',
                            'name': '玉米', 'cell': 1})

    layout = desk.tabs[tab]['layout']
    # 只有第 2 格变了，第 1 格 + tab 名都不动 ✓
    assert layout['symbols'] == [tab, 'DCE.c2701']
    assert layout['cells'][0]['symbol'] == tab
    assert layout['cells'][1]['symbol'] == 'DCE.c2701'
    assert desk.tabs.get('DCE.c2701') is None       # tab 没有改名 ✓
    # 第 1 格的指标保留，第 2 格清空（换合约不保留旧指标 ✓）
    assert layout['cells'][0]['indicators'] == [{'key': 'ma'}]
    assert layout['cells'][1]['indicators'] == []
    assert desk.tabs[tab]['indicators'] == [{'key': 'ma'}]
    # 推了「只换第 2 格」的补丁（前端按 cell 更新标题 ✓）
    con = ' '.join(_patches(desk))
    assert 'switch_symbol' in con and 'DCE.c2701' in con
    assert '"cell":1' in con or "'cell': 1" in con or 'cell' in con


def test_switch_cell_zero_keeps_tab_name_but_clears_tab_indicators(
        tmp_path, monkeypatch):
    desk, tab = _two_cell_desk(tmp_path, monkeypatch)
    desk.tabs[tab]['strategy'] = {'name': 'ma'}

    desk._on_switch_symbol({'from': tab, 'to': 'DCE.c2701', 'cell': 0})

    layout = desk.tabs[tab]['layout']
    assert layout['symbols'] == ['DCE.c2701', 'DCE.m2701']
    assert 'strategy' not in desk.tabs[tab]         # 旧策略属于旧合约 ✓
    assert desk.tabs[tab]['indicators'] == []
    assert desk.tabs.get('DCE.c2701') is None       # tab 名仍是旧的 ✓
    # 第 2 格完全不动 ✓
    assert layout['cells'][1]['symbol'] == 'DCE.m2701'
    assert layout['cells'][1]['indicators'] == [{'key': 'rsi'}]


def test_single_cell_still_renames_tab(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    tab = 'DCE.a2701'
    desk.tabs[tab] = {'cycle': 60,
                      'layout': {'symbols': [tab], 'cells': [{'symbol': tab}]}}

    desk._on_switch_symbol({'from': tab, 'to': 'DCE.c2701', 'cell': 0})

    # 单图：老行为（tab 改名，K 线 / 账户按新合约重推 ✓）
    assert tab not in desk.tabs
    assert 'DCE.c2701' in desk.tabs
    assert any('switch_symbol' in item for item in _patches(desk))


# ------------------------------------------------------------------ 前端
def test_frontend_sends_cell_for_sprite_and_search():
    page = _read('chart-page.ts')
    # 键盘精灵选合约 → 带 cell / prev / multi ✓
    assert page.count("prev: current, multi: this.cells.length > 1,") >= 2
    assert 'const cell = this.activeCell;' in page
    assert "this.options.onCommand?.('switch_symbol', {" in page


def test_frontend_updates_only_that_cell():
    page = _read('chart-page.ts')
    app = _read('app.ts')
    # 只改该格的合约 / 图例标题 / 指标 / 持仓线 ✓
    assert 'setCellSymbol(cell: number, symbol: string, name = \'\'): void {' in page
    assert 'this.cellSymbols[index] = symbol;' in page
    assert 'this._refreshCellTitle(index);' in page
    assert 'this.hidePositionLine(index);' in page
    assert 'this.cellLegendTitles.push(title);' in page
    # app：带 `cell` 的 switch_symbol 不再重命名整个 tab ✓
    assert "if (typeof patch.cell === 'number') {" in app
    assert 'page.setCellSymbol(Number(patch.cell),' in app


# --------------------------------------------------- 手动切布局（后端不知道）
def test_layout_sync_records_cells(tmp_path, monkeypatch):
    """工具栏切的布局是**前端**行为 → `layout_sync` 必须让后端记住每格合约 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    tab = 'SHFE.ag2612'
    desk.tabs[tab] = {'cycle': 60}

    desk._on_layout_sync({'symbol': tab, 'cols': 2, 'rows': 1,
                          'symbols': [tab, 'SHFE.au2612']})

    layout = desk.tabs[tab]['layout']
    assert layout['cols'] == 2 and layout['rows'] == 1
    assert layout['symbols'] == [tab, 'SHFE.au2612']
    assert layout['cells'][1]['symbol'] == 'SHFE.au2612'


def test_layout_sync_keeps_indicators_of_unchanged_cells(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    tab = 'SHFE.ag2612'
    desk.tabs[tab] = {'cycle': 60,
                      'layout': {'cols': 2, 'rows': 1,
                                 'symbols': [tab, 'SHFE.au2612'],
                                 'cells': [{'symbol': tab,
                                            'indicators': [{'key': 'ma'}]},
                                           {'symbol': 'SHFE.au2612',
                                            'indicators': [{'key': 'rsi'}]}]}}

    # 同一个合约再同步一次 → 指标保留 ✓
    desk._on_layout_sync({'symbol': tab, 'cols': 2, 'rows': 1,
                          'symbols': [tab, 'SHFE.au2612']})

    cells = desk.tabs[tab]['layout']['cells']
    assert cells[0]['indicators'] == [{'key': 'ma'}]
    assert cells[1]['indicators'] == [{'key': 'rsi'}]


def test_switch_cell_when_backend_never_heard_of_layout(tmp_path, monkeypatch):
    """后端只认识单格，但前端报了 `cells` + `multi` → 仍只切那一格 ✓

    这正是用户 2026-10-29 的场景：打开 SHFE.ag2612 → 工具栏切左右布局
    （纯前端）→ 在格 2 搜 au2612 → 以前两个图都跳走 ✗
    """
    desk = _desk(tmp_path, monkeypatch)
    tab = 'SHFE.ag2612'
    desk.tabs[tab] = {'cycle': 60}          # 没有 layout（后端不知道有第 2 格）

    desk._on_switch_symbol({
        'from': tab, 'to': 'SHFE.au2612', 'name': '黄金2612',
        'cell': 1, 'prev': tab, 'multi': True, 'cells': [tab, tab],
    })

    layout = desk.tabs[tab]['layout']
    assert layout['symbols'] == [tab, 'SHFE.au2612']
    assert desk.tabs.get('SHFE.au2612') is None     # tab 没被重开 ✓
    # 第 1 格还是 ag2612（合约没变，指标也不用清 ✓）
    assert layout['cells'][0]['symbol'] == tab


def test_frontend_syncs_layout_and_cells():
    page = _read('chart-page.ts')
    # ① 切布局 / 关掉某一格 → 通知后端（否则第 2..N 格拿不到真数据 ✓）
    assert "this.options.onCommand?.('layout_sync', {" in page
    assert 'this._syncLayoutToBackend();' in page
    assert page.count('this._syncLayoutToBackend();') >= 2
    # ② 切合约时把「每格合约」一起报给后端 ✓
    assert page.count('cells: this.cellSymbols.slice(),') >= 2


# ------------------------------------------------ 多布局：给「其它格」加指标
def test_add_indicator_to_other_cell_uses_cell_symbol(tmp_path, monkeypatch):
    """前端发的是**该格合约**（`symbolForCell(cell)`），不是 tab 名 ✓

    用户 2026-10-30 反馈：格 2 用「指标」菜单 / 键盘精灵 / 右键收藏加指标，
    第一次跑到格 1，之后都加不进去。原因：`_on_add_indicator` 没把格子合约
    解析回 tab → `tabs.setdefault(格子合约)` 建了个幽灵 tab，指标落在那个
    空 tab 的第 1 格上；推回去的补丁 `symbol` 也是格子合约 →
    前端 `pages.get('chart:<格子合约>')` 找不到，整包丢掉 ✗
    """
    desk, tab = _two_cell_desk(tmp_path, monkeypatch)

    desk._on_add_indicator({'symbol': 'DCE.m2701', 'key': 'MA', 'cell': 1})

    assert desk.tabs.get('DCE.m2701') is None            # 没有幽灵 tab ✓
    layout = desk.tabs[tab]['layout']
    assert [item['key'] for item in layout['cells'][0]['indicators']] == ['ma']
    assert [item['key'] for item in layout['cells'][1]['indicators']] \
        == ['ma' if False else 'rsi', 'MA']
    # 补丁必须用**主 tab** 当 symbol + 带 cell（前端按 cell 落到那一格 ✓）
    con = ' '.join(_patches(desk))
    assert '"symbol":"DCE.a2701"' in con
    assert '"cell":1' in con
    assert '"symbol":"DCE.m2701"' not in con


def test_repeated_adds_to_other_cell_accumulate(tmp_path, monkeypatch):
    """继续加第 2 / 3 个指标也要成功（以前第二次开始静默失败 ✗）"""
    desk, tab = _two_cell_desk(tmp_path, monkeypatch)
    desk.tabs[tab]['layout']['cells'][1]['indicators'] = []

    for key in ('MA', 'RSI', 'KDJ'):
        desk._on_add_indicator({'symbol': 'DCE.m2701', 'key': key, 'cell': 1})

    cells = desk.tabs[tab]['layout']['cells']
    assert [item['key'] for item in cells[1]['indicators']] == ['MA', 'RSI', 'KDJ']
    assert cells[0]['indicators'] == [{'key': 'ma'}]      # 格 1 不动 ✓
    # 三条都推了 cell=1 的补丁
    patches = [item for item in desk.sent if '"cell":1' in str(item)]
    assert len(patches) >= 3


def test_add_indicator_fills_cells_from_symbols(tmp_path, monkeypatch):
    """老布局只登记了 `symbols`（没有 `cells`）→ 按 symbols 补齐再落格 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    tab = 'SHFE.ag2612'
    desk.tabs[tab] = {'cycle': 60,
                      'layout': {'cols': 2, 'rows': 1,
                                 'symbols': [tab, 'SHFE.au2612']}}

    desk._on_add_indicator({'symbol': 'SHFE.au2612', 'key': 'RSI', 'cell': 1})

    cells = desk.tabs[tab]['layout']['cells']
    assert len(cells) == 2
    assert cells[0]['symbol'] == tab
    assert [item['key'] for item in cells[1]['indicators']] == ['RSI']


def test_frontend_routes_indicator_patch_by_layout():
    """`case 'indicator'` 也要按布局反查页面（和 bars / positions 一致 ✓）"""
    app = _read('app.ts')
    segment = app.split("case 'indicator': {", 1)[1].split('case ', 1)[0]
    assert '_chartPageFor' in segment
    assert "pages.get(`chart:${patch.symbol}`)" not in segment
    # 「指标」菜单：实时图表也带活动格（以前只有本地图表带 → 永远加格 1 ✗）
    assert 'const chartCell = page?.activeCellIndex ?? 0;' in app
    assert app.count('cell: local ? localCell : chartCell,') >= 2
