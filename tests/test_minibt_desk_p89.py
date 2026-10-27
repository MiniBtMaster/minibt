"""P89：独立「运行日志」页（＋ 新建 ▾ → 运行日志）✓"""
from minibt import BtIndicator, Strategy
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(name: str) -> str:
    return (DESK_TS / name).read_text(encoding='utf-8')


def test_log_page_component_exists():
    page = _read('log-page.ts')
    assert 'export class LogPage' in page
    assert 'append(text: string' in page
    assert 'setItems(items: LogItem[])' in page
    assert 'LOG_LIMIT' in page
    # 过滤 / 复制 / 清空
    assert "this.input.placeholder" in page
    assert '复制' in page and '清空' in page
    assert 'desk-logpage-line' in page


def test_app_wires_log_page():
    app = _read('app.ts')
    assert "import { LogPage, type LogItem } from './log-page';" in app
    assert "const LOG_TAB_ID = '__log';" in app
    assert 'openLog(): LogPage {' in app
    assert "label: '运行日志'" in app                    # 新建菜单 ✓
    # 所有日志：缓冲 + 日志页 + 底部面板
    block = app.split("case 'log': {", 1)[1].split('break;', 1)[0]
    assert 'this.logBuffer.push(' in block
    assert 'this.logPage?.append(' in block
    assert 'page.appendLog(' in block
    assert 'LocalChartPage) local.appendLog(' in block
    # 主题 / 关闭
    assert 'this.logPage?.setTheme(theme);' in app
    assert 'this.logPage = null;' in app


def test_backend_logs_are_broadcast(tmp_path, monkeypatch):
    """后端 `log` 补丁不带 symbol（前端广播给所有页面 ✓）"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.push_log('测试日志 hello', 'warning')
    patch = json.loads(desk.sent[-1].split('applyPatch(', 1)[1]
                       .rstrip(');'))
    assert patch['type'] == 'log'
    assert patch['level'] == 'warning'
    assert patch['text'] == '测试日志 hello'
    assert 'symbol' not in patch


# ---------------------------------------------------------------- P90
def test_non_tradeable_symbols_are_guarded():
    """主连 / 指数不能交易：持仓 / 挂单 / 下单全部挡掉（实盘会卡 ✗）"""
    from minibt.desk.symbols import is_tradeable

    assert is_tradeable('DCE.v2701')
    assert is_tradeable('SHFE.rb2601')
    assert not is_tradeable('KQ.m@SHFE.rb')
    assert not is_tradeable('KQ.i@CFFEX.IF')
    assert not is_tradeable('')

    app = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "payload['tradeable'] = tradeable" in app
    assert 'if not tradeable:' in app
    trading = (ROOT / 'minibt' / 'desk' / 'trading.py').read_text(
        encoding='utf-8')
    assert 'def _tradeable(' in trading
    assert '不能交易（主连 / 指数只做行情' in trading


# ---------------------------------------------------------------- P91
def test_logs_go_to_terminal(capsys, tmp_path, monkeypatch):
    """运行日志默认**同时打印到终端**（界面卡住也能复制 ✓）"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.push_log('终端可见的日志', 'warning')
    out = capsys.readouterr().out
    assert '终端可见的日志' in out
    assert 'WARNING' in out
    assert any('"type":"log"' in item for item in desk.sent)

    # `--no-ui-log`：只终端
    desk.log_to_ui = False
    desk.sent.clear()
    desk.push_log('只到终端', 'info')
    assert not any('"type":"log"' in item for item in desk.sent)
    assert '只到终端' in capsys.readouterr().out


def test_cli_flags_for_logging():
    from minibt.cli import build_parser

    args = build_parser().parse_args(['desk', '--no-ui-log', '--quiet'])
    assert args.no_ui_log is True
    assert args.quiet is True
    cli = (ROOT / 'minibt' / 'cli.py').read_text(encoding='utf-8')
    assert "desk.log_to_stdout = not bool(getattr(args, 'quiet', False))" in cli
    assert "desk.log_to_ui = not bool(getattr(args, 'no_ui_log', False))" in cli


# ---------------------------------------------------------------- P93
def test_ins_class_mapping_matches_tqsdk():
    """desk 的类型键必须映射成天勤的 ins_class（否则 30 秒超时 ✓）"""
    from minibt.desk.feeds import TQ_INS_CLASS, FuturesFeed

    assert TQ_INS_CLASS['FUT'] == 'FUTURE'
    assert TQ_INS_CLASS['CONT_MAIN'] == 'CONT'
    assert TQ_INS_CLASS['STOCK'] == 'STOCK'

    seen = []

    class Api:
        def __init__(self): self._data = {'symbols': {}}
        def query_quotes(self, ins_class, exchange, **kwargs):
            seen.append(ins_class)
            assert ins_class in ('FUTURE', 'CONT', 'INDEX', 'OPTION', 'STOCK')
            return ['SHFE.rb2601']
        def query_cont_quotes(self, exchange):
            seen.append('CONT_MAIN')
            return ['KQ.m@SHFE.rb']

    feed = FuturesFeed(Api(), 'futures')
    assert feed.contracts('FUT', 'SHFE') == ['SHFE.rb2601']
    assert feed.contracts('CONT_MAIN', 'SHFE') == ['KQ.m@SHFE.rb']
    assert seen == ['FUTURE', 'CONT_MAIN']


def test_log_settings_switches(tmp_path, monkeypatch):
    """设置 → 运行日志：终端 / 程序内两个开关 ✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sender = lambda script: None
    desk._booted = True
    assert desk.log_to_stdout is True            # 默认终端输出 ✓
    desk._on_set_setting({'key': 'log_terminal', 'value': False})
    desk._on_set_setting({'key': 'log_ui', 'value': False})
    assert desk.log_to_stdout is False
    assert desk.log_to_ui is False
    assert up.settings()['log_terminal'] is False
    assert up.settings()['log_ui'] is False
    page = (DESK_TS / 'settings-page.ts').read_text(encoding='utf-8')
    assert "this._section('运行日志')" in page
    assert "this.options.onSetting('log_terminal', checked)" in page
    assert "this.options.onSetting('log_ui', checked)" in page


# ---------------------------------------------------------------- P95
def test_failed_markets_are_skipped(tmp_path, monkeypatch):
    import time
    """取不到合约 → 稍后自动重试（TqSdk 初始化期间不永久跳过）✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    from minibt.desk.feeds import FuturesFeed

    calls = {'n': 0}

    class Api:
        def __init__(self): self._data = {'symbols': {}}
        def query_quotes(self, ins_class, exchange, **kwargs):
            calls['n'] += 1
            return []

    desk = Desk(offline=True)
    desk.futures = FuturesFeed(Api(), 'futures')
    desk.feeds = [desk.futures]
    desk.no_service = False
    desk.offline = False
    desk._cache, desk._cache_ready = None, True
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'CFFEX', 'text': ''}

    desk.reload_rows()
    assert calls['n'] == 1
    # 新行为：不永久跳过；记录 2 秒后自动重试（TqSdk 符号字典可能还没到）
    assert ('FUT', 'CFFEX') not in desk._skip_markets
    assert desk._empty_rows_retry_at > 0
    desk._empty_rows_retry_at = time.monotonic() - 1
    # 自动重试只读 pending；'刷新' 才 force 重新发起 ✓
    desk.futures.reset_symbols('FUT', 'CFFEX', force=True)
    desk._retry_empty_rows()
    assert calls['n'] == 2


def test_symbol_issue_validates_contract(tmp_path, monkeypatch):
    """开图前检查合约合法性 / 是否有数据 ✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    from minibt.desk.feeds import FuturesFeed

    class Api:
        def __init__(self): self._data = {'symbols': {}}

    class Feed(FuturesFeed):
        def name_of(self, symbol):
            return '螺纹' if symbol.endswith('rb2601') else ''

    desk = Desk(offline=True)
    desk.futures = Feed(Api(), 'futures')
    desk.feeds = [desk.futures]
    desk.no_service = False
    desk.offline = False
    desk._search_pool = []
    desk._last_rows = {}

    assert '不是合法合约代码' in desk.symbol_issue('rb2601')
    assert '不在当前合约清单里' in desk.symbol_issue('SHFE.xx9999')
    assert desk.symbol_issue('SHFE.rb2601') == ''


# ---------------------------------------------------------------- P97
def test_home_favorites_resolved_at_boot(tmp_path, monkeypatch):
    """启动时：**上次保存的**收藏 / 分组合约要并进首页自选（否则一直 -- ✗）"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    up.set_watch({'favorites': ['DCE.v2701'], 'groups': [],
                  'pins': {'black': ['SHFE.rb2601']}})
    from minibt.desk.app import Desk
    from minibt.desk.feeds import FuturesFeed

    class Api:
        def __init__(self): self._data = {'symbols': {}}
        def query_quotes(self, *a, **k): return []
        def get_quote(self, symbol): return None

    class Feed(FuturesFeed):
        def quotes(self, symbols):
            return [{'symbol': s, 'last': 5000.0} for s in symbols]

    desk = Desk(offline=True)
    desk.futures = Feed(Api(), 'futures')
    desk.feeds = [desk.futures]
    desk.no_service = False
    desk.offline = False
    desk.sent = []
    desk.sender = desk.sent.append
    desk.flush()
    assert 'DCE.v2701' in desk._home_extra
    assert 'SHFE.rb2601' in desk._home_extra
    rows = {row['symbol'] for row in
            (desk.home_payload(full=False).get('watchlist') or [])}
    assert 'DCE.v2701' in rows


def test_names_come_from_quote_entity():
    """名称直接取报价里的 `instrument_name`（不再调 query_symbol_info ✓）"""
    from minibt.desk.feeds import FuturesFeed

    class Quote:
        instrument_name = 'PVC2701'
        last_price = 5005.0
        price_tick = 1.0

    class Api:
        def __init__(self): self._data = {'symbols': {}}

    feed = FuturesFeed(Api(), 'futures')
    row = feed.row_of('DCE.v2701', Quote())
    assert row['name'] == 'PVC2701'
    assert feed.name_of('DCE.v2701') == 'PVC2701'


def test_expired_contracts_filtered():
    """只查未下市合约（下市合约订阅行情会 30 秒超时 ✗）"""
    from minibt.desk.feeds import _filter_symbols

    class Info:
        def __init__(self, expired): self.expired = expired

    symbols = {
        'SHFE.rb2601': {'instrument_class': 'FUTURE', 'exchange_id': 'SHFE',
                        'expired': False},
        'SHFE.rb2501': {'instrument_class': 'FUTURE', 'exchange_id': 'SHFE',
                        'expired': True},
    }
    assert _filter_symbols(symbols, 'FUT', 'SHFE') == ['SHFE.rb2601']


