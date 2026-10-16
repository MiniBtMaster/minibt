# coding: utf-8
"""miniqt 单合约策略示例：N 周期突破。

演示「只用当前图表那一格数据」的单合约写法 —— 不写合约名、不写周期，
miniqt 自动注入当前面板的 K 线 ✓。
"""

from minibt import Strategy


class DonchianBreakDemo(Strategy):
    """## 单合约 · N 周期高低点突破

    收盘价创 ``length`` 根新高 → 开多；跌破 ``length`` 根新低 → 平多。
    （用 ``sma`` / ``rolling`` 之类都可以，``IndSeries`` 支持链式调用 ✓）
    """

    params = dict(length=20, size=1)

    def __init__(self):
        self.kline = self.get_kline(self.params.symbol)
        self.hh = self.kline.high.rolling(self.params.length).max()
        self.ll = self.kline.low.rolling(self.params.length).min()

    def next(self):
        close = self.kline.close[-1]
        pos = self.kline.position.pos
        # 用前一根的高/低点，避免「自己包含自己」
        if not pos and close > self.hh[-2]:
            self.kline.buy(size=self.params.size)
        elif pos > 0 and close < self.ll[-2]:
            self.kline.close()
