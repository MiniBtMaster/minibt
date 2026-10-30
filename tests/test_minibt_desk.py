"""minibt desk（报价 + 看盘）骨架：协议 / 补丁流 / 双壳 / 前端产物。

P0 验收内容：

* ``Desk(...).handle('ready')`` → boot → types → exchanges → rows（分块）
* 协议编解码 + K 线帧转换（纳秒 → 秒）
* 行模型（涨跌/涨跌幅按昨结算算）
* 富途代码映射
* 浏览器壳（HTTP 页面 + 静态资源 + POST 回调）
* 前端产物存在（``pylightcharts/js/desk.html`` / ``desk.js`` / ``desk.css``）
"""
import json
import pathlib
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from minibt.desk import protocol                       # noqa: E402
from minibt.desk.app import Desk, DESK_HTML            # noqa: E402
from minibt.desk import feeds, stocks, symbols         # noqa: E402


# ------------------------------------------------------------------ 协议
def test_patch_encode_decode_roundtrip():
    script = protocol.encode_patch({'type': 'toast', 'text': '你好'})
    assert script.startswith('window.__desk.applyPatch(') and script.endswith(');')
    payload = json.loads(script[len('window.__desk.applyPatch('):-2])
    assert payload == {'type': 'toast', 'text': '你好'}

    message = protocol.encode_command({'cmd': 'ready'})
    assert message.startswith('desk_~_')
    assert protocol.decode_command(message) == {'cmd': 'ready'}
    assert protocol.decode_command('garbage') == {}
    assert protocol.decode_command('desk_~_[1,2]') == {}


def test_chunked_splits_first_payload():
    blocks = protocol.chunked(range(1300), 500)
    assert [len(block) for block in blocks] == [500, 500, 300]
    assert protocol.chunked([], 500) == []


def test_bars_from_frame_converts_nanoseconds():
    pd = pytest.importorskip('pandas')
    frame = pd.DataFrame({
        'datetime': [1_700_000_000_000_000_000, 1_700_000_060_000_000_000],
        'open': [1.0, 2.0], 'high': [3.0, 4.0], 'low': [0.5, 1.5],
        'close': [2.5, 3.5], 'volume': [10, 20],
    })
    bars = protocol.bars_from_frame(frame)
    assert [bar['time'] for bar in bars] == [1_700_000_000, 1_700_000_060]
    assert bars[-1]['close'] == 3.5
    assert protocol.bars_from_frame(None) == []


# ------------------------------------------------------------------ 行模型
class _Quote:
    last_price = 110.0
    pre_settlement = 100.0
    pre_close = 99.0
    bid_price1 = 109.5
    bid_volume1 = 3
    ask_price1 = 110.5
    ask_volume1 = 4
    upper_limit = 120.0
    lower_limit = 90.0
    volume = 1234
    open = 101.0
    highest = 111.0
    lowest = 98.0
    price_tick = 0.5
    datetime = '2026-10-18 09:31:00'


def test_quote_row_uses_pre_settlement_for_change():
    row = symbols.quote_row('SHFE.rb2610', '螺纹', _Quote())
    assert row['symbol'] == 'SHFE.rb2610' and row['name'] == '螺纹'
    assert row['chg'] == pytest.approx(10.0)
    assert row['chg_pct'] == pytest.approx(10.0)
    assert row['quote_time'] == '09:31:00'
    assert set(row) == set(symbols.ROW_FIELDS)          # 不多不少 ✓


def test_row_filters_unknown_fields():
    row = symbols.row(symbol='A', name='B', bogus=1)
    assert 'bogus' not in row and row['last'] is None


def test_stock_code_mapping():
    assert stocks.to_futu_code('SSE.600000') == 'SH.600000'
    assert stocks.to_futu_code('SZSE.000001') == 'SZ.000001'
    assert stocks.to_futu_code('HK.00700') == 'HK.00700'
    assert stocks.to_futu_code('US.AAPL') == 'US.AAPL'
    assert stocks.from_futu_code('SH.600000') == 'SSE.600000'
    assert stocks.market_of('SZSE.000001') == 'SZSE'
    assert stocks.US_EXCHANGE_TYPES == ('US_NASDAQ', 'US_NYSE', 'US_AMEX')


# ------------------------------------------------------------- 补丁流
def _desk_with_recorder(**kwargs):
    sent = []
    desk = Desk(offline=True, **kwargs)
    desk.sender = sent.append
    return desk, sent


def _payload(script):
    return json.loads(script[len('window.__desk.applyPatch('):-2])


def _types_of(sent):
    return [_payload(script)['type'] for script in sent]


