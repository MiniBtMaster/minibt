# -*- coding: utf-8 -*-
"""StyleZoo_Table —— **动态统计表格**样例（`tablestyle` + `table_rows()` ✓）

和 `style_zoo_osc.py` 的静态表格区别：
* 静态：`tablestyle = TableStyle(headings=(...), rows=((...), ...))`
* 动态：类上写 `tablestyle = TableStyle(header='…')`，再实现
  ``def table_rows(self, index=None, values=None) -> [(标签, 值), ...]``
  —— 表格内容每次刷新时按**当前数据**重算（`tradingview` 系列指标
  用它显示形态名 / 状态 ✓）

desk 会把钩子绑到 `IndFrame` 上调用（`self` = IndFrame，可读 `self['列名']`）。
"""
from __future__ import annotations

import numpy as np

from minibt import BtIndicator
from minibt.utils import Colors, LineStyle, TableStyle


def _sma(values, length: int):
    length = max(1, int(length))
    out = np.full(values.shape[0], np.nan)
    if values.shape[0] >= length:
        out[length - 1:] = np.convolve(
            values, np.ones(length) / length, mode='valid')
    return out


class StyleZoo_Table(BtIndicator):
    """动态表格：显示最新价 / 均线 / 偏离 / 当前方向"""

    lines = ('ma_fast', 'ma_slow', 'dev')
    params = dict(fast=10, slow=30)
    overlap = dict(ma_fast=True, ma_slow=True, dev=False)

    linestyle = dict(
        ma_fast=LineStyle(line_color=Colors.lime, line_width=2),
        ma_slow=LineStyle(line_color=Colors.tomato, line_width=2,
                          price_line=False),
        dev=LineStyle(line_color='#2196f3', line_width=1,
                      price_line=False),
    )

    #: 只给表头 / 位置，**内容**由 `table_rows()` 动态生成 ✓
    tablestyle = TableStyle(header='StyleZoo_Table', position='top-right')

    def next(self):
        close = np.asarray(self.close.values, dtype=float)
        fast = _sma(close, self.params.fast)
        slow = _sma(close, self.params.slow)
        dev = close / np.where(slow != 0, slow, np.nan) - 1.0
        return fast, slow, dev

    def table_rows(self, index=None, values=None):
        """返回 `[(标签, 值), …]`；**支持鼠标那根**（`index` = 行号 ✓）

        desk 的「表格跟随鼠标」会把鼠标所在那根的下标传进来：

        * `index is None` → 最后一根（实时 / 鼠标离开时 ✓）
        * `index = N`     → 第 N 根（鼠标在第 N 根 K 线上 ✓）

        所以**必须**按 `index` 取列值（只取 `[-1]` 的话表格永远是最后一根 ✗）。
        """
        def _at(name, row):
            try:
                column = np.asarray(self[name].values, dtype=float)
                return float(column[row])
            except Exception:                                    # noqa: BLE001
                return float('nan')

        try:
            size = len(self['ma_fast'].values)
        except Exception:                                        # noqa: BLE001
            size = 0
        row = -1 if index is None else int(index)
        if size and not (-size <= row < size):
            row = -1
        fast = _at('ma_fast', row)
        slow = _at('ma_slow', row)
        dev = _at('dev', row)
        trend = '多头' if fast == fast and slow == slow and fast > slow else '空头'
        return [
            ('序号', '最后' if index is None else f'#{int(index)}'),
            ('快线', f'{fast:.2f}'),
            ('慢线', f'{slow:.2f}'),
            ('偏离', f'{dev * 100:+.2f}%'),
            ('方向', trend),
        ]
