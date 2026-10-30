"""数值水平轴（yield / options）与自定义水平轴（month）。

覆盖的 API：
- `YieldCurveChart` / `OptionsChart`（`_NumericMixin`）：`add_curve(...)`、
  `add_series('Line'|'Area', ...)`、`series.set(time 为数值的 DataFrame)`。
- `class MonthChart(Chart)` 的 `_horz_scale_name` / `_horz_scale`，
  以及 `AbstractChart.register_horz_scale_behavior(name, spec)` 的
  `(params, body)` 写法：`options` / `preprocessData` /
  `convertHorzItemToInternal` / `key` / `cacheKey` / `formatHorzItem` /
  `formatTickmark`。

注意：数值轴图表**没有 K 线**，不要调用 `chart.set(df)`；先用 `add_curve` /
`add_series` 建序列，再 `series.set(df)`。

运行（默认 yield）：
    python examples/11_api_tour/12_numeric_and_scale.py --kind yield
    python examples/11_api_tour/12_numeric_and_scale.py --kind options
    python examples/11_api_tour/12_numeric_and_scale.py --kind month
"""
import argparse

import numpy as np
import pandas as pd

from pylightcharts import Chart, OptionsChart, YieldCurveChart

# 供 JS 回调使用的月份名数组字面量（回调必须是纯 JS 片段）
_MONTHS_JS = "['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']"


def make_curve_data() -> pd.DataFrame:
    """自包含的数值横轴数据：time 是期限（月），避免依赖外部 csv。"""
    rng = np.random.default_rng(1212)
    time = np.array([1, 3, 6, 12, 24, 36, 60, 120])
    rate = 2.4 + np.log1p(time) * 0.55 + rng.normal(0, 0.04, time.size)
    spread = 0.15 + rng.uniform(0.0, 0.25, time.size)
    return pd.DataFrame({'time': time, 'rate': rate, 'spread': spread})


def make_month_data() -> pd.DataFrame:
    """自包含的自定义横轴数据：time 是月份序号 1~12。"""
    rng = np.random.default_rng(1213)
    time = np.arange(1, 13)
    value = 100 + np.cumsum(rng.normal(0, 3.0, time.size))
    return pd.DataFrame({'time': time, 'value': value})


class MonthChart(Chart):
    """横轴为「月份」的自定义水平轴图表。

    `_horz_scale` / `_horz_scale_name` 会被 `AbstractChart._setup_horz_scale()`
    在创建 `Lib.Handler` 之前读取，并通过 `register_horz_scale_behavior` 注册为
    `IHorzScaleBehavior`，随后 `_chart_kind` 变成 `custom:month`。
    """

    # 自定义水平轴名称（注册名，与 _chart_kind 的 custom:<name> 对应）
    _horz_scale_name = 'month'
    # 横轴不再是时间：让 series.set() 保留数值 time，不做 datetime 转换
    _time_based = False
    # 逐方法映射到 JS 回调：(params, body) 元组在注册时即时编译
    _horz_scale = {
        # options：IHorzScaleBehavior.options()，返回横轴行为自身的选项对象
        'options': ([], 'return {};'),
        # preprocessData：整批数据写入前预处理（此处原样返回）
        'preprocessData': (['data'], 'return data;'),
        # convertHorzItemToInternal：把数据里的 time 转成内部横轴值
        'convertHorzItemToInternal': (['item'], 'return Number(item);'),
        # key：内部横轴值的唯一字符串键
        'key': (['item'], 'return String(item);'),
        # cacheKey：内部横轴值的数值缓存键
        'cacheKey': (['item'], 'return Number(item);'),
        # formatHorzItem：格式化单个横轴项（十字光标标签），time 为 1~12
        'formatHorzItem': (['item'], f'return {_MONTHS_JS}[(Math.round(item) - 1) % 12];'),
        # formatTickmark：格式化刻度，item 是 TickMark 对象（取 item.time）
        'formatTickmark': (['item', 'loc'], f'return {_MONTHS_JS}[(item.time - 1) % 12];'),
    }


def build_curve(chart: MonthChart) -> None:
    """数值横轴：`add_curve` 与 `add_series('Line'|'Area', ...)`（可复用）。"""
    df = make_curve_data()

    # add_curve（_NumericMixin）：在数值横轴上建一条 Line，name 即数据列名
    curve = chart.add_curve('rate', kind='Line', color='#2962FF', line_width=2)
    # set：写入 time 为数值的 DataFrame（数值轴没有 K 线，不能用 chart.set）
    curve.set(df[['time', 'rate']])

    # add_series('Area', ...)：在数值横轴上再叠加一条面积序列
    area = chart.add_series('Area', 'spread', line_color='#26A69A',
                            top_color='rgba(38, 166, 154, 0.35)',
                            bottom_color='rgba(38, 166, 154, 0.02)', line_width=2)
    # set：写入该面积序列的数值 time 数据
    area.set(df[['time', 'spread']])

    # fit：缩放以显示全部期限点
    chart.fit()


def build_month(chart: MonthChart) -> None:
    """自定义水平轴：在 MonthChart 上 `add_series('Line', ...)`（可复用）。"""
    df = make_month_data()

    # add_series('Line', ...)：自定义横轴上建折线，数据列名与 name 一致
    series = chart.add_series('Line', 'value', color='#FF9800', line_width=2)
    # set：写入 time 为月份序号的 DataFrame（MonthChart 已关闭 datetime 转换）
    series.set(df[['time', 'value']])

    # fit：让 1~12 月完整显示
    chart.fit()


def main() -> None:
    parser = argparse.ArgumentParser(description='数值轴 / 自定义水平轴示例')
    # --kind：在 yield（默认）、options、month 三种入口之间切换
    parser.add_argument(
        '--kind', choices=('yield', 'options', 'month'), default='yield')
    args = parser.parse_args()

    if args.kind == 'month':
        # 自定义水平轴入口：Chart 子类 + _horz_scale
        chart = MonthChart(width=1100, height=750,
                           title='pylightcharts - 自定义月份水平轴')
        build_month(chart)
    elif args.kind == 'options':
        # 数值横轴入口（options）：横轴是行权价
        chart = OptionsChart(width=1100, height=750,
                             title='pylightcharts - 数值水平轴（options）')
        build_curve(chart)
    else:
        # 数值横轴入口（yield，默认）：横轴是期限（月）
        chart = YieldCurveChart(width=1100, height=750,
                                title='pylightcharts - 数值水平轴（yield）')
        build_curve(chart)

    chart.show(block=True)


if __name__ == '__main__':
    main()
