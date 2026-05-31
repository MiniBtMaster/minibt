from minibt import *


class StepStrategy(Strategy):

    def __init__(self):
        self.kline = self.get_kline(LocalDatas.v2601_300, height=400)
        self.utbot = self.kline.tradingview.UT_Bot_Alerts()

    def next(self):
        self.utbot.step()


if __name__ == "__main__":
    Bt().run()
