"""P8 测试：个人指标/策略（持久化）+ CLI 入口（4 种连接情况）。"""

import json
import pathlib
import sys

import numpy as np
import pytest

from minibt.desk import personal as pi
from minibt.desk import protocol

pd = pytest.importorskip('pandas')

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


@pytest.fixture()
def personal_dirs(tmp_path, monkeypatch):
    """临时个人指标/策略目录（配置也写到临时文件 ✓）"""
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'personal.json'))
    ind_dir = tmp_path / 'my_inds'
    ind_dir.mkdir()
    (ind_dir / 'basic.py').write_text(
        "import pandas as pd\n"
        "__desk_indicator__ = {'overlap': True, 'label': '我的均线'}\n"
        "def my_ma(df, length=5):\n"
        "    return df['close'].rolling(length).mean()\n"
        "def my_spread(df, fast=3, slow=10):\n"
        "    c = df['close']\n"
        "    return pd.DataFrame({'fast': c.rolling(fast).mean(),\n"
        "                         'slow': c.rolling(slow).mean()})\n",
        encoding='utf-8')
    strat_dir = tmp_path / 'my_strats'
    strat_dir.mkdir()
    (strat_dir / 'demo.py').write_text(
        "from minibt import Strategy\n"
        "class MyStrategy(Strategy):\n"
        "    def next(self): pass\n", encoding='utf-8')
    return ind_dir, strat_dir


def _frame(rows: int = 60):
    rng = np.random.default_rng(1)
    close = 100 + np.cumsum(rng.normal(0, 1, rows))
    return pd.DataFrame({
        'datetime': [(1_700_000_000 + index * 60) * 1_000_000_000
                     for index in range(rows)],
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': 1.0,
    })


# ------------------------------------------------------------------ 持久化
def test_add_and_persist_directories(personal_dirs, tmp_path):
    ind_dir, strat_dir = personal_dirs
    result = pi.add_directory(str(ind_dir), 'indicator')
    assert result['ok'] and result['category'] == 'my_inds'
    pi.add_directory(str(strat_dir), 'strategy')

    config = json.loads(pathlib.Path(pi.CONFIG_FILE).read_text(encoding='utf-8'))
    assert [item['category'] for item in config['directories']] == [
        'my_inds', 'my_strats']
    assert [item['kind'] for item in config['directories']] == [
        'indicator', 'strategy']

    # 重复添加 → 更新 kind，不新增 ✓
    again = pi.add_directory(str(ind_dir), 'indicator')
    assert again['updated'] is True
    assert len(pi.load_config()['directories']) == 2

    # 路径不存在的会被过滤 ✓
    pi.add_directory(str(tmp_path / 'nope'), 'indicator') if False else None
    config = pi.load_config()
    config['directories'].append({'path': str(tmp_path / 'gone'),
                                  'category': 'gone', 'kind': 'indicator'})
    pi.save_config(config)
    assert [item['category'] for item in pi.directories()] == [
        'my_inds', 'my_strats']


def test_bad_directory_rejected(personal_dirs, tmp_path):
    result = pi.add_directory(str(tmp_path / 'nope'), 'indicator')
    assert result['ok'] is False and '不存在' in result['error']


def test_remove_directory(personal_dirs):
    ind_dir, _strat = personal_dirs
    pi.add_directory(str(ind_dir), 'indicator')
    assert pi.remove_directory('my_inds') is True
    assert pi.directories() == []
    assert pi.remove_directory('my_inds') is False


# ------------------------------------------------------------ 扫描 / 计算
def test_scan_indicators_and_strategies(personal_dirs):
    ind_dir, strat_dir = personal_dirs
    pi.add_directory(str(ind_dir), 'indicator')
    pi.add_directory(str(strat_dir), 'strategy')

    indicators = pi.scan('indicator')
    keys = {item['key'] for item in indicators}
    assert keys == {'pi:my_inds/my_ma', 'pi:my_inds/my_spread'}
    my_ma = next(item for item in indicators if item['name'] == 'my_ma')
    assert my_ma['overlap'] is True
    assert [param['name'] for param in my_ma['params']] == ['length']
    assert my_ma['group'] == '个人指标 · my_inds'

    strategies = pi.scan('strategy')
    assert [item['key'] for item in strategies] == ['pi:my_strats/MyStrategy']
    assert strategies[0]['strategy'] is True


