"""指标标签齿轮菜单 + 单行图例 + 收起按钮（minibt 复刻 miniqt）。

覆盖：
* ``minibt/strategy/indicator_menu.py`` 的纯函数（配置/写回/覆盖）；
* 两条渲染路径的接线（源码约束）；
* JS bundle 里确实带了新功能（齿轮菜单 / 收起 / 单行图例）。
"""
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


def _read(*parts):
    return (REPO.joinpath(*parts)).read_text(encoding='utf-8')


# --------------------------------------------------------------------------- #
# 纯函数
# --------------------------------------------------------------------------- #
def test_build_config_from_spec():
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im

    spec = SimpleNamespace(
        name='macd', source='macd', kind='Line', line_style='dashed',
        line_width=3, color='#2196f3', price_line=True, price_label=False,
        menu_params=[{'name': 'fast', 'value': 12, 'type': 'int'}])
    config = im.build_config(spec)
    assert config['title'] == 'macd指标参数'
    assert config['lineStyle'] == 'dashed'
    assert config['lineWidth'] == 3
    assert config['lineColor'] == '#2196f3'
    assert config['priceLine'] is True
    assert config['params'][0]['name'] == 'fast'
    assert config['showStyle'] is True
    # 中文菜单文案（与 miniqt 卡片一致）
    assert config['labels']['params'] == '参数'
    assert config['labels']['color'] == '线颜色'


def test_line_style_defaults_price_visible():
    """``LineStyle(...)`` 没写 price_line/price_label 时，默认也是 True ✓。

    这是 01_plotinfo_overview.py 这类教程/策略的实际默认来源（不是
    ``IndicatorSpec`` 的字段）—— 之前这里写死 False，菜单才显示“关”✗。
    """
    from minibt.utils import LineStyle

    style = LineStyle(line_color='orange', line_width=2)
    assert style.price_line is True
    assert style.price_label is True


def test_build_config_defaults_price_visible_when_spec_omits_it():
    """spec 没写 price_line/price_label 时，菜单默认**勾选**价格线 / 价格标签 ✓。"""
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im

    spec = SimpleNamespace(name='ma', kind='Line', line_style='solid',
                           line_width=2, color='#ffffff')
    config = im.build_config(spec)
    assert config['priceLine'] is True
    assert config['priceLabel'] is True


def test_build_config_histogram_hides_line_style():
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im

    spec = SimpleNamespace(name='v', source='s', kind='Histogram',
                           line_style='vbar', line_width=1, color=None)
    config = im.build_config(spec)
    assert config['showStyle'] is False
    assert config['lineStyle'] == 'solid'          # 柱体没有 lineStyle


def test_normalize_style():
    from minibt.strategy import indicator_menu as im

    assert im.normalize_style('dotted', 'Line') == 'dotted'
    assert im.normalize_style('vbar', 'Line') == 'solid'
    assert im.normalize_style('dashed', 'Histogram') == 'solid'


def test_apply_visual_writes_back():
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im

    spec = SimpleNamespace(name='a', source='s', kind='Line',
                           line_style='solid', line_width=2, color='#fff',
                           palette_color=True, price_line=False,
                           price_label=False)
    assert im.apply_visual(spec, 'style', {'value': 'dotted'}) is True
    assert spec.line_style == 'dotted'
    assert im.apply_visual(spec, 'width', {'value': 5}) is True
    assert spec.line_width == 5
    assert im.apply_visual(spec, 'color', {'value': '#f23645'}) is True
    assert spec.color == '#f23645' and spec.palette_color is False
    assert im.apply_visual(spec, 'price',
                           {'priceLine': True, 'priceLabel': True}) is True
    assert spec.price_line is True and spec.price_label is True
    # 参数不属于视觉设置 → False（交给重算回调）
    assert im.apply_visual(spec, 'params', {'values': {}}) is False


def test_override_round_trip_survives_rebuild():
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im

    old = SimpleNamespace(name='a', source='s', kind='Line',
                          line_style='solid', line_width=2, color='#fff',
                          palette_color=True, price_line=False,
                          price_label=False)
    overrides = {}
    values = im.override_values(old, 'style', {'value': 'dashed'})
    overrides.setdefault(im.override_key(old), {}).update(values)
    values = im.override_values(old, 'color', {'value': '#f23645'})
    overrides.setdefault(im.override_key(old), {}).update(values)

    fresh = SimpleNamespace(name='a', source='s', kind='Line',
                            line_style='solid', line_width=2, color='#fff',
                            palette_color=True, price_line=False,
                            price_label=False)
    im.apply_overrides(fresh, overrides)
    assert fresh.line_style == 'dashed'
    assert fresh.color == '#f23645'
    assert fresh.palette_color is False


def test_enable_menu_and_collapse_are_safe_without_api():
    from minibt.strategy import indicator_menu as im

    assert im.enable_menu(object(), {}, lambda *a: None) is False
    im.pin_row(object())          # 不抛
    im.enable_collapse(object())  # 不抛