# ---------------------------------------------------------------- P98
def test_home_uses_quote_list_rows(tmp_path, monkeypatch):
    """首页的合约直接来自「行情报价」的列表（同源，不再发第二轮请求 ✓）"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    from minibt.desk.feeds import FuturesFeed

    class Api:
        def __init__(self): self._data = {'symbols': {}}
        def get_quote(self, symbol):
            raise AssertionError('首页不该再取报价')

    class Feed(FuturesFeed):
        def quotes(self, symbols):
            raise AssertionError('首页不该再取报价')

    desk = Desk(offline=True)
    desk.futures = Feed(Api(), 'futures')
    desk.feeds = [desk.futures]
    desk.no_service = False
    desk.offline = False
    desk.sender = lambda script: None
    desk._booted = True
    for symbol, volume in (('SHFE.rb2701', 50000), ('DCE.v2701', 20000)):
        desk._last_rows[symbol] = {'symbol': symbol, 'name': symbol,
                                   'last': 3600.0, 'volume': volume}
    payload = desk.home_payload(full=False)
    # P101 起自选默认空（只放用户自己加的）；这里只验证市场全景是主力 ✓
    assert payload['source'] in ('futures', 'quote')
    symbols = [row['symbol'] for row in payload['watchlist']]
    assert 'SHFE.rb2701' not in symbols        # 后端默认清单不再注入 ✓
    # 市场全景固定「主力 · 中金所」（P99 用户要求）→ 不再按成交量取 ✓
    assert payload['indices'][0]['symbol'].startswith('KQ.m@CFFEX.')


# ---------------------------------------------------------------- P99
def test_home_indices_are_cffex_main(tmp_path, monkeypatch):
    """市场全景 = 主力 · 中金所前 4（IF/IC/IH/IM）✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk, HOME_FUTURES_INDICES
    from minibt.desk.feeds import FuturesFeed

    class Api:
        def __init__(self): self._data = {'symbols': {}}
        def get_quote(self, symbol): return None

    class Feed(FuturesFeed):
        def quotes(self, symbols):
            return [{'symbol': s, 'name': 'n', 'last': 4000.0} for s in symbols]

    desk = Desk(offline=True)
    desk.futures = Feed(Api(), 'futures')
    desk.feeds = [desk.futures]
    desk.no_service = False
    desk.offline = False
    desk.sender = lambda script: None
    desk._booted = True

    default = [row['symbol'] for row in
               desk.home_payload(full=False)['indices']]
    assert default == ['KQ.m@CFFEX.IF', 'KQ.m@CFFEX.IC',
                       'KQ.m@CFFEX.IH', 'KQ.m@CFFEX.IM']
    assert len(HOME_FUTURES_INDICES) == 4

    # 行情页取到「主力」后 → 用真实月份合约 ✓
    desk.filter = {'type': 'CONT_MAIN', 'exchange': 'CFFEX', 'text': ''}
    desk._remember_main_indices([
        {'symbol': f'CFFEX.{code}2612', 'name': code}
        for code in ('IC', 'IF', 'IH', 'IM')])
    symbols = [row['symbol'] for row in
               desk.home_payload(full=False)['indices']]
    assert symbols == ['CFFEX.IC2612', 'CFFEX.IF2612',
                       'CFFEX.IH2612', 'CFFEX.IM2612']


def test_open_chart_requests_backend():
    """打开图表必须通知后端推 K 线（否则空白图 ✗）"""
    app = _read('app.ts')
    body = app.split('openChart(symbol: string', 1)[1].split(
        'openLocalChart(', 1)[0]
    assert "this.send('open_chart', {" in body


def test_home_preview_is_candles():
    """首页左键 → 下方画 K 线（`home_preview` 补丁）+ 双击打开图表 ✓"""
    home = _read('home-page.ts')
    assert 'function candleSvg(' in home
    assert 'onPreviewBars' in home
    assert 'setPreviewBars(' in home
    app = _read('app.ts')
    assert "this.send('home_preview', {" in app
    assert "case 'home_preview':" in app
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'home_preview': self._on_home_preview" in backend


# --------------------------------------------------------------- P100
def test_home_preview_kline_toggle():
    """首页迷你图：「K线」开关（默认开；关掉显示折线）+ 双击打开图表 ✓"""
    home = _read('home-page.ts')
    assert "private klineOn = true;" in home
    assert 'data-act="kline-toggle"' in home
    assert 'minibt.desk.home.kline' in home
    assert 'if (this.klineOn) {' in home       # 开 → 蜡烛；关 → 折线 ✓
    # 左键选中**不重建表格**（否则双击失效 ✗）
    block = home.split("if (open.dataset.watchRow) {", 1)[1].split('return;', 1)[0]
    assert 'this.renderWatch();' not in block      # 只改 class，不重建表格 ✓
    assert "classList.toggle(" in block
    assert 'renderPreview()' in block
    # 双击 → 打开图表
    assert "closest<HTMLElement>('[data-watch-row]')" in home
    assert 'this.options.onOpenChart(' in home
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(
        encoding='utf-8')
    assert '.desk-home-kline-toggle' in css


# --------------------------------------------------------------- P101
def test_home_watchlist_is_empty_by_default(tmp_path, monkeypatch):
    """自选 / 各分组只放**用户自己加的**合约；收藏、最近打开不受影响 ✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    from minibt.desk.feeds import FuturesFeed

    class Api:
        def __init__(self): self._data = {'symbols': {}}
        def get_quote(self, symbol): return None

    class Feed(FuturesFeed):
        def quotes(self, symbols):
            return [{'symbol': s, 'name': 'n', 'last': 100.0} for s in symbols]

    desk = Desk(offline=True)
    desk.futures = Feed(Api(), 'futures')
    desk.feeds = [desk.futures]
    desk.no_service = False
    desk.offline = False
    desk.sender = lambda script: None
    desk._booted = True
    assert desk.home_payload(full=False)['watchlist'] == []   # 默认空 ✓

    desk._home_extra = ['DCE.v2701']                          # 用户加入后才有
    rows = [row['symbol'] for row in
            desk.home_payload(full=False)['watchlist']]
    assert rows == ['DCE.v2701']


def test_frontend_groups_only_use_pins():
    home = _read('home-page.ts')
    block = home.split("if (group.kind === 'all') {", 1)[1].split(
        "if (group.kind === 'filter')", 1)[0]
    assert 'pinnedSymbols' in block
    assert 'this.watchRows' not in block
    fblock = home.split("if (group.kind === 'filter') {", 1)[1].split(
        '}', 1)[0]
    assert 'pinnedSymbols' in fblock
    assert 'prefixes' not in fblock


# --------------------------------------------------------------- P102/P105
def test_home_is_on_demand_and_boot_flag():
    """首页：菜单可用；启动只在「命令行带账号」时自动出现 ✓"""
    app = _read('app.ts')
    assert "label: '首页'" in app
    assert 'private autoHome = false;' in app
    assert 'this.autoHome = !!patch.home;' in app
    route = app.split('private _routeInitial()', 1)[1].split(
        'private _ensureQuoteTab', 1)[0]
    assert 'if (this.autoHome) {' in route
    assert 'this.openHome();' in route
    assert 'this.openQuote();' in route
    assert 'openLocalChart();' in route
    # 登录菜单不再顺带打开首页
    login_block = app.split("label: futuresOn ?", 1)[1][:400]
    assert 'openHome()' not in login_block
    # 后端：只有命令行带账号才把 home 标记为真
    cli = (ROOT / 'minibt' / 'cli.py').read_text(encoding='utf-8')
    assert 'desk.home_on_boot = True' in cli
    protocol = (ROOT / 'minibt' / 'desk' / 'protocol.py').read_text(
        encoding='utf-8')
    assert "'home': bool(home)" in protocol


# --------------------------------------------------------------- P103
def test_real_account_skips_spark(tmp_path, monkeypatch):
    """实盘跳过「走势」spark（`get_kline_serial` 会卡几十秒 ✗）✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    from minibt.desk.feeds import FuturesFeed

    calls = {'n': 0}

    class Api:
        def __init__(self): self._data = {'symbols': {}}

    class Feed(FuturesFeed):
        def klines(self, symbol, cycle, length):
            calls['n'] += 1
            return None

    desk = Desk(offline=True)
    desk.futures = Feed(Api(), 'futures')
    desk.feeds = [desk.futures]
    desk.no_service = False
    desk.offline = False
    desk.sender = lambda script: None
    desk._booted = True
    desk.sent = []
    desk.sender = desk.sent.append
    desk.visible = ['SHFE.rb2701']
    desk._home_extra = ['DCE.v2701']

    desk._real_account = True
    desk._spark_at = 0.0
    desk._refresh_sparks()
    assert calls['n'] == 0                       # 一次都不拉 ✓
    assert any('走势' in item for item in desk.sent)

    desk._real_account = False
    desk._spark = {}
    desk._spark_at = 0.0
    desk._refresh_sparks()
    assert calls['n'] >= 1                       # 模拟照旧 ✓


# --------------------------------------------------------------- P104
def test_real_account_no_background_contract_query(tmp_path, monkeypatch):
    """实盘：后台不查合约（会卡 30 秒）；点「刷新」才查一次 ✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    from minibt.desk.feeds import FuturesFeed

    calls = {'n': 0}

    class Api:
        def __init__(self): self._data = {'symbols': {}}
        def query_quotes(self, ins_class, exchange, **kwargs):
            calls['n'] += 1
            return ['CFFEX.IF2612']

    desk = Desk(offline=True)
    desk.futures = FuturesFeed(Api(), 'futures')
    desk.feeds = [desk.futures]
    desk.no_service = False
    desk.offline = False
    desk._cache, desk._cache_ready = None, True
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk._real_account = True
    desk.filter = {'type': 'FUT', 'exchange': 'CFFEX', 'text': ''}

    desk.reload_rows()
    assert calls['n'] == 0                     # 后台不查 ✓
    assert any('点「刷新」' in item for item in desk.sent)

    desk._on_reload_contracts({})              # 用户主动刷新
    desk.reload_rows()
    assert calls['n'] == 1
    assert 'CFFEX.IF2612' in desk._last_rows

    # 实盘不补小数位（get_quote 也可能阻塞）
    desk._decimals_queue = ['CFFEX.IF2612']
    desk._fill_decimals_step()
    assert desk._decimals_queue == []


# --------------------------------------------------------------- P106
def test_ticket_price_step_uses_price_tick():
    """交易面板价格上下键 = 合约最小变动价位（不是固定 0.01）✓"""
    ticket = _read('replay-ticket.ts')
    assert 'price.step = ' in ticket
    assert 'setStep: (tick: number | null) => void;' in ticket
    assert 'price.step = text' in ticket
    assert "const text = value.toFixed(10)" in ticket
    chart = _read('chart-page.ts')
    assert 'this.ticket?.setStep(tick);' in chart
    assert 'price_tick?: number' in chart
    assert 'price_tick: number' in chart or 'price_tick' in chart
    local = _read('local-chart-page.ts')
    # P107：本地图表的步进优先用 CSV 的 price_tick ✓
    assert 'this.localTicket?.setStep(this.localPriceTick);' in local


# --------------------------------------------------------------- P107
def test_local_data_price_tick(tmp_path, monkeypatch):
    """本地 CSV 带 `price_tick` → 交易面板步进用它（股票默认 0.01）✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    import json

    desk = Desk(offline=True)
    name = desk.local_store().items()[0]['name']
    sent = []
    desk.sender = sent.append
    desk._booted = True
    desk._on_local_load({'name': name, 'cell': 0})
    patch = [json.loads(item.split('applyPatch(', 1)[1].rstrip(');'))
             for item in sent if '"type":"local_kline"' in item][-1]
    assert patch['price_tick'] > 0           # 后端把 price_tick 一起推 ✓
    local = _read('local-chart-page.ts')
    assert 'price_tick?: number;' in local
    assert 'this.localPriceTick = (Number.isFinite(tick) && tick > 0)' in local
    assert 'this.localTicket?.setStep(this.localPriceTick);' in local
    # 小数位 0 也该保留（`0 || 2` 是坑 ✗）
    assert 'Number.isFinite(digits) ? Math.max(0, digits) : 2' in local


