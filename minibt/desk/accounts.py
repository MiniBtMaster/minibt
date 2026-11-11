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
# ★ 天勤里这两个**不是**一回事（用户实测 SHFE.ag2612 2026-11-03 ✗）：
#   - `open_price_*`    = 今仓开仓均价；
#   - `position_price_*`= 持仓均价（**真实成本**，`float_profit_*` 就是按它算的）。
#   以前「持仓均价」先取 `open_price_*` → 显示 11,780.33，而浮动盈亏是
#   -(24,195)（按 11,210.33 算的）→ 用户看到「成本 11780、现价 11748 却亏 2.4 万」
#   这种**自相矛盾**的数字 ✗
LONG_AVG = ('position_price_long', 'open_price_long')
SHORT_AVG = ('position_price_short', 'open_price_short')
LONG_PRICE = ('open_price_long', 'position_price_long')
SHORT_PRICE = ('open_price_short', 'position_price_short')
LONG_PROFIT = ('float_profit_long', 'position_profit_long')
SHORT_PROFIT = ('float_profit_short', 'position_profit_short')
#: 持仓市值 / 占用保证金（期货用 *long* / *short*，股票没有这两个字段 ✓）
LONG_VALUE = ('market_value_long',)
SHORT_VALUE = ('market_value_short',)
LONG_MARGIN = ('margin_long', 'margin')
SHORT_MARGIN = ('margin_short', 'margin')
#: 合约乘数 / 最新价（持仓市值、盈亏兜底都要用 ✓）
VOLUME_MULTIPLE = ('volume_multiple',)
LAST_PRICE = ('last_price',)

POSITION_COLUMNS = ('合约', '买卖', '总仓', '可用', '开仓价', '持仓均价',
                    '浮动盈亏', '持仓市值', '占用保证金')
ORDER_COLUMNS = ('委托合约', '买卖', '开平', '手数', '未成交', '报单价',
                 '挂单状态', '成交价', '报单时间')
TRADE_COLUMNS = ('成交合约', '买卖', '开平', '成交价', '手数', '手续费',
                 '成交时间')


def _num(value) -> Optional[float]:
    """转数字；`None` / 非数字 / **NaN / inf** 都算"没数据" ✓

    天勤持仓里 `market_value_long` 之类字段在期货上常常是 `nan`，
    以前 `float(nan)` 原样返回 → 表格里直接印出 `nan` ✗（用户实测 ag2612）
    """
    import math
    try:
        number = None if value is None else float(value)
    except (TypeError, ValueError):
        return None
    if number is None or math.isnan(number) or math.isinf(number):
        return None
    return number


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


def position_cost(item, volume: float, avg_keys, profit_keys,
                  side: str = '多') -> tuple:
    """``(持仓均价, 浮动盈亏)`` —— 保证两者**互相自洽** ✓

    用户 2026-11-03（SHFE.ag2612）：表里「持仓均价」显示 11,780.33、
    浮动盈亏 -24,195，看着"矛盾"；但**快期（券商终端）的持仓表同样显示
    开仓均价 11,780.3、亏损 -30,495**（当时最新价 12,458：
    `(11780.3 − 12458) × 15 × 3 ≈ −30,495`）→ 说明券商的成本价就是 11,780.33，
    **盈亏是对的**，不要拿盈亏去"改写"成本价 ✗（以前试过反推，反而把
    11,780.33 改成 11,210.33，和快期对不上 ✗）。

    **期货是当日无负债结算**（用户 2026-11-03 说明 ✓）：隔夜持仓每天收盘后
    按结算价把盈亏划走、成本价重算成结算价 —— 这正是天勤 `position_price_*`
    的口径。所以：

    1. 成本价取 `position_price_*`（结算后的持仓成本），没有再退 `open_price_*`；
    2. 盈亏取 `float_profit_*`（按最新价）→ `position_profit_*`；
    3. 只有**没有**盈亏字段时才用成本价 × 最新价算一个 —— 有就一律**直接引用
       天勤账户的数据**，desk 不做任何"修正"（拿盈亏反推成本价会和券商对不上 ✗）。
    """
    avg = _num(_field_any(item, avg_keys))
    profit = _num(_field_any(item, profit_keys))
    mult = _num(_field_any(item, VOLUME_MULTIPLE)) or 0.0
    last = _num(_field_any(item, LAST_PRICE))
    short = str(side or '多') == '空'
    unit = mult * float(volume or 0.0)
    if profit is None and avg and unit and last:
        # 没有盈亏字段才自己算（有就以券商 / 天勤给的为准 ✓）
        profit = ((avg - last) if short else (last - avg)) * unit
    return avg, profit


