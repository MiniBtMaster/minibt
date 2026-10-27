"""pylightcharts 看盘窗口（``windows/pylightcharts_window.py``）的守卫测试。

只做源码级/纯逻辑断言（不建 GUI）：把这几轮踩出来的规矩钉住，避免以后改回去：

* **三条铁律**：用 ``ci.get_chart_class()`` 建图、``get_webview()`` 嵌布局、
  数据 ``time`` 走 ``to_chart_time``（datetime64）、送数据要有排队/延后；
* **布局**：``arrange`` 要给已存在的 anchor 也回调 ``on_create``
  （pylightcharts 只对新图调 —— 不补首张就没数据，实测 ``bars: 0``）；
* **主题跟随 miniqt**（不自己做开关）、**实时增量**走 ``update_from_tick``；
* 工具栏：周期组 7 个 + "自"、布局按钮、截图。

    pytest tests/test_pylightcharts_window.py
"""
from __future__ import annotations

import pathlib

WINDOW = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app'
          / 'windows' / 'pylightcharts_window.py')


def _source() -> str:
    return WINDOW.read_text(encoding='utf-8')


def _topbar_source() -> str:
    return (WINDOW.parent / 'tradingview_topbar.py').read_text(encoding='utf-8')


def test_window_lives_next_to_the_other_chart_files():
    assert WINDOW.exists()
    folder = WINDOW.parent
    assert (folder / 'chart_interface.py').exists()      # 旧的（未动）
    assert (folder / 'pylightcharts_page.py').exists()   # P0 的冒烟页


def test_three_rules_are_kept():
    source = _source()
    assert 'get_chart_class()' in source            # 用 miniqt 补丁版 QtChart
    assert 'get_webview()' in source                # 视图就是它
    assert '_pending' in source                     # 未就绪先排队
    assert 'QTimer.singleShot' in source            # 建图后延后发数据


def test_arrange_also_feeds_the_anchor():
    """`on_create` 必须连 anchor 一起回调（否则首张图没数据）。"""
    source = _source()
    body = source.split('def arrange(', 1)[1]
    body = body.split(chr(10) + '    @property', 1)[0]
    assert 'on_create' in body
    assert 'on_create(self.chart)' in body          # anchor


def test_toolbar_layout_menu_and_close_layout():
    """工具栏：「布局」（2/3 个窗口的子菜单）+「关闭布局」（关最后点击过的图 ✓）。"""
    source = _source()
    assert 'LAYOUT_MENUS' in source
    assert "'2 个窗口'" in source and "'3 个窗口'" in source
    assert "'上1下左1下右1'" in source and "'上左1上右1下1'" in source
    assert 'DEFAULT_FOR_COUNT' in source          # 删除后回落（2 -> 左右 ✓）
    assert 'def close_layout' in source
    assert 'last_panel' in source                 # 跟踪最后点击过的图
    assert 'events.click' in source               # 用 click 事件跟踪 ✓
    assert 'arrange_tiles' in source              # 2D 布局
    # 布局按钮在顶栏右侧工具组里（图标 + tooltip ✓）
    topbar = _topbar_source()
    assert "('layoutButton', FluentIcon.LAYOUT, '布局'" in topbar


def test_layout_sync_options_are_disabled_only_watermark_enabled():
    """9 宫格下面的「同步到所有图表」联动选项未实现 → 置灰；仅水印可用 ✓。"""
    source = _source()
    body = source.split('def _populate_layout_menu', 1)[1].split(
        '\n    def ', 1)[0]
    assert 'action.setEnabled(False)' in body
    assert "action.setToolTip('功能未实现')" in body
    # 水印保持可点（不能也给它 setEnabled(False)）
    watermark = body.split("watermark = Action('水印'", 1)[1]
    watermark = watermark.split('menu.addAction(watermark)', 1)[0]
    assert 'setEnabled(False)' not in watermark


def test_hiding_the_dock_restores_the_maximized_chart():
    """底部面板隐藏 / 进回放前要先恢复被最大化遮住的图表 ✓。"""
    source = _source()
    assert 'def _restore_chart_before_hiding_sim' in source
    toggle = source.split('def toggle_sim_panel', 1)[1].split(
        '\n    def ', 1)[0]
    assert '_restore_chart_before_hiding_sim()' in toggle
    replay = source.split('def enter_replay', 1)[1].split(
        '\n    def ', 1)[0]
    assert '_restore_chart_before_hiding_sim()' in replay


def test_watch_editor_hides_strategy_actions():
    """看盘窗口隐藏「策略回测 / 参数优化」；回测模块保持默认显示 ✓。"""
    source = _source()
    assert "kwargs.setdefault('show_strategy_actions', False)" in source
    page = (WINDOW.parent / 'qtvscode_page.py').read_text(encoding='utf-8')
    assert 'show_strategy_actions: bool = True' in page   # 回测模块默认 ✓
    assert 'if self.show_strategy_actions:' in page


