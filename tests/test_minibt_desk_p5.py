"""P5 测试：股票全链路（清单 / 快照 / 代码统一 / 模拟盘交易 / 大批量）。"""

import json

import numpy as np
import pytest

from minibt.desk import protocol, stocks

pd = pytest.importorskip('pandas')


# ------------------------------------------------------------ 代码统一
def test_display_symbol_keeps_futures_case():
    assert stocks.display_symbol('SH.600000') == 'SSE.600000'
    assert stocks.display_symbol('SZ.000001') == 'SZSE.000001'
    assert stocks.display_symbol('SHFE.rb2610') == 'SHFE.rb2610'
    assert stocks.display_symbol('HK.00700') == 'HK.00700'
    assert stocks.display_symbol('US.AAPL') == 'US.AAPL'
    assert stocks.display_symbol('') == ''


# ------------------------------------------------ 富途清单 / 快照（假 ctx）
class _FakeCtx:
    def __init__(self, frame=None, snapshot=None):
        self.frame = frame
        self.snapshot = snapshot

    def get_stock_basicinfo(self, market, security_type):
        return 0, self.frame

    def get_market_snapshot(self, codes):
        return 0, self.snapshot


class _FakeApi:
    _RET_OK = 0

    def __init__(self, frame=None, snapshot=None):
        self._ctx = _FakeCtx(frame, snapshot)
        self._ctx.get_market_snapshot = lambda codes: (
            0, pd.DataFrame([]) if snapshot is None else snapshot)
        self.targets = []
        self.cancelled = None


def test_basic_rows_filters_delisted_and_normalizes_symbols():
    frame = pd.DataFrame([
        {'code': 'SH.600000', 'name': '浦发银行', 'stock_type': 'STOCK',
         'exchange_type': 'SH'},
        {'code': 'SH.600001', 'name': '退市股',
         'stock_type': 'STOCK_DELISTING', 'exchange_type': 'SH'},
        {'code': 'SZ.000001', 'name': '平安银行', 'stock_type': 'STOCK',
         'exchange_type': 'SZ'},
    ])
    rows = stocks.basic_rows(_FakeApi(frame), 'SSE')
    assert [row['symbol'] for row in rows] == ['SSE.600000']
    assert rows[0]['name'] == '浦发银行'

    # 深市只留 SZSE（futu 的 SH./SZ. 已经按 market 过滤）✓
    rows_sz = stocks.basic_rows(_FakeApi(frame), 'SZSE')
    assert [row['symbol'] for row in rows_sz] == ['SZSE.000001']


def test_basic_rows_us_keeps_only_main_exchanges():
    frame = pd.DataFrame([
        {'code': 'US.AAPL', 'name': 'Apple', 'stock_type': 'STOCK',
         'exchange_type': 'US_NASDAQ'},
        {'code': 'US.OTCM', 'name': 'OTC', 'stock_type': 'STOCK',
         'exchange_type': 'US_PINK'},
        {'code': 'US.IBM', 'name': 'IBM', 'stock_type': 'STOCK',
         'exchange_type': 'US_NYSE'},
    ])
    rows = stocks.basic_rows(_FakeApi(frame), 'US')
    assert [row['symbol'] for row in rows] == ['US.AAPL', 'US.IBM']


def test_snapshot_quote_matches_tq_shape():
    frame = pd.DataFrame([{
        'code': 'SH.600000', 'name': '浦发银行', 'last_price': 10.5,
        'prev_close_price': 10.0, 'bid_price': 10.49, 'ask_price': 10.51,
        'bid_vol': 100, 'ask_vol': 200, 'volume': 123456,
        'open_price': 10.1, 'high_price': 10.6, 'low_price': 9.9,
        'price_spread': 0.01, 'update_time': '2026-10-18 09:31:00',
    }])
    items = stocks.quotes(_FakeApi(snapshot=frame), ['SSE.600000'])
    assert len(items) == 1
    quote = items[0]
    assert quote.last_price == 10.5
    assert quote.pre_settlement == 10.0          # 股票：昨结 = 昨收 ✓
    assert quote.bid_price1 == 10.49 and quote.ask_price1 == 10.51
    assert quote.price_tick == 0.01
    assert quote.datetime == '09:31:00'


def test_snapshot_missing_symbol_is_none():
    empty = pd.DataFrame([])
    items = stocks.quotes(_FakeApi(snapshot=empty), ['SSE.600000', 'HK.00700'])
    assert items == [None, None]


