"""8.1 · 指标体系总览 —— 21 个库门面 + 怎么选

演示要点
--------
minibt 把 **21 个指标门面**统一挂到数据对象上（代理机制见 9.7）。
其中**带 🦀 的是 Rust 库**（可选依赖：没装就在 desk / 目录里自动消失 ✓）：

| 门面 | 类 | 方法数（本机实测） | 命名风格 |
| --- | --- | --- | --- |
| `kline.pta` | `PandasTa` | 174 | 小写 + `length` |
| `kline.pta_rs` 🦀 | `PtaRs` | 28 | **pandas_ta 口径**（`length`，Rust 实现） |
| `kline.talib` | `TaLib` | 99 | **大写** + `timeperiod` |
| `kline.tulip` | `TuLip` | 104 | 小写 + `period`（tulipy） |
| `kline.tulip_rs` 🦀 | `TulipRS` | 90 | **大写** + `period`（tulip-rs） |
| `kline.ferro` 🦀 | `FerroTa` | 227 | **大写** + `timeperiod`（ferro-ta，含 `CDL*` 形态） |
| `kline.kand` 🦀 | `Kand` | 61 | 小写 + `period`（kand） |
| `kline.vta` 🦀 | `VectorTa` | 211 | 小写 + `length`（vector-ta，可传 `kernel=`） |
| `kline.wickra` 🦀 | `Wickra` | 429 | 大小写混排（wickra，含谐波 / TD / 统计比率） |
| `kline.finta` | `FinTa` | 85 | **大写** + `period` |
| `kline.tqta` | `TqTa` | 63 | 大写 + 短参数（`short/long/m`） |
| `kline.tqfunc` | `TqFunc` | 28 | 小写 + `length` |
| `kline.pine` | `Pine` | 58 | 小写 + `length`（Pine 风格） |
| `kline.btind` | `BtInd` | 38 | 小写 + `length` |
| `kline.pairtrading` | `Pair` | 8 | 配对/价差 |
| `kline.tradingsystem` | `TradingSystem` | 41 | 交易系统（只出信号，`ts_` 前缀） |
| `kline.tradingview` | `TradingView` | 114 | TradingView / Pine 指标（含信号） |
| `kline.alpha` 🦀 | `Alpha` | 79 | py-alpha-lib（Rust） |
| `kline.alpha101` 🦀 | `Alpha101` | 103 | WQ Alpha101 因子（Rust） |
| `kline.alpha191` 🦀 | `Alpha191` | 193 | GTJA Alpha191 因子（Rust） |
| `kline.ta` | `DataFrameIndicators` | 2257 | 核心 ta 命名空间（含 ha / cdl_pattern / Factors…） |

> ⚠ **`kline.tulip` 与 `kline.tulip_rs` 是两家库**：前者是 tulipy（`TuLip`，
> 小写 `ema(period=20)`），后者是 tulip-rs（`TulipRS`，大写 `EMA(period=20)`）。
> v1.3.9 曾把两者都叫 `tulip` → 后定义的覆盖前者，`kline.tulip.ema` 报
> `AttributeError`（已修复）。

**同一个指标，不同库的结果对比**：本例算 6 个 EMA(20) 看差异（都很小）。

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
    facades = ('pta', 'pta_rs', 'talib', 'tulip', 'tulip_rs', 'ferro', 'kand',
               'vta', 'wickra', 'finta', 'tqta', 'tqfunc', 'pine', 'btind',
               'pairtrading', 'tradingsystem', 'tradingview', 'alpha',
               'alpha101', 'alpha191', 'ta')
    for name in facades:
        obj = getattr(kline, name, None)
        cls = type(obj)
        n = len([m for m in dir(obj) if not m.startswith('_')])
        print(f'① kline.{name:14s} -> {cls.__name__:20s} 成员 {n:4d}')

    # ② 六个库算同一个 EMA(20)
    emas = {
        'pta': kline.close.ema(20),
        'talib': kline.talib.EMA(timeperiod=20),
        'tulip': kline.tulip.ema(period=20),          # tulipy（小写）
        'tulip_rs': kline.tulip_rs.EMA(period=20),    # tulip-rs（大写）
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
