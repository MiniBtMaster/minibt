# coding:utf-8
"""布局模板：捕获当前布局 / 保存 / 加载（先清空再重建）/ 删除 / 重命名 ✓。"""
from __future__ import annotations

import os
import types

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# 必须在创建 QApplication 之前导入（main_window 会 import 它 ✗）
import PyQt6.QtWebEngineWidgets  # noqa: F401,E402

pytest.importorskip('PyQt6')

from miniqt.app.common.chart_data import ChartDataManager


# ---- 持久化 ----------------------------------------------------------------
def test_layout_templates_persist_rename_delete(tmp_path):
    path = tmp_path / 'chart_data.json'
    manager = ChartDataManager(str(path))
    assert manager.get_layout_templates() == []

    manager.save_layout_template({
        'name': '我的布局', 'layout': 'h2', 'cycle': 60,
        'panels': [{'symbol': 'SHFE.ag2612', 'indicators': []},
                   {'symbol': 'SHFE.au2612', 'indicators': []}]})
    reloaded = ChartDataManager(str(path))
    assert [t['name'] for t in reloaded.get_layout_templates()] == ['我的布局']
    assert reloaded.get_layout_templates()[0]['layout'] == 'h2'

    # 同名覆盖
    manager.save_layout_template({'name': '我的布局', 'layout': 'v2'})
    assert len(manager.get_layout_templates()) == 1
    assert manager.get_layout_templates()[0]['layout'] == 'v2'

    # 重命名 / 删除
    manager.rename_layout_template('我的布局', '改名后')
    assert [t['name'] for t in manager.get_layout_templates()] == ['改名后']
    manager.delete_layout_template('改名后')
    assert manager.get_layout_templates() == []
    # 结构校验：没有 name 的丢掉
    manager.set_layout_templates([{'name': 'a'}, {'layout': 'h2'}, 'x'])
    assert [t['name'] for t in manager.get_layout_templates()] == ['a']


# ---- 捕获 / 保存 / 加载 ----------------------------------------------------
@pytest.fixture()
def layout_env(tmp_path, monkeypatch):
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    import miniqt.app.common.chart_data as chart_data
    manager = ChartDataManager(str(tmp_path / 'chart_data.json'))
    monkeypatch.setattr(chart_data, 'chart_data_manager', manager)

    class _Bar:
        @staticmethod
        def success(*args, **kwargs):
            pass

        @staticmethod
        def warning(*args, **kwargs):
            pass

        @staticmethod
        def info(*args, **kwargs):
            pass

    monkeypatch.setattr(window_module, 'InfoBar', _Bar)
    return window_module, manager


class _Chart:
    def __init__(self, cid):
        self.id = cid


def _capture_window(window_module):
    W = window_module.PylightchartsChartWindow
    a, b = _Chart('a'), _Chart('b')
    window = types.SimpleNamespace(
        cycle=60, _layout_key='h2',
        panels=lambda: [a, b],
        _panel_symbol=lambda chart: {'a': 'SHFE.ag2612',
                                     'b': 'SHFE.au2612'}[chart.id],
        indicators=[{'chart': a, 'spec': {'group': 'TaLib', 'name': 'SMA',
                                          'params': {'length': 9}}},
                    {'chart': b, 'spec': {'group': 'TaLib', 'name': 'RSI',
                                          'params': {'length': 14}}}])
    window.capture_layout_template = types.MethodType(
        W.capture_layout_template, window)
    return window, a, b


def test_capture_layout_template(layout_env):
    window_module, manager = layout_env
    window, _a, _b = _capture_window(window_module)
    template = window.capture_layout_template()
    assert template['layout'] == 'h2'
    assert template['cycle'] == 60
    assert [p['symbol'] for p in template['panels']] == [
        'SHFE.ag2612', 'SHFE.au2612']
    assert template['panels'][0]['indicators'] == [
        {'group': 'TaLib', 'name': 'SMA', 'params': {'length': 9}}]
    assert template['panels'][1]['indicators'][0]['name'] == 'RSI'


