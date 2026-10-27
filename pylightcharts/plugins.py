"""Handles for the v5 plugin primitives (markers, up/down markers, watermarks).

Lightweight Charts v5 moved markers and watermarks from chart/series options to
*plugins* created by ``createSeriesMarkers`` / ``createUpDownMarkers`` /
``createTextWatermark`` / ``createImageWatermark``. The bridge creates them and
registers a JS handle; these classes wrap that handle so the whole plugin
lifecycle (set data, read state, apply options, detach) is usable from Python.

They are obtained through the convenience factories:

.. code-block:: python

    markers  = series.markers_plugin()          # SeriesMarkersPlugin
    updown   = series.up_down_markers_plugin()  # UpDownMarkersPlugin
    text     = chart.text_watermark_plugin('hi')  # TextWatermarkPlugin
    image    = chart.image_watermark_plugin('logo.png')  # ImageWatermarkPlugin

All methods are thin RPC wrappers; objects returned by the engine (e.g. the
marker array, a pane handle) are registered on the JS side and returned as
handles.
"""
from __future__ import annotations

from typing import Optional

from .util import Pane


class _Plugin(Pane):
    """Base for plugin handles: ``self.id`` points at a registered JS object."""

    def __init__(self, window, handle: str):
        # Pane.__init__ keeps an existing `id` and only sets up the bridge.
        self.id = handle
        super().__init__(window)

    def _call(self, method: str, *args):
        self.win.invoke(self.id, method, *args)

    def _call_get(self, method: str, *args):
        return self.win.invoke_get(self.id, method, *args)

    def _store(self, method: str, handle: str, *args) -> str:
        self.win.invoke(self.id, method, *args, store_as=handle)
        return handle


class SeriesMarkersPlugin(_Plugin):
    """``ISeriesMarkersPluginApi`` — markers attached to one series (v5)."""

    def set_markers(self, markers):
        """Replace all markers (see ``SeriesMarker``)."""
        self._call('setMarkers', markers)

    def markers(self):
        """The current markers as returned by the engine."""
        return self._call_get('markers')

    def apply_options(self, **options):
        """Apply plugin options (snake_case keys are camelCased)."""
        self._call('applyOptions', options)

    def detach(self):
        """Detach the marker primitive from its series."""
        self._call('detach')

    def get_series(self) -> str:
        """Handle of the series this plugin is attached to."""
        return self._store('getSeries', f'{self.id}.series')


class UpDownMarkersPlugin(_Plugin):
    """``ISeriesUpDownMarkerPluginApi`` — up/down markers (Line / Area only).

    This plugin draws its markers at a *price*: a marker is
    ``{'time': t, 'value': price, 'sign': 1 | 0 | -1}`` (the engine's
    ``SeriesUpDownMarker``), where `sign` picks the arrow direction. That is not
    the classic ``series.marker(...)`` format (``position``/``shape``/``color``/
    ``text``): use :meth:`SeriesCommon.marker` for those.
    """

    def set_data(self, data):
        """Take over the series' data and generate up/down markers from it."""
        self._call('setData', data)

    def update(self, data, historical_update: bool = False):
        """Update one point; the generated marker expires after
        ``update_visibility_duration`` ms (see ``apply_options``)."""
        self._call('update', data, historical_update)

    def markers(self):
        """The markers the plugin currently holds (expired ones are gone)."""
        return self._call_get('markers')

    def set_markers(self, markers):
        """Replace the plugin's markers with ``{'time', 'value', 'sign'}`` dicts.

        ``sign`` is ``1`` (up), ``0`` (neutral) or ``-1`` (down) and defaults to
        ``0``; ``value`` is the price the marker is drawn at. The classic marker
        format is silently ignored by the engine (a missing ``value`` has no
        price to draw at), so it is rejected here instead.
        """
        markers = list(markers)
        for marker in markers:
            missing = {'time', 'value'} - set(marker)
            if missing:
                raise ValueError(
                    'up/down markers need '
                    f"{sorted({'time', 'value', 'sign'})}, missing "
                    f'{sorted(missing)} in {marker!r}. The classic marker '
                    'format (position/shape/color/text) belongs to '
                    'series.marker(...) / marker_list(...).')
        self._call('setMarkers', markers)

    def clear_markers(self):
        """Drop every marker (the series data is left alone)."""
        self._call('clearMarkers')

    def apply_options(self, **options):
        """Options such as ``positive_color`` / ``negative_color`` /
        ``update_visibility_duration`` (snake_case keys are camelCased)."""
        self._call('applyOptions', options)

    def detach(self):
        """Detach the plugin; the series keeps the data it was given."""
        self._call('detach')

    def get_series(self) -> str:
        """Handle of the series this plugin is attached to."""
        return self._store('getSeries', f'{self.id}.series')


class _WatermarkPlugin(_Plugin):
    """Shared members of the text/image watermark plugins."""

    def apply_options(self, **options):
        self._call('applyOptions', options)

    def detach(self):
        self._call('detach')

    def get_pane(self) -> str:
        """Handle of the pane the watermark lives in."""
        return self._store('getPane', f'{self.id}.pane')


class TextWatermarkPlugin(_WatermarkPlugin):
    """``ITextWatermarkPluginApi``."""


class ImageWatermarkPlugin(_WatermarkPlugin):
    """``IImageWatermarkPluginApi``."""


__all__ = [
    'SeriesMarkersPlugin', 'UpDownMarkersPlugin',
    'TextWatermarkPlugin', 'ImageWatermarkPlugin',
]
