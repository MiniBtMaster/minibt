"""5.12 · 性能陷阱 —— 指标太多 / 线太多 / 每拍重建

演示要点
--------
| 陷阱 | 怎么办 |
| --- | --- |
| 一个指标里几十条线、全画出来 | ``isplot`` 只留要看的几条（数据照样能算） |
| 每拍 `delete + create` 几十个序列 | 用"单序列 + 透明缺口"（框架已默认 ``prefer_single_gap``） |
| 回测跑很久 | ``run(data_length=…)`` 只算最近 N 根；``min_start_length`` 预热 |
| 指标反复重算 | 复用同一个指标对象，别在 `next()` 里新建 |

本例把一个指标做成 **30 条 EMA**，量一下计算耗时，然后只画其中 3 条 ——
"算全部、只画需要的"是常见做法。

运行：``python tutorials/tips/12_perf_pitfalls.py``
文档：``minibt_docs/docs/minibt_tips/5.12_performance_pitfalls.md``
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *

#: 一共算多少条 EMA
N = 30


class ManyEma(BtIndicator):
    """30 条 EMA：**全部计算**，但只画前 3 条（`isplot` 关掉其余）。"""

    # 第 i 条 = EMA(5 * (i+1)) → 5, 10, ... 150
    lines = tuple(f'ema{5 * (i + 1)}' for i in range(N))

    overlap = True
    # 只画最快的 3 条；其余 27 条只留数据（策略里仍可读）
    isplot = {name: (i < 3) for i, name in enumerate(lines)}
    linestyle = dict(
        ema5=LineStyle(line_color=Colors.red, line_width=2),
        ema10=LineStyle(line_color=Colors.orange, line_width=2),
        ema15=LineStyle(line_color=Colors.blue, line_width=2),
    )

    def next(self):
        return tuple(self.close.ema(5 * (i + 1)) for i in range(N))


def main(gui=None):
    kline = LocalDatas.test.kline
    print(f'K 线根数 = {len(kline)}，算 {N} 条 EMA')

    t0 = time.perf_counter()
    ind = ManyEma(kline)
    cost = time.perf_counter() - t0
    print(f'① 计算全部 {N} 条：{cost * 1000:.0f} ms')

    info = ind.plotinfo
    shown = [k for k, v in info.isplot.items() if v]
    print(f'② 实际画出来的线：{shown}（其余 {N - len(shown)} 条 isplot=False）')

    t0 = time.perf_counter()
    _ = ind.ema150[-1]          # 关掉的线照样能取值
    print(f'③ 关掉的线取最新值：{ind.ema150[-1]:.2f}'
          f'（{(time.perf_counter() - t0) * 1000:.2f} ms）')

    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
