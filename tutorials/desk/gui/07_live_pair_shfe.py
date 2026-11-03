"""07 · 实时**配对交易**策略（desk 实时图表，上期所主力：白银 / 黄金）

```bash
python tutorials/desk/gui/07_live_pair_shfe.py --user 账号 --password 密码
```

策略逻辑（最简配对）
--------------------
1. 两腿：`SHFE.ag2612`（白银主力）与 `SHFE.au2612`（黄金主力）；
2. 用 `ag - beta * au` 构造价差，取 60 根滚动 z-score；
3. `z > +1` → 空白银、多黄金；`z < -1` → 多白银、空白银；
   `|z| < 0.3` → 两边都平（套利收敛）；
4. 每条腿 1 手（真实手数按资金自己调）。

desk 里会看到
-------------
* 一个「实时图表」= 左右两格（ag / au），各自带均线 + 价差指标；
* 两格的**持仓线**、账户面板的持仓 / 委托 / 成交是同一个快期模拟账户；
* 想退出：关窗（或 Ctrl+C），desk 会停掉策略并关掉 TqApi。
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
import pandas as pd

from minibt import *                      # noqa: F401,F403
from minibt import (BtIndicator, Colors, Config, Gui, LineDash, LineStyle,
                    Markers, SignalStyle, Strategy)

#: ★ 上期所主力（白银 / 黄金）
LEG_A = 'SHFE.ag2612'
LEG_B = 'SHFE.au2612'


class SpreadZ(BtIndicator):
    """价差 z-score（副图），带零轴参考线用的两条水平线。"""

    lines = ('zscore',)
    params = dict(window=60)
    overlap = False

    linestyle = dict(
        zscore=LineStyle(line_color='#ff9800', line_width=2),
    )
    #: 只画线、不显示图例（想看名字删掉这一行）
    legend = False

    def next(self):
        a = np.asarray(self.close.values, dtype=float)     # 当前腿的价格
        values = pd.Series(a)
        z = ((values - values.rolling(int(self.params.window)).mean())
             / values.rolling(int(self.params.window)).std())
        return z.to_numpy()


class LivePairSpread(Strategy):
    """白银 / 黄金配对：z-score 反向开仓、收敛平仓。"""

    config = Config(value=1_000_000.0, margin_rate=0.05,
                    fixed_commission=1.0)
    params = dict(leg_a=LEG_A, leg_b=LEG_B, window=60,
                  entry=1.0, exit=0.3, size=1)

    def __init__(self):
        self.min_start_length = 120
        self.a = self.get_kline(self.params.leg_a)
        self.b = self.get_kline(self.params.leg_b)
        #: 主图均线（两条腿各画自己的）
        self.ma_a = self.a.close.sma(30, overlap=True)
        self.ma_b = self.b.close.sma(30, overlap=True)
        #: 价差指标（挂在 A 腿的副图）
        self.spread = SpreadZ(self.a)

    # ------------------------------------------------------------ 工具
    @staticmethod
    def _pos(kline) -> float:
        return float(getattr(kline.position, 'pos', kline.position) or 0.0)

    def _z(self):
        a = float(self.a.current_close or np.nan)
        b = float(self.b.current_close or np.nan)
        if not np.isfinite([a, b]).all() or b <= 0:
            return np.nan
        # 用最近 window 根的对数价差算 z-score ✓
        na = np.asarray(self.a.close.values, dtype=float)
        nb = np.asarray(self.b.close.values, dtype=float)
        n = min(len(na), len(nb), int(self.params.window))
        if n < 20:
            return np.nan
        spread = np.log(na[-n:] / np.maximum(nb[-n:], 1e-9))
        std = float(np.nanstd(spread))
        if not np.isfinite(std) or std <= 0:
            return np.nan
        return float((spread[-1] - np.nanmean(spread)) / std)

    def _flat(self):
        if self._pos(self.a):
            self.a.set_target_size(0)
        if self._pos(self.b):
            self.b.set_target_size(0)

    # ------------------------------------------------------------ 交易
    def next(self):
        z = self._z()
        if not np.isfinite(z):
            return
        size = int(self.params.size)
        long_a = self._pos(self.a) > 0
        short_a = self._pos(self.a) < 0
        long_b = self._pos(self.b) > 0
        short_b = self._pos(self.b) < 0
        holding = long_a or short_a or long_b or short_b

        # 收敛 → 平掉两条腿
        if holding and abs(z) <= float(self.params.exit):
            self._flat()
            return

        if not holding:
            if z >= float(self.params.entry):          # A 贵 B 便宜
                self.a.set_target_size(-size)
                self.b.set_target_size(size)
            elif z <= -float(self.params.entry):       # A 便宜 B 贵
                self.a.set_target_size(size)
                self.b.set_target_size(-size)


def main() -> int:
    parser = argparse.ArgumentParser(description='desk 实时配对策略示例')
    parser.add_argument('--user', default=os.environ.get('TQ_USER', ''))
    parser.add_argument('--password', default=os.environ.get('TQ_PASS', ''))
    parser.add_argument('--leg-a', default=LEG_A)
    parser.add_argument('--leg-b', default=LEG_B)
    args = parser.parse_args()
    if not args.user or not args.password:
        print('请提供天勤账号：--user 账号 --password 密码'
              '（或设置环境变量 TQ_USER / TQ_PASS）')
        return 2

    from tqsdk import TqApi, TqAuth, TqKq
    api = TqApi(TqKq(), auth=TqAuth(args.user, args.password))

    strategy = LivePairSpread.copy(name='LivePairSpread',
                                   params=dict(leg_a=args.leg_a,
                                               leg_b=args.leg_b, size=1))
    bt = Bt(auto=False, live=True)
    bt.addTqapi(api=api)
    bt.addstrategy(strategy)
    bt.run(gui=Gui.Desk)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
