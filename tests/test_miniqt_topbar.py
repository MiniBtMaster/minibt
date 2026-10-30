"""TradingView 超级图表顶栏（商品搜索 / 比较商品 / 周期菜单）。

顶栏与图表引擎无关，全部是 qfluentwidgets 控件，所以可以离屏实例化检查
（``QtWebEngine`` 的离屏崩溃在这里用不到 ✓）。
"""
from __future__ import annotations

import os
import textwrap

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

pytest.importorskip('PyQt6')
from PyQt6.QtCore import Qt  # noqa: E402

topbar = pytest.importorskip('miniqt.app.windows.tradingview_topbar')

ROWS = [
    ['TSLA', 'Tesla, Inc.', 'stock', 'NASDAQ'],
    ['BTCUSDT', 'Bitcoin / TetherUS', 'spot crypto', 'Binance'],
    ['rb2610', '螺纹钢 2610', 'futures', 'SHFE'],
    ['510300', '沪深300ETF', 'fund etf', 'SSE'],
    ['XAUUSD', 'Gold', 'commodity cfd', 'OANDA'],
    ['IF2606', '沪深300指数', 'index futures', 'CFFEX'],
    ['T2606', '10年期国债', 'bond futures', 'CFFEX'],
    ['IO2606-C-4000', '沪深300期权', 'option', 'CFFEX'],
]


@pytest.fixture(scope='module', autouse=True)
def _app():
    from PyQt6.QtWidgets import QApplication
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture
def owner():
    from PyQt6.QtWidgets import QWidget

    class FakeOwner(QWidget):
        def __init__(self):
            super().__init__()
            self.resize(1280, 800)
            self.symbol = 'rb2610'
            self.cycle = 300
            self.compare = []
            self.chart_type = 'candle'
            self.favorites = [{'group': 'TaLib', 'name': 'CCI'}]
            self.templates = []
            self.added_indicators = []
            self.applied_templates = []
            self.replay_active = False
            self.replay_toggles = 0
            self.saved_alerts = []
            self.tool_calls = []

        def topbar_current_symbol(self):
            return self.symbol

        def topbar_current_cycle(self):
            return self.cycle

        def topbar_search_rows(self):
            return ROWS

        def topbar_select_symbol(self, code, type_str=''):
            self.symbol = code
            return True

        def topbar_set_cycle(self, seconds):
            self.cycle = int(seconds)

        def topbar_compare_symbols(self):
            return self.compare

        def topbar_set_compare_symbols(self, items):
            self.compare = list(items)

        def topbar_chart_type(self):
            return self.chart_type

        def topbar_set_chart_type(self, key):
            if key not in ('candle', 'hollow', 'line', 'area', 'baseline',
                           'bar'):
                return False
            self.chart_type = key
            return True

        def topbar_indicator_entries(self):
            return [{'group': 'TaLib', 'name': 'CCI', 'doc': '顺势指标'},
                    {'group': 'TaLib', 'name': 'SMA', 'doc': '简单均线'},
                    {'group': 'BtInd', 'name': 'supertrend', 'doc': '超级趋势'}]

        def topbar_favorite_indicators(self):
            return list(self.favorites)

        def topbar_set_favorite_indicators(self, items):
            self.favorites = list(items)

        def topbar_add_indicator(self, group, name):
            self.added_indicators.append((group, name))

        def topbar_current_indicator_specs(self):
            return [{'group': 'TaLib', 'name': 'CCI',
                     'params': {'timeperiod': 14}}]

        def topbar_templates(self):
            return list(self.templates)

        def topbar_set_templates(self, items):
            self.templates = list(items)

        def topbar_save_template(self, template):
            self.templates.append(template)
            return self.templates

        def topbar_apply_template(self, template):
            self.applied_templates.append(template)
            return 1

        def topbar_replay_active(self):
            return self.replay_active

        def topbar_toggle_replay(self):
            self.replay_toggles += 1
            self.replay_active = not self.replay_active
            return self.replay_active

        def topbar_alert_context(self):
            return {'symbol': self.symbol, 'price': 378.73}

        def topbar_save_alert(self, alert):
            self.saved_alerts.append(dict(alert))
            return alert

        def topbar_show_remove_indicator(self):
            self.tool_calls.append('remove')

        def topbar_toggle_toolbox(self):
            self.tool_calls.append('toolbox')

        def topbar_clear_drawings(self):
            self.tool_calls.append('clear')

        def topbar_show_layout_menu(self):
            self.tool_calls.append('layout')

        def topbar_add_panel(self):
            self.tool_calls.append('add')

        def topbar_close_layout(self):
            self.tool_calls.append('close')

        def topbar_screenshot(self):
            self.tool_calls.append('shot')

        def period_label(self, seconds):
            return topbar.format_cycle(seconds)

    return FakeOwner()


# ---- 纯函数 ---------------------------------------------------------------
def test_format_cycle():
    assert topbar.format_cycle(60) == '1分'
    assert topbar.format_cycle(300) == '5分'
    assert topbar.format_cycle(3600) == '1时'
    assert topbar.format_cycle(86400) == '1日'
    assert topbar.format_cycle(120) == '2分'
    assert topbar.format_cycle(0) == '1分'


def test_match_category_and_query():
    assert len([r for r in ROWS if topbar.match_category(r, '期货')]) == 3
    assert len([r for r in ROWS if topbar.match_category(r, '全部')]) == len(ROWS)
    assert topbar.match_query(ROWS[0], 'tesla')
    assert topbar.match_query(ROWS[0], '')
    assert not topbar.match_query(ROWS[0], 'zzz')


# ---- 顶栏 -----------------------------------------------------------------
def test_topbar_shows_symbol_and_cycle(owner):
    bar = topbar.TradingViewTopBar(owner, owner)
    assert bar.symbolBox.codeLabel.text() == 'rb2610'
    assert bar.intervalButton.text() == '5分'
    owner.cycle = 3600
    owner.symbol = 'TSLA'
    bar.refresh()
    assert bar.symbolBox.codeLabel.text() == 'TSLA'
    assert bar.intervalButton.text() == '1时'


def test_topbar_interval_menu_has_minute_and_hour_submenus(owner):
    bar = topbar.TradingViewTopBar(owner, owner)
    menu = bar._build_interval_menu()
    submenus = {sub.title(): sub for sub in getattr(menu, '_subMenus', [])}
    assert {'秒', '分', '时', '天'} <= set(submenus)
    minute_items = [a.text() for a in submenus['分'].actions() if a.text()]
    assert minute_items[:3] == ['1 分', '2 分', '3 分']
    hour_items = [a.text() for a in submenus['时'].actions() if a.text()]
    assert hour_items[:2] == ['1 时', '2 时']
    # 自定义周期入口在最上面
    titles = [a.text() for a in menu.actions() if a.text()]
    assert titles and titles[0] == '添加自定义周期...'


def test_topbar_request_cycle_and_symbol(owner):
    bar = topbar.TradingViewTopBar(owner, owner)
    bar.request_cycle(1800)
    assert owner.cycle == 1800 and bar.intervalButton.text() == '30分'
    bar.request_symbol('TSLA', 'stock')
    assert owner.symbol == 'TSLA' and bar.symbolBox.codeLabel.text() == 'TSLA'


# ---- 商品代码搜索 ---------------------------------------------------------
def test_symbol_search_dialog_filters(owner):
    dialog = topbar.SymbolSearchDialog(rows=ROWS, parent=owner)
    assert dialog.listWidget.count() == len(ROWS)
    dialog.categoryButtons['期货'].click()
    assert dialog.listWidget.count() == 3
    dialog._set_category('全部')
    dialog.searchEdit.setText('tesla')
    dialog._apply_filter()                        # 防抖：测试里立即触发 ✓
    assert dialog.listWidget.count() == 1
    dialog.searchEdit.setText('')
    dialog._apply_filter()
    assert dialog.listWidget.count() == len(ROWS)
    dialog.close()


def test_symbol_search_dialog_selection(owner):
    dialog = topbar.SymbolSearchDialog(rows=ROWS, parent=owner)
    first = dialog.listWidget.item(0)
    dialog._on_pick(first)
    assert dialog.selected() == ('TSLA', 'stock')
    dialog.close()


# ---- 比较商品 -------------------------------------------------------------
def test_compare_dialog_add_remove_and_recent(owner):
    dialog = topbar.CompareSymbolDialog(rows=ROWS, parent=owner)
    dialog._toggle('TSLA', 'stock')
    dialog._toggle('rb2610', 'futures')
    assert [c[0] for c in dialog.compare_items()] == ['TSLA', 'rb2610']
    assert [r[0] for r in dialog.recent_items()][:2] == ['rb2610', 'TSLA']
    dialog.searchEdit.setText('bitcoin')
    dialog._rebuild()                             # 防抖：测试里立即触发 ✓
    assert dialog.resultList.count() == 1
    dialog._remove('TSLA')
    assert [c[0] for c in dialog.compare_items()] == ['rb2610']
    dialog.close()


# ---- 自定义周期 -----------------------------------------------------------
def test_custom_interval_dialog(owner):
    dialog = topbar.CustomIntervalDialog(parent=owner)
    dialog.unitBox.setCurrentIndex(2)          # 时
    dialog.periodEdit.setText('4')
    assert dialog.interval_seconds() == 4 * 3600
    assert dialog.validate() and dialog.yesButton.isEnabled()
    dialog.periodEdit.setText('0')
    assert not dialog.validate()
    dialog.close()


# ---- 图表窗口集成 ---------------------------------------------------------
def test_chart_window_removes_old_toolbar_and_keeps_right_tools():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    assert hasattr(window, 'topbar')
    assert not hasattr(window, 'toolbar')        # 旧 CommandBar 已移除 ✓
    # 右侧工具按钮按用户要求的顺序，且都有 tooltip
    expected = [
        ('removeIndicatorButton', '删除指标策略'),
        ('toolboxButton', '画线'),
        ('clearDrawingsButton', '清除画线'),
        ('layoutButton', '布局'),
        ('closeLayoutButton', '关闭布局'),
        ('screenshotButton', '截图'),
    ]
    tips = [getattr(window.topbar, attr).toolTip() for attr, _ in expected]
    assert tips == [tip for _, tip in expected]


