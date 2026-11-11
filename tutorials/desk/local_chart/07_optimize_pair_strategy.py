"""07 · Strategy 参数优化（配对交易）

和 `03_strategy_pair.py` 相同的两腿配对逻辑，多了 `OpConfig`：

* 优化 `open_h / open_l / close_pos / close_neg`；
* 目标 `sharpe`（也可以写 `['result', 'sharpe']` 等多目标）；
* 两腿各 1 手；手续费 1 元/手。

desk 用法：编辑器打开本文件 → 「参数优化」。
普通配对回测 / 图表回放请用 `03_strategy_pair.py`。

直接运行：`python tutorials/desk/local_chart/07_optimize_pair_strategy.py`
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
        xs, ys = pd.Series(x), pd.Series(y)
        var = xs.rolling(window, min_periods=window).var()
        cov = xs.rolling(window, min_periods=window).cov(ys)
        beta = cov / var
        spread = ys - beta * xs
        mean = spread.rolling(window, min_periods=window).mean()
        std = spread.rolling(window, min_periods=window).std()
        zscore = ((spread - mean) / std).replace(
            [float('inf'), float('-inf')], 0)
        return (spread.to_numpy(), zscore.fillna(0).to_numpy(),
                beta.fillna(0).to_numpy())


class PairTradingOptimize(Strategy):
    """两腿各 1 手 + OpConfig。"""

    config = Config(
        value=1_000_000.0,
        margin_rate=0.05,
        fixed_commission=1.0,
    )

    params = dict(open_h=1.5, open_l=-2.25,
                  close_pos=0.0, close_neg=-0.75,
                  size=1)

    op_config = OpConfig(
        target='sharpe',
        weights=1.0,
        opconfig=OptunaConfig(n_trials=30, sampler='TPESampler'),
        op_method='optuna',
        params=dict(
            open_h=(1.0, 3.0, 0.25),
            open_l=(-3.0, -1.0, 0.25),
            close_pos=(-0.5, 1.0, 0.25),
            close_neg=(-1.5, 0.0, 0.25),
        ),
    )

    def __init__(self):
        self.min_start_length = 30
        self.data_l = self.get_kline(LocalDatas.l2609_60)
        self.data_pp = self.get_kline(LocalDatas.pp2609_60)
        self.spread = IndFrame(dict(
            l_close=self.data_l.close.values,
            pp_close=self.data_pp.close.values,
        ))
        self.pair_signal = PairZScore(self.spread)
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
        if z != z:
            return
        left = self._net(self.data_l)
        right = self._net(self.data_pp)
        if bool(left) != bool(right):
            self._flat()
            return

        size = int(self.params.size)
        if not left and not right:
            if z < self.params.open_l:
                self.data_l.set_target_size(size)
                self.data_pp.set_target_size(-size)
            elif z > self.params.open_h:
                self.data_l.set_target_size(-size)
                self.data_pp.set_target_size(size)
            return

        if left > 0 and z >= self.params.close_neg:
            self._flat()
        elif left < 0 and z <= self.params.close_pos:
            self._flat()


if __name__ == '__main__':
    # 直接运行会按 op_config 跑优化（30 trials，配对回测较慢）；
    # 只想看一次配对回测请用 03_strategy_pair.py
    Bt().run()
