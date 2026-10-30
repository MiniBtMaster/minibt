"""二级报价分笔 / 点档填价 / 预警线（P75）回归测试。"""
from __future__ import annotations

from pathlib import Path

from minibt.desk.app import Desk

ROOT = Path(__file__).resolve().parents[1]
JSLIB = ROOT / 'jslib' / 'src' / 'desk'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_tick_rows_use_candle_up_down_colors_for_buy_sell():
    panel = _read(JSLIB / 'quote-panel.ts')
    css = _read(JSLIB / 'desk.css')

    assert 'function tickClass' in panel
    assert "text.includes('买')" in panel
    assert "text.includes('卖')" in panel
    assert 'row.className = cls' in panel
    assert '.desk-book-ticks tbody tr.buy td' in css
    assert '.desk-book-ticks tbody tr.sell td' in css
    assert 'color: var(--desk-up)' in css
    assert 'color: var(--desk-down)' in css


def test_level_click_fills_bottom_order_price_input():
    panel = _read(JSLIB / 'quote-panel.ts')

    # 统一交易面板重构后：QuotePanel 通过 onPricePick 把价格交给 host ✓
    assert 'onPricePick: ((price: number) => void) | null' in panel
    click = panel.split("row.addEventListener('click'", 1)[1].split(
        '});', 1)[0]
    assert 'this.onPricePick?.(price)' in click
    assert 'this.onLevelClick?.(side, price)' in click
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = _read(JSLIB / name)
        assert 'this.book.onPricePick' in page


def test_alert_dialog_has_line_checkbox_default_on():
    dialog = _read(ROOT / 'jslib' / 'src' / 'panels' / 'alert-dialog.ts')

    assert 'private lineEnabled = true;' in dialog
    assert 'lineCheck.checked = this.lineEnabled;' in dialog
    assert "document.createTextNode('预警线')" in dialog
    assert 'line: !!this.lineEnabled' in dialog
    assert 'pylc-al-check' in dialog


def test_backend_alert_stores_line_flag():
    desk = Desk(offline=True)
    desk._on_add_alert({
        'symbol': 'SHFE.rb2610', 'price': 3600, 'cross': '上穿',
        'action': '无操作', 'qty': 1, 'message': 'test',
    })
    desk._on_add_alert({
        'symbol': 'SHFE.rb2610', 'price': 3700, 'cross': '下穿',
        'action': '无操作', 'qty': 1, 'line': False,
    })
    assert desk.alerts[0]['line'] is True
    assert desk.alerts[1]['line'] is False
    view = desk._alert_view(desk.alerts[0])
    assert view['line'] is True
    assert desk._alert_view(desk.alerts[1])['line'] is False


def test_chart_and_local_chart_render_alert_lines_with_left_badge():
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = _read(JSLIB / name)
        assert 'private alertLines' in page
        assert 'private _renderAlertLines()' in page
        assert 'private _placeAlertBadges()' in page
        assert 'desk-alert-badge' in page
        assert "item.line === false" in page
        assert "badge.style.left = '8px'" in page
    css = _read(JSLIB / 'desk.css')
    assert '.desk-alert-badge' in css


def test_alert_line_is_removed_with_alert_list():
    page = _read(JSLIB / 'chart-page.ts')
    set_alerts = page.split('setAlerts(items:', 1)[1].split(
        'clearAlerts', 1)[0]
    assert 'this._renderAlertLines()' in set_alerts
    clear = page.split('clearAlerts(): void', 1)[1].split('}', 1)[0]
    assert 'this._renderAlertLines()' in clear
