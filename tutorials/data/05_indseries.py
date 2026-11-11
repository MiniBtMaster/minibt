"""9.5 · IndSeries —— 单列指标对象

演示要点
--------
`IndSeries` 是"一维指标"：`kline.close.ema(20)`、`kline['close']`、
`kline.close.cross_up(...)` 等都返回它。

它继承 `Series`（pandas 方法都能用），另外多了一层**绘图样式**：

| 组 | 成员 |
| --- | --- |
| **样式** | `line_style` / `line_color` / `line_dash` / `line_width` / `price_line` / `price_label` |
| **信号** | `idx()`（信号点下标）/ `signal_profit()`（单信号收益曲线） |
| 继承自 `IndicatorsBase` | `new` / `prev` / `shift` / `rolling` / `cross_up` / `cross_down` / `btplot` / `kline` … |

运行：``python tutorials/data/05_indseries.py``
文档：``minibt_docs/docs/minibt_data/9.5_indseries.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline
    close = kline.close

    # ① 从哪来
    ema = close.ema(20)
    print('① close.ema(20) ->', type(ema).__name__,
          '| len:', len(ema), '| sname:', ema.sname)
    print('   前 3 个值:', [round(float(v), 2) for v in ema[:3]],
          '（EMA(20) 前 19 个是 NaN）')
    print('   最后 1 个:', round(float(ema[-1]), 2),
          '| new:', round(float(ema.new), 2),
          '| prev:', round(float(ema.prev), 2))

    # ② 信号点下标（idx）
    print('② ema.idx()[:5] ->', ema.idx()[:5], '（有效值下标）')

    # ③ 时间序列运算（返回同类对象）
    print('③ ema.shift(1)[-1] ->', round(float(ema.shift(1)[-1]), 2))
    print('   (ema + 1) ->', type(ema + 1).__name__,
          '| (ema > close) ->', type(ema > close).__name__)

    # ④ 交叉（返回 0/1 的 IndSeries）
    cross = close.cross_up(ema)
    print('④ close.cross_up(ema) ->', type(cross).__name__,
          '| 前 5 个信号点:', cross.idx()[:5])

    # ⑤ 单信号收益曲线（isplot=False 不出图）
    prof = cross.signal_profit(bar=5, isplot=False)
    print('⑤ cross.signal_profit(bar=5) ->', type(prof).__name__,
          '| keys:', list(prof)[:4])

    # ⑥ 绘图样式（直接写回 PlotInfo）
    ema.line_color = Colors.red
    ema.line_width = 2
    ema.line_dash = LineDash.dashed
    ema.price_line = True
    print('⑥ line_style:', ema.line_style)

    # ⑦ 底层 pandas 对象
    print('⑦ ema.pandas_object ->', type(ema.pandas_object).__name__)


if __name__ == '__main__':
    main()
