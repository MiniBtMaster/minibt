"""策略回测 / 参数优化的后端会话（minibt desk P118+）。

设计原则：
* **一个策略 = 一个独立账户**；同一策略里的多个 ``get_kline`` 共用一个账户；
* 数据源由策略自己决定（``get_kline(LocalDatas.xxx / 本地 CSV / ...)``）；
* 回测 / 优化在后台线程跑，结果通过 desk 补丁推给前端；
* 前端只负责图表和二级 Tab，不在浏览器里跑 Python。
"""
from __future__ import annotations

import glob
import io
import os
import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

#: 图表最多送多少根（回测可能 8964 根；先送最近 3000 根，结果页仍用全量） ✓
MAX_CHART_BARS = 10000
#: 权益曲线最多送多少点（避免单个补丁过大） ✓
MAX_EQUITY_POINTS = 1800
#: 交易记录最多送多少行 ✓
MAX_TRADES = 5000

#: 策略指标默认颜色
COLORS = ('#f6c343', '#2196f3', '#e91e63', '#ff9800', '#9c27b0',
          '#26a69a', '#ef5350', '#00bcd4')

#: minibt LineDash → LWC LineStyle 数值
DASH_STYLE = {
    'solid': 0, 'dotted': 1, 'dashed': 2, 'large_dashed': 3,
    'large_dash': 3, 'dotdash': 4, 'dashdot': 4,
}


