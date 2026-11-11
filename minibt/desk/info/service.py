"""资讯服务：**缓存优先 + 后台抓取**（页面 / MCP 工具都走这里 ✓）。

调用约定：

* `news()` / `calendar()` 立刻返回**缓存**（可能为空），需要新数据时
  `refresh_*` 在**后台线程**抓取并回调 `on_done`（desk 收到后用补丁推给前端）；
* 抓取失败不影响界面：返回缓存 + `stale` 标记 + `error` 原因；
* 所有入口都容忍「没装 AkShare」→ `need_install` + 安装提示。
"""
from __future__ import annotations

import datetime as _dt
import threading
from typing import Any, Callable, Dict, List, Optional

from . import cache, providers

#: 后台抓取去重（同一类同时只跑一个 ✓）
_RUNNING: Dict[str, bool] = {}
_LOCK = threading.Lock()

#: 没数据时的兜底（保持首页不空白；和旧版静态一样 ✓）
FALLBACK_EVENTS = [
    {'time': '20:30', 'text': '美国初请失业金人数', 'tail': '宏观',
     'tone': 'amber'},
    {'time': '22:00', 'text': '欧洲央行利率决议', 'tail': '宏观',
     'tone': 'blue'},
]


def _key(kind: str, symbol: str = '', day: str = '') -> str:
    """缓存标记键：空的部分不拼（`flash` / `flash:600519` ✓）"""
    return ':'.join(part for part in (kind, symbol, day) if part)


def _spawn(key: str, work: Callable[[], Any],
           on_done: Optional[Callable[[Any], None]] = None) -> bool:
    """后台跑一次抓取（同一个 key 不并发 ✓）"""
    with _LOCK:
        if _RUNNING.get(key):
            return False
        _RUNNING[key] = True

    def runner() -> None:
        result: Any = None
        error = ''
        try:
            result = work()
        except Exception as exc:                             # noqa: BLE001
            error = f'{type(exc).__name__}: {exc}'
        finally:
            with _LOCK:
                _RUNNING[key] = False
            if on_done is not None:
                try:
                    on_done({'result': result, 'error': error})
                except Exception:                            # noqa: BLE001
                    pass

    threading.Thread(target=runner, daemon=True).start()
    return True


# ---------------------------------------------------------------- 日历
def calendar(days: int = 3, day: Optional[str] = None,
             limit: int = 200) -> Dict[str, Any]:
    """读缓存里的财经日历（`day='YYYY-MM-DD'` 精确某天 ✓）"""
    days_list = [day] if day else [
        (_dt.date.today() + _dt.timedelta(days=offset)).isoformat()
        for offset in range(max(1, min(int(days or 3), 7)))]
    rows = cache.load_calendar(days_list, limit=limit)
    return {'ok': True, 'day': day or '', 'days': days_list,
            'count': len(rows), 'items': rows,
            'stale': not cache.fresh(_key('calendar', '', days_list[0]),
                                     'calendar'),
            'installed': providers.akshare_info()['installed']}


def refresh_calendar(days: int = 3,
                     on_done: Optional[Callable[[Dict[str, Any]], None]] = None
                     ) -> bool:
    """后台抓日历 → 写缓存 → 回调（`{'items': [...]}`）"""
    days = max(1, min(int(days or 3), 7))
    today = _dt.date.today().isoformat()

    def work() -> Dict[str, Any]:
        items = providers.fetch_calendar(days)
        saved = cache.save_calendar(items)
        cache.meta_set(_key('calendar', '', today), str(saved))
        return {'items': items, 'saved': saved, 'days': days}

    def done(payload: Dict[str, Any]) -> None:
        if on_done is not None:
            on_done(payload)

    return _spawn(_key('calendar', '', today), work, done)


