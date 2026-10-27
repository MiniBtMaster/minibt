"""Indicator maths (checked against pandas / TA-Lib when available) and their
chart integration through the generic bridge."""
import numpy as np
import pandas as pd
import pytest

from pylightcharts import indicators as ind
from pylightcharts.abstract import AbstractChart, Window


@pytest.fixture()
def frame():
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.standard_normal(250))
    return pd.DataFrame({
        'time': pd.date_range('2020-01-01', periods=250, freq='D'),
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': rng.integers(1, 100, 250),
    })


@pytest.fixture()
def chart(frame):
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    chart.set(frame)
    captured.clear()
    return chart


# --------------------------------------------------------------------------
# maths
# --------------------------------------------------------------------------

def test_sma_matches_pandas(frame):
    got = ind.sma(frame['close'], 20)
    expected = frame['close'].rolling(20, min_periods=1).mean()
    pd.testing.assert_series_equal(got, expected)


def test_bollinger_ordering(frame):
    bands = ind.bollinger(frame['close'], 20, 2)
    assert (bands['upper'] >= bands['middle']).all()
    assert (bands['middle'] >= bands['lower']).all()


def test_rsi_matches_talib(frame):
    talib = pytest.importorskip('talib')
    got = ind.rsi(frame['close'], 14).to_numpy()
    expected = talib.RSI(frame['close'].to_numpy(), timeperiod=14)
    mask = ~np.isnan(expected)
    assert np.allclose(got[mask], expected[mask])


def test_atr_matches_talib(frame):
    talib = pytest.importorskip('talib')
    got = ind.atr(frame, 14).to_numpy()
    expected = talib.ATR(frame['high'].to_numpy(), frame['low'].to_numpy(), frame['close'].to_numpy(), 14)
    mask = ~np.isnan(expected)
    assert np.allclose(got[mask], expected[mask], atol=5e-3)


def test_macd_histogram_identity(frame):
    result = ind.macd(frame['close'])
    expected = result['macd'] - result['signal']
    pd.testing.assert_series_equal(result['histogram'], expected, check_names=False)


def test_stochastic_and_donchian_bounds(frame):
    stoch = ind.stochastic(frame)
    valid = stoch['k'].dropna()
    assert valid.between(0, 100).all()
    channel = ind.donchian(frame, 20)
    assert (channel['upper'] >= channel['lower']).all()


def test_vwap_is_between_low_and_high(frame):
    vwap = ind.vwap(frame).dropna()
    assert vwap.between(frame['low'].min(), frame['high'].max()).all()


# --------------------------------------------------------------------------
# chart integration
# --------------------------------------------------------------------------

def test_add_sma_adds_series(chart):
    chart.add_sma('close', 20)
    scripts = '\n'.join(chart.captured)
    assert '"addSeries"' in scripts and '"SMA 20"' in scripts
    assert '.series.setData(' in scripts


def test_add_ema_custom_name(chart):
    chart.add_ema('close', 9, name='EMA9', color='#f00', line_width=2)
    scripts = '\n'.join(chart.captured)
    assert '"EMA9"' in scripts and '"lineWidth":2' in scripts


def test_overlay_stays_in_main_pane(chart):
    chart.captured.clear()
    chart.add_sma('close', 20)
    series_scripts = [s for s in chart.captured if 'addSeries' in s]
    assert series_scripts, chart.captured
    assert not any('addPane' in s for s in chart.captured)


def test_rsi_creates_its_own_pane(chart):
    chart.captured.clear()
    rsi = chart.add_rsi(length=14)
    scripts = '\n'.join(chart.captured)
    assert '"addPane"' in scripts
    assert '"RSI 14"' in scripts
    # the series is created in pane 1
    add_series_script = [s for s in chart.captured if 'addSeries' in s][0]
    assert ',1,true]' in add_series_script.replace(' ', '')
    assert chart._pane_count == 2


def test_rsi_guide_lines(chart):
    chart.captured.clear()
    chart.add_rsi(length=14, overbought=70, oversold=30)
    scripts = '\n'.join(chart.captured)
    assert scripts.count('Lib.HorizontalLine') >= 2


def test_macd_returns_three_series(chart):
    chart.captured.clear()
    macd, signal, histogram = chart.add_macd()
    assert macd is not None and signal is not None and histogram is not None
    scripts = '\n'.join(chart.captured)
    assert '"MACD 12,26"' in scripts
    assert '"Histogram"' in scripts
    assert '"color"' in scripts          # per-bar histogram colours


def test_add_indicator_requires_data():
    window = Window(script_func=lambda s: None)
    window.loaded = True
    empty = AbstractChart(window)
    with pytest.raises(ValueError):
        empty.add_sma('close', 20)


def test_indicator_unknown_source(chart):
    with pytest.raises(NameError):
        chart.add_sma('does_not_exist', 20)


