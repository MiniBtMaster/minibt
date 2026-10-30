"""Screener panel: a :class:`~pylightcharts.panels.DataGrid` with conditions.

The DataGrid already sorts and has a search box; the Screener adds **multiple
column conditions** applied in Python before the rows are pushed, so a host can
build a filter UI on top (see :class:`~pylightcharts.panels.FilterBar`) or drive
it from code::

    from pylightcharts import Screener, Column

    screener = Screener(chart.win, rows, columns=[
        Column('symbol', '代码'),
        Column('chg_pct', '涨跌幅', type='percent'),
        Column('volume', '成交量', type='number', compact=True),
    ])
    screener.add_filter('chg_pct', '>', 2)          # only up > 2%
    screener.add_filter('volume', '>=', 10000)
    screener.set_match('any')                        # OR instead of AND
    screener.clear_filters()

With a filter bar (chips + optional inline adder)::

    bar = FilterBar(chart.win, columns=['chg_pct', 'volume'], editable=True)
    screener.bind_filter_bar(bar)                    # two-way sync
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from .data_grid import DataGrid

#: comparison operators accepted by :meth:`Screener.add_filter`
OPERATORS = ('>', '>=', '<', '<=', '==', '!=', 'contains', 'in')

Condition = Tuple[str, str, object]


def _matches(value, op: str, target) -> bool:
    if value is None:
        return False
    if op == 'contains':
        return str(target).lower() in str(value).lower()
    if op == 'in':
        try:
            return value in target
        except TypeError:
            return False
    try:
        left, right = float(value), float(target)
    except (TypeError, ValueError):
        left, right = str(value), str(target)
    if op == '>':
        return left > right
    if op == '>=':
        return left >= right
    if op == '<':
        return left < right
    if op == '<=':
        return left <= right
    if op == '==':
        return left == right
    if op == '!=':
        return left != right
    return False


def _condition(entry) -> Condition:
    """Accept ``(column, op, value)``, ``[column, op, value]`` or a dict."""
    if isinstance(entry, dict):
        return (str(entry['column']), str(entry['op']), entry.get('value'))
    column, op, value = entry
    return (str(column), str(op), value)


def _condition_dict(condition: Condition) -> dict:
    column, op, value = condition
    return {'column': column, 'op': op, 'value': value}


class Screener(DataGrid):
    """A screener: a table whose rows are filtered by column conditions.

    :param match: ``'all'`` (default, AND) or ``'any'`` (OR).
    :param on_change: called with the current filter list after any change.
    """

    def __init__(
        self,
        window,
        rows: Optional[Iterable[dict]] = None,
        columns: Optional[Sequence] = None,
        *,
        row_key: str = 'symbol',
        color_scheme: str = 'cn',
        filters: Optional[Sequence] = None,
        match: str = 'all',
        on_change: Optional[Callable[[List[Condition]], None]] = None,
        presets: Optional[dict] = None,
        **options,
    ):
        super().__init__(window, columns, row_key=row_key,
                         color_scheme=color_scheme, **options)
        self._all_rows: list = []
        self._conditions: List[Condition] = []
        self._match = 'any' if str(match).lower() == 'any' else 'all'
        self._on_change = on_change
        self._filter_bar = None
        self._presets: dict = {}
        if rows is not None:
            self.set_rows(rows)
        if filters:
            self.set_filters(filters)
        if presets:
            self.load_presets(presets)

    # ------------------------------------------------------------------ data
    def set_rows(self, rows: Iterable[dict]) -> 'Screener':
        """Replace the full dataset (conditions are re-applied)."""
        self._all_rows = list(rows)
        self._refresh_view()
        return self

    def data(self) -> list:
        """The full dataset (unfiltered)."""
        return list(self._all_rows)

    # ------------------------------------------------------------- conditions
    def add_filter(self, column: str, op: str, value) -> 'Screener':
        if op not in OPERATORS:
            raise ValueError(
                f'unknown operator {op!r}; expected one of {", ".join(OPERATORS)}')
        self._conditions.append((column, op, value))
        self._refresh_view()
        return self

    def remove_filter(self, column: str, op: Optional[str] = None,
                      value=None) -> 'Screener':
        """Remove conditions matching the given column/op/value prefix."""
        self._conditions = [
            condition for condition in self._conditions
            if not (condition[0] == column
                    and (op is None or condition[1] == op)
                    and (value is None or condition[2] == value))
        ]
        self._refresh_view()
        return self

    def set_filters(self, filters: Sequence) -> 'Screener':
        """Replace every condition at once."""
        self._conditions = [_condition(entry) for entry in filters]
        self._refresh_view()
        return self

    def clear_filters(self) -> 'Screener':
        self._conditions = []
        self._refresh_view()
        return self

    def filters(self) -> List[Condition]:
        return list(self._conditions)

    def match(self) -> str:
        return self._match

    def set_match(self, match: str) -> 'Screener':
        """``'all'`` (AND) or ``'any'`` (OR)."""
        self._match = 'any' if str(match).lower() == 'any' else 'all'
        self._refresh_view()
        return self

    def apply(self) -> 'Screener':
        """Re-run the conditions (e.g. after mutating ``data()`` rows)."""
        self._refresh_view()
        return self

    def on_change(self, func: Optional[Callable[[List[Condition]], None]]
                  ) -> 'Screener':
        self._on_change = func
        return self

    # -------------------------------------------------------------- presets
    def save_preset(self, name: str, filters: Optional[Sequence] = None
                    ) -> 'Screener':
        """Store the current conditions (or ``filters``) under ``name``."""
        source = self._conditions if filters is None else filters
        self._presets[str(name)] = [_condition(entry) for entry in source]
        return self

    def apply_preset(self, name: str) -> 'Screener':
        """Replace the conditions with a saved preset and re-filter."""
        key = str(name)
        if key not in self._presets:
            raise KeyError(f'unknown preset {name!r}')
        self._conditions = list(self._presets[key])
        self._refresh_view()
        return self

    def presets(self) -> dict:
        return {name: list(conditions)
                for name, conditions in self._presets.items()}

    def delete_preset(self, name: str) -> 'Screener':
        self._presets.pop(str(name), None)
        return self

    def load_presets(self, presets: dict) -> 'Screener':
        self._presets = {
            str(name): [_condition(entry) for entry in conditions]
            for name, conditions in (presets or {}).items()
        }
        return self

    # ---------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        """Everything needed to restore the screen (filters, presets, view)."""
        return {
            'match': self._match,
            'filters': [_condition_dict(c) for c in self._conditions],
            'presets': {name: [_condition_dict(c) for c in conditions]
                        for name, conditions in self._presets.items()},
            'sort': {'column': self._sort_column,
                     'direction': self._sort_direction},
            'search': self._filter_text,
        }

    def load_dict(self, data: dict) -> 'Screener':
        """Restore a screen saved by :meth:`to_dict` (accepts ``{}``)."""
        data = data or {}
        self.load_presets(data.get('presets') or {})
        self._match = ('any' if str(data.get('match', 'all')).lower() == 'any'
                       else 'all')
        self._conditions = [_condition(entry)
                            for entry in (data.get('filters') or [])]
        sort = data.get('sort') or {}
        self._sort_column = sort.get('column')
        self._sort_direction = int(sort.get('direction') or 1)
        self._filter_text = data.get('search') or ''
        self._refresh_view()
        self.sort(self._sort_column, self._sort_direction)
        self.set_filter(self._filter_text)
        return self

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def loads(self, text: str) -> 'Screener':
        return self.load_dict(json.loads(text))

    def save(self, path) -> str:
        """Write the screen to a JSON file (returns the path)."""
        target = Path(path)
        target.write_text(self.dumps(), encoding='utf-8')
        return str(target)

    def load(self, path) -> 'Screener':
        return self.loads(Path(path).read_text(encoding='utf-8'))

    # ------------------------------------------------------------- filter bar
    def bind_filter_bar(self, bar) -> 'Screener':
        """Keep a :class:`~pylightcharts.panels.FilterBar` in sync (both ways)."""
        self._filter_bar = bar
        bar.set_filters([
            {'column': column, 'op': op, 'value': value}
            for column, op, value in self._conditions
        ])
        bar.on_change(self._on_bar_change)
        return self

    def _on_bar_change(self, filters) -> None:
        self._conditions = [_condition(entry) for entry in filters]
        self._refresh_view(notify_bar=False)

    # ------------------------------------------------------------------ inner
    def _refresh_view(self, notify_bar: bool = True) -> None:
        rows = self._all_rows
        if self._conditions:
            if self._match == 'any':
                rows = [row for row in rows
                        if any(_matches(row.get(column), op, value)
                               for column, op, value in self._conditions)]
            else:
                for column, op, value in self._conditions:
                    rows = [row for row in rows
                            if _matches(row.get(column), op, value)]
        super().set_rows(rows)
        if self._on_change is not None:
            self._on_change(self.filters())
        if notify_bar and self._filter_bar is not None:
            self._filter_bar.set_filters([
                {'column': column, 'op': op, 'value': value}
                for column, op, value in self._conditions
            ])
