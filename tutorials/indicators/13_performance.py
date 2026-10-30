"""8.13 · 指标性能 —— 首算 / 重复调用 / 数据长度

演示要点
--------
1. **首次调用慢一点**：要 import 对应库（`pandas_ta` / `talib` 等），之后才快；
2. **指标不按参数做 memo**：`kline.macd()` 每次都是一个**新对象**（会重算）——
   策略里请存到 `self.xxx`，**别在 `next()` 里反复算**；
3. **数据长度直接影响耗时**：`data_length=500` 比 8964 根快一个数量级；
4. 回测/实时里框架按 `btindex` **增量**推进（自己不用重算全量）。

运行：``python tutorials/indicators/13_performance.py``
文档：``minibt_docs/docs/minibt_indicators/8.13_performance.md``
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def _time(fn, repeat=3):
    """跑 repeat 次取最快的一次（毫秒）。"""
    best = float('inf')
    out = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        out = fn()
        best = min(best, time.perf_counter() - t0)
    return out, best * 1000


def main(gui=None):
    kline = LocalDatas.test.kline
    print('K 线根数:', len(kline))

    # ① 首次 vs 再次（没有 memo：每次都是新对象）
    m1, t1 = _time(lambda: kline.macd(), repeat=1)
    m2, t2 = _time(lambda: kline.macd(), repeat=1)
    print(f'① macd() 第 1 次 {t1:.1f}ms | 第 2 次 {t2:.1f}ms | '
          f'同一对象: {m1 is m2}')

    # ② 换一个"贵一点"的指标
    adx, t3 = _time(lambda: kline.adx(length=14), repeat=2)
    print(f'② adx(14) {t3:.1f}ms')

    # ③ 长度的影响（5 分钟线 8964 根 vs 只取 500 根）
    strategy = Strategy()
    short = strategy.get_kline(LocalDatas.test, duration_seconds=300,
                               data_length=500)
    _, t_short = _time(lambda: short.macd(), repeat=2)
    print(f'③ macd()：8964 根 {t2:.1f}ms | 500 根 {t_short:.1f}ms')

    # ④ 复用已有对象取值很快（不用重算）
    _, t_get = _time(lambda: float(m1.macdx[-1]), repeat=5)
    print(f'④ 从已有指标取一个值 {t_get:.2f}ms（不重算）')

    # ⑤ 相反：在 next() 里反复新建指标 = 反复重算（要避免）
    print('⑤ [避免] def next(self): self.ind = MyInd(self.data)   # 每根都重算')
    print('   [推荐] def __init__(self): self.ind = MyInd(self.data)')

    # ⑥ 大数据/多指标时
    print('⑥ 提速手段：data_length 截断 / isplot 少画线 / 少建指标（见 5.12）')


if __name__ == '__main__':
    main()
