"""8.1 · 指标体系总览 —— 12 个库门面 + 怎么选

演示要点
--------
minibt 把 **12 个指标门面**统一挂到数据对象上（代理机制见 9.7）：

| 门面 | 类 | 方法数（本机实测） | 命名风格 |
| --- | --- | --- | --- |
| `kline.pta` | `PandasTa` | 174 | 小写 + `length` |
| `kline.talib` | `TaLib` | 99 | **大写** + `timeperiod` |
| `kline.tulip` | `TuLip` | 104 | 小写 + `period` |
| `kline.finta` | `FinTa` | 85 | **大写** + `period` |
| `kline.tqta` | `TqTa` | 63 | 大写 + 短参数（`short/long/m`） |
| `kline.tqfunc` | `TqFunc` | 28 | 小写 + `length` |
| `kline.pine` | `Pine` | 57 | 小写 + `length`（Pine 风格） |
| `kline.btind` | `BtInd` | 37 | 小写 + `length` |
| `kline.pairtrading` | `Pair` | 8 | 配对/价差 |
| `kline.tradingsystem` | `TradingSystem` | 13 | 交易系统辅助 |
| `kline.tradingview` | `TradingView` | 114 | TradingView / Pine 指标（含信号） |
| `kline.ta` | `DataFrameIndicators` | 851 | 核心 ta 命名空间（含 ha / cdl_pattern / Factors…） |

**同一个指标，不同库的结果对比**：本例算 5 个 EMA(20) 看差异（都很小）。

运行：``python tutorials/indicators/01_overview.py``
文档：``minibt_docs/docs/minibt_indicators/8.1_overview.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 各门面的类名 + 方法数
    facades = ('pta', 'talib', 'tulip', 'finta', 'tqta', 'tqfunc', 'pine',
               'btind', 'pairtrading', 'tradingsystem', 'tradingview', 'ta')
    for name in facades:
        obj = getattr(kline, name, None)
        cls = type(obj)
        n = len([m for m in dir(obj) if not m.startswith('_')])
        print(f'① kline.{name:14s} -> {cls.__name__:20s} 成员 {n:4d}')

    # ② 五个库算同一个 EMA(20)
    emas = {
        'pta': kline.close.ema(20),
        'talib': kline.talib.EMA(timeperiod=20),
        'tulip': kline.tulip.ema(period=20),
        'finta': kline.finta.EMA(period=20),
        'pine': kline.pine.ema(length=20),
    }
    print('② 同一个 EMA(20) 的最后一个值：')
    for name, series in emas.items():
        print(f'   {name:6s} {float(series[-1]):.4f}')

    # ③ 统一调用：kline.close.xxx(...) 等价于对应库的第一个
    print('③ 代理调用 kline.close.ema(20) =', round(
        float(kline.close.ema(20)[-1]), 4))

    # ④ 都能直接看图（第 7 章）
    print('④ 任何指标都能 ind.btplot()；列/样式见第 7 章')


if __name__ == '__main__':
    main()
