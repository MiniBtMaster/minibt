"""P23：CSV 多带 decimals 列 + 导出落 `~/.minibt/exports/` ✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------------ 后端落盘
def test_export_csv_writes_to_exports_dir(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, protocol, user_prefs

    exports = tmp_path / 'exports'
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(appmod, 'EXPORTS_DIR', str(exports))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    text = '代码,最新价,小数位\nSHFE.rb2610,3600,0\n'
    desk.handle(protocol.encode_command({
        'cmd': 'export_csv',
        'payload': {'name': 'quotes_2026-10-18.csv', 'text': text},
    }))
    files = list(exports.glob('*.csv'))
    assert len(files) == 1
    assert files[0].name == 'quotes_2026-10-18.csv'
    assert files[0].read_text(encoding='utf-8-sig').splitlines() == [
        '代码,最新价,小数位', 'SHFE.rb2610,3600,0']
    toast = [row for row in desk.sent if '"toast"' in str(row)]
    assert toast and files[0].name in str(toast[-1])
    log = [row for row in desk.sent if '"log"' in str(row)]
    assert log and '已导出 1 行' in str(log[-1])


def test_export_csv_dedupes_names(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, protocol, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(appmod, 'EXPORTS_DIR', str(tmp_path))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    for _ in range(2):
        desk.handle(protocol.encode_command({
            'cmd': 'export_csv',
            'payload': {'name': 'a.csv', 'text': 'x,y\n1,2\n'},
        }))
    assert sorted(f.name for f in tmp_path.glob('a*.csv')) == [
        'a.csv', 'a_2.csv']


def test_export_csv_empty_and_bad_name(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, protocol, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(appmod, 'EXPORTS_DIR', str(tmp_path / 'out'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.handle(protocol.encode_command({
        'cmd': 'export_csv', 'payload': {'name': 'x.csv', 'text': ''}}))
    assert '内容为空' in str(desk.sent[-1])
    # 文件名清洗
    assert appmod._safe_filename('a/b:c*?.csv') == 'b_c__.csv'
    assert appmod._safe_filename('') == 'export.csv'
    assert appmod._safe_filename('noext') == 'noext.csv'


# ------------------------------------------------------------ 前端接线
def test_quote_page_adds_decimals_column():
    page = _read('jslib/src/desk/quote-page.ts')
    assert 'CSV_DECIMALS_COLUMN' in page
    assert "title: '小数位'" in page
    assert 'exportColumns: [...QUOTE_COLUMNS, CSV_DECIMALS_COLUMN]' in page
    assert 'onExportCsv' in page


def test_data_grid_export_hook_and_columns():
    grid = _read('jslib/src/panels/data-grid.ts')
    for key in ('onExport?: (filename: string, text: string)',
                'exportColumns?: DataGridColumn[]',
                '_exportHook && this._exportHook(name, text)',
                'setExportHandler', 'csvDecimals'):
        assert key in grid, key


def test_export_goes_through_backend_in_desk():
    app = _read('jslib/src/desk/app.ts')
    assert "this.send('export_csv', { name: filename, text })" in app
    page = _read('jslib/src/desk/chart-page.ts')
    assert "this.options.onCommand?.('export_csv', {" in page
    dock = _read('jslib/src/desk/account-dock.ts')
    assert 'public onExport' in dock
    assert 'if (this.onExport && this.onExport(name, lines.join' in dock
    # 带千分位的字符串在 CSV 里去掉逗号（Excel 才不会当文本 ✗）
    assert 'text.replace(/,/g, \'\')' in dock
