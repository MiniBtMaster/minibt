"""P70：模拟账户（现价 / 手续费 / 设置页分析）✓"""
import json
import pathlib

from minibt.desk import protocol
from minibt.desk.local_data import LocalSim

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _ts(name):
    return (DESK_TS / name).read_text(encoding='utf-8')


# ------------------------------------------------- ① 开仓：现价 = 开仓价
def test_open_keeps_open_price_and_zero_profit():
    sim = LocalSim(100000.0, 'fixed', 0.0)
    sim.set_price('X', 100.0, 2, bar='t1')
    sim.order('X', 'buy', 2, 100.0)
    rows = sim.payload('X')['tables']['positions']['rows']
    assert rows == [['X', '多', '2', '100.00', '100.00', '0.00']]
    assert sim.payload('X')['values']['float_profit'] == 0.0


def test_same_bar_does_not_overwrite_open_price():
    sim = LocalSim(100000.0, 'fixed', 0.0)
    sim.set_price('X', 100.0, 2, bar='t1')
    sim.order('X', 'sell', 1, 100.0)          # 空 1 手
    sim.set_price('X', 130.0, 2, bar='t1')    # 同一根 → 不动 ✓
    rows = sim.payload('X')['tables']['positions']['rows']
    assert rows[0][4] == '100.00'             # 现价还是开仓价
    assert rows[0][5] == '0.00'               # 浮盈 0
    sim.set_price('X', 130.0, 2, bar='t2')    # 下一根 → 更新 ✓
    rows = sim.payload('X')['tables']['positions']['rows']
    assert rows[0][4] == '130.00'
    assert rows[0][5].startswith('-30.00')    # 空单亏 30
    assert sim.payload('X')['values']['float_profit'] == -30.0


# ------------------------------------------------- ② 手续费
def test_fixed_fee_per_lot():
    sim = LocalSim(100000.0, 'fixed', 5.0)
    sim.set_price('X', 100.0, 2)
    result = sim.order('X', 'buy', 3, 100.0)
    assert result['fee'] == 15.0              # 5 元 × 3 手 ✓
    assert sim.commission == 15.0
    payload = sim.payload('X')
    assert payload['values']['commission'] == 15.0
    assert payload['values']['available'] == 100000.0 - 300.0 - 15.0


def test_percent_fee_of_turnover():
    sim = LocalSim(100000.0, 'percent', 0.5)   # 成交额 0.5%
    sim.set_price('X', 1000.0, 2)
    result = sim.order('X', 'buy', 2, 1000.0)
    assert result['fee'] == 10.0              # 2000 × 0.5% ✓
    sim.configure(fee_mode='fixed', fee_value=3)
    assert sim.fee_of(2, 1000.0) == 6.0
    sim.configure(fee_value=0)
    assert sim.fee_of(2, 1000.0) == 0.0


def test_configure_initial_cash_resets_account():
    sim = LocalSim(100000.0, 'fixed', 1.0)
    sim.set_price('X', 100.0, 2, bar='t1')
    sim.order('X', 'buy', 1, 100.0)
    sim.configure(initial_cash=50000.0)
    assert sim.initial_cash == 50000.0
    assert sim.payload('X')['values']['available'] == 50000.0
    assert sim.positions == {}                # 换钱 → 重置 ✓
    assert sim.settings() == {'initial_cash': 50000.0, 'fee_mode': 'fixed',
                              'fee_value': 1.0}


# ------------------------------------------------- ④ 分析数据（曲线 / 统计）
def test_analysis_payload(monkeypatch):
    from minibt.desk import local_data

    tick = [0]

    def fake_strftime(fmt):
        tick[0] += 1
        return f'00:00:{tick[0] % 60:02d}'

    monkeypatch.setattr(local_data.time, 'strftime', fake_strftime)
    sim = LocalSim(100000.0, 'fixed', 2.0)
    sim.set_price('X', 100.0, 2, bar='t1')
    sim.order('X', 'buy', 2, 100.0)
    sim.set_price('X', 120.0, 2, bar='t2')
    sim.order('X', 'sell', 2, 120.0, True)     # 赚 40
    sim.set_price('Y', 50.0, 2, bar='t2')
    sim.order('Y', 'sell', 1, 50.0)
    sim.set_price('Y', 70.0, 2, bar='t3')
    sim.order('Y', 'buy', 1, 70.0, True)       # 亏 20
    payload = sim.analysis()
    assert payload['type'] == 'sim_analysis'
    assert payload['settings']['fee_mode'] == 'fixed'
    assert len(payload['equity']) >= 3
    names = [item['name'] for item in payload['series']]
    assert names[:2] == ['X', 'Y']
    # 累计（不是每笔）：X 累计 40，Y 累计 -20 ✓
    assert payload['series'][0]['points'][-1][1] == 40.0
    assert payload['series'][1]['points'][-1][1] == -20.0
    table = payload['table']
    assert table['columns'][:4] == ['品种', '交易次数', '平仓次数', '胜率']
    rows = {row[0]: row for row in table['rows']}
    assert rows['X'][3] == '100.0%'
    assert rows['X'][4] == '40.00'
    assert rows['X'][5] == '8.00'            # 2 笔 × 2 手 × 2 元 = 8 元 ✓
    summary = payload['summary']
    assert summary['trades'] == 4 and summary['closes'] == 2
    assert summary['wins'] == 1


