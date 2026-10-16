"""09 · 网页版实时 —— 挂单 + 冷却 + 反手

模式：**pylightcharts_web 引擎 + 实时**
运行：``python tutorials/plots/09_live_pylightcharts_web.py``（需要天勤账号）

本示例重点演示 v1.2.7 的**实盘接口**：

* ``insert_order``   —— 天勤原生下单（市价 / 限价 / FAK/FOK / 指定单号 / 多账户）
* ``in_cooldown``    —— 开仓冷却（秒 或 K 线根数），防止信号反复 ping-pong
* ``reverse=True``   —— 反手（平仓后立即反向开仓）
* ``Strategy.copy()``—— 深度合并 ``params`` / ``config``，复制策略只传差异

切换提示：``Gui.PylightchartsWeb`` → ``Gui.Pylightcharts`` / ``Gui.Bokeh``；
把 ``live=True`` 去掉、换本地数据即可回测（``insert_order`` 只在实盘有效）。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *
from minibt.order import OrderSide      # 天勤下单方向（未在 __all__ 里）


class BreakoutPullback(BtIndicator):
    """突破回踩：先突破 N 日高点，回踩不破均线再进场。"""

    lines = ('upper', 'ma', 'long_signal', 'short_signal')
    params = dict(PERIOD=20, MA=20)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = dict(upper=True, ma=True)
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle).set_label('S'),
    )

    def next(self):
        p = self.params
        upper = self.high.tqfunc.hhv(p.PERIOD).shift()
        ma = self.close.sma(p.MA)
        long_signal = (self.close.cross_up(upper) > 0) & (self.low > ma)
        short_signal = self.close.cross_down(ma)
        return upper, ma, long_signal, short_signal


class BreakoutLiveStrategy(Strategy):
    config = Config(theme='dark', volume_mode='overlay')
    params = dict(symbol='SHFE.ni2610', volume=1, cooldown=600)

    def __init__(self):
        if self._is_live_trading:
            # [1.2.9] 实盘无限历史
            self.data = self.get_kline(self.params.symbol,
                                       history_length=10000, data_length=200)
        else:
            self.data = self.get_kline(LocalDatas.test, height=500)
        self.ind = BreakoutPullback(self.data)

    def next(self):
        p = self.params
        # [1.2.7] 开仓冷却：cooldown 秒内不再下单
        if self.in_cooldown(self.data, cooldown_seconds=p.cooldown):
            return
        if self.ind.long_signal.new:
            if self._is_live_trading:
                # [1.2.7] 天勤原生市价单（如需限价可传 limit_price=...）
                self.insert_order(self.data, direction=OrderSide.Buy,
                                  volume=p.volume)
            self.data.buy(reverse=True, stop=BtStop.ThreeCommasStop)
        elif self.ind.short_signal.new:
            if self._is_live_trading:
                # 平仓单：offset='close'
                self.insert_order(self.data, direction=OrderSide.Sell,
                                  offset='close', volume=p.volume)
            self.data.sell(reverse=True, stop=BtStop.ThreeCommasStop)


if __name__ == '__main__':
    # 需要天勤账号：把用户名/密码换成自己的再取消注释
    # from tqsdk import TqApi, TqAuth, TqKq
    # api = TqApi(TqKq(), auth=TqAuth("用户名", "密码"))
    # bt = Bt(auto=False, live=True)
    # bt.addTqapi(api=api)
    # ni = BreakoutLiveStrategy
    # ag = BreakoutLiveStrategy.copy(params=dict(symbol='SHFE.ag2610'))  # 深度合并
    # bt.addstrategy(ni, ag)
    # bt.run(gui=Gui.PylightchartsWeb)    # ⑨ 网页版实时
    raise SystemExit('实时示例：请先在天勤账号处填入用户名/密码并取消注释')