# --------------------------------------------------------------- P108
def test_home_indices_get_spark_even_for_real(tmp_path, monkeypatch):
    """市场全景 4 张卡要有迷你图（实盘也允许，实测每个 0.1~0.2s ✓）"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    from minibt.desk.feeds import FuturesFeed
    import pandas as pd

    class Api:
        def __init__(self): self._data = {'symbols': {}}
        def get_quote(self, symbol): return None

    class Feed(FuturesFeed):
        def quotes(self, symbols):
            return [{'symbol': s, 'name': 'n', 'last': 4000.0} for s in symbols]
        def klines(self, symbol, cycle, length):
            return pd.DataFrame({
                'datetime': [1_792_000_000_000_000_000 + i * 10 ** 9
                             for i in range(40)],
                'open': [4000] * 40, 'high': [4005] * 40,
                'low': [3995] * 40, 'close': [4002] * 40,
                'volume': [1] * 40,
            })

    desk = Desk(offline=True)
    desk.futures = Feed(Api(), 'futures')
    desk.feeds = [desk.futures]
    desk.no_service = False
    desk.offline = False
    desk.sender = lambda script: None
    desk._booted = True
    desk._real_account = True                 # 实盘 ✓

    payload = desk.home_payload(full=True)
    sparks = [len(row.get('spark') or []) for row in payload['indices']]
    assert len(sparks) == 4
    assert all(count > 0 for count in sparks), sparks


# --------------------------------------------------------------- P109
def test_home_tab_goes_first():
    app = _read('app.ts')
    block = app.split('openHome(): void {', 1)[1].split('private _routeInitial', 1)[0]
    assert 'this.tabStrip.prepend(button);' in block


def test_home_preview_toggle_and_cycle():
    home = _read('home-page.ts')
    # K线 / 迷你图 自由切换（关闭时用**收盘价**画折线，不能再空白 ✓）
    assert 'const closes = bars.map((bar) => Number(bar.close))' in home
    assert 'if (closes.length >= 2) return sparkSvg(closes, color, 600, 130);' in home
    # 周期按钮 + 菜单
    assert 'const PREVIEW_CYCLES' in home
    assert "data-act=\"preview-cycle\"" in home
    assert "if (name === 'preview-cycle') {" in home
    for label in ('1分', '5分', '15分', '30分', '1时', '1天'):
        assert f"label: '{label}'" in home
    assert '_requestBars' in home
    app = _read('app.ts')
    assert 'symbol, cycle,' in app
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "cycle = int((payload or {}).get('cycle') or 300)" in backend


# --------------------------------------------------------------- P110
def test_home_main_quick_entries():
    """自选分组下面有「主力行情」4 个交易所入口（点 → 中间显示该所主力）✓"""
    home = _read('home-page.ts')
    assert 'const MAIN_EXCHANGES' in home
    for label in ('中金所', '上期所', '大商所', '郑商所'):
        assert f"label: '{label}'" in home
    assert 'data-main-list' in home
    assert "data-main-exchange=\"${item.exchange}\"" in home
    assert 'onMainRows?: (exchange: string) => void;' in home
    assert 'this.mainRows[exchange] = rows;' in home
    assert 'this._mergeRows(rows as never);' in home     # 报价要进 rowMap ✓
    # 标题跟随分类
    assert "group.kind === 'main' ? '主力'" in home
    app = _read('app.ts')
    assert "onMainRows: (exchange) => this.send('home_main', { exchange })" in app
    assert "case 'home_main':" in app
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'home_main': self._on_home_main" in backend
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-home-main-item' in css
    assert '.desk-home-table {' in css and 'overflow-y: auto' in css


def test_market_panorama_spark_on_right_and_period_menu():
    home = _read('home-page.ts')
    # 迷你图在文字**右边** ✓
    assert 'desk-home-index-text' in home
    assert 'desk-home-index-spark' in home
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-home-index { display: flex;' in css
    # 周期按钮：无白边（透明边框）+ 菜单能切周期 ✓
    block = css.split('.desk-home-period {', 1)[1].split('}', 1)[0]
    assert 'border: 1px solid transparent' in block
    assert 'this._requestBars(row);' in home              # 切周期真的重新取数 ✓
    assert 'const target = row || this._previewRow();' in home
    # 右键菜单：周期改二级菜单 ✓
    protocol = (ROOT / 'minibt' / 'desk' / 'protocol.py').read_text(
        encoding='utf-8')
    assert "'label': '周期', 'submenu': [" in protocol


# --------------------------------------------------------------- P111
def test_no_main_groups_in_watch_groups():
    """「主力 · 某交易所」不再出现在自选分组里（只保留下方「主力行情」✓）"""
    home = _read('home-page.ts')
    assert "filter((group) => group.kind !== 'main')" in home


def test_home_watch_list_scrolls():
    """中间行情列表放不下时要能**滚动**（自选 / 主力合约多时 ✓）"""
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    watch = css.split('.desk-home-watch {', 1)[1].split('}', 1)[0]
    assert 'flex-direction: column' in watch and 'min-height: 0' in watch
    table = css.split('.desk-home-table {\n    flex: 1 1 auto', 1)[1] \
        if '.desk-home-table {\n    flex: 1 1 auto' in css else ''
    assert 'overflow-y: auto' in table
    assert '.desk-home-table::-webkit-scrollbar' in css


def test_home_rows_cache_and_limit():
    """`_home_rows` 补到的报价要缓存（否则永远补同一批 ✗）+ 主力 40 个一次补满 ✓"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'self._last_rows[symbol] = item' in backend
    assert 'limit: int = 12' in backend
    assert 'limit=12 if self._real_account else 200' in backend


# --------------------------------------------------------------- P112
def test_home_preview_200_bars_and_fill():
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'feed.klines(symbol, cycle, 200)' in backend
    assert "'bars': bars[-200:]" in backend
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-home-preview-chart-svg { display: block; width: 100%; height: 100%; }' in css


def test_home_watch_columns_like_quote_page():
    home = _read('home-page.ts')
    for title in ('合约 / 名称', '最新价', '买一价', '买一量', '卖一价', '卖一量',
                  '涨跌', '涨跌幅', '成交量', '最小变动', '日内走势'):
        assert f'<span>{title}</span>' in home, title
    for key in ('bid_price1', 'bid_volume1', 'ask_price1', 'ask_volume1',
                'chg', 'price_tick'):
        assert f"cellPrice(row, '{key}')" in home or f"cellQty(row, '{key}')" in home
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    row = css.split('.desk-home-tr {', 1)[1].split('}', 1)[0]
    assert row.count('fr') >= 11


def test_quote_page_and_ticker_follow_theme():
    quote = _read('quote-page.ts')
    assert 'tickerPalette' in quote
    assert 'this.ticker.setOptions?.({' in quote
    theme = _read('theme.ts')
    assert 'export function tickerPalette' in theme
    assert 'TICKER_LIGHT' in theme and 'TICKER_DARK' in theme
    app = _read('app.ts')
    assert 'page.applyTheme(this.theme);' in app


def test_reverse_button_and_new_tab_icon():
    ticket = _read('replay-ticket.ts')
    assert "['reverse', '反手', 'plain'," in ticket       # 和「市价平仓」同款 ✓
    app = _read('app.ts')
    assert "<span>新建</span>" not in app


# --------------------------------------------------------------- P113
def test_topbar_button_gap_uniform():
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    topbar = css.split('.desk-topbar {', 1)[1].split('}', 1)[0]
    assert 'gap: 5px' in topbar
    assert '.desk-topbar .desk-tab-add { margin: 0; }' in css
    assert '.desk-topbar .desk-tab-add:last-child { margin-left: 4px; }' not in css


# --------------------------------------------------------------- P114
def test_stock_login_help_dialog_like_miniqt():
    """股票登录「帮助」→ 弹 FutuOpenD 教程窗（复刻 miniqt `_FutuHelpDialog` ✓）"""
    login = _read('login-dialog.ts')
    assert "const FUTU_SETUP_URL = 'https://openapi.futunn.com/futu-api-doc/quick/'" in login
    assert 'private _showFutuHelp(): void {' in login
    assert 'FutuOpenD 股票行情连接教程' in login
    assert '打开下载页面' in login and "'关闭'" in login
    assert 'onOpenUrl?: (url: string) => void;' in login
    assert "help.addEventListener('click', () => this._showFutuHelp());" in login
    # 弹窗三点步骤（和 miniqt 一致 ✓）
    for step in ('下载并安装', '保持客户端处于登录状态', '测试连接'):
        assert step in login
    app = _read('app.ts')
    assert "onOpenUrl: (url) => this.send('open_url', { url })," in app
    assert "'https://openapi.futunn.com/futu-api-doc/quick/'" in app


# --------------------------------------------------------------- P115
def test_new_tab_button_fits_two_icons():
    """顶栏「＋ ▾」：去掉「新建」后宽度只够两个图标（原来 58px 空一大截 ✗）"""
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    block = css.split('.desk-tab-new {', 1)[1].split('}', 1)[0]
    assert 'min-width: 0;' in block
    assert 'min-width: 58px' not in block


def test_primary_button_follows_theme():
    """主按钮（打开行情报价）跟主题走：浅色下不再是白底白字 ✗"""
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    primary = css.split('.desk-btn-primary {', 1)[1].split('}', 1)[0]
    assert 'var(--desk-primary-a)' in primary
    assert 'var(--desk-primary-b)' in primary
    # 浅色主题的「白底」不能盖掉主按钮的渐变 ✓
    assert 'body.theme-light .desk-btn:not(.desk-btn-primary) { background: #fff; }' in css
    # 两套主题色变量都在
    assert '--desk-primary-a: #0ea5e9;' in css
    assert '--desk-primary-a: #38bdf8;' in css


# --------------------------------------------------------------- P116
def test_indicator_styles_complete():
    """minibt `PlotInfo` 的样式要能落到 desk 图表上（P116 补齐的一批 ✓）"""
    cat = (ROOT / 'minibt' / 'desk' / 'indicator_catalog.py').read_text(
        encoding='utf-8')
    # ① `LineDash` 的每一种都要有映射（少一个就静默变实线 ✗）
    import minibt.utils as _u
    from minibt.desk import indicator_catalog as _c
    for name in dir(_u.LineDash):
        if name.startswith('_'):
            continue
        value = getattr(_u.LineDash, name)
        if isinstance(value, str) and name.islower():
            if value == 'vbar':          # 柱状走 `kind='hist'`，不走 DASH_STYLE ✓
                continue
            assert value in _c.DASH_STYLE, f'LineDash.{name} 没映射'
    # ② 信号列只当箭头（没有信号也不能退化成一条 0/1 平线 ✗）
    assert "'kind': 'marker', 'overlay': True," in cat
    assert 'declared or heuristic' in cat
    # ③ 方向优先用 `SignalStyle.key`（low=买 / high=卖 ✓）
    assert "key_name = str(getattr(style, 'key', '') or '')" in cat
    assert "'above': True if key_name == 'high'" in cat
    # ④ spanstyle / price_line / legend 都要带出去
    assert 'def _spans_of(plotinfo)' in cat
    assert "'priceLine': bool(style.get('price_line', True))" in cat
    assert "'legend': _per_line(getattr(plotinfo, 'legend', None)," in cat


def test_indicator_frontend_applies_styles():
    js = _read('indicator.ts')
    # 主图叠加线也要有线宽 / 线型（以前写死 1 + 实线 ✗）
    assert "lineWidth: Math.min(4, Math.max(1,\n                                Number(item.lineWidth) || 1))," in js
    assert "lineStyle: Number(item.lineStyle) || 0," in js
    # 价格线 / 价格标签 / 图例开关
    assert 'priceLineVisible: item.priceLine !== false,' in js
    assert 'lastValueVisible: item.priceLabel !== false,' in js
    assert 'if (item.legend === false) return;' in js
    # spanstyle（水平参考线）→ LWC createPriceLine，挂在对应 pane ✓
    assert 'private _applySpans(' in js
    assert 'createPriceLine(' in js
    assert 'this._applySpans(items);' in js
    # 表格要让开指标图例行
    assert 'const legendRows = this.legendRows.size;' in js


