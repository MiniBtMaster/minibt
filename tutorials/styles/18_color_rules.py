"""7.18 · color_rules / color_by —— 逐点配色

演示要点
--------
``color_by(condition, color, else_color)`` 给数据**逐点**（按 bar）上色：

```python
kline.color_by(condition, color=Colors.red, else_color=Colors.green)
ind.color_by(condition, color=Colors.red, else_color=Colors.green)
```

* 规则记在 ``PlotInfo.color_rules`` 里，图表侧统一落地（``apply_color_rules``），
  所以回测 / 回放 / 实时都生效，指标重算、切合约也不会掉色；
* 蜡烛会**整根**变色（含影线/边框，可用 ``wick_color`` / ``border_color`` 细分）；
  指标线是**逐点**变色。

⚠️ 三个反直觉的点（已实测）
--------------------------
1. 规则要挂在**指标对象**上（``ind.color_by(...)``），**不是**单条线上
   （``ind.osc.color_by(...)`` 不生效）；
2. 一条规则会作用到这个指标的**所有线** —— "只给某一条线上色"要么拆成独立指标，
   要么直接用 ``linestyle`` 固定颜色（[7.7](7.7_linestyle.md)）；
3. 条件建议用 **numpy 数组**（``np.asarray(...) > 0``）：minibt 的 Series/Line
   定义了 ``__call__``，传对象进去可能被当成"回调"而不是"逐点条件"。

运行：``python tutorials/styles/18_color_rules.py``
文档：``minibt_docs/docs/minibt_styles/7.18_color_rules.md``
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class ColorByDemo(BtIndicator):
    """一条偏离率曲线（副图），零轴以上红、以下绿。"""

    lines = ('osc',)
    overlap = False
    linestyle = dict(osc=LineStyle(line_width=2))

    def next(self):
        return self.close - self.close.ema(30)


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 主图 K 线：只给「极端放量」的根上色（成交量 > 60 日均量 5 倍）
    volume = np.asarray(kline.volume, dtype=float)
    vol_ma = pd.Series(volume).rolling(60).mean().to_numpy()
    spike = volume > 5 * vol_ma
    print('放量根数 =', int(np.nansum(spike)))
    kline.color_by(spike, color='#ff9800')

    ind = ColorByDemo(kline)
    # ② 指标线：osc > 0 红、否则绿（逐点变色）
    osc = np.asarray(ind, dtype=float)
    ind.color_by(osc > 0, color=Colors.red, else_color=Colors.green)

    print('K 线规则数 =', len(kline.plotinfo.color_rules))
    print('指标规则数 =', len(ind.plotinfo.color_rules))
    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
