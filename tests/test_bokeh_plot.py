"""bokeh 回测绘图（`minibt/strategy/bokeh_plot.py::plot`）的回归测试。

覆盖：

* 双合约解包（历史 bug：``ValueError: too many values to unpack (expected 12)``）；
* 主题（``theme`` / ``bokeh_fullscreen``）与 tooltip 深/浅色 CSS 注入。

用子进程跑：bokeh 的全局 output/state 不会污染本进程，失败时也更好定位。
"""
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'minibt' / 'data' / 'test' / 'pp2609_60.csv'

pytestmark = pytest.mark.skipif(
    not DATA.exists(),
    reason='缺少本地测试数据 minibt/data/test/pp2609_60.csv（跳过 bokeh 回归）',
)

# 双合约：合约 0 有信号、合约 1 没有 —— 正好触发“从合约 0 复制信号标记”
# 那个解包循环（历史 bug 所在）。
CODE = r'''
import pathlib, sys, tempfile, webbrowser
sys.path.insert(0, {root!r})
webbrowser.open = lambda *a, **k: None   # 不弹浏览器
import minibt.strategy.bokeh_plot as bp
bp.show = lambda *a, **k: None
from minibt import Bt, Config, LocalDatas, Strategy


class Mini(Strategy):
    config = Config(islog=False, profit_plot=False, theme={theme!r},
                    bokeh_fullscreen={fullscreen!r}, toolbox={toolbar!r})

    def __init__(self):
        self.data = self.get_kline(LocalDatas.pp2609_60)
        self.data1 = self.get_kline(LocalDatas.l2609_60)
        self.cci = self.data.close.cci(14)

    def next(self):
        if not self.data.position:
            if self.cci.cross_up(-100).new:
                self.data.buy()
            elif self.cci.cross_down(100).new:
                self.data.sell()


bt = Bt(auto=False)
bt.addstrategy(Mini)
bt.run(isplot=False)
out = pathlib.Path(tempfile.mkdtemp())
tabs = bt.bokeh_plot(save_plot=True, plot_cwd=str(out))
assert tabs is not None, 'bokeh_plot 返回了 None'
html = next(out.glob('*bokeh_plot.html')).read_text(encoding='utf-8')
assert '--tooltip-color' in html, 'tooltip 主题色 CSS 未注入'
import re
if {toolbar!r}:
    assert re.search(r'"toolbar_location":\s*"right"', html), '开启 toolbox 应出现右侧工具栏'
else:
    assert re.search(r'"toolbar_location":\s*null', html), '默认不应出现工具栏'
{check}
print('BOKEH_PLOT_OK')
'''


def _run(code: str):
    env = dict(os.environ,
               PYTHONPATH=os.pathsep.join([str(ROOT),
                                           os.environ.get('PYTHONPATH', '')]))
    return subprocess.run([sys.executable, '-c', code], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)


@pytest.mark.parametrize('theme, fullscreen, toolbar, check', [
    ('dark', False, False,
     "assert '#454545' in html, '未套用深色主题（DARK_TABS_CSS 未注入）'\n"
     "assert '100vh' not in html, '未开启全屏不应注入 100vh 布局'"),
    ('light', False, False,
     "assert '#454545' not in html, 'light 主题不应注入 DARK_TABS_CSS'"),
    ('dark', True, False,
     "assert '#454545' in html\n"
     "assert '100vh' in html, '开启全屏应注入 100vh 布局'"),
    ('dark', False, True, "assert True"),
])
def test_bokeh_backtest_plot_renders_with_theme(theme, fullscreen, toolbar, check):
    result = _run(CODE.format(root=str(ROOT), theme=theme,
                              fullscreen=fullscreen, toolbar=toolbar,
                              check=check))
    assert result.returncode == 0, result.stderr
    assert 'BOKEH_PLOT_OK' in result.stdout


# 实盘「无限历史」：KLine 只保留最后 `_preload` 根（图表开局先放出的量），
# 而 `get_plot_datas()` 里的指标数组仍是全量 —— 历史 bug：
# `signal_price = price_data[signaldata > 0]` 报
# "boolean index did not match indexed array ... 200 ... 10000"。
CODE_PRELOAD = r'''
import pathlib, sys
sys.path.insert(0, {root!r})
import minibt.strategy.bokeh_plot as bp
bp.show = lambda *a, **k: None
from minibt import Bt, Colors, Config, LocalDatas, Markers, SignalStyle, Strategy
from minibt.indicators.base import IndicatorsBase


class Mini(Strategy):
    config = Config(islog=False)

    def __init__(self):
        self.data = self.get_kline(LocalDatas.pp2609_60)
        self.data1 = self.get_kline(LocalDatas.l2609_60)
        self.cci = self.data.close.cci(14)
        # SignalStyle('low', ...) 默认 overlap=True -> 取价用 K 线的 low 列
        self.cci.signal_style = dict(
            long_signal=SignalStyle(
                'low', Colors.red, Markers.triangle).set_label('B'),
            short_signal=SignalStyle(
                'high', Colors.green, Markers.inverted_triangle).set_label('S'),
        )

    def next(self):
        if not self.data.position:
            if self.cci.cross_up(-100).new:
                self.data.buy()
            elif self.cci.cross_down(100).new:
                self.data.sell()


bt = Bt(auto=False)
bt.addstrategy(Mini)
bt.run(isplot=False)
st = bt.strategies[0]

# 模拟实盘 preload：K 线只剩最后 PRELOAD 根，指标仍是全量
PRELOAD = 200
_orig_get = IndicatorsBase.__dict__['pandas_object'].fget


def _truncated(self):
    obj = _orig_get(self)
    try:
        if len(obj) > PRELOAD:
            return obj.iloc[-PRELOAD:]
    except Exception:
        pass
    return obj


IndicatorsBase.pandas_object = property(_truncated)
st.get_results = lambda: []          # 实盘没有回测结果

assert len(st.data.pandas_object) == PRELOAD
reg = {{}}
bp.plot(bt.strategies, live_sources=reg, build_only=True, with_equity=False,
        volume_mode='overlay')
print('BOKEH_PLOT_PRELOAD_OK')
'''


