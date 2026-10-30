"""pylightcharts 的**蜡烛副图**（``category='candles'``）。

历史 bug：``extract_minibt_indicators`` 里对 ``iscandles`` 直接 ``continue``
（"蜡烛图类指标先跳过"），于是 pylightcharts 下蜡烛副图**整条不画**（bokeh 正常）。
现在改为：前 4 条（open/high/low/close）出一条 ``Candlestick``，同一指标里其余
可画线（CDV 的 ``ctl`` / ``sma1`` / ``sma2`` / ``ema1`` / ``ema2``）按同一个
``overlap``/``source`` 追加 —— 副图蜡烛时它们靠 ``source`` 落到**同一个副图**。
"""
import numpy as np
import pytest


@pytest.fixture()
def headless(monkeypatch):
    """把 StrategyWindow 的 Chart 换成 HeadlessChart（不出窗口）。"""
    import minibt.strategy.strategy_window as sw
    from pylightcharts.headless import HeadlessChart
    monkeypatch.setattr(
        sw, 'Chart',
        lambda *a, **kw: HeadlessChart(
            **{k: v for k, v in kw.items() if k != 'title'}))
    return sw


def _make(strategy_cls, indicator):
    from minibt import LocalDatas
    from minibt.utils import Config
    import minibt.btplot as btp
    k = LocalDatas.test.kline
    strat = btp._make_step_strategy(k, [indicator], Config(theme='dark'),
                                    'CDV')
    strat._start_strategy_run()
    return strat


def test_cdv_subfigure_has_candlestick_and_ma_lines(headless):
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    ind = k.tradingview.CumulativeDeltaVolume(
        showma1=True, showma2=True, showema1=True, showema2=True)
    strat = _make(None, ind)

    specs = rt.extract_minibt_indicators(strat, 0)
    kinds = {s.name: (s.kind, s.overlap) for s in specs}
    assert kinds.get('CumulativeDeltaVolume') == ('Candlestick', False), kinds
    for name in ('ctl', 'sma1', 'sma2', 'ema1', 'ema2'):
        assert name in kinds, (name, list(kinds))
        assert kinds[name][0] == 'Line', kinds[name]
        assert kinds[name][1] is False, kinds[name]

    chart = rt.RealtimeChart([strat], browser=False, realtime=False,
                             bars='chart', theme='dark', info_pages=False)
    # 主图 + 蜡烛副图 = 2 个 pane
    assert chart.chart.pane_count() == 2, chart.chart.pane_count()
    names = [getattr(s, 'name', '?') for s in chart.chart.lines()]
    assert 'CumulativeDeltaVolume' in names, names
    for name in ('sma1', 'sma2', 'ema1', 'ema2'):
        assert name in names, names


def test_cdv_line_mode_has_ctl_line(headless):
    """``style='Line'``：``ctl`` 有线；蜡烛 OHLC 全 NaN（渲染不出蜡烛）。"""
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    ind = k.tradingview.CumulativeDeltaVolume(style='Line')
    strat = _make(None, ind)
    specs = rt.extract_minibt_indicators(strat, 0)
    by_name = {s.name: s for s in specs}
    assert 'ctl' in by_name and by_name['ctl'].kind == 'Line', list(by_name)
    cand = by_name.get('CumulativeDeltaVolume')
    if cand is not None:
        assert cand.kind == 'Candlestick'
        for key in ('open', 'high', 'low', 'close'):
            arr = np.asarray(cand.ohlc[key], dtype=float)
            assert not np.isfinite(arr).any(), (key, arr[:5])


def test_candlestick_indicator_pushes_ohlc_on_update_last():
    """蜡烛型副图（ha / CDV）实时更新要推 **OHLC**。

    历史 bug：``IndicatorManager.update_last`` 给**所有**序列都推单值
    ``{'time', 'value'}``，而 ``Candlestick`` 引擎收不到 ``value`` ——
    于是副图蜡烛从打开那一刻起就**永远不更新** ✗（用户反馈 ``ha`` 不刷新）。
    """
    import pandas as pd
    from minibt.strategy.realtime import IndicatorManager, IndicatorSpec

    class FakeChart:
        candle_data = pd.DataFrame({
            'time': [10, 20, 30],
            'open': [1.0, 2.0, 3.0], 'high': [1.0, 2.0, 3.0],
            'low': [1.0, 2.0, 3.0], 'close': [1.0, 2.0, 3.0],
        })

    class FakeSeries:
        def __init__(self):
            self.points = []

        def update(self, row):
            self.points.append(dict(row))

    manager = IndicatorManager(FakeChart())
    spec = IndicatorSpec(
        name='ha', overlap=False, kind='Candlestick', source='pta_ha',
        ohlc={'open': np.array([1.0, 2.0, 3.0]),
              'high': np.array([1.0, 2.0, 3.0]),
              'low': np.array([1.0, 2.0, 3.0]),
              'close': np.array([1.0, 2.0, 3.0])})
    series = FakeSeries()
    manager.specs.append(spec)
    manager.series.append(series)

    manager.update_last(30, offset=0)          # 最新一根
    assert series.points, '蜡烛型指标没有更新'
    point = series.points[-1]
    assert point['time'] == 30
    assert (point['open'], point['high'], point['low'], point['close']) == (
        3.0, 3.0, 3.0, 3.0)
    assert 'value' not in point                # 不能再推单值 ✗

    # 换根回填上一根：时间 = ``when``（当前这根），值取 ``-1-offset``
    # （不能拿 chart.candle_data 反查 —— 那样时间会倒退，引擎报
    #  “Cannot update oldest data” ✗）
    manager.update_last(20, offset=1)
    assert series.points[-1]['time'] == 20
    assert series.points[-1]['close'] == 2.0

    # ``get_ohlc`` 返回 **DataFrame** 时不能用 ``if not ohlc``（歧义）✗
    spec.get_ohlc = lambda: pd.DataFrame({
        'open': [1.0, 2.0, 4.0], 'high': [1.0, 2.0, 4.0],
        'low': [1.0, 2.0, 4.0], 'close': [1.0, 2.0, 4.0]})
    manager.update_last(30, offset=0)
    assert series.points[-1]['close'] == 4.0
