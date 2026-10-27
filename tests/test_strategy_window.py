"""`StrategyWindow._has_backtest` 的判定：纯指标策略（无 `next`）不该显示信息页。

用户反馈 `vp.py` 的四个纯 VP 策略（`VPMode1` / `VPMode2` / `VPMulti` / `VPMode3`）
都没有 `next`、不交易，却出现了「回测结果 / 指标记录」两个信息页。根因是
`_has_backtest()` 以前只要 `equity is not None` 就算“有回测数据”，而不交易的
策略回测循环照跑、会得到一条**恒定等于期初资金**的权益曲线。
"""
import pandas as pd


def _window(backtests):
    from minibt.strategy.strategy_window import StrategyWindow

    win = StrategyWindow.__new__(StrategyWindow)   # 不跑 __init__（不需要真图表）
    win.strategy = 'S'
    win.backtests = backtests
    return win


def test_has_backtest_ignores_flat_equity():
    """恒定权益（没交易过）+ 无成交 → 不算回测数据（不显示两页）。"""
    flat = pd.DataFrame({'time': [0, 1, 2], 'value': [1e6, 1e6, 1e6]})
    win = _window({'S': {'trades': None, 'equity': flat}})
    assert win._has_backtest() is False


def test_has_backtest_true_when_equity_moves():
    moving = pd.DataFrame({'time': [0, 1, 2], 'value': [1e6, 1e6 + 5, 1e6 + 3]})
    win = _window({'S': {'trades': None, 'equity': moving}})
    assert win._has_backtest() is True


def test_has_backtest_true_when_trades_exist():
    """有成交记录就算（哪怕这一刻权益还没变化，如刚开仓未平）。"""
    win = _window({'S': {'trades': [{'a': 1}], 'equity': None}})
    assert win._has_backtest() is True


def test_has_backtest_false_without_data():
    win = _window({})
    assert win._has_backtest() is False
