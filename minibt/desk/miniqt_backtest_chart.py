"""直接复用 MiniQT 的回测图表代码（不是重新实现）。

这里只把 MiniQT ``BacktestInterface`` 里和 Qt 无关的**画图部分**搬过来：

* ``_prepare_contract_frame`` / ``_build_info_contracts``
* ``_render_contract`` 里的 ``_plot_contract_overlays``
* ``BacktestPage``（minibt.strategy.pages，MiniQT 回测结果页用的就是它）

唯一的替换是：MiniQT 用 ``PylightchartsChartWindow`` + QtWebEngine；
desk 浏览器端用 ``pylightcharts.headless.HeadlessChart`` 记录同一套
pylightcharts 调用，再由 :meth:`HeadlessChart.to_html` 生成一个
**自包含 HTML**，前端用 iframe 装载。

这样图表里的 K 线、指标、交易信号、入场→离场连线、停止线、成交量、
权益 / 回撤 / 盈亏副图、图例……全部和 MiniQT 是同一份代码画出来的，
不再由 desk 的 TypeScript 重画一套。
"""
from __future__ import annotations

import pandas as pd

from pylightcharts.headless import HeadlessChart
from pylightcharts.util import LINE_STYLE, as_enum

from ..strategy.pages import BacktestPage
from ..strategy.realtime import (apply_signals, draw_contract_info,
                                 draw_trade_lines,
                                 extract_minibt_indicators,
                                 extract_minibt_signal_texts,
                                 extract_minibt_signals, palette_for,
                                 strategy_backtest_dict, strategy_contracts,
                                 strategy_kline_frame)


def to_chart_time(values) -> pd.Series:
    """MiniQT ``windows.backtest_chart.to_chart_time`` 的原实现（复制）。"""
    series = pd.Series(values)
    if pd.api.types.is_datetime64_any_dtype(series):
        times = pd.to_datetime(series)
        if getattr(times.dt, 'tz', None) is not None:
            times = times.dt.tz_convert('UTC').dt.tz_localize(None)
    else:
        numeric = pd.to_numeric(series, errors='coerce').fillna(0)
        top = float(numeric.abs().max() or 0)
        if top > 1e17:
            times = pd.to_datetime(numeric, unit='ns')
        elif top > 1e14:
            times = pd.to_datetime(numeric, unit='us')
        elif top > 1e11:
            times = pd.to_datetime(numeric, unit='ms')
        else:
            times = pd.to_datetime(numeric, unit='s')
    return (times + pd.Timedelta(hours=8)).astype('datetime64[ns]')


def _tail_offset(total: int, bars: int) -> int:
    """MiniQT ``BacktestInterface._tail_offset``（复制）。"""
    try:
        bars = int(bars or 0)
    except (TypeError, ValueError):
        bars = 0
    return max(0, int(total) - bars) if bars > 0 else 0


def _prepare_contract_frame(strategy, contract: str,
                            initial_bars: int = 0):
    """MiniQT ``_prepare_contract_frame``（复制，去掉 Qt 日志）。"""
    try:
        frame = strategy_kline_frame(strategy, contract)
    except Exception:                                            # noqa: BLE001
        return None, 0
    if frame is None or getattr(frame, 'empty', True):
        return None, 0
    try:
        frame = frame.copy()
        frame['time'] = to_chart_time(frame['time'])
        offset = _tail_offset(len(frame), initial_bars)
        if offset:
            frame = frame.iloc[offset:].reset_index(drop=True)
        return frame[['time', 'open', 'high', 'low', 'close', 'volume']], offset
    except Exception:                                            # noqa: BLE001
        return None, 0


def _chart_time_frame(data, offset: int = 0):
    """MiniQT ``_chart_time_frame``（复制）。"""
    if data is None:
        return None
    try:
        frame = pd.DataFrame(data)
    except Exception:                                            # noqa: BLE001
        return data
    if frame.empty or 'time' not in frame.columns:
        return frame
    frame = frame.copy()
    try:
        frame['time'] = to_chart_time(frame['time'])
    except Exception:                                            # noqa: BLE001
        return frame
    if offset and offset < len(frame):
        # ⚠ `offset >= len(frame)` 时**不能**直接返回 None：盈亏 / 权益这些
        #   逐笔数据的根数本来就比 K 线少，整段被丢掉 → 副图空白、只剩标签
        #   （用户反馈 cci 的盈亏散点图不显示 ✗）
        frame = frame.iloc[offset:].reset_index(drop=True)
    return frame


def _apply_legend(chart, contract: str, theme_dark: bool = True) -> None:
    """MiniQT ``_apply_panel_legend`` 的核心（复制，去掉 Qt 主题读取）。"""
    symbol, _sep, cycle = str(contract or '').rpartition('_')
    options = {'visible': True, 'ohlc': True, 'percent': True,
               'lines': True, 'text_visible': False}
    if symbol:
        options['text'] = f'{symbol}  {cycle}' if cycle else symbol
    else:
        options['text'] = str(contract or '')
    try:
        chart.legend(**options)
    except Exception:                                            # noqa: BLE001
        try:
            chart.legend(visible=True, text=str(options.get('text') or ''),
                         text_visible=False)
        except Exception:                                    # noqa: BLE001
            pass


