"""7.7 · linestyle 全字段 —— 颜色 / 线宽 / 线型 / 价格线 / 价格标签

演示要点
--------
``PlotInfo.linestyle`` 是一个 ``{线名: LineStyle}`` 的字典，``LineStyle`` 有 9 个
字段，本例演示最常用的 5 个：

* ``line_color``  颜色（``Colors.*`` 或 ``'#rrggbb'``）；
* ``line_width``  线宽（数字，越大越粗）；
* ``line_dash``   线型（``LineDash.solid / dashed / dotted / large_dashed /
  sparse_dotted / dashdot / dotdash``）；
* ``price_line``  在**右侧价格轴**上画一条对应颜色的价格线；
* ``price_label`` 在右侧显示**价格标签**（跟着最后一根走）。

另外 4 个 ``vbar_*`` 字段是柱状线专用，见 [7.8](7.8_vbar.md)。

运行：``python tutorials/styles/07_linestyle.py``
文档：``minibt_docs/docs/minibt_styles/7.7_linestyle.md``
"""

import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class LineStyleDemo(BtIndicator):
    """4 条 EMA 叠在主图，用 4 种线型 / 线宽 / 颜色对比。"""

    lines = ('ema_10', 'ema_30', 'ema_60', 'ema_120')
    overlap = True                       # 全叠主图

    linestyle = dict(
        ema_10=LineStyle(line_color=Colors.orange, line_width=1.5,
                         line_dash=LineDash.solid),
        ema_30=LineStyle(line_color=Colors.blue, line_width=2,
                         line_dash=LineDash.dashed),
        ema_60=LineStyle(line_color=Colors.purple, line_width=2.5,
                         line_dash=LineDash.dotted),
        # 最慢的一条：加粗 + 价格线 + 价格标签（右轴会跟着它走）
        ema_120=LineStyle(line_color=Colors.green, line_width=3,
                          line_dash=LineDash.large_dashed,
                          price_line=True, price_label=True),
    )

    def next(self):
        return (self.close.ema(10),
                self.close.ema(30),
                self.close.ema(60),
                self.close.ema(120))


def main(gui=None):
    print('LineStyle 全部字段：',
          [f.name for f in dataclasses.fields(LineStyle)])

    kline = LocalDatas.test.kline
    ind = LineStyleDemo(kline)
    for name in ('ema_10', 'ema_30', 'ema_60', 'ema_120'):
        st = ind.plotinfo.linestyle[name]
        print(f'  {name:8s} color={st.line_color:8s} width={st.line_width} '
              f'dash={st.line_dash:12s} price_line={st.price_line} '
              f'price_label={st.price_label}')

    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
