"""Heatmap panel: a treemap sized by one metric and coloured by another.

Covers the TradingView heatmap family (Stock / Crypto / ETF / Forex) — they all
render the same treemap, only the data and colours differ::

    from pylightcharts import Heatmap

    heat = Heatmap(chart.win, [
        {'symbol': '聚乙烯', 'value': 9, 'chg_pct': 1.2},
        {'symbol': '聚丙烯', 'value': 4, 'chg_pct': -0.8},
    ], color_scheme='cn', on_item_click=lambda symbol: print(symbol))

Items are ``{symbol, name?, value, chg_pct}`` where ``value`` is the tile size
(volume / market cap / equal weight) and ``chg_pct`` is the colour metric.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Iterable, Optional

from .base import Panel, _derived_theme_colors


class Heatmap(Panel):
    """A treemap heatmap.

    :param items: list of ``{symbol, name, value, chg_pct}``.
    :param color_scheme: ``'cn'`` (red up / green down) or ``'tv'``.
    :param max_shock: ``|chg_pct|`` at which the colour is fully saturated.
    :param show_labels: draw the symbol / change inside the tiles.
    :param on_item_click: ``func(symbol)`` when a tile is clicked.
    """

    def __init__(
        self,
        window,
        items: Optional[Iterable[dict]] = None,
        *,
        color_scheme: str = 'cn',
        max_shock: float = 5.0,
        padding: int = 1,
        show_labels: bool = True,
        show_group_labels: bool = True,
        show_legend: bool = True,
        group_label_height: int = 16,
        tooltip: bool = True,
        label_min_width: int = 26,
        label_min_height: int = 20,
        theme: Optional[dict] = None,
        on_item_click: Optional[Callable[[str], None]] = None,
        container: Optional[str] = None,
    ):
        super().__init__(window)
        self._on_item_click = on_item_click
        options: dict = {
            'colorScheme': color_scheme,
            'maxShock': max_shock,
            'padding': padding,
            'showLabels': show_labels,
            'showGroupLabels': show_group_labels,
            'showLegend': show_legend,
            'groupLabelHeight': group_label_height,
            'tooltip': tooltip,
            'labelMinWidth': label_min_width,
            'labelMinHeight': label_min_height,
        }
        if items is not None:
            options['items'] = list(items)
        if theme:
            options['theme'] = theme
        self._create('Heatmap', options, container)
        if on_item_click is not None:
            self._bind()

    def set_items(self, items: Iterable[dict]) -> 'Heatmap':
        self._set('setItems', list(items))
        return self

    def set_groups(self, groups: Iterable[dict]) -> 'Heatmap':
        """Grouped heatmap: ``[{'name': '能源', 'items': [...]}, ...]``.

        Groups are laid out first (each gets a label strip), then the tiles
        inside. Call :meth:`set_items` to go back to a single group.
        """
        payload = [
            {'name': group['name'], 'items': list(group.get('items', []))}
            for group in groups
        ]
        self._set('setGroups', payload)
        return self

    def set_options(self, **options) -> 'Heatmap':
        """Update JS options (``colorScheme``, ``maxShock``, ``showLabels`` ...)."""
        self._set('setOptions', options)
        return self

    def on_item_click(self, func: Callable[[str], None]) -> 'Heatmap':
        self._on_item_click = func
        self._bind()
        return self

    def apply_theme(self, spec: dict) -> None:
        derived = _derived_theme_colors(spec)
        theme = {
            'background': spec.get('background'),
            'border': 'rgba(128,128,128,0.35)',
            'text': '#ffffff',
            'muted': spec.get('crosshair'),
            'neutral': derived['neutral'],
            'legendBackground': derived['legend'],
        }
        theme = {key: value for key, value in theme.items() if value}
        if theme:
            self._set('setOptions', {'theme': theme})

    def _bind(self) -> None:
        func = self._on_item_click
        if func is None:
            return

        if asyncio.iscoroutinefunction(func):
            async def handler(symbol: str) -> None:
                await func(symbol)
        else:
            def handler(symbol: str) -> None:
                func(symbol)

        self._bind_callback(handler)


class StockHeatmap(Heatmap):
    """Stock heatmap (tiles = symbols, sized by market cap / volume)."""


class CryptoHeatmap(Heatmap):
    """Crypto heatmap."""


class EtfHeatmap(Heatmap):
    """ETF heatmap."""


class ForexHeatmap(Heatmap):
    """Forex heatmap."""
