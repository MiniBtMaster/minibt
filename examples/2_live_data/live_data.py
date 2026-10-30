import os
import pandas as pd
from time import sleep
from pylightcharts import Chart


# The data files sit next to each example, so it runs from any directory.
HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':

    chart = Chart()

    df1 = pd.read_csv(os.path.join(HERE, 'ohlcv.csv'))
    df2 = pd.read_csv(os.path.join(HERE, 'next_ohlcv.csv'))

    chart.set(df1)

    chart.show()

    last_close = df1.iloc[-1]['close']

    try:
        for i, series in df2.iterrows():
            if not chart.is_alive:          # the window was closed
                break
            chart.update(series)

            if series['close'] > 20 and last_close < 20:
                chart.marker(text='The price crossed $20!')

            last_close = series['close']
            sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        chart.exit()                        # shut the webview process down
