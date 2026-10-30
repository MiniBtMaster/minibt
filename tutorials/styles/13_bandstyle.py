"""7.13 · bandstyle —— 两条线之间填充色带

演示要点
--------
``PlotInfo.bandstyle`` 是 ``BandStyle`` 列表，把**两条指标线之间**填成半透明色带：

| 字段 | 默认 | 作用 |
| --- | --- | --- |
| ``lower`` | ``None`` | **下沿的线名**（= ``lines`` 里的名字） |
| ``upper`` | ``None`` | **上沿的线名** |
| ``fill_color`` | ``'steelblue'`` | 填充色 |
| ``fill_alpha`` | ``0.03`` | 填充透明度（0~1，越大越实） |
| ``line_color`` | ``None`` | 给色带的上下沿**再画一圈边框线** |
| ``level`` | ``'underlay'`` | 层级；pylightcharts 走 ``fill_between``，此字段不参与 |

典型用法：通道（上下轨）、布林带、均线带的渐变背景。

运行：``python tutorials/styles/13_bandstyle.py``
文档：``minibt_docs/docs/minibt_styles/7.13_bandstyle.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class EmaChannel(BtIndicator):
    """均线 ±2% 通道，上下轨之间填色带。"""

    lines = ('upper', 'lower', 'mid')
    overlap = True
    params = dict(LEN=20, BAND=0.02)

    linestyle = dict(
        upper=LineStyle(line_color=Colors.blue, line_width=1.5),
        lower=LineStyle(line_color=Colors.blue, line_width=1.5),
        mid=LineStyle(line_color=Colors.orange, line_width=2,
                      line_dash=LineDash.dashed),
    )

    # ★ 色带：lower / upper 是**线名**，不是数值
    bandstyle = [
        BandStyle(lower='lower', upper='upper',
                  fill_color='#4dabf7', fill_alpha=0.18),
    ]

    def next(self):
        p = self.params
        mid = self.close.ema(p.LEN)
        return mid * (1 + p.BAND), mid * (1 - p.BAND), mid


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = EmaChannel(kline)
    for band in ind.plotinfo.bandstyle:
        print(f'  色带 {band.lower} ~ {band.upper}  '
              f'fill={band.fill_color} alpha={band.fill_alpha} '
              f'line={band.line_color}')
    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
