"""主题跟随 / 按钮 tooltip / 二级报价格式 / 预警对话框 / 股票诊断。

对应这一轮用户反馈的 4 组问题：

1. 报价列表与图表不跟随主题 → `theme.ts` + `applyTheme` 广播
2. 二级报价「成交额」太长 → 改「额」+ 万/亿；深色滚动条 → `color-scheme: dark`
3. 股票没数据但没报错 → `stocks.last_error` + toast + `minibt desk --check`
4. tooltips / 预警界面（pylightcharts `AlertDialog`）/ 工具栏「交易」「二级报价」「截图靠右」
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


# ------------------------------------------------------------ 1) 主题跟随
def test_theme_palettes_and_broadcast():
    theme = _read(DESK_TS / 'theme.ts')
    assert 'export function gridPalette' in theme
    assert 'export function chartOptions' in theme
    assert "'#ffffff'" in theme and "'#0f1115'" in theme

    app = _read(DESK_TS / 'app.ts')
    assert 'this.quotePage?.applyTheme(theme)' in app
    assert 'page.applyTheme(theme)' in app
    assert 'this.send(\'alerts\', {})' in app

    quote = _read(DESK_TS / 'quote-page.ts')
    assert 'applyTheme(theme: DeskTheme)' in quote
    assert 'gridPalette(theme)' in quote

    chart = _read(DESK_TS / 'chart-page.ts')
    assert 'applyTheme(theme: \'light\' | \'dark\')' in chart
    assert 'chartOptions(theme)' in chart
    assert 'this.indicators?.applyTheme(theme)' in chart

    indicator = _read(DESK_TS / 'indicator.ts')
    # P35：副图 = 主图的 pane（同一个 chart），主题由主图统一应用 ✓
    assert 'applyTheme(' in indicator


# ------------------------------------------------ 2) 成交额 / 滚动条 / tooltip
def test_book_amount_is_short():
    panel = _read(DESK_TS / 'quote-panel.ts')
    assert "['amount', '额']" in panel
    assert 'function compact(' in panel
    assert '亿' in panel and '万' in panel          # 万/亿 缩写 ✓
    # 原始值放进 title（悬停看完整数字 ✓）
    assert 'title="${num(value, digits)}"' in panel


def test_dark_scrollbars_and_tooltips():
    css = _read(DESK_TS / 'desk.css')
    assert 'body.theme-dark { color-scheme: dark; }' in css
    assert '.desk-book-ticks::-webkit-scrollbar-thumb' in css
    assert 'body.theme-dark .desk-book-ticks::-webkit-scrollbar-thumb' in css

    chart = _read(DESK_TS / 'chart-page.ts')
    # 所有工具栏按钮都带 tooltip ✓
    for tip in ('价格预警', '画线工具箱', '布局：单图', '显示 / 隐藏下方',
                '显示 / 隐藏右侧', '截图（PNG）'):
        assert tip in chart, tip


# --------------------------------------------- 3) 工具栏顺序 / 交易与报价开关
def test_toolbar_order_and_toggles():
    chart = _read(DESK_TS / 'chart-page.ts')
    # 右组以截图结尾：spacer 之后的最后一个按钮是 📷 ✓
    assert 'spacer,' in chart
    tail = chart.split('spacer,', 1)[1].split(');', 1)[0]
    assert tail.strip().endswith('shotButton')
    assert 'tradeButton' in tail and 'bookButton' in tail
    assert 'toggleDock' in chart and 'toggleBook' in chart
    assert 'this.dock.element.style.display' in chart
    assert 'this.book.element.style.display' in chart


# --------------------------------------------------------- 4) 预警方向/到期
class _Feed:
    kind = 'futures'

    def __init__(self, price=100.0):
        self.price = price

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
        return type('Q', (), {'last_price': self.price})()

    def klines(self, *args, **kwargs):
        return None


def _desk(feed=None):
    from minibt.desk.app import Desk

    desk = Desk(offline=True, allow_trading=False)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = feed or _Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    desk.tabs['SHFE.rb2610'] = {'feed': desk.futures, 'cycle': 60}
    return desk


def _patches(sent):
    return [json.loads(script[len('window.__desk.applyPatch('):-2])
            for script in sent]


def test_alert_cross_directions():
    from minibt.desk.app import _alert_crossed

    assert _alert_crossed('上穿', 99.0, 101.0, 100.0) is True
    assert _alert_crossed('上穿', 101.0, 102.0, 100.0) is False
    assert _alert_crossed('下穿', 101.0, 99.0, 100.0) is True
    assert _alert_crossed('下穿', 99.0, 98.0, 100.0) is False
    assert _alert_crossed('穿过', 101.0, 99.0, 100.0) is True
    assert _alert_crossed('穿过', None, 100.0, 100.0) is True


def test_alert_stores_cross_action_qty_message():
    desk = _desk()
    desk.handle(protocol.encode_command({
        'cmd': 'add_alert',
        'payload': {'symbol': 'SHFE.rb2610', 'price': 100.0, 'cross': '上穿',
                    'action': '买', 'qty': 3, 'message': '到价了',
                    'expire': 3600},
    }))
    alert = desk.alerts[0]
    assert alert['cross'] == '上穿' and alert['action'] == 'buy'
    assert alert['qty'] == 3 and alert['message'] == '到价了'
    assert alert['expires_at'] and alert['expires_at'] > 0

    patch = [p for p in _patches(desk.sent) if p['type'] == 'alerts'][-1]
    assert patch['items'][0]['cross'] == '上穿'
    assert patch['items'][0]['action'] == 'buy'


def test_alert_expires_and_fires_once():
    desk = _desk(_Feed(price=100.0))
    desk.handle(protocol.encode_command({
        'cmd': 'add_alert',
        'payload': {'symbol': 'SHFE.rb2610', 'price': 100.0, 'cross': '穿过'},
    }))
    desk.alerts[0]['expires_at'] = 1          # 已过期 ✓
    desk.sent.clear()
    desk.check_alerts()
    assert desk.alerts[0]['fired'] is True
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert 'alert_fired' not in kinds          # 过期不触发下单提醒 ✓

    desk2 = _desk(_Feed(price=100.0))
    desk2.handle(protocol.encode_command({
        'cmd': 'add_alert',
        'payload': {'symbol': 'SHFE.rb2610', 'price': 100.0},
    }))
    desk2.sent.clear()
    desk2.check_alerts()
    assert 'alert_fired' in [p['type'] for p in _patches(desk2.sent)]


def test_alerts_command_returns_list():
    desk = _desk()
    desk.handle(protocol.encode_command({
        'cmd': 'add_alert',
        'payload': {'symbol': 'SHFE.rb2610', 'price': 100.0, 'qty': 2},
    }))
    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'alerts',
                                         'payload': {'symbol': 'SHFE.rb2610'}}))
    patch = _patches(desk.sent)[-1]
    assert patch['type'] == 'alerts' and patch['items']
    assert patch['items'][-1]['qty'] == 2


# ------------------------------------------- 5) pylightcharts AlertDialog 面板
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
                    return f'window.al{index}'

                def __getattr__(self, item):
                    return f'window.al{index}.{item}'

            return Handle()

    _id_gen = _Gen()


def test_alert_dialog_panel_python():
    from pylightcharts.panels import AlertDialog

    window = FakeWin()
    dialog = AlertDialog(window, symbol='SHFE.rb2610', price=3600.0,
                         items=[{'id': 1, 'price': 3600.0}])
    assert 'new Lib.AlertDialog(' in window.scripts[0]
    assert '"symbol":"SHFE.rb2610"' in window.scripts[0]
    assert list(window.handlers) == [str(dialog.id)]

    window.scripts.clear()
    dialog.open()
    dialog.set_items([{'id': 2, 'price': 3610.0, 'fired': True}])
    dialog.set_theme('light')
    joined = '\n'.join(window.scripts)
    assert '.open()' in joined and '.setItems(' in joined
    assert '.setTheme("light")' in joined

    calls = []
    dialog.on_create(lambda payload: calls.append(('create', payload)))
    dialog.on_delete(lambda alert_id: calls.append(('delete', alert_id)))
    dialog._dispatch('create;;;{"price": 3600, "action": "买", "qty": 2}')
    dialog._dispatch('delete;;;7')
    assert calls[0][0] == 'create' and calls[0][1]['qty'] == 2
    assert calls[1] == ('delete', 7)


def test_alert_dialog_asset_built():
    source = _read(PANEL_TS / 'alert-dialog.ts')
    for key in ('export class AlertDialog', 'pylc-al-mask', 'setSymbol',
                'setPrice', 'setItems', 'setTheme', 'onCreateCallback'):
        assert key in source, key
    assert "export * from './alert-dialog';" in _read(PANEL_TS / 'index.ts')
    bundle = _read(REPO / 'pylightcharts' / 'js' / 'bundle.js')
    assert 'pylc-al-mask' in bundle
    desk_bundle = _read(REPO / 'pylightcharts' / 'js' / 'desk.js')
    assert 'pylc-al-mask' in desk_bundle       # desk 也打包进来了 ✓


# ---------------------------------------------------------- 6) 股票诊断
def test_stock_error_is_reported(monkeypatch):
    from minibt.desk import stocks

    class _Ctx:
        def get_stock_basicinfo(self, market, security_type):
            return -1, '缺少额度'

    class _Api:
        _RET_OK = 0
        _ctx = _Ctx()

    monkeypatch.setattr(stocks, 'last_error', '')
    assert stocks.basic_rows(_Api(), 'SSE') == []
    assert '缺少额度' in stocks.last_error or 'ret=' in stocks.last_error


def test_cli_check_reports_counts(capsys):
    from minibt import cli
    from minibt.desk.app import Desk

    class _Feed:
        kind = 'futures'
        api = None

        def contracts(self, ins_class, exchange):
            return ['SHFE.rb2610'] if exchange == 'SHFE' else []

    desk = Desk.__new__(Desk)
    desk.futures = _Feed()
    desk.stocks = _Feed()

    # `--check` 现在走 `stocks.probe()`（带 ret / 失败原因 ✓）
    import minibt.desk.stocks as stocks_mod
    original = stocks_mod.probe
    stocks_mod.probe = lambda api, market: {
        'market': market, 'count': 1 if market == 'SSE' else 0,
        'ret': 0, 'error': '',
        'example': 'SSE.600000' if market == 'SSE' else '',
    }
    try:
        code = cli.check(desk)
    finally:
        stocks_mod.probe = original
    out = capsys.readouterr().out
    assert code == 0
    assert 'SHFE.rb2610' in out and 'SSE.600000' in out
    assert '合约总数' in out


def test_cli_check_returns_2_when_empty(capsys):
    from minibt import cli
    from minibt.desk.app import Desk

    class _Feed:
        kind = 'futures'
        api = None

        def contracts(self, *args):
            return []

    desk = Desk.__new__(Desk)
    desk.futures = _Feed()
    desk.stocks = _Feed()

    import minibt.desk.stocks as stocks_mod
    original = stocks_mod.probe
    stocks_mod.probe = lambda api, market: {
        'market': market, 'count': 0, 'ret': -1,
        'error': '缺少额度', 'example': '',
    }
    try:
        assert cli.check(desk) == 2
    finally:
        stocks_mod.probe = original
    assert '没有数据' in capsys.readouterr().out
