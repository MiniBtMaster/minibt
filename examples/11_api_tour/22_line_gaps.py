"""折线断点（空白点 / whitespace）：数据里的 `nan` 不应被连线连过去。

LWC 的规矩：**同一根时间轴上**，如果某个数据点只有 `time` 没有值，引擎就把它当
"空白点" —— 折线在这里断开，不会跨越缺口连过去。所以要让
`[1, 2, 3, nan, nan, 6, 7, 8]` 显示成**两段**，必须把 nan 那两根仍然下发成
``{"time": ...}``（而不是整个丢掉，否则引擎会把 3 和 6 直接连起来）。

本示例用最小数据复现这个场景：

```
时间   →   1   2   3   4    5    6   7   8
数值   →   1   2   3   nan  nan  6   7   8
期望   →   ─────────(断开)───────
实际   应显示两段折线（3 之前一段、6 之后一段）
```

覆盖的 API：
- `chart.create_line(...)` / `add_series('Line', ...)` + `series.set(...)`；
- 数据里的 `nan` → **空白点**（`{'time': ...}`），`encode_series_data()` 会因此
  走 JSON 路径（NaN 不能进 base64 浮点块，否则引擎会连过去）；
- `series.data` 读回：能数出空白点个数，方便断言"真的是两段"。

运行：
    python examples/11_api_tour/22_line_gaps.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart

UP, DOWN = '#26A69A', '#EF5350'
#: 目标形状：1 2 3 _ _ 6 7 8 —— 中间两个空白点，折线应断成两段
VALUES = [1.0, 2.0, 3.0, np.nan, np.nan, 6.0, 7.0, 8.0]
#: 截图写在脚本旁边，和 18~21 保持一致（从任何工作目录运行都对）
HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_22.png')


def make_frame(values=VALUES) -> pd.DataFrame:
    """最小行情：每根 K 线一个时间点 + 一个可能为 nan 的值。"""
    return pd.DataFrame({
        'time': pd.bdate_range('2024-01-01', periods=len(values)),
        'close': [float(v) for v in values],
    })


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    frame = make_frame()
    chart.set(frame)                      # K 线主图（nan 会自然断开/空白）
    chart.legend(visible=True, font_size=12, text='折线在 nan 处断开 = 两段')

    line = chart.add_series('Line', name='close')   # 单值序列：列名与序列同名
    line.set(frame[['time', 'close']], format_cols=False)
    line.style(color='#2962FF', line_width=2)

    # 参考：把 nan 换成 0 会变成一条不断开的线（放在副图便于对照）
    filled = make_frame([0.0 if (v != v) else float(v) for v in VALUES])
    zeros = chart.add_series('Line', name='nan→0', pane_index='new',
                             color='#FFB300', line_width=1)
    zeros.set(filled[['time', 'close']].rename(columns={'close': 'nan→0'}),
              format_cols=False)
    chart.fit()


def report(chart: Chart) -> None:
    """读回：数一数空白点（只有时间、没有值）的个数。

    注意 `series.data` 是 **DataFrame**：`for row in df` 迭代出来的是**列名**，
    要按列取值（这里用 pandas 自己判断 NaN）。
    """
    line = next(series for series in chart._lines if series.name == 'close')
    data = line.data
    values = data['value'] if 'value' in data else data.iloc[:, -1]
    blanks = int(pd.isna(values).sum())
    print(f'[gaps] 数据点 {len(data)} 个，其中空白点 {blanks} 个 '
          f'（期望 2 -> 折线断成两段）')
    print('[gaps] NaN 行仍会下发成 {"time": ...}（空白点），真正的断开由'
          ' pylightcharts 拆段完成')


def capture(chart: Chart) -> None:
    """截图写盘（需要窗口已加载）。"""
    png = chart.screenshot()
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    chart = Chart(width=1200, height=820, title='pylightcharts - 折线断点')
    build(chart)
    chart.show(block=False)
    report(chart)
    capture(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
