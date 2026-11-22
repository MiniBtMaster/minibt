import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
from minibt import *


class ReplayStrategy(Strategy):
    params = dict(symbol="test")

    def __init__(self):
        self.data = self.get_kline(
            LocalDatas.get(self.params.symbol), height=400)
        self.data.fixed_commission=1.
        self.ma = self.data.close.t3()
        self.pmax = self.data.close.btind.pmax3()
        self.pmax.thrend.isplot = False
        self.macd = self.data.close.macd()
        self.test = self.data.tradingview.UT_Bot_Alerts()
        self.test.long_signal.isplot = False
        self.test.short_signal.isplot = False

    def next(self):
        if not self.data.position:
            if self.test.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.test.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


ReplayStrategy1 = ReplayStrategy.copy(params=dict(symbol="l2609_60"))
if __name__ == "__main__":
    Bt(replay=True).run()