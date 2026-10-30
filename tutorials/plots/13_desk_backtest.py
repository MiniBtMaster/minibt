"""13 · Gui.Desk 回测 —— 策略「加到图表」+ desk「策略回测」页

模式：**desk 界面 + 回测**
运行：``python tutorials/plots/13_desk_backtest.py``
（Jupyter：打开 ``13_desk_backtest.ipynb``，同一个例子，单元格形式）

演示：

* ``bt.run(gui=Gui.Desk, desk_mode='backtest')`` —— 等价于在 desk 里点
  **「策略回测」**：本地图表「加到图表」 → 再开一个回测页；
* 回测页里能看到：合约图（K 线 + 指标 + 买卖点 / 停止线）、
  **回测结果**（权益 / 回撤双轴曲线）、**交易记录**、**指标记录**（16 项统计）；
* 一个策略一个账户、一个策略多个 `get_kline` 共用一个账户；
  数据源由策略 ``get_kline(...)`` 决定（这里是内置本地 CSV，离线可跑 ✓）。

切换提示：``desk_mode='chart'`` 只加到图表；``desk_mode='optimize'`` 换成参数
优化页；去掉 ``gui=Gui.Desk`` 就是其它引擎的回测（见 04 / 07）。
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


class DeskMa(BtIndicator):
    """双均线 + 交叉箭头（样式会一起画到 desk 图表 / 回测页上）。"""

    lines = ('fast', 'slow', 'long_signal', 'short_signal')
    params = dict(fast=10, slow=30, cooldown=20)
    overlap = True
    #: 信号列只画箭头，不当普通折线画
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


class DeskBacktestMa(Strategy):
    """金叉多 1 手、死叉平仓（最小可回测策略）。"""

    config = Config(value=1_000_000.0, margin_rate=0.05,
                    fixed_commission=1.0)
    params = dict(size=1)

    def __init__(self):
        self.min_start_length = 30
        self.data = self.get_kline(LocalDatas.l2609_60)
        self.ma = DeskMa(self.data)       # 指标作为属性 → 自动登记给策略

    def next(self):
        position = float(getattr(self.data.position, 'pos',
                                 self.data.position) or 0.0)
        if self.ma.long_signal.new and position <= 0:
            self.data.set_target_size(int(self.params.size))
        elif self.ma.short_signal.new and position > 0:
            self.data.set_target_size(0)


if __name__ == '__main__':
    # ★ auto=False：只跑本文件里 addstrategy 的策略（别把仓库其它策略带上）
    bt = Bt(auto=False)
    bt.addstrategy(DeskBacktestMa)
    bt.run(gui=Gui.Desk, desk_mode='backtest')
