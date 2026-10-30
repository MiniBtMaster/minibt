"""10.5 · 反手 —— `reverse=True`

演示要点
--------
| 写法 | 金叉时（已持空单） |
| --- | --- |
| `data.buy()` | **加多**（空单还在，变成对冲/多空都有） |
| `data.buy(reverse=True)` | **先平空、再开多**（反手） |
| `data.buy(reverse=True, reverse_size=2)` | 反手到 **2 手**多 |

运行：``python tutorials/orders/05_reverse.py``
文档：``minibt_docs/docs/minibt_orders/10.5_reverse.md``
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
    print('① 不反手（buy/sell 只加仓）：')
    _report('buy()/sell()', run_cross(lambda d, s: getattr(d, s)()))

    print('② reverse=True（先平后开）：')
    _report('reverse=True',
            run_cross(lambda d, s: getattr(d, s)(reverse=True)))

    print('③ reverse=True, reverse_size=2（反手到 2 手）：')
    _report('reverse_size=2',
            run_cross(lambda d, s: getattr(d, s)(reverse=True,
                                                 reverse_size=2)))

    print('\n④ 注意：reverse 只在**持有反向仓**时生效；空仓时 buy() 就是开多')


if __name__ == '__main__':
    main()
