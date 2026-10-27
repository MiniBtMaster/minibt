"""MultiKernelRegression 主图：与 Pine 一致 —— **一条** ``nrp`` 线 + 逐点配色。

原码：``plot(nrp_sum, "Non Repaint MA", nrp_color)``，其中
``nrp_color := (nrp_sum - nrp_sum[1] > 0) ? bullish_color : bearish_color``。
以前为了做双色把它拆成了 ``nrp_up`` / ``nrp_dn`` 两条线（图上就是两条）。
"""
import pandas as pd


def _rules(ind):
    return list(getattr(ind.plotinfo, 'color_rules', []) or [])


def test_multi_kernel_regression_is_single_line():
    from minibt import LocalDatas
    ind = LocalDatas.test.kline.tradingview.MultiKernelRegression()
    isplot = dict(ind.isplot)
    assert isplot['nrp'] is True, isplot
    assert isplot['nrp_up'] is False, isplot
    assert isplot['nrp_dn'] is False, isplot


def test_multi_kernel_regression_has_slope_color_rule():
    from minibt import LocalDatas
    ind = LocalDatas.test.kline.tradingview.MultiKernelRegression()
    rules = _rules(ind)
    assert rules, '应有一条逐点配色规则'
    rule = rules[0]
    assert rule.get('color') and rule.get('else_color'), rule
    cond = rule.get('condition')
    assert callable(cond), rule
    df = pd.DataFrame({
        'time': pd.date_range('2025-01-01', periods=4, freq='min'),
        'nrp': [1.0, 2.0, 1.0, 3.0]})
    assert list(cond(df)) == [False, True, False, True]


def test_multi_kernel_regression_chart_has_one_ma_line(monkeypatch):
    """图上只有一条 MA 线（不是 nrp_up + nrp_dn 两条）。"""
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
    ind = k.tradingview.MultiKernelRegression()
    strat = btp._make_step_strategy(k, [ind], Config(theme='dark'), 'MKR')
    strat._start_strategy_run()
    stats = rt.extract_minibt_indicators(strat, 0)
    assert 'nrp' in [s.name for s in stats], [s.name for s in stats]
    assert 'nrp_up' not in [s.name for s in stats]
    assert 'nrp_dn' not in [s.name for s in stats]
