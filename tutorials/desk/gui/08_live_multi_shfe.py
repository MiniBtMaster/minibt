"""08 · 实时**多策略**（desk 里每个策略一个图表页）

```bash
python tutorials/desk/gui/08_live_multi_shfe.py --user 账号 --password 密码
```

三个策略同时跑（都是上期所主力）：

| 策略 | 合约 | 逻辑 |
| --- | --- | --- |
| `LiveMaAg` | `SHFE.ag2612` 白银 | 双均线金叉多 / 死叉平 |
| `LiveMaAu` | `SHFE.au2612` 黄金 | 反向：死叉做空 / 金叉平 |
| `LiveBreakCu` | `SHFE.cu2612` 铜 | 区间突破（20 根高低点） |

desk 会打开 **3 个实时图表页**（每个策略一页），各自带指标 + 买卖箭头；
右下角账户面板是同一个快期模拟账户（能看到三条腿的持仓）。
关窗 / Ctrl+C 一起停。
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np

from minibt import *                      # noqa: F401,F403
from minibt import (BtIndicator, Colors, Config, Gui, LineDash, LineStyle,
                    Markers, SignalStyle, Strategy)

AG = 'SHFE.ag2612'
AU = 'SHFE.au2612'
CU = 'SHFE.cu2612'


# ------------------------------------------------------------------ 指标
class MaLines(BtIndicator):
    """双均线（样式在 desk 图上生效）。"""

    lines = ('fast', 'slow')
    params = dict(fast=10, slow=30)
    overlap = True
    linestyle = dict(
        fast=LineStyle(line_color='#f6c343', line_width=2),
        slow=LineStyle(line_color='#2196f3', line_width=2,
                       line_dash=LineDash.dashed),
    )

    def next(self):
        fast = self.close.rolling(int(self.params.fast)).mean().to_numpy()
        slow = self.close.rolling(int(self.params.slow)).mean().to_numpy()
        return fast, slow


class Breakout(BtIndicator):
    """区间突破指标：上轨 / 下轨 + 突破箭头。"""

    lines = ('upper', 'lower', 'long_signal', 'short_signal')
    params = dict(length=20)
    overlap = True
    isplot = dict(long_signal=False, short_signal=False)
    linestyle = dict(
        upper=LineStyle(line_color='#ef5350', line_width=1,
                        line_dash=LineDash.dotted, price_label=False),
        lower=LineStyle(line_color='#26a69a', line_width=1,
                        line_dash=LineDash.dotted, price_label=False),
    )
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.lime, Markers.arrow_up, size=12),
        short_signal=SignalStyle('high', Colors.tomato, Markers.arrow_down,
                                 size=12),
    )

    def next(self):
        high = self.high.rolling(int(self.params.length)).max().to_numpy()
        low = self.low.rolling(int(self.params.length)).min().to_numpy()
        close = np.asarray(self.close.values, dtype=float)
        prev_high = np.concatenate(([np.nan], high[:-1]))
        prev_low = np.concatenate(([np.nan], low[:-1]))
        long_signal = np.where(close > prev_high, 1.0, 0.0)
        short_signal = np.where(close < prev_low, -1.0, 0.0)
        return high, low, long_signal, short_signal


# ------------------------------------------------------------------ 策略
class LiveMaAg(Strategy):
    """白银：金叉多 1 手、死叉平。"""

    params = dict(symbol=AG, size=1)

    def __init__(self):
        self.min_start_length = 60
        self.data = self.get_kline(self.params.symbol)
        self.ma = MaLines(self.data)

    def next(self):
        position = float(getattr(self.data.position, 'pos',
                                 self.data.position) or 0.0)
        if self.ma.fast.new > self.ma.slow.new and position <= 0:
            self.data.set_target_size(int(self.params.size))
        elif self.ma.fast.new < self.ma.slow.new and position > 0:
            self.data.set_target_size(0)


class LiveMaAu(Strategy):
    """黄金：**反向**——死叉做空 1 手、金叉平。"""

    params = dict(symbol=AU, size=1)

    def __init__(self):
        self.min_start_length = 60
        self.data = self.get_kline(self.params.symbol)
        self.ma = MaLines(self.data)

    def next(self):
        position = float(getattr(self.data.position, 'pos',
                                 self.data.position) or 0.0)
        if self.ma.fast.new < self.ma.slow.new and position >= 0:
            self.data.set_target_size(-int(self.params.size))
        elif self.ma.fast.new > self.ma.slow.new and position < 0:
            self.data.set_target_size(0)


class LiveBreakCu(Strategy):
    """铜：突破 20 根高点做多、跌破低点做空（始终有仓）。"""

    params = dict(symbol=CU, size=1)

    def __init__(self):
        self.min_start_length = 40
        self.data = self.get_kline(self.params.symbol)
        self.bo = Breakout(self.data)

    def next(self):
        size = int(self.params.size)
        if self.bo.long_signal.new:
            self.data.set_target_size(size)
        elif self.bo.short_signal.new:
            self.data.set_target_size(-size)


# ------------------------------------------------------------------ 入口
def main() -> int:
    parser = argparse.ArgumentParser(description='desk 多策略实时示例')
    parser.add_argument('--user', default=os.environ.get('TQ_USER', ''))
    parser.add_argument('--password', default=os.environ.get('TQ_PASS', ''))
    args = parser.parse_args()
    if not args.user or not args.password:
        print('请提供天勤账号：--user 账号 --password 密码'
              '（或设置环境变量 TQ_USER / TQ_PASS）')
        return 2

    from tqsdk import TqApi, TqAuth, TqKq
    api = TqApi(TqKq(), auth=TqAuth(args.user, args.password))

    account = Config(value=1_000_000.0, margin_rate=0.05,
                     fixed_commission=1.0)
    strategies = []
    for cls in (LiveMaAg, LiveMaAu, LiveBreakCu):
        cls.config = account                       # 同一个资金配置 ✓
        strategies.append(cls.copy(name=cls.__name__))

    bt = Bt(auto=False, live=True)                 # auto=False：只跑这三个
    bt.addTqapi(api=api)
    bt.addstrategy(*strategies)
    bt.run(gui=Gui.Desk)                           # → 3 个实时图表页
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