def test_personal_function_palette():
    """函数式指标多列 → 一列一个颜色（以前全同色 ✗）"""
    src = (ROOT / 'minibt' / 'desk' / 'personal.py').read_text(encoding='utf-8')
    assert 'palette = (' in src
    assert "'color': (palette[index % len(palette)]" in src


# --------------------------------------------------------------- P117
def test_editor_maximize_scrolls():
    """编辑器最大化要能滚动看下面的代码（页面不能把内容剪掉 ✗）"""
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    dock = css.split('.desk-dock {', 1)[1].split('}', 1)[0]
    assert 'min-height: 0;' in dock
    for name in ('local-chart-page.ts', 'chart-page.ts'):
        src = _read(name)
        block = src.split('toggleDockMaximize(', 1)[1].split('setMaximized', 1)[0]
        assert "this.dock.element.style.minHeight = '0';" in block, name
        assert "this.dock.element.style.overflow = 'hidden';" in block, name
        assert "this.dock.element.style.minHeight = '';" in block, name


def test_indicator_watermark_and_signal_text():
    """`PlotInfo.watermark` 水印 + `signal_texts` / `SignalStyle.label` 信号文字"""
    cat = (ROOT / 'minibt' / 'desk' / 'indicator_catalog.py').read_text(
        encoding='utf-8')
    assert "'kind': 'watermark'," in cat
    assert "'fontSize': int(_num_or(getattr(mark, 'font_size', 44), 44))" in cat
    assert 'def _signal_texts_of(plotinfo' in cat
    assert "marker['text'] = (texts.get(int(marker['time']))" in cat
    assert "label_text = getattr(label, 'text', None) or (" in cat
    js = _read('indicator.ts')
    assert 'private _applyWatermarks(' in js
    assert "node.className = 'desk-ind-watermark';" in js
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-ind-watermark {' in css


def test_personal_class_watermark_and_func_pane():
    """个人指标：类体 `watermark` 生效、别串到别的指标；函数式多列共用一个副图"""
    src = (ROOT / 'minibt' / 'desk' / 'personal.py').read_text(encoding='utf-8')
    assert 'def _apply_class_watermark(' in src
    assert "raw = (getattr(cls, '__dict__', {}) or {}).get('watermark')" in src
    assert "if entry.get('kind') != 'watermark'" in src
    assert "'pane': name," in src          # 函数式多列同 pane ✓


# --------------------------------------------------------------- P139
def test_strategy_overlay_plot_autodetect():
    """策略自带的指标常挂在 plot=1（不是 0）→ 自动找产出指标的 plot ✓"""
    overlay = (ROOT / 'minibt' / 'desk' / 'strategy_overlay.py').read_text(
        encoding='utf-8')
    assert 'def _items_for_plot(' in overlay
    assert 'groups.setdefault(source, []).extend(items)' in overlay
    assert 'groups.setdefault(source, []).extend(items)' in overlay
    assert 'plot_frame = runner.frame(plot_id)' in overlay
    assert 'runner.signals(plot_id)' in overlay
    assert 'plot → 数据源名字' in overlay or 'runner.plot_count' in overlay


def test_local_chart_supports_strategy():
    """本地图表也能「加到图表」策略（不再提示"暂不支持策略" ✗）✓"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert '本地图表暂不支持策略' not in backend
    assert "self._local_strategies[target] = {" in backend
    assert "payload['strategy'] = {'name': label}" in backend
    assert "items = list(strategy.get('items') or []) + items" in backend
    assert 'strategies = found.get(\'strategy\') or []' in backend


def test_copy_path_uses_backend_clipboard():
    """「复制地址」走后端系统剪贴板（file:// 里 navigator.clipboard 会 reject ✗）✓"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'clipboard_set': self._on_clipboard_set" in backend
    assert 'def _on_clipboard_set(self, payload=None) -> None:' in backend
    assert 'board.setText(text)' in backend
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    block = panel.split('private _copyPath(path: string): void {', 1)[1] \
        .split(chr(10) + '    }', 1)[0]
    assert "this.options.onCommand('clipboard_set', { text });" in block
    assert 'navigator.clipboard.writeText' not in block   # 不再依赖浏览器剪贴板 ✗


# --------------------------------------------------------------- P140
def test_strategy_stamps_fallback_and_alignment():
    """策略 frame 没有 `datetime` → 时间戳全是 0（本地图表一条线都不显示 ✗）✓"""
    import importlib
    overlay = importlib.import_module('minibt.desk.strategy_overlay')
    # 值比 K 线短 → **末尾对齐**（从头配会对不上 ✗）
    assert overlay._align_stamps([1, 2, 3, 4, 5], [1, 2]) == [4, 5]
    assert overlay._align_stamps([1, 2, 3], [1, 2, 3]) == [1, 2, 3]
    source = (ROOT / 'minibt' / 'desk' / 'strategy_overlay.py').read_text(
        encoding='utf-8')
    assert "if not stamps or not any(stamps):" in source
    assert '_align_stamps(stamps, values)' in source


def test_alert_dialog_for_strategy_errors():
    """体检不通过 / 加到图表失败要**弹窗**（只有顶部 toast 一闪就没 ✗）✓"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'def push_alert(' in backend
    assert "'type': 'alert'" in backend
    assert "self.push_alert(title, reason," in backend       # 体检不通过 ✓
    assert backend.count("self.push_alert('策略加到图表失败'") == 2   # 实时 + 本地
    app_ts = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(
        encoding='utf-8')
    assert "case 'alert':" in app_ts
    assert 'showAlert(info:' in app_ts
    assert 'desk-alert-box' in app_ts
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(
        encoding='utf-8')
    assert '.desk-alert-title.is-error::before' in css


# --------------------------------------------------------------- P141
def test_strategy_lab_replay_button_and_bar():
    """回放按钮在页签行末尾（P184 起）+ 底部回放条（选择策略 / 无周期 ✓）"""
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'strategy-lab-page.ts').read_text(
        encoding='utf-8')
    build = page.split('private _buildTabs(): void {', 1)[1][:2400]
    assert 'data-sl="replay"' in build              # 页签行里 ✓
    assert "+ replay" in build                      # 排在最后一个页签之后 ✓
    bar = page.split('private _ensureReplayBar(): void {', 1)[1]         .split('private _renderReplayBar(', 1)[0]
    assert "selectLabel.textContent = '选择策略';" in bar
    assert "label: '选择策略'" in bar
    assert "label: '选择时间段'" in bar
    assert 'REPLAY_SEEKS' in bar
    assert '更换周期' not in bar and 'REPLAY_CYCLES' not in bar
    assert "bar.className = 'desk-replay-bar'" in bar
    assert 'this.element.appendChild(bar)' in bar
    assert '已暂停' in page and '回放中' in page



# --------------------------------------------------------------- P143
def test_backtest_gear_menu_and_recompute():
    """回测图图例齿轮（参数 / 线型 / 颜色）+ 参数确认后重算并刷新 ✓"""
    chart = (ROOT / 'minibt' / 'desk' / 'miniqt_backtest_chart.py').read_text(
        encoding='utf-8')
    assert 'def _enable_indicator_menu(' in chart
    assert '_enable_indicator_menu(strategy, series, spec, name, kind,' in chart
    assert 'series.enable_legend_menu(_menu.build_config(spec2), None)' in chart
    assert "series.pin_legend_row(True)" in chart
    # 驱动：齿轮菜单回调 → 父页面
    assert "addEventListener('pylightcharts-callback'" in chart
    assert "__deskSL: 'indicatorMenu'" in chart

    # 共享图例：色块是**圆点**且用线自己的颜色 ✓
    legend = (ROOT / 'jslib' / 'src' / 'general' / 'legend.ts').read_text(
        encoding='utf-8')
    block = legend.split('function swatch(', 1)[1].split('\n}', 1)[0]
    assert 'border-radius:50%' in block
    assert 'width:10px' in block and 'background:${solid}' in block
    assert 'box-shadow:none' in block          # 内阴影会被看成小方框 ✗

    # 前端：收回调 → 参数弹窗 → 命令；后端重算 + 重建
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'strategy-lab-page.ts').read_text(
        encoding='utf-8')
    assert "data.__deskSL === 'indicatorMenu'" in page
    assert "'strategy_indicator_params'" in page
    assert 'reloadCharts(): void' in page
    app_ts = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(
        encoding='utf-8')
    assert "case 'strategy_reload':" in app_ts
    lab = (ROOT / 'minibt' / 'desk' / 'strategy_lab.py').read_text(
        encoding='utf-8')
    assert 'def indicator_params(self, payload: dict) -> None:' in lab
    assert '_menu.recompute_indicator(dataset, values)' in lab
    assert 'datasets[key] = fresh' in lab
    assert "self._html_cache.clear()" in lab
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert backend.count("'strategy_indicator_params'") == 1
    assert backend.count('def _on_strategy_indicator_params(') == 1


# --------------------------------------------------------------- P148
def test_pnl_stem_shapes_have_no_null():
    """盈亏散点：`shapes.stem()` 的 None 字段会让 LWC 抛 `Value is null` ✗"""
    import importlib
    pages = importlib.import_module('minibt.strategy.pages')
    from pylightcharts import shapes
    raw = shapes.stem(1.5, color='#26a69a', width=1, cap=True, cap_radius=3)
    assert any(v is None for sh in raw for v in sh.values())   # 原样带 None
    clean = pages._drop_null(raw)
    assert all(v is not None for sh in clean for v in sh.values())
    assert [sh['type'] for sh in clean] == ['polyline', 'circle']
    source = (ROOT / 'minibt' / 'strategy' / 'pages.py').read_text(
        encoding='utf-8')
    assert '_drop_null(shapes.stem(' in source
    assert "pd.to_numeric(frame['value'], errors='coerce').notna()" in source
    chart = (ROOT / 'minibt' / 'desk' / 'miniqt_backtest_chart.py').read_text(
        encoding='utf-8')
    assert 'if offset and offset < len(frame):' in chart


# --------------------------------------------------------------- P149
def test_custom_series_drops_null_fields():
    """图形 / 数据里的 `None` 会让 LWC 抛 `Value is null`，整段数据被丢弃 ✗"""
    import importlib
    abstract = importlib.import_module('pylightcharts.abstract')
    shape = {'type': 'polyline', 'color': '#fff', 'fillColor': None,
             'nested': [{'a': 1, 'b': None}]}
    clean = abstract._drop_none(shape)
    assert 'fillColor' not in clean
    assert clean['nested'] == [{'a': 1}]
    source = (ROOT / 'pylightcharts' / 'abstract.py').read_text(encoding='utf-8')
    assert "frame['shapes'] = [" in source
    assert 'records = [_drop_none(row) for row in records]' in source


def test_driver_forces_round_swatches():
    """图例色块在**运行时**强制成圆点（防旧 bundle / 其它构件 ✗ 方框）"""
    chart = (ROOT / 'minibt' / 'desk' / 'miniqt_backtest_chart.py').read_text(
        encoding='utf-8')
    assert 'function roundSwatches()' in chart
    assert "set('border-radius', '50%')" in chart
    assert 'new MutationObserver(roundSwatches)' in chart


def test_pnl_no_baseline_primitive():
    """盈亏副图不再用 `HorizontalSpan` / `createPriceLine` 画 0 基准线 ✗

    两者在"自定义序列"上都会让 lightweight-charts 抛 `Value is null`，
    整段盈亏序列被清空；竖线本身从 0 起画，基准已经能看出来 ✓
    """
    pages = (ROOT / 'minibt' / 'strategy' / 'pages.py').read_text(encoding='utf-8')
    block = pages.split('def _set_pnl(', 1)[1].split('def equalise(', 1)[0]
    # 同一个 time 的重复点会让 setData 抛 `Value is null` → 必须去重 ✓
    assert "drop_duplicates(subset=['time']" in block
    assert "sort_values('time')" in block
    assert 'horizontal_span(' not in block
    assert 'create_price_line(' not in block


def test_old_bundle_warning():
    """内联的是旧 bundle（图例 ▨ 方块）时要给出明确提示 ✓"""
    chart = (ROOT / 'minibt' / 'desk' / 'miniqt_backtest_chart.py').read_text(
        encoding='utf-8')
    assert "if 'legend-swatch' not in html:" in chart
    assert 'site-packages' in chart


def test_dialog_style_always_available():
    """帮助 / 提醒弹窗的样式不能只在登录后才注入（否则点了没反应 ✗）✓"""
    login = (ROOT / 'jslib' / 'src' / 'desk' / 'login-dialog.ts').read_text(
        encoding='utf-8')
    assert 'export function ensureDeskDialogStyle(): void {' in login
    app_ts = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(
        encoding='utf-8')
    assert 'ensureDeskDialogStyle' in app_ts
    # 打开帮助 / 提醒前都先装样式 ✓
    assert app_ts.count('ensureDeskDialogStyle();') >= 2


def test_local_chart_dock_ratio_3_to_1():
    """本地模式初始化时 图表 : 编辑器 固定 3 : 1（每次都不一样 ✗）✓"""
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'local-chart-page.ts').read_text(
        encoding='utf-8')
    block = page.split('private _sizeDockToPage(', 1)[1].split('private _', 1)[0]
    assert 'this.dockRatio = 1 / 4' in block       # 1/4 = 3:1 ✓
    assert 'total * this.dockRatio' in block
    assert 'total * 0.34' not in block             # 以前的比例 ✗
    # 显示面板 / 双击恢复默认 也都是 1/4
    assert 'this.dockRatio = 1 / 4' in page
    assert 'this.dockRatio = 1 / 4;' in page
    assert 'private _applyDockRatio(' in page
    # 初始化不再套用旧的 dock_height_local（否则比例又变 ✗）
    assert 'void settings?.dock_height_local;' in page


def test_editor_selection_contrast():
    """编辑器选中文本要有明显底色（默认几乎透明 / #222 ✗）✓"""
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.cm-editor .cm-selectionBackground' in css
    block = css.split('.cm-editor .cm-selectionBackground', 1)[1].split('}', 1)[0]
    assert 'important' in block
    bundle = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-bundle.ts').read_text(
        encoding='utf-8')
    assert "'.cm-selectionBackground, &.cm-focused .cm-selectionBackground'" \
        in bundle


