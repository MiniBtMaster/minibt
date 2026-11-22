"""``minibt.zigzag.core`` 的**纯 Python 兜底实现**。

为什么需要它
-----------
``zigzag/core.pyx`` 会被 ``setup.py`` 编成扩展模块
``minibt.zigzag.core``（产物名形如 ``core.cp312-win_amd64.pyd``）。
Python 的导入优先级是 **扩展模块 > 源码**，所以：

* 编好了 ``.pyd`` / ``.so`` → 用 Cython 版本（快）✓
* 没编（换了 Python 小版本、或者就地跑源码）→ 用本文件的纯 Python 版本 ✓

历史包袱
--------
本文件以前是一段 ``__bootstrap__()`` 引导代码，里面**硬编码了**
``core.cp312-win_amd64.pyd`` 这个文件名 ——

* 在 3.13 / 3.14 上必然 ``ImportError``（文件名对不上）；
* 还依赖已经被 setuptools 弃用的 ``pkg_resources``；
* 而且它**永远不会**走纯 Python 分支（一旦 import 失败就整包崩）。

现在改成纯 Python 实现，等价于 ``core.pyx`` 的算法（逐值一致）。
"""
from __future__ import annotations

import numpy as np

__all__ = [
    'PEAK',
    'PURE_PYTHON',
    'VALLEY',
    'compute_segment_returns',
    'identify_initial_pivot',
    'max_drawdown',
    'max_drawdown_c',
    'peak_valley_pivots',
    'peak_valley_pivots_detailed',
    'pivots_to_modes',
]

#: 标记：当前用的是纯 Python 兜底（有 pyd 时这个模块根本不会被加载 ✓）
PURE_PYTHON = True

PEAK = 1
VALLEY = -1


def _to_ndarray(X):
    """任意序列 → ``float64`` ndarray（和 ``core.pyx`` 的 ``_to_ndarray`` 等价）"""
    if isinstance(X, np.ndarray):
        array = X
    elif hasattr(X, 'to_numpy'):                    # pandas Series / Index
        array = X.to_numpy()
    elif isinstance(X, (list, tuple)):
        array = np.asarray(X)
    else:
        array = np.asarray(X)
    if not str(array.dtype).startswith('float'):
        array = array.astype(np.float64)
    return np.ascontiguousarray(array, dtype=np.float64)


def identify_initial_pivot(X, up_thresh: float, down_thresh: float) -> int:
    """判断序列的第一个转折是峰（``PEAK``）还是谷（``VALLEY``）✓"""
    array = _to_ndarray(X)
    if array.size == 0:
        raise ValueError('identify_initial_pivot: 序列不能为空')
    x_0 = array[0]
    max_x = min_x = x_0
    max_t = min_t = 0
    up_thresh = float(up_thresh) + 1.0
    down_thresh = float(down_thresh) + 1.0
    for t in range(1, array.size):
        x_t = array[t]
        if x_t / min_x >= up_thresh:
            return VALLEY if min_t == 0 else PEAK
        if x_t / max_x <= down_thresh:
            return PEAK if max_t == 0 else VALLEY
        if x_t > max_x:
            max_x, max_t = x_t, t
        if x_t < min_x:
            min_x, min_t = x_t, t
    t_n = array.size - 1
    return VALLEY if x_0 < array[t_n] else PEAK


def peak_valley_pivots_detailed(X, up_thresh: float, down_thresh: float,
                                limit_to_finalized_segments: bool = True,
                                use_eager_switching_for_non_final: bool = False):
    """找到峰 / 谷（0 = 非转折点，1 = 峰，-1 = 谷）✓"""
    array = _to_ndarray(X)
    if down_thresh > 0:
        raise ValueError('The down_thresh must be negative.')
    if array.size == 0:
        return np.zeros(0, dtype=np.int64)

    initial_pivot = identify_initial_pivot(array, up_thresh, down_thresh)
    t_n = array.size
    pivots = np.zeros(t_n, dtype=np.int64)
    trend = -initial_pivot
    last_pivot_t = 0
    last_pivot_x = array[0]
    pivots[0] = initial_pivot

    up = float(up_thresh) + 1.0
    down = float(down_thresh) + 1.0
    for t in range(1, t_n):
        x = array[t]
        r = x / last_pivot_x
        if trend == -1:
            if r >= up:
                pivots[last_pivot_t] = trend
                trend = PEAK
                last_pivot_x = x
                last_pivot_t = t
            elif x < last_pivot_x:
                last_pivot_x = x
                last_pivot_t = t
        else:
            if r <= down:
                pivots[last_pivot_t] = trend
                trend = VALLEY
                last_pivot_x = x
                last_pivot_t = t
            elif x > last_pivot_x:
                last_pivot_x = x
                last_pivot_t = t

    if limit_to_finalized_segments:
        if use_eager_switching_for_non_final:
            if 0 < last_pivot_t < t_n - 1:
                pivots[last_pivot_t] = trend
                pivots[t_n - 1] = -trend
            else:
                pivots[t_n - 1] = trend
        else:
            if last_pivot_t == t_n - 1:
                pivots[last_pivot_t] = trend
            elif pivots[t_n - 1] == 0:
                pivots[t_n - 1] = -trend
    return pivots


def peak_valley_pivots(X, up_thresh: float, down_thresh: float):
    """``peak_valley_pivots_detailed`` 的简化入口（默认口径）✓"""
    return peak_valley_pivots_detailed(X, up_thresh, down_thresh, True, False)


def max_drawdown_c(X) -> float:
    """最大回撤（严格递增 → 0）✓"""
    array = np.ascontiguousarray(np.asarray(X, dtype=np.float64))
    if array.size == 0:
        return 0.0
    peak = float(array[0])
    mdd = 0.0
    for value in array:
        x = float(value)
        peak = max(peak, x)
        dd = (peak - x) / peak
        mdd = max(mdd, dd)
    return mdd if mdd != 0.0 else 0.0


def max_drawdown(X) -> float:
    """``max_drawdown_c`` 的通用入口（自动转 float64）✓"""
    return max_drawdown_c(_to_ndarray(X))


def pivots_to_modes(pivots):
    """峰谷序列 → 趋势模式（峰到谷 = -1，谷到峰 = +1）✓"""
    array = np.ascontiguousarray(np.asarray(pivots, dtype=np.int64))
    if array.size == 0:
        return np.zeros(0, dtype=np.int64)
    modes = np.zeros(array.size, dtype=np.int64)
    mode = -int(array[0])
    modes[0] = array[0]
    for t in range(1, array.size):
        x = int(array[t])
        if x != 0:
            modes[t] = mode
            mode = -x
        else:
            modes[t] = mode
    return modes


def compute_segment_returns(X, pivots):
    """相邻转折点之间的收益（``pivot_to_pivot``）✓"""
    array = _to_ndarray(X)
    pivots = np.asarray(pivots)
    points = array[pivots != 0]
    if points.size < 2:
        return np.zeros(0, dtype=np.float64)
    return points[1:] / points[:-1] - 1.0
