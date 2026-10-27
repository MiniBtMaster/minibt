"""本地数据平台：DuckDB / Parquet 行情库、数据质量检查、主力换月 / 复权、
多周期对齐、Tick / 盘口回放。

设计
----
* **存储**：CSV 仍是一等公民（desk 本地图表沿用），新增 Parquet 读写；
  DuckDB 在则用 DuckDB（``SELECT`` 查询 / ``read_parquet`` / 导出），
  不在则自动退回 pandas（功能不丢，只是 SQL 只能查已登记文件）。
* **质量检查**：缺列 / 时间重复 / 时间乱序 / OHLC 不自洽 / 跳空 / 零成交 /
   极端涨跌，全部给分数与明细。
* **主力连续**：按成交量选主力 + 换月拼接；复权支持 ``none`` /
  ``difference``（价差） / ``ratio``（比例）。
* **多周期**：``resample_bars`` 任意 rule（如 ``5min`` / ``1h`` / ``1D``）。
* **Tick / 盘口**：``ticks_to_bars`` 把逐笔聚合成任意秒数 K 线。

所有函数都不依赖 Qt / 网络，可直接在脚本里用::

    from minibt.desk.datahub import DataCatalog, quality_report
    catalog = DataCatalog()
    catalog.refresh()
    print(catalog.items()[:3])
"""
from __future__ import annotations

import glob
import json
import os
import re
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

#: 单文件最多读多少行（防止误选超大文件卡死）
MAX_ROWS = 2000000

#: 标准 OHLCV 列
COLUMNS = ('datetime', 'open', 'high', 'low', 'close', 'volume')

_ALIASES = {
    'datetime': ('datetime', 'date_time', 'time', 'date', 'timestamp',
                 'trade_date'),
    'open': ('open', 'o'), 'high': ('high', 'h'),
    'low': ('low', 'l'), 'close': ('close', 'c'),
    'volume': ('volume', 'vol', 'v', 'turnover_volume'),
    'amount': ('amount', 'turnover', 'value'),
    'open_interest': ('open_interest', 'oi', 'hold'),
    'symbol': ('symbol', 'instrument', 'contract', 'code'),
}


def datas_dir() -> str:
    path = os.environ.get('MINIBT_DESK_DATAS', '').strip()
    if path:
        return path
    try:
        from ..data.tools import user_datas_dir
        return user_datas_dir()
    except Exception:                                            # noqa: BLE001
        return os.path.join(os.path.expanduser('~'), '.minibt', 'datas')


def default_folders() -> List[str]:
    """数据平台默认扫描的目录：用户目录 + **包内 test** + 外部登记 ✓"""
    out: List[str] = []
    try:
        from ..data.tools import datas_dirs, external_paths
        for folder in datas_dirs():
            folder = str(folder)
            if os.path.isdir(folder) and folder not in out:
                out.append(folder)
        for path in external_paths():
            folder = str(path)
            if os.path.isfile(folder):
                folder = os.path.dirname(folder)
            if os.path.isdir(folder) and folder not in out:
                out.append(folder)
    except Exception:                                            # noqa: BLE001
        pass
    folder = datas_dir()
    if os.path.isdir(folder) and folder not in out:
        out.append(folder)
    return out


def duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401
        return True
    except Exception:                                            # noqa: BLE001
        return False


def normalize_ohlcv(frame: pd.DataFrame,
                    *, symbol: str = '') -> pd.DataFrame:
    """列名 / 类型 / 排序 / 去重 统一成标准 OHLCV（坏行直接丢）"""
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=COLUMNS)
    out = frame.copy()
    rename: Dict[str, str] = {}
    lowered = {str(col).strip().lower(): col for col in out.columns}
    for want, aliases in _ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                rename[lowered[alias]] = want
                break
    out = out.rename(columns=rename)
    if 'datetime' not in out.columns:
        raise ValueError('数据缺少 datetime / date / time 列')
    out['datetime'] = pd.to_datetime(out['datetime'], errors='coerce')
    for key in ('open', 'high', 'low', 'close', 'volume'):
        if key not in out.columns:
            out[key] = np.nan
        out[key] = pd.to_numeric(out[key], errors='coerce')
    out = out.dropna(subset=['datetime'])
    out = out.sort_values('datetime')
    out = out.drop_duplicates(subset=['datetime'], keep='last')
    out = out.reset_index(drop=True)
    if symbol:
        out['symbol'] = str(symbol)
    keep = [col for col in COLUMNS if col in out.columns]
    keep += [col for col in out.columns if col not in keep]
    out = out[keep]
    if len(out) > MAX_ROWS:
        out = out.iloc[-MAX_ROWS:].reset_index(drop=True)
    return out


