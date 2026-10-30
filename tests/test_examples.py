"""Regression tests for the API-tour examples (the docs' source of truth).

Only the generated JS is asserted, so these run without a browser.
"""
import base64
import importlib.util
import io
import json
import pathlib
import re

import numpy as np
import pytest
from PIL import Image

from pylightcharts.headless import HeadlessChart

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOUR = ROOT / 'examples' / '11_api_tour'


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOUR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_series_types_keeps_volume_on_its_own_scale():
    """A histogram from the generic bridge must not join the pane scale.

    ``add_series('Histogram', ...)`` follows the engine default
    (``priceScaleId: 'right'``), so volume (~5e4) shared one axis with the
    baselines (~100): pane 2 stretched to 0..50000 and flattened every price
    series in it.
    """
    module = _load('tour02', '02_series_types.py')
    chart = HeadlessChart(width=1100, height=800)
    module.build(chart)
    js = chart.to_scripts()

    calls = [line for line in js.splitlines()
             if 'addSeries' in line and '"Histogram"' in line]

    def title(call: str) -> str:
        """系列名（`addSeries("Histogram", "<name>", ...)` 的第二个参数）。

        不能用 `'osc' in call`：句柄是 `window.<名><随机后缀>`，随机后缀里刚好
        出现 "osc" 的行（例如 volume 那条）会被误判 —— 这个测试以前会随机失败。
        """
        found = re.search(r'"Histogram"\s*,\s*"([^"]*)"', call)
        return found.group(1) if found else ''

    volume = [line for line in calls if title(line).startswith('volume')]
    assert volume, 'example 02 should still demo a volume histogram'
    for call in volume:
        assert '"priceScaleId"' in call, call

    # the conditional-colour oscillator histogram intentionally shares its pane's
    # scale with the oscillator line (both hover around zero)
    osc = [line for line in calls if title(line).startswith('osc')]
    assert osc, 'the conditional-colour pane should still be there'
    for call in osc:
        assert '"priceScaleId"' not in call, call

    # create_histogram does this for the caller (own scale id, volume format)
    assert '"priceFormat":{"type":"volume"}' in js


def test_series_types_demos_conditional_colours():
    """Per-point colours ride along with the data (`color` column)."""
    module = _load('tour02', '02_series_types.py')
    chart = HeadlessChart(width=1100, height=800)
    module.build(chart)
    js = chart.to_scripts()

    # oscillator histogram red/green and line blue/orange, once per data point
    assert js.count('"color":"#26A69A"') > 50
    assert js.count('"color":"#EF5350"') > 50
    assert js.count('"color":"#2962FF"') > 50
    assert js.count('"color":"#FF9800"') > 50


def test_series_types_uses_distinct_legend_labels():
    """Every legend row must be identifiable: no more five rows called 'close'.

    The name doubles as the value column, so a distinct label needs its own
    column too - `make_data` adds them.
    """
    module = _load('tour02', '02_series_types.py')
    chart = HeadlessChart(width=1100, height=800)
    module.build(chart)
    js = chart.to_scripts()

    names = re.findall(r'create(?:Line|Histogram)Series\(\s*"([^"]*)"', js)
    for line in js.splitlines():
        if '"addSeries"' in line:
            payload = line.split('"addSeries", ', 1)[1]
            payload = payload.rsplit('])', 1)[0] + ']'
            names.append(json.loads(payload)[1])
    labels = [name for name in names if name]

    assert labels, 'expected legend-labelled series in example 02'
    assert len(labels) == len(set(labels)), f'duplicate labels: {labels}'
    assert labels.count('close') <= 1, labels
    # every row must answer its own eye: the count of rows with a legend label has
    # to match the number of eyes minus the rows explicitly created without one
    assert len(labels) >= 4, labels


