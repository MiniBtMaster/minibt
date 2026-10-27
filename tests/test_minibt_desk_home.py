"""首页（方案 B）+ 离线/在线初始化路由的回归测试。"""
from __future__ import annotations

from pathlib import Path


from minibt.desk.app import Desk
from minibt.desk.symbols import row

ROOT = Path(__file__).resolve().parents[1]
JSLIB = ROOT / 'jslib' / 'src' / 'desk'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


class FakeFeed:
    def __init__(self, kind: str = 'futures', price: float = 100.0):
        self.kind = kind
        self.api = object()
        self.price = price
        self._names = {}

    def available(self) -> bool:
        return True

    def quotes(self, symbols):
        return [dict(
            row(symbol=symbol, name='测试', last=self.price,
                chg_pct=1.2, volume=12000, decimals=2, price_tick=0.01),
            spark=[1, 2, 3, 4],
        ) for symbol in symbols]

    def klines(self, *args, **kwargs):
        return None

    def name_of(self, symbol):
        return ''


def _desk_with(feed: FakeFeed) -> Desk:
    desk = Desk()
    desk.feeds = [feed]
    if feed.kind == 'futures':
        desk.futures = feed
    else:
        desk.stocks = feed
    desk._spark = {
        symbol: [1, 2, 3]
        for symbol in (
            'KQ.m@CFFEX.IF', 'KQ.m@CFFEX.IM', 'KQ.m@SHFE.rb',
            'KQ.m@SHFE.cu',
        )
    }
    desk.home_account = lambda: {
        'kind': feed.kind,
        'label': '快期模拟' if feed.kind == 'futures' else '富途账户',
        'values': {'balance': 100.0, 'available': 80.0,
                   'position_profit': 2.0, 'risk_ratio': 0.2},
    }
    return desk


def test_home_prefers_futures_when_both_connected():
    futures = FakeFeed('futures', 100.0)
    stocks = FakeFeed('stocks', 20.0)
    desk = _desk_with(futures)
    desk.stocks = stocks
    desk.feeds = [futures, stocks]

    payload = desk.home_payload()

    assert payload['type'] == 'home'
    assert payload['source'] == 'futures'
    assert payload['markets']['futures'] is True
    assert payload['markets']['stocks'] is True
    assert len(payload['indices']) == 4
    # P101：自选默认**空**（除收藏 / 最近打开外都由用户自己加 ✓）
    assert payload['watchlist'] == []
    assert payload['account']['label'] == '快期模拟'
    assert 1 <= len(payload['signals']) <= 3
    assert payload['events']


def test_home_uses_stocks_when_only_stocks_connected():
    stocks = FakeFeed('stocks', 20.0)
    desk = _desk_with(stocks)

    payload = desk.home_payload()

    assert payload['source'] == 'stocks'
    assert payload['markets']['futures'] is False
    assert payload['watchlist'] == []           # 同上：默认空 ✓
    assert payload['account']['label'] == '富途账户'


def test_home_no_service_is_empty_and_does_not_fake_rows():
    desk = Desk()
    desk.no_service = True

    payload = desk.home_payload()

    assert payload['empty'] is True
    assert payload['indices'] == []
    assert payload['watchlist'] == []
    assert desk.market_map()['offline'] is True
    assert desk.market_map()['no_service'] is True
    assert desk.status()['offline'] is True


def test_home_commands_are_registered_and_custom_symbols_work():
    desk = _desk_with(FakeFeed('futures'))
    patches = []
    desk.sender = lambda script: patches.append(script)
    desk._booted = True

    assert 'home' in desk.commands()
    assert 'home_refresh' in desk.commands()
    assert 'home_symbols' in desk.commands()

    desk.handle('desk_~_{"cmd":"home","payload":{"active":true}}')
    assert desk._home_active is True
    assert any('"type":"home"' in item for item in patches)

    patches.clear()
    desk.handle('desk_~_{"cmd":"home_symbols",'
                '"payload":{"symbols":["KQ.m@SHFE.rb"]}}')
    assert any('"type":"home_symbols"' in item for item in patches)
    assert any('KQ.m@SHFE.rb' in item for item in patches)


def test_frontend_initial_route_and_lazy_quote():
    app = _read(JSLIB / 'app.ts')
    home = _read(JSLIB / 'home-page.ts')
    css = _read(JSLIB / 'desk.css')

    assert "const HOME_TAB_ID = '__home'" in app
    assert 'private _routeInitial()' in app
    assert 'pendingLocalAutoLoad' in app
    assert "this.send('home', { active: true })" in app
    assert 'private _ensureQuoteTab()' in app
    assert 'openQuote(): void' in app
    assert 'quoteQueue' in app
    assert 'desk-tab-new' in app
    assert '+ 新建' in app or '新建' in app
    assert '最近打开' in home and '收藏' in home and '新建分组' in home
    assert 'home_symbols' in home
    assert '.desk-home-shell' in css
    assert '.desk-home-side' in css and '.desk-home-right' in css