def _tail_values(values, count: int):
    """把全量信号数组对齐到**当前图**的 `count` 根（取最后 count 个 ✓）

    `extract_minibt_signals` 给的是全量（回测跑完整段），而合约图只画最后
    `visible_bars` 根 → 不切就会整体错位（信号全跑到最后一根上 ✗）
    """
    if values is None:
        return None
    try:
        seq = list(values)
    except TypeError:
        return values
    if count <= 0 or len(seq) <= count:
        return seq
    return seq[-count:]


def _enable_indicator_menu(strategy, series, spec, name: str, kind: str,
                           style: str, line_width: int,
                           color) -> None:
    """图例上的**齿轮菜单**（参数 / 线型 / 线宽 / 颜色 / 其它 ✓）

    `minibt/strategy/indicator_menu.py` 里那套（实时图表 / miniqt 早就用上了），
    回测图以前没挂 → 用户反馈"回测图没有指标设置按钮" ✗。
    参数页确认后由 desk 侧重算指标并重建 HTML（见 `StrategyLab.indicator_params`）。
    """
    try:
        from types import SimpleNamespace
        from ..strategy import indicator_menu as _menu
    except Exception:                                            # noqa: BLE001
        return
    params = None
    try:
        datasets = getattr(strategy, '_btindicatordataset', None) or {}
        source = str(getattr(spec, 'source', '') or '')
        dataset = datasets.get(source)
        if dataset is not None:
            params = _menu.params_for_dataset(dataset) or None
    except Exception:                                            # noqa: BLE001
        params = None
    spec2 = SimpleNamespace(
        name=name, kind=kind, line_style=style, line_width=line_width,
        color=color, price_line=bool(getattr(spec, 'price_line', True)),
        price_label=bool(getattr(spec, 'price_label', True)),
        menu_params=params)
    try:
        series.pin_legend_row(True)      # 没有十字线也常驻图例行 ✓
    except Exception:                                            # noqa: BLE001
        pass
    try:
        series.enable_legend_menu(_menu.build_config(spec2), None)
    except Exception:                                            # noqa: BLE001
        pass


def _plot_contract_overlays(chart, strategy, contract: str,
                            frame: pd.DataFrame, plot_id: int,
                            theme_dark: bool = True) -> None:
    """MiniQT ``_plot_contract_overlays``（复制）。

    * 指标线：主图叠加 / 副图；
    * 信号：B / S 标记；
    * 入场→离场连线 + 四类交易标记。
    """
    if chart is None or frame is None:
        return
    times = list(frame['time'])
    palette = palette_for(chart)
    palette_index = 0

    # 指标线（与 MiniQT 的 _plot_contract_overlays 完全相同）
    try:
        specs = extract_minibt_indicators(strategy, plot_id)
    except Exception:                                            # noqa: BLE001
        specs = []
    for spec in specs:
        try:
            kind = getattr(spec, 'kind', 'Line') or 'Line'
            name = getattr(spec, 'name', '') or 'line'
            style = str(getattr(spec, 'line_style', 'solid') or 'solid')
            options = {'name': name,
                       'line_width': getattr(spec, 'line_width', 2)}
            if kind == 'Line':
                options['line_style'] = as_enum(style, LINE_STYLE)
            color = getattr(spec, 'color', None)
            # MiniQT 的 IndicatorSpec 经常是 color=None（引擎默认全是蓝色）。
            # 这里用 MiniQT 同一套 palette 给没配色的线分配不同颜色 ✓
            if not color:
                if palette:
                    color = palette[palette_index % len(palette)]
                    palette_index += 1
            if color:
                options['color'] = color
            if getattr(spec, 'overlap', False):
                series = chart.add_series(kind, **options)
            else:
                series = chart.pane_add_series(chart.add_pane(), kind,
                                               **options)
            _enable_indicator_menu(strategy, series, spec, name, kind,
                                   style, options.get('line_width', 2),
                                   color)
            try:
                series.prefer_single_gap()
            except Exception:                                    # noqa: BLE001
                pass
            values = getattr(spec, 'values', None)
            if values is not None:
                vals = list(values)
                if len(vals) > len(times):
                    vals = vals[-len(times):]
                if len(vals) == len(times):
                    series.set(pd.DataFrame({'time': times, name: vals}))
        except Exception:                                        # noqa: BLE001
            continue

    # 交易信号 → **自定义序列**的 B / S 三角（和 MiniQT / 实时窗口同一份代码）
    #
    # ⚠ 以前用 `chart.marker_list(...)`（LWC 原生 marker primitive）：
    #   * 标记不计入自动缩放 → 放大后下方的标记被裁掉；
    #   * 回放时序列数据被截断，但 marker 是挂在序列上的 primitive，**截不掉**
    #     → 未来的信号全堆在最后一根 K 线上（用户实测 ✗）。
    #   改用 `apply_signals`（`add_custom_series`）后，信号是**数据**，
    #   跟着回放一起截断 ✓
    try:
        total = len(times)
        signals = []
        for (name, values, style, anchor, _pane) in extract_minibt_signals(
                strategy, plot_id):
            sliced = None if values is None else _tail_values(values, total)
            anchor_values = (None if anchor is None
                             else _tail_values(anchor, total))
            signals.append((name, sliced, style, anchor_values, 0))
        texts = extract_minibt_signal_texts(strategy, plot_id, theme_dark)
        apply_signals(chart, frame, signals, texts)
    except Exception:                                            # noqa: BLE001
        pass

    # 入场→离场连线 + 四类交易标记
    try:
        draw_trade_lines(chart, strategy, contract, frame, 0,
                         theme_dark=theme_dark, align='tail')
    except Exception:                                            # noqa: BLE001
        pass


