"""P26：看盘页商品搜索改成全市场（miniqt 样式）✓"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


class _Futures:
    kind = 'futures'
    api = None

    def available(self):
        return True

    def contracts(self, kind, exchange):
        if kind != 'FUT':
            return []
        return {'SHFE': ['SHFE.rb2610'], 'CFFEX': ['CFFEX.IC2009'],
                'DCE': ['DCE.m2609']}.get(exchange, [])

    def fill_names(self, names):
        return None

    def name_of(self, symbol):
        return {'SHFE.rb2610': '螺纹钢2610', 'CFFEX.IC2009': '中证2009',
                'DCE.m2609': '豆粕2609'}.get(symbol, '')

    def quotes(self, keys):
        return []

    def spec(self, symbol):
        return None


class _Stocks:
    kind = 'stocks'
    api = None

    def available(self):
        return True

    def stock_rows(self, market):
        return {
            'SSE': [{'symbol': 'SSE.600000', 'name': '浦发银行'}],
            'HK': [{'symbol': 'HK.00700', 'name': '腾讯控股'}],
            'US': [{'symbol': 'US.AAPL', 'name': 'Apple'}],
            'SZSE': [{'symbol': 'SZSE.000001', 'name': '平安银行'}],
        }.get(market, [])

    def name_of(self, symbol):
        return ''

    def quotes(self, keys):
        return []

    def spec(self, symbol):
        return None


def _index(tmp_path, monkeypatch):
    from minibt.desk import symbol_index as module

    monkeypatch.setattr(module, 'INDEX_FILE',
                        str(tmp_path / 'index.sqlite3'))
    return module


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.delenv('MINIBT_DESK_NO_INDEX', raising=False)   # 本文件要测索引 ✓
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.futures = _Futures()
    desk.stocks = _Stocks()
    desk.feeds = [desk.futures, desk.stocks]
    desk.offline = False
    return desk


# ------------------------------------------------------------ 索引文件
def test_index_save_load_search(tmp_path, monkeypatch):
    idx = _index(tmp_path, monkeypatch)
    assert idx.stale()                             # 没有文件 → 过期 ✓
    rows = [{'symbol': 'SHFE.rb2610', 'name': '螺纹钢', 'exchange': 'SHFE',
             'type': 'FUT', 'market': '上期所'},
            {'symbol': 'HK.00700', 'name': '腾讯控股', 'exchange': 'HK',
             'type': 'STOCK', 'market': '港股'}]
    assert idx.save(rows)
    assert not idx.stale()
    loaded = idx.load()
    assert len(loaded) == 2
    assert loaded[0]['type_label'] == '期货'
    assert [row['symbol'] for row in idx.search(loaded, 'rb')] == [
        'SHFE.rb2610']
    assert [row['symbol'] for row in idx.search(loaded, '腾讯')] == ['HK.00700']
    assert idx.search(loaded, '') == []            # 空输入不刷全表 ✓
    assert [row['symbol'] for row in idx.search(loaded, '00', 'STOCK')] == [
        'HK.00700']
    assert idx.search(loaded, '00', 'FUT') == []


def test_index_markets_payload():
    from minibt.desk import symbol_index as idx

    keys = [item['key'] for item in idx.markets_payload()]
    labels = [item['label'] for item in idx.markets_payload()]
    assert keys[0] == '' and labels[0] == '全部'
    for key in ('FUT', 'CONT_MAIN', 'INDEX', 'OPTION', 'STOCK'):
        assert key in keys


# ------------------------------------------------------------ 全市场构建
def test_build_covers_all_markets(tmp_path, monkeypatch):
    idx = _index(tmp_path, monkeypatch)
    rows = idx.build([_Futures(), _Stocks()])
    symbols = {row['symbol'] for row in rows}
    assert {'SHFE.rb2610', 'CFFEX.IC2009', 'DCE.m2609'} <= symbols
    assert {'SSE.600000', 'SZSE.000001', 'HK.00700', 'US.AAPL'} <= symbols
    kinds = {row['type'] for row in rows}
    assert kinds == {'FUT', 'STOCK'}
    # 已落盘 → 再 load 还在 ✓
    assert len(idx.load()) == len(rows)


# ------------------------------------------------------------ 搜索跨市场
def test_search_crosses_market_filter(tmp_path, monkeypatch):
    """用户反馈的重点：报价页停在期货/上期所，也能搜到港股 / 美股 ✓"""
    from minibt.desk import protocol

    idx = _index(tmp_path, monkeypatch)
    idx.save(idx.build([_Futures(), _Stocks()]))
    desk = _desk(tmp_path, monkeypatch)
    desk._symbol_rows = idx.load()
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}

    def search(text, market=''):
        desk.sent.clear()
        desk.handle(protocol.encode_command({
            'cmd': 'symbol_search',
            'payload': {'text': text, 'market': market},
        }))
        patch = [json.loads(row[len('window.__desk.applyPatch('):-2])
                 for row in desk.sent if '"type":"symbol_search"' in row][-1]
        return patch

    patch = search('00700')
    assert [item['symbol'] for item in patch['items']] == ['HK.00700']
    assert patch['items'][0]['type_label'] == '股票'
    assert len(patch['markets']) >= 6              # chips ✓
    assert patch['total'] == 7   # 3 个期货 + 4 个股票 ✓

    assert [item['symbol'] for item in search('aapl')['items']] == ['US.AAPL']
    assert [item['symbol'] for item in search('rb')['items']] == ['SHFE.rb2610']
    # 市场筛选
    assert {item['type'] for item in search('00', 'STOCK')['items']} == {'STOCK'}
    assert {item['type'] for item in search('00', 'FUT')['items']} == {'FUT'}
    assert search('00', 'FUT')['market'] == 'FUT'


def test_build_pushes_symbol_index_patch(tmp_path, monkeypatch):
    idx = _index(tmp_path, monkeypatch)
    desk = _desk(tmp_path, monkeypatch)
    desk.refresh_symbol_index(force=True)
    while getattr(desk, '_symbol_building', False):
        desk._index_step()
    patches = [json.loads(row[len('window.__desk.applyPatch('):-2])
               for row in desk.sent if '"type":"symbol_index"' in row]
    assert patches and patches[-1]['count'] == 7
    assert desk._symbol_rows and desk._symbol_building is False
    logs = [row for row in desk.sent if '"type":"log"' in row]
    assert any('合约索引已更新' in str(row) for row in logs)


# ------------------------------------------------------------ 前端
def test_symbol_search_panel_has_markets_and_badges():
    panel = _read('jslib/src/panels/symbol-search.ts')
    for key in ('export interface SearchMarket', 'pylc-ss-chip',
                'onMarketCallback', 'setMarkets(', 'pylc-ss-badge',
                'type_label', 'badgeColor('):
        assert key in panel, key


def test_chart_page_sends_market_and_total():
    page = _read('jslib/src/desk/chart-page.ts')
    assert "this.options.onCommand?.('symbol_search', {" in page
    assert 'market: this.searchMarket' in page
    assert 'setSearchMarkets(' in page
    assert '全市场 ${total} 个合约' in page
    app = _read('jslib/src/desk/app.ts')
    assert "case 'symbol_index'" in app
    assert 'Number(patch.total || 0)' in app


def test_quote_chips_can_be_resent_after_reopen(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.sent.clear()
    desk.filter.update({'type': 'FUT', 'exchange': 'SHFE'})
    desk._on_quote_chips({})
    patches = [json.loads(row[len('window.__desk.applyPatch('):-2])
               for row in desk.sent]
    assert any(patch.get('type') == 'types' for patch in patches)
    assert any(patch.get('type') == 'exchanges' for patch in patches)
