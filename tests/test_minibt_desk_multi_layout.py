"""多布局持仓线 / 挂单线、策略管理、全平、交易面板价格的回归用例。

用户 2026-10-26 反馈（都会直接导致「模拟账户明明有仓，图上没有」）：

1. 多布局里**只有第 1 格**有持仓线 / 挂单线；
2. 加了策略后点「指标 → 策略布局」报
   ``AttributeError: 'list' object has no attribute 'get'``
   （``layout['cells']`` 是 list，旧代码当 dict 用）；
3. 右键「全」（全平）提示「全部平仓：N 个合约」，实际一手都没平
   —— 天勤持仓里的 ``instrument_id`` 只有 ``ag2612``（**没有交易所**），
   拿去建 ``TargetPosTask`` 直接报 ``contains non-existent instrument``；
4. 点第 2/3 格时，交易面板的**价格框**还是上一个合约的价格。
"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding='utf-8')


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.log_to_stdout = False
    desk.log_to_ui = False
    return desk


# ---------------------------------------------------------------- 全平
class _PosRow:
    """天勤 `get_position_list()` 里的一条（`instrument_id` 没有交易所 ✓）"""

    def __init__(self, instrument_id, exchange_id, long=1, short=0):
        self.instrument_id = instrument_id
        self.exchange_id = exchange_id
        self.pos_long = long
        self.pos_short = short


def test_position_symbol_adds_exchange():
    from minibt.desk.accounts import position_symbol
    assert position_symbol(_PosRow('ag2612', 'SHFE')) == 'SHFE.ag2612'
    assert position_symbol(_PosRow('SHFE.ag2612', 'SHFE')) == 'SHFE.ag2612'
    assert position_symbol(_PosRow('600000', 'SSE')) == 'SSE.600000'


def test_close_all_uses_full_symbols(tmp_path, monkeypatch):
    """全平必须拿 `SHFE.ag2612` 去调仓（裸 `ag2612` 会被天勤拒掉 ✗）"""
    desk = _desk(tmp_path, monkeypatch)
    trader = desk.trading_view()
    rows = [_PosRow('ag2612', 'SHFE'), _PosRow('a2701', 'DCE', short=2)]
    trader._positions = lambda: rows                      # 假持仓 ✓
    calls = []
    trader._set_target = lambda symbol, target: (
        calls.append((symbol, target)) or f'{symbol} → {target}')
    text = trader._close_all()
    assert '全部平仓' in text
    assert calls == [('SHFE.ag2612', 0), ('DCE.a2701', 0)]


def test_positions_table_shows_full_symbols(tmp_path, monkeypatch):
    """持仓表 / 委托表里的代码也必须带交易所（右键平仓才发得出去 ✓）"""
    desk = _desk(tmp_path, monkeypatch)

    class _Api:
        def get_position_list(self):
            return [_PosRow('ag2612', 'SHFE')]

        def get_position(self, *a, **k):
            return None

    view = desk.account_view()
    view.api = lambda symbol='': _Api()
    view.decimals_of = lambda symbol, default=2: 1
    payload = view.tables(50, '')
    codes = [row[0] for row in
             ((payload.get('positions') or {}).get('rows') or [])]
    assert 'SHFE.ag2612' in codes
    assert 'ag2612' not in codes


# ---------------------------------------------------------------- 策略管理
def test_strategy_manage_rows_handles_list_cells(tmp_path, monkeypatch):
    """`layout.cells` 是 **list** → 以前 `cells.get(...)` 直接 AttributeError ✗"""
    desk = _desk(tmp_path, monkeypatch)
    desk.tabs['SHFE.ag2612'] = {
        'strategy': {'name': 'test1', 'path': '/tmp/x.py'},
        'strategy_items': [{'key': 'st:test1:0', 'label': 'a'}],
        'layout': {'cols': 2, 'rows': 1,
                   'symbols': ['SHFE.ag2612', 'SHFE.au2612'],
                   'cells': [{'symbol': 'SHFE.ag2612', 'indicators': []},
                             {'symbol': 'SHFE.au2612', 'indicators': [],
                              'strategy_items': [{'key': 'st:test1:1'}],
                              'strategy': {'name': 'test1'}}]},
    }
    rows = desk._strategy_manage_rows()
    assert [row['cell'] for row in rows] == [0, 1]
    assert rows[1]['symbol'] == 'SHFE.au2612'
    assert rows[1]['name'] == 'test1'
    assert rows[1]['lines'] == 1


def test_strategy_manage_rows_handles_dict_cells(tmp_path, monkeypatch):
    """老格式（dict）也不能挂 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    desk.tabs['SHFE.ag2612'] = {
        'strategy': {'name': 's'},
        'layout': {'symbols': ['SHFE.ag2612', 'SHFE.au2612'],
                   'cells': {'1': {'symbol': 'SHFE.au2612',
                                   'strategy': {'name': 's2'}}}},
    }
    rows = desk._strategy_manage_rows()
    assert [row['cell'] for row in rows] == [0, 1]
    assert rows[1]['name'] == 's2'