def test_toolbar_has_periods_layout_and_screenshot():
    source = _source()
    assert 'PERIODS' in source
    for label in ('30秒', '1分', '5分', '15分', '30分', '1时', '1日', '自'):
        assert f"'{label}'" in source, label
    assert 'cycleChanged' in source                 # 周期变化的信号
    assert 'close_layout' in source                 # 关闭布局 ✓
    assert 'takeScreenshot' in source               # 截图走页面 canvas


def test_theme_follows_miniqt_only():
    """主题由 miniqt 决定：跟随 qconfig.themeChanged，不提供独立开关。"""
    source = _source()
    assert 'qconfig.themeChanged' in source
    assert 'isDarkTheme' in source
    assert 'def apply_theme' in source
    # 不该有"主题"按钮（水印/价格线同理：水印在布局菜单里，价格线在指标属性）
    assert "TransparentPushButton(\n            '主题'" not in source
    assert "self._button('水印'" not in source


def test_layout_divider_color_follows_the_theme():
    """多布局图表之间的间隔条要跟着主题：浅色主题不能用深色 #2a2e39 ✗。"""
    import sys
    import types
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)

    def brightness(css):
        value = css.lstrip('#')
        return sum(int(value[i:i + 2], 16) for i in (0, 2, 4))

    assert W.THEMES[False]['divider'] != '#2a2e39'
    assert brightness(W.THEMES[False]['divider']) > \
        brightness(W.THEMES[True]['divider']) + 200

    calls = []

    class Layout:
        def set_divider(self, **kwargs):
            calls.append(kwargs)

    window = types.SimpleNamespace()
    W._apply_layout_divider(window, {'divider': '#e3e6ea'},
                            types.SimpleNamespace(layout=Layout()))
    assert calls == [{'color': '#e3e6ea'}]


def test_realtime_uses_update_from_tick():
    source = _source()
    assert "self._call('update_from_tick'" in source
    assert 'def push_tick' in source
    assert 'cumulative_volume' in source


def test_watermark_stays_out_until_the_context_menu():
    """水印按约定不做在工具栏（留给右键菜单）；价格线已归到指标参数窗口 ✓。"""
    source = _source()
    assert "self._button('水印'" not in source
    # 价格线/价格标签是指标参数（不是工具栏按钮），见 add_indicator ✓
    assert "self._button('价格线'" not in source
    assert 'price_line=price_line' in source


def test_multi_contract_provider_and_panel_realtime():
    """多合约取数：`set_contracts` + `_contract_frame` + `start_panel_realtime`。"""
    source = _source()
    for name in ('def set_contracts', 'def _contract_frame',
                 'def feed_contract_panel', 'def start_panel_realtime',
                 'def stop_panel_realtime', 'def _panel_realtime_step'):
        assert name in source, name
    assert 'self.contracts' in source
    assert 'self.data_provider' in source
    # contracts[index % len] 循环取合约 ✓
    assert 'index % len(self.contracts)' in source


def test_new_watch_window_replaces_the_old_one():
    """新看盘窗口（替代旧 MarketWatchWindow）就在旁边，且主窗口已接上。"""
    watch = WINDOW.parent / 'pylightcharts_market_watch.py'
    assert watch.exists()
    src = watch.read_text(encoding='utf-8')
    for name in ('class PylightchartsMarketWatchWindow', 'def _frame',
                 'def _feed_panel', 'def _bootstrap',
                 'set_contracts', 'start_panel_realtime',
                 'set_last_clicked_widget'):
        assert name in src, name
    # 旧接口对齐（main_window.start_minibt_chart 直接替换）
    for attr in ('self.symbol', 'self.cycle', 'self.length',
                 'self.is_stock', 'self.main_window'):
        assert attr in src, attr

    main = WINDOW.parents[1] / 'view' / 'main_window.py'
    main_src = main.read_text(encoding='utf-8')
    assert 'pylightcharts_market_watch' in main_src      # 新窗口
    assert 'chart_engine' in main_src and 'LEGACY' in main_src  # 可回退
    assert 'market_watch_window import MarketWatchWindow' in main_src


def test_toolbar_has_drawing_and_panel_buttons():
    """画线 / 清除画线 / 布局 / 截图（已从旧 CommandBar 迁到顶栏右侧 ✓）。"""
    source = _source()
    for name in ('def toggle_toolbox', 'def clear_drawings', 'def add_panel',
                 'def remove_panel', 'def screenshot'):
        assert name in source, name
    assert 'from pylightcharts.toolbox import ToolBox' in source
    topbar = _topbar_source()
    for label in ('删除指标策略', '画线', '清除画线', '布局',
                  '关闭布局', '截图'):
        assert f"'{label}'" in topbar, label
    # 「添加板块」入口暂时停用（代码保留）✓
    assert "# ('addPanelButton'" in topbar


