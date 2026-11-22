"""8.9 · 从零写一个自定义指标（完整版）

演示要点
--------
一个自定义指标 = **继承 `BtIndicator`** + 写 `next()`：

```python
class MyInd(BtIndicator):
    lines = ('fast', 'slow', 'long_signal')     # 输出列（顺序 = return 顺序）
    params = dict(FAST=10, SLOW=30)             # 参数（self.params.FAST）
    overlap = dict(fast=True, slow=True)        # 主图/副图
    isplot = dict(long_signal=False)            # 信号线不画折线
    linestyle = {...}                           # 线型
    signalstyle = {...}                         # 信号样式
    def next(self):
        ...
        return fast, slow, fast.cross_up(slow)
```

**关键规则**

| 事项 | 说明 |
| --- | --- |
| `next()` 里的 `self` | 是**源 K 线**（`self.close` / `self.high` 都能用） |
| `lines` 顺序 | 必须和 `return` 顺序一致（[7.2](../minibt_styles/7.2_lines.md)） |
| `params` | 实例上是 `self.params.FAST`；类上是 `cls.params` |
| 预热 NaN | 指标前 N 个 NaN 是正常的（`idx()` 找第一个有效值） |
| 自动解析 | 不写 `lines` 会从 `return` 猜名字（不推荐，见 7.2） |

运行：``python tutorials/indicators/09_custom_indicator.py``
文档：``minibt_docs/docs/minibt_indicators/8.9_custom_indicator.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class MyChannel(BtIndicator):
    """均线通道（上/中/下）+ 突破信号 —— 一个完整的自定义指标。"""

    lines = ('upper', 'middle', 'lower', 'long_signal', 'short_signal')
    params = dict(LEN=20, BAND=0.02)

    # 三条通道线在主图；信号线不画折线
    overlap = dict(upper=True, middle=True, lower=True)
    isplot = dict(long_signal=False, short_signal=False)

    linestyle = dict(
        upper=LineStyle(line_color=Colors.blue, line_width=1.2),
        middle=LineStyle(line_color=Colors.orange, line_width=2,
                         line_dash=LineDash.dashed),
        lower=LineStyle(line_color=Colors.blue, line_width=1.2),
    )
    bandstyle = [BandStyle(lower='lower', upper='upper',
                           fill_color='#4dabf7', fill_alpha=0.12)]
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red,
                                Markers.triangle).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle).set_label('S'),
    )

    def next(self):
        p = self.params                      # ← 参数直接用属性取
        middle = self.close.ema(p.LEN)       # ← self 是源 K 线
        upper = middle * (1 + p.BAND)
        lower = middle * (1 - p.BAND)
        return (upper, middle, lower,
                self.close.cross_up(upper),
                self.close.cross_down(lower))


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = MyChannel(kline)

    print('① 类型:', type(ind).__name__, '| isMDim:', ind.isMDim,
          '| len:', len(ind))
    print('② lines:', list(ind.lines), '| sname:', ind.sname)
    print('③ params:', dict(ind.params or {}))
    print('④ 通道最后值: upper', round(float(ind.upper[-1]), 2),
          '| middle', round(float(ind.middle[-1]), 2),
          '| lower', round(float(ind.lower[-1]), 2))
    print('⑤ 信号点个数: long', len(ind.long_signal.idx()),
          '| short', len(ind.short_signal.idx()))
    info = ind.plotinfo
    print('⑥ plotinfo: overlap=', info.overlap, '| isplot=', info.isplot)
    print('   bandstyle=', [(b.lower, b.upper) for b in info.bandstyle])

    # ⑦ 直接用（策略里 self.my = MyChannel(self.data)），也能看图
    print('⑦ ind.btplot(...) 可出图（第 7 章）')


if __name__ == '__main__':
    main()
