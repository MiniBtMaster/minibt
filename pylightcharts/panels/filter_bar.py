"""FilterBar panel: the chip bar for :class:`~pylightcharts.panels.Screener`.

Active conditions are chips with an ×; the optional inline adder lets the user
add a condition (column / operator / value). Every change reports the **full
filter list** back to Python (base64-JSON, so no value can break the bridge).
"""
from __future__ import annotations

import base64
import json
from typing import Callable, Iterable, List, Optional, Sequence, Union

from .base import Panel

FilterLike = Union[dict, tuple, list]


def _as_filter(entry: FilterLike) -> dict:
    if isinstance(entry, dict):
        return {'column': str(entry['column']), 'op': str(entry['op']),
                'value': entry.get('value')}
    column, op, value = entry
    return {'column': str(column), 'op': str(op), 'value': value}


class FilterBar(Panel):
    """A removable-chip filter bar.

    :param columns: column names offered by the inline adder.
    :param editable: show the inline "add condition" form.
    :param on_change: ``func(filters)`` where ``filters`` is a list of
        ``{'column', 'op', 'value'}`` dicts.
    """

    def __init__(
        self,
        window,
        filters: Optional[Sequence[FilterLike]] = None,
        *,
        columns: Optional[Sequence[str]] = None,
        operators: Optional[Sequence[str]] = None,
        editable: bool = False,
        clear_label: str = '清除',
        add_label: str = '添加',
        theme: Optional[dict] = None,
        on_change: Optional[Callable[[List[dict]], None]] = None,
        container: Optional[str] = None,
    ):
        super().__init__(window)
        self._filters = [_as_filter(entry) for entry in (filters or [])]
        self._on_change = on_change
        options: dict = {
            'filters': self._filters,
            'editable': editable,
            'clearLabel': clear_label,
            'addLabel': add_label,
        }
        if columns is not None:
            options['columns'] = list(columns)
        if operators is not None:
            options['operators'] = list(operators)
        if theme:
            options['theme'] = theme
        self._create('FilterBar', options, container)
        if on_change is not None:
            self._bind()

    def set_filters(self, filters: Iterable[FilterLike]) -> 'FilterBar':
        self._filters = [_as_filter(entry) for entry in filters]
        self._set('setFilters', self._filters)
        return self

    def get_filters(self) -> List[dict]:
        return [dict(entry) for entry in self._filters]

    def set_columns(self, columns: Sequence[str]) -> 'FilterBar':
        self._set('setColumns', list(columns))
        return self

    def on_change(self, func: Callable[[List[dict]], None]) -> 'FilterBar':
        self._on_change = func
        self._bind()
        return self

    def apply_theme(self, spec: dict) -> None:
        theme = {
            'background': spec.get('table_section_background')
            or spec.get('table_background'),
            'text': spec.get('text'),
            'muted': spec.get('crosshair'),
            'border': spec.get('border_color'),
            'hover': spec.get('hover_background'),
            'chip': spec.get('table_background'),
        }
        theme = {key: value for key, value in theme.items() if value}
        if theme:
            self._set('setOptions', {'theme': theme})

    def _bind(self) -> None:
        func = self._on_change
        if func is None:
            return

        def handler(payload: str) -> None:
            try:
                filters = json.loads(base64.b64decode(payload).decode('utf-8'))
            except Exception:                                    # noqa: BLE001
                return
            self._filters = filters
            func(filters)

        self._bind_callback(handler)
