"""volume 交易系统（`kline.tradingsystem.volume.` 的补全来源）。

量价关系（OBV / MFI / VWAP …）。本文件由两部分组成：

* **生成区** —— `# <ts-entries:begin>` ~ `# <ts-entries:end>`：
  由 `scripts/gen_trading_systems.py` 把 `tradingsystem.py` 的 `SYSTEMS`
  规则表展开成**真实方法**（`def` 而不是运行时 `type()` 挂属性）——
  这样编辑器在 `kline.tradingsystem.volume.` 后面能**补全方法名**、
  悬停能看中文文档、`help(Volume)` 也有内容 ✓
  **别手改生成区**：改完规则表跑
  `py -3.12 scripts/gen_trading_systems.py --write`；
* **手写区**（标记外面）：随便加方法 / `TradingSystemBase` 子类，
  重新生成不会覆盖（示例见 `trend.py` 的 `kama_trend`）✓

两类入口都**只算值、不画线**：

* 交易系统：`kline.tradingsystem.volume.<系统>(...)`
  → 只有 `long_signal` / `short_signal` 两列信号；
* 底层指标：`kline.tradingsystem.volume.<指标>(...)`（`LIB_INDICATORS`）
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
    ('mfi', 1),
    ('obv', 1),
    ('vwap', 1),
)


class Volume(_generated_category('volume', LIB_INDICATORS)):
    """成交量交易系统（OBV / MFI / VWAP 等）"""

    # <ts-entries:begin>  ← scripts/gen_trading_systems.py 生成，勿手改 ✓（手写方法放在标记外面）

    # ------------------------------ 交易系统（只出信号）
    def mfi_reversal(self, length: int = 14, **params) -> TradingSystemBase:
        """资金流量反转（20 下做多 / 80 上做空）（交易系统：只出信号）"""
        return self._system('mfi_reversal', length=length)

    def obv_trend(self, length: int = 20, **params) -> TradingSystemBase:
        """OBV 能量潮趋势（上穿自身均线做多）（交易系统：只出信号）"""
        return self._system('obv_trend', length=length)

    def vwap_cross(self, **params) -> TradingSystemBase:
        """价格穿越 VWAP（上穿做多 / 下穿做空）（交易系统：只出信号）"""
        return self._system('vwap_cross')

    # ------------------------------ 底层指标取值（只算值、不出信号）
    def mfi(self, length: int = 14, **params) -> pd.Series:
        """底层指标 `mfi` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `mfi_reversal`）"""
        return self._lib('mfi', 1, length=length)

    def obv(self, **params) -> pd.Series:
        """底层指标 `obv` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `obv_trend`）"""
        return self._lib('obv', 1)

    def vwap(self, **params) -> pd.Series:
        """底层指标 `vwap` 取值入口：只算值、不出信号（1 条线）（参数默认值取自 `vwap_cross`）"""
        return self._lib('vwap', 1)

    # <ts-entries:end>  ← 生成区结束