def read_table(path: str, *, symbol: str = '') -> pd.DataFrame:
    """读 CSV / Parquet（Parquet 优先 DuckDB，其次 pandas）"""
    path = str(path or '')
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f'找不到数据文件：{path}')
    lower = path.lower()
    if lower.endswith(('.parquet', '.pq')):
        if duckdb_available():
            import duckdb
            shown = path.replace(chr(92), '/').replace("'", "''")
            frame = duckdb.sql(
                f"SELECT * FROM read_parquet('{shown}')").df()
        else:
            frame = pd.read_parquet(path)
    elif lower.endswith(('.csv', '.txt', '.tsv')):
        frame = pd.read_csv(path, sep='\t' if lower.endswith('.tsv') else ',')
    else:
        raise ValueError(f'不支持的数据格式：{os.path.splitext(path)[1]}')
    return normalize_ohlcv(frame, symbol=symbol or
                           os.path.splitext(os.path.basename(path))[0])


def to_parquet(frame: pd.DataFrame, path: str) -> str:
    """写 Parquet（有 DuckDB 就用 DuckDB，没 pyarrow 也能写）"""
    frame = normalize_ohlcv(frame)
    path = str(path)
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if duckdb_available():
        import duckdb
        con = duckdb.connect()
        try:
            con.register('_frame', frame)
            target = path.replace(chr(92), '/').replace("'", "''")
            con.execute(f"COPY (SELECT * FROM _frame) TO '{target}' "
                        "(FORMAT PARQUET, COMPRESSION ZSTD)")
        finally:
            con.close()
    else:
        frame.to_parquet(path, index=False)
    return path


def resample_bars(frame: pd.DataFrame, rule: str = '5min') -> pd.DataFrame:
    """多周期重采样（开高低收量；索引按 datetime）"""
    frame = normalize_ohlcv(frame)
    if frame.empty:
        return frame
    indexed = frame.set_index('datetime')
    grouped = indexed.resample(str(rule)).agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last',
        'volume': 'sum'})
    grouped = grouped.dropna(subset=['close']).reset_index()
    extra = [col for col in ('symbol', 'open_interest', 'amount')
             if col in frame.columns]
    if extra and 'symbol' in extra:
        grouped['symbol'] = str(frame['symbol'].iloc[-1])
    return grouped[['datetime', 'open', 'high', 'low', 'close', 'volume']
                   + [col for col in extra if col != 'symbol']]


def align_timeframes(frames: Dict[str, pd.DataFrame],
                     rule: str = '5min') -> Dict[str, pd.DataFrame]:
    """多周期对齐：每个 DataFrame 各自重采样，再按并集时间外连接"""
    out: Dict[str, pd.DataFrame] = {}
    for name, frame in (frames or {}).items():
        part = resample_bars(frame, rule)
        part = part.set_index('datetime').add_prefix(f'{name}.')
        out[name] = part
    if not out:
        return {}
    joined = None
    for part in out.values():
        joined = part if joined is None else joined.join(part, how='outer')
    joined = joined.reset_index().sort_values('datetime')
    return {'joined': joined}


