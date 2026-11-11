"""05 · 配对指标：pair_backtest 回测 + 参数优化

这是 test_6.py 的精简教程版：两条真实合约交给 `pair_backtest`，
所以回测 / 优化后**仍然保留两个合约的 K 线和图表**。

指标类里的约定：
* `data`：默认腿（也用于普通指标模式）
* `pair_klines = (腿A, 腿B)`：desk 看到它就走 `pair_backtest(...)`
* `pair_backtest_kwargs`：两腿手数 / 手续费 / 保证金 / 初始资金

两腿各 1 手，1 元/手；多价差 = 多 l + 空 pp，空价差 = 空 l + 多 pp。

直接运行：`python tutorials/desk/local_chart/05_indicator_pair.py`
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


_PAIR_A = LocalDatas.l2609_60.kline
_PAIR_B = LocalDatas.pp2609_60.kline
_A_CLOSE = pd.Series(np.asarray(_PAIR_A.close.values, dtype=float))
_B_CLOSE = pd.Series(np.asarray(_PAIR_B.close.values, dtype=float))


class PairSignal(BtIndicator):
    """滚动 beta + 价差 zscore 的配对信号。"""

    lines = ('pair_z', 'long_signal', 'short_signal',
             'exitlong_signal', 'exitshort_signal')
    isplot = dict(long_signal=False, short_signal=False,
                  exitlong_signal=False, exitshort_signal=False)
    overlap = False
    params = dict(close_neg=-0.75, close_pos=0,
                  open_h=1.5, open_l=-2.25, window=30)

    data = LocalDatas.l2609_60
    pair_klines = (LocalDatas.l2609_60, LocalDatas.pp2609_60)
    pair_backtest_kwargs = dict(
        size=1,
        commission=(1.0, 1.0),          # 每条腿 1 元/手
        com_type=CommissionType.Fixed,
        margin_rate=(0.05, 0.05),
        leg_size_ratio=1.0,             # 两腿 1:1
        init_cash=1_000_000.0,
    )

    op_config = OptimizeConfig(
        params=dict(
            window=(20, 120, 10),
            open_h=(1.5, 3.0, 0.25),
            open_l=(-3.0, -1.5, 0.25),
            close_pos=(-0.25, 1.25, 0.25),
            close_neg=(-1.25, 0.25, 0.25),
        ),
        target=['final_equity', 'sharpe'],
        weights=(1.0, 1.0),
        method='optuna',
        config={'n_trials': 40, 'sampler': 'NSGAIISampler'},
        n_jobs=2,
        output_dir='./results',
    )

    def next(self):
        count = min(len(self), len(_A_CLOSE), len(_B_CLOSE))
        if count <= 0:
            return (self.zeros(), self.zeros(), self.zeros(),
                    self.zeros(), self.zeros())

        window = max(10, int(self.params.window))
        # x = pp（腿B），y = l（腿A）；spread = l - beta * pp
        x = _B_CLOSE.iloc[:count].reset_index(drop=True)
        y = _A_CLOSE.iloc[:count].reset_index(drop=True)
        var = x.rolling(window, min_periods=window).var()
        cov = x.rolling(window, min_periods=window).cov(y)
        beta = cov / var
        spread = y - beta * x
        mean = spread.rolling(window, min_periods=window).mean()
        std = spread.rolling(window, min_periods=window).std()
        z = ((spread - mean) / std).replace(
            [float('inf'), float('-inf')], 0)

        open_h = float(self.params.open_h)
        open_l = float(self.params.open_l)
        close_pos = float(self.params.close_pos)
        close_neg = float(self.params.close_neg)
        prev = z.shift(1)

        long_signal = (z < open_l) & (prev >= open_l)
        short_signal = (z > open_h) & (prev <= open_h)
        exitlong_signal = (z >= close_neg) & (prev < close_neg)
        exitshort_signal = (z <= close_pos) & (prev > close_pos)

        return (z.fillna(0.0),
                long_signal.fillna(False).astype(float),
                short_signal.fillna(False).astype(float),
                exitlong_signal.fillna(False).astype(float),
                exitshort_signal.fillna(False).astype(float))


if __name__ == '__main__':
    a, b = _PAIR_A, _PAIR_B
    count = min(len(a), len(b))
    prices = np.column_stack([
        np.asarray(a.close.values, dtype=float)[:count],
        np.asarray(b.close.values, dtype=float)[:count],
    ])

    ind = PairSignal(a)
    result = ind.pair_backtest(
        kline_a=a, kline_b=b, prices=prices,
        isplot=False, isreport=False,
        optimize=PairSignal.op_config,
        **PairSignal.pair_backtest_kwargs,
    )
    result.pprint()
    result.plot_optuna()
