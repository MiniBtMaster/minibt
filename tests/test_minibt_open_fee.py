"""开仓手续费必须计入每笔盈亏（回测「盈亏」图）。

历史 bug：每笔盈亏的基准在**开仓那根**才取（``entry_cp = cum[i]`` /
``entry_value = profits[i]``），而 ``cum_profits`` / 权益在开仓那根已经减过
开仓手续费 → ``exit - entry`` 把开仓手续费**抵消**掉了，只剩平仓手续费。
"""
import numpy as np
import pandas as pd
import pytest


def _empty_logger(monkeypatch):
    import minibt.logger as logger_mod

    class _Logger:
        trade_history = []

    monkeypatch.setattr(logger_mod, 'get_logger', lambda: _Logger())


# flat -> 开多(手续费5) -> flat(手续费7)；毛利 +100，净 88
_POS = [0, 1, 1, 0, 0]
_CUM = [0.0, -5.0, -5.0, 88.0, 88.0]      # cum_profits（开仓那根已 -5）
_BAL = [1000.0, 995.0, 995.0, 1088.0, 1088.0]
_CLOSE = [100.0, 100.0, 110.0, 110.0, 110.0]
_FEE = [0.0, 5.0, 5.0, 12.0, 12.0]


def _result():
    return pd.DataFrame({'positions': _POS, 'cum_profits': _CUM,
                         'total_fee': _FEE})


def test_extract_trade_lines_include_open_fee():
    from minibt.strategy.realtime import extract_trade_lines

    class FakeStrategy:
        _results = [_result()]

    frame = pd.DataFrame({'close': _CLOSE})
    lines = extract_trade_lines(FakeStrategy(), 0, frame)
    assert len(lines) == 1
    # 净盈亏 = 100 - 5 - 7 = 88（旧代码会给 93，少了开仓手续费）
    assert lines[0]['profit'] == pytest.approx(88.0)


def test_extract_trades_include_open_fee(monkeypatch):
    _empty_logger(monkeypatch)
    from minibt.strategy.realtime import RealtimeChart

    class FakeStrategy:
        pass

    records, pnl = RealtimeChart._extract_trades(
        FakeStrategy(), _result(), np.asarray(_BAL), list(range(1, 6)),
        cum_values=np.asarray(_CUM), symbol='X')
    closes = [r for r in records if r.get('pnl') is not None]
    assert len(closes) == 1
    # 交易记录里本笔盈亏含开仓手续费：100 - 5 - 7 = 88
    assert closes[0]['pnl'] == pytest.approx(88.0)
    # 盈亏散点：开仓事件 -5（开仓费）+ 平仓事件 93（88 - (-5)）= 88 ✓
    assert pnl is not None
    assert list(pnl['kind']) == ['open', 'close']
    assert float(pnl['value'].iloc[0]) == pytest.approx(-5.0)
    assert float(pnl['value'].iloc[1]) == pytest.approx(93.0)
    assert float(pnl['value'].sum()) == pytest.approx(88.0)
