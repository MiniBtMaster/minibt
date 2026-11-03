"""指标信号参数优化：Cython ``from_signals``。

和 ``Strategy.next()`` 不同，这里只产出交易信号，回测由 Cython 加速：

    long_signal / short_signal / exitlong_signal / exitshort_signal
        → entries / exits → from_signals → 权益曲线 → QuantStats

运行::

    python tutorials/elegantrl/02_signal_cython_optimize.py --check
    python tutorials/elegantrl/02_signal_cython_optimize.py
    python tutorials/elegantrl/02_signal_cython_optimize.py --full

这条路径也**不是 ElegantRL**；它是静态信号参数搜索 + Cython 回测。
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from minibt import (BtIndicator, LocalDatas, OptimizeConfig)  # noqa: E402


class MACrossSignal(BtIndicator):
    """双均线信号：只负责算信号，交易由 Cython 引擎模拟。"""

    lines = (
        'ma1', 'ma2',
        'long_signal', 'short_signal',
        'exitlong_signal', 'exitshort_signal',
    )
    params = dict(fast=10, slow=30)
    overlap = dict(ma1=True, ma2=True)
    isplot = dict(
        long_signal=False, short_signal=False,
        exitlong_signal=False, exitshort_signal=False,
    )

    def next(self):
        ma1 = self.close.sma(self.params.fast)
        ma2 = self.close.sma(self.params.slow)
        long_signal = ma1.cross_up(ma2)
        short_signal = ma1.cross_down(ma2)
        # 反手：多信号平空，空信号平多
        return (
            ma1, ma2,
            long_signal, short_signal,
            short_signal, long_signal,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description='信号参数优化（Cython）')
    parser.add_argument('--check', action='store_true', help='只检查配置')
    parser.add_argument('--full', action='store_true', help='Optuna 100 trials')
    args = parser.parse_args()

    if args.check:
        print('信号指标参数:', MACrossSignal.params)
        print('参数空间: fast=(5,30,5), slow=(20,60,10)')
        print('引擎: Cython from_signals')
        print('[example] 配置检查通过（不优化）')
        return 0

    ind = MACrossSignal(LocalDatas.test.kline)
    if args.full:
        config = OptimizeConfig(
            params={'fast': (5, 30, 5), 'slow': (20, 60, 10)},
            target=['sharpe', 'max_drawdown'],
            weights=(1.0, -1.0),
            method='optuna',
            config={'n_trials': 100, 'sampler': 'TPESampler'},
            n_jobs=2,
            output_dir='./opt_results',
        )
    else:
        # 默认 2 个参数、6 组组合，几十秒内能跑完
        config = OptimizeConfig(
            params={'fast': (5, 15, 5), 'slow': (20, 40, 10)},
            target='sharpe',
            method='grid',
            n_jobs=2,
        )

    result = ind.signal_backtest(
        optimize=config,
        isplot=False,
        isreport=False,
    )
    print('最优参数:', result.best_params)
    print('最优指标:', {
        key: result.best_metrics.get(key)
        for key in ('sharpe', 'max_drawdown', 'total_return_pct')
        if key in result.best_metrics
    })
    print('[example] 信号参数优化完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
