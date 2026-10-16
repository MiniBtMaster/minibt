"""10 · Bokeh 实时（本地 mock tick，无需天勤账号）

模式：**Bokeh 引擎 + 实时（本地模拟）**
运行：``python tutorials/plots/10_live_bokeh_mock.py``

没有天勤账号时，用 ``MockLiveFeed`` 就能看到和真实盘几乎一样的 bokeh 实时图：
策略一开始用**全量本地数据**把指标 / 交易 / 权益算好，之后每隔 ``period_ms``
**逐根揭开**一根，视口跟着右移，顶部“账户信息”按当前 bar 的累计盈亏更新 ——
效果就是「一根一根往右长」的实时图。

关键在于 ``feed_factory``：``run_live`` / ``build_live_app`` 允许把数据源换成
任意带 ``bind(reg)`` / ``tick()`` 的对象；``MockLiveFeed`` 是框架内置的本地实现。

切换提示：把 ``feed_factory`` 换成真实天勤（去掉它、走 ``03_live_bokeh.py`` 的
``Bt(live=True)`` 写法）即为真实盘；``speed`` 可加速。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *
from minibt.strategy import bokeh_realtime as rt


class DonchianBreakout(BtIndicator):
    """唐奇安通道突破（mock 实时演示用）。"""

    lines = ('upper', 'lower', 'mid', 'long_signal', 'short_signal')
    params = dict(PERIOD=20)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = dict(upper=True, lower=True, mid=True)
    bandstyle = [BandStyle('lower', 'upper', fill_color='#20c997', fill_alpha=0.10)]
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle).set_label('S'),
    )

    def next(self):
        n = self.params.PERIOD
        upper = self.high.tqfunc.hhv(n).shift()
        lower = self.low.tqfunc.llv(n).shift()
        mid = (upper + lower) / 2
        long_signal = self.close.cross_up(upper)
        short_signal = self.close.cross_down(lower)
        return upper, lower, mid, long_signal, short_signal


class MockLiveStrategy(Strategy):
    config = Config(theme='dark', volume_mode='overlay', grid=False)

    def __init__(self):
        # 本地数据（mock 实时不需要天勤）
        self.data = self.get_kline(LocalDatas.test, height=500)
        self.ind = DonchianBreakout(self.data)

    def next(self):
        if not self.data.position:
            if self.ind.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.ind.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == '__main__':
    # 1) 先用全量本地数据把指标 / 交易 / 权益算好（不绘图）
    bt = Bt(auto=False)
    bt.addstrategy(MockLiveStrategy)
    bt.run(isplot=False)

    # 2) 用 MockLiveFeed 逐根“揭开” = 本地模拟实时
    rt.run_live(
        bt.strategies,
        port=8980,
        period_ms=400,                      # 每 400ms 走一根
        plot_kwargs=dict(plot_width=1400, volume_mode='overlay'),
        feed_factory=lambda strategys, reg: rt.MockLiveFeed(
            strategys, reg, start_bars=300, window=300, speed=1),
    )
