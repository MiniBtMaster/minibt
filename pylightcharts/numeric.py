"""Charts whose horizontal axis is numeric rather than time.

- :class:`YieldCurveChart` — x axis is duration in months (only Line/Area)
- :class:`OptionsChart` — x axis is price (option chains, distributions)

They share the whole `AbstractChart` surface (panes, options, drawings, custom
series) except the candlestick/volume machinery, which does not exist here.
Data points use a numeric ``time``::

    chart = YieldCurveChart()
    curve = chart.add_series('Line', 'rate')
    curve.set(pd.DataFrame({'time': [1, 3, 12], 'rate': [4.2, 4.0, 3.6]}))
"""
from __future__ import annotations

from typing import Optional, Union

from .abstract import AbstractChart
from .chart import Chart


class _NumericMixin:
    _time_based = False

    def set(self, df=None, keep_drawings: bool = False):
        raise TypeError(
            f'{type(self).__name__} has no candlestick series. Create one with '
            "chart.add_series('Line', '<column>') and call series.set(df)."
        )

    def add_curve(self, name: str = '', kind: str = 'Line',
                  pane_index: Optional[Union[int, str]] = None, **options):
        """Add a Line/Area series to a numeric-x chart and return it."""
        return self.add_series(kind, name, pane_index=pane_index, **options)


class YieldCurveChart(_NumericMixin, Chart):
    """Yield curve chart: the horizontal axis is a duration in months."""

    _chart_kind = 'yield-curve'


class OptionsChart(_NumericMixin, Chart):
    """Options chart: the horizontal axis is a price."""

    _chart_kind = 'options'


class AbstractYieldCurveChart(_NumericMixin, AbstractChart):
    """Backend-agnostic yield curve chart (see :class:`YieldCurveChart`)."""

    _chart_kind = 'yield-curve'


class AbstractOptionsChart(_NumericMixin, AbstractChart):
    """Backend-agnostic options chart (see :class:`OptionsChart`)."""

    _chart_kind = 'options'
