"""10.1 · 交易模型总览 —— `buy` / `sell` / `insert_order`

演示要点
--------
| 入口 | 谁用 | 说明 |
| --- | --- | --- |
| `data.buy(...)` / `data.sell(...)` | **回测 + 实盘** | 开多/开空（`reverse` 反手、`stop` 止损） |
| `data.set_target_size(...)` | 回测 + 实盘 | 目标仓位（自动加/减到 size 手） |
| `data.insert_order(...)` | **实盘（天勤）** | 原生下单（direction/offset/volume/limit_price） |

一次交易的生命周期：

```text
信号（next / step）
   → buy()/sell()/set_target_size()
     → Order（委托）
       → 成交（Trade）→ position（持仓）
         → BtStop 止损止盈 → 平仓
```

本例跑一遍最小回测，打印**账户快照**（`Config(print_account=False)` 关掉控制台表）。

运行：``python tutorials/orders/01_model.py``
文档：``minibt_docs/docs/minibt_orders/10.1_model.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _shared import account_snapshot, run_cross      # noqa: E402
from minibt import *                                  # noqa: E402,F403


def main(gui=None):
    # ① 最朴素的下单：金叉买入、死叉卖出
    bt = run_cross(lambda data, side:
                   data.buy() if side == 'buy' else data.sell())

    # ② 账户快照（回测结束后）
    snap = account_snapshot(bt)
    for key, value in snap.items():
        if key in ('risk_ratio', 'net'):        # 比例，保留 4 位
            print(f'② {key:16s} = {value:.4f}')
        else:
            print(f'② {key:16s} = {value:,.2f}')

    # ③ 持仓：回测最后停在什么方向
    strategy = bt.strategies[0]
    position = strategy.position            # ★ 是 int 子类：1 多 / 0 空 / -1 空头
    print('③ position:', type(position).__name__,
          '| int(position) =', int(position))
    print('   手数(pos):', position.pos,
          '| 开仓价:', position.open_price)

    # ④ 关键概念：buy/sell 是"开仓"，平仓靠 stop / reverse / 反向信号
    print('④ 平仓方式：stop=BtStop.xxx / reverse=True / 反向信号（见 10.5/10.6）')


if __name__ == '__main__':
    main()
