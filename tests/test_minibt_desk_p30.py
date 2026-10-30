"""P30：增量 update / 播放条开关进看盘页 / 指示器包加载容错 ✓"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------------ 增量 update
def test_set_bars_uses_series_update():
    page = _read('jslib/src/desk/chart-page.ts')
    for key in ('private _updateTail(', 'series.update(toCandle(bar) as never)',
                'volume?.update?.(toVolume(bar) as never)',
                'if (!replace) {', 'mergeBars(this.bars, bars)'):
        assert key in page, key


def test_merge_bars_still_dedupes():
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'if (!last || bar.time > last.time)' in page
    assert 'merged[merged.length - 1] = bar;' in page


# ------------------------------------------------------------ 播放条开关（看盘页）
def test_chart_toolbar_has_no_ticker_toggle():
    """P40：播放条只属于行情报价页 → 看盘窗口的工具栏里**没有**它 ✓"""
    page = _read('jslib/src/desk/chart-page.ts')
    assert "const tickerButton = this._toolButton(" not in page
    assert "'播放条'" not in page


# ------------------------------------------------------------ 指标包加载容错
def test_catalog_imports_submodules_not_package():
    cat = _read('minibt/desk/indicator_catalog.py')
    for key in ('def _submodule(', 'def _library(', 'def core_indicators()',
                "importlib.import_module(f'minibt.indicators.{name}')",
                "LIB_MODULES = {", "'PandasTa': 'pandas_ta'"):
        assert key in cat, key


def test_catalog_works_with_broken_package(tmp_path, monkeypatch):
    """模拟用户机器上的 `minibt.indicators` 成了 namespace 包
    （`ImportError: cannot import name 'CoreIndicators' ... (unknown location)`）✓
    """
    import sys
    import types

    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    import minibt

    path = pathlib.Path(minibt.__file__).parent / 'indicators'
    broken = types.ModuleType('minibt.indicators')
    broken.__path__ = [str(path)]
    monkeypatch.setitem(sys.modules, 'minibt.indicators', broken)
    monkeypatch.setattr(minibt, 'indicators', broken, raising=False)
    monkeypatch.delattr(minibt, 'IndicatorClass', raising=False)

    items = cat.catalog(refresh=True)
    assert len(items) > 500, f'目录还是空的（{len(items)}）'
    groups = {}
    for item in items:
        groups[item['group']] = groups.get(item['group'], 0) + 1
    assert groups.get('PandasTA', 0) > 100
    assert groups.get('TA-Lib', 0) > 50


def test_compute_works_with_broken_package(tmp_path, monkeypatch):
    import sys
    import types

    from minibt.desk import indicator_catalog as cat

    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    import minibt

    path = pathlib.Path(minibt.__file__).parent / 'indicators'
    broken = types.ModuleType('minibt.indicators')
    broken.__path__ = [str(path)]
    monkeypatch.setitem(sys.modules, 'minibt.indicators', broken)
    monkeypatch.setattr(minibt, 'indicators', broken, raising=False)
    monkeypatch.delattr(minibt, 'IndicatorClass', raising=False)
    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))

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
    out = cat.compute(frame, ['pta_sma'])
    assert out and out[0]['data'], '坏包情况下算不出指标 ✗'


# ------------------------------------------------------------ 缓存击穿
def test_desk_html_is_cache_busted():
    html = _read('pylightcharts/js/desk.html')
    assert 'desk.js?v=' in html
    assert 'desk.css?v=' in html
    script = _read('jslib/scripts/postbuild.mjs')
    assert 'desk.html cache-bust' in script