# --------------------------------------------------------------------------- #
# 源码接线
# --------------------------------------------------------------------------- #
def test_pylightcharts_exposes_menu_and_collapse():
    source = _read('pylightcharts', 'abstract.py')
    assert 'def enable_legend_menu' in source
    assert 'addSettingsMenu' in source
    assert 'def enable_legend_collapse' in source
    assert 'legend.enableCollapse' in source
    assert 'indicator_menu{self._chart.id}' in source


def test_bundle_has_new_legend_features():
    bundle = _read('pylightcharts', 'js', 'bundle.js')
    assert 'addSettingsMenu' in bundle
    assert 'enableCollapse' in bundle
    assert 'legend-menu' in bundle
    assert 'legend-collapse' in bundle
    # 单行图例：不再用 <br>V 换行，并且有时间格式化
    assert '<br>V ' not in bundle
    assert 'legendTimeFormat' in bundle


def test_realtime_wires_menu_and_collapse():
    source = _read('minibt', 'strategy', 'realtime.py')
    assert 'menu_params' in source
    assert 'style_overrides' in source
    assert 'def _wire_menu' in source
    assert 'def _on_menu' in source
    assert 'indicator_menu.enable_collapse' in source
    assert 'indicator_menu.apply_overrides' in source


def test_light_chart_wires_menu_and_collapse():
    source = _read('minibt', 'strategy', 'light_chart.py')
    assert 'def _wire_indicator_menus' in source
    assert 'indicator_menu.enable_collapse' in source
    assert 'indicator_menu.enable_menu' in source


def test_replay_window_wires_collapse():
    """回放路径也要挂收起/展开按钮（以前只建图例行 + 眼睛，用户反馈 ✗）。"""
    source = _read('minibt', 'strategy', 'replay_window.py')
    assert 'indicator_menu.enable_collapse' in source


def test_js_legend_one_line_readout():
    source = _read('jslib', 'src', 'general', 'legend.ts')
    assert 'legendTimeFormat' in source
    assert '<br>V ' not in source
    assert 'addSettingsMenu' in source
    assert 'enableCollapse' in source


def test_js_menu_has_two_level_groups():
    source = _read('jslib', 'src', 'general', 'legend-menu.ts')
    for key in ('params', 'style', 'width', 'color', 'other'):
        assert f"['{key}'" in source
    assert 'legend-menu-sub' in source      # 二级菜单 flyout


@pytest.mark.parametrize('name', ['solid', 'dotted', 'dashed',
                                  'large_dashed', 'sparse_dotted'])
def test_line_styles_match_miniqt(name):
    from minibt.strategy import indicator_menu as im

    assert name in im.LINE_STYLES


# --------------------------------------------------------------------------- #
# 真实指标：参数提取 + 重算
# --------------------------------------------------------------------------- #
def test_params_and_recompute_with_real_indicator():
    import numpy as np

    from minibt import LocalDatas
    from minibt.strategy import indicator_menu as im

    k = LocalDatas.test.kline
    ind = k.tradingview.CumulativeDeltaVolume(showma1=True, showma2=True)
    params = im.params_for_dataset(ind)
    names = {p['name'] for p in params}
    assert 'showma1' in names, names
    assert all(set(p) == {'name', 'value', 'type', 'readonly'} for p in params)

    values = {p['name']: p['value'] for p in params}
    values['showma1'] = False
    new = im.recompute_indicator(ind, values)
    assert new is not None
    before = ind.pandas_object.fillna(0).to_numpy()
    after = new.pandas_object.fillna(0).to_numpy()
    assert before.shape == after.shape
    assert np.isfinite(after).any()
    assert (before != after).any()          # 新参数确实改变了数值


def test_recompute_returns_none_without_meta():
    from minibt.strategy import indicator_menu as im

    assert im.recompute_indicator(object(), {'a': 1}) is None


def test_recompute_preserves_id():
    from minibt import LocalDatas
    from minibt.strategy import indicator_menu as im

    k = LocalDatas.test.kline
    ind = k.tradingview.CumulativeDeltaVolume(showma1=True)
    new = im.recompute_indicator(ind, {'showma1': False})
    assert new is not None
    assert new.id == ind.id          # 沿用旧 id ✓
    assert new.pandas_object.shape == ind.pandas_object.shape


def test_recompute_meta_default_on_and_switchable():
    """``_bt_recompute`` 默认挂（参数页需要）；可全局关掉（零开销）✓。"""
    from minibt import LocalDatas
    from minibt.indicators import base as base_mod

    try:
        assert base_mod.RECOMPUTE_META is True
        k = LocalDatas.test.kline
        ind = k.tradingview.CumulativeDeltaVolume(showma1=True)
        assert isinstance(getattr(ind, '_bt_recompute', None), dict)

        base_mod.enable_recompute_meta(False)
        ind2 = k.tradingview.CumulativeDeltaVolume(showma2=True)
        assert getattr(ind2, '_bt_recompute', None) is None
    finally:
        base_mod.enable_recompute_meta(True)


