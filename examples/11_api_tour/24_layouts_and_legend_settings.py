"""多布局（2D tiles + 可拖分割条）与指标线设置（图例齿轮）—— 迁移过程中加的扩展。

覆盖的 API（都是 `pylightcharts` 在把 miniqt 看盘迁到新引擎时**新增的扩展**，
上游 Lightweight Charts 本身没有）：

- `chart.win.layout.arrange_tiles(tiles, dividers=True)`：**2D 分块布局**
  （`[(1.0, 0.5), (0.5, 0.5), (0.5, 0.5)]` = 上 1 满宽 + 下 2 并排），
  `tiles` 是按顺序的 `(宽, 高)` 分数。**一列/一行**时格子之间会自动放
  **可拖动的分隔条**（拖动改两个格子/两行的比例）；2D（多行多列）也会在行与行、
  行内列与列之间放分隔条。切回普通浮动布局（`arrange()` / `single()`）时会自动
  调 `Lib.clearLayoutTiles` 把绝对定位复位 ✓。
- `series.enable_legend_settings(callback)`：给该序列的图例行加一个**齿轮**；
  点击回调 `callback(series, x, y)`（x/y 是点击处在 webview 里的坐标，方便把设置
  卡片弹在齿轮旁）。这就是"鼠标移到指标标签 → 指标设置"的入口 ✓。
- `series.pin_legend_row(True)`：图例行**常显**（默认只有十字线悬停时才显示），
  名字 + 眼睛 + 齿轮一直看得到 ✓。
- `series.set_line_width` / `set_line_color` / `set_line_style` /
  `set_price_visible` / `is_visible`：运行时改指标线的线宽/颜色/线型、
  价格线/价格标签，以及读可见性（指标设置卡片靠这几个方法 ✓）。
- `chart.remove()`：销毁图表时**连同它的 DOM wrapper 一起摘掉**（以前只销毁引擎，
  wrapper 留在页面里占位，后面新建的图会被盖住 ✗）。

运行：
    python examples/11_api_tour/24_layouts_and_legend_settings.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_24.png')

#: 齿轮点一次就轮换一套：颜色 / 线宽 / 线型
STYLES = (
    ('#FF9800', 4, 'solid'),
    ('#E91E63', 2, 'dashed'),
    ('#00BCD4', 3, 'dotted'),
    ('#8BC34A', 1, 'large_dashed'),
)
STYLE_STATE = {'index': -1}


def make_data(rows: int = 260, seed: int = 24) -> pd.DataFrame:
    """自包含合成 OHLCV。"""
    rng = np.random.default_rng(seed)
    index = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = 100 + np.cumsum(rng.normal(0.05, 1.1, rows))
    open_ = close + rng.normal(0, 0.4, rows)
    return pd.DataFrame({
        'time': index, 'open': open_.round(2),
        'high': (np.maximum(open_, close) + 0.6).round(2),
        'low': (np.minimum(open_, close) - 0.6).round(2),
        'close': close.round(2),
        'volume': np.abs(rng.normal(900, 200, rows)).round(),
    })


def on_legend_settings(series, x=None, y=None):
    """图例齿轮回调：演示用 `set_line_*` / `set_price_visible` 改指标线。"""
    print(f'[legend] 齿轮: {series.name} @ ({x}, {y})')
    STYLE_STATE['index'] = (STYLE_STATE['index'] + 1) % len(STYLES)
    color, width, style = STYLES[STYLE_STATE['index']]
    series.set_line_color(color)
    series.set_line_width(width)
    series.set_line_style(style)
    # 价格标签（Y 轴上最后一价）奇偶切换，演示 set_price_visible
    series.set_price_visible('price_label', STYLE_STATE['index'] % 2 == 0)
    print(f'[legend] {series.name}: color={color} width={width} style={style} '
          f'| visible={series.is_visible()}')


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    data = make_data()
    chart.set(data)
    chart.legend(visible=True, ohlc=False, percent=False, lines=True,
                 text='TILES')

    frame = chart.candle_data
    # ---- 指标线 + 图例齿轮 + 常显图例行 ------------------------------
    ma = chart.create_line('MA20', color='#FF9800', width=2,
                           price_line=False)
    ma.set(pd.DataFrame({'time': frame['time'],
                         'MA20': frame['close'].rolling(20).mean()}))
    ma.pin_legend_row(True)                 # 名字 + 眼睛 + 齿轮常显
    ma.enable_legend_settings(on_legend_settings)

    ema = chart.create_line('EMA12', color='#2196F3', width=2,
                            price_line=False)
    ema.set(pd.DataFrame({'time': frame['time'],
                          'EMA12': frame['close'].ewm(span=12).mean()}))
    ema.pin_legend_row(True)
    ema.enable_legend_settings(on_legend_settings)
    # 演示一次齿轮回调（真实运行时是点图例齿轮触发 ✓）：改颜色/线宽/线型/价格标签
    on_legend_settings(ma, 0, 0)

    # ---- 多布局：2D tiles（带可拖动分隔条）+ 普通行列 + 单图 -----------
    window = chart.win
    layout = window.layout
    created: list = []

    def prepare(sub: Chart):
        created.append(sub)
        sub.set(make_data(seed=240 + len(created)))
        sub.legend(visible=True, ohlc=False, percent=False, lines=False,
                   text=f'SUB {len(created)}')

    def apply_layout(choice: str):
        if choice == '2D 上1下2':
            # 上 1 满宽 + 下 2 并排：行间/行内都自动放可拖分隔条 ✓
            layout.arrange_tiles([(1.0, 0.5), (0.5, 0.5), (0.5, 0.5)],
                                 dividers=True, on_create=prepare)
        elif choice == '2D 上2下1':
            layout.arrange_tiles([(0.5, 0.5), (0.5, 0.5), (1.0, 0.5)],
                                 dividers=True, on_create=prepare)
        elif choice == '竖排':
            # 普通浮动布局：arrange('vertical', ...) 自己会 clearLayoutTiles ✓
            layout.arrange('vertical', 3, divider=True, on_create=prepare)
        elif choice == '横排':
            layout.arrange('horizontal', 3, divider=True, on_create=prepare)
        elif choice == '单图':
            layout.single()
        print(f'[layout] -> {choice} | 可见 {len(layout.charts)} / '
              f'隐藏 {len(layout.hidden_charts)} | tiles={layout._tiles}')

    def on_layout(owner):
        apply_layout(owner.topbar['layout'].value)

    chart.topbar.switcher('layout',
                          ('2D 上1下2', '2D 上2下1', '竖排', '横排', '单图'),
                          default='2D 上1下2', func=on_layout)
    apply_layout('2D 上1下2')
    chart.fit()


def report(chart: Chart) -> None:
    """读回类信息 —— 需要窗口已加载。"""
    layout = chart.win.layout
    print('[layout] 可见:', len(layout.charts),
          '| 隐藏:', len(layout.hidden_charts),
          '| tiles:', layout._tiles)
    for i, sub in enumerate(layout.charts):
        print(f'[layout] chart {i}: width={sub._width:.3f} '
              f'height={sub._height:.3f}')
    for series in chart.lines()[:2]:
        print(f'[series] {series.name}: visible={series.is_visible()}')
    # 图例行数（含常显的指标行）可以从页面 JS 读
    print('[legend rows]', chart.win.eval_js(
        f'Lib.lookup("{chart.id}").legend._lines.length'))

    # ---- chart.remove()：销毁图表时连 DOM wrapper 一起摘掉 ------------
    temp = chart.create_subchart(position='left', width=0.3, height=0.3)
    temp.set(make_data(seed=99))
    layout.register(temp)
    print('[remove] 前:', len(layout.charts))
    layout.unregister(temp)
    temp.remove()
    print('[remove] 后:', len(layout.charts))


def capture(chart: Chart) -> None:
    """截图写盘（需要窗口已加载）。"""
    png = chart.screenshot()
    if not png:
        return
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    chart = Chart(width=1280, height=840,
                  title='pylightcharts - 2D tiles 布局 + 图例齿轮设置')
    build(chart)
    print('提示：点顶部“布局”切换到 2D / 竖排 / 横排 / 单图；'
          '拖动格子之间的灰色分隔条改比例；点指标图例行的齿轮看回调。')
    chart.show(block=False)
    report(chart)
    capture(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
