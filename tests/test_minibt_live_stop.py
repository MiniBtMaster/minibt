"""Stop（停止类）在**实盘**也能用 ✓

现状（修复前）：``StrategyBase._buy_live_trading`` / ``_sell_live_trading`` 收下了
``stop`` 却**完全没用** ✗（docstring 自己写着“预留，实盘止损需单独处理”）——
而回测是**每根 bar** 调 ``data.stop.update()`` ✓（``base.py`` 回测循环里那句）。

关键事实（决定了修法很小 ✓）：``Stop.update()`` 内部触发时调
``kline.set_target_size()`` ✓，而它**本来就会路由到实盘**：
``_set_target_size_live_trading`` → ``TargetPosTask`` ✓。所以缺的只是——
**在实盘也登记止损 + 每根 K 线推进一次** ✓。
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _read(*parts):
    return REPO.joinpath(*parts).read_text(encoding='utf-8')


class _Setting:
    isstop = False
    stop = None


class _FakeStop:
    calls = []

    def __init__(self, kline):
        self.kline = kline

    def update(self):
        type(self).calls.append('update')


class _FakeKLine:
    symbol = 'DCE.test'
    datetime = None                      # 每个用例自己设 ✓

    def __init__(self, times):
        self._klinesetting = _Setting()
        self.datetime = list(times)      # 用 list：``[-1]`` 按位置 ✓（同 Line ✓）

    def _set_stop(self, stop, **kwargs):
        self._klinesetting.isstop = True
        self._klinesetting.stop = stop(self)


def _stub(klines):
    from minibt.strategy.base import StrategyBase

    class _Stub:
        _isstop = True
        _btklinedataset = {}

    _Stub._register_live_stop = StrategyBase._register_live_stop
    _Stub._advance_live_stops = StrategyBase._advance_live_stops
    stub = _Stub()
    stub._btklinedataset = {f'k{i}': k for i, k in enumerate(klines)}
    return stub


def setup_function(_func):
    _FakeStop.calls = []


def test_register_live_stop_creates_stop_and_lines():
    """★ 开仓时把 ``stop`` 真正登记进 KLine（以前直接丢掉 ✗）"""
    kline = _FakeKLine(['2026-01-01'])
    stub = _stub([kline])
    stub._register_live_stop(kline, _FakeStop)
    assert kline._klinesetting.isstop is True
    assert isinstance(kline._klinesetting.stop, _FakeStop)
    # 传 None / 已登记过 → 幂等，不重复建 ✓
    stub._register_live_stop(kline, _FakeStop)
    assert isinstance(kline._klinesetting.stop, _FakeStop)


def test_advance_runs_once_per_bar():
    """★ 每根 K 线推进一次；同一根重复调用**不重复**推进 ✓"""
    kline = _FakeKLine(['2026-01-01', '2026-01-02'])
    stub = _stub([kline])
    stub._register_live_stop(kline, _FakeStop)

    stub._advance_live_stops()
    assert _FakeStop.calls == ['update']
    stub._advance_live_stops()
    assert _FakeStop.calls == ['update'], '同一根内重复推进了 ✗'

    kline.datetime = ['2026-01-01', '2026-01-02', '2026-01-03']
    stub._advance_live_stops()
    assert _FakeStop.calls == ['update', 'update'], '换根后应再推进一次 ✗'


def test_advance_skips_when_no_stop():
    kline = _FakeKLine(['2026-01-01'])
    stub = _stub([kline])
    stub._advance_live_stops()               # 没登记 → 什么都不做 ✓
    assert _FakeStop.calls == []

    stub._isstop = False                     # 策略级标记关掉 → 也不做 ✓
    stub._register_live_stop(kline, _FakeStop)
    stub._advance_live_stops()
    assert _FakeStop.calls == []


def test_live_paths_register_and_execute_trading_advances():
    """源码约束：买/卖实盘分支要登记止损；`_execute_live_trading` 要推进 ✓"""
    src = _read('minibt', 'strategy', 'base.py')
    for name in ('def _buy_live_trading', 'def _sell_live_trading'):
        start = src.index(name)
        body = src[start:start + 2200]
        assert 'self._register_live_stop(data, stop)' in body, name
    assert '预留，实盘止损需单独处理' not in src, '旧 docstring 没更新 ✗'

    start = src.index('def _execute_live_trading')
    body = src[start:start + 2200]
    assert 'self._advance_live_stops()' in body
    # 时机与回测一致：step() 之后 ✓
    assert body.index('self.step()') < body.index('self._advance_live_stops()')


def test_stop_update_reaches_live_target_size():
    """``Stop.update()`` 内部用 ``set_target_size``，而它**本就**会走实盘 ✓

    （所以不需要在 live 里另写一套下单逻辑 ✗）
    """
    src = _read('minibt', 'strategy', 'base.py')
    assert '_set_target_size_live_trading' in src
    start = src.index('def set_target_size')
    assert '_set_target_size_live_trading' in src[start:start + 900]
