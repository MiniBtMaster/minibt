# coding: utf-8
"""minibt 本地**模拟盘**账户的持久化（sqlite，零外部依赖）。

`StockApi` 在 ``trade=False`` 时用本模块记账，所以**关掉程序再打开**还能读到
上一次的：现金 / 持仓 / 委托 / 成交 / 权益曲线。

默认位置：``~/.minibt/stock_sim.sqlite3``（可用 ``sim_db`` 指定）。

表结构：

| 表 | 内容 |
| --- | --- |
| ``account`` | 每个账户（``account_key``）的初始资金 / 现金 / 已实现盈亏 / 手续费 |
| ``positions`` | 持仓（按账户 + 代码；多空手数 + 均价） |
| ``orders`` | 委托（含状态；撤单会更新状态） |
| ``trades`` | 成交（每笔含已实现盈亏） |
| ``equity`` | 权益曲线（时间点快照：现金 / 市值 / 权益 / 浮盈 / 已实现） |
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time

#: 默认数据库路径（``~/.minibt/stock_sim.sqlite3`` ✓）
DEFAULT_DB = os.path.join(os.path.expanduser('~'), '.minibt',
                          'stock_sim.sqlite3')

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS account (
        account_key   TEXT PRIMARY KEY,
        initial_cash  REAL NOT NULL DEFAULT 100000,
        cash          REAL NOT NULL DEFAULT 100000,
        realized_pnl  REAL NOT NULL DEFAULT 0,
        commission    REAL NOT NULL DEFAULT 0,
        created_at    TEXT,
        updated_at    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS positions (
        account_key TEXT NOT NULL,
        code        TEXT NOT NULL,
        long_qty    REAL NOT NULL DEFAULT 0,
        short_qty   REAL NOT NULL DEFAULT 0,
        avg_long    REAL NOT NULL DEFAULT 0,
        avg_short   REAL NOT NULL DEFAULT 0,
        updated_at  TEXT,
        PRIMARY KEY (account_key, code)
    )""",
    """CREATE TABLE IF NOT EXISTS orders (
        account_key TEXT NOT NULL,
        order_id    TEXT PRIMARY KEY,
        code        TEXT,
        direction   TEXT,
        offset      TEXT,
        qty         REAL,
        price       REAL,
        status      TEXT,
        created_at  TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS trades (
        account_key  TEXT NOT NULL,
        trade_id     TEXT PRIMARY KEY,
        order_id     TEXT,
        code         TEXT,
        direction    TEXT,
        offset       TEXT,
        qty          REAL,
        price        REAL,
        realized_pnl REAL,
        created_at   TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS equity (
        account_key  TEXT NOT NULL,
        ts           TEXT NOT NULL,
        cash         REAL,
        market_value REAL,
        balance      REAL,
        float_profit REAL,
        realized_pnl REAL,
        PRIMARY KEY (account_key, ts)
    )""",
)


