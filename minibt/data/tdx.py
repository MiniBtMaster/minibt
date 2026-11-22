"""**通达信（TDX）本地 K 线**读取：`.day` / `.lc5`（`.lc1`）✓

不引入 `mootdx` 依赖（用户 2026-11-22 明确要求自己移植）：两种文件都是
**32 字节定长记录**，直接 `struct` 解析即可。

| 文件 | 目录（相对通达信安装根） | 每条记录 |
|---|---|---|
| `.day` 日线 | `vipdoc/<market>/lday/*.day` | `int32 date(YYYYMMDD), int32 o/h/l/c(×100), float32 amount, int32 volume, int32 _` |
| `.lc5` 5 分钟 | `vipdoc/<market>/fzline/*.lc5` | `uint16 date, uint16 minute, float32 o/h/l/c/amount, uint32 volume, uint32 _` |
| `.lc1` 1 分钟 | `vipdoc/<market>/min/*.lc1` | 同 `.lc5` |

* `date` 编码：`(年-2004) * 2048 + 月 * 100 + 日`
* `minute` 编码：`小时 * 60 + 分钟`
* 价格：日线是 **整数 ×100**，分钟线是 **float**（不再除 100）
* `market`：`sh` 上交所 / `sz` 深交所 / `bj` 北交所 / `ds` 期货等

对外接口（其余模块只用这几个）：

* :func:`read_tdx` —— 任意 `.day/.lc5/.lc1` → DataFrame（minibt K 线列）
* :func:`is_tdx_file` / :func:`tdx_id` / :func:`split_tdx_id`
* :func:`scan_root` —— 递归扫一个通达信根目录（只列文件名，**不读内容** ✓）
* :func:`resolve` —— 根目录 + 代码 + 周期 → 文件路径
* :func:`load` —— 根目录 + 代码 + 周期 → DataFrame（带 symbol/duration 列）
"""
from __future__ import annotations

import os
import struct
from typing import Iterable, Optional

import numpy as np
import pandas as pd

__all__ = ['read_tdx', 'is_tdx_file', 'tdx_id', 'split_tdx_id', 'scan_root',
           'resolve', 'load', 'PERIODS', 'MARKETS', 'TDX_SUFFIXES']

#: 后缀 → (周期秒, 目录名)
PERIODS = {'.day': (86400, 'lday'), '.lc5': (300, 'fzline'),
           '.lc1': (60, 'min')}

#: 目录/文件前缀 → 市场名
MARKETS = {'sh': 'SH', 'sz': 'SZ', 'bj': 'BJ', 'ds': 'DS'}

TDX_SUFFIXES = tuple(PERIODS)

#: 预扫目录名（`vipdoc/<market>/<dir>`）
SCAN_DIRS = ('lday', 'fzline', 'min')

RECORD = 32

_DAY = struct.Struct('<iiiiifii')
_MIN = struct.Struct('<HHfffffII')


def is_tdx_file(path: str) -> bool:
    """是不是通达信 K 线文件（`.day` / `.lc5` / `.lc1`）✓"""
    return os.path.splitext(str(path or ''))[1].lower() in PERIODS


def _decode_day(stamp: int) -> pd.Timestamp:
    text = f'{int(stamp):08d}'
    return pd.Timestamp(f'{text[:4]}-{text[4:6]}-{text[6:8]}')


def _decode_min(stamp: int, minute: int) -> pd.Timestamp:
    year = 2004 + (int(stamp) >> 11)
    month = (int(stamp) % 2048) // 100
    day = (int(stamp) % 2048) % 100
    hour = int(minute) // 60
    mins = int(minute) % 60
    return pd.Timestamp(f'{year:04d}-{month:02d}-{day:02d} '
                        f'{hour:02d}:{mins:02d}:00')


