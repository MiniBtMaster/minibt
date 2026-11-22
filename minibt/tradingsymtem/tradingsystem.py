"""交易系统注册表 + 规则表驱动生成（用户 2026-11-22）

一个「交易系统」= **值序列 + 判定规则** → `long_signal` / `short_signal`，
**不画指标线**（图表上只有买卖箭头，和东方财富「交易系统」一致 ✓）。

```python
from minibt import *

self.ts = self.kline.tradingsystem.momentum.rsi_reversal()   # 只出信号
```

或用注册表遍历（desk / 文档用）：

```python
from minibt.tradingsymtem import systems
for category, table in systems().items():
    print(category, list(table))
```

**扩展**：在 `minibt/tradingsymtem/<分类>.py` 的分类类上**显式加方法**即可
（示例见 `trend.py` 的 `kama_trend` / `psar_trend`）；若同步在 `SYSTEMS`
里补一条规则，desk「交易系统」左栏也会出现。

**补全**：规则表 → 分类类上的**真实方法**由 `scripts/gen_trading_systems.py`
生成（写在 `# <ts-entries:begin>` / `# <ts-entries:end>` 之间）——
这样在 `kline.tradingsystem.trend.` 后面有补全、悬停有中文说明；加了规则
就重跑一次脚本：

```bash
py -3.12 scripts/gen_trading_systems.py --write    # 重新生成分类方法
py -3.12 scripts/gen_trading_systems.py --check    # CI：检查是否忘记生成
```

**底层库优先级**：`vector_ta` → `tulip_rs` → `pta_rs`（`TradingSystemBase.LIB_ORDER`）。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .base import TradingSystemBase, TradingSystemCategory, _as_series, _has_data

__all__ = ['CATEGORIES', 'SYSTEMS', 'TradingSystem', 'build', 'get', 'systems']

#: 分类 → 中文名（desk 左栏「交易系统」下的 section）
CATEGORIES: dict[str, str] = {
    'overlap': '重叠指标',
    'momentum': '动量指标',
    'trend': '趋势指标',
    'volatility': '波动率',
    'volume': '成交量',
    'statistics': '统计指标',
    'cycle': '周期指标',
    'performance': '表现指标',
    'candle': '蜡烛图',
    'support_resistance': '支撑阻力',
}

#: 规则表：分类 → {系统名: 配置}
#:
#: `rule` 是内置规则之一：
#:
#: * `cross`：`fast` 上穿 `value`（`fast` 上穿 `value` 做多 / 下穿做空）
#: * `cross_multi`：多输出指标的前两条线交叉（可用 `lines=(1, 0)` 调顺序）
#: * `band`：`value`（一般是 close）突破通道上下轨（`lines=(上轨, 下轨)`）
#: * `cross_mid`：`value`（一般是 close）穿越通道中轨
#: * `threshold`：低于 `levels[0]` 看多 / 高于 `levels[1]` 看空
#: * `compare`：比前一根高看多 / 低看空
#: * `compare_sign`：由负转正看多 / 由正转负看空
#: * `adx`：ADX 过滤 + ±DI 方向
#: * `cross_ma`：`value` 上穿自身均线看多 / 下穿看空
#: * `candle_engulf` / `candle_doji`：蜡烛形态
#:
#: `value` / `fast` / `band` / `di` 都是 ``(指标名, {参数})`` 或 ``('close', {})``。
SYSTEMS: dict[str, dict[str, dict[str, Any]]] = {
    # ---------------------------------------------------------- 重叠 / 均线
    'overlap': {
        'ma_cross': {
            'title': '双均线交叉（金叉做多 / 死叉做空）',
            'params': {'fast': 5, 'slow': 20},
            'value': ('sma', {'length': 'slow'}),
            'rule': 'cross',
            'fast': ('sma', {'length': 'fast'}),
        },
        'ema_trend': {
            'title': '价格与 EMA 趋势（站上看多 / 跌破看空）',
            'params': {'length': 20},
            'value': ('ema', {'length': 'length'}),
            'rule': 'cross',
            'fast': ('close', {}),
        },
        'bbands_break': {
            'title': '布林带突破（上轨追多 / 下轨追空）',
            'params': {'length': 20, 'std': 2.0},
            'value': ('close', {}),
            'rule': 'band',
            'band': ('bbands', {'length': 'length', 'std': 'std'}),
            'lines': (0, 2),
        },
        'donchian_break': {
            'title': '唐奇安通道突破（20 期新高做多 / 新低做空）',
            'params': {'length': 20},
            'value': ('close', {}),
            'rule': 'band',
            'band': ('donchian', {'length': 'length'}),
            'lines': (0, 2),
        },
    },
    # ---------------------------------------------------------- 动量
    'momentum': {
        'rsi_reversal': {
            'title': 'RSI 超买超卖（30 下做多 / 70 上做空）',
            'params': {'length': 14, 'low': 30, 'high': 70},
            'value': ('rsi', {'length': 'length'}),
            'rule': 'threshold',
        },
        'macd_cross': {
            'title': 'MACD 金叉死叉（DIF 上穿 DEA 做多）',
            'params': {'fast': 12, 'slow': 26, 'signal': 9},
            'value': ('macd', {}),
            'rule': 'cross_multi',
            'lines': (0, 1),
        },
        'stoch_cross': {
            'title': '随机指标交叉（K 上穿 D 做多）',
            'params': {'k': 14, 'd': 3},
            'value': ('stoch', {}),
            'rule': 'cross_multi',
            'lines': (0, 1),
        },
        'cci_zero': {
            'title': 'CCI 零轴穿越（上穿 0 做多 / 下穿 0 做空）',
            'params': {'length': 20},
            'value': ('cci', {'length': 'length'}),
            'rule': 'compare_sign',
        },
        'willr_reversal': {
            'title': '威廉指标反转（-80 下做多 / -20 上做空）',
            'params': {'length': 14},
            'value': ('willr', {'length': 'length'}),
            'rule': 'threshold',
            'levels': (-80.0, -20.0),
        },
    },
    # ---------------------------------------------------------- 趋势
    'trend': {
        'adx_trend': {
            'title': 'ADX 趋势过滤（ADX>20 且 +DI>-DI 做多）',
            'params': {'length': 14, 'threshold': 20},
            'value': ('adx', {'length': 'length'}),
            'rule': 'adx',
            'di': ('di', {'length': 'length'}),
        },
        'aroon_trend': {
            'title': 'Aroon 趋势（Aroon Up 上穿 Down 做多）',
            'params': {'length': 25},
            'value': ('aroon', {'length': 'length'}),
            'rule': 'cross_multi',
            'lines': (1, 0),      # vector-ta / tulip-rs 输出是 (down, up)
        },
        'trix_signal': {
            'title': 'TRIX 动能（上穿自身均线做多）',
            'params': {'length': 10, 'signal': 9},
            'value': ('trix', {'length': 'length'}),
            'rule': 'cross_ma',
        },
        'supertrend_follow': {
            'title': 'Supertrend 抬头（趋势线抬升做多 / 回落做空）',
            'params': {'length': 10, 'multiplier': 3.0},
            'value': ('supertrend', {'period': 'length',
                                     'multiplier': 'multiplier'}),
            'rule': 'compare',
        },
        'kama_trend': {
            'title': 'KAMA 自适应均线（价格上穿做多 / 下穿做空）',
            'params': {'length': 10},
            'value': ('kama', {'length': 'length'}),
            'rule': 'cross',
            'fast': ('close', {}),
        },
        'psar_trend': {
            'title': '抛物线 SAR（价格上穿做多 / 下穿做空）',
            'params': {'acceleration': 0.02, 'maximum': 0.2},
            'value': ('psar', {'acceleration': 'acceleration',
                               'maximum': 'maximum'}),
            'rule': 'cross',
            'fast': ('close', {}),
        },
    },
    # ---------------------------------------------------------- 波动率
    'volatility': {
        'keltner_break': {
            'title': '肯特纳通道突破（EMA ± ATR 带）',
            'params': {'length': 20, 'multiplier': 2.0},
            'value': ('close', {}),
            'rule': 'band',
            'band': ('keltner', {'period': 'length',
                                 'multiplier': 'multiplier'}),
            'lines': (0, 2),
        },
        'atr_rising': {
            'title': 'ATR 抬头 = 波动放大（放大做多 / 收缩做空）',
            'params': {'length': 14},
            'value': ('atr', {'length': 'length'}),
            'rule': 'compare',
        },
        'zscore_band': {
            'title': 'Z 分数极端反转（|z|>2 反向）',
            'params': {'length': 20, 'z': 2.0},
            'value': ('zscore', {'length': 'length'}),
            'rule': 'threshold',
            'levels': (-2.0, 2.0),
        },
    },
    # ---------------------------------------------------------- 成交量
    'volume': {
        'obv_trend': {
            'title': 'OBV 能量潮趋势（上穿自身均线做多）',
            'params': {'length': 20},
            'value': ('obv', {}),
            'rule': 'cross_ma',
        },
        'mfi_reversal': {
            'title': '资金流量反转（20 下做多 / 80 上做空）',
            'params': {'length': 14},
            'value': ('mfi', {'length': 'length'}),
            'rule': 'threshold',
            'levels': (20.0, 80.0),
        },
        'vwap_cross': {
            'title': '价格穿越 VWAP（上穿做多 / 下穿做空）',
            'params': {},
            'value': ('vwap', {}),
            'rule': 'cross',
            'fast': ('close', {}),
        },
    },
    # ---------------------------------------------------------- 统计
    'statistics': {
        'zscore_reversal': {
            'title': 'Z 分数反转（-2 下做多 / +2 上做空）',
            'params': {'length': 20},
            'value': ('zscore', {'length': 'length'}),
            'rule': 'threshold',
            'levels': (-2.0, 2.0),
        },
        'rank_extreme': {
            'title': '分位极端（排名靠低做多 / 靠高做空）',
            'params': {'length': 20},
            'value': ('rsi', {'length': 'length'}),
            'rule': 'threshold',
            'levels': (20.0, 80.0),
        },
    },
    # ---------------------------------------------------------- 周期
    'cycle': {
        'dpo_turn': {
            'title': 'DPO 过零（上穿 0 做多 / 下穿 0 做空）',
            'params': {'length': 20},
            'value': ('dpo', {'length': 'length'}),
            'rule': 'compare_sign',
        },
        'roc_cycle': {
            'title': 'ROC 动能拐头（动量转正做多 / 转负做空）',
            'params': {'length': 10},
            'value': ('roc', {'length': 'length'}),
            'rule': 'compare_sign',
        },
    },
    # ---------------------------------------------------------- 表现
    'performance': {
        'roc_momentum': {
            'title': 'ROC 动量（>0 做多 / <0 做空）',
            'params': {'length': 10},
            'value': ('roc', {'length': 'length'}),
            'rule': 'compare_sign',
        },
        'apo_momentum': {
            'title': 'APO 动量（快慢均线差过 0）',
            'params': {'fast': 12, 'slow': 26},
            'value': ('apo', {'fast': 'fast', 'slow': 'slow'}),
            'rule': 'compare_sign',
        },
    },
    # ---------------------------------------------------------- 蜡烛图
    'candle': {
        'engulfing_signal': {
            'title': '吞没形态 + 趋势过滤（做多 / 做空）',
            'params': {'length': 9},
            'value': ('close', {}),
            'rule': 'candle_engulf',
        },
        'doji_reversal': {
            'title': '十字星反转（实体极小 + 位置极端）',
            'params': {'body': 0.1},
            'value': ('close', {}),
            'rule': 'candle_doji',
        },
    },
    # ---------------------------------------------------------- 支撑阻力
    'support_resistance': {
        'donchian_sr': {
            'title': '前高前低穿越（做多 / 做空）',
            'params': {'length': 20},
            'value': ('close', {}),
            'rule': 'band',
            'band': ('donchian', {'length': 'length'}),
            'lines': (0, 2),
        },
        'bbands_sr': {
            'title': '布林中轨穿越（站上做多 / 跌破做空）',
            'params': {'length': 20, 'std': 2.0},
            'value': ('close', {}),
            'rule': 'cross_mid',
            'band': ('bbands', {'length': 'length', 'std': 'std'}),
            'lines': (1,),
        },
    },
}


def _resolve(value_spec: dict, params: dict) -> dict:
    """`{'length': 'slow'}` → 实际值（`'slow'` 从 params 里取 ✓）"""
    out: dict = {}
    for key, value in (value_spec or {}).items():
        if isinstance(value, str) and value in params:
            out[key] = params[value]
        else:
            out[key] = value
    return out


def _merged(params: dict, system) -> dict:
    """类默认参数 + 运行时参数（运行时优先 ✓）"""
    return {**dict(params or {}), **dict(getattr(system, 'params', None) or {})}


def _line(system, spec, merged: dict):
    """一条值序列（`('close', {})` 直接取收盘价 ✓）

    ⚠ `next(self)` 里的 `self` 是**源 KLine**（`BtIndicator` 的约定），
    不是交易系统实例 → 这里统一走 `TradingSystemBase.lib(...)`。
    """
    if not isinstance(spec, (tuple, list)) or not spec:
        return TradingSystemBase.lib(system, 'close')
    if str(spec[0]) == 'close':
        return TradingSystemBase.lib(system, 'close')
    return TradingSystemBase.lib(system, str(spec[0]),
                                 **_resolve(spec[1], merged))


def _multi(system, spec, merged: dict, count: int):
    """多条值序列（`('macd', {})` → 2 条 / `('bbands', {})` → 3 条 ✓）"""
    if not isinstance(spec, (tuple, list)) or not spec:
        return tuple(pd.Series(dtype=float) for _ in range(count))
    return TradingSystemBase.lib_multi(system, str(spec[0]), count,
                                       **_resolve(spec[1], merged))


def build(category: str, name: str, spec: dict):
    """把注册表配方 → 真正的 `TradingSystemBase` 子类 ✓"""
    params = dict(spec.get('params') or {})
    rule = str(spec.get('rule') or 'compare')
    base = spec.get('value') or ('close', {})
    fast_spec = spec.get('fast') or ()
    band_spec = spec.get('band') or ()
    di_spec = spec.get('di') or ()

    def next_(self):
        merged = _merged(params, self)

        if rule == 'cross':
            fast = _line(self, fast_spec, merged)
            slow = _line(self, base, merged)
            long_, short_ = TradingSystemBase.cross(fast, slow)
        elif rule == 'cross_multi':
            lines = _multi(self, base, merged, 2)
            index = spec.get('lines') or (0, 1)
            long_, short_ = TradingSystemBase.cross(lines[int(index[0])],
                                                    lines[int(index[1])])
        elif rule == 'band':
            value = _line(self, base, merged)
            lines = _multi(self, band_spec, merged, 3)
            index = spec.get('lines') or (0, 2)
            long_, short_ = TradingSystemBase.band(value,
                                                   lines[int(index[0])],
                                                   lines[int(index[1])])
        elif rule == 'cross_mid':
            value = _line(self, base, merged)
            lines = _multi(self, band_spec, merged, 3)
            index = spec.get('lines') or (1,)
            long_, short_ = TradingSystemBase.cross(value,
                                                    lines[int(index[0])])
        elif rule == 'threshold':
            levels = spec.get('levels') or (merged.get('low', 30.0),
                                            merged.get('high', 70.0))
            long_, short_ = TradingSystemBase.threshold(
                _line(self, base, merged),
                float(levels[0]),
                float(levels[1]))
        elif rule == 'adx':
            adx = _line(self, base, merged)
            dmp, dmn = _multi(self, di_spec, merged, 2)
            if not (_has_data(dmp) and _has_data(dmn)):
                # ★ `di` 只在部分库里有（vector-ta）；只装了 pta_rs 时取不到 →
                #   用 `adx` 自己的多输出（adx / +DI / -DI）补齐 ✓
                lines = _multi(self, base, merged, 3)
                if len(lines) >= 3 and _has_data(lines[1]):
                    dmp, dmn = lines[1], lines[2]
            level = float(merged.get('threshold', 20))
            long_ = ((adx > level) & (dmp > dmn)).astype(float)
            short_ = ((adx > level) & (dmp < dmn)).astype(float)
        elif rule == 'cross_ma':
            series = _line(self, base, merged)
            ma = series.rolling(max(1, int(merged.get('length', 20)))).mean()
            long_, short_ = TradingSystemBase.cross(series, ma)
        elif rule == 'compare_sign':
            series = _line(self, base, merged)
            sign = np.sign(series.fillna(0.0))
            long_, short_ = TradingSystemBase.cross(
                sign, pd.Series(0.0, index=series.index))
        elif rule in ('candle_engulf', 'candle_doji'):
            frame = getattr(self, 'pandas_object', None)
            long_, short_ = _candle_rule(frame, rule, merged)
        else:                                   # compare
            long_, short_ = TradingSystemBase.compare(_line(self, base, merged))

        long_ = _as_series(long_, self, fill=0.0)
        short_ = _as_series(short_, self, fill=0.0)
        both = (long_ > 0) & (short_ > 0)
        if bool(both.any()):
            long_ = long_.where(~both, 0.0)
            short_ = short_.where(~both, 0.0)
        return pd.DataFrame({'long_signal': long_, 'short_signal': short_})

    attrs = {
        'params': params,
        'title': spec.get('title') or name,
        'category': category,
        'next': next_,
        '__doc__': f'{spec.get("title") or name}（交易系统：只出信号）',
        '__module__': __name__,
    }
    return type(f'TS_{category}_{name}', (TradingSystemBase,), attrs)


def _candle_rule(frame, rule: str, params: dict):
    """蜡烛图规则（吞没 / 十字星 + 趋势过滤）✓"""
    if frame is None:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    open_ = np.asarray(frame['open'], dtype=np.float64)
    close = np.asarray(frame['close'], dtype=np.float64)
    high = np.asarray(frame['high'], dtype=np.float64)
    low = np.asarray(frame['low'], dtype=np.float64)
    body = np.abs(close - open_)
    index = frame.index
    prev_open = np.roll(open_, 1)
    prev_close = np.roll(close, 1)
    bull = (close > open_) & (prev_close < prev_open) & (close >= prev_open) \
        & (open_ <= prev_close)
    bear = (close < open_) & (prev_close > prev_open) & (close <= prev_open) \
        & (open_ >= prev_close)
    if rule == 'candle_doji':
        ratio = float(params.get('body', 0.1))
        small = body <= np.abs(high - low) * ratio
        bull = small & (close > open_)
        bear = small & (close < open_)
    long_ = pd.Series(bull.astype(float), index=index)
    short_ = pd.Series(bear.astype(float), index=index)
    long_.iloc[:1] = 0.0
    short_.iloc[:1] = 0.0
    # 趋势过滤：只在均线顺向时出信号（避免乱做）
    trend = pd.Series(close, index=index).rolling(
        max(1, int(params.get('length', 9)))).mean()
    rising = pd.Series(close, index=index) > trend
    return (long_ * rising.astype(float)), (short_ * (~rising).astype(float))


#: 生成好的类（分类 → {名字: 类}）
_REGISTRY: dict[str, dict[str, type]] = {}


def systems(refresh: bool = False) -> dict[str, dict[str, type]]:
    """分类 → {系统名: 类}（首次调用时生成 ✓）"""
    if _REGISTRY and not refresh:
        return _REGISTRY
    _REGISTRY.clear()
    for category, table in SYSTEMS.items():
        _REGISTRY[category] = {
            name: build(category, name, spec)
            for name, spec in table.items()
        }
    return _REGISTRY


def get(category: str, name: str):
    """取一个交易系统类（`get('momentum', 'rsi_reversal')` ✓）"""
    table = systems().get(category) or {}
    cls = table.get(name)
    if cls is None:
        raise KeyError(f'没有这个交易系统：{category}/{name}')
    return cls


def _generated_category(category: str, lib_indicators: tuple = ()):
    """从规则表生成**显式分类类**（方法 = 真实属性，IDE 可补全 ✓）

    `kline.tradingsystem.overlap.ma_cross` 这类访问不再走 `__getattr__`，
    而是分类类上真实定义的方法；`dir()` 和静态分析都能看到 ✓

    `lib_indicators`：`(指标名, 输出数)` 序列。输出数 `1` 的生成
    ``kline.tradingsystem.<分类>.<指标名>(...)`` 取值入口（返回 `pd.Series`）；
    输出数 `>1` 的返回 ``tuple[pd.Series, ...]``。
    """
    table = systems().get(category, {})

    def __init__(self, data):
        self._data = data

    attrs: dict[str, Any] = {'__init__': __init__,
                             '_category': category}
    for name, cls in table.items():
        def method(self, _cls=cls, **params):
            return _cls(self._data, **params)

        method.__name__ = name
        method.__qualname__ = f'{category}_category.{name}'
        method.__doc__ = getattr(cls, '__doc__', '') or name
        attrs[name] = method

    # -------------------------------------------------- 底层指标取值入口
    for name, count in (lib_indicators or ()):
        def lib_method(self, _name=name, _count=int(count), **params):
            if _count <= 1:
                return TradingSystemBase.lib(self._data, _name, **params)
            return TradingSystemBase.lib_multi(self._data, _name, _count,
                                               **params)

        lib_method.__name__ = name
        lib_method.__qualname__ = f'{category}_category.{name}'
        lib_method.__doc__ = (
            f'底层指标 `{name}` 取值入口（只算值、不出信号；'
            f'输出数 {int(count)}）')
        attrs[name] = lib_method
    return type(f'_{category.title()}Category',
                (TradingSystemCategory,), attrs)


# ★ 显式扩展的分类类（先有 `_generated_category` 再 import，避免循环依赖）
#
# 用户自己加指标时，在对应分类文件里（如 `trend.py`）继续给 `Trend` 类加方法，
# 或在文件里定义新的 `TradingSystemBase` 子类 + 方法即可；desk 会自动出现在
# 「交易系统」左栏对应分类下（若同步在 `SYSTEMS` 里补一条规则）。
from . import candle as _candle
from . import cycle as _cycle
from . import momentum as _momentum
from . import overlap as _overlap
from . import performance as _performance
from . import statistics as _statistics
from . import support_resistance as _support_resistance
from . import trend as _trend
from . import volatility as _volatility
from . import volume as _volume


class TradingSystem:
    """## 交易系统门面（`kline.tradingsystem.<分类>.<系统>(...)`）

    * **分类属性是显式的**：`overlap` / `momentum` / `trend` / … 都是
      `__init__` 里真实赋值的对象，IDE 在 `kline.tradingsystem.` 后能补全 ✓
    * 只出信号：调用返回的 `IndFrame` 只有 `long_signal` / `short_signal` 两列；
    * 分类访问：`kline.tradingsystem.momentum.rsi_reversal(length=14)`；
    * 扁平访问：`kline.tradingsystem.momentum_rsi_reversal(length=14)`
      （desk 目录 / 参数表单用 ✓）。
    """

    def __init__(self, data):
        self._data = data
        # ---------------------------------------------------------- 显式分类
        # 每个分类都是对应文件里真实定义的类（IDE 可补全 ✓）
        self.overlap = _overlap.Overlap(data)
        self.momentum = _momentum.Momentum(data)
        self.trend = _trend.Trend(data)          # 显式扩展示例：trend.py ✓
        self.volatility = _volatility.Volatility(data)
        self.volume = _volume.Volume(data)
        self.statistics = _statistics.Statistics(data)
        self.cycle = _cycle.Cycle(data)
        self.performance = _performance.Performance(data)
        self.candle = _candle.Candle(data)
        self.support_resistance = _support_resistance.SupportResistance(data)

    def __getattr__(self, name: str):
        # 扁平访问：`momentum_rsi_reversal` → 直接调用（desk 目录用 ✓）
        for category in CATEGORIES:
            prefix = f'{category}_'
            if name.startswith(prefix):
                system_name = name[len(prefix):]
                try:
                    cls = get(category, system_name)
                except KeyError as error:
                    raise AttributeError(
                        f'没有这个交易系统：{name}') from error

                def call(_cls=cls, **params):
                    return _cls(self._data, **params)

                return call
        raise AttributeError(f'没有这个交易系统成员：{name}')

    def __dir__(self):
        names = list(CATEGORIES)
        for category, table in systems().items():
            names += [f'{category}_{name}' for name in table]
        return names

    # <ts-flat:begin>  ← 扁平访问入口（scripts/gen_trading_systems.py 生成，勿手改 ✓）
    # 扁平访问：等价于 `<分类>.<系统>(...)`（desk 目录 / 参数表单用）
    def overlap_bbands_break(self, length: int = 20,
                                   std: float = 2.0,
                                   **params) -> TradingSystemBase:
        """布林带突破（上轨追多 / 下轨追空）（扁平访问，等价于 `overlap.bbands_break` ✓）"""
        return self.overlap.bbands_break(length=length, std=std)

    def overlap_donchian_break(self, length: int = 20,
                                     **params) -> TradingSystemBase:
        """唐奇安通道突破（20 期新高做多 / 新低做空）（扁平访问，等价于 `overlap.donchian_break` ✓）"""
        return self.overlap.donchian_break(length=length)

    def overlap_ema_trend(self, length: int = 20,
                                **params) -> TradingSystemBase:
        """价格与 EMA 趋势（站上看多 / 跌破看空）（扁平访问，等价于 `overlap.ema_trend` ✓）"""
        return self.overlap.ema_trend(length=length)

    def overlap_ma_cross(self, fast: int = 5,
                               slow: int = 20, **params) -> TradingSystemBase:
        """双均线交叉（金叉做多 / 死叉做空）（扁平访问，等价于 `overlap.ma_cross` ✓）"""
        return self.overlap.ma_cross(fast=fast, slow=slow)

    def momentum_cci_zero(self, length: int = 20,
                                **params) -> TradingSystemBase:
        """CCI 零轴穿越（上穿 0 做多 / 下穿 0 做空）（扁平访问，等价于 `momentum.cci_zero` ✓）"""
        return self.momentum.cci_zero(length=length)

    def momentum_macd_cross(self, fast: int = 12,
                                  slow: int = 26,
                                  signal: int = 9,
                                  **params) -> TradingSystemBase:
        """MACD 金叉死叉（DIF 上穿 DEA 做多）（扁平访问，等价于 `momentum.macd_cross` ✓）"""
        return self.momentum.macd_cross(fast=fast, slow=slow, signal=signal)

    def momentum_rsi_reversal(self, length: int = 14,
                                    low: int = 30,
                                    high: int = 70,
                                    **params) -> TradingSystemBase:
        """RSI 超买超卖（30 下做多 / 70 上做空）（扁平访问，等价于 `momentum.rsi_reversal` ✓）"""
        return self.momentum.rsi_reversal(length=length, low=low, high=high)

    def momentum_stoch_cross(self, k: int = 14,
                                   d: int = 3, **params) -> TradingSystemBase:
        """随机指标交叉（K 上穿 D 做多）（扁平访问，等价于 `momentum.stoch_cross` ✓）"""
        return self.momentum.stoch_cross(k=k, d=d)

    def momentum_willr_reversal(self, length: int = 14,
                                      **params) -> TradingSystemBase:
        """威廉指标反转（-80 下做多 / -20 上做空）（扁平访问，等价于 `momentum.willr_reversal` ✓）"""
        return self.momentum.willr_reversal(length=length)

    def trend_adx_trend(self, length: int = 14,
                              threshold: int = 20,
                              **params) -> TradingSystemBase:
        """ADX 趋势过滤（ADX>20 且 +DI>-DI 做多）（扁平访问，等价于 `trend.adx_trend` ✓）"""
        return self.trend.adx_trend(length=length, threshold=threshold)

    def trend_aroon_trend(self, length: int = 25,
                                **params) -> TradingSystemBase:
        """Aroon 趋势（Aroon Up 上穿 Down 做多）（扁平访问，等价于 `trend.aroon_trend` ✓）"""
        return self.trend.aroon_trend(length=length)

    def trend_kama_trend(self, length: int = 10,
                               **params) -> TradingSystemBase:
        """KAMA 自适应均线（价格上穿做多 / 下穿做空）（扁平访问，等价于 `trend.kama_trend` ✓）"""
        return self.trend.kama_trend(length=length)

    def trend_psar_trend(self,
                               acceleration: float = 0.02,
                               maximum: float = 0.2,
                               **params) -> TradingSystemBase:
        """抛物线 SAR（价格上穿做多 / 下穿做空）（扁平访问，等价于 `trend.psar_trend` ✓）"""
        return self.trend.psar_trend(acceleration=acceleration, maximum=maximum)

    def trend_supertrend_follow(self, length: int = 10,
                                      multiplier: float = 3.0,
                                      **params) -> TradingSystemBase:
        """Supertrend 抬头（趋势线抬升做多 / 回落做空）（扁平访问，等价于 `trend.supertrend_follow` ✓）"""
        return self.trend.supertrend_follow(length=length, multiplier=multiplier)

    def trend_trix_signal(self, length: int = 10,
                                signal: int = 9,
                                **params) -> TradingSystemBase:
        """TRIX 动能（上穿自身均线做多）（扁平访问，等价于 `trend.trix_signal` ✓）"""
        return self.trend.trix_signal(length=length, signal=signal)

    def volatility_atr_rising(self, length: int = 14,
                                    **params) -> TradingSystemBase:
        """ATR 抬头 = 波动放大（放大做多 / 收缩做空）（扁平访问，等价于 `volatility.atr_rising` ✓）"""
        return self.volatility.atr_rising(length=length)

    def volatility_keltner_break(self, length: int = 20,
                                       multiplier: float = 2.0,
                                       **params) -> TradingSystemBase:
        """肯特纳通道突破（EMA ± ATR 带）（扁平访问，等价于 `volatility.keltner_break` ✓）"""
        return self.volatility.keltner_break(length=length, multiplier=multiplier)

    def volatility_zscore_band(self, length: int = 20,
                                     z: float = 2.0,
                                     **params) -> TradingSystemBase:
        """Z 分数极端反转（|z|>2 反向）（扁平访问，等价于 `volatility.zscore_band` ✓）"""
        return self.volatility.zscore_band(length=length, z=z)

    def volume_mfi_reversal(self, length: int = 14,
                                  **params) -> TradingSystemBase:
        """资金流量反转（20 下做多 / 80 上做空）（扁平访问，等价于 `volume.mfi_reversal` ✓）"""
        return self.volume.mfi_reversal(length=length)

    def volume_obv_trend(self, length: int = 20,
                               **params) -> TradingSystemBase:
        """OBV 能量潮趋势（上穿自身均线做多）（扁平访问，等价于 `volume.obv_trend` ✓）"""
        return self.volume.obv_trend(length=length)

    def volume_vwap_cross(self, **params) -> TradingSystemBase:
        """价格穿越 VWAP（上穿做多 / 下穿做空）（扁平访问，等价于 `volume.vwap_cross` ✓）"""
        return self.volume.vwap_cross()

    def statistics_rank_extreme(self, length: int = 20,
                                      **params) -> TradingSystemBase:
        """分位极端（排名靠低做多 / 靠高做空）（扁平访问，等价于 `statistics.rank_extreme` ✓）"""
        return self.statistics.rank_extreme(length=length)

    def statistics_zscore_reversal(self,
                                         length: int = 20,
                                         **params) -> TradingSystemBase:
        """Z 分数反转（-2 下做多 / +2 上做空）（扁平访问，等价于 `statistics.zscore_reversal` ✓）"""
        return self.statistics.zscore_reversal(length=length)

    def cycle_dpo_turn(self, length: int = 20, **params) -> TradingSystemBase:
        """DPO 过零（上穿 0 做多 / 下穿 0 做空）（扁平访问，等价于 `cycle.dpo_turn` ✓）"""
        return self.cycle.dpo_turn(length=length)

    def cycle_roc_cycle(self, length: int = 10,
                              **params) -> TradingSystemBase:
        """ROC 动能拐头（动量转正做多 / 转负做空）（扁平访问，等价于 `cycle.roc_cycle` ✓）"""
        return self.cycle.roc_cycle(length=length)

    def performance_apo_momentum(self, fast: int = 12,
                                       slow: int = 26,
                                       **params) -> TradingSystemBase:
        """APO 动量（快慢均线差过 0）（扁平访问，等价于 `performance.apo_momentum` ✓）"""
        return self.performance.apo_momentum(fast=fast, slow=slow)

    def performance_roc_momentum(self, length: int = 10,
                                       **params) -> TradingSystemBase:
        """ROC 动量（>0 做多 / <0 做空）（扁平访问，等价于 `performance.roc_momentum` ✓）"""
        return self.performance.roc_momentum(length=length)

    def candle_doji_reversal(self, body: float = 0.1,
                                   **params) -> TradingSystemBase:
        """十字星反转（实体极小 + 位置极端）（扁平访问，等价于 `candle.doji_reversal` ✓）"""
        return self.candle.doji_reversal(body=body)

    def candle_engulfing_signal(self, length: int = 9,
                                      **params) -> TradingSystemBase:
        """吞没形态 + 趋势过滤（做多 / 做空）（扁平访问，等价于 `candle.engulfing_signal` ✓）"""
        return self.candle.engulfing_signal(length=length)

    def support_resistance_bbands_sr(self,
                                           length: int = 20,
                                           std: float = 2.0,
                                           **params) -> TradingSystemBase:
        """布林中轨穿越（站上做多 / 跌破做空）（扁平访问，等价于 `support_resistance.bbands_sr` ✓）"""
        return self.support_resistance.bbands_sr(length=length, std=std)

    def support_resistance_donchian_sr(self,
                                             length: int = 20,
                                             **params) -> TradingSystemBase:
        """前高前低穿越（做多 / 做空）（扁平访问，等价于 `support_resistance.donchian_sr` ✓）"""
        return self.support_resistance.donchian_sr(length=length)

    # <ts-flat:end>  ← 生成区结束

