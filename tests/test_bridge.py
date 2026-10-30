"""Regression tests for the generic Python -> JS bridge (Phase 1).

These run without a browser: a fake `Window` records every script that would
have been sent to the webview, so we can assert on the generated JS.
"""
import inspect
import json

import pandas as pd
import pytest

from pylightcharts.abstract import AbstractChart, Baseline, Window
from pylightcharts.util import js_call, js_data, js_value, snake_to_camel


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True  # run scripts straight into the capture list
    chart = AbstractChart(window)
    chart.captured = captured
    captured.clear()
    return chart


# --------------------------------------------------------------------------
# serializer
# --------------------------------------------------------------------------

def test_js_value_camelizes_keys_and_drops_none():
    out = js_value({'line_color': 'red', 'line_width': 2, 'price_scale_id': None,
                    'nested_opt': {'scale_margin_top': 0.1}})
    assert json.loads(out) == {'lineColor': 'red', 'lineWidth': 2,
                               'nestedOpt': {'scaleMarginTop': 0.1}}


def test_js_value_handles_numpy_and_nan():
    import numpy as np
    out = js_value({'a': np.int64(5), 'b': np.float64(1.5), 'c': float('nan')})
    assert json.loads(out) == {'a': 5, 'b': 1.5}


def test_js_data_is_compact_and_drops_nan():
    df = pd.DataFrame({'time': [1, 2], 'close': [1.5, float('nan')]})
    out = js_data(df)
    assert '\n' not in out and '  ' not in out          # no pretty printing
    assert json.loads(out) == [{'time': 1, 'close': 1.5}, {'time': 2}]


def test_js_call_shape():
    out = js_call('window.ab', 'applyOptions', [{'line_width': 2}])
    assert out == 'Lib.invoke("window.ab", "applyOptions", [{"lineWidth":2}])'


# --------------------------------------------------------------------------
# chart chrome
# --------------------------------------------------------------------------

def test_on_js_load_evaluates_each_script_separately():
    """One failing script must not swallow the rest of the setup.

    The scripts used to be concatenated into one ``evaluate_js`` call, so the
    first error (e.g. an undefined DOM node) aborted every later statement,
    and the message only showed the head of the whole batch.
    """
    calls = []
    window = Window(script_func=calls.append)
    window._return_q = None                 # skip the readyState probe
    window.run_script('first();')
    window.run_script('second();')
    window.run_script('last();', run_last=True)

    window.on_js_load()

    assert calls == ['first();', 'second();', 'last();']


def test_layout_does_not_assume_a_container_element(chart):
    chart.layout(background_color='#0b0e14')
    script = chart.captured[-2]
    assert 'document.getElementById("container") || document.body' in script
    assert "getElementById('container').style" not in script


def test_spinner_goes_through_the_handler_method(chart):
    """Regression: the spinner element only exists in JS, so poking ``.style``
    from python threw "Cannot read properties of undefined" and killed the rest
    of the initial script (no data, no hotkeys)."""
    chart.spinner(True)
    shown = chart.captured[-1]
    chart.spinner(False)
    hidden = chart.captured[-1]

    for script, expected in ((shown, '[true]'), (hidden, '[false]')):
        assert 'Lib.invoke' in script
        assert '"setSpinner"' in script
        assert expected in script
    assert not any('.spinner.style' in script for script in chart.captured)


# --------------------------------------------------------------------------
# generic series creation
# --------------------------------------------------------------------------

@pytest.mark.parametrize('kind,method', [
    ('Area', 'create_area'),
    ('Bar', 'create_bar'),
    ('Baseline', 'create_baseline'),
])
def test_create_series_goes_through_bridge(chart, kind, method):
    getattr(chart, method)(name='close')

    script = chart.captured[-1]
    assert script.startswith('window.')
    assert 'Lib.invoke' in script
    assert '"addSeries"' in script
    assert f'"{kind}"' in script


def test_add_series_generic_kind(chart):
    series = chart.add_series('Baseline', name='close', base_value=50, top_line_color='#0f0')
    script = chart.captured[-1]
    assert '"Baseline"' in script
    assert '"topLineColor"' in script      # snake_case -> camelCase
    assert '"baseValue"' in script


