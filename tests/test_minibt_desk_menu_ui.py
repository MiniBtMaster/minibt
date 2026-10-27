"""图表右键菜单 / 二级报价交易 / 图例齿轮 / 画线按钮 / 合约概览 回归测试。"""
from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

JSLIB = REPO / 'jslib' / 'src' / 'desk'
GENERAL = REPO / 'jslib' / 'src' / 'general'


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


# ---------------------------------------------------------------- 右键菜单
def test_chart_context_menu_matches_miniqt():
    menu = _read(JSLIB / 'chart-context-menu.ts')
    for label in ('指标', '收藏指标', '收藏策略', '删除指标策略',
                  '周期', '布局', '收藏布局', '画线', '清除画线',
                  '价格预警', '清除预警', '截图'):
        assert f"label: '{label}'" in menu or f"'{label}'" in menu, label
    assert 'showMenu(x, y, items)' in menu


def test_chart_page_wires_context_menu_and_clear_alerts():
    page = _read(JSLIB / 'chart-page.ts')
    assert "import { showChartContextMenu }" in page
    assert "this.host.addEventListener('contextmenu'" in page
    assert 'Drawing.hoveredObject' in page
    assert 'private _openChartContextMenu(' in page
    assert 'clearAlerts(): void' in page
    assert "onCommand?.('clear_alerts'" in page
    app = _read(REPO / 'minibt' / 'desk' / 'app.py')
    assert "'clear_alerts': self._on_clear_alerts" in app
    assert 'def _on_clear_alerts' in app


# ---------------------------------------------------- 二级报价 平/反/撤
def test_book_trading_flag_uses_symbol_feed_not_quote_filter():
    from minibt.desk.app import Desk

    class Api:
        def get_position(self, symbol, **kwargs):
            return None

    class Feed:
        kind = 'futures'

        def __init__(self):
            self.api = Api()

        def available(self):
            return True

    desk = Desk(offline=True, browser=True)
    feed = Feed()
    desk.futures = feed
    desk.feeds = [feed]
    desk.trading = True
    # 报价页停在「股票」时，期货合约的二级报价按钮仍应可用 ✓
    desk.filter = {'type': 'STOCK', 'exchange': '', 'text': ''}
    assert desk.book_payload('SHFE.rb2610', feed)['trading'] is True


def test_trading_close_reverse_cancel_use_symbol_api():
    from minibt.desk.app import Desk
    from minibt.desk.trading import Trading

    class Pos:
        pos_long = 2
        pos_short = 0

    class Task:
        def __init__(self):
            self.target = None

        def set_target_volume(self, value):
            self.target = value

    class Api:
        def __init__(self):
            self.task = Task()
            self.cancelled = []

        def get_position(self, symbol, **kwargs):
            return Pos()

        def target_pos_task(self, symbol):
            return self.task

        def get_order(self, **kwargs):
            return [{'order_id': 'o1', 'status': 'ALIVE',
                     'instrument_id': 'SHFE.rb2610'}]

        def cancel_order(self, order_id, **kwargs):
            self.cancelled.append(order_id)

    class Feed:
        kind = 'futures'

        def __init__(self):
            self.api = Api()

        def available(self):
            return True

    desk = Desk(offline=True, browser=True)
    feed = Feed()
    desk.futures = feed
    desk.feeds = [feed]
    desk.trading = True
    desk.filter = {'type': 'STOCK', 'exchange': '', 'text': ''}
    trader = Trading(desk)
    assert '目标仓位' in trader.action('close', 'SHFE.rb2610')
    assert feed.api.task.target == 0
    assert '目标仓位' in trader.action('reverse', 'SHFE.rb2610')
    assert feed.api.task.target == -2
    assert '已撤 1 笔' in trader.action('cancel', 'SHFE.rb2610')
    assert feed.api.cancelled == ['o1']


def test_desk_clear_alerts_command():
    from minibt.desk.app import Desk
    desk = Desk(offline=True, browser=True)
    patches = []
    desk.sender = lambda script: patches.append(script)
    desk._booted = True
    desk.alerts = [{'id': 1, 'symbol': 'X', 'price': 1}]
    desk.handle('desk_~_' + json.dumps({'cmd': 'clear_alerts'}))
    assert desk.alerts == []
    assert any('"type":"alerts"' in item and '"items":[]' in item
               for item in patches)


# ---------------------------------------------------- 齿轮 / 画线按钮
def test_gear_uses_same_stroke_as_eye():
    legend = _read(GENERAL / 'legend.ts')
    gear = legend.split('export const GEAR', 1)[1].split('export const EYE_OPEN', 1)[0]
    eye = legend.split('export const EYE_OPEN', 1)[1].split('export const EYE_CLOSED', 1)[0]
    assert 'stroke-width:2' in gear
    assert 'stroke-opacity:1' in gear
    assert 'stroke-miterlimit:4' in gear
    assert 'stroke-width:2' in eye


def test_toolbox_button_is_left_of_position_line_and_highlights():
    for name in ('chart-page.ts',):
        page = _read(JSLIB / name)
        append = page.split('toolbar.append(', 1)[1].split(');', 1)[0]
        assert append.index('lineButton') < append.index('ticketButton'), name
        assert 'this.lineButton = lineButton' in page
        assert "this.lineButton?.classList.toggle('on', this.toolBoxOn)" in page


# ---------------------------------------------------- 合约概览 / 迷你图
def test_symbol_preview_has_close_button_and_esc():
    preview = _read(JSLIB / 'symbol-preview.ts')
    assert 'desk-preview-close' in preview
    assert "event.key === 'Escape'" in preview
    assert 'pointerdown' in preview


