# -*- coding: utf-8 -*-
"""StyleZoo_Osc — **副图样式**测试指标（柱状 / 横线 / 统计表）

| 样式 | 用法 | 图上应该看到 |
| --- | --- | --- |
| `LineDash.vbar` | `hist` 线 | 红绿柱（`vbar_base=0` + `vbar_up/down_color`） |
| `linestyle` 普通线 | `k` 实线 / `d` 虚线 | 蓝实线 + 红虚线（0~100 刻度） |
| `isplot=False` | `raw` 列 | **看不到**这条线（只是数据列） |
| `spanstyle` | 0 / 30 / 50 / 70 | 副图里四条水平参考线 |
| `tablestyle` | `position='top-right'` | 图**右上角**一张统计表 |
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from minibt import BtIndicator
from minibt.utils import (
    Colors, LineDash, LineStyle, SpanStyle, TableStyle,
)


class StyleZoo_Osc(BtIndicator):
    """副图样式大全（柱状 + 参考线 + 隐藏列 + 右上角统计表）"""

    lines = ('k', 'd', 'hist', 'raw')
    params = dict(length=14)
    overlap = False

    linestyle = dict(
        k=LineStyle(line_color='#2196f3', line_width=2),
        d=LineStyle(line_color='#e91e63', line_width=1,
                    line_dash=LineDash.dashed),
        hist=LineStyle(line_dash=LineDash.vbar, vbar_base=0.0,
                       vbar_up_color=Colors.lime,
                       vbar_down_color=Colors.tomato,
                       price_line=False, price_label=False),
    )

    #: `raw` 只当数据列、不画 ✓
    isplot = dict(raw=False)

    #: 水平参考线（`PlotInfo.spanstyle` ✓）
    spanstyle = [SpanStyle(0.0, line_color='#666666', line_dash=LineDash.solid),
                 SpanStyle(30.0, line_color=Colors.green),
                 SpanStyle(50.0, line_color=Colors.blue,
                           line_dash=LineDash.dotted),
                 SpanStyle(70.0, line_color=Colors.red)]

    #: 统计表放**右上角**（左上角会被指标图例占住 ✓）
    tablestyle = TableStyle(
        position='top-right', draggable=True,
        header='StyleZoo 统计', footer='仅用于样式测试',
        headings=('项目', '值'),
        rows=[('快线周期', '14'), ('慢线周期', '5'),
              ('柱状基线', '0'), ('参考线', '0 / 30 / 50 / 70')])

    def next(self):
        close = np.asarray(self.close.values, dtype=float)
        high = np.asarray(self.high.values, dtype=float)
        low = np.asarray(self.low.values, dtype=float)
        length = max(2, int(self.params.length))
        # 随机指标 %K（0~100）+ 它的均线 → 刻度统一 ✓
        hh = pd.Series(high).rolling(length).max().to_numpy()
        ll = pd.Series(low).rolling(length).min().to_numpy()
        span = np.where(hh - ll == 0, np.nan, hh - ll)
        k = np.clip((close - ll) / span * 100.0, 0.0, 100.0)
        d = pd.Series(k).rolling(max(2, length // 3)).mean().to_numpy()
        hist = k - d                          # 围绕 0 的柱状 ✓
        raw = close - pd.Series(close).rolling(length).mean().to_numpy()
        return k, d, hist, raw
