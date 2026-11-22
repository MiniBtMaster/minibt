"""9.11 · 与 pandas 互操作 —— DataFrame ↔ KLine / 指标

演示要点
--------
| 方向 | 用 |
| --- | --- |
| `DataFrame` → `KLine` | `kline_from_dataframe(df)` / `get_kline(df)` / `kline_from_path(csv)` |
| `KLine` → `DataFrame` | `kline.pandas_object` / `LocalDatas.get_dataframe(name)` |
| 指标 → `DataFrame` | `ind.pandas_object`（列 = 指标线） |
| `DataFrame` → 指标 | 先把 df 包成 `KLine`，再正常算 |

`kline_from_dataframe` 只需要 `datetime/open/high/low/close/volume`，
缺的合约字段（`symbol`/`duration`/`price_tick`/`volume_multiple`）会**自动补默认**。

运行：``python tutorials/data/11_dataframe.py``
文档：``minibt_docs/docs/minibt_data/9.11_dataframe.md``
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    strategy = Strategy()

    # ① LocalDatas → DataFrame
    df = LocalDatas.get_dataframe('test')
    print('① LocalDatas.get_dataframe:', df.shape,
          '| 前 6 列:', list(df.columns)[:6])

    # ② 手搓一个最小 DataFrame → KLine（只给 OHLCV）
    small = pd.DataFrame({
        'datetime': pd.date_range('2026-01-05 09:00', periods=6, freq='5min'),
        'open': [100, 101, 102, 101, 103, 104],
        'high': [101, 102, 103, 103, 104, 105],
        'low': [99, 100, 101, 100, 102, 103],
        'close': [101, 102, 101, 103, 104, 104],
        'volume': [10, 12, 8, 15, 20, 18],
    })
    k = strategy.kline_from_dataframe(small)
    print('② kline_from_dataframe(6 行) ->', len(k), '根 |',
          k.symbol, '| cycle', k.cycle)
    print('   自动补的合约字段: price_tick', k.price_tick,
          '| volume_multiple', k.volume_multiple,
          '| symbol', k.symbol)

    # ③ KLine → DataFrame（round-trip）
    raw = k.pandas_object.copy()
    raw['close'] = raw['close'] + 10          # 改点数据
    k2 = strategy.kline_from_dataframe(raw)
    print('③ 改完再包回去:', len(k2), '根 |',
          'close 最后一根 =', float(k2.close[-1]))

    # ④ 指标 → DataFrame
    macd = LocalDatas.test.kline.macd()
    print('④ macd.pandas_object:', macd.pandas_object.shape,
          '| 列:', list(macd.pandas_object.columns))
    plain = pd.DataFrame(macd.pandas_object)   # 转成普通 DataFrame
    print('   普通 DataFrame 可用 pandas 运算:',
          round(float(plain['macdx'].tail(5).mean()), 2))

    # ⑤ 用 pandas 造完再算指标
    df2 = LocalDatas.get_dataframe('test').tail(300).copy()
    k3 = strategy.kline_from_dataframe(df2)
    print('⑤ tail(300) → KLine → ema(20):', len(k3), '根 |',
          '最后值', round(float(k3.close.ema(20)[-1]), 2))


if __name__ == '__main__':
    main()
