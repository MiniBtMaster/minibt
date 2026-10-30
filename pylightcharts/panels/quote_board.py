"""``QuoteBoard``：行情报价（类型/交易所分类 + 报价表 + 滚动条）。

miniqt「行情报价」页的公共组件版，把 :class:`~pylightcharts.panels.DataGrid`
和 :class:`~pylightcharts.panels.Ticker` 拼在一起，并多了：

* **类型 chips**（期货 / 主连 / 指数 / 期权 / 股票 …）
* **交易所 chips**（中金所 / 上期所 / … / 港股 / 美股）
* 顶部搜索（本地过滤）+ 行数 + 「刷新」
* **加载中 / 暂无数据** 两种空表文案（不会「永远在加载」✓）
* 事件回调：单击 / 双击 / 右键 / 筛选变化 / 刷新

```python
from pylightcharts import QtPanel
from pylightcharts.panels import Column, QuoteBoard

panel = QtPanel()
board = QuoteBoard(panel.win, columns=[
    Column('symbol', '代码', width=1.4),
    Column('name', '名称', width=1.2),
    Column('last', '最新', type='number', color_by='sign'),
    Column('chg', '涨跌', type='change'),
    Column('chg_pct', '涨跌幅', type='percent'),
    Column('volume', '成交量', type='number', compact=True),
])
board.set_types([('FUT', '期货'), ('STOCK', '股票')], current='FUT')
board.set_exchanges([('CFFEX', '中金所'), ('SHFE', '上期所')], current='CFFEX')
board.set_rows(rows)                      # list[dict]
board.on_filter(lambda type_, exchange, text: print(type_, exchange, text))
board.on_double_click(lambda symbol: print('open', symbol))
```
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional, Sequence

from .base import Panel, _derived_theme_colors
from .data_grid import Column, ColumnLike

#: ``parse_event_message`` 的列表分隔符（和 ``;;;`` 保持一致 ✓）
_SEP = ';;;'


def _column_dict(column: ColumnLike) -> dict:
    if isinstance(column, Column):
        return column.to_dict()
    if isinstance(column, str):
        return {'key': column, 'title': column}
    return dict(column)


class QuoteBoard(Panel):
    """行情报价面板（类型/交易所 chips + 报价表 + 可选滚动条）。"""

    def __init__(
        self,
        window,
        *,
        columns: Optional[Sequence[ColumnLike]] = None,
        types: Optional[Sequence[tuple]] = None,
        exchanges: Optional[Sequence[tuple]] = None,
        type: str = '',
        exchange: str = '',
        row_height: Optional[int] = None,
        font_size: Optional[int] = None,
        color_scheme: str = 'cn',
        show_search: bool = True,
        show_ticker: bool = False,
        loading_text: str = '正在加载合约…',
        empty_text: str = '暂无数据',
        theme: Optional[dict] = None,
    ):
        super().__init__(window)
        options = {
            'columns': [_column_dict(column) for column in (columns or [])],
            'types': _chips(types),
            'exchanges': _chips(exchanges),
            'type': type,
            'exchange': exchange,
            'colorScheme': color_scheme,
            'showSearch': bool(show_search),
            'showTicker': bool(show_ticker),
            'loadingText': loading_text,
            'emptyText': empty_text,
        }
        if row_height:
            options['rowHeight'] = int(row_height)
        if font_size:
            options['fontSize'] = int(font_size)
        if theme:
            options['theme'] = dict(theme)
        self._create('QuoteBoard', options)
        self._bind_callback(self._dispatch)

        self._on_filter: Optional[Callable] = None
        self._on_click: Optional[Callable] = None
        self._on_double_click: Optional[Callable] = None
        self._on_context: Optional[Callable] = None
        self._on_refresh: Optional[Callable] = None

    # ------------------------------------------------------------- 数据
    def set_types(self, items: Iterable[tuple], current: str = '') -> 'QuoteBoard':
        """``[('FUT', '期货'), …]``（``current`` 为空 → 保持当前选择 ✓）"""
        self._set('setTypes', _chips(items), current or '')
        return self

    def set_exchanges(self, items: Iterable[tuple],
                      current: str = '') -> 'QuoteBoard':
        self._set('setExchanges', _chips(items), current or '')
        return self

    def set_rows(self, rows: Iterable[dict]) -> 'QuoteBoard':
        """整表替换（自动清掉「加载中」状态 ✓）"""
        self._set('setRows', list(rows or []))
        return self

    def append_rows(self, rows: Iterable[dict]) -> 'QuoteBoard':
        self._set('appendRows', list(rows or []))
        return self

    def update_rows(self, rows: Iterable[dict]) -> 'QuoteBoard':
        """增量更新（只推可见行 → 几千行也不卡 ✓）"""
        self._set('updateRows', list(rows or []))
        return self

    def set_loading(self, loading: bool = True, text: str = '') -> 'QuoteBoard':
        """加载中 → 空表显示「正在加载 …」；``False`` 恢复「暂无数据」✓"""
        self._set('setLoading', bool(loading), text or '')
        return self

    def set_count(self, text: str) -> 'QuoteBoard':
        self._set('setCount', text)
        return self

    def set_ticker(self, items: Iterable[dict]) -> 'QuoteBoard':
        self._set('setTicker', list(items or []))
        return self

    def set_column_visibility(self, key: str, visible: bool) -> 'QuoteBoard':
        """期权表才显示「行权价 / 到期日」时用得上 ✓"""
        self._set('setColumnVisibility', key, bool(visible))
        return self

    def visible_keys(self) -> 'QuoteBoard':      # 兼容老名字
        self._set('visibleKeys')
        return self

    # ------------------------------------------------------------- 事件
    def on_filter(self, func: Callable[[str, str, str], None]) -> 'QuoteBoard':
        """``func(type, exchange, text)`` —— 用户点了 chips / 输入搜索 ✓"""
        self._on_filter = func
        return self

    def on_click(self, func: Callable) -> 'QuoteBoard':
        """``func(symbol, x, y)`` —— 单击（做「合约概览」气泡用）"""
        self._on_click = func
        return self

    def on_double_click(self, func: Callable) -> 'QuoteBoard':
        """``func(symbol)`` —— 双击（通常用来开图）"""
        self._on_double_click = func
        return self

    def on_context(self, func: Callable) -> 'QuoteBoard':
        """``func(symbol)`` —— 右键（周期菜单）"""
        self._on_context = func
        return self

    def on_refresh(self, func: Callable) -> 'QuoteBoard':
        """``func()`` —— 点「刷新」按钮（绕过缓存重拉 ✓）"""
        self._on_refresh = func
        return self

    def _dispatch(self, *args) -> None:
        """桥接回调：``'<symbol>;;;dblclick'`` / ``'filter;;;…'`` ✓"""
        message = str(args[0]) if args else ''
        parts = message.split(_SEP)
        if not parts:
            return
        # 事件名固定在**第 2 段**（click 后面还会带坐标 ✓）
        kind = parts[1] if len(parts) > 1 else ''
        if parts[0] == 'filter':
            if self._on_filter is not None:
                values = (parts + ['', '', ''])[1:4]
                self._on_filter(*values)
            return
        if parts[0] == 'refresh':
            if self._on_refresh is not None:
                self._on_refresh()
            return
        symbol = parts[0]
        if kind == 'click':
            if self._on_click is not None:
                x = _int(parts[2] if len(parts) > 2 else 0)
                y = _int(parts[3] if len(parts) > 3 else 0)
                self._on_click(symbol, x, y)
        elif kind == 'dblclick':
            if self._on_double_click is not None:
                self._on_double_click(symbol)
        elif kind == 'context':
            if self._on_context is not None:
                self._on_context(symbol)

    # ------------------------------------------------------------- 主题
    def apply_theme(self, spec: dict) -> None:
        colors = _derived_theme_colors(spec or {})
        theme = {
            'background': spec.get('background'),
            'headerBackground': spec.get('muted_background')
            or spec.get('hover_background'),
            'headerText': spec.get('text'),
            'text': spec.get('text'),
            'muted': colors['neutral'],
            'border': spec.get('border'),
            'rowHover': colors['hover'],
            'striped': colors['striped'],
            'gridLine': colors['grid'],
            'scrollbar': colors['scrollbar'],
            'accent': spec.get('active_background') or spec.get('hover_background'),
            'positive': spec.get('positive') or '#ef5350',
            'negative': spec.get('negative') or '#26a69a',
        }
        self._set('setOptions', {'theme': theme})


def _chips(items) -> list:
    """``[('key', '标签'), …]`` → ``[{'key':…, 'label':…}]`` ✓"""
    out = []
    for item in items or []:
        if isinstance(item, dict):
            out.append({'key': str(item.get('key') or ''),
                        'label': str(item.get('label') or item.get('key') or '')})
            continue
        key, label = (item + (None,))[:2] if isinstance(item, (tuple, list)) \
            else (item, None)
        out.append({'key': str(key), 'label': str(label or key)})
    return out


def _int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0
