"""P39：ATR 警告 / 删除指标菜单 / 键盘精灵（空格键）✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------- ① ATR 的 NaN 警告
def test_atr_no_nan_warning():
    """`np.maximum` 遇到 NaN 会刷 `invalid value encountered` ✗"""
    source = _read('minibt/indicators/tradingview.py')
    assert '_pc[0] = close[0] if n else 0.0' in source   # 首根用收盘价占位 ✓
    assert "np.errstate(invalid='ignore')" in source      # 兜底不刷警告 ✓
    assert '_tr[0] = np.nan' in source                    # 首根仍是 na ✓


def test_alphatrend_runs_without_warnings():
    import warnings

    import pytest

    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt import KLine

    rows = 200
    close = 100 + np.sin(np.arange(rows) / 9.0) * 3
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close + 0.4, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': np.abs(np.sin(np.arange(rows) / 5)) * 100,
        'symbol': 'SHFE.demo01', 'duration': 60,
    })
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        out = KLine(frame).tradingview.AlphaTrend()
    assert not [item for item in caught
                if 'invalid value encountered' in str(item.message)]
    values = out['alpha_trend'].to_numpy()
    assert np.isnan(values[0])                 # `ta.tr(false)` 首根 na ✓
    assert not np.isnan(values[14])            # ATR 要 AP 根才有效 ✓


# ------------------------------------------------------- ② 删除指标菜单
def test_remove_menu_lists_every_chart():
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'openRemoveMenu(' in page
    assert 'openRemoveMenu(button)' in page          # 🗑 点开菜单（不是直删）
    for key in ('this.cellItems.forEach', '_cellTitle(',
                '删除全部指标', 'removeIndicator(source, cell)',
                'removeStrategy(this.activeCell)', 'removeSource?.('):
        assert key in page, key
    # 一个指标可能有多条线 → 按 `source` 归组 ✓
    assert "item.source || key.split(':')[0]" in page
    assert '_sourceLabel(' in page                    # `pta_macd` → `pta.macd` ✓


def test_remove_indicator_supports_cell():
    app = _read('minibt/desk/app.py')
    assert 'def _on_remove_indicator' in app
    assert "_drop_cell_indicators(info, cells, cell, key)" in app
    assert "'cell': int(payload.get('cell') or 0)" in app
    for key in ("if payload.get('cell') is None:", '_push_cell_indicators'):
        assert key in app, key


def test_indicator_items_carry_source():
    catalog = _read('minibt/desk/indicator_catalog.py')
    assert "'source': key," in catalog
    builtin = _read('minibt/desk/indicators.py')
    assert "item.setdefault('source', key)" in builtin


# ------------------------------------------------------- ③ 键盘精灵
def test_keyboard_sprite_component():
    sprite = _read('jslib/src/desk/keyboard-sprite.ts')
    for key in ('export class KeyboardSprite', "'indicator'", "'strategy'",
                "'symbol'", 'ArrowDown', 'ArrowUp', 'Escape', 'dblclick',
                'isTypingTarget'):
        assert key in sprite, key


def test_space_hotkey_and_pick():
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'private _bindSpriteHotkey()' in page
    assert "event.key !== ' ' && event.code !== 'Space'" in page
    assert 'isTypingTarget(event.target)' in page       # 输入框里空格就是空格 ✓
    assert 'pickSprite(item' in page
    assert "'switch_symbol'" in page                    # 合约/股票 → 切换 ✓
    assert 'onAddIndicator?.(item.key' in page           # 指标/策略 → 添加 ✓
    assert 'openSprite(' in page


def test_sprite_backend_command():
    app = _read('minibt/desk/app.py')
    assert "'sprite_search': self._on_sprite_search" in app
    body = app.split('def _on_sprite_search', 1)[1].split(
        '\n    def ', 1)[0]
    assert "kind': 'indicator'" in body
    assert "kind': 'strategy'" in body
    assert "kind': 'symbol'" in body
    assert "'type': 'sprite'" in body
    # 前端要把结果交给键盘精灵 ✓
    front = _read('jslib/src/desk/app.ts')
    assert "case 'sprite':" in front
    assert 'setSpriteResults(' in front