def test_save_layout_template(layout_env):
    window_module, manager = layout_env
    window, _a, _b = _capture_window(window_module)
    window.save_layout_template = types.MethodType(
        window_module.PylightchartsChartWindow.save_layout_template, window)
    window.layout_templates = types.MethodType(
        window_module.PylightchartsChartWindow.layout_templates, window)
    window.save_layout_template('布局A')
    assert [t['name'] for t in manager.get_layout_templates()] == ['布局A']
    assert manager.get_layout_templates()[0]['panels'][1]['symbol'] == \
        'SHFE.au2612'


def test_load_layout_template_clears_then_rebuilds(layout_env):
    window_module, manager = layout_env
    W = window_module.PylightchartsChartWindow
    calls = []
    scheduled = []
    ready = []

    class FakeTimer:
        @staticmethod
        def singleShot(ms, fn):
            scheduled.append(fn)

    original = window_module.QTimer
    window_module.QTimer = FakeTimer
    try:
        window = types.SimpleNamespace(
            LAYOUTS=W.LAYOUTS, _defer_ms=0, length=1000, cycle=60,
            data_provider=None, market_watch=None, indicators=[],
            clear_indicators=lambda: calls.append('clear'),
            set_contracts=lambda contracts, **kwargs: calls.append(
                ('contracts', list(contracts), kwargs.get('cycle'))),
            apply_named_layout=lambda key, reset, on_ready=None: (
                calls.append(('layout', key, reset)),
                ready.append(on_ready)),
            panels=lambda: [], refresh_topbar=lambda: None,
            add_indicator_to_manager=lambda *a, **k: None)
        window.load_layout_template = types.MethodType(
            W.load_layout_template, window)
        template = {'name': 'T', 'layout': 'v2', 'cycle': 300,
                    'panels': [{'symbol': 'SHFE.ag2612',
                                'indicators': [{'group': 'G', 'name': 'N',
                                                'params': {}}]}]}
        assert window.load_layout_template(template) is True
        # 先清空，再设合约/周期，再按布局重建（reset=True → 先清格 ✓）
        assert calls[0] == 'clear'
        assert calls[1] == ('contracts', ['SHFE.ag2612'], 300)
        assert calls[2] == ('layout', 'v2', True)
        assert ready and callable(ready[0])     # ready 驱动加指标 ✓
    finally:
        window_module.QTimer = original


