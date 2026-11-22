"""cycle 交易系统（`kline.tradingsystem.cycle.` 的补全来源）。

周期类（DPO / 周期检测 …）。本文件由两部分组成：

* **生成区** —— `# <ts-entries:begin>` ~ `# <ts-entries:end>`：
  由 `scripts/gen_trading_systems.py` 把 `tradingsystem.py` 的 `SYSTEMS`
  规则表展开成**真实方法**（`def` 而不是运行时 `type()` 挂属性）——
  这样编辑器在 `kline.tradingsystem.cycle.` 后面能**补全方法名**、
  悬停能看中文文档、`help(Cycle)` 也有内容 ✓
  **别手改生成区**：改完规则表跑
  `py -3.12 scripts/gen_trading_systems.py --write`；
* **手写区**（标记外面）：随便加方法 / `TradingSystemBase` 子类，
  重新生成不会覆盖（示例见 `trend.py` 的 `kama_trend`）✓

两类入口都**只算值、不画线**：

* 交易系统：`kline.tradingsystem.cycle.<系统>(...)`
  → 只有 `long_signal` / `short_signal` 两列信号；
* 底层指标：`kline.tradingsystem.cycle.<指标>(...)`（`LIB_INDICATORS`）
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
    ('dpo', 1),
    ('roc', 1),
)


class Cycle(_generated_category('cycle', LIB_INDICATORS)):
    """周期指标交易系统（DPO / ROC 等）"""

    # <ts-entries:begin>  ← scripts/gen_trading_systems.py 生成，勿手改 ✓（手写方法放在标记外面）

    # ------------------------------ 交易系统（只出信号）
    def dpo_turn(self, length: int = 20, **params) -> TradingSystemBase:
        """DPO 过零（上穿 0 做多 / 下穿 0 做空）（交易系统：只出信号）"""
        return self._system('dpo_turn', length=length)

    def roc_cycle(self, length: int = 10, **params) -> TradingSystemBase:
        """ROC 动能拐头（动量转正做多 / 转负做空）（交易系统：只出信号）"""
        return self._system('roc_cycle', length=length)

    # ------------------------------ 底层指标取值（只算值、不出信号）
    def dpo(self, length: int = 20, **params) -> pd.Series:
        """底层指标 `dpo` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `dpo_turn`）"""
        return self._lib('dpo', 1, length=length)

    def roc(self, length: int = 10, **params) -> pd.Series:
        """底层指标 `roc` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `roc_cycle`）"""
        return self._lib('roc', 1, length=length)

    # <ts-entries:end>  ← 生成区结束

