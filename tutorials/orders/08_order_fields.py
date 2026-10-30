"""10.8 · 订单 / 成交 / 持仓对象字段

演示要点
--------
| 对象 | 怎么拿 | 关键字段 |
| --- | --- | --- |
| `Order` | `broker._completed_orders` / `_orders` / `_pending_orders` | `exectype` `price` `size` `status` `executed_price` `is_buy` `bar` `ref` |
| `position` | `strategy.position`（`BtPosition`，int 子类） | `int()` 方向 / `pos` 手数 / `open_price` |
| `account` | `strategy.account`（`BtAccount`） | `cash` `balance` `margin` `total_profit` `total_commission` |

`OrderStatus`：`Created(0) / Submitted(1) / Accepted(2) / Partial(3) /
Completed(4) / Canceled(5) / Expired(6) / Margin(7) / Rejected(8)`。

运行：``python tutorials/orders/08_order_fields.py``
文档：``minibt_docs/docs/minibt_orders/10.8_order_fields.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _shared import run_cross                        # noqa: E402
from minibt import *                                  # noqa: E402,F403
from minibt.order import OrderStatus                  # noqa: E402


def main(gui=None):
    bt = run_cross(lambda d, s: getattr(d, s)())
    broker = bt.strategies[0].account.brokers[0]

    # ① 委托
    done = list(getattr(broker, '_completed_orders', []))
    pending = list(getattr(broker, '_pending_orders', []))
    print('① 已完成委托:', len(done), '| 挂起:', len(pending))
    if done:
        order = done[0]
        print('   第一条委托：')
        for key in ('side', 'exectype', 'size', 'price', 'status',
                    'executed_price', 'is_buy', 'is_sell', 'bar'):
            print(f'     {key:15s} =', getattr(order, key, '<缺>'))
        info = order.to_dict()
        print('   to_dict 前 8 个键:', list(info)[:8])

    # ② OrderStatus 表
    print('② OrderStatus:', [(n, int(getattr(OrderStatus, n)))
                              for n in ('Created', 'Submitted', 'Completed',
                                        'Canceled', 'Rejected')])

    # ③ 持仓
    pos = bt.strategies[0].position
    print('③ position: 方向', int(pos), '| 手数', pos.pos,
          '| 开仓价', pos.open_price)

    # ④ 账户
    acc = bt.strategies[0].account
    print('④ account: cash', round(float(acc.cash), 2),
          '| balance', round(float(acc.balance), 2),
          '| margin', round(float(acc.margin), 2),
          '| 手续费', round(float(acc.total_commission), 2))

    # ⑤ 实盘：天勤原生对象（TqOrder/TqTrade/TqPosition）
    print('⑤ 实盘用 api.get_order()/get_trade()/get_position()（字段同天勤文档）')


if __name__ == '__main__':
    main()
