"""8.5 · TqTa / TqFunc —— 天勤（tqsdk）的函数与指标

演示要点
--------
| 门面 | 方法数 | 特点 |
| --- | --- | --- |
| `kline.tqta` | 63 | 天勤指标（MACD/KDJ/BOLL/DMI/ATR/BIAS…），参数名短（`short/long/m`） |
| `kline.tqfunc` | 28 | 天勤**函数**（`ref/ma/sma/ema/ema2/std`），风格接近 Pine |

两者都是**天勤口径**，和 PandasTa/TaLib 的数值会有细微差别（算法/预热不同）——
做天勤实盘时用它们能和平台对齐。

运行：``python tutorials/indicators/05_tqta_tqfunc.py``
文档：``minibt_docs/docs/minibt_indicators/8.5_tqta_tqfunc.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① TqTa：指标（参数名短）
    macd = kline.tqta.MACD(short=12, long=26, m=9)
    print('① kline.tqta.MACD(short=12, long=26, m=9) ->',
          type(macd).__name__, '| 列:', list(macd.pandas_object.columns))
    boll = kline.tqta.BOLL(short=20, m=2)
    print('   kline.tqta.BOLL(short=20, m=2) ->', type(boll).__name__,
          '| 列:', list(boll.pandas_object.columns))

    # ② TqFunc：函数（Pine 风格）
    for name, fn in (('ref(1)', lambda: kline.tqfunc.ref(1)),
                     ('ma(length=20)', lambda: kline.tqfunc.ma(length=20)),
                     ('sma(n=10, m=2)', lambda: kline.tqfunc.sma(n=10, m=2)),
                     ('ema2(length=20)', lambda: kline.tqfunc.ema2(length=20))):
        try:
            out = fn()
            print(f'② kline.tqfunc.{name:18s} -> {type(out).__name__} '
                  f'| 最后值 {round(float(out[-1]), 2)}')
        except Exception as error:                   # noqa: BLE001
            print(f'② kline.tqfunc.{name:18s} -> {type(error).__name__}: '
                  f'{str(error)[:50]}')

    # ③ 和 PandasTa 对比（口径不同：天勤 EMA2 是另一种 EMA 初始化）
    pta = kline.close.ema(20)
    tq = kline.tqfunc.ema2(length=20)
    print('③ PandasTa ema(20)', round(float(pta[-1]), 4),
          '| 天勤 ema2(20)', round(float(tq[-1]), 4),
          '（差几个点，属正常：算法不同）')

    # ④ TqTa 的 ATR/KDJ 等也能直接用
    atr = kline.tqta.ATR(n=14) if hasattr(kline.tqta, 'ATR') else None
    print('④ kline.tqta.ATR(n=14) ->', type(atr).__name__ if atr is not None
          else '（参数名不同，试 kline.tqta.ATR(length=14)）')


if __name__ == '__main__':
    main()
