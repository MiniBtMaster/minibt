from minibt import *


class ReplayStrategy(Strategy):
    params = dict(symbol="v2601_300")

    def __init__(self):
        self.data = self.get_kline(
            LocalDatas.get(self.params.symbol), height=400)
        self.ma = self.data.close.t3()
        self.pmax = self.data.close.btind.pmax3()
        self.macd = self.data.close.macd()
        self.test = self.data.tradingview.UT_Bot_Alerts()

    def next(self):
        if not self.data.position:
            if self.test.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.test.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


ReplayStrategy1 = ReplayStrategy.copy(params=dict(symbol="v2601_60"))
if __name__ == "__main__":
    Bt(replay=True).run(period_milliseconds=1000)
