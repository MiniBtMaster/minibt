"""10.3 · 目标仓位 —— `set_target_size` 与 `SizeType`

演示要点
--------
| 写法 | 语义 |
| --- | --- |
| `data.buy()` / `sell()` | **加仓**（每次 +size，可能越加越多） |
| `data.set_target_size(n)` | **目标仓位**：调到 n 手（正多负空，0 平），幂等 |
| `data.set_target_size(n, reverse=True)` | 目标 + 反手 |

`SizeType`（用在 `signal_backtest(size=..., size_type=...)`）：

| `SizeType` | 值 | 含义 |
| --- | --- | --- |
| `Amount` | 0 | 手数 |
| `Value` | 1 | 金额 |
| `Percent` | 2 | 资金比例 |

运行：``python tutorials/orders/03_target_size.py``
文档：``minibt_docs/docs/minibt_orders/10.3_target_size.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _shared import account_snapshot, run_cross      # noqa: E402
from minibt import *                                  # noqa: E402,F403


def _report(name, bt):
    snap = account_snapshot(bt)
    pos = bt.strategies[0].position
    print(f'  {name:22s} 总盈亏={snap["total_profit"]:>10,.2f} '
          f'| 手数={pos.pos:+d} | 方向={int(pos):+d}')


def main(gui=None):
    print('① buy()/sell() 每次加仓：')
    _report('buy()/sell()',
            run_cross(lambda d, s: getattr(d, s)()))

    print('② set_target_size(±1)：目标仓位（幂等）')
    _report('set_target_size(±1)',
            run_cross(lambda d, s: d.set_target_size(1 if s == 'buy' else -1)))

    print('③ set_target_size(±2)：目标 2 手')
    _report('set_target_size(±2)',
            run_cross(lambda d, s: d.set_target_size(2 if s == 'buy' else -2)))

    print('④ SizeType 取值:', [(n, int(getattr(SizeType, n)))
                              for n in ('Amount', 'Value', 'Percent')])
    print('   用法：ind.signal_backtest(size=0.5, size_type=SizeType.Percent)')


if __name__ == '__main__':
    main()
