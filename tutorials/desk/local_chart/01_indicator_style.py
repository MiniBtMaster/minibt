"""01 · 本地图表指标 + PlotInfo 样式

在 minibt desk 的「本地图表」里打开一个 CSV，然后在编辑器打开本文件，
点「加到图表」：当前格子会按 CSV 重算这个指标。

演示：
* 两条均线 + 上下包络 → `bandstyle` 色带
* 实线 / 虚线 / 点划线 / 线宽 → `linestyle`
* 金叉 / 死叉 → `signalstyle` 箭头 + 固定文字
* 右上角统计表 → `tablestyle`
* 图表水印 → `watermark`

注意：指标类只在 `next()` 里返回与 `lines` **数量、顺序一致**的列。
"""
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import numpy as np
import pandas as pd

from minibt import *
from minibt.utils import TableStyle


class LocalStyleDemo(BtIndicator):
    """本地图表样式演示：均线 + 色带 + 信号箭头 + 表格 + 水印。"""

    lines = ('ma_fast', 'ma_slow', 'env_upper', 'env_lower',
             'long_signal', 'short_signal')
    params = dict(fast=10, slow=30, band=2.0, cooldown=60)
    overlap = True

    linestyle = dict(
        ma_fast=LineStyle(line_color='#f6c343', line_width=2),
        ma_slow=LineStyle(line_color='#2196f3', line_width=2,
                          line_dash=LineDash.dashed),
        env_upper=LineStyle(line_color='#ff9800', line_width=1,
                            line_dash=LineDash.dotdash,
                            price_line=False, price_label=False),
        env_lower=LineStyle(line_color='#ff9800', line_width=1,
                            line_dash=LineDash.dotdash,
                            price_line=False, price_label=False),
    )

    #: 上下包络之间填半透明色带 ✓
    bandstyle = [
        BandStyle(lower='env_lower', upper='env_upper',
                  fill_color='#ff9800', fill_alpha=0.18),
    ]

    #: 信号箭头：low = 画在 K 线下方，high = 画在上方 ✓
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.lime, Markers.arrow_up,
                                size=12).set_label('买', 11, color='#26a69a'),
        short_signal=SignalStyle('high', Colors.tomato, Markers.arrow_down,
                                 size=12).set_label('卖', 11, color='#ef5350'),
    )

    #: 包络下轨只画线，不在图例里占一行 ✓
    legend = dict(env_lower=False)

    #: 图表中央水印（本地图表同样生效 ✓）
    watermark = WaterMark(text='LOCAL STYLE', font_size=36)

    tablestyle = TableStyle(
        position='top-right', draggable=True,
        header='本地图表样式',
        headings=('项目', '值'),
        rows=[('快线', '10'), ('慢线', '30'), ('色带', '2 倍波动'),
              ('信号', '金叉 / 死叉')],
    )

    #: 回测时用的默认数据；加到本地图表时以当前 CSV 为准 ✓
    data = LocalDatas.l2609_60

    def next(self):
        close = np.asarray(self.close.values, dtype=float)
        fast = _sma(close, self.params.fast)
        slow = _sma(close, self.params.slow)
        diff = fast - slow
        prev = np.concatenate(([np.nan], diff[:-1]))

        # 用最近 50 根的平均振幅做包络，避免固定百分比在大小合约上失真
        amp = pd.Series(np.abs(np.diff(close, prepend=close[0]))) \
            .rolling(50).mean().to_numpy()
        band = amp * float(self.params.band) * 4.0
        upper = fast + band
        lower = fast - band

        long_signal = _sparse_cross(diff, prev, up=True,
                                    cooldown=int(self.params.cooldown))
        short_signal = _sparse_cross(diff, prev, up=False,
                                     cooldown=int(self.params.cooldown))
        return fast, slow, upper, lower, long_signal, short_signal


def _sma(values, length):
    return pd.Series(values).rolling(max(1, int(length))).mean().to_numpy()


def _sparse_cross(diff, prev, up=True, cooldown=60):
    """交叉信号 + 冷却期：避免一屏出现几十个箭头。"""
    out = np.zeros(len(diff), dtype=float)
    last = -10 ** 9
    for index in range(1, len(diff)):
        if not np.isfinite([diff[index], prev[index]]).all():
            continue
        crossed = (prev[index] <= 0 < diff[index]) if up \
            else (prev[index] >= 0 > diff[index])
        if crossed and index - last >= max(1, int(cooldown)):
            out[index] = 1.0
            last = index
    return out
