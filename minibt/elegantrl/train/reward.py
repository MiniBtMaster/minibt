"""RL 奖励成本模型：手续费、滑点、换手与回撤风险。"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class RewardConfig:
    """奖励中的交易成本 / 风险参数。

    - ``commission_rate``：单位换手的手续费率；
    - ``slippage_rate``：单位换手的滑点率；
    - ``risk_penalty``：回撤惩罚系数，``risk = risk_penalty * abs(drawdown)``；
    - ``reward_scale``：最终奖励缩放。
    """

    commission_rate: float = 0.0
    slippage_rate: float = 0.0
    risk_penalty: float = 0.0
    reward_scale: float = 1.0
    min_equity: float = 1e-9


@dataclass
class RewardBreakdown:
    """一步奖励的分解，便于排查“成本把收益吃光”的问题。"""

    gross: float
    commission: float
    slippage: float
    risk: float
    net: float
    turnover: float
    drawdown: float

    def to_dict(self) -> dict:
        return asdict(self)


def drawdown_from_equity(equity: float, peak_equity: float) -> float:
    """返回 ``equity / peak - 1``，没有峰值时返回 0。"""
    try:
        equity = float(equity)
        peak_equity = float(peak_equity)
    except (TypeError, ValueError):
        return 0.0
    if peak_equity <= 0:
        return 0.0
    return min(0.0, equity / peak_equity - 1.0)


def compute_reward(
    prev_position: float,
    position: float,
    next_return: float = 0.0,
    *,
    gross_return: float | None = None,
    equity: float | None = None,
    peak_equity: float | None = None,
    config: RewardConfig | None = None,
    return_breakdown: bool = False,
):
    """计算一步净奖励。

    默认 ``gross = position * next_return``；如果策略已经算好了价差 / 配对
    收益，可以传 ``gross_return`` 直接跳过这一步乘法。
    """
    cfg = config or RewardConfig()
    prev_position = float(prev_position)
    position = float(position)
    turnover = abs(position - prev_position)
    gross = (float(gross_return) if gross_return is not None
             else position * float(next_return))
    commission = float(cfg.commission_rate) * turnover
    slippage = float(cfg.slippage_rate) * turnover
    dd = (drawdown_from_equity(equity, peak_equity)
          if equity is not None and peak_equity is not None else 0.0)
    risk = float(cfg.risk_penalty) * abs(dd)
    net = (gross - commission - slippage - risk) * float(cfg.reward_scale)
    breakdown = RewardBreakdown(
        gross=float(gross), commission=float(commission),
        slippage=float(slippage), risk=float(risk), net=float(net),
        turnover=float(turnover), drawdown=float(dd),
    )
    return breakdown if return_breakdown else float(net)


class RewardModel:
    """带权益 / 回撤状态的奖励模型。

    适合奖励已经是“收益率”的场景；如果奖励是价差绝对值，请直接用
    :func:`compute_reward` 并自行维护权益。
    """

    def __init__(self, config: RewardConfig | None = None,
                 initial_equity: float = 1.0):
        self.config = config or RewardConfig()
        self.initial_equity = float(initial_equity)
        self.equity = float(initial_equity)
        self.peak_equity = float(initial_equity)
        self.last: RewardBreakdown | None = None

    def reset(self):
        self.equity = float(self.initial_equity)
        self.peak_equity = float(self.initial_equity)
        self.last = None

    @property
    def drawdown(self) -> float:
        return drawdown_from_equity(self.equity, self.peak_equity)

    def step(self, prev_position: float, position: float,
             next_return: float = 0.0, *, gross_return: float | None = None,
             return_breakdown: bool = False):
        breakdown = compute_reward(
            prev_position, position, next_return,
            gross_return=gross_return,
            equity=self.equity, peak_equity=self.peak_equity,
            config=self.config, return_breakdown=True,
        )
        self.equity = max(float(self.config.min_equity),
                          self.equity * (1.0 + breakdown.net))
        self.peak_equity = max(self.peak_equity, self.equity)
        self.last = breakdown
        return breakdown if return_breakdown else float(breakdown.net)


__all__ = [
    'RewardConfig', 'RewardBreakdown', 'RewardModel',
    'compute_reward', 'drawdown_from_equity',
]