def test_compute_personal_indicator_single_and_multi_line(personal_dirs):
    ind_dir, _strat = personal_dirs
    pi.add_directory(str(ind_dir), 'indicator')
    frame = _frame()

    single = pi.compute(frame, 'pi:my_inds/my_ma', {'length': 10})
    assert len(single) == 1 and single[0]['overlay'] is True
    # 完整长度 + 预热期 None（前端按时间戳对齐 ✓）
    assert len(single[0]['data']) == len(frame)
    assert single[0]['data'][0][1] is None

    multi = pi.compute(frame, 'pi:my_inds/my_spread')
    assert {item['key'] for item in multi} == {
        'pi:my_inds/my_spread:fast', 'pi:my_inds/my_spread:slow'}

    assert pi.compute(frame, 'pi:my_inds/nope') == []
    assert pi.compute(None, 'pi:my_inds/my_ma') == []


def test_broken_script_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'p.json'))
    folder = tmp_path / 'bad'
    folder.mkdir()
    (folder / 'broken.py').write_text('raise RuntimeError("boom")',
                                      encoding='utf-8')
    (folder / 'good.py').write_text(
        "def ok(df, n=2):\n    return df['close']\n", encoding='utf-8')
    pi.add_directory(str(folder), 'indicator')
    keys = {item['key'] for item in pi.scan('indicator')}
    assert keys == {'pi:bad/ok'}                 # 坏文件被跳过 ✓


# ---------------------------------------------------------------- Desk 集成
def test_menu_contains_personal_group(personal_dirs, tmp_path):
    ind_dir, strat_dir = personal_dirs
    pi.add_directory(str(ind_dir), 'indicator')
    pi.add_directory(str(strat_dir), 'strategy')
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.handle(protocol.encode_command(
        {'cmd': 'indicator_menu', 'payload': {'symbol': 'SHFE.rb2610'}}))
    patch = json.loads(desk.sent[-1][len('window.__desk.applyPatch('):-2])
    groups = {item['group'] for item in patch['items']}
    assert '个人指标 · my_inds' in groups
    assert '个人策略 · my_strats' in groups


def test_add_personal_indicator_computes(personal_dirs, tmp_path):
    ind_dir, _strat = personal_dirs
    pi.add_directory(str(ind_dir), 'indicator')
    from minibt.desk.app import Desk

    class _Feed:
        kind = 'futures'

        def available(self):
            return True

        def contracts(self, ins_class, exchange):
            return ['SHFE.rb2610']

        def fill_names(self, symbols):
            return None

        def name_of(self, symbol):
            return '螺纹'

        def quotes(self, keys):
            return []

        def spec(self, symbol):
            return None

        def klines(self, symbol, cycle, length=500):
            return _frame()

    desk = Desk(offline=True, allow_trading=False)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = _Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    desk.tabs['SHFE.rb2610'] = {'feed': desk.futures, 'cycle': 60}

    desk.handle(protocol.encode_command({
        'cmd': 'add_indicator',
        'payload': {'symbol': 'SHFE.rb2610', 'key': 'pi:my_inds/my_ma',
                    'params': {'length': 10}},
    }))
    payload = desk.indicator_payload('SHFE.rb2610')
    assert payload['items'], '个人指标没有算出来'
    assert payload['items'][0]['key'] == 'pi:my_inds/my_ma:my_ma'


def test_strategy_cannot_be_drawn(personal_dirs):
    _ind, strat_dir = personal_dirs
    pi.add_directory(str(strat_dir), 'strategy')
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.tabs['SHFE.rb2610'] = {}
    desk.handle(protocol.encode_command({
        'cmd': 'add_indicator',
        'payload': {'symbol': 'SHFE.rb2610', 'key': 'pi:my_strats/MyStrategy'},
    }))
    kinds = [json.loads(script[len('window.__desk.applyPatch('):-2])['type']
             for script in desk.sent]
    assert 'toast' in kinds
    assert desk.tabs['SHFE.rb2610'].get('indicators') in (None, [])