def read_tdx(path: str) -> pd.DataFrame:
    """读通达信 `.day` / `.lc5` / `.lc1` → minibt K 线 DataFrame ✓

    列：``datetime / open / high / low / close / volume / amount``
    （`amount` = 成交额，日线是元、分钟线是原始 float）

    >>> read_tdx(r'E:/new_tdx/vipdoc/sh/lday/sh600000.day').tail()
    >>> read_tdx(r'E:/new_tdx/vipdoc/sh/fzline/sh600000.lc5').tail()
    """
    suffix = os.path.splitext(str(path))[1].lower()
    if suffix not in PERIODS:
        raise ValueError(f'不是通达信 K 线文件（需要 .day / .lc5 / .lc1）：{path}')
    if not os.path.exists(path):
        raise FileNotFoundError(f'通达信文件不存在：{path}')
    blob = np.fromfile(path, dtype=np.uint8)
    count = int(blob.size // RECORD)
    if count <= 0:
        return pd.DataFrame(columns=['datetime', 'open', 'high', 'low',
                                     'close', 'volume', 'amount'])
    records = blob[: count * RECORD].tobytes()

    if suffix == '.day':
        rows = list(_DAY.iter_unpack(records))
        stamps = [_decode_day(row[0]) for row in rows]
        prices = np.array([[row[1], row[2], row[3], row[4]] for row in rows],
                          dtype=np.float64) / 100.0
        amount = np.array([row[5] for row in rows], dtype=np.float64)
        volume = np.array([row[6] for row in rows], dtype=np.float64)
    else:
        rows = list(_MIN.iter_unpack(records))
        stamps = [_decode_min(row[0], row[1]) for row in rows]
        prices = np.array([[row[2], row[3], row[4], row[5]] for row in rows],
                          dtype=np.float64)
        amount = np.array([row[6] for row in rows], dtype=np.float64)
        volume = np.array([row[7] for row in rows], dtype=np.float64)

    frame = pd.DataFrame({
        'datetime': pd.DatetimeIndex(stamps),
        'open': prices[:, 0], 'high': prices[:, 1],
        'low': prices[:, 2], 'close': prices[:, 3],
        'volume': volume, 'amount': amount,
    })
    return frame.loc[frame['datetime'].notna()].reset_index(drop=True)


def tdx_id(market: str, code: str, suffix: str) -> str:
    """文件名 → **稳定 id**（desk 选中 / 缓存用）✓

    >>> tdx_id('sh', '600000', '.day')   # 'tdx:sh600000@day'
    """
    period = suffix.lstrip('.').lower()
    return f'tdx:{market.lower()}{code}@{period}'


def split_tdx_id(name: str) -> Optional[tuple[str, str, str]]:
    """`tdx:sh600000@day` → `('sh', '600000', '.day')`；不合法返回 None ✓"""
    text = str(name or '').strip()
    if not text.lower().startswith('tdx:') or '@' not in text:
        return None
    body, _, period = text[4:].partition('@')
    if not body or not period:
        return None
    market, code = body[:2], body[2:]
    if market.lower() not in MARKETS or not code:
        return None
    suffix = f'.{period.lower()}'
    if suffix not in PERIODS:
        return None
    return market.lower(), code, suffix


def scan_root(root: str) -> dict[str, list[dict]]:
    """扫一个通达信根目录 → `{周期后缀: [ {id, market, code, path, rows} ]}` ✓

    * 只列**文件名**（不读内容，几千个也很快）；
    * 支持传**安装根**（含 `vipdoc/`）或**直接传 `vipdoc/`**；
    * 没找到 `vipdoc` 时退回"把传入目录当作数据目录"（含 `*.day` / `*.lc5`）。
    """
    base = os.path.abspath(os.path.expanduser(str(root or '').strip()))
    if not base or not os.path.isdir(base):
        return {}
    vipdoc = os.path.join(base, 'vipdoc')
    scan_base = vipdoc if os.path.isdir(vipdoc) else base
    found: dict[str, list[dict]] = {suffix: [] for suffix in PERIODS}

    def _add(path: str, suffix: str) -> None:
        name = os.path.splitext(os.path.basename(path))[0].lower()
        market, code = name[:2], name[2:]
        if market not in MARKETS or not code:
            return
        found[suffix].append({
            'id': tdx_id(market, code, suffix),
            'market': market.upper(),
            'code': code,
            'path': path,
        })

    # ① 标准结构：vipdoc/<market>/<lday|fzline|min>/*.ext
    for market in MARKETS:
        for sub in SCAN_DIRS:
            folder = os.path.join(scan_base, market, sub)
            if not os.path.isdir(folder):
                continue
            for entry in os.scandir(folder):
                suffix = os.path.splitext(entry.name)[1].lower()
                if suffix in PERIODS and entry.is_file():
                    _add(entry.path, suffix)
    # ② 兜底：传入的目录里直接躺着一堆 .day（用户手动挑的 lday 文件夹）
    if not any(found.values()):
        for entry in os.scandir(scan_base):
            suffix = os.path.splitext(entry.name)[1].lower()
            if suffix in PERIODS and entry.is_file():
                _add(entry.path, suffix)
    for suffix in found:
        found[suffix].sort(key=lambda item: (item['market'], item['code']))
    return {suffix: items for suffix, items in found.items() if items}


def resolve(root: str, code: str, period: str | int = 'day') -> Optional[str]:
    """根目录 + 代码 + 周期 → 文件路径（找不到返回 None ✓）

    ``period`` 支持 ``'day'`` / ``'5m'`` / ``'1m'`` / ``'.day'`` / ``300`` …
    """
    suffix = _suffix_of(period)
    if not suffix:
        return None
    table = scan_root(root)
    items = table.get(suffix) or []
    wanted = str(code or '').strip().lower()
    for item in items:
        if item['code'].lower() == wanted or item['id'].lower() == wanted:
            return item['path']
        if item['id'].lower().endswith(wanted):
            return item['path']
    return None


def load(root: str, code: str, period: str | int = 'day') -> pd.DataFrame:
    """根目录 + 代码 + 周期 → DataFrame（带 `symbol` / `duration` 列 ✓）"""
    path = resolve(root, code, period)
    if not path:
        raise FileNotFoundError(
            f'通达信里找不到 {code}（周期 {period}）：root={root}')
    return load_path(path)


def load_path(path: str) -> pd.DataFrame:
    """读文件 + 补 `symbol` / `duration` / `price_tick` / `volume_multiple` ✓"""
    frame = read_tdx(path)
    suffix = os.path.splitext(path)[1].lower()
    duration = PERIODS[suffix][0]
    name = os.path.splitext(os.path.basename(path))[0].lower()
    market, code = name[:2], name[2:]
    frame['symbol'] = f'{MARKETS.get(market, market.upper())}.{code}'
    frame['duration'] = duration
    frame['price_tick'] = 0.01
    frame['volume_multiple'] = 1.0
    return frame


def _suffix_of(period: str | int) -> Optional[str]:
    """周期写法 → 后缀（`'day'` / `'5m'` / 300 / `.lc5` …）✓"""
    text = str(period or '').strip().lower()
    if text in PERIODS:
        return text
    if not text.startswith('.'):
        text = f'.{text}'
    if text in PERIODS:
        return text
    alias = {'d': '.day', 'day': '.day', '1d': '.day', 'daily': '.day',
             '5m': '.lc5', 'm5': '.lc5', '5min': '.lc5', '300': '.lc5',
             '1m': '.lc1', 'm1': '.lc1', '1min': '.lc1', '60': '.lc1'}
    return alias.get(str(period).strip().lower())


def roots_from(paths: Iterable[str]) -> list[str]:
    """候选目录里挑出**通达信根**（含 `vipdoc/` 或直接有 `.day`）✓"""
    out: list[str] = []
    for path in paths:
        folder = os.path.abspath(os.path.expanduser(str(path or '').strip()))
        if not folder or not os.path.isdir(folder) or folder in out:
            continue
        if os.path.isdir(os.path.join(folder, 'vipdoc')):
            out.append(folder)
            continue
        # 用户直接选了 `.../vipdoc` 或 `.../vipdoc/sh/lday`
        parent = folder
        for _ in range(3):
            if os.path.basename(parent).lower() == 'vipdoc' or \
                    os.path.isdir(os.path.join(parent, 'vipdoc')):
                if parent not in out:
                    out.append(parent if os.path.basename(parent).lower()
                               == 'vipdoc' else os.path.dirname(parent))
                break
            try:
                next_entry = next(
                    (item for item in os.scandir(folder)
                     if item.is_file() and os.path.splitext(item.name)[1]
                     .lower() in PERIODS), None)
            except OSError:
                next_entry = None
            if next_entry is not None:
                out.append(folder)          # 直接是"一堆 .day 的目录"
                break
            parent = os.path.dirname(parent)
            if parent == folder:
                break
    return out
