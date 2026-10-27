"""pylightcharts 的**滚动成交量分布图**（``category='vp'``）。

历史状态：bokeh 侧早就用 ``hbar`` 画出了 VP（``_add_volume_profile``），
但 pylightcharts 侧完全没有 —— ``vp0..vpN`` 是**等宽价格档**的分布矩阵
（不是普通指标线），逐线建 ``Line`` 只会得到 40 条乱线。

现在 ``extract_minibt_indicators`` 命中 ``category == 'vp'`` 时出一条
``kind='VolumeProfile'`` 的 spec，``IndicatorManager`` 用 ``CustomSeries``
+ ``rendererDraw`` 画横条（几何约定与 bokeh 完全一致：锚在最右可见 K 线、
向左生长、满量程 = 可视跨度 × 0.30）。
"""
import numpy as np
import pandas as pd
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


def _make(indicator, tag='VP'):
    from minibt import LocalDatas
    from minibt.utils import Config
    import minibt.btplot as btp
    k = LocalDatas.test.kline
    strat = btp._make_step_strategy(k, [indicator], Config(theme='dark'), tag)
    strat._start_strategy_run()
    return strat


def test_rolling_volume_profile_spec(headless):
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    strat = _make(k.tradingview.RollingVolumeProfile())
    specs = rt.extract_minibt_indicators(strat, 0)

    vp = [s for s in specs if s.kind == 'VolumeProfile']
    assert len(vp) == 1, [(s.name, s.kind) for s in specs]
    vp = vp[0]
    # 矩阵：(K线根数, 40 档)，且列就是 vp0..vp39
    assert vp.profile is not None and vp.profile.shape[1] == 40
    assert vp.profile.shape[0] == len(k)
    # 档区窗口 / 配色来自 linestyle
    assert vp.vp_price_bars == 500
    assert vp.vp_color == '#3498db' and vp.vp_poc_color == '#f39c12'
    assert vp.overlap is True and vp.vp_y_mode == 'price'
    # 不再逐线建 40 条 Line
    assert not [s for s in specs if str(s.name).startswith('vp')]


def test_volume_profile_keeps_ma_line(headless):
    """VolumeProfileMA 的 ``ma`` 列 ``isplot=True``，仍走普通线。"""
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    strat = _make(k.tradingview.VolumeProfileMA(), 'VPMA')
    specs = rt.extract_minibt_indicators(strat, 0)

    assert len([s for s in specs if s.kind == 'VolumeProfile']) == 1
    ma = [s for s in specs if s.name == 'ma']
    assert len(ma) == 1 and ma[0].kind == 'Line'


def test_vp_draw_js_anchors_right_edge_and_follows_mouse(headless):
    """位置固定在**可视范围最右端**，只有数值跟随鼠标；样式来自 `VPStyle`。"""
    import minibt.strategy.realtime as rt
    from minibt.utils import VPStyle

    js = rt._vp_draw_js(40, VPStyle(), 'row.vmax', False, 'VPX')
    assert 'window.VPX' in js                      # 鼠标 CSS x
    assert 'row.vmax' in js                        # 逐行量程（实时可增长）
    assert 'visibleBars()' in js
    assert 'Math.abs(b.x - hx)' in js              # 挑最近的那根（数值跟随鼠标）
    # ★ 锚点 = 绘图区**最右端**（scope.mediaSize.width），不是鼠标那根、
    #   也不是最后一根 K 线的中心 —— 位置固定在可视 X 轴右端（对齐成交量柱）
    assert 'const anchor = scope.mediaSize.width;' in js
    assert 'const anchor = lastVis.x;' not in js
    assert 'useBitmapCoordinateSpace' in js
    # 默认样式：颜色 / 透明度 / 柱体粗细（档高占比）/ POC
    assert '"#3498db"' in js and '"#f39c12"' in js
    assert 'ctx.globalAlpha = 0.6' in js  # 默认透明度（与 bokeh 旧值一致）
    assert '* 0.88' in js
    assert 'ctx.strokeRect' in js and 'ctx.lineWidth = 0.4' in js  # 默认白色描边
    assert '(q >= mx)' in js

    # 自定义 vpstyle 真的生效
    js2 = rt._vp_draw_js(
        40, VPStyle(bar_color='#ff0000', poc_color='#00ff00',
                    highlight_poc=False, fill_alpha=0.25, bin_ratio=0.5,
                    profile_frac=0.12, line_color='#fff', line_width=1.5),
        'row.vmax', False, 'VPX')
    assert '"#ff0000"' in js2
    assert 'ctx.globalAlpha = 0.25' in js2
    assert '* 0.5' in js2
    assert '"#fff"' in js2 and 'ctx.strokeRect' in js2 and 'ctx.lineWidth = 1.5' in js2
    assert '(q >= mx) ?' not in js2                # highlight_poc=False -> 不分色
    assert '0.12' in js2                           # profile_frac

    # 副图模式：y 用档位序号（分层直方图）
    js_idx = rt._vp_draw_js(40, VPStyle(), 'row.vmax', True, 'VPX')
    assert 'base = 0; bw = 1;' in js_idx