def test_library_indicator_params_from_call():
    """库函数指标（``data.sma``）没有 ``params``，参数从原始调用取 ✓。"""
    from minibt import LocalDatas
    from minibt.strategy import indicator_menu as im

    k = LocalDatas.test.kline
    ind = k.sma(length=20)
    params = im.params_for_dataset(ind)
    names = {p['name'] for p in params}
    assert 'length' in names, names
    length = next(p for p in params if p['name'] == 'length')
    assert length['value'] == 20


def test_smt_param_change_reruns_wrapper_and_keeps_object_params():
    """★ 回归：改参数后必须**重跑 wrapper**，且对比合约对象不能被字符串覆盖。

    以前 ``recompute_indicator`` 直接构造 ``SMTDivergences`` 类（绕过
    ``kline.tradingview.SMTDivergences`` wrapper）→ 退回类上的**静态**
    ``isplot``（``pivot_high=True``）：改个 ``length`` 就把本该隐藏的 Swing
    高低点虚线又画了出来，同时菜单回传的 ``str(kline)`` 把 ``sym1`` 弄丢 →
    背离线全没了 ✗✗
    """
    from minibt import LocalDatas
    from minibt.strategy import indicator_menu as im

    k = LocalDatas.test.kline
    sym = LocalDatas.test.kline
    ind = k.tradingview.SMTDivergences(sym1=sym)
    assert ind.isplot['pivot_high'] is False        # 有对比合约 → pivot 不画 ✓
    assert ind.isplot['div_high'] is True

    # 模拟菜单回传：全部参数都变成字符串（sym1 是 DataFrame 的 repr）
    payload = {p['name']: p['value'] for p in im.params_for_dataset(ind)}
    payload['length'] = '5'

    new = im.recompute_indicator(ind, payload)
    assert new is not None
    assert new.params['sym1'] is sym, 'sym1 被字符串覆盖了 ✗'
    assert new.params['length'] == 5
    assert new.isplot['pivot_high'] is False, new.isplot
    assert new.isplot['pivot_low'] is False, new.isplot
    # 再把 use_sym1 关掉：wrapper 重跑 → has_sym=False → pivot 重新画出来 ✓
    # （证明 wrapper 真的按新参数重算了，而不是套用类上的静态 isplot）
    off = im.recompute_indicator(ind, {'use_sym1': 'false'})
    assert off is not None
    assert off.isplot['pivot_high'] is True, off.isplot
    assert off.params['sym1'] is sym           # 即使关掉 use_sym1，sym1 也没被毁 ✓


def test_params_for_dataset_marks_objects_readonly():
    from minibt import LocalDatas
    from minibt.strategy import indicator_menu as im

    k = LocalDatas.test.kline
    sym = LocalDatas.test.kline
    ind = k.tradingview.SMTDivergences(sym1=sym)
    rows = {r['name']: r for r in im.params_for_dataset(ind)}
    assert rows['sym1']['readonly'] is True
    assert 'KLine' in str(rows['sym1']['value'])     # 不塞 DataFrame repr ✓
    assert rows['length']['readonly'] is False
    assert rows['use_sym1']['readonly'] is False


def test_raw_params_keeps_objects():
    from minibt import LocalDatas
    from minibt.strategy import indicator_menu as im

    k = LocalDatas.test.kline
    sym = LocalDatas.test.kline
    ind = k.tradingview.SMTDivergences(sym1=sym)
    raw = im.raw_params(ind)
    assert raw['sym1'] is sym
    assert raw['length'] == 3


def test_sanitize_params_only_scalars_and_types():
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im

    obj = object()
    ds = SimpleNamespace(params={
        'int_p': 1, 'float_p': 2.5, 'bool_p': True, 'str_p': 'x',
        'none_p': None, 'obj_p': obj, '_hidden': 9,
    })
    out = im.sanitize_params(ds, {
        'int_p': '7', 'float_p': '1.25', 'bool_p': 'false', 'str_p': 'y',
        'none_p': '', 'obj_p': 'garbage', 'unknown': 1, '_hidden': '5',
    })
    assert out == {'int_p': 7, 'float_p': 1.25, 'bool_p': False, 'str_p': 'y'}
    assert out['bool_p'] is False
    # None 原值：只有填了新内容才接受 ✓
    assert im.sanitize_params(ds, {'none_p': 'close'}) == {'none_p': 'close'}


def test_params_equal_object_identity():
    from minibt.strategy import indicator_menu as im

    obj = object()
    assert im.params_equal({'a': obj, 'b': 1}, {'a': obj, 'b': 1}) is True
    assert im.params_equal({'a': obj}, {'a': object()}) is False


