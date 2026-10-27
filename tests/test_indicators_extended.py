"""Extended indicators (OBV/CCI/%R/ADX/Keltner/ROC/MFI): maths + chart wiring."""
import numpy as np
import pandas as pd
import pytest

from pylightcharts import indicators as ind
from pylightcharts.abstract import AbstractChart, Window


@pytest.fixture()
def ohlcv():
    rng = np.random.default_rng(3)
    rows = 400
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': pd.date_range('2020-01-01', periods=rows, freq='D'),
        'open': close,
        'high': close + np.abs(rng.standard_normal(rows)),
        'low': close - np.abs(rng.standard_normal(rows)),
        'close': close,
        'volume': rng.integers(100, 10_000, rows).astype(float),
    })


@pytest.fixture()
def chart(ohlcv):
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    chart.set(ohlcv)
    captured.clear()
    return chart


# --------------------------------------------------------------------------
# maths (cross-checked against TA-Lib when available)
# --------------------------------------------------------------------------

def test_obv_matches_talib(ohlcv):
    talib = pytest.importorskip('talib')
    got = ind.obv(ohlcv['close'], ohlcv['volume']).to_numpy()
    expected = talib.OBV(ohlcv['close'].to_numpy(), ohlcv['volume'].to_numpy())
    assert np.allclose(got, expected)


def test_cci_matches_talib(ohlcv):
    talib = pytest.importorskip('talib')
    got = ind.cci(ohlcv, 20).to_numpy()
    expected = talib.CCI(ohlcv['high'].to_numpy(), ohlcv['low'].to_numpy(),
                         ohlcv['close'].to_numpy(), 20)
    mask = ~np.isnan(expected)
    assert np.allclose(got[mask], expected[mask])


def test_williams_r_matches_talib(ohlcv):
    talib = pytest.importorskip('talib')
    got = ind.williams_r(ohlcv, 14).to_numpy()
    expected = talib.WILLR(ohlcv['high'].to_numpy(), ohlcv['low'].to_numpy(),
                           ohlcv['close'].to_numpy(), 14)
    mask = ~np.isnan(expected)
    assert np.allclose(got[mask], expected[mask])


def test_roc_matches_talib(ohlcv):
    talib = pytest.importorskip('talib')
    got = ind.roc(ohlcv['close'], 12).to_numpy()
    expected = talib.ROC(ohlcv['close'].to_numpy(), 12)
    mask = ~np.isnan(expected)
    assert np.allclose(got[mask], expected[mask])


def test_mfi_matches_talib(ohlcv):
    talib = pytest.importorskip('talib')
    got = ind.mfi(ohlcv, 14).to_numpy()
    expected = talib.MFI(ohlcv['high'].to_numpy(), ohlcv['low'].to_numpy(),
                         ohlcv['close'].to_numpy(), ohlcv['volume'].to_numpy(), 14)
    mask = ~np.isnan(expected)
    assert np.allclose(got[mask], expected[mask])


def test_adx_close_to_talib(ohlcv):
    talib = pytest.importorskip('talib')
    result = ind.adx(ohlcv, 14)
    for key, expected in (
        ('adx', talib.ADX(ohlcv['high'].to_numpy(), ohlcv['low'].to_numpy(), ohlcv['close'].to_numpy(), 14)),
        ('plus_di', talib.PLUS_DI(ohlcv['high'].to_numpy(), ohlcv['low'].to_numpy(), ohlcv['close'].to_numpy(), 14)),
        ('minus_di', talib.MINUS_DI(ohlcv['high'].to_numpy(), ohlcv['low'].to_numpy(), ohlcv['close'].to_numpy(), 14)),
    ):
        got = result[key].to_numpy()
        mask = ~np.isnan(expected)
        # the first value lands on the same index as TA-Lib; residual differences
        # come from Wilder accumulation rounding (~0.1 on a 0..100 scale)
        assert np.allclose(got[mask], expected[mask], atol=0.5), key


