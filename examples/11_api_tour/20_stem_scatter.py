"""垂直虚线散点图（棒棒糖 / lollipop）：`shapes.stem`。

LWC 本身**没有"竖直虚线"图元**，但同一根 K 线上的两点 `polyline` 就是它 ——
`shapes.stem` 把这件事包成一个现成的预设，常用于：

* 每笔交易的盈亏（从 0 轴拉一根棒子，涨绿跌红）；
* 每根 K 线相对均线/中轴的**偏离**；
* 价位上的成交量分布（volume-at-price）。

本示例用"每根 K 线相对 SMA 的偏离"演示，主图看 K 线 + 均线，
副图看偏离棒棒糖 —— 典型的技术指标面板。

覆盖的 API：
- `shapes.stem(price, baseline=0.0, color=None, width=1, style='dashed',
  cap=False, cap_radius=3)`：从 `baseline` 到 `price` 的竖直棒；`style` 默认
  虚线，`cap=True` 在端点补一个小圆点（数值贴近基线时也看得见）；
- 挂在**自定义序列**上：`chart.pane_add_custom_series(pane, name, ...)` +
  `series.set(df, shapes=lambda row: ...)`；
  - 数据项**必须含 `value` 字段**（渲染器用它驱动自动缩放，也用它判断"是不是
    空白点"）—— 列名不能像内置序列那样随序列名走；
  - 逐点颜色：把颜色放进数据列，在 shapes 回调里 `row['color']` 取用；
- 基准线用 `chart.horizontal_span(0.0, filled=False, pane_index=pane)`
  （自定义序列挂不上价格线图元）；
- 一个 `stem` 可以返回多个图元（棒 + 端点圆），所以"散点 + 竖线"是一体的。

运行：
    python examples/11_api_tour/20_stem_scatter.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart, shapes

UP, DOWN = '#26A69A', '#EF5350'
ROWS = 120
#: 截图写在脚本旁边，和 18/19 保持一致（从任何工作目录运行都对）
HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_20.png')


def make_source(rows: int = ROWS) -> pd.DataFrame:
    """自包含合成行情：价格 + 一根用来做偏离基准的均线。"""
    rng = np.random.default_rng(20)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.8)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + rng.uniform(0.1, 0.8, rows)
    low = np.minimum(open_, close) - rng.uniform(0.1, 0.8, rows)
    frame = pd.DataFrame({
        'time': pd.bdate_range('2024-01-01', periods=rows),
        'open': open_.round(2),
        'high': high.round(2),
        'low': low.round(2),
        'close': close.round(2),
        'volume': np.abs(rng.normal(900, 220, rows)).round(),
    })
    frame['sma'] = frame['close'].rolling(20, min_periods=1).mean().round(2)
    frame['deviation'] = (frame['close'] - frame['sma']).round(2)
    return frame


def _stem_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """自定义序列的数据：`value` 必须有，颜色按正负分。"""
    return pd.DataFrame({
        'time': frame['time'],
        'value': frame['deviation'].to_numpy(),
        'color': [UP if value >= 0 else DOWN for value in frame['deviation']],
    })


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    source = make_source()
    chart.set(source)
    chart.legend(visible=True, font_size=12, text='偏离 = close - SMA20')

    # 主图：K 线 + 作为偏离基准的均线
    sma = chart.add_series('Line', name='SMA 20', line_width=2, color='#2962FF')
    sma.set(pd.DataFrame({'time': source['time'], 'SMA 20': source['sma']}))

    # 副图：一根棒棒糖 = 一条从 0 到偏离值的竖直虚线 + 端点小圆点
    pane = chart.add_pane()
    stems = chart.pane_add_custom_series(pane, '偏离', legend=True)
    stems.set(_stem_frame(source), shapes=lambda row: shapes.stem(
        row['value'], baseline=0.0, color=row['color'], width=1,
        style='dashed', cap=True, cap_radius=3))

    # 自定义序列挂不上价格线图元，基准线用全宽水平线
    chart.horizontal_span(0.0, filled=False, pane_index=pane,
                          line_color='#787B86', line_width=1,
                          line_style='dashed')
    chart.set_pane_stretch(0, 3)          # 主图 : 副图 = 3 : 1
    chart.set_pane_stretch(pane, 1)
    chart.fit()


def report(chart: Chart) -> None:
    """读回：棒棒糖所在面板、数据点数与取值范围（仅在窗口就绪后调用）。"""
    series = chart._lines[-1]
    values = series.data['value'].to_numpy()
    print(f'[stem] pane={series._pane_index} bars={values.size} '
          f'min={values.min():.2f} max={values.max():.2f}')
    print('[stem] 每条棒棒糖 = polyline([(0, 0), (0, value)], style="dashed")'
          ' + 端点 circle')


def capture(chart: Chart) -> None:
    """截图写盘（需要窗口已加载）。"""
    png = chart.screenshot()
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    chart = Chart(width=1200, height=820, title='pylightcharts - 垂直虚线散点图')
    build(chart)
    chart.show(block=False)
    report(chart)
    capture(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
