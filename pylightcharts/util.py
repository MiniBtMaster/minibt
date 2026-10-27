import asyncio
import base64 as _base64
import json
import math
from datetime import datetime
from random import choices
from typing import Literal, Union
import numpy as np
from numpy import isin
import pandas as pd


def infer_time_unit(values) -> str:
    """`'ns'` / `'us'` / `'ms'` / `'s'` for a numeric epoch time axis.

    Every chart of this package keeps its ``time`` column in **epoch seconds**
    (that is what ``candle_data`` / ``series.data`` hold), while hand-written
    code often passes milliseconds, and pandas' own ``int64`` times are
    nanoseconds. Without a unit, ``pd.to_datetime`` reads a bare number as
    nanoseconds - so passing ``chart.candle_data['time']`` back in landed in 1970.
    The magnitude is the only hint available, and it is unambiguous for real
    epoch values.
    """
    if len(values) == 0:
        return 's'
    magnitude = max(abs(float(pd.Series(values).max())),
                    abs(float(pd.Series(values).min())))
    return ('ns' if magnitude >= 1e17 else
            'us' if magnitude >= 1e14 else
            'ms' if magnitude >= 1e11 else 's')


class Pane:
    def __init__(self, window):
        from pylightcharts import Window
        self.win: Window = window
        self.run_script = window.run_script
        self.bulk_run = window.bulk_run
        if hasattr(self, 'id'):
            return
        self.id = Window._id_gen.generate()

    def _invoke(self, method: str, *args):
        """Call `self.id.method(*args)` in the webview through the generic bridge."""
        self.win.invoke(self.id, method, *args)

    def _invoke_get(self, method: str, *args):
        """Like `_invoke` but returns the (JSON-serializable) result."""
        return self.win.invoke_get(self.id, method, *args)

    def _invoke_assign(self, var: str, method: str, *args):
        """Call `self.id.method(*args)` and assign the result to the JS variable `var`.

        The trailing `null` matters: PyQt6 的 ``runJavaScript(script)`` 即使不传
        回调，也会尝试把**最后一个表达式的值**转成 ``QVariant`` —— 这个值是一个
        活的 Lightweight Charts 序列（循环引用 / 原生对象）时，渲染进程会卡死
        （``add_series`` / ``add_custom_series`` 实测必现 ✗）。把 ``null`` 放到
        末尾就让整段脚本求值成 ``null``（和 ``Line`` 构造里的 ``null`` 同理 ✓）。
        """
        self.run_script(f'{var} = {js_call(self.id, method, args)}\nnull')


class IDGen(list):
    ascii = 'abcdefghijklmnopqrstuvwxyz'

    def generate(self) -> str:
        var = ''.join(choices(self.ascii, k=8))
        if var not in self:
            self.append(var)
            return f'window.{var}'
        self.generate()


def parse_event_message(window, string):
    name, args = string.split('_~_')
    args = args.split(';;;')
    # Unknown names (e.g. a table cell dragged without a callback) are ignored
    # instead of raising KeyError and killing the show() event loop.
    func = window.handlers.get(name)
    return func, args


def js_data(data: Union[pd.DataFrame, pd.Series]):
    if isinstance(data, pd.DataFrame):
        d = data.to_dict(orient='records')
        filtered_records = [{k: v for k, v in record.items() if v is not None and not pd.isna(v)} for record in d]
    else:
        d = data.to_dict()
        filtered_records = {k: v for k, v in d.items()}
    # no `indent`: the payload goes straight through evaluate_js, whitespace is pure overhead
    return json.dumps(_sanitize(filtered_records, camelize=False), allow_nan=False, separators=(',', ':'))


def _camelize_key(key: str) -> str:
    return snake_to_camel(key) if '_' in key else key


