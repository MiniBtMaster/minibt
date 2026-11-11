"""7.11 · signal_texts / signal_text() —— 每根信号写不同文字

演示要点
--------
``SignalStyle.label`` 只能给一个**固定**文字（所有信号都写 ``'B'``）。要让每根
信号写**不同**内容（价格、编号、形态名…），用 ``signal_text()`` 钩子：

```python
def signal_text(self) -> dict | None:
    return {'long_signal': [文本或 np.nan, ...],   # 长度 = K 线根数
            'short_signal': [...]}
```

* 返回 ``{信号线名: 数组}``，数组里 ``np.nan`` 表示**这一根不写字**；
* 也可以返回 ``None``，在方法里用 ``self.signaltext.set_signal(...)`` 就地写；
* 计算完的指标对象会自动收口，**静态派生一次**即可。

⚠️ **``signal_text()`` 里的 ``self`` 是「算完的指标」（IndFrame），不是源 K 线**
——所以 ``self.close`` 取不到（`AttributeError`）。要用价格，就把它当成一列算出来
（本例 ``lines`` 里的 ``price``，再用 ``isplot=False`` 隐藏）。

运行：``python tutorials/styles/11_signal_text.py``
文档：``minibt_docs/docs/minibt_styles/7.11_signal_text.md``
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class SignalTextDemo(BtIndicator):
    """金叉/死叉时，在信号旁边写出**当根收盘价**（B 5432 / S 5120）。"""

    # price 只是为了让 signal_text() 能读到价格：算一列、但不画
    lines = ('ema_fast', 'ema_slow', 'price', 'long_signal', 'short_signal')
    params = dict(FAST=60, SLOW=200)

    overlap = dict(ema_fast=True, ema_slow=True)
    isplot = dict(price=False, long_signal=False, short_signal=False)

    linestyle = dict(
        ema_fast=LineStyle(line_color=Colors.orange, line_width=1.5),
        ema_slow=LineStyle(line_color=Colors.blue, line_width=1.5),
    )
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle,
                                size=12).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle,
                                 size=12).set_label('S'),
    )

    def next(self):
        p = self.params
        fast = self.close.ema(p.FAST)
        slow = self.close.ema(p.SLOW)
        return (fast, slow, self.close,
                fast.cross_up(slow), fast.cross_down(slow))

    def signal_text(self):
        """每条信号写当根收盘价；没信号的位置填 np.nan（不显示）。"""
        price = np.asarray(self.price, dtype=float)
        out = {}
        for name, prefix in (('long_signal', 'B'), ('short_signal', 'S')):
            signal = np.asarray(getattr(self, name), dtype=float)
            texts = np.full(len(signal), np.nan, dtype=object)
            hit = np.isfinite(signal) & (signal != 0)
            texts[hit] = [f'{prefix} {v:.0f}' for v in price[hit]]
            out[name] = texts
        return out


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = SignalTextDemo(kline)
    texts = ind.plotinfo.signal_texts
    for name in ('long_signal', 'short_signal'):
        values = [t for t in texts.get(name, []) if isinstance(t, str)]
        print(f'  {name:13s} 文本数={len(values):4d} 样例={values[:3]}')
    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
