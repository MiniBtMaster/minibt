"""minibt.strategy.realtime —— `PlotInfo` -> pylightcharts 映射层单测。

不跑完整回测：用假的策略/数据集对象喂 `extract_minibt_*`，用 `HeadlessChart`
捕获下发的脚本，断言映射结果。覆盖：

* 样式映射表（线型 / 标记形状 / 尺寸）；
* `extract_minibt_{spans,bands,candlestyle,signal_texts}`；
* `apply_{spans,bands,histogram_colors,color_rules,signals}`。
"""
import importlib.util
import pathlib
import sys
import threading
import time

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pylightcharts.headless import HeadlessChart          # noqa: E402

RT_PATH = ROOT / 'minibt' / 'strategy' / 'realtime.py'
if not RT_PATH.exists():
    # 从 sdist 运行、或只装了 pip 版 minibt 时没有这个文件，整份跳过
    pytest.skip('minibt/strategy/realtime.py 不存在（跳过映射层单测）',
                allow_module_level=True)


def _load_realtime():
    spec = importlib.util.spec_from_file_location('minibt_realtime', RT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules['minibt_realtime'] = module       # dataclass 需要注册模块
    spec.loader.exec_module(module)
    return module


rt = _load_realtime()


# ------------------------------------------------------------------ 测试替身

class FakeStyle:
    """`SignalStyle` / `SpanStyle` / `BandStyle` 的替身（属性访问）。"""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeDataset:
    """`_btindicatordataset` 的值：只要 `_get_plot_datas` 的 11/13/10 项。"""

    def __init__(self, spans=(), bands=(), texts=None, plot_id=0,
                 iscandles=False):
        self.plot_id = plot_id
        self.iscandles = iscandles
        self.pandas_object = None
        self._spans = list(spans)
        self._bands = list(bands)
        self._texts = dict(texts or {})

    def _get_plot_datas(self, key):                # noqa: ARG002
        data = [None] * 14
        data[10] = {'signal_texts': self._texts}
        data[11] = self._spans
        data[13] = self._bands
        return tuple(data)


class FakeKline:
    """`_btklinedataset` 的值：`extract_minibt_candlestyle` 读的那几个属性。"""

    def __init__(self, contract='DCE.pp2609_60', up=None, down=None):
        symbol, cycle = contract.rsplit('_', 1)   # 'DCE.pp2601' + '60'
        self.symbol = symbol
        self.cycle = cycle
        self._light_chart_candles_up_color = up is not None
        self._light_chart_candles_down_color = down is not None
        self.bull_color = up
        self.bear_color = down


class FakeSignalDataset:
    """`extract_minibt_signals` 需要的：`_plotinfo.signalstyle` + plot[4]/plot[8]。"""

    def __init__(self, lines, values, signalstyle, plot_id=0,
                 pandas_object=None, grouped=None):
        import types

        self.plot_id = plot_id
        self.pandas_object = pandas_object
        self._plotinfo = types.SimpleNamespace(
            signalstyle=dict(signalstyle))
        self._lines = list(lines)
        self._values = np.asarray(values, dtype=float)
        self._grouped = grouped            # 模拟多分组指标：plot[8] 非规整二维

    def _get_plot_datas(self, key):                # noqa: ARG002
        data = [None] * 14
        data[4] = self._lines
        data[8] = self._grouped if self._grouped is not None else self._values
        return tuple(data)


class FakeStrategy:
    def __init__(self, datasets=None, klines=None):
        self._btindicatordataset = datasets or {}
        self._btklinedataset = klines or {}


class FakeManager:
    def __init__(self, series, specs):
        self.series = list(series)
        self.specs = list(specs)


# -------------------------------------------------------------------- 工具

def make_frame(rows=4):
    base = np.arange(rows, dtype=float)
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='min'),
        'open': base, 'high': base + 1.0, 'low': base, 'close': base,
        'volume': base,
    })


def make_chart(frame=None):
    chart = HeadlessChart(width=800, height=600)
    chart.set(make_frame() if frame is None else frame)
    return chart


def scripts(chart):
    return '\n'.join(chart._scripts)


def test_extract_signals_anchors_to_named_indicator_line():
    """`SignalStyle('vidya_up', ...)`：锚点取该**指标线**的值（4 元组第 4 项）。"""
    lines = ['vidya_up', 'vidya_down', 'long_signal', 'short_signal']
    values = np.array([
        [10.0, np.nan, np.nan, np.nan],
        [11.0, np.nan, 11.0, np.nan],      # long 事件，锚 vidya_up = 11
        [np.nan, 12.0, np.nan, 12.0],      # short 事件，锚 vidya_down = 12
    ])
    styles = {'long_signal': FakeStyle(key='vidya_up'),
              'short_signal': FakeStyle(key='vidya_down')}
    dataset = FakeSignalDataset(lines, values, styles)
    out = rt.extract_minibt_signals(FakeStrategy({'d': dataset}), 0)
    anchors = {name: anchor for name, _v, _s, anchor, _p in out}
    assert anchors['long_signal'][0] == 10.0     # 整条 vidya_up 列都带过来
    assert anchors['long_signal'][1] == 11.0
    assert np.isnan(anchors['long_signal'][2])
    assert anchors['short_signal'][2] == 12.0


def test_extract_signals_kline_anchor_stays_none():
    """`SignalStyle('low', ...)`（贴 K 线）不应该产生锚点数组。"""
    lines = ['vidya_up', 'long_signal']
    values = np.array([[10.0, np.nan], [11.0, 11.0]])
    dataset = FakeSignalDataset(lines, values,
                               {'long_signal': FakeStyle(key='low')})
    out = rt.extract_minibt_signals(FakeStrategy({'d': dataset}), 0)
    assert len(out) == 1 and out[0][3] is None


def test_signal_payload_anchors_marker_on_the_line():
    """给了锚点数组时，标记 base/value 都等于线价、偏移 0（正好贴线）。"""
    frame = make_frame()
    style = FakeStyle(key='vidya_up', color='red', marker='triangle', size=12)
    values = np.array([np.nan, 1.0, np.nan, 2.0])
    anchor = np.array([np.nan, 55.0, 56.0, 57.0])
    data, make_shapes, _ = rt._signal_payload(frame, 'long_signal', values,
                                              style, None, anchor)
    assert list(data['base']) == [55.0, 57.0]
    assert list(data['value']) == [55.0, 57.0]     # 自动缩放也用线价
    assert make_shapes(data.iloc[0])[0]['offset'] == 0.0


def test_extract_signals_grouped_indicator_reads_anchor_from_pandas():
    """多分组指标（`plot[8]` 不是规整二维数组，如 VIDYA）时锚点走 pandas 兜底。

    这是"箭头全跑到 K 线最高价"那个 bug：一旦 `np.asarray(plot[8])` 报
    `inhomogeneous shape`，先前只在规整数组里取锚点的写法就被跳过了。
    """
    lines = ['vidya_up', 'long_signal']
    grouped = [np.zeros((3, 1)), np.zeros((3, 2))]     # 不等宽 → np.asarray 报错
    frame = pd.DataFrame({
        'time': [1, 2, 3],
        'vidya_up': [10.0, 11.0, 12.0],
        'long_signal': [np.nan, 11.0, np.nan],
    })
    dataset = FakeSignalDataset(
        lines, [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]],
        {'long_signal': FakeStyle(key='vidya_up')},
        pandas_object=frame, grouped=grouped)
    out = rt.extract_minibt_signals(FakeStrategy({'d': dataset}), 0)
    assert len(out) == 1
    name, _values_arr, _style, anchor, _pane = out[0]
    assert name == 'long_signal'
    assert anchor is not None
    assert list(anchor) == [10.0, 11.0, 12.0]      # 就是 vidya_up 那一列


def test_extract_signals_overlap_false_follows_indicator_pane():
    """`SignalStyle(..., overlap=False)` 的信号跟指标本体去同一个副图。

    `overlap=True`（默认）仍然留主图 pane 0；`overlap=False` 时取该指标
    （同 `source`）的 pane —— 例如 QQE 的 `qqe_slow` 在副图，信号也去副图。
    """
    lines = ['qqe_slow', 'long_signal']
    values = np.array([[50.0, np.nan], [51.0, 51.0], [52.0, np.nan]])
    style = {'long_signal': FakeStyle(key='qqe_slow', overlap=False)}
    dataset = FakeSignalDataset(lines, values, style)
    strategy = FakeStrategy({'d': dataset})
    assert rt.extract_minibt_signals(strategy, 0, {'d': 3})[0][4] == 3

    style_main = {'long_signal': FakeStyle(key='qqe_slow')}     # overlap 默认 True
    dataset_main = FakeSignalDataset(lines, values, style_main)
    assert rt.extract_minibt_signals(FakeStrategy({'d': dataset_main}), 0,
                                     {'d': 3})[0][4] == 0


def test_set_signal_overlap_keeps_user_choice_when_indicator_draws_lines():
    """`PlotInfo._set_signal_overlap()` 的判据是"整个指标有没有画线"。

    信号线本身 `isplot=False`（只画标记）是常态，按单条判断会把用户显式的
    `SignalStyle(..., overlap=False)` 无条件覆盖成主图 —— QQE 那种
    "指标线在副图、信号也想跟着去副图"的写法就永远不生效。
    """
    utils = pytest.importorskip('minibt.utils')

    class Info:                       # 鸭子类型：方法只用到这三个属性
        isplot = {'qqe_slow': True, 'long_signal': False}
        signallines = ['long_signal']
        signalstyle = {'long_signal': FakeStyle(overlap=False)}

    info = Info()
    utils.PlotInfo._set_signal_overlap(info)
    assert info.signalstyle['long_signal'].overlap is False


def test_set_signal_overlap_forces_main_for_marker_only_indicators():
    """纯标记型指标（一条线都不画）仍然强制回主图，避免空副图面板。"""
    utils = pytest.importorskip('minibt.utils')

    class Info:
        isplot = {'long_signal': False}
        signallines = ['long_signal']
        signalstyle = {'long_signal': FakeStyle(overlap=False)}

    info = Info()
    utils.PlotInfo._set_signal_overlap(info)
    assert info.signalstyle['long_signal'].overlap is True


def test_qqe_signals_keep_overlap_false():
    """真实指标实测：QQE 的 `overlap=False` 不被改写（否则信号会跑主图）。"""
    pytest.importorskip('minibt')
    from minibt import LocalDatas

    try:
        kline = LocalDatas.test.kline
    except Exception:                 # pragma: no cover - 缺数据时跳过
        pytest.skip('拿不到本地测试 K 线')
    indicator = kline.tradingview.QuantitativeQualitativeEstimation()
    styles = indicator._plotinfo.signalstyle
    assert styles['long_signal'].overlap is False
    assert styles['short_signal'].overlap is False


def test_sott_signalstyle_follows_the_source():
    """SOTT 的信号样式按原码 `plotshape`：绿三角 "Buy" / 红倒三角 "Sell"。

    锚在 OTT 复制线 `ott_s2` 上、画在指标自己的副图（原码 study 未 overlay），
    对应原码 `shape.labelup` + `color.green` / `shape.labeldown` + `color.red`。
    """
    pytest.importorskip('minibt')
    from minibt import LocalDatas

    try:
        kline = LocalDatas.test.kline
    except Exception:                 # pragma: no cover - 缺数据时跳过
        pytest.skip('拿不到本地测试 K 线')
    indicator = kline.tradingview.StochasticOptimizedTrendTracker()
    styles = indicator._plotinfo.signalstyle
    long_style, short_style = styles['long_signal'], styles['short_signal']
    assert long_style.key == 'ott_s2' and long_style.marker == 'triangle'
    assert short_style.key == 'ott_s2'
    assert short_style.marker == 'inverted_triangle'
    assert long_style.overlap is False and short_style.overlap is False
    assert long_style.color == 'green' and short_style.color == 'red'


def test_sott_signals_are_on_by_default():
    """SOTT 的 `show_signals` 默认打开（原码 `defval=false`，minibt 改成 True）。

    这个开关在 minibt 里是**计算开关**：关着时 `next()` 整段跳过，
    `long_signal`/`short_signal` 恒为 0 —— 图上既没有 Buy/Sell 标记也没有文本
    （两个引擎都一样）。类和访问器（`kline.tradingview.X()`）两处默认值必须一致，
    否则只改类、访问器仍然显式传 False。
    """
    pytest.importorskip('minibt')
    import inspect

    from minibt import LocalDatas
    from minibt.indicators.tradingview import (StochasticOptimizedTrendTracker,
                                               TradingView)

    assert StochasticOptimizedTrendTracker.params['show_signals'] is True
    default = inspect.signature(
        TradingView.StochasticOptimizedTrendTracker).parameters[
            'show_signals'].default
    assert default is True

    try:
        kline = LocalDatas.test.kline
    except Exception:                 # pragma: no cover - 缺数据时跳过
        pytest.skip('拿不到本地测试 K 线')
    indicator = kline.tradingview.StochasticOptimizedTrendTracker()   # 不传参数
    long_values = np.asarray(indicator.long_signal.values, dtype=float)
    short_values = np.asarray(indicator.short_signal.values, dtype=float)
    assert (long_values > 0).sum() > 0
    assert (short_values > 0).sum() > 0


