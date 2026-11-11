"""03 · 策略「加到图表」（desk 本地图表，指标带样式）

```bash
python tutorials/desk/gui/03_strategy_local_chart.py
```

发生什么
--------
1. desk 用**本地图表**打开一张空图；
2. 策略里写的是 `get_kline(LocalDatas.l2609_60)`，desk 自动：
   选单图布局 → 加载 `DCE.l2609_60.csv` → 运行策略；
3. 策略里的指标（`DeskMa`，带颜色 / 虚线 / 箭头样式）被「加到图表」；
4. 之后可以点 ▶▶ 回放，看它逐根下单（本地模拟账户）。

> `desk_mode='chart'` = 只加到图表、不自动打开回测页
> （要回测见 `04_backtest_local_chart.py`）。
"""
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import numpy as np
import pandas as pd

from minibt import *                      # noqa: F401,F403
from minibt import (BtIndicator, Colors, Config, Gui, LineDash, LineStyle,
                    LocalDatas, Markers, SignalStyle, Strategy)


class DeskMa(BtIndicator):
    """双均线 + 交叉箭头：颜色 / 线型 / 线宽 / 箭头都写在这里。"""

    lines = ('fast', 'slow', 'long_signal', 'short_signal')
    params = dict(fast=10, slow=30, cooldown=30)
    overlap = True
    isplot = dict(long_signal=False, short_signal=False)

    linestyle = dict(
        fast=LineStyle(line_color='#f6c343', line_width=2),
        slow=LineStyle(line_color='#2196f3', line_width=2,
                       line_dash=LineDash.dashed),
    )
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.lime, Markers.arrow_up,
                                size=12).set_label('B', 11, color='#26a69a'),
        short_signal=SignalStyle('high', Colors.tomato, Markers.arrow_down,
                                 size=12).set_label('S', 11, color='#ef5350'),
    )

    def next(self):
        close = np.asarray(self.close.values, dtype=float)
        fast = pd.Series(close).rolling(int(self.params.fast)).mean().to_numpy()
        slow = pd.Series(close).rolling(int(self.params.slow)).mean().to_numpy()
        diff = fast - slow
        prev = np.concatenate(([np.nan], diff[:-1]))
        long_signal = _cross(diff, prev, up=True,
                             cooldown=int(self.params.cooldown))
        short_signal = _cross(diff, prev, up=False,
                              cooldown=int(self.params.cooldown))
        return fast, slow, long_signal, short_signal


def _cross(diff, prev, up=True, cooldown=30):
    out = np.zeros(len(diff), dtype=float)
    last = -10 ** 9
    for index in range(1, len(diff)):
        if not np.isfinite([diff[index], prev[index]]).all():
            continue
        crossed = (prev[index] <= 0 < diff[index]) if up \
            else (prev[index] >= 0 > diff[index])
        if crossed and index - last >= max(1, int(cooldown)):
            out[index] = 1.0 if up else -1.0
            last = index
    return out


class LocalMaCross(Strategy):
    """金叉多 1 手、死叉平仓；指标 `DeskMa` 带样式一起上屏。"""

    config = Config(value=1_000_000.0, margin_rate=0.05,
                    fixed_commission=1.0)
    params = dict(size=1)

    def __init__(self):
        self.min_start_length = 30
        self.data = self.get_kline(LocalDatas.l2609_60)
        # ★ 指标作为属性 → 自动登记给策略，desk「加到图表」时按样式画 ✓
        self.ma = DeskMa(self.data)

    def next(self):
        fast = self.ma.fast.new
        slow = self.ma.slow.new
        if not np.isfinite([fast, slow]).all():     # 均线预热期
            return
        position = float(getattr(self.data.position, 'pos',
                                 self.data.position) or 0.0)
        if self.ma.long_signal.new and position <= 0:
            self.data.set_target_size(self.params.size)
        elif self.ma.short_signal.new and position > 0:
            self.data.set_target_size(0)


if __name__ == '__main__':
    # ★ desk 界面：本地图表「加到图表」（不自动打开回测页）
    bt = Bt(auto=False)                 # auto=False：只跑本文件的策略
    bt.addstrategy(LocalMaCross)
    bt.run(gui=Gui.Desk, desk_mode='chart')
