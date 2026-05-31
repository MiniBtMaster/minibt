from minibt import *


class OPTStrategy(Strategy):
    params = dict(len1=8, len2=16, a=1., c=10)

    def __init__(self) -> None:
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.ma1 = self.data.sma(self.params.len1)
        self.ma2 = self.data.sma(self.params.len2)

        self.utbot = self.data.tradingview.UT_Bot_Alerts(
            a=self.params.a, c=self.params.c)
        self.long_signal = self.ma1 > self.ma2
        self.short_signal = self.ma1 < self.ma2

    def next(self):
        if not self.data.position:
            if self.long_signal.new and self.utbot.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.short_signal.new and self.utbot.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    bt = Bt()
    bt.optstrategy(['profit', 'sharpe', 'max_drawdown'],
                   (1., 1., 1.), opconfig=OptunaConfig(n_trials=10), op_method='optuna', show_bar=True,
                   len1=(5, 21, 1), len2=(10, 31, 1), a=(0.5, 3., 0.1), c=(5, 31, 1), skip=False)
    bt.run()
