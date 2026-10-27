"""``SMTDivergences`` 对比合约的对齐（**时间轴** ✓ / 尾部兜底）。

回归背景：以前 ``_sym_hl`` 只按**位置**取尾部 ``sym.high[-n:]`` —— 两侧根数或
起始时间不同时会整体错位，甚至两个**时间完全不重叠**的合约都能“算出”背离 ✗。
"""
import numpy as np
import pandas as pd


def test_sym_hl_aligns_by_timestamp():
    """给了时间轴 → 按**时间**取（不是按位置）✓"""
    from minibt import LocalDatas
    from minibt.indicators.tradingview import SMTDivergences

    k = LocalDatas.pp2609_60.kline
    sym = LocalDatas.l2609_60.kline
    times = np.asarray(k.pandas_object['datetime'])[-5:]
    hh, ll = SMTDivergences._sym_hl(sym, 5, times)

    index = pd.DatetimeIndex(pd.to_datetime(sym.pandas_object['datetime']))
    want = index.get_indexer(pd.DatetimeIndex(pd.to_datetime(times)))
    assert len(hh) == 5
    assert np.allclose(hh, np.asarray(sym.high, dtype=float)[want])
    assert np.allclose(ll, np.asarray(sym.low, dtype=float)[want])


def test_sym_hl_falls_back_to_tail_without_times():
    """没给时间轴 / 指标为 None → 老行为（尾部对齐 / None）✓"""
    from minibt import LocalDatas
    from minibt.indicators.tradingview import SMTDivergences

    sym = LocalDatas.pp2609_60.kline
    hh, ll = SMTDivergences._sym_hl(sym, 4)
    assert np.allclose(hh, np.asarray(sym.high, dtype=float)[-4:])
    assert np.allclose(ll, np.asarray(sym.low, dtype=float)[-4:])
    assert SMTDivergences._sym_hl(None, 4) is None


def test_sym_hl_unmatched_times_become_nan():
    """时间对不上的根 → NaN（**不是**错位去比 ✗）"""
    from minibt import LocalDatas
    from minibt.indicators.tradingview import SMTDivergences

    k = LocalDatas.pp2609_60.kline
    other = LocalDatas.test.kline               # 2025 年，与 2026 完全不重叠
    times = np.asarray(k.pandas_object['datetime'])[-100:]
    hh, ll = SMTDivergences._sym_hl(other, 100, times)
    assert len(hh) == 100
    assert not np.isfinite(hh).any(), '时间对不上却取到了值 ✗'
    assert not np.isfinite(ll).any()


def test_no_bogus_divergences_for_disjoint_contracts():
    """★ 回归：时间完全不重叠的两个合约不该“算出”任何背离 ✗

    修复前：``div_high`` 30 个、``div_low`` 80 个（全是错位比出来的垃圾 ✗）。
    """
    from minibt import LocalDatas

    k = LocalDatas.pp2609_60.kline
    ind = k.tradingview.SMTDivergences(sym1=LocalDatas.test.kline)
    for name in ('div_high', 'div_low'):
        values = np.asarray(ind.pandas_object[name], dtype=float)
        assert not np.isfinite(values).any(), (name, int(np.isfinite(values).sum()))


def test_aligned_contract_keeps_previous_result():
    """★ 回归：时间轴一致时结果与老的「尾部对齐」**完全相同**（784 / 519）✓"""
    from minibt import LocalDatas

    k = LocalDatas.pp2609_60.kline
    sym = LocalDatas.l2609_60.kline
    kt = pd.to_datetime(k.pandas_object['datetime'])
    st = pd.to_datetime(sym.pandas_object['datetime'])
    assert len(kt) == len(st) and bool((kt.values == st.values).all())

    ind = k.tradingview.SMTDivergences(sym1=sym)
    dh = np.asarray(ind.pandas_object['div_high'], dtype=float)
    dl = np.asarray(ind.pandas_object['div_low'], dtype=float)
    assert int(np.isfinite(dh).sum()) == 784
    assert int(np.isfinite(dl).sum()) == 519
    # wrapper 的动态开关照旧：传了对比合约 → 不画 pivot ✓
    assert ind.isplot['pivot_high'] is False
    assert ind.isplot['div_high'] is True
