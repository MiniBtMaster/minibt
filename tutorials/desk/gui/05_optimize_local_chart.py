"""05 · 本地图表「参数优化」（desk 界面，Optuna）

```bash
python tutorials/desk/gui/05_optimize_local_chart.py
```

和你在 desk 里点「参数优化」按钮**完全一样**：

1. desk 打开本地图表，把这个策略「加到图表」；
2. 再打开「优化」标签页，在后台跑 Optuna（可随时点「取消」）；
3. 优化页有：每个 trial 的收益 / 回撤表、最优参数（可一键写回代码）、
   参数热力图（`optimize` 提供的两个参数时）。

> 想少跑几次：改 `op_config['opconfig']['n_trials']`（这里默认 30）。
> 只想看图不要优化：用 `03_strategy_local_chart.py`。
"""
from minibt import (BtIndicator, Colors, Config, Gui, LineDash, LineStyle,
                    LocalDatas, Markers, SignalStyle, Strategy)
import numpy as np
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)


from minibt import *                      # noqa: F401,F403


class OptimizeMa(BtIndicator):
    """优化的两条均线（样式在优化页 / 图表上都生效）。"""

    lines = ('fast', 'slow', 'long_signal', 'short_signal')
    params = dict(fast=10, slow=30)
    overlap = True
    isplot = dict(long_signal=False, short_signal=False)

    linestyle = dict(
        fast=LineStyle(line_color='#f6c343', line_width=2),
        slow=LineStyle(line_color='#2196f3', line_width=2,
                       line_dash=LineDash.dashed),
    )
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.lime, Markers.arrow_up, size=12),
        short_signal=SignalStyle('high', Colors.tomato, Markers.arrow_down,
                                 size=12),
    )

    def next(self):
        fast = self.close.rolling(int(self.params.fast)).mean().to_numpy()
        slow = self.close.rolling(int(self.params.slow)).mean().to_numpy()
        diff = fast - slow
        prev = np.concatenate(([np.nan], diff[:-1]))
        up = np.where((prev <= 0) & (diff > 0), 1.0, 0.0)
        dn = np.where((prev >= 0) & (diff < 0), -1.0, 0.0)
        return fast, slow, up, dn


class LocalOptimizeStrategy(Strategy):
    """被优化的双均线策略（`op_config` 决定优化哪些参数）。"""

    config = Config(value=1_000_000.0, margin_rate=0.05,
                    fixed_commission=1.0)
    params = dict(fast=10, slow=30, size=1)

    #: desk 的「参数优化」页按这份配置搜索（也可以手动勾选参数）
    op_config = dict(
        target='profit_ratio',
        params=dict(fast=range(5, 21, 5), slow=range(20, 61, 10)),
        opconfig=dict(n_trials=30),
    )

    def __init__(self):
        self.min_start_length = 60
        self.data = self.get_kline(LocalDatas.l2609_60)
        # ★ 优化 trial 会改 self.params.fast/slow → 指标必须跟着用同一组参数，
        #   否则每个 trial 都算 10/30 均线，目标值全一样（帕累托成一条水平线 ✗）
        self.ma = OptimizeMa(self.data, params=self.params)

    def next(self):
        # ★ minibt 优化时 `self.ma` 可能还是上一轮的指标对象；
        #   从指标数据集取当前 trial 最新注册的 `ma`，确保 next 用的是
        #   当前 fast/slow 的结果（否则所有 trial 目标值相同 ✗）
        ma = self._btindicatordataset.get('ma')
        if ma is None:
            ma = self.ma
        position = float(getattr(self.data.position, 'pos',
                                 self.data.position) or 0.0)
        if ma.long_signal.new and position <= 0:
            self.data.set_target_size(self.params.size)
        elif ma.short_signal.new and position > 0:
            self.data.set_target_size(0)


if __name__ == '__main__':
    # ★ desk：本地图表「加到图表」+ 打开「参数优化」页
    bt = Bt(auto=False)                 # auto=False：只跑本文件的策略
    bt.addstrategy(LocalOptimizeStrategy)
    bt.run(gui=Gui.Desk, desk_mode='optimize')
