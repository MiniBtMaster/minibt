"""7.9 · candlestyle —— 蜡烛涨跌配色（主图 K 线 + 蜡烛型指标）

演示要点
--------
``CandleStyle`` 只有两个字段：``bull``（涨）和 ``bear``（跌）。两处都能用：

1. **主图 K 线** —— 用 ``kline.bull_color`` / ``kline.bear_color`` 赋值
   （setter 会同时把 ``_plotinfo.candlestyle`` 改掉并打上"用户显式设过"的标记，
   图表侧据此覆盖主题色）；
2. **蜡烛型指标**（``category='candles'``）—— 设 ``plotinfo.candlestyle``，
   只影响这条指标自己的蜡烛，不影响主图。

本例：主图改成蓝 / 橙，副图的压缩蜡烛改成粉 / 青 —— 一眼就能看出是两套配色。

运行：``python tutorials/styles/09_candlestyle.py``
文档：``minibt_docs/docs/minibt_styles/7.9_candlestyle.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *
from minibt.utils import Category


class CompressedCandle(BtIndicator):
    """最近 ``LEN`` 根合成一根蜡烛（同 7.3）。"""

    lines = ('open', 'high', 'low', 'close')
    params = dict(LEN=3)
    category = Category.Candles
    linestyle = dict(close=LineStyle(price_line=True, price_label=True))

    def next(self):
        n = self.params.LEN
        return (self.close.shift(n),
                self.high.rolling(n).max(),
                self.low.rolling(n).min(),
                self.close)


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 主图 K 线：蓝涨 / 橙跌（也可以传 Colors.red / '#26a69a' 这类值）
    print('主图改色前 candlestyle =', kline.plotinfo.candlestyle)
    kline.bull_color = '#2196f3'
    kline.bear_color = '#ff9800'
    print('主图改色后 candlestyle =', kline.plotinfo.candlestyle)

    # ② 副图蜡烛型指标：粉涨 / 青跌
    ind = CompressedCandle(kline)
    ind.plotinfo.candlestyle = CandleStyle(bull='#e91e63', bear='#009688')
    print('指标 candlestyle      =', ind.plotinfo.candlestyle)

    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