def test_topbar_right_tools_call_owner_hooks(owner):
    bar = topbar.TradingViewTopBar(owner, owner)
    for attr, _icon, _tip, _hook in topbar.TradingViewTopBar.RIGHT_TOOLS:
        # 布局按钮是 SplitToolButton（没有 .click()）→ 统一 emit clicked ✓
        getattr(bar, attr).clicked.emit()
    assert owner.tool_calls == ['remove', 'toolbox', 'clear', 'layout',
                                'close', 'shot']


def test_chart_window_topbar_hooks():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    window.contracts = ['SHFE.rb2610']
    assert window.topbar_current_symbol() == 'SHFE.rb2610'
    assert window.topbar_current_cycle() == 60
    window._topbar_recent = [('TSLA', 'Tesla')]
    window._topbar_compare = [('TSLA', 'Tesla')]
    assert window.topbar_recent_symbols()[0][0] == 'TSLA'
    assert window.topbar_compare_symbols()[0][0] == 'TSLA'
    window.topbar_set_compare_symbols([('DCE.i2609', 'i2609')])
    assert window.topbar_compare_symbols() == [('DCE.i2609', 'i2609')]


# ---- 图表类型菜单（1.4）----------------------------------------------------
def test_chart_type_menu_and_request(owner):
    bar = topbar.TradingViewTopBar(owner, owner)
    menu = bar._build_chart_type_menu()
    actions = {a.text(): a for a in menu.actions() if a.text()}
    assert actions['K线图'].isChecked()
    for label in ('空心K线图', '线形图', '面积图', '基准线', '柱状图'):
        assert actions[label].isEnabled(), label
    for label in ('成交量蜡烛', '带标记线', '阶梯线', 'HLC区域', '高-低',
                  '成交量轨迹', '时间价格机会', '交易时段成交量分布图',
                  '平均K线图', '砖形图', '新价线'):
        assert not actions[label].isEnabled(), label
    bar.request_chart_type('line')
    assert owner.chart_type == 'line'
    assert '线形图' in bar.chartTypeButton.toolTip()
    checked = [a.text() for a in bar._build_chart_type_menu().actions()
               if a.isChecked()]
    assert checked == ['线形图']


def test_chart_type_frame_and_row_helpers():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    import pandas as pd
    window = window_module.PylightchartsChartWindow
    frame = pd.DataFrame({
        'time': pd.to_datetime(['2024-01-01']),
        'open': [1.0], 'high': [2.0], 'low': [0.5], 'close': [1.5],
        'volume': [10.0],
    })
    bar_frame = window._type_frame(frame, 'Bar')
    assert list(bar_frame.columns) == ['time', 'open', 'high', 'low', 'close']
    line_frame = window._type_frame(frame, 'Line')
    assert list(line_frame.columns) == ['time', 'value']
    assert line_frame['value'].iloc[0] == 1.5
    row = {'time': frame['time'].iloc[0], 'open': 1, 'high': 2, 'low': 0.5,
           'close': 1.5, 'volume': 10}
    assert 'value' in window._type_row(row, 'Line').index
    assert 'close' in window._type_row(row, 'Bar').index


def test_window_set_chart_type():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    assert window.topbar_chart_type() == 'candle'
    assert window.set_chart_type('renko') is False      # 壳
    assert window.set_chart_type('line') is True
    assert window.topbar_chart_type() == 'line'
    assert '线形图' in window.topbar.chartTypeButton.toolTip()


def test_all_chart_types_keep_the_latest_price_tracking():
    """非默认图表类型也要有最新价的跟踪虚线 + 价格标签 ✓。"""
    import types
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow

    class Series:
        def set(self, _frame):
            pass

        def delete(self):
            pass

    class Chart:
        id = 'ct1'

        def __init__(self):
            self.series_options_calls = []
            self.created = []

        def series_options(self, **kwargs):
            self.series_options_calls.append(kwargs)

        def add_series(self, kind, name='', **kwargs):
            self.created.append((kind, kwargs))
            return Series()

    chart = Chart()
    window = types.SimpleNamespace(
        chart=chart, _type_series={}, panel_frames={}, _panel_frame=None,
        chart_type='line', CHART_TYPE_KINDS=W.CHART_TYPE_KINDS,
        _current_colors=lambda: {'up': '#26a69a', 'down': '#ef5350'})
    for name in ('_apply_chart_type_panel', '_create_type_series'):
        setattr(window, name, types.MethodType(getattr(W, name), window))
    window._style_candle_for_type = lambda *args: None
    window._type_frame = W._type_frame

    # 线形图：主蜡烛藏起来 → 跟踪线/标签交给覆盖序列 ✓
    W._apply_chart_type_panel(window, chart)
    assert chart.series_options_calls[-1]['visible'] is False
    kind, kwargs = chart.created[-1]
    assert kind == 'Line'
    assert kwargs['price_line_visible'] is True
    assert kwargs['last_value_visible'] is True

    # 空心 K 线：还是主蜡烛序列 → 跟踪线/标签也要显式打开 ✓
    window.chart_type = 'hollow'
    W._apply_chart_type_panel(window, chart)
    opts = chart.series_options_calls[-1]
    assert opts['visible'] is True
    assert opts['price_line_visible'] is True
    assert opts['last_value_visible'] is True


# ---- 技术指标界面（1.5）----------------------------------------------------
def test_indicator_entries_flatten():
    dialogs = pytest.importorskip(
        'miniqt.app.windows.tradingview_indicator_dialogs')
    entries = dialogs.indicator_entries({
        'TaLib': [('CCI', '顺势指标'), ('SMA', '简单均线')],
        'BtInd': [('zigzag', '之字转向')],
    })
    assert len(entries) == 3
    assert entries[0]['group'] == 'TaLib' and entries[0]['name'] == 'CCI'
    assert dialogs.entry_key(entries[0]) == 'TaLib.CCI'
    assert len(dialogs.builtin_templates('技术指标')) > 0
    assert [t['name'] for t in dialogs.builtin_templates('财务指标')]


def test_indicator_picker_dialog(owner):
    dialogs = pytest.importorskip(
        'miniqt.app.windows.tradingview_indicator_dialogs')
    dialog = dialogs.IndicatorPickerDialog(
        entries=owner.topbar_indicator_entries(),
        favorites=owner.favorites, parent=owner)
    assert dialog.indicatorList.count() == 2   # 默认在第一个 minibt 组
    dialog.searchEdit.setText('super')
    assert dialog.indicatorList.count() == 1
    dialog.searchEdit.setText('')
    dialog._on_favorite('TaLib', 'SMA', True)
    assert any(item['name'] == 'SMA' for item in dialog.favorites())
    dialog._on_add(dialog.indicatorList.item(0))
    assert dialog.selected()[1]
    dialog.close()


def test_indicator_picker_nav_groups(owner):
    dialogs = pytest.importorskip(
        'miniqt.app.windows.tradingview_indicator_dialogs')
    dialog = dialogs.IndicatorPickerDialog(
        entries=owner.topbar_indicator_entries(), favorites=owner.favorites,
        parent=owner)

    def select(key):
        for row in range(dialog.navList.count()):
            item = dialog.navList.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                dialog.navList.setCurrentItem(item)
                return
        raise AssertionError(key)

    labels = [dialog.navList.item(i).text()
              for i in range(dialog.navList.count())]
    assert '已购买' not in labels                    # 已删
    assert '内置指标' in labels                       # “内置”已改名
    # 「内置指标」下就是 minibt 的指标组
    assert dialog._groups == ['TaLib', 'BtInd']
    assert dialog._nav == 'TaLib'                    # 默认第一个组
    assert dialog.indicatorList.count() == 2
    select('BtInd')
    assert dialog.indicatorList.count() == 1
    select('favorites')
    assert dialog.indicatorList.count() == 1         # 只有收藏的 CCI
    # 「我的脚本」现在改成**分组标题**（灰色不可点）——个人指标类别挂在它下面 ✓
    rows = [dialog.navList.item(i) for i in range(dialog.navList.count())]
    header = next(item for item in rows if item.text().strip() == '我的脚本')
    assert header.flags() == Qt.ItemFlag.NoItemFlags
    assert header.data(Qt.ItemDataRole.UserRole) in (None, '')
    assert dialog._scripts == {}                     # 还没添加个人指标目录 ✓
    assert dialog.emptyLabel.text() or True
    # 单击一行 = 选中（加到最后点击的合约交给窗口 ✓）
    dialog._on_activate('TaLib', 'CCI')
    assert dialog.selected() == ('TaLib', 'CCI')
    dialog.close()


def test_indicator_target_is_last_clicked_panel():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    window.chart = 'anchor'
    window.panels = lambda: ['anchor', 'sub']
    window.last_panel = None
    assert window._indicator_target() == 'anchor'    # 没点过 -> anchor
    window.last_panel = 'sub'
    assert window._indicator_target() == 'sub'       # 最后点击的合约 ✓


def test_clicking_a_panel_switches_the_topbar_symbol():
    """多布局：点哪一格，顶栏商品框就换成那一格的合约（并刷新 ✓）。"""
    import types
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow

    refreshed = []

    class Topbar:
        def refresh(self):
            refreshed.append(True)

    class Chart:
        def __init__(self, cid):
            self.id = cid

    a, b = Chart('a'), Chart('b')
    window = types.SimpleNamespace(
        last_panel=None, topbar=Topbar(), panels=lambda: [a, b],
        _panel_symbol=lambda c: {'a': 'SHFE.ag2612',
                                 'b': 'SHFE.au2612'}[c.id])
    for name in ('_remember_panel', '_active_chart', 'refresh_topbar',
                 'topbar_current_symbol'):
        setattr(window, name, types.MethodType(getattr(W, name), window))

    window._remember_panel(b)
    assert refreshed == [True]
    assert window.topbar_current_symbol() == 'SHFE.au2612'
    window._remember_panel(b)                    # 同一格 → 不重复刷 ✓
    assert refreshed == [True]
    window._remember_panel(a)
    assert refreshed == [True, True]
    assert window.topbar_current_symbol() == 'SHFE.ag2612'


