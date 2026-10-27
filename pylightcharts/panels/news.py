"""NewsFeed panel: a headline list (TradingView Top Stories).

The library has no news source; the host feeds the items::

    from pylightcharts import NewsFeed

    feed = NewsFeed(chart.win, [
        {'title': '...', 'source': 'Reuters', 'time': '10:24',
         'url': 'https://...', 'summary': '...'},
    ])
    feed.set_items(new_items)
"""
from __future__ import annotations

import asyncio
from typing import Callable, Iterable, Optional

from .base import Panel


class NewsFeed(Panel):
    """A scrollable list of news items.

    :param items: ``{title, source, time, url, summary}``.
    :param open_links: open ``url`` in a new tab on click (default True).
    :param on_item_click: ``func(index)`` (called after opening the link).
    """

    def __init__(
        self,
        window,
        items: Optional[Iterable[dict]] = None,
        *,
        open_links: bool = True,
        theme: Optional[dict] = None,
        on_item_click: Optional[Callable[[int], None]] = None,
        container: Optional[str] = None,
    ):
        super().__init__(window)
        self._on_item_click = on_item_click
        options: dict = {'openLinks': open_links}
        if items is not None:
            options['items'] = list(items)
        if theme:
            options['theme'] = theme
        self._create('NewsFeed', options, container)
        if on_item_click is not None:
            self._bind()

    def set_items(self, items: Iterable[dict]) -> 'NewsFeed':
        self._set('setItems', list(items))
        return self

    def on_item_click(self, func: Callable[[int], None]) -> 'NewsFeed':
        self._on_item_click = func
        self._bind()
        return self

    def apply_theme(self, spec: dict) -> None:
        theme = {
            'background': spec.get('background'),
            'text': spec.get('text'),
            'muted': spec.get('crosshair'),
            'border': spec.get('border_color'),
        }
        theme = {key: value for key, value in theme.items() if value}
        if theme:
            self._set('setOptions', {'theme': theme})

    def _bind(self) -> None:
        func = self._on_item_click
        if func is None:
            return

        if asyncio.iscoroutinefunction(func):
            async def handler(index: str) -> None:
                await func(int(index))
        else:
            def handler(index: str) -> None:
                func(int(index))

        self._bind_callback(handler)


class TopStories(NewsFeed):
    """TradingView Top Stories — the same feed with a news-page intent."""