def test_class_path_fallback_when_no_accessor():
    """找不到 wrapper 时回退到直接构造类（仍然能用 ✓）。"""
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im

    class _Ind:
        def __init__(self, source, **params):
            self.source = source
            self.params = params
            self.isplot = {'a': True}
            self.id = 7

    source = object()
    ds = SimpleNamespace(
        _bt_indicator_cls=_Ind, sname='NopeIndicator', params={'a': 1},
        _dataset=SimpleNamespace(source_object=source),
        _bt_recompute=None)
    new = im.recompute_indicator(ds, {'a': '2'})
    assert new is not None and new.params == {'a': 2} and new.id == 7


def test_js_menu_marks_readonly_params():
    bundle = _read('pylightcharts', 'js', 'bundle.js')
    assert 'is-readonly' in bundle
    assert '不可编辑' in bundle
    css = _read('pylightcharts', 'js', 'styles.css')
    assert 'legend-menu-param-row.is-readonly' in css


def test_config_gate_default_on():
    from minibt.utils import Config, resolve_indicator_recompute

    assert resolve_indicator_recompute(None) is False
    cfg = Config()
    assert cfg.indicator_recompute is True        # minibt 默认**开**（参数页可见）✓

    class _S:
        pass

    strategy = _S()
    strategy.config = cfg
    assert resolve_indicator_recompute(strategy) is True
    cfg.indicator_recompute = False
    assert resolve_indicator_recompute(strategy) is False


# --------------------------------------------------------------------------- #
# 端到端（headless 图表）：config 开关 → 参数页 / 重算重建
# --------------------------------------------------------------------------- #
@pytest.fixture()
def headless(monkeypatch):
    import minibt.strategy.strategy_window as sw
    from pylightcharts.headless import HeadlessChart

    monkeypatch.setattr(
        sw, 'Chart',
        lambda *a, **kw: HeadlessChart(
            **{k: v for k, v in kw.items() if k != 'title'}))
    return sw


def _make_strategy(config):
    import minibt.btplot as btp
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    ind = k.tradingview.CumulativeDeltaVolume(showma1=True, showma2=True)
    return btp._make_step_strategy(k, [ind], config, 'CDV')


def _build_chart(strategy):
    import minibt.strategy.realtime as rt

    return rt.RealtimeChart([strategy], browser=False, realtime=False,
                            bars='chart', theme='dark', info_pages=False)


def test_recompute_on_populates_params_and_rebuilds(headless):
    from minibt.utils import Config

    strat = _make_strategy(Config(theme='dark', indicator_recompute=True))
    strat._start_strategy_run()
    chart = _build_chart(strat)
    spec = next(s for s in chart.indicators.specs
                if s.source == 'CumulativeDeltaVolume')
    assert spec.menu_params, '开启时菜单应带参数页数据'
    chart._on_indicator_params(spec, {'showma1': False})
    dataset = strat._btindicatordataset['CumulativeDeltaVolume']
    assert dataset.params['showma1'] is False
    # 重算后图表仍有序列（没崩）
    assert chart.chart.lines()


def test_recompute_off_hides_params(headless):
    from minibt.utils import Config

    strat = _make_strategy(Config(theme='dark', indicator_recompute=False))
    strat._start_strategy_run()
    chart = _build_chart(strat)
    specs = chart.indicators.specs
    assert specs
    assert all(not s.menu_params for s in specs), '关闭时不应出现参数页'


def test_recompute_on_all_indicators_get_params(headless):
    """开启时**所有**指标（含库函数指标）都有参数页 ✓。"""
    import minibt.btplot as btp
    from minibt import LocalDatas
    from minibt.utils import Config

    k = LocalDatas.test.kline
    ind1 = k.tradingview.CumulativeDeltaVolume(showma1=True)
    ind2 = k.sma(length=20)
    strat = btp._make_step_strategy(
        k, [ind1, ind2], Config(theme='dark', indicator_recompute=True), 'X')
    strat._start_strategy_run()
    chart = _build_chart(strat)
    sources = {s.source for s in chart.indicators.specs if s.menu_params}
    assert 'CumulativeDeltaVolume' in sources
    assert 'pta_sma' in sources, sources


def test_param_override_survives_rebuild(headless):
    """用户改的参数跨「策略重建」保留（实盘每拍会用原参数重建 ✓）。"""
    from minibt.utils import Config

    strat = _make_strategy(Config(theme='dark', indicator_recompute=True))
    strat._start_strategy_run()
    chart = _build_chart(strat)
    spec = next(s for s in chart.indicators.specs
                if s.source == 'CumulativeDeltaVolume')
    chart._on_indicator_params(spec, {'showma1': False})
    assert strat._btindicatordataset['CumulativeDeltaVolume'].params['showma1'] is False

    # 模拟实盘：策略用**原始参数**重建指标
    datasets = strat._btindicatordataset
    old = datasets['CumulativeDeltaVolume']
    cls, src = old._bt_indicator_cls, old._dataset.source_object
    original = dict(old.params)
    original['showma1'] = True
    datasets.add_data('CumulativeDeltaVolume', cls(src, **original))
    assert datasets['CumulativeDeltaVolume'].params['showma1'] is True

    # 重建图表 → 覆盖重新套用
    chart._rebuild_indicators(fit=False)
    assert datasets['CumulativeDeltaVolume'].params['showma1'] is False


