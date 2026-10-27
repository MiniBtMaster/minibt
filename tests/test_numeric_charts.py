"""Numeric-horizontal-axis charts (yield curve / options)."""
import pandas as pd
import pytest

from pylightcharts.abstract import Window
from pylightcharts.numeric import AbstractOptionsChart, AbstractYieldCurveChart


@pytest.fixture()
def make_chart():
    def factory(cls):
        captured = []
        window = Window(script_func=captured.append)
        window.loaded = True
        chart = cls(window)
        chart.captured = captured
        captured.clear()
        return chart
    return factory


def test_yield_curve_uses_its_own_chart_kind():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractYieldCurveChart(window)
    assert chart._chart_kind == 'yield-curve'
    assert chart._time_based is False
    assert any('"yield-curve"' in script for script in captured)


def test_options_chart_kind(make_chart):
    chart = make_chart(AbstractOptionsChart)
    assert chart._chart_kind == 'options'
    assert chart._time_based is False


def test_handler_receives_the_kind(make_chart):
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    AbstractOptionsChart(window)
    assert any('"options"' in script for script in captured)


def test_numeric_series_keeps_numeric_time(make_chart):
    chart = make_chart(AbstractYieldCurveChart)
    curve = chart.add_curve('rate')
    chart.captured.clear()
    curve.set(pd.DataFrame({'time': [1, 3, 12], 'rate': [4.2, 4.0, 3.6]}))
    script = chart.captured[-1]
    assert '"time":1' in script and '"value":4.2' in script
    assert '1577836800' not in script      # not converted to epoch seconds


def test_numeric_chart_has_no_candlestick_set(make_chart):
    chart = make_chart(AbstractOptionsChart)
    with pytest.raises(TypeError, match='no candlestick series'):
        chart.set(pd.DataFrame({'time': [1], 'open': [1], 'high': [2],
                                'low': [0], 'close': [1]}))


def test_numeric_charts_still_expose_common_api(make_chart):
    chart = make_chart(AbstractYieldCurveChart)
    chart.captured.clear()
    chart.apply_options(localization={'price_format': {'precision': 2}})
    chart.set_visible_range(1, 12)
    assert any('applyOptions' in s for s in chart.captured)
    assert chart.pane_count() == 1