def test_area_data_reuses_series_handle(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    area.set(pd.DataFrame({'time': pd.date_range('2024-01-01', periods=2),
                           'open': [1.0, 2.0], 'high': [2, 3], 'low': [0.5, 1.5], 'close': [1.5, 2.5]}))
    script = chart.captured[-1]
    assert script.startswith(f'{area.id}.series.setData(')


# --------------------------------------------------------------------------
# legend visibility toggle (the eye in the top-left legend rows)
# --------------------------------------------------------------------------

def _add_series_args(script: str) -> list:
    """The JSON argument list of the ``addSeries`` call in `script`."""
    payload = script.split('"addSeries", ', 1)[1]
    payload = payload.rsplit('])', 1)[0] + ']'
    return json.loads(payload)


def test_create_line_shows_the_legend_toggle_by_default(chart):
    chart.create_line(name='close')
    assert ',\n                true\n' in chart.captured[-1]


def test_create_line_can_hide_the_legend_toggle(chart):
    chart.create_line(name='close', legend_toggle=False)
    assert ',\n                false\n' in chart.captured[-1]


def test_create_histogram_can_hide_the_legend_toggle(chart):
    chart.create_histogram(name='volume', legend_toggle=False)
    script = chart.captured[-1]
    assert 'createHistogramSeries' in script
    assert 'false' in script.split('priceFormat')[1]


@pytest.mark.parametrize('method,kind', [
    ('create_area', 'Area'),
    ('create_bar', 'Bar'),
    ('create_baseline', 'Baseline'),
])
def test_create_series_forwards_legend_toggle(chart, method, kind):
    getattr(chart, method)(name='close', legend_toggle=False)
    args = _add_series_args(chart.captured[-1])
    assert args[0] == kind
    assert args[-1] is False


def test_add_series_forwards_legend_toggle(chart):
    chart.add_series('Line', name='close', legend_toggle=False)
    assert _add_series_args(chart.captured[-1])[-1] is False
    chart.add_series('Line', name='close')
    assert _add_series_args(chart.captured[-1])[-1] is True


def test_add_custom_series_forwards_legend_toggle(chart):
    chart.add_custom_series('range', legend_toggle=False)
    script = chart.captured[-1]
    assert 'createCustomSeries' in script
    # 末尾多一个 `null` 终结符：PyQt 的 runJavaScript 会转换脚本最后一个表达式的
    # 值，而"活的" LWC 序列对象转换时会卡死渲染进程（见 util._invoke_assign ✓）
    assert script.rstrip().endswith('false])\nnull')


def test_indicator_series_inherit_legend_toggle(chart):
    """`add_sma(legend_toggle=False)` must reach the created bridge series."""
    df = pd.DataFrame({'time': pd.date_range('2024-01-01', periods=30,
                                             freq='D'),
                       'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
                       'volume': 10})
    chart.set(df)
    chart.captured.clear()
    chart.add_sma(length=5, legend_toggle=False)
    script = next(s for s in reversed(chart.captured) if '"addSeries"' in s)
    assert _add_series_args(script)[-1] is False
    chart.captured.clear()
    chart.add_sma(length=5)
    script = next(s for s in reversed(chart.captured) if '"addSeries"' in s)
    assert _add_series_args(script)[-1] is True


# --------------------------------------------------------------------------
# migrated methods
# --------------------------------------------------------------------------

def test_series_apply_options_via_bridge(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    area.style(line_width=5)
    script = chart.captured[-1]
    assert f'Lib.invoke("{area.id}.series", "applyOptions"' in script
    assert '"lineWidth":5' in script


def test_delete_uses_remove_series(chart):
    area = chart.create_area(name='close')
    chart.captured.clear()
    area.delete()
    assert any('"removeSeries"' in s for s in chart.captured)


def test_histogram_scale_via_bridge(chart):
    hist = chart.create_histogram(name='volume')
    chart.captured.clear()
    hist.scale(0.1, 0.2)
    script = chart.captured[-1]
    assert f'Lib.invoke("{hist.id}.priceScale", "applyOptions"' in script
    assert '"scaleMargins"' in script


# --------------------------------------------------------------------------
# legend rows (the `legend=` flag) and the baseline default
# --------------------------------------------------------------------------

def test_create_baseline_legend_row_is_optional(chart):
    """A baseline is a reference line: `legend=False` keeps it (and its eye) out of
    the legend so it cannot be confused with the indicator rows."""
    chart.create_baseline(name='base', base_value=100, legend=False)
    # 名字**照常传下去**（数据列映射要用）；图例行是建完之后**摘掉**的 ✓
    assert _add_series_args(chart.captured[-2])[1] == 'base'
    assert 'removeChild' in chart.captured[-1]
    chart.create_baseline(name='base', base_value=100)
    assert _add_series_args(chart.captured[-1])[1] == 'base'
    # every series type behaves the same way by default
    assert inspect.signature(Baseline.__init__).parameters['legend'].default is True
    assert (inspect.signature(AbstractChart.create_baseline)
            .parameters['legend'].default is True)


def test_add_series_can_skip_the_legend_row(chart):
    chart.add_series('Baseline', name='base', legend=False)
    assert _add_series_args(chart.captured[-2])[1] == 'base'
    assert 'removeChild' in chart.captured[-1]
    chart.add_series('Line', name='ma', legend=False)
    assert _add_series_args(chart.captured[-2])[1] == 'ma'
    assert 'removeChild' in chart.captured[-1]


def test_create_line_can_skip_the_legend_row(chart):
    chart.create_line(name='ma', legend=False)
    # 真名字照给（列映射），图例行随后摘掉 ✓
    assert 'createLineSeries(' in chart.captured[-2]
    assert '"ma"' in chart.captured[-2]
    assert 'removeChild' in chart.captured[-1]


def test_create_histogram_can_skip_the_legend_row(chart):
    chart.create_histogram(name='vol', legend=False)
    assert 'createHistogramSeries(' in chart.captured[-2]
    assert '"vol"' in chart.captured[-2]
    assert 'removeChild' in chart.captured[-1]


def test_series_creation_creates_missing_panes(chart):
    """The engine clamps an out-of-range paneIndex to panes.length, so a series
    asked for pane 5 used to land in the last existing pane (3) instead."""
    chart.add_series('Line', name='ma', pane_index=5)
    assert chart.pane_count() == 6
    assert sum('"addPane"' in script for script in chart.captured) == 5
    assert _add_series_args(chart.captured[-1])[4] == 5


def test_baseline_accepts_a_scalar_base_value(chart):
    """The engine reads `baseValue.price`; a bare number made its gradient stops
    non-finite, so the baseline existed (hover worked) but was never drawn."""
    from pylightcharts.abstract import _normalize_base_value

    assert _normalize_base_value('Line', {'base_value': 1}) == {'base_value': 1}
    assert _normalize_base_value('Baseline', {'base_value': 1}) == {
        'base_value': {'type': 'price', 'price': 1.0}}
    assert _normalize_base_value('Baseline', {'baseValue': 2.5}) == {
        'baseValue': {'type': 'price', 'price': 2.5}}
    engine_shape = {'type': 'price', 'price': 3}
    assert _normalize_base_value('Baseline', {'base_value': engine_shape}) == {
        'base_value': engine_shape}

    chart.add_series('Baseline', name='base', base_value=103.5)
    assert '"baseValue":{"type":"price","price":103.5}' in chart.captured[-1]

    series = chart.add_series('Baseline', name='base')
    chart.captured.clear()
    series.apply_options(base_value=5)
    assert '"baseValue":{"type":"price","price":5.0}' in chart.captured[-1]


def test_add_series_resolves_the_new_pane(chart):
    """`pane_index='new'` used to reach the engine as the string 'new'
    ("Assertion failed: Index should be greater or equal to 0")."""
    chart.add_series('Line', name='x', pane_index='new')
    assert _add_series_args(chart.captured[-1])[4] == 1
    assert sum('"addPane"' in script for script in chart.captured) == 1
    chart.captured.clear()
    chart.create_area(name='close', pane_index='new')
    assert _add_series_args(chart.captured[-1])[4] == 2


def test_conditional_colours_travel_with_the_data(chart):
    """Per-point `color` / `borderColor` / `wickColor` columns must reach the
    engine with their camelCase key names."""
    df = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=4, freq='D'),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
    })
    df['color'] = ['#26a69a', '#ef5350', '#26a69a', '#ef5350']
    df['borderColor'] = df['color']
    df['wickColor'] = df['color']

    chart.captured.clear()
    chart.set(df)                                  # main candles
    script = '\n'.join(chart.captured)
    assert '"color":"#26a69a"' in script
    assert '"borderColor":"#ef5350"' in script
    assert '"wickColor":"#ef5350"' in script

    line = chart.create_line(name='close')
    chart.captured.clear()
    line.set(df[['time', 'close', 'color']])       # any series with a value column
    assert '"value":1.5,"color":"#ef5350"' in chart.captured[-1]


