"""回测图表（``miniqt/app/windows/backtest_chart.py``）的纯函数测试。

这里只测**不建控件**的部分：策略 K 线 → pylightcharts 的 DataFrame、成交流水 →
买卖点标记。之前 ``strategy_candles`` 里一句缩进写错（``columns`` 落进了 ``else``
分支）就导致整张图建不出来 —— 这种错必须由这里的测试拦住。

    pytest tests/test_miniqt_backtest_chart.py
"""
from __future__ import annotations

import os
import pathlib
import sys

import pandas as pd
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

pytest.importorskip('PyQt6')
chart = pytest.importorskip('miniqt.app.windows.backtest_chart')


class FakeKLine:
    """只有 ``pandas_object``（策略里那种 K 线数据集元素）。"""

    def __init__(self, frame):
        self.pandas_object = frame


def _frame(datetime_values, rows=3):
    data = {
        'datetime': datetime_values,
        'open': [1.0] * rows,
        'high': [2.0] * rows,
        'low': [0.5] * rows,
        'close': [1.5] * rows,
        'volume': [10] * rows,
    }
    return pd.DataFrame(data)


def test_strategy_candles_converts_datetime64():
    """datetime64 走 int64（纳秒）分支，且必须带上 time 列。"""
    strategy = type('S', (), {})
    strategy._btklinedataset = {0: FakeKLine(
        _frame(pd.date_range('2024-01-01', periods=3, freq='min')))}
    frame = chart.strategy_candles(strategy)
    assert frame is not None
    assert list(frame.columns) == ['time', 'open', 'high', 'low', 'close',
                                   'volume']
    assert len(frame) == 3
    # 必须是 **datetime64**（整数秒会让图表只画坐标轴、不画 K 线）
    assert pd.api.types.is_datetime64_any_dtype(frame['time'])
    assert frame['time'].iloc[0] == pd.Timestamp('2024-01-01 08:00:00')


def test_to_chart_time_normalises_every_unit():
    """ns / µs / ms / s 都要归一成 datetime64（并补 8 小时北京时间）。"""
    base = 1_700_000_000
    expected = pd.Timestamp(base, unit='s') + pd.Timedelta(hours=8)
    for raw in (base, base * 1000, base * 10 ** 6, base * 10 ** 9):
        result = chart.to_chart_time([raw] * 3)
        assert pd.api.types.is_datetime64_any_dtype(result)
        assert result.iloc[0] == expected, raw


def test_to_chart_time_handles_timezone_aware_input():
    """策略里的 datetime 可能是 tz-aware —— astype 会直接报错，必须先把时区抹掉。"""
    aware = pd.date_range('2024-01-01 08:00', periods=3, freq='min', tz='UTC')
    result = chart.to_chart_time(aware)
    assert pd.api.types.is_datetime64_any_dtype(result)
    assert getattr(result.dt, 'tz', None) is None
    # UTC 08:00 → 北京 16:00
    assert result.iloc[0] == pd.Timestamp('2024-01-01 16:00:00')


def test_strategy_candles_skips_unusable_sources():
    strategy = type('S', (), {})
    strategy._btklinedataset = {0: FakeKLine(pd.DataFrame({'foo': [1]}))}
    assert chart.strategy_candles(strategy) is None
    strategy._btklinedataset = {}
    assert chart.strategy_candles(strategy) is None
    assert chart.strategy_candles(object()) is None


def test_trades_to_markers_maps_indices_to_times():
    times = [1000, 2000, 3000, 4000, 5000]
    records = [
        {'direction': '多', 'time': '1→3', 'pnl': 12.5, 'fee': 0.0},
        {'direction': '空', 'time': '4→0', 'pnl': -3.0, 'fee': 1.0},
    ]
    markers = chart.trades_to_markers(records, times)
    # 按时间排序（LWC 要求），所以是 t=1000 出场、2000 入场、4000 出场、5000 入场
    assert [m['text'] for m in markers] == ['X', 'B', 'X', 'S']
    by_text = {}
    for marker in markers:
        by_text.setdefault(marker['text'], marker)
    assert by_text['B']['shape'] == 'arrow_up'
    assert by_text['B']['position'] == 'below'
    assert by_text['S']['shape'] == 'arrow_down'
    assert by_text['S']['position'] == 'above'
    assert {m['time'] for m in markers} <= set(times)


def test_trades_to_markers_ignores_bad_rows():
    times = [1000, 2000]
    records = [
        {'direction': '多', 'time': 'oops'},
        {'direction': '多'},                       # 没有 time
        {'direction': '多', 'time': '0→99'},        # 越界下标被跳过
    ]
    markers = chart.trades_to_markers(records, times)
    assert [m['text'] for m in markers] == ['B']   # 只有入场那一条
    assert chart.trades_to_markers(None, times) == []
    assert chart.trades_to_markers([{'time': '0→1'}], []) == []


def test_is_available_respects_the_legacy_switch(monkeypatch):
    monkeypatch.setenv('MINIQT_LEGACY_REPLAY', '1')
    assert chart.is_available() is False
    monkeypatch.delenv('MINIQT_LEGACY_REPLAY', raising=False)
    assert chart.is_available() is bool(
        chart.is_available())              # 环境里能建就是 True，不强制
