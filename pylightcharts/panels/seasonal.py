"""SeasonalChart panel: seasonality bars (average performance per period).

The library draws the bars; the aggregation is a small helper here::

    import pandas as pd
    from pylightcharts import SeasonalChart

    chart = SeasonalChart(my_window)
    chart.from_frame(df)                 # df with time + close columns
    # or set the numbers yourself:
    chart.set_data([1.2, -0.4, 2.1, ...], labels=['1月', '2月', ...])

:func:`seasonal_monthly` computes the average month-of-year return of a price
series (each month's last-vs-previous-month last, averaged across years).
"""
from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd

from .base import Panel


def _resample_last(series: pd.Series) -> pd.Series:
    """Month-end ``last``, compatible with pandas 2.2 (``ME``) and older (``M``)."""
    for rule in ('ME', 'M'):
        try:
            return series.resample(rule).last()
        except ValueError:                       # unknown rule on this pandas
            continue
    return series.resample('M').last()           # pragma: no cover - fallback


def seasonal_monthly(
    frame: pd.DataFrame,
    *,
    time_col: str = 'time',
    value_col: str = 'close',
    percent: bool = True,
) -> dict:
    """Average month-of-year return of ``value_col`` (a series of closes/values).

    Returns ``{'labels': ['1月', ...], 'values': [...]}``; the values are percent
    by default, and months that never appear are ``None``.
    """
    data = frame[[time_col, value_col]].copy()
    data[time_col] = pd.to_datetime(data[time_col])
    data = data.dropna().sort_values(time_col).set_index(time_col)
    monthly = _resample_last(data[value_col].astype('float64'))
    returns = monthly.pct_change().dropna()
    grouped = returns.groupby(returns.index.month).mean()
    labels = [f'{month}月' for month in range(1, 13)]
    scale = 100.0 if percent else 1.0
    values = [float(grouped[month]) * scale if month in grouped.index else None
              for month in range(1, 13)]
    return {'labels': labels, 'values': values}


class SeasonalChart(Panel):
    """A seasonality bar chart.

    :param values: numbers, or ``{label, value}`` points.
    :param labels: period labels (used when ``values`` are plain numbers).
    :param percent: add ``%`` to the bar labels (default True).
    :param on_item_click: not supported (bars are not interactive).
    """

    def __init__(
        self,
        window,
        values: Optional[Sequence] = None,
        labels: Optional[Sequence[str]] = None,
        *,
        color_scheme: str = 'cn',
        show_values: bool = True,
        show_zero_line: bool = True,
        decimals: int = 2,
        percent: bool = True,
        padding: int = 1,
        theme: Optional[dict] = None,
        container: Optional[str] = None,
    ):
        super().__init__(window)
        options: dict = {
            'colorScheme': color_scheme,
            'showValues': show_values,
            'showZeroLine': show_zero_line,
            'decimals': decimals,
            'percent': percent,
            'padding': padding,
        }
        if values is not None:
            options['values'] = list(values)
        if labels is not None:
            options['labels'] = list(labels)
        if theme:
            options['theme'] = theme
        self._create('SeasonalChart', options, container)

    def set_data(self, values: Sequence, labels: Optional[Sequence[str]] = None
                 ) -> 'SeasonalChart':
        if labels is None:
            self._set('setData', list(values))
        else:
            self._set('setData', list(values), list(labels))
        return self

    def from_frame(self, frame: pd.DataFrame, *, time_col: str = 'time',
                   value_col: str = 'close',
                   percent: bool = True) -> 'SeasonalChart':
        """Aggregate ``frame`` into month-of-year seasonality and draw it."""
        data = seasonal_monthly(frame, time_col=time_col, value_col=value_col,
                                percent=percent)
        self.set_options(percent=percent)
        self.set_data(data['values'], data['labels'])
        return self

    def set_options(self, **options) -> 'SeasonalChart':
        self._set('setOptions', options)
        return self

    def apply_theme(self, spec: dict) -> None:
        theme = {
            'background': spec.get('background'),
            'text': spec.get('text'),
            'muted': spec.get('crosshair'),
        }
        theme = {key: value for key, value in theme.items() if value}
        if theme:
            self._set('setOptions', {'theme': theme})
