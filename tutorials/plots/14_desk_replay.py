"""14 · Gui.Desk 回放 —— 策略挂上图表，用 desk 的 ▶▶ 逐根回放

模式：**desk 界面 + 回放**
运行：``python tutorials/plots/14_desk_replay.py``
（Jupyter：打开 ``14_desk_replay.ipynb``，同一个例子，单元格形式）

desk 的回放和 ``Gui.Pylightcharts`` 的独立回放窗口**不是一回事**：

* Python 侧只负责把策略「加到图表」（``Bt(replay=True)`` 让策略按逐根回放预算，
  止损线有历史；``desk_mode='replay'`` 表示不再额外打开回测页）；
* **播放 / 暂停 / 单步 / 0.5x~10x / 选择时间段**都在 desk 界面里
  （工具栏 ▶ 或图表底部回放条）；
* 回放时策略按**回放价**在「本地模拟账户」成交，持仓线 / 账户 / 交易记录
  都跟着回放走；退出回放会恢复回放前的 K 线 / 指标 / 可视范围 ✓。

所以：**跑完这个脚本后，在 desk 里点 ▶ 开始回放**（默认截取末尾 30%）。

切换提示：``Bt(replay=True).run(gui=Gui.Pylightcharts)`` 是独立的回放窗口；
``gui=Gui.PylightchartsWeb`` 是浏览器里的回放；``Gui.Bokeh`` 是 bokeh 回放。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from minibt import *                      # noqa: F401,F403
from minibt import (BtIndicator, Colors, Config, Gui, LineDash, LineStyle,
                    LocalDatas, Markers, SignalStyle, Strategy)


class ReplayMa(BtIndicator):
    """双均线 + 交叉箭头。"""

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


class ReplayMaStrategy(Strategy):
    """回放用策略：金叉多 1 手 / 死叉平仓（成交走本地模拟账户）。"""

    config = Config(value=1_000_000.0, margin_rate=0.05,
                    fixed_commission=1.0)
    params = dict(size=1)

    def __init__(self):
        self.min_start_length = 30
        self.data = self.get_kline(LocalDatas.l2609_60)
        self.ma = ReplayMa(self.data)

    def next(self):
        position = float(getattr(self.data.position, 'pos',
                                 self.data.position) or 0.0)
        if self.ma.long_signal.new and position <= 0:
            self.data.set_target_size(int(self.params.size))
        elif self.ma.short_signal.new and position > 0:
            self.data.set_target_size(0)


if __name__ == '__main__':
    bt = Bt(auto=False, replay=True)
    bt.addstrategy(ReplayMaStrategy)
    # ★ 加到图表（回放版），不额外打开回测页
    bt.run(gui=Gui.Desk, desk_mode='replay')