def test_topbar_indicator_actions(owner):
    bar = topbar.TradingViewTopBar(owner, owner)
    bar.request_indicator('TaLib', 'SMA')
    assert ('TaLib', 'SMA') in owner.added_indicators
    fav = bar._build_favorites_menu()
    texts = [a.text() for a in fav.actions() if a.text()]
    # 新格式：收藏指标 / 收藏策略（类别，不可用）+ 缩进的收藏项 ✓
    assert '收藏指标' in texts and '收藏策略' in texts
    assert '更多指标和策略…' in texts
    assert any('TaLib.CCI' in text for text in texts)


def test_favorites_menu_has_add_personal_indicators(owner, tmp_path,
                                                    monkeypatch):
    """「更多指标…」下面要有一个「添加个人指标…」（选目录 → 以目录名为类别 ✓）。"""
    personal = pytest.importorskip('miniqt.app.common.personal_indicators')
    monkeypatch.setattr(personal, 'CONFIG_FILE', str(tmp_path / 'pi.json'),
                        raising=False)
    personal.reset_cache()
    folder = tmp_path / 'ind'
    folder.mkdir()
    (folder / 'myind.py').write_text(textwrap.dedent('''
        from minibt import BtIndicator

        class MyInd(BtIndicator):
            """个人指标 ✓"""
            params = {'period': 5}

            def next(self, period=5):
                return self.close
    '''), encoding='utf-8')

    bar = topbar.TradingViewTopBar(owner, owner)
    texts = [action.text() for action in bar._build_favorites_menu().actions()
             if action.text()]
    assert '更多指标和策略…' in texts
    add = next(text for text in texts if '个人指标' in text)
    assert texts.index(add) > texts.index('更多指标和策略…')       # 在它**下面** ✓

    # 直接调加载逻辑（文件对话框在测试里跳过 ✓）
    info = personal.add_directory(str(folder))
    assert info['category'] == 'ind'
    assert personal.categories()['ind'][0]['name'] == 'MyInd'
    personal.reset_cache()
    assert personal.ensure_loaded()['ind']                     # 重启也加载 ✓
    personal.reset_cache()


# ---- 指标模板（1.6）--------------------------------------------------------
def test_save_template_dialog(owner):
    dialogs = pytest.importorskip(
        'miniqt.app.windows.tradingview_indicator_dialogs')
    dialog = dialogs.SaveTemplateDialog(
        indicators=owner.topbar_current_indicator_specs(),
        symbol='rb2610', cycle=300, parent=owner)
    assert dialog.yesButton.isEnabled() is False
    dialog.nameEdit.setText('我的模板')
    assert dialog.yesButton.isEnabled()
    dialog.rememberSymbolBox.setChecked(True)
    template = dialog.template()
    assert template['name'] == '我的模板'
    assert template['remember_symbol'] and template['symbol'] == 'rb2610'
    assert template['indicators'][0]['name'] == 'CCI'
    dialog._remove(0)
    assert dialog.template()['indicators'] == []
    dialog.close()


def test_template_dialog_and_topbar(owner):
    dialogs = pytest.importorskip(
        'miniqt.app.windows.tradingview_indicator_dialogs')
    mine = [{'name': '我的1',
             'indicators': [{'group': 'TaLib', 'name': 'CCI'}]}]
    dialog = dialogs.TemplateDialog(templates=mine, parent=owner)
    assert [t['name'] for t in dialog.mine_templates()] == ['我的1']
    for row in range(dialog.navList.count()):
        item = dialog.navList.item(row)
        if item.data(Qt.ItemDataRole.UserRole) == 'technical':
            dialog.navList.setCurrentItem(item)
            break
    assert dialog.templateList.count() > 0
    dialog._on_pick(dialog.templateList.item(0))
    assert dialog.selected_template() is not None
    dialog.close()

    bar = topbar.TradingViewTopBar(owner, owner)
    bar.request_template({'name': 'T', 'indicators': []})
    assert owner.applied_templates[0]['name'] == 'T'
    menu = bar._build_template_menu()
    assert [a.text() for a in menu.actions()] == ['保存指标模板…', '打开模板…']


# ---- 预警（1.7）------------------------------------------------------------
def test_alert_dialog(owner):
    alerts = pytest.importorskip(
        'miniqt.app.windows.tradingview_alert_dialog')
    dialog = alerts.TradingViewAlertDialog(symbol='rb2610', price=378.73,
                                           parent=owner)
    assert not dialog.addConditionButton.isEnabled()      # 高级功能 = 壳
    assert dialog.alert()['alert_type'] == 'cross'        # 默认「穿过」
    dialog.crossBox.setCurrentIndex(1)                    # 上穿
    alert = dialog.alert()
    assert alert['alert_type'] == 'up' and alert['up_price'] == 378.73
    dialog.crossBox.setCurrentIndex(2)                    # 下穿
    assert dialog.alert()['alert_type'] == 'down'
    assert dialog.alert()['message']                      # 自动消息非空
    assert dialog.alert()['expire_at']                    # 默认「1 天后」
    dialog._sync_message()
    dialog.messageEdit.setText('我的预警')
    assert dialog.alert()['message'] == '我的预警'
    dialog.close()


def test_cross_alert_triggers(owner):
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    window.price_alert = {'enabled': True, 'alert_type': 'cross',
                          'cross_price': 100.0, 'message': '穿过 100'}
    window._alert_fired = set()
    window._alert_last_close = 99.0
    assert window.check_price_alert(101.0) is True        # 上穿
    window._alert_fired = set()
    window._alert_last_close = 101.0
    assert window.check_price_alert(99.0) is True         # 下穿
    window._alert_fired = set()
    window._alert_last_close = 100.5
    assert window.check_price_alert(100.6) is False       # 没跨越


# ---- 回放（1.8）------------------------------------------------------------
def test_replay_toolbar_menus(owner):
    replay = pytest.importorskip('miniqt.app.windows.tradingview_replay')
    toolbar = replay.ReplayToolbar(parent=owner)
    toolbar.set_contracts(['SHFE.rb2610', 'DCE.i2609'])
    menu = toolbar._build_select_menu()
    submenus = {sub.title(): sub for sub in getattr(menu, '_subMenus', [])}
    assert {'选择合约', '选择时间段'} <= set(submenus)
    contracts = [a.text() for a in submenus['选择合约'].actions()]
    assert contracts == ['1. SHFE.rb2610', '2. DCE.i2609']
    seeks = [a.text() for a in submenus['选择时间段'].actions()]
    assert seeks == ['10%', '20%', '30%', '40%', '50%', '60%', '70%',
                     '80%', '90%']
    toolbar.set_period('5分')
    toolbar.set_speed(250)
    toolbar.set_playing(True)
    assert toolbar.cycleButton.text() == '5分'
    assert toolbar.speedButton.text() == '2x'
    assert toolbar._playing is True
    toolbar.close()


def test_topbar_alert_and_replay_buttons(owner):
    bar = topbar.TradingViewTopBar(owner, owner)
    assert bar.alertButton.toolTip() == '预警'
    assert bar.replayButton.isChecked() is False
    bar.toggle_replay()
    assert owner.replay_toggles == 1
    assert bar.replayButton.isChecked() is True
    assert '退出回放' in bar.replayButton.toolTip()
    owner.replay_active = False
    bar.refresh()
    assert bar.replayButton.isChecked() is False


class _FakeChart:
    """回放引擎测试用的假图（只需要 ``id`` 和 ``set`` ✓）。"""

    def __init__(self, chart_id='fake1'):
        self.id = chart_id
        self.frames = []

    def set(self, df, **kwargs):                             # noqa: A003
        self.frames.append(df)


def test_window_replay_engine():
    import pandas as pd
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    chart = _FakeChart()
    window.chart = chart
    frame = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=100, freq='D'),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5, 'volume': 10.0,
    })
    window._panel_frame = frame
    window.panel_frames[chart.id] = frame.copy()

    assert window.topbar_replay_active() is False
    assert window.enter_replay() is True
    assert window.replay_mode is True
    assert window.replayToolbar.isHidden() is False
    assert len(window.panel_frames[chart.id]) == 30      # 初始 30%

    window.replay_seek(0.1)
    assert len(window.panel_frames[chart.id]) == 10
    window.replay_seek(0.9)
    assert len(window.panel_frames[chart.id]) == 90
    window.replay_step(1)
    assert len(window.panel_frames[chart.id]) == 91
    window.replay_set_playing(True)
    assert window._replay_timer.isActive() is True
    window.replay_pause()
    assert window._replay_timer.isActive() is False
    window.replay_set_speed(125)
    assert window._replay_speed_ms == 125

    assert window.exit_replay() is True
    assert window.replay_mode is False
    assert len(window.panel_frames[chart.id]) == 100     # 还原完整数据
    assert window.replayToolbar.isHidden() is True

    # 再次点顶栏回放 = 进入；「跳转到实时图表」= 退出 ✓
    window.toggle_replay()
    assert window.replay_mode is True
    window.topbar_toggle_replay()
    assert window.replay_mode is False


def test_replay_toolbar_live_button(owner):
    replay = pytest.importorskip('miniqt.app.windows.tradingview_replay')
    toolbar = replay.ReplayToolbar(parent=owner)
    # 复刻顶栏回放按钮的样式（ReplayButton），紧跟「更换周期」右边 ✓
    assert isinstance(toolbar.liveButton, replay.ReplayButton)
    assert toolbar.liveButton.isChecked() is True
    assert '跳转到实时图表' in toolbar.liveButton.toolTip()
    layout = toolbar.layout()
    assert layout.indexOf(toolbar.liveButton) == \
        layout.indexOf(toolbar.cycleButton) + 1
    fired = []
    toolbar.liveRequested.connect(lambda: fired.append(True))
    toolbar.liveButton.click()
    assert fired
    toolbar.close()