def test_personal_menu_and_drop(personal_dirs):
    ind_dir, _strat = personal_dirs
    pi.add_directory(str(ind_dir), 'indicator')
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.handle(protocol.encode_command({'cmd': 'personal_menu'}))
    patch = json.loads(desk.sent[-1][len('window.__desk.applyPatch('):-2])
    assert patch['type'] == 'personal_menu'
    assert patch['items'][0]['category'] == 'my_inds'

    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'drop_personal', 'payload': {'category': 'my_inds'}}))
    # 默认的两个系统目录（personal/indicators、personal/strategies）还在 ✓
    left = [item['category'] for item in pi.directories()]
    assert 'my_inds' not in left
    assert all(item['path'].endswith(('indicators', 'strategies'))
               for item in pi.directories())
    kinds = [json.loads(script[len('window.__desk.applyPatch('):-2])['type']
             for script in desk.sent]
    assert 'log' in kinds and 'toast' in kinds


def test_pick_personal_uses_system_dialog(tmp_path):
    """P78：选目录走**系统对话框**（不再让前端弹输入框 ✓）"""
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    called = []
    desk.pick_directory = lambda title='': (called.append(title), '')[1]
    desk.handle(protocol.encode_command(
        {'cmd': 'pick_personal', 'payload': {'kind': 'indicator'}}))
    assert called and '指标' in called[0]        # 弹了系统框 ✓
    patch = json.loads(desk.sent[-1][len('window.__desk.applyPatch('):-2])
    assert patch['type'] == 'log'                # 取消 → 只记日志 ✓
    assert '取消' in patch['text']


# -------------------------------------------------------------------- CLI
def _args(**kwargs):
    from minibt.cli import build_parser
    argv = ['desk']
    for key, value in kwargs.items():
        flag = '--' + key.replace('_', '-')
        if value is True:
            argv.append(flag)
        elif value not in (None, ''):
            argv.extend([flag, str(value)])
    return build_parser().parse_args(argv)


def test_cli_four_connection_cases(monkeypatch):
    from minibt import cli
    from minibt.desk.app import Desk

    calls = {'futures': 0, 'stocks': 0, 'run': 0}

    def fake_futures(self, *args, **kwargs):
        calls['futures'] += 1
        if calls['futures'] < 0:
            raise RuntimeError('no tq')
        return self

    def fake_stocks(self, *args, **kwargs):
        calls['stocks'] += 1
        return self

    monkeypatch.setattr(Desk, 'add_futures', fake_futures)
    monkeypatch.setattr(Desk, 'add_stocks', fake_stocks)
    monkeypatch.setattr(Desk, 'run', lambda self, **kwargs: calls.__setitem__(
        'run', calls['run'] + 1))

    # ① 都连上
    desk, futures_ok, stocks_ok = cli.build_desk(_args(user='u', password='p'),
                                                 log=lambda *_: None)
    assert futures_ok and stocks_ok
    # ② 只有期货
    desk, futures_ok, stocks_ok = cli.build_desk(
        _args(user='u', password='p', no_stocks=True), log=lambda *_: None)
    assert futures_ok and not stocks_ok
    # ③ 只有股票（不给账号）
    desk, futures_ok, stocks_ok = cli.build_desk(_args(), log=lambda *_: None)
    assert not futures_ok and stocks_ok
    # ④ 都没连上 → 不退出，进入离线模式（前端自动打开本地图表 ✓）
    monkeypatch.setattr(Desk, 'add_stocks',
                        lambda self, *a, **kw: (_ for _ in ()).throw(
                            RuntimeError('no opend')))
    assert cli.main(['desk']) == 0
    assert calls['run'] == 1


def test_cli_offline_starts():
    from minibt import cli
    from minibt.desk.app import Desk

    started = []
    original = Desk.run

    def fake_run(self, **kwargs):
        started.append(True)

    Desk.run = fake_run
    try:
        assert cli.main(['desk', '--offline']) == 0
        assert started == [True]
    finally:
        Desk.run = original


def test_cli_help_and_scripts_entry():
    from minibt.cli import main
    assert main([]) == 0                          # 无子命令 → 打帮助 ✓
    pyproject = (REPO / 'minibt' / 'pyproject.toml').read_text(encoding='utf-8')
    assert '[project.scripts]' in pyproject
    assert 'minibt = "minibt.cli:main"' in pyproject


def test_p8_assets_built():
    script = (REPO / 'pylightcharts' / 'js' / 'desk.js').read_text(
        encoding='utf-8', errors='ignore')
    for key in ('pick_personal', 'personal_menu', 'drop_personal'):
        assert key in script, key
    menu = (REPO / 'jslib' / 'src' / 'desk' / 'indicator-menu.ts').read_text(
        encoding='utf-8')
    assert 'onImport' in menu and 'showPersonalManager' in menu
    assert (REPO / 'minibt' / 'desk' / 'personal.py').is_file()
    assert (REPO / 'minibt' / 'cli.py').is_file()


