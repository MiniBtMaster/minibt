from __future__ import annotations
from bokeh.embed import file_html
from bokeh.resources import INLINE, CDN
from copy import deepcopy
import warnings
from bokeh.palettes import Category10
from .strategy import Strategy
import os
import bokeh.colors.named as bcn
from itertools import cycle
from ..indicators import pd, np, Callable
from ..utils import text_width_pt,resolve_signal_text_style, signal_text_below
# [新增] marker 兼容: 把 Markers 里的 lightweight_charts 专用名
#   (arrow_up/arrow_down) 与 label_up/label_down 收敛为 bokeh 可渲染名
from ..constant import to_bokeh_marker
from functools import partial
from bokeh.models import Tabs
from bokeh.transform import factor_cmap
from bokeh.models import (
    CrosshairTool,
    CustomJS,
    ColumnDataSource,
    NumeralTickFormatter,
    Span,
    HoverTool,
    Range1d,
    WheelZoomTool,
    LabelSet,
    Band,
)
from bokeh.layouts import gridplot, column, row
from bokeh.io import show
from bokeh.plotting import figure as _figure
from bokeh.models.glyphs import VBar
setattr(_figure, '_main_ohlc', False)
setattr(_figure, '_candles', False)

try:  # 版本API有变
    from bokeh.models import TabPanel as Panel
except:
    from bokeh.models import Panel
warnings.filterwarnings("ignore", category=UserWarning)
# 'JPY_PARENT_PID' in os.environ
# IS_JUPYTER_NOTEBOOK = 'JPY_INTERRUPT_EVENT' in os.environ
try:
    from IPython import get_ipython
    _shell = get_ipython()
    IS_JUPYTER_NOTEBOOK = _shell is not None and _shell.__class__.__name__ == 'ZMQInteractiveShell'
except (ImportError, AttributeError):
    IS_JUPYTER_NOTEBOOK = False
FILED = ['open', 'high', 'low', 'close']
_FILED = ['datetime', 'open', 'high', 'low', 'close', 'volume']
_FILED = ['datetime', 'open', 'high', 'low', 'close', 'volume']
_factors_plot: Callable = None

DARK_TABS_CSS = """
    :host(.dark-tabs) {
        background-color: #1a1a1a;
        border-color: #333;
    }
    :host(.dark-tabs) .bk-tabs-header {
        background-color: #333;
    }
    :host(.dark-tabs) .bk-tab {
        color: #ccc;
        border-color: #666;
    }
    :host(.dark-tabs) .bk-active {
        background-color: #1a1a1a;
        color: #fff;
    }
    """
panel_CUSTOM_CSS = """
:host {
    height: auto;
}
.bk-Column {
    display: flex;
    flex-direction: column;
    height: auto;
}
.bk-Column > * {
    flex: 0 0 auto;
}
"""


def ffillnan(arr: np.ndarray) -> np.ndarray:
    if len(arr.shape) > 1:
        arr = pd.DataFrame(arr)
    else:
        arr = pd.Series(arr)
    arr.ffill(inplace=True)
    arr.bfill(inplace=True)
    return arr.values


def set_tooltips(fig: _figure, tooltips=(), vline=True, renderers=(), if_datetime: bool = True, if_date=False) -> None:
    tooltips = list(tooltips)
    renderers = list(renderers)

    if if_datetime:
        formatters = {'@datetime': 'datetime'}
        if if_date:
            tooltips += [("Datetime", "@datetime{%Y-%m-%d}")]
        else:
            tooltips += [("Datetime", "@datetime{%Y-%m-%d %H:%M:%S}")]
    else:
        formatters = {}
    fig.add_tools(HoverTool(
        point_policy='follow_mouse',
        renderers=renderers, formatters=formatters,
        tooltips=tooltips, mode='vline' if vline else 'mouse'),
    )


def new_bokeh_figure(plot_width, height=300) -> Callable:
    return partial(
        _figure,
        x_axis_type='linear',
        width=plot_width,
        height=height,
        width_policy='max',
        tools="xpan,xwheel_zoom,box_zoom,undo,redo,reset,save",  # ,crosshair
        active_drag='xpan',
        active_scroll='xwheel_zoom')


def new_bokeh_figure_main(plot_width, height=150) -> Callable:
    return partial(
        _figure,
        x_axis_type='linear',
        width_policy='max',
        width=plot_width,
        height=height,
        tools="xpan,xwheel_zoom",  # ,crosshair
        active_drag='xpan',
        active_scroll='xwheel_zoom')


def new_indicator_figure(new_bokeh_figure: Callable, fig_ohlc: _figure, plot_width, height=80, **kwargs) -> _figure:
    height = int(height) if height and height > 10 else 80
    fig = new_bokeh_figure(plot_width, height)(x_range=fig_ohlc.x_range,
                                               active_scroll='xwheel_zoom',
                                               active_drag='xpan',
                                               **kwargs)
    fig.xaxis.visible = False
    fig.yaxis.minor_tick_line_color = None
    return fig


def search_index(ls: list[list], name) -> tuple[int]:
    for i, ls1 in enumerate(ls):
        for j, ls2 in enumerate(ls1):
            if ls2 == name:
                return i, j
    assert False, "找不到索引"


def colorgen():
    yield from cycle(Category10[10])


def _span_values(indicator, isplot):
    """取「当前指标里被绘制的那几列」的数值 —— 给自动均值虚线用。

    ★ [BUG 修复] 调用它的那段代码位于 ``for j in range(len(isplot)):`` 的
      **for-else** 子句里：VP 指标（``category='vp'``）的 ``isplot`` 全为 False，
      循环体一次都没执行，但 **for-else 仍会执行** —— 原代码直接用了 ``ind``，
      而它此时还是**上一个指标遗留的变量**（可能是 list），于是
      ``ind.astype(np.float32)`` 抛 ``AttributeError: 'list' object has no
      attribute 'astype'``（纯 VP 副图 ``RollingVolumeProfile(overlap=False)`` 必崩）。
      这里改为按当前指标的“要绘制的列”重新取数，既不崩、均值也才对得上。
    """
    try:
        a = np.asarray(indicator, dtype=np.float64)
        if a.ndim > 1:
            m = np.asarray(isplot, dtype=bool)
            if m.size != a.shape[1]:
                m = np.ones(a.shape[1], dtype=bool)
            if m.any():
                a = a[:, m]
        return a.reshape(-1).astype(np.float32)
    except Exception:
        try:
            return np.asarray(indicator, dtype=np.float32).reshape(-1)
        except Exception:
            return np.array([], dtype=np.float32)