def test_vpstyle_drives_the_spec(headless):
    """`vpstyle`（写在指标类上或构造时传入）要进 spec，并覆盖 linestyle 的颜色。"""
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas
    from minibt.utils import VPStyle

    k = LocalDatas.test.kline
    # 1) 默认：读的是 RollingVolumeProfile 类上的 vpstyle
    strat = _make(k.tradingview.RollingVolumeProfile())
    spec = [s for s in rt.extract_minibt_indicators(strat, 0)
            if s.kind == 'VolumeProfile'][0]
    assert spec.vpstyle is not None
    assert spec.vp_color == '#3498db' and spec.vp_poc_color == '#f39c12'
    assert spec.vpstyle['profile_frac'] == 0.30
    assert spec.vpstyle['bin_ratio'] == 0.88

    # 2) 构造时用 vpstyle= 覆盖
    strat2 = _make(k.tradingview.RollingVolumeProfile(
        vpstyle=VPStyle(bar_color='#ff5722', poc_color='#9c27b0',
                        fill_alpha=0.4, profile_frac=0.18,
                        bin_ratio=0.6, price_bars=120,
                        highlight_poc=False)))
    spec2 = [s for s in rt.extract_minibt_indicators(strat2, 0)
             if s.kind == 'VolumeProfile'][0]
    assert spec2.vp_color == '#ff5722' and spec2.vp_poc_color == '#9c27b0'
    assert spec2.vp_frac == 0.18
    assert spec2.vp_price_bars == 120
    assert spec2.vpstyle['highlight_poc'] is False
    assert spec2.vpstyle['bin_ratio'] == 0.6


def test_volume_profile_builds_custom_series(headless):
    """构建后要真的下发 `createCustomSeries`（带 rendererDraw 回调）。"""
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    strat = _make(k.tradingview.RollingVolumeProfile())
    chart = rt.RealtimeChart([strat], browser=False, realtime=False,
                             bars='chart', theme='dark', info_pages=False)
    scripts = '\n'.join(getattr(chart.chart, '_scripts', []) or [])

    assert scripts.count('createCustomSeries') == 1, scripts[-300:]
    assert 'minibt_vp_draw_' in scripts
    assert 'rendererDraw' in scripts
    # 三个 JS 回调：rendererDraw / priceValueBuilder / isWhitespace
    assert scripts.count('registerCallback') == 3
    # 鼠标跟随：纯 JS 十字线监听 + 强制重绘
    assert 'addCrosshairListener' in scripts
    assert 'applyOptions({})' in scripts

    # 逐根数据：time + lo/hi/vmax + vp0..vp39
    spec = [s for s in chart.indicators.specs
            if s.kind == 'VolumeProfile'][0]
    n = spec.profile.shape[0]
    frame = pd.DataFrame({'time': list(range(n)),
                          'low': np.arange(n, dtype=float),
                          'high': np.arange(n, dtype=float) + 2.0})
    df = chart.indicators._vp_frame(spec, frame)
    assert df is not None and len(df) == n
    assert {'time', 'lo', 'hi', 'vmax', 'vp0', 'vp39'} <= set(df.columns)
    assert np.isfinite(df['lo']).all() and np.isfinite(df['hi']).all()
    assert np.isfinite(df['vmax']).all() and (df['vmax'] > 0).all()


