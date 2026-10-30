"""策略研究平台：Walk-forward / 批量回测 / 参数热力图 / Pareto / 实验库 / 报告。

模块分层
--------
* **纯函数**（可在没有网络、没有 Qt 的环境测试）：
  ``walk_forward_windows`` / ``param_grid`` / ``heatmap`` / ``pareto`` /
  ``summarize``。
* **ExperimentStore**：SQLite 实验库（实验 + trials + 报告路径）。
* **ResearchLab**：后台线程跑「窗口回测 / 批量回测 / 参数网格」，
  通过 desk 补丁推送进度和结果。

默认回测入口 ``run_strategy_slice`` 复用 minibt 的 ``Bt``：
策略文件 + 本地 CSV（或调用方给的 DataFrame）→ 回测 → 指标。
测试可以注入自己的 ``runner``，完全不启动 minibt 回测。
"""
from __future__ import annotations

import contextlib
import csv
import glob
import json
import math
import os
import shutil
import tempfile
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

#: 默认实验库路径（可用环境变量覆盖）
def default_db() -> str:
    path = os.environ.get('MINIBT_DESK_RESEARCH_DB', '').strip()
    if path:
        return path
    return os.path.join(os.path.expanduser('~'), '.minibt',
                        'desk_research.sqlite3')


#: 默认数据目录（desk 本地图表也扫这个目录）
def datas_dir() -> str:
    try:
        from ..data.tools import user_datas_dir
        return user_datas_dir()
    except Exception:                                            # noqa: BLE001
        return os.path.join(os.path.expanduser('~'), '.minibt', 'datas')


#: 常用指标（从 minibt 策略 metrics 里取，取不到就是 None）
METRIC_KEYS = ('profit_ratio', 'profit_ratio_year', 'max_drawdown',
               'sharpe_ratio', 'sortino_ratio', 'win_ratio', 'profit',
               'trade_count', 'calmar_ratio', 'volatility')

#: ``minibt.typing_.OPTTargetType`` 的全部取值（运行时 Literal 在 TYPE_CHECKING
#: 里，拿不到，所以这里复制一份；测试会对照源码防止漂移 ✓）
TARGET_METRICS = (
    'result', 'profit', 'profit_rate', 'adjusted_sortino',
    'autocorr_penalty', 'avg_loss', 'avg_return', 'avg_win', 'best', 'cagr',
    'calmar', 'common_sense_ratio', 'comp', 'compare', 'compsum',
    'conditional_value_at_risk', 'consecutive_losses', 'consecutive_wins',
    'cpc_index', 'cvar', 'distribution', 'drawdown_details',
    'expected_return', 'expected_shortfall', 'exposure',
    'gain_to_pain_ratio', 'geometric_mean', 'ghpr', 'greeks',
    'implied_volatility', 'information_ratio', 'kelly_criterion', 'kurtosis',
    'max_drawdown', 'monthly_returns', 'omega', 'outlier_loss_ratio',
    'outlier_win_ratio', 'outliers', 'payoff_ratio', 'pct_rank',
    'profit_factor', 'profit_ratio', 'r2', 'r_squared', 'rar',
    'recovery_factor', 'remove_outliers', 'risk_of_ruin',
    'risk_return_ratio', 'rolling_greeks', 'rolling_sharpe',
    'rolling_sortino', 'rolling_volatility', 'ror', 'serenity_index',
    'sharpe', 'skew', 'smart_sharpe', 'smart_sortino', 'sortino',
    'tail_ratio', 'to_drawdown_series', 'ulcer_index',
    'ulcer_performance_index', 'upi', 'value_at_risk', 'var', 'volatility',
    'warn', 'win_loss_ratio', 'win_rate', 'worst',
)

#: 正数且**越小越好**的指标（波动 / 连续亏损 / 风险概率…）
_LOWER_IS_BETTER = {
    'volatility', 'consecutive_losses', 'outlier_loss_ratio', 'ulcer_index',
    'risk_of_ruin', 'kurtosis', 'autocorr_penalty', 'expected_shortfall',
}


def metric_direction(metric: str) -> int:
    """目标方向：``1`` = 越大越好，``-1`` = 越小越好。

    ``max_drawdown`` / ``avg_loss`` / ``var`` 这类 QuantStats 返回**负数**的
    指标保留 ``1``：-0.05 比 -0.20 大，正好就是“回撤更小” ✓
    """
    return -1 if str(metric) in _LOWER_IS_BETTER else 1


def normalize_metrics(value: Any) -> List[str]:
    """前端传来的指标（str / list）→ 去重后的 1~3 个合法 OPTTargetType ✓"""
    if isinstance(value, str):
        raw = [item for item in value.replace(',', ' ').split() if item]
    elif isinstance(value, (list, tuple, set)):
        raw = [str(item) for item in value if str(item or '').strip()]
    else:
        raw = []
    out: List[str] = []
    for item in raw:
        name = str(item).strip()
        if name and name in TARGET_METRICS and name not in out:
            out.append(name)
        if len(out) >= 3:
            break
    return out or ['profit_ratio']


