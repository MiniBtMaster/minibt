"""Declarative primitives built from JSON specs + registered JS callbacks.

Lightweight Charts primitives (`ISeriesPrimitive` / `IPanePrimitive`) run their
`draw` / `hitTest` / `autoscaleInfo` methods synchronously inside the render
loop, so they cannot call back into Python. Instead you build them from a *spec*
whose extension points reference callbacks registered with
:meth:`AbstractChart.register_js_callback`:

.. code-block:: python

    chart.register_js_callback(
        'draw', ['target', 'priceConverter', 'view', 'prim'],
        "const y = prim.series.priceToCoordinate(100); "
        "target.useBitmapCoordinateSpace(s => { s.context.fillText('100', 0, y); });")

    prim = chart.create_series_primitive({
        'paneViews': [{'draw': 'draw', 'zOrder': 'top'}],
        'hitTest': 'hit',
        'autoscaleInfo': 'autoscale',
    })
    prim.attach_to(series)

Spec fields (all optional)

``paneViews`` / ``priceAxisPaneViews`` / ``timeAxisPaneViews``
    lists of ``{ 'zOrder': 'bottom'|'normal'|'top', 'draw': <callback>,
    'drawBackground': <callback> }``
``priceAxisViews`` / ``timeAxisViews``
    lists of ``{ 'coordinate', 'text', 'textColor', 'backColor', 'visible',
    'tickVisible' }`` (all callback names)
``autoscaleInfo``
    callback ``(startTimePoint, endTimePoint, primitive) -> AutoscaleInfo|None``
``hitTest``
    callback ``(x, y, primitive) -> PrimitiveHoveredItem|None``
``attached`` / ``detached`` / ``updateAllViews``
    lifecycle callbacks
"""
from __future__ import annotations

from typing import Optional

from .util import Pane


class _PrimitiveBase(Pane):
    """Handle to a declarative primitive registered on the JS side."""

    def __init__(self, window, handle: str):
        self.id = handle
        super().__init__(window)

    def apply_options(self, **options):
        """Update the primitive's spec (shallow-merged on the JS side)."""
        self.win.invoke(self.id, 'applyOptions', options)

    def options(self):
        """The current spec."""
        return self.win.invoke_get(self.id, 'options')

    def request_update(self):
        """Ask the chart to redraw (calls the primitive's ``requestUpdate``)."""
        self.win.invoke(self.id, 'requestUpdate')


class SeriesPrimitive(_PrimitiveBase):
    """An ``ISeriesPrimitive`` built from a spec."""

    def attach_to(self, series) -> 'SeriesPrimitive':
        """Attach to a series (``series.attachPrimitive``)."""
        series.attach_primitive(self.id)
        return self

    def detach_from(self, series) -> 'SeriesPrimitive':
        """Detach from a series (``series.detachPrimitive``)."""
        series.detach_primitive(self.id)
        return self


class PanePrimitive(_PrimitiveBase):
    """An ``IPanePrimitive`` built from a spec."""

    def attach_to(self, chart, pane_index: int = 0) -> 'PanePrimitive':
        """Attach to a pane (``pane.attachPrimitive``)."""
        chart.attach_pane_primitive(self.id, pane_index)
        return self

    def detach_from(self, chart, pane_index: int = 0) -> 'PanePrimitive':
        """Detach from a pane (``pane.detachPrimitive``)."""
        chart.detach_pane_primitive(self.id, pane_index)
        return self


__all__ = ['SeriesPrimitive', 'PanePrimitive']
