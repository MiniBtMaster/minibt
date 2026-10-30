# coding: utf-8
"""miniqt 单合约策略示例：双均线交叉。

**用法（miniqt）**

1. 「技术指标界面 → 内置指标 → 交易策略 → samples」点 ``SmaCrossDemo``；或
2. 代码编辑器里打开本文件 →「添加策略到当前图表」。

**数据**：单合约策略**不用**在代码里写合约 / 周期 —— symbol 留空即可，
miniqt 会把**鼠标最后点击那格图表**的 K 线喂进来（同源，指标与 K 线对齐 ✓）。

**交易**：在 miniqt 里目前是**回测口径**（策略内部模拟账户），不会真下单；
持仓会画在图上（副图「策略持仓」阶梅线）。
"""

from minibt import Strategy


class SmaCrossDemo(Strategy):
    """## 单合约 · 双均线交叉（快线上穿慢线开多，下穿平多）"""

    #: 参数会在图例齿轮 / 指标设置里出现（可在界面改 ✓）
    params = dict(fast=10, slow=20)

    def __init__(self):
        # symbol 留空 → miniqt 用「当前图表那格」的数据 ✓
        self.kline = self.get_kline(self.params.symbol)
        self.ma_fast = self.kline.close.sma(self.params.fast)
        self.ma_slow = self.kline.close.sma(self.params.slow)

    def next(self):
        fast, slow = self.ma_fast[-1], self.ma_slow[-1]
        pos = self.kline.position.pos
        if not pos and fast > slow:
            self.kline.buy()          # 金叉开多
        elif pos > 0 and fast < slow:
            self.kline.close()        # 死叉平多