def _build_info_contracts(chart, strategy, contract: str,
                          theme_dark: bool = True, initial_bars: int = 0):
    """MiniQT ``_build_info_contracts``（复制，去掉 Qt 窗口操作）。"""
    contracts = list(strategy_contracts(strategy))
    if not contracts:
        return None, 0
    main = contract if contract in contracts else contracts[0]
    frame0, offset = _prepare_contract_frame(strategy, main, initial_bars)
    if frame0 is None:
        return None, 0
    chart.set(frame0)
    chart.fit()
    palette = palette_for(chart)
    draw_contract_info(
        chart, strategy, main, frame0, 0,
        palette=palette, theme_dark=theme_dark, align='tail',
        single_gap=True)
    draw_trade_lines(
        chart, strategy, main, frame0, 0,
        theme_dark=theme_dark, align='tail')
    for other in contracts:
        if other == main:
            continue
        frame, _offset = _prepare_contract_frame(strategy, other,
                                                 initial_bars)
        if frame is None:
            continue
        try:
            pane = chart.add_pane()
            series = chart.pane_add_series(
                pane, 'Candlestick', name=other,
                price_line_visible=False)
            series.set(frame)
            draw_contract_info(
                chart, strategy, other, frame, pane,
                palette=palette, theme_dark=theme_dark, align='tail',
                single_gap=True)
            draw_trade_lines(
                chart, strategy, other, frame, pane,
                theme_dark=theme_dark, align='tail')
        except Exception:                                        # noqa: BLE001
            continue
    return main, offset


def _show_tail(chart, total: int, bars: int = 300) -> None:
    """初始只显示最近 N 根（和 MiniQT 看盘/回测截图的观感一致）。

    数据仍然全部在图表里，用户可以继续缩放 / 平移；只是不把 8964 根
    压成 0.1px 一根（那样蜡烛和标记会挤成一团）。
    """
    if total <= 0:
        return
    bars = min(max(30, int(bars or 300)), total)
    try:
        chart.set_visible_logical_range(total - bars - 0.5, total - 0.5)
    except Exception:                                            # noqa: BLE001
        try:
            chart.fit()
        except Exception:                                    # noqa: BLE001
            pass


def _style_pane_separators(chart, theme_dark: bool = True) -> None:
    """主图 / 副图、副图 / 副图之间的分隔线：2px + 跟本地图表同款底色。

    LWC 只允许通过 ``layout.panes.separatorColor`` 改颜色，固定 1px；
    2px 的高度由生成 HTML 后注入的 CSS 补上。``enable_resize=True``
    仍然保留，拖分隔线调整副图高度的热区不受影响 ✓。
    """
    color = ('rgba(148, 163, 184, .45)' if theme_dark
             else 'rgba(100, 116, 139, .32)')
    try:
        chart.pane_separator(color=color,
                             hover_color='rgba(56,189,248,.55)',
                             enable_resize=True)
    except Exception:                                            # noqa: BLE001
        pass


def _hide_pane_separators(chart, theme_dark: bool = True) -> None:
    """兼容旧调用名（实际已经是 2px 可见分隔线，不再隐藏）。"""
    _style_pane_separators(chart, theme_dark)


#: 画线工具 / 图表类型 / 回放 的**前端驱动**（P119）
#:
#: * `图表类型`：蜡烛 / 收盘线 / 面积 / 柱 —— 客户端换序列，不重新生成 HTML；
#: * `画线工具`：pylightcharts 自带 toolbox 的显示 / 隐藏；
#: * `删除画线工具`：`toolBox.clearDrawings()`；
#: * `回放`：参考 MiniQT `ReplayWindow`，逐根放出 K 线（指标 / 信号跟着截断）。
#:
#: 通信：父页面 `postMessage({__deskSL: cmd, ...})`，子页面回
#: `postMessage({__deskSL: 'state', ...})`（跨源也能用，Qt 的 file:// 壳同样 ✓）。
DESK_DRIVER_CSS = """
<style id="desk-sl-style">
/* 画线工具默认隐藏，点「画线工具」才显示；用 CSS 类控制，LWC 的 resize
   改 display 也盖不住 ✓ */
#container .toolbox { display: none !important; }
body.desk-sl-toolbox #container .toolbox { display: flex !important; }

/* ---- 左上角图例（K 线信息 + 指标标签）----
   * 字号跟**设置 → 图表配置 → 图表字体大小**（桌面端 `--desk-sl-font` 会覆盖 ✓）
   * 浅色主题下文字 / 眼睛 / 齿轮用深色，不再淡到看不见 ✓
   * 指标前的色块 → **圆点**（和本地图表一致 ✓） */
#container .legend, #container .legend * ,
#container .legend .series-container { font-size: var(--desk-sl-font, 13px) !important; }
body.desk-sl-light #container .legend,
body.desk-sl-light #container .legend * { color: #131722 !important; }
body.desk-sl-light #container .legend svg,
body.desk-sl-light #container .legend svg * { stroke: #131722 !important; }
/* 指标色块 = **圆点**（用户要求；8px 太小时会被看成小方框 ✗） */
#container .legend .legend-swatch,
#container .legend .series-container > div > span:first-child {
  border-radius: 50% !important; width: 10px !important;
  height: 10px !important; min-width: 10px !important;
  background-image: none !important; border: 0 !important;
  box-shadow: none !important; margin-right: 6px !important;
  display: inline-block !important; vertical-align: middle !important;
}
/* 折叠按钮（∧ / ∨ N）稍微明显一点 ✓ */
#container .legend-collapse { opacity: .95; font-size: 11px !important; }
</style>
"""

