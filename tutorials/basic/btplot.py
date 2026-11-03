import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
from minibt import *
# desk加到图表测试
# from minibt.indicators.tradingview import UT_Bot_Alerts # noqa: F401

if __name__ == "__main__":
    LocalDatas.test.kline.tradingview.UT_Bot_Alerts().btplot()
    # desk加到图表测试
    # uba=UT_Bot_Alerts
    
