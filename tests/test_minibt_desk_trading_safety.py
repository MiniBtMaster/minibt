"""交易执行安全：平仓别名 / 全平失败 / 反手失败 / 账户缓存清理 ✓"""
from __future__ import annotations

from types import SimpleNamespace

from minibt.desk.trading import Trading


def _trading():
    trader = Trading.__new__(Trading)
    trader.desk = SimpleNamespace(trading=True, push_log=lambda *a, **k: None)
    trader._tasks = {}
    trader._position_error = ''
    trader._replay_sim = lambda symbol='': None
    trader._decimals = lambda symbol='': 2
    trader.account_label = lambda symbol='': '测试账户'
    trader.account_kwargs = lambda symbol='': {}
    return trader


def test_close_uses_volume_aliases():
    trader = _trading()
    trader._position = lambda symbol: SimpleNamespace(volume_long=2)
    calls = []

    class Api:
        def insert_order(self, **kwargs):
            calls.append(kwargs)

    trader.api = lambda symbol='': Api()
    text = trader.place('SHFE.rb2610', 'close', 2)
    assert 'SELL' in text
    assert calls and calls[0]['volume'] == 2
    assert calls[0]['offset'] == 'CLOSE'


def test_close_all_reports_set_target_failure():
    trader = _trading()
    trader._positions = lambda: [SimpleNamespace(
        instrument_id='SHFE.rb2610', pos_long=1)]
    trader._set_target = lambda symbol, target: '调仓失败: network down'
    assert '失败' in trader._close_all()


def test_close_all_reports_position_query_failure():
    trader = _trading()
    def positions():
        trader._position_error = 'network down'
        return []

    trader._positions = positions
    text = trader._close_all()
    assert '无法查询持仓' in text and 'network down' in text


def test_reverse_does_not_open_when_close_fails():
    trader = _trading()
    trader.ready = lambda symbol='': True
    trader._position = lambda symbol: SimpleNamespace(pos_long=1)
    calls = []

    def market(symbol, direction, offset, volume):
        calls.append((direction, offset, volume))
        return '下单失败：rejected'

    trader._market_order = market
    text = trader.reverse_symbol('SHFE.rb2610')
    assert '反手失败' in text
    assert calls == [('SELL', 'CLOSE', 1)]


def test_clear_account_cache_drops_target_tasks():
    trader = _trading()
    trader._tasks['SHFE.rb2610'] = object()
    trader.clear_account_cache()
    assert trader._tasks == {}
