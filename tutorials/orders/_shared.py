"""orders 示例的共用小工具：一个 EMA 交叉指标 + 回测入口。

不放进 `minibt` 包里 —— 只是教程用的"脚手架"，让每个 10.x 例子都能
**只关注自己的那个概念**（订单类型 / 目标仓位 / 冷却 / 反手 / 止损）。

用法::

    from _shared import run_cross

    bt = run_cross(lambda data, side: data.buy(exectype=OrderType.Market)
                                       if side == 'buy' else
                                       data.sell(exectype=OrderType.Market))
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *            # noqa: E402,F401,F403


class Cross(BtIndicator):
    """10/30 EMA 交叉（只出信号）。"""

    lines = ('ema_fast', 'ema_slow', 'long_signal', 'short_signal')
    params = dict(FAST=10, SLOW=30)
    overlap = dict(ema_fast=True, ema_slow=True)
    isplot = dict(long_signal=False, short_signal=False)
    linestyle = dict(
        ema_fast=LineStyle(line_color=Colors.orange, line_width=1.5),
        ema_slow=LineStyle(line_color=Colors.blue, line_width=1.5),
    )

    def next(self):
        p = self.params
        fast = self.close.ema(p.FAST)
        slow = self.close.ema(p.SLOW)
        return fast, slow, fast.cross_up(slow), fast.cross_down(slow)


def run_cross(order_fn, config=None, guard=None, setup=None):
    """跑一遍 EMA 交叉回测。

    :param order_fn: ``order_fn(data, side)``，``side`` 是 ``'buy'`` / ``'sell'``；
                     里面自己决定用哪种下单方式（`buy` / `set_target_size` / …）
    :param config: 策略 `Config`（默认不打印账户表）
    :param guard: 可选 ``guard(strategy) -> bool``；返回 True 表示**这一拍跳过下单**
                  （冷却 / 过滤用）
    :param setup: 可选 ``setup(strategy)``，在 ``__init__`` 末尾调用（设手续费/滑点等）
    :return: 跑完的 `Bt`
    """
    cfg = config or Config(print_account=False, islog=False)

    class _Strategy(Strategy):
        config = cfg

        def __init__(self):
            # ★ 每次从 CSV 重新读一条 K 线：`LocalDatas.test.kline` 是**共享对象**，
            #   连续跑多次回测会把上一次的持仓/止损状态带进来（数字会飘）
            self.data = self.kline_from_path(LocalDatas.get_path('test'))
            self.ind = Cross(self.data)
            if setup is not None:
                setup(self)

        def next(self):
            if guard is not None and guard(self):
                return
            if self.ind.long_signal.new:
                order_fn(self.data, 'buy')
            elif self.ind.short_signal.new:
                order_fn(self.data, 'sell')

    # ★ `Bt(auto=False)` + 显式 addstrategy：只跑这一条策略。
    #   `Bt(auto=True)`（默认）会自动把**全局所有** Strategy 都跑一遍，
    #   同一进程里连续回测会互相干扰（结果取到上一轮的）✗
    bt = Bt(auto=False)
    bt.addstrategy(_Strategy)
    bt.run(isplot=False, isreport=False)
    return bt


def account_snapshot(bt):
    """从跑完的 `Bt` 里取一份账户快照（dict）。"""
    strategy = bt.strategies[0]
    account = strategy.account
    def _f(name):
        try:
            return float(getattr(account, name, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    return {
        'cash': _f('cash'),                  # 可用现金
        'balance': _f('balance'),            # 账户权益
        'margin': _f('margin'),              # 占用保证金
        'risk_ratio': _f('risk_ratio'),      # 风险度
        'total_profit': _f('total_profit'),  # 总盈亏
        'total_commission': _f('total_commission'),
        'profit': _f('profit'),              # 当期盈亏
        'net': _f('net'),                    # 盈利率（小数）
    }