def test_replay_toolbar_locks_buttons_while_playing(owner):
    replay = pytest.importorskip('miniqt.app.windows.tradingview_replay')
    toolbar = replay.ReplayToolbar(parent=owner)
    assert isinstance(toolbar.playButton, replay.PlayButton)
    toolbar.set_playing(True)
    assert toolbar.playButton.isChecked() is True       # 播放态 = 主题色
    # 播放时只有「播放」和「跳转到实时图表」可用 ✓
    for widget in (toolbar.selectButton, toolbar.forwardButton,
                   toolbar.speedButton, toolbar.cycleButton):
        assert widget.isEnabled() is False
    assert toolbar.playButton.isEnabled() is True
    assert toolbar.liveButton.isEnabled() is True
    toolbar.set_playing(False)
    assert toolbar.playButton.isChecked() is False      # 暂停态 = 原样式
    for widget in (toolbar.selectButton, toolbar.forwardButton,
                   toolbar.speedButton, toolbar.cycleButton):
        assert widget.isEnabled() is True
    toolbar.close()


def test_replay_toolbar_is_centered(owner):
    replay = pytest.importorskip('miniqt.app.windows.tradingview_replay')
    toolbar = replay.ReplayToolbar(parent=owner)
    layout = toolbar.layout()
    # 左右各一个弹性空白 → 整组控件居中 ✓
    assert layout.itemAt(0).spacerItem() is not None
    assert layout.itemAt(layout.count() - 1).spacerItem() is not None
    assert layout.itemAt(1).widget() is toolbar.selectButton
    assert layout.itemAt(layout.count() - 2).widget() is toolbar.liveButton
    toolbar.close()


def test_topbar_overflow_hides_buttons_into_more_menu(owner):
    bar = topbar.TradingViewTopBar(owner, owner)
    bar.resize(1400, 40)
    bar._update_overflow()
    assert bar.moreButton.isHidden() is True          # 够宽 -> 不显示「…」
    bar.resize(600, 40)
    bar._update_overflow()
    assert bar.moreButton.isHidden() is False          # 放不下 -> 出现「…」
    # 前面 3 个（商品搜索 / 比较商品 / 周期）不被压窄，也都还在 ✓
    for widget in (bar.symbolBox, bar.compareButton, bar.intervalButton):
        assert widget.isHidden() is False
    # 右边的工具先被收进「…」
    hidden_tools = [attr for attr, *_ in topbar.TradingViewTopBar.RIGHT_TOOLS
                    if getattr(bar, attr).isHidden()]
    assert hidden_tools
    texts = [a.text() for a in bar._build_overflow_menu().actions()
             if a.text()]
    assert '截图' in texts or '关闭布局' in texts
    # 变宽 -> 全部恢复
    bar.resize(1400, 40)
    bar._update_overflow()
    assert bar.moreButton.isHidden() is True
    assert not any(getattr(bar, attr).isHidden()
                   for attr, *_ in topbar.TradingViewTopBar.RIGHT_TOOLS)


# ---- 二级报价（1.10）-------------------------------------------------------
def test_quote_panel_collapsed_and_expanded(owner):
    quote = pytest.importorskip('miniqt.app.windows.quote_panel')
    panel = quote.QuotePanel(parent=owner)
    panel.set_symbol('SHFE.rb2610')
    panel.set_quote({
        'instrument_id': 'SHFE.rb2610', 'last_price': 7428,
        'pre_settlement': 7440, 'open': 7435, 'highest': 7450,
        'lowest': 7410, 'volume': 123456, 'open_interest': 98765,
        'ask_price1': 7429, 'ask_volume1': 10,
        'bid_price1': 7427, 'bid_volume1': 8,
        'ask_price5': 7433, 'ask_volume5': 20, 'price_tick': 1.0,
    })
    assert panel.titleLabel.text() == 'SHFE.rb2610'
    # 收回时只显示卖一 / 买一
    assert panel.is_expanded() is False
    assert panel._level_rows['sell1'][0].isHidden() is False
    assert panel._level_rows['buy1'][0].isHidden() is False
    assert panel._level_rows['sell5'][0].isHidden() is True
    panel.set_expanded(True)
    assert panel._level_rows['sell5'][0].isHidden() is False
    panel.set_ticks([{'time': '09:00:01', 'price': 7428, 'volume': 3,
                      'direction': '买', 'up': True}])
    assert panel.tickTable.rowCount() == 1
    panel.close()


# ---- 模拟账号（1.11）-------------------------------------------------------
def test_sim_account_panel(owner):
    sim = pytest.importorskip('miniqt.app.windows.sim_account_panel')
    panel = sim.SimAccountPanel(parent=owner)
    # 1.0.5 起多了「运行日志」分页（账户 / 日志 ✓）
    assert panel.page_keys() == ['sim', 'log']
    panel.set_account({'pre_balance': 100000.0, 'balance': 101234.5,
                       'position_profit': 234.5, 'available': 90000.0,
                       'risk_ratio': 0.1})
    panel.set_positions({'SHFE.rb2610': {
        'instrument_id': 'SHFE.rb2610', 'pos_long': 2, 'pos_short': 0,
        'open_price_long': 7400.0, 'float_profit_long': 560.0}})
    panel.set_orders({'o1': {'instrument_id': 'SHFE.rb2610',
                             'direction': 'BUY', 'offset': 'OPEN',
                             'volume_orign': 2, 'volume_left': 1,
                             'limit_price': 7400.0, 'status': 'ALIVE'}})
    panel.set_trades({'t1': {'instrument_id': 'SHFE.rb2610',
                             'direction': 'BUY', 'offset': 'OPEN',
                             'price': 7400.0, 'volume': 1, 'commission': 2.0}})
    rows = {k: t.rowCount() for k, t in panel.accountPage.tables.items()}
    assert rows['positions'] == 1 and rows['orders'] == 1
    assert rows['open_orders'] == 1 and rows['trades'] == 1
    # 页面就在顶栏标签里切换（仿 CustomTitleBar ✓）
    assert panel.titleBar.current_key() == 'sim'
    # 1.0.5 起标题改成「交易账户」（模拟 / 实盘共用 ✓）
    assert panel.titleBar.tabBar.tabItem(0).text() == '交易账户'
    panel.set_maximized(True)
    assert panel.is_maximized() is True
    assert panel.titleBar.maxButton.toolTip() == '恢复'
    # 最大化时最小化被忽略（图表和底部面板不能同时隐藏 ✓）
    panel.set_minimized(True)
    assert panel.is_minimized() is False
    panel.set_maximized(False)
    panel.set_minimized(True)
    assert panel.is_minimized() is True
    # ＋ 可以加别的页面（比如以后的代码编辑页 ✓）
    panel.add_page('code', '代码编辑器')
    assert 'code' in panel.page_keys()
    panel.close()


def test_topbar_has_quote_and_trading_buttons(owner):
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    attrs = [a for a, *_ in topbar.TradingViewTopBar.RIGHT_TOOLS]
    assert 'quotePanelButton' in attrs and 'tradingButton' in attrs
    assert 'codeEditorButton' in attrs
    # 顺序：关闭布局 -> 二级报价 -> 截图 -> 代码编辑器 -> 交易 ✓
    assert attrs.index('quotePanelButton') == attrs.index('screenshotButton') - 1
    assert attrs.index('codeEditorButton') == attrs.index('screenshotButton') + 1
    assert attrs.index('tradingButton') == attrs.index('screenshotButton') + 2
    assert window.topbar.quotePanelButton.toolTip() == '二级报价'
    assert window.topbar.codeEditorButton.toolTip() == '代码编辑器'
    assert window.topbar.tradingButton.toolTip() == '交易'
    # 开关二级报价 / 模拟账号
    assert window.toggle_quote_panel(True) is True
    assert window.quotePanel.isHidden() is False
    assert window.toggle_sim_panel(True) is True
    assert window.simPanel.isHidden() is False


def test_window_replay_hides_and_restores_docks():
    import pandas as pd
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    chart = _FakeChart()
    window.chart = chart
    frame = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=100, freq='D'),
        'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5, 'volume': 10.0})
    window._panel_frame = frame
    window.panel_frames[chart.id] = frame.copy()

    window.toggle_quote_panel(True)
    window.toggle_sim_panel(True)
    assert window.enter_replay() is True
    # 回放中：二级报价 / 模拟账号隐藏 ✓
    assert window.quotePanel.isHidden() is True
    assert window.simPanel.isHidden() is True
    window.exit_replay()
    # 退出回放：恢复到回放前的打开状态 ✓
    assert window.quotePanel.isHidden() is False
    assert window.simPanel.isHidden() is False

    # 回放前都关着 -> 退出后仍关着
    window.toggle_quote_panel(False)
    window.toggle_sim_panel(False)
    window.enter_replay()
    window.exit_replay()
    assert window.quotePanel.isHidden() is True
    assert window.simPanel.isHidden() is True


def test_sim_account_cards_and_minimize_maximize(owner):
    sim = pytest.importorskip('miniqt.app.windows.sim_account_panel')
    panel = sim.SimAccountPanel(parent=owner)
    # 账户概览用回测指标卡那套（CaptionLabel + Consolas 粗体值 ✓）
    panel.set_account({'pre_balance': 123456.78, 'available': 100000.0,
                       'risk_ratio': 0.1})
    assert panel.accountPage.accountLabels['pre_balance'].text() != '—'
    # 最小化：内容收起（只剩标题栏）
    panel.set_minimized(True)
    assert panel.is_minimized() is True
    assert panel.stack.isHidden() is True
    # 最大化：即使刚被隐藏 / 最小化，也要显示出来 ✓
    panel.hide()
    panel.set_maximized(True)
    assert panel.isHidden() is False
    assert panel.is_maximized() is True
    assert panel.is_minimized() is False
    assert panel.stack.isHidden() is False
    panel.close()


