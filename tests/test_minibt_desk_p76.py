"""P76：离线也能接入服务（登录入口 / 首页常驻 / 行情报价可打开）✓"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(name: str) -> str:
    return (DESK_TS / name).read_text(encoding='utf-8')


def _desk(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.no_service = True
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    return desk


def _patches(desk, kind: str = '') -> list:
    out = []
    for item in desk.sent:
        if not isinstance(item, str):
            continue
        payload = json.loads(item.split('applyPatch(', 1)[1].rstrip(');'))
        if kind and payload.get('type') != kind:
            continue
        out.append(payload)
    return out


def _wait_login(desk, timeout: float = 12.0) -> None:
    """等后台线程的登录结果进发件箱 → 冲出来（最多 ``timeout`` 秒 ✓）"""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        desk.flush_outbox()
        patches = _patches(desk, 'login')
        if patches and patches[-1].get('ok') is not None:
            return
        time.sleep(0.05)


# ------------------------------------------------------------------ 新建菜单
def test_new_menu_has_home_quote_and_logins():
    app = _read('app.ts')
    menu = app.split('private _showNewMenu(', 1)[1].split(
        'private _goHome', 1)[0]
    # P105：首页恢复可用（点它才打开，启动不再自动出现 ✓）
    assert "label: '首页'" in menu
    assert "run: () => this.openHome()" in menu
    assert "label: '行情报价'" in menu
    assert "label: '本地图表（minibt 内置数据 / CSV）'" in menu
    assert '登录期货账户（天勤）' in menu
    assert '连接股票（富途 OpenD）' in menu
    # ★ 行情报价不再因为离线被 disable ✓
    quote_item = menu.split("label: '行情报价'", 1)[1].split('},', 1)[0]
    assert 'disabled' not in quote_item


def test_offline_initial_route_stays_on_local_chart():
    """P79：离线启动**只开本地图表**，首页藏起来（点菜单 / 登录才出现 ✓）"""
    app = _read('app.ts')
    route = app.split('private _routeInitial()', 1)[1].split(
        'private _ensureQuoteTab', 1)[0]
    assert '_dropHome()' in route
    assert 'openLocalChart()' in route
    assert 'openHome(): void' in app


# ------------------------------------------------------------------ 后端命令
def test_login_commands_registered(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    for cmd in ('login_info', 'connect_futures', 'connect_stocks', 'test_futu'):
        assert cmd in desk.commands()


def test_login_info_returns_saved(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    from minibt.desk import user_prefs as up

    up.save_login('futures', {'username': '13800000000', 'password': 'pw',
                              'remember': True})
    desk._on_login_info({'kind': 'futures'})
    patch = _patches(desk, 'login')[-1]
    assert patch['state'] == 'info'
    assert patch['saved']['username'] == '13800000000'
    assert patch['saved']['password'] == 'pw'


def test_connect_futures_requires_credentials(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk._on_connect_futures({'username': '', 'password': ''})
    patch = _patches(desk, 'login')[-1]
    assert patch['state'] == 'error' and patch['ok'] is False
    assert '账号和密码' in patch['text']
    # 实盘缺少券商信息 → 也拦住 ✓
    desk.sent.clear()
    desk._on_connect_futures({'username': 'u', 'password': 'p', 'real': True})
    assert _patches(desk, 'login')[-1]['state'] == 'error'


def test_connect_stocks_reports_gateway_error(tmp_path, monkeypatch):
    """P85：连接改到**主线程**（tick 里 `_run_connect`）→ 这里手动触发 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    desk._on_connect_stocks({'host': '127.0.0.1', 'port': 1})
    assert _patches(desk, 'login')[-1]['state'] == 'pending'
    assert desk._connect_pending and desk._connect_pending[0] == 'stocks'
    desk._run_connect()                       # 主线程连接（会失败 ✓）
    patch = _patches(desk, 'login')[-1]
    assert patch['state'] == 'error' and patch['ok'] is False
    assert 'FutuOpenD' in patch['text']


