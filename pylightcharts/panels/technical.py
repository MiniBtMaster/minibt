"""Technical Analysis panel: a buy/sell gauge, a summary and indicator tables.

The library computes nothing about markets by default; :func:`ta_summary` is a
small, self-contained helper that turns a price frame into the widget's data
(7 oscillators + 11 moving averages), and :class:`TechnicalAnalysis` renders
whatever the host supplies::

    from pylightcharts import TechnicalAnalysis
    from pylightcharts.panels import ta_summary

    ta = TechnicalAnalysis(chart.win, ta_summary(df))

    # ...or feed signals computed elsewhere:
    ta.set_data({
        'score': 0.32, 'counts': {'buy': 10, 'neutral': 3, 'sell': 2},
        'oscillators': [{'name': 'RSI(14)', 'value': 56.3, 'signal': 'buy'}],
        'moving_averages': [{'name': 'MA10', 'value': 190.2, 'signal': 'buy'}],
    })
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from .base import Panel

__all__ = ['TechnicalAnalysis', 'ta_summary', 'TA_MA_PERIODS']

#: moving-average periods used by :func:`ta_summary`
TA_MA_PERIODS = (5, 10, 20, 50, 100, 200)


# --------------------------------------------------------------- 指标计算
def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - 100 / (1 + rs)


def _macd(series: pd.Series) -> tuple:
    line = _ema(series, 12) - _ema(series, 26)
    return line, _ema(line, 9)


def _cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    typical = (df['high'] + df['low'] + df['close']) / 3
    ma = typical.rolling(period).mean()
    mad = (typical - ma).abs().rolling(period).mean()
    return (typical - ma) / (0.015 * mad)


def _stoch(df: pd.DataFrame, period: int = 14) -> pd.Series:
    low = df['low'].rolling(period).min()
    high = df['high'].rolling(period).max()
    return 100 * (df['close'] - low) / (high - low)


def _williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df['high'].rolling(period).max()
    low = df['low'].rolling(period).min()
    return -100 * (high - df['close']) / (high - low)


def _adx(df: pd.DataFrame, period: int = 14) -> tuple:
    up = df['high'].diff()
    down = -df['low'].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / period, adjust=False).mean(), plus_di, minus_di


def _last(series) -> Optional[float]:
    try:
        value = float(series.iloc[-1])
    except (TypeError, ValueError, IndexError):
        return None
    return None if math.isnan(value) else value


def _tristate(value, buy_when_above=None, sell_when_below=None) -> str:
    if buy_when_above is not None and value > buy_when_above:
        return 'buy'
    if sell_when_below is not None and value < sell_when_below:
        return 'sell'
    return 'neutral'


def ta_summary(frame: pd.DataFrame, *, price: str = 'close') -> dict:
    """Compute a TradingView-style summary from a price frame.

    ``frame`` needs a ``price`` column (default ``close``); ``high`` / ``low`` are
    used when present (otherwise the close is used for both). Returns
    ``{score, counts, oscillators, moving_averages}`` — feed it straight to
    :class:`TechnicalAnalysis`.
    """
    close = pd.to_numeric(frame[price], errors='coerce').astype(float)
    high = (pd.to_numeric(frame['high'], errors='coerce').astype(float)
            if 'high' in frame.columns else close)
    low = (pd.to_numeric(frame['low'], errors='coerce').astype(float)
           if 'low' in frame.columns else close)
    df = pd.DataFrame({'close': close, 'high': high, 'low': low}).dropna()
    df = df.reset_index(drop=True)
    empty = {'score': 0.0, 'counts': {'buy': 0, 'neutral': 0, 'sell': 0},
             'oscillators': [], 'moving_averages': []}
    if len(df) < 2:
        return empty
    last = float(df['close'].iloc[-1])

    oscillators: list = []

    def add(name: str, value: Optional[float], signal: str) -> None:
        if value is None:
            return
        oscillators.append({'name': name, 'value': round(float(value), 4),
                            'signal': signal})

    rsi = _last(_rsi(df['close']))
    if rsi is not None:
        add('RSI(14)', rsi, _tristate(rsi, buy_when_above=50, sell_when_below=50))
    stoch = _last(_stoch(df))
    if stoch is not None:
        add('STOCH %K', stoch, _tristate(stoch, 50, 50))
    cci = _last(_cci(df))
    if cci is not None:
        add('CCI(20)', cci, _tristate(cci, 0, 0))
    williams = _last(_williams_r(df))
    if williams is not None:
        add('Williams %R', williams, _tristate(williams, -50, -50))
    momentum = _last(df['close'] - df['close'].shift(10))
    if momentum is not None:
        add('Momentum(10)', momentum, _tristate(momentum, 0, 0))
    macd_line, macd_signal = _macd(df['close'])
    macd_value = _last(macd_line)
    if macd_value is not None:
        signal_series = _last(macd_signal)
        signal = ('buy' if signal_series is not None and macd_value > signal_series
                  else 'sell')
        add('MACD(12,26,9)', macd_value, signal)
    adx, plus_di, minus_di = _adx(df)
    adx_value = _last(adx)
    if adx_value is not None:
        pd_value, md_value = _last(plus_di), _last(minus_di)
        if adx_value < 20 or pd_value is None or md_value is None:
            signal = 'neutral'
        else:
            signal = 'buy' if pd_value > md_value else 'sell'
        add('ADX(14)', adx_value, signal)

    moving_averages: list = []

    def add_ma(prefix: str, period: int, series: pd.Series) -> None:
        value = _last(series)
        if value is None:
            return
        moving_averages.append({
            'name': f'{prefix}{period}', 'value': round(value, 4),
            'signal': 'buy' if last > value else 'sell'})

    for period in TA_MA_PERIODS:
        add_ma('MA', period, _sma(df['close'], period))
    for period in TA_MA_PERIODS:
        add_ma('EMA', period, _ema(df['close'], period))

    signals = [row['signal'] for row in oscillators + moving_averages]
    weights = {'buy': 1.0, 'neutral': 0.0, 'sell': -1.0}
    score = sum(weights.get(signal, 0.0) for signal in signals) / len(signals) \
        if signals else 0.0
    counts = {name: signals.count(name) for name in ('buy', 'neutral', 'sell')}
    return {'score': round(score, 4), 'counts': counts,
            'oscillators': oscillators, 'moving_averages': moving_averages}


class TechnicalAnalysis(Panel):
    """Gauge + summary + oscillator / moving-average tables.

    :param data: ``{score, label?, counts, oscillators, moving_averages}`` (see
        :func:`ta_summary`).
    """

    def __init__(
        self,
        window,
        data: Optional[dict] = None,
        *,
        decimals: int = 2,
        theme: Optional[dict] = None,
        container: Optional[str] = None,
    ):
        super().__init__(window)
        options: dict = {'decimals': decimals}
        if data:
            options.update(data)
        if theme:
            options['theme'] = theme
        self._create('TechnicalAnalysis', options, container)

    def set_data(self, data: dict) -> 'TechnicalAnalysis':
        self._set('setData', data)
        return self

    def set_options(self, **options) -> 'TechnicalAnalysis':
        self._set('setOptions', options)
        return self

    def apply_theme(self, spec: dict) -> None:
        theme = {
            'background': spec.get('background'),
            'text': spec.get('text'),
            'muted': spec.get('crosshair'),
            'border': spec.get('border_color'),
        }
        theme = {key: value for key, value in theme.items() if value}
        if theme:
            self._set('setOptions', {'theme': theme})