# ---------------------------------------------------------------- 质量
def quality_report(frame: pd.DataFrame) -> Dict[str, Any]:
    """数据质量检查（返回分数 0~100 + 明细；不修改输入）"""
    frame = normalize_ohlcv(frame)
    issues: List[Dict[str, Any]] = []

    def add(kind: str, level: str, count: int, detail: str) -> None:
        if count:
            issues.append({'kind': kind, 'level': level,
                           'count': int(count), 'detail': detail})

    total = len(frame)
    if not total:
        return {'rows': 0, 'score': 0.0, 'ok': False, 'issues': [
            {'kind': 'empty', 'level': 'error', 'count': 0,
             'detail': '没有数据'}]}

    for key in COLUMNS:
        if key not in frame.columns:
            add('missing_column', 'error', 1, f'缺少 {key} 列')
    missing = frame[['open', 'high', 'low', 'close']].isna().any(axis=1)
    add('missing_price', 'error', int(missing.sum()), 'OHLC 有空值')

    invalid = ((frame['high'] < frame['low'])
               | (frame['high'] < frame['close'])
               | (frame['low'] > frame['close'])
               | (frame['high'] < frame['open'])
               | (frame['low'] > frame['open']))
    add('ohlc_inconsistent', 'error', int(invalid.sum()),
        'high/low 与 open/close 不自洽')

    duplicate = frame['datetime'].duplicated().sum()
    add('duplicate_time', 'warning', int(duplicate), '同一时间多根 K 线')
    if not frame['datetime'].is_monotonic_increasing:
        add('unordered_time', 'warning', 1, '时间没有升序')
    if len(frame) > 1:
        deltas = frame['datetime'].diff().dt.total_seconds().dropna()
        if len(deltas):
            median = float(deltas.median() or 0)
            gaps = int((deltas > max(1.0, median * 6)).sum())
            add('time_gap', 'warning', gaps,
                f'相邻间隔超过 {max(1.0, median * 6):.0f}s')
    zero_volume = int((frame['volume'].fillna(0) <= 0).sum())
    add('zero_volume', 'info', zero_volume, '成交量为 0')

    if len(frame) > 2:
        change = frame['close'].pct_change(fill_method=None).replace(
            [np.inf, -np.inf], np.nan)
        spikes = int((change.abs() > 0.2).sum())
        add('price_spike', 'warning', spikes, '单根涨跌超过 20%')

    weights = {'error': 12, 'warning': 4, 'info': 1}
    penalty = 0.0
    for issue in issues:
        ratio = min(1.0, issue['count'] / max(1, total))
        penalty += weights[issue['level']] * (0.25 + ratio)
    score = round(max(0.0, 100.0 - penalty), 1)
    return {
        'rows': total,
        'from': str(frame['datetime'].iloc[0]),
        'to': str(frame['datetime'].iloc[-1]),
        'score': score,
        'ok': not any(item['level'] == 'error' for item in issues),
        'issues': issues,
        'missing': int(missing.sum()),
        'duplicate': int(duplicate),
    }


# ---------------------------------------------------------------- 主力 / 复权
def dominant_contracts(frames: Dict[str, pd.DataFrame],
                       *, min_rows: int = 1) -> List[str]:
    """按成交量和行数挑每个时间段的主力（简单但可解释）"""
    score: Dict[str, float] = {}
    for name, frame in (frames or {}).items():
        if frame is None or frame.empty or len(frame) < min_rows:
            continue
        score[name] = float(frame['volume'].fillna(0).sum())
    return [name for name, _value in sorted(score.items(),
                                            key=lambda item: item[1],
                                            reverse=True)]


def roll_contracts(frames: Dict[str, pd.DataFrame], *,
                   mode: str = 'ratio',
                   volume_column: str = 'volume') -> pd.DataFrame:
    """换月拼接 + 复权。

    Args:
        frames: ``{合约名: DataFrame}``（只需标准 OHLCV）
        mode: ``none`` / ``difference`` / ``ratio``
        volume_column: 用来判断主力切换的列

    规则：按时间遍历所有合约，**当前 K 线里成交量最大**的合约当主力；
    切换时按前一主力最后收盘价对新合约做价差 / 比例复权，然后把
    历史部分整体平移，得到连续价格。
    """
    prepared: Dict[str, pd.DataFrame] = {}
    for name, frame in (frames or {}).items():
        part = normalize_ohlcv(frame)
        if part.empty:
            continue
        part['_symbol'] = name
        part['_volume'] = pd.to_numeric(
            part.get(volume_column, part.get('volume')), errors='coerce'
        ).fillna(0.0)
        prepared[name] = part
    if not prepared:
        return pd.DataFrame(columns=list(COLUMNS) + ['symbol'])

    all_times = sorted({time_value for part in prepared.values()
                        for time_value in part['datetime']})
    rows: List[Dict[str, Any]] = []
    active = ''
    adjust = 0.0          # 价差 / 比例累计
    previous_close: Optional[float] = None
    for stamp in all_times:
        candidates = []
        for name, part in prepared.items():
            match = part[part['datetime'] == stamp]
            if not match.empty:
                candidates.append((name, match.iloc[0]))
        if not candidates:
            continue
        candidates.sort(key=lambda item: float(item[1].get('_volume') or 0),
                        reverse=True)
        name, row = candidates[0]
        if name != active:
            if active and previous_close is not None:
                new_close = float(row.get('close') or 0)
                if mode == 'ratio' and new_close:
                    adjust = previous_close / new_close
                elif mode == 'difference':
                    adjust = previous_close - new_close
            active = name
        close = float(row.get('close') or 0)
        if mode == 'none':
            price = close
        elif mode == 'difference':
            price = close + adjust
        else:
            price = close * adjust if adjust else close
        base_ratio = (price / close) if close else 1.0
        rows.append({
            'datetime': stamp,
            'open': float(row.get('open') or 0) * base_ratio,
            'high': float(row.get('high') or 0) * base_ratio,
            'low': float(row.get('low') or 0) * base_ratio,
            'close': price,
            'volume': float(row.get('_volume') or 0),
            'symbol': name,
        })
        previous_close = close
    return pd.DataFrame(rows, columns=list(COLUMNS) + ['symbol'])


