"""全部绘图工具（drawings）。

覆盖的 API：
- `horizontal_line` / `vertical_line` / `vertical_span`（单时间、两时间各一次）
- `horizontal_span`（两价格 -> 色带，单价格 -> 横线）
- `ray_line` / `trend_line` / `box` / `fibonacci` / `measure` /
  `parallel_channel` / `position` / `long_position` / `short_position`
- `andrews_pitchfork` / `triangle` / `fibonacci_extension` / `gann_fan`
- 图元操作：`update(...)` / `delete()` / `options(...)` /
  `ParallelChannel.set_offset(...)` / `Position.set_risk_ratio(...)`
- 交互式绘图工具箱（`Chart(toolbox=True)`）
- `chart.legend(True)`：打开图例（默认关闭），显示 OHLC 区块与序列标签行

运行：
    python examples/11_api_tour/05_drawings.py

工具箱快捷键（按住 Alt）：
    T 趋势线 / H 水平线 / V 垂直线 / R 射线 / B 矩形 / F 斐波那契 / M 测量 /
    C 平行通道 / P 仓位 / A 音叉 / G 三角形 / X 斐波那契扩展 / N 江恩扇；
    Ctrl+Z 撤销；工具箱右上角可保存/加载/导入/导出绘图。
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart


def make_data(rows: int = 320) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.7)
    open_ = close + rng.standard_normal(rows) * 0.4
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.4, rows)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.4, rows)
    volume = rng.integers(1_000, 50_000, rows)
    return pd.DataFrame({
        'time': pd.date_range('2023-01-01', periods=rows, freq='D'),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()
    chart.set(df)
    # legend(True)：打开图例（默认关闭，与 lightweight-charts-python 一致），
    # 显示 OHLC 区块和每条序列的标签行（色块 + 名称 + 当前值）
    chart.legend(True)

    t = df['time']
    o = df['open'].to_numpy()
    h = df['high'].to_numpy()
    l = df['low'].to_numpy()
    c = df['close'].to_numpy()

    # 水平线：create + update 移动价位 + options 改样式
    hl = chart.horizontal_line(
        float(c[60]), color='#FF9800', width=2, text='support')
    hl.update(float(c[90]))                                     # 把水平线移动到新价位
    hl.options(color='#FFEB3B', style='dashed', width=2,
               text='support (moved)')  # 改线色 / 线型

    # 垂直线：create + update 移动时间 + options 改样式
    vl = chart.vertical_line(
        t.iloc[40], color='#26A69A', width=2, text='vline')
    vl.update(t.iloc[55])                                       # 把垂直线移动到新时间
    vl.options(color='#00BCD4', style='dotted', width=2,
               text='vline (moved)')  # 改线色 / 线型

    # 垂直区间（两时间）：start_time 与 end_time 都给 -> 填充色带
    chart.vertical_span(t.iloc[10], t.iloc[25],
                        color='rgba(252, 219, 3, 0.15)')
    # 垂直区间（单时间）：省略 end_time -> 单条竖线
    chart.vertical_span(t.iloc[70], color='rgba(252, 219, 3, 0.25)')

    # 水平区间（两条价格）：横贯整个图表的色带（支撑/压力区间）
    band = chart.horizontal_span(float(c.min()) + 2, float(c.min()) + 8,
                                 color='#7E57C2', opacity=0.25,   # 透明度单独给
                                 line_color='rgba(126, 87, 194, 0.9)')
    band.set_prices(float(c.min()) + 3, float(c.min()) + 9)      # 移动/改宽度
    band.apply_options(line_width=2, line_style='dashed')        # 改样式
    # 水平区间（单价格）：只画一条贯穿整个宽度的横线
    chart.horizontal_span(float(c.max()) + 2,
                          line_color='rgba(255, 255, 255, 0.4)')

    # 射线：create + options + update（通用两参数 time / price）
    ray = chart.ray_line(t.iloc[5], float(
        c[5]), color='#E91E63', width=2, text='ray')
    ray.options(color='#9C27B0', style='solid', width=2)        # 改样式
    ray.update(t.iloc[5], float(c[5]))                          # 更新锚点

    # 趋势线：create + options + update
    tl = chart.trend_line(t.iloc[30], float(l[30]), t.iloc[140], float(h[140]),
                          line_color='#2196F3', width=2)
    tl.options(color='#03A9F4', style='solid', width=3)         # 改样式
    tl.update(t.iloc[30], float(l[30]), t.iloc[150], float(h[150]))  # 更新两个端点

    # 矩形：create + update + options
    box = chart.box(t.iloc[50], float(l[50]), t.iloc[100], float(h[100]),
                    color='#4CAF50', fill_color='rgba(76, 175, 80, 0.15)', width=2)
    box.update(t.iloc[50], float(l[50]), t.iloc[105], float(h[105]))  # 拉伸矩形
    box.options(color='#8BC34A', style='solid', width=2)        # 改边框样式

    # 斐波那契回撤：create + options
    fib = chart.fibonacci(t.iloc[30], float(l[30]), t.iloc[140], float(h[140]))
    fib.options(color='#FF5722', style='solid', width=1)        # 改回撤线样式

    # 测量工具：显示涨跌幅与 bar 数
    chart.measure(t.iloc[40], float(c[40]), t.iloc[110], float(c[110]))

    # 平行通道：create + set_offset 调整平行线间距
    channel = chart.parallel_channel(t.iloc[35], float(l[35]), t.iloc[130], float(h[130]),
                                     offset=8.0)
    channel.set_offset(14.0)                                    # 把平行线外移

    # 仓位工具：create + set_risk_ratio 调整止损距离
    pos = chart.position(t.iloc[60], float(c[60]), t.iloc[120], float(h[120]),
                         risk_ratio=1.0)
    pos.set_risk_ratio(1.5)                                     # 放大止损区

    # 多头仓位（止损在下方）
    chart.long_position(t.iloc[150], float(l[150]), t.iloc[200], float(h[200]))
    # 空头仓位（止损在上方）
    chart.short_position(t.iloc[210], float(
        h[210]), t.iloc[260], float(l[260]))

    # 安德鲁音叉：三点工具
    chart.andrews_pitchfork(t.iloc[30], float(l[30]), t.iloc[80], float(h[80]),
                            t.iloc[130], float(l[130]))
    # 三角形：三点工具
    chart.triangle(t.iloc[60], float(l[60]), t.iloc[100], float(h[100]),
                   t.iloc[140], float(l[140]))
    # 斐波那契扩展：三点工具
    chart.fibonacci_extension(t.iloc[30], float(c[30]), t.iloc[90], float(h[90]),
                              t.iloc[150], float(l[150]))
    # 江恩扇：create（origin -> end 为 1x1 线）
    chart.gann_fan(t.iloc[40], float(l[40]), t.iloc[120], float(h[120]))

    # delete()：新建一条临时趋势线并立即删除，演示删除操作
    temp = chart.trend_line(t.iloc[0], float(c[0]), t.iloc[8], float(c[8]),
                            line_color='#EF5350', width=1)
    temp.delete()


def main() -> None:
    # toolbox=True 开启交互式画线工具箱：直接在上方工具栏点图标（或按 Alt+快捷键）
    # 手动画线，画完可拖动/改样式；再对照本文件中用 Python API 创建的同一批图元。
    chart = Chart(width=1100, height=750,
                  title='pylightcharts - 绘图工具', toolbox=True)
    build(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
