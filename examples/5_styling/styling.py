import os
import pandas as pd
from pylightcharts import Chart


# The data files sit next to each example, so it runs from any directory.
HERE = os.path.dirname(os.path.abspath(__file__))


if __name__ == '__main__':

    chart = Chart()

    df = pd.read_csv(os.path.join(HERE, 'ohlcv.csv'))

    chart.layout(background_color='#090008', text_color='#FFFFFF', font_size=16, font_family='Helvetica')

    chart.candle_style(up_color='#00ff55', down_color='#ed4807', border_up_color='#FFFFFF', border_down_color='#FFFFFF',
                       wick_up_color='#FFFFFF', wick_down_color='#FFFFFF')

    chart.volume_config(up_color='#00ff55', down_color='#ed4807')

    chart.watermark('1D', color='rgba(180, 180, 240, 0.7)')

    chart.crosshair(mode='normal', vert_color='#FFFFFF', vert_style='dotted', horz_color='#FFFFFF', horz_style='dotted')

    chart.legend(visible=True, font_size=14)

    chart.set(df)

    chart.show(block=True)
