# coding: utf-8
"""miniqt 多合约策略示例（**声明式 charts**）。

``charts`` 告诉 miniqt「每根 K 线看哪一格」：

>>> charts = [('SHFE.rb2610', 0), ('DCE.i2609', 0)]

* 每项 = ``(合约, 周期秒)``；**周期写 0 = 跟当前图表周期**；
* 也可以只写合约字符串：``charts = ['SHFE.rb2610', 'DCE.i2609']``（周期同上）。

miniqt 加载时：

1. 把当前多布局各格的 K 线按 **合约名** 匹配到 ``charts``（``SHFE.rb2610``
   ↔ ``rb2610`` 都认）；
2. 合约名对不上就**按顺序**用当前图的各格（数量相等时）；
3. 加载进图表后，每根 K 线的指标画到它对应的那一格。

**前置**：当前图表要开成多布局（左右/上下 2 格），并显示这两个合约。
"""

from minibt import Strategy


class PairMaDemo(Strategy):
    """## 多合约 · 两个合约各一条均线（声明式 charts）"""

    #: 声明式合约表：miniqt 靠它把 K 线映射到面板（推荐的多合约写法 ✓）
    charts = [('SHFE.rb2610', 0), ('DCE.i2609', 0)]
    params = dict(length=10)

    def __init__(self):
        self.k_a = self.get_kline(self.charts[0][0])
        self.k_b = self.get_kline(self.charts[1][0])
        self.ma_a = self.k_a.close.sma(self.params.length)
        self.ma_b = self.k_b.close.sma(self.params.length)

    def next(self):
        # 示例逻辑：a 上穿自身均线开多 a；b 下穿自身均线开空 b
        pos_a = self.k_a.position.pos
        if not pos_a and self.k_a.close[-1] > self.ma_a[-1]:
            self.k_a.buy()
        pos_b = self.k_b.position.pos
        if not pos_b and self.k_b.close[-1] < self.ma_b[-1]:
            self.k_b.sell()