#: 驱动脚本（纯 JS，`__deskSL*` 是父页面调用的入口 ✓）
DESK_DRIVER_JS = r"""(function () {
  if (window.__deskSL) return;

  function findHandler() {
    if (window.__deskSLHandler) return window.__deskSLHandler;
    var keys = Object.keys(window);
    for (var i = 0; i < keys.length; i += 1) {
      var value;
      try { value = window[keys[i]]; } catch (err) { continue; }
      if (value && typeof value === 'object' && value.chart && value.series
          && typeof value.series.setData === 'function') {
        window.__deskSLHandler = value;
        return value;
      }
    }
    return null;
  }

  function allSeries(h) {
    var out = [];
    var push = function (s) { if (s && out.indexOf(s) < 0) out.push(s); };
    push(h.series);
    push(h.volumeSeries);
    (h._seriesList || []).forEach(push);
    return out;
  }

  var state = {
    kind: 'candle', toolbox: false, replay: false, speed: 1,
    bars: 0, total: 0, full: null, alt: null, timer: null,
    winWidth: 300,
    //: 左右各留 100 根**空白**（whitespace data）→ 缩放/平移到 (-100, 长度+100)
    pad: null, padLen: 0
  };

  //: 两端各留多少根空白（用户要求 `(-100, K线长度+100)` ✓）
  var PAD_BARS = 100;

  /* 数据按时间升序 → 二分找「<= last 的最后一个点」的下标，回放每拍只切一刀 ✓ */
  function cutIndex(times, last) {
    var lo = 0;
    var hi = times.length;
    while (lo < hi) {
      var mid = (lo + hi) >> 1;
      if (times[mid] <= last) lo = mid + 1; else hi = mid;
    }
    return lo;
  }

  function pack(data) {
    var times = new Array(data.length);
    for (var i = 0; i < data.length; i += 1) {
      times[i] = data[i] && data[i].time !== undefined ? data[i].time : 0;
    }
    return { data: data, times: times, cut: data.length };
  }

  /** 给 K 线两端补「空白数据点」，这样横向能滚到 -100 / 长度+100 ✓ */
  function buildPad(candles) {
    if (!candles || candles.length < 2) return;
    var step = candles[candles.length - 1].time
      - candles[candles.length - 2].time;
    if (!isFinite(step) || step <= 0) step = 60;
    var prefix = [];
    var suffix = [];
    for (var i = PAD_BARS; i >= 1; i -= 1) {
      prefix.push({ time: candles[0].time - step * i });
    }
    for (var j = 1; j <= PAD_BARS; j += 1) {
      suffix.push({ time: candles[candles.length - 1].time + step * j });
    }
    state.pad = { prefix: prefix, suffix: suffix };
    state.padLen = prefix.length;
  }

  /** 真实数据 + 两端空白 → 真正 setData 的数组 ✓ */
  function withPad(rows) {
    if (!state.pad) return rows;
    return state.pad.prefix.concat(rows, state.pad.suffix);
  }

  function snapshot(h) {
    if (state.full) return state.full;
    state.full = allSeries(h).map(function (series) {
      var data = [];
      try { data = series.data() || []; } catch (err) { data = []; }
      var entry = pack(data);
      entry.series = series;
      return entry;
    });
    state.total = 0;
    for (var i = 0; i < state.full.length; i += 1) {
      if (state.full[i].series === h.series) {
        state.total = state.full[i].data.length;
      }
    }
    if (!state.total && state.full.length) {
      state.total = state.full[0].data.length;
    }
    // 只给**K 线**补空白（时间轴是全局的，补一份就够；指标序列不用）✓
    var candle = candleEntry(h);
    if (candle && !state.pad) {
      buildPad(candle.data);
      try {
        candle.series.setData(withPad(candle.data));
        candle.cut = candle.data.length;
      } catch (err) { /* ignore */ }
    }
    return state.full;
  }

  function candleEntry(h) {
    var snap = snapshot(h);
    for (var i = 0; i < snap.length; i += 1) {
      if (snap[i].series === h.series) return snap[i];
    }
    return snap.length ? snap[0] : null;
  }

  function altData(h) {
    if (!state.alt) return { data: [], times: [], cut: 0 };
    return state.alt;
  }

  function buildAlt(h) {
    var candles = candleEntry(h);
    var rows = candles ? candles.data : [];
    var data;
    if (state.kind === 'bar') {
      data = rows.filter(function (bar) { return bar && bar.open !== undefined; });
    } else {
      data = [];
      rows.forEach(function (bar) {
        if (bar && typeof bar.close === 'number') {
          data.push({ time: bar.time, value: bar.close });
        }
      });
    }
    state.alt = pack(data);
    return state.alt;
  }

  function currentRange(h) {
    try { return h.chart.timeScale().getVisibleLogicalRange(); }
    catch (err) { return null; }
  }

  /**
   * 新增一根 K 线 → 视窗**整体左移一根**（宽度和「最新 K 线到右边界的距离」都不变 ✓）
   *
   * 以前每拍都 `setVisibleLogicalRange({from: to-width, to: n})`：右边界被钉死在
   * 最新一根上 → 用户缩放 / 拖动后一旦来新 K 线就被拉回去（用户实测 ✗）。
   * 现在只做**平移 delta**：
   *   * 最新一根在视窗里 → 平移 delta（缩放级别、右侧留白都保持）；
   *   * 用户拖到历史里（最新一根不在视窗）→ **不动**，让人安心看历史 ✓
   */
  function shiftForBars(h, prevBars, nextBars) {
    var delta = nextBars - prevBars;
    if (!(delta > 0)) return;
    var range = currentRange(h);
    if (!range || !isFinite(range.from) || !isFinite(range.to)) return;
    var newest = prevBars - 1;                 // 上一根最新 K 线的逻辑下标
    if (range.to < newest - 0.5) return;       // 最新一根在右边看不见 → 不打扰
    try {
      h.chart.timeScale().setVisibleLogicalRange({
        from: range.from + delta, to: range.to + delta
      });
    } catch (err) { /* ignore */ }
  }

  /* 按「放出根数」重设所有序列（指标 / 信号自动跟着截断，未变化就跳过 ✓） */
  function applyBars(h, count) {
    var snap = snapshot(h);
    var candles = candleEntry(h);
    var total = candles ? candles.data.length : 0;
    var n = Math.max(2, Math.min(Math.round(count), total));
    var last = candles && candles.data[n - 1] ? candles.data[n - 1].time : null;
    for (var i = 0; i < snap.length; i += 1) {
      var entry = snap[i];
      if (last === null) {
        if (entry.cut !== entry.data.length) {
          entry.series.setData(entry.data);
          entry.cut = entry.data.length;
        }
        continue;
      }
      var cut = cutIndex(entry.times, last);
      if (cut === entry.cut) continue;     // 这一拍该序列没变化 → 不重发 ✓
      var sliced = entry.data.slice(0, cut);
      entry.series.setData(entry === candles ? withPad(sliced) : sliced);
      entry.cut = cut;
    }
    var alt = altData(h);
    if (state.kind !== 'candle' && alt.data.length) {
      var altCut = last === null ? alt.data.length : cutIndex(alt.times, last);
      if (altCut !== alt.cut) {
        if (state.altSeries) state.altSeries.setData(alt.data.slice(0, altCut));
        alt.cut = altCut;
      }
    }
    // ★ 只平移、不重设范围：缩放级别 / 右侧留白都保持（用户拖动缩放不受影响 ✓）
    shiftForBars(h, state.bars, n);
    state.bars = n;
    post();
  }

  function restore(h) {
    var snap = snapshot(h);
    var candlesAll = candleEntry(h);
    for (var i = 0; i < snap.length; i += 1) {
      snap[i].series.setData(snap[i] === candlesAll
        ? withPad(snap[i].data) : snap[i].data);
      snap[i].cut = snap[i].data.length;
    }
    if (state.kind !== 'candle' && state.altSeries && state.alt) {
      state.altSeries.setData(state.alt.data);
      state.alt.cut = state.alt.data.length;
    }
    state.bars = state.total;
    try {
      var to = state.padLen + state.total;
      h.chart.timeScale().setVisibleLogicalRange({
        from: to - state.winWidth, to: to
      });
    } catch (err) { /* ignore */ }
    post();
  }

  function stopTimer() {
    if (state.timer) { clearInterval(state.timer); state.timer = null; }
  }

  function tick() {
    var h = findHandler();
    if (!h) return;
    if (state.bars >= state.total) { stopTimer(); post(); return; }
    applyBars(h, state.bars + 1);
    if (state.bars >= state.total) stopTimer();
  }

  function measureWindow(h) {
    var width = state.winWidth || 300;
    try {
      var range = h.chart.timeScale().getVisibleLogicalRange();
      if (range && isFinite(range.from) && isFinite(range.to)
          && range.to > range.from + 1) {
        width = Math.round(range.to - range.from);
      }
    } catch (err) { /* ignore */ }
    // 回测结果图初始是「全量 fit」（几千根）→ 夹到 600，否则回放一屏太多 ✓
    state.winWidth = Math.max(20, Math.min(600, width));
    return state.winWidth;
  }

  function startReplay(h, bars) {
    snapshot(h);
    state.replay = true;
    measureWindow(h);
    if (!bars) {
      bars = Math.max(30, Math.min(state.winWidth,
        Math.round(state.total * 0.6)));
    }
    var target = Math.min(bars, state.total);
    // 先把视窗摆到目标位置（宽度 = 当前视窗宽度，或默认 300；下标含左侧空白）
    var lastIdx = state.padLen + (target - 1) + 1;
    try {
      h.chart.timeScale().setVisibleLogicalRange({
        from: lastIdx - state.winWidth, to: lastIdx
      });
    } catch (err) { /* ignore */ }
    state.bars = target;                       // 先记位置，平移才不会多加
    applyBars(h, target);
    post();
  }

  function play(h) {
    if (!state.replay) startReplay(h, 0);
    stopTimer();
    var interval = Math.max(16, Math.round(400 / Math.max(1, state.speed)));
    state.timer = setInterval(tick, interval);
    post();
  }

  function setType(h, kind) {
    kind = String(kind || 'candle');
    if (['candle', 'line', 'area', 'bar'].indexOf(kind) < 0) kind = 'candle';
    state.kind = kind;
    if (state.altSeries) {
      try { h.chart.removeSeries(state.altSeries); } catch (err) { /* ignore */ }
      state.altSeries = null;
    }
    state.alt = null;
    try { h.series.applyOptions({ visible: kind === 'candle' }); }
    catch (err) { /* ignore */ }
    if (kind !== 'candle') {
      var L = window.LightweightCharts || {};
      var def = kind === 'line' ? L.LineSeries
        : (kind === 'area' ? L.AreaSeries : L.BarSeries);
      var options = {};
      if (kind === 'line') { options.color = '#2196f3'; options.lineWidth = 2; }
      if (kind === 'area') { options.lineColor = '#2196f3'; options.lineWidth = 2; }
      var alt = h.chart.addSeries(def, options, 0);
      try {
        alt.priceScale().applyOptions({ scaleMargins: { top: 0.2, bottom: 0.2 } });
      } catch (err) { /* ignore */ }
      var packed = buildAlt(h);
      alt.setData(packed.data);
      state.altSeries = alt;
    }
    if (state.replay) applyBars(h, state.bars);
    post();
  }

  function post() {
    try {
      parent.postMessage({
        __deskSL: 'state', kind: state.kind, toolbox: state.toolbox,
        replay: state.replay, playing: !!state.timer, bars: state.bars,
        total: state.total, speed: state.speed, window: state.winWidth
      }, '*');
    } catch (err) { /* ignore */ }
  }

  function applyCrosshair(h, color) {
    if (!h || !h.chart) return;
    // 空 = 恢复我们的默认蓝色（和 desk 十字线设置一致 ✓）
    var fallback = document.body.classList.contains('desk-sl-light')
      ? '#1a73e8' : '#2962ff';
    var label = color || fallback;
    try {
      h.chart.applyOptions({ crosshair: {
        vertLine: { labelBackgroundColor: label },
        horzLine: { labelBackgroundColor: label }
      }});
    } catch (err) { /* ignore */ }
  }

  function command(cmd, payload) {
    var h = findHandler();
    if (!h) return;
    payload = payload || {};
    switch (cmd) {
      case 'type': setType(h, payload.kind); break;
      case 'font': applyFont(payload.size); break;
      case 'crosshair': applyCrosshair(h, payload.color); break;
      case 'toolbox':
        state.toolbox = payload.show !== false;
        document.body.classList.toggle('desk-sl-toolbox', state.toolbox);
        post();
        break;
      case 'clearDrawings':
        try { if (h.toolBox) h.toolBox.clearDrawings(); } catch (err) { /* ignore */ }
        break;
      case 'replayStart': startReplay(h, Number(payload.bars) || 0); break;
      case 'replayPlay': play(h); break;
      case 'replayPause': stopTimer(); post(); break;
      case 'replayStep':
        stopTimer();
        if (!state.replay) startReplay(h, 0);
        else applyBars(h, state.bars + 1);
        break;
      case 'replaySpeed':
        state.speed = Math.max(1, Number(payload.speed) || 1);
        if (state.timer) play(h); else post();
        break;
      case 'replaySeek':
        if (!state.replay) startReplay(h, 0);
        applyBars(h, Math.round(state.total
          * Math.min(1, Math.max(0, Number(payload.frac) || 0))));
        break;
      case 'replayExit':
        stopTimer();
        state.replay = false;
        restore(h);
        break;
      default: break;
    }
  }

  window.__deskSL = {
    command: command, state: state, post: post, findHandler: findHandler
  };

  window.addEventListener('message', function (event) {
    var data = event.data;
    if (!data || !data.__deskSL || data.__deskSL === 'state') return;
    try { command(String(data.__deskSL), data); }
    catch (err) { console.error('[desk] strategy chart', err); }
  });

  /** 指标标签的「上拉 / 下拉」按钮（pylightcharts 自带 `legend.enableCollapse`） */
  function enableCollapse(h) {
    try {
      if (h.legend && h.legend.enableCollapse) h.legend.enableCollapse();
      else if (h.enableLegendCollapse) h.enableLegendCollapse();
    } catch (err) { /* ignore */ }
  }

  /**
   * 放宽缩放下限：默认最小 barSpacing 会把「一屏最多多少根」卡在 ~2000 根，
   * 用户缩放到底也拉不出完整历史 ✗ → 调小 `minBarSpacing`，并允许左右各留
   * 100 根的空白（`rightOffset`），这样 `(-100, 长度+100)` 都能滚到 ✓
   */
  function relaxZoom(h) {
    try {
      h.chart.timeScale().applyOptions({
        minBarSpacing: 0.02,
        rightOffset: 100,
        fixLeftEdge: false,
        fixRightEdge: false,
        lockVisibleTimeRangeOnResize: false
      });
    } catch (err) { /* ignore */ }
  }

  function applyFont(size) {
    var px = Math.max(9, Math.min(28, Number(size) || 13));
    try { document.body.style.setProperty('--desk-sl-font', px + 'px'); }
    catch (err) { /* ignore */ }
  }

  /** 图例色块统一成**圆点**（不管 HTML 由哪个版本的 bundle 生成 ✓） */
  function roundSwatches() {
    if (!document || typeof document.querySelectorAll !== 'function') return;
    var nodes = document.querySelectorAll(
      '#container .legend .series-container > div > *:first-child,'
      + ' #container .legend .legend-swatch');
    for (var i = 0; i < nodes.length; i += 1) {
      var el = nodes[i];
      // ⚠ 只处理"纯色块"：有子元素 / 有文字 / 带 svg 的一律跳过，
      //   否则会把整行（或眼睛/齿轮）压成 10px → 文字和图标重叠 ✗
      if (!el || el.tagName === 'BUTTON' || el.tagName === 'SVG') continue;
      if (el.children && el.children.length) continue;
      if (el.querySelector && el.querySelector('svg')) continue;
      if (String(el.textContent || '').trim()) continue;
      var set = function (name, value) {
        try { el.style.setProperty(name, value, 'important'); }
        catch (err) { el.style[name] = value; }
      };
      set('border-radius', '50%');
      set('width', '10px');
      set('height', '10px');
      set('min-width', '10px');
      set('min-height', '10px');
      set('display', 'inline-block');
      set('vertical-align', 'middle');
      set('border', '0');
      set('box-shadow', 'none');
      set('background-image', 'none');
    }
  }

  function boot() {
    var h = findHandler();
    if (!h) return;
    roundSwatches();
    try {
      if (typeof MutationObserver === 'function' && document.body) {
        new MutationObserver(roundSwatches).observe(
          document.body, { childList: true, subtree: true });
      }
    } catch (err) { /* 无 DOM 的环境（node 测试）忽略 ✓ */ }
    snapshot(h);
    enableCollapse(h);
    relaxZoom(h);
    post();
  }
  // ★ 图例齿轮菜单（参数 / 线型 / 颜色）→ 交给父页面处理 ✓
  //   回调格式：`<callback>_~_<seriesId>;;;kind;;;json`
  function onLegendMenu(event) {
    var raw = String((event && event.detail) || '');
    if (!raw) return;
    var parts = raw.split(';;;');
    if (parts.length < 3) return;
    var head = parts[0].split('_~_');
    var body = { series: head[1] || '', kind: parts[1] || '' };
    try { body.payload = JSON.parse(parts[2] || '{}'); }
    catch (err) { body.payload = {}; }
    try { parent.postMessage({ __deskSL: 'indicatorMenu', data: body }, '*'); }
    catch (err) { /* ignore */ }
  }
  window.addEventListener('pylightcharts-callback', onLegendMenu);
  window.addEventListener('load', boot);
  if (document.readyState === 'complete') boot();
})();
"""


