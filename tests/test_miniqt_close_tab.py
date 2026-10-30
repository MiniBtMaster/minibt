"""关闭标题栏标签后的返回页：优先「上一次打开的导航页」，否则 **行情报价** ✓。

    pytest tests/test_miniqt_close_tab.py
"""
from __future__ import annotations

import os
import types

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# 必须在导入 main_window 之前 import（main_window 会 import 它 ✗）
import PyQt6.QtWebEngineWidgets  # noqa: F401,E402


def _mw():
    return pytest.importorskip('miniqt.app.view.main_window')


class _FakeStacked:
    def __init__(self, pages):
        self._pages = list(pages)

    def count(self):
        return len(self._pages)

    def widget(self, index):
        return self._pages[index]


def _make(pages, last, tabs):
    """造一个假的 CustomTitleBar（不建 GUI），只测 `_restore_last_page` ✓。"""
    window = types.SimpleNamespace(
        stackedWidget=_FakeStacked(pages),
        marketQuotePreviewInterface=pages[1] if len(pages) > 1 else None,
        homeInterface=pages[0],
        navigated=[],
    )
    window._navigateTo = lambda widget: window.navigated.append(widget)
    bar = types.SimpleNamespace(main_window=window, qobject=tabs,
                                _last_page=last)
    bar._restore_last_page = types.MethodType(
        _mw().CustomTitleBar._restore_last_page, bar)
    return bar, window


def test_close_returns_to_the_last_page_not_settings():
    home, quote, settings = object(), object(), object()
    bar, window = _make([home, quote, settings], last=quote, tabs={})
    bar._restore_last_page()
    assert window.navigated == [quote]      # 不是 qrouter 顶部的设置 ✗


def test_close_falls_back_to_market_quote():
    home, quote, settings = object(), object(), object()
    bar, window = _make([home, quote, settings], last=None, tabs={})
    bar._restore_last_page()
    assert window.navigated == [quote]


def test_close_falls_back_to_home_when_quote_missing():
    home = object()
    bar, window = _make([home], last=None, tabs={})
    bar._restore_last_page()
    assert window.navigated == [home]


def test_close_with_other_tabs_lets_the_router_decide():
    home, quote = object(), object()
    bar, window = _make([home, quote], last=home, tabs={'chart1': object()})
    bar._restore_last_page()
    assert window.navigated == []           # 还有标签 → 不插手 ✓


def test_add_tab_remembers_the_current_navigation_page():
    home, quote = object(), object()

    class FakeWidget:
        def objectName(self):               # noqa: N802
            return 'Chart'

    window = types.SimpleNamespace(
        stackedWidget=types.SimpleNamespace(currentWidget=lambda: quote))
    bar = types.SimpleNamespace(main_window=window, qobject={}, _last_page=home)
    bar.addTab = types.MethodType(_mw().CustomTitleBar.addTab, bar)
    bar.addSubInterface = lambda *a, **k: None
    bar._safe_set_current_widget = lambda widget: None
    bar.addTab(FakeWidget())
    assert bar._last_page is quote