# ---------------------------------------------------- StockFeed（清单/报价）
class _StockApi(_FakeApi):
    def get_account(self, account=None, *args, **kwargs):
        return type('Acc', (), {
            'pre_balance': 10000.0, 'balance': 10500.0,
            'position_profit': 500.0, 'close_profit': 0.0,
            'float_profit': 500.0, 'commission': 5.0, 'margin': 0.0,
            'frozen_margin': 0.0, 'frozen_commission': 0.0,
            'available': 9995.0, 'risk_ratio': 0.0,
            'market_value': 1020.0})()

    def get_market_snapshot(self, codes):
        rows = [{'code': code, 'name': '浦发银行', 'last_price': 10.5,
                 'prev_close_price': 10.0, 'bid_price': 10.49,
                 'ask_price': 10.51, 'bid_vol': 100, 'ask_vol': 200,
                 'volume': 1000, 'open_price': 10.1, 'high_price': 10.6,
                 'low_price': 9.9, 'price_spread': 0.01,
                 'update_time': '2026-10-18 09:31:00'}
                for code in codes]
        return 0, pd.DataFrame(rows)

    def get_quote_list(self, symbols):
        rows = []
        for symbol in symbols:
            rows.append(type('Q', (), {
                'last_price': 10.5, 'pre_settlement': 10.0,
                'pre_close': 10.0, 'bid_price1': 10.49, 'ask_price1': 10.51,
                'bid_volume1': 100, 'ask_volume1': 200, 'volume': 1000,
                'open': 10.1, 'highest': 10.6, 'lowest': 9.9,
                'price_tick': 0.01, 'datetime': '2026-10-18 09:31:00',
            })())
        return rows

    def get_position(self, symbol=None, account=None):
        return type('P', (), {'pos_long': 100, 'pos_short': 0,
                              'open_price_long': 10.2,
                              'float_profit_long': 30.0})()

    def get_position_list(self, account=None):
        return [type('P', (), {
            'instrument_id': 'SH.600000', 'pos_long': 100, 'pos_short': 0,
            'open_price_long': 10.2, 'float_profit_long': 30.0,
            'volume_long_today': 100, 'margin': 1020.0})()]

    def get_order(self, order_id=None, account=None):
        return [type('O', (), {
            'order_id': 'x1', 'instrument_id': 'SZ.000001',
            'direction': 'BUY', 'offset': 'OPEN', 'volume_orign': 100,
            'volume_left': 0, 'status': 'FINISHED', 'limit_price': 10.0,
            'insert_date_time': '2026-10-18 09:31:00'})()]

    def get_trade(self, trade_id=None, account=None):
        return [type('T', (), {
            'instrument_id': 'SH.600000', 'direction': 'BUY',
            'offset': 'OPEN', 'price': 10.2, 'volume': 100,
            'commission': 5.0,
            'trade_date_time': '2026-10-18 09:31:00'})()]

    def insert_order(self, *args, **kwargs):
        self.last_order = kwargs or args
        return type('O', (), {'order_id': 'sim1'})()

    def cancel_order(self, order_id, account=None, **kwargs):
        self.cancelled = order_id

    def target_pos_task(self, symbol):
        api = self

        class _Task:
            def set_target_volume(self, value):
                api.targets.append((symbol, value))

        return _Task()


from minibt.desk import feeds as _feeds          # noqa: E402


class _StockFeed(_feeds.StockFeed):
    """直接继承 StockFeed：stock_rows / quotes / row_of 都是真的 ✓"""

    def __init__(self, api=None):
        super().__init__(api or _StockApi(), 'stocks')
        self.remember({'SSE.600000': '浦发银行', 'SZSE.000001': '平安银行'})

    def spec(self, symbol):
        return None

    def klines(self, symbol, cycle, length=500):
        rows = 60
        close = 10 + np.cumsum(np.random.default_rng(3).normal(0, 0.05, rows))
        return pd.DataFrame({
            'datetime': [(1_700_000_000 + index * 60) * 1_000_000_000
                         for index in range(rows)],
            'open': close - 0.02, 'high': close + 0.05,
            'low': close - 0.05, 'close': close, 'volume': 1000.0,
        })


class _EmptyCtx:
    def get_stock_basicinfo(self, market, security_type):
        return 0, pd.DataFrame([])


def _desk(tmp_path, rows: int = 0):
    from minibt.desk.app import Desk
    from minibt.desk.symbol_cache import SymbolCache

    desk = Desk(offline=True, allow_trading=True)
    desk.sent = []
    desk.sender = desk.sent.append
    api = _StockApi()
    if rows:
        api._ctx = type('Ctx', (), {})()
        frame = pd.DataFrame([
            {'code': f'SH.{600000 + index}', 'name': f'股票{index}',
             'stock_type': 'STOCK', 'exchange_type': 'SH'}
            for index in range(rows)])
        api._ctx.get_stock_basicinfo = lambda market, st: (0, frame)
        api._ctx.get_market_snapshot = api.get_market_snapshot
    desk.stocks = _StockFeed(api)
    desk.feeds = [desk.stocks]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'STOCK', 'exchange': 'SSE', 'text': ''}
    desk._cache = SymbolCache(str(tmp_path / 'symbols.sqlite3'))
    desk._cache_ready = True
    return desk


