"""8.2 · 内置指标 —— `kline.ta` / `kline.btind`

演示要点
--------
| 入口 | 是什么 | 常用 |
| --- | --- | --- |
| `kline.ta` | 核心 ta 命名空间（`DataFrameIndicators`，851 个成员） | `ha()` / `cdl_pattern()` / `Linear_Regression_Candles` / `Factors` / `PairTrading` |
| `kline.btind` | 内置 BtInd（37 个） | `smoothrng` / `rngfilt` / `alerts` / `noises_*` |
| `kline.pairtrading` | 配对工具（8 个） | 见 8.7 |

⚠️ `kline.ta.xxx()` 有些返回的是**普通 `DataFrame`**（不是 `IndFrame`），
要当指标用就先 `kline_from_dataframe` 包一层（或者直接用 `kline.ha()` 那种
`IndFrame` 版本）。

运行：``python tutorials/indicators/02_builtin.py``
文档：``minibt_docs/docs/minibt_indicators/8.2_builtin.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① kline.ta：核心 ta 命名空间
    ta = kline.ta
    names = [n for n in dir(ta) if not n.startswith('_')]
    print('① kline.ta ->', type(ta).__name__, '| 成员数:', len(names))
    print('   例:', [n for n in names
                     if n in ('ha', 'cdl_pattern', 'cdl_z', 'lrc',
                              'Linear_Regression_Candles',
                              'Heikin_Ashi_Candles')])

    # ② ha / cdl_pattern：返回 DataFrame（原始表）
    ha = kline.ta.ha()
    print('② kline.ta.ha() ->', type(ha).__name__, '| shape:', ha.shape)
    print('   列:', list(ha.columns)[:6])
    pattern = kline.ta.cdl_pattern(name='doji')
    print('   kline.ta.cdl_pattern(name="doji") ->', type(pattern).__name__,
          '| shape:', pattern.shape)

    # ③ 想要 IndFrame 版：直接用 kline.ha()（见 7.3）
    ha_ind = kline.ha()
    print('③ kline.ha() ->', type(ha_ind).__name__,
          '| 列:', list(ha_ind.pandas_object.columns))

    # ④ kline.btind：内置 BtInd
    bt = kline.btind
    bt_names = [n for n in dir(bt) if not n.startswith('_')]
    print('④ kline.btind ->', type(bt).__name__, '| 成员数:', len(bt_names))
    print('   例:', bt_names[:8])
    smooth = kline.btind.smoothrng(length=14, mult=2.0)
    print('   kline.btind.smoothrng(length=14, mult=2.0) ->',
          type(smooth).__name__, '| 最后值', round(float(smooth[-1]), 2))

    # ⑤ 这些指标也能看图
    print('⑤ smooth.btplot(...) 可直接出图（样式见第 7 章）')


if __name__ == '__main__':
    main()
