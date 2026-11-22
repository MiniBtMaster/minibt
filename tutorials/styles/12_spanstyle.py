"""7.12 · spanstyle —— 水平分界线（价格位）

演示要点
--------
``PlotInfo.spanstyle`` 是一个 ``SpanStyle`` 列表，在图上画出**整宽的水平线**：

| 字段 | 默认 | 作用 |
| --- | --- | --- |
| ``location`` | ``nan`` | **价格**（水平线画在这个价位） |
| ``line_color`` | ``'#666666'`` | 线色 |
| ``line_dash`` | ``'dashed'`` | 线型：``solid`` / ``dashed`` / ``dotted`` / ``large_dashed`` / ``sparse_dotted`` |
| ``line_width`` | ``0.8`` | 线宽 |
| ``dimension`` | ``'width'`` | 方向；**pylightcharts 目前只画水平线**（bokeh 侧同样按 ``width`` 画） |

水平线很适合标：支撑 / 阻力、超买超卖阈值（RSI 30/70）、目标价、成本线。

运行：``python tutorials/styles/12_spanstyle.py``
文档：``minibt_docs/docs/minibt_styles/7.12_spanstyle.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class SpanDemo(BtIndicator):
    """两条均线 + 3 条水平分界线（4800 / 5000 / 5200）。"""

    lines = ('ema_fast', 'ema_slow')
    overlap = True

    linestyle = dict(
        ema_fast=LineStyle(line_color=Colors.orange, line_width=1.5),
        ema_slow=LineStyle(line_color=Colors.blue, line_width=1.5),
    )

    # 3 条水平线：颜色 / 线型 / 宽度各不同
    spanstyle = [
        SpanStyle(location=4800, line_color=Colors.green,
                  line_dash='dotted', line_width=2),
        SpanStyle(location=5000, line_color=Colors.red,
                  line_dash='dashed', line_width=2),      # 关键位
        SpanStyle(location=5200, line_color=Colors.purple,
                  line_dash='solid', line_width=1),
    ]

    def next(self):
        return self.close.ema(20), self.close.ema(60)


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = SpanDemo(kline)
    for i, span in enumerate(ind.plotinfo.spanstyle):
        print(f'  span[{i}] location={span.location} color={span.line_color:8s} '
              f'dash={span.line_dash:8s} width={span.line_width} '
              f'dimension={span.dimension}')
    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
