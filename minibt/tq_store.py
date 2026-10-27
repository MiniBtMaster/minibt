"""期货（天勤）账户**本地持久化**：权益曲线 + 成交记录（sqlite）。

和 ``minibt.sim_account`` 的分工：

* ``sim_account.StockSimStore`` —— **股票**模拟盘，**参与撮合**（下单/持仓/权益都在里面）
* ``TqAccountStore``（本模块）    —— **期货**实盘/模拟账户，**只记录不撮合**
  （订单还是天勤管的，这里只是把 ``get_account()`` / ``get_trade()`` 的结果存下来，
  这样：① 权益曲线重启不丢；② 多账户/多进程可以事后汇总对比 ✓）

默认路径 ``~/.minibt/tq_accounts.sqlite3``（可用 ``path=`` 覆盖 / ``path=':memory:'``）。

表结构：

    account(name, ts, balance, available, float_profit, close_profit, extra,
            ratio, session)                 -- 每 5 秒一个权益点（主键 name+ts）
    trade(name, trade_id, ts, symbol, direction, offset, price, volume,
          commission, realized_pnl)         -- 成交（主键 name+trade_id → 自动去重）

用法：

    >>> from minibt import TqAccountStore
    >>> store = TqAccountStore()
    >>> store.record_account('H宏源期货/123456', {'balance': 100000, ...})
    >>> store.equity('H宏源期货/123456')[-1]
    ('2026-10-18 14:05:01', 100320.0)
    >>> store.names()
    ['H宏源期货/123456']
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .utils import PROGRAM_START

#: 默认库文件（和股票模拟盘 ``stock_sim.sqlite3`` 放同一个目录 ✓）
DEFAULT_DB = os.path.join(os.path.expanduser('~'), '.minibt',
                          'tq_accounts.sqlite3')

#: 程序本次运行的标记（用于区分「本次会话」的权益点）
SESSION_TAG = time.strftime('%Y%m%d_%H%M%S', time.localtime(PROGRAM_START))

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS account(
        name TEXT NOT NULL,
        ts TEXT NOT NULL,
        balance REAL,
        available REAL,
        float_profit REAL,
        close_profit REAL,
        extra REAL,
        ratio REAL,
        session TEXT,
        PRIMARY KEY(name, ts))""",
    """CREATE TABLE IF NOT EXISTS trade(
        name TEXT NOT NULL,
        trade_id TEXT NOT NULL,
        ts TEXT,
        symbol TEXT,
        direction TEXT,
        offset TEXT,
        price REAL,
        volume INTEGER,
        commission REAL,
        realized_pnl REAL,
        PRIMARY KEY(name, trade_id))""",
    """CREATE INDEX IF NOT EXISTS ix_account_ts ON account(name, ts)""",
    """CREATE INDEX IF NOT EXISTS ix_trade_ts ON trade(name, ts)""",
)


