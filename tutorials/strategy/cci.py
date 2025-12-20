from minibt import *


class CCI(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/mean-reversion/cci-strategy"""
    isplot = dict(long_signal=False, short_signal=False)
    params = dict(CCI_PERIOD=10, CCI_UPPER=100, CCI_LOWER=-100)

    def next(self):
        CCI_PERIOD = self.params.CCI_PERIOD  # CCI计算周期
        CCI_UPPER = self.params.CCI_UPPER  # CCI上轨
        CCI_LOWER = self.params.CCI_LOWER  # CCI下轨
        cci = self.close.cci(CCI_PERIOD)
        size = cci.size
        cci_state = self.ones
        for i in range(CCI_PERIOD+1, size):
            cci_state[i] = cci[i] > CCI_UPPER and 1. or (
                cci[i] < CCI_LOWER and -1. or cci[i-1])
        long_signal = cci_state.cross_up(0.)
        short_signal = cci_state.cross_down(0.)
        return cci, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.pp2601_60, height=500)
        self.cci = CCI(self.data)

    def next(self):
        if not self.data.position:
            if self.cci.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.cci.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
