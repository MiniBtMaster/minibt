"""实时图表：多合约策略（test_2 / test_3 两种写法）的数据 + 下单路由。

* test_3.py 写法：`self.klines1 / self.klines2` → 用多布局各格的 frames；
* test_2.py 写法：`get_kline(LocalDatas.pp2609_60)` → 实时图表里按
  “品种代码”对到真实合约（DCE.pp2609），或按调用顺序兜底；
* 每拍必须把**每个合约自己的 frame** 灌进对应的 KLine，不能都用主图覆盖。
"""
from __future__ import annotations

import pandas as pd
import pytest

from minibt import Strategy
from minibt.desk.strategy_runner import (StrategyRunner, _is_local_name,
                                         _same_underlying)


def _frame(symbol: str, closes, start='2026-01-01 09:00'):
    count = len(closes)
    return pd.DataFrame({
        'datetime': pd.date_range(start, periods=count, freq='min'),
        'open': [float(value) for value in closes],
        'high': [float(value) + 1 for value in closes],
        'low': [float(value) - 1 for value in closes],
        'close': [float(value) for value in closes],
        'volume': [100.0] * count,
        'symbol': [symbol] * count,
        'duration': [60] * count,
        'price_tick': [1.0] * count,
        'volume_multiple': [10.0] * count,
    })


class GetKlinePair(Strategy):
    """test_2.py 的写法：在 __init__ 里两次 get_kline ✓"""

    def __init__(self):
        self.left = self.get_kline('LEFT')
        self.right = self.get_kline('RIGHT')
        self.seen = None

    def next(self):
        self.seen = (float(self.left.close.new),
                     float(self.right.close.new))


class KlinesPair(Strategy):
    """test_3.py 的写法：直接用 klines1 / klines2 ✓"""

    def __init__(self):
        self.fast = self.klines1.close.sma(2)
        self.slow = self.klines2.close.sma(2)
        self.seen = None

    def next(self):
        self.seen = (float(self.klines1.close.new),
                     float(self.klines2.close.new))


def test_symbol_matching_helpers():
    assert _same_underlying('pp2609_60', 'DCE.pp2609')
    assert _same_underlying('l2609_60', 'DCE.l2609')
    assert _same_underlying('SHFE.rb2601', 'rb2601')
    assert not _same_underlying('pp2609_60', 'DCE.l2609')
    assert _is_local_name('pp2609_60')
    assert not _is_local_name('DCE.pp2609')


def test_get_kline_pair_advance_updates_each_contract():
    """get_kline 写法：prepare 后每拍重跑 __init__ 也不能变成 None ✓"""
    runner = StrategyRunner(GetKlinePair, symbol='LEFT', cycle=60)
    left = _frame('LEFT', [10, 11, 12, 13, 14])
    right = _frame('RIGHT', [20, 21, 22, 23, 24])
    runner.prepare([('LEFT', left), ('RIGHT', right)], seed_kline=True)
    strategy = runner.strategy
    assert strategy.left is not None and strategy.right is not None
    assert runner.update_symbols() == ['LEFT', 'RIGHT']
    assert len({id(runner._klines[0])}) == 1

    left2 = _frame('LEFT', [10, 11, 12, 13, 99])
    right2 = _frame('RIGHT', [20, 21, 22, 23, 88])
    assert runner.advance({'LEFT': left2, 'RIGHT': right2})
    # advance 里会重跑用户 __init__（get_kline 必须返回**同一个** KLine）
    assert strategy.left is not None and strategy.right is not None
    # on_close=True（默认）→ 第一次按**上一根已完成**的 K 线跑 next
    assert strategy.seen == (13.0, 23.0)
    # 两个 KLine 各用各的 frame（不会都被主图覆盖 ✗）
    assert float(runner._klines[-2].close.new) == 99.0
    assert float(runner._klines[-1].close.new) == 88.0


def test_klines_pair_uses_layout_frames(tmp_path, monkeypatch):
    """klines1/2 写法：多布局两格 → 各自独立 K 线 ✓"""
    runner = StrategyRunner(KlinesPair, symbol='LEFT', cycle=60)
    runner.prepare([('LEFT', _frame('LEFT', [10, 11, 12, 13, 14])),
                    ('RIGHT', _frame('RIGHT', [20, 21, 22, 23, 24]))],
                   seed_kline=True)
    strategy = runner.strategy
    assert runner.update_symbols() == ['LEFT', 'RIGHT']
    assert runner.advance({
        'LEFT': _frame('LEFT', [10, 11, 12, 13, 77]),
        'RIGHT': _frame('RIGHT', [20, 21, 22, 23, 66]),
    })
    assert strategy.seen == (13.0, 23.0)


