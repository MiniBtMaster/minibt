from minibt import *


class Hull(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/hull-strategy"""
    params = dict(LONG_HMA_PERIOD=30, SHORT_HMA_PERIOD=5)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = True

    def _hma(self, period):
        half_period = period // 2
        sqrt_period = int(np.sqrt(period))
        wma1 = self.close.wma(half_period)
        wma2 = self.close.wma(period)

        raw_hma = 2 * wma1 - wma2

        return raw_hma.wma(sqrt_period)

    def next(self):
        short_hma = self._hma(self.params.SHORT_HMA_PERIOD)
        long_hma = self._hma(self.params.LONG_HMA_PERIOD)
        long_signal = short_hma.cross_up(long_hma)
        long_signal &= self.close > long_hma
        short_signal = short_hma.cross_down(long_hma)
        short_signal &= self.close < long_hma
        return short_hma, long_hma, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.trix = Hull(self.data)

    def next(self):
        if not self.data.position:
            if self.trix.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.trix.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