def _nan_reduce_axis1(a, mode: str) -> np.ndarray:
    """按行做 NaN 安全的 max/min(等价 ``np.nanmax`` / ``np.nanmin``),
    但对整行全 NaN 不会触发 RuntimeWarning, 而是返回 NaN。

    框架用该结果生成副图的 ``*_h`` / ``*_l`` 极值列, 供前端 autoscale
    回调按可视区间缩放副图 y 轴。若直接用 ``np.max`` / ``np.min``, 只要
    某行存在 NaN(例如 vbar 信号柱在无信号处恒为 NaN)整行极值即为 NaN,
    前端会把副图 y_range 设成 NaN, 表现为缩放/拖动后副图空白。
    """
    arr = np.asarray(a, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    valid = ~np.isnan(arr)
    fill = -np.inf if mode == 'max' else np.inf
    filled = np.where(valid, arr, fill)
    out = filled.max(axis=1) if mode == 'max' else filled.min(axis=1)
    out[~valid.any(axis=1)] = np.nan
    return out


# ======================================================================
# Volume Profile（`category == 'vp'`）绘制
# ======================================================================
def _vp_interactive(fig, vp_src, indicator, vidx, vmax, band, anchor,
                    bar_color, poc_color, ax_vol=None, vticks=None,
                    profile_frac: float = 0.30,
                    lo_arr=None, hi_arr=None, y_mode: str = 'price'):
    """照 test8.py 的 **ANCHOR_MODE="right_edge"** 给 VP 加交互。

    与 test8 完全一致的几何约定（都在**主轴 index 数据单位**里算, 不换坐标系）::

        span   = x1 - x0                    # 当前**可见**序号跨度(RangesUpdate 自带)
        BAND   = span * PROFILE_FRAC        # 满量程柱长(随缩放自适应)
        anchor = x1                         # ★ right_edge: 锚点=视口右端=成交量 0 刻度
        right  = anchor                     # 柱右端 = 0 刻度
        left   = anchor - v / VMAX * BAND   # 向左生长

    触发源（缺一不可, 且事件必须进 `subscribed_events` 否则前端根本不发）:
    - `MouseMove`    -> 统计"鼠标所在那根 K 线 + 前 LEN-1 根"
    - `MouseLeave`   -> 回到"最右可见 K 线"
    - `RangesUpdate` -> ★ 拖动/缩放主通道(自带 x0/x1), 统计"最右可见 K 线"
    - `x_range` 的 start/end 变化 -> 兜底再对齐一次
    """
    try:
        from bokeh.models import (ColumnDataSource as _VPCDS,
                                  CustomJS as _VPCJS)
        from bokeh.events import MouseMove, MouseLeave, RangesUpdate
        # 注意: 传进来的 indicator **已经是切好的 VP 切片**(调用端做了 _ind2[:, _vidx]),
        #   不能再按 vidx 切一次(否则 IndexError)。vidx 仅作兼容保留。
        prof = np.asarray(indicator)
        if prof.ndim == 1:
            prof = prof.reshape(-1, 1)
        roll = _VPCDS(dict(
            {"x": np.arange(prof.shape[0], dtype=np.float64)},
            **{f"p{j}": prof[:, j] for j in range(prof.shape[1])}))
        code = """
// ★ NB 必须是**档数**(矩阵列数), 不能取 p0.length ——
//   p{j} 是矩阵的一列, 长度 = K线根数! 取错会让循环去访问不存在的
//   p40/p41... -> undefined[i] -> 每次回调抛错 -> 分布永远不更新。
const dt = roll.data["x"], N = dt.length, NB = N_BINS;
const xr = range;
function barAt(t){
  if (t == null || isNaN(t)) return N - 1;
  return Math.max(0, Math.min(N - 1, Math.round(t)));
}
function showBar(i, x0, x1){
  i = Math.max(0, Math.min(N - 1, i));
  const span = (x0 != null && x1 != null && x1 > x0) ? (x1 - x0) : N;
  const BAND = span * FRAC;
  const anchor = (x1 != null && x1 > x0) ? x1 : (N - 1);   // ★ right_edge
  const vol = [], left = [], right = [], col = [];
  let mx = 0;
  for (let j = 0; j < NB; j++){
    const v = roll.data["p" + j][i] || 0;
    vol.push(v); if (v > mx) mx = v;
  }
  // ★ 档区逐根滚动: 锚点那根的档区决定柱子的 y(价格档中心)与 height(档高)。
  //   只改 left/right 而不改 y/height, 鼠标移到别的 K 线时分布就会落在错误的价位。
  if (YMODE === 'price' && LO != null && HI != null){
    const lo = LO[i], hi = HI[i];
    if (isFinite(lo) && isFinite(hi) && hi > lo){
      const bw = (hi - lo) / NB;
      const yv = [], ht = [];
      for (let j = 0; j < NB; j++){
        yv.push(lo + (j + 0.5) * bw);
        ht.push(bw * 0.88);
      }
      src.data["y"] = yv; src.data["height"] = ht;
    }
  }
  for (let j = 0; j < NB; j++){
    right.push(anchor);
    left.push(anchor - vol[j] / VMAX * BAND);
    col.push((mx > 0 && vol[j] >= mx) ? POC : BAR);
  }
  src.data["left"] = left; src.data["right"] = right; src.data["color"] = col;
  src.change.emit();
  if (ax_vol != null && VTICKS != null){
    const tk = [], ov = {};
    for (let k = 0; k < VTICKS.length; k++){
      const x = anchor - VTICKS[k] / VMAX * BAND;
      tk.push(x); ov[x] = VTICKS[k].toLocaleString();
    }
    ax_vol.ticker.ticks = tk;
    ax_vol.major_label_overrides = ov;
  }
}
showBar(barAt(xr.end), xr.start, xr.end);
"""
        args = dict(roll=roll, src=vp_src, VMAX=vmax, FRAC=profile_frac,
                    N_BINS=int(prof.shape[1]),
                    BAR=bar_color, POC=poc_color, range=fig.x_range,
                    ax_vol=ax_vol, VTICKS=vticks,
                    # ★ 逐根档区（与指标端同一规则）: LO/HI 为每根 K 线的
                    #   [min(low), max(high)] 数组, 供 JS 按锚点重算 y/height。
                    LO=(None if lo_arr is None else np.asarray(lo_arr, dtype=np.float64)),
                    HI=(None if hi_arr is None else np.asarray(hi_arr, dtype=np.float64)),
                    YMODE=y_mode)
        cb_init = _VPCJS(args=args, code=code)
        cb_move = _VPCJS(args=args, code=code + "showBar(barAt(cb_obj.x), xr.start, xr.end);")
        cb_leave = _VPCJS(args=args, code=code + "showBar(barAt(xr.end), xr.start, xr.end);")
        cb_rng = _VPCJS(args=args, code=code + "showBar(barAt(cb_obj.x1), cb_obj.x0, cb_obj.x1);")
        fig.js_on_event(MouseMove, cb_move)
        fig.js_on_event(MouseLeave, cb_leave)
        fig.js_on_event(RangesUpdate, cb_rng)          # ★ 拖动/缩放主通道
        for _e in ("mousemove", "mouseleave", "rangesupdate"):
            fig.subscribed_events.add(_e)              # ★ 不订阅前端就不发事件
        for _e in ("start", "end"):                    # 兜底
            fig.x_range.js_on_change(_e, cb_init)
    except Exception as _e:
        import sys as _s
        print(f"[volume_profile] 交互挂载失败: {type(_e).__name__}: {_e}", file=_s.stderr)

def _add_volume_profile(fig, cds, indicator, df, ic,
                        black_color=None, profile_frac: float = 0.30,
                        y_mode: str = 'price', bar_color=None, poc_color=None,
                        vidx=None, price_bars=None, y_range_name=None,
                        show_vol_axis: bool = True,
                        y_tick_labels: bool = True):
    """在价格图上叠加**滚动 Volume Profile**（右端=0刻度、向左生长、贴右缘）。

    数据约定（与 `RollingVolumeProfile` 指标端一致）
    -------------------------------------------------
    - `indicator` 形状 `(K线根数, 档数)`；一维时当作"只有 1 档"；
    - **列 = 等宽价格档**，档位区间为 `[min(low), max(high)]`（**同一段 df**）；
    - 第 i 行第 j 列 = 该时刻窗口内落在第 j 档的成交量之和。

    本函数只画**最后一行**（最新时刻）的分布 —— 即 `ANCHOR_MODE="right_edge"`：
      锚点(柱右端/0刻度) = 最后一根 K 线的 index
      满量程柱长        = 数据宽度 × profile_frac
      柱长 = 该档成交量 / 全矩阵最大成交量 × 满量程柱长   （向左生长）
    与 test8 一样: x 用的是**主轴 index 坐标**，与 K 线共用同一套 transform，
    因此不存在"两套坐标系换算"导致的错位。
    """
    prof = np.asarray(indicator, dtype=np.float64)
    if prof.ndim == 1:
        prof = prof.reshape(-1, 1)          # 一维 -> (n, 1)
    if prof.ndim != 2 or prof.shape[0] == 0:
        return None
    n, nb = prof.shape

    # ---- 价格档（与指标端**同一条规则**）----
    #   指标端 RollingVolumeProfile.next() 默认只用**最后 price_bars 根**的
    #   [min(low), max(high)] 定档位（档位数固定，若覆盖整段数据则只有极少数档
    #   落在滚动窗口内 -> 图上只剩 2~3 根柱子）。这里必须用同一条规则，
    #   否则横条的价格位置会与指标算出的分布对不上。
    try:
        _pb = None if price_bars is None else int(price_bars)
    except Exception:
        _pb = None
    if _pb is not None and 0 < _pb < len(df):
        lo = float(np.nanmin(df['low'].values[-_pb:]))
        hi = float(np.nanmax(df['high'].values[-_pb:]))
    else:
        lo = float(np.nanmin(df['low'].values))
        hi = float(np.nanmax(df['high'].values))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return None
    edges = np.linspace(lo, hi, nb + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0
    bin_h = (hi - lo) / nb

    # ---- [新增] 每根 K 线**自己**的档区（滚动, 与指标端 next() 完全同一条规则）----
    #   为什么需要: JS 交互时锚点会落到**任意一根** K 线上, 柱子的 y（价格档中心）
    #   与 height（档高）必须用**那一根**的档区来算 —— 否则鼠标移到早期 K 线时,
    #   分布会被放在错误的价位/用错的档高。
    #   注意 i = 最后一根时该区间恰等于上面用 price_bars 算出的 [lo, hi] ->
    #   初始绘制（= 最后一根的分布）与这里完全一致。
    _lows = np.asarray(df['low'].values, dtype=np.float64)
    _highs = np.asarray(df['high'].values, dtype=np.float64)
    if _pb is not None and 0 < _pb < len(_lows):
        _lo_arr = np.empty(len(_lows), dtype=np.float64)
        _hi_arr = np.empty(len(_lows), dtype=np.float64)
        for _i in range(len(_lows)):
            _a = _i - _pb + 1
            if _a < 0:
                _a = 0
            _lo_arr[_i] = np.nanmin(_lows[_a:_i + 1])
            _hi_arr[_i] = np.nanmax(_highs[_a:_i + 1])
    else:
        _lo_arr = np.full(len(_lows), lo)
        _hi_arr = np.full(len(_lows), hi)

    # y 坐标: 主图用**价格档中心**; 副图(overlap=False)不是价格轴, 改用**档位序号**
    #   -> 画成"分层直方图", 每档一根横条(0 刻度仍在右端)
    if y_mode == 'index':
        y_vals = np.arange(nb, dtype=np.float64)
        bar_h = 0.88
    else:
        y_vals = centers
        bar_h = bin_h * 0.88

    row = prof[-1]                                    # 最新一根的分布
    vmax = float(np.nanmax(prof)) if np.isfinite(prof).any() else 0.0
    vmax = vmax if vmax > 0 else 1.0                  # 固定量程(跨时刻可比)

    # ---- x: 主轴 index 坐标 ----
    x = np.arange(n, dtype=np.float64)
    anchor = float(x[-1])                             # 锚点 = 右端 = 0 刻度
    band = (float(x[-1]) - float(x[0])) * float(profile_frac)   # 满量程柱长

    left = anchor - np.nan_to_num(row, nan=0.0) / vmax * band
    right = np.full(nb, anchor)
    row_max = np.nanmax(row) if np.isfinite(row).any() else 0.0
    _bar = bar_color or '#3498db'
    _poc = poc_color or '#f39c12'
    colors = [_poc if v >= row_max else _bar for v in row]

    # ★ [新增] 副图(overlap=False)专用: 给 VP 一个**自己的 y range**。
    #   为什么需要: 副图里往往还有普通指标线(如 RSI, 值域 0~100), 而 VP 的 y 是
    #   **档位序号**(0..nb-1)。两者共用同一个自动纵轴时: 柱子高度 0.88 相对 100
    #   只有 0.9%(细如发丝), 而且框架的 autoscale 回调会把副图纵轴设成指标线的
    #   极值(indicators_h/l 只统计 isplot=True 的列) -> 柱子直接落到可视范围之外
    #   -> 用户看到的是“只有指标线, 右端根本没有 VP 图”。
    #   修法: 档位数在 Python 侧就是已知的, 所以直接给一根**固定 Range1d**
    #   (-0.5 .. nb-0.5) 挂到 extra_y_ranges, hbar 用 y_range_name 指过去 ——
    #   不需要任何 JS 镜像（之前“A 方案”失败是因为要去镜像主图的 DataRange1d;
    #   这里是自建的固定 range，性质完全不同）。autoscale 只改 fig.y_range。
    _yrn = None
    if y_range_name:
        try:
            from bokeh.models import Range1d as _VPRange
            fig.extra_y_ranges[y_range_name] = _VPRange(
                start=-0.5, end=max(nb - 0.5, 0.5))
            _yrn = y_range_name
        except Exception:
            _yrn = None

    # ★ 分布图用**自己的** ColumnDataSource(与 test8.py 一致):
    #   档数(40)与 K 线根数(几千)本来就不同, 塞进同一个源会造成列长不一致
    #   -> bokeh 截断整张图 / 柱子错位 / 出现垂直线。独立源彻底避免。
    from bokeh.models import ColumnDataSource
    # ★ height 也做成**列**（不再是标量）: 档区逐根滚动后, 档高 = (hi_i-lo_i)/nb
    #   会随锚点变, 必须能由 JS 改写。
    _vp_src = ColumnDataSource(dict(y=y_vals, left=left, right=right,
                                    height=np.full(nb, bar_h, dtype=np.float64),
                                    color=colors))
    if y_mode == 'index' and y_tick_labels:
        # 副图的 y 是档位序号 -> 刻度标上该档的价格中心, 便于读数。
        # ★ 是否标刻度由调用处决定(y_tick_labels):
        #   - 副图里**只有 VP**(没有指标线) -> True: 标价格中心, 读者能对上价位;
        #   - 副图里还有指标线(如 RSI) -> False: 不能改 fig.yaxis, 否则会把
        #     指标线自己的纵轴刻度覆盖掉。
        try:
            from bokeh.models import FixedTicker
            _st = max(1, nb // 8)
            _bt = list(range(0, nb, _st))
            fig.yaxis.ticker = FixedTicker(ticks=[float(b) for b in _bt])
            fig.yaxis.major_label_overrides = {
                float(b): f"{centers[b]:.1f}" for b in _bt}
            fig.yaxis.axis_label = "价格档"
        except Exception:
            ...
    # [改回] 原「A 方案」在此为 VP 建独立 y range(extra_y_ranges['vp_y'])
    #   并用 JS 镜像主 y 轴。实测: DataRange1d 的 start/end 在**模型层恒为
    #   null**(真值只在 view 里算), 镜像回调的条件永不成立 -> vp_y 永远停在
    #   整段价格范围 [lo, hi], VP 柱子的价格坐标与 K 线对不上 => 主图上出现
    #   大量"垂直线"。而 VP 的 y 值本来就落在 [min(low), max(high)] 内
    #   (= K 线自身范围), 根本不会撑宽主 Y 轴, 故该方案整体多余, 直接去掉:
    # ★ [更正] 上面"DataRange1d 的 start/end 在**模型层恒为 null**"的说法**不准确**:
    #   bokehjs 的 DataRange1d.update() 确实会在模型层写入 start/end(模型初值 null
    #   只是"还没 update"), 所以"镜像回调条件永不成立"这个理由不成立; 放弃该方案的
    #   真正原因就是后半句 —— VP 的 y 本就 ⊆ K 线范围, 独立 y range 多余。
    #   而 update() 会用**全部数据**覆盖 start/end, 这正是 Y 轴缩放"先跟随可见 K 线、
    #   随即弹回全段范围"的根因, 已在 autoscale_cb.js 里用 have_updated_interactively 修掉。
    #   from bokeh.models import Range1d as _VPRange, CustomJS as _VPMir
    #   _vp_y_rng = _VPRange(start=float(centers[0]), end=float(centers[-1]))
    #   fig.extra_y_ranges['vp_y'] = _vp_y_rng
    #   _mirror = _VPMir(args=dict(a=fig.y_range, b=_vp_y_rng), code="...")
    #   fig.y_range.js_on_change('start', _mirror)
    #   fig.y_range.js_on_change('end', _mirror)
    # ⚠ y_range_name 传 None 会被 bokeh 校验拒绝
    #   (ValueError: expected a value of type str, got None) -> 所以 None 时
    #   **不要**把这个 kwarg 传给 hbar, 否则 overlay 的 VP 会被 try/except 静默跳过。
    _hbar_kw = {} if _yrn is None else {'y_range_name': _yrn}
    r = fig.hbar(y='y', left='left', right='right', height='height',
                 **_hbar_kw,
                 source=_vp_src, fill_color='color', line_color="white",
                 line_width=0.4, alpha=0.6)
    # ---- 成交量刻度轴: 位置 = 锚点 - v/vmax*band, 标签仍是 v ----
    _ax, _vt = None, None          # 下面 try 里创建; 失败也要能交互
    # ★ [开关 show_vol_axis] False = **不画**这根“成交量刻度轴”（挂在图顶、
    #   标签“成交量（右→左 递增）”、刻度数字出现在图的右上角）。
    #   为什么要开关：副图(overlap=False)里 VP 是**背景分布**，顶部再挂一根
    #   成交量轴又挤又容易和副图自己的纵轴刻度打架，所以副图默认关掉
    #   （调用处传 show_vol_axis=is_overlay）。价格主图的 VP 仍然保留。
    #   需要恢复：传 show_vol_axis=True 即可 —— 原逻辑一字未删，只是被 if 包住。
    if show_vol_axis:
        try:
            from bokeh.models import LinearAxis, FixedTicker
            _vt = [0.0, vmax * .25, vmax * .5, vmax * .75, vmax]
            _tk = [anchor - _v / vmax * band for _v in _vt]
            _ax = LinearAxis(axis_label="成交量（右→左 递增）",
                             axis_line_color=None, major_tick_line_color=None,
                             minor_tick_line_color=None,
                             major_label_text_font_size="9pt")
            _ax.ticker = FixedTicker(ticks=_tk)
            _ax.major_label_overrides = {float(_t): f"{_v:,.0f}"
                                         for _t, _v in zip(_tk, _vt)}
            fig.add_layout(_ax, "above")
        except Exception:
            ...
    # 让分布柱垫在 K 线下面（渲染顺序 = 加入顺序, 这里重排一下）
    try:
        from bokeh.models.glyphs import HBar
        fig.renderers = sorted(fig.renderers, key=lambda x_: not isinstance(
            x_.glyph, (HBar, VBar)))
    except Exception:
        ...
    _vp_interactive(fig, _vp_src, indicator, vidx, vmax, band, anchor,
                    _bar, _poc, ax_vol=_ax, vticks=_vt,
                    profile_frac=profile_frac,
                    lo_arr=_lo_arr, hi_arr=_hi_arr, y_mode=y_mode)
    try:
        r.tags = ['__vp_excl__']
    except Exception:
        ...
    return r


def plot(strategys: list[Strategy],
         trade_signal: bool = True,
         black_style: bool = False,
         open_browser: bool = False,
         plot_width: int = None,
         plot_cwd: str = "",
         plot_name: str = "",
         save_plot: bool = False,
         volume_mode: str = 'sub') -> Tabs:
    """
    Like much of GUI code everywhere, this is a mess.
    """
    from bokeh.io import reset_output
    reset_output()
    global IS_JUPYTER_NOTEBOOK, _factors_plot

    black_color = "white" if black_style else "black"
    white_color = "black" if black_style else "white"
    num = len(strategys)
    s_name: list[str] = [t.__class__.__name__ for t in strategys]
    results: list[list[pd.DataFrame]] = [t.get_results()
                                         for t in strategys]  # 回测结果
    
    # 修复：在 replay 模式下，使用_plot_datas 中的 K 线数据（已截断），而不是原始数据
    datas: list[list[pd.DataFrame]] = []
    for t in strategys:
        if getattr(t, '_strategy_replay', False) and hasattr(t, '_plot_datas') and t._plot_datas:
            # 使用_plot_datas 中已截断的 K 线数据
            datas.append(t._plot_datas[1])
        else:
            # 非 replay 模式使用原始数据
            datas.append([data for data in t._btklinedataset.values()])
    
    # ===== DEBUG: 打印数据长度信息 =====
    # print("\n" + "="*60)
    # print("[DEBUG] bokeh_plot.py - plot() 函数数据长度信息")
    # print("="*60)
    for i, s in enumerate(strategys):
        # print(f"\n策略 {i}: {s_name[i]}")
        # print(f"  - min_start_length: {getattr(s, 'min_start_length', 'N/A')}")
        # print(f"  - _strategy_replay: {getattr(s, '_strategy_replay', False)}")
        
        # K 线数据长度
        kline_lengths = [len(d.pandas_object) for d in datas[i]]
        # print(f"  - K 线数据长度 (datas): {kline_lengths}")
        
        # 回测结果长度
        result_lengths = [len(r) for r in results[i]]
        # print(f"  - 回测结果长度 (results): {result_lengths}")
        # 回测结果索引范围
        result_indexes = [(r.index.min(), r.index.max()) for r in results[i]]
        # print(f"  - 回测结果索引范围：{result_indexes}")
        
        # _plot_datas 中的 K 线长度
        if hasattr(s, '_plot_datas') and s._plot_datas:
            plot_kline_lengths = [len(d.pandas_object) if hasattr(d, 'pandas_object') else len(d) for d in s._plot_datas[1]]
            # print(f"  - K 线数据长度 (_plot_datas): {plot_kline_lengths}")
        
        # 指标数据长度
        plot_datas = s.get_plot_datas()
        if len(plot_datas) > 2:
            ind_datas = plot_datas[2]
            for j, ind_data in enumerate(ind_datas):
                if ind_data:
                    for k, ind in enumerate(ind_data):
                        if len(ind) > 8 and hasattr(ind[8], 'shape'):
                            print(f"  - 指标[{j}][{k}] 数据形状: {ind[8].shape}")
    
    # print("="*60 + "\n")
    btind_main = [
        [data.ismain for data in t._btklinedataset.values()] for t in strategys]
    btind_info = [t.get_plot_datas()[3]
                  for t in strategys]
    dir = strategys[0].get_base_dir()  # 路径
    indicator_datas: list[list[list]] = [t.get_plot_datas()[2]
                                         for t in strategys]  # 指标数据indicator
    datas_num: list[int] = [
        t._btklinedataset.num for t in strategys]  # 合约个数
    symbols: list[list[str]] = [
        [data.symbol for data in t._btklinedataset.values()] for t in strategys]  # 合约名称
    symbol_multi_cycle: list[list[int]] = [
        [data.cycle for data in t._btklinedataset.values()] for t in strategys]  # 周期
    start_value: list[float] = [t.config.value for t in strategys]  # 开始回测价值
    profit_plot: list[bool] = [
        t._profit_plot or t.config.profit_plot for t in strategys]
    click_policy: list[str] = [t.config.click_policy for t in strategys]
    # K线颜色
    # COLORS = [BEAR_COLOR, BULL_COLOR]
    COLORS = [bcn.tomato, bcn.lime]
    inc_cmap = factor_cmap('inc', COLORS, ['0', '1'])
    new_colors = {'bear': bcn.tomato, 'bull': bcn.lime}
    BAR_WIDTH = .8  # K宽度
    NBSP = '\N{NBSP}' * 4
    # 'solid', 'dashed', 'dotted', 'dotdash', 'dashdot'

    lines_setting = dict(line_dash='solid', line_width=1.3)

    factors_dfs = [[] for _ in strategys]
    factors_names = [[] for _ in strategys]
    with open(f'{dir}/strategy/autoscale_cb.js', encoding='utf-8') as _f:
        _AUTOSCALE_JS_CALLBACK = _f.read()

    value_source: list[list] = [[] for _ in range(num)]  # 价值数据

    if trade_signal:
        long_source: list[list] = [[] for _ in range(num)]
        short_source: list[list] = [[] for _ in range(num)]
        long_flat_source: list[list] = [[] for _ in range(num)]
        short_flat_source: list[list] = [[] for _ in range(num)]
        long_segment_source: list[list] = [[] for _ in range(num)]
        short_segment_source: list[list] = [[] for _ in range(num)]
    source: list[list[ColumnDataSource]] = [[] for _ in range(num)]  # K线数据
    figs_ohlc: list[list[_figure]] = [[] for _ in range(num)]
    ts: list[Tabs] = []
    fig_ohlc_list = [{} for i in range(num)]  # K线数据
    signal_ind_data_source: list[list[list]] = [[] for i in range(num)]  # K线数据

    for i, rs in enumerate(results):
        for j, trades in enumerate(rs):
            _td = datas[i][j]
            symbol = symbols[i][j]
            if trade_signal:
                _long_source, _short_source, _long_flat_source, _short_flat_source, \
                    _long_segment_source, _short_segment_source = get_trades_source(
                        _td, trades)
                long_source[i].append(_long_source)
                short_source[i].append(_short_source)
                long_flat_source[i].append(_long_flat_source)
                short_flat_source[i].append(_short_flat_source)
                long_segment_source[i].append(_long_segment_source)
                short_segment_source[i].append(_short_segment_source)
            value_source[i].append(ColumnDataSource(dict(
                index=trades.index,
                datetime=_td.datetime.values,
                value=trades.total_profit.values,
                level=np.ones(_td.shape[0])*start_value[i],
            )))

    for ik, _datas in enumerate(datas):
        panel = []
        all_plots = []
        # 用于存储主图表的 x_range 和长度，实现 X 轴联动
        main_x_range = None
        main_length = None
        for id, df in enumerate(_datas):
            factors_dfs[ik].append(getattr(df, "factors_df", None))
            factors_names[ik].append(df.sname)
            df = df.pandas_object
            signal_ind_data_source[ik].append([])
            df.reset_index(drop=True, inplace=True)

            index = df.index
            current_length = len(index)
            pad = (index[-1] - index[0]) / 20
            df = df[_FILED]
            df['volume5'] = df.volume.rolling(5).mean()
            df['volume10'] = df.volume.rolling(10).mean()
            df["inc"] = (df.close >=
                         df.open).values.astype(np.uint8).astype(str)
            df["Low"] = df[['low', 'high']].min(1)
            df["High"] = df[['low', 'high']].max(1)
            source[ik].append(ColumnDataSource(df))

            # K线图
            if btind_main[ik][id] and id != 0:
                # ismain=True 的图表，只有当长度一致时才共享主图表的 x_range 实现 X 轴联动
                if main_x_range is not None and main_length == current_length:
                    x_range = main_x_range
                else:
                    x_range = Range1d(index[0], index[-1],
                                      min_interval=10,
                                      bounds=(index[0] - pad,
                                              index[-1] + pad)) if index.size > 1 else None
                fig_ohlc: _figure = new_bokeh_figure_main(plot_width, btind_info[ik][id].get('height', 150))(
                    x_range=x_range)
                fig_ohlc._main_ohlc = True
            else:
                # 主图表（id=0），创建并保存 x_range 和长度
                x_range = Range1d(index[0], index[-1],
                                  min_interval=10,
                                  bounds=(index[0] - pad,
                                          index[-1] + pad)) if index.size > 1 else None
                if id == 0:
                    main_x_range = x_range
                    main_length = current_length
                fig_ohlc: _figure = new_bokeh_figure(plot_width, btind_info[ik][id].get('height', 300))(
                    x_range=x_range)
            fig_ohlc.css_classes = ["candle-chart"]
            # 显式设置Y轴，确保Y轴范围独立，避免Y轴联动
            # 获取当前K线数据的价格范围
            if index.size > 0:
                price_min = df['low'].min()
                price_max = df['high'].max()
                y_pad = (price_max - price_min) * 0.05  # 添加5%的边距
                fig_ohlc.y_range.start = price_min - y_pad
                fig_ohlc.y_range.end = price_max + y_pad
            _colors = btind_info[ik][id].get('candlestyle', new_colors)
            if _colors and id == 0:
                _COLORS = list(_colors.values())
                inc_cmap = factor_cmap('inc', _COLORS, ['0', '1'])
            # 上下影线
            fig_ohlc.segment('index', 'high', 'index', 'low',
                             source=source[ik][id], color=black_color)
            # # 实体线
            ohlc_bars = fig_ohlc.vbar('index', BAR_WIDTH, 'open', 'close', source=source[ik][id],
                                      line_color=black_color, fill_color=inc_cmap)

            # [新增] 成交量**固定叠加到主 K 线图**底部(与 btplot.py 同款);
            #   副 Y 轴量程 = 最大量/VOL_FRAC -> 最高柱恰好占底部 VOL_FRAC, 不受价格缩放影响。
            # ⚠ 必须给主 Y 轴限定拟合范围, 否则成交量量级会把价格轴撑坏。
            # [开关] 由 Config.volume_mode 决定（'overlay' / 'both' 时开启）
            #   原代码: SHOW_VOL_OVERLAY = False   # [改回] 主图成交量叠加已停用
            SHOW_VOL_OVERLAY = volume_mode in ('overlay', 'both')
            if SHOW_VOL_OVERLAY and 'volume' in source[ik][id].column_names:
                _vol = np.nan_to_num(np.asarray(source[ik][id].data['volume'], dtype=np.float64))
                if _vol.size and _vol.max() > 0:
                    # ★ 成交量用**自己的 CDS**:
                    #   JS 刷新它时不会触碰主数据源 -> 价格 y 轴不会重新拟合 ->
                    #   既没有反馈死循环(成交量不停下移), 也**不需要干预 y_range.renderers**
                    #   (之前限制了拟合 -> 价格轴范围失真)。
                    from bokeh.models import (ColumnDataSource as _VPCDS,
                                      CustomJS as _VPCJS)
                    _F = 0.20
                    _vmax = float(_vol.max())
                    # ★ 初始基线 = **视口下沿**（优先取当前价格 y_range，它已含 padding），
                    #   取不到就退化为整段价格的 [min,max] 再补 5% padding。
                    #   关键: 柱体因此**始终落在可视价格范围内** -> DataRange1d 自动拟合
                    #   出来的范围等于 K 线自身范围, 成交量**不会把价格轴撑宽**
                    #   （与 VP 同理: 值域 ⊆ 价格值域）。
                    try:
                        _y0 = float(fig_ohlc.y_range.start)
                        _y1 = float(fig_ohlc.y_range.end)
                    except Exception:
                        _y0 = _y1 = float('nan')
                    if not (_y1 > _y0):
                        _ylo = float(np.nanmin(df['low'].values))
                        _yhi = float(np.nanmax(df['high'].values))
                        _pad = (_yhi - _ylo) * 0.05
                        _y0, _y1 = _ylo - _pad, _yhi + _pad
                    _span = (_y1 - _y0) or 1.0
                    _vol_cds = _VPCDS(dict(
                        index=np.arange(len(_vol), dtype=np.float64),
                        inc=list(source[ik][id].data.get('inc', ['1'] * len(_vol))),
                        vol_ov_bottom=np.full(len(_vol), _y0),      # 视口下沿
                        vol_ov_top=_y0 + _vol / _vmax * _span * _F,  # 之后由 JS 按视口刷新
                        vol_ov_ratio=_vol / _vmax))
                    _vol_r = fig_ohlc.vbar('index', BAR_WIDTH, 'vol_ov_bottom', 'vol_ov_top',
                                  source=_vol_cds,
                                  fill_color=factor_cmap('inc', COLORS, ['0', '1']),
                                  line_alpha=0, alpha=0.35)
                    try:
                        _vol_r.tags = ['__vp_excl__']
                        # ★ 立刻限定价格 y 轴的拟合对象: 此刻 renderers 里只有 K 线,
                        #   把成交量 overlay 排除(它的 y 基线是整段数据最低点, 会钉死 Y 轴)。
                        try:
                            _keep_r = [r for r in fig_ohlc.renderers if r is not _vol_r]
                            if _keep_r:
                                fig_ohlc.y_range.renderers = _keep_r
                        except Exception as _e:
                            import sys as _s
                            print('[y_range.renderers] 失败:', repr(_e), file=_s.stderr)
                    except Exception:
                        ...
                    # bottom_edge: 可见 Y 范围一变就重算基线 -> 始终贴在下沿
                    # [说明] 此处原本是 `from bokeh.models import CustomJS`。
                    #   函数内出现裸 `CustomJS`/`ColumnDataSource` 导入会把它**绑成局部名**,
                    #   使同函数内**早于它**使用的同名调用(框架自身的 CustomJS)抛
                    #   UnboundLocalError。两者模块顶部已导入(btplot.py 第 17/18 行),
                    #   故此处不再重复导入; 需要别名时用 `Xxx as _Alias` 形式。
                    _vol_js = _VPCJS(args=dict(
                        src=_vol_cds, F=_F, xr=fig_ohlc.x_range,
                        yr=fig_ohlc.y_range,          # ★ 视口下沿 = y_range.start
                        hiA=np.asarray(df['high'].values, dtype=np.float64),
                        loA=np.asarray(df['low'].values, dtype=np.float64)),
                        code="""
// bottom_edge: 成交量柱贴**视口最下端**(TradingView Volume overlay 效果)。
//   基线 base = 价格 y_range.start（= 当前可见范围最底部, 已含 padding）-> 视觉紧贴底边;
//   高度 = 归一化量 × 可见跨度 span × F。
//   ★ 柱子始终落在**可视价格范围内** -> DataRange1d 自动拟合出的范围等于 K 线自身范围,
//     成交量**不会影响 K 线图的可见范围**(与 VP 同理: 值域 ⊆ 价格值域)。
//   y_range 还没就绪时退化为"可见 x 窗口内 K 线的 low/high"。
const r = src.data['vol_ov_ratio'];
if (!r) return;
const a = Math.max(0, Math.round(xr.start));
const b = Math.min(r.length - 1, Math.round(xr.end));
let base = null, span = null;
if (yr != null && yr.start != null && yr.end != null && yr.end > yr.start) {
    base = yr.start;
    span = yr.end - yr.start;
} else if (a <= b) {
    let lo = Infinity, hi = -Infinity;
    for (let i = a; i <= b; i++) {
        if (loA[i] < lo) lo = loA[i];
        if (hiA[i] > hi) hi = hiA[i];
    }
    if (isFinite(lo) && isFinite(hi)) {
        base = lo;
        span = (hi - lo) || 1;
    }
}
if (base == null) return;
const bot = [], top = [];
for (let i = 0; i < r.length; i++) {
    bot.push(base);
    top.push(base + r[i] * span * F);
}
src.data['vol_ov_bottom'] = bot;
src.data['vol_ov_top'] = top;
src.change.emit();
""")
                    fig_ohlc.x_range.js_on_change('start', _vol_js)
                    fig_ohlc.x_range.js_on_change('end', _vol_js)
                    # [改] 归一化量已经在**独立 CDS** `_vol_cds` 里, 这里**不再**往主数据源
                    #   加列 —— 否则 JS 每次刷新都会改动主数据源, 触发价格轴重新拟合(反馈死循环)。
                    #   原代码: source[ik][id].add(_vol / _vmax, "vol_ov_ratio")
                    try:
                        # ★ 拖动/缩放时重算基线: 成交量**始终贴在可见 Y 范围底部**。
                        #   cb_obj 就是价格 y_range; src 必须指向**独立 CDS**。
                        _vol_js = _VPCJS(args=dict(src=_vol_cds, F=_F), code="""
const r = src.data['vol_ov_ratio'];
const lo = cb_obj.start, hi = cb_obj.end;
if (lo == null || hi == null || !r) return;
const sp = (hi - lo) || 1;
const bot = [], top = [];
for (let i = 0; i < r.length; i++) { bot.push(lo); top.push(lo + r[i] * sp * F); }
src.data['vol_ov_bottom'] = bot;
src.data['vol_ov_top'] = top;
src.change.emit();
""")
                        fig_ohlc.y_range.js_on_change('start', _vol_js)
                        fig_ohlc.y_range.js_on_change('end', _vol_js)
                    except Exception:
                        ...
            # 提示格式
            ohlc_tooltips = [
                ('x, y', NBSP.join(('$index',
                                    '$y{0,0.0[0000]}'))),
                ('OHLC', NBSP.join(('@open{0,0.0[0000]}',
                                    '@high{0,0.0[0000]}',
                                    '@low{0,0.0[0000]}',
                                    '@close{0,0.0[0000]}'))),
                ('Volume', '@volume{0,0}')]

            spanstyle = btind_info[ik][id].get('spanstyle', [])
            for ohlc_span in spanstyle:
                fig_ohlc.add_layout(Span(**ohlc_span))

            # 指标数据
            indicators_data = indicator_datas[ik][id]
            indicator_candles_index = []
            indicator_figs = []
            indicator_h: list[str] = []
            indicator_l: list[str] = []

            if indicators_data:
                ohlc_colors = colorgen()
                ic = 0
                for ind_index, (isplot, name, lines, _lines, ind_name, is_overlay, category, indicator, doubles, plotinfo, span, _signal, bandstyle) in enumerate(indicators_data):
                    lineinfo: dict = plotinfo.get('linestyle', {})
                    datainfo = plotinfo.get('source', "")
                    signal_info: dict = plotinfo.get('signalstyle', {})

                    if doubles:
                        _doubles_fig = []
                        for ids in range(2):
                            if any(isplot[ids]):
                                is_candles = category[ids] == 'candles'
                                tooltips = []
                                colors = cycle(
                                    ohlc_colors if is_overlay[ids] else colorgen())
                                legend_label = name[ids]  # 初始化命名的名称
                                if is_overlay[ids] and not is_candles:  # 主图叠加
                                    fig = fig_ohlc
                                else:
                                    fig = new_indicator_figure(
                                        new_bokeh_figure, fig_ohlc, plot_width, plotinfo.get('height', 150))
                                    indicator_figs.append(fig)
                                    _mulit_ind = len(
                                        indicator[ids].shape) > 1
                                    source[ik][id].add(
                                        _nan_reduce_axis1(indicator[ids][:, np.arange(len(isplot[ids]))[isplot[ids]]], 'max') if _mulit_ind else indicator[ids], f"{legend_label}_h")
                                    source[ik][id].add(
                                        _nan_reduce_axis1(indicator[ids][:, np.arange(len(isplot[ids]))[isplot[ids]]], 'min') if _mulit_ind else indicator[ids], f"{legend_label}_l")
                                    indicator_h.append(f"{legend_label}_h")
                                    indicator_l.append(f"{legend_label}_l")
                                    ic += 1
                                _doubles_fig.append(fig)

                                if not is_candles:
                                    if_vbar = False
                                    for j in range(len(isplot[ids])):
                                        if isplot[ids][j]:
                                            _lines_name = _lines[ids][j]
                                            ind = indicator[ids][:, j]
                                            color = next(colors)
                                            source_name = lines[ids][j]
                                            if ind.dtype == bool:
                                                ind = ind.astype(
                                                    np.float64)
                                            source[ik][id].add(ind,
                                                               source_name)
                                            tooltips.append(
                                                f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                            # tooltips.append(f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                            _lineinfo = deepcopy(
                                                lines_setting)
                                            if _lines_name in lineinfo:
                                                _lineinfo = {
                                                    **_lineinfo, **lineinfo[_lines_name]}
                                            # if 'line_color' not in _lineinfo:
                                            if _lineinfo.get("line_color", None) is None:
                                                _lineinfo.update(
                                                    dict(line_color=color))
                                            if "price_line" in _lineinfo:
                                                del _lineinfo["price_line"]
                                            if "price_label" in _lineinfo:
                                                del _lineinfo["price_label"]

                                                # [新增] vbar_base 是本框架为柱体线新增的字段(不是 bokeh Line/VBar 的属性),
                                                #   必须像 price_line/price_label 一样在传给 bokeh 前剔除, 否则
                                                #   fig.line(**lineinfo) 会因未知属性报 AttributeError。柱体分支
                                                #   改为直接从 LineStyle 对象读取该值。
                                                _lineinfo.pop("vbar_base", None)
                                            if is_overlay[ids]:
                                                fig.line(
                                                    'index', source_name, source=source[ik][id],
                                                    legend_label=source_name, **_lineinfo)
                                            else:
                                                if lineinfo and _lines_name in lineinfo and lineinfo[_lines_name].get('line_dash', None) == 'vbar':
                                                    if_vbar = True
                                                    # [修改] 同 btplot.py: 柱底由硬编码 0 改为逐线
                                                    #   vbar_base(默认 None -> 0.0, 保持旧行为),
                                                    #   上下行配色改按"数值 vs 基线"判定。
                                                    # 此处 _lineinfo 已被清洗掉 vbar_base,
                                                    # 故直接从该线的 LineStyle 对象读取。
                                                    _vbase = lineinfo[_lines_name].get('vbar_base', None)
                                                    _vbase = 0.0 if _vbase is None else float(_vbase)
                                                    _base_col = f"{_lines_name}_base"
                                                    if _base_col not in source[ik][id].column_names:
                                                        source[ik][id].add(
                                                            [_vbase, ] * len(ind), _base_col)
                                                    _line_inc = np.where(ind > _vbase, 1, 0).astype(
                                                        np.uint8).astype(str).tolist()
                                                    source[ik][id].add(
                                                        _line_inc, f"{_lines_name}_inc")
                                                    # if "line_color" in lineinfo[_lines_name]:
                                                    _line_inc_cmap = lineinfo[_lines_name]["line_color"]
                                                    if _line_inc_cmap is None:
                                                        _line_inc_cmap = factor_cmap(
                                                            f"{_lines_name}_inc", COLORS, ['0', '1'])
                                                    r = fig.vbar('index', BAR_WIDTH, _base_col, source_name, source=source[ik][id],
                                                                 line_color='black', fill_color=_line_inc_cmap)
                                                else:
                                                    r = fig.line(
                                                        'index', source_name, source=source[ik][id],
                                                        legend_label=source_name, **_lineinfo)
                                        # 两条线之间填充背景色
                                        band_lines = _lines[ids]  # 原始列名(无前缀)
                                        band_source_lines = lines[ids]  # 数据源列名(带前缀)
                                        if len(band_lines) >= 2:
                                            for band_dict in bandstyle:
                                                _bd = dict(band_dict)
                                                lower_name = _bd.get('lower', '')
                                                upper_name = _bd.get('upper', '')
                                                if lower_name in band_lines and upper_name in band_lines and all([isplot[ids][band_lines.index(lower_name)], isplot[ids][band_lines.index(upper_name)]]):
                                                    # 将原始列名替换为数据源中带前缀的列名
                                                    _bd['lower'] = band_source_lines[band_lines.index(lower_name)]
                                                    _bd['upper'] = band_source_lines[band_lines.index(upper_name)]
                                                    band_ = Band(
                                                        base='index',
                                                        source=source[ik][id],
                                                        **_bd,
                                                    )
                                                    fig.add_layout(band_)

                                    else:
                                        if if_vbar:
                                            renderers = fig.renderers.copy()
                                            fig.renderers = list(
                                                sorted(renderers, key=lambda x: not isinstance(x.glyph, VBar)))

                                        if span:
                                            for ind_span in span:
                                                if np.isnan(ind_span["location"]) and not all(is_overlay):
                                                    ind = _span_values(indicator, isplot)
                                                    _valid_ind = ind[~np.isnan(
                                                        ind)]
                                                    mean = _valid_ind.mean() if len(_valid_ind) > 0 else np.nan
                                                    if not np.isnan(mean) and (abs(mean) < .1 or
                                                                               round(abs(mean), 1) == .5 or
                                                                               round(abs(mean), -1) in (50, 100, 200)):
                                                        fig.add_layout(Span(location=float(mean), dimension='width',
                                                                            line_color='#666666', line_dash='dashed',
                                                                            line_width=.8))
                                                else:
                                                    fig.add_layout(
                                                        Span(**ind_span))
                                        else:
                                            ind = _span_values(indicator, isplot)
                                            _valid_ind = ind[~np.isnan(
                                                ind)]
                                            mean = _valid_ind.mean() if len(_valid_ind) > 0 else np.nan
                                            if not np.isnan(mean) and (abs(mean) < .1 or
                                                                       round(abs(mean), 1) == .5 or
                                                                       round(abs(mean), -1) in (50, 100, 200)):
                                                fig.add_layout(Span(location=float(mean), dimension='width',
                                                                    line_color='#666666', line_dash='dashed',
                                                                    line_width=.8))

                                    if is_overlay[ids]:
                                        ohlc_tooltips.append(
                                            (legend_label, NBSP.join(tuple(tooltips))))
                                    else:
                                        set_tooltips(
                                            fig, [(legend_label, NBSP.join(tooltips))], vline=True, renderers=[r])
                                        fig.yaxis.axis_label = legend_label
                                        fig.yaxis.axis_label_text_color = black_color
                                        if fig_ohlc._main_ohlc:
                                            fig.yaxis.visible = False
                                        else:
                                            fig.yaxis.visible = True
                                        if len(lines) == 1:
                                            fig.legend.glyph_width = 0
                            
                    else:
                        # [修正] Volume Profile(category='vp')的列全是 isplot=False,
                        #   若仍用 `if any(isplot):` 则 VP 专门分支不会执行 -> VP 画不出来。
                        if any(isplot) or category == 'vp':
                            # if any(isplot):
                            is_candles = category == 'candles'
                            if is_candles and len(lines) < 4:
                                is_candles = False
                            # [新增] Volume Profile 指标(category == 'vp'):
                            #   next() 返回 (K线根数, 档数) 矩阵, 画成"横向成交量分布"
                            is_vp = (category == 'vp')
                            tooltips = []
                            colors = cycle(
                                ohlc_colors if is_overlay else colorgen())
                            legend_label = name  # 初始化命名的名称
                            if is_vp:                       # Volume Profile
                                # overlap=True -> 画在价格主图(y=价格档);
                                # overlap=False -> 另开副图(y=档位序号, 分层直方图)
                                if is_overlay:
                                    if datainfo in fig_ohlc_list[ik]:
                                        fig = fig_ohlc_list[ik].get(datainfo)
                                    else:
                                        fig = fig_ohlc
                                    _vp_y, _vp_isnew = 'price', False
                                else:
                                    fig = new_indicator_figure(
                                        new_bokeh_figure, fig_ohlc, plot_width,
                                        plotinfo.get('height', 150))
                                    _vp_y, _vp_isnew = 'index', True
                                # [新增] 按 lines 的 **'vp' 前缀**切分:
                                #   前缀之前的列 = 普通指标线(可选, 先按折线画);
                                #   前缀及之后的列 = Volume Profile 数据块。
                                try:
                                    _nm = [str(x) for x in (_lines if _lines is not None else [])]
                                    _cut = next((_i for _i, _x in enumerate(_nm)
                                                 if _x.lower().startswith('vp')), None)
                                except Exception:
                                    _nm, _cut = [], None
                                _ind2 = indicator if np.ndim(indicator) > 1 else indicator.reshape(-1, 1)
                                if _nm and _cut is not None:
                                    _lidx, _vidx = list(range(_cut)), list(range(_cut, len(_nm)))
                                else:
                                    _lidx, _vidx = [], list(range(_ind2.shape[1]))
                                for _i, _li in enumerate(_lidx):
                                    _cn = f"vpl_{ic}_{_i}"
                                    # [BUG 修复] 这里原来写的是 `CDS` —— 本函数（plot）里
                                    #   数据源叫 `source[ik][id]`，根本没有 `CDS` 这个名字；
                                    #   因为 RollingVolumeProfile 没有“普通指标线”列 -> _lidx 为空，
                                    #   这行永不执行所以一直没暴露；换成 VolumeProfileMA（有 'ma' 列）
                                    #   后 _lidx=[0] -> 直接抛 NameError: name 'CDS' is not defined。
                                    #   同时把 `a if c else b` 嵌套写法改成直白的 if。
                                    _src_vp = source[ik][id]
                                    if _cn not in _src_vp.column_names:
                                        _src_vp.add(_ind2[:, _li], _cn)
                                    _lp = plotinfo.get('linestyle', {}).get(_nm[_li], None) if isinstance(plotinfo.get('linestyle'), dict) else None
                                    _lkw = dict(line_width=1.3)
                                    if _lp is not None:
                                        _lkw['line_color'] = getattr(_lp, 'line_color', None)
                                        _lkw['line_width'] = getattr(_lp, 'line_width', 1.3) or 1.3
                                    _lkw = {k: v for k, v in _lkw.items() if v is not None}
                                    fig.line('index', _cn, source=_src_vp, **_lkw)
                                # [按用户要求暂时关闭] VP 图的 tooltips —— 需要时取消下面两行注释即可:

                                #(vp* 的几十档当 tooltip 没有意义)
                                if _lidx:
                                    try:
                                        _tt = [(str(_nm[_li]),
                                                "@vpl_" + str(ic) + "_" + str(_i) + "{0,0.0[0000]}")
                                               for _i, _li in enumerate(_lidx)]
                                        set_tooltips(fig, _tt, vline=True)
                                    except Exception:
                                        ...
                                _c0, _c1 = None, None
                                # ★ [BUG 修复] 同 btplot.py: linestyle['vp0'] 可能是
                                #   颜色字符串而不是 LineStyle -> 原 getattr 拿不到颜色,
                                #   导致 vp_color / vp_poc_color 失效(永远是默认蓝/橙)。
                                def _pick_vp_color(_v):
                                    if _v is None:
                                        return None
                                    if isinstance(_v, str):
                                        return _v
                                    if isinstance(_v, dict):
                                        return _v.get('line_color')
                                    return getattr(_v, 'line_color', None)
                                try:
                                    _lin = plotinfo.get('linestyle') or {}
                                    _c0 = _pick_vp_color(_lin.get(_nm[_vidx[0]]))
                                    _c1 = _pick_vp_color(_lin.get('vp_poc'))
                                    _lpb = _lin.get('vp_price_bars')
                                    _pbv = None if hasattr(_lpb, 'line_color') else _lpb
                                except Exception:
                                    _c0, _c1, _pbv = None, None, None
                                try:
                                    # ★ [BUG 修复] 接住返回的渲染器赋给 r:
                                    #   纯 VP 指标没有折线列 -> 后面 renderers=[r]
                                    #   会 UnboundLocalError(参见 btplot.py 同处说明)。
                                    r = _add_volume_profile(
                                        fig, source[ik][id], _ind2[:, _vidx], df, ic,
                                        black_color=black_color, y_mode=_vp_y,
                                        bar_color=_c0, poc_color=_c1, vidx=_vidx,
                                        price_bars=_pbv,
                                        # 副图里 VP 用自己的 y range（见函数内说明）
                                        y_range_name=(None if is_overlay else
                                                      f'vp_y{len(fig.extra_y_ranges)}'),
                                        # 副图不要顶部那根“成交量刻度轴”（见函数内开关说明）
                                        show_vol_axis=bool(is_overlay),
                                        # 副图里只有 VP(无指标线)时才把纵轴刻度标成价格中心
                                        y_tick_labels=(len(_lidx) == 0))
                                    if _vp_isnew:
                                        indicator_figs.append(fig)
                                    ic += 1        # 占一个序号, 保证列名唯一
                                except Exception as _e:      # 画不出就跳过, 但不静默
                                    import sys as _sys
                                    print(f"[volume_profile] 绘制失败: {type(_e).__name__}: {_e}",
                                          file=_sys.stderr)
                            elif is_overlay and not is_candles:  # 主图叠加
                                if datainfo in fig_ohlc_list[ik]:  # 副图
                                    fig = fig_ohlc_list[ik].get(
                                        datainfo)
                                else:
                                    fig = fig_ohlc
                            elif is_candles:  # 副图是蜡烛图
                                # if any(isplot):
                                indicator_candles_index.append(ic)
                                assert len(lines) >= 4
                                lines = list(
                                    map(lambda x: x.lower(), lines))
                                filed_index = []
                                missing_index = []
                                for ii, file in enumerate(FILED):
                                    is_missing = True
                                    for n in lines:
                                        if file in n:
                                            filed_index.append(
                                                lines.index(n))
                                            is_missing = False
                                    else:
                                        if is_missing:
                                            missing_index.append(ii)
                                assert not missing_index, f"数据中缺失{[FILED[ii] for ii in missing_index]}字段"
                                for ie in filed_index:
                                    source[ik][id].add(indicator[:,
                                                                 ie], lines[ie])
                                # 副图蜡烛按“指标自身”的开/收涨跌着色(不跟随主K线的 inc)
                                _ohlc_inc_field = f"candle_inc_{ic}"
                                _ohlc_inc = (np.asarray(indicator[:, filed_index[3]],
                                                        dtype=np.float64)
                                             >= np.asarray(indicator[:, filed_index[0]],
                                                           dtype=np.float64)
                                             ).astype(np.uint8).astype(str).tolist()
                                source[ik][id].add(_ohlc_inc, _ohlc_inc_field)
                                # [修改] 蜡烛指标优先使用**自身**的 candlestyle(plotinfo.candlestyle);
                                #   未设置时才回退到 _colors(主 K 线配色) / COLORS —— 原代码直接用 _colors,
                                #   导致蜡烛型指标无法自定义涨/跌配色。
                                _cs_ind = plotinfo.get('candlestyle', None)
                                if _cs_ind:
                                    _ohlc_palette = list(_cs_ind.values())
                                elif _colors:
                                    _ohlc_palette = list(_colors.values())
                                else:
                                    _ohlc_palette = COLORS
                                _ohlc_cmap = factor_cmap(
                                    _ohlc_inc_field, _ohlc_palette, ['0', '1'])
                                index = np.arange(indicator.shape[0])
                                pad = (index[-1] - index[0]) / 20
                                # [修改] 支持“主图双蜡烛”: 蜡烛型指标 overlap=True 时,
                                #   把蜡烛画到**主图** fig_ohlc(而不是另开副图),
                                #   并用更窄柱宽(BAR_WIDTH/2)避免完全盖住主 K 线;
                                #   overlap=False 仍按原逻辑单独开副图。
                                if is_overlay:
                                    fig_ohlc_ = fig_ohlc
                                    _candle_w = BAR_WIDTH / 2
                                else:
                                    fig_ohlc_ = new_indicator_figure(
                                        new_bokeh_figure, fig_ohlc, plot_width, plotinfo.get('height', 100))
                                    _candle_w = BAR_WIDTH
                                fig_ohlc_.segment(
                                    'index', lines[filed_index[1]], 'index', lines[filed_index[2]], source=source[ik][id], color=black_color)
                                ohlc_bars_ = fig_ohlc_.vbar('index', _candle_w, lines[filed_index[0]], lines[filed_index[3]], source=source[ik][id],
                                                            line_color=black_color, fill_color=_ohlc_cmap)
                                ohlc_tooltips_ = [
                                    ('x, y', NBSP.join(('$index',
                                                        '$y{0,0.0[0000]}'))),
                                    ('OHLC', NBSP.join((f"@{lines[filed_index[0]]}{'{'}0,0.0[0000]{'}'}",
                                                        f"@{lines[filed_index[1]]}{'{'}0,0.0[0000]{'}'}",
                                                        f"@{lines[filed_index[2]]}{'{'}0,0.0[0000]{'}'}",
                                                        f"@{lines[filed_index[3]]}{'{'}0,0.0[0000]{'}'}")))]

                                # [修改] is_overlay 时 fig_ohlc_ 就是主图, 不能改它的 y 轴标题/可见性,
                                #   否则会把主 K 线的 y 轴盖掉; 仅副图蜡烛才按原逻辑设置。
                                if not is_overlay:
                                    fig_ohlc_.yaxis.axis_label = ind_name
                                    fig_ohlc_.yaxis.axis_label_text_color = black_color
                                    if fig_ohlc._main_ohlc:
                                        fig_ohlc_.yaxis.visible = False
                                    else:
                                        fig_ohlc_.yaxis.visible = True
                                fig_ohlc_list[ik].update(
                                    {ind_name: fig_ohlc_})

                                for j in range(len(lines)):
                                    if j not in filed_index:
                                        if isplot[j]:
                                            tooltips = []
                                            _lines_name = _lines[j]
                                            ind = indicator[:, j]
                                            color = next(colors)
                                            source_name = lines[j]
                                            if ind.dtype == bool:
                                                ind = ind.astype(int)
                                            source[ik][id].add(ind,
                                                               source_name)
                                            tooltips.append(
                                                f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                            _lineinfo = deepcopy(lines_setting)
                                            if _lines_name in lineinfo:
                                                _lineinfo = {
                                                    **_lineinfo, **lineinfo[_lines_name]}
                                            if _lineinfo.get("line_color", None) is None:
                                                _lineinfo.update(
                                                    dict(line_color=color))
                                            if "price_line" in _lineinfo:
                                                del _lineinfo["price_line"]
                                            if "price_label" in _lineinfo:
                                                del _lineinfo["price_label"]

                                                # [新增] vbar_base 是本框架为柱体线新增的字段(不是 bokeh Line/VBar 的属性),
                                                #   必须像 price_line/price_label 一样在传给 bokeh 前剔除, 否则
                                                #   fig.line(**lineinfo) 会因未知属性报 AttributeError。柱体分支
                                                #   改为直接从 LineStyle 对象读取该值。
                                                _lineinfo.pop("vbar_base", None)
                                            # if is_overlay:
                                            fig_ohlc_.line(
                                                'index', source_name, source=source[ik][id],
                                                legend_label=source_name, **_lineinfo)
                                            ohlc_tooltips_.append(
                                                (_lines_name, NBSP.join(tuple(tooltips))))
                                set_tooltips(fig_ohlc_, ohlc_tooltips_,
                                             vline=True, renderers=[ohlc_bars_])
                                # [修改] 主图叠加时不往 indicator_figs 里加(它就是主图 fig_ohlc)
                                if not is_overlay:
                                    indicator_figs.append(fig_ohlc_)
                                ic += 1
                                _mulit_ind = len(indicator.shape) > 1
                                source[ik][id].add(_nan_reduce_axis1(indicator[:, np.arange(len(isplot))[isplot]], 'max') if _mulit_ind else indicator,
                                                   f"{legend_label}_h")
                                source[ik][id].add(_nan_reduce_axis1(indicator[:, np.arange(len(isplot))[isplot]], 'min') if _mulit_ind else indicator,
                                                   f"{legend_label}_l")
                                indicator_h.append(f"{legend_label}_h")
                                indicator_l.append(f"{legend_label}_l")

                            else:
                                if datainfo in fig_ohlc_list[ik]:  # 副图
                                    __fig = fig_ohlc_list[ik].get(
                                        datainfo)
                                else:
                                    __fig = fig_ohlc
                                fig = new_indicator_figure(
                                    new_bokeh_figure, __fig, plot_width, plotinfo.get('height', 150))
                                indicator_figs.append(fig)
                                ic += 1
                                _mulit_ind = len(indicator.shape) > 1
                                source[ik][id].add(_nan_reduce_axis1(indicator[:, np.arange(len(isplot))[isplot]], 'max') if _mulit_ind else indicator,
                                                   f"{legend_label}_h")
                                source[ik][id].add(_nan_reduce_axis1(indicator[:, np.arange(len(isplot))[isplot]], 'min') if _mulit_ind else indicator,
                                                   f"{legend_label}_l")
                                indicator_h.append(f"{legend_label}_h")
                                indicator_l.append(f"{legend_label}_l")

                            if not is_candles:
                                if_vbar = False
                                for j in range(len(isplot)):
                                    if isplot[j]:
                                        _lines_name = _lines[j]
                                        ind = indicator[:, j]
                                        color = next(colors)
                                        source_name = lines[j]
                                        if ind.dtype == bool:
                                            ind = ind.astype(int)
                                        source[ik][id].add(ind,
                                                           source_name)
                                        tooltips.append(
                                            f"@{source_name}{'{'}0,0.0[0000]{'}'}")
                                        _lineinfo = deepcopy(lines_setting)
                                        if _lines_name in lineinfo:
                                            _lineinfo = {
                                                **_lineinfo, **lineinfo[_lines_name]}
                                        if _lineinfo.get("line_color", None) is None:
                                            _lineinfo.update(
                                                dict(line_color=color))
                                        if "price_line" in _lineinfo:
                                            del _lineinfo["price_line"]
                                        if "price_label" in _lineinfo:
                                            del _lineinfo["price_label"]

                                            # [新增] vbar_base 是本框架为柱体线新增的字段(不是 bokeh Line/VBar 的属性),
                                            #   必须像 price_line/price_label 一样在传给 bokeh 前剔除, 否则
                                            #   fig.line(**lineinfo) 会因未知属性报 AttributeError。柱体分支
                                            #   改为直接从 LineStyle 对象读取该值。
                                            _lineinfo.pop("vbar_base", None)
                                        if is_overlay:
                                            fig.line(
                                                'index', source_name, source=source[ik][id],
                                                legend_label=source_name, **_lineinfo)
                                        else:
                                            if lineinfo and _lines_name in lineinfo and lineinfo[_lines_name].get('line_dash', None) == 'vbar':
                                                if_vbar = True
                                                if "zeros" not in source[ik][id].column_names:
                                                    source[ik][id].add(
                                                        [0.,]*len(ind), "zeros")
                                                _line_inc = np.where(ind > 0., 1, 0).astype(
                                                    np.uint8).astype(str).tolist()
                                                source[ik][id].add(
                                                    _line_inc, f"{_lines_name}_inc")
                                                _line_inc_cmap = lineinfo[_lines_name]["line_color"]
                                                if _line_inc_cmap is None:
                                                    _line_inc_cmap = factor_cmap(
                                                        f"{_lines_name}_inc", COLORS, ['0', '1'])
                                                r = fig.vbar('index', BAR_WIDTH, 'zeros', source_name, source=source[ik][id],
                                                             line_color='black', fill_color=_line_inc_cmap)
                                            else:
                                                r = fig.line(
                                                    'index', source_name, source=source[ik][id],
                                                    legend_label=source_name, **_lineinfo)

                                else:

                                    if if_vbar:
                                        renderers = fig.renderers.copy()
                                        fig.renderers = list(
                                            sorted(renderers, key=lambda x: not isinstance(x.glyph, VBar)))
                                    if span:
                                        for ind_span in span:
                                            if np.isnan(ind_span["location"]) and not is_overlay if isinstance(is_overlay, bool) else not all(is_overlay):
                                                ind = _span_values(indicator, isplot)
                                                _valid_ind = ind[~np.isnan(
                                                    ind)]
                                                mean = _valid_ind.mean() if len(_valid_ind) > 0 else np.nan
                                                if not np.isnan(mean) and (abs(mean) < .1 or
                                                                           round(abs(mean), 1) == .5 or
                                                                           round(abs(mean), -1) in (50, 100, 200)):
                                                    fig.add_layout(Span(location=float(mean), dimension='width',
                                                                        line_color='#666666', line_dash='dashed',
                                                                        line_width=.8))
                                            else:
                                                fig.add_layout(
                                                    Span(**ind_span))
                                    else:
                                        ind = _span_values(indicator, isplot)
                                        non_nan_ind = ind[~np.isnan(ind)]
                                        mean = non_nan_ind.mean() if len(non_nan_ind) > 0 else np.nan
                                        if not np.isnan(mean) and (abs(mean) < .1 or
                                                                   round(abs(mean), 1) == .5 or
                                                                   round(abs(mean), -1) in (50, 100, 200)):
                                            fig.add_layout(Span(location=float(mean), dimension='width',
                                                                line_color='#666666', line_dash='dashed',
                                                                line_width=.8))

                                if is_overlay:
                                    ohlc_tooltips.append(
                                        (ind_name, NBSP.join(tuple(tooltips))))
                                else:
                                    set_tooltips(
                                        fig, [(legend_label, NBSP.join(tooltips))], vline=True, renderers=[r])
                                    fig.yaxis.axis_label = ind_name
                                    fig.yaxis.axis_label_text_color = black_color
                                    if len(lines) == 1:
                                        fig.legend.glyph_width = 0
                                    if fig_ohlc._main_ohlc:
                                        fig.yaxis.visible = False
                                    else:
                                        fig.yaxis.visible = True
                        # 两条线之间填充背景色
                        if len(_lines) >= 2:
                            for band_dict in bandstyle:
                                _bd = dict(band_dict)
                                lower_name = _bd.get('lower', '')
                                upper_name = _bd.get('upper', '')
                                if lower_name in _lines and upper_name in _lines and all([isplot[_lines.index(lower_name)], isplot[_lines.index(upper_name)]]):
                                    # 将原始列名替换为数据源中带前缀的列名
                                    _bd['lower'] = lines[_lines.index(lower_name)]
                                    _bd['upper'] = lines[_lines.index(upper_name)]
                                    band_ = Band(
                                        base='index',
                                        source=source[ik][id],
                                        **_bd,
                                    )
                                    fig.add_layout(band_)
                    if signal_info:
                        # 逐点信号标签文本: {信号key: 长度=bar数 的 object 数组, 有文本=str, 无=np.nan}
                        signal_texts_map: dict = plotinfo.get(
                            'signal_texts', {}) or {}
                        signal_style = resolve_signal_text_style(
                            signal_texts_map, black_style)
                        signal_ind_data_ = dict(
                            long_signal=None, exitlong_signal=None, short_signal=None, exitshort_signal=None)
                        for k, v in signal_info.items():
                            signalkey, signalcolor, signalmarker, signaloverlap, signalshow, signalsize, signallabel = list(
                                v.values())

                            if signalshow:
                                signaldata: np.ndarray
                                islabel = isinstance(signallabel, dict)
                                pertexts = None
                                label_text = None
                                if islabel:
                                    label_text = signallabel.pop("text", k)
                                if doubles:
                                    index1, index2 = search_index(
                                        _lines, k)
                                    signaldata = indicator[index1][:, index2]
                                else:
                                    signaldata = indicator[:, _lines.index(
                                        k)]
                                signal_index = np.argwhere(
                                    signaldata > 0)[:, 0]
                                if signaloverlap:
                                    price_data = df[signalkey].values
                                    signal_fig = fig_ohlc
                                else:
                                    signal_fig = fig
                                    try:
                                        if doubles:
                                            index1, index2 = search_index(
                                                _lines, signalkey)
                                            price_data = indicator[index1][:, index2]
                                        else:
                                            price_data = indicator[:, _lines.index(
                                                signalkey)]
                                    except:
                                        price_data = signaldata.copy()
                                signal_price = price_data[signaldata > 0]
                                signal_datetime = df.datetime.values[signaldata > 0]
                                # 逐点文本: 与数值信号线同索引对齐, 文本为 nan 的信号点跳过
                                pertexts = signal_texts_map.get(k)
                                if pertexts is not None and len(pertexts) != len(signaldata):
                                    # 长度与数值行不一致(数据截断/多周期/切图), 回退统一文本防错位
                                    pertexts = None
                                # [修改] 原代码在这里用 _valid 就地子集化 signal_index /
                                #   signal_price / signal_datetime:
                                #       elif not _valid.all():
                                #           pertexts = pertexts[_valid]
                                #           signal_index = signal_index[_valid]
                                #           signal_price = signal_price[_valid]
                                #           signal_datetime = signal_datetime[_valid]
                                #   但 marker(scatter) 与文本(LabelSet) 共用同一个
                                #   signal_source_ -> "没有文本的信号点连 marker 也一起
                                #   被剔除", 与"文本为 nan 的信号点跳过"(只跳文本)不符。
                                #   改为: marker 恒用全量信号点(signal_*),
                                #   文本另走 text_* 三件套。
                                text_index = signal_index
                                text_price = signal_price
                                text_datetime = signal_datetime
                                if pertexts is not None:
                                    pertexts = np.asarray(
                                        pertexts[signaldata > 0], dtype=object)
                                    _valid = ~pd.isna(pertexts)
                                    if not _valid.any():
                                        pertexts = None
                                    elif not _valid.all():
                                        pertexts = pertexts[_valid]
                                        text_index = signal_index[_valid]
                                        text_price = signal_price[_valid]
                                        text_datetime = signal_datetime[_valid]
                                # 文字标签: 逐点文本优先(无需先 set_label), 否则回退统一 label 配置
                                label_kw = dict(signallabel) if islabel else {}
                                xoff_col = False
                                # marker 的数据源: 始终是全量信号点
                                signal_source_ = ColumnDataSource(dict(
                                    index=signal_index,
                                    datetime=signal_datetime,
                                    price=signal_price,
                                    size=[float(signalsize), ] * len(signal_index),
                                ))
                                # 文本的数据源: 默认与 marker 共用(统一文本/无文本场景),
                                # 逐点文本场景下换成只含"有文本点"的子集(label_source_)。
                                label_source_ = signal_source_
                                if pertexts is not None:
                                    # 逐点文本: 支持 "\n" 多行; 水平偏移按各自文字宽度居中
                                    if not islabel:
                                        # 默认文字颜色随主题: 浅色→黑字, 深色→白字
                                        label_kw.update(dict(
                                            text_font_size="10pt",
                                            text_font_style="bold",
                                            text_color="white" if black_style else "black"))
                                    _fs = str(label_kw.get(
                                        "text_font_size", "10pt")).replace("pt", "")
                                    try:
                                        font_size = float(_fs)
                                    except (TypeError, ValueError):
                                        font_size = 10.
                                    # 方向判定: 以价格锚点列高/低决定文字落在信号点哪一侧
                                    # (锚点在低点→文字在下方, 锚点在高点→文字在上方),
                                    # 避免文字覆盖信号点与 K 线。锚点列无法判断时回退信号名。
                                    is_buy = signal_text_below(signalkey, k)
                                    if not islabel:
                                        label_kw.setdefault(
                                            "y_offset", -2.5 * font_size if is_buy else 1.4 * font_size)
                                    label_kw.pop("x_offset", None)
                                    xoff_col = True
                                    # 按 "\n" 拆行; 各点行数可不同, 缺行以 None 标记(渲染时剔除)
                                    split_rows = [str(t).split("\n") for t in pertexts]
                                    max_lines = max((len(r) for r in split_rows), default=1)
                                    pertext_lines = [
                                        [r[li] if li < len(r) else None for r in split_rows]
                                        for li in range(max_lines)]
                                    # [修改] 原代码:
                                    #     signal_source_ = ColumnDataSource(dict(
                                    #         index=signal_index,
                                    #         datetime=signal_datetime,
                                    #         price=signal_price,
                                    #         size=[float(signalsize), ] *
                                    #         len(signal_index),
                                    #         text=[str(t) for t in pertexts],
                                    #         x_offset=[...],
                                    #     ))
                                    #   它把文本与 marker 塞进同一个 CDS。现在 text/x_offset
                                    #   列长度 = 有文本的点数, 与全量 marker 点数不一致
                                    #   (bokeh 不校验列长), 必须拆成独立的 label_source_。
                                    label_source_ = ColumnDataSource(dict(
                                        index=text_index,
                                        datetime=text_datetime,
                                        price=text_price,
                                        size=[float(signalsize), ] *
                                        len(text_index),
                                        text=[str(t) for t in pertexts],
                                        x_offset=[-0.5 * text_width_pt(str(t), font_size, is_buy)
                                                  for t in pertexts],
                                    ))
                                elif islabel:
                                    pertext_lines = None
                                    # [修改] 原为 signal_source_ = ; 拆开以免 scatter
                                    #   被塞入仅文本需要的 text 列。
                                    label_source_ = ColumnDataSource(dict(
                                        index=signal_index,
                                        datetime=signal_datetime,
                                        price=signal_price,
                                        size=[float(signalsize),] *
                                        len(signal_index),
                                        text=[label_text] *
                                        len(signal_index),  # 标签文字列表
                                    ))
                                else:
                                    pertext_lines = None
                                    signal_source_ = ColumnDataSource(dict(
                                        index=signal_index,
                                        datetime=signal_datetime,
                                        price=signal_price,
                                        size=[float(signalsize),] *
                                        len(signal_index),
                                    ))
                                signal_ind_data_.update(
                                    {k: signal_source_})
                                signal_ind_data_source[ik][id].append(
                                    signal_ind_data_)

                                # [修改] 原代码: marker=signalmarker
                                #   signalmarker 可能是 Markers 枚举里的 lightweight_charts 专用名
                                #   (arrow_up/arrow_down), 或 TradingView 风格的 label_up/label_down;
                                #   bokeh 不认这些名字 -> E-1001 BAD_COLUMN_NAME 且标记被静默丢弃。
                                #   统一经 to_bokeh_marker 收敛(见 minibt/constant.py)。
                                r = signal_fig.scatter(x='index', y='price', source=signal_ind_data_source[ik][id][-1].get(k), fill_color=signalcolor,
                                                       marker=to_bokeh_marker(signalmarker), line_color='black', size="size")
                                if pertext_lines is not None and len(pertext_lines) > 1:
                                    # --- 多行文本: 每行一个 LabelSet, 逐行错开一个行距 ---
                                    # 低点锚点向下展开, 高点锚点向上展开(均背离 K 线)
                                    if islabel:
                                        # 已配置统一 label 样式: 保留其主题背景衬托
                                        label_kw.update(
                                            dict(background_fill_alpha=0.5,
                                                 background_fill_color="white" if black_style else "black"))
                                    else:
                                        if signal_style:
                                            label_kw.update(signal_style)
                                        else:
                                            # 逐点默认文本: 灰底+边框衬块(与面板拉开层次)
                                            if black_style:
                                                label_kw.update(dict(
                                                    text_color="white",
                                                    background_fill_color="#333333",
                                                    background_fill_alpha=0.7,
                                                    border_line_color="#888888",
                                                    border_line_alpha=0.8))
                                            else:
                                                label_kw.update(dict(
                                                    text_color="black",
                                                    background_fill_color="#EAEAEA",
                                                    background_fill_alpha=0.8,
                                                    border_line_color="#999999",
                                                    border_line_alpha=0.8))
                                    y0 = float(label_kw.get("y_offset", 0.))
                                    _fs2 = str(label_kw.get(
                                        "text_font_size", "10pt")).replace("pt", "")
                                    try:
                                        font_size2 = float(_fs2)
                                    except (TypeError, ValueError):
                                        font_size2 = 10.
                                    line_gap = font_size2 * 1.3
                                    _base_rows = list(zip(text_index, text_price,
                                                          text_datetime))
                                    # 行展开方向: 低点锚点文本在信号点下方, 多行继续向下(负向)
                                    # 展开; 高点锚点文本在信号点上方, 多行继续向上(正向)展开,
                                    # 均背离 K 线, 避免堆叠遮挡信号点与 K 线
                                    _row_dir = -1 if is_buy else 1
                                    for li, line_txts in enumerate(pertext_lines):
                                        keep = [(r[0], r[1], r[2], tx)
                                                for r, tx in zip(_base_rows, line_txts)
                                                if tx]
                                        if not keep:
                                            continue
                                        _lkw = dict(label_kw)
                                        _lkw['y_offset'] = y0 + _row_dir * li * line_gap
                                        _lkw['x_offset'] = 'x_offset'
                                        labels = LabelSet(
                                            x='index',
                                            y='price',
                                            text='text',
                                            source=ColumnDataSource(dict(
                                                index=[r[0] for r in keep],
                                                datetime=[r[2] for r in keep],
                                                price=[r[1] for r in keep],
                                                text=[r[3] for r in keep],
                                                x_offset=[-0.5 * text_width_pt(
                                                    r[3], font_size2, is_buy) for r in keep],
                                            )),
                                            **_lkw,
                                        )
                                        signal_fig.add_layout(labels)
                                elif pertexts is not None or islabel:
                                    # --- 单行文本: 用单个 LabelSet 添加文字标签 ---
                                    if islabel:
                                        # 已配置统一 label 样式: 保留其主题背景衬托
                                        label_kw.update(
                                            dict(background_fill_alpha=0.5,
                                                 background_fill_color="white" if black_style else "black"))
                                    else:
                                        # 逐点文本: signal_style(含按主题解析的预设/用户自定义)优先
                                        if signal_style:
                                            label_kw.update(signal_style)
                                        else:
                                            # 逐点默认文本: 灰底+边框衬块(与面板拉开层次)
                                            if black_style:
                                                label_kw.update(dict(
                                                    text_color="white",
                                                    background_fill_color="#333333",
                                                    background_fill_alpha=0.7,
                                                    border_line_color="#888888",
                                                    border_line_alpha=0.8))
                                            else:
                                                label_kw.update(dict(
                                                    text_color="black",
                                                    background_fill_color="#EAEAEA",
                                                    background_fill_alpha=0.8,
                                                    border_line_color="#999999",
                                                    border_line_alpha=0.8))
                                    if xoff_col:
                                        # 逐点模式: 水平偏移用数据列(每点自适应宽度居中)
                                        label_kw['x_offset'] = 'x_offset'
                                    labels = LabelSet(
                                        x='index',        # 标签 x 坐标（与散点 x 一致）
                                        y='price',        # 标签 y 坐标（与散点 y 一致）
                                        text='text',      # 标签文字来源（数据源的 text 字段）
                                        source=label_source_,  # 文本数据源(逐点文本时为子集)
                                        **label_kw,
                                    )
                                    signal_fig.add_layout(labels)  # 将标签添加到图形中
                                tooltips = [(k, "@price{0.00}"),]
                                set_tooltips(signal_fig, tooltips,
                                             vline=False, renderers=[r,])

            # 如果当前合约有交易但没有信号标记，从合约0复制信号标记
            if id > 0 and trade_signal and not signal_ind_data_source[ik][id]:
                ref_indicators = indicator_datas[ik][0]
                for ref_isplot, ref_name, ref_lines, ref__lines, ref_ind_name, ref_is_overlay, ref_category, ref_indicator, ref_doubles, ref_plotinfo, ref_span, ref__signal in ref_indicators:
                    ref_signal_info = ref_plotinfo.get('signalstyle', {})
                    if not ref_signal_info:
                        continue
                    signal_ind_data_ = dict(
                        long_signal=None, exitlong_signal=None, short_signal=None, exitshort_signal=None)
                    for k, v in ref_signal_info.items():
                        signalkey, signalcolor, signalmarker, signaloverlap, signalshow, signalsize, signallabel = list(
                            v.values())
                        if not signalshow:
                            continue
                        islabel = isinstance(signallabel, dict)
                        if islabel:
                            label_text = signallabel.pop("text", k)
                        # 从合约0获取信号索引
                        ref_source_list = signal_ind_data_source[ik][0]
                        signal_index = None
                        for sd in ref_source_list:
                            if k in sd and sd[k] is not None:
                                signal_index = sd[k].data['index']
                                break
                        if signal_index is None:
                            continue
                        # 使用当前合约的价格数据
                        if signaloverlap:
                            price_data = df[signalkey].values
                            signal_fig = fig_ohlc
                        else:
                            signal_fig = fig
                            try:
                                if ref_doubles:
                                    index1, index2 = search_index(
                                        ref__lines, signalkey)
                                    price_data = ref_indicator[index1][:, index2]
                                else:
                                    price_data = ref_indicator[:, ref__lines.index(
                                        signalkey)]
                            except:
                                price_data = np.zeros(len(signal_index))
                        signal_price = price_data[signal_index.astype(int)]
                        signal_datetime = df.datetime.values[signal_index.astype(int)]
                        if islabel:
                            signal_source_ = ColumnDataSource(dict(
                                index=signal_index,
                                datetime=signal_datetime,
                                price=signal_price,
                                size=[float(signalsize),] *
                                len(signal_index),
                                text=[label_text] *
                                len(signal_index),
                            ))
                        else:
                            signal_source_ = ColumnDataSource(dict(
                                index=signal_index,
                                datetime=signal_datetime,
                                price=signal_price,
                                size=[float(signalsize),] *
                                len(signal_index),
                            ))
                        signal_ind_data_.update({k: signal_source_})
                        # [修改] 原代码: marker=signalmarker
                        #   signalmarker 可能是 Markers 枚举里的 lightweight_charts 专用名
                        #   (arrow_up/arrow_down), 或 TradingView 风格的 label_up/label_down;
                        #   bokeh 不认这些名字 -> E-1001 BAD_COLUMN_NAME 且标记被静默丢弃。
                        #   统一经 to_bokeh_marker 收敛(见 minibt/constant.py)。
                        r = signal_fig.scatter(x='index', y='price', source=signal_source_, fill_color=signalcolor,
                                              marker=to_bokeh_marker(signalmarker), line_color='black', size="size")
                        if islabel:
                            signallabel.update(
                                dict(background_fill_alpha=0.1, background_fill_color="white" if black_style else "black"))
                            labels = LabelSet(
                                x='index', y='price', text='text', source=signal_source_, **signallabel)
                            signal_fig.add_layout(labels)
                        tooltips = [(k, "@price{0.00}"),]
                        set_tooltips(signal_fig, tooltips,
                                     vline=False, renderers=[r,])
                    if any(v is not None for v in signal_ind_data_.values()):
                        signal_ind_data_source[ik][id].append(
                            signal_ind_data_)

            set_tooltips(fig_ohlc, ohlc_tooltips,
                         vline=True, renderers=[ohlc_bars])
            fig_ohlc.yaxis.axis_label = f"{symbols[ik][id]}_{symbol_multi_cycle[ik][id]}"
            fig_ohlc.yaxis.axis_label_text_color = black_color

                        # [新增] 把 Volume Profile / 成交量 overlay 排除出价格 y 轴的自动拟合:
            #   它们的 y 值跨越整段数据的价格范围(成交量基线更是常量最低价),
            #   若不排除, y 轴掩码会把主轴拉成全历史范围(横缩后极值仍不对)。
            #   此处所有图层均已建完 -> 除它们之外全部图层照旧参与拟合。
            try:
                _ex = [r for r in fig_ohlc.renderers
                       if getattr(r, 'tags', None) and '__vp_excl__' in r.tags]
                if _ex:
                    fig_ohlc.y_range.renderers = [r for r in fig_ohlc.renderers
                                                  if r not in _ex]
            except Exception:
                ...
            custom_js_args = dict(ohlc_range=fig_ohlc.y_range, indicator_range=[indicator_figs[_ic].y_range for _ic in range(len(indicator_figs))],
                                  indicator_h=indicator_h, indicator_l=indicator_l, source=source[ik][id])

            # 成交量
            # [修改] 成交量已**固定叠加到主 K 线图**(见 ohlc_bars 之后那段),
            #   这里默认不再单独显示高度 60 的成交量副图; 需要时把 show_volume_pane 改 True。
            # [开关] 由 Config.volume_mode 决定（'sub' / 'both' 时显示独立副图）
            #   原代码: show_volume_pane = True    # [改回] 恢复原来的独立成交量副图
            show_volume_pane = volume_mode in ('sub', 'both')
            fig_volume = new_indicator_figure(
                new_bokeh_figure, fig_ohlc, plot_width, y_axis_label="volume", height=60)
            fig_volume.css_classes = ["volume-chart"]
            fig_volume.visible = show_volume_pane
            fig_volume.xaxis.formatter = fig_ohlc.xaxis[0].formatter
            fig_volume.xaxis.visible = True
            # ★ [修复] 只有**真的显示**成交量副图时才隐藏主图 x 轴（否则会把时间轴藏掉，
            #   而副图又不可见 -> 图上看不到任何时间刻度）。原代码是无条件执行:
            #   fig_ohlc.xaxis.visible = False  # Show only Volume's xaxis
            if show_volume_pane:
                fig_ohlc.xaxis.visible = False  # Show only Volume's xaxis
            
            r_volume = fig_volume.vbar(
                'index', BAR_WIDTH, 'volume', source=source[ik][id], color=inc_cmap)
            colors = cycle(colorgen())
            r_volume5 = fig_volume.line('index', 'volume5', source=source[ik][id],
                                        legend_label='volume5', line_color=next(colors),
                                        line_width=1.3)
            r_volume10 = fig_volume.line('index', 'volume10', source=source[ik][id],
                                         legend_label='volume10', line_color=next(colors),
                                         line_width=1.3)
            set_tooltips(fig_volume, [
                        ('volume', '@volume{0.00}'), ('volume5', '@volume5{0.00}'), ('volume10', '@volume10{0.00}'),], renderers=[r_volume])
            fig_volume.yaxis.formatter = NumeralTickFormatter(
                format="0 a")  # format="0"
            fig_volume.yaxis.axis_label_text_color = black_color
            
            if fig_ohlc._main_ohlc:
                fig_volume.yaxis.visible = False
                # 当 ismain=True 时，不添加自动缩放回调，避免影响主图表的 Y 轴
            else:
                fig_volume.yaxis.visible = True
                # 只有非 ismain 的图表才添加自动缩放回调
                custom_js_args.update(volume_range=fig_volume.y_range)
                fig_ohlc.x_range.js_on_change('end', CustomJS(args=custom_js_args,
                                                              code=_AUTOSCALE_JS_CALLBACK))
            # 交易信号线段（每个合约都显示）
            if trade_signal:
                # 多头连线：用虚线连接入场→出场，悬停显示P/L
                ls = fig_ohlc.segment(x0='index', y0='price', x1='flat_index', y1='flat_price',
                                    source=long_segment_source[ik][id], color='yellow' if black_style else "blue", line_width=3, line_dash="4 4")
                ss = fig_ohlc.segment(x0='index', y0='price', x1='flat_index', y1='flat_price',
                                    source=short_segment_source[ik][id], color='yellow' if black_style else "blue", line_width=3, line_dash="4 4")
                # 多单入场信号：正三角
                l_entry = fig_ohlc.scatter(x='index', y='price', source=long_segment_source[ik][id],
                                           marker='triangle', size=12, color='red', fill_color='red')
                # 空单入场信号：倒三角
                s_entry = fig_ohlc.scatter(x='index', y='price', source=short_segment_source[ik][id],
                                           marker='inverted_triangle', size=12, color='green', fill_color='green')
                # 为 datetime 字段添加格式化器
                fig_ohlc.add_tools(HoverTool(
                    point_policy='follow_mouse',
                    renderers=[ls, ss, l_entry, s_entry],
                    formatters={'@entry_datetime': 'datetime', '@exit_datetime': 'datetime'},
                    tooltips=[("方向", "@side"), ("入场时间", "@entry_datetime{%Y-%m-%d %H:%M}"), ("出场时间", "@exit_datetime{%Y-%m-%d %H:%M}"), ("持仓分钟", "@hold_minutes{0}"), ("入场价", "@price{0.00}"), ("出场价", "@flat_price{0.00}"), ("P/L", "@profit{0.00}")],
                    mode='mouse'))
            plots: list[_figure] = [
                fig_ohlc, fig_volume]+indicator_figs
            # 权益曲线（仅第一个合约显示）
            if id == 0 and profit_plot[ik]:
                source_key = 'value'
                fig_value = new_indicator_figure(new_bokeh_figure, fig_ohlc, plot_width,
                                                 y_axis_label=source_key,
                                                 height=90)
                fig_value.css_classes = ["value-chart"]
                fig_value.tags = ["profit_plot"]
                fig_value.patch('index', 'level',
                                source=value_source[ik][id],
                                fill_color='#ffffea', line_color='#ffcb66', line_dash='dashed')
                # 初始资金与权益曲线之间的色带（level 为初始资金，value 为权益曲线）
                band_value = Band(
                    base='index',
                    lower='level',
                    upper=source_key,
                    source=value_source[ik][id],
                    fill_color='#4dabf7',
                    fill_alpha=0.15,
                    line_width=0,
                    level='underlay',
                )
                fig_value.add_layout(band_value)
                r_value = fig_value.line(
                    'index', source_key, source=value_source[ik][id], legend_label='value', line_color='blue', line_width=2, line_alpha=1)
                tooltip_format = f'@{source_key}{{+0,0.[00]}}'
                tick_format = '0,0.[00]'
                set_tooltips(
                    fig_value, [(source_key, tooltip_format)], renderers=[r_value,])

                fig_value.yaxis.formatter = NumeralTickFormatter(
                    format=tick_format)
                fig_value.yaxis.axis_label = 'Value'
                fig_value.yaxis.axis_label_text_color = black_color
                plots.insert(0, fig_value)
            figs_ohlc[ik].append(fig_ohlc)
            linked_crosshair = CrosshairTool(
                dimensions='both', line_color=black_color)

            for f in plots:
                if f.legend:
                    f.legend.nrows = 1
                    f.legend.label_height = 6
                    f.legend.visible = True
                    f.legend.location = 'top_left'
                    f.legend.border_line_width = 0
                    f.legend.padding = 1
                    f.legend.spacing = 0
                    f.legend.margin = 0
                    f.legend.label_text_font_size = '8pt'
                    f.legend.label_text_line_height = 1.2
                    f.legend.click_policy = click_policy[ik]

                f.min_border_left = 0
                f.min_border_top = 0  # 3
                f.min_border_bottom = 6
                f.min_border_right = 10
                f.outline_line_color = '#666666'

                if black_style:
                    # 图表全局样式
                    f.background_fill_color = "#1a1a1a"  # 更柔和的深灰色
                    f.border_fill_color = "#1a1a1a"
                    f.outline_line_color = "#404040"  # 边框线颜色

                    # 坐标轴样式
                    f.xaxis.major_label_text_color = "#cccccc"
                    f.xaxis.axis_label_text_color = "#cccccc"
                    f.xaxis.major_tick_line_color = "#666666"
                    f.xaxis.minor_tick_line_color = "#444444"
                    f.xaxis.axis_line_color = "#666666"

                    f.yaxis.major_label_text_color = "#cccccc"
                    f.yaxis.axis_label_text_color = "#cccccc"
                    f.yaxis.major_tick_line_color = "#666666"
                    f.yaxis.minor_tick_line_color = "#444444"
                    f.yaxis.axis_line_color = "#666666"

                    # 网格线样式
                    f.xgrid.grid_line_color = "#333333"
                    f.xgrid.grid_line_alpha = 0.3
                    f.ygrid.grid_line_color = "#333333"
                    f.ygrid.grid_line_alpha = 0.3

                    # 图例样式
                    f.legend.background_fill_color = "#333333"
                    f.legend.background_fill_alpha = 0.7
                    f.legend.label_text_color = "#ffffff"
                    f.legend.border_line_color = "#555555"

                    # 标题样式（如果图表有标题）
                    if f.title:
                        f.title.text_color = "#ffffff"
                        f.title.text_font_style = "bold"

                    # 成交量图特殊处理
                    if f == fig_volume:
                        f.background_fill_alpha = 0.5  # 半透明效果
                        f.border_fill_alpha = 0.5
                f.add_tools(linked_crosshair)
                wheelzoom_tool = next(
                    wz for wz in f.tools if isinstance(wz, WheelZoomTool))
                wheelzoom_tool.maintain_focus = False
                if f._main_ohlc:
                    f.yaxis.visible = False
                    f.tools.visible = False
            kwargs = dict(
                ncols=1,
                toolbar_location='right',
                sizing_mode='scale_width',  # 改为scale_width，只横向拉伸，保持纵向高度
                toolbar_options=dict(logo=None),
                merge_tools=True
            )
            all_plots.append(plots)

        ismain = btind_main[ik][1:]

        # 初始化 panels 列表
        panels = []

        if any(ismain):
            _ip = 0
            _all_plots = [_p for _ip, _p in enumerate(
                all_plots[1:]) if not ismain[_ip]]
            first_plot = all_plots[0]
            row_plots = []
            for _ismain, _plots in list(zip(ismain, all_plots[1:])):
                if _ismain:
                    _ip += 1
                    figs = gridplot(
                        _plots,
                        ** kwargs
                    )
                    row_plots.append(figs)
            controls = row(*row_plots, width_policy='max') if row_plots else None
            figs = gridplot(
                first_plot,
                ** kwargs
            )
            # 将 ismain=True 的图表合并到主布局
            if controls:
                _lay = column(controls, figs, width_policy='max',
                              sizing_mode='scale_width')
            else:
                _lay = column(figs, width_policy='max',
                              sizing_mode='scale_width')
            name_ = '_'.join(
                [symbols[ik][0], *(str(symbol_multi_cycle[ik][__ip]) for __ip in range(1, _ip+1))])
            # 将合并后的布局添加到 panels 列表的开头
            panels.append(
                Panel(child=_lay, title=name_))
            # 更新 all_plots 为不包含 ismain=True 的图表
            all_plots = _all_plots
        else:
            # 如果没有 ismain=True 的图表，将第一个图表作为默认面板
            figs = gridplot(
                all_plots[0],
                ** kwargs
            )
            panels.append(
                Panel(child=column(figs, width_policy='max', sizing_mode='scale_width'),
                      title=f"{symbols[ik][0]}_{symbol_multi_cycle[ik][0]}"))
            all_plots = all_plots[1:]
        # 添加剩余的 ismain=False 的图表
        for _ips, __plots in enumerate(all_plots):
            layout = column(
                children=__plots,
                sizing_mode='scale_width',
                css_classes=["dynamic-column"],
                stylesheets=[panel_CUSTOM_CSS],  # 注入自定义CSS
            )

            panels.append(
                Panel(
                    child=layout, title=f"{symbols[ik][_ips + (1 if any(ismain) else 1)]}_{symbol_multi_cycle[ik][_ips + (1 if any(ismain) else 1)]}"))
        # 添加因子分析图表作为新的Panel
        for fi, factors_df in enumerate(factors_dfs[ik]):
            if factors_df is not None:
                if _factors_plot is None:
                    from .factors_plot import factors_plot
                    _factors_plot = factors_plot
                factor_layout = _factors_plot(factors_df)  # 生成因子分析布局
                # 加入当前策略的panels
                panels.append(Panel(child=factor_layout,
                              title=f"{factors_names[ik][fi]}因子分析"))

        ts.append(Tabs(tabs=panels,
                  width=plot_width if plot_width else None, width_policy='max',
                  sizing_mode='scale_width',
                       css_classes=["dark-tabs"] if black_style else [],
                       stylesheets=[DARK_TABS_CSS] if black_style else []
                       ))
    # 创建策略图表的面板
    all_panels = [Panel(child=t, title=s_name[i]) for i, t in enumerate(ts)]
    tabs = Tabs(tabs=all_panels,
                background=white_color, width=plot_width if plot_width else None, width_policy='max',
                sizing_mode='scale_width',
                css_classes=["dark-tabs"] if black_style else [],
                stylesheets=[DARK_TABS_CSS] if black_style else []
                )
    if open_browser:
        IS_JUPYTER_NOTEBOOK = False
    INLINE.css_raw.append(panel_CUSTOM_CSS)  # 确保CSS被包含
    if IS_JUPYTER_NOTEBOOK:
        from bokeh.io import output_notebook
        notebook_handle = True
        open_browser = False
        output_notebook(INLINE)
    else:
        notebook_handle = False
        open_browser = True

    # 保存图表
    if plot_name and isinstance(plot_name, str):
        if not plot_name.endswith('.html'):
            plot_name += 'bokeh_plot.html'
    else:
        plot_name = 'bokeh_plot.html'
    plot_cwd = plot_cwd if isinstance(
        plot_cwd, str) and plot_cwd else os.path.join(os.path.dirname(os.path.abspath(__file__)), "plots")
    if not os.path.exists(plot_cwd):
        os.makedirs(plot_cwd, exist_ok=True)
    FileName = os.path.join(plot_cwd, plot_name)
    html = file_html(tabs, CDN, "Strategy Plot")
    if save_plot or IS_JUPYTER_NOTEBOOK:
        with open(FileName, 'w', encoding='utf-8') as f:
            f.write(html)

    # 显示图表
    try:
        show(tabs, browser=None if open_browser else 'none',
             notebook_handle=notebook_handle)
    except Exception as e:
        if IS_JUPYTER_NOTEBOOK:
            from IPython.display import display, HTML

            # 读取保存的 HTML 文件内容
            with open(FileName, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # 在 Jupyter 中显示 HTML 内容
            display(HTML(html_content))
        else:
            import webbrowser
            # 在默认浏览器中打开 HTML 文件
            webbrowser.open('file://' + os.path.abspath(FileName))

    return tabs


def get_trades_source(data: pd.DataFrame, trades: pd.DataFrame) -> tuple[ColumnDataSource]:
    datetime = data.datetime.values
    high = data.high.values
    low = data.low.values
    close = data.close.values
    position = trades.positions.values
    sizes = trades.sizes.values
    ps = position*sizes
    cum_profit = trades.cum_profits.values
    short_ticks = []
    long_ticks = []
    long_flat_ticks = []
    short_flat_ticks = []
    long_profit = []
    short_profit = []
    pre_pos = 0
    for i, pos_ in enumerate(position):
        cp = cum_profit[i]
        if pos_ == -1 and pre_pos == 0:
            short_ticks.append(i)
            pre_cp = cum_profit[max(i-1, 0)]  # 开仓bar已扣手续费，取前一根bar避免计入
        elif pos_ == 1 and pre_pos == 0:
            long_ticks.append(i)
            pre_cp = cum_profit[max(i-1, 0)]  # 开仓bar已扣手续费，取前一根bar避免计入
        elif pos_ == 0:
            if pre_pos == 1:
                long_flat_ticks.append(i)
                long_profit.append(cp - pre_cp)
            elif pre_pos == -1:
                short_flat_ticks.append(i)
                short_profit.append(cp - pre_cp)
        else:
            if pos_ != pre_pos and pre_pos != 0:
                if pos_ == 1:
                    short_flat_ticks.append(i)
                    short_profit.append(cp - pre_cp)

                    long_ticks.append(i)
                    pre_cp = cp
                else:
                    long_flat_ticks.append(i)
                    long_profit.append(cp - pre_cp)
                    short_ticks.append(i)
                    pre_cp = cp
        pre_pos = pos_

    # long
    long_source = ColumnDataSource(dict(
        index=long_ticks,
        datetime=datetime[long_ticks],
        price=low[long_ticks],
        pos=ps[long_ticks],
        size=[12.,]*len(long_ticks)
    ))
    short_source = ColumnDataSource(dict(
        index=short_ticks,
        datetime=datetime[short_ticks],
        price=high[short_ticks],
        pos=ps[short_ticks],
        size=[12.,]*len(short_ticks)
    ))
    long_flat_source = ColumnDataSource(dict(
        index=long_flat_ticks,
        datetime=datetime[long_flat_ticks],
        price=high[long_flat_ticks],
        pos=ps[long_flat_ticks],
        profit=long_profit,
        size=[12.,]*len(long_flat_ticks)
    ))

    short_flat_source = ColumnDataSource(dict(
        index=short_flat_ticks,
        datetime=datetime[short_flat_ticks],
        price=low[short_flat_ticks],
        pos=ps[short_flat_ticks],
        profit=short_profit,
        size=[12.,]*len(short_flat_ticks)
    ))
    if len(long_ticks) != len(long_flat_ticks):
        long_ticks = long_ticks[:-1]
    if len(short_ticks) != len(short_flat_ticks):
        short_ticks = short_ticks[:-1]

    long_segment_source = ColumnDataSource(dict(
        index=long_ticks,
        price=close[long_ticks],
        flat_index=long_flat_ticks,
        flat_price=close[long_flat_ticks],
        profit=long_profit,
        side=['多头']*len(long_ticks),
        entry_datetime=datetime[long_ticks],
        exit_datetime=datetime[long_flat_ticks],
        hold_minutes=(datetime[long_flat_ticks] - datetime[long_ticks]).astype('timedelta64[m]').astype(float),
    ))
    short_segment_source = ColumnDataSource(dict(
        index=short_ticks,
        price=close[short_ticks],
        flat_index=short_flat_ticks,
        flat_price=close[short_flat_ticks],
        profit=short_profit,
        side=['空头']*len(short_ticks),
        entry_datetime=datetime[short_ticks],
        exit_datetime=datetime[short_flat_ticks],
        hold_minutes=(datetime[short_flat_ticks] - datetime[short_ticks]).astype('timedelta64[m]').astype(float),
    ))

    return long_source, short_source, long_flat_source, short_flat_source, long_segment_source, short_segment_source
