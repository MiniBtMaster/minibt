"""7.8 · vbar —— 柱状线（MACD 那种围绕 0 轴的红绿柱）

演示要点
--------
把 ``line_dash`` 设成 ``LineDash.vbar``，这条线就变成**柱体（Histogram）**，
再用 4 个 ``vbar_*`` 字段控制柱体：

| 字段 | 作用 |
| --- | --- |
| ``vbar_base`` | 柱子**从哪个值画起**（MACD 用 0） |
| ``vbar_up_color`` | 值 **> 分界**时的颜色 |
| ``vbar_down_color`` | 值 **< 分界**时的颜色 |
| ``vbar_color_base`` | **分色**用的分界（不设 = 跟随 ``vbar_base``，再默认 0） |

配色优先级（``apply_histogram_colors``）：
``vbar_up_color/vbar_down_color`` > ``line_color``（单色）> 主图 K 线涨跌色 > 默认色。

运行：``python tutorials/styles/08_vbar.py``
文档：``minibt_docs/docs/minibt_styles/7.8_vbar.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class MacdHist(BtIndicator):
    """DIFF / DEA 两条线 + 柱子（``hist = 2 * (DIFF - DEA)``），全在副图。"""

    lines = ('diff', 'dea', 'hist')
    overlap = False                      # 副图

    linestyle = dict(
        diff=LineStyle(line_color=Colors.orange, line_width=1.5),
        dea=LineStyle(line_color=Colors.blue, line_width=1.5),
        # ★ 柱状线：从 0 画起，正红负绿（与主图 K 线的涨跌色无关，这里显式指定）
        hist=LineStyle(
            line_dash=LineDash.vbar,     # ← 这一行让它变成柱体
            vbar_base=0,                 # 柱底基线
            vbar_up_color=Colors.red,    # 柱子在 0 以上 → 红
            vbar_down_color=Colors.green,  # 柱子在 0 以下 → 绿
        ),
    )

    def next(self):
        diff = self.close.ema(12) - self.close.ema(26)
        dea = diff.ema(9)
        hist = (diff - dea) * 2
        return diff, dea, hist


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = MacdHist(kline)
    st = ind.plotinfo.linestyle['hist']
    print('hist  -> dash =', st.line_dash,
          '| base =', st.vbar_base,
          '| up =', st.vbar_up_color,
          '| down =', st.vbar_down_color)
    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
