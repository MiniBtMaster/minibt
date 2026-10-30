"""Tests for the pylightcharts page-level top bar and the chart layout.

Both are pylightcharts extensions (Lightweight Charts has neither), so these
are the only place their behaviour is pinned down. They run without a browser:
a fake `Window` records the generated JS and the layout geometry lives in
python (`AbstractChart._width/_height`).
"""
import re

import pytest

from pylightcharts.abstract import AbstractChart, Window
from pylightcharts.layout import HORIZONTAL, VERTICAL, Layout


@pytest.fixture()
def window():
    captured = []
    win = Window(script_func=captured.append)
    win.loaded = True
    win.captured = captured
    return win


@pytest.fixture()
def chart(window):
    chart = AbstractChart(window)
    window.captured.clear()
    return chart


# --------------------------------------------------------------------------
# page-level top bar
# --------------------------------------------------------------------------

def test_page_topbar_is_a_singleton_on_the_window(chart):
    win = chart.win
    bar = win.page_topbar()

    assert win.page_topbar() is bar
    assert bar._page is True
    assert bar._created is False                    # nothing in the DOM yet


def test_page_topbar_spans_the_window_not_a_chart(chart):
    """A chart bar grows inside its chart; the page bar is created globally."""
    bar = chart.win.page_topbar()
    bar.textbox('symbol', 'BTCUSDT')

    js = '\n'.join(chart.win.captured)
    assert 'Lib.createPageTopBar()' in js
    assert 'createTopBar()' not in js           # no chart-level bar involved
    # the chart bar would have gone through its own handler
    assert f'{chart.id}.createTopBar' not in js


def test_page_topbar_widgets_register_handlers(chart):
    bar = chart.win.page_topbar()
    bar.switcher('timeframe', ('5m', '15m'), default='5m', func=lambda w: None)
    bar.button('indicators', '指标', func=lambda w: None)
    bar.menu('layout', ('上下布局', '左右布局'), default='布局',
             align='right', func=lambda w: None)

    assert set(bar._widgets) == {'timeframe', 'indicators', 'layout'}
    for widget in bar._widgets.values():
        assert chart.win.handlers[widget.id] is not None
    js = '\n'.join(chart.win.captured)
    assert 'makeSwitcher' in js and 'makeMenu' in js and 'makeButton' in js
    # the menu keeps its own label until an item is picked
    assert '"布局"' in js
    assert "'上下布局', '左右布局'" in js


def test_page_topbar_callbacks_receive_the_window(chart):
    """Chart bars hand their chart to the callback, page bars the window."""
    win = chart.win
    seen = []
    bar = win.page_topbar()
    bar.button('settings', '设置', func=seen.append)

    chart.win.handlers[bar['settings'].id]('设置')      # what JS calls back
    assert seen == [win]
    assert bar['settings'].value == '设置'


def test_chart_topbar_still_receives_its_chart(chart):
    seen = []
    chart.topbar.button('mark', 'Mark', func=seen.append)

    chart.win.handlers[chart.topbar['mark'].id]('Mark')
    assert seen == [chart]


# --------------------------------------------------------------------------
# layout
# --------------------------------------------------------------------------

def test_window_layout_holds_the_charts_in_creation_order(chart):
    sub = chart.create_subchart(position='left', width=0.5, height=0.5)

    assert chart.win.layout.charts == [chart, sub]
    assert chart.win.layout.anchor is chart


def test_vertical_adds_a_chart_below(chart):
    """上下布局：默认在下方新增一张，两张各占一半高度。"""
    charts = chart.win.layout.vertical()

    assert len(charts) == 2 and chart.win.layout.kind == VERTICAL
    assert [(c._width, c._height) for c in charts] == [
        (1.0, 0.5), (1.0, 0.5)]                     # full width = stacked
    assert charts[0] is chart                      # anchor keeps its place
    # multi-timeframe / multi-symbol charts must not move together
    assert 'syncCharts' not in '\n'.join(chart.win.captured)


def test_charts_are_independent_unless_sync_is_asked_for(chart):
    """A layout is for different periods / symbols: no sync by default.

    ``sync=True`` / ``sync='crosshair'`` stay available for a linked view.
    """
    layout = chart.win.layout
    layout.vertical()
    assert 'syncCharts' not in '\n'.join(chart.win.captured)
    assert layout.sync_mode is None

    # asking for the link also covers the chart that already existed, and the
    # one the layout now creates
    chart.win.captured.clear()
    charts = layout.horizontal(3, sync=True)
    synced = [line for line in chart.win.captured if 'syncCharts' in line]
    assert layout.sync_mode == 'full'
    for sub in charts[1:]:
        assert any(sub.id in line and chart.id in line
                   for line in synced), synced


def test_crosshair_only_sync_is_available(chart):
    layout = chart.win.layout
    subs = layout.horizontal(sync='crosshair')

    assert layout.sync_mode == 'crosshair'
    synced = [line for line in chart.win.captured if 'syncCharts' in line]
    assert synced, chart.win.captured
    for line in synced:
        assert 'true' in line           # crosshairs_only=True
        assert subs[1].id in line and chart.id in line