def test_no_indicator_hides_its_signal_markers_by_default():
    """守卫"保持信号打开"：任何 `SignalStyle(...)` 都不该默认 `show=False`。

    `SignalStyle(key, color, marker, overlap, show, size)` 的第 5 个参数是
    `show` —— 写成 `False` 就等于"这个指标的信号标记永远不画"。有些指标用
    params 里的开关驱动它，这里至少守住"别在静态样式里直接关掉"。
    """
    import ast

    import pathlib as _pathlib

    src = (_pathlib.Path(__file__).resolve().parents[1] / 'minibt' / 'indicators'
           / 'tradingview.py')
    if not src.exists():
        pytest.skip('minibt 源码不在（跳过）')
    tree = ast.parse(src.read_text(encoding='utf-8'))
    hidden = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, 'id', None) or getattr(func, 'attr', None)
        if name != 'SignalStyle':
            continue
        positional = node.args[4] if len(node.args) > 4 else None
        keyword = next((k.value for k in node.keywords if k.arg == 'show'),
                       None)
        value = keyword if keyword is not None else positional
        if (isinstance(value, ast.Constant) and value.value is False):
            hidden.append(node.lineno)
    assert not hidden, f'这些 SignalStyle 把信号标记默认关掉了：{hidden}'


# ------------------------------------------------------------ 样式映射表

@pytest.mark.parametrize('name,expected', [
    ('solid', 0), ('dotted', 1), ('dashed', 2), ('large_dashed', 3),
    ('sparse_dotted', 4), ('dotdash', 2), ('dashdot', 3), ('SOLID', 0),
])
def test_line_style_value(name, expected):
    assert rt.line_style_value(name) == expected


def test_unknown_line_style_falls_back_to_solid(capsys):
    assert rt.line_style_value('nope') == 0
    assert '未知线型' in capsys.readouterr().out


@pytest.mark.parametrize('name,expected', [
    ('triangle', 'arrow_up'), ('inverted_triangle', 'arrow_down'),
    ('circle', 'circle'), ('circle_cross', 'circle'), ('square', 'square'),
    ('dot', 'circle'), ('nope', 'circle'),
])
def test_marker_shape_value(name, expected):
    assert rt.marker_shape_value(name) == expected


def test_marker_size_is_clamped():
    assert rt.marker_size_value(12) == pytest.approx(1.0)
    assert rt.marker_size_value(1) >= 0.5
    assert rt.marker_size_value(999) <= 2.0


@pytest.mark.parametrize('value,expected', [
    ('red', 'red'), (None, None), ('', None),
])
def test_as_color(value, expected):
    assert rt._as_color(value, 'fallback') == (
        expected if expected is not None else 'fallback')


def test_iter_style_accepts_list_dict_and_single():
    span = FakeStyle(location=0)
    assert list(rt._iter_style([span])) == [span]
    assert list(rt._iter_style({'a': span})) == [span]
    assert list(rt._iter_style(span)) == [span]
    assert rt._iter_style(None) == []


# --------------------------------------------------------- extract_* 提取

def test_extract_spans():
    dataset = FakeDataset(spans=[FakeStyle(location=0.0, line_color='red',
                                           line_dash='dotted', line_width=2),
                                 FakeStyle(location=np.nan)])
    spans = rt.extract_minibt_spans(FakeStrategy({'cci': dataset}), 0)
    assert spans == [{'source': 'cci', 'price': 0.0, 'color': 'red',
                      'style': 'dotted', 'width': 2}]


def test_extract_spans_skips_other_plot():
    dataset = FakeDataset(spans=[FakeStyle(location=1.0)], plot_id=7)
    assert rt.extract_minibt_spans(FakeStrategy({'x': dataset}), 0) == []


def test_extract_spans_uses_defaults():
    dataset = FakeDataset(spans=[FakeStyle(location=-100.0)])
    span = rt.extract_minibt_spans(FakeStrategy({'c': dataset}), 0)[0]
    assert span['color'] == '#666666'
    assert span['style'] == 'dashed' and span['width'] == 1


def test_extract_bands():
    dataset = FakeDataset(bands=[FakeStyle(lower='cci', upper='zero',
                                           fill_color='steelblue',
                                           fill_alpha=0.3)])
    bands = rt.extract_minibt_bands(FakeStrategy({'cci': dataset}), 0)
    assert bands == [{'source': 'cci', 'lower': 'cci', 'upper': 'zero',
                      'color': 'steelblue', 'alpha': 0.3,
                      'line_color': None}]


def test_extract_bands_skips_incomplete():
    dataset = FakeDataset(bands=[FakeStyle(lower='a'), FakeStyle(upper='b')])
    assert rt.extract_minibt_bands(FakeStrategy({'x': dataset}), 0) == []


def test_extract_candlestyle_only_explicit_colors():
    kline = FakeKline(up='lime', down='#ff5722')
    strategy = FakeStrategy(klines={'k': kline})
    assert rt.extract_minibt_candlestyle(
        strategy, 'DCE.pp2609_60') == {'up': 'lime', 'down': '#ff5722'}


def test_extract_candlestyle_empty_when_unset():
    strategy = FakeStrategy(klines={'k': FakeKline()})
    assert rt.extract_minibt_candlestyle(strategy, 'DCE.pp2609_60') == {}


def test_extract_candlestyle_other_contract():
    strategy = FakeStrategy(klines={'k': FakeKline(up='lime')})
    assert rt.extract_minibt_candlestyle(strategy, 'SHFE.ni2601_60') == {}


def test_extract_signal_texts():
    dataset = FakeDataset(texts={'long_signal': ['', 'R', '', 'B']})
    texts = rt.extract_minibt_signal_texts(FakeStrategy({'d': dataset}), 0)
    assert texts == {'long_signal': ['', 'R', '', 'B']}


# ------------------------------------------------------------- apply_* 落地

def test_apply_spans_emits_horizontal_span():
    chart = make_chart()
    made = rt.apply_spans(chart, [{'source': 'x', 'price': 50.0,
                                   'color': 'red', 'style': 'dotted',
                                   'width': 2}])
    assert len(made) == 1
    out = scripts(chart)
    assert 'HorizontalSpan' in out
    assert "lineColor: 'red'" in out and 'filled: false' in out


def test_apply_bands_uses_fill_between_with_alpha():
    chart = make_chart()
    upper = chart.add_series('Line', name='zero')
    lower = chart.add_series('Line', name='cci')
    times = list(make_frame()['time'])
    upper.set(pd.DataFrame({'time': times, 'zero': [0.0] * 4}))
    lower.set(pd.DataFrame({'time': times,
                            'cci': [1.0, -1.0, 2.0, -2.0]}))
    spec = rt.IndicatorSpec(name='zero', overlap=False)
    spec.source = 'cci'
    lower_spec = rt.IndicatorSpec(name='cci', overlap=False)
    lower_spec.source = 'cci'
    manager = rt.IndicatorManager(chart)      # 用真管理器：需要 series_named
    manager.series = [upper, lower]
    manager.specs = [spec, lower_spec]
    rt.apply_bands(manager, [{'source': 'cci', 'lower': 'cci',
                              'upper': 'zero', 'color': 'steelblue',
                              'alpha': 0.3, 'line_color': None}])
    out = scripts(chart)
    assert 'LineFill' in out and 'opacity: 0.3' in out


def test_apply_bands_skips_missing_line():
    chart = make_chart()
    manager = FakeManager([], [])
    rt.apply_bands(manager, [{'source': 'cci', 'lower': 'a', 'upper': 'b',
                              'color': 'x', 'alpha': 1.0,
                              'line_color': None}])
    assert 'LineFill' not in scripts(chart)


def test_apply_histogram_colors_splits_by_base():
    frame = make_frame()
    chart = make_chart(frame)
    series = chart.add_series('Histogram', name='macdh')
    series.set(pd.DataFrame({'time': list(frame['time']),
                             'macdh': [-1.0, 2.0, -3.0, 4.0]}))
    spec = rt.IndicatorSpec(name='macdh', overlap=False,
                            values=pd.Series([-1.0, 2.0, -3.0, 4.0]),
                            kind='Histogram')
    spec.source = 'macd'
    manager = FakeManager([series], [spec])
    rt.apply_histogram_colors(manager, FakeStrategy(), '', 4)
    out = scripts(chart)
    assert '"color":"#26a69a"' in out or "'#26a69a'" in out


def test_apply_color_rules_on_kline_and_indicator():
    frame = make_frame()
    chart = make_chart(frame)
    series = chart.add_series('Line', name='ma')
    series.set(pd.DataFrame({'time': list(frame['time']),
                             'ma': [1.0, -1.0, 1.0, -1.0]}))
    kline = FakeKline()
    kline.__dict__['_color_rules'] = [{
        'condition': np.array([True, False, True, False]), 'color': 'red',
        'else_color': None, 'options': {'wick_color': 'orange'}}]
    dataset = FakeDataset()
    dataset.__dict__['_color_rules'] = [{
        'condition': np.array([True, True, False, False]), 'color': 'green',
        'else_color': 'gray', 'options': {}}]
    strategy = FakeStrategy({'ma': dataset}, {'k': kline})
    spec = rt.IndicatorSpec(name='ma', overlap=True)
    spec.source = 'ma'
    rt.apply_color_rules(chart, FakeManager([series], [spec]), strategy,
                         'DCE.pp2609_60')
    out = scripts(chart)
    assert 'orange' in out            # K 线：逐根变色
    assert 'gray' in out              # 指标：else_color


def test_indicator_reslice_keeps_histogram_colors_on_update():
    """回放逐根推进（`reslice` 增量分支 / 整段 set）都要保持柱体配色。

    历史 bug：增量分支只发 `{time, value}`，新柱子掉回系列默认色 —— 回放时
    看着就是“macd / rsi 变回 line_color”。
    """
    frame = make_frame()
    chart = make_chart(frame)
    series = chart.add_series('Histogram', name='macdh')
    values = pd.Series([1.0, -1.0, 2.0, -2.0])
    series.set(pd.DataFrame({'time': list(frame['time']), 'macdh': values}))
    spec = rt.IndicatorSpec(name='macdh', overlap=False, kind='Histogram',
                            values=values, vbar_base=0.0,
                            vbar_up_color='red', vbar_down_color='green',
                            up_color='red', down_color='green')
    manager = rt.IndicatorManager(chart)
    manager.align = 'tail'
    manager.series, manager.specs = [series], [spec]

    # 增量：2 -> 4 根，只 update 后两根，但必须带颜色
    chart._scripts.clear()
    manager.reslice(frame, previous=2)
    joined = '\n'.join(chart._scripts)
    assert '"color":"red"' in joined and '"color":"green"' in joined, joined

    # 整段 set 也要把颜色刷回来
    chart._scripts.clear()
    manager.reslice(frame)
    joined = '\n'.join(chart._scripts)
    assert '"color":"red"' in joined and '"color":"green"' in joined, joined


def test_bokeh_pops_every_minibt_only_linestyle_key():
    """`LineStyle` 里 bokeh 不认识的字段，必须在传给 bokeh 前全部剔除。

    历史 bug：新增 `vbar_up_color` / `vbar_color_base` 时漏了剔除，bokeh 直接
    报 `AttributeError: unexpected attribute '...' to Line`。这个测试把"每个
    非 bokeh 字段都要有对应的 pop/del"钉住。
    """
    import dataclasses
    try:
        from minibt.utils import LineStyle
    except Exception:
        pytest.skip('minibt not importable')
    bokeh_line_keys = {'line_dash', 'line_width', 'line_color', 'name'}
    minibt_only = {f.name for f in dataclasses.fields(LineStyle)} - bokeh_line_keys
    for relative in ('minibt/strategy/bokeh_plot.py', 'minibt/btplot.py'):
        path = ROOT / relative
        if not path.exists():
            continue
        source = path.read_text(encoding='utf-8', errors='ignore')
        for key in sorted(minibt_only):
            popped = (f'_lineinfo.pop("{key}", None)' in source
                      or f'del _lineinfo["{key}"]' in source)
            assert popped, (relative, key)


