"""P19：参数容忍 / 选择器分组 / 全部指标 / decimals / 点档位下单 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK = ROOT / 'minibt' / 'desk'
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'
PANEL_TS = ROOT / 'jslib' / 'src' / 'panels'


def _read(path):
    return path.read_text(encoding='utf-8')


# ------------------------------------------------------------ 参数容忍（用户 bug）
def test_as_params_accepts_catalog_param_table():
    from minibt.desk.app import _as_params

    table = [{'name': 'length', 'label': '周期', 'default': 20, 'type': 'int'},
             {'name': 'width', 'label': '倍数', 'default': 2.0,
              'type': 'float'}]
    assert _as_params(table) == {'length': 20, 'width': 2.0}
    assert _as_params({'length': 5}) == {'length': 5}
    assert _as_params(None) == {}
    assert _as_params([['a', 1], ['b', 2]]) == {'a': 1, 'b': 2}


def test_add_indicator_with_param_list_does_not_raise(tmp_path, monkeypatch):
    """收藏的 MA 通过指标菜单加载 → 以前报
    `dictionary update sequence element #0 has length 4; 2 is required` ✓"""
    from minibt.desk import protocol, user_prefs
    from minibt.desk.app import Desk

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.tabs['SHFE.demo01'] = {'cycle': 60, 'indicators': []}
    desk.handle(protocol.encode_command({
        'cmd': 'add_indicator',
        'payload': {'symbol': 'SHFE.demo01', 'key': 'MA',
                    'params': [{'name': 'length', 'label': '周期',
                                'default': 20, 'type': 'int'}]},
    }))
    entries = desk.tabs['SHFE.demo01']['indicators']
    assert entries and entries[0]['key'] == 'MA'
    assert entries[0]['params'] == {'length': 20}
    assert not [row for row in desk.sent if '命令失败' in str(row)]


# ------------------------------------------------------------ 选择器分组
def test_picker_sections_cover_every_library(tmp_path, monkeypatch):
    from minibt.desk import indicator_catalog as cat, user_prefs
    from minibt.desk.app import Desk

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    desk = Desk(offline=True)
    counts = {}
    for item in desk.picker_items():
        counts[item['section']] = counts.get(item['section'], 0) + 1
    # 以前 TqTa / TqFunc 是空的（中文标签没映射上 ✗）
    assert counts.get('tqta', 0) > 30, counts
    assert counts.get('tqfunc', 0) > 10, counts
    assert counts.get('tradingview', 0) > 80, counts
    assert counts.get('talib', 0) > 50, counts
    assert counts.get('finta', 0) > 50, counts
    assert counts.get('pta', 0) < 200, counts      # 不再把 TqTa/TqFunc 混进来
    # P59：「常用」组已删除（全部走 minibt 指标库 ✓）
    assert counts.get('common', 0) == 0
    total = sum(counts.values())
    assert total > 650, total


def test_picker_groups_have_all_section(tmp_path, monkeypatch):
    from minibt.desk import user_prefs
    from minibt.desk.app import Desk

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = Desk(offline=True)
    sections = [section['key'] for group in desk._picker_groups()
                for section in group['sections']]
    assert 'common' not in sections and 'all' in sections
    for key in ('tqta', 'tqfunc', 'tradingview', 'talib', 'finta'):
        assert key in sections, key
    assert 'pair' not in sections and 'factor' not in sections


def test_picker_renders_all_section_and_opens_all():
    panel = _read(PANEL_TS / 'indicator-picker.ts')
    assert "this.section === 'all'" in panel
    page = _read(DESK_TS / 'chart-page.ts')
    # 没有收藏时停在「常用」，不是空列表 ✓
    assert "favorites.length ? 'favorites' : 'all'" in page
    # 收藏项不再把参数表当 dict 发 ✗
    assert 'onAddIndicator?.(String(row.key), {})' in page


# ------------------------------------------------------------ decimals（price_tick）
def test_decimals_from_tick():
    from minibt.desk.app import _decimals_from_tick

    assert _decimals_from_tick(1) == 0
    assert _decimals_from_tick(0.5) == 1
    assert _decimals_from_tick(0.2) == 1
    assert _decimals_from_tick(0.05) == 2
    assert _decimals_from_tick(0.01) == 2
    assert _decimals_from_tick(0.001) == 3
    assert _decimals_from_tick(0.0001) == 4
    assert _decimals_from_tick(None) == 2
    assert _decimals_from_tick('x') == 2


def test_book_payload_has_decimals_from_price_tick(tmp_path, monkeypatch):
    from minibt.desk import user_prefs
    from minibt.desk.app import Desk

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))

    class Quote:
        price_tick = 0.5
        ask_price1, bid_price1 = 13842.5, 13842.0
        ask_volume1, bid_volume1 = 3, 4

    class Feed:
        api = None

        def available(self):
            return True

        def spec(self, symbol):
            return Quote()

    desk = Desk(offline=True)
    payload = desk.book_payload('SHFE.demo01', Feed())
    assert payload['decimals'] == 1
    assert payload['price_tick'] == 0.5


def test_chart_page_applies_decimals_and_toggle():
    page = _read(DESK_TS / 'chart-page.ts')
    assert 'this.setDecimals(decimals)' in page
    # P34 起买卖盘改成「透明三格 + 市价调仓」，旧的「点档位下单」开关已移除 ✓
    assert 'ticket_order' in page
    book = _read(DESK_TS / 'quote-panel.ts')
    # 二级报价点档位 → 只填价（买卖盘本身是市价调仓 ✓）
    assert 'onLevelClick' in book and 'setTicketPrice(price)' in page
    css = _read(DESK_TS / 'desk.css')
    assert '.desk-ticket-side' in css      # 买卖盘三格样式 ✓


# ------------------------------------------------------------ 设置落盘
def test_settings_roundtrip(tmp_path, monkeypatch):
    from minibt.desk import user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    assert user_prefs.settings() == {}
    values = user_prefs.set_setting('ticket_click_orders', True)
    assert values == {'ticket_click_orders': True}
    assert user_prefs.settings() == {'ticket_click_orders': True}
    # 白名单外的不落盘
    assert user_prefs.set_setting('nope', 1) == {'ticket_click_orders': True}
    # 收藏不受影响
    assert user_prefs.toggle_favorite('MA', True) == ['MA']
    assert user_prefs.load()['settings'] == {'ticket_click_orders': True}


def test_set_setting_command_pushes_patch(tmp_path, monkeypatch):
    from minibt.desk import protocol, user_prefs
    from minibt.desk.app import Desk

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.handle(protocol.encode_command({
        'cmd': 'set_setting',
        'payload': {'key': 'ticket_click_orders', 'value': True},
    }))
    patches = [row for row in desk.sent if '"settings"' in str(row)]
    assert patches and 'ticket_click_orders' in str(patches[-1])


def test_catalog_filters_multi_contract_and_non_kline(tmp_path, monkeypatch):
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    keys = {item['key'] for item in cat.catalog(refresh=True)}
    for key in ('pair_z_score', 'factor_optimizer',
                'pta_ZeroDivision', 'pta_above', 'ti_abs', 'ti_crossany',
                'talib_ADD', 'btind_rngfilt', 'tqfunc_crossup'):
        assert key not in keys, key
    assert not any(key.startswith(('pair_', 'factor_')) for key in keys)
    groups = {item['group'] for item in cat.catalog()}
    assert 'Pair' not in groups and 'Factors' not in groups
