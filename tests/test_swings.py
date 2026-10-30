"""Swing points (`indicators.swing_points`) and `mark_swings`.

Lightweight Charts has no swing detection of its own - it can only *draw* the
markers - so the helper lives here and the markers are pushed through the
regular marker API.
"""
import numpy as np
import pandas as pd
import pytest

from pylightcharts.abstract import AbstractChart, Window
from pylightcharts.indicators import swing_points, zigzag


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    rows = 60
    t = np.arange(rows)
    close = 100 + 10 * np.sin(t / 5)
    chart.set(pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows),
        'open': close, 'high': close + 1, 'low': close - 1,
        'close': close, 'volume': 10,
    }))
    captured.clear()
    return chart


# --------------------------------------------------------------------------
# the maths
# --------------------------------------------------------------------------

def test_swing_points_alternate_highs_and_lows():
    # `low` mirrors `high`, so bar 4 is both the highest high and the lowest low
    high = pd.Series([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 5, 4, 3], dtype=float)
    low = -high

    swings = swing_points(high, low, length=3)

    assert swings['kind'].tolist() == ['high', 'low']
    assert swings['price'].tolist() == [5.0, -5.0]
    assert swings['time'].tolist() == [4, 4]


def test_swing_points_keeps_the_time_column():
    frame = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=15),
        'high': [1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 5, 4, 3],
        'low': [-1, -2, -3, -4, -5, -4, -3, -2, -1, -2, -3, -4, -5, -4, -3],
    })
    swings = swing_points(frame['high'], frame['low'], length=3,
                          time=frame['time'])

    assert swings['time'].tolist() == [frame['time'].iloc[4]] * 2


def test_swing_points_ignore_flat_windows():
    """A plateau is not a swing - otherwise every bar of it would be marked."""
    flat = pd.Series([1.0] * 9)
    assert swing_points(flat, flat, length=2).empty


def test_swing_points_validate_their_input():
    with pytest.raises(ValueError, match='at least 1'):
        swing_points(pd.Series([1.0]), pd.Series([1.0]), length=0)
    with pytest.raises(ValueError, match='same length'):
        swing_points(pd.Series([1.0, 2.0]), pd.Series([1.0]))


# --------------------------------------------------------------------------
# the chart helper
# --------------------------------------------------------------------------

def test_mark_swings_pushes_priced_markers(chart):
    swings = chart.mark_swings(length=4)

    assert len(swings) >= 4
    assert set(swings['kind']) == {'high', 'low'}
    script = '\n'.join(chart.captured)
    high = swings[swings['kind'] == 'high'].iloc[0]
    low = swings[swings['kind'] == 'low'].iloc[0]
    # the price is the marker text, the shape points at the pivot
    assert f'"{high.price:.2f}"' in script
    assert f'"{low.price:.2f}"' in script
    assert '"arrowDown"' in script and '"arrowUp"' in script
    assert '"aboveBar"' in script and '"belowBar"' in script
    # ... and the label can be turned off
    chart.captured.clear()
    chart.mark_swings(length=4, label=False)
    unlabeled = '\n'.join(chart.captured).replace(' ', '')
    assert 'arrowDown' in unlabeled
    assert '"text":""' in unlabeled


def test_mark_swings_works_on_a_series(chart):
    line = chart.create_line(name='close')
    line.set(chart.candle_data[['time', 'close']])
    chart.captured.clear()

    swings = line.mark_swings(length=4)

    assert len(swings) >= 4
    assert len(line.markers) == len(swings)
    assert '.setMarkers(' in '\n'.join(chart.captured)


def test_mark_swings_needs_data(chart):
    empty = AbstractChart(chart.win)
    with pytest.raises(ValueError, match='before marking swings'):
        empty.mark_swings()

    empty_line = chart.create_line(name='close')
    with pytest.raises(ValueError, match='before marking swings'):
        empty_line.mark_swings()


def test_mark_swings_clear_drops_the_previous_markers(chart):
    chart.marker(position='above', shape='circle', color='#fff')
    assert len(chart.markers) == 1

    chart.mark_swings(length=4, clear=True)

    kinds = [m['shape'] for m in chart.markers.values()]
    assert 'circle' not in kinds


def test_mark_swings_colours_can_be_changed(chart):
    chart.captured.clear()
    chart.mark_swings(length=4, high_color='#111111', low_color='#222222',
                      decimals=0, size=4)
    script = '\n'.join(chart.captured).replace(' ', '')

    assert '"#111111"' in script and '"#222222"' in script
    assert '"size":4' in script
    label = script.split('"text":"')[1].split('"')[0]
    assert label and '.' not in label          # `decimals=0`


# --------------------------------------------------------------------------
# ZigZag (percentage-based alternation)
# --------------------------------------------------------------------------

def _leg_prices():
    """100 -> 119 (up 19%), -> 103 (down 13%), -> 107.5 (up)."""
    return ([100 + i for i in range(20)] + [119 - i for i in range(16)]
            + [103 + i * 0.5 for i in range(10)])


def test_zigzag_alternates_after_the_threshold():
    prices = pd.Series(_leg_prices(), dtype=float)
    swings = zigzag(prices, prices - 1, threshold=0.05,
                    include_unconfirmed=True)

    assert swings['kind'].tolist() == ['low', 'high', 'low', 'high']
    assert swings['price'].tolist() == [99.0, 119.0, 102.0, 107.5]
    assert swings['time'].tolist() == [0, 20, 36, 45]
    # everything but the running leg is confirmed
    assert swings['confirmed'].tolist() == [True, True, True, False]

    # ... and the default returns only the confirmed pivots
    confirmed = zigzag(prices, prices - 1, threshold=0.05)
    assert confirmed['kind'].tolist() == ['low', 'high', 'low']
    assert confirmed['confirmed'].all()


