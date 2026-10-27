"""A second symbol on its own price scale (a pylightcharts extension).

The official
`Two Price Scales <https://tradingview.github.io/lightweight-charts/tutorials/how_to/two-price-scales>`_
tutorial makes both the right and the left price scale visible and assigns the
second series to the left one. This does the same, keeping the main candles on
the **right** axis (the usual habit) and giving the overlay the **left** one:

.. code-block:: python

    chart.set(btc)                                     # main candles, right axis
    chart.add_symbol('ETHUSDT', eth, kind='candles')   # candles on the left axis
    chart.add_symbol('BTC/GLD', ratio, kind='line')    # or a line/area/bar

Both scales autoscale their own series, so the two symbols share the pane. To
stack them instead of overlapping them, hand out vertical shares with
``margins=`` (the overlay) and :meth:`AbstractChart.scale_margins` (the main
series): ``margins=(0.55, 0.0)`` keeps a symbol in the lower 45% of the pane.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple, Union

import pandas as pd

#: ``kind=`` -> the built-in series type it maps to (see :meth:`add_series`)
KINDS = {
    'candles': 'Candlestick', 'candlestick': 'Candlestick',
    'bars': 'Bar', 'bar': 'Bar',
    'line': 'Line', 'area': 'Area', 'baseline': 'Baseline',
    'histogram': 'Histogram',
}

#: kinds whose data has OHLC columns instead of one value column
OHLC_KINDS = ('Candlestick', 'Bar')

#: the four columns a bar needs
OHLC_COLUMNS = ('open', 'high', 'low', 'close')

#: where a single-value frame hides its numbers, in the order they are tried
VALUE_COLUMNS = ('value', 'close', 'price')


def _kind(kind: str) -> str:
    """Validate ``kind=`` (a typo raises deep inside the bridge otherwise)."""
    try:
        return KINDS[str(kind).lower()]
    except KeyError:
        raise ValueError(
            f'kind must be one of {sorted(KINDS)}, not {kind!r}') from None


def _scale(scale: str) -> str:
    """Validate ``scale=``; anything but left/right is an overlay scale."""
    if not isinstance(scale, str) or not scale:
        raise ValueError(f'scale must be a non-empty string, not {scale!r}')
    return scale


def _value_column(frame: pd.DataFrame, name: str) -> str:
    """The one numeric column of a single-value frame."""
    for candidate in VALUE_COLUMNS + (name,):
        if candidate in frame.columns:
            return candidate
    numeric = [column for column in frame.columns
               if column != 'time'
               and pd.api.types.is_numeric_dtype(frame[column])]
    if len(numeric) != 1:
        raise ValueError(
            f'cannot tell which column holds the values of {name!r}: '
            f'{list(frame.columns)} - pass value_column=')
    return numeric[0]


def frame_for(data, name: str, kind: str, value_column: Optional[str] = None
              ) -> pd.DataFrame:
    """Shape `data` for :meth:`SeriesCommon.set`.

    ``set()`` matches single-value series by column name, so the value
    column is renamed to the symbol; bars keep their OHLC columns as they are.
    """
    if isinstance(data, pd.Series):
        data = data.to_frame(value_column or 'value')
    if not isinstance(data, pd.DataFrame):
        data = pd.DataFrame(data)
    if kind in OHLC_KINDS:
        missing = [column for column in OHLC_COLUMNS
                   if column not in data.columns]
        if missing:
            raise ValueError(
                f'a {kind.lower()} overlay needs the columns '
                f'{list(OHLC_COLUMNS)}, missing {missing}')
        return data
    if name and name not in data.columns:
        data = data.rename(
            columns={value_column or _value_column(data, name): name})
    return data


def add_symbol(chart, name: str, data=None, *, kind: str = 'candles',
               scale: str = 'left',
               margins: Optional[Tuple[float, float]] = None,
               value_column: Optional[str] = None,
               up_color: Optional[str] = None,
               down_color: Optional[str] = None,
               color: Optional[str] = None,
               line_width: Optional[float] = None,
               price_line: bool = True, price_label: bool = True,
               legend_toggle: bool = True, **options):
    """Add `data` as a second symbol on its own price scale.

    :param name: the symbol; it labels the legend row and the price line.
    :param data: a DataFrame (time + value, or time + OHLC for a bar), a Series
        whose index is the time, or ``None`` to fill it later with ``set()``.
    :param kind: ``'candles'`` (default) / ``'bars'`` / ``'line'`` /
        ``'area'`` / ``'baseline'`` / ``'histogram'``.
    :param scale: ``'left'`` (default) or ``'right'``; any other id becomes an
        *overlay* scale with no axis of its own (that is how the volume series
        works), so ``'left'`` / ``'right'`` are the ones with a visible scale.
    :param margins: ``(top, bottom)`` share of the pane to keep the scale in,
        e.g. ``(0.55, 0.0)`` for the lower 45% (see
        :meth:`AbstractChart.scale_margins` for the other one).
    :param value_column: which column holds the values of a single-value frame
        when it cannot be guessed.
    :param up_color/down_color: candle / bar colours (borders and wicks follow
        unless they are set explicitly in ``options``).
    :param color/line_width: the line / area colour and width.
    :param price_line/price_label: draw the price line and its label (the label
        shows `name`, which is what makes the two axes readable).
    :return: the created series (a :class:`BridgeSeries`).
    """
    series_kind = _kind(kind)
    # `price_scale_id` is the engine-side spelling of `scale`; accept either
    scale = _scale(options.pop('price_scale_id', scale))
    # the scale has to be visible before a series can use it; the tutorial does
    # this through chart options, `priceScale(id)` is the per-scale way
    scale_handle = chart.get_price_scale(scale)
    scale_handle.apply_options(visible=True)
    if margins is not None:
        top, bottom = margins
        scale_handle.apply_options(
            scale_margins={'top': top, 'bottom': bottom})

    style = dict(options)
    if series_kind in OHLC_KINDS:
        if up_color or down_color:
            up = up_color or '#26A69A'
            down = down_color or '#EF5350'
            for key, value in (('up_color', up), ('down_color', down),
                               ('border_up_color', up),
                               ('border_down_color', down),
                               ('wick_up_color', up),
                               ('wick_down_color', down)):
                style.setdefault(key, value)
    else:
        if color:
            style.setdefault('color', color)
        if line_width:
            style.setdefault('line_width', line_width)
    style.setdefault('price_scale_id', scale)
    # 价格线 / 价格标签 / 标题直接在建系列时给（camelCase 由引擎转换）。
    # 原来是建完再 `series.price_line(label_visible=..., line_visible=...,
    # title=...)` —— 那是第二次 `applyOptions`，快速切页 / 连续重建时那个句柄
    # 可能已经被删掉，LWC 会抛 `Value is null`（控制台里 `[pylightcharts]
    # Error ... Value is null`，script 就是那条 applyOptions）。
    style.setdefault('price_line_visible', price_line)
    style.setdefault('last_value_visible', price_label)
    if name:
        style.setdefault('title', name)
    series = chart.add_series(series_kind, name, legend_toggle=legend_toggle,
                              **style)
    if data is not None:
        series.set(frame_for(data, name, series_kind, value_column))
    return series