def test_sync_can_be_dropped_and_switched(chart):
    """`sync` is not a one-way door: the link is replaced, not stacked."""
    layout = chart.win.layout
    layout.horizontal(sync=True)

    chart.win.captured.clear()
    layout.horizontal()                 # independent again
    assert 'unsyncCharts' in '\n'.join(chart.win.captured)
    assert layout.sync_mode is None
    assert layout._synced == {}

    chart.win.captured.clear()
    layout.horizontal(sync='crosshair')  # crosshair only, replacing nothing
    assert layout.sync_mode == 'crosshair'
    assert 'true' in '\n'.join(chart.win.captured)

    chart.win.captured.clear()
    layout.horizontal(sync=True)         # upgrade again
    js = '\n'.join(chart.win.captured)
    assert 'syncCharts' in js and 'false' in js
    assert 'unsyncCharts' not in js      # JS side replaces the old link


def test_layout_rejects_unknown_sync_modes(chart):
    with pytest.raises(ValueError, match='sync must be'):
        chart.win.layout.horizontal(sync='sometimes')


def test_chart_sync_and_unsync(chart):
    sub = chart.create_subchart(position='left', width=0.5, height=0.5)

    chart.sync(sub, crosshairs_only=True)
    assert 'syncCharts' in '\n'.join(chart.win.captured)

    chart.win.captured.clear()
    chart.unsync(sub)
    assert 'unsyncCharts' in '\n'.join(chart.win.captured)


def test_horizontal_adds_a_chart_to_the_right(chart):
    """左右布局：默认在右侧新增一张，两张各占一半宽度。"""
    charts = chart.win.layout.horizontal()

    assert [(c._width, c._height) for c in charts] == [
        (0.5, 1.0), (0.5, 1.0)]                     # half width = side by side
    assert chart.win.layout.kind == HORIZONTAL


def test_switching_layout_reuses_the_same_charts(chart):
    first = chart.win.layout.vertical()
    second = chart.win.layout.horizontal()

    assert first == second                          # no chart was re-created
    assert [(c._width, c._height) for c in second] == [(0.5, 1.0), (0.5, 1.0)]


def test_arrange_creates_and_hides_charts(chart):
    layout = chart.win.layout
    charts = layout.arrange(HORIZONTAL, 3)

    assert len(charts) == 3
    assert [round(c._width, 4) for c in charts] == [0.3333, 0.3333, 0.3333]
    assert [c._height for c in charts] == [1.0, 1.0, 1.0]

    # shrinking parks the extra charts at 0x0 instead of dropping them
    kept = layout.arrange(HORIZONTAL, 2)
    assert kept == charts[:2]
    assert layout.hidden_charts == [charts[2]]
    assert (charts[2]._width, charts[2]._height) == (0, 0)

    # ... and they come back, with their data, when the layout grows again
    again = layout.arrange(HORIZONTAL, 3)
    assert again == charts
    assert layout.hidden_charts == []
    assert (charts[2]._width, charts[2]._height) == (pytest.approx(1 / 3), 1.0)


def test_layout_on_create_hook_feeds_new_charts(chart):
    """`on_create` is how a host fills the charts the layout creates."""
    filled = []
    layout = chart.win.layout
    layout.vertical(on_create=filled.append)

    assert filled == layout.charts[1:]
    # a chart that was only hidden and shown again is not "created" twice
    layout.horizontal()
    layout.vertical()
    assert filled == layout.charts[1:]


def test_layout_on_create_default_and_register(chart):
    layout = chart.win.layout
    layout.on_create = lambda c: None
    assert layout.on_create is not None

    extra = chart.create_subchart(position='left', width=0.5, height=0.5)
    layout.unregister(extra)
    assert extra not in layout.charts
    layout.register(extra)
    assert layout.charts[-1] is extra

    layout.register(extra)                          # idempotent
    assert layout.charts.count(extra) == 1


def test_layout_validates_its_arguments(chart):
    layout = chart.win.layout
    with pytest.raises(ValueError, match='horizontal'):
        layout.arrange('diagonal', 2)
    with pytest.raises(ValueError, match='at least 1'):
        layout.horizontal(0)

    empty = Layout(chart.win)                       # no chart registered
    with pytest.raises(ValueError, match='no chart'):
        empty.vertical()


def test_layout_single_collapses_back(chart):
    layout = chart.win.layout
    layout.horizontal(3)
    assert len(layout.charts) == 3

    assert layout.single() == [chart]
    assert (chart._width, chart._height) == (1.0, 1.0)
    assert len(layout.hidden_charts) == 2


def test_layout_forwards_subchart_options(chart):
    sub = chart.win.layout.vertical(toolbox=True, scale_candles_only=True)[1]

    assert sub._scale_candles_only is True
    assert hasattr(sub, 'toolbox')


# --------------------------------------------------------------------------
# draggable dividers between the charts
# --------------------------------------------------------------------------