def test_multi_chart_layout_page_topbar_and_menu():
    """Example 14: one page-level bar on top, a layout menu that splits it.

    Everything asserted here is a pylightcharts extension: Lightweight Charts
    has neither a window-spanning top bar nor several charts sharing a page.
    """
    module = _load('tour14', '14_multi_chart_layout.py')
    chart = HeadlessChart(width=1200, height=760)
    module.build(chart)
    js = chart.to_scripts()

    # the bar belongs to the window, not to a chart (no per-chart top bar)
    assert 'Lib.createPageTopBar()' in js
    assert 'createTopBar()' not in js
    # left: timeframe switcher + indicators button; right: layout menu + button
    assert 'makeSwitcher' in js and 'makeMenu' in js
    assert js.count('makeButton') >= 2
    assert "'上下布局', '左右布局'" in js and '"布局"' in js
    # the page bar has no title / symbol
    assert 'makeTextBoxWidget' not in js

    win = chart.win
    layout = win.layout
    assert len(layout.charts) == 1        # one chart to start with
    # the charts are separated by a draggable gap (its width is the example's
    # own choice - see `Layout.set_divider`)
    assert layout.divider is True and layout.divider_size > 0
    # periods / symbols stay independent
    assert 'syncCharts' not in js

    bar = win.page_topbar()
    before = len(chart.to_scripts())

    # what the JS does on a menu click: dispatch the widget's callback
    win.handlers[bar['layout'].id]('上下布局')
    assert layout.kind == 'vertical'
    assert [(c._width, c._height) for c in layout.charts] == [
        (1.0, 0.5), (1.0, 0.5)]

    win.handlers[bar['layout'].id]('左右布局')
    assert [(c._width, c._height) for c in layout.charts] == [
        (0.5, 1.0), (0.5, 1.0)]

    # the chart the layout created was fed by Layout.on_create
    assert 'setData' in chart.to_scripts()[before:]

    # the other buttons only log, so they must not touch the layout
    win.handlers[bar['timeframe'].id]('4H')
    win.handlers[bar['indicators'].id]('指标')
    assert bar['timeframe'].value == '4H'
    assert layout.kind == 'horizontal'


def test_indicators_example_turns_the_legend_on():
    """Example 07 is a tour of the indicators: every row needs a label.

    The legend is off by default (lightweight-charts-python behaviour), so a
    chart with 35 indicator series and no `chart.legend(...)` call shows no
    labels at all - nothing but the chart.
    """
    module = _load('tour07', '07_indicators.py')
    chart = HeadlessChart(width=1100, height=800)
    module.build(chart)
    js = chart.to_scripts()

    # rows and the OHLC block are both gated by the mode flags
    assert '.legend.linesEnabled = true' in js
    assert '.legend.ohlcEnabled = true' in js
    assert '.legend.div.style.display = \'flex\'' in js

    # `add_*` names the series itself, and that name is what the row shows
    for label in ('SMA 20', 'EMA 50', 'WMA 30', 'BB upper 20', 'DC lower 20',
                  'VWAP', 'KC middle 20', 'RSI 14', 'MACD 12,26',
                  'MACD signal 9', 'MACD histogram', '%K 14', '%D 3',
                  'ATR 14', 'OBV', 'ROC 12', '%R 14', 'CCI 20', 'MFI 14',
                  'ADX 14', '+DI 14', '-DI 14', 'raw SMA 60', 'H-L range',
                  'raw EMA 60'):
        assert f'"{label}"' in js, label

    # every series of the tour is named (an empty name = no legend row)
    names = re.findall(r'"addSeries",\s*\["[^"]*",\s*"([^"]*)"', js)
    assert len(names) == js.count('"addSeries"')
    assert names and all(names), names


@pytest.mark.parametrize('filename', [
    '05_drawings.py', '06_panes.py', '07_indicators.py',
    '08_custom_series.py', '09_plugins.py', '10_primitives.py',
    '11_callbacks.py',
])
def test_tour_examples_enable_the_legend(filename):
    """A chart without `chart.legend(...)` shows no labels at all.

    The legend (and with it every series/indicator row) is off by default -
    `lightweight-charts-python` behaviour - so each tour example has to turn it
    on. Example 12 is a numeric-axis chart and has no legend object at all.
    """
    module = _load('tour' + filename[:2], filename)
    chart = HeadlessChart(width=1100, height=800)
    module.build(chart)
    js = chart.to_scripts()

    assert '.legend.linesEnabled = true' in js, filename
    assert '.legend.div.style.display' in js, filename


