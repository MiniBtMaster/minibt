"""9.4 · IndFrame —— 多列指标对象

演示要点
--------
`IndFrame` 是"多列指标"（`macd()` / 自定义 `BtIndicator` 的输出）。
它继承 `DataFrame`（所以 pandas 的方法都能用），另外提供：

| 组 | 成员 |
| --- | --- |
| **一键回测** | `backtest()` / `signal_backtest()` / `pair_backtest()` |
| **信号收益** | `signal_profit()` |
| **信号列** | `long_signal` / `short_signal` / `exitlong_signal` / `exitshort_signal` / `entries` / `exits` |
| **列访问** | `iloc` / `loc` / `pop()` / `series` / `to_lines()` / `to_ndarray()` |
| **样式** | `line_style` / `line_color` / `line_dash` / `line_width` / `bandstyle` / `signal_*` |

运行：``python tutorials/data/04_indframe.py``
文档：``minibt_docs/docs/minibt_data/9.4_indframe.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 基本结构
    macd = kline.macd()
    print('① 类型:', type(macd).__name__, '| isMDim:', macd.isMDim,
          '| len:', len(macd))
    print('   列:', list(macd.pandas_object.columns))
    print('   lines:', list(macd.lines), '| sname:', macd.sname)

    # ② 列 → 对象
    print('② to_lines ->', [line.sname for line in macd.to_lines()])
    print('   to_ndarray ->', [a.shape for a in macd.to_ndarray()])
    print('   series.macdx ->', type(macd.series.macdx).__name__)

    # ③ 索引（pandas 风格，但返回 minibt 对象）
    part = macd.iloc[:3, :2]
    print('③ macd.iloc[:3, :2] ->', type(part).__name__, part.shape)

    # ④ pop（在副本上，别改原对象）
    copy = macd.copy()
    got = copy.pop('macds')
    print('④ pop("macds") ->', type(got).__name__,
          '| 副本剩余列:', list(copy.columns))
    print('   原对象列仍是:', list(macd.pandas_object.columns))

    # ⑤ 有信号的指标：signallines / entries / exits
    ind = kline.tradingview.SingleEMACross(ema1=10, ema2=20)
    print('⑤ signallines:', [str(x) for x in ind.signallines])
    print('   entries ->', type(ind.entries).__name__,
          '| exits ->', type(ind.exits).__name__)
    print('   long_signal 前几根:', list(ind.long_signal[:5]))

    # ⑥ 信号收益曲线（isplot=False 不出图）
    prof = ind.signal_profit(bar=5, isplot=False)
    print('⑥ signal_profit(bar=5) ->', type(prof).__name__,
          '| keys:', list(prof)[:6])

    # ⑦ 一行回测（Cython 版，不画图不报告）
    result = ind.signal_backtest(size=1, isplot=False, isreport=False)
    print('⑦ signal_backtest ->', type(result).__name__)

    # ⑧ backtest() 需要指标自己实现 step()（交易逻辑）
    print('⑧ macd 有 step 吗?', 'step' in getattr(macd, '__dict__', {}),
          '（没有 → backtest() 会报错；带 step 的指标见 8.12）')


if __name__ == '__main__':
    main()
