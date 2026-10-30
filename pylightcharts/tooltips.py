"""Crosshair tooltips - the tracking and magnifier ones (pylightcharts extra).

Lightweight Charts has no tooltip of its own: the official
`tooltips tutorial <https://tradingview.github.io/lightweight-charts/tutorials/how_to/tooltips>`_
builds one from an ``html`` element plus ``chart.subscribeCrosshairMove``. These
two do the same thing inside the bundle, so nothing round-trips to python while
the mouse moves:

* ``tracking``  - an opaque box next to the cursor, flipping to the other side
  near the right / bottom edge.
* ``magnifier`` - a translucent band pinned to the top of the pane that only
  slides along the time axis (the tutorial's magnifying glass); it is as tall as
  the pane, while the tracking box hugs its own content (``height=`` fixes it).

They are created through the series they read their data from:

.. code-block:: python

    tip = series.tracking_tooltip(title='ABC Inc.')
    tip = chart.magnifier_tooltip(fields=('open', 'high', 'low', 'close'))

The background and the value text default to the root CSS variables, so a
tooltip follows ``chart.win.theme('light')`` like the rest of the interface; the
title and the frame default to the series' own colour. It is placed inside the
chart, so panes, price scales, the top bar and resizes are handled for you.
"""
from __future__ import annotations

from typing import Literal, Sequence, Union

from .util import Pane

#: ``mode=`` values accepted by :meth:`SeriesCommon.tooltip`
TOOLTIP_MODE = Literal['tracking', 'magnifier']


def _mode(mode: str) -> str:
    """Validate a tooltip mode (a typo would otherwise silently do nothing)."""
    if isinstance(mode, str) and mode in ('tracking', 'magnifier'):
        return mode
    raise ValueError(
        f"mode must be 'tracking' or 'magnifier', not {mode!r}")


def _fields(fields: Union[Sequence[str], str, None]):
    """Normalise ``fields=`` into a list, ``'auto'`` or ``None``."""
    if fields is None or fields == 'auto':
        return fields
    if isinstance(fields, str):
        fields = [fields]
    if not all(isinstance(field, str) for field in fields):
        raise ValueError(f'fields must be field names, not {fields!r}')
    fields = list(fields)
    # `set_fields('auto')` arrives as a one item list
    return 'auto' if fields == ['auto'] else fields


class Tooltip(Pane):
    """Handle for a tooltip created by ``tracking_tooltip`` / ``magnifier_tooltip``.

    Every method is a thin wrapper around the JS object, so the tooltip can be
    restyled and shown/hidden while the chart runs:

    .. code-block:: python

        tip.apply_options(width=120, background='#101418')
        tip.set_title('AAPL')
        tip.hide() / tip.show() / tip.visible()
        tip.remove()
    """

    def __init__(self, window, handle: str, mode: str = 'tracking'):
        self.id = handle
        super().__init__(window)
        self.mode = mode

    def __repr__(self) -> str:
        return f'<Tooltip {self.mode!r} handle={self.id!r}>'

    def apply_options(self, **options) -> 'Tooltip':
        """Update any creation option (``title=``, ``width=``, colours, ...)."""
        self.win.invoke(self.id, 'applyOptions', options)
        return self

    def set_title(self, title: str) -> 'Tooltip':
        """Change the first line (``''`` hides it)."""
        return self.apply_options(title=title)

    def set_fields(self, *fields) -> 'Tooltip':
        """Change the extra fields, e.g. ``set_fields('open', 'close')``.

        ``set_fields('auto')`` shows every numeric field of the hovered point
        (for a candlestick that is open / high / low / close) and
        ``set_fields()`` drops them.
        """
        value = _fields(list(fields) if fields else None)
        return self.apply_options(fields=value)

    def set_mode(self, mode: TOOLTIP_MODE = 'tracking') -> 'Tooltip':
        """Switch between the tracking and the magnifier tooltip."""
        self.mode = _mode(mode)
        return self.apply_options(mode=self.mode)

    def show(self) -> 'Tooltip':
        """Follow the crosshair again after :meth:`hide`."""
        self.win.invoke(self.id, 'show')
        return self

    def hide(self) -> 'Tooltip':
        """Stop following the crosshair and hide the box."""
        self.win.invoke(self.id, 'hide')
        return self

    def visible(self) -> bool:
        """Is it currently following the crosshair (not hidden)?."""
        return bool(self.win.invoke_get(self.id, 'visible'))

    def options(self) -> dict:
        """The options the JS tooltip holds (defaults included)."""
        return self.win.invoke_get(self.id, 'options')

    def remove(self) -> None:
        """Remove the box from the page and stop listening.

        The handle is dropped as well, so the object must not be used again.
        """
        self.win.invoke(self.id, 'remove')


def create_tooltip(series, mode: str = 'tracking', **options) -> Tooltip:
    """Create a tooltip for `series` - see :meth:`SeriesCommon.tooltip`."""
    mode = _mode(mode)
    options['mode'] = mode
    # the title defaults to the series' name (e.g. 'SMA 20'), like the legend
    if 'title' not in options:
        options['title'] = getattr(series, 'name', '') or ''
    if 'fields' in options:
        options['fields'] = _fields(options['fields'])
    if options.get('field_labels') is not None:
        options['field_labels'] = list(options['field_labels'])
    handle = f'{series.id}.{mode}Tooltip'
    chart = getattr(series, '_chart', None) or series
    series.win.invoke(chart.id, 'createTooltip',
                      {'$ref': f'{series.id}.series'}, options, handle)
    return Tooltip(series.win, handle, mode)
