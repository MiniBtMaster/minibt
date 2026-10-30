"""加载策略后的多布局规则（本地图表 / 实时图表 ✓）

用户 2026-10-30 要求（都是在**已加载策略**的前提下；没加载策略走原逻辑）：

1. 布局菜单里**格数 < 策略合约数**的布局 → 禁用；
2. 格数 **相等** → 可以切（切完保持策略：合约按格对上，不能两格同一个）；
3. 格数 **更大** → 可以切，多出来的格子没有策略、保持原样；
4. 加载策略时如果**策略合约数 < 当前格数** → 保持当前布局，多余格不关
   （以前实时图表会把多余格删掉 ✗）。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(name: str) -> str:
    return (DESK_TS / name).read_text(encoding='utf-8')


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, local_data, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(local_data, 'STATE_FILE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(local_data, 'FOLDERS_FILE',
                        str(tmp_path / 'folders.json'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.log_to_stdout = False
    desk.log_to_ui = False
    return desk


def _patches(desk):
    import json
    out = []
    for script in desk.sent:
        text = str(script)
        if text.startswith('window.__desk.applyPatch('):
            out.append(json.loads(text[len('window.__desk.applyPatch('):-2]))
    return out


# ------------------------------------------------ 策略合约 < 现有格数（实时）
def test_realtime_strategy_keeps_extra_cells(tmp_path, monkeypatch):
    """2 个合约放进 3 格布局 → 布局不变、多余格不关 ✓"""
    from minibt.desk import protocol, strategy_plan
    desk = _desk(tmp_path, monkeypatch)
    tab = 'DCE.a2701'
    cells = [{'symbol': tab, 'indicators': [{'key': 'MA'}]},
             {'symbol': 'DCE.b2701', 'indicators': [{'key': 'RSI'}]},
             {'symbol': 'DCE.c2701', 'indicators': []}]
    desk.tabs[tab] = {'cycle': 60,
                      'indicators': [{'key': 'MA'}],
                      'layout': {'cols': 3, 'rows': 1,
                                 'symbols': [tab, 'DCE.b2701', 'DCE.c2701'],
                                 'cells': cells}}

    class Frame:
        def __len__(self):
            return 2

    monkeypatch.setattr(strategy_plan, 'analyze',
                        lambda path: {'contracts': ['DCE.b2701', 'DCE.c2701'],
                                      'klines': 0})
    monkeypatch.setattr(desk, '_resolve_realtime_contract',
                        lambda name, info: name)
    monkeypatch.setattr(desk, '_validate_realtime_contracts',
                        lambda names: [])
    monkeypatch.setattr(desk, '_strategy_frame',
                        lambda name, info=None, cycle=0: Frame())
    monkeypatch.setattr(protocol, 'bars_from_frame',
                        lambda frame, bar_count=0: [
                            {'time': 1, 'open': 1.0, 'high': 1.0,
                             'low': 1.0, 'close': 1.0, 'volume': 1.0}])

    prepared = desk._prepare_realtime_strategy(tab, desk.tabs[tab],
                                               '/tmp/x.py', object, 60)

    assert prepared.get('ok'), prepared
    layout = desk.tabs[tab]['layout']
    assert layout['symbols'] == [tab, 'DCE.b2701', 'DCE.c2701']   # 3 格还在 ✓
    assert len(layout['cells']) == 3                               # 没被删 ✓
    # 合约按「已有同名格」对上去（b→格2、c→格3），格 1 不动 ✓
    assert prepared['cells'] == [1, 2]
    # 没有推「切布局」补丁（前端不会被重建成 2 格 ✓）
    layouts = [item for item in _patches(desk) if item['type'] == 'layout']
    assert not layouts


# ------------------------------------------------ 格数 < 策略合约 → 拒绝切换
def test_set_layout_rejects_smaller_layout(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    tab = 'DCE.a2701'
    desk.tabs[tab] = {'cycle': 60, 'strategy_contracts': ['DCE.a2701',
                                                          'DCE.b2701'],
                      'layout': {'cols': 2, 'rows': 1,
                                 'symbols': [tab, 'DCE.b2701'],
                                 'cells': [{'symbol': tab},
                                           {'symbol': 'DCE.b2701'}]}}
    desk._on_set_layout({'symbol': tab, 'cols': 1, 'rows': 1})
    assert desk.tabs[tab]['layout']['symbols'] == [tab, 'DCE.b2701']   # 没变 ✓
    con = ' '.join(str(item) for item in desk.sent)
    assert '策略需要 2 个图表' in con


# ------------------------------------------------ 换布局后重推策略线（含多余格）
def test_layout_sync_repushes_strategy_lines(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    tab = 'DCE.a2701'
    line = {'key': 'editor:S:line:0', 'label': 'ma'}
    desk.tabs[tab] = {
        'cycle': 60,
        'strategy': {'name': 'S', 'path': '/tmp/s.py'},
        'strategy_items': [line],
        'strategy_groups': {'DCE.a2701': [line]},
        'strategy_contracts': ['DCE.a2701'],
        'layout': {'cols': 3, 'rows': 1,
                   'symbols': [tab, 'DCE.b2701', 'DCE.c2701'],
                   'cells': [{'symbol': tab, 'indicators': []},
                             {'symbol': 'DCE.b2701', 'indicators': []},
                             {'symbol': 'DCE.c2701', 'indicators': []}]},
    }
    desk.sent.clear()
    desk._on_layout_sync({'symbol': tab, 'cols': 3, 'rows': 1,
                          'symbols': [tab, 'DCE.b2701', 'DCE.c2701']})

    patches = _patches(desk)
    # 格 1 的策略线重推了（换布局后前端重建了格子 ✓）
    assert any(item['type'] == 'indicator'
               and item.get('strategy') == 'S'
               and any(str(line.get('key', '')).startswith('editor:')
                       for line in (item.get('items') or []))
               for item in patches)
    # 策略合约只有 1 个 → 第 2/3 格**不画**策略线 ✓
    for item in patches:
        if item.get('type') == 'indicator' and item.get('cell'):
            assert not [line for line in (item.get('items') or [])
                        if str(line.get('key', '')).startswith('editor:')]


# ------------------------------------------------ 本地：合约 ≤ 格数 → 保持布局
def test_local_autolayout_keeps_extra_cells(tmp_path, monkeypatch):
    from minibt.desk import local_data
    desk = _desk(tmp_path, monkeypatch)
    desk._local_cell_names = {0: 'pp2609_60', 1: 'l2609_60',
                              2: 'test'}
    desk._active_local_page = 'local:1'
    desk.sent.clear()
    desk._auto_layout_local(['pp2609_60', 'l2609_60'], current='pp2609_60')

    # 没有推「切布局」补丁（3 格不变 ✓）
    assert not [item for item in _patches(desk) if item['type'] == 'layout']
    # 两个合约装进原来的格 1 / 格 2，格 3（test）保持不动 ✓
    loaded = [(item['name'], item['cell']) for item in _patches(desk)
              if item['type'] == 'local_kline']
    assert ('pp2609_60', 0) in loaded and ('l2609_60', 1) in loaded
    assert ('test', 2) not in loaded
    assert desk._local_cell_names == {0: 'pp2609_60', 1: 'l2609_60',
                                      2: 'test'}


# ------------------------------------------------------------------ 前端
def test_frontend_layout_presets_disabled_by_strategy():
    page = _read('chart-page.ts')
    assert 'private strategyCells = 0;' in page
    assert 'this._noteStrategyCells(payload as unknown as Record<string, unknown>);' in page
    assert "payload['strategyContracts']" not in page      # 后端字段名 ✓
    assert 'strategyContracts' in page
    # 预设 / 已保存布局都按策略禁用更小的布局 ✓
    assert 'disabled: !!this.strategyCells' in page
    assert page.count('item.cells.length < this.strategyCells') >= 2
    # 兜底：setLayoutSpec 里也拦一下 ✓
    assert '策略需要 ${this.strategyCells} 个图表，不能切到更少的布局' in page
    # 右键菜单的布局子菜单同一份（带禁用 ✓）
    assert 'private _contextLayoutItems(): MenuItem[] {' in page
    assert 'layoutItems: this._contextLayoutItems(),' in page

    local = _read('local-chart-page.ts')
    assert 'private strategyCells = 0;' in local
    assert 'disabled: !!this.strategyCells' in local
    assert local.count('item.cells.length < this.strategyCells') >= 2
    assert '策略需要 ${this.strategyCells} 个图表，不能切到更少的布局' in local


def test_frontend_keeps_cell_symbols_on_layout_change():
    """换布局不再把所有格重置成主合约（否则策略两格同一个合约 ✗）"""
    page = _read('chart-page.ts')
    block = page.split('private _buildCells(): void {', 1)[1][:5000]
    assert 'const oldSymbols = this.cellSymbols.slice();' in block
    assert 'this.cellSymbols.push(oldSymbols[index] || oldSymbols[0]' in block


def test_frontend_local_layout_syncs_cells():
    page = _read('local-chart-page.ts')
    block = page.split('setLayoutSpec(spec: DeskLayoutSpec, sync = true): void {',
                       1)[1][:4000]
    assert 'if (sync) {' in block
    assert "this.options.onCommand?.('local_cells', {" in block
