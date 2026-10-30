"""Share one window between several charts.

pylightcharts extension: Lightweight Charts itself knows nothing about several
charts sharing a page, and upstream ``lightweight-charts-python`` only offers
``create_subchart`` (a floater at a given position/size). Trading UIs want
more: a row or a column of charts that *tile* the area, which is what the
layout menu of a top bar needs.

    chart = Chart(...)
    chart.win.layout.vertical()            # 上下：下方加一张
    chart.win.layout.horizontal()          # 左右：右侧加一张
    chart.win.layout.arrange('horizontal', 3)   # 三张并排

``arrange`` is the single entry point: it creates as many charts as asked,
hides the extra ones, and sizes every visible chart so they share the window.

The charts are **independent** by default - a multi-timeframe or multi-symbol
workspace wants each chart to keep its own time scale and crosshair::

    win.layout.horizontal()                   # independent (default)
    win.layout.horizontal(sync=True)          # pan / zoom / crosshair together
    win.layout.horizontal(sync='crosshair')   # only the crosshair together
    win.layout.horizontal()                   # back to independent

``sync`` also accepts ``'full'`` / ``'both'`` and ``'crosshairs_only'``. It
applies to every chart of the layout, including the ones that already exist,
and can be changed or removed later (the engine link is replaced, never
stacked).
"""
from typing import List, Literal, Optional, Union

from .util import IDGen, js_value

KIND = Literal['horizontal', 'vertical']
#: what ``arrange(sync=...)`` accepts
SYNC = Union[bool, str, None]

HORIZONTAL: KIND = 'horizontal'
VERTICAL: KIND = 'vertical'

SYNC_NONE = False
SYNC_FULL = 'full'
SYNC_CROSSHAIR = 'crosshair'


def _flow_tiles(tiles):
    """``[(w, h), …]`` → ``[[x, y, w, h], …]``（按行流式，放不下就换行 ✓）。"""
    out: List[list] = []
    x = y = row_h = 0.0
    for width, height in tiles:
        if x + width > 1.0 + 1e-9:
            x, y = 0.0, y + row_h
            row_h = 0.0
        out.append([round(x, 6), round(y, 6), float(width), float(height)])
        x += width
        row_h = max(row_h, float(height))
    return out


def _sync_mode(sync: SYNC) -> Optional[str]:
    """Normalise `sync` into ``None`` / ``'crosshair'`` / ``'full'``."""
    if sync is None or sync is False:
        return None
    if sync is True:
        return SYNC_FULL
    if isinstance(sync, str):
        key = sync.strip().lower().replace('-', '_')
        if key in ('crosshair', 'crosshairs', 'crosshair_only',
                   'crosshairs_only'):
            return SYNC_CROSSHAIR
        if key in ('full', 'both', 'all'):
            return SYNC_FULL
        if key in ('none', 'off', 'independent'):
            return None
    raise ValueError(
        'sync must be False/None, True, \'crosshair\' or \'full\', '
        f'not {sync!r}')