# ---------------------------------------------------------------- 多格持仓线
def test_each_cell_gets_position_and_orders(tmp_path, monkeypatch):
    """多布局：第 2..N 格也要推持仓线 / 挂单线（带 `cell` ✓）"""
    desk = _desk(tmp_path, monkeypatch)
    pushed = []
    desk.push = lambda patch: pushed.append(patch)
    desk.position_payload = lambda symbol, feed=None: {
        'type': 'position', 'symbol': symbol, 'long': None, 'short': None}
    desk.orders_payload = lambda symbol, local=False: {
        'type': 'orders', 'symbol': symbol, 'items': []}
    info = {'cycle': 60,
            'layout': {'cols': 2, 'rows': 1,
                       'symbols': ['DCE.a2701', 'DCE.m2701'],
                       'cells': [{'symbol': 'DCE.a2701'},
                                 {'symbol': 'DCE.m2701'}]}}
    desk.filter = {'type': 'FUT', 'exchange': 'DCE'}
    desk._push_cell_bars('DCE.a2701', info)
    cells = {(item['type'], item.get('cell')) for item in pushed}
    assert ('position', 1) in cells
    assert ('orders', 1) in cells
    # 主 tab 路由用 `symbol`，但持仓/挂单是**第 2 格自己的合约** ✓
    position = [item for item in pushed if item['type'] == 'position'][0]
    assert position['symbol'] == 'DCE.m2701'


