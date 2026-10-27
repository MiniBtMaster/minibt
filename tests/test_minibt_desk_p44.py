"""P44：布局（含跨格）/ 关闭图表 / 报价页修复 / 设置页 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(path):
    return (ROOT / path).read_text(encoding='utf-8')


# ------------------------------------------------------- ① 布局（跨格）
def test_layout_presets_include_spans():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    for key, label in (("'v2'", '上下两图'), ("'t1b2'", '上下左下右'),
                       ("'t2b1'", '上左上右下'), ("'h3'", '横排三个'),
                       ("'v3'", '竖排三个')):
        assert key in page, key
        assert label in page, label
    # 跨格：上 1 下 2 → 第一格 colSpan=2；上 2 下 1 → 第三格 colSpan=2
    assert 'cells: [[0, 0, 2, 1], [0, 1, 1, 1], [1, 1, 1, 1]]' in page
    assert 'cells: [[0, 0, 1, 1], [1, 0, 1, 1], [0, 1, 2, 1]]' in page
    # 建格按 cells 摆（gridColumn / gridRow 的 span ✓）
    assert 'cell.style.gridColumn = `${col + 1} / span' in page
    assert 'cell.style.gridRow = `${row + 1} / span' in page
    # 菜单用 DESK_LAYOUTS 全量列出
    assert 'DESK_LAYOUTS.map((item) => ({' in page


def test_layout_spec_helpers():
    """`layoutSpecOf` / `layoutSpecByKey` / `layoutSpecForCount` ✓"""
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    for name in ('export function layoutSpecOf(', 'export function layoutSpecByKey(',
                 'export function layoutSpecForCount('):
        assert name in page, name
    assert "setLayoutByKey(key: string)" in page


# ------------------------------------------------------- ② 关闭图表
def test_context_menu_close_chart():
    menu = (DESK_TS / 'chart-context-menu.ts').read_text(encoding='utf-8')
    assert 'canCloseChart?: boolean' in menu
    assert "'关闭图表（只有一格）'" in menu
    assert 'disabled: !spec.canCloseChart' in menu
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    assert 'canCloseChart: this.cells.length > 1' in page
    assert 'closeCell(index = -1): boolean' in page
    local = (DESK_TS / 'local-chart-page.ts').read_text(encoding='utf-8')
    assert 'closeCell(index = -1): boolean' in local


def test_close_cell_keeps_remaining_cells():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    body = page.split('closeCell(index = -1): boolean {', 1)[1][:1400]
    assert 'this.cells.length <= 1' in body          # 只剩一格 → 不许关
    assert 'layoutSpecForCount(' in body
    assert 'this.cellItems.map(' in body


# ------------------------------------------------------- ③ 报价页修复
def test_quote_updates_only_touch_known_rows():
    """rows_update 只更新已有行（否则主力里会混进别的交易所 ✗）"""
    quote = (DESK_TS / 'quote-page.ts').read_text(encoding='utf-8')
    body = quote.split('updateRows(rows: RowData[]): this {', 1)[1][:1200]
    assert 'if (!known) continue;' in body
    assert "{ ...known, ...row }" in body
    assert 'if (next.spark == null && known.spark != null)' in body
    assert "if (!String(next.name ?? '').trim()) next.name = known.name" in body


def test_backend_filters_visible_and_keeps_spark():
    app = _read('minibt/desk/app.py')
    # 只认当前清单里的合约（清单为空时不过滤，离线 / 单测也对 ✓）
    assert 'keys = [key for key in (self.visible or [])' in app
    assert 'if not known or key in known]' in app
    assert "spark = self._spark.get(str(item.get('symbol') or ''))" in app
    assert "item['spark'] = spark" in app


def test_backend_name_fallback():
    app = _read('minibt/desk/app.py')
    assert 'def _name_of(self, symbol: str) -> str:' in app
    # P84：名称改成**主线程小批补**（不再一次性 query_symbol_info 卡界面 ✓）
    assert 'def _fill_names_step(' in app
    assert '_name_queue' in app


# ------------------------------------------------------- ④ 设置页
def test_settings_page_sections():
    page = (DESK_TS / 'settings-page.ts').read_text(encoding='utf-8')
    for text in ('本地文件', '个性化', '关于', '图表配置', '图表颜色',
                 '应用主题', '主题色', '界面缩放',
                 '恢复当前页面默认值', '期货历史长度', '期货数据长度', '图表字体大小',
                 '持仓线', '挂单线',          # P77 起在图表配置里 ✓
                 '鼠标标签颜色', '上涨颜色', '下跌颜色',
                 '帮助', '提供反馈', '检查更新'):
        assert text in page, text
    assert 'open_data_dir' in page and 'open_url' in page


def test_settings_topbar_buttons_and_closable_tab():
    app = (DESK_TS / 'app.ts').read_text(encoding='utf-8')
    assert "site.textContent = '🌐'" in app           # minibt 官网
    assert "gear.textContent = '⚙'" in app            # 设置
    assert "'https://www.minibt.cn'" in app
    assert 'openSettings(' in app
    assert 'SETTINGS_TAB_ID' in app
    # P89 起：除首页外所有页签都可关闭（`tab.kind !== 'home'` ✓）
    assert "if (tab.kind !== 'home') {" in app
    # 缩放 / 主题色 / 图表项都落地
    assert 'private _applyZoom(' in app
    assert 'private _applyAccent(' in app
    assert 'private _applySettings(' in app


def test_settings_backend_support():
    prefs = _read('minibt/desk/user_prefs.py')
    for key in ('theme_accent', 'ui_zoom', 'chart_font_size',
                'chart_history', 'chart_data_length', 'chart_color_up',
                'chart_color_down', 'chart_color_crosshair', 'app_theme',
                'chart_reset', 'position_line', 'order_line'):
        assert f"'{key}'" in prefs, key
    app = _read('minibt/desk/app.py')
    assert "'open_url': self._on_open_url" in app
    assert "'open_data_dir': self._on_open_data_dir" in app
    assert 'def candles_length(self) -> int:' in app
    assert 'def chart_lengths(self) -> tuple:' in app


def test_chart_config_applied_to_pages():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    assert 'setChartConfig(values: Record<string, unknown>): void' in page
    assert 'private _applyCrosshairColor(): void' in page
    assert 'this.customUp || pal.up' in page      # 自定义涨跌色 ✓