def test_replay_build_indicators_applies_all_decorations(monkeypatch):
    """回放路径必须也应用「柱体配色 / 逐点配色 / 色带 / 水平线 / K 线涨跌色」。

    历史 bug：这些只在 `RealtimeChart._rebuild_indicators` 里调用了，回放
    （`ReplayWindow._build_indicators`）漏掉 —— 表现就是 replay 里 macd 柱子
    颜色不生效（只有 vbar 形状，没有上下行配色）。
    """
    try:
        import minibt.strategy.realtime as real
        import minibt.strategy.replay_window as rw
    except Exception:                    # 没有 minibt 包：跳过
        pytest.skip('minibt not importable')
    called = []
    names = ('apply_histogram_colors', 'apply_color_rules', 'apply_bands',
             'apply_spans', 'apply_candlestyle', 'apply_watermark',
             'palette_for', 'strategy_contracts', 'strategy_watermark',
             'extract_minibt_bands', 'extract_minibt_spans',
             'extract_minibt_candlestyle')
    for name in names:
        assert hasattr(real, name), name
        monkeypatch.setattr(real, name,
                            lambda *a, _n=name, **k: called.append(_n))
    # `strategy_contracts` 要返回列表（代码里会 .index(contract)）
    monkeypatch.setattr(real, 'strategy_contracts',
                        lambda *a, **k: (called.append('strategy_contracts'),
                                         ['X_60'])[1])
    # 收起/展开按钮也必须挂上（用户反馈：回放里指标不能一键收起 ✗）
    from minibt.strategy import indicator_menu as im
    assert hasattr(im, 'enable_collapse')
    monkeypatch.setattr(im, 'enable_collapse',
                        lambda chart: called.append('enable_collapse'))

    frame = make_frame()
    chart = FakeStyle(candle_data=pd.DataFrame(
        {'time': list(frame['time']), 'open': 1.0, 'high': 2.0, 'low': 0.5,
         'close': 1.5, 'volume': 1.0}))
    holder = FakeStyle(
        chart=chart,
        indicators_of=lambda strategy, contract: [object()],
        window=FakeStyle(strategy='S', contract='X_60',
                         _apply_pane_stretch=lambda: called.append('stretch')),
        _strategy_by_name=lambda name: FakeStyle(),
        _refresh_signals=lambda frame=None: called.append('signals'),
        spans=[])
    holder._indicator_manager = FakeStyle(
        build=lambda *a, **k: called.append('manager.build'))

    rw.ReplayWindow._build_indicators(holder)

    for expected in ('manager.build', 'enable_collapse',
                     'apply_histogram_colors', 'apply_color_rules',
                     'apply_bands', 'apply_spans', 'apply_candlestyle'):
        assert expected in called, (expected, called)


def test_replay_speed_is_linear_and_step_releases_one_bar(monkeypatch):
    """★ 倍速只改间隔（Nx = BASE/N），且每 tick 只放一根。

    历史 bug：tick 间隔除以 N、`step()` 又按倍速一次放 N 根，实际速度成了
    N²（2x 快 4 倍、10x 快 100 倍）——5x/10x “跑得飞快”、暂停后还要再跑一段，
    且 K 线与指标脱节。
    """
    import minibt.strategy.replay_window as rw
    frame = make_frame(rows=10)

    class FakeTimer:
        def __init__(self, parent=None):
            self.interval = None
            self.timeout = FakeStyle(connect=lambda fn: None)

        def start(self, ms):
            self.interval = ms

        def stop(self):
            pass

    class FakeChart:
        is_alive = True

        def __init__(self):
            self.candle_data = frame
            self.updates = 0
            self.batches = 0

        def update(self, bar):
            self.updates += 1

        def batch(self):
            chart = self

            class _Ctx:
                def __enter__(self_):
                    chart.batches += 1
                    return chart

                def __exit__(self_, *args):
                    return False

            return _Ctx()

        def fit(self):
            pass

    def make_holder(speed):
        holder = FakeStyle(chart=FakeChart(), frame=frame, index=0, speed=speed,
                           playing=False, _timer=None, _interval=0)
        # `play()` 会拿 QApplication/QTimer；这里用假的，强制走定时器路径
        holder._qt_app = lambda: object()
        holder._qt_modules = lambda: (FakeTimer, object)
        holder._step_lock = threading.Lock()
        holder.pause = lambda: None
        holder.step = lambda: None
        holder._sync_play_button = lambda: None
        holder._reslice_indicators = lambda: None
        holder._show_progress = lambda: None
        holder._refresh_backtest = lambda force=False: None
        return holder

    expected = {'1x': 400, '2x': 200, '5x': 80, '10x': 40}
    for speed, interval in expected.items():
        holder = make_holder(speed)
        rw.ReplayWindow.play(holder)
        assert holder.playing is True
        assert holder._interval == interval, (speed, holder._interval)
        # 每个 tick 只放一根（以前 10x 一次放 10 根）
        rw.ReplayWindow.step(holder)
        assert holder.chart.updates == 1, (speed, holder.chart.updates)
        assert holder.index == 1, (speed, holder.index)
        # K 线 + 指标 + 进度必须在同一批下发，避免画面脱节
        assert holder.chart.batches == 1, (speed, holder.chart.batches)


def test_replay_refresh_backtest_time_gate():
    """回测重算有**时间**下限：高倍速下不会每 tick 都重算。"""
    import minibt.strategy.replay_window as rw
    frame = make_frame(rows=100)
    calls = []
    holder = FakeStyle(
        chart=FakeStyle(is_alive=True),
        frame=frame, index=10, _refreshed_at=-1,
        refresh_every=5, refresh_interval=10.0,
        _last_refresh_time=time.monotonic(),
        window=FakeStyle(strategy='S',
                         set_backtest=lambda **k: calls.append(k)),
        backtest=lambda released: {'stats': {}, 'equity': None},
        _refresh_equity_overlay=lambda data: None,
        _refresh_capital_overlay=lambda: None,
    )
    rw.ReplayWindow._refresh_backtest(holder)
    assert calls == []                     # 时间未到：跳过
    holder._last_refresh_time = 0.0
    rw.ReplayWindow._refresh_backtest(holder)
    assert len(calls) == 1                 # 时间到：执行
    assert holder._refreshed_at == 10


def test_replay_worker_is_single_and_persistent(monkeypatch):
    """`play/pause` 反复切只应有一个常驻 worker，`pause` 不再清空 `_thread`。

    历史 bug：`pause()` 立刻把 `_thread` 置 None，`play()` 又新建一个，旧线程
    没退出时两个线程同时 `step()`，引擎数据乱掉后所有按钮都不再推进（用户反馈 ✗）。
    """
    import minibt.strategy.replay_window as rw

    created = []

    class FakeThread:
        def __init__(self, target=None, name=None, daemon=None):
            self.target = target
            self._alive = False
            created.append(self)

        def start(self):
            self._alive = True

        def is_alive(self):
            return self._alive

        def join(self, timeout=None):
            pass

    monkeypatch.setattr(threading, 'Thread', FakeThread)

    holder = FakeStyle(playing=False, _thread=None, _wake=None, _closed=False,
                       _interval=100, _timer=None,
                       chart=FakeStyle(is_alive=True))
    holder._thread_loop = lambda: None
    holder._sync_play_button = lambda: None
    holder._refresh_backtest = lambda force=False: None

    rw.ReplayWindow._ensure_thread(holder)
    rw.ReplayWindow._ensure_thread(holder)
    assert len(created) == 1                # 只建一个 worker
    first = holder._thread
    rw.ReplayWindow.pause(holder)
    assert holder._thread is first          # pause 不再把 _thread 清空
    rw.ReplayWindow._ensure_thread(holder)
    assert len(created) == 1                # 复用，不重复建


def test_replay_settings_expose_recover():
    """「设置」菜单里要有「恢复回放」（卡死时重发当前进度拉回一致）。"""
    source = (ROOT / 'minibt' / 'strategy' / 'replay_window.py').read_text(
        encoding='utf-8')
    assert 'extra_settings' in source
    assert '恢复回放' in source
    assert 'def recover' in source


def test_topbar_callback_exception_is_isolated(capsys):
    """顶栏回调抛异常不能冒出去。

    以前它会一路冒到 `Chart.show_async`，把整个事件循环带走 —— 窗口还在，
    但整个界面的按钮全没反应（用户反馈 ✗）。
    """
    chart = HeadlessChart(400, 300)

    def boom(_chart):
        raise RuntimeError('boom')

    chart.topbar.button('x', 'x', func=boom)
    widget = chart.topbar['x']
    chart.win.handlers[widget.id]('false')        # 不应抛
    assert '回调失败' in capsys.readouterr().err


def test_replay_recover_resends_slice_and_clamps_index():
    """「恢复回放」要把越界索引夹回来，并按当前进度重发一遍 K 线。"""
    import minibt.strategy.replay_window as rw

    frame = make_frame(rows=20)

    class FakeChart:
        is_alive = True

        def __init__(self):
            self.candle_data = frame.iloc[:0]
            self.set_arg = None
            self.fitted = False

        def set(self, df):
            self.set_arg = df
            self.candle_data = df

        def fit(self):
            self.fitted = True

    def make_holder(index):
        holder = FakeStyle(chart=FakeChart(), frame=frame, index=index,
                           start_bars=3, window=FakeStyle())
        holder.pause = lambda: None
        holder._build_indicators = lambda: None
        holder._refresh_backtest = lambda force=False: None
        holder._show_progress = lambda: None
        holder._sync_play_button = lambda: None
        holder._slice_loader = lambda strategy, contract: frame
        return holder

    holder = make_holder(999)
    rw.ReplayWindow.recover(holder)
    assert holder.index == len(frame)              # 越界上限被夹回
    assert holder.chart.set_arg is not None
    assert len(holder.chart.set_arg) == len(frame)
    assert holder.chart.fitted is True
    assert holder._indicator_len == len(frame)

    holder2 = make_holder(-5)
    rw.ReplayWindow.recover(holder2)
    assert holder2.index == 3                       # 下界 = start_bars


def test_vbar_line_style_colors_control_histogram():
    """`LineStyle(vbar_up_color/vbar_down_color, vbar_base)` 控制柱体上下行颜色。

    不设颜色时跟主图 K 线色一致（`strategy_candle_colors`）。
    """
    frame = make_frame()
    chart = make_chart(frame)
    series = chart.add_series('Histogram', name='macdh')

    class _Manager:                 # 无 view_values/spec_values：落回 spec.values
        def __init__(self, s, sp):
            self.series, self.specs = [s], [sp]

    values = pd.Series([1.0, -1.0, 2.0, -2.0])
    series.set(pd.DataFrame({'time': list(frame['time']), 'macdh': values}))
    spec = rt.IndicatorSpec(name='macdh', overlap=False, kind='Histogram',
                            values=values, vbar_base=0.0,
                            vbar_up_color='red', vbar_down_color='green')
    rt.apply_histogram_colors(_Manager(series, spec), FakeStrategy(),
                              'DCE.pp2609_60', len(values))
    assert series.data['color'].tolist() == ['red', 'green', 'red', 'green']
    assert (spec.up_color, spec.down_color) == ('red', 'green')

    # 不设颜色：跟 K 线色（这里没有 -> pylightcharts 默认涨/跌色）
    spec2 = rt.IndicatorSpec(name='macdh2', overlap=False, kind='Histogram',
                             values=values, vbar_base=0.0)
    series2 = chart.add_series('Histogram', name='macdh2')
    series2.set(pd.DataFrame({'time': list(frame['time']), 'macdh2': values}))
    rt.apply_histogram_colors(_Manager(series2, spec2), FakeStrategy(),
                              'DCE.pp2609_60', len(values))
    assert series2.data['color'].tolist() == ['#26a69a', '#ef5350',
                                              '#26a69a', '#ef5350']

    # `vbar_color_base`：柱子仍从 vbar_base(0) 画，但按 1.5 分色
    spec3 = rt.IndicatorSpec(name='macdh3', overlap=False, kind='Histogram',
                             values=values, vbar_base=0.0,
                             vbar_color_base=1.5, vbar_up_color='red',
                             vbar_down_color='green')
    series3 = chart.add_series('Histogram', name='macdh3')
    series3.set(pd.DataFrame({'time': list(frame['time']), 'macdh3': values}))
    rt.apply_histogram_colors(_Manager(series3, spec3), FakeStrategy(),
                              'DCE.pp2609_60', len(values))
    # values = [1, -1, 2, -2] vs 1.5 -> [F, F, T, F]
    assert series3.data['color'].tolist() == ['green', 'green', 'red', 'green']

    # 显式 line_color 且没给上下行色：整段单色（不逐点配色）
    spec4 = rt.IndicatorSpec(name='macdh4', overlap=False, kind='Histogram',
                             values=values, vbar_base=0.0, color='blue')
    series4 = chart.add_series('Histogram', name='macdh4')
    series4.set(pd.DataFrame({'time': list(frame['time']), 'macdh4': values}))
    rt.apply_histogram_colors(_Manager(series4, spec4), FakeStrategy(),
                              'DCE.pp2609_60', len(values))
    assert 'color' not in series4.data.columns
    assert (spec4.up_color, spec4.down_color) == ('blue', 'blue')


def test_apply_color_rules_ignores_missing_condition():
    chart = make_chart()
    kline = FakeKline()
    kline.__dict__['_color_rules'] = [{'condition': None, 'color': 'red'}]
    strategy = FakeStrategy(klines={'k': kline})
    rt.apply_color_rules(chart, FakeManager([], []), strategy,
                         'DCE.pp2609_60')
    assert 'red' not in scripts(chart)   # condition 为 None → 不下发


