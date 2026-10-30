"""The miniqt panel gallery page wires every plugin to a builder.

These only check the (Qt-free) wiring and mock data shapes; the page itself needs a
real QtWebEngine window to render.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

pytest.importorskip('PyQt6')
gallery = pytest.importorskip('miniqt.app.view.panels_gallery_interface')


def test_specs_cover_the_catalog_in_order():
    titles = [title for title, _method in gallery._SPECS]
    assert len(titles) == 26                     # 27 widgets minus Advanced Chart
    assert titles[0].startswith('2 ')            # Symbol Overview
    assert titles[-1].startswith('27 ')          # Broker Reviews
    # the two not-yet-implemented ones are placeholders, in the right places
    assert any('Technical Analysis' in title for title in titles)
    assert any('Economic Map' in title for title in titles)


def test_every_spec_has_a_builder():
    for _title, method in gallery._SPECS:
        builder = getattr(gallery.PanelsGalleryInterface, method, None)
        assert callable(builder), method


def test_mock_data_shapes():
    rows = gallery._rows(10)
    assert len(rows) == 10
    assert {'symbol', 'name', 'last', 'chg', 'chg_pct', 'spark'} <= set(rows[0])

    items = gallery._items(rows)
    assert items[0]['symbol'] == rows[0]['symbol']
    assert 'spark' not in items[0]

    heat = gallery._heat_items(12, 1)
    assert len(heat) == 12 and 'chg_pct' in heat[0]

    frame = gallery._ohlcv(100, 1)
    assert list(frame.columns)[:5] == ['time', 'open', 'high', 'low', 'close']
    assert len(frame) == 100

    seasonal = gallery.PanelsGalleryInterface._seasonal_frame(2, 1)
    assert 'close' in seasonal.columns and 'time' in seasonal.columns


def test_gallery_build_enables_scroll_and_height_sync():
    """画廊页要能滚到**全部** 26 个插件。

    以前只靠页面 ``window.callbackFunction`` 回传高度：桥没就绪时它被换成空函数，
    webview 就不长大（停在 600px）→ 只显示前几行、外层 ScrollArea 也没得滚 ✗。
    现在两重保险：① html/body 允许内部滚动（对齐 ``examples/13_panels/10_gallery.py``）；
    ② Python 直接 ``runJavaScript`` 多拍取最大高度把 webview 撑开。
    """
    import inspect
    build = inspect.getsource(gallery.PanelsGalleryInterface._build_gallery)
    assert "overflow = 'auto'" in build
    assert "_sync_gallery_height" in build
    assert callable(gallery.PanelsGalleryInterface._sync_gallery_height)


def test_sync_gallery_height_uses_run_javascript():
    """``_sync_gallery_height`` 不依赖页面回调，直接量高度并把 webview 撑开。"""
    class FakePage:
        def __init__(self):
            self.calls = 0

        def runJavaScript(self, _js, callback):
            self.calls += 1
            callback(2450)

    class FakeView:
        def __init__(self):
            self.page_ = FakePage()
            self.fixed_height = None

        def page(self):
            return self.page_

        def setFixedHeight(self, height):
            self.fixed_height = height

    class FakePanel:
        def __init__(self):
            self.view = FakeView()

        def get_webview(self):
            return self.view

    page = gallery.PanelsGalleryInterface.__new__(
        gallery.PanelsGalleryInterface)
    page._panel = FakePanel()
    page._gallery_height = 0
    page._sync_gallery_height(tries=1)
    assert page._panel.get_webview().fixed_height == 2454
