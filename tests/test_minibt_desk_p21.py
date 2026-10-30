"""P21：气泡 / 持仓表 / 播放条 / 预警 也用 decimals + 筛选记忆 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'
PANEL_TS = ROOT / 'jslib' / 'src' / 'panels'


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


def _desk(tmp_path, monkeypatch, **last_rows):
    from minibt.desk import user_prefs
    from minibt.desk.app import Desk

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk._last_rows = {key: {'price_tick': value}
                       for key, value in last_rows.items()}
    return desk


# ------------------------------------------------------------ decimals_of
def test_decimals_of_uses_quote_row(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch, **{'SHFE.rb2610': 1.0,
                                           'SHFE.au2612': 0.02})
    assert desk.decimals_of('SHFE.rb2610') == 0
    assert desk.decimals_of('SHFE.au2612') == 2
    # 持仓里给的是不带交易所的代码 → 也要能对上 ✓
    assert desk.decimals_of('rb2610') == 0
    # 未知合约 → 默认 2（股票）
    assert desk.decimals_of('X.none') == 2
    # 缓存生效（改 tick 不再影响，直到重启）
    desk._last_rows['SHFE.rb2610']['price_tick'] = 0.5
    assert desk.decimals_of('SHFE.rb2610') == 0


# ------------------------------------------------------------ 持仓 / 委托 / 成交表
class _Api:
    def get_position_list(self):
        return [{'instrument_id': 'SHFE.rb2610', 'pos_long': 2,
                 'open_price_long': 3600.5, 'position_profit_long': 120.0,
                 'margin': 36005.0}]

    def get_order(self, **_kwargs):
        return [{'instrument_id': 'SHFE.au2612', 'direction': 'BUY',
                 'offset': 'OPEN', 'volume_orign': 1, 'volume_left': 1,
                 'limit_price': 456.32, 'status': 'ALIVE',
                 'trade_price': 456.0}]

    def get_trade(self, **_kwargs):
        return [{'instrument_id': 'SHFE.au2612', 'direction': 'BUY',
                 'offset': 'OPEN', 'price': 456.32, 'volume': 1,
                 'commission': 10.0, 'trade_date_time': 1}]


def test_account_tables_use_contract_decimals(tmp_path, monkeypatch):
    from minibt.desk.accounts import AccountView

    desk = _desk(tmp_path, monkeypatch, **{'SHFE.rb2610': 1.0,
                                           'SHFE.au2612': 0.02})
    view = AccountView(desk)
    view.api = lambda symbol='': _Api()
    tables = view.tables()
    position = tables['positions']['rows'][0]
    assert position[4] == '3,600'            # 开仓价（tick 1 → 0 位）
    assert position[5] == '3,600'            # 持仓均价
    assert position[6] == '120.00'           # 盈亏还是 2 位 ✓
    order = tables['orders']['rows'][0]
    assert order[5] == '456.32'              # 报单价（tick 0.02 → 2 位）
    trade = tables['trades']['rows'][0]
    assert trade[3] == '456.32'              # 成交价


def test_account_tables_fallback_without_tick(tmp_path, monkeypatch):
    from minibt.desk.accounts import AccountView

    desk = _desk(tmp_path, monkeypatch)      # 没有任何报价行 → 默认 2 位
    view = AccountView(desk)
    view.api = lambda symbol='': _Api()
    row = view.tables()['positions']['rows'][0]
    assert row[4] == '3,600.50'


# ------------------------------------------------------------ 气泡 / 播放条 / 预警
def test_preview_patch_carries_decimals(tmp_path, monkeypatch):
    from minibt.desk import protocol

    desk = _desk(tmp_path, monkeypatch, **{'SHFE.rb2610': 1.0})
    desk._last_rows['SHFE.rb2610'].update({'symbol': 'SHFE.rb2610',
                                          'last': 3600.0})
    desk.handle(protocol.encode_command({
        'cmd': 'row_click',
        'payload': {'symbol': 'SHFE.rb2610', 'name': 'rb', 'x': 10, 'y': 10},
    }))
    patches = [p for p in desk.sent if '"preview"' in str(p)]
    assert patches, '没有 preview 补丁'
    assert '"decimals":0' in str(patches[-1]).replace(' ', '')


def test_alert_view_has_decimals(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch, **{'SHFE.rb2610': 1.0})
    view = desk._alert_view({'id': 1, 'symbol': 'SHFE.rb2610', 'price': 3600})
    assert view['decimals'] == 0


def test_ticker_and_preview_frontend_use_decimals():
    preview = _read('jslib/src/desk/symbol-preview.ts')
    assert 'decimals?: number | null;' in preview
    assert 'text(data.last, decimals)' in preview
    assert '_decimals(data)' in preview
    ticker = _read('jslib/src/panels/ticker.ts')
    assert 'decimals?: number | null;' in ticker
    assert 'this._format(item.last, item.decimals)' in ticker
    alert = _read('jslib/src/panels/alert-dialog.ts')
    assert 'setDecimals(' in alert and 'private _fmt(' in alert
    assert 'this.priceInput.value = this._fmt(price)' in alert


# ------------------------------------------------------------ 选择器筛选记忆
def test_settings_whitelist_includes_filter(tmp_path, monkeypatch):
    from minibt.desk import user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    values = user_prefs.set_setting('indicator_overlay_filter', 'main')
    assert values == {'indicator_overlay_filter': 'main'}
    assert user_prefs.settings() == {'indicator_overlay_filter': 'main'}


def test_picker_filter_is_remembered():
    picker = _read('jslib/src/panels/indicator-picker.ts')
    assert 'onFilterCallback' in picker
    assert 'setOverlayFilter(kind, notify = false)' in picker or \
        'notify = false' in picker
    assert 'this.setOverlayFilter(key, true)' in picker
    page = _read('jslib/src/desk/chart-page.ts')
    assert "key: 'indicator_overlay_filter', value: kind" in page
    assert 'this.indicatorPicker.setOverlayFilter(this.indicatorFilter)' in page
    assert "settings?.indicator_overlay_filter" in page
