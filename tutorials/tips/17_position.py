"""5.17 · 仓位管理三件套 —— set_target_size / 冷却 / 反手

演示要点
--------
| 写法 | 语义 | 备注 |
| --- | --- | --- |
| `data.buy()` / `sell()` | **加仓**（每次 +1，可能越加越多） | 基线 |
| `data.set_target_size(n)` | **目标仓位**：调到 n 手（正多负空，0 平），幂等 | 建议默认用它 |
| `set_target_size(n, reverse=True)` | 持反向仓时**先平后开** | 空仓时等同普通目标仓位 |
| 自记 bar + 冷却 | 距上次开仓不足 N 根就跳过 | `in_cooldown` 回测里恒 False |
| `in_cooldown(...)` | **只在实盘生效** | 回测里调用 8964 次命中 0 次 |

运行：``python tutorials/tips/17_position.py``
文档：``minibt_docs/docs/minibt_tips/5.17_position.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'tutorials', 'orders'))

from _shared import account_snapshot, run_cross      # noqa: E402
from minibt import *                                  # noqa: E402,F403


def _report(name, bt, extra=''):
    snap = account_snapshot(bt)
    pos = bt.strategies[0].position
    print(f'   {name:30s} 总盈亏={snap["total_profit"]:>10,.2f} '
          f'| 手数={pos.pos:+d} | 方向={int(pos):+d} {extra}')


def main(gui=None):
    print('① 逐笔下单 vs 目标仓位')
    _report('buy()/sell() 加仓',
            run_cross(lambda d, s: getattr(d, s)()))
    _report('set_target_size(±1) 目标仓位',
            run_cross(lambda d, s: d.set_target_size(1 if s == 'buy' else -1)))

    print('② 反手：set_target_size(±1, reverse=True)')
    _report('reverse=False（只调目标）',
            run_cross(lambda d, s: d.set_target_size(1 if s == 'buy' else -1)))
    _report('reverse=True（先平后开）',
            run_cross(lambda d, s: d.set_target_size(
                1 if s == 'buy' else -1, reverse=True)))
    _report('reverse=True, reverse_size=2',
            run_cross(lambda d, s: d.set_target_size(
                1 if s == 'buy' else -1, reverse=True, reverse_size=2)))

    print('③ 目标仓位 + 手动冷却（回测可用）')
    for bars in (20, 100, 500):
        state = {'i': -1, 'last': -10 ** 9, 'blocked': 0}

        def guard(strategy, _bars=bars, _state=state):
            _state['i'] += 1
            want = (strategy.ind.long_signal.new
                    or strategy.ind.short_signal.new)
            if not want:
                return False
            if _state['i'] - _state['last'] < _bars:
                _state['blocked'] += 1
                return True
            return False

        def order(data, side, _state=state):
            _state['last'] = _state['i']
            data.set_target_size(1 if side == 'buy' else -1)

        bt = run_cross(order, guard=guard)
        _report(f'目标仓位 + 冷却 {bars} 根', bt,
                f'| 拦下 {state["blocked"]} 次')

    print('④ 内置 in_cooldown：回测里恒 False（实盘专用）')
    calls = {'n': 0, 'hit': 0}

    def guard_builtin(strategy):
        calls['n'] += 1
        if strategy.in_cooldown(strategy.data, cooldown_bars=100):
            calls['hit'] += 1
            return True
        return False

    run_cross(lambda d, s: d.set_target_size(1 if s == 'buy' else -1),
              guard=guard_builtin)
    print(f'   调用 {calls["n"]} 次 / 命中 {calls["hit"]} 次'
          f' —— 回测里恒 False')

    print('⑤ 三件套一起：目标仓位 2 手 + 冷却 100 根 + 反手')
    state = {'i': -1, 'last': -10 ** 9}

    def guard2(strategy):
        state['i'] += 1
        want = (strategy.ind.long_signal.new
                or strategy.ind.short_signal.new)
        return bool(want and state['i'] - state['last'] < 100)

    def order2(data, side):
        state['last'] = state['i']
        data.set_target_size(2 if side == 'buy' else -2, reverse=True)

    _report('2 手 + 冷却 100 + 反手', run_cross(order2, guard=guard2))


if __name__ == '__main__':
    main()
