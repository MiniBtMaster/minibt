"""DataGrid panel: a sortable, filterable, virtualised data table.

It is the shared primitive behind the TradingView-style market widgets
(Market Data, Watchlist, Screener, ...)::

    from pylightcharts import Chart
    from pylightcharts.panels import DataGrid, Column

    chart = Chart()
    grid = DataGrid(chart.win, columns=[
        Column('symbol', '代码'),
        Column('name', '名称'),
        Column('last', '最新', type='number', color_by='sign'),
        Column('chg_pct', '涨跌幅', type='percent'),
        Column('spark', '走势', type='spark'),
    ])
    grid.set_rows(rows)                 # rows: list[dict]
    grid.on_row_double_click(lambda key: print('open', key))

Rows are plain dicts keyed by the column ``key``. Large numbers can be
formatted as 万/亿 with ``compact=True``, and the ``'spark'`` column type draws
a :class:`~pylightcharts.panels.Sparkline` from a list of numbers.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Iterable, Optional, Sequence, Union

from .base import Panel, _derived_theme_colors

ColumnLike = Union['Column', dict, str]


class Column:
    """Declarative DataGrid column.

    :param key: field name in each row dict (must match the data).
    :param title: header label (defaults to ``key``).
    :param width: flex grow weight relative to the other columns (default 1).
    :param align: ``'left'`` / ``'center'`` / ``'right'`` (default by type).
    :param type: ``'text'`` / ``'number'`` / ``'percent'`` / ``'change'`` /
        ``'spark'``.
    :param color_by: ``'sign'`` colours the cell by the value's sign,
        ``'none'`` keeps the theme text colour.
    :param compact: render large numbers as 万 / 亿.
    :param spark: options forwarded to the inline :class:`Sparkline`
        (JS names, e.g. ``{'lineWidth': 1.5}``).
    """

    def __init__(
        self,
        key: str,
        title: Optional[str] = None,
        *,
        width: float = 1,
        align: Optional[str] = None,
        type: str = 'text',
        decimals: Optional[int] = None,
        trim: bool = False,
        color_by: str = 'none',
        visible: bool = True,
        sortable: bool = True,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
        compact: bool = False,
        colors: Optional[dict] = None,
        spark: Optional[dict] = None,
    ):
        self.key = key
        self.title = title if title is not None else key
        self.width = width
        self.align = align
        self.type = type
        self.decimals = decimals
        self.trim = trim
        self.color_by = color_by
        self.visible = visible
        self.sortable = sortable
        self.prefix = prefix
        self.suffix = suffix
        self.compact = compact
        self.colors = colors
        self.spark = spark

    def to_dict(self) -> dict:
        data: dict = {
            'key': self.key,
            'title': self.title,
            'width': self.width,
            'type': self.type,
            'colorBy': self.color_by,
            'visible': self.visible,
            'sortable': self.sortable,
            'compact': self.compact,
        }
        if self.align is not None:
            data['align'] = self.align
        if self.decimals is not None:
            data['decimals'] = self.decimals
        if self.trim:
            data['trim'] = True
        if self.prefix is not None:
            data['prefix'] = self.prefix
        if self.suffix is not None:
            data['suffix'] = self.suffix
        if self.colors is not None:
            data['colors'] = self.colors
        if self.spark is not None:
            data['spark'] = self.spark
        return data


def _as_column(column: ColumnLike) -> dict:
    if isinstance(column, Column):
        return column.to_dict()
    if isinstance(column, dict):
        return column
    if isinstance(column, str):
        return {'key': column, 'title': column}
    raise TypeError(
        f'column must be a Column, dict or str, not {type(column).__name__}')


class DataGrid(Panel):
    """A themed data table (see the module docstring for an example)."""

    def __init__(
        self,
        window,
        columns: Optional[Sequence[ColumnLike]] = None,
        *,
        row_key: str = 'symbol',
        row_height: int = 26,
        header_height: Optional[int] = None,
        font_size: Optional[int] = None,
        searchable: bool = True,
        color_scheme: str = 'cn',
        striped: bool = True,
        empty_text: str = '暂无数据',
        theme: Optional[dict] = None,
        container: Optional[str] = None,
        on_row_click: Optional[Callable[[str], None]] = None,
        on_row_double_click: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(window)
        self._columns = [_as_column(column) for column in (columns or [])]
        self._on_click = on_row_click
        self._on_dbl = on_row_double_click
        #: last sort / search set from Python (kept so a host can persist them)
        self._sort_column: Optional[str] = None
        self._sort_direction = 1
        self._filter_text = ''

        options: dict = {
            'columns': self._columns,
            'rowKey': row_key,
            'rowHeight': row_height,
            'searchable': searchable,
            'colorScheme': color_scheme,
            'striped': striped,
            'emptyText': empty_text,
        }
        if font_size is not None:
            options['fontSize'] = int(font_size)
        if header_height is not None:
            options['headerHeight'] = header_height
        if theme:
            options['theme'] = theme
        self._create('DataGrid', options, container)
        if on_row_click or on_row_double_click:
            self._bind_events()

    # ------------------------------------------------------------------ data
    def set_columns(self, columns: Sequence[ColumnLike]) -> 'DataGrid':
        """Replace the columns (and rebuild the header)."""
        self._columns = [_as_column(column) for column in columns]
        self._set('setColumns', self._columns)
        return self

    def set_rows(self, rows: Iterable[dict]) -> 'DataGrid':
        """Replace all rows (keyed by ``row_key``)."""
        self._set('setRows', list(rows))
        return self

    def append_rows(self, rows: Iterable[dict]) -> 'DataGrid':
        self._set('appendRows', list(rows))
        return self

    def update_row(self, row: dict) -> 'DataGrid':
        """Replace one row (matched by its ``row_key`` value)."""
        self._set('updateRow', row)
        return self

    def update_rows(self, rows: Iterable[dict]) -> 'DataGrid':
        self._set('updateRows', list(rows))
        return self

    def delete_row(self, key) -> 'DataGrid':
        self._set('deleteRow', str(key))
        return self

    def set_cell(self, key, column: str, value) -> 'DataGrid':
        """Update a single cell (``key`` identifies the row)."""
        self._set('setCell', str(key), column, value)
        return self

    def clear(self) -> 'DataGrid':
        self._set('clear')
        return self

    # --------------------------------------------------------------- display
    def set_filter(self, text: str) -> 'DataGrid':
        self._filter_text = text or ''
        self._set('setFilter', self._filter_text)
        return self

    def sort(self, column: Optional[str], direction: int = 1) -> 'DataGrid':
        """Sort by ``column`` (``None`` restores insertion order)."""
        self._sort_column = column
        self._sort_direction = int(direction)
        self._set('sort', column, self._sort_direction)
        return self

    def re_size(self, width: Optional[float] = None,
                height: Optional[float] = None) -> 'DataGrid':
        self._set('reSize', width, height)
        return self

    def set_options(self, **options) -> 'DataGrid':
        """Update grid options at runtime (JS names, e.g. ``colorScheme='tv'``)."""
        self._set('setOptions', options)
        return self

    def apply_theme(self, spec: dict) -> None:
        """Map a :meth:`Window.theme` spec onto the grid's own theme."""
        derived = _derived_theme_colors(spec)
        theme = {
            'background': spec.get('background'),
            'text': spec.get('text'),
            'border': spec.get('border_color'),
            'rowHover': derived['hover'],
            'headerBackground': spec.get('table_section_background')
            or spec.get('table_background'),
            'headerText': spec.get('text'),
            'muted': spec.get('crosshair'),
            'striped': derived['striped'],
            'gridLine': derived['grid'],
            'scrollbar': derived['scrollbar'],
        }
        theme = {key: value for key, value in theme.items() if value}
        if theme:
            self._set('setOptions', {'theme': theme})
        scheme = spec.get('color_scheme')
        if scheme:
            self._set('setOptions', {'colorScheme': scheme})

    # --------------------------------------------------------------- events
    def on_row_click(self, func: Optional[Callable[[str], None]]) -> 'DataGrid':
        """Call ``func(key)`` when a row is clicked."""
        self._on_click = func
        self._bind_events()
        return self

    def on_row_double_click(
            self, func: Optional[Callable[[str], None]]) -> 'DataGrid':
        """Call ``func(key)`` when a row is double-clicked."""
        self._on_dbl = func
        self._bind_events()
        return self

    def _bind_events(self) -> None:
        on_click, on_dbl = self._on_click, self._on_dbl
        asynchronous = (asyncio.iscoroutinefunction(on_click)
                        or asyncio.iscoroutinefunction(on_dbl))

        if asynchronous:
            async def handler(key, kind='rowclick'):
                if kind == 'rowdblclick':
                    if on_dbl:
                        await on_dbl(key)
                elif on_click:
                    await on_click(key)
        else:
            def handler(key, kind='rowclick'):
                if kind == 'rowdblclick':
                    if on_dbl:
                        on_dbl(key)
                elif on_click:
                    on_click(key)

        self.win.handlers[self.id] = handler
        self.run_script(f'{self.id}.callbackName = {self.id!r};')
