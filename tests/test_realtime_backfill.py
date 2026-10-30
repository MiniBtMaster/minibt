"""实时图「换根时回填上一根」的正确性 —— LWC 的 ``historicalUpdate`` ✓。

背景（用户提出）：网络延时下，上一根 K 线最后一次更新时可能还不是收盘价，
所以**新 K 线到来时必须连上一根一起重推**（K 线 + 指标），否则上一根永远停在
“最后一拍”的中间价上 ✗。minibt ``_refresh_market`` 本来就是这么做的
（回填上一根 + 把中间漏掉的多根按序补齐 ✓），但引擎那一步缺了关键参数：

LWC v5 的 ``series.update(bar, historicalUpdate)`` 第二个参数不传时**只能**改写
“最后一根”或追加“更新的一根”，**更旧的一根会报 ``Cannot update oldest data``
被静默丢掉** ✗ —— 而回填旧根正是这种用法。
"""
import pandas as pd


# --------------------------------------------------------------------------- #
# pylightcharts：update() 要能真正改写旧根 ✓
# --------------------------------------------------------------------------- #
class _StubSeries:
    """只借用 ``SeriesCommon.update`` 需要的几个属性/方法 ✓"""

    name = 'ind'      # 不触发 rename（真实场景里指标名才在行里 ✓）
    id = 'w.s1'

    def __init__(self, times, values):
        self.data = pd.DataFrame({'time': pd.to_datetime(times),
                                  'close': values})
        self._last_bar = self.data.iloc[-1].copy()
        self.scripts = []

    def run_script(self, script):
        self.scripts.append(script)

    def _series_datetime_format(self, series, exclude_lowercase=False):
        return series

    def _is_finite_value(self, value):
        return True

    def _sync_gap_segments(self, data):
        pass

    # 真实现挂在 SeriesCommon 上 ✓（只借用它，不重建整个对象）
    from pylightcharts.abstract import SeriesCommon
    _overwrite_row = SeriesCommon._overwrite_row
    _normalize_time_column = SeriesCommon._normalize_time_column


def _update(stub, time, value, historical_update=False):
    from pylightcharts.abstract import SeriesCommon

    row = pd.Series({'time': pd.Timestamp(time), 'close': value})
    SeriesCommon.update(stub, row, historical_update)
    return stub.scripts[-1]


def test_older_bar_is_sent_with_historical_update_flag():
    """★ 更早的一根必须带第二个参数 ``true``，否则引擎会丢掉 ✗"""
    times = ['2026-01-01 09:00', '2026-01-01 09:01', '2026-01-01 09:02']
    stub = _StubSeries(times, [1.0, 2.0, 3.0])
    script = _update(stub, '2026-01-01 09:01', 22.0)
    assert script.rstrip().endswith(', true)'), script
    # mirror（self.data）里对应那一行被改掉，**长度不变** ✓
    assert len(stub.data) == 3
    assert list(stub.data['close']) == [1.0, 22.0, 3.0]
    # “最后一根”不能被回填的那根顶掉 ✓
    assert stub._last_bar['close'] == 3.0


def test_newer_bar_appends_without_flag():
    times = ['2026-01-01 09:00', '2026-01-01 09:01']
    stub = _StubSeries(times, [1.0, 2.0])
    script = _update(stub, '2026-01-01 09:02', 3.0)
    assert ', true)' not in script and ', true)' not in script
    assert len(stub.data) == 3
    assert stub._last_bar['close'] == 3.0


def test_same_bar_updates_in_place():
    times = ['2026-01-01 09:00', '2026-01-01 09:01']
    stub = _StubSeries(times, [1.0, 2.0])
    _update(stub, '2026-01-01 09:01', 2.5)
    assert len(stub.data) == 2
    assert stub._last_bar['close'] == 2.5


# --------------------------------------------------------------------------- #
# minibt：换根时确实回填上一根 + 把漏掉的多根补齐 ✓
# --------------------------------------------------------------------------- #
def _read(*parts):
    import pathlib

    return pathlib.Path(__file__).resolve().parents[1].joinpath(
        *parts).read_text(encoding='utf-8')


def test_refresh_market_backfills_previous_bar():
    """源码约束：``_refresh_market`` 回填上一根时带 ``historical=True`` ✓"""
    src = _read('minibt', 'strategy', 'realtime.py')
    start = src.index('def _refresh_market')
    body = src[start:start + 3500]
    assert 'indicator_offset=count' in body, '没有回填上一根 ✗'
    assert 'historical=True' in body
    # 新根从旧到新逐根补齐（漏掉多根时 = 更新多于 2 根 ✓）
    assert 'indicator_offset=count - 1 - j' in body
    assert 'for j in range(count):' in body


def test_on_bar_and_update_last_carry_historical_flag():
    from minibt.strategy.realtime import IndicatorManager

    class _Chart:
        def __init__(self):
            self.calls = []

        def update(self, row, historical_update=False):
            self.calls.append(historical_update)

    class _Ind:
        def __init__(self):
            self.calls = []

        def update_last(self, when, offset=0, historical=False):
            self.calls.append((offset, historical))

    class _RC:
        chart = _Chart()
        indicators = _Ind()
        _last_time = None

    from minibt.strategy.realtime import RealtimeChart

    rc = _RC()
    RealtimeChart.on_bar(rc, {'time': pd.Timestamp('2026-01-01 09:01'),
                              'close': 1.0}, indicator_offset=1,
                         historical=True)
    assert rc.chart.calls[-1] is True
    assert rc.indicators.calls[-1] == (1, True)
    RealtimeChart.on_bar(rc, {'time': pd.Timestamp('2026-01-01 09:02'),
                              'close': 2.0})
    assert rc.chart.calls[-1] is False
    assert rc.indicators.calls[-1] == (0, False)


def test_push_point_falls_back_for_old_backends():
    from minibt.strategy.realtime import IndicatorManager

    class _Modern:
        def __init__(self):
            self.seen = []

        def update(self, point, historical_update=False):
            self.seen.append(historical_update)

    class _Legacy:
        def __init__(self):
            self.seen = []

        def update(self, point):
            self.seen.append('plain')

    modern, legacy = _Modern(), _Legacy()
    IndicatorManager._push_point(modern, {'time': 1}, True)
    IndicatorManager._push_point(legacy, {'time': 1}, True)
    IndicatorManager._push_point(legacy, {'time': 2}, False)
    assert modern.seen == [True]
    assert legacy.seen == ['plain', 'plain']      # 旧后端退回普通 update ✓