# ---------------------------------------------------------------- Tick
def ticks_to_bars(ticks: pd.DataFrame, *, seconds: int = 60,
                  price_column: str = 'last_price') -> pd.DataFrame:
    """逐笔 / 快照 → K 线（自动识别时间列；支持买卖盘列）"""
    if ticks is None or ticks.empty:
        return pd.DataFrame(columns=COLUMNS)
    frame = ticks.copy()
    rename = {}
    lowered = {str(col).strip().lower(): col for col in frame.columns}
    for alias in ('datetime', 'date_time', 'time', 'timestamp', 'trade_time'):
        if alias in lowered:
            rename[lowered[alias]] = 'datetime'
            break
    for alias in (price_column.lower(), 'last_price', 'last', 'price',
                  'close'):
        if alias in lowered:
            rename[lowered[alias]] = 'price'
            break
    for alias in ('volume', 'vol', 'trade_volume'):
        if alias in lowered:
            rename[lowered[alias]] = 'volume'
            break
    frame = frame.rename(columns=rename)
    if 'datetime' not in frame.columns or 'price' not in frame.columns:
        raise ValueError('Tick 数据需要时间列和价格列')
    frame['datetime'] = pd.to_datetime(frame['datetime'], errors='coerce')
    frame['price'] = pd.to_numeric(frame['price'], errors='coerce')
    frame = frame.dropna(subset=['datetime', 'price']).sort_values('datetime')
    if 'volume' not in frame.columns:
        frame['volume'] = 1.0
    frame['volume'] = pd.to_numeric(frame['volume'], errors='coerce').fillna(0)
    rule = f'{max(1, int(seconds))}s'
    grouped = frame.set_index('datetime').resample(rule).agg({
        'price': ['first', 'max', 'min', 'last'], 'volume': 'sum'})
    grouped.columns = ['open', 'high', 'low', 'close', 'volume']
    grouped = grouped.dropna(subset=['close']).reset_index()
    return grouped[list(COLUMNS)]


def book_snapshot(ticks: pd.DataFrame, index: int = -1) -> Dict[str, Any]:
    """从带买卖盘列的 Tick 表里取一条盘口快照（回放用）"""
    if ticks is None or ticks.empty:
        return {}
    row = ticks.iloc[index].to_dict()
    out = {'datetime': str(row.get('datetime') or row.get('time') or '')}
    for level in range(1, 6):
        for side in ('bid', 'ask'):
            for key in (f'{side}_price{level}', f'{side}{level}',
                        f'{side}_{level}'):
                if key in row:
                    out[f'{side}_price{level}'] = row.get(key)
                    break
            for key in (f'{side}_volume{level}', f'{side}_vol{level}',
                        f'{side}_size{level}'):
                if key in row:
                    out[f'{side}_volume{level}'] = row.get(key)
                    break
    return out


