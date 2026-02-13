from minibt import *


class Vortex(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/vortex-indicator-strategy"""
    params = dict(VI_PERIOD=14, ATR_PERIOD=14, VI_THRESHOLD=1.0,)
    isplot = dict(long_signal=False, short_signal=False)

    def next(self):
        tr = self.true_range()
        # 计算正向涡旋运动(+VM)
        plus_vm = (self.high-self.low.shift()).abs()
        # 计算负向涡旋运动(-VM)
        minus_vm = (self.low-self.high.shift()).abs()
        # 计算N周期内的总和
        tr_sum = tr.rolling(self.params.ATR_PERIOD).sum()
        plus_vm_sum = plus_vm.rolling(self.params.ATR_PERIOD).sum()
        minus_vm_sum = minus_vm.rolling(self.params.ATR_PERIOD).sum()
        # 计算涡旋指标
        plus_vi = plus_vm_sum/tr_sum
        minus_vi = minus_vm_sum/tr_sum
        long_signal = plus_vi.cross_up(minus_vi)
        long_signal &= plus_vi > self.params.VI_THRESHOLD
        short_signal = minus_vi.cross_up(plus_vi)
        short_signal &= minus_vi > self.params.VI_THRESHOLD
        return plus_vi, minus_vi, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.trix = Vortex(self.data)

    def next(self):
        if not self.data.position:
            if self.trix.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.trix.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