def test_strategy_object_param_survives_recompute(headless):
    """★ 用户场景：**策略里** ``self.kline.tradingview.SMTDivergences(sym1=...)``
    改参数（length 3→5）后，对比合约与绘图开关都必须保持原样 ✓。

    这是 ``指标重载后.png`` 的完整端到端回归：走策略 → 图例「参数」页确认 →
    ``RealtimeChart._on_indicator_params`` → ``recompute_indicator``。
    """
    import minibt.btplot as btp
    from minibt import LocalDatas
    from minibt.utils import Config

    k = LocalDatas.test.kline
    sym = LocalDatas.test.kline
    ind = k.tradingview.SMTDivergences(sym1=sym)
    strat = btp._make_step_strategy(
        k, [ind], Config(theme='dark', indicator_recompute=True), 'SMT')
    strat._start_strategy_run()
    chart = _build_chart(strat)
    spec = next(s for s in chart.indicators.specs
                if s.source == 'SMTDivergences')
    rows = {p['name']: p for p in spec.menu_params}
    assert rows['sym1']['readonly'] is True, rows['sym1']
    assert rows['length']['readonly'] is False

    before = len(list(strat._btindicatordataset))
    chart._on_indicator_params(
        spec, {p['name']: p['value'] for p in spec.menu_params}
        | {'length': '5'})
    dataset = strat._btindicatordataset['SMTDivergences']
    assert dataset.params['length'] == 5
    assert dataset.params['sym1'] is sym, '对比合约被菜单回传的字符串毁了 ✗'
    assert dataset.isplot['pivot_high'] is False, dataset.isplot
    assert dataset.isplot['div_high'] is True
    # 重算不应额外注册一份指标（防 wrapper 重复登记 ✗）
    assert len(list(strat._btindicatordataset)) == before
    assert chart.chart.lines()


def test_recompute_keeps_vbar_style_and_positional_params():
    """★ 回归（用户 ``cci.py`` 的 RSI）：``line_style = LineStyle(vbar, base=50)``
    必须跨重算保留；同时 ``k.close.sma(30)`` 这种**按位置**传参不能因重复 kwargs
    而静默失败 ✗。
    """
    from minibt import LineDash, LineStyle, LocalDatas
    from minibt.strategy import indicator_menu as im

    k = LocalDatas.test.kline
    rsi = k.close.rsi()
    rsi.line_style = LineStyle(line_dash=LineDash.vbar, vbar_base=50.)
    new = im.recompute_indicator(rsi, {'length': '7'})
    assert new is not None
    style = new._plotinfo.linestyle['pta_rsi']
    assert style.line_dash == LineDash.vbar, style
    assert style.vbar_base == 50., style

    # 按位置传参的库指标：以前 ``wrapper(*call_args, length=42)`` 会
    # ``got multiple values for argument 'length'`` → 静默返回 None ✗
    ma = k.close.sma(30)
    ma.line_style = LineStyle(line_dash=LineDash.dashdot, line_width=3)
    new_ma = im.recompute_indicator(ma, {'length': '42'})
    assert new_ma is not None, '按位置传参的指标重算失败了 ✗'
    sma_style = new_ma._plotinfo.linestyle['pta_sma']
    assert sma_style.line_dash == LineDash.dashdot
    assert sma_style.line_width == 3

    # kwargs 形式也不能坏
    assert im.recompute_indicator(k.close.sma(length=20),
                                  {'length': '9'}) is not None


def test_recompute_keeps_span_band_and_linestyle():
    """PlotInfo 的 span / band / linestyle 都要跨重算保留 ✓（不止 linestyle）。"""
    from minibt import BandStyle, LineDash, LineStyle, LocalDatas, SpanStyle
    from minibt.strategy import indicator_menu as im

    k = LocalDatas.test.kline
    sym = LocalDatas.test.kline
    ind = k.tradingview.SMTDivergences(sym1=sym)
    ind.span_style += [SpanStyle(0), SpanStyle(-100)]
    ind.bandstyle += BandStyle('div_high', 'div_low', fill_color='#ff0000',
                               fill_alpha=0.3)
    ind.line_style = LineStyle(line_dash=LineDash.dashdot, line_width=4)
    new = im.recompute_indicator(ind, {'length': '5'})
    assert new is not None
    assert len(new._plotinfo.spanstyle) >= 2
    assert len(new._plotinfo.bandstyle) >= 1
    style = new._plotinfo.linestyle['div_high']
    assert style.line_dash == LineDash.dashdot
    assert style.line_width == 4
    # 参数驱动的绘图开关仍按**新参数**重算（不被旧值冻结 ✓）
    assert new.isplot['pivot_high'] is False, new.isplot


