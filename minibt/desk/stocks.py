"""富途（OpenD）行情适配：股票清单 / 快照报价。

只做**行情**（元数据 + 报价），K 线与下单仍走 :class:`minibt.StockApi`。
``futu`` 是惰性导入的（没装/没启动 OpenD 时只影响股票页 ✓）。
"""
from __future__ import annotations

from types import SimpleNamespace
import os
import time
from typing import Dict, List

#: 表格里的交易所键 → futu Market 名
MARKET_NAMES = {'SSE': 'SH', 'SZSE': 'SZ', 'HK': 'HK', 'US': 'US'}
FUTU_MARKETS = {'SSE': 'SH', 'SZSE': 'SZ'}

#: 美股只保留这三个交易所（去掉 OTC/粉色单 ✓，同 miniqt）
US_EXCHANGE_TYPES = ('US_NASDAQ', 'US_NYSE', 'US_AMEX')


def to_futu_code(symbol: str) -> str:
    """``SSE.600000`` → ``SH.600000``；``HK.00700`` / ``US.AAPL`` 原样 ✓"""
    text = str(symbol or '').strip().upper()
    if '.' not in text:
        return ''
    head, tail = text.split('.', 1)
    if head in ('SSE', 'SH'):
        return f'SH.{tail}'
    if head in ('SZSE', 'SZ'):
        return f'SZ.{tail}'
    if head in ('HK', 'US'):
        return f'{head}.{tail}'
    return ''


def from_futu_code(code: str) -> str:
    """``SH.600000`` → ``SSE.600000``（统一成天勤 A 股写法 ✓）"""
    text = str(code or '').strip().upper()
    if '.' not in text:
        return ''
    head, tail = text.split('.', 1)
    return {'SH': 'SSE', 'SZ': 'SZSE'}.get(head, head) + '.' + tail


def display_symbol(symbol: str) -> str:
    """统一成天勤写法：``SH.600000`` → ``SSE.600000``（HK/US 原样 ✓）

    富途返回的持仓/委托/成交里都是 ``SH.``/``SZ.``，而报价表和图都用
    ``SSE.``/``SZSE.`` —— 不统一的话同一只票会出现两种代码 ✗
    """
    text = str(symbol or '').strip()
    if not text:
        return ''
    head = text.split('.', 1)[0]
    if head.upper() in ('SH', 'SZ'):
        return from_futu_code(text.upper())      # SH.600000 → SSE.600000 ✓
    return text          # 期货（SHFE.rb2610）大小写敏感，别动 ✓


def market_of(symbol: str) -> str:
    head = str(symbol or '').split('.')[0].upper()
    return {'SH': 'SSE', 'SSE': 'SSE', 'SZ': 'SZSE', 'SZSE': 'SZSE',
            'HK': 'HK', 'US': 'US'}.get(head, '')


def ensure_futu():
    """导入 futu 前先处理 protobuf 老版本（仓库里附带 futu 10.02 ✓）

    与 `minibt/stock_api.py` 同一套处理：protobuf >= 3.21 时用纯 Python 实现，
    否则 `Descriptors cannot be created directly` ✗
    """
    import os
    if not os.environ.get('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'):
        try:
            import importlib.metadata as _metadata
            parts = [int(item) for item in
                     _metadata.version('protobuf').split('.')[:2]]
            if parts and (parts[0] > 3 or (parts[0] == 3 and parts[1] >= 21)):
                os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'
        except Exception:                                        # noqa: BLE001
            pass
    import futu
    return futu


def _ctx(api):
    """拿 ``OpenQuoteContext``（``StockApi`` 内部那个 ✓）"""
    return getattr(api, '_ctx', None) if api is not None else None


def _ret_ok(api) -> int:
    return int(getattr(api, '_RET_OK', 0))


#: 最近一次清单失败的原因（给 UI 提示用 ✓）
last_error = ''

#: 最近一次 futu 的返回值（`ret`）——诊断用 ✓
last_ret = None