def _sanitize(value, camelize: bool = True):
    """Convert a python value into something `json.dumps` can emit as JS.

    - numpy / pandas scalars are unwrapped via `.item()`
    - NaN / inf become dropped dict entries or null
    - dict keys are snake_cased into camelCase (lightweight-charts option style)
    - `None` values inside dicts are dropped so JS keeps its defaults
    """
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, str):
        return value
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else value
    if isinstance(value, pd.DataFrame):
        return _sanitize(value.to_dict(orient='records'), camelize)
    if isinstance(value, pd.Series):
        return _sanitize(value.to_dict(), camelize)
    if isinstance(value, (datetime, pd.Timestamp)):
        return int(value.timestamp())
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            sanitized = _sanitize(v, camelize)
            # drop None/NaN entries so JS keeps its own defaults
            if sanitized is None:
                continue
            key = _camelize_key(str(k)) if camelize else str(k)
            out[key] = sanitized
        return out
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(v, camelize) for v in value]
    # numpy / pandas scalars (np.int64, np.float64, pd.NA, ...)
    if hasattr(value, 'item'):
        try:
            return _sanitize(value.item(), camelize)
        except (ValueError, AttributeError):
            pass
    if value is pd.NaT:
        return None
    return str(value)


def js_value(obj) -> str:
    """Serialize a python object into a JS literal expression (camelCased keys)."""
    return json.dumps(_sanitize(obj), allow_nan=False, separators=(',', ':'))


def js_raw(obj) -> str:
    """Serialize into a JS literal **without** camelCasing dict keys.

    Panel data (DataGrid rows / columns) uses the caller's own field names, so
    ``open_interest`` must stay ``open_interest`` - unlike chart options, which
    follow the Lightweight Charts camelCase style and go through
    :func:`js_value`.
    """
    return json.dumps(_sanitize(obj, camelize=False), allow_nan=False,
                      separators=(',', ':'))


class BridgeError(RuntimeError):
    """Raised when a script evaluated inside the webview throws."""


def js_call(handle: str, method: str, args, store_as: str = None) -> str:
    """Build a `Lib.invoke(handle, method, args[, storeAs])` expression for the bridge."""
    base = f'Lib.invoke({json.dumps(handle)}, {json.dumps(method)}, {js_value(list(args))}'
    if store_as is not None:
        base += f', {json.dumps(store_as)}'
    return base + ')'


def ref(handle: str) -> dict:
    """Reference a JS handle so it can be passed as an argument.

    The bridge resolves `{"$ref": handle}` into the live JS object, which makes
    APIs that take objects (attachPrimitive, etc.) usable from python.
    """
    return {'$ref': handle}


#: DataFrames at or above this many rows are sent as a binary buffer instead of
#: JSON source (much cheaper to transfer and to rebuild in the browser).
BINARY_DATA_THRESHOLD = 2000


def js_binary_data(data, columns=None) -> str:
    """Encode a DataFrame/Series as a `Lib.decodeData(...)` expression.

    Numeric columns travel as a base64 column-major Float64 buffer, string
    columns (e.g. per-bar ``color``) travel as a small JSON object.
    """
    if isinstance(data, pd.Series):
        data = data.to_frame()
    if columns is None:
        columns = [c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])]
    string_columns = [c for c in data.columns if c not in columns]

    row_count = len(data)
    matrix = np.empty((len(columns), row_count), dtype='<f8')
    for index, column in enumerate(columns):
        matrix[index] = pd.to_numeric(data[column], errors='coerce').to_numpy(dtype='float64')
    payload = _base64.b64encode(matrix.tobytes(order='C')).decode('ascii')

    call = f'Lib.decodeData({json.dumps(payload)}, {json.dumps(list(columns))}'
    if string_columns:
        strings = {
            column: [None if pd.isna(value) else str(value) for value in data[column]]
            for column in string_columns
        }
        call += f', {json.dumps(strings)}'
    return call + ')'


def _needs_json(data) -> bool:
    """表里有 **dict / list 列**（如 LWC 的 ``customValues``）吗 ✓。

    ``js_binary_data`` 会把非数值列一律 ``str()`` 成字符串 ✗（dict 列会变成
    "{'volume': 1.0}" 这种字符串，引擎根本读不到 ✗），所以这类表**必须走
    JSON 路径** ✓。
    """
    try:
        frame = data.to_frame() if isinstance(data, pd.Series) else data
        for column in frame.columns:
            if frame[column].dtype != object:
                continue
            sample = frame[column].dropna()
            if len(sample) and isinstance(sample.iloc[0], (dict, list, tuple)):
                return True
    except Exception:                                            # noqa: BLE001
        return False
    return False


