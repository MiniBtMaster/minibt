"""全市场合约索引（复刻 miniqt「商品代码搜索」✓）

miniqt 的搜索框**不分类型 / 交易所** —— 输入 `rb` / `600000` / `00700` 都能找到。
desk 之前的 `search_pool()` 只扫**报价页当前看过**的缓存，所以切了交易所就搜不到
别的市场（用户反馈 ✗）。

这里建一份**全市场索引**：

* 期货：`FUT` / `CONT_MAIN` / `INDEX` × 6 家交易所（天勤 `query_quotes`）
* 期权：`OPTION` × 6 家（量大，默认不动；`include_options=True` 才拉）
* 股票：`SSE` / `SZSE` / `HK` / `US`（Futu / `StockApi`）

落到 ``~/.minibt/desk_symbol_index.sqlite3``，24 小时有效；构建在**后台线程**，
所以打开搜索框时不卡（先给缓存里的，索引好了自动变全 ✓）。
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

#: 索引文件（和别的 desk 数据放一起 ✓）
INDEX_FILE = os.path.join(os.path.expanduser('~'), '.minibt',
                          'desk_symbol_index.sqlite3')

#: 多久算过期（秒）—— 新合约不常有，一天一次足够 ✓
MAX_AGE = 24 * 3600

#: 期货要拉的合约类型（期权太多，默认不拉 ✓）
FUTURES_CLASSES = ('FUT', 'CONT_MAIN', 'INDEX')

#: 类型 → 中文（搜索结果右侧 / 筛选 chips ✓）
TYPE_LABELS = {
    'FUT': '期货', 'CONT_MAIN': '主连', 'INDEX': '指数', 'OPTION': '期权',
    'STOCK': '股票', 'ETF': '基金',
}

#: 市场 chips（miniqt 顶部那排 ✓）
MARKETS = (
    ('', '全部'),
    ('FUT', '期货'),
    ('CONT_MAIN', '主连'),
    ('INDEX', '指数'),
    ('OPTION', '期权'),
    ('STOCK', '股票'),
)

_LOCK = threading.RLock()


def disabled() -> bool:
    """`MINIBT_DESK_NO_INDEX=1` → 不建全市场索引（测试 / 断网时 ✓）"""
    return str(os.environ.get('MINIBT_DESK_NO_INDEX') or '').strip().lower()         in ('1', 'true', 'yes', 'on')


# ---------------------------------------------------------------- sqlite
def _connect(path: Optional[str] = None) -> Optional[sqlite3.Connection]:
    try:
        folder = os.path.dirname(path or INDEX_FILE)
        if folder:
            os.makedirs(folder, exist_ok=True)
        conn = sqlite3.connect(path or INDEX_FILE)
        conn.execute(
            'CREATE TABLE IF NOT EXISTS symbols ('
            'symbol TEXT PRIMARY KEY, name TEXT, exchange TEXT, type TEXT, '
            'market TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, '
                     'value TEXT)')
        return conn
    except Exception:                                            # noqa: BLE001
        return None


def save(rows: Iterable[Dict[str, Any]], path: Optional[str] = None) -> bool:
    """整表写入（先清空再批量插 ✓）"""
    conn = _connect(path)
    if conn is None:
        return False
    try:
        with conn:
            conn.execute('DELETE FROM symbols')
            conn.executemany(
                'INSERT OR REPLACE INTO symbols '
                '(symbol, name, exchange, type, market) VALUES (?,?,?,?,?)',
                [(str(row.get('symbol') or ''), str(row.get('name') or ''),
                  str(row.get('exchange') or ''), str(row.get('type') or ''),
                  str(row.get('market') or ''))
                 for row in rows if row.get('symbol')])
            conn.execute('INSERT OR REPLACE INTO meta (key, value) '
                         'VALUES ("built_at", ?)', (str(int(time.time())),))
        return True
    except Exception:                                            # noqa: BLE001
        return False
    finally:
        conn.close()


def load(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """读出索引（没有 → 空列表 ✓）"""
    if not os.path.exists(path or INDEX_FILE):
        return []
    conn = _connect(path)
    if conn is None:
        return []
    try:
        rows = conn.execute(
            'SELECT symbol, name, exchange, type, market FROM symbols'
        ).fetchall()
    except Exception:                                            # noqa: BLE001
        rows = []
    finally:
        conn.close()
    return [{'symbol': row[0], 'name': row[1], 'exchange': row[2],
             'type': row[3], 'market': row[4],
             'type_label': TYPE_LABELS.get(row[3], row[3])}
            for row in rows]


def built_at(path: Optional[str] = None) -> int:
    if not os.path.exists(path or INDEX_FILE):
        return 0
    conn = _connect(path)
    if conn is None:
        return 0
    try:
        row = conn.execute(
            'SELECT value FROM meta WHERE key = "built_at"').fetchone()
        return int(row[0]) if row else 0
    except Exception:                                            # noqa: BLE001
        return 0
    finally:
        conn.close()


def stale(path: Optional[str] = None, max_age: int = MAX_AGE) -> bool:
    """索引是否该重建（不存在 / 过期 / 空表 ✓）"""
    if not os.path.exists(path or INDEX_FILE):
        return True
    return (time.time() - built_at(path)) > max_age


# ---------------------------------------------------------------- 构建
def build(feeds: Iterable[Any], *, include_options: bool = False,
          on_progress: Optional[Callable[[str, int], None]] = None,
          path: Optional[str] = None,
          incremental: bool = False) -> List[Dict[str, Any]]:
    """拉**所有市场**的合约（后台线程里跑 ✓）

    Args:
        feeds: `Desk.feeds`（期货 feed + 股票 feed）
        include_options: 是否也拉期权（很慢，默认关）
        on_progress: `(market_label, count)` 回调（写日志用）

    Returns:
        索引行 ``[{symbol, name, exchange, type, market, type_label}]``
    """
    from . import symbols as _symbols

    rows: List[Dict[str, Any]] = []
    seen = set()
    existing = load(path) if incremental else []
    for row in existing:                 # 增量：保留已有条目，只补新的 ✓
        seen.add(str(row.get('symbol') or ''))
    rows.extend(existing)

    def add(symbol: str, name: str, exchange: str, kind: str, market: str):
        symbol = str(symbol or '').strip()
        if not symbol or symbol in seen:
            return
        seen.add(symbol)
        rows.append({'symbol': symbol, 'name': str(name or ''),
                     'exchange': str(exchange or ''), 'type': str(kind or ''),
                     'market': str(market or ''),
                     'type_label': TYPE_LABELS.get(kind, kind)})

    futures = next((feed for feed in feeds
                    if getattr(feed, 'kind', '') == 'futures'), None)
    stocks = next((feed for feed in feeds
                   if getattr(feed, 'kind', '') == 'stocks'), None)

    # ---- 期货：所有类型 × 所有交易所 ----
    if futures is not None and getattr(futures, 'available', lambda: False)():
        classes = list(FUTURES_CLASSES) + (['OPTION'] if include_options else [])
        for kind in classes:
            exchanges = _symbols.DEFAULT_EXCHANGES.get(kind) or []
            if kind == 'OPTION' and not exchanges:
                exchanges = _symbols.DEFAULT_EXCHANGES.get('OPTION') or []
            for exchange, label in exchanges:
                try:
                    # ★ 只读本地符号字典（不发请求，绝不阻塞 ✓）
                    getter = getattr(futures, 'contracts_local',
                                     futures.contracts)
                    names = getter(kind, exchange) or []
                except Exception:                                # noqa: BLE001
                    names = []
                # ⚠ 这里**不调** `fill_names`：几千个合约的
                #   `query_symbol_info` 会在后台线程里阻塞 tqsdk，
                #   主线程 `pump()` 抢锁 → 界面转圈（用户实测 ✗）。
                #   名称由 `Desk._fill_names_step()` 在主线程小批补 ✓
                for symbol in names:
                    add(symbol, futures.name_of(symbol), exchange, kind, label)
                if on_progress:
                    added = sum(1 for row in rows if row.get('market') == label)
                    on_progress(f'{label} · {TYPE_LABELS.get(kind, kind)}',
                                added if incremental else len(names))
                if rows:
                    save(rows, path)           # 每个交易所存一次（断了也不白跑 ✓）

    # ---- 股票：4 个市场 ----
    if stocks is not None and getattr(stocks, 'available', lambda: False)():
        for exchange, label in _symbols.DEFAULT_EXCHANGES.get('STOCK') or []:
            try:
                items = stocks.stock_rows(exchange) or []
            except Exception:                                    # noqa: BLE001
                items = []
            for item in items:
                symbol = str(item.get('symbol') or '')
                add(symbol, str(item.get('name') or ''), exchange, 'STOCK',
                    label)
            if on_progress:
                on_progress(label, len(items))
            if rows:
                save(rows, path)

    save(rows, path)
    return rows


# ---------------------------------------------------------------- 搜索
def _score(row: Dict[str, Any], text: str) -> tuple:
    """排序：代码前缀 > 代码包含 > 名称前缀 > 名称包含（同 miniqt 手感 ✓）"""
    symbol = str(row.get('symbol') or '').lower()
    name = str(row.get('name') or '').lower()
    bare = symbol.split('.')[-1]
    if bare == text or symbol == text:
        return (0, symbol)
    if bare.startswith(text) or symbol.startswith(text):
        return (1, symbol)
    if text in symbol:
        return (2, symbol)
    if name.startswith(text):
        return (3, name)
    if text in name:
        return (4, name)
    return (9, symbol)


def search(rows: List[Dict[str, Any]], text: str = '', market: str = '',
           limit: int = 60) -> List[Dict[str, Any]]:
    """全市场搜索（`market` = `FUT` / `STOCK` / … ，空 = 全部 ✓）"""
    text = str(text or '').strip().lower()
    market = str(market or '').strip().upper()
    pool = rows
    if market:
        pool = [row for row in rows
                if str(row.get('type') or '').upper() == market]
    if not text:
        return []                     # 空输入不刷全表（几万个太吓人 ✗）
    matched = [row for row in pool if _score(row, text)[0] < 9]
    matched.sort(key=lambda row: _score(row, text))
    return matched[:int(limit)]


def markets_payload() -> List[Dict[str, str]]:
    """chips 数据（`{key, label}` ✓）"""
    return [{'key': key, 'label': label} for key, label in MARKETS]


def batches(feeds: Iterable[Any], *, include_options: bool = False,
            path: Optional[str] = None):
    """**逐市场**产出索引（生成器；给主线程每拍建一批，避免卡界面 ✓）

    用法::

        job = batches(desk.feeds)
        label, rows = next(job)      # 每次只拉一个市场（几十毫秒）

    每批都会 `save()` 一次（中途退出也不白跑 ✓）。
    """
    from . import symbols as _symbols

    rows: List[Dict[str, Any]] = list(load(path) or [])
    seen = {str(row.get('symbol') or '') for row in rows}

    def add(symbol: str, name: str, exchange: str, kind: str,
            market: str) -> None:
        symbol = str(symbol or '').strip()
        if not symbol or symbol in seen:
            return
        seen.add(symbol)
        rows.append({'symbol': symbol, 'name': str(name or ''),
                     'exchange': str(exchange or ''), 'type': str(kind or ''),
                     'market': str(market or ''),
                     'type_label': TYPE_LABELS.get(kind, kind)})

    futures = next((feed for feed in feeds
                    if getattr(feed, 'kind', '') == 'futures'), None)
    stocks = next((feed for feed in feeds
                   if getattr(feed, 'kind', '') == 'stocks'), None)

    if futures is not None and getattr(futures, 'available', lambda: False)():
        classes = list(FUTURES_CLASSES) + (['OPTION'] if include_options else [])
        for kind in classes:
            exchanges = _symbols.DEFAULT_EXCHANGES.get(kind) or []
            for exchange, label in exchanges:
                try:
                    names = futures.contracts(kind, exchange) or []
                except Exception:                                # noqa: BLE001
                    names = []
                for symbol in names:
                    add(symbol, futures.name_of(symbol), exchange, kind, label)
                save(rows, path)
                yield f'{label} · {TYPE_LABELS.get(kind, kind)}', rows

    if stocks is not None and getattr(stocks, 'available', lambda: False)():
        for exchange, label in _symbols.DEFAULT_EXCHANGES.get('STOCK') or []:
            try:
                items = stocks.stock_rows(exchange) or []
            except Exception:                                    # noqa: BLE001
                items = []
            for item in items:
                add(str(item.get('symbol') or ''), str(item.get('name') or ''),
                    exchange, 'STOCK', label)
            save(rows, path)
            yield label, rows

    save(rows, path)


def refresh(feeds: Iterable[Any], *, path: Optional[str] = None,
            on_progress: Optional[Callable[[str, int], None]] = None
            ) -> List[Dict[str, Any]]:
    """**增量更新**：只补新上市 / 新标的，不必整天重建 ✓

    已经全量建过一次（文件在）→ 走 `build(incremental=True)`；
    没有索引文件 → 直接全量建。
    """
    if not os.path.exists(path or INDEX_FILE):
        return build(feeds, path=path, on_progress=on_progress)
    return build(feeds, path=path, on_progress=on_progress, incremental=True)


def count(path: Optional[str] = None) -> int:
    """索引里的合约数（不载入全部数据 ✓）"""
    if not os.path.exists(path or INDEX_FILE):
        return 0
    conn = _connect(path)
    if conn is None:
        return 0
    try:
        row = conn.execute('SELECT COUNT(*) FROM symbols').fetchone()
        return int(row[0]) if row else 0
    except Exception:                                            # noqa: BLE001
        return 0
    finally:
        conn.close()
