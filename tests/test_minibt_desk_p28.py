"""P28：周期箭头 / 布局缩略 / Ticker 价格 / 目录改 IndicatorClass ✓"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------------ 周期箭头 / 布局缩略
def test_cycle_and_layout_buttons_have_caret():
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'desk-tool-caret' in page
    assert "cycleArrow.textContent = '▾'" in page
    assert "layoutCaret.textContent = '▾'" in page
    css = _read('jslib/src/desk/desk.css')
    assert '.desk-tool-caret' in css and '.desk-tool-arrow' in css


def test_layout_menu_rows_show_summary():
    page = _read('jslib/src/desk/chart-page.ts')
    for key in ('`${count}格`', 'cycleLabel(cycle)', 'row.desc', 'row.favorite'):
        assert key in page, key


# ------------------------------------------------------------ Ticker 价格
class _Feed:
    kind = 'futures'
    api = None

    def available(self):
        return True

    def quotes(self, keys):
        return [{'symbol': key, 'name': '', 'last': 3600.0 + index,
                 'chg': 12.0, 'chg_pct': 0.35, 'volume': 100 - index,
                 'decimals': 0} for index, key in enumerate(keys)]

    def spec(self, symbol):
        return None


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = _Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    return desk


def test_ticker_gets_prices_from_quotes(tmp_path, monkeypatch):
    """合约清单没有 last → 播放条不能只显示名字（用户实测 ✗）"""
    desk = _desk(tmp_path, monkeypatch)
    desk.visible = ['SHFE.rb2610']
    desk._refresh_ticker([{'symbol': 'SHFE.rb2610', 'name': '螺纹钢2610'}])
    patch = [json.loads(row[len('window.__desk.applyPatch('):-2])
             for row in desk.sent if '"type":"ticker"' in row][-1]
    assert patch['items'][0]['name'] == '螺纹钢2610'

    desk.sent.clear()
    desk._refresh_visible()            # 报价到了 → 顺带刷新播放条 ✓
    patches = [json.loads(row[len('window.__desk.applyPatch('):-2])
               for row in desk.sent if '"type":"ticker"' in row]
    assert patches, '报价刷新后没有更新播放条'
    item = patches[-1]['items'][0]
    assert item['last'] == 3600.0
    assert item['chg_pct'] == 0.35
    assert item['decimals'] == 0
    assert item['name'] == '螺纹钢2610'      # 中文名保留 ✓


def test_ticker_refresh_is_throttled(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.visible = ['SHFE.rb2610']
    desk._refresh_visible()
    desk.sent.clear()
    desk._refresh_visible()                  # 1 秒内不再推 ✓
    assert not [row for row in desk.sent if '"type":"ticker"' in row]


# ------------------------------------------------------------ 目录走 IndicatorClass
def test_catalog_uses_indicator_class(tmp_path, monkeypatch):
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    items = cat.catalog(refresh=True)
    keys = [item['key'] for item in items]
    assert len(keys) == len(set(keys)), '目录里有重复 key ✗'
    groups = {}
    for item in items:
        groups[item['group']] = groups.get(item['group'], 0) + 1
    # 和 miniqt 同源 → 指标数不能缩水 ✓
    # 合并 IndicatorClass + 模块反射 + CoreIndicators 兜底 → 只会多不会少 ✓
    # ★ Pair / Factors / NON_KLINE_INDICATORS 过滤后数量会减少；
    #   TradingView 不受影响 ✓
    assert groups['PandasTA'] >= 159
    assert groups['TA-Lib'] >= 90
    assert groups['天勤函数'] >= 10
    assert groups['TradingView'] == 114
    assert sum(groups.values()) >= 690


def test_catalog_fallback_when_indicator_class_missing(tmp_path, monkeypatch):
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    import minibt
    monkeypatch.delattr(minibt, 'IndicatorClass', raising=False)
    items = cat.catalog(refresh=True)
    # 退回模块反射也要有货（不然选择器就空了 ✗）
    assert len(items) > 400
    assert any(item['key'].startswith('pta_') for item in items)


def test_compute_works_for_both_sources():
    from minibt.desk import indicator_catalog as cat
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    rows = 120
    close = 100 + np.arange(rows, dtype=float)
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close - 1, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': np.ones(rows),
        'symbol': 'SHFE.rb2610', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })
    out = cat.compute(frame, ['pta_sma', 'talib_RSI'])
    assert out and all(item['data'] for item in out)


def test_isplot_false_signal_columns_still_become_markers(tmp_path, monkeypatch):
    """`isplot=False` 的 long/short_signal 仍要按 signalstyle 画箭头 ✓"""
    from minibt.desk import indicator_catalog as cat
    import numpy as np
    pd = pytest.importorskip('pandas')

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    rows = 320
    close = 100 + np.cumsum(np.random.default_rng(2).normal(0, 0.5, rows))
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close - 0.5, 'high': close + 1, 'low': close - 1,
        'close': close, 'volume': np.ones(rows),
        'symbol': 'SHFE.rb2610', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })
    items = cat.compute(frame, ['tv:ScalpingPullBackTool'], {}, limit=rows)
    keys = {item['key'] for item in items}
    assert 'tv:ScalpingPullBackTool:long_signal' in keys
    assert 'tv:ScalpingPullBackTool:short_signal' in keys
    assert any(item['kind'] == 'band' for item in items)
    long_item = next(item for item in items
                     if item['key'].endswith(':long_signal'))
    assert long_item['kind'] == 'marker'
    assert long_item['overlay'] is True
