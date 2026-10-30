"""前端剩余项：优化表筛选/排序、嵌套参数写回、Web tab 安全、二级报价按钮。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / 'jslib' / 'src' / 'desk'


def _read(name):
    return (DESK / name).read_text(encoding='utf-8')


def test_optimization_table_has_filter_and_sort():
    page = _read('strategy-lab-page.ts')
    assert 'data-opt-filter' in page
    assert 'data-opt-sort' in page
    assert 'private _renderOptimization()' in page
    assert 'this.optSortDir *= -1' in page
    css = _read('desk.css')
    assert '.desk-strategy-opt-filter' in css
    assert '.desk-strategy-table th.sortable' in css


def test_params_writeback_handles_nested_dict():
    page = _read('editor-panel.ts')
    assert 'function replaceParamsDict(' in page
    assert 'depth += 1' in page and 'depth -= 1' in page
    assert 'text.slice(index + 1)' in page      # 配对到最后一个右括号 ✓


def test_web_tab_nav_checks_iframe_source_and_escapes_url():
    page = _read('app.ts')
    assert 'frame.contentWindow === event.source' in page
    assert 'iframe.desk-web-frame' in page
    assert 'escapeHtml(url)' in page
    assert 'title="${safeUrl}"' in page


def test_local_toolbar_has_book_button():
    page = _read('local-chart-page.ts')
    append = page.split('toolbar.append(', 1)[1].split(');', 1)[0]
    assert 'bookButton' in append


def test_account_table_empty_state():
    page = _read('account-dock.ts')
    assert 'if (!rows.length)' in page
    assert '（暂无数据）' in page


def test_login_clears_old_password():
    page = _read('login-dialog.ts')
    assert "if (!('password' in saved))" in page
    assert "password.value = ''" in page


def test_menu_listeners_are_released():
    for name in ('menu.ts', 'indicator-menu.ts', 'param-popover.ts'):
        page = _read(name)
        assert 'dismissHandler' in page
        assert "removeEventListener('mousedown', dismissHandler)" in page


def test_short_replay_index_never_exceeds_total():
    page = _read('replay.ts')
    assert 'this.bars.length\n            ? Math.max(1' in page
    assert 'Math.max(5, Math.min(this.bars.length' not in page
    assert 'Math.max(5, Math.round(this.bars.length' not in page


def test_screenshot_has_feedback():
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = _read(name)
        assert "当前图表暂不支持截图" in page


def test_topbar_has_search_and_log():
    page = _read('app.ts')
    assert "title = '全局搜索（打开报价页并聚焦搜索框）'" in page
    assert "title = '打开运行日志'" in page
    assert 'this.quotePage?.focusSearch()' in page
    assert 'this.openLog()' in page


def test_settings_personalization_rows():
    page = _read('settings-page.ts')
    for key in ('indicator_overlay_filter', 'ticker_only_quoted',
                'watch_default_group'):
        assert key in page
    prefs = (ROOT / 'minibt' / 'desk' / 'user_prefs.py').read_text(
        encoding='utf-8')
    assert "'watch_default_group'" in prefs
    home = _read('home-page.ts')
    assert 'setDefaultGroup(' in home


def test_home_workspace_replay_alert_pages_are_real():
    page = _read('workspace-pages.ts')
    for name in ('class WorkspacePage', 'class ReplayLabPage',
                 'class AlertCenterPage'):
        assert name in page
    app = _read('app.ts')
    for name in ('openWorkspace(', 'openReplayLab(', 'openAlertCenter('):
        assert name in app
    home = _read('home-page.ts')
    for name in ('onOpenWorkspace', 'onOpenReplayLab', 'onOpenAlerts'):
        assert name in home


def test_option_columns_entry_exists():
    page = _read('quote-page.ts')
    assert "textContent = '期权列'" in page
    assert 'this._applyFavoriteColumn()' in page


def test_stock_trade_ui_and_polling():
    login = _read('login-dialog.ts')
    assert 'data-f="trade"' in login
    assert "dataset.f = 'trd_env'" in login
    assert "dataset.f = 'trd_market'" in login
    assert "['CN', '沪深市场']" in login
    assert "['HK', '香港市场']" in login
    assert "['US', '美国市场']" in login
    assert "['JP', '日本市场']" in login
    assert "values.trd_env" in login
    app = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "params.get('trade')" in app
    assert "trd_env=str(params.get('trd_env')" in app
    stock = (ROOT / 'minibt' / 'stock_api.py').read_text(encoding='utf-8')
    assert 'def _refresh_real_orders' in stock
    assert 'order_list_query' in stock
    assert 'SUBMITTED' in stock


def test_place_order_accepts_qty_payload():
    app = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "payload.get('volume') or payload.get('qty')" in app
    ticket = _read('replay-ticket.ts')
    assert "qtyLabel.textContent = options.qtyLabel || '手数'" in ticket
    assert "options.qtyDefault || 1" in ticket


def test_home_account_switcher():
    page = _read('home-page.ts')
    assert 'HomeAccountChoice' in page
    assert 'data-home-account' in page
    assert "home_account_kind" in page
    app = _read('app.ts')
    assert "case 'home_account'" in app
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'home_account_kind': self._on_home_account_kind" in backend
    assert "快期模拟" in backend and "富途模拟" in backend


def test_home_watch_rows_refresh_each_tick():
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    block = backend.split('def _home_rows(', 1)[1].split(
        'def home_signals(', 1)[0]
    assert 'refresh: bool = True' in block
    assert 'if refresh or symbol not in by_symbol' in block


def test_home_main_stays_on_futures_feed():
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    block = backend.split('def _on_home_main(', 1)[1].split(
        'def _on_home_preview(', 1)[0]
    assert 'feed = self.futures or self.current_feed()' in block


def test_empty_futures_rows_retry_after_login():
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'def _retry_empty_rows' in backend
    assert '2 秒后自动重试' in backend
    block = backend.split('def _drain_rows_result(', 1)[1].split(
        'def _cache_key(', 1)[0]
    assert '_empty_rows_retry_at = time.monotonic() + 2.0' in block


def test_home_main_empty_rows_auto_retry():
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert '_home_main_retry_exchange' in backend
    block = backend.split('def _refresh_home(', 1)[1].split(
        'def symbol_cache(', 1)[0]
    assert '_on_home_main' in block


def test_indicator_last_incremental_frontend_and_backend():
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'def _refresh_indicator_last' in backend
    assert "'mode': 'last'" in backend
    assert 'INDICATOR_TAIL_BARS' in backend
    indicator = (ROOT / 'jslib' / 'src' / 'desk' / 'indicator.ts').read_text(
        encoding='utf-8')
    assert 'applyLast(payload' in indicator
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'chart-page.ts').read_text(
        encoding='utf-8')
    assert '_mergeLastItems' in page
    assert "payload.mode === 'last'" in page


def test_profile_is_opt_in():
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "MINIBT_DESK_PROFILE" in backend
    assert '[性能] 看盘 tab 明细' in backend


def test_realtime_table_follows_last_bar():
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'chart-page.ts').read_text(
        encoding='utf-8')
    assert '_refreshLiveTables' in page
    assert "_syncTableIndex(null, true)" in page


def test_indicator_interval_settings_ui():
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'settings-page.ts').read_text(
        encoding='utf-8')
    for text in ('指标/策略图表更新频率', 'VP / 表格只在新 K 线更新',
                 'K 线推送'):
        assert text in page
    for old in ('主图指标刷新间隔', '副图指标刷新间隔', 'VP / 表格刷新间隔'):
        assert old not in page
    prefs = (ROOT / 'minibt' / 'desk' / 'user_prefs.py').read_text(
        encoding='utf-8')
    for key in ('indicator_refresh_interval_ms',
                'indicator_custom_new_bar'):
        assert key in prefs


def test_vp_eye_toggle_syncs_canvas_overlay():
    """👁 隐藏指标时，VP（canvas 覆盖层）也要跟着隐藏 ✓

    注意：眼睛只隐藏**指标线**，指标标签/图例行必须留在原地（用户要求），
    所以这里不再用「过滤 items 再 layer.apply」那种删标签的做法 ✗。
    """
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = (ROOT / 'jslib' / 'src' / 'desk' / name).read_text(
            encoding='utf-8')
        assert 'this._syncVpOverlay(cell, (this.cellItems[cell] || [])' in page
        assert '.filter((item) => !hidden.has(item.key)));' in page
        # 删 items 的旧做法不能回来（会把指标标签一起删掉 ✗）
        assert '_visibleItems' not in page


def test_saved_layout_key_falls_back_to_cols_rows():
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = (ROOT / 'jslib' / 'src' / 'desk' / name).read_text(
            encoding='utf-8')
        assert 'DESK_LAYOUTS.find((item) => item.key === String(payload.key))' in page
        assert 'const preset = payload.key' in page
        assert 'preset || (payload.count !== undefined' in page


def test_band_fill_runs_after_line_series_creation():
    layer = (ROOT / 'jslib' / 'src' / 'desk' / 'indicator.ts').read_text(
        encoding='utf-8')
    loop = layer.index('for (const item of items) {')
    band = layer.index('this._applyBands(items);', loop)
    assert band > loop


def test_indicator_settings_keep_state_and_fit_after_growth():
    layer = (ROOT / 'jslib' / 'src' / 'desk' / 'indicator.ts').read_text(
        encoding='utf-8')
    assert 'styleOverrides' in layer
    assert 'styleOf(key: string)' in layer
    assert 'setVisible(key: string' in layer
    assert 'lineStyle: saved.lineStyle' in (
        ROOT / 'jslib' / 'src' / 'desk' / 'chart-page.ts'
    ).read_text(encoding='utf-8')
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'chart-page.ts').read_text(
        encoding='utf-8')
    assert 'this.bars.length > before + 1' in page
    assert 'this.needsFit = true;' in page