def test_bokeh_plot_tail_aligns_indicators_to_preload_kline():
    """K 线只给 preload 根时，指标数组要截尾对齐后再画（否则 IndexError）。"""
    result = _run(CODE_PRELOAD.format(root=str(ROOT)))
    assert result.returncode == 0, result.stderr
    assert 'BOKEH_PLOT_PRELOAD_OK' in result.stdout


def test_add_band_breaks_splits_at_nan():
    """bokeh 的 `Band` 会把 NaN 两侧连起来 → 按连续有效段拆成多条。

    指标列常是分段有效的（VIDYA 的 `vidya_up` 在空头段为 NaN），不拆的话
    "两段色带中间会被补上"。
    """
    bokeh_models = pytest.importorskip('bokeh.models')
    numpy = pytest.importorskip('numpy')
    pytest.importorskip('bokeh.plotting')

    import sys

    sys.path.insert(0, str(ROOT))
    from minibt.strategy.bokeh_plot import add_band_breaks
    from bokeh.plotting import figure

    fig = figure()
    lower = numpy.array([1.0, 2.0, 3.0, numpy.nan, numpy.nan, 6.0, 7.0, 8.0])
    upper = numpy.array([1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5])
    source = bokeh_models.ColumnDataSource({
        'index': numpy.arange(8), 'up': lower, 'hl2': upper})
    options = {'lower': 'up', 'upper': 'hl2', 'fill_color': '#17dfad',
               'fill_alpha': 0.08}

    made = add_band_breaks(fig, source, 'index', options)
    assert len(made) == 2, 'NaN 处必须断开成两段'
    for band in made:
        values = numpy.asarray(band.source.data['up'], dtype=float)
        assert not numpy.isnan(values).any(), '拆出来的段不能再含 NaN'
    assert [len(b.source.data['index']) for b in made] == [3, 3]

    # 没有 NaN 时行为不变：仍然只画一条
    flat = bokeh_models.ColumnDataSource({
        'index': numpy.arange(4), 'a': [1.0, 2.0, 3.0, 4.0],
        'b': [2.0, 3.0, 4.0, 5.0]})
    assert len(add_band_breaks(fig, flat, 'index',
                               {'lower': 'a', 'upper': 'b'})) == 1


# ----------------------------------------------------------------------
# Volume Profile 的 `VPStyle`（`category='vp'` 专用）要一路传到渲染层
# ----------------------------------------------------------------------
CODE_VP = r'''
import pathlib, sys, json
sys.path.insert(0, {root!r})
import minibt.strategy.bokeh_plot as bp
bp.show = lambda *a, **k: None
from minibt import Bt, Config, LocalDatas, Strategy
from minibt.utils import VPStyle

seen = {{}}
_real = bp._add_volume_profile
def spy(*a, **kw):
    seen.update(kw)
    return _real(*a, **kw)
bp._add_volume_profile = spy


class Mini(Strategy):
    config = Config(islog=False)

    def __init__(self):
        self.data = self.get_kline(LocalDatas.test)
        self.vp = self.data.tradingview.RollingVolumeProfile(vpstyle=VPStyle(
            bar_color='#ff5722', poc_color='#9c27b0', fill_alpha=0.35,
            profile_frac=0.20, bin_ratio=0.55, line_color='#222222',
            line_width=1.0, highlight_poc=False, price_bars=120,
            show_axis=False))

    def next(self):
        pass


bt = Bt(auto=False)
bt.addstrategy(Mini)
bt.run(isplot=False)
bt.bokeh_plot(save_plot=True, plot_cwd={out!r})
assert seen, 'VP 分支没有调用 _add_volume_profile'
keys = ['bar_color', 'poc_color', 'profile_frac', 'fill_alpha', 'bin_ratio',
        'line_color', 'line_width', 'highlight_poc', 'price_bars']
print('VPWIRE ' + json.dumps({{k: str(seen.get(k)) for k in keys}}))
print('BOKEH_VP_OK')
'''