def test_delete_passes_the_series_as_a_reference(chart):
    """`removeSeries` must receive the wrapper *object*: with a plain handle
    string the JS side bails out early, so the series and its legend row (swatch,
    name, eye) stayed on the chart."""
    series_list = [
        chart.create_line(name='close'),
        chart.create_histogram(name='volume'),
        chart.add_series('Line', name='ma'),
    ]
    for series in series_list:
        chart.captured.clear()
        series.delete()
        script = '\n'.join(chart.captured)
        assert '"removeSeries"' in script
        assert f'{{"$ref":"{series.id}"}}' in script, script
        assert f'["{series.id}"]' not in script, script   # the old, broken form
        assert series not in chart._lines


def test_numeric_times_are_unit_inferred(chart):
    """`_single_datetime_format` accepts seconds / ms / ns / datetime / string.

    The chart's own `time` column is epoch **seconds**, which used to be read as
    milliseconds: `chart.marker(time=int(epoch))` landed in 1970 (and was drawn
    nowhere), while the raw bridge paths (`update_raw`, `set`) were fine.
    """
    frame = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=30, freq='D'),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
    })
    chart.set(frame)
    seconds = int(chart.candle_data['time'].iloc[5])

    for value in (seconds, seconds * 1000, seconds * 10 ** 9,
                  pd.Timestamp('2024-01-06'), '2024-01-06'):
        assert chart._single_datetime_format(value) == seconds

    # ... and a marker created with epoch seconds lands on the right bar
    chart.captured.clear()
    chart.marker(time=seconds, position='above', shape='circle', color='#fff')
    assert f'"time": {seconds}' in chart.captured[-1]