def test_ready_emits_boot_chips_and_rows():
    desk, sent = _desk_with_recorder()
    desk.handle(protocol.encode_command({'cmd': 'ready'}))
    # ★ 启动时会先推一行「版本指纹」log（build fingerprint ✓）
    kinds = [kind for kind in _types_of(sent) if kind != 'log']
    assert kinds[0] == 'boot'
    assert 'types' in kinds and 'exchanges' in kinds
    # 首屏只推骨架 + 「加载中」，真正的取数交给 tick（不阻塞 UI ✓）
    assert 'rows_loading' in kinds
    desk._tick_at = 0.0
    desk.tick()
    kinds = _types_of(sent)
    assert kinds.count('rows') >= 1
    boot = _payload(sent[kinds.index('boot')])
    assert boot['theme'] == 'dark' and boot['title']
    assert boot['markets']['offline'] is True
    first_rows = _payload(sent[kinds.index('rows')])
    assert first_rows['replace'] is True and first_rows['rows']


def test_filter_switch_rebuilds_exchanges():
    desk, sent = _desk_with_recorder()
    desk.handle(protocol.encode_command({'cmd': 'ready'}))
    sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'filter', 'payload': {'type': 'STOCK'}}))
    kinds = _types_of(sent)
    assert 'types' not in kinds            # 只有换类型才推 chips ✓
    assert 'exchanges' in kinds and 'rows' in kinds
    exchanges = _payload(sent[kinds.index('exchanges')])
    labels = [item['label'] for item in exchanges['items']]
    assert '港股' in labels and '美股' in labels


class _FakeFeed:
    """假行情源：不连网也能测 open_chart / set_cycle ✓"""

    kind = 'futures'

    def __init__(self):
        self.cycle = None

    def available(self):
        return True

    def contracts(self, ins_class, exchange):
        return ['SHFE.rb2610']

    def fill_names(self, symbols):
        return None

    def name_of(self, symbol):
        return '螺纹'

    def quotes(self, keys):
        return [symbols.row(symbol=key, name='螺纹', last=3600.0) for key in keys]

    def klines(self, symbol, cycle, length=500):
        self.cycle = cycle
        pd = pytest.importorskip('pandas')
        return pd.DataFrame({
            'datetime': [1_700_000_000_000_000_000, 1_700_000_060_000_000_000],
            'open': [1.0, 2.0], 'high': [3.0, 4.0], 'low': [0.5, 1.5],
            'close': [2.5, 3.5], 'volume': [10, 20],
        })


def test_open_chart_and_cycle():
    desk, sent = _desk_with_recorder()
    fake = _FakeFeed()
    desk.futures = fake
    desk.feeds = [fake]
    desk._booted = True
    sent.clear()

    desk.handle(protocol.encode_command(
        {'cmd': 'open_chart', 'payload': {'symbol': 'SHFE.rb2610'}}))
    kinds = _types_of(sent)
    # open_chart 现在还会带二级报价 + 持仓（P2 ✓）
    assert kinds[:2] == ['open_tab', 'kline']
    assert 'book' in kinds and 'position' in kinds
    tab = _payload(sent[0])
    assert tab['symbol'] == 'SHFE.rb2610' and tab['cycle'] == 60
    bars = _payload(sent[1])
    assert bars['replace'] is True and len(bars['bars']) == 2
    assert desk.tabs['SHFE.rb2610']['cycle'] == 60

    sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'set_cycle', 'payload': {'symbol': 'SHFE.rb2610', 'cycle': 86400}}))
    assert fake.cycle == 86400
    assert _types_of(sent) == ['kline']
    assert desk.tabs['SHFE.rb2610']['cycle'] == 86400


def test_visible_triggers_row_update():
    desk, sent = _desk_with_recorder()
    desk.futures = _FakeFeed()
    desk.feeds = [desk.futures]
    desk._booted = True
    sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'visible', 'payload': {'keys': ['SHFE.rb2610']}}))
    desk._tick_at = 0.0
    desk.tick()
    assert 'rows_update' in _types_of(sent)


def test_stock_symbol_opens_daily_tab():
    desk, sent = _desk_with_recorder()
    fake = _FakeFeed()
    desk.futures = fake
    desk.stocks = fake
    desk.feeds = [fake]
    desk._booted = True
    sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'open_chart', 'payload': {'symbol': 'HK.00700'}}))
    assert _payload(sent[0])['cycle'] == 86400      # 股票默认日线 ✓