def test_desk_builds_frame_map_for_each_symbol(tmp_path, monkeypatch):
    """Desk 每拍：主图用已有 frame，另一腿单独取（不能拿主图冒充）✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sender = lambda *_a, **_k: None
    desk._booted = True
    left = _frame('LEFT', [10, 11, 12])
    right = _frame('RIGHT', [20, 21, 22])
    frames = {'LEFT': left, 'RIGHT': right}
    monkeypatch.setattr(
        desk, '_strategy_frame',
        lambda symbol, info=None, cycle=0: frames.get(str(symbol)))

    class FakeRunner:
        def update_symbols(self):
            return ['LEFT', 'RIGHT']

    info = {'cycle': 60}
    result = desk._strategy_update_frames(
        FakeRunner(), 'LEFT', info, left)
    assert isinstance(result, dict)
    assert result['LEFT'] is left
    assert result['RIGHT'] is right
    # 第二次走缓存（同一秒内不再取）✓
    again = desk._strategy_update_frames(FakeRunner(), 'LEFT', info, left)
    assert again['RIGHT'] is right


def test_chart_frames_put_layout_cells_first(tmp_path, monkeypatch):
    """多布局：klines1/2 必须按**格序**，不是按“当前点的是哪格” ✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sender = lambda *_a, **_k: None
    desk._booted = True
    monkeypatch.setattr(
        desk, '_strategy_frame',
        lambda symbol, info=None, cycle=0: _frame(str(symbol), [1, 2, 3]))
    info = {'cycle': 60, 'layout': {
        'symbols': ['DCE.pp2609', 'DCE.l2609'],
        'cells': [{'symbol': 'DCE.pp2609'}, {'symbol': 'DCE.l2609'}],
    }}
    frames = desk._strategy_frames_for_chart('DCE.l2609', info)
    assert [name for name, _frame_ in frames] == [
        'DCE.pp2609', 'DCE.l2609']


def test_live_pair_orders_route_to_each_real_contract(monkeypatch):
    """实时/模拟盘：test_2 的 LocalDatas 名字 → 两个真实合约各自下单 ✓"""
    from minibt.utils import Base
    from minibt.indicators import core as core_module

    class FakeQuote:
        last_price = 100.0
        price_tick = 1.0
        volume_multiple = 10.0
        margin = 1000.0
        margin_rate = 0.08

    class FakePosition:
        def __init__(self):
            self.pos = 0
            self.margin = 0.0
            self.float_profit = 0.0

    class FakeTarget:
        def __init__(self, position):
            self.position = position

        def set_target_volume(self, target):
            self.position.pos = int(target)

    class FakeTqObjs:
        registry = {}

        def __init__(self, symbol, account=None):
            self.symbol = symbol
            self.Quote = FakeQuote()
            self.Position = FakePosition()
            self.TargetPosTask = FakeTarget(self.Position)
            FakeTqObjs.registry[symbol] = self

    class FakeAccount:
        available = 1_000_000.0

    class FakeApi:
        def get_account(self, account=None):
            return FakeAccount()

        def wait_update(self, timeout=1):
            return True

    class LivePair(Strategy):
        def __init__(self):
            # test_2.py 的写法：本地 CSV 名（带 _60）
            self.left = self.get_kline('pp2609_60')
            self.right = self.get_kline('l2609_60')

        def next(self):
            self.left.set_target_size(2)
            self.right.set_target_size(-3)

    monkeypatch.setattr(core_module, 'TqObjs', FakeTqObjs)
    monkeypatch.setattr(Base, '_is_live_trading', True, raising=False)
    monkeypatch.setattr(Base, '_tqobjs', {}, raising=False)
    FakeTqObjs.registry.clear()
    api = FakeApi()
    left = _frame('DCE.pp2609', [100, 101, 102, 103, 104])
    right = _frame('DCE.l2609', [200, 201, 202, 203, 204])
    runner = StrategyRunner(
        LivePair, symbol='DCE.pp2609', cycle=60,
        live=True, api=api, account=FakeAccount())
    runner.prepare([('DCE.pp2609', left), ('DCE.l2609', right)],
                   seed_kline=True)
    assert runner.update_symbols() == ['DCE.pp2609', 'DCE.l2609']
    # 预建 K 线也必须是**真实合约**（klines1/2 写法的下单靠它 ✓）
    assert runner._klines[0].symbol == 'DCE.pp2609'
    assert runner._klines[1].symbol == 'DCE.l2609'
    # 实盘每手保证金（test_2 用它算手数；空仓也必须 > 0 ✓）
    assert runner.strategy.left.margin == 1000.0
    assert runner.strategy.left.volume_multiple == 10.0
    assert runner.advance({
        'DCE.pp2609': left,
        'DCE.l2609': right,
    })
    # 两个腿分别下到自己的真实合约（不是都下到主图）✓
    assert FakeTqObjs.registry['DCE.pp2609'].Position.pos == 2
    assert FakeTqObjs.registry['DCE.l2609'].Position.pos == -3
    assert set(FakeTqObjs.registry) == {'DCE.pp2609', 'DCE.l2609'}