def test_recompute_keeps_color_rules():
    from minibt import Colors, LocalDatas
    from minibt.strategy import indicator_menu as im

    k = LocalDatas.test.kline
    ma = k.close.sma(30)
    ma.color_by(ma.diff() > 0, Colors.orange)
    assert len(ma._plotinfo.color_rules) == 1
    new = im.recompute_indicator(ma, {'length': '42'})
    assert new is not None
    assert len(new._plotinfo.color_rules) == 1


def test_style_delta_ignores_param_driven_styles():
    """基座 = 同参数新建 → 参数驱动的样式**不算** delta（改颜色参数仍生效 ✓）。"""
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im

    def _obj(linestyle, spanstyle):
        return SimpleNamespace(
            _plotinfo=SimpleNamespace(linestyle=linestyle, spanstyle=spanstyle))

    base = _obj({'a': 1}, [1])
    assert im.style_delta(_obj({'a': 1}, [1]), base) == {}
    assert im.style_delta(_obj({'a': 2}, [1, 3]), base) == {
        'linestyle': {'a': 2}, 'spanstyle': [3]}


def test_realtime_rebuild_reapplies_all_plotinfo_styles():
    """重算后 pylightcharts 侧的样式落地要**全套**重来（span/band/table/watermark…）✓"""
    src = _read('minibt', 'strategy', 'realtime.py')
    for call in ('apply_bands(', 'apply_spans(', 'apply_color_rules(',
                 'apply_indicator_tables(', 'apply_watermark(',
                 'apply_candlestyle(', 'apply_histogram_colors(',
                 'self.signal_manager.build('):
        assert call in src, call


def test_strategy_vbar_style_survives_param_change(headless):
    """★ 用户 ``cci.py`` 完整场景：策略里 ``self.rsi.line_style =
    LineStyle(line_dash=LineDash.vbar, vbar_base=50.)`` —— 改参数重载后仍然是
    **柱体**（``kind='Histogram'`` / ``line_style='vbar'``），不是普通实线 ✓。
    """
    import minibt.btplot as btp
    from minibt import LineDash, LineStyle, LocalDatas
    from minibt.utils import Config

    k = LocalDatas.test.kline
    rsi = k.close.rsi()
    rsi.line_style = LineStyle(line_dash=LineDash.vbar, vbar_base=50.)
    strat = btp._make_step_strategy(
        k, [rsi], Config(theme='dark', indicator_recompute=True), 'RSI')
    strat._start_strategy_run()
    chart = _build_chart(strat)

    def _spec():
        return next(s for s in chart.indicators.specs
                    if s.source == 'pta_rsi')

    assert _spec().kind == 'Histogram', _spec().kind
    assert _spec().line_style == 'vbar'
    chart._on_indicator_params(_spec(), {'length': '7'})
    again = _spec()
    assert again.kind == 'Histogram', '重载后柱体退化成实线了 ✗'
    assert again.line_style == 'vbar', again.line_style


def test_replay_hides_indicator_gear():
    """★ 回放里**所有合约**的指标行不挂图例齿轮（参数不能改）✓。

    回测结果是按当前指标参数跑出来的，回放图里改参数没有意义（录好的信号 /
    成交对不上 ✗）。图例行 + 眼睛（显/隐）开关仍然保留 ✓。
    """
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im
    from minibt.strategy.realtime import IndicatorManager

    class _Series:
        def __init__(self):
            self.pinned = None
            self.menu = None

        def pin_legend_row(self, value=True):
            self.pinned = value

        def enable_legend_menu(self, *args):
            self.menu = args

    spec = SimpleNamespace(
        name='rsi', source='rsi', kind='Line', line_style='solid',
        line_width=2, color='#ffffff', price_line=False, price_label=False,
        menu_params=None)
    chart = SimpleNamespace()

    live = IndicatorManager(chart)
    assert live.legend_menu is True
    series = _Series()
    live._wire_menu(spec, series, True)
    assert series.pinned is True
    assert series.menu is not None        # 实盘 / btplot：有齿轮 ✓

    replay = IndicatorManager(chart, legend_menu=False)
    assert replay.legend_menu is False
    series2 = _Series()
    replay._wire_menu(spec, series2, True)
    assert series2.pinned is True         # 图例行仍固定显示 ✓
    assert series2.menu is None, '回放里不该挂齿轮菜单 ✗'

    # 没有图例的线本来就不挂（行为不变 ✓）
    series3 = _Series()
    replay._wire_menu(spec, series3, False)
    assert series3.pinned is None and series3.menu is None


