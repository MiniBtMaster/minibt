"""8.7 · Pair / Factors —— 配对与因子

演示要点
--------
| 门面 | 方法数 | 用途 |
| --- | --- | --- |
| `kline.pairtrading`（`Pair`） | 8 | 配对/价差指标：`z_score` / `kalman_filter` / `bollinger_bands` / `percentage_deviation` / `rolling_quantile` / `hurst_filter` |
| `Factors`（`from minibt import Factors`） | 4 | 因子工具：`pca_trend_indicator` / `adaptive_weight_trend` / `single_asset_multi_factor_strategy` / `factor_optimizer` |

**Pair 要作用在"价差序列"上**（`a.close - b.close`），不是 K 线上：

```python
spread = a.close - b.close
ind = spread.pairtrading.z_score(window=60)   # → IndFrame（z + 信号）
```

⚠️ `kalman_filter` 需要**两列**（`(根数, 2)`），用价差（单列）会报
`data must be 2-dimensional`。

运行：``python tutorials/indicators/07_pair_factors.py``
文档：``minibt_docs/docs/minibt_indicators/8.7_pair_factors.md``
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    # ① 两条价差（同周期、同长度）
    a = LocalDatas.pp2609_60.kline
    b = LocalDatas.l2609_60.kline
    spread = a.close - b.close
    print('① spread = a.close - b.close ->', type(spread).__name__,
          '| len:', len(spread))

    # ② Pair：价差上的统计指标
    for name, kwargs in (('z_score', dict(window=60, z_threshold=2.0)),
                         ('percentage_deviation', dict(window=60)),
                         ('bollinger_bands', dict(window=60)),
                         ('rolling_quantile', dict(window=60))):
        try:
            out = getattr(spread.pairtrading, name)(**kwargs)
            print(f'② spread.pairtrading.{name:20s} -> '
                  f'{type(out).__name__} | 列 {list(out.pandas_object)}')
        except Exception as error:                   # noqa: BLE001
            print(f'② spread.pairtrading.{name:20s} -> '
                  f'{type(error).__name__}: {str(error)[:50]}')

    try:
        hf = spread.pairtrading.hurst_filter()
        print('   spread.pairtrading.hurst_filter() ->', type(hf).__name__,
              '| 列', list(hf.pandas_object))
    except Exception as error:                       # noqa: BLE001
        print('   hurst_filter ->', type(error).__name__, str(error)[:50])

    # ③ kalman_filter 需要 2-D（两列）
    try:
        spread.pairtrading.kalman_filter(window=60)
    except Exception as error:                       # noqa: BLE001
        print('③ kalman_filter(单列价差) →', type(error).__name__,
              str(error)[:60], '（它要两列）')

    # ④ Factors：4 个高阶工具
    print('④ Factors 方法:', [n for n in dir(Factors)
                              if not n.startswith('_')])
    for name in ('pca_trend_indicator', 'adaptive_weight_trend',
                 'single_asset_multi_factor_strategy', 'factor_optimizer'):
        print(f'   Factors.{name}{inspect.signature(getattr(Factors, name))}')

    # ⑤ 配对回测（真正跑需要信号；见 9.12）
    print('⑤ 配对回测：ind.pair_backtest(kline_a=a, kline_b=b, ...)')


if __name__ == '__main__':
    main()
