"""performance 交易系统（`kline.tradingsystem.performance.` 的补全来源）。

表现类（ROC / APO …）。本文件由两部分组成：

* **生成区** —— `# <ts-entries:begin>` ~ `# <ts-entries:end>`：
  由 `scripts/gen_trading_systems.py` 把 `tradingsystem.py` 的 `SYSTEMS`
  规则表展开成**真实方法**（`def` 而不是运行时 `type()` 挂属性）——
  这样编辑器在 `kline.tradingsystem.performance.` 后面能**补全方法名**、
  悬停能看中文文档、`help(Performance)` 也有内容 ✓
  **别手改生成区**：改完规则表跑
  `py -3.12 scripts/gen_trading_systems.py --write`；
* **手写区**（标记外面）：随便加方法 / `TradingSystemBase` 子类，
  重新生成不会覆盖（示例见 `trend.py` 的 `kama_trend`）✓

两类入口都**只算值、不画线**：

* 交易系统：`kline.tradingsystem.performance.<系统>(...)`
  → 只有 `long_signal` / `short_signal` 两列信号；
* 底层指标：`kline.tradingsystem.performance.<指标>(...)`（`LIB_INDICATORS`）
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
    ('apo', 1),
    ('roc', 1),
)


class Performance(_generated_category('performance', LIB_INDICATORS)):
    """表现指标交易系统（ROC / APO 等）"""

    # <ts-entries:begin>  ← scripts/gen_trading_systems.py 生成，勿手改 ✓（手写方法放在标记外面）

    # ------------------------------ 交易系统（只出信号）
    def apo_momentum(self, fast: int = 12,
                           slow: int = 26, **params) -> TradingSystemBase:
        """APO 动量（快慢均线差过 0）（交易系统：只出信号）"""
        return self._system('apo_momentum', fast=fast, slow=slow)

    def roc_momentum(self, length: int = 10, **params) -> TradingSystemBase:
        """ROC 动量（>0 做多 / <0 做空）（交易系统：只出信号）"""
        return self._system('roc_momentum', length=length)

    # ------------------------------ 底层指标取值（只算值、不出信号）
    def apo(self, fast: int = 12, slow: int = 26, **params) -> pd.Series:
        """底层指标 `apo` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `apo_momentum`）"""
        return self._lib('apo', 1, fast=fast, slow=slow)

    def roc(self, length: int = 10, **params) -> pd.Series:
        """底层指标 `roc` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `roc_momentum`）"""
        return self._lib('roc', 1, length=length)

    # <ts-entries:end>  ← 生成区结束

