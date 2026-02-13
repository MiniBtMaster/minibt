from minibt import *


class VPT(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/vpt-strategy"""
    params = dict(VPT_MA_PERIOD=14, VOLUME_THRESHOLD=1.5,)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = False

    def next(self):
        size = self.V
        vpt = self.volume.copy(True)
        volume = self.volume.values
        close = self.close.values
        diff = self.close.diff().values
        for i in range(1, size):
            vpt[i] = vpt[i-1]+volume[i]*diff[i]/close[i-1]
        vpt_ma = vpt.sma(self.params.VPT_MA_PERIOD)
        avg_volume = self.volume.sma(self.params.VPT_MA_PERIOD)

        long_signal = vpt > vpt_ma
        long_signal &= self.close.diff() > 0.
        long_signal &= self.volume > (self.params.VOLUME_THRESHOLD*avg_volume)
        short_signal = vpt < vpt_ma
        short_signal &= self.close.diff() < 0.
        short_signal &= self.volume > (self.params.VOLUME_THRESHOLD*avg_volume)
        return vpt, vpt_ma, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.vpt = VPT(self.data)

    def next(self):
        if not self.data.position:
            if self.vpt.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.vpt.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
