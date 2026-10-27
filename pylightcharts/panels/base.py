"""Base class for the DOM panels of :mod:`pylightcharts.panels`."""
from __future__ import annotations

import json
from typing import Callable, Optional

from ..util import Pane, js_raw


def _background_is_light(spec: dict) -> bool:
    """Heuristic: is the theme's background light? (for derived tints)"""
    color = str(spec.get('background') or '').strip()
    if color.startswith('#'):
        digits = color[1:]
        if len(digits) == 3:
            digits = ''.join(ch * 2 for ch in digits)
        if len(digits) >= 6:
            try:
                red = int(digits[0:2], 16)
                green = int(digits[2:4], 16)
                blue = int(digits[4:6], 16)
            except ValueError:
                return False
            return (0.299 * red + 0.587 * green + 0.114 * blue) > 140
    return False


def _derived_theme_colors(spec: dict) -> dict:
    """Tints that have to flip between dark and light backgrounds."""
    light = _background_is_light(spec)
    return {
        'light': light,
        'striped': 'rgba(0,0,0,0.03)' if light else 'rgba(255,255,255,0.02)',
        'grid': 'rgba(0,0,0,0.06)' if light else 'rgba(255,255,255,0.04)',
        'scrollbar': '#c9ced6' if light else '#3a3f4b',
        'hover': spec.get('hover_background') or ('#f0f3fa' if light else '#2a2e39'),
        'neutral': '#c7ccd6' if light else '#3a3f4b',
        'legend': 'rgba(255,255,255,0.85)' if light else 'rgba(19,23,34,0.72)',
    }


class Panel(Pane):
    """A DOM component (table, sparkline, ticker, ...) living in a host page.

    A panel is **not** a chart: it is created on a
    :class:`~pylightcharts.Window`, so it can share a page with charts
    (``DataGrid(chart.win)``) or live in a chart-less panel page
    (``DataGrid(panel.win)`` on a :class:`~pylightcharts.QtPanel`).

    Subclasses create their JS object through :meth:`_create` and drive it
    through :meth:`_set`. Unlike chart options, the field names of panel data
    are the caller's own (``open_interest`` stays ``open_interest``), so the
    arguments are serialised with :func:`~pylightcharts.util.js_raw`.
    """

    def __init__(self, window, *, register: bool = True):
        super().__init__(window)
        if register:
            panels = getattr(window, '_panels', None)
            if panels is not None:
                panels.append(self)

    def _create(self, js_class: str, options: Optional[dict] = None,
                container: Optional[str] = None) -> None:
        """Instantiate ``Lib.<js_class>`` and assign it to ``self.id``.

        ``container`` is a JS expression (e.g. ``'window.abc123'``) the panel
        should append itself to; without it the JS default
        (``window.containerDiv``) is used.
        """
        args = js_raw(options) if options is not None else '{}'
        if container:
            self.run_script(
                f'{self.id} = new Lib.{js_class}({args}, {container});')
        else:
            self.run_script(f'{self.id} = new Lib.{js_class}({args});')
        # a panel created after `Window.theme(...)` inherits the current theme
        theme = getattr(self.win, '_theme', None)
        if theme:
            try:
                self.apply_theme(theme)
            except Exception:                                     # noqa: BLE001
                pass

    def _set(self, method: str, *args) -> None:
        """Call ``self.id.method(*args)`` keeping dict keys verbatim."""
        joined = ', '.join(js_raw(arg) for arg in args)
        self.run_script(f'{self.id}.{method}({joined});')

    def _stack(self, direction: str = 'column',
               container: Optional[str] = None) -> str:
        """Create a flex container at ``self.id`` and return its JS expression.

        Composite panels (Symbol Overview, Market Data, Company Profile) put a
        header/tabs and a body in one of these; child panels are created with
        ``container=self.id``.
        """
        css = (f'display:flex;flex-direction:{direction};height:100%;'
               f'width:100%;min-height:0')
        target = container or 'window.containerDiv'
        self.run_script(
            f"{self.id} = document.createElement('div');"
            f"{self.id}.className='pylc-stack';"
            f"{self.id}.style.cssText={json.dumps(css)};"
            f"{target}.appendChild({self.id});")
        return self.id

    def _bind_callback(self, handler: Callable) -> None:
        """Register ``handler`` for this panel's ``callbackName`` events."""
        self.win.handlers[self.id] = handler
        self.run_script(f'{self.id}.callbackName = {self.id!r};')

    def apply_theme(self, spec: dict) -> None:
        """Recolour the panel for a :meth:`Window.theme` switch.

        Overridden by subclasses; the default does nothing.
        """

    def delete(self) -> None:
        """Remove the panel from the page and from the window registry."""
        self.run_script(
            f'if ({self.id} && {self.id}.destroy) {{ {self.id}.destroy(); }}')
        panels = getattr(self.win, '_panels', None)
        if panels is not None and self in panels:
            panels.remove(self)
