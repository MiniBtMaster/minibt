"""11.8 · 实盘 vs 回测 —— 差异清单 + 实测影响

演示要点
--------
回测是"理想成交"，实盘有这些差异：

| 差异 | 回测 | 实盘 | 本例怎么变差 |
| --- | --- | --- | --- |
| 成交价 | `Close`/`Market` 精确成交 | 排队、滑点、部分成交 | `slip_point=1` |
| 手续费 | 可设/可忽略 | 真实扣费 | `tick_commission=1` |
| 保证金 | `margin_rate` | 交易所/期货公司加收 | 见 10.9 |
| 数据 | 完整历史 | 断线/延迟/缺口 | 11.5 |
| 交易时段 | 全时段可交易 | 只能在时段内 | 10.11 |

本例用同一策略跑三遍，量化"滑点 / 手续费"的影响（离线、可复现）。

运行：``python tutorials/realtime/08_live_vs_backtest.py``
文档：``minibt_docs/docs/minibt_realtime/11.8_live_vs_backtest.md``
"""

import os
import sys

_ORDERS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'orders')
sys.path.insert(0, _ORDERS)

import _shared                                        # noqa: E402
from minibt import *                                  # noqa: E402,F403

BASE = dict(print_account=False, islog=False)


def _run(label, config=None, setup=None):
    bt = _shared.run_cross(lambda d, s: getattr(d, s)(),
                           config=config, setup=setup)
    acc = bt.strategies[0].account
    print('  %-22s 手续费=%8.2f | 权益=%12.2f'
          % (label, float(acc.total_commission), float(acc.balance)))
    return float(acc.balance)


def main(gui=None):
    print('① 理想回测（无滑点、无手续费）：')
    ideal = _run('理想', config=_shared.Config(**BASE))

    print('② 加滑点（买 +1 / 卖 -1）：')
    slip = _run('slip_point=1.0',
                setup=lambda s: setattr(s.data, 'slip_point', 1.0))

    print('③ 加手续费（tick=1）：')
    fee = _run('tick_commission=1.0',
               config=_shared.Config(tick_commission=1.0, **BASE))

    print('\n④ 差距：滑点 -%.2f | 手续费 -%.2f'
          % (ideal - slip, ideal - fee))
    print('   实盘还会叠加：排队/部分成交、断线、时段限制')


if __name__ == '__main__':
    main()
