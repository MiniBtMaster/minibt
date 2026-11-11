"""7.14 · watermark —— 图表水印

演示要点
--------
水印有**三个来源**，优先级从高到低：

1. ``config.watermark = False`` → **全部合约都不画**（策略里改 ``self.config``）；
2. K 线对象上显式设过：``kline.watermark = '文本'``（或 ``WaterMark('文本')``）；
3. 都没设 → 自动用**合约名**（``kline.symbol``）。

本例用第 2 种：给主图写死一段自定义水印。

``WaterMark.font_size`` 会透传给图表（``chart.watermark(text, font_size=…)``），
所以字号也能改 —— 本例用 72 号。

运行：``python tutorials/styles/14_watermark.py``
文档：``minibt_docs/docs/minibt_styles/7.14_watermark.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class WatermarkDemo(BtIndicator):
    """两条均线，只为给水印提供一张有内容的图。"""

    lines = ('ema_fast', 'ema_slow')
    overlap = True
    linestyle = dict(
        ema_fast=LineStyle(line_color=Colors.orange, line_width=1.5),
        ema_slow=LineStyle(line_color=Colors.blue, line_width=1.5),
    )

    def next(self):
        return self.close.ema(20), self.close.ema(60)


def main(gui=None):
    kline = LocalDatas.test.kline
    print('① 默认水印（不设）= 合约名 =', kline.symbol)

    # ② 自定义文本 + 字号（WaterMark 的 font_size 会透传给图表）
    kline.watermark = WaterMark('EMA 20 / 60', 72)
    print('② 显式设置后      =', kline.watermark.text,
          '| 字号 =', kline.watermark.font_size)

    # ③ 想彻底关掉：在策略里设 config（例子是 btplot 的临时策略，不便演示）
    #    self.config.watermark = False

    ind = WatermarkDemo(kline)
    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
