"""8.4 · TaLib —— 99 个指标（大写名 + `timeperiod`）

演示要点
--------
| 事项 | PandasTa | TaLib |
| --- | --- | --- |
| 方法名 | 小写 `ema` / `rsi` | **大写** `EMA` / `RSI` |
| 周期参数 | `length=20` | **`timeperiod=20`** |
| 移动平均类型 | 各指标各写 | 统一的 **`matype=`**（`MaType`） |
| 多返回值 | 名字有意义（`macdx/macdh/macds`） | 有自己的名字（`MACD` → `dif/dem/histogram`） |

`MaType`（TA-Lib 的均线类型）：`SMA / EMA / WMA / DEMA / TEMA / TRIMA /
KAMA / MAMA / T3`。

运行：``python tutorials/indicators/04_talib.py``
文档：``minibt_docs/docs/minibt_indicators/8.4_talib.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 大写 + timeperiod（注意：门面已绑定数据源，不要再传 kline.close）
    sma = kline.talib.SMA(timeperiod=20)
    print('① kline.talib.SMA(timeperiod=20) ->', type(sma).__name__,
          '| 最后值', round(float(sma[-1]), 2))

    # ② 和 PandasTa 对比
    pta = kline.close.sma(20)
    print('② pta sma(20) 最后值:', round(float(pta[-1]), 2),
          '| 两者一致:', abs(float(pta[-1]) - float(sma[-1])) < 1e-9)

    # ③ MaType：同一个 MA 换均线类型
    for ma in (MaType.SMA, MaType.EMA, MaType.WMA):
        out = kline.talib.MA(timeperiod=20, matype=ma)
        print(f'③ talib.MA(timeperiod=20, matype={ma}) -> '
              f'{round(float(out[-1]), 2)}')

    # ④ 多返回值（TaLib 有自己的列名）
    macd = kline.talib.MACD(fastperiod=12, slowperiod=26, signalperiod=9)
    print('④ talib.MACD ->', type(macd).__name__,
          '| 列:', list(macd.pandas_object.columns))

    # ⑤ ⚠ 参数名别混：传错名字**不报错**，只是用了默认值
    wrong = kline.talib.SMA(length=20)      # ← 它要 timeperiod，这里被忽略
    right = kline.talib.SMA(timeperiod=20)
    print('⑤ 传 length（错）:', round(float(wrong[-1]), 2),
          '| 传 timeperiod（对）:', round(float(right[-1]), 2),
          '→ 不报错，但结果不同')


if __name__ == '__main__':
    main()
