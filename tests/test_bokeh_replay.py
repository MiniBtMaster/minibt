"""bokeh 回放（``minibt/strategy/bokeh_replay.py``）的回归测试。

覆盖：

* 复用 ``bokeh_plot.plot`` 构建的图与数据源（``live_sources`` 登记）；
* 按各数据源的 ``index`` 列逐 bar「揭开」（``reveal_sources`` / ``reveal``），
  这是修复「更新数据错位 / 两个合约图一样 / 一根不动」的核心；
* bokeh server app 能构建 ``make_document``（不真起服务）。

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
    reason='缺少本地测试数据 minibt/data/test/pp2609_60.csv（跳过 bokeh 回放回归）',
)

CODE = r'''
import pathlib, sys
sys.path.insert(0, {root!r})
import minibt.strategy.bokeh_plot as bp
bp.show = lambda *a, **k: None
from minibt import Bt, Config, LocalDatas, Strategy
import minibt.strategy.bokeh_replay as br


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

reg = {{}}
tabs = bp.plot(bt.strategies, live_sources=reg, build_only=True,
               volume_mode='overlay')
assert reg.get('cds'), '未登记任何可更新数据源'
kline_lens = [len(reg['full'][c.id]['index']) for c in reg['cds']]
assert max(kline_lens) >= 300, ('K 线数据源长度异常', kline_lens)

total = br.collect_total(reg)
assert total == max(kline_lens) - 1, ('collect_total 异常', total, max(kline_lens))

# 揭开到 300：所有登记的源不应超过 index 300
br.reveal(reg, 300, window=300)
mx = max(int(c.data['index'][-1]) if len(c.data['index']) else -1
         for c in reg['cds'])
assert mx <= 300, ('reveal 未截断', mx)

# 之后只"平移"：跨度保留（用户缩放/拖动不被打乱），整体移 10 步
xr = reg['x_ranges'][0]
span0, start0 = xr.end - xr.start, xr.start
br.reveal(reg, 310, window=300, prev=300)
assert abs((xr.end - xr.start) - span0) < 1e-6, ('span 被重置', span0, xr.end - xr.start)
assert round(xr.start - start0) == 10, ('未整体平移 10 步', xr.start)
mx2 = max(int(c.data['index'][-1]) if len(c.data['index']) else -1
          for c in reg['cds'])
assert 300 < mx2 <= 310, ('reveal 未推进', mx2)

# 主图成交量叠加源**不参与**揭开（不重写 vol_ov_bottom/top -> 不闪；
# 视觉上由 X 轴窗口推进 + 它自己的 CustomJS 控制）
assert not any('vol_ov_ratio' in reg['full'][c.id] for c in reg['cds']), \
    '成交量叠加源不应参与揭开'

# server app：make_document 能构建（不真起服务）
app = br.build_replay_app(bt.strategies, start_bars=300, period_ms=1000,
                          speed=5, plot_kwargs=dict(volume_mode='overlay'))
fn = app.handlers[0]._func
from bokeh.document import Document
from bokeh.models import Tabs
doc = Document()
fn(doc)
assert doc.roots, 'make_document 未添加 root'
has_tabs = any(isinstance(r, Tabs) or any(isinstance(c, Tabs)
               for c in getattr(r, 'children', [])) for r in doc.roots)
assert has_tabs, '未找到 Tabs'
print('BOKEH_REPLAY_OK')
'''


def _run(code: str):
    env = dict(os.environ,
               PYTHONPATH=os.pathsep.join([str(ROOT),
                                           os.environ.get('PYTHONPATH', '')]))
    return subprocess.run([sys.executable, '-c', code], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)


def test_bokeh_replay_reveal_registry_and_app():
    result = _run(CODE.format(root=str(ROOT)))
    assert result.returncode == 0, result.stderr
    assert 'BOKEH_REPLAY_OK' in result.stdout