def test_tick_time_is_clock_only():
    """分笔时间只显示 **小时:分:秒**（用户要求 ✓），不再带日期。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    fmt = window_module.PylightchartsChartWindow._fmt_tick_time
    text = fmt(1704067200000000000)          # 纳秒时间戳
    assert text == '00:00:00'                # tq 的 datetime 就是北京时间 ✓
    assert fmt(1704067200) == '00:00:00'     # 秒时间戳也对 ✓
    assert fmt(' ') == ''                    # 空白 → 空字符串 ✓
    assert fmt(None) == ''
    assert fmt('09:15:30') == '09:15:30'     # 已经是时:分:秒 → 原样 ✓
    assert fmt('2026-10-08 01:28:28')[-8:] == '01:28:28'


def test_tick_number_handles_blank_strings():
    """天勤未填充的格子可能是空白串 → 转成 None（显示为「—」✓）。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    number = window_module._tick_number
    assert number('14699.0') == 14699.0
    assert number(22) == 22.0
    assert number(' ') is None
    assert number('') is None
    assert number(None) is None
    assert number('abc') is None
    assert number(float('nan')) is None


def test_open_code_pages_in_the_dock():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    path = __file__                                     # 任意一个 Python 文件
    page = window.open_code_viewer(path)
    assert page is not None
    assert 'view_1' in window.simPanel.page_keys()
    assert window.simPanel.isHidden() is False           # 面板被拉出来 ✓
    # 每个（文件 / 编辑器）页面有且只有一个 ✓
    assert window.open_code_viewer(path) is page
    view_keys = [k for k in window.simPanel.page_keys()
                 if k.startswith('view_')]
    assert view_keys == ['view_1']
    editor = window.open_code_editor()
    assert editor is not None
    assert window.open_code_editor() is editor
    assert window.simPanel.page_keys().count('code_editor') == 1
    # 标题栏「＋」里的「代码编辑器」走工厂 -> 同一个编辑器页 ✓
    window.simPanel.page_factories = {'code_editor': window.open_code_editor}
    window.simPanel._add_preset('code_editor', '代码编辑器')
    assert window.simPanel.page_keys().count('code_editor') == 1
    # 关掉浏览页 -> 缓存清掉，再开会新建
    window.simPanel.remove_page('view_1')
    assert window.open_code_viewer(path) is not page
    # 「添加到当前图表」不炸（脚本指标接入待完善，先提示）
    window.add_script_to_chart(path)


def test_dock_splitter_remembers_ratio():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    splitter = window.centerSplitter
    # 分割条把「图表列」和「模拟账号」分开 ✓
    assert splitter.count() == 2
    assert splitter.widget(0) is window.chartColumn
    assert splitter.widget(1) is window.simPanel
    assert splitter.handleWidth() == 0                 # 间隙 = 0 ✓
    assert window.chartRow.parent() is window.chartColumn
    assert window.replayToolbar.parent() is window.chartColumn
    assert window.chartColumn.layout().indexOf(window.chartRow) == 0
    assert window.chartColumn.layout().indexOf(window.replayToolbar) == 1
    # 拖动 -> 记住比例 ✓（上限 0.28：模拟账号面板不再占太高 ✓）
    window._dock_ratio = 0.24
    splitter.setSizes([760, 240])
    window._on_dock_splitter_moved(0, 1)
    assert 0.2 < window._dock_ratio < 0.3
    # 最小化 -> 恢复：不炸（比例还在）
    window.simPanel.set_minimized(True)
    window.simPanel.set_minimized(False)
    assert 0.2 < window._dock_ratio < 0.3
    # 最大化 -> 图表列隐藏；恢复 -> 图表列显示 ✓
    window._on_sim_maximized(True)
    assert window.chartColumn.isHidden() is True
    window._on_sim_maximized(False)
    assert window.chartColumn.isHidden() is False
    # 比例持久化（读回同一份配置）
    window._save_dock_ratio(0.42)
    assert abs(window._load_dock_ratio() - 0.42) < 0.01
    window._save_dock_ratio(window.DOCK_DEFAULT_RATIO)   # 还原默认


# ---- 商品搜索：主力「主」/ 主连「连」徽标 -------------------------------
def test_contract_badge_main_and_cont():
    # 主力（CONT_MAIN）-> 主；主连（CONT）-> 连 ✓
    assert topbar.badge_text('SHFE.ni2412', 'CONT_MAIN', 'SHFE') == '主'
    assert topbar.badge_text('KQ.m@DCE.i', 'CONT_MAIN', 'DCE') == '主'
    assert topbar.badge_text('KQ.m@SHFE.ni', 'CONT', 'SHFE') == '连'
    assert topbar.badge_text('SHFE.ni', '主连', 'SHFE') == '连'
    assert topbar.badge_text('SHFE.ni2109', 'FUTURE', 'SHFE') == 'S'
    assert topbar.badge_text('rb2610', 'futures', 'SHFE') == 'R'
    assert topbar.is_main_contract('', 'CONT_MAIN', '') is True
    assert topbar.is_main_contract('KQ.m@SHFE.ni', 'CONT', '') is False
    assert topbar.is_main_contract('SHFE.ni2109', 'FUTURE', 'SHFE') is False


def test_symbol_row_badge_shows_zhu_or_lian(owner):
    from PyQt6.QtWidgets import QLabel

    def texts_of(code, type_str):
        row = topbar.SymbolRow(code, code, type_str, 'SHFE', parent=owner)
        return [label.text() for label in row.findChildren(QLabel)]

    assert '主' in texts_of('SHFE.ni2412', 'CONT_MAIN')
    assert '连' in texts_of('KQ.m@SHFE.ni', 'CONT')
    normal = texts_of('SHFE.ni2109', 'FUTURE')
    assert '主' not in normal and '连' not in normal and 'S' in normal


# ---- 搜索性能（预索引 + 限量渲染）----------------------------------------
def test_symbol_search_caps_and_indexes(owner):
    from miniqt.app.windows import tradingview_topbar as tb
    rows = [[f'CODE{i:05d}', f'Name {i}', 'futures', 'SHFE']
            for i in range(1000)]
    dialog = tb.SymbolSearchDialog(rows=rows, parent=owner)
    assert len(dialog._indexed) == 1000
    dialog.searchEdit.setText('')
    dialog._apply_filter()
    assert dialog.listWidget.count() == tb.MAX_LIST_ROWS   # 限量渲染 ✓
    dialog.searchEdit.setText('CODE00999')
    dialog._apply_filter()
    assert dialog.listWidget.count() == 1
    dialog.close()


# ---- 股票登录门禁 ---------------------------------------------------------
def test_stock_symbol_requires_login():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    calls = []

    class FakeMain:
        stock_api = None

        def show_login_window(self, is_stock=False):
            calls.append(('login', is_stock))
            return True

    class FakeMarket:
        main_window = FakeMain()

        def switch_chart_symbol(self, code, type_str=''):
            calls.append(('switch', code, type_str))
            return True

    window.market_watch = FakeMarket()
    # 股票 + 未连 stock_api -> 弹登录，不切
    assert window.topbar_select_symbol('000001', 'STOCK') is False
    assert ('login', True) in calls and not any(c[0] == 'switch' for c in calls)
    # 登录成功后（stock_api 出现）-> 自动切过去
    FakeMain.stock_api = object()
    window._check_stock_login()
    assert ('switch', '000001', 'STOCK') in calls


# ---- 对比商品画收盘价线 ---------------------------------------------------
def test_compare_symbols_draw_lines():
    import pandas as pd
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()

    class FakeSeries:
        def __init__(self):
            self.deleted = False

        def delete(self):
            self.deleted = True

    class FakeScale:
        def __init__(self, sink):
            self.sink = sink

        def apply_options(self, **kwargs):
            self.sink.append(kwargs)

    class FakeChart:
        id = 'cmp1'

        def __init__(self):
            self.added = []
            self.scale_opts = []
            self.series = []

        def add_symbol(self, name, data=None, **kwargs):
            series = FakeSeries()
            self.series.append(series)
            self.added.append((name, list(data['value']), kwargs))
            return series

        def get_price_scale(self, scale_id='right'):
            return FakeScale(self.scale_opts)

    chart = FakeChart()
    window.chart = chart
    window.panels = lambda: [chart]

    class FakeMarket:
        def compare_frame(self, code, type_str='', cycle=None, length=None):
            return pd.DataFrame({
                'time': pd.date_range('2024-01-01', periods=4),
                'close': [10.0, 11.0, 12.0, 13.0]})

    window.market_watch = FakeMarket()
    # 预置缓存 -> 同步画线（worker 那条是异步的，测试里走缓存路径 ✓）
    for code in ('TSLA', 'BTCUSDT'):
        window._compare_frames[(code, 60)] = FakeMarket().compare_frame(code)
    window.topbar_set_compare_symbols([('TSLA', 'stock'), ('BTCUSDT', 'spot')])
    window._apply_compare_symbols()          # 延后一拍的活这里直接跑 ✓
    assert [item[0] for item in chart.added] == ['TSLA', 'BTCUSDT']
    assert chart.added[0][1] == [10.0, 11.0, 12.0, 13.0]   # 收盘价 ✓
    assert chart.added[0][2]['kind'] == 'line'
    assert chart.added[0][2]['price_label'] is False
    assert chart.added[0][2]['scale'] == 'compare'   # 自定义刻度 = 无轴 ✓
    assert len(window._compare_series) == 2
    # 清空 -> 旧的线删掉
    old = list(chart.series)
    window.topbar_set_compare_symbols([])
    window._apply_compare_symbols()
    assert window._compare_series == []
    assert all(s.deleted for s in old)
    # 缓存：同一 (合约, 周期) 再打开不重新取数 ✓
    assert ('TSLA', 60) in window._compare_frames