CODE_WICK = r'''
import minibt.strategy.bokeh_plot as bp
import minibt.btplot as btp
from minibt import LocalDatas
from minibt.utils import Config
from bokeh.models import Segment


def _wick_segments(fig):
    return [r.glyph for r in fig.renderers if isinstance(r.glyph, Segment)]


def _assert_two_wicks(fig, src):
    y = [(g.y0, g.y1) for g in _wick_segments(fig)]
    assert ('wick_top', 'high') in y, y       # 实体顶 -> 最高点
    assert ('wick_bottom', 'low') in y, y     # 最低点 -> 实体底
    assert ('high', 'low') not in y, ('单条影线会穿过实体', y)
    assert 'wick_top' in src.data and 'wick_bottom' in src.data


k = LocalDatas.test.kline
ind = k.tradingview.ScalpPro()
strat = btp._make_step_strategy(k, [ind], Config(theme='dark'), 'ScalpPro')
strat._start_strategy_run()
reg = {}
bp.plot([strat], live_sources=reg, build_only=True, with_equity=False,
        volume_mode='overlay')
assert reg['ohlc_figs'], '没有找到主 K 线图'
for src, fig in reg['ohlc_figs']:
    _assert_two_wicks(fig, src)
print('WICK_OK')
'''


def test_bokeh_candle_wicks_are_two_segments():
    """K 线上/下影线必须是两条（实体顶->high、low->实体底）。

    历史 bug：只画了一条 ``segment(high -> low)``，它会横穿实体，
    看起来像“实体中间多了一条线段”。
    """
    result = _run(CODE_WICK)
    assert result.returncode == 0, result.stderr
    assert 'WICK_OK' in result.stdout, result.stdout + result.stderr


def test_bokeh_volume_profile_style_is_wired():
    """`vpstyle` 必须一路传到 `_add_volume_profile`（否则 bokeh 侧样式改不动）。"""
    import json
    import tempfile

    out = pathlib.Path(tempfile.mkdtemp())
    result = _run(CODE_VP.format(root=str(ROOT), out=str(out)))
    assert result.returncode == 0, result.stderr
    assert 'BOKEH_VP_OK' in result.stdout, result.stdout + result.stderr
    line = [l for l in result.stdout.splitlines() if l.startswith('VPWIRE ')][0]
    got = json.loads(line[len('VPWIRE '):])
    assert got['bar_color'] == '#ff5722', got
    assert got['poc_color'] == '#9c27b0', got
    assert got['fill_alpha'] == '0.35', got
    assert got['bin_ratio'] == '0.55', got
    assert got['highlight_poc'] == 'False', got
    assert got['line_width'] == '1.0', got
    assert got['line_color'] == '#222222', got
    assert got['price_bars'] == '120', got
    assert got['profile_frac'] == '0.2', got


# 交易连线样式：`config.tradestyle` 必须作用到 bokeh 的连线与四类标记 ✓
CODE_TRADE_STYLE = r'''
import pathlib, sys, tempfile, webbrowser
sys.path.insert(0, {root!r})
webbrowser.open = lambda *a, **k: None
import minibt.strategy.bokeh_plot as bp
bp.show = lambda *a, **k: None
from minibt import (Bt, Config, LineDash, LocalDatas, Markers, Strategy,
                    TradeStyle, TradeMarkerStyle)


class Mini(Strategy):
    config = Config(
        islog=False, profit_plot=False,
        tradestyle=TradeStyle(
            long_entry=TradeMarkerStyle('#123456', Markers.square, 20),
            short_entry=TradeMarkerStyle('#654321', Markers.circle, 18),
            long_exit=TradeMarkerStyle('#abcdef', Markers.cross, 8),
            short_exit=TradeMarkerStyle('#fedcba', Markers.dot, 6),
            line_color='#ff00ff', line_width=5,
            line_dash=LineDash.dotted))

    def __init__(self):
        self.data = self.get_kline(LocalDatas.pp2609_60)
        self.data1 = self.get_kline(LocalDatas.l2609_60)
        self.cci = self.data.close.cci(14)

    def next(self):
        if not self.data.position:
            if self.cci.cross_up(-100).new:
                self.data.buy()
            elif self.cci.cross_down(100).new:
                self.data.sell()


bt = Bt(auto=False)
bt.addstrategy(Mini)
bt.run(isplot=False)
out = pathlib.Path(tempfile.mkdtemp())
assert bt.bokeh_plot(save_plot=True, plot_cwd=str(out)) is not None
html = next(out.glob('*bokeh_plot.html')).read_text(encoding='utf-8')
for want in ('#ff00ff', '#123456', '#654321', '#abcdef', '#fedcba'):
    assert want in html, want
print('BOKEH_TRADE_STYLE_OK')
'''


def test_bokeh_trade_style_from_config():
    """bokeh 交易连线/标记读 `config.tradestyle`（颜色全部落到 HTML ✓）。"""
    result = _run(CODE_TRADE_STYLE.format(root=str(ROOT)))
    assert result.returncode == 0, result.stderr
    assert 'BOKEH_TRADE_STYLE_OK' in result.stdout
