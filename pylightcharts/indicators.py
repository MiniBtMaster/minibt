"""Technical indicators implemented with pandas/numpy only.

Keeping these dependency-free (no pandas-ta / TA-Lib) makes the package easy to
install and the behaviour predictable. Everything operates on a ``pd.Series``
(or a DataFrame containing ``high``/``low``/``close``) and returns a Series, or
a dict of Series for multi-line indicators.

The maths is deliberately numpy-first: ``Series.clip``/``where``/``mask`` pass
their condition through ``pandas.core.common.apply_if_callable``, which invokes
anything that looks callable. Some libraries (minibt sets ``pd.Series.__call__``
to build frames from plain DataFrames) make every Series callable, and the
boolean mask then gets invoked and silently misaligned. See
``tests/test_pandas_traps.py`` for the regression guard.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    'sma', 'ema', 'wma', 'rsi', 'macd', 'bollinger', 'stochastic', 'atr',
    'vwap', 'donchian',
    'obv', 'cci', 'williams_r', 'adx', 'keltner', 'roc', 'mfi',
    'swing_points', 'zigzag',
]


def sma(series: pd.Series, length: int = 20) -> pd.Series:
    """Simple moving average."""
    return series.rolling(length, min_periods=1).mean()


def ema(series: pd.Series, length: int = 20) -> pd.Series:
    """Exponential moving average."""
    return series.ewm(span=length, adjust=False, min_periods=1).mean()


def wma(series: pd.Series, length: int = 20) -> pd.Series:
    """Weighted moving average (linear weights)."""
    weights = np.arange(1, length + 1, dtype=float)
    return series.rolling(length, min_periods=1).apply(
        lambda window: float(np.dot(window, weights[-len(window):]) / weights[-len(window):].sum()),
        raw=True,
    )


def _rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder's smoothing (RMA): SMA seed, then EMA with alpha = 1/length."""
    values = series.to_numpy(dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    if n < length:
        return pd.Series(out, index=series.index)
    seed = float(np.mean(values[:length]))
    out[length - 1] = seed
    if n > length:
        # prepend the seed so ewm continues the Wilder recursion exactly
        combined = np.concatenate(([seed], values[length:]))
        smoothed = pd.Series(combined).ewm(alpha=1.0 / length, adjust=False).mean().to_numpy()
        out[length:] = smoothed[1:]
    return pd.Series(out, index=series.index)


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder) in 0..100."""
    # NOTE: numpy first. `Series.clip`/`where`/`mask` hand their condition to
    # `pandas.core.common.apply_if_callable`, which *invokes* the condition when
    # it looks callable. minibt sets `pd.Series.__call__`, so the boolean mask
    # would be invoked and silently misaligned. See tests/test_pandas_traps.py.
    values = np.asarray(series, dtype=float)
    delta = np.diff(values)
    index = series.index[1:]
    gain = pd.Series(np.clip(delta, 0.0, None), index=index)
    loss = pd.Series(np.clip(-delta, 0.0, None), index=index)
    avg_gain = _rma(gain, length)
    avg_loss = _rma(loss, length)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return (100 - (100 / (1 + rs))).reindex(series.index)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """Moving Average Convergence/Divergence.

    Returns ``{'macd': Series, 'signal': Series, 'histogram': Series}``.
    """
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': macd_line - signal_line,
    }


def bollinger(series: pd.Series, length: int = 20, std: float = 2) -> dict:
    """Bollinger bands. Returns ``{'upper', 'middle', 'lower'}``."""
    middle = sma(series, length)
    deviation = series.rolling(length, min_periods=1).std(ddof=0)
    return {
        'upper': middle + std * deviation,
        'middle': middle,
        'lower': middle - std * deviation,
    }


def stochastic(df: pd.DataFrame, k: int = 14, d: int = 3, smooth: int = 3) -> dict:
    """Stochastic oscillator %K/%D in 0..100."""
    lowest = df['low'].rolling(k, min_periods=1).min()
    highest = df['high'].rolling(k, min_periods=1).max()
    raw_k = 100 * (df['close'] - lowest) / (highest - lowest).replace(0.0, np.nan)
    k_line = raw_k.rolling(smooth, min_periods=1).mean()
    return {'k': k_line.fillna(50.0), 'd': k_line.rolling(d, min_periods=1).mean().fillna(50.0)}


def _true_range(df: pd.DataFrame) -> pd.Series:
    previous_close = df['close'].shift()
    return pd.concat([
        df['high'] - df['low'],
        (df['high'] - previous_close).abs(),
        (df['low'] - previous_close).abs(),
    ], axis=1).max(axis=1)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average True Range (Wilder smoothing)."""
    return _rma(_true_range(df), length)


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume weighted average price (cumulative)."""
    typical = (df['high'] + df['low'] + df['close']) / 3
    volume = df['volume'].astype(float) if 'volume' in df else pd.Series(1.0, index=df.index)
    return (typical * volume).cumsum() / volume.cumsum().replace(0.0, np.nan)


def donchian(df: pd.DataFrame, length: int = 20) -> dict:
    """Donchian channel. Returns ``{'upper', 'middle', 'lower'}``."""
    upper = df['high'].rolling(length, min_periods=1).max()
    lower = df['low'].rolling(length, min_periods=1).min()
    return {'upper': upper, 'middle': (upper + lower) / 2, 'lower': lower}


def typical_price(df: pd.DataFrame) -> pd.Series:
    """(high + low + close) / 3."""
    return (df['high'] + df['low'] + df['close']) / 3


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On Balance Volume: cumulative signed volume.

    The first bar contributes its whole volume, matching TA-Lib/TradingView.
    """
    # built in numpy so nothing writes into a slice of the caller's data
    prices = np.asarray(close, dtype=float)
    volumes = np.asarray(volume, dtype=float)
    direction = np.sign(np.concatenate(([0.0], np.diff(prices))))
    contribution = direction * volumes
    if len(contribution):
        contribution[0] = volumes[0]
    return pd.Series(np.cumsum(contribution), index=close.index)