# --------------------------------------------------------------- 浏览器壳
def test_browser_shell_serves_page_and_static():
    from minibt.desk import web

    desk = Desk(offline=True, port=0)
    thread = threading.Thread(target=lambda: web.serve(desk, open_browser=False),
                              daemon=True)
    thread.start()
    for _ in range(100):
        if getattr(desk, 'url', None):
            break
        time.sleep(0.05)
    assert getattr(desk, 'url', None), '浏览器壳没起来'
    base = desk.url.rstrip('/')

    page = urllib.request.urlopen(base + '/', timeout=5).read().decode('utf-8')
    assert './desk.js' in page and 'transport' in page
    assert str(desk._web_token) in page       # 命令令牌写进页面 ✓

    script = urllib.request.urlopen(base + '/static/desk.js', timeout=5).read()
    assert script.lstrip().startswith(b'var Desk')
    css = urllib.request.urlopen(base + '/static/desk.css', timeout=5).read()
    assert b'.desk-root' in css
    assert urllib.request.urlopen(base + '/health', timeout=5).read() == b'ok'

    body = json.dumps({'cmd': 'ready'}).encode()
    request = urllib.request.Request(
        base + '/callback', data=body,
        headers={'Content-Type': 'application/json',
                 'X-Desk-Token': str(getattr(desk, '_web_token', ''))})
    answer = json.loads(urllib.request.urlopen(request, timeout=5).read())
    assert answer == {'ok': True}

    # 无 token / 错 token → 403（防任意网页 POST 下单 ✓）
    for headers in ({'Content-Type': 'application/json'},
                    {'Content-Type': 'application/json',
                     'X-Desk-Token': 'wrong'}):
        bad = urllib.request.Request(base + '/callback', data=body,
                                     headers=headers)
        with pytest.raises(urllib.error.HTTPError) as info:
            urllib.request.urlopen(bad, timeout=5)
        assert info.value.code == 403


# ------------------------------------------------------------- 前端产物
def test_frontend_artifacts_present():
    js_dir = REPO / 'pylightcharts' / 'js'
    for name in ('desk.html', 'desk.js', 'desk.css', 'lightweight-charts.js'):
        assert (js_dir / name).is_file(), f'缺少 {name}（先 cd jslib && npm run build）'
    html = (js_dir / 'desk.html').read_text(encoding='utf-8')
    assert './desk.js' in html and './desk.css' in html
    script = (js_dir / 'desk.js').read_text(encoding='utf-8', errors='ignore')
    assert 'applyPatch' in script
    assert DESK_HTML.endswith('desk.html')


def test_transport_layer_has_three_backends():
    source = (REPO / 'jslib' / 'src' / 'desk' / 'transport.ts').read_text(
        encoding='utf-8')
    for name in ('QtTransport', 'SseTransport', 'RestTransport', 'MockTransport'):
        assert f'class {name}' in source, name
    app = (REPO / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    for case in ("'boot'", "'rows'", "'rows_update'", "'open_tab'", "'kline'",
                 "'toast'"):
        assert f'case {case}' in app, case
    quote = (REPO / 'jslib' / 'src' / 'desk' / 'quote-page.ts').read_text(
        encoding='utf-8')
    assert 'DataGrid' in quote and 'Ticker' in quote
    assert '行权价' in quote and '到期日' in quote


# ============================================ P1：缓存 / 气泡 / 右键 / 播放条
def test_symbol_cache_roundtrip_and_expiry(tmp_path):
    from minibt.desk.symbol_cache import SymbolCache

    db = str(tmp_path / 'symbols.sqlite3')
    cache = SymbolCache(db)
    rows = [{'symbol': 'SHFE.rb2610', 'name': '螺纹'}]
    assert cache.get('FUT:SHFE') is None
    cache.put('FUT:SHFE', rows)
    assert cache.get('FUT:SHFE') == rows
    assert cache.keys() == ['FUT:SHFE']

    other = SymbolCache(db)                     # 跨实例 / 跨进程 ✓
    assert other.get('FUT:SHFE') == rows

    other.put('FUT:SHFE', [{'symbol': 'X', 'name': '旧'}], updated=0)
    assert other.get('FUT:SHFE') is None        # 过期 → 忽略 ✓
    assert other.get('missing') is None

    other.drop('FUT:SHFE')
    assert other.keys() == []
    other.put('A', rows)
    other.clear()
    assert other.keys() == []


class _CountingFeed:
    """假行情源：记录被调用次数（验证缓存命中不再联网 ✓）"""

    kind = 'futures'

    def __init__(self):
        self.calls = 0
        self.cycle = None

    def available(self):
        return True

    def contracts(self, ins_class, exchange):
        self.calls += 1
        return ['SHFE.rb2610', 'SHFE.rb2611']

    def fill_names(self, symbols):
        return None

    def name_of(self, symbol):
        return '螺纹'

    def quotes(self, keys):
        return []

    def klines(self, symbol, cycle, length=500):
        self.cycle = cycle
        pd = pytest.importorskip('pandas')
        return pd.DataFrame({'close': [100.0 + index for index in range(120)]})


def _desk_p1(tmp_path):
    from minibt.desk.symbol_cache import SymbolCache

    sent = []
    desk = Desk(offline=True)
    desk.sender = sent.append
    desk._cache = SymbolCache(str(tmp_path / 'symbols.sqlite3'))
    desk._cache_ready = True
    desk.futures = _CountingFeed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    return desk, sent


def test_reload_rows_uses_cache_and_emits_ticker(tmp_path):
    desk, sent = _desk_p1(tmp_path)
    desk.reload_rows()
    kinds = _types_of(sent)
    assert 'rows' in kinds and 'ticker' in kinds and 'status' in kinds
    assert desk.futures.calls == 1

    ticker = _payload(sent[kinds.index('ticker')])
    assert {item['symbol'] for item in ticker['items']} == {'SHFE.rb2610',
                                                            'SHFE.rb2611'}

    sent.clear()
    desk.reload_rows()                       # 第二次走缓存 → 不再联网 ✓
    assert desk.futures.calls == 1
    assert 'rows' in _types_of(sent)


def test_row_click_emits_preview_with_spark(tmp_path):
    desk, sent = _desk_p1(tmp_path)
    desk.reload_rows()
    sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'row_click',
        'payload': {'symbol': 'SHFE.rb2610', 'x': 120, 'y': 240},
    }))
    patch = _payload(sent[-1])
    assert patch['type'] == 'preview'
    assert (patch['x'], patch['y']) == (120, 240)
    assert patch['data']['symbol'] == 'SHFE.rb2610'
    assert len(patch['data']['spark']) == 40
    assert patch['data']['spark'][-1] == 219.0     # 最新一根
    assert desk.futures.cycle == 60                # spark 用 1 分钟线 ✓

    # 第二次走缓存（不再拉 K 线）
    calls = desk.futures.calls
    desk.handle(protocol.encode_command({
        'cmd': 'row_click', 'payload': {'symbol': 'SHFE.rb2610'},
    }))
    assert desk.futures.calls == calls


