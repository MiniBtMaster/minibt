"""06 · 纯 pylightcharts 实时 —— Pine `ta.*` 双均线 + ATR

模式：**纯 pylightcharts 引擎 + 实时**
运行：``python tutorials/plots/06_live_pylightcharts.py``（需要天勤账号）

本示例重点演示 **Pine Script `ta.*` 指标接口**（1.2.9 由 8 个扩展到 **57 个**函数）：

```python
self.close.pine.sma(20)          # 单序列
self.data.pine.atr(14)           # K 线多序列
self.close.pine.crossover(ma)    # 布尔
(cond).pine.barssince()          # 条件
```

同时演示：``history_length`` 无限历史、实时图顶栏的**断开连接 / 重新连接**菜单、
``color_by`` 逐根配色。

切换提示：``gui=Gui.Pylightcharts`` → ``Gui.PylightchartsWeb`` / ``Gui.Bokeh``。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class PineTrend(BtIndicator):
    """双均线趋势 + ATR 波动过滤（用 Pine 接口实现）。"""

    lines = ('fast', 'slow', 'atr_up', 'atr_dn', 'long_signal', 'short_signal')
    params = dict(FAST=10, SLOW=30, ATR_LEN=14, ATR_MULT=1.5)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = dict(fast=True, slow=True, atr_up=True, atr_dn=True)
    bandstyle = [BandStyle('atr_dn', 'atr_up',
                           fill_color='#7950f2', fill_alpha=0.08)]
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle).set_label('S'),
    )

    def next(self):
        p = self.params
        # [1.2.9] Pine 接口：`ta.sma` / `ta.atr` / `ta.crossover` / `ta.crossunder`
        fast = self.close.pine.sma(p.FAST)
        slow = self.close.pine.sma(p.SLOW)
        atr = self.pine.atr(p.ATR_LEN)
        atr_up = slow + atr * p.ATR_MULT
        atr_dn = slow - atr * p.ATR_MULT
        long_signal = self.close.pine.crossover(atr_up)
        short_signal = self.close.pine.crossunder(atr_dn)
        return fast, slow, atr_up, atr_dn, long_signal, short_signal


class PineTrendStrategy(Strategy):
    config = Config(theme='dark', volume_mode='overlay', grid=False)
    params = dict(symbol='SHFE.ni2610')

    def __init__(self):
        if self._is_live_trading:
            # [1.2.9] 实盘多取历史（窗口先显示 200 根，向左滚动按页补）
            self.data = self.get_kline(self.params.symbol,
                                       history_length=10000, data_length=200)
        else:
            self.data = self.get_kline(LocalDatas.test, height=500)
        self.data.color_by(self.data.close < self.data.open,
                           color='#3ba272', else_color='#d94b4b')
        self.ind = PineTrend(self.data)

    def next(self):
        if not self.data.position:
            if self.ind.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.ind.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == '__main__':
    # 需要天勤账号：把用户名/密码换成自己的再取消注释
    # from tqsdk import TqApi, TqAuth, TqKq
    # api = TqApi(TqKq(), auth=TqAuth("用户名", "密码"))
    # bt = Bt(auto=False, live=True)
    # bt.addTqapi(api=api)
    # bt.addstrategy(PineTrendStrategy)
    # bt.run(gui=Gui.Pylightcharts)       # ⑥ pylightcharts 实时（顶栏可断开/重连）
    raise SystemExit('实时示例：请先在天勤账号处填入用户名/密码并取消注释')