def test_pane_index_new_and_explicit(chart):
    chart.captured.clear()
    chart.add_rsi(length=7)                 # pane 1
    chart.add_macd(pane_index=2)            # pane 2
    add_series = [s for s in chart.captured if 'addSeries' in s]
    assert any(',1,true]' in s.replace(' ', '') for s in add_series)
    assert any(',2,true]' in s.replace(' ', '') for s in add_series)
    assert chart._pane_count == 3


# --------------------------------------------------------------------------
# drawing tools (Fibonacci / Measure / ParallelChannel)
# --------------------------------------------------------------------------

def test_fibonacci_primitive(chart):
    chart.captured.clear()
    chart.fibonacci('2020-01-05', 100, '2020-02-01', 120)
    script = '\n'.join(chart.captured)
    assert 'new Lib.FibonacciRetracement' in script
    assert 'levels:' in script
    assert 'showLabels: true' in script
    assert '.series.attachPrimitive(' in script


def test_fibonacci_custom_levels(chart):
    chart.captured.clear()
    chart.fibonacci('2020-01-05', 100, '2020-02-01', 120, levels=(0, 0.5, 1))
    assert 'levels: [0.0, 0.5, 1.0]' in '\n'.join(chart.captured)


def test_measure_primitive(chart):
    chart.captured.clear()
    chart.measure('2020-01-05', 100, '2020-02-01', 120)
    script = '\n'.join(chart.captured)
    assert 'new Lib.Measure' in script
    assert 'showTimeRange: true' in script


def test_parallel_channel_offset(chart):
    chart.captured.clear()
    channel = chart.parallel_channel('2020-01-05', 100, '2020-02-01', 120, offset=5)
    script = '\n'.join(chart.captured)
    assert 'new Lib.ParallelChannel' in script
    assert 'channelOffset: 5.0' in script
    chart.captured.clear()
    channel.set_offset(2.5)
    assert 'channelOffset: 2.5' in chart.captured[-1]


def test_drawing_update_and_delete(chart):
    chart.captured.clear()
    fib = chart.fibonacci('2020-01-05', 100, '2020-02-01', 120)
    chart.captured.clear()
    fib.update('2020-01-06', 101, '2020-02-02', 121)
    assert 'updatePoints(' in chart.captured[-1]
    chart.captured.clear()
    fib.delete()
    assert '.detach()' in chart.captured[-1]


# --------------------------------------------------------------------------
# binary data encoding
# --------------------------------------------------------------------------

def test_binary_encoding_layout():
    import base64
    import re
    from pylightcharts.util import js_binary_data
    df = pd.DataFrame({'time': [1, 2, 3], 'close': [1.5, float('nan'), 3.5]})
    expr = js_binary_data(df)
    match = re.match(r'Lib\.decodeData\("([^"]+)", (\[.*?\])(?:, (.*))?\)$', expr)
    assert match, expr
    floats = np.frombuffer(base64.b64decode(match.group(1)), dtype='<f8')
    # column-major: all of `time`, then all of `close`
    assert floats[:3].tolist() == [1.0, 2.0, 3.0]
    assert floats[3] == 1.5 and np.isnan(floats[4]) and floats[5] == 3.5
    assert match.group(2) == '["time", "close"]'


def test_binary_encoding_string_columns():
    from pylightcharts.util import js_binary_data
    df = pd.DataFrame({'time': [1, 2], 'close': [1.0, 2.0], 'color': ['#aaa', '#bbb']})
    expr = js_binary_data(df)
    assert '{"color": ["#aaa", "#bbb"]}' in expr
    assert '["time", "close"]' in expr


def test_encode_series_data_threshold():
    from pylightcharts.util import encode_series_data
    small = pd.DataFrame({'time': [1, 2], 'close': [1.0, 2.0]})
    large = pd.DataFrame({'time': range(3000), 'close': range(3000)})
    assert 'decodeData' not in encode_series_data(small)
    assert 'decodeData' in encode_series_data(large)


def test_chart_set_uses_binary_for_large_frames(chart):
    rows = 3000
    big = pd.DataFrame({
        'time': pd.date_range('2020-01-01', periods=rows, freq='min'),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5, 'volume': 10,
    })
    chart.captured.clear()
    chart.set(big)
    scripts = '\n'.join(chart.captured)
    assert 'Lib.decodeData' in scripts
    assert '.series.setData(' in scripts


# --------------------------------------------------------------------------
# position / risk-reward tool
# --------------------------------------------------------------------------

def test_position_primitive(chart):
    chart.captured.clear()
    chart.position('2020-01-05', 100, '2020-02-01', 120, risk_ratio=2.0)
    script = '\n'.join(chart.captured)
    assert 'new Lib.Position' in script
    assert 'riskRatio: 2.0' in script
    assert 'profitFillColor' in script and 'lossFillColor' in script
    assert '.series.attachPrimitive(' in script


