"""A second symbol on its own price scale (`chart.add_symbol`).

Mirrors the official *Two Price Scales* tutorial - both scales visible, the
main candles on the right and the overlay on the left - plus candle overlays.
"""
import pandas as pd
import pytest

from pylightcharts import Window
from pylightcharts.abstract import AbstractChart
from pylightcharts.overlay import KINDS, add_symbol, frame_for


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    chart.set(pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=6, freq='D'),
        'open': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        'high': [2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
        'low': [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
        'close': [1.5, 2.5, 3.5, 4.5, 5.5, 6.5],
        'volume': [10, 11, 12, 13, 14, 15],
    }))
    chart.captured.clear()
    return chart


def script(chart) -> str:
    """Everything the overlay emitted, as one string."""
    return chr(10).join(chart.captured)  # the emitted scripts, joined


def creation(chart) -> str:
    """The `addSeries` call `add_symbol` made."""
    return next(line for line in chart.captured if 'addSeries' in line)


@pytest.fixture()
def eth():
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=6, freq='D'),
        'open': [2000.0, 2010.0, 2020.0, 2030.0, 2040.0, 2050.0],
        'high': [2100.0, 2110.0, 2120.0, 2130.0, 2140.0, 2150.0],
        'low': [1950.0, 1960.0, 1970.0, 1980.0, 1990.0, 2000.0],
        'close': [2050.0, 2060.0, 2070.0, 2080.0, 2090.0, 2100.0],
    })


# --------------------------------------------------------------------------
# creating the overlay
# --------------------------------------------------------------------------

def test_add_symbol_shows_the_left_scale_and_uses_it(chart, eth):
    eth_series = chart.add_symbol('ETHUSDT', eth)
    script = '\n'.join(chart.captured)

    # both scales visible, second series on the left one (the tutorial)
    assert '"visible":true' in script
    assert '"priceScaleId":"left"' in script
    assert '"Candlestick"' in script and '"ETHUSDT"' in script
    assert eth_series.kind == 'Candlestick'
    # the price line label carries the symbol, so the two axes are readable
    assert '"title":"ETHUSDT"' in script
    assert '"lastValueVisible":true' in script
    assert '"priceLineVisible":true' in script


def test_the_main_series_keeps_the_right_scale(chart):
    """It must not be moved to the left scale - only the overlay is."""
    assert '"priceScaleId"' not in '\n'.join(chart.captured)


def test_candle_overlay_colours_borders_and_wicks(chart, eth):
    chart.add_symbol('ETHUSDT', eth, up_color='#26A69A', down_color='#EF5350')
    script = creation(chart)
    for option in ('"upColor":"#26A69A"', '"borderUpColor":"#26A69A"',
                   '"wickUpColor":"#26A69A"', '"downColor":"#EF5350"',
                   '"borderDownColor":"#EF5350"', '"wickDownColor":"#EF5350"'):
        assert option in script


def test_an_explicit_colour_is_not_overwritten(chart, eth):
    chart.add_symbol('ETHUSDT', eth, up_color='#26A69A',
                     border_up_color='#111111')
    assert '"borderUpColor":"#111111"' in creation(chart)
    assert '"wickUpColor":"#26A69A"' in creation(chart)


def test_line_overlay_takes_colour_and_width(chart):
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                      index=pd.date_range('2024-01-01', periods=6))
    chart.add_symbol('BTC/GLD', close, kind='line', color='#FFB300',
                     line_width=3)
    script = creation(chart)
    assert '"Line"' in script and '"color":"#FFB300"' in script
    assert '"lineWidth":3' in script


def test_data_can_be_added_later(chart, eth):
    series = chart.add_symbol('ETHUSDT', kind='candles')
    assert 'setData' not in script(chart)
    chart.captured.clear()
    series.set(eth)
    assert '"open":2000.0' in chart.captured[-1]


def test_the_anchor_scale_is_made_visible_before_use(chart, eth):
    chart.captured.clear()
    chart.add_symbol('ETHUSDT', eth)
    calls = [line for line in chart.captured if 'applyOptions' in line]
    assert 'priceScale.left' in chart.captured[0]
    assert '"visible":true' in calls[0]


# --------------------------------------------------------------------------
# data shaping
# --------------------------------------------------------------------------

