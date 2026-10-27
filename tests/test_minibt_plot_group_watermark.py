"""副图分组键（``PlotInfo.source``）+ 水印字号（``WaterMark.font_size``）。

两个历史缺陷：

1. ``PlotInfo.source`` 只有 bokeh 读 —— pylightcharts 建规格时写死
   ``source=key``，用户设了也没用 ✗。现在拆成两层：
   * ``IndicatorSpec.source`` 仍然是**指标登记键**（取数据用）；
   * 新增 ``IndicatorSpec.group`` = ``plotinfo.source`` 优先，否则退回 key
     （**副图分组**用）✓
2. ``WaterMark.font_size`` 没透传 —— ``apply_watermark`` 只发文本，
   字号永远 44 ✗。现在按 K 线上的 ``WaterMark.font_size`` 透传 ✓
"""
import pytest


def _strategy(indicator):
    """用 btplot 的临时策略壳跑一遍，拿到带 `_btindicatordataset` 的策略。"""
    from minibt import LocalDatas
    from minibt.utils import Config
    import minibt.btplot as btp
    k = LocalDatas.test.kline
    strat = btp._make_step_strategy(k, [indicator], Config(theme='dark'), 'GRP')
    strat._start_strategy_run()
    return strat, k


def test_default_group_is_indicator_key():
    """没设 ``plotinfo.source`` → 分组键 == 指标 key（一个指标一个副图）。"""
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    ind = k.macd()
    strat, _ = _strategy(ind)
    specs = rt.extract_minibt_indicators(strat, 0)
    assert specs, '没有拿到规格'
    for spec in specs:
        assert spec.group == spec.source, (spec.name, spec.group, spec.source)


def test_custom_plotinfo_source_becomes_group():
    """``ind.plotinfo.source = 'shared'`` → 分组键变成 shared，取数据仍按 key。"""
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    ind = k.macd()
    ind.plotinfo.source = 'shared'          # ★ 用户显式指定
    strat, _ = _strategy(ind)
    specs = rt.extract_minibt_indicators(strat, 0)
    assert specs, '没有拿到规格'
    for spec in specs:
        assert spec.group == 'shared', (spec.name, spec.group)
        assert spec.source and spec.source != 'shared', spec.source
        # `_spec_group` 用它做 pane 分组
        assert rt._spec_group(spec) == 'shared'


def test_candle_default_source_is_key():
    """蜡烛型指标默认 ``source=key``（bokeh 靠它复用同名子图），不能被清空。"""
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    ind = k.ha()
    strat, _ = _strategy(ind)
    specs = rt.extract_minibt_indicators(strat, 0)
    candles = [s for s in specs if s.kind == 'Candlestick']
    assert candles, [(s.name, s.kind) for s in specs]
    for spec in candles:
        assert spec.source == 'pta_ha', spec.source
        assert spec.group == 'pta_ha', spec.group


def test_spec_group_falls_back_when_empty():
    import minibt.strategy.realtime as rt
    spec = rt.IndicatorSpec(name='ma', overlap=False, source='pta_ma')
    assert rt._spec_group(spec) == 'pta_ma'
    spec.group = 'shared'
    assert rt._spec_group(spec) == 'shared'


def test_plot_group_ignores_blank_and_non_str():
    import minibt.strategy.realtime as rt
    assert rt._plot_group({'source': ''}, 'key') == 'key'
    assert rt._plot_group({'source': '   '}, 'key') == 'key'
    assert rt._plot_group({'source': None}, 'key') == 'key'
    assert rt._plot_group({}, 'key') == 'key'
    assert rt._plot_group(None, 'key') == 'key'
    assert rt._plot_group({'source': ' shared '}, 'key') == 'shared'


def test_watermark_font_size_from_watermark_object():
    """``kline.watermark = WaterMark('t', 60)`` → 字号 60；字符串 → 默认 44。"""
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas, WaterMark

    k = LocalDatas.test.kline
    # ★ 必须用**策略里那条** K 线（LocalDatas 每次取可能是新对象）
    strat, k = _strategy(k.macd())
    contract = f'{k.symbol}_{k.cycle}'

    # 默认（没设 watermark）→ 44
    assert rt.watermark_font_size(strat, contract) == 44

    # 字符串 → 文本生效、字号默认
    k.watermark = 'hello'
    assert rt.watermark_font_size(strat, contract) == 44

    # WaterMark 对象 → 用它的 font_size
    k.watermark = WaterMark('hello', 60)
    assert rt.watermark_font_size(strat, contract) == 60


def test_apply_watermark_passes_font_size():
    """``apply_watermark`` 把字号透传给 ``chart.watermark``（旧版退回只传文本）。"""
    import minibt.strategy.realtime as rt

    calls = []

    class Chart:
        def watermark(self, text, font_size=44):
            calls.append((text, font_size))

    r = rt.apply_watermark(Chart(), 'hello', 60)
    assert r is None
    assert calls == [('hello', 60)]

    # 没给字号 → 只传文本（走默认形参）
    rt.apply_watermark(Chart(), 'hi')
    assert calls[-1] == ('hi', 44)

    # 空文本 → 什么都不画
    before = len(calls)
    rt.apply_watermark(Chart(), '')
    assert len(calls) == before


def test_apply_watermark_tolerates_old_signature():
    """老版 ``watermark(text)`` 没有 font_size 形参时不能崩。"""
    import minibt.strategy.realtime as rt

    calls = []

    class OldChart:
        def watermark(self, text):
            calls.append(text)

    rt.apply_watermark(OldChart(), 'hello', 60)
    assert calls == ['hello']