def test_fetch_frame_resolves_local_name_to_open_contract(tmp_path, monkeypatch):
    """test_2 的 LocalDatas.pp2609_60 → 已打开的 DCE.pp2609（跨 tab 也行）✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sender = lambda *_a, **_k: None
    desk._booted = True
    desk.tabs = {'DCE.l2609': {}, 'DCE.pp2609': {}}
    monkeypatch.setattr(
        desk, '_strategy_frame',
        lambda symbol, info=None, cycle=0: _frame(str(symbol), [1, 2, 3]))
    fetch = desk._fetch_strategy_frame({'cycle': 60}, 60)
    real, frame = fetch('pp2609_60', 60)
    assert real == 'DCE.pp2609'
    assert frame is not None and len(frame) == 3
    # 已经是真实合约 → 直接用 ✓
    real, _frame_ = fetch('DCE.l2609', 60)
    assert real == 'DCE.l2609'


def test_klines2_requires_prepared_layout(tmp_path, monkeypatch):
    """klines1/2 写法无法从策略里知道合约 → 必须先把布局/合约准备好 ✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sender = lambda *_a, **_k: None
    desk._booted = True
    desk.tabs = {'DCE.pp2609': {}, 'DCE.l2609': {}}
    monkeypatch.setattr(
        desk, '_strategy_frame',
        lambda symbol, info=None, cycle=0: _frame(str(symbol), [1, 2, 3]))
    path = tmp_path / 'pair.py'
    path.write_text(
        'class X:\n    def __init__(self):\n        self.a = self.klines2\n',
        encoding='utf-8')
    info = {'cycle': 60}
    # 当前布局是单图 → 不会擅自拿另一个 tab 来凑数 ✓
    frames = desk._strategy_frames_for_chart(
        'DCE.pp2609', info, path=str(path))
    assert [name for name, _f in frames] == ['DCE.pp2609']
    prepared = desk._prepare_realtime_strategy(
        'DCE.pp2609', info, str(path), None, 60)
    assert not prepared.get('ok')
    assert 'klines1..klines2' in str(prepared.get('error'))
    # 用户先切好 2 格布局并加载两个合约 → 就能加策略 ✓
    info['layout'] = {'cols': 2, 'rows': 1,
                      'symbols': ['DCE.pp2609', 'DCE.l2609'],
                      'cells': [{'symbol': 'DCE.pp2609'},
                                {'symbol': 'DCE.l2609'}]}
    prepared = desk._prepare_realtime_strategy(
        'DCE.pp2609', info, str(path), None, 60)
    assert prepared.get('ok')
    assert [name for name, _f in prepared['frames']] == [
        'DCE.pp2609', 'DCE.l2609']


def test_run_overlay_multi_frames_do_not_overwrite_second_leg():
    """「加到图表」的第一次 advance 也必须按每个合约自己的 frame ✓"""
    from minibt.desk import strategy_overlay as overlay

    class Pair(Strategy):
        def __init__(self):
            self.left = self.get_kline('LEFT')
            self.right = self.get_kline('RIGHT')
            self.fast = self.left.close.sma(2)
            self.seen = None

        def next(self):
            self.seen = (float(self.left.close.new),
                         float(self.right.close.new))

    left = _frame('LEFT', [10, 11, 12, 13, 14])
    right = _frame('RIGHT', [20, 21, 22, 23, 24])
    result = overlay.run_overlay(
        left, Pair, 'LEFT', 60,
        frames=[('LEFT', left), ('RIGHT', right)])
    assert result.get('ok'), result.get('error')
    runner = result['runner']
    assert runner.strategy.seen == (13.0, 23.0)


