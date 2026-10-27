"""`legend=False` 必须**在创建序列那一步**就生效（pylightcharts 底层）。

用 `HeadlessChart` 把下发给 JS 的脚本录下来断言 ✓ —— 不需要浏览器窗口 ✓，
所以这几条测试是确定性的（不依赖 QtWebEngine ✓）。

断言的是两件事：
1. **名字照常传下去** ✓（名字是数据列映射的依据，清空它会踩
   「空名字 + 列名对不上 → 图表卡死」的坑 ✗）；
2. 建完序列后**把这一行图例摘掉** ✓（JS 侧 `createLineSeries` 是无条件建行的 ✗，
   「空名字 = 跳过图例行」这个老假设并不成立 ✗）。
"""
import pytest

pytest.importorskip('pylightcharts')

from pylightcharts.headless import HeadlessChart          # noqa: E402


def test_legend_true_keeps_the_row():
    """默认 `legend=True`：名字照给，**不**摘行 ✓。"""
    chart = HeadlessChart()
    chart.create_line('macd')
    script = chart.to_scripts()
    assert 'createLineSeries(' in script
    assert '"macd"' in script
    assert 'removeChild' not in script


def test_legend_false_passes_the_name_and_removes_the_row():
    """`legend=False`：名字照给 ✓ + 图例行摘掉 ✓（本功能的核心 ✓）。"""
    chart = HeadlessChart()
    chart.create_line('macd', legend=False)
    script = chart.to_scripts()
    assert '"macd"' in script, '名字必须照常传下去（数据列映射要用 ✓）'
    assert 'removeChild' in script, '图例行必须被摘掉 ✓'
    assert 'legend._lines' in script, '用的是图例自己的账本 ✓'


def test_legend_false_works_for_every_series_constructor():
    """四种建序列的方式都要认这个参数 ✓。"""
    chart = HeadlessChart()
    chart.create_line('l1', legend=False)
    chart.create_histogram('h1', legend=False)
    chart.add_series('Line', 's1', legend=False)
    chart.add_custom_series('c1', legend=False)
    script = chart.to_scripts()
    assert script.count('removeChild') >= 4
    for name in ('l1', 'h1', 's1', 'c1'):
        assert f'"{name}"' in script


def test_legend_false_also_removes_the_row_inside_a_pane():
    """副图（pane）里的序列一样要摘 ✓（macd 这类指标就在副图 ✗）。"""
    chart = HeadlessChart()
    pane = chart.add_pane()
    chart.pane_add_series(pane, 'Line', 'macd', legend=False)
    script = chart.to_scripts()
    assert '"macd"' in script
    assert 'removeChild' in script
