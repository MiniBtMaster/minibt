"""指标标签开关：`legend=False` —— 只画线、不显示左上角的图例行。

覆盖的 API：
- `chart.create_line(..., legend=False)` —— 序列以**空名字**创建，
  于是 **不生成图例行**，但**数据仍按原名字映射**（不会踩
  「空名字 + 列名对不上 → 图表卡死」的坑 ✓）；
- `chart.create_histogram(..., legend=False)` / `add_series('Line', ...,
  legend=False)` / `pane_add_series(index, 'Line', ..., legend=False)` —— 同一开关；
- `legend_toggle=False` 则是**另一种**语义：图例行还在，只是少了那只眼睛图标。

minibt 侧（**指标级**开关，本示例不依赖 minibt，写成注释备查）：

```python
from minibt import BtIndicator, np

class PositionLine(BtIndicator):
    \"\"\"载体线：不画图例标签；数值全 NaN 时自己也不画线。\"\"\"
    isplot = False          # 不画这条线（只在需要载体时用）
    legend = False          # ★ 不显示图例标签（本示例实现的属性）
    lines = ('pl',)

    def next(self):
        self.lines.pl = np.array([14550.] * self.length)
```

minibt 的 `PlotInfo.legend`（默认 `True`）与指标类属性 `legend = False`
都会被透传到 `pylightcharts` 的 `create_line(legend=...)`，
所以**任何内置/脚本指标**都能一行关掉自己的标签 ✓。

运行：
    python examples/11_api_tour/19_indicator_legend.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_19.png')


def make_data(rows: int = 220, seed: int = 19) -> pd.DataFrame:
    """合成 OHLCV —— 自包含，不依赖网络。"""
    rng = np.random.default_rng(seed)
    index = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = 100 + np.cumsum(rng.normal(0.1, 1.2, rows))
    open_ = close + rng.normal(0, 0.6, rows)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.8, rows))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.8, rows))
    volume = rng.integers(1_000, 9_000, rows).astype(float)
    return pd.DataFrame({'time': index, 'open': open_, 'high': high,
                         'low': low, 'close': close, 'volume': volume})


def build(chart: Chart) -> None:
    """全部 API 调用都在这里（不打开窗口）。"""
    df = make_data()
    chart.set(df)
    chart.legend(visible=True)                      # 主图图例打开，方便对照
    times = df['time']
    close = df['close']

    # ---- 1) 有标签的线（默认 legend=True）—— 左上角会出现一行 ✓ ----
    labeled = chart.create_line('有标签的均线', color='#2962ff', width=2)
    labeled.set(pd.DataFrame({'time': times,
                              '有标签的均线': close.rolling(10).mean()}))

    # ---- 2) 无标签的线：legend=False —— 线上图、但左上角**没有**这一行 ✓ ----
    silent = chart.create_line('不显示标签的均线', color='#ff9800', width=2,
                               legend=False)
    silent.set(pd.DataFrame({'time': times,
                             '不显示标签的均线': close.rolling(20).mean()}))

    # ---- 3) 同一开关对柱状图同样有效 ✓ ----
    silent_hist = chart.create_histogram('不显示标签的柱', color='#26a69a',
                                         price_line=False, price_label=False,
                                         legend=False)
    silent_hist.set(pd.DataFrame({'time': times,
                                  '不显示标签的柱': close.diff()}))

    # ---- 4) 副图里也一样：pane_add_series(..., legend=False) ✓ ----
    sub = chart.add_pane()                    # 返回**新面板的索引** ✓
    pane_line = chart.pane_add_series(sub, 'Line', '副图（显示标签）',
                                      color='#ab47bc', line_width=2)
    pane_line.set(pd.DataFrame({'time': times,
                                '副图（显示标签）': close.rolling(30).mean()}))
    pane_silent = chart.pane_add_series(sub, 'Line', '副图（不显示标签）',
                                        color='#ef5350', line_width=2,
                                        legend=False)
    pane_silent.set(pd.DataFrame({'time': times,
                                  '副图（不显示标签）': close.rolling(60).mean()}))
    assert sub > 0, f'新面板索引应该是 >0，实际 {sub}'

    # ---- 5) 对照：legend_toggle=False 是「行还在，只是没有眼睛图标」 ----
    # 注意：这个开关和 `legend` **不是**一回事 ✗ —— `legend_toggle=False`
    # 只去掉图例行上的眼睛图标（行还在 ✓）；`legend=False` 才是整行不建 ✓。
    chart.create_line('行在但没有眼睛', color='#8d6e63', width=1,
                      price_line=False, price_label=False,
                      legend_toggle=False).set(
        pd.DataFrame({'time': times,
                      '行在但没有眼睛': close.rolling(5).mean()}))


def report(chart) -> None:
    """读回类 API（需真实窗口）。"""
    lines = chart.lines()
    print(f'序列数 = {len(lines)}')
    for line in lines:
        print(f'  - name={line.name!r} series_type={line.series_type()}')
    print('左上角应该只有这几行：有标签的均线 / 副图（显示标签）/ '
          '行在但没有眼睛（没有眼睛图标 ✓）；'
          'legend=False 的那 3 条**完全没有图例行** ✓')
    print(f'截图可存到：{SCREENSHOT_PATH}')


def main() -> None:
    chart = Chart()
    build(chart)
    chart.show(block=False)
    report(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
