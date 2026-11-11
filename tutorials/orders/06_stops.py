"""10.6 · 止损止盈 —— `BtStop` 九种策略

演示要点
--------
`buy/sell(stop=...)` 挂上止损策略：

```python
data.buy(stop=BtStop.FixedStop(stop_distance=10, target_distance=20))
data.buy(stop=BtStop.SegmentationTracking(length=14, mult=2.0, method='atr'))
data.buy(stop=BtStop.ThreeCommasStop)      # 也可以只给类（用默认参数）
```

| `BtStop` | 主要参数 | 说明 |
| --- | --- | --- |
| `FixedStop` | `stop_distance` / `target_distance` | 固定点数止损 + 止盈 |
| `FSStop` | `stop_distance` | 只固定止损 |
| `FTStop` | `target_distance` | 只固定止盈 |
| `SegmentationTracking` | `length` / `mult` / `method` / `acceleration` / `min_distance` | 分段跟踪（ATR 等） |
| `TimeSegmentationTracking` | `count` / `length` / `mult` / `days` / `acceleration` | 时间分段跟踪 |
| `TrailingStopLoss` | `trailingstart` / `trailingstep` | 标准跟踪止损 |
| `AnotherATRTrailingStop` | （默认参数） | 另一种 ATR 跟踪 |
| `ThreeCommasStop` | `swing_lookback` / `atr_len` / `risk_m` / `rnr` / `use_limit` / `trail_stop` … | 摆动点 + ATR + 盈亏比 |
| `CAC40` | `trailstart` / `basepercent` / `stepsize` / `percentinc` / `roundto` … | CAC40 分段利润跟踪 |

运行：``python tutorials/orders/06_stops.py``
文档：``minibt_docs/docs/minibt_orders/10.6_stops.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _shared import account_snapshot, run_cross      # noqa: E402
from minibt import *                                  # noqa: E402,F403


def _report(name, bt):
    snap = account_snapshot(bt)
    pos = bt.strategies[0].position
    print(f'  {name:26s} 总盈亏={snap["total_profit"]:>10,.2f} '
          f'| 手数={pos.pos:+d}')


def main(gui=None):
    print('① 无止损：')
    _report('无', run_cross(lambda d, s: getattr(d, s)()))

    print('② FixedStop（10 点止损 / 20 点止盈）：')
    _report('FixedStop(10,20)',
            run_cross(lambda d, s: getattr(d, s)(
                stop=BtStop.FixedStop(stop_distance=10,
                                      target_distance=20))))

    print('③ FSStop（只止损 15 点）：')
    _report('FSStop(15)',
            run_cross(lambda d, s: getattr(d, s)(
                stop=BtStop.FSStop(stop_distance=15))))

    print('④ SegmentationTracking（ATR 分段跟踪）：')
    _report('SegmentationTracking',
            run_cross(lambda d, s: getattr(d, s)(
                stop=BtStop.SegmentationTracking(length=14, mult=2.0,
                                                 method='atr'))))

    print('⑤ ThreeCommasStop（默认参数）：')
    _report('ThreeCommasStop',
            run_cross(lambda d, s: getattr(d, s)(
                stop=BtStop.ThreeCommasStop)))

    print('\n⑥ 九种策略全在 BtStop 上；参数以各类 docstring / 实参为准')


if __name__ == '__main__':
    main()