def test_context_menu_emits_periods(tmp_path):
    desk, sent = _desk_p1(tmp_path)
    sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'context_menu',
        'payload': {'symbol': 'SHFE.rb2610', 'name': '螺纹', 'x': 10, 'y': 20},
    }))
    patch = _payload(sent[-1])
    assert patch['type'] == 'menu'
    assert patch['symbol'] == 'SHFE.rb2610'
    # 菜单已改成「打开图表 + 周期 ›（二级）」（P20 起的结构 ✓）
    labels = [item.get('label') for item in patch['items']]
    assert labels == ['打开图表', '周期']
    submenu = patch['items'][1]['submenu']
    assert [item['cycle'] for item in submenu] == [
        30, 60, 300, 900, 1800, 3600, 86400]


def test_preview_and_menu_assets_built():
    js_dir = REPO / 'pylightcharts' / 'js'
    script = (js_dir / 'desk.js').read_text(encoding='utf-8', errors='ignore')
    css = (js_dir / 'desk.css').read_text(encoding='utf-8')
    assert 'desk-preview' in script and 'desk-preview' in css
    assert 'desk-menu-sep' in script and 'desk-menu-sep' in css
    # 前端源码里两个新补丁都在
    app = (REPO / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    for case in ("'preview'", "'menu'", "'close_menu'"):
        assert f'case {case}' in app, case
    assert (REPO / 'jslib' / 'src' / 'desk' / 'symbol-preview.ts').is_file()
    assert (REPO / 'jslib' / 'src' / 'desk' / 'menu.ts').is_file()


def test_spark_column_fills_visible_rows(tmp_path):
    desk, sent = _desk_p1(tmp_path)
    desk.reload_rows()
    desk.handle(protocol.encode_command(
        {'cmd': 'visible', 'payload': {'keys': ['SHFE.rb2610', 'SHFE.rb2611']}}))
    sent.clear()
    desk._tick_at = 0.0
    desk._spark_at = 0.0
    desk.tick()
    updates = [_payload(script) for script in sent
               if _payload(script)['type'] == 'rows_update']
    assert updates, '没有补 spark'
    rows = {row['symbol']: row for row in updates[0]['rows']}
    assert 'spark' in rows['SHFE.rb2610']
    assert len(rows['SHFE.rb2610']['spark']) == 40
    # 5 秒内不重复拉 ✓
    sent.clear()
    desk._tick_at = 0.0
    desk.tick()
    assert not [s for s in sent if _payload(s)['type'] == 'rows_update']