def home_events(limit: int = 2) -> List[Dict[str, Any]]:
    """首页「事件日历」两行：高重要性优先，无数据回退静态 ✓"""
    today = _dt.date.today().isoformat()
    rows = cache.load_calendar([today], limit=40)
    if not rows:
        return [dict(item) for item in FALLBACK_EVENTS]
    # ★ 首页只放两行 → 按「市场影响」打分挑：
    #   重要性(0~2) ×3 + 有预期值 +2 + 已公布 +1 + 中美 +1 + 有具体时间 +1
    #   （日历里 130 条大多是 00:00 的例行调查项，不能只按时间排 ✗）
    def score(item: Dict[str, Any]) -> int:
        value = int(item.get('importance') or 0) * 3
        if str(item.get('forecast') or '').strip():
            value += 2
        if str(item.get('actual') or '').strip():
            value += 1
        if str(item.get('region') or '') in ('中国', '美国'):
            value += 1
        if str(item.get('time') or '') not in ('', '00:00', '--:--'):
            value += 1
        return value

    rows.sort(key=lambda item: (-score(item), str(item.get('time') or '')))
    out = []
    for row in rows[:max(1, int(limit or 2))]:
        importance = int(row.get('importance') or 0)
        tail = '高' if importance >= 2 else '中'
        out.append({
            'time': str(row.get('time') or ''),
            'text': f"{row.get('region') or ''} {row.get('event') or ''}".strip(),
            'tail': tail,
            'tone': 'amber' if importance >= 2 else 'blue',
        })
    return out


# ---------------------------------------------------------------- 新闻
def news(kind: str = 'flash', symbol: str = '', limit: int = 40,
         query: str = '') -> Dict[str, Any]:
    """读缓存；`query` 非空时只搜索（不联网 ✓）"""
    kind = str(kind or 'flash').lower()
    if query:
        rows = cache.search_news(query, limit=limit)
    else:
        rows = cache.load_news(kind, symbol, limit=limit)
    return {'ok': True, 'kind': kind, 'symbol': symbol,
            'count': len(rows), 'items': rows,
            'query': query,
            'stale': (not query) and (not cache.fresh(
                _key(kind, symbol), kind)),
            'installed': providers.akshare_info()['installed']}


def refresh_news(kind: str = 'flash', symbol: str = '', limit: int = 40,
                 on_done: Optional[Callable[[Dict[str, Any]], None]] = None
                 ) -> bool:
    kind = str(kind or 'flash').lower()

    def work() -> Dict[str, Any]:
        items = providers.fetch_news(kind, symbol, limit)
        saved = cache.save_news(items)
        cache.meta_set(_key(kind, symbol), str(saved))
        return {'items': items, 'saved': saved, 'kind': kind,
                'symbol': symbol}

    return _spawn(_key(kind, symbol), work, on_done)


# ---------------------------------------------------------------- 状态
def status() -> Dict[str, Any]:
    info = providers.akshare_info()
    data = cache.stats()
    return {
        'ok': True,
        'installed': info['installed'],
        'version': info.get('version', ''),
        'error': info.get('error', ''),
        'hint': info.get('hint', ''),
        'last_error': providers.last_error(),
        'cache': data,
        'ttl': dict(cache.TTL),
        'running': [key for key, value in _RUNNING.items() if value],
    }


def clear() -> Dict[str, Any]:
    cache.clear()
    return status()


# ---------------------------------------------------------------- 宏观
def macro(names: Optional[List[str]] = None, limit: int = 12,
          refresh: bool = False,
          on_done: Optional[Callable[[Dict[str, Any]], None]] = None
          ) -> Dict[str, Any]:
    """宏观指标：缓存优先；`refresh=True` 后台抓一次 ✓"""
    key = _key('macro')
    cached = cache.load_snapshot(key).get('payload') or []
    if refresh or not cache.snapshot_fresh(key, 'macro'):
        def work() -> List[Dict[str, Any]]:
            items = providers.fetch_macro(names, limit=limit)
            cache.save_snapshot(key, items)
            return items

        def done(payload: Dict[str, Any]) -> None:
            items = payload.get('result') or []
            if on_done is not None:
                on_done({'ok': bool(items), 'items': items,
                         'error': payload.get('error') or ''})

        _spawn(key, work, done)
    return {'ok': True, 'names': providers.macro_names(),
            'count': len(cached), 'items': cached,
            'stale': not cache.snapshot_fresh(key, 'macro'),
            'installed': providers.akshare_info()['installed']}


