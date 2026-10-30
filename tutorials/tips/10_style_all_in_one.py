"""5.10 · 样式速查（一张图里塞满常用样式）

演示要点
--------
一页看完常用样式怎么组合。本例同时用了：

* ``overlap`` 逐线分主/副（均线主图、振荡器副图）；
* ``linestyle`` 的 颜色 / 线宽 / 线型 / 价格线 / 价格标签；
* ``bandstyle`` 两线之间填充；
* ``spanstyle`` 关键价位水平线；
* ``signalstyle`` 信号图标 + 文字标签；
* ``legend`` 只隐藏其中一条线的图例行；
* ``isplot`` 关掉"仅数据"的列。

字段的完整说明在 **第 7 章 图表样式**，这里只做"速查 + 一张图看全"。

运行：``python tutorials/tips/10_style_all_in_one.py``
文档：``minibt_docs/docs/minibt_tips/5.10_style_cheatsheet.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class StyleAllInOne(BtIndicator):
    """BOLL 通道 + 振荡器 + 突破信号，一次用满常用样式。"""

    lines = ('upper', 'middle', 'lower', 'osc', 'osc_ma',
             'long_signal', 'short_signal')
    params = dict(LEN=120, BAND=2.5, SIG=9)

    # ① 主图/副图
    overlap = dict(upper=True, middle=True, lower=True,
                   osc=False, osc_ma=False)
    # ② 信号线不画折线
    isplot = dict(long_signal=False, short_signal=False)
    # ③ 图例：只藏 osc_ma 那一行（线照画）
    legend = dict(osc_ma=False)

    linestyle = dict(
        upper=LineStyle(line_color='#5c6bc0', line_width=1.2),
        middle=LineStyle(line_color=Colors.orange, line_width=2),
        lower=LineStyle(line_color='#5c6bc0', line_width=1.2,
                        price_line=True, price_label=True),
        osc=LineStyle(line_color=Colors.purple, line_width=1.6),
        osc_ma=LineStyle(line_color=Colors.gray, line_width=1.2,
                         line_dash=LineDash.dotted),
    )
    # ④ 色带
    bandstyle = [BandStyle(lower='lower', upper='upper',
                           fill_color='#5c6bc0', fill_alpha=0.12)]
    # ⑤ 关键位水平线
    spanstyle = [
        SpanStyle(location=5000, line_color=Colors.red,
                  line_dash='dashed', line_width=2),
        SpanStyle(location=5200, line_color=Colors.purple,
                  line_dash='dotted', line_width=1),
    ]
    # ⑥ 信号图标 + 文字
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red,
                                Markers.triangle, size=12).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle,
                                 size=12).set_label('S'),
    )

    def next(self):
        p = self.params
        mid = self.close.ema(p.LEN)
        std = self.close.rolling(p.LEN).std()
        upper = mid + std * p.BAND
        lower = mid - std * p.BAND
        base = self.close.ema(p.LEN)
        osc = (self.close - base) / base * 100
        return (upper, mid, lower, osc, osc.ema(p.SIG),
                self.close.cross_up(upper),
                self.close.cross_down(lower))


def main(gui=None):
    ind = StyleAllInOne(LocalDatas.test.kline)
    info = ind.plotinfo
    print('overlap   =', info.overlap)
    print('isplot    =', info.isplot)
    print('legend    =', info.legend)
    print('bandstyle =', [(b.lower, b.upper) for b in info.bandstyle])
    print('spanstyle =', [s.location for s in info.spanstyle])
    ind.btplot(gui=gui, grid=True)


if __name__ == '__main__':
    main()
