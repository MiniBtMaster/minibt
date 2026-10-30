"""10.11 · 交易时段 —— `TradeTimeFilter`

演示要点
--------
```python
from minibt.utils import TradeTimeFilter

f = TradeTimeFilter(day_segments=[('09:00:00', '10:15:00'),
                                  ('10:30:00', '11:30:00'),
                                  ('13:30:00', '15:00:00')])
f.exclude_open_minutes(15)      # 开盘 15 分钟内不交易
f.exclude_close_minutes(10)     # 收盘前 10 分钟不交易
f.exclude_time('11:00:00', '11:15:00')

f.can_trade(datetime.datetime(2026, 1, 5, 9, 30))    # → bool
```

| 成员 | 说明 |
| --- | --- |
| `can_trade(current_time=None)` | 现在能不能交易 |
| `exclude_time(start, end)` | 排除一个时段 |
| `exclude_open_minutes(n)` / `exclude_close_minutes(n)` | 开盘后 / 收盘前 n 分钟 |
| `get_sessions_info()` / `get_tradable_segments()` | 会话 / 可交易段 |
| `tradable_str` | 人类可读的时段字符串（**属性**，不是方法） |

⚠ 实盘里可以直接用 `kline.exclude_time(...)` / `kline.can_trade()`（它们内部
用天勤的 `tradingtime`）；**回测**没有 tq 对象，就自己构造 `TradeTimeFilter`。

运行：``python tutorials/orders/11_trade_time.py``
文档：``minibt_docs/docs/minibt_orders/10.11_trade_time.md``
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt.utils import TradeTimeFilter               # noqa: E402


def main(gui=None):
    f = TradeTimeFilter(day_segments=[('09:00:00', '10:15:00'),
                                      ('10:30:00', '11:30:00'),
                                      ('13:30:00', '15:00:00')])
    f.exclude_open_minutes(15)
    f.exclude_close_minutes(10)

    # ① 逐时刻判断
    for text in ('08:50', '09:05', '09:30', '10:20', '12:00',
                 '14:00', '14:55'):
        moment = datetime.datetime.strptime('2026-01-05 ' + text,
                                            '%Y-%m-%d %H:%M')
        print(f'① {text} can_trade ->', f.can_trade(moment))

    # ② 会话 / 时段
    print('② get_sessions_info():', f.get_sessions_info()[:2], '…')
    print('   get_tradable_segments():', f.get_tradable_segments()[:3], '…')
    print('   tradable_str:', str(f.tradable_str)[:70])

    # ③ 额外排除一个时段
    f.exclude_time('10:45:00', '11:00:00')
    moment = datetime.datetime.strptime('2026-01-05 10:50', '%Y-%m-%d %H:%M')
    print('③ 10:50 can_trade（排除后） ->', f.can_trade(moment))


if __name__ == '__main__':
    main()