def test_layout_adds_draggable_dividers(chart):
    """Like the separators between panes, but between the charts."""
    layout = chart.win.layout
    charts = layout.horizontal()

    js = '\n'.join(chart.win.captured)
    assert 'Lib.setLayoutDividers' in js
    for c in charts:
        assert c.id in js                      # handed over in layout order
    assert '"horizontal"' in js
    assert layout.divider is True
    assert layout.divider_size == 6
    # the JS side reports the shares back after a drag
    assert layout._callback_id in chart.win.handlers


def test_layout_divider_can_be_disabled(chart):
    layout = chart.win.layout
    charts = layout.horizontal(divider=False)
    assert charts
    # size 0 tells the JS side to drop the dividers
    js = '\n'.join(chart.win.captured)
    assert re.search(r'"horizontal",\s*0,', js), js

    chart.win.captured.clear()
    layout.set_divider(enabled=True, size=10, color='#123456',
                       hover_color='#654321')
    js = '\n'.join(chart.win.captured)
    assert layout.divider_size == 10 and layout.divider_color == '#123456'
    assert '10' in js and '#123456' in js and '#654321' in js

    chart.win.captured.clear()
    layout.set_divider(enabled=False)
    js = '\n'.join(chart.win.captured)
    assert re.search(r'"horizontal",\s*0,', js), js


def test_layout_drag_updates_the_chart_shares(chart):
    """Dragging a divider must leave `_width` / `_height` truthful."""
    layout = chart.win.layout
    charts = layout.horizontal()
    drag = chart.win.handlers[layout._callback_id]

    drag('0.7', '0.3')                       # what JS sends on mouseup
    assert (charts[0]._width, charts[1]._width) == (0.7, 0.3)

    layout.vertical()
    drag('0.25', '0.75')
    assert (charts[0]._height, charts[1]._height) == (0.25, 0.75)

    drag('not-a-number', '0.5')              # malformed payloads are ignored
    assert (charts[0]._height, charts[1]._height) == (0.25, 0.75)


def test_arrange_tiles_positions_and_can_clear(chart):
    """A vertical tile layout goes through `setLayoutTiles` in (x, y, w, h)."""
    layout = chart.win.layout
    chart.win.captured.clear()
    charts = layout.arrange_tiles([(1.0, 1 / 3)] * 3)

    assert len(charts) == 3
    script = '\n'.join(script for script in chart.win.captured
                       if 'setLayoutTiles' in script).replace(' ', '')
    assert '[0.0,0.0,1.0,0.3333333333333333]' in script
    assert '[0.0,0.333333,1.0,0.3333333333333333]' in script
    assert layout._tiles is not None

    chart.win.captured.clear()
    layout.arrange('horizontal', 3)
    assert 'Lib.clearLayoutTiles' in '\n'.join(chart.win.captured)
    assert layout._tiles is None


def test_arrange_tiles_dividers_are_handled_by_the_tiles(chart):
    """Column tiles get their dividers from `setLayoutTiles`, not the float one."""
    layout = chart.win.layout
    chart.win.captured.clear()
    layout.arrange_tiles([(1.0, 1 / 2), (1.0, 1 / 2)], dividers=True)

    js = '\n'.join(chart.win.captured)
    assert 'Lib.setLayoutTiles' in js
    assert 'Lib.setLayoutDividers' not in js        # the float divider path
    assert re.search(r'\[\[0\.0,0\.0,1\.0,0\.5\]', js.replace(' ', ''))
    assert re.search(r'\],\s*6,', js), js
    assert '#2a2e39' in js and '#2962FF' in js


def test_set_divider_reapplies_the_tiles_color(chart):
    """主题切换重设间隔条颜色时，tiles 布局要重新下发一次（浅色主题 ✓）。"""
    layout = chart.win.layout
    layout.arrange_tiles([(1.0, 1 / 2), (1.0, 1 / 2)], dividers=True)
    chart.win.captured.clear()

    layout.set_divider(color='#e3e6ea')
    js = '\n'.join(chart.win.captured)
    assert layout.divider_color == '#e3e6ea'
    assert 'Lib.setLayoutTiles' in js
    assert '#e3e6ea' in js
    # 尺寸/间隙也还在（6px ✓）
    assert re.search(r'\],\s*6,', js), js


def test_switcher_set_clicks_the_matching_button(chart):
    """`SwitcherWidget.set` must click the button, not pass the option text.

    The JS `onItemClicked` takes the button element (it toggles the active class
    and reads `innerText`); passing a string threw
    "Cannot read properties of undefined (reading 'add')" and the switcher lost
    its highlight, so the callback never fired.
    """
    bar = chart.win.page_topbar()
    bar.switcher('tf', ('1m', '5m', '1h'), default='5m',
                 func=lambda win: None)
    widget = bar['tf']
    chart.win.captured.clear()

    widget.set('1h')
    script = chart.win.captured[-1]
    assert '.intervalElements[2].click()' in script, script
    assert 'onItemClicked("1h")' not in script
    assert widget.value == '1h'

    with pytest.raises(ValueError, match='does not exist'):
        widget.set('9h')