def _inject_driver(html: str, theme_dark: bool = True) -> str:
    """把前端驱动（画线工具 / 图表类型 / 回放 / 图例样式）塞进 HTML ✓

    `theme_dark=False` 时给 `<body>` 加 `desk-sl-light` 类：浅色主题下把图例文字、
    眼睛 / 齿轮描边统一压成深色（默认是给深色背景调的浅灰，浅色下几乎看不见 ✗）
    """
    if 'desk-sl-driver' in html:
        return html
    # ⚠ 老版 pylightcharts 的图例色块是 **`▨` 文字字形**（方块+斜纹），
    #   CSS 改不成圆点 ✗ —— 说明页面内联的是**旧 bundle**（常见原因：
    #   `pylightcharts` 是装进 site-packages 的**副本**，仓库里重新 build 了
    #   JS 却没同步过去）。这里给一条明确提示，省得再靠猜 ✓
    if 'legend-swatch' not in html:
        print('[desk] 警告：回测图内联的 pylightcharts bundle 是旧版'
              '（图例为 ▨ 方块）→ 需要把仓库的 pylightcharts/js 同步到'
              ' site-packages（或改成 editable 安装）')
    script = '<script id="desk-sl-driver">' + DESK_DRIVER_JS + '</script>'
    if not theme_dark:
        html = html.replace('<body>', '<body class="desk-sl-light">', 1)
    # ★ 早期错误钩子：装在**图表脚本之前**，才能抓到它们的报错
    #   （`Value is null` 这种一旦发生，同一批语句后面的图就全没了 ✗）
    hook = ('<script id="desk-sl-errorhook">window.__deskSLErrors=[];'
            'window.addEventListener("error",function(e){'
            'window.__deskSLErrors.push(String(e.message)+" @ "+'
            'String(e.filename||"")+":"+String(e.lineno||0)+":"+'
            'String(e.colno||0));'
            'if(window.__deskSLErrorHook) window.__deskSLErrorHook(e);});</script>')
    html = html.replace('<body>', hook + '<body>', 1)
    if 'desk-sl-errorhook' not in html:
        html = html.replace('<body ', hook + '<body ', 1)
    return html.replace('</body>', DESK_DRIVER_CSS + script + '</body>')