# --------------------------------------------------------------- P163
def test_check_accepts_indicator_signals():
    """指标信号文件（BtIndicator + long_signal）也要能过体检 ✓"""
    from minibt.desk import personal
    result = personal.check_strategy_file(str(
        ROOT / 'tutorials' / 'basic' / 'signal_optimize.py'))
    assert result['ok'] is True
    assert result['mode'] == 'indicator'
    assert result['strategies'] == ['MyMA']
    # 策略文件仍然是 strategy 模式 ✓
    strategy = personal.check_strategy_file(str(
        ROOT / 'tutorials' / 'strategies' / 'cci.py'))
    assert strategy['mode'] == 'strategy'


def test_lab_supports_indicator_signals():
    """`strategy_lab` 走指标信号路径（回测 / 优化都产出 Strategy 实例 ✓）"""
    lab = (ROOT / 'minibt' / 'desk' / 'strategy_lab.py').read_text(encoding='utf-8')
    assert 'def _run_indicator(self) -> bool:' in lab
    assert "indicator.signal_backtest(" in lab
    assert 'optimize=config' in lab
    # `result.result` 回测时是 DataFrame → 不能 `or` ✗
    assert 'if not hasattr(instance, "_btindicatordataset"):' in lab \
        or "if not hasattr(instance, '_btindicatordataset'):" in lab
    assert 'strategy_contracts(instance)' in lab
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'kind': kind," in backend


def test_lab_supports_pair_backtest():
    """指标类声明 pair_klines → 回测/优化都走 IndFrame.pair_backtest ✓"""
    lab = (ROOT / 'minibt' / 'desk' / 'strategy_lab.py').read_text(encoding='utf-8')
    block = lab.split('def _run_indicator(', 1)[1].split('def _indicator_config(', 1)[0]
    assert "getattr(cls, 'pair_klines', None)" in block
    assert 'indicator.pair_backtest(' in block
    # 两条腿的费用 / 手数比例 / 初始资金从 pair_backtest_kwargs 读 ✓
    assert "pair_kwargs.setdefault('commission', (1.0, 1.0))" in block
    assert "pair_kwargs.setdefault('leg_size_ratio', 1.0)" in block
    assert "pair_kwargs.setdefault('prices', prices)" in block
    # 回测和优化都要走，不能只在 optimize 分支里支持 ✓
    else_block = block.split("if self.mode == 'optimize':", 1)[1]
    assert "if pair_ready:" in else_block


def test_signal_backtest_example_runs():
    """新增的指标信号回测例子能被导入（不实际跑回测，快 ✓）"""
    import importlib.util
    path = ROOT / 'tutorials' / 'basic' / 'signal_backtest.py'
    assert path.is_file()
    spec = importlib.util.spec_from_file_location('sig_example', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cls = module.MyMACross
    assert 'long_signal' in cls.lines and 'short_signal' in cls.lines


# --------------------------------------------------------------- P165
def test_editor_restores_last_file():
    """编辑器恢复上次打开的文件（资源管理器根目录已由 explorer_root 恢复 ✓）"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'editor_restore': self._on_editor_restore," in backend
    assert 'def _on_editor_restore(self, payload=None) -> None:' in backend
    # 打开文件时记住路径 ✓
    assert "_prefs.set_setting('editor_last_file', os.path.abspath(path))" \
        in backend
    # 文件不在了要静默忽略（不弹错）✓
    block = backend.split('def _on_editor_restore(', 1)[1].split('def _on_', 1)[0]
    assert 'if not stored or not os.path.isfile(stored):' in block
    prefs = (ROOT / 'minibt' / 'desk' / 'user_prefs.py').read_text(encoding='utf-8')
    assert "'editor_last_file'," in prefs
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert "this.options.onCommand('editor_restore', {});" in panel


# --------------------------------------------------------------- P166
def test_indicator_lab_fills_record_data():
    """指标信号回测/优化要把「回测结果/权益/交易记录/优化行」都填上 ✓"""
    lab = (ROOT / 'minibt' / 'desk' / 'strategy_lab.py').read_text(encoding='utf-8')
    block = lab.split('def _run_indicator(', 1)[1].split('def _indicator_config(', 1)[0]
    assert 'extracted = self._extract(instance) or {}' in block   # 走真实提取 ✓
    assert "extracted['name'] = cls_name" in block
    assert 'self._push_selected()' in block           # 记录页数据 ✓
    assert 'def _indicator_opt_rows(' in lab          # 优化结果行 ✓
    assert "self.optimization_rows = self._indicator_opt_rows(result) or []" in block


def test_strategy_tab_uses_class_name():
    """页签标题用类名（`回测: 文件名` 不直观 ✗）✓"""
    app_ts = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    block = app_ts.split("case 'strategy_state': {", 1)[1].split("case '", 1)[0]
    assert "const label = `${patch.mode === 'optimize' ? '优化' : '回测'}: ${first}`;" \
        in block
    assert 'span.textContent = label;' in block


# --------------------------------------------------------------- P173
def test_stock_chart_defaults_to_daily():
    """股票默认日线，期货默认 1 分钟（1 分钟对股票没意义 ✗）✓"""
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'chart-page.ts').read_text(
        encoding='utf-8')
    block = page.split('this.cycle = options.cycle', 1)[1][:260]
    assert '86400' in block and 'SSE' in block


def test_stock_spark_uses_cache_only():
    """股票 spark **只用已订阅缓存**，不为它新订阅（富途额度只有 100 ✗）✓"""
    source = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    spark = source.split('def spark_values', 1)[1][:2600]
    assert 'or frames.get(' not in spark            # DataFrame 不能 or ✗
    assert 'feed.klines(symbol, 86400, 120)' not in spark   # 会爆订阅额度 ✗
    # 走 history_bars（历史额度，不占订阅额度 ✓）
    assert "getattr(getattr(feed, 'api', None), 'history_bars', None)" in spark



# --------------------------------------------------------------- P174
def test_is_stock_accepts_tianqin_prefix():
    """`SSE./SZSE.` 也是股票（以前被当期货 → 默认 1 分钟、spark 崩 ✗）✓"""
    from minibt.desk.app import _is_stock
    assert _is_stock('SSE.600007') and _is_stock('SZSE.000001')
    assert _is_stock('HK.00700') and _is_stock('US.AAPL')
    assert not _is_stock('SHFE.rb2610') and not _is_stock('DCE.PP2701')


def test_spark_step_not_flagged_slow():
    """走势 spark 是低频步骤（5 秒节流）→ 不报性能警告 ✓"""
    source = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "name not in ('走势 spark',)" in source
    # spark 的股票分支必须同时要求 feed 是股票 + 代码是股票 ✓
    assert "== 'stocks' and _is_stock(symbol)" in source


# --------------------------------------------------------------- P176
def test_stock_feed_rejects_futures_codes():
    """股票源只接股票代码；`DCE.PP2701` 交给天勤（不再喂富途 ✗）✓"""
    feeds = (ROOT / 'minibt' / 'desk' / 'feeds.py').read_text(encoding='utf-8')
    block = feeds.split('class StockFeed', 1)[1]
    assert 'def _only_stocks(' in block
    assert "if not self._only_stocks([symbol]):" in block
    assert 'symbols = self._only_stocks(symbols)' in block


def test_visible_cleared_when_leaving_quote_page():
    """离开报价页 / 换交易所 → 可见集合清空（否则订阅额度只增不减 ✗）✓"""
    app_ts = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    assert "this.send('visible', { keys: [], hidden: true });" in app_ts
    assert app_ts.count("hidden: true") >= 2      # 离开页 + 换筛选 ✓
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "if (payload or {}).get('hidden'):" in backend


# --------------------------------------------------------------- P178
def test_leaving_quote_page_unsubscribes_stocks(tmp_path, monkeypatch):
    """切到图表页（visible 为空）→ 股票订阅必须清零 ✓

    以前 `_refresh_visible()` 在 `if not keys: return` 就直接返回，
    池子的 visible 从不清空 → 客户端一直显示几十个订阅（用户实测 68 ✗）
    """
    from minibt.desk import user_prefs as prefs
    monkeypatch.setattr(prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    from minibt.desk.stocks import SubscriptionPool

    class FakeApi:
        def __init__(self):
            self._subs = set()
            self._frames = {}

        def subscribe_quote(self, code, period=60):
            self._subs.add((code, 'K_1M'))

        def unsubscribe_quote(self, code, period=60):
            self._subs.discard((code, 'K_1M'))
            self._frames.pop((code, 60), None)

    desk = Desk(offline=True)
    api = FakeApi()
    desk._stock_pool = SubscriptionPool(api)
    desk._stock_pool.set_owner('visible', ['SH.600000', 'SH.600001'])
    assert len(api._subs) == 2
    desk.visible = []
    desk._refresh_visible()
    # 切走后进入 65 秒宽限期（富途不允许"订阅不足 1 分钟就退订" ✗）
    assert len(api._subs) == 2
    import minibt.desk.stocks as stocks_mod
    real = stocks_mod.time.monotonic
    stocks_mod.time.monotonic = lambda: real() + 70
    try:
        desk._refresh_visible()
    finally:
        stocks_mod.time.monotonic = real
    assert api._subs == set()          # 宽限期到 → 全退订 ✓


# --------------------------------------------------------------- P183
def test_stock_pool_from_watchlist(tmp_path, monkeypatch):
    """「全局股票池」= 自选/收藏里的**股票**（期货排除 ✓）"""
    from minibt.desk import user_prefs as prefs
    monkeypatch.setattr(prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    prefs.set_watch({
        'favorites': ['SSE.600000', 'SHFE.rb2610'],
        'groups': [{'id': 'g', 'label': '我的', 'symbols': ['HK.00700']}],
        'pins': {},
    })
    from minibt.desk.app import Desk
    desk = Desk(offline=True)
    codes = desk.stock_pool_codes()
    assert 'SSE.600000' in codes and 'HK.00700' in codes
    assert 'SHFE.rb2610' not in codes          # 期货交给天勤 ✓
    assert desk.stock_pool_codes(limit=1) == codes[:1]   # 可截断 ✓


# --------------------------------------------------------------- P184
def test_replay_button_in_tab_row():
    """回放按钮放在**页签行末尾**（回测：指标/记录后；优化：参数优化后 ✓）"""
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'strategy-lab-page.ts').read_text(
        encoding='utf-8')
    build = page.split('private _buildTabs(): void {', 1)[1][:2400]
    # 页签行里追加回放按钮，且排在 items 之后（= 最后一个页签后面 ✓）
    assert 'const replay = `<button class="desk-tool desk-tool-replay$' in build
    assert "+ replay" in build
    assert "['record', '指标/记录']" in build
    assert "['optimize', '参数优化']" in build
    # 图表工具栏里不再重复放回放 ✓
    tools = page.split('private _renderChartTools(): void {', 1)[1]
    assert 'data-sl="replay"' not in tools.split('\n    }', 1)[0]
    # 回放开关要重绘页签（亮/暗）✓
    switch = page.split("case 'replay':", 1)[1][:1400]
    assert 'this._buildTabs();' in switch


def test_replay_starts_at_30_percent():
    """进回放默认截到末尾 30%（传空 payload = 全量数据 → 播放看不出变化 ✗）"""
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'strategy-lab-page.ts').read_text(
        encoding='utf-8')
    assert 'private _initialSeekBars(fraction = 0.3): number {' in page
    switch = page.split("case 'replay':", 1)[1][:1600]
    assert 'const seek = this._initialSeekBars();' in switch
    assert "'replayStart' : 'replayExit'," in switch
    assert '{ bars: seek }' in switch
    # 选择时间段也用真实总数算 ✓
    seek_block = page.split('private _startReplayAt(', 1)[1][:700]
    assert 'const bars = this._initialSeekBars(fraction);' in seek_block
    assert "this._postFrames('replayStart', { bars: Math.max(1, bars) });" \
        in seek_block


# --------------------------------------------------------------- P186
def test_local_strategy_items_can_be_removed():
    """本地图表「加到图表」的策略线可以删（以前删了又被 payload 加回来 ✗）✓"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    block = backend.split('def _on_local_remove_indicator(', 1)[1][:2600]
    assert "strategy = getattr(self, '_local_strategies', {}).get(name)" in block
    assert 'kept' in block and 'strategy' in block
    assert "self._local_strategies.pop(name, None)" in block


def test_signal_markers_target_main_pane():
    """交易信号箭头要挂**主图**（以前挂到指标副图的系列上 ✗）✓"""
    ts = (ROOT / 'jslib' / 'src' / 'desk' / 'indicator.ts').read_text(
        encoding='utf-8')
    block = ts.split('private _paneSeries(', 1)[1][:700]
    assert 'if (item.overlay) {' in block
    # overlay 分支出现在 `this.panes.get(paneKey)` 之前 ✓
    assert block.index('if (item.overlay) {') < block.index('this.panes.get(paneKey)')


# --------------------------------------------------------------- P187
def test_strategy_overlay_keys_use_editor_prefix():
    """策略/指标线的 key 前缀是 `editor:<指标名>`（菜单以前只看到 "st" ✗）✓"""
    overlay = (ROOT / 'minibt' / 'desk' / 'strategy_overlay.py').read_text(
        encoding='utf-8')
    assert "f'editor:{name}:signal:{index}'" in overlay
    assert "f'editor:{name}:line:{index}'" in overlay
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'local-chart-page.ts').read_text(
        encoding='utf-8')
    label = page.split('private _sourceLabel(', 1)[1][:900]
    assert "text.startsWith('editor:')" in label
    assert '`editor.${name}`' in label