def test_zigzag_ignores_small_wiggles():
    """A 1% sawtooth is nothing when 3% is required."""
    base = pd.Series([100 + (i % 2) * 0.5 for i in range(40)], dtype=float)
    assert zigzag(base, base - 0.2, threshold=0.03).empty
    # with a threshold below the wiggle every leg shows up
    assert len(zigzag(base, base - 0.2, threshold=0.002,
                      include_unconfirmed=True)) > 2


def test_zigzag_monotone_series_is_a_single_open_leg():
    """No reversal means no confirmed pivot beyond the starting extreme.

    That is how the usual ZigZag draws a trend: one leg from the first extreme
    to the running high, and that high is flagged as unconfirmed (it moves until
    a reversal of `threshold` closes the leg).
    """
    rising = pd.Series([100 + i for i in range(30)], dtype=float)

    confirmed = zigzag(rising, rising - 0.5, threshold=0.03)
    assert len(confirmed) == 1                    # the starting low
    assert confirmed.iloc[0]['kind'] == 'low'
    assert confirmed.iloc[0]['price'] == 99.5

    tentative = zigzag(rising, rising - 0.5, threshold=0.03,
                       include_unconfirmed=True)
    assert tentative['kind'].tolist() == ['low', 'high']
    assert tentative['confirmed'].tolist() == [True, False]


def test_zigzag_validates_its_arguments():
    prices = pd.Series([100.0, 101.0, 99.0])
    with pytest.raises(ValueError, match='positive'):
        zigzag(prices, prices, threshold=0)
    with pytest.raises(ValueError, match='same length'):
        zigzag(prices, prices.iloc[:2])


def test_add_zigzag_draws_a_line_and_keeps_it_updated(chart):
    line = chart.add_zigzag(threshold=0.05)

    assert line.name == 'ZigZag 5%'
    script = '\n'.join(chart.captured)
    assert '.series.setData(' in script          # the sparse pivot data
    assert '"arrowDown"' in script and '"arrowUp"' in script   # pivot markers
    points = len(line.data)
    assert points >= 3

    # a new bar triggers a recompute (the binding is registered like an indicator)
    chart.captured.clear()
    last = chart.candle_data.iloc[-1]
    chart.update(pd.Series({
        'time': int(last['time']) + 60,
        'open': float(last['close']),
        'high': float(last['close']) + 50,        # a big move up
        'low': float(last['close']) - 1,
        'close': float(last['close']) + 40,
    }))
    script = '\n'.join(chart.captured)
    assert f'{line.id}.series.setData(' in script
    assert len(line.data) >= points


def test_add_zigzag_can_skip_the_markers(chart):
    chart.captured.clear()
    chart.add_zigzag(threshold=0.05, markers=False, label=True)
    script = '\n'.join(chart.captured)
    assert '.series.setData(' in script
    assert '"arrowDown"' not in script             # no pivot arrows


# --------------------------------------------------------------------------
# inverted price scale (价格倒挂)
# --------------------------------------------------------------------------

def _marker_sides(chart):
    """(above, below, down, up) marker counts in the last scripts."""
    js = '\n'.join(chart.captured)
    return (js.count('"aboveBar"'), js.count('"belowBar"'),
            js.count('"arrowDown"'), js.count('"arrowUp"'))


def test_an_inverted_scale_flips_the_marker_side_and_the_arrow(chart):
    chart.mark_swings(length=4)
    straight = _marker_sides(chart)

    chart.clear_markers()
    chart.captured.clear()
    chart.price_scale(invert_scale=True)
    chart.mark_swings(length=4)
    flipped = _marker_sides(chart)

    # the values stay at the same prices, only the side/direction change
    assert straight[0] == flipped[1] and straight[1] == flipped[0]
    assert straight[2] == flipped[3] and straight[3] == flipped[2]


def test_the_inversion_is_remembered_from_every_entry_point(chart):
    for call in (lambda: chart.price_scale(invert_scale=True),
                 lambda: chart.apply_options(
                     rightPriceScale={'invertScale': True}),
                 lambda: chart.get_price_scale('right').invert()):
        chart._price_scale_inverted = False
        call()
        assert chart._price_scale_inverted is True


def test_an_explicit_inverted_flag_wins_over_the_chart(chart):
    # the chart state says "inverted", the call says otherwise
    chart.price_scale(invert_scale=True)
    chart.captured.clear()
    chart.mark_swings(length=4, inverted=False, clear=True)
    above, below = _marker_sides(chart)[:2]

    assert above > below                     # highs above: not flipped
    # ... and the explicit value becomes what the chart remembers
    assert chart._price_scale_inverted is False


def test_a_zigzag_added_before_the_inversion_is_re_marked(chart):
    chart.add_zigzag(0.05, name='zigzag')
    chart.captured.clear()

    chart.apply_options(rightPriceScale={'invertScale': True})

    js = '\n'.join(chart.captured)
    # the pivot markers have to be re-sent: they are screen-relative
    assert 'setData' in js
    assert '"arrowUp"' in js or '"arrowDown"' in js
    assert chart._price_scale_inverted is True
