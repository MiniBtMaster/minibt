"""04 · 本地图表「策略回测」（desk 界面）

```bash
python tutorials/desk/gui/04_backtest_local_chart.py
```

和你在 desk 里点「策略回测」按钮**完全一样**：

1. desk 打开本地图表，把这个策略「加到图表」（自动布局 + 加载 CSV）；
2. 再打开一个「回测」标签页，在后台跑一次真实回测；
3. 回测页里有：资金曲线、成交明细、每笔盈亏、图上 K 线 + 指标 + 买卖点。

命令行里也能直接看结果：`Bt(...).run()` 打印的账户摘要会一起输出到终端。
参数（`--file`）默认就是本文件，所以 desk 的「策略回测」页读的也是这份代码。
"""
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import numpy as np

from minibt import *                      # noqa: F401,F403
from minibt import (BtIndicator, Colors, Config, Gui, LineDash, LineStyle,
                    LocalDatas, Markers, SignalStyle, Strategy)


class BacktestMa(BtIndicator):
    """回测用的指标（样式同样会画在回测页 / 本地图表上）。"""

    lines = ('fast', 'slow', 'long_signal', 'short_signal')
    params = dict(fast=10, slow=30, cooldown=20)
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


class LocalBacktestStrategy(Strategy):
    """单合约双均线（回测示例）。"""

    config = Config(value=1_000_000.0, margin_rate=0.05,
                    fixed_commission=1.0)
    params = dict(size=1)

    def __init__(self):
        self.min_start_length = 30
        self.data = self.get_kline(LocalDatas.l2609_60)
        self.ma = BacktestMa(self.data)

    def next(self):
        position = float(getattr(self.data.position, 'pos',
                                 self.data.position) or 0.0)
        if self.ma.long_signal.new and position <= 0:
            self.data.set_target_size(self.params.size)
        elif self.ma.short_signal.new and position > 0:
            self.data.set_target_size(0)


if __name__ == '__main__':
    # ★ desk：本地图表「加到图表」+ 打开「策略回测」页
    bt = Bt(auto=False)                 # auto=False：只跑本文件的策略
    bt.addstrategy(LocalBacktestStrategy)
    bt.run(gui=Gui.Desk, desk_mode='backtest')