# ------------------------------------------------- 后端接线
def _desk(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    return desk


def _patches(desk):
    out = []
    for item in desk.sent:
        if isinstance(item, str) and 'applyPatch(' in item:
            out.append(json.loads(item.split('applyPatch(', 1)[1].rstrip(');')))
    return out


def test_sim_settings_commands(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk._on_set_setting({'key': 'sim_initial_cash', 'value': 200000})
    desk._on_set_setting({'key': 'sim_fee_mode', 'value': 'percent'})
    desk._on_set_setting({'key': 'sim_fee_value', 'value': 0.3})
    sim = desk.local_sim()
    assert sim.settings() == {'initial_cash': 200000.0,
                             'fee_mode': 'percent', 'fee_value': 0.3}
    types = [patch.get('type') for patch in _patches(desk)]
    assert 'sim_analysis' in types
    assert 'local_account' in types

    desk.handle(protocol.encode_command({'cmd': 'sim_analysis',
                                         'payload': {}}))
    payload = [patch for patch in _patches(desk)
               if patch.get('type') == 'sim_analysis'][-1]
    assert payload['settings']['fee_mode'] == 'percent'

    sim.set_price('X', 100.0, 2, bar='t1')
    sim.order('X', 'buy', 1, 100.0)
    desk.handle(protocol.encode_command({'cmd': 'sim_reset', 'payload': {}}))
    payload = [patch for patch in _patches(desk)
               if patch.get('type') == 'sim_analysis'][-1]
    assert payload['summary']['trades'] == 0
    assert payload['summary']['initial_cash'] == 200000.0


def test_replay_sim_keeps_open_price(tmp_path, monkeypatch):
    """回放下单后「现价」不能被 `_last_rows` 冲掉 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    symbol = 'SHFE.ag2612'
    desk.replay_symbols.add(symbol)
    desk._last_rows[symbol] = {'last': 13974.0}
    desk._on_replay_price({'symbol': symbol, 'price': 13900.0, 'time': 't1'})
    desk._on_replay_order({'symbol': symbol, 'side': 'buy', 'qty': 1,
                           'price': 13900.0})
    rows = [patch for patch in _patches(desk)
            if patch.get('type') == 'account'][-1]['tables']['positions']['rows']
    assert rows[0][3] == '13,900.00' and rows[0][4] == '13,900.00'
    assert rows[0][5] == '0.00'

    # 下一根 K 线 → 现价 / 浮盈跟着走
    desk._on_replay_price({'symbol': symbol, 'price': 13960.0, 'time': 't2'})
    rows = [patch for patch in _patches(desk)
            if patch.get('type') == 'account'][-1]['tables']['positions']['rows']
    assert rows[0][4] == '13,960.00'
    assert rows[0][5] == '60.00'


def test_local_chart_replay_price_routed_to_local_account(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    symbol = 'local_demo'                      # 不是看盘窗口回放 ✓
    desk._on_replay_price({'symbol': symbol, 'price': 100.0, 'time': 't1'})
    desk._on_local_order({'symbol': symbol, 'side': 'buy', 'qty': 1,
                          'price': 100.0})
    desk._on_replay_price({'symbol': symbol, 'price': 110.0, 'time': 't2'})
    patches = _patches(desk)
    assert 'local_account' in [patch.get('type') for patch in patches]
    last = [patch for patch in patches
            if patch.get('type') == 'local_account'][-1]
    assert last['tables']['positions']['rows'][0][4] == '110.00'


# ------------------------------------------------- 前端接线
def test_settings_page_has_sim_section():
    page = _ts('settings-page.ts')
    assert "{ key: 'sim', label: '模拟账户' }" in page
    assert 'private _renderSim(): void' in page
    # 三项设置 ✓
    assert "'sim_initial_cash'" in page
    assert "'sim_fee_mode'" in page
    assert "'sim_fee_value'" in page
    assert '固定手续费用（每手）' in page
    assert '百分比手续费用（成交额 %）' in page
    # 分析区：权益曲线 / 各品种累计盈亏 / 统计表 ✓
    assert '账户权益曲线' in page
    assert '各品种累计盈亏' in page
    assert '各品种统计' in page
    assert 'renderMiniChart' in page
    # 死循环保护
    assert 'private quiet = false;' in page


def test_mini_chart_module():
    chart = _ts('mini-chart.ts')
    assert 'export function renderMiniChart' in chart
    assert "'polyline'" in chart
    assert 'zeroLine' in chart
    assert 'desk-mini-chart-legend' in chart


def test_replay_price_sends_bar_time():
    page = _ts('chart-page.ts')
    assert 'time: tailBar.time,' in page
    local = _ts('local-chart-page.ts')
    assert "this.options.onCommand?.('replay_price', {" in local
    assert 'time: last.time,' in local


def test_backend_registers_sim_commands():
    app = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'sim_analysis': self._on_sim_analysis" in app
    assert "'sim_reset': self._on_sim_reset" in app
    assert 'def _sim_settings' in app
    assert 'bar=payload.get(\'time\')' in app
    prefs = (ROOT / 'minibt' / 'desk' / 'user_prefs.py').read_text(
        encoding='utf-8')
    for key in ('sim_initial_cash', 'sim_fee_mode', 'sim_fee_value'):
        assert f"'{key}'" in prefs
    routes = (DESK_TS / 'app.ts').read_text(encoding='utf-8')
    assert "case 'sim_analysis':" in routes
