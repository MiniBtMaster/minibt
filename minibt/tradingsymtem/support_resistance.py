"""support_resistance 交易系统（`kline.tradingsystem.support_resistance.` 的补全来源）。

支撑阻力（唐奇安 / 布林中轨 …）。本文件由两部分组成：

* **生成区** —— `# <ts-entries:begin>` ~ `# <ts-entries:end>`：
  由 `scripts/gen_trading_systems.py` 把 `tradingsystem.py` 的 `SYSTEMS`
  规则表展开成**真实方法**（`def` 而不是运行时 `type()` 挂属性）——
  这样编辑器在 `kline.tradingsystem.support_resistance.` 后面能**补全方法名**、
  悬停能看中文文档、`help(SupportResistance)` 也有内容 ✓
  **别手改生成区**：改完规则表跑
  `py -3.12 scripts/gen_trading_systems.py --write`；
* **手写区**（标记外面）：随便加方法 / `TradingSystemBase` 子类，
  重新生成不会覆盖（示例见 `trend.py` 的 `kama_trend`）✓

两类入口都**只算值、不画线**：

* 交易系统：`kline.tradingsystem.support_resistance.<系统>(...)`
  → 只有 `long_signal` / `short_signal` 两列信号；
* 底层指标：`kline.tradingsystem.support_resistance.<指标>(...)`（`LIB_INDICATORS`）
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
)


class SupportResistance(_generated_category('support_resistance', LIB_INDICATORS)):
    """支撑阻力交易系统（唐奇安 / 布林中轨等）"""

    # <ts-entries:begin>  ← scripts/gen_trading_systems.py 生成，勿手改 ✓（手写方法放在标记外面）

    # ------------------------------ 交易系统（只出信号）
    def bbands_sr(self, length: int = 20,
                        std: float = 2.0, **params) -> TradingSystemBase:
        """布林中轨穿越（站上做多 / 跌破做空）（交易系统：只出信号）"""
        return self._system('bbands_sr', length=length, std=std)

    def donchian_sr(self, length: int = 20, **params) -> TradingSystemBase:
        """前高前低穿越（做多 / 做空）（交易系统：只出信号）"""
        return self._system('donchian_sr', length=length)

    # ------------------------------ 底层指标取值（只算值、不出信号）
    def bbands(self, length: int = 20,
                     std: float = 2.0, **params) -> tuple[pd.Series, ...]:
        """底层指标 `bbands` 取值入口：只算值、不出信号（3 条线）（参数默认值取自 `bbands_sr`）"""
        return self._lib('bbands', 3, length=length, std=std)

    def donchian(self, length: int = 20, **params) -> tuple[pd.Series, ...]:
        """底层指标 `donchian` 取值入口：只算值、不出信号（3 条线）（参数默认值取自 `donchian_sr`）"""
        return self._lib('donchian', 3, length=length)

    # <ts-entries:end>  ← 生成区结束

