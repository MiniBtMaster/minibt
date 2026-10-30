"""8.8 · Pine —— `ta.*` 风格的 57 个函数

演示要点
--------
`kline.pine`（`Pine`，57 个）复刻了 **Pine Script `ta.*`** 的常用函数：

| 函数 | Pine 对应 | 说明 |
| --- | --- | --- |
| `sma(length=10)` / `ema` / `rma(n=20)` | `ta.sma/ema/rma` | 均线（`rma` 是 Wilder 平滑） |
| `rsi(n=20)` | `ta.rsi` | Wilder 平滑 RSI |
| `cci(n=10)` | `ta.cci` | 商品通道指数 |
| `atr(length=14, handle_na=True)` | `ta.atr` | 真实波幅 |
| `adx_wilder(n=20)` | `ta.dmi` 里的 ADX | Wilder ADX |
| `barssince()` | `ta.barssince` | 距上次条件成立的 bar 数 |
| `normalize(lo=0, hi=1)` | MLExtensions | 历史 min/max 归一化 |
| `wavetrend(n1=10, n2=11)` | — | 波形趋势 |

**和别的库的差别**：Pine 风格的参数名是 `n=` / `length=`，且**预热/NaN 处理**
按 Pine 语义（`ta.rma` 用前 n 个非 NaN 的 SMA 播种，见源码 docstring）。

运行：``python tutorials/indicators/08_pine.py``
文档：``minibt_docs/docs/minibt_indicators/8.8_pine.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 常用 ta.* 函数
    for label, fn in (
        ('sma(length=20)', lambda: kline.pine.sma(length=20)),
        ('ema(length=20)', lambda: kline.pine.ema(length=20)),
        ('rma(n=20)', lambda: kline.pine.rma(n=20)),
        ('rsi(n=14)', lambda: kline.pine.rsi(n=14)),
        ('cci(n=20)', lambda: kline.pine.cci(n=20)),
        ('atr(length=14)', lambda: kline.pine.atr(length=14)),
        ('barssince()', lambda: kline.pine.barssince()),
        ('normalize(0, 1)', lambda: kline.pine.normalize(0.0, 1.0)),
    ):
        try:
            out = fn()
            print(f'① kline.pine.{label:22s} -> {type(out).__name__} '
                  f'| 最后值 {round(float(out[-1]), 3)}')
        except Exception as error:                   # noqa: BLE001
            print(f'① kline.pine.{label:22s} -> {type(error).__name__}: '
                  f'{str(error)[:50]}')

    # ② 和 PandasTa 对比（ta.sma / ta.rsi 口径一致）
    pta = kline.close.ema(20)
    pine = kline.pine.ema(length=20)
    print('② EMA(20)：PandasTa', round(float(pta[-1]), 4),
          '| Pine', round(float(pine[-1]), 4))

    # ③ barssince：找一个条件（收盘 > EMA20 的最后一根距今多少根）
    cond = kline.close > kline.close.ema(20)
    print('③ barssince 用法示意：kline.pine.barssince() 需要条件列'
          '（示例只打印普通 rsi）')

    # ④ Pine 指标也能看参数/直接画图
    print('④ 这些指标都是 IndSeries/IndFrame，可直接 btplot（第 7 章）')


if __name__ == '__main__':
    main()