def test_adx_first_value_matches_talib_index(ohlcv):
    talib = pytest.importorskip('talib')
    mine = ind.adx(ohlcv, 14)['adx'].to_numpy()
    theirs = talib.ADX(ohlcv['high'].to_numpy(), ohlcv['low'].to_numpy(),
                       ohlcv['close'].to_numpy(), 14)
    assert np.argmax(~np.isnan(mine)) == np.argmax(~np.isnan(theirs)) == 2 * 14 - 1


def test_keltner_bands_are_ordered(ohlcv):
    bands = ind.keltner(ohlcv, 20, 2.0, 10)
    valid = bands['upper'].notna() & bands['lower'].notna()
    assert (bands['upper'][valid] >= bands['middle'][valid]).all()
    assert (bands['middle'][valid] >= bands['lower'][valid]).all()


def test_williams_r_bounds(ohlcv):
    values = ind.williams_r(ohlcv, 14).dropna()
    assert values.between(-100, 0).all()


def test_mfi_bounds(ohlcv):
    values = ind.mfi(ohlcv, 14).dropna()
    assert values.between(0, 100).all()


# --------------------------------------------------------------------------
# chart wiring
# --------------------------------------------------------------------------

@pytest.mark.parametrize('method,label', [
    ('add_obv', 'OBV'),
    ('add_roc', 'ROC 12'),
    ('add_williams_r', '%R 14'),
    ('add_cci', 'CCI 20'),
    ('add_mfi', 'MFI 14'),
])
def test_chart_indicator_methods(chart, method, label):
    getattr(chart, method)()
    scripts = '\n'.join(chart.captured)
    assert f'"{label}"' in scripts
    assert '"addPane"' in scripts          # oscillators get their own pane


def test_add_adx_returns_three_series(chart):
    adx, plus, minus = chart.add_adx()
    assert all(series is not None for series in (adx, plus, minus))
    scripts = '\n'.join(chart.captured)
    for label in ('"ADX 14"', '"+DI 14"', '"-DI 14"'):
        assert label in scripts


def test_add_keltner_is_an_overlay(chart):
    upper, middle, lower = chart.add_keltner()
    assert all(series is not None for series in (upper, middle, lower))
    scripts = '\n'.join(chart.captured)
    assert '"KC upper 20"' in scripts
    assert '"addPane"' not in scripts      # overlays stay on the price pane


def test_new_indicators_auto_refresh(chart):
    chart.set(pd.DataFrame())              # reset captured / data
    frame = chart.candle_data
    assert frame.empty
    with pytest.raises(ValueError):
        chart.add_obv()


def test_autochartpatterns_accessor_matches_indicator_params():
    """`kline.tradingview.AutoChartPatterns()` 的默认值必须与指标类 `params` 一致。

    走访问器（`TradingView.AutoChartPatterns`）时，实际生效的是**访问器的默认值**
    （它会把所有参数显式传给指标类），而 `AutoChartPatterns(kline)` 走的才是
    `cls.params`。两边不一致时，同一个指标会因为调用方式不同而给出不同结果 ——
    默认值对齐原码（ZigzagLite 8/55、numberOfPivots 5/6、errorThresold 20%、
    maxPatterns 20）时尤其容易漏掉一处。
    """
    import inspect

    pytest.importorskip('minibt')          # 这条只对 minibt 侧有意义（CI 里会跳过）
    from minibt.indicators import TradingView
    from minibt.indicators.tradingview import AutoChartPatterns

    signature = inspect.signature(TradingView.AutoChartPatterns)
    params = AutoChartPatterns.params
    for name, value in signature.parameters.items():
        if name in ('self', 'kwargs'):
            continue
        assert name in params, f'{name} 只在访问器里有'
        assert params[name] == value.default, (
            f'{name}: 访问器默认 {value.default!r} != 指标类 params {params[name]!r}')
    for name in params:
        assert name in signature.parameters, f'{name} 没有在访问器里暴露'