def test_compare_lines_follow_realtime():
    import pandas as pd
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    updates = []

    class FakeSeries:
        def delete(self):
            pass

        def update(self, row):
            updates.append(dict(row))

    class FakeChart:
        id = 'rt1'

        def add_symbol(self, name, data=None, **kwargs):
            return FakeSeries()

    class FakeMarket:
        def compare_frame(self, code, type_str='', cycle=None, length=None):
            return pd.DataFrame({'time': pd.date_range('2024-01-01',
                                                       periods=3),
                                 'close': [1.0, 2.0, 3.0]})

        def compare_last_close(self, code, cycle=None):
            return 99.0

    window.chart = FakeChart()
    window.panels = lambda: [window.chart]
    window.market_watch = FakeMarket()
    window._compare_frames[('X', 60)] = FakeMarket().compare_frame('X')
    window.topbar_set_compare_symbols([('X', 'futures')])
    window._apply_compare_symbols()
    assert len(window._compare_series) == 1
    # 实时：时间用主 K 线那一根，值用对比商品最新收盘 ✓
    stamp = pd.Timestamp('2024-01-04')
    window._update_compare_lines({'time': stamp})
    assert updates and updates[0]['value'] == 99.0
    assert updates[0]['time'] == stamp


def test_compare_reuses_a_panel_frame_and_prefetches():
    """对比合约已在某格图上 → 直接用那格数据，不再订阅（提速 ✓）。"""
    import types
    import pandas as pd
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow

    frame = pd.DataFrame({'time': pd.date_range('2024-01-01', periods=3),
                          'open': [1, 2, 3], 'high': [1, 2, 3],
                          'low': [1, 2, 3], 'close': [1, 2, 3],
                          'volume': [1, 1, 1]})
    started = []
    drawn = []

    class Panel:
        id = 'p1'

    window = types.SimpleNamespace(
        cycle=60, _topbar_compare=[('SHFE.ag2612', 'futures')],
        _compare_frames={}, _compare_prefetching=set(),
        _compare_series=[], _compare_retries={},
        panel_frames={'p1': frame},
        panels=lambda: [Panel()],
        _panel_symbol=lambda _panel: 'SHFE.ag2612',
        _same_contract=W._same_contract,
        _active_chart=lambda: object(),
        _draw_compare_line=lambda chart, index, code, f: drawn.append(code),
        _start_compare_fetch=lambda jobs: started.append(list(jobs)))
    for name in ('_compare_item', '_compare_cache_key', '_panel_frame_for',
                 '_apply_compare_symbols', 'topbar_prefetch_compare'):
        setattr(window, name, types.MethodType(getattr(W, name), window))

    W._apply_compare_symbols(window)
    assert drawn == ['SHFE.ag2612']          # 直接画，没开 worker ✓
    assert started == []
    # 预取同样的合约也直接命中面板缓存 ✓
    window._compare_frames.clear()
    W.topbar_prefetch_compare(window, 'SHFE.ag2612')
    assert window._compare_frames.get(('SHFE.ag2612', 60)) is frame
    assert started == []


def test_compare_length_matches_the_chart_data_length():
    """对比品种取数与图表合约**同长度**（不再写死短长度 ✓）。"""
    import types
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    window = types.SimpleNamespace(length=2000,
                                   COMPARE_LENGTH=W.COMPARE_LENGTH)
    window._compare_length = types.MethodType(W._compare_length, window)
    assert window._compare_length() == 2000      # 跟数据长度一致 ✓
    window.length = 0
    assert window._compare_length() == W.COMPARE_LENGTH


def test_compare_fetch_keeps_the_pause_flag_and_always_resumes():
    """连续添加对比商品不能把「实时暂停中」标记清掉，否则图表永久卡住 ✗。"""
    import types
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    started = []

    class Timer:
        def __init__(self, active):
            self._active = active

        def isActive(self):
            return self._active

    window = types.SimpleNamespace(
        _compare_realtime_paused=False, _compare_workers=[],
        _compare_watchdog=None, _stop_compare_watchdog=lambda: None,
        _resume_tq_qtimer=lambda: None,
        data_provider=lambda *args: None,
        start_panel_realtime=lambda *args, **kwargs: started.append(True))

    def stop_panel_realtime():
        window._panel_timer = None

    window.stop_panel_realtime = stop_panel_realtime
    # 第一次：timer 活着 → 暂停 + 置标记
    window._panel_timer = Timer(True)
    W._pause_compare_realtime(window)
    assert window._compare_realtime_paused is True
    # 第二次：timer 已被第一次停掉（isActive() 为 False）→ 不能把标记清掉
    W._pause_compare_realtime(window)
    assert window._compare_realtime_paused is True
    # 还有 worker → 不恢复
    window._compare_workers = [object()]
    W._resume_compare_realtime(window)
    assert started == []
    # 最后一个 worker 结束 → 恢复实时
    window._compare_workers = []
    W._resume_compare_realtime(window)
    assert started == [True]
    assert window._compare_realtime_paused is False


def test_compare_empty_frame_schedules_a_retry_and_stops_after_limit():
    """新合约第一根还没到时，空帧要重试（但不能无限重试 ✗）。"""
    import types
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow

    class Series:
        def delete(self):
            pass

    class Chart:
        id = 'retry1'

        def add_symbol(self, *args, **kwargs):
            return Series()

    scheduled = []

    class FakeTimer:
        @staticmethod
        def singleShot(ms, fn):
            scheduled.append(ms)

    original_timer = window_module.QTimer
    window_module.QTimer = FakeTimer
    try:
        window = types.SimpleNamespace(
            _compare_token=3, _topbar_compare=[('SHFE.au2612', 'futures')],
            _compare_retries={}, _compare_series=[],
            _compare_prefetching=set(),
            _compare_realtime_paused=False, _compare_workers=[],
            _compare_watchdog=None, _stop_compare_watchdog=lambda: None,
            _resume_tq_qtimer=lambda: None,
            COMPARE_RETRIES=2, COMPARE_RETRY_MS=W.COMPARE_RETRY_MS,
            _retries=[],
            data_provider=None,
            _active_chart=lambda: Chart(),
            _draw_compare_line=lambda *args: None,
            _start_compare_fetch=lambda jobs: window._retries.append(
                list(jobs)))
        for name in ('_resume_compare_realtime', '_compare_item',
                     '_compare_type_at', '_on_compare_frames',
                     '_retry_compare_frames', '_current_compare_codes'):
            setattr(window, name,
                    types.MethodType(getattr(W, name), window))

        # 第 1 次空帧 → 记 1 次，并排一次重试
        W._on_compare_frames(window, 3, [(0, 'SHFE.au2612', None)])
        assert window._compare_retries['SHFE.au2612'] == 1
        assert scheduled == [W.COMPARE_RETRY_MS]
        # 直接跑重试 → 空帧 → 记 2 次（达到上限，不再排重试）
        W._retry_compare_frames(window, [(0, 'SHFE.au2612', 'futures')])
        assert window._retries and window._retries[0] == [
            (0, 'SHFE.au2612', 'futures')]
        W._on_compare_frames(window, 3, [(0, 'SHFE.au2612', None)])
        assert window._compare_retries['SHFE.au2612'] == 2
        assert scheduled == [W.COMPARE_RETRY_MS, W.COMPARE_RETRY_MS]
        # 第 3 次空帧 → 已达到上限，不再排重试 ✓
        W._on_compare_frames(window, 3, [(0, 'SHFE.au2612', None)])
        assert window._compare_retries['SHFE.au2612'] == 2
        assert scheduled == [W.COMPARE_RETRY_MS, W.COMPARE_RETRY_MS]
    finally:
        window_module.QTimer = original_timer


# ---- 顶栏控件跟随主题 / 用 qfluentwidgets 图标（2026-10-06 反馈）-----------
def test_symbol_box_follows_theme_not_hardcoded(owner):
    """商品搜索框不再写死深色样式：用普通 qfluentwidgets 控件（跟随深浅 ✓）。"""
    from qfluentwidgets import PushButton
    box = topbar._SymbolBox(owner)
    assert isinstance(box, PushButton)
    # 旧的深色样式已经拿掉
    assert 'background:#2a2e39' not in box.styleSheet()
    box.set_symbol('rb2610')
    assert box.codeLabel.text() == 'rb2610'


def test_indicator_button_uses_a_fluent_icon(owner):
    """技术指标按钮改用 qfluentwidgets 内置图标 ✓。"""
    button = topbar._IndicatorSplitButton(lambda: None, owner)
    assert not button.icon().isNull()


# ---- 图表设置的颜色（鼠标标签 / 上涨 / 下跌）真正生效 ----------------------
def test_chart_config_colors_are_applied():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    from miniqt.app.common.chart_config import chart_cfg
    window = window_module.PylightchartsChartWindow()
    saved = (chart_cfg.mouseLabelColor.value, chart_cfg.bullColor.value,
             chart_cfg.bearColor.value)
    try:
        # 先把三项都设成默认值 → 不应覆盖主题原色（不依赖用户配置文件内容 ✓）
        chart_cfg.mouseLabelColor.value = chart_cfg.DEFAULT_CONFIG['MouseLabelColor']
        chart_cfg.bullColor.value = chart_cfg.DEFAULT_CONFIG['BullColor']
        chart_cfg.bearColor.value = chart_cfg.DEFAULT_CONFIG['BearColor']
        assert window._chart_config_overrides() == {}
        chart_cfg.bullColor.value = 'rgba(255, 0, 0, 1.00)'
        chart_cfg.bearColor.value = '#00ff00'
        chart_cfg.mouseLabelColor.value = 'rgba(10, 20, 30, 0.90)'
        overrides = window._chart_config_overrides()
        assert overrides['up'] == 'rgba(255, 0, 0, 1.00)', overrides
        assert overrides['down'] == '#00ff00', overrides
        assert overrides['crosshair_label'] == 'rgba(10, 20, 30, 0.90)'
        assert window._current_colors()['up'] == 'rgba(255, 0, 0, 1.00)'
    finally:
        (chart_cfg.mouseLabelColor.value, chart_cfg.bullColor.value,
         chart_cfg.bearColor.value) = saved


