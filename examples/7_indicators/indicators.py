"""Indicators + multi-pane example.

Indicators are computed in pure pandas (see `pylightcharts/indicators.py`).
Overlays (SMA / Bollinger) land on the price pane, oscillators (RSI / MACD)
get their own pane automatically.

    python examples/7_indicators/indicators.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart


def make_data(n=400):
    rng = np.random.default_rng(11)
    close = 100 + np.cumsum(rng.standard_normal(n) * 0.8)
    high = close + np.abs(rng.standard_normal(n))
    low = close - np.abs(rng.standard_normal(n))
    open_ = close + rng.standard_normal(n) * 0.3
    return pd.DataFrame({
        'time': pd.date_range('2022-01-01', periods=n, freq='D'),
        'open': open_, 'high': high, 'low': low, 'close': close,
        'volume': rng.integers(1_000, 50_000, n),
    })


def main():
    chart = Chart(width=1000, height=800, title='pylightcharts - indicators')

    df = make_data()
    chart.set(df)

    # overlays on the price pane
    chart.add_sma('close', 20, color='#FF9800', line_width=2)
    chart.add_sma('close', 50, color='#2196F3', line_width=2)
    chart.add_bollinger('close', 20, 2)
    chart.add_keltner(20, 2.0)

    # oscillators, each in their own pane
    chart.add_rsi(14)
    chart.add_macd()
    chart.add_adx(14)
    chart.add_obv()

    # indicators follow the data: chart.update(bar) refreshes them automatically
    chart.show(block=True)


if __name__ == '__main__':
    main()
