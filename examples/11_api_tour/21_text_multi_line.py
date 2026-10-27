"""逐点文本图元（**多行**）：`shapes.text`。

LWC 的图元里没有"文字"。pylightcharts 的声明式自定义序列补了 `shapes.text`：
在数据点上画一段文字 —— 而且像 bokeh 的 `LabelSet` 一样，**文本里的 `\\n`
会渲染成多行**（`line_height` 控制行距，`baseline` 决定整块文字往哪边铺开）。
每个点还可以有**自己的**文本、颜色、行数。

典型场景：信号点标注（"方向 + 触发它的指标名"）、背离点列出同时背离的指标、
价格标签、逐笔盈亏说明……

覆盖的 API：
- `shapes.text(price, text, offset=0.0, color=None, font_size=12,
  align='center', baseline='middle', line_height=1.2,
  offset_x=0.0, offset_y=0.0, font_family=None, font_weight=None,
  font_style=None, background_color=None, background_alpha=None,
  border_color=None, border_alpha=None, border_width=1.0, padding=4.0)`；
- **像素偏移** `offset_x` / `offset_y`、字体族/粗细/斜体、以及可选的**文本底色**
  （`background_color` + `background_alpha` + `border_color` + `padding`，按最宽一行
  自动撑出外框）；这些键与 minibt 里的逐点文本样式是**同一套**，两个图表引擎通用；
- 多行：`'BUY\\nCCI\\nRSI'` → 三行；`baseline='top'` 向下铺、`'bottom'` 向上铺、
  `'middle'`（默认）整块居中到 `price`；
- 逐点不同文本 / 颜色 / 行距：都放进数据列，`shapes=lambda row: ...` 里取用；
- 与 `shapes.marker` 组合：一个信号点 = 标记 + 文本（shapes 回调返回列表）；
- 自定义序列的数据项**必须含 `value` 字段**（渲染器靠它驱动自动缩放、
  并判断"是不是空白点"）。

运行：
    python examples/11_api_tour/21_text_multi_line.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart, shapes

UP, DOWN = '#26A69A', '#EF5350'
ROWS = 90
#: 截图写在脚本旁边，和 18/19/20 保持一致（从任何工作目录运行都对）
HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_21.png')

#: 信号点携带的多行文本：行数逐个变多，方便一眼看出"多行 + 整块锚定"
INDICATORS = ['CCI', 'RSI', 'MACD', 'OBV', 'MFI']


def make_source(rows: int = ROWS) -> pd.DataFrame:
    """自包含合成行情（不需要外部数据文件）。"""
    rng = np.random.default_rng(21)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.7)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + rng.uniform(0.1, 0.7, rows)
    low = np.minimum(open_, close) - rng.uniform(0.1, 0.7, rows)
    return pd.DataFrame({
        'time': pd.bdate_range('2024-01-01', periods=rows),
        'open': open_.round(2),
        'high': high.round(2),
        'low': low.round(2),
        'close': close.round(2),
        'volume': np.abs(rng.normal(900, 220, rows)).round(),
    })


def signal_frame(frame: pd.DataFrame, step: int = 12) -> pd.DataFrame:
    """每 `step` 根造一个信号点：文本放进 `text` 列，逐点不同。"""
    rows = []
    for order, index in enumerate(range(6, len(frame), step)):
        bar = frame.iloc[index]
        below = order % 2 == 0                        # 交替做多 / 做空信号
        lines = ['BUY' if below else 'SELL']
        lines += INDICATORS[:1 + order % len(INDICATORS)]   # 行数逐渐变多
        rows.append({
            'time': bar['time'],
            # 自定义序列必须有 value：贴在 K 线外侧，随便自动缩放
            'value': float(bar['low'] if below else bar['high']),
            'text': '\n'.join(lines),
            'color': UP if below else DOWN,
            'marker': 'arrow_up' if below else 'arrow_down',
            # 文字往 K 线**外侧**铺开：做多时向下（top），做空时向上（bottom）
            'baseline': 'top' if below else 'bottom',
            'line_height': 1.25 if below else 1.0,
            'font_size': 13 if order % 3 == 0 else 11,
            'offset_x': 14 if below else -14,
            'background_color': '#222222' if below else '#332222',
            'background_alpha': 0.75,
        })
    return pd.DataFrame(rows)


def signal_shapes(row) -> list:
    """一个信号点 = 像素标记 + 多行文本（回调返回一个列表即可）。"""
    below = row['baseline'] == 'top'
    return [
        shapes.marker(row['value'], marker=row['marker'],
                      offset=14 if below else -14, size=7, color=row['color']),
        shapes.text(row['value'], row['text'], color=row['color'],
                    font_size=float(row['font_size']),
                    baseline=row['baseline'],
                    line_height=float(row['line_height']),
                    offset_x=float(row['offset_x']),
                    background_color=row['background_color'],
                    background_alpha=float(row['background_alpha']),
                    border_color=row['color'], padding=3),
    ]


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    frame = make_source()
    chart.set(frame)
    chart.legend(visible=True, font_size=12, text='逐点文本 = 方向 + 触发指标')

    signals = chart.add_custom_series('信号（多行文本）', color='#2962FF')
    # format_cols=False：不要把数据列改名/格式化（自定义序列的列名要原样保留）
    signals.set(signal_frame(frame), format_cols=False, shapes=signal_shapes)
    chart.fit()


def report(chart: Chart) -> None:
    """读回：信号条数、每个信号的文本行数（仅在窗口就绪后调用）。"""
    series = chart._lines[-1]
    data = series.data
    texts = list(data['text'])
    print(f'[text] signals={len(data)} 行数={[t.count(chr(10)) + 1 for t in texts]}')
    print('[text] 例:', repr(texts[0]).replace('\\n', ' / '),
          '| baseline=', data.iloc[0]['baseline'])
    print('[text] shapes.marker + shapes.text 各一个 -> 一个信号两个图元')


def capture(chart: Chart) -> None:
    """截图写盘（需要窗口已加载）。"""
    png = chart.screenshot()
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    chart = Chart(width=1200, height=820,
                  title='pylightcharts - 逐点多行文本')
    build(chart)
    chart.show(block=False)
    report(chart)
    capture(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
