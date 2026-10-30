"""Indicator sub-charts as v5 **panes**: create, fill, remove.

The companion example is `examples/11_api_tour/19_indicator_panes.py`; the real
engine behaviour (an emptied pane disappearing, the legend row going with the
series) is checked in `tests/e2e/smoke.py` (`paneLifecycle`).
"""
import pandas as pd
import pytest

from pylightcharts import Window
from pylightcharts.abstract import AbstractChart


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


def add_indicator(chart, name='RSI 14', pane=None):
    """A line in its own pane, like the example's `show_indicator`."""
    pane = chart.add_pane() if pane is None else pane
    series = chart.pane_add_series(pane, 'Line', name=name, color='#7E57C2')
    series.set(pd.DataFrame({'time': chart.candle_data['time'],
                             name: range(len(chart.candle_data))}))
    return pane, series


# --------------------------------------------------------------------------
# creating
# --------------------------------------------------------------------------

def test_add_pane_numbers_offline(chart):
    """`pane_count()` has to work before the webview is loaded."""
    assert chart.pane_count() == 1
    first = chart.add_pane()
    second = chart.add_pane()
    assert (first, second) == (1, 2)
    assert chart.pane_count() == 3
    assert '"addPane"' in chr(10).join(chart.captured)


def test_a_pane_series_records_its_pane(chart):
    pane, series = add_indicator(chart)
    assert pane == 1 and series.pane_index == 1
    script = chr(10).join(chart.captured)
    assert '"Line","RSI 14"' in script
    assert '"addSeries"' in script
    # the pane index is the 5th positional argument of `addSeries`
    assert ',1,true])' in script.replace(' ', '')


def test_the_main_pane_is_zero(chart):
    assert chart.pane_index == 0


# --------------------------------------------------------------------------
# removing a series: the pane follows
# --------------------------------------------------------------------------

def test_deleting_a_series_removes_it_and_its_legend_row(chart):
    _, series = add_indicator(chart)
    chart.captured.clear()
    series.delete()
    script = chr(10).join(chart.captured)
    # the legend row is dropped by the JS side, which needs the live wrapper -
    # so the handle is passed as a reference (a plain string is ignored)
    assert '"removeSeries"' in script
    assert '"$ref"' in script
    assert series not in chart._lines


def test_deleting_a_series_twice_is_a_noop(chart):
    """同一序列可能同时登记在多个列表里，第二次 delete 不能再发 removeSeries
    （否则会引用已被 JS 删掉的 handle，报 “Value is undefined”）。"""
    _, series = add_indicator(chart)
    chart.captured.clear()
    series.delete()
    series.delete()                      # 重复删除
    script = chr(10).join(chart.captured)
    assert script.count('"removeSeries"') == 1


def test_an_emptied_pane_shifts_the_later_ones_up(chart):
    _, first = add_indicator(chart, 'first')
    _, second = add_indicator(chart, 'second')
    assert (first.pane_index, second.pane_index) == (1, 2)

    first.delete()

    assert chart.pane_count() == 2          # the engine dropped pane 1
    assert second.pane_index == 1           # ... and pane 2 moved up
    assert chart._lines == [second]


def test_deleting_in_the_main_pane_keeps_the_panes(chart):
    _, series = add_indicator(chart)
    volume = chart.create_histogram('volume')
    volume._pane_index = 0
    chart._lines.append(volume)
    chart.captured.clear()

    volume.delete()

    assert chart.pane_count() == 2
    assert series.pane_index == 1
    assert volume not in chart._lines


def test_a_series_with_siblings_keeps_the_pane(chart):
    pane, first = add_indicator(chart, 'first')
    second = chart.pane_add_series(pane, 'Line', name='second')
    first.delete()
    assert chart.pane_count() == 2          # 'second' is still there
    assert second.pane_index == 1


# --------------------------------------------------------------------------
# preserved panes and explicit removal
# --------------------------------------------------------------------------

def test_a_preserved_pane_survives(chart):
    pane = chart.add_pane(preserve_empty=True)
    series = chart.pane_add_series(pane, 'Line', name='probe')
    series.delete()
    assert chart.pane_count() == 2
    assert chart._preserved_panes == {pane}


def test_remove_pane_shifts_and_forgets(chart):
    preserved = chart.add_pane(preserve_empty=True)
    _, series = add_indicator(chart)        # pane 2
    chart.captured.clear()

    chart.remove_pane(preserved)            # drop pane 1 on purpose

    assert '"removePane"' in chr(10).join(chart.captured)
    assert chart.pane_count() == 2
    assert series.pane_index == 1           # pane 2 moved up
    assert chart._preserved_panes == set()


def test_removing_the_main_pane_is_ignored_offline(chart):
    chart.remove_pane(0)
    assert chart.pane_count() == 1


