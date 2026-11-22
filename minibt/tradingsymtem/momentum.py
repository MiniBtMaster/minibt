"""momentum 交易系统（`kline.tradingsystem.momentum.` 的补全来源）。

RSI / MACD / 随机指标等动能类。本文件由两部分组成：

* **生成区** —— `# <ts-entries:begin>` ~ `# <ts-entries:end>`：
  由 `scripts/gen_trading_systems.py` 把 `tradingsystem.py` 的 `SYSTEMS`
  规则表展开成**真实方法**（`def` 而不是运行时 `type()` 挂属性）——
  这样编辑器在 `kline.tradingsystem.momentum.` 后面能**补全方法名**、
  悬停能看中文文档、`help(Momentum)` 也有内容 ✓
  **别手改生成区**：改完规则表跑
  `py -3.12 scripts/gen_trading_systems.py --write`；
* **手写区**（标记外面）：随便加方法 / `TradingSystemBase` 子类，
  重新生成不会覆盖（示例见 `trend.py` 的 `kama_trend`）✓

两类入口都**只算值、不画线**：

* 交易系统：`kline.tradingsystem.momentum.<系统>(...)`
  → 只有 `long_signal` / `short_signal` 两列信号；
* 底层指标：`kline.tradingsystem.momentum.<指标>(...)`（`LIB_INDICATORS`）
  → 直接返回 `pd.Series`（多输出返回 tuple）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 只给编辑器 / 类型检查用，运行时不 import ✓
    import pandas as pd

    from .base import TradingSystemBase


from .tradingsystem import _generated_category

#: (底层指标名, 输出数)：`1` → 返回 `pd.Series`；`>1` → 返回 tuple
LIB_INDICATORS = (
    ('ao', 1),
    ('apo', 1),
    ('cci', 1),
    ('kdj', 3),
    ('macd', 3),
    ('roc', 1),
    ('rsi', 1),
    ('stoch', 2),
    ('ultosc', 3),
    ('willr', 1),
)


class Momentum(_generated_category('momentum', LIB_INDICATORS)):
    """动量指标交易系统（RSI / MACD / 随机指标等）"""

    # <ts-entries:begin>  ← scripts/gen_trading_systems.py 生成，勿手改 ✓（手写方法放在标记外面）

    # ------------------------------ 交易系统（只出信号）
    def cci_zero(self, length: int = 20, **params) -> TradingSystemBase:
        """CCI 零轴穿越（上穿 0 做多 / 下穿 0 做空）（交易系统：只出信号）"""
        return self._system('cci_zero', length=length)

    def macd_cross(self, fast: int = 12, slow: int = 26,
                         signal: int = 9, **params) -> TradingSystemBase:
        """MACD 金叉死叉（DIF 上穿 DEA 做多）（交易系统：只出信号）"""
        return self._system('macd_cross', fast=fast, slow=slow, signal=signal)

    def rsi_reversal(self, length: int = 14,
                           low: int = 30,
                           high: int = 70, **params) -> TradingSystemBase:
        """RSI 超买超卖（30 下做多 / 70 上做空）（交易系统：只出信号）"""
        return self._system('rsi_reversal', length=length, low=low, high=high)

    def stoch_cross(self, k: int = 14, d: int = 3,
                          **params) -> TradingSystemBase:
        """随机指标交叉（K 上穿 D 做多）（交易系统：只出信号）"""
        return self._system('stoch_cross', k=k, d=d)

    def willr_reversal(self, length: int = 14, **params) -> TradingSystemBase:
        """威廉指标反转（-80 下做多 / -20 上做空）（交易系统：只出信号）"""
        return self._system('willr_reversal', length=length)

    # ------------------------------ 底层指标取值（只算值、不出信号）
    def ao(self, **params) -> pd.Series:
        """底层指标 `ao` 取值入口：只算值、不出信号（1 条线）"""
        return self._lib('ao', 1)

    def apo(self, **params) -> pd.Series:
        """底层指标 `apo` 取值入口：只算值、不出信号（1 条线）"""
        return self._lib('apo', 1)

    def cci(self, length: int = 20, **params) -> pd.Series:
        """底层指标 `cci` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `cci_zero`）"""
        return self._lib('cci', 1, length=length)

    def kdj(self, **params) -> tuple[pd.Series, ...]:
        """底层指标 `kdj` 取值入口：只算值、不出信号（3 条线）"""
        return self._lib('kdj', 3)

    def macd(self, **params) -> tuple[pd.Series, ...]:
        """底层指标 `macd` 取值入口：只算值、不出信号（3 条线）（参数默认值取自 `macd_cross`）"""
        return self._lib('macd', 3)

    def roc(self, **params) -> pd.Series:
        """底层指标 `roc` 取值入口：只算值、不出信号（1 条线）"""
        return self._lib('roc', 1)

    def rsi(self, length: int = 14, **params) -> pd.Series:
        """底层指标 `rsi` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `rsi_reversal`）"""
        return self._lib('rsi', 1, length=length)

    def stoch(self, **params) -> tuple[pd.Series, ...]:
        """底层指标 `stoch` 取值入口：只算值、不出信号（2 条线）（参数默认值取自 `stoch_cross`）"""
        return self._lib('stoch', 2)

    def ultosc(self, **params) -> tuple[pd.Series, ...]:
        """底层指标 `ultosc` 取值入口：只算值、不出信号（3 条线）"""
        return self._lib('ultosc', 3)

    def willr(self, length: int = 14, **params) -> pd.Series:
        """底层指标 `willr` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `willr_reversal`）"""
        return self._lib('willr', 1, length=length)

    # <ts-entries:end>  ← 生成区结束

