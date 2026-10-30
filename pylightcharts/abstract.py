import asyncio
import json
import numbers
import numpy as np
import os
import queue
import sys
import threading
import time
import uuid
from base64 import b64decode, b64encode
from contextlib import contextmanager
from datetime import datetime
from typing import (TYPE_CHECKING, Callable, Union, Literal,
                    List, Optional)
import pandas as pd

from .table import POSITION, Table
from . import indicators
from .colors import color_by
from .indicators import swing_points, zigzag
from .layout import Layout
from .toolbox import ToolBox
from .price_scale import PriceLine, PriceScale
from .indicators_api import IndicatorMixin, _IndicatorBinding
from .drawings import (
    AndrewsPitchfork, Box, Fibonacci, FibonacciExtension, GannFan, HorizontalLine,
    HorizontalSpan, LineFill,
    Measure, ParallelChannel, Position, RayLine, ThreePointDrawing, TrendLine,
    Triangle, TwoPointDrawing, VerticalLine, VerticalSpan,
)
from .topbar import TopBar
from .util import (
    infer_time_unit,
    BulkRunScript, Pane, Events, IDGen, as_enum, jbool, js_json, js_call, js_value, ref, TIME, NUM, FLOAT,
    LINE_STYLE, MARKER_POSITION, MARKER_SHAPE, CROSSHAIR_MODE, BridgeError,
    snake_to_camel,
    PRICE_SCALE_MODE, marker_position, marker_shape, js_data, encode_series_data,
)
from .plugins import (
    SeriesMarkersPlugin, UpDownMarkersPlugin, TextWatermarkPlugin, ImageWatermarkPlugin,
)
from .tooltips import TOOLTIP_MODE, Tooltip

if TYPE_CHECKING:                       # pragma: no cover - typing only
    from .history import InfiniteHistory
from .primitives import SeriesPrimitive, PanePrimitive

current_dir = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(current_dir, 'js', 'index.html')

#: Whether newly created charts draw the TradingView attribution logo (the small
#: "Charting by TradingView" mark in the bottom-left of every chart). Hidden by
#: default; see :func:`set_attribution_logo`.
ATTRIBUTION_LOGO = False


def set_attribution_logo(visible: bool) -> None:
    """Show the TradingView attribution logo on charts created from now on.

    Lightweight Charts reads ``layout.attributionLogo`` while a chart is being
    built and never re-renders it afterwards, so this cannot change a chart that
    is already on screen - create the chart after calling it (subcharts included).

    The library hides the logo by default. Lightweight Charts is Apache-2.0 and
    its notice asks for attribution: if you ship an application that keeps this
    hidden, credit TradingView and link to https://www.tradingview.com/ somewhere
    your users can see it - that link is what the logo would otherwise provide.
    """
    global ATTRIBUTION_LOGO
    ATTRIBUTION_LOGO = bool(visible)


#: engine shape of `baseValue` (see lightweight-charts ``BaseValuePrice``)
_BASE_VALUE_KEYS = ('base_value', 'baseValue')


def _normalize_base_value(kind: Optional[str], options: dict) -> dict:
    """Wrap a plain ``base_value=100`` into ``{type: 'price', price: 100}``.

    The engine reads ``baseValue.price``, so a bare number makes its gradient
    stops non-finite and the baseline silently stops being drawn (the series
    still exists, so hover/legend keep working).
    """
    if kind != 'Baseline' or not options:
        return options
    for key in _BASE_VALUE_KEYS:
        value = options.get(key)
        if isinstance(value, numbers.Real) and not isinstance(value, bool):
            options = {**options,
                       key: {'type': 'price', 'price': float(value)}}
    return options


class Window:
    _id_gen = IDGen()
    handlers = {}
    # the webview is single threaded, so round-trips are serialised; a lock plus
    # per-request ids guarantees a reply can never reach the wrong caller
    _round_trip_lock = threading.RLock()
    #: seconds to wait for a value returned from the webview
    round_trip_timeout = 30.0

    def __init__(
        self,
        script_func: Optional[Callable] = None,
        js_api_code: Optional[str] = None,
        run_script: Optional[Callable] = None
    ):
        self.loaded = False
        self.script_func = script_func
        self.scripts = []
        self.final_scripts = []
        self._preload_count = 0
        # `bulk_run` 需要一个真正能把合并后的脚本发出去的函数。有的后端
        # （StaticLWC / BrowserChart）只传 `run_script`（它们自己就是发货口），
        # 不传 `script_func` —— 这时用 `run_script` 兜底，否则 `chart.batch()`
        # 退出时会报 `NoneType is not callable`（浏览器 / 静态图批量下发失效 ✗）。
        self.bulk_run = BulkRunScript(
            script_func if script_func is not None else run_script)
        self._page_topbar: Optional['TopBar'] = None
        self._layout: Optional['Layout'] = None
        self._theme: Optional[dict] = None
        #: floating tables built on this window (they follow a theme switch)
        self._tables: list = []
        #: DOM panels (DataGrid / Sparkline, see ``pylightcharts.panels``);
        #: they follow a theme switch too
        self._panels: list = []

        if run_script:
            self.run_script = run_script

        if js_api_code:
            # 这一句是队列里的第一条。以前是直接赋值：桥（Qt 的
            # window.pythonObject、wx 的 wx_msg…）还没就绪时抛 TypeError，
            # 而脚本是**批量**下发的 —— 后面的 new Lib.Handler(...) / setData
            # 全被跳过，表现就是"窗口在、图全白"。包一层 try 之后，桥晚到只影响
            # 回调，图表本身照常渲染。
            self.run_script(
                '(function () { try { window.callbackFunction = '
                f'{js_api_code}; }} catch (error) {{ '
                'window.callbackFunction = function () {}; '
                'console.warn("pylightcharts: web bridge not ready", error); '
                '} })()')

    def theme(self, name='dark', **overrides) -> 'Window':
        """Apply a whole-UI colour theme to every chart of this window.

        `name` is ``'light'`` / ``'dark'`` (see :mod:`pylightcharts.themes`) or a
        dict of colours; `**overrides` replaces single colours:

            chart.win.theme('light')
            chart.win.theme('light', up='#0a7d5a')

        It styles the root CSS variables (top bar, legend, menus, hover states)
        plus every chart's background, grid, crosshair, candles, volume, price
        scale and pane separators - and charts created later inherit it. Every
        individual setter still works afterwards and wins over the theme.
        """
        from .themes import resolve as resolve_theme
        spec = resolve_theme(name, overrides)
        self._theme = spec
        self.style(background_color=spec['background'],
                   hover_background_color=spec['hover_background'],
                   click_background_color=spec['click_background'],
                   active_background_color=spec['active_background'],
                   muted_background_color=spec['muted_background'],
                   border_color=spec['border_color'],
                   color=spec['text'],
                   active_color=spec['active_text'])
        for chart in self._themed_charts():
            chart._apply_theme(spec)
        for table in list(self._tables):
            table.apply_theme(spec)
        for panel in list(self._panels):
            panel.apply_theme(spec)
        return self

    def _themed_charts(self) -> list:
        """Every chart of the window (visible and parked ones)."""
        if self._layout is None:
            return []
        return list(self._layout.charts) + list(self._layout.hidden_charts)

    @property
    def layout(self) -> 'Layout':
        """The :class:`~pylightcharts.layout.Layout` of this window.

        Charts register themselves when they are created, so the first chart of
        the window is the anchor the others are attached to::

            chart.win.layout.vertical()      # 上下：add one below
            chart.win.layout.horizontal(3)   # 左右：three in a row
        """
        if self._layout is None:
            self._layout = Layout(self)
        return self._layout

    def page_topbar(self) -> 'TopBar':
        """The top bar that spans the window, above every chart.

        Unlike :attr:`AbstractChart.topbar` (which lives inside one chart and
        shrinks with it) this bar stays put at the top of the page when charts
        are added below it. Its widget callbacks receive this window, e.g.
        ``bar.menu('layout', ('上下布局', '左右布局'), func=on_layout)`` with
        ``def on_layout(win): win.layout.vertical()``.
        """
        if self._page_topbar is None:
            self._page_topbar = TopBar(self, page=True)
        return self._page_topbar

    def preload(self, script: str):
        """Queue `script` to run *before* the chart handler is created.

        Must be called before the webview loads. Useful for registering JS
        extensions such as custom horizontal scale behaviors::

            chart.win.preload("Lib.registerHorzScaleBehavior('x', new X())")
        """
        if self.loaded:
            raise RuntimeError(
                'preload() must be called before the webview loads')
        self.scripts.insert(self._preload_count, script)
        self._preload_count += 1

    def on_js_load(self):
        if self.loaded:
            return
        self.loaded = True

        # the webview 'loaded' event already fired, but some backends (Qt/wx) are
        # racy, so wait - without busy-looping - for the document to be complete
        if getattr(self, '_return_q', None) is not None:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                try:
                    if self.run_script_and_get('document.readyState === "complete"', timeout=1.0):
                        break
                except Exception:
                    pass
                time.sleep(0.05)

        # Evaluate the queued scripts one by one: joining them would make the
        # first failure swallow the rest of the setup, and the message would
        # show only the head of the whole batch.
        self.scripts.extend(self.final_scripts)
        for script in self.scripts:
            self.script_func(script)

    def run_script(self, script: str, run_last: bool = False):
        """
        For advanced users; evaluates JavaScript within the Webview.
        """
        if self.script_func is None:
            raise AttributeError("script_func has not been set")
        if self.loaded:
            if self.bulk_run.enabled:
                self.bulk_run.add_script(script)
            else:
                self.script_func(script)
        elif run_last:
            self.final_scripts.append(script)
        else:
            self.scripts.append(script)

    def run_script_and_get(self, script: str, timeout: Optional[float] = None):
        """Evaluate a JS expression and return its value.

        Replies are correlated by request id, so a stale reply (e.g. from an
        earlier timed-out call) can never be handed to the wrong caller. JS
        errors are raised as :class:`~pylightcharts.util.BridgeError` instead of
        silently returning ``None``.
        """
        return_queue = getattr(self, '_return_q', None)
        if return_queue is None:
            raise BridgeError('No webview attached (headless chart?)')
        timeout = self.round_trip_timeout if timeout is None else timeout
        request_id = uuid.uuid4().hex

        with Window._round_trip_lock:
            self.run_script(f'_~_~RETURN~_~_{request_id}~|~{script}')
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f'No reply from the webview for: {script[:200]}')
                try:
                    reply = return_queue.get(timeout=remaining)
                except queue.Empty:
                    raise TimeoutError(
                        f'No reply from the webview for: {script[:200]}')
                if isinstance(reply, tuple) and len(reply) == 3 and reply[0] == request_id:
                    _, ok, payload = reply
                    if not ok:
                        raise BridgeError(payload)
                    return payload
                # otherwise: a stale reply, keep waiting for ours

    # ------------------------------------------------------------------
    # Generic bridge
    # ------------------------------------------------------------------
    def invoke(self, handle: str, method: str, *args, store_as: Optional[str] = None) -> None:
        """Call `handle.method(*args)` inside the webview (fire-and-forget).

        `handle` is a JS handle such as `window.abcdefgh` (a chart) or
        `window.abcdefgh.series`. When `store_as` is given, the return value is
        registered under that handle so it can be addressed in later calls.
        See `jslib/src/general/rpc.ts`.

        ★ 结尾补 ``null``：PyQt6 的 ``runJavaScript`` 即使不传回调，也会把
        **最后一个表达式的值**转成 ``QVariant`` —— 当它是活的 LWC 对象（如
        ``addPane`` 返回的 pane、``getSeries`` 返回的序列）时，渲染进程会卡死
        （同 :meth:`Pane._invoke_assign` 的坑 ✗）。补 ``null`` 让整段脚本
        求值成 ``null``，但 ``store_as`` 的注册仍照常执行 ✓。
        """
        self.run_script(js_call(handle, method, args, store_as) + '\nnull')

    def invoke_get(self, handle: str, method: str, *args):
        """Like :meth:`invoke` but returns the (JSON-serializable) result."""
        return self.run_script_and_get(js_call(handle, method, args))

    def eval_js(self, expression: str):
        """Evaluate an arbitrary JS expression and return its value."""
        return self.run_script_and_get(expression)

    def read_property(self, handle: str, path: Optional[str] = None):
        """Read a value from a JS handle (property or zero-arg call).

        Unlike :meth:`invoke` this works for *non-function* values and goes
        through ``Lib.lookup`` so both registry handles and dotted global paths
        are supported. ``path`` is appended verbatim, so a call is allowed too::

            chart.win.read_property(f'{chart.id}.chart', 'options()')
            chart.win.read_property(f'{chart.id}.chart', 'timeScale().options()')

        Only JSON-serializable values come back. Live objects must be kept with
        ``store_as`` (see :meth:`invoke`) instead of being returned here.
        """
        expression = f'Lib.lookup({json.dumps(handle)})'
        if path:
            expression += f'.{path}'
        return self.eval_js(expression)

    def create_table(
        self,
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
    ) -> 'Table':
        theme = getattr(self, '_theme', None)
        if theme:
            # a window theme supplies the colours unless they were given
            if background_color == '#121417':
                background_color = theme['table_background']
            if border_color == 'rgb(70, 70, 70)':
                border_color = theme['table_border']
        table = Table(self, width, height, headings, widths, alignments,
                      position, draggable, margin_x, margin_y,
                      background_color, border_color,
                      border_width, heading_text_colors,
                      heading_background_colors, return_clicked_cells, func)
        if theme:
            table.apply_theme(theme)
        return table

    def create_data_grid(self, columns=None, **options):
        """Create a :class:`~pylightcharts.panels.DataGrid` on this window.

        The table appends itself to the page container; it can share a page
        with charts or live on a chart-less
        :class:`~pylightcharts.QtPanel`. See :mod:`pylightcharts.panels`.
        """
        from .panels import DataGrid
        return DataGrid(self, columns, **options)

    def create_sparkline(self, **options):
        """Create a :class:`~pylightcharts.panels.Sparkline` on this window."""
        from .panels import Sparkline
        return Sparkline(self, **options)

    def create_subchart(
        self,
        position: FLOAT = 'left',
        width: float = 0.5,
        height: float = 0.5,
        sync_id: Optional[str] = None,
        scale_candles_only: bool = False,
        sync_crosshairs_only: bool = False,
        toolbox: bool = False,
        keyboard: bool = True
    ) -> 'AbstractChart':
        subchart = AbstractChart(
            self,
            width,
            height,
            scale_candles_only,
            toolbox,
            position=position,
            keyboard=keyboard
        )
        if not sync_id:
            return subchart
        self.run_script(f'''
            Lib.Handler.syncCharts(
                {subchart.id},
                {sync_id},
                {jbool(sync_crosshairs_only)}
            )
        ''', run_last=True)
        return subchart

    def style(
        self,
        background_color: str = '#0c0d0f',
        hover_background_color: str = '#3c434c',
        click_background_color: str = '#50565E',
        active_background_color: str = 'rgba(0, 122, 255, 0.7)',
        muted_background_color: str = 'rgba(0, 122, 255, 0.3)',
        border_color: str = '#3C434C',
        color: str = '#d8d9db',
        active_color: str = '#ececed'
    ):
        self.run_script(f'Lib.Handler.setRootStyles({js_json(locals())});')


