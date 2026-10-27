"""P2 补充测试：二级报价 / 持仓线 / 看盘页刷新链路。"""

import json

import pytest

from minibt.desk import protocol


class _Quote:
    last_price = 3600.0
    pre_settlement = 3590.0
    pre_close = 3588.0
    open = 3595.0
    highest = 3610.0
    lowest = 3580.0
    volume = 12000.0
    open_interest = 5000.0
    amount = 1.2e9
    settlement = None
    price_tick = 1.0

    def __init__(self):
        for index in range(1, 6):
            setattr(self, f'ask_price{index}', 3600.0 + index)
            setattr(self, f'ask_volume{index}', 10 + index)
            setattr(self, f'bid_price{index}', 3600.0 - index)
            setattr(self, f'bid_volume{index}', 20 + index)


class _Position:
    pos_long = 2
    pos_short = 1
    open_price_long = 3595.0
    open_price_short = 3610.0
    float_profit_long = 100.0
    float_profit_short = -50.0


class _Api:
    def get_tick_serial(self, symbol):
        pd = pytest.importorskip('pandas')
        return pd.DataFrame({
            'datetime': [1_700_000_000_000_000_000] * 3,
            'last_price': [3600.0, 3601.0, 3599.0],
            'volume': [1, 2, 3],
            'bid_price1': [3599.0] * 3,
            'ask_price1': [3601.0] * 3,
        })

    def get_position(self, symbol, account=None):
        return _Position()


class _BookFeed:
    """能提供 spec / ticks / position 的假行情源 ✓"""

    kind = 'futures'

    def __init__(self):
        self.api = _Api()
        self.cycle = None

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
        return _Quote()

    def klines(self, symbol, cycle, length=500):
        self.cycle = cycle
        pd = pytest.importorskip('pandas')
        return pd.DataFrame({
            'datetime': [1_700_000_000_000_000_000, 1_700_000_060_000_000_000],
            'open': [1.0, 2.0], 'high': [2.0, 3.0], 'low': [0.5, 1.5],
            'close': [1.5, 2.5], 'volume': [10, 20],
        })


def _desk_book(tmp_path):
    from minibt.desk.app import Desk
    from minibt.desk.symbol_cache import SymbolCache

    sent = []
    desk = Desk(offline=True)
    desk.sender = sent.append
    desk._cache = SymbolCache(str(tmp_path / 'symbols.sqlite3'))
    desk._cache_ready = True
    desk.futures = _BookFeed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    return desk, sent


def _payload(script):
    return json.loads(script[len('window.__desk.applyPatch('):-2])


def test_book_payload_five_levels_and_ticks(tmp_path):
    desk, _sent = _desk_book(tmp_path)
    book = desk.book_payload('SHFE.rb2610')
    assert book['type'] == 'book' and book['symbol'] == 'SHFE.rb2610'
    assert book['levels'] == 5 and book['depth'] == 5
    assert [level['price'] for level in book['asks']] == [
        3601.0, 3602.0, 3603.0, 3604.0, 3605.0]
    assert [level['price'] for level in book['bids']] == [
        3599.0, 3598.0, 3597.0, 3596.0, 3595.0]
    assert book['info']['last'] == 3600.0
    assert book['info']['chg'] == pytest.approx(10.0)          # 按昨结算 ✓
    assert book['info']['open_interest'] == 5000.0
    # 现手 = 相邻两笔累计差：首笔算不出差 → 跳过（3 条 tick → 2 条现手 ✓）
    assert len(book['ticks']) == 2
    assert set(book['ticks'][0]) == {'time', 'price', 'volume', 'direction'}
    assert book['trading'] is True                             # P4：已接交易 ✓


def test_book_payload_stock_has_depth_one(tmp_path):
    desk, _sent = _desk_book(tmp_path)
    book = desk.book_payload('HK.00700')
    assert book['levels'] == 1 and book['depth'] == 1
    assert len(book['asks']) == 1 and len(book['bids']) == 1


def test_position_payload_long_and_short(tmp_path):
    desk, _sent = _desk_book(tmp_path)
    payload = desk.position_payload('SHFE.rb2610')
    assert payload['type'] == 'position'
    assert payload['long']['volume'] == 2.0
    assert payload['long']['avg'] == 3595.0
    assert payload['long']['side'] == '多'
    assert payload['short']['volume'] == 1.0
    assert payload['short']['side'] == '空'


def test_position_payload_empty_when_no_position(tmp_path):
    desk, _sent = _desk_book(tmp_path)

    class _Flat:
        pos_long = 0
        pos_short = 0

    desk.futures.api.get_position = lambda symbol, account=None: _Flat()
    payload = desk.position_payload('SHFE.rb2610')
    assert payload['long'] is None and payload['short'] is None


def test_open_chart_emits_kline_book_position(tmp_path):
    desk, sent = _desk_book(tmp_path)
    sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'open_chart', 'payload': {'symbol': 'SHFE.rb2610'}}))
    kinds = [_payload(script)['type'] for script in sent]
    # P3/P4 之后首屏还会带账户面板 + 交易状态 ✓
    assert kinds[:4] == ['open_tab', 'kline', 'book', 'position']
    assert 'account' in kinds and 'trading' in kinds


def test_tick_refreshes_book_and_position(tmp_path):
    desk, sent = _desk_book(tmp_path)
    desk.handle(protocol.encode_command(
        {'cmd': 'open_chart', 'payload': {'symbol': 'SHFE.rb2610'}}))
    sent.clear()
    # 打开时已经**全量推过** K 线，且同一根 1 秒内不重复推（省带宽 ✓）
    # → 把「上次推送时间」拨回 1 秒前，模拟下一拍该刷了 ✓
    desk.tabs['SHFE.rb2610']['_kline_at'] = 0.0
    desk._tick_at = 0.0
    desk.tick()
    kinds = [_payload(script)['type'] for script in sent]
    assert 'kline' in kinds and 'book' in kinds and 'position' in kinds


def test_book_command_flushes_panel(tmp_path):
    desk, sent = _desk_book(tmp_path)
    sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'book', 'payload': {'symbol': 'SHFE.rb2610'}}))
    assert [_payload(script)['type'] for script in sent] == ['book']


def test_p2_assets_built():
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[1]
    js_dir = repo / 'pylightcharts' / 'js'
    script = (js_dir / 'desk.js').read_text(encoding='utf-8', errors='ignore')
    css = (js_dir / 'desk.css').read_text(encoding='utf-8')
    assert 'desk-book' in script and 'desk-book' in css
    assert 'desk-chart-body' in script and 'desk-chart-body' in css
    panel = repo / 'jslib' / 'src' / 'desk' / 'quote-panel.ts'
    assert panel.is_file()
    app = (repo / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    for case in ("'book'", "'position'"):
        assert f'case {case}' in app, case
    chart = (repo / 'jslib' / 'src' / 'desk' / 'chart-page.ts').read_text(
        encoding='utf-8')
    assert 'HorizontalLine' in chart and 'setPosition' in chart
