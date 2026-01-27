from minibt import *


class CMO(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/cmo-strategy"""
    params = dict(CMO_PERIOD=6, SIGNAL_PERIOD=4, CMO_SLOPE_PERIOD=2,
                  OVERBOUGHT_THRESHOLD=50, OVERSOLD_THRESHOLD=-50, SMA_PERIOD=10)
    isplot = dict(cmo_slope=False, long_signal=False, short_signal=False)
    overlap = dict(sma=True, cmo=False, cmo_signal=False)

    def next(self):
        cmo = self.close.cmo(self.params.CMO_PERIOD)
        cmo_signal = cmo.sma(self.params.SIGNAL_PERIOD)
        cmo_slope = cmo.diff(self.params.CMO_SLOPE_PERIOD)
        sma = self.close.sma(self.params.SMA_PERIOD)
        long_signal = cmo.cross_up(self.params.OVERSOLD_THRESHOLD)
        long_signal |= cmo.cross_up(cmo_signal)
        long_signal |= cmo.cross_up(0.)
        short_signal = cmo.cross_down(self.params.OVERBOUGHT_THRESHOLD)
        short_signal |= cmo.cross_down(cmo_signal)
        short_signal |= cmo.cross_down(0.)

        return sma, cmo, cmo_signal, cmo_slope, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.trix = CMO(self.data)

    def next(self):
        if not self.data.position:
            if self.trix.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.trix.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