def _inject_separator_css(html: str, theme_dark: bool = True) -> str:
    """主图 / 副图之间的**分隔行**：高度 2px + 深浅主题都看得见的底色 ✓

    以前压成 0 高 + 全透明 → 分隔线完全消失；现在给一条 2px 的浅灰，
    深色 / 浅色主题下都清楚（拖动调整副图高度的热区仍然保留 ✓）
    """
    color = ('rgba(148, 163, 184, .45)' if theme_dark
             else 'rgba(100, 116, 139, .32)')
    style = f"""
<style id="miniqt-pane-separators">
/* LWC 的分隔行：每个 td[colspan="3"] 就是一个 pane separator */
#container tr:has(> td[colspan="3"]),
.tv-lightweight-charts tr:has(> td[colspan="3"]) {{
  height: 2px !important; min-height: 2px !important;
  line-height: 2px !important; overflow: visible !important;
  background: {color} !important;
}}
#container tr > td[colspan="3"],
.tv-lightweight-charts tr > td[colspan="3"] {{
  height: 2px !important; min-height: 2px !important; line-height: 2px !important;
  padding: 0 !important; border: 0 !important;
  overflow: visible !important; background: {color} !important;
}}
</style>
"""
    return html.replace('</head>', style + '</head>')


def build_contract_html(strategy, contract: str, *, theme_dark: bool = True,
                        width: int = 1400, height: int = 900,
                        visible_bars: int = 300) -> str:
    """生成 MiniQT 合约图表 HTML（K 线 + 指标 + 信号 + 交易连线）。"""
    frame, _offset = _prepare_contract_frame(strategy, contract, 0)
    if frame is None:
        raise ValueError(f'{contract} 没有 K 线数据')
    contracts = list(strategy_contracts(strategy))
    try:
        plot_id = contracts.index(contract)
    except ValueError:
        plot_id = 0
    # `toolbox=True` → 图表自带画线工具（默认隐藏，点「画线工具」才显示 ✓）
    chart = HeadlessChart(width=width, height=height, toolbox=True)
    if not theme_dark:
        try:
            chart.theme('light')
        except Exception:                                    # noqa: BLE001
            pass
    chart.set(frame)
    chart.fit()
    _plot_contract_overlays(chart, strategy, contract, frame, plot_id,
                            theme_dark=theme_dark)
    _apply_legend(chart, contract, theme_dark)
    try:
        chart.enable_legend_collapse()      # 指标标签的 ∧ / ∨ N 按钮 ✓
    except Exception:                                        # noqa: BLE001
        pass
    _style_pane_separators(chart, theme_dark)
    _show_tail(chart, len(frame), visible_bars)
    return _inject_driver(_inject_separator_css(
        chart.to_html(title=f'MiniQT · {contract}'), theme_dark), theme_dark)


