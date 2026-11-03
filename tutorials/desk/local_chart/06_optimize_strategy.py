"""06 · Strategy 参数优化（单合约）

和 `02_strategy_single.py` 相同的双均线逻辑，但多了 `op_config`：

```python
op_config = OpConfig(
    target='sharpe',
    weights=1.,
    opconfig=OptunaConfig(n_trials=30, sampler='TPESampler'),
    op_method='optuna',
    params=dict(fast=(5, 20, 1), slow=(20, 60, 2)),
)
```

在 desk 编辑器打开本文件 → 「参数优化」：
* 后台运行 Optuna；
* 完成后可看参数排名 / 试验记录；
* 选中解可回测，也可「写回最优参数」。

⚠ 本文件专门用于参数优化；做图表回放 / 普通回测请用
`02_strategy_single.py`，避免优化配置干扰“加到图表”的普通运行。

直接运行：`python tutorials/desk/local_chart/06_optimize_strategy.py`
"""
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from minibt import *


class MaCrossOptimize(Strategy):
    """双均线策略 + OpConfig（只优化 fast / slow）。"""

    config = Config(
        value=1_000_000.0,
        margin_rate=0.05,
        fixed_commission=1.0,
    )

    params = dict(fast=10, slow=30, size=1)

    op_config = OpConfig(
        target='sharpe',
        weights=1.0,
        opconfig=OptunaConfig(n_trials=30, sampler='TPESampler'),
        op_method='optuna',
        params=dict(
            fast=(5, 20, 1),
            slow=(20, 60, 2),
        ),
    )

    def __init__(self):
        self.min_start_length = 30
        self.data = self.get_kline(LocalDatas.l2609_60)
        self.fast = self.data.close.sma(self.params.fast, overlap=True)
        self.slow = self.data.close.sma(self.params.slow, overlap=True)
        self.data.fixed_commission = 1.0

    @staticmethod
    def _net(kline):
        position = kline.position
        return float(getattr(position, 'pos', position) or 0.0)

    def next(self):
        fast = self.fast.new
        slow = self.slow.new
        if fast != fast or slow != slow:
            return

        position = self._net(self.data)
        if fast > slow and position <= 0:
            self.data.set_target_size(self.params.size)
        elif fast < slow and position > 0:
            self.data.set_target_size(0)


if __name__ == '__main__':
    # 直接运行会按 op_config 跑优化（30 trials，可能较慢）；
    # 只想看一次回测请用 02_strategy_single.py
    Bt().run()