def _install_fake_live(monkeypatch):
    """Fake TqObjs / API（不下真单，只记录 TargetPosTask 目标仓位）✓"""
    from minibt.utils import Base
    from minibt.indicators import core as core_module

    class FakeQuote:
        last_price = 100.0
        price_tick = 1.0
        volume_multiple = 10.0
        margin = 1000.0
        margin_rate = 0.08

    class FakePosition:
        def __init__(self):
            self.pos = 0
            self.margin = 0.0
            self.float_profit = 0.0

    class FakeTarget:
        def __init__(self, position):
            self.position = position

        def set_target_volume(self, target):
            self.position.pos = int(target)

    class FakeTqObjs:
        registry = {}

        def __init__(self, symbol, account=None):
            self.symbol = symbol
            self.Quote = FakeQuote()
            self.Position = FakePosition()
            self.TargetPosTask = FakeTarget(self.Position)
            FakeTqObjs.registry[symbol] = self

    class FakeAccount:
        available = 1_000_000.0

    class FakeApi:
        def get_account(self, account=None):
            return FakeAccount()

        def wait_update(self, timeout=1):
            return True

    monkeypatch.setattr(core_module, 'TqObjs', FakeTqObjs)
    monkeypatch.setattr(Base, '_is_live_trading', True, raising=False)
    monkeypatch.setattr(Base, '_tqobjs', {}, raising=False)
    FakeTqObjs.registry.clear()
    return FakeTqObjs, FakeApi, FakeAccount


def test_live_get_kline_second_contract_fetched_from_another_tab(
        monkeypatch):
    """只开了主图 tab 时，get_kline('l2609_60') 也要能按品种取到另一 tab ✓"""
    FakeTqObjs, FakeApi, FakeAccount = _install_fake_live(monkeypatch)

    class LivePair(Strategy):
        def __init__(self):
            self.left = self.get_kline('pp2609_60')
            self.right = self.get_kline('l2609_60')

        def next(self):
            self.left.set_target_size(1)
            self.right.set_target_size(-2)

    left = _frame('DCE.pp2609', [100, 101, 102, 103, 104])
    right = _frame('DCE.l2609', [200, 201, 202, 203, 204])

    def fetch(symbol, duration_seconds=None):
        if _same_underlying('DCE.l2609', str(symbol)):
            return ('DCE.l2609', right)
        return None

    runner = StrategyRunner(
        LivePair, symbol='DCE.pp2609', cycle=60,
        live=True, api=FakeApi(), account=FakeAccount(),
        fetch_frame=fetch)
    runner.prepare([('DCE.pp2609', left)], seed_kline=True)
    assert runner.update_symbols() == ['DCE.pp2609', 'DCE.l2609']
    assert runner.advance({'DCE.pp2609': left, 'DCE.l2609': right})
    assert FakeTqObjs.registry['DCE.pp2609'].Position.pos == 1
    assert FakeTqObjs.registry['DCE.l2609'].Position.pos == -2


def test_live_klines_pair_buy_sell_route_to_each_contract(monkeypatch):
    """test_3 写法：klines1/2 + self.buy/sell(data=...) 各自下单 ✓"""
    FakeTqObjs, FakeApi, FakeAccount = _install_fake_live(monkeypatch)

    class LiveKlinesPair(Strategy):
        def __init__(self):
            self.fast = self.klines1.close.sma(2)
            self.slow = self.klines2.close.sma(2)

        def next(self):
            self.buy(data=self.klines1, size=1)
            self.sell(data=self.klines2, size=2)

    left = _frame('DCE.pp2609', [100, 101, 102, 103, 104])
    right = _frame('DCE.l2609', [200, 201, 202, 203, 204])
    runner = StrategyRunner(
        LiveKlinesPair, symbol='DCE.pp2609', cycle=60,
        live=True, api=FakeApi(), account=FakeAccount())
    runner.prepare([('DCE.pp2609', left), ('DCE.l2609', right)],
                   seed_kline=True)
    assert runner.advance({
        'DCE.pp2609': left,
        'DCE.l2609': right,
    })
    assert FakeTqObjs.registry['DCE.pp2609'].Position.pos == 1
    assert FakeTqObjs.registry['DCE.l2609'].Position.pos == -2