def test_custom_series_example_colours_every_legend_row():
    """A custom series' `color` only feeds the legend swatch (its real colours
    live inside the shapes), so the tour sets it to each series' main color
    - otherwise all five rows show the same default blue."""
    module = _load('tour08', '08_custom_series.py')
    chart = HeadlessChart(width=1200, height=950)
    module.build(chart)
    js = chart.to_scripts()

    calls = [line for line in js.splitlines()
             if '"createCustomSeries"' in line]
    assert len(calls) == 5, len(calls)
    for line in calls:
        assert '"color"' in line, line

    for colour in ('#2962FF', '#FF5252', '#FFB300', '#26A69A', '#7E57C2'):
        assert f'"{colour}"' in js, colour

    # the box plot's shapes use the same amber as its legend swatch (whiskers
    # lines repeat it on every row, so it shows up far more than once)
    assert js.count('"color":"#FFB300"') > 100
    # the spec paneView draws with the purple its swatch advertises
    assert "ctx.fillStyle = '#7E57C2'" in js


def test_plugins_example_logo_is_a_visible_png():
    """The image watermark paints the image's pixels.

    A fully transparent (or broken / mis-split base64) data URI draws nothing
    all and the engine reports no error, so the failure looks exactly like a
    plugin that does not work. Example 09 must ship an image you can see.
    """
    module = _load('tour09', '09_plugins.py')
    payload = module.LOGO_PNG.split(',', 1)[1]
    data = base64.b64decode(payload)

    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'it must hold a real PNG'
    image = Image.open(io.BytesIO(data)).convert('RGBA')
    pixels = np.asarray(image)                       # (height, width, 4)
    assert pixels[..., 3].min() == 255, 'the logo is transparent'
    colours = np.unique(pixels[..., :3].reshape(-1, 3), axis=0)
    assert len(colours) > 1, 'the logo is a flat pixel'


def test_plugins_example_uses_the_updown_marker_format():
    """Up/down markers are `{time, value, sign}`, not the classic one."""
    module = _load('tour09', '09_plugins.py')
    chart = HeadlessChart(width=1100, height=800)
    module.build(chart)
    js = chart.to_scripts()

    assert '"createUpDownMarkers"' in js
    assert '"setMarkers"' in js
    # the chart is fitted: markers on early bars are outside the default view
    # (the last ~170 of 320) and the engine only draws markers in view
    assert '"fitContent"' in js
    # the payload carries a price and a direction (the classic format has
    # neither, which is what the engine silently ignores)
    assert '"sign":1' in js.replace(' ', '')
    # markers are scaled up: at 320 bars fitted the default size is ~7px
    # (the two plugin markers are the ones that survive to the end)
    assert js.count('"size":3') >= 2
    assert '"positiveColor"' in js
    # the image watermark gets an inline image, not a file path
    assert '"createImageWatermark"' in js and 'data:image/png;base64' in js


def test_callbacks_example_does_not_mix_formatter_modes():
    """Example 11 shows both formatter styles, without mixing them."""
    module = _load('tour11', '11_callbacks.py')
    chart = HeadlessChart(width=1100, height=750)
    module.build(chart)
    js = chart.to_scripts()

    # the named formatter is selected on its own
    assert '"setPriceFormatter", ["eur"]' in js
    assert '"setTimeFormatter", ["time_short"]' in js
    # the declarative one is still demonstrated
    assert '"prefix":"$"' in js and '"thousands":true' in js
    # ... and the generic callback rewrites the same option last
    assert 'localization.priceFormatter' in js


def test_workspace_example_styles_the_crosshair():
    """Example 13 mirrors the official crosshair snippet.

    `chart.crosshair(...)` is the Python form of
    `chart.applyOptions({crosshair: {vertLine: ..., horzLine: ...}})`.
    """
    module = _load('tour13', '13_workspace.py')
    chart = HeadlessChart(width=1200, height=820, toolbox=True)
    module.build(chart)
    js = chart.to_scripts()

    assert '"crosshair"' in js
    assert '"mode":0' in js.replace(' ', '')          # CrosshairMode.Normal
    assert '"width":8' in js.replace(' ', '')
    assert '"#C3BCDB44"' in js                        # vertical line colour
    assert '"style":0' in js.replace(' ', '')         # LineStyle.Solid
    assert js.count('"#9B7DFF"') >= 3                 # label backgrounds + horz