def encode_series_data(data) -> str:
    """Pick the cheapest encoding for a payload of bars.

    带 NaN/缺失值的序列必须走 JSON 路径：`js_data` 会把缺失键丢掉（引擎按
    “空白点”处理 -> 断点），而 base64 浮点块会把 NaN 原样下发，引擎会直接
    连过去（竖直线/直连）。
    """
    if len(data) >= BINARY_DATA_THRESHOLD and not _has_missing(data) \
            and not _needs_json(data):
        return js_binary_data(data)
    return js_data(data)


def _has_missing(data) -> bool:
    """序列里有没有 NaN/None/**inf**。

    ★ 必须把 inf 也算缺失：base64 浮点块会把 inf 原样下发成 JS ``Infinity``，
    使 Lightweight Charts 的自动缩放/图例读数出错 ✗（曾导致 supertrend 的
    ``long``/``short`` 线异常）。JSON 路径的 :func:`_sanitize` 会把 inf 变 null，
    所以只要判出“有 inf”就会改走 JSON 路径 ✓。
    """
    try:
        frame = data.to_frame() if isinstance(data, pd.Series) else data
        numeric = frame.select_dtypes(include=['number'])
        if numeric.shape[1] and not np.isfinite(
                numeric.to_numpy(dtype=float)).all():
            return True
        return bool(frame.isna().to_numpy().any())
    except Exception:
        try:
            return bool(data.isna().to_numpy().any())
        except Exception:
            return False


def snake_to_camel(s: str):
    components = s.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

def js_json(d: dict):
    filtered_dict = {}
    for key, val in d.items():
        if key in ('self') or val in (None,):
            continue
        if '_' in key:
            key = snake_to_camel(key)
        filtered_dict[key] = val
    return f"JSON.parse('{json.dumps(filtered_dict)}')"


def jbool(b: bool): return 'true' if b is True else 'false' if b is False else None


LINE_STYLE = Literal['solid', 'dotted', 'dashed', 'large_dashed', 'sparse_dotted']

MARKER_POSITION = Literal['above', 'below', 'inside']

MARKER_SHAPE = Literal['arrow_up', 'arrow_down', 'circle', 'square']

CROSSHAIR_MODE = Literal['normal', 'magnet', 'hidden']

PRICE_SCALE_MODE = Literal['normal', 'logarithmic', 'percentage', 'index100']

TIME = Union[datetime, pd.Timestamp, str, float]

NUM = Union[float, int]

FLOAT = Literal['left', 'right', 'top', 'bottom']


def as_enum(value, string_types):
    types = string_types.__args__
    return -1 if value not in types else types.index(value)


def marker_shape(shape: MARKER_SHAPE):
    return {
        'arrow_up': 'arrowUp',
        'arrow_down': 'arrowDown',
        'arrowUp': 'arrowUp',       # tolerate the underlying v5 vocabulary
        'arrowDown': 'arrowDown',
    }.get(shape) or shape


def marker_position(p: MARKER_POSITION):
    return {
        'above': 'aboveBar',
        'below': 'belowBar',
        'inside': 'inBar',
        'aboveBar': 'aboveBar',     # tolerate the underlying v5 vocabulary
        'belowBar': 'belowBar',
        'inBar': 'inBar',
    }.get(p)


class Emitter:
    def __init__(self):
        self._callable = None

    def __iadd__(self, other):
        self._callable = other
        return self

    def _emit(self, *args):
        if self._callable:
            if asyncio.iscoroutinefunction(self._callable):
                asyncio.create_task(self._callable(*args))
            else:
                self._callable(*args)


