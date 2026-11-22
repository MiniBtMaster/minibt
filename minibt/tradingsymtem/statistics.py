"""statistics 交易系统（`kline.tradingsystem.statistics.` 的补全来源）。

统计类（Z 分数 / 分位数 / 相关性 …）。本文件由两部分组成：

* **生成区** —— `# <ts-entries:begin>` ~ `# <ts-entries:end>`：
  由 `scripts/gen_trading_systems.py` 把 `tradingsystem.py` 的 `SYSTEMS`
  规则表展开成**真实方法**（`def` 而不是运行时 `type()` 挂属性）——
  这样编辑器在 `kline.tradingsystem.statistics.` 后面能**补全方法名**、
  悬停能看中文文档、`help(Statistics)` 也有内容 ✓
  **别手改生成区**：改完规则表跑
  `py -3.12 scripts/gen_trading_systems.py --write`；
* **手写区**（标记外面）：随便加方法 / `TradingSystemBase` 子类，
  重新生成不会覆盖（示例见 `trend.py` 的 `kama_trend`）✓

两类入口都**只算值、不画线**：

* 交易系统：`kline.tradingsystem.statistics.<系统>(...)`
  → 只有 `long_signal` / `short_signal` 两列信号；
* 底层指标：`kline.tradingsystem.statistics.<指标>(...)`（`LIB_INDICATORS`）
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
    ('rsi', 1),
    ('zscore', 1),
)


class Statistics(_generated_category('statistics', LIB_INDICATORS)):
    """统计指标交易系统（Z 分数 / 分位数等）"""

    # <ts-entries:begin>  ← scripts/gen_trading_systems.py 生成，勿手改 ✓（手写方法放在标记外面）

    # ------------------------------ 交易系统（只出信号）
    def rank_extreme(self, length: int = 20, **params) -> TradingSystemBase:
        """分位极端（排名靠低做多 / 靠高做空）（交易系统：只出信号）"""
        return self._system('rank_extreme', length=length)

    def zscore_reversal(self, length: int = 20,
                              **params) -> TradingSystemBase:
        """Z 分数反转（-2 下做多 / +2 上做空）（交易系统：只出信号）"""
        return self._system('zscore_reversal', length=length)

    # ------------------------------ 底层指标取值（只算值、不出信号）
    def rsi(self, length: int = 20, **params) -> pd.Series:
        """底层指标 `rsi` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `rank_extreme`）"""
        return self._lib('rsi', 1, length=length)

    def zscore(self, length: int = 20, **params) -> pd.Series:
        """底层指标 `zscore` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `zscore_reversal`）"""
        return self._lib('zscore', 1, length=length)

    # <ts-entries:end>  ← 生成区结束

