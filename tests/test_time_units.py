"""The `time` column of every chart is in **epoch seconds**.

Feeding that column back into `set()` (or handing in milliseconds by mistake)
used to be read as nanoseconds, which put the data in 1970 - the indicator lines
of `examples/11_api_tour/19_indicator_panes.py` ended up far left of the candles.
`infer_time_unit` infers the unit from the magnitude instead.
"""
import pandas as pd
import pytest

from pylightcharts import Window
from pylightcharts.abstract import AbstractChart
from pylightcharts.util import infer_time_unit

START = pd.Timestamp('2024-01-01 00:00:00')
SECONDS = int(START.timestamp())


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    return chart


def frame(times, **extra):
    base = {'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5}
    base.update(extra)
    return pd.DataFrame({'time': list(times), **base})


@pytest.mark.parametrize('multiplier', [1, 10 ** 3, 10 ** 6, 10 ** 9])
def test_every_epoch_unit_lands_on_the_same_date(chart, multiplier):
    """seconds / ms / us / ns all describe the same instant."""
    step = 86400 * multiplier
    chart.set(frame([SECONDS * multiplier, SECONDS * multiplier + step]))
    assert chart.candle_data['time'].tolist() == [SECONDS, SECONDS + 86400]


def test_the_charts_own_time_column_can_be_fed_back(chart):
    """`chart.candle_data` is the natural input for an indicator frame."""
    chart.set(frame(pd.date_range('2024-01-01', periods=4)))
    first = chart.candle_data.copy()

    chart.set(first)                       # the round trip that used to break

    assert chart.candle_data['time'].tolist() == first['time'].tolist()
    assert pd.to_datetime(chart.candle_data['time'].iloc[0], unit='s') == START


def test_an_indicator_frame_can_reuse_the_candle_times(chart):
    """What a pane indicator does: same time column, computed values."""
    chart.set(frame(pd.date_range('2024-01-01', periods=6)))
    times = chart.candle_data['time']
    indicator = pd.DataFrame({'time': times, 'RSI 14': range(len(times))})

    pane = chart.add_pane()
    series = chart.pane_add_series(pane, 'Line', name='RSI 14')
    series.set(indicator)

    assert series.data['time'].min() == chart.candle_data['time'].min()
    assert series.data['time'].max() == chart.candle_data['time'].max()
    assert series.pane_index == 1


def test_datetimes_and_strings_still_work(chart):
    chart.set(frame(['2024-01-01', '2024-01-02']))
    assert chart.candle_data['time'].tolist() == [SECONDS, SECONDS + 86400]


def test_a_datetime_index_is_used(chart):
    data = pd.DataFrame({'open': [1.0, 1.0], 'high': [2.0, 2.0],
                         'low': [0.5, 0.5], 'close': [1.5, 1.5]},
                        index=pd.date_range('2024-01-01', periods=2))
    chart.set(data)
    assert chart.candle_data['time'].tolist() == [SECONDS, SECONDS + 86400]


def test_the_helper_reads_the_magnitude():
    assert infer_time_unit([SECONDS]) == 's'
    assert infer_time_unit([SECONDS * 10 ** 3]) == 'ms'
    assert infer_time_unit([SECONDS * 10 ** 6]) == 'us'
    assert infer_time_unit([SECONDS * 10 ** 9]) == 'ns'
    assert infer_time_unit([]) == 's'