def _num(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _json(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _target_value(instance: Any, metric: str,
                  fallback: Optional[Dict[str, Any]] = None) -> Optional[float]:
    """取 ``OPTTargetType`` 里的任意指标（和 minibt 参数优化同一套 Stats）。"""
    stats = getattr(instance, '_stats', None)
    fn = getattr(stats, metric, None)
    if callable(fn):
        try:
            value = fn()
            if isinstance(value, pd.DataFrame):
                return None
            if isinstance(value, (pd.Series, np.ndarray, list, tuple)):
                values = list(value)
                value = values[-1] if values else None
            number = _num(value)
            if number is not None:
                return number
        except Exception:                                    # noqa: BLE001
            pass
    payload = fallback or {}
    aliases = {
        'max_drawdown': ('max_drawdown', 'drawdown'),
        'win_rate': ('win_rate', 'winrate'),
        'sharpe': ('sharpe', 'sharpe_ratio'),
        'sortino': ('sortino', 'sortino_ratio'),
        'profit_rate': ('profit_rate', 'return_pct'),
        'trade_count': ('trade_count', 'trades'),
        'profit_factor': ('profit_factor', 'payoff_ratio'),
    }
    for key in aliases.get(metric, (metric,)):
        number = _num(payload.get(key))
        if number is not None:
            return number
    return None


def metrics_of(instance: Any, names: Sequence[str]) -> Dict[str, Any]:
    """提取选中的 1~3 个目标指标（其余别名一并保留给前端卡片）"""
    from .strategy_lab import _metrics_payload
    payload = _metrics_payload(instance) or {}
    out = {key: _json(value) for key, value in payload.items()}
    for name in names:
        out[str(name)] = _target_value(instance, str(name), payload)
    return out


# ---------------------------------------------------------------- 纯函数
def walk_forward_windows(total: int, train: int, test: int,
                         step: int = 0) -> List[Dict[str, int]]:
    """滚动窗口边界（**按 bar 下标**；训练窗口可以重叠）

    >>> walk_forward_windows(100, 40, 10, 10)[0]
    {'train_start': 0, 'train_end': 40, 'test_start': 40, 'test_end': 50}
    """
    total, train, test = int(total), max(1, int(train)), max(1, int(test))
    step = max(1, int(step or test))
    windows: List[Dict[str, int]] = []
    start = 0
    while start + train + test <= total:
        windows.append({
            'index': len(windows),
            'train_start': start, 'train_end': start + train,
            'test_start': start + train, 'test_end': start + train + test,
        })
        start += step
        if len(windows) >= 500:          # 防御：数据量特别大时别生成上万窗口
            break
    return windows


def split_windows(frame: pd.DataFrame, train: int, test: int,
                  step: int = 0) -> List[Dict[str, Any]]:
    """DataFrame → 训练 / 测试切片（带时间范围，给报告用）"""
    if frame is None or getattr(frame, 'empty', True):
        return []
    windows = walk_forward_windows(len(frame), train, test, step)
    out: List[Dict[str, Any]] = []
    for window in windows:
        train_frame = frame.iloc[window['train_start']:window['train_end']]
        test_frame = frame.iloc[window['test_start']:window['test_end']]
        item = dict(window)
        for key, part in (('train', train_frame), ('test', test_frame)):
            if 'datetime' in part.columns and len(part):
                item[f'{key}_from'] = str(part['datetime'].iloc[0])
                item[f'{key}_to'] = str(part['datetime'].iloc[-1])
        out.append({'window': item, 'train': train_frame, 'test': test_frame})
    return out


def param_grid(params: Dict[str, Sequence[Any]]) -> List[Dict[str, Any]]:
    """参数网格（``{'length': [10, 20], 'std': [1, 2]}`` → 4 组）"""
    import itertools
    keys = list((params or {}).keys())
    values = []
    for key in keys:
        raw = params[key]
        if not isinstance(raw, (list, tuple, set)):
            raw = [raw]
        values.append(list(raw))
    if not keys:
        return [{}]
    out = [dict(zip(keys, combo))
           for combo in itertools.product(*values)]
    return out[:5000]                    # 防御：别把界面撑爆


def heatmap(rows: Iterable[Dict[str, Any]], x: str, y: str,
            metric: str = 'profit_ratio') -> Dict[str, Any]:
    """实验 / trial 行 → 二维热力图（前端用表格 + 颜色渲染）"""
    cells: Dict[tuple, List[float]] = {}
    xs, ys = [], []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        params = row.get('params') if isinstance(row.get('params'), dict)             else row
        xv = params.get(x)
        yv = params.get(y)
        metrics = row.get('metrics') if isinstance(row.get('metrics'),
                                                   dict) else {}
        value = _num(row.get(metric, metrics.get(metric)))
        if xv is None or yv is None or value is None:
            continue
        key = (str(xv), str(yv))
        cells.setdefault(key, []).append(value)
        if str(xv) not in xs:
            xs.append(str(xv))
        if str(yv) not in ys:
            ys.append(str(yv))
    grid = []
    for yv in ys:
        line = []
        for xv in xs:
            values = cells.get((xv, yv))
            line.append(round(float(np.mean(values)), 6) if values else None)
        grid.append(line)
    return {'x': x, 'y': y, 'metric': metric, 'x_values': xs,
            'y_values': ys, 'grid': grid}


def pareto(rows: Iterable[Dict[str, Any]], *,
           maximize: Sequence[str] = ('profit_ratio',),
           minimize: Sequence[str] = ('max_drawdown',)) -> List[Dict[str, Any]]:
    """非支配解（Pareto 前沿）；缺指标的行走不到前沿"""
    def values(row: Dict[str, Any]) -> Optional[Dict[str, float]]:
        metrics = row.get('metrics') if isinstance(row.get('metrics'), dict) \
            else row
        out: Dict[str, float] = {}
        for name in list(maximize) + list(minimize):
            number = _num((metrics or {}).get(name))
            if number is None:
                return None
            out[name] = number
        return out

    items: List[tuple] = []
    for row in rows or []:
        vec = values(row)
        if vec is not None:
            items.append((row, vec))

    def dominates(left: Dict[str, float], right: Dict[str, float]) -> bool:
        better = True
        strict = False
        for name in maximize:
            if left[name] < right[name]:
                better = False
            if left[name] > right[name]:
                strict = True
        for name in minimize:
            if left[name] > right[name]:
                better = False
            if left[name] < right[name]:
                strict = True
        return better and strict

    front = []
    for index, (row, vec) in enumerate(items):
        if any(other_index != index and dominates(other_vec, vec)
               for other_index, (_other, other_vec) in enumerate(items)):
            continue
        front.append({**row, '_objectives': vec})
    return front


def summarize(rows: Iterable[Dict[str, Any]],
              metric: str = 'profit_ratio') -> Dict[str, Any]:
    """稳定性摘要：均值 / 标准差 / 胜率 / 最差 / 最好"""
    values: List[float] = []
    for row in rows or []:
        metrics = row.get('metrics') if isinstance(row.get('metrics'), dict) \
            else row
        number = _num((metrics or {}).get(metric))
        if number is not None:
            values.append(number)
    if not values:
        return {'metric': metric, 'count': 0, 'mean': None, 'std': None,
                'positive_rate': None, 'worst': None, 'best': None}
    array = np.asarray(values, dtype=float)
    return {
        'metric': metric, 'count': int(len(values)),
        'mean': round(float(array.mean()), 6),
        'std': round(float(array.std(ddof=0)), 6),
        'positive_rate': round(float((array > 0).mean()), 4),
        'worst': round(float(array.min()), 6),
        'best': round(float(array.max()), 6),
    }


def stability_score(summary: Dict[str, Any], metric: str = '') -> Optional[float]:
    """把均值 / 波动 / 胜率压成一个 0~100 的分数（给实验库排序用）

    ``metric`` 传入时按方向调整：``volatility`` 这类越小越好 ✓
    """
    mean = _num(summary.get('mean'))
    std = _num(summary.get('std')) or 0.0
    rate = _num(summary.get('positive_rate')) or 0.0
    if mean is None:
        return None
    direction = metric_direction(metric) if metric else 1
    score = 50.0 + mean * 100.0 * direction - std * 80.0 + (rate - 0.5) * 40.0
    return round(max(0.0, min(100.0, score)), 2)


# ---------------------------------------------------------------- 数据
def load_frame(path: str, *, start: str = '', end: str = '',
               limit: int = 200000) -> pd.DataFrame:
    """读 CSV（``datetime, open, high, low, close, volume``）并按时间截取"""
    path = str(path or '')
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f'找不到数据文件：{path}')
    if path.lower().endswith(('.parquet', '.pq')):
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    rename = {}
    for want, aliases in {
            'datetime': ('datetime', 'date_time', 'time', 'date', 'timestamp'),
            'open': ('open', 'o'), 'high': ('high', 'h'),
            'low': ('low', 'l'), 'close': ('close', 'c'),
            'volume': ('volume', 'vol', 'v')}.items():
        for alias in aliases:
            if alias in frame.columns:
                rename[alias] = want
                break
    frame = frame.rename(columns=rename)
    if 'datetime' not in frame.columns or 'close' not in frame.columns:
        raise ValueError(f'{os.path.basename(path)} 缺少 datetime / close 列')
    frame['datetime'] = pd.to_datetime(frame['datetime'], errors='coerce')
    frame = frame.dropna(subset=['datetime']).sort_values('datetime')
    frame = frame.reset_index(drop=True)
    if start:
        frame = frame[frame['datetime'] >= pd.to_datetime(start)]
    if end:
        frame = frame[frame['datetime'] <= pd.to_datetime(end)]
    if limit and len(frame) > limit:
        frame = frame.iloc[-int(limit):]
    return frame.reset_index(drop=True)


def local_data_names() -> List[str]:
    """``LocalDatas`` 里可用的数据名（包内 test / l2609_60 / pp2609_60 +
    用户目录 + 外部登记）✓
    """
    try:
        from ..data.tools import list_csv_names
        return list_csv_names()
    except Exception:                                        # noqa: BLE001
        return []


def _local_data_path(name: str) -> str:
    """数据名 → CSV 路径（包内 / 用户目录 / 外部登记；找不到 → ``''``）✓"""
    try:
        from ..data.tools import get_csv_path
        path = get_csv_path(str(name))
        if path and os.path.isfile(path):
            return path
    except Exception:                                        # noqa: BLE001
        pass
    return ''


def strategy_data_names(file: str) -> List[str]:
    """策略文件里 ``get_kline(LocalDatas.xxx)`` / 字面量 → 数据名列表 ✓"""
    try:
        from .strategy_plan import analyze
        return [str(item) for item in
                (analyze(str(file)).get('contracts') or [])]
    except Exception:                                        # noqa: BLE001
        return []


def resolve_data_files(names: Iterable[str], root: str = '') -> List[str]:
    """数据名 / 绝对路径 → CSV 路径列表。

    支持：
    * ``LocalDatas.test`` → ``minibt/data/test/test.csv``（包内基础数据）
    * ``LocalDatas.xxx``（用户目录 / 外部登记）
    * ``C:/data/ag.csv``（绝对路径）
    * ``ag2612_60``（在 ``~/.minibt/datas`` 里找）
    """
    root = root or datas_dir()
    out: List[str] = []
    for raw in names or []:
        text = str(raw or '').strip()
        if not text:
            continue
        candidates: List[str] = []
        if os.path.isfile(text):
            candidates = [text]
        elif os.path.isabs(text):
            candidates = [text]
        else:
            local = _local_data_path(text)
            if local:
                candidates.append(local)
            for folder in (root, os.path.expanduser('~/.minibt/datas')):
                candidates.extend(glob.glob(os.path.join(folder, text)))
                if not os.path.splitext(text)[1]:
                    candidates.extend(glob.glob(os.path.join(
                        folder, text + '.csv')))
        for path in candidates:
            if path not in out and os.path.isfile(path):
                out.append(path)
    return out


# ---------------------------------------------------------------- 回测入口
@contextlib.contextmanager
def _patched_local_data(frames: Dict[str, pd.DataFrame]):
    """让策略里的 ``get_kline(LocalDatas.xxx)`` 读到**当前窗口**的 CSV ✓

    minibt 的 ``get_kline`` 优先读本地 CSV（优先级高于 ``Bt.adddata``），
    所以 walk-forward 只靠 ``adddata`` 是切不动数据的。这里把每个窗口的
    DataFrame 写成临时 CSV，并临时替换 ``data.tools.get_csv_path``。
    """
    from ..data import tools as data_tools
    temp = tempfile.mkdtemp(prefix='minibt_wf_')
    mapping: Dict[str, str] = {}
    try:
        for name, frame in (frames or {}).items():
            if frame is None or getattr(frame, 'empty', True):
                continue
            path = os.path.join(temp, f'{name}.csv')
            frame.to_csv(path, index=False)
            mapping[str(name)] = path
            mapping[os.path.splitext(os.path.basename(str(name)))[0]] = path
        original = data_tools.get_csv_path

        def patched(name: str) -> str:
            text = str(name or '')
            if text in mapping:
                return mapping[text]
            stem = os.path.splitext(os.path.basename(text))[0]
            if stem in mapping:
                return mapping[stem]
            return original(name)

        data_tools.get_csv_path = patched
        try:
            yield mapping
        finally:
            data_tools.get_csv_path = original
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def run_strategy_slice(file: str, frames: Dict[str, pd.DataFrame],
                       params: Optional[Dict[str, Any]] = None,
                       metrics: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """用 minibt ``Bt`` 跑一段回测（默认 runner；测试可替换）

    Returns ``{'strategies': [{'name', 'metrics', 'trades'}], 'elapsed'}``
    """
    from ..bt import Bt

    started = time.time()
    bt = Bt(auto=False)
    bt.addstrategy(file)
    if not bt.strategies:
        raise ValueError('文件里没有找到 Strategy 子类')
    if params:
        for cls in bt.strategies:
            try:
                base = dict(getattr(cls, 'params', {}) or {})
                base.update(params)
                cls.params = base
                if getattr(cls, 'op_config', None):
                    cls.op_config = None
            except Exception:                                    # noqa: BLE001
                pass
    if frames:
        bt.adddata(**{name: frame for name, frame in frames.items()
                      if frame is not None and not frame.empty})
    for cls in bt.strategies:
        try:
            cls._light_chart = False
        except Exception:                                        # noqa: BLE001
            pass
    with _patched_local_data(frames):
        bt.run(isplot=False, close_api=False, model='sequential')

    wanted = normalize_metrics(metrics or ['profit_ratio'])
    strategies = []
    for instance in getattr(bt, 'strategies', []) or []:
        if getattr(instance, 'profits', None) is None:
            continue
        values = metrics_of(instance, wanted)
        trades = []
        for trade in getattr(instance, 'trade_records', []) or []:
            if isinstance(trade, dict):
                trades.append({key: _json(value) for key, value in
                               trade.items() if key in (
                                   'time', 'datetime', 'symbol', 'direction',
                                   'offset', 'price', 'volume', 'pnl')})
        strategies.append({'name': instance.__class__.__name__,
                           'metrics': values, 'trades': trades[-500:]})
    return {'strategies': strategies,
            'elapsed': round(time.time() - started, 2)}


# ---------------------------------------------------------------- 实验库
class ExperimentStore:
    """SQLite 实验库（实验 = 一次 walk-forward / 批量 / 网格）"""

    def __init__(self, path: str = ''):
        self.path = path or default_db()
        if self.path != ':memory:':
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
        self._lock = threading.RLock()
        import sqlite3
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock, self._db:
            self._db.execute(
                'CREATE TABLE IF NOT EXISTS experiments ('
                'id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, '
                'mode TEXT, file TEXT, symbols TEXT, params TEXT, '
                'metrics TEXT, summary TEXT, windows TEXT, score REAL, '
                'report TEXT, note TEXT, created REAL)')
            self._db.execute(
                'CREATE TABLE IF NOT EXISTS trials ('
                'id INTEGER PRIMARY KEY AUTOINCREMENT, experiment INTEGER, '
                'window INTEGER, params TEXT, metrics TEXT, status TEXT, '
                'created REAL)')
            self._db.execute(
                'CREATE INDEX IF NOT EXISTS idx_exp_created '
                'ON experiments(created DESC)')

    def add_experiment(self, *, name: str = '', mode: str = '',
                       file: str = '', symbols: Any = None,
                       params: Any = None, metrics: Any = None,
                       summary: Any = None, windows: Any = None,
                       score: Optional[float] = None, note: str = '') -> int:
        with self._lock, self._db:
            cursor = self._db.execute(
                'INSERT INTO experiments (name, mode, file, symbols, params, '
                'metrics, summary, windows, score, note, created) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (str(name), str(mode), str(file),
                 json.dumps(symbols or [], ensure_ascii=False, default=str),
                 json.dumps(params or {}, ensure_ascii=False, default=str),
                 json.dumps(metrics or {}, ensure_ascii=False, default=str),
                 json.dumps(summary or {}, ensure_ascii=False, default=str),
                 json.dumps(windows or [], ensure_ascii=False, default=str),
                 _num(score), str(note), time.time()))
            return int(cursor.lastrowid or 0)

    def add_trial(self, experiment: int, *, window: int = 0,
                  params: Any = None, metrics: Any = None,
                  status: str = 'ok') -> int:
        with self._lock, self._db:
            cursor = self._db.execute(
                'INSERT INTO trials (experiment, window, params, metrics, '
                'status, created) VALUES (?,?,?,?,?,?)',
                (int(experiment), int(window),
                 json.dumps(params or {}, ensure_ascii=False, default=str),
                 json.dumps(metrics or {}, ensure_ascii=False, default=str),
                 str(status), time.time()))
            return int(cursor.lastrowid or 0)

    def experiments(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                'SELECT * FROM experiments ORDER BY created DESC LIMIT ?',
                (max(1, int(limit or 100)),)).fetchall()
        return [self._row(item) for item in rows]

    def experiment(self, experiment_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._db.execute('SELECT * FROM experiments WHERE id=?',
                                   (int(experiment_id),)).fetchone()
        return self._row(row) if row else None

    def trials(self, experiment_id: int, limit: int = 2000) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                'SELECT * FROM trials WHERE experiment=? ORDER BY id LIMIT ?',
                (int(experiment_id), max(1, int(limit or 2000)))).fetchall()
        return [self._row(item) for item in rows]

    def update_report(self, experiment_id: int, path: str) -> None:
        with self._lock, self._db:
            self._db.execute('UPDATE experiments SET report=? WHERE id=?',
                             (str(path), int(experiment_id)))

    def delete(self, experiment_id: int) -> bool:
        with self._lock, self._db:
            first = self._db.execute(
                'DELETE FROM trials WHERE experiment=?',
                (int(experiment_id),)).rowcount
            second = self._db.execute(
                'DELETE FROM experiments WHERE id=?',
                (int(experiment_id),)).rowcount
        return bool(first or second)

    @staticmethod
    def _row(row) -> Dict[str, Any]:
        item = dict(row)
        for key in ('symbols', 'params', 'metrics', 'summary', 'windows'):
            try:
                item[key] = json.loads(item.get(key) or 'null')
            except (TypeError, ValueError):
                item[key] = None
        return item

    def close(self) -> None:
        with self._lock:
            try:
                self._db.close()
            except Exception:                                    # noqa: BLE001
                pass


# ---------------------------------------------------------------- 报告
def export_report(experiment: Dict[str, Any], path: str = '',
                  *, trials: Optional[List[Dict[str, Any]]] = None) -> str:
    """导出 Markdown 报告（同名 CSV 一起写，方便 Excel 打开）"""
    experiment = experiment or {}
    name = str(experiment.get('name') or 'experiment')
    safe = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in name)
    path = str(path or os.path.join(
        os.path.expanduser('~/.minibt/desk/reports'),
        f'{safe}_{int(time.time())}.md'))
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    metrics = experiment.get('metrics') or {}
    summary = experiment.get('summary') or {}
    windows = experiment.get('windows') or []
    lines = [
        f'# {name}', '',
        f"- 模式：{experiment.get('mode', '')}",
        f"- 策略：{experiment.get('file', '')}",
        f"- 合约：{', '.join(experiment.get('symbols') or [])}",
        f"- 创建：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(experiment.get('created') or time.time()))}",
        f"- 稳定性分数：{experiment.get('score', '')}", '',
        '## 汇总指标', '',
        '| 指标 | 值 |', '| --- | --- |',
    ]
    for key, value in metrics.items():
        lines.append(f'| {key} | {value} |')
    lines += ['', '## Walk-forward 稳定性', '',
              '| 指标 | 值 |', '| --- | --- |']
    for key, value in summary.items():
        lines.append(f'| {key} | {value} |')
    lines += ['', '## 窗口', '',
              '| # | 训练区间 | 测试区间 | 指标 |', '| --- | --- | --- | --- |']
    for index, item in enumerate(windows):
        shown = ', '.join(f'{key}={value}' for key, value in
                          (item.get('metrics') or {}).items() if value is not None)
        lines.append(f"| {index + 1} | {item.get('train', '')} | "
                     f"{item.get('test', '')} | {shown} |")
    if trials:
        csv_path = os.path.splitext(path)[0] + '.csv'
        keys = sorted({key for row in trials for key in (row.get('params') or {})})
        metric_keys = sorted({key for row in trials
                              for key in (row.get('metrics') or {})})
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.writer(handle)
            writer.writerow(['window'] + keys + metric_keys)
            for row in trials:
                params = row.get('params') or {}
                metrics_row = row.get('metrics') or {}
                writer.writerow([row.get('window')]
                                + [params.get(key) for key in keys]
                                + [metrics_row.get(key) for key in metric_keys])
        lines += ['', f'明细 CSV：`{csv_path}`']
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    return path


