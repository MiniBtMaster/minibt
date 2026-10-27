"""策略文件 → 自动选布局 / 选合约（本地 & 实时）✓"""
from __future__ import annotations

import json

import pandas as pd

from minibt import Strategy
from minibt.desk.strategy_plan import analyze


def _frame(symbol: str):
    return pd.DataFrame({
        'datetime': pd.Series(pd.date_range(
            '2026-01-01 09:00', periods=3, freq='min')).astype('int64'),
        'open': [1.0, 2.0, 3.0], 'high': [2.0, 3.0, 4.0],
        'low': [0.0, 1.0, 2.0], 'close': [1.5, 2.5, 3.5],
        'volume': [1.0, 1.0, 1.0], 'symbol': [symbol] * 3,
        'duration': [60] * 3, 'price_tick': [1.0] * 3,
        'volume_multiple': [10.0] * 3,
    })


def _desk(tmp_path, monkeypatch):
    from minibt.desk import local_data, user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(local_data, 'STATE_FILE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(local_data, 'FOLDERS_FILE',
                        str(tmp_path / 'folders.json'))
    monkeypatch.setenv('MINIBT_DESK_SIM_DB', str(tmp_path / 'sim.sqlite3'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    return desk


def _patches(desk):
    return [json.loads(item.split('applyPatch(', 1)[1].rstrip(');'))
            for item in desk.sent
            if isinstance(item, str) and 'applyPatch(' in item]


# ---------------------------------------------------------------- 解析
def test_analyze_get_kline_styles(tmp_path):
    local = tmp_path / 'local.py'
    local.write_text(
        'class S:\n'
        '    def __init__(self):\n'
        '        self.a = self.get_kline(LocalDatas.pp2609_60)\n'
        '        self.b = self.get_kline(LocalDatas.l2609_60)\n',
        encoding='utf-8')
    plan = analyze(str(local))
    assert plan['contracts'] == ['pp2609_60', 'l2609_60']
    assert plan['klines'] == 2

    real = tmp_path / 'real.py'
    real.write_text(
        'class S:\n'
        '    def __init__(self):\n'
        '        self.a = self.get_kline("SHFE.ag2701")\n'
        '        self.b = self.get_kline("SHFE.au2701")\n',
        encoding='utf-8')
    plan = analyze(str(real))
    assert plan['contracts'] == ['SHFE.ag2701', 'SHFE.au2701']

    klines = tmp_path / 'klines.py'
    klines.write_text(
        'class S:\n'
        '    def __init__(self):\n'
        '        self.fast = self.klines1.close.sma(5)\n'
        '        self.slow = self.klines2.close.sma(20)\n',
        encoding='utf-8')
    plan = analyze(str(klines))
    assert plan['contracts'] == []
    assert plan['klines'] == 2


def test_layout_for_count_prefers_left_right():
    from minibt.desk.app import Desk
    assert Desk._layout_for_count(1) == ('single', 1, 1)
    assert Desk._layout_for_count(2) == ('h2', 2, 1)
    assert Desk._layout_for_count(3) == ('h3', 3, 1)
    assert Desk._layout_for_count(4) == ('grid4', 2, 2)


# ---------------------------------------------------------------- 本地
def test_local_auto_layout_and_load(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk._auto_layout_local(['pp2609_60', 'l2609_60'], current='test')
    patches = _patches(desk)
    layout = [item for item in patches if item.get('type') == 'layout'][-1]
    assert layout['local'] is True
    assert layout['count'] == 2 and layout['key'] == 'h2'
    assert layout['symbols'] == ['pp2609_60', 'l2609_60']
    loaded = [item for item in patches if item.get('type') == 'local_kline']
    assert [(item['name'], item['cell']) for item in loaded] == [
        ('pp2609_60', 0), ('l2609_60', 1)]
    assert desk._local_cell_names == {0: 'pp2609_60', 1: 'l2609_60'}
    frames = desk._local_frames_for_strategy('pp2609_60', 0)
    assert [name for name, _f in frames] == ['pp2609_60', 'l2609_60']


# ---------------------------------------------------------------- 实时
def _realtime_info(desk, tab='DCE.rb2601'):
    desk.tabs = {tab: {'cycle': 60}}
    return desk.tabs[tab]


def test_realtime_auto_layout_and_load(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    info = _realtime_info(desk)
    path = tmp_path / 'test4.py'
    path.write_text(
        'class S:\n'
        '    def __init__(self):\n'
        '        self.a = self.get_kline("SHFE.ag2701")\n'
        '        self.b = self.get_kline("SHFE.au2701")\n',
        encoding='utf-8')
    monkeypatch.setattr(desk, '_strategy_frame',
                        lambda symbol, info=None, cycle=0: _frame(str(symbol)))
    monkeypatch.setattr(desk, '_validate_realtime_contracts',
                        lambda contracts: [])
    prepared = desk._prepare_realtime_strategy(
        'DCE.rb2601', info, str(path), None, 60)
    assert prepared.get('ok'), prepared
    assert [name for name, _f in prepared['frames']] == [
        'SHFE.ag2701', 'SHFE.au2701']
    assert info['layout']['symbols'] == ['SHFE.ag2701', 'SHFE.au2701']
    patches = _patches(desk)
    layout = [item for item in patches if item.get('type') == 'layout'][-1]
    assert layout['count'] == 2 and layout['key'] == 'h2'
    assert layout['symbols'] == ['SHFE.ag2701', 'SHFE.au2701']
    klines = [item for item in patches if item.get('type') == 'kline']
    assert [(item['symbol'], item['cell']) for item in klines] == [
        ('DCE.rb2601', 0), ('DCE.rb2601', 1)]


def test_realtime_invalid_contract_alerts_without_layout(tmp_path,
                                                         monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    info = _realtime_info(desk)
    path = tmp_path / 'bad.py'
    path.write_text(
        'class S:\n'
        '    def __init__(self):\n'
        '        self.a = self.get_kline("SHFE.no9999")\n',
        encoding='utf-8')
    monkeypatch.setattr(desk, '_strategy_frame',
                        lambda symbol, info=None, cycle=0: _frame(str(symbol)))
    monkeypatch.setattr(desk, '_validate_realtime_contracts',
                        lambda contracts: [{'symbol': contracts[0],
                                            'reason': '天勤报价里没有这个合约'}])
    prepared = desk._prepare_realtime_strategy(
        'DCE.rb2601', info, str(path), None, 60)
    assert not prepared.get('ok')
    assert '找不到' in str(prepared.get('error'))
    assert not [item for item in _patches(desk)
                if item.get('type') == 'layout']


def test_realtime_local_name_resolves_to_open_contract(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    info = _realtime_info(desk)
    info['layout'] = {'cols': 2, 'rows': 1,
                      'symbols': ['DCE.pp2609', 'DCE.l2609']}
    assert desk._resolve_realtime_contract('pp2609_60', info) == 'DCE.pp2609'
    assert desk._resolve_realtime_contract('l2609_60', info) == 'DCE.l2609'


def test_frontend_handles_auto_layout_patch():
    """后端 push 的 layout 补丁：本地/实时都要真的重建格子 ✓"""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    app = (root / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(
        encoding='utf-8')
    assert 'if (patch.local)' in app
    assert 'local.applyLayout' in app
    chart = (root / 'jslib' / 'src' / 'desk' / 'chart-page.ts').read_text(
        encoding='utf-8')
    assert 'this.spec = spec;' in chart
    assert 'layoutSpecForCount(count)' in chart
    local = (root / 'jslib' / 'src' / 'desk' / 'local-chart-page.ts').read_text(
        encoding='utf-8')
    block = local.split('applyLayout(payload', 1)[1].split('setCellBars', 1)[0]
    assert 'this.setLayoutSpec(spec);' in block
    backend = (root / 'minibt' / 'desk' / 'app.py').read_text(
        encoding='utf-8')
    assert "'local': True" in backend              # 本地布局补丁 ✓
    assert "_protocol.patch_kline(symbol, bars, True)" in backend


def test_local_editor_add_strategy_auto_layout_end_to_end(tmp_path, monkeypatch):
    """本地图表：加 test_2 风格策略 → 自动二布局 + 装 pp/l + 再跑策略 ✓"""
    import time

    from minibt.desk import protocol

    desk = _desk(tmp_path, monkeypatch)
    path = tmp_path / 'pair_local.py'
    path.write_text(
        'from minibt import *\n'
        'class PairLocal(Strategy):\n'
        '    def __init__(self):\n'
        '        self.a = self.get_kline(LocalDatas.pp2609_60)\n'
        '        self.b = self.get_kline(LocalDatas.l2609_60)\n'
        '        self.ma1 = self.a.close.sma(5, overlap=True)\n'
        '        self.ma2 = self.b.close.sma(5, overlap=True)\n'
        '    def next(self):\n'
        '        pass\n',
        encoding='utf-8')
    desk.handle(protocol.encode_command({
        'cmd': 'editor_add_indicator',
        'payload': {'path': str(path), 'symbol': 'test', 'cell': 0,
                    'local': True},
    }))
    deadline = time.time() + 30
    while time.time() < deadline:
        if {'pp2609_60', 'l2609_60'} <= set(desk._local_strategies):
            break
        time.sleep(0.05)
    assert {'pp2609_60', 'l2609_60'} <= set(desk._local_strategies)
    desk.flush_outbox()          # 后台策略线程的补丁 → 主线程发件箱 ✓
    assert desk._local_cell_names == {0: 'pp2609_60', 1: 'l2609_60'}
    patches = _patches(desk)
    layout = [item for item in patches if item.get('type') == 'layout'][-1]
    assert layout['local'] is True and layout['count'] == 2
    loaded = [(item['name'], item['cell']) for item in patches
              if item.get('type') == 'local_kline']
    assert ('pp2609_60', 0) in loaded and ('l2609_60', 1) in loaded
    # 两格的策略线都推了（第 2 格带 cell ✓）
    # ★ 策略线是**后台线程**算完才 push 的（先进 `_outbox`）→ 上面那一次
    #   flush 有竞态；这里等到补丁真的到齐（最多 10 秒 ✓）
    def editor_cells():
        return [item.get('cell') for item in _patches(desk)
                if item.get('type') == 'local_indicator'
                and any(str(line.get('key', '')).startswith('editor:')
                        for line in (item.get('items') or []))]

    deadline = time.time() + 10
    cells = editor_cells()
    while time.time() < deadline and not (0 in cells and 1 in cells):
        time.sleep(0.1)
        desk.flush_outbox()
        cells = editor_cells()
    assert 0 in cells and 1 in cells


def test_realtime_same_layout_keeps_indicators(tmp_path, monkeypatch):
    """布局 / 合约已经一样 → 不重建、不清指标 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    info = _realtime_info(desk)
    info['layout'] = {'cols': 2, 'rows': 1,
                      'symbols': ['SHFE.ag2701', 'SHFE.au2701'],
                      'cells': [{'symbol': 'SHFE.ag2701',
                                 'indicators': [{'key': 'MA'}]},
                                {'symbol': 'SHFE.au2701',
                                 'indicators': [{'key': 'RSI'}]}]}
    info['indicators'] = [{'key': 'MA'}]
    path = tmp_path / 'test4.py'
    path.write_text(
        'class S:\n'
        '    def __init__(self):\n'
        '        self.a = self.get_kline("SHFE.ag2701")\n'
        '        self.b = self.get_kline("SHFE.au2701")\n',
        encoding='utf-8')
    monkeypatch.setattr(desk, '_strategy_frame',
                        lambda symbol, info=None, cycle=0: _frame(str(symbol)))
    monkeypatch.setattr(desk, '_validate_realtime_contracts',
                        lambda contracts: [])
    prepared = desk._prepare_realtime_strategy(
        'DCE.rb2601', info, str(path), None, 60)
    assert prepared.get('ok'), prepared
    assert not [item for item in _patches(desk)
                if item.get('type') == 'layout']
    assert info['indicators'] == [{'key': 'MA'}]
    assert info['layout']['cells'][1]['indicators'] == [{'key': 'RSI'}]
    # 但 K 线仍会重新加载（同一布局也能刷新数据）✓
    assert [item.get('cell') for item in _patches(desk)
            if item.get('type') == 'kline'] == [0, 1]


def test_local_klines_style_requires_layout_reminder(tmp_path, monkeypatch):
    """klines1/2 本地写法：布局/合约没准备好 → 弹窗提醒，不运行策略 ✓"""
    from minibt.desk import protocol

    desk = _desk(tmp_path, monkeypatch)
    path = tmp_path / 'klines_local.py'
    path.write_text(
        'from minibt import *\n'
        'class KPair(Strategy):\n'
        '    def __init__(self):\n'
        '        self.fast = self.klines1.close.sma(5, overlap=True)\n'
        '        self.slow = self.klines2.close.sma(5, overlap=True)\n'
        '    def next(self):\n'
        '        pass\n',
        encoding='utf-8')
    desk.handle(protocol.encode_command({
        'cmd': 'editor_add_indicator',
        'payload': {'path': str(path), 'symbol': 'test', 'cell': 0,
                    'local': True},
    }))
    assert not desk._local_strategies
    alerts = [item for item in _patches(desk)
              if item.get('type') == 'alert']
    assert alerts and 'K线数量不够' in str(alerts[-1].get('title'))


def test_local_sim_uses_contract_multiplier():
    """本地模拟账户：期货盈亏 = 价差 × 手数 × 合约乘数 ✓"""
    from minibt.desk.local_data import LocalSim

    sim = LocalSim(200000.0, 'fixed', 0.0)
    sim.set_contract('pp2609_60', 5.0, 0)
    sim.set_price('pp2609_60', 8000.0, 0)
    sim.order('pp2609_60', 'buy', 2, 8000.0)
    sim.set_price('pp2609_60', 8010.0, 0)
    # 浮盈 = 10 × 2 × 5 = 100
    row = sim.payload('pp2609_60')['tables']['positions']['rows'][0]
    assert row[5] == '100.00'
    result = sim.order('pp2609_60', 'sell', 2, 8010.0, True)
    assert result['realized'] == 100.0
    assert sim.realized == 100.0
    assert sim.multiplier('pp2609_60') == 5.0


def test_percent_fee_includes_multiplier():
    from minibt.desk.local_data import LocalSim

    sim = LocalSim(200000.0, 'percent', 0.5)
    sim.set_contract('X', 5.0)
    # 成交额 = 1000 × 2 × 5 = 10000；0.5% = 50
    assert sim.fee_of(2, 1000.0, 'X') == 50.0


def test_kline_keeps_csv_volume_multiple_and_tick(tmp_path):
    """策略 KLine 不能把 CSV 的合约乘数/最小变动丢掉（以前全变 1/0.01 ✗）"""
    from minibt.desk.strategy_runner import StrategyRunner

    class S(Strategy):
        def __init__(self):
            self.data = self.get_kline('LEFT')

        def next(self):
            pass

    runner = StrategyRunner(S, symbol='LEFT', cycle=60)
    runner.prepare([('LEFT', _frame('DCE.pp2609'))], seed_kline=True)
    assert runner.strategy.data.symbol == 'DCE.pp2609'
    assert runner.strategy.data.volume_multiple == 10.0
    assert runner.strategy.data.price_tick == 1.0


def test_local_load_registers_multiplier(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk._on_local_load({'name': 'pp2609_60', 'cell': 0})
    assert desk.local_sim().multiplier('pp2609_60') == 5.0


def test_prepare_replay_uses_minibt_specs(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    sim = desk.local_sim()

    class FakeRunner:
        def account_spec(self):
            return {
                'initial_cash': 1_000_000.0,
                'contracts': {
                    'pp2609_60': {
                        'price_tick': 1.0, 'volume_multiple': 5.0,
                        'margin_rate': 0.05, 'slip_point': 0.0,
                        'commission': {'fixed_commission': 1.0},
                    },
                    'l2609_60': {
                        'price_tick': 1.0, 'volume_multiple': 5.0,
                        'margin_rate': 0.08, 'slip_point': 1.0,
                        'commission': {'fixed_commission': 2.0},
                    },
                },
            }

    sim.restore_desk = lambda: None
    desk._prepare_replay_account(FakeRunner())
    assert sim.initial_cash == 1_000_000.0
    assert sim.multiplier('pp2609_60') == 5.0
    assert sim.margin_rate('pp2609_60') == 0.05
    assert sim.margin_rate('l2609_60') == 0.08
    assert sim.fee_rules['pp2609_60'] == {'mode': 'fixed', 'value': 1.0}
    assert sim.fee_rules['l2609_60'] == {'mode': 'fixed', 'value': 2.0}
    assert sim.slip_of('l2609_60') == 1.0
    assert sim.decimals['pp2609_60'] == 0


def test_local_sim_margin_fee_and_slip():
    from minibt.desk.local_data import LocalSim

    sim = LocalSim(1_000_000.0, 'fixed', 0.0)
    sim.prepare_replay(1_000_000.0, {
        'X': {'price_tick': 1.0, 'volume_multiple': 5.0,
              'margin_rate': 0.05, 'slip_point': 1.0,
              'commission': {'fixed_commission': 2.0}},
    })
    sim.set_price('X', 100.0, 0)
    result = sim.order('X', 'buy', 1, 100.0, auto=True)
    # 买单滑点 +1 → 101；固定手续费 2
    assert result['order']['price'] == 101.0
    assert result['fee'] == 2.0
    values = sim.payload('X')['values']
    # 保证金 = 101 × 1 × 5 × 5% = 25.25
    assert values['margin'] == 25.25
    assert values['available'] == 1_000_000.0 - 2.0 - 25.25
    # 平仓：卖价 110 - 滑点 1 = 109；盈亏 (109-101) × 1 × 5 = 40
    sim.set_price('X', 110.0, 0)
    result = sim.order('X', 'sell', 1, 110.0, close=True, auto=True)
    assert result['order']['price'] == 109.0
    assert result['realized'] == 40.0
    values = sim.payload('X')['values']
    assert values['margin'] == 0.0
    assert values['realized_pnl'] == 40.0
    assert values['commission'] == 4.0
    assert values['balance'] == 1_000_036.0


def test_replay_reset_applies_minibt_account(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)

    class Runner:
        def account_spec(self):
            return {'initial_cash': 500000.0, 'contracts': {
                'A': {'price_tick': 1.0, 'volume_multiple': 5.0,
                      'margin_rate': 0.08, 'slip_point': 0.0,
                      'commission': {'fixed_commission': 3.0}},
            }}

    desk._local_runners = {'S': {'runner': Runner(), 'orders': 0,
                                 'targets': 0, 'frames': [], 'name': 'A'}}
    desk._local_cell_names = {0: 'A'}
    desk._on_replay_price({
        'symbol': 'A', 'price': 100.0, 'time': 1, 'index': 0,
        'cells': [{'symbol': 'A', 'price': 100.0, 'time': 1, 'index': 0}],
        'advance': False, 'reset': True,
    })
    sim = desk.local_sim()
    assert sim.initial_cash == 500000.0
    assert sim.margin_rate('A') == 0.08
    assert sim.multiplier('A') == 5.0
    assert sim.fee_rules['A'] == {'mode': 'fixed', 'value': 3.0}


def test_account_spec_reads_per_contract_fee_and_contract_fields():
    from minibt.desk.strategy_runner import StrategyRunner

    class Pair(Strategy):
        def __init__(self):
            self.a = self.get_kline('LEFT')
            self.b = self.get_kline('RIGHT')
            self.a.fixed_commission = 2.0
            self.b.fixed_commission = 3.0

        def next(self):
            pass

    runner = StrategyRunner(Pair, symbol='LEFT', cycle=60)
    runner.prepare([('LEFT', _frame('LEFT')),
                    ('RIGHT', _frame('RIGHT'))],
                   seed_kline=True)
    spec = runner.account_spec()
    assert spec['initial_cash'] == 1_000_000.0
    left = spec['contracts']['LEFT']
    right = spec['contracts']['RIGHT']
    assert left['volume_multiple'] == 10.0
    assert left['price_tick'] == 1.0
    assert left['margin_rate'] == 0.05
    assert left['commission'] == {'fixed_commission': 2.0}
    assert right['commission'] == {'fixed_commission': 3.0}
