import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
from minibt import *


class Test(Strategy):
    config = Config(grid=True)

    def __init__(self):
        self.kline = self.get_kline("SHFE.ag2612")
        # self.kline = self.get_kline(LocalDatas.test)
        self.mlrsi = self.kline.tradingview.MachineLearningRSI()


if __name__ == "__main__":
    Bt(replay=True).run()
