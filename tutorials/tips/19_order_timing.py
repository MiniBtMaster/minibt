"""5.19 · 下单时机 —— is_changing / is_key_changing / is_last_price_changing

演示要点
--------
| 属性 | 判断什么 | 典型用法 |
| --- | --- | --- |
| `self.is_changing` | **默认合约的 K 线**是否有新数据 | `if not self.is_changing: return`（K 线驱动） |
| `self.is_key_changing('volume')` | K 线的某个**字段**是否变化 | 只在成交量变化时算 |
| `self.is_last_price_changing` | **任意合约的最新价**是否变化 | 多合约 / 报价驱动的策略 |

⚠ 三个都是**实盘专用属性**（内部先判 `self._is_live_trading`）：
**回测里恒 `False`**，`next()` 本来每根只调用一次，不需要判断。

运行：``python tutorials/tips/19_order_timing.py``
文档：``minibt_docs/docs/minibt_tips/5.19_order_timing.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class FakeApi:
    """把 tqsdk 的 ``is_changing`` 换成一个可离线复现的假实现。"""

    def __init__(self, ticks):
        # ticks: [(kline_changed, volume_changed, last_price_changed), ...]
        self.ticks = list(ticks)
        self.i = 0
        self.calls = {'kline': 0, 'key': 0, 'last': 0}

    def is_changing(self, obj, key=None):
        if self.i >= len(self.ticks):
            return False
        kline_changed, volume_changed, last_changed = self.ticks[self.i]
        if key is None:
            self.calls['kline'] += 1
            return kline_changed
        if key == 'volume':
            self.calls['key'] += 1
            return volume_changed
        self.calls['last'] += 1
        return last_changed


class FakeLive:
    """模拟 Strategy 上的三个属性（只是为了离线演示判断逻辑）。"""

    def __init__(self, api):
        self.api = api

    @property
    def is_changing(self):
        return self.api.is_changing(object())

    def is_key_changing(self, key):
        return self.api.is_changing(object(), key)

    @property
    def is_last_price_changing(self):
        # 真实现是 any([api.is_changing(合约, 'last_price') for 合约 in ...])
        return self.api.is_changing(object(), 'last_price')


def next_tick(strategy):
    """一次 ``next()`` 的典型写法：不满足条件就直接返回。"""
    if not strategy.is_changing:
        return 'skip: K 线没更新'
    if not strategy.is_key_changing('volume'):
        return 'skip: 成交量没变'
    if not strategy.is_last_price_changing:
        return 'skip: 最新价没变'
    return 'run: 下单/调仓'


def main(gui=None):
    # ① 回测里三个属性恒 False
    seen = {'is_changing': set(), 'is_key_changing': set(),
            'is_last_price_changing': set()}

    class Backtest(Strategy):
        config = Config(print_account=False, islog=False)

        def __init__(self):
            self.data = self.get_kline(LocalDatas.test, duration_seconds=300,
                                       data_length=300)
            self.count = 0

        def next(self):
            self.count += 1
            seen['is_changing'].add(self.is_changing)
            seen['is_key_changing'].add(self.is_key_changing('volume'))
            seen['is_last_price_changing'].add(self.is_last_price_changing)

    bt = Bt(auto=False)
    bt.addstrategy(Backtest)
    bt.run(isplot=False, isreport=False, data_length=300)
    strategy = bt.strategies[0]
    print('① 回测：next() 调用', strategy.count, '次（≈ K 线根数）')
    for name, values in seen.items():
        print(f'   {name:24s} 出现过的值: {values}')

    # ② 离线模拟实盘的一段 tick 流
    print('② 实盘 tick 模拟（谁会被拦下）')
    ticks = [
        (False, False, False),   # 纯报价刷新
        (False, True, True),     # 只有 volume / last_price 变
        (True, False, True),     # 新 K 线，但 volume 没变
        (True, True, True),      # 全都变 → 真正执行
    ]
    api = FakeApi(ticks)
    live = FakeLive(api)
    for i, tick in enumerate(ticks):
        api.i = i
        print(f'   tick{i} {tick} -> {next_tick(live)}')

    print('③ 调用计数:', api.calls)
    print('④ 结论：回测不需要这三个属性；实盘用它把"报价刷新"和"K 线更新"分开，'
          '避免同一根 K 线重复下单')


if __name__ == '__main__':
    main()