# ---------------------------------------------------------------- 会话
class ResearchLab:
    """一个 desk 的研究会话（后台线程 + 补丁推送）"""

    def __init__(self, desk, *, store: Optional[ExperimentStore] = None,
                 runner: Optional[Callable[..., Dict[str, Any]]] = None):
        self.desk = desk
        self.store = store or ExperimentStore()
        self.runner = runner or run_strategy_slice
        self.status = 'idle'
        self.error = ''
        self.result: Dict[str, Any] = {}
        self.metrics: List[str] = ['profit_ratio']
        self.progress_current = 0
        self.progress_total = 0
        self._thread: Optional[threading.Thread] = None
        self._stop = False

    # ------------------------------------------------------------ 推送
    def _push(self, patch: Dict[str, Any]) -> None:
        try:
            self.desk.push(patch)
        except Exception:                                        # noqa: BLE001
            pass

    def _log(self, text: str) -> None:
        if self.desk is not None:
            try:
                self.desk.push_log(f'[研究] {text}', 'info')
            except Exception:                                    # noqa: BLE001
                pass

    def _progress(self, current: int, total: int, text: str = '') -> None:
        self.progress_current, self.progress_total = int(current), int(total)
        self._push({'type': 'research_progress', 'current': self.progress_current,
                    'total': self.progress_total, 'text': str(text)})

    def cancel(self) -> None:
        self._stop = True

    # ------------------------------------------------------------ 启动
    def start(self, payload: Dict[str, Any]) -> None:
        payload = payload or {}
        if self._thread is not None and self._thread.is_alive():
            self._push({'type': 'research_error',
                        'message': '已有研究任务在运行'})
            return
        mode = str(payload.get('mode') or 'walk_forward')
        if mode not in ('walk_forward', 'batch', 'grid'):
            mode = 'walk_forward'
        self.metrics = normalize_metrics(
            payload.get('metrics') or payload.get('metric')
            or ['profit_ratio'])
        self.status = 'running'
        self.error = ''
        self._stop = False
        self._push({'type': 'research_state', 'status': self.status,
                    'mode': mode, 'message': '准备中…'})
        self._thread = threading.Thread(
            target=self._run, args=(mode, dict(payload)),
            name='desk-research', daemon=True)
        self._thread.start()

    # ------------------------------------------------------------ 执行
    def _run(self, mode: str, payload: Dict[str, Any]) -> None:
        try:
            strategy = str(payload.get('file') or '')
            if not strategy or not os.path.isfile(strategy):
                raise ValueError('策略文件不存在')
            tokens = [item for item in
                      str(payload.get('data') or '').replace(',', ' ').split()
                      if item]
            if not tokens:
                # 数据留空 → 从策略里 get_kline(LocalDatas.xxx) 自动识别 ✓
                tokens = strategy_data_names(strategy)
            files = resolve_data_files(tokens)
            if not files:
                available = local_data_names()
                shown = '、'.join(available[:12]) or '（空）'
                raise ValueError(
                    f'没有找到数据文件 {tokens or "（策略里也没有 LocalDatas）"}；'
                    f'可用本地数据：{shown}'
                    + (' …' if len(available) > 12 else ''))
            frames = {os.path.splitext(os.path.basename(path))[0]:
                      load_frame(path, start=str(payload.get('start') or ''),
                                 end=str(payload.get('end') or ''))
                      for path in files}
            # 策略里 `get_kline(LocalDatas.xxx)` 的 xxx 必须和窗口数据对得上，
            # 否则 walk-forward 只切了 adddata、策略仍读整份 CSV（结果不可信 ✗）
            used = strategy_data_names(strategy)
            if used and not any(name in frames for name in used):
                raise ValueError(
                    f'策略里用的是 {used}，但数据文件是 {list(frames)}；'
                    '请把「数据文件」改成策略里的 LocalDatas 名，或留空自动识别')
            base_params = payload.get('params')
            if isinstance(base_params, str):
                base_params = json.loads(base_params or '{}')
            base_params = dict(base_params or {})
            if mode == 'walk_forward':
                self._walk_forward(strategy, frames, base_params, payload)
            elif mode == 'grid':
                self._grid(strategy, frames, base_params, payload)
            else:
                self._batch(strategy, files, frames, base_params, payload)
            if self._stop:
                self.status = 'cancelled'
            self._push({'type': 'research_state', 'status': self.status,
                        'result': self.result})
        except Exception as error:                               # noqa: BLE001
            import traceback
            self.error = f'{type(error).__name__}: {error}'
            self.status = 'error'
            self._log(traceback.format_exc())
            self._push({'type': 'research_error', 'message': self.error})
        finally:
            self._push({'type': 'research_state', 'status': self.status,
                        'error': self.error, 'result': self.result})

    def _call_runner(self, strategy: str, frames: Dict[str, pd.DataFrame],
                     params: Dict[str, Any]) -> Dict[str, Any]:
        """兼容 3 参数 / 4 参数（带 metrics）的 runner（测试可注入）✓"""
        import inspect
        try:
            parameters = inspect.signature(self.runner).parameters
            names = list(parameters.values())
            if 'metrics' in parameters:
                return self.runner(strategy, frames, params,
                                   metrics=self.metrics)
            positional = [item for item in names if item.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD)]
            if len(positional) >= 4:
                return self.runner(strategy, frames, params, self.metrics)
        except (TypeError, ValueError):
            pass
        return self.runner(strategy, frames, params)

    def _summaries(self, rows: List[Dict[str, Any]]
                   ) -> tuple[Dict[str, Dict[str, Any]], Optional[float]]:
        """每个选中指标各算一份稳定性；总分取各指标分数的平均 ✓"""
        summaries = {name: summarize(rows, name) for name in self.metrics}
        scores = [stability_score(summaries[name], name)
                  for name in self.metrics]
        scores = [item for item in scores if item is not None]
        score = round(float(np.mean(scores)), 2) if scores else None
        return summaries, score

    def _pareto(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        maximize = tuple(name for name in self.metrics
                         if metric_direction(name) > 0)
        minimize = tuple(name for name in self.metrics
                         if metric_direction(name) < 0)
        return pareto(rows, maximize=maximize or ('profit_ratio',),
                      minimize=minimize)

    def _heatmaps(self, rows: List[Dict[str, Any]],
                  x: str, y: str) -> Dict[str, Dict[str, Any]]:
        return {name: heatmap(rows, x, y, name) for name in self.metrics}

    def _walk_forward(self, strategy: str, frames: Dict[str, pd.DataFrame],
                      params: Dict[str, Any], payload: Dict[str, Any]) -> None:
        train = int(payload.get('train') or 240)
        test = int(payload.get('test') or 60)
        step = int(payload.get('step') or test)
        name = str(payload.get('name') or
                   f'WF {os.path.basename(strategy)}')
        primary = next(iter(frames.values()))
        windows = split_windows(primary, train, test, step)
        if not windows:
            raise ValueError(f'数据只有 {len(primary)} 根，不够 '
                             f'{train}+{test} 根做 walk-forward')
        results: List[Dict[str, Any]] = []
        self._progress(0, len(windows), 'walk-forward')
        experiment_id = self.store.add_experiment(
            name=name, mode='walk_forward', file=strategy,
            symbols=list(frames), params=params, metrics={},
            summary={}, windows=[], score=None,
            note=f'train={train} test={test} step={step}')
        for index, item in enumerate(windows):
            if self._stop:
                break
            window = item['window']
            # 训练 + 测试拼在一起回测，再按测试区间统计（更接近实盘）
            combined = {}
            for key, frame in frames.items():
                if key == next(iter(frames)):
                    combined[key] = pd.concat(
                        [item['train'], item['test']], ignore_index=True)
                else:
                    combined[key] = frame
            try:
                output = self._call_runner(strategy, combined, params)
                metrics = (output.get('strategies') or [{}])[0].get(
                    'metrics') or {}
            except Exception as error:                           # noqa: BLE001
                metrics = {'error': f'{type(error).__name__}: {error}'}
            record = {
                'window': index,
                'train': f"{window.get('train_from', '')} → "
                         f"{window.get('train_to', '')}",
                'test': f"{window.get('test_from', '')} → "
                        f"{window.get('test_to', '')}",
                'metrics': metrics,
            }
            results.append(record)
            self.store.add_trial(experiment_id, window=index, params=params,
                                 metrics=metrics,
                                 status='ok' if 'error' not in metrics else 'error')
            self._progress(index + 1, len(windows),
                           f"窗口 {index + 1}/{len(windows)}")
        summaries, score = self._summaries(results)
        primary = self.metrics[0]
        metrics = {'windows': len(results),
                   **{key: value.get('mean')
                      for key, value in summaries.items()}}
        self.store.add_experiment(
            name=f'{name}（汇总）', mode='walk_forward_summary', file=strategy,
            symbols=list(frames), params=params, metrics=metrics,
            summary=summaries[primary], windows=results, score=score,
            note=f'experiment #{experiment_id}; metrics={",".join(self.metrics)}')
        heatmaps = self._heatmaps(results, 'window', 'window')
        self.result = {
            'kind': 'walk_forward', 'experiment': experiment_id,
            'name': name, 'windows': results,
            'summary': summaries[primary], 'summaries': summaries,
            'score': score, 'metric': primary,
            'metrics': list(self.metrics),
            'heatmaps': heatmaps, 'heatmap': heatmaps[primary],
            'pareto': self._pareto(results),
            'experiments': self.store.experiments(50),
        }
        self.status = 'ready'
        self._push({'type': 'research_result', **self.result})

    def _grid(self, strategy: str, frames: Dict[str, pd.DataFrame],
              params: Dict[str, Any], payload: Dict[str, Any]) -> None:
        grid = param_grid(params)
        if not grid:
            raise ValueError('参数网格为空')
        name = str(payload.get('name') or f'Grid {os.path.basename(strategy)}')
        experiment_id = self.store.add_experiment(
            name=name, mode='grid', file=strategy, symbols=list(frames),
            params=params, metrics={}, summary={}, windows=[], score=None,
            note=f'{len(grid)} 组参数')
        rows: List[Dict[str, Any]] = []
        self._progress(0, len(grid), '参数网格')
        for index, combo in enumerate(grid):
            if self._stop:
                break
            try:
                output = self._call_runner(strategy, frames, combo)
                metrics = (output.get('strategies') or [{}])[0].get(
                    'metrics') or {}
            except Exception as error:                           # noqa: BLE001
                metrics = {'error': f'{type(error).__name__}: {error}'}
            row = {'window': index, 'params': combo, 'metrics': metrics}
            rows.append(row)
            self.store.add_trial(experiment_id, window=index, params=combo,
                                 metrics=metrics,
                                 status='ok' if 'error' not in metrics else 'error')
            self._progress(index + 1, len(grid), f'{index + 1}/{len(grid)}')
        keys = list(params)
        x = keys[0] if keys else 'x'
        y = keys[1] if len(keys) > 1 else x
        summaries, score = self._summaries(rows)
        primary = self.metrics[0]
        metrics = {key: value.get('mean')
                   for key, value in summaries.items()}
        self.store.add_experiment(
            name=f'{name}（汇总）', mode='grid_summary', file=strategy,
            symbols=list(frames), params=params,
            metrics=metrics, summary=summaries[primary],
            windows=rows, score=score,
            note=f'experiment #{experiment_id}; metrics={",".join(self.metrics)}')
        heatmaps = self._heatmaps(rows, x, y)
        self.result = {
            'kind': 'grid', 'experiment': experiment_id, 'name': name,
            'grid_rows': rows, 'summary': summaries[primary],
            'summaries': summaries, 'score': score, 'metric': primary,
            'metrics': list(self.metrics),
            'heatmaps': heatmaps, 'heatmap': heatmaps[primary],
            'pareto': self._pareto(rows),
            'experiments': self.store.experiments(50),
        }
        self.status = 'ready'
        self._push({'type': 'research_result', **self.result})

    def _batch(self, strategy: str, files: List[str],
               frames: Dict[str, pd.DataFrame], params: Dict[str, Any],
               payload: Dict[str, Any]) -> None:
        name = str(payload.get('name') or f'Batch {os.path.basename(strategy)}')
        experiment_id = self.store.add_experiment(
            name=name, mode='batch', file=strategy, symbols=list(frames),
            params=params, metrics={}, summary={}, windows=[], score=None,
            note=f'{len(files)} 个数据文件')
        rows: List[Dict[str, Any]] = []
        self._progress(0, len(files), '批量回测')
        for index, path in enumerate(files):
            if self._stop:
                break
            label = os.path.splitext(os.path.basename(path))[0]
            try:
                output = self._call_runner(strategy, {label: frames[label]}, params)
                metrics = (output.get('strategies') or [{}])[0].get(
                    'metrics') or {}
            except Exception as error:                           # noqa: BLE001
                metrics = {'error': f'{type(error).__name__}: {error}'}
            row = {'window': index, 'name': label,
                   'params': {'data': label}, 'metrics': metrics}
            rows.append(row)
            self.store.add_trial(experiment_id, window=index,
                                 params={'data': label}, metrics=metrics,
                                 status='ok' if 'error' not in metrics else 'error')
            self._progress(index + 1, len(files), label)
        summaries, score = self._summaries(rows)
        primary = self.metrics[0]
        metrics = {key: value.get('mean')
                   for key, value in summaries.items()}
        self.store.add_experiment(
            name=f'{name}（汇总）', mode='batch_summary', file=strategy,
            symbols=list(frames), params=params,
            metrics=metrics, summary=summaries[primary],
            windows=rows, score=score,
            note=f'experiment #{experiment_id}; metrics={",".join(self.metrics)}')
        heatmaps = self._heatmaps(rows, 'name', 'name')
        self.result = {
            'kind': 'batch', 'experiment': experiment_id, 'name': name,
            'batch_rows': rows, 'summary': summaries[primary],
            'summaries': summaries, 'score': score, 'metric': primary,
            'metrics': list(self.metrics),
            'heatmaps': heatmaps, 'heatmap': heatmaps[primary],
            'pareto': self._pareto(rows),
            'experiments': self.store.experiments(50),
        }
        self.status = 'ready'
        self._push({'type': 'research_result', **self.result})

    # ------------------------------------------------------------ 查询
    def snapshot(self) -> Dict[str, Any]:
        return {'type': 'research', 'status': self.status,
                'error': self.error,
                'result': self.result,
                'metrics': list(TARGET_METRICS),
                'metric_directions': {name: metric_direction(name)
                                      for name in TARGET_METRICS},
                'data_names': local_data_names(),
                'experiments': self.store.experiments(100)}

    def report(self, experiment_id: int, path: str = '') -> str:
        experiment = self.store.experiment(int(experiment_id))
        if not experiment:
            raise ValueError(f'实验 #{experiment_id} 不存在')
        path = export_report(experiment, path,
                             trials=self.store.trials(int(experiment_id)))
        self.store.update_report(int(experiment_id), path)
        return path