def test_watch_window_keyelf_and_symbol_switch():
    """新看盘窗口要支持键盘精灵（空格）与切合约 ✓。"""
    watch = WINDOW.parent / 'pylightcharts_market_watch.py'
    src = watch.read_text(encoding='utf-8')
    for name in ('active_chart_widget', 'show_key_elf', 'switch_chart_symbol',
                 '_init_symbol_search_data', '_restore_key_elf',
                 'keyPressEvent', '_KeyElfGlobalFilter', 'symbol_search_data'):
        assert name in src, name
    assert 'KeyElfWindow' in src
    assert 'add_market_watch_window' in src


def test_indicator_and_drawing_persistence_hooks():
    """指标/画线持久化：`save_indicators`/`load_indicators` + 工具箱保存回调 ✓。"""
    source = _source()
    for name in ('def save_indicators', 'def load_indicators',
                 'def _indicator_key', 'def _panel_symbol',
                 'def _init_drawings_persistence', 'def _drawing_tag'):
        assert name in source, name
    assert 'chart_data_manager' in source
    assert 'set_indicators' in source and 'get_indicators' in source
    assert 'save_drawings' in source and 'set_drawings' in source
    assert 'loadDrawings' in source


def test_add_panel_contract_picker_hook():
    """「添加板块」入口暂时注释（功能代码保留）；contract_picker 仍在 ✓。"""
    source = _source()
    assert 'contract_picker' in source
    assert 'def topbar_add_panel' in source
    topbar = _topbar_source()
    # 入口已注释掉，功能代码（hook / add_panel）保留 ✓
    assert "# ('addPanelButton'" in topbar
    assert 'topbar_add_panel' in topbar
    watch = WINDOW.parent / 'pylightcharts_market_watch.py'
    watch_src = watch.read_text(encoding='utf-8')
    assert 'contract_picker' in watch_src
    assert '_show_add_contract_menu' in watch_src


def test_price_alert_hooks_and_dialog():
    """价格预警：设置/清除/触发锁定 + 新 TradingView 预警界面 ✓。"""
    source = _source()
    for name in ('def load_price_alert', 'def show_price_alert_dialog',
                 'def apply_price_alert', 'def reset_price_alert',
                 'def check_price_alert', 'def topbar_alert_context',
                 'def topbar_save_alert', 'def open_tradingview_alert'):
        assert name in source, name
    assert '_alert_fired' in source          # 触发锁定
    assert 'set_price_alerts' in source and 'get_price_alerts' in source

    dialog = WINDOW.parent / 'price_alert_dialog.py'
    assert dialog.exists()
    src = dialog.read_text(encoding='utf-8')
    for name in ('class PriceAlertDialog', 'alertSettingsChanged',
                 'def settings', 'def _validate_input'):
        assert name in src, name
    assert "'both'" in src and "'up'" in src and "'down'" in src

    # 1.7 的新预警界面
    tv = WINDOW.parent / 'tradingview_alert_dialog.py'
    assert tv.exists()
    tv_src = tv.read_text(encoding='utf-8')
    for name in ('class TradingViewAlertDialog', 'def alert',
                 'cross_price', 'expire_at'):
        assert name in tv_src, name


def test_context_menu_and_price_alert_button():
    source = _source()
    for name in ('def show_context_menu', 'def show_price_alert_dialog',
                 'def _menu_action'):
        assert name in source, name
    assert 'CustomContextMenu' in source        # webview 右键
    assert "'指标'" in source and "'删除指标策略'" in source
    # 新增：收藏指标 / 布局 / 收藏布局 / 清除预警（有预警才可用 ✓）
    assert "'收藏指标'" in source
    assert "'收藏布局'" in source
    assert "'清除预警'" in source
    assert 'def has_price_alert' in source
    assert 'def clear_price_alerts' in source
    assert "'插入位置'" not in source           # 旧功能已删 ✓
    # 预警按钮在顶栏（1.7）；旧工具栏的预警菜单已移除 ✓
    topbar = _topbar_source()
    assert 'FluentIcon.RINGER' in topbar and "'预警'" in topbar
    assert 'def show_price_alert_menu' not in source


