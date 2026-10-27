"""chart 创建、数据写入与全局样式。

覆盖的 API：
- 数据：`set(df)` / `set(df, keep_drawings=True)` / `update(row)` /
  `update_from_tick(...)` / `batch()`。
- 外观与配置：`layout()` / `style()`（`Window.style`）/ `grid()` / `crosshair()` /
  `watermark()` / `legend()` / `spinner()` / `hotkey()` / `candle_style()` /
  `volume_config()` / `price_scale()`（主序列价格轴）/ `series_options()` /
  `precision()` / `resize()` / `fit()` / `apply_options()` / `time_scale()` /
  `time_scale_options()` / `set_price_formatter()` / `set_time_formatter()`。
- 序列：`hide_data()` / `show_data()` / `create_line()` / `create_histogram()`。

注意：`batch()` 与数据显隐在实时窗口里演示，因此 `main()` 里先 `show(block=False)`，
实时演示完成后再 `show(block=True)` 阻塞显示。

运行：
    python examples/11_api_tour/01_chart_and_data.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart


def make_data(rows: int = 300) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(101)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.5)
    open_ = close + rng.standard_normal(rows) * 0.3
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.0, rows)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.0, rows)
    volume = rng.integers(1_000, 50_000, rows)
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01 00:00', periods=rows, freq='min'),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()

    # ------------------------------------------------------------------
    # 全局外观
    # ------------------------------------------------------------------
    # layout：背景色 / 文字颜色 / 字号 / 字体
    chart.layout(background_color='#0b0e14', text_color='#d1d4dc',
                 font_size=12, font_family='Menlo')

    # style：根 CSS 变量（Window.style，通过 chart.win 暴露）
    chart.win.style(background_color='#0b0e14', hover_background_color='#2a2e39',
                    click_background_color='#363a45', active_background_color='#2962FF',
                    border_color='#2a2e39', color='#d1d4dc', active_color='#ffffff')

    # grid：纵/横网格线的显隐、颜色与线型
    chart.grid(vert_enabled=True, horz_enabled=True,
               color='rgba(42, 46, 57, 0.6)', style='dotted')

    # crosshair：十字光标模式与两条线的样式
    chart.crosshair(mode='magnet',
                    vert_visible=True, vert_width=1, vert_color='#758696', vert_style='dashed',
                    horz_visible=True, horz_width=1, horz_color='#758696', horz_style='dashed')

    # watermark：图表中央水印文字
    chart.watermark('API TOUR 01', font_size=40,
                    color='rgba(120, 123, 134, 0.22)')

    # legend：图例开关与内容（OHLC / 涨跌幅 / 指标行）
    chart.legend(visible=True, ohlc=True, percent=True, lines=True,
                 color='#d1d4dc', font_size=12, text='BTC/USDT')

    # spinner：加载转圈遮罩，先开再关
    chart.spinner(True)
    chart.spinner(False)

    # hotkey：注册 Ctrl+K 全局快捷键（回调参数为按下的键名）
    chart.hotkey('ctrl', 'k', lambda *_: print('[hotkey] ctrl+k pressed'))

    # ------------------------------------------------------------------
    # 主 K 线与成交量的样式
    # ------------------------------------------------------------------
    # candle_style：K 线实体 / 影线 / 边框配色
    chart.candle_style(up_color='#26a69a', down_color='#ef5350',
                       wick_visible=True, border_visible=True,
                       border_up_color='#26a69a', border_down_color='#ef5350')

    # volume_config：成交量副图的缩放边距与涨跌配色
    chart.volume_config(scale_margin_top=0.8, scale_margin_bottom=0.0,
                        up_color='rgba(38, 166, 154, 0.6)',
                        down_color='rgba(239, 83, 80, 0.6)')

    # price_scale：主序列所属价格轴（自动缩放 / 模式 / 反向 / 边距 / 边框）
    chart.price_scale(auto_scale=True, mode='normal', invert_scale=False,
                      align_labels=True, scale_margin_top=0.15, scale_margin_bottom=0.15,
                      border_visible=True, border_color='#2a2e39',
                      visible=True, ticks_visible=False)

    # series_options：主（K 线）序列的任意选项透传
    chart.series_options(last_value_visible=True,
                         price_line_visible=True, title='Main')

    # precision：主序列价格精度（小数位与最小变动）
    chart.precision(2)

    # set_price_formatter：价格轴刻度的声明式格式化
    chart.set_price_formatter(decimals=2, thousands=True, prefix='$')

    # set_time_formatter：时间轴刻度的声明式格式化
    chart.set_time_formatter(template='YYYY-MM-DD HH:mm', utc=False)

    # ------------------------------------------------------------------
    # 时间轴选项
    # ------------------------------------------------------------------
    # time_scale：右偏移 / 最小柱间距 / 时间与秒显示 / 边框
    chart.time_scale(right_offset=5, min_bar_spacing=1.0, visible=True,
                     time_visible=True, seconds_visible=False,
                     border_visible=True, border_color='#2a2e39')

    # time_scale_options：时间轴的任意选项透传
    chart.time_scale_options(
        fix_left_edge=True, shift_visible_range_on_new_bar=True)

    # apply_options：chart 级任意选项透传（snake_case 自动转 camelCase）
    chart.apply_options(handle_scroll={'mouseWheel': True, 'pressedMouseMove': True},
                        handle_scale={'mouseWheel': True, 'pinch': True})

    # ------------------------------------------------------------------
    # 数据写入 / 更新
    # ------------------------------------------------------------------
    # set：写入初始 K 线（含成交量）
    chart.set(df)

    # set(df, keep_drawings=True)：重新写入且保留手绘图形
    chart.set(df, keep_drawings=True)

    # update(row)：用一行 Series 覆盖/追加最后一根 K 线
    chart.update(df.iloc[-1])

    # update_from_tick：以 tick 更新，相同时间戳合并、否则开新 bar
    tick_time = df['time'].iloc[-1] + pd.Timedelta(minutes=1)
    chart.update_from_tick(pd.Series({
        'time': tick_time,
        'price': float(df['close'].iloc[-1]) + 1.0,
        'volume': 10.0,
    }), cumulative_volume=True)

    # ------------------------------------------------------------------
    # 额外序列
    # ------------------------------------------------------------------
    # create_line：叠加一条折线（列名与 name 一致）
    line = chart.create_line(name='close', color='#f0b90b', style='solid', width=2,
                             price_line=False, price_label=False)
    line.set(df[['time', 'close']])

    # create_histogram：新建一个独立价格轴的直方图序列
    hist = chart.create_histogram(name='volume', color='rgba(120, 123, 134, 0.4)',
                                  price_line=False, price_label=False,
                                  scale_margin_top=0.0, scale_margin_bottom=0.0)
    hist.set(df[['time', 'volume']])

    # ------------------------------------------------------------------
    # 尺寸
    # ------------------------------------------------------------------
    # resize：在窗口内按比例重新布局（0~1）
    chart.resize(0.95, 0.95)
    # fit：缩放以显示全部数据
    chart.fit()


def report(chart) -> None:
    """实时阶段的演示：`batch()` 与数据显隐（需要已经加载完成的真实窗口）。"""
    df = make_data()
    tick_time = df['time'].iloc[-1] + pd.Timedelta(minutes=10)

    # batch：批处理，退出 with 时把多次更新一次性提交
    with chart.batch():
        for i in range(1, 6):
            chart.update_from_tick(pd.Series({
                'time': tick_time + pd.Timedelta(minutes=i),
                'price': float(df['close'].iloc[-1]) + i,
                'volume': 5.0,
            }), cumulative_volume=True)

    # hide_data / show_data：隐藏再恢复主序列数据
    chart.hide_data()
    chart.show_data()

    # scroll_position：顺带打印一个时间轴只读值，确认窗口处于实时状态
    print('scroll_position:', chart.scroll_position())


def main() -> None:
    chart = Chart(width=1100, height=750, title='pylightcharts - chart 与数据')
    build(chart)
    # 先非阻塞显示，待窗口加载完成后再演示 batch 与显隐
    chart.show(block=False)
    report(chart)
    # 继续阻塞，直到用户关闭窗口
    chart.show(block=True)


if __name__ == '__main__':
    main()
