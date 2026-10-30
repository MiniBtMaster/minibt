"""P36：一个指标一个副图（pane 去重，不会无限增加）✓"""
import json
import pathlib
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------------ 后端：pane key
def test_catalog_items_carry_stable_pane(tmp_path, monkeypatch):
    """同一条指标的多根线必须共用 `pane`（否则一条线一个副图 ✗）"""
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    rows = 120
    close = 100 + np.arange(rows, dtype=float)
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close - 1, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': np.ones(rows),
        'symbol': 'SHFE.demo01', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })
    out = cat.compute(frame, ['talib_MACD'])
    assert out, 'MACD 没算出来'
    panes = {item.get('pane') for item in out}
    assert panes == {'MACD'}, panes           # 3 根线共用一个副图 ✓


# ------------------------------------------------------------ 前端：pane 去重
def test_panes_reused_and_removed():
    layer = _read('jslib/src/desk/indicator.ts')
    # 复用：按 `item.pane || item.key` 取 handle ✓
    assert 'const paneKey = item.pane || item.key;' in layer
    # 删除：removePane + 修正后面的 index（否则下标串位/残留空 pane ✗）
    assert 'removePane?.(index)' in layer
    assert 'handle.index > index' in layer
    assert 'add.call(chart, false)' in layer      # 不留空 pane ✓


def test_pane_addition_is_bounded(tmp_path, monkeypatch):
    """重复推同一份指标补丁 → 副图数量不增长（用户实测：无限增加 ✗）"""
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    rows = 80
    close = 100 + np.arange(rows, dtype=float)
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close - 1, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': np.ones(rows),
        'symbol': 'SHFE.demo01', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })
    out = cat.compute(frame, ['talib_MACD'])
    panes = {item['pane'] for item in out}
    assert len(panes) == 1                    # 一个指标 → 一个副图 ✓


# ------------------------------------------------------------ 账户页（顶栏）
def test_account_page_does_not_touch_contract_bar():
    """账户页不在合约栏选项里 → 不能强 set（用户实测报错 ✗）"""
    window = _read('minibt/strategy/strategy_window.py')
    assert ("if contract not in INFO_PAGES and contract != ACCOUNT_PAGE:"
            in window)
    assert ("self.chart.topbar['contract'].set(contract)" in window)
    # 顶栏「账户」按钮仍然在 ✓
    assert "page_bar.button('account', '账户'" in window
