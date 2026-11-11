"""7.17 · tablestyle —— 指标自带的统计表格

演示要点
--------
``TableStyle`` 在图上放一个**可拖动的小表格**，行内容由一个钩子提供：

```python
def table_rows(self, index=None, values=None) -> [(标签, 值), ...]:
    ...
```

* ``self`` 是**算完的 IndFrame**（和 ``signal_text()`` 一样，取不到源 K 线的
  ``self.close`` —— 要价格就把它算成一列）；
* 读列值时**用 ``self.pandas_object['列名']``**（或钩子的 ``values`` 参数）：
  列名若和指标库的代理方法同名（``rsi`` / ``macd`` / ``cci`` …），
  ``self.rsi`` 会解析到**方法**而不是「这一列」；
* ``index`` 是十字光标所在 bar；``None`` = 没有光标（静态图 / 鼠标移出）；
* ``values`` 是桥接层现取的 ``{线名: 最新整条值}``（含 ``isplot=False`` 的列），
  实盘每次重算指标对象时用它更稳。

``TableStyle`` 字段见下表；``rows`` 留空时框架自动用类上的 ``table_rows()``。

运行：``python tutorials/styles/17_tablestyle.py``
文档：``minibt_docs/docs/minibt_styles/7.17_tablestyle.md``
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *
from minibt.utils import TableStyle      # 不在 __all__ 里，要显式导入


class RsiTable(BtIndicator):
    """RSI + 它的均线，左上角一个"RSI 状态"小表。"""

    lines = ('rsi', 'rsi_ma')
    overlap = False
    params = dict(LEN=14, MA=5)

    linestyle = dict(
        rsi=LineStyle(line_color=Colors.orange, line_width=1.6),
        rsi_ma=LineStyle(line_color=Colors.blue, line_width=1.2,
                         line_dash=LineDash.dashed),
    )

    # 表格：位置 / 尺寸 / 可拖动（rows 留空 → 用下面的 table_rows）
    tablestyle = TableStyle(
        position='top-left',
        headings=('指标', '值'),
        width=0.18,
        height=0.14,
        draggable=True,
        margin_x=80,
        margin_y=80,
    )

    def next(self):
        p = self.params
        rsi = self.close.rsi(p.LEN)
        return rsi, rsi.ema(p.MA)

    def table_rows(self, index=None, values=None):
        """返回 [(标签, 值), ...]；十字光标移动时跟着变。"""
        arr = (values or {}).get('rsi')
        if arr is None:
            # ⚠️ 不能用 self.rsi：`rsi` 同时是指标库的代理方法，
            #    属性会被方法遮蔽（取到的是 method）→ 用 pandas_object 取列
            arr = self.pandas_object['rsi']
        arr = np.asarray(arr, dtype=float).ravel()
        if index is None:
            i = len(arr) - 1
        else:
            i = max(0, min(int(index), len(arr) - 1))
        value = float(arr[i])
        if value != value:                       # NaN
            state = '—'
        elif value >= 70:
            state = '超买'
        elif value <= 30:
            state = '超卖'
        else:
            state = '中性'
        return [('RSI(14)', f'{value:.2f}'), ('状态', state)]


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = RsiTable(kline)
    print('tablestyle =', ind.plotinfo.tablestyle)
    # 钩子被绑到 plotinfo.table_rows（不是 IndFrame 的属性）
    hook = ind.plotinfo.table_rows
    print('表格行（最后一根）=', hook() if callable(hook) else None)
    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
