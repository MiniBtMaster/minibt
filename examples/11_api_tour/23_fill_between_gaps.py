"""色带断点（`fill_between`）：通道线有 `nan` 时不填色。

`upper.fill_between(lower)` 会在两条线之间填色。真实指标里通道线常常**断续**：
典型就是 ZeroLagTrendSignals 那种"多头段只有 `zlema_bull`、空头段只有 `zlema_bear`"，
另一侧是 `nan`。这种地方**不能填色**（否则色带会跨过缺口，把两条线直接连成一大块）。

本示例演示：

* `series.fill_between(other, color=..., opacity=..., line_color=...)`；
* 通道线 `bull_leg` 在**空头段**是 `nan`（另一条线 `lower_band` 一直有值）——
  色带随之**一段一段**断开，空头段完全留白；
* 中间还挖了一个"双缺口"（两条线都缺 8 根）：同样不填色；
* 缺值判定是"**任一侧**为 `nan` 就不画"，`nan` 段两端各自收口（不会连成三角形）。

运行：
    python examples/11_api_tour/23_fill_between_gaps.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart

UP, DOWN = '#26A69A', '#EF5350'
ROWS = 160
#: 截图写在脚本旁边，和 18~22 保持一致（从任何工作目录运行都对）
HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_23.png')


def make_source(rows: int = ROWS) -> pd.DataFrame:
    """合成行情 + 两条"断续"的通道线（模拟多空交替时只有一侧有效）。"""
    rng = np.random.default_rng(23)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.7)
    frame = pd.DataFrame({
        'time': pd.bdate_range('2024-01-01', periods=rows),
        'close': close.round(2),
    })

    # 通道：以收盘均值为中轴上下各 2 点；趋势方向按 30 根一段交替
    centre = frame['close'].rolling(10, min_periods=1).mean()
    trend = np.where(((np.arange(rows) // 30) % 2 == 0), 1.0, -1.0)
    upper = (centre + 3.0).to_numpy()
    lower = (centre - 3.0).to_numpy()

    # 多头段：只保留 upper（"多头通道"），lower 缺值；空头段相反 —— 与
    # ZeroLagTrendSignals 的 zlema_bull / zlema_bear 完全同构
    bull = np.where(trend > 0, upper, np.nan)
    bear = np.where(trend < 0, lower, np.nan)
    # 再挖两处真正的"双缺口"（两根线都缺），展示连通缺口也不会填色
    bull[70:78] = np.nan
    bear[70:78] = np.nan
    frame['upper_band'] = upper.round(2)
    frame['lower_band'] = lower.round(2)
    frame['bull_leg'] = bull.round(2)
    frame['bear_leg'] = bear.round(2)
    return frame


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    frame = make_source()
    chart.set(frame)
    chart.legend(visible=True, font_size=12,
                 text='色带在 nan 处断开（多空段交替 + 双缺口）')

    times = frame['time']
    bull_leg = chart.add_series('Line', name='bull_leg', color=UP, line_width=2)
    bull_leg.set(pd.DataFrame({'time': times, 'bull_leg': frame['bull_leg']}))
    lower = chart.add_series('Line', name='lower_band', color='#787B86',
                             line_width=1)
    lower.set(pd.DataFrame({'time': times, 'lower_band': frame['lower_band']}))
    upper = chart.add_series('Line', name='upper_band', color='#787B86',
                             line_width=1)
    upper.set(pd.DataFrame({'time': times, 'upper_band': frame['upper_band']}))

    # 只画**一条**色带：bull_leg 有值的区间填色；空头段 bull_leg 是 nan ->
    # 不填色（留白），中间的双缺口同样留白。任一侧为 nan 都不画。
    bull_leg.fill_between(lower, color=UP, opacity=0.25)
    chart.fit()


def report(chart: Chart) -> None:
    """读回：数一数每条色带被切成几段（= 连续有效段的个数）。"""
    frame = make_source()
    for name in ('bull_leg',):
        values = pd.to_numeric(frame[name], errors='coerce').to_numpy()
        valid = np.isfinite(values)
        edges = np.diff(np.concatenate(([0], valid.view(np.int8), [0])))
        print(f'[fill] {name}: 有值 {int(valid.sum())} 根 -> '
              f'色带 {int((edges == 1).sum())} 段（缺口处断开）')


def capture(chart: Chart) -> None:
    """截图写盘（需要窗口已加载）。"""
    png = chart.screenshot()
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    chart = Chart(width=1280, height=760,
                  title='pylightcharts - 色带断点')
    build(chart)
    chart.show(block=False)
    report(chart)
    capture(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
