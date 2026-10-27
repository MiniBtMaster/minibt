"""P3 测试：底部「交易账户」面板（11 卡 + 4 表 + 多账户 + 日志）。"""

import json

import pytest

from minibt.desk import protocol
from minibt.desk.accounts import ACCOUNT_FIELDS, AccountView


class _Acc:
    pre_balance = 100.0
    balance = 101.0
    position_profit = 2.0
    close_profit = 1.0
    float_profit = 3.0
    commission = 0.5
    margin = 10.0
    frozen_margin = 0.0
    frozen_commission = 0.0
    available = 90.0
    risk_ratio = 0.099
    market_value = 55.0


class _Real:
    broker_id = 'H宏源期货'
    account_id = '123456'


class _Sim:
    broker_id = ''
    account_id = ''


class _Api:
    def __init__(self, accounts=None):
        if accounts:
            self._account = type('Multi', (), {
                '_account_list': list(accounts)})()
        else:
            # 单账户：tqsdk 里就是 TqKq / TqAccount 本身 ✓
            self._account = type('TqKq', (), {})()

    def get_account(self, account=None):
        return _Acc()

    def get_position_list(self):
        return [{'instrument_id': 'SHFE.rb2610', 'pos_long': 2, 'pos_short': 1,
                 'open_price_long': 3595.0, 'open_price_short': 3610.0,
                 'float_profit_long': 100.0, 'float_profit_short': -50.0,
                 'volume_long_today': 2, 'volume_short_today': 1,
                 'margin': 7000.0}]

    def get_position(self, **kwargs):
        return {}

    def get_order(self, **kwargs):
        return {
            'o1': {'instrument_id': 'SHFE.rb2610', 'direction': 'BUY',
                   'offset': 'OPEN', 'volume_orign': 2, 'volume_left': 1,
                   'limit_price': 3600.0, 'status': 'ALIVE',
                   'insert_date_time': '2026-10-18 09:30:00'},
            'o2': {'instrument_id': 'SHFE.rb2610', 'direction': 'SELL',
                   'offset': 'CLOSE', 'volume_orign': 1, 'volume_left': 0,
                   'limit_price': 3610.0, 'status': 'FINISHED',
                   'insert_date_time': '2026-10-18 09:31:00'},
        }

    def get_trade(self, **kwargs):
        return {'t1': {'instrument_id': 'SHFE.rb2610', 'direction': 'BUY',
                       'offset': 'OPEN', 'price': 3600.0, 'volume': 1,
                       'commission': 1.0,
                       'trade_date_time': '2026-10-18 09:31:00'}}


class _Feed:
    kind = 'futures'

    def __init__(self, accounts=None):
        self.api = _Api(accounts)

    def available(self):
        return True

    def contracts(self, ins_class, exchange):
        return ['SHFE.rb2610']

    def fill_names(self, symbols):
        return None

    def name_of(self, symbol):
        return '螺纹'

    def quotes(self, keys):
        return []

    def spec(self, symbol):
        return None

    def klines(self, *args, **kwargs):
        return None


def _desk(tmp_path, accounts=None):
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = _Feed(accounts)
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    return desk


def _payload(script):
    return json.loads(script[len('window.__desk.applyPatch('):-2])


def test_account_labels_and_switch(tmp_path):
    desk = _desk(tmp_path, accounts=[_Sim(), _Real()])
    view = desk.account_view()
    assert view.labels() == ['快期模拟', 'H宏源期货/123456']
    assert view.index == 0
    view.switch(1)
    assert view.index == 1
    view.switch(99)                       # 越界 → 夹住 ✓
    assert view.index == 1
    assert view.account_kwargs()          # 多账户 → 带 account= ✓

    single = _desk(tmp_path, accounts=[])
    single_view = AccountView(single)
    assert single_view.labels() == ['快期模拟']
    assert single_view.account_kwargs() == {}


