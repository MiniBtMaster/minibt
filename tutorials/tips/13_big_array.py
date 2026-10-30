"""5.13 · 大数组性能 —— dtype / 只读视图 / 向量化

演示要点
--------
| 坑 | 现象 | 怎么办 |
| --- | --- | --- |
| `Line` 是 **object** dtype | `kline.close.values.dtype == object`，`np.isnan()` 直接报错 | 先 `np.asarray(values, dtype=float)`，或用 `kline.pandas_object['close'].values` |
| 指标结果是**只读视图** | `ema.values[0] = 1` → `ValueError: read-only` | 要改先 `.copy()` |
| 逐根 Python 循环 | 8964 根要十几 ms，长数据更慢 | `pd.Series.rolling` / `np.convolve` / 框架 `rolling_apply` |
| 到处 `.copy()` | 无谓复制大数组，内存翻倍、GC 变慢 | 只读计算**不用** copy，只在"要原地改"时 copy |

运行：``python tutorials/tips/13_big_array.py``
文档：``minibt_docs/docs/minibt_tips/5.13_big_array.md``
"""

import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *

WINDOW = 20


def _ms(func, *args):
    """跑一次并返回 (毫秒, 结果)。"""
    t0 = time.perf_counter()
    result = func(*args)
    return (time.perf_counter() - t0) * 1000, result


def loop_mean(values, window=WINDOW):
    """最朴素的逐根循环（反面教材）。"""
    out = np.empty(len(values) - window + 1)
    for i in range(len(out)):
        out[i] = values[i:i + window].mean()
    return out


def main(gui=None):
    kline = LocalDatas.test.kline
    close = kline.close
    ema = close.ema(WINDOW)

    # ① dtype：Line.values 是 object，指标结果是 float64
    print('① dtype')
    print(f'   close.values : {close.dtype} / {close.values.dtype}'
          f'  writable={close.values.flags.writeable}')
    print(f'   ema.values   : {ema.dtype} / {ema.values.dtype}'
          f'  writable={ema.values.flags.writeable}')
    print('   kline.pandas_object["close"].values:',
          kline.pandas_object['close'].values.dtype)

    # ② object 数组的坑：np.isnan / 数值运算会不按预期工作
    print('② object 数组')
    try:
        np.isnan(close.values)
    except TypeError as error:
        print('   np.isnan(close.values) ->', type(error).__name__, error)
    raw = np.asarray(close.values, dtype=np.float64)   # ← 一次性转 float
    print('   np.asarray(..., dtype=float) ->', raw.dtype,
          '| NaN 个数', int(np.isnan(raw).sum()))

    # ③ 只读视图：指标结果不能原地改
    print('③ 只读视图')
    try:
        ema.values[0] = 0.0
    except ValueError as error:
        print('   ema.values[0] = 0 ->', type(error).__name__, error)
    writable = ema.values.copy()
    writable[0] = 0.0
    print('   ema.values.copy() 之后可以改:', writable[0])

    # ④ 四种写法算同一个 20 窗口均值（数值 / 耗时）
    print(f'④ {len(raw)} 根 K 线算 {WINDOW} 窗口均值')
    cost, looped = _ms(loop_mean, raw)
    print(f'   Python 逐根循环      {cost:8.2f} ms')
    cost, rolled = _ms(lambda: pd.Series(raw).rolling(WINDOW).mean().to_numpy())
    print(f'   pd.Series.rolling    {cost:8.2f} ms')
    cost, conv = _ms(lambda: np.convolve(raw, np.ones(WINDOW) / WINDOW,
                                         mode='valid'))
    print(f'   np.convolve          {cost:8.2f} ms')
    cost, ind = _ms(lambda: close.rolling_apply(
        lambda w: np.nanmean(np.asarray(w, dtype=float)), WINDOW))
    print(f'   Line.rolling_apply   {cost:8.2f} ms')

    # ⑤ 结果一致性（rolling / convolve / 循环；框架结果开头是 NaN 规则不同）
    print('⑤ 一致性（取第 100 个值）')
    print(f'   loop={looped[100 - WINDOW + 1]:.4f}  '
          f'rolling={rolled[100]:.4f}  convolve={conv[100 - WINDOW + 1]:.4f}')

    # ⑥ copy 的成本：大数组 copy 一次很便宜，但别在循环里反复 copy
    cost_copy, _ = _ms(lambda: raw.copy())
    cost_sum, _ = _ms(lambda: raw.sum())
    print(f'⑥ copy 一次 {cost_copy:.3f} ms / sum 一次 {cost_sum:.3f} ms'
          f'（copy 不是主要矛盾，**循环里**反复 copy 才是）')


if __name__ == '__main__':
    main()
