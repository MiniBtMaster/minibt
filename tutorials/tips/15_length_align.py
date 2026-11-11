"""5.15 · 长度对齐 —— data_length / 预热 / RangeIndex

演示要点
--------
| 事项 | 说明 |
| --- | --- |
| `data_length` | 只留**最近 N 根**；回测传 `<300` 会被修正成 10000（超过全量就等于全量） |
| 指标长度 | 与 K 线**等长**，开头 `window-1` 个是 `NaN`（预热） |
| 不同长度算同一指标 | SMA/rolling **完全一致**；EMA 有递归初始值，窗口越短差越大 |
| 索引 | `kline.index` 是 `RangeIndex`（0..N-1），**不能当时间用**；按时间对齐要用 `datetime` 列 |
| `min_start_length` | 只决定"前多少根不下单"，**不改变**取到的根数 |

运行：``python tutorials/tips/15_length_align.py``
文档：``minibt_docs/docs/minibt_tips/5.15_length_align.md``
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    strategy = Strategy()
    full = LocalDatas.test.kline

    # ① data_length：只留最近 N 根
    print('① 主数据总根数:', len(full))
    for length in (None, 500, 2000):
        k = strategy.get_kline(LocalDatas.test, duration_seconds=300,
                               data_length=length)
        print(f'   data_length={length!s:5s} -> {len(k):5d} 根 | '
              f'{k.datetime.iloc[0]} → {k.datetime.iloc[-1]}')

    # ② 回测下限修正：< 300 会被当成 10000（超过全量 → 全量）
    k100 = strategy.get_kline(LocalDatas.test, duration_seconds=300,
                              data_length=100)
    print('② data_length=100 ->', len(k100), '根（回测 <300 修正为 10000；'
          '全量只有', len(full), '根，所以等于全量）')

    # ③ 指标与 K 线等长，开头是 NaN
    ema20 = full.close.ema(20)
    print('③ K 线', len(full), '根 | ema20', len(ema20),
          '根 | 开头 NaN 个数',
          int(np.isnan(np.asarray(ema20.values, dtype=float)).sum()))

    # ④ 同一指标用不同长度的数据算，尾部是否对得上
    print('④ 拿后 N 根重算 ema20 / sma20（与全量比尾部）：')
    base_ema = float(full.close.ema(20)[-1])
    base_sma = float(full.close.sma(20)[-1])
    for n in (25, 50, 100, 300):
        tail = full[-n:]                       # ★ 切片仍是 KLine
        d_ema = abs(float(tail.close.ema(20)[-1]) - base_ema)
        d_sma = abs(float(tail.close.sma(20)[-1]) - base_sma)
        print(f'   后 {n:3d} 根: sma 差 {d_sma:.6f} | ema 差 {d_ema:.6f}')
    print('   → SMA/rolling 只看窗口内数据，完全一致；'
          'EMA 有递归初始值，预热不够就差')

    # ⑤ 索引不是时间：RangeIndex
    print('⑤ kline.index =', type(full.index).__name__,
          '| 前 3 个:', full.index[:3].tolist())
    print('   datetime 列才是时间:', full.datetime.iloc[0], '…',
          full.datetime.iloc[-1])
    print('   跨数据源对齐要按 datetime 合并，不要按位置 concat')

    # ⑥ min_start_length 不改变取数长度（只影响回测里何时开始下单）
    class WarmUp(Strategy):
        config = Config(min_start_length=200, print_account=False, islog=False)

        def __init__(self):
            self.data = self.get_kline(LocalDatas.test, duration_seconds=300,
                                       data_length=500)
            print('⑥ Config(min_start_length=200) + get_kline(data_length=500)'
                  ' ->', len(self.data), '根（没有变成 700）')
            self.ind = self.data.close.ema(200)
            self.first_bar = None

        def next(self):
            if self.first_bar is None:
                self.first_bar = len(self.data) - 1

    bt = Bt(auto=False)
    bt.addstrategy(WarmUp)
    bt.run(isplot=False, isreport=False, data_length=500)
    print('   ema200 预热需要 199 根；min_start_length 让前 200 根不下单')


if __name__ == '__main__':
    main()
