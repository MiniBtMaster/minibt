"""Tabs panel: a horizontal group switcher for composite panels."""
from __future__ import annotations

from typing import Callable, Optional, Sequence, Union

from .base import Panel

TabLike = Union[str, tuple, list, dict]


def _as_tab(tab: TabLike) -> dict:
    if isinstance(tab, dict):
        return tab
    if isinstance(tab, (tuple, list)) and len(tab) >= 2:
        return {'key': str(tab[0]), 'title': str(tab[1])}
    return {'key': str(tab), 'title': str(tab)}


class Tabs(Panel):
    """A tab bar; the active key is reported through ``on_change``.

    Used by :class:`~pylightcharts.panels.MarketData` (exchange groups) and
    :class:`~pylightcharts.panels.SymbolOverview` (timeframes)::

        tabs = Tabs(chart.win, [('DCE', '大商所'), ('SHFE', '上期所')],
                    on_change=lambda key: print(key))
    """

    def __init__(
        self,
        window,
        items: Optional[Sequence[TabLike]] = None,
        *,
        active: Optional[str] = None,
        theme: Optional[dict] = None,
        on_change: Optional[Callable[[str], None]] = None,
        container: Optional[str] = None,
    ):
        super().__init__(window)
        self._on_change = on_change
        options: dict = {'items': [_as_tab(item) for item in (items or [])]}
        if active is not None:
            options['active'] = active
        if theme:
            options['theme'] = theme
        self._create('Tabs', options, container)
        if on_change is not None:
            self._bind()

    def set_tabs(self, items: Sequence[TabLike],
                 active: Optional[str] = None) -> 'Tabs':
        payload = [_as_tab(item) for item in items]
        if active is None:
            self._set('setTabs', payload)
        else:
            self._set('setTabs', payload, active)
        return self

    def set_active(self, key: str) -> 'Tabs':
        self._set('setActive', str(key))
        return self

    def on_change(self, func: Callable[[str], None]) -> 'Tabs':
        self._on_change = func
        self._bind()
        return self

    def apply_theme(self, spec: dict) -> None:
        theme = {
            'background': spec.get('table_section_background')
            or spec.get('table_background'),
            'text': spec.get('text'),
            'muted': spec.get('crosshair'),
            'activeText': spec.get('active_text'),
            'activeBackground': spec.get('active_background'),
            'hover': spec.get('hover_background'),
            'border': spec.get('border_color'),
        }
        theme = {key: value for key, value in theme.items() if value}
        if theme:
            self._set('setTheme', theme)

    def _bind(self) -> None:
        func = self._on_change
        if func is None:
            return

        def handler(key: str) -> None:
            func(key)

        self._bind_callback(handler)
