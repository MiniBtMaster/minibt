import os
import pandas as pd
from time import sleep
from pylightcharts import Chart


# The data files sit next to each example, so it runs from any directory.
HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':

    df1 = pd.read_csv(os.path.join(HERE, 'ohlc.csv'))

    # Columns: time | price
    df2 = pd.read_csv(os.path.join(HERE, 'ticks.csv'))

    chart = Chart()

    chart.set(df1)

    chart.show()

    try:
        for i, tick in df2.iterrows():
            if not chart.is_alive:          # the window was closed
                break
            chart.update_from_tick(tick)
            sleep(0.03)
    except KeyboardInterrupt:
        pass
    finally:
        chart.exit()                        # shut the webview process down
