"""实时图表「切换策略 / 向前翻页后右侧数据缺失」——全量指标值缓存。

三轮修复（同一处）：

1. ``_build_value_caches``：指标值比 K 线短时**前补 NaN 对齐**，不再 ``continue``
   丢掉整条历史缓存（丢了就 ``cached_series=None`` → 只画活值 ✗）；
2. （上一轮）回写尾部只写**缓存里已有的时间戳**，避免 ``.loc[新标签] =`` 把索引
   撑乱 → 但副作用是**新 K 线永远进不了缓存** ✗✗；
3. （本轮）缓存是**开局建好就冻结**的（``_build_value_caches`` 只调一次），
   所以改为：
   * ``_write_cache_tail`` **可以追加**比缓存更晚的时间戳（更早的仍交给无限历史 ✓）；
   * ``view_values`` 用**活值尾部对齐**补上缓存没覆盖到的时间戳 ✓。

现象：切换策略后所有策略的图表**右侧一截没有数据**（K 线/成交量/指标都空）✗。
"""
import numpy as np
import pandas as pd


def _times(n, start=0):
    return pd.Index(np.arange(start, start + n) * 60, dtype='int64')


def _frame(index):
    return pd.DataFrame({'time': pd.to_datetime(index * 10 ** 9)})


def test_value_cache_aligns_length_mismatch():
    import inspect
    from minibt.strategy import realtime as mod

    src = inspect.getsource(mod.RealtimeChart._build_value_caches)
    assert 'if len(values) != len(times):' not in src
    assert 'np.full(len(times) - len(values), np.nan)' in src


# --------------------------------------------------------------------------- #
# ① view_values：缓存没覆盖到的新 K 线要用活值补上 ✓
# --------------------------------------------------------------------------- #
def test_view_values_fills_uncached_tail_with_live():
    """★ 核心回归：缓存冻结在开局，新来的 K 线必须用**活值**补上，不能是 NaN ✗"""
    from minibt.strategy import realtime as rt

    cached = pd.Series(np.arange(1000, dtype=float), index=_times(1000))
    frame = _frame(_times(1005))                 # 行情又走了 5 根
    live = np.arange(1000, 1005, dtype=float)    # 活值 = 新来的那几根

    class _Mgr(rt.IndicatorManager):
        def __init__(self):
            self.align = 'tail'

        def live_values(self, spec):
            return live

    spec = rt.IndicatorSpec(name='ma', overlap=True, values=live,
                            get_values=lambda: live)
    spec.cached_series = cached
    out = _Mgr().view_values(spec, frame)
    assert len(out) == 1005
    assert int(np.isfinite(out).sum()) == 1005, '右侧仍是 NaN ✗'
    assert list(out[-5:]) == [1000., 1001., 1002., 1003., 1004.]


def test_view_values_keeps_history_nan():
    """活值也缺的历史段必须仍是 NaN（那段由无限历史负责 ✓）"""
    from minibt.strategy import realtime as rt

    cached = pd.Series(np.full(1000, np.nan), index=_times(1000))
    cached.iloc[-3:] = [7.0, 8.0, 9.0]
    frame = _frame(_times(1000))
    live = np.array([7.0, 8.0, 9.0])             # 活值只有最后 3 根

    class _Mgr(rt.IndicatorManager):
        def __init__(self):
            self.align = 'tail'

        def live_values(self, spec):
            return live

    spec = rt.IndicatorSpec(name='ma', overlap=True, values=live,
                            get_values=lambda: live)
    spec.cached_series = cached
    out = _Mgr().view_values(spec, frame)
    assert int(np.isfinite(out).sum()) == 3
    assert list(out[-3:]) == [7.0, 8.0, 9.0]


