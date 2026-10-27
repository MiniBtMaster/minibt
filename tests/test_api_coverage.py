"""Tests for the API-coverage additions: price lines, data readback,
coordinate conversion, series scheduling, time scale helpers, events."""
import pandas as pd
import pytest

from pylightcharts.abstract import AbstractChart, Window


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    chart.set(pd.DataFrame({
        'time': pd.date_range('2020-01-01', periods=30),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5, 'volume': 10,
    }))
    captured.clear()
    return chart


class _Recorder:
    """Stands in for a live webview: records invoke_get calls."""

    def __init__(self, result=42):
        self.calls = []
        self.result = result

    def __call__(self, handle, method, *args):
        self.calls.append((handle, method, args))
        return self.result


# --------------------------------------------------------------------------
# price lines
# --------------------------------------------------------------------------

def test_create_price_line(chart):
    chart.captured.clear()
    line = chart.create_price_line(105.5, color='#f00', title='entry', line_width=2)
    script = chart.captured[-1]
    assert '"createPriceLine"' in script
    assert '"price":105.5' in script and '"title":"entry"' in script
    assert '"lineWidth":2' in script and '"color":"#f00"' in script
    assert f'"{line.id}"' in script              # stored under a handle
    assert chart.price_lines() == [line]


def test_price_line_options_and_remove(chart):
    line = chart.create_price_line(100)
    chart.captured.clear()
    line.apply_options(color='#0f0', line_visible=False)
    script = chart.captured[-1]
    assert f'Lib.invoke("{line.id}", "applyOptions"' in script
    assert '"color":"#0f0"' in script and '"lineVisible":false' in script

    chart.captured.clear()
    line.remove()
    script = chart.captured[-1]
    assert '"removePriceLine"' in script
    assert '"$ref":"' + line.id + '"' in script
    assert chart.price_lines() == []


# --------------------------------------------------------------------------
# series scheduling
# --------------------------------------------------------------------------

