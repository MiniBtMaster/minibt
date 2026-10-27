"""P20：选择器二级筛选（主图/副图）+ decimals 用到报价页 / 二级报价 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'
PANEL_TS = ROOT / 'jslib' / 'src' / 'panels'


def _read(path):
    return path.read_text(encoding='utf-8')


# ------------------------------------------------------------ 每行 decimals
def test_quote_row_has_decimals():
    from minibt.desk.symbols import quote_row

    class Quote:
        last_price = 3600.0
        pre_settlement = 3590.0
        price_tick = 1.0
        bid_price1, bid_volume1 = 3600.0, 3
        ask_price1, ask_volume1 = 3601.0, 4

    row = quote_row('SHFE.rb2610', 'rb', Quote())
    assert row['price_tick'] == 1.0
    assert row['decimals'] == 0

    class Fine(Quote):
        price_tick = 0.001

    assert quote_row('SHFE.ag2612', 'ag', Fine())['decimals'] == 3


def test_decimals_in_row_fields():
    from minibt.desk import symbols

    assert 'decimals' in symbols.ROW_FIELDS
    assert symbols.row(symbol='X')['decimals'] is None


# ------------------------------------------------------------ 选择器 overlay
def test_picker_items_expose_overlay(tmp_path, monkeypatch):
    from minibt.desk import indicator_catalog as cat, user_prefs
    from minibt.desk.app import Desk

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    desk = Desk(offline=True)
    items = desk.picker_items()
    main = [item for item in items if item.get('overlay')]
    # 主图指标不能是 0（以前字段名写错 → 全是副图 ✗）
    assert len(main) > 200, len(main)
    labels = {item['key'] for item in main}
    # P59：常用 6 个（MA/EMA/BOLL…）已从选择器移除，只查 minibt 指标库 ✓
    for key in ('pta_sma', 'pta_ema', 'tqta_BOLL', 'talib_BBANDS'):
        assert key in labels, key


def test_picker_filter_has_three_chips():
    panel = _read(PANEL_TS / 'indicator-picker.ts')
    for key in ("'all', '全部'", "'main', '主图叠加'", "'sub', '副图'",
                'setOverlayFilter', '_visibleRows', 'pylc-ip-filter',
                'pylc-ip-filter-count'):
        assert key in panel, key
    # 未知 overlay（个人脚本）不能因为筛选而消失 ✓
    assert "item.overlay !== true" in panel


# ------------------------------------------------------------ DataGrid / 报价页
def test_data_grid_supports_per_row_decimals():
    grid = _read(PANEL_TS / 'data-grid.ts')
    assert 'decimalsOf?: (row: RowData) => number | undefined' in grid
    assert 'this._format(value, column, row)' in grid
    assert 'column.decimalsOf(row)' in grid
    page = _read(DESK_TS / 'quote-page.ts')
    assert 'function rowDecimals(' in page
    # 价格列都走 decimalsOf（不再硬编码 3 位）
    for key in ('last', 'bid_price1', 'ask_price1', 'open', 'high', 'low',
                'pre_close', 'pre_settlement', 'upper_limit', 'lower_limit',
                'chg'):
        assert f"key: '{key}'" in page, key
    assert page.count('decimalsOf: rowDecimals()') >= 10


# ------------------------------------------------------------ 二级报价
def test_quote_panel_uses_book_decimals():
    panel = _read(DESK_TS / 'quote-panel.ts')
    assert 'private decimals = 3;' in panel
    assert 'this.decimals = Math.min(6' in panel
    assert 'num(level?.price, this.decimals)' in panel
    assert 'num(level?.price, this.decimals)' in panel
    assert 'toFixed(3)' not in panel
