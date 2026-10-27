"""双标的 / 双价格刻度（官方 Two Price Scales 教程）+ 蜡烛叠加。

对应官方教程 https://tradingview.github.io/lightweight-charts/tutorials/how_to/two-price-scales
教程里是「K 线在右、另一个标的在左」，这里保持一致（右侧留给 K 线的习惯），
并且额外支持把第二个标的也画成**蜡烛图**叠加上去。

覆盖的 API：
- `chart.add_symbol(name, data, kind=..., scale='left', margins=(top, bottom),
  up_color=..., down_color=..., color=..., line_width=..., price_line=...,
  price_label=..., legend_toggle=...)`；
- `chart.scale_margins(right=(top, bottom), left=(top, bottom))`：两个刻度在
  窗格里的上下占比（叠加 or 上下分割）；
- `kind='line'`（教程的线叠加）与 `kind='candles'`（蜡烛叠加）；
- 每条价格刻度上的「最后一价标签」用 `series.price_line(title=...)` 标注标的
  名称，两张刻度不会认错；
- 顶栏 switcher：`view` 在「叠加 / 分割」之间切换，`symbol` 在「线 / 蜡烛」之间
  切换（用 `series.hide_data()` / `show_data()`）；
- 十字线 `mode='normal'`（教程提示：默认会吸附到第一个序列的数据点）。

运行：
    python examples/11_api_tour/17_two_symbols.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_17.png')


def make_data(rows: int = 220, start: float = 60000.0, seed: int = 3,
              drift: float = 0.0004, vol: float = 0.02) -> pd.DataFrame:
    """A random walk with OHLC columns (a different price level per symbol)."""
    rng = np.random.default_rng(seed)
    index = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = start * np.exp(np.cumsum(rng.normal(drift, vol, rows)))
    open_ = close * (1 + rng.normal(0, vol / 3, rows))
    high = np.maximum(open_, close) * (
        1 + np.abs(rng.normal(0, vol / 4, rows)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, vol / 4, rows)))
    return pd.DataFrame({'time': index, 'open': open_.round(2),
                         'high': high.round(2), 'low': low.round(2),
                         'close': close.round(2)})


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    btc = make_data(start=60000.0, seed=3)
    eth = make_data(start=3000.0, seed=11, vol=0.03)

    # 主标的：K 线 + 成交量，用右侧刻度（默认）
    chart.set(btc)
    chart.legend(visible=True, font_size=12, text='BTCUSDT')
    # 教程提示：默认十字线会吸附第一个序列的数据点，normal 更自由
    chart.crosshair(mode='normal')

    # 第二个标的：线，走左侧刻度（官方教程的写法）
    eth_line = chart.add_symbol(
        'ETHUSDT', eth[['time', 'close']], kind='line',
        color='#2962FF', line_width=2,
    )
    # 第二个标的：蜡烛叠加（本文件的第 2 个需求），同样在左侧刻度
    eth_candles = chart.add_symbol(
        'ETHUSDT K', eth, kind='candles', scale='left',
        up_color='#26A69A', down_color='#EF5350',
    )
    eth_candles.hide_data()

    symbols = {'line': eth_line, 'candles': eth_candles}
    views = {'overlay': (0.2, 0.2, 0.2, 0.2),        # 两条刻度重叠（教程效果）
             'split': (0.0, 0.55, 0.55, 0.0)}        # 右刻度在上、左刻度在下

    def on_symbol(owner):
        name = owner.topbar['symbol'].value
        for key, series in symbols.items():
            series.show_data() if key == name else series.hide_data()

    def on_view(owner):
        right_top, right_bottom, left_top, left_bottom = views[
            owner.topbar['view'].value]
        chart.scale_margins(right=(right_top, right_bottom),
                            left=(left_top, left_bottom))

    chart.topbar.switcher('symbol', ('line', 'candles'), default='line',
                          func=on_symbol)
    chart.topbar.switcher('view', ('overlay', 'split'), default='overlay',
                          func=on_view)
    on_view(chart)
    chart.fit()


def report(chart: Chart) -> None:
    """打印双刻度状态（读回，仅在窗口就绪后调用）。"""
    left = chart.get_price_scale('left')
    right = chart.get_price_scale('right')
    print('[scales] left width:', left.width(),
          '| right width:', right.width())
    print('[ranges] left:', left.get_visible_range())
    print('[ranges] right:', right.get_visible_range())
    print('[layout]', chart.topbar['view'].value,
          '| symbol:', chart.topbar['symbol'].value)


def capture(chart: Chart) -> None:
    """截图写盘（需要窗口已加载）。"""
    png = chart.screenshot()
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    chart = Chart(width=1200, height=820, title='pylightcharts - 双标的双刻度')
    build(chart)
    chart.show(block=False)
    report(chart)
    capture(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
