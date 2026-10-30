"""Ticker panels: quote strips (Ticker Tape / Tag / Single Ticker / Tickers).

One implementation (:class:`Ticker`) covers the whole TradingView ticker family
by ``layout``: ``'scroll'`` is the moving marquee, ``'wrap'`` a static wrap/grid
of quote chips.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Iterable, Optional

from .base import Panel, _derived_theme_colors


class Ticker(Panel):
    """A quote strip.

    :param items: list of dicts ``{symbol, name, last, chg, chg_pct}``.
    :param layout: ``'scroll'`` (marquee) or ``'wrap'``.
    :param speed: marquee speed in pixels per second.
    :param color_scheme: ``'cn'`` (red up / green down) or ``'tv'``.
    :param compact: format numbers as 万 / 亿.
    :param on_item_click: ``func(symbol)`` when a chip is clicked.
    """

    def __init__(
        self,
        window,
        items: Optional[Iterable[dict]] = None,
        *,
        layout: str = 'scroll',
        speed: float = 60,
        color_scheme: str = 'cn',
        separator: str = '',
        decimals: int = 2,
        compact: bool = False,
        show_name: bool = False,
        theme: Optional[dict] = None,
        on_item_click: Optional[Callable[[str], None]] = None,
        container: Optional[str] = None,
    ):
        super().__init__(window)
        self._on_item_click = on_item_click
        options: dict = {
            'layout': layout,
            'speed': speed,
            'colorScheme': color_scheme,
            'separator': separator,
            'decimals': decimals,
            'compact': compact,
            'showName': show_name,
        }
        if items is not None:
            options['items'] = list(items)
        if theme:
            options['theme'] = theme
        self._create('Ticker', options, container)
        if on_item_click is not None:
            self._bind()

    def set_items(self, items: Iterable[dict]) -> 'Ticker':
        self._set('setItems', list(items))
        return self

    def set_data(self, items: Iterable[dict]) -> 'Ticker':
        """Update values **in place** (keeps the marquee animation running).

        ``set_items`` rebuilds the DOM and restarts the scroll from the beginning ✗;
        use this for periodic refreshes. It falls back to ``set_items`` automatically
        when the symbol list / order changed (e.g. switching the current page).
        """
        self._set('setData', list(items))
        return self

    def update_item(self, item: dict) -> 'Ticker':
        self._set('updateItem', item)
        return self

    def set_options(self, **options) -> 'Ticker':
        """Update JS options (e.g. ``layout='wrap'``, ``speed=120``)."""
        self._set('setOptions', options)
        return self

    def on_item_click(self, func: Callable[[str], None]) -> 'Ticker':
        self._on_item_click = func
        self._bind()
        return self

    def apply_theme(self, spec: dict) -> None:
        derived = _derived_theme_colors(spec)
        theme = {
            'background': spec.get('background'),
            'text': spec.get('text'),
            'muted': spec.get('crosshair'),
            'border': spec.get('border_color'),
            'hover': derived['hover'],
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


class TickerTape(Ticker):
    """The moving marquee (TradingView Ticker Tape)."""

    def __init__(self, window, items=None, **options):
        options.setdefault('layout', 'scroll')
        super().__init__(window, items, **options)


class TickerTag(Ticker):
    """A single quote chip (TradingView Ticker Tag)."""

    def __init__(self, window, items=None, **options):
        options.setdefault('layout', 'wrap')
        super().__init__(window, items, **options)


class SingleTicker(Ticker):
    """One instrument (TradingView Single Ticker)."""

    def __init__(self, window, items=None, **options):
        options.setdefault('layout', 'wrap')
        super().__init__(window, items, **options)


class Tickers(Ticker):
    """A grid of quote chips (TradingView Tickers)."""

    def __init__(self, window, items=None, **options):
        options.setdefault('layout', 'wrap')
        super().__init__(window, items, **options)
