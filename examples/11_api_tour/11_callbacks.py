"""函数式 options（JS 回调）与 constants 枚举。

覆盖的 API：
- AbstractChart.register_js_formatter + set_price_formatter(name=...)
- AbstractChart.set_time_formatter（模板式与 name 式）
- AbstractChart.register_js_callback
- AbstractChart.set_tick_mark_formatter
- AbstractChart.set_price_formatter_callback
- AbstractChart.set_time_formatter_callback
- AbstractChart.set_option_callback(handle, method, option_path, callback)
- SeriesCommon.set_price_format_formatter / set_autoscale_info_provider
- pylightcharts.constants：LineStyle / PriceScaleMode / CrosshairMode /
  TickMarkType / ColorType + constants.verify
- chart.legend(True)：打开图例（默认关闭），显示 OHLC 区块与序列标签行

注意：`constants.verify()` 是 readback，需要真实窗口；因此 `main()` 先
`show(block=False)`，校验完成后再 `show(block=True)` 阻塞显示。

运行：
    python examples/11_api_tour/11_callbacks.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart, constants
from pylightcharts.constants import (
    ColorType,
    CrosshairMode,
    LineStyle,
    PriceScaleMode,
    TickMarkType,
)


def make_data(rows: int = 300) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(11)
    close = 100 + np.cumsum(rng.standard_normal(rows))
    return pd.DataFrame({
        'time': pd.date_range('2023-01-01', periods=rows, freq='D'),
        'open': close + rng.normal(0, 0.4, rows),
        'high': close + rng.uniform(0.3, 2.0, rows),
        'low': close - rng.uniform(0.3, 2.0, rows),
        'close': close,
        'volume': rng.integers(1_000, 50_000, rows),
    })


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()
    # 先建一条与 close 同名的折线，chart.set() 会自动把该列灌进去
    series = chart.create_line(name='close', color='#FF9800', width=2)
    # 灌入主 K 线与成交量
    chart.set(df)
    # legend(True)：打开图例（默认关闭），叠加序列才会有标签行
    chart.legend(True)

    # ------------------------------------------------------------------
    # 1) 声明式 formatter：register_js_formatter + set_*_formatter(name=)
    # ------------------------------------------------------------------
    # 声明式价格 formatter（两位小数、千分位、美元前缀）→ 价格轴显示 $1,234.50
    chart.set_price_formatter(decimals=2, thousands=True, prefix='$')
    # 注册一个 JS 表达式 formatter（Lib.registerFormatter）
    chart.register_js_formatter(
        'eur', "value => '\u20ac' + Number(value).toFixed(2)")
    # 用名字选中上面注册的 formatter → 价格轴变成 €1234.50。
    # 注意：name= 是“整体替换”，decimals/thousands/prefix/suffix/compact 会被
    # 忽略（传了会直接 ValueError），不是叠加；而且 formatter 是“最后一次设置
    # 生效”，本文件最后那个 set_option_callback(localization.priceFormatter)
    # 会把价格轴的 formatter 再改成 3 位小数（可用 chart.format_price() 验证）。
    chart.set_price_formatter(name='eur')
    # 声明式时间 formatter（模板 + 是否 UTC）
    chart.set_time_formatter(template='YYYY-MM-DD HH:mm', utc=True)
    # 注册一个 JS 表达式 formatter，再按名字选中
    chart.register_js_formatter(
        'time_short', "time => new Date(Number(time) * 1000).toISOString().slice(0, 10)")
    chart.set_time_formatter(name='time_short')

    # ------------------------------------------------------------------
    # 2) register_js_callback + 各 setter（把回调装到对应 option path）
    # ------------------------------------------------------------------
    # tickMarkFormatter 的 JS 回调（参数: time / tickMarkType / locale）
    chart.register_js_callback(
        'tick_label',
        ['time', 'tickMarkType', 'locale'],
        "const d = new Date(Number(time) * 1000); "
        f"return tickMarkType === {int(TickMarkType.Year.value)} "
        "? String(d.getUTCFullYear()) "
        ": String(d.getUTCMonth() + 1).padStart(2, '0') + '-' "
        "+ String(d.getUTCDate()).padStart(2, '0');")
    # timeScale.tickMarkFormatter
    chart.set_tick_mark_formatter('tick_label')

    # localization.priceFormatter 回调
    chart.register_js_callback(
        'price_label', ['price'], "return '$' + Number(price).toFixed(2);")
    # 把回调装为 localization.priceFormatter
    # chart.set_price_formatter_callback('price_label')

    # localization.timeFormatter 回调
    chart.register_js_callback(
        'time_label', ['time'],
        "const d = new Date(Number(time) * 1000); "
        "return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0');")
    # 把回调装为 localization.timeFormatter
    chart.set_time_formatter_callback('time_label')

    # series.priceFormat.formatter 回调（merge-safe，不会丢掉 priceFormat.type）
    chart.register_js_callback(
        'series_price', ['price'], "return Number(price).toFixed(1) + ' $';")
    # 装到折线系列的 priceFormat.formatter
    series.set_price_format_formatter('series_price')

    # series.autoscaleInfoProvider 回调（original 是默认自动缩放函数）
    chart.register_js_callback(
        'series_autoscale', ['original'],
        """
        const res = original();
        if (!res || !res.priceRange) return res;
        const pad = (res.priceRange.maxValue - res.priceRange.minValue) * 0.1;
        res.priceRange.minValue -= pad;
        res.priceRange.maxValue += pad;
        return res;
        """)
    # 装到折线系列的 autoscaleInfoProvider
    series.set_autoscale_info_provider('series_autoscale')

    # 通用入口：把回调装到任意 handle.method 的 dotted option path 上。
    # 它和 set_price_formatter / set_price_formatter_callback 写的是同一个
    # option（localization.priceFormatter），所以这之后价格轴就是 3 位小数。
    chart.register_js_callback(
        'price_option', ['price'], "return Number(price).toFixed(3);")
    # handle 用具体的 JS 句柄，如 f'{chart.id}.chart'
    chart.set_option_callback(
        f'{chart.id}.chart', 'applyOptions', 'localization.priceFormatter', 'price_option')

    # ------------------------------------------------------------------
    # 3) constants：至少 5 个枚举 + verify
    # ------------------------------------------------------------------
    # LineStyle：把折线设为虚线（apply_options 直接发数值，不走 as_enum）
    series.apply_options(lineStyle=LineStyle.Dashed)
    # PriceScaleMode：把价格轴切成对数轴（枚举名 -> 字符串字面量）
    chart.set_price_scale_mode(PriceScaleMode.Logarithmic.name.lower())
    # CrosshairMode：磁吸十字光标
    chart.apply_options(crosshair={'mode': CrosshairMode.Magnet})
    # ColorType：垂直渐变背景
    chart.apply_options(layout={'background': {
        'type': ColorType.VerticalGradient,
        'top_color': '#101820',
        'bottom_color': '#000000',
    }})
    # TickMarkType：上面 tick_label 回调用 Year(=0) 区分年份刻度
    print('TickMarkType.Year =', int(TickMarkType.Year.value))


def report(chart) -> None:
    """校验常量一致性 —— constants.verify() 是 readback，需要已加载的真实窗口。"""
    # constants.verify(chart)：校验本地常量与内嵌引擎枚举逐值一致（空表示一致）
    mismatches = constants.verify(chart)
    print('constants.verify mismatches:', mismatches)
    # format_price()：用“当前生效的”价格 formatter 格式化一个值 ——
    # 本文件最后设置的是 price_option（3 位小数），所以这里是 1234.500
    print('[formatter] 1234.5 ->', chart.format_price(1234.5))
    # 再设一次声明式 formatter，立刻能看到它变成 $1,234.50（最后一次生效）
    chart.set_price_formatter(decimals=2, thousands=True, prefix='$')
    print('[formatter] 1234.5 ->', chart.format_price(1234.5))


def main() -> None:
    chart = Chart(width=1100, height=750,
                  title='pylightcharts - function options & constants')
    build(chart)
    # 先非阻塞显示，待窗口加载完成后再校验常量
    chart.show(block=False)
    report(chart)
    # 继续阻塞，直到用户关闭窗口
    chart.show(block=True)


if __name__ == '__main__':
    main()