def test_replay_window_disables_legend_menu():
    """``Bt(replay=True)`` 默认走 ``ReplayWindow`` → 必须显式关掉齿轮 ✓"""
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im

    src = _read('minibt', 'strategy', 'replay_window.py')
    assert 'legend_menu=False' in src
    # btplot / 回测展示仍然保留齿轮（用户要靠它改参数 ✓）
    rt = _read('minibt', 'strategy', 'realtime.py')
    assert 'IndicatorManager(self.chart)' in rt


def test_legend_supports_per_line_forms():
    """``legend`` 支持 bool / dict（按**线名**）/ list（按**线序**）—— 与 ``isplot`` 同形 ✓。

    用户 ``cci.py`` 里写 ``legend = False`` 会**整个指标**都不建图例行（只画线），
    想只藏零轴那一行就写 ``legend = dict(zero=False)`` ✓。
    """
    from types import SimpleNamespace

    from minibt.strategy.realtime import (_resolve_legend,
                                          indicator_legend_visible)

    assert _resolve_legend(True, 'a', 0) is True
    assert _resolve_legend(False, 'a', 0) is False
    assert _resolve_legend({'zero': False}, 'cci', 0) is True
    assert _resolve_legend({'zero': False}, 'zero', 1) is False
    assert _resolve_legend([True, False], 'a', 0) is True
    assert _resolve_legend([True, False], 'b', 1) is False
    # 解析不出来 → 保持显示（老行为，不会意外把标签藏掉 ✓）
    assert _resolve_legend({'zero': False}) is True
    assert _resolve_legend([True, False], 'x', 9) is True

    ind = SimpleNamespace(legend={'zero': False})
    owner = SimpleNamespace(_btindicatordataset={'CCI': ind})
    assert indicator_legend_visible(owner, 'CCI', 'cci', 0) is True
    assert indicator_legend_visible(owner, 'CCI', 'zero', 1) is False
    assert indicator_legend_visible(owner, 'missing', 'a', 0) is True
    assert indicator_legend_visible(SimpleNamespace(), 'CCI', 'a', 0) is True


def test_append_group_resolves_legend_per_line():
    """``_append_group`` 必须把**线名 / 线序**传进图例开关，才能按线隐藏 ✓"""
    src = _read('minibt', 'strategy', 'realtime.py')
    assert 'indicator_legend_visible(strategy, key, col, line_idx)' in src


def test_legend_dict_hides_single_line_end_to_end(headless):
    """端到端：``legend = dict(b=False)`` → 只有 ``a`` 那一行有图例 ✓"""
    import numpy as np

    import minibt.btplot as btp
    from minibt import BtIndicator, LocalDatas
    from minibt.strategy.realtime import extract_minibt_indicators
    from minibt.utils import Config

    class TwoLines(BtIndicator):
        lines = ('a', 'b')
        overlap = False
        params = dict(length=3)
        legend = {'b': False}

        def next(self):
            n = len(self.close)
            return np.zeros(n), np.ones(n)

    k = LocalDatas.test.kline
    strat = btp._make_step_strategy(k, [TwoLines(k)], Config(theme='dark'),
                                    'TwoLines')
    strat._start_strategy_run()
    got = {s.name: s.legend for s in extract_minibt_indicators(strat, 0)
           if s.source == 'TwoLines'}
    assert got.get('a') is True, got
    assert got.get('b') is False, got


def test_btplot_shell_matches_real_strategy_specs(headless):
    """★ ``btplot(gui='pylightcharts')`` 与「真策略」必须给出**同一批**指标线。

    两条路都是先造一个策略再走同一个 ``RealtimeChart`` →
    ``extract_minibt_indicators``：带 ``step`` 的指标用 ``_make_step_strategy``
    （真回测），否则用 ``_BtplotStrategy``（纯图表壳）。用户反馈「策略显示与
    btplot 显示不一样」时，先看这里 —— 线名 / 种类 / 绘图开关 / 数值形状
    应该**完全一致**（不一致就说明差异来自指标怎么建的，而不是渲染 ✗）。
    """
    import numpy as np

    import minibt.btplot as btp
    from minibt import LocalDatas
    from minibt.strategy.realtime import extract_minibt_indicators
    from minibt.utils import Config

    k = LocalDatas.test.kline
    sym = LocalDatas.test.kline
    ind = k.tradingview.SMTDivergences(sym1=sym)
    cfg = Config(theme='dark')
    shell = btp._BtplotStrategy(k, ind, [ind], cfg, 'SMT')
    strat = btp._make_step_strategy(k, [ind], cfg, 'SMT')
    strat._start_strategy_run()

    def snap(obj):
        return {x.name: (x.kind, x.legend, x.line_style,
                         np.asarray(x.values, dtype=float).shape)
                for x in extract_minibt_indicators(obj, 0)}

    assert snap(shell) == snap(strat), (snap(shell), snap(strat))
    # 传了对比合约 → wrapper 关掉 pivot，只留背离线 ✓
    assert set(snap(shell)) == {'div_high', 'div_low'}, snap(shell)


