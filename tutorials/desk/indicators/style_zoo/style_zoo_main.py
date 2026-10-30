# -*- coding: utf-8 -*-
"""StyleZoo_Main — **主图样式**测试指标（minibt desk 看盘 / 本地图表）

一个指标把主图能用的 `minibt.utils.PlotInfo` 样式全用一遍：

| 样式 | 用法 | 图上应该看到 |
| --- | --- | --- |
| `linestyle` | 6 条 MA，各用一种 `LineDash` + 不同 `line_width` | 实线 / 虚线 / 点线 / 点划线 / 稀疏点 / 长虚线，线宽 1~3 |
| `linestyle.price_line` | 只有 `ma_solid` 开 | 右侧一条横向价格线 |
| `linestyle.price_label` | 全部开 | 右侧轴上一排价格标签 |
| `bandstyle` | `env_upper` / `env_lower` 之间 | 半透明色带 |
| `legend` | `env_lower=False` | 该线**不出图例行**（线还在） |
| `signalstyle` | `long_signal` / `short_signal` + `set_label('买'/'卖')` | 主图绿↑ / 红↓ 箭头 + **文字** |
| `watermark` | `WaterMark('STYLE ZOO')` | 图表中央大水印 |

交易信号**故意稀疏**：慢线用 3 倍周期 + 90 根冷却 → 5 分钟图上一天 1~2 个箭头。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from minibt import BtIndicator
from minibt.utils import (
    BandStyle, Colors, LineDash, LineStyle, Markers, SignalStyle, WaterMark,
)

COLORS = ('#f6c343', '#2196f3', '#e91e63', '#26a69a',
          '#9c27b0', '#ff9800', '#00bcd4')


def _sma(values: np.ndarray, length: int) -> np.ndarray:
    return pd.Series(values).rolling(max(1, int(length))).mean().to_numpy()


def _sparse_signals(fast: np.ndarray, slow: np.ndarray,
                    cooldown: int = 90) -> dict:
    """交叉 → 稀疏信号（冷却期内不再出信号 ✓）"""
    size = len(fast)
    long_sig = np.zeros(size, dtype=float)
    short_sig = np.zeros(size, dtype=float)
    last = -10 ** 9
    holding = 0
    cooldown = max(1, int(cooldown))
    for index in range(1, size):
        a0, a1 = fast[index - 1], fast[index]
        b0, b1 = slow[index - 1], slow[index]
        if not np.isfinite([a0, a1, b0, b1]).all():
            continue
        up = a0 <= b0 and a1 > b1
        down = a0 >= b0 and a1 < b1
        if not (up or down) or index - last < cooldown:
            continue
        last = index
        if up:
            long_sig[index] = 1.0
            holding = 1
        else:
            short_sig[index] = 1.0
            holding = -1
    void = holding
    return {'long': long_sig, 'short': short_sig, 'holding': void}


class StyleZoo_Main(BtIndicator):
    """主图样式大全（线型 / 线宽 / 色带 / 价格线 / 水印 / 带文字的信号箭头）"""

    lines = ('ma_solid', 'ma_dashed', 'ma_dotted', 'ma_dashdot',
             'ma_sparse', 'ma_large', 'env_upper', 'env_lower',
             'long_signal', 'short_signal')
    params = dict(length=20, band=2.0, cooldown=90)
    overlap = True

    linestyle = dict(
        ma_solid=LineStyle(line_color=COLORS[0], line_width=2),
        ma_dashed=LineStyle(line_color=COLORS[1], line_width=2,
                            line_dash=LineDash.dashed, price_line=False),
        ma_dotted=LineStyle(line_color=COLORS[2], line_width=2,
                            line_dash=LineDash.dotted, price_line=False),
        ma_dashdot=LineStyle(line_color=COLORS[3], line_width=2,
                             line_dash=LineDash.dotdash, price_line=False),
        ma_sparse=LineStyle(line_color=COLORS[4], line_width=1,
                            line_dash=LineDash.sparse_dotted,
                            price_line=False),
        ma_large=LineStyle(line_color=COLORS[5], line_width=3,
                           line_dash=LineDash.large_dashed, price_line=False),
        env_upper=LineStyle(line_color=COLORS[6], line_width=1,
                            price_line=False, price_label=False),
        env_lower=LineStyle(line_color=COLORS[6], line_width=1,
                            price_line=False, price_label=False),
    )

    #: `set_label(...)` → 箭头旁边显示文字（`SignalStyle.label` ✓）
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.lime, Markers.triangle,
                                size=16).set_label('买', 12, color='#26a69a'),
        short_signal=SignalStyle('high', Colors.tomato,
                                 Markers.inverted_triangle,
                                 size=16).set_label('卖', 12, color='#ef5350'),
    )

    bandstyle = [BandStyle(lower='env_lower', upper='env_upper',
                           fill_color=COLORS[6], fill_alpha=0.30)]

    #: 逐线隐藏图例：`env_lower` 只画线、不出图例行 ✓
    legend = dict(env_lower=False)

    #: 图表水印（desk 已支持 ✓）
    watermark = WaterMark(text='STYLE ZOO', font_size=40)

    def next(self):
        close = np.asarray(self.close.values, dtype=float)
        base = max(2, int(self.params.length))
        mas = [_sma(close, base + index * 8) for index in range(6)]
        spread = _sma(np.abs(np.diff(close, prepend=close[0])), 50) \
            * float(self.params.band) * 6
        signals = _sparse_signals(mas[0], _sma(close, base * 3),
                                  cooldown=int(self.params.cooldown))
        return (*mas, mas[0] + spread, mas[0] - spread,
                signals['long'], signals['short'])
