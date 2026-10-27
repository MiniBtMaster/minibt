"""全部内置序列类型与序列（Series）API。

覆盖的 API：
- 工厂：`create_line` / `create_area` / `create_bar` / `create_baseline` /
  `create_histogram` / `add_series('Candlestick'|'Line'|'Area'|'Bar'|'Baseline'|'Histogram')` /
  `lines()`。
- 每个序列的写操作：`set` / `update` / `update_raw` / `apply_options` / `style` /
  `price_scale_options` / `set_price_scale_mode` / `set_scale_margins` / `price_line` /
  `precision` / `hide_data` / `show_data` / `move_to_pane` / `set_series_order` /
  `delete`。
- 每个序列的读操作：`series_type` / `options` / `data_points` / `data_by_index` /
  `pop` / `last_value_data` / `bars_in_logical_range` / `price_to_coordinate` /
  `coordinate_to_price` / `get_pane_index` / `get_pane` / `series_order`。
- 标记：`marker` / `marker_list` / `remove_marker` / `clear_markers`。
- 价格线：`create_price_line` / `price_lines` + `PriceLine.apply_options` /
  `PriceLine.options` / `PriceLine.remove`。
- 副图色带：`chart.fill_between(upper, lower, ...)`（两条指标线之间的填充）+
  `series.horizontal_span(low, high, ...)`（价格区间色带，带 `opacity`）。
- pane 高度：`set_pane_stretch(index, factor)`（按比例）/ `set_pane_height(px, index)`
  （绝对高度）/ `pane_height` / `pane_stretch_factor` / `pane_size`。
- 条件上色：数据里带 `color` 列（K 线还支持 `borderColor` / `wickColor`），
  见 `osc · histogram` / `osc · line` 那个副图；`update()` 同样能带颜色。
  蜡烛的条件上色用 `color_by(df, 条件, 颜色)`（产出 color / wickColor /
  borderColor 三列，条件外的行保持原样）；`chart.mark_swings(length=)` /
  `series.mark_swings(...)` 标注波段高低点及其价格。

说明：每个序列都用独立的列名/名字（图例里显示为 `line · create_line` 这类标签），
并且各 pane 用不同的指标线（close / MA10 / MA30 / EMA20 / 偏移线），否则同数据的
序列完全重叠，图例行也全叫 `close`，分不清谁是谁。

注意：读操作需要真实窗口，因此 `main()` 里先 `show(block=False)`，读取完成后再
`show(block=True)` 阻塞显示。

运行：
    python examples/11_api_tour/02_series_types.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart, color_by


def make_data(rows: int = 200) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(202)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.7)
    open_ = close + rng.standard_normal(rows) * 0.4
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.2, rows)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.2, rows)
    volume = rng.integers(1_000, 50_000, rows)
    df = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    # 每个序列一个自己的列名，图例里才能分清谁是谁（序列名必须与值列同名，
    # 因为 SeriesCommon.set() 是按序列名去数据里找值列的）；另外给每个 pane 一条
    # 不同的"指标线"，否则同数据的序列完全重叠，看不出眼图标的开关效果。
    ma10 = df['close'].rolling(10, min_periods=1).mean()
    ma30 = df['close'].rolling(30, min_periods=1).mean()
    ema20 = df['close'].ewm(span=20, adjust=False).mean()
    df['line · create_line'] = df['close']
    df['area · create_area'] = ma10
    df['baseline · create_baseline'] = df['close']
    df['line · add_series'] = ema20
    df['area · add_series'] = ma30
    df['baseline · add_series'] = df['close'] + 2.0
    df['volume · create_histogram'] = df['volume']
    df['volume · add_series'] = df['volume']
    # 副图色带用的两条"带宽"线：close 的 ±2σ 包络（真实场景可用布林带）
    rolling = df['close'].rolling(20, min_periods=1)
    df['band · upper'] = rolling.mean() + rolling.std().fillna(0.0) * 2
    df['band · lower'] = rolling.mean() - rolling.std().fillna(0.0) * 2

    # 条件上色用的震荡指标：close 与 MA20 的差 + 它的 EMA，并逐点算好颜色
    osc = df['close'] - rolling.mean()
    osc_ema = osc.ewm(span=5, adjust=False).mean()
    df['osc · histogram'] = osc
    df['osc · line'] = osc_ema
    df['osc · hist color'] = np.where(osc >= 0, '#26A69A', '#EF5350')
    df['osc · line color'] = np.where(osc_ema.diff().fillna(0.0) >= 0,
                                      '#2962FF', '#FF9800')
    return df


def _paint(frame: pd.DataFrame, color_column: str) -> pd.DataFrame:
    """把某个颜色列改名为引擎认识的 `color`（set() 会保留它）。"""
    return frame.rename(columns={color_column: 'color'})


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 的全部“写操作”作用在传入的 chart 上（不调用 show）。"""
    df = make_data()
    # 条件上色（蜡烛）：close 高于 SMA20 的 K 线整体（实体 + 影线 + 边框）
    # 涂成琥珀色，其余的保持序列样式 —— 就是官方 "Customizing the Crosshair"
    # 那种 map 写法在 pylightcharts 里的等价物：color_by 直接产出
    # color / wickColor / borderColor 三列，条件外的行不写颜色键。
    above = df['close'] > df['close'].rolling(20, min_periods=1).mean()
    chart.set(color_by(df, above, '#FFB300'))
    chart.legend(True)
    # 波段高低点：mark_swings 用 length 根分形找高低点，并在高点上标最高价、
    # 低点下标最低价（LWC 本身没有波段识别，只有画标记的能力）
    chart.mark_swings(length=5, size=2)
    # 波段线（ZigZag）：按最小涨跌幅交替的高低点，画成折线并像指标一样自动更新
    chart.add_zigzag(threshold=0.03, markers=True, label=False)
    chart.pane_separator(color="#98ABDD",  # 分隔线颜色
                         hover_color="#5A5F6F",  # 鼠标悬停(可拖动调节高度)时的颜色
                         enable_resize=True)  # False=去掉拖动调节的手柄
    # 直接隐藏这条线
    # chart.pane_separator(color='transparent')

    # 等价的原始写法(apply_options是万能入口):
    # chart.apply_options(layout={'panes':{
    #     'separator_color': '#2A2E39',
    #     'separator_hover_color': '#363A45',
    #     'enable_resize': True,
    # }})
    # 预留多个 pane，便于把不同类型分开放置
    pane1 = chart.add_pane()
    pane2 = chart.add_pane()
    pane3 = chart.add_pane()
    pane4 = chart.add_pane()
    pane5 = chart.add_pane()
    pane6 = chart.add_pane()      # 色带演示副图
    pane7 = chart.add_pane()      # 条件上色演示副图

    # ------------------------------------------------------------------
    # create_* 工厂
    # ------------------------------------------------------------------
    # create_line：折线序列
    line = chart.create_line(name='line · create_line', color='#2962FF',
                             style='solid', width=2,
                             price_line=True, price_label=True)
    line.set(df[['time', 'line · create_line']])

    # create_area：面积序列
    area = chart.create_area(name='area · create_area', line_color='#26a69a',
                             top_color='rgba(38, 166, 154, 0.35)',
                             bottom_color='rgba(38, 166, 154, 0.0)',
                             line_width=2, pane_index=pane1)
    area.set(df[['time', 'area · create_area']])

    # create_bar：美国线（OHLC）序列
    bar = chart.create_bar(name='', up_color='rgba(38, 166, 154, 0.9)',
                           down_color='rgba(239, 83, 80, 0.9)', pane_index=pane3)
    bar.set(df)

    # create_baseline：以基准价分色的序列。注意它**不是水平线**：数据线照常
    # 画，只是在 base_value 上下用不同颜色/填充（真正的水平参考线用
    # chart.horizontal_line / series.create_price_line）。基准线默认不建图例
    # 行（legend=False），免得和真正的指标标签混在一起；要标签传 legend=True。
    baseline_value = float(df['baseline · create_baseline'].mean())
    baseline = chart.create_baseline(name='baseline · create_baseline',
                                     base_value=baseline_value,
                                     pane_index=pane2, legend=True)
    baseline.set(df[['time', 'baseline · create_baseline']])
    baseline.horizontal_span(100., 108.,
                             color='#FF5252', opacity=0.12,
                             line_color='rgba(255, 82, 82, 0.5)')

    # create_histogram：直方图序列
    hist = chart.create_histogram(name='volume · create_histogram',
                                  color='rgba(120, 123, 134, 0.5)',
                                  price_line=False, price_label=False)
    hist.set(df[['time', 'volume · create_histogram']])
    hist.move_to_pane(pane3)

    # ------------------------------------------------------------------
    # add_series：按名字创建全部内置类型
    # ------------------------------------------------------------------
    # Candlestick
    gen_candle = chart.add_series('Candlestick', name='', pane_index=pane3,
                                  up_color='#26a69a', down_color='#ef5350')
    gen_candle.set(df)
    # Line
    gen_line = chart.add_series('Line', name='line · add_series', pane_index=0,
                                color='#f0b90b', line_width=1)
    gen_line.set(df[['time', 'line · add_series']])
    # Area
    # legend_toggle：这一行的图例行要不要眼睛图标（默认 True）。显隐由外部
    # 窗口比如指标参数对话框负责时传 False，避免出现第二个入口。
    gen_area = chart.add_series('Area', name='area · add_series',
                                pane_index=pane1, line_color='#9c27b0',
                                top_color='rgba(156, 39, 176, 0.3)',
                                legend_toggle=True)
    gen_area.set(df[['time', 'area · add_series']])
    # Bar
    gen_bar = chart.add_series('Bar', name='', pane_index=pane3)
    gen_bar.set(df)
    # Baseline（基准线：同上；`add_series` 默认 legend=True，这里显式关掉）
    gen_baseline_value = float(df['baseline · add_series'].mean())
    gen_baseline = chart.add_series('Baseline', name='baseline · add_series',
                                    pane_index=pane5, legend=True,
                                    base_value=gen_baseline_value)
    gen_baseline.set(df[['time', 'baseline · add_series']])
    gen_zone = chart.horizontal_span(106.0, 108.0,  # low，high(两个价格)
                                     color="#6F9A1E",  # 填充色(任意CSS颜色)
                                     opacity=0.5,  # 填充透明度;None-用颜色自带alj
                                     # 上下边线
                                     line_color='rgba(126, 87, 194, 0.9)',
                                     line_width=1, line_style='solid',
                                     autoscale=False,  # True则这两条价也参与自动缩放
                                     pane_index=pane5)
    zone = chart.horizontal_span(98.0, 102.0,  # low，high(两个价格)
                                 color='#7E57C2',  # 填充色(任意CSS颜色)
                                 opacity=0.2,  # 填充透明度;None-用颜色自带alj
                                 line_color='rgba(126, 87, 194, 0.9)',  # 上下边线
                                 line_width=1, line_style='solid',
                                 autoscale=False)  # True则这两条价也参与自动缩放
    zone.set_prices(100.0, 106.0)  # 移动/改宽度
    zone.apply_options(opacity=0.3, line_style='dashed')
    # zone.delete()
    # 只传一个价格(或价格列表)每个价格一条贯穿全宽的横线
    chart.horizontal_span(108.0, line_color='rgba(255,255,255,0.4)')
    chart.horizontal_span([98.0, 108.0], filled=False)

    # Histogram
    # `add_series` 走引擎默认值，直方图会挂在 pane 的 'right' 价格轴上。
    # volume（1e3~5e4）和上面的 baseline（~100）共轴会把坐标轴拉到 0~50000，
    # 价格序列被压成一条底部的直线，所以给它一个独立价格轴 + volume 格式，
    # 与 create_histogram 的做法一致。
    gen_hist = chart.add_series('Histogram', name='volume · add_series',
                                pane_index=pane4, color='#9fea98',
                                price_scale_id='volume2',
                                price_format={'type': 'volume'})
    gen_hist.set(df[['time', 'volume · add_series']])

    # ------------------------------------------------------------------
    # 副图色带：两条指标线之间的填充 + 价格区间色带
    # ------------------------------------------------------------------
    # 两条带宽线放在新建的副图（pane6）里，共用一个价格轴
    band_upper = chart.add_series('Line', name='band · upper',
                                  pane_index=pane6, color='#26A69A',
                                  line_width=1, price_line=False,
                                  price_label=False)
    band_upper.set(df[['time', 'band · upper']])
    band_lower = chart.add_series('Line', name='band · lower',
                                  pane_index=pane6, color='#26A69A',
                                  line_width=1, price_line=False,
                                  price_label=False)
    band_lower.set(df[['time', 'band · lower']])

    # fill_between：把两条线之间的区域填成色带；opacity 单独给，
    # None 表示沿用颜色自带的 alpha（真实场景可换成 add_bollinger 的两条线）
    band_fill = chart.fill_between(band_upper, band_lower,
                                   color='#26A69A', opacity=0.18)

    # horizontal_span：在同一个副图里再画一条价格区间色带（支撑/压力区间）；
    # 从序列上调用 -> 色带落在该序列所在的 pane
    zone_low = float(df['band · lower'].min())
    band_zone = band_upper.horizontal_span(zone_low, zone_low + 2.0,
                                           color='#FF5252', opacity=0.12,
                                           line_color='rgba(255, 82, 82, 0.5)')

    # ------------------------------------------------------------------
    # 条件上色：把颜色写进数据（引擎的键名就是 `color`），按条件逐点着色
    # ------------------------------------------------------------------
    # histogram：osc > 0 画绿、< 0 画红
    osc_hist = chart.add_series('Histogram', name='osc · histogram',
                                pane_index=pane7, color='#787B86',
                                price_line=False, price_label=False)
    osc_hist.set(_paint(df[['time', 'osc · histogram', 'osc · hist color']],
                        'osc · hist color'))

    # line：按"是否上升"上色（蓝=上升 / 橙=下降），同一副图共用一个价格轴
    osc_line = chart.add_series('Line', name='osc · line', pane_index=pane7,
                                line_width=2, price_line=False,
                                price_label=False)
    osc_line.set(_paint(df[['time', 'osc · line', 'osc · line color']],
                        'osc · line color'))

    # pane 高度：set_pane_stretch 给"拉伸因子"，各 pane 按比例分配
    # （这里主图 : 色带副图 = 3 : 1；比例是对"扣掉分隔条与时间轴后的可用高度"而言）
    chart.set_pane_stretch(0, 3)
    chart.set_pane_stretch(pane6, 1.4)

    # lines()：返回通过 create_*/add_series 建立的序列列表
    series_list = chart.lines()
    print('[build] lines() ->', len(series_list))

    value_series = [line, area, baseline, hist,
                    gen_line, gen_area, gen_baseline, gen_hist,
                    band_upper, band_lower,
                    osc_hist, osc_line]

    ohlc_series = [bar, gen_candle, gen_bar]
    all_series = value_series + ohlc_series
    #: histograms are volume overlays: they sit in the bottom band of the pane
    histograms = {hist, gen_hist}

    # ------------------------------------------------------------------
    # 每个序列的通用写操作
    # ------------------------------------------------------------------
    for s in all_series:
        # 直方图（volume）贴底显示，价格序列上下各留 10%
        top, bottom = (0.8, 0.0) if s in histograms else (0.1, 0.1)
        # apply_options：任意序列选项透传
        s.apply_options(last_value_visible=True)
        # style：BridgeSeries 的便捷样式方法（Line / Histogram 没有该方法）
        if hasattr(s, 'style'):
            s.style(last_value_visible=True)
        # price_scale_options：该序列所属价格轴的任意选项
        s.price_scale_options(scale_margins={'top': top, 'bottom': bottom})
        # set_price_scale_mode：normal / logarithmic / percentage / index100
        s.set_price_scale_mode('normal')
        # set_scale_margins：价格轴上下边距
        s.set_scale_margins(top, bottom)
        # price_line：最后值标签与价格线的开关
        s.price_line(label_visible=True, line_visible=True, title='')
        # precision：价格小数位
        s.precision(2)

    # update：为每个序列覆盖/追加最后一个点
    next_time = df['time'].iloc[-1] + pd.Timedelta(days=1)
    for s in value_series:
        s.update(pd.Series({'time': next_time,
                            s.name: float(df[s.name].iloc[-1]) + 0.1}))
    for s in ohlc_series:
        row = df.iloc[-1].copy()
        row['time'] = next_time
        row['close'] = float(row['close']) + 0.5
        s.update(row)

    # 条件上色的序列在 update() 时也能带颜色：把最后一根改成"下降"的橙色
    osc_line.update(pd.Series({'time': next_time,
                               'value': float(df['osc · line'].iloc[-1]),
                               'color': '#FF9800'}))

    # update_raw：直接传入图表格式的点（time 为 UTC 秒）
    line.update_raw({'time': int(next_time.timestamp()),
                     'value': float(df['close'].iloc[-1]) + 0.7})

    # move_to_pane：把一条序列移动到另一个 pane
    gen_line.move_to_pane(pane3)

    # ------------------------------------------------------------------
    # 标记
    # ------------------------------------------------------------------
    # marker：添加单个标记，返回其 id
    marker_id = line.marker(time=df['time'].iloc[50], position='below',
                            shape='arrow_up', color='#26a69a', text='B')
    # marker_list：批量添加标记
    line.marker_list([
        {'time': df['time'].iloc[80], 'position': 'above', 'shape': 'circle',
         'color': '#ef5350', 'text': 'S'},
        {'time': df['time'].iloc[120], 'position': 'below', 'shape': 'square',
         'color': '#2962FF', 'text': 'X'},
    ])
    # remove_marker：按 id 删除单个标记
    line.remove_marker(marker_id)
    # clear_markers：清空全部标记
    # line.clear_markers()

    # ------------------------------------------------------------------
    # 价格线
    # ------------------------------------------------------------------
    # create_price_line：在折线上创建一条水平价格线
    price_line = line.create_price_line(price=float(df['close'].iloc[-1]) + 2,
                                        color='#f0b90b', line_width=1, line_style='dashed',
                                        axis_label_visible=True, line_visible=True,
                                        title='target')
    # PriceLine.apply_options：修改已创建价格线的选项
    price_line.apply_options(color='#ff9800', line_style='dotted')


