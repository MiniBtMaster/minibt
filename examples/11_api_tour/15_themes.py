"""主题：整站浅色 / 深色切换（`chart.win.theme`）。

覆盖的 API：
- `Window.theme(name='light'|'dark', **overrides)`：一次性套用整套配色 ——
  根 CSS 变量（顶栏 / 图例 / 菜单 / 悬停态）+ 每张图的背景 / 网格 / 十字线 /
  K 线 / 成交量 / 价格轴 / 分隔条；之后创建的图（子图）会自动继承。
- `AbstractChart.theme(...)`：单图写法，内部就是 `chart.win.theme(...)`，
  因为根 CSS 变量是窗口级的，所以它作用于整个界面。
- `pylightcharts.themes`：`LIGHT` / `DARK` 调色板与 `resolve(name)`；
  也可以用 `theme('light', up='#0a7d5a')` 覆盖单个颜色，或直接传 dict。
- `Table` 的底色 / 边框 / 文字 / 页眉页脚底色也会跟随主题：新建的表格用主题
  配色，已存在的表格由 `Window.theme` 调用 `Table.set_colors(...)` 重新上色；
  创建时显式传了 `background_color=` / `border_color=` 的表格不跟随。
- 图例（左上角标签）的文字颜色是内联样式，CSS 变量管不到，所以主题里会一并
  重设（`legend(...)` 的其它设置保持不变）。

主题只是"一次性把一批 setter 调一遍"，之后任何单独的 setter 都会覆盖它，
所以可以 `theme('dark')` 之后再用 `layout(...)` / `candle_style(...)` 微调。

运行：
    python examples/11_api_tour/15_themes.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_15.png')


def make_data(rows: int = 220, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = 100 + np.cumsum(rng.normal(0.15, 1.4, rows))
    open_ = close + rng.normal(0, 0.6, rows)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.7, rows))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.7, rows))
    volume = np.abs(rng.normal(900, 260, rows)).round()
    return pd.DataFrame({'time': index, 'open': open_.round(2),
                         'high': high.round(2), 'low': low.round(2),
                         'close': close.round(2), 'volume': volume})


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()
    chart.set(df)
    chart.legend(visible=True, font_size=12, text='THEME')
    chart.add_zigzag(name='zigzag')

    # theme：整套深色（默认配色，写出来更直观）
    chart.win.theme('dark')

    # 顶栏切换整站主题；回调拿到的是这张图，改的是它所属的窗口
    def on_theme(owner):
        # 单图写法：等价于 owner.win.theme(...)
        owner.theme(owner.topbar['theme'].value)

    chart.topbar.switcher('theme', ('dark', 'light'),
                          default='dark', func=on_theme)

    # 表格：不传底色 / 边框时跟随主题
    table = chart.create_table(width=250, height=90,
                               headings=('symbol', 'last'), draggable=True)
    table.new_row('BTCUSDT', 100.0)
    # table.set_colors(background_color='#ffffff', border_color='#e0e3eb',
    #                  text_color='#131722', section_color='#f0f3fa')

    # 子图（独立坐标 + 十字线联动）：主题同样覆盖它，且后建的图自动继承
    sub = chart.create_subchart(position='right', width=0.5, height=0.5)
    sub.set(df[['time', 'close']].rename(columns={'close': 'value'}))
    sub.legend(visible=True, text='SUB')
    chart.sync(sub, crosshairs_only=True)

    chart.fit()


def report(chart: Chart) -> None:
    """打印主题相关状态（读回，仅在窗口就绪后调用）。"""
    from pylightcharts.themes import resolve
    print('[themes]', sorted(resolve('light')) == sorted(resolve('dark')),
          '| colours:', len(resolve('light')))
    print('[current]', chart.win._theme['background'],
          '| topbar:', chart.topbar['theme'].value)
    print('[charts]', len(chart.win._themed_charts()))
    print('[price]', chart.format_price(1234.5))


def capture(chart: Chart) -> None:
    """截图写盘（需要窗口已加载）。"""
    png = chart.screenshot()
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    chart = Chart(width=1200, height=820, title='pylightcharts - 主题')
    build(chart)
    chart.show(block=False)
    report(chart)
    capture(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
