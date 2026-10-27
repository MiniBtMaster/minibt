"""Sparkline panel: a tiny canvas line/area chart.

Unlike the charts of this package a sparkline is a single ``<canvas>`` (no
Lightweight Charts instance), so hundreds of them - one per table row - stay
cheap::

    from pylightcharts import QtPanel
    from pylightcharts.panels import Sparkline

    panel = QtPanel()
    spark = Sparkline(panel.win, width=160, height=40)
    spark.set_data([1, 2, 1.5, 3, 2.5, 4])
"""
from __future__ import annotations

from typing import Optional, Sequence

from .base import Panel


class Sparkline(Panel):
    """A canvas sparkline.

    :param window: the :class:`~pylightcharts.Window` to create it on.
    :param width: width in CSS pixels (default 120).
    :param height: height in CSS pixels (default 32).
    :param baseline: colour the line by ``'first'`` (last vs first value,
        default), ``'zero'`` (last vs 0) or ``'none'`` (always ``line_color``).
    :param container: JS expression of the element to append to; defaults to
        ``window.containerDiv``.
    """

    def __init__(
        self,
        window,
        *,
        width: int = 120,
        height: int = 32,
        line_color: Optional[str] = None,
        fill_color: Optional[str] = None,
        up_color: Optional[str] = None,
        down_color: Optional[str] = None,
        line_width: Optional[float] = None,
        baseline: str = 'first',
        padding: Optional[int] = None,
        end_dot: bool = False,
        container: Optional[str] = None,
    ):
        super().__init__(window)
        options: dict = {
            'width': width,
            'height': height,
            'baseline': baseline,
            'endDot': end_dot,
        }
        if line_color is not None:
            options['lineColor'] = line_color
        if fill_color is not None:
            options['fillColor'] = fill_color
        if up_color is not None:
            options['upColor'] = up_color
        if down_color is not None:
            options['downColor'] = down_color
        if line_width is not None:
            options['lineWidth'] = line_width
        if padding is not None:
            options['padding'] = padding
        self._create('Sparkline', options, container or 'window.containerDiv')

    def set_data(self, values: Sequence[float]) -> 'Sparkline':
        """Replace the data and redraw."""
        self._set('setData', list(values))
        return self

    def set_options(self, **options) -> 'Sparkline':
        """Update colours / sizing options (JS option names, e.g. ``lineColor``)."""
        self._set('setOptions', options)
        return self

    def re_size(self, width: int, height: int) -> 'Sparkline':
        self._set('reSize', width, height)
        return self

    def apply_theme(self, spec: dict) -> None:
        """Follow the window theme's up/down colours (background is transparent)."""
        options = {}
        if spec.get('up'):
            options['upColor'] = spec['up']
        if spec.get('down'):
            options['downColor'] = spec['down']
        if options:
            self._set('setOptions', options)
