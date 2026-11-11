"""05 · 纯 pylightcharts 回放 —— MACD 柱状

模式：**纯 pylightcharts 引擎 + 回放**
运行：``python tutorials/plots/05_replay_pylightcharts.py``

本示例重点演示**柱状指标**的画法：

* ``LineDash.vbar``                          —— 把指标线画成柱体（1.2.8）
* ``LineStyle.vbar_base``                    —— 柱底基线（默认 0；可设 50 之类做成绕中轴振荡）
* ``BandStyle``                              —— DIF / DEA 之间填充
* 回放控件（播放 / 暂停 / 单步 / 调速）

切换提示：``Gui.Pylightcharts`` → ``Gui.PylightchartsWeb`` / ``Gui.Bokeh``。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class MACDHistogram(BtIndicator):
    """MACD：DIF / DEA 两条线 + 柱状 HIST。"""

    lines = ('dif', 'dea', 'hist', 'long_signal', 'short_signal')
    params = dict(FAST=12, SLOW=26, SIGNAL=9)
    isplot = dict(hist=True, long_signal=False, short_signal=False)
    overlap = dict(dif=False, dea=False, hist=False)
    # [1.2.8] 柱体：HIST 画成柱，柱底基线为 0（正负自动分色）
    linestyle = dict(
        dif=LineStyle(line_color='#F0B90B', line_width=1.4),
        dea=LineStyle(line_color='#4dabf7', line_width=1.4),
        hist=LineStyle(line_dash=LineDash.vbar, vbar_base=0.0),
    )
    # DIF 与 DEA 之间填充
    bandstyle = [BandStyle('dea', 'dif', fill_color='#ffcb66', fill_alpha=0.10)]
    spanstyle = [SpanStyle(0)]
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle).set_label('S'),
    )

    def next(self):
        p = self.params
        dif, dea, hist = self.close.macd(p.FAST, p.SLOW, p.SIGNAL)
        long_signal = hist.cross_up(0.)
        short_signal = hist.cross_down(0.)
        return dif, dea, hist, long_signal, short_signal


class MACDHistogramStrategy(Strategy):
    config = Config(theme='dark', volume_mode='sub')

    def __init__(self):
        self.data = self.get_kline(LocalDatas.test, height=500)
        self.macd = MACDHistogram(self.data)

    def next(self):
        if not self.data.position:
            if self.macd.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.macd.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == '__main__':
    Bt(replay=True).run(gui=Gui.Pylightcharts)   # ⑤ pylightcharts 回放