class Layout:
    """Splits a window between charts: one row or one column.

    Charts are tiled with floats (``position='left'``) and sized as fractions
    of the window, so ``count=1`` is a single full-size chart. Charts keep the
    order they were registered in (their creation order), so the first chart of
    the window is the anchor a new one is attached to.

    The charts do not move together by default: a layout is usually for
    different periods or symbols, so panning, zooming and the crosshair stay
    per chart. ``arrange(sync=...)`` links them (``True`` = everything,
    ``'crosshair'`` = crosshair only) and can drop the link again.
    """

    def __init__(self, window, on_create=None, divider=True,
                 divider_size=6, divider_color='#2a2e39',
                 divider_hover_color='#2962FF'):
        self.win = window
        #: called with every chart this layout creates, e.g. to feed it data;
        #: ``arrange(on_create=...)`` overrides it for a single call
        self.on_create = on_create
        #: draggable separators between the charts (like a pane separator)
        self.divider = divider
        self.divider_size = divider_size
        self.divider_color = divider_color
        self.divider_hover_color = divider_hover_color
        self._charts: List = []
        self._hidden: List = []
        self._kind: Optional[KIND] = None
        #: the 2D tile spec while a tiles layout is in place, else ``None``
        self._tiles = None
        #: whether the tiles layout draws draggable dividers (arrange_tiles ✓)
        self._tiles_dividers = False
        #: chart -> 'full' / 'crosshair', the link currently in place
        self._synced: dict = {}
        self._mode: Optional[str] = None
        self._id = IDGen().generate()
        # the JS side reports the shares back after a drag, so `_width` /
        # `_height` stay truthful
        self._callback_id = IDGen().generate()
        window.handlers[self._callback_id] = self._on_drag

    # ------------------------------------------------------------- geometry
    @property
    def charts(self) -> List:
        """The visible charts of the layout, in layout order."""
        return list(self._charts)

    @property
    def hidden_charts(self) -> List:
        """Charts the layout put away (they keep their data and series)."""
        return list(self._hidden)

    @property
    def anchor(self):
        """The chart new ones are attached to (the first registered one)."""
        return self._charts[0]

    @property
    def kind(self) -> Optional[KIND]:
        """``'horizontal'`` / ``'vertical'`` once arranged, else ``None``."""
        return self._kind

    @property
    def sync_mode(self) -> Optional[str]:
        """The link in place: ``None`` (independent), ``'full'`` or
        ``'crosshair'``."""
        return self._mode

    # ---------------------------------------------------------- membership
    def register(self, chart) -> None:
        """Add a chart to the layout (the first one becomes the anchor)."""
        if chart in self._charts or chart in self._hidden:
            return
        self._charts.append(chart)

    def unregister(self, chart) -> None:
        """Remove a chart from the layout without resizing the others."""
        if chart in self._charts:
            self._charts.remove(chart)
        elif chart in self._hidden:
            self._hidden.remove(chart)
        self._synced.pop(chart, None)

    # ------------------------------------------------------------- arrange
    def arrange(self, kind: KIND = HORIZONTAL, count: int = 2,
                sync: SYNC = SYNC_NONE, on_create=None,
                divider: Optional[bool] = None,
                divider_size: Optional[int] = None,
                divider_color: Optional[str] = None,
                divider_hover_color: Optional[str] = None,
                **kwargs) -> List:
        """Lay `count` charts out in a row / column and return them.

        Missing charts are created and `on_create` is called with each of them;
        extra ones are hidden. Every visible chart gets an equal share of the
        window.

        `sync` links the charts to the anchor chart: ``True`` / ``'full'``
        makes them pan, zoom and crosshair together, ``'crosshair'`` (also
        ``'crosshairs_only'``) links only the crosshair, and ``False`` /
        ``None`` (the default) leaves them independent. The link covers the
        charts that already exist too, and calling `arrange` again changes or
        drops it.

        `kwargs` are forwarded to :meth:`AbstractChart.create_subchart`.

        `divider` / `divider_size` / `divider_color` / `divider_hover_color`
        change the draggable separators for good (`Layout.set_divider` does the
        same without arranging anything).
        """
        if kind not in (HORIZONTAL, VERTICAL):
            raise ValueError(
                f"kind must be 'horizontal' or 'vertical', not {kind!r}")
        if count < 1:
            raise ValueError(f'count must be at least 1, not {count}')
        if not self._charts:
            raise ValueError(
                'the layout has no chart yet: create a chart (or call '
                'layout.register(chart)) before arranging charts')

        mode = _sync_mode(sync)

        was_tiles = self._tiles is not None
        self._tiles = None            # 离开 tiles 布局 ✓
        while len(self._charts) < count:
            chart = self._hidden.pop() if self._hidden else None
            if chart is None:
                # a new chart registers itself with the window's layout, so
                # `register` (idempotent) puts it in place of a plain append
                chart = self._create(sync_mode=mode, on_create=on_create,
                                     **kwargs)
            self.register(chart)
        while len(self._charts) > count:
            chart = self._charts.pop()
            self._hide(chart)
            self._hidden.append(chart)

        self._apply_sync(mode)

        if was_tiles:
            # the wrappers are still absolutely positioned from the 2D layout;
            # hand them back to the float layout before sizing the row/column
            self._clear_tiles()

        share = 1 / len(self._charts)
        for chart in self._charts:
            if kind == HORIZONTAL:
                chart.resize(share, 1.0)
            else:
                chart.resize(1.0, share)
        self._kind = kind
        self._divider_options(divider, divider_size, divider_color,
                              divider_hover_color)
        self._apply_dividers()
        return self.charts

    def _clear_tiles(self) -> None:
        """Leave a 2D layout: restore the float geometry of every chart.

        The hidden charts are included too - they keep the absolute styles of a
        previous tiles layout as well, and are reused by a later ``arrange``.
        """
        charts = list(self._charts) + list(self._hidden)
        if not charts:
            return
        ids = ', '.join(chart.id for chart in charts)
        self.win.run_script(f'''
            Lib.clearLayoutTiles(
                {js_value(self._id)},
                [{ids}]
            )
        ''', run_last=True)

    def arrange_tiles(self, tiles, sync: SYNC = SYNC_NONE,
                      on_create=None, dividers: bool = False,
                      **kwargs) -> List:
        """Lay the charts out as **arbitrary rectangles** (2D).

        ``tiles`` is an ordered list of ``(width, height)`` fractions (0..1),
        e.g. TradingView-style 2D layouts::

            layout.arrange_tiles([(1.0, 0.5), (0.5, 0.5), (0.5, 0.5)])
            #   上 1 满宽 + 下 2 并排
            layout.arrange_tiles([(0.5, 0.5), (0.5, 0.5), (1.0, 0.5)])
            #   上 2 并排 + 下 1 满宽

        Missing charts are created (``on_create`` called for each), extra ones
        are hidden, exactly like :meth:`arrange`. Each chart gets its own
        ``resize(width, height)`` — the page flows them in order, so the order
        of ``tiles`` matters.

        Draggable dividers are **off** by default (they assume a single row /
        column); pass ``dividers=True`` only for a plain row/column.
        """
        tiles = [(float(w), float(h)) for w, h in tiles]
        if not tiles:
            raise ValueError('tiles must not be empty')
        if not self._charts:
            raise ValueError(
                'the layout has no chart yet: create a chart (or call '
                'layout.register(chart)) before arranging charts')

        mode = _sync_mode(sync)
        count = len(tiles)
        while len(self._charts) < count:
            chart = self._hidden.pop() if self._hidden else None
            if chart is None:
                chart = self._create(sync_mode=mode, on_create=on_create,
                                     **kwargs)
            self.register(chart)
        while len(self._charts) > count:
            chart = self._charts.pop()
            self._hide(chart)
            self._hidden.append(chart)

        self._apply_sync(mode)
        # 排成 (x, y, w, h)（按行流式：放不下就换行 ✓），再交给 JS 绝对定位 ✓ ——
        # 老路（只设 width/height 靠 float 流）在换布局后会残留旧尺寸 ✗，而且
        # 竖向排列 / 2D 都排不出来 ✓。
        self._tiles = tiles
        self._tiles_dividers = bool(dividers)
        self._apply_tiles_js()
        for chart, (width, height) in zip(self._charts, tiles):
            # 兜底：JS 不可用时至少把尺寸写对 ✓
            chart.resize(width, height)
        # 注意：**不能**把 ``_kind`` 设成 ``'tiles'`` —— ``single()`` /
        # ``horizontal()`` 会把他当 kind 传给 ``arrange``，于是抛
        # ``kind must be 'horizontal' or 'vertical', not 'tiles'`` ✗。
        # tiles 规格另存一份即可 ✓。
        self._kind = None
        # 分割条由 `setLayoutTiles` 在 JS 侧按 tile 间隙建 ✓（见上），
        # 这里不要再走 float 版的 `_apply_dividers` ✗（会叠一层错的）。
        self._divider_options(bool(dividers))
        return self.charts

    def _apply_tiles_js(self) -> None:
        """把当前的 tiles 规格 + 分割条配色重新下发给 JS 绝对定位层 ✓。

        ``arrange_tiles`` 会用一次；主题切换时 ``set_divider(color=…)`` 再用一次
        —— 否则浅色主题下间隔条还是深色 ✗。
        """
        if not self._tiles:
            return
        base = _flow_tiles(self._tiles)
        ids = ', '.join(chart.id for chart in self._charts)
        gap = self.divider_size if self._tiles_dividers else 0
        self.win.run_script(f'''
            Lib.setLayoutTiles(
                {js_value(self._id)},
                [{ids}],
                {js_value(base)},
                {js_value(gap)},
                {js_value(self.divider_color)},
                {js_value(self.divider_hover_color)}
            )
        ''', run_last=True)

    def horizontal(self, count: int = 2, **kwargs) -> List:
        """左右布局：`count` 张并排（默认在右侧加一张，彼此独立）。

        ``sync=True`` 让它们与第一张图联动平移 / 缩放 / 十字线，
        ``sync='crosshair'`` 只联动十字线。
        """
        return self.arrange(HORIZONTAL, count, **kwargs)

    def vertical(self, count: int = 2, **kwargs) -> List:
        """上下布局：`count` 张上下排（默认在下方加一张，彼此独立）。

        ``sync=True`` 让它们与第一张图联动平移 / 缩放 / 十字线，
        ``sync='crosshair'`` 只联动十字线。
        """
        return self.arrange(VERTICAL, count, **kwargs)

    def single(self, kind: Optional[KIND] = None, **kwargs) -> List:
        """Collapse back to one full-size chart (the others are hidden)."""
        # ``_kind`` 可能是 None（比如刚跑过 ``arrange_tiles`` ✓），
        # 也绝不能把 'tiles' 之类的东西传下去 ✗。
        current = self._kind if self._kind in (HORIZONTAL, VERTICAL) else None
        self._kind = kind or current
        return self.arrange(self._kind or HORIZONTAL, 1, **kwargs)

    def set_divider(self, enabled: Optional[bool] = None,
                    size: Optional[int] = None,
                    color: Optional[str] = None,
                    hover_color: Optional[str] = None) -> 'Layout':
        """Restyle / show / hide the draggable separators and redraw them."""
        self._divider_options(enabled, size, color, hover_color)
        if self._kind is not None:
            self._apply_dividers()
        elif self._tiles:
            # tiles 布局（``_kind`` 是 None）的间隔条由 setLayoutTiles 画，
            # 换了颜色要重新下发一次 ✓（否则浅色主题下间隔条还是深色 ✗）
            self._apply_tiles_js()
        return self

    def _divider_options(self, enabled=None, size=None, color=None,
                         hover_color=None) -> None:
        if enabled is not None:
            self.divider = bool(enabled)
        if size is not None:
            self.divider_size = size
        if color is not None:
            self.divider_color = color
        if hover_color is not None:
            self.divider_hover_color = hover_color

    def _apply_dividers(self) -> None:
        """Hand the charts to the JS splitter: it subtracts the divider space
        out of the page and lets the user drag it between neighbours."""
        show = self.divider
        ids = ', '.join(chart.id for chart in self._charts)
        size = self.divider_size if show else 0
        self.win.run_script(f'''
            Lib.setLayoutDividers(
                {js_value(self._id)},
                [{ids}],
                {js_value(self._kind or HORIZONTAL)},
                {size},
                {js_value(self.divider_color)},
                {js_value(self.divider_hover_color)},
                {js_value(self._callback_id)}
            )
        ''', run_last=True)

    def _on_drag(self, *shares: str) -> None:
        """A divider was dragged: adopt the shares the JS side reports."""
        axis = 'height' if self._kind == VERTICAL else 'width'
        for chart, share in zip(self._charts, shares):
            try:
                setattr(chart, f'_{axis}', float(share))
            except (TypeError, ValueError):
                return

    # ------------------------------------------------------------ internal
    def _apply_sync(self, mode: Optional[str]) -> None:
        """Link (or unlink) every visible chart with the anchor chart."""
        anchor = self.charts[0]
        for chart in self._charts[1:]:
            current = self._synced.get(chart)
            if current == mode:
                continue
            if mode is None:
                if current is not None:
                    anchor.unsync(chart)
                    self._synced.pop(chart, None)
                continue
            # `sync` replaces the previous link in JS, so switching between
            # 'crosshair' and 'full' cannot stack handlers
            anchor.sync(chart, crosshairs_only=mode == SYNC_CROSSHAIR)
            self._synced[chart] = mode
        self._mode = mode

    def _create(self, sync_mode: Optional[str] = None, on_create=None,
                **kwargs):
        chart = self.anchor.create_subchart(
            position='left', width=0.5, height=0.5,
            sync=True if sync_mode else None,
            sync_crosshairs_only=sync_mode == SYNC_CROSSHAIR, **kwargs)
        if sync_mode is not None:
            self._synced[chart] = sync_mode
        hook = self.on_create if on_create is None else on_create
        if hook is not None:
            hook(chart)
        return chart

    @staticmethod
    def _hide(chart) -> None:
        """Park a chart outside the layout: 0x0, still alive and reusable."""
        chart.resize(0, 0)