def test_a_bar_overlay_keeps_its_columns_and_its_name(chart, eth):
    """`set()` matches single-value series by column, bars by legend label."""
    series = chart.add_symbol('ETHUSDT', eth)
    assert series.name == 'ETHUSDT'
    assert '"open":2000.0' in script(chart)
    assert '"value"' not in script(chart)


def test_a_single_value_overlay_renames_its_column(chart, eth):
    frame = frame_for(eth[['time', 'close']], 'ETHUSDT', 'Line')
    assert list(frame.columns) == ['time', 'ETHUSDT']

    chart.add_symbol('ETHUSDT', eth[['time', 'close']], kind='line')
    assert '"value":2050.0' in script(chart)


def test_value_column_can_be_chosen(chart, eth):
    data = eth[['time', 'close', 'open']]
    frame = frame_for(data, 'ETHUSDT', 'Line', value_column='open')
    assert list(frame.columns) == ['time', 'close', 'ETHUSDT']


def test_a_series_gets_the_symbol_name(chart):
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                      index=pd.date_range('2024-01-01', periods=6))
    frame = frame_for(close, 'ETHUSDT', 'Line')
    assert list(frame.columns) == ['ETHUSDT']


def test_an_ambiguous_single_value_frame_is_rejected():
    frame = pd.DataFrame({'time': pd.date_range('2024-01-01', periods=3),
                          'alpha': [1.0, 2.0, 3.0],
                          'beta': [4.0, 5.0, 6.0]})
    with pytest.raises(ValueError, match='value_column'):
        frame_for(frame, 'ETHUSDT', 'Line')


def test_a_bar_overlay_needs_ohlc(chart):
    frame = pd.DataFrame({'time': pd.date_range('2024-01-01', periods=3),
                          'close': [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match='missing'):
        frame_for(frame, 'ETHUSDT', 'Candlestick')


def test_a_single_value_series_still_needs_its_column(chart):
    """The bar/OHLC exception must not hide a genuine typo."""
    with pytest.raises(NameError, match='No column named'):
        chart.create_line('does_not_exist').set(pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=3),
            'close': [1.0, 2.0, 3.0],
        }))


# --------------------------------------------------------------------------
# margins / validation
# --------------------------------------------------------------------------

def test_margins_stack_the_overlay(chart, eth):
    chart.add_symbol('ETHUSDT', eth, margins=(0.55, 0.0))
    assert '"scaleMargins":{"top":0.55,"bottom":0.0}' in script(chart)


def test_scale_margins_handles_both_sides(chart):
    chart.scale_margins(right=(0.0, 0.55), left=(0.55, 0.0))
    script = '\n'.join(chart.captured)
    assert 'priceScale.right' in script and 'priceScale.left' in script
    assert '"scaleMargins":{"top":0.0,"bottom":0.55}' in script
    assert '"scaleMargins":{"top":0.55,"bottom":0.0}' in script


def test_scale_margins_ignores_missing_sides(chart):
    chart.scale_margins(left=(0.5, 0.0))
    assert 'priceScale.right' not in '\n'.join(chart.captured)


def test_a_custom_scale_id_is_an_invisible_overlay(chart, eth):
    chart.add_symbol('ETHUSDT', eth, scale='volume')
    assert '"priceScaleId":"volume"' in '\n'.join(chart.captured)


def test_unknown_kind_and_bad_scale_are_rejected(chart, eth):
    with pytest.raises(ValueError, match='kind must be one of'):
        chart.add_symbol('ETHUSDT', eth, kind='candle')
    with pytest.raises(ValueError, match='scale must be'):
        chart.add_symbol('ETHUSDT', eth, scale='')


def test_the_kind_table_maps_to_series_types():
    assert KINDS['candles'] == 'Candlestick' and KINDS['bars'] == 'Bar'
    assert KINDS['line'] == 'Line' and KINDS['histogram'] == 'Histogram'


def test_legend_toggle_is_forwarded(chart, eth):
    chart.add_symbol('ETHUSDT', eth, legend_toggle=False)
    # the generic bridge appends `\nnull` so PyQt6 never converts a live handle
    # (0.1.4) - the `false` still sits right before the closing bracket
    assert creation(chart).rstrip().endswith('false])\nnull')


def test_add_symbol_is_reachable_from_the_chart_method(chart, eth):
    series = chart.add_symbol('ETHUSDT', eth, kind='line',
                              price_scale_id='left')
    assert series.kind == 'Line'
    assert '"priceScaleId":"left"' in creation(chart)
