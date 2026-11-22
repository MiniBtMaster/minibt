"""ElegantRL 动态仓位：RL 优化的是动作，不是静态参数。

这个例子把 ``Strategy`` 直接当 RL 环境：

    reset() -> (obs, info)
    step(action) -> (obs, reward, terminated, truncated, info)

动作是离散的 ``空 / 平 / 多``，状态是最近 N 根 K 线的指标窗口，
奖励是下一根收益 - 换手成本。训练完成后，``Bt.run()`` 会加载 actor
并在同一段数据上跑一遍推理回测。

运行::

    python tutorials/elegantrl/03_rl_position.py --check
    python tutorials/elegantrl/03_rl_position.py --steps 512
    python tutorials/elegantrl/03_rl_position.py --steps 2000

默认只训练 512 步，目的是演示接口；真实研究请用几千到几十万步，
并做 walk-forward / 样本外验证。
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np  # noqa: E402

from minibt import Agents, Bt, LocalDatas, Strategy  # noqa: E402
from minibt.elegantrl.train import (  # noqa: E402
    PositionState, RewardConfig, RewardModel, append_state_features,
    small_model_kwargs,
)


class RLPosition(Strategy):
    """离散动作：0=空仓，1=平仓，2=多仓。"""

    rl = True
    BREAK_STEP = 512
    WINDOW = 10
    COMMISSION_RATE = 0.0002
    SLIPPAGE_RATE = 0.0001
    RISK_PENALTY = 0.05

    def __init__(self):
        self.data = self.get_kline(
            LocalDatas.test, data_length=600, duration_seconds=300)
        # 这些指标会进入 signal_features，作为 RL 的观测
        self.ma = self.data.close.sma(20)
        self.rsi = self.data.close.rsi(14)
        self._close = np.asarray(self.data.close.values, dtype=float)

        # 让指标预热段不参与交易
        self.min_start_length = 60
        self.current_step = self.rl_reset_index()
        self._last_target = 0.0
        self._position = 0.0
        self._holding_days = 0
        self._entry_price = 0.0
        self._unrealized = 0.0
        self._drawdown = 0.0
        self._reward = RewardModel(RewardConfig(
            commission_rate=self.COMMISSION_RATE,
            slippage_rate=self.SLIPPAGE_RATE,
            risk_penalty=self.RISK_PENALTY,
        ))

        self.set_model_params(
            agent=Agents.AgentDiscretePPO,
            train=True,
            window_size=self.WINDOW,
            max_step=len(self._close) - 1,
            break_step=int(self.BREAK_STEP),
            learning_rate=6e-5,
            gamma=0.98,
            **small_model_kwargs(
                if_discrete=True,
                action_dim=3,
                net_dims=(64, 32),
                min_start_mode='random',
                eval_per_step=10 ** 9,  # 演示不做中途评估
                cwd=os.path.join(os.path.expanduser('~'), '.minibt',
                                 'models', 'rl_position_demo'),
                if_remove=True,
            ),
        )

    # ---------------------------------------------------------- 观测
    def _obs(self):
        end = min(self.current_step + 1, len(self.signal_features))
        start = max(0, end - self.window_size)
        obs = self.signal_features[start:end]
        state = PositionState(
            position=self._position,
            holding_days=self._holding_days,
            unrealized_pnl=self._unrealized,
            drawdown=self._drawdown,
        )
        return append_state_features(
            obs, state, max_holding_days=20.0)

    def _reset_state(self):
        self._last_target = 0.0
        self._position = 0.0
        self._holding_days = 0
        self._entry_price = 0.0
        self._unrealized = 0.0
        self._drawdown = 0.0
        self._reward.reset()

    def reset(self):
        # fixed / random / incremental 由 min_start_mode 决定
        self.current_step = self.rl_reset_index()
        self._btindex = self.current_step
        self._reset_state()
        return self._obs(), {}

    # ---------------------------------------------------------- 动作
    def _target_from_action(self, action) -> float:
        # AgentDiscretePPO: 0/1/2 -> -1/0/+1
        return float(int(np.asarray(action).reshape(-1)[0]) - 1)

    def step(self, action):
        target = self._target_from_action(action)

        i = self.current_step
        if self.train:
            # 训练：不真正下单，用下一根收益作为 reward（含成本 / 回撤惩罚）
            ret = 0.0
            if 0 <= i and i + 1 < len(self._close):
                ret = self._close[i + 1] / self._close[i] - 1.0
            reward = self._reward.step(
                self._position, target, ret)
        else:
            # 推理：真正执行目标仓位（回测账户 / 实盘由 KLine 决定）
            self.data.set_target_size(int(target))
            reward = 0.0

        # 状态：仓位 / 持仓天数 / 浮盈 / 回撤；训练、推理统一更新
        if target == 0.0:
            self._position = 0.0
            self._holding_days = 0
            self._entry_price = 0.0
            self._unrealized = 0.0
        else:
            if self._position == 0.0 or target != self._position:
                self._entry_price = (self._close[i] if 0 <= i < len(self._close)
                                     else 0.0)
                self._holding_days = 1
            else:
                self._holding_days += 1
            self._position = target
            if self._entry_price > 0 and 0 <= i < len(self._close):
                self._unrealized = target * (
                    self._close[i] / self._entry_price - 1.0)
        if self.train:
            self._drawdown = self._reward.drawdown
        self._last_target = target
        self.current_step += 1
        done = self.current_step >= self.max_step
        return self._obs(), float(reward), done, False, {}


def _make_policy(steps: int):
    policy = RLPosition.copy(name='RLPositionDemo', BREAK_STEP=int(steps))
    return policy


def main() -> int:
    parser = argparse.ArgumentParser(description='ElegantRL 动态仓位示例')
    parser.add_argument('--check', action='store_true',
                        help='只检查环境和维度，不训练')
    parser.add_argument('--steps', type=int, default=512,
                        help='训练步数（默认 512；真实研究请调大）')
    args = parser.parse_args()

    policy = _make_policy(args.steps)

    if args.check:
        strategy = policy()
        strategy._prepare_before_strategy_start()
        print('state_dim:', strategy.state_dim)
        print('action_dim:', strategy.action_dim)
        print('if_discrete:', strategy.if_discrete)
        print('max_step:', strategy.max_step)
        print('signal_features:', strategy.signal_features.shape)
        print('reward = 下一根收益 - 手续费 - 滑点 - 回撤惩罚')
        print('[example] RL 环境检查通过（不训练）')
        return 0

    bt = Bt(auto=False)
    bt.addstrategy(policy)
    # 训练完成后自动 load_agent，再用同一段数据推理回测
    bt.run(isplot=False, isreport=False)
    print('[example] RL 训练 + 推理完成')
    print('模型目录: ~/.minibt/models/rl_position_demo')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
