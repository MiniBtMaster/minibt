"""P66：删除菜单含策略 / 指标与策略共存 / 内置指标可删 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / 'jslib' / 'src' / 'desk' / 'chart-page.ts'


def _desk(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import personal as pi
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))

    class Feed:
        kind = 'futures'
        api = None

        def available(self):
            return True

        def klines(self, symbol, cycle, length=500):
            rows = 200
            close = 101 + np.sin(np.arange(rows) / 7) * 3
            return pd.DataFrame({
                'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                             for i in range(rows)],
                'open': close + 0.4, 'high': close + 2, 'low': close - 2,
                'close': close, 'volume': np.ones(rows),
                'symbol': symbol, 'duration': cycle,
                'price_tick': 1.0, 'volume_multiple': 10,
            })

        def quotes(self, keys):
            return []

        def spec(self, symbol):
            return None

    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.futures = Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk.tabs['SHFE.demo01'] = {'feed': desk.futures, 'cycle': 60,
                               'indicators': []}
    return desk, pi


def test_indicator_and_strategy_coexist(tmp_path, monkeypatch):
    """策略最多 1 个、指标不限、两者共存（P66 ✓）"""
    desk, pi = _desk(tmp_path, monkeypatch)
    indicator = pi.create_file('indicator', 'c_ma')
    strategy = pi.create_file('strategy', 'c_st')

    desk._on_editor_add_indicator({'path': strategy['path']})
    desk._on_editor_add_indicator({'path': indicator['path']})
    payload = desk.indicator_payload('SHFE.demo01')
    keys = [item['key'] for item in payload.get('items') or []]
    assert any(key.startswith('editor:') for key in keys)       # 策略线 ✓
    assert any(key.startswith('pi:') for key in keys)       # 指标线 ✓
    assert payload.get('strategy') == 'c_st'
    assert desk.tabs['SHFE.demo01']['indicators']           # 指标没被清 ✓

    # 换策略 = 替换（指标不动 ✓）
    other = pi.create_file('strategy', 'c_st2')
    desk._on_editor_add_indicator({'path': other['path']})
    payload = desk.indicator_payload('SHFE.demo01')
    assert payload.get('strategy') == 'c_st2'
    assert len(desk.tabs['SHFE.demo01']['indicators']) >= 1


def test_remove_strategy_keeps_indicators(tmp_path, monkeypatch):
    desk, pi = _desk(tmp_path, monkeypatch)
    indicator = pi.create_file('indicator', 'r_ma')
    strategy = pi.create_file('strategy', 'r_st')
    desk._on_editor_add_indicator({'path': strategy['path']})
    desk._on_editor_add_indicator({'path': indicator['path']})

    desk._on_remove_strategy({'symbol': 'SHFE.demo01'})
    payload = desk.indicator_payload('SHFE.demo01')
    keys = [item['key'] for item in payload.get('items') or []]
    assert keys and all(not key.startswith('editor:') for key in keys)  # 策略没了
    assert any(key.startswith('pi:') for key in keys)               # 指标还在 ✓
    assert not payload.get('strategy')


def test_remove_indicator_accepts_strategy_kind(tmp_path, monkeypatch):
    """`remove_indicator{kind:'strategy'}` 也能删策略（兼容旧入口 ✓）"""
    desk, pi = _desk(tmp_path, monkeypatch)
    strategy = pi.create_file('strategy', 'k_st')
    desk._on_editor_add_indicator({'path': strategy['path']})
    desk._on_remove_indicator({'symbol': 'SHFE.demo01', 'key': 'st',
                               'kind': 'strategy'})
    assert not desk.tabs['SHFE.demo01'].get('strategy_items')


def test_clear_all_removes_both(tmp_path, monkeypatch):
    desk, pi = _desk(tmp_path, monkeypatch)
    desk._on_editor_add_indicator(
        {'path': pi.create_file('strategy', 'z_st')['path']})
    desk._on_editor_add_indicator(
        {'path': pi.create_file('indicator', 'z_ma')['path']})
    desk._on_remove_indicator({'symbol': 'SHFE.demo01', 'key': '*'})
    info = desk.tabs['SHFE.demo01']
    assert info['indicators'] == []
    assert not info.get('strategy_items')
    assert not info.get('strategy')


def test_async_custom_patch_keeps_strategy():
    """完整库是后台算的：旧快照不能把策略冲掉（P66 bug ✗）"""
    app = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    body = app.split('def _compute_custom', 1)[1][:2600]
    assert "latest = self.tabs.get(symbol) or {}" in body
    assert "strategy_items = list(latest.get('strategy_items') or [])" in body
    assert "merged['items'] = strategy_items + list(" in body


def test_remove_menu_lists_strategy_and_builtin():
    page = PAGE.read_text(encoding='utf-8')
    block = page.split('openRemoveMenu(anchor: HTMLElement): void {', 1)[1]
    block = block.split('/** 指标 key → 菜单上的一行文字', 1)[0]
    # 策略单独一行（miniqt 的「删除交易策略」✓）
    assert 'editor.' in block and 'removeStrategy' in block
    assert 'removeStrategy(cell)' in block
    # 内置 / 目录 / 个人指标都按 `source` 列出来（跳过策略线 ✓）
    assert "key.startsWith('editor:')" in block
    assert 'this.cellStrategy[cell]' in block
    assert '删除全部指标' in block
    # 前端也记策略名（`payload.strategy` ✓）
    assert "this.cellStrategy[cell] = String(" in page
    assert "'remove_strategy'" in page
