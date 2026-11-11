"""8.12 · 指标自带交易逻辑 —— 一行 `backtest()`

演示要点
--------
指标类里重写 **`step()`**（交易逻辑），就能**一行回测**，不用写 `Strategy`：

```python
class EmaCrossTrade(BtIndicator):
    ...
    def step(self):                    # ← 每根 K 线调用一次
        if not self.kline.position:    # ★ 交易用 self.kline，不是 self
            if self.long_signal.new:
                self.kline.buy()
            elif self.short_signal.new:
                self.kline.sell()

ind = EmaCrossTrade(kline)
bt = ind.backtest(isplot=False, isreport=False)
```

| 要点 | 说明 |
| --- | --- |
| `step()` 里的 `self` | 是**指标**；交易要走 `self.kline.buy/sell` |
| 只在有 `step` 时能回测 | 普通指标（`macd()`）没有 `step` → 报错 |
| 参数 | `backtest(**kwargs)` 透传 `Bt.run`（`isplot`/`isreport`/`gui`…） |
| 图形入口 | `ind.btplot()` 会自动跑一遍回测（带 `step` 的指标） |

运行：``python tutorials/indicators/12_step_backtest.py``
文档：``minibt_docs/docs/minibt_indicators/8.12_step_backtest.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class EmaCrossTrade(BtIndicator):
    """均线交叉 + 自带交易逻辑（`step`）。"""

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

    def step(self):
        """每一根 K 线调用一次：金叉做多、死叉做空（`reverse` 反手）。"""
        if self.long_signal.new:
            self.kline.buy(reverse=True)      # 有空单就先平掉再开多
        elif self.short_signal.new:
            self.kline.sell(reverse=True)


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 指标里有没有 step
    ind = EmaCrossTrade(kline)
    print('① 有自带 step:', 'step' in getattr(ind, '__dict__', {}))

    # ② 一行回测（不画图/不报告，快）
    bt = ind.backtest(isplot=False, isreport=False,
                      config=Config(print_account=False))
    print('② ind.backtest() ->', type(bt).__name__)

    # ③ 结果结构：list[策略] -> list[腿] -> DataFrame
    res = bt.get_results()
    df = res[0][0]
    print('③ 结果列:', list(df.columns))
    print('   行数:', len(df))
    print('   权益末值(total_profit):',
          round(float(df['total_profit'].iloc[-1]), 2))
    print('   累计平仓盈亏(cum_profits):',
          round(float(df['cum_profits'].iloc[-1]), 2))
    print('   持仓非零行数:', int((df['sizes'] != 0).sum()))

    # ④ 没有 step 的指标不能一键回测
    plain = kline.macd()
    try:
        plain.backtest(isplot=False, isreport=False,
                       config=Config(print_account=False))
    except Exception as error:                       # noqa: BLE001
        print('④ macd().backtest() →', type(error).__name__,
              str(error)[:70])

    # ⑤ 想看带成交标记的图：ind.btplot()（见 7.19）
    print('⑤ 看图：ind.btplot(gui=...)（带 step 会自动跑一遍回测）')


if __name__ == '__main__':
    main()