def basic_rows(api, market: str) -> List[dict]:
    """股票清单（``[{symbol, name}]``）；拿不到 → ``[]`` ✓"""
    ctx = _ctx(api)
    if ctx is None or market not in MARKET_NAMES:
        return []
    try:
        futu = ensure_futu()
    except ImportError:                                          # pragma: no cover
        return []
    futu_market = getattr(futu.Market, MARKET_NAMES[market], None)
    if futu_market is None:
        return []
    global last_error, last_ret
    try:
        ret, frame = ctx.get_stock_basicinfo(futu_market,
                                             futu.SecurityType.STOCK)
        last_ret = ret
    except Exception as error:                                   # noqa: BLE001
        last_error = f'get_stock_basicinfo 异常：{error!r}'
        print(f'[desk] 股票清单失败（{market}）：{last_error}')
        return []
    if ret != _ret_ok(api):
        last_error = f'get_stock_basicinfo 返回 ret={ret}：{frame}'
        print(f'[desk] 股票清单失败（{market}）：{last_error}')
        return []
    if frame is None or getattr(frame, 'empty', True):
        last_error = f'get_stock_basicinfo 返回空表（{market}）'
        print(f'[desk] 股票清单为空（{market}）')
        return []
    out = []
    for item in frame.to_dict('records'):
        code = str(item.get('code') or '')
        name = str(item.get('name') or '')
        if not code or 'delisting' in str(item.get('stock_type') or '').lower():
            continue
        if market == 'US':
            if str(item.get('exchange_type') or '') not in US_EXCHANGE_TYPES:
                continue
        symbol = from_futu_code(code)
        if not symbol:
            continue
        # 只留本市场的（防 futu 版本/参数差异把别的市场也返回 ✓）
        prefix = 'SSE.' if market == 'SSE' else ('SZSE.' if market == 'SZSE'
                                                else '')
        if prefix and not symbol.startswith(prefix):
            continue
        out.append({'symbol': symbol, 'name': name})
    return out


def snapshot_to_quote(symbol: str, row) -> SimpleNamespace:
    """futu 快照行 → **天勤 Quote 形状**（字段名与 `symbols.quote_row` 对齐 ✓）"""
    def num(key):
        try:
            value = row.get(key)
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    pre_close = num('prev_close_price') or num('last_close')
    return SimpleNamespace(
        symbol=symbol,
        name=str(row.get('name') or ''),
        last_price=num('last_price'),
        bid_price1=num('bid_price'), ask_price1=num('ask_price'),
        bid_volume1=num('bid_vol'), ask_volume1=num('ask_vol'),
        upper_limit=num('upper_limit'), lower_limit=num('lower_limit'),
        volume=num('volume'), open=num('open_price'),
        highest=num('high_price'), lowest=num('low_price'),
        pre_close=pre_close, pre_settlement=pre_close,
        price_tick=num('price_spread') or 0.001,
        datetime=str(row.get('update_time') or '')[-8:],
    )


def quotes(api, symbols: List[str]) -> List[object]:
    """批量快照（单次 ≤400 只；取不到的项为 ``None`` ✓）"""
    ctx = _ctx(api)
    if ctx is None or not symbols:
        return [None] * len(symbols)
    pairs = [(symbol, to_futu_code(symbol)) for symbol in symbols]
    codes = [code for _, code in pairs if code]
    if not codes:
        return [None] * len(symbols)
    try:
        ret, frame = ctx.get_market_snapshot(codes)
    except Exception:                                            # noqa: BLE001
        return [None] * len(symbols)
    if ret != _ret_ok(api) or frame is None or frame.empty:
        return [None] * len(symbols)
    by_code: Dict[str, object] = {str(item.get('code')): item
                                  for item in frame.to_dict('records')}
    out = []
    for symbol, code in pairs:
        row = by_code.get(code)
        out.append(snapshot_to_quote(symbol, row) if row is not None else None)
    return out


def probe(api, market: str) -> dict:
    """单个市场的诊断（`--check` 用 ✓）

    Returns:
        ``{'market', 'count', 'ret', 'error'}``
    """
    global last_error
    before = last_error
    last_error = ''
    try:
        rows = basic_rows(api, market)
    except Exception as error:                                   # noqa: BLE001
        rows = []
        last_error = f'{error!r}'
    result = {'market': market, 'count': len(rows),
              'ret': last_ret, 'error': last_error or '',
              'example': (rows[0]['symbol'] if rows else '')}
    if not result['error']:
        last_error = before
    return result


def connection_info(api) -> str:
    """futu 连接信息（版本 / 网关地址 ✓）"""
    info = []
    try:
        import importlib.metadata as _metadata
        info.append('futu-api ' + _metadata.version('futu-api'))
    except Exception:                                            # noqa: BLE001
        info.append('futu-api ?')
    host = getattr(api, '_host', '') or getattr(api, 'host', '')
    port = getattr(api, '_port', '') or getattr(api, 'port', '')
    if host or port:
        info.append(f'{host or "127.0.0.1"}:{port or 11111}')
    return ' / '.join(info)