class JSEmitter:
    # `wrapper` stays the 4th positional argument so code written against
    # lightweight-charts-python keeps working; `on_delete` is keyword-only.
    def __init__(self, chart, name, on_iadd, wrapper=None, *, on_delete=None):
        self._on_iadd = on_iadd
        self._on_delete = on_delete
        self._chart = chart
        self._name = name
        self._wrapper = wrapper

    def __iadd__(self, other):
        def final_wrapper(*arg):
            other(self._chart, *arg) if not self._wrapper else self._wrapper(other, self._chart, *arg)
        async def final_async_wrapper(*arg):
            await other(self._chart, *arg) if not self._wrapper else await self._wrapper(other, self._chart, *arg)

        self._chart.win.handlers[self._name] = final_async_wrapper if asyncio.iscoroutinefunction(other) else final_wrapper
        self._on_iadd(other)
        return self

    def unsubscribe(self):
        """Remove both the JS subscription and the python callback."""
        if self._on_delete is not None:
            self._on_delete()
        self._chart.win.handlers.pop(self._name, None)


class Events:
    def __init__(self, chart):
        self.new_bar = Emitter()
        salt = chart.id[chart.id.index('.') + 1:]

        def _float(value):
            # JS may hand over null/undefined/NaN for a missing coordinate.
            return None if value in ('null', 'undefined', 'NaN', '') else float(value)

        self.search = JSEmitter(
            chart, f'search{chart.id}',
            lambda o: chart.run_script(f'''
            Lib.Handler.makeSpinner({chart.id})
            {chart.id}.search = Lib.Handler.makeSearchBox({chart.id})
            '''),
        )
        self.range_change = JSEmitter(
            chart, f'range_change{salt}',
            lambda o: chart.run_script(f'''
            window.checkLogicalRange{salt} = (logical) => {{
                {chart.id}.chart.timeScale().unsubscribeVisibleLogicalRangeChange(window.checkLogicalRange{salt})

                let barsInfo = {chart.id}.series.barsInLogicalRange(logical)
                if (barsInfo) window.callbackFunction(`range_change{salt}_~_${{barsInfo.barsBefore}};;;${{barsInfo.barsAfter}}`)

                setTimeout(() => {chart.id}.chart.timeScale().subscribeVisibleLogicalRangeChange(window.checkLogicalRange{salt}), 50)
            }}
            {chart.id}.chart.timeScale().subscribeVisibleLogicalRangeChange(window.checkLogicalRange{salt})
            '''),
            on_delete=lambda: chart.run_script(
                f'{chart.id}.chart.timeScale().unsubscribeVisibleLogicalRangeChange(window.checkLogicalRange{salt})'),
            wrapper=lambda o, c, *arg: o(c, *[float(a) for a in arg]),
        )

        self.click = JSEmitter(
            chart, f'subscribe_click{salt}',
            lambda o: chart.run_script(f'''
            if (window.clickHandler{salt}) {chart.id}.removeClickListener(window.clickHandler{salt})
            window.clickHandler{salt} = (param) => {{
                if (!param.point) return;
                const time = {chart.id}.chart.timeScale().coordinateToTime(param.point.x)
                const price = {chart.id}.series.coordinateToPrice(param.point.y);
                window.callbackFunction(`subscribe_click{salt}_~_${{time}};;;${{price}}`)
            }}
            {chart.id}.addClickListener(window.clickHandler{salt})
            '''),
            on_delete=lambda: chart.run_script(
                f'if (window.clickHandler{salt}) {chart.id}.removeClickListener(window.clickHandler{salt})'),
            wrapper=lambda func, c, *args: func(c, *[_float(a) for a in args]),
        )

        self.dblclick = JSEmitter(
            chart, f'subscribe_dblclick{salt}',
            lambda o: chart.run_script(f'''
            if (window.dblClickHandler{salt}) {chart.id}.removeDblClickListener(window.dblClickHandler{salt})
            window.dblClickHandler{salt} = (param) => {{
                if (!param.point) return;
                const time = {chart.id}.chart.timeScale().coordinateToTime(param.point.x)
                const price = {chart.id}.series.coordinateToPrice(param.point.y);
                window.callbackFunction(`subscribe_dblclick{salt}_~_${{time}};;;${{price}}`)
            }}
            {chart.id}.addDblClickListener(window.dblClickHandler{salt})
            '''),
            on_delete=lambda: chart.run_script(
                f'if (window.dblClickHandler{salt}) {chart.id}.removeDblClickListener(window.dblClickHandler{salt})'),
            wrapper=lambda func, c, *args: func(c, *[_float(a) for a in args]),
        )

        self.crosshair_move = JSEmitter(
            chart, f'crosshair_move{salt}',
            lambda o: chart.run_script(f'''
            if (window.crosshairHandler{salt}) {chart.id}.removeCrosshairListener(window.crosshairHandler{salt})
            window.crosshairHandler{salt} = (param) => {{
                const time = typeof param.time === 'number' ? param.time : ''
                const price = param.point ? {chart.id}.series.coordinateToPrice(param.point.y) : null
                window.callbackFunction(`crosshair_move{salt}_~_${{time}};;;${{price}}`)
            }}
            {chart.id}.addCrosshairListener(window.crosshairHandler{salt})
            '''),
            on_delete=lambda: chart.run_script(
                f'if (window.crosshairHandler{salt}) {chart.id}.removeCrosshairListener(window.crosshairHandler{salt})'),
            wrapper=lambda func, c, *args: func(c, *[_float(a) for a in args]),
        )

        # Visible *time* range (range_change above reports logical bars).
        self.visible_time_range_change = JSEmitter(
            chart, f'time_range_change{salt}',
            lambda o: chart.run_script(f'''
            window.timeRangeHandler{salt} = (range) => {{
                if (!range) return;
                window.callbackFunction(`time_range_change{salt}_~_${{range.from}};;;${{range.to}}`)
            }}
            {chart.id}.chart.timeScale().subscribeVisibleTimeRangeChange(window.timeRangeHandler{salt})
            '''),
            on_delete=lambda: chart.run_script(
                f'{chart.id}.chart.timeScale().unsubscribeVisibleTimeRangeChange(window.timeRangeHandler{salt})'),
            wrapper=lambda func, c, *args: func(c, *args),
        )

        # Time-scale size (width / height) changes.
        # Upstream signature: (width: number, height: number) => void
        self.size_change = JSEmitter(
            chart, f'size_change{salt}',
            lambda o: chart.run_script(f'''
            window.sizeChangeHandler{salt} = (width, height) => {{
                window.callbackFunction(`size_change{salt}_~_${{width}};;;${{height}}`)
            }}
            {chart.id}.chart.timeScale().subscribeSizeChange(window.sizeChangeHandler{salt})
            '''),
            on_delete=lambda: chart.run_script(
                f'{chart.id}.chart.timeScale().unsubscribeSizeChange(window.sizeChangeHandler{salt})'),
            wrapper=lambda func, c, *args: func(c, *[_float(a) for a in args]),
        )

class BulkRunScript:
    def __init__(self, script_func):
        self.enabled = False
        self.scripts = []
        self.script_func = script_func

    def __enter__(self):
        self.enabled = True

    def __exit__(self, *args):
        self.enabled = False
        # 用 ``;`` 把每条脚本隔开：脚本之间**不能靠自动分号插入（ASI）**连接。
        # 有些脚本以 ``null``/``)`` 结尾且不带分号（如 ``createLineSeries`` 的
        # ``null``，见 ``Pane._invoke_assign``），紧接着的 ``remove_legend_row``
        # 又是以 ``(`` 开头的 IIFE —— 拼在一起会变成 ``null(function(){...})()``，
        # 运行时报 ``null is not a function``，**整批后续脚本（含 setData）全被
        # 吞掉**，于是 ``legend=False`` 的指标线永远画不出来 ✗。显式分号断开即可 ✓。
        self.script_func('\n;\n'.join(self.scripts))
        self.scripts = []

    def add_script(self, script):
        self.scripts.append(script)
