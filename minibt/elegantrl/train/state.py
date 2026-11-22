"""RL 状态补全：仓位、持仓天数、浮盈、回撤。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PositionState:
    """策略当前持仓状态。

    ``unrealized_pnl`` / ``drawdown`` 建议使用**收益率**（小数），
    这样不同品种、不同价格量级可以共用同一套网络。
    """

    position: float = 0.0
    holding_days: int = 0
    unrealized_pnl: float = 0.0
    drawdown: float = 0.0

    def features(self, *, normalize: bool = True,
                 max_abs_position: float = 1.0,
                 max_holding_days: float = 60.0) -> np.ndarray:
        position = float(self.position)
        holding = float(self.holding_days)
        unrealized = float(self.unrealized_pnl)
        drawdown = float(self.drawdown)
        if normalize:
            scale = max(1e-9, abs(float(max_abs_position)))
            position = float(np.clip(position / scale, -1.0, 1.0))
            holding = float(np.clip(
                holding / max(1.0, float(max_holding_days)), 0.0, 1.0))
            unrealized = float(np.clip(unrealized, -1.0, 1.0))
            drawdown = float(np.clip(drawdown, -1.0, 0.0))
        return np.asarray(
            [position, holding, unrealized, drawdown], dtype=np.float32)


def drawdown_from_equity(equity: float, peak_equity: float) -> float:
    """``equity / peak - 1`` 的薄封装（避免示例重复写）。"""
    try:
        equity = float(equity)
        peak_equity = float(peak_equity)
    except (TypeError, ValueError):
        return 0.0
    if peak_equity <= 0:
        return 0.0
    return min(0.0, equity / peak_equity - 1.0)


def position_features(state: PositionState, **kwargs) -> np.ndarray:
    """把 :class:`PositionState` 转成固定 4 维特征。"""
    return state.features(**kwargs)


def append_state_features(obs, state: PositionState,
                          **kwargs) -> np.ndarray:
    """``指标窗口`` + ``仓位状态``，并统一展平成一维。"""
    base = np.asarray(obs, dtype=np.float32).reshape(-1)
    return np.hstack([base, position_features(state, **kwargs)]).astype(
        np.float32)


__all__ = [
    'PositionState', 'drawdown_from_equity', 'position_features',
    'append_state_features',
]
