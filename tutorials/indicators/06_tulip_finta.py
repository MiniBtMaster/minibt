"""8.6 · TuLip / FinTa —— 另外两个指标库

演示要点
--------
| 门面 | 方法数 | 命名 | 周期参数 |
| --- | --- | --- | --- |
| `kline.tulip` | 103 | 小写（`ema` / `rsi` / `adx`） | **`period=`** |
| `kline.finta` | 85 | **大写**（`SMA` / `EMA` / `RSI`） | **`period=`** |

三家（PandasTa / TuLip / FinTa）算同一个 EMA(20)，结果基本一致 ——
差异主要在**预热/缺失值**处理上。

运行：``python tutorials/indicators/06_tulip_finta.py``
文档：``minibt_docs/docs/minibt_indicators/8.6_tulip_finta.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① TuLip（小写 + period）
    tulip_ema = kline.tulip.ema(period=20)
    tulip_rsi = kline.tulip.rsi(period=14)
    print('① tulip.ema(period=20) ->', type(tulip_ema).__name__,
          '| 最后值', round(float(tulip_ema[-1]), 4))
    print('   tulip.rsi(period=14) 最后值:', round(float(tulip_rsi[-1]), 2))

    # ② FinTa（大写 + period）
    finta_ema = kline.finta.EMA(period=20)
    finta_macd = kline.finta.MACD()
    print('② finta.EMA(period=20) ->', type(finta_ema).__name__,
          '| 最后值', round(float(finta_ema[-1]), 4))
    print('   finta.MACD() ->', type(finta_macd).__name__,
          '| 列:', list(finta_macd.pandas_object.columns))

    # ③ 三家对比（EMA 20）
    pta = kline.close.ema(20)
    print('③ EMA(20)：')
    for name, series in (('PandasTa', pta), ('TuLip', tulip_ema),
                         ('FinTa', finta_ema)):
        print(f'   {name:9s} {float(series[-1]):.4f}')

    # ④ 大小写敏感：finta 是小写会报错
    try:
        kline.finta.ema(period=20)
    except Exception as error:                       # noqa: BLE001
        print('④ finta.ema（小写）→', type(error).__name__,
              str(error)[:50])


if __name__ == '__main__':
    main()