def position_value(item, volume: float, avg: Optional[float]) -> Optional[float]:
    """持仓市值：优先 `market_value_*`，没有（期货常给 NaN）就自己算 ✓

    以前直接 `volume × 均价`（期货少了乘数）+ NaN 原样打印 → 表格里一个
    大大的 `nan` ✗（用户实测 ag2612）
    """
    value = _num(_field_any(item, LONG_VALUE + SHORT_VALUE))
    if value is not None:
        return value
    mult = _num(_field_any(item, VOLUME_MULTIPLE))
    last = _num(_field_any(item, LAST_PRICE))
    if volume and mult and last:
        return float(volume) * mult * last
    price = avg or last
    if volume and price:
        return float(volume) * price
    return None


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
    def api(self, symbol: str = '', key: str = ''):
        """账户面板用的 api —— 跟着**合约 / 这一页的账户**走 ✓

        以前用 `current_feed()`（报价页筛选）→ 报价页停在「股票」时，
        底部面板显示的是**股票账户**，而实际下单可能在天勤（或反过来），
        用户会看到“成交了但没持仓”✗

        ★ 2026-11-05：多布局 / 每页独立账户后，`key` 优先——
          否则股票格的账户数据会走期货 api（取到模拟账户的 861,741 ✗）
        """
        # ⚠ **不能**在这里问 `desk.account_key_for()`：
        #   它会走 `home_key()` → `_verified_account_key()` → `account_view()`
        #   → `identities()` → `api()` → **无限递归 → 界面卡死 / 账户信息消失** ✗
        #   需要按页取账户的调用方（`account_payload` / `Trading`）自己把 key 传进来 ✓
        kind = str(key or '')
        if not kind:
            #   ⚠ 直接读字段（不能调 `active_account_key()`：它会再问 catalog，
            #      catalog 又问 identities → 无限递归 ✗）
            kind = str(getattr(self.desk, '_account_kind', '') or '')
        if kind == 'futu':
            stocks = getattr(self.desk, 'stocks', None)
            return getattr(stocks, 'api', None) if stocks is not None else None
        if kind in ('kq', 'real'):
            futures = getattr(self.desk, 'futures', None)
            api = getattr(futures, 'api', None) if futures is not None else None
            return api
        getter = getattr(self.desk, 'feed_of', None)
        feed = getter(symbol) if callable(getter) else self.desk.current_feed()
        return getattr(feed, 'api', None) if feed is not None else None

    def _api_of(self, symbol: str = '', key: str = ''):
        """兼容旧签名：`api(symbol)`（测试 / 扩展会 monkeypatch 单参数 ✓）"""
        try:
            return self.api(symbol, key)
        except TypeError:
            return self.api(symbol)

    def instances(self, symbol: str = '', key: str = '') -> List[Any]:
        api = self._api_of(symbol, key)
        account = getattr(api, '_account', None)
        if account is None:
            # 股票（富途）没有 `_account`：把 api 自己当唯一账户 ✓
            return [api] if api is not None else []
        items = list(getattr(account, '_account_list', None) or [])
        return items or [account]

    def labels(self, symbol: str = '') -> List[str]:
        # ★ 统一账户：当前是「富途模拟」→ 只有一个股票账户 ✓
        if str(getattr(self.desk, '_account_kind', '') or '') == 'futu':
            return ['富途模拟']
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

    @staticmethod
    def identity_of(item) -> str:
        """账户身份串：``sim`` / ``real:期货公司:资金账号`` ✓

        重连后 `_account_list` 的**下标可能变**，靠身份才找得回来 ✓
        """
        if item is None:
            return ''
        broker = str(_field(item, 'broker_id', '') or '')
        code = str(_field(item, 'account_id', '') or '')
        if broker or code:
            return f'real:{broker}:{code}'
        # ★ 没有期货公司 / 资金账号 = **模拟类账户**（`TqKq` / `TqSim` …）✓
        return 'sim'

    def identities(self, symbol: str = '', key: str = '') -> List[str]:
        """每个账户的身份串（和 `labels()` 一一对应 ✓）"""
        return [self.identity_of(item)
                for item in self.instances(symbol, key)]

    def index_of(self, identity: str, symbol: str = '') -> int:
        """按身份找下标（找不到 → 0）✓"""
        try:
            return max(0, self.identities(symbol).index(str(identity)))
        except ValueError:
            return 0

    def switch_identity(self, identity: str) -> None:
        """按**身份**切换账户（重连后用 ✓）"""
        self.switch(self.index_of(identity))

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

    def instance_for(self, key: str = '', symbol: str = ''):
        """按账户 key（``kq`` / ``real`` / ``futu``）取实例 ✓

        用户 2026-11-05：首页 / 每个实时图表页的账户切换要**各自独立**
        → 读数据不能再靠全局 `self.index`，而是按页面的 key 显式取 ✓
        """
        key = str(key or '').lower()
        items = self.instances(symbol, key)
        if not items:
            return None
        if key in ('kq', 'sim'):
            for item in items:
                if not str(_field(item, 'broker_id', '') or ''):
                    return item
            return items[0]
        if key == 'real':
            for item in items:
                if str(_field(item, 'broker_id', '') or ''):
                    return item
            return items[0]
        if key == 'futu':
            return items[0]
        return self.current()

    def index_for_key(self, key: str = '', symbol: str = '') -> int:
        """key → 账户下标（给 `index` / `label` 用 ✓）"""
        target = self.instance_for(key, symbol)
        try:
            items = self.instances(symbol, key)
            if target is not None and target in items:
                return items.index(target)
        except Exception:                                        # noqa: BLE001
            pass
        return 0

    def account_kwargs(self, symbol: str = '', key: str = '') -> Dict[str, Any]:
        """多账户时下游调用都要带 ``account=``（按 key 取 ✓）"""
        items = self.instances(symbol, key)
        if not items:
            return {}
        account = self.instance_for(key, symbol)
        if len(items) <= 1 and not key:
            return {}
        return {'account': account}

    # ------------------------------------------------------------ 快照
    def summary(self, symbol: str = '', key: str = '') -> Dict[str, Any]:
        # ⚠ `key` 后面会被 `for key, _title, percent in ACCOUNT_FIELDS` 覆盖 →
        #   先存一份，否则 `payload['key']` 变成最后一个字段名（'risk_ratio' ✗）
        payload_key = str(key or '')
        index_hint = 0
        api = self._api_of(symbol, key)
        account = self.instance_for(key, symbol)
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
        index = (self.index_for_key(payload_key, symbol) if payload_key
                 else int(self.index))
        return {
            'type': 'account',
            'kind': 'stock' if is_stock else 'futures',
            'index': int(index),
            'key': payload_key,
            'labels': labels,
            'label': labels[index] if labels else '',
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
    def tables(self, limit: int = 100, symbol: str = '',
               key: str = '') -> Dict[str, Any]:
        api = self._api_of(symbol, key)
        if api is None:
            return {}
        kwargs = self.account_kwargs(symbol, key)
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
            # 参数顺序：开仓价键（`open_price_*`）、持仓均价键（`position_price_*`）
            for side, volumes, opens, prices, profits, values, margins in (
                    ('买', LONG_VOLUME, LONG_PRICE, LONG_AVG, LONG_PROFIT,
                     LONG_VALUE, LONG_MARGIN),
                    ('卖', SHORT_VOLUME, SHORT_PRICE, SHORT_AVG, SHORT_PROFIT,
                     SHORT_VALUE, SHORT_MARGIN)):
                volume = _num(_field_any(item, volumes)) or 0.0
                if volume <= 0:
                    continue
                digits = self.decimals_of(code)
                # 开仓价 = 今仓开仓均价；持仓均价 = **真实成本**（和盈亏对齐 ✓）
                open_price = _num(_field_any(item, opens))
                avg, profit = position_cost(
                    item, volume, prices, profits,
                    '空' if side == '卖' else '多')
                if avg is None:
                    avg = open_price
                value = position_value(item, volume, avg)
                margin = _num(_field_any(item, margins))
                rows.append([
                    code, side, _int(volume),
                    _int(_field_any(item, LONG_TODAY if side == '买'
                                    else SHORT_TODAY)),
                    _money(open_price, digits), _money(avg, digits),
                    _money(profit),
                    _money(value),
                    _money(margin if margin is not None
                           else _field(item, 'margin')),
                ])
                raw.append({'symbol': code,
                            'side': '多' if side == '买' else '空',
                            'volume': int(volume), 'avg': avg,
                            'profit': profit})
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
    def payload(self, limit: int = 100, symbol: str = '',
                key: str = '') -> Dict[str, Any]:
        payload = self.summary(symbol, key)
        if not payload:
            return {'type': 'account', 'empty': True}
        payload['tables'] = self.tables(limit, symbol, key)
        # ★ 实盘标记：持仓行右键「平 / 反 / 全」要弹二次确认（用户要求 ✓）
        try:
            payload['real'] = self.is_real(symbol, key)
        except Exception:                                        # noqa: BLE001
            payload['real'] = False
        return payload

    def is_real(self, symbol: str = '', key: str = '') -> bool:
        """这个账户是不是**实盘**（有 broker_id / 股票实盘交易）✓"""
        try:
            account = self.instance_for(key, symbol)
        except Exception:                                        # noqa: BLE001
            account = None
        broker = str(_field(account, 'broker_id', '') or '')
        if broker:
            return True
        feed = self._api_of(symbol, key)
        if not feed or getattr(feed, '_trd', None) is None:
            return False
        env = str(getattr(feed, '_trd_env', '') or '').upper()
        return env.endswith('REAL')
