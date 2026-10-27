"""BreaksAndRetests：支撑/阻力是**水平线**，换箱处不能有连接线。

原码用 ``box.new(...)`` —— 每个 pivot 一个**独立矩形**（旧 box 右端 = 新 box 左端
= ``bar_index-bb``），两段互不相连。minibt 用阶梯线近似，换箱处必须插入 NaN 断开；
否则图上会出现一条从旧价位斜到新价位的连接线。
"""
import numpy as np


def _segments(values):
    """返回 ``[(start, end), ...]``（连续非 NaN 段）。"""
    fin = np.isfinite(values)
    starts = np.where(fin & ~np.concatenate([[False], fin[:-1]]))[0]
    ends = np.where(fin & ~np.concatenate([fin[1:], [False]]))[0]
    return list(zip(starts.tolist(), ends.tolist()))


def test_breaks_and_retests_levels_are_horizontal():
    from minibt import LocalDatas
    ind = LocalDatas.test.kline.tradingview.BreaksAndRetests()
    for name in ('s_top', 'r_bot'):
        values = np.asarray(ind[name].values, dtype=float)
        segs = _segments(values)
        assert segs, f'{name} 应有水平段'
        for start, end in segs:
            seg = values[start:end + 1]
            assert np.unique(seg).size == 1, \
                f'{name} 第 {start}-{end} 段内出现了值突变（=连接线）'


def test_hema_trend_levels_boxes_are_horizontal_segments():
    """HemaTrendLevels 的支撑/阻力箱（2 支撑 + 2 阻力）也必须是水平段。

    原码每个箱是**独立 box**（最新那个 ``set_right(bar_index)`` 一直延伸，旧的停在
    下一个同类型 box 前一拍、至少 ``left+5``）；用阶梯线近似时要在换箱处 NaN 断开。
    """
    from minibt import LocalDatas
    ind = LocalDatas.test.kline.tradingview.HemaTrendLevels()
    for name in ('bull_box_top', 'bull_box_bottom',
                 'bear_box_top', 'bear_box_bottom'):
        values = np.asarray(ind[name].values, dtype=float)
        segs = _segments(values)
        assert segs, f'{name} 应有水平段'
        for start, end in segs:
            seg = values[start:end + 1]
            assert np.unique(seg).size == 1, \
                f'{name} 第 {start}-{end} 段内出现了值突变（=连接线）'
    # 色带：支撑箱、阻力箱各一条
    bands = [(b.lower, b.upper) for b in (ind.plotinfo.bandstyle or [])]
    assert ('bull_box_bottom', 'bull_box_top') in bands, bands
    assert ('bear_box_bottom', 'bear_box_top') in bands, bands


def test_band_edges_get_hidden_series(monkeypatch):
    """色带的上下沿即使是 `isplot=False` 的“仅数据”列，也必须建（隐藏）序列。

    否则 `apply_bands` 的 `fill_between` 找不到 line —— HemaTrendLevels 的
    支撑/阻力带、均线渐变带之前就因此完全看不见。
    """
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
    ind = k.tradingview.HemaTrendLevels()
    strat = btp._make_step_strategy(k, [ind], Config(theme='dark'), 'HEMA')
    strat._start_strategy_run()
    bands = rt.extract_minibt_bands(strat, 0)
    assert len(bands) == 4, bands
    chart = rt.RealtimeChart([strat], browser=False, realtime=False,
                             bars='chart', theme='dark', info_pages=False)
    for band in bands:
        assert chart.indicators.series_named(band['source'], band['lower']), band
        assert chart.indicators.series_named(band['source'], band['upper']), band
    scripts = '\n'.join(getattr(chart.chart, '_scripts', []) or [])
    assert scripts.count('LineFill') >= 4, scripts.count('LineFill')


def test_histogram_vbar_base_sent_to_series(monkeypatch):
    """`LineStyle.vbar_base` 要作为 Histogram 的 `base` 选项下发。

    以前 `vbar_base` 只用于“值 vs 基线”判上下行分色、没传给序列，所以柱子
    永远从 0 起（MarketStructureOscillator 的 `cycle` 应绕 50 振荡）。
    """
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
    ind = k.tradingview.MarketStructureOscillator()
    strat = btp._make_step_strategy(k, [ind], Config(theme='dark'), 'MSO')
    strat._start_strategy_run()
    specs = {s.name: s for s in rt.extract_minibt_indicators(strat, 0)}
    assert specs['cycle'].kind == 'Histogram', specs['cycle'].kind
    assert float(specs['cycle'].vbar_base) == 50.0, specs['cycle'].vbar_base
    chart = rt.RealtimeChart([strat], browser=False, realtime=False,
                             bars='chart', theme='dark', info_pages=False)
    scripts = '\n'.join(getattr(chart.chart, '_scripts', []) or [])
    assert '"base":50.0' in scripts, scripts[-400:]
