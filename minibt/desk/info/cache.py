"""资讯缓存（SQLite，`~/.minibt/data/info.db`）。

用户 2026-11-08 确认的落库策略：**只存标题 + 时间 + 来源 + 链接 + 短摘要**，
不落正文（体积小、无版权风险），可以离线看列表 / 搜索。
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

#: 缓存库路径（测试可改 / `MINIBT_DESK_INFO_DB` 覆盖 ✓）
DB_FILE = os.environ.get(
    'MINIBT_DESK_INFO_DB',
    os.path.join(os.path.expanduser('~'), '.minibt', 'data', 'info.db'))

#: 缓存 TTL（秒）
TTL = {
    'flash': 60,          # 快讯：1 分钟
    'market': 600,        # 要闻：10 分钟
    'symbol': 900,        # 个股新闻：15 分钟
    'futures': 900,       # 期货新闻：15 分钟
    'calendar': 6 * 3600,  # 财经日历：6 小时
    'macro': 12 * 3600,    # 宏观：12 小时（月度 / 季度数据 ✓）
    'contract': 12 * 3600,  # 合约规则（保证金 / 涨跌停）：12 小时
    'inventory': 6 * 3600,  # 库存：6 小时
    'basis': 3600,          # 基差：1 小时（每天变 ✓）
    'profile': 12 * 3600,   # 个股资料：12 小时
    'capital': 300,         # 资金流：5 分钟
    'financials': 24 * 3600,  # 财务摘要：1 天（东财接口要拉十几页、30s+ ✗）
    'notices': 1800,        # 公告：30 分钟（按天翻页，较慢 ✓）
}

_LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    symbol TEXT DEFAULT '',
    title TEXT, summary TEXT, source TEXT, url TEXT,
    published TEXT, fetched REAL
);
CREATE INDEX IF NOT EXISTS news_kind ON news (kind, symbol, published);
CREATE TABLE IF NOT EXISTS calendar (
    id TEXT PRIMARY KEY,
    day TEXT NOT NULL, time TEXT, region TEXT, event TEXT,
    actual TEXT, forecast TEXT, previous TEXT,
    importance INTEGER DEFAULT 0, fetched REAL
);
CREATE INDEX IF NOT EXISTS calendar_day ON calendar (day, time);
-- 全文搜索（FTS5 trigram：中文也能按字串搜；不支持时自动退回 LIKE ✓）
CREATE VIRTUAL TABLE IF NOT EXISTS news_fts USING fts5(
    title, summary, content='news', content_rowid='rowid',
    tokenize='trigram'
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY, value TEXT, fetched REAL
);
-- 宏观 / 合约规则 / 库存 / 基差这类「整块快照」：JSON 存一行 + TTL ✓
CREATE TABLE IF NOT EXISTS snapshots (
    key TEXT PRIMARY KEY, payload TEXT, fetched REAL
);
"""


def _connect() -> sqlite3.Connection:
    folder = os.path.dirname(DB_FILE)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# ---------------------------------------------------------------- 新闻
def _fts_ok(conn) -> bool:
    try:
        conn.execute("SELECT count(*) FROM news_fts")
        return True
    except Exception:                                        # noqa: BLE001
        return False


def save_news(items: List[Dict[str, Any]]) -> int:
    """写入 / 覆盖（`id` 天然去重 ✓），返回写入条数"""
    rows = [item for item in (items or []) if item.get('id')]
    if not rows:
        return 0
    now = time.time()
    with _LOCK:
        conn = _connect()
        try:
            conn.executemany(
                'INSERT OR REPLACE INTO news '
                '(id, kind, symbol, title, summary, source, url, published,'
                ' fetched) VALUES (?,?,?,?,?,?,?,?,?)',
                [(item['id'], item.get('kind') or 'flash',
                  item.get('symbol') or '', item.get('title') or '',
                  item.get('summary') or '', item.get('source') or '',
                  item.get('url') or '', item.get('published') or '',
                  now) for item in rows])
            if _fts_ok(conn):
                try:
                    conn.execute("INSERT INTO news_fts (news_fts) "
                                 "VALUES ('rebuild')")
                except Exception:                            # noqa: BLE001
                    pass
            conn.commit()
        finally:
            conn.close()
    return len(rows)


