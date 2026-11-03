"""7.10 · signalstyle —— 信号图标、颜色、大小、文字标签

演示要点
--------
``PlotInfo.signalstyle`` 是 ``{信号线: SignalStyle}``。``SignalStyle`` 字段：

| 字段 | 默认 | 作用 |
| --- | --- | --- |
| ``key`` | ``None`` | **锚定价格**：``'low'``（画在 K 线下方）/ ``'high'``（上方）/ ``'close'`` |
| ``color`` | ``None`` | 图标颜色 |
| ``marker`` | ``None`` | 图标形状（``Markers.*``） |
| ``overlap`` | ``True`` | 信号画在主图还是副图 |
| ``show`` | ``True`` | ``False`` = **不画这个信号**（配置留着） |
| ``size`` | ``12.0`` | 图标大小 |
| ``label`` | ``False`` | 文字标签（``set_label('B')`` 一次设置） |

四个**保留信号名**：``long_signal`` / ``exitlong_signal`` / ``short_signal`` /
``exitshort_signal``（见 [7.2](7.2_lines.md)），每个可以配不同的图标。

本例：开多 / 开空用大三角 + 文字；平多用**不带文字的小圆叉**（价格跌破 120 期
均线才画，比较稀）；**平空故意 ``show=False``** —— 它配好了、但不画，
图例里也看不到（演示这个开关）。

运行：``python tutorials/styles/10_signalstyle.py``
文档：``minibt_docs/docs/minibt_styles/7.10_signalstyle.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class SignalStyleDemo(BtIndicator):
    """进场用均线交叉，出场用价格跌破/升破快线。"""

    lines = ('ema_fast', 'ema_slow',
             'long_signal', 'exitlong_signal', 'short_signal',
             'exitshort_signal')
    params = dict(FAST=10, SLOW=30)

    overlap = dict(ema_fast=True, ema_slow=True)
    isplot = dict(long_signal=False, exitlong_signal=False,
                  short_signal=False, exitshort_signal=False)

    linestyle = dict(
        ema_fast=LineStyle(line_color=Colors.orange, line_width=1.5),
        ema_slow=LineStyle(line_color=Colors.blue, line_width=1.5),
    )

    # 4 个信号：形状 / 颜色 / 大小 / 标签各不相同
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle,
                                size=14).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle,
                                 size=14).set_label('S'),
        # 出场信号不写文字（只留小图标，避免和 B/S 挤在一起）
        exitlong_signal=SignalStyle('high', Colors.orange, Markers.circle_x,
                                    size=9),
        # show=False：配好了、但不画（图例里也不出现）—— 演示这个开关
        exitshort_signal=SignalStyle('low', Colors.blue, Markers.circle,
                                     size=9, show=False),
    )

    def next(self):
        p = self.params
        fast = self.close.ema(p.FAST)
        slow = self.close.ema(p.SLOW)
        return (fast, slow,
                fast.cross_up(slow),                       # 开多：均线金叉
                self.close.cross_down(self.close.ema(120)),  # 平多：跌破慢趋势线
                fast.cross_down(slow),                     # 开空：均线死叉
                self.close.cross_up(self.close.ema(120)))  # 平空（show=False）


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = SignalStyleDemo(kline)
    for name, st in ind.plotinfo.signalstyle.items():
        label = getattr(st.label, 'text', st.label)
        print(f'  {name:17s} key={str(st.key):5s} marker={str(st.marker):18s} '
              f'size={st.size:<4} label={str(label):3s} show={st.show}')
    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
