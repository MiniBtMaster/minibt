"""overlap 交易系统（`kline.tradingsystem.overlap.` 的补全来源）。

均线 / 通道类（价格与均线、通道上下轨的关系）。本文件由两部分组成：

* **生成区** —— `# <ts-entries:begin>` ~ `# <ts-entries:end>`：
  由 `scripts/gen_trading_systems.py` 把 `tradingsystem.py` 的 `SYSTEMS`
  规则表展开成**真实方法**（`def` 而不是运行时 `type()` 挂属性）——
  这样编辑器在 `kline.tradingsystem.overlap.` 后面能**补全方法名**、
  悬停能看中文文档、`help(Overlap)` 也有内容 ✓
  **别手改生成区**：改完规则表跑
  `py -3.12 scripts/gen_trading_systems.py --write`；
* **手写区**（标记外面）：随便加方法 / `TradingSystemBase` 子类，
  重新生成不会覆盖（示例见 `trend.py` 的 `kama_trend`）✓

两类入口都**只算值、不画线**：

* 交易系统：`kline.tradingsystem.overlap.<系统>(...)`
  → 只有 `long_signal` / `short_signal` 两列信号；
* 底层指标：`kline.tradingsystem.overlap.<指标>(...)`（`LIB_INDICATORS`）
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
    ('bbands', 3),
    ('donchian', 3),
    ('ema', 1),
    ('keltner', 3),
    ('sma', 1),
    ('wma', 1),
)


class Overlap(_generated_category('overlap', LIB_INDICATORS)):
    """重叠指标交易系统（均线 / 通道类）"""

    # <ts-entries:begin>  ← scripts/gen_trading_systems.py 生成，勿手改 ✓（手写方法放在标记外面）

    # ------------------------------ 交易系统（只出信号）
    def bbands_break(self, length: int = 20,
                           std: float = 2.0, **params) -> TradingSystemBase:
        """布林带突破（上轨追多 / 下轨追空）（交易系统：只出信号）"""
        return self._system('bbands_break', length=length, std=std)

    def donchian_break(self, length: int = 20, **params) -> TradingSystemBase:
        """唐奇安通道突破（20 期新高做多 / 新低做空）（交易系统：只出信号）"""
        return self._system('donchian_break', length=length)

    def ema_trend(self, length: int = 20, **params) -> TradingSystemBase:
        """价格与 EMA 趋势（站上看多 / 跌破看空）（交易系统：只出信号）"""
        return self._system('ema_trend', length=length)

    def ma_cross(self, fast: int = 5, slow: int = 20,
                       **params) -> TradingSystemBase:
        """双均线交叉（金叉做多 / 死叉做空）（交易系统：只出信号）"""
        return self._system('ma_cross', fast=fast, slow=slow)

    # ------------------------------ 底层指标取值（只算值、不出信号）
    def bbands(self, length: int = 20,
                     std: float = 2.0, **params) -> tuple[pd.Series, ...]:
        """底层指标 `bbands` 取值入口：只算值、不出信号（3 条线）（参数默认值取自 `bbands_break`）"""
        return self._lib('bbands', 3, length=length, std=std)

    def donchian(self, length: int = 20, **params) -> tuple[pd.Series, ...]:
        """底层指标 `donchian` 取值入口：只算值、不出信号（3 条线）（参数默认值取自 `donchian_break`）"""
        return self._lib('donchian', 3, length=length)

    def ema(self, length: int = 20, **params) -> pd.Series:
        """底层指标 `ema` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `ema_trend`）"""
        return self._lib('ema', 1, length=length)

    def keltner(self, **params) -> tuple[pd.Series, ...]:
        """底层指标 `keltner` 取值入口：只算值、不出信号（3 条线）"""
        return self._lib('keltner', 3)

    def sma(self, length: int = 20, **params) -> pd.Series:
        """底层指标 `sma` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `ma_cross`）"""
        return self._lib('sma', 1, length=length)

    def wma(self, **params) -> pd.Series:
        """底层指标 `wma` 取值入口：只算值、不出信号（1 条线）"""
        return self._lib('wma', 1)

    # <ts-entries:end>  ← 生成区结束

