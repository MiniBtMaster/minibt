"""本地 K 线数据 + 本地模拟账户（`minibt desk` 的「本地图表」用）。

设计
----
* **数据源**：minibt 包内 `minibt/data/test/*.csv`（默认 3 个）+
  `~/.minibt/datas/*.csv` + 用户手动添加的文件夹；
* CSV 表头沿用 minibt 的格式：``datetime, open, high, low, close, volume``
  （``date / time / vol`` 等常见别名也认）；
* **静态**：本地图表只读一次 CSV，前端回放完全在本地逐根播放，不联网；
* **模拟账户**：一个本地账户（默认 10 万），买卖/平仓即时按给定价格成交，
  持仓 / 委托 / 成交 / 浮盈都能在 desk 的「交易账户」页看到。
"""
from __future__ import annotations

import contextlib
import glob
import json
import math
import os
import sqlite3
import threading
import time
from typing import Any, Optional

#: 默认（包内）数据目录由 minibt.data.tools 提供
from ..data import tools as _data_tools

#: 用户添加的数据文件夹记录
FOLDERS_FILE = os.path.join(
    os.path.expanduser('~'), '.minibt', 'desk_local_folders.json')
#: 本地图表状态（每个数据选过哪些指标）
STATE_FILE = os.path.join(
    os.path.expanduser('~'), '.minibt', 'desk_local_state.json')

#: 单文件最多读多少根（防止误选超大 CSV 卡死前端）
MAX_BARS = 20000

_ALIASES = {
    'datetime': ('datetime', 'date_time', 'time', 'date', 'timestamp'),
    'open': ('open', 'o'),
    'high': ('high', 'h'),
    'low': ('low', 'l'),
    'close': ('close', 'c'),
    'volume': ('volume', 'vol', 'v'),
}


def _write_json(path: str, payload: Any) -> None:
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except Exception:                                            # noqa: BLE001
        ...


def _read_json(path: str, fallback: Any) -> Any:
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except Exception:                                            # noqa: BLE001
        return fallback


def _pick(columns: dict[str, str], name: str) -> Optional[str]:  # noqa: UP045
    for alias in _ALIASES.get(name, (name,)):
        if alias in columns:
            return columns[alias]
    return None


def _human_size(size: int) -> str:
    value = float(size or 0)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'
        value /= 1024
    return f'{value:.1f} GB'


#: 通达信周期 → 中文（搜索列表 / 设置页 ✓）
_TDX_PERIOD_LABELS = {'.day': '日线', '.lc5': '5 分钟', '.lc1': '1 分钟'}


class LocalDataError(RuntimeError):
    """本地 CSV 不合法 / 文件夹不存在（给前端 toast 用 ✓）"""


