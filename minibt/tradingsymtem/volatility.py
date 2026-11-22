"""volatility 交易系统（`kline.tradingsystem.volatility.` 的补全来源）。

波动率与通道宽度（ATR / 肯特纳 / Z 分数 …）。本文件由两部分组成：

* **生成区** —— `# <ts-entries:begin>` ~ `# <ts-entries:end>`：
  由 `scripts/gen_trading_systems.py` 把 `tradingsystem.py` 的 `SYSTEMS`
  规则表展开成**真实方法**（`def` 而不是运行时 `type()` 挂属性）——
  这样编辑器在 `kline.tradingsystem.volatility.` 后面能**补全方法名**、
  悬停能看中文文档、`help(Volatility)` 也有内容 ✓
  **别手改生成区**：改完规则表跑
  `py -3.12 scripts/gen_trading_systems.py --write`；
* **手写区**（标记外面）：随便加方法 / `TradingSystemBase` 子类，
  重新生成不会覆盖（示例见 `trend.py` 的 `kama_trend`）✓

两类入口都**只算值、不画线**：

* 交易系统：`kline.tradingsystem.volatility.<系统>(...)`
  → 只有 `long_signal` / `short_signal` 两列信号；
* 底层指标：`kline.tradingsystem.volatility.<指标>(...)`（`LIB_INDICATORS`）
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
    ('atr', 1),
    ('keltner', 3),
    ('zscore', 1),
)


class Volatility(_generated_category('volatility', LIB_INDICATORS)):
    """波动率交易系统（布林带 / 肯特纳 / ATR 等）"""

    # <ts-entries:begin>  ← scripts/gen_trading_systems.py 生成，勿手改 ✓（手写方法放在标记外面）

    # ------------------------------ 交易系统（只出信号）
    def atr_rising(self, length: int = 14, **params) -> TradingSystemBase:
        """ATR 抬头 = 波动放大（放大做多 / 收缩做空）（交易系统：只出信号）"""
        return self._system('atr_rising', length=length)

    def keltner_break(self, length: int = 20,
                            multiplier: float = 2.0,
                            **params) -> TradingSystemBase:
        """肯特纳通道突破（EMA ± ATR 带）（交易系统：只出信号）"""
        return self._system('keltner_break', length=length, multiplier=multiplier)

    def zscore_band(self, length: int = 20,
                          z: float = 2.0, **params) -> TradingSystemBase:
        """Z 分数极端反转（|z|>2 反向）（交易系统：只出信号）"""
        return self._system('zscore_band', length=length, z=z)

    # ------------------------------ 底层指标取值（只算值、不出信号）
    def atr(self, length: int = 14, **params) -> pd.Series:
        """底层指标 `atr` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `atr_rising`）"""
        return self._lib('atr', 1, length=length)

    def keltner(self, period: int = 20,
                      multiplier: float = 2.0,
                      **params) -> tuple[pd.Series, ...]:
        """底层指标 `keltner` 取值入口：只算值、不出信号（3 条线）（参数默认值取自 `keltner_break`）"""
        return self._lib('keltner', 3, period=period, multiplier=multiplier)

    def zscore(self, length: int = 20, **params) -> pd.Series:
        """底层指标 `zscore` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `zscore_band`）"""
        return self._lib('zscore', 1, length=length)

    # <ts-entries:end>  ← 生成区结束