def test_context_menu_clear_alert_logic(monkeypatch):
    """右键「清除预警」：该格有预警才可用，点它只清该格 ✓。"""
    import sys
    import types
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.windows import pylightcharts_window as pw
    W = pw.PylightchartsChartWindow

    class _Bar:
        @staticmethod
        def info(*args, **kwargs):
            pass

    monkeypatch.setattr(pw, 'InfoBar', _Bar)

    class Chart:
        id = 'c1'

    chart = Chart()
    saved = []
    window = types.SimpleNamespace(
        chart=chart, last_panel=chart,
        _panel_symbol=lambda _c: 'SHFE.ag2612',
        _same_contract=W._same_contract,
        alert_records=lambda: [{'id': 'a1', 'symbol': 'SHFE.ag2612'},
                               {'id': 'a2', 'symbol': 'SHFE.au2612'}],
        _save_alert_records=lambda records: saved.append(list(records)),
        price_alert={}, reset_price_alert=lambda: None,
        panels=lambda: [chart])
    for name in ('_active_chart', 'has_price_alert', 'clear_price_alerts'):
        setattr(window, name, types.MethodType(getattr(W, name), window))

    assert window.has_price_alert() is True
    assert window.clear_price_alerts() == 1     # 只清本格的 1 条 ✓
    assert [r['id'] for r in saved[0]] == ['a2']


def test_period_switch_reloads_panels():
    """周期切换后要重新拉各格数据（`reload_panels` ✓）。"""
    source = _source()
    assert 'def reload_panels' in source
    assert '_on_period' in source
    assert 'self.reload_panels(seconds)' in source
    watch = WINDOW.parent / 'pylightcharts_market_watch.py'
    assert 'reload_panels' in watch.read_text(encoding='utf-8')


def test_watch_window_cycle_normalization_and_insert_position():
    """股票周期归一化 + 插入位置（S5 ✓）。"""
    import sys
    sys.path.insert(0, str(WINDOW.parents[2]))       # 仓库根
    from miniqt.app.windows.pylightcharts_market_watch import (
        normalize_cycle, STOCK_PERIODS)
    assert normalize_cycle(False, 3) == 3            # 期货任意秒
    assert normalize_cycle(False, 123) == 123
    assert normalize_cycle(True, 60) == 60
    assert normalize_cycle(True, 120) == 60          # 最近受支持周期
    assert normalize_cycle(True, 400) == 300
    assert normalize_cycle(True, 1000) == 900
    assert normalize_cycle(True, 99999999) == max(STOCK_PERIODS)

    source = _source()
    assert 'insert_position' in source
    # 右键菜单里旧的「插入位置」已删除 ✓（功能仍在 _insert_index ✓）
    assert "'插入位置'" not in source
    watch = (WINDOW.parent / 'pylightcharts_market_watch.py').read_text(
        encoding='utf-8')
    assert 'def _insert_index' in watch and 'def set_insert_position' in watch


def test_drawings_reload_on_cycle_and_symbol_change():
    """切周期/换合约后画线要按新键重载（`_reload_drawings` ✓）。"""
    source = _source()
    assert 'def _reload_drawings' in source
    assert 'self._reload_drawings(_chart)' in source    # reload_panels 里逐格
    assert 'self._drawing_tag(chart)' in source         # 保存时按格动态取键
    watch = (WINDOW.parent / 'pylightcharts_market_watch.py').read_text(
        encoding='utf-8')
    assert '_reload_drawings' in watch                  # switch_chart_symbol 里
    # 换合约 / 换周期后：K 线被整段替换 → 指标必须**整段重发**（根数常常没变 ✗）✓
    assert 'def _bump_frame_generation' in source
    assert '_indicator_full_redraw' in source
    assert '(not full and count and count == previous' in source
    assert '_bump_frame_generation' in watch
    assert "'refresh_indicators'" in watch         # getattr 拿它
    assert 'refresher(force=True)' in watch         # 换合约后整段重发 ✓
    # 换合约/周期后策略也要重建 runner（不能带旧持仓跑）✓
    # 换合约（根数常常没变）→ 叠加层（信号 / 色带 / 蜡烛）也要 force 重画 ✓
    assert 'def _refresh_indicator_overlays' in source
    assert 'force=full' in source
    assert 'def _refresh_indicator_candles' in source
    assert 'self._refresh_indicator_candles(' in source
    assert 'def reset_strategies' in source
    assert 'self.reset_strategies' in source        # reload_panels 里
    assert "'reset_strategies'" in watch            # switch_chart_symbol 里 getattr
    assert 'resetter(target)' in watch


def test_old_commandbar_toolbar_is_removed():
    """旧 ``CommandBar`` 工具栏已移除，唯一的工具栏就是 TradingView 顶栏 ✓。"""
    source = _source()
    assert 'CommandBar(' not in source          # 不再建旧工具栏
    assert 'self.toolbar' not in source
    assert 'toolbarLayout' not in source
    assert 'TradingViewTopBar' in source and 'self.topbar' in source


