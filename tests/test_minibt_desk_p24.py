"""P24：导出历史 + toast「打开文件/文件夹」按钮 ✓"""
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


# ------------------------------------------------------------ 导出历史
def test_record_export_dedupes_and_limits(tmp_path, monkeypatch):
    from minibt.desk import user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    user_prefs.record_export('/tmp/a.csv', 'a.csv', 3)
    items = user_prefs.record_export('/tmp/a.csv', 'a.csv', 4)
    assert len(items) == 1 and items[0]['rows'] == 4     # 同路径只留最新 ✓
    for index in range(25):
        user_prefs.record_export(f'/tmp/f{index}.csv', f'f{index}.csv', 1)
    items = user_prefs.exports()
    assert len(items) == user_prefs.EXPORT_LIMIT == 20
    assert items[0]['name'] == 'f24.csv'                 # 新的在前 ✓
    assert user_prefs.load()['exports'][0]['name'] == 'f24.csv'


def test_export_csv_pushes_actions_and_history(tmp_path, monkeypatch):
    from minibt.desk import protocol

    desk = _desk(tmp_path, monkeypatch)
    desk.handle(protocol.encode_command({
        'cmd': 'export_csv',
        'payload': {'name': 'q.csv', 'text': 'a,b\n1,2\n3,4\n'},
    }))
    toast = [row for row in desk.sent if '"toast"' in str(row)][-1]
    assert '已导出 2 行' in str(toast)
    assert '"actions"' in str(toast)
    assert '打开文件' in str(toast) and '打开文件夹' in str(toast)
    assert '"detail"' in str(toast)
    history = [row for row in desk.sent if '"type":"exports"' in str(row)]
    assert history and 'q.csv' in str(history[-1])


# ------------------------------------------------------------ 打开文件 / 文件夹
def test_open_export_uses_recent_when_no_path(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, protocol

    desk = _desk(tmp_path, monkeypatch)
    opened = []
    monkeypatch.setattr(appmod, '_open_path',
                        lambda target: (opened.append(target), '')[1])
    desk.handle(protocol.encode_command({
        'cmd': 'export_csv',
        'payload': {'name': 'q.csv', 'text': 'a\n1\n'},
    }))
    desk.handle(protocol.encode_command({
        'cmd': 'open_export', 'payload': {}}))
    assert opened and opened[-1].endswith('q.csv')


def test_open_export_folder_and_missing(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, protocol

    desk = _desk(tmp_path, monkeypatch)
    opened = []
    monkeypatch.setattr(appmod, '_open_path',
                        lambda target: (opened.append(target), '')[1])
    desk.handle(protocol.encode_command({
        'cmd': 'export_csv',
        'payload': {'name': 'q.csv', 'text': 'a\n1\n'},
    }))
    path = opened_path = None
    from minibt.desk import user_prefs
    path = user_prefs.exports()[0]['path']
    desk.handle(protocol.encode_command({
        'cmd': 'open_export', 'payload': {'path': path, 'folder': True}}))
    assert opened[-1] == str(pathlib.Path(path).parent)
    # 不存在的文件 → 提示而不是崩溃 ✓
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'open_export',
        'payload': {'path': str(tmp_path / 'nope.csv')}}))
    assert '文件不存在' in str(desk.sent[-1])
    assert opened_path is None


def test_open_path_reports_error(tmp_path):
    from minibt.desk.app import _open_path

    # 不存在的路径：至少不能抛异常（返回错误字符串或空）
    result = _open_path(str(tmp_path / 'definitely-missing'))
    assert isinstance(result, str)


# ------------------------------------------------------------ 前端接线
def test_toast_action_support():
    app = _read('jslib/src/desk/app.ts')
    assert 'export interface ToastAction' in app
    assert 'desk-toast-action' in app
    assert 'actions?: ToastAction[]' in app
    assert "case 'exports'" in app
    assert 'this.quotePage?.setExports(items)' in app
    assert 'get exports(): ExportItem[]' in app
    css = _read('jslib/src/desk/desk.css')
    assert '.desk-toast-action' in css


def test_quote_page_export_history():
    page = _read('jslib/src/desk/quote-page.ts')
    assert "historyButton.textContent = '导出历史'" in page
    assert 'setExports(items: ExportRow[])' in page
    assert 'showExportHistory(' in page
    assert 'showExportHistory(' in page
    history = _read('jslib/src/desk/export-history.ts')
    assert '📂 打开导出文件夹' in history
    assert 'onOpenExport' in page and 'onExportHistory' in page
    app = _read('jslib/src/desk/app.ts')
    assert "onExportHistory: () => this.send('exports'" in app
    assert "this.send('open_export', {" in app


def test_patch_toast_accepts_actions():
    protocol = _read('minibt/desk/protocol.py')
    assert 'def patch_toast(text: str, level: str = ' in protocol
    assert 'actions=None' in protocol
    assert "patch['actions']" in protocol
    assert "patch['detail']" in protocol
