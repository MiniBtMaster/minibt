"""P4 测试：交易执行（下单 / 平反全 / 撤单 / 实盘识别 / 开关）。"""

import json

from minibt.desk import protocol
from minibt.desk.trading import Trading


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


class _Real:
    broker_id = 'H宏源期货'
    account_id = '123456'


class _Sim:
    broker_id = ''
    account_id = ''


class _Api:
    def __init__(self, accounts=None):
        self.orders = []
        self.cancelled = []
        self.targets = []
        self._account = type('Multi', (), {
            '_account_list': list(accounts or [_Sim()])})()

    def get_account(self, account=None):
        return _Acc()

    def insert_order(self, *args, **kwargs):
        self.orders.append(kwargs or args)

    def cancel_order(self, order_id, **kwargs):
        self.cancelled.append(order_id)

    def get_order(self, **kwargs):
        return {
            'alive': {'order_id': 'O1', 'instrument_id': 'SHFE.rb2610',
                      'status': 'ALIVE', 'direction': 'BUY', 'offset': 'OPEN',
                      'volume_orign': 1, 'volume_left': 1},
            'done': {'order_id': 'O2', 'instrument_id': 'SHFE.rb2610',
                     'status': 'FINISHED'},
        }

    def get_position(self, symbol=None, **kwargs):
        return type('P', (), {'pos_long': 2, 'pos_short': 0})()

    def get_position_list(self):
        return [{'instrument_id': 'SHFE.rb2610', 'pos_long': 2,
                 'pos_short': 0}]

    def target_pos_task(self, symbol):
        api = self

        class _Task:
            def set_target_volume(self, value):
                api.targets.append((symbol, value))

        return _Task()


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


def _desk(tmp_path, accounts=None, allow_trading=True):
    from minibt.desk.app import Desk

    desk = Desk(offline=True, allow_trading=allow_trading)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = _Feed(accounts)
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    desk.tabs['SHFE.rb2610'] = {'feed': desk.futures, 'cycle': 60}
    return desk


def _payload(script):
    return json.loads(script[len('window.__desk.applyPatch('):-2])


def test_trading_state_and_gate(tmp_path):
    desk = _desk(tmp_path)
    state = desk.trading_state()
    assert state['type'] == 'trading' and state['enabled'] is True
    # P33 起账户名带来源前缀（天勤模拟·快期模拟 / 股票本地模拟 ✓）
    assert state['real'] is False and state['account'].endswith('快期模拟')
    assert state['kind'] == 'futures'

    off = _desk(tmp_path, allow_trading=False)
    assert off.trading_state()['enabled'] is False
    assert '未启用' in off.trading_view().place('SHFE.rb2610', 'buy', 1)


def test_place_order_passes_account_and_logs(tmp_path):
    desk = _desk(tmp_path, accounts=[_Sim(), _Real()])
    text = desk.trading_view().place('SHFE.rb2610', 'buy', 2, 3600.0)
    order = desk.futures.api.orders[-1]
    assert order['symbol'] == 'SHFE.rb2610'
    assert order['direction'] == 'BUY' and order['offset'] == 'OPEN'
    assert order['volume'] == 2 and order['limit_price'] == 3600.0
    assert order['account'] is not None          # 多账户必带 account ✓
    assert '手 @' in text and '快期模拟' in text

    # 市价（price=None）也要能下 ✓
    desk.trading_view().place('SHFE.rb2610', 'sell', 1, None)
    assert desk.futures.api.orders[-1]['limit_price'] is None


def test_close_order_picks_direction_from_position(tmp_path):
    desk = _desk(tmp_path)
    desk.trading_view().place('SHFE.rb2610', 'close', 1, 3600.0)
    order = desk.futures.api.orders[-1]
    assert order['offset'] == 'CLOSE' and order['direction'] == 'SELL'


def test_actions_close_reverse_all_cancel(tmp_path):
    desk = _desk(tmp_path)
    trader = desk.trading_view()
    api = desk.futures.api

    trader.action('close', 'SHFE.rb2610')
    assert api.targets[-1] == ('SHFE.rb2610', 0)
    trader.action('reverse', 'SHFE.rb2610')
    assert api.targets[-1] == ('SHFE.rb2610', -2)
    trader.action('all')                          # 全部平 → 逐合约 target 0 ✓
    assert api.targets[-1] == ('SHFE.rb2610', 0)

    assert '撤' in trader.action('cancel_all', 'SHFE.rb2610')
    assert api.cancelled == ['O1']

    trader.action('cancel', 'NOTHING')            # 没有匹配的委托 → 提示 ✓
    assert '没有可撤' in trader.action('cancel', 'NOTHING')


def test_commands_place_and_account_action(tmp_path):
    desk = _desk(tmp_path)
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'place_order',
        'payload': {'symbol': 'SHFE.rb2610', 'side': 'buy',
                    'volume': 1, 'price': 3600},
    }))
    kinds = [_payload(script)['type'] for script in desk.sent]
    assert 'toast' in kinds and 'log' in kinds and 'account' in kinds

    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'account_action',
        'payload': {'action': 'close', 'symbol': 'SHFE.rb2610'},
    }))
    kinds = [_payload(script)['type'] for script in desk.sent]
    assert 'toast' in kinds and 'account' in kinds
    assert desk.futures.api.targets[-1] == ('SHFE.rb2610', 0)


def test_real_account_needs_confirmation_flag(tmp_path):
    desk = _desk(tmp_path, accounts=[_Sim(), _Real()])
    desk.account_view().switch(1)
    state = desk.trading_state()
    assert state['real'] is True
    assert 'H宏源期货' in state['account']


def test_book_trading_flag_follows_gate(tmp_path):
    desk = _desk(tmp_path)
    book = desk.book_payload('SHFE.rb2610')
    assert book['trading'] is True               # 有 api → 可以下单 ✓

    off = _desk(tmp_path, allow_trading=False)
    assert off.book_payload('SHFE.rb2610')['trading'] is False


def test_p4_assets_built():
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[1]
    script = (repo / 'pylightcharts' / 'js' / 'desk.js').read_text(
        encoding='utf-8', errors='ignore')
    for key in ('place_order', 'account_action', 'trading_state'):
        assert key in script, key
    panel = (repo / 'jslib' / 'src' / 'desk' / 'quote-panel.ts').read_text(
        encoding='utf-8')
    assert 'setTrading' in panel and 'OrderRequest' in panel
    # P79：二级报价不再下单 → 实盘二次确认在**交易面板**里 ✓
    assert 'confirm(' in (repo / 'jslib' / 'src' / 'desk'
                        / 'chart-page.ts').read_text(encoding='utf-8')
    trading = (repo / 'minibt' / 'desk' / 'trading.py').read_text(
        encoding='utf-8')
    for key in ('def place', 'def action', 'cancel_all', 'is_real'):
        assert key in trading, key