def test_apply_visual_now_calls_pylightcharts_setters():
    """★ 回归：菜单改了线型/线宽/线颜色/价格线要**立刻**写到序列上 ✓

    以前 ``_on_menu`` 只改 spec + 记 ``style_overrides`` → 要等下一次**重建**才
    生效 ✗（用户反馈：“选完没反应，重载其中一个指标后所有设置又生效了”）。
    """
    from minibt.strategy.realtime import IndicatorManager

    class _Series:
        def __init__(self):
            self.calls = []

        def set_line_style(self, value):
            self.calls.append(('style', value))

        def set_line_width(self, value):
            self.calls.append(('width', value))

        def set_line_color(self, value):
            self.calls.append(('color', value))

        def set_price_visible(self, name, value):
            self.calls.append(('price', name, value))

    manager = IndicatorManager(object())
    series = _Series()
    assert manager.apply_visual_now(series, 'style', {'value': 'dotted'}) == 1
    assert series.calls[-1] == ('style', 'dotted')
    assert manager.apply_visual_now(series, 'width', {'value': '3'}) == 1
    assert series.calls[-1] == ('width', 3)
    assert manager.apply_visual_now(series, 'color', {'value': '#ff0000'}) == 1
    assert series.calls[-1] == ('color', '#ff0000')
    assert manager.apply_visual_now(
        series, 'price', {'priceLine': True, 'priceLabel': False}) == 2
    assert series.calls[-2:] == [('price', 'price_line', True),
                                 ('price', 'price_label', False)]

    # 后端没有这些 API / 未知 kind / 宽度非法 → 安静跳过（老行为 ✓）
    assert manager.apply_visual_now(object(), 'color', {'value': '#fff'}) == 0
    assert manager.apply_visual_now(series, 'other', {}) == 0
    assert manager.apply_visual_now(series, 'width', {'value': 'x'}) == 0


def test_on_menu_applies_visual_immediately():
    """源码约束：``_on_menu`` 改完 spec 必须顺手 ``apply_visual_now`` ✓"""
    src = _read('minibt', 'strategy', 'realtime.py')
    start = src.index('def _on_menu(self, series, kind: str, payload: dict)')
    body = src[start:start + 1200]
    assert 'self.apply_visual_now(series, kind, payload)' in body


def test_menu_style_maps_minibt_aliases():
    """★ 回归：``cci.py`` 的 SMA 用 ``LineDash.dashdot``，菜单里必须显示**虚线** ✓

    以前 ``normalize_style`` 只认那 5 个名字，其余一律退回 ``solid`` ✗ ——
    于是“图上是长虚线、菜单却勾着实线”（用户反馈 ✗）。颜色按用户要求**不做**
    归一化/强插色板（可以不勾选默认 ✓）。
    """
    from types import SimpleNamespace

    from minibt.strategy import indicator_menu as im

    assert im.menu_style('dashdot') == 'dashed'
    assert im.menu_style('dotdash') == 'dashed'
    assert im.menu_style('long_dash') == 'large_dashed'
    assert im.menu_style('solid') == 'solid'
    assert im.menu_style('weird') == 'solid'
    assert im.menu_style('dashdot', 'Histogram') == 'solid'

    spec = SimpleNamespace(name='pta_sma', kind='Line', line_style='dashdot',
                           line_width=3, color='blue', price_line=False,
                           price_label=False, menu_params=None)
    config = im.build_config(spec)
    assert config['lineStyle'] == 'dashed', config['lineStyle']
    assert config['lineWidth'] == 3
    assert config['lineColor'] == 'blue'          # 颜色保持原样 ✓
    assert 'dashdot' not in config['styles']      # 菜单只给能画的 5 种 ✓


def test_menu_style_matches_indicator_end_to_end(headless):
    """端到端：``LineStyle(line_dash=LineDash.dashdot, line_width=3)`` 的指标，
    菜单配置必须与图上实际一致 ✓"""
    import minibt.btplot as btp
    from minibt import LineDash, LineStyle, LocalDatas
    from minibt.strategy import indicator_menu as im
    from minibt.strategy.realtime import extract_minibt_indicators
    from minibt.utils import Config

    k = LocalDatas.test.kline
    ma = k.close.sma(30)
    ma.line_style = LineStyle(line_dash=LineDash.dashdot, line_width=3)
    strat = btp._make_step_strategy(k, [ma], Config(theme='dark'), 'X')
    strat._start_strategy_run()
    spec = next(s for s in extract_minibt_indicators(strat, 0)
                if s.source == 'pta_sma')
    config = im.build_config(spec)
    assert spec.line_style == 'dashdot'
    assert config['lineStyle'] == im.menu_style(spec.line_style) == 'dashed'
    assert config['lineWidth'] == spec.line_width == 3
