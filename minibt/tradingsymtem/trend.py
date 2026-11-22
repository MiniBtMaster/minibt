"""trend 交易系统（`kline.tradingsystem.trend.` 的补全来源）。

趋势方向与强度（ADX / Aroon / Supertrend / KAMA …）。本文件由两部分组成：

* **生成区** —— `# <ts-entries:begin>` ~ `# <ts-entries:end>`：
  由 `scripts/gen_trading_systems.py` 把 `tradingsystem.py` 的 `SYSTEMS`
  规则表展开成**真实方法**（`def` 而不是运行时 `type()` 挂属性）——
  这样编辑器在 `kline.tradingsystem.trend.` 后面能**补全方法名**、
  悬停能看中文文档、`help(Trend)` 也有内容 ✓
  **别手改生成区**：改完规则表跑
  `py -3.12 scripts/gen_trading_systems.py --write`；
* **手写区**（标记外面）：随便加方法 / `TradingSystemBase` 子类，
  重新生成不会覆盖（示例见 `trend.py` 的 `kama_trend`）✓

两类入口都**只算值、不画线**：

* 交易系统：`kline.tradingsystem.trend.<系统>(...)`
  → 只有 `long_signal` / `short_signal` 两列信号；
* 底层指标：`kline.tradingsystem.trend.<指标>(...)`（`LIB_INDICATORS`）
  → 直接返回 `pd.Series`（多输出返回 tuple）。
"""

from __future__ import annotations


import pandas as pd

from .base import TradingSystemBase, _as_series
from .tradingsystem import _generated_category

#: (底层指标名, 输出数)：`1` → 返回 `pd.Series`；`>1` → 返回 tuple
LIB_INDICATORS = (
    ('adx', 1),
    ('aroon', 2),
    ('di', 2),
    ('kama', 1),
    ('psar', 1),
    ('supertrend', 1),
    ('trix', 1),
)


class KAMATrend(TradingSystemBase):
    """KAMA 自适应均线趋势（价格上穿做多 / 下穿做空）示例。

    参数:
        length: KAMA 周期（默认 10）
    """

    params = {'length': 10}  # noqa: RUF012

    def next(self):
        length = int(self.params.get('length', 10))
        kama = TradingSystemBase.lib(self, 'kama', length=length)
        close = TradingSystemBase.lib(self, 'close')
        long_, short_ = TradingSystemBase.cross(close, kama)
        long_ = _as_series(long_, self, fill=0.0)
        short_ = _as_series(short_, self, fill=0.0)
        both = (long_ > 0) & (short_ > 0)
        if bool(both.any()):
            long_ = long_.where(~both, 0.0)
            short_ = short_.where(~both, 0.0)
        return pd.DataFrame({'long_signal': long_, 'short_signal': short_})


class PSARTrend(TradingSystemBase):
    """抛物线 SAR 趋势（价格上穿做多 / 下穿做空）示例。

    参数:
        acceleration: 加速因子（默认 0.02）
        maximum: 最大加速因子（默认 0.2）
    """

    params = {'acceleration': 0.02, 'maximum': 0.2}  # noqa: RUF012

    def next(self):
        acceleration = float(self.params.get('acceleration', 0.02))
        maximum = float(self.params.get('maximum', 0.2))
        psar = TradingSystemBase.lib(self, 'psar',
                                     acceleration=acceleration,
                                     maximum=maximum)
        close = TradingSystemBase.lib(self, 'close')
        long_, short_ = TradingSystemBase.cross(close, psar)
        long_ = _as_series(long_, self, fill=0.0)
        short_ = _as_series(short_, self, fill=0.0)
        both = (long_ > 0) & (short_ > 0)
        if bool(both.any()):
            long_ = long_.where(~both, 0.0)
            short_ = short_.where(~both, 0.0)
        return pd.DataFrame({'long_signal': long_, 'short_signal': short_})


class Trend(_generated_category('trend', LIB_INDICATORS)):
    """趋势类交易系统（显式方法 → IDE 可补全 ✓）。

    内置：``adx_trend`` / ``aroon_trend`` / ``trix_signal`` /
    ``supertrend_follow``；下面是两个扩展示例：

    >>> kline.tradingsystem.trend.kama_trend(length=10)
    >>> kline.tradingsystem.trend.psar_trend(acceleration=0.02, maximum=0.2)
    """

    # <ts-entries:begin>  ← scripts/gen_trading_systems.py 生成，勿手改 ✓（手写方法放在标记外面）

    # ------------------------------ 交易系统（只出信号）
    def adx_trend(self, length: int = 14,
                        threshold: int = 20, **params) -> TradingSystemBase:
        """ADX 趋势过滤（ADX>20 且 +DI>-DI 做多）（交易系统：只出信号）"""
        return self._system('adx_trend', length=length, threshold=threshold)

    def aroon_trend(self, length: int = 25, **params) -> TradingSystemBase:
        """Aroon 趋势（Aroon Up 上穿 Down 做多）（交易系统：只出信号）"""
        return self._system('aroon_trend', length=length)

    def supertrend_follow(self, length: int = 10,
                                multiplier: float = 3.0,
                                **params) -> TradingSystemBase:
        """Supertrend 抬头（趋势线抬升做多 / 回落做空）（交易系统：只出信号）"""
        return self._system('supertrend_follow', length=length, multiplier=multiplier)

    def trix_signal(self, length: int = 10,
                          signal: int = 9, **params) -> TradingSystemBase:
        """TRIX 动能（上穿自身均线做多）（交易系统：只出信号）"""
        return self._system('trix_signal', length=length, signal=signal)

    # ------------------------------ 底层指标取值（只算值、不出信号）
    def adx(self, length: int = 14, **params) -> pd.Series:
        """底层指标 `adx` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `adx_trend`）"""
        return self._lib('adx', 1, length=length)

    def aroon(self, length: int = 25, **params) -> tuple[pd.Series, ...]:
        """底层指标 `aroon` 取值入口：只算值、不出信号（2 条线）（参数默认值取自 `aroon_trend`）"""
        return self._lib('aroon', 2, length=length)

    def di(self, length: int = 14, **params) -> tuple[pd.Series, ...]:
        """底层指标 `di` 取值入口：只算值、不出信号（2 条线）（参数默认值取自 `adx_trend`）"""
        return self._lib('di', 2, length=length)

    def kama(self, length: int = 10, **params) -> pd.Series:
        """底层指标 `kama` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `kama_trend`）"""
        return self._lib('kama', 1, length=length)

    def psar(self, acceleration: float = 0.02,
                   maximum: float = 0.2, **params) -> pd.Series:
        """底层指标 `psar` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `psar_trend`）"""
        return self._lib('psar', 1, acceleration=acceleration, maximum=maximum)

    def supertrend(self, period: int = 10,
                         multiplier: float = 3.0, **params) -> pd.Series:
        """底层指标 `supertrend` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `supertrend_follow`）"""
        return self._lib('supertrend', 1, period=period, multiplier=multiplier)

    def trix(self, length: int = 10, **params) -> pd.Series:
        """底层指标 `trix` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `trix_signal`）"""
        return self._lib('trix', 1, length=length)

    # <ts-entries:end>  ← 生成区结束

    def kama_trend(self, length: int = 10):
        """KAMA 自适应均线趋势（价格上穿做多 / 下穿做空）"""
        return KAMATrend(self._data, length=length)

    def psar_trend(self, acceleration: float = 0.02,
                   maximum: float = 0.2):
        """抛物线 SAR 趋势（价格上穿做多 / 下穿做空）"""
        return PSARTrend(self._data, acceleration=acceleration,
                         maximum=maximum)
