"""8.10 · 指标的数据字段 —— 用哪一列做计算

演示要点
--------
指标默认从 K 线的**同名字段**取数据（`rsi` → `close`、`atr` → `high/low/close`），
也可以**显式覆盖**：

```python
kline.rsi(14, close=kline.open)   # 用开盘价算 RSI
kline.open.rsi(14)                # 等价写法（直接在那条线上算）
```

| 指标 | 默认字段 |
| --- | --- |
| `rsi` / `sma` / `ema` / `macd` / `bbands` | `close` |
| `atr` / `cci` / `willr` / `stoch` / `adx` | `high`、`low`、`close` |
| `obv` / `vwma` | `close`、`volume` |

⚠️ `line_filed`（`_name` 那种内部列名）是**框架内部**用来对齐"线名 ↔ 数据集列"的，
一般不用手写；要"换数据源"就用上面的**字段 kwarg** 或 `.open.xxx()`。

运行：``python tutorials/indicators/10_fields.py``
文档：``minibt_docs/docs/minibt_indicators/8.10_fields.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 默认：rsi 用 close
    rsi_close = kline.rsi(14)
    print('① kline.rsi(14)（默认 close）最后值:',
          round(float(rsi_close[-1]), 2))

    # ② 换成开盘价（两种写法等价）
    a = kline.rsi(14, close=kline.open)
    b = kline.open.rsi(14)
    print('② rsi(14, close=open) 最后值:', round(float(a[-1]), 2),
          '| kline.open.rsi(14):', round(float(b[-1]), 2),
          '| 两种写法一致:', abs(float(a[-1]) - float(b[-1])) < 1e-9)

    # ③ ATR 三个字段都能换
    atr = kline.atr(14)
    atr_custom = kline.atr(14, high=kline.open, low=kline.low,
                           close=kline.close)
    print('③ atr(14) 最后值:', round(float(atr[-1]), 3),
          '| 换 high=open 后:', round(float(atr_custom[-1]), 3))

    # ④ 用"均线"当价格算指标（常见技巧）
    ma20 = kline.close.sma(20)
    rsi_on_ma = kline.rsi(14, close=ma20)
    print('④ 用 MA20 当价格算 RSI:', round(float(rsi_on_ma[-1]), 2))

    # ⑤ 在某一列上直接算（等价于换字段）
    ema_on_volume = kline.volume.ema(20)
    print('⑤ kline.volume.ema(20) 最后值:', round(float(ema_on_volume[-1]), 2))

    # ⑥ 多合约：把 A 的字段传给 B 的指标（同一周期、等长时可用）
    other = LocalDatas.l2609_60.kline
    print('⑥ 跨合约换字段：other.rsi(14, close=kline.close) 需要等长对齐')


if __name__ == '__main__':
    main()
