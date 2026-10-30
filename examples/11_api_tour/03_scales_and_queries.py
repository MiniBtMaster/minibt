"""时间轴 / 价格轴控制与各类查询（readback）。

覆盖的 API：
- 时间轴：`scroll_to_position` / `scroll_to_real_time` / `reset_time_scale` /
  `scroll_position` / `time_scale_width` / `time_scale_height` / `get_visible_range` /
  `get_visible_logical_range` / `set_visible_logical_range` / `set_visible_range` /
  `time_to_coordinate` / `coordinate_to_time` / `time_to_index` /
  `logical_to_coordinate` / `coordinate_to_logical` / `time_scale_settings`。
- 价格轴（`get_price_scale('right'/'left')`）：`apply_options` / `set_mode` /
  `invert` / `set_visible_range` / `get_visible_range` / `set_auto_scale` /
  `width` / `options`。
- chart 级只读：`chart_options` / `chart_element` / `horz_behavior` /
  `auto_size_active` / `version` / `pane_size`。
- 十字光标定位：`set_crosshair_position` / `clear_crosshair_position`。

注意：查询类 API 需要真实窗口，因此 `main()` 里先 `show(block=False)`，读取完成后再
`show(block=True)` 阻塞显示。

运行：
    python examples/11_api_tour/03_scales_and_queries.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart


def make_data(rows: int = 300) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(303)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.6)
    open_ = close + rng.standard_normal(rows) * 0.3
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.0, rows)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.0, rows)
    volume = rng.integers(1_000, 50_000, rows)
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })


def build(chart: Chart) -> None:
    """把“写操作”作用在传入的 chart 上（查询操作见 `report`，不调用 show）。"""
    df = make_data()

    # set：主 K 线数据
    chart.set(df)
    chart.legend(True)

    # add_series：一条使用左价格轴的折线，便于演示 left 价格轴
    left = chart.add_series('Line', name='close', price_scale_id='left',
                            color='#f0b90b', line_width=2)
    left.set(df[['time', 'close']])

    # ------------------------------------------------------------------
    # 时间轴滚动
    # ------------------------------------------------------------------
    # scroll_to_position：把最右一根 bar 滚动到距右边缘 position 根 bar 处
    chart.scroll_to_position(20, animated=False)
    # scroll_to_real_time：滚动到最新 bar
    chart.scroll_to_real_time()
    # reset_time_scale：恢复时间轴默认状态
    chart.reset_time_scale()

    # ------------------------------------------------------------------
    # 可见范围
    # ------------------------------------------------------------------
    # set_visible_logical_range：按逻辑索引设置可见区间
    chart.set_visible_logical_range(20, 180)
    # set_visible_range：按时间设置可见区间
    chart.set_visible_range(df['time'].iloc[50], df['time'].iloc[220])

    # ------------------------------------------------------------------
    # 右价格轴（默认）
    # ------------------------------------------------------------------
    right = chart.get_price_scale('right')
    # apply_options：价格轴任意选项
    right.apply_options(
        scale_margins={'top': 0.2, 'bottom': 0.2}, border_visible=True)
    # set_mode：normal / logarithmic / percentage / index100
    right.set_mode('normal')
    # invert：是否反向（价格从上到下递增）
    right.invert(False)
    # set_auto_scale：启用自动缩放
    right.set_auto_scale(True)

    # ------------------------------------------------------------------
    # 左价格轴
    # ------------------------------------------------------------------
    left_scale = chart.get_price_scale('left')
    # apply_options：给左轴加边框
    left_scale.apply_options(border_visible=True, border_color='#2a2e39')
    # set_mode：切成百分比模式
    left_scale.set_mode('percentage')
    # invert：演示左轴反向再恢复
    left_scale.invert(True)
    left_scale.invert(False)
    # set_auto_scale：先关闭自动缩放，才能固定可见范围
    left_scale.set_auto_scale(False)
    # set_visible_range：固定左轴可见价格范围
    left_scale.set_visible_range(90.0, 130.0)

    # ------------------------------------------------------------------
    # 十字光标定位（程序化）
    # ------------------------------------------------------------------
    # set_crosshair_position：把十字光标放到指定序列的某个点
    chart.set_crosshair_position(float(df['close'].iloc[100]), df['time'].iloc[100],
                                 series=left)
    # clear_crosshair_position：清除程序化放置的十字光标
    chart.clear_crosshair_position()


def report(chart) -> None:
    """读取时间轴 / 价格轴 / chart 状态 —— 需要已经加载完成的真实窗口。"""
    df = make_data()

    # ------------------------------------------------------------------
    # 时间轴读回
    # ------------------------------------------------------------------
    # scroll_position：当前滚动位置
    print('scroll_position       :', chart.scroll_position())
    # time_scale_width / time_scale_height：时间轴尺寸
    print('time_scale_width      :', chart.time_scale_width())
    print('time_scale_height     :', chart.time_scale_height())
    # get_visible_range：可见时间范围
    print('get_visible_range     :', chart.get_visible_range())
    # get_visible_logical_range：可见逻辑范围
    print('get_visible_logical_range:', chart.get_visible_logical_range())
    # time_scale_settings：时间轴全部设置
    print('time_scale_settings   :', chart.time_scale_settings())

    # ------------------------------------------------------------------
    # 时间 / 逻辑 <-> 坐标
    # ------------------------------------------------------------------
    t = df['time'].iloc[100]
    # time_to_coordinate：时间 -> x 坐标
    print('time_to_coordinate    :', chart.time_to_coordinate(t))
    # coordinate_to_time：x 坐标 -> 时间
    print('coordinate_to_time    :', chart.coordinate_to_time(300))
    # time_to_index：时间 -> 数据索引
    print('time_to_index         :', chart.time_to_index(t))
    # logical_to_coordinate：逻辑索引 -> x 坐标
    print('logical_to_coordinate :', chart.logical_to_coordinate(100))
    # coordinate_to_logical：x 坐标 -> 逻辑索引
    print('coordinate_to_logical :', chart.coordinate_to_logical(300))

    # ------------------------------------------------------------------
    # 价格轴读回
    # ------------------------------------------------------------------
    right = chart.get_price_scale('right')
    # width：右轴宽度
    print('right.width           :', right.width())
    # options：右轴全部选项
    print('right.options(keys)   :', len(right.options()))
    # get_visible_range：右轴可见价格范围
    print('right.get_visible_range:', right.get_visible_range())

    left_scale = chart.get_price_scale('left')
    # width：左轴宽度
    print('left.width            :', left_scale.width())
    # options：左轴全部选项
    print('left.options(keys)    :', len(left_scale.options()))
    # get_visible_range：左轴可见价格范围（上面用 set_visible_range 固定过）
    print('left.get_visible_range:', left_scale.get_visible_range())

    # ------------------------------------------------------------------
    # chart 级只读
    # ------------------------------------------------------------------
    # chart_options：chart 全部选项
    print('chart_options(keys)   :', list(chart.chart_options().keys()))
    # chart_element：chart 根 DOM 节点句柄
    print('chart_element         :', chart.chart_element())
    # horz_behavior：水平轴行为对象句柄
    print('horz_behavior         :', chart.horz_behavior())
    # auto_size_active：是否开启自动尺寸
    print('auto_size_active      :', chart.auto_size_active())
    # version：Lightweight Charts 版本
    print('version               :', chart.version())
    # pane_size：pane 尺寸（全部 / 指定索引）
    print('pane_size()           :', chart.pane_size())
    print('pane_size(0)          :', chart.pane_size(0))


def main() -> None:
    chart = Chart(width=1100, height=750, title='pylightcharts - 时间轴/价格轴/查询')
    build(chart)
    # 先非阻塞显示，待窗口加载完成后再读取各类状态
    chart.show(block=False)
    report(chart)
    # 继续阻塞，直到用户关闭窗口
    chart.show(block=True)


if __name__ == '__main__':
    main()
