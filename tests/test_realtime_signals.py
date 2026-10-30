"""实时图「交易信号/信号文本在新 K 线后突然消失且不再显示」✗。

根因链：

1. 图表 mirror 的 ``time`` 列在第一次 ``update()`` 之后会因写进 float
   （``1760712900.0``）退化成 ``object`` dtype ✗；
2. ``IndicatorManager._frame_seconds`` 只在 ``is_numeric_dtype`` 时按**秒**处理，
   否则走 ``pd.to_datetime(...)`` —— 而 pandas 把**数字**当**纳秒**解释 ✗ →
   时间轴变成 ``[1, 1]`` ✗；
3. 信号值是按这个时间轴从 ``_value_cache`` 里 ``reindex`` 出来的 → 命中 **0/N**
   → 整条信号变 NaN ✗；
4. ``SignalManager.update`` 对**已存在**的序列照发 ``series.set(空)`` ✗ →
   标记/文本整段被清掉；此后每一拍都算出空 → **再也回不来** ✗。
"""
import numpy as np
import pandas as pd


def _frame(seconds):
    return pd.DataFrame({'time': seconds, 'open': 1.0, 'high': 1.0,
                         'low': 1.0, 'close': 1.0, 'volume': 1.0})


# --------------------------------------------------------------------------- #
# ① _frame_seconds：object 列里的“秒”不能被当纳秒 ✗
# --------------------------------------------------------------------------- #
def test_frame_seconds_handles_object_epoch_seconds():
    """★ 核心回归：``time`` 列退化成 object（混 int/float）也要当**秒** ✓"""
    from minibt.strategy.realtime import IndicatorManager

    ints = IndicatorManager._frame_seconds(_frame([1760712300, 1760712600]))
    mixed = IndicatorManager._frame_seconds(
        _frame(pd.Series([1760712300, 1760712600.0, 1760712900.0],
                         dtype=object)))
    assert list(ints) == [1760712300, 1760712600]
    assert list(mixed) == [1760712300, 1760712600, 1760712900], \
        'object 列被当成纳秒了 ✗（时间轴会变成 1）'
    # 真正的日期字符串仍然按日期解析 ✓
    dates = IndicatorManager._frame_seconds(
        _frame(['2026-06-03 09:00:00', '2026-06-03 09:01:00']))
    assert dates[1] - dates[0] == 60


def test_frame_seconds_numeric_unchanged():
    from minibt.strategy.realtime import IndicatorManager

    out = IndicatorManager._frame_seconds(_frame(np.array([10, 70], dtype='int64')))
    assert list(out) == [10, 70]


# --------------------------------------------------------------------------- #
# ② 已有信号序列不能被空 payload 清掉 ✗
# --------------------------------------------------------------------------- #
class _Series:
    def __init__(self):
        self.calls = []

    def set(self, data, shapes=None):
        self.calls.append(0 if data is None else len(data))

    def delete(self):
        self.calls.append('deleted')


def test_empty_payload_then_recovery():
    """空 payload 会清掉（合法：信号真的全没了 ✓），但**能恢复** ✓

    用户遇到的“消失后不再显示”根因是时间轴被解析错 → 之后每一拍都算出空 ✗；
    ``_frame_seconds`` 修好后下一拍就会重新 set 回来 ✓。
    """
    from minibt.strategy.realtime import SignalManager

    class _Chart:
        def add_custom_series(self, **kwargs):
            raise AssertionError('不该新建 ✗')

    manager = SignalManager(_Chart(), align='tail')
    series = _Series()
    manager.series = {'long_signal': series}
    manager._panes = {'long_signal': 0}
    frame = _frame(np.arange(60, 60 * 6, 60))

    manager.update(frame, [('long_signal', np.zeros(5), {}, None, 0)])
    assert series.calls == [0]                  # 空 → 清掉（合法 ✓）

    values = np.zeros(5)
    values[-1] = 1.0
    manager.update(frame, [('long_signal', values, {}, None, 0)])
    assert series.calls[-1] > 0, '恢复不回来 ✗'


def test_missing_signal_series_is_still_deleted():
    """信号维度变了（换指标）仍然要删掉对应序列 ✓（别把这条老的清理也弄丢）"""
    from minibt.strategy.realtime import SignalManager

    class _Chart:
        def add_custom_series(self, **kwargs):
            raise AssertionError('不该新建 ✗')

    manager = SignalManager(_Chart(), align='tail')
    old = _Series()
    manager.series = {'gone': old}
    manager._panes = {'gone': 0}
    manager.update(_frame(np.arange(60, 60 * 6, 60)), [])
    assert old.calls == ['deleted']


# --------------------------------------------------------------------------- #
# ③ 缓存按时间全落空时要退回活值 ✓
# --------------------------------------------------------------------------- #
def test_refresh_signals_falls_back_to_live_values():
    """源码约束：``reindex`` 全 NaN 时必须退回**活值尾部对齐** ✓

    （否则整条信号变 NaN → 被清掉且再也回不来 ✗）
    """
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / 'minibt' /
           'strategy' / 'realtime.py').read_text(encoding='utf-8')
    start = src.index('def _refresh_signals')
    body = src[start:start + 2200]
    assert 'not np.isfinite(got).any()' in body
    assert "_align_values(values, len(frame), 'tail')" in body


# --------------------------------------------------------------------------- #
# ④ mirror 的 time 列及时归一化 ✓
# --------------------------------------------------------------------------- #
def test_normalize_time_column_casts_object_back_to_int():
    from pylightcharts.abstract import SeriesCommon

    class _Stub:
        data = pd.DataFrame({'time': pd.Series(
            [1760712300, 1760712600.0], dtype=object), 'close': [1.0, 2.0]})

        _normalize_time_column = SeriesCommon._normalize_time_column

    stub = _Stub()
    stub._normalize_time_column()
    assert stub.data['time'].dtype == 'int64', stub.data['time'].dtype
    assert list(stub.data['time']) == [1760712300, 1760712600]
