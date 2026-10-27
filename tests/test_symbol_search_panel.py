"""SymbolSearch 插件 + desk 的搜索/切换合约 + 交易面板默认隐藏。

覆盖：
* pylightcharts `SymbolSearch`（Python 包装 / 事件）
* desk `symbol_search` / `switch_symbol`（后端搜合约 + tab 换合约）
* 「交易」「二级报价」默认隐藏、按钮高亮同步
* 预警不再用 bridge 回调名（0.1.5 会 TypeError ✗）
"""
import contextlib
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from minibt.desk import protocol                     # noqa: E402

DESK_TS = REPO / 'jslib' / 'src' / 'desk'
PANEL_TS = REPO / 'jslib' / 'src' / 'panels'


def _read(path):
    return pathlib.Path(path).read_text(encoding='utf-8')


# ------------------------------------------------------ pylightcharts 面板
class FakeWin:
    def __init__(self):
        self.scripts = []
        self.handlers = {}
        self._panels = []

    def run_script(self, script):
        self.scripts.append(script)

    def invoke(self, *args, **kwargs):
        return None

    def invoke_get(self, *args, **kwargs):
        return None

    @contextlib.contextmanager
    def bulk_run(self):
        yield

    class _Gen:
        count = 0

        def generate(self):
            FakeWin._Gen.count += 1
            index = FakeWin._Gen.count

            class Handle:
                def __str__(self):
                    return f'window.ss{index}'

                def __getattr__(self, item):
                    return f'window.ss{index}.{item}'

            return Handle()

    _id_gen = _Gen()


def test_symbol_search_python_panel():
    from pylightcharts.panels import SymbolSearch

    window = FakeWin()
    search = SymbolSearch(window, items=[
        {'symbol': 'SHFE.rb2610', 'name': '螺纹', 'exchange': 'SHFE'}])
    first = window.scripts[0]
    assert 'new Lib.SymbolSearch(' in first
    assert '"symbol":"SHFE.rb2610"' in first
    assert list(window.handlers) == [str(search.id)]

    window.scripts.clear()
    search.open('rb')
    search.set_items([{'symbol': 'DCE.i2609'}])
    search.set_results([{'symbol': 'SHFE.rb2611'}])
    search.set_theme('light')
    joined = '\n'.join(window.scripts)
    assert '.open("rb")' in joined
    assert '.setItems([{"symbol":"DCE.i2609"' in joined
    assert '.setResults(' in joined and '.setTheme("light")' in joined

    calls = []
    search.on_query(lambda text: calls.append(('query', text)))
    search.on_pick(lambda item: calls.append(('pick', item['symbol'])))
    search._dispatch('query;;;rb')
    search._dispatch('pick;;;SHFE.rb2610')
    assert calls == [('query', 'rb'), ('pick', 'SHFE.rb2610')]


def test_symbol_search_assets():
    source = _read(PANEL_TS / 'symbol-search.ts')
    for key in ('export class SymbolSearch', 'pylc-ss-mask', 'setItems',
                'setResults', 'onQueryCallback', 'onPickCallback',
                'ArrowDown'):
        assert key in source, key
    assert "export * from './symbol-search';" in _read(PANEL_TS / 'index.ts')
    assert 'pylc-ss-mask' in _read(REPO / 'pylightcharts' / 'js' / 'bundle.js')
    assert 'pylc-ss-mask' in _read(REPO / 'pylightcharts' / 'js' / 'desk.js')


def test_symbol_search_example_check_mode():
    import subprocess

    script = REPO / 'examples' / '13_panels' / '13_symbol_search.py'
    result = subprocess.run([sys.executable, str(script), '--check'],
                            capture_output=True, text=True, encoding='utf-8',
                            env={**dict(__import__('os').environ),
                                 'PYTHONIOENCODING': 'utf-8'})
    assert result.returncode == 0, result.stderr[-600:]
    assert 'SymbolSearch 数据检查通过' in result.stdout


