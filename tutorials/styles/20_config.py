"""7.20 · Config —— 全局图表/回测配置（34 个字段）

演示要点
--------
``Config`` 是**策略级**的开关集合：图表长什么样、回测算哪些成本、日志怎么打、
结果页显示什么。写在策略类上：

```python
class MyStrategy(Strategy):
    config = Config(theme='light', grid=True, volume_mode='sub', ...)
```

本例挑几个**肉眼可见**的字段对比默认值：

| 字段 | 本例 | 默认 | 效果 |
| --- | --- | --- | --- |
| ``grid`` | ``True`` | ``True`` | 网格线 |
| ``y_margin`` | ``0.02`` | ``0.1`` | 价格轴上下留白（越小越"满"） |
| ``tradestyle`` | ``show=False`` | 画成交 | 本例只看图，不画成交标记 |
| ``print_account`` | ``False`` | ``True`` | 不往控制台打账户表 |
| ``theme`` | ``'light'`` | ``'light'`` | 配色 |

其余字段（财务 / 日志 / 回放 / 性能 / 成交量模式）见文档里的完整表；
⚠️ ``volume_mode`` 只对 **bokeh** 生效（pylightcharts 固定叠在主图）。

运行：``python tutorials/styles/20_config.py``
文档：``minibt_docs/docs/minibt_styles/7.20_config.md``
"""

import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class EmaCross(BtIndicator):
    """20/60 均线交叉。"""

    lines = ('ema_fast', 'ema_slow', 'long_signal', 'short_signal')
    params = dict(FAST=20, SLOW=60)
    overlap = dict(ema_fast=True, ema_slow=True)
    isplot = dict(long_signal=False, short_signal=False)
    linestyle = dict(
        ema_fast=LineStyle(line_color=Colors.orange, line_width=1.5),
        ema_slow=LineStyle(line_color=Colors.blue, line_width=1.5),
    )
    # 本例只想看"图"本身：把信号图标关掉（否则满屏三角）
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle, show=False),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle, show=False),
    )

    def next(self):
        p = self.params
        fast = self.close.ema(p.FAST)
        slow = self.close.ema(p.SLOW)
        return fast, slow, fast.cross_up(slow), fast.cross_down(slow)


class ConfigDemo(Strategy):
    """★ 本例的重点：这一行 Config。"""

    config = Config(
        theme='light',
        grid=True,
        y_margin=0.02,                       # 价格轴留白（默认 0.1）
        tradestyle=TradeStyle(show=False),   # 本例不画成交标记
        print_account=False,                 # 不打印账户表
        capital_line=True,                   # 权益页：初始资金虚线
    )

    def __init__(self):
        self.data = self.get_kline(LocalDatas.test, height=500)
        self.ind = EmaCross(self.data)

    def next(self):
        if self.ind.long_signal.new:
            self.data.buy(reverse=True)
        elif self.ind.short_signal.new:
            self.data.sell(reverse=True)


def main(gui=None):
    print('Config 字段数 =', len(dataclasses.fields(Config)))
    print('  y_margin    =', ConfigDemo.config.y_margin)
    print('  capital_line=', ConfigDemo.config.capital_line)
    print('  volume_mode =', ConfigDemo.config.volume_mode,
          '（只对 bokeh 生效）')
    Bt().run(gui=gui or Gui.Pylightcharts)


if __name__ == '__main__':
    main()
