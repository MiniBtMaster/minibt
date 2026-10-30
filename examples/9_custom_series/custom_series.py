"""Declarative custom series.

Python describes *what* to draw as shape descriptors (see `pylightcharts.shapes`);
a single generic JS renderer draws them every frame, so there is no per-frame
round-trip to python.

    python examples/9_custom_series/custom_series.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart, shapes


def make_data(rows=200):
    rng = np.random.default_rng(9)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    df = pd.DataFrame({
        'time': pd.date_range('2023-01-01', periods=rows, freq='D'),
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': rng.integers(1_000, 50_000, rows),
    })
    # rolling quantiles for a box plot
    df['q1'] = df['close'].rolling(20, min_periods=1).quantile(0.25)
    df['median'] = df['close'].rolling(20, min_periods=1).median()
    df['q3'] = df['close'].rolling(20, min_periods=1).quantile(0.75)
    return df


def main():
    chart = Chart(width=1000, height=750, title='pylightcharts - custom series')
    df = make_data()
    chart.set(df)

    # range bars overlaid on the price pane
    ranges = chart.add_custom_series('range bars')
    ranges.set(df, shapes=lambda row: shapes.range_bar(row['low'], row['high'],
                                                       color='rgba(41, 98, 255, 0.45)'))

    # a box plot in its own pane
    box = chart.add_custom_series('box plot', pane_index='new')
    box.set(df, shapes=lambda row: shapes.box_plot(
        row['low'], row['q1'], row['median'], row['q3'], row['high']))

    chart.show(block=True)


if __name__ == '__main__':
    main()