# --------------------------------------------------------------------------- #
# ② _write_cache_tail：可以追加新时间戳（但要保持升序、不重复）✓
# --------------------------------------------------------------------------- #
def _stub(cached, specs=()):
    class _I:
        pass

    class _RC:
        def __init__(self):
            self._value_cache = {KEY: cached}
            self.indicators = _I()
            self.indicators.specs = list(specs)

    return _RC()


KEY = ('CCIStrategy', 'SHFE.ag2612_60', 'src', 'ma')


def _spec(source, name, cached):
    from minibt.strategy import realtime as rt

    spec = rt.IndicatorSpec(name=name, overlap=True, values=None)
    spec.source = source
    spec.cached_series = cached
    return spec


def test_write_cache_tail_appends_newer_timestamps():
    cached = pd.Series(np.arange(1000, dtype=float), index=_times(1000))
    spec = _spec('src', 'ma', cached)
    stub = _stub(cached, [spec])
    live = np.arange(1000, 1005, dtype=float)
    from minibt.strategy.realtime import RealtimeChart

    RealtimeChart._write_cache_tail(stub, KEY, cached, _times(1005), live)
    grown = stub._value_cache[KEY]
    assert len(grown) == 1005, (len(grown), '新 K 线没进缓存 ✗')
    assert list(grown.iloc[-5:]) == [1000., 1001., 1002., 1003., 1004.]
    assert grown.index.is_monotonic_increasing
    assert not grown.index.has_duplicates
    assert spec.cached_series is grown, '已建好的 spec 要换成新对象 ✓'


def test_write_cache_tail_updates_existing_in_place():
    """已存在的时间戳**原地更新**（不重建对象，保持引用稳定 ✓）"""
    cached = pd.Series([1.0, 2.0, 3.0], index=_times(3))
    stub = _stub(cached)
    from minibt.strategy.realtime import RealtimeChart

    RealtimeChart._write_cache_tail(stub, KEY, cached, _times(3),
                                    np.array([10., 20., 30.]))
    assert stub._value_cache[KEY] is cached
    assert list(cached) == [10., 20., 30.]
    assert len(cached) == 3


def test_write_cache_tail_never_prepends_older_timestamps():
    """比缓存**更早**的时间戳不追加（历史交给无限历史，避免打乱顺序 ✗）"""
    cached = pd.Series([5.0, 6.0], index=_times(2, start=10))
    stub = _stub(cached)
    from minibt.strategy.realtime import RealtimeChart

    RealtimeChart._write_cache_tail(stub, KEY, cached, _times(3, start=8),
                                    np.array([1., 2., 3.]))
    assert stub._value_cache[KEY] is cached
    assert len(cached) == 2 and list(cached.index) == [600, 660]


def test_sync_history_cache_uses_appending_write():
    """源码约束：``_sync_history_cache`` 走可追加的 ``_write_cache_tail`` ✓"""
    import inspect
    from minibt.strategy import realtime as mod

    src = inspect.getsource(mod.RealtimeChart._sync_history_cache)
    assert '_write_cache_tail(' in src
    assert '_cached_tail_labels(' not in src
    assert 'cached.loc[times[-n:]] = live[-n:]' not in src


# --------------------------------------------------------------------------- #
# ③ 切合约/切策略要清掉“上一根 K 线时间”的记忆 ✓
# --------------------------------------------------------------------------- #
def test_set_contract_resets_last_bar_time():
    """★ 回归：不清 ``_last_time`` 的话，新合约时间更早就再也推不上 K 线 ✗

    （``chart.update(旧时间)`` 会被 LWC 静默拒绝 → 右侧一截没有 K 线/成交量 ✗）
    """
    src = __import__('pathlib').Path(__file__).resolve().parents[1].joinpath(
        'minibt', 'strategy', 'realtime.py').read_text(encoding='utf-8')
    start = src.index('def set_contract(contract: str, force: bool = False)')
    body = src[start:start + 4000]
    assert 'self._last_time = None' in body, '切合约没清 _last_time ✗'
    assert body.index('self._stop_history()') < body.index('self._last_time = None')