class TqAccountStore:
    """期货账户记录器（sqlite；线程安全，可跨进程读 ✓）。"""

    def __init__(self, path: Optional[str] = None):
        self.path = str(path or DEFAULT_DB)
        if self.path not in (':memory:', '') and os.path.dirname(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute('PRAGMA journal_mode=WAL')
        for sql in _SCHEMA:
            self._conn.execute(sql)
        self._conn.commit()

    # ------------------------------------------------------------- 写入
    def record_account(self, name: str, summary: Dict[str, Any],
                       ts: Optional[str] = None,
                       session: Optional[str] = None) -> bool:
        """记一个权益点（同一 ``name+ts`` 只留一条 → 重复调用幂等 ✓）"""
        name = str(name or '').strip()
        if not name or not summary:
            return False
        ts = str(ts or time.strftime('%Y-%m-%d %H:%M:%S'))
        row = (name, ts,
               _float(summary.get('balance')),
               _float(summary.get('available')),
               _float(summary.get('float_profit')),
               _float(summary.get('close_profit')),
               _float(summary.get('extra')),
               _float(summary.get('ratio')),
               str(session or SESSION_TAG))
        with self._lock:
            self._conn.execute(
                'INSERT OR REPLACE INTO account(name, ts, balance, available,'
                ' float_profit, close_profit, extra, ratio, session)'
                ' VALUES(?,?,?,?,?,?,?,?,?)', row)
            self._conn.commit()
        return True

    def record_trade(self, name: str, trade: Dict[str, Any]) -> bool:
        """记一笔成交（``trade_id`` 相同 → 自动跳过 ✓ 返回 False）"""
        name = str(name or '').strip()
        trade_id = str(trade.get('trade_id') or '').strip()
        if not name or not trade_id:
            return False
        with self._lock:
            cursor = self._conn.execute(
                'INSERT OR IGNORE INTO trade(name, trade_id, ts, symbol,'
                ' direction, offset, price, volume, commission, realized_pnl)'
                ' VALUES(?,?,?,?,?,?,?,?,?,?)',
                (name, trade_id, str(trade.get('ts') or ''), 
                 str(trade.get('symbol') or ''),
                 str(trade.get('direction') or ''),
                 str(trade.get('offset') or ''),
                 _float(trade.get('price')),
                 _int(trade.get('volume')),
                 _float(trade.get('commission')),
                 _float(trade.get('realized_pnl'))))
            self._conn.commit()
            return bool(cursor.rowcount)

    # ------------------------------------------------------------- 读取
    def names(self) -> List[str]:
        """所有记录过的账户名（按最近一条权益点倒序 ✓）"""
        with self._lock:
            rows = self._conn.execute(
                'SELECT name, MAX(ts) AS last FROM account'
                ' GROUP BY name ORDER BY last DESC').fetchall()
        return [str(row[0]) for row in rows]

    def equity(self, name: str, since: Optional[str] = None,
               limit: Optional[int] = None
               ) -> List[Tuple[str, float]]:
        """权益曲线 ``[(ts, balance), ...]``（``since`` 是 'YYYY-MM-DD HH:MM:SS'）"""
        sql = ('SELECT ts, balance FROM account WHERE name=? AND balance'
               ' IS NOT NULL')
        args: List[Any] = [str(name)]
        if since:
            sql += ' AND ts >= ?'
            args.append(str(since))
        sql += ' ORDER BY ts'
        if limit:
            sql += ' DESC LIMIT %d' % int(limit)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        points = [(str(row[0]), float(row[1])) for row in rows]
        return list(reversed(points)) if limit else points

    def trades(self, name: str, limit: int = 200) -> List[Dict[str, Any]]:
        """最近成交（新的在前 ✓）"""
        with self._lock:
            rows = self._conn.execute(
                'SELECT ts, symbol, direction, offset, price, volume,'
                ' commission, realized_pnl, trade_id FROM trade'
                ' WHERE name=? ORDER BY ts DESC, trade_id DESC LIMIT ?',
                (str(name), int(limit))).fetchall()
        keys = ('ts', 'symbol', 'direction', 'offset', 'price', 'volume',
                'commission', 'realized_pnl', 'trade_id')
        return [dict(zip(keys, row)) for row in rows]

    def overview(self) -> List[Dict[str, Any]]:
        """每个账户一条最新快照（``latest`` 是最近一个权益点 ✓）"""
        result = []
        for name in self.names():
            points = self.equity(name)
            latest = points[-1] if points else (None, None)
            first = points[0] if points else (None, None)
            profit = (None if latest[1] is None or first[1] is None
                      else latest[1] - first[1])
            result.append({'name': name, 'count': len(points),
                           'first_ts': first[0], 'first': first[1],
                           'last_ts': latest[0], 'last': latest[1],
                           'profit': profit})
        return result

    # ------------------------------------------------------------- 维护
    def reset(self, name: Optional[str] = None) -> None:
        """清空（``name=None`` → 全部 ✓）"""
        with self._lock:
            if name:
                for table in ('account', 'trade'):
                    self._conn.execute(f'DELETE FROM {table} WHERE name=?',
                                       (str(name),))
            else:
                for table in ('account', 'trade'):
                    self._conn.execute(f'DELETE FROM {table}')
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:                                    # noqa: BLE001
                pass

    def __repr__(self) -> str:
        return f'TqAccountStore({self.path!r})'


def _float(value) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _int(value) -> Optional[int]:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None
