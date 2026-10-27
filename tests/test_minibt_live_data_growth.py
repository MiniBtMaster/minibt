"""实盘「新 K 线的指标值全是同一个固定值」—— KLine 长度缓存导致指标登记被拒 ✗。

根因链（用户反馈：初始化时到第 1000 根，之后 1001~1009 的指标值是固定值，
只有最新一根在动）：

1. 实盘 ``_execute_live_trading()`` → ``kline._inplace_values()`` 把数据
   **原地加长**（不经过 ``add_data`` / ``update_values`` → 不会清缓存 ✗）；
2. ``KLinesSet.lengths`` / ``max_length`` 是**缓存**的 → 一直返回**初始化时**
   的长度 ✗；
3. ``Strategy.__setattr__`` 用 ``len(ind) in self._btklinedataset.lengths``
   判断“这个指标该不该登记” → 长度对不上 → **新指标永远登记不进去** ✗；
4. 图表端 ``_indicator_values(key)`` 每次按 key 现取 → 拿到的还是**初始化那一刻**
   的指标对象 → 那一段全是同一个固定值 ✗。
"""
import numpy as np
import pandas as pd


def _strategy():
    from minibt import LocalDatas
    from minibt.utils import Config
    import minibt.btplot as btp

    k = LocalDatas.test.kline
    strat = btp._make_step_strategy(k, [k.sma(length=5)],
                                    Config(theme='dark'), 'X')
    strat._start_strategy_run()
    return k, strat


def _grow(kline, *, close_delta: float = 5.0):
    """模拟实盘：K 线**原地**长出一根（同 ``_inplace_values`` 的写法 ✓）。"""
    df = kline.pandas_object
    last = df.iloc[[-1]].copy()
    last['datetime'] = (pd.to_datetime(df['datetime'].iloc[-1])
                        + pd.Timedelta(minutes=1))
    close = float(df['close'].iloc[-1]) + close_delta
    last['close'] = close
    last['high'] = close + 1
    last['low'] = close - 1
    kline._update_replace(pd.concat([df, last], ignore_index=True))
    return close


def test_lengths_follows_inplace_growth():
    """★ ``KLinesSet.lengths`` / ``max_length`` 不能是**初始化时的**缓存 ✗"""
    k, strat = _strategy()
    before = list(strat._btklinedataset.lengths)
    assert before, before

    _grow(k)
    after = list(strat._btklinedataset.lengths)
    assert after == [n + 1 for n in before], (before, after)
    assert strat._btklinedataset.max_length == max(after)
    assert len(k.pandas_object) == max(after)


def test_rebuilt_indicator_replaces_dataset_entry():
    """★ 数据长起来后重建指标，必须**替换**掉 ``_btindicatordataset`` 里的旧对象 ✓

    修复前：``len(new) not in lengths``（lengths 是旧缓存）→ 登记被 `if` 挡掉 ✗
    → 图表每次按 key 现取拿到的还是初始化那一刻的对象 → 值一片固定 ✗
    """
    k, strat = _strategy()
    old = strat._btindicatordataset['pta_sma']

    for step in range(1, 4):
        close = _grow(k, close_delta=step * 5.0)
        strat._in_next_context = False          # ≈ _execute_live_trading 里的设置
        strat.pta_sma = k.sma(length=5)         # ≈ 用户 __init__ 里重建指标
        now = strat._btindicatordataset['pta_sma']
        assert now is not old, '新指标没登记进去（还是初始化那个对象）✗'
        old = now
        values = np.asarray(now._get_plot_datas('pta_sma')[8],
                            dtype=float).ravel()
        assert len(values) == len(k.pandas_object), (len(values),
                                                     len(k.pandas_object))
        # 最后一根的 5 均线要跟着新收盘价走（不是初始化时的常数 ✗）
        expected = float(k.pandas_object['close'].iloc[-5:].mean())
        assert abs(float(values[-1]) - expected) < 1e-6, (values[-1], expected,
                                                          close)


def test_registration_tolerates_one_bar_race():
    """指标长度与 K 线差一根（重算时机 / 预热窗口）也不能拒收 ✗"""
    import inspect
    from minibt.strategy import strategy as mod

    src = inspect.getsource(mod.Strategy.__setattr__)
    assert '_klens = self._btklinedataset.lengths' in src
    assert 'abs(len(value) - n) <= 1' in src


def test_lengths_property_is_computed_live():
    """源码约束：``lengths`` / ``max_length`` 不许再走 ``_*_cache`` ✓"""
    import inspect
    from minibt.utils import KLinesSet

    for name in ('lengths', 'max_length'):
        src = inspect.getsource(getattr(KLinesSet, name).fget)
        assert '_cache' not in src, name
