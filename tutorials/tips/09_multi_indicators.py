"""5.9 · 一张图看多个指标 —— 三种组织方式

演示要点
--------
| 想达到的效果 | 做法 |
| --- | --- |
| 主图叠均线 + 副图放振荡器 | **一个指标类**，用 ``overlap`` 逐线分主/副 |
| 两个指标各占一个副图 | **派生指标**（``B(A)``）+ ``btplot`` 自动画整条源链 |
| 全都想叠在主图 | ``overlap = True``（量纲要一致） |

本例：``Mixed`` 一个指标里 2 条均线（主图）+ 1 条振荡器（副图 1）；
``Smoothed`` 基于它再平滑一次 → 副图 2。所以一张图里 **3 个区域**。

运行：``python tutorials/tips/09_multi_indicators.py``
文档：``minibt_docs/docs/minibt_tips/5.9_multi_indicator_in_one_chart.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class Mixed(BtIndicator):
    """均线（主图）+ 偏离率与信号线（副图 1）。"""

    lines = ('ma_fast', 'ma_slow', 'osc', 'osc_ma')
    params = dict(FAST=20, SLOW=60, LEN=20, SIG=9)
    # ★ 逐线分主图 / 副图 —— 一个指标里就能混着放
    overlap = dict(ma_fast=True, ma_slow=True, osc=False, osc_ma=False)
    linestyle = dict(
        ma_fast=LineStyle(line_color=Colors.orange, line_width=1.5),
        ma_slow=LineStyle(line_color=Colors.blue, line_width=1.5),
        osc=LineStyle(line_color=Colors.purple, line_width=1.6),
        osc_ma=LineStyle(line_color=Colors.gray, line_width=1.2,
                         line_dash=LineDash.dashed),
    )

    def next(self):
        p = self.params
        ma_fast = self.close.ema(p.FAST)
        ma_slow = self.close.ema(p.SLOW)
        base = self.close.ema(p.LEN)
        osc = (self.close - base) / base * 100
        return ma_fast, ma_slow, osc, osc.ema(p.SIG)


class Smoothed(BtIndicator):
    """基于 Mixed 再平滑一次（源是 Mixed，不是 K 线）→ 副图 2。"""

    lines = ('osc_smooth',)
    overlap = False
    linestyle = dict(osc_smooth=LineStyle(line_color=Colors.teal,
                                          line_width=1.8))

    def next(self):
        # 这里 self 是 **Mixed 的 IndFrame**，所以取列名而不是 self.close
        return self.osc.ema(21)


def main(gui=None):
    kline = LocalDatas.test.kline
    mixed = Mixed(kline)
    smooth = Smoothed(mixed)
    print('Mixed.lines  =', list(mixed.plotinfo.lines))
    print('Mixed.overlap=', mixed.plotinfo.overlap)
    print('Smoothed 基于 Mixed → btplot 会把整条源链画出来（3 个区域）')
    smooth.btplot(gui=gui)


if __name__ == '__main__':
    main()
