"""7.3 · category —— 指标分类决定「画成什么」

演示要点
--------
``PlotInfo.category`` 告诉图表「这条指标是哪一类」，最直观的是蜡烛型：

* ``category='candles'`` —— 四条线 ``open / high / low / close`` **合成一根
  蜡烛**（而不是四条折线），默认落在**副图**；
* 不写 ``category``（默认 ``'any'``）—— 每条线各画一条折线；
* 同类还有 ``heikin_ashi_candles`` / ``linear_regression_candles``；另外
  ``momentum`` / ``trend`` / ``volatility`` / ``volume`` / ``statistics`` /
  ``performance`` 是**语义分类**（影响副图归属、统计页、绩效页）。

本例用一个自定义的「压缩蜡烛」指标（最近 N 根压成一根）来演示：
**只改 ``category`` 这一行**，副图就从「4 条折线」变成「一根蜡烛」——
把下面那行改成 ``category = Category.Any``（或删掉）就能看到 4 条折线。

运行：``python tutorials/styles/03_category.py``
文档：``minibt_docs/docs/minibt_styles/7.3_category.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *
from minibt.utils import Category


class CompressedCandle(BtIndicator):
    """最近 ``LEN`` 根合成一根蜡烛（只为演示 ``category``，不是标准 HA）。"""

    lines = ('open', 'high', 'low', 'close')
    params = dict(LEN=3)

    # ★ 这一行就是本例的主角：声明「我是蜡烛型」
    #   把它改成 Category.Any（或删掉）→ 同一个指标会画成 4 条折线
    category = Category.Candles

    # 副图也能带右轴价格线/价格标签（蜡烛型一样支持）
    linestyle = dict(close=LineStyle(price_line=True, price_label=True))

    def next(self):
        n = self.params.LEN
        return (self.close.shift(n),          # open：N 根前的收盘
                self.high.rolling(n).max(),   # high：N 根最高
                self.low.rolling(n).min(),    # low ：N 根最低
                self.close)                   # close：当前收盘


def main(gui=None):
    print('Category 全部取值：')
    for name in ('Any', 'Candles', 'Heikin_Ashi_Candles',
                 'Linear_Regression_Candles', 'Overlap', 'Momentum',
                 'Trend', 'Volatility', 'Volume', 'Statistics',
                 'Performance'):
        print(f'  {name:26s} = {getattr(Category, name)!r}')

    kline = LocalDatas.test.kline
    ind = CompressedCandle(kline)

    info = ind.plotinfo
    print('category =', info.category)
    print('lines    =', list(info.lines))
    print('overlap  =', info.overlap)      # 全 False → 独立副图

    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