class SeriesCommon(Pane):
    def __init__(self, chart: 'AbstractChart', name: str = ''):
        super().__init__(chart.win)
        self._chart = chart
        if hasattr(chart, '_interval'):
            self._interval = chart._interval
        else:
            self._interval = 1
        self._last_bar = None
        #: set when the candles' price scale is inverted (价格倒挂): the helpers
        #: that mark "at the high / at the low" have to flip with it
        self._price_scale_inverted = False
        self.name = name
        self.num_decimals = 2
        self.offset = 0
        self.data = pd.DataFrame()
        #: pane this series lives in (0 = main; updated by ``move_to_pane`` and by
        #: the ``pane_index`` argument of the factories)
        self._pane_index = 0
        self.markers = {}
        self._price_lines = []
        #: last visibility set through hide_data()/show_data() (the legend eye
        #: toggles it inside JS, so this can go stale after a click - it is the
        #: python-side default, not a live read)
        self._visible = True

    def _set_interval(self, df: pd.DataFrame):
        if not pd.api.types.is_datetime64_any_dtype(df['time']):
            # this is the first place a `time` column is interpreted, so the unit
            # has to be inferred here: a bare epoch number would be read as
            # nanoseconds, and every chart keeps `time` in *seconds*
            # (`candle_data`), so feeding that column back into `set()` used to
            # land in 1970 (`infer_time_unit`)
            unit = (infer_time_unit(df['time'])
                    if pd.api.types.is_numeric_dtype(df['time']) else None)
            df['time'] = pd.to_datetime(df['time'], unit=unit)
        common_interval = df['time'].diff().value_counts()
        if common_interval.empty:
            return
        self._interval = common_interval.index[0].total_seconds()

        units = [
            pd.Timedelta(
                microseconds=df['time'].dt.microsecond.value_counts().index[0]),
            pd.Timedelta(seconds=df['time'].dt.second.value_counts().index[0]),
            pd.Timedelta(minutes=df['time'].dt.minute.value_counts().index[0]),
            pd.Timedelta(hours=df['time'].dt.hour.value_counts().index[0]),
            pd.Timedelta(days=df['time'].dt.day.value_counts().index[0]),
        ]
        self.offset = 0
        for value in units:
            value = value.total_seconds()
            if value == 0:
                continue
            elif value >= self._interval:
                break
            self.offset = value
            break

    @staticmethod
    def _format_labels(data, labels, index, exclude_lowercase):
        def rename(la, mapper):
            return [mapper[key] if key in mapper else key for key in la]
        if 'date' not in labels and 'time' not in labels:
            labels = labels.str.lower()
            if exclude_lowercase:
                labels = rename(
                    labels, {exclude_lowercase.lower(): exclude_lowercase})
        if 'date' in labels:
            labels = rename(labels, {'date': 'time'})
        elif 'time' not in labels:
            data['time'] = index
            labels = [*labels, 'time']
        return labels

    def _df_datetime_format(self, df: pd.DataFrame, exclude_lowercase=None):
        df = df.copy()
        df.columns = self._format_labels(
            df, df.columns, df.index, exclude_lowercase)
        self._set_interval(df)
        if not pd.api.types.is_datetime64_any_dtype(df['time']):
            # a numeric time axis carries epoch values and pandas would read them
            # as nanoseconds: infer seconds / ms / us / ns from the magnitude -
            # every chart keeps `time` in seconds (`candle_data`), so feeding
            # that column back into `set()` used to land in 1970
            unit = None
            if pd.api.types.is_numeric_dtype(df['time']):
                unit = infer_time_unit(df['time'])
            df['time'] = pd.to_datetime(df['time'], unit=unit)
        df['time'] = df['time'].astype('int64') // 10 ** 9
        return df

    def _series_datetime_format(self, series: pd.Series, exclude_lowercase=None):
        series = series.copy()
        series.index = self._format_labels(
            series, series.index, series.name, exclude_lowercase)
        series['time'] = self._single_datetime_format(series['time'])
        return series

    def _single_datetime_format(self, arg) -> float:
        """Snap one time value onto the chart's bar grid (epoch seconds).

        Numbers are unit-inferred by magnitude, because every chart of this
        package keeps its `time` column in **epoch seconds** (`candle_data`) while
        hand-written code often passes milliseconds (and pandas' ``int64`` times
        are nanoseconds).
        """
        if isinstance(arg, (str, numbers.Number))                 or not pd.api.types.is_datetime64_any_dtype(arg):
            unit = None
            if isinstance(arg, numbers.Number) and not isinstance(arg, bool):
                unit = infer_time_unit([arg])
            try:
                arg = pd.to_datetime(arg, unit=unit)
            except ValueError:
                arg = pd.to_datetime(arg)
        # 没从数据里推出周期时 ``_interval`` 可能是 0（例如帧只有一行 / 还没 set 过）；
        # 直接 ``// self._interval`` 会 ZeroDivisionError('float floor division by zero') ✗
        interval = self._interval or 1
        arg = interval * (arg.timestamp() // interval) + self.offset
        return arg

    def _inverted(self, inverted: Optional[bool] = None) -> bool:
        """Is the price scale inverted? `inverted=` overrides the guess."""
        if inverted is not None:
            self._price_scale_inverted = bool(inverted)
        return bool(getattr(self, '_price_scale_inverted', False))

    @property
    def pane_index(self) -> int:
        """The pane this series lives in (0 = the main pane)."""
        return getattr(self, '_pane_index', 0) or 0

    def _time_based(self) -> bool:
        """Whether the chart's horizontal scale is time (False for numeric-x charts)."""
        return getattr(self._chart, '_time_based', True)

    def set(self, df: Optional[pd.DataFrame] = None, format_cols: bool = True):
        if df is None or df.empty:
            self.run_script(f'{self.id}.series.setData([])')
            self.data = pd.DataFrame()
            return
        if format_cols and self._time_based():
            df = self._df_datetime_format(df, exclude_lowercase=self.name)
        if self.name:
            # for a single-value series the name is the *column* to plot; a bar
            # series (candles) carries its name as a legend label instead, so an
            # overlay with both OHLC data and a symbol name works
            if self.name in df:
                df = df.rename(columns={self.name: 'value'})
            elif not {'open', 'high', 'low', 'close'} <= set(df.columns):
                raise NameError(f'No column named "{self.name}".')
        self.data = df.copy()
        self._last_bar = df.iloc[-1]
        # ★ 单序列缺口路径：**在唯一一次 setData 时就把缺口点染透明** ——
        #   以前先 setData(原始 NaN) 再由 `_draw_gap_single_series` 重新
        #   setData(上色帧)，同一份大 payload 要序列化/下发两次 ✗。
        frame = df
        if not self.__dict__.get('_skip_gap'):
            segments = self._split_gap_segments(df)
            if len(segments) >= 2 and (
                    self.__dict__.get('_prefer_single_gap')
                    or len(segments) > self.MAX_GAP_SEGMENTS):
                colored = self._single_gap_frame(df)
                if colored is not None:
                    frame = colored
                    self._clear_gap_series()      # 清掉可能残留的分段序列
                    self._set_main_visible()      # 单序列路径主线保持可见
        self.run_script(
            f'{self.id}.series.setData({encode_series_data(frame)}); ')
        if frame is df:
            self._sync_gap_segments(df)

    # ------------------------------------------------------------------
    # NaN 断点：LWC v5 的 whitespace 只延长时间轴，**不会断线**（纯引擎渲染
    # 验证过），所以断开由这里自己做 —— 主序列隐藏，每段画一条同款、
    # 不进图例、不带价格标签的 Line 序列。
    # ------------------------------------------------------------------

    @staticmethod
    def _is_finite_value(value) -> bool:
        try:
            return bool(pd.notna(value)) and float(value) == float(value)
        except (TypeError, ValueError):
            return False

    def _gap_value_column(self, df):
        """拿"要画的那一列"（单值序列；OHLC 不参与断点）。"""
        # 只处理 Line：Area 的"填充"是另一套字段（topColor/bottomColor），
        # 只藏线不藏填充反而更糟，等有需求再单独做
        if getattr(self, 'kind', None) != 'Line':
            return None
        if not hasattr(self, '_time_based') or not df.columns.size:
            return None
        if 'value' in df:
            return 'value'
        return self.name if (self.name and self.name in df) else None

    def _split_gap_segments(self, df) -> list:
        """按 NaN 把数据切成连续段；没有 NaN 时返回空列表。"""
        column = self._gap_value_column(df)
        if column is None:
            return []
        values = pd.to_numeric(df[column], errors='coerce').to_numpy(dtype=float)
        finite = np.isfinite(values)              # NaN / inf 都算缺失
        if finite.all():
            return []                             # 常态：一次 numpy 判断（微秒级）
        # 连续 True 段的起止：向量化求差分，不跑 Python 逐行循环
        edges = np.diff(np.concatenate(([0], finite.view(np.int8), [0])))
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        return [df.iloc[int(first):int(last)]
                for first, last in zip(starts, ends)]

    def _remember_options(self, options: dict) -> None:
        """记下本序列用过的样式（`apply_options` / `style` 都会经过）。"""
        local = self.__dict__.setdefault('_local_options', {})
        for key, value in (options or {}).items():
            local[key] = value

    def _gap_series_style(self) -> dict:
        """复制主序列当前的线型样式（颜色/宽度/虚实/刻度 等）。

        **纯本地读取**：早先这里调 `series.options()`（阻塞式 JS 往返），而它发生在
        `set()` 里、窗口还没显示，会把启动拖慢好几秒；现在只读创建时 + 之后
        `apply_options` 记下来的那份副本。
        """
        local = self.__dict__.get('_local_options') or {}
        style = {}
        for key in ('color', 'line_width', 'line_style', 'line_type',
                    'crosshair_marker_radius', 'crosshair_marker_visible',
                    'price_scale_id', 'price_format', 'point_markers_visible',
                    'line_visible'):
            camel = snake_to_camel(key)
            if key in local:
                style[key] = local[key]
            elif camel in local:
                style[key] = local[camel]
        # 价格线 / 最后一价标签 / 图例只由主序列负责，避免重复
        style['price_line_visible'] = False
        style['last_value_visible'] = False
        return style

    def _clear_gap_series(self) -> None:
        had = bool(self.__dict__.get('_gap_series'))
        for series in self.__dict__.get('_gap_series') or []:
            try:
                series.delete()
            except Exception:
                pass
        self.__dict__['_gap_series'] = []
        if had:
            try:                     # 摘掉主序列上的分段引用（否则是死对象）
                self.run_script(f'{self.id}.series.__gapSegments = [];')
            except Exception:
                pass

    #: 拆段上限：段数超过它就不再一段一个序列。
    #:
    #: 一段一个 `addSeries` + `setData` 会造出成百上千个内部序列，每个都是一次
    #: JS 往返 + 一次浏览器重绘，表现就是"指标线一条条从左到右画出来 + 加载
    #: 明显变慢"。超过这个段数就改用 :meth:`_draw_gap_single_series`（一个序列 +
    #: 透明缺口），断开的视觉效果一样，却只占一个序列。
    MAX_GAP_SEGMENTS = 64
    #: 兜底路径的碎片化判定：平均段长低于它（= 逐 bar 交替 NaN）就回单序列
    MIN_GAP_SEGMENT_LEN = 3
    #: 分段序列的**兜底上限**：只有透明缺口路径用不了（拿不到线色等）时才走到
    #: 这里 —— 超过它就直接回单序列，免得造出几百上千个分段序列。
    MAX_GAP_SPLIT_SERIES = 256
    #: 透明缺口色：缺口点补成前值并染成透明，引擎就不会画那一段。
    GAP_COLOR = 'rgba(0, 0, 0, 0)'
    #: 创建时没显式给色的线，实际渲染用的是 LWC v5 Line 引擎默认色
    #: （``lineStyleDefaults.color = '#2196f3'``，与 ``seriesColor()`` 的兜底
    #: 一致）；透明缺口路径要靠它给非缺口点上色，拿不到也不能放弃单序列路径
    #: （回退成一段一序列，77 段就能把渲染线程永久拖死 ✗）。
    #: ★ 必须与引擎默认色**完全一致**，否则无色的指标线会莫名换成另一种蓝 ✗。
    DEFAULT_LINE_COLOR = '#2196f3'

    def skip_gap_segments(self, value: bool = True):
        """不要再为 NaN 断点拆分段序列（**隐藏载体线**用 ✓）。

        色带的上下沿常常是 ``isplot=False`` 的隐藏线（线宽 0 / 完全透明），
        只用来给 ``fill_between`` 当承载体 —— 它们不需要“断线”效果，却会被
        拆成上百个分段序列（实测 HemaTrendLevels 的 8 条边在 2000 根上各有
        45 段 → 360 个序列），历史加载时直接卡死 ✗。
        """
        self.__dict__['_skip_gap'] = bool(value)
        if value:
            self._clear_gap_series()
        return self

    def prefer_single_gap(self, value: bool = True):
        """NaN 断点优先用「单序列 + 透明缺口」（**实时刷新的指标线**用 ✓）。

        逐段拆（段数 ≤ ``MAX_GAP_SEGMENTS``）在**每秒刷新**下会不断
        ``delete`` + ``addSeries`` + ``setData``（实测 supertrend 这类“一半 NaN”
        的线每拍 ~130~270 次 JS 调用），把渲染线程拖死 → 图表卡住 ✗。
        单序列路径视觉一样（见 :meth:`_draw_gap_single_series`），却只占 1 个序列 ✓。
        """
        self.__dict__['_prefer_single_gap'] = bool(value)
        return self

    def _sync_gap_segments(self, df) -> None:
        """让"NaN 处断开"落地的唯一入口（无 NaN 时只做一次廉价判断）。"""
        if self.__dict__.get('_skip_gap'):
            return                       # 隐藏载体线：不需要断点 ✗
        segments = self._split_gap_segments(df)
        if len(segments) < 2:
            segments = []
        elif (self.__dict__.get('_prefer_single_gap')
              or len(segments) > self.MAX_GAP_SEGMENTS):
            # 段数偏多（或指标线声明优先单序列）：优先改用「单序列 + 透明缺口」，
            # 省下成百上千个分段序列（每个 addSeries + setData 都是一次 JS 往返
            # + 一次重绘，实时每秒刷新时会把渲染线程拖死 ✗）。拿不到线色等才退回
            # 下面的旧规则。
            if self._draw_gap_single_series(df):
                return
            if len(segments) > self.MAX_GAP_SPLIT_SERIES:
                segments = []      # 实在太多：回单序列（可能连起来）
            else:
                # 平均段长很短 = 逐 bar 交替 NaN，为它拆段不值得
                try:
                    total = sum(len(s) for s in segments)
                    avg = total / max(1, len(segments))
                except Exception:
                    avg = 0.0
                if avg < self.MIN_GAP_SEGMENT_LEN:
                    segments = []
        existing = self.__dict__.get('_gap_series') or []
        if not segments:
            self._clear_gap_series()
            if existing:
                self._set_main_visible(True)
            return
        column = self._gap_value_column(df)
        self._clear_gap_series()
        self._set_main_visible(False)
        style = self._gap_series_style()
        made = []
        for segment in segments:
            piece = segment[[c for c in ('time', column) if c in segment]]
            if column != 'value':
                piece = piece.rename(columns={column: 'value'})
            try:
                extra = self._chart.add_series(
                    'Line', name='', legend=False, legend_toggle=False,
                    pane_index=self._pane_index, **style)
                # 分段序列是**内部实现**：从公共序列列表里摘掉，免得
                # `chart._lines` / pane 检查 / 图例把它们算进去
                if extra in self._chart._lines:
                    self._chart._lines.remove(extra)
                extra.__dict__['_gap_parent'] = self
                extra.set(piece, format_cols=False)
                made.append(extra)
            except Exception as error:
                print('[pylightcharts] 断点分段绘制失败:', error)
        self.__dict__['_gap_series'] = made
        if made:
            # 把分段序列挂到主序列上：图例的眼睛只对主序列 applyOptions，
            # 不带上它们的话，点了眼睛线还是一段一段留在图上。
            handles = ', '.join(f'{piece.id}.series' for piece in made)
            self.run_script(
                f'{self.id}.series.__gapSegments = [{handles}];')

    def _set_main_visible(self, visible: bool = True) -> None:
        """主序列显示/隐藏：只在状态**真的变化**时下发一次 JS ✓。"""
        visible = bool(visible)
        if self.__dict__.get('_gap_main_hidden', False) == (not visible):
            return                       # 已是目标状态，别再发一次
        self.__dict__['_gap_main_hidden'] = not visible
        self.run_script(
            f'{self.id}.series.applyOptions('
            f'{{lineVisible: {jbool(visible)}}}); ')

    def _single_gap_frame(self, df) -> Optional[pd.DataFrame]:
        """算出「单序列 + 透明缺口」要下发的帧（**无副作用**，可先算后发）。

        缺口点补成前值并染成透明（:attr:`GAP_COLOR`），有效点用线色。引擎给
        每一段线取**起点**颜色，所以缺口那一段不会被画出来 —— 视觉上与逐段拆
        一样，却只占 1 个序列（见 :meth:`_draw_gap_single_series`）。

        :return: 上色后的 DataFrame；用不了这条路径时返回 ``None``。
        """
        column = self._gap_value_column(df)
        if column is None:
            return None
        style = self._gap_series_style()
        # 没显式给色（``color=None``）时线实际就是引擎默认色 —— 用它上色即可；
        # 这里若 return None，调用方会回退成一段一个内部序列，77 个 NaN 段就能
        # 把 JS 渲染线程永久卡死（回测止损/止平价线实测 ✓→✗）。
        color = (style.get('color') or style.get('line_color')
                 or self.DEFAULT_LINE_COLOR)
        values = pd.to_numeric(df[column], errors='coerce').to_numpy(dtype=float)
        finite = np.isfinite(values)
        if finite.all():
            return None
        filled = pd.Series(values).ffill().bfill()
        if filled.isna().to_numpy().any():   # 整列没有可画的值
            return None
        frame = df.copy()
        frame[column] = filled.to_numpy()
        colors = np.full(len(frame), self.GAP_COLOR, dtype=object)
        colors[finite] = color
        frame['color'] = colors
        return frame

    def _draw_gap_single_series(self, df, frame=None) -> bool:
        """用**一个序列**画出 NaN 断点（`update()` 等重算路径的入口）。

        :return: 是否已用这条路径画好（False 时调用方回退成原行为）。
        """
        if frame is None:
            frame = self._single_gap_frame(df)
        if frame is None:
            return False
        self._clear_gap_series()
        self._set_main_visible(True)
        self.run_script(
            f'{self.id}.series.setData({encode_series_data(frame)})')
        return True

    def repaint_gaps(self) -> bool:
        """重发数据，让「单序列缺口」的逐点颜色跟着新的线色走 ✓。

        颜色是在 ``setData`` 时按点烤进数据的，之后 ``apply_options(color=…)``
        只改线色、盖不住逐点颜色 —— 改色后需要重发一次。无缺口/非单序列时
        返回 False（普通 `apply_options` 已经生效）。
        """
        df = self.data
        if df is None or getattr(df, 'empty', True):
            return False
        if self.__dict__.get('_gap_series'):
            self._sync_gap_segments(df)
            return True
        return self._draw_gap_single_series(df)

    def add_symbol(self, name: str, data=None, *, kind: str = 'candles',
                   scale: str = 'left',
                   margins: Optional[tuple] = None, **options):
        """Add a second symbol on its own price scale (pylightcharts extra).

        The official *Two Price Scales* tutorial puts the second series on the
        left axis; this keeps the main candles on the right one and overlays the
        new symbol on the left:

        .. code-block:: python

            chart.set(btc)                                     # right axis
            chart.add_symbol('ETHUSDT', eth, kind='candles')    # left axis
            chart.add_symbol('BTC/GLD', ratio, kind='line')

        `kind` is ``'candles'`` / ``'bars'`` / ``'line'`` / ``'area'`` /
        ``'baseline'`` / ``'histogram'``; `margins` ``(top, bottom)`` stacks the
        two symbols instead of overlapping them (see :meth:`scale_margins`).
        See :func:`pylightcharts.overlay.add_symbol` for every option.
        """
        from .overlay import add_symbol
        return add_symbol(self, name, data, kind=kind, scale=scale,
                          margins=margins, **options)

    def scale_margins(self, right: Optional[tuple] = None,
                      left: Optional[tuple] = None, **scales) -> None:
        """Share the pane out between price scales (pylightcharts extra).

        ``(top, bottom)`` is the empty space above / below the data, so
        ``scale_margins(right=(0.0, 0.55), left=(0.55, 0.0))`` puts the right
        scale's symbol in the top 45% and the left scale's one below it.
        """
        for scale_id, margins in dict(right=right, left=left, **scales).items():
            if margins is None:
                continue
            top, bottom = margins
            self.get_price_scale(scale_id).apply_options(
                scale_margins={'top': top, 'bottom': bottom})

    def theme(self, name='dark', **overrides) -> 'AbstractChart':
        """Apply a whole-UI colour theme (every chart of the window).

        Shortcut for :meth:`Window.theme`, so a single-chart app can write
        ``chart.theme('light')``.
        """
        self.win.theme(name, **overrides)
        return self

    def _apply_theme(self, spec: dict) -> None:
        """The chart-level half of a theme (the root CSS is window-level)."""
        self.apply_options(layout={
            'background': {'type': 'solid', 'color': spec['background']},
            'text_color': spec['text'],
        })
        self.apply_options(grid={
            'vert_lines': {'color': spec['grid']},
            'horz_lines': {'color': spec['grid']},
        })
        self.apply_options(crosshair={
            'vert_line': {'color': spec['crosshair'],
                          'label_background_color': spec['crosshair_label']},
            'horz_line': {'color': spec['crosshair'],
                          'label_background_color': spec['crosshair_label']},
        })
        try:
            self.candle_style(up_color=spec['up'], down_color=spec['down'],
                              wick_up_color=spec['up'],
                              wick_down_color=spec['down'],
                              border_up_color=spec['up'],
                              border_down_color=spec['down'])
        except Exception:                    # numeric charts have no candles
            pass
        try:
            self.volume_config(up_color=spec['volume_up'],
                               down_color=spec['volume_down'])
        except Exception:                    # ... and no volume series
            pass
        self.pane_separator(color=spec['pane_separator'],
                            hover_color=spec['separator_hover'])
        self.time_scale_options(border_color=spec['scale_border'])
        self.price_scale_options(text_color=spec['text'],
                                 border_color=spec['scale_border'])
        # `price_scale_options` 只碰主图右轴；成交量和每个副图指标各有一条
        # 独立的价格轴（默认灰字 + 近白竖线），得单独换色。
        self.run_script(f'''
        if ({self.id}.volumeSeries) {{
            {self.id}.volumeSeries.priceScale().applyOptions({{
                textColor: {json.dumps(spec['text'])},
                borderColor: {json.dumps(spec['scale_border'])},
            }});
        }}''')
        for index in range(1, max(1, self._pane_count)):
            for scale_id in ('right', 'left'):
                try:
                    self.pane_price_scale(index, scale_id).apply_options(
                        text_color=spec['text'],
                        border_color=spec['scale_border'])
                except Exception:
                    pass
        # the legend sets its colour as an inline style, so the CSS variables
        # do not reach it: re-apply the legend, keeping the user's options
        if self._legend_options:
            self.legend(**{**self._legend_options, 'color': spec['text']})

    def mark_swings(self, length: int = 5, *, swings: Optional[pd.DataFrame] = None,
                    label: bool = True,
                    decimals: int = 2, high_color: str = '#EF5350',
                    low_color: str = '#26A69A', size: int = 2,
                    clear: bool = False,
                    inverted: Optional[bool] = None) -> pd.DataFrame:
        """Mark the swing highs/lows with their price (pylightcharts helper).

        Lightweight Charts has no swing detection of its own - the markers it
        *draws* are the built-in part. This computes `length`-bar fractals
        (:func:`pylightcharts.indicators.swing_points`) and pushes one marker per
        pivot: an `arrow_down` above the high showing the high price, an
        `arrow_up` below the low showing the low price.

        Works on the chart (candles: high/low) and on a series (peaks/troughs of
        its own values). Markers share the series' marker primitive, so
        `series.markers_plugin().set_markers(...)` replaces them and
        `series.clear_markers()` removes them.

        The pivots are found here, from the data the chart already holds
        (`candle_data` for the chart, `series.data` for a series) - nothing has
        to be passed in and the chart's own epoch-second time column is used.
        Pass `swings` when you want to mark points computed elsewhere (a custom
        rule, or the result of :func:`pylightcharts.indicators.swing_points`).

        :param length: bars on each side of a pivot (a pivot needs `length` bars
            after it to be confirmed).
        :param swings: a ``time`` / ``price`` / ``kind`` frame to mark instead of
            detecting new pivots (``length`` is then unused).
        :param label: show the price as the marker text.
        :param decimals: decimals used in that label.
        :param size: marker size multiplier (see :meth:`marker`).
        :param clear: drop the series' existing markers first.
        :param inverted: place the markers for an inverted (价格倒挂) price scale;
            ``None`` (default) follows the chart, which tracks
            `price_scale(invert_scale=True)`, `PriceScale.invert()` and
            `apply_options(rightPriceScale={'invertScale': True})`.
        :return: the swing points (`time` / `price` / `kind`).
        """
        if swings is None:
            frame, high_column, low_column = self._swing_source()
            swings = swing_points(frame[high_column], frame[low_column],
                                  length=length, time=frame['time'])
        else:
            missing = {'time', 'price', 'kind'} - set(swings.columns)
            if missing:
                raise ValueError(
                    f'swings needs the columns {sorted({"time", "price", "kind"})}, '
                    f'missing {sorted(missing)}')
            swings = swings.sort_values('time').reset_index(drop=True)
        if clear:
            self.clear_markers()
        flipped = self._inverted(inverted)
        for row in swings.itertuples():
            is_high = row.kind == 'high'
            self.marker(
                row.time,
                # on an inverted scale the high sits *lower* on screen, so the
                # arrow and its side flip (the price itself stays correct)
                position=('below' if is_high else 'above') if flipped
                else ('above' if is_high else 'below'),
                shape=('arrow_up' if is_high else 'arrow_down') if flipped
                else ('arrow_down' if is_high else 'arrow_up'),
                color=high_color if is_high else low_color,
                text=f'{row.price:.{decimals}f}' if label else '',
                size=size,
            )
        return swings

    def add_zigzag(self, threshold: float = 0.03, *, name: Optional[str] = None,
                   color: str = '#2962FF', line_width: int = 2,
                   markers: bool = True, label: bool = False, size: int = 2,
                   include_unconfirmed: bool = True,
                   inverted: Optional[bool] = None,
                   legend_toggle: bool = True, **options) -> 'BridgeSeries':
        """Draw a ZigZag ("波段线") over the candles and keep it up to date.

        A `Line` series through the pivots of
        :func:`pylightcharts.indicators.zigzag` - alternating highs and lows
        after a retracement of more than `threshold` (a fraction: ``0.03`` = 3%).
        The series is recomputed automatically whenever the chart data changes
        (`chart.set()` / `chart.update()`), so it works on a live chart too.

        :param threshold: minimum retracement that confirms a reversal.
        :param name: legend name (default ``'ZigZag 3%'``).
        :param markers: also mark the pivots on the candles (arrows with the
            price when `label=True`).
        :param include_unconfirmed: draw the last, still open leg as well (it
            moves until the reversal is confirmed - the usual ZigZag behaviour).
        :param inverted: marker side/direction for an inverted price scale
            (``None`` = follow the chart, see :meth:`mark_swings`).
        :return: the zigzag `Line` series.
        """
        frame, high_column, low_column = self._swing_source()
        series = self.add_series(
            'Line', name=name or f'ZigZag {threshold * 100:g}%',
            pane_index=0, color=color, line_width=line_width,
            price_line=False, price_label=False, legend_toggle=legend_toggle,
            **options)
        binding = _ZigzagBinding(self, series, threshold, high_column,
                                 low_column, markers=markers, label=label,
                                 size=size,
                                 include_unconfirmed=include_unconfirmed,
                                 inverted=inverted)
        self._indicator_bindings.append(binding)
        binding.refresh(frame, full=True)
        return series

    def _swing_source(self):
        """The frame and the two columns :meth:`mark_swings` works on."""
        if self is self._chart:
            frame = getattr(self, 'candle_data', None)
            if frame is None or frame.empty:
                raise ValueError('Set the chart data before marking swings.')
            return frame, 'high', 'low'
        frame = self.data
        if frame is None or frame.empty:
            raise ValueError('Set the series data before marking swings.')
        # a single-valued series only has peaks and troughs
        return frame, 'value', 'value'

    def keyboard(self, enabled: Optional[bool] = None,
                 step: Optional[float] = None) -> 'AbstractChart':
        """Configure the built-in arrow-key navigation at runtime.

        :param enabled: ``False`` disables it for this chart (same as
            ``keyboard=False`` in the constructor).
        :param step: fraction of the visible window one press moves / zooms
            (default ``0.1`` = 10%).

        Zooming out (``ArrowDown``) keeps the right edge where it is once the
        newest bar is on screen - the extra width goes to the older bars - so the
        live edge does not drift. With the newest bar off screen the zoom stays
        anchored on the middle of the window.

        .. code-block:: python

            chart.keyboard(step=0.25)      # coarse pan/zoom
            chart.keyboard(enabled=False)  # let the host handle the arrows
        """
        if enabled is not None:
            self.run_script(f'{self.id}.keyboardNavigation = {jbool(enabled)}')
        if step is not None:
            self.run_script(f'{self.id}.keyboardStep = {step}')
        return self

    def color_by(self, condition, color, else_color=None,
                 **kwargs) -> pd.DataFrame:
        """Re-send this series' data with per-point colours applied.

        Works on every series - including indicators, whose data is computed for
        you (`add_sma(...).color_by(slope > 0, '#26a69a', else_color='#ef5350')`)
        - and on the chart itself, where it colours the main candles:

            chart.color_by(chart.candle_data['close'] > 205, 'orange')

        `condition` is a boolean Series / array (a Series is aligned on `time`
        when it holds fewer rows than the series) or a callable that receives the
        frame. `color`, `else_color`, `wick_color` and `border_color` are the
        same as in :func:`pylightcharts.colors.color_by`.

        A later full refresh (``chart.set()``, indicator recompute) sends the
        computed data again and drops the colours - call this again afterwards.
        :return: the coloured frame that was sent.
        """
        frame = self._color_frame()
        if frame is None or frame.empty:
            raise ValueError(
                'Set the data before colouring it (chart.set / series.set).')
        coloured = color_by(frame, condition, color, else_color, **kwargs)
        self.run_script(
            f'{self.id}.series.setData({encode_series_data(coloured)})')
        if self is self._chart:
            self.candle_data = coloured.copy()
        else:
            self.data = coloured.copy()
            self._last_bar = coloured.iloc[-1]
        return coloured

    def _color_frame(self) -> Optional[pd.DataFrame]:
        """The frame this object currently holds (candles for the chart)."""
        if self is self._chart:
            return getattr(self, 'candle_data', None)
        return self.data

    def update(self, series: pd.Series, historical_update: bool = False):
        """Push one bar/point.

        ★ ``historical_update``（或**自动识别**）对应 LWC v5 的第二个参数：
        ``series.update(bar, historicalUpdate)``。不带它时 ``update`` **只能**
        改写“最后一根”或追加“更新的一根”，**更旧的一根会报
        ``Cannot update oldest data`` 被静默丢掉** ✗ —— 实时图“新 K 线来了要顺带
        回填上一根的收盘价/指标”正是这种用法 ✓。这里：

        * 时间**更晚** → 先把正在形成的那根落盘，再追加（老行为 ✓）；
        * 时间**相同** → 就地更新最后一根 ✓；
        * 时间**更早**（历史回填）→ **只覆盖** mirror 里对应时间的那一行（不能当
          新根追加 ✗，否则 mirror 乱序/重复，之后按时间取值全错 ✗），
          并自动带上 ``historicalUpdate=True`` ✓。
        """
        series = self._series_datetime_format(
            series, exclude_lowercase=self.name)
        if self.name in series.index:
            series.rename({self.name: 'value'}, inplace=True)
        last = self._last_bar
        newer = True
        if last is None:
            self._last_bar = series
        else:
            when = pd.Timestamp(series['time'])
            last_time = pd.Timestamp(last['time'])
            if when > last_time:
                self.data.loc[self.data.index[-1]] = last
                self.data = pd.concat(
                    [self.data, series.to_frame().T], ignore_index=True)
                self._normalize_time_column()
                self._last_bar = series
            elif when == last_time:
                self._last_bar = series          # 同一根：就地更新 ✓
            else:
                newer = False                     # 历史回填（更早的一根）✓
                self._overwrite_row(series)
        if historical_update or not newer:
            self.run_script(
                f'{self.id}.series.update({js_data(series)}, {jbool(True)})')
        else:
            self.run_script(f'{self.id}.series.update({js_data(series)})')
        if (self.__dict__.get('_gap_series')
                or not self._is_finite_value(series.get('value'))):
            # 断层出现/消失/延长时才重算；没有 nan 的序列这条分支永不进入
            self._sync_gap_segments(self.data)

    def _normalize_time_column(self) -> None:
        """把 mirror 的 ``time`` 列拉回 **int64 秒** ✓。

        ``update()`` 里写进的 time 是 float（``1760712900.0``）—— 往 int64 列里
        写 float 会让整列退化成 ``object`` ✗，而消费方（minibt 按时间 reindex
        指标/信号）就会把“秒”当纳秒解释 → 全部落空 ✗。这里及时归一化 ✓。
        """
        try:
            if 'time' not in self.data.columns:
                return
            if pd.api.types.is_numeric_dtype(self.data['time']):
                return
            numeric = pd.to_numeric(self.data['time'], errors='coerce')
            if len(numeric) and bool(numeric.notna().all()):
                self.data['time'] = np.asarray(numeric, dtype='int64')
        except Exception:                                        # noqa: BLE001
            pass

    def _overwrite_row(self, series: pd.Series) -> None:
        """把 mirror（``self.data``）里**对应时间**的那一行改成 ``series``。

        历史回填专用：不追加、不改 ``_last_bar`` ✓（保持“最后一根”不变 ✓）。
        """
        try:
            mask = pd.to_datetime(self.data['time']) == pd.Timestamp(
                series['time'])
            if not mask.any():
                return
            for col in series.index:
                if col in self.data.columns:
                    self.data.loc[mask, col] = series[col]
        except Exception:                                        # noqa: BLE001
            pass

    def _invoke_series(self, method: str, *args):
        """Call a method on the underlying `ISeriesApi` (i.e. `series.<method>`)."""
        self.win.invoke(f'{self.id}.series', method, *args)

    def _invoke_series_get(self, method: str, *args):
        """Like :meth:`_invoke_series` but returns the (JSON-serializable) result."""
        return self.win.invoke_get(f'{self.id}.series', method, *args)

    def apply_options(self, **options):
        """Apply arbitrary series options (snake_case keys are camelCased automatically).

        This is the escape hatch that gives python full access to the series API
        without needing a dedicated method for every option.
        """
        if hasattr(self, '_remember_options'):
            self._remember_options(options)
        self._invoke_series(
            'applyOptions', _normalize_base_value(getattr(self, 'kind', None), options))

    def _ensure_price_scale(self) -> str:
        """Register this series' price scale in the webview and return its handle."""
        handle = f'{self.id}.priceScaleHandle'
        self.win.invoke(f'{self.id}.series', 'priceScale', store_as=handle)
        return handle

    def price_scale_options(self, **options):
        """Apply arbitrary price-scale options for this series."""
        _remember_inversion(self, options)
        self.win.invoke(self._ensure_price_scale(), 'applyOptions', options)

    def set_price_scale_mode(self, mode: PRICE_SCALE_MODE = 'normal'):
        """Set the price scale mode: normal / logarithmic / percentage / index100."""
        self.price_scale_options(mode=as_enum(mode, PRICE_SCALE_MODE))

    def set_scale_margins(self, top: float = 0.2, bottom: float = 0.2):
        """Set the top/bottom margins of this series' price scale (0..1)."""
        self.price_scale_options(scale_margins={'top': top, 'bottom': bottom})

    # ---- primitives / plugins (v5) ----

    def attach_primitive(self, primitive: str):
        """Attach a JS primitive registered under `primitive` to this series."""
        self._invoke_series('attachPrimitive', ref(primitive))

    def detach_primitive(self, primitive: str):
        """Detach a previously attached primitive from this series."""
        self._invoke_series('detachPrimitive', ref(primitive))

    def create_up_down_markers(self, positive_color: str = '#26a69a', negative_color: str = '#ef5350',
                               update_visibility_duration: int = 0, handle: Optional[str] = None) -> str:
        """Attach the v5 up/down markers plugin and return its JS handle.

        The engine only supports **Line** and **Area** series here; calling it on
        a candlestick/bar/histogram (or on the chart itself, which is the
        candlestick series) raises instead of failing inside the page.
        """
        # no round trip: `series_type()` would need a live webview, and the
        # kind is already known here (class name or the `kind` attribute)
        kind = getattr(self, 'kind', type(self).__name__)
        if self is self._chart:
            # `chart.up_down_markers_plugin()` -> the chart's candlestick series
            kind = 'the chart itself (a candlestick series)'
        if kind not in ('Line', 'Area'):
            raise ValueError(
                f'up/down markers need a Line or Area series, not {kind!r}. '
                'Create one with chart.create_line(...) / create_area(...) '
                'and call up_down_markers_plugin() on that series.')
        handle = handle or f'{self.id}.upDownMarkers'
        self.win.invoke(self._chart.id, 'createUpDownMarkers', ref(f'{self.id}.series'), {
            'positiveColor': positive_color,
            'negativeColor': negative_color,
            'updateVisibilityDuration': update_visibility_duration,
        }, store_as=handle)
        return handle

    def infinite_history(self, loader=None, page: int = 200,
                         threshold: int = 50, **kwargs) -> 'InfiniteHistory':
        """Load older bars when the chart is scrolled to its left edge.

        The official *infinite history* demo subscribes to the visible logical
        range and prepends another chunk of bars; here the chunk comes from
        Python - `loader(count)` (or `loader(count, before)`) returns older bars
        and they are put in front of what is loaded:

        .. code-block:: python

            def load(count, before=None):
                return read_bars(end=before, limit=count)

            history = chart.infinite_history(load, page=300, threshold=80)

        The main series goes through ``chart.set(..., keep_drawings=True)``, so
        the volume series, every computed indicator and the toolbox drawings stay
        in sync. `threshold` is how close to the left edge (in bars) the viewport
        must get, `page` how many bars a request asks for. See
        :class:`pylightcharts.history.InfiniteHistory` for the rest
        (``loaded`` / ``earliest`` / ``exhausted`` / ``load()`` / ``stop()``,
        ``spinner=True``, ``on_load=``, ``on_exhausted=``).

        .. _infinite history: https://tradingview.github.io/lightweight-charts/tutorials/demos/infinite-history
        """
        from .history import InfiniteHistory
        if loader is None:
            raise ValueError('infinite_history needs a loader(count) callable')
        return InfiniteHistory(self, loader, page=page, threshold=threshold,
                               **kwargs)

    def tooltip(self, mode: TOOLTIP_MODE = 'tracking',
                **options) -> 'Tooltip':
        """A crosshair tooltip that reads *this* series' data.

        ``mode='tracking'`` puts an opaque box next to the cursor (it flips to
        the other side near the right / bottom edge), ``mode='magnifier'`` pins a
        translucent band to the top of the pane and only slides it along the
        time axis - the two from the official `tooltips tutorial`_.

        Every option of :class:`~pylightcharts.tooltips.Tooltip` can be passed
        along, the useful ones being ``title=``, ``fields=`` (``'auto'`` shows
        open / high / low / close), ``width=`` / ``height=``, ``margin=``,
        ``decimals=``, ``time_format=``, ``color_by_candle=`` and the colour
        options (``background=`` / ``text_color=`` default to the theme's CSS
        variables, so light / dark just work; ``title_color=`` / ``border_color=``
        default to this series' colour).

        .. _tooltips tutorial: https://tradingview.github.io/lightweight-charts/tutorials/how_to/tooltips

        :return: a :class:`~pylightcharts.tooltips.Tooltip` handle.
        """
        from .tooltips import create_tooltip
        return create_tooltip(self, mode, **options)

    def tracking_tooltip(self, **options) -> 'Tooltip':
        """A tooltip that follows the cursor (see :meth:`tooltip`)."""
        return self.tooltip('tracking', **options)

    def magnifier_tooltip(self, **options) -> 'Tooltip':
        """A tooltip pinned to the top of the pane (see :meth:`tooltip`)."""
        return self.tooltip('magnifier', **options)

    def markers_plugin(self, handle: Optional[str] = None) -> 'SeriesMarkersPlugin':
        """A :class:`SeriesMarkersPlugin` for this series' markers (v5 primitive).

        Markers are still managed through :meth:`marker` / :meth:`marker_list`;
        this exposes the underlying plugin so its state can be read, options
        applied, or the primitive detached.
        """
        handle = handle or f'{self.id}.markersPlugin'
        self.run_script(
            f'Lib.Handler.setMarkers({self.id}.series, '
            f'{json.dumps(list(self.markers.values()))}, {json.dumps(handle)})')
        self._markers_plugin_handle = handle
        return SeriesMarkersPlugin(self.win, handle)

    def up_down_markers_plugin(self, **kwargs) -> 'UpDownMarkersPlugin':
        """A :class:`UpDownMarkersPlugin` around :meth:`create_up_down_markers`."""
        handle = self.create_up_down_markers(**kwargs)
        return UpDownMarkersPlugin(self.win, handle)

    # ------------------------------------------------------------------
    # Data readback / coordinate conversion
    # ------------------------------------------------------------------

    def price_to_coordinate(self, price: float) -> Optional[float]:
        """Convert a price into a y coordinate (``None`` when not visible)."""
        return self._invoke_series_get('priceToCoordinate', price)

    def coordinate_to_price(self, coordinate: float) -> Optional[float]:
        """Convert a y coordinate into a price."""
        return self._invoke_series_get('coordinateToPrice', coordinate)

    def data_by_index(self, index: int, mismatch_direction: int = 0) -> Optional[dict]:
        """The data item at `index` (mismatch_direction: 0 none, -1 back, 1 forward)."""
        return self._invoke_series_get('dataByIndex', index, mismatch_direction)

    def data_points(self) -> list:
        """All data points currently held by the series (JS side).

        Note: the ``series.data`` *attribute* is the local pandas DataFrame;
        this method reads back what the chart itself holds.
        """
        return self._invoke_series_get('data')

    def pop(self, count: int = 1) -> list:
        """Remove and return the last `count` data points."""
        return self._invoke_series_get('pop', count)

    def last_value_data(self) -> Optional[dict]:
        """Information about the last visible value of the series."""
        return self._invoke_series_get('lastValueData')

    def bars_in_logical_range(self, from_logical: float, to_logical: float) -> Optional[dict]:
        """Bars before/after a logical range (``None`` when fully outside)."""
        return self._invoke_series_get('barsInLogicalRange', {'from': from_logical, 'to': to_logical})

    def series_type(self) -> str:
        """The series type, e.g. ``'Candlestick'``."""
        return self._invoke_series_get('seriesType')

    def options(self) -> dict:
        """The series' current options as a dict."""
        return self._invoke_series_get('options')

    def get_pane_index(self) -> int:
        """Index of the pane this series lives in."""
        handle = f'{self.id}.paneHandle'
        self.win.invoke(f'{self.id}.series', 'getPane', store_as=handle)
        return self.win.invoke_get(handle, 'paneIndex')

    def get_pane(self) -> 'Pane':
        """A :class:`Pane` handle for the pane this series lives in."""
        handle = f'{self.id}.paneHandle'
        self.win.invoke(f'{self.id}.series', 'getPane', store_as=handle)
        pane = Pane(self.win)
        pane.id = handle
        return pane

    def price_formatter(self) -> str:
        """Handle of this series' ``IPriceFormatter`` object."""
        handle = f'{self.id}.priceFormatter'
        self.win.invoke(f'{self.id}.series', 'priceFormatter', store_as=handle)
        return handle

    def set_price_format_formatter(self, callback: str):
        """Use a registered JS callback as this series' ``priceFormat.formatter``."""
        self.run_script(
            f'Lib.setPriceFormatFormatter({json.dumps(f"{self.id}.series")}, '
            f'{json.dumps(callback)})')

    def set_autoscale_info_provider(self, callback: str):
        """Use a registered JS callback as this series' ``autoscaleInfoProvider``."""
        handle = json.dumps(f'{self.id}.series')
        self.run_script(
            f'Lib.setOptionCallback({handle}, "applyOptions", '
            f'"autoscaleInfoProvider", {json.dumps(callback)})')

    def move_to_pane(self, pane_index: int):
        """Move this series into another pane (creating it if needed)."""
        self._chart._ensure_pane(pane_index)
        self._invoke_series('moveToPane', pane_index)
        self._pane_index = pane_index

    def series_order(self) -> Optional[int]:
        """Drawing order of this series within its pane."""
        return self._invoke_series_get('seriesOrder')

    def set_series_order(self, order: int):
        """Set the drawing order of this series within its pane."""
        self._invoke_series('setSeriesOrder', order)

    # ------------------------------------------------------------------
    # Price lines
    # ------------------------------------------------------------------

    def create_price_line(self, price: float, color: str = '#2962FF', line_width: int = 1,
                          line_style: LINE_STYLE = 'solid', axis_label_visible: bool = True,
                          line_visible: bool = True, title: str = '',
                          axis_label_color: Optional[str] = None,
                          axis_label_text_color: Optional[str] = None) -> 'PriceLine':
        """Draw a horizontal price line on this series."""
        handle = f'{self.id}.priceLine.{len(self._price_lines)}'
        self.win.invoke(f'{self.id}.series', 'createPriceLine', {
            'price': price,
            'color': color,
            'lineWidth': line_width,
            'lineStyle': as_enum(line_style, LINE_STYLE),
            'axisLabelVisible': axis_label_visible,
            'lineVisible': line_visible,
            'title': title,
            'axisLabelColor': axis_label_color,
            'axisLabelTextColor': axis_label_text_color,
        }, store_as=handle)
        line = PriceLine(self, handle)
        self._price_lines.append(line)
        return line

    def price_lines(self) -> List['PriceLine']:
        """The price lines created through :meth:`create_price_line`."""
        return list(self._price_lines)

    def js_price_lines(self) -> str:
        """Handle of the JS array returned by ``ISeriesApi.priceLines()``.

        The python list of created lines is available via :meth:`price_lines`;
        this exposes the *live* JS collection (use ``chart.win.eval_js(f'{h}.length')``
        for the count, or pass the handle to other primitives/plugins).
        """
        handle = f'{self.id}.priceLinesArray'
        self.win.invoke(f'{self.id}.series', 'priceLines', store_as=handle)
        return handle

    def subscribe_data_changed(self, func: Callable):
        """Call ``func(series, scope)`` when this series' data changes.

        ``scope`` is the upstream ``DataChangedScope`` (``'full'`` / ``'update'``).
        """
        salt = uuid.uuid4().hex[:8]
        name = f'data_changed{salt}'
        self._data_changed_name = name
        self._data_changed_salt = salt
        self.win.handlers[name] = lambda scope=None, **_: func(self, scope)
        self.run_script(f'''
        window.dataChangedHandler{salt} = (scope) => window.callbackFunction(`{name}_~_${{scope}}`)
        {self.id}.series.subscribeDataChanged(window.dataChangedHandler{salt})
        ''')

    def unsubscribe_data_changed(self):
        """Remove the subscription installed by :meth:`subscribe_data_changed`."""
        salt = getattr(self, '_data_changed_salt', None)
        name = getattr(self, '_data_changed_name', None)
        if name is None:
            return
        self.run_script(
            f'{self.id}.series.unsubscribeDataChanged(window.dataChangedHandler{self._data_changed_salt})')
        self.win.handlers.pop(name, None)
        self._data_changed_name = None

    def update_raw(self, point: dict):
        """Update a single point that is already in chart format (time in seconds)."""
        self.run_script(f'{self.id}.series.update({js_value(point)})')

    def _update_markers(self):
        # lightweight-charts v5: markers are managed by the createSeriesMarkers primitive.
        # ★ 必须包成无返回 IIFE：``Handler.setMarkers`` **返回 marker 原语对象**（循环
        # 引用的代理），QtWebEngine 对裸语句的完成值做收集时会在渲染线程里**永久挂起**
        # —— 表现就是「setMarkers 一调，图卡死、其它页面正常」（实测 PyQt6 ✓）。
        # IIFE 不 return，完成值为 undefined，原语照常创建 ✓。
        # v5 markers 契约：数组必须按 time 升序（乱序会导致 marker 随机消失，
        # 同 time 多个 marker 允许 —— 稳定排序保留原有上下堆叠顺序 ✓）。
        ordered = sorted(self.markers.values(),
                         key=lambda entry: entry.get('time', 0))
        self.run_script(
            f'(function(){{Lib.Handler.setMarkers({self.id}.series, '
            f'{json.dumps(ordered)});}})()'
        )

    def marker_list(self, markers: list):
        """
        Creates multiple markers.\n
        :param markers: The list of markers to set. These should be in the format:\n
        [
            {"time": "2021-01-21", "position": "below", "shape": "circle", "color": "#2196F3", "text": ""},
            {"time": "2021-01-22", "position": "below", "shape": "circle", "color": "#2196F3", "text": ""},
            ...
        ]
        :return: a list of marker ids.
        """
        markers = markers.copy()
        marker_ids = []
        for marker in markers:
            marker_id = self.win._id_gen.generate()
            entry = {
                "time": self._single_datetime_format(marker['time']),
                "position": marker_position(marker['position']),
                "color": marker['color'],
                "shape": marker_shape(marker['shape']),
                "text": marker['text'],
            }
            if marker.get('size') is not None:
                entry['size'] = marker['size']
            self.markers[marker_id] = entry
            marker_ids.append(marker_id)
        self._update_markers()
        return marker_ids

    def marker(self, time: Optional[datetime] = None, position: MARKER_POSITION = 'below',
               shape: MARKER_SHAPE = 'arrow_up', color: str = '#2196F3', text: str = '',
               size: Optional[int] = None
               ) -> str:
        """
        Creates a new marker.\n
        :param time: Time location of the marker. If no time is given, it will be placed at the last bar.
        :param position: The position of the marker.
        :param color: The color of the marker (rgb, rgba or hex).
        :param shape: The shape of the marker.
        :param text: The text to be placed with the marker.
        :param size: Scale of the marker (``None`` keeps the engine default, ``1``).
        :return: The id of the marker placed.
        """
        try:
            formatted_time = self._last_bar['time'] if not time else self._single_datetime_format(
                time)
        except TypeError:
            raise TypeError('Chart marker created before data was set.')
        marker_id = self.win._id_gen.generate()

        self.markers[marker_id] = {
            "time": formatted_time,
            "position": marker_position(position),
            "color": color,
            "shape": marker_shape(shape),
            "text": text,
        }
        if size is not None:
            self.markers[marker_id]["size"] = size
        self._update_markers()
        return marker_id

    def remove_marker(self, marker_id: str):
        """
        Removes the marker with the given id.\n
        """
        self.markers.pop(marker_id)
        self._update_markers()

    def remove_markers(self, marker_ids) -> None:
        """Remove **many** markers at once (one re-render instead of N) ✓."""
        changed = False
        for marker_id in marker_ids or ():
            if self.markers.pop(marker_id, None) is not None:
                changed = True
        if changed:
            self._update_markers()

    def horizontal_line(self, price: NUM, color: str = 'rgb(122, 146, 202)', width: int = 2,
                        style: LINE_STYLE = 'solid', text: str = '', axis_label_visible: bool = True,
                        func: Optional[Callable] = None,
                        label_visible: bool = False,
                        label_background_color: Optional[str] = None,
                        label_text_color: Optional[str] = None,
                        label_font: Optional[str] = None,
                        ) -> 'HorizontalLine':
        """
        Creates a horizontal line at the given price.

        ``text`` is shown on the price axis by default. Pass ``label_visible=True``
        to also (or instead, with ``axis_label_visible=False``) draw it **inside**
        the pane, pinned to the left edge of the visible range.
        """
        return HorizontalLine(self, price, color, width, style, text,
                              axis_label_visible, func, label_visible,
                              label_background_color, label_text_color,
                              label_font)

    def trend_line(
        self,
        start_time: TIME,
        start_value: NUM,
        end_time: TIME,
        end_value: NUM,
        round: bool = False,
        line_color: str = '#1E80F0',
        width: int = 2,
        style: LINE_STYLE = 'solid',
    ) -> TwoPointDrawing:
        return TrendLine(*locals().values())

    def box(
        self,
        start_time: TIME,
        start_value: NUM,
        end_time: TIME,
        end_value: NUM,
        round: bool = False,
        color: str = '#1E80F0',
        fill_color: str = 'rgba(255, 255, 255, 0.2)',
        width: int = 2,
        style: LINE_STYLE = 'solid',
    ) -> TwoPointDrawing:
        return Box(*locals().values())

    def fibonacci(self, start_time: TIME, start_value: NUM, end_time: TIME, end_value: NUM,
                  line_color: str = '#787B86', width: int = 1, style: LINE_STYLE = 'solid',
                  levels: Optional[tuple] = None, show_labels: bool = True,
                  fill_background: bool = True,
                  background_color: str = 'rgba(41, 98, 255, 0.08)',
                  text_color: str = '#9598A1') -> Fibonacci:
        """Fibonacci retracement between two points (0 = end, 1 = start)."""
        if levels is None:
            levels = (0, 0.236, 0.382, 0.5, 0.618, 0.786, 1)
        return Fibonacci(self, start_time, start_value, end_time, end_value,
                         line_color, width, style, levels, show_labels,
                         fill_background, background_color, text_color)

    def measure(self, start_time: TIME, start_value: NUM, end_time: TIME, end_value: NUM,
                line_color: str = '#2962FF', width: int = 1, style: LINE_STYLE = 'solid',
                fill_color: str = 'rgba(41, 98, 255, 0.18)', text_color: str = '#FFFFFF',
                background_color: str = 'rgba(41, 98, 255, 0.85)',
                show_time_range: bool = True) -> Measure:
        """Measurement tool showing price change, percentage and bar count."""
        return Measure(self, start_time, start_value, end_time, end_value,
                       line_color, width, style, fill_color, text_color,
                       background_color, show_time_range)

    def parallel_channel(self, start_time: TIME, start_value: NUM, end_time: TIME, end_value: NUM,
                         offset: float = 0.0, line_color: str = '#2962FF', width: int = 2,
                         style: LINE_STYLE = 'solid',
                         fill_color: str = 'rgba(41, 98, 255, 0.12)',
                         fill_enabled: bool = True) -> ParallelChannel:
        """A trend line plus a parallel line ``offset`` price units away."""
        return ParallelChannel(self, start_time, start_value, end_time, end_value,
                               offset, line_color, width, style, fill_color, fill_enabled)

    def position(self, entry_time: TIME, entry_price: NUM, target_time: TIME, target_price: NUM,
                 risk_ratio: float = 1.0, line_color: str = '#787B86', width: int = 1,
                 style: LINE_STYLE = 'solid',
                 profit_fill_color: str = 'rgba(38, 166, 154, 0.25)',
                 loss_fill_color: str = 'rgba(239, 83, 80, 0.25)',
                 profit_line_color: str = '#26A69A', loss_line_color: str = '#EF5350',
                 text_color: str = '#FFFFFF', show_labels: bool = True) -> Position:
        """Risk/reward tool: profit and stop-loss zones from an entry point.

        Long when ``target_price > entry_price``, short otherwise.
        """
        return Position(self, entry_time, entry_price, target_time, target_price,
                        risk_ratio, line_color, width, style, profit_fill_color,
                        loss_fill_color, profit_line_color, loss_line_color,
                        text_color, show_labels)

    def long_position(self, entry_time: TIME, entry_price: NUM, target_time: TIME,
                      target_price: NUM, **kwargs) -> Position:
        """Alias of :meth:`position` for a long (target above entry)."""
        return self.position(entry_time, entry_price, target_time, target_price, **kwargs)

    def short_position(self, entry_time: TIME, entry_price: NUM, target_time: TIME,
                       target_price: NUM, **kwargs) -> Position:
        """Alias of :meth:`position` for a short (target below entry)."""
        return self.position(entry_time, entry_price, target_time, target_price, **kwargs)

    def andrews_pitchfork(self, p1_time: TIME, p1_price: NUM, p2_time: TIME, p2_price: NUM,
                          p3_time: TIME, p3_price: NUM, line_color: str = '#2962FF',
                          width: int = 1, style: LINE_STYLE = 'solid',
                          fill_color: str = 'rgba(41, 98, 255, 0.08)',
                          fill_enabled: bool = True, extension: float = 4) -> AndrewsPitchfork:
        """Andrew's pitchfork through three points."""
        return AndrewsPitchfork(self, p1_time, p1_price, p2_time, p2_price, p3_time, p3_price,
                                line_color, width, style, fill_color, fill_enabled, extension)

    def triangle(self, p1_time: TIME, p1_price: NUM, p2_time: TIME, p2_price: NUM,
                 p3_time: TIME, p3_price: NUM, line_color: str = '#2962FF', width: int = 1,
                 style: LINE_STYLE = 'solid',
                 fill_color: str = 'rgba(41, 98, 255, 0.15)',
                 fill_enabled: bool = True) -> Triangle:
        """A triangle through three points."""
        return Triangle(self, p1_time, p1_price, p2_time, p2_price, p3_time, p3_price,
                        line_color, width, style, fill_color, fill_enabled)

    def fibonacci_extension(self, p1_time: TIME, p1_price: NUM, p2_time: TIME, p2_price: NUM,
                            p3_time: TIME, p3_price: NUM, line_color: str = '#787B86',
                            width: int = 1, style: LINE_STYLE = 'solid',
                            levels: Optional[tuple] = None, show_labels: bool = True,
                            text_color: str = '#9598A1',
                            extension: float = 0.5) -> FibonacciExtension:
        """Fibonacci extension: the p1 -> p2 impulse projected from the p3 retracement."""
        if levels is None:
            levels = (0, 0.382, 0.618, 1, 1.272, 1.618, 2, 2.618)
        return FibonacciExtension(self, p1_time, p1_price, p2_time, p2_price,
                                  p3_time, p3_price, line_color, width, style, levels,
                                  show_labels, text_color, extension)

    def gann_fan(self, origin_time: TIME, origin_price: NUM, end_time: TIME, end_price: NUM,
                 line_color: str = '#2962FF', width: int = 1, style: LINE_STYLE = 'solid',
                 ratios: Optional[tuple] = None, extension: float = 3.0,
                 highlight_color: str = '#FF9800', show_labels: bool = False,
                 text_color: str = '#9598A1') -> GannFan:
        """Gann fan: p1 -> p2 is the 1x1 line, plus steeper and shallower rays."""
        return GannFan(self, origin_time, origin_price, end_time, end_price,
                       line_color, width, style, ratios, extension,
                       highlight_color, show_labels, text_color)

    def ray_line(
        self,
        start_time: TIME,
        value: NUM,
        round: bool = False,
        color: str = '#1E80F0',
        width: int = 2,
        style: LINE_STYLE = 'solid',
        text: str = ''
    ) -> RayLine:
        # TODO
        return RayLine(*locals().values())

    def vertical_line(
        self,
        time: TIME,
        color: str = '#1E80F0',
        width: int = 2,
        style: LINE_STYLE = 'solid',
        text: str = ''
    ) -> VerticalLine:
        return VerticalLine(*locals().values())

    def clear_markers(self):
        """
        Clears the markers displayed on the data.\n
        """
        self.markers.clear()
        self._update_markers()

    def price_line(self, label_visible: bool = True, line_visible: bool = True, title: str = ''):
        self._invoke_series('applyOptions', {
            'lastValueVisible': label_visible, 'priceLineVisible': line_visible, 'title': title,
        })

    def precision(self, precision: int):
        """
        Sets the precision and minMove.\n
        :param precision: The number of decimal places.
        """
        min_move = 1 / (10**precision)
        self._invoke_series('applyOptions', {'priceFormat': {
                            'precision': precision, 'minMove': min_move}})
        self.num_decimals = precision

    def hide_data(self):
        self._toggle_data(False)

    def show_data(self):
        self._toggle_data(True)

    def is_visible(self) -> bool:
        """Whether the series is shown (last value set from python)."""
        return bool(getattr(self, '_visible', True))

    def set_line_width(self, width: int):
        """Change the line width (indicator settings card)."""
        self.apply_options(line_width=int(width))

    def set_line_color(self, color: str):
        """Change the line colour (indicator settings card)."""
        self.apply_options(color=color)

    def set_line_style(self, style: str):
        """Change the line style (``solid`` / ``dashed`` / …)."""
        self.apply_options(line_style=as_enum(style, LINE_STYLE))

    def set_price_visible(self, name: str, value: bool):
        """Toggle the price line / price label (``price_line`` / ``price_label``).

        The old indicator card speaks in terms of the two pylightcharts/LWC
        options, so it can drive them through one method.
        """
        if name == 'price_line':
            self.apply_options(price_line_visible=bool(value))
        elif name == 'price_label':
            self.apply_options(last_value_visible=bool(value))

    def enable_legend_settings(self, func):
        """Show a settings (gear) button on this series' legend row.

        Clicking it calls ``func(series, x, y)`` on the python side (``x``/``y``
        are the click coordinates inside the webview, so the caller can pop its
        card next to the legend). Replaces the old "watch every mouse move over
        the legend" approach with a single click round trip.
        """
        callback = f'legend_settings{self._chart.id}'
        # All series of one chart share this callback name, so the handler must
        # dispatch by the series id the JS sends (a closure over `self` would be
        # overwritten by the next series and open the wrong card ✗).
        registry = self._chart.__dict__.setdefault(
            '_legend_settings_series', {})
        registry[self.id] = self

        def _dispatch(series_id, x=None, y=None):
            series = registry.get(series_id)
            if series is not None:
                func(series, x, y)

        self.win.handlers[callback] = _dispatch
        self.run_script(f'''
            (function() {{
                var legend = {self._chart.id}.legend;
                var s = {self.id};
                if (!legend || !s) return;
                var series = s.series;
                if (series && legend.addSettingsToggle) {{
                    legend.addSettingsToggle(series, {json.dumps(self.id)},
                                             {json.dumps(callback)});
                }}
            }})()
        ''')
        return self

    def enable_legend_menu(self, config: dict, func):
        """Show a settings (gear) button that opens a **JavaScript** menu.

        Counterpart of :meth:`enable_legend_settings` (whose gear opens a PyQt
        card): this builds a two-level menu inside the page - ``参数`` / ``线型``
        / ``线宽`` / ``线颜色`` / ``其它设置`` - so hosts without Qt (minibt /
        btplot) get the same settings surface. Every change calls
        ``func(series, kind, payload)`` on the python side so the host can keep
        its own model in sync (and recompute on ``kind == 'params'``).

        ``config`` is a plain dict, e.g.::

            {
                'title': 'MACD指标参数',
                'params': [{'name': 'fast', 'value': 12, 'type': 'int'}],
                'lineStyle': 'solid', 'lineWidth': 2,
                'lineColor': '#2196f3',
                'priceLine': True, 'priceLabel': True,
            }
        """
        callback = f'indicator_menu{self._chart.id}'
        registry = self._chart.__dict__.setdefault(
            '_legend_menu_series', {})
        registry[self.id] = self

        def _dispatch(series_id, kind, payload=None):
            series = registry.get(series_id)
            if series is None:
                return
            try:
                data = json.loads(payload) if payload else {}
            except Exception:                                    # noqa: BLE001
                data = {}
            func(series, kind, data)

        self.win.handlers[callback] = _dispatch
        self.run_script(f'''
            (function() {{
                var legend = {self._chart.id}.legend;
                var s = {self.id};
                if (!legend || !s) return;
                var series = s.series;
                if (series && legend.addSettingsMenu) {{
                    legend.addSettingsMenu(series, {json.dumps(self.id)},
                                           {json.dumps(config)},
                                           {json.dumps(callback)});
                }}
            }})()
        ''')
        return self

    def pin_legend_row(self, pinned: bool = True):
        """Keep this series' legend row visible without a crosshair."""
        self.run_script(f'''
            (function() {{
                var legend = {self._chart.id}.legend;
                var s = {self.id};
                if (!legend || !s) return;
                var series = s.series;
                if (series && legend.pinSeriesRow) {{
                    legend.pinSeriesRow(series, {jbool(pinned)});
                }}
            }})()
        ''')
        return self

    def remove_legend_row(self):
        """Remove this series' legend row from the chart (idempotent).

        The JS side creates a legend row for **every** series it is handed
        (``handler.ts::createLineSeries`` → ``legend.makeSeriesRow(...)`` runs
        unconditionally), so "an empty name skips the row" does **not** hold.
        Removing the row afterwards is the reliable way to honour
        ``legend=False`` while still passing the real name down (the name is what
        the data columns are mapped by — an empty one used to freeze rendering).

        Uses the legend's own bookkeeping (``legend._lines``), so the value
        readout / eye toggle that belong to the row go with it.
        """
        # 控制台痕迹（默认关）：跑测试/调试时设 PYLIGHTCHARTS_DEBUG_LEGEND=1 打开。
        # ⚠ 默认关闭：NaN 断点会为**每一段**建一个 legend=False 序列，
        #   一条碎线就能刷几十上百行，看着像"泄漏"（实际不是 ✗）。
        if os.environ.get('PYLIGHTCHARTS_DEBUG_LEGEND'):
            print(f'[pylightcharts] legend=False → 摘图例行 {self.id} name={self.name!r}')
        self.run_script(f'''
            ;(function() {{
                var legend = {self._chart.id}.legend;
                var s = {self.id};
                if (!legend || !Array.isArray(legend._lines) || !s) return;
                var series = s.series;
                for (var i = legend._lines.length - 1; i >= 0; i--) {{
                    if (legend._lines[i].series === series) {{
                        var row = legend._lines[i].row;
                        if (row && row.parentNode) {{
                            row.parentNode.removeChild(row);
                        }}
                        legend._lines.splice(i, 1);
                    }}
                }}
            }})()
        ''')
        return self

    def _toggle_data(self, arg):
        self._visible = bool(arg)
        self._invoke_series('applyOptions', {'visible': arg})
        # Only the main candlestick chart owns a volume series under this handle;
        # guard it so hide_data()/show_data() also work on overlay/indicator series.
        self.run_script(
            f'if ({self.id}.volumeSeries) '
            f'{self.id}.volumeSeries.applyOptions({{visible: {jbool(arg)}}})')

    def vertical_span(
        self,
        start_time: Union[TIME, tuple, list],
        end_time: Optional[TIME] = None,
        color: str = 'rgba(252, 219, 3, 0.2)',
        round: bool = False,
        opacity: Optional[float] = None
    ):
        """
        Creates a vertical line or span across the chart.\n
        Start time and end time can be used together, or end_time can be
        omitted and a single time or a list of times can be passed to start_time.
        """
        if round:
            start_time = self._single_datetime_format(start_time)
            end_time = self._single_datetime_format(
                end_time) if end_time else None
        return VerticalSpan(self, start_time, end_time, color, opacity)

    def horizontal_span(
        self,
        low: Union[NUM, tuple, list],
        high: Optional[NUM] = None,
        color: str = '#7E57C2',
        opacity: Optional[float] = 0.2,
        line_color: str = 'rgba(126, 87, 194, 0.90)',
        line_width: int = 1,
        line_style: LINE_STYLE = 'solid',
        autoscale: bool = False,
        filled: Optional[bool] = None,
        pane_index: Optional[int] = None
    ):
        """Shade a horizontal band between two prices (a support/resistance zone).

        Both prices given → a filled band; a single price (or a list of prices) →
        one full-width horizontal line each; ``filled`` forces one of the two.

        The band lands in the pane this method is called on - call it on the
        chart (main pane) or on a series inside a sub-pane. ``pane_index=`` does
        that for you: it anchors to the first series created in that pane, which
        is the way to put constant support/resistance levels into a sub-pane
        without keeping a series reference around.

        Use :meth:`~pylightcharts.drawings.HorizontalSpan.set_prices` /
        ``apply_options`` on the returned object to move or restyle it.
        """
        target = self
        if pane_index is not None:
            target = self._chart._pane_series(pane_index)
        return HorizontalSpan(target, low, high, color, opacity, line_color,
                              line_width, line_style, autoscale, filled)

    def fill_between(self, other: 'SeriesCommon',
                     lower: Optional['SeriesCommon'] = None, **options):
        """Shade the area between two series lines (a band / "fill between").

        Both usages work and mean the same thing::

            upper.fill_between(lower)              # on one of the two series
            chart.fill_between(upper, lower)        # or on the chart

        The two series have to be on the same pane and price scale (the upper and
        lower lines of :meth:`add_bollinger` / :meth:`add_keltner`, for example).
        Options: ``color``, ``line_color`` (optional outline), ``line_width``,
        ``line_style``; the returned object also has ``apply_options`` /
        ``delete``.
        """
        if lower is None:
            first, second = self, other
        else:
            first, second = other, lower
        for series in (first, second):
            if not hasattr(series, 'id') or not hasattr(series, '_chart'):
                raise TypeError(
                    'fill_between() expects two series created by this chart '
                    '(e.g. the upper/lower lines of add_bollinger)')
        return LineFill(self._chart, first, second, **options)

    def _do_delete(self):
        """Shared, **idempotent** series removal.

        Several managers keep the same series in more than one list and can end
        up calling `delete()` twice; the second call used to emit
        `removeSeries({"$ref": ...})` for a handle the JS side had already
        dropped, which logged "Value is undefined". A `_deleted` flag makes a
        repeated delete a no-op.
        """
        if self.__dict__.get('_deleted'):
            return
        self.__dict__['_deleted'] = True
        # NaN 断点用的分段序列一起删掉，否则它们会留在图上
        if hasattr(self, '_clear_gap_series'):
            self._clear_gap_series()
        self._chart._forget_series(self)
        if self in self._chart._lines:
            self._chart._lines.remove(self)
        # the JS side looks the wrapper up to drop the legend row with it, so the
        # handle has to be passed as a reference, not as a plain string
        self._chart._invoke('removeSeries', ref(self.id))
        self.win.run_script(f'delete {self.id}')


class Line(SeriesCommon):
    #: 序列类型。``SeriesCommon`` 的 NaN 断点拆分（``_gap_value_column``）只认
    #: ``kind == 'Line'``，而 ``create_line()`` 建的线以前**没有** kind，
    #: 所以它画的指标线在 NaN 处不会断开（``add_series('Line')`` 因为 kind 齐全正常）✓
    kind = 'Line'

    def __init__(self, chart, name, color, style, width, price_line,
                 price_label, price_scale_id=None, crosshair_marker=True,
                 legend_toggle: bool = True, legend: bool = True):

        super().__init__(chart, name)
        self.color = color
        # 记一份样式：NaN 断点拆段时要复制线色/线宽/虚实（否则分段会用默认色 ✗）
        self._remember_options({
            'color': color, 'line_style': style, 'line_width': width,
            'price_line_visible': price_line, 'last_value_visible': price_label,
        })

        self.run_script(f'''
            {self.id} = {self._chart.id}.createLineSeries(
                "{name}",
                {{
                    color: '{color}',
                    lineStyle: {as_enum(style, LINE_STYLE)},
                    lineWidth: {width},
                    lastValueVisible: {jbool(price_label)},
                    priceLineVisible: {jbool(price_line)},
                    crosshairMarkerVisible: {jbool(crosshair_marker)},
                    priceScaleId: {f'"{price_scale_id}"' if price_scale_id else 'undefined'}
                    {"""autoscaleInfoProvider: () => ({
                            priceRange: {
                                minValue: 1_000_000_000,
                                maxValue: 0,
                            },
                        }),
                    """ if chart._scale_candles_only else ''}
                }},
                {jbool(legend_toggle)}
            )
        null''')
        if not legend:
            self.remove_legend_row()          # 真名字照给 ✓，图例行摘掉 ✓

    # def _set_trend(self, start_time, start_value, end_time, end_value, ray=False, round=False):
    #     if round:
    #         start_time = self._single_datetime_format(start_time)
    #         end_time = self._single_datetime_format(end_time)
    #     else:
    #         start_time, end_time = pd.to_datetime((start_time, end_time)).astype('int64') // 10 ** 9

    #     self.run_script(f'''
    #     {self._chart.id}.chart.timeScale().applyOptions({{shiftVisibleRangeOnNewBar: false}})
    #     {self.id}.series.setData(
    #         calculateTrendLine({start_time}, {start_value}, {end_time}, {end_value},
    #                             {self._chart.id}, {jbool(ray)}))
    #     {self._chart.id}.chart.timeScale().applyOptions({{shiftVisibleRangeOnNewBar: true}})
    #     ''')

    def delete(self):
        """
        Irreversibly deletes the line, its legend row and (when it was the last
        series of its pane) the pane itself.
        """
        self._do_delete()


class Histogram(SeriesCommon):
    kind = 'Histogram'

    def __init__(self, chart, name, color, price_line, price_label, scale_margin_top,
                 scale_margin_bottom, legend_toggle: bool = True,
                 legend: bool = True):
        super().__init__(chart, name)
        self.color = color
        self.run_script(f'''
        {self.id} = {chart.id}.createHistogramSeries(
            "{name}",
            {{
                color: '{color}',
                lastValueVisible: {jbool(price_label)},
                priceLineVisible: {jbool(price_line)},
                priceScaleId: '{self.id}',
                priceFormat: {{type: "volume"}},
            }},
            {jbool(legend_toggle)}
            // precision: 2,
        )
        {self.id}.series.priceScale().applyOptions({{
            scaleMargins: {{top:{scale_margin_top}, bottom: {scale_margin_bottom}}}
        }})''')
        if not legend:
            self.remove_legend_row()

    def delete(self):
        """
        Irreversibly deletes the histogram, its legend row and (when it was the
        last series of its pane) the pane itself.
        """
        self._do_delete()

    def scale(self, scale_margin_top: float = 0.0, scale_margin_bottom: float = 0.0):
        # migrated to the generic bridge (was a hand-written JS snippet)
        self.win.invoke(
            f'{self.id}.priceScale', 'applyOptions',
            {'scaleMargins': {'top': scale_margin_top, 'bottom': scale_margin_bottom}},
        )


def _drop_none(value):
    """递归去掉 dict 里值为 `None` 的键（lightweight-charts 不接受 null ✓）"""
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    if isinstance(value, dict):
        return {key: _drop_none(item) for key, item in value.items()
                if item is not None}
    return value


class BridgeSeries(SeriesCommon):
    """Base class for series created through the generic bridge.

    The series type is looked up by name in the JS `Handler._seriesDefinitions`
    map, which already covers Line/Area/Bar/Baseline/Candlestick/Histogram.
    Supporting a new series type therefore needs Python changes only.
    """

    kind: str = 'Line'

    def __init__(self, chart: 'AbstractChart', name: str = '', options: Optional[dict] = None,
                 pane_index: Optional[int] = None, legend_toggle: bool = True,
                 legend: bool = True):
        super().__init__(chart, name)
        self._create(chart, name, options, pane_index, legend_toggle, legend)

    def _create(self, chart: 'AbstractChart', name: str, options: Optional[dict],
                pane_index: Optional[int] = None, legend_toggle: bool = True,
                legend: bool = True):
        # 'new' -> a fresh pane, int -> that pane (creating the missing ones: the
        # engine clamps an out-of-range paneIndex to panes.length, so the series
        # would otherwise silently land in the last pane)
        pane_index = chart._resolve_pane(pane_index)
        self._pane_index = pane_index if pane_index is not None else 0
        # assign the created wrapper to this series' global handle so the shared
        # SeriesCommon data/marker methods can keep using `{id}.series`
        # paneIndex has to be passed explicitly for `legend_toggle` to line up.
        # NOTE: the JS side builds a legend row for every series regardless of the
        # name, so an empty name is *not* what skips it — the row is removed
        # explicitly below (`remove_legend_row`, see its docstring).
        args = [self.kind, name, options or {}, self.id,
                pane_index if pane_index is not None else 0, legend_toggle]
        chart._invoke_assign(self.id, 'addSeries', *args)
        if not legend:
            self.remove_legend_row()
        # 本地留一份样式：复制样式时不必做同步 JS 往返（那是启动变慢的元凶）
        self.__dict__['_local_options'] = dict(options or {})

    def style(self, **options):
        """Apply arbitrary (snake_cased) series options through the bridge."""
        self.apply_options(**options)

    def delete(self):
        """Remove the series, its legend row and an emptied pane with it."""
        self._do_delete()


class CustomSeries(BridgeSeries):
    """A declarative custom series.

    Python supplies the *shape descriptors* for each data point (see
    :mod:`pylightcharts.shapes`); one generic JS renderer draws them every frame,
    so there is no per-frame round-trip between python and the browser.

        series = chart.add_custom_series('range')
        series.set(df, shapes=lambda row: shapes.range_bar(row['low'], row['high']))
    """

    kind = 'Custom'

    def __init__(self, chart: 'AbstractChart', name: str = '', options: Optional[dict] = None,
                 pane_index: Optional[int] = None, spec: Optional[dict] = None,
                 legend_toggle: bool = True, legend: bool = True):
        self._spec = spec
        super().__init__(chart, name, options, pane_index, legend_toggle, legend)

    def _create(self, chart: 'AbstractChart', name: str, options: Optional[dict],
                pane_index: Optional[int] = None, legend_toggle: bool = True,
                legend: bool = True):
        pane_index = chart._resolve_pane(pane_index)   # 'new' -> fresh pane
        self._pane_index = pane_index if pane_index is not None else 0
        # spec=None -> the built-in declarative renderer; paneIndex is explicit so
        # that `legend_toggle` lines up with the JS signature
        args = [name, options or {}, self.id,
                pane_index if pane_index is not None else 0,
                self._spec, legend_toggle]
        chart._invoke_assign(self.id, 'createCustomSeries', *args)
        if not legend:
            self.remove_legend_row()

    def set(self, df: Optional[pd.DataFrame] = None, format_cols: bool = True, shapes=None):
        """Set the data. `shapes` is a column name, a list per row, or a callable(row)."""
        if df is None or df.empty:
            self.run_script(f'{self.id}.series.setData([])')
            self.data = pd.DataFrame()
            return
        frame = df.copy()
        if format_cols:
            frame = self._df_datetime_format(frame)
        if shapes is not None:
            if callable(shapes):
                frame['shapes'] = [shapes(row) for _, row in frame.iterrows()]
            else:
                frame['shapes'] = list(shapes)
            # ★ 图形字典里的 `None`（`shapes.stem` / `triangle` 等会带
            #   `fillColor: None` / `borderColor: None`）会让 lightweight-charts
            #   抛 `Uncaught Error: Value is null`，**整段数据被丢弃** ✗
            #   → 统一在这里去掉，所有调用方（盈亏散点 / 交易信号 / 画线）都受益 ✓
            frame['shapes'] = [
                _drop_none(shape) for shape in frame['shapes']]
        self.data = frame.copy()
        self._last_bar = frame.iloc[-1]
        records = frame.to_dict(orient='records')
        if shapes is not None:
            records = [_drop_none(row) for row in records]
        # nested shape lists cannot go through the numeric binary path
        self.run_script(
            f'{self.id}.series.setData({js_value(records)})')

    def update(self, row):
        """Update the last data point (a dict or Series including ``time``)."""
        if isinstance(row, pd.Series):
            row = row.to_dict()
        self.run_script(f'{self.id}.series.update({js_value(row)})')


class GenericSeries(BridgeSeries):
    """A series whose type is chosen at call time, e.g. `chart.add_series('Area', ...)`."""

    def __init__(self, chart: 'AbstractChart', kind: str, name: str = '', options: Optional[dict] = None,
                 pane_index: Optional[int] = None, legend_toggle: bool = True,
                 legend: bool = True):
        self.kind = kind
        super().__init__(chart, name, _normalize_base_value(kind, options or {}),
                         pane_index, legend_toggle, legend)


class Area(BridgeSeries):
    kind = 'Area'

    def __init__(self, chart: 'AbstractChart', name: str = '', line_color: str = 'rgba(214, 237, 255, 0.6)',
                 top_color: Optional[str] = None, bottom_color: Optional[str] = None, line_width: int = 2,
                 price_line: bool = True, price_label: bool = True, price_scale_id: Optional[str] = None,
                 pane_index: Optional[int] = None, legend_toggle: bool = True,
                 legend: bool = True):
        super().__init__(chart, name, {
            'lineColor': line_color,
            'topColor': top_color or line_color,
            'bottomColor': bottom_color or 'rgba(0, 0, 0, 0)',
            'lineWidth': line_width,
            'lastValueVisible': price_label,
            'priceLineVisible': price_line,
            'priceScaleId': price_scale_id,
        }, pane_index, legend_toggle, legend)


class Bar(BridgeSeries):
    kind = 'Bar'

    def __init__(self, chart: 'AbstractChart', name: str = '', up_color: str = 'rgba(39, 157, 130, 0.9)',
                 down_color: str = 'rgba(200, 97, 100, 0.9)', price_line: bool = True,
                 price_label: bool = True, price_scale_id: Optional[str] = None,
                 pane_index: Optional[int] = None, legend_toggle: bool = True,
                 legend: bool = True):
        super().__init__(chart, name, {
            'upColor': up_color,
            'downColor': down_color,
            'lastValueVisible': price_label,
            'priceLineVisible': price_line,
            'priceScaleId': price_scale_id,
        }, pane_index, legend_toggle, legend)


class Baseline(BridgeSeries):
    kind = 'Baseline'

    def __init__(self, chart: 'AbstractChart', name: str = '', base_value: Optional[float] = None,
                 top_line_color: str = 'rgba(39, 157, 130, 0.9)',
                 bottom_line_color: str = 'rgba(200, 97, 100, 0.9)',
                 price_line: bool = True, price_label: bool = True,
                 price_scale_id: Optional[str] = None, pane_index: Optional[int] = None,
                 legend_toggle: bool = True, legend: bool = True):
        # a baseline is a normal series; pass legend=False to keep a reference
        # line out of the legend (and with no eye to confuse the other rows)
        super().__init__(chart, name, {
            'baseValue': {'type': 'price', 'price': base_value} if base_value is not None else None,
            'topLineColor': top_line_color,
            'bottomLineColor': bottom_line_color,
            'lastValueVisible': price_label,
            'priceLineVisible': price_line,
            'priceScaleId': price_scale_id,
        }, pane_index, legend_toggle, legend)


class Candlestick(SeriesCommon):
    def __init__(self, chart: 'AbstractChart'):
        super().__init__(chart)
        self._volume_up_color = 'rgba(83,141,131,0.8)'
        self._volume_down_color = 'rgba(200,127,130,0.8)'

        self.candle_data = pd.DataFrame()

        # self.run_script(f'{self.id}.makeCandlestickSeries()')

    def set(self, df: Optional[pd.DataFrame] = None, keep_drawings=False):
        """
        Sets the initial data for the chart.\n
        :param df: columns: date/time, open, high, low, close, volume (if volume enabled).
        :param keep_drawings: keeps any drawings made through the toolbox. Otherwise, they will be deleted.
        """
        if df is None or df.empty:
            self.run_script(f'{self.id}.series.setData([])')
            self.run_script(f'{self.id}.volumeSeries.setData([])')
            self.candle_data = pd.DataFrame()
            self._refresh_indicators(full=True)
            return
        df = self._df_datetime_format(df)
        self.candle_data = df.copy()
        self._last_bar = df.iloc[-1]
        self.run_script(f'{self.id}.series.setData({encode_series_data(df)})')

        self._send_volume(df)

        for line in self._lines:
            if line.name not in df.columns:
                continue
            line.set(df[['time', line.name]], format_cols=False)
        # set autoScale to true in case the user has dragged the price scale
        self.run_script(f'''
            if (!{self.id}.chart.priceScale("right").options.autoScale)
                {self.id}.chart.priceScale("right").applyOptions({{autoScale: true}})
        ''')
        # keep every computed indicator in sync with the new data
        self._refresh_indicators(full=True)
        # TODO keep drawings doesn't work consistenly w
        if keep_drawings:
            self.run_script(
                f'{self._chart.id}.toolBox?._drawingTool.repositionOnTime()')
        else:
            self.run_script(f"{self._chart.id}.toolBox?.clearDrawings()")

    def update(self, series: pd.Series, _from_tick=False):
        """
        Updates the data from a bar;
        if series['time'] is the same time as the last bar, the last bar will be overwritten.\n
        :param series: labels: date/time, open, high, low, close, volume (if using volume).
        """
        series = self._series_datetime_format(
            series) if not _from_tick else series
        if series['time'] != self._last_bar['time']:
            self.candle_data.loc[self.candle_data.index[-1]] = self._last_bar
            self.candle_data = pd.concat(
                [self.candle_data, series.to_frame().T], ignore_index=True)
            self._chart.events.new_bar._emit(self)

        self._last_bar = series
        self.run_script(f'{self.id}.series.update({js_data(series)})')
        if 'volume' in series:
            volume = series.drop(['open', 'high', 'low', 'close']).rename(
                {'volume': 'value'})
            volume['color'] = self._volume_up_color if series['close'] > series['open'] else self._volume_down_color
            self.run_script(
                f'{self.id}.volumeSeries.update({js_data(volume)})')
        # push just the last point of every indicator
        self._refresh_indicators(full=False)

    def update_from_tick(self, series: pd.Series, cumulative_volume: bool = False):
        """
        Updates the data from a tick.\n
        :param series: labels: date/time, price, volume (if using volume).
        :param cumulative_volume: Adds the given volume onto the latest bar.
        """
        series = self._series_datetime_format(series)
        if series['time'] < self._last_bar['time']:
            raise ValueError(
                f'Trying to update tick of time "{pd.to_datetime(series["time"])}", which occurs before the last bar time of "{pd.to_datetime(self._last_bar["time"])}".')
        bar = pd.Series(dtype='float64')
        if series['time'] == self._last_bar['time']:
            bar = self._last_bar
            bar['high'] = max(self._last_bar['high'], series['price'])
            bar['low'] = min(self._last_bar['low'], series['price'])
            bar['close'] = series['price']
            if 'volume' in series:
                if cumulative_volume:
                    bar['volume'] += series['volume']
                else:
                    bar['volume'] = series['volume']
        else:
            for key in ('open', 'high', 'low', 'close'):
                bar[key] = series['price']
            bar['time'] = series['time']
            if 'volume' in series:
                bar['volume'] = series['volume']
        self.update(bar, _from_tick=True)

    def price_scale(
        self,
        auto_scale: bool = True,
        mode: PRICE_SCALE_MODE = 'normal',
        invert_scale: bool = False,
        align_labels: bool = True,
        scale_margin_top: float = 0.2,
        scale_margin_bottom: float = 0.2,
        border_visible: bool = False,
        border_color: Optional[str] = None,
        text_color: Optional[str] = None,
        entire_text_only: bool = False,
        visible: bool = True,
        ticks_visible: bool = False,
        minimum_width: int = 0
    ):
        self.price_scale_options(
            auto_scale=auto_scale,
            mode=as_enum(mode, PRICE_SCALE_MODE),
            invert_scale=invert_scale,
            align_labels=align_labels,
            scale_margins={'top': scale_margin_top,
                           'bottom': scale_margin_bottom},
            border_visible=border_visible,
            border_color=border_color,
            text_color=text_color,
            entire_text_only=entire_text_only,
            visible=visible,
            ticks_visible=ticks_visible,
            minimum_width=minimum_width,
        )

    def series_options(self, **options):
        """Apply arbitrary options to the main (candlestick) series.

        `chart.apply_options()` targets the *chart*, this targets the series
        the chart is built around.
        """
        self._invoke_series('applyOptions', options)

    def candle_style(
            self, up_color: str = 'rgba(39, 157, 130, 100)', down_color: str = 'rgba(200, 97, 100, 100)',
            wick_visible: bool = True, border_visible: bool = True, border_up_color: str = '',
            border_down_color: str = '', wick_up_color: str = '', wick_down_color: str = ''):
        """
        Candle styling for each of its parts.\n
        If only `up_color` and `down_color` are passed, they will color all parts of the candle.
        """
        self._invoke_series('applyOptions', {
            'upColor': up_color,
            'downColor': down_color,
            'wickVisible': wick_visible,
            'borderVisible': border_visible,
            'borderUpColor': border_up_color or up_color,
            'borderDownColor': border_down_color or down_color,
            'wickUpColor': wick_up_color or up_color,
            'wickDownColor': wick_down_color or down_color,
        })

    def _volume_data(self, frame=None) -> Optional[pd.DataFrame]:
        """The volume series' data, coloured by the up/down candles."""
        frame = self.candle_data if frame is None else frame
        if frame is None or frame.empty or 'volume' not in frame.columns:
            return None
        volume = frame.drop(columns=['open', 'high', 'low', 'close']).rename(
            columns={'volume': 'value'})
        volume['color'] = self._volume_down_color
        volume.loc[frame['close'] > frame['open'],
                   'color'] = self._volume_up_color
        return volume

    def _send_volume(self, frame=None) -> None:
        volume = self._volume_data(frame)
        if volume is not None:
            self.run_script(
                f'{self.id}.volumeSeries.setData({encode_series_data(volume)})')

    def volume_config(self, scale_margin_top: float = 0.8, scale_margin_bottom: float = 0.0,
                      up_color='rgba(83,141,131,0.8)', down_color='rgba(200,127,130,0.8)'):
        """
        Configure volume settings.\n
        Numbers for scaling must be greater than 0 and less than 1.\n
        Volume colors must be applied prior to setting/updating the bars.\n
        """
        self._volume_up_color = up_color or self._volume_up_color
        self._volume_down_color = down_color or self._volume_down_color
        # the per-bar colours travel with the data, so re-send it: switching a
        # theme on a chart that already has bars keeps them the old colour
        if self.candle_data is not None and not self.candle_data.empty:
            self._send_volume()
        handle = f'{self.id}.volumePriceScaleHandle'
        self.win.invoke(f'{self.id}.volumeSeries',
                        'priceScale', store_as=handle)
        self.win.invoke(handle, 'applyOptions', {
            'scaleMargins': {'top': scale_margin_top, 'bottom': scale_margin_bottom},
        })


def _reject_formatter_mix(method: str, name: str, options: dict,
                          defaults: Optional[dict] = None) -> None:
    """`name=` selects a registered formatter: mixing it with the declarative
    options silently ignored them, which reads like 'the option does nothing'."""
    defaults = defaults or {}
    given = {key: value for key, value in options.items()
             if value is not None and value != defaults.get(key)}
    if given:
        keys = ', '.join(sorted(given))
        raise ValueError(
            f"{method} got name={name!r} together with {keys}: a named "
            'formatter replaces the declarative options, so those are ignored. '
            'Pass either the options or the name (and remember the last '
            'formatter call wins).')


def _remember_inversion(target, options) -> None:
    """Track `invertScale` so the swing helpers can flip their markers.

    Set from `price_scale(invert_scale=...)`, `PriceScale.invert()` and the raw
    `apply_options(rightPriceScale={'invertScale': True})` escape hatch - the
    python side is the only place that knows, since reading it back would need a
    live webview.
    """
    if not isinstance(options, dict):
        return
    for key in ('invert_scale', 'invertScale'):
        if key in options:
            chart = getattr(target, '_chart', target)
            changed = bool(options[key]) != bool(
                getattr(chart, '_price_scale_inverted', False))
            chart._price_scale_inverted = bool(options[key])
            if changed:
                _remark_scaled_markers(chart)
            return


def _remark_scaled_markers(chart) -> None:
    """Re-place the markers that depend on the price scale's direction.

    Inverting the scale flips where a high/low *appears*, and marker positions
    are screen-relative (`aboveBar` / `belowBar`), so a ZigZag added before the
    inversion has to redraw its arrows.
    """
    frame = getattr(chart, 'candle_data', None)
    if frame is None or getattr(frame, 'empty', True):
        return
    for binding in list(getattr(chart, '_indicator_bindings', [])):
        if getattr(binding, 'flips_with_scale', False):
            binding.refresh(frame, full=True)


class _ZigzagBinding:
    """Keeps a ZigZag line (and its markers) in sync with the chart data."""

    def __init__(self, chart: 'AbstractChart', series, threshold: float,
                 high_column: str, low_column: str, markers: bool = True,
                 label: bool = False, size: int = 2,
                 include_unconfirmed: bool = True,
                 inverted: Optional[bool] = None):
        self.chart = chart
        self.series = series
        self.threshold = threshold
        self.high_column = high_column
        self.low_column = low_column
        self.markers = markers
        self.label = label
        self.size = size
        self.include_unconfirmed = include_unconfirmed
        self.inverted = inverted
        #: its markers sit next to a pivot price, so a price-scale inversion
        #: has to re-mark them (see `_remember_inversion`)
        self.flips_with_scale = True

    def refresh(self, frame, full: bool = True) -> None:
        """Recompute the pivots and re-send the (sparse) line data."""
        swings = zigzag(frame[self.high_column], frame[self.low_column],
                        threshold=self.threshold, time=frame['time'],
                        include_unconfirmed=self.include_unconfirmed)
        data = swings.rename(columns={'price': 'value'})[['time', 'value']]
        self.chart.run_script(
            f'{self.series.id}.series.setData({encode_series_data(data)})')
        self.series.data = data.copy()
        if self.markers:
            confirmed = swings if self.include_unconfirmed else \
                swings[swings['confirmed']]
            self.chart.mark_swings(swings=confirmed, label=self.label,
                                   size=self.size, decimals=2, clear=True,
                                   inverted=self.inverted)


class AbstractChart(IndicatorMixin, Candlestick, Pane):
    #: which chart constructor to use: 'time', 'yield-curve', 'options' or 'custom:<name>'
    _chart_kind: str = 'time'
    #: whether the horizontal scale is time (False for numeric-x charts)
    _time_based: bool = True
    #: optional custom horizontal scale (see :meth:`register_horz_scale_behavior`)
    _horz_scale_name: Optional[str] = None
    _horz_scale: Optional[dict] = None

    def __init__(self, window: Window, width: float = 1.0, height: float = 1.0,
                 scale_candles_only: bool = False, toolbox: bool = False,
                 autosize: bool = True, position: FLOAT = 'left',
                 attribution_logo: Optional[bool] = None,
                 keyboard: bool = True, keyboard_step: float = 0.1):
        Pane.__init__(self, window)
        self._setup_horz_scale()

        self._lines = []
        self._pane_count = 1
        #: panes created with `preserve_empty=True` (the engine keeps them)
        self._preserved_panes: set = set()
        self._indicator_bindings: List[_IndicatorBinding] = []
        self._scale_candles_only = scale_candles_only
        self._width = width
        self._height = height
        self.events: Events = Events(self)

        from pylightcharts.polygon import PolygonAPI
        self.polygon: PolygonAPI = PolygonAPI(self)

        # `attribution_logo` defaults to the module-level setting
        # (`set_attribution_logo`, off unless asked for); an explicit
        # True/False only affects this chart.
        logo = bool(ATTRIBUTION_LOGO if attribution_logo is None
                    else attribution_logo)
        self.run_script(
            f'{self.id} = new Lib.Handler("{self.id}", {width}, {height}, "{position}", '
            f'{jbool(autosize)}, "{self._chart_kind}", {jbool(logo)})')
        # arrow keys pan/zoom this chart (on by default, see `Handler._handleArrowKey`)
        if not keyboard:
            self.run_script(f'{self.id}.keyboardNavigation = false')
        if keyboard_step != 0.1:
            self.run_script(f'{self.id}.keyboardStep = {keyboard_step}')

        Candlestick.__init__(self, self)

        self.topbar: TopBar = TopBar(self)
        #: the last `legend(...)` call, so a theme can restyle without resetting
        self._legend_options: Optional[dict] = None
        # page-level layout: the window tracks its charts in creation order
        self.win.layout.register(self)
        # a theme set on the window also covers charts created later
        theme = getattr(self.win, '_theme', None)
        if theme:
            self._apply_theme(theme)
        if toolbox:
            self.toolbox: ToolBox = ToolBox(self)

    def fit(self):
        """
        Fits the maximum amount of the chart data within the viewport.
        """
        self.win.invoke(f'{self.id}.timeScale', 'fitContent')

    # ------------------------------------------------------------------
    # Custom horizontal scale
    # ------------------------------------------------------------------

    def _setup_horz_scale(self):
        spec = getattr(self, '_horz_scale', None)
        if not spec:
            return
        name = getattr(self, '_horz_scale_name', None) or 'custom'
        self.register_horz_scale_behavior(name, spec)
        self._chart_kind = f'custom:{name}'

    def register_horz_scale_behavior(self, name: str, spec: dict):
        """Register a callback-driven ``IHorzScaleBehavior`` under ``name``.

        ``spec`` maps ``IHorzScaleBehavior`` method names to either a registered
        callback name (str) or a ``(params, body)`` tuple registered on the fly.
        It must run *before* the chart's ``Handler`` is created; the usual way is
        to set ``_horz_scale_name`` / ``_horz_scale`` on a chart subclass (or
        call this from :meth:`Window.preload` with ``chart._chart_kind`` set to
        ``custom:<name>``).
        """
        mapping = {}
        for key, value in spec.items():
            if (isinstance(value, (tuple, list)) and len(value) == 2
                    and isinstance(value[0], (tuple, list))):
                params, body = value
                callback = f'__horz_{name}_{key}'
                self.run_script(
                    f'Lib.registerCallback({json.dumps(callback)}, '
                    f'{json.dumps(list(params))}, {json.dumps(body)})')
            else:
                callback = value
            mapping[key] = callback
        self.run_script(
            f'Lib.registerHorzScaleBehaviorSpec({json.dumps(name)}, {js_value(mapping)})')

    @contextmanager
    def batch(self):
        """Buffer every bridge call and flush them as a single script on exit.

        Use it to push a burst of ticks without paying one webview round-trip
        per update::

            with chart.batch():
                for tick in ticks:
                    chart.update(tick)
        """
        with self.win.bulk_run:
            yield self

    def apply_options(self, **options):
        """Apply arbitrary chart options (snake_case keys are camelCased automatically).

        This is the escape hatch that gives python full access to the chart API.
        """
        for key in ('right_price_scale', 'rightPriceScale', 'left_price_scale',
                    'leftPriceScale', 'invert_scale', 'invertScale'):
            if key in options:
                _remember_inversion(self, options[key]
                                    if isinstance(options[key], dict)
                                    else options)
        self.win.invoke(f'{self.id}.chart', 'applyOptions', options)

    def time_scale_options(self, **options):
        """Apply arbitrary time-scale options (snake_case keys are camelCased)."""
        self.win.invoke(f'{self.id}.timeScale', 'applyOptions', options)

    def time_scale_settings(self) -> dict:
        """Read the time scale's current (merged) options."""
        return self.win.invoke_get(f'{self.id}.timeScale', 'options')

    # ------------------------------------------------------------------
    # Formatters (declarative, because the JS callbacks are synchronous)
    # ------------------------------------------------------------------

    def set_price_formatter(self, decimals: Optional[int] = None, thousands: bool = False,
                            prefix: str = '', suffix: str = '', compact: bool = False,
                            name: Optional[str] = None):
        """Format the price-scale labels.

        `name` selects a formatter registered with :meth:`register_js_formatter`
        and **replaces** the declarative options (passing both is an error, not a
        merge). The last call wins - a later :meth:`set_option_callback` on
        ``localization.priceFormatter`` overrides this one too. Use
        :meth:`format_price` to see what the axis currently renders.
        """
        if name is not None:
            _reject_formatter_mix('set_price_formatter', name, {
                'decimals': decimals, 'prefix': prefix, 'suffix': suffix,
                'thousands': thousands, 'compact': compact},
                defaults={'decimals': None, 'prefix': '', 'suffix': '',
                          'thousands': False, 'compact': False})
            spec = name
        else:
            spec = {
                'decimals': decimals,
                'thousands': thousands,
                'prefix': prefix,
                'suffix': suffix,
                'compact': compact,
            }
        self.win.invoke(self.id, 'setPriceFormatter', spec)

    def set_time_formatter(self, template: str = 'YYYY-MM-DD', utc: bool = True,
                           name: Optional[str] = None):
        """Format the time-scale labels, e.g. ``'YYYY-MM-DD HH:mm'``.

        Tokens: ``YYYY YY MMM MM DD HH mm ss``. As with
        :meth:`set_price_formatter`, `name` replaces `template` / `utc`, and the
        last call wins.
        """
        if name is not None:
            _reject_formatter_mix('set_time_formatter', name, {
                'template': template, 'utc': utc},
                defaults={'template': 'YYYY-MM-DD', 'utc': True})
            spec = name
        else:
            spec = {'template': template, 'utc': utc}
        self.win.invoke(self.id, 'setTimeFormatter', spec)

    def format_price(self, value: float) -> str:
        """Format `value` with the formatter the price scale uses right now.

        A readback (the chart has to be loaded), handy to check which of several
        formatter calls is the effective one.
        """
        return self.win.eval_js(
            f'({self.id}.chart.options().localization.priceFormatter'
            f' || ((v) => String(v)))({value})')

    def register_js_formatter(self, name: str, body: str):
        """Register a JS formatter so it can be selected by name.

        :param body: a JS expression returning a function, e.g.
            ``"value => '€' + value.toFixed(2)"``
        """
        self.run_script(f'Lib.registerFormatter({json.dumps(name)}, {body})')

    def register_js_callback(self, name: str, params: Optional[list] = None,
                             body: str = 'return undefined;'):
        """Register a JS callback for function-valued options.

        :param name: handle used later (by name).
        :param params: positional parameter names, e.g. ``['price']``.
        :param body: JS statement body, e.g. ``"return (price/1e6).toFixed(1)+'M'"``.
        """
        self.run_script(
            f'Lib.registerCallback({json.dumps(name)}, {json.dumps(params or [])}, '
            f'{json.dumps(body)})')

    def set_option_callback(self, handle: str, method: str, option_path: str, callback: str):
        """Install a registered JS callback at ``handle.<method>({option_path: fn})``.

        ``option_path`` may be dotted (e.g. ``localization.priceFormatter``).
        """
        self.run_script(
            f'Lib.setOptionCallback({json.dumps(handle)}, {json.dumps(method)}, '
            f'{json.dumps(option_path)}, {json.dumps(callback)})')

    def set_tick_mark_formatter(self, callback: str):
        """Use a registered JS callback as ``timeScale.tickMarkFormatter``."""
        self.set_option_callback(f'{self.id}.timeScale', 'applyOptions',
                                 'tickMarkFormatter', callback)

    def set_price_formatter_callback(self, callback: str):
        """Use a registered JS callback as the chart ``localization.priceFormatter``."""
        self.set_option_callback(f'{self.id}.chart', 'applyOptions',
                                 'localization.priceFormatter', callback)

    def set_time_formatter_callback(self, callback: str):
        """Use a registered JS callback as the chart ``localization.timeFormatter``."""
        self.set_option_callback(f'{self.id}.chart', 'applyOptions',
                                 'localization.timeFormatter', callback)

    def sync(self, other: 'AbstractChart', crosshairs_only: bool = False):
        """Synchronise another chart with this one (pan/zoom, optionally crosshairs only).

        Calling it again replaces the previous link instead of stacking
        listeners, and :meth:`unsync` undoes it.
        """
        self.run_script(
            f'Lib.Handler.syncCharts({other.id}, {self.id}, {jbool(crosshairs_only)}); null')
        return other

    def unsync(self, other: 'AbstractChart'):
        """Undo :meth:`sync`: the two charts move independently again."""
        self.run_script(
            f'Lib.Handler.unsyncCharts({other.id}, {self.id}); null')
        return other

    # ------------------------------------------------------------------
    # Time scale
    # ------------------------------------------------------------------

    def scroll_to_position(self, position: float, animated: bool = True):
        """Scroll so the rightmost bar sits at `position` (bar offsets from the right edge)."""
        self.win.invoke(f'{self.id}.timeScale',
                        'scrollToPosition', position, animated)

    def scroll_to_real_time(self, animated: bool = True):
        """Scroll to the latest bar."""
        self.win.invoke(f'{self.id}.timeScale', 'scrollToRealTime', animated)

    def reset_time_scale(self):
        """Reset the time scale to its default state."""
        self.win.invoke(f'{self.id}.timeScale', 'resetTimeScale')

    def scroll_position(self) -> float:
        return self.win.invoke_get(f'{self.id}.timeScale', 'scrollPosition')

    def time_scale_width(self) -> int:
        return self.win.invoke_get(f'{self.id}.timeScale', 'width')

    def time_scale_height(self) -> int:
        return self.win.invoke_get(f'{self.id}.timeScale', 'height')

    def get_visible_range(self) -> Optional[dict]:
        """The currently visible time range (``{'from': .., 'to': ..}``)."""
        return self.win.invoke_get(f'{self.id}.timeScale', 'getVisibleRange')

    def get_visible_logical_range(self) -> Optional[dict]:
        return self.win.invoke_get(f'{self.id}.timeScale', 'getVisibleLogicalRange')

    def set_visible_logical_range(self, from_logical: float, to_logical: float):
        self.win.invoke(f'{self.id}.timeScale', 'setVisibleLogicalRange',
                        {'from': from_logical, 'to': to_logical})

    def time_to_coordinate(self, time: TIME) -> Optional[float]:
        return self.win.invoke_get(f'{self.id}.timeScale', 'timeToCoordinate',
                                   self._single_datetime_format(time))

    def coordinate_to_time(self, x: float):
        return self.win.invoke_get(f'{self.id}.timeScale', 'coordinateToTime', x)

    def time_to_index(self, time: TIME):
        return self.win.invoke_get(f'{self.id}.timeScale', 'timeToIndex',
                                   self._single_datetime_format(time))

    def logical_to_coordinate(self, logical: float) -> Optional[float]:
        return self.win.invoke_get(f'{self.id}.timeScale', 'logicalToCoordinate', logical)

    def coordinate_to_logical(self, x: float) -> Optional[float]:
        return self.win.invoke_get(f'{self.id}.timeScale', 'coordinateToLogical', x)

    def get_price_scale(self, price_scale_id: str = 'right') -> 'PriceScale':
        """Return a handle to a chart-level price scale ('left'/'right'/custom id)."""
        return PriceScale(self, price_scale_id)

    # ------------------------------------------------------------------
    # Panes (lightweight-charts v5 native multi-pane)
    # ------------------------------------------------------------------

    def pane_count(self) -> int:
        """Number of panes currently in the chart.

        Before the webview is loaded the count is tracked python-side so this
        (and :meth:`add_pane`) can be called while building a chart offline.
        """
        if self.win.loaded and getattr(self.win, '_return_q', None) is not None:
            return int(self.win.eval_js(f'{self.id}.chart.panes().length'))
        return self._pane_count

    def add_pane(self, preserve_empty: bool = False) -> int:
        """Add an empty pane and return its index.

        ``preserve_empty=True`` keeps the pane around when its last series is
        removed (the engine drops an empty pane otherwise - that is what
        :meth:`remove_series` relies on).
        """
        index = self._pane_count
        self._pane_count += 1
        if preserve_empty:
            self._preserved_panes.add(index)
        self.win.invoke(f'{self.id}.chart', 'addPane', preserve_empty)
        return index

    def remove_series(self, series: 'SeriesCommon') -> None:
        """Remove a series and, when that emptied its pane, the pane too.

        This is what ``series.delete()`` ends up calling: the series and its
        legend row go away, and because an empty pane (created without
        ``preserve_empty``) is dropped by the engine, the python-side pane
        bookkeeping follows - later panes move up one slot, so the pane indices
        of the series that lived below stay correct.
        """
        self._forget_series(series)

    def _forget_series(self, series: 'SeriesCommon') -> None:
        pane = getattr(series, '_pane_index', None)
        if not isinstance(pane, int) or pane == 0:
            return
        if pane in self._preserved_panes:
            return
        remaining = [other for other in self._lines
                     if other is not series
                     and getattr(other, '_pane_index', None) == pane]
        if remaining:
            return
        self._shift_panes_up(pane)

    def _shift_panes_up(self, index: int) -> None:
        """A pane was removed: later panes (and their series) move up a slot."""
        self._pane_count = max(1, self._pane_count - 1)
        self._preserved_panes = {
            pane - 1 if pane > index else pane
            for pane in self._preserved_panes if pane != index}
        for series in self._lines:
            pane = getattr(series, '_pane_index', None)
            if isinstance(pane, int) and pane > index:
                series._pane_index = pane - 1

    def _ensure_pane(self, index: int):
        """Make sure panes up to `index` exist (creating empty ones if needed)."""
        while self._pane_count <= index:
            self.add_pane(preserve_empty=True)

    def _pane_series(self, pane_index: int) -> 'SeriesCommon':
        """A series living in `pane_index` (anchor for pane-level overlays).

        Pane 0 is the chart itself (the main candlestick/bar series); other panes
        need at least one series, since a price band is converted through a
        series' price scale.
        """
        if pane_index == 0:
            return self
        for series in self._lines:
            if getattr(series, '_pane_index', None) == pane_index:
                return series
        raise ValueError(
            f'pane {pane_index} has no series yet: create one there first, or '
            'call series.horizontal_span(...) on one of its series')

    def _resolve_pane(self, pane_index: Optional[Union[int, str]]) -> Optional[int]:
        """Resolve a pane spec: None -> main pane, 'new' -> a fresh pane, int -> that pane."""
        if pane_index == 'new':
            pane_index = self._pane_count
        if isinstance(pane_index, int):
            self._ensure_pane(pane_index)
        return pane_index

    # ------------------------------------------------------------------
    # Indicators (pure-pandas implementations, see `indicators.py`)
    # ------------------------------------------------------------------

    def remove_pane(self, index: int):
        """Remove the pane at `index` (its series go with it)."""
        self.win.invoke(f'{self.id}.chart', 'removePane', index)
        if index > 0:
            self._shift_panes_up(index)

    def swap_panes(self, first: int, second: int):
        """Swap the positions of two panes."""
        self.win.invoke(f'{self.id}.chart', 'swapPanes', first, second)

    def pane_separator(self, color: str = '#2A2E39',
                       hover_color: str = 'rgba(178, 181, 189, 0.4)',
                       enable_resize: bool = True):
        """Style the dividers *between* panes (``layout.panes``).

        The engine colour defaults to ``'#E0E3EB'`` - a near-white line that
        stands out on a dark chart. Pass ``color='transparent'`` to hide it
        completely, and ``enable_resize=False`` to drop the drag handle (the
        handle uses ``hover_color`` while the mouse is over it).

        Note the divider *thickness* is fixed at 1px by Lightweight Charts
        (``SeparatorConstants.SeparatorHeight``); only the colours and the
        resize behaviour are configurable.
        """
        self.apply_options(layout={'panes': {
            'separatorColor': color,
            'separatorHoverColor': hover_color,
            'enableResize': enable_resize,
        }})

    def set_pane_stretch(self, index: int, stretch_factor: float):
        """Set a pane's share of the chart height (its stretch factor).

        Panes split the height left after the separators and the time scale in
        proportion to these factors. The main pane starts at 2 and every other
        pane at 1, so a 3:1 main/sub split is::

            chart.set_pane_stretch(0, 3)
            chart.set_pane_stretch(1, 1)

        Use :meth:`pane_stretch_factor` to read it back.
        """
        self.win.invoke(self._pane_handle(index),
                        'setStretchFactor', stretch_factor)

    def _pane_handle(self, pane_index: int = 0) -> str:
        """Register and return a handle to the pane at `pane_index`."""
        panes = f'{self.id}.panesArray'
        pane = f'{self.id}.pane.{pane_index}'
        self.win.invoke(f'{self.id}.chart', 'panes', store_as=panes)
        self.win.invoke(panes, 'at', pane_index, store_as=pane)
        return pane

    def attach_pane_primitive(self, primitive: str, pane_index: int = 0):
        """Attach a JS primitive registered under `primitive` to a pane."""
        self.win.invoke(self._pane_handle(pane_index),
                        'attachPrimitive', ref(primitive))

    def detach_pane_primitive(self, primitive: str, pane_index: int = 0):
        """Detach a previously attached pane primitive."""
        self.win.invoke(self._pane_handle(pane_index),
                        'detachPrimitive', ref(primitive))

    def create_series_primitive(self, spec: dict, handle: Optional[str] = None) -> 'SeriesPrimitive':
        """Build a declarative ``ISeriesPrimitive`` from a spec.

        Attach it with ``primitive.attach_to(series)``. See
        :mod:`pylightcharts.primitives` for the spec format.
        """
        handle = handle or f'{self.id}.seriesPrimitive.{uuid.uuid4().hex[:6]}'
        self.run_script(
            f'Lib.createSeriesPrimitive({js_value(spec)}, {json.dumps(handle)})')
        return SeriesPrimitive(self.win, handle)

    def create_pane_primitive(self, spec: dict, handle: Optional[str] = None) -> 'PanePrimitive':
        """Build a declarative ``IPanePrimitive`` from a spec.

        Attach it with ``primitive.attach_to(chart, pane_index)``.
        """
        handle = handle or f'{self.id}.panePrimitive.{uuid.uuid4().hex[:6]}'
        self.run_script(
            f'Lib.createPanePrimitive({js_value(spec)}, {json.dumps(handle)})')
        return PanePrimitive(self.win, handle)

    def create_image_watermark(self, image: str, max_width: Optional[int] = None,
                               max_height: Optional[int] = None, pane_index: int = 0) -> str:
        """Add an image watermark to a pane.

        `image` may be a URL, a data URI, or a local file path (read and inlined).
        Returns the JS handle of the created plugin.
        """
        if not image.startswith(('http://', 'https://', 'data:')):
            with open(image, 'rb') as file:
                encoded = b64encode(file.read()).decode()
            image = f'data:image/png;base64,{encoded}'
        handle = f'{self.id}.imageWatermark'
        self.win.invoke(self.id, 'createImageWatermark', pane_index, image, {
            'maxWidth': max_width,
            'maxHeight': max_height,
        }, store_as=handle)
        return handle

    def pane_height(self, index: int = 0) -> int:
        """Current height of a pane in pixels."""
        return self.win.invoke_get(self._pane_handle(index), 'getHeight')

    def set_pane_height(self, height: int, index: int = 0):
        """Give a pane an absolute height in pixels (``height`` first!).

        The engine converts it into a stretch factor and shrinks/grows the other
        panes accordingly; every pane keeps at least 30px. Prefer
        :meth:`set_pane_stretch` when you want a fixed ratio.
        """
        self.win.invoke(self._pane_handle(index), 'setHeight', height)

    def pane_stretch_factor(self, index: int = 0) -> float:
        """The pane's current stretch factor (see :meth:`set_pane_stretch`)."""
        return self.win.invoke_get(self._pane_handle(index), 'getStretchFactor')

    def set_pane_preserve_empty(self, preserve: bool = True, index: int = 0):
        """Keep a pane alive even when it has no series."""
        self.win.invoke(self._pane_handle(index),
                        'setPreserveEmptyPane', preserve)

    def pane_preserve_empty(self, index: int = 0) -> bool:
        return self.win.invoke_get(self._pane_handle(index), 'preserveEmptyPane')

    def pane_series_count(self, index: int = 0) -> int:
        """How many series live in a pane.

        The pane handle contains a numeric segment (``...pane.1``), so it cannot be
        pasted into raw JS (``.1`` is a syntax error); resolve it through
        ``Lib.lookup`` instead.
        """
        return int(self.win.read_property(self._pane_handle(index), 'getSeries().length'))

    def pane_price_scale(self, index: int = 0, price_scale_id: str = 'right') -> 'PriceScale':
        """A price scale belonging to a specific pane."""
        return PriceScale(self, price_scale_id, pane_index=index)

    def pane_size(self, index: Optional[int] = None) -> dict:
        """Size of a pane (``{'height': .., 'width': ..}``)."""
        if index is None:
            return self.win.invoke_get(f'{self.id}.chart', 'paneSize')
        return self.win.invoke_get(f'{self.id}.chart', 'paneSize', index)

    def pane_get_htmlelement(self, index: int = 0) -> str:
        """Handle of a pane's ``HTMLElement`` (the node itself cannot cross the bridge)."""
        handle = f'{self.id}.paneElement.{index}'
        self.win.invoke(self._pane_handle(index),
                        'getHTMLElement', store_as=handle)
        return handle

    def pane_series_handle(self, index: int = 0) -> str:
        """Handle of the JS array returned by a pane's ``getSeries()``."""
        handle = f'{self.id}.paneSeries.{index}'
        self.win.invoke(self._pane_handle(index), 'getSeries', store_as=handle)
        return handle

    def pane_move_to(self, index: int, target: int):
        """Move the pane at ``index`` to position ``target``."""
        self.win.invoke(self._pane_handle(index), 'moveTo', target)

    # ------------------------------------------------------------------
    # Chart lifecycle / crosshair
    # ------------------------------------------------------------------

    def remove(self):
        """Destroy the chart and free its resources (terminal operation).

        Also drops the chart's wrapper from the page: ``IChartApi.remove()`` only
        disposes the engine, and the leftover ``.handler`` box kept its old size
        and position (see ``Handler.destroy``) - a closed layout tile then went on
        covering the tiles created next.
        """
        self.win.invoke(f'{self.id}.chart', 'remove')
        self.win.invoke(self.id, 'destroy')

    def version(self) -> str:
        """The lightweight-charts version string (requires a live window)."""
        return self.win.eval_js('LightweightCharts.version()')

    def auto_size_active(self) -> bool:
        return self.win.invoke_get(f'{self.id}.chart', 'autoSizeActive')

    def chart_options(self) -> dict:
        """Read the chart's current (merged) options."""
        return self.win.read_property(f'{self.id}.chart', 'options()')

    def chart_element(self) -> str:
        """Handle of the chart's root ``HTMLDivElement``.

        The DOM node itself cannot cross the bridge, so it is registered under
        ``<chart>.chartElement`` and the handle is returned.
        """
        handle = f'{self.id}.chartElement'
        self.win.invoke(f'{self.id}.chart', 'chartElement', store_as=handle)
        return handle

    def horz_behavior(self) -> str:
        """Handle of the chart's ``IHorzScaleBehavior`` object."""
        handle = f'{self.id}.horzBehavior'
        self.win.invoke(f'{self.id}.chart', 'horzBehaviour', store_as=handle)
        return handle

    def set_crosshair_position(self, price: float, time: TIME, series: Optional['SeriesCommon'] = None):
        """Programmatically place the crosshair."""
        series_handle = ref(f'{series.id}.series') if series is not None else ref(
            f'{self.id}.series')
        self.win.invoke(f'{self.id}.chart', 'setCrosshairPosition',
                        price, self._single_datetime_format(time), series_handle)

    def clear_crosshair_position(self):
        """Remove the crosshair placed by :meth:`set_crosshair_position`."""
        self.win.invoke(f'{self.id}.chart', 'clearCrosshairPosition')

    def create_line(
            self, name: str = '', color: str = 'rgba(214, 237, 255, 0.6)',
            style: LINE_STYLE = 'solid', width: int = 2,
            price_line: bool = True, price_label: bool = True, price_scale_id: Optional[str] = None,
            legend_toggle: bool = True, legend: bool = True
    ) -> Line:
        """
        Creates and returns a Line object.

        ``legend_toggle=False`` leaves the legend row without its eye icon (for
        series whose visibility is controlled elsewhere).
        """
        self._lines.append(Line(self, name, color, style, width, price_line, price_label,
                                price_scale_id, legend_toggle=legend_toggle, legend=legend))
        return self._lines[-1]

    def create_histogram(
            self, name: str = '', color: str = 'rgba(214, 237, 255, 0.6)',
            price_line: bool = True, price_label: bool = True,
            scale_margin_top: float = 0.0, scale_margin_bottom: float = 0.0,
            legend_toggle: bool = True, legend: bool = True
    ) -> Histogram:
        """
        Creates and returns a Histogram object.

        ``legend_toggle=False`` leaves the legend row without its eye icon.
        """
        return Histogram(
            self, name, color, price_line, price_label,
            scale_margin_top, scale_margin_bottom, legend_toggle, legend)

    def create_area(self, name: str = '', line_color: str = 'rgba(214, 237, 255, 0.6)',
                    top_color: Optional[str] = None, bottom_color: Optional[str] = None,
                    line_width: int = 2, price_line: bool = True, price_label: bool = True,
                    price_scale_id: Optional[str] = None, pane_index: Optional[int] = None,
                    legend_toggle: bool = True, legend: bool = True) -> Area:
        """Creates an Area series through the generic bridge."""
        area = Area(self, name, line_color, top_color, bottom_color,
                    line_width, price_line, price_label, price_scale_id,
                    pane_index, legend_toggle, legend)
        self._lines.append(area)
        return area

    def create_bar(self, name: str = '', up_color: str = 'rgba(39, 157, 130, 0.9)',
                   down_color: str = 'rgba(200, 97, 100, 0.9)', price_line: bool = True,
                   price_label: bool = True, price_scale_id: Optional[str] = None,
                   pane_index: Optional[int] = None, legend_toggle: bool = True,
                   legend: bool = True) -> Bar:
        """Creates a Bar series through the generic bridge."""
        bar = Bar(self, name, up_color, down_color, price_line, price_label,
                  price_scale_id, pane_index, legend_toggle, legend)
        self._lines.append(bar)
        return bar

    def create_baseline(self, name: str = '', base_value: Optional[float] = None,
                        top_line_color: str = 'rgba(39, 157, 130, 0.9)',
                        bottom_line_color: str = 'rgba(200, 97, 100, 0.9)',
                        price_line: bool = True, price_label: bool = True,
                        price_scale_id: Optional[str] = None,
                        pane_index: Optional[int] = None,
                        legend_toggle: bool = True, legend: bool = True) -> Baseline:
        """Creates a Baseline series through the generic bridge."""
        baseline = Baseline(self, name, base_value, top_line_color,
                            bottom_line_color, price_line, price_label,
                            price_scale_id, pane_index, legend_toggle, legend)
        self._lines.append(baseline)
        return baseline

    def add_series(self, kind: str, name: str = '', pane_index: Optional[int] = None,
                   legend_toggle: bool = True, legend: bool = True, **options) -> BridgeSeries:
        """Create any built-in series type by name (Line/Area/Bar/Baseline/Candlestick/Histogram).

        `options` are passed through the bridge and snake_cased automatically.
        ``legend_toggle=False`` leaves the legend row without its eye icon.
        """
        series = GenericSeries(self, kind, name, options, pane_index,
                               legend_toggle, legend)
        self._lines.append(series)
        return series

    def add_custom_series(self, name: str = '', pane_index: Optional[Union[int, str]] = None,
                          spec: Optional[dict] = None,
                          legend_toggle: bool = True, legend: bool = True,
                          **options) -> CustomSeries:
        """Create a declarative custom series (see :mod:`pylightcharts.shapes`).

        Pass ``spec`` to override the pane view (``rendererDraw``,
        ``priceValueBuilder``, ``isWhitespace``, ``defaultOptions``,
        ``rendererHitTest``, ``destroy``, ``conflationReducer`` — callback
        names registered with :meth:`register_js_callback`).
        """
        series = CustomSeries(self, name, options, self._resolve_pane(pane_index), spec,
                              legend_toggle, legend)
        self._lines.append(series)
        return series

    def pane_add_series(self, index: int, kind: str, name: str = '', **options) -> BridgeSeries:
        """Create a built-in series inside a specific pane (``IPaneApi.addSeries``)."""
        return self.add_series(kind, name, pane_index=index, **options)

    def pane_add_custom_series(self, index: int, name: str = '', **options) -> CustomSeries:
        """Create a custom series inside a specific pane (``IPaneApi.addCustomSeries``)."""
        return self.add_custom_series(name, pane_index=index, **options)

    def lines(self) -> List[Line]:
        """
        Returns all lines for the chart.
        """
        return self._lines.copy()

    def set_visible_range(self, start_time: TIME, end_time: TIME):
        self.win.invoke(f'{self.id}.timeScale', 'setVisibleRange', {
            'from': pd.to_datetime(start_time).timestamp(),
            'to': pd.to_datetime(end_time).timestamp(),
        })

    def resize(self, width: Optional[float] = None, height: Optional[float] = None):
        """
        Resizes the chart within the window.
        Dimensions should be given as a float between 0 and 1.
        """
        self._width = width if width is not None else self._width
        self._height = height if height is not None else self._height
        self.run_script(f'''
        {self.id}.scale.width = {self._width}
        {self.id}.scale.height = {self._height}
        {self.id}.reSize()
        ''')

    def time_scale(self, right_offset: int = 0, min_bar_spacing: float = 0.5,
                   visible: bool = True, time_visible: bool = True, seconds_visible: bool = False,
                   border_visible: bool = True, border_color: Optional[str] = None):
        """
        Options for the timescale of the chart.
        """
        self.win.invoke(f'{self.id}.timeScale', 'applyOptions', {
            'rightOffset': right_offset,
            'minBarSpacing': min_bar_spacing,
            'visible': visible,
            'timeVisible': time_visible,
            'secondsVisible': seconds_visible,
            'borderVisible': border_visible,
            'borderColor': border_color,
        })

    def layout(self, background_color: str = '#000000', text_color: Optional[str] = None,
               font_size: Optional[int] = None, font_family: Optional[str] = None):
        """
        Global layout options for the chart.
        """
        self.run_script(
            '(document.getElementById("container") || document.body)'
            f'.style.backgroundColor = {json.dumps(background_color)}')
        self.win.invoke(f'{self.id}.chart', 'applyOptions', {'layout': {
            'background': {'color': background_color},
            'textColor': text_color,
            'fontSize': font_size,
            'fontFamily': font_family,
        }})

    def attribution_logo(self, visible: bool = True):
        """Deprecated stub kept for symmetry; use :func:`set_attribution_logo`.

        Lightweight Charts only reads ``layout.attributionLogo`` while a chart is
        being created, so this cannot affect an existing chart - see
        :func:`pylightcharts.abstract.set_attribution_logo`.
        """
        set_attribution_logo(visible)

    def grid(self, vert_enabled: bool = True, horz_enabled: bool = True,
             color: str = 'rgba(29, 30, 38, 5)', style: LINE_STYLE = 'solid'):
        """
        Grid styling for the chart.
        """
        line_style = as_enum(style, LINE_STYLE)
        self.win.invoke(f'{self.id}.chart', 'applyOptions', {'grid': {
            'vertLines': {'visible': vert_enabled, 'color': color, 'style': line_style},
            'horzLines': {'visible': horz_enabled, 'color': color, 'style': line_style},
        }})

    def crosshair(
        self,
        mode: CROSSHAIR_MODE = 'normal',
        vert_visible: bool = True,
        vert_width: int = 1,
        vert_color: Optional[str] = None,
        vert_style: LINE_STYLE = 'large_dashed',
        vert_label_background_color: str = 'rgb(46, 46, 46)',
        horz_visible: bool = True,
        horz_width: int = 1,
        horz_color: Optional[str] = None,
        horz_style: LINE_STYLE = 'large_dashed',
        horz_label_background_color: str = 'rgb(55, 55, 55)'
    ):
        """
        Crosshair formatting for its vertical and horizontal axes.
        """
        self.win.invoke(f'{self.id}.chart', 'applyOptions', {'crosshair': {
            'mode': as_enum(mode, CROSSHAIR_MODE),
            'vertLine': {
                'visible': vert_visible,
                'width': vert_width,
                'color': vert_color,
                'style': as_enum(vert_style, LINE_STYLE),
                'labelBackgroundColor': vert_label_background_color,
            },
            'horzLine': {
                'visible': horz_visible,
                'width': horz_width,
                'color': horz_color,
                'style': as_enum(horz_style, LINE_STYLE),
                'labelBackgroundColor': horz_label_background_color,
            },
        }})

    def watermark(self, text: str, font_size: int = 44, color: str = 'rgba(180, 180, 200, 0.5)',
                  handle: Optional[str] = None):
        """
        Adds a watermark to the chart.
        """
        # lightweight-charts v5: watermark is a pane primitive, not a chart option.
        handle_js = json.dumps(handle) if handle else 'null'
        # ★ 结尾必须补 ``\nnull``：``setWatermark`` 返回的是活的 pane primitive
        #   （``TextWatermark`` 对象，内部有循环引用），而 PyQt6 的
        #   ``runJavaScript(script)`` 即使不传回调，也会把**最后一个表达式的值**
        #   转成 QVariant —— 转一个 LWC 原生对象会把渲染进程卡死（实测：之后所有
        #   ``runJavaScript`` 全部返回 None，图上只剩坐标轴、K 线再也不画 ✗）。
        #   补 ``null`` 后整段求值成 ``null``，但水印照常创建 ✓
        #   （与 :meth:`Window.invoke` / ``Pane._invoke_assign`` 同一个坑）。
        self.run_script(
            f'{self.id}.setWatermark({json.dumps(text)}, {int(font_size)}, '
            f'{json.dumps(color)}, {handle_js})\nnull'
        )

    def text_watermark_plugin(self, text: str = '', font_size: int = 44,
                              color: str = 'rgba(180, 180, 200, 0.5)',
                              handle: Optional[str] = None) -> 'TextWatermarkPlugin':
        """Create/replace the text watermark and return a :class:`TextWatermarkPlugin`."""
        handle = handle or f'{self.id}.textWatermark'
        self.watermark(text, font_size, color, handle=handle)
        return TextWatermarkPlugin(self.win, handle)

    def image_watermark_plugin(self, image: str, max_width: Optional[int] = None,
                               max_height: Optional[int] = None,
                               pane_index: int = 0) -> 'ImageWatermarkPlugin':
        """Create an image watermark and return an :class:`ImageWatermarkPlugin`."""
        handle = self.create_image_watermark(
            image, max_width, max_height, pane_index)
        return ImageWatermarkPlugin(self.win, handle)

    def legend(self, visible: bool = False, ohlc: bool = True, percent: bool = True, lines: bool = True,
               color: str = 'rgb(191, 195, 203)', font_size: int = 11, font_family: str = 'Monaco',
               text: str = '', color_based_on_candle: bool = False,
               text_visible: bool = True):
        """
        Configures the legend of the chart.

        ``text_visible=False`` hides the free ``text`` row (the title line above
        the OHLC readout) - the main K-line row then starts at the date, which is
        what miniqt wants.
        """
        self._legend_options = None if not visible else {
            'visible': True, 'ohlc': ohlc, 'percent': percent, 'lines': lines,
            'color': color, 'font_size': font_size,
            'font_family': font_family, 'text': text,
            'color_based_on_candle': color_based_on_candle,
            'text_visible': text_visible,
        }
        l_id = f'{self.id}.legend'
        if not visible:
            self.run_script(f'''
            {l_id}.div.style.display = "none"
            {l_id}.ohlcEnabled = false
            {l_id}.percentEnabled = false
            {l_id}.linesEnabled = false
            ''')
            return
        self.run_script(f'''
        {l_id}.div.style.display = 'flex'
        {l_id}.ohlcEnabled = {jbool(ohlc)}
        {l_id}.percentEnabled = {jbool(percent)}
        {l_id}.linesEnabled = {jbool(lines)}
        {l_id}.colorBasedOnCandle = {jbool(color_based_on_candle)}
        {l_id}.div.style.color = '{color}'
        {l_id}.color = '{color}'
        {l_id}.div.style.fontSize = '{font_size}px'
        {l_id}.div.style.fontFamily = '{font_family}'
        {l_id}.text.innerText = '{text}'
        {l_id}.text.style.display = {jbool(text_visible)} ? '' : 'none'
        ''')

    def enable_legend_collapse(self):
        """Add the collapse/expand button below the indicator legend rows.

        The button hides/shows every indicator row (TradingView's ``∨ N``); it
        is drawn by the JS legend (``legend.enableCollapse``), so both the Qt and
        the browser hosts get it. Idempotent.
        """
        self.run_script(f'''
            (function() {{
                var legend = {self.id}.legend;
                if (legend && legend.enableCollapse) legend.enableCollapse();
            }})()
        ''')
        return self

    def spinner(self, visible: bool):
        """Show or hide the loading spinner (``Lib.Handler.setSpinner``)."""
        self.win.invoke(self.id, 'setSpinner', visible)

    def hotkey(self, modifier_key: Literal['ctrl', 'alt', 'shift', 'meta', None],
               keys: Union[str, tuple, int], func: Callable):
        if not isinstance(keys, tuple):
            keys = (keys,)
        for key in keys:
            key = str(key)
            if key.isalnum() and len(key) == 1:
                key_code = f'Digit{key}' if key.isdigit(
                ) else f'Key{key.upper()}'
                key_condition = f'event.code === "{key_code}"'
            else:
                key_condition = f'event.key === "{key}"'
            if modifier_key is not None:
                key_condition += f'&& event.{modifier_key}Key'

            self.run_script(f'''
                    {self.id}.commandFunctions.unshift((event) => {{
                        if ({key_condition}) {{
                            event.preventDefault()
                            window.callbackFunction(`{modifier_key, keys}_~_{key}`)
                            return true
                        }}
                        else return false
                    }})''')
        self.win.handlers[f'{modifier_key, keys}'] = func

    def create_table(
        self,
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
    ) -> Table:
        args = locals()
        del args['self']
        return self.win.create_table(*args.values())

    def create_html_panel(self, **options) -> 'HtmlPanel':
        """整页 HTML 面板（报表页）：盖在本图表的画布上，可滚动、吃主题色。

        ``panel.set_html('<h2>…</h2>')`` 整体替换内容，``panel.show()`` /
        ``panel.hide()`` 切换显示；颜色用根 CSS 变量，跟着 `chart.theme()` 自动换。
        """
        from .table import HtmlPanel
        return HtmlPanel(self, **options)

    def screenshot(self) -> bytes:
        """
        Takes a screenshot. This method can only be used after the chart window is visible.
        :return: a bytes object containing a screenshot of the chart.
        """
        expression = f'{self.id}.chart.takeScreenshot().toDataURL()'
        try:
            serial_data = self.win.run_script_and_get(expression)
        except BridgeError:
            # panes created just before the first paint have no layout yet, which
            # makes the engine's gradient stops non-finite; one short retry is enough
            time.sleep(0.2)
            serial_data = self.win.run_script_and_get(expression)
        return b64decode(serial_data.split(',')[1])

    def create_subchart(self, position: FLOAT = 'left', width: float = 0.5, height: float = 0.5,
                        sync: Optional[Union[str, bool]] = None, scale_candles_only: bool = False,
                        sync_crosshairs_only: bool = False,
                        toolbox: bool = False) -> 'AbstractChart':
        if sync is True:
            sync = self.id
        args = locals()
        del args['self']
        return self.win.create_subchart(*args.values())
