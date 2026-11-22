"""Alpha101 / Alpha191 因子（vendor 自 `py-alpha-lib` 官方示例，BSD-2-Clause）

* `wq101.py` / `gtja191.py` —— **原样 vendor 的因子函数**（别手改）；
* `registry.py` —— 编号 / 公式 / 类型（纯时序 / 横截面 / 缺外部数据）；
* `context.py` —— 单标的 K 线 → 面板 DataFrame，复用上游 `ExecContext` ✓

入口：

* 指标：`self.data.af.alpha191_002()`（138 个纯时序因子）；
* 参数化：`self.data.af.alpha101(no=6)` / `alpha191(no=191)`；
* 研究：`minibt.factor.panel(df, 'wq101', 101)`（横截面因子）。

`py-alpha-lib` 是**可选依赖**：没装时本包只在真正调用因子时才报可读错误，
`import minibt` 完全不受影响 ✓
"""
from __future__ import annotations

from .context import (available, compute_series, compute_values, factor_frame,
                      factor_info, panel_values)
from .registry import CROSS_NUMBERS, EXTERNAL_NUMBERS, FACTORS, FAMILIES, \
    TS_NUMBERS

__all__ = ['FACTORS', 'FAMILIES', 'TS_NUMBERS', 'CROSS_NUMBERS',
           'EXTERNAL_NUMBERS', 'factor_frame', 'factor_info',
           'compute_values', 'compute_series', 'panel_values', 'available']
