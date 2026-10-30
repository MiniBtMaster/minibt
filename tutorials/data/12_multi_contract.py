"""9.12 · 多合约 / 多品种

演示要点
--------
| 场景 | 做法 |
| --- | --- |
| 一个策略里两个合约 | `self.a = self.get_kline(...)`、`self.b = self.get_kline(...)` |
| 看有哪些合约 | `self.klines`（列表）/ `self.klinesset`（字典）/ `self.kline`（默认第一条） |
| 配对/价差回测 | `ind.pair_backtest(kline_a=..., kline_b=...)` |
| 多策略并行 | `Bt().addstrategy(S1, S2).run()` |
| 数据分块 | `Config(data_segments=...)` |

⚠️ 只有 ``self.xxx = self.get_kline(...)``（**赋值**）才登记到 ``klinesset``；
光调 ``get_kline()`` 不登记（框架靠 `Strategy.__setattr__` 收口）。

运行：``python tutorials/data/12_multi_contract.py``
文档：``minibt_docs/docs/minibt_data/9.12_multi_contract.md``
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    strategy = Strategy()

    # ① 两个合约（本地数据，离线）
    a = strategy.get_kline(LocalDatas.pp2609_60, duration_seconds=60,
                           data_length=1500)
    b = strategy.get_kline(LocalDatas.l2609_60, duration_seconds=60,
                           data_length=1500)
    print('① A:', a.symbol, len(a), '根 | B:', b.symbol, len(b), '根')
    print('   两者时间范围一致:', a.datetime.iloc[0] == b.datetime.iloc[0])

    # ② 注册方式（在真实 Strategy 里这么写）
    print('② 策略里注册：')
    print('   self.a = self.get_kline(...)   # → self.klinesset["a"]')
    print('   self.b = self.get_kline(...)')
    print('   self.klines ->', type(strategy.klines).__name__,
          '| self.klinesset ->', type(strategy.klinesset).__name__,
          '（本例没赋值，所以是空的）')

    # ③ 配对回测（价差/配对策略）
    print('③ pair_backtest 签名:')
    print('  ', inspect.signature(IndFrame.pair_backtest))

    # ④ 多策略
    print('④ 多策略：Bt().addstrategy(S1, S2).run()'
          '（各自独立回测，可并行）')

    # ⑤ 数据分块
    print('⑤ Config().data_segments =', Config().data_segments,
          '（数据切段，用于并行/分块，一般不用改）')

    # ⑥ 同一策略里跨合约对齐：按 time 对齐（resample/指标都用 time）
    print('⑥ A/B 都按 time 对齐；配对用 (A - B) 之类的价差序列即可')


if __name__ == '__main__':
    main()
