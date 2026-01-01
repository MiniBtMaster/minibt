from minibt import *


class RSI(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/mean-reversion/rsi-strategy"""
    isplot = dict(long_signal=False, short_signal=False)
    params = dict(RSI_PERIOD=6, OVERBOUGHT_THRESHOLD=65, OVERSOLD_THRESHOLD=35)

    def next(self):
        RSI_PERIOD = self.params.RSI_PERIOD  # RSI计算周期，
        OVERBOUGHT_THRESHOLD = self.params.OVERBOUGHT_THRESHOLD  # 超买阈值
        OVERSOLD_THRESHOLD = self.params.OVERSOLD_THRESHOLD  # 超卖阈值
        rsi = self.close.rsi(RSI_PERIOD)
        long_signal = rsi.cross_up(OVERSOLD_THRESHOLD)
        short_signal = rsi.cross_down(OVERBOUGHT_THRESHOLD)
        return rsi, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.rsi = RSI(self.data)

    def next(self):
        if not self.data.position:
            if self.rsi.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.rsi.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
