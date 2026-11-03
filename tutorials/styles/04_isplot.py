"""7.4 · isplot —— 哪些线「画」、哪些线只当数据

演示要点
--------
``PlotInfo.isplot`` 控制每条线**要不要画曲线**，三种写法都支持：

.. code-block:: python

    isplot = False                              # 所有线都不画
    isplot = True                               # 所有线都画（默认）
    isplot = [True, True, False, False]         # 按**线序**（与 lines 对齐）
    isplot = dict(line_c=False, line_d=False)   # 按**线名**（推荐）

⚠️ 常见误解
------------
* ``isplot=False`` 只是**不画折线**，图例行还在（要连图例一起隐藏用 ``legend``，见 7.5）；
* 信号线（``long_signal`` 等）正常就是要 ``isplot=False``：只落图标不画线。

本例：4 条 EMA 全放副图，但只画前两条，后两条只保留数据（打印/策略里能用）。

运行：``python tutorials/styles/04_isplot.py``
文档：``minibt_docs/docs/minibt_styles/7.4_isplot.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class IsplotDemo(BtIndicator):
    """4 条 EMA 放同一个副图，只画 10 / 30，60 / 120 只留数据。"""

    lines = ('ema_10', 'ema_30', 'ema_60', 'ema_120')

    # 全部放副图（False）
    overlap = False

    # 按线名关掉两条（按线序写法：isplot=[True, True, False, False]）
    isplot = dict(ema_60=False, ema_120=False)

    linestyle = dict(
        ema_10=LineStyle(line_color=Colors.orange, line_width=2),
        ema_30=LineStyle(line_color=Colors.blue, line_width=2),
        ema_60=LineStyle(line_color=Colors.purple, line_width=2),
        ema_120=LineStyle(line_color=Colors.green, line_width=2),
    )

    def next(self):
        return (self.close.ema(10),
                self.close.ema(30),
                self.close.ema(60),
                self.close.ema(120))


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = IsplotDemo(kline)

    info = ind.plotinfo
    print('lines  =', list(info.lines))
    print('isplot =', info.isplot)
    # 数据仍在：关掉的线照样能取值
    print('ema_120 最后一根 =', ind.ema_120[-1])

    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
