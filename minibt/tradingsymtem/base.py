"""交易系统指标基类：**只出交易信号、不出指标线**（用户 2026-11-22）

设计目标（和东方财富「公式管理器 → 系统公式 → 交易系统」一样）：

* 图表上**只看到买卖箭头**，看不到指标线（值序列不外露）；
* 底层数值优先用 **vector-ta**（Rust，快）→ 没有就 **tulip-rs** → 最后 `pta_rs`；
* 信号统一成 `long_signal` / `short_signal`（`1 / 0 / -1`）——框架会自动把它们
  当信号线（`SIGNAL_Str`），画箭头、给技术分析 / 预警复用 ✓

写一个新交易系统只要三步（也可以直接用 `tradingsystem.py` 里的规则表）：

```python
class MyTrend(TradingSystemBase):
    params = dict(fast=5, slow=20)

    def value(self):
        return self.lib('sma', length=self.params.slow)

    def rule(self, value):
        return self.cross(self.lib('sma', length=self.params.fast), value)
```
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators.core import BtIndicator

__all__ = [
    'LIB_ORDER',
    'LIB_TABLE',
    'TradingSystemBase',
    'TradingSystemCategory',
    'compute_raw',
    'compute_value',
    'split_lines',
]

#: 底层库优先级（用户要求：vector-ta → tulip-rs → pta_rs）✓
LIB_ORDER = ('vta', 'tulip', 'pta_rs')

#: 指标名 → 各库的调用方式
#:
#: * ``vta``：`vector_ta.<func>(*data, **params, **fixed)`。
#:   `data` 是**按位置**传的 K 线列；`params` 把本交易系统的参数名映射到
#:   vector-ta 的关键字参数名；`fixed` 是写死的默认（如 MACD 的 `ma_type`）✓
#: * ``tulip``：`tulip_rs.indicators.<func>.indicator([输入], [选项])`。
#:   `options` 里的名字是**本交易系统的参数名**（只取数值，和 tulip 的
#:   `info()['options']` 顺序一一对应）✓
#: * ``pta_rs``：`data.pta_rs.<func>(**params)`（兜底；参数名与 pandas_ta 一致）✓
#:
#: ⚠ 每个库的输出**行序**不一样：vector-ta / tulip-rs 返回 ``(输出数, 长度)``，
#: pta_rs 的 DataFrame 是 ``(长度, 输出数)``。`split_lines()` 会统一转成
#: 与数据等长的 `pd.Series` 列表，**方向自适应** ✓。
LIB_TABLE: dict[str, dict] = {
    # ------------------------------------------------------------------ 均线
    'sma': {
        'vta': {'func': 'sma', 'data': ['close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'sma', 'data': ['close'], 'options': ['length']},
        'pta_rs': {'func': 'sma', 'params': {'length': 'length'}},
    },
    'ema': {
        'vta': {'func': 'ema', 'data': ['close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'ema', 'data': ['close'], 'options': ['length']},
        'pta_rs': {'func': 'ema', 'params': {'length': 'length'}},
    },
    'wma': {
        'vta': {'func': 'wma', 'data': ['close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'wma', 'data': ['close'], 'options': ['length']},
    },
    # ------------------------------------------------------------------ 通道
    'bbands': {
        'vta': {'func': 'bollinger_bands', 'data': ['close'],
                'params': {'period': 'length', 'devup': 'std',
                           'devdn': 'std'},
                'fixed': {'matype': 'sma', 'devtype': 0}},
        'tulip': {'func': 'bbands', 'data': ['close'],
                  'options': ['length', 'std']},
        'pta_rs': {'func': 'bbands', 'params': {'length': 'length',
                                               'std': 'std'}},
    },
    'donchian': {
        'vta': {'func': 'donchian', 'data': ['high', 'low'],
                'params': {'period': 'length'}},
        'pta_rs': {'func': 'donchian', 'params': {'lower_length': 'length',
                                                 'upper_length': 'length'}},
    },
    'keltner': {
        'vta': {'func': 'keltner',
                'data': ['high', 'low', 'close', 'close'],
                'params': {'period': 'period', 'multiplier': 'multiplier'},
                'fixed': {'ma_type': 'ema'}},
        'pta_rs': {'func': 'kc', 'params': {'length': 'period',
                                           'scalar': 'multiplier'}},
    },
    # ------------------------------------------------------------------ 动量
    'rsi': {
        'vta': {'func': 'rsi', 'data': ['close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'rsi', 'data': ['close'], 'options': ['length']},
        'pta_rs': {'func': 'rsi', 'params': {'length': 'length'}},
    },
    'roc': {
        'vta': {'func': 'roc', 'data': ['close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'roc', 'data': ['close'], 'options': ['length']},
        'pta_rs': {'func': 'roc', 'params': {'length': 'length'}},
    },
    'macd': {
        'vta': {'func': 'macd', 'data': ['close'],
                'params': {'fast_period': 'fast', 'slow_period': 'slow',
                           'signal_period': 'signal'},
                'fixed': {'ma_type': 'ema'}},
        'tulip': {'func': 'macd', 'data': ['close'],
                  'options': ['fast', 'slow', 'signal']},
        'pta_rs': {'func': 'macd', 'params': {'fast': 'fast',
                                             'slow': 'slow',
                                             'signal': 'signal'}},
    },
    'stoch': {
        'vta': {'func': 'stoch', 'data': ['high', 'low', 'close'],
                'params': {'fastk_period': 'k', 'slowk_period': 'd',
                           'slowd_period': 'd'},
                'fixed': {'slowk_ma_type': 'sma', 'slowd_ma_type': 'sma'}},
        'tulip': {'func': 'stoch', 'data': ['high', 'low', 'close'],
                  'options': ['k', 'd', 'd']},
        'pta_rs': {'func': 'stoch', 'params': {'k': 'k', 'd': 'd',
                                              'smooth_k': 'd'}},
    },
    'cci': {
        'vta': {'func': 'cci', 'data': ['close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'cci', 'data': ['high', 'low', 'close'],
                  'options': ['length']},
    },
    'mfi': {
        'vta': {'func': 'mfi', 'data': ['typical_price', 'volume'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'mfi', 'data': ['high', 'low', 'close', 'volume'],
                  'options': ['length']},
        'pta_rs': {'func': 'mfi', 'params': {'length': 'length'}},
    },
    'willr': {
        'vta': {'func': 'willr', 'data': ['high', 'low', 'close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'willr', 'data': ['high', 'low', 'close'],
                  'options': ['length']},
    },
    'kdj': {
        'vta': {'func': 'kdj', 'data': ['high', 'low', 'close'],
                'params': {'fast_k_period': 'period',
                           'slow_k_period': 'signal',
                           'slow_d_period': 'signal'},
                'fixed': {'slow_k_ma_type': 'sma', 'slow_d_ma_type': 'sma'}},
        'pta_rs': {'func': 'kdj', 'params': {'length': 'period',
                                            'signal': 'signal'}},
    },
    # ------------------------------------------------------------------ 趋势
    'adx': {
        'vta': {'func': 'adx', 'data': ['high', 'low', 'close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'adx', 'data': ['high', 'low', 'close'],
                  'options': ['length']},
        'pta_rs': {'func': 'adx', 'params': {'length': 'length',
                                            'signal_length': 'length'}},
    },
    'di': {
        'vta': {'func': 'di', 'data': ['high', 'low', 'close'],
                'params': {'period': 'length'}},
    },
    'aroon': {
        'vta': {'func': 'aroon', 'data': ['high', 'low'],
                'params': {'length': 'length'}},
        'tulip': {'func': 'aroon', 'data': ['high', 'low'],
                  'options': ['length']},
    },
    'supertrend': {
        'vta': {'func': 'supertrend', 'data': ['high', 'low', 'close'],
                'params': {'period': 'period', 'factor': 'multiplier'}},
        'tulip': {'func': 'supertrend', 'data': ['high', 'low', 'close'],
                  'options': ['period', 'multiplier']},
    },
    'kama': {
        'vta': {'func': 'kama', 'data': ['close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'kama', 'data': ['close'], 'options': ['length']},
    },
    'psar': {
        'vta': {'func': 'sar', 'data': ['high', 'low'],
                'params': {'acceleration': 'acceleration',
                           'maximum': 'maximum'}},
        'tulip': {'func': 'psar', 'data': ['high', 'low'],
                  'options': ['acceleration', 'maximum']},
    },
    'trix': {
        'vta': {'func': 'trix', 'data': ['close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'trix', 'data': ['close'], 'options': ['length']},
        'pta_rs': {'func': 'trix', 'params': {'length': 'length',
                                             'signal': 'signal'}},
    },
    # ------------------------------------------------------------------ 波动
    'atr': {
        'vta': {'func': 'atr', 'data': ['high', 'low', 'close'],
                'params': {'length': 'length'}},
        'tulip': {'func': 'atr', 'data': ['high', 'low', 'close'],
                  'options': ['length']},
        'pta_rs': {'func': 'atr', 'params': {'length': 'length'}},
    },
    'zscore': {
        'vta': {'func': 'zscore', 'data': ['close'],
                'params': {'period': 'length'},
                'fixed': {'ma_type': 'sma', 'nbdev': 1.0, 'devtype': 0}},
    },
    # ------------------------------------------------------------------ 量价
    'obv': {
        'vta': {'func': 'obv', 'data': ['close', 'volume']},
        'tulip': {'func': 'obv', 'data': ['close', 'volume'], 'options': []},
        'pta_rs': {'func': 'obv', 'params': {}},
    },
    'vwap': {
        'vta': {'func': 'vwap',
                'data': ['timestamp', 'volume', 'close']},
        'tulip': {'func': 'vwap',
                  'data': ['high', 'low', 'close', 'volume'], 'options': []},
        'pta_rs': {'func': 'vwap', 'params': {}},
    },
    # ------------------------------------------------------------------ 周期/表现
    'dpo': {
        'vta': {'func': 'dpo', 'data': ['close'],
                'params': {'period': 'length'}},
        'tulip': {'func': 'dpo', 'data': ['close'], 'options': ['length']},
    },
    'apo': {
        'vta': {'func': 'apo', 'data': ['close'],
                'params': {'short_period': 'fast', 'long_period': 'slow'}},
        'tulip': {'func': 'apo', 'data': ['close'],
                  'options': ['fast', 'slow']},
    },
    'ao': {
        'vta': {'func': 'ao', 'data': ['high', 'low'],
                'params': {'short_period': 'fast', 'long_period': 'slow'}},
        'tulip': {'func': 'ao', 'data': ['high', 'low'], 'options': []},
        'pta_rs': {'func': 'ao', 'params': {'fast': 'fast', 'slow': 'slow'}},
    },
    'ultosc': {
        'vta': {'func': 'ultosc', 'data': ['high', 'low', 'close'],
                'fixed': {'timeperiod1': 7, 'timeperiod2': 14,
                          'timeperiod3': 28}},
        'tulip': {'func': 'ultosc', 'data': ['high', 'low', 'close'],
                  'options': []},
    },
    'ad': {
        'vta': {'func': 'ad', 'data': ['high', 'low', 'close', 'volume']},
        'tulip': {'func': 'ad', 'data': ['high', 'low', 'close', 'volume'],
                  'options': []},
    },
}

#: 指标名 → 需要的 K 线列（拿不到就跳过这个库）
_LIB_MODULE = {'vta': 'vector_ta', 'tulip': 'tulip_rs', 'pta_rs': 'pta_rs'}


def _module(name: str):
    """惰性 import 底层库（没装 / 没编好 → None ✓）"""
    import importlib

    if name == 'pta_rs':
        return None                      # pta_rs 走 `data.pta_rs`，不 import 模块
    try:
        return importlib.import_module(_LIB_MODULE[name])
    except Exception:                                            # noqa: BLE001
        return None


def _frame_of(data) -> pd.DataFrame:
    frame = getattr(data, 'pandas_object', data)
    return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame)


def _column(frame: pd.DataFrame, name: str):
    if name == 'timestamp':
        try:
            stamps = pd.to_datetime(pd.Series(frame['datetime']))
            return (stamps.astype('int64') // 10 ** 9).to_numpy()
        except Exception:                                        # noqa: BLE001
            return None
    if name == 'typical_price':
        try:
            high = np.asarray(frame['high'], dtype=np.float64)
            low = np.asarray(frame['low'], dtype=np.float64)
            close = np.asarray(frame['close'], dtype=np.float64)
            return (high + low + close) / 3.0
        except Exception:                                        # noqa: BLE001
            return None
    try:
        return np.ascontiguousarray(
            np.asarray(frame[name], dtype=np.float64))
    except Exception:                                            # noqa: BLE001
        return None


def compute_raw(data, name: str, lib: str, params: dict):
    """用**指定库**算原始数值；算不了返回 `None`（调用方换下一个库 ✓）

    * vector-ta / tulip-rs 多输出数组：形状 ``(输出数, 长度)``；
    * pta_rs 多输出：形状 ``(长度, 输出数)``（`split_lines()` 会自适应）。
    """
    spec = LIB_TABLE.get(str(name).lower())
    if not spec or lib not in spec:
        return None
    frame = _frame_of(data)
    if frame is None or not len(frame):
        return None
    entry = spec[lib]

    if lib == 'vta':
        module = _module('vta')
        if module is None:
            return None
        func = getattr(module, entry.get('func'), None)
        if func is None:
            return None
        args = []
        for column in entry.get('data', []):
            array = _column(frame, column)
            if array is None:
                return None
            args.append(array)
        kwargs: dict = {}
        for kwarg, canonical in entry.get('params', {}).items():
            value = params.get(canonical)
            if value is None:
                return None
            kwargs[kwarg] = value
        kwargs.update(entry.get('fixed', {}))
        try:
            return func(*args, **kwargs)
        except Exception:                                        # noqa: BLE001
            return None

    if lib == 'tulip':
        module = _module('tulip')
        if module is None:
            return None
        engine = getattr(getattr(module, 'indicators', None) or object(),
                         entry.get('func'), None)
        if engine is None or not hasattr(engine, 'indicator'):
            return None
        inputs = []
        for column in entry.get('data', []):
            array = _column(frame, column)
            if array is None:
                return None
            inputs.append(array)
        values = []
        for canonical in entry.get('options', []):
            value = params.get(canonical)
            if value is None:
                return None
            values.append(int(value) if isinstance(value, int)
                          else float(value))
        try:
            result = engine.indicator(inputs, values)
        except Exception:                                        # noqa: BLE001
            return None
        if isinstance(result, tuple):
            return result[0] if result else None
        return result

    if lib == 'pta_rs':
        accessor = getattr(data, 'pta_rs', None)
        if accessor is None:
            return None
        func = getattr(accessor, entry.get('func'), None)
        if not callable(func):
            return None
        kwargs: dict = {}
        for kwarg, canonical in entry.get('params', {}).items():
            value = params.get(canonical)
            if value is None:
                continue                       # pta_rs 自己有默认值 ✓
            kwargs[kwarg] = value
        try:
            result = func(**kwargs)
        except Exception:                                        # noqa: BLE001
            return None
        values = getattr(result, 'pandas_object', result)
        if hasattr(values, 'to_numpy'):
            values = values.to_numpy()
        # 统一成 vector-ta / tulip-rs 的 `(输出数, 长度)` 方向 ✓
        if getattr(values, 'ndim', 1) == 2 and values.shape[1] > 1:
            values = values.T
        return values

    return None


def compute_value(data, name: str, lib: str, params: dict):
    """`compute_raw` 的兼容别名（只取第一条线，老接口 ✓）"""
    raw = compute_raw(data, name, lib, params)
    if raw is None:
        return None
    lines = split_lines(raw, data, 1)
    return lines[0] if lines else None


def split_lines(raw, like, count: int = 2):
    """任意数值结果 → ``count`` 条与数据等长的 `pd.Series`（不足补空 ✓）

    * 一维数组 / Series → 当作第一条线；
    * 二维数组：自动识别 ``(输出数, 长度)``（vector-ta / tulip-rs）还是
      ``(长度, 输出数)``（pta_rs 的 DataFrame）。
    """
    empty = pd.Series(dtype=float)
    if raw is None:
        return tuple(empty for _ in range(count))
    arr = np.asarray(raw, dtype=np.float64)
    if arr.ndim == 1:
        arrays = [arr]
    elif arr.shape[0] == 0 or arr.shape[1] == 0:
        arrays = []
    else:
        # vector-ta / tulip-rs 多输出是 (输出数, 长度)，行少、列多；
        # pta_rs 是 (长度, 输出数)，行多、列少。
        if arr.shape[0] <= count and arr.shape[1] > count:
            arrays = [arr[index] for index in range(arr.shape[0])]
        elif arr.shape[1] <= count:
            arrays = [arr[:, index] for index in range(arr.shape[1])]
        else:
            arrays = [arr[index] for index in range(min(arr.shape[0], count))]
    out = [_as_series(array, like) for array in arrays]
    while len(out) < count:
        out.append(pd.Series(dtype=float))
    return tuple(out[:count])


def _has_data(series: pd.Series) -> bool:
    """这条线有没有**至少一个**有效值（NaN 全空 = 这库没算出来）✓"""
    try:
        return bool(np.isfinite(series.to_numpy(dtype=np.float64)).any())
    except Exception:                                            # noqa: BLE001
        return False


class TradingSystemCategory:
    """交易系统**分类门面**基类（`kline.tradingsystem.trend` 这种对象）。

    每个分类（`overlap` / `momentum` / `trend` …）都是**显式类**，
    类上的方法就是该分类下的指标入口 —— 这样 IDE 在
    `kline.tradingsystem.trend.` 后能直接补全方法名 ✓

    方法分两种（都由 `scripts/gen_trading_systems.py` 从规则表生成，
    所以 `dir()` / 补全 / 悬停文档三者一致）：

    * **交易系统**（出信号）：`self._system('adx_trend', length=14)`
      → 返回该系统的 `TradingSystemBase` 实例（只有 `long_signal` /
      `short_signal` 两列信号）；
    * **底层指标取值**（只算值、不出信号）：`self._lib('adx', length=14)`
      → 返回 `pd.Series`（多输出指标返回 `tuple[pd.Series, ...]`）。

    手写方法也照样能加（示例见 `trend.py` 的 `kama_trend`）：

    ```python
    class Trend(TradingSystemCategory):
        def my_rule(self, length=10):
            return MyRule(self._data, length=length)
    ```
    """

    #: 分类名（`_generated_category()` 会覆盖；手写分类可以自己写）✓
    _category: str = ''

    def __init__(self, data):
        self._data = data

    # ------------------------------------------------------ 两个入口助手
    def _system(self, name: str, **params):
        """按名字取本分类的**交易系统**（只出信号，IDE 看不到动态成员 ✓）"""
        from .tradingsystem import get

        return get(type(self)._category, name)(self._data, **params)

    def _lib(self, name: str, count: int = 1, **params):
        """按名字取**底层指标数值**（`count > 1` 返回 tuple ✓）"""
        if int(count) <= 1:
            return TradingSystemBase.lib(self._data, name, **params)
        return TradingSystemBase.lib_multi(self._data, name, int(count),
                                          **params)

    def __getattr__(self, name: str):
        # 兼容：还没重新生成的分类方法（规则表新加、脚本没跑）也能调用 ✓
        if name.startswith('_'):
            raise AttributeError(name)
        category = type(self)._category
        from .tradingsystem import get, systems

        if name in (systems().get(category) or {}):
            def call(**params):
                return get(category, name)(self._data, **params)

            return call
        raise AttributeError(f'没有这个交易系统成员：{name}')

    def __dir__(self):
        base = set(super().__dir__())
        base.update(name for name in self.__class__.__dict__
                    if not name.startswith('_'))
        return sorted(base)


class TradingSystemBase(BtIndicator):
    """## 交易系统指标基类（**只出信号、不出线** ✓）

    * `lines` 固定两条信号线 `long_signal` / `short_signal`（`1 / 0 / -1`）；
    * **不返回值序列** → 图上没有指标线，只有买卖箭头（东方财富"交易系统"同款）；
    * `signalstyle` 由框架自动补默认箭头（`SIGNAL_Str` 里的名字 ✓）；
    * 底层数值按 `LIB_ORDER` 取：**vector-ta → tulip-rs → pta_rs**；
    * 技术分析 / 预警直接读 `signals`（`long_signal > 0` 看多）。

    子类实现两个钩子：

    * `value()` → 一条 `pd.Series`（**不会画出来**，只用来算信号）；
    * `rule(values, frame)` → `(long, short)` 两个 0/1 序列（或 1/0/-1）。
    """

    #: 只画信号（值线不返回，所以图上没有线 ✓）
    overlap = False
    isplot = False
    #: 信号线（框架按 `SIGNAL_Str` 自动加箭头 + signalstyle ✓）
    lines = ('long_signal', 'short_signal')
    category = 'tradingsystem'
    params: dict = {}  # noqa: RUF012

    #: 库优先级（子类可覆盖，例如蜡烛类只认 kand ✓）
    LIB_ORDER = LIB_ORDER

    def lib(self, name: str, **params):
        """按优先级取**一条**值序列（`pd.Series`）；全都不行 → 全 NaN ✓

        `close` / `open` / `high` / `low` / `volume` 直接取 K 线列 ✓
        """
        if str(name).lower() in ('close', 'open', 'high', 'low', 'volume'):
            frame = _frame_of(self)
            array = _column(frame, str(name).lower())
            if array is not None:
                return pd.Series(array, index=self.index)
            return pd.Series(np.full(len(self), np.nan), index=self.index)
        merged = {**dict(self.params or {}), **params}
        for lib in TradingSystemBase.LIB_ORDER:
            result = compute_raw(self, name, lib, merged)
            if result is None:
                continue
            lines = split_lines(result, self, 1)
            if lines and _has_data(lines[0]):
                return lines[0]
        return pd.Series(np.full(len(self), np.nan), index=self.index)

    def lib_multi(self, name: str, count: int = 2, **params):
        """按优先级取**多条**值序列（元组 `pd.Series`）✓"""
        merged = {**dict(self.params or {}), **params}
        for lib in TradingSystemBase.LIB_ORDER:
            result = compute_raw(self, name, lib, merged)
            if result is None:
                continue
            lines = split_lines(result, self, count)
            if lines and any(_has_data(series) for series in lines):
                return lines
        return tuple(pd.Series(np.full(len(self), np.nan), index=self.index)
                     for _ in range(count))

    # ------------------------------------------------------------------ 规则
    @staticmethod
    def cross(fast, slow):
        """`fast` 上穿 `slow` → (long, short) ✓"""
        fast = _align(fast)
        slow = _align(slow)
        above = fast > slow
        below = fast < slow
        long_ = (above & above.shift(1).eq(False)).fillna(False).astype(float)
        short_ = (below & below.shift(1).eq(False)).fillna(False).astype(float)
        return long_, short_

    @staticmethod
    def threshold(values, low: float, high: float):
        """低于 `low` → 看多；高于 `high` → 看空（反转类 ✓）"""
        series = _align(values)
        long_ = (series < low).fillna(False).astype(float)
        short_ = (series > high).fillna(False).astype(float)
        return long_, short_

    @staticmethod
    def compare(values):
        """比前一根高 → 看多，比前一根低 → 看空 ✓"""
        series = _align(values)
        diff = series.diff()
        return (diff > 0).astype(float), (diff < 0).astype(float)

    @staticmethod
    def band(values, upper, lower):
        """站上上轨 → 看多；跌破下轨 → 看空 ✓"""
        series = _align(values)
        up = _align(upper)
        down = _align(lower)
        return ((series > up).astype(float),
                (series < down).astype(float))

    # ------------------------------------------------------------------ 入口
    def value(self):                                             # pragma: no cover
        return None

    def rule(self, values, frame=None):                          # pragma: no cover
        return self.compare(values)

    def next(self):
        """算值 → 出信号（**只返回信号线** ✓）"""
        try:
            values = self.value()
        except Exception:                                        # noqa: BLE001
            values = None
        if values is None:
            empty = pd.Series(np.zeros(len(self)), index=self.index)
            return pd.DataFrame({'long_signal': empty,
                                 'short_signal': empty.copy()})
        long_, short_ = self.rule(values, _frame_of(self))
        long_ = _as_series(long_, self, fill=0.0)
        short_ = _as_series(short_, self, fill=0.0)
        # 同一根不要既多又空
        both = (long_ > 0) & (short_ > 0)
        if bool(both.any()):
            long_ = long_.where(~both, 0.0)
            short_ = short_.where(~both, 0.0)
        return pd.DataFrame({'long_signal': long_, 'short_signal': short_})


def _as_series(values, like, fill: float | None = None):
    """任意一维结果 → 与数据等长的 `pd.Series`（NaN 补齐；`fill` 填零 ✓）"""
    if values is None:
        return None
    if isinstance(values, (tuple, list)):                 # 多输出取第一条 ✓
        values = values[0] if values else None
    if values is None:
        return None
    series = values if isinstance(values, pd.Series) else pd.Series(
        np.asarray(values, dtype=np.float64).ravel())
    index = getattr(like, 'index', None)
    if index is not None and len(series) != len(index):
        # 紧凑数组（tulip 不补预热 NaN）→ 右侧对齐补 NaN ✓
        if series.size < len(index):
            series = pd.Series(np.concatenate(
                [np.full(len(index) - series.size, np.nan),
                 series.to_numpy(dtype=np.float64)]), index=index)
        else:
            series = pd.Series(series.to_numpy(dtype=np.float64)[-len(index):],
                               index=index)
    elif index is not None:
        series = pd.Series(series.to_numpy(dtype=np.float64), index=index)
    if fill is not None:
        series = series.fillna(fill)
    return series.astype(float)


def _align(values):
    if isinstance(values, pd.Series):
        return values.astype(float)
    if values is None:
        return pd.Series(dtype=float)
    return pd.Series(np.asarray(values, dtype=np.float64).ravel())
