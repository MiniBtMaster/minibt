"""参数 / 策略自适应：bandit 元控制器原型。

这个例子演示“**不是每根 K 线都重算一套参数，而是按窗口选择参数 preset**”：

    Cython 先给每个候选参数组算一条权益曲线
        ↓
    按窗口把“下一段收益”作为 bandit 的 reward
        ↓
    UCB 选择 preset（可替换成 ElegantRL AgentEnsembleDQN）

UCB 版本很轻、方便先验证数据与 reward；要把选择器换成神经网络，
把 ``_choose`` 换成 ``AgentEnsembleDQN`` 的 actor 即可。

运行::

    python tutorials/elegantrl/04_parameter_bandit.py --check
    python tutorials/elegantrl/04_parameter_bandit.py
"""
from __future__ import annotations

import argparse
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np  # noqa: E402

from minibt import BtIndicator, LocalDatas  # noqa: E402

#: 候选参数 preset（实际研究可用 Optuna 先粗筛，再交给 bandit）
PRESETS = [
    dict(fast=5, slow=20),
    dict(fast=5, slow=40),
    dict(fast=10, slow=30),
    dict(fast=10, slow=50),
]

#: 每 STEP 根做一次选择，看未来 HORIZON 根收益
START = 100
STEP = 20
HORIZON = 20


class CandidateSignal(BtIndicator):
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
        return (ma1, ma2, long_signal, short_signal, short_signal, long_signal)


def _equity_for(kline, preset: dict) -> np.ndarray:
    """用 Cython signal_backtest 给一个 preset 算权益曲线。"""
    cls = type(
        f"Candidate_{preset['fast']}_{preset['slow']}",
        (CandidateSignal,),
        {'params': dict(preset)},
    )
    result = cls(kline).signal_backtest(isplot=False, isreport=False)
    equity = np.asarray(result.profits, dtype=float)
    # 去掉可能的 NaN / 0，避免窗口收益除法异常
    return np.nan_to_num(equity, nan=0.0, posinf=0.0, neginf=0.0)


def _window_reward(equity: np.ndarray, start: int, arm: int) -> float:
    i = start
    j = min(start + HORIZON, len(equity[arm]) - 1)
    if i < 0 or i >= j:
        return 0.0
    base = equity[arm][i]
    if base <= 0:
        return 0.0
    return float(equity[arm][j] / base - 1.0)


def _choose_ucb(counts: np.ndarray, values: np.ndarray, total: int) -> int:
    """未选过的 arm 先各试一次，之后用 UCB1。"""
    for arm in range(len(counts)):
        if counts[arm] == 0:
            return arm
    score = values / counts + np.sqrt(2.0 * math.log(max(total, 1)) / counts)
    return int(np.argmax(score))


def main() -> int:
    parser = argparse.ArgumentParser(description='参数 preset bandit（UCB）')
    parser.add_argument('--check', action='store_true', help='只检查候选配置')
    args = parser.parse_args()

    if args.check:
        print('候选 preset:')
        for index, preset in enumerate(PRESETS):
            print(f'  [{index}] fast={preset["fast"]}, slow={preset["slow"]}')
        print(f'窗口: 每 {STEP} 根选一次，reward = 未来 {HORIZON} 根收益')
        print('选择器: UCB1（可替换为 ElegantRL AgentEnsembleDQN）')
        print('[example] bandit 配置检查通过')
        return 0

    kline = LocalDatas.test.kline
    print('计算候选 preset 的 Cython 权益曲线...')
    equity = np.vstack([_equity_for(kline, preset) for preset in PRESETS])
    print('权益曲线:', equity.shape)

    end = min(equity.shape[1], len(kline)) - HORIZON - 1
    counts = np.zeros(len(PRESETS), dtype=int)
    values = np.zeros(len(PRESETS), dtype=float)
    rewards = []
    choices = []

    for total, start in enumerate(range(START, end, STEP), start=1):
        arm = _choose_ucb(counts, values, total)
        reward = _window_reward(equity, start, arm)
        counts[arm] += 1
        values[arm] += reward
        rewards.append(reward)
        choices.append(arm)

    print('\n选择次数:', dict(enumerate(counts.tolist())))
    print('平均 reward:', float(np.mean(rewards)))
    for index, preset in enumerate(PRESETS):
        if counts[index]:
            print(f'  preset {index}: 平均 {values[index] / counts[index]:+.6f}')
    static = [np.nanmean([_window_reward(equity, start, arm)
                          for start in range(START, end, STEP)])
              for arm in range(len(PRESETS))]
    print('最佳静态 preset:', int(np.nanargmax(static)),
          f'平均 {np.nanmax(static):+.6f}')
    print('[example] bandit 选择完成')
    print('提示: 把 _choose_ucb 换成 ElegantRL AgentEnsembleDQN，'
          '用同样的 (state, action, reward) 训练即可。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
