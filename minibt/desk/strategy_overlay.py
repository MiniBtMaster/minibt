"""把个人 `Strategy` 类"加到图表"（P63）✓

desk 没有实盘/回测引擎，但 `minibt/desk/strategy_runner.py`（P65 从
miniqt 移植过来的那套逻辑，**只依赖 minibt**）能把一个策略**离线跑一遍**并抽出
指标线与买卖信号。这里把结果转成 desk 的 `IndicatorLine` 结构：

* 指标线 → `{key,label,overlay,kind:'line'|'hist',color,data}`
* 买卖信号 → `{kind:'marker', markers:[...]}`

**只依赖 minibt**：不需要安装 miniqt（用户要求 ✓）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

#: `line_style`（minibt）→ Lightweight Charts 的 `LineStyle` 数值
DASH_STYLE = {'solid': 0, 'dotted': 1, 'dashed': 2, 'large_dash': 3}

#: 默认调色（策略没给颜色时轮转 ✓）
COLORS = ('#f6c343', '#2196f3', '#e91e63', '#26a69a', '#9c27b0', '#ff9800')


def _stamps(frame) -> List[int]:
    out: List[int] = []
    for value in frame['datetime'].tolist():
        try:
            out.append(int(value) // 1_000_000_000)
        except (TypeError, ValueError):
            out.append(0)
    return out


def _align_stamps(stamps: List[int], values) -> List[int]:
    """把时间戳数量和指标值对齐（**末尾对齐** ✓）

    指标值通常比 K 线短（前几根 NaN / 预热期），从头配会对不上 ✗。
    """
    if not stamps:
        return stamps
    try:
        count = len(values)
    except TypeError:
        return stamps
    if count <= 0 or count == len(stamps):
        return stamps
    if count < len(stamps):
        return stamps[len(stamps) - count:]
    return stamps


def _series_points(values, stamps: List[int], keep_edges: bool = False) -> List[list]:
    """`pd.Series` → ``[[time, value], …]``；NaN 保留成 ``[time, None]``。

    LWC 的折线遇到**只有 time 没有 value**的点才会断开；以前这里直接丢掉
    NaN，引擎就会把缺口两边连起来（Chandelier_Exit 等指标实测 ✗）。
    """
    out: List[list] = []
    try:
        array = list(values)
    except TypeError:
        return out
    for index, value in enumerate(array):
        if index >= len(stamps):
            break
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = None
        if number is None or number != number:                   # NaN → 空白点
            out.append([stamps[index], None])
            continue
        out.append([stamps[index], number])
    # ★ 去掉**首尾**的空点（策略只回放了一段时，前面成千上万个 NaN 会变成
    #   成千上万个 `value: null` → 前端逐点设色几乎全是透明点 → 整条线画不出来 ✗）
    #   中间的缺口保留（Chandelier_Exit 这类需要断线 ✓）
    #   `keep_edges=True` 用于 stop_price / target_price：它们必须和 K 线
    #   等长，否则按索引取第 3200 根会错位（本地 CCI 停止线测试 ✓）。
    if not keep_edges:
        while out and out[0][1] is None:
            out.pop(0)
        while out and out[-1][1] is None:
            out.pop()
    return out


def _indicator_candidates(strategy) -> List[Any]:
    """找出策略里**带 `signal_text()`** 的指标实例 ✓

    策略常写成 ``self.trix = CMO(self.data)`` —— `_btindicatordataset` 里只有
    `IndFrame`（没有 plotinfo、也调不到 `signal_text`），所以直接遍历策略
    实例的属性即可；再兜一层 dataset 的 `source_obj`。
    """
    out: List[Any] = []
    for value in vars(strategy or {}).values():
        if callable(getattr(value, 'signal_text', None)):
            out.append(value)
        else:
            # 容器里再找一层（`self.inds = [CMO(...)]` / dict ✓）
            if isinstance(value, (list, tuple, dict)):
                items = value.values() if isinstance(value, dict) else value
                for item in items:
                    if callable(getattr(item, 'signal_text', None)):
                        out.append(item)
    datasets = getattr(strategy, '_btindicatordataset', None) or {}
    for dataset in list(datasets.values()):
        for attr in ('indicator_obj', 'source_obj', '_source_obj', 'obj'):
            source = getattr(dataset, attr, None)
            if callable(getattr(source, 'signal_text', None)):
                out.append(source)
                break
    return out


def _dataset_stamps(length: int, strategy) -> List[int]:
    """找一个**长度匹配**的 dataset frame，取其时间戳（纳秒 → 秒 ✓）"""
    datasets = getattr(strategy, '_btindicatordataset', None) or {}
    for dataset in list(datasets.values()):
        frame = getattr(dataset, 'pandas_object', None)
        try:
            column = frame['datetime'].tolist()
        except Exception:                                        # noqa: BLE001
            continue
        if len(column) != length:
            continue
        out: List[int] = []
        for value in column:
            try:
                out.append(int(value) // 1_000_000_000)
            except (TypeError, ValueError):
                out.append(0)
        return out
    return []


def _point_texts_from_signal_text(strategy,
                                  stamps: List[int]) -> Dict[str, Dict[int, str]]:
    """调用指标的 `signal_text()`（`{信号名: 等长文本数组}`）✓

    约定和 `tradingview.AutoChartPatterns.signal_text()` 一致；
    文本长度和图表的 stamps 一致时按下标对，否则按 dataset 自己的时间戳对 ✓
    """
    out: Dict[str, Dict[int, str]] = {}
    for indicator in _indicator_candidates(strategy):
        try:
            payload = indicator.signal_text()
        except Exception:                                        # noqa: BLE001
            continue
        if not isinstance(payload, dict):
            continue
        for name, column in payload.items():
            try:
                values = list(column)
            except TypeError:
                continue
            mapping = out.setdefault(str(name), {})
            same_len = len(values) == len(stamps)
            own = [] if same_len else _dataset_stamps(len(values), strategy)
            for row, value in enumerate(values):
                text = str(value).strip()
                if not text or text.lower() == 'nan':
                    continue
                if same_len:
                    stamp = stamps[row]
                elif row < len(own):
                    stamp = own[row]
                else:
                    continue
                mapping[int(stamp)] = text
    return out


def _point_texts(strategy, stamps: List[int]) -> Dict[str, Dict[int, str]]:
    """`PlotInfo.signal_texts` → `{信号名: {时间戳: 文本}}`（逐点文本 ✓）

    minibt 里它是**和 K 线等长**的 object 数组（没有文字的位置是 NaN）。
    """
    out: Dict[str, Dict[int, str]] = {}
    datasets = getattr(strategy, '_btindicatordataset', None) or {}
    for dataset in list(datasets.values()):
        plotinfo = getattr(dataset, '_plotinfo', None) or             getattr(dataset, 'plotinfo', None)
        if plotinfo is None:
            # `IndFrame` 上没有 plotinfo → 用 source_obj（生成它的指标实例）✓
            for attr in ('source_obj', '_source_obj', 'obj'):
                source = getattr(dataset, attr, None)
                if source is not None:
                    plotinfo = (getattr(source, '_plotinfo', None)
                                or getattr(source, 'plotinfo', None))
                    if plotinfo is not None:
                        break
        raw = getattr(plotinfo, 'signal_texts', None) if plotinfo else None
        if not raw:
            continue
        try:
            items = raw.items() if hasattr(raw, 'items') else []
        except Exception:                                        # noqa: BLE001
            items = []
        for name, column in items:
            try:
                values = list(column)
            except TypeError:
                continue
            mapping = out.setdefault(str(name), {})
            # 文本数组常比图表 K 线长（策略用全量数据算的）→ 按**时间戳**对 ✓
            same_len = len(values) == len(stamps)
            own = [] if same_len else _dataset_stamps(len(values), strategy)
            for row, value in enumerate(values):
                if value is None:
                    continue
                text = str(value).strip()
                if not text or text.lower() == 'nan':
                    continue
                if same_len:
                    mapping[int(stamps[row])] = text
                elif row < len(own):
                    mapping[int(own[row])] = text
    return out


def _signal_items(signals, stamps: List[int], frame,
                  texts: Optional[Dict[str, Dict[int, str]]] = None
                  ) -> List[Dict[str, Any]]:
    """`extract_minibt_signals` → desk 的 marker items ✓"""
    items: List[Dict[str, Any]] = []
    highs = lows = None
    try:
        highs = frame['high'].tolist()
        lows = frame['low'].tolist()
    except Exception:                                            # noqa: BLE001
        highs = lows = None
    for index, signal in enumerate(signals or []):
        try:
            name, values, style, anchor, pane = signal[:5]
        except Exception:                                        # noqa: BLE001
            continue
        # `SignalStyle`（extract_minibt_signals 的第 3 段）：size / marker / 文字
        size = 0
        glyph = ''
        fixed_text = ''
        label_size = 0
        label_color = None
        try:
            size = (int(style.resolved_size('pylightcharts'))
                    if hasattr(style, 'resolved_size')
                    else int(getattr(style, 'size', 0) or 0))
            glyph = str(getattr(style, 'marker', '') or '')
            # 信号的 `Markers.triangle/inverted_triangle` 一直画成**箭头**
            # （和 LWC 原生 arrowUp/arrowDown 一致）；不想改 `Markers` 本身的
            # 三角形语义，所以只在这里映射 ✓
            glyph = {'triangle': 'arrow_up',
                     'triangle_dot': 'arrow_up',
                     'inverted_triangle': 'arrow_down',
                     'arrow_up': 'arrow_up',
                     'arrow_down': 'arrow_down'}.get(glyph, glyph)
            label = getattr(style, 'label', None)
            # `set_label("B", 14)` 存的是 `SignalLabel(text='B', size=14)`
            fixed_text = str(getattr(label, 'text', label) or '')
            label_size = int(getattr(label, 'size', 0) or 0)
            label_color = getattr(label, 'color', None)
        except Exception:                                        # noqa: BLE001
            pass
        markers = []
        try:
            array = list(values)
        except TypeError:
            continue
        for row, value in enumerate(array):
            if row >= len(stamps):
                break
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number != number or number == 0:
                continue
            # ★ 方向优先看**信号名**（`short_signal` 的值也是 +1 → 只按正负
            #   判断会把空头画成多头 ✗）
            low = str(name).lower()
            if any(word in low for word in ('short', 'sell', 'exit')):
                buy = False
            elif any(word in low for word in ('long', 'buy')):
                buy = True
            else:
                buy = number > 0
            price = None
            if highs is not None and lows is not None and row < len(highs):
                price = float(lows[row] if buy else highs[row])
            markers.append({
                'time': stamps[row],
                'position': 'belowBar' if buy else 'aboveBar',
                'shape': 'arrowUp' if buy else 'arrowDown',
                'color': '#26a69a' if buy else '#ef5350',
                # 逐点文本 > `set_label` 固定文字 > 默认 B/S ✓
                'text': ((texts or {}).get(str(name), {}).get(stamps[row])
                         or fixed_text or ('B' if buy else 'S')),
                'price': price,
                'up': buy,          # ★ 方向：多头向上 / 空头向下 ✓
                'size': int(size or 0),
                'glyph': glyph or ('arrow_up' if buy else 'arrow_down'),
                'textSize': label_size,
                'textColor': label_color,
            })
        if not markers:
            continue
        # 自定义序列行（前端有 Handler 时用它画箭头；否则退回 markers ✓）
        try:
            from ..markers import Markers
            shape_rows = Markers.series([
                {'time': item.get('time'), 'price': item.get('price'),
                 'up': bool(item.get('up', True)),   # 多头↑ / 空头↓ ✓
                 'color': item.get('color'),
                 'text': item.get('text') or '',
                 'size': int(item.get('size') or 0),
                 'shape': item.get('glyph'),
                 'textSize': item.get('textSize'),
                 'textColor': item.get('textColor')} for item in markers])
        except Exception:                                        # noqa: BLE001
            shape_rows = []
        items.append({
            'key': f'editor:{name}:signal:{index}',
            'label': str(name),
            'overlay': True,
            'kind': 'marker',
            'pane': 'main',          # 箭头永远在主图 ✓
            'color': '#26a69a',
            'markers': markers,
            'shapeRows': shape_rows,  # 自定义序列（能缩放 / 回放截断 ✓）
            'data': [],
        })
    return items


def run_overlay(frame, cls, symbol: str = '', cycle: int = 60,
                *, live: bool = False, api=None, account=None,
                replay: bool = False,
                replay_bars: Optional[int] = None,
                frames=None, fetch_frame=None) -> Dict[str, Any]:
    """跑一遍策略 → `{'ok', 'items', 'error', 'name'}` ✓

    `fetch_frame(symbol, cycle) -> DataFrame`：实时图表多合约策略按需取
    `get_kline('其它合约')` 的 K 线（策略里没写进 `frames` 时用 ✓）。
    """
    if frame is None or len(frame) == 0:
        return {'ok': False, 'error': '没有 K 线数据（先打开图表）', 'items': []}
    # ★ 用 **minibt 自己**的 runner（P65）：不依赖 miniqt，装 minibt 就能跑 ✓
    from . import strategy_runner as _runner
    from ..utils import Base
    # ★ KLine 初始化时会读全局 Base._is_live_trading / Base._api：
    #   只在 prepare（创建 KLine）期间打开，跑完恢复，避免影响其它回测 ✓
    was_live = Base._is_live_trading
    was_api = Base._api
    if live:
        Base._is_live_trading = True
        Base._api = api
    try:
        runner = _runner.StrategyRunner(
            cls, symbol=symbol, cycle=int(cycle or 60),
            live=live, api=api, account=account,
            fetch_frame=fetch_frame)
        # ★ 多合约：`frames=[(名字, frame), …]`（按格序）→
        #   `self.klines1 / klines2 …` 分别对应格 1 / 格 2 ✓
        seed_frames = list(frames) if frames else [frame]
        runner.prepare(seed_frames, seed_kline=True)
        # ★ 本地图表要把 BtStop 的 stop_price / target_price 也画出来：
        #   必须逐根跑一次 next（止损价是策略边跑边赋值的，不是静态指标）。
        #   实时图表仍只 advance 一次（避免每拍阻塞）；本地策略加到图表时
        #   调用方传 replay=True。
        if replay:
            bars = int(replay_bars or 0) or len(frame)
            ok = runner.replay(frame, bars)
            if not ok:
                ok = runner.advance([frame])
        else:
            # ★ **只算一次**（初始化不必跑几百次 next ✓ 用户要求）：
            #   指标一次性算好；之后每拍由 `desk` 调 `runner.advance()` 增量更新
            # ★ 多合约：必须按**各合约自己的 frame** 推进（以前用 [frame]
            #   会把每条 K 线都覆盖成主图 → 下单下到同一个合约 ✗）
            if frames:
                frame_map = {str(name): item for name, item in seed_frames}
                ok = runner.advance(frame_map)
            else:
                ok = runner.advance([frame])
        if not ok:
            return {'ok': False, 'items': [],
                    'error': f'策略步进失败：{runner.error}'}
    except Exception as error:                                   # noqa: BLE001
        return {'ok': False, 'items': [],
                'error': f'策略运行失败：{type(error).__name__}: {error}'}
    finally:
        Base._is_live_trading = was_live
        Base._api = was_api
    result = collect(runner, frame, cls)
    # 把 runner 交回去：desk 每拍用它 `advance()` 增量更新指标 ✓
    try:
        result['runner'] = runner
    except Exception:                                            # noqa: BLE001
        pass
    return result


def _items_for_plot(runner, plot_id: int, frame, fallback_frame):
    """取第 `plot_id` 条 K 线的指标线 + 信号（多合约里**每条线单独算** ✓）"""
    specs: List[Any] = []
    try:
        specs = list(runner.specs(plot_id))
    except Exception:                                            # noqa: BLE001
        specs = []
    if not specs:
        return []
    plot_frame = None
    try:
        plot_frame = runner.frame(plot_id)
    except Exception:                                            # noqa: BLE001
        plot_frame = None
    if plot_frame is None or len(plot_frame) == 0:
        plot_frame = fallback_frame
    stamps = _stamps(plot_frame)
    if not stamps or not any(stamps):
        # 策略自取数据时 `runner.frame()` 常常没有 `datetime` → 退回图表时间戳
        chart_stamps = _stamps(fallback_frame)
        if chart_stamps and any(chart_stamps):
            stamps = chart_stamps
            plot_frame = fallback_frame
    if not stamps or not any(stamps):
        stamps = _stamps(plot_frame)
    items: List[Dict[str, Any]] = []
    for index, spec in enumerate(specs):
        name = str(getattr(spec, 'name', '') or f'line{index}')
        values = getattr(spec, 'values', None)
        if not isinstance(values, pd.Series):
            continue
        keep_edges = str(name) in ('stop_price', 'target_price')
        points = _series_points(values, _align_stamps(stamps, values),
                                keep_edges=keep_edges)
        if not points:
            continue
        kind = 'hist' if str(getattr(spec, 'kind', 'Line')).lower().startswith(
            'hist') else 'line'
        color = getattr(spec, 'color', None) or COLORS[index % len(COLORS)]
        item = {
            'key': f'editor:{name}:line:{index}',
            'label': name,
            'overlay': bool(getattr(spec, 'overlap', False)),
            'kind': kind,
            # ★ 副图按**指标名**分 pane（以前全是 'strategy' →
            #   多个指标的副图被合并成一张，用户实测 ✗）
            # ★ 按**指标来源**分副图（`spec.source` = 指标 key；同指标的
            #   多条线（MACD 的 dif/dea…）必须共用一张副图，不然会被拆散 ✗）
            'pane': ('strategy' if bool(getattr(spec, 'overlap', False))
                     else 'strategy:' + str(
                         getattr(spec, 'source', '') or name)),
            'color': color,
            'lineWidth': max(1, int(getattr(spec, 'line_width', 2) or 2)),
            'lineStyle': DASH_STYLE.get(
                str(getattr(spec, 'line_style', 'solid') or 'solid'), 0),
            'data': points,
        }
        if kind == 'hist':
            item['base'] = float(getattr(spec, 'vbar_base', 0.0) or 0.0)
            item['upColor'] = getattr(spec, 'up_color', None) or color
            item['downColor'] = getattr(spec, 'down_color', None) or color
        items.append(item)
    try:
        items.extend(_signal_items(
            runner.signals(plot_id), stamps, plot_frame,
            _point_texts(getattr(runner, 'strategy', None), stamps)))
    except Exception:                                            # noqa: BLE001
        pass
    return items


def _apply_plot_routing(runner, groups: Dict[str, List[Dict[str, Any]]]):
    """按 `plot_symbol` / `plot_id` 把指标挪到指定合约的分组 ✓

    * `self.data2.plot_symbol = 'pp2609_60'` → 该指标的列画在 pp2609_60 的图上；
    * `self.data2.plot_id = 0` → 画在第 1 格（= 第 1 条 K 线）的合约上；
    * 两者都没设 → 保持原来的自动判断（不变 ✓）。
    """
    strategy = getattr(runner, 'strategy', None)
    if strategy is None:
        return groups
    routing: Dict[str, str] = {}
    try:
        items = list(vars(strategy).items())
    except Exception:                                            # noqa: BLE001
        return groups
    seeds = list(getattr(runner, '_seed_order', None) or [])
    for _name, obj in items:
        symbol = getattr(obj, 'plot_symbol', None)
        index = getattr(obj, 'plot_id', None)
        columns = []
        try:
            # ⚠ 不能用 `index or []`（pandas 的 Index 布尔判断会抛
            #   `The truth value of a Index is ambiguous`）✗
            raw_columns = getattr(getattr(obj, 'pandas_object', None),
                                  'columns', None)
            if raw_columns is None:
                raw_columns = getattr(obj, 'columns', None)
            if raw_columns is not None:
                columns = [str(col) for col in raw_columns]
        except Exception:                                        # noqa: BLE001
            columns = []
        if not columns:
            continue
        target = ''
        if symbol:
            target = str(symbol)
        elif index is not None and seeds:
            try:
                position = int(index)
            except (TypeError, ValueError):
                position = -1
            if 0 <= position < len(seeds):
                target = str(seeds[position])
        if not target:
            continue
        for column in columns:
            routing[column] = target
    if not routing:
        return groups
    moved: Dict[str, List[Dict[str, Any]]] = {key: [] for key in groups}
    for source, group in groups.items():
        for item in group:
            target = routing.get(str(item.get('label') or ''))
            if target:
                moved.setdefault(target, []).append(item)
            else:
                moved.setdefault(source, []).append(item)
    return {key: value for key, value in moved.items() if value}


def collect(runner, frame, cls) -> Dict[str, Any]:
    """从跑完的 runner 里取指标线 + 信号 → desk items ✓

    ★ **多合约**（配对交易最小用例）：策略里
    ``get_kline(LocalDatas.l2609_60)`` / ``get_kline(LocalDatas.pp2609_60)``
    会各建一条 K 线（plot 1、2…），这里按 **plot → 数据源名字** 分组返回
    ``groups = {源名: [items]}``，desk 再把每组落到对应的图表格上 ✓
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    try:
        count = int(runner.plot_count()) if hasattr(runner, 'plot_count') else 1
    except Exception:                                            # noqa: BLE001
        count = 1
    for plot_id in range(0, max(1, count)):
        items = _items_for_plot(runner, plot_id, frame, frame)
        if not items:
            continue
        try:
            source = str(runner.source_of(plot_id) or '')
        except Exception:                                        # noqa: BLE001
            source = ''
        groups.setdefault(source, []).extend(items)
    # ★ `self.xxx.plot_symbol = 'pp2609_60'` / `self.xxx.plot_id = 0`
    #   → 把该指标的线**挪到指定合约 / 格子**的分组里 ✓
    try:
        groups = _apply_plot_routing(runner, groups)
    except Exception:                                            # noqa: BLE001
        pass
    # 首选「线最多的那组」当主结果（兼容老调用方只读 `items` ✓）
    items: List[Dict[str, Any]] = []
    for source, group in groups.items():
        if len(group) > len(items):
            items = group
    name = getattr(cls, '__name__', 'Strategy')
    if not items:
        return {'ok': False, 'items': [], 'groups': {}, 'name': name,
                'error': f'策略 {name} 没有产生可画的指标线 / 信号'}
    return {'ok': True, 'items': items, 'groups': groups, 'name': name,
            'error': ''}


def classes_of(module) -> Dict[str, Any]:
    """一个模块里的 `Strategy` / `BtIndicator` 类（策略优先 ✓）"""
    from . import personal as _pi

    strategies: List[Any] = []
    indicators: List[Any] = []
    for name in dir(module):
        if name.startswith('_'):
            continue
        obj = getattr(module, name, None)
        if not isinstance(obj, type):
            continue
        if getattr(obj, '__module__', '') != module.__name__:
            continue
        if _pi._is_strategy(obj):
            strategies.append(obj)
        elif _pi._is_bt_indicator(obj):
            indicators.append(obj)
    return {'strategy': strategies, 'indicator': indicators}
