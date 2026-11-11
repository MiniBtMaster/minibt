"""合约清单的本地缓存（sqlite）。

为什么需要：期货 `query_quotes` 要**逐个交易所**拉，A 股 `get_stock_basicinfo`
也要联网，首屏等 2~5 秒很烦。这里按 ``(品种, 交易所)`` 存一份，默认**当天有效**
（跨日自动刷新，和 miniqt 的 `contracts_refreshed_on` 一个思路 ✓）。

    >>> from minibt.desk.symbol_cache import SymbolCache
    >>> cache = SymbolCache()
    >>> cache.get('FUT:SHFE')            # None = 没有 / 过期
    >>> cache.put('FUT:SHFE', rows)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import List, Optional

#: 默认库（和股票模拟盘/期货落盘放同一个目录 ✓）
DEFAULT_DB = os.path.join(os.path.expanduser('~'), '.minibt',
                          'desk_symbols.sqlite3')


class SymbolCache:
    """按 key 缓存合约清单（``[{symbol,name}, …]``）；过期自动忽略 ✓"""

    def __init__(self, path: Optional[str] = None, ttl_hours: float = 24.0):
        self.path = str(path or DEFAULT_DB)
        self.ttl = float(ttl_hours) * 3600.0
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute(
            'CREATE TABLE IF NOT EXISTS symbols('
            ' key TEXT PRIMARY KEY, updated REAL NOT NULL, payload TEXT NOT NULL)')
        self._conn.commit()

    # ------------------------------------------------------------ 读写
    def get(self, key: str) -> Optional[List[dict]]:
        with self._lock:
            row = self._conn.execute(
                'SELECT updated, payload FROM symbols WHERE key=?',
                (str(key),)).fetchone()
        if not row:
            return None
        updated, payload = float(row[0]), row[1]
        if self.ttl and (time.time() - updated) > self.ttl:
            return None
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            return None
        return data if isinstance(data, list) else None

    def get_any(self, key: str) -> Optional[List[dict]]:
        """读缓存，**不管是否过期**（行情源暂时连不上时先显示旧清单 ✓）"""
        with self._lock:
            row = self._conn.execute(
                'SELECT payload FROM symbols WHERE key=?', (str(key),)
            ).fetchone()
        if not row:
            return None
        try:
            data = json.loads(row[0])
        except (TypeError, ValueError):
            return None
        return data if isinstance(data, list) else None

    def age(self, key: str) -> Optional[float]:
        """缓存年龄（秒）；没有 → None ✓"""
        with self._lock:
            row = self._conn.execute(
                'SELECT updated FROM symbols WHERE key=?', (str(key),)
            ).fetchone()
        if not row:
            return None
        try:
            return max(0.0, time.time() - float(row[0]))
        except (TypeError, ValueError):
            return None

    def put(self, key: str, rows: List[dict],
            updated: Optional[float] = None) -> None:
        payload = json.dumps(list(rows or []), ensure_ascii=False,
                             separators=(',', ':'))
        with self._lock:
            stamp = time.time() if updated is None else float(updated)
            self._conn.execute(
                'INSERT OR REPLACE INTO symbols(key, updated, payload)'
                ' VALUES(?,?,?)', (str(key), stamp, payload))
            self._conn.commit()

    def drop(self, key: str) -> None:
        with self._lock:
            self._conn.execute('DELETE FROM symbols WHERE key=?', (str(key),))
            self._conn.commit()

    def clear(self) -> None:
        with self._lock:
            self._conn.execute('DELETE FROM symbols')
            self._conn.commit()

    def keys(self) -> List[str]:
        with self._lock:
            return [str(row[0]) for row in
                    self._conn.execute('SELECT key FROM symbols').fetchall()]

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:                                    # noqa: BLE001
                pass
