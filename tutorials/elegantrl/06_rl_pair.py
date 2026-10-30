"""旧 ``77_31 / 78_1`` 配对 RL 示例整理版。

把两条腿的价差作为状态/奖励来源：

    动作 0 = 观望 / 保持
    动作 1 = 做多价差（多 pp、空 l）
    动作 2 = 做空价差（空 pp、多 l）

训练奖励按“开仓价差 → 当前价差”的差计算；推理时真正对两条腿 buy/sell。
旧示例使用的 ``pp2509_60 / v2509_60`` 已不在当前内置数据中，这里改成
``pp2609_60 / l2609_60``。

运行::

    python tutorials/elegantrl/06_rl_pair.py --check
    python tutorials/elegantrl/06_rl_pair.py --steps 256
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
    PositionState, RewardConfig, append_state_features, compute_reward,
    drawdown_from_equity, small_model_kwargs,
)


class RLPairSpread(Strategy):
    """pp - l 价差配对，动作 0/1/2。"""

    rl = True
    STEPS = 256
    WINDOW = 10
    COMMISSION_RATE = 0.0002
    SLIPPAGE_RATE = 0.0001
    RISK_PENALTY = 0.05

    def __init__(self):
        self.data = self.get_kline(
            LocalDatas.pp2609_60, data_length=900)
        self.data1 = self.get_kline(
            LocalDatas.l2609_60, data_length=900)

        self._pp = np.asarray(self.data.close.values, dtype=float)
        self._ll = np.asarray(self.data1.close.values, dtype=float)

        # 价差特征（旧示例也是围绕价差做指标）
        self.spread = self.data.close - self.data1.close
        self.spread_z = self.spread.zscore(20)
        self.spread_std = self.spread.rolling(20).std()
        self.spread_diff = self.spread.diff(5)
        self.bbands = self.spread.pairtrading.bollinger_bands(window=20)
        self.set_process_quant_features(
            normalize_method='robust',
            use_log_transform=True,
            handle_outliers='clip',
        )

        self.min_start_length = 120
        self.current_step = self.rl_reset_index()
        self.pos = 0
        self.last_price = [0.0, 0.0]
        self._holding_days = 0
        self._entry_spread = 0.0
        self._unrealized = 0.0
        self._equity = 1.0
        self._peak_equity = 1.0
        self._drawdown = 0.0
        self._reward_config = RewardConfig(
            commission_rate=self.COMMISSION_RATE,
            slippage_rate=self.SLIPPAGE_RATE,
            risk_penalty=self.RISK_PENALTY,
        )

        self.set_model_params(
            Agents.AgentDiscretePPO,
            train=True,
            window_size=self.WINDOW,
            break_step=int(self.STEPS),
            **small_model_kwargs(
                if_discrete=True,
                action_dim=3,
                net_dims=(64, 32),
                min_start_mode='random',
                eval_per_step=10 ** 9,
                cwd=os.path.join(os.path.expanduser('~'), '.minibt',
                                 'models', 'rl_pair_spread'),
                if_remove=True,
            ),
        )
        self.max_step -= 1

        for kline in (self.data, self.data1):
            kline.margin_rate = 0.11
            kline.price_tick = 1.0
            kline.volume_multiple = 5.0
            kline.fixed_commission = 0.0

    # ---------------------------------------------------------- 观测
    def _obs(self):
        end = min(self.current_step + 1, len(self.signal_features))
        start = max(0, end - self.window_size)
        obs = self.signal_features[start:end]
        base = (self.data_enhancement(obs, rate=0.3)
                if self.train else obs.flatten())
        state = PositionState(
            position=(self.pos if self.train else float(
                getattr(self.data.position, 'pos', self.data.position) or 0.0)),
            holding_days=self._holding_days,
            unrealized_pnl=self._unrealized,
            drawdown=self._drawdown,
        )
        return append_state_features(
            base, state, max_holding_days=20.0)

    def _reset_state(self):
        self.pos = 0
        self.last_price = [0.0, 0.0]
        self._holding_days = 0
        self._entry_spread = 0.0
        self._unrealized = 0.0
        self._equity = 1.0
        self._peak_equity = 1.0
        self._drawdown = 0.0

    def reset(self):
        # fixed / random / incremental 由 min_start_mode 决定
        self.current_step = self.rl_reset_index()
        self._btindex = self.current_step
        self._reset_state()
        return self._obs(), {}

    # ---------------------------------------------------------- 动作
    def step(self, action):
        action = int(np.asarray(action).reshape(-1)[0])
        i = self.current_step
        pp = self._pp[i]
        ll = self._ll[i]
        reward = 0.0
        prev_pos = self.pos

        if self.train:
            if action == 1:
                if self.pos < 0:
                    reward = (self.last_price[0] - pp
                              + ll - self.last_price[1])
                    self.pos = 0
                elif self.pos == 0:
                    self.last_price = [pp, ll]
                    self.pos = 1
            elif action == 2:
                if self.pos > 0:
                    reward = (pp - self.last_price[0]
                              + self.last_price[1] - ll)
                    self.pos = 0
                elif self.pos == 0:
                    self.last_price = [pp, ll]
                    self.pos = -1
            # 两条腿换手成本在后面的 compute_reward() 统一扣
        else:
            pp_pos = self.data.position
            ll_pos = self.data1.position
            if pp_pos == 0 and ll_pos == 0:
                if action == 1:
                    self.data.buy()
                    self.data1.sell()
                elif action == 2:
                    self.data.sell()
                    self.data1.buy()
            elif pp_pos < 0 and ll_pos > 0:
                if action == 1:
                    self.data.buy()
                    self.data1.sell()
            elif pp_pos > 0 and ll_pos < 0:
                if action == 2:
                    self.data.sell()
                    self.data1.buy()

        # 统一成本 / 风险：训练和推理都更新持仓状态
        if self.train:
            reward = compute_reward(
                prev_pos, self.pos, gross_return=reward,
                equity=self._equity, peak_equity=self._peak_equity,
                config=self._reward_config,
            )
            spread = pp - ll
            if self.pos == 0:
                self._holding_days = 0
                self._entry_spread = 0.0
                self._unrealized = 0.0
            else:
                if prev_pos == 0 or self.pos != prev_pos:
                    self._entry_spread = spread
                    self._holding_days = 1
                else:
                    self._holding_days += 1
                self._unrealized = self.pos * (
                    (spread - self._entry_spread)
                    / max(abs(self._entry_spread), 1e-9))
            self._equity = max(1e-9, self._equity + reward / max(
                abs(spread), 1e-9))
            self._peak_equity = max(self._peak_equity, self._equity)
            self._drawdown = drawdown_from_equity(
                self._equity, self._peak_equity)
        else:
            pp_pos = float(getattr(self.data.position, 'pos',
                                   self.data.position) or 0.0)
            ll_pos = float(getattr(self.data1.position, 'pos',
                                   self.data1.position) or 0.0)
            self.pos = pp_pos
            spread = pp - ll
            if pp_pos and ll_pos:
                if self._entry_spread == 0.0:
                    self._entry_spread = spread
                    self._holding_days = 1
                else:
                    self._holding_days += 1
                self._unrealized = self.pos * (
                    (spread - self._entry_spread)
                    / max(abs(self._entry_spread), 1e-9))
            else:
                self._holding_days = 0
                self._entry_spread = 0.0
                self._unrealized = 0.0
            reward = 0.0

        self.current_step += 1
        done = self.current_step >= self.max_step
        return self._obs(), float(reward), done, False, {}


def _policy(args):
    return RLPairSpread.copy(
        name='RLPairSpreadDemo', STEPS=int(args.steps))


def main() -> int:
    parser = argparse.ArgumentParser(description='RL 配对价差示例')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--steps', type=int, default=256)
    args = parser.parse_args()
    policy = _policy(args)

    if args.check:
        strategy = policy()
        strategy._prepare_before_strategy_start()
        print('state_dim:', strategy.state_dim)
        print('action_dim:', strategy.action_dim)
        print('if_discrete:', strategy.if_discrete)
        print('max_step:', strategy.max_step)
        print('signal_features:', strategy.signal_features.shape)
        print('动作: 0=观望 1=多价差 2=空价差')
        print('reward = 价差收益 - 手续费 - 滑点 - 回撤惩罚')
        print('[example] RL 配对检查通过')
        return 0

    bt = Bt(auto=False)
    bt.addstrategy(policy)
    bt.run(isplot=False, isreport=False)
    print('[example] RL 配对训练 + 推理完成')
    print('模型目录: ~/.minibt/models/rl_pair_spread')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
