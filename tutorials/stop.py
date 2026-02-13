from minibt import *


class ATRDynamicStop(Stop):
    """基于ATR的动态止损止盈策略"""

    def __init__(self, atr_length: int = 14, atr_mult: float = 1.0):
        # 初始化参数
        self.atr_length = atr_length
        self.atr_mult = atr_mult
        # 前置计算ATR指标（核心能力1）
        self._atr = self.kline.atr(self.atr_length)  # 全量KLine访问（核心能力2）

    def long(self):
        """多头ATR动态止损止盈（核心能力3+4）"""
        # 计算多头止损价：最新最低价 - ATR*乘数
        if np.isnan(self.stop_price[-2]):
            stop_price = self.low[-1] - self.atr_mult * self._atr[-1]
        else:
            stop_price = self.stop_price[-2]
        # 计算多头止盈价：开仓价 + 2倍止损空间
        if np.isnan(self.target_price[-2]):
            target_price = self.kline.open_price + \
                (self.kline.open_price - stop_price) * 2
        else:
            target_price = self.target_price[-2]
        # 赋值停止价/目标价
        self.stop_price.new = stop_price
        self.target_price.new = target_price

    def short(self):
        """空头ATR动态止损止盈（核心能力3+5）"""
        # 计算空头止损价：最新最高价 + ATR*乘数
        if np.isnan(self.stop_price[-2]):
            stop_price = self.high[-1] + self.atr_mult * self._atr[-1]
        else:
            stop_price = self.stop_price[-2]
        # 计算空头止盈价：开仓价 - 2倍止损空间
        if np.isnan(self.target_price[-2]):
            target_price = self.kline.open_price - \
                (stop_price - self.kline.open_price) * 2
        else:
            target_price = self.target_price[-2]
        # 赋值停止价/目标价
        self.stop_price.new = stop_price
        self.target_price.new = target_price


class owen(Strategy):
    config = Config(islog=False, print_account=True,
                    take_time=True, islogorder=False)
    params = dict(symbol="v2601_300")

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(
            LocalDatas.get(self.params.symbol), height=400).iloc[:]
        self.ma5 = self.data.close.sma(5)
        self.ma10 = self.data.close.sma(10)
        self.long_signal = self.ma5.cross_up(self.ma10)
        self.short_signal = self.ma5.cross_down(self.ma10)

    def next(self):
        if not self.data.position:
            if self.long_signal.new:
                self.data.buy(exectype=OrderType.Market,
                              stop=ATRDynamicStop)
            elif self.short_signal.new:
                self.data.sell(exectype=OrderType.Market,
                               stop=ATRDynamicStop)


if __name__ == "__main__":
    Bt().run()
