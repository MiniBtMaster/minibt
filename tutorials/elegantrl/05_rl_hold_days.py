"""旧 ``rl = True`` 示例整理版：持仓天数动作 + 多指标特征。

对应以前的：

- ``77_3 / 77_5 / 77_7 / 77_8 / 77_9 / 77_10``：离散动作
- ``77_4 / 77_6 / 77_11 / 77_12 / 77_13 / 700005``：连续动作

统一成一条 ``hold days`` 逻辑：

    动作 0..5 / 连续 [-1,1] → 持仓 -3..-1 / +1..+3 根
    训练奖励 = 未来 1/2/3 根的价格变化
    推理时 = 真正 buy/sell，并按持仓天数倒计时平仓

运行::

    python tutorials/elegantrl/05_rl_hold_days.py --check
    python tutorials/elegantrl/05_rl_hold_days.py --agent d3qn --steps 256
    python tutorials/elegantrl/05_rl_hold_days.py --agent ppo --steps 256

注意：旧示例使用的 ``v2509_60`` 数据已不在当前内置数据中，
这里统一改用 ``LocalDatas.test``，这样仓库里可以直接运行。
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

#: 旧示例里出现过的算法；连续/离散按算法本身自动选择
AGENTS = {
    'd3qn': (Agents.AgentD3QN, True),
    'double-dqn': (Agents.AgentDoubleDQN, True),
    'dueling-dqn': (Agents.AgentDuelingDQN, True),
    'ensemble-dqn': (Agents.AgentEnsembleDQN, True),
    'discrete-ppo': (Agents.AgentDiscretePPO, True),
    'ppo': (Agents.AgentPPO, False),
    'ddpg': (Agents.AgentDDPG, False),
    'td3': (Agents.AgentTD3, False),
    'sac': (Agents.AgentSAC, False),
    'mod-sac': (Agents.AgentModSAC, False),
}


class RLHoldDays(Strategy):
    """多指标特征 + 持仓天数动作。"""

    rl = True
    STEPS = 5e4
    AGENT = 'discrete-ppo'
    TRAIN = True
    ACTOR_PATH = ''
    DATA = None
    FIT_RANGE = None
    FEATURE_STATE = None
    CWD = ''
    WINDOW = 10
    COMMISSION_RATE = 0.0002
    SLIPPAGE_RATE = 0.0001
    RISK_PENALTY = 0.05

    def __init__(self):
        source = self.DATA if self.DATA is not None else LocalDatas.test
        self.data = self.get_kline(source).iloc[:8000]
        self._close = np.asarray(self.data.close.values, dtype=float)

        # 旧示例的特征集（精简版）：趋势 / 震荡 / 波动 / 量价
        self.ma3 = self.data.close.sma(3)
        self.ma8 = self.data.close.sma(8)
        self.ma21 = self.data.close.sma(21)
        self.ma55 = self.data.close.sma(55)
        self.zscore20 = self.data.close.zscore(20)
        self.rsi = self.data.close.rsi()
        self.atr = self.data.atr(14)
        self.std = self.data.close.stdev(14)
        self.cci = self.data.close.cci(14)
        self.adx = self.data.close.adx(14).iloc[:, 0]

        # 旧示例用 robust + log + clip；保留同一套特征处理
        self.set_process_quant_features(
            normalize_method='robust',
            use_log_transform=True,
            handle_outliers='clip',
            fit_range=self.FIT_RANGE,
        )
        # walk-forward 的 val / test 复用 train 的 scaler / PCA / 阈值
        if self.FEATURE_STATE is not None:
            self.set_quant_feature_state(self.FEATURE_STATE)

        # 未来 1/2/3 根收益率，作为训练奖励（用收益率而非价格差，
        # 这样手续费 / 滑点 / 回撤惩罚可以按比例统一扣减）
        close = self.data.pandas_object.close
        self.long_prices = [
            close.pct_change().shift(-i).values for i in range(1, 4)]
        self.short_prices = [-x for x in self.long_prices]

        self.min_start_length = 120
        self.current_step = self.rl_reset_index()
        self.hoding_day = 0
        self.last_action = 0
        self._target = 0.0
        self._hold_left = 0
        self._position = 0.0
        self._entry_price = 0.0
        self._unrealized = 0.0
        self._drawdown = 0.0
        self._reward = RewardModel(RewardConfig(
            commission_rate=self.COMMISSION_RATE,
            slippage_rate=self.SLIPPAGE_RATE,
            risk_penalty=self.RISK_PENALTY,
        ))

        agent_cls, discrete = AGENTS[self.AGENT]
        self.set_model_params(
            agent_cls,
            train=bool(self.TRAIN),
            actor_path=str(self.ACTOR_PATH),
            window_size=self.WINDOW,
            break_step=5e4,
            **small_model_kwargs(
                if_discrete=discrete,
                action_dim=6 if discrete else 1,
                net_dims=(64, 32),
                min_start_mode='random',
                eval_per_step=5e3,
                cwd=(self.CWD or os.path.join(
                    os.path.expanduser('~'), '.minibt', 'models',
                    f'rl_hold_{self.AGENT}')),
                if_remove=bool(self.TRAIN),
            ),
        )
        # 最后 3 根没有未来收益
        self.max_step -= 4

        self.data.price_tick = 1.0
        self.data.volume_multiple = 5.0
        self.data.fixed_commission = 0.0

    # ---------------------------------------------------------- 观测
    def _obs(self):
        end = min(self.current_step + 1, len(self.signal_features))
        start = max(0, end - self.window_size)
        obs = self.signal_features[start:end]
        if self.train:
            base = self.data_enhancement(obs, rate=0.3)
            pos, hold = self._position, self._hold_left
        else:
            base = obs.flatten()
            pos = float(getattr(self.data.position, 'pos', self.data.position)
                        or 0.0)
            hold = self.hoding_day
        # 状态补全：仓位 / 持仓天数 / 浮盈 / 回撤
        state = PositionState(
            position=pos,
            holding_days=hold,
            unrealized_pnl=self._unrealized,
            drawdown=self._drawdown,
        )
        return append_state_features(
            base, state, max_holding_days=10.0)

    def _reset_state(self):
        self.hoding_day = 0
        self.last_action = 0
        self._target = 0.0
        self._hold_left = 0
        self._position = 0.0
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
    def _hold_days(self, action) -> int:
        """0..5 或连续 [-1,1] → -3..-1 / +1..+3。"""
        if self.if_discrete:
            raw = int(np.asarray(action).reshape(-1)[0])
        else:
            x = float(np.asarray(action).reshape(-1)[0])
            raw = int(round(0 + (np.clip(x, -1, 1) + 1) * 5 / 2))
        raw = min(5, max(0, raw))
        hold = raw - 3
        return hold + 1 if hold >= 0 else hold

    def step(self, action):
        hold = self._hold_days(action)
        i = self.current_step
        reward = 0.0
        prev_position = self._position

        if self.train:
            # 供下一次观测使用：动作方向 + 剩余持仓
            self._target = float(np.sign(hold))
            if hold:
                self._hold_left = abs(hold)
            else:
                self._hold_left = max(0, self._hold_left - 1)
            gross = 0.0
            if 0 <= i < len(self._close):
                if hold > 0:
                    gross = float(self.long_prices[hold - 1][i])
                elif hold < 0:
                    gross = float(self.short_prices[-hold - 1][i])
            # 成本 + 回撤惩罚都在 RewardModel 里扣
            reward = self._reward.step(prev_position, self._target, gross)
            self._position = self._target
            self._drawdown = self._reward.drawdown
        else:
            pos = self.data.position
            if pos == 0:
                if hold > 0:
                    self.data.buy()
                    self.hoding_day = hold
                    self.last_action = hold
                    self._entry_price = (self._close[i]
                                         if 0 <= i < len(self._close) else 0.0)
                elif hold < 0:
                    self.data.sell()
                    self.hoding_day = -hold
                    self.last_action = hold
                    self._entry_price = (self._close[i]
                                         if 0 <= i < len(self._close) else 0.0)
            elif pos > 0:
                if hold > 0:
                    self.hoding_day = min(hold, self.hoding_day)
                self.hoding_day -= 1
                if self.hoding_day <= 0:
                    self.data.sell()
                    self._entry_price = 0.0
            else:
                if hold < 0:
                    self.hoding_day = min(-hold, self.hoding_day)
                self.hoding_day -= 1
                if self.hoding_day <= 0:
                    self.data.buy()
                    self._entry_price = 0.0
            self._position = float(getattr(self.data.position, 'pos',
                                           self.data.position) or 0.0)
            if (self._position and self._entry_price > 0
                    and 0 <= i < len(self._close)):
                self._unrealized = self._position * (
                    self._close[i] / self._entry_price - 1.0)
            else:
                self._unrealized = 0.0

        # 训练分支也要更新浮盈，供下一次 _obs()
        if self.train:
            if self._position and self._entry_price <= 0:
                self._entry_price = (self._close[i]
                                     if 0 <= i < len(self._close) else 0.0)
            if self._position == 0:
                self._entry_price = 0.0
                self._unrealized = 0.0
            elif self._entry_price > 0 and 0 <= i < len(self._close):
                self._unrealized = self._position * (
                    self._close[i] / self._entry_price - 1.0)

        self.current_step += 1
        done = self.current_step >= self.max_step
        return self._obs(), float(reward), done, False, {}


def _policy(args):
    # ★ 不传 --steps 时使用类里的 STEPS；旧写法默认 256 会覆盖 STEPS=5e4
    steps = (int(args.steps) if args.steps is not None
             else int(RLHoldDays.STEPS))
    return RLHoldDays.copy(
        name='RLHoldDaysDemo',
        AGENT=args.agent,
        STEPS=steps,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='RL 持仓天数示例')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--steps', type=int, default=None,
                        help='训练步数（默认使用类里的 STEPS）')
    parser.add_argument('--agent', choices=sorted(AGENTS),
                        default='discrete-ppo')
    args = parser.parse_args()
    policy = _policy(args)

    if args.check:
        strategy = policy()
        strategy._prepare_before_strategy_start()
        print('agent:', args.agent)
        print('state_dim:', strategy.state_dim)
        print('action_dim:', strategy.action_dim)
        print('if_discrete:', strategy.if_discrete)
        print('max_step:', strategy.max_step)
        print('signal_features:', strategy.signal_features.shape)
        print('break_step:', strategy._rl_config.break_step)
        print('[example] RL hold-days 检查通过')
        return 0

    bt = Bt(auto=False)
    bt.addstrategy(policy)
    bt.run(isplot=False, isreport=False)
    print(f'[example] {args.agent} 训练 + 推理完成')
    print(f'模型目录: ~/.minibt/models/rl_hold_{args.agent}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
