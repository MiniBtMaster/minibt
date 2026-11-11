"""指标 / 策略的**信号（signals）**（v1.3.7-73）。

minibt desk 技术分析金融插件指标设置：

* 指标 / 策略上声明 `signals = {'rsi': Threshold(0, 1)}`；
* 每个信号把**最新值（或某条线）**判成 **1（多）/ 0（中立）/ -1（空）**；
* 两种"常态化"信号：

  - :class:`Threshold`（原 `Osc`）：与固定数值比较 —— 大于 → 方向，等于 → 0；
  - :class:`Compare`（原 `Trend`）：当前值与**历史索引值**比较（负索引，-1 = 最新）。

* 也支持**函数**（`lambda series: -1/0/1`）或**方法名字符串**（可持久化）。

技术分析插件、K 线信号圆点、预警条件都复用同一套评估逻辑 ✓
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Sequence

#: 三个分组（技术分析插件里的三类）
GROUPS = {
    'oscillator': '震荡指标',
    'trend': '趋势指标',
    'other': '其他指标',
}


def _last(values: Sequence[Any], index: int = -1) -> Optional[float]:
    try:
        number = float(values[index])
    except (IndexError, TypeError, ValueError):
        return None
    if number != number:                                # NaN
        return None
    return number


class Signal:
    """信号基类（子类实现 :meth:`evaluate`）"""

    #: 需要多少根数据才判定（不足 → 中立 0）
    min_history = 1
    #: 分组：oscillator / trend / other
    group = 'other'
    #: 权重（技术分析汇总 score 用；默认 1）
    weight = 1.0

    def __init__(self, label: str = '', group: str = '',
                 weight: float = 1.0) -> None:
        self.label = str(label or '')
        if group:
            self.group = str(group)
        self.weight = float(weight or 1.0)

    # ------------------------------------------------------------ 子类实现
    def evaluate(self, values: Sequence[Any]) -> int:
        raise NotImplementedError

    # ------------------------------------------------------------ 通用
    def describe(self) -> str:
        """UI 文案（子类覆盖）"""
        return self.label or self.__class__.__name__

    def to_spec(self) -> Dict[str, Any]:
        """可序列化（模板 / 前端用 ✓）"""
        return {'kind': self.__class__.__name__.lower(),
                'group': self.group, 'weight': self.weight,
                'label': self.label}

    def __repr__(self) -> str:                            # pragma: no cover
        return f'{self.__class__.__name__}({self.describe()})'


class Threshold(Signal):
    """与固定数值比较（**原 `Osc`**）

    ``Threshold(0, 1)``：最新值 **> 0 → 1（多）**，``== 0 → 0``，``< 0 → -1``；
    ``direction=-1`` 则完全反过来（上方看空 ✓）。
    """

    min_history = 1

    def __init__(self, level: float = 0.0, direction: int = 1,
                 line: Optional[str] = None, label: str = '',
                 group: str = 'oscillator', weight: float = 1.0) -> None:
        super().__init__(label=label, group=group, weight=weight)
        self.level = float(level or 0.0)
        self.direction = 1 if int(direction or 1) >= 0 else -1
        self.line = line or None

    def describe(self) -> str:
        if self.label:
            return self.label
        side = '看多' if self.direction > 0 else '看空'
        return f'{self.level:g} 上方{side}'

    def evaluate(self, values: Sequence[Any]) -> int:
        value = _last(values)
        if value is None:
            return 0
        if abs(value - self.level) < 1e-12:
            return 0
        return self.direction if value > self.level else -self.direction

    def to_spec(self) -> Dict[str, Any]:
        return {**super().to_spec(), 'level': self.level,
                'direction': self.direction, 'line': self.line or ''}


class Compare(Signal):
    """当前值与历史索引值比较（**原 `Trend`**）

    ``Compare(-2, 1)``：最新值 > 前一根 → 1（多），等于 → 0，小于 → -1；
    ``direction=-1`` 反向；``level`` 是额外阈值（比较差值，默认 0）。
    """

    def __init__(self, offset: int = -2, direction: int = 1,
                 level: float = 0.0, line: Optional[str] = None,
                 label: str = '', group: str = 'trend',
                 weight: float = 1.0) -> None:
        super().__init__(label=label, group=group, weight=weight)
        offset = int(offset if offset is not None else -2)
        if offset >= 0:
            raise ValueError('Compare.offset 必须为负数（-1 = 最新，-2 = 前一根）')
        self.offset = offset
        self.level = float(level or 0.0)
        self.direction = 1 if int(direction or 1) >= 0 else -1
        self.line = line or None
        self.min_history = max(2, abs(offset))

    def describe(self) -> str:
        if self.label:
            return self.label
        side = '看多' if self.direction > 0 else '看空'
        which = {-1: '最新', -2: '前一根', -3: '前两根',
                 -4: '前 3 根', -5: '前 4 根'}.get(self.offset,
                                               f'{self.offset} 根')
        return f'高于{which}时{side}'

    def evaluate(self, values: Sequence[Any]) -> int:
        if len(values) < self.min_history:
            return 0
        last = _last(values, -1)
        base = _last(values, self.offset)
        if last is None or base is None:
            return 0
        delta = last - base
        if abs(delta - self.level) < 1e-12:
            return 0
        return self.direction if delta > self.level else -self.direction

    def to_spec(self) -> Dict[str, Any]:
        return {**super().to_spec(), 'offset': self.offset,
                'level': self.level, 'direction': self.direction,
                'line': self.line or ''}


class Custom(Signal):
    """自定义函数：``Custom(lambda s: 1 if s.iloc[-1] > 0 else -1)`` ✓"""

    def __init__(self, fn: Callable[[Sequence[Any]], Any],
                 label: str = '', group: str = 'other',
                 weight: float = 1.0, min_history: int = 1) -> None:
        super().__init__(label=label, group=group, weight=weight)
        self.fn = fn
        self.min_history = max(1, int(min_history or 1))

    def evaluate(self, values: Sequence[Any]) -> int:
        result = self.fn(values)
        try:
            number = float(result)
        except (TypeError, ValueError):
            return 0
        if number != number:                               # NaN
            return 0
        return 1 if number > 0 else (-1 if number < 0 else 0)

    def describe(self) -> str:
        return self.label or '自定义信号'

    def to_spec(self) -> Dict[str, Any]:
        return {**super().to_spec(), 'kind': 'custom',
                'label': self.label or '自定义信号'}


#: 兼容旧名（用户最早的设计里叫 `Osc` / `Trend` ✓）
Osc = Threshold
Trend = Compare


def spec_of(signal: Any) -> Dict[str, Any]:
    """任意信号 → 可序列化 dict（模板 / 前端 ✓）"""
    if isinstance(signal, Signal):
        return signal.to_spec()
    return {'kind': 'custom', 'label': '自定义信号', 'group': 'other'}


def signal_from_spec(spec: Dict[str, Any],
                     group: str = '') -> Optional[Signal]:
    """dict → 信号对象（模板反序列化 ✓）；非法返回 None"""
    if not isinstance(spec, dict):
        return None
    kind = str(spec.get('kind') or '').strip().lower()
    try:
        if kind == 'threshold':
            return Threshold(spec.get('level') or 0.0,
                             spec.get('direction') or 1,
                             line=spec.get('line') or None,
                             label=str(spec.get('label') or ''),
                             group=group or spec.get('group') or 'oscillator',
                             weight=float(spec.get('weight') or 1.0))
        if kind == 'compare':
            return Compare(int(spec.get('offset') if spec.get('offset')
                               is not None else -2),
                           spec.get('direction') or 1,
                           spec.get('level') or 0.0,
                           line=spec.get('line') or None,
                           label=str(spec.get('label') or ''),
                           group=group or spec.get('group') or 'trend',
                           weight=float(spec.get('weight') or 1.0))
    except Exception:                                        # noqa: BLE001
        return None
    return None


def evaluate_values(signal: Signal, values: Sequence[Any]) -> int:
    """安全评估：任何异常 / 数据不足都回 **0（中立）** ✓"""
    try:
        if len(values) < int(getattr(signal, 'min_history', 1) or 1):
            return 0
        result = int(signal.evaluate(values))
    except Exception:                                        # noqa: BLE001
        return 0
    return 1 if result > 0 else (-1 if result < 0 else 0)


def resolve_signal(spec: Any, owner: Any = None) -> Optional[Signal]:
    """声明值 → 信号对象（支持对象 / dict / callable / 方法名 ✓）"""
    if isinstance(spec, Signal):
        return spec
    if isinstance(spec, dict):
        return signal_from_spec(spec)
    if callable(spec):
        return Custom(spec)
    if isinstance(spec, str) and owner is not None:
        fn = getattr(owner, spec, None)
        if callable(fn):
            return Custom(fn)
    return None


def summarize(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """信号行 → `{score, label, counts}`（技术分析汇总 ✓）"""
    counts = {'buy': 0, 'neutral': 0, 'sell': 0}
    total = 0.0
    weight = 0.0
    for row in rows or []:
        signal = int(row.get('signal') or 0)
        counts['buy' if signal > 0 else ('sell' if signal < 0
                                         else 'neutral')] += 1
        row_weight = float(row.get('weight') or 1.0)
        total += signal * row_weight
        weight += row_weight
    score = (total / weight) if weight else 0.0
    label = 'BUY' if score > 0.15 else ('SELL' if score < -0.15 else 'NEUTRAL')
    return {'score': round(score, 4), 'label': label, 'counts': counts}


# ---------------------------------------------------------------- 内置信号表
#: 目录 key → `{线名: 信号}`（v1.3.7-73）
#:
#: 为什么不逐个改 `@tobtind`？700 个指标各加一遍太重、也容易漏；
#: 这里按「key 前缀 + 名字」集中登记，目录合并时自动带上 ✓
BUILTIN_SIGNALS: Dict[str, Dict[str, Any]] = {
    # 震荡类：与固定数值比较
    'pta_rsi': {'rsi': Threshold(50, 1, label='50 上方看多')},
    'finta_RSI': {'rsi': Threshold(50, 1, label='50 上方看多')},
    'tv:rsi': {'rsi': Threshold(50, 1, label='50 上方看多')},
    'pta_cci': {'cci': Threshold(0, 1, label='0 上方看多')},
    'tv:cci': {'cci': Threshold(0, 1, label='0 上方看多')},
    'pta_willr': {'willr': Threshold(-50, 1, label='-50 上方看多')},
    'tv:williams_r': {'williams_r': Threshold(-50, 1, label='-50 上方看多')},
    'pta_mfi': {'mfi': Threshold(50, 1, label='50 上方看多')},
    'pta_stoch': {'stoch': Threshold(50, 1, label='50 上方看多')},
    'tv:stoch': {'k': Threshold(50, 1, label='%K 50 上方看多')},
    'pta_adx': {'adx': Threshold(20, 1, label='20 上方趋势成立')},
    'tv:adx': {'adx': Threshold(20, 1, label='20 上方趋势成立')},
    'pta_macd': {'macd': Threshold(0, 1, label='MACD 0 轴上方看多')},
    'tv:macd': {'macd': Threshold(0, 1, label='MACD 0 轴上方看多')},
    # 趋势类：与历史值比较
    'pta_sma': {'sma': Compare(-2, 1, label='高于前一根看多')},
    'pta_ema': {'ema': Compare(-2, 1, label='高于前一根看多')},
    'tv:sma': {'sma': Compare(-2, 1, label='高于前一根看多')},
    'tv:ema': {'ema': Compare(-2, 1, label='高于前一根看多')},
    'pta_wma': {'wma': Compare(-2, 1, label='高于前一根看多')},
    'pta_hma': {'hma': Compare(-2, 1, label='高于前一根看多')},
    'tv:supertrend': {'supertrend': Compare(-2, 1,
                                            label='高于前一根看多')},
}


def builtin_signals(key: str, overlap: bool = False) -> Dict[str, Any]:
    """目录 key → 内置信号表（没有就返回空 dict ✓）"""
    rows = BUILTIN_SIGNALS.get(str(key or ''))
    if rows:
        return dict(rows)
    return {}
