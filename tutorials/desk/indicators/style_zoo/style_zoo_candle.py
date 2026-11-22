# -*- coding: utf-8 -*-
"""StyleZoo_Candle —— **蜡烛型指标**样例（`candlestyle` ✓）

指标输出 **open/high/low/close 四列** → 图表把它画成一串**小蜡烛**
（主图叠加或独立副图），涨跌配色来自类上的 `candlestyle`：

```python
candlestyle = CandleStyle(bull=Colors.lime, bear=Colors.tomato)
```

这里用"平滑后的 OHLC"（对收盘价的短均线做高低包络）当示例，方便肉眼看出
蜡烛形态，而不是重复主图的 K 线。
"""
from __future__ import annotations

import numpy as np

from minibt import BtIndicator
from minibt.utils import CandleStyle, Colors


def _sma(values, length: int):
    length = max(1, int(length))
    out = np.full(values.shape[0], np.nan)
    if values.shape[0] >= length:
        out[length - 1:] = np.convolve(
            values, np.ones(length) / length, mode='valid')
    return out


class StyleZoo_Candle(BtIndicator):
    """蜡烛型指标：四列 OHLC（平滑 K 线）"""

    lines = ('open', 'high', 'low', 'close')
    params = dict(length=5)
    overlap = True                     # 副图；改成 True 就叠到主图 ✓

    #: 涨 / 跌配色（只作用于这组蜡烛）✓
    candlestyle = CandleStyle(bull=Colors.lime, bear=Colors.tomato)

    def next(self):
        close = np.asarray(self.close.values, dtype=float)
        high = np.asarray(self.high.values, dtype=float)
        low = np.asarray(self.low.values, dtype=float)
        open_ = np.asarray(self.open.values, dtype=float)
        n = max(1, int(self.params.length))
        sm_open = _sma(open_, n)
        sm_close = _sma(close, n)
        sm_high = np.fmax(_sma(high, n), np.fmax(sm_open, sm_close))
        sm_low = np.fmin(_sma(low, n), np.fmin(sm_open, sm_close))
        return sm_open, sm_high, sm_low, sm_close
