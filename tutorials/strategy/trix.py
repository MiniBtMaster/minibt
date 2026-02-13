from minibt import *


class TRIX(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/trix-strategy"""
    params = dict(TRIX_PERIOD=12, SIGNAL_PERIOD=9, MA_PERIOD=60)
    isplot = dict(long_signal=False, short_signal=False)

    def next(self):
        ema1 = self.close.ema(self.params.TRIX_PERIOD)
        ema2 = ema1.ema(self.params.TRIX_PERIOD)
        ema3 = ema2.ema(self.params.TRIX_PERIOD)
        trix = ema3.diff().ZeroDivision(ema3.shift())*100.
        signal = trix.sma(self.params.SIGNAL_PERIOD)
        long_signal = trix.cross_up(signal)
        short_signal = trix.cross_down(signal)
        return trix, signal, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.trix = TRIX(self.data)

    def next(self):
        if not self.data.position:
            if self.trix.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.trix.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
