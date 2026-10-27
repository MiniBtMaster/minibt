"""desk 的交易执行：限价下单 / 平 / 反 / 全 / 撤单。

* 期货：``tqsdk`` 的 ``api.insert_order`` + ``TargetPosTask``（多账户带 account=）
* 股票：``StockApi`` 同形接口（默认本地模拟盘；``trade=True`` 才是真实交易）

安全：只有 ``Desk(allow_trading=True)`` 且拿到 api 才会真的下单；
实盘账户（有 ``broker_id``）由前端**二次确认**，且所有动作都写进运行日志 ✓。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .stocks import display_symbol

#: 方向/开平映射（前端只发 buy/sell/close ✓）
SIDE_MAP = {
    'buy': ('BUY', 'OPEN'),
    'sell': ('SELL', 'OPEN'),
    'close': ('CLOSE', 'CLOSE'),
}


def _tradeable(symbol: str) -> bool:
    """主连 / 指数不能交易（`KQ.m@…` / `KQ.i@…`）✓"""
    try:
        from .symbols import is_tradeable
        return is_tradeable(symbol)
    except Exception:                                            # noqa: BLE001
        text = str(symbol or '')
        return bool(text) and not text.upper().startswith('KQ.')


def _num(value) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _field(item, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _field_any(item, names, default=None):
    for name in names:
        value = _field(item, name)
        if value is not None:
            return value
    return default


#: 记录列表统一走 `accounts.record_rows`（含 **tqsdk Entity** 的特殊处理 ✓）
from .accounts import position_symbol, record_rows as _records  # noqa: E402

#: 天勤 Position 的多空字段别名（新老版本不一样 ✓）
LONG_VOLUME = ('pos_long', 'volume_long')
SHORT_VOLUME = ('pos_short', 'volume_short')


def _unit(symbol: str) -> str:
    """期货「手」/ 股票「股」——日志和 UI 不要混 ✓"""
    return ('股' if str(symbol or '').upper().startswith(
        ('SH.', 'SZ.', 'HK.', 'US.', 'JP.')) else '手')


def _trade_failed(text: str) -> bool:
    """交易返回值是不是失败提示（统一给 app 的 toast 用 ✓）"""
    return any(word in str(text or '') for word in (
        '失败', '未启用', '没有持仓', '无法', '不能交易', '未连接',
        '禁止', '未知', '未成功', '没有交易', '不能'))


class Trading:
    """一个 desk 的下单执行器（只依赖「tqsdk 形状」的 api ✓）"""

    def __init__(self, desk):
        self.desk = desk
        self._tasks: Dict[str, Any] = {}
        self._position_error = ''

    def clear_account_cache(self) -> None:
        """切换模拟/实盘后清掉 TargetPosTask 缓存（否则仍下到旧账户 ✗）"""
        self._tasks.clear()

    # ------------------------------------------------------------ 回放
    def _replay_sim(self, symbol: str = ''):
        """回放中 → 返回**本地模拟账户**（否则 None ✓）"""
        checker = getattr(self.desk, 'is_replaying', None)
        if not callable(checker):
            return None
        try:
            if not checker(symbol):
                return None
        except Exception:                                        # noqa: BLE001
            return None
        getter = getattr(self.desk, 'replay_sim', None)
        return getter(symbol) if callable(getter) else None

    # ------------------------------------------------------------ 基础
    def api(self, symbol: str = ''):
        """下单用的 api —— **按合约**选行情源（不是报价页筛选 ✓）"""
        getter = getattr(self.desk, 'feed_of', None)
        feed = getter(symbol) if callable(getter) else self.desk.current_feed()
        return getattr(feed, 'api', None) if feed is not None else None

    def account_kwargs(self, symbol: str = '') -> Dict[str, Any]:
        view = self.desk.account_view()
        if view is None:
            return {}
        try:
            return view.account_kwargs(symbol)
        except TypeError:                       # 旧签名（不带 symbol）✓
            return view.account_kwargs()

    def account_label(self, symbol: str = '') -> str:
        if self._replay_sim(symbol) is not None:
            return '本地模拟（回放）'
        """下单目标的名字：`天勤模拟` / `天勤实盘` / `股票本地模拟` ✓

        desk 的约定（用户明确要求）：**股票 → 本地模拟盘，期货 → 天勤账号**，
        两者互不混用 ✓
        """
        feed = self.desk.feed_of(symbol) if hasattr(self.desk, 'feed_of')             else self.desk.current_feed()
        kind = getattr(feed, 'kind', '')
        if kind == 'stocks':
            api = getattr(feed, 'api', None)
            trading = bool(getattr(api, '_trd', None) is not None)
            return '股票实盘' if trading else '股票本地模拟'
        view = self.desk.account_view()
        if view is None:
            return '天勤'
        labels = view.labels()
        name = labels[view.index] if labels else ''
        real = bool(str(_field(view.current(), 'broker_id', '') or ''))
        return f'天勤{"实盘" if real else "模拟"}{"·" + name if name else ""}'

    def is_real(self, symbol: str = '') -> bool:
        """实盘才需要二次确认（股票实盘 / 天勤实盘 ✓）"""
        if self._replay_sim(symbol) is not None:
            return False
        feed = self.desk.feed_of(symbol) if hasattr(self.desk, 'feed_of')             else self.desk.current_feed()
        if getattr(feed, 'kind', '') == 'stocks':
            api = getattr(feed, 'api', None)
            return bool(getattr(api, '_trd', None) is not None)
        view = self.desk.account_view()
        if view is None:
            return False
        return bool(str(_field(view.current(), 'broker_id', '') or ''))

    def ready(self, symbol: str = '') -> bool:
        # ★ 回放中：本地模拟账户随时可下单（不依赖天勤 ✓）
        if self._replay_sim(symbol) is not None:
            return True
        return bool(getattr(self.desk, 'trading', False)
                    and self.api(symbol) is not None)

    # ------------------------------------------------------------ 下单
    def place(self, symbol: str, side: str, volume: int,
              price: Optional[float] = None) -> str:
        """限价下单（``price`` 为空 → 市价）✓ 返回给用户看的一句话"""
        if not _tradeable(symbol):
            return f'{symbol} 不能交易（主连 / 指数只做行情，请打开具体月份合约）'
        sim = self._replay_sim(symbol)
        if sim is not None:
            # ★ 回放：记进本地模拟账户（和本地图表一样 ✓）
            try:
                last = (self.desk._last_rows.get(symbol) or {}).get('last')
            except Exception:                                    # noqa: BLE001
                last = None
            use_price = price or last or 0
            close = str(side).lower() == 'close'
            if close:
                book = (sim.positions or {}).get(symbol) or {}
                long_volume = float(book.get('long') or 0.0)
                short_volume = float(book.get('short') or 0.0)
                if long_volume <= 0 and short_volume <= 0:
                    return f'{symbol} 没有持仓'
                volume = int(long_volume or short_volume)
                side = 'sell' if long_volume > 0 else 'buy'
            result = sim.order(symbol, str(side).lower(), volume, use_price,
                               close)
            if not result.get('ok'):
                return f"下单失败：{result.get('error')}"
            pusher = getattr(self.desk, 'replay_account_payload', None)
            if callable(pusher):
                self.desk.push(pusher(symbol))
            shown = _price_text(use_price, self._decimals(symbol))
            text = (f'本地模拟（回放） {symbol} '
                    f"{'平仓' if close else str(side).upper()} "
                    f'{int(volume)} 手 @ {shown}')
            self.desk.push_log(f'[下单] {text}', 'success')
            return text
        if not getattr(self.desk, 'trading', False):
            return '下单未启用（需要先连接行情/交易接口）'
        api = self.api(symbol)
        if api is None:
            feed = self.desk.feed_of(symbol) if hasattr(self.desk, 'feed_of')                 else None
            name = '股票' if getattr(feed, 'kind', '') == 'stocks' else '期货'
            return f'{symbol} 所属的{name}接口未连接，无法下单'
        direction, offset = SIDE_MAP.get(str(side).lower(), ('BUY', 'OPEN'))
        volume = max(1, int(volume or 1))
        if str(side).lower() == 'close':
            position = self._position(symbol)
            # ★ 天勤新老版本字段名不一样：pos_long / volume_long 都要认 ✓
            long_volume = _num(_field_any(position, LONG_VOLUME)) or 0.0
            short_volume = _num(_field_any(position, SHORT_VOLUME)) or 0.0
            if long_volume <= 0 and short_volume <= 0:
                return f'{symbol} 没有持仓'
            direction = 'SELL' if long_volume > 0 else 'BUY'
        try:
            kwargs = self.account_kwargs(symbol)
            api.insert_order(symbol=symbol, direction=direction,
                             offset=offset, volume=volume,
                             limit_price=(None if not price else float(price)),
                             **kwargs)
        except TypeError:                       # 老签名不支持 keyword 写法
            api.insert_order(symbol, direction, offset, volume,
                             (None if not price else float(price)),
                             **self.account_kwargs(symbol))
        except ValueError as error:                              # 期货单发给股票接口
            return str(error)
        except Exception as error:                               # noqa: BLE001
            return f'下单失败: {error!r}'
        shown = '市价' if not price else _price_text(
            price, self._decimals(symbol))
        text = (f'{self.account_label(symbol)} {symbol} {direction}/{offset} '
                f'{volume} {_unit(symbol)} @ {shown}')
        self.desk.push_log(f'[下单] {text}', 'success')
        return text

    def _decimals(self, symbol: str) -> int:
        """合约小数位（日志里的价格和界面一致 ✓）"""
        getter = getattr(self.desk, 'decimals_of', None)
        if callable(getter):
            try:
                return int(getter(symbol))
            except Exception:                                    # noqa: BLE001
                pass
        return 2

    # ------------------------------------------------------------ 平 / 反 / 全
    def action(self, kind: str, symbol: str = '') -> str:
        """``close`` 平 / ``reverse`` 反 / ``all`` 全平 / ``cancel`` 撤 / ``cancel_all`` 全撤"""
        if symbol and not _tradeable(symbol) and str(kind or '').lower() not in (
                'all', 'cancel_all'):
            return f'{symbol} 不能交易（主连 / 指数只做行情）'
        sim = self._replay_sim(symbol)
        if sim is not None:
            kind_lower = str(kind or '').lower()
            if kind_lower in ('cancel', 'cancel_all'):
                count = sim.cancel_pending(symbol)
                if not count:
                    return '没有未成交的挂单'
                self.desk.push_log(f'回放模拟账户：已撤 {count} 笔挂单', 'info')
                pusher = getattr(self.desk, 'replay_account_payload', None)
                if callable(pusher):
                    self.desk.push(pusher(symbol))
                return f'已撤 {count} 笔挂单'
            if kind_lower == 'all':
                sim.close_all()
                self.desk.push_log('回放模拟账户：市价平掉全部持仓', 'info')
            elif kind_lower == 'reverse':
                sim.reverse_all()
                self.desk.push_log('回放模拟账户：反手（平仓 + 反向开仓）',
                                   'info')
            elif kind_lower in ('close', 'close_main'):
                book = (sim.positions or {}).get(symbol) or {}
                long_volume = float(book.get('long') or 0.0)
                short_volume = float(book.get('short') or 0.0)
                if long_volume <= 0 and short_volume <= 0:
                    return f'{symbol} 没有持仓'
                sim.order(symbol, 'sell' if long_volume > 0 else 'buy',
                          long_volume or short_volume, sim._price(symbol),
                          True)
                self.desk.push_log(f'回放模拟账户：平仓 {symbol}', 'info')
            else:
                return f'未知动作 {kind!r}'
            pusher = getattr(self.desk, 'replay_account_payload', None)
            if callable(pusher):
                self.desk.push(pusher(symbol))
            return '本地模拟（回放）已执行'
        if not self.ready(symbol):
            return '交易未启用'
        kind = str(kind or '').lower()
        if kind in ('cancel', 'cancel_all'):
            return self._cancel(symbol, all_orders=kind == 'cancel_all')
        if kind == 'all':
            return self._close_all()          # 全平不需要指定合约 ✓
        if not symbol:
            return '缺少合约'
        position = self._position(symbol)
        long_volume = int(_num(_field_any(position, LONG_VOLUME)) or 0.0)
        short_volume = int(_num(_field_any(position, SHORT_VOLUME)) or 0.0)
        held = long_volume - short_volume
        if not long_volume and not short_volume:
            return f'{symbol} 没有持仓'
        if kind in ('close', 'close_main'):
            # 平仓 / 主价平仓：目标仓归零（TargetPosTask 走市价 ✓）
            target = 0
        elif kind == 'reverse':
            target = -held if held else 0
        else:
            return f'未知动作 {kind!r}'
        return self._set_target(symbol, target)

    def close_symbol(self, symbol: str, volume: int = 0) -> str:
        """**市价平掉指定合约**的持仓（`volume=0` → 全部）/ 回放走本地模拟 ✓"""
        if not _tradeable(symbol):
            return f'{symbol} 不能交易（主连 / 指数只做行情）'
        sim = self._replay_sim(symbol)
        if sim is not None:
            book = (sim.positions or {}).get(symbol) or {}
            long_volume = float(book.get('long') or 0.0)
            short_volume = float(book.get('short') or 0.0)
            if long_volume <= 0 and short_volume <= 0:
                return f'{symbol} 没有持仓'
            held = int(long_volume or short_volume)
            qty = max(1, min(int(volume or held), held))
            sim.order(symbol, 'sell' if long_volume > 0 else 'buy', qty,
                      sim._price(symbol), True)
            pusher = getattr(self.desk, 'replay_account_payload', None)
            if callable(pusher):
                self.desk.push(pusher(symbol))
            return f'回放模拟：市价平 {symbol} {qty} 手'
        if not self.ready(symbol):
            return '交易未启用'
        position = self._position(symbol)
        long_volume = int(_num(_field_any(position, LONG_VOLUME)) or 0.0)
        short_volume = int(_num(_field_any(position, SHORT_VOLUME)) or 0.0)
        held = long_volume or short_volume
        if not held:
            return f'{symbol} 没有持仓'
        qty = max(1, min(int(volume or held), held))
        direction = 'SELL' if long_volume > 0 else 'BUY'
        return self._market_order(symbol, direction, 'CLOSE', qty)

    def reverse_symbol(self, symbol: str, volume: int = 0) -> str:
        """**反手**：市价平掉 `volume` 手后反向开同样手数 ✓"""
        if not _tradeable(symbol):
            return f'{symbol} 不能交易（主连 / 指数只做行情）'
        sim = self._replay_sim(symbol)
        if sim is not None:
            book = (sim.positions or {}).get(symbol) or {}
            long_volume = float(book.get('long') or 0.0)
            short_volume = float(book.get('short') or 0.0)
            held = int(long_volume or short_volume)
            if not held:
                return f'{symbol} 没有持仓'
            qty = max(1, min(int(volume or held), held))
            if long_volume > 0:
                sim.order(symbol, 'sell', qty, sim._price(symbol), True)
                sim.order(symbol, 'sell', qty, sim._price(symbol))
            else:
                sim.order(symbol, 'buy', qty, sim._price(symbol), True)
                sim.order(symbol, 'buy', qty, sim._price(symbol))
            pusher = getattr(self.desk, 'replay_account_payload', None)
            if callable(pusher):
                self.desk.push(pusher(symbol))
            return f'回放模拟：反手 {symbol} {qty} 手'
        if not self.ready(symbol):
            return '交易未启用'
        position = self._position(symbol)
        long_volume = int(_num(_field_any(position, LONG_VOLUME)) or 0.0)
        short_volume = int(_num(_field_any(position, SHORT_VOLUME)) or 0.0)
        held = long_volume or short_volume
        if not held:
            return f'{symbol} 没有持仓'
        qty = max(1, min(int(volume or held), held))
        # 先市价平，再反向开（两条 insert_order，逻辑直观 ✓）
        closed = self._market_order(
            symbol, 'SELL' if long_volume > 0 else 'BUY', 'CLOSE', qty)
        if _trade_failed(closed):
            return f'反手失败（平仓未成功）：{closed}'
        other = 'BUY' if long_volume > 0 else 'SELL'
        return self._market_order(symbol, other, 'OPEN', qty)

    def cancel_order(self, order_id: str, symbol: str = '') -> str:
        """撤**指定**委托（`order_id`）；本地模拟 / 回放按合约撤 ✓"""
        sim = self._replay_sim(symbol)
        if sim is not None:
            count = sim.cancel_pending(symbol)
            return (f'回放模拟：已撤 {count} 笔挂单' if count
                    else '没有可撤的挂单')
        if not self.ready(symbol):
            return '交易未启用'
        api = self.api(symbol)
        if api is None or not order_id:
            return '缺少委托号'
        canceller = getattr(api, 'cancel_order', None)
        if not callable(canceller):
            return '当前接口不支持按单撤单'
        try:
            try:
                canceller(order_id=order_id)
            except TypeError:
                canceller(order_id)
        except Exception as error:                               # noqa: BLE001
            return f'撤单失败：{error!r}'
        self.desk.push_log(f'[撤单] {symbol or ""} {order_id}', 'success')
        return f'已撤委托 {order_id}'

    def _market_order(self, symbol: str, direction: str, offset: str,
                      volume: int) -> str:
        """市价单（`limit_price=None`）✓"""
        api = self.api(symbol)
        if api is None:
            return '没有交易接口'
        try:
            kwargs = self.account_kwargs(symbol)
            try:
                api.insert_order(symbol=symbol, direction=direction,
                                 offset=offset, volume=int(volume),
                                 limit_price=None, **kwargs)
            except TypeError:
                api.insert_order(symbol, direction, offset, int(volume),
                                 None, **kwargs)
        except Exception as error:                               # noqa: BLE001
            return f'下单失败：{error!r}'
        text = (f'{self.account_label(symbol)} {symbol} {direction}/{offset} '
                f'{int(volume)} {_unit(symbol)} @ 市价')
        self.desk.push_log(f'[下单] {text}', 'success')
        return text

    def _close_all(self) -> str:
        self._position_error = ''
        positions = self._positions()
        if not positions and self._position_error:
            return f'全部平仓失败：无法查询持仓（{self._position_error}）'
        done = 0
        failed = []
        for item in positions:
            code = position_symbol(item)
            long_volume = int(_num(_field_any(item, LONG_VOLUME)) or 0.0)
            short_volume = int(_num(_field_any(item, SHORT_VOLUME)) or 0.0)
            if not long_volume and not short_volume:
                continue
            text = self._set_target(code, 0)
            if _trade_failed(text):
                failed.append(f'{code}: {text}')
            else:
                done += 1
        if failed:
            return (f'全部平仓：成功 {done} 个，失败 {len(failed)} 个（'
                    + '；'.join(failed[:3]) + '）')
        return f'全部平仓：{done} 个合约' if done else '没有持仓'

    def _set_target(self, symbol: str, target: int) -> str:
        task = self._target_task(symbol)
        if task is None:
            return f'{symbol} 无法建目标仓任务'
        api = self.api(symbol)
        raw = getattr(api, 'raw_call', None)

        def apply(item) -> None:
            if hasattr(item, 'set_target_volume'):
                item.set_target_volume(int(target))
            else:
                item.set_target_size(size=int(target))

        try:
            if callable(raw):
                raw(lambda _api: apply(task), 3.0)   # 在 api 线程里调 ✓
            else:
                apply(task)
        except Exception as error:                               # noqa: BLE001
            return f'调仓失败: {error!r}'
        text = f'{self.account_label()} {symbol} 目标仓位 → {target}'
        self.desk.push_log(f'[调仓] {text}', 'success')
        return text

    def _target_task(self, symbol: str):
        if symbol in self._tasks:
            return self._tasks[symbol]
        api = self.api(symbol)
        if api is None:
            return None
        kwargs = self.account_kwargs(symbol)
        raw = getattr(api, 'raw_call', None)

        def build(item):
            factory = getattr(item, 'target_pos_task', None)   # 股票版 ✓
            if callable(factory):
                return factory(symbol)
            from tqsdk import TargetPosTask
            return TargetPosTask(item, symbol, **kwargs)

        try:
            if callable(raw):
                # ★ 必须用**真 api** 建（代理对象不是 TqApi 实例 ✗）
                task = raw(build, 5.0)
            else:
                task = build(api)
            if task is None:
                return None
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] TargetPosTask 创建失败: {error!r}')
            return None
        self._tasks[symbol] = task
        return task

    # ------------------------------------------------------------ 撤单
    def _cancel(self, symbol: str = '', all_orders: bool = False) -> str:
        api = self.api(symbol)
        if api is None:
            return '没有交易接口'
        kwargs = self.account_kwargs(symbol)
        try:
            orders = _records(api.get_order(**kwargs))
        except Exception:                                        # noqa: BLE001
            orders = []

        def same_symbol(item) -> bool:
            full = position_symbol(item)
            want = str(symbol or '')
            return (not want or not full or full == want
                    or ('.' in want and full.split('.')[-1]
                        == want.split('.')[-1]
                        and full.split('.')[0].upper()
                        == want.split('.')[0].upper()))

        targets = [item for item in orders
                   if str(_field(item, 'status') or '').upper() == 'ALIVE'
                   and (all_orders or same_symbol(item))]
        cancelled = 0
        for item in targets:
            order_id = _field(item, 'order_id')
            if not order_id:
                continue
            try:
                api.cancel_order(order_id, **kwargs)
                cancelled += 1
            except Exception:                                    # noqa: BLE001
                pass
        if cancelled:
            self.desk.push_log(f'[撤单] {self.account_label()} '
                               f'{symbol or "全部"} 撤 {cancelled} 笔', 'warning')
            return f'已撤 {cancelled} 笔委托'
        return '没有可撤的委托'

    # ------------------------------------------------------------ 查询
    def _position(self, symbol: str):
        api = self.api(symbol)
        if api is None or not symbol:
            return None
        try:
            return api.get_position(symbol, **self.account_kwargs())
        except Exception:                                        # noqa: BLE001
            # 有些接口只认 `get_position()`（不给 symbol）→ 从全量里挑 ✓
            try:
                for item in _records(api.get_position(
                        **self.account_kwargs())):
                    code = position_symbol(item)
                    if (code == symbol
                            or code.split('.')[-1] == symbol.split('.')[-1]):
                        return item
            except Exception:                                    # noqa: BLE001
                pass
            return None

    def _positions(self):
        self._position_error = ''
        api = self.api()
        if api is None:
            self._position_error = '没有交易接口'
            return []
        lister = getattr(api, 'get_position_list', None)
        if callable(lister):
            try:
                return list(lister() or [])
            except Exception as error:                           # noqa: BLE001
                self._position_error = str(error)
                return []
        try:
            return _records(api.get_position(**self.account_kwargs()))
        except Exception as error:                               # noqa: BLE001
            self._position_error = str(error)
            return []


def _price_text(value, digits: int = 2) -> str:
    """价格 → 字符串（按合约小数位，带千分位 ✓）"""
    number = _num(value)
    if number is None:
        return '--'
    return f'{number:,.{max(0, int(digits))}f}'