def test_color_rules_tail_align_when_chart_loaded_more_history():
    """实盘「无限历史」：图比条件长（401/601 vs 200）时按尾部对齐。

    老 K 线（条件未覆盖）必须**不套色**，而不是被 `else_color` 统一刷色
    （历史 bug：直接报 `condition has 200 rows but the frame has 601`）。
    """
    n = 601
    times = pd.date_range('2024-01-01', periods=n, freq='min')
    frame = pd.DataFrame({'time': times, 'open': 1.0, 'high': 2.0,
                          'low': 0.5, 'close': 1.5, 'volume': 1.0})
    chart = make_chart(frame)
    mask = np.zeros(200, dtype=bool)
    mask[-1] = True
    kline = FakeKline()
    kline.__dict__['_color_rules'] = [{
        'condition': mask, 'color': 'red', 'else_color': 'blue',
        'options': {}}]
    strategy = FakeStrategy(klines={'k': kline})
    manager = FakeManager([], [])
    manager.align = 'tail'
    rt._COLOR_BY_WARNED.clear()
    rt.apply_color_rules(chart, manager, strategy, 'DCE.pp2609_60')
    assert not rt._COLOR_BY_WARNED, rt._COLOR_BY_WARNED   # 不再报长度不匹配
    colors = list(chart.candle_data['color'])
    assert len(colors) == n
    assert set(colors[:n - 200]) == {None}     # 老 K 线：保持原色
    assert colors[-1] == 'red'                 # 最后 200 根：命中
    assert colors[-2] == 'blue'                # 最后 200 根：未命中


# ----------------------------------------------------------------- 信号

def test_apply_signals_forwards_marker_and_text():
    frame = make_frame()
    chart = make_chart(frame)
    style = FakeStyle(key='low', color='red', marker='circle_cross',
                      size=12, label=FakeStyle(text='B', size=9,
                                               color='blue'))
    rt.apply_signals(chart, frame,
                     [('long_signal', np.array([0.0, 1.0, 0.0, 1.0]), style)])
    out = scripts(chart)
    assert '"marker":"circle_cross"' in out      # 原样透传 minibt 名字
    assert '"type":"marker"' in out and '"type":"text"' in out
    assert '"text":"B"' in out


def test_apply_signals_per_point_texts_win():
    frame = make_frame()
    chart = make_chart(frame)
    style = FakeStyle(key='low', color='red', marker='triangle', size=12,
                      label=FakeStyle(text='B', size=9, color='blue'))
    rt.apply_signals(chart, frame,
                     [('long_signal', np.array([0.0, 1.0, 0.0, 0.0]), style)],
                     {'long_signal': ['', 'R', '', '']})
    out = scripts(chart)
    assert '"text":"R"' in out and '"text":"B"' not in out


def test_apply_signals_skips_when_no_signal():
    frame = make_frame()
    chart = make_chart(frame)
    style = FakeStyle(key='low', color='red', marker='triangle', size=12)
    rt.apply_signals(chart, frame,
                     [('long_signal', np.zeros(4), style)])
    assert '"type":"marker"' not in scripts(chart)


def test_apply_signals_handles_nan_gapped_signals():
    """稀疏 NaN 信号（VIDYA 的趋势箭头）每个事件都要画，不能被上次非 0 卡住。"""
    frame = make_frame(rows=6)
    chart = make_chart(frame)
    style = FakeStyle(key='low', color='red', marker='triangle', size=12)
    values = np.array([np.nan, 1.0, np.nan, 2.0, np.nan, 3.0])
    rt.apply_signals(chart, frame, [('long_signal', values, style)])
    out = scripts(chart)
    assert out.count('"type":"marker"') == 3, out


def test_apply_signals_short_uses_high_anchor():
    frame = make_frame()
    chart = make_chart(frame)
    style = FakeStyle(key='high', color='green', marker='inverted_triangle',
                      size=12)
    rt.apply_signals(chart, frame,
                     [('short_signal', np.array([0.0, 0.0, 1.0, 0.0]), style)])
    out = scripts(chart)
    assert '"marker":"inverted_triangle"' in out
    assert '"offset":-2.0' in out                # 上方信号锚点为尖端


def test_apply_signals_returns_deletable_series():
    """信号是自定义序列，返回值必须能 delete（切策略/合约时清理用）。"""
    frame = make_frame()
    chart = make_chart(frame)
    style = FakeStyle(key='low', color='red', marker='triangle', size=12)
    made = rt.apply_signals(
        chart, frame,
        [('long_signal', np.array([0.0, 1.0, 0.0, 0.0]), style)])
    assert len(made) == 1
    made[0].delete()
    assert 'removeSeries' in scripts(chart)


# ------------------------------------------------- 实盘更新（重取 + 逐点配色）

class ValueDataset:
    """`_get_plot_datas` 第 8 项带数值的替身（模拟会被策略重建的指标对象）。"""

    def __init__(self, values, plot_id=0):
        self.plot_id = plot_id
        self.iscandles = False
        self.pandas_object = None
        self._values = np.asarray(values, dtype=float)

    def _get_plot_datas(self, key):            # noqa: ARG002
        data = [None] * 14
        data[8] = self._values.reshape(-1, 1) if self._values.ndim == 1 \
            else self._values
        return tuple(data)


def test_indicator_values_resolve_fresh_dataset():
    """实盘每次跑策略会重建指标对象，取值必须按 key 现取而不是闭包旧对象。"""
    strategy = FakeStrategy({'ma': ValueDataset([1.0, 2.0, 3.0])})
    get_values = rt._indicator_values(strategy, 'ma', 0, 0)
    assert list(get_values()) == [1.0, 2.0, 3.0]
    strategy._btindicatordataset['ma'] = ValueDataset([1.0, 2.0, 3.0, 9.9])
    assert list(get_values()) == [1.0, 2.0, 3.0, 9.9]


def test_update_last_sends_histogram_color():
    frame = make_frame()
    chart = make_chart(frame)
    series = chart.add_series('Histogram', name='macdh')
    series.set(pd.DataFrame({'time': list(frame['time']),
                             'macdh': [0.5, -1.0, 2.0, -3.0]}))
    spec = rt.IndicatorSpec(name='macdh', overlap=False, kind='Histogram',
                            up_color='lime', down_color='tomato',
                            get_values=lambda: np.array([0.5, -1.0, 2.0,
                                                         -3.0]))
    manager = rt.IndicatorManager(chart)
    manager.series, manager.specs = [series], [spec]
    manager.update_last(frame['time'].iloc[-1])
    out = scripts(chart)
    assert '"value":-3.0' in out and '"color":"tomato"' in out


def test_update_last_sends_color_rule():
    """均线等 color_by 线更新最后一点时要带颜色，否则会掉回基色。"""
    frame = make_frame()
    chart = make_chart(frame)
    series = chart.add_series('Line', name='ma')
    series.set(pd.DataFrame({'time': list(frame['time']),
                             'ma': [1.0, 2.0, 3.0, 4.0]}))
    spec = rt.IndicatorSpec(name='ma', overlap=True, color='yellow',
                            get_values=lambda: np.array([1.0, 2.0, 3.0,
                                                         4.0]),
                            color_conditions=[
                                (np.array([False, False, True, True]),
                                 'orange', None)])
    manager = rt.IndicatorManager(chart)
    manager.series, manager.specs = [series], [spec]
    manager.update_last(frame['time'].iloc[-1])
    assert '"color":"orange"' in scripts(chart)


def test_update_last_skips_nan_point():
    """全 NaN 的线（如未触发的止损线）不推更新，避免 value 被 pandas 转成 NaT。"""
    frame = make_frame()
    chart = make_chart(frame)
    series = chart.add_series('Line', name='stop')
    series.set(pd.DataFrame({'time': list(frame['time']),
                             'stop': [np.nan] * 4}))
    spec = rt.IndicatorSpec(name='stop', overlap=True,
                            get_values=lambda: np.array([np.nan] * 4))
    manager = rt.IndicatorManager(chart)
    manager.series, manager.specs = [series], [spec]
    before = len(chart._scripts)
    manager.update_last(frame['time'].iloc[-1])
    assert len(chart._scripts) == before          # 没有下发 update


def test_signal_manager_updates_add_remove_and_hold():
    """tick 中信号出现 / 保持 / 消失；换根时最后两根重新计算。"""
    frame = make_frame()
    chart = make_chart(frame)
    style = FakeStyle(key='low', color='red', marker='triangle', size=12,
                      label=FakeStyle(text='B', size=9, color='blue'))
    manager = rt.SignalManager(chart)

    def rows():
        series = manager.series.get('long_signal')
        return 0 if series is None else len(series.data)

    manager.update(frame, [('long_signal', np.array([0., 1., 0., 0.]), style)])
    assert rows() == 1                       # 第 2 根出现信号
    manager.update(frame, [('long_signal', np.array([0., 1., 1., 0.]), style)])
    assert rows() == 1                       # 条件保持 -> 仍然只有一个
    manager.update(frame, [('long_signal', np.array([0., 1., 0., 1.]), style)])
    assert rows() == 2                       # 末根新信号
    manager.update(frame, [('long_signal', np.array([0., 0., 0., 0.]), style)])
    assert rows() == 0                       # 信号消失 -> 点也删掉
    manager.update(frame, [('long_signal', np.array([0., 0., 0., 1.]), style)])
    assert rows() == 1
    manager.clear()
    assert manager.series == {}


class SignalDataset:
    """`_get_plot_datas` 第 4/8 项带列名和数值的信号数据集替身。"""

    def __init__(self, long_signal, short_signal=None, plot_id=0):
        n = len(long_signal)
        short = np.zeros(n) if short_signal is None else np.asarray(
            short_signal, dtype=float)
        self.plot_id = plot_id
        self._lines = ['cci', 'zero', 'long_signal', 'short_signal']
        self._values = np.column_stack([
            np.zeros(n), np.zeros(n),
            np.asarray(long_signal, dtype=float), short])
        self._plotinfo = FakeStyle(
            signallines=['long_signal', 'short_signal'],
            signalstyle={'long_signal': FakeStyle(show=True, key='low',
                                                  color='red'),
                         'short_signal': FakeStyle(show=True, key='high',
                                                   color='green')})

    def _get_plot_datas(self, key):            # noqa: ARG002
        data = [None] * 14
        data[4] = self._lines
        data[8] = self._values
        return tuple(data)


def test_extract_signals_reads_fresh_dataset():
    """实盘每次重算会换掉指标对象；信号要按 key 现取，不能停在旧值。"""
    strategy = FakeStrategy({'cci': SignalDataset([0., 0., 1., 0.])})
    before = rt.extract_minibt_signals(strategy, 0)
    assert float(np.asarray(before[0][1])[-1]) == 0.0
    # 模拟 tick：最后一根的信号出现（新对象，值和旧的不一样）
    strategy._btindicatordataset['cci'] = SignalDataset(
        [0., 0., 1., 1.])
    after = rt.extract_minibt_signals(strategy, 0)
    assert float(np.asarray(after[0][1])[-1]) == 1.0


def test_signal_manager_reuses_series():
    """更新不能每次重建序列（否则会闪烁 / 报 detach）。"""
    frame = make_frame()
    chart = make_chart(frame)
    style = FakeStyle(key='low', color='red', marker='triangle', size=12)
    manager = rt.SignalManager(chart)
    manager.update(frame, [('long_signal', np.array([0., 1., 0., 0.]), style)])
    series = manager.series['long_signal']
    manager.update(frame, [('long_signal', np.array([0., 1., 1., 0.]), style)])
    assert manager.series['long_signal'] is series


def test_strategy_preload_reads_kline_attribute():
    kline = FakeKline()
    kline._preload = 500
    strategy = FakeStrategy(klines={'k': kline})
    assert rt.strategy_preload(strategy, 'DCE.pp2609_60') == 500
    assert rt.strategy_preload(strategy, 'SHFE.ni2610_60') is None


def test_realtime_history_prepends_and_keeps_newest():
    """无限历史：向前补一批，最新一根不能丢（实时 update 走 chart.update）。"""
    index = pd.date_range('2024-01-01', periods=30, freq='min')
    full = pd.DataFrame({
        'time': index, 'open': np.arange(30.0), 'high': np.arange(30.0) + 1,
        'low': np.arange(30.0), 'close': np.arange(30.0) + 0.5,
        'volume': 1.0})
    chart = make_chart(full.tail(10).reset_index(drop=True))

    def loader(count, before=None):
        data = full
        if before is not None:
            data = data[data['time'] < pd.Timestamp(before)]
        return data.tail(int(count))

    added = []
    history = rt.RealtimeHistory(
        chart, loader, page=8, threshold=3,
        on_load=lambda h, n: added.append(n))
    history.stop()                       # 手动触发，避免 set() 引发的自动翻页
    assert history.load() == 8
    assert len(chart.candle_data) == 18
    assert pd.Timestamp(int(chart.candle_data['time'].max()), unit='s') == \
        full['time'].iloc[-1]
    # 实时又追加了一根新 K 线，再向前翻页不能把它丢掉
    new_bar = full.iloc[-1].copy()
    new_bar['time'] = full['time'].iloc[-1] + pd.Timedelta(minutes=1)
    chart.update(new_bar)
    assert history.load() == 8
    assert pd.Timestamp(int(chart.candle_data['time'].max()), unit='s') == \
        pd.Timestamp(new_bar['time'])
    assert added[:2] == [8, 8]


