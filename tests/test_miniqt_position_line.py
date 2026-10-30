# coding:utf-8
"""持仓线的**清理**逻辑：平仓要彻底收掉 primitive + 载体指标 ✓。

用户反馈：平仓后持仓线没清理干净——primitive 只改透明、载体序列最后一根
的点还留着，图上多出一条小横线 ✗；关掉持仓线显示才消失。
"""
from __future__ import annotations

import os
import types

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PyQt6')

window_mod = pytest.importorskip('miniqt.app.windows.pylightcharts_window')
POSITION_LINE_GROUP = window_mod.POSITION_LINE_GROUP


class _FakeLine:
    def __init__(self):
        self.deleted = False
        self.options_calls = []

    def delete(self):
        self.deleted = True

    def options(self, **kwargs):
        self.options_calls.append(kwargs)

    def update(self, price):
        pass


class _FakeChart:
    def __init__(self, cid='c1'):
        self.id = cid
        self.removed_markers = []

    def remove_markers(self, markers):
        self.removed_markers.append(markers)


def _window():
    W = window_mod.PylightchartsChartWindow
    window = W.__new__(W)
    window._closing = False
    window._position_lines = {}
    window.indicators = []
    return window


def test_remove_position_line_everything_deletes_line_and_carrier():
    """`_remove_position_line_everything`：删 primitive + 载体指标 ✓。"""
    window = _window()
    chart = _FakeChart()
    line = _FakeLine()
    window._position_lines['c1'] = {'line': line, 'carrier': object(),
                                    'chart': chart, 'markers': []}
    removed = []
    window.remove_indicator = lambda i: removed.append(i)
    carrier = types.SimpleNamespace(indicator_cls=POSITION_LINE_GROUP)
    window.indicators = [{'id': 'e1', 'indicator': carrier, 'chart': chart}]
    window._remove_position_line_everything(chart)
    assert window._position_lines == {}
    assert line.deleted is True
    assert removed == ['e1']


def test_close_position_removes_line_instead_of_hiding(monkeypatch):
    """平仓（没有持仓）→ 调 `_remove_position_line_everything`，不再只藏 ✓。"""
    monkeypatch.setattr(window_mod, 'DEBUG_POSITION_LINE', False, raising=False)
    window = _window()
    chart = _FakeChart()
    item = {'line': _FakeLine(), 'chart': chart}
    window._position_lines['c1'] = item
    window._position_rows = lambda: []
    window._panel_symbol = lambda c: 'SHFE.ag2612'
    calls = []
    window._remove_position_line_everything = lambda c: calls.append(c.id)
    drawn = window._update_one_position_line('c1', item)
    assert calls == ['c1']
    assert drawn == 0
    # 不再用「改透明藏线」那条老路 ✗
    assert item['line'].options_calls == []


def test_position_line_cleanup_source_guards():
    """源码守卫：平仓分支必须是**删除**，不能再是 `color='transparent'` 藏线。"""
    source = (window_mod.__file__)
    with open(source, encoding='utf-8') as handle:
        text = handle.read()
    assert 'def _remove_position_line_everything' in text
    assert 'self._remove_position_line_everything(chart)' in text
