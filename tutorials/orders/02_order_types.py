"""10.2 · `OrderType` —— 五种订单类型

演示要点
--------
| `OrderType` | 值 | 成交价 |
| --- | --- | --- |
| `Market` | 0 | **下一根开盘价** |
| `Close` | 1 | **当前根收盘价**（`Config`/`buy` 默认） |
| `Limit` | 2 | 限价（到价才成交） |
| `Stop` | 3 | 止损单（触发价成交） |
| `StopLimit` | 4 | 止损限价 |

本例用同一套信号，分别用 `Close` / `Market` / `Limit` 下单，对比结果；
`Stop` / `StopLimit` 需要 `price=`，只演示写法。

运行：``python tutorials/orders/02_order_types.py``
文档：``minibt_docs/docs/minibt_orders/10.2_order_types.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _shared import account_snapshot, run_cross      # noqa: E402
from minibt import *                                  # noqa: E402,F403


def _report(name, bt):
    snap = account_snapshot(bt)
    pos = bt.strategies[0].position
    print(f'  {name:10s} total_profit={snap["total_profit"]:>10,.2f} '
          f'| position={int(pos):+d} | 开仓价={pos.open_price}')


def main(gui=None):
    print('① Close（当前根收盘价，默认）：')
    _report('Close', run_cross(lambda d, s: getattr(d, s)(
        exectype=OrderType.Close)))

    print('② Market（下一根开盘价）：')
    _report('Market', run_cross(lambda d, s: getattr(d, s)(
        exectype=OrderType.Market)))

    print('③ Limit（限价，挂远一点通常不成交）：')
    def limit_order(data, side):
        price = float(data.close[-1])
        if side == 'buy':                    # 低于市价 3% 才买
            data.buy(exectype=OrderType.Limit, price=price * 0.97)
        else:                                 # 高于市价 3% 才卖
            data.sell(exectype=OrderType.Limit, price=price * 1.03)
    _report('Limit', run_cross(limit_order))

    print('④ Stop / StopLimit 写法（价格触发，需要 price=）：')
    print('   data.buy(exectype=OrderType.Stop, price=price * 1.01)')
    print('   data.buy(exectype=OrderType.StopLimit, price=..., price_limit=...)')

    print('\n⑤ 默认 exectype 由 Config / buy() 决定；回测里 Close 最直观，'
          '实盘常用 Limit')


if __name__ == '__main__':
    main()
