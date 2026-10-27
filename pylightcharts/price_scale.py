"""Price-scale and price-line handles."""
from __future__ import annotations

from typing import Optional

from .util import PRICE_SCALE_MODE, as_enum, ref


class PriceScale:
    """A handle to a chart price scale, e.g. ``chart.get_price_scale('left')``.

    `price_scale_id` is any id known to lightweight-charts: ``'left'``, ``'right'``,
    or a custom id used through a series' ``price_scale_id``.
    """

    def __init__(self, chart: 'AbstractChart', price_scale_id: str = 'right',
                 pane_index: Optional[int] = None):
        self._chart = chart
        self.price_scale_id = price_scale_id
        self.pane_index = pane_index
        if pane_index is None:
            self.id = f'{chart.id}.priceScale.{price_scale_id}'
            chart.win.invoke(f'{chart.id}.chart', 'priceScale', price_scale_id, store_as=self.id)
        else:
            self.id = f'{chart.id}.pane{pane_index}.priceScale.{price_scale_id}'
            chart.win.invoke(chart._pane_handle(pane_index), 'priceScale', price_scale_id, store_as=self.id)

    def apply_options(self, **options):
        """Apply arbitrary price-scale options (snake_case keys are camelCased)."""
        if 'invert_scale' in options or 'invertScale' in options:
            # remember it: the swing helpers flip their markers when the scale
            # is inverted, and reading it back needs a live webview
            self._chart._price_scale_inverted = bool(
                options.get('invert_scale', options.get('invertScale')))
        self._chart.win.invoke(self.id, 'applyOptions', options)

    def options(self) -> dict:
        """Read the price scale's current (merged) options."""
        return self._chart.win.invoke_get(self.id, 'options')

    def set_mode(self, mode: PRICE_SCALE_MODE = 'normal'):
        """normal / logarithmic / percentage / index100."""
        self.apply_options(mode=as_enum(mode, PRICE_SCALE_MODE))

    def invert(self, inverted: bool = True):
        self.apply_options(invert_scale=inverted)

    def set_visible_range(self, min_value: float, max_value: float):
        self._chart.win.invoke(self.id, 'setVisibleRange', {'from': min_value, 'to': max_value})

    def get_visible_range(self) -> Optional[dict]:
        """The price range currently visible on this scale."""
        return self._chart.win.invoke_get(self.id, 'getVisibleRange')

    def set_auto_scale(self, auto_scale: bool = True):
        """Enable/disable automatic scaling."""
        self._chart.win.invoke(self.id, 'setAutoScale', auto_scale)

    def width(self) -> float:
        return self._chart.win.invoke_get(self.id, 'width')


class PriceLine:
    """A horizontal price line, created via :meth:`SeriesCommon.create_price_line`."""

    def __init__(self, series: 'SeriesCommon', handle: str):
        self._series = series
        self.id = handle

    def apply_options(self, **options):
        """Apply arbitrary price line options (snake_case keys are camelCased)."""
        self._series.win.invoke(self.id, 'applyOptions', options)

    def options(self) -> dict:
        return self._series.win.invoke_get(self.id, 'options')

    def remove(self):
        """Delete this price line from the chart."""
        self._series.win.invoke(f'{self._series.id}.series', 'removePriceLine', ref(self.id))
        if self in self._series._price_lines:
            self._series._price_lines.remove(self)
