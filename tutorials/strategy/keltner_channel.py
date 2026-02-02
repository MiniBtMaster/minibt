from minibt import *


class KeltnerChannel(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/trend-following/keltner-channel-strategy"""
    params = dict(EMA_PERIOD=8, ATR_PERIOD=7, ATR_MULTIPLIER=1.5,
                  SHORT_EMA_PERIOD=5, trend=0.5, mult=0.8)
    # isplot = dict(long_signal=False, short_signal=False)
    overlap = True

    def next(self):
        # 计算中轨（EMA）和短期EMA（用于趋势确认）
        ema = self.close.ema(self.params.EMA_PERIOD)
        ema_short = self.close.ema(self.params.SHORT_EMA_PERIOD)
        # 计算趋势方向和强度
        trend_direction = self.zeros().ifs(ema_short > ema, 1., ema_short < ema, -1.)
        trend_strength = (ema_short-ema).abs()/self.close*100.
        # 计算ATR
        tr = self.true_range()
        atr = tr.sma(self.params.ATR_PERIOD)

        # 动态调整ATR乘数，根据趋势强度调整通道宽度, 强趋势时使用更窄的通道
        dynamic_multiplier = self.full(self.params.ATR_MULTIPLIER).mask(
            trend_strength > 0.5, self.params.ATR_MULTIPLIER*0.8)
        # 计算通道上下轨
        upper_band = ema + dynamic_multiplier * atr
        lower_band = ema - dynamic_multiplier * atr
        long_signal = self.close > upper_band
        long_signal &= trend_direction > 0.
        short_signal = self.close < lower_band
        short_signal &= trend_direction < 0.
        return upper_band, lower_band, long_signal, short_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.trix = KeltnerChannel(self.data)

    def next(self):
        if not self.data.position:
            if self.trix.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.trix.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
