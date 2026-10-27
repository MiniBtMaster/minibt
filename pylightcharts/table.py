import asyncio
import inspect
import json
import random
from typing import Callable, Literal, Optional, Tuple, Union

from .util import jbool, Pane, NUM

#: every value accepted by ``create_table(position=...)`` and
#: :meth:`Table.set_position`; the first four are the canonical corners, the
#: rest are the legacy CSS-float spellings kept for compatibility
POSITION = Literal[
    'top-left', 'top-right', 'bottom-left', 'bottom-right',
    'center', 'middle',
    'left', 'right', 'top', 'bottom',
]

#: accepted value -> (horizontal, vertical) pair of edges
POSITIONS = {
    'top-left': ('left', 'top'),
    'top-right': ('right', 'top'),
    'bottom-left': ('left', 'bottom'),
    'bottom-right': ('right', 'bottom'),
    # legacy ``create_table(position=...)`` values: CSS float only ever honoured
    # ``left``/``right``; ``top``/``bottom`` were ignored (like ``left``), so
    # they keep the left edge and pick the matching vertical one
    'left': ('left', 'top'),
    'right': ('right', 'top'),
    'top': ('left', 'top'),
    'bottom': ('left', 'bottom'),
    # centred: only meaningful for the tables this package draws (a plain CSS
    # float has no centre), used by the info pages
    'center': ('center', 'center'),
    'middle': ('center', 'center'),
}


def _resolve_position(position: str) -> Tuple[str, str]:
    """``position`` -> ``('left'|'right', 'top'|'bottom')``."""
    try:
        return POSITIONS[position]
    except KeyError:
        raise ValueError(
            f'unknown position {position!r}, expected one of '
            f'{", ".join(sorted(POSITIONS))}') from None


class Section(Pane):
    def __init__(self, table, section_type):
        super().__init__(table.win)
        self._table = table
        self.type = section_type

    def __call__(self, number_of_text_boxes: int, func: Optional[Callable] = None):
        if func is not None:
            self.win.handlers[self.id] = lambda boxId: func(
                self._table, int(boxId))
        self.run_script(f'''
        {self._table.id}.makeSection("{self.id}", "{self.type}", {number_of_text_boxes}, {"true" if func else ""})
        ''')

    def __setitem__(self, key, value):
        self.run_script(
            f'{self._table.id}.{self.type}[{key}].innerText = "{value}"')


class Row(dict):
    def __init__(self, table, id, items):
        super().__init__()
        self.run_script = table.run_script
        self._table = table
        self.id = id
        self.meta = {}
        self.run_script(
            f'{self._table.id}.newRow("{self.id}", {jbool(table.return_clicked_cells)})')
        for key, val in items.items():
            self[key] = val

    def __setitem__(self, column, value):
        if isinstance(column, tuple):
            [self.__setitem__(col, val) for col, val in zip(column, value)]
            return
        original_value = value
        if column in self._table._formatters:
            value = self._table._formatters[column].replace(
                self._table.VALUE, str(value))
        self.run_script(
            f'{self._table.id}.updateCell("{self.id}", "{column}", "{value}")')
        return super().__setitem__(column, original_value)

    def background_color(self, column, color): self._style(
        'backgroundColor', column, color)

    def text_color(self, column, color): self._style(
        'textColor', column, color)

    def _style(self, style, column, arg):
        self.run_script(
            f"{self._table.id}.styleCell({self.id}, '{column}', '{style}', '{arg}')")

    def delete(self):
        self.run_script(f"{self._table.id}.deleteRow('{self.id}')")
        self._table.pop(self.id)


