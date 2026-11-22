# -*- coding: utf-8 -*-
"""StyleZoo_Func — **函数式**指标（对照用）

函数式指标只返回数据（Series / DataFrame），**写不了 PlotInfo 样式**：
* 多列 → 图表按**调色板**给每列不同颜色（`personal.py` 里那 8 个色）✓
* 单一颜色 / 叠加方式只能在菜单里用 `__desk_indicator__` 指定：
  ``__desk_indicator__ = {'label': ..., 'overlap': True}``

用它和 `StyleZoo_Main` 对比：类式（`BtIndicator`）能带全套样式，函数式只有颜色 ✓
"""
from __future__ import annotations

import pandas as pd


def StyleZoo_Func(frame, fast: int = 20, slow: int = 100):
    """四条均线（多列 → 自动配色）"""
    close = pd.to_numeric(frame['close'], errors='coerce')
    ma_fast = close.rolling(int(fast)).mean()
    ma_slow = close.rolling(int(slow)).mean()
    diff = ma_fast - ma_slow
    return pd.DataFrame({
        'fast': ma_fast,
        'slow': ma_slow,
        'diff': diff,
        'diff_ma': diff.rolling(5).mean(),
    })


__desk_indicator__ = {'label': 'StyleZoo 函数式', 'overlap': dict(fast=True,slow=True,diff=False,diff_ma=False)}