# ---------------------------------------------------------------- 标的（期货）
def _snapshot_info(symbol: str, kind: str, builder) -> Dict[str, Any]:
    """通用：整块快照（合约 / 库存 / 基差）+ 失败不抛 ✓"""
    key = _key(kind, symbol)
    row = cache.load_snapshot(key)
    fresh = cache.snapshot_fresh(key, kind)
    if not row.get('payload'):
        try:
            payload = builder()
            cache.save_snapshot(key, payload)
            return payload
        except Exception as error:                            # noqa: BLE001
            return {'error': f'{type(error).__name__}: {error}',
                    'stale': True}
    return {**row['payload'], 'stale': not fresh}


def symbol_info(symbol: str, desk=None) -> Dict[str, Any]:
    """标的资料：期货 = 合约规则 + 库存 + 基差；股票 = 富途快照 + 财务 + 公告 ✓"""
    text = str(symbol or '').strip()
    if not text:
        return {'ok': False, 'error': '需要 symbol'}
    # ★ 股票：富途优先，AkShare 兜底（用户 2026-11-08 ✓）
    if providers.is_stock(text):
        return stock_info(text, desk)
    variety = providers.variety_of(text)
    out: Dict[str, Any] = {
        'ok': True, 'symbol': text, 'variety': variety,
        'exchange': providers.exchange_of(text),
        'installed': providers.akshare_info()['installed'],
    }
    if not providers.akshare_info()['installed']:
        out.update({'ok': False, 'need_install': True,
                    'hint': 'pip install "minibt[news]"（或 pip install akshare）'})
        return out
    out['profile'] = _snapshot_info(
        text, 'profile', lambda: providers.fetch_profile(text))
    if variety:
        out['contract'] = _snapshot_info(
            text, 'contract', lambda: providers.fetch_contract(variety))
        try:
            out['inventory'] = _snapshot_info(
                text, 'inventory', lambda: providers.fetch_inventory(variety))
        except Exception as error:                            # noqa: BLE001
            out['inventory'] = {'error': str(error)}
        out['basis'] = _snapshot_info(
            text, 'basis', lambda: providers.fetch_basis(variety))
    return out


def refresh_symbol(symbol: str,
                   on_done: Optional[Callable[[Dict[str, Any]], None]] = None
                   ) -> bool:
    """强制刷新一个标的的三块数据（合约 / 库存 / 基差）✓"""
    text = str(symbol or '')
    variety = providers.variety_of(text)
    for kind in (('contract', 'inventory', 'basis') if variety else ()):
        cache.save_snapshot(_key(kind, text), None)
    def work() -> Dict[str, Any]:
        return symbol_info(text)
    return _spawn(_key('symbol', text), work,
                  (lambda payload: on_done(payload)) if on_done else None)


# ---------------------------------------------------------------- 股票（P2）
def _stock_piece(desk, symbol: str, kind: str, builder) -> Dict[str, Any]:
    """股票数据块：快照缓存 + 失败降级 ✓"""
    key = _key(kind, symbol)
    row = cache.load_snapshot(key)
    fresh = cache.snapshot_fresh(key, kind)
    if not row.get('payload'):
        try:
            payload = builder()
            if payload:
                cache.save_snapshot(key, payload)
            return payload or {}
        except Exception as error:                            # noqa: BLE001
            return {'error': f'{type(error).__name__}: {error}', 'stale': True}
    return {**row['payload'], 'stale': not fresh}


def stock_info(symbol: str, desk=None) -> Dict[str, Any]:
    """个股资料：**富途优先**（快照 / 资金流），AkShare 兜底（财务 / 公告）。

    用户 2026-11-08：「优先使用富途，没连富途再用 AkShare」✓
    """
    from . import futu_source
    text = str(symbol or '').strip()
    if not text:
        return {'ok': False, 'error': '需要 symbol'}
    out: Dict[str, Any] = {'ok': True, 'symbol': text,
                           'kind': 'stock'}
    futu = futu_source.available(desk)
    out['futu'] = futu
    if futu:
        snap = _stock_piece(
            desk, text, 'profile',
            lambda: futu_source.snapshot(desk, text))
        out['profile'] = {'source': 'futu', 'items': snap.get('items') or [],
                          'name': snap.get('name'),
                          'stale': snap.get('stale')}
        capital = _stock_piece(
            desk, text, 'capital',
            lambda: futu_source.capital_flow(desk, text))
        out['capital'] = capital
    else:
        out['profile'] = _stock_piece(
            desk, text, 'profile', lambda: providers.fetch_profile(text))
        out['profile'].setdefault('source', 'akshare')
        out['profile_note'] = ('富途没连上 → 资料用 AkShare；'
                               '连上富途后会有资金流与实时 PE/PB')
    installed = providers.akshare_info()['installed']
    out['financials'] = (_stock_piece(
        desk, text, 'financials',
        lambda: providers.fetch_stock_financials(text))
        if installed else {'error': '没装 AkShare：pip install minibt[news]'})
    out['notices'] = (_stock_piece(
        desk, text, 'notices', lambda: providers.fetch_notices(text))
        if installed else {'error': '没装 AkShare'})
    return out