def test_themes_example_styles_the_whole_window():
    """Example 15: `Window.theme` styles the root CSS and every chart.

    A theme is a window-level thing (the CSS variables are shared), so the
    chart created *after* `theme('dark')` inherits the palette as well - both
    charts therefore carry the same candle colours in their scripts.
    """
    module = _load('tour15', '15_themes.py')
    chart = HeadlessChart(width=1200, height=820)
    module.build(chart)
    js = chart.to_scripts()

    assert js.count('Lib.Handler.setRootStyles') == 1
    assert '"upColor":"rgba(39, 157, 130, 100)"' in js    # dark palette
    # main chart + subchart created later: the theme reaches both
    assert js.count('"upColor":"rgba(39, 157, 130, 100)"') == 2
    assert js.count('new Lib.Handler') == 2               # main + subchart
    assert 'arrowDown' in js or 'arrowUp' in js           # zigzag markers


def test_themes_example_uses_the_module_level_palettes():
    """`pylightcharts.themes` is importable and covers the table colours."""
    from pylightcharts.themes import DARK, LIGHT, resolve

    module = _load('tour15', '15_themes.py')
    assert module.SCREENSHOT_PATH.endswith('screenshot_15.png')
    for spec in (DARK, LIGHT, resolve('light'), resolve('dark')):
        assert 'table_background' in spec and 'table_border' in spec


def test_tooltips_example_builds_both_modes():
    """Example 16: the tutorial's tracking + magnifier tooltips.

    The DOM behaviour (position, flipping, clamping, lifecycle) is covered by
    `tests/e2e/smoke.py` in a real browser; here we check the example wires up
    both tooltips and the tutorial's crosshair style.
    """
    module = _load('tour16', '16_tooltips.py')
    chart = HeadlessChart(width=1100, height=760)
    module.build(chart)
    js = chart.to_scripts()

    assert js.count('createTooltip') == 2
    assert '"mode":"tracking"' in js and '"mode":"magnifier"' in js
    assert '"title":"ABC Inc."' in js
    assert '"fields":"auto"' in js
    assert '"fieldLabels":["O","H","L","C"]' in js
    # the tutorial hides the horizontal crosshair line and both labels
    assert '"horzLine":{"visible":false,"labelVisible":false}' in js
    assert '"vertLine":{"visible":true,"width":1,"color":"#758696"' in js


def test_two_symbols_example_uses_both_price_scales():
    """Example 17: the main candles stay on the right, the overlay on the left.

    Also covers the candle overlay (the second series is a candlestick, not a
    line) and the margins toggle.
    """
    module = _load('tour17', '17_two_symbols.py')
    chart = HeadlessChart(width=1150, height=780)
    module.build(chart)
    js = chart.to_scripts()

    # both scales visible, two overlays, both on the left axis
    assert '"visible":true' in js
    assert js.count('"priceScaleId":"left"') == 2
    assert '"Candlestick"' in js and '"Line"' in js
    assert '"ETHUSDT"' in js and '"ETHUSDT K"' in js
    # the overlay candles get their own colours and the split layout its margins
    assert '"upColor":"#26A69A"' in js
    assert '"scaleMargins":{"top":0.2,"bottom":0.2}' in js
    # the tutorial's crosshair tip for two symbols on one pane
    assert '"mode":0' in js.replace(' ', '')


def test_infinite_history_example_extends_indicators():
    """Example 18: older bars load into the candles *and* both indicators.

    The range change itself needs the window's event loop, so the example is
    driven here through `history.check(...)` - the same call the event makes.
    """
    module = _load('tour18', '18_infinite_history.py')
    chart = HeadlessChart(width=1150, height=780)
    module.build(chart)
    history = module.HISTORY
    sma, rsi = chart._lines[0], chart._lines[1]

    assert history.loaded == 200 and history.requests == 0
    assert (sma.name, sma._pane_index) == ('SMA 50', 0)
    assert rsi._pane_index == 1

    before = len(chart._scripts)
    added = history.check(0)

    assert added == 250 and history.loaded == 450
    assert history.requests == 1 and history.exhausted is False
    # both indicators cover the prepended bars, in their own panes
    oldest = int(history.earliest.timestamp())
    for indicator in (sma, rsi):
        assert len(indicator.data) == 450
        assert indicator.data['time'].min() == oldest
    script = chr(10).join(chart._scripts[before:])
    assert script.count('setData') >= 4          # candles, volume, SMA, RSI
    assert 'volumeSeries.setData' in script
    assert str(oldest) in script
    # the topbar reports it
    assert '450 bars' in chart.topbar['bars'].value


