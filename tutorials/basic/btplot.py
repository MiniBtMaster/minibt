import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
from minibt import *

if __name__ == "__main__":
    LocalDatas.test.kline.tradingview.UT_Bot_Alerts().btplot()