def test_refresh_market_updates_previous_and_all_new_bars(monkeypatch):
    """换根：上一根用最终值回填，之后每一根新 K 线都 K 线+指标一起补；
    即使一次 feed 跳了多根（指标算得慢）也不能漏根。"""
    index = pd.date_range('2024-01-01', periods=6, freq='min')
    frame_all = pd.DataFrame({
        'time': index, 'open': np.arange(6.0), 'high': np.arange(6.0) + 1,
        'low': np.arange(6.0), 'close': np.arange(6.0) + 0.5,
        'volume': 1.0})
    chart = make_chart(frame_all.iloc[:3].reset_index(drop=True))

    rc = object.__new__(rt.RealtimeChart)
    rc.chart = chart
    rc.indicators = rt.IndicatorManager(chart)
    rc.indicators.align = 'tail'
    rc.signal_manager = rt.SignalManager(chart)
    rc.spans = []
    rc._last_time = pd.Timestamp(frame_all['time'].iloc[2])
    rc.window = type('W', (), {'contract': 'X', 'strategy': 'S'})()
    rc._strategy_obj = lambda: type(
        'S', (), {'_btindicatordataset': {}, '_btklinedataset': {}})()

    values = np.arange(10.0, 16.0)          # 6 根：10..15
    spec = rt.IndicatorSpec(name='ma', overlap=True,
                            values=pd.Series(values[:3]),
                            get_values=lambda: values)
    series = chart.add_series('Line', name='ma')
    series.set(pd.DataFrame({'time': list(frame_all['time'].iloc[:3]),
                             'ma': values[:3]}))
    rc.indicators.series, rc.indicators.specs = [series], [spec]
    monkeypatch.setattr(rt, 'strategy_kline_frame',
                        lambda strategy, contract, tail=None: frame_all)
    chart._scripts.clear()
    rc._refresh_market()

    # K 线补齐到 6 根
    assert len(chart.candle_data) == 6
    # 上一根（index2，值 12）+ 3 根新根（13/14/15）都推送了
    updates = [s for s in chart._scripts if 'series.update' in s
               and '"value"' in s]
    pushed = [float(s.split('"value":')[1].split(',')[0].split('}')[0])
              for s in updates]
    assert pushed == [12.0, 13.0, 14.0, 15.0]


class _MarketApi:
    def __init__(self, changed):
        self.changed = changed
        self.calls = 0

    def is_changing(self, obj, key=None):
        self.calls += 1
        return self.changed


class _MarketStrategy:
    def __init__(self, api, klines):
        self._api = api
        self._btklinedataset = klines


def _market_kline(tq):
    return FakeStyle(_dataset=FakeStyle(tq_object=tq))


def test_market_changed_uses_tq_is_changing():
    frame = make_frame()
    strategy = _MarketStrategy(_MarketApi(True),
                               {'k': _market_kline(frame)})
    assert rt.RealtimeChart._market_changed(strategy) is True
    strategy2 = _MarketStrategy(_MarketApi(False),
                                {'k': _market_kline(frame)})
    assert rt.RealtimeChart._market_changed(strategy2) is False


class _FeedStrategy:
    """`feed()` 用的假策略：wait_update 恒返回 True，可调用（实盘入口）。"""

    _is_live_trading = True          # 走 item(step_only=not changed) 分支

    def __init__(self, api, klines):
        self._api = api
        self._btklinedataset = klines
        self.steps = []

    def wait_update(self, timeout=None):
        return True

    def __call__(self, step_only=False):
        self.steps.append(step_only)


def _feed_chart(api):
    strategy = _FeedStrategy(api, {'k': _market_kline(make_frame())})
    rc = object.__new__(rt.RealtimeChart)
    rc.strategies = [strategy]
    rc._disconnected = False
    rc._switching = False
    rc._lock = threading.RLock()
    rc._push_interval = 0.0                 # 默认：不限速
    rc._last_push = 0.0
    rc._last_time = None
    rc.window = FakeStyle(contract='X', strategy='S')
    rc._strategy_obj = lambda: strategy
    calls = []
    rc._refresh_market = lambda push_indicators=True: calls.append(
        ('kline', push_indicators))
    rc._sync_history_cache = lambda: calls.append(('cache', None))
    return rc, strategy, calls


def test_feed_pushes_kline_every_loop_even_if_market_unchanged():
    """行情没变：仍推 K 线（push_indicators=False），但不重算指标/信号。"""
    rc, strategy, calls = _feed_chart(_MarketApi(False))
    rc.feed(timeout=0)
    assert strategy.steps == [True], strategy.steps     # step_only=True
    assert calls == [('kline', False)], calls           # 只推 K 线


def test_feed_recomputes_indicators_when_market_changed():
    """行情变了：K 线 + 指标 + 信号一起推，并同步无限历史缓存。"""
    rc, strategy, calls = _feed_chart(_MarketApi(True))
    rc.feed(timeout=0)
    assert strategy.steps == [False], strategy.steps
    assert calls == [('kline', True), ('cache', None)], calls


def test_market_changed_falls_back_to_true():
    # 没有天勤 api / 没有 tq_object -> 保持旧行为（每次都算）
    frame = make_frame()
    assert rt.RealtimeChart._market_changed(
        _MarketStrategy(None, {'k': _market_kline(frame)})) is True
    assert rt.RealtimeChart._market_changed(
        _MarketStrategy(_MarketApi(False), {'k': _market_kline(None)})) is True


class _PushKline:
    symbol = 'X'
    cycle = 60

    def __init__(self, tq):
        self._dataset = FakeStyle(tq_object=tq)


class _CloseApi:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_realtime_disconnect_closes_api_and_is_idempotent():
    api = _CloseApi()
    rc = object.__new__(rt.RealtimeChart)
    rc.strategies = [FakeStyle(_api=api)]
    rc._disconnected = False
    rc._api_factory = None
    rc._period_ms = 100
    rc._loop_thread = None
    rc.chart = FakeStyle(is_alive=False)
    rc.window = FakeStyle(replace_setting=lambda *a, **k: None,
                          set_contract=lambda *a, **k: None)
    rc.disconnect()
    rc.disconnect()                       # 重复点击不应再次 close
    assert rc._disconnected is True and api.closed is True


def test_realtime_disconnect_reconnect_rebinds_api():
    class _Tq(_CloseApi):
        def __init__(self, name):
            super().__init__()
            self.name = name

        def get_account(self):
            return ('acct', self.name)

        def get_kline_serial(self, symbol, cycle, length):
            return ('kline', self.name)

        def get_tick_serial(self, symbol):
            return ('tick', self.name)

    old, new = _Tq('old'), _Tq('new')
    dataset = FakeStyle(tq_object='old_kline', tq_tick='old_tick')
    kline = FakeStyle(symbol='X', cycle=60, _dataset=dataset, _preload=200)
    strategy = FakeStyle(_api=old, _btklinedataset={'k': kline})
    menu = []
    rc = object.__new__(rt.RealtimeChart)
    rc.strategies = [strategy]
    rc._disconnected = False
    rc._api_factory = lambda: new
    rc._period_ms = 100
    rc._loop_thread = None
    rc.chart = FakeStyle(is_alive=False)
    rc.window = FakeStyle(
        contract='X_60', strategy='S',
        replace_setting=lambda o, n, cb=None: menu.append((o, n)),
        set_contract=lambda *a, **k: None)
    rc.disconnect()
    assert old.closed is True and rc._disconnected is True
    assert menu[-1] == ('断开连接', '重新连接')
    rc.reconnect()
    assert strategy._api is new and rc._disconnected is False
    assert dataset.tq_object == ('kline', 'new')
    assert menu[-1] == ('重新连接', '断开连接')


def test_realtime_reset_returns_to_first_strategy_and_contract():
    class Window:
        strategies = ['A', 'B']
        strategy = 'B'
        contract = 'B_c2'

        def contracts_of(self, name):
            return {'A': ['A_c1'], 'B': ['B_c1']}[name]

        def set_strategy(self, name, contract=None):
            self.strategy, self.contract = name, contract

    rc = object.__new__(rt.RealtimeChart)
    rc.window = Window()
    rc.chart = FakeStyle()
    rc.reset()
    assert rc.window.strategy == 'A' and rc.window.contract == 'A_c1'


def test_push_throttle_and_new_bar_override():
    ns0 = 1704067200000000000
    ns1 = 1704067260000000000
    tq = pd.DataFrame({'datetime': [ns0, ns1]})
    strategy = FakeStyle(_btklinedataset={'k': _PushKline(tq)})
    chart = object.__new__(rt.RealtimeChart)
    chart.window = FakeStyle(contract='X_60')
    chart._strategy_obj = lambda: strategy
    chart._push_interval = 100.0
    chart._last_time = pd.Timestamp(ns1)          # 已是最新一根
    chart._last_push = time.monotonic()
    assert chart._should_push() is False          # 刚推过 -> 节流
    chart._last_time = pd.Timestamp(ns0)          # 落后一根
    chart._last_push = time.monotonic()
    assert chart._should_push() is True           # 有新根 -> 立即推
    chart._push_interval = 0.0
    assert chart._should_push() is True           # 关闭节流


def test_fast_time_to_datetime_matches_reference():
    pytest.importorskip('minibt')
    from minibt.indicators.core import _fast_time_to_datetime
    from minibt.utils import time_to_datetime
    values = pd.Series([1704067200000000000, 1704067260000000000],
                       dtype='int64')
    fast = list(_fast_time_to_datetime(values))
    slow = list(values.apply(time_to_datetime))
    assert fast == slow


def test_view_values_uses_time_indexed_cache():
    """实盘策略只算 preload 根时，历史部分从全量缓存按时间取。"""
    frame = make_frame(6)
    chart = make_chart(frame.iloc[:3])
    manager = rt.IndicatorManager(chart)
    manager.align = 'tail'
    times = rt.IndicatorManager._frame_seconds(frame)
    spec = rt.IndicatorSpec(name='ma', overlap=True,
                            values=pd.Series([10., 11, 12, 13, 14, 15]),
                            get_values=lambda: np.array([13., 14, 15]))
    spec.cached_series = pd.Series([10., 11, 12, 13, 14, 15], index=times)
    # 视图是最后 3 根 -> 缓存按时间取到 13/14/15
    view = frame.tail(3).reset_index(drop=True)
    assert list(manager.view_values(spec, view)) == [13.0, 14.0, 15.0]
    # 视图扩到 5 根 -> 取到 11..15（实时值只有最后 3 个，但缓存是全量）
    view5 = frame.tail(5).reset_index(drop=True)
    assert list(manager.view_values(spec, view5)) == [11.0, 12.0, 13.0,
                                                      14.0, 15.0]


def test_apply_histogram_colors_uses_candle_rule_colors():
    """K 线用 color_by 配色时，MACD 柱体也应跟着用同一组颜色（不再是默认红绿）。"""
    frame = make_frame()
    chart = make_chart(frame)
    series = chart.add_series('Histogram', name='macdh')
    series.set(pd.DataFrame({'time': list(frame['time']),
                             'macdh': [-1.0, 2.0, -3.0, 4.0]}))
    spec = rt.IndicatorSpec(name='macdh', overlap=False,
                            values=pd.Series([-1.0, 2.0, -3.0, 4.0]),
                            kind='Histogram')
    spec.source = 'macd'
    kline = FakeKline()
    kline.__dict__['_color_rules'] = [{
        'condition': np.array([True, False, True, False]),
        'color': 'lime', 'else_color': 'tomato', 'options': {}}]
    strategy = FakeStrategy({'macd': FakeDataset()}, {'k': kline})
    manager = FakeManager([series], [spec])
    rt.apply_histogram_colors(manager, strategy, 'DCE.pp2609_60', 4)
    out = scripts(chart)
    assert 'lime' in out and 'tomato' in out
    assert '#26a69a' not in out                   # 默认色不应再出现
    assert spec.up_color == 'lime' and spec.down_color == 'tomato'


# --------------------------------------------------------------------------
# 1.3.0：btplot 的 gui 归一化 / Gui 枚举 / main 保护检测
# --------------------------------------------------------------------------

def test_resolve_btplot_gui_accepts_gui_enum():
    """`Gui.*` 枚举（str-Enum）必须能被 btplot 识别 —— 3.11+ 的 str(Gui.X)
    会得到 'Gui.X' 而不是它的值，早先这里直接报「未知的 gui」。"""
    pytest.importorskip('bokeh')
    from minibt import Gui
    from minibt.btplot import _resolve_btplot_gui
    assert _resolve_btplot_gui(None) == 'pylightcharts'
    assert _resolve_btplot_gui('') == 'pylightcharts'
    assert _resolve_btplot_gui(Gui.Pylightcharts) == 'pylightcharts'
    assert _resolve_btplot_gui(Gui.LightChart) == 'pylightcharts'
    assert _resolve_btplot_gui(Gui.PylightchartsWeb) == 'pylightcharts_web'
    assert _resolve_btplot_gui(Gui.Browser) == 'pylightcharts_web'
    assert _resolve_btplot_gui(Gui.Bokeh) == 'bokeh'
    assert _resolve_btplot_gui(Gui.Jupyter) == 'jupyter'
    assert _resolve_btplot_gui(' BOKEH ') == 'bokeh'
    with pytest.raises(ValueError):
        _resolve_btplot_gui('plotly')


