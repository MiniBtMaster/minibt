"""5.16 · 与 pandas 互操作 —— 清洗 → 回填 → 导出

演示要点
--------
| 方向 | 用法 |
| --- | --- |
| `DataFrame` → `KLine` | `strategy.kline_from_dataframe(df)`（6 列：datetime/OHLC/volume） |
| `KLine` → `DataFrame` | `kline.pandas_object`（含合约字段）/ `LocalDatas.get_dataframe(name)` |
| 指标 → `DataFrame` | `ind.pandas_object`（列 = 指标线） |
| 清洗后再回测 | 用 pandas 过滤 / 排序 / 补缺，然后包回 `KLine` |

⚠ 时间列时区要统一：`LocalDatas.get_dataframe()` 是 **tz-naive**，
`strategy.get_kline()` 是 **tz-aware（+00:00）** —— 混用会在对齐/相减时报错。

运行：``python tutorials/tips/16_df_interop.py``
文档：``minibt_docs/docs/minibt_tips/5.16_df_interop.md``
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    strategy = Strategy()

    # ① 两个入口的时间列不一样
    df = LocalDatas.get_dataframe('test')
    k = strategy.get_kline(LocalDatas.test, duration_seconds=300,
                           data_length=500)
    print('① 时间列')
    print('   LocalDatas.get_dataframe:', df.shape,
          '| datetime tz =', df['datetime'].dt.tz)
    print('   strategy.get_kline     :', (len(k), k.pandas_object.shape[1]),
          '| datetime tz =', k.datetime.dt.tz)

    # ② pandas 清洗：去无成交 / 去缺失 / 只留最近 3000 根
    clean = df.copy()
    before = len(clean)
    clean = clean[clean['volume'] > 0]
    clean = clean.dropna(subset=['open', 'high', 'low', 'close'])
    clean = clean.sort_values('datetime').tail(3000)
    clean = clean.reset_index(drop=True)
    print(f'② 清洗: {before} -> {len(clean)} 根'
          f'（volume>0 + dropna + 最近 3000 根）')

    # ③ 包回 KLine：缺的合约字段自动补默认
    kc = strategy.kline_from_dataframe(clean)
    print('③ kline_from_dataframe ->', len(kc), '根 |',
          'symbol =', kc.symbol, '| cycle =', kc.cycle,
          '| price_tick =', kc.price_tick)

    # ④ 算指标（和直接用 LocalDatas.test.kline 完全一样）
    ema = kc.close.ema(20)
    print('④ ema20:', len(ema), '根 | 最后值',
          round(float(ema[-1]), 2), '| NaN 个数',
          int(np.isnan(np.asarray(ema.values, dtype=float)).sum()))

    # ⑤ 指标 → DataFrame，拼回原始表用于导出
    ind_df = pd.DataFrame(np.asarray(ema.values, dtype=float),
                          columns=['ema20'],
                          index=kc.pandas_object.index)
    export = pd.concat([kc.pandas_object, ind_df], axis=1)
    print('⑤ 导出表:', export.shape, '| 尾部列',
          list(export.columns)[-2:])
    print('   前 3 行 ema20 =',
          export['ema20'].head(3).round(2).tolist(), '（NaN 是预热）')

    # ⑥ 列名撞 pandas 方法时，用 ind['列名'] 而不是 ind.列名
    macd = kc.close.macd()
    print('⑥ macd 列:', list(macd.pandas_object.columns),
          '| macd["macds"] 最后值', round(float(macd['macds'][-1]), 3))
    print('   （macd.diff 可能取到 pandas 的 diff 方法 → 一律用 [] 取列）')


if __name__ == '__main__':
    main()
