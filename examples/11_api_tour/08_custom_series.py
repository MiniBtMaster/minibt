"""声明式自定义系列：全部图元 + 自定义 paneView（spec）。

覆盖的 API：
- 图元构造器：`shapes.rect` / `band` / `line` / `circle` / `text` /
  `polyline` / `range_bar` / `box_plot` / `error_bar`。
- `chart.add_custom_series(...)`，主图与新面板共 4 个声明式系列 +
  1 个 spec 系列，每个都调用 `set(df, shapes=...)` 与 `update(row)`。
- `chart.add_custom_series(spec={...})`：自定义 paneView 的
  `rendererDraw` / `priceValueBuilder` / `isWhitespace` / `defaultOptions`，
  其中 `rendererDraw` 用 `chart.register_js_callback` 注册成 JS 绘制回调。
- `chart.legend(True)`：打开图例（默认关闭），每个自定义系列一个标签行
  （色块 + 名称 + 值；range 类显示 low–high 区间）。每个系列都传了 `color=`
  作为图例色块色（取自该系列的图元主色），所以标签行和图上颜色一一对应。

运行：
    python examples/11_api_tour/08_custom_series.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart, shapes


def make_data(rows: int = 200) -> pd.DataFrame:
    """自包含的合成 OHLCV，并附带箱线图所需的滚动分位数。"""
    rng = np.random.default_rng(808)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.7)
    open_ = close + rng.standard_normal(rows) * 0.4
    high = np.maximum(open_, close) + rng.uniform(0.2, 1.6, rows)
    low = np.minimum(open_, close) - rng.uniform(0.2, 1.6, rows)
    df = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': rng.integers(1_000, 50_000, rows),
    })
    # 箱线图要用到的滚动分位数 / 中位数
    df['q1'] = df['close'].rolling(20, min_periods=1).quantile(0.25)
    df['median'] = df['close'].rolling(20, min_periods=1).median()
    df['q3'] = df['close'].rolling(20, min_periods=1).quantile(0.75)
    return df


# ----------------------------------------------------------------------
# 每个数据点的图元构造器（set 与 update 共用，保证前后一致）
# ----------------------------------------------------------------------

def range_shapes(row) -> list:
    """range_bar + rect + band + line：在一个数据点上叠加四种图元。"""
    return [
        # 低-高竖条（内部由 rect 组成）
        *shapes.range_bar(row['low'], row['high'], color='rgba(41, 98, 255, 0.30)'),
        # 开-收小矩形
        shapes.rect(row['open'], row['close'], left=-0.18, right=0.18,
                    fill_color='rgba(255, 193, 7, 0.60)'),
        # 低-开填充带
        shapes.band(row['low'], row['open'], left=-0.45, right=0.45,
                    fill_color='rgba(0, 150, 136, 0.12)'),
        # 收盘价水平线段
        shapes.line(row['close'], left=-0.45, right=0.45, color='#FFFFFF', width=1),
    ]


def label_shapes(row) -> list:
    """circle + text：收盘价圆点与最高价文字标签。"""
    return [
        # 收盘价处画圆点
        shapes.circle(row['close'], radius=3, color='#FF5252'),
        # 最高价上方写文字
        shapes.text(row['high'], text=f"{row['high']:.1f}", offset=0.0,
                    color='#FFFFFF', font_size=10),
    ]


def box_shapes(row) -> list:
    """box_plot：低 / Q1 / 中位 / Q3 / 高 的箱线图（琥珀色，与图例色块同色）。"""
    return shapes.box_plot(row['low'], row['q1'], row['median'], row['q3'],
                           row['high'], color='rgba(255, 179, 0, 0.35)',
                           line_color='#FFB300')


def poly_shapes(row) -> list:
    """polyline + error_bar：折线路径与误差棒。"""
    close = row['close']
    return [
        # 围绕收盘价的折线路径（带填充）
        shapes.polyline([(-0.45, close * 0.995), (0.0, close * 1.010), (0.45, close * 0.995)],
                        color='#26A69A', width=2, fill_color='rgba(38, 166, 154, 0.15)'),
        # 低/高误差棒 + 中心点
        *shapes.error_bar(close, row['low'], row['high'], color='rgba(255, 109, 0, 0.9)'),
    ]


def update_last(series, frame, shape_fn) -> None:
    """对自定义系列调用 update(row)：更新最后一根并携带 shapes。"""
    last = frame.iloc[-1]
    series.update({
        'time': int(last['time']),
        'value': float(last['close']),
        'low': float(last['low']),
        'high': float(last['high']),
        'shapes': shape_fn(last),
    })


def build(chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()

    # 主图：K 线（自定义系列叠加在它上面）
    chart.set(df)
    # legend(True)：打开图例（默认关闭），自定义系列的标签行会显示
    # 色块 + 名称 + 值（range 类只有 low/high 时显示区间）
    chart.legend(True)
    # 使用内部已格式化的时间列（epoch 秒），保证 set / update 时间一致
    frame = chart.candle_data.copy()

    # 系列 1（主图）：range_bar + rect + band + line
    # color 只影响图例色块（自定义系列的颜色由 shapes 决定），这里取该系列
    # 的主色，和图元画出来的颜色对得上，图例才容易区分
    ranges = chart.add_custom_series('range + band', color='#2962FF')
    # set(df, shapes=...)：为每一行生成一组图元
    ranges.set(frame, format_cols=False, shapes=range_shapes)
    # update(row)：更新最后一个数据点
    update_last(ranges, frame, range_shapes)

    # 系列 2（主图）：circle + text
    labels = chart.add_custom_series('circles + labels', color='#FF5252')
    labels.set(frame, format_cols=False, shapes=label_shapes)
    update_last(labels, frame, label_shapes)

    # 系列 3（新面板）：box_plot（颜色见 box_shapes）
    boxes = chart.add_custom_series('box plot', pane_index='new',
                                    color='#FFB300')
    boxes.set(frame, format_cols=False, shapes=box_shapes)
    update_last(boxes, frame, box_shapes)

    # 系列 4（新面板）：polyline + error_bar
    poly = chart.add_custom_series('polyline + error bar', pane_index='new',
                                   color='#26A69A')
    poly.set(frame, format_cols=False, shapes=poly_shapes)
    update_last(poly, frame, poly_shapes)

    # ------------------------------------------------------------------
    # add_custom_series(spec={...})：完全自定义的 paneView
    # ------------------------------------------------------------------
    # register_js_callback：注册 rendererDraw 用的 JS 绘制回调（逐帧执行）
    chart.register_js_callback(
        'tour_spec_draw', ['target', 'priceConverter', 'view'],
        "target.useBitmapCoordinateSpace(scope => {"
        "  const ctx = scope.context;"
        "  const h = scope.horizontalPixelRatio;"
        "  const v = scope.verticalPixelRatio;"
        "  ctx.fillStyle = '#7E57C2';"
        # 只有可视范围内的 bar 坐标有效（屏外的 x 是 NaN 或旧帧的残留值）
        "  for (const bar of view.visibleBars()) {"
        "    const y = priceConverter(bar.originalData.value);"
        "    if (y === null || y === undefined) continue;"
        "    ctx.beginPath();"
        "    ctx.arc(bar.x * h, y * v, 2.5 * h, 0, Math.PI * 2);"
        "    ctx.fill();"
        "  }"
        "});")
    # register_js_callback：priceValueBuilder（决定自动缩放取值）
    chart.register_js_callback('tour_spec_prices', ['row', 'view'],
                               'return [row.value, row.value, row.value];')
    # register_js_callback：isWhitespace（判断某个点是否为空）
    chart.register_js_callback('tour_spec_whitespace', ['data', 'view'],
                               'return data.value === undefined;')

    # spec 通过回调名引用上面的 JS，并合并 defaultOptions
    # color 与 rendererDraw 里的 fillStyle('#7E57C2') 一致
    spec = chart.add_custom_series('spec paneView', pane_index='new',
                                   color='#7E57C2', spec={
        'rendererDraw': 'tour_spec_draw',
        'priceValueBuilder': 'tour_spec_prices',
        'isWhitespace': 'tour_spec_whitespace',
        'defaultOptions': {'lastValueVisible': True, 'priceLineVisible': False},
    })
    # spec 系列同样调用 set(...) / update(row)
    values = frame[['time', 'close']].rename(columns={'close': 'value'})
    spec.set(values, format_cols=False)
    last = frame.iloc[-1]
    spec.update({'time': int(last['time']), 'value': float(last['close'])})


def main() -> None:
    chart = Chart(width=1100, height=950, title='pylightcharts - 自定义系列')
    build(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()
