"""06 · 实时**单合约**策略（desk 实时图表，上期所主力合约）

```bash
# 天勤账号（快期模拟即可）：命令行参数或环境变量
python tutorials/desk/gui/06_live_single_shfe.py --user 账号 --password 密码
set TQ_USER=账号 & set TQ_PASS=密码 & python tutorials/desk/gui/06_live_single_shfe.py
```

跑起来会发生什么
----------------
1. `TqApi(TqKq(), auth=TqAuth(...))` 登录（快期模拟盘，不动真钱）；
2. `Bt(live=True, auto=False).addTqapi(api).run(gui=Gui.Desk)` →
   desk 复用**同一个 TqApi**，打开「实时图表」并把策略「加到图表」；
3. 图上就是这个策略的指标 + 买卖箭头，**按策略真实下单**
   （desk 右下角账户面板能看到持仓 / 委托 / 成交）。

默认合约：`SHFE.ag2612`（上期所白银主力）。想换成主力连续/其它合约，
改下面的 `SYMBOL`；或用 `--symbol SHFE.au2612`。

⚠ 交易时段外连得上但没有行情；不确定时先用快期模拟跑。
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

#: ★ 上期所主力合约（白银）。换黄金：SHFE.au2612
SYMBOL = 'SHFE.ag2612'


class LiveMa(BtIndicator):
    """实时图上的双均线 + 交叉箭头。"""

    lines = ('fast', 'slow', 'long_signal', 'short_signal')
    params = dict(fast=10, slow=30, cooldown=30)
    overlap = True
    isplot = dict(long_signal=False, short_signal=False)

    linestyle = dict(
        fast=LineStyle(line_color='#f6c343', line_width=2),
        slow=LineStyle(line_color='#2196f3', line_width=2,
                       line_dash=LineDash.dashed),
    )
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.lime, Markers.arrow_up,
                                size=12).set_label('B', 11, color='#26a69a'),
        short_signal=SignalStyle('high', Colors.tomato, Markers.arrow_down,
                                 size=12).set_label('S', 11, color='#ef5350'),
    )

    def next(self):
        fast = self.close.rolling(int(self.params.fast)).mean().to_numpy()
        slow = self.close.rolling(int(self.params.slow)).mean().to_numpy()
        diff = fast - slow
        prev = np.concatenate(([np.nan], diff[:-1]))
        up = np.where((prev <= 0) & (diff > 0), 1.0, 0.0)
        dn = np.where((prev >= 0) & (diff < 0), -1.0, 0.0)
        return fast, slow, up, dn


class LiveSingleMa(Strategy):
    """单合约实时：金叉多 1 手、死叉平仓。"""

    config = Config(value=1_000_000.0, margin_rate=0.05,
                    fixed_commission=1.0)
    params = dict(symbol=SYMBOL, size=1)

    def __init__(self):
        self.min_start_length = 60
        self.data = self.get_kline(self.params.symbol)
        self.ma = LiveMa(self.data)

    def next(self):
        position = float(getattr(self.data.position, 'pos',
                                 self.data.position) or 0.0)
        if self.ma.long_signal.new and position <= 0:
            self.data.set_target_size(int(self.params.size))
        elif self.ma.short_signal.new and position > 0:
            self.data.set_target_size(0)


def main() -> int:
    parser = argparse.ArgumentParser(description='desk 实时单合约策略示例')
    parser.add_argument('--user', default=os.environ.get('TQ_USER', ''))
    parser.add_argument('--password', default=os.environ.get('TQ_PASS', ''))
    parser.add_argument('--symbol', default=SYMBOL)
    parser.add_argument('--real', action='store_true',
                        help='用实盘账户（默认快期模拟 TqKq）')
    args = parser.parse_args()
    if not args.user or not args.password:
        print('请提供天勤账号：--user 账号 --password 密码'
              '（或设置环境变量 TQ_USER / TQ_PASS）')
        return 2

    from tqsdk import TqAccount, TqApi, TqAuth, TqKq
    auth = TqAuth(args.user, args.password)
    api = TqApi(TqKq(), auth=auth) if not args.real else TqApi(
        TqAccount(args.user, args.password, ''), auth=auth)

    strategy = LiveSingleMa.copy(name='LiveSingleMa',
                                 params=dict(symbol=args.symbol, size=1))
    bt = Bt(auto=False, live=True)      # auto=False：只跑这一个策略
    bt.addTqapi(api=api)
    bt.addstrategy(strategy)
    # ★ desk 实时图表「加到图表」= 真下单（模拟盘）；关窗即停
    bt.run(gui=Gui.Desk)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
