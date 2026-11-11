"""5.14 · rolling_apply 的正确用法与边界

演示要点
--------
| 用法 | 写法 |
| --- | --- |
| 固定窗口、单输出 | `close.rolling_apply(f, 20)` → `IndSeries` |
| 固定窗口、多输出 | `f` 返回 tuple + `lines=['a','b']` → `IndFrame` |
| 多列按参数名传入 | 函数参数名必须是**列名**（`def f(high, low): …`） |
| 整表 2D 传入 | 函数只收一个参数 → 收到 `(window, 列数)` 的 ndarray |
| 可变窗口 | `window` 传与数据**等长**的正整数序列 |
| 并行 | `n_jobs=-1` 只在函数**很重**时有用（轻函数反而慢 100 倍） |

运行：``python tutorials/tips/14_rolling_apply.py``
文档：``minibt_docs/docs/minibt_tips/5.14_rolling_apply.md``
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline
    close = kline.close

    # ① 固定窗口、单输出 → IndSeries
    low20 = close.rolling_apply(lambda w: np.asarray(w, dtype=float).min(), 20)
    print('① 单输出 ->', type(low20).__name__, '| 长度', len(low20),
          '| 最后值', round(float(low20[-1]), 2))

    # ② 固定窗口、多输出 → IndFrame（lines 数必须与返回个数一致）
    def min_max_std(w):
        w = np.asarray(w, dtype=float)
        return w.min(), w.max(), w.std()

    stat20 = close.rolling_apply(min_max_std, 20,
                                 lines=['low20', 'high20', 'std20'])
    print('② 多输出 ->', type(stat20).__name__,
          '| 列', list(stat20.pandas_object.columns))

    # ③ 多列输入：参数名 = 列名（high / low）
    sub = kline.loc[:, ['high', 'low']]
    body = sub.rolling_apply(
        lambda high, low: (high.mean() - low.mean()),
        10, lines=['body10'])
    print('③ 多列按参数名 ->', type(body).__name__,
          '| 最后值', round(float(body[-1]), 2))
    print('   （f 只返回 1 个值 → 自动降为 IndSeries，lines 就是它的名字）')

    # ④ 整表 2D 输入：只收一个参数 → (window, 列数)
    def whole(window2d):
        return window2d.mean(), window2d.std()

    ohlc = kline.loc[:, ['open', 'high', 'low', 'close']].rolling_apply(
        whole, 10, lines=['ohlc_mean', 'ohlc_std'])
    print('④ 整表 2D ->', list(ohlc.pandas_object.columns),
          '| 最后行', np.round(ohlc.values[-1], 2).tolist())

    # ⑤ 可变窗口：窗口随 20 根波动率变化（5~60）
    vol = np.asarray(close.rolling(20).std().values, dtype=float)
    vol = np.nan_to_num(vol, nan=float(np.nanmean(vol)))
    window = np.clip(5 + (vol / (vol.max() or 1)) * 55, 5, 60).astype(int)
    adaptive = close.rolling_apply(
        lambda w: np.asarray(w, dtype=float).mean(),
        window, prepend_nans=False)
    print('⑤ 可变窗口: 窗口范围', int(window.min()), '~', int(window.max()),
          '| 1/3 处窗口', int(window[len(window) // 3]),
          '| 最后值', round(float(adaptive[-1]), 2))

    # ⑥ 边界：窗口比数据长（用独立的小 K 线，避免受前面的操作影响）
    small = Strategy().kline_from_dataframe(
        LocalDatas.get_dataframe('test').tail(10))
    print('⑥ 边界')
    print('   窗口 20 > 数据 10 根：')
    tiny = small.loc[:, ['close', 'high']].rolling_apply(
        lambda close, high: close.mean(), 20)
    print('   - IndFrame/float 路径 ->', float(tiny.values[0]), '（全 NaN）')
    print('   - prepend_nans=False 的 Line 路径 -> 扩展窗口，第一根 =',
          round(float(small.close.rolling_apply(
              lambda w: w.mean(), 20, prepend_nans=False)[0]), 2))
    try:
        close.rolling_apply(lambda w: w.mean(), np.full(5, 3))
    except ValueError as error:
        print('   可变窗口长度不匹配 ->', type(error).__name__, ':', error)

    # ⑦ 性能：n_jobs 只在"重函数"上划算
    def heavy(w):
        x = np.asarray(w, dtype=float)
        return float(np.sqrt(np.abs(x)).mean() + np.log1p(np.abs(x)).std())

    sample = Strategy().kline_from_dataframe(
        LocalDatas.get_dataframe('test').tail(500)).close
    for jobs in (1, -1):
        t0 = time.perf_counter()
        sample.rolling_apply(heavy, 20, prepend_nans=False, n_jobs=jobs)
        print(f'⑦ n_jobs={jobs:2d}  {time.perf_counter() - t0:6.3f} s')
    print('   轻函数用 n_jobs=-1 反而更慢（线程调度开销 >> 计算量）')


if __name__ == '__main__':
    main()
