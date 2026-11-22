"""10.9 · 手续费 / 滑点 / 保证金

演示要点
--------
手续费三选一（**设 > 0 的那个**，优先级 `percent > tick > fixed`）：

| `Config` 字段 | 含义 | 值 |
| --- | --- | --- |
| `tick_commission` | 按"跳"（`price_tick × volume_multiple`） | `1.0` = 1 个 tick |
| `fixed_commission` | 每手固定金额 | `5.0` = 5 元/手 |
| `percent_commission` | 按成交额比例 | `0.0002` = 万分之二 |

| `CommissionType` | 值 |
| --- | --- |
| `Tick` / `Fixed` / `Percent` | 0 / 1 / 2 |

保证金：`Config(margin_rate=…)`（实测生效）。
滑点：`self.data.slip_point = 1.0`（买 +1 / 卖 -1，价格单位）。

运行：``python tutorials/orders/09_fees.py``
文档：``minibt_docs/docs/minibt_orders/10.9_fees.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _shared                                        # noqa: E402
from minibt import *                                  # noqa: E402,F403

BASE = dict(print_account=False, islog=False)


def main(gui=None):
    print('① CommissionType:', [(n, int(getattr(CommissionType, n)))
                                for n in ('Tick', 'Fixed', 'Percent')])

    # ② 三种收费方式（Config 里设 > 0 的那个）
    for name, cfg in (
        ('不收费', _shared.Config(**BASE)),
        ('tick=1', _shared.Config(tick_commission=1.0, **BASE)),
        ('fixed=5/手', _shared.Config(fixed_commission=5.0, **BASE)),
        ('percent=0.0002', _shared.Config(percent_commission=0.0002,
                                          **BASE)),
    ):
        bt = _shared.run_cross(lambda d, s: getattr(d, s)(), config=cfg)
        acc = bt.strategies[0].account
        print('② %-16s 手续费=%9.2f | 权益=%12.2f'
              % (name, float(acc.total_commission), float(acc.balance)))

    # ③ 保证金率
    for rate in (0.05, 0.2):
        cfg = _shared.Config(margin_rate=rate, **BASE)
        bt = _shared.run_cross(lambda d, s: getattr(d, s)(), config=cfg)
        acc = bt.strategies[0].account
        print('③ margin_rate=%-5s 保证金=%9.2f | 风险度=%.4f'
              % (rate, float(acc.margin), float(acc.risk_ratio)))

    # ④ 也可以直接写策略属性（等价，运行时改）
    def setup(strategy):
        strategy.tick_commission = 1.0

    bt = _shared.run_cross(lambda d, s: getattr(d, s)(), setup=setup)
    print('④ self.tick_commission = 1.0 -> 手续费=%.2f'
          % float(bt.strategies[0].account.total_commission))

    # ⑤ 滑点
    print('⑤ 滑点：self.data.slip_point = 1.0（买 +1 / 卖 -1，价格单位）')


if __name__ == '__main__':
    main()
