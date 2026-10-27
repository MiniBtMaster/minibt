"""P33：股票/期货账户分离 + 时区 + 图例圆点 + 持仓线标签左侧 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------------ 账户分离
def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.trading = True
    return desk


class _Feed:
    def __init__(self, kind, api):
        self.kind = kind
        self.api = api

    def available(self):
        return True


class _Api:
    _account = None
    _trd = None

    def __init__(self):
        self.calls = []

    def insert_order(self, **kwargs):
        self.calls.append(kwargs.get('symbol'))
        return 'ok'


def test_futures_and_stocks_route_to_their_own_api(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    fut, stk = _Api(), _Api()
    desk.futures = _Feed('futures', fut)
    desk.stocks = _Feed('stocks', stk)
    desk.feeds = [desk.futures, desk.stocks]
    desk.offline = False
    desk.tabs['SHFE.ag2612'] = {'feed': desk.futures, 'cycle': 60}

    trader = desk.trading_view()
    trader.place('SHFE.ag2612', 'buy', 1, 7000)
    trader.place('SSE.600000', 'buy', 100, 10.0)
    trader.place('HK.00700', 'buy', 100, 300.0)

    assert fut.calls == ['SHFE.ag2612']            # 期货 → 天勤 ✓
    assert stk.calls == ['SSE.600000', 'HK.00700']  # 股票 → 本地模拟 ✓


def test_account_labels_split_stock_and_futures(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.futures = _Feed('futures', _Api())
    desk.stocks = _Feed('stocks', _Api())
    desk.feeds = [desk.futures, desk.stocks]
    desk.offline = False
    trader = desk.trading_view()
    assert trader.account_label('SHFE.ag2612') == '天勤模拟'
    assert trader.account_label('SSE.600000') == '股票本地模拟'

    state = desk.trading_state('SHFE.ag2612')
    assert state['kind'] == 'futures' and state['account'] == '天勤模拟'
    state = desk.trading_state('SSE.600000')
    assert state['kind'] == 'stocks' and state['account'] == '股票本地模拟'


def test_looks_stock_knows_desk_prefixes():
    from minibt.desk.feeds import _looks_stock

    for symbol in ('SSE.600000', 'SZSE.000001', 'HK.00700', 'US.AAPL'):
        assert _looks_stock(symbol), symbol
    for symbol in ('SHFE.ag2612', 'CFFEX.IC2009', 'DCE.m2609'):
        assert not _looks_stock(symbol), symbol


def test_stock_api_rejects_futures_symbols():
    """本地股票模拟盘绝不能接期货单（否则“成交”了但天勤没持仓 ✗）"""
    from minibt.stock_api import StockApi

    api = object.__new__(StockApi)           # 不连网关，只测护栏 ✓
    with pytest.raises(ValueError) as info:
        api.insert_order(symbol='SHFE.ag2612', direction='BUY', volume=1)
    assert '期货' in str(info.value)


# ------------------------------------------------------------ 时区
def test_futures_timezone_shift():
    pd = pytest.importorskip('pandas')
    from minibt.desk import feeds

    assert feeds.TZ_OFFSET_HOURS == 8
    utc = pd.to_datetime(['2026-10-19 02:30:00']).astype('int64')   # UTC
    frame = pd.DataFrame({'datetime': utc, 'open': [1.0], 'high': [1.0],
                          'low': [1.0], 'close': [1.0], 'volume': [1]})
    shifted = feeds.shift_timezone(frame)
    stamp = pd.to_datetime(int(shifted['datetime'].iloc[0]))
    assert stamp.hour == 10 and stamp.minute == 30           # 北京 10:30 ✓
    # 股票（本来就是本地）不平移 ✓
    plain = feeds.shift_timezone(frame, offset_hours=0)
    assert pd.to_datetime(int(plain['datetime'].iloc[0])).hour == 2


def test_quote_time_clock_handles_microseconds():
    from minibt.desk.symbols import _clock

    assert _clock('2026-10-19 10:30:00.000000') == '10:30:00'
    assert _clock('2026-10-19 02:30:00.5', 8) == '10:30:00'


def test_futures_feed_shifts_but_stock_feed_does_not():
    feeds = _read('minibt/desk/feeds.py')
    assert 'time_shift_hours = TZ_OFFSET_HOURS' in feeds
    assert 'return shift_timezone(frame, offset_hours=self.time_shift_hours)' in feeds


def test_feed_klines_uses_its_own_time_shift():
    """股票 09:30 不能被 +8；期货 UTC 仍要 +8 ✓"""
    import pandas as pd
    from minibt.desk.feeds import BaseFeed

    local = pd.to_datetime(['2026-10-19 09:30:00']).astype('int64')

    class FakeApi:
        def get_kline_serial(self, *args, **kwargs):
            return pd.DataFrame({'datetime': local, 'open': [1.0],
                                 'high': [1.0], 'low': [1.0],
                                 'close': [1.0], 'volume': [1]})

    feed = BaseFeed.__new__(BaseFeed)
    feed.api = FakeApi()
    feed.time_shift_hours = 0
    out = feed.klines('SH.600000', 60)
    assert pd.to_datetime(int(out['datetime'].iloc[0])).hour == 9
    feed.time_shift_hours = 8
    out = feed.klines('SHFE.rb2610', 60)
    assert pd.to_datetime(int(out['datetime'].iloc[0])).hour == 17


# ------------------------------------------------------------ 图例圆点 / 持仓标签
def test_legend_uses_round_swatch():
    legend = _read('jslib/src/general/legend.ts')
    assert 'function swatch(' in legend
    assert 'border-radius:50%' in legend
    # 只在注释里还提到 `▨`（说明历史），代码里不能再出现 ✓
    assert legend.count('▨') == 1


def test_position_line_label_is_inside_chart():
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'axisLabelVisible: false' in page      # 不再画在价格轴里 ✓
    assert '_addPositionBadge(' in page
    assert "badge.style.left = '8px'" in page
    css = _read('jslib/src/desk/desk.css')
    assert '.desk-pos-badge' in css
