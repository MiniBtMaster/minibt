"""行情源：期货（tqsdk ``TqApi``）+ 股票（``StockApi`` / 富途 OpenD）统一成一张表。

两边都是"tqsdk 形状"的 api，所以这里只做三件事：

1. **合约清单**：期货 ``query_quotes(ins_class, exchange_id)``；股票走
   :mod:`minibt.desk.stocks`（futu ``get_stock_basicinfo``）；
2. **报价**：``get_quote_list`` / futu 快照，批量（期货返回 live ``Quote``
   引用，股票每次重取 ✓）；
3. **行模型**：统一成 :data:`minibt.desk.symbols.ROW_FIELDS`。
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional

from .symbols import quote_row, row

#: 一次最多拉多少只的报价（股票快照单次上限 ~400，留余量 ✓）
QUOTE_CHUNK = 200

#: 天勤的 `datetime` 是 **UTC 纳秒**，图表要按**东八区**显示 ✓
#: （股票那路 futu 给的 `time_key` 本来就是本地时间，**不能**再偏移 ✗）
TZ_OFFSET_HOURS = int(os.environ.get('MINIBT_DESK_TZ', '8') or 8)
TZ_OFFSET_NS = TZ_OFFSET_HOURS * 3600 * 10 ** 9


#: desk 的类型键 → 天勤 `ins_class`（`query_quotes` 只认右边这些 ✓）
TQ_INS_CLASS = {
    'FUT': 'FUTURE',
    'CONT_MAIN': 'CONT',
    'STOCK': 'STOCK',
    'INDEX': 'INDEX',
    'CONT': 'CONT',
    'OPTION': 'OPTION',
}


def _local_symbols(api) -> Dict[str, Any]:
    """`TqApi` 已经下载好的合约字典（不发请求 ✓）"""
    data = getattr(api, '_data', None)
    if not isinstance(data, dict):
        return {}
    symbols = data.get('symbols')
    return symbols if isinstance(symbols, dict) else {}


def _field_of(item, name: str) -> str:
    value = item.get(name) if isinstance(item, dict) else getattr(
        item, name, None)
    return str(value or '')


def _filter_symbols(symbols: Dict[str, Any], ins_class: str,
                    exchange: str) -> List[str]:
    """按类型 / 交易所筛本地符号（主连 `KQ.m@…` 也算 CONT ✓）"""
    # desk 的 ins_class ↔ tqsdk 的 instrument_class（FUT → FUTURE ✓）
    want_class = {'CONT_MAIN': 'CONT', 'FUT': 'FUTURE'}.get(
        ins_class, ins_class)
    out = []
    for symbol, info in symbols.items():
        symbol = str(symbol or '')
        if not symbol:
            continue
        klass = _field_of(info, 'instrument_class').upper()
        ex = _field_of(info, 'exchange_id').upper()
        expired = info.get('expired') if isinstance(info, dict) else getattr(
            info, 'expired', False)
        if expired:
            continue                       # 已下市 → 不要（订阅会超时 ✗）
        if exchange and ex and ex != exchange.upper():
            continue
        if want_class:
            if want_class == 'CONT':
                if not symbol.startswith('KQ.m@'):
                    continue
            elif klass and klass != want_class.upper():
                continue
        out.append(symbol)
    return out


class BaseFeed:
    """一路行情源（期货 / 股票各一个实例）"""

    kind = 'base'

    def __init__(self, api=None, name: str = ''):
        self.api = api
        self.name = name
        #: 正在查询的合约列表（`SymbolList`，异步填充 ✓）
        self._symbol_lists = {}
        #: 异步合约查询的发起时间（不要 2 秒就把它重置，TqSdk 有些交易所
        #: `query_quotes` 需要几秒才回来 ✓）
        self._symbol_started: Dict[Any, float] = {}
        self._names: Dict[str, str] = {}
        #: 通过 `query_quotes` / 本地 symbols 确认存在的合约 ✓
        self._known_symbols: set = set()
        self._bad_symbols: set = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------ 清单
    def available(self) -> bool:
        return self.api is not None

    def valid_symbol(self, symbol: str) -> bool:
        """合约是否值得订阅（默认都行；期货按本地符号字典过滤 ✓）"""
        return True

    def _fast_call(self, fn, *args, **kwargs):
        """调用 TqSdk 时**禁止内部 wait_update 等网络**（防主线程卡死）

        TqSdk 的 `get_quote_list` / `get_kline_serial` 在首次/断线时会内部
        `wait_update` 最多 25~30 秒（用户实测断线后整个报价窗口冻住 ✗）。
        这里临时把 `api.wait_update` 换成立即返回 False：
        调用会马上抛超时 / 返回空，任务仍在，下一次 `pump()` 继续填充；
        界面保持流畅，最多暂时没有新报价 / K 线。
        """
        api = self.api
        if api is None:
            return None
        wait = getattr(api, 'wait_update', None)
        loop = getattr(api, '_loop', None)
        old_running = getattr(loop, 'is_running', None) if loop else None

        def _no_wait(*_a, **_k):
            return False

        def _running():
            return True

        try:
            # ★ 关键：TqSdk 的 `get_quote_list` 在 `loop.is_running()` 为
            #   False 时会 `while not task.done(): wait_update()`。以前只把
            #   wait_update 换成 False → 立刻 TqTimeoutError，返回空表，
            #   首页 / 报价永远没有价格 ✗。
            #   这里让它**以为 loop 正在跑** → 直接返回 QuoteList / DataFrame，
            #   真实的订阅任务交给下一拍 `pump()` 继续填充 ✓。
            if loop is not None and callable(old_running):
                loop.is_running = _running
            if callable(wait):
                api.wait_update = _no_wait
            return fn(*args, **kwargs)
        finally:
            if loop is not None and callable(old_running):
                loop.is_running = old_running
            if callable(wait):
                api.wait_update = wait

    def _fast_query(self, api) -> None:
        """把 `api._get_symbol_list` 换成**不等待**的版本 ✓

        tqsdk 原版：`if not self._loop.is_running(): while not done: wait_update()`
        → 主线程最多阻塞 **30 秒**（实盘实测：查询迟迟不回 → 整个终端卡死 ✗）。
        它返回的本来就是个 `SymbolList`（list 子类，任务异步填充）——
        我们只要**不等待**，让它随 `pump()` 慢慢填，几拍之后就能读到 ✓。
        全程在**主线程**（tqsdk 只支持单线程），不碰后台线程 ✗。
        """
        if getattr(api, '_desk_fast_lists', False):
            return
        try:
            from tqsdk.objs_not_entity import SymbolList
            from tqsdk.utils import _generate_uuid
        except Exception:                                        # noqa: BLE001
            return

        def fast(query: str, filter_=None, **kwargs):
            # ★ TqSdk 是以关键字 `filter=...` 调 `_get_symbol_list` 的；
            #   以前参数名写成 `filter_`，这里会 TypeError，导致所有
            #   query_quotes/query_cont_quotes 直接返回 None（DCE 永远空表 ✗）。
            actual = filter_ if filter_ is not None else kwargs.get('filter')
            return SymbolList(api, query_id=_generate_uuid("PYSDK_api"),
                              query=query, filter=actual)

        try:
            api._get_symbol_list = fast
            api._desk_fast_lists = True
        except Exception:                                        # noqa: BLE001
            pass

    def start_symbols(self, ins_class: str, exchange: str):
        """发起一次**异步**合约查询（几拍后 `poll_symbols()` 取结果 ✓）"""
        api = self.api
        if api is None:
            return None
        self._fast_query(api)
        key = (ins_class, exchange)
        try:
            pending = self._symbol_lists.get((ins_class, exchange))
            if pending is not None:
                # 已有异步查询在跑 → 先把当前读到的给出去（可能是空 ✓）
                return list(pending or [])
            if ins_class == 'CONT_MAIN':
                result = api.query_cont_quotes(exchange)
            elif ins_class == 'OPTION':
                return None
            else:
                result = api.query_quotes(
                    TQ_INS_CLASS.get(ins_class, ins_class), exchange,
                    expired=False)
        except Exception:                                        # noqa: BLE001
            return None
        self._symbol_lists[key] = result
        self._symbol_started[key] = __import__('time').monotonic()
        return result

    def reset_symbols(self, ins_class: str = '',
                      exchange: str = '', force: bool = False) -> None:
        """清掉某次异步查询；默认至少保留 180 秒（天勤全量查询可能很慢）✓

        DCE / CZCE 的 `query_quotes` 在 miniqt 实测要 1~2 分钟才回；
        自动重试不能把还在跑的查询重置掉。只有用户手动刷新才 force=True。
        """
        import time as _time
        if ins_class:
            key = (ins_class, exchange)
            started = float(self._symbol_started.get(key) or 0.0)
            if (not force and started
                    and _time.monotonic() - started < 180.0):
                return
            self._symbol_lists.pop(key, None)
            self._symbol_started.pop(key, None)
        else:
            self._symbol_lists.clear()
            self._symbol_started.clear()

    def poll_symbols(self):
        """已就绪的合约列表（`{}` = 还没有 ✓）"""
        out = {}
        for key, result in list(self._symbol_lists.items()):
            try:
                symbols = list(result or [])
            except Exception:                                    # noqa: BLE001
                continue
            if not symbols:
                continue
            out[key] = symbols
            self._symbol_lists.pop(key, None)
        return out

    def contracts(self, ins_class: str, exchange: str) -> List[str]:
        """该类型/交易所下的合约代码（子类实现）"""
        return []

    def contracts_local(self, ins_class: str,
                        exchange: str) -> List[str]:
        """**只读本地缓存**的合约（不会触发网络请求；没有就返回空 ✓）"""
        return []

    def stock_rows(self, market: str) -> List[dict]:
        """股票/期权元数据行（没有该市场 → 空）"""
        return []

    # ------------------------------------------------------------ 报价
    #: 用 `get_quote_list` 批量取（期货默认**不用**：实盘里批量接口偶尔
    #: 会卡 30 秒 → 改成逐个 `get_quote`，和 trade.py / 官方示例一致 ✓）
    use_quote_list = False

    def drop_symbol(self, symbol: str) -> None:
        """TqSdk 服务端报“不存在”时，把它从订阅里移除（避免每拍都报错 ✓）"""
        symbol = str(symbol or '')
        if not symbol:
            return
        self._known_symbols.discard(symbol)
        self._bad_symbols.add(symbol)
        api = self.api
        requests = getattr(api, '_requests', None)
        if isinstance(requests, dict):
            quotes = requests.get('quotes')
            if isinstance(quotes, set):
                for item in list(quotes):
                    if str(item) == symbol or str(item).endswith('.' + symbol):
                        quotes.discard(item)
                try:
                    api._send_pack({
                        'aid': 'subscribe_quote',
                        'ins_list': ','.join(sorted(quotes)),
                    })
                except Exception:                            # noqa: BLE001
                    pass
        data = getattr(api, '_data', None)
        if isinstance(data, dict):
            quotes = data.get('quotes')
            if isinstance(quotes, dict):
                # 连带移除“主连 KQ.m@… → 这个标的”的订阅；否则主连
                # 仍会继续请求不存在的标的（rb2701）✗
                bad_keys = []
                for item, quote in list(quotes.items()):
                    underlying = str(getattr(quote, 'underlying_symbol', '') or '')
                    if (str(item) == symbol
                            or str(item).endswith('.' + symbol)
                            or underlying == symbol
                            or underlying.endswith('.' + symbol)):
                        bad_keys.append(str(item))
                for item in bad_keys:
                    quotes.pop(item, None)
                    if isinstance(requests, dict):
                        req = requests.get('quotes')
                        if isinstance(req, set):
                            req.discard(item)
        if isinstance(requests, dict):
            req = requests.get('quotes')
            if isinstance(req, set):
                try:
                    api._send_pack({
                        'aid': 'subscribe_quote',
                        'ins_list': ','.join(sorted(req)),
                    })
                except Exception:                            # noqa: BLE001
                    pass

    def quotes(self, symbols: List[str]) -> List[dict]:
        """批量报价（顺序与 ``symbols`` 对齐；取不到的跳过 ✓）

        ★ 默认**逐个** `get_quote`：
          * 官方推荐用法（trade.py / miniqt 都这么用）✓
          * 实盘里 `get_quote_list` 在某些时序下会**卡 30 秒** ✗
          * 第二次之后 tqsdk 直接返回缓存的 Quote 实体，几乎零成本 ✓
        """
        api = self.api
        if api is None or not symbols:
            return []
        # ★ 天勤遇到不存在的合约（旧 tab 里的 `ag2701` 之类）会让
        #   `wait_update` 抛 GraphQL 错误 → 报价泵一直异常；先按本地
        #   symbols 过滤掉（只在 symbols 已下载后生效，刚登录不拦 ✓）。
        symbols = [symbol for symbol in symbols
                   if self.valid_symbol(str(symbol))]
        if not symbols:
            return []
        out: List[dict] = []
        if self.use_quote_list:
            for start in range(0, len(symbols), QUOTE_CHUNK):
                chunk = symbols[start:start + QUOTE_CHUNK]
                try:
                    items = self._fast_call(api.get_quote_list, chunk)
                except Exception:                                # noqa: BLE001
                    items = []
                for symbol, quote in zip(chunk, items or []):
                    if quote is not None:
                        out.append(self.row_of(symbol, quote))
            return out
        for symbol in symbols:
            try:
                quote = self._fast_call(api.get_quote, symbol)
            except Exception:                                    # noqa: BLE001
                continue
            if quote is None:
                continue
            out.append(self.row_of(symbol, quote))
        return out

    def spec(self, symbol: str):
        """单个合约的 ``get_quote``（图表用；期货是 live 引用 ✓）"""
        api = self.api
        if api is None or not self.valid_symbol(str(symbol)):
            return None
        try:
            return self._fast_call(api.get_quote, symbol)
        except Exception:                                        # noqa: BLE001
            return None

    def klines(self, symbol: str, cycle: int, length: int = 500):
        """K 线 DataFrame（期货 ``get_kline_serial`` / 股票同形 ✓）

        ⚠ 天勤的 `datetime` 是 **UTC 纳秒** → 这里加 ``TZ_OFFSET_HOURS``（默认 8），
        否则图表 X 轴比实际行情**少 8 小时**（用户实测 ✗）
        """
        api = self.api
        if api is None or not self.valid_symbol(str(symbol)):
            return None
        try:
            frame = self._fast_call(
                api.get_kline_serial, symbol, int(cycle), int(length))
        except Exception:                                        # noqa: BLE001
            return None
        # ★ 期货 UTC 要 +8；股票 Futu `time_key` 已是本地时间 → 必须 0
        #   以前这里用默认 +8，股票 09:30 会显示成 17:30 ✗
        return shift_timezone(frame, offset_hours=self.time_shift_hours)

    def close(self) -> None:
        """关掉行情源（tqsdk / futu 的 api 都要 `close()` ✓）

        不关的话进程退出时 asyncio 任务还挂着，会刷一屏
        `Task was destroyed but it is pending!` / `Event loop is closed`（用户实测 ✗）
        """
        api = self.api
        self.api = None
        if api is None:
            return
        closer = getattr(api, 'close', None)
        if not callable(closer):
            return
        try:
            closer()
        except Exception as error:                               # noqa: BLE001
            text = str(error)
            # tqsdk：`不能在协程中调用 close` → 先让 wait_update 返回再关 ✓
            # ★ 关窗口时 TargetPosTask / InsertOrderTask 还没跑完是**正常**的
            #   （天勤内部 task 随 api 一起销毁）→ 不打一屏红字 ✗
            if ('InsertOrderTask' in text or 'TargetPosTask' in text
                    or '执行超时' in text):
                return
            if '协程' in text or 'coroutine' in text.lower():
                try:
                    wait = getattr(api, 'wait_update', None)
                    if callable(wait):
                        import time as _time
                        wait(deadline=_time.time() + 0.05)
                    closer()
                    return
                except Exception:                                # noqa: BLE001
                    pass
            print(f'[desk] 关闭行情源失败（{self.kind}）：{error!r}', flush=True)

    def name_of(self, symbol: str) -> str:
        with self._lock:
            return self._names.get(symbol, '')

    def remember(self, mapping: Dict[str, str]) -> None:
        with self._lock:
            self._names.update({str(k): str(v or '') for k, v in mapping.items()})

    #: 报价里的 `datetime` 要不要按东八区平移（期货 = UTC，股票已经是本地 ✓）
    time_shift_hours = 0

    #: **报价行**的 `quote_time` 要不要平移 —— 天勤 ``Quote.datetime``
    #: 本来就是**北京时间**（tqsdk 文档原文），只有 K 线是 UTC 纳秒；
    #: 以前报价也 +8 → 「行情更新时间」比实际晚 8 小时（用户看到
    #: 18:42 显示成 02:42，以为只有隔夜缓存 ✗）。所以这里固定 0 ✓
    quote_shift_hours = 0

    def row_of(self, symbol: str, quote) -> dict:
        # ★ 天勤报价自带 `instrument_name` → 不用再发 `query_symbol_info` ✓
        #   （那个接口会把 ins_query 通道搞乱，实盘里导致后续查询 30 秒超时 ✗）
        name = self.name_of(symbol) or str(
            getattr(quote, 'instrument_name', '') or '')
        if name and not self.name_of(symbol):
            self.remember({symbol: name})
        return quote_row(symbol, name, quote,
                         shift_hours=self.quote_shift_hours)


class FuturesFeed(BaseFeed):
    """期货：天勤 ``TqApi``（模拟盘 / 实盘）"""

    kind = 'futures'
    #: 天勤 `datetime` 是 UTC → 行情更新时间显示要 +8 ✓
    time_shift_hours = TZ_OFFSET_HOURS

    def valid_symbol(self, symbol: str) -> bool:
        """过滤已下市 / 根本不存在的合约（`ag2701` 会让 TqSdk 查询报错 ✓）

        本地 symbols / 已查到的合约清单都还没有时返回 True（登录刚开始
        不拦合法新合约）；主连 `KQ.` 单独放行（本地字典里不一定有）。
        """
        symbol = str(symbol or '')
        if not symbol:
            return True
        # ★ 只有行情泵明确报过“不存在”的合约才拉黑；
        #   不能拿 `_data['symbols']` 做白名单：它可能只包含本次 query
        #   的部分结果，会把缓存里的合法合约全部挡掉 → 有行但价格不更新 ✗。
        bad = getattr(self, '_bad_symbols', set())
        return not (symbol in bad or any(symbol.endswith('.' + str(item))
                                         for item in bad))

    def contracts(self, ins_class: str, exchange: str) -> List[str]:
        """合约清单（**优先本地**，不触发网络请求 ✓）

        ⚠ 实盘里 `query_quotes` / `query_cont_quotes` 会向后端发请求并
        **阻塞到 30 秒超时**（没权限 / 连接异常时）→ 以前整窗卡死 ✗。
        现在先读 `TqApi` **已经下载好的**合约字典（`api._data['symbols']`，
        `query_quotes` 内部也是从这里筛的），拿不到才退回官方接口。
        """
        api = self.api
        if api is None:
            return []
        symbols = _local_symbols(api)
        if symbols:
            rows = _filter_symbols(symbols, ins_class, exchange)
            if rows:
                self._known_symbols.update(rows)
                return rows
            # 本地字典里没有这个分类（例如本地只有 FUTURE、没有主连）
            # → 继续走异步 query_cont_quotes ✓
        try:
            # ★ 用 `start_symbols` 缓存**同一个** `SymbolList`：
            #   TqSdk 的 query 是异步的，第一次 `list(...)` 必然为空；
            #   如果每次都新建查询，下一拍还是空 → DCE/CZCE 永远 0 行 ✗。
            #   缓存后下一拍 pump 把它填满，2 秒重试就能读到 ✓。
            rows = self.start_symbols(ins_class, exchange)
            if rows is None:
                return []                    # OPTION 懒加载 ✓
            rows = list(rows or [])
            if rows:
                self._known_symbols.update(str(item) for item in rows)
            return rows
        except Exception:                                        # noqa: BLE001
            return []

    def contracts_local(self, ins_class: str,
                        exchange: str) -> List[str]:
        """本地符号字典里筛（`TqApi` 启动时就下载好了）✓"""
        symbols = _local_symbols(self.api)
        if not symbols:
            return []
        rows = _filter_symbols(symbols, ins_class, exchange)
        if rows:
            self._known_symbols.update(rows)
        return rows

    def fill_names(self, symbols: List[str]) -> None:
        """``query_symbol_info`` 补名称（合约清单一次就够 ✓）"""
        api = self.api
        if api is None or not symbols:
            return
        try:
            frame = api.query_symbol_info(symbols)
        except Exception:                                        # noqa: BLE001
            return
        mapping = {}
        try:
            for item in frame.to_dict('records'):
                mapping[str(item.get('instrument_id') or '')] = str(
                    item.get('instrument_name') or '')
        except Exception:                                        # noqa: BLE001
            return
        mapping.pop('', None)
        self.remember(mapping)


class StockFeed(BaseFeed):
    """股票：``StockApi``（富途 OpenD；``sim_account`` 决定本地模拟盘账本 ✓）"""

    kind = 'stocks'

    def stock_rows(self, market: str) -> List[dict]:
        """股票清单（A 股 / 港股 / 美股；只给代码 + 名称，报价另取 ✓）"""
        from . import stocks as _stocks
        rows = _stocks.basic_rows(self.api, market)
        for item in rows:
            self.remember({item['symbol']: item.get('name') or ''})
        return [row(symbol=item['symbol'], name=item.get('name') or '')
                for item in rows]

    @staticmethod
    def _only_stocks(symbols):
        """股票源只接股票代码（`DCE.PP2701` 这类必须交给天勤 ✓）"""
        out = []
        for symbol in symbols or []:
            head = str(symbol or '').split('.')[0].upper()
            if head in ('SSE', 'SZSE', 'SH', 'SZ', 'HK', 'US', 'BSE'):
                out.append(symbol)
        return out

    def klines(self, symbol: str, cycle: int, length: int = 500):
        """非股票代码直接返回 None（**绝不**喂给富途 ✗）"""
        if not self._only_stocks([symbol]):
            return None
        return super().klines(symbol, cycle, length)

    def quotes(self, symbols: List[str]) -> List[dict]:
        """股票必须**每次重取快照**（不像期货是 live 引用 ✓）"""
        from . import stocks as _stocks
        symbols = self._only_stocks(symbols)
        items = _stocks.quotes(self.api, symbols)
        out = []
        for symbol, quote in zip(symbols, items or []):
            if quote is not None:
                out.append(self.row_of(symbol, quote))
        return out


def offline_rows(count: int = 60) -> List[dict]:
    """离线演示数据（不连网也能看 UI ✓）"""
    rows = []
    for index in range(count):
        base = 3600.0 + index * 7.5
        rows.append(row(
            symbol=f'SHFE.demo{index:02d}', name=f'演示{index:02d}',
            last=base, bid_price1=base - 1, bid_volume1=3 + index % 5,
            ask_price1=base + 1, ask_volume1=2 + index % 4,
            upper_limit=base * 1.1, lower_limit=base * 0.9,
            chg=index - count / 2, chg_pct=(index - count / 2) / 10.0,
            volume=10000 + index * 137, open=base - 3, high=base + 12,
            low=base - 9, pre_close=base - 5, pre_settlement=base - 4,
            quote_time='09:31:00', price_tick=0.5,
        ))
    return rows


def pick_feed(feeds: List[BaseFeed], symbol: str) -> Optional[BaseFeed]:
    """按代码前缀选行情源（``SHFE.`` → 期货，``SH.``/``HK.``/``US.`` → 股票 ✓）"""
    for feed in feeds:
        if not feed.available():
            continue
        if feed.kind == 'stocks' and _looks_stock(symbol):
            return feed
        if feed.kind == 'futures' and not _looks_stock(symbol):
            return feed
    for feed in feeds:
        if feed.available():
            return feed
    return None


#: 股票市场前缀（desk 里股票统一写成 `SSE.` / `SZSE.` / `HK.` / `US.` ✓；
#: 早期还有 `SH.` / `SZ.` 的写法，一起认）
STOCK_MARKETS = ('SSE', 'SZSE', 'BSE', 'SH', 'SZ', 'HK', 'US')


def _looks_stock(symbol: str) -> bool:
    """`SSE.600000` / `HK.00700` / `US.AAPL` → 股票 ✓

    ⚠ 以前只认 `SH/SZ/HK/US`，而 desk 的股票代码前缀是 **`SSE.` / `SZSE.`** ——
    于是股票单被路由到**天勤**（期货）接口下单（用户实测：股票成交跑到期货 ✗）
    """
    head = str(symbol or '').split('.')[0].upper()
    return head in STOCK_MARKETS

def shift_timezone(frame, offset_hours: int = None):
    """把 ``datetime``（纳秒 UTC）平移成**东八区**（原地 copy，失败则原样返回 ✓）"""
    if frame is None or not hasattr(frame, 'columns'):
        return frame
    if 'datetime' not in getattr(frame, 'columns', ()):
        return frame
    hours = TZ_OFFSET_HOURS if offset_hours is None else int(offset_hours)
    if not hours:
        return frame
    try:
        import pandas as pd

        out = frame.copy()
        out['datetime'] = pd.to_numeric(out['datetime'], errors='coerce')             + hours * 3600 * 10 ** 9
        return out
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] 时区平移失败（保持原样）: {error!r}')
        return frame
