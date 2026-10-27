"""十字线提示：追踪提示（tracking）+ 放大镜提示（magnifier）。

对应官方教程 https://tradingview.github.io/lightweight-charts/tutorials/how_to/tooltips
的两种实现（第三种 floating 把框钉在数据点上，十字线经过高低点时跳动很大，
官方例子之间差异也小，这里没有实现）。

覆盖的 API：
- `series.tooltip(mode='tracking'|'magnifier', **options)`，以及
  `series.tracking_tooltip(...)` / `series.magnifier_tooltip(...)`；
  `chart.` 前缀版本作用于主 K 线序列。
- 选项：`title` / `fields`（`'auto'` = 该点的全部数值字段，如 OHLC）/
  `field_labels` / `color_by_candle` / `decimals` / `time_format` / `width` /
  `height` / `margin` / `padding` / `font_size` / `big_font_size` /
  `background` / `background_opacity` / `text_color` / `border_color` /
  `border_width` / `border_radius` / `shadow` / `show_title` / `show_value` /
  `show_time` / `flip` / `z_index`。
- 运行期：`apply_options` / `set_title` / `set_fields` / `set_mode` /
  `show` / `hide` / `visible` / `options` / `remove`。
- 提示的颜色默认取根 CSS 变量，所以跟随 `chart.win.theme(...)`；顶栏
  switcher 用来在 tracking / magnifier / 关闭 之间切换。
- 配合十字线样式：隐藏水平线与标签（教程里的做法）。

运行：
    python examples/11_api_tour/16_tooltips.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_16.png')


def make_data(rows: int = 220, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = 100 + np.cumsum(rng.normal(0.1, 1.2, rows))
    open_ = close + rng.normal(0, 0.5, rows)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.6, rows))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.6, rows))
    volume = np.abs(rng.normal(900, 240, rows)).round()
    return pd.DataFrame({'time': index, 'open': open_.round(2),
                         'high': high.round(2), 'low': low.round(2),
                         'close': close.round(2), 'volume': volume})


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()
    chart.set(df)
    chart.legend(visible=True, font_size=12)
    # 指标线：它的提示标题会默认取指标名（SMA 20）
    sma = chart.add_sma(length=20, line_width=2, color='#2962FF')

    # 教程里的十字线做法：藏掉水平线与两端的标签，只留竖线
    chart.crosshair(vert_width=1, vert_color='#758696')
    chart.apply_options(crosshair={
        'horz_line': {'visible': False, 'label_visible': False},
        'vert_line': {'label_visible': False},
    })

    # tracking：跟随光标的不透明框，显示 OHLC；靠右/下边缘会自动翻到另一侧
    tracking = chart.tracking_tooltip(
        title='ABC Inc.', fields='auto', width=120,
        field_labels=('O', 'H', 'L', 'C'), color_by_candle=True,
    )
    # magnifier：贴着窗格顶部的半透明竖条，只沿时间轴滑动
    magnifier = sma.magnifier_tooltip(width=96, decimals=2)

    tips = {'tracking': tracking, 'magnifier': magnifier}

    def on_tooltip(owner):
        mode = owner.topbar['tooltip'].value
        for name, tip in tips.items():
            tip.show() if name == mode else tip.hide()

    chart.topbar.switcher('tooltip', ('tracking', 'magnifier', 'off'),
                          default='tracking', func=on_tooltip)

    chart.fit()


def report(chart: Chart) -> None:
    """打印提示状态（读回，仅在窗口就绪后调用）。"""
    tip = chart.tracking_tooltip(title='readback')
    print('[tooltip]', tip, '| mode:', tip.mode, '| visible:', tip.visible())
    print('[options]', sorted(tip.options())[:8], '...')
    tip.set_mode('magnifier').set_title('changed')
    print('[changed]', tip.mode, tip.options()['title'])
    tip.remove()
    print('[removed] ok')


def capture(chart: Chart) -> None:
    """截图写盘（需要窗口已加载）。"""
    png = chart.screenshot()
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    chart = Chart(width=1200, height=820, title='pylightcharts - 十字线提示')
    build(chart)
    chart.show(block=False)
    report(chart)
    capture(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