def test_infinite_history_example_stops_when_the_source_runs_out():
    module = _load('tour18', '18_infinite_history.py')
    chart = HeadlessChart(width=1150, height=780)
    module.build(chart)
    history = module.HISTORY

    guard = 0
    while not history.exhausted and guard < 40:
        history.check(-1)
        guard += 1

    assert history.exhausted is True
    # the whole 4000 bar source ended up on the chart, and the last request
    # (the one that returned nothing) is what marked it exhausted
    assert history.loaded == 4000
    assert 'no more history' in chart.topbar['bars'].value
    assert history.check(0) == 0                 # and it stays quiet



def test_stem_scatter_draws_a_dashed_stick_per_point():
    """Example 20: every bar gets a dashed vertical stem from 0 + a tip dot.

    `shapes.stem` is a two-point `polyline` sharing one bar offset - LWC has no
    vertical-dashed-line primitive, so this is what makes a lollipop chart
    possible without touching the renderer.
    """
    module = _load('tour20', '20_stem_scatter.py')
    chart = HeadlessChart(width=1100, height=800)
    module.build(chart)
    js = chart.to_scripts()

    sticks = re.findall(
        r'"type":"polyline","points":\[\[0\.0,0\.0\],\[0\.0,'
        r'[-0-9.]+\]\][^}]*"style":2', js)
    assert len(sticks) > 20, 'each bar should carry a dashed stem'
    assert js.count('"type":"circle"') > 20, 'cap=True should add tip dots'
    assert 'HorizontalSpan' in js, 'the 0 baseline should be a horizontal span'
    # per-point colours: both directions show up
    assert '#26A69A' in js and '#EF5350' in js


def test_text_multi_line_example_emits_multi_line_text():
    """`shapes.text` 的多行支持：换行符原样进 JS，由渲染器按行拆开绘制。

    `20_stem_scatter.py` 覆盖 `shapes.stem`，这里覆盖 `shapes.text` 的多行 +
    逐点 `lineHeight`（与 bokeh 的 `LabelSet` 行为对齐）。
    """
    module = _load('tour21', '21_text_multi_line.py')
    chart = HeadlessChart(width=1100, height=800)
    module.build(chart)
    js = chart.to_scripts().replace(' ', '')          # 去掉 JSON 里的空格再断言
    newline = chr(92) + 'n'                           # 字面量反斜杠 + n

    assert '"type":"text"' in js, '没有生成 text 图元'
    # 数据里的换行必须原样保留（渲染端 split 后才有多行）
    assert ('"text":"BUY' + newline + 'CCI"') in js, js[:200]
    assert '"lineHeight":1.25' in js, '未按数据列设置行距'
    # 示例里做多/做空给了不同的行距（1.25 / 1.0），两个都要出现
    assert '"lineHeight":1.25' in js and '"lineHeight":1.0' in js
    assert 'arrow_up' in js and 'arrow_down' in js, 'marker 没和文本组合'
    # 1.3.0 起 shapes.text 还支持像素偏移 / 字体 / 文本底色
    assert '"offsetX":14' in js or '"offsetX":-14' in js, '像素偏移没进数据'
    assert '"backgroundColor":"#222222"' in js, '文本底色没进数据'
    assert '"padding":3' in js, '内边距没进数据'


def test_line_gaps_example_splits_segments():
    """`22_line_gaps.py`（NaN 断点）：主序列隐藏 + 每段一条同款序列。"""
    module = _load('tour22', '22_line_gaps.py')
    chart = HeadlessChart(width=1100, height=620)
    module.build(chart)
    js = chart.to_scripts()

    assert 'lineVisible: false' in js, '主序列没有让位给分段'
    # 主序列 + 两段（数据是 3 个值 / 2 个 nan / 3 个值）
    assert js.count('setData') == 5, js.count('setData')   # 另有 K 线 + nan→0 两条
    # 只看 setData 的数据（`_invoke_assign` 现在会在每个脚本末尾补 `\nnull`，
    # 那是桥的哨兵值，不是数据）：分段后数据里不应再出现 NaN / null
    data = [line for line in js.splitlines() if 'setData' in line]
    assert data and all('NaN' not in line and 'null' not in line for line in data), \
        '分段后不应再出现 NaN/null'
    # `report()` 只读数据，不需要窗口 -> 一起测，别再让"for row in df"这种坑溜过去
    module.report(chart)


