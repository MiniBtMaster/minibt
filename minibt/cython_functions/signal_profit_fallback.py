"""``calc_signal_profit`` / ``calc_single_signal_profit`` 的**纯 Python 兜底**。

只有在 Cython 扩展 ``minibt.cython_functions.signal_profit`` 不可用时才会被
:func:`minibt.cython_functions.load` 加载（例如换到 3.13 / 3.14 且还没编 pyd）。

算法与 ``signal_profit.pyx`` **逐值一致**（同一套循环，只是挪到 numpy/Python 层）：

* 初始 ``profit = 1.0``；
* 多头：``profit *= 1 + (current - open) / open``；
* 空头：``profit *= 1 + (open - current) / open``；
* ``open`` = 信号出现那根的收盘价（固定），``current`` = 逐根推进的收盘价。
"""
from __future__ import annotations

import numpy as np

__all__ = ['PURE_PYTHON', 'calc_signal_profit', 'calc_single_signal_profit']

#: 标记：说明当前走的是纯 Python 兜底（排查 / 日志用 ✓）
PURE_PYTHON = True


def _as_float_array(values) -> np.ndarray:
    array = np.ascontiguousarray(np.asarray(values, dtype=np.float64).ravel())
    return array


def calc_signal_profit(signals, close, bars):
    """根据交易信号计算持仓 N 根后的收益（**纯 Python 版**）✓

    Args:
        signals: 信号数组（0 = 无信号，>0 = 多头，<0 = 空头）
        close: 收盘价数组
        bars: 持仓根数列表（如 ``[3, 5, 10]``）

    Returns:
        dict：``long_profits`` / ``short_profits`` / ``signal_indices`` /
        ``signal_directions`` / ``cum_profit`` / ``bars``
    """
    signal_arr = _as_float_array(signals)
    close_arr = _as_float_array(close)
    bars = [int(value) for value in (bars or [])]
    n = int(signal_arr.size)
    m = len(bars)

    signal_indices = np.flatnonzero(signal_arr != 0).astype(np.int64).tolist()
    signal_directions = [1 if signal_arr[index] > 0 else -1
                         for index in signal_indices]
    num_signals = len(signal_indices)

    if not num_signals:
        return {
            'long_profits': np.zeros((0, m), dtype=np.float64),
            'short_profits': np.zeros((0, m), dtype=np.float64),
            'signal_indices': [],
            'signal_directions': [],
            'cum_profit': [],
            'bars': bars,
        }

    long_profits = np.zeros((num_signals, m), dtype=np.float64)
    short_profits = np.zeros((num_signals, m), dtype=np.float64)

    for j, sig_idx in enumerate(signal_indices):
        open_price = close_arr[sig_idx]
        if not np.isfinite(open_price) or open_price <= 0:
            long_profits[j, :] = np.nan
            short_profits[j, :] = np.nan
            continue
        for k, bar_hold in enumerate(bars):
            end_idx = min(sig_idx + bar_hold, n - 1)
            window = close_arr[sig_idx + 1:end_idx + 1]
            window = window[np.isfinite(window)]
            if window.size:
                long_factors = 1.0 + (window - open_price) / open_price
                short_factors = 1.0 + (open_price - window) / open_price
                long_profits[j, k] = float(np.prod(long_factors))
                short_profits[j, k] = float(np.prod(short_factors))
            else:
                long_profits[j, k] = 1.0
                short_profits[j, k] = 1.0

    cum_profit_list: list[np.ndarray] = []
    for k, bar_hold in enumerate(bars):
        cum_profit = np.full(n, np.nan, dtype=np.float64)
        cum_value = 1.0
        last_idx = -1
        for j, sig_idx in enumerate(signal_indices):
            direction = signal_directions[j]
            if last_idx + 1 < sig_idx:
                cum_profit[last_idx + 1:sig_idx] = cum_value
            settle_idx = min(sig_idx + bar_hold, n - 1)
            if direction == 1:
                cum_value = long_profits[j, k]
            else:
                cum_value = short_profits[j, k]
            next_sig_idx = (signal_indices[j + 1]
                            if j + 1 < num_signals else n)
            end_fill = min(settle_idx, next_sig_idx - 1)
            if settle_idx <= end_fill:
                cum_profit[settle_idx:end_fill + 1] = cum_value
            last_idx = end_fill
        if last_idx + 1 < n:
            cum_profit[last_idx + 1:] = cum_value
        cum_profit_list.append(cum_profit)

    return {
        'long_profits': long_profits,
        'short_profits': short_profits,
        'signal_indices': signal_indices,
        'signal_directions': signal_directions,
        'cum_profit': cum_profit_list,
        'bars': bars,
    }


def calc_single_signal_profit(signal, close, bar_hold):
    """单个信号的收益（``bar_hold`` 是标量）✓"""
    bar_hold = int(bar_hold)
    result = calc_signal_profit(signal, close, [bar_hold])
    return {
        'long_profits': result['long_profits'],
        'short_profits': result['short_profits'],
        'signal_indices': result['signal_indices'],
        'signal_directions': result['signal_directions'],
        'cum_profit': result['cum_profit'] if result['cum_profit'] else [],
        'bars': [bar_hold],
    }
