"""Table position anchoring: assert on the JS the bridge generates.

Runs without a browser - a fake `Window` records every script that would have
been sent to the webview (same pattern as `test_bridge.py`).
"""
import re

import pytest

from pylightcharts.abstract import AbstractChart, Window
from pylightcharts.table import POSITIONS


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True  # run scripts straight into the capture list
    chart = AbstractChart(window)
    chart.captured = captured
    captured.clear()
    return chart


@pytest.fixture()
def table(chart):
    table = chart.create_table(width=340, height=180,
                               headings=('symbol', 'price'), draggable=True)
    chart.captured.clear()
    return table


def _script(chart) -> str:
    return '\n'.join(chart.captured)


def _float_arg(js: str) -> str:
    """The CSS-float value handed to the JS ``Lib.Table`` constructor."""
    call = js[js.index('new Lib.Table('):]
    return re.search(r"\n\s+'(left|right|top|bottom)',\n", call).group(1)


def _offsets(js: str) -> dict:
    """``{'left': '0', 'right': 'auto', ...}`` as written into the div style."""
    out = {}
    for side in ('left', 'right', 'top', 'bottom'):
        marker = f'div.style.{side} = '
        start = js.rindex(marker) + len(marker)     # last call wins
        out[side] = js[start:js.index(';', start)].strip("'")
    return out


def test_set_position_defaults_to_the_top_right_corner(table, chart):
    table.set_position()
    js = _script(chart)
    assert "div.style.position = 'absolute'" in js     # overlays the chart
    assert "div.style.float = ''" in js                # no longer in the flow
    assert _offsets(js) == {
        'left': 'auto', 'right': '0', 'top': '0', 'bottom': 'auto'}


@pytest.mark.parametrize('position, expected', [
    ('top-left', {'left': '0', 'right': 'auto', 'top': '0', 'bottom': 'auto'}),
    ('top-right', {'left': 'auto', 'right': '0', 'top': '0', 'bottom': 'auto'}),
    ('bottom-left', {'left': '0', 'right': 'auto', 'top': 'auto', 'bottom': '0'}),
    ('bottom-right', {'left': 'auto', 'right': '0', 'top': 'auto', 'bottom': '0'}),
    ('left', {'left': '0', 'right': 'auto', 'top': '0', 'bottom': 'auto'}),
    ('right', {'left': 'auto', 'right': '0', 'top': '0', 'bottom': 'auto'}),
])
def test_set_position_anchors_to_every_corner(table, chart, position, expected):
    table.set_position(position)
    assert _offsets(_script(chart)) == expected


def test_set_position_overwrites_the_previous_corner(table, chart):
    table.set_position('top-left')
    table.set_position('bottom-right')
    assert _offsets(_script(chart)) == {
        'left': 'auto', 'right': '0', 'top': 'auto', 'bottom': '0'}


def test_set_position_rejects_unknown_values(table):
    with pytest.raises(ValueError, match='unknown position'):
        table.set_position('middle-left')      # 'middle' is a centre alias now


def test_create_table_applies_position_at_construction(chart):
    chart.create_table(width=340, height=180, headings=('a',),
                       position='bottom-right', draggable=True)
    js = _script(chart)
    assert "div.style.position = 'absolute'" in js
    assert _offsets(js) == {
        'left': 'auto', 'right': '0', 'top': 'auto', 'bottom': '0'}
    assert _float_arg(js) == 'right'          # legal CSS float for the JS API


def test_create_table_defaults_to_the_top_right_corner(chart):
    chart.create_table(width=340, height=180, headings=('a',), draggable=True)
    js = _script(chart)
    assert _offsets(js) == {
        'left': 'auto', 'right': '0', 'top': '0', 'bottom': 'auto'}