def test_account_summary_fields_and_percent(tmp_path):
    desk = _desk(tmp_path, accounts=[_Sim(), _Real()])
    payload = desk.account_payload()
    assert payload['type'] == 'account' and payload['kind'] == 'futures'
    assert [field['key'] for field in payload['fields']] == [
        key for key, _title, _pct in ACCOUNT_FIELDS]
    percent = [field for field in payload['fields'] if field['percent']]
    assert [field['key'] for field in percent] == ['risk_ratio']
    assert payload['values']['balance'] == 101.0
    assert payload['values']['risk_ratio'] == 0.099
    assert payload['index'] == 0
    assert payload['labels'] == ['快期模拟', 'H宏源期货/123456']


def test_account_tables_positions_orders_trades(tmp_path):
    desk = _desk(tmp_path)
    tables = desk.account_payload()['tables']
    positions = tables['positions']
    assert positions['columns'][0] == '合约'
    assert len(positions['rows']) == 2                    # 多 + 空 两行 ✓
    long_row = positions['rows'][0]
    assert long_row[0] == 'SHFE.rb2610' and long_row[1] == '买'
    # 价格列按合约小数位（`price_tick` 未知 → 默认 2 位 ✓）
    assert long_row[2] == '2' and long_row[4] == '3,595.00'
    assert long_row[6] == '100.00'                        # 浮动盈亏 ✓

    orders = tables['orders']
    assert orders['total'] == 2                            # 全部委托
    assert tables['unfilled']['total'] == 1                # 只有 ALIVE ✓
    assert tables['unfilled']['rows'][0][6] == '有效'

    trades = tables['trades']
    assert trades['rows'][0][0] == 'SHFE.rb2610'
    assert trades['rows'][0][3] == '3,600.00'
    assert trades['rows'][0][6] == '09:31:00'


def test_refresh_docks_throttles_and_requires_tab(tmp_path):
    desk = _desk(tmp_path)
    desk.sent.clear()
    desk._refresh_docks()                                  # 没有 tab → 不推 ✓
    assert desk.sent == []

    desk.tabs['SHFE.rb2610'] = {'feed': desk.futures, 'cycle': 60}
    desk._dock_at = 0.0
    desk._refresh_docks()
    # ★ P77 起每拍还会推挂单线（`orders`）✓
    assert [_payload(script)['type'] for script in desk.sent][:1] == ['account']

    desk.sent.clear()
    desk._refresh_docks()                                  # 1 秒内 → 跳过 ✓
    assert desk.sent == []


def test_account_and_switch_commands(tmp_path):
    desk = _desk(tmp_path, accounts=[_Sim(), _Real()])
    desk.tabs['SHFE.rb2610'] = {'feed': desk.futures, 'cycle': 60}

    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'account'}))
    assert [_payload(script)['type'] for script in desk.sent] == ['account']

    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'switch_account', 'payload': {'index': 1}}))
    kinds = [_payload(script)['type'] for script in desk.sent]
    assert kinds == ['log', 'account']
    assert desk.account_view().index == 1
    assert 'H宏源期货' in _payload(desk.sent[0])['text']


def test_push_log_patch(tmp_path):
    desk = _desk(tmp_path)
    desk.sent.clear()
    desk.push_log('测试', 'warning')
    patch = _payload(desk.sent[-1])
    assert patch['type'] == 'log' and patch['level'] == 'warning'
    assert patch['text'] == '测试' and len(patch['ts']) == 8


def test_p3_assets_built():
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[1]
    script = (repo / 'pylightcharts' / 'js' / 'desk.js').read_text(
        encoding='utf-8', errors='ignore')
    css = (repo / 'pylightcharts' / 'js' / 'desk.css').read_text(encoding='utf-8')
    for key in ('desk-dock', 'desk-dock-cards', 'desk-dock-log'):
        assert key in css, key
    for key in ('desk-dock', 'switch_account', 'account_action'):
        assert key in script, key
    assert (repo / 'jslib' / 'src' / 'desk' / 'account-dock.ts').is_file()
    app = (repo / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    for case in ("'account'", "'log'"):
        assert f'case {case}' in app, case
