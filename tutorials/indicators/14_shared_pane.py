"""8.14 · 指标组合与共享副图

演示要点
--------
默认**一个指标 = 一个副图**（[7.15](../minibt_styles/7.15_source.md)）。想让
**两个指标挤进同一个副图**，把它们的 `plotinfo.source` 设成**同一个非空值**：

```python
a = OscA(kline);  a.plotinfo.source = 'shared'
b = OscB(a);      b.plotinfo.source = 'shared'
b.btplot()        # → A、B 的线都在**同一个副图**
```

这在"同一个量纲的多个振荡器"（如 RSI + 它的均线 + 平滑版）里很常用：
不占两个副图、对比更直观。

| 组合方式 | 用 |
| --- | --- |
| 同一指标多列（天然同图） | `lines = ('a', 'b', 'c')` |
| **两个指标共享副图** | 两边设同一个 `plotinfo.source` |
| 叠到主图 | `overlap = True`（量纲要一致） |

运行：``python tutorials/indicators/14_shared_pane.py``
文档：``minibt_docs/docs/minibt_indicators/8.14_shared_pane.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class OscA(BtIndicator):
    """偏离率 + 信号线（默认一个副图）。"""

    lines = ('osc', 'signal')
    overlap = False
    params = dict(LEN=20, SIG=9)
    linestyle = dict(
        osc=LineStyle(line_color=Colors.orange, line_width=1.6),
        signal=LineStyle(line_color=Colors.blue, line_width=1.2,
                         line_dash=LineDash.dashed),
    )

    def next(self):
        p = self.params
        ma = self.close.ema(p.LEN)
        osc = (self.close - ma) / ma * 100
        return osc, osc.ema(p.SIG)


class OscB(BtIndicator):
    """把 OscA 的 osc 再平滑一次。"""

    lines = ('smooth',)
    overlap = False
    linestyle = dict(smooth=LineStyle(line_color=Colors.purple,
                                      line_width=1.8))

    def next(self):
        return self.osc.ema(21)


def main(gui=None):
    kline = LocalDatas.test.kline
    a = OscA(kline)
    b = OscB(a)

    print('① 默认 source：A =', repr(a.plotinfo.source),
          '| B =', repr(b.plotinfo.source), '→ 两个副图')

    # ② 设成同一个 source → 合并成一个副图
    a.plotinfo.source = 'shared'
    b.plotinfo.source = 'shared'
    print('② 设置后：A =', repr(a.plotinfo.source),
          '| B =', repr(b.plotinfo.source), '→ 一个副图（3 条线）')

    b.btplot(gui=gui)


if __name__ == '__main__':
    main()