# ---- 管理页面 --------------------------------------------------------------
def test_layout_templates_dialog_lists_and_operates(layout_env):
    window_module, manager = layout_env
    dialogs = pytest.importorskip(
        'miniqt.app.windows.layout_templates_dialog')
    from PyQt6.QtWidgets import QApplication, QWidget

    manager.save_layout_template({
        'name': '布局A', 'layout': 'h2', 'cycle': 60,
        'panels': [{'symbol': 'SHFE.ag2612',
                    'indicators': [{'group': 'TaLib', 'name': 'SMA',
                                    'params': {'length': 9}}]},
                   {'symbol': 'SHFE.au2612', 'indicators': []}]})

    loaded = []
    favorites = []
    deleted = []

    class Window:
        @staticmethod
        def layout_templates():
            return manager.get_layout_templates()

        @staticmethod
        def load_layout_template(template):
            loaded.append(template.get('name'))

        @staticmethod
        def set_layout_template_favorite(name, favorite=True):
            favorites.append((name, favorite))
            return manager.set_layout_template_favorite(name, favorite)

        @staticmethod
        def delete_layout_template(name):
            deleted.append(name)
            return manager.delete_layout_template(name)

    manager.save_layout_template({
        'name': '布局B', 'layout': 'single', 'cycle': 300,
        'panels': [{'symbol': 'DCE.i2609', 'indicators': []}]})

    parent = QWidget()
    dialog = dialogs.LayoutTemplatesDialog(Window(), parent=parent)
    QApplication.processEvents()
    assert dialog.list.count() == 2
    # 底部没有「关闭」按钮（右上角已有 ✕ 关闭 ✓）
    assert dialog.cancelButton.isHidden() and dialog.yesButton.isHidden()

    def _row(index):
        return dialog.list.itemWidget(dialog.list.item(index))

    row = _row(0)
    assert row.nameLabel.text() == '布局A'
    # 每条记录带边框；悬浮底色与预警记录一致 ✓
    assert 'border:1px solid' in row.styleSheet()
    assert 'border:1px solid' in dialogs._row_qss('layoutTemplateRow')
    assert 'rgba(128,128,128,0.12)' in dialogs._row_qss(
        'layoutTemplateRow', True)
    assert 'SHFE.ag2612' in row.detailLabel.text()
    assert 'SMA' in row.detailLabel.text()
    # 星标 / 重命名 / 删除 都在；操作按钮默认隐藏（悬停才显 ✓）
    assert row.star is not None and row.renameButton is not None
    assert row.deleteButton is not None
    assert row.renameButton.isHidden() is True
    row.renameButton.show()
    assert row.renameButton.isHidden() is False

    # 搜索过滤
    dialog.searchEdit.setText('布局B')
    QApplication.processEvents()
    assert dialog.list.count() == 1
    assert _row(0).nameLabel.text() == '布局B'
    dialog.searchEdit.setText('')
    QApplication.processEvents()
    assert dialog.list.count() == 2

    # 收藏（星标）
    dialog.toggle_favorite(row.template)
    assert favorites and favorites[0] == ('布局A', True)
    assert _row(0).star.text() == '★'

    # 点行 = 加载 ✓
    dialog.load_template(row.template)
    assert loaded == ['布局A']

    # 删除
    dialog.delete_template(row.template)
    assert deleted == ['布局A']
    assert dialog.list.count() == 1
    dialog.close()

    # 保存窗口：名称为空时不可保存；填了 / 给了默认名才能 ✓
    save = dialogs.SaveLayoutDialog(summary='布局：左右', parent=parent)
    assert save.yesButton.isEnabled() is False
    save.nameBox.setText('我的布局')
    assert save.yesButton.isEnabled() is True
    assert save.name() == '我的布局'
    save.close()
    # 已有模板名能下拉选；默认名预填（时间戳）→ 打开即可保存 ✓
    save2 = dialogs.SaveLayoutDialog(
        summary='布局：左右', default_name='布局 2026-10-09 11:30',
        names=['布局A', '布局B'], parent=parent)
    assert save2.yesButton.isEnabled() is True
    assert save2.name() == '布局 2026-10-09 11:30'
    assert save2.nameBox.count() == 2           # 列出已有模板 ✓
    assert save2.nameBox.itemText(0) == '布局A'
    # 选中已有模板 → 名称跟着变（同名保存 = 覆盖 ✓）
    save2.nameBox.setCurrentIndex(1)
    assert save2.name() == '布局B'
    save2.close()


# ---- 首页卡片 + 打开模板（需要登录）---------------------------------------
def test_home_rebuilds_layout_template_cards(layout_env):
    window_module, manager = layout_env
    from miniqt.app.view.home_interface import HomeInterface

    manager.save_layout_template({
        'name': '布局A', 'layout': 'h2', 'cycle': 60,
        'panels': [{'symbol': 'SHFE.ag2612', 'indicators': []},
                   {'symbol': 'SHFE.au2612', 'indicators': []}]})

    events = []

    class View:
        flowLayout = types.SimpleNamespace(
            takeAllWidgets=lambda: events.append('clear'))

        def addSampleCard(self, **kwargs):
            events.append(kwargs)

        def setVisible(self, _visible):
            pass

    window = types.SimpleNamespace(layoutTemplatesView=View())
    window._layout_template_content = HomeInterface._layout_template_content
    HomeInterface._rebuild_layout_templates(window)

    assert events[0] == 'clear'
    cards = [e for e in events if isinstance(e, dict)]
    assert len(cards) == 1
    assert cards[0]['title'] == '布局A'
    assert cards[0]['routeKey'] == 'layoutTemplate'
    assert cards[0]['index'] == 0
    assert 'SHFE.ag2612' in cards[0]['content']


