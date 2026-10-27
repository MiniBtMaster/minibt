"""Server-side rendering example: no window, just a PNG - plus a static HTML page.

    python examples/8_headless/render.py

Uses Playwright if installed, otherwise a local Chrome/Edge in headless mode.
The same chart can also be written to a self-contained ``.html`` file (engine,
bridge and styles inlined): open it in any browser, host it, mail it - no
server, no Node, no extra dependency.
"""
import numpy as np
import pandas as pd

from pylightcharts.headless import HeadlessChart


def make_data(rows=400):
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': pd.date_range('2023-01-01', periods=rows, freq='D'),
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': rng.integers(1_000, 50_000, rows),
    })


def main():
    df = make_data()

    chart = HeadlessChart(width=1200, height=800)
    chart.set(df)
    chart.add_sma('close', 20, color='#FF9800')
    chart.add_bollinger('close', 20, 2)
    chart.add_rsi(14)
    chart.add_macd()

    # a Fibonacci retracement over the last leg
    start, end = df['time'].iloc[100], df['time'].iloc[-1]
    chart.fibonacci(start, float(df['close'].iloc[100]), end, float(df['close'].iloc[-1]))

    png = chart.render('chart.png')
    print(f'wrote chart.png ({len(png)} bytes)')

    # browser view without any server/npm: one self-contained HTML file
    html_path = chart.save_html('chart.html')
    print(f'wrote {html_path} ({len(chart.to_html())} bytes, '
          'double-click it in a browser)')
    # ... or open it right away (stdlib webbrowser, no extra dependency)
    # chart.open_in_browser('chart.html')


if __name__ == '__main__':
    main()
