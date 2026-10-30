"""10.4 · 冷却 —— 防止信号 ping-pong

演示要点
--------
**内置 `in_cooldown` 只在实盘生效**（源码：`if not self._is_live_trading: return False`）：

```python
def next(self):
    if self.in_cooldown(self.data, cooldown_bars=100):   # 实盘：开仓后 100 根内禁交易
        return
```

回测里想要同样效果，要**自己记"上次开仓的 bar"**（本例 ③）。

运行：``python tutorials/orders/04_cooldown.py``
文档：``minibt_docs/docs/minibt_orders/10.4_cooldown.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _shared import account_snapshot, run_cross      # noqa: E402
from minibt import *                                  # noqa: E402,F403


def main(gui=None):
    # ① 无冷却
    bt = run_cross(lambda d, s: getattr(d, s)())
    snap = account_snapshot(bt)
    print('① 无冷却            总盈亏=%10.2f | 手数=%+d'
          % (snap['total_profit'], bt.strategies[0].position.pos))

    # ② 内置 in_cooldown（回测里恒 False，实盘才生效）
    calls = {'n': 0, 'hit': 0}

    def guard_builtin(strategy):
        calls['n'] += 1
        if strategy.in_cooldown(strategy.data, cooldown_bars=100):
            calls['hit'] += 1
            return True
        return False

    bt2 = run_cross(lambda d, s: getattr(d, s)(), guard=guard_builtin)
    print('② 内置 in_cooldown  调用 %d 次 / 命中 %d 次'
          ' —— 回测里恒 False（实盘专用）'
          % (calls['n'], calls['hit']))

    # ③ 手动冷却（回测可用）：距上次开仓不足 N 根就不交易
    #    ⚠ 用自己的 bar 计数器（KLine 里是全部历史，len() 不是"当前 bar"）
    for bars in (20, 100, 500):
        state = {'i': -1, 'last': -10 ** 9, 'skipped': 0}

        def guard(strategy, _bars=bars, _state=state):
            _state['i'] += 1                       # 每根 K 线 +1
            want = (strategy.ind.long_signal.new
                    or strategy.ind.short_signal.new)
            if not want:
                return False
            if _state['i'] - _state['last'] < _bars:
                _state['skipped'] += 1
                return True
            return False

        def order(data, side, _state=state):
            _state['last'] = _state['i']           # 记住这次开仓的 bar
            getattr(data, side)()

        bt3 = run_cross(order, guard=guard)
        snap3 = account_snapshot(bt3)
        print('③ 手动冷却 %3d 根   总盈亏=%10.2f | 手数=%+d | 信号被拦 %d 次'
              % (bars, snap3['total_profit'],
                 bt3.strategies[0].position.pos, state['skipped']))

    print('')
    print('④ 实盘里直接用 in_cooldown(cooldown_seconds=…)；'
          '回测里用 ③ 的手动方案')


if __name__ == '__main__':
    main()
