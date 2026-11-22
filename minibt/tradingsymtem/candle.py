"""candle 交易系统（`kline.tradingsystem.candle.` 的补全来源）。

蜡烛形态（吞没 / 十字星 …）。本文件由两部分组成：

* **生成区** —— `# <ts-entries:begin>` ~ `# <ts-entries:end>`：
  由 `scripts/gen_trading_systems.py` 把 `tradingsystem.py` 的 `SYSTEMS`
  规则表展开成**真实方法**（`def` 而不是运行时 `type()` 挂属性）——
  这样编辑器在 `kline.tradingsystem.candle.` 后面能**补全方法名**、
  悬停能看中文文档、`help(Candle)` 也有内容 ✓
  **别手改生成区**：改完规则表跑
  `py -3.12 scripts/gen_trading_systems.py --write`；
* **手写区**（标记外面）：随便加方法 / `TradingSystemBase` 子类，
  重新生成不会覆盖（示例见 `trend.py` 的 `kama_trend`）✓

两类入口都**只算值、不画线**：

* 交易系统：`kline.tradingsystem.candle.<系统>(...)`
  → 只有 `long_signal` / `short_signal` 两列信号；
* 底层指标：`kline.tradingsystem.candle.<指标>(...)`（`LIB_INDICATORS`）
  → 直接返回 `pd.Series`（多输出返回 tuple）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 只给编辑器 / 类型检查用，运行时不 import ✓
    import pandas as pd

    from .base import TradingSystemBase


from .tradingsystem import _generated_category

#: 蜡烛图形态直接用 OHLC，不在 `LIB_TABLE` 里 → 没有底层取值入口
LIB_INDICATORS = ()


class Candle(_generated_category('candle', LIB_INDICATORS)):
    """蜡烛图交易系统（吞没 / 十字星等）"""

    # <ts-entries:begin>  ← scripts/gen_trading_systems.py 生成，勿手改 ✓（手写方法放在标记外面）

    # ------------------------------ 交易系统（只出信号）
    def doji_reversal(self, body: float = 0.1, **params) -> TradingSystemBase:
        """十字星反转（实体极小 + 位置极端）（交易系统：只出信号）"""
        return self._system('doji_reversal', body=body)

    def engulfing_signal(self, length: int = 9,
                               **params) -> TradingSystemBase:
        """吞没形态 + 趋势过滤（做多 / 做空）（交易系统：只出信号）"""
        return self._system('engulfing_signal', length=length)

    # <ts-entries:end>  ← 生成区结束

