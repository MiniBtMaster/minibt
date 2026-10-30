# -*- coding: utf-8 -*-
"""StyleZoo_VP —— **成交量分布（Volume Profile）** 样例（`vpstyle` ✓）

和 minibt 内置的 `RollingVolumeProfile` 同一套数据约定：

* `next()` 返回 **(K 线根数, 档数)** 的二维矩阵，列 = 等宽价格档；
* 第 i 行的价格区间 = `[min(low[i-price_bars+1:i+1]), max(high[...])]`；
* 值 = 窗口内落在该档的**成交量之和**。

★ 关键：成交量要按**每根 K 线的 `low~high` 区间摊开**（不是只按收盘价）
—— 只按收盘价摊，40 档里大量档位是 0，画出来就是**断断续续的柱** ✗；
按 `low~high` 均匀摊，档档都有量，才是 minibt 那种连续的分布图 ✓

desk 会把它画成**右侧横向直方图**（POC 档高亮、贴可视区右边缘、鼠标跟随）。
"""
from __future__ import annotations

import numpy as np

from minibt import BtIndicator
from minibt.utils import Colors, VPStyle


class StyleZoo_VP(BtIndicator):
    """滚动成交量分布（自实现，便于改参数看效果）"""

    BINS = 40
    #: ★ VP 指标**必须**声明 40 条线（框架按 `lines` 数量校验二维矩阵的列数 ✓）
    lines = tuple(f'vp{j}' for j in range(40))
    params = dict(length=120, price_bars=120)
    overlap = True                 # VP 叠在主图右侧 ✓
    category = 'vp'                # ★ 关键：告诉渲染器"这是 VP 指标"

    #: `category='vp'` 的指标才读它；改颜色/粗细/长度都在这 ✓
    vpstyle = VPStyle(bar_color=Colors.skyblue, poc_color=Colors.orange,
                      fill_alpha=0.55, line_color='white', line_width=0.4,
                      profile_frac=0.30, bin_ratio=0.88)

    def next(self):
        close = np.asarray(self.close.values, dtype=float)
        high = np.asarray(self.high.values, dtype=float)
        low = np.asarray(self.low.values, dtype=float)
        volume = np.asarray(self.volume.values, dtype=float)
        size = close.shape[0]
        bins = int(self.BINS)
        window = int(self.params.price_bars)
        length = int(self.params.length)
        out = np.zeros((size, bins), dtype=float)
        for index in range(size):
            # 档区：最近 `price_bars` 根的 [min(low), max(high)]
            lo = low[max(0, index - window + 1):index + 1].min()
            hi = high[max(0, index - window + 1):index + 1].max()
            if not (hi > lo):
                continue
            step = (hi - lo) / bins
            start = max(0, index - length + 1)
            for k in range(start, index + 1):
                vol = volume[k]
                if not np.isfinite(vol) or vol <= 0:
                    continue
                # ★ 按该根的 low~high 区间**均匀摊量**（minibt 同款 ✓）
                k_lo = max(float(low[k]), lo)
                k_hi = min(float(high[k]), hi)
                if not (k_hi > k_lo):
                    # 一字板 / 区间退化 → 全部摊到收盘价所在档
                    slot = int((close[k] - lo) / step) if step > 0 else 0
                    slot = min(max(slot, 0), bins - 1)
                    out[index, slot] += vol
                    continue
                first = int((k_lo - lo) / step)
                last = int((k_hi - lo) / step)
                first = min(max(first, 0), bins - 1)
                last = min(max(last, first), bins - 1)
                span = last - first + 1
                out[index, first:last + 1] += vol / span
        return out
