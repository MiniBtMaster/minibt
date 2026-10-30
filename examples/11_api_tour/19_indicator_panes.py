"""指标副图用 pane 管理：建 / 换 / 移除（含指标线与左上角标签）。

这是给 minibt 那类需求做的案例：副图不再是 `create_subchart`（独立图表 / 独立
webview），而是 lightweight-charts v5 原生的 **pane**，因此

* 一条 webview、一套时间轴与十字线（缩放/平移天然同步）；
* 移除指标时 `series.delete()` 会同时摘掉**指标线**和**左上角的指标标签**（图例行，
  含眼睛图标）；最后一个序列被摘掉后，引擎会自动把这个清空的 pane 去掉
  （`add_pane(preserve_empty=True)` 建的 pane 例外，需要 `remove_pane()`）；
* `chart.pane_count()` / `series.pane_index` 在 Python 侧同步维护，后面的 pane 会
  自动上移，所以"删了再加"不会错位。

覆盖的 API：
- `add_pane(preserve_empty=)` / `pane_count()` / `pane_add_series(index, kind, ...)` /
  `pane_add_custom_series` / `set_pane_height` / `pane_price_scale` / `remove_pane(index)`；
- `series.delete()`（指标线 + 图例行 + 空 pane）、`series.pane_index`；
- 顶栏 switcher 切换"当前副图指标"（= 先 delete 旧的，再建新的 pane + 指标）、
  按钮切换"保留空 pane"、按钮"删除最后一个副图"（`remove_last_pane()`：
  先逐个 `series.delete()`，若该 pane 是保留下来的空 pane 再 `remove_pane()`）；
- `chart.legend(visible=True)` 用于确认标签（含眼睛图标）也一起被移除。

运行：
    python examples/11_api_tour/19_indicator_panes.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_19.png')

#: 副图指标 -> (名称, 计算函数, 颜色)
INDICATORS = {
    'RSI': ('RSI 14', lambda frame: _rsi(frame['close'], 14), '#7E57C2'),
    'MACD': ('MACD 12,26', lambda frame: _macd(frame['close'])[0], '#2962FF'),
    'CCI': ('CCI 20', lambda frame: _cci(frame, 20), '#FFB300'),
}


def _rsi(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def _macd(close: pd.Series, fast: int = 12, slow: int = 26,
          signal: int = 9) -> pd.Series:
    line = (close.ewm(span=fast, adjust=False).mean()
            - close.ewm(span=slow, adjust=False).mean())
    return line - line.ewm(span=signal, adjust=False).mean()


def _cci(frame: pd.DataFrame, length: int = 20) -> pd.Series:
    typical = (frame['high'] + frame['low'] + frame['close']) / 3
    mean = typical.rolling(length).mean()
    deviation = (typical - mean).abs().rolling(length).mean()
    return (typical - mean) / (0.015 * deviation)


def make_data(rows: int = 260, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = 100 + np.cumsum(rng.normal(0.05, 1.2, rows))
    open_ = close + rng.normal(0, 0.4, rows)
    return pd.DataFrame({
        'time': index, 'open': open_.round(2),
        'high': (np.maximum(open_, close) + 0.6).round(2),
        'low': (np.minimum(open_, close) - 0.6).round(2),
        'close': close.round(2),
        'volume': np.abs(rng.normal(900, 200, rows)).round(),
    })


#: 当前副图（pane 索引, 指标线），删/建时更新
SUBPLOT = {'pane': None, 'series': None}


def show_indicator(chart: Chart, name: str) -> None:
    """换副图指标：先把旧的连标签一起删掉（空 pane 自动消失），再建新的。"""
    remove_indicator(chart)
    if name == 'none':
        return
    title, compute, color = INDICATORS[name]
    frame = chart.candle_data
    pane = chart.add_pane()
    series = chart.pane_add_series(pane, 'Line', name=title, color=color,
                                   line_width=2)
    values = pd.DataFrame({'time': frame['time'], title: compute(frame)})
    series.set(values)
    chart.set_pane_height(120, index=pane)
    SUBPLOT.update(pane=pane, series=series)


def remove_indicator(chart: Chart) -> None:
    """移除当前副图：`delete()` 摘掉指标线 + 左上角标签，空 pane 由引擎去掉。"""
    series = SUBPLOT.get('series')
    if series is None:
        return
    series.delete()
    SUBPLOT.update(pane=None, series=None)


def remove_last_pane(chart: Chart) -> bool:
    """删除最后一个副图 pane（它的指标线与左上角标签一起走）。

    先挨个 `delete()` 该 pane 里的序列（最后一个删掉时空 pane 由引擎自动去掉）；
    如果这个 pane 是 `add_pane(preserve_empty=True)` 建的（还留着），再显式
    `remove_pane()`。返回是否真的删掉了一个副图。
    """
    index = chart.pane_count() - 1
    if index <= 0:
        return False
    for series in [item for item in chart._lines if item.pane_index == index]:
        series.delete()
    if chart.pane_count() > index:          # 保留下来的空 pane
        chart.remove_pane(index)
    if SUBPLOT.get('pane') == index:
        SUBPLOT.update(pane=None, series=None)
    return True


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    chart.set(make_data())
    chart.legend(visible=True, font_size=12, text='PANE DEMO')

    current = {'name': 'RSI'}

    def on_indicator(owner):
        current['name'] = owner.topbar['indicator'].value
        show_indicator(chart, current['name'])

    def on_keep(owner):
        keep = owner.topbar['keep'].value == '保留空 pane'
        # 建一个显式保留的空 pane，用来对比"自动消失"的行为
        pane = chart.add_pane(preserve_empty=keep)
        chart.pane_add_series(pane, 'Line', name='probe', color='#26A69A')

    def on_remove_last(owner):
        if not remove_last_pane(chart):
            print('[pane] 只剩主图了，没有副图可删')

    chart.topbar.switcher('indicator', ('RSI', 'MACD', 'CCI', 'none'),
                          default='RSI', func=on_indicator)
    chart.topbar.button('keep', '保留空 pane', toggle=True, func=on_keep)
    chart.topbar.button('remove_pane', '删除最后一个副图', func=on_remove_last)
    show_indicator(chart, 'RSI')
    chart.fit()


def report(chart: Chart) -> None:
    """打印 pane / 指标状态（读回，仅在窗口就绪后调用）。"""
    print('[panes]', chart.pane_count(), '| series per pane:',
          [chart.pane_series_count(i) for i in range(chart.pane_count())])
    print('[subplot] pane:', SUBPLOT['pane'],
          '| series:', SUBPLOT['series'] and SUBPLOT['series'].name)
    print('[topbar] buttons:', [widget for widget in chart.topbar._widgets])
    for i, series in enumerate(chart._lines):
        print(f'[series {i}] {series.name!r} pane={series.pane_index}')
    # eval_js returns whatever the expression yields: this one is a number
    print('[legend rows]', chart.win.eval_js(
        f'Lib.lookup("{chart.id}").legend._lines.length'))


def capture(chart: Chart) -> None:
    """截图写盘（需要窗口已加载）。"""
    png = chart.screenshot()
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    chart = Chart(width=1200, height=820, title='pylightcharts - pane 副图')
    build(chart)
    chart.show(block=False)
    report(chart)
    capture(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
