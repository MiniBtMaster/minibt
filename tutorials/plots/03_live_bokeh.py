"""03 · Bokeh 实时 —— ATR 跟踪止损（ThreeCommasStop）

模式：**Bokeh 引擎 + 实时**
运行：``python tutorials/plots/03_live_bokeh.py``（需要天勤账号）

实时图是纯 bokeh server，数据由天勤 ``api.wait_update`` 驱动，只在内存里更新。
本示例重点演示：

* ``Bt(live=True).run(gui=Gui.Bokeh)``         —— 实时入口（1.2.9）
* ``get_kline(..., history_length=10000)``     —— 无限历史（1.2.9，窗口只先显示 200 根）
* ``BtStop.ThreeCommasStop``                   —— 摆动点 + ATR 跟踪止损 / 盈亏比止盈（1.2.8）
* ``in_cooldown``                              —— 开仓后冷却，防止 ping-pong（1.2.7）
* 顶部**账户信息**（权益 / 可用 / 保证金 / 浮动盈亏 / 风险度）

切换提示：``gui=Gui.Bokeh`` → ``Gui.Pylightcharts``（原生窗口）/ ``Gui.PylightchartsWeb``
（浏览器 + SSE，支持断开/重连）。把 ``live=True`` 去掉、用本地数据即可回测。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class DonchianBreakout(BtIndicator):
    """唐奇安通道突破（实时里只用它出信号）。"""

    lines = ('upper', 'lower', 'mid', 'long_signal', 'short_signal')
    params = dict(PERIOD=20)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = dict(upper=True, lower=True, mid=True)
    # [1.2.8] 通道内填充
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


class DonchianLiveStrategy(Strategy):
    config = Config(theme='dark', volume_mode='overlay', grid=False)
    params = dict(symbol='SHFE.ni2610')

    def __init__(self):
        if self._is_live_trading:
            # [1.2.9] 实盘一次多取一些历史（窗口只先显示 200 根，向左滚动按页补）
            self.data = self.get_kline(self.params.symbol,
                                       history_length=10000, data_length=200)
        else:
            self.data = self.get_kline(LocalDatas.test, height=500)
        self.ind = DonchianBreakout(self.data)

    def next(self):
        if not self.data.position:
            # [1.2.7] 开仓后 300 秒内不再开仓，避免信号反复
            if self.in_cooldown(self.data, cooldown_seconds=300):
                return
            if self.ind.long_signal.new:
                # [1.2.8] ThreeCommasStop：摆动点 + ATR 跟踪止损 + 盈亏比止盈
                self.data.buy(stop=BtStop.ThreeCommasStop)
            elif self.ind.short_signal.new:
                self.data.sell(stop=BtStop.ThreeCommasStop)


if __name__ == '__main__':
    # 需要天勤账号：把用户名/密码换成自己的再取消注释
    # from tqsdk import TqApi, TqAuth, TqKq
    # api = TqApi(TqKq(), auth=TqAuth("用户名", "密码"))
    # bt = Bt(auto=False, live=True)
    # bt.addTqapi(api=api)
    # bt.addstrategy(DonchianLiveStrategy,
    #                DonchianLiveStrategy.copy(params=dict(symbol='SHFE.ag2610')))
    # bt.run(gui=Gui.Bokeh)             # ③ Bokeh 实时
    raise SystemExit('实时示例：请先在天勤账号处填入用户名/密码并取消注释')
