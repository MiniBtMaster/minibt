"""bokeh 实时图表（``minibt/strategy/bokeh_realtime.py``）的回归测试。

覆盖：

* ``with_equity=False`` 时不建权益曲线（实时图表只要策略/合约页）；
* ``bokeh_plot.sync_sources`` 能把「同一套构建器重算的数据」同步到已挂载的 CDS；
* ``build_live_app`` 能构建 server app（不真连天勤，用假 ``feed_factory``）。

用子进程跑，避免 bokeh 全局状态污染本进程。
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
    reason='缺少本地测试数据 minibt/data/test/pp2609_60.csv（跳过 bokeh 实时回归）',
)

CODE = r'''
import pathlib, sys
sys.path.insert(0, {root!r})
import minibt.strategy.bokeh_plot as bp
bp.show = lambda *a, **k: None
from minibt import Bt, Config, LocalDatas, Strategy
import minibt.strategy.bokeh_realtime as rt


class Mini(Strategy):
    config = Config(islog=False, theme='dark', bokeh_fullscreen=True,
                    toolbox=False)

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

# 1) 不建权益曲线
reg = {{}}
bp.plot(bt.strategies, live_sources=reg, build_only=True,
        with_equity=False, volume_mode='overlay')
assert reg.get('cds'), '未登记数据源'
assert not any('value' in reg['full'][c.id] for c in reg['cds']), \
    'with_equity=False 仍建了权益曲线'

# 1b) 实时模式没有回测结果（_results 为空）也要能建图（回归 IndexError:
#     long_segment_source[ik][id] out of range）
for _s in bt.strategies:
    _s._results = []
reg_nr = {{}}
bp.plot(bt.strategies, live_sources=reg_nr, build_only=True,
        with_equity=False, volume_mode='overlay')
assert reg_nr.get('cds'), '无回测结果时未登记数据源'
assert not any('value' in reg_nr['full'][c.id] for c in reg_nr['cds'])

# 2) sync_sources：同一套管线重算 -> 同步
reg2 = {{}}
bp.plot(bt.strategies, live_sources=reg2, build_only=True,
        with_equity=False, volume_mode='overlay')
n = bp.sync_sources(reg, reg2)
assert n == len(reg['cds']), ('sync_sources 数量不符', n, len(reg['cds']))
for c in reg['cds']:
    assert reg['full'].get(c.id), 'sync 后 full 缺失'


# 3) build_live_app（假 feed，不连天勤）
class DummyFeed:
    def __init__(self, strategys, reg):
        self.strategys = strategys
        self.reg = reg
        self.ticks = 0

    def bind(self, reg):
        self.reg = reg

    def tick(self):
        src = {{}}
        bp.plot(self.strategys, live_sources=src, build_only=True,
                with_equity=False, volume_mode='overlay')
        bp.sync_sources(self.reg, src)
        self.ticks += 1
        return self.ticks < 3


app = rt.build_live_app(bt.strategies, period_ms=1000,
                        plot_kwargs=dict(volume_mode='overlay'),
                        feed_factory=DummyFeed)
fn = app.handlers[0]._func
from bokeh.document import Document
from bokeh.models import Tabs
doc = Document()
fn(doc)
assert doc.roots, 'make_document 未添加 root'
has_tabs = any(isinstance(r, Tabs) or any(isinstance(c, Tabs)
               for c in getattr(r, 'children', [])) for r in doc.roots)
assert has_tabs, '未找到 Tabs'
print('BOKEH_REALTIME_OK')
'''


def _run(code: str):
    env = dict(os.environ,
               PYTHONPATH=os.pathsep.join([str(ROOT),
                                           os.environ.get('PYTHONPATH', '')]))
    return subprocess.run([sys.executable, '-c', code], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)


def test_bokeh_realtime_app_and_sync():
    result = _run(CODE.format(root=str(ROOT)))
    assert result.returncode == 0, result.stderr
    assert 'BOKEH_REALTIME_OK' in result.stdout


# `Model.references()` / `select()` 基于 set，迭代顺序不稳定 —— 两次完全相同的
# 构建，CDS 顺序都可能不同；而 `sync_sources` 是按位置配对的，配错就会把数据
# 写进错的源（K 线/指标/信号全部消失，只有不参与同步的成交量留在图上）。
CODE_SYNC = r'''
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
        self.cci.signal_style = dict(
            long_signal=SignalStyle(
                'low', Colors.red, Markers.triangle).set_label('B'),
            short_signal=SignalStyle(
                'high', Colors.green, Markers.inverted_triangle).set_label('S'))

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
KW = dict(build_only=True, with_equity=False, volume_mode='overlay')

r1 = {{}}
bp.plot(bt.strategies, live_sources=r1, **KW)
r2 = {{}}
bp.plot(bt.strategies, live_sources=r2, **KW)
k1 = [tuple(sorted(c.data)) for c in r1['cds']]
k2 = [tuple(sorted(c.data)) for c in r2['cds']]
assert k1 == k2, 'CDS 顺序不稳定，sync_sources 会写错源'
print('ORDER_STABLE OK')

# 更新：模拟实盘 preload（K 线只剩最后 PRELOAD 根）
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
st.get_results = lambda: []

src = {{}}
bp.plot(bt.strategies, live_sources=src, **KW)
n = bp.sync_sources(r1, src)
assert n == len(r1['cds']), ('sync 返回异常', n)
bad = 0
kline_rows = []
for d, s in zip(r1['cds'], src['cds']):
    full = (src['full'] or {{}}).get(s.id) or {{}}
    if set(d.data) != set(full):
        bad += 1
    if 'close' in d.data and 'high' in d.data:
        kline_rows.append(len(d.data['close']))
assert bad == 0, f'{{bad}} 个 CDS 配对错位'
assert kline_rows and all(r == PRELOAD for r in kline_rows), kline_rows
print('SYNC_PAIRED_OK', kline_rows)
'''


def test_bokeh_realtime_sync_pairs_the_same_cds_in_the_same_order():
    """同步必须按确定顺序配对，否则会把数据写进错的 CDS。"""
    result = _run(CODE_SYNC.format(root=str(ROOT)))
    assert result.returncode == 0, result.stderr
    assert 'ORDER_STABLE OK' in result.stdout, result.stdout
    assert 'SYNC_PAIRED_OK' in result.stdout, result.stdout


# 实盘首帧如果按全量（history_length）建图，第一次行情变化后 K 线被 `_preload`
# 截短（index 空间 0..999 -> 0..199），x 窗口却还停在尾部 -> 主图空白、只剩不
# 参与同步的成交量。两处修正：首帧就按 preload 建图；窗口完全落到数据右边时跟回。
CODE_PRELOAD_X = r'''
import pathlib, sys
sys.path.insert(0, {root!r})
import cci
from minibt import Bt
import minibt.strategy.bokeh_realtime as rt

bt = Bt()
bt.addstrategy(cci.CCIStrategy)
bt.run(isplot=False)
st = bt.strategies[0]
kl = st.kline if hasattr(st, 'kline') else st.data
kl._preload = 200
kl._dataset.tq_object = kl.pandas_object      # 模拟天勤底层对象
before = len(kl.pandas_object)
rt._apply_preload([st])
after = len(kl.pandas_object)
assert before > 200 and after == 200, (before, after)
print('PRELOAD_OK', before, after)


class _XR:
    def __init__(self, start, end):
        self.start = start
        self.end = end


class _CDS:
    id = 'x'


reg = {{'x_ranges': [_XR(700.0, 1002.0), _XR(0.0, 1500.0)],
       'cds': [_CDS()],
       'full': {{'x': {{'index': list(range(200))}}}}}}
feed = rt.StrategyLiveFeed.__new__(rt.StrategyLiveFeed)
feed.reg = reg
feed.window = 300
feed._follow_x()
assert reg['x_ranges'][0].start == 0, reg['x_ranges'][0].start
assert reg['x_ranges'][0].end > 200, reg['x_ranges'][0].end
assert reg['x_ranges'][1].start == 0.0 and reg['x_ranges'][1].end == 1500.0, \
    '用户拖动/缩放的窗口不应被移动'
print('FOLLOW_X_OK')
'''


def test_bokeh_realtime_preload_and_stale_x_window():
    """首帧按 preload 建图；x 窗口落到数据右边时要跟回（用户缩放不动）。"""
    result = _run(CODE_PRELOAD_X.format(root=str(ROOT)))
    assert result.returncode == 0, result.stderr
    assert 'PRELOAD_OK' in result.stdout, result.stdout
    assert 'FOLLOW_X_OK' in result.stdout, result.stdout


CODE_PUSH = r'''
import pathlib, sys
sys.path.insert(0, {root!r})
import minibt.strategy.bokeh_plot as bp
bp.show = lambda *a, **k: None
from minibt import Bt, Config, LocalDatas, Strategy
import minibt.strategy.bokeh_realtime as rt


class Mini(Strategy):
    config = Config(islog=False)

    def __init__(self):
        self.data = self.get_kline(LocalDatas.pp2609_60)
        self.cci = self.data.close.cci(14)

    def next(self):
        pass


bt = Bt(auto=False)
bt.addstrategy(Mini)
bt.run(isplot=False)

reg = {{}}
bp.plot(bt.strategies, live_sources=reg, build_only=True, with_equity=False,
        volume_mode='overlay')
# ``build_live_app`` 会把 ``with_equity`` 写进 ``plot_kwargs`` 再交给
# ``StrategyLiveFeed``，所以 ``_push()`` 里不能再显式传一次同名关键字
# （旧版报 "got multiple values for keyword argument 'with_equity'"）。
feed = rt.StrategyLiveFeed(bt.strategies,
                           plot_kwargs=dict(volume_mode='overlay',
                                            with_equity=False))
feed.bind(reg)
feed._push()
print('BOKEH_REALTIME_PUSH_OK')
'''


def test_bokeh_realtime_push_allows_with_equity_in_plot_kwargs():
    """`_push()` 不能与 `plot_kwargs` 里的 `with_equity` 冲突。"""
    result = _run(CODE_PUSH.format(root=str(ROOT)))
    assert result.returncode == 0, result.stderr
    assert 'BOKEH_REALTIME_PUSH_OK' in result.stdout
