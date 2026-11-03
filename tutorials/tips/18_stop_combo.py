"""5.18 · 止损组合 —— 一个类多档 / 移动止损 / sl+tp+trail

演示要点
--------
| 需求 | 写法 |
| --- | --- |
| 只止损 | `BtStop.FSStop(stop_distance=15)` |
| 只止盈 | `BtStop.FTStop(target_distance=30)` |
| 止损 + 止盈 | `BtStop.FixedStop(stop_distance=15, target_distance=30)` |
| 移动止损 | `BtStop.TrailingStopLoss(trailingstart=10, trailingstep=5)` |
| ATR 自适应 | `BtStop.SegmentationTracking(length=14, mult=2, method='atr')` |
| 止损+止盈+移动（指标回测） | `ind.signal_backtest(sl_stop=10, tp_stop=20, sl_trail=1)` |

⚠ **一个仓位只挂一个停止器**：`buy(stop=...)` 之后再传一个新的不会叠加
（`_set_stop` 里有 `isstop` 守卫），"组合"要靠上面这些**单个类自带的多档参数**。

运行：``python tutorials/tips/18_stop_combo.py``
文档：``minibt_docs/docs/minibt_tips/5.18_stop_combo.md``
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tutorials', 'orders'))

from _shared import account_snapshot, run_cross      # noqa: E402
from minibt import *                                  # noqa: E402,F403


def _report(name, bt):
    snap = account_snapshot(bt)
    pos = bt.strategies[0].position
    print(f'   {name:34s} 总盈亏={snap["total_profit"]:>10,.2f} '
          f'| 手数={pos.pos:+d}')


def main(gui=None):
    # ①~⑥ BtStop 路线：一个停止器类，自带止损/止盈/移动参数
    print('① BtStop 路线（同一个信号，不同停止器）')
    _report('无止损', run_cross(lambda d, s: getattr(d, s)()))
    _report('FSStop(15) 只止损',
            run_cross(lambda d, s: getattr(d, s)(
                stop=BtStop.FSStop(stop_distance=15))))
    _report('FTStop(30) 只止盈',
            run_cross(lambda d, s: getattr(d, s)(
                stop=BtStop.FTStop(target_distance=30))))
    _report('FixedStop(15, 30) 止损+止盈',
            run_cross(lambda d, s: getattr(d, s)(
                stop=BtStop.FixedStop(stop_distance=15,
                                      target_distance=30))))
    _report('TrailingStopLoss(10, 5) 移动止损',
            run_cross(lambda d, s: getattr(d, s)(
                stop=BtStop.TrailingStopLoss(trailingstart=10,
                                             trailingstep=5))))
    _report('SegmentationTracking(ATR14×2)',
            run_cross(lambda d, s: getattr(d, s)(
                stop=BtStop.SegmentationTracking(length=14, mult=2.0,
                                                 method='atr'))))

    # ② signal_backtest 路线：一个调用里同时给止损 / 止盈 / 移动
    print('② signal_backtest 路线（指标自带 long/short_signal）')
    kline = LocalDatas.test.kline
    ind = kline.tradingview.SingleEMACross(ema1=10, ema2=20)

    def profits(result):
        try:
            return round(float(result.result['cum_profits'].iloc[-1]), 2)
        except Exception:                              # noqa: BLE001
            return None

    base = ind.signal_backtest(commission=1.0, com_type=1,
                               isplot=False, isreport=False)
    print('   无止损                    累计盈亏',
          profits(base))

    combo = ind.signal_backtest(sl_stop=10, tp_stop=20, stop_mode=0,
                                sl_trail=1,
                                commission=1.0, com_type=1,
                                isplot=False, isreport=False)
    print('   sl=10 + tp=20 + sl_trail=1 累计盈亏',
          profits(combo))

    # ③ 第三种组合：@stop_callback 动态改止损距离（见 10.7）
    @stop_callback
    def dynamic_sl(bar_idx, direction, entry, price, ref, cur_dist,
                   tick, mult, size, args_data, args_count):
        return (5.0 + (bar_idx % 20) / 10.0) * tick    # 5~7 tick 之间变化

    dyn = ind.signal_backtest(sl_callback=dynamic_sl, sl_stop=10,
                              stop_mode=0, commission=1.0, com_type=1,
                              isplot=False, isreport=False)
    print('   @stop_callback 动态止损   累计盈亏',
          profits(dyn))

    print('\n③ 结论')
    print('   - 一个仓位只挂一个 BtStop；要"组合"就选自带多档参数的那个类')
    print('   - 指标回测直接 signal_backtest(sl_stop=, tp_stop=, sl_trail=1)')
    print('   - 随行情变化的止损用 @stop_callback（numba）')


if __name__ == '__main__':
    main()