def test_push_orders_can_target_a_cell(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    pushed = []
    desk.push = lambda patch: pushed.append(patch)
    desk.orders_payload = lambda symbol, local=False: {
        'type': 'orders', 'symbol': symbol, 'items': []}
    desk._push_orders('DCE.a2701', cell=0)
    assert pushed[0]['cell'] == 0


# ---------------------------------------------------------------- 泵异常
def test_pump_does_not_purge_bare_codes(tmp_path, monkeypatch):
    """裸代码（`ag2612`）不能按后缀删掉合法合约 `SHFE.ag2612` ✗"""
    desk = _desk(tmp_path, monkeypatch)
    desk._last_rows = {'SHFE.ag2612': {'symbol': 'SHFE.ag2612'}}
    desk._purge_bad_symbol('ag2612')
    assert 'SHFE.ag2612' in desk._last_rows
    desk._purge_bad_symbol('SHFE.ag2612')
    assert 'SHFE.ag2612' not in desk._last_rows


def test_contract_exists_distinguishes_bare_codes(tmp_path, monkeypatch):
    """裸代码报错要先查合约字典：真有 `SHFE.ag2612` 就不该拉黑它 ✓"""
    desk = _desk(tmp_path, monkeypatch)

    class _Api:
        _data = {'symbols': {'SHFE.ag2612': {}, 'DCE.a2701': {}}}

    class _Feed:
        api = _Api()

    desk.futures = _Feed()
    assert desk._contract_exists('ag2612') is True
    assert desk._contract_exists('SHFE.ag2612') is True
    assert desk._contract_exists('rb2701') is False       # 真不存在 → 拉黑 ✓


def test_feed_valid_symbol_blocks_blacklisted_contracts():
    from minibt.desk.feeds import FuturesFeed
    feed = FuturesFeed.__new__(FuturesFeed)
    feed._bad_symbols = {'SHFE.rb2701'}
    assert feed.valid_symbol('SHFE.rb2701') is False
    assert feed.valid_symbol('SHFE.rb2610') is True
    # 裸代码（真的不存在）也要挡住对应的完整合约（天勤报错只给裸代码 ✓）
    feed._bad_symbols = {'rb2701'}
    assert feed.valid_symbol('SHFE.rb2701') is False
    assert feed.valid_symbol('SHFE.rb2610') is True


# ---------------------------------------------------------------- 价格框
def test_trade_symbol_updates_ticket_price():
    """点第 2 格 → 价格框换成那一格的最新价（并恢复“跟随最新价” ✓）"""
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'resetPrice?: (value: number | null) => void;' in page
    assert 'private _priceOfSymbol(symbol: string): number | null {' in page
    assert 'this._priceOfSymbol(symbol)' in page
    ticket = _read('jslib/src/desk/replay-ticket.ts')
    assert 'resetPrice: (price: number | null) => void;' in ticket
    assert 'resetPrice: (value: number | null) => {' in ticket
    # 价格框跟随当前交易标的的最新价（用户手填过不覆盖 ✓）
    assert 'if (data.symbol === target)' in page or \
        'if (!data.symbol || data.symbol === target)' in page


def test_multi_cell_position_and_orders_wiring():
    page = _read('jslib/src/desk/chart-page.ts')
    app = _read('jslib/src/desk/app.ts')
    # 每格各一份持仓线 / 挂单线（含左侧色块的格号 ✓）
    assert 'positionLinesByCell' in page
    assert 'orderLinesByCell' in page
    assert "badge.dataset.cell = String(cell);" in page
    assert 'page.setPosition(sides, typeof patch.cell === \'number\'' in app
    assert 'page.setOrders(items, typeof patch.cell === \'number\'' in app


def test_remove_strategy_clears_all_layout_cells(tmp_path, monkeypatch):
    """删策略必须把多布局每格的策略线都清掉（不能只清格 1）✓"""
    desk = _desk(tmp_path, monkeypatch)
    pushed = []
    desk.push = lambda patch: pushed.append(patch)
    desk.indicator_payload = lambda symbol, frame=None: {
        'type': 'indicator', 'symbol': symbol, 'items': []}
    info = {
        'strategy': {'name': 'Pair'},
        'strategy_items': [{'key': 'editor:Pair:line:0'}],
        'strategy_runner': object(),
        'strategy_config': {'run_next': True},
        'layout': {
            'symbols': ['SHFE.ag2612', 'SHFE.au2612'],
            'cells': [{'symbol': 'SHFE.ag2612'},
                      {'symbol': 'SHFE.au2612'}],
        },
    }
    desk.tabs['SHFE.ag2612'] = info
    assert desk._remove_strategy_of('SHFE.ag2612') is True
    assert not info.get('strategy_items')
    assert 'strategy_runner' not in info
    cell_patches = [item for item in pushed
                    if item.get('type') == 'indicator'
                    and item.get('cell') == 1]
    assert cell_patches
    assert cell_patches[0]['items'] == []
    assert cell_patches[0]['strategyOnly'] is True


def test_remove_local_strategy_clears_every_contract_cell(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    pushed = []
    desk.push = lambda patch: pushed.append(patch)
    desk._local_indicator_payload = lambda name, cell=0: {
        'type': 'local_indicator', 'symbol': name, 'cell': cell, 'items': []}
    desk._local_strategies = {
        'ag2612_60': {'name': 'Pair', 'path': 'p.py', 'items': [{}]},
        'au2612_60': {'name': 'Pair', 'path': 'p.py', 'items': [{}]},
    }
    desk._local_strategy_of = {'ag2612_60': 'Pair', 'au2612_60': 'Pair'}
    desk._local_cell_names = {0: 'ag2612_60', 1: 'au2612_60'}
    assert desk._remove_local_strategy('ag2612_60') is True
    assert desk._local_strategies == {}
    assert desk._local_strategy_of == {}
    assert {item['symbol'] for item in pushed} == {'ag2612_60', 'au2612_60'}


def test_position_line_falls_back_to_last_price_when_avg_missing(
        tmp_path, monkeypatch):
    """持仓成本字段为 NaN/0 时也要画持仓线（用最新价兜底）✓"""
    desk = _desk(tmp_path, monkeypatch)
    desk._last_rows = {'SHFE.ag2612': {'last': 7000.0}}

    class Row:
        pos_long = 1
        pos_short = 0
        open_price_long = float('nan')
        position_price_long = float('nan')
        float_profit_long = 0.0

    class Api:
        def get_position(self, symbol):
            return Row()

    class Feed:
        api = Api()

    payload = desk.position_payload('SHFE.ag2612', Feed())
    assert payload['long']['volume'] == 1
    assert payload['long']['avg'] == 7000.0


def test_indicator_delete_uses_tab_symbol_not_cell_symbol():
    """看盘窗口删第 2 格指标时，后端必须按 tab 主合约定位 ✓"""
    page = _read('jslib/src/desk/chart-page.ts')
    block = page.split('removeIndicator(source: string', 1)[1].split(
        '// 本格立即先撤掉', 1)[0]
    assert 'symbol: this.options.symbol, key: source, cell' in block
    assert 'symbolForCell(cell)' not in block


def test_resolve_tab_symbol_finds_layout_cell(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.tabs['SHFE.ag2612'] = {
        'layout': {'symbols': ['SHFE.ag2612', 'SHFE.au2612'],
                   'cells': [{'symbol': 'SHFE.ag2612'},
                             {'symbol': 'SHFE.au2612'}]},
    }
    assert desk._resolve_tab_symbol('SHFE.au2612') == 'SHFE.ag2612'
    assert desk._resolve_tab_symbol('SHFE.ag2612') == 'SHFE.ag2612'
    assert desk._resolve_tab_symbol('SHFE.other') == 'SHFE.other'


def test_position_payload_uses_selected_account(tmp_path, monkeypatch):
    """多账户：持仓线查的账户必须和账户面板选中的一致 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    calls = []

    class Row:
        pos_long = 1
        pos_short = 0
        sell_price_long = 0
        position_price_long = 7000.0
        float_profit_long = 0.0

    class Api:
        def get_position(self, symbol, **kwargs):
            calls.append(kwargs)
            return Row()

    class Feed:
        api = Api()

    class View:
        def account_kwargs(self, symbol=''):
            return {'account': 'SELECTED'}

    monkeypatch.setattr(desk, 'account_view', lambda: View())
    payload = desk.position_payload('SHFE.ag2612', Feed())
    assert payload['long']['volume'] == 1
    assert calls and calls[0].get('account') == 'SELECTED'


def test_realtime_layout_saves_all_cells_styles_and_strategy(
        tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    path = str(tmp_path / 'live_pair.py')
    (tmp_path / 'live_pair.py').write_text('x = 1\n', encoding='utf-8')
    style = {
        'key': 'MA', 'params': {'length': 10}, 'color': '#abcdef',
        'lineWidth': 3, 'visible': False, 'overlay': False,
    }
    info = {
        'cycle': 60,
        'strategy': {'name': 'LivePair', 'path': path},
        'indicators': [dict(style)],
        'layout': {
            'cols': 2, 'rows': 1,
            'symbols': ['SHFE.ag2612', 'SHFE.au2612'],
            'cells': [
                {'symbol': 'SHFE.ag2612', 'indicators': [dict(style)]},
                {'symbol': 'SHFE.au2612', 'indicators': [
                    {'key': 'MACD', 'params': {}, 'color': '#123456',
                     'lineWidth': 2, 'visible': True}]},
            ],
        },
    }
    desk.tabs['SHFE.ag2612'] = info
    cells = desk._layout_cells('SHFE.ag2612')
    assert len(cells) == 2
    assert cells[1]['indicators'][0]['key'] == 'MACD'
    desk._on_layout_save({
        'symbol': 'SHFE.ag2612', 'name': 'RT',
        'cols': 2, 'rows': 1, 'cycle': 60,
        'cells': cells,
    })
    from minibt.desk import user_prefs
    record = next(item for item in user_prefs.layouts()
                  if item['name'] == 'RT')
    first = record['cells'][0]['indicators'][0]
    second = record['cells'][1]['indicators'][0]
    assert first['color'] == '#abcdef'
    assert first['lineWidth'] == 3
    assert first['visible'] is False
    assert second['key'] == 'MACD'
    assert second['color'] == '#123456'
    assert record['cells'][0]['strategy']['path'] == path


def test_realtime_layout_save_frontend_sends_cells():
    page = _read('jslib/src/desk/chart-page.ts')
    block = page.split('openSaveLayout(): void {', 1)[1].split(
        'openLayoutManager(): void', 1)[0]
    assert 'indicators: rows.map' in block
    assert 'layer?.styleOf?.(key)' in block
    assert 'visible: style.visible' in block
    assert 'cells,' in block
