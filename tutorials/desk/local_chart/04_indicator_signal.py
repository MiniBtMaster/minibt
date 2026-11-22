"""04 · 指标信号：回测 + 参数优化（单合约）

文件类型是 `BtIndicator`（不是 Strategy），通过信号列让 desk 自动
调用 `signal_backtest(...)`：

* `long_signal` / `short_signal`：开多 / 开空
* `exitlong_signal` / `exitshort_signal`：平多 / 平空

在 desk 编辑器打开本文件后：
* 「策略回测」→ 单合约信号回测；
* 「参数优化」→ 使用类里的 `OptimizeConfig` 优化 fast / slow。

信号回测的手续费：默认从 `data.kline` 的 `commission` / broker 读取；
本例在 `_LocalSignalData.kline` 里把它设为 1 元/手。

直接运行：`python tutorials/desk/local_chart/04_indicator_signal.py`
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


class _FixedFeeBroker:
    """signal_backtest 默认从 KLine / broker 读手续费。"""

    commission = {'fixed_commission': 1.0}
    margin_rate = 0.05
    slip_point = 0.0


class _LocalSignalData:
    """给 desk 的指标模式提供 `data.kline`，并设置 1 元/手手续费。"""

    _kline = None

    @property
    def kline(self):
        if self._kline is None:
            kline = LocalDatas.l2609_60.kline
            kline.fixed_commission = 1.0
            kline._broker = _FixedFeeBroker()
            self._kline = kline
        return self._kline


class MaSignal(BtIndicator):
    """双均线信号：金叉多、死叉空，反向交叉时平仓。"""

    lines = ('fast', 'slow', 'long_signal', 'short_signal',
             'exitlong_signal', 'exitshort_signal')
    params = dict(fast=10, slow=30)
    overlap = True

    linestyle = dict(
        fast=LineStyle(line_color='#f6c343', line_width=2),
        slow=LineStyle(line_color='#2196f3', line_width=2,
                       line_dash=LineDash.dashed),
    )

    data = _LocalSignalData()

    #: 单合约信号优化：权益 + 夏普率，两个都最大化
    op_config = OptimizeConfig(
        params=dict(fast=(5, 30, 1), slow=(30, 90, 2)),
        target=['final_equity', 'sharpe'],
        weights=(1.0, 1.0),
        method='optuna',
        config={'n_trials': 40, 'sampler': 'TPESampler'},
        n_jobs=2,
        output_dir='./results',
    )

    def next(self):
        close = np.asarray(self.close.values, dtype=float)
        fast = _sma(close, self.params.fast)
        slow = _sma(close, self.params.slow)
        diff = fast - slow
        prev = np.concatenate(([np.nan], diff[:-1]))

        long_signal = (prev <= 0) & (diff > 0)
        short_signal = (prev >= 0) & (diff < 0)
        exitlong_signal = (prev >= 0) & (diff < 0)
        exitshort_signal = (prev <= 0) & (diff > 0)

        return (fast, slow,
                long_signal.astype(float), short_signal.astype(float),
                exitlong_signal.astype(float),
                exitshort_signal.astype(float))


def _sma(values, length):
    return pd.Series(values).rolling(max(1, int(length))).mean().to_numpy()


if __name__ == '__main__':
    ind = MaSignal(MaSignal.data.kline)
    result = ind.signal_backtest(
        size=1, isplot=False, isreport=False,
        optimize=MaSignal.op_config,
    )
    result.pprint()
    result.plot_optuna()