def test_open_layout_template_checks_login_then_opens(layout_env, monkeypatch):
    window_module, manager = layout_env
    from miniqt.app.view import main_window as mw

    manager.save_layout_template({
        'name': '布局A', 'layout': 'v2', 'cycle': 300, 'is_stock': False,
        'panels': [{'symbol': 'SHFE.ag2612', 'indicators': []},
                   {'symbol': 'SHFE.au2612', 'indicators': []}]})

    window = mw.MainWindow.__new__(mw.MainWindow)
    window._layout_templates = types.MethodType(
        mw.MainWindow._layout_templates, window)
    window.open_layout_template = types.MethodType(
        mw.MainWindow.open_layout_template, window)
    window._apply_layout_template = types.MethodType(
        mw.MainWindow._apply_layout_template, window)

    # 未登录 → 只弹登录，不打开图表
    opened = []
    window.show_login_window = lambda is_stock=False: True
    window.start_minibt_chart = lambda *a, **k: opened.append('open')
    window.open_layout_template(0)
    assert opened == []

    # 已登录 → 打开图表并把模板**一起传进去**（无固定延时；数据后台取 ✓）
    captured = {}

    def fake_start(symbol, **kwargs):
        captured['symbol'] = symbol
        captured.update(kwargs)
        return types.SimpleNamespace(chart_window=object())

    window.show_login_window = lambda is_stock=False: False
    window.start_minibt_chart = fake_start
    window.open_layout_template(0)
    assert captured['symbol'] == 'SHFE.ag2612'
    assert captured['cycle'] == 300
    assert captured['template']['name'] == '布局A'
    assert captured['template']['layout'] == 'v2'
    assert captured['force_new'] is True        # 首页点模板 → 总是新建窗口 ✓


# ---- 下拉菜单辅助方法 ------------------------------------------------------
def test_favorites_and_load_by_name(layout_env):
    window_module, manager = layout_env
    W = window_module.PylightchartsChartWindow
    manager.save_layout_template({'name': '布局A', 'layout': 'h2',
                                  'favorite': True, 'panels': []})
    manager.save_layout_template({'name': '布局B', 'layout': 'single',
                                  'panels': []})

    loaded = []
    window = types.SimpleNamespace(_layout_template_name='布局A')
    for name in ('layout_templates', 'favorite_layout_templates',
                 'current_layout_template_name',
                 'load_layout_template_by_name'):
        setattr(window, name, types.MethodType(getattr(W, name), window))
    window.load_layout_template = lambda t: loaded.append(t.get('name'))

    assert [t['name'] for t in window.favorite_layout_templates()] == ['布局A']
    # 和当前同名 → 不重复加载 ✓
    window.load_layout_template_by_name('布局A')
    assert loaded == []
    # 不同 → 加载 ✓
    window.load_layout_template_by_name('布局B')
    assert loaded == ['布局B']


def test_copy_current_layout_template(layout_env):
    window_module, manager = layout_env
    W = window_module.PylightchartsChartWindow
    captured = []
    window = types.SimpleNamespace(_layout_template_name='布局A')
    window.current_layout_template_name = types.MethodType(
        W.current_layout_template_name, window)
    window.show_save_layout_dialog = lambda default_name=None: captured.append(
        default_name)
    window.copy_current_layout_template = types.MethodType(
        W.copy_current_layout_template, window)
    window.copy_current_layout_template()
    assert captured == ['布局A 副本']


def test_set_layout_template_favorite(layout_env):
    window_module, manager = layout_env
    W = window_module.PylightchartsChartWindow
    manager.save_layout_template({'name': '布局A', 'layout': 'h2',
                                  'panels': []})
    window = types.SimpleNamespace()
    window.layout_templates = types.MethodType(W.layout_templates, window)
    window.favorite_layout_templates = types.MethodType(
        W.favorite_layout_templates, window)
    window.set_layout_template_favorite = types.MethodType(
        W.set_layout_template_favorite, window)
    window.set_layout_template_favorite('布局A', True)
    assert [t['name'] for t in window.favorite_layout_templates()] == ['布局A']
    window.set_layout_template_favorite('布局A', False)
    assert window.favorite_layout_templates() == []