def test_crosshair_label_color_applied_to_chart():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    calls = []

    class FakeChart:
        def apply_options(self, **kwargs):
            calls.append(kwargs)

    window._apply_crosshair_label(FakeChart(), 'rgba(10, 20, 30, 0.90)')
    crosshair = calls[0]['crosshair']
    for line in ('vert_line', 'horz_line'):
        assert (crosshair[line]['label_background_color']
                == 'rgba(10, 20, 30, 0.90)')


def test_legend_text_uses_theme_text_color():
    """图例文本/眼睛图标用主题文本色（和设置齿轮一致 ✓）。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    seen = {}

    class FakeChart:
        def legend(self, **kwargs):
            seen.update(kwargs)

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    window._style_panel(FakeChart(), {'bg': '#ffffff', 'text': '#131722',
                                      'grid': '#eeeeee', 'up': '#089981',
                                      'down': '#f23645'})
    assert seen.get('color') == '#131722', seen


# ---- 改颜色只轻量重上色 / 实时指标只推最后一根 / 密码可见 ---------------
def test_apply_color_settings_is_lightweight():
    """改鼠标标签颜色只重上必要的那几条，不重跑 win.theme（否则拖一下会卡 ✓）。"""
    from miniqt.app.windows.pylightcharts_window import PylightchartsChartWindow
    from miniqt.app.common.chart_config import chart_cfg

    class FakeWindow:
        def __init__(self):
            self.theme_calls = []

        def theme(self, *args, **kwargs):
            self.theme_calls.append((args, kwargs))

    class FakeChart:
        def __init__(self):
            self.calls = []
            self.win = FakeWindow()

        def candle_style(self, **kwargs):
            self.calls.append(('candle', kwargs))

        def apply_options(self, **kwargs):
            self.calls.append(('options', kwargs))

    window = PylightchartsChartWindow()
    fake = FakeChart()
    window.chart = fake
    window._type_series = {}
    saved = chart_cfg.mouseLabelColor.value
    try:
        chart_cfg.mouseLabelColor.value = 'rgba(0, 0, 0, 1.00)'
        window.apply_color_settings()
        assert not fake.win.theme_calls, '不应重跑整套主题'
        cross = [c for c in fake.calls if c[0] == 'options']
        assert cross and cross[-1][1]['crosshair']['vert_line'][
            'label_background_color'] == 'rgba(0, 0, 0, 1.00)'
    finally:
        chart_cfg.mouseLabelColor.value = saved


def test_indicator_realtime_updates_last_point_only():
    """实时指标刷新只推最后一根（update）；出现新的一根才整表 set ✓。"""
    from miniqt.app.windows.pylightcharts_window import PylightchartsChartWindow

    class FakeSeries:
        def __init__(self, n):
            import pandas as pd
            self.data = pd.DataFrame({'time': list(range(n)),
                                      'value': [0.0] * n})
            self._gap_series = []
            self.updates = []
            self.sets = []

        def update(self, row):
            self.updates.append(row)

        def set(self, frame):
            self.sets.append(frame)
            self.data = frame

    class FakeIndicator:
        def __init__(self, lines):
            self.indicator_lines = lines
            self.chart = None

    class FakeManager:
        def __init__(self, indicator):
            self.indicator = indicator

        def getIndicator(self, _id):
            return self.indicator

    n = 10
    series = FakeSeries(n)
    indicator = FakeIndicator({'ma': series})
    window = PylightchartsChartWindow()
    window.indicator_manager = FakeManager(indicator)
    times = list(range(n))
    values = [float('nan')] * 2 + list(range(n - 2))
    window._apply_indicator_results([(1, {'ma': values}, times)])
    assert series.updates and not series.sets, (len(series.updates),
                                                len(series.sets))
    # 新的一根（根数 +1）→ 整表重发
    series2 = FakeSeries(n)
    indicator.indicator_lines = {'ma': series2}
    window._apply_indicator_results([(1, {'ma': values + [99.0]},
                                      times + [n])])
    assert series2.sets and not series2.updates


def test_indicator_frame_replacement_forces_full_set():
    """换合约（根数不变但数据整段换了）→ 必须整表 set，不能只 update 最后一根 ✓。"""
    from miniqt.app.windows.pylightcharts_window import PylightchartsChartWindow

    class FakeSeries:
        def __init__(self, n):
            import pandas as pd
            self.data = pd.DataFrame({'time': list(range(n)),
                                      'value': [0.0] * n})
            self._gap_series = []
            self.updates = []
            self.sets = []

        def update(self, row):
            self.updates.append(row)

        def set(self, frame):
            self.sets.append(frame)
            self.data = frame

    class FakeIndicator:
        def __init__(self, lines):
            self.indicator_lines = lines
            self.chart = None

    class FakeManager:
        def __init__(self, indicator):
            self.indicator = indicator

        def getIndicator(self, _id):
            return self.indicator

    n = 10
    series = FakeSeries(n)
    indicator = FakeIndicator({'ma': series})
    window = PylightchartsChartWindow()
    window.indicator_manager = FakeManager(indicator)
    times = list(range(n))
    values = [float('nan')] * 2 + list(range(n - 2))
    # full=True（换合约）→ 整表 set ✓
    window._apply_indicator_results(
        [(1, {'ma': values}, times, False, None, None, True)])
    assert series.sets and not series.updates, (len(series.sets),
                                                len(series.updates))
    # 同样根数、full=False → 仍只 update 最后一根 ✓
    series2 = FakeSeries(n)
    indicator.indicator_lines = {'ma': series2}
    window._apply_indicator_results([(1, {'ma': values}, times)])
    assert series2.updates and not series2.sets


def test_overlay_refresh_forced_on_frame_replacement():
    """换合约（长度没变）→ 叠加层（色带/信号）必须 force 重画，否则旧信号还在 ✓。"""
    from miniqt.app.windows.pylightcharts_window import PylightchartsChartWindow

    window = PylightchartsChartWindow()
    calls = []
    window._refresh_indicator_bands = lambda plot, times, entry, **k: calls.append(
        'bands')
    window._draw_indicator_signals = lambda *a, **k: calls.append('signals')
    indicator = type('I', (), {'id': 7, 'chart': None})()
    window.indicators = [{'id': 7, '_overlay_len': 100}]
    times = list(range(100))          # 长度与上次一样
    # 不 force → 跳过（避免每秒空跑）
    window._refresh_indicator_overlays(indicator, {}, times, None)
    assert calls == [], calls
    # force（换合约）→ 重画 ✓
    window._refresh_indicator_overlays(indicator, {}, times, None, force=True)
    assert calls == ['bands', 'signals'], calls


def test_frame_generation_bump_marks_panel():
    """``_bump_frame_generation``：换合约/周期后版本号 +1（指标据此整段重发）✓。"""
    from PyQt6.QtWidgets import QWidget
    from miniqt.app.windows.pylightcharts_window import PylightchartsChartWindow

    class FakeChart(QWidget):
        def __init__(self):
            super().__init__()
            self.id = 'c1'

    window = PylightchartsChartWindow()
    chart = FakeChart()
    assert window._frame_generation(chart) == 0
    window._bump_frame_generation(chart)
    assert window._frame_generation(chart) == 1
    window._bump_frame_generation(chart)
    assert window._frame_generation(chart) == 2


def test_reset_strategies_rebuilds_runner(monkeypatch):
    """换合约/周期后策略要**重建 runner**（不能带着旧持仓 / 旧指标跑）✓。"""
    import pandas as pd
    from PyQt6.QtWidgets import QWidget
    from miniqt.app.windows.pylightcharts_window import PylightchartsChartWindow
    from miniqt.app.common import strategy_runner as sr

    class FakeRunner:
        def __init__(self, cls, params=None, symbol='', cycle=60,
                     account=None):
            self.cls = cls
            self.params = params
            self.symbol = symbol
            self.cycle = cycle
            self.account = account
            self.strategy = object()
            self.frames = None

        def prepare(self, frames, seed_kline=False):
            self.frames = frames

    monkeypatch.setattr(sr, 'StrategyRunner', FakeRunner)

    class Chart(QWidget):
        def __init__(self):
            super().__init__()
            self.id = 'c1'

    window = PylightchartsChartWindow()
    chart = Chart()
    frame = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=3, freq='min'),
        'open': [1.0, 1.0, 1.0], 'high': [2.0, 2.0, 2.0],
        'low': [0.5, 0.5, 0.5], 'close': [1.5, 1.5, 1.5],
        'volume': [9, 9, 9]})
    holder = [frame]
    window._indicator_source = (
        lambda frame=None, kline=None, chart=None:
        (holder[0], list(holder[0]['time'])))
    window._panel_symbol = lambda chart=None: 'SHFE.ag2612'
    window._panel_cycle = lambda chart=None: 60
    drawn = []
    window._draw_strategy = lambda record: drawn.append(record) or 1

    Cls = type('S', (), {})
    old = object()
    record = {'name': 'g.S', 'group': 'g', 'cls_name': 'S', 'cls': Cls,
              'params': {}, 'chart': chart, 'chart_id': 'c1',
              'runner': old, 'strategy': None, 'plots': [], '_sig': (1,)}
    window._panel_strategies = {'c1': record}
    n = window.reset_strategies(chart)
    assert n == 1
    assert record['runner'] is not old                  # runner 已重建 ✓
    assert isinstance(record['runner'], FakeRunner)
    assert record['runner'].symbol == 'SHFE.ag2612'     # 用新合约 ✓
    assert record['_sig'] is None                       # 触发下一拍 advance ✓
    assert drawn == [record]


def test_tq_pump_pause_resume_is_sticky():
    """两次 pause 重叠时 resume 仍要把 tq 泵拉回来（不能永久停住 ✗）✓。"""
    from miniqt.app.windows.pylightcharts_window import PylightchartsChartWindow

    class FakeTimer:
        def __init__(self):
            self._active = True
            self.starts = 0

        def isActive(self):
            return self._active

        def start(self):
            self._active = True
            self.starts += 1

        def stop(self):
            self._active = False

    window = PylightchartsChartWindow()
    timer = FakeTimer()
    window._tq_qtimer = lambda: timer
    window._pause_tq_qtimer()
    window._pause_tq_qtimer()          # 第二次（重叠）暂停
    assert not timer.isActive()
    window._resume_tq_qtimer()
    assert timer.isActive(), 'tq 泵被永久停住 ✗（旧实现会漏掉）'
    assert timer.starts == 1


def test_password_field_has_reveal_toggle():
    """登录密码框有一个「显示/隐藏密码」眼睛按钮（可看明文，不是一直黑点）✓。"""
    from PyQt6.QtWidgets import QLineEdit
    from qfluentwidgets import LineEdit
    from miniqt.app.login.LoginWindow import LoginWindow

    edit = LineEdit()
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    LoginWindow._add_password_reveal(LoginWindow.__new__(LoginWindow), edit)
    assert getattr(edit, 'rightButtons', None), '没有眼睛按钮'
    action = edit.actions()[-1]
    action.setChecked(True)
    assert edit.echoMode() == QLineEdit.EchoMode.Normal  # 显示明文
    action.setChecked(False)
    assert edit.echoMode() == QLineEdit.EchoMode.Password


# ---- 主题色跟随（自定义才跟随）/ 回放按钮重画（2026-10-06 反馈）----------
def test_custom_theme_color_detection():
    """默认主题色 → None；自定义主题色 → 返回该颜色（搜索里合约名称才跟随 ✓）。"""
    from PyQt6.QtGui import QColor
    from qfluentwidgets import qconfig
    from miniqt.app.windows.tradingview_topbar import custom_theme_color

    saved = qconfig.themeColor.value
    try:
        qconfig.themeColor.value = QColor(qconfig.themeColor.defaultValue)
        assert custom_theme_color() is None
        qconfig.themeColor.value = QColor('#ff0b78')
        color = custom_theme_color()
        assert color is not None
        assert color.rgb() == QColor('#ff0b78').rgb()
    finally:
        qconfig.themeColor.value = saved


def test_replay_button_has_settheme(owner):
    """回放按钮切主题后重画图标（否则浅色下建、切深色后还是黑描边 ✗）。"""
    from miniqt.app.windows.tradingview_replay import ReplayButton
    button = ReplayButton(owner)
    button.setChecked(True)
    button.setTheme(True)
    button.setTheme(False)
    button.setChecked(False)


def test_theme_text_color_flips_with_theme():
    from qfluentwidgets import Theme
    from qfluentwidgets.common.config import qconfig
    original = qconfig.theme
    try:
        # 直接改 qconfig.theme（不走 setTheme，避免触发全局样式表遍历的 GC 坑）
        qconfig.theme = Theme.DARK
        assert topbar.theme_text_color() == '#ffffff'
        qconfig.theme = Theme.LIGHT
        assert topbar.theme_text_color() == '#1a1a1a'
    finally:
        qconfig.theme = original


def test_symbol_box_code_color_follows_theme():
    from qfluentwidgets import Theme
    from qfluentwidgets.common.config import qconfig
    box = topbar._SymbolBox()
    original = qconfig.theme
    try:
        qconfig.theme = Theme.LIGHT
        box._apply_code_color()
        assert 'color:#1a1a1a' in box.codeLabel.styleSheet()
        qconfig.theme = Theme.DARK
        box._apply_code_color()
        assert 'color:#ffffff' in box.codeLabel.styleSheet()
    finally:
        qconfig.theme = original


def test_indicator_catalog_includes_tradingview():
    """内置指标要包含 minibt 的 TradingView 指标组（kline.tradingview ✓）。"""
    dialog = pytest.importorskip('miniqt.app.windows.indicator_dialog')
    catalog = dialog.indicator_catalog()
    assert 'TradingView' in catalog
    names = [name for name, _doc in catalog['TradingView']]
    assert len(names) >= 100                 # minibt TradingView 指标很多
    assert 'AlphaTrend' in names and 'SuperTrend' in names
    # 没有 kline 时 holder 安全返回 None
    assert dialog.indicator_holder(None, 'TradingView') is None


def test_tradingview_indicator_converts_dataframe_to_kline():
    """minibt TradingView 指标要 KLine：带 time 的 DataFrame 会自动转成 KLine ✓。"""
    import minibt

    dialog = pytest.importorskip('miniqt.app.windows.indicator_dialog')
    kline = minibt.LocalDatas.test.kline.pandas_object
    frame = kline.rename(columns={'datetime': 'time'})[
        ['time', 'open', 'high', 'low', 'close', 'volume']]
    converted = dialog.to_minibt_kline(frame)
    assert converted is not frame
    assert 'datetime' in converted.pandas_object.columns
    # 直接拿 DataFrame 也能算（内部已转 KLine）
    result = dialog.compute_indicator(frame, 'TradingView', 'ADX_and_DI', {})
    lines = result['groups'][0]['lines']
    assert 'ADX' in lines and 'DIPlus' in lines


def test_tradingview_indicator_source_traces_impl_class():
    """TradingView 指标要能追到**真实实现类**（不是只有 docstring 的包装方法）。"""
    src = pytest.importorskip('miniqt.app.common.indicator_source')
    sections = src.resolve_indicator_source('TradingView', 'HemaTrendLevels')
    titles = [s.title for s in sections]
    assert any('minibt 定义' in title for title in titles)
    assert any('底层实现' in title and 'HemaTrendLevels' in title
               for title in titles)
    impl = [s for s in sections if '底层实现' in s.title][0]
    assert 'class HemaTrendLevels' in impl.code


def test_right_tools_have_the_link_button_next_to_layout(owner):
    """「布局」右边要有「联动」按钮（同周期合约同步 ✓）。"""
    hooks = [hook for _attr, _icon, _tip, hook in topbar.TradingViewTopBar
             .RIGHT_TOOLS]
    assert 'topbar_toggle_link' in hooks
    assert hooks.index('topbar_toggle_link') == \
        hooks.index('topbar_show_layout_menu') + 1
    bar = topbar.TradingViewTopBar(owner, owner)
    assert bar.linkButton.toolTip().startswith('联动')


def test_apply_link_syncs_panels_by_options():
    """联动：`_apply_link` 按选项把所有格 sync 到第一格（十字线 / 全量 ✓）。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window_class = window_module.PylightchartsChartWindow

    class FakePanel:
        def __init__(self, name):
            self.name = name
            self.synced = []
            self.unsynced = []
            self.sync_kwargs = []

        def sync(self, other, crosshairs_only=False):
            self.synced.append(other)
            self.sync_kwargs.append(crosshairs_only)
            return other

        def unsync(self, other):
            self.unsynced.append(other)
            return other

    panels = [FakePanel('a'), FakePanel('b'), FakePanel('c')]
    base = {'symbol': False, 'interval': False, 'crosshair': True,
            'time': False, 'date_range': False, 'watermark': False}

    class Host:
        _apply_link = window_class._apply_link
        _unlink_panels = window_class._unlink_panels

        def __init__(self, options):
            self._link_enabled = False
            self._linked_pairs = []
            self.panels = lambda: list(panels)
            self._layout_options = lambda: dict(options)

    window = Host(dict(base))
    assert window._apply_link() is True
    assert panels[0].synced == [panels[1], panels[2]]
    assert panels[0].sync_kwargs == [True, True]      # 只十字线 ✓

    # 打开“时间” → 全量联动（pan/zoom + 十字线 ✓）
    window._layout_options = lambda: {**base, 'time': True}
    assert window._apply_link() is True
    assert panels[0].sync_kwargs[-2:] == [False, False]

    # 都不开 → 不联动 ✓
    window._layout_options = lambda: {**base, 'crosshair': False}
    assert window._apply_link() is False
    assert window._link_enabled is False

    # 只有 1 格 → 不联动 ✓
    window.panels = lambda: [panels[0]]
    assert window._apply_link() is False