class LocalStore:
    """本地 CSV 列表 + 读取（带 mtime 缓存 ✓）"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[str, tuple] = {}
        folders = _read_json(FOLDERS_FILE, [])
        self.folders: list[str] = [str(item) for item in folders
                                   if isinstance(item, str) and os.path.isdir(item)]
        # ★ 并入 `LocalDatas` 登记的**外部文件夹**（`~/.minibt/datas_external.json`）
        #   → 「+ 数据文件夹」登记过一次，之后重开 desk 自动就有 ✓
        try:
            from ..data.tools import external_paths
            for path in external_paths():
                folder = str(path)
                if os.path.isfile(folder):
                    folder = os.path.dirname(folder)     # 单个 CSV → 其所在目录
                if os.path.isdir(folder) and folder not in self.folders:
                    self.folders.append(folder)
        except Exception:                                        # noqa: BLE001
            ...
        state = _read_json(STATE_FILE, {})
        self.state: dict[str, dict] = state if isinstance(state, dict) else {}

    # ------------------------------------------------------------ 列表
    def items(self) -> list[dict]:
        """内置 + 用户目录 + 已添加文件夹里的 CSV（按名字去重 ✓）"""
        seen: dict[str, dict] = {}

        def add(path: str, source: str) -> None:
            name = os.path.splitext(os.path.basename(path))[0]
            if not name or name in seen:
                return
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            meta = self._header(path)
            if not meta.get('valid'):
                return                      # 表头不符合 minibt K 线格式 → 跳过
            seen[name] = {
                'key': name,
                'name': name,
                'path': path,
                'source': source,
                'symbol': meta.get('symbol') or name,
                'duration': meta.get('duration') or 60,
                'rows': meta.get('rows') or 0,
                'size': size,
                'size_text': _human_size(size),
            }

        # 1) 包内基础数据（默认 3 个）
        package_dir = getattr(_data_tools, '_PACKAGE_DATAS', '')
        if package_dir and os.path.isdir(package_dir):
            for path in sorted(glob.glob(os.path.join(package_dir, '*.csv'))):
                add(path, '内置')
        # 2) 用户目录（~/.minibt/datas）
        user_dir = _data_tools.user_datas_dir()
        if os.path.isdir(user_dir):
            for path in sorted(glob.glob(os.path.join(user_dir, '*.csv'))):
                add(path, '用户')
        # 3) 手动添加的文件夹
        for folder in self.folders:
            if not os.path.isdir(folder):
                continue
            label = os.path.basename(folder.rstrip('\\/')) or folder
            for path in sorted(glob.glob(os.path.join(folder, '*.csv'))):
                add(path, label)
        return sorted(seen.values(), key=lambda item: (
            0 if item['source'] == '内置' else 1, item['name'].lower()))

    # ------------------------------------------------------------ 通达信
    def tdx_roots(self) -> list[str]:
        """通达信数据根目录：设置里的 `tdx_root` + 已添加文件夹里"像 TDX"的 ✓"""
        from ..data import tdx as _tdx

        candidates: list[str] = []
        try:
            from . import user_prefs as _prefs
            root = str((_prefs.settings() or {}).get('tdx_root') or '').strip()
            if root:
                candidates.append(root)
        except Exception:                                        # noqa: BLE001
            ...
        candidates.extend(self.folders)
        return _tdx.roots_from(candidates)

    def _tdx_table(self, refresh: bool = False) -> dict:
        """扫所有通达信根 → `{后缀: [item]}`（缓存 60 s，几千文件也很快 ✓）"""
        import time as _time

        from ..data import tdx as _tdx

        roots = tuple(self.tdx_roots())
        stamp = (_time.time() // 60, roots)
        with self._lock:
            cached = getattr(self, '_tdx_cache', None)
            if cached and not refresh and cached[0] == stamp:
                return cached[1]
        table: dict = {}
        for root in roots:
            try:
                scanned = _tdx.scan_root(root)
            except Exception:                                    # noqa: BLE001
                continue
            for suffix, items in scanned.items():
                bucket = table.setdefault(suffix, [])
                seen = {item['id'] for item in bucket}
                for item in items:
                    if item['id'] in seen:
                        continue
                    item = dict(item)
                    item['root'] = root
                    bucket.append(item)
                    seen.add(item['id'])
        for suffix in table:
            table[suffix].sort(key=lambda item: (item['market'], item['code']))
        with self._lock:
            self._tdx_cache = (stamp, table)
        return table

    def tdx_payload(self) -> dict:
        """`local_data` 补丁里的通达信信息（**只给数量，不列代码** ✓）"""
        from ..data import tdx as _tdx

        table = self._tdx_table()
        counts = {suffix.lstrip('.'): len(items)
                  for suffix, items in table.items()}
        return {'roots': self.tdx_roots(),
                'counts': counts,
                'periods': [{'key': suffix.lstrip('.'),
                             'label': _TDX_PERIOD_LABELS[suffix],
                             'count': counts.get(suffix.lstrip('.'), 0)}
                            for suffix in _tdx.PERIODS]}

    def tdx_list(self, text: str = '', period: str = 'day',
                 offset: int = 0, limit: int = 50) -> dict:
        """**分页**查通达信代码（选中才读文件，列表只给元信息 ✓）"""
        from ..data import tdx as _tdx

        suffix = _tdx._suffix_of(period) or '.day'
        items = list(self._tdx_table().get(suffix) or [])
        needle = str(text or '').strip().lower()
        if needle:
            items = [item for item in items
                     if needle in item['code'].lower()
                     or needle in item['market'].lower()]
        total = len(items)
        start = max(0, int(offset or 0))
        size = max(1, min(500, int(limit or 50)))
        page = items[start:start + size]
        rows = []
        for item in page:
            rows.append({
                'key': item['id'],
                'name': item['id'],
                'symbol': item['id'],
                'code': item['code'],
                'market': item['market'],
                'period': suffix.lstrip('.'),
                'source': '通达信',
                'path': item['path'],
                'label': f"{item['market']}.{item['code']} · "
                         f"{_TDX_PERIOD_LABELS[suffix]}",
            })
        return {'type': 'local_tdx', 'items': rows, 'total': total,
                'offset': start, 'limit': size,
                'has_more': start + len(rows) < total,
                'period': suffix.lstrip('.'),
                'roots': self.tdx_roots()}

    def _tdx_frame(self, name: str):
        """`tdx:sh600000@day` → DataFrame（minibt K 线格式，datetime=int64 纳秒）"""
        from ..data import tdx as _tdx

        parsed = _tdx.split_tdx_id(name)
        if not parsed:
            return None
        market, code, suffix = parsed
        wanted = _tdx.tdx_id(market, code, suffix)
        for item in self._tdx_table().get(suffix) or []:
            if item['id'] != wanted:
                continue
            frame = _tdx.load_path(item['path'])
            frame = frame.tail(MAX_BARS).reset_index(drop=True)
            frame['datetime'] = frame['datetime'].astype('int64')
            return frame
        raise LocalDataError(f'通达信里找不到 {name}（根目录：'
                             f'{self.tdx_roots() or "未设置"}）')

    def _header(self, path: str) -> dict:
        """只读表头（列表页用，不加载整表 ✓）"""
        try:
            import pandas as pd
            frame = pd.read_csv(path, nrows=2)
        except Exception:  # noqa: BLE001
            return {}
        columns = {str(col).strip().lower(): str(col) for col in frame.columns}
        if _pick(columns, 'datetime') is None:
            return {}
        if any(_pick(columns, key) is None
               for key in ('open', 'high', 'low', 'close')):
            return {}
        meta: dict[str, Any] = {'valid': True}
        for key in ('symbol', 'duration'):
            col = columns.get(key)
            if col and len(frame):
                try:
                    value = frame[col].iloc[0]
                    meta[key] = (int(float(value)) if key == 'duration'
                                 else str(value))
                except Exception:                                # noqa: BLE001
                    ...
        return meta

    # ------------------------------------------------------------ 文件夹
    def add_folder(self, path: str) -> list[dict]:
        folder = os.path.abspath(os.path.expanduser(str(path or '').strip()))
        if not folder or not os.path.isdir(folder):
            raise LocalDataError(f'文件夹不存在：{path}')
        with self._lock:
            if folder not in self.folders:
                self.folders.append(folder)
                _write_json(FOLDERS_FILE, self.folders)
        # ★ 同时登记到 minibt 的 `LocalDatas`（这样代码里也能用
        #   `LocalDatas.名字` / `get_kline('名字')` 按路径读取 ✓）
        try:
            from ..data.tools import add_external
            # 文件夹方式登记（扫描一层，逐个校验 `FILED.ALL` 表头 ✓）
            add_external(folder, rewrite=True)
        except Exception:                                        # noqa: BLE001
            ...
        return self.items()

    def remove_folder(self, path: str) -> list[dict]:
        folder = os.path.abspath(os.path.expanduser(str(path or '').strip()))
        with self._lock:
            self.folders = [item for item in self.folders if item != folder]
            _write_json(FOLDERS_FILE, self.folders)
        return self.items()

    # ------------------------------------------------------------ 读取
    def path_of(self, name: str) -> Optional[str]:  # noqa: UP045
        from ..data import tdx as _tdx

        if _tdx.split_tdx_id(name):
            parsed = _tdx.split_tdx_id(name)
            market, code, suffix = parsed
            wanted = _tdx.tdx_id(market, code, suffix)
            for item in self._tdx_table().get(suffix) or []:
                if item['id'] == wanted:
                    return item['path']
            return None
        for item in self.items():
            if item['name'] == name:
                return item['path']
        if os.path.isfile(name):
            return name
        return None

    def frame(self, name: str):
        """读成 minibt 指标能吃的 DataFrame（`datetime` = int64 纳秒 ✓）

        `name` 可以是 CSV 名字，也可以是**通达信 id**（`tdx:sh600000@day`）✓
        """
        from ..data import tdx as _tdx

        if _tdx.split_tdx_id(name):
            return self._tdx_frame(name)
        path = self.path_of(name)
        if not path:
            raise LocalDataError(f'找不到本地数据：{name}')
        try:
            stamp = os.path.getmtime(path)
        except OSError:
            stamp = 0.0
        key = os.path.abspath(path)
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] == stamp:
                return cached[1].copy()
        try:
            import pandas as pd
        except Exception as error:
            raise LocalDataError(f'需要 pandas 才能读取 CSV：{error!r}') from error
        try:
            frame = pd.read_csv(path)
        except Exception as error:
            raise LocalDataError(f'读取 CSV 失败：{error!r}') from error
        columns = {str(col).strip().lower(): str(col) for col in frame.columns}
        dt_col = _pick(columns, 'datetime')
        if dt_col is None:
            raise LocalDataError('CSV 缺少 datetime 列（minibt K 线格式）')
        out = pd.DataFrame()
        try:
            out['datetime'] = pd.to_datetime(frame[dt_col], errors='coerce')
        except Exception as error:
            raise LocalDataError(f'datetime 解析失败：{error!r}') from error
        for target in ('open', 'high', 'low', 'close'):
            column = _pick(columns, target)
            if column is None:
                raise LocalDataError(f'CSV 缺少 {target} 列（minibt K 线格式）')
            out[target] = pd.to_numeric(frame[column], errors='coerce')
        volume_col = _pick(columns, 'volume')
        out['volume'] = (pd.to_numeric(frame[volume_col], errors='coerce')
                         if volume_col else 0)
        out = out.dropna(subset=['datetime', 'open', 'high', 'low', 'close'])
        out = out.sort_values('datetime').drop_duplicates(
            subset=['datetime'], keep='last').reset_index(drop=True)
        if out.empty:
            raise LocalDataError('CSV 里没有有效的 K 线行')
        out = out.tail(MAX_BARS).reset_index(drop=True)
        # minibt 指标（`_stamps` / `_kline_of`）吃 int64 纳秒 ✓
        out['datetime'] = out['datetime'].astype('int64')
        symbol_col = columns.get('symbol')
        symbol = (str(frame[symbol_col].iloc[0])
                  if symbol_col and len(frame) else
                  os.path.splitext(os.path.basename(path))[0])
        duration_col = columns.get('duration')
        duration = 60
        if duration_col and len(frame):
            try:
                duration = int(float(frame[duration_col].iloc[0]))
            except Exception:                                    # noqa: BLE001
                duration = 60
        if not duration_col:
            diff = out['datetime'].diff().dropna()
            if len(diff):
                duration = max(1, int(round(diff.median() / 1_000_000_000)))  # noqa: RUF046
        out['symbol'] = symbol
        out['duration'] = duration
        price_col = columns.get('price_tick')
        price_tick = 0.01
        if price_col:
            try:
                values = pd.to_numeric(frame[price_col], errors='coerce')
                price_tick = float(values.dropna().iloc[0])
            except Exception:                                    # noqa: BLE001
                price_tick = 0.01
        out['price_tick'] = price_tick
        mult_col = columns.get('volume_multiple')
        volume_multiple = 1.0
        if mult_col:
            try:
                values = pd.to_numeric(frame[mult_col], errors='coerce')
                volume_multiple = float(values.dropna().iloc[0])
            except Exception:                                    # noqa: BLE001
                volume_multiple = 1.0
        out['volume_multiple'] = volume_multiple
        with self._lock:
            self._cache[key] = (stamp, out.copy())
        return out

    def info(self, name: str) -> dict:
        from ..data import tdx as _tdx

        if _tdx.split_tdx_id(name):
            frame = self.frame(name)
            return {'key': name, 'name': name, 'path': self.path_of(name) or '',
                    'source': '通达信',
                    'symbol': str(frame['symbol'].iloc[0]),
                    'duration': int(frame['duration'].iloc[0]),
                    'rows': len(frame), 'size': 0, 'size_text': ''}
        for item in self.items():
            if item['name'] == name:
                try:
                    frame = self.frame(name)
                    item = dict(item)
                    item['rows'] = len(frame)
                    item['duration'] = int(frame['duration'].iloc[0])
                    item['symbol'] = str(frame['symbol'].iloc[0])
                except Exception:                                # noqa: BLE001
                    ...
                return item
        raise LocalDataError(f'找不到本地数据：{name}')

    def bars(self, name: str) -> list[dict]:
        from . import protocol as _protocol
        return _protocol.bars_from_frame(self.frame(name))

    # ------------------------------------------------------------ 指标选择
    #: 本地图表支持多布局：指标按 **(数据名, 格号)** 分开存。
    #: 旧状态只有 ``indicators`` → 当作**第 1 格**的旧数据兼容 ✓。
    def _cell_indicators(self, record: Any, cell: int) -> list[dict]:
        if not isinstance(record, dict):
            return []
        cells = record.get('cells')
        if isinstance(cells, dict):
            row = cells.get(str(int(cell)))
            items = row.get('indicators') if isinstance(row, dict) else None
            return [dict(item) for item in (items or [])
                    if isinstance(item, dict)]
        # 旧格式：只有一格指标
        if int(cell) != 0:
            return []
        items = record.get('indicators')
        return [dict(item) for item in (items or [])
                if isinstance(item, dict)]

    def indicators(self, name: str, cell: int = 0) -> list[dict]:
        """某条本地数据在**第 cell 格**选过的指标（多布局互不影响 ✓）"""
        return self._cell_indicators(self.state.get(name) or {}, cell)

    def strategy(self, name: str) -> dict[str, Any]:
        """该本地数据当前挂着的策略（name / path；没有 → 空 dict ✓）"""
        record = self.state.get(str(name)) or {}
        value = record.get('strategy')
        return dict(value) if isinstance(value, dict) else {}

    def set_strategy(self, name: str, strategy: Optional[dict]) -> None:  # noqa: UP045
        """记住 / 清除本地数据上的策略（布局重载后也能恢复策略线 ✓）"""
        name = str(name or '')
        if not name:
            return
        record = dict(self.state.get(name) or {})
        if strategy and (strategy.get('path') or strategy.get('name')):
            record['strategy'] = {
                'name': str(strategy.get('name') or ''),
                'path': str(strategy.get('path') or ''),
            }
        else:
            record.pop('strategy', None)
        self.state[name] = record
        _write_json(STATE_FILE, self.state)

    def set_indicators(self, name: str, items: list[dict],
                       cell: int = 0) -> None:
        """写某一格的指标；旧 ``indicators`` 自动迁移到第 1 格 ✓"""
        cell = max(0, int(cell or 0))
        record = dict(self.state.get(name) or {})
        cells = dict(record.get('cells') or {})
        legacy = record.get('indicators')
        if isinstance(legacy, list) and '0' not in cells:
            cells['0'] = {'indicators': [dict(item) for item in legacy
                                         if isinstance(item, dict)]}
        cells[str(cell)] = {'indicators': [
            dict(item) for item in items if isinstance(item, dict)]}
        record.pop('indicators', None)
        record['cells'] = cells
        self.state[name] = record
        _write_json(STATE_FILE, self.state)


#: 权益曲线 / 累计盈亏曲线最多留多少个点
MAX_CURVE_POINTS = 1200


def default_sim_db() -> str:
    """本地期货模拟账户的 SQLite 路径（跟 `desk_user_prefs.json` 同目录）

    测试 monkeypatch `user_prefs.PREFS_FILE` 后会自动落到 tmp 目录，
    不会污染真实 `~/.minibt/desk_sim.sqlite3`。
    """
    override = str(os.environ.get('MINIBT_DESK_SIM_DB') or '')
    if override:
        return override
    # pytest 里默认不落真实 ~/.minibt，避免测试互相污染；
    # 要测持久化请显式传 db_path / 设置 MINIBT_DESK_SIM_DB ✓
    if os.environ.get('PYTEST_CURRENT_TEST'):
        return ''
    try:
        from . import user_prefs as _prefs
        folder = os.path.dirname(os.path.abspath(_prefs.PREFS_FILE))
    except Exception:                                            # noqa: BLE001
        folder = os.path.join(os.path.expanduser('~'), '.minibt')
    return os.path.join(folder or '.', 'desk_sim.sqlite3')


class LocalSimStore:
    """`LocalSim` 的 SQLite 持久化（零外部依赖）"""

    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(str(path))
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        with self._session() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                initial_cash REAL, cash REAL, realized REAL,
                commission REAL, seq INTEGER
            );
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY, long REAL, short REAL,
                avg_long REAL, avg_short REAL
            );
            CREATE TABLE IF NOT EXISTS prices (
                symbol TEXT PRIMARY KEY, price REAL
            );
            CREATE TABLE IF NOT EXISTS orders (
                seq INTEGER PRIMARY KEY, ts TEXT, symbol TEXT, side TEXT,
                offset TEXT, qty REAL, price REAL, status TEXT,
                left_qty REAL, fee REAL, is_close INTEGER
            );
            CREATE TABLE IF NOT EXISTS trades (
                seq INTEGER PRIMARY KEY, ts TEXT, symbol TEXT, side TEXT,
                offset TEXT, qty REAL, price REAL, status TEXT,
                fee REAL, realized REAL, is_close INTEGER
            );
            CREATE TABLE IF NOT EXISTS equity (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, value REAL
            );
            CREATE TABLE IF NOT EXISTS symbol_curve (
                id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT,
                ts TEXT, value REAL
            );
            CREATE TABLE IF NOT EXISTS symbol_stats (
                symbol TEXT PRIMARY KEY, json TEXT
            );
            CREATE TABLE IF NOT EXISTS specs (
                symbol TEXT PRIMARY KEY, decimals INTEGER,
                multiplier REAL, price_tick REAL, margin_rate REAL,
                slip REAL, fee_rule TEXT, source TEXT
            );
            """)

    @contextlib.contextmanager
    def _session(self):
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def load(self):
        with self._session() as conn:
            account = conn.execute(
                'SELECT * FROM account WHERE id = 1').fetchone()
            if account is None:
                return None
            data = {
                'initial_cash': account['initial_cash'],
                'cash': account['cash'],
                'realized': account['realized'],
                'commission': account['commission'],
                'seq': account['seq'],
                'positions': {}, 'prices': {}, 'orders': [], 'trades': [],
                'equity': [], 'symbol_curve': {}, 'symbol_stats': {},
                'specs': {},
            }
            for row in conn.execute('SELECT * FROM positions'):
                data['positions'][row['symbol']] = {
                    'long': row['long'] or 0.0,
                    'short': row['short'] or 0.0,
                    'avg_long': row['avg_long'] or 0.0,
                    'avg_short': row['avg_short'] or 0.0,
                }
            for row in conn.execute('SELECT * FROM prices'):
                data['prices'][row['symbol']] = row['price'] or 0.0
            for row in conn.execute(
                    'SELECT * FROM orders ORDER BY seq DESC LIMIT 200'):
                data['orders'].append({
                    'id': row['seq'], 'ts': row['ts'], 'symbol': row['symbol'],
                    'side': row['side'], 'offset': row['offset'],
                    'qty': row['qty'], 'price': row['price'],
                    'status': row['status'], 'left': row['left_qty'],
                    'fee': row['fee'], 'close': bool(row['is_close']),
                })
            data['orders'].reverse()
            for row in conn.execute(
                    'SELECT * FROM trades ORDER BY seq DESC LIMIT 200'):
                data['trades'].append({
                    'id': row['seq'], 'ts': row['ts'], 'symbol': row['symbol'],
                    'side': row['side'], 'offset': row['offset'],
                    'qty': row['qty'], 'price': row['price'],
                    'status': row['status'], 'fee': row['fee'],
                    'realized': row['realized'],
                    'close': bool(row['is_close']),
                })
            data['trades'].reverse()
            data['equity'] = [
                [row['ts'], row['value']] for row in conn.execute(
                    'SELECT ts, value FROM equity ORDER BY id')]
            for row in conn.execute(
                    'SELECT symbol, ts, value FROM symbol_curve ORDER BY id'):
                data['symbol_curve'].setdefault(row['symbol'], []).append(
                    [row['ts'], row['value']])
            for row in conn.execute('SELECT * FROM symbol_stats'):
                try:
                    data['symbol_stats'][row['symbol']] = json.loads(
                        row['json'] or '{}')
                except (TypeError, ValueError):
                    ...
            for row in conn.execute('SELECT * FROM specs'):
                try:
                    fee_rule = json.loads(row['fee_rule'] or 'null')
                except (TypeError, ValueError):
                    fee_rule = None
                data['specs'][row['symbol']] = {
                    'decimals': row['decimals'],
                    'multiplier': row['multiplier'],
                    'price_tick': row['price_tick'],
                    'margin_rate': row['margin_rate'],
                    'slip': row['slip'],
                    'fee_rule': fee_rule,
                    'source': row['source'],
                }
            return data

    def save(self, sim) -> None:
        with self._session() as conn:
            for table in ('account', 'positions', 'prices', 'orders',
                          'trades', 'equity', 'symbol_curve',
                          'symbol_stats', 'specs'):
                conn.execute(f'DELETE FROM {table}')
            conn.execute(
                'INSERT INTO account VALUES (1, ?, ?, ?, ?, ?)',
                (sim.initial_cash, sim.cash, sim.realized,
                 sim.commission, sim._seq))
            conn.executemany(
                'INSERT INTO positions VALUES (?, ?, ?, ?, ?)',
                [(symbol, book.get('long') or 0.0,
                  book.get('short') or 0.0, book.get('avg_long') or 0.0,
                  book.get('avg_short') or 0.0)
                 for symbol, book in sim.positions.items()])
            conn.executemany(
                'INSERT INTO prices VALUES (?, ?)',
                [(symbol, price) for symbol, price in sim.prices.items()])
            conn.executemany(
                'INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                [(int(item.get('id') or 0), item.get('ts') or '',
                  item.get('symbol') or '', item.get('side') or '',
                  item.get('offset') or '', float(item.get('qty') or 0.0),
                  float(item.get('price') or 0.0),
                  item.get('status') or '', float(item.get('left') or 0.0),
                  float(item.get('fee') or 0.0),
                  1 if item.get('close') else 0)
                 for item in sim.orders[-2000:]])
            conn.executemany(
                'INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                [(int(item.get('id') or 0), item.get('ts') or '',
                  item.get('symbol') or '', item.get('side') or '',
                  item.get('offset') or '', float(item.get('qty') or 0.0),
                  float(item.get('price') or 0.0),
                  item.get('status') or '', float(item.get('fee') or 0.0),
                  float(item.get('realized') or 0.0),
                  1 if item.get('close') else 0)
                 for item in sim.trades[-2000:]])
            conn.executemany(
                'INSERT INTO equity (ts, value) VALUES (?, ?)',
                [(str(row[0]), float(row[1])) for row in sim.equity])
            conn.executemany(
                'INSERT INTO symbol_curve (symbol, ts, value) VALUES (?, ?, ?)',
                [(symbol, str(row[0]), float(row[1]))
                 for symbol, curve in sim.symbol_curve.items()
                 for row in curve])
            conn.executemany(
                'INSERT INTO symbol_stats VALUES (?, ?)',
                [(symbol, json.dumps(stat, ensure_ascii=False))
                 for symbol, stat in sim.symbol_stats.items()])
            conn.executemany(
                'INSERT INTO specs VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                [(symbol,
                  int(sim.decimals.get(symbol, 2)),
                  float(sim.multipliers.get(symbol, 1.0)),
                  float(sim.price_ticks.get(symbol, 0.0)),
                  (None if symbol not in sim.margin_rates
                   else float(sim.margin_rates.get(symbol) or 0.0)),
                  float(sim.slips.get(symbol, 0.0)),
                  json.dumps(sim.fee_rules.get(symbol), ensure_ascii=False),
                  str(sim.spec_sources.get(symbol) or ''))
                 for symbol in set(sim.decimals) | set(sim.multipliers) |
                 set(sim.price_ticks) | set(sim.margin_rates) |
                 set(sim.slips) | set(sim.fee_rules) |
                 set(sim.spec_sources)])


