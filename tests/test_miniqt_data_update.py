# coding: utf-8
"""「数据更新」相关测试：设置页按钮 + 合约全量刷新回调 / 广播 ✓。

行情报价的合约表在**每天首次登录**时全量刷新一次（`database_meta`
的 ``contracts_refreshed_on`` = 当天日期）；这里只测设置页触发的**手动强制**
刷新链路，不碰真实天勤。
"""
from __future__ import annotations

import os
import types

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

pytest.importorskip('PyQt6')


def test_signal_bus_has_contracts_refreshed():
    from miniqt.app.common.signal_bus import signalBus
    assert hasattr(signalBus, 'contractsRefreshed')


def test_data_update_group_and_card():
    """设置-数据设置里有「数据更新 → 更新报价类型和交易所」卡片 ✓。"""
    setting_mod = pytest.importorskip('miniqt.app.view.setting_interface')
    w = setting_mod.DataSettingInterface()
    try:
        assert hasattr(w, 'dataUpdateGroup')
        assert hasattr(w, 'refreshContractsCard')
        assert '更新报价类型和交易所' in w.refreshContractsCard.titleLabel.text()
        # 卡片挂在「数据更新」组里 ✓
        assert w.refreshContractsCard.parent() is w.dataUpdateGroup
        # 「更新」按钮存在且可用 ✓
        assert w.refreshContractsCard.button.text() == '更新'
    finally:
        w.deleteLater()


def test_refresh_button_starts_background_update():
    """点「更新」→ 强制后台刷新 + 完成后恢复按钮 ✓。"""
    setting_mod = pytest.importorskip('miniqt.app.view.setting_interface')
    w = setting_mod.DataSettingInterface()
    try:
        calls = {}

        class _FakeMarket:
            def is_refreshing_contracts(self):
                return False

            def refresh_contracts_from_tq(self, force=False,
                                          on_finished=None):
                calls['force'] = force
                calls['cb'] = on_finished
                return True

        w.setting_interface = types.SimpleNamespace(
            marketQuoteInterface=_FakeMarket(), tq_api=object())
        w._DataSettingInterface__onRefreshContractsClicked()
        assert calls.get('force') is True          # 强制刷新 ✓
        assert callable(calls.get('cb'))           # 登记了完成回调 ✓
        # 完成后按钮恢复可用 ✓
        calls['cb'](2, 1)
        assert w.refreshContractsCard.button.isEnabled() is True
    finally:
        w.deleteLater()


def test_refresh_finished_calls_callback_and_broadcasts():
    """全量刷新收尾：调用 ``on_finished(success, empty)`` 并广播 ✓。"""
    market_mod = pytest.importorskip(
        'miniqt.app.view.market_quote_interface')
    from miniqt.app.common.signal_bus import signalBus

    MarketQuoteInterface = market_mod.MarketQuoteInterface
    host = types.SimpleNamespace()
    host._MarketQuoteInterface__onSegmentedChanged = lambda: None
    got = []
    host._refresh_state = {
        'date': '2026-10-11', 'success': 0, 'empty': 2,
        'on_finished': lambda success, empty: got.append((success, empty)),
    }
    fired = []
    fn = lambda: fired.append(True)                          # noqa: E731
    signalBus.contractsRefreshed.connect(fn)
    try:
        MarketQuoteInterface._on_refresh_finished(host)
    finally:
        signalBus.contractsRefreshed.disconnect(fn)

    assert got == [(0, 2)]                # 回调带 (成功, 空) ✓
    assert fired                          # 广播发出 ✓
    assert host._refresh_state is None    # 状态已清理 ✓


def test_is_refreshing_contracts():
    market_mod = pytest.importorskip(
        'miniqt.app.view.market_quote_interface')
    host = types.SimpleNamespace(_refresh_state=None)
    assert market_mod.MarketQuoteInterface.is_refreshing_contracts(host) is False
    host._refresh_state = {'index': 0}
    assert market_mod.MarketQuoteInterface.is_refreshing_contracts(host) is True


def test_quote_preview_refreshes_on_contracts_refreshed():
    """报价预览页也监听 ``contractsRefreshed`` 并刷新（分类 + 表格 ✓）。"""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app'
           / 'view' / 'market_quote_preview.py').read_text(encoding='utf-8')
    assert 'signalBus.contractsRefreshed.connect(self.on_cont_quotes_updated)' \
        in src


def test_market_watch_reloads_search_data_on_refresh():
    """看盘窗口监听了 ``contractsRefreshed`` 并在刷新后重载搜索数据 ✓。"""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app'
           / 'windows' / 'pylightcharts_market_watch.py').read_text(
               encoding='utf-8')
    assert 'contractsRefreshed.connect(self._reload_search_data)' in src
    assert 'def _reload_search_data' in src
    # 重载时也要清掉合约校验缓存（否则还是旧表 ✗）
    assert '_quote_key_cache = None' in src