def test_panel_callback_uses_the_real_panel_index():
    """喂数要用**该格在面板里的真实下标**（不是回调计数 ✓）。

    ``prepare_panels`` 只回调新建的格，计数从 0 起会错位一格 → 第二格被喂成
    第一格的合约。
    """
    import sys
    import types
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)

    panels = ['a', 'b']
    window = types.SimpleNamespace(
        panels=lambda: list(panels), _track_click=lambda chart: None)
    seen = []
    callback = types.MethodType(W._panel_callback, window)
    hook = callback(lambda chart, index: seen.append((chart, index)))
    hook('b')            # 新建的格在 panels 里是下标 1（不是 0 ✗）
    hook('a')
    assert seen == [('b', 1), ('a', 0)]


def test_set_contracts_clears_stale_panel_frames():
    """合约变了 → 旧的 panel_frames 作废（否则 merge 会混两个合约的数据 ✗）。"""
    import sys
    import types
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)

    window = types.SimpleNamespace(
        contracts=['SHFE.ag2612'],
        panel_frames={'c1': 'old-frame'},
        refresh_topbar=lambda: None,
        data_provider=None, cycle=60, length=1000)
    W.set_contracts(window, ['SHFE.ag2612', 'SHFE.au2612'])
    assert window.panel_frames == {}                 # 旧帧已清 ✓
    assert window.contracts == ['SHFE.ag2612', 'SHFE.au2612']


def test_indicator_worker_guards_deleted_object():
    """后台 worker 被 deleteLater 后，`refresh_indicators` 不能再碰它 ✗。"""
    source = _source()
    assert 'def _on_indicator_worker_finished' in source
    assert 'except RuntimeError' in source
    assert 'worker.deleteLater()' in source
    assert 'self._indicator_worker = None' in source


def test_no_toolbar_button_uses_a_checked_background():
    """周期按钮和画线按钮都不勾选高亮（用户要求）✓。

    （布局菜单里的选项是 ``Action.setCheckable``，不是工具栏按钮 ✓）
    """
    source = _source()
    assert 'button.setCheckable' not in source
    assert 'button.setChecked' not in source
    assert 'def toggle_toolbox' in source
    # 画线工具栏：窗口级共用、钉在整个图表区左边、跟随“最后点击那格” ✓
    assert 'def _active_chart' in source
    assert '_toolbox_visible' in source
    assert 'def _apply_shared_toolbox' in source
    assert "position='fixed'" in source


def test_reload_panels_uses_single_argument_feed():
    """`reload_panels` 必须只给 feed 一个参数（否则 set 不发 → 旧数据 + update 报错 ✗）。"""
    source = _source()
    body = source.split('def reload_panels', 1)[1].split('\n    def ', 1)[0]
    assert 'feed(chart)' in body
    assert 'feed(chart, index)' not in body


def test_screenshot_shows_a_notification():
    source = _source()
    assert "InfoBar.success('截图已保存'" in source
    assert "InfoBar.warning('截图失败'" in source
    assert 'def _save_shot(self' in source          # 变成实例方法（要有 parent 弹 InfoBar）
    assert '@staticmethod' not in source.split('def _save_shot', 1)[0][-40:]


def test_reload_guards_realtime_updates():
    """切周期重载期间不跑实时 update（避免 set 未到就先 update 旧序列 ✗）。"""
    source = _source()
    assert 'self._reloading = False' in source
    assert "getattr(self, '_reloading', False)" in source
    assert 'def _panel_realtime_step' in source


def test_period_label_and_two_line_legend():
    """图例第一行 = 合约名+周期；第二行 = 四价+成交量+百分比（一行）✓。"""
    import sys
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)
    assert W.period_label(60) == '1分'
    assert W.period_label(300) == '5分'
    assert W.period_label(86400) == '1日'
    assert W.period_label(180) == '3分'          # 不在预设里也拼得出
    assert W.period_label(90) == '90秒'

    source = _source()
    assert 'def _panel_legend_title' in source
    assert 'def _style_panel' in source          # 每一格都上图例
    assert 'def _apply_custom_legend' in source
    # 单行图例（D | O | H | L | C | V | pct%）+ 隐藏标题行现在由 pylightcharts
    # **默认**渲染；miniqt 不再自己包一层 legendHandler ✓
    assert 'text_visible=False' in source
    assert "text += ' | V '" not in source      # 不再自己拼一行图例 ✓


def test_panels_all_get_the_legend():
    """多布局时每一格都要上图例（`apply_theme` 不再只给 anchor ✗）。"""
    source = _source()
    body = source.split('def apply_theme', 1)[1].split(
        'def _watch_theme', 1)[0]
    assert 'for chart in panels' in body
    assert 'self._style_panel(chart, colors)' in body
    feed = source.split('def feed_contract_panel', 1)[1].split(
        '\n    def ', 1)[0]
    assert 'self._style_panel(chart)' in feed


