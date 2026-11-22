"""10.12 · 账户查询 —— 回测结果 + 实盘接口

演示要点
--------
| 场景 | 用 |
| --- | --- |
| 回测结束时 | `strategy.account` / `strategy.position` / `bt.get_results()` |
| 逐笔历史 | `account.get_history_results()`（DataFrame，按 bar） |
| 盈亏序列 | `account.get_profits()` |
| 实盘（天勤） | `api.get_position(symbol, account=)` / `get_order()` / `get_trade()` |

账户字段（`BtAccount`）：`cash` / `available` / `balance` / `margin` /
`risk_ratio` / `total_profit` / `total_commission` / `profit` / `net` / `history`。

运行：``python tutorials/orders/12_account.py``
文档：``minibt_docs/docs/minibt_orders/10.12_account.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _shared import run_cross                        # noqa: E402
from minibt import *                                  # noqa: E402,F403


def main(gui=None):
    bt = run_cross(lambda d, s: getattr(d, s)())
    strategy = bt.strategies[0]
    account = strategy.account

    # ① 账户快照
    print('① account:')
    for key in ('cash', 'available', 'balance', 'margin', 'risk_ratio',
                'total_profit', 'total_commission', 'profit', 'net'):
        value = getattr(account, key, None)
        try:
            value = round(float(value), 4)
        except (TypeError, ValueError):
            value = None
        print(f'   {key:17s} = {value}')

    # ② 持仓
    pos = strategy.position
    print('② position: 方向', int(pos), '| 手数', pos.pos,
          '| 多', pos.pos_long, '| 空', pos.pos_short,
          '| 开仓价', pos.open_price)

    # ③ 委托
    broker = account.brokers[0]
    print('③ 委托：完成', len(list(getattr(broker, '_completed_orders', []))),
          '| 挂起', len(list(getattr(broker, '_pending_orders', []))),
          '| 撤销', len(list(getattr(broker, '_canceled_orders', []))))

    # ④ 逐 bar 结果
    df = bt.get_results()[0][0]
    print('④ bt.get_results()[0][0]:', df.shape,
          '| 列:', list(df.columns))
    print('   权益末值:', round(float(df['total_profit'].iloc[-1]), 2),
          '| 累计平仓盈亏:', round(float(df['cum_profits'].iloc[-1]), 2))

    # ⑤ 历史 / 盈亏（会打印一张统计表，这里只看有没有）
    print('⑤ account.get_history_results() / get_profits() 可用:',
          hasattr(account, 'get_history_results'),
          hasattr(account, 'get_profits'))

    # ⑥ 实盘
    print('⑥ 实盘（天勤）：api.get_position(symbol, account=) / '
          'get_order(order_id) / get_trade(trade_id)')


if __name__ == '__main__':
    main()
