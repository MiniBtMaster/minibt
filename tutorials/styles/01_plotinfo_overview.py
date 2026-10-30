"""7.1 · PlotInfo 心智模型 —— 一条指标从「计算」到「上图」的完整链路

演示要点
--------
一个 ``BtIndicator`` 只需要声明几件事，图形就出来了：

* ``lines``       —— 数据有几列、每列叫什么（**返回值的顺序必须和它对上**）；
* ``overlap``     —— 每条线画在**主图**（``True``）还是**副图**（``False``）；
* ``isplot``      —— 每条线要不要**画曲线**（信号线通常 ``False``，只落图标）；
* ``linestyle``   —— 每条线的颜色 / 宽度 / 线型；
* ``signalstyle`` —— 信号线的图标、颜色、文字标签。

这些字段最终都会汇总成一份 ``self.plotinfo``（``minibt.utils.PlotInfo``），
**三个引擎（bokeh / pylightcharts / 网页版）读的都是同一份**，所以样式只写一次。

运行：``python tutorials/styles/01_plotinfo_overview.py``
文档：``minibt_docs/docs/minibt_styles/7.1_plotinfo_overview.md``
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class Overview(BtIndicator):
    """主图两条均线 + 副图一个振荡器 + 两个信号。

    这是「一份 PlotInfo 同时管主图 / 副图 / 信号」的最小例子：
    5 条线里，2 条在主图、1 条在副图、2 条不画线只落信号图标。
    """

    lines = ('ma_fast', 'ma_slow', 'osc', 'long_signal', 'short_signal')
    params = dict(FAST=10, SLOW=30)

    # 逐线指定「主图 / 副图」：True = 叠在主图，False = 独立副图
    overlap = dict(ma_fast=True, ma_slow=True, osc=False)
    # 信号线只用来落图标，不画折线
    isplot = dict(long_signal=False, short_signal=False)

    linestyle = dict(
        ma_fast=LineStyle(line_color=Colors.orange, line_width=2),
        ma_slow=LineStyle(line_color=Colors.blue, line_width=2),
        osc=LineStyle(line_color=Colors.purple, line_width=1.5),
    )
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red,
                                Markers.triangle).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle).set_label('S'),
    )

    def next(self):
        p = self.params
        ma_fast = self.close.ema(p.FAST)
        ma_slow = self.close.ema(p.SLOW)
        # 快慢均线的相对差（百分比），量纲和价格不同 → 必须放副图
        osc = (ma_fast - ma_slow) / self.close * 100
        long_signal = ma_fast.cross_up(ma_slow)
        short_signal = ma_fast.cross_down(ma_slow)
        return ma_fast, ma_slow, osc, long_signal, short_signal


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = Overview(kline)

    # 对照文档里的字段表：这几行就是「PlotInfo 在管什么」
    info = ind.plotinfo
    print('lines       =', list(info.lines))
    print('line_filed  =', list(info.line_filed))
    print('signallines =', list(info.signallines))
    print('overlap     =', info.overlap)
    print('isplot      =', info.isplot)
    print('category    =', info.category)

    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
