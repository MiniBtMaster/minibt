from minibt import *


class Zscore(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/mean-reversion/zscore-strategy"""
    isplot = dict(long_signal=False, short_signal=False,
                  exitlong_signal=False, exitshort_signal=False)
    params = dict(WINDOW_SIZE=14, ENTRY_THRESHOLD=1.8,
                  EXIT_THRESHOLD=0.4, STOP_LOSS_THRESHOLD=2.5)

    def next(self):
        WINDOW_SIZE = self.params.WINDOW_SIZE  # Z-Score计算窗口期
        ENTRY_THRESHOLD = self.params.ENTRY_THRESHOLD  # 开仓阈值
        EXIT_THRESHOLD = self.params.EXIT_THRESHOLD  # 平仓阈值
        STOP_LOSS_THRESHOLD = self.params.STOP_LOSS_THRESHOLD  # 止损阈值
        zscore = self.close.zscore(WINDOW_SIZE)
        long_signal = zscore.cross_down(-ENTRY_THRESHOLD)
        short_signal = zscore.cross_up(ENTRY_THRESHOLD)
        exitlong_signal1 = self.ones.where((-EXIT_THRESHOLD <=
                                           zscore) & (zscore <= EXIT_THRESHOLD), 0.).astype(bool)
        exitlong_signal2 = self.ones.where(
            zscore < -STOP_LOSS_THRESHOLD, 0.).astype(bool)
        exitlong_signal = exitlong_signal1 | exitlong_signal2
        exitshort_signal1 = self.ones.where((-EXIT_THRESHOLD <=
                                            zscore) & (zscore <= EXIT_THRESHOLD), 0.).astype(bool)
        exitshort_signal2 = self.ones.where(
            zscore < -STOP_LOSS_THRESHOLD, 0.).astype(bool)
        exitshort_signal = exitshort_signal1 | exitshort_signal2
        return zscore, long_signal, short_signal, exitlong_signal, exitshort_signal


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.zscore = Zscore(self.data)

    def next(self):
        if not self.data.position:
            if self.zscore.long_signal.new:
                self.data.buy()
            elif self.zscore.short_signal.new:
                self.data.sell()
        elif self.data.position > 0 and self.zscore.exitlong_signal.new:
            self.data.sell()
        elif self.data.position < 0 and self.zscore.exitshort_signal.new:
            self.data.buy()


if __name__ == "__main__":
    Bt().run()
