"""P25：导出历史删除单条 / 清空 + 看盘页也能打开历史 ✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(appmod, 'EXPORTS_DIR', str(tmp_path / 'exports'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    return desk


def _export(desk, name='a.csv', text='x,y\n1,2\n'):
    from minibt.desk import protocol

    desk.handle(protocol.encode_command({
        'cmd': 'export_csv', 'payload': {'name': name, 'text': text}}))


# ------------------------------------------------------------ 后端
def test_remove_export_keeps_file(tmp_path, monkeypatch):
    from minibt.desk import protocol, user_prefs

    desk = _desk(tmp_path, monkeypatch)
    _export(desk)
    path = user_prefs.exports()[0]['path']
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'export_remove', 'payload': {'path': path}}))
    assert user_prefs.exports() == []
    assert pathlib.Path(path).is_file()          # 文件不删 ✓
    history = [row for row in desk.sent if '"type":"exports"' in str(row)]
    assert history and '"items":[]' in str(history[-1]).replace(' ', '')
    assert '已删除记录' in str(desk.sent[-1])


def test_clear_exports_keeps_files(tmp_path, monkeypatch):
    from minibt.desk import protocol, user_prefs

    desk = _desk(tmp_path, monkeypatch)
    _export(desk, 'a.csv')
    _export(desk, 'b.csv')
    paths = [item['path'] for item in user_prefs.exports()]
    assert len(paths) == 2
    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'exports_clear'}))
    assert user_prefs.exports() == []
    assert all(pathlib.Path(path).is_file() for path in paths)
    assert '已清空导出历史' in str(desk.sent[-1])


def test_remove_unknown_path_is_noop(tmp_path, monkeypatch):
    from minibt.desk import protocol, user_prefs

    desk = _desk(tmp_path, monkeypatch)
    _export(desk)
    before = user_prefs.exports()
    desk.handle(protocol.encode_command({
        'cmd': 'export_remove', 'payload': {'path': '/nope/x.csv'}}))
    assert user_prefs.exports() == before


# ------------------------------------------------------------ 前端
def test_menu_item_supports_inline_delete():
    menu = _read('jslib/src/desk/menu.ts')
    assert 'onDelete?: () => void;' in menu
    assert 'desk-menu-remove' in menu
    assert 'event.stopPropagation();' in menu
    css = _read('jslib/src/desk/desk.css')
    assert '.desk-menu-remove' in css


def test_shared_export_history_menu():
    history = _read('jslib/src/desk/export-history.ts')
    for key in ('export function showExportHistory', 'ExportHistoryHooks',
                '📂 打开导出文件夹', '🗑 清空历史', 'onDelete'):
        assert key in history, key


def test_quote_and_chart_pages_both_open_history():
    quote = _read('jslib/src/desk/quote-page.ts')
    assert 'showExportHistory(this.historyButton' in quote
    assert 'openExportHistory()' in quote
    chart = _read('jslib/src/desk/chart-page.ts')
    # P40：看盘窗口**不放**「导出历史」按钮（只属于行情报价页 ✓），
    # 但共用实现（删除 / 清空 / 打开）还留着 ✓
    assert "this._toolButton(\n            '导出历史'" not in chart
    assert 'showExportHistory(' in chart
    assert "'export_remove'" in chart and "'exports_clear'" in chart
    app = _read('jslib/src/desk/app.ts')
    assert 'page.setExports(items)' in app
    assert "this.send('export_remove', { path })" in app
    assert "this.send('exports_clear', {})" in app