class Table(Pane, dict):
    VALUE = 'CELL__~__VALUE__~__PLACEHOLDER'

    def __init__(
            self,
            window,
            width: NUM,
            height: NUM,
            headings: tuple,
            widths: Optional[tuple] = None,
            alignments: Optional[tuple] = None,
            position: POSITION = 'top-right',
            draggable: bool = False,
            margin_x: NUM = 0,
            margin_y: NUM = 0,
            background_color: str = '#121417',
            border_color: str = 'rgb(70, 70, 70)',
            border_width: int = 1,
            heading_text_colors: Optional[tuple] = None,
            heading_background_colors: Optional[tuple] = None,
            return_clicked_cells: bool = False,
            func: Optional[Callable] = None
    ):
        dict.__init__(self)
        Pane.__init__(self, window)
        # validate before creating anything, so a typo cannot leave a half-built table
        horizontal, _ = _resolve_position(position)
        self._formatters = {}
        self.headings = headings
        self.is_shown = True
        # the colours are baked into the DOM at construction, so they are kept
        # here: `set_colors` / `apply_theme` re-apply them at runtime
        theme = getattr(window, '_theme', None) or {}
        self.background_color = background_color
        self.border_color = border_color
        self.text_color = theme.get('text', 'white')
        self.section_background = theme.get('table_section_background',
                                           'rgb(30, 30, 30)')
        # a table follows the window theme unless explicit colours were given
        self.theme_follows = (
            background_color in ('#121417', theme.get('table_background'))
            and border_color in ('rgb(70, 70, 70)', theme.get('table_border')))
        tables = getattr(window, '_tables', None)
        if tables is not None:
            tables.append(self)

        def _accepts_column_heading(callback) -> bool:
            """回调是否接收第二个参数（被点单元格的列名）。

            ``return_clicked_cells=True`` 的文档契约是 ``func(row, heading)``，
            但很多人只写 ``func(row)``。这里按签名判断，两种写法都能用，
            否则会 ``TypeError: func() takes 1 positional argument but 2 were given``。
            """
            try:
                signature = inspect.signature(callback)
            except (TypeError, ValueError):
                return True          # 内建 / 装饰过的：按文档契约传两个
            positional = 0
            for parameter in signature.parameters.values():
                if parameter.kind == parameter.VAR_POSITIONAL:
                    return True
                if parameter.kind in (parameter.POSITIONAL_ONLY,
                                      parameter.POSITIONAL_OR_KEYWORD):
                    positional += 1
                    if positional >= 2:
                        return True
            return False

        pass_heading = return_clicked_cells and _accepts_column_heading(func)

        def wrapper(rId, cId=None):
            if pass_heading:
                func(self[rId], cId)
            else:
                func(self[rId])

        async def async_wrapper(rId, cId=None):
            if pass_heading:
                await func(self[rId], cId)
            else:
                await func(self[rId])

        self.win.handlers[self.id] = async_wrapper if asyncio.iscoroutinefunction(
            func) else wrapper
        self.return_clicked_cells = return_clicked_cells

        # ``Lib.Table`` only understands CSS floats; the corner itself is applied
        # below by ``set_position`` (absolute positioning).
        float_side = 'right' if horizontal == 'right' else 'left'
        self.run_script(f'''
        {self.id} = new Lib.Table(
            {width},
            {height},
            {list(headings)},
            {list(widths) if widths else []},
            {list(alignments) if alignments else []},
            '{float_side}',
            {jbool(draggable)},
            '{background_color}',
            '{border_color}',
            {border_width},
            {list(heading_text_colors) if heading_text_colors else []},
            {list(heading_background_colors) if heading_background_colors else []}
        );''')
        self.run_script(
            f'{self.id}.callbackName = "{self.id}"') if func else None
        self.footer = Section(self, 'footer')
        self.header = Section(self, 'header')
        # make the constructor's ``position`` / margins take effect right away
        self.margin_x = margin_x or 0
        self.margin_y = margin_y or 0
        self.set_position(position)

    def new_row(self, *values, id=None) -> Row:
        row_id = random.randint(0, 99_999_999) if not id else id
        self[row_id] = Row(
            self, row_id, {heading: item for heading, item in zip(self.headings, values)})
        return self[row_id]

    def clear(self): self.run_script(f"{self.id}.clearRows()"), super().clear()

    def get(self, __key: Union[int, str]
            ) -> Row: return super().get(int(__key))

    def __getitem__(self, item): return super().__getitem__(int(item))

    def format(self, column: str,
               format_str: str): self._formatters[column] = format_str

    def resize(self, width: NUM, height: NUM): self.run_script(
        f'{self.id}.reSize({width}, {height})')

    def set_position(self, position: POSITION = 'top-right',
                     margin_x: Optional[NUM] = None,
                     margin_y: Optional[NUM] = None) -> None:
        """Anchor the floating table to a corner of the chart.

        The table is taken out of the document flow (``position: absolute``),
        so it overlays the chart instead of flowing below it, and it stays
        pinned to that corner when the window is resized. Dragging still works:
        the drag handler writes ``left``/``top``, which wins over the anchor.

        The corner is relative to the chart window (the webview viewport).

        :param position: ``'top-right'`` (default), ``'top-left'``,
            ``'bottom-right'``, ``'bottom-left'`` or ``'center'``. The legacy spellings
            ``'left'`` / ``'right'`` / ``'top'`` / ``'bottom'`` are accepted
            too and resolve to the matching corner (see :data:`POSITIONS`).
        :param margin_x: **水平间距** px —— 从该角最近的**左/右边**到表格的距离
            （``top-left`` / ``bottom-left`` 量左边，``top-right`` /
            ``bottom-right`` 量右边）。``None`` = 0（贴边）。
        :param margin_y: **垂直间距** px —— 从该角最近的**上/下边**到表格的距离
            （``top-*`` 量上边，``bottom-*`` 量下边）。``None`` = 0（贴边）。
        """
        horizontal, vertical = _resolve_position(position)
        if margin_x is not None:
            self.margin_x = margin_x
        if margin_y is not None:
            self.margin_y = margin_y
        x = getattr(self, 'margin_x', 0) or 0
        y = getattr(self, 'margin_y', 0) or 0
        x = '0' if not x else f'{x}px'      # 0 保留旧的 '0'（兼容旧测试/行为）
        y = '0' if not y else f'{y}px'
        offsets = {
            'left': f"'{x}'" if horizontal == 'left' else "'auto'",
            'right': f"'{x}'" if horizontal == 'right' else "'auto'",
            'top': f"'{y}'" if vertical == 'top' else "'auto'",
            'bottom': f"'{y}'" if vertical == 'bottom' else "'auto'",
        }
        # centring uses left/top 50% + a transform (the box keeps its own size,
        # so it works for any table size and on resize)
        transform = ("'translate(-50%, -50%)'" if horizontal == 'center'
                     else "''")
        if horizontal == 'center':
            offsets['left'] = "'50%'"
            offsets['top'] = "'50%'" if vertical == 'center' else offsets['top']
        # the leading ``;`` matters: scripts can be concatenated (bulk mode,
        # ``to_scripts``) and ``(function...)()`` would otherwise be parsed as a
        # call on the previous statement (ASI does not apply)
        self.run_script(f''';(() => {{
            const div = {self.id}._div;
            div.style.position = 'absolute';
            div.style.float = '';
            div.style.left = {offsets['left']};
            div.style.right = {offsets['right']};
            div.style.top = {offsets['top']};
            div.style.bottom = {offsets['bottom']};
            div.style.transform = {transform};
        }})()
        ''')

    def visible(self, visible: bool):
        self.is_shown = visible
        self.run_script(f"""
        {self.id}._div.style.display = '{'flex' if visible else 'none'}'
        {self.id}._div.{'add' if visible else 'remove'}EventListener('mousedown', {self.id}.onMouseDown)
        """)

    def set_colors(self, background_color: Optional[str] = None,
                   border_color: Optional[str] = None,
                   text_color: Optional[str] = None,
                   section_color: Optional[str] = None) -> None:
        """Restyle a table that is already on the page (pylightcharts extra).

        The constructor paints the background, borders and text colour into the
        DOM, so changing them later needs this call - it is what
        :meth:`Window.theme` uses to recolour existing tables.
        """
        self.background_color = background_color or self.background_color
        self.border_color = border_color or self.border_color
        self.text_color = text_color or self.text_color
        self.section_background = section_color or self.section_background
        self.win.invoke(self.id, 'setColors', self.background_color,
                        self.border_color, self.text_color,
                        self.section_background)

    def apply_theme(self, spec: dict) -> None:
        """Recolour this table to match a window theme, if it follows it."""
        if not getattr(self, 'theme_follows', False):
            return
        self.set_colors(spec['table_background'], spec['table_border'],
                        spec['text'], spec['table_section_background'])


