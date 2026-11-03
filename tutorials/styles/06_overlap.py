"""7.6 · overlap —— 主图叠加 vs 独立副图

演示要点
--------
``PlotInfo.overlap`` 决定一条线落在**主图（K 线那张）**还是**独立副图**：

.. code-block:: python

    overlap = True                       # 这个指标的线全叠主图
    overlap = False                      # 全放副图（默认）
    overlap = [True, False, True]        # 按线序（与 lines 对齐）
    overlap = dict(ema=True, osc=False)  # 按线名（推荐，最常用）

判定顺序（写样式时按这个想）
----------------------------
1. 先看 ``category``：``'candles'`` 会先把 4 条线**合成一根蜡烛**（7.3）；
2. 再看 ``overlap``：``True`` 叠主图，``False`` 进副图；
3. 进副图后，**多个指标是否共用同一个副图**由 ``source`` 决定（见 7.15）。

本例用和 7.3 同一个「压缩蜡烛」指标（默认在副图），把它改成
``overlap=True`` 并换成蓝/橙配色 —— 它就从副图**叠到主图**上了，
这是"用另一套蜡烛覆盖主图"（比如 HA / Renko）的常用写法。

运行：``python tutorials/styles/06_overlap.py``
文档：``minibt_docs/docs/minibt_styles/7.6_overlap.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *
from minibt.utils import Category


class CompressedCandle(BtIndicator):
    """最近 ``LEN`` 根合成一根蜡烛（与 7.3 相同）。"""

    lines = ('open', 'high', 'low', 'close')
    params = dict(LEN=3)
    category = Category.Candles

    def next(self):
        n = self.params.LEN
        return (self.close.shift(n),
                self.high.rolling(n).max(),
                self.low.rolling(n).min(),
                self.close)


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = CompressedCandle(kline)
    print('改之前 overlap =', ind.plotinfo.overlap)   # 全 False → 副图

    # ① 整条指标叠到主图（bool 形式；也可以 dict(open=True, ...) 逐线设）
    ind.plotinfo.overlap = True

    # ② 换个配色，方便看清"主图 K 线之上还有一套蜡烛"
    ind.plotinfo.candlestyle = CandleStyle(bull='#2196f3', bear='#ff9800')

    print('改之后 overlap =', ind.plotinfo.overlap)
    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