def test_stock_feed_rows_normalizes_symbols(tmp_path):
    desk = _desk(tmp_path, rows=3)
    rows = desk._rows_for_filter()
    assert [row['symbol'] for row in rows] == [
        'SSE.600000', 'SSE.600001', 'SSE.600002']
    assert rows[0]['name'] == '股票0'


def test_a_share_6500_rows_are_chunked(tmp_path):
    from minibt.desk import protocol as _protocol

    desk = _desk(tmp_path, rows=6500)
    desk.sent.clear()
    desk.reload_rows()
    blocks = [json.loads(script[len('window.__desk.applyPatch('):-2])
              for script in desk.sent]
    row_blocks = [patch for patch in blocks if patch['type'] == 'rows']
    assert len(row_blocks) == 13                    # 6500 / 500 ✓
    assert sum(len(block['rows']) for block in row_blocks) == 6500
    assert row_blocks[0]['replace'] is True
    assert all(block['replace'] is False for block in row_blocks[1:])

    # 第二次走缓存 → 不再联网（ctx 被换掉也不会报错）✓
    desk.stocks.api._ctx = type('Broken', (), {
        'get_stock_basicinfo': lambda self, *a: (1, None)})()
    desk.sent.clear()
    desk.reload_rows()
    row_blocks = [json.loads(script[len('window.__desk.applyPatch('):-2])
                  for script in desk.sent]
    row_blocks = [patch for patch in row_blocks
                  if patch['type'] == 'rows' and patch.get('rows')]
    assert sum(len(block['rows']) for block in row_blocks) == 6500


def test_stock_quotes_only_visible(tmp_path):
    desk = _desk(tmp_path, rows=2)
    desk.handle(protocol.encode_command(
        {'cmd': 'visible', 'payload': {'keys': ['SSE.600000']}}))
    desk.sent.clear()
    desk._tick_at = 0.0
    desk.tick()
    updates = [json.loads(script[len('window.__desk.applyPatch('):-2])
               for script in desk.sent]
    rows_update = [patch for patch in updates
                   if patch['type'] == 'rows_update']
    assert rows_update and rows_update[0]['rows'][0]['symbol'] == 'SSE.600000'
    assert rows_update[0]['rows'][0]['chg'] == pytest.approx(0.5)


def test_stock_account_tables_use_tq_symbols(tmp_path):
    desk = _desk(tmp_path, rows=1)
    payload = desk.account_payload()
    tables = payload['tables']
    assert tables['positions']['rows'][0][0] == 'SSE.600000'
    assert tables['trades']['rows'][0][0] == 'SSE.600000'
    assert tables['orders']['rows'][0][0] == 'SZSE.000001'
    assert payload['kind'] == 'stock'


def test_stock_trading_uses_local_sim(tmp_path):
    desk = _desk(tmp_path, rows=1)
    trader = desk.trading_view()
    trader.place('SSE.600000', 'buy', 100, 10.5)
    order = desk.stocks.api.last_order
    assert order['symbol'] == 'SSE.600000'
    assert order['direction'] == 'BUY' and order['offset'] == 'OPEN'
    assert order['volume'] == 100 and order['limit_price'] == 10.5

    trader.action('close', 'SSE.600000')
    assert desk.stocks.api.targets[-1] == ('SSE.600000', 0)

    trader.action('all')                       # 全平：符号要统一成 SSE. ✓
    assert desk.stocks.api.targets[-1][0] == 'SSE.600000'


def test_stock_indicators_compute(tmp_path):
    from minibt.desk import indicators as ind

    desk = _desk(tmp_path, rows=1)
    frame = desk.stocks.klines('SSE.600000', 60)
    payload = ind.compute('SSE.600000', frame, [{'key': 'MA'},
                                                {'key': 'MACD'}])
    keys = [item['key'] for item in payload['items']]
    assert 'MA20' in keys and 'MACD_DIF' in keys
    assert all(item['data'] for item in payload['items'])


def test_add_stocks_uses_desk_sim_account(monkeypatch):
    from minibt.desk.app import Desk
    import minibt.stock_api as stock_api

    captured = {}

    class _Api(stock_api.StockApi):
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(stock_api, 'StockApi', _Api)
    desk = Desk(offline=True)
    desk.add_stocks(host='127.0.0.1', port=11111)
    assert captured['sim_account'] == 'desk'
    assert captured['trade'] is False
    assert desk.stocks is not None and desk.stocks.kind == 'stocks'


def test_p5_assets_built():
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[1]
    stocks_src = (repo / 'minibt' / 'desk' / 'stocks.py').read_text(
        encoding='utf-8')
    assert 'def display_symbol' in stocks_src
    feeds_src = (repo / 'minibt' / 'desk' / 'feeds.py').read_text(
        encoding='utf-8')
    assert 'class StockFeed' in feeds_src
    app_src = (repo / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "sim_account: str = 'desk'" in app_src
