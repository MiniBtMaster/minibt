import os
import pandas as pd
from pylightcharts import Chart


# The data files sit next to each example, so it runs from any directory.
HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    chart = Chart()

    # Columns: time | open | high | low | close | volume
    df = pd.read_csv(os.path.join(HERE, 'ohlcv.csv'))
    chart.set(df)

    chart.show(block=True)
