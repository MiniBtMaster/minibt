"""ScalpPro（副图指标）：交易信号 + 信号文本必须在**副图**，不能画到主图。

原码 ``plotshape(..., style=shape.labelup/labeldown, text='Buy'/'Sell')`` 画在
指标自己的 pane；而 ``SignalStyle(..., overlap=True)`` 会让标记跑去**主图**，
且锚点 ``'low'``/``'high'`` 是 K 线价格量纲，和 ``macd``（价格差 × scale）不同量级。
"""
import numpy as np


def _chart(monkeypatch):
    import minibt.strategy.strategy_window as sw
    from pylightcharts.headless import HeadlessChart
    monkeypatch.setattr(
        sw, 'Chart',
        lambda *a, **kw: HeadlessChart(
            **{k: v for k, v in kw.items() if k != 'title'}))
    import minibt.strategy.realtime as rt
    import minibt.btplot as btp
    from minibt import LocalDatas
    from minibt.utils import Config
    k = LocalDatas.test.kline
    ind = k.tradingview.ScalpPro()
    strat = btp._make_step_strategy(k, [ind], Config(theme='dark'), 'ScalpPro')
    strat._start_strategy_run()
    chart = rt.RealtimeChart([strat], browser=False, realtime=False,
                             bars='chart', theme='dark', info_pages=False)
    return rt, strat, chart


def test_scalp_pro_signal_style_not_overlap():
    from minibt import LocalDatas
    ind = LocalDatas.test.kline.tradingview.ScalpPro()
    styles = dict(ind.plotinfo.signalstyle or {})
    assert styles, '应有信号样式'
    for name in ('long_signal', 'short_signal'):
        st = styles[name]
        assert st.overlap is False, (name, st.overlap)
        # 锚点不能用 K 线列（价格量纲），要用指标自己的线
        assert st.key.lower() not in ('low', 'high', 'open', 'close'), (name, st.key)


def test_scalp_pro_signals_route_to_subfigure(monkeypatch):
    rt, strat, chart = _chart(monkeypatch)
    panes = chart.indicators.panes
    assert panes.get('ScalpPro') == 1, panes        # 指标本体在副图 1
    sigs = rt.extract_minibt_signals(strat, 0, panes)
    assert sigs, '应有信号'
    for name, _values, style, anchor, pane in sigs:
        assert pane == 1, (name, pane)              # 信号也去副图
        assert anchor is not None, name             # 锚到指标线（不是 K 线）
        assert getattr(style, 'key', '') in ('macd', 'signal'), (name, style.key)
        arr = np.asarray(anchor, dtype=float)
        assert np.isfinite(arr).any(), name
