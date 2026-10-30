"""08 · 网页版回放 —— SuperTrend + 主图双蜡烛叠加

模式：**pylightcharts_web 引擎 + 回放**
运行：``python tutorials/plots/08_replay_pylightcharts_web.py``

本示例重点演示：

* ``overlap=True`` 的**蜡烛型指标**直接叠加到主图 —— 主 K 线之上再画一组“双蜡烛”
  （1.2.8：蜡烛分支区分 ``is_overlap``，柱宽自动缩为一半，不遮住主 K 线）
* ``Config(volume_mode='both')``                 —— 主图叠加 + 独立副图都显示成交量
* ``set_stop_lines_style``                       —— 开仓前提前设置止损 / 止盈线型（1.2.8）

切换提示：``Gui.PylightchartsWeb`` → ``Gui.Pylightcharts`` / ``Gui.Bokeh``；
``replay=True`` → 去掉即回测，``live=True`` 即实时。
"""

import numpy as np

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class HeikinAshi(BtIndicator):
    """Heikin-Ashi 蜡烛（蜡烛型指标，``overlap=True`` 叠加到主图）。"""

    lines = ('open', 'high', 'low', 'close')
    category = 'candles'                 # [1.2.8] 声明为蜡烛型
    overlap = True                       # 叠加到主图（而非另开副图）
    # [1.2.8] 指标自带的蜡烛配色
    candlestyle = CandleStyle(bull='#26a69a', bear='#ef5350')

    def next(self):
        src = self.close.values.astype(float)
        o = self.open.values.astype(float)
        h = self.high.values.astype(float)
        lw = self.low.values.astype(float)
        ha_close = (o + h + lw + src) / 4.0
        ha_open = np.full_like(ha_close, np.nan)
        ha_open[0] = (o[0] + src[0]) / 2.0
        for i in range(1, ha_close.size):
            ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0
        ha_high = np.maximum.reduce([h, ha_open, ha_close])
        ha_low = np.minimum.reduce([lw, ha_open, ha_close])
        return ha_open, ha_high, ha_low, ha_close


class SuperTrend(BtIndicator):
    """ATR 通道构成的 SuperTrend 趋势线。"""

    lines = ('trend', 'long_signal', 'short_signal')
    params = dict(PERIOD=10, MULT=2.0)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = dict(trend=True)
    linestyle = dict(trend=LineStyle(line_color='#f0b90b', line_width=2))
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle).set_label('S'),
    )

    def next(self):
        p = self.params
        close = self.close.values.astype(float)
        mid = (self.high + self.low) / 2
        atr = self.pine.atr(p.PERIOD)
        upper = (mid + atr * p.MULT).values.astype(float)
        lower = (mid - atr * p.MULT).values.astype(float)
        trend = np.full_like(close, np.nan)
        direction = np.ones_like(close)
        for i in range(1, close.size):
            if close[i] > upper[i - 1]:
                direction[i] = 1
            elif close[i] < lower[i - 1]:
                direction[i] = -1
            else:
                direction[i] = direction[i - 1]
            trend[i] = lower[i] if direction[i] > 0 else upper[i]
        prev = np.roll(trend, 1)
        prev[0] = np.nan
        long_signal = ((close > trend) & (close <= prev)).astype(float)
        short_signal = ((close < trend) & (close >= prev)).astype(float)
        return trend, long_signal, short_signal


class SuperTrendHeikinStrategy(Strategy):
    config = Config(theme='dark', volume_mode='both')
    params = dict(symbol='SHFE.ni2610')

    def __init__(self):
        if self._is_live_trading:
            self.data = self.get_kline(self.params.symbol)
        else:
            self.data = self.get_kline(LocalDatas.test, height=500)
            self.ha = HeikinAshi(self.data)        # 主图双蜡烛
        self.st = SuperTrend(self.data)
        # [1.2.8] 开仓前就把止损 / 止盈线型设好
        self.data.set_stop_lines_style(
            stop=LineStyle(line_color='#ff6b6b', line_dash=LineDash.dashed),
            target=LineStyle(line_color='#51cf66', line_dash=LineDash.dotted))

    def next(self):
        if not self.data.position:
            if self.st.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.st.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == '__main__':
    Bt(replay=True).run(gui=Gui.PylightchartsWeb)   # ⑧ 网页版回放