def test_gui_enum_str_is_its_value():
    from minibt import Gui
    assert str(Gui.Bokeh) == 'bokeh'
    assert f'{Gui.Pylightcharts}' == 'pylightcharts'
    assert f'{Gui.PylightchartsWeb}' == 'pylightcharts_web'


def test_main_guard_missing_detects_the_guard(tmp_path):
    """入口脚本缺少 main 保护时应当被识别（spawn 平台才会需要它）。"""
    import types
    from minibt.utils import main_guard_missing
    if sys.platform not in ('win32', 'darwin'):
        pytest.skip('只有 spawn 平台（Windows / macOS）需要 main 保护')

    unguarded = tmp_path / 'unguarded.py'
    unguarded.write_text('print(1)\n', encoding='utf-8')
    guarded = tmp_path / 'guarded.py'
    guarded.write_text('if __name__ == "__main__":\n    print(1)\n',
                       encoding='utf-8')
    assert main_guard_missing(types.SimpleNamespace(__file__=str(unguarded)))
    assert not main_guard_missing(types.SimpleNamespace(__file__=str(guarded)))
    # 交互式 / Notebook：没有 __file__，交给上层判断（不报 True）
    assert not main_guard_missing(types.SimpleNamespace())


def test_btplot_native_window_blocks_until_closed(monkeypatch):
    """脚本里原生窗口必须阻塞显示。

    原生窗口由子进程渲染、且子进程随父进程一起结束 —— 如果 `btplot` 立刻返回，
    脚本一结束界面就"一闪而过"（1.3.0 前就是这个表现）。
    """
    pytest.importorskip('bokeh')
    import minibt.strategy.realtime as rt_module
    import minibt.utils as utils_module
    from minibt import Gui, LocalDatas

    seen = []

    class FakeChart:
        def __init__(self, *args, **kwargs):
            seen.append(('init', bool(kwargs.get('browser')),
                         kwargs.get('theme'), kwargs.get('title')))

        def show(self, block=False):
            seen.append(('show', bool(block)))

        def set_backtest_from_strategy(self, *args, **kwargs):
            pass

    monkeypatch.setattr(rt_module, 'RealtimeChart', FakeChart)
    # 伪造"入口脚本有 main 保护"，否则会走浏览器回退分支
    monkeypatch.setattr(utils_module, 'main_guard_missing',
                        lambda *args, **kwargs: False)

    indicator = LocalDatas.test.kline.tradingview.SPMATrendNAL()

    seen.clear()
    indicator.btplot()                       # 默认 = 原生窗口
    # 原生引擎 + 1.3.0 起默认主题是 light（不再是"跟随策略"的 dark）
    init = next(item for item in seen if item[0] == 'init')
    assert init[1] is False, seen            # 不是浏览器
    assert init[2] == 'light', seen          # 默认浅色
    # 1.3.0 起标题按用途给：btplot 是**静态指标图**，不能写"实时图表"
    assert init[3] and '指标图' in init[3] and '实时' not in init[3], seen
    assert ('show', True) in seen, seen      # 阻塞显示

    seen.clear()
    indicator.btplot(theme='dark')           # 显式深色仍然生效
    assert any(item[0] == 'init' and item[2] == 'dark' for item in seen), seen

    seen.clear()
    indicator.btplot(gui=Gui.PylightchartsWeb)   # 网页版：静态页自包含，不用等
    assert ('show', False) in seen, seen


def test_divergence_many_per_point_texts_reach_both_charts():
    """逐点信号文本（`signal_text()` 钩子）必须能从**访问器**调用里产出来。

    1.3.0 前的 bug：`self.data.tradingview.DivergenceMany()` 走装饰器路径，
    那里把「没传 signal_text」写成了显式的 ``None``，于是 core.py 的
    ``kwargs.pop("signal_text", cls.signal_text)`` 拿到 None —— 类上定义的
    ``signal_text()`` 钩子**永远不执行**，异常还被静默吞掉，结果 bokeh 的
    LabelSet 与 pylightcharts 的逐点文本两边都一个都不显示。
    """
    from minibt import Bt, Config, LocalDatas, Strategy
    from minibt.indicators.tradingview import _param

    class FakeParams:                      # 属性可访问的"对象型"参数
        show_names = 'Short'

    assert _param({'show_names': 'Full'}, 'show_names', 'X') == 'Full'
    assert _param(FakeParams(), 'show_names', 'X') == 'Short'
    assert _param({}, 'div_table', ()) == ()

    class S(Strategy):
        config = Config(islog=False)

        def __init__(self):
            self.data = self.get_kline(LocalDatas.pp2609_60, height=300)
            self.dm = self.data.tradingview.DivergenceMany()

        def next(self):
            pass

    bt = Bt(auto=False)
    bt.addstrategy(S)
    bt.run(isplot=False)

    strategy = bt.strategies[0]
    texts = strategy.dm._plotinfo.signal_texts
    long_texts = [x for x in np.asarray(texts['long_signal'], dtype=object)
                  if isinstance(x, str)]
    assert long_texts, 'signal_text() 钩子没有产出文本（钩子又被跳过了？）'
    assert any('\n' in x for x in long_texts), long_texts[:3]   # 多行文本

    # pylightcharts 侧用的是同一份 signal_texts，也应该逐点拿得到
    extracted = rt.extract_minibt_signal_texts(strategy, 0)
    got = [x for x in extracted['long_signal'] if isinstance(x, str)]
    assert got == long_texts


def test_pmax_on_rsi_t3_signals_styled_and_in_its_own_pane():
    """PMaxOnRsiT3 的 Buy/Sell：绿/红底白字、锚 `pmax`、画在 RSI 副图。

    早期写法是 ``SignalStyle('low'/'high', ..., overlap=True)`` —— 信号跑到
    主图 K 线上、还是个灰色默认框。副图是 0~100 的 RSI 轴，必须锚 `pmax`
    并用 ``overlap=False`` 落回指标自己的 pane。
    """
    import pandas as pd
    from minibt import Config, LocalDatas
    from minibt.btplot import _BtplotStrategy
    from minibt.strategy.realtime import (IndicatorManager,
                                          extract_minibt_indicators,
                                          extract_minibt_signals)
    from pylightcharts.headless import HeadlessChart

    k = LocalDatas.pp2609_60.kline
    ind = k.tradingview.PMaxOnRsiT3()
    style = ind._plotinfo.signalstyle
    for name, text, bg in (('long_signal', 'Buy', 'green'),
                           ('short_signal', 'Sell', 'red')):
        item = style[name]
        assert str(item.key) == 'pmax', item.key
        assert item.overlap is False
        assert item.label.text == text
        assert item.label.color == 'white'
        assert item.label.background_fill_color == bg

    chart = HeadlessChart()
    times = list(pd.to_datetime(k['datetime']))
    chart.set(pd.DataFrame({'time': times, 'open': k['open'],
                            'high': k['high'], 'low': k['low'],
                            'close': k['close']}))
    strat = _BtplotStrategy(k, ind, [ind], Config(), 'PmR3')
    manager = IndicatorManager(chart)
    manager.build(chart.candle_data,
                  extract_minibt_indicators(strat, 0), None)
    signals = extract_minibt_signals(strat, 0, manager.panes)
    found = {str(name): (pane, anchor)
             for name, _values, _style, anchor, pane in signals}
    assert found['long_signal'][0] > 0        # 副图，不是主图 pane 0
    assert found['short_signal'][0] > 0
    assert found['long_signal'][1] is not None    # 锚到 pmax 线本身
    assert found['short_signal'][1] is not None


def test_machine_learning_rsi_conditional_colors_barcolor_and_table():
    """MachineLearningRSI 对齐原码：副图条件色 RSI + 主图 barcolor + 表格。"""
    from minibt import Config, LocalDatas
    from minibt.btplot import _BtplotStrategy
    from minibt.strategy.realtime import apply_indicator_tables
    from pylightcharts.headless import HeadlessChart
    import pandas as pd

    k = LocalDatas.test.kline
    ind = k.tradingview.MachineLearningRSI()
    obj = ind.pandas_object

    # 副图（不是主图叠加）
    overlaps = ind._plotinfo.overlap
    assert overlaps is False or not any(overlaps.values())

    # 条件色：RSI>50 落在 rsi_bull、其余落在 rsi_bear
    rsi = np.asarray(obj['rsi'], float)
    bull = np.asarray(obj['rsi_bull'], float)
    bear = np.asarray(obj['rsi_bear'], float)
    up = np.isfinite(rsi) & (rsi > 50)
    down = np.isfinite(rsi) & (rsi <= 50)
    assert up.any() and down.any()
    assert np.allclose(bull[up], rsi[up])
    assert np.allclose(bear[down], rsi[down])

    # barcolor：给 K 线挂了逐根配色规则
    assert k.__dict__.get('_color_rules'), 'barcolor 规则没挂到 K 线'

    # 表格：类上的 `TableStyle`（像 LineStyle 一样）+ 桥接层落地（可拖动）
    style = ind._plotinfo.tablestyle
    assert style is not None and style.draggable is True
    assert style.live is True                    # 默认跟随十字光标
    chart = HeadlessChart()
    times = list(pd.to_datetime(k['datetime']))
    chart.set(pd.DataFrame({'time': times, 'open': k['open'],
                            'high': k['high'], 'low': k['low'],
                            'close': k['close']}))
    strat = _BtplotStrategy(k, ind, [ind], Config(), 'MLRSI')
    contract = f'{k.symbol}_{k.cycle}'
    tables = apply_indicator_tables(chart, strat, contract, None, plot_id=0)
    key = 'MachineLearningRSI_0'
    assert key in tables
    table = tables[key]
    rows = [dict(row) for row in table.values()]
    assert len(rows) == 5 and rows[0][str(style.headings[0])] == 'RSI'
    # 表格跟随十字光标：移到第 100 根显示那根的 RSI，移出回最后一根
    # `Window.handlers` 是类级共享 dict（多张图共存），要按本图的 salt 取
    handler = chart.win.handlers[
        f'crosshair_move{chart.id[chart.id.index(".") + 1:]}']
    rsi = np.asarray(ind.pandas_object['rsi'], dtype=float)
    handler(int(chart.candle_data['time'].iloc[100]), 100.0)
    hovered = [dict(row) for row in table.values()]
    assert hovered[0][str(style.headings[1])] == f'{rsi[100]:.2f}'
    handler('', '')                              # JS 移出 K 线发空串
    back = [dict(row) for row in table.values()]
    assert back[0][str(style.headings[1])] == f'{rsi[-1]:.2f}'
    # 实时刷新：桥接层现取 ``{线名: 最新整条值}``（含 isplot=False 的 rsi），
    # 并暴露一个刷新闭包给 RealtimeChart 在行情推进时调用
    from minibt.strategy.realtime import _table_live_values
    live = _table_live_values(strat, key)
    assert live and 'rsi' in live
    assert callable(getattr(chart, '_refresh_indicator_tables'))
    chart._refresh_indicator_tables(None)
    assert [dict(row) for row in table.values()][0][
        str(style.headings[1])] == f'{float(live["rsi"][-1]):.2f}'

    again = apply_indicator_tables(chart, strat, contract, tables, plot_id=0)
    assert again[key] is table

    # header / footer / 间距
    style.header = 'MLRSI'
    style.footer = 'streaming'
    style.margin_x = 10
    style.margin_y = 6
    apply_indicator_tables(chart, strat, contract, tables, plot_id=0)
    js = chart.to_scripts()
    assert 'makeSection' in js
    assert 'MLRSI' in js and 'streaming' in js


def test_custombase_hooks_default_to_none():
    """`CustomBase` 预置的 `table_rows` / `signal_text` 默认是 None（= 没设）。

    覆写了 `table_rows` 的指标会把它绑到 `IndFrame` 的 `PlotInfo`；
    没覆写的（仍是 `None`）不会平白多出一块空表格，也不会报错。
    """
    from minibt import LocalDatas
    from minibt.indicators.core import CustomBase

    assert CustomBase.table_rows is None
    assert CustomBase.signal_text is None
    assert CustomBase.tablestyle is None

    k = LocalDatas.test.kline
    ind = k.tradingview.MachineLearningRSI()
    assert callable(getattr(ind._plotinfo, 'table_rows', None))
    assert ind.params.get('color_mode') == 'Trend Following'   # 实例参数已挂上

    other = k.tradingview.MACDBollingerBands()
    assert getattr(other._plotinfo, 'table_rows', None) is None
    assert list(other.pandas_object.columns)  # 指标照常算出