def test_fill_between_example_keeps_the_nan_gaps():
    """`23_fill_between_gaps.py`：色带必须在 `nan` 处断开。

    真正的分段逻辑在 JS（`line-fill` 的 pane-view / renderer），这里守两件事：
    ① 确实建了色带（`LineFill` + `attachPrimitive`）；
    ② 通道线下发的数据里**保留了空白点**（`{time}` 而没有 `value`）——
    缺口信息要传到前端，色带才可能断开。
    """
    module = _load('tour23', '23_fill_between_gaps.py')
    chart = HeadlessChart(width=1280, height=700)
    module.build(chart)
    js = chart.to_scripts()

    assert 'LineFill' in js and 'attachPrimitive' in js, '没有建出色带'
    payloads = re.findall(r'\.series\.setData\(\[(.*?)\]\)', js, re.S)
    single = [p for p in payloads if '"value"' in p]
    assert single, '没有单值（通道线）序列的载荷'
    assert any(any('"value"' not in item for item in p.split('},{'))
               for p in single), '缺口（没有 value 的空白点）没有下发'


def test_layouts_and_legend_settings_example():
    """`24_layouts_and_legend_settings.py`：迁移过程中加的扩展都要用上。

    - 2D tile 布局（`Lib.setLayoutTiles`）+ 可拖分割条（gap 参数）；
    - 图例齿轮（`addSettingsToggle`）与常显图例行（`pinSeriesRow`）；
    - 序列样式设置（`set_line_width` / `set_line_color` / `set_line_style` /
      `set_price_visible`）。
    """
    module = _load('tour24', '24_layouts_and_legend_settings.py')
    chart = HeadlessChart(width=1280, height=840)
    module.build(chart)
    js = chart.to_scripts()

    assert 'Lib.setLayoutTiles' in js, '没有用 2D tile 布局'
    # dividers=True -> gap 参数（默认 divider_size=6）传给 JS
    assert re.search(r'setLayoutTiles\([\s\S]*?\],\s*6,', js), \
        'tile 分隔条没有开启'
    assert 'addSettingsToggle' in js, '图例齿轮没有挂'
    assert 'pinSeriesRow' in js, '图例行没有常显'
    assert '"lineWidth"' in js and '"lineStyle"' in js, '线宽/线型没有下发'
    assert '"lastValueVisible"' in js, '价格标签开关没有下发'


def test_live_value_table_follows_crosshair_and_realtime():
    """`25_live_value_table.py`：表格跟随十字光标 + 实时刷新。

    关键点是鼠标移出 K 线时要回到**最后一根**的值（表格常显，不像图例标签
    会消失），以及实时追加一根后表格跟着更新。
    """
    module = _load('tour25', '25_live_value_table.py')
    chart = HeadlessChart(width=1100, height=720)
    state = module.build(chart)
    table = state['table']

    def rows():
        return [dict(row) for row in table.table.values()]

    # 初始：最后一根
    assert rows()[-1] == {'Field': 'Cursor', 'Value': 'last'}

    # 鼠标移到第 7 根 -> 显示那一根的指标值
    times = table._times
    table.on_crosshair(chart, times[7], 100.0)
    hovered = rows()
    assert hovered[1]['Value'] == f"{state['fast'][7]:.2f}"
    assert hovered[2]['Value'] == f"{state['slow'][7]:.2f}"

    # 移出 K 线（time 为空）-> 回到最后一根
    table.on_crosshair(chart, None, None)
    assert rows()[-1] == {'Field': 'Cursor', 'Value': 'last'}
    assert rows()[1]['Value'] == f"{state['fast'][-1]:.2f}"

    # 实时追加一根 -> 表格跟着前移
    last_before = state['fast'][-1]
    module.append_bar(chart, state)
    assert state['fast'][-1] != last_before
    assert rows()[1]['Value'] == f"{state['fast'][-1]:.2f}"
    assert 'Lib.Table' in chart.to_scripts()
