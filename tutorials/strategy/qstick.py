from minibt import *


class Qstick(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/qstick-strategy"""
    params = dict(QSTICK_PERIOD=10, SMA_PERIOD=8)
    overlap = True

    def next(self):
        # 计算Qstick指标
        qstick = (self.close-self.open).sma(self.params.QSTICK_PERIOD)
        # 计算价格SMA，用于确认趋势
        sma = self.close.sma(self.params.SMA_PERIOD)
        long_signal = qstick.cross_up(0.)
        long_signal &= self.close > sma
        short_signal = qstick.cross_down(0.)
        short_signal &= self.close < sma
        return qstick, sma, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.trix = Qstick(self.data)

    def next(self):
        if not self.data.position:
            if self.trix.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.trix.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
