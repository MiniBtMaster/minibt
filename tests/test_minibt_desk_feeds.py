"""行情源非阻塞：TqSdk 首次/断线 get_* 不能卡住主线程 ✓"""
from __future__ import annotations

import time

from minibt.desk.feeds import BaseFeed


class _SlowApi:
    def wait_update(self, deadline=None):
        time.sleep(2.0)
        return True


def test_fast_call_disables_inner_wait_update():
    api = _SlowApi()
    feed = BaseFeed(api)
    original = api.wait_update

    def get_kline_serial(*args, **kwargs):
        api.wait_update(deadline=999)
        return 'frame'

    started = time.monotonic()
    assert feed._fast_call(get_kline_serial, 'X', 60) == 'frame'
    assert time.monotonic() - started < 0.5
    assert api.wait_update == original


def test_fast_call_keeps_exception_for_caller():
    api = _SlowApi()
    feed = BaseFeed(api)

    def timeout_get(*args, **kwargs):
        api.wait_update()
        raise TimeoutError('quote timeout')

    try:
        feed._fast_call(timeout_get)
    except TimeoutError:
        pass
    else:
        raise AssertionError('应把超时交给调用方处理')
    assert api.wait_update != None  # noqa: E711  # restored


def test_futures_feed_skips_unknown_symbol_after_symbols_loaded():
    from minibt.desk.feeds import FuturesFeed

    class Api:
        _data = {'symbols': {'SHFE.ag2612': {'instrument_class': 'FUTURE',
                                             'exchange_id': 'SHFE'}}}

    feed = FuturesFeed(Api(), 'futures')
    assert feed.valid_symbol('SHFE.ag2612') is True
    assert feed.valid_symbol('KQ.m@SHFE.ag') is True
    # 只有 pump 明确报不存在时才拉黑；不能用局部 symbols 白名单误杀缓存合约 ✓
    feed.drop_symbol('SHFE.ag2701')
    assert feed.valid_symbol('SHFE.ag2701') is False
    assert feed.klines('SHFE.ag2701', 60, 10) is None


def test_fast_call_marks_loop_running_for_quote_list():
    from types import SimpleNamespace
    from minibt.desk.feeds import FuturesFeed

    class Loop:
        def is_running(self):
            return False

    class Api:
        _data = {'quotes': {}}
        _loop = Loop()

        def get_quote_list(self, symbols):
            if not self._loop.is_running():
                raise TimeoutError('would block')
            return [SimpleNamespace(
                last_price=100.0, pre_settlement=99.0,
                bid_price1=99.0, bid_volume1=1, ask_price1=101.0,
                ask_volume1=2, upper_limit=110.0, lower_limit=90.0,
                volume=10, open=99.0, highest=101.0, lowest=98.0,
                pre_close=99.0, datetime='2026-10-26T10:00:00Z',
                price_tick=1.0, instrument_name='测试')]

    feed = FuturesFeed(Api(), 'futures')
    feed.use_quote_list = True
    rows = feed.quotes(['SHFE.rb2601'])
    assert rows and rows[0]['last'] == 100.0
    assert Api._loop.is_running() is False  # 恢复 ✓


def test_fast_query_accepts_tqsdk_filter_keyword():
    import inspect
    from minibt.desk.feeds import BaseFeed
    source = inspect.getsource(BaseFeed._fast_query)
    assert "kwargs.get('filter')" in source
    assert 'filter_=None' in source