# --------------------------------------------------------------------------
# the example
# --------------------------------------------------------------------------

def _example():
    import importlib.util
    import pathlib as _pathlib
    path = (_pathlib.Path(__file__).resolve().parents[1]
            / 'examples' / '11_api_tour' / '19_indicator_panes.py')
    spec = importlib.util.spec_from_file_location('tour19', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_example_builds_one_indicator_pane():
    from pylightcharts.headless import HeadlessChart
    module = _example()
    chart = HeadlessChart(width=1100, height=760)
    module.build(chart)

    assert chart.pane_count() == 2
    assert [series.name for series in chart._lines] == ['RSI 14']
    assert chart._lines[0].pane_index == 1
    assert module.SUBPLOT['pane'] == 1
    script = chr(10).join(chart._scripts)
    assert 'RSI 14' in script
    # the legend (the label + its eye icon) is switched on
    assert "legend.div.style.display = 'flex'" in script
    assert "legend.text.innerText = 'PANE DEMO'" in script


def test_the_example_swaps_the_indicator_and_its_pane():
    from pylightcharts.headless import HeadlessChart
    module = _example()
    chart = HeadlessChart(width=1100, height=760)
    module.build(chart)

    module.show_indicator(chart, 'MACD')
    assert chart.pane_count() == 2                    # one sub pane, swapped
    assert [series.name for series in chart._lines] == ['MACD 12,26']
    assert chart._lines[0].pane_index == 1

    module.show_indicator(chart, 'none')
    assert chart.pane_count() == 1                    # back to the main pane
    assert chart._lines == []
    assert module.SUBPLOT == {'pane': None, 'series': None}


def test_the_example_removes_the_last_pane():
    """The topbar button: drop the last sub pane (series + label + pane)."""
    from pylightcharts.headless import HeadlessChart
    module = _example()
    chart = HeadlessChart(width=1100, height=760)
    module.build(chart)
    assert chart.pane_count() == 2

    assert module.remove_last_pane(chart) is True

    assert chart.pane_count() == 1
    assert chart._lines == []
    assert module.SUBPLOT == {'pane': None, 'series': None}
    # nothing left to remove
    assert module.remove_last_pane(chart) is False


def test_removing_the_last_pane_also_takes_a_preserved_one():
    from pylightcharts.headless import HeadlessChart
    module = _example()
    chart = HeadlessChart(width=1100, height=760)
    module.build(chart)

    # the '保留空 pane' button's pane survives its series, so the remove button
    # has to drop it explicitly
    pane = chart.add_pane(preserve_empty=True)
    chart.pane_add_series(pane, 'Line', name='probe', color='#26A69A')
    assert chart.pane_count() == 3

    assert module.remove_last_pane(chart) is True

    assert chart.pane_count() == 2          # the preserved probe pane is gone
    assert chart._preserved_panes == set()
    assert [series.name for series in chart._lines] == ['RSI 14']


def test_the_example_wires_the_remove_button():
    from pylightcharts.headless import HeadlessChart
    module = _example()
    chart = HeadlessChart(width=1100, height=760)
    module.build(chart)
    assert set(chart.topbar._widgets) == {'indicator', 'keep', 'remove_pane'}
    assert '删除最后一个副图' in chr(10).join(chart._scripts)


def test_the_example_indicator_lines_up_with_the_candles():
    """The pane indicator must use the chart's own (epoch second) time axis.

    It used to be fed `chart.candle_data['time']`, which pandas read as
    nanoseconds, so the line was drawn in 1970 - far left of the candles.
    """
    from pylightcharts.headless import HeadlessChart
    import numpy as np
    module = _example()
    chart = HeadlessChart(width=1100, height=760)
    module.build(chart)

    rsi = chart._lines[0]
    assert int(rsi.data['time'].min()) == chart.candle_data['time'].min()
    assert int(rsi.data['time'].max()) == chart.candle_data['time'].max()
    assert len(rsi.data) == len(chart.candle_data)
    # `set()` renames the name column to `value`
    assert list(rsi.data.columns) == ['time', 'value']
    # the warm-up bar is the only gap
    assert int(rsi.data['value'].isna().sum()) == 1
    assert np.isfinite(rsi.data['value'].dropna()).all()


def test_switching_the_example_indicator_keeps_the_time_axis():
    from pylightcharts.headless import HeadlessChart
    module = _example()
    chart = HeadlessChart(width=1100, height=760)
    module.build(chart)

    for name in ('MACD', 'CCI'):
        module.show_indicator(chart, name)
        series = chart._lines[0]
        assert series.name == module.INDICATORS[name][0]
        assert int(series.data['time'].min()) == chart.candle_data['time'].min()
        assert int(series.data['time'].max()) == chart.candle_data['time'].max()