def roc(series: pd.Series, length: int = 12) -> pd.Series:
    """Rate of Change in percent."""
    return (series / series.shift(length) - 1) * 100


def williams_r(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Williams %R in -100..0."""
    highest = df['high'].rolling(length, min_periods=length).max()
    lowest = df['low'].rolling(length, min_periods=length).min()
    return -100 * (highest - df['close']) / (highest - lowest).replace(0.0, np.nan)


def cci(df: pd.DataFrame, length: int = 20) -> pd.Series:
    """Commodity Channel Index."""
    price = typical_price(df)
    average = price.rolling(length, min_periods=length).mean()
    deviation = price.rolling(length, min_periods=length).apply(
        lambda window: float(np.abs(window - window.mean()).mean()), raw=True)
    return (price - average) / (0.015 * deviation.replace(0.0, np.nan))


def keltner(df: pd.DataFrame, length: int = 20, multiplier: float = 2.0,
            atr_length: int = 10) -> dict:
    """Keltner channel: EMA ± multiplier × ATR. Returns upper/middle/lower."""
    middle = ema(df['close'], length)
    band = atr(df, atr_length) * multiplier
    return {'upper': middle + band, 'middle': middle, 'lower': middle - band}


def adx(df: pd.DataFrame, length: int = 14) -> dict:
    """Average Directional Index (Wilder). Returns adx / plus_di / minus_di.

    The Wilder accumulation starts on the *second* bar, matching TA-Lib, so the
    first ADX value lands at index ``2 * length - 1``.
    """
    up_move = np.concatenate(([np.nan], np.diff(np.asarray(df['high'], dtype=float))))
    down_move = np.concatenate(([np.nan], -np.diff(np.asarray(df['low'], dtype=float))))
    index = df.index[1:]                      # the accumulation starts on bar 2
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)[1:],
                        index=index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)[1:],
                         index=index)
    true_range = pd.Series(np.asarray(_true_range(df), dtype=float)[1:], index=index)

    average_range = _rma(true_range, length)
    plus_di = 100 * _rma(plus_dm, length) / average_range
    minus_di = 100 * _rma(minus_dm, length) / average_range
    denominator = (plus_di + minus_di).replace(0.0, np.nan)
    # drop the directional-index warm-up so the ADX seed is a real mean
    dx = (100 * (plus_di - minus_di).abs() / denominator).dropna()
    return {
        'adx': _rma(dx, length).reindex(df.index),
        'plus_di': plus_di.reindex(df.index),
        'minus_di': minus_di.reindex(df.index),
    }


def mfi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Money Flow Index in 0..100."""
    price = np.asarray(typical_price(df), dtype=float)
    flow = price * np.asarray(df['volume'], dtype=float)
    previous = np.concatenate(([np.nan], price[:-1]))
    positive = pd.Series(np.where(price > previous, flow, 0.0), index=df.index)
    negative = pd.Series(np.where(price < previous, flow, 0.0), index=df.index)
    positive = positive.rolling(length, min_periods=length).sum()
    negative = negative.rolling(length, min_periods=length).sum().replace(0.0, np.nan)
    return 100 - 100 / (1 + positive / negative)


def swing_points(high: pd.Series, low: pd.Series, length: int = 5,
                 time=None) -> pd.DataFrame:
    """Fractal swing highs and lows ("波段高低点").

    A bar is a swing high when its high is the highest of the `length` bars on
    either side (a swing low likewise for the low). This is the classic
    `length`-bar fractal: deterministic and non-repainting, but a pivot is only
    *confirmed* `length` bars later - the newest `length` bars can still change.

    :param high/low: the price series (same length).
    :param length: bars on each side of the pivot (default 5).
    :param time: values for the `time` column (e.g. ``chart.candle_data['time']``);
        defaults to the index.
    :return: a frame with `time` / `price` / `kind` (`'high'` or `'low'`),
        ordered by time.

    Display it with :meth:`AbstractChart.mark_swings` or by hand::

        swings = swing_points(df['high'], df['low'], length=5)
        for row in swings.itertuples():
            chart.marker(row.time, position='above' if row.kind == 'high' else 'below',
                         shape='arrow_down' if row.kind == 'high' else 'arrow_up',
                         text=f'{row.price:.2f}')
    """
    if length < 1:
        raise ValueError(f'length must be at least 1, not {length}')
    high = pd.Series(high).reset_index(drop=True).astype(float)
    low = pd.Series(low).reset_index(drop=True).astype(float)
    if len(high) != len(low):
        raise ValueError('high and low must have the same length')
    times = (pd.Series(time).reset_index(drop=True) if time is not None
             else pd.Series(high.index))

    window = 2 * length + 1
    highest = high.rolling(window, center=True).max()
    lowest = low.rolling(window, center=True).min()
    is_high = (high == highest) & high.notna()
    is_low = (low == lowest) & low.notna()
    # a flat window is not a swing at all (and would flag every bar of the run)
    is_high &= highest != lowest
    is_low &= highest != lowest
    is_high &= ~is_high.shift(1, fill_value=False)
    is_low &= ~is_low.shift(1, fill_value=False)

    rows = [
        {'time': times[i], 'price': float(high[i]), 'kind': 'high'}
        for i in range(len(high)) if is_high[i]
    ]
    rows += [
        {'time': times[i], 'price': float(low[i]), 'kind': 'low'}
        for i in range(len(low)) if is_low[i]
    ]
    frame = pd.DataFrame(rows, columns=['time', 'price', 'kind'])
    return frame.sort_values('time').reset_index(drop=True)


def zigzag(high: pd.Series, low: pd.Series, threshold: float = 0.03,
           time=None, include_unconfirmed: bool = False) -> pd.DataFrame:
    """ZigZag swing pivots: alternate high/low after a minimum move.

    This is the "波段线" algorithm of most trading software: from the running
    extreme, a retracement of more than `threshold` (a **fraction**, ``0.03`` =
    3%) confirms the extreme as a pivot and flips the direction, so the result
    always alternates high, low, high, ... and small wiggles are ignored - which
    is what `swing_points` (fixed `length`-bar fractals) cannot do.

    :param high/low: the price series (same length).
    :param threshold: minimum retracement to confirm a reversal (fraction > 0).
    :param time: values for the `time` column (e.g. ``chart.candle_data['time']``).
    :param include_unconfirmed: also return the running extreme of the last,
        still open leg (the classic ZigZag draws it; it **repaints** until a
        reversal confirms it).
    :return: a frame with `time` / `price` / `kind` (`'high'` / `'low'`) /
        `confirmed` (``False`` only for that last leg). Feed it to
        :meth:`AbstractChart.mark_swings` or :meth:`AbstractChart.add_zigzag`.

    Handy when analysing structure: alternating pivots give you leg sizes,
    retracement ratios and higher-high / lower-low sequences.
    """
    if threshold <= 0:
        raise ValueError(f'threshold must be positive, not {threshold}')
    high = pd.Series(high).reset_index(drop=True).astype(float)
    low = pd.Series(low).reset_index(drop=True).astype(float)
    if len(high) != len(low):
        raise ValueError('high and low must have the same length')
    if len(high) == 0:
        return pd.DataFrame(columns=['time', 'price', 'kind', 'confirmed'])
    times = (pd.Series(time).reset_index(drop=True) if time is not None
             else pd.Series(high.index))

    h = high.to_numpy()
    l = low.to_numpy()
    pivots = []                       # (index, price, kind)
    trend = 0                         # +1 up, -1 down, 0 = not decided yet
    # while the direction is unknown both extremes are tracked, so the index of
    # each has to be kept separately (an index shared by both would point at
    # whichever extreme moved last)
    ext_h, ext_hi = h[0], 0
    ext_l, ext_lo = l[0], 0
    for i in range(1, len(h)):
        if trend >= 0 and h[i] >= ext_h:
            ext_h, ext_hi = h[i], i         # rising: keep the highest high
        if trend <= 0 and l[i] <= ext_l:
            ext_l, ext_lo = l[i], i         # falling: keep the lowest low
        if trend == 0:
            # the first move beyond the threshold decides the initial direction
            if l[i] <= ext_h * (1 - threshold):
                pivots.append((ext_hi, ext_h, 'high'))
                trend, ext_l, ext_lo = -1, l[i], i
            elif h[i] >= ext_l * (1 + threshold):
                pivots.append((ext_lo, ext_l, 'low'))
                trend, ext_h, ext_hi = 1, h[i], i
        elif trend > 0 and l[i] <= ext_h * (1 - threshold):
            pivots.append((ext_hi, ext_h, 'high'))
            trend, ext_l, ext_lo = -1, l[i], i
        elif trend < 0 and h[i] >= ext_l * (1 + threshold):
            pivots.append((ext_lo, ext_l, 'low'))
            trend, ext_h, ext_hi = 1, h[i], i

    rows = [{'time': times[i], 'price': float(price), 'kind': kind,
             'confirmed': True} for i, price, kind in pivots]
    if include_unconfirmed and trend != 0:
        up = trend > 0
        rows.append({'time': times[ext_hi if up else ext_lo],
                     'price': float(ext_h if up else ext_l),
                     'kind': 'high' if up else 'low', 'confirmed': False})
    return pd.DataFrame(rows, columns=['time', 'price', 'kind', 'confirmed'])
