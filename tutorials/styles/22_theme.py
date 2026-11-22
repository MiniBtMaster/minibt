"""7.22 · 主题 —— light / dark 与自定义配色

演示要点
--------
主题决定**背景、文字、网格、默认涨跌色**，三处都能设，优先级：

1. 入口参数：``btplot(theme='dark')`` / ``run(theme='dark')``（**临时**覆盖）；
2. 策略/指标上：``Config(theme='dark')`` 或 ``self.theme = 'dark'``；
3. 都没有 → 库默认 ``'light'``。

``theme`` 只有两个取值：``'light'`` / ``'dark'``（旧写法 ``black_style=True/False``
仍然兼容，``True`` = dark）。

本例用 ``theme='dark'`` 出一张深色图：背景、网格、涨跌色、成交线颜色都会跟着变。

运行：``python tutorials/styles/22_theme.py``
文档：``minibt_docs/docs/minibt_styles/7.22_theme.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *
from minibt.utils import resolve_theme


class ThemeDemo(BtIndicator):
    """BOLL 通道 + 均线，浅色/深色都好看。"""

    lines = ('upper', 'middle', 'lower')
    overlap = True
    linestyle = dict(
        upper=LineStyle(line_color=Colors.blue, line_width=1.4),
        middle=LineStyle(line_color=Colors.orange, line_width=2),
        lower=LineStyle(line_color=Colors.blue, line_width=1.4),
    )
    bandstyle = [BandStyle(lower='lower', upper='upper',
                           fill_color='#4dabf7', fill_alpha=0.15)]

    def next(self):
        mid = self.close.ema(20)
        return mid * 1.02, mid, mid * 0.98


def main(gui=None):
    ind = ThemeDemo(LocalDatas.test.kline)
    print('默认主题 =', resolve_theme(None, None, ind))
    # ★ 深色：背景/网格/涨跌色/成交线全部换一套
    ind.btplot(gui=gui, theme='dark')


if __name__ == '__main__':
    main()
