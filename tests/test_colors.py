"""Tests for `pylightcharts.colors.color_by` (per-point colours)."""
import numpy as np
import pandas as pd
import pytest

from pylightcharts import Window, color_by
from pylightcharts.abstract import AbstractChart


@pytest.fixture()
def frame():
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=5, freq='D'),
        'open': [1.0, 2.0, 3.0, 4.0, 5.0],
        'high': [2.0, 3.0, 4.0, 5.0, 6.0],
        'low': [0.0, 1.0, 2.0, 3.0, 4.0],
        'close': [1.5, 2.5, 3.5, 4.5, 5.5],
    })


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    return chart


# --------------------------------------------------------------------------
# the helper
# --------------------------------------------------------------------------

def test_color_by_fills_body_wick_and_border(frame):
    out = color_by(frame, frame['close'] > 3, 'orange')

    # the condition is what the javascript example does with .map()
    assert out['color'].tolist() == [None, None, 'orange', 'orange', 'orange']
    # a candle needs all three keys to be repainted completely
    assert out['wickColor'].tolist() == out['color'].tolist()
    assert out['borderColor'].tolist() == out['color'].tolist()
    # the input frame is left alone
    assert 'color' not in frame.columns
    assert list(out.columns) == list(frame.columns) + [
        'color', 'wickColor', 'borderColor']


def test_color_by_else_color_paints_both_branches(frame):
    out = color_by(frame, frame['close'] > 3, '#26a69a',
                   else_color='#ef5350')

    assert out['color'].tolist() == ['#ef5350', '#ef5350',
                                     '#26a69a', '#26a69a', '#26a69a']
    assert out['wickColor'].tolist() == out['color'].tolist()


def test_color_by_wick_and_border_can_be_skipped_or_overridden(frame):
    body_only = color_by(frame, frame['close'] > 3, 'orange',
                         wick_color=False)
    assert 'wickColor' not in body_only.columns
    assert 'borderColor' in body_only.columns          # still follows `color`

    custom = color_by(frame, frame['close'] > 3, 'orange',
                      wick_color='red', border_color=False)
    assert custom['wickColor'].tolist() == [None, None, 'red', 'red', 'red']
    assert 'borderColor' not in custom.columns


def test_color_by_accepts_per_row_colors_and_callables(frame):
    per_row = color_by(frame, frame['close'] > 3, ['a', 'b', 'c', 'd', 'e'])
    assert per_row['color'].tolist() == [None, None, 'c', 'd', 'e']

    by_callable = color_by(frame, lambda df: df['close'] > 3, 'orange')
    assert by_callable['color'].tolist() == (
        [None, None, 'orange', 'orange', 'orange'])

    by_array = color_by(frame, np.array([0, 0, 1, 1, 1]), 'orange')
    assert by_array['color'].tolist() == by_callable['color'].tolist()


def test_color_by_validates_its_arguments(frame):
    with pytest.raises(ValueError, match='condition has 2 rows'):
        color_by(frame, [True, False], 'orange')
    with pytest.raises(ValueError, match='color has 2 entries'):
        color_by(frame, frame['close'] > 3, ['a', 'b'])
    with pytest.raises(ValueError, match='else_color has 2 entries'):
        color_by(frame, frame['close'] > 3, 'orange', else_color=['a', 'b'])
    with pytest.raises(ValueError, match='must be a colour'):
        color_by(frame, frame['close'] > 3, 'orange', wick_color=1)


# --------------------------------------------------------------------------
# through the bridge
# --------------------------------------------------------------------------

def test_color_by_reaches_the_engine(chart, frame):
    """The coloured frame has to survive the JSON/binary encoders."""
    chart.captured.clear()
    chart.set(color_by(frame, frame['close'] > 3, 'orange'))
    script = '\n'.join(chart.captured)

    assert '"color":"orange"' in script
    assert '"wickColor":"orange"' in script
    assert '"borderColor":"orange"' in script
    # rows outside the condition carry no colour key at all
    assert script.count('"color":"orange"') == 3

    line = chart.create_line(name='close')
    chart.captured.clear()
    line.set(color_by(frame, frame['close'] > 3, '#26a69a',
                      else_color='#ef5350')[['time', 'close', 'color']])
    script = '\n'.join(chart.captured)
    assert '"color":"#26a69a"' in script
    assert '"color":"#ef5350"' in script


# --------------------------------------------------------------------------
# series / chart shortcut
# --------------------------------------------------------------------------

def test_series_color_by_resends_the_frame(chart, frame):
    """`series.color_by` colours data the series already holds - indicators."""
    line = chart.create_line(name='close')
    line.set(frame[['time', 'close']])
    line.data['value'] = [1.0, 2.0, 3.0, 4.0, 5.0]     # like an indicator
    chart.captured.clear()

    rising = line.data['value'].diff().fillna(0.0) > 0
    out = line.color_by(rising, '#26a69a', else_color='#ef5350')

    script = '\n'.join(chart.captured)
    assert '.series.setData(' in script          # the binary-capable path
    assert '"color":"#26a69a"' in script and '"color":"#ef5350"' in script
    assert list(out.columns) == ['time', 'value', 'color', 'wickColor',
                                 'borderColor']
    # the series keeps the coloured frame (so a second call sees the colours)
    assert 'color' in line.data.columns
    assert out['color'].tolist() == ['#ef5350', '#26a69a', '#26a69a',
                                     '#26a69a', '#26a69a']


def test_chart_color_by_colours_the_candles(chart, frame):
    chart.set(frame)
    chart.captured.clear()

    out = chart.color_by(frame['close'] > 3, 'orange')

    script = '\n'.join(chart.captured)
    assert '.series.setData(' in script
    assert '"wickColor":"orange"' in script
    assert 'color' in chart.candle_data.columns
    assert len(out) == len(frame)
    assert out['color'].tolist() == [None, None, 'orange', 'orange', 'orange']


def test_series_color_by_needs_data(chart):
    line = chart.create_line(name='close')
    with pytest.raises(ValueError, match='Set the data before colouring'):
        line.color_by([True], 'orange')


def test_series_color_by_aligns_a_shorter_condition_by_time(chart, frame):
    """A condition computed on fewer rows (dropped NaNs) lines up by time."""
    line = chart.create_line(name='close')
    line.set(frame[['time', 'close']])
    line.data['value'] = [1.0, 2.0, 3.0, 4.0, 5.0]
    chart.captured.clear()

    condition = pd.Series([False, True, True],
                          index=line.data['time'].to_numpy()[2:])
    out = line.color_by(condition, 'orange')

    # rows the condition does not cover keep the series style
    assert out['color'].tolist() == [None, None, None, 'orange', 'orange']
