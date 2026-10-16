"""04 · 纯 pylightcharts 回测 —— 一行回测内置指标

模式：**纯 pylightcharts 引擎 + 回测**
运行：``python tutorials/plots/04_backtest_pylightcharts.py``

本示例重点演示 **`IndFrame.backtest()`**（1.2.8）：对“指标自带交易逻辑”
（类里重写了 ``step()``）的内置 TradingView 指标，**一行代码**即可回测 + 出图，
不用再手写 ``Strategy``。附带演示 ``reverse=True`` 反手。

切换提示：``gui=Gui.Pylightcharts`` → ``Gui.PylightchartsWeb`` / ``Gui.Bokeh``；
``backtest()`` 的参数与 ``Bt.run`` 一致（``isplot`` / ``isreport`` / ``gui`` …）。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


# ── 方式一：内置指标自带 step()，一行回测 ────────────────────────────────
kline = LocalDatas.test.kline
ema = kline.tradingview.SingleEMACross(ema1=10, ema2=20)


# ── 方式二：自定义策略，演示 reverse 反手 ────────────────────────────────
class EMACross(BtIndicator):
    """双 EMA 交叉信号（仅信号，不含交易逻辑）。"""

    lines = ('ema_fast', 'ema_slow', 'long_signal', 'short_signal')
    params = dict(FAST=10, SLOW=20)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = dict(ema_fast=True, ema_slow=True)
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle).set_label('S'),
    )

    def next(self):
        p = self.params
        ema_fast = self.close.ema(p.FAST)
        ema_slow = self.close.ema(p.SLOW)
        long_signal = ema_fast.cross_up(ema_slow)
        short_signal = ema_fast.cross_down(ema_slow)
        return ema_fast, ema_slow, long_signal, short_signal


class ReverseEMACrossStrategy(Strategy):
    """金叉做多 / 死叉反手做空（``reverse=True`` 一键反手，1.2.8）。"""

    def __init__(self):
        self.data = self.get_kline(LocalDatas.test, height=500)
        self.ind = EMACross(self.data)

    def next(self):
        if self.ind.long_signal.new:
            # 持空单时直接反手做多；持多单 / 空仓则退化为普通买
            self.data.buy(reverse=True, stop=BtStop.SegmentationTracking)
        elif self.ind.short_signal.new:
            self.data.sell(reverse=True, stop=BtStop.SegmentationTracking)


if __name__ == '__main__':
    # 方式一：一行回测（指标自带 step()）
    ema.backtest(gui=Gui.Pylightcharts)

    # 方式二：自定义策略 + 反手（取消注释即可）
    # Bt().run(gui=Gui.Pylightcharts)
