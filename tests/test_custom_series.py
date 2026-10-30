"""Tests for declarative custom series and the shape DSL."""
import pandas as pd
import pytest

from pylightcharts import shapes
from pylightcharts.abstract import AbstractChart, CustomSeries, Window


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    chart.set(pd.DataFrame({
        'time': pd.date_range('2020-01-01', periods=6),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
    }))
    captured.clear()
    return chart


@pytest.fixture()
def frame():
    return pd.DataFrame({
        'time': pd.date_range('2020-01-01', periods=4),
        'low': [1.0, 2.0, 3.0, 4.0],
        'high': [2.0, 3.0, 4.0, 5.0],
        'value': [1.5, 2.5, 3.5, 4.5],
    })


# --------------------------------------------------------------------------
# shape DSL
# --------------------------------------------------------------------------

def test_shape_helpers():
    rect = shapes.rect(1, 2, fill_color='#f00', border_color='#000')
    assert rect['type'] == 'rect' and rect['from'] == 1.0 and rect['to'] == 2.0
    assert rect['fillColor'] == '#f00' and rect['borderColor'] == '#000'

    assert shapes.line(5, style='dashed')['style'] == 2
    assert shapes.line(5, style=3)['style'] == 3
    assert shapes.circle(5, radius=4, offset=0.2)['radius'] == 4
    assert shapes.text(5, 'hi')['text'] == 'hi'
    # 多行文本：换行符原样保留（渲染器按行拆开画），lineHeight 默认 1.2
    multi = shapes.text(5, 'BUY\nCCI\nRSI', line_height=1.5)
    assert multi['text'] == 'BUY\nCCI\nRSI'
    assert multi['lineHeight'] == 1.5
    assert multi['baseline'] == 'middle'
    assert shapes.text(5, 'x')['lineHeight'] == 1.2
    assert shapes.band(1, 2)['type'] == 'band'
    assert shapes.polyline([(0, 1), (0.5, 2)])['points'] == [[0.0, 1.0], [0.5, 2.0]]


def test_shape_presets():
    assert len(shapes.range_bar(1, 2)) == 1
    assert len(shapes.box_plot(1, 2, 3, 4, 5)) == 5
    assert len(shapes.error_bar(1, 0.5, 1.5)) == 3


# --------------------------------------------------------------------------
# custom series
# --------------------------------------------------------------------------

def test_add_custom_series(chart):
    series = chart.add_custom_series('my custom')
    assert isinstance(series, CustomSeries)
    script = chart.captured[-1]
    assert '"createCustomSeries"' in script
    assert '"my custom"' in script
    assert f'"{series.id}"' in script


def test_set_with_shape_builder(chart, frame):
    series = chart.add_custom_series('ranges')
    chart.captured.clear()
    series.set(frame, shapes=lambda row: shapes.range_bar(row['low'], row['high']))
    script = chart.captured[-1]
    assert '.series.setData(' in script
    assert '"shapes"' in script and '"type":"rect"' in script
    assert '"from":1.0' in script and '"to":2.0' in script
    assert '"time":1577836800' in script            # epoch seconds


def test_set_with_shapes_column(chart, frame):
    series = chart.add_custom_series('ranges')
    frame = frame.copy()
    frame['shapes'] = [[shapes.line(1.0)] for _ in range(len(frame))]
    chart.captured.clear()
    series.set(frame)
    assert '"type":"line"' in chart.captured[-1]


def test_set_with_shapes_list(chart, frame):
    series = chart.add_custom_series('ranges')
    chart.captured.clear()
    series.set(frame, shapes=[[shapes.circle(1.0)] for _ in range(len(frame))])
    assert '"type":"circle"' in chart.captured[-1]


def test_custom_series_in_new_pane(chart, frame):
    chart.add_custom_series('osc', pane_index='new')
    scripts = chart.captured
    assert any('"addPane"' in s for s in scripts)
    create = [s for s in scripts if 'createCustomSeries' in s][0]
    assert ',1,null,true]' in create.replace(' ', '')


def test_custom_series_update(chart):
    series = chart.add_custom_series('ranges')
    chart.captured.clear()
    series.update({'time': 1577836800, 'value': 3.0, 'shapes': [shapes.circle(3.0)]})
    script = chart.captured[-1]
    assert '.series.update(' in script and '"type":"circle"' in script


def test_custom_series_clear(chart, frame):
    series = chart.add_custom_series('ranges')
    series.set(frame)
    chart.captured.clear()
    series.set(pd.DataFrame())
    assert '.series.setData([])' in chart.captured[-1]


def test_custom_series_delete_uses_remove_series(chart):
    series = chart.add_custom_series('ranges')
    chart.captured.clear()
    series.delete()
    assert any('"removeSeries"' in s for s in chart.captured)


def test_stem_draws_a_vertical_dashed_stick():
    """`shapes.stem` = 同一 bar 偏移上的两点 polyline（竖直虚线）+ 可选端点圆。

    LWC 没有"竖直虚线"图元，`stem` 就是它的替代：两个点共用同一个 bar 偏移，
    渲染器对 polyline 本来就会 `setDash(shape.style)`，所以不需要任何 JS。
    """
    from pylightcharts import shapes

    stick = shapes.stem(12.0, baseline=0.0)
    assert len(stick) == 1
    assert stick[0]['type'] == 'polyline'
    assert stick[0]['points'] == [[0.0, 0.0], [0.0, 12.0]]
    assert stick[0]['style'] != 0                 # 默认是虚线
    capped = shapes.stem(-8.0, cap=True, cap_radius=4)
    assert [s['type'] for s in capped] == ['polyline', 'circle']
    assert capped[1]['price'] == -8.0 and capped[1]['radius'] == 4
