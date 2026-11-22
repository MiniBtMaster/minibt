"""7.5 · legend —— 图例行显示/隐藏（和 isplot 的区别）

演示要点
--------
``PlotInfo.legend`` 只管**图例行（左上角那几行名字）**，不影响曲线本身：

.. code-block:: python

    legend = False                    # 整个指标的图例都不显示
    legend = True                     # 全显示（默认）
    legend = [True, False, True]      # 按**线序**（与 lines 对齐）
    legend = dict(ema_30=False)       # 按**线名**（推荐）

⚠️ ``isplot`` vs ``legend``
---------------------------
* ``isplot=False`` → **线不画**，但图例行还在（容易误以为"没生效"）；
* ``legend=False`` → **线照画**，只是图例里不列出它；
* 想"线也不画、图例也没有" → 两个都设（7.4 + 7.5）。

本例：3 条 EMA 都画，但只在图例里显示 2 行。

运行：``python tutorials/styles/05_legend.py``
文档：``minibt_docs/docs/minibt_styles/7.5_legend.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class LegendDemo(BtIndicator):
    """3 条均线都画在主图，但 ``ema_30`` 不占图例行。"""

    lines = ('ema_10', 'ema_30', 'ema_60')

    # 三条都在主图
    overlap = True

    # 按线名关掉 ema_30 的图例行（按线序写法：legend=[True, False, True]）
    legend = dict(ema_30=False)

    linestyle = dict(
        ema_10=LineStyle(line_color=Colors.orange, line_width=2),
        ema_30=LineStyle(line_color=Colors.blue, line_width=2),
        ema_60=LineStyle(line_color=Colors.purple, line_width=2),
    )

    def next(self):
        return (self.close.ema(10),
                self.close.ema(30),
                self.close.ema(60))


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = LegendDemo(kline)
    print('lines  =', list(ind.plotinfo.lines))
    print('legend =', ind.plotinfo.legend)
    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
