"""P72：本地模拟交易的持仓线（本地图表 + 回放）✓"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _desk(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    return desk


def _positions(desk):
    out = []
    for item in desk.sent:
        if isinstance(item, str) and '"type":"position"' in item:
            out.append(json.loads(item.split('applyPatch(', 1)[1].rstrip(');')))
    return out


def test_sim_position_payload(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    sim = desk.local_sim()
    sim.set_price('X', 100.0, 2, bar='t1')
    sim.order('X', 'buy', 3, 100.0)
    patch = desk.sim_position('X', local=True)
    assert patch['type'] == 'position' and patch['local'] is True
    assert patch['long']['side'] == '多'
    assert patch['long']['volume'] == 3.0
    assert patch['long']['avg'] == 100.0
    assert patch['long']['profit'] == 0.0
    assert 'short' not in patch

    sim.set_price('X', 110.0, 2, bar='t2')
    patch = desk.sim_position('X')
    assert patch['long']['profit'] == 30.0
    assert 'local' not in patch

    sim.order('X', 'sell', 3, 110.0, True)
    assert desk.sim_position('X') == {'type': 'position', 'symbol': 'X'}


def test_local_order_pushes_position(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.local_sim().set_price('l2609', 7965.0, 1, bar='t1')
    desk._on_local_order({'symbol': 'l2609', 'side': 'buy', 'qty': 2,
                          'price': 7965.0})
    patch = _positions(desk)[-1]
    assert patch['local'] is True
    assert patch['long']['volume'] == 2.0
    # 平仓 → 空补丁（前端删线 ✓）
    desk._on_local_order({'symbol': 'l2609', 'side': 'sell', 'qty': 2,
                          'price': 7965.0, 'close': True})
    assert _positions(desk)[-1] == {'type': 'position', 'symbol': 'l2609',
                                    'local': True}


def test_replay_order_pushes_position(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    symbol = 'SHFE.ag2612'
    desk.replay_symbols.add(symbol)
    desk._last_rows[symbol] = {'last': 13900.0}
    desk._on_replay_order({'symbol': symbol, 'side': 'sell', 'qty': 1,
                           'price': 13900.0})
    patch = _positions(desk)[-1]
    assert 'local' not in patch                    # 看盘窗口用 ✓
    assert patch['short']['side'] == '空'
    desk._on_replay_action({'symbol': symbol, 'action': 'all'})
    assert _positions(desk)[-1] == {'type': 'position', 'symbol': symbol}


def test_replay_price_updates_position_profit(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    symbol = 'SHFE.ag2612'
    desk.replay_symbols.add(symbol)
    desk._last_rows[symbol] = {'last': 13900.0}
    desk._on_replay_order({'symbol': symbol, 'side': 'buy', 'qty': 2,
                           'price': 13900.0})
    desk._on_replay_price({'symbol': symbol, 'price': 13960.0, 'time': 't9'})
    patch = _positions(desk)[-1]
    assert patch['long']['profit'] == 120.0        # 60 × 2 ✓


def test_replay_enter_and_exit_positions(tmp_path, monkeypatch):
    """进回放推持仓线，退出回放推空补丁清线 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    symbol = 'SHFE.ag2612'
    desk.local_sim().set_price(symbol, 13900.0, 1, bar='t1')
    desk.local_sim().order(symbol, 'buy', 1, 13900.0)
    desk.replay_symbols.add(symbol)
    desk._push_sim_position(symbol)
    assert _positions(desk)[-1]['long']['volume'] == 1.0

    source = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    start = source.index('    def _on_replay_exit')
    block = source[start:start + 1600]
    assert "self.push({'type': 'position', 'symbol': symbol})" in block
    assert 'self.replay_symbols.discard(symbol)' in block


def test_sim_reset_and_settings_refresh_positions(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.last_symbol = 'X'
    desk.local_sim().set_price('X', 100.0, 2, bar='t1')
    desk.local_sim().order('X', 'buy', 1, 100.0)
    before = len(_positions(desk))
    desk._on_set_setting({'key': 'sim_fee_value', 'value': 3})
    after = _positions(desk)
    assert len(after) > before
    assert after[-1]['local'] is True
    # 换初始现金 → 账户重置 → 空补丁（线消失 ✓）
    desk._on_set_setting({'key': 'sim_initial_cash', 'value': 500000})
    assert _positions(desk)[-1].get('long') is None


def test_frontend_routes_position_to_local_chart():
    app = (DESK_TS / 'app.ts').read_text(encoding='utf-8')
    block = app.split("case 'position': {", 1)[1].split("case 'account'", 1)[0]
    assert 'if (patch.local) {' in block
    assert 'item instanceof LocalChartPage' in block
    # ★ 多布局：持仓补丁带 `cell` → 画到**那一格**（以前写死第 1 格 ✗）
    assert 'page.setPosition(sides, typeof patch.cell' in block
    assert 'this.pages.get(`chart:${symbol}`)' in block


def test_local_page_supports_position_line():
    local = (DESK_TS / 'local-chart-page.ts').read_text(encoding='utf-8')
    assert 'private positionLineVisible = true;' in local
    assert 'setPosition(payload: { long?: PosSide | null; short?: PosSide | null }' in local
    assert 'desk-pos-badge' in local
    assert 'private _addPositionBadge(' in local
    # 持仓线按钮在工具栏（复用实时图表那套 ✓）
    assert 'togglePositionLine' in local