# ------------------------------------------------ 多图布局 / 工具箱 / 预警
class _QuoteFeed:
    kind = 'futures'

    def __init__(self, last: float = 3600.0):
        self.last = last

    def available(self):
        return True

    def contracts(self, ins_class, exchange):
        return ['SHFE.rb2610']

    def fill_names(self, symbols):
        return None

    def name_of(self, symbol):
        return '螺纹'

    def quotes(self, keys):
        return []

    def spec(self, symbol):
        return type('Q', (), {'last_price': self.last})()

    def klines(self, *args, **kwargs):
        return _frame()


def _alert_desk(tmp_path):
    from minibt.desk.app import Desk

    desk = Desk(offline=True, allow_trading=False)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = _QuoteFeed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    desk.tabs['SHFE.rb2610'] = {'feed': desk.futures, 'cycle': 60}
    return desk


def test_add_check_and_drop_alert(tmp_path):
    desk = _alert_desk(tmp_path)
    desk.handle(protocol.encode_command({
        'cmd': 'add_alert',
        'payload': {'symbol': 'SHFE.rb2610', 'price': 3600.0,
                    'action': 'buy', 'qty': 2}}))
    assert len(desk.alerts) == 1 and desk.alerts[0]['fired'] is False

    desk.sent.clear()
    desk.check_alerts()
    kinds = [json.loads(script[len('window.__desk.applyPatch('):-2])['type']
             for script in desk.sent]
    assert 'alert_fired' in kinds
    fired = next(json.loads(script[len('window.__desk.applyPatch('):-2])
                 for script in desk.sent
                 if '"alert_fired"' in script)
    assert fired['price'] == 3600.0 and fired['last'] == 3600.0
    assert fired['action'] == 'buy' and fired['qty'] == 2

    # 第二次不再触发 ✓
    desk.sent.clear()
    desk.check_alerts()
    kinds = [json.loads(script[len('window.__desk.applyPatch('):-2])['type']
             for script in desk.sent]
    assert 'alert_fired' not in kinds

    desk.handle(protocol.encode_command(
        {'cmd': 'drop_alert', 'payload': {'id': desk.alerts[0]['id']}}))
    assert desk.alerts == []


def test_alert_not_triggered_when_far(tmp_path):
    desk = _alert_desk(tmp_path)
    desk.futures.last = 3500.0
    desk.handle(protocol.encode_command({
        'cmd': 'add_alert',
        'payload': {'symbol': 'SHFE.rb2610', 'price': 3600.0}}))
    desk.sent.clear()
    desk.check_alerts()
    kinds = [json.loads(script[len('window.__desk.applyPatch('):-2])['type']
             for script in desk.sent]
    assert 'alert_fired' not in kinds


def test_bad_alert_price_rejected(tmp_path):
    desk = _alert_desk(tmp_path)
    desk.handle(protocol.encode_command({
        'cmd': 'add_alert', 'payload': {'symbol': 'SHFE.rb2610',
                                        'price': 'abc'}}))
    assert desk.alerts == []


def test_layout_and_toolbox_sources():
    chart = (REPO / 'jslib' / 'src' / 'desk' / 'chart-page.ts').read_text(
        encoding='utf-8')
    for key in ('setLayout', '_buildCells', 'toggleToolBox', 'createToolBox',
                '左右两图', '四图'):
        assert key in chart, key
    css = (REPO / 'pylightcharts' / 'js' / 'desk.css').read_text(encoding='utf-8')
    assert 'desk-chart-grid' in css and 'desk-chart-cell' in css
    script = (REPO / 'pylightcharts' / 'js' / 'desk.js').read_text(
        encoding='utf-8', errors='ignore')
    for key in ('add_alert', 'alert_fired', 'desk-chart-grid'):
        assert key in script, key


# ------------------- 修复：pylightcharts 0.1.5 没有 QtPanel(url=) → 自动降级
class _FakeWeb:
    def __init__(self):
        self.loaded = []
        #:　DeskWindow 会 connect(loadFinished)（真实 QWebEngineView 自带 ✓）
        self.loadFinished = type('Sig', (), {'connect': staticmethod(
            lambda *_a, **_kw: None)})()

    def load(self, url):
        self.loaded.append(url)


