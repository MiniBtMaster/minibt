"""策略初始化 / 逻辑 next 的分频与 on_close（上一根完成后再跑）✓"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from minibt import Config, LocalDatas, Strategy
from minibt.desk.strategy_runner import StrategyRunner


def _frame(rows=12, base=100.0):
    close = [base + index * 0.5 for index in range(rows)]
    return pd.DataFrame({
        'datetime': pd.date_range('2024-01-01', periods=rows, freq='1min'),
        'open': close, 'high': [value + 1 for value in close],
        'low': [value - 1 for value in close], 'close': close,
        'volume': [10.0] * rows, 'symbol': 'test', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })


def _strategy():
    class Counter(Strategy):
        params = {}
        config = Config(on_close=True)
        init_calls = 0
        next_calls = 0
        last_index = -1

        def __init__(self):
            Counter.init_calls += 1
            self.data = self.get_kline(LocalDatas.test)

        def next(self):
            Counter.next_calls += 1
            Counter.last_index = int(getattr(self, '_btindex', -1))

    return Counter


def _runner(strategy_cls):
    runner = StrategyRunner(strategy_cls, symbol='test', cycle=60)
    runner.prepare([('test', _frame(12))], seed_kline=True)
    return runner


def test_on_close_runs_next_on_previous_completed_bar():
    cls = _strategy()
    runner = _runner(cls)
    frame = _frame(12)
    # 第一拍：__init__ 后按**上一根已完成**的 K 线跑一次 next（index 11）✓
    assert runner.advance([frame]) is True
    assert cls.init_calls >= 1
    assert cls.next_calls == 1
    assert cls.last_index == 10
    # 同一根 K 线：继续更新指标，但不重复跑 next
    assert runner.advance([frame]) is True
    assert cls.next_calls == 1
    # 新 K 线出现：on_close=True → 跑**上一根**（index 11），不是新的一根 12
    frame2 = _frame(13)
    assert runner.advance([frame2]) is True
    assert cls.next_calls == 2
    assert cls.last_index == 11


def test_on_close_false_uses_latest_bar():
    cls = _strategy()
    cls.config = Config(on_close=False)
    runner = _runner(cls)
    runner.advance([_frame(12)])
    assert cls.next_calls == 1
    frame2 = _frame(13)
    runner.advance([frame2])
    assert cls.next_calls == 2
    assert cls.last_index == 12


def test_frequency_mode_runs_next_when_data_changes():
    cls = _strategy()
    cls.config = Config(on_close=True)
    runner = _runner(cls)
    runner.override = {'next_on_new_bar': False}
    frame = _frame(12)
    runner.advance([frame])
    assert cls.next_calls == 1      # 频率模式：第一拍有数据就运行
    # 同一根 K 线、close 不变 → 不重复运行 next
    runner.advance([frame])
    assert cls.next_calls == 1
    # 同一根 K 线、close 变化 → 有新数据，运行 next
    frame2 = frame.copy()
    frame2.loc[frame2.index[-1], 'close'] = 101.0
    runner.advance([frame2])
    assert cls.next_calls == 2


def test_run_next_false_only_refreshes_init():
    cls = _strategy()
    runner = _runner(cls)
    runner.override = {'run_next': False}
    runner.advance([_frame(12)])
    runner.advance([_frame(13)])
    assert cls.next_calls == 0
    assert cls.init_calls >= 2
