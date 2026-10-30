"""TextBlock panel: a styled, scrollable text/HTML block.

Used by the detail shells (company profile description, notes). ``text`` is set
safely (``textContent``); ``html`` is injected raw, so the host owns it.
"""
from __future__ import annotations

from typing import Optional

from .base import Panel


class TextBlock(Panel):
    def __init__(
        self,
        window,
        text: Optional[str] = None,
        *,
        html: Optional[str] = None,
        title: Optional[str] = None,
        theme: Optional[dict] = None,
        container: Optional[str] = None,
    ):
        super().__init__(window)
        options: dict = {}
        if html is not None:
            options['html'] = html
        elif text is not None:
            options['text'] = text
        if title is not None:
            options['title'] = title
        if theme:
            options['theme'] = theme
        self._create('TextBlock', options, container)

    def set_text(self, text: str) -> 'TextBlock':
        self._set('setOptions', {'text': text or ''})
        return self

    def set_html(self, html: str) -> 'TextBlock':
        self._set('setOptions', {'html': html or ''})
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
