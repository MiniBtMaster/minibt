"""02 · Bokeh 回放 —— RSI 均值回归

模式：**Bokeh 引擎 + 回放**
运行：``python tutorials/plots/02_replay_bokeh.py``

回放是纯 bokeh server（内存逐 bar 揭开，不落盘）：先放出一段历史，之后可
**播放 / 暂停 / 单步 / 调速**。本示例重点演示：

* ``Bt(replay=True).run(gui=Gui.Bokeh)`` —— 回放入口（1.2.9）
* ``Config(volume_mode='sub')``         —— 成交量独立副图（高度为其它副图的一半）
* ``Config(theme='light')``             —— 浅色主题（1.2.9 统一 ``theme`` 参数）
* ``SpanStyle``                         —— RSI 超买 / 超卖分界线
* ``plot_width``                        —— 指定图宽

切换提示：``gui=Gui.Bokeh`` → ``Gui.Pylightcharts``（原生窗口）/ ``Gui.PylightchartsWeb``
（浏览器）；``replay=True`` → 去掉即为回测。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class RSIMeanReversion(BtIndicator):
    """RSI 超卖做多、超买做空。"""

    lines = ('rsi', 'long_signal', 'short_signal')
    params = dict(PERIOD=6, OVERBOUGHT=70, OVERSOLD=30)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = False                       # RSI 走独立副图
    # [1.2.9] 超买 / 超卖分界线
    spanstyle = [SpanStyle(70), SpanStyle(50), SpanStyle(30)]
    # [1.2.9] 信号图标 + 文本
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.circle).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.circle_dot).set_label('S'),
    )

    def next(self):
        p = self.params
        rsi = self.close.rsi(p.PERIOD)
        long_signal = rsi.cross_up(p.OVERSOLD)
        short_signal = rsi.cross_down(p.OVERBOUGHT)
        return rsi, long_signal, short_signal


class RSIMeanReversionStrategy(Strategy):
    config = Config(theme='light', volume_mode='sub', grid=False)

    def __init__(self):
        self.data = self.get_kline(LocalDatas.test, height=500)
        self.rsi = RSIMeanReversion(self.data)

    def next(self):
        if not self.data.position:
            if self.rsi.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.rsi.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == '__main__':
    Bt(replay=True).run(gui=Gui.Bokeh, plot_width=1400)   # ② Bokeh 回放