# ------------------------------------------------------------ desk 搜索/切换
class _Feed:
    kind = 'futures'

    def __init__(self):
        self.api = None

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
        return type('Q', (), {'last_price': 3600.0})()

    def klines(self, symbol, cycle, length=500):
        pd = pytest.importorskip('pandas')
        return pd.DataFrame({
            'datetime': [1_700_000_000_000_000_000] * 2,
            'open': [1.0, 2.0], 'high': [2.0, 3.0], 'low': [0.5, 1.5],
            'close': [1.5, 2.5], 'volume': [10, 20]})


class _Cache:
    def __init__(self, data):
        self.data = data

    def keys(self):
        return list(self.data)

    def get(self, key):
        return self.data.get(key)

    def put(self, key, rows):
        self.data[key] = rows


def _desk(tmp_path):
    from minibt.desk.app import Desk

    desk = Desk(offline=True, allow_trading=False)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = _Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    desk._cache = _Cache({
        'FUT:SHFE': [{'symbol': 'SHFE.rb2610', 'name': '螺纹钢2610'},
                     {'symbol': 'SHFE.rb2611', 'name': '螺纹钢2611'}],
        'FUT:DCE': [{'symbol': 'DCE.i2609', 'name': '铁矿石2609'}],
        'stock:SSE': [{'symbol': 'SSE.600000', 'name': '浦发银行'}],
    })
    desk._cache_ready = True
    desk.tabs['SHFE.rb2610'] = {'feed': desk.futures, 'cycle': 60}
    return desk


def _patches(sent):
    return [json.loads(script[len('window.__desk.applyPatch('):-2])
            for script in sent]


def test_symbol_search_matches_code_and_name(tmp_path):
    desk = _desk(tmp_path)
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'symbol_search', 'payload': {'text': 'rb'}}))
    patch = _patches(desk.sent)[-1]
    assert patch['type'] == 'symbol_search'
    symbols = [item['symbol'] for item in patch['items']]
    assert symbols == ['SHFE.rb2610', 'SHFE.rb2611']      # 前缀优先 ✓

    desk.handle(protocol.encode_command(
        {'cmd': 'symbol_search', 'payload': {'text': '浦发'}}))
    hit = _patches(desk.sent)[-1]['items']
    assert hit and hit[0]['symbol'] == 'SSE.600000'


def test_switch_symbol_reloads_everything(tmp_path):
    desk = _desk(tmp_path)
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'switch_symbol',
        'payload': {'from': 'SHFE.rb2610', 'to': 'DCE.i2609',
                    'name': '铁矿石2609'},
    }))
    patches = _patches(desk.sent)
    kinds = [patch['type'] for patch in patches]
    assert kinds[0] == 'switch_symbol'
    assert kinds[0] == 'switch_symbol' and patches[0]['new'] == 'DCE.i2609'
    for key in ('kline', 'book', 'position', 'account', 'indicator'):
        assert key in kinds, key
    assert list(desk.tabs) == ['DCE.i2609']               # tab 换键 ✓
    assert desk.tabs['DCE.i2609']['cycle'] == 60

    # 切换合约必须清掉旧合约的指标（旧线 / 旧价位不能带过去 ✓）；
    # 前端 resetIndicators() 后由用户在新合约上重新加指标。
    desk.tabs['DCE.i2609']['indicators'] = [{'key': 'MA', 'params': {}}]
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'switch_symbol',
        'payload': {'from': 'DCE.i2609', 'to': 'SHFE.rb2610'},
    }))
    assert desk.tabs['SHFE.rb2610']['indicators'] == []


# --------------------------------------------------- 交易/二级报价默认隐藏
def test_dock_and_book_default_hidden():
    chart = _read(DESK_TS / 'chart-page.ts')
    assert 'private dockVisible = false;' in chart
    assert 'private bookVisible = false;' in chart
    assert "this.dock.element.style.display = 'none';" in chart
    assert "this.book.element.style.display = 'none';" in chart
    assert 'classList.toggle(\'on\', this.dockVisible)' in chart
    # 高亮色 = chips 选中色 ✓
    css = _read(DESK_TS / 'desk.css')
    assert '.desk-tool.on {' in css and 'var(--desk-accent)' in css


def test_alert_dialog_does_not_use_bridge_callback():
    chart = _read(DESK_TS / 'chart-page.ts')
    assert "callbackName = 'desk-alert'" not in chart
    assert 'onCreateCallback' in chart and 'onDeleteCallback' in chart