def report(chart) -> None:
    """读取序列状态 —— 这些是 readback，需要已经加载完成的真实窗口。"""
    df = make_data()
    # 从 chart.lines() 里取回 build 建立的全部序列
    all_series = chart.lines()

    for s in all_series:
        # series_type：序列类型名
        print('series_type          :', s.series_type())
        # options：读取当前全部选项
        print('options(keys)        :', len(s.options()))
        # data_points：读取 JS 侧全部数据点
        print('data_points          :', len(s.data_points()))
        # data_by_index：按下标读取单个数据点
        print('data_by_index        :', s.data_by_index(10))
        # last_value_data：最后一个可见值信息
        print('last_value_data      :', s.last_value_data())
        # bars_in_logical_range：某逻辑区间内的 bar 信息
        print('bars_in_logical_range:', s.bars_in_logical_range(0, 50))
        # price_to_coordinate / coordinate_to_price：价格与坐标互转
        print('price_to_coordinate  :', s.price_to_coordinate(
            float(df['close'].iloc[-1])))
        print('coordinate_to_price  :', s.coordinate_to_price(200))
        # get_pane_index / get_pane：所在 pane 的索引与句柄
        print('get_pane_index       :', s.get_pane_index())
        print('get_pane             :', s.get_pane())
        # series_order：同 pane 内的绘制顺序
        order = s.series_order()
        print('series_order         :', order)
        # set_series_order：把顺序设置为读回的值（演示写 API）
        s.set_series_order(order if order is not None else 0)
        # hide_data / show_data：隐藏再恢复该序列
        # （库内部还会访问主图专有的 volumeSeries，非 K 线序列会在控制台打印一条
        #   桥接警告，但不影响序列本身显隐与后续调用）
        s.hide_data()
        s.show_data()

    # pop：从尾部弹出 2 个数据点并返回
    for s in all_series:
        if s.name == 'area · create_area' and s.series_type() == 'Area':
            print('pop                  :', len(s.pop(2)))
            break

    # price_lines：读回价格线列表
    for s in all_series:
        lines = s.price_lines()
        if lines:
            # PriceLine.options：读取价格线选项
            print('price_line.options   :', lines[0].options())
            # PriceLine.remove：删除价格线
            lines[0].remove()
            break


def main() -> None:
    chart = Chart(width=1100, height=800, title='pylightcharts - 全部序列类型')
    build(chart)
    # 先非阻塞显示，待窗口加载完成后再读取序列状态
    chart.show(block=False)
    report(chart)
    # delete：删除一个序列（放在最后，避免影响上面的读取）
    for s in chart.lines():
        if s.series_type() == 'Histogram':
            s.delete()
            break
    # 继续阻塞，直到用户关闭窗口
    chart.show(block=True)


if __name__ == '__main__':
    main()
