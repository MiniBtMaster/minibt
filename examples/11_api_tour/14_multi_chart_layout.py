"""多图表布局：页面顶栏（周期 / 指标 | 布局 / 设置）+ 上下、左右分屏。

覆盖的 API（都是 pylightcharts 扩展，Lightweight Charts 本身没有）：

- `chart.win.page_topbar()`：**横跨整个窗口**、位于所有图表之上的顶栏。
  普通 `chart.topbar` 长在某一张图里（宽度 = 那张图的宽度，图表变窄时
  它也跟着变窄）；页面顶栏不随分屏变化，因此在多周期 / 多图表工作区里
  用它来放全局控件。
- `chart.win.layout`（`pylightcharts.layout.Layout`）：把窗口分给多张
  图表。`vertical()` = 上下布局（默认在下方新增一张），`horizontal()` =
  左右布局（默认在右侧新增一张），`arrange(kind, count)` 想一次排几张都行。
  各图表默认**独立**（多周期 / 不同标的本来就不该联动平移缩放），要联动时传
  `sync=True`；图表之间带**可拖动的分隔条**，间隙宽度用
  `Layout.set_divider(size=...)`（也可按次传 `vertical(divider_size=...)`，
  或者 `divider=False` 关掉）；`Layout.on_create` 可以顺手给新图灌数据。
- 顶栏按钮菜单：`TopBar.menu(...)`（用 `TopBar.menu` 做的"布局"下拉菜单，
  上游 lightweight-charts-python 没有这个控件）。

示例里除"布局"外的按钮只打印日志，不实现具体功能。

运行：
    python examples/11_api_tour/14_multi_chart_layout.py
"""
import threading
import time

import numpy as np
import pandas as pd
from regex import F

from pylightcharts import Chart


def make_data(rows: int = 240, seed: int = 1414) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.8)
    open_ = close + rng.standard_normal(rows) * 0.4
    high = np.maximum(open_, close) + np.abs(rng.standard_normal(rows)) * 0.5
    low = np.minimum(open_, close) - np.abs(rng.standard_normal(rows)) * 0.5
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': open_, 'high': high, 'low': low, 'close': close,
        'volume': rng.integers(500, 5000, rows),
    })


def build(chart: Chart) -> None:
    df = make_data()
    chart.set(df)
    chart.legend(visible=True, ohlc=False, percent=True, lines=False,
                 text='15m')

    window = chart.win
    # ------------------------------------------------------------------
    # 页面顶栏：顶部一条，横跨窗口；不写合约/标的标题（多周期下写一个
    # 合约没意义），左侧放周期按钮 + 指标按钮，右侧放布局 + 设置
    # ------------------------------------------------------------------
    bar = window.page_topbar()

    # 左：周期按钮（分段选择器）
    def on_timeframe(win):
        # 实际项目里在这里拉取该周期的数据并 set 到各图表
        print(f"[topbar] 周期 -> {bar['timeframe'].value}")

    bar.switcher('timeframe', ('5m', '15m', '1H', '4H', '1D'),
                 default='15m', align='left', func=on_timeframe)

    # 左：指标按钮（示例只打印）
    def on_indicators(win):
        print('[topbar] 指标 -> 打开指标面板（示例未实现）')

    bar.button('indicators', '指标', align='left', separator=True,
               func=on_indicators)

    # 右：布局菜单 —— 两个选择：上下布局 / 左右布局
    def on_layout(win):
        choice = bar['layout'].value
        if choice == '上下布局':
            win.layout.vertical()
        elif choice == '左右布局':
            win.layout.horizontal()
        print(f'[topbar] 布局 -> {choice}，当前 '
              f'{len(win.layout.charts)} 张图（{win.layout.kind}）')

    # default='布局' 让按钮显示"布局 ↓"，点击后再显示选中的布局名
    bar.menu('layout', ('上下布局', '左右布局'), default='布局',
             align='right', func=on_layout)

    # 右：设置按钮（示例只打印）
    def on_settings(win):
        print('[topbar] 设置 -> 打开设置（示例未实现）')

    bar.button('settings', '设置', align='right', separator=True,
               func=on_settings)

    # ------------------------------------------------------------------
    # 布局：新建的图表由 on_create 初始化（灌数据 + 自己的图例）
    # 各图数据不同，且互不联动（多周期 / 多标的场景）
    # ------------------------------------------------------------------
    created: list = []

    def prepare(sub: Chart):
        created.append(sub)
        sub.set(make_data(seed=1414 + len(created)))
        sub.legend(visible=True, ohlc=False, percent=True, lines=False,
                   text=f'SUB {len(created)}')

    window.layout.on_create = prepare
    # 想联动时：window.layout.horizontal(sync=True)（平移+缩放+十字线），
    # window.layout.horizontal(sync='crosshair')  # 只要十字线对齐：
    #
    # 图表之间的间隙：可拖动的分隔条（默认 6px，这里 5px）。
    # set_divider 是全局设置，之后每次 arrange / 点布局菜单都用它；
    # 也可以按次传，或干脆不要间隙：
    window.layout.set_divider(size=5, color='#2a2e39',
                              hover_color='#2962FF')
    # window.layout.horizontal(divider_size=3)      # 按次设宽度
    # window.layout.set_divider(enabled=False)      # 关掉分隔条
    # window.layout.horizontal(divider=False)       # 这次不要分隔条


def report(chart) -> None:
    """读回类信息 —— 需要窗口已加载。"""
    layout = chart.win.layout
    print('[layout] 可见图表:', len(layout.charts),
          '| 隐藏图表:', len(layout.hidden_charts),
          '| kind:', layout.kind)
    for i, sub in enumerate(layout.charts):
        print(f'[layout] chart {i}: width={sub._width:.2f} '
              f'height={sub._height:.2f}')


def main() -> None:
    chart = Chart(width=1200, height=760,
                  title='pylightcharts - 多图表布局（页面顶栏 + 上下/左右分屏）')
    build(chart)
    print('提示：点右上角"布局"菜单可在 上下布局 / 左右布局 之间切换；'
          '3 秒后示例会自动"点"一次菜单演示回调链路。')

    def demo_click() -> None:
        # MenuWidget.set 等于用户点菜单项：走同一条 JS -> python 回调链路
        time.sleep(3)
        chart.win.page_topbar()['layout'].set('左右布局')
        time.sleep(1)
        report(chart)

    threading.Thread(target=demo_click, daemon=True).start()
    chart.show(block=True)


if __name__ == '__main__':
    main()
