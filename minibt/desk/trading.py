"""desk 的交易执行：限价下单 / 平 / 反 / 全 / 撤单。

* 期货：``tqsdk`` 的 ``api.insert_order`` + ``TargetPosTask``（多账户带 account=）
* 股票：``StockApi`` 同形接口（默认本地模拟盘；``trade=True`` 才是真实交易）

安全：只有 ``Desk(allow_trading=True)`` 且拿到 api 才会真的下单；
实盘账户（有 ``broker_id``）由前端**二次确认**，且所有动作都写进运行日志 ✓。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .stocks import display_symbol


def _protocol_push_toast(text: str, level: str = 'info') -> Dict[str, Any]:
    """最小的 toast 补丁（不想在 trading 里 import desk.protocol 全量 ✓）"""
    return {'type': 'toast', 'text': str(text), 'level': str(level)}

#: 方向/开平映射（前端只发 buy/sell/close ✓）
#: 今仓 / 昨仓字段（上期所、能源中心"平今 / 平昨"必须分开下 ✓）
LONG_TODAY_FIELDS = ('pos_long_today', 'volume_long_today')
LONG_HIS_FIELDS = ('pos_long_his', 'volume_long_his')
SHORT_TODAY_FIELDS = ('pos_short_today', 'volume_short_today')
SHORT_HIS_FIELDS = ('pos_short_his', 'volume_short_his')

#: 分「平今 / 平昨」的交易所（用户实测：只发 CLOSE 会被拒 / 平不掉 ✗）
SPLIT_CLOSE_EXCHANGES = ('SHFE', 'INE')

#: 持仓均价字段（对手价兜底用 ✓）
LONG_AVG_DEFAULT = ('position_price_long', 'open_price_long')
SHORT_AVG_DEFAULT = ('position_price_short', 'open_price_short')

SIDE_MAP = {
    'buy': ('BUY', 'OPEN'),
    'sell': ('SELL', 'OPEN'),
    'close': ('CLOSE', 'CLOSE'),
}


#: 股票代码前缀（tqsdk / 富途写法都认 ✓）
_STOCK_PREFIXES = ('SH.', 'SZ.', 'HK.', 'US.', 'JP.', 'SSE.', 'SZSE.', 'BSE.')


def _is_stock_symbol(symbol: str) -> bool:
    return str(symbol or '').upper().startswith(_STOCK_PREFIXES)


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
        '禁止', '未知', '未成功', '没有交易', '不能',
        # ★ 平仓相关的"没下单"提示（以前被当成成功 → 清仓提示成功但没交易 ✗）
        '没有可平', '已取消下单', '可平', '没有可撤'))


class Trading:
    """一个 desk 的下单执行器（只依赖「tqsdk 形状」的 api ✓）"""

    def __init__(self, desk):
        self.desk = desk
        self._tasks: Dict[str, Any] = {}
        self._position_error = ''

    def clear_account_cache(self) -> None:
        """切换模拟 / 实盘 / **换天勤账户**后清缓存 ✓

        不清的话 `TargetPosTask` 还绑着旧 api（下单串到旧连接），
        拒单回执（`_watch`）也会把旧账户的单号带过来 ✗
        """
        self._tasks.clear()
        try:
            self._watch.clear()
        except Exception:                                        # noqa: BLE001
            pass

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
        """多账户时下游调用都要带 ``account=``（**按该页面的账户** ✓）"""
        view = self.desk.account_view()
        if view is None:
            return {}
        key = self._account_key(symbol)
        try:
            return view.account_kwargs(symbol, key)
        except TypeError:                       # 旧签名（不带 symbol）✓
            try:
                return view.account_kwargs(symbol)
            except TypeError:
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
            # ★ 富途**模拟账户**不算实盘（以前只要交易上下文存在就当实盘 ✗）
            ctx = getattr(api, '_trd', None) is not None
            env = str(getattr(api, '_trd_env', '') or '').upper()
            if ctx and env.endswith('REAL'):
                return '股票实盘（富途）'
            if ctx:
                return '股票模拟（富途）'
            return '股票本地模拟'
        # ★ 统一账户：按**当前账户 kind** 起名（快期模拟 / 富途模拟 / TqAccount）✓
        key = self._account_key(symbol)
        if key == 'futu':
            return '富途模拟'
        view = self.desk.account_view()
        if view is None:
            return '天勤模拟' if key != 'real' else '天勤实盘'
        current = view.instance_for(key, symbol)
        real = bool(str(_field(current, 'broker_id', '') or ''))
        # 「快期模拟」不带后缀（旧测试 / 日志里都是这个名字 ✓）
        return '天勤实盘' if real else '天勤模拟'

    def is_real(self, symbol: str = '') -> bool:
        """实盘才需要二次确认（股票实盘 / 天勤实盘 ✓）"""
        if self._replay_sim(symbol) is not None:
            return False
        key = self._account_key(symbol)
        if key == 'kq':
            return False
        feed = (self.desk.feed_of(symbol) if hasattr(self.desk, 'feed_of')
                else self.desk.current_feed())
        if getattr(feed, 'kind', '') == 'stocks':
            api = getattr(feed, 'api', None)
            # 只有**真实**交易上下文才要二次确认（模拟盘不需要 ✓）
            if getattr(api, '_trd', None) is None:
                return False
            env = str(getattr(api, '_trd_env', '') or '').upper()
            return env.endswith('REAL')
        view = self.desk.account_view()
        if view is None:
            return False
        try:
            return bool(str(_field(view.instance_for(key, symbol),
                                   'broker_id', '') or ''))
        except Exception:                                        # noqa: BLE001
            return bool(str(_field(view.current(), 'broker_id', '') or ''))

    def ready(self, symbol: str = '') -> bool:
        # ★ 回放中：本地模拟账户随时可下单（不依赖天勤 ✓）
        if self._replay_sim(symbol) is not None:
            return True
        return bool(getattr(self.desk, 'trading', False)
                    and self.api(symbol) is not None)

    # ------------------------------------------------------------ 下单
    #: 最近下的单（`order_id` → 时间），下一拍检查是否被**拒单** ✓
    PENDING_CHECK_SECONDS = 60.0

    def market_price(self, symbol: str, side: str):
        """**对手价**：买入看卖一、卖出看买一（没有就退最新价）✓

        快期交易页的「价格」留空时就是对手价（用户要求 2026-11-05 ✓）
        """
        quote = None
        try:
            feed = self.desk.feed_of(symbol) if hasattr(self.desk, 'feed_of')                 else None
            spec = getattr(feed, 'spec', None)
            quote = spec(symbol) if callable(spec) else None
        except Exception:                                        # noqa: BLE001
            quote = None
        keys = (('ask_price1', 'last_price') if str(side).lower() == 'buy'
                else ('bid_price1', 'last_price'))
        for key in keys:
            value = _num(getattr(quote, key, None))
            if value and value > 0:
                return float(value)
        # 兜底：报价行缓存 → 持仓均价（**绝不返回 None**，见下）✓
        try:
            row = (getattr(self.desk, '_last_rows', {}) or {}).get(symbol) or {}
            value = _num(row.get('last'))
            if value and value > 0:
                return float(value)
        except Exception:                                        # noqa: BLE001
            pass
        position = self._position(symbol)
        for key in (LONG_AVG_DEFAULT, SHORT_AVG_DEFAULT):
            value = _num(_field_any(position, key))
            if value and value > 0:
                return float(value)
        return None

    def close_plan(self, symbol: str, side: str,
                   volume: int) -> List[tuple]:
        """平仓要发几笔、各多少手 → ``[(offset, qty), …]`` ✓

        **锁仓**（同一合约多空都有）时，交易所按**方向**区分平哪边：
        ``SELL + CLOSE`` 平多头、``BUY + CLOSE`` 平空头 —— 所以
        "平多" 必须是 SHFE 的 ``SELL/CLOSE``、**不能**发成开仓 ✗。

        另外 **上期所 / 能源中心** 必须区分**平今**（``CLOSETODAY``）和
        **平昨**（``CLOSE``）：只发 ``CLOSE`` 在"全是今仓"时会失败：
        委托被拒 → 界面看起来"什么都没发生"（用户实测 2026-11-05 ✗）。
        """
        volume = max(0, int(volume or 0))
        if volume <= 0:
            return []
        code = str(symbol or '').upper()
        exchange = code.split('.')[0] if '.' in code else ''
        if exchange not in SPLIT_CLOSE_EXCHANGES:
            return [('CLOSE', volume)]
        position = self._position(symbol)
        long_side = str(side or '').lower() == 'sell'
        today = _num(_field_any(
            position,
            LONG_TODAY_FIELDS if long_side else SHORT_TODAY_FIELDS)) or 0.0
        his = _num(_field_any(
            position,
            LONG_HIS_FIELDS if long_side else SHORT_HIS_FIELDS)) or 0.0
        total = _num(_field_any(
            position, LONG_VOLUME if long_side else SHORT_VOLUME)) or 0.0
        if today <= 0 and his <= 0:
            # 老版本没有今/昨字段 → 只能发 CLOSE（交易所自己挑）
            return [('CLOSE', volume)]
        if today <= 0 and his > 0:
            return [('CLOSE', volume)]
        if his <= 0 and today > 0:
            return [('CLOSETODAY', volume)]
        plan: List[tuple] = []
        remaining = volume
        use_his = min(remaining, int(his))
        if use_his > 0:
            plan.append(('CLOSE', use_his))
            remaining -= use_his
        use_today = min(remaining, int(today))
        if use_today > 0:
            plan.append(('CLOSETODAY', use_today))
        if not plan:
            plan.append(('CLOSE', min(volume, int(total or volume))))
        return plan

    def position_sides(self, symbol: str) -> Dict[str, int]:
        """该合约**多 / 空各多少手**（锁仓时两边都 > 0 ✓）"""
        position = self._position(symbol)
        long_volume = int(_num(_field_any(position, LONG_VOLUME)) or 0.0)
        short_volume = int(_num(_field_any(position, SHORT_VOLUME)) or 0.0)
        return {'long': long_volume, 'short': short_volume}

    def _account_key(self, symbol: str = '') -> str:
        """这个合约所在页面的账户 key（**按页独立** ✓ 用户 2026-11-05）"""
        reader = getattr(self.desk, 'account_key_for', None)
        if callable(reader):
            try:
                return str(reader(symbol) or '')
            except Exception:                                    # noqa: BLE001
                return ''
        try:
            return str(self.desk.active_account_key() or '')
        except Exception:                                        # noqa: BLE001
            return ''

    def account_kind_issue(self, symbol: str) -> str:
        """品种 vs **当前账户**是否匹配 → 返回错误文案（空串 = 可以交易 ✓）

        用户 2026-11-05：快期模拟 / TqAccount 只交易**期货**，富途模拟只交易
        **股票** —— 用错账户直接拦下来并提示切换 ✓
        """
        try:
            key = str(self._account_key(symbol) or '')
        except Exception:                                        # noqa: BLE001
            key = ''
        stock = _is_stock_symbol(symbol)
        if key == 'futu' and not stock:
            return (f'{symbol} 是期货，当前账户是「富途模拟」'
                    '（只能交易股票）→ 请切换账户')
        if key in ('kq', 'real') and stock:
            label = '快期模拟' if key == 'kq' else 'TqAccount'
            return (f'{symbol} 是股票，当前账户是「{label}」'
                    '（只能交易期货）→ 请切换账户')
        return ''

    def insert(self, symbol: str, side: str, offset: str, volume: int,
               price=None) -> str:
        """**限价下单**（`side`=buy/sell，`offset`=open/close）—— 快期四个按钮用 ✓

        * `price` 为空 / 0 → **对手价**（买→卖一，卖→买一）；
        * 平仓前校验手数 ≤ 对应方向持仓（超了直接提醒，不下单 ✗）；
        * 下单后把 `order_id` 记下来，下一拍检查天勤是否**拒单**
          （保证金不足 / 超过可平手数…），把 `last_msg` 弹给用户 ✓
        """
        symbol = str(symbol or '')
        side = str(side or '').lower()
        offset = str(offset or 'open').lower()
        try:
            volume = max(1, int(volume or 1))
        except (TypeError, ValueError):
            volume = 1
        if side not in ('buy', 'sell'):
            return f'方向不合法：{side}'
        if offset not in ('open', 'close'):
            return f'开平不合法：{offset}'
        mismatch = self.account_kind_issue(symbol)
        if mismatch:
            return mismatch
        if not _tradeable(symbol):
            return (f'{symbol} 不能交易（主连 / 指数只做行情，'
                    '请打开具体月份合约）')
        direction = 'BUY' if side == 'buy' else 'SELL'
        tq_offset = 'OPEN' if offset == 'open' else 'CLOSE'
        plan = ([('OPEN', int(volume))] if offset == 'open'
                else self.close_plan(symbol, side, volume))
        # ---- 平仓：手数不能超过该方向持仓 ✓
        if offset == 'close':
            position = self._position(symbol)
            long_volume = _num(_field_any(position, LONG_VOLUME)) or 0.0
            short_volume = _num(_field_any(position, SHORT_VOLUME)) or 0.0
            available = short_volume if side == 'buy' else long_volume
            if available <= 0:
                return (f'{symbol} 没有可平的'
                        f'{"空" if side == "buy" else "多"}头持仓')
            if volume > available:
                return (f'{symbol} 可平{int(available)}手，'
                        f'你填了 {volume} 手（已取消下单）')
        # ---- 价格：空 = 对手价 ✓
        limit = None
        try:
            given = float(price or 0)
        except (TypeError, ValueError):
            given = 0.0
        if given > 0:
            limit = given
        else:
            # 空 = 对手价。⚠ **绝不**用 `limit_price=None`：
            #   上期所 / 中金所 / 能源中心 / 上交所 / 深交所**不支持市价单**
            #   （用户实测 2026-11-05：`不支持市价单，请使用 limit_price` ✗）
            limit = self.market_price(symbol, side)
            if limit is None:
                # 连对手价 / 最新价 / 持仓均价都拿不到（极少见：行情未就绪）
                # → 只能退回市价单；上期所等会拒单，`poll_orders()` 会把
                #   天勤的原话弹出来提示用户填价格 ✓
                try:
                    self.desk.push_log(
                        f'{symbol} 行情未就绪，本次按市价单提交'
                        '（上期所 / 中金所等可能不支持，被拒后请填价格重试）',
                        'warning')
                except Exception:                                # noqa: BLE001
                    pass
        # ---- 回放 / 本地模拟：直接记账 ✓
        sim = self._replay_sim(symbol)
        if sim is not None:
            result = sim.order(symbol, side, volume, limit,
                               offset == 'close')
            if not result.get('ok'):
                return f"下单失败：{result.get('error')}"
            pusher = getattr(self.desk, 'replay_account_payload', None)
            if callable(pusher):
                self.desk.push(pusher(symbol))
            text = (f'本地模拟（回放） {symbol} '
                    f'{"买" if side == "buy" else "卖"}'
                    f'{"开" if offset == "open" else "平"} {volume} 手 @ '
                    f'{_price_text(limit, self._decimals(symbol))}')
            self.desk.push_log(f'[下单] {text}', 'success')
            return text
        if not getattr(self.desk, 'trading', False):
            return '下单未启用（需要先连接行情/交易接口）'
        api = self.api(symbol)
        if api is None:
            return f'{symbol} 所属接口未连接，无法下单'
        self.release_target_task(symbol)          # 停掉"目标仓机器人" ✓
        kwargs = self.account_kwargs(symbol)
        parts: List[str] = []
        for tq_offset, chunk in (plan or [(tq_offset, int(volume))]):
            try:
                order = api.insert_order(symbol=symbol, direction=direction,
                                         offset=tq_offset, volume=int(chunk),
                                         limit_price=limit, **kwargs)
            except TypeError:
                try:
                    order = api.insert_order(symbol, direction, tq_offset,
                                             int(chunk), limit, **kwargs)
                except ValueError as error:                    # 期货单发股票接口
                    return str(error)
            except ValueError as error:
                return str(error)
            except Exception as error:                           # noqa: BLE001
                return f'下单失败: {error!r}'
            self.watch_order(order)
            if offset == 'open':
                label = ''        # 动词里已经有"开"了 ✓
            elif tq_offset == 'CLOSETODAY':
                label = '平今'
            else:
                label = ''        # 普通平仓（动词里已经有"平"了 ✓）
            parts.append(f'{label} {int(chunk)} 手'.strip())
        detail = ' + '.join(parts)
        verb = ('买开' if offset == 'open' and side == 'buy' else
                '卖开' if offset == 'open' else
                '买平' if side == 'buy' else '卖平')
        text = (f'{self.account_label(symbol)} {symbol} {verb} {detail} @ '
                f'{"市价" if limit is None else _price_text(limit, self._decimals(symbol))}')
        self.desk.push_log(f'[下单] {text}', 'success')
        return text

    def watch_order(self, order) -> None:
        """记下刚下的单，下一拍看天勤有没有**拒单**（保证金不足等 ✓）"""
        order_id = str(getattr(order, 'order_id', '') or '')
        if not order_id:
            return
        pending = getattr(self, '_watch', None)
        if pending is None:
            pending = self._watch = {}
        pending[order_id] = {'at': __import__('time').monotonic(),
                             'symbol': str(getattr(order, 'instrument_id', '')
                                           or '')}

    def poll_orders(self) -> None:
        """检查最近下的单：**被拒**（保证金不足 / 平仓超量）→ 弹提示 ✓

        tqsdk 的 `insert_order` 是异步的，拒单信息在 `order.status` =
        ``REJECTED`` 和 `order.last_msg` 里（用户截图 `保证金不足.png` ✓）
        """
        pending = getattr(self, '_watch', None)
        if not pending:
            return
        api_getter = getattr(self, 'api', None)
        now = __import__('time').monotonic()
        for order_id, meta in list(pending.items()):
            symbol = str(meta.get('symbol') or '')
            api = api_getter(symbol) if callable(api_getter) else None
            getter = getattr(api, 'get_order', None) if api is not None else None
            order = None
            if callable(getter):
                try:
                    order = getter(order_id, **self.account_kwargs(symbol))
                except TypeError:
                    order = getter(order_id)
                except Exception:                                # noqa: BLE001
                    order = None
            status = str(getattr(order, 'status', '') or '').upper()
            message = str(getattr(order, 'last_msg', '') or '')
            if status == 'REJECTED':
                pending.pop(order_id, None)
                text = message or '下单被拒绝'
                self.desk.push_log(f'[下单失败] {symbol} {text}', 'error')
                self.desk.push(_protocol_push_toast(
                    f'下单失败：{text}', 'error'))
                continue
            if status in ('FINISHED', 'DELETED', 'CANCELLED'):
                pending.pop(order_id, None)
                continue
            if now - float(meta.get('at') or 0.0) > self.PENDING_CHECK_SECONDS:
                pending.pop(order_id, None)

    def release_target_task(self, symbol: str) -> None:
        """释放某合约的 ``TargetPosTask``（**手动下单前必须调** ✓）

        ``TargetPosTask`` 是"持续维持目标仓位"的机器人：它每收到一次回报就会
        **撤掉自己不认识的挂单**再重新下单。所以用户手填价格挂出的限价单
        （平仓线）会在下一拍被它撤掉 —— 表现为"平仓线闪一下就消失、
        未成交委托也没了"（用户实测 2026-11-05 ✗）。
        手动下单 = 用户明确意图 → 先把这个机器人停掉 ✓
        """
        task = None
        try:
            task = self._tasks.pop(str(symbol or ''), None)
        except Exception:                                        # noqa: BLE001
            task = None
        if task is None:
            return
        cancel = getattr(task, 'cancel', None)
        if not callable(cancel):
            return
        api = self.api(symbol)
        raw = getattr(api, 'raw_call', None)

        def stop(item) -> None:
            try:
                cancel()
            except Exception:                                    # noqa: BLE001
                pass

        try:
            if callable(raw):
                raw(lambda _api: stop(task), 2.0)
            else:
                stop(task)
        except Exception:                                        # noqa: BLE001
            pass

    def place(self, symbol: str, side: str, volume: int,
              price: Optional[float] = None) -> str:
        """老接口兼容：``close`` = 按持仓方向平仓，``buy``/``sell`` = 开仓 ✓

        ⚠ 老实现里 ``SIDE_MAP['close'] = ('CLOSE', 'CLOSE')`` 的**方向非法**，
          被 fallback 改回 ``('BUY', 'OPEN')`` 却把 offset 留在 ``OPEN``
          → 空仓 9 手"平仓 1 手"实际下成**卖开 1 手**（9 → 10 手 ✗，
          用户实测 2026-11-05）。现在统一走 `insert(side, offset)` ✓
        """
        key = str(side or '').lower()
        try:
            volume = max(1, int(volume or 1))
        except (TypeError, ValueError):
            volume = 1
        if key == 'close':
            position = self._position(symbol)
            long_volume = _num(_field_any(position, LONG_VOLUME)) or 0.0
            short_volume = _num(_field_any(position, SHORT_VOLUME)) or 0.0
            if long_volume <= 0 and short_volume <= 0:
                return f'{symbol} 没有持仓'
            # 平多 → 卖出平；平空 → 买入平 ✓（绝不会变成开仓）
            return self.insert(symbol, 'sell' if long_volume > 0 else 'buy',
                               'close', volume, price)
        return self.insert(symbol, 'sell' if key == 'sell' else 'buy',
                           'open', volume, price)

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
            # ★ 全平也要带合约：账户 / 行情源都按**这一页**取
            #   （用户 2026-11-06：期货页"清仓"却提示富途模拟 ✗）
            return self._close_all(symbol)
        if not symbol:
            return '缺少合约'
        position = self._position(symbol)
        long_volume = int(_num(_field_any(position, LONG_VOLUME)) or 0.0)
        short_volume = int(_num(_field_any(position, SHORT_VOLUME)) or 0.0)
        held = long_volume - short_volume
        if not long_volume and not short_volume:
            return f'{symbol} 没有持仓'
        if kind in ('close', 'close_main'):
            # ★ 平仓：显式**限价（对手价）**单 —— 以前走 TargetPosTask 的市价，
            #   上期所 / 中金所 / 能源中心 / 沪深**不支持市价单** → 下单失败 ✗
            #   （用户实测 2026-11-05：`不支持市价单，请使用 limit_price`）
            # ★ 锁仓（多空都有）→ **两边各平一次**（以前只平一边，看着没生效 ✗）
            if long_volume > 0 and short_volume > 0:
                first = self.insert(symbol, 'sell', 'close', long_volume, 0)
                second = self.insert(symbol, 'buy', 'close', short_volume, 0)
                return f'{first}；{second}'
            # ⚠ `held` 是**净仓**（空头为负）→ 手数用绝对值 ✓
            volume = abs(int(held)) or (long_volume or short_volume)
            return self.insert(symbol, 'sell' if long_volume > 0 else 'buy',
                               'close', int(volume), 0)
        if kind == 'reverse':
            # 反手 = 先按对手价平掉，再反向开同样手数（两笔限价单 ✓）
            volume = abs(held) or (long_volume or short_volume)
            close_side = 'sell' if long_volume > 0 else 'buy'
            first = self.insert(symbol, close_side, 'close', volume, 0)
            if _trade_failed(first):
                return first
            open_side = 'buy' if close_side == 'sell' else 'sell'
            second = self.insert(symbol, open_side, 'open', volume, 0)
            return f'{first}；{second}'
        return f'未知动作 {kind!r}'

    def close_symbol(self, symbol: str, volume: int = 0,
                     side: str = '') -> str:
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
        sides = self.position_sides(symbol)
        long_volume, short_volume = sides['long'], sides['short']
        wanted = str(side or '').strip()
        # ★ 锁仓（多空都有）必须按行**指定平哪一边**，否则方向就错了 ✗
        if wanted in ('多', 'long', '买'):
            use_side, held = 'sell', long_volume
        elif wanted in ('空', 'short', '卖'):
            use_side, held = 'buy', short_volume
        elif long_volume > 0 and short_volume > 0:
            return (f'{symbol} 处于锁仓（多 {long_volume} / 空 {short_volume}），'
                    '请在持仓行上右键指定平多还是平空 ✓')
        elif long_volume > 0:
            use_side, held = 'sell', long_volume
        elif short_volume > 0:
            use_side, held = 'buy', short_volume
        else:
            return f'{symbol} 没有持仓'
        if held <= 0:
            return f'{symbol} 没有可平的{"多" if use_side == "sell" else "空"}头持仓'
        qty = max(1, min(int(volume or held), held))
        return self.insert(symbol, use_side, 'close', qty, 0)

    def reverse_symbol(self, symbol: str, volume: int = 0,
                       side: str = '') -> str:
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
        sides = self.position_sides(symbol)
        long_volume, short_volume = sides['long'], sides['short']
        wanted = str(side or '').strip()
        if wanted in ('多', 'long', '买'):
            close_side, opened, held = 'sell', 'buy', long_volume
        elif wanted in ('空', 'short', '卖'):
            close_side, opened, held = 'buy', 'sell', short_volume
        elif long_volume > 0 and short_volume > 0:
            return (f'{symbol} 处于锁仓（多 {long_volume} / 空 {short_volume}），'
                    '请在持仓行上右键指定反手多单还是空单 ✓')
        elif long_volume > 0:
            close_side, opened, held = 'sell', 'buy', long_volume
        elif short_volume > 0:
            close_side, opened, held = 'buy', 'sell', short_volume
        else:
            return f'{symbol} 没有持仓'
        if held <= 0:
            return f'{symbol} 没有可反手的持仓'
        qty = max(1, min(int(volume or held), held))
        # 反手 = 平掉这一边 + 反向开同样手数（两笔限价单 ✓）
        closed = self.insert(symbol, close_side, 'close', qty, 0)
        if _trade_failed(closed):
            return f'反手失败（平仓未成功）：{closed}'
        return f'{closed}；' + self.insert(symbol, opened, 'open', qty, 0)

    def _all_account_kwargs(self) -> List[Dict[str, Any]]:
        """多账户：**每个账户**各来一份 kwargs（全平要跨账户 ✓）

        没有多账户（或拿不到账户列表）→ 只有一份 `{}` ✓
        """
        view = None
        try:
            view = self.desk.account_view()
        except Exception:                                        # noqa: BLE001
            view = None
        if view is None:
            return [{}]
        try:
            items = list(view.instances() or [])
        except Exception:                                        # noqa: BLE001
            items = []
        if len(items) <= 1:
            return [{}]
        out: List[Dict[str, Any]] = []
        for item in items:
            try:
                out.append({'account': item})
            except Exception:                                    # noqa: BLE001
                continue
        return out or [{}]

    def _positions_all(self) -> List[Any]:
        """**所有账户**的持仓（全平 / 全部反手用 ✓）

        ⚠ 任何一步失败都退回 `_positions()`（单账户模型），
          不能因为"查账户列表"失败就把全平整体搞挂 ✗
        """
        rows: List[Any] = []
        seen = set()
        try:
            kwargs_list = self._all_account_kwargs()
        except Exception:                                        # noqa: BLE001
            kwargs_list = [{}]
        for kwargs in kwargs_list:
            if not kwargs:
                # ★ 单账户：直接用 `_positions()`（走 `get_position_list`，
                #   返回的行**带 instrument_id / exchange_id** ✓；
                #   只调 `get_position()` 的话是天勤的实体对象，字段名不一样 ✗）
                items = list(self._positions() or [])
                for item in items:
                    key = (position_symbol(item),
                           int(_num(_field_any(item, LONG_VOLUME)) or 0.0),
                           int(_num(_field_any(item, SHORT_VOLUME)) or 0.0))
                    if key[0] and key not in seen:
                        seen.add(key)
                        rows.append(item)
                continue
            try:
                api = self.api()
            except TypeError:
                api = self.api('')
            except Exception:                                    # noqa: BLE001
                api = None
            getter = getattr(api, 'get_position', None) if api is not None else None
            items: List[Any] = []
            if callable(getter):
                try:
                    items = _records(getter(**kwargs))
                except TypeError:
                    try:
                        items = _records(getter())
                    except Exception:                            # noqa: BLE001
                        items = []
                except Exception:                                # noqa: BLE001
                    items = []
            if not items:
                continue
            for item in items:
                key = (position_symbol(item),
                       int(_num(_field_any(item, LONG_VOLUME)) or 0.0),
                       int(_num(_field_any(item, SHORT_VOLUME)) or 0.0),
                       str(kwargs.get('account') or ''))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)
        return rows or self._positions()

    def _close_all(self, symbol: str = '') -> str:
        """**全平**：所有账户 / 所有合约的**多头 + 空头**逐笔平掉 ✓

        * 锁仓（同合约多空都有）也要两边各平一次（以前只平一边 ✗）；
        * 上期所 / 能源中心按平今 / 平昨拆单；
        * 全部走**对手价限价单**（这些交易所不支持市价单 ✓）
        """
        self._position_error = ''
        # ★ 只平**当前选中的账户**（用户 2026-11-05 明确要求；跨账户交给"全部账户"再切）
        #   `symbol` 决定用哪个账户 / 行情源（多布局每格独立 ✓）
        positions = self._positions_for(symbol)
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
            # ★ 锁仓：多头、空头**各平一次**（以前只平一边 ✗）
            for side, qty in (('sell', long_volume), ('buy', short_volume)):
                if qty <= 0:
                    continue
                text = self.insert(code, side, 'close', int(qty), 0)
                if _trade_failed(text):
                    failed.append(f'{code}: {text}')
                else:
                    done += 1
        label = self.account_label(symbol)
        if failed:
            return (f'{label} 全部平仓：成功 {done} 个，失败 {len(failed)} 个（'
                    + '；'.join(failed[:3]) + '）')
        return f'{label} 全部平仓：已按对手价平掉 {done} 笔持仓（多 / 空分开计算 ✓）'

    def order_snapshot(self, order_id: str, symbol: str = '') -> Dict[str, Any]:
        """查一笔委托的原始信息（改单窗口预填用 ✓）

        返回 ``{symbol, direction, offset, volume, left, price, status}``；
        `direction` 是 ``BUY`` / ``SELL``，`offset` 是 ``OPEN`` / ``CLOSE`` /
        ``CLOSETODAY``（界面不区分平今平昨时按"平"显示 ✓）。
        """
        api = self.api(symbol)
        getter = getattr(api, 'get_order', None) if api is not None else None
        if not callable(getter) or not order_id:
            return {}
        order = None
        try:
            order = getter(order_id, **self.account_kwargs(symbol))
        except TypeError:
            try:
                order = getter(order_id)
            except Exception:                                    # noqa: BLE001
                order = None
        except Exception:                                        # noqa: BLE001
            order = None
        if order is None:
            return {}
        left = _num(getattr(order, 'volume_left', None))
        return {
            'symbol': position_symbol(order) or str(symbol or ''),
            'direction': str(getattr(order, 'direction', '') or '').upper(),
            'offset': str(getattr(order, 'offset', '') or '').upper(),
            'volume': int(_num(getattr(order, 'volume_orign', None))
                          or _num(getattr(order, 'volume', None)) or 0),
            'left': int(left or 0),
            'price': _num(getattr(order, 'limit_price', None)),
            'status': str(getattr(order, 'status', '') or '').upper(),
        }

    def modify_order(self, symbol: str, order_id: str, volume: int,
                     price, direction: str = '', offset: str = '') -> str:
        """**改单** = 撤掉旧委托 + 用新价 / 新手数重新委托（同方向、同开平 ✓）

        快期「修改当前委托单」就是这两步（交易所没有真正的 modify 指令）。
        """
        symbol = str(symbol or '')
        order_id = str(order_id or '')
        if not symbol or not order_id:
            return '缺少委托号'
        snapshot = self.order_snapshot(order_id, symbol)
        side = str(direction or snapshot.get('direction') or '').upper()
        kind = str(offset or snapshot.get('offset') or '').upper()
        if not side or not kind:
            return '拿不到这笔委托的方向 / 开平，无法改单'
        try:
            volume = max(1, int(volume or 0))
        except (TypeError, ValueError):
            volume = 0
        if volume <= 0:
            return '手数要大于 0'
        # 1) 撤旧单
        cancelled = self.cancel_order(order_id, symbol)
        if _trade_failed(cancelled):
            return f'改单失败（撤旧单没成功）：{cancelled}'
        # 2) 按新价 / 新量重下（开平保持不变 ✓）
        side_key = 'buy' if side == 'BUY' else 'sell'
        offset_key = 'open' if kind == 'OPEN' else 'close'
        text = self.insert(symbol, side_key, offset_key, volume, price)
        if _trade_failed(text):
            return f'旧单已撤，但新单提交失败：{text}'
        label = '买' if side_key == 'buy' else '卖'
        label += '开' if offset_key == 'open' else '平'
        return f'已改单（{label} {volume} 手）：{cancelled}；{text}'

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
        """**"市价" = 对手价限价单** ✓

        上期所 / 中金所 / 能源中心 / 上交所 / 深交所**不支持市价单**
        （`limit_price=None` 会被拒：`不支持市价单，请使用 limit_price`
        — 用户实测 2026-11-05 ✗）。所以这里一律取对手价当限价 ✓
        """
        side = 'buy' if str(direction).upper() == 'BUY' else 'sell'
        kind = 'open' if str(offset).upper() == 'OPEN' else 'close'
        return self.insert(symbol, side, kind, int(volume), 0)

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
            self.desk.push_log(f'[撤单] {self.account_label(symbol)} '
                               f'{symbol or "全部"} 撤 {cancelled} 笔', 'warning')
            return f'已撤 {cancelled} 笔委托'
        return '没有可撤的委托'

    # ------------------------------------------------------------ 查询
    def _position(self, symbol: str):
        api = self.api(symbol)
        if api is None or not symbol:
            return None
        kwargs = self.account_kwargs(symbol)
        try:
            return api.get_position(symbol, **kwargs)
        except Exception:                                        # noqa: BLE001
            # 有些接口只认 `get_position()`（不给 symbol）→ 从全量里挑 ✓
            try:
                for item in _records(api.get_position(**kwargs)):
                    code = position_symbol(item)
                    if (code == symbol
                            or code.split('.')[-1] == symbol.split('.')[-1]):
                        return item
            except Exception:                                    # noqa: BLE001
                pass
            return None

    def _positions_for(self, symbol: str = ''):
        """`_positions(symbol)`（兼容旧签名 / 测试里 monkeypatch 的无参版本 ✓）"""
        try:
            return self._positions(symbol)
        except TypeError:
            return self._positions()

    def _positions(self, symbol: str = ''):
        """当前账户的持仓（`symbol` 决定用哪个行情源 / 账户 ✓）"""
        self._position_error = ''
        api = self.api(symbol) or self.api()
        if api is None:
            self._position_error = '没有交易接口'
            return []
        kwargs = self.account_kwargs(symbol)
        account = kwargs.get('account')
        lister = getattr(api, 'get_position_list', None)
        if callable(lister):
            items = None
            try:
                items = list(lister(**kwargs) or [])
            except TypeError:                                    # 旧签名
                try:
                    items = list(lister() or [])
                except Exception as error:                       # noqa: BLE001
                    self._position_error = str(error)
                    return []
            except Exception as error:                           # noqa: BLE001
                self._position_error = str(error)
                return []
            if account is not None and items:
                # ★ 多账户：只留**这个账户**的持仓（以前会连别的账户一起平 ✗）
                same = [item for item in items
                        if getattr(item, 'account', None) is account]
                if same:
                    return same
            return items or []
        try:
            return _records(api.get_position(**kwargs))
        except Exception as error:                               # noqa: BLE001
            self._position_error = str(error)
            return []


def _price_text(value, digits: int = 2) -> str:
    """价格 → 字符串（按合约小数位，带千分位 ✓）"""
    number = _num(value)
    if number is None:
        return '--'
    return f'{number:,.{max(0, int(digits))}f}'