# ---------------------------------------------------------------- 目录
class DataCatalog:
    """本地行情库：扫描 CSV / Parquet，缓存元数据 + 质量报告"""

    def __init__(self, folders: Optional[Sequence[str]] = None, *,
                 recursive: bool = True):
        self.folders: List[str] = []
        for folder in (folders if folders is not None else default_folders()):
            if folder and os.path.isdir(str(folder)):
                path = str(folder)
                if path not in self.folders:
                    self.folders.append(path)
        self.recursive = bool(recursive)
        self._lock = threading.RLock()
        self._items: List[Dict[str, Any]] = []
        self._quality: Dict[str, Dict[str, Any]] = {}
        self._frames: Dict[str, pd.DataFrame] = {}
        self._at = 0.0

    def add_folder(self, folder: str) -> bool:
        folder = str(folder or '')
        if folder and os.path.isdir(folder) and folder not in self.folders:
            self.folders.append(folder)
            self._at = 0.0
            return True
        return False

    def files(self) -> List[str]:
        out: List[str] = []
        for folder in self.folders:
            pattern = '**/*' if self.recursive else '*'
            for path in glob.glob(os.path.join(folder, pattern),
                                  recursive=self.recursive):
                if os.path.splitext(path)[1].lower() in (
                        '.csv', '.parquet', '.pq', '.tsv'):
                    if path not in out:
                        out.append(path)
        return sorted(out, key=os.path.getmtime, reverse=True)

    def refresh(self, *, force: bool = False) -> List[Dict[str, Any]]:
        now = time.time()
        if not force and self._items and now - self._at < 3.0:
            return list(self._items)
        items: List[Dict[str, Any]] = []
        for path in self.files():
            name = os.path.splitext(os.path.basename(path))[0]
            item = {'name': name, 'path': path,
                    'format': os.path.splitext(path)[1].lstrip('.').lower(),
                    'size': os.path.getsize(path),
                    'mtime': os.path.getmtime(path),
                    'rows': 0, 'from': '', 'to': '', 'score': None}
            try:
                frame = read_table(path)
                item['rows'] = int(len(frame))
                if len(frame):
                    item['from'] = str(frame['datetime'].iloc[0])
                    item['to'] = str(frame['datetime'].iloc[-1])
            except Exception as error:                            # noqa: BLE001
                item['error'] = f'{type(error).__name__}: {error}'
            items.append(item)
        with self._lock:
            self._items = items
            self._at = now
        return list(items)

    def items(self) -> List[Dict[str, Any]]:
        return self.refresh()

    def find(self, name: str) -> Optional[Dict[str, Any]]:
        text = str(name or '')
        for item in self.items():
            if item['name'] == text or item['path'] == text:
                return item
        return None

    def load(self, name: str) -> pd.DataFrame:
        item = self.find(name)
        if not item:
            raise FileNotFoundError(f'行情库里没有：{name}')
        return read_table(item['path'], symbol=item['name'])

    def quality(self, name: str, *, force: bool = False) -> Dict[str, Any]:
        key = str(name)
        if not force and key in self._quality:
            return self._quality[key]
        frame = self.load(key)
        report = quality_report(frame)
        with self._lock:
            self._quality[key] = report
        return report

    def resample(self, name: str, rule: str = '5min') -> pd.DataFrame:
        return resample_bars(self.load(name), rule)

    def roll(self, names: Iterable[str], *, mode: str = 'ratio') -> pd.DataFrame:
        frames = {name: self.load(name) for name in names}
        return roll_contracts(frames, mode=mode)

    def ticks(self, name: str, *, seconds: int = 60) -> pd.DataFrame:
        return ticks_to_bars(self.load(name), seconds=seconds)

    def query(self, sql: str, limit: int = 2000) -> List[Dict[str, Any]]:
        """只读 SQL（DuckDB）；CSV / Parquet 都可直接 ``SELECT``"""
        text = str(sql or '').strip()
        if not re.match(r'^(select|with)\b', text, re.I):
            raise ValueError('只允许 SELECT / WITH 查询')
        if not duckdb_available():
            raise RuntimeError('未安装 duckdb：pip install duckdb')
        import duckdb
        con = duckdb.connect()
        try:
            for item in self.items():
                path = item['path'].replace(chr(92), '/').replace("'", "''")
                view = re.sub(r'\W', '_', item['name'])
                reader = ('read_parquet' if item['format'] in ('parquet', 'pq')
                          else 'read_csv_auto')
                try:
                    con.execute(
                        f"CREATE OR REPLACE VIEW \"{view}\" AS "
                        f"SELECT * FROM {reader}('{path}')")
                except Exception:                                # noqa: BLE001
                    continue
            frame = con.execute(text).fetchdf()
            if limit:
                frame = frame.head(int(limit))
            return json.loads(frame.to_json(orient='records',
                                            date_format='iso'))
        finally:
            con.close()

    def export_parquet(self, name: str, path: str = '') -> str:
        frame = self.load(name)
        path = path or os.path.join(self.folders[0] if self.folders else '.',
                                    f'{name}.parquet')
        return to_parquet(frame, path)

    def snapshot(self) -> Dict[str, Any]:
        items = self.items()
        return {'type': 'datahub', 'folders': list(self.folders),
                'duckdb': duckdb_available(),
                'items': items,
                'quality': dict(self._quality)}