class LocalSim:
    """本地内置模拟账户（静态 K 线 / 回放里都能下单 ✓）

    手续费（设置页「模拟账户」✓）：
    * ``fee_mode='fixed'``   → **每手固定** ``fee_value`` 元；
    * ``fee_mode='percent'`` → 成交额 **百分比** ``fee_value`` %；
    * ``fee_value=0`` 或 ``fee_mode=''`` → 不收手续费。
    """

    def __init__(self, initial_cash: float = 100000.0, fee_mode: str = 'fixed',
                 fee_value: float = 0.0, db_path: Optional[str] = None) -> None:  # noqa: UP045
        self._lock = threading.RLock()
        self._store = LocalSimStore(db_path) if db_path else None
        self._loading = False
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.realized = 0.0
        self.commission = 0.0
        self.fee_mode = str(fee_mode or 'fixed')
        self.fee_value = float(fee_value or 0.0)
        self.positions: dict[str, dict] = {}
        self.orders: list[dict] = []
        self.trades: list[dict] = []
        self.prices: dict[str, float] = {}
        self._seq = 0
        self.decimals: dict[str, int] = {}
        #: 合约乘数（每手多少单位）——期货盈亏必须乘它 ✓
        self.multipliers: dict[str, float] = {}
        #: minibt 合约参数：最小变动 / 保证金率 / 滑点 / 手续费规则
        self.price_ticks: dict[str, float] = {}
        self.margin_rates: dict[str, float] = {}
        self.slips: dict[str, float] = {}
        #: ``{symbol: {'mode': 'fixed'|'percent'|'tick', 'value': float}}``
        self.fee_rules: dict[str, dict] = {}
        #: ``'minibt'`` / ``'desk'``（只用于日志 / 排查）
        self.spec_sources: dict[str, str] = {}
        #: 权益曲线 ``[[时间, 权益], ...]``（开仓 / 价格变化都记一点 ✓）
        self.equity: list[list[Any]] = []
        #: 每个品种的累计平仓盈亏 ``{symbol: [[时间, 累计], ...]}``
        self.symbol_curve: dict[str, list[list[Any]]] = {}
        #: 每个品种的统计（交易次数 / 胜率 / 盈亏 / 手续费 ✓）
        self.symbol_stats: dict[str, dict] = {}
        #: 「这一根 K 线」的下标；下单后同一根不再覆盖开仓价 ✓
        self._bar: dict[str, Any] = {}
        self._hold: dict[str, Any] = {}
        #: 合约别名 → 账户里真正用的名字（`DCE.l2609` → `l2609_60`）✓
        #: 同一个合约可能有好几个写法：图表 CSV 名（`l2609_60` /
        #: `DCE.l2609_60`）、DataFrame 里的真实合约（`DCE.l2609`）、
        #: 策略里写的数据名（`test`）→ 不归一化就会出现「持仓在 A、
        #: 现价更新到 B、规格登记在 C」→ 浮盈恒 0 / 保证金 0 / 可用资金暴涨 ✗
        self.aliases: dict[str, str] = {}
        if self._store is not None:
            self._loading = True
            try:
                self._load()
            except Exception as error:                            # noqa: BLE001
                print(f'[desk] 读取本地模拟账户失败（用新账户）：{error!r}')
            finally:
                self._loading = False
            if not self.equity:
                self._mark_equity()

    def _load(self) -> None:
        """从 SQLite 恢复账户（没有记录 = 新账户）"""
        if self._store is None:
            return
        data = self._store.load()
        if not data:
            return
        try:
            self.initial_cash = float(data.get('initial_cash')
                                      or self.initial_cash)
        except (TypeError, ValueError):
            ...
        self.cash = float(data.get('cash') or self.initial_cash)
        self.realized = float(data.get('realized') or 0.0)
        self.commission = float(data.get('commission') or 0.0)
        self._seq = int(data.get('seq') or 0)
        self.positions = dict(data.get('positions') or {})
        self.prices = dict(data.get('prices') or {})
        self.orders = list(data.get('orders') or [])
        self.trades = list(data.get('trades') or [])
        self.equity = [list(item) for item in (data.get('equity') or [])]
        if len(self.equity) > MAX_CURVE_POINTS:
            self.equity = self.equity[-MAX_CURVE_POINTS:]
        self.symbol_curve = {
            str(key): [list(row) for row in (curve or [])][-MAX_CURVE_POINTS:]
            for key, curve in (data.get('symbol_curve') or {}).items()}
        self.symbol_stats = dict(data.get('symbol_stats') or {})
        for symbol, spec in (data.get('specs') or {}).items():
            if not isinstance(spec, dict):
                continue
            if spec.get('decimals') is not None:
                self.decimals[str(symbol)] = int(spec['decimals'])
            if spec.get('multiplier') is not None:
                self.multipliers[str(symbol)] = float(spec['multiplier'])
            if spec.get('price_tick') is not None:
                self.price_ticks[str(symbol)] = float(spec['price_tick'])
            if spec.get('margin_rate') is not None:
                self.margin_rates[str(symbol)] = float(spec['margin_rate'])
            if spec.get('slip') is not None:
                self.slips[str(symbol)] = float(spec['slip'])
            if spec.get('fee_rule') is not None:
                self.fee_rules[str(symbol)] = spec['fee_rule']
            if spec.get('source'):
                self.spec_sources[str(symbol)] = str(spec['source'])
        self._migrate_symbols()

    def _migrate_symbols(self) -> None:
        """老版本的持仓名（`DCE.l2609`）→ 对齐到规格里的名字（`l2609_60`）✓

        以前下单用的是 DataFrame 里的真实合约，规格却登记在 CSV 名上 →
        旧数据库里会留下 `DCE.l2609` 的持仓。归一后如果不迁，这些持仓
        会“消失”（现价 / 平仓都找不到）✗
        """
        specs = list(self.multipliers) + list(self.margin_rates)
        if not specs:
            return
        bare = self._norm_name

        def stem(name: str) -> str:
            text = bare(name).split('.')[-1]
            return self._strip_cycle(text)

        names = list(self.positions) + list(self.prices)
        for old in names:
            if old in specs:
                continue
            target = next((new for new in specs
                           if bare(new).split('.')[-1] == bare(old).split('.')[-1]
                           or stem(new) == stem(old)), '')
            if not target:
                continue
            self.register_alias(old, target)
            if old in self.positions:
                book = self.positions.pop(old)
                self.positions.setdefault(target, book)
            if old in self.prices:
                price = self.prices.pop(old)
                self.prices.setdefault(target, price)

    def save(self) -> None:
        """立即落盘（下单 / 重置 / 退出时调用；无 db 时是 no-op）"""
        if self._store is None or self._loading:
            return
        try:
            self._store.save(self)
        except Exception as error:                                # noqa: BLE001
            print(f'[desk] 保存本地模拟账户失败：{error!r}')

    # ------------------------------------------------------------ 设置
    def configure(self, initial_cash: Optional[float] = None,  # noqa: UP045
                  fee_mode: Optional[str] = None,  # noqa: UP045
                  fee_value: Optional[float] = None) -> None:  # noqa: UP045
        """改设置（初始现金变了 → 顺带重置账户 ✓）"""
        with self._lock:
            if fee_mode is not None:
                self.fee_mode = str(fee_mode or 'fixed')
            if fee_value is not None:
                try:
                    self.fee_value = max(0.0, float(fee_value))
                except (TypeError, ValueError):
                    self.fee_value = 0.0
            if initial_cash is not None:
                try:
                    value = float(initial_cash)
                except (TypeError, ValueError):
                    return
                if value <= 0:
                    return
                changed = abs(value - self.initial_cash) > 1e-9
                self.initial_cash = value
                if changed:
                    self.reset()
                self.save()

    def settings(self) -> dict:
        return {'initial_cash': self.initial_cash,
                'fee_mode': self.fee_mode,
                'fee_value': self.fee_value}

    def fee_of(self, qty: float, price: float, symbol: str = '') -> float:
        """这一笔的手续费

        * 有 minibt 合约规格 → 按 ``fixed / percent / tick`` 规则；
        * 没有 → 回退到设置页的全局 ``fixed / percent`` ✓
        """
        try:
            qty = abs(float(qty))
            price = float(price)
        except (TypeError, ValueError):
            return 0.0
        if qty <= 0 or price <= 0:
            return 0.0
        symbol = self.resolve(symbol)
        rule = self.fee_rules.get(str(symbol or ''))
        if rule is not None:
            try:
                value = float(rule.get('value') or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            if value <= 0:
                return 0.0
            mode = str(rule.get('mode') or 'fixed')
            multiple = self.multiplier(symbol)
            if mode == 'percent':
                return price * qty * multiple * value
            if mode == 'tick':
                return multiple * value * qty
            return value * qty
        if self.fee_value <= 0:
            return 0.0
        if str(self.fee_mode) == 'percent':
            # 设置页的 percent 是“百分比”（0.5 = 0.5%）✓
            return price * qty * self.multiplier(symbol) * self.fee_value / 100.0
        return self.fee_value * qty

    @staticmethod
    def _normalize_fee(commission: Optional[dict]) -> Optional[dict]:  # noqa: UP045
        """minibt 佣金字典 → ``{'mode','value'}``（没配置返回 None ✓）"""
        if not isinstance(commission, dict):
            return None
        for key in ('percent_commission', 'tick_commission',
                    'fixed_commission'):
            try:
                value = float(commission.get(key) or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0:
                return {'mode': key.split('_')[0], 'value': value}
        # 显式传了空 / 全 0 → 该合约不收手续费（不回退全局）✓
        return {'mode': 'fixed', 'value': 0.0}

    @staticmethod
    def _decimals_for_tick(tick: float) -> int:
        try:
            tick = float(tick)
        except (TypeError, ValueError):
            return 2
        if tick <= 0:
            return 2
        if tick >= 1:
            return 0
        return max(0, min(8, int(round(-math.log10(tick)))))  # noqa: RUF046

    # ------------------------------------------------------ 合约名归一化
    @staticmethod
    def _norm_name(name) -> str:
        return str(name or '').strip().upper()

    @staticmethod
    def _strip_cycle(text: str) -> str:
        """`L2609_60` → `L2609`（本地 CSV 名的周期后缀 ✓）"""
        text = str(text or '')
        head, sep, tail = text.rpartition('_')
        return head if sep and tail.isdigit() else text

    def _known_names(self) -> list:
        """账户里已登记过的规范名（positions / 规格 / 现价 ✓）"""
        names: list = list(self.aliases.values())
        for source in (self.positions, self.prices, self.multipliers,
                       self.price_ticks, self.margin_rates, self.slips,
                       self.fee_rules):
            names.extend(str(key) for key in source)
        seen: set = set()
        out: list = []
        for name in names:
            if name and name not in seen:
                seen.add(name)
                out.append(name)
        return out

    def resolve(self, symbol: str = '') -> str:
        """任何合约写法 → 账户里**真正用的名字** ✓

        优先级：显式别名 > 已登记名字（忽略大小写）> 同代码
        （`DCE.l2609` ≈ `l2609_60` 去周期后缀）> 原样返回。
        不认识的合约**绝不硬猜**（策略多合约时不能把 A 成交到 B 上 ✗）。
        """
        text = str(symbol or '')
        if not text:
            return text
        key = self._norm_name(text)
        target = self.aliases.get(key)
        if target:
            return str(target)
        names = self._known_names()
        for name in names:
            if self._norm_name(name) == key:
                return name
        bare = key.split('.')[-1]
        for name in names:
            if self._norm_name(name).split('.')[-1] == bare:
                return name
        stem = self._strip_cycle(bare)
        if stem != bare:
            for name in names:
                other = self._norm_name(name).split('.')[-1]
                if self._strip_cycle(other) == stem:
                    return name
        return text

    def register_alias(self, name: str, target: str = '') -> None:
        """登记别名 → 规范名（空名字直接忽略 ✓）"""
        name = str(name or '')
        if not name:
            return
        if not target:
            target = self.resolve(name) or name
        self.aliases[self._norm_name(name)] = str(target)

    def book(self, symbol: str = '') -> dict:
        """某个合约的持仓（别名自动归一；没有持仓 → 空 dict ✓）"""
        with self._lock:
            return self.positions.get(self.resolve(symbol)) or {}

    def clear_hold(self, symbol: str = '') -> None:
        """清掉「同一根不覆盖现价」的锁定（回放每推一根都用 ✓）"""
        with self._lock:
            self._hold.pop(self.resolve(symbol), None)

    def set_contract(self, symbol: str, volume_multiple=None,
                     decimals=None, *, price_tick=None, margin_rate=None,
                     commission=None, slip_point=None,
                     source: str = 'desk', alias=None) -> None:
        """登记合约参数（本地 CSV / 天勤 / minibt 策略配置 ✓）

        ``alias``：这个合约的**另一种写法**（DataFrame 里的 `DCE.l2609`）→
        之后 `set_price` / `order` 用哪种写法都能落到同一份持仓 ✓
        """
        symbol = self.resolve(str(symbol or ''))
        symbol = str(symbol or '')
        if not symbol:
            return
        with self._lock:
            self.register_alias(symbol, symbol)
            if alias:
                self.register_alias(str(alias), symbol)
            if price_tick is not None:
                try:
                    tick = float(price_tick)
                except (TypeError, ValueError):
                    tick = 0.0
                if tick > 0:
                    self.price_ticks[symbol] = tick
                    if decimals is None:
                        self.decimals[symbol] = self._decimals_for_tick(tick)
            if decimals is not None:
                try:
                    self.decimals[symbol] = int(decimals)
                except (TypeError, ValueError):
                    ...
            if volume_multiple is not None:
                try:
                    value = float(volume_multiple)
                except (TypeError, ValueError):
                    value = 0.0
                if value > 0:
                    self.multipliers[symbol] = value
            if margin_rate is not None:
                try:
                    rate = float(margin_rate)
                except (TypeError, ValueError):
                    rate = 0.0
                self.margin_rates[symbol] = max(0.0, rate)
            if commission is not None:
                rule = self._normalize_fee(commission)
                if rule is not None:
                    self.fee_rules[symbol] = rule
            if slip_point is not None:
                try:
                    self.slips[symbol] = max(0.0, float(slip_point))
                except (TypeError, ValueError):
                    self.slips[symbol] = 0.0
            if source:
                self.spec_sources[symbol] = str(source)
            self.save()

    def multiplier(self, symbol: str = '') -> float:
        """合约乘数（没登记 → 1，兼容股票 / 老数据 ✓）"""
        symbol = self.resolve(symbol)
        try:
            value = float(self.multipliers.get(str(symbol or ''), 1.0))
        except (TypeError, ValueError):
            value = 1.0
        return value if value > 0 else 1.0

    def margin_rate(self, symbol: str = '') -> Optional[float]:  # noqa: UP045
        """保证金率；``None`` = 该合约走现货（非期货）模式 ✓"""
        text = self.resolve(symbol)
        if text not in self.margin_rates:
            return None
        try:
            return max(0.0, float(self.margin_rates.get(text) or 0.0))
        except (TypeError, ValueError):
            return 0.0

    def slip_of(self, symbol: str = '') -> float:
        symbol = self.resolve(symbol)
        try:
            return max(0.0, float(self.slips.get(str(symbol or ''), 0.0)))
        except (TypeError, ValueError):
            return 0.0

    def prepare_replay(self, initial_cash: float,
                       contracts: Optional[dict] = None) -> None:  # noqa: UP045
        """回放开始 / seek：按 minibt 策略账户重置本地模拟账户 ✓

        * 初始资金 = ``strategy.config.value``（不是 desk 设置）；
        * 清空持仓 / 委托 / 成交 / 曲线；
        * 注册每合约的 ``price_tick / volume_multiple / margin_rate /
          commission / slip_point``；
        * 没有传入的合约继续用 desk 全局手续费。
        """
        try:
            value = float(initial_cash)
        except (TypeError, ValueError):
            value = 0.0
        if value <= 0:
            value = self.initial_cash
        with self._lock:
            old_loading = self._loading
            self._loading = True
            self.initial_cash = value
            self.cash = value
            self.realized = 0.0
            self.commission = 0.0
            self.positions.clear()
            self.orders.clear()
            self.trades.clear()
            self.prices.clear()
            self.equity.clear()
            self.symbol_curve.clear()
            self.symbol_stats.clear()
            self._bar.clear()
            self._hold.clear()
            self._seq = 0
            self.aliases.clear()
            self.multipliers.clear()
            self.decimals.clear()
            self.price_ticks.clear()
            self.margin_rates.clear()
            self.slips.clear()
            self.fee_rules.clear()
            self.spec_sources.clear()
            for symbol, spec in (contracts or {}).items():
                if not isinstance(spec, dict):
                    continue
                self.set_contract(
                    str(symbol),
                    volume_multiple=spec.get('volume_multiple'),
                    price_tick=spec.get('price_tick'),
                    margin_rate=spec.get('margin_rate'),
                    commission=spec.get('commission'),
                    slip_point=spec.get('slip_point'),
                    source=str(spec.get('source') or 'minibt'),
                    # ★ `DCE.l2609`（DataFrame / 策略下单用的真实合约）也要
                    #   落到同一个账户名上 ✓
                    alias=spec.get('minibt_symbol'))
            self._mark_equity()
            self._loading = old_loading
        self.save()

    # ------------------------------------------------------------ 价格
    def set_price(self, symbol: str, price: float,
                  decimals: Optional[int] = None, bar: Any = None) -> None:  # noqa: UP045
        """更新现价（``bar`` = 当前这根 K 线；和开仓那根相同 → 不覆盖 ✓）"""
        try:
            value = float(price)
        except (TypeError, ValueError):
            return
        if value <= 0:
            return
        symbol = self.resolve(str(symbol))
        with self._lock:
            if decimals is not None:
                self.decimals[symbol] = int(decimals)
            if bar is not None:
                self._bar[symbol] = bar
                # ★ 刚开仓那根：现价保持 = 开仓价（浮盈 0 ✓）
                if self._hold.get(symbol, object()) == bar:
                    return
            self.prices[symbol] = value
            self._fill_pending(symbol, value)
            self._mark_equity()

    def _fill_pending(self, symbol: str, price: float) -> None:
        """价格到价 → 把该合约的挂单成交（能成交多少算多少 ✓）"""
        for item in list(self.orders):
            if item.get('symbol') != symbol:
                continue
            if str(item.get('status')) != '未成交':
                continue
            limit = float(item.get('price') or 0.0)
            side = item.get('side')
            if side == 'buy' and price > limit + 1e-9:
                continue
            if side == 'sell' and price < limit - 1e-9:
                continue
            left = float(item.get('left') or item.get('qty') or 0.0)
            if left <= 0:
                item['status'] = '已撤'
                continue
            # 按挂单价成交（限价单的成交价不会更差 ✓）
            result = self.order(symbol, str(side), left, limit,
                                bool(item.get('close')), touch_price=False)
            if not result.get('ok'):
                item['status'] = '已撤'
                continue
            filled = float((result.get('order') or {}).get('qty') or 0.0)
            left -= filled
            item['left'] = max(0.0, left)
            if left <= 1e-9:
                item['status'] = '全部成交'
                item['filled_at'] = time.strftime('%H:%M:%S')

    def pending_orders(self, symbol: str = '') -> list[dict]:
        """未成交委托（挂单线用：`[{id, symbol, price, side, qty}]` ✓）"""
        symbol = self.resolve(symbol) if symbol else ''
        with self._lock:
            out = []
            for item in self.orders:
                if str(item.get('status')) != '未成交':
                    continue
                if symbol and item.get('symbol') != symbol:
                    continue
                qty = float(item.get('left') or item.get('qty') or 0.0)
                if qty <= 0:
                    continue
                out.append({
                    'id': str(item.get('id') or ''),
                    'symbol': item.get('symbol'),
                    'price': float(item.get('price') or 0.0),
                    'side': '买' if item.get('side') == 'buy' else '卖',
                    'offset': '平' if item.get('close') else '开',
                    'qty': qty,
                    'status': '挂单',
                })
            return out

    def cancel_pending(self, symbol: str = '') -> int:
        """撤掉挂单（`全撤` / 换合约时用 ✓）"""
        symbol = self.resolve(symbol) if symbol else ''
        with self._lock:
            count = 0
            for item in self.orders:
                if str(item.get('status')) != '未成交':
                    continue
                if symbol and item.get('symbol') != symbol:
                    continue
                item['status'] = '已撤'
                count += 1
            self.save()
            return count

    def _price(self, symbol: str) -> float:
        return float(self.prices.get(self.resolve(symbol)) or 0.0)

    def _digits(self, symbol: str) -> int:
        return int(self.decimals.get(self.resolve(symbol), 2))

    # ------------------------------------------------------------ 下单
    def order(self, symbol: str, side: str, qty: float, price: float,
              close: bool = False, touch_price: bool = True,
              force: bool = False, auto: bool = False) -> dict:
        """下单（限价单：价格暂不可成交 → **先挂单**，到价才成交 ✓）

        ``touch_price=False``：挂单成交时用（成交价是限价，不该改动现价 ✓）
        ``auto=True``：策略自动成交（按 minibt `slip_point` 加滑点 ✓）
        """
        symbol = str(symbol or '')
        side = str(side or '').lower()
        # ★ 先把各种写法归一到账户里的合约名（`DCE.l2609` → `l2609_60`）✓
        symbol = self.resolve(symbol)
        try:
            qty = abs(float(qty))
        except (TypeError, ValueError):
            qty = 0.0
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = 0.0
        # ★ 价格留空（交易面板「对手价」/ 回放中价格框是空的）→ 用**现价**
        #   以前 0 直接判「下单参数不合法」，指标 / K 线回放时完全没法下单 ✗
        #   （用户 2026-11-21 实测）
        if price <= 0:
            price = self._price(symbol)
        if not symbol or qty <= 0 or price <= 0 or side not in ('buy', 'sell'):
            return {'ok': False, 'error': '下单参数不合法（价格 / 手数 / 方向）'}
        # ★ 策略自动成交：和 minibt Broker._handle_slip_point 一致
        if auto:
            slip = self.slip_of(symbol)
            if slip > 0:
                price = price + slip if side == 'buy' else price - slip
        book = self.positions.setdefault(
            symbol, {'long': 0.0, 'short': 0.0, 'avg_long': 0.0,
                     'avg_short': 0.0})
        realized = 0.0
        multiple = self.multiplier(symbol)
        futures = self.margin_rate(symbol) is not None
        offset = '平仓' if close else '开仓'
        with self._lock:
            # ★ 限价单：买价低于现价 / 卖价高于现价 → **先挂单**（不成交 ✓）
            #   等 `set_price` 到价再真正成交（挂单线就靠这个 ✓）
            last = self._price(symbol)
            marketable = bool(force) or (last <= 0
                                         or (side == 'buy' and price >= last)
                                         or (side == 'sell' and price <= last))
            if not marketable:
                self._seq += 1
                order = {'id': self._seq, 'ts': time.strftime('%H:%M:%S'),
                         'symbol': symbol, 'side': side, 'offset': offset,
                         'qty': qty, 'price': price, 'status': '未成交',
                         'left': qty, 'fee': 0.0, 'close': bool(close)}
                self.orders.append(order)
                self.orders = self.orders[-200:]
                self.save()
                return {'ok': True, 'order': order, 'pending': True,
                        'realized': 0.0, 'fee': 0.0}
            if close:
                if side == 'sell' and book['long'] > 0:
                    done = min(qty, book['long'])
                    realized = (price - book['avg_long']) * done * multiple
                    book['long'] -= done
                    if not futures:
                        self.cash += price * done * multiple
                    qty = done
                elif side == 'buy' and book['short'] > 0:
                    done = min(qty, book['short'])
                    realized = (book['avg_short'] - price) * done * multiple
                    book['short'] -= done
                    if not futures:
                        self.cash -= price * done * multiple
                    qty = done
                else:
                    return {'ok': False,
                            'error': '没有可平的持仓' if close else '参数不合法'}
                # 期货：开仓没付名义本金，平仓只结算盈亏 ✓
                if futures:
                    self.cash += realized
                self.realized += realized
            elif side == 'buy':
                total = book['long'] + qty
                book['avg_long'] = (
                    (book['avg_long'] * book['long'] + price * qty) / total
                    if total else 0.0)
                book['long'] = total
                if not futures:
                    self.cash -= price * qty * multiple
            else:
                total = book['short'] + qty
                book['avg_short'] = (
                    (book['avg_short'] * book['short'] + price * qty) / total
                    if total else 0.0)
                book['short'] = total
                if not futures:
                    self.cash += price * qty * multiple
            if book['long'] <= 1e-9:
                book['long'] = 0.0
                book['avg_long'] = 0.0
            if book['short'] <= 1e-9:
                book['short'] = 0.0
                book['avg_short'] = 0.0
            self._seq += 1
            stamp = time.strftime('%H:%M:%S')
            fee = self.fee_of(qty, price, symbol)
            self.commission += fee
            self.cash -= fee
            order = {'id': self._seq, 'ts': stamp, 'symbol': symbol,
                     'side': side, 'offset': offset, 'qty': qty,
                     'price': price, 'status': '全部成交', 'fee': fee}
            self.orders.append(order)
            self.trades.append({**order, 'realized': realized})
            self.orders = self.orders[-200:]
            self.trades = self.trades[-200:]
            # ★ 现价 = 开仓价（同一根 K 线内不再被回放价覆盖 ✓）
            if touch_price:
                self.prices[symbol] = price
                self._hold[symbol] = self._bar.get(symbol, object())
            self._book_stats(symbol, realized, fee, qty, price, close, stamp)
            self._mark_equity()
            self.save()
        return {'ok': True, 'order': order, 'realized': realized,
                'fee': fee}

    # ------------------------------------------------------------ 曲线 / 统计
    def _mark_equity(self) -> None:
        """记一个权益点（时间变了才记，最多 `MAX_CURVE_POINTS` 点 ✓）"""
        try:
            value = self._equity_value()
        except Exception:                                        # noqa: BLE001
            return
        stamp = time.strftime('%H:%M:%S')
        # ★ 同一个"秒"内只保留**最新值**（覆盖，不追加）：回放里一秒内
        #   会连续成交很多笔 → 以前每秒塞几十个点 → 权益曲线锯齿 ✗
        if self.equity and self.equity[-1][0] == stamp:
            self.equity[-1][1] = round(value, 2)
            return
        self.equity.append([stamp, round(value, 2)])
        if len(self.equity) > MAX_CURVE_POINTS:
            del self.equity[:len(self.equity) - MAX_CURVE_POINTS]

    def _account_values(self) -> dict:
        """账户口径（和 minibt `BtAccount` 尽量一致 ✓）

        * 期货合约（登记了 `margin_rate`）：
          `cash = 初始资金 + 已实现盈亏 - 手续费`，
          `权益 = cash + 浮动盈亏`，`可用 = cash - 占用保证金`；
        * 股票 / 无保证金规格：保持原来的现货模型。
        """
        futures_pnl = 0.0
        spot_value = 0.0
        float_pnl = 0.0
        margin = 0.0
        for code, book in self.positions.items():
            long_qty = float(book.get('long') or 0.0)
            short_qty = float(book.get('short') or 0.0)
            if long_qty <= 0 and short_qty <= 0:
                continue
            price = self._price(code) or float(
                book.get('avg_long') or book.get('avg_short') or 0.0)
            multiple = self.multiplier(code)
            pnl = ((price - float(book.get('avg_long') or 0.0)) * long_qty
                   + (float(book.get('avg_short') or 0.0) - price)
                   * short_qty) * multiple
            float_pnl += pnl
            rate = self.margin_rate(code)
            if rate is None:
                spot_value += (long_qty - short_qty) * price * multiple
            else:
                futures_pnl += pnl
                margin += (long_qty + short_qty) * price * multiple * rate
        equity = self.cash + spot_value + futures_pnl
        return {
            'cash': self.cash,
            'float_pnl': float_pnl,
            'equity': equity,
            'margin': margin,
            'available': self.cash - margin,
            'risk_ratio': (margin / equity) if equity > 0 else 0.0,
            'spot_value': spot_value,
        }

    def _equity_value(self) -> float:
        return float(self._account_values()['equity'])

    def _book_stats(self, symbol: str, realized: float, fee: float,
                    qty: float, price: float, close: bool,
                    stamp: str) -> None:
        stat = self.symbol_stats.setdefault(
            symbol, {'symbol': symbol, 'trades': 0, 'closes': 0, 'wins': 0,
                     'losses': 0, 'realized': 0.0, 'commission': 0.0,
                     'volume': 0.0, 'turnover': 0.0})
        stat['trades'] += 1
        stat['volume'] += abs(qty)
        stat['turnover'] += (abs(qty) * abs(price)
                             * self.multiplier(symbol))
        stat['commission'] += fee
        if close:
            stat['closes'] += 1
            stat['realized'] += realized
            net_value = realized - fee
            if net_value > 0:
                stat['wins'] += 1
            elif net_value < 0:
                stat['losses'] += 1
            curve = self.symbol_curve.setdefault(symbol, [])
            curve.append([stamp, round(stat['realized'], 2)])
            if len(curve) > MAX_CURVE_POINTS:
                del curve[:len(curve) - MAX_CURVE_POINTS]

    def analysis(self) -> dict:
        """设置页「模拟账户」：权益曲线 / 各品种累计盈亏 / 统计表 ✓"""
        with self._lock:
            if not self.equity:
                self._mark_equity()
            equity = [list(item) for item in self.equity]
            palette = ['#2962ff', '#f23645', '#089981', '#ff9800',
                       '#9c27b0', '#00bcd4', '#e91e63', '#7c4dff',
                       '#8d6e63', '#607d8b']
            series: list[dict] = []
            for index, (symbol, curve) in enumerate(self.symbol_curve.items()):
                if not curve:
                    continue
                series.append({'name': symbol,
                               'color': palette[index % len(palette)],
                               'points': [list(item) for item in curve]})
            rows: list[list] = []
            for symbol, stat in sorted(
                    self.symbol_stats.items(),
                    key=lambda item: -float(item[1].get('realized') or 0.0)):
                closes = int(stat.get('closes') or 0)
                wins = int(stat.get('wins') or 0)
                rate = f'{(wins / closes * 100):.1f}%' if closes else '--'
                rows.append([
                    symbol, f"{int(stat.get('trades') or 0)}",
                    f"{closes}", rate,
                    f"{float(stat.get('realized') or 0.0):,.2f}",
                    f"{float(stat.get('commission') or 0.0):,.2f}",
                    # ⚠ 这里的格式串以前写成 `: , .2f`（逗号/点号两边带空格）
                    #   → `ValueError: Invalid format specifier`，只要有一个
                    #   **平过仓**的合约，本地账户「分析」页就直接报错 ✗
                    f"{float(stat.get('realized') or 0.0)
                       - float(stat.get('commission') or 0.0):,.2f}",
                ])
            summary = {
                'initial_cash': self.initial_cash,
                'balance': round(self._equity_value(), 2),
                'realized': round(self.realized, 2),
                'commission': round(self.commission, 2),
                # ⚠ 不能用 len(self.trades)：明细列表只保留最近 200 条，
                #   成交次数会永远停在 200（用户实测 ✗）。
                #   完整累计在 symbol_stats['trades']（reset 时一起清零）✓
                'trades': sum(int(item.get('trades') or 0)
                              for item in self.symbol_stats.values()),
                'closes': sum(int(item.get('closes') or 0)
                              for item in self.symbol_stats.values()),
                'wins': sum(int(item.get('wins') or 0)
                            for item in self.symbol_stats.values()),
            }
            return {
                'type': 'sim_analysis',
                'kind': 'local',
                'settings': self.settings(),
                'summary': summary,
                'equity': equity,
                'series': series,
                'table': {
                    'columns': ['品种', '交易次数', '平仓次数', '胜率',
                                '平仓盈亏', '手续费', '净盈亏'],
                    'rows': rows,
                },
            }

    def close_all(self) -> list:
        """市价平掉**全部**持仓（本地图表「交易账户 → 全」/ 右键「全」✓）

        ★ 用 `close_positions()`：`force=True` → 立即按现价成交，
          以前价格不够"够得着"就变成挂着不成交 ✗
        """
        return self.close_positions()

    def close_positions(self, symbols=None, prices=None) -> list:
        """按**当前收盘价**平掉指定合约（退出回放 / 关闭 desk ✓）

        * `symbols` 为空 → 平掉账户里**所有**有持仓的合约；
        * `prices` = 前端回放进度带上来的「当前那根 K 线的收盘价」；
          没给 → 用账户现价；再没有 → 用持仓成本价（绝不用 0 ✗）；
        * `force=True`：这是「退出前平仓」，**必须立即成交**，不能变成挂单 ✓
        """
        def _num(value) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        wanted = {self.resolve(str(name)): _num((prices or {}).get(str(name)))
                  for name in (symbols or []) if str(name or '')}
        with self._lock:
            books = dict(self.positions)
        done: list[str] = []
        for name, book in books.items():
            long_qty = _num(book.get('long'))
            short_qty = _num(book.get('short'))
            if long_qty <= 0 and short_qty <= 0:
                continue
            if wanted and name not in wanted:
                continue
            price = wanted.get(name, 0.0) or self._price(name)
            if price <= 0:
                price = _num(book.get('avg_long')) or _num(book.get('avg_short'))
            if price <= 0:
                continue
            if long_qty > 0:
                self.order(name, 'sell', long_qty, price, True, force=True)
            if short_qty > 0:
                self.order(name, 'buy', short_qty, price, True, force=True)
            done.append(name)
        if done:
            self.save()
        return done

    def reverse_all(self) -> None:
        """反手：平掉现有仓位，再按同手数反向开仓 ✓"""
        with self._lock:
            books = list(self.positions.items())
        for symbol, book in books:
            price = self._price(symbol) or float(
                book.get('avg_long') or book.get('avg_short') or 0.0)
            long_qty = float(book.get('long') or 0.0)
            short_qty = float(book.get('short') or 0.0)
            # ★ 市价 + `force=True`：平要**立即成交**，反手也要立即建仓 ✓
            if long_qty > 0:
                self.order(symbol, 'sell', long_qty, price, True, force=True)
                self.order(symbol, 'sell', long_qty, price, False, force=True)
            if short_qty > 0:
                self.order(symbol, 'buy', short_qty, price, True, force=True)
                self.order(symbol, 'buy', short_qty, price, False, force=True)

    def close_side(self, symbol: str, side: str = '', volume: float = 0,
                   price: float = 0) -> list:
        """平掉某合约的**多 / 空**（可按手数）—— 持仓右键「平」✓

        `side`：`'多'` / `'空'`（空 = 多空都平）；`volume`：0 = 全部；
        `price`：0 = 用现价（市价单 ✓）
        """
        name = self.resolve(symbol)
        book = self.book(name) or {}
        long_qty = float(book.get('long') or 0.0)
        short_qty = float(book.get('short') or 0.0)
        want = str(side or '')
        lots = max(0.0, float(volume or 0.0))
        market = float(price or 0.0) or self._price(name)
        done: list = []
        if long_qty > 0 and want in ('', '多', 'long', '买'):
            qty = min(lots, long_qty) if lots > 0 else long_qty
            if qty > 0 and market > 0:
                self.order(name, 'sell', qty, market, True, force=True)
                done.append(('多', qty, market))
        if short_qty > 0 and want in ('', '空', 'short', '卖'):
            qty = min(lots, short_qty) if lots > 0 else short_qty
            if qty > 0 and market > 0:
                self.order(name, 'buy', qty, market, True, force=True)
                done.append(('空', qty, market))
        return done

    def reset(self) -> None:
        with self._lock:
            self.cash = self.initial_cash
            self.realized = 0.0
            self.commission = 0.0
            self.positions.clear()
            self.orders.clear()
            self.trades.clear()
            self.prices.clear()
            self.equity.clear()
            self.symbol_curve.clear()
            self.symbol_stats.clear()
            self._hold.clear()
            self._mark_equity()
            self.save()

    # ------------------------------------------------------------ 快照
    def _money(self, value: float) -> str:
        return f'{float(value):,.2f}'

    def _fmt_price(self, symbol: str, value: float) -> str:
        digits = self._digits(symbol)
        return f'{float(value):,.{digits}f}'

    def payload(self, symbol: str = '') -> dict:
        """`AccountDock` 直接能吃的账户补丁 ✓"""
        with self._lock:
            last = self._price(symbol) if symbol else 0.0
            float_profit = 0.0
            market_value = 0.0
            position_rows: list[list] = []
            for code, book in self.positions.items():
                long_qty = float(book.get('long') or 0.0)
                short_qty = float(book.get('short') or 0.0)
                multiple = self.multiplier(code)
                price = self._price(code) or float(book.get('avg_long') or
                                                   book.get('avg_short') or 0.0)
                market_value += (long_qty * price -
                                 short_qty * price) * multiple
                if long_qty > 0:
                    pnl = (price - float(book.get('avg_long') or 0.0)) \
                        * long_qty * multiple
                    float_profit += pnl
                    position_rows.append([
                        code, '多', f'{long_qty:g}',
                        self._fmt_price(code, book.get('avg_long') or 0.0),
                        self._fmt_price(code, price), self._money(pnl)])
                if short_qty > 0:
                    pnl = (float(book.get('avg_short') or 0.0) - price) \
                        * short_qty * multiple
                    float_profit += pnl
                    position_rows.append([
                        code, '空', f'{short_qty:g}',
                        self._fmt_price(code, book.get('avg_short') or 0.0),
                        self._fmt_price(code, price), self._money(pnl)])
            # （以前这里还有一行 `balance = self.cash + market_value` ——
            #   算了但**从没用过**：下面 `values['balance']` 取的是
            #   `account['equity']`（期货按保证金口径 `cash + 浮动盈亏`）。
            #   留着反而误导人以为账户权益是 `现金 + 名义市值` ✗ 已删除）
            account = self._account_values()
            # ★ 右键菜单（平 / 反手 / 全平 · 撤单）需要**原始字段**：
            #   以前只给 `rows`（预格式化字符串）→ 前端拿到空 symbol / 0 手 ✗
            raw_positions: list[dict] = []
            for code, book in self.positions.items():
                long_qty = float(book.get('long') or 0.0)
                short_qty = float(book.get('short') or 0.0)
                price = self._price(code) or float(
                    book.get('avg_long') or book.get('avg_short') or 0.0)
                multiple = self.multiplier(code)
                if long_qty > 0:
                    raw_positions.append({
                        'symbol': code, 'side': '多', 'volume': long_qty,
                        'avg': float(book.get('avg_long') or 0.0),
                        'price': price,
                        'profit': (price - float(book.get('avg_long') or 0.0))
                        * long_qty * multiple,
                    })
                if short_qty > 0:
                    raw_positions.append({
                        'symbol': code, 'side': '空', 'volume': short_qty,
                        'avg': float(book.get('avg_short') or 0.0),
                        'price': price,
                        'profit': (float(book.get('avg_short') or 0.0) - price)
                        * short_qty * multiple,
                    })
            raw_orders = [
                {'symbol': item['symbol'], 'side': item['side'],
                 'offset': item['offset'], 'volume': item['qty'],
                 'left': item['qty'] if item['status'] == '未成交' else 0,
                 'price': item['price'], 'status': item['status'],
                 'alive': item['status'] == '未成交',
                 'order_id': str(item.get('id') or '')}
                for item in self.orders[-100:]
            ]
            rows_orders = [
                [item['ts'], item['symbol'],
                 '买' if item['side'] == 'buy' else '卖', item['offset'],
                 f"{item['qty']:g}", self._fmt_price(item['symbol'],
                                                     item['price']),
                 item['status']]
                for item in self.orders[-100:]
            ]
            rows_trades = [
                [item['ts'], item['symbol'],
                 '买' if item['side'] == 'buy' else '卖', item['offset'],
                 f"{item['qty']:g}", self._fmt_price(item['symbol'],
                                                     item['price']),
                 self._money(item.get('realized') or 0.0)]
                for item in self.trades[-100:]
            ]
            return {
                'type': 'local_account',
                'kind': 'local',
                'index': 0,
                # ★ 这一份账户数据是**哪个合约的价格上下文**（前端交易面板
                #   据此决定要不要把「价格框」跟到这个合约 ✓）
                'symbol': str(symbol or ''),
                'labels': ['本地模拟账户'],
                'fields': [
                    {'key': 'initial_cash', 'title': '静态权益'},
                    {'key': 'balance', 'title': '账户权益'},
                    {'key': 'float_profit', 'title': '持仓盈亏'},
                    {'key': 'realized_pnl', 'title': '平仓盈亏'},
                    {'key': 'commission', 'title': '手续费'},
                    {'key': 'margin', 'title': '占用保证金'},
                    {'key': 'risk_ratio', 'title': '资金使用率',
                     'percent': True},
                    {'key': 'available', 'title': '可用资金'},
                    {'key': 'position_count', 'title': '持仓数'},
                    {'key': 'trade_count', 'title': '成交数'},
                ],
                'values': {
                    'initial_cash': self.initial_cash,
                    'balance': account['equity'],
                    'float_profit': account['float_pnl'],
                    'realized_pnl': self.realized,
                    'commission': self.commission,
                    'available': account['available'],
                    'margin': account['margin'],
                    'risk_ratio': account['risk_ratio'],
                    'market_value': market_value,
                    'position_count': sum(
                        1 for book in self.positions.values()
                        if (book.get('long') or 0) > 0
                        or (book.get('short') or 0) > 0),
                    'trade_count': sum(
                        int(item.get('trades') or 0)
                        for item in self.symbol_stats.values())
                    or len(self.trades),
                },
                'tables': {
                    'positions': {
                        'columns': ['代码', '方向', '手数', '均价', '现价',
                                    '浮盈'],
                        'rows': position_rows,
                        'raw': raw_positions,
                    },
                    'orders': {
                        'columns': ['时间', '代码', '买卖', '开平', '手数',
                                    '价格', '状态'],
                        'rows': rows_orders,
                        'raw': raw_orders,
                    },
                    'trades': {
                        'columns': ['时间', '代码', '买卖', '开平', '手数',
                                    '价格', '已实现盈亏'],
                        'rows': rows_trades,
                    },
                    'unfilled': {'columns': [], 'rows': []},
                },
                'last_price': last,
            }
