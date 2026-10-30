"""pylightcharts 的「NaN 处断线」分段策略。

* **少量段**（≤ ``Line.MAX_GAP_SEGMENTS``，默认 64）仍逐段拆：每段一个
  legend-less ``Line`` 序列，tooltip / 十字光标最干净；
* **超过 64 段**改用 **单序列 + 透明缺口**：缺口点补成前值并染透明，引擎按
  每段**起点**取色，缺口那一段就不画 —— 效果与逐段拆一样，却只有 1 个序列
  （几百上千个分段序列每个都要一次 `addSeries` + `setData` + 一次重绘，
  加载时会"一条条从左到右画出来"）。
"""
import numpy as np
import pandas as pd


def _set(chart, name, values, **options):
    n = len(values)
    times = pd.date_range('2025-01-01', periods=n, freq='min')
    line = chart.add_series('Line', name=name, **options)
    line.set(pd.DataFrame({'time': list(times), name: values}),
             format_cols=False)
    return line


def _segments(n, length, gap):
    """`n` 段、每段 `length` 根、间隔 `gap` 根的 NaN 数据。"""
    step = length + gap
    vals = np.full(n * step, np.nan)
    for i in range(0, n * step, step):
        vals[i:i + length] = np.arange(length, dtype=float) + i
    return vals


def test_few_segments_are_split():
    """10 段（≤ 64）：仍逐段拆成 10 个分段序列。"""
    from pylightcharts.headless import HeadlessChart
    chart = HeadlessChart()
    line = _set(chart, 'st_up', _segments(10, 30, 5))
    assert len(line.__dict__.get('_gap_series') or []) == 10


def test_many_segments_use_one_transparent_series():
    """110 段、每段 30 根：1 个序列 + 透明缺口，不再建 110 个序列。"""
    from pylightcharts.headless import HeadlessChart
    chart = HeadlessChart()
    line = _set(chart, 'st_up', _segments(110, 30, 30), color='#09D142')
    assert not (line.__dict__.get('_gap_series') or [])
    payload = '\n'.join(chart._scripts)
    assert 'rgba(0, 0, 0, 0)' in payload          # 缺口点染透明
    assert '#09D142' in payload                   # 有效段仍是线色


def test_fragmented_line_uses_transparent():
    """100 段、每段 1 根（逐 bar 交替 NaN）：同样走单序列 + 透明缺口。"""
    from pylightcharts.headless import HeadlessChart
    chart = HeadlessChart()
    line = _set(chart, 'frag', _segments(100, 1, 2), color='#e00000')
    assert not (line.__dict__.get('_gap_series') or [])
    assert 'rgba(0, 0, 0, 0)' in '\n'.join(chart._scripts)


def test_no_nan_stays_single():
    from pylightcharts.headless import HeadlessChart
    chart = HeadlessChart()
    line = _set(chart, 'smooth', np.arange(100.0))
    assert not (line.__dict__.get('_gap_series') or [])


def test_create_line_also_splits_at_nan():
    """``create_line()`` 建的线也要断点。

    它以前**没有 kind**，``SeriesCommon._gap_value_column`` 只认 ``kind ==
    'Line'``，于是 NaN 处被直接连过去（``add_series('Line')`` 因为 kind 齐全
    正常）。修完 kind 之后，miniqt 主图叠加的指标线（走 create_line）才断得开 ✓。
    """
    from pylightcharts.headless import HeadlessChart
    chart = HeadlessChart()
    values = [1.0, 2.0, 3.0, np.nan, np.nan, 6.0, 7.0, 8.0]
    times = pd.date_range('2025-01-01', periods=len(values), freq='min')
    line = chart.create_line('ma', color='#FF9800', width=3)
    line.set(pd.DataFrame({'time': list(times), 'ma': values}))
    made = line.__dict__.get('_gap_series') or []
    assert len(made) == 2, '3 和 6 之间应断成两段'
    style = line._gap_series_style()
    assert style.get('color') == '#FF9800'      # 分段复制主线颜色，不落默认色
    assert style.get('line_width') == 3


def test_hidden_carrier_line_can_skip_gap_segments():
    """隐藏载体线（色带上下沿）``skip_gap_segments(True)`` 后不再拆分段序列 ✓。

    这类线线宽 0 / 完全透明，只给 ``fill_between`` 当承载体 —— 拆段没意义，
    却会造出几百个内部序列（实测 HemaTrendLevels 8 条边各 45 段 → 360 个），
    历史加载时把主线程拖死 ✗。
    """
    from pylightcharts.headless import HeadlessChart
    chart = HeadlessChart()
    line = chart.create_line('edge', color='rgba(0,0,0,0)', width=0)
    line.skip_gap_segments(True)
    values = _segments(10, 2, 2)
    times = pd.date_range('2025-01-01', periods=len(values), freq='min')
    line.set(pd.DataFrame({'time': list(times), 'edge': values}),
             format_cols=False)
    assert not (line.__dict__.get('_gap_series') or [])
    # 再来一次 update 也不能冒出来
    line.update(pd.Series({'time': times[-1], 'edge': 1.0}))
    assert not (line.__dict__.get('_gap_series') or [])


