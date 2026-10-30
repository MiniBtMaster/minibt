"""03 · 多合约单策略：配对交易（本地图表 / 回放 / 回测）

参考 `~/.minibt/personal/strategies/test_2.py` 和 `test_6.py`，但这里
使用更直观的“滚动 beta + 价差 zscore”，并且两腿固定各 1 手：

* 腿 A：`l2609_60`
* 腿 B：`pp2609_60`
* 价差：`l - beta * pp`
* 多价差 = 多 l + 空 pp；空价差 = 空 l + 多 pp

在 desk 本地图表里点「加到图表」时：
1. 系统扫描到两个 `get_kline(LocalDatas.xxx)`；
2. 自动选择左右两图布局；
3. 先加载 l2609_60 / pp2609_60 两个本地 CSV；
4. 再添加策略。

进入回放后，播放 / 单步会推进 `next()`，两条腿会一起在本地模拟账户
成交；两张图各自显示自己的持仓线。

直接运行：`python tutorials/desk/local_chart/03_strategy_pair.py`
"""
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import numpy as np
import pandas as pd

from minibt import *


class PairZScore(BtIndicator):
    """滚动 OLS beta + 价差 zscore。"""

    lines = ('spread', 'zscores', 'beta')
    params = dict(window=30)
    overlap = False
    isplot = dict(beta=False)

    def next(self):
        x = np.asarray(self.pp_close.values, dtype=float)
        y = np.asarray(self.l_close.values, dtype=float)
        window = max(10, int(self.params.window))
        xs = pd.Series(x)
        ys = pd.Series(y)
        var = xs.rolling(window, min_periods=window).var()
        cov = xs.rolling(window, min_periods=window).cov(ys)
        beta = cov / var
        spread = ys - beta * xs
        mean = spread.rolling(window, min_periods=window).mean()
        std = spread.rolling(window, min_periods=window).std()
        zscore = ((spread - mean) / std).replace(
            [float('inf'), float('-inf')], 0)
        return spread.to_numpy(), zscore.fillna(0).to_numpy(), \
            beta.fillna(0).to_numpy()


class PairTradingStrategy(Strategy):
    """两腿各 1 手的配对均值回归策略。"""

    config = Config(
        value=1_000_000.0,
        margin_rate=0.05,
        fixed_commission=1.0,
    )

    #: test_6.py 回写的最优信号参数（可按需修改）
    params = dict(open_h=1.5, open_l=-2.25,
                  close_pos=0.0, close_neg=-0.75,
                  size=1)

    def __init__(self):
        self.min_start_length = 30
        self.data_l = self.get_kline(LocalDatas.l2609_60)
        self.data_pp = self.get_kline(LocalDatas.pp2609_60)

        # IndFrame 只是“两条腿的收盘价”，不会额外画一条 K 线
        self.spread = IndFrame(dict(
            l_close=self.data_l.close.values,
            pp_close=self.data_pp.close.values,
        ))
        self.pair_signal = PairZScore(self.spread)

        #: 每条腿 1 元/手；覆盖 config 的全局手续费
        self.data_l.fixed_commission = 1.0
        self.data_pp.fixed_commission = 1.0

    @staticmethod
    def _net(kline):
        position = kline.position
        return float(getattr(position, 'pos', position) or 0.0)

    def _flat(self):
        self.data_l.set_target_size(0)
        self.data_pp.set_target_size(0)

    def next(self):
        z = self.pair_signal.zscores.new
        if z != z:                              # 预热期
            return

        left = self._net(self.data_l)
        right = self._net(self.data_pp)

        # 单腿裸奔（成交失败 / 人工干预）→ 先清掉，下一根重新来
        if bool(left) != bool(right):
            self._flat()
            return

        size = int(self.params.size)

        if not left and not right:
            # 价差太低：多 l + 空 pp
            if z < self.params.open_l:
                self.data_l.set_target_size(size)
                self.data_pp.set_target_size(-size)
            # 价差太高：空 l + 多 pp
            elif z > self.params.open_h:
                self.data_l.set_target_size(-size)
                self.data_pp.set_target_size(size)
            return

        # 多价差：z 回升到 close_neg 平仓
        if left > 0 and z >= self.params.close_neg:
            self._flat()
        # 空价差：z 回落到 close_pos 平仓
        elif left < 0 and z <= self.params.close_pos:
            self._flat()


if __name__ == '__main__':
    Bt().run()
