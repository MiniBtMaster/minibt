"""无限历史（官方 demos/infinite-history）：向左滚动时自动加载更早的 K 线。

对应官方 demo https://tradingview.github.io/lightweight-charts/tutorials/demos/infinite-history
官方做法是订阅可见逻辑区间，靠近左边缘时把更早的一批数据 prepend 上去
（`series.setData([...older, ...current])`），引擎会保持视口不动。这里的数据来自
Python：用图表自己的 `events.range_change`（就是 `barsInLogicalRange().barsBefore`，
仓库里已自带节流），到边缘就调 `loader(count)` 取更早的一批。

覆盖的 API：
- `chart.infinite_history(loader, page=, threshold=, spinner=, on_load=,
  on_exhausted=, max_requests=, autostart=)`；
- `loader(count)` 或 `loader(count, before)`（也可写成 `before=` 关键字）返回
  比现有数据更早的一批：DataFrame（time + OHLC [+ volume]）、带时间索引的 Series，
  或 `None` / 空表表示"没有更早的了"；
- 运行期：`history.loaded` / `.earliest` / `.latest` / `.exhausted` / `.requests` /
  `.loading` / `.load()`（手动拉一批）/ `.stop()`（不再跟随可见区间）；
- **指标会一起延长**：主图指标（SMA）和副图指标（RSI，`pane_index=1`）都会用
  补进来的老数据重算并重新下发，所以指标线和 K 线一样能一直往前延伸 —— 而且
  拼接口附近原来"半截窗口"的指标值会变成完整窗口的准确值；
- 失败/穷尽处理：loader 返回空表即标记 `exhausted` 并停止请求（`on_exhausted`）。

注意：`range_change` 这类 JS → Python 回调是在窗口事件循环里派发的，所以
`show(block=True)`（真实应用里就是主循环）期间才会触发；本文件按惯例先
`show(block=False)` 截图，再 `show(block=True)` 留给用户滚动。

运行：
    python examples/11_api_tour/18_infinite_history.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_18.png')

#: the running controller, so `report()` (and tests) can look at it
HISTORY = None


def make_source(rows: int = 4000) -> pd.DataFrame:
    """A long history the chart only sees a slice of at first."""
    index = pd.date_range(end='2024-06-01', periods=rows, freq='D')
    rng = np.random.default_rng(7)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.014, rows)))
    open_ = close * (1 + rng.normal(0, 0.004, rows))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, rows)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, rows)))
    return pd.DataFrame({
        'time': index, 'open': open_.round(2), 'high': high.round(2),
        'low': low.round(2), 'close': close.round(2),
        'volume': np.abs(rng.normal(900, 220, rows)).round(),
    })


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    global HISTORY
    source = make_source()
    chart.set(source.tail(200))                      # start with the newest 200
    chart.legend(visible=True, font_size=12,
                 text=f'{len(source)} bars available')

    # 主图指标 + 副图指标：两者都要跟着历史一起往前延伸
    sma = chart.add_sma(length=50, line_width=2)
    rsi = chart.add_rsi(length=14, pane_index=1)

    def load(count, before=None):
        older = source if before is None else source[source['time'] < before]
        return older.tail(count)

    def on_load(history, added):
        chart.topbar['bars'].set(
            f'{history.loaded} bars   ({added} older)' if added
            else f'{history.loaded} bars')

    def on_exhausted(history):
        chart.topbar['bars'].set(f'{history.loaded} bars   (no more history)')

    chart.topbar.textbox('bars', '200 bars')
    HISTORY = chart.infinite_history(
        load, page=250, threshold=60, spinner=True,
        on_load=on_load, on_exhausted=on_exhausted)

    # a small marker so the two indicator panes are easy to tell apart
    sma.apply_options(price_line=False)
    rsi.apply_options(price_line=False)
    chart.fit()


def report(chart: Chart) -> None:
    """打印加载状态与指标覆盖范围（读回，仅在窗口就绪后调用）。"""
    if HISTORY is None:
        return
    print('[history]', HISTORY, '| requests:', HISTORY.requests)
    print('[bars] loaded:', HISTORY.loaded, '| earliest:', HISTORY.earliest,
          '| latest:', HISTORY.latest)
    for name, series in (('SMA 50', chart._lines[0]), ('RSI 14', chart._lines[1])):
        print(f'[indicator] {name} pane={series._pane_index} '
              f'bars={len(series.data)} '
              f'from={pd.to_datetime(series.data["time"].min(), unit="s")}')


def capture(chart: Chart) -> None:
    """截图写盘（需要窗口已加载）。"""
    png = chart.screenshot()
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    chart = Chart(width=1200, height=820, title='pylightcharts - 无限历史')
    build(chart)
    chart.show(block=False)
    report(chart)
    capture(chart)
    # 事件在窗口事件循环里派发：阻塞显示期间向左滚动即可看到历史不断补进来
    chart.show(block=True)


if __name__ == '__main__':
    main()
