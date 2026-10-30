"""P29：布局缩略带指标数 / Ticker 开关 / 实时合并 / 目录 Core 兜底 ✓"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------------ 布局缩略信息
def test_layout_summary_omits_indicator_count():
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'Number(row.indicators || 0)' not in page
    assert '${indicators}指标' not in page
    # 后端仍保留 indicators 字段供内部使用，但 desc 不拼指标 / 参数 ✓
    app = _read('minibt/desk/app.py')
    assert "'indicators': sum(len(cell.get('indicators') or [])" in app
    assert "for item in cell.get('indicators') or []:" not in app.split(
        'def _layout_view', 1)[1].split('def _on_layouts', 1)[0]


# ------------------------------------------------------------ Ticker 开关 / 位置
def test_ticker_only_quoted_setting(tmp_path, monkeypatch):
    from minibt.desk import user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    assert 'ticker_only_quoted' in user_prefs.SETTING_KEYS
    assert user_prefs.set_setting('ticker_only_quoted', True) == {
        'ticker_only_quoted': True}


def test_ticker_filters_unquoted_rows(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    user_prefs.set_setting('ticker_only_quoted', True)
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk._ticker_names = {}
    # 一根有报价 + 一根没有
    desk._last_rows = {'SHFE.rb2610': {'symbol': 'SHFE.rb2610', 'name': '螺纹',
                                      'last': 3600.0, 'chg_pct': 0.3,
                                      'volume': 10}}
    desk._refresh_ticker([{'symbol': 'SHFE.rb2610', 'name': '螺纹'},
                          {'symbol': 'DCE.m2609', 'name': '豆粕'}])
    patch = [json.loads(row[len('window.__desk.applyPatch('):-2])
             for row in desk.sent if '"type":"ticker"' in row][-1]
    assert [item['symbol'] for item in patch['items']] == ['SHFE.rb2610']


def test_quote_page_is_not_position_relative():
    """`.desk-quote-page` 不能覆盖 `.desk-stack > *` 的绝对定位（会溢出 ✗）"""
    css = _read('jslib/src/desk/desk.css')
    block = css.split('.desk-quote-page {', 1)[1].split('}', 1)[0]
    assert 'position: relative' not in block
    assert 'height: 100%' in block and 'min-height: 0' in block
    assert 'overflow: hidden' in block
    grid = css.split('.desk-quote-grid-host {', 1)[1].split('}', 1)[0]
    assert 'overflow: hidden' in grid


def test_quote_page_has_ticker_toggle_button():
    page = _read('jslib/src/desk/quote-page.ts')
    for key in ("tickerButton.textContent = '播放条'", 'tickerOnlyQuoted',
                'onTickerSetting', 'onTickerRefresh', 'setSettings('):
        assert key in page, key
    app = _read('jslib/src/desk/app.ts')
    assert "onTickerSetting: (key, value) => this.send('set_setting', {" in app
    assert "onTickerRefresh: () => this.send('ticker_refresh'" in app


# ------------------------------------------------------------ 图表实时合并
def test_merge_bars_helper():
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'export function mergeBars(' in page
    assert 'this.bars = replace ? bars.slice() : mergeBars(this.bars, bars);' \
        in page
    # 同时间覆盖 / 新的追加 / 历史忽略
    assert 'merged[merged.length - 1] = bar;' in page
    assert 'if (!last || bar.time > last.time)' in page


def test_kline_push_is_throttled(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    rows = 30
    close = 100 + np.arange(rows, dtype=float)

    class Feed:
        kind = 'futures'
        api = None

        def available(self):
            return True

        def klines(self, symbol, cycle, length=500):
            return pd.DataFrame({
                'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                             for i in range(rows)],
                'open': close - 1, 'high': close + 2, 'low': close - 2,
                'close': close, 'volume': np.ones(rows),
                'symbol': 'SHFE.demo01', 'duration': 60, 'price_tick': 1.0,
                'volume_multiple': 10})

        def quotes(self, keys):
            return []

        def spec(self, symbol):
            return None

        def get_position(self, symbol):
            return None

    desk.futures = Feed()
    desk.feeds = [desk.futures]
    desk.tabs['SHFE.demo01'] = {'feed': desk.futures, 'cycle': 60,
                                'indicators': []}
    desk._refresh_tabs()
    first = [row for row in desk.sent if '"type":"kline"' in row]
    assert first, '第一次没有推 K 线'
    desk.sent.clear()
    desk._refresh_tabs()          # 1 秒内、同一根 → 不重复推 ✓
    assert not [row for row in desk.sent if '"type":"kline"' in row]


# ------------------------------------------------------------ 目录 Core 兜底
def test_catalog_core_fallback(tmp_path, monkeypatch):
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    core = cat._build_from_core()
    groups = {}
    for item in core:
        groups[item['group']] = groups.get(item['group'], 0) + 1
    assert groups.get('PandasTA', 0) > 150
    assert groups.get('TA-Lib', 0) > 90
    assert len(core) > 500


def test_catalog_survives_missing_indicator_class(tmp_path, monkeypatch):
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    import minibt
    monkeypatch.delattr(minibt, 'IndicatorClass', raising=False)
    # 模块反射也废掉 → 只剩 CoreIndicators 兜底，仍要有货 ✓
    monkeypatch.setattr(cat, '_build_from_modules', lambda: [])
    items = cat.catalog(refresh=True)
    assert len(items) > 500


def test_kline_full_replace_when_initial_frame_grows(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True

    class Feed:
        kind = 'futures'
        api = None
        rows = 2

        def available(self):
            return True

        def klines(self, symbol, cycle, length=500):
            close = 100 + np.arange(self.rows, dtype=float)
            return pd.DataFrame({
                'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                             for i in range(self.rows)],
                'open': close - 1, 'high': close + 2, 'low': close - 2,
                'close': close, 'volume': np.ones(self.rows),
                'symbol': 'SHFE.demo01', 'duration': 60, 'price_tick': 1.0,
                'volume_multiple': 10})

        def quotes(self, keys):
            return []

        def spec(self, symbol):
            return None

        def get_position(self, symbol):
            return None

    feed = Feed()
    desk.futures = feed
    desk.feeds = [feed]
    desk.tabs['SHFE.demo01'] = {'feed': feed, 'cycle': 60,
                                'indicators': [], '_kline_frame_len': 2}
    desk._refresh_tabs()
    feed.rows = 30
    desk.sent.clear()
    desk._refresh_tabs()
    patch = [json.loads(row[len('window.__desk.applyPatch('):-2])
             for row in desk.sent if '"type":"kline"' in row][-1]
    assert patch['replace'] is True
    assert len(patch['bars']) == 30
