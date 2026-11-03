# coding: utf-8
"""miniqt 多合约策略示例（**不声明 charts，靠 get_kline 的合约名**）。

和 ``multi_pair_declared.py`` 效果一样，只是**不写** ``charts`` 声明：
miniqt 会从 ``get_kline('SHFE.rb2610')`` 的参数里读合约名来匹配面板 ✓。

两种写法都支持，二选一：

* 写 ``charts``（推荐）：映射最明确，还能标周期；
* 不写（本文件）：代码更省，靠 ``get_kline`` 的合约名。
"""

from minibt import Strategy


class TwoContractDemo(Strategy):
    """## 多合约 · 按 get_kline 合约名匹配面板"""

    params = dict(fast=10, slow=20)

    def __init__(self):
        # 两个不同合约 → get_kline 各取一次，miniqt 按合约名分到两格 ✓
        self.k_a = self.get_kline('SHFE.rb2610')
        self.k_b = self.get_kline('DCE.i2609')
        self.ma_a = self.k_a.close.sma(self.params.fast)
        self.ma_b = self.k_b.close.sma(self.params.slow)

    def next(self):
        # 示例：a 金叉开多；b 死叉开空
        pos_a = self.k_a.position.pos
        if not pos_a and self.k_a.close[-1] > self.ma_a[-1]:
            self.k_a.buy()
        pos_b = self.k_b.position.pos
        if not pos_b and self.k_b.close[-1] < self.ma_b[-1]:
            self.k_b.sell()