def test_custom_legend_only_installs_collapse():
    """`_apply_custom_legend` 现在只装收起/展开按钮。

    单行 K 线信息（``D | O | H | L | C | V | pct%``）与隐藏标题行交给
    pylightcharts **默认**图例渲染，miniqt 不再自己包 ``legendHandler`` ✓。
    """
    import sys
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)

    window = W.__new__(W)

    class Fake:
        id = 'window.fake'

        def __init__(self):
            self.scripts = []

        def run_script(self, script):
            self.scripts.append(script)

    fake = Fake()
    window._apply_custom_legend(fake)
    assert fake.scripts, '应生成收起/展开按钮的 JS'
    assert all('legendHandler' not in script for script in fake.scripts)
    assert any('__miniqtCollapsible' in script for script in fake.scripts)


def test_panel_symbol_and_indicator_key_are_panel_aware():
    """多面板：合约名按 `index % len(contracts)`；子格指标键带 `|p<index>` ✓。"""
    import sys
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)

    class Fake:
        pass

    window = W.__new__(W)
    window.cycle = 60
    anchor, second = Fake(), Fake()
    window.chart = anchor
    window.contracts = ['SHFE.ni2611']
    window.panels = lambda: [anchor, second]
    # 单合约时每一格都显示这个合约（否则子格图例第一行缺合约名 ✗）
    assert window._panel_symbol(anchor) == 'SHFE.ni2611'
    assert window._panel_symbol(second) == 'SHFE.ni2611'

    window.contracts = ['A', 'B', 'C']
    assert window._panel_symbol(anchor) == 'A'
    assert window._panel_symbol(second) == 'B'
    # anchor 用 合约|周期；子格再加 |p<index>，避免共用键导致重复恢复 ✗
    assert window._indicator_key(anchor) == 'A|60'
    assert window._indicator_key(second) == 'B|60|p1'


def test_load_indicators_skips_a_chart_that_already_has_them():
    source = _source()
    body = source.split('def load_indicators', 1)[1].split('\n    def ', 1)[0]
    assert "any(entry.get('chart') is chart" in body


def test_chart_font_size_setting_applies_to_legend():
    """「图表字体大小」配置项 + apply_chart_font 把字号刷到所有图表图例 ✓。"""
    import sys
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.common.chart_config import chart_cfg
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)

    assert chart_cfg.DEFAULT_CONFIG['FontSize'] == 14      # 默认 14

    scripts = []

    class Fake:
        id = 'window.fake'

        def run_script(self, script):
            scripts.append(script)

    window = W.__new__(W)
    window.chart = Fake()
    window._order_tickets = {}
    window.panels = lambda: [window.chart]
    original = chart_cfg.chartFontSize.value
    try:
        chart_cfg.chartFontSize.value = 15
        window.apply_chart_font()
    finally:
        chart_cfg.chartFontSize.value = original
    assert any("fontSize='15px'" in script for script in scripts)


def test_style_panel_passes_the_font_size_to_legend():
    """重上主题 / 新建面板时也要带着用户字号，否则会被默认 11px 覆盖 ✗。"""
    import sys
    import types
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)

    calls = []

    class FakeChart:
        def legend(self, **kwargs):
            calls.append(kwargs)

    window = types.SimpleNamespace(
        _panel_legend_title=lambda _chart: 'SHFE.ag2612  1分',
        _chart_font_size=lambda: 17,
        _current_colors=lambda: {'text': '#d1d4dc'},
        _apply_custom_legend=lambda _chart: None)
    W._style_panel(window, FakeChart())
    assert calls and calls[0]['font_size'] == 17
    assert calls[0]['text'] == 'SHFE.ag2612  1分'


def test_sim_panel_fit_height_uses_the_laid_out_metrics_height():
    """FlowLayout 的 sizeHint 会失真到 ~460；fit 高度要用 heightForWidth ✓。"""
    import sys
    import types
    sys.path.insert(0, str(WINDOW.parents[2]))
    from PyQt6.QtCore import QMargins, QSize
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)

    class Metrics:
        def maximumHeight(self):
            return 170

        def width(self):
            return 940

        def hasHeightForWidth(self):
            return True

        def heightForWidth(self, _width):
            return 84

        def height(self):
            return 84

        def minimumHeight(self):
            return 0

        def sizeHint(self):
            return QSize(940, 462)          # 失真值：不能用 ✗

    class OrderTicket:
        def sizeHint(self):
            return QSize(240, 368)

        def height(self):
            return 368

        def minimumHeight(self):
            return 0

    class PageLayout:
        def contentsMargins(self):
            return QMargins(8, 4, 8, 6)

        def spacing(self):
            return 4

    class Page:
        metricsContainer = Metrics()
        orderTicket = OrderTicket()

        def width(self):
            return 940

        def layout(self):
            return PageLayout()

    class TitleBar:
        def sizeHint(self):
            return QSize(100, 28)           # 旧 sizeHint；实际 Fixed 高度是 34

        def width(self):
            return 0

        def height(self):
            return 0

        def minimumHeight(self):
            return 34

    class Panel:
        accountPage = Page()
        titleBar = TitleBar()

    window = types.SimpleNamespace(simPanel=Panel())
    # 34（标题栏）+ 3（分隔线兜底）+ 14（页边距 4+4+6）
    # + 84（概览真实高度，非 462）+ 368（下单窗口）= 503
    assert W._sim_panel_fit_height(window) == 503


