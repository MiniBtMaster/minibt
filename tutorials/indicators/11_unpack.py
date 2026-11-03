"""8.11 · 多返回值解包 —— `a, b, c = ind`

演示要点
--------
`IndFrame` **可迭代**，迭代出来的是 **`Line`**（每列一个），所以能直接解包：

```python
macdx, macdh, macds = kline.macd()      # 三个 Line
upper, mid, lower  = kline.bbands()
```

三种取值方式对比：

| 方式 | 结果 | 适合 |
| --- | --- | --- |
| `a, b, c = ind` | `Line`（单条线，可设样式） | 要用某一条线 |
| `ind.to_lines()` | `list[Line]` | 批量处理 |
| `ind.to_ndarray()` | `tuple[np.ndarray]` | 纯数值计算 |
| `ind['列名']` | `IndSeries` | 按名字取 |

运行：``python tutorials/indicators/11_unpack.py``
文档：``minibt_docs/docs/minibt_indicators/8.11_unpack.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 解包：拿到的是 Line
    macd = kline.macd()
    a, b, c = macd
    print('① a, b, c = kline.macd() ->',
          [type(x).__name__ for x in (a, b, c)])
    print('   sname:', [x.sname for x in (a, b, c)])
    print('   末值:', [round(float(x[-1]), 2) for x in (a, b, c)])

    # ② 解包后能直接设样式（因为它是 Line）
    a.line_color = Colors.orange
    a.line_width = 2
    print('② 解包出的 a 也能设样式:', a.line_style.line_color)

    # ③ to_lines / to_ndarray
    print('③ ind.to_lines() ->', [x.sname for x in macd.to_lines()])
    print('   ind.to_ndarray() ->', [arr.shape for arr in macd.to_ndarray()])

    # ④ 按名字取（撞名时用中括号）
    print('④ macd["macdx"] ->', type(macd['macdx']).__name__)

    # ⑤ 布尔信号也能解包（0/1 序列）
    up, dn = kline.close.cross_up(kline.close.ema(20)), \
        kline.close.cross_down(kline.close.ema(20))
    print('⑤ 信号点：上穿', len(up.idx()), '次 | 下穿', len(dn.idx()), '次')

    # ⑥ 常见多返回值指标
    for name, fn in (('bbands()', lambda: kline.bbands()),
                     ('stoch()', lambda: kline.stoch()),
                     ('kc()', lambda: kline.kc())):
        try:
            ind = fn()
            print(f'⑥ kline.{name:10s} -> {len(ind.lines)} 列: '
                  f'{list(ind.lines)}')
        except Exception as error:                   # noqa: BLE001
            print(f'⑥ kline.{name:10s} -> {type(error).__name__}: '
                  f'{str(error)[:40]}')


if __name__ == '__main__':
    main()
