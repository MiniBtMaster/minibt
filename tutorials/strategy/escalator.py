from minibt import *


class Escalator(Strategy):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/escalator-strategy"""
    params = dict(MA_SLOW=8, MA_FAST=40)

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        high, low, close = self.data.loc[:, FILED.HLC]
        self.ma_slow = close.sma(self.params.MA_SLOW, overlap=True)
        self.ma_fast = close.sma(self.params.MA_FAST, overlap=True)
        kl_range_cur = (close.shift(2)-low.shift(2)
                        ).ZeroDivision(high.shift(2)-low.shift(2))
        kl_range_pre = (close.shift(3)-low.shift(3)
                        ).ZeroDivision(high.shift(3)-low.shift(3))
        kl_max = self.ma_slow.tqfunc.max(self.ma_fast)
        kl_min = self.ma_slow.tqfunc.min(self.ma_fast)
        self.long_signal = close.shift() > kl_max
        self.long_signal &= kl_range_pre <= 0.25
        self.long_signal &= kl_range_cur >= 0.75
        self.short_signal = close.shift() < kl_min
        self.short_signal &= kl_range_pre >= 0.75
        self.short_signal &= kl_range_cur <= 0.25
        self.long_signal.isplot = False
        self.short_signal.isplot = False

    def next(self):
        if not self.data.position:
            if self.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
