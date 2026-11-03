"""9.6 · Line —— 单条线对象

演示要点
--------
`Line` 是"单条线"：`kline.close`、`macd.macdx`、`ind.long_signal` 都是它。

| 组 | 成员 |
| --- | --- |
| **线型** | `line_style` / `line_color` / `line_dash` / `line_width` / `price_line` / `price_label` |
| **显隐** | `isplot` / `overlap` / `follow`（都与父级同步） |
| **信号线专用** | `signal_color` / `signal_marker` / `signal_size` / `signal_label` / `signal_show` / `signal_key` / `signal_style` / `set_label()` |
| **来源** | `source`（父级数据）、`sname`（线名） |
| 继承自 `IndicatorsBase`/`IndSeries` | `new` / `prev` / `shift` / `idx` / `cross_up` / `signal_profit` … |

运行：``python tutorials/data/06_line.py``
文档：``minibt_docs/docs/minibt_data/9.6_line.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 一条普通线
    line = kline.close
    print('① 类型:', type(line).__name__, '| sname:', line.sname,
          '| source:', type(line.source).__name__)
    print('   isplot:', line.isplot, '| overlap:', line.overlap,
          '| follow:', line.follow)
    print('   prev/new:', line.prev, '|', line.new)

    # ② 线型（写回父级 PlotInfo）
    line.line_color = Colors.orange
    line.line_width = 2
    line.line_dash = LineDash.dashed
    print('② line_style:', line.line_style)

    # ③ 价格线 / 价格标签
    line.price_line = True
    line.price_label = True
    print('③ price_line/price_label:', line.price_line, line.price_label)

    # ④ 指标输出的 Line
    macd = kline.macd()
    print('④ macd.macdx ->', type(macd.macdx).__name__,
          '| sname:', macd.macdx.sname)

    # ⑤ 信号线（Line 专属的一套 signal_*）
    ind = kline.tradingview.SingleEMACross(ema1=10, ema2=20)
    sig = ind.long_signal
    print('⑤ 信号线:', sig.sname,
          '| signal_color:', sig.signal_color,
          '| signal_marker:', sig.signal_marker,
          '| signal_size:', sig.signal_size)
    print('   signal_key(锚定列):', sig.signal_key)

    # ⑥ 快捷设标签
    sig.set_label('B', size=12)
    print('⑥ set_label("B") -> signal_label:', sig.signal_label)

    # ⑦ 隐藏信号
    sig.signal_show = False
    print('⑦ signal_show:', sig.signal_show)
    sig.signal_show = True

    # ⑧ 线也是 IndSeries 的子类 → 指标/信号收益都能用
    print('⑧ isinstance(sig, Line):', isinstance(sig, Line),
          '| sig.idx()[:3]:', sig.idx()[:3])


if __name__ == '__main__':
    main()