def test_prefer_single_gap_avoids_per_segment_churn():
    """``prefer_single_gap(True)`` 的线走「单序列 + 透明缺口」，不逐段拆 ✓。

    实时每秒刷新时，逐段拆会不断 delete + addSeries + setData（实测 supertrend
    这类“一半 NaN”的线每拍 ~130~270 次 JS 调用），把渲染线程拖死 → 图表卡住 ✗。
    """
    from pylightcharts.headless import HeadlessChart
    chart = HeadlessChart()
    line = chart.create_line('st', color='#09D142')
    line.prefer_single_gap(True)
    values = _segments(10, 2, 2)          # 10 段（≤ 64）
    times = pd.date_range('2025-01-01', periods=len(values), freq='min')
    line.set(pd.DataFrame({'time': list(times), 'st': values}),
             format_cols=False)
    assert not (line.__dict__.get('_gap_series') or [])
    before = len(chart._scripts)
    line.set(pd.DataFrame({'time': list(times), 'st': values}),
             format_cols=False)          # 刷新一次
    # 优化后：缺口帧在唯一一次 setData 时就上色 —— 刷新只发 1 条 JS ✓
    added = chart._scripts[before:]
    assert len(added) == 1
    assert added[0].count('setData') == 1


def test_missing_color_still_uses_single_gap_series():
    """回归 v1.0.97：指标没给颜色（``color=None``）也必须走单序列缺口 ✓。

    回测的 ``stop_price`` / ``target_price`` 是**未指定颜色**的 Line，2000 根窗口
    里有 77 个 NaN 段。旧路径因为拿不到线色直接放弃透明缺口 → 退回一段一个内部
    序列（77 个 ``addSeries``）把 JS 渲染线程拖死；现在缺色回退
    :attr:`Line.DEFAULT_LINE_COLOR`，仍然是 1 个序列 ✓。
    """
    from pylightcharts.headless import HeadlessChart
    chart = HeadlessChart()
    line = chart.add_series('Line', name='stop_price', line_width=2)
    assert line._gap_series_style().get('color') is None      # 确实没给色
    values = _segments(77, 18, 5)         # 77 段 > MAX_GAP_SEGMENTS(64)
    times = pd.date_range('2025-01-01', periods=len(values), freq='min')
    line.set(pd.DataFrame({'time': list(times), 'stop_price': values}),
             format_cols=False)
    assert not (line.__dict__.get('_gap_series') or [])       # 0 个额外序列 ✓
    payload = '\n'.join(chart._scripts)
    assert 'rgba(0, 0, 0, 0)' in payload                      # 缺口透明
    assert line.DEFAULT_LINE_COLOR in payload                 # 有效段回退默认色
    # 兜底色必须与 LWC v5 引擎的 Line 默认色一致（否则无色指标线会变蓝 ✗）
    assert line.DEFAULT_LINE_COLOR.lower() == '#2196f3'


def test_update_markers_wraps_in_iife_and_sorts():
    """回归 v1.0.97：``setMarkers`` 必须包成**无返回 IIFE**且按 time 升序 ✓。

    裸语句 ``Lib.Handler.setMarkers(...)`` 会返回 marker 原语对象（循环引用
    的 JS 代理），QtWebEngine 收集完成值时在渲染线程永久同步挂起 —— 图出来
    但整图无响应。包成 IIFE（不 return）后完成值是 undefined；同时 v5 markers
    契约要求 time 升序，乱序会让标记随机消失。
    """
    import json
    import re

    from pylightcharts.headless import HeadlessChart
    chart = HeadlessChart()
    line = chart.create_line('x')
    line.marker_list([
        {'time': '2025-01-03', 'position': 'above',
         'shape': 'arrow_down', 'color': '#ef5350', 'text': 'S'},
        {'time': '2025-01-01', 'position': 'below',
         'shape': 'arrow_up', 'color': '#26a69a', 'text': 'B'},
    ])
    script = chart._scripts[-1]
    assert script.startswith('(function(){Lib.Handler.setMarkers(')
    assert script.endswith('})()')                            # 无返回 IIFE ✓
    assert not script.startswith('Lib.Handler.setMarkers')    # 不能是裸语句 ✗
    match = re.search(r'setMarkers\([^,]+,\s*(\[.*\])\s*\);',
                      script, re.DOTALL)
    payload = json.loads(match.group(1))
    assert [m['text'] for m in payload] == ['B', 'S']         # 升序重排 ✓
