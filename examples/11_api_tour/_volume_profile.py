"""滚动成交量分布图（Rolling Volume Profile）的共用实现。

只被 ``26_volume_profile.py`` / ``27_volume_profile_live.py`` 引用，本身不是
一个"示例"。核心是两件事：

1. **逐根算分布** —— ``volume_profile`` 把每根 K 线往前 ``window`` 根的 K 线按
   **它自己的档区** ``[min(low), max(high)]`` 等宽切 ``bins`` 份，累加成交量。
   档区逐根滚动（不是全段一刀切），每根的价格档位因此不同。
2. **画横条** —— ``add_vp`` 用 ``add_custom_series(spec={...})`` 挂一条
   自定义 series，绘制逻辑全在 ``rendererDraw`` 里：

   - 每帧取 ``view.visibleBars()``，按**鼠标的 CSS x**（``bar.x`` 也是 CSS
     像素）挑**最近的那根**当锚点；鼠标不在图上就回落到**最右可见**那根。
   - 满量程柱长 ``band`` = 当前**可视跨度 * frac``（随缩放自适应），
     ``left = anchor - 该档量 / vmax * band`` —— 向左生长。
   - 量最大的一档（POC）换一种颜色。
   - 主图用**价格档中心**做 y；副图（``pane_index='new'``）改用**档位序号**。

   ``rendererDraw`` 只在序列**重绘**时被调用，而 lightweight-charts 的十字线
   移动并不重绘序列层，所以 ``add_vp`` 顺手在十字线监听里调一次
   ``series.applyOptions({})`` 强制重绘（实测这是最便宜的触发方式）。
   """
from __future__ import annotations

import re

import numpy as np
import pandas as pd

BINS = 40           # 价格档数
WINDOW = 60         # 每根的滚动窗口（根）
FRAC = 0.30         # 满量程柱长 = 可视跨度 * FRAC


def make_data(rows: int = 400, seed: int = 1126) -> pd.DataFrame:
    """自包含的合成 OHLCV。"""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.7)
    open_ = close + rng.standard_normal(rows) * 0.4
    high = np.maximum(open_, close) + rng.uniform(0.2, 1.6, rows)
    low = np.minimum(open_, close) - rng.uniform(0.2, 1.6, rows)
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': open_, 'high': high, 'low': low, 'close': close,
        'volume': rng.integers(1_000, 50_000, rows),
    })


def volume_profile(df: pd.DataFrame, window: int = WINDOW, bins: int = BINS):
    """逐根算滚动分布，返回 ``(lo, hi, matrix)``。

    ``matrix[i, j]`` = 第 ``i`` 根那一时刻、窗口内成交量落在第 ``j`` 档的和；
    每根的档区是它往前 ``window`` 根的 ``[min(low), max(high)]``。代表价用典型价
    ``(H+L+C)/3``，落到哪个档就 ``np.add.at`` 累加多少量。
    """
    lows = df['low'].to_numpy(dtype=float)
    highs = df['high'].to_numpy(dtype=float)
    closes = df['close'].to_numpy(dtype=float)
    volume = df['volume'].to_numpy(dtype=float)
    n = len(df)

    lo = np.empty(n, dtype=float)
    hi = np.empty(n, dtype=float)
    matrix = np.zeros((n, bins), dtype=float)
    typical = (highs + lows + closes) / 3.0

    for i in range(n):
        start = max(0, i - window + 1)
        seg = slice(start, i + 1)
        lo[i] = np.nanmin(lows[seg])
        hi[i] = np.nanmax(highs[seg])
        if not (hi[i] > lo[i]):
            continue
        width = (hi[i] - lo[i]) / bins
        idx = np.clip(((typical[seg] - lo[i]) / width).astype(int), 0, bins - 1)
        np.add.at(matrix[i], idx, volume[seg])
    return lo, hi, matrix


def build_frame(chart, df: pd.DataFrame, lo, hi, matrix) -> pd.DataFrame:
    """把分布矩阵 + 档区拼成自定义序列的逐根数据（``time/lo/hi/vmax/vp*``）。

    ``vmax`` 是**逐行列**（同一帧内所有根共用一个值）：实时新数据把量做大时
    柱长比例才能跟着变，而同一屏内跨根仍然可比。
    """
    frame = chart.candle_data.copy()          # 已格式化的 time（epoch 秒）
    frame['lo'] = lo
    frame['hi'] = hi
    vmax = float(matrix.max()) if matrix.size else 0.0
    frame['vmax'] = vmax if vmax > 0 else 1.0
    for j in range(matrix.shape[1]):
        frame[f'vp{j}'] = matrix[:, j]
    return frame


def reset_vp_hover(chart, series) -> None:
    """数据一变就把鼠标跟随坐标清空 —— **实时更新优先于鼠标跟随**。

    否则鼠标停在某根 K 线上不动时，分布图会一直卡在那根上，看着像“实时不更新”。
    清掉之后本帧画的是最新一根；鼠标再动一下才重新跟随。
    """
    key = getattr(series, 'vp_mouse_key', None)
    if key:
        chart.run_script(f'window.{key} = null;')


