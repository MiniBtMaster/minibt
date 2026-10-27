"""P22：导出 CSV 用合约小数位 + 预警触发弹窗价格格式化 ✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'
PANEL_TS = ROOT / 'jslib' / 'src' / 'panels'


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------------ 预警触发弹窗
def test_alert_popup_formats_price_with_decimals():
    app = _read('jslib/src/desk/app.ts')
    assert 'export function fmtPrice(' in app
    assert 'fmtPrice(patch.price, patch.decimals)' in app
    assert 'fmtPrice(patch.last, patch.decimals)' in app
    # 千分位 + 固定小数位
    assert 'minimumFractionDigits: digits' in app


def test_alert_fired_patch_has_decimals(tmp_path, monkeypatch):
    from minibt.desk import user_prefs
    from minibt.desk.app import Desk

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk._last_rows = {'SHFE.rb2610': {'price_tick': 1.0}}
    assert desk.decimals_of('SHFE.rb2610') == 0
    view = desk._alert_view({'id': 1, 'symbol': 'SHFE.rb2610',
                             'price': 3600, 'last': 3602})
    assert view['decimals'] == 0


# ------------------------------------------------------------ DataGrid 导出
def test_data_grid_export_uses_per_row_decimals():
    grid = _read(PANEL_TS / 'data-grid.ts')
    for key in ('exportCsv(filename?: string): number', 'this._view',
                'this._format(value, target, row).replace(/,/g, \'\')',
                'const name = filename || `grid_${stamp}.csv`',
                '\\ufeff'):
        assert key in grid, key
    # CSV 里不要千分位（Excel 会把 3,600 当文本 ✗）
    assert ".replace(/,/g, '')" in grid


def test_data_grid_toolbar_has_export_button():
    grid = _read(PANEL_TS / 'data-grid.ts')
    assert 'pylc-dg-export' in grid
    assert "exportButton.textContent = '导出'" in grid
    assert 'setExportVisible' in grid
    css = grid  # CSS 与 TS 同文件（ensureStyle）✓
    assert '.pylc-dg-export:hover' in css


# ------------------------------------------------------------ 报价页导出
def test_quote_page_exports_csv():
    page = _read('jslib/src/desk/quote-page.ts')
    assert "exportButton.textContent = '导出'" in page
    assert 'this.grid.exportCsv(' in page
    assert 'onExportEmpty' in page
    app = _read('jslib/src/desk/app.ts')
    assert 'onExportEmpty: () => this.toast(' in app


# ------------------------------------------------------------ 账户表 CSV
def test_account_csv_keeps_contract_decimals():
    dock = _read('jslib/src/desk/account-dock.ts')
    for key in ('const cellText =', 'cell.toFixed(places)',
                'const needs = text.includes(\'"\')'):
        assert key in dock, key
    # 表里的价格本来就是后端按合约位格式化好的字符串 ✓
    accounts = _read('minibt/desk/accounts.py')
    assert 'digits = self.decimals_of(code)' in accounts
    assert '_money(avg, digits)' in accounts