def test_test_futu_probe_reports_failure(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk._on_test_futu({'host': '127.0.0.1', 'port': 1})
    _wait_login(desk)
    patch = _patches(desk, 'login')[-1]
    assert patch['state'] == 'test' and patch['ok'] is False
    assert '连不上' in patch['text']


def test_after_connect_flips_markets_and_reloads(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)

    class _Feed:
        kind = 'futures'
        api = object()

        def available(self):
            return True

    desk.futures = _Feed()
    desk.feeds.append(desk.futures)
    desk._after_connect('futures', '天勤已连接')
    markets = _patches(desk, 'markets')[-1]['markets']
    assert markets['futures'] is True
    assert markets['offline'] is False and markets['no_service'] is False
    assert desk.no_service is False and desk.offline is False
    assert desk._reload_pending is True        # 报价页换成实时数据 ✓
    assert _patches(desk, 'login')[-1]['state'] == 'ok'


# ------------------------------------------------------------ 离线行情报价
def test_offline_quote_page_uses_cache(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    patches = []
    desk.sender = lambda script: patches.append(script)
    desk.flush()
    assert any('离线 · 本地数据' in item for item in patches)
    assert any('"type":"types"' in item for item in patches)
    assert any('"type":"exchanges"' in item for item in patches)

    # 有本地缓存 → 报价页能显示（不联网、不更新 ✓）
    desk.sender = desk.sent.append          # 收回发送钩子（上面临时接了 lambda ✓）
    # 缓存行要和当前交易所一致（`CFFEX`；别的交易所会被校验丢掉 ✓）
    desk.symbol_cache().put(desk._cache_key(), [
        {'symbol': 'CFFEX.IF2612', 'name': '沪深2612'},
        {'symbol': 'CFFEX.IC2612', 'name': '中证2612'},
    ])
    desk.sent.clear()
    desk.reload_rows()
    rows = [row for patch in _patches(desk, 'rows') for row in patch['rows']]
    assert [row['symbol'] for row in rows] == ['CFFEX.IF2612', 'CFFEX.IC2612']
    assert '本地缓存' in _patches(desk, 'status')[-1]['text']
    assert desk._rows_for_filter()          # 离线也走缓存 ✓


def test_offline_quote_page_without_cache_is_empty(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.sent.clear()
    desk.reload_rows()
    assert _patches(desk, 'rows')[-1]['rows'] == []
    assert '无本地缓存' in _patches(desk, 'status')[-1]['text']
    logs = _patches(desk, 'log')
    assert any('登录期货' in item['text'] for item in logs)


# ------------------------------------------------------------------ 前端 UI
def test_login_dialog_supports_both_markets():
    dialog = _read('login-dialog.ts')
    assert 'export class LoginDialog' in dialog
    assert "kind: LoginKind = 'futures'" in dialog
    assert "'期货登录'" in dialog and "'股票登录'" in dialog
    assert "data-f=\"username\"" in dialog or "this._input('username'" in dialog
    assert "this._input('password'" in dialog
    assert "data-f=\"remember\"" in dialog           # 记住密码 ✓
    assert "data-f=\"real\"" in dialog               # 实盘账户 ✓
    assert "'trade_password'" in dialog
    assert "this._input('host'" in dialog and "this._input('port'" in dialog
    assert "'测试连接'" in dialog                     # 富途网关测试 ✓
    assert 'H宏源期货' in dialog                      # 期货公司（同 miniqt ✓）


def test_home_source_rows_are_clickable():
    home = _read('home-page.ts')
    assert 'onLogin?: (kind: \'futures\' | \'stocks\') => void;' in home
    assert 'data-login="${item.key}"' in home
    assert "loginRow.dataset.login === 'stocks'" in home
    assert "this.options.onLogin(kind)" in home
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    row = css.split('.desk-home-source-row {', 1)[1].split('}', 1)[0]
    assert 'cursor: pointer' in row


def test_app_wires_login_dialog_and_patches():
    app = _read('app.ts')
    assert 'openLogin(kind: LoginKind = \'futures\'' in app
    assert "this.send(target === 'stocks'\n                        ? 'connect_stocks' : 'connect_futures', values);" in app
    assert "case 'markets'" in app
    assert "case 'login'" in app
    assert "this.send('login_info', { kind })" in app


def test_prefs_keep_password_only_when_remembered(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    up.save_login('futures', {'username': 'u', 'password': 'p',
                              'remember': False})
    assert 'password' not in up.login()['futures']
    up.save_login('futures', {'username': 'u', 'password': 'p',
                              'remember': True})
    assert up.login()['futures']['password'] == 'p'
    # 改成不记住 → 旧密码要删掉 ✓
    up.save_login('futures', {'username': 'u', 'password': 'p',
                              'remember': False})
    assert 'password' not in up.login()['futures']
    # 其它偏好不会把登录信息冲掉 ✓
    up.set_setting('app_theme', 'light')
    assert up.login()['futures']['username'] == 'u'
