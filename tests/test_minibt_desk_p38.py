"""P38：图例收起按钮 / 副图间隙 0 / PlotInfo 样式加载 / 调色板 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------- ① 图例收起 / 下拉
def test_legend_collapse_button_replicated():
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'enableCollapse?.()' in page          # miniqt 同款 `∨ N` ✓
    legend = _read('jslib/src/general/legend.ts')
    assert 'enableCollapse()' in legend
    css = _read('jslib/src/general/styles.css')
    assert '.legend-collapse' in css


# ------------------------------------------------------- ② 主图副图间隙 0
def test_pane_separator_is_transparent():
    """副图分隔线：P123 起改成**主题色**（2px，浅/深都看得见 ✓）"""
    theme = _read('jslib/src/desk/theme.ts')
    assert 'separatorColor' in theme
    assert "theme === 'light'" in theme           # 深浅两套颜色 ✓
    assert 'enableResize: true' in theme          # 还能拖高度 ✓
    css = _read('jslib/src/desk/desk.css')
    assert '.desk-cell-sub { flex: 0 0 auto; height: 0;' in css


# ------------------------------------------------------- ③ PlotInfo 样式
def _frame(rows: int = 120):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    close = 100 + np.sin(np.arange(rows) / 9.0) * 3
    return pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close + 0.4, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': np.abs(np.sin(np.arange(rows) / 5)) * 100,
        'symbol': 'SHFE.demo01', 'duration': 60,
    })


def test_catalog_uses_plotinfo_accessor(tmp_path, monkeypatch):
    """`pta_bbands` → `kline.pta.bbands()`（**带 PlotInfo** ✓）"""
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    assert cat._split_key('pta_bbands') == ('pta', 'bbands')
    assert cat._split_key('talib_SMA') == ('talib', 'SMA')
    assert cat.ACCESSOR_OF['pta'] == 'pta'
    source = _read('minibt/desk/indicator_catalog.py')
    assert 'def _plotinfo_calls(' in source


def test_overlap_decides_main_and_sub(tmp_path, monkeypatch):
    """BOLL：3 根线在**主图**、width/percent 在**副图** ✓"""
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    items = cat.compute(_frame(), ['pta_bbands'])
    main = [item['key'] for item in items if item['overlay']]
    sub = [item['key'] for item in items if not item['overlay']]
    assert any('bb_upper' in key for key in main)
    assert any('bb_lower' in key for key in main)
    assert any('bb_width' in key for key in sub)      # 以前全部当副图 ✗
    assert all(item['kind'] == 'line' for item in items)


def test_vbar_becomes_histogram(tmp_path, monkeypatch):
    """`line_dash='vbar'` → 柱状（MACD 柱 ✓）"""
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    items = cat.compute(_frame(), ['pta_macd'])
    kinds = {item['key'].split(':')[-1]: item['kind'] for item in items}
    assert kinds.get('macdh') == 'hist'
    assert kinds.get('macdx') == 'line'
    assert all(not item['overlay'] for item in items)  # MACD = 副图 ✓


def test_linestyle_colors_and_width(tmp_path, monkeypatch):
    """颜色 / 线宽 / 线型都来自 `PlotInfo.linestyle` ✓"""
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    items = cat.compute(_frame(), ['tv:HalfTrend'])
    colors = {item['color'] for item in items if item['kind'] == 'line'}
    assert any(color.startswith('#') for color in colors)
    dashed = [item for item in items if item.get('lineStyle')]
    assert dashed, 'PlotInfo 里的虚线没生效'
    assert all(item.get('lineWidth', 1) >= 1 for item in items)


def test_bandstyle_fills_between_lines(tmp_path, monkeypatch):
    """`bandstyle` → 两条线之间填充（`kind: 'band'` ✓）"""
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    items = cat.compute(_frame(), ['tv:HalfTrend'])
    bands = [item for item in items if item['kind'] == 'band']
    assert bands, '色带没出来'
    assert bands[0]['lowerKey'] and bands[0]['upperKey']
    assert bands[0]['color'].startswith('rgba(')      # 带透明度 ✓
    page = _read('jslib/src/desk/indicator.ts')
    assert 'LineFill' in page and 'attachPrimitive' in page


def test_frontend_kinds_supported():
    page = _read('jslib/src/desk/indicator.ts')
    for key in ("'line' | 'hist' | 'candles' | 'marker' | 'vp'",
                "| 'band' | 'table' | 'span'",
                "lineStyle: Number(item.lineStyle) || 0",
                "_applyBands(", "_applyTables(", 'desk-ind-table'):
        assert key in page, key
    css = _read('jslib/src/desk/desk.css')
    assert '.desk-ind-table' in css


# ------------------------------------------------------- ④ 调色板
def test_palette_picker_at_end_of_colors():
    settings = _read('jslib/src/desk/indicator-settings.ts')
    assert "picker.type = 'color';" in settings         # 系统三色取色窗口 ✓
    assert 'desk-is-color-custom' in settings
    body = settings.split('const colors = document.createElement', 1)[1]
    body = body.split('box.appendChild(colors);', 1)[0]
    assert body.index('desk-is-color-custom') > body.index(
        'for (const color of LINE_COLORS)')             # 排在最后 ✓
    # 样式在 indicator-settings.ts 里自带（和这个组件一起 ✓）
    assert '.desk-is-color-input' in settings
    assert 'opacity: 0' in settings