def test_indicator_table_values_align_to_replay_prefix():
    """回放（`align='head'`）表格按**已放出根数**取值，不是全量最后一根。

    回放时策略在全量数据上跑，指标值也是全量；表格必须按图表长度切片。
    """
    from minibt import Config, LocalDatas
    from minibt.btplot import _BtplotStrategy
    from minibt.strategy.realtime import apply_indicator_tables, _table_live_values
    from pylightcharts.headless import HeadlessChart
    import pandas as pd

    k = LocalDatas.test.kline
    ind = k.tradingview.MachineLearningRSI()
    strat = _BtplotStrategy(k, ind, [ind], Config(), 'MLRSI')
    key = 'MachineLearningRSI_0'
    full = _table_live_values(strat, key)
    head = _table_live_values(strat, key, 120, 'head')
    tail = _table_live_values(strat, key, 120, 'tail')
    assert len(head['rsi']) == 120 and len(tail['rsi']) == 120
    assert head['rsi'][-1] == full['rsi'][119]      # 前 N 根（回放）
    assert tail['rsi'][-1] == full['rsi'][-1]       # 最后 N 根（实时）

    epoch = (pd.to_datetime(k['datetime']).astype('int64') // 10 ** 9).tolist()
    base = pd.DataFrame({'time': epoch, 'open': k['open'], 'high': k['high'],
                         'low': k['low'], 'close': k['close']})
    chart = HeadlessChart()
    chart.set(base.iloc[:120])                      # 已放出前 120 根
    tables = apply_indicator_tables(chart, strat, f'{k.symbol}_{k.cycle}',
                                    None, plot_id=0, align='head')
    table = tables[key]
    first_row = [dict(row) for row in table.values()][0]
    assert list(first_row.values())[1] == f'{float(full["rsi"][119]):.2f}'

    # 推进到 200 根后刷新 -> 表格跟着 K 线走
    chart.candle_data = base.iloc[:200].reset_index(drop=True)
    chart._refresh_indicator_tables(None)
    refreshed = [dict(row) for row in table.values()][0]
    assert list(refreshed.values())[1] == f'{float(full["rsi"][199]):.2f}'

    # 光标跟随：**现取** candle_data['time']，推进后移到新放出的那根也能对上
    # `Window.handlers` 是类级共享 dict（多张图共存），要按本图的 salt 取
    handler = chart.win.handlers[
        f'crosshair_move{chart.id[chart.id.index(".") + 1:]}']
    handler(int(chart.candle_data['time'].iloc[180]), 1.0)
    hovered = [dict(row) for row in table.values()][0]
    assert list(hovered.values())[1] == f'{float(full["rsi"][180]):.2f}'

    # 行结构不变时**就地 updateCell**，不 clearRows（否则鼠标移动时会一闪一闪）
    chart._scripts.clear()
    handler(int(chart.candle_data['time'].iloc[181]), 1.0)
    js = '\n'.join(chart._scripts)
    assert 'updateCell' in js and 'clearRows' not in js


def test_ghost_tangent_crossings_arcs_are_two_coloured():
    """椭圆弧按上摆/下摆拆成两列上色（原码 `polarity ? up_color : down_color`）。

    旧实现把上/下摆全画进同一个 `zigzag` 线列（单一绿色），原图却是
    上摆绿 / 下摆红两组颜色 —— 所以拆成 `zigzag_up` / `zigzag_down`。
    """
    from minibt import LocalDatas
    k = LocalDatas.test.kline
    ind = k.tradingview.GhostTangentCrossings()
    obj = ind.pandas_object
    for name in ('zigzag_up', 'zigzag_down',
                 'ghost_zigzag_up', 'ghost_zigzag_down',
                 'equipoint_up', 'equipoint_down',
                 'ghost_equipoint_up', 'ghost_equipoint_down'):
        assert name in obj.columns, name
    assert 'zigzag' not in obj.columns          # 旧的单色列已拆开
    assert np.isfinite(np.asarray(obj['zigzag_up'], float)).any()
    assert np.isfinite(np.asarray(obj['zigzag_down'], float)).any()
    style = ind._plotinfo.linestyle
    assert (style['zigzag_up'].line_color
            != style['zigzag_down'].line_color)


def test_ghost_tangent_crossings_keeps_all_arcs_by_default():
    """默认 `max_zig=0` = 保留全部历史弧（原码默认 10 只留最近 10 段）。

    原码每根都 `zig_zags.shift().delete()`，所以长图上早期一段弧都没有；
    minibt 默认不淘汰，传 `max_zig=10` 才恢复原码行为。
    """
    from minibt import LocalDatas
    k = LocalDatas.test.kline

    def span(ind):
        obj = ind.pandas_object
        finite = (np.isfinite(np.asarray(obj['zigzag_up'], float))
                  | np.isfinite(np.asarray(obj['zigzag_down'], float)))
        idx = np.flatnonzero(finite)
        return int(idx.min()), int(idx.max())

    first_default, last_default = span(k.tradingview.GhostTangentCrossings())
    first_capped, last_capped = span(
        k.tradingview.GhostTangentCrossings(max_zig=10))
    assert first_default < first_capped     # 默认保留到更早的历史
    assert first_capped > 8000              # 原码上限只覆盖最近一小段
    assert last_default == last_capped      # 最近一段弧两边一致


def test_signal_text_style_maps_to_both_engines():
    """一套逐点文本样式键 → 两个引擎各自的渲染参数。

    minibt 只定义一份规范键（`utils.SIGNAL_TEXT_STYLE_KEYS`），
    pylightcharts 侧由 `_text_shape_kwargs()` 翻译成 `shapes.text(...)` 参数，
    bokeh 侧由 `_bokeh_text_options()` 翻译成 `LabelSet` 关键字 —— 这样同一个
    参数设置在两个图表上同时生效，且键名一致。
    """
    from minibt.utils import (SignalLabel, normalise_signal_text_style,
                              resolve_signal_text_style)

    style = {'font_size': 16, 'line_height': 1.5, 'text_color': '#ffd400',
             'text_align': 'left', 'offset_x': 6, 'offset_y': -3,
             'background_fill_color': '#222222',
             'background_fill_alpha': 0.6,
             'border_line_color': '#888888', 'font_weight': 'bold',
             'font_family': 'serif', 'font_style': 'italic'}
    # 别名 + '12pt' 这种写法也能吃
    assert normalise_signal_text_style({'text_font_size': '12pt'}) == {
        'font_size': 12.0}
    assert normalise_signal_text_style({'font_color': 'red'}) == {
        'text_color': 'red'}
    assert normalise_signal_text_style({'text_font_style': 'bold italic'}) == {
        'font_weight': 'bold', 'font_style': 'italic'}

    resolved = resolve_signal_text_style(None, True, point=style)
    shape_kwargs = rt._text_shape_kwargs(resolved)          # pylightcharts
    assert shape_kwargs['font_size'] == 16
    assert shape_kwargs['color'] == '#ffd400'
    assert shape_kwargs['line_height'] == 1.5
    assert shape_kwargs['align'] == 'left'
    assert shape_kwargs['offset_x'] == 6 and shape_kwargs['offset_y'] == -3
    assert shape_kwargs['background_color'] == '#222222'
    assert shape_kwargs['border_color'] == '#888888'

    pytest.importorskip('bokeh')
    import minibt.strategy.bokeh_plot as bp
    bokeh_kwargs = bp._bokeh_text_options(resolved)         # bokeh
    assert bokeh_kwargs['text_font_size'] == '16pt'
    assert bokeh_kwargs['text_color'] == '#ffd400'
    assert bokeh_kwargs['text_align'] == 'left'
    assert bokeh_kwargs['text_font'] == 'serif'
    assert bokeh_kwargs['text_font_style'] == 'bold italic'
    assert bokeh_kwargs['background_fill_color'] == '#222222'
    # 像素偏移要翻成 bokeh 的 x_offset / y_offset（两者都是屏幕单位）
    assert bokeh_kwargs['x_offset'] == 6 and bokeh_kwargs['y_offset'] == -3
    # 规范键不能原样漏给 LabelSet：bokeh 不认 offset_y / line_height / padding，
    # 直接塞进去会 `AttributeError: unexpected attribute 'offset_y' to LabelSet`
    from bokeh.models import LabelSet
    allowed = set(LabelSet.properties())
    assert set(bokeh_kwargs) <= allowed, sorted(set(bokeh_kwargs) - allowed)
    assert 'offset_y' not in bokeh_kwargs
    assert 'line_height' not in bokeh_kwargs

    # 优先级：指标级 < 逐线 label < 逐点
    label = SignalLabel('B', 12, 'bold', 'blue')
    label.set_text_style(font_size=14, text_color='green')
    line = resolve_signal_text_style(None, True, label=label)
    assert line['font_size'] == 14 and line['text_color'] == 'green'
    point = resolve_signal_text_style(None, True, label=label,
                                      point={'text_color': 'red'})
    assert point['text_color'] == 'red' and point['font_size'] == 14

    # SignalLabel 自动算出来的 x/y_offset 不算用户样式（否则会和引擎自身的
    # 居中叠加成双倍偏移）
    auto = SignalLabel('B').set_position('long_signal', 'low')
    assert 'offset_x' not in resolve_signal_text_style(None, True, label=auto)


def test_signal_style_set_text_style_works_in_a_class_body():
    """在**类体**里直接 `SignalStyle(...).set_text_style(...)` 不能报错。

    类体求值时 `SignalStyle.name` 还不存在（只有 `set_label` /
    `set_default_label` 才会设它），早期实现会抛
    `AttributeError: 'SignalStyle' object has no attribute 'name'` —— 也就是在
    `DivergenceMany` 类里加 `signalstyle = dict(... .set_text_style(...))` 时
    遇到的 **import 期**报错。
    """
    from minibt.utils import SignalLabel

    src = (
        "from minibt import SignalStyle, Colors, Markers\n"
        "class Probe:\n"
        "    signalstyle = dict(\n"
        "        long_signal=SignalStyle('low', Colors.bull_color,\n"
        "                               Markers.translate).set_text_style(\n"
        "            font_size=14, text_color='#ffd400', line_height=1.4,\n"
        "            background_fill_color='#222222'),\n"
        "        short_signal=SignalStyle('high', Colors.bear_color,\n"
        "                                Markers.translate).set_text_style(\n"
        "            font_size=14))\n"
    )
    namespace: dict = {}
    exec(src, namespace)                       # 类体求值：以前这里就炸

    style = namespace['Probe'].signalstyle['long_signal']
    assert isinstance(style.label, SignalLabel)
    assert style.label.size == 14
    assert style.label.line_height == 1.4
    assert style.label.background_fill_color == '#222222'
    # SignalLabel.vars 仍用老的 bokeh 风格键名，两者能互相翻译
    assert style.label.vars['text_font_size'] == '14pt'
    assert style.label.vars['text_color'] == '#ffd400'


# --------------------------------------------------------------------------
# 多合约回测结果页：每个合约都要有**它自己**的交易信号 + 止损/止盈线
# --------------------------------------------------------------------------

class FakeStopLines:
    """`KLine.stop_lines`（IndFrame）的替身。"""

    def __init__(self, stop, target, plot_id=0, isplot=True, lineinfo=None):
        self.plot_id = plot_id
        self.pandas_object = pd.DataFrame({
            'stop_price': np.asarray(stop, dtype=float),
            'target_price': np.asarray(target, dtype=float)})
        self._isplot = isplot
        self._lineinfo = dict(lineinfo or {})

    def _get_plot_datas(self, key):                # noqa: ARG002
        data = [None] * 14
        data[0] = self.plot_id
        data[1] = self._isplot
        data[3] = ['stop_lines_stop_price', 'stop_lines_target_price']
        data[4] = ['stop_price', 'target_price']
        data[10] = {'linestyle': self._lineinfo}
        return tuple(data)


class FakeKlineSetting:
    def __init__(self, stop_lines, isstop=True):
        self.stop_lines = stop_lines
        self.isstop = isstop


class FakeStopKline:
    def __init__(self, symbol, cycle, stop_lines):
        self.symbol = symbol
        self.cycle = cycle
        self._klinesetting = FakeKlineSetting(stop_lines)


def _multi_contract_strategy():
    """两个合约：各自 1 条 long_signal；合约 0 有止损线，合约 1 全 NaN。"""
    n = 10
    frame0 = make_frame(n)
    frame1 = make_frame(n)
    signal_style = {'long_signal': FakeStyle(marker='triangle', color='lime')}
    values0 = np.zeros((n, 1))
    values0[2, 0] = 1.0
    values1 = np.zeros((n, 1))
    values1[4, 0] = 1.0
    sig0 = FakeSignalDataset(['long_signal'], values0, signal_style, plot_id=0)
    sig1 = FakeSignalDataset(['long_signal'], values1, signal_style, plot_id=1)
    stop0 = FakeStopLines([np.nan, np.nan] + [10.0] * (n - 2),
                          [np.nan, np.nan] + [20.0] * (n - 2), plot_id=0)
    stop1 = FakeStopLines([np.nan] * n, [np.nan] * n, plot_id=1)
    klines = {
        # `strategy_contracts` 拼的是 `f'{symbol}_{cycle}'` -> DCE.l2609_60
        'k0': FakeStopKline('DCE.l2609', '60', stop0),
        'k1': FakeStopKline('DCE.pp2609', '60', stop1),
    }
    # 关键：`_btindicatordataset` 里 `stop_lines` 会被后一个合约覆盖（只剩 stop1）
    datasets = {'sig0': sig0, 'sig1': sig1, 'stop_lines': stop1}
    return FakeStrategy(datasets, klines), frame0, frame1


def test_extract_stop_line_specs_is_per_contract_and_skips_all_nan():
    strategy, *_ = _multi_contract_strategy()
    spec0 = rt._extract_stop_line_specs(strategy, 0)
    assert {s.name for s in spec0} == {'stop_price', 'target_price'}
    assert all(s.source == 'stop_lines' for s in spec0)
    assert all(np.isfinite(np.asarray(s.values, dtype=float)).any()
               for s in spec0)
    # 合约 1 的止损线全 NaN -> 一条都不出（用户要求「全 nan 可以不显示」）
    assert rt._extract_stop_line_specs(strategy, 1) == []
    # `extract_minibt_indicators` 也不能把被覆盖的 stop_lines 算到别的合约头上
    inds0 = rt.extract_minibt_indicators(strategy, 0)
    assert any(s.source == 'stop_lines' for s in inds0)


def test_info_page_draws_per_contract_signals_and_stop_lines(monkeypatch):
    strategy, frame0, frame1 = _multi_contract_strategy()
    # `strategy_watermark` 内部用相对导入 `from ..utils import ...`，本测试是
    # 以独立文件加载 `realtime.py`（没有父包），这里直接绕过水印。
    monkeypatch.setattr(rt, 'strategy_watermark', lambda *a, **k: None)

    chart = HeadlessChart(width=800, height=600)
    chart.set(frame0)
    pane1 = chart.add_pane()
    series1 = chart.pane_add_series(pane1, 'Candlestick',
                                    name='DCE.pp2609_60')
    series1.set(frame1)

    class Window:
        contract_panes = [series1]
        _contract_panes_for = ['DCE.pp2609_60']

        def _main_contract(self):
            return 'DCE.l2609_60'

        def loader(self, name, contract):
            return frame1 if contract == 'DCE.pp2609_60' else frame0

    rc = object.__new__(rt.RealtimeChart)
    rc.chart = chart
    rc.window = Window()
    rc.indicators = FakeStyle(panes={})
    rc._info_overlays = []
    rc._theme_name = 'dark'
    rc._strategy_obj = lambda: strategy
    rc.palette = lambda: ['#111111', '#222222']

    rc._apply_info_decorations()

    lines = [(getattr(line, 'name', ''), line.pane_index)
             for line in chart._lines]
    # 两个合约各自都有自己的交易信号
    assert ('long_signal', 0) in lines
    assert ('long_signal', 1) in lines
    # 合约 0 的止损/止盈线画在主图；合约 1 全 NaN -> 不画
    assert ('stop_price', 0) in lines
    assert ('target_price', 0) in lines
    assert ('stop_price', 1) not in lines
    assert ('target_price', 1) not in lines
    # 回测结果页不要其它指标
    assert all(name not in ('cci', 'cci1') for name, _ in lines)
    assert len(rc._info_overlays) == 4


# --------------------------------------------------------------------------
# 入场/离场连线（复刻 bokeh 的交易信号；与指标信号区分）
# --------------------------------------------------------------------------

class FakeTradeResult:
    """`strategy._results[plot_id]` 的替身：只要 positions / cum_profits。"""

    columns = ['positions', 'cum_profits']

    def __init__(self, positions, cum):
        self._data = {'positions': np.asarray(positions, dtype=float),
                      'cum_profits': np.asarray(cum, dtype=float)}

    def __getitem__(self, key):
        return self._data[key]


def _trade_strategy(n=12):
    positions = np.zeros(n)
    positions[2:5] = 1          # 多头 2 -> 5
    positions[6:9] = -1         # 空头 6 -> 9
    cum = np.arange(n, dtype=float)
    strategy = FakeStrategy({}, {'k': FakeStopKline('X', '60', None)})
    strategy._results = [FakeTradeResult(positions, cum)]
    return strategy


def test_extract_trade_lines_follows_positions():
    frame = make_frame(12)
    strategy = _trade_strategy()
    cum = np.arange(12, dtype=float)
    trades = rt.extract_trade_lines(strategy, 0, frame)
    assert [(t['side'], t['entry_index'], t['exit_index'])
            for t in trades] == [('long', 2, 5), ('short', 6, 9)]
    assert trades[0]['entry_price'] == float(frame['close'].iloc[2])
    assert trades[0]['exit_price'] == float(frame['close'].iloc[5])
    # ★ 本笔盈亏 = cum[exit] - cum[**开仓前一根**] —— cum_profits 在开仓那根
    #   已经扣了开仓手续费，用 cum[entry] 会把这笔手续费抵消掉 ✗
    assert trades[0]['profit'] == float(cum[5] - cum[2 - 1])
    assert trades[1]['profit'] == float(cum[9] - cum[6 - 1])


def test_draw_trade_lines_makes_segment_and_four_markers():
    frame = make_frame(12)
    strategy = _trade_strategy()
    chart = make_chart(frame)
    made = rt.draw_trade_lines(chart, strategy, 'X_60', frame, 0,
                               theme_dark=True)
    names = [getattr(series, 'name', '') for series in made]
    assert names == ['交易连线', '交易-long_entry', '交易-short_entry',
                     '交易-long_exit', '交易-short_exit']
    # 连线：一笔一条，挂在入场那根，水平偏移 = 持仓根数
    line = made[0]
    assert list(line.data['_offset']) == [3, 3]
    assert float(line.data['low'].iloc[0]) == min(
        float(frame['close'].iloc[2]), float(frame['close'].iloc[5]))
    assert float(line.data['high'].iloc[0]) == max(
        float(frame['close'].iloc[2]), float(frame['close'].iloc[5]))
    # 四类标记各一条，款式与指标信号不同（自定义 series，不进图例 ✓）
    assert len(made[1].data) == 1 and len(made[2].data) == 1
    assert len(made[3].data) == 1 and len(made[4].data) == 1
    assert not made[0].data.empty


def test_trade_style_from_config_controls_markers_and_line():
    """`config.tradestyle` 控制四点标记的颜色/形状/大小 + 连线的色/宽/型 ✓。"""
    import types as _types
    from minibt.utils import (TradeStyle, TradeMarkerStyle,
                              resolve_tradestyle, normalise_tradestyle)
    from minibt.constant import Colors, Markers, LineDash

    style = TradeStyle(
        long_entry=TradeMarkerStyle(Colors.orange, Markers.square, 20),
        short_entry=TradeMarkerStyle(Colors.purple, Markers.circle, 18),
        long_exit=TradeMarkerStyle(Colors.cyan, Markers.cross, 8),
        short_exit=TradeMarkerStyle(Colors.brown, Markers.dot, 6),
        line_color=Colors.magenta, line_width=5,
        line_dash=LineDash.dotted)

    frame = make_frame(12)
    strategy = _trade_strategy()
    strategy.config = _types.SimpleNamespace(tradestyle=style)
    # 解析出来就是用户设的那份（缺省字段已补全）
    assert resolve_tradestyle(strategy).line_color == Colors.magenta

    chart = make_chart(frame)
    made = rt.draw_trade_lines(chart, strategy, 'X_60', frame, 0,
                               theme_dark=True)
    line_head = list(made[0].data['shapes'])[0][0]
    assert line_head['color'] == 'magenta'
    assert line_head['width'] == 5
    assert line_head['style'] == 1                  # dotted -> 1 ✓
    # 多头入场：orange 方块、半径 round(20*0.8)=16
    entry_head = list(made[1].data['shapes'])[0][0]
    assert entry_head['marker'] == 'square'
    assert entry_head['color'] == 'orange'
    assert entry_head['size'] == 16.0
    # 空头入场：purple 圆、半径 round(18*0.8)=14
    short_head = list(made[2].data['shapes'])[0][0]
    assert short_head['marker'] == 'circle'
    assert short_head['color'] == 'purple'
    assert short_head['size'] == 14.0
    # 离场：cross / dot
    assert list(made[3].data['shapes'])[0][0]['marker'] == 'cross'
    assert list(made[4].data['shapes'])[0][0]['marker'] == 'dot'
    # `show=False` -> 一条都不画
    hidden = normalise_tradestyle(TradeStyle(show=False))
    assert hidden.show is False


class FakeContractResult:
    """`strategy._results[plot_id]` 的替身（positions / cum_profits / total_fee）。"""

    columns = ['positions', 'cum_profits', 'total_fee']

    def __init__(self, positions, cum):
        self._data = {'positions': np.asarray(positions, dtype=float),
                      'cum_profits': np.asarray(cum, dtype=float),
                      'total_fee': pd.Series([0.0])}

    def __getitem__(self, key):
        return self._data[key]


def test_extract_all_contract_trades_merges_and_sorts(monkeypatch):
    """多合约交易记录：两个合约都保留、按时间重排、盈亏用各自 cum_profits ✓。"""
    n = 8
    frame0 = make_frame(n)
    frame1 = make_frame(n)
    pos0 = np.zeros(n)
    pos0[1:3] = 1                       # A：多头 1 -> 3
    pos1 = np.zeros(n)
    pos1[2:5] = -1                      # B：空头 2 -> 5
    cum0 = np.array([0, 0, 0, 10, 10, 10, 10, 10], dtype=float)
    cum1 = np.array([0, 0, 0, 0, -5, -5, -5, -5], dtype=float)

    strategy = FakeStrategy({}, {})
    strategy._results = [FakeContractResult(pos0, cum0),
                         FakeContractResult(pos1, cum1)]
    monkeypatch.setattr(rt, 'strategy_contracts',
                        lambda s: ['A_60', 'B_60'])
    frames = {'A_60': frame0, 'B_60': frame1}
    monkeypatch.setattr(rt, 'strategy_kline_frame',
                        lambda s, c: frames[c])
    # 别去读真实 logger（可能残留别的测试的数据）
    monkeypatch.setattr(rt.RealtimeChart, '_trades_from_log',
                        staticmethod(lambda strategy, limit_time=None:
                                     ([], [])))

    times = list(frame0['time'])
    values = np.zeros(n)
    records, pnl = rt.RealtimeChart._extract_all_contract_trades(
        strategy, strategy._results, values, times)

    assert {r['symbol'] for r in records} == {'A_60', 'B_60'}
    stamps = [pd.Timestamp(r['time']) for r in records]
    assert stamps == sorted(stamps)                 # 按时间重排 ✓
    # A 开多(1) / B 开空(2) / A 平多(3) / B 平空(5) —— 按时间排出来 ✓
    assert [r['direction'] for r in records] == \
        ['开多', '开空', '平多', '平空']
    assert pnl['value'].tolist() == pytest.approx([10.0, -5.0])
    assert pnl['time'].is_monotonic_increasing


def test_backtest_dict_falls_back_to_the_strategys_own_contract(monkeypatch):
    """多策略登记：传进来的合约不在本策略数据集里时，用**本策略自己的**合约。

    以前 `set_backtest_from_strategy` 用 `self.window.contract`（当前显示策略的
    合约）去另一个策略里找 K 线 → 找不到 → 权益/回撤退回
    `pd.date_range('2020-01-01')` 的假时间 → 整页与 K 线错位 ✗（用户反馈：
    单策略正常、多策略时权益和回撤没跟 K 线对齐）。
    """
    seen = {}
    monkeypatch.setattr(rt, 'strategy_contracts', lambda s: ['DCE.A_60'])

    def fake_frame(strategy, contract, tail=None):
        seen['contract'] = contract
        return pd.DataFrame({'time': pd.date_range('2026-01-01', periods=3,
                                                   freq='min')})

    monkeypatch.setattr(rt, 'strategy_kline_frame', fake_frame)
    monkeypatch.setattr(rt.RealtimeChart, '_trades_from_log',
                        staticmethod(lambda strategy, limit_time=None:
                                     ([], [])))
    monkeypatch.setattr(rt.RealtimeChart, '_extract_all_contract_trades',
                        staticmethod(lambda *a, **k: ([], None)))

    class FakeProfitStrategy:
        _results = [{'total_profit': 3.0, 'total_fee': 0.0}]
        profits = pd.Series([1.0, 2.0, 3.0])

    data = rt.strategy_backtest_dict(FakeProfitStrategy(),
                                     contract='DCE.OTHER_60')
    assert seen['contract'] == 'DCE.A_60', seen
    times = list(data['equity']['time'])
    assert times[0].year == 2026, times      # 不是 2020 的假时间


def test_indicator_spec_and_options_default_price_visible():
    """所有指标默认显示价格线 / 价格标签（用户要求 ✓）。"""
    spec = rt.IndicatorSpec(name='ma', overlap=True)
    assert spec.price_line is True
    assert spec.price_label is True
    opts = rt._color_options('Line', '#ffffff', 2, 'solid')
    assert opts['price_line_visible'] is True
    assert opts['last_value_visible'] is True
