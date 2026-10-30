"""Regression tests for Phase 2 (options passthrough, panes, primitives)."""
import json

import pytest

from pylightcharts.abstract import AbstractChart, PriceScale, Window
from pylightcharts.util import ref


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    captured.clear()
    return chart


# --------------------------------------------------------------------------
# chart / time scale / layout / grid / crosshair
# --------------------------------------------------------------------------

def test_chart_apply_options(chart):
    chart.apply_options(auto_size=True, localization={'price_format': {'precision': 4}})
    script = chart.captured[-1]
    assert f'Lib.invoke("{chart.id}.chart", "applyOptions"' in script
    assert '"autoSize":true' in script
    assert '"priceFormat"' in script and '"precision":4' in script


def test_time_scale_options(chart):
    chart.time_scale_options(right_offset=10, bar_spacing=6)
    script = chart.captured[-1]
    assert f'Lib.invoke("{chart.id}.timeScale", "applyOptions"' in script
    assert '"rightOffset":10' in script and '"barSpacing":6' in script


def test_time_scale_named_method(chart):
    chart.time_scale(right_offset=3, seconds_visible=True)
    script = chart.captured[-1]
    assert f'Lib.invoke("{chart.id}.timeScale", "applyOptions"' in script
    assert '"secondsVisible":true' in script


def test_layout_uses_bridge(chart):
    chart.layout(background_color='#101010', text_color='#ffffff', font_size=14)
    assert any('applyOptions' in s and '"layout"' in s for s in chart.captured)
    assert any('"backgroundColor": "#101010"' in s or '"#101010"' in s for s in chart.captured)


def test_grid_uses_bridge(chart):
    chart.grid(vert_enabled=False, color='#222222')
    script = chart.captured[-1]
    assert '"grid"' in script and '"vertLines"' in script and '"visible":false' in script


def test_crosshair_uses_bridge(chart):
    chart.crosshair(mode='magnet', vert_width=2, vert_color='#fff')
    script = chart.captured[-1]
    assert '"crosshair"' in script and '"mode":1' in script
    assert '"vertLine"' in script and '"width":2' in script


def test_fit_and_visible_range(chart):
    chart.fit()
    assert f'Lib.invoke("{chart.id}.timeScale", "fitContent"' in chart.captured[-1]
    chart.set_visible_range('2024-01-01', '2024-02-01')
    script = chart.captured[-1]
    assert f'Lib.invoke("{chart.id}.timeScale", "setVisibleRange"' in script
    assert '"from":' in script and '"to":' in script


# --------------------------------------------------------------------------
# price scale
# --------------------------------------------------------------------------

def test_series_price_scale_options(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    area.price_scale_options(mode=1, invert_scale=True)
    scripts = chart.captured
    assert any('"priceScale"' in s for s in scripts)
    assert f'Lib.invoke("{area.id}.priceScaleHandle", "applyOptions"' in scripts[-1]
    assert '"invertScale":true' in scripts[-1]


def test_set_price_scale_mode(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    area.set_price_scale_mode('logarithmic')
    assert '"mode":1' in chart.captured[-1]


def test_chart_get_price_scale_registers_handle(chart):
    ps = chart.get_price_scale('left')
    assert isinstance(ps, PriceScale)
    script = chart.captured[-1]
    assert '"priceScale"' in script and '"left"' in script and f'"{ps.id}"' in script
    chart.captured.clear()
    ps.set_mode('percentage')
    assert '"mode":2' in chart.captured[-1]


# --------------------------------------------------------------------------
# panes
# --------------------------------------------------------------------------

def test_add_series_to_pane(chart):
    chart.add_series('Line', 'paneLine', pane_index=1, color='#0ff')
    script = chart.captured[-1]
    assert '"addSeries"' in script
    assert '"paneLine"' in script
    assert script.rstrip().endswith(',1,true])\nnull') and ',1,true]' in script.replace(' ', '')


def test_create_area_in_pane(chart):
    chart.create_area(name='close', pane_index=2)
    assert ',2,true]' in chart.captured[-1].replace(' ', '')


def test_pane_count_tracks_python_side(chart):
    # without a live webview the count is tracked python-side
    assert chart.pane_count() == 1
    chart.add_pane()
    assert chart.pane_count() == 2


def test_pane_helpers(chart):
    chart.captured.clear()
    chart.add_pane()
    assert any('"addPane"' in s for s in chart.captured)
    chart.remove_pane(0)
    assert any('"removePane"' in s for s in chart.captured)
    chart.swap_panes(0, 1)
    assert any('"swapPanes"' in s for s in chart.captured)
    chart.set_pane_stretch(1, 2.5)
    script = chart.captured[-1]
    assert '"setStretchFactor"' in script and '2.5' in script


# --------------------------------------------------------------------------
# primitives / plugins
# --------------------------------------------------------------------------

def test_ref_helper():
    assert ref('myHandle') == {'$ref': 'myHandle'}


def test_attach_detach_primitive(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    area.attach_primitive('myPrimitive')
    assert '"attachPrimitive"' in chart.captured[-1]
    assert json.loads('{"$ref": "myPrimitive"}') == {'$ref': 'myPrimitive'}
    assert '\\"$ref\\"' not in chart.captured[-1]      # not double-encoded
    assert '"$ref":"myPrimitive"' in chart.captured[-1]
    area.detach_primitive('myPrimitive')
    assert '"detachPrimitive"' in chart.captured[-1]


def test_create_up_down_markers(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    handle = area.create_up_down_markers(positive_color='#0f0', update_visibility_duration=500)
    script = chart.captured[-1]
    assert '"createUpDownMarkers"' in script
    assert '"$ref"' in script and f'{area.id}.series' in script
    assert '"updateVisibilityDuration":500' in script
    assert handle == f'{area.id}.upDownMarkers'


# --------------------------------------------------------------------------
# migrated candle/volume config
# --------------------------------------------------------------------------

def test_candle_style_goes_through_bridge(chart):
    chart.captured.clear()
    chart.candle_style(up_color='#0f0', down_color='#f00', border_visible=False)
    script = chart.captured[-1]
    assert f'Lib.invoke("{chart.id}.series", "applyOptions"' in script
    assert '"upColor":"#0f0"' in script and '"borderVisible":false' in script
    assert '"wickUpColor":"#0f0"' in script      # defaults filled in


def test_series_options_targets_series(chart):
    chart.captured.clear()
    chart.series_options(price_line_width=2, base_line_visible=False)
    script = chart.captured[-1]
    assert f'Lib.invoke("{chart.id}.series", "applyOptions"' in script
    assert '"priceLineWidth":2' in script


def test_precision_and_hide_data(chart):
    chart.captured.clear()
    chart.precision(4)
    assert '"minMove":0.0001' in chart.captured[-1]
    chart.hide_data()
    # 主序列走 JSON（Lib.invoke applyOptions），成交量序列走 JS 字面量
    # 且带存在性守卫，所以要看**全部**脚本而不只是最后一条。
    joined = '\n'.join(chart.captured)
    assert '"visible":false' in joined
    assert 'volumeSeries' in joined and 'visible: false' in joined
    chart.show_data()
    joined = '\n'.join(chart.captured)
    assert '"visible":true' in joined
    assert 'visible: true' in joined