def build_result_html(strategy, contract: str, *, theme_dark: bool = True,
                      width: int = 1400, height: int = 1100,
                      visible_bars: int = 300) -> str:
    """生成 MiniQT 回测结果页 HTML（合约 K 线 + 信号 / 停止线 + 权益 / 回撤 / 盈亏）。"""
    chart = HeadlessChart(width=width, height=height, toolbox=True)
    if not theme_dark:
        try:
            chart.theme('light')
        except Exception:                                    # noqa: BLE001
            pass
    main, offset = _build_info_contracts(chart, strategy, contract,
                                         theme_dark=theme_dark,
                                         initial_bars=0)
    chart_frame_main = _prepare_contract_frame(strategy, main, 0)[0]         if main is not None else None
    if main is None:
        raise ValueError('没有可用于回测结果页的 K 线数据')
    data = {}
    try:
        data = strategy_backtest_dict(strategy) or {}
    except Exception:                                            # noqa: BLE001
        data = {}
    equity = _chart_time_frame(data.get('equity'), offset)
    drawdown = _chart_time_frame(data.get('drawdown'), offset)
    pnl = _chart_time_frame(data.get('pnl'), offset)
    baseline_color = '#9aa4b2' if theme_dark else '#7b8494'
    page = BacktestPage(
        chart, name='权益',
        baseline_color=baseline_color,
        baseline_width=1)
    page.update(equity, drawdown=drawdown, pnl=pnl)
    try:
        page.equalise()
    except Exception:                                            # noqa: BLE001
        pass
    _apply_legend(chart, main, theme_dark)
    try:
        chart.enable_legend_collapse()      # 指标标签的 ∧ / ∨ N 按钮 ✓
    except Exception:                                        # noqa: BLE001
        pass
    _style_pane_separators(chart, theme_dark)
    total = len(chart_frame_main) if chart_frame_main is not None else 0
    _show_tail(chart, total, visible_bars)
    return _inject_driver(_inject_separator_css(
        chart.to_html(title=f'MiniQT · {main} · 回测结果'), theme_dark),
        theme_dark)