def _draw_js(bins: int, frac: float, mouse_key: str, price_mode: bool) -> str:
    """``rendererDraw``：**位置固定在可视范围最右端**（与 bokeh 一致），
    只有**数值**跟随鼠标（画鼠标最近那根的分布）。"""
    if price_mode:
        # 价格模式：档区逐根不同 -> 从该根的 `lo/hi` 现算 y 与档高
        geometry = (
            "  const lo = row.lo, hi = row.hi;\n"
            "  if (!(isFinite(lo) && isFinite(hi) && hi > lo)) return;\n"
            "  base = lo; bw = (hi - lo) / %(bins)d;\n"
        )
    else:
        # 档位序号模式：y 就是 0..bins（分层直方图）
        geometry = "  base = 0; bw = 1;\n"
    return (
        "const bars = view.visibleBars();\n"
        "if (!bars.length) return;\n"
        "const first = bars[0], lastVis = bars[bars.length - 1];\n"
        "const band = Math.max(Math.abs(lastVis.x - first.x), 1) * %(frac)s;\n"
        # 只有 row（要画哪根的分布）跟随鼠标。鼠标不在图上 -> 用最右那根。
        "let last = lastVis;\n"
        "const hx = window.%(mouse)s;\n"
        "if (hx !== null && hx !== undefined) {\n"
        "  let best = null, bd = Infinity;\n"
        "  for (const b of bars) { const d = Math.abs(b.x - hx); if (d < bd) { bd = d; best = b; } }\n"
        "  if (best) last = best;\n"
        "}\n"
        "const row = last.originalData;\n"
        "let mx = 0;\n"
        "for (let j = 0; j < %(bins)d; j++) { const q = row['vp' + j] || 0; if (q > mx) mx = q; }\n"
        "if (!(mx > 0)) return;\n"
        "let base = 0, bw = 1;\n"
        "if (%(price_mode)s) {\n"
        + geometry +
        "}\n"
        "target.useBitmapCoordinateSpace(scope => {\n"
        "  const ctx = scope.context;\n"
        "  const h = scope.horizontalPixelRatio;\n"
        "  const v = scope.verticalPixelRatio;\n"
        # ★ 锚点 = 绘图区**最右端**（可视 X 轴的右端，与主图成交量柱的最右边对齐）。
        #   必须在 useBitmapCoordinateSpace 的 scope 里取。
        "  const anchor = scope.mediaSize.width;\n"
        "  for (let j = 0; j < %(bins)d; j++) {\n"
        "    const q = row['vp' + j] || 0;\n"
        "    if (!(q > 0)) continue;\n"
        "    const w = q / row.vmax * band;\n"
        "    const y0 = priceConverter(base + j * bw);\n"
        "    const y1 = priceConverter(base + (j + 1) * bw);\n"
        "    if (!isFinite(y0) || !isFinite(y1)) continue;\n"
        "    ctx.fillStyle = (q >= mx) ? '#f39c12' : '#3498db';\n"
        "    ctx.fillRect((anchor - w) * h, Math.min(y0, y1) * v,\n"
        "                 w * h, Math.abs(y1 - y0) * v * 0.88);\n"
        "  }\n"
        "});"
    ) % {'bins': int(bins), 'frac': repr(float(frac)),
         'mouse': mouse_key, 'price_mode': 'true' if price_mode else 'false'}


def add_vp(chart, frame, name: str, pane_index=None, price_mode: bool = True):
    """挂一条 VP 系列：自定义 paneView + 三个 JS 回调 + 鼠标跟随监听。"""
    suffix = re.sub(r'\W+', '_', str(name)).strip('_')
    draw = f'vp_draw_{suffix}'
    prices = f'vp_price_{suffix}'
    empty = f'vp_empty_{suffix}'
    hover = f'vpHover_{suffix}'
    mouse_key = f'__vpMouse_{suffix}'
    bins = sum(1 for c in frame.columns if str(c).startswith('vp'))

    chart.register_js_callback(draw, ['target', 'priceConverter', 'view'],
                               _draw_js(bins, FRAC, mouse_key, price_mode))
    if price_mode:
        chart.register_js_callback(
            prices, ['row', 'view'],
            'return (row.lo === row.hi) ? null : [row.lo, row.hi];')
    else:
        chart.register_js_callback(prices, ['row', 'view'],
                                   f'return [0, {bins}];')
    chart.register_js_callback(empty, ['data', 'view'], 'return false;')

    series = chart.add_custom_series(
        name=name, pane_index=pane_index, color='#3498db',
        spec={'rendererDraw': draw, 'priceValueBuilder': prices,
              'isWhitespace': empty,
              'defaultOptions': {'lastValueVisible': False,
                                 'priceLineVisible': False}})
    series.set(frame, format_cols=False)
    # 让调用方能在数据更新后清掉鼠标跟随（`reset_vp_hover`）
    series.vp_mouse_key = mouse_key

    # 鼠标跟随：纯 JS 的十字线监听（不回调 Python），把鼠标 CSS x 存到
    # window[mouse_key]；顺手 applyOptions({}) 强制序列重绘（十字线移动本身
    # 不会重绘序列层）。鼠标移出图表时 param.point 为空 -> null -> 回落。
    chart.run_script(
        f'if (window.{hover}) {chart.id}.removeCrosshairListener(window.{hover});\n'
        f'window.{hover} = (param) => {{\n'
        f'  window.{mouse_key} = (param && param.point) ? param.point.x : null;\n'
        f'  try {{ {series.id}.applyOptions({{}}); }} catch (e) {{}}\n'
        f'}};\n'
        f'{chart.id}.addCrosshairListener(window.{hover});')
    return series
