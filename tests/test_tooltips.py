"""Crosshair tooltips (`pylightcharts.tooltips`).

The tutorial builds them from an `html` element plus `subscribeCrosshairMove`;
these do it inside the bundle. The DOM behaviour (positions, flipping, clamping,
lifecycle) is verified in a real browser by `tests/e2e/smoke.py` - here we check
the bridge: what python sends, and where each method goes.
"""
import pandas as pd
import pytest

from pylightcharts import Window
from pylightcharts.abstract import AbstractChart
from pylightcharts.tooltips import Tooltip


class _Recorder:
    """Stands in for a live webview: records invoke_get calls."""

    def __init__(self, result=True):
        self.calls = []
        self.result = result

    def __call__(self, handle, method, *args):
        self.calls.append((handle, method, args))
        return self.result


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    chart.set(pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=5, freq='D'),
        'open': [1.0, 2.0, 3.0, 4.0, 5.0],
        'high': [2.0, 3.0, 4.0, 5.0, 6.0],
        'low': [0.0, 1.0, 2.0, 3.0, 4.0],
        'close': [1.5, 2.5, 3.5, 4.5, 5.5],
        'volume': [10, 11, 12, 13, 14],
    }))
    chart.captured.clear()
    return chart


# --------------------------------------------------------------------------
# creating one
# --------------------------------------------------------------------------

def test_tracking_tooltip_creates_it_for_the_right_series(chart):
    line = chart.create_line('sma', color='#2962FF')
    chart.captured.clear()
    tip = line.tracking_tooltip(title='ABC Inc.')

    script = chart.captured[-1]
    # the chart creates it, the series is passed as a reference (like
    # `removeSeries` and `attachPrimitive`)
    assert f'Lib.invoke("{chart.id}", "createTooltip"' in script
    assert f'{{"$ref":"{line.id}.series"}}' in script
    assert '"title":"ABC Inc."' in script
    assert '"mode":"tracking"' in script
    assert isinstance(tip, Tooltip) and tip.mode == 'tracking'
    assert tip.id == f'{line.id}.trackingTooltip'


def test_chart_level_tooltip_reads_the_main_series(chart):
    chart.tracking_tooltip()
    script = chart.captured[-1]
    assert f'{{"$ref":"{chart.id}.series"}}' in script


def test_magnifier_and_tracking_use_separate_handles(chart):
    chart.captured.clear()
    tracking = chart.tracking_tooltip()
    magnifier = chart.magnifier_tooltip()
    assert tracking.id.endswith('.trackingTooltip')
    assert magnifier.id.endswith('.magnifierTooltip')
    modes = [line for line in chart.captured if 'createTooltip' in line]
    assert '"mode":"magnifier"' in modes[-1]


def test_options_are_camel_cased(chart):
    chart.captured.clear()
    chart.tracking_tooltip(title='X', big_font_size=20, color_by_candle=False,
                           time_format='YYYY-MM-DD HH:mm', background_opacity=0.5)
    script = chart.captured[-1]
    for option in ('"bigFontSize":20', '"colorByCandle":false',
                   '"timeFormat":"YYYY-MM-DD HH:mm"', '"backgroundOpacity":0.5'):
        assert option in script


def test_the_title_defaults_to_the_series_name(chart):
    line = chart.create_line('SMA 20')
    chart.captured.clear()
    line.tracking_tooltip()
    assert '"title":"SMA 20"' in chart.captured[-1]


def test_fields_accept_auto_a_sequence_and_a_single_name(chart):
    chart.captured.clear()
    tip = chart.tracking_tooltip(fields='auto')
    assert '"fields":"auto"' in chart.captured[-1]

    tip.set_fields('open', 'high', 'low', 'close')
    assert '"fields":["open","high","low","close"]' in chart.captured[-1]

    # a single name is not split into characters, and a one-item 'auto' list
    # still means 'auto'
    tip.set_fields('auto')
    assert '"fields":"auto"' in chart.captured[-1]


def test_field_labels_are_sent_as_a_list(chart):
    chart.captured.clear()
    chart.tracking_tooltip(fields=('open', 'close'), field_labels=('O', 'C'))
    script = chart.captured[-1]
    assert '"fieldLabels":["O","C"]' in script


def test_an_unknown_mode_is_rejected(chart):
    with pytest.raises(ValueError, match='tracking'):
        chart.tooltip('magnifyer')
    with pytest.raises(ValueError, match='tracking'):
        chart.tooltip(3)


def test_bad_fields_are_rejected(chart):
    with pytest.raises(ValueError, match='field names'):
        chart.tracking_tooltip(fields=(1, 2))


# --------------------------------------------------------------------------
# driving one
# --------------------------------------------------------------------------

def test_the_handle_methods_go_to_the_js_object(chart):
    tip = chart.tracking_tooltip(title='X')
    chart.captured.clear()

    assert tip.apply_options(width=120) is tip
    assert tip.set_title('AAPL') is tip
    assert tip.set_fields('close') is tip
    assert tip.hide() is tip
    assert tip.show() is tip
    calls = [line for line in chart.captured if 'Lib.invoke' in line]
    assert len(calls) == 5
    assert '"applyOptions", [{"width":120}]' in calls[0]
    assert '"hide"' in calls[3] and '"show"' in calls[4]
    # every call targets the tooltip's own handle
    assert all(f'"{tip.id}"' in line for line in calls)


def test_set_mode_switches_between_the_two(chart):
    tip = chart.tracking_tooltip()
    chart.captured.clear()
    tip.set_mode('magnifier')
    assert tip.mode == 'magnifier'
    assert '"mode":"magnifier"' in chart.captured[-1]
    with pytest.raises(ValueError):
        tip.set_mode('nope')


def test_remove_targets_the_handle(chart):
    tip = chart.magnifier_tooltip()
    chart.captured.clear()
    tip.remove()
    assert f'"{tip.id}", "remove"' in chart.captured[-1]


def test_visible_and_options_read_back(chart):
    tip = chart.tracking_tooltip()
    recorder = _Recorder(True)
    chart.win.invoke_get = recorder
    assert tip.visible() is True
    assert recorder.calls[-1] == (tip.id, 'visible', ())

    recorder.result = {'mode': 'tracking', 'width': 96}
    assert tip.options()['width'] == 96
    assert recorder.calls[-1] == (tip.id, 'options', ())


def test_headless_readbacks_raise_instead_of_silently_returning_none(chart):
    tip = chart.tracking_tooltip()
    with pytest.raises(Exception):
        tip.visible()
