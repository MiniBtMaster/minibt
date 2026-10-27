"""Indicator auto-refresh: full refresh on set(), incremental on update(),
and batching of bridge calls."""
import json

import numpy as np
import pandas as pd
import pytest

from pylightcharts import indicators
from pylightcharts.abstract import AbstractChart, Window


def _frame(rows, start='2020-01-01'):
    rng = np.random.default_rng(4)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': pd.date_range(start, periods=rows, freq='D'),
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': rng.integers(1, 1000, rows),
    })


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    return chart


def _payload(captured, series_id, method):
    marker = f'{series_id}.series.{method}('
    scripts = [s for s in captured if marker in s]
    assert scripts, f'no {method}() for {series_id}'
    return json.loads(scripts[-1].split(marker, 1)[1].rsplit(')', 1)[0])


def _next_bar(df, delta=3.0):
    time = df['time'].iloc[-1] + pd.Timedelta(days=1)
    close = float(df['close'].iloc[-1]) + delta
    return pd.Series({'time': time, 'open': close, 'high': close + 1,
                      'low': close - 1, 'close': close, 'volume': 10})


# --------------------------------------------------------------------------
# auto refresh
# --------------------------------------------------------------------------

def test_set_refreshes_indicators(chart):
    chart.set(_frame(50))
    sma = chart.add_sma('close', 5)
    chart.captured.clear()
    chart.set(_frame(60))                      # brand new data
    payload = _payload(chart.captured, sma.id, 'setData')
    assert isinstance(payload, list) and len(payload) == 60
    assert payload[-1]['value'] == pytest.approx(
        float(indicators.sma(chart.candle_data['close'], 5).iloc[-1]))


def test_update_pushes_only_last_point(chart):
    df = _frame(3000)                          # > tail_window -> incremental
    chart.set(df)
    sma = chart.add_sma('close', 20)
    chart.captured.clear()
    chart.update(_next_bar(df))

    payload = _payload(chart.captured, sma.id, 'update')
    assert set(payload) == {'time', 'value'}
    assert payload['time'] == int(chart.candle_data['time'].iloc[-1])
    assert payload['value'] == pytest.approx(
        float(indicators.sma(chart.candle_data['close'], 20).iloc[-1]), rel=1e-12)


def test_recursive_indicator_incremental_matches_full(chart):
    df = _frame(3000)
    chart.set(df)
    rsi = chart.add_rsi(14, overbought=None, oversold=None)
    chart.captured.clear()
    chart.update(_next_bar(df))

    payload = _payload(chart.captured, rsi.id, 'update')
    expected = float(indicators.rsi(chart.candle_data['close'], 14).iloc[-1])
    assert payload['value'] == pytest.approx(expected, rel=1e-9, abs=1e-9)


def test_macd_histogram_incremental_carries_colour(chart):
    df = _frame(3000)
    chart.set(df)
    _, _, histogram = chart.add_macd()
    chart.captured.clear()
    chart.update(_next_bar(df, delta=5.0))

    payload = _payload(chart.captured, histogram.id, 'update')
    assert set(payload) == {'time', 'value', 'color'}
    assert payload['color'].startswith('rgba(')


def test_small_chart_refreshes_fully_on_update(chart):
    df = _frame(50)                            # <= tail_window -> full re-send
    chart.set(df)
    sma = chart.add_sma('close', 5)
    chart.captured.clear()
    chart.update(_next_bar(df))
    payload = _payload(chart.captured, sma.id, 'setData')
    assert len(payload) == 51


def test_vwap_always_recomputes_fully(chart):
    df = _frame(3000)
    chart.set(df)
    vwap = chart.add_vwap()
    chart.captured.clear()
    chart.update(_next_bar(df))
    # 3000+ rows go through the binary path, so assert on the encoding used
    scripts = [s for s in chart.captured if f'{vwap.id}.series.setData(' in s]
    assert scripts, 'VWAP must be re-sent in full'
    assert 'Lib.decodeData' in scripts[-1]
    assert not any(f'{vwap.id}.series.update(' in s for s in chart.captured)


# --------------------------------------------------------------------------
# batching
# --------------------------------------------------------------------------

def test_batch_groups_bridge_calls(chart):
    chart.set(_frame(50))
    chart.captured.clear()
    with chart.batch():
        chart.set_visible_logical_range(0, 10)
        chart.scroll_to_real_time()
        chart.reset_time_scale()
    assert len(chart.captured) == 1
    assert chart.captured[0].count('Lib.invoke') == 3


def test_batch_flushes_after_an_exception(chart):
    chart.set(_frame(50))
    chart.captured.clear()
    with pytest.raises(RuntimeError):
        with chart.batch():
            chart.scroll_to_real_time()
            raise RuntimeError('boom')
    assert len(chart.captured) == 1
    assert 'scrollToRealTime' in chart.captured[0]


def test_batch_works_on_browser_chart():
    """`chart.batch()` 在浏览器/静态后端也要能用。

    `StaticLWC` / `BrowserChart` 只传 `run_script`（没有 `script_func`），以前
    `BulkRunScript.__exit__` 会对 `None` 求值 -> `TypeError`，批量下发直接崩 ✗。
    """
    from pylightcharts import BrowserChart

    chart = BrowserChart(width=800, height=600)
    chart.win.loaded = True
    chart.set(_frame(50))
    before = len(chart._html)
    with chart.batch():
        chart.scroll_to_real_time()
        chart.reset_time_scale()
    appended = chart._html[before:]
    assert 'scrollToRealTime' in appended
    assert 'resetTimeScale' in appended