class _OldPanel:
    """模拟 pylightcharts 0.1.5：``QtPanel(widget=None)``"""

    def __init__(self, widget=None):
        self.webview = _FakeWeb()
        self.win = object()


class _NewPanel:
    def __init__(self, widget=None, url=None):
        self.webview = _FakeWeb()
        self.win = object()
        self.url = url


def test_make_panel_falls_back_on_old_qtpanel(tmp_path):
    from minibt.desk.app_window import make_panel

    html = tmp_path / 'desk.html'
    html.write_text('<html></html>', encoding='utf-8')

    # 老版本：不传 url → 建完再 load ✓
    panel = make_panel(_OldPanel, None, str(html))
    assert isinstance(panel, _OldPanel)
    assert len(panel.webview.loaded) == 1

    # 新版本：直接传 url，不额外 load ✓
    panel = make_panel(_NewPanel, None, str(html))
    assert panel.url == str(html) and panel.webview.loaded == []


def test_resolve_desk_html_prefers_existing(tmp_path):
    from minibt.desk.app import resolve_desk_html

    missing = tmp_path / 'missing.html'
    exists = tmp_path / 'desk.html'
    exists.write_text('<html></html>', encoding='utf-8')
    assert resolve_desk_html([str(missing), str(exists)]) == str(exists)
    # 都不存在 → 返回第一个（方便报错信息指出预期路径 ✓）
    assert resolve_desk_html([str(missing), '/nope']) == str(missing)


def test_desk_html_actually_exists():
    from minibt.desk.app import DESK_HTML

    assert DESK_HTML.endswith('desk.html')
    assert pathlib.Path(DESK_HTML).is_file(), \
        '缺少 desk.html（先在 jslib 执行 npm run build）'


def test_desk_window_works_with_old_qtpanel(monkeypatch):
    """端到端：模拟 0.1.5 的 QtPanel（无 url 参数）→ DeskWindow 仍能建起来 ✓"""
    import pylightcharts.widgets as widgets
    from minibt.desk.app import Desk
    from minibt.desk.app_window import DeskWindow

    class _StubPanel:
        def __init__(self, widget=None):          # 0.1.5 的签名
            self.webview = _FakeWeb()
            self.win = type('W', (), {'handlers': {}, 'run_script': lambda *a: None,
                                      'loaded': False})()

    monkeypatch.setattr(widgets, 'QtPanel', _StubPanel)
    desk = Desk(offline=True)
    window = DeskWindow(desk)
    assert isinstance(window.panel, _StubPanel)
    assert len(window.webview.loaded) == 1        # 手动加载了 desk.html ✓
    assert 'desk' in window.win.handlers          # 命令回调已注册 ✓
    assert callable(desk.sender)                  # 补丁通道已接上 ✓


# ------------- 修复：QApplication 的 argv 不能为空 + 退出时关连接
def test_qt_argv_is_never_empty(monkeypatch):
    from minibt.desk.app import qt_argv

    monkeypatch.setattr(sys, 'argv', [])
    assert qt_argv() == ['minibt-desk']            # 空 → 补程序名 ✓
    monkeypatch.setattr(sys, 'argv', ['minibt.exe', 'desk'])
    assert qt_argv() == ['minibt.exe', 'desk']
    assert qt_argv(['a', None, 'b']) == ['a', 'b']


def test_run_qt_uses_non_empty_argv():
    source = (REPO / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'QApplication(qt_argv())' in source     # 不再用空 argv ✓
    # 只允许出现在注释里（解释为什么必须非空），代码里不能再调用 ✓
    assert 'QApplication([])' not in source.split('def _run_qt')[1]
    assert 'application.exec()' in source and 'self.close()' in source


def test_desk_close_closes_apis():
    from minibt.desk.app import Desk

    class _Api:
        def __init__(self):
            self.closed = 0

        def close(self):
            self.closed += 1

    class _Feed:
        kind = 'futures'

        def __init__(self):
            self.api = _Api()

        def available(self):
            return True

    desk = Desk(offline=True)
    first, second = _Feed(), _Feed()
    desk.feeds = [first, second]
    desk.close()
    assert first.api.closed == 1 and second.api.closed == 1
    desk.close()                                  # 关两次也不能炸、且幂等 ✓
    assert first.api.closed == 1 and second.api.closed == 1
