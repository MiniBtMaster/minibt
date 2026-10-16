from minibt import *


class Test(Strategy):
    config = Config(grid=True)

    def __init__(self):
        self.kline = LocalDatas.test.kline
        self.mlrsi = self.kline.tradingview.MachineLearningRSI()


if __name__ == "__main__":
    Bt(replay=True).run()
