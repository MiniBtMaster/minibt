from minibt import Strategy


class SmaCrossStrategy(Strategy):
    """## 测试用无实际交易逻辑交易策略"""
    params = dict(symbol = "")

    def __init__(self):
        self.kline = self.get_kline(self.params.symbol)
        self.ma1=self.kline.close.sma(10)
        self.ma2=self.kline.close.sma(20)

    def next(self):
        print(f"{self.__class__.__name__}策略在运行：ma1:{self.ma1[-1]:0.2f},ma2:{self.ma1[-1]:0.2f}")
        if not self.kline.position.pos:
            ...