def test_vp_price_bands_roll_per_bar(headless):
    """档区按 ``price_bars`` 逐根滚动（不是全段一刀切）。"""
    import minibt.strategy.realtime as rt
    from minibt import LocalDatas

    k = LocalDatas.test.kline
    frame = k.pandas_object.copy() if hasattr(k, 'pandas_object') else k
    lo, hi = rt._vp_price_bands(frame, 20, 40)
    assert lo is not None and len(lo) == len(frame)
    assert hi is not None
    # 第一根的档区只含它自己，最后一根含前 20 根 -> 区间应更宽
    assert (hi[-1] - lo[-1]) >= (hi[0] - lo[0])
    assert np.all(hi >= lo)


def _vp_js_payload():
    """构造 `rendererDraw` 执行测试用的数据（minibt + 示例两份 JS）。"""
    import json
    import os
    import sys

    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'examples', '11_api_tour'))
    from minibt.utils import VPStyle
    import minibt.strategy.realtime as rt
    import _volume_profile as vp

    nb = 4
    rows = []
    for i in range(5):
        row = {'lo': 100.0, 'hi': 200.0, 'vmax': 100.0}
        for j in range(nb):
            row[f'vp{j}'] = 0.0
        row[f'vp{i % nb}'] = 100.0
        rows.append(row)
    bars = [{'x': float(10 * (i + 1)), 'originalData': rows[i]}
            for i in range(5)]
    payload = {
        'minibt_price': rt._vp_draw_js(nb, VPStyle(), 'row.vmax', False, 'VPX'),
        'minibt_index': rt._vp_draw_js(nb, VPStyle(), 'row.vmax', True, 'VPX'),
        'example_price': vp._draw_js(nb, 0.30, 'VPX', True),
        'example_index': vp._draw_js(nb, 0.30, 'VPX', False),
        'bars': bars,
    }
    return json.dumps(payload)


_NODE_RUN = r'''
const fs = require('fs');
const cfg = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
function run(js, hoverX) {
  const rects = [];
  const ctx = { fillStyle: null, strokeStyle: null, lineWidth: 1, globalAlpha: 1,
                fillRect: (x, y, w, h) => rects.push([x, y, w, h]),
                strokeRect: (x, y, w, h) => rects.push([x, y, w, h]) };
  const scope = { context: ctx, horizontalPixelRatio: 1, verticalPixelRatio: 1,
                  mediaSize: { width: 918, height: 600 },
                  bitmapSize: { width: 918, height: 600 } };
  const target = { useBitmapCoordinateSpace: (fn) => fn(scope) };
  const view = { visibleBars: () => cfg.bars };
  global.window = { VPX: hoverX };
  new Function('target', 'priceConverter', 'view', js)(target, (p) => 1000 - p, view);
  if (!rects.length) throw new Error('no rects drawn');
  const right = rects[0][0] + rects[0][2];
  if (Math.abs(right - 918) > 1e-6) throw new Error('anchor != mediaSize.width: ' + right);
  return rects.length;
}
for (const [name, js] of Object.entries(cfg)) {
  if (name === 'bars') continue;
  run(js, null); run(js, 250);
}
console.log('VPJS_OK');
'''


def test_vp_draw_js_actually_runs():
    """生成的 `rendererDraw` JS 必须能**真的跑起来**（minibt 与示例两份）。

    历史 bug：`anchor` 写成 `scope.mediaSize.width` 却放在
    `useBitmapCoordinateSpace(scope => ...)` **外面** -> `scope is not
    defined` -> `rendererDraw` 抛错 -> VP（示例 `26`/`27`）整张图不画。
    """
    import json
    import shutil
    import subprocess
    import tempfile

    js = json.loads(_vp_js_payload())
    # 1) `scope.mediaSize.width` 必须在 `useBitmapCoordinateSpace` 之后取
    for name, code in js.items():
        if name == 'bars':
            continue
        assert code.index('useBitmapCoordinateSpace') < \
            code.index('scope.mediaSize.width'), name
    # 2) 真的用 node 跑一遍（没装 node 就只做上面的静态检查）
    node = shutil.which('node')
    if not node:
        pytest.skip('node 不可用，跳过 JS 执行检查')
    with tempfile.TemporaryDirectory() as tmp:
        payload = f'{tmp}/vp.json'
        script = f'{tmp}/vp.js'
        with open(payload, 'w', encoding='utf-8') as handle:
            handle.write(_vp_js_payload())
        with open(script, 'w', encoding='utf-8') as handle:
            handle.write(_NODE_RUN)
        result = subprocess.run([node, script, payload],
                                capture_output=True, text=True, timeout=120)
    assert 'VPJS_OK' in result.stdout, result.stdout + result.stderr