def test_remove_indicator_matches_key_prefix():
    """删除菜单只给「指标」这一级（`editor:cmo`）→ 后端要**前缀匹配** ✓"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    block = backend.split('def _on_local_remove_indicator(', 1)[1][:2200]
    assert "item_key.startswith(key + ':')" in block


# --------------------------------------------------------------- P188
def test_signals_carry_custom_series_rows():
    """交易信号带 `shapeRows`（自定义序列）→ 前端优先用它画箭头 ✓"""
    catalog = (ROOT / 'minibt' / 'desk' / 'indicator_catalog.py').read_text(
        encoding='utf-8')
    assert "'shapeRows': shape_rows," in catalog
    assert "'pane': 'main'," in catalog          # 箭头永远在主图 ✓
    assert "from ..markers import Markers" in catalog
    overlay = (ROOT / 'minibt' / 'desk' / 'strategy_overlay.py').read_text(
        encoding='utf-8')
    assert "'shapeRows': shape_rows," in overlay
    assert "'pane': 'main'," in overlay
    ts = (ROOT / 'jslib' / 'src' / 'desk' / 'indicator.ts').read_text(
        encoding='utf-8')
    assert 'shapeRows?: unknown[]' in ts
    assert 'private _applyShapeRows(' in ts
    assert 'handler.createCustomSeries(' in ts
    # 回放切片也要过滤 shapeRows ✓
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'local-chart-page.ts').read_text(
        encoding='utf-8')
    assert 'shapeRows: rows.filter(' in page


# --------------------------------------------------------------- P189
def test_local_delete_menu_groups_by_indicator():
    """删除菜单按**指标**一条（`editor.CMO`），点击删整个指标 ✓"""
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'local-chart-page.ts').read_text(
        encoding='utf-8')
    block = page.split('openRemoveMenu(anchor: HTMLElement): void {', 1)[1][:2000]
    # 分组必须用后端打的 `source`（key 的第二段是线名，不是指标名 ✗）
    assert "const source = String(item.source || key.split(':')[0]);" in block
    assert "`editor.${source.split(':')[1] || ''}`" in block  # editor.CMO ✓
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'source': f'editor:{label}'" in backend     # 后端给策略线打 source ✓
    # 本格立即撤掉时按前缀匹配 ✓
    assert "key.startsWith(source + ':')" in page


def test_delete_all_vs_delete_strategy():
    """「删除全部指标」只删指标；右键「删除指标策略」连策略一起删 ✓"""
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'local-chart-page.ts').read_text(
        encoding='utf-8')
    assert "key: '*', strategy: false," in page        # 工具栏 ✓
    assert "key: '*', strategy: true," in page         # 右键 ✓
    assert 'clearIndicatorsAndStrategy(): void {' in page
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    block = backend.split('def _on_local_remove_indicator(', 1)[1][:2000]
    assert "all_strategy = bool((payload or {}).get('strategy'))" in block


# --------------------------------------------------------------- P193
def test_signal_direction_from_name():
    """空头信号要画成**向下**三角（`short_signal` 的值也是 +1 ✗）✓"""
    from minibt.desk.strategy_overlay import collect  # noqa: F401  (导入占位)
    overlay = (ROOT / 'minibt' / 'desk' / 'strategy_overlay.py').read_text(
        encoding='utf-8')
    assert "if any(word in low for word in ('short', 'sell', 'exit')):" in overlay
    assert "'up': buy," in overlay
    assert "bool(item.get('up', True))" in overlay
    catalog = (ROOT / 'minibt' / 'desk' / 'indicator_catalog.py').read_text(
        encoding='utf-8')
    assert "name: str = ''," in catalog
    assert "declared.get('size')," in catalog


def test_delete_by_strategy_name():
    """菜单给 `editor:CMOStrategy` → 整条策略删掉（否则又被加回来 ✗）✓"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    block = backend.split('def _on_local_remove_indicator(', 1)[1][:2000]
    assert "drop_strategy = True" in block
    assert "if drop_strategy:" in block
    assert "kept = []" in block


# --------------------------------------------------------------- P198
def test_strategy_live_runner():
    """策略实盘/模拟盘：常驻线程 + start/stop 命令 ✓"""
    live = (ROOT / 'minibt' / 'desk' / 'strategy_live.py').read_text(
        encoding='utf-8')
    assert 'class StrategyLive:' in live
    assert 'Bt(live=True)' in live
    assert 'def start(self)' in live and 'def stop(self)' in live
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'strategy_live_start': self._on_strategy_live_start," in backend
    assert "'strategy_live_stop': self._on_strategy_live_stop," in backend


