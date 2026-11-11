"""9.10 · 长度与对齐 —— data_length / history_length / min_start_length

演示要点
--------
| 参数 | 在哪 | 作用 |
| --- | --- | --- |
| ``data_length`` | `get_kline` / `run` / `backtest` | 取多少根（只保留**最近** N 根） |
| ``history_length`` | `get_kline`（tqsdk） | "无限历史"的底层取数长度；设了且 > data_length 时，图开局只显示 data_length，向左滚再放 |
| ``min_start_length`` | `Config` | 前多少根**不下单**（指标预热）；回测实际取数 = data_length + min_start_length |
| ``data_length``（回测） | `get_kline` | < 300 会被**修正为 10000**；实盘 < 10 修正为 300 |

本例用本地 CSV 演示 `data_length` 的"取最近 N 根"效果（离线、可复现）。

运行：``python tutorials/data/10_length.py``
文档：``minibt_docs/docs/minibt_data/9.10_length.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    strategy = Strategy()

    print('主数据总根数:', len(LocalDatas.test.kline))
    for length in (None, 500, 2000):
        k = strategy.get_kline(LocalDatas.test, duration_seconds=300,
                               data_length=length)
        print(f'① data_length={length!s:5s} -> {len(k):5d} 根 | '
              f'{k.datetime.iloc[0]} → {k.datetime.iloc[-1]}')

    print('② Config().min_start_length =', Config().min_start_length,
          '（前 N 根不下单，只算指标）')
    print('   Config(min_start_length=200) =',
          Config(min_start_length=200).min_start_length)

    print('③ history_length（只在 get_kline 的 tqsdk 源生效）:')
    print('   get_kline("SHFE.ni2610", data_length=200, history_length=10000)')
    print('   → 图开局显示 200 根，向左滚动再逐步放出到 10000 根')

    print('④ 回测入口的长度：Bt().run(data_length=3000)'
          '（只算最近 3000 根，指标预热另算）')

    # ⑤ 长度对齐：不同长度的指标可以直接对齐比较（按 time）
    k = strategy.get_kline(LocalDatas.test, duration_seconds=300,
                           data_length=500)
    ema = k.close.ema(20)
    print('⑤ 同一 K 线上的指标长度：kline', len(k), '| ema', len(ema),
          '（等长，前 19 个是 NaN）')


if __name__ == '__main__':
    main()
