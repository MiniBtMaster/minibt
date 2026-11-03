"""10.7 · `@stop_callback` —— 动态止损/止盈回调（numba）

演示要点
--------
```python
@stop_callback
def my_sl(bar_idx, direction, entry, price, ref, cur_dist, tick, mult,
          size, args_data, args_count):
    return 5.0 * tick            # 返回：止损距离（价格单位）

ind.signal_backtest(sl_callback=my_sl, sl_stop=10, stop_mode=0, ...)
```

| 参数 | 说明 |
| --- | --- |
| `sl_callback` / `tp_callback` | 止损 / 止盈回调（`@stop_callback` 编译） |
| `sl_stop` / `tp_stop` | 固定止损/止盈（tick 数或价格，看 `stop_mode`） |
| `stop_mode` | 0 = 距离、1 = 百分比、2 = 价格（按实现） |
| `sl_callback_args` / `tp_callback_args` | 传给回调的**数组**（`args_data[bar_idx]` 取当根值） |

⚠ 回调要 **numba 可编译**（纯 Python 数值运算，别用 pandas）。

运行：``python tutorials/orders/07_stop_callback.py``
文档：``minibt_docs/docs/minibt_orders/10.7_stop_callback.md``
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def _profits(result):
    """从 signal_backtest 的返回值里取**累计平仓盈亏**末值。"""
    try:
        return round(float(result.result['cum_profits'].iloc[-1]), 2)
    except Exception:                                # noqa: BLE001
        try:
            return round(float(result.profits.iloc[-1]), 2)
        except Exception:                            # noqa: BLE001
            return None


def main(gui=None):
    kline = LocalDatas.test.kline
    ind = kline.tradingview.SingleEMACross(ema1=10, ema2=20)

    # ① 固定止损（不传回调）
    r1 = ind.signal_backtest(sl_stop=10, stop_mode=0,
                             commission=1.0, com_type=1,
                             isplot=False, isreport=False)
    print('① sl_stop=10 ->', type(r1).__name__, '| 累计盈亏', _profits(r1))

    # ② 回调：固定 5 tick 止损
    @stop_callback
    def my_sl(bar_idx, direction, entry, price, ref, cur_dist, tick, mult,
              size, args_data, args_count):
        return 5.0 * tick

    r2 = ind.signal_backtest(sl_callback=my_sl, sl_stop=10, stop_mode=0,
                             commission=1.0, com_type=1,
                             isplot=False, isreport=False)
    print('② sl_callback=5tick ->', '| 累计盈亏', _profits(r2))

    # ③ 回调 + args_data：前半段紧（3 tick）、后半段松（8 tick）
    dynamic = np.full(len(kline), 3.0)
    dynamic[len(kline) // 2:] = 8.0

    @stop_callback
    def my_sl2(bar_idx, direction, entry, price, ref, cur_dist, tick, mult,
               size, args_data, args_count):
        if args_count > bar_idx:
            return args_data[bar_idx] * tick
        return cur_dist

    r3 = ind.signal_backtest(sl_callback=my_sl2,
                             sl_callback_args=(dynamic,),
                             sl_stop=10, stop_mode=0,
                             commission=1.0, com_type=1,
                             isplot=False, isreport=False)
    print('③ 动态（3→8 tick） ->', '| 累计盈亏', _profits(r3))

    # ④ 返回对象上的统计
    print('④ r.stats:', type(r3.stats).__name__,
          '| r.result 列:', list(r3.result.columns)[:6])


if __name__ == '__main__':
    main()
