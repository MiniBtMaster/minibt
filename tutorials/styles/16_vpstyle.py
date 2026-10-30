"""7.16 · vpstyle —— 成交量分布（Volume Profile）

演示要点
--------
``category='vp'`` 的指标（框架自带 ``RollingVolumeProfile`` / ``VolumeProfileMA``）
不走普通折线，而是画成**横向成交量分布**：``next()`` 返回 ``(根数, 档数)`` 的矩阵
（每根 K 线一行 = 它那个窗口的价格分档成交量）。

``PlotInfo.vpstyle``（``VPStyle``）控制外观：

| 字段 | 默认 | 作用 |
| --- | --- | --- |
| ``bar_color`` | ``'#3498db'`` | 分布柱体颜色 |
| ``poc_color`` | ``'#f39c12'`` | POC（成交最密集价位）颜色 |
| ``highlight_poc`` | ``True`` | 是否高亮 POC |
| ``fill_alpha`` | ``0.6`` | 柱体透明度 |
| ``line_color`` / ``line_width`` | ``'white'`` / ``0.4`` | 柱体描边 |
| ``profile_frac`` | ``0.30`` | 分布宽度占比 |
| ``bin_ratio`` | ``0.88`` | 档高/档距比（<1 让柱之间有缝） |
| ``price_bars`` | ``None`` | 统计多少根的价格区间（``None`` = 用指标的 ``length``） |
| ``show_axis`` | ``False`` | 是否显示档位轴 |

``overlap=True``（默认）→ 分布画在**价格主图**右端；``overlap=False`` → 另开副图。

运行：``python tutorials/styles/16_vpstyle.py``
文档：``minibt_docs/docs/minibt_styles/7.16_vpstyle.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *
from minibt.utils import VPStyle
from minibt.utils import TableStyle  # noqa: F401  （同目录其它例子用到，提醒路径）


def main(gui=None):
    kline = LocalDatas.test.kline

    # 框架自带的「滚动成交量分布 + 均线」：category='vp'，默认叠在主图。
    # length 越大 → 分布覆盖的**价格区间越高**（在 5 个月的全景图上也看得见）
    ind = kline.tradingview.VolumeProfileMA(length=600, ma_len=20)
    info = ind.plotinfo
    print('category  =', info.category)
    print('lines[0:2]=', list(info.lines)[:2], '… 共', len(info.lines), '列')
    print('overlap(ma) =', info.overlap.get('ma') if isinstance(
        info.overlap, dict) else info.overlap)

    # 自定义外观（也可以构造时传 vpstyle=VPStyle(...)）
    info.vpstyle = VPStyle(
        bar_color='#26a69a',
        poc_color='#ff9800',
        highlight_poc=True,
        fill_alpha=0.5,
        profile_frac=0.30,
        bin_ratio=0.88,
    )
    print('vpstyle   =', info.vpstyle)

    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
