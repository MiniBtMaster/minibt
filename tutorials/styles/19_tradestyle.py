"""7.19 · tradestyle —— 成交标记与入场→离场连线

演示要点
--------
回测图上的**真实成交**（不是指标信号）由 ``TradeStyle`` / ``TradeMarkerStyle`` 控制，
写在策略的 ``Config`` 里（也可以写成策略属性 ``self.tradestyle``）：

| 字段（``TradeStyle``） | 默认 | 作用 |
| --- | --- | --- |
| ``long_entry`` | ``None`` | 多头**入场**标记（``TradeMarkerStyle``） |
| ``short_entry`` | ``None`` | 空头**入场**标记 |
| ``long_exit`` | ``None`` | 多头**离场**标记 |
| ``short_exit`` | ``None`` | 空头**离场**标记 |
| ``line_color`` | ``None`` | 入场→离场**连线**颜色（``None`` = 跟主题） |
| ``line_width`` | ``3.0`` | 连线宽度 |
| ``line_dash`` | ``'dashed'`` | 连线线型 |
| ``show`` | ``True`` | ``False`` = 不画成交（信号照画） |

``TradeMarkerStyle`` 只有 3 个字段：``color`` / ``marker``（``Markers.*``）/ ``size``。

⚠️ 这个例子是**真回测**（有开平仓），所以图是"回测结果"页（带顶栏、成交标记）；
``btplot`` 那种静态指标图**没有成交**，也就看不到这些样式。

运行：``python tutorials/styles/19_tradestyle.py``
文档：``minibt_docs/docs/minibt_styles/7.19_tradestyle.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *
from minibt.utils import resolve_tradestyle   # 不在 __all__ 里


class EmaCross(BtIndicator):
    """60/200 均线交叉（只出信号，交易交给策略）。"""

    lines = ('ema_fast', 'ema_slow', 'long_signal', 'short_signal')
    params = dict(FAST=60, SLOW=200)
    overlap = dict(ema_fast=True, ema_slow=True)
    isplot = dict(long_signal=False, short_signal=False)
    linestyle = dict(
        ema_fast=LineStyle(line_color=Colors.orange, line_width=1.5),
        ema_slow=LineStyle(line_color=Colors.blue, line_width=1.5),
    )
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle, size=10),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle, size=10),
    )

    def next(self):
        p = self.params
        fast = self.close.ema(p.FAST)
        slow = self.close.ema(p.SLOW)
        return fast, slow, fast.cross_up(slow), fast.cross_down(slow)


class TradeStyleDemo(Strategy):
    """★ 成交样式写在 Config.tradestyle 里。"""

    config = Config(
        theme='light',
        grid=True,
        tradestyle=TradeStyle(
            long_entry=TradeMarkerStyle(color=Colors.red,
                                        marker=Markers.triangle, size=14),
            short_entry=TradeMarkerStyle(color=Colors.green,
                                         marker=Markers.inverted_triangle,
                                         size=14),
            long_exit=TradeMarkerStyle(color=Colors.orange,
                                       marker=Markers.circle_x, size=10),
            short_exit=TradeMarkerStyle(color=Colors.blue,
                                        marker=Markers.circle, size=10),
            line_color=Colors.purple,     # 入场→离场连线
            line_width=2,
            line_dash=LineDash.dashed,
        ),
    )

    def __init__(self):
        self.data = self.get_kline(LocalDatas.test, height=500)
        self.ind = EmaCross(self.data)

    def next(self):
        # 金叉做多 / 死叉做空，reverse=True 让反手自动平掉旧仓
        if self.ind.long_signal.new:
            self.data.buy(reverse=True)
        elif self.ind.short_signal.new:
            self.data.sell(reverse=True)


def main(gui=None):
    print('成交样式 =', resolve_tradestyle(TradeStyleDemo()))
    Bt().run(gui=gui or Gui.Pylightcharts)


if __name__ == '__main__':
    main()
