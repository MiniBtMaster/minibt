"""9.1 · 数据对象总览 —— 从 LocalDatas 到 Line 的五层

演示要点
--------
minibt 的数据是**五个层级**，每一层都能直接算指标：

| 层 | 类型 | 怎么拿 | 说明 |
| --- | --- | --- | --- |
| 数据源 | `LocalDatas` / `DataString` | `LocalDatas.test` | 一个名字（`str` 子类）+ `.kline` |
| K 线 | `KLine` | `LocalDatas.test.kline` / `strategy.get_kline(...)` | OHLCV + 所有指标 |
| 多列指标 | `IndFrame` | `kline.macd()` / 自定义 `BtIndicator` | 每列是一个 `Line` |
| 单列指标 | `IndSeries` | `kline.close.ema(20)` | 一维值 |
| 单条线 | `Line` | `macd.diff` / `kline.close` | 算术 / 比较 / `ema()`… |

**代理机制**：`PandasTa` / `TaLib` / `TradingView` / `TqTa` … 这些指标库类的方法，
在框架初始化时被**挂到数据类上**，所以：

```python
kline.macd.__qualname__      # 'PandasTa.macd'（还是库里的名字）
dir(kline)                   # 几百个方法（各库指标总和）
kline.tradingview.SingleEMACross()   # 显式走 TradingView 门面
kline.close.ema(20)          # Line 上也能直接调
```

运行：``python tutorials/data/01_overview.py``
文档：``minibt_docs/docs/minibt_data/9.1_overview.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    # ① 数据源
    d = LocalDatas.test
    print('① LocalDatas.test  ->', type(d).__name__, '| str():', str(d))

    # ② K 线
    k = d.kline
    print('② .kline           ->', type(k).__name__, '| 根数:', len(k))
    print('   pandas 列:', list(k.pandas_object.columns))

    # ③ 单条线
    print('③ k.close          ->', type(k.close).__name__)

    # ④ 单列指标
    ema = k.close.ema(20)
    print('④ k.close.ema(20)  ->', type(ema).__name__, '| 长度', len(ema))

    # ⑤ 多列指标（pandas_ta 的 MACD 列名是 macdx / macdh / macds）
    macd = k.macd()
    print('⑤ k.macd()         ->', type(macd).__name__,
          '| 列:', list(macd.pandas_object.columns))
    print('   macd.macdx      ->', type(macd.macdx).__name__)

    # ⑥ 代理机制
    print('⑥ k.macd 的 qualname =', k.macd.__qualname__, '（代理自 PandasTa）')
    print('   KLine 上的公开方法数 =',
          len([n for n in dir(k) if not n.startswith('_')]))

    # ⑦ 五种类型都能直接算指标（同一个入口）
    print('⑦ macd.macdx.ema(9) ->', type(macd.macdx.ema(9)).__name__)

    # ⑧ ⚠ 列名撞 pandas 方法：macd.diff 是 DataFrame.diff()，不是那一列
    print('⑧ macd.diff 的实际类型 =', type(macd.diff).__name__,
          '（pandas 方法，不是列）')
    print('   macd["macdx"]        =', type(macd['macdx']).__name__)


if __name__ == '__main__':
    main()