class HtmlPanel(Pane):
    """整页 HTML 面板：盖在图表画布上，替换成一张 HTML 报表页。

    和 :class:`Table` 一样是 webview 里的 DOM，但它是**全屏、可滚动、带不透明
    背景**的页面容器（不是浮层小表）。`show()` / `hide()` 切换显示，
    `set_html()` 整体替换内容。颜色用根 CSS 变量（``--bg-color`` / ``--color``
    / ``--border-color`` …），所以会跟着 `chart.theme()` 自动换深色/浅色。
    """

    def __init__(self, chart, *, padding: str = '28px'):
        Pane.__init__(self, chart.win)
        self._chart = chart
        self.padding = padding
        self.is_shown = False
        self._html = ''
        self.run_script(f'''
        {self.id} = document.createElement('div');
        {self.id}.setAttribute('data-pylightcharts-panel', '1');
        {self.id}.style.cssText =
            'position:absolute;top:0;left:0;right:0;bottom:0;overflow:auto;'
            + 'display:none;background:var(--bg-color, #131722);'
            + 'color:var(--color, #d1d4dc);z-index:20;'
            + 'padding:{self.padding};box-sizing:border-box;font-family:inherit;';
        {chart.id}.div.appendChild({self.id});
        ''')
        # 深色/浅色主题下的滚动条（用根 CSS 变量，跟主题一起换）
        self.run_script('''
        if (!document.getElementById('pylightcharts-panel-scrollbar')) {
            const style = document.createElement('style');
            style.id = 'pylightcharts-panel-scrollbar';
            style.textContent = `
                [data-pylightcharts-panel]::-webkit-scrollbar {
                    width: 10px; height: 10px; }
                [data-pylightcharts-panel]::-webkit-scrollbar-track {
                    background: var(--muted-bg-color, transparent); }
                [data-pylightcharts-panel]::-webkit-scrollbar-thumb {
                    background: var(--border-color, #888); border-radius: 5px; }
                [data-pylightcharts-panel]::-webkit-scrollbar-thumb:hover {
                    background: var(--hover-bg-color, #666); }
            `;
            document.head.appendChild(style);
        }
        ''')

    def set_html(self, html: str) -> 'HtmlPanel':
        """整体替换面板内容（一段 HTML 字符串）。"""
        self._html = html
        self.run_script(f'{self.id}.innerHTML = {json.dumps(html)}')
        return self

    def show(self) -> 'HtmlPanel':
        self.is_shown = True
        self.run_script(f'{self.id}.style.display = "block"')
        return self

    def hide(self) -> 'HtmlPanel':
        self.is_shown = False
        self.run_script(f'{self.id}.style.display = "none"')
        return self

    def delete(self) -> None:
        """移除面板 DOM。"""
        self.run_script(f'{self.id}.remove()')
