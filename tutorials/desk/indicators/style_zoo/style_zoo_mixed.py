# -*- coding: utf-8 -*-
"""StyleZoo_Mixed — **主图 + 副图混排**测试指标

| 样式 | 用法 | 图上应该看到 |
| --- | --- | --- |
| `overlap` 逐线 | `dict(trend=True, gain=False)` | `trend` 在主图、`gain` 在副图 |
| `linestyle` | 粗长虚线 / 细实线 | 主图橙色长虚线 + 副图绿色实线 |
| `signalstyle` | `exitlong_signal` / `exitshort_signal` | 主图橙/蓝**圆形**标记 + 文字 |

信号同样是**低频**（冷却 110 根），一屏可能只有一两个点 ✓
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from minibt import BtIndicator
from minibt.utils import Colors, LineDash, LineStyle, Markers, SignalStyle


def _sma(values: np.ndarray, length: int) -> np.ndarray:
    return pd.Series(values).rolling(max(1, int(length))).mean().to_numpy()


def _sparse(fast: np.ndarray, slow: np.ndarray, cooldown: int = 110) -> dict:
    size = len(fast)
    out = {'long': np.zeros(size), 'short': np.zeros(size),
           'exitlong': np.zeros(size), 'exitshort': np.zeros(size)}
    last = -10 ** 9
    holding = 0
    for index in range(1, size):
        a0, a1 = fast[index - 1], fast[index]
        b0, b1 = slow[index - 1], slow[index]
        if not np.isfinite([a0, a1, b0, b1]).all():
            continue
        if index - last < max(1, int(cooldown)):
            continue
        if a0 <= b0 and a1 > b1:
            if holding < 0:
                out['exitshort'][index] = 1.0
            out['long'][index] = 1.0
            holding = 1
        elif a0 >= b0 and a1 < b1:
            if holding > 0:
                out['exitlong'][index] = 1.0
            out['short'][index] = 1.0
            holding = -1
        else:
            continue
        last = index
    return out


class StyleZoo_Mixed(BtIndicator):
    """同一指标里：趋势线画主图、振荡线画副图 + 圆形离场标记"""

    lines = ('trend', 'gain', 'exitlong_signal', 'exitshort_signal')
    params = dict(length=34, cooldown=110)
    #: 逐线 `overlap`：True → 主图 / False → 副图 ✓
    overlap = dict(trend=True, gain=False)

    linestyle = dict(
        trend=LineStyle(line_color='#00bcd4', line_width=3,
                        line_dash=LineDash.large_dashed),
        gain=LineStyle(line_color='#8bc34a', line_width=2),
    )

    signalstyle = dict(
        exitlong_signal=SignalStyle('high', Colors.orange, Markers.circle,
                                    size=14).set_label('平多', 11,
                                                       color='#ff9800'),
        exitshort_signal=SignalStyle('low', Colors.blue, Markers.circle,
                                     size=14).set_label('平空', 11,
                                                        color='#2196f3'),
    )

    def next(self):
        close = np.asarray(self.close.values, dtype=float)
        trend = _sma(close, self.params.length)
        gain = np.clip((close / np.where(trend == 0, np.nan, trend) - 1.0)
                       * 1000.0 + 50.0, 0.0, 100.0)
        signals = _sparse(trend, _sma(close, int(self.params.length) * 4),
                          cooldown=int(self.params.cooldown))
        return trend, gain, signals['exitlong'], signals['exitshort']
