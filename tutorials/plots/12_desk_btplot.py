"""12 · Gui.Desk 指标 —— `btplot` 一行画进 minibt desk

模式：**desk 界面 + btplot（指标）**
运行：``python tutorials/plots/12_desk_btplot.py``
（Jupyter：打开 ``12_desk_btplot.ipynb``，同一个例子，单元格形式）

演示：

* ``ind.btplot(gui=Gui.Desk)`` —— 指标 → desk **本地图表**「加到图表」；
* `PlotInfo` 样式在 desk 上一样生效：`linestyle`（颜色 / 线宽 / 虚线）、
  `overlap`（主图叠加 / 独立副图）、`legend`（是否进图例行）。
  desk 显示的是 minibt **算好的线**，不会重算，所以样式 / 信号 / 停止线都保留 ✓。

Jupyter：desk 自动用**浏览器壳 + iframe** 内嵌（不阻塞 kernel）；
普通脚本则弹 Qt 桌面窗口，关窗即结束。

切换提示：``gui=Gui.Pylightcharts``（默认，原生窗口）/ ``Gui.PylightchartsWeb``
（浏览器标签）/ ``gui='jupyter'``（Notebook 内联网页版）。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *                      # noqa: F401,F403
from minibt import (BtIndicator, Gui, LineDash, LineStyle, LocalDatas)


class MaBand(BtIndicator):
    """一条主图均线 + 一条副图带宽（最简的指标 → desk 图表）。"""

    lines = ('ma', 'band')
    params = dict(length=20, k=2.0)

    #: 均线叠在主图、带宽单独一个副图
    overlap = dict(ma=True, band=False)

    linestyle = dict(
        ma=LineStyle(line_color='#f6c343', line_width=2),
        band=LineStyle(line_color='#2196f3', line_width=1,
                       line_dash=LineDash.dashed),
    )

    #: 副图这条不进左上角图例行（想看名字就删掉这一行）
    legend = dict(band=False)

    def next(self):
        ma = self.close.rolling(int(self.params.length)).mean()
        band = self.close.rolling(int(self.params.length)).std() * float(self.params.k)
        return ma.to_numpy(), band.to_numpy()


if __name__ == '__main__':
    kline = LocalDatas.l2609_60.kline
    # ★ 唯一区别：gui=Gui.Desk（等价 gui='desk'）
    MaBand(kline).btplot(gui=Gui.Desk)
