from minibt import *


class Aroon(Strategy):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/aroon-strategy"""
    params = dict(AROON_PERIOD=10, AROON_UPPER_THRESHOLD=75,
                  AROON_LOWER_THRESHOLD=25)

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.aroon = self.data.aroon(self.params.AROON_PERIOD)
        self.long_signal = self.aroon.aroon_up > self.params.AROON_UPPER_THRESHOLD
        self.long_signal &= self.aroon.aroon_down < self.params.AROON_LOWER_THRESHOLD
        self.short_signal = self.aroon.aroon_down > self.params.AROON_UPPER_THRESHOLD
        self.short_signal &= self.aroon.aroon_up < self.params.AROON_LOWER_THRESHOLD
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
