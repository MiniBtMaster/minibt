"""7.15 · source / 副图归属 —— 一个指标 = 一个副图

演示要点
--------
``overlap`` 决定「主图 / 副图」；**进了副图之后，按什么分 pane？** 答案是
``IndicatorSpec.source``：

* pylightcharts 侧，``source`` 就是**指标的注册 key**（源码里写死 ``source=key``）；
* 所以：**一个指标 = 一个副图**，同一指标的多条线**共用**这个副图；
* 两个指标（哪怕 ``overlap=False`` 都设了）→ **两个副图**。

本例：``OscB`` 是基于 ``OscA`` 的派生指标（``btplot`` 会把整条源链都画出来），
所以图上会看到**两个副图** —— 这就是 ``source`` 在分组。

⚠️ ``PlotInfo.source`` 在 pylightcharts 分支**不起作用**（会被指标 key 覆盖）；
只有 bokeh 侧会读 ``plotinfo['source']``。想让 pylightcharts 里的两个指标合到一个
副图，做法见文档「三种合并办法」。

运行：``python tutorials/styles/15_source.py``
文档：``minibt_docs/docs/minibt_styles/7.15_source.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class OscA(BtIndicator):
    """副图 1：偏离率 + 它的均线。"""

    lines = ('osc', 'signal')
    overlap = False
    params = dict(LEN=20, SIG=9)
    linestyle = dict(
        osc=LineStyle(line_color=Colors.orange, line_width=1.6),
        signal=LineStyle(line_color=Colors.blue, line_width=1.2,
                         line_dash=LineDash.dashed),
    )

    def next(self):
        p = self.params
        ma = self.close.ema(p.LEN)
        osc = (self.close - ma) / ma * 100
        return osc, osc.ema(p.SIG)


class OscB(BtIndicator):
    """副图 2：把 OscA 的 osc 再平滑一次（源是 OscA，不是 K 线）。"""

    lines = ('smooth',)
    overlap = False
    linestyle = dict(smooth=LineStyle(line_color=Colors.purple,
                                      line_width=1.8))

    def next(self):
        # 这里 self 是 **OscA 的 IndFrame**（不是 KLine），所以能取到 self.osc
        return self.osc.ema(21)


def main(gui=None):
    kline = LocalDatas.test.kline
    a = OscA(kline)
    b = OscB(a)
    print('OscA.plotinfo.source =', repr(a.plotinfo.source),
          '（空 = 没设；实际分组用指标 key）')
    print('OscB 基于 OscA：btplot 会把 A、B 都画出来 → 两个副图')
    b.btplot(gui=gui)


if __name__ == '__main__':
    main()
