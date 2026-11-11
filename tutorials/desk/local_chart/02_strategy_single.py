"""02 · 单合约策略（本地图表 / 回放 / 回测）

一个最小的单合约双均线策略：

* 数据：`LocalDatas.l2609_60`（加到本地图表时，系统会先选单图布局，
  再加载这个本地 CSV，最后添加策略）
* 交易：金叉做多 1 手，死叉平仓；只做多，先保持逻辑简单
* 账户：在 `config` 里设置 minibt 内置账户参数；每合约手续费可再覆盖

在 desk 里：
1. 打开本地图表，编辑器打开本文件；
2. 点「加到图表」→ 自动加载 l2609_60 并画出均线；
3. 点 ▶▶ 进入回放，再点播放 / 单步：
   - 策略 `next()` 逐根推进；
   - 本地模拟账户按策略的 `set_target_size()` 自动成交；
   - 持仓线、权益、交易记录都会更新。

直接运行：`python tutorials/desk/local_chart/02_strategy_single.py`
"""
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from minibt import *


class MaCrossSingle(Strategy):
    """单合约双均线：金叉多 1 手，死叉平仓。"""

    #: minibt 内置账户：初始资金 / 保证金率 / 手续费 / 滑点
    #: desk 本地模拟账户在回放开始时按这份配置重置 ✓
    config = Config(
        value=1_000_000.0,
        margin_rate=0.05,
        fixed_commission=1.0,
    )

    params = dict(fast=10, slow=30, size=1)

    def __init__(self):
        self.min_start_length = 30
        self.data = self.get_kline(LocalDatas.l2609_60)
        self.fast = self.data.close.sma(self.params.fast, overlap=True)
        self.slow = self.data.close.sma(self.params.slow, overlap=True)
        #: 这一条合约单独指定 1 元/手（优先级高于 config.fixed_commission）
        self.data.fixed_commission = 1.0

    @staticmethod
    def _net(kline):
        """回测 / 本地模拟 / 天勤持仓都取净仓。"""
        position = kline.position
        return float(getattr(position, 'pos', position) or 0.0)

    def next(self):
        fast = self.fast.new
        slow = self.slow.new
        if fast != fast or slow != slow:       # NaN：均线预热期
            return

        position = self._net(self.data)
        if fast > slow and position <= 0:
            self.data.set_target_size(self.params.size)
        elif fast < slow and position > 0:
            self.data.set_target_size(0)


if __name__ == '__main__':
    Bt().run()
