"""02 · `BtIndicator` + 完整指标样式（desk 本地图表）

```bash
python tutorials/desk/gui/02_btindicator_style.py
```

演示 desk 能正确落地的 PlotInfo 样式：

| 写法 | desk 里看到的 |
| --- | --- |
| `overlap=True` | 主图叠加（`False` = 独立副图） |
| `LineStyle(line_color=…, line_width=…)` | 线颜色 / 线宽 |
| `line_dash=LineDash.dashed / dotdash / dotted` | 实线 / 虚线 / 点划线 |
| `signalstyle=SignalStyle(...)` | 买 / 卖箭头 + 固定文字 |
| `isplot=dict(long_signal=False)` | 信号列只画箭头、不当普通线画 |
| `legend=dict(xxx=False)` | 这一条不进左上角图例 |
| `price_line / price_label` | 右侧价格线 / 价格标签 |

> 色带 `bandstyle`、统计表 `tablestyle`、水印 `watermark` 属于 desk
> **指标目录**路径（见 `tutorials/desk/indicators/style_zoo/`）。
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
from minibt import (BtIndicator, Colors, Gui, LineDash, LineStyle,
                    LocalDatas, Markers, SignalStyle)


class DeskStyleDemo(BtIndicator):
    """双均线 + 交叉信号，颜色 / 线型 / 线宽 / 箭头全配好。"""

    lines = ('ma_fast', 'ma_slow', 'long_signal', 'short_signal')
    params = dict(fast=10, slow=30, cooldown=30)

    #: 全部画在主图（想让均线进副图就设 False）
    overlap = True

    linestyle = dict(
        ma_fast=LineStyle(line_color='#f6c343', line_width=2),
        ma_slow=LineStyle(line_color='#2196f3', line_width=2,
                          line_dash=LineDash.dashed),
    )

    #: 信号列只画箭头（不画成折线）
    isplot = dict(long_signal=False, short_signal=False)

    #: low = 画在 K 线下方；high = 上方；再带一个固定文字 ✓
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
    """金叉 / 死叉（带冷却期，避免一屏几十个箭头）。"""
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


if __name__ == '__main__':
    kline = LocalDatas.l2609_60.kline
    DeskStyleDemo(kline).btplot(gui=Gui.Desk)