def test_desk_default_window_title_and_quote_tab():
    """窗口 / 浏览器标题 = minibt桌面端；行情报价页签仍叫「行情报价」✓"""
    import inspect
    from minibt.desk import protocol
    from minibt.desk.app import Desk

    assert inspect.signature(Desk.__init__).parameters['title'].default == (
        'minibt桌面端')
    assert protocol.patch_boot()['title'] == 'minibt桌面端'
    cli = _read(ROOT / 'minibt' / 'cli.py')
    assert "default='minibt桌面端'" in cli
    html = _read(JSLIB / 'desk.html')
    assert '<title>minibt桌面端</title>' in html
    app = _read(JSLIB / 'app.ts')
    # title 只改窗口 / 浏览器标题；报价页签名称保持「行情报价」
    assert "label: '行情报价'" in app
    assert 'document.title = String(patch.title)' in app
    assert "tab.label = patch.title" not in app


def test_add_menu_has_local_sim_account_entry():
    app = _read(JSLIB / 'app.ts')
    assert "label: '本地模拟账户…'" in app
    assert "this.openSettings('sim')" in app


def test_offline_start_stays_on_local_chart():
    """P79：离线**只开本地图表**（首页收起，`openHome()` 再拿回来 ✓）"""
    app = _read(JSLIB / 'app.ts')
    route = app.split('private _routeInitial()', 1)[1].split(
        'private _ensureQuoteTab', 1)[0]
    assert '_dropHome()' in route
    assert 'openLocalChart()' in route
    assert 'openHome()' in app
    # 首页页签永远不带关闭按钮 ✓
    assert "if (id === HOME_TAB_ID) return;" in app
    # 首页之外所有页签都可关闭（P89 起统一成 `tab.kind !== 'home'` ✓）
    assert "if (tab.kind !== 'home') {" in app


def test_account_summary_has_label_for_home():
    # AccountView.summary 需要给首页一个可读账户名 ✓
    source = _read(ROOT / 'minibt' / 'desk' / 'accounts.py')
    assert "'label': labels[self.index]" in source


def test_no_service_flush_pushes_offline_skeleton_only():
    """P76：离线也推 chips / 表头骨架（报价页能打开），但**不推假行情** ✓"""
    desk = Desk()
    desk.no_service = True
    patches = []
    desk.sender = lambda script: patches.append(script)
    desk.flush()
    assert any('离线 · 本地数据' in item for item in patches)
    assert any('"type":"types"' in item for item in patches)
    assert any('"type":"exchanges"' in item for item in patches)
    assert any('"type":"rows_loading"' in item for item in patches)
    assert not any('"type":"rows"' in item for item in patches)
    assert desk._rows_for_filter() == []          # 没有缓存 → 空表 ✓


def test_default_realtime_uses_first_shfe_main_contract():
    """「＋ → 实时图表」默认打开主力 / 上期所第一个合约 ✓"""
    desk = _desk_with(FakeFeed('futures'))
    desk.symbol_index = lambda: [
        {'symbol': 'KQ.m@CFFEX.IF', 'type': 'CONT_MAIN',
         'exchange': 'CFFEX', 'name': '沪深'},
        {'symbol': 'SHFE.rb2612', 'type': 'CONT_MAIN',
         'exchange': 'SHFE', 'name': '螺纹钢主力'},
        {'symbol': 'SHFE.cu2612', 'type': 'CONT_MAIN',
         'exchange': 'SHFE', 'name': '沪铜主力'},
    ]
    pushes = []
    desk.push = lambda patch: pushes.append(patch)
    desk._on_default_realtime()
    assert pushes[-1] == {'type': 'default_realtime',
                          'symbol': 'SHFE.rb2612',
                          'name': '螺纹钢主力'}


def test_default_realtime_without_tq_is_blank():
    desk = _desk_with(FakeFeed('futures'))
    desk.futures = None
    pushes = []
    desk.push = lambda patch: pushes.append(patch)
    desk._on_default_realtime()
    assert pushes[-1]['symbol'] == ''


def test_realtime_default_frontend_command():
    app = _read(JSLIB / 'app.ts')
    assert 'default_realtime' in app
    assert 'pendingRealtime' in app
    assert '_openBlankChartFallback' in app
