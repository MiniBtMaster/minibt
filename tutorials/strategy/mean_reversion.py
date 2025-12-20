from minibt import *


class MeanReversion(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/mean-reversion/mean-reversion-strategy"""
    isplot = dict(long_signal=False, short_signal=False)
    params = dict(RSI_PERIOD=9, OVERBOUGHT=78, OVERSOLD=22,
                  BOLL_PERIOD=15, BOLL_DEV=2.5)
    overlap = dict(rsi=False, bb_lower=True, bb_upper=True,
                   ma_short=True, ma_long=True)

    def next(self):
        RSI_PERIOD = self.params.RSI_PERIOD  # RSI周期
        OVERBOUGHT = self.params.OVERBOUGHT  # 超买阈值
        OVERSOLD = self.params.OVERSOLD  # 超卖阈值
        BOLL_PERIOD = self.params.BOLL_PERIOD  # 布林带周期
        BOLL_DEV = self.params.BOLL_DEV  # 布林带标准差倍数
        # 计算指标
        rsi = self.close.rsi(RSI_PERIOD)
        boll = self.close.bbands(BOLL_PERIOD, BOLL_DEV)
        bb_lower = boll.bb_lower
        bb_upper = boll.bb_upper
        # 加入MA趋势过滤
        ma_short = self.close.sma(20)  # 20小时均线
        ma_long = self.close.sma(60)  # 60小时均线
        trend_up = ma_short.shift() > ma_long.shift()
        trend_down = ma_short.shift() < ma_long.shift()

        long_signal = rsi < OVERSOLD
        long_signal &= self.close < bb_lower
        long_signal &= trend_down

        short_signal = rsi > OVERBOUGHT
        short_signal &= self.close < bb_upper
        short_signal &= trend_up
        return rsi, bb_lower, bb_upper, ma_short, ma_long, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.mean_reversion = MeanReversion(self.data)

    def next(self):
        if not self.data.position:
            if self.mean_reversion.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.mean_reversion.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