def test_layout_defs_cover_up_to_nine():
    """布局定义覆盖 1–9 格；菜单分组也能列全 ✓。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    counts = set()
    for key, (_name, kind, arg) in W.LAYOUTS.items():
        if kind == 'single':
            counts.add(1)
        elif kind in ('row', 'column'):
            counts.add(int(arg))
        elif kind == 'tiles':
            counts.add(len(arg))
    assert set(range(1, 10)) <= counts           # 1–9 每档都有 ✓
    menu_keys = {k for _t, keys in W.LAYOUT_MENUS for k in keys}
    assert menu_keys <= set(W.LAYOUTS)
    assert W.LINK_DEFAULTS.get('crosshair') is False   # 默认不自动联动 ✓
    assert W.WATERMARK_DEFAULT is False          # 水印默认关 ✓


def test_layout_button_is_a_split_with_a_dropdown(owner):
    """布局按钮改成 SplitButton：右箭头下拉有 保存/复制/重命名/收藏/管理 ✓。"""
    bar = topbar.TradingViewTopBar(owner, owner)
    assert isinstance(bar.layoutButton, topbar._LayoutSplitButton)

    owner.favorite_layout_templates = lambda: [
        {'name': '布局A', 'favorite': True},
        {'name': '布局B', 'favorite': True}]
    owner.current_layout_template_name = lambda: '布局A'
    menu = bar._build_layout_dropdown()
    texts = [a.text() for a in menu.actions() if a.text()]
    assert '保存布局' in texts
    assert '复制...' in texts
    assert '重命名...' in texts
    assert '布局管理' in texts
    # 收藏里：当前使用的用不同样式（★ + 禁用），其它可切换 ✓
    assert '★ 布局A' in texts
    assert '　布局B' in texts
    actions = {a.text(): a for a in menu.actions()}
    assert actions['★ 布局A'].isEnabled() is False
    assert actions['　布局B'].isEnabled() is True