# ---------------------------------------------------------------- 标的专属事件
def symbol_events(symbol: str, desk=None,
                  all_events: bool = False) -> Dict[str, Any]:
    """**只跟这个标的有关**的事件（图表圆点用 ✓）

    用户 2026-11-08：宏观日历不再画在 K 线上 —— 只有：
    * 股票：**公告日期**（东财公告，缓存 30min）；
    * 期货：日历里**事件文本带品种名**（如「白银」）的条目。
    """
    text = str(symbol or '').strip()
    if not text:
        return {'ok': False, 'error': '需要 symbol', 'items': []}
    items: List[Dict[str, Any]] = []
    if providers.is_stock(text):
        try:
            notices = symbol_info(text, desk).get('notices') or {}
        except Exception:                                    # noqa: BLE001
            notices = {}
        for row in (notices.get('items') or [])[:20]:
            day = str(row.get('date') or '')[:10]
            title = str(row.get('title') or '').strip()
            if day and title:
                items.append({'day': day, 'time': '',
                              'text': title[:40], 'kind': 'notice'})
    else:
        variety = providers.variety_of(text)
        names = {variety.upper()} if variety else set()
        try:
            snapshot = symbol_info(text, desk)
            contract = snapshot.get('contract') or {}
            first = (contract.get('items') or [{}])[0]
            name = str(first.get('variety') or '').strip()
            if name:
                names.add(name)
        except Exception:                                    # noqa: BLE001
            pass
        day_list = [(__import__('datetime').date.today()
                     + __import__('datetime').timedelta(days=offset)).isoformat()
                    for offset in range(0, 8)]
        for row in cache.load_calendar(day_list, limit=400):
            event = str(row.get('event') or '')
            if not event:
                continue
            if not any(key and key in event for key in names):
                continue
            # ★ 默认只画中/高重要性；`chart_events_all` 打开后全画 ✓
            if not all_events and int(row.get('importance') or 0) < 1:
                continue
            items.append({'day': str(row.get('day') or ''),
                          'time': str(row.get('time') or ''),
                          'text': event[:40], 'kind': 'variety'})
    items.sort(key=lambda row: (row.get('day') or '', row.get('time') or ''))
    return {'ok': True, 'symbol': text, 'count': len(items),
            'items': items[-20:]}


# ---------------------------------------------------------------- 标的资讯（v1.3.7-70）
def symbol_news(symbol: str, name: str = '', variety: str = '',
                kind: str = 'stock', limit: int = 20) -> Dict[str, Any]:
    """单个标的的资讯：专属源 + 全市场关键词匹配（合并去重 ✓）"""
    key = _key('symbolnews', symbol)
    cached = cache.load_snapshot(key).get('payload') or []
    return {'ok': True, 'symbol': symbol, 'count': len(cached),
            'items': cached,
            'stale': not cache.snapshot_fresh(key, 'symbol'),
            'installed': providers.akshare_info()['installed']}


def refresh_symbol_news(symbol: str, name: str = '', variety: str = '',
                        kind: str = 'stock', limit: int = 20,
                        on_done: Optional[Callable[[Dict[str, Any]], None]]
                        = None) -> bool:
    key = _key('symbolnews', symbol)

    def work() -> List[Dict[str, Any]]:
        items = providers.fetch_symbol_news(symbol, name=name,
                                            variety=variety, kind=kind,
                                            limit=limit)
        cache.save_snapshot(key, items)
        return items

    def done(payload: Dict[str, Any]) -> None:
        if on_done is not None:
            on_done({'ok': bool(payload.get('result')),
                     'items': payload.get('result') or [],
                     'error': payload.get('error') or ''})

    return _spawn(key, work, done)