# --------------------------------------------------------------- 订阅池
class SubscriptionPool:
    """股票**全局订阅池**（miniqt 同款思路 ✓）

    * `pool`   ：全局股票池（进池即订阅）；
    * `visible`：报价页当前**可见**的股票（换屏时增减）；
    * `charts` ：正在画图的股票（**永不被可见范围挤掉** ✓）。

    规则：任何一个来源需要 → 订阅；都不需要 → 退订。
    这样报价页滚来滚去不会把图表正在用的股票退掉 ✗
    """

    #: 富途正股**订阅额度上限 = 100**（超出会报
    #: 「订阅额度不足（已用正股额度：100/100）」✗）→ 池子必须卡在这里 ✓
    LIMIT = 100

    def __init__(self, api=None, limit: int = 0) -> None:
        self.api = api
        self.limit = int(limit or self.LIMIT)
        self.owners: Dict[str, set] = {'pool': set(), 'visible': set()}
        self.charts: set = set()
        self.subscribed: set = set()

    # ------------------------------------------------------------- 口子
    def _wanted(self) -> set:
        wanted = set(self.charts)
        for codes in self.owners.values():
            wanted |= set(codes)
        return wanted

    def set_owner(self, name: str, codes) -> None:
        """设置某个来源需要的代码集合（`pool` / `visible` ✓）"""
        self.owners[str(name or 'pool')] = {
            str(code or '').upper() for code in (codes or []) if code}
        self.sync()

    def set_charts(self, codes) -> None:
        self.charts = {str(code or '').upper() for code in (codes or [])
                       if code}
        self.sync()

    def sync(self) -> None:
        """按需订阅 / 退订（**带 1 分钟宽限期 + 容量上限** ✓）

        ⚠ 富途限制：K 线订阅**不足 1 分钟不能退订**，否则报
          `订阅时间过短，至少需要订阅1分钟`（用户实测 ✗）。
        所以不能"滚出屏幕立刻退"：

        * 池子容量 `capacity`（默认 80，留 20 个余量给图表/分笔）；
        * 滚出可见范围的代码先进**宽限期**（65 秒），到期才退；
        * 只有"要订阅却超容量"时才提前退最久没露面的（LRU）；
        * 宽限期内回来 → 继续沿用，不重复订阅（省额度也避免抖动）✓
        """

        wanted = self._wanted()
        now = time.monotonic()
        seen = self.__dict__.setdefault('_seen', {})
        for code in wanted:
            seen[code] = now
        subscribe = getattr(self.api, 'subscribe_quote', None)
        unsubscribe = getattr(self.api, 'unsubscribe_all', None)             or getattr(self.api, 'unsubscribe_quote', None)

        def _release(code: str) -> None:
            if callable(unsubscribe):
                if getattr(unsubscribe, '__name__', '') == 'unsubscribe_quote':
                    unsubscribe(code, 60)
                else:
                    unsubscribe(code)
            self.subscribed.discard(code)

        # ① 超容量 → 先退"最久没露面"的（LRU，可能还没到宽限期）
        capacity = int(getattr(self, 'capacity', 0) or 0) or             max(20, self.limit - 20)
        idle = sorted((self.subscribed - wanted),
                      key=lambda code: seen.get(code, 0))
        while len(self.subscribed) > capacity and idle:
            _release(idle.pop(0))

        # ② 宽限期到期 → 退订（≥65 秒，富途才允许）
        for code in list(self.subscribed - wanted):
            if now - float(seen.get(code) or 0) > 65.0:
                _release(code)

        # ③ 订阅新进入可见范围的（先确认容量）
        for code in sorted(wanted - self.subscribed):
            if len(self.subscribed) >= capacity:
                break
            if callable(subscribe):
                subscribe(code, 60)
            subs = getattr(self.api, '_subs', None)
            if isinstance(subs, set) and (code, 'K_1M') not in subs:
                continue          # 额度不足 / 失败 → 不记账 ✓
            self.subscribed.add(code)

        # ④ 诊断（**已注释**：排查订阅问题时再打开 ✓）
        # try:
        #     truth = getattr(self.api, '_subs', None)
        #     stats = (len(wanted), len(self.subscribed),
        #              len(truth) if isinstance(truth, set) else -1,
        #              tuple(sorted(wanted))[:4])
        #     if stats != getattr(self, '_last_stats', None):
        #         self._last_stats = stats
        #         print(f'[pool] 需要 {stats[0]} | 已订 {stats[1]} | '
        #               f'富途真实 {stats[2]} | 样本 {stats[3]}', flush=True)
        # except Exception:                                      # noqa: BLE001
        #     pass
