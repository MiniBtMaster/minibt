"""底部「交易账户」面板的数据层：11 张指标卡 + 4 张表 + 多账户。

与 miniqt 的 `sim_account_panel.py` 对齐：

* 指标卡：静态权益 / 账户权益 / 持仓盈亏 / 平仓盈亏 / 浮动盈亏 / 手续费 /
  占用保证金 / 冻结保证金 / 冻结手续费 / 可用资金 / 资金使用率
* 子表：持仓 / 委托 / 成交记录 / 未成委托
* 多账户：期货 ``TqMultiAccount._account_list``；股票 ``StockApi`` 只有 1 个

只做**读**（下单/平反全在 P4 的 `trading.py`）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .stocks import display_symbol

#: 指标卡（key, 标题, 是否百分比）
ACCOUNT_FIELDS = (
    ('pre_balance', '静态权益', False),
    ('balance', '账户权益', False),
    ('position_profit', '持仓盈亏', False),
    ('close_profit', '平仓盈亏', False),
    ('float_profit', '浮动盈亏', False),
    ('commission', '手续费', False),
    ('margin', '占用保证金', False),
    ('frozen_margin', '冻结保证金', False),
    ('frozen_commission', '冻结手续费', False),
    ('available', '可用资金', False),
    ('risk_ratio', '资金使用率', True),
)

#: 天勤 Position 的多空字段别名（新老版本不一样 ✓）
LONG_VOLUME = ('pos_long', 'volume_long')
SHORT_VOLUME = ('pos_short', 'volume_short')
LONG_TODAY = ('pos_long_today', 'volume_long_today')
SHORT_TODAY = ('pos_short_today', 'volume_short_today')
LONG_AVG = ('open_price_long', 'position_price_long')
SHORT_AVG = ('open_price_short', 'position_price_short')
LONG_PRICE = ('position_price_long', 'open_price_long')
SHORT_PRICE = ('position_price_short', 'open_price_short')
LONG_PROFIT = ('float_profit_long', 'position_profit_long')
SHORT_PROFIT = ('float_profit_short', 'position_profit_short')
#: 持仓市值 / 占用保证金（期货用 *long* / *short*，股票没有这两个字段 ✓）
LONG_VALUE = ('market_value_long',)
SHORT_VALUE = ('market_value_short',)
LONG_MARGIN = ('margin_long',)
SHORT_MARGIN = ('margin_short',)

POSITION_COLUMNS = ('合约', '买卖', '总仓', '可用', '开仓价', '持仓均价',
                    '浮动盈亏', '持仓市值', '占用保证金')
ORDER_COLUMNS = ('委托合约', '买卖', '开平', '手数', '未成交', '报单价',
                 '挂单状态', '成交价', '报单时间')
TRADE_COLUMNS = ('成交合约', '买卖', '开平', '成交价', '手数', '手续费',
                 '成交时间')


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


def position_symbol(item) -> str:
    """持仓 / 委托 / 成交记录 → **完整合约代码**（带交易所 ✓）

    ⚠ 天勤 ``get_position_list()`` / ``get_order()`` 里的 ``instrument_id``
    只有 ``ag2612``（**没有交易所**）：

    * 表格里显示 ``ag2612`` 和行情表的 ``SHFE.ag2612`` 对不上；
    * 右键「平 / 反」发上去的是裸代码 → 下单 / 调仓都会失败 ✗；
    * ``decimals_of('ag2612')`` → ``get_quote('ag2612')`` → 天勤合约服务报
      ``contains non-existent instrument``，把行情泵打断 ✗。

    所以统一用 ``exchange_id`` 拼成 ``SHFE.ag2612``（股票走 ``display_symbol``）✓
    """
    code = str(_field(item, 'instrument_id') or
               _field(item, 'symbol') or '').strip()
    if not code:
        return ''
    exchange = str(_field(item, 'exchange_id') or '').strip()
    if '.' not in code and exchange:
        return f'{exchange}.{code}'
    return display_symbol(code)


def record_rows(source) -> list:
    """``get_position`` / ``get_order`` / ``get_trade`` 的返回值统一成 list ✓

    ⚠ **天勤 `tqsdk.objs.Entity` 不是 dict 子类**（只有
    ``__getitem__`` / ``__iter__`` / ``__len__``，迭代它拿到的是 **key**），
    以前走到最后 ``return [source]`` → 整批记录被当成「一条」→ 字段全取不到
    → **金额卡片有数、持仓/委托/成交表永远空** ✗
    （用户实测：天勤模拟账户明明有多单，desk 持仓表却是空的）。

    现在和 miniqt 的 `sim_account_panel._rows()` 完全一致：
    DataFrame → dict → list → **Entity 按字符串 key 逐个取值** ✓
    """
    if source is None:
        return []
    # ① pandas DataFrame（`get_position()` 不带参数时就是它）
    if hasattr(source, 'to_dict') and hasattr(source, 'columns'):
        try:
            return list(source.to_dict('records'))
        except Exception:                                        # noqa: BLE001
            return []
    if isinstance(source, dict):
        return list(source.values())
    if isinstance(source, (list, tuple, set)):
        return list(source)
    # ② tqsdk Entity：只认「字符串 key」，别误伤字符串 / 数组 ✓
    if hasattr(source, '__getitem__') and hasattr(source, '__len__'):
        try:
            keys = [key for key in source
                    if isinstance(key, str) and not key.startswith('_')]
        except Exception:                                        # noqa: BLE001
            keys = []
        rows = []
        for key in keys:
            try:
                rows.append(source[key])
            except Exception:                                    # noqa: BLE001
                continue
        if rows:
            return rows
    return [source]


#: 老名字（本模块 / `trading.py` 都用它 ✓）
_records = record_rows


def _money(value, digits: int = 2) -> str:
    number = _num(value)
    return '--' if number is None else f'{number:,.{digits}f}'


def _int(value) -> str:
    number = _num(value)
    return '--' if number is None else f'{int(number)}'


def _dir(value) -> str:
    text = str(value or '').upper()
    return {'BUY': '买', 'SELL': '卖', 'LONG': '买', 'SHORT': '卖'}.get(text, text)


def _offset(value) -> str:
    text = str(value or '').upper()
    return {'OPEN': '开', 'CLOSE': '平', 'CLOSETODAY': '平今',
            'CLOSEYESTERDAY': '平昨'}.get(text, text)


def _status(value) -> str:
    text = str(value or '').upper()
    return {'ALIVE': '有效', 'FINISHED': '已完成', 'PENDING': '待报',
            'OPEN': '有效', 'DELETED': '已撤'}.get(text, text)


def _clock(value) -> str:
    """时间 → ``HH:MM:SS``（天勤给的是 ``2026-10-19 10:02:11.123`` ✓）

    以前无条件取末 8 位 → ``:11.123``（用户看到的成交时间就是这个 ✗）
    """
    text = str(value or '').strip()
    if not text:
        return ''
    inside = text.split(' ')[-1]                  # 去掉日期部分 ✓
    inside = inside.split('.')[0]                 # 去掉毫秒 ✓
    if ':' in inside:
        return inside[-8:].rjust(8, '0') if len(inside) < 8 else inside[-8:]
    return text[-8:]


class AccountView:
    """一个账户面板的**只读**视图（多账户可切换 ✓）"""

    def __init__(self, desk):
        self.desk = desk
        #: 当前选中的账户下标（0 = 第一个；股票恒为 0）
        self.index = 0

    # ------------------------------------------------------------ 账户
    def api(self, symbol: str = ''):
        """账户面板用的 api —— 跟着**合约 / 打开的看盘 tab** 走 ✓

        以前用 `current_feed()`（报价页筛选）→ 报价页停在「股票」时，
        底部面板显示的是**股票账户**，而实际下单可能在天勤（或反过来），
        用户会看到“成交了但没持仓”✗
        """
        getter = getattr(self.desk, 'feed_of', None)
        feed = getter(symbol) if callable(getter) else self.desk.current_feed()
        return getattr(feed, 'api', None) if feed is not None else None

    def instances(self, symbol: str = '') -> List[Any]:
        api = self.api(symbol)
        account = getattr(api, '_account', None)
        if account is None:
            return []
        items = list(getattr(account, '_account_list', None) or [])
        return items or [account]

    def labels(self, symbol: str = '') -> List[str]:
        labels = []
        for item in self.instances(symbol):
            broker = str(_field(item, 'broker_id', '') or '')
            code = str(_field(item, 'account_id', '') or '')
            name = type(item).__name__
            if broker or code:
                labels.append(f'{broker}/{code}' if broker and code else
                              (broker or code))
            else:
                labels.append('快期模拟' if ('Kq' in name or 'Sim' in name)
                              else name)
        return labels

    def current(self):
        items = self.instances()
        if not items:
            return None
        self.index = max(0, min(int(self.index), len(items) - 1))
        return items[self.index]

    def switch(self, index) -> None:
        items = self.instances()
        if items:
            self.index = max(0, min(int(index), len(items) - 1))

    def account_kwargs(self, symbol: str = '') -> Dict[str, Any]:
        """多账户时下游调用都要带 ``account=`` ✓"""
        items = self.instances(symbol)
        if len(items) <= 1:
            return {}
        return {'account': self.current()}

    # ------------------------------------------------------------ 快照
    def summary(self, symbol: str = '') -> Dict[str, Any]:
        api = self.api(symbol)
        account = self.current()
        if api is None:
            return {}
        try:
            if account is not None:
                acc = api.get_account(account=account)
            else:
                acc = api.get_account()
        except TypeError:                            # 老签名不接 account=
            try:
                acc = api.get_account()
            except Exception:                                    # noqa: BLE001
                return {}
        except Exception:                                        # noqa: BLE001
            return {}
        if acc is None:
            return {}
        # 股票 / 期货按**这个合约所属的行情源**判断（不是报价页筛选 ✗）
        getter = getattr(self.desk, 'feed_of', None)
        feed = getter(symbol) if callable(getter) else None
        if feed is None and hasattr(self.desk, 'current_feed'):
            feed = self.desk.current_feed()
        is_stock = (getattr(feed, 'kind', '') == 'stocks'
                    or type(api).__name__ == 'StockApi')
        values: Dict[str, Any] = {}
        for key, _title, percent in ACCOUNT_FIELDS:
            value = _num(_field(acc, key))
            values[key] = value
        if is_stock:
            # 股票：保证金 → 市值；没有冻结字段 → None（前端显示 -- ✓）
            values['margin'] = _num(_field(acc, 'market_value'))
            values['frozen_margin'] = None
            values['frozen_commission'] = None
            values['pre_balance'] = values.get('pre_balance')
        labels = self.labels(symbol)
        return {
            'type': 'account',
            'kind': 'stock' if is_stock else 'futures',
            'index': int(self.index),
            'labels': labels,
            'label': labels[self.index] if labels else '',
            'values': values,
            'fields': [{'key': key, 'title': title, 'percent': percent}
                       for key, title, percent in ACCOUNT_FIELDS],
        }

    def decimals_of(self, symbol: str) -> int:
        """合约小数位（走 `Desk.decimals_of`，和报价页/买卖盘同一套 ✓）"""
        getter = getattr(self.desk, 'decimals_of', None)
        if callable(getter):
            try:
                return int(getter(symbol))
            except Exception:                                    # noqa: BLE001
                pass
        return 2

    # ------------------------------------------------------------ 明细
    def tables(self, limit: int = 100, symbol: str = '') -> Dict[str, Any]:
        api = self.api(symbol)
        if api is None:
            return {}
        kwargs = self.account_kwargs(symbol)
        return {
            'positions': self._positions(api, kwargs, limit),
            'orders': self._orders(api, kwargs, limit, alive_only=False),
            'unfilled': self._orders(api, kwargs, limit, alive_only=True),
            'trades': self._trades(api, kwargs, limit),
        }

    def _positions(self, api, kwargs, limit: int) -> Dict[str, Any]:
        lister = getattr(api, 'get_position_list', None)
        items = []
        if callable(lister):
            try:
                items = list(lister() or [])
            except Exception:                                    # noqa: BLE001
                items = []
        if not items:
            try:
                items = _records(api.get_position(**kwargs))
            except Exception:                                    # noqa: BLE001
                items = []
        rows = []
        raw: List[Dict[str, Any]] = []
        for item in items:
            code = position_symbol(item)
            for side, volumes, opens, prices, profits, values, margins in (
                    ('买', LONG_VOLUME, LONG_AVG, LONG_PRICE, LONG_PROFIT,
                     LONG_VALUE, LONG_MARGIN),
                    ('卖', SHORT_VOLUME, SHORT_AVG, SHORT_PRICE, SHORT_PROFIT,
                     SHORT_VALUE, SHORT_MARGIN)):
                volume = _num(_field_any(item, volumes)) or 0.0
                if volume <= 0:
                    continue
                digits = self.decimals_of(code)
                # 开仓价 / 持仓均价分开取（当日有成交会被摊平，两者不同 ✓）
                open_price = _num(_field_any(item, opens))
                avg = _num(_field_any(item, prices)) or open_price
                value = _num(_field_any(item, values))
                margin = _num(_field_any(item, margins))
                rows.append([
                    code, side, _int(volume),
                    _int(_field_any(item, LONG_TODAY if side == '买'
                                    else SHORT_TODAY)),
                    _money(open_price, digits), _money(avg, digits),
                    _money(_field_any(item, profits)),
                    _money(value if value is not None
                           else volume * (avg or 0.0)),
                    _money(margin if margin is not None
                           else _field(item, 'margin')),
                ])
                raw.append({'symbol': code,
                            'side': '多' if side == '买' else '空',
                            'volume': int(volume), 'avg': avg,
                            'profit': _num(_field_any(item, profits))})
        return {'columns': list(POSITION_COLUMNS), 'rows': rows[:limit],
                'raw': raw[:limit],
                'total': len(rows), 'limit': limit}

    def _orders(self, api, kwargs, limit: int, alive_only: bool) -> Dict[str, Any]:
        try:
            items = _records(api.get_order(**kwargs))
        except Exception:                                        # noqa: BLE001
            items = []
        rows = []
        raw: List[Dict[str, Any]] = []
        for item in items:
            left = _num(_field(item, 'volume_left'))
            status_text = str(_field(item, 'status') or '').upper()
            alive = status_text in ('ALIVE', 'PENDING', 'OPEN') or bool(
                left and left > 0) if status_text not in (
                    'FINISHED', 'DELETED') else False
            if alive_only and not alive:
                continue
            code = position_symbol(item)
            digits = self.decimals_of(code)
            volume = _int(_field(item, 'volume_orign')
                          or _field(item, 'volume'))
            rows.append([
                code,
                _dir(_field(item, 'direction')),
                _offset(_field(item, 'offset')),
                volume,
                _int(_field(item, 'volume_left')),
                _money(_field(item, 'limit_price'), digits),
                _status(_field(item, 'status')),
                _money(_field(item, 'trade_price'), digits),
                _clock(_field(item, 'insert_date_time') or
                       _field(item, 'created_at')),
            ])
            raw.append({
                'symbol': code,
                'side': _dir(_field(item, 'direction')),
                'offset': _offset(_field(item, 'offset')),
                'volume': volume,
                'left': int(left or 0),
                'price': _num(_field(item, 'limit_price')),
                'status': _status(_field(item, 'status')),
                'alive': bool(alive),
                'order_id': str(_field(item, 'order_id') or ''),
            })
        return {'columns': list(ORDER_COLUMNS), 'rows': rows[:limit],
                'raw': raw[:limit],
                'total': len(rows), 'limit': limit}

    def pending_orders(self, symbol: str = '') -> List[Dict[str, Any]]:
        """未成交委托（挂单线用 ✓）

        天勤的 ``get_order`` 里 ``status`` 是 ``ALIVE`` 的才算挂单；
        返回**原始数值**（前端要按价格画线，不能用预格式化字符串 ✗）。
        """
        api = self.api(symbol)
        if api is None:
            return []
        kwargs = self.account_kwargs(symbol)
        getter = getattr(api, 'get_order', None)
        if not callable(getter):
            return []
        try:
            items = _records(getter(**kwargs))
        except Exception:                                        # noqa: BLE001
            return []
        want = display_symbol(symbol) if symbol else ''
        # ★ 主连（`KQ.m@SHFE.rb`）→ 也认它对应的真实合约（`SHFE.rb2610`）✓
        alternatives = {want}
        if want.startswith('KQ.m@'):
            alternatives.add(want.split('@', 1)[1])
        alternatives = {item.upper() for item in alternatives if item}

        def matches(code: str) -> bool:
            if not alternatives:
                return True
            upper = code.upper()
            if upper in alternatives:
                return True
            # 也接受「不带交易所」的写法（rb2610 / SHFE.rb2610 ✓）
            bare = upper.split('.')[-1]
            return any(item.split('.')[-1] == bare for item in alternatives)

        out: List[Dict[str, Any]] = []
        for item in items:
            status = str(_field(item, 'status') or '').upper()
            if status in ('FINISHED', 'DELETED', 'CANCELLED', 'CANCELED'):
                continue
            left = _num(_field(item, 'volume_left'))
            alive = status in ('ALIVE', 'PENDING', 'OPEN')
            # 状态不标准时：还有未成交手数也算挂单 ✓
            if not alive and not (left and left > 0):
                continue
            code = position_symbol(item)
            if not matches(code):
                continue
            price = _num(_field(item, 'limit_price')) or 0.0
            if price <= 0:
                continue
            qty = left
            if not qty or qty <= 0:
                qty = _num(_field(item, 'volume_orign')) or                     _num(_field(item, 'volume')) or 0.0
            if qty <= 0:
                continue
            out.append({
                'id': str(_field(item, 'order_id') or ''),
                'symbol': code,
                'price': float(price),
                'side': _dir(_field(item, 'direction')) or '买',
                'offset': _offset(_field(item, 'offset')) or '开',
                'qty': float(qty),
                'status': '挂单',
            })
        return out

    def _trades(self, api, kwargs, limit: int) -> Dict[str, Any]:
        try:
            items = _records(api.get_trade(**kwargs))
        except Exception:                                        # noqa: BLE001
            items = []
        rows = []
        for item in reversed(items):
            code = position_symbol(item)
            digits = self.decimals_of(code)
            rows.append([
                code,
                _dir(_field(item, 'direction')),
                _offset(_field(item, 'offset')),
                _money(_field(item, 'price'), digits),
                _int(_field(item, 'volume')),
                _money(_field(item, 'commission')),
                _clock(_field(item, 'trade_date_time') or
                       _field(item, 'created_at')),
            ])
        return {'columns': list(TRADE_COLUMNS), 'rows': rows[:limit],
                'total': len(rows), 'limit': limit}

    # ------------------------------------------------------------ 一起推
    def payload(self, limit: int = 100, symbol: str = '') -> Dict[str, Any]:
        payload = self.summary(symbol)
        if not payload:
            return {'type': 'account', 'empty': True}
        payload['tables'] = self.tables(limit, symbol)
        return payload