def _num(value, default=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _json_value(value):
    """numpy / pandas 标量 → Python（JSON 安全）✓"""
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _time_list(frame: pd.DataFrame) -> List[int]:
    """DataFrame datetime（可能 tz-aware）→ unix 秒（+8h，和 miniqt 图表一致）✓"""
    if frame is None or 'datetime' not in getattr(frame, 'columns', ()):
        return []
    try:
        times = pd.to_datetime(frame['datetime'], errors='coerce')
        try:
            if getattr(times.dt, 'tz', None) is not None:
                times = times.dt.tz_convert('UTC').dt.tz_localize(None)
        except Exception:                                        # noqa: BLE001
            pass
        values = (times.astype('int64') // 1_000_000_000 + 8 * 3600)
        return [int(item) for item in values.tolist()]
    except Exception:                                            # noqa: BLE001
        return []


def _candle_rows(frame: pd.DataFrame, times: List[int]) -> List[dict]:
    rows = []
    if frame is None or not times:
        return rows
    try:
        records = frame.to_dict('records')
    except Exception:                                            # noqa: BLE001
        return rows
    for index, item in enumerate(records):
        if index >= len(times):
            break
        close = _num(item.get('close'))
        if close is None:
            continue
        rows.append({
            'time': times[index],
            'open': _num(item.get('open')),
            'high': _num(item.get('high')),
            'low': _num(item.get('low')),
            'close': close,
            'volume': _num(item.get('volume'), 0.0),
        })
    return rows


def _downsample(values, limit: int = MAX_EQUITY_POINTS):
    list_values = list(values or [])
    if len(list_values) <= limit:
        return list_values
    step = max(1, len(list_values) // limit)
    out = list_values[::step]
    if out and out[-1] != list_values[-1]:
        out.append(list_values[-1])
    return out


def _trade_rows(strategy, plot_id: int, frame: pd.DataFrame,
                times: List[int], symbol: str) -> tuple[list, list]:
    """从策略的 positions / cum_profits 提取「开/平」交易 + 图表 B/S 标记。"""
    trades: List[dict] = []
    markers: List[dict] = []
    links: List[dict] = []
    try:
        from ..strategy.realtime import extract_trade_lines
        lines = extract_trade_lines(strategy, plot_id, frame, align='tail')
    except Exception:                                            # noqa: BLE001
        lines = []
    if not lines:
        return trades, markers, links
    result = None
    try:
        results = getattr(strategy, '_results', None) or []
        result = results[plot_id] if plot_id < len(results) else None
    except Exception:                                            # noqa: BLE001
        result = None
    for item in lines:
        try:
            entry = int(item.get('entry_index'))
            exit_ = int(item.get('exit_index'))
            side = str(item.get('side') or '')
            entry_price = _num(item.get('entry_price'))
            exit_price = _num(item.get('exit_price'))
            profit = _num(item.get('profit'), 0.0)
            qty = 1.0
            if result is not None:
                try:
                    sizes = result['sizes']
                    qty = abs(float(sizes.iloc[entry]))
                except Exception:                                # noqa: BLE001
                    pass
            if side == 'short':
                entry_label, exit_label = '开空', '平空'
                marker_shape, marker_text = 'arrowDown', 'S'
                marker_position = 'aboveBar'
                color = '#26a69a'
            else:
                entry_label, exit_label = '开多', '平多'
                marker_shape, marker_text = 'arrowUp', 'B'
                marker_position = 'belowBar'
                color = '#ef5350'
            entry_time = times[entry] if 0 <= entry < len(times) else None
            exit_time = times[exit_] if 0 <= exit_ < len(times) else None
            if entry_time is not None:
                trades.append({
                    'time': entry_time, 'time_text': '',
                    'direction': entry_label, 'symbol': symbol,
                    'price': entry_price, 'qty': qty, 'fee': 0.0,
                    'equity': None, 'pnl': None,
                })
                markers.append({
                    'time': entry_time, 'position': marker_position,
                    'shape': marker_shape, 'color': color,
                    'text': marker_text, 'price': entry_price,
                })
            if exit_time is not None:
                trades.append({
                    'time': exit_time, 'time_text': '',
                    'direction': exit_label, 'symbol': symbol,
                    'price': exit_price, 'qty': qty, 'fee': 0.0,
                    'equity': None, 'pnl': profit,
                })
                if entry_time is not None and entry_price is not None                         and exit_price is not None:
                    links.append({
                        'time0': entry_time, 'price0': entry_price,
                        'time1': exit_time, 'price1': exit_price,
                        'side': 'short' if side == 'short' else 'long',
                    })
                markers.append({
                    'time': exit_time, 'position': 'aboveBar'
                    if marker_position == 'belowBar' else 'belowBar',
                    'shape': 'circle', 'color': '#787b86',
                    'text': 'X', 'price': exit_price,
                })
        except Exception:                                        # noqa: BLE001
            continue
    trades.sort(key=lambda row: row['time'])
    markers.sort(key=lambda row: row['time'])
    links.sort(key=lambda row: row['time0'])
    return trades, markers, links


def _indicator_items(strategy, plot_id: int, frame: pd.DataFrame,
                     times: List[int], include_signals: bool = True) -> List[dict]:
    """策略的 `_btindicatordataset` → desk `IndicatorLine` 结构。"""
    def as_list(value):
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    items: List[dict] = []
    dataset = getattr(strategy, '_btindicatordataset', None) or {}
    if not dataset or not times:
        return items
    for key, indicator in dataset.items():
        try:
            data = indicator._get_plot_datas(key)
        except Exception:                                        # noqa: BLE001
            continue
        if not data or len(data) < 13:
            continue
        target_plot = int(data[0])
        if target_plot != int(plot_id):
            continue
        isplot = as_list(data[1])
        sname = as_list(data[2])
        display_lines = as_list(data[3])
        raw_lines = as_list(data[4])
        overlaps = as_list(data[6])
        arrays = as_list(data[8])
        plotinfo = data[10] if isinstance(data[10], dict) else {}
        signalstyles = data[12] if isinstance(data[12], dict) else {}
        signallines = set(str(item) for item in
                          (plotinfo.get('signallines') or []))
        linestyle = plotinfo.get('linestyle') or {}
        for pane in range(min(len(arrays), len(raw_lines))):
            values = arrays[pane]
            try:
                array = np.asarray(values.pandas_object
                                   if hasattr(values, 'pandas_object')
                                   else values, dtype=float)
            except Exception:                                    # noqa: BLE001
                try:
                    array = np.asarray(values, dtype=float)
                except Exception:                                # noqa: BLE001
                    continue
            if array.ndim == 1:
                array = array.reshape(-1, 1)
            columns = as_list(raw_lines[pane]) if pane < len(raw_lines) else []
            shown = as_list(display_lines[pane]) if pane < len(display_lines)                 else list(columns)
            pane_name = str(sname[pane] if pane < len(sname)
                            else sname[0] if sname else 'strategy')
            overlay = bool(overlaps[pane]) if pane < len(overlaps) else False
            pane_plot = as_list(isplot[pane]) if pane < len(isplot) else []
            pane_key = f'st:{pane_name}:{pane}'
            for column_index, column in enumerate(columns):
                if column_index >= array.shape[1]:
                    break
                column_name = str(column)
                label = str(shown[column_index]
                            if column_index < len(shown) else column_name)
                series = array[:, column_index]
                style = linestyle.get(column_name) or {}
                should_plot = True
                if pane_plot:
                    if len(pane_plot) > 1:
                        should_plot = bool(pane_plot[column_index])                             if column_index < len(pane_plot) else True
                    else:
                        should_plot = bool(pane_plot[0])
                if not should_plot:
                    continue
                if column_name in signallines or column_name in signalstyles:
                    if not include_signals:
                        continue
                    markers = []
                    signal_style = signalstyles.get(column_name) or {}
                    buy = str(signal_style.get('key') or 'low') == 'low'
                    color = signal_style.get('color') or (
                        '#26a69a' if buy else '#ef5350')
                    for row_index, value in enumerate(series):
                        if row_index >= len(times) or not np.isfinite(value) or value == 0:
                            continue
                        markers.append({
                            'time': times[row_index],
                            'position': 'belowBar' if buy else 'aboveBar',
                            'shape': 'arrowUp' if buy else 'arrowDown',
                            'color': color, 'text': 'B' if buy else 'S',
                            'price': None,
                        })
                    if markers:
                        items.append({
                            'key': f'{pane_key}:signal:{column_name}',
                            'label': label, 'overlay': True,
                            'kind': 'marker', 'pane': pane_key,
                            'color': color, 'markers': markers, 'data': [],
                        })
                    continue
                points = []
                for row, value in enumerate(series):
                    if row >= len(times) or not np.isfinite(value):
                        continue
                    points.append([times[row], float(value)])
                if not points:
                    continue
                color = style.get('line_color') or COLORS[
                    len(items) % len(COLORS)]
                dash = str(style.get('line_dash') or 'solid').lower()
                line_style = DASH_STYLE.get(dash, 0)
                if ('stop' in pane_name.lower()
                        or column_name in ('stop_price', 'target_price')
                        or 'stop' in column_name.lower()
                        or 'target' in column_name.lower()):
                    line_style = 2            # 停止线固定虚线 ✓
                items.append({
                    'key': f'{pane_key}:{column_index}:{column_name}',
                    'label': label, 'overlay': overlay, 'kind': 'line',
                    'pane': pane_key, 'color': color,
                    'lineWidth': max(1, int(round(float(
                        style.get('line_width') or 1.3)))),
                    'lineStyle': line_style,
                    'data': points,
                })
    return items


def _metrics_payload(strategy) -> dict:
    try:
        metrics = strategy._compute_backtest_metrics()
    except Exception:                                            # noqa: BLE001
        metrics = None
    if not metrics:
        return {
            'profit': 0.0, 'return_pct': 0.0, 'total_fee': 0.0,
            'payoff_ratio': 0.0, 'avg_return': 0.0, 'avg_win': 0.0,
            'avg_loss': 0.0, 'sharpe': 0.0, 'drawdown': 0.0,
            'var': 0.0, 'risk_return': 0.0, 'winrate': 0.0,
            'wins': 0, 'losses': 0, 'profit_ratio': 0.0,
            'trades': 0,
        }
    return {
        'profit': _num(metrics.get('final_return'), 0.0),
        'return_pct': _num(metrics.get('compounded'), 0.0),
        'total_fee': _num(metrics.get('commission'), 0.0),
        'payoff_ratio': _num(metrics.get('profit_factor'), 0.0),
        'avg_return': _num(metrics.get('avg_return'), 0.0),
        'avg_win': _num(metrics.get('avg_win'), 0.0),
        'avg_loss': _num(metrics.get('avg_loss'), 0.0),
        'sharpe': _num(metrics.get('sharpe'), 0.0),
        'drawdown': _num(metrics.get('max_drawdown'), 0.0),
        'var': _num(metrics.get('value_at_risk'), 0.0),
        'risk_return': _num(metrics.get('risk_return_ratio'), 0.0),
        'winrate': _num(metrics.get('win_rate'), 0.0),
        'wins': int(metrics.get('wins') or 0),
        'losses': int(metrics.get('losses') or 0),
        'profit_ratio': _num(metrics.get('profit_ratio'), 0.0),
        'trades': int(metrics.get('trade_count') or 0),
    }


def _equity_payload(strategy):
    values = []
    times = []
    try:
        profits = getattr(strategy, 'profits', None)
        if profits is not None:
            values = [_num(item, 0.0) for item in list(profits.values)]
            try:
                index = pd.to_datetime(profits.index)
                times = [int(item) for item in
                         (index.astype('int64') // 1_000_000_000).tolist()]
            except Exception:                                    # noqa: BLE001
                times = list(range(len(values)))
    except Exception:                                            # noqa: BLE001
        pass
    values = _downsample(values)
    if len(times) > len(values):
        step = max(1, len(times) // max(1, len(values)))
        times = times[::step][:len(values)]
    drawdown = []
    if values:
        peak = np.maximum.accumulate(np.asarray(values, dtype=float))
        drawdown = [float((value - high) / high) if high else 0.0
                    for value, high in zip(values, peak)]
    return {'times': times, 'values': values, 'drawdown': drawdown}


class StrategyLab:
    """一个策略实验室会话（回测 / 优化）。"""

    def __init__(self, desk, session_id: str):
        self.desk = desk
        self.id = session_id
        self.file = ''
        self.mode = 'backtest'
        self.status = 'idle'
        self.strategies: List[dict] = []
        self.selected_strategy = ''
        self.selected_contract = ''
        self.optimization_rows: List[dict] = []
        self._opt_key = ''
        #: 本次优化开始时间；只收集这次新写出的 CSV（避免旧结果假装新结果 ✗）
        self._opt_started = 0.0
        #: 用户通过「优化目标」选的 1~3 个 OPTTargetType（空 = 用策略 op_config）
        self.targets: List[str] = []
        self.weights: List[float] = []
        self.params: Dict[str, Any] = {}
        self.progress_current = 0
        self.progress_total = 0
        self._thread: Optional[threading.Thread] = None
        self._stop = False
        self.error = ''
        #: 回测后的**策略实例**（MiniQT 图表直接复用它的原始数据）
        self._instances: List[Any] = []
        #: 生成的 MiniQT 图表 HTML（key + theme -> html）✓
        self._html_cache: Dict[tuple, str] = {}
        #: Qt 壳（file://）下 iframe 需要**真实文件路径**，不能走 /strategy_chart ✓
        self._html_files: Dict[tuple, str] = {}

    # ------------------------------------------------------------ 启动
    def start(self, payload: dict) -> None:
        self.file = str((payload or {}).get('file') or '')
        self.mode = 'optimize' if str(
            (payload or {}).get('mode') or '') == 'optimize' else 'backtest'
        if not self.file or not os.path.isfile(self.file):
            self._error('策略文件不存在')
            return
        if self._thread is not None and self._thread.is_alive():
            self._error('已有回测正在运行')
            return
        self.params = dict((payload or {}).get('params') or {})
        if self.mode == 'optimize':
            override = ((payload or {}).get('metrics')
                        or (payload or {}).get('targets'))
            if override:
                from .research import normalize_metrics
                self.targets = normalize_metrics(override)
            elif 'metrics' in (payload or {}) or 'targets' in (payload or {}):
                self.targets = []
            raw_weights = (payload or {}).get('weights')
            if isinstance(raw_weights, (list, tuple)) and raw_weights:
                self.weights = [float(item) for item in raw_weights
                                if float(item or 0) != 0]
                if len(self.weights) != len(self.targets):
                    self.weights = []
            elif not self.targets:
                self.weights = []
            if self.targets and not self.weights:
                from .research import metric_direction
                self.weights = [float(metric_direction(name))
                                for name in self.targets]
        self._instances = []
        self._html_cache.clear()
        self._html_files.clear()
        self.status = 'running'
        self.error = ''
        self._stop = False
        self._push_progress(0, 0, '准备中…')
        self._push_state()
        self._thread = threading.Thread(
            target=self._run, name=f'desk-strategy-{self.id}', daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._stop = True

    def _log(self, text: str) -> None:
        if self._stop:
            return
        self.desk.push({'type': 'strategy_log', 'id': self.id,
                        'line': str(text)})

    def _push_progress(self, current: int, total: int,
                       text: str = '') -> None:
        self.progress_current = int(current)
        self.progress_total = int(total)
        self.desk.push({
            'type': 'strategy_progress', 'id': self.id,
            'current': self.progress_current,
            'total': self.progress_total,
            'text': str(text or ''),
        })

    def _error(self, message: str) -> None:
        self.status = 'error'
        self.error = str(message)
        self.desk.push({'type': 'strategy_error', 'id': self.id,
                        'message': str(message)})
        self._push_state()

    def _push_state(self) -> None:
        targets = list(self.targets)
        try:
            from .research import TARGET_METRICS
            options = list(TARGET_METRICS)
        except Exception:                                        # noqa: BLE001
            options = []
        self.desk.push({
            'type': 'strategy_state', 'id': self.id, 'file': self.file,
            'mode': self.mode, 'status': self.status,
            'targets': targets,
            'weights': list(self.weights),
            'target_options': options,
            'strategies': [{
                'name': item.get('name'),
                'contracts': [row.get('contract') or row.get('symbol')
                              for row in (item.get('contracts') or [])],
                'metrics': item.get('metrics', {}),
            } for item in self.strategies],
            'selected': {
                'strategy': self.selected_strategy,
                'contract': self.selected_contract,
            },
            'error': self.error,
        })

    # ------------------------------------------------------------ 回测
    def _run_indicator(self) -> bool:
        """指标信号回测 / 优化（`BtIndicator` + `signal_backtest`）✓

        参考 miniqt 的 `_SignalOptimizationWorker`：
        * 回测 → `ind.signal_backtest(size=1, isplot=False, isreport=False)`
        * 优化 → `ind.signal_backtest(optimize=OptimizeConfig(...))`，
          取 `result.result`（也是 Strategy 实例）作为"最优参数回测"
        两条路径产出的对象都塞进 `self._instances`，后面渲染完全复用 ✓
        """
        import importlib.util
        from .. import BtIndicator, LocalDatas
        try:
            spec = importlib.util.spec_from_file_location(
                f'desk_lab_{self.id}', self.file)
            if spec is None or spec.loader is None:
                return False
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as error:                               # noqa: BLE001
            self._log(f'[指标] 导入失败：{error!r}')
            return False
        signals = {'long_signal', 'short_signal',
                   'exitlong_signal', 'exitshort_signal'}
        classes = []
        for name in dir(module):
            obj = getattr(module, name, None)
            if not (isinstance(obj, type) and issubclass(obj, BtIndicator)):
                continue
            if obj is BtIndicator:
                continue
            candidates = set(dir(obj)) | set(getattr(obj, 'lines', []) or [])
            if candidates & signals:
                classes.append(obj)
        if not classes:
            return False
        cls = classes[0]
        cls_name = getattr(cls, '__name__', 'Indicator')
        self._log(f'[指标] 指标信号模式：{cls_name}')
        kline = getattr(cls, 'data', None)
        try:
            # ⚠ KLine 的 `__bool__` 是 ambiguous，不能用 `or` ✗
            kline = getattr(kline, 'kline', None)
            if kline is None:
                kline = LocalDatas.test.kline
        except Exception as error:                               # noqa: BLE001
            self._log(f'[指标] 数据准备失败：{error!r}')
            return False
        # ★ 配对指标：类里写 `pair_klines = (腿A, 腿B)` → 用 pair_backtest ✓
        pair_raw = getattr(cls, 'pair_klines', None)
        pair_kwargs = dict(getattr(cls, 'pair_backtest_kwargs', {}) or {})
        pair_ready = False
        if isinstance(pair_raw, (list, tuple)) and len(pair_raw) >= 2:
            try:
                leg_a = getattr(pair_raw[0], 'kline', None)
                if leg_a is None:
                    leg_a = pair_raw[0]
                leg_b = getattr(pair_raw[1], 'kline', None)
                if leg_b is None:
                    leg_b = pair_raw[1]
                if leg_a is not None and leg_b is not None:
                    from .. import CommissionType
                    count = min(len(leg_a), len(leg_b))
                    prices = pair_kwargs.get('prices')
                    if prices is None:
                        prices = np.column_stack([
                            np.asarray(leg_a.close.values)[:count],
                            np.asarray(leg_b.close.values)[:count]])
                    pair_kwargs.setdefault('kline_a', leg_a)
                    pair_kwargs.setdefault('kline_b', leg_b)
                    pair_kwargs.setdefault('prices', prices)
                    pair_kwargs.setdefault('size', 1)
                    pair_kwargs.setdefault('commission', (1.0, 1.0))
                    pair_kwargs.setdefault('com_type', CommissionType.Fixed)
                    pair_kwargs.setdefault('margin_rate', (0.05, 0.05))
                    pair_kwargs.setdefault('leg_size_ratio', 1.0)
                    pair_kwargs.pop('optimize', None)
                    pair_kwargs.pop('isplot', None)
                    pair_kwargs.pop('isreport', None)
                    pair_ready = True
            except Exception as error:                       # noqa: BLE001
                self._log(f'[指标] 配对数据准备失败：{error!r}')
                pair_ready = False
        try:
            indicator = cls(kline)
        except Exception as error:                               # noqa: BLE001
            self._error(f'指标实例化失败：{error}')
            return False
        try:
            if self.mode == 'optimize':
                from dataclasses import replace
                from .. import OptimizeConfig
                config = getattr(cls, 'op_config', None)
                if not isinstance(config, OptimizeConfig):
                    config = self._indicator_config(cls)
                if config is None:
                    self._error('指标里没有 op_config，也没有可优化的参数')
                    return True
                # ★ 指标优化也要推进度：OptimizeConfig.config 支持 callbacks ✓
                total = 0
                try:
                    if str(config.method) == 'optuna':
                        raw = dict(config.config or {})
                        total = int(raw.get('n_trials') or 0)
                        if total:
                            callbacks = list(raw.get('callbacks') or [])

                            def _ind_callback(study, trial):
                                if self._stop:
                                    try:
                                        study.stop()
                                    except Exception:        # noqa: BLE001
                                        pass
                                self._push_progress(
                                    int(getattr(trial, 'number', 0)) + 1,
                                    total, '参数优化中…')
                            callbacks.append(_ind_callback)
                            raw['callbacks'] = callbacks
                            config = replace(config, config=raw)
                            self._push_progress(0, total, '参数优化中…')
                except Exception:                            # noqa: BLE001
                    total = 0
                if pair_ready:
                    result = indicator.pair_backtest(
                        isplot=False, isreport=False,
                        optimize=config, **pair_kwargs)
                else:
                    result = indicator.signal_backtest(
                        size=1, isplot=False, isreport=False, optimize=config)
                if total and not self._stop:
                    self._push_progress(total, total, '参数优化完成')
            else:
                if pair_ready:
                    result = indicator.pair_backtest(
                        isplot=False, isreport=False, **pair_kwargs)
                else:
                    result = indicator.signal_backtest(
                        size=1, isplot=False, isreport=False)
        except Exception as error:                               # noqa: BLE001
            self._error(f'指标信号回测失败：{error}')
            return True
        if self._stop:
            self._log('[指标] 已取消')
            self.status = 'cancelled'
            self._push_state()
            return True
        # ⚠ 不能用 `a or b`：回测时 `result.result` 是 **DataFrame**，
        #   `bool(DataFrame)` 会抛 "truth value is ambiguous" ✗
        #   回测 → `result` 本身就是 Strategy；优化 → `result.result` 才是 ✓
        instance = result
        if not hasattr(instance, '_btindicatordataset'):
            inner = getattr(result, 'result', None)
            if inner is not None and hasattr(inner, '_btindicatordataset'):
                instance = inner
        if not hasattr(instance, '_btindicatordataset'):
            self._error('指标信号回测没有产出可绘制的实例')
            return True
        self._instances = [instance]
        contracts = []
        try:
            from ..strategy.realtime import strategy_contracts
            contracts = [str(item) for item in
                         (strategy_contracts(instance) or [])]
        except Exception:                                        # noqa: BLE001
            contracts = []
        if not contracts:
            name = ''
            for attr in ('symbol', 'contract', 'name'):
                name = str(getattr(instance, attr, '') or '')
                if name:
                    break
            contracts = [name or 'LOCAL_TEST']
        try:
            # ★ 必须走 `_extract()`：指标 / 记录页的「回测结果 / 权益回撤 /
            #   分合约结果 / 交易记录」全靠它填（以前只塞了个空壳 → 页面有
            #   框架但一条数据都没有 ✗）
            extracted = self._extract(instance) or {}
            extracted['name'] = cls_name
            if not extracted.get('contracts') and contracts:
                extracted['contracts'] = [{'contract': item, 'symbol': item}
                                          for item in contracts]
            self.strategies = [extracted]
            self.selected_strategy = cls_name
            self.selected_contract = contracts[0] if contracts else ''
        except Exception as error:                               # noqa: BLE001
            self._log(f'[指标] 提取回测数据失败：{error!r}')
            self.strategies = [{
                'name': cls_name,
                'contracts': [{'contract': item} for item in contracts],
                'metrics': {},
            }]
        self.status = 'ready'
        if self.mode == 'optimize':
            self.optimization_rows = self._indicator_opt_rows(result) or []
            if self.optimization_rows:
                self.desk.push({'type': 'strategy_opt', 'id': self.id,
                                'rows': self.optimization_rows})
        self._log(f'[指标] 完成：{cls_name}')
        self._push_state()
        self._push_selected()
        return True

    def _indicator_opt_rows(self, result) -> List[dict]:
        """`OptimizationResult` → 优化页的表格行（尝试几种常见出口 ✓）"""
        frame = None
        for attr in ('result_df', 'to_dataframe', 'df', 'dataframe'):
            value = getattr(result, attr, None)
            try:
                frame = value() if callable(value) else value
            except Exception:                                    # noqa: BLE001
                frame = None
            if frame is not None and hasattr(frame, 'to_dict'):
                break
            frame = None
        if frame is None:
            return []
        rows: List[dict] = []
        try:
            for item in frame.head(500).to_dict(orient='records'):
                rows.append({str(key): _json_value(value)
                             for key, value in dict(item).items()})
        except Exception:                                        # noqa: BLE001
            return []
        return rows

    def _indicator_config(self, cls):
        """指标没写 `op_config` 时，用 `params` 里的数值**生成网格** ✓"""
        try:
            from .. import OptimizeConfig
        except Exception:                                        # noqa: BLE001
            return None
        params = dict(getattr(cls, 'params', {}) or {})
        space = {}
        for key, value in params.items():
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if isinstance(value, bool) or number != int(number):
                continue
            base = int(number)
            low = max(1, int(base * 0.5))
            high = max(low + 2, int(base * 1.5))
            space[str(key)] = (low, high, max(1, (high - low) // 4))
        if not space:
            return None
        return OptimizeConfig(params=space, target='sharpe',
                              method='grid', n_jobs=2)

    def _run(self) -> None:
        import sys
        from ..bt import Bt
        started = time.time()
        self._log(f'[策略] 开始{"参数优化" if self.mode == "optimize" else "回测"}：{self.file}')
        old_out, old_err = sys.stdout, sys.stderr
        capture = io.StringIO()
        try:
            bt = Bt(auto=False)
            bt.addstrategy(self.file)
            if not bt.strategies:
                # ★ 没有 Strategy → 试试**指标信号**模式（和 miniqt 一致：
                #   `ind.signal_backtest(...)` 返回的 `SignalIndicatorStrategy`
                #   本身就是 Strategy 子类，出图 / 交易记录链路直接复用 ✓）
                if self._run_indicator():
                    return
                self._error('文件里没有找到 Strategy 子类')
                return
            for cls in bt.strategies:
                try:
                    cls._light_chart = False
                except Exception:                                # noqa: BLE001
                    pass
            if self.params:
                for cls in bt.strategies:
                    try:
                        base = dict(getattr(cls, 'params', {}) or {})
                        base.update(self.params)
                        cls.params = base
                        if getattr(cls, 'op_config', None):
                            cls.op_config = None
                    except Exception:                            # noqa: BLE001
                        pass
                self._log(f'[策略] 使用指定参数：{self.params}')
            self._log(f'[策略] 找到 {len(bt.strategies)} 个策略：'
                      + ', '.join(item.__name__ for item in bt.strategies))
            sys.stdout = capture
            sys.stderr = capture
            try:
                self._run_with_cancel(bt)
            finally:
                sys.stdout, sys.stderr = old_out, old_err
            self._consume_capture(capture)
            if self._stop:
                self._log('[策略] 已取消')
                self.status = 'cancelled'
                self._push_state()
                return
            instances = []
            for instance in getattr(bt, 'strategies', []) or []:
                try:
                    if getattr(instance, 'profits', None) is not None:
                        instances.append(instance)
                except Exception:                                # noqa: BLE001
                    continue
            if not instances:
                self._error('所有策略都没有产生回测结果')
                return
            self._instances = list(instances)
            self.strategies = [self._extract(item) for item in instances]
            if self.mode == 'optimize':
                self._collect_optimization(bt)
            self.status = 'ready'
            self.selected_strategy = self.strategies[0]['name']
            contracts = self.strategies[0].get('contracts') or []
            self.selected_contract = (
                contracts[0].get('contract') or contracts[0].get('symbol')
            ) if contracts else ''
            self._log(f'[策略] 完成：{len(self.strategies)} 个策略，'
                      f'{time.time() - started:.1f}s')
            self._push_state()
            self._push_selected()
        except Exception as error:                               # noqa: BLE001
            import traceback
            self._log(traceback.format_exc())
            self._error(f'{type(error).__name__}: {error}')
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def _run_with_cancel(self, bt) -> None:
        """给本次回测的 Strategy 类装 `_cancel_check`，跑完恢复 ✓

        `Bt.run()` 自己会创建实例；在类上挂 `staticmethod(lambda: _stop)`，
        实例继承后由 `_execute_core_trading_loop()` 每根 bar 检查。
        优化模式也共用；Optuna 自己的 callback 仍会 `study.stop()`。
        """
        classes = list(getattr(bt, 'strategies', []) or [])
        old = {cls: ('_cancel_check' in cls.__dict__,
                     cls.__dict__.get('_cancel_check')) for cls in classes}
        for cls in classes:
            try:
                setattr(cls, '_cancel_check',
                        staticmethod(lambda: self._stop))
            except Exception:                                    # noqa: BLE001
                pass
        try:
            if self.mode == 'optimize':
                self._run_optimize(bt)
            else:
                bt.run(isplot=False, close_api=False, model='sequential')
        finally:
            for cls, (defined, value) in old.items():
                try:
                    if defined:
                        setattr(cls, '_cancel_check', value)
                    elif '_cancel_check' in cls.__dict__:
                        delattr(cls, '_cancel_check')
                except Exception:                                # noqa: BLE001
                    pass

    def _consume_capture(self, capture: io.StringIO) -> None:
        for line in capture.getvalue().splitlines():
            if line.strip():
                self._log(line.rstrip())

    def _optuna_callback(self, total: int):
        """Optuna 每个 trial 后推进度；取消时 `study.stop()` ✓"""
        def callback(study, trial):
            if self._stop:
                try:
                    study.stop()
                except Exception:                            # noqa: BLE001
                    pass
            self._push_progress(
                int(getattr(trial, 'number', 0)) + 1, total)
        return callback

    def _run_optimize(self, bt) -> None:
        """参数优化：走 minibt 的 optstrategy（策略需声明 op_config）。"""
        cls = next((item for item in bt.strategies
                    if getattr(item, 'op_config', None)), None)
        if cls is None:
            self._log('[优化] 没有 op_config，回退为普通回测')
            bt.run(isplot=False, close_api=False, model='sequential')
            return
        cfg = cls.op_config
        params = cfg.get('params') or {}
        target = cfg.get('target') or 'profit_ratio'
        if self.targets:
            target = list(self.targets)
            weights = list(self.weights) or [1.0] * len(target)
            weights_value: Any = (weights[0] if len(weights) == 1
                                  else tuple(weights))
        else:
            weights_value = cfg.get('weights', 1.)
            if isinstance(target, str):
                target = [target]
            else:
                target = list(target)
            self.targets = list(target)
            from .research import metric_direction
            if isinstance(weights_value, (list, tuple)):
                self.weights = [float(item) for item in weights_value]
            else:
                self.weights = [float(metric_direction(name))
                                for name in target]
        raw = cfg.get('opconfig') or {}
        first_target = target[0] if target else 'profit_ratio'
        self._opt_key = f'opt_{cls.__name__}_{first_target}'
        total = 0
        try:
            if isinstance(raw, (list, tuple)) and raw:
                optimize_kwargs = dict(raw[0] or {})
                study_kwargs = dict(raw[1] or {}) if len(raw) > 1 else {}
                total = int(optimize_kwargs.get('n_trials') or 0)
                callbacks = list(optimize_kwargs.get('callbacks') or [])
                callbacks.append(self._optuna_callback(total))
                optimize_kwargs['callbacks'] = callbacks
                raw = (optimize_kwargs, study_kwargs)
            elif isinstance(raw, dict):
                optimize_kwargs = dict(raw)
                study_kwargs: Dict[str, Any] = {}
                total = int(optimize_kwargs.get('n_trials') or 0)
                callbacks = list(optimize_kwargs.get('callbacks') or [])
                callbacks.append(self._optuna_callback(total))
                optimize_kwargs['callbacks'] = callbacks
                # ★ minibt 的 optuna 只认 `(optimize_kwargs, study_kwargs)`
                #   元组；以前传 dict 会被它忽略 → 默认 100 trials、无 callback
                #   → 优化页没有进度（用户实测 ✗）
                raw = (optimize_kwargs, study_kwargs)
        except Exception:                                        # noqa: BLE001
            total = 0
        self._push_progress(0, total, '参数优化中…')
        self._opt_started = time.time()
        bt.optstrategy(target, weights_value,
                       opconfig=raw, op_method=cfg.get('op_method', 'optuna'),
                       show_bar=False, **params)
        bt.run(isplot=False, close_api=False, model='sequential')
        if not self._stop:
            self._push_progress(total, total, '参数优化完成')

    def _collect_optimization(self, bt) -> None:
        """从 minibt 的 op_params CSV 收集 trial 表（参数优化 Tab）✓"""
        self.optimization_rows = []
        try:
            path = getattr(bt, '_Bt__op_path', '') or ''
            if not path:
                import minibt as _pkg
                path = os.path.join(os.path.dirname(_pkg.__file__), 'op_params')
            pattern = os.path.join(path, f'{self._opt_key}*.csv')
            files = sorted(glob.glob(pattern), key=os.path.getmtime,
                           reverse=True)
            # 只要**本次**优化写出的文件；旧 CSV 不能冒充新结果 ✗
            if self._opt_started:
                files = [path for path in files
                         if os.path.getmtime(path) >= self._opt_started - 1.0]
            if files:
                import csv
                with open(files[0], encoding='utf-8-sig') as handle:
                    self.optimization_rows = list(csv.DictReader(handle))
                # ★ 单目标 Optuna CSV 是 `value`，多目标是 `values_0/values_1`；
                #   前端图表统一按 `values_*` 读 → 这里把单目标规范化 ✓
                if (self.optimization_rows
                        and 'value' in self.optimization_rows[0]
                        and 'values_0' not in self.optimization_rows[0]):
                    for row in self.optimization_rows:
                        if 'value' in row:
                            row['values_0'] = row.pop('value')
                self._log(f'[优化] 收集 {len(self.optimization_rows)} 条 trial')
        except Exception as error:                               # noqa: BLE001
            self._log(f'[优化] 读取 trial 失败：{error!r}')

    # ------------------------------------------------------------ 提取
    def _extract(self, strategy) -> dict:
        name = strategy.__class__.__name__
        metrics = _metrics_payload(strategy)
        equity = _equity_payload(strategy)
        contracts = []
        dataset = getattr(strategy, '_btklinedataset', None) or {}
        for index, (key, kline) in enumerate(dataset.items()):
            frame = getattr(kline, 'pandas_object', None)
            if frame is None or getattr(frame, 'empty', True):
                continue
            if 'symbol' in frame.columns and len(frame):
                symbol = str(frame['symbol'].iloc[0])
            else:
                symbol = str(getattr(kline, 'symbol', '') or key)
            contract_key = (f'{getattr(kline, "symbol", "")}_'
                            f'{getattr(kline, "cycle", "")}')
            times = _time_list(frame)
            bars = _candle_rows(frame, times)
            trades, markers, links = _trade_rows(
                strategy, index, frame, times, symbol)
            all_items = _indicator_items(strategy, index, frame, times,
                                          include_signals=True)
            indicators = [item for item in all_items
                          if item.get('kind') != 'marker']
            signals = [item for item in all_items
                       if item.get('kind') == 'marker']
            contracts.append({
                'symbol': symbol,
                #: MiniQT 的合约键：``{symbol}_{cycle}``（图表 / 顶栏都用它）
                'contract': contract_key,
                'bars': bars,
                'indicators': indicators,
                'signals': signals,
                'markers': markers,
                'links': links[:MAX_TRADES],
                'trades': trades[:MAX_TRADES],
                'trade_count': len(trades),
            })
        trade_style = {'show': True, 'color': '#f6c343',
                       'width': 2, 'dash': 'dashed'}
        try:
            from ..utils import resolve_tradestyle
            style = resolve_tradestyle(strategy)
            trade_style = {
                'show': bool(getattr(style, 'show', True)),
                'color': str(getattr(getattr(style, 'line_color', None),
                                     'value', None)
                             or getattr(style, 'line_color', '')
                             or '#f6c343'),
                'width': max(1, int(round(float(
                    getattr(style, 'line_width', 2) or 2)))),
                'dash': str(getattr(style, 'line_dash', 'dashed') or 'dashed'),
            }
        except Exception:                                        # noqa: BLE001
            pass
        pnl = []
        for contract in contracts:
            for row in contract.get('trades') or []:
                if row.get('pnl') is not None and row.get('time'):
                    pnl.append([row['time'], row['pnl']])
        pnl.sort(key=lambda item: item[0])
        return {
            'name': name,
            'metrics': metrics,
            'equity': equity,
            'pnl': pnl,
            'trade_style': trade_style,
            'contracts': contracts,
        }

    # ------------------------------------------------------------ 选择 / 下发
    def select(self, payload: dict) -> None:
        strategy = str((payload or {}).get('strategy') or '')
        contract = str((payload or {}).get('contract') or '')
        if strategy:
            self.selected_strategy = strategy
        if contract:
            self.selected_contract = contract
        self._push_selected()

    def indicator_params(self, payload: dict) -> None:
        """图例齿轮「参数」确认 → **重算该指标并重建图表** ✓

        回测图是静态 HTML（MiniQT 代码生成），页面里没法重算指标，
        所以由这里按新参数重跑 `indicator_menu.recompute_indicator`，
        再清掉 HTML 缓存让前端重新装载（= 自动重跑回测的图表部分 ✓）。
        """
        series = str((payload or {}).get('series') or '')
        values = dict((payload or {}).get('values') or {})
        if not series or not values:
            return
        try:
            from ..strategy import indicator_menu as _menu
        except Exception as error:                               # noqa: BLE001
            self._error(f'指标设置不可用：{error}')
            return
        changed = False
        for strategy in self._instances or []:
            datasets = getattr(strategy, '_btindicatordataset', None) or {}
            for key, dataset in list(datasets.items()):
                name = str(getattr(dataset, 'name', '') or key)
                # 图例上的名字是**线名**（`cmo` / `sma`），dataset 的 key
                # 是策略里的变量名（`trix`）→ 列名也要认，否则找不到 ✗
                columns: List[str] = []
                try:
                    frame = getattr(dataset, 'pandas_object', None)
                    # ⚠ `Index or []` 会抛 ValueError（布尔歧义）→ 先判 None
                    cols = getattr(frame, 'columns', None)
                    if cols is not None:
                        columns = [str(col) for col in cols]
                except Exception:                                # noqa: BLE001
                    columns = []
                if series not in (str(key), name) and series not in columns:
                    continue
                try:
                    fresh = _menu.recompute_indicator(dataset, values)
                except Exception:                                # noqa: BLE001
                    continue
                if fresh is not None and hasattr(fresh, '_get_plot_datas'):
                    # ★ `recompute_indicator` 返回**新**dataset（不改旧对象）
                    #   → 必须写回 `_btindicatordataset`，否则图还是旧参数 ✗
                    #   ⚠ 有些指标重算出来是**裸 DataFrame**（没有 `_get_plot_datas`），
                    #     写回去会把 dataset 打坏（图表全部报错 ✗）→ 只认完整对象
                    datasets[key] = fresh
                    changed = True
        if not changed:
            self._error(f'找不到指标 {series}，无法重算')
            return
        self._html_cache.clear()
        self._html_files.clear()
        self.desk.push_log(f'指标 {series} 已按新参数重算：{values}', 'success')
        self.desk.push({'type': 'strategy_reload', 'id': self.id})

    def _selected(self) -> Optional[dict]:
        for item in self.strategies:
            if item.get('name') == self.selected_strategy:
                return item
        return self.strategies[0] if self.strategies else None

    def _selected_contract(self, strategy: dict) -> Optional[dict]:
        contracts = strategy.get('contracts') or []
        for item in contracts:
            if self.selected_contract in (item.get('contract'),
                                          item.get('symbol')):
                return item
        if contracts:
            self.selected_contract = str(contracts[0].get('contract')
                                         or contracts[0].get('symbol') or '')
            return contracts[0]
        return None

    def chart_html(self, key: str, theme: str = 'dark') -> str:
        """返回 MiniQT 图表 HTML（合约图 / 回测结果图）。

        直接调用 ``miniqt_backtest_chart`` 里从 MiniQT 复制过来的画图代码；
        不经过 desk 的 TypeScript 重画。结果按 ``(key, theme)`` 缓存。
        """
        from .miniqt_backtest_chart import (build_contract_html,
                                            build_result_html)
        if not self._instances:
            raise RuntimeError('回测还没有完成')
        cache_key = (str(key or ''), self.selected_strategy,
                     self.selected_contract, 'dark' if theme == 'dark'
                     else 'light')
        if cache_key in self._html_cache:
            return self._html_cache[cache_key]
        dark = cache_key[3] == 'dark'
        if key == 'result':
            instance = self._instance_for(self.selected_strategy)
            contract = self.selected_contract or ''
            html = build_result_html(instance, contract, theme_dark=dark)
        elif str(key).startswith('c:'):
            _prefix, strategy_name, contract = str(key).split(':', 2)
            instance = self._instance_for(strategy_name)
            html = build_contract_html(instance, contract, theme_dark=dark)
        else:
            raise ValueError(f'未知图表：{key}')
        self._html_cache[cache_key] = html
        return html

    def chart_file(self, key: str, theme: str = 'dark') -> str:
        """把 MiniQT 图表 HTML 写到本地临时文件，返回 ``file://`` URL。

        Qt 壳的 desk.html 是 ``file://`` 打开的，没有 HTTP 服务；
        iframe 用 ``/strategy_chart`` 会被浏览器当成“本地文件不存在”。
        这里直接生成一个真实 HTML 文件，iframe 用它的 file URL 装载。
        """
        import hashlib
        import tempfile
        from pathlib import Path as _Path
        cache_key = (str(key or ''), self.selected_strategy,
                     self.selected_contract, 'dark' if theme == 'dark'
                     else 'light')
        target = self._html_files.get(cache_key)
        if target and os.path.isfile(target):
            return _Path(target).as_uri()
        html = self.chart_html(key, theme)
        digest = hashlib.sha1(html.encode('utf-8')).hexdigest()[:16]
        safe_id = ''.join(ch if ch.isalnum() or ch in '-_' else '_'
                          for ch in self.id)[:40]
        folder = os.path.join(tempfile.gettempdir(), 'minibt_desk_charts')
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f'{safe_id}_{digest}.html')
        if not os.path.isfile(path):
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(html)
        self._html_files[cache_key] = path
        return _Path(path).as_uri()

    def _instance_for(self, name: str):
        wanted = str(name or '')
        for instance in self._instances:
            if instance.__class__.__name__ == wanted:
                return instance
        if self._instances:
            return self._instances[0]
        raise RuntimeError('回测还没有完成')

    def _push_selected(self) -> None:
        strategy = self._selected()
        if strategy is None:
            return
        contract = self._selected_contract(strategy)
        self._push_state()
        if self.optimization_rows:
            self.desk.push({
                'type': 'strategy_opt', 'id': self.id,
                'rows': self.optimization_rows,
            })
        self.desk.push({
            'type': 'strategy_result', 'id': self.id,
            'strategy': strategy.get('name'),
            'metrics': strategy.get('metrics') or {},
            'equity': strategy.get('equity') or {},
            'pnl': strategy.get('pnl') or [],
            'trade_style': strategy.get('trade_style') or {},
            'contracts': [{
                'symbol': item.get('symbol'),
                'contract': item.get('contract'),
                'trade_count': item.get('trade_count', 0),
                'bars': len(item.get('bars') or []),
            } for item in strategy.get('contracts') or []],
        })
        if contract is None:
            return
        bars = contract.get('bars') or []
        cutoff = bars[-MAX_CHART_BARS]['time'] if len(bars) > MAX_CHART_BARS \
            else (bars[0]['time'] if bars else 0)
        indicators = []
        for item in contract.get('indicators') or []:
            points = [point for point in item.get('data') or []
                      if point and point[0] >= cutoff]
            markers = [marker for marker in item.get('markers') or []
                       if marker and marker.get('time') and
                       marker['time'] >= cutoff]
            indicators.append({**item, 'data': points, 'markers': markers})
        markers = [marker for marker in contract.get('markers') or []
                   if marker and marker.get('time') and marker['time'] >= cutoff]
        links = [link for link in contract.get('links') or []
                 if link and link.get('time1') and link['time1'] >= cutoff]
        signals = []
        for item in contract.get('signals') or []:
            item_markers = [marker for marker in item.get('markers') or []
                            if marker and marker.get('time') and
                            marker['time'] >= cutoff]
            signals.append({**item, 'markers': item_markers})
        self.desk.push({
            'type': 'strategy_chart', 'id': self.id,
            'strategy': strategy.get('name'),
            'contract': contract.get('contract') or contract.get('symbol'),
            'bars': bars[-MAX_CHART_BARS:],
            'indicators': indicators,
            'signals': signals,
            'markers': markers,
            'links': links,
        })
        self.desk.push({
            'type': 'strategy_trades', 'id': self.id,
            'strategy': strategy.get('name'),
            'contract': contract.get('symbol'),
            'rows': [row for row in contract.get('trades') or []
                     if row.get('time') and row['time'] >= cutoff][:MAX_TRADES],
        })
