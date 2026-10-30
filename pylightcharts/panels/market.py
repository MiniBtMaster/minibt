"""Market panels: Market Data (grouped table) and Watchlist."""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

from .base import Panel
from .data_grid import Column, DataGrid
from .tabs import Tabs

#: default columns of a :class:`Watchlist`
WATCHLIST_COLUMNS = [
    Column('symbol', '代码', width=1.4),
    Column('name', '名称', width=1.2),
    Column('last', '最新', type='number', color_by='sign'),
    Column('chg', '涨跌', type='change'),
    Column('chg_pct', '涨跌幅', type='percent'),
    Column('volume', '成交量', type='number', compact=True),
    Column('spark', '走势', type='spark', width=1.4),
]


class MarketData(Panel):
    """A market table with exchange / sector **group tabs**.

    ``groups`` is a mapping ``{group_key: [rows]}``; switching a tab swaps the
    grid's rows::

        market = MarketData(chart.win, groups={
            'DCE': dce_rows, 'SHFE': shfe_rows, 'CZCE': czce_rows,
        }, columns=[...])
        market.set_group_rows('DCE', new_rows)

    Without ``groups`` it behaves like a single :class:`DataGrid`.
    """

    def __init__(
        self,
        window,
        groups: Optional[dict] = None,
        columns: Optional[Sequence] = None,
        *,
        color_scheme: str = 'cn',
        row_key: str = 'symbol',
        container: Optional[str] = None,
        **grid_options,
    ):
        super().__init__(window)
        self._groups: dict = {}
        self._active: Optional[str] = None
        self._grid_options = dict(grid_options)
        self._row_key = row_key
        self._stack('column', container)
        self.tabs = Tabs(window, [], container=self.id, on_change=self._on_tab)
        self.grid = DataGrid(
            window, columns, row_key=row_key, color_scheme=color_scheme,
            container=self.id, **grid_options)
        if groups:
            self.set_groups(groups)

    # ------------------------------------------------------------------ groups
    def set_groups(self, groups: dict) -> 'MarketData':
        self._groups = {str(key): list(rows) for key, rows in groups.items()}
        items = [(key, str(key)) for key in self._groups]
        first = next(iter(self._groups), None)
        self.tabs.set_tabs(items, active=first)
        self._active = first
        self.grid.set_rows(self._groups.get(first, []))
        return self

    def set_group_rows(self, key: str, rows: Iterable[dict]) -> 'MarketData':
        """Replace one group; refresh the table if it is the active one."""
        key = str(key)
        self._groups[key] = list(rows)
        if key == self._active:
            self.grid.set_rows(self._groups[key])
        return self

    def group_keys(self) -> list:
        return list(self._groups)

    def update_groups(self, groups: dict) -> 'MarketData':
        """Refresh every group, keeping the active tab when the keys are unchanged.

        Use this for periodic refreshes (a full :meth:`set_groups` would reset
        the selected tab every tick).
        """
        groups = {str(key): list(rows) for key, rows in groups.items()}
        if set(groups) == set(self._groups):
            for key, rows in groups.items():
                self.set_group_rows(key, rows)
            return self
        return self.set_groups(groups)

    def set_rows(self, rows: Iterable[dict]) -> 'MarketData':
        """Set the rows of the active group (or the only table)."""
        if self._active is not None:
            self._groups[self._active] = list(rows)
        self.grid.set_rows(rows)
        return self

    def active_group(self) -> Optional[str]:
        return self._active

    def _on_tab(self, key: str) -> None:
        self._active = key
        self.grid.set_rows(self._groups.get(key, []))

    # ------------------------------------------------------------------ misc
    def on_row_double_click(self, func) -> 'MarketData':
        self.grid.on_row_double_click(func)
        return self

    def on_row_click(self, func) -> 'MarketData':
        self.grid.on_row_click(func)
        return self

    def sort(self, column: Optional[str], direction: int = 1) -> 'MarketData':
        self.grid.sort(column, direction)
        return self

    def set_filter(self, text: str) -> 'MarketData':
        self.grid.set_filter(text)
        return self

    def apply_theme(self, spec: dict) -> None:
        self.tabs.apply_theme(spec)
        self.grid.apply_theme(spec)

    def delete(self) -> None:
        self.tabs.delete()
        self.grid.delete()
        self.run_script(f'{self.id}.remove();')
        panels = getattr(self.win, '_panels', None)
        if panels is not None and self in panels:
            panels.remove(self)


class Watchlist(DataGrid):
    """A self-selected list: a :class:`DataGrid` with add / remove / update.

    Rows are keyed by ``symbol``; the in-memory list is kept in sync so it can
    be persisted by the host (miniqt stores it next to the chart layout)::

        watch = Watchlist(chart.win, rows=my_rows)
        watch.add({'symbol': 'DCE.l2609', 'last': 8005})
        watch.remove('DCE.l2609')
    """

    def __init__(
        self,
        window,
        rows: Optional[Iterable[dict]] = None,
        *,
        columns: Optional[Sequence] = None,
        color_scheme: str = 'cn',
        row_key: str = 'symbol',
        **options,
    ):
        super().__init__(
            window,
            columns if columns is not None else WATCHLIST_COLUMNS,
            row_key=row_key, color_scheme=color_scheme, **options)
        self._watchlist: dict = {}
        if rows is not None:
            self.set_watchlist(rows)

    def set_watchlist(self, rows: Iterable[dict]) -> 'Watchlist':
        self._watchlist = {str(row.get('symbol')): row for row in rows}
        self.set_rows(list(self._watchlist.values()))
        return self

    def add(self, row: dict) -> 'Watchlist':
        self._watchlist[str(row.get('symbol'))] = row
        self.append_rows([row])
        return self

    def update(self, row: dict) -> 'Watchlist':
        self._watchlist[str(row.get('symbol'))] = row
        self.update_row(row)
        return self

    def remove(self, symbol) -> 'Watchlist':
        self._watchlist.pop(str(symbol), None)
        self.delete_row(symbol)
        return self

    def symbols(self) -> list:
        return list(self._watchlist)
