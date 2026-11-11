"""15 · Gui.Desk 实时 —— 策略进 desk 的「实时图表」，按策略真下单

模式：**desk 界面 + 实时（快期模拟盘）**
运行：

```bash
# 天勤账号（快期模拟即可）
python tutorials/plots/15_desk_live.py --user 账号 --password 密码
set TQ_USER=账号 & set TQ_PASS=密码 & python tutorials/plots/15_desk_live.py
```

Jupyter：打开 ``15_desk_live.ipynb``，先在单元格里填账号（或设环境变量
``TQ_USER`` / ``TQ_PASS``）再运行 —— desk 会以 **iframe** 内嵌实时图表。

演示：

* ``Bt(live=True).run(gui=Gui.Desk)`` —— desk 复用这个 `TqApi`，打开
  **实时图表** 并「加到图表」；图上按策略**真实下单**（默认快期模拟盘）；
* desk 底部账户面板能看到持仓 / 委托 / 成交；工具栏可切周期 / 指标 / 布局；
* 关窗（或 Ctrl+C）→ 停策略并关闭天勤连接。

默认合约 ``SHFE.ag2612``（上期所白银主力），可用 ``--symbol`` 换。
⚠ 交易时段外能连上但没有行情；请先用快期模拟验证。

切换提示：``gui=Gui.Pylightcharts``（原生窗口）/ ``Gui.PylightchartsWeb``
（浏览器标签）—— 策略代码完全不用改，只换 ``gui``。
"""

from __future__ import annotations

import argparse
import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from minibt import *                      # noqa: F401,F403
from minibt import (BtIndicator, Colors, Config, Gui, LineDash, LineStyle,
                    Markers, SignalStyle, Strategy)

#: ★ 上期所主力合约（白银）；换黄金：SHFE.au2612
SYMBOL = 'SHFE.ag2612'


class LiveMa(BtIndicator):
    """双均线 + 交叉箭头（实时图上用的指标）。"""

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


class LiveMaStrategy(Strategy):
    """实时策略：金叉多 1 手、死叉平仓。

    ``params.symbol`` 一定要写具体合约：desk 靠它决定打开哪个实时图表页
    （主连 / 指数 ``KQ.*`` 不可交易，只适合看行情 ✓）。
    """

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
    parser = argparse.ArgumentParser(description='desk 实时（Gui.Desk）示例')
    parser.add_argument('--user', default=os.environ.get('TQ_USER', ''))
    parser.add_argument('--password', default=os.environ.get('TQ_PASS', ''))
    parser.add_argument('--symbol', default=SYMBOL)
    args = parser.parse_args()
    if not args.user or not args.password:
        print('请提供天勤账号：--user 账号 --password 密码'
              '（或设置环境变量 TQ_USER / TQ_PASS）')
        return 2

    from tqsdk import TqApi, TqAuth, TqKq
    # 快期模拟盘（不动真钱）；实盘账户写法见 tutorials/desk/gui/06
    api = TqApi(TqKq(), auth=TqAuth(args.user, args.password))

    strategy = LiveMaStrategy.copy(name='LiveMaStrategy',
                                   params=dict(symbol=args.symbol, size=1))
    bt = Bt(auto=False, live=True)      # auto=False：只跑这一个策略
    bt.addTqapi(api=api)
    bt.addstrategy(strategy)
    # ★ desk：实时图表「加到图表」= 真下单（模拟盘）；关窗即停
    bt.run(gui=Gui.Desk)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
