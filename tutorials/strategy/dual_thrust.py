from minibt import *


class DualThrust(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/dual-thrust"""
    params = dict(NDAY=14, K1=0.6, K2=0.6)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = True

    def next(self):
        HH = self.high.tqfunc.hhv(self.params.NDAY).shift()
        HC = self.close.tqfunc.hhv(self.params.NDAY).shift()
        LC = self.close.tqfunc.llv(self.params.NDAY).shift()
        LL = self.low.tqfunc.llv(self.params.NDAY).shift()
        range = (HH - LC).tqfunc.max(HC - LL)
        buy_line = self.open + range * self.params.K1  # 上轨
        sell_line = self.open - range * self.params.K2  # 下轨
        long_signal = self.close.cross_up(buy_line)
        short_signal = self.close.cross_down(sell_line)
        return buy_line, sell_line, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.dual_thrust = DualThrust(self.data)

    def next(self):
        if not self.data.position:
            if self.dual_thrust.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.dual_thrust.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
