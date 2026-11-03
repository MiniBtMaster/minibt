"""8.3 · PandasTa —— 173 个指标 + `@tobtind` 通用参数

演示要点
--------
`PandasTa` 是**默认指标库**（代理调用 `kline.close.ema(20)` 走的就是它）。

| 事项 | 说明 |
| --- | --- |
| 方法数 | 173（`kline.pta` 成员 174，含 `_df`） |
| 参数量纲 | 周期参数统一叫 **`length`** |
| 多返回值 | 返回 `IndFrame`（如 `macd()` → `macdx/macdh/macds`） |
| 单返回值 | 返回 `IndSeries` |
| 通用 kwargs | `offset=` 整体平移、`fillna=` 填缺失、`lines=` 给多列改名 |

`lines=` 只对**多列**指标有效（单列时列名就是 `pta_<指标名>`）。

运行：``python tutorials/indicators/03_pandasta.py``
文档：``minibt_docs/docs/minibt_indicators/8.3_pandasta.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 基本调用
    ema = kline.close.ema(20)
    print('① kline.close.ema(20) ->', type(ema).__name__,
          '| sname:', ema.sname, '| 最后值', round(float(ema[-1]), 2))

    # ② 多列指标
    macd = kline.macd()
    print('② kline.macd() ->', type(macd).__name__,
          '| 列:', list(macd.pandas_object.columns))

    # ③ 通用 kwargs：offset（整体平移）
    ema1 = kline.close.ema(20, offset=1)
    print('③ ema(20, offset=1) 最后值:', round(float(ema1[-1]), 2),
          '（= 上一根的 ema(20)', round(float(ema[-2]), 2), '）')

    # ④ 通用 kwargs：fillna（把预热 NaN 填掉）
    ema0 = kline.close.ema(20, fillna=0)
    print('④ ema(20, fillna=0) 前 3 个:', list(ema0[:3]))

    # ⑤ 通用 kwargs：lines（给多列改名，影响下游引用）
    named = kline.macd(lines=('d', 'h', 's'))
    print('⑤ macd(lines=("d","h","s")) ->', list(named.lines))

    # ⑥ 按分类找指标（PandasTa 的 category）
    from minibt.utils import Category
    print('⑥ Category 取值:', [getattr(Category, n) for n in
                              ('Momentum', 'Overlap', 'Trend', 'Volatility',
                               'Volume', 'Statistics', 'Candles')])

    # ⑦ 指标也能直接看图
    print('⑦ macd.btplot() / ema.btplot() 都能出图（见第 7 章）')


if __name__ == '__main__':
    main()