def test_sparkline_uses_real_width_and_dpr():
    preview = _read(JSLIB / 'symbol-preview.ts')
    show = preview.split('show(data: PreviewData', 1)[1].split(
        'const box', 1)[0]
    # 先显示再画，避免隐藏时按 80px 画完再放大 ✓
    assert show.index("style.display = ''") < show.index('this.update(data)')
    assert "reSize('100%', 40)" in preview
    spark = _read(REPO / 'jslib' / 'src' / 'panels' / 'sparkline.ts')
    assert 'devicePixelRatio' in spark
    assert 'parentElement?.clientWidth' in spark


# ---------------------------------------------------- 本地图表：多布局/联动
def test_gear_css_inherits_legend_color():
    css = _read(GENERAL / 'styles.css')
    block = css.split('.legend-settings-switch {', 1)[1].split('}', 1)[0]
    assert 'color: inherit' in block


def test_local_toolbar_has_link_ticket_layout():
    page = _read(JSLIB / 'local-chart-page.ts')
    append = page.split('toolbar.append(', 1)[1].split(');', 1)[0]
    for name in ('linkButton', 'ticketButton', 'layoutButton'):
        assert name in append, name
    assert 'openLocalLayoutMenu' in page
    assert 'setLayoutSpec(' in page
    assert 'openLocalLayoutMenu' in page


def test_local_layout_starts_with_first_chart_data():
    page = _read(JSLIB / 'local-chart-page.ts')
    layout = page.split('setLayout(cols: number', 1)[1].split(
        'private _buildCells', 1)[0]
    assert 'oldBars[0]?.length ? oldBars[0]' in layout
    assert 'oldBars[index]?.length ? oldBars[index] : firstBars' in layout
    assert 'localIndicators[index] = oldIndicators[index]' in layout


def test_local_link_aligns_by_index_not_time():
    page = _read(JSLIB / 'local-chart-page.ts')
    link = page.split('private _bindLink()', 1)[1].split(
        'togglePositionLine', 1)[0]
    assert 'setVisibleLogicalRange(range)' in link
    assert 'param.logical' in link
    assert 'Math.round(logical)' in link
    assert 'subscribeVisibleTimeRangeChange' not in link


def test_local_replay_builds_per_cell_bars_and_indicators():
    page = _read(JSLIB / 'local-chart-page.ts')
    start = page.split('startReplay(options', 1)[1].split(
        '/** 进入回放', 1)[0]
    assert 'this.cellBars.map' in start
    assert 'this.localIndicators[index]' in start
    assert 'cells,' in start
    exit_block = page.split('exitReplay(): void', 1)[1].split(
        '// ------------------------------------------------------------- 删除', 1)[0]
    assert 'this.localBarsByCell[index]' in exit_block
    assert 'this.localIndicators[index]' in exit_block


def test_play_pause_icons_are_svg():
    icons = _read(JSLIB / 'icons.ts')
    assert 'export const ICON_PLAY' in icons
    assert 'export const ICON_PAUSE' in icons
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = _read(JSLIB / name)
        assert 'play.innerHTML = ICON_PLAY' in page
        assert 'ICON_PAUSE : ICON_PLAY' in page


def test_local_indicator_payload_has_full_history_and_cell():
    from minibt.desk.app import Desk
    desk = Desk(offline=True, browser=True)
    desk.local_store().set_indicators('test', [{'key': 'MA',
                                                'params': {'length': 10}}], 2)
    payload = desk._local_indicator_payload('test', 2)
    assert payload['cell'] == 2
    assert payload['items']
    # 全历史（> 600）—— 回放早期也能画指标 ✓
    assert len(payload['items'][0]['data']) > 600


def test_local_sprite_lists_local_data_first():
    from minibt.desk.app import Desk
    desk = Desk(offline=True, browser=True)
    patches = []
    desk.sender = lambda script: patches.append(script)
    desk._booted = True
    desk.handle('desk_~_' + json.dumps(
        {'cmd': 'sprite_search',
         'payload': {'text': '', 'limit': 5, 'local': True}}))
    text = patches[-1]
    first = text.index('l2609_60')
    assert first < text.index('KDJ')


# ---------------------------------------------------- 回放视窗 / 指标裁剪
def test_replay_indicators_are_clipped_on_both_sides():
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = _read(JSLIB / name)
        block = page.split('private _applyReplayIndicators()', 1)[1].split(
            'exitReplay', 1)[0]
        assert 'Number(time) >= first' in block, name
        assert 'Number(time) <= last' in block, name


def test_replay_viewport_keeps_user_zoom_and_shifts_one_bar():
    """P60：播放中**不改视窗** —— LWC 自己按 rightOffset 跟随 ✓

    首次 / seek 才摆窗口（整段 + 右侧留白），用户拖动 / 缩放也不会被拉回。
    """
    page = _read(JSLIB / 'chart-page.ts')
    block = page.split('private _syncReplayViewport', 1)[1].split(
        'private _applyReplayIndicators', 1)[0]
    assert 'REPLAY_WINDOW' in block and 'REPLAY_PADDING' in block
    assert 'from: range.from + 1' not in block
    assert 'scrollToRealTime' not in block


def test_real_chart_ignores_full_indicator_patch_while_replaying():
    page = _read(JSLIB / 'chart-page.ts')
    block = page.split('setIndicators(payload', 1)[1].split(
        'setCellIndicators', 1)[0]
    assert 'if (this.replaying)' in block
    assert 'this.replayIndicators = payload.items' in block
    assert '_applyReplayIndicators()' in block