def test_long_short_position_aliases(chart):
    chart.captured.clear()
    chart.long_position('2020-01-05', 100, '2020-02-01', 120)
    assert 'new Lib.Position' in '\n'.join(chart.captured)
    chart.captured.clear()
    chart.short_position('2020-01-05', 120, '2020-02-01', 100)
    assert 'new Lib.Position' in '\n'.join(chart.captured)


def test_position_set_risk_ratio(chart):
    position = chart.position('2020-01-05', 100, '2020-02-01', 120)
    chart.captured.clear()
    position.set_risk_ratio(3.0)
    assert 'riskRatio: 3.0' in chart.captured[-1]


# --------------------------------------------------------------------------
# three-point drawings
# --------------------------------------------------------------------------

def test_andrews_pitchfork_primitive(chart):
    chart.captured.clear()
    chart.andrews_pitchfork('2020-01-05', 100, '2020-01-20', 110, '2020-02-01', 90, extension=5)
    script = '\n'.join(chart.captured)
    assert 'new Lib.AndrewsPitchfork' in script
    assert 'extension: 5' in script
    assert '.series.attachPrimitive(' in script


def test_three_point_drawing_sends_three_points(chart):
    chart.captured.clear()
    chart.andrews_pitchfork('2020-01-05', 100, '2020-01-20', 110, '2020-02-01', 90)
    script = [s for s in chart.captured if 'AndrewsPitchfork' in s][0]
    assert script.count('"price"') == 3
    assert script.count('"logical"') == 3


def test_triangle_primitive(chart):
    chart.captured.clear()
    chart.triangle('2020-01-05', 100, '2020-01-20', 110, '2020-02-01', 90, fill_enabled=False)
    script = '\n'.join(chart.captured)
    assert 'new Lib.Triangle' in script
    assert 'fillEnabled: false' in script


def test_three_point_drawing_update(chart):
    fork = chart.andrews_pitchfork('2020-01-05', 100, '2020-01-20', 110, '2020-02-01', 90)
    chart.captured.clear()
    fork.update('2020-01-06', 101, '2020-01-21', 111, '2020-02-02', 91)
    script = chart.captured[-1]
    assert 'updatePoints(' in script
    assert script.count('"price"') == 3


# --------------------------------------------------------------------------
# projection drawings (fibonacci extension / gann fan)
# --------------------------------------------------------------------------

def test_fibonacci_extension_primitive(chart):
    chart.captured.clear()
    chart.fibonacci_extension('2020-01-05', 100, '2020-01-20', 120, '2020-02-01', 110,
                              levels=(0, 0.618, 1, 1.618), extension=0.25)
    script = '\n'.join(chart.captured)
    assert 'new Lib.FibonacciExtension' in script
    assert 'levels: [0.0, 0.618, 1.0, 1.618]' in script
    assert 'extension: 0.25' in script
    assert script.count('"price"') == 3


def test_gann_fan_primitive(chart):
    chart.captured.clear()
    chart.gann_fan('2020-01-05', 100, '2020-02-01', 130, extension=2.0, show_labels=True)
    script = '\n'.join(chart.captured)
    assert 'new Lib.GannFan' in script
    assert 'ratios: [' in script
    assert 'extension: 2.0' in script
    assert 'showLabels: true' in script
    assert 'highlightColor' in script


def test_gann_fan_custom_ratios(chart):
    chart.captured.clear()
    chart.gann_fan('2020-01-05', 100, '2020-02-01', 130, ratios=(0.5, 1, 2))
    assert 'ratios: [0.5, 1.0, 2.0]' in '\n'.join(chart.captured)


# --------------------------------------------------------------------------
# horizontal line: price-axis badge vs in-pane label
# --------------------------------------------------------------------------

def test_horizontal_line_in_pane_label_options(chart):
    series = chart.create_line('carrier')
    chart.captured.clear()
    series.horizontal_line(101.5, text='多仓1手', axis_label_visible=False,
                           label_visible=True,
                           label_background_color='#ef5350',
                           label_text_color='#fff')
    script = '\n'.join(chart.captured)
    assert 'new Lib.HorizontalLine' in script
    assert 'axisLabelVisible: false' in script
    assert 'labelVisible: true' in script
    assert "labelBackgroundColor: '#ef5350'" in script
    assert "labelTextColor: '#fff'" in script


def test_horizontal_line_defaults_keep_axis_label(chart):
    series = chart.create_line('carrier')
    chart.captured.clear()
    line = series.horizontal_line(101.5, text='support')
    script = '\n'.join(chart.captured)
    assert 'axisLabelVisible: true' in script
    assert 'labelVisible' not in script
    # runtime updates must not silently turn the in-pane label on
    chart.captured.clear()
    line.options(color='#26a69a', text='resistance')
    assert 'labelVisible' not in '\n'.join(chart.captured)
