"""首页「快捷入口」→ 指标和策略 的跳转 ✓。

用户要求：主页 **快捷入口-行情报价 后面** 加一个「指标和策略」入口，
点击跳到「指标和策略」页 ✓。这里锁死两件事：

1. 卡片顺序：行情报价 → **指标和策略** → qtvscode（源码顺序 ✓）；
2. ``switchToSample("indicatorStrategyInterface")`` 会导航到
   ``MainWindow.indicatorStrategyInterface`` ✓。

    pytest tests/test_miniqt_home_quick_entries.py
"""
from __future__ import annotations

import os
import types

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# 必须早于任何 QApplication / main_window 导入 ✓
import PyQt6.QtWebEngineWidgets  # noqa: F401,E402

import pytest  # noqa: E402


def test_quick_entry_order_has_indicator_strategy_after_market_quote():
    """源码顺序：行情报价 → 指标和策略 → 策略回测/参数优化 ✓。"""
    import inspect
    from miniqt.app.view import home_interface as hi
    source = inspect.getsource(hi.HomeInterface.loadSamples)
    i_quote = source.index('title="行情报价"')
    i_ind = source.index('title="指标和策略"')
    i_code = source.index('title="策略回测/参数优化"')
    assert i_quote < i_ind < i_code, '指标和策略必须在行情报价后面 ✓'
    # 卡片参数：路由 key 正确、图标用交易所行情图标（icon 在 title 前 ✓）
    block = source[source.rindex('addSampleCard', 0, i_ind):i_code]
    assert 'icon=FluentIcon.MARKET' in block
    assert 'routeKey="indicatorStrategyInterface"' in block
    # 快捷入口已把 qtvscode 换成「策略回测/参数优化」✓
    assert 'routeKey="qtvscodeInterface"' not in source
    assert 'routeKey="backtestInterface"' in source


def test_quick_entry_card_routes_to_indicator_strategy_page():
    """点击卡片 → switchToSample 导航到指标和策略页 ✓。"""
    from miniqt.app.view.main_window import MainWindow
    navigated = []
    fake = types.SimpleNamespace(
        _navigateTo=lambda widget: navigated.append(widget),
        indicatorStrategyInterface=object(),
    )
    MainWindow.switchToSample(fake, 'indicatorStrategyInterface', 0)
    assert navigated == [fake.indicatorStrategyInterface]


def test_indicator_strategy_page_object_name_matches_route_key():
    """页面的 objectName 就是路由 key（``_navigateTo`` 靠它高亮导航项 ✓）。"""
    import inspect
    from miniqt.app.view.indicator_strategy_interface import (
        IndicatorStrategyInterface)
    source = inspect.getsource(IndicatorStrategyInterface)
    assert 'setObjectName("indicatorStrategyInterface")' in source


def test_quick_entry_backtest_routes_to_backtest_page():
    """快捷入口「策略回测/参数优化」→ ``MainWindow.backtestInterface`` ✓。"""
    from miniqt.app.view.main_window import MainWindow
    navigated = []
    fake = types.SimpleNamespace(
        _navigateTo=lambda widget: navigated.append(widget),
        backtestInterface=object(),
    )
    MainWindow.switchToSample(fake, 'backtestInterface', 0)
    assert navigated == [fake.backtestInterface]
