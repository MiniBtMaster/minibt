import os
import pandas as pd
from pylightcharts import Chart


# The data files sit next to each example, so it runs from any directory.
HERE = os.path.dirname(os.path.abspath(__file__))


def calculate_sma(df, period: int = 50):
    return pd.DataFrame({
        'time': df['date'],
        f'SMA {period}': df['close'].rolling(window=period).mean()
    }).dropna()


if __name__ == '__main__':
    chart = Chart()
    chart.legend(visible=True)

    df = pd.read_csv(os.path.join(HERE, 'ohlcv.csv'))
    chart.set(df)

    line = chart.create_line('SMA 50')
    sma_data = calculate_sma(df, period=50)
    line.set(sma_data)

    chart.show(block=True)