@pytest.mark.parametrize('position, expected', [
    ('left', 'top-left'),
    ('right', 'top-right'),
    ('top', 'top-left'),
    ('bottom', 'bottom-left'),
])
def test_create_table_accepts_the_legacy_float_values(chart, position, expected):
    chart.create_table(width=340, height=180, headings=('a',),
                       position=position, draggable=True)
    js = _script(chart)
    assert _offsets(js) == {
        'left': '0' if expected.endswith('left') else 'auto',
        'right': '0' if expected.endswith('right') else 'auto',
        'top': '0' if expected.startswith('top') else 'auto',
        'bottom': '0' if expected.startswith('bottom') else 'auto'}


def test_create_table_rejects_unknown_position_before_building(chart):
    with pytest.raises(ValueError, match='unknown position'):
        chart.create_table(width=340, height=180, headings=('a',),
                           position='middle-left')
    assert 'Lib.Table' not in _script(chart)   # nothing half-built


def test_position_table_covers_every_accepted_keyword():
    assert set(POSITIONS) == {
        'top-left', 'top-right', 'bottom-left', 'bottom-right',
        'center', 'middle',
        'left', 'right', 'top', 'bottom'}
    # the centre aliases resolve to the centring pair
    assert POSITIONS['center'] == POSITIONS['middle'] == ('center', 'center')


def test_centred_table_uses_a_transform(chart):
    chart.captured.clear()
    table = chart.create_table(width=300, height=200, headings=('a',),
                               position='center', draggable=True)
    script = chr(10).join(chart.captured)
    assert "div.style.left = '50%'" in script
    assert "div.style.top = '50%'" in script
    assert "div.style.transform = 'translate(-50%, -50%)'" in script

    chart.captured.clear()
    table.set_position('top-left')            # and it can go back to a corner
    script = chr(10).join(chart.captured)
    assert "div.style.transform = ''" in script
    assert "div.style.left = '0'" in script


def test_table_position_supports_margins(chart):
    """`margin_x` / `margin_y` 控制离“该角最近两条边”的间距。"""
    chart.create_table(width=200, height=100, headings=('a',),
                       position='top-right', margin_x=12, margin_y=8,
                       draggable=True)
    script = chr(10).join(chart.captured)
    assert "div.style.right = '12px'" in script
    assert "div.style.top = '8px'" in script
    assert "div.style.left = 'auto'" in script

    chart.captured.clear()
    table = chart.create_table(width=200, height=100, headings=('a',),
                               position='bottom-left', margin_x=4,
                               margin_y=6)
    script = chr(10).join(chart.captured)
    assert "div.style.left = '4px'" in script
    assert "div.style.bottom = '6px'" in script
    assert "div.style.right = 'auto'" in script

    # set_position 运行期也能改间距
    chart.captured.clear()
    table.set_position('top-left', margin_x=9, margin_y=0)
    script = chr(10).join(chart.captured)
    assert "div.style.left = '9px'" in script
    assert "div.style.top = '0'" in script


def test_clicked_cell_callback_accepts_one_or_two_arguments(chart):
    """`return_clicked_cells=True` 时 1 参 / 2 参回调都能用。

    文档契约是 ``func(row, heading)``，但只写 ``func(row)`` 的人很多；
    以前会 ``TypeError: ... takes 1 positional argument but 2 were given``。
    """
    one, two, plain = [], [], []
    t1 = chart.create_table(width=200, height=100, headings=('a', 'b'),
                            return_clicked_cells=True,
                            func=lambda row: one.append(dict(row)))
    row1 = t1.new_row('x', 'y')
    chart.win.handlers[t1.id](row1.id, 'b')
    assert one == [{'a': 'x', 'b': 'y'}]

    t2 = chart.create_table(width=200, height=100, headings=('a', 'b'),
                            return_clicked_cells=True,
                            func=lambda row, col: two.append((dict(row), col)))
    row2 = t2.new_row('x', 'y')
    chart.win.handlers[t2.id](row2.id, 'b')
    assert two == [({'a': 'x', 'b': 'y'}, 'b')]

    t3 = chart.create_table(width=200, height=100, headings=('a', 'b'),
                            func=lambda row: plain.append(dict(row)))
    row3 = t3.new_row('x', 'y')
    chart.win.handlers[t3.id](row3.id)
    assert plain == [{'a': 'x', 'b': 'y'}]
