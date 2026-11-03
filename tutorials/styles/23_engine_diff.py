"""7.23 · 三引擎差异 —— 同一个 PlotInfo，bokeh / 原生 / 网页

演示要点
--------
minibt 有三个图表引擎，读的是**同一份 `PlotInfo`**：

* ``Gui.Pylightcharts`` —— 原生窗口（PyQt6 + WebView2）；
* ``Gui.PylightchartsWeb`` —— 本地 SSE + 浏览器（VS Code 扩展、远程都用这个）；
* ``Gui.Bokeh`` —— bokeh server / 静态 HTML。

本例是一张**综合样式**图（BOLL 通道色带 + 信号），用来对照文档里的差异表：
哪些字段三个引擎都认、哪些只有某一个认。

运行：``python tutorials/styles/23_engine_diff.py``
文档：``minibt_docs/docs/minibt_styles/7.23_engine_diff.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class BollSignals(BtIndicator):
    """BOLL 通道：色带 + 右轴价格线（多种样式叠加的综合示例）。"""

    lines = ('upper', 'middle', 'lower')
    params = dict(LEN=60, BAND=2.0)
    overlap = True

    linestyle = dict(
        upper=LineStyle(line_color='#5c6bc0', line_width=1.2,
                        price_line=True),
        middle=LineStyle(line_color=Colors.orange, line_width=2),
        lower=LineStyle(line_color='#5c6bc0', line_width=1.2),
    )
    bandstyle = [BandStyle(lower='lower', upper='upper',
                           fill_color='#5c6bc0', fill_alpha=0.12)]

    def next(self):
        p = self.params
        mid = self.close.ema(p.LEN)
        std = self.close.rolling(p.LEN).std()
        upper = mid + std * p.BAND
        lower = mid - std * p.BAND
        return upper, mid, lower


def main(gui=None):
    ind = BollSignals(LocalDatas.test.kline)
    info = ind.plotinfo
    print('category =', info.category, '| 线数 =', len(info.lines))
    print('色带 =', [(b.lower, b.upper) for b in info.bandstyle])
    print('信号 =', list(info.signalstyle))
    # 想换引擎：改这一行即可（bokeh / pylightcharts / pylightcharts_web）
    ind.btplot(gui=gui, theme='light', grid=True, toolbox=True)


if __name__ == '__main__':
    main()