def test_move_to_pane_creates_target_pane(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    area.move_to_pane(2)
    scripts = '\n'.join(chart.captured)
    assert '"addPane"' in scripts                # panes 1 and 2 created
    assert '"moveToPane"' in scripts


def test_series_order(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    area.set_series_order(3)
    assert '"setSeriesOrder"' in chart.captured[-1]
    recorder = _Recorder(3)
    chart.win.invoke_get = recorder
    assert area.series_order() == 3
    assert recorder.calls[-1][1] == 'seriesOrder'


# --------------------------------------------------------------------------
# data readback / coordinate conversion
# --------------------------------------------------------------------------

def test_data_readback_methods(chart):
    recorder = _Recorder(7)
    chart.win.invoke_get = recorder

    assert chart.price_to_coordinate(100) == 7
    assert chart.coordinate_to_price(50) == 7
    assert chart.data_by_index(5) == 7
    assert chart.data_points() == 7
    assert chart.pop(2) == 7
    assert chart.last_value_data() == 7
    assert chart.bars_in_logical_range(0, 10) == 7
    assert chart.series_type() == 7

    methods = [call[1] for call in recorder.calls]
    assert methods == [
        'priceToCoordinate', 'coordinateToPrice', 'dataByIndex', 'data',
        'pop', 'lastValueData', 'barsInLogicalRange', 'seriesType',
    ]
    assert recorder.calls[0][0].endswith('.series')
    assert recorder.calls[6][2] == ({'from': 0, 'to': 10},)


def test_get_pane_index(chart):
    chart.captured.clear()
    recorder = _Recorder(1)
    chart.win.invoke_get = recorder
    assert chart.get_pane_index() == 1
    assert any('"getPane"' in script for script in chart.captured)
    assert recorder.calls[-1][1] == 'paneIndex'


# --------------------------------------------------------------------------
# time scale
# --------------------------------------------------------------------------

def test_time_scale_fire_and_forget(chart):
    chart.captured.clear()
    chart.scroll_to_real_time()
    assert '"scrollToRealTime"' in chart.captured[-1]
    chart.scroll_to_position(3, animated=False)
    assert '"scrollToPosition"' in chart.captured[-1] and 'false' in chart.captured[-1]
    chart.reset_time_scale()
    assert '"resetTimeScale"' in chart.captured[-1]
    chart.set_visible_logical_range(0, 50)
    assert '"setVisibleLogicalRange"' in chart.captured[-1]


def test_time_scale_readback(chart):
    recorder = _Recorder(11)
    chart.win.invoke_get = recorder
    assert chart.scroll_position() == 11
    assert chart.time_scale_width() == 11
    assert chart.time_scale_height() == 11
    assert chart.get_visible_range() == 11
    assert chart.get_visible_logical_range() == 11
    assert chart.time_to_coordinate('2020-01-05') == 11
    assert chart.coordinate_to_time(10) == 11
    assert chart.time_to_index('2020-01-05') == 11
    assert chart.logical_to_coordinate(3) == 11
    assert chart.coordinate_to_logical(10) == 11
    assert [call[1] for call in recorder.calls] == [
        'scrollPosition', 'width', 'height', 'getVisibleRange', 'getVisibleLogicalRange',
        'timeToCoordinate', 'coordinateToTime', 'timeToIndex', 'logicalToCoordinate',
        'coordinateToLogical',
    ]


# --------------------------------------------------------------------------
# pane queries
# --------------------------------------------------------------------------

def test_pane_queries(chart):
    recorder = _Recorder(2)
    chart.win.invoke_get = recorder
    assert chart.pane_height(0) == 2
    assert chart.pane_stretch_factor(0) == 2
    assert chart.pane_size() == 2
    assert [call[1] for call in recorder.calls] == ['getHeight', 'getStretchFactor', 'paneSize']

    chart.captured.clear()
    chart.set_pane_height(300, index=0)
    assert '"setHeight"' in chart.captured[-1] and '300' in chart.captured[-1]


# --------------------------------------------------------------------------
# price scale extras
# --------------------------------------------------------------------------

def test_price_scale_visible_range_and_autoscale(chart):
    scale = chart.get_price_scale('right')
    recorder = _Recorder(0)
    chart.win.invoke_get = recorder
    chart.captured.clear()
    scale.set_auto_scale(False)
    assert '"setAutoScale"' in chart.captured[-1] and 'false' in chart.captured[-1]
    assert scale.get_visible_range() == 0
    assert recorder.calls[-1][1] == 'getVisibleRange'


def test_pane_price_scale_registers_pane_handle(chart):
    scale = chart.pane_price_scale(0, 'left')
    assert scale.pane_index == 0
    assert scale.id.endswith('.pane0.priceScale.left')
    assert '"priceScale"' in '\n'.join(chart.captured)


# --------------------------------------------------------------------------
# chart lifecycle / crosshair
# --------------------------------------------------------------------------

def test_chart_lifecycle(chart):
    chart.captured.clear()
    chart.clear_crosshair_position()
    assert '"clearCrosshairPosition"' in chart.captured[-1]
    chart.set_crosshair_position(105.0, '2020-01-05')
    script = chart.captured[-1]
    assert '"setCrosshairPosition"' in script and '105.0' in script and '"$ref"' in script
    chart.remove()
    # releasing a chart disposes the engine and drops its wrapper from the page
    lifecycle = '\n'.join(chart.captured)
    assert '"remove"' in lifecycle and '"destroy"' in lifecycle


# --------------------------------------------------------------------------
# events
# --------------------------------------------------------------------------

def test_crosshair_and_dblclick_events(chart):
    """Crosshair moves go through the handler's fan-out, not the chart's single slot
    (``chart.subscribeCrosshairMove`` can only hold one subscriber, which used to
    evict the drawing tool whenever the host subscribed)."""
    chart.captured.clear()
    chart.events.crosshair_move += lambda c, time, price: None
    script = '\n'.join(chart.captured)
    assert 'addCrosshairListener' in script
    assert 'subscribeCrosshairMove' not in script
    chart.captured.clear()
    chart.events.crosshair_move.unsubscribe()
    assert 'removeCrosshairListener' in '\n'.join(chart.captured)

    chart.captured.clear()
    chart.events.dblclick += lambda c, time, price: None
    script = '\n'.join(chart.captured)
    assert 'addDblClickListener' in script
    assert 'subscribeDblClick' not in script
    chart.captured.clear()
    chart.events.dblclick.unsubscribe()
    assert 'removeDblClickListener' in '\n'.join(chart.captured)


def test_click_and_range_change_unsubscribe(chart):
    chart.events.click += lambda c, time, price: None
    assert 'addClickListener' in '\n'.join(chart.captured)
    chart.captured.clear()
    chart.events.click.unsubscribe()
    script = '\n'.join(chart.captured)
    assert 'removeClickListener' in script
    assert 'unsubscribeClick' not in script

    chart.events.range_change += lambda c, before, after: None
    chart.captured.clear()
    chart.events.range_change.unsubscribe()
    assert 'unsubscribeVisibleLogicalRangeChange' in '\n'.join(chart.captured)


def test_event_handler_is_removed_from_python_registry(chart):
    chart.events.crosshair_move += lambda c, time, price: None
    name = chart.events.crosshair_move._name
    assert name in chart.win.handlers
    chart.events.crosshair_move.unsubscribe()
    assert name not in chart.win.handlers


def test_event_handlers_are_window_scoped(chart):
    """`let` declarations in evaluate_js do not persist between calls, so event
    handlers must be attached to `window` or unsubscribe() fails at runtime."""
    chart.captured.clear()
    chart.events.click += lambda c, t, p: None
    assert 'window.clickHandler' in '\n'.join(chart.captured)

    chart.captured.clear()
    chart.events.dblclick += lambda c, t, p: None
    assert 'window.dblClickHandler' in '\n'.join(chart.captured)

    chart.captured.clear()
    chart.events.range_change += lambda c, before, after: None
    script = '\n'.join(chart.captured)
    assert 'window.checkLogicalRange' in script
    assert 'let checkLogicalRange' not in script

    chart.captured.clear()
    chart.events.crosshair_move += lambda c, t, p: None
    assert 'window.crosshairHandler' in '\n'.join(chart.captured)


# --------------------------------------------------------------------------
# Phase 0/1 additions: value reads, new events, plugins handles, constants
# --------------------------------------------------------------------------

def test_read_property_expression(chart):
    """`read_property` resolves a handle through Lib.lookup and appends the path."""
    calls = []

    def fake(script, timeout=None):
        calls.append(script)
        return 'x'

    chart.win.run_script_and_get = fake
    assert chart.win.read_property('window.abc', 'options()') == 'x'
    assert calls[-1] == 'Lib.lookup("window.abc").options()'
    chart.win.read_property('window.abc')
    assert calls[-1] == 'Lib.lookup("window.abc")'


def test_chart_options_readback(chart):
    calls = []

    def fake(script, timeout=None):
        calls.append(script)
        return {'layout': {'fontSize': 12}}

    chart.win.run_script_and_get = fake
    assert chart.chart_options() == {'layout': {'fontSize': 12}}
    assert 'options()' in calls[-1]


def test_chart_element_and_horz_behavior(chart):
    chart.captured.clear()
    elem = chart.chart_element()
    assert elem.endswith('.chartElement')
    assert '"chartElement"' in chart.captured[-1]
    chart.captured.clear()
    hb = chart.horz_behavior()
    assert hb.endswith('.horzBehavior')
    assert '"horzBehaviour"' in chart.captured[-1]


def test_time_scale_settings(chart):
    recorder = _Recorder({'timeVisible': True})
    chart.win.invoke_get = recorder
    assert chart.time_scale_settings() == {'timeVisible': True}
    assert recorder.calls[-1][0].endswith('.timeScale')
    assert recorder.calls[-1][1] == 'options'


def test_price_scale_options_readback(chart):
    scale = chart.get_price_scale('right')
    recorder = _Recorder({'mode': 0})
    chart.win.invoke_get = recorder
    assert scale.options() == {'mode': 0}
    assert recorder.calls[-1] == (scale.id, 'options', ())


def test_series_price_formatter_and_price_lines_handles(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    fmt = area.price_formatter()
    assert fmt.endswith('.priceFormatter')
    assert '"priceFormatter"' in chart.captured[-1]
    chart.captured.clear()
    arr = area.js_price_lines()
    assert arr.endswith('.priceLinesArray')
    assert '"priceLines"' in chart.captured[-1]


def test_series_update_historical_flag(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    point = pd.Series({'time': pd.Timestamp('2020-02-01'), 'value': 1.5})
    area.update(point, historical_update=True)
    assert chart.captured[-1].count('true') >= 1


def test_series_get_pane_returns_handle(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    pane = area.get_pane()
    assert pane.id.endswith('.paneHandle')
    assert '"getPane"' in chart.captured[-1]


def test_pane_element_series_move_to(chart):
    chart.captured.clear()
    elem = chart.pane_get_htmlelement(0)
    assert elem.endswith('.paneElement.0')
    assert '"getHTMLElement"' in chart.captured[-1]
    chart.captured.clear()
    series = chart.pane_series_handle(0)
    assert series.endswith('.paneSeries.0')
    assert '"getSeries"' in chart.captured[-1]
    chart.captured.clear()
    chart.pane_move_to(1, 0)
    assert '"moveTo"' in chart.captured[-1]


def test_visible_time_range_and_size_change_events(chart):
    chart.captured.clear()
    chart.events.visible_time_range_change += lambda c, frm, to: None
    script = '\n'.join(chart.captured)
    assert 'subscribeVisibleTimeRangeChange' in script
    chart.captured.clear()
    chart.events.visible_time_range_change.unsubscribe()
    assert 'unsubscribeVisibleTimeRangeChange' in '\n'.join(chart.captured)

    chart.captured.clear()
    chart.events.size_change += lambda c, w, h: None
    assert 'subscribeSizeChange' in '\n'.join(chart.captured)
    chart.captured.clear()
    chart.events.size_change.unsubscribe()
    assert 'unsubscribeSizeChange' in '\n'.join(chart.captured)


def test_subscribe_data_changed(chart):
    area = chart.create_area(name='close')
    seen = []
    chart.captured.clear()
    area.subscribe_data_changed(lambda series, scope: seen.append(scope))
    assert 'subscribeDataChanged' in '\n'.join(chart.captured)
    assert area._data_changed_name in chart.win.handlers
    # simulate a callback arriving from JS
    chart.win.handlers[area._data_changed_name]('update')
    assert seen == ['update']
    chart.captured.clear()
    area.unsubscribe_data_changed()
    assert 'unsubscribeDataChanged' in '\n'.join(chart.captured)
    assert area._data_changed_name is None


def test_constants_match_upstream():
    from pylightcharts import constants
    assert constants.ColorType.Solid.value == 'solid'
    assert int(constants.CrosshairMode.Magnet) == 1
    assert int(constants.LineStyle.Dashed) == 2
    assert int(constants.LineType.Curved) == 2
    assert int(constants.PriceScaleMode.Logarithmic) == 1
    assert int(constants.TickMarkType.TimeWithSeconds) == 4
    assert int(constants.MarkerSign.Negative) == -1
    assert constants.SeriesType.Candlestick.value == 'Candlestick'
    assert constants.VERSION == '5.2.1'


def test_vertical_span_uses_v5_primitive(chart):
    chart.captured.clear()
    span = chart.vertical_span('2020-01-03', '2020-01-10')
    script = '\n'.join(chart.captured)
    assert 'new Lib.VerticalSpan' in script
    assert 'addHistogramSeries' not in script
    assert 'attachPrimitive' in script
    assert 'filled: true' in script
    chart.captured.clear()
    span.delete()
    assert 'detach' in chart.captured[-1]


def test_vertical_span_list_draws_lines(chart):
    chart.captured.clear()
    chart.vertical_span(['2020-01-03', '2020-01-04', '2020-01-05'])
    script = '\n'.join(chart.captured)
    assert 'new Lib.VerticalSpan' in script
    assert 'filled: false' in script


def test_vertical_line_update_uses_time(chart):
    chart.captured.clear()
    line = chart.vertical_line('2020-01-05')
    line.update('2020-01-09')
    script = chart.captured[-1]
    assert 'updatePoints' in script
    assert 'price' not in script


# --------------------------------------------------------------------------
# Phase 2: v5 plugin lifecycle
# --------------------------------------------------------------------------

def test_series_markers_plugin(chart):
    from pylightcharts.plugins import SeriesMarkersPlugin
    area = chart.create_area(name='close')
    chart.captured.clear()
    plugin = area.markers_plugin()
    assert isinstance(plugin, SeriesMarkersPlugin)
    script = chart.captured[-1]
    assert 'setMarkers' in script and f'"{plugin.id}"' in script

    recorder = _Recorder([{'time': 1}])
    chart.win.invoke_get = recorder
    assert plugin.markers() == [{'time': 1}]
    assert recorder.calls[-1][1] == 'markers'

    chart.captured.clear()
    plugin.set_markers([{'time': 2}])
    assert '"setMarkers"' in chart.captured[-1]
    chart.captured.clear()
    plugin.apply_options(z_index=1)
    assert '"applyOptions"' in chart.captured[-1] and '"zIndex":1' in chart.captured[-1]
    chart.captured.clear()
    handle = plugin.get_series()
    assert handle.endswith('.series') and '"getSeries"' in chart.captured[-1]
    chart.captured.clear()
    plugin.detach()
    assert '"detach"' in chart.captured[-1]


def test_up_down_markers_plugin(chart):
    from pylightcharts.plugins import UpDownMarkersPlugin
    area = chart.create_area(name='close')
    chart.captured.clear()
    plugin = area.up_down_markers_plugin(positive_color='#0f0')
    assert isinstance(plugin, UpDownMarkersPlugin)
    assert plugin.id == f'{area.id}.upDownMarkers'
    assert '"createUpDownMarkers"' in chart.captured[-1]

    chart.captured.clear()
    plugin.set_data([{'time': 1, 'value': 1.0}])
    assert '"setData"' in chart.captured[-1]
    chart.captured.clear()
    plugin.update({'time': 2, 'value': 2.0}, historical_update=True)
    assert '"update"' in chart.captured[-1] and 'true' in chart.captured[-1]
    chart.captured.clear()
    # up/down markers use the plugin's own format: {time, value, sign}
    plugin.set_markers([{'time': 1, 'value': 1.5, 'sign': 1}])
    assert '"setMarkers"' in chart.captured[-1]
    assert '"value"' in chart.captured[-1] and '"sign"' in chart.captured[-1]
    chart.captured.clear()
    plugin.clear_markers()
    assert '"clearMarkers"' in chart.captured[-1]
    chart.captured.clear()
    plugin.apply_options(positive_color='#fff')
    assert '"applyOptions"' in chart.captured[-1]
    chart.captured.clear()
    plugin.detach()
    assert '"detach"' in chart.captured[-1]


def test_up_down_markers_need_a_line_or_area_series(chart):
    """The engine only supports Line/Area, and `chart.up_down_markers_plugin()`
    means the chart's own candlestick series - a common mistake."""
    with pytest.raises(ValueError, match='the chart itself'):
        chart.up_down_markers_plugin()

    hist = chart.create_histogram(name='volume')
    with pytest.raises(ValueError, match='Line or Area'):
        hist.up_down_markers_plugin()

    # the two supported types still work
    area = chart.create_area(name='close')
    assert area.up_down_markers_plugin().id == f'{area.id}.upDownMarkers'


def test_up_down_markers_reject_the_classic_marker_format(chart):
    """The engine ignores markers without a `value` (there is no price to draw
    at) and silently paints nothing, so the wrapper refuses them."""
    area = chart.create_area(name='close')
    plugin = area.up_down_markers_plugin(positive_color='#0f0')

    with pytest.raises(ValueError, match='series.marker'):
        plugin.set_markers([{'time': 1, 'position': 'aboveBar',
                             'shape': 'circle', 'color': '#f00'}])
    # the plugin's format goes through, `sign` is optional
    plugin.set_markers([{'time': 1, 'value': 1.5}])
    assert '"setMarkers"' in chart.captured[-1]


def test_text_watermark_plugin(chart):
    from pylightcharts.plugins import TextWatermarkPlugin
    chart.captured.clear()
    plugin = chart.text_watermark_plugin('hello', font_size=30, color='#fff')
    assert isinstance(plugin, TextWatermarkPlugin)
    script = chart.captured[-1]
    assert 'setWatermark' in script and f'"{plugin.id}"' in script
    # ★ 结尾必须补 null：setWatermark 返回活的 pane primitive，
    #   PyQt6 runJavaScript 转它的值会把渲染进程卡死（之后 JS 全部返回 None）✗
    assert script.rstrip().endswith('null')

    chart.captured.clear()
    plugin.apply_options(horz_align='left')
    assert '"applyOptions"' in chart.captured[-1]
    chart.captured.clear()
    pane = plugin.get_pane()
    assert pane.endswith('.pane') and '"getPane"' in chart.captured[-1]
    chart.captured.clear()
    plugin.detach()
    assert '"detach"' in chart.captured[-1]


def test_image_watermark_plugin(chart):
    from pylightcharts.plugins import ImageWatermarkPlugin
    chart.captured.clear()
    plugin = chart.image_watermark_plugin('data:image/png;base64,AAAA', max_width=100)
    assert isinstance(plugin, ImageWatermarkPlugin)
    script = chart.captured[-1]
    assert '"createImageWatermark"' in script
    assert plugin.id.endswith('.imageWatermark')


def test_pane_level_add_series(chart):
    chart.captured.clear()
    chart.pane_add_series(0, 'Line', name='pane_line')
    assert '"addSeries"' in '\n'.join(chart.captured)
    chart.captured.clear()
    chart.pane_add_custom_series(0, name='pane_custom')
    assert '"createCustomSeries"' in '\n'.join(chart.captured)


# --------------------------------------------------------------------------
# Phase 3: function-valued options (JS callbacks)
# --------------------------------------------------------------------------

def test_register_js_callback(chart):
    chart.captured.clear()
    chart.register_js_callback('vol', params=['price'],
                               body="return (price/1e6).toFixed(1)+'M'")
    script = chart.captured[-1]
    assert 'Lib.registerCallback("vol"' in script
    assert '["price"]' in script and '1e6' in script


def test_set_tick_mark_and_localization_callbacks(chart):
    chart.captured.clear()
    chart.set_tick_mark_formatter('tmf')
    script = chart.captured[-1]
    assert 'Lib.setOptionCallback' in script
    assert '"tickMarkFormatter"' in script and '"tmf"' in script
    chart.captured.clear()
    chart.set_price_formatter_callback('pf')
    assert '"localization.priceFormatter"' in chart.captured[-1]
    chart.captured.clear()
    chart.set_time_formatter_callback('tf')
    assert '"localization.timeFormatter"' in chart.captured[-1]


def test_series_price_format_and_autoscale_callbacks(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    area.set_price_format_formatter('sf')
    assert 'Lib.setPriceFormatFormatter' in chart.captured[-1]
    chart.captured.clear()
    area.set_autoscale_info_provider('ap')
    script = chart.captured[-1]
    assert '"autoscaleInfoProvider"' in script and '"ap"' in script


# --------------------------------------------------------------------------
# Phase 4: declarative primitives & custom series pane view
# --------------------------------------------------------------------------

def test_create_series_primitive(chart):
    from pylightcharts.primitives import SeriesPrimitive
    chart.captured.clear()
    prim = chart.create_series_primitive(
        {'paneViews': [{'draw': 'd', 'zOrder': 'top'}], 'hitTest': 'h'})
    assert isinstance(prim, SeriesPrimitive)
    script = chart.captured[-1]
    assert 'Lib.createSeriesPrimitive' in script
    assert '"paneViews"' in script and '"zOrder":"top"' in script

    area = chart.create_area(name='close')
    chart.captured.clear()
    prim.attach_to(area)
    script = chart.captured[-1]
    assert '"attachPrimitive"' in script and '"$ref":"' + prim.id + '"' in script
    chart.captured.clear()
    prim.request_update()
    assert '"requestUpdate"' in chart.captured[-1]
    chart.captured.clear()
    prim.apply_options(paneViews=[])
    assert '"applyOptions"' in chart.captured[-1]
    chart.captured.clear()
    prim.detach_from(area)
    assert '"detachPrimitive"' in chart.captured[-1]


def test_create_pane_primitive(chart):
    from pylightcharts.primitives import PanePrimitive
    chart.captured.clear()
    prim = chart.create_pane_primitive({'paneViews': [{'draw': 'd'}]})
    assert isinstance(prim, PanePrimitive)
    assert 'Lib.createPanePrimitive' in chart.captured[-1]
    chart.captured.clear()
    prim.attach_to(chart, 0)
    assert '"attachPrimitive"' in chart.captured[-1]
    chart.captured.clear()
    prim.detach_from(chart, 0)
    assert '"detachPrimitive"' in chart.captured[-1]


def test_custom_series_pane_view_spec(chart):
    chart.captured.clear()
    chart.add_custom_series(name='spec', spec={
        'rendererDraw': 'rd', 'rendererHitTest': 'rh',
        'priceValueBuilder': 'pvb', 'isWhitespace': 'iw',
        'defaultOptions': {'lastValueVisible': True},
    })
    script = chart.captured[-1]
    assert '"createCustomSeries"' in script
    assert 'rendererDraw' in script and 'pvb' in script and 'iw' in script


# --------------------------------------------------------------------------
# Phase 5: custom horizontal scale behavior (IHorzScaleBehavior)
# --------------------------------------------------------------------------

def test_register_horz_scale_behavior(chart):
    chart.captured.clear()
    chart.register_horz_scale_behavior('m', {
        'formatTickmark': (['tickMark', 'loc'], 'return String(tickMark)'),
        'formatHorzItem': 'myFmt',
    })
    script = '\n'.join(chart.captured)
    assert 'Lib.registerCallback' in script
    assert '__horz_m_formatTickmark' in script
    assert 'Lib.registerHorzScaleBehaviorSpec' in script
    assert '"formatHorzItem":"myFmt"' in script


def test_horz_scale_class_attributes():
    from pylightcharts.abstract import AbstractChart, Window
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True

    class MonthChart(AbstractChart):
        _horz_scale_name = 'month'
        _horz_scale = {'formatTickmark': ([], 'return String(1)')}

    c = MonthChart(window)
    script = '\n'.join(captured)
    assert c._chart_kind == 'custom:month'
    assert 'Lib.registerHorzScaleBehaviorSpec("month"' in script
    # registration must precede Handler creation
    assert script.index('registerHorzScaleBehaviorSpec') < script.index('new Lib.Handler')
    assert '"custom:month"' in script


def test_size_change_uses_width_height(chart):
    """Upstream `SizeChangeEventHandler = (width, height) => void`, not a size object."""
    chart.captured.clear()
    chart.events.size_change += lambda c, w, h: None
    script = '\n'.join(chart.captured)
    assert '(width, height) =>' in script
    assert 'size.width' not in script


def test_size_change_tolerates_missing_values(chart):
    """A callback carrying `undefined` must not raise (it used to crash show())."""
    seen = []
    chart.events.size_change += lambda c, w, h: seen.append((w, h))
    handler = chart.win.handlers[chart.events.size_change._name]
    handler('800', '600')
    handler('undefined', 'undefined')
    assert seen == [(800.0, 600.0), (None, None)]


def test_parse_event_message_ignores_unknown(chart):
    """A table cell without a callback used to send `null_~_...` and crash the loop."""
    from pylightcharts.util import parse_event_message
    func, args = parse_event_message(chart.win, 'null_~_1')
    assert func is None
    assert args == ['1']


def test_pane_series_count_uses_lookup(chart):
    """Pane handles end in `.N` (invalid raw JS), so count must go through Lib.lookup."""
    calls = []

    def fake_read_property(handle, path=None):
        calls.append((handle, path))
        return 3

    chart.win.read_property = fake_read_property
    assert chart.pane_series_count(1) == 3
    assert calls[-1][1] == 'getSeries().length'
    assert calls[-1][0].endswith('.pane.1')


def test_horizontal_span_uses_v5_primitive(chart):
    chart.captured.clear()
    span = chart.horizontal_span(98.0, 102.0)
    script = '\n'.join(chart.captured)
    assert 'new Lib.HorizontalSpan' in script
    assert '{price: 98.0}, {price: 102.0}' in script
    assert 'filled: true' in script
    assert 'attachPrimitive' in script
    chart.captured.clear()
    span.delete()
    assert 'detach' in chart.captured[-1]


def test_span_delete_is_safe_after_series_deleted(chart):
    """主题切换时先删了指标线，再删水平线不能去 detach 一个已死的 series。"""
    series = chart.create_line(name='cci')
    span = series.horizontal_span(0.0, filled=False)
    other = series.horizontal_span(-100.0, filled=False)
    series.delete()                            # 指标线先没了
    chart.captured.clear()
    span.delete()
    other.delete()
    assert not any('detachPrimitive' in script for script in chart.captured)


def test_horizontal_span_single_price_draws_lines(chart):
    chart.captured.clear()
    chart.horizontal_span([98.0, 102.0], line_color='#FFFFFF')
    script = '\n'.join(chart.captured)
    assert 'new Lib.HorizontalSpan' in script
    assert 'filled: false' in script
    assert "lineColor: '#FFFFFF'" in script


def test_horizontal_span_can_move_and_restyle(chart):
    span = chart.horizontal_span(98.0, 102.0, autoscale=True)
    assert 'autoscale: true' in '\n'.join(chart.captured)
    chart.captured.clear()
    span.set_prices(90.0, 110.0)
    assert '"setPrices"' in chart.captured[-1]
    assert '"price":90.0' in chart.captured[-1]
    chart.captured.clear()
    span.apply_options(fill_color='rgba(239, 83, 80, 0.3)', line_width=2)
    script = chart.captured[-1]
    assert '"fillColor":"rgba(239, 83, 80, 0.3)"' in script
    assert '"lineWidth":2' in script


def test_horizontal_span_apply_options_converts_the_style(chart):
    """A raw 'dashed' string used to reach setLineStyle() and make
    ctx.setLineDash() throw, which aborted the whole frame."""
    span = chart.horizontal_span(98.0, 102.0)
    chart.captured.clear()
    span.apply_options(line_width=2, line_style='dashed')
    script = chart.captured[-1]
    assert '"lineStyle":2' in script        # LINE_STYLE['dashed'] == 2
    assert '"dashed"' not in script
    assert '"lineWidth":2' in script


def test_horizontal_span_works_on_a_series_too(chart):
    line = chart.create_line(name='close')
    chart.captured.clear()
    line.horizontal_span(100.0, 105.0)
    script = '\n'.join(chart.captured)
    assert 'new Lib.HorizontalSpan' in script
    assert f'{line.id}.series.attachPrimitive' in script


def test_fill_between_uses_the_other_series_handle(chart):
    upper = chart.create_line(name='close', color='#00BCD4')
    lower = chart.create_line(name='close')
    chart.captured.clear()
    band = chart.fill_between(upper, lower, color='rgba(0, 200, 255, 0.4)')
    script = '\n'.join(chart.captured)
    assert 'new Lib.LineFill' in script
    assert f'"{lower.id}.series"' in script
    assert f'{upper.id}.series.attachPrimitive' in script
    assert "fillColor: 'rgba(0, 200, 255, 0.4)'" in script
    chart.captured.clear()
    band.delete()
    assert 'detach' in chart.captured[-1]


def test_fill_between_works_from_either_side(chart):
    upper = chart.create_line(name='close')
    lower = chart.create_line(name='close')
    chart.captured.clear()
    upper.fill_between(lower)                     # on one of the two series
    assert f'"{lower.id}.series"' in '\n'.join(chart.captured)
    chart.captured.clear()
    chart.fill_between(upper, lower)              # or on the chart
    assert f'"{lower.id}.series"' in '\n'.join(chart.captured)


def test_fill_between_rejects_non_series(chart):
    line = chart.create_line(name='close')
    with pytest.raises(TypeError, match='two series'):
        chart.fill_between(line, 'not-a-series')


def test_fill_between_apply_options_converts_the_style(chart):
    upper = chart.create_line(name='close')
    lower = chart.create_line(name='close')
    band = chart.fill_between(upper, lower)
    chart.captured.clear()
    band.apply_options(fill_color='rgba(239, 83, 80, 0.3)',
                       line_color='#FFFFFF', line_style='dotted')
    script = chart.captured[-1]
    assert '"lineStyle":1' in script         # LINE_STYLE['dotted'] == 1
    assert '"dotted"' not in script
    assert '"lineColor":"#FFFFFF"' in script
    assert '"fillColor":"rgba(239, 83, 80, 0.3)"' in script


def test_bands_accept_an_opacity(chart):
    chart.captured.clear()
    chart.horizontal_span(98.0, 102.0, color='#7E57C2', opacity=0.35)
    assert "fillColor: '#7E57C2'" in chart.captured[-1]
    assert 'opacity: 0.35' in chart.captured[-1]
    chart.captured.clear()
    chart.horizontal_span(98.0, 102.0, opacity=None)   # colour's own alpha
    assert 'opacity: null' in chart.captured[-1]

    upper = chart.create_line(name='close')
    lower = chart.create_line(name='close')
    chart.captured.clear()
    chart.fill_between(upper, lower, opacity=0.5)
    assert 'opacity: 0.5' in chart.captured[-1]

    chart.captured.clear()
    chart.vertical_span('2020-01-03', '2020-01-10', opacity=0.4)
    assert 'opacity: 0.4' in chart.captured[-1]


def test_pane_separator_styles_layout_panes(chart):
    """The divider colour is `layout.panes.separatorColor` (white by default)."""
    chart.captured.clear()
    chart.pane_separator(color='#2A2E39', hover_color='#363A45',
                         enable_resize=False)
    script = chart.captured[-1]
    assert '"applyOptions"' in script
    assert '"separatorColor":"#2A2E39"' in script
    assert '"separatorHoverColor":"#363A45"' in script
    assert '"enableResize":false' in script


def test_horizontal_span_filled_flag(chart):
    """`filled` forces band vs lines (auto: band when `high` is given)."""
    chart.captured.clear()
    chart.horizontal_span(98.0, 108.0, filled=False)
    assert 'filled: false' in chart.captured[-1]
    chart.captured.clear()
    chart.horizontal_span([95.0, 100.0, 105.0], filled=True)
    assert 'filled: true' in chart.captured[-1]


def test_horizontal_span_can_target_a_pane(chart):
    """`pane_index=` anchors the band to the first series created in that pane."""
    chart.add_pane()
    osc = chart.add_series('Line', name='close', pane_index=2, color='#26A69A')
    chart.captured.clear()
    chart.horizontal_span(2.0, 6.0, pane_index=2)
    script = chart.captured[-1]
    assert f'{osc.id}.series.attachPrimitive' in script
    assert '{price: 2.0}, {price: 6.0}' in script

    empty = chart.add_pane()
    with pytest.raises(ValueError, match='no series yet'):
        chart.horizontal_span(1.0, 2.0, pane_index=empty)


def test_series_remembers_its_pane(chart):
    """`_pane_index` powers `pane_index=` and must follow `move_to_pane`."""
    chart.add_pane()
    series = chart.add_series('Line', name='close', pane_index=2)
    assert chart._pane_series(2) is series
    assert chart._pane_series(0) is chart            # pane 0 = the chart itself
    series.move_to_pane(3)
    assert chart._pane_series(3) is series


def test_legend_settings_and_toggle_helpers(chart):
    """Series helpers the indicator card drives: style/hide/price flags."""
    line = chart.create_line('ma', color='#FF9800', width=2)
    chart.captured.clear()

    line.set_line_width(4)
    assert '"lineWidth"' in chart.captured[-1] and '4' in chart.captured[-1]
    line.set_line_color('#123456')
    assert '"color"' in chart.captured[-1] and '#123456' in chart.captured[-1]
    line.set_line_style('dashed')
    assert '"lineStyle"' in chart.captured[-1]
    line.set_price_visible('price_label', False)
    assert '"lastValueVisible"' in chart.captured[-1]
    line.set_price_visible('price_line', False)
    assert '"priceLineVisible"' in chart.captured[-1]

    assert line.is_visible() is True
    line.hide_data()
    assert line.is_visible() is False
    line.show_data()
    assert line.is_visible() is True


def test_legend_settings_dispatches_by_series_id(chart):
    """One callback name per chart: the gear must open the series it belongs to."""
    line_a = chart.create_line('a')
    line_b = chart.create_line('b')
    seen = []
    line_a.enable_legend_settings(lambda s, x, y: seen.append((s.name, x, y)))
    line_b.enable_legend_settings(lambda s, x, y: seen.append((s.name, x, y)))

    handler = chart.win.handlers[f'legend_settings{chart.id}']
    handler(line_a.id, '10', '20')
    handler(line_b.id, '30', '40')
    assert seen == [('a', '10', '20'), ('b', '30', '40')]
