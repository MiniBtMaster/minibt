"""交易/验证指标：给 walk-forward / 独立 eval_env 用的轻量工具。

不依赖 QuantStats，只从权益曲线或收益率计算样本外常用指标。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _series(values) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.astype(float).reset_index(drop=True)
    return pd.Series(np.asarray(values, dtype=float))


def equity_metrics(equity, *, periods_per_year: float = 252.0,
                   risk_free: float = 0.0) -> dict:
    """从权益曲线计算净收益 / 风险指标。

    Args:
        equity: 权益曲线（每个 bar 一个点）
        periods_per_year: 年化周期数。日线 252；1 分钟线通常
            ``252 * 240`` 或按实际交易分钟数调整。
        risk_free: 年化无风险利率。

    Returns:
        包含 total_return / cagr / sharpe / sortino / max_drawdown /
        calmar / volatility / final_equity 的字典。
    """
    eq = _series(equity)
    eq = eq.replace([np.inf, -np.inf], np.nan).dropna()
    if len(eq) < 2:
        return {
            'total_return': 0.0, 'cagr': 0.0, 'sharpe': 0.0,
            'sortino': 0.0, 'max_drawdown': 0.0, 'calmar': 0.0,
            'volatility': 0.0, 'final_equity': float(eq.iloc[-1])
            if len(eq) else 0.0,
        }

    ret = eq.pct_change().dropna()
    n = max(1, len(ret))
    rf_per_bar = float(risk_free) / max(1.0, periods_per_year)
    excess = ret - rf_per_bar

    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    cagr = float((1.0 + total_return) ** (periods_per_year / n) - 1.0)
    std = float(ret.std(ddof=1))
    volatility = float(std * np.sqrt(periods_per_year))
    sharpe = (float(excess.mean()) / std * np.sqrt(periods_per_year)
              if std > 1e-12 else 0.0)
    downside = ret[ret < 0]
    down_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino = (float(excess.mean()) / down_std * np.sqrt(periods_per_year)
               if down_std > 1e-12 else 0.0)
    drawdown = eq / eq.cummax() - 1.0
    max_dd = float(drawdown.min())
    calmar = float(cagr / abs(max_dd)) if max_dd < -1e-12 else 0.0

    return {
        'total_return': total_return,
        'cagr': cagr,
        'sharpe': sharpe,
        'sortino': sortino,
        'max_drawdown': max_dd,
        'calmar': calmar,
        'volatility': volatility,
        'final_equity': float(eq.iloc[-1]),
    }


def returns_metrics(returns, *, periods_per_year: float = 252.0,
                    risk_free: float = 0.0) -> dict:
    """从每 bar 收益率计算与 :func:`equity_metrics` 相同的指标。"""
    ret = _series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    # 首点权益 = 1，后面按收益率累乘；与 equity_metrics 的口径一致
    eq = np.concatenate(([1.0], (1.0 + ret).cumprod().to_numpy()))
    return equity_metrics(eq, periods_per_year=periods_per_year,
                          risk_free=risk_free)


__all__ = ['equity_metrics', 'returns_metrics']