def test_line_breaks_at_nan_gaps(chart):
    """`[1, 2, 3, nan, nan, 6, 7, 8]` 必须画成**两段**。

    LWC v5 的 whitespace 只延长时间轴、**不会断线**（用纯引擎渲染验证过），
    所以断开由 pylightcharts 自己做：主序列 `lineVisible:false`，每段再画一条
    同款、不进图例、不带价格标签的 Line 序列。
    """
    frame = pd.DataFrame({
        'time': pd.bdate_range('2024-01-01', periods=8),
        'close': [1.0, 2.0, 3.0, float('nan'), float('nan'), 6.0, 7.0, 8.0],
    })
    line = chart.add_series('Line', name='close')
    line.set(frame)

    scripts = ' '.join(chart.captured)
    assert 'lineVisible: false' in scripts          # 主序列让位
    assert scripts.count('setData') == 3            # 主序列 + 两段
    # `_invoke_assign` 末尾的 `null` 是脚本结果终结符（不是数据里的 null），
    # 先去掉再断言：数据里的缺失值必须省略键，不能写成 NaN / null ✓
    payload = scripts.replace('\nnull', '')
    assert 'NaN' not in payload and 'null' not in payload
    # 分段要挂到主序列上：图例的眼睛只对主序列 applyOptions，不带上它们
    # 的话，点了眼睛线还是一段一段留在图上。
    assert f'{line.id}.series.__gapSegments = [' in scripts


def test_line_without_gaps_is_untouched(chart):
    """没有 NaN 时一次都不分段（常态零开销）。"""
    frame = pd.DataFrame({'time': pd.bdate_range('2024-01-01', periods=4),
                          'close': [1.0, 2.0, 3.0, 4.0]})
    line = chart.add_series('Line', name='close')
    line.set(frame)

    scripts = ' '.join(chart.captured)
    assert 'lineVisible' not in scripts
    assert '__gapSegments' not in scripts          # 没有分段就不该有这个链接
    assert scripts.count('setData') == 1


def test_line_with_fragmented_nan_is_not_split(chart):
    """逐 bar 交替 NaN 的线（色带边界那种）不拆段。

    否则 400 根就会造出 200 个内部序列，每个一次 addSeries + setData +
    一次浏览器重绘 —— 表现就是"指标线分好几组先后出现 + 加载慢"。
    """
    n = 400
    values = [1.0 if i % 2 == 0 else float('nan') for i in range(n)]
    frame = pd.DataFrame({'time': pd.bdate_range('2024-01-01', periods=n),
                          'fill_up_low': values})
    line = chart.add_series('Line', name='fill_up_low')
    line.set(frame)

    scripts = ' '.join(chart.captured)
    assert 'lineVisible' not in scripts          # 不拆：主序列照常画
    assert '__gapSegments' not in scripts
    assert scripts.count('setData') == 1
