
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
from minibt import *
class CCI(BtIndicator):
    isplot = dict(long_signal=False, short_signal=False)
    params = dict(CCI_PERIOD=10, CCI_UPPER=100, CCI_LOWER=-100)
    def next(self):
        CCI_PERIOD = self.params.CCI_PERIOD
        CCI_UPPER = self.params.CCI_UPPER
        CCI_LOWER = self.params.CCI_LOWER
        cci = self.close.cci(CCI_PERIOD)
        size = cci.size
        cci_state = self.ones
        for i in range(CCI_PERIOD+1, size):
            cci_state[i] = cci[i] > CCI_UPPER and 1. or (cci[i] < CCI_LOWER and -1. or cci[i-1])
        long_signal = cci_state.cross_up(0.)
        short_signal = cci_state.cross_down(0.)
        return cci, long_signal, short_signal
