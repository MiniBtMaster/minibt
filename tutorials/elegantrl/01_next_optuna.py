"""ElegantRL 之外的静态参数优化：含 ``next()`` 的 Strategy。

结论：如果目标是找 ``fast/slow`` 这类**静态参数**，不要用 ElegantRL；
用 ``Bt.optstrategy`` + Optuna/GA 更直接、更省样本。

运行::

    python tutorials/elegantrl/01_next_optuna.py --check
    python tutorials/elegantrl/01_next_optuna.py            # 少量 trials，快速演示
    python tutorials/elegantrl/01_next_optuna.py --full     # 100 trials

注意：这不是 RL，``next()`` 在每根 K 线上执行，参数由 Optuna 采样。
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from minibt import Bt, LocalDatas, OptunaConfig, Strategy  # noqa: E402


class MACross(Strategy):
    """双均线交叉：金叉做多、死叉做空。"""

    params = dict(fast=10, slow=30)

    def __init__(self):
        # data_length 小一点，参数优化演示更快
        self.data = self.get_kline(LocalDatas.test, data_length=1200)
        self.fast = self.data.close.sma(self.params.fast)
        self.slow = self.data.close.sma(self.params.slow)

    def next(self):
        if not self.data.position:
            if self.fast.cross_up(self.slow).new:
                self.data.buy()
            elif self.fast.cross_down(self.slow).new:
                self.data.sell()
        elif self.data.position > 0 and self.fast.cross_down(self.slow).new:
            self.data.sell()
        elif self.data.position < 0 and self.fast.cross_up(self.slow).new:
            self.data.buy()


def main() -> int:
    parser = argparse.ArgumentParser(description='next 策略参数优化')
    parser.add_argument('--check', action='store_true', help='只检查配置，不跑优化')
    parser.add_argument('--full', action='store_true', help='100 trials（默认 6）')
    args = parser.parse_args()

    if args.check:
        print('策略参数:', MACross.params)
        print('待优化: fast=(5,30,5), slow=(20,60,10)')
        print('目标: sharpe 最大化 / max_drawdown 最小化')
        print('[example] 配置检查通过（不训练、不优化）')
        return 0

    bt = Bt(auto=False)
    bt.addstrategy(MACross)
    bt.optstrategy(
        target=['sharpe', 'max_drawdown'],
        weights=(1.0, -1.0),
        op_method='optuna',
        opconfig=OptunaConfig(
            n_trials=100 if args.full else 6,
            n_jobs=1,
            show_progress_bar=False,
        ),
        fast=(5, 30, 5),
        slow=(20, 60, 10),
    )
    bt.run(isplot=False, isreport=False)
    print('[example] 参数优化完成（结果 CSV 在 ~/.minibt/op_params/）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