class StockSimStore:
    """一个账户的 sqlite 持久化（线程安全 ✓）"""

    def __init__(self, account_key: str = 'default',
                 db_path: str | None = None,
                 initial_cash: float = 100000.0) -> None:
        self.key = str(account_key or 'default')
        self.path = str(db_path or DEFAULT_DB)
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        try:
            self._conn.execute('PRAGMA journal_mode=WAL')
        except sqlite3.Error:
            pass
        with self._lock:
            for statement in _SCHEMA:
                self._conn.execute(statement)
            self._conn.execute(
                'INSERT OR IGNORE INTO account'
                ' (account_key, initial_cash, cash, created_at, updated_at)'
                ' VALUES (?, ?, ?, ?, ?)',
                (self.key, float(initial_cash), float(initial_cash),
                 self._now(), self._now()))
            self._conn.commit()

    # ---------------------------------------------------------------- 基础
    @staticmethod
    def _now() -> str:
        return time.strftime('%Y-%m-%d %H:%M:%S')

    def _rows(self, sql: str, params=()) -> list:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            return cursor.fetchall()

    def _write(self, sql: str, params=()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    # ---------------------------------------------------------------- 账户
    def load_account(self) -> dict:
        rows = self._rows(
            'SELECT initial_cash, cash, realized_pnl, commission'
            ' FROM account WHERE account_key=?', (self.key,))
        if not rows:
            return {'initial_cash': 100000.0, 'cash': 100000.0,
                    'realized_pnl': 0.0, 'commission': 0.0}
        initial, cash, realized, commission = rows[0]
        return {'initial_cash': float(initial), 'cash': float(cash),
                'realized_pnl': float(realized or 0.0),
                'commission': float(commission or 0.0)}

    def save_account(self, cash: float, realized_pnl: float,
                     commission: float) -> None:
        self._write(
            'UPDATE account SET cash=?, realized_pnl=?, commission=?,'
            ' updated_at=? WHERE account_key=?',
            (float(cash), float(realized_pnl), float(commission),
             self._now(), self.key))

    # ---------------------------------------------------------------- 持仓
    def load_positions(self) -> dict:
        rows = self._rows(
            'SELECT code, long_qty, short_qty, avg_long, avg_short'
            ' FROM positions WHERE account_key=?', (self.key,))
        return {
            str(code): {'long': float(long_qty or 0.0),
                        'short': float(short_qty or 0.0),
                        'avg_long': float(avg_long or 0.0),
                        'avg_short': float(avg_short or 0.0)}
            for code, long_qty, short_qty, avg_long, avg_short in rows
        }

    def save_position(self, code: str, book: dict) -> None:
        self._write(
            'INSERT INTO positions (account_key, code, long_qty, short_qty,'
            ' avg_long, avg_short, updated_at) VALUES (?,?,?,?,?,?,?)'
            ' ON CONFLICT(account_key, code) DO UPDATE SET'
            ' long_qty=excluded.long_qty, short_qty=excluded.short_qty,'
            ' avg_long=excluded.avg_long, avg_short=excluded.avg_short,'
            ' updated_at=excluded.updated_at',
            (self.key, str(code), float(book.get('long') or 0.0),
             float(book.get('short') or 0.0),
             float(book.get('avg_long') or 0.0),
             float(book.get('avg_short') or 0.0), self._now()))

    # ---------------------------------------------------------------- 委托
    def add_order(self, order_id: str, code: str, direction: str,
                  offset: str, qty: float, price: float,
                  status: str = 'FINISHED') -> None:
        self._write(
            'INSERT OR REPLACE INTO orders (account_key, order_id, code,'
            ' direction, offset, qty, price, status, created_at)'
            ' VALUES (?,?,?,?,?,?,?,?,?)',
            (self.key, str(order_id), str(code), str(direction),
             str(offset), float(qty), float(price), str(status), self._now()))

    def update_order(self, order_id: str, status: str) -> None:
        self._write('UPDATE orders SET status=? WHERE account_key=?'
                    ' AND order_id=?', (str(status), self.key, str(order_id)))

    def recent_orders(self, limit: int = 200) -> list:
        """最近的委托（旧 → 新；给 ``StockApi.get_order()`` 用 ✓）"""
        rows = self._rows(
            'SELECT order_id, code, direction, offset, qty, price, status'
            ' FROM orders WHERE account_key=? ORDER BY created_at DESC,'
            ' rowid DESC LIMIT ?', (self.key, int(limit)))
        return [{'order_id': r[0], 'code': r[1], 'direction': r[2],
                 'offset': r[3], 'qty': float(r[4] or 0.0),
                 'price': float(r[5] or 0.0), 'status': r[6]}
                for r in reversed(rows)]

    # ---------------------------------------------------------------- 成交
    def add_trade(self, trade_id: str, order_id: str, code: str,
                  direction: str, offset: str, qty: float, price: float,
                  realized_pnl: float = 0.0) -> None:
        self._write(
            'INSERT OR REPLACE INTO trades (account_key, trade_id, order_id,'
            ' code, direction, offset, qty, price, realized_pnl, created_at)'
            ' VALUES (?,?,?,?,?,?,?,?,?,?)',
            (self.key, str(trade_id), str(order_id), str(code),
             str(direction), str(offset), float(qty), float(price),
             float(realized_pnl), self._now()))

    def recent_trades(self, limit: int = 200) -> list:
        rows = self._rows(
            'SELECT trade_id, order_id, code, direction, offset, qty, price,'
            ' realized_pnl, created_at FROM trades WHERE account_key=?'
            ' ORDER BY created_at DESC, rowid DESC LIMIT ?',
            (self.key, int(limit)))
        return [{'trade_id': r[0], 'order_id': r[1], 'code': r[2],
                 'direction': r[3], 'offset': r[4], 'qty': float(r[5] or 0.0),
                 'price': float(r[6] or 0.0),
                 'realized_pnl': float(r[7] or 0.0),
                 'created_at': r[8]}
                for r in reversed(rows)]

    # ---------------------------------------------------------------- 权益
    def add_equity(self, cash: float, market_value: float, balance: float,
                   float_profit: float, realized_pnl: float) -> None:
        self._write(
            'INSERT OR REPLACE INTO equity (account_key, ts, cash,'
            ' market_value, balance, float_profit, realized_pnl)'
            ' VALUES (?,?,?,?,?,?,?)',
            (self.key, time.strftime('%Y-%m-%d %H:%M:%S'), float(cash),
             float(market_value), float(balance), float(float_profit),
             float(realized_pnl)))

    def equity_curve(self, limit: int = 1000) -> list:
        rows = self._rows(
            'SELECT ts, balance, cash, market_value, float_profit,'
            ' realized_pnl FROM equity WHERE account_key=?'
            ' ORDER BY ts DESC LIMIT ?', (self.key, int(limit)))
        return [{'ts': r[0], 'balance': float(r[1] or 0.0),
                 'cash': float(r[2] or 0.0),
                 'market_value': float(r[3] or 0.0),
                 'float_profit': float(r[4] or 0.0),
                 'realized_pnl': float(r[5] or 0.0)}
                for r in reversed(rows)]

    # ---------------------------------------------------------------- 维护
    def reset(self, initial_cash: float | None = None) -> None:
        """清空该账户的持仓/委托/成交/权益（现金回到初始 ✓）"""
        account = self.load_account()
        cash = float(initial_cash if initial_cash is not None
                     else account['initial_cash'])
        with self._lock:
            for table in ('positions', 'orders', 'trades', 'equity'):
                self._conn.execute(
                    f'DELETE FROM {table} WHERE account_key=?', (self.key,))
            self._conn.execute(
                'UPDATE account SET initial_cash=?, cash=?, realized_pnl=0,'
                ' commission=0, updated_at=? WHERE account_key=?',
                (cash, cash, self._now(), self.key))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.commit()
            except sqlite3.Error:
                pass
            try:
                self._conn.close()
            except sqlite3.Error:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
