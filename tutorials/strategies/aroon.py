import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
from minibt import *


class AroonStrategy(Strategy):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/aroon-strategy"""
    params = dict(AROON_PERIOD=10, AROON_UPPER_THRESHOLD=75,
                  AROON_LOWER_THRESHOLD=25)
    config = Config(islog=True)

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.test, height=500)
        self.aroon = self.data.aroon(self.params.AROON_PERIOD)
        self.long_signal = self.aroon.aroon_up > self.params.AROON_UPPER_THRESHOLD
        self.long_signal &= self.aroon.aroon_down < self.params.AROON_LOWER_THRESHOLD
        self.short_signal = self.aroon.aroon_down > self.params.AROON_UPPER_THRESHOLD
        self.short_signal &= self.aroon.aroon_up < self.params.AROON_LOWER_THRESHOLD
        self.long_signal.isplot = False
        self.short_signal.isplot = False
        self.data.fixed_commission = 1.

    def next(self):
        if not self.data.position:
            if self.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