def load_news(kind: str = '', symbol: str = '', limit: int = 40,
              query: str = '') -> List[Dict[str, Any]]:
    """读缓存（最新在前）；`query` 走 LIKE（P2 换 FTS5 ✓）"""
    where = []
    args: List[Any] = []
    if kind:
        where.append('kind = ?')
        args.append(str(kind))
    if symbol:
        where.append('symbol = ?')
        args.append(str(symbol))
    if query:
        where.append('(title LIKE ? OR summary LIKE ?)')
        args.extend([f'%{query}%', f'%{query}%'])
    sql = 'SELECT * FROM news'
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY published DESC, fetched DESC LIMIT ?'
    args.append(max(1, min(int(limit or 40), 500)))
    with _LOCK:
        conn = _connect()
        try:
            rows = [dict(row) for row in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()
    return rows


def search_news(query: str, limit: int = 40) -> List[Dict[str, Any]]:
    """全文搜索：**FTS5 trigram 优先**，不支持时退回 LIKE（结果一致 ✓）"""
    text = str(query or '').strip()
    if not text:
        return []
    size = max(1, min(int(limit or 40), 500))
    # ★ trigram 索引至少要 3 个字；两个字的词（「降准」）直接走 LIKE ✓
    if len(text) < 3:
        return load_news(limit=size, query=text)
    with _LOCK:
        conn = _connect()
        try:
            if _fts_ok(conn):
                try:
                    rows = conn.execute(
                        'SELECT n.* FROM news_fts f '
                        'JOIN news n ON n.rowid = f.rowid '
                        'WHERE news_fts MATCH ? '
                        'ORDER BY n.published DESC LIMIT ?',
                        (f'"{text}"', size)).fetchall()
                    return [dict(row) for row in rows]
                except Exception:                        # noqa: BLE001
                    pass
        finally:
            conn.close()
    return load_news(limit=size, query=text)


# ---------------------------------------------------------------- 日历
def save_calendar(items: List[Dict[str, Any]]) -> int:
    rows = [item for item in (items or []) if item.get('id')]
    if not rows:
        return 0
    now = time.time()
    with _LOCK:
        conn = _connect()
        try:
            conn.executemany(
                'INSERT OR REPLACE INTO calendar '
                '(id, day, time, region, event, actual, forecast, previous,'
                ' importance, fetched) VALUES (?,?,?,?,?,?,?,?,?,?)',
                [(item['id'], item.get('day') or '', item.get('time') or '',
                  item.get('region') or '', item.get('event') or '',
                  item.get('actual') or '', item.get('forecast') or '',
                  item.get('previous') or '',
                  int(item.get('importance') or 0), now) for item in rows])
            conn.commit()
        finally:
            conn.close()
    return len(rows)


def load_calendar(days: Optional[List[str]] = None,
                  limit: int = 200) -> List[Dict[str, Any]]:
    sql = 'SELECT * FROM calendar'
    args: List[Any] = []
    if days:
        marks = ','.join('?' for _ in days)
        sql += f' WHERE day IN ({marks})'
        args.extend(days)
    sql += ' ORDER BY day ASC, time ASC LIMIT ?'
    args.append(max(1, min(int(limit or 200), 1000)))
    with _LOCK:
        conn = _connect()
        try:
            return [dict(row) for row in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()


# ---------------------------------------------------------------- 快照
def save_snapshot(key: str, payload: Any) -> None:
    """宏观 / 合约规则 / 库存 / 基差的整块快照（JSON ✓）"""
    import json as _json
    with _LOCK:
        conn = _connect()
        try:
            conn.execute('INSERT OR REPLACE INTO snapshots '
                         '(key, payload, fetched) VALUES (?,?,?)',
                         (str(key), _json.dumps(payload, ensure_ascii=False),
                          time.time()))
            conn.commit()
        finally:
            conn.close()


def load_snapshot(key: str) -> Dict[str, Any]:
    """读快照 → `{'payload': ..., 'fetched': ts}`；没有就空字典 ✓"""
    import json as _json
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute('SELECT * FROM snapshots WHERE key = ?',
                               (str(key),)).fetchone()
        finally:
            conn.close()
    if not row:
        return {}
    try:
        payload = _json.loads(row['payload'] or 'null')
    except Exception:                                         # noqa: BLE001
        payload = None
    return {'payload': payload, 'fetched': float(row['fetched'] or 0)}


def snapshot_fresh(key: str, kind: str) -> bool:
    row = load_snapshot(key)
    if not row:
        return False
    return (time.time() - float(row.get('fetched') or 0)) < float(
        TTL.get(kind, 3600))


# ---------------------------------------------------------------- meta / TTL
def meta_set(key: str, value: str = '') -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute('INSERT OR REPLACE INTO meta (key, value, fetched)'
                         ' VALUES (?,?,?)', (str(key), str(value), time.time()))
            conn.commit()
        finally:
            conn.close()


def meta_get(key: str) -> Dict[str, Any]:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute('SELECT * FROM meta WHERE key = ?',
                               (str(key),)).fetchone()
        finally:
            conn.close()
    return dict(row) if row else {}


def fresh(key: str, kind: str) -> bool:
    """缓存还新鲜吗（`key` 由 service 拼好 ✓）"""
    row = meta_get(key)
    if not row:
        return False
    ttl = float(TTL.get(kind, 600))
    return (time.time() - float(row.get('fetched') or 0)) < ttl


def stats() -> Dict[str, Any]:
    """缓存统计（设置页「数据源体检」用 ✓）"""
    with _LOCK:
        conn = _connect()
        try:
            news = conn.execute('SELECT COUNT(*) AS n FROM news').fetchone()
            cal = conn.execute('SELECT COUNT(*) AS n FROM calendar').fetchone()
            last = conn.execute(
                'SELECT MAX(fetched) AS t FROM news').fetchone()
        finally:
            conn.close()
    return {'file': DB_FILE, 'news': int(news['n'] if news else 0),
            'calendar': int(cal['n'] if cal else 0),
            'last_fetch': float(last['t'] or 0) if last else 0.0}


def clear() -> Dict[str, Any]:
    """清空缓存（不动配置 ✓）"""
    with _LOCK:
        conn = _connect()
        try:
            conn.execute('DELETE FROM news')
            conn.execute('DELETE FROM calendar')
            conn.execute('DELETE FROM meta')
            conn.execute('DELETE FROM snapshots')
            conn.commit()
        finally:
            conn.close()
    return stats()