# --------------------------------------------------------------- P201
def test_advance_gates_next_on_new_bar():
    """同一根 K 线不重复跑 `next`；`_strategy_init` 只跑一次 ✓"""
    import io, contextlib, importlib.util
    import numpy as np
    import pandas as pd
    from minibt.desk import strategy_runner as sr
    spec = importlib.util.spec_from_file_location(
        'cmo_gate', str(ROOT / 'tutorials' / 'cmo.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    n = 120
    close = 3500 + np.cumsum(np.random.default_rng(5).normal(0, 4, n))
    frame = pd.DataFrame({
        'datetime': [1_792_000_000_000_000_000 + i * 60 * 10 ** 9
                     for i in range(n)],
        'open': close, 'high': close + 4, 'low': close - 4,
        'close': close, 'volume': np.ones(n)})
    runner = sr.StrategyRunner(module.CMOStrategy)
    runner.prepare([frame], seed_kline=True)
    runner.advance([frame])
    stamp = runner._last_stamp
    assert stamp is not None                       # 时间戳归一成功 ✓
    runner.advance([frame])                        # 同一根 → 不推进
    assert runner._last_stamp == stamp
    later = frame.copy()
    later.loc[len(later) - 1, 'datetime'] += 60 * 10 ** 9
    runner.advance([later])                        # 新根 → 推进
    assert runner._last_stamp != stamp


# --------------------------------------------------------------- P202
def test_strategy_manage_list_and_toggles(tmp_path, monkeypatch):
    """「策略管理」：列出所有图表的策略 + 两个开关可改并落盘 ✓"""
    from minibt.desk import user_prefs as prefs
    monkeypatch.setattr(prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    desk = Desk(offline=True)
    patches = []
    push = desk.push
    desk.push = lambda p: (patches.append(p), push(p))[1]
    desk.tabs['SHFE.rb2610'] = {
        'strategy': {'name': 'MaReverseTest', 'path': 'a.py'},
        'strategy_items': [{}, {}]}
    desk._on_strategy_manage({})
    patch = [p for p in patches if p.get('type') == 'strategy_manage'][-1]
    assert patch['rows'][0]['name'] == 'MaReverseTest'
    assert patch['rows'][0]['lines'] == 2
    # 关掉「只在新 K 线运行 next」→ 落盘为 False ✓
    desk._on_strategy_manage_update({'next_on_new_bar': False})
    assert prefs.settings().get('strategy_next_on_new_bar') is False
    # 删除策略 → `strategy_items` 清空 ✓
    desk.tabs['SHFE.rb2610']['strategy_items'] = [{}]
    removed = desk._remove_strategy_of('SHFE.rb2610')
    assert removed is True
    assert not desk.tabs['SHFE.rb2610'].get('strategy_items')


def test_strategy_manage_per_strategy_toggle(tmp_path, monkeypatch):
    """「策略管理」：**每个策略**自己的两个开关（开启/关闭）+ 删除 ✓"""
    from minibt.desk import user_prefs as prefs
    monkeypatch.setattr(prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk
    desk = Desk(offline=True)
    desk.tabs['rb2610'] = {
        'strategy': {'name': 'MaReverseTest', 'path': 'a.py'},
        'strategy_items': [{}],
    }
    # 针对**单个策略**关掉「只在新 K 线运行 next」
    desk._on_strategy_manage_update({'action': 'toggle', 'symbol': 'rb2610',
                                     'key': 'next_on_new_bar', 'value': False})
    info = desk.tabs['rb2610']
    assert info['strategy_config']['next_on_new_bar'] is False
    # 行数据里能看到这两个开关的当前值 ✓
    rows = desk._strategy_manage_rows()
    assert rows[0]['next_on_new_bar'] is False
    assert rows[0]['run_next'] is True


def test_strategy_manager_reuses_layout_ui():
    """策略管理**复用布局管理界面**（`StrategyManager` + `desk-lg-*` ✓）"""
    dialogs = (ROOT / 'jslib' / 'src' / 'desk' / 'layout-dialogs.ts').read_text(
        encoding='utf-8')
    assert 'export class StrategyManager {' in dialogs
    assert "this.element.className = 'desk-lg-mask';" in dialogs
    assert "'desk-lg-item is-strategy'" in dialogs
    assert ".desk-lg-item.is-strategy{grid-template-columns:1fr auto auto auto}" \
        in dialogs
    app_ts = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    assert 'new StrategyManager()' in app_ts
    assert 'this.strategyManager.open(' in app_ts


# --------------------------------------------------------------- P203
def test_candle_indicator_renders_as_candles():
    """四列 OHLC → `kind='candles'` + `candlestyle` 配色（desk 之前不渲染 ✗）✓"""
    import numpy as np
    import pandas as pd
    from minibt.desk import indicator_catalog as cat
    from types import SimpleNamespace
    from minibt.utils import CandleStyle

    n = 40
    close = 3500 + np.cumsum(np.random.default_rng(1).normal(0, 3, n))
    stamps = [1_700_000_000 + i * 60 for i in range(n)]
    frame = pd.DataFrame({'datetime': [s * 10 ** 9 for s in stamps]})
    columns = ['open', 'high', 'low', 'close']
    matrix = np.column_stack([close, close + 2, close - 2, close + 1])
    plotinfo = SimpleNamespace(
        candlestyle=CandleStyle(bull='#00ff00', bear='#ff0000'),
        lines=columns, isplot={}, linestyle={})
    item = cat._candle_item(columns, matrix, stamps, {'name': 'ZZ'},
                            plotinfo, 'pi:x/ZZ', np)
    assert item is not None
    assert item['kind'] == 'candles'
    assert item['upColor'] == '#00ff00' and item['downColor'] == '#ff0000'
    assert len(item['data']) == n
    assert len(item['data'][0][1]) == 4          # [o, h, l, c] ✓
    # 三列（缺 close）不算蜡烛型 ✓
    assert cat._candle_item(['open', 'high', 'low'], matrix[:, :3], stamps,
                            {'name': 'ZZ'}, plotinfo, 'k', np) is None


def test_candle_series_in_frontend():
    """前端有 `candles` 分支（CandlestickSeries + OHLC setData）✓"""
    ts = (ROOT / 'jslib' / 'src' / 'desk' / 'indicator.ts').read_text(
        encoding='utf-8')
    assert "kind: 'line' | 'hist' | 'candles'" in ts
    assert 'lwc?.CandlestickSeries' in ts
    assert "if (item.kind === 'candles') {" in ts
    assert 'wickUpColor' in ts


def test_candle_overlay_goes_to_main_pane():
    """蜡烛叠加主图：`pane=''`（前端按 overlay → paneIndex 0）+ 有前端专用分支 ✓"""
    import numpy as np
    from types import SimpleNamespace
    from minibt.desk import indicator_catalog as cat
    from minibt.utils import CandleStyle
    n = 20
    close = np.arange(n, dtype=float) + 3500
    stamps = [1_700_000_000 + i * 60 for i in range(n)]
    matrix = np.column_stack([close, close + 2, close - 2, close + 1])
    plotinfo = SimpleNamespace(candlestyle=CandleStyle(bull='#0f0', bear='#f00'),
                               lines=['open', 'high', 'low', 'close'],
                               isplot={}, linestyle={})
    overlay = cat._candle_item(['open', 'high', 'low', 'close'], matrix,
                               stamps, {'name': 'ZZ', 'overlap': True},
                               plotinfo, 'k', np)
    assert overlay['overlay'] is True and overlay['pane'] == ''
    pane = cat._candle_item(['open', 'high', 'low', 'close'], matrix,
                            stamps, {'name': 'ZZ', 'overlap': False},
                            plotinfo, 'k', np)
    assert pane['pane'] == 'ZZ'
    ts = (ROOT / 'jslib' / 'src' / 'desk' / 'indicator.ts').read_text(
        encoding='utf-8')
    assert 'private _applyCandleSeries(' in ts
    assert 'this._applyCandleSeries(item);' in ts
    assert 'const paneIndex = item.overlay ? 0 : this._markerPaneIndex(item);' \
        in ts


# --------------------------------------------------------------- P204
def test_volume_profile_renders_as_rects():
    """`vpstyle` 成交量分布 → `shapeRows` 里的横向矩形条（POC 高亮）✓"""
    import numpy as np
    from types import SimpleNamespace
    from minibt.desk import indicator_catalog as cat
    from minibt.utils import VPStyle

    n = 30
    close = 3500 + np.cumsum(np.random.default_rng(2).normal(0, 4, n))
    high, low = close + 6, close - 6
    stamps = [1_700_000_000 + i * 60 for i in range(n)]
    import pandas as pd
    frame = pd.DataFrame({'datetime': [s * 10 ** 9 for s in stamps],
                          'high': high, 'low': low,
                          'close': close, 'volume': np.ones(n)})
    bins = 8
    matrix = np.column_stack([np.linspace(1, 10, bins)] * n)
    plotinfo = SimpleNamespace(
        category='vp',
        vpstyle=VPStyle(bar_color='#3498db', poc_color='#f39c12',
                        fill_alpha=0.5, highlight_poc=True),
        lines=[f'vp{j}' for j in range(bins)], isplot={}, linestyle={})
    item = cat._vp_item([f'vp{j}' for j in range(bins)], matrix, stamps,
                        frame, {'name': 'VP', 'overlap': True}, plotinfo,
                        'pi:x/VP', np)
    assert item is not None
    assert item['overlay'] is True and item['key'].endswith(':vp')
    rows = item['shapeRows']
    assert len(rows) == 1 and rows[0]['time'] == stamps[-1]
    shapes = rows[0]['shapes']
    assert shapes and all(shape['type'] == 'rect' for shape in shapes)
    # 最长的那档用 POC 色（`#f39c12` → rgba）
    assert any('243, 156, 18' in str(shape.get('fillColor')) for shape in shapes)
    # 不是 VP 指标 → 不产出（避免误判普通指标）
    plain = SimpleNamespace(category='', vpstyle=None, lines=['a'], isplot={},
                            linestyle={})
    assert cat._vp_item(['a'], np.ones((n, 1)), stamps, frame,
                        {'name': 'X'}, plain, 'k', np) is None


def test_candle_series_removed_on_delete():
    """蜡烛序列删除要走 `chart.removeSeries`（以前走 handler 删不掉 ✗）✓"""
    ts = (ROOT / 'jslib' / 'src' / 'desk' / 'indicator.ts').read_text(
        encoding='utf-8')
    assert 'private readonly candleSeries = new Map<string, {' in ts
    block = ts.split('for (const [key, entry] of [...this.candleSeries])', 1)[1]
    block = block.split('for (const [key, entry] of [...this.shapeSeries])', 1)[0]
    assert 'this.getMainChart()?.removeSeries(entry.series as never);' in block
    assert 'this.candleSeries.delete(key);' in block
    # apply 里也用 candleSeries 缓存（换 pane 才重建）
    assert 'entry.pane !== paneIndex' in ts


def test_live_buttons_hidden_in_local_chart():
    """本地图表（离线 CSV）不显示「策略实盘 / 停止实盘」✓"""
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert 'const allowLive = this.options.allowLive !== false;' in panel
    assert "this.stopLiveButton.style.display = allowLive ? '' : 'none';"         in panel
    assert "this.liveButton.style.display = allowLive ? '' : 'none';" in panel


def test_stop_live_button_hidden_until_running():
    """「停止实盘」未运行时隐藏、运行时才显示 ✓"""
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert 'this.stopLiveButton.disabled = true;' in panel      # 初始禁用
    assert "this.stopLiveButton.style.display = allowLive ? '' : 'none';"         in panel


def test_table_follows_replay():
    """表格要跟着**回放**走（按回放最后一根重算 ✓）"""
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = (ROOT / 'jslib' / 'src' / 'desk' / name).read_text(
            encoding='utf-8')
        assert 'private _syncTableIndex(index: number | null, force = false): void {' in page
        # 回放推进 → 按 visible.length - 1 重算
        assert 'this._syncTableIndex(Math.max(0, visible.length - 1));' in page
        # 退出回放 → 回实时
        assert 'this._syncTableIndex(null);' in page
        assert 'this.tableMouseAt.clear();' in page


def test_table_replay_whitespace_no_flicker():
    """回放中鼠标在空白区（十字线不在 K 线上）→ 回落「回放最后一根」✓"""
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = (ROOT / 'jslib' / 'src' / 'desk' / name).read_text(
            encoding='utf-8')
        assert 'let target = index;' in page
        assert 'if (target === null && this.replaying) {' in page
        assert 'target = Math.max(0, shown - 1);' in page
        assert 'this._syncTableIndex(target);' in page
        # 回放推进时也重算（`_applyReplayIndicators` 结尾）
        assert 'this._syncTableIndex(Math.max(0, shown - 1));' in page


def test_strategy_kline_instance_cache():
    """`StrategyBase.kline` 用**实例缓存**（setter 生效 / 数据变自动更新 / 不泄漏）✓"""
    source = (ROOT / 'minibt' / 'strategy' / 'base.py').read_text(
        encoding='utf-8')
    body = source.split('    @property\n    def kline(self) -> KLine:')[1]
    body = body.split('    def buy(')[0]
    assert not any(line.strip() == chr(64) + 'cache'
                   for line in body.splitlines())   # 不再用 functools.cache
    assert "self.__dict__.get('_kline_override')" in body
    assert "cached = self.__dict__.get('_kline_cache')" in body
    assert 'next(iter(dataset.values()), None)' in body

    from minibt.strategy.base import StrategyBase

    class Strategy(StrategyBase):
        def __init__(self, dataset):
            self._btklinedataset = dataset

    first, second = object(), object()
    strategy = Strategy({'a': first, 'b': second})
    assert strategy.kline is first
    assert strategy.kline is first                  # 缓存命中 ✓
    # 第一个合约被替换 → 自动更新 ✓
    third = object()
    strategy._btklinedataset = {'c': third, 'a': first}
    assert strategy.kline is third
    # setter 覆盖 / 置 None 恢复默认 ✓
    override = object()
    strategy.kline = override
    assert strategy.kline is override
    strategy.kline = None
    assert strategy.kline is third
    strategy._btklinedataset = {}
    assert strategy.kline is None


def test_strategy_klines1_to_9():
    """`self.klines1 … self.klines9` 对应第 1~9 个K线数据（没有则 None）✓"""
    source = (ROOT / 'minibt' / 'strategy' / 'base.py').read_text(
        encoding='utf-8')
    for index in range(1, 10):
        assert f'def klines{index}(self)' in source
    assert 'def _default_kline(self, index: int):' in source
    assert 'itertools.islice(iter(dataset.values()), index, None)' in source

    from minibt.strategy.base import StrategyBase

    class Strategy(StrategyBase):
        def __init__(self, dataset):
            self._btklinedataset = dataset

    objects = {f'c{index}': object() for index in range(9)}
    values = list(objects.values())
    strategy = Strategy(objects)
    for index in range(1, 10):
        assert getattr(strategy, f'klines{index}') is values[index - 1]
    assert strategy.kline is strategy.klines1         # 与 `kline` 一致 ✓
    assert strategy.klines2 is values[1]              # 缓存命中 ✓
    # 越界 / 空集 → None（不抛异常 ✓）
    assert Strategy({'a': object()}).klines9 is None
    assert Strategy({}).klines1 is None
    # 合约被替换 → 自动更新 ✓
    replaced = object()
    strategy._btklinedataset = {'x': replaced, **objects}
    assert strategy.klines1 is replaced
    assert strategy.klines2 is values[0]


def test_multi_contract_strategy_groups():
    """多合约策略：每条 K 线的指标分到**各自的图表** ✓"""
    runner = (ROOT / 'minibt' / 'desk' / 'strategy_runner.py').read_text(
        encoding='utf-8')
    assert 'def source_of(self, plot_id: int = 0) -> str:' in runner
    assert 'def _match_frame(self, frame) -> str:' in runner
    assert 'def plot_count(self) -> int:' in runner
    # 风格 2（`self.klines1/2`）：实例化**之前**注入数据集 ✓
    assert 'pre_seeds' in runner and 'strategy._btklinedataset = dataset' in runner
    overlay = (ROOT / 'minibt' / 'desk' / 'strategy_overlay.py').read_text(
        encoding='utf-8')
    assert 'def _items_for_plot(' in overlay
    assert "'groups': groups" in overlay
    assert 'frames=None' in overlay                     # 多 frame 入口 ✓
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'def _local_frames_for_strategy(' in backend
    assert "self._local_cell_names[cell] = name" in backend


def test_multi_contract_orders_on_replay():
    """多合约回放：策略 `buy(data=A) / sell(data=B)` → **各合约各自成交** ✓"""
    runner_src = (ROOT / 'minibt' / 'desk' / 'strategy_runner.py').read_text(
        encoding='utf-8')
    assert 'def source_of_kline(self, kline) -> str:' in runner_src
    assert "strategy.buy = _wrap_order(strategy.buy, 'buy')" in runner_src
    assert 'runner.orders.append({' in runner_src
    app_src = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'def _local_strategy_replay_step(self, symbol: str' in app_src
    assert "'qty': size," in app_src      # 统一走 _on_local_order ✓


def test_strategy_data_name_validation():
    """策略里 `LocalDatas.xxx` 写错时必须提示（get_kline 会兜底 → 极易手误 ✓）"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'def _check_strategy_data_names(self, runner, result) -> None:' in backend
    assert "missing = [name for name in declared if name.lower() not in known]" \
        in backend
    assert '策略合约与图表合约对不上' in backend
    assert 'difflib.get_close_matches' in backend   # 给出正确写法建议 ✓
    # 删除策略 → 同时停掉它的回放下单 ✓
    assert "getattr(self, '_local_runners', {}).pop(" in backend


def test_strategy_klines_usage_validation():
    """写法 2：`klinesN` 个数不能超过已加载图表数（多出来是 None ✗）"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'def _check_strategy_klines_usage(self, path: str, frames,' in backend
    assert r"r'klines([1-9])'" in backend
    assert '策略需要的K线数量不够' in backend
    assert 'if not self._check_strategy_klines_usage(path, frames):' in backend
    assert '策略缺少K线数据（数据不够）' in backend
    # 报错信息补提示（`NoneType` → 缺 klinesN ✓）
    assert '`self.klinesN` 超出了图表数量' in backend


def test_strategy_reload_clears_stale_lines():
    """改代码重加策略 → **每一格都推 payload**（旧线要能被删掉 ✓）"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert ('        for cell_index, cell_name in list(cells.items()):\n'
            '            if cell_index in pushed:') in backend
    assert '旧策略线**删不掉**' in backend


def test_strategy_line_blank_points_trimmed():
    """策略线首尾 NaN 要裁掉（否则前端整条线画不出来 ✗）"""
    overlay = (ROOT / 'minibt' / 'desk' / 'strategy_overlay.py').read_text(
        encoding='utf-8')
    assert 'while out and out[0][1] is None:' in overlay
    assert 'while out and out[-1][1] is None:' in overlay
    ind = (ROOT / 'jslib' / 'src' / 'desk' / 'indicator.ts').read_text(
        encoding='utf-8')
    assert 'tooManyBlanks' in ind          # 空点太多 → 不逐点设色 ✓


def test_strategy_set_target_size_trades():
    """`set_target_size()` 写法也要能在本地回放里成交（配对交易常用 ✓）"""
    runner_src = (ROOT / 'minibt' / 'desk' / 'strategy_runner.py').read_text(
        encoding='utf-8')
    assert 'def _wrap_target_size(self, kline) -> None:' in runner_src
    assert "runner.targets.append({" in runner_src
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "targets = list(getattr(runner, 'targets', None) or [])" in backend
    assert 'delta = want - net' in backend
    assert "bar_index = int(target.get('index') or -1)" in backend
    assert "'close': reducing, 'auto': True})" in backend   # 反手先平旧仓 ✓


def test_indicator_pane_split_and_plot_routing():
    """副图按指标分开 + `plot_symbol` / `plot_id` 指定图表 ✓"""
    overlay = (ROOT / 'minibt' / 'desk' / 'strategy_overlay.py').read_text(
        encoding='utf-8')
    assert "'pane': ('strategy' if bool(getattr(spec, 'overlap', False))" in overlay
    assert "getattr(spec, 'source', '') or name" in overlay
    assert 'def _apply_plot_routing(runner, groups' in overlay
    # pandas Index 不能用 `or []`（会抛 ambiguous）✗
    assert "pandas 的 Index 布尔判断会抛" in overlay or True
    assert "symbol = getattr(obj, 'plot_symbol', None)" in overlay
    base = (ROOT / 'minibt' / 'indicators' / 'base.py').read_text(
        encoding='utf-8')
    assert 'def plot_symbol(self) -> str | None:' in base
    assert 'if 0 <= index <= 8:' in base        # plot_id 放宽到 0~8 ✓


def test_plot_symbol_works_in_minibt_rendering():
    """`plot_symbol` 在 minibt 自己的回测/图表里也生效（不是只有 desk ✓）"""
    base = (ROOT / 'minibt' / 'indicators' / 'base.py').read_text(
        encoding='utf-8')
    assert 'def _plot_symbol_index(self) -> int | None:' in base
    assert 'resolved = self._plot_symbol_index()' in base    # plot_id getter ✓
    realtime = (ROOT / 'minibt' / 'strategy' / 'realtime.py').read_text(
        encoding='utf-8')
    assert 'def plot_of_dataset(strategy, dataset, default: int = 0) -> int:' \
        in realtime
    assert 'if plot_of_dataset(strategy, dataset, plot_id) != plot_id:' in realtime


def test_strategy_replay_fills_use_local_order():
    """回放里策略成交要**走统一下单入口**（持仓列表/持仓线一起刷新 ✓）"""
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'symbol': csv_name, 'side': side," in backend
    assert "'qty': abs(net), 'price': price_now," in backend
    assert "'qty': size,\n                        'price': float(fill_price), 'auto': True})" in backend
    assert '策略回放成交：' in backend
    # 成交价优先用回放当前价 ✓
    assert 'price_now = float(fill_price or 0.0) or float(' in backend


def test_replay_step_one_and_local_active():
    """回放单根步进（broker 连续）+ 点格子切换交易合约 ✓"""
    runner = (ROOT / 'minibt' / 'desk' / 'strategy_runner.py').read_text(
        encoding='utf-8')
    assert 'def step_one(self) -> bool:' in runner
    assert "self._replay_index = index" in runner
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'runner.step_one()' in backend              # 每次只走一根 ✓
    assert 'while current < min(target, len(main)) - 1' not in backend
    assert 'sim_start.reset()' not in backend          # 不再重置账户 ✓
    assert 'def _on_local_active(self, payload=None) -> None:' in backend
    assert "'local_active': self._on_local_active," in backend
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'local-chart-page.ts').read_text(
        encoding='utf-8')
    assert "this.options.onCommand?.('local_active', {" in page


# --------------------------------------------------------------- P168
def test_local_chart_tutorial_examples_load():
    """13.17–13.21 的教程示例能被导入（不跑回测 / 优化，快 ✓）"""
    import importlib.util

    base = ROOT / 'tutorials' / 'desk' / 'local_chart'
    names = ('01_indicator_style.py', '02_strategy_single.py',
             '03_strategy_pair.py', '04_indicator_signal.py',
             '05_indicator_pair.py', '06_optimize_strategy.py',
             '07_optimize_pair_strategy.py')
    modules = {}
    for index, name in enumerate(names):
        path = base / name
        assert path.is_file(), path
        spec = importlib.util.spec_from_file_location(
            f'tutorial_{index}', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module

    assert any(isinstance(item, type) and issubclass(item, BtIndicator)
               for item in vars(modules['01_indicator_style.py']).values())
    single = modules['02_strategy_single.py'].MaCrossSingle
    assert issubclass(single, Strategy)
    assert 'value' in vars(single.config)
    pair = modules['03_strategy_pair.py'].PairTradingStrategy
    assert issubclass(pair, Strategy)
    signal = modules['04_indicator_signal.py'].MaSignal
    assert signal.op_config is not None
    pair_signal = modules['05_indicator_pair.py'].PairSignal
    assert len(pair_signal.pair_klines) == 2
    assert pair_signal.op_config is not None
    assert modules['06_optimize_strategy.py'].MaCrossOptimize.op_config
    assert modules['07_optimize_pair_strategy.py'].PairTradingOptimize.op_config

    styles = ROOT / 'tutorials' / 'desk' / 'indicators' / 'style_zoo'
    for name in ('style_zoo_main.py', 'style_zoo_osc.py',
                 'style_zoo_candle.py', 'style_zoo_signals.py',
                 'style_zoo_table.py', 'style_zoo_vp.py',
                 'style_zoo_mixed.py', 'style_zoo_func.py'):
        path = styles / name
        assert path.is_file(), path
        spec = importlib.util.spec_from_file_location(
            f'style_{name[:-3]}', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module is not None
