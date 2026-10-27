"""「柱体线 + 指标线」混合副图的**绘制层级**：柱体必须先建（在底层）✓。

LWC 同一 pane 里序列按**创建顺序**堆叠：先建的在下层 ✗ —— macd 的线序是
``macdx / macdh / macds``，柱体夹在中间 → 先建的 ``macdx`` 被柱体盖住 ✗
（用户反馈）。所以要先建柱体、再建指标线；并且因为改了顺序，**实时更新**
（``update_last`` / ``reslice`` / ``apply_*`` 都按 ``zip(series, specs)`` 同下标
取值 ✓）必须跟着一致 ✓。
"""
import numpy as np
import pandas as pd


import pytest


@pytest.fixture
def headless(monkeypatch):
    """把 StrategyWindow 的 Chart 换成 HeadlessChart（不出窗口 ✓）。"""
    import minibt.strategy.strategy_window as sw
    from pylightcharts.headless import HeadlessChart
    monkeypatch.setattr(
        sw, 'Chart',
        lambda *a, **kw: HeadlessChart(
            **{k: v for k, v in kw.items() if k != 'title'}))
    return sw


def _read(*parts):
    import pathlib

    return pathlib.Path(__file__).resolve().parents[1].joinpath(
        *parts).read_text(encoding='utf-8')


def test_pane_zorder_bars_before_lines():
    from minibt.strategy.realtime import IndicatorSpec, _pane_zorder

    bar = IndicatorSpec(name='macdh', overlap=False, kind='Histogram')
    line = IndicatorSpec(name='macdx', overlap=False, kind='Line')
    candle = IndicatorSpec(name='ha', overlap=False, kind='Candlestick')
    assert _pane_zorder(bar) < _pane_zorder(line)
    assert _pane_zorder(bar) < _pane_zorder(candle)


def test_build_creates_histogram_first(headless):
    """★ 回归：``IndicatorManager.build`` 里第一个建出来的必须是**柱体** ✓"""
    import minibt.btplot as btp
    from minibt import LocalDatas
    from minibt.utils import Config
    from minibt.strategy.realtime import RealtimeChart

    k = LocalDatas.test.kline
    ind = k.close.macd()
    strat = btp._make_step_strategy(k, [ind], Config(theme='dark'), 'X')
    strat._start_strategy_run()
    chart = RealtimeChart([strat], browser=False, realtime=False,
                          bars='chart', theme='dark', info_pages=False)

    specs = [s for s in chart.indicators.specs
             if 'macd' in str(s.source)]
    assert [s.name for s in specs] == ['macdh', 'macdx', 'macds'], \
        [s.name for s in specs]
    assert specs[0].kind == 'Histogram'

    # 实时更新是 zip(series, specs) 同下标 —— 两个列表必须一样长、且顺序一致 ✓
    assert len(chart.indicators.series) == len(chart.indicators.specs)
    assert [s.name for s in chart.indicators.specs] == \
        [s.name for s in specs], 'self.specs 没有跟着排序 ✗'


def test_build_keeps_series_specs_in_sync_after_reorder():
    """源码约束：排序结果必须写回 ``self.specs``（否则 zip 会错位 ✗）"""
    src = _read('minibt', 'strategy', 'realtime.py')
    start = src.index('def build(self, frame: pd.DataFrame')
    body = src[start:start + 900]
    assert 'specs = sorted(specs, key=_pane_zorder)' in body
    assert 'self.specs = specs' in body


def test_signal_manager_align_is_unaffected():
    """信号管理器是独立对象（不参与本次重排 ✓）"""
    from minibt.strategy.realtime import SignalManager

    src = _read('minibt', 'strategy', 'realtime.py')
    start = src.index('class SignalManager')
    body = src[start:start + 400]
    assert 'align' in body


# --------------------------------------------------------------------------- #
# miniqt：同一套要求 ✓
# --------------------------------------------------------------------------- #
def test_miniqt_histogram_first_is_stable():
    """miniqt 的建序列循环也要柱体优先，且**稳定**（同类保持原序 ✓）"""
    from miniqt.app.windows.pylightcharts_window import _histogram_first

    lines = {'macdx': 1, 'macdh': 2, 'macds': 3}
    styles = {'macdx': {'line_dash': 'solid'},
              'macdh': {'line_dash': 'vbar'},
              'macds': {'line_dash': 'solid'}}
    assert [n for n, _ in _histogram_first(lines, styles)] == \
        ['macdh', 'macdx', 'macds']
    # 全是线 → 原序不变 ✓
    assert [n for n, _ in _histogram_first({'a': 1, 'b': 2, 'c': 3}, {})] == \
        ['a', 'b', 'c']
    # 多个柱体 → 也保持原相对顺序 ✓
    two = {'l1': 1, 'h1': 2, 'l2': 3, 'h2': 4}
    st2 = {'h1': {'line_dash': 'vbar'}, 'h2': {'line_dash': 'vbar'}}
    assert [n for n, _ in _histogram_first(two, st2)] == \
        ['h1', 'h2', 'l1', 'l2']


def test_miniqt_uses_histogram_first_in_creation_loop():
    src = _read('miniqt', 'app', 'windows', 'pylightcharts_window.py')
    assert "_histogram_first(\n                            group_info['lines'], styles)" in src