def test_panel_realtime_merge_keeps_loaded_history():
    """实时帧并入 panel_frames 时不能把无限历史补进来的更早 K 线丢掉 ✗。"""
    import sys
    import types
    import pandas as pd
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)

    full = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=10, freq='min'),
        'open': range(10), 'high': range(10), 'low': range(10),
        'close': range(10), 'volume': range(10)})
    short = full.tail(3).reset_index(drop=True).copy()
    short['close'] = [100, 101, 102]

    window = types.SimpleNamespace(panel_frames={'c1': full})
    window._merge_panel_frame = types.MethodType(W._merge_panel_frame, window)
    merged = window._merge_panel_frame('c1', short)
    assert len(merged) == 10                          # 历史没丢 ✓
    assert list(merged['close'].iloc[:7]) == list(range(7))
    assert list(merged['close'].iloc[-3:]) == [100, 101, 102]

    # 没有历史（相等长度）→ 直接替换 ✓
    window.panel_frames['c2'] = short
    replaced = window._merge_panel_frame('c2', short)
    assert len(replaced) == 3


def test_shared_toolbox_pins_only_the_active_chart_on_the_left():
    """多布局：画线工具栏只把**当前点击那格**钉在左边，其余隐藏 ✓。"""
    import sys
    import types
    sys.path.insert(0, str(WINDOW.parents[2]))
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow as W)

    class Chart:
        def __init__(self, cid):
            self.id = cid
            self.scripts = []
            self.toolbox = None

        def run_script(self, script):
            self.scripts.append(script)

    a, b = Chart('window.a'), Chart('window.b')
    window = types.SimpleNamespace(
        chart=a, panels=lambda: [a, b], last_panel=b,
        _toolbox_visible=False)
    window._ensure_toolbox = lambda chart: (
        setattr(chart, 'toolbox', object()) or chart.toolbox)
    for name in ('_active_chart', '_apply_shared_toolbox', 'toggle_toolbox'):
        setattr(window, name, types.MethodType(getattr(W, name), window))
    window._pin_toolbox_js = W._pin_toolbox_js
    window._hide_toolbox_js = W._hide_toolbox_js

    # 让 a 也有工具箱（模拟它之前是当前格）→ 切到 b 时 a 要被隐藏 ✓
    a.toolbox = object()
    W._apply_shared_toolbox(window, b, True)
    assert any("position='fixed'" in s for s in b.scripts)
    assert any("display='none'" in s for s in a.scripts)

    # 点 a → 可见工具栏切到 a（a 钉住、b 隐藏）✓
    a.scripts.clear()
    b.scripts.clear()
    W._apply_shared_toolbox(window, a, True)
    assert any("position='fixed'" in s for s in a.scripts)
    assert any("display='none'" in s for s in b.scripts)

    # 窗口级开关：开 → 关 ✓
    assert W.toggle_toolbox(window) is True
    assert window._toolbox_visible is True
    assert W.toggle_toolbox(window) is False
    assert window._toolbox_visible is False


def test_bottom_dock_hides_when_all_pages_closed():
    """底部面板页全关光 → 收起；工具栏「交易 / 代码编辑器」再唤醒 ✓。"""
    source = _source()
    # 连接宿主槽
    assert 'allPagesClosed.connect(self._on_dock_all_pages_closed)' in source
    # 槽里收起面板
    body = source.split('def _on_dock_all_pages_closed', 1)[1]
    body = body.split('\n    def ', 1)[0]
    assert 'toggle_sim_panel(False)' in body
    # 「交易」按钮：藏着 / 模拟账户页没了 → 先唤醒
    hook = source.split('def topbar_toggle_sim_panel', 1)[1]
    hook = hook.split('\n    def ', 1)[0]
    assert 'isHidden()' in hook and "has_page('sim')" in hook
    assert 'open_sim_account_page()' in hook
    # 「代码编辑器」/ 其它 dock 页：显示时连比例一起恢复
    show = source.split('def _show_dock_page', 1)[1]
    show = show.split('\n    def ', 1)[0]
    assert 'toggle_sim_panel(True)' in show


