"""P18：目录缓存结构版本 + TradingView 信号箭头/配色 + 买卖盘点差盘 ✓"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(path):
    return path.read_text(encoding='utf-8')


def _frame(rows=12):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    close = 100 + np.arange(rows, dtype=float)
    return pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close - 1, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': np.ones(rows),
        'symbol': 'SHFE.demo01', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })


# ------------------------------------------------------- 目录缓存结构版本
def test_schema_stamp_covers_structure(tmp_path, monkeypatch):
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    stamp = cat.schema_stamp()
    assert f'schema{cat.CATALOG_SCHEMA}' in stamp
    # 分组 / 库定义变了 → 版本一定变（不然会用到旧缓存 ✗）
    assert 'TradingView' in stamp or cat.TRADINGVIEW_PREFIX in stamp
    # 旧缓存只写了 minibt 版本 → 视为过期 ✓
    (tmp_path / 'ind.json').write_text(json.dumps(
        {'version': cat.minibt_version(), 'items': [{'key': 'stale'}]}),
        encoding='utf-8')
    items = cat.catalog()
    assert items and items[0]['key'] != 'stale'


def test_cache_roundtrip_uses_schema_stamp(tmp_path, monkeypatch):
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    items = cat.catalog(refresh=True)
    data = json.loads((tmp_path / 'ind.json').read_text(encoding='utf-8'))
    assert data['version'] == cat.schema_stamp()
    again = cat.catalog()
    assert len(again) == len(items)


# ------------------------------------------------------- 信号箭头 / 配色
def test_signal_columns_become_markers():
    from minibt.desk import indicator_catalog as cat
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')

    frame = _frame()
    result = pd.DataFrame({
        'long_signal': [0, 1, 0, 0, -1, 0, 1, 0, 0, 0, 0, 0],
        'value': np.arange(12, dtype=float),
    })
    items = cat._to_items('tv:Demo', {'name': 'Demo', 'overlap': True},
                          result, cat._stamps(frame), np, 600, frame)
    by_key = {item['key']: item for item in items}
    signal = by_key['tv:Demo:long_signal']
    assert signal['kind'] == 'marker'
    assert signal['overlay'] is True
    # 0 = 没有信号，不当箭头 ✓
    assert len(signal['markers']) == 3
    first = signal['markers'][0]
    assert first['position'] == 'belowBar' and first['shape'] == 'arrowUp'
    assert first['color'] == cat.SIGNAL_BUY_COLOR
    sell = [m for m in signal['markers'] if m['shape'] == 'arrowDown']
    assert sell and sell[0]['position'] == 'aboveBar'
    assert sell[0]['color'] == cat.SIGNAL_SELL_COLOR
    # 普通数值列还是线
    assert by_key['tv:Demo:value']['kind'] == 'line'


def test_signal_line_colors_by_name():
    from minibt.desk import indicator_catalog as cat

    colors = ('#111111', '#222222')
    assert cat._signal_color('long_signal', 0, colors) == cat.SIGNAL_BUY_COLOR
    assert cat._signal_color('short_signal', 1, colors) == cat.SIGNAL_SELL_COLOR
    assert cat._signal_color('k1', 1, colors) == '#222222'


def test_is_signal_line_needs_hint_and_discrete_values():
    from minibt.desk import indicator_catalog as cat

    assert cat._is_signal_line('buy_signal', [0, 0, 1])
    # 名字像信号但取值是连续量 → 不当箭头（避免把均线画成箭头 ✗）
    assert not cat._is_signal_line(
        'long_value', [float(i) / 100 for i in range(60)])
    # 名字没有提示词 → 不是信号
    assert not cat._is_signal_line('k1', [0, 1, 0])


# ------------------------------------------------------- 买卖盘（点差盘）
def test_ticket_has_buy_spread_sell_layout():
    page = _read(DESK_TS / 'chart-page.ts')
    # P34 起买卖盘只有三个格子（透明、无手数/价格/档位 ✓）
    for key in ('desk-ticket-row', 'desk-ticket-side', 'desk-ticket-spread',
                '买入', '卖出', '平仓', '_ticketClick',
                "'ticket_order'", 'setTicketBook', 'setDecimals'):
        assert key in page, key
    css = _read(DESK_TS / 'desk.css')
    for key in ('.desk-ticket-side.buy', '.desk-ticket-side.sell',
                '.desk-ticket-side.flat', '.desk-ticket-spread'):
        assert key in css, key


def test_ticket_labels_follow_position():
    page = _read(DESK_TS / 'chart-page.ts')
    # 多仓 → 右侧平仓；空仓 → 左侧平仓（和 minibt 实时图一致 ✓）
    assert 'const leftClose = net < 0' in page
    assert 'const rightClose = net > 0' in page
    # 点差 = |卖一 − 买一|
    assert 'Math.abs(this.ticketAsk - this.ticketBid)' in page


def test_marker_kind_supported_in_layer():
    layer = _read(DESK_TS / 'indicator.ts')
    for key in ("'line' | 'hist' | 'candles' | 'marker' | 'vp'", 'createSeriesMarkers',
                '_applyMarkers', 'markerSeries.delete'):
        assert key in layer, key
