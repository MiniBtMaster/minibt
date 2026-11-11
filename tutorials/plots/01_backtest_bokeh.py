"""01 · Bokeh 回测 —— EMA 通道突破

模式：**Bokeh 引擎 + 回测**
运行：``python tutorials/plots/01_backtest_bokeh.py``

本示例重点演示 v1.2.7 ~ v1.2.9 的**样式映射**与 **bokeh 图表配置**：

* ``BandStyle``        —— 两条均线之间填充色带（1.2.8）
* ``SpanStyle``        —— 分界线（1.2.9）
* ``signalstyle``      —— 信号图标（Markers）+ ``set_label`` 文字（1.2.8/1.2.9）
* ``color_by``         —— K 线逐根配色（1.2.9）
* ``Config(...)``      —— ``theme`` / ``grid`` / ``toolbox`` / ``volume_mode`` /
  ``bokeh_fullscreen``（1.2.8/1.2.9）

切换提示：把最后一行改成 ``Bt(replay=True).run(gui=Gui.Bokeh)`` 即为 Bokeh 回放，
``Bt().run(gui=Gui.PylightchartsWeb)`` 即为网页版回测。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class EMAChannel(BtIndicator):
    """EMA 通道突破：价格上穿上轨做多、下穿下轨做空。"""

    lines = ('ema_fast', 'ema_slow', 'channel_up', 'channel_dn',
             'long_signal', 'short_signal')
    params = dict(FAST=10, SLOW=30, BAND=1.2)
    # 信号线本身不画曲线，只在图上落图标 / 文本
    isplot = dict(long_signal=False, short_signal=False)
    # 均线 / 通道画在主图
    overlap = dict(ema_fast=True, ema_slow=True, channel_up=True, channel_dn=True)
    # [1.2.8] 上下轨之间填充色带
    bandstyle = [
        BandStyle('channel_dn', 'channel_up', fill_color='#4dabf7', fill_alpha=0.12),
    ]
    # [1.2.9] 信号图标 + 文字标签
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red,
                                Markers.triangle).set_label('多'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle).set_label('空'),
    )

    def next(self):
        p = self.params
        ema_fast = self.close.ema(p.FAST)
        ema_slow = self.close.ema(p.SLOW)
        mid = (ema_fast + ema_slow) / 2
        gap = (ema_fast - ema_slow) * p.BAND
        channel_up = mid + gap
        channel_dn = mid - gap
        long_signal = self.close.cross_up(channel_up)
        short_signal = self.close.cross_down(channel_dn)
        return ema_fast, ema_slow, channel_up, channel_dn, long_signal, short_signal


class EMAChannelStrategy(Strategy):
    # [1.2.8/1.2.9] 主题 / 网格 / 工具栏 / 成交量 / 全屏
    config = Config(theme='dark', grid=True, toolbox=True,
                    volume_mode='overlay', bokeh_fullscreen=True)

    def __init__(self):
        self.data = self.get_kline(LocalDatas.test, height=500)
        # [1.2.9] 阳线亮绿、阴线番茄红（K 线逐根配色）
        self.data.color_by(self.data.close < self.data.open,
                           color=Colors.tomato, else_color=Colors.lime)
        self.ind = EMAChannel(self.data)

    def next(self):
        if not self.data.position:
            if self.ind.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.ind.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == '__main__':
    Bt().run(gui=Gui.Bokeh)            # ① Bokeh 回测