def test_order_ticket_is_created_for_every_layout_panel():
    """多布局：买卖盘**每格一个**（按图唯一 host id），不能只挂在第一格 ✓。"""
    source = _source()
    assert 'self._order_tickets: dict' in source
    assert 'def _order_ticket_charts' in source
    assert "host_id = f'__orderTicketHost_{key}'" in source
    assert 'for chart in charts:' in source
    # 换布局 / 新格子：延后补一次
    assert 'QTimer.singleShot(300, self._sync_order_ticket)' in source


def test_position_line_toggle_targets_every_layout_panel():
    """持仓线按钮也要覆盖**每一格**（不只第一格）✓。"""
    source = _source()
    assert 'def _layout_charts' in source
    assert 'panels = self._layout_charts()' in source
    assert 'for chart in self._layout_charts():' in source
    assert 'QTimer.singleShot(300, self._ensure_position_line_all_panels)' in source


def test_sim_ticket_follows_clicked_panel_only_when_open():
    """点哪一格 → 模拟账户二级报价切到该格合约；只在模拟账户页可见时切 ✓。"""
    source = _source()
    assert 'def _sync_sim_ticket_to_chart' in source
    assert 'self._sync_sim_ticket_to_chart(chart)' in source
    assert 'self.simPanel.stack.currentWidget() is not page' in source
    assert 'not self.simPanel.stack.isVisible()' in source
    assert 'page.set_ticket_symbol(symbol)' in source


def test_context_menu_has_period_and_strategy_favorites():
    """右键：周期菜单 / 收藏策略 / 删除指标策略（都要能真正执行 ✓）。"""
    source = _source()
    assert 'def _build_context_period_menu' in source
    assert 'def _build_favorite_strategies_menu' in source
    assert 'def _apply_favorite_strategy' in source
    assert "'收藏策略'" in source
    assert 'self.topbar_set_cycle(s)' in source
    # 删除菜单：指标 + 策略都列，点策略走 remove_strategy ✓
    assert "'删除指标策略'" in source
    assert 'self.remove_strategy(sid)' in source


def test_indicator_settings_menu_follows_the_mouse():
    """多布局：指标齿轮的设置卡片要出现在鼠标位置（不再跑到第一格）✓。"""
    source = _source()
    assert 'QCursor.pos() + QPoint' in source
    # 兜底仍然保留按 (x, y) 映射
    assert 'webview.mapToGlobal(QPoint(int(x), int(y)))' in source


def test_sim_account_log_page_replaces_notes():
    """模拟账户「笔记」→「日志」：指标/策略加载信息要能在这里看到 ✓。"""
    sim = (WINDOW.parent / 'sim_account_panel.py').read_text(encoding='utf-8')
    assert 'class LogPage' in sim
    assert "('log', '日志')" in sim or "add_page('log', '运行日志'" in sim
    assert "('notes', '笔记')" not in sim
    assert 'def append_log' in sim
    # 日志默认打开 + 未入 stack 前先 hide（修标题栏左侧文字残留 ✓）
    assert ("self.add_page('log', '日志', self.logPage)" in sim
            or "self.add_page('log', '运行日志', self.logPage)" in sim)
    assert 'self.logPage.hide()' in sim
    source = _source()
    assert "recorder(f'[{level}] {title}：{content}')" in source
    assert "self._append_ui_log(f'[指标] {group}.{name} 已加载')" in source


def test_strategy_same_name_replaces_the_old_one():
    """同图重复加载同名策略 → 先删旧再挂新（像指标一样）✓；
    不同名仍保持「每格只能挂一个策略」✓。"""
    source = _source()
    body = source.split('def _finish_strategy_record', 1)[1].split('\n    def ', 1)[0]
    assert 'same, other = [], []' in body
    assert "self.remove_strategy(record.get('id'))" in body
    assert '每格只能挂一个策略' in body
    # 先判断“不同名”，再删同名 → 不同名时不动原来的策略 ✓
    assert body.index('if other:') < body.index('for record in same:')
    # 旧的一次性冲突判断已移除（改为 same/other 分流 ✓）
    assert "cids & set(getattr(self, '_panel_strategies', {}))" not in source


def test_same_name_strategy_reload_keeps_user_indicators():
    """同名策略重载（改参数后重新加载）要保留用户自己加的指标 ✓。"""
    source = _source()
    body = source.split('def _finish_strategy_record', 1)[1].split('\n    def ', 1)[0]
    assert 'if not same:' in body
    # _clear_indicators_on 在“非同名替换”分支里（同名重载跳过 ✓）
    assert body.index('if not same:') < body.index('self._clear_indicators_on(chart)')
    # 旧策略的线仍由 remove_strategy 删除 ✓
    assert "self.remove_strategy(record.get('id'))" in body
