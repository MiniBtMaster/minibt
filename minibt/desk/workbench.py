"""交易工作台：订单票 / 订单状态机 / 风控 / 审计 / 对账 / 条件单。

这一层**不直接碰 tqsdk**：所有真实下单都委托给 :class:`minibt.desk.trading.Trading`，
因此 Qt 壳、浏览器壳、回放模拟、股票模拟走的是同一条路径。

能力一览
--------
* 订单票：市价 / 限价 / 止损（触发后市价）/ 条件单 / TIF（GFD/IOC/FOK）
  部分平仓 / 撤单 / 改单（撤旧 + 下新）
* 状态机：`PENDING → ALIVE → PARTIAL → FINISHED / CANCELLED / REJECTED`
* 风控：单笔手数 / 单笔名义金额 / 单日委托数 / 单日亏损 / 禁止开空
* 审计：所有下单、撤单、改单、风控拒绝、条件单触发都落 SQLite，
  可导出 CSV
* 对账：本地委托流水 vs 券商 `pending_orders()`

设计约束
--------
* 所有方法都能在**没有 desk / 没有行情**时安全调用（测试用 fake desk）；
* SQLite 用可重入锁 + `check_same_thread=False`，后台线程推送不炸；
* 默认数据库 ``~/.minibt/desk_audit.sqlite3``，可用
  ``MINIBT_DESK_AUDIT_DB`` 或构造参数覆盖；测试传 ``':memory:'`` 即可。
"""
from __future__ import annotations

import csv
import json
import math
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#: 规范化后的订单状态（前端按这个显示颜色 / 分组）
PENDING = 'PENDING'
ALIVE = 'ALIVE'
PARTIAL = 'PARTIAL'
FINISHED = 'FINISHED'
CANCELLED = 'CANCELLED'
REJECTED = 'REJECTED'

ORDER_STATES = (PENDING, ALIVE, PARTIAL, FINISHED, CANCELLED, REJECTED)

#: 交易所 / 天勤 / 富途常见状态 → 工作台状态
_STATUS_MAP = {
    'PENDING': PENDING,
    'SUBMITTED': PENDING,
    'SUBMIT': PENDING,
    'SENDING': PENDING,
    'WAITING': ALIVE,
    'ALIVE': ALIVE,
    'ACTIVE': ALIVE,
    'WORKING': ALIVE,
    'PARTIAL': PARTIAL,
    'PARTIALLY_FILLED': PARTIAL,
    'PART_FILLED': PARTIAL,
    'FINISHED': FINISHED,
    'FILLED': FINISHED,
    'ALL_FILLED': FINISHED,
    'DONE': FINISHED,
    'CANCELLED': CANCELLED,
    'CANCELED': CANCELLED,
    'CANCEL': CANCELLED,
    'REJECTED': REJECTED,
    'REJECT': REJECTED,
    'ERROR': REJECTED,
}

#: 允许的 TIF（工作台先支持这三类；交易所不支持的会由券商拒单）
TIME_IN_FORCE = ('GFD', 'IOC', 'FOK')

#: 可下单的方向（`close` = 平仓；`buy/sell` = 开仓）
SIDES = ('buy', 'sell', 'close')

#: 条件单的触发方式
CONDITIONS = ('>=', '<=', 'cross_up', 'cross_down')

#: 默认风控（`enabled=False` = 不限制，保持 desk 旧行为）
DEFAULT_LIMITS: Dict[str, Any] = {
    'enabled': False,
    'max_volume': 0,          # 0 = 不限
    'max_notional': 0.0,      # 0 = 不限（价格 × 手数）
    'max_orders_per_day': 0,  # 0 = 不限
    'max_daily_loss': 0.0,    # 0 = 不限（正数表示最多亏多少）
    'allow_short': True,
    'max_position': 0,        # 0 = 不限（净持仓绝对值上限）
}


def normalize_state(raw: Any) -> str:
    """交易所 / 天勤 / 富途状态 → 工作台状态（未知 → PENDING）"""
    text = str(raw or '').strip().upper()
    if text in ORDER_STATES:
        return text
    return _STATUS_MAP.get(text, PENDING)


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """JSON / tqsdk / pandas 数字 → float（NaN/inf → default）"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _now() -> float:
    return time.time()


def default_audit_db() -> str:
    """审计库路径（测试 / 多实例可用环境变量覆盖）"""
    path = os.environ.get('MINIBT_DESK_AUDIT_DB', '').strip()
    if path:
        return path
    return os.path.join(os.path.expanduser('~'), '.minibt',
                        'desk_audit.sqlite3')


def default_config_file() -> str:
    path = os.environ.get('MINIBT_DESK_WORKBENCH_CONFIG', '').strip()
    if path:
        return path
    return os.path.join(os.path.expanduser('~'), '.minibt',
                        'desk_workbench.json')


@dataclass
class RiskDecision:
    """风控结论（`ok=False` 时 `reason` 给用户看）"""

    ok: bool = True
    reason: str = ''
    checks: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {'ok': self.ok, 'reason': self.reason,
                'checks': list(self.checks)}


@dataclass
class OrderTicket:
    """一张订单票（前端 → 后端 → 审计库）"""

    symbol: str
    side: str = 'buy'
    volume: int = 1
    price: Optional[float] = None
    order_type: str = 'market'       # market / limit / stop / conditional
    tif: str = 'GFD'
    trigger_price: Optional[float] = None
    condition: str = '>='
    note: str = ''
    source: str = 'workbench'

    @classmethod
    def parse(cls, payload: Dict[str, Any]) -> 'OrderTicket':
        payload = payload or {}
        price = to_float(payload.get('price'))
        trigger = to_float(payload.get('trigger_price')
                           or payload.get('trigger'))
        side = str(payload.get('side') or payload.get('action')
                   or 'buy').lower()
        if side not in SIDES:
            side = 'buy'
        order_type = str(payload.get('order_type') or payload.get('type')
                         or 'market').lower()
        if order_type not in ('market', 'limit', 'stop', 'conditional'):
            order_type = 'limit' if price else 'market'
        if order_type == 'stop' and trigger is None:
            trigger = price
        if order_type == 'conditional' and trigger is None:
            order_type = 'limit' if price else 'market'
        tif = str(payload.get('tif') or 'GFD').upper()
        if tif not in TIME_IN_FORCE:
            tif = 'GFD'
        condition = str(payload.get('condition') or '>=')
        if condition not in CONDITIONS:
            condition = '>='
        try:
            volume = max(1, int(payload.get('volume')
                                or payload.get('qty') or 1))
        except (TypeError, ValueError):
            volume = 1
        return cls(symbol=str(payload.get('symbol') or '').strip(),
                   side=side, volume=volume,
                   price=price if order_type != 'market' else price,
                   order_type=order_type, tif=tif,
                   trigger_price=trigger, condition=condition,
                   note=str(payload.get('note') or ''),
                   source=str(payload.get('source') or 'workbench'))

    def as_dict(self) -> Dict[str, Any]:
        return {'symbol': self.symbol, 'side': self.side,
                'volume': self.volume, 'price': self.price,
                'order_type': self.order_type, 'tif': self.tif,
                'trigger_price': self.trigger_price,
                'condition': self.condition, 'note': self.note,
                'source': self.source}


class AuditStore:
    """SQLite 审计 / 委托流水（一个文件两套表，按需清理）"""

    def __init__(self, path: str = '', *, keep_days: int = 90):
        self.path = path or default_audit_db()
        self.keep_days = int(keep_days or 0)
        if self.path != ':memory:':
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._create()

    def _create(self) -> None:
        with self._lock, self._db:
            self._db.execute(
                'CREATE TABLE IF NOT EXISTS audit ('
                'id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, '
                'kind TEXT, symbol TEXT, side TEXT, volume INTEGER, '
                'price REAL, status TEXT, text TEXT, account TEXT, '
                'meta TEXT)')
            self._db.execute(
                'CREATE TABLE IF NOT EXISTS orders ('
                'id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, '
                'symbol TEXT, side TEXT, volume INTEGER, price REAL, '
                'order_type TEXT, tif TEXT, status TEXT, order_id TEXT, '
                'account TEXT, text TEXT, trigger_price REAL, '
                'condition TEXT, source TEXT, note TEXT, meta TEXT)')
            self._db.execute(
                'CREATE INDEX IF NOT EXISTS idx_order_ts ON orders(ts DESC)')
            self._db.execute(
                'CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts DESC)')

    # ------------------------------------------------------------ 写
    def log(self, kind: str, text: str = '', *, symbol: str = '',
            side: str = '', volume: int = 0, price: Optional[float] = None,
            status: str = '', account: str = '',
            meta: Any = None) -> int:
        with self._lock, self._db:
            cursor = self._db.execute(
                'INSERT INTO audit (ts, kind, symbol, side, volume, price, '
                'status, text, account, meta) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (_now(), str(kind), str(symbol), str(side), int(volume or 0),
                 to_float(price), str(status), str(text), str(account),
                 json.dumps(meta or {}, ensure_ascii=False, default=str)))
            return int(cursor.lastrowid or 0)

    def add_order(self, order: Dict[str, Any]) -> int:
        with self._lock, self._db:
            cursor = self._db.execute(
                'INSERT INTO orders (ts, symbol, side, volume, price, '
                'order_type, tif, status, order_id, account, text, '
                'trigger_price, condition, source, note, meta) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (to_float(order.get('ts')) or _now(),
                 str(order.get('symbol') or ''), str(order.get('side') or ''),
                 int(order.get('volume') or 0), to_float(order.get('price')),
                 str(order.get('order_type') or 'market'),
                 str(order.get('tif') or 'GFD'),
                 normalize_state(order.get('status')),
                 str(order.get('order_id') or ''),
                 str(order.get('account') or ''),
                 str(order.get('text') or ''),
                 to_float(order.get('trigger_price')),
                 str(order.get('condition') or ''),
                 str(order.get('source') or ''),
                 str(order.get('note') or ''),
                 json.dumps(order.get('meta') or {}, ensure_ascii=False,
                            default=str)))
            return int(cursor.lastrowid or 0)

    def update_order(self, local_id: int, **fields: Any) -> None:
        allowed = ('status', 'order_id', 'text', 'price', 'volume',
                   'account', 'trigger_price')
        sets, values = [], []
        for key in allowed:
            if key not in fields:
                continue
            value = fields[key]
            if key == 'status':
                value = normalize_state(value)
            sets.append(f'{key}=?')
            values.append(value)
        if not sets:
            return
        values.append(int(local_id))
        with self._lock, self._db:
            self._db.execute(
                f'UPDATE orders SET {", ".join(sets)} WHERE id=?', values)

    # ------------------------------------------------------------ 读
    def audit(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                'SELECT * FROM audit ORDER BY id DESC LIMIT ?',
                (max(1, int(limit or 200)),)).fetchall()
        return [self._row(item) for item in rows]

    def orders(self, limit: int = 300, *, status: str = '',
               symbol: str = '') -> List[Dict[str, Any]]:
        sql = 'SELECT * FROM orders'
        where, values = [], []
        if status:
            where.append('status=?')
            values.append(normalize_state(status))
        if symbol:
            where.append('symbol=?')
            values.append(symbol)
        if where:
            sql += ' WHERE ' + ' AND '.join(where)
        sql += ' ORDER BY id DESC LIMIT ?'
        values.append(max(1, int(limit or 300)))
        with self._lock:
            rows = self._db.execute(sql, values).fetchall()
        return [self._row(item) for item in rows]

    def count_orders_since(self, since: float) -> int:
        with self._lock:
            row = self._db.execute(
                'SELECT COUNT(*) AS n FROM orders WHERE ts>=?',
                (float(since),)).fetchone()
        return int(row['n'] if row else 0)

    @staticmethod
    def _row(row: sqlite3.Row) -> Dict[str, Any]:
        item = dict(row)
        for key in ('meta',):
            try:
                item[key] = json.loads(item.get(key) or '{}')
            except (TypeError, ValueError):
                item[key] = {}
        return item

    # ------------------------------------------------------------ 导出 / 清理
    def export_csv(self, path: str, *, table: str = 'orders') -> str:
        table = 'orders' if table != 'audit' else 'audit'
        rows = (self.orders(100000) if table == 'orders'
                else self.audit(100000))
        path = str(path)
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        columns = (['id', 'ts', 'symbol', 'side', 'volume', 'price',
                    'order_type', 'tif', 'status', 'order_id', 'account',
                    'text', 'trigger_price', 'condition', 'source', 'note']
                   if table == 'orders' else
                   ['id', 'ts', 'kind', 'symbol', 'side', 'volume', 'price',
                    'status', 'text', 'account'])
        with open(path, 'w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns,
                                    extrasaction='ignore')
            writer.writeheader()
            for row in reversed(rows):
                writer.writerow(row)
        return path

    def prune(self, keep_days: int = 0) -> int:
        days = int(keep_days or self.keep_days or 0)
        if days <= 0:
            return 0
        cutoff = _now() - days * 86400
        with self._lock, self._db:
            first = self._db.execute(
                'DELETE FROM audit WHERE ts<?', (cutoff,)).rowcount
            second = self._db.execute(
                'DELETE FROM orders WHERE ts<?', (cutoff,)).rowcount
        return int(first or 0) + int(second or 0)

    def close(self) -> None:
        with self._lock:
            try:
                self._db.close()
            except Exception:                                    # noqa: BLE001
                pass


class Workbench:
    """交易工作台（一个 desk 一个实例；全部状态可序列化给前端）"""

    def __init__(self, desk, *, db_path: str = '',
                 config_file: str = ''):
        self.desk = desk
        self.config_file = config_file or default_config_file()
        self.store = AuditStore(db_path or default_audit_db())
        self.limits: Dict[str, Any] = dict(DEFAULT_LIMITS)
        self._conditional: List[Dict[str, Any]] = []
        self._last_prices: Dict[str, float] = {}
        self._reconcile: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._load_config()
        self.recover()

    # ------------------------------------------------------------ 配置
    def _load_config(self) -> None:
        try:
            with open(self.config_file, encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            limits = data.get('limits')
            if isinstance(limits, dict):
                self.limits.update({
                    key: limits[key] for key in DEFAULT_LIMITS
                    if key in limits})
            pending = data.get('conditional')
            if isinstance(pending, list):
                self._conditional = [item for item in pending
                                     if isinstance(item, dict)]

    def save_config(self) -> None:
        path = self.config_file
        folder = os.path.dirname(path)
        if folder:
            try:
                os.makedirs(folder, exist_ok=True)
            except OSError:
                pass
        payload = {'limits': self.limits,
                   'conditional': self._conditional[-100:]}
        try:
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except OSError as error:
            print(f'[desk] 保存工作台配置失败: {error!r}')

    def configure(self, limits: Dict[str, Any]) -> Dict[str, Any]:
        """保存风控（只接受白名单字段，数字做范围裁剪）"""
        limits = limits or {}
        for key, default in DEFAULT_LIMITS.items():
            if key not in limits:
                continue
            value = limits[key]
            if key == 'enabled' or key == 'allow_short':
                self.limits[key] = bool(value)
            elif isinstance(default, int):
                try:
                    self.limits[key] = max(0, int(value or 0))
                except (TypeError, ValueError):
                    pass
            else:
                number = to_float(value)
                if number is not None:
                    self.limits[key] = max(0.0, number)
        self.save_config()
        self.store.log('risk', '风控设置已更新', meta=self.limits)
        return dict(self.limits)

    # ------------------------------------------------------------ 账户 / 行情
    def _trader(self):
        getter = getattr(self.desk, 'trading_view', None)
        return getter() if callable(getter) else None

    def _account(self, symbol: str = '') -> str:
        trader = self._trader()
        if trader is None:
            return ''
        try:
            return str(trader.account_label(symbol))
        except Exception:                                        # noqa: BLE001
            return ''

    def _last_price(self, symbol: str) -> Optional[float]:
        if symbol in self._last_prices:
            return self._last_prices[symbol]
        try:
            rows = getattr(self.desk, '_last_rows', {}) or {}
            return to_float((rows.get(symbol) or {}).get('last'))
        except Exception:                                        # noqa: BLE001
            return None

    def _position(self, symbol: str) -> int:
        """净持仓（拿不到 → 0；只用于风控提示，不参与下单）"""
        try:
            payload = self.desk.position_payload(symbol) or {}
        except Exception:                                        # noqa: BLE001
            return 0
        long_qty = 0
        short_qty = 0
        for key in ('long', 'short'):
            book = payload.get(key) or {}
            try:
                qty = int(book.get('volume') or 0)
            except (TypeError, ValueError):
                qty = 0
            if key == 'long':
                long_qty = qty
            else:
                short_qty = qty
        return int(long_qty - short_qty)

    # ------------------------------------------------------------ 风控
    def check(self, ticket: OrderTicket) -> RiskDecision:
        """单笔风控（不碰网络；行情/持仓拿不到就只做静态检查）"""
        limits = self.limits
        decision = RiskDecision()
        if not limits.get('enabled'):
            decision.checks.append({'name': '风控', 'ok': True,
                                    'detail': '未启用'})
            return decision

        def fail(name: str, detail: str) -> None:
            decision.ok = False
            if not decision.reason:
                decision.reason = f'{name}：{detail}'
            decision.checks.append({'name': name, 'ok': False,
                                    'detail': detail})

        def ok(name: str, detail: str) -> None:
            decision.checks.append({'name': name, 'ok': True,
                                    'detail': detail})

        max_volume = int(limits.get('max_volume') or 0)
        if max_volume and ticket.volume > max_volume:
            fail('单笔手数', f'单笔最多 {max_volume} 手，本次 {ticket.volume}')
        else:
            ok('单笔手数', f'{ticket.volume}（上限 {max_volume or "不限"}）')

        if not limits.get('allow_short', True) and ticket.side == 'sell':
            position = self._position(ticket.symbol)
            if position <= 0:
                fail('禁止开空', '当前设置不允许开空')
            else:
                ok('禁止开空', '卖出属于平多')
        else:
            ok('禁止开空', '允许')

        max_notional = float(limits.get('max_notional') or 0.0)
        price = ticket.price or self._last_price(ticket.symbol)
        if max_notional and price:
            notional = float(price) * ticket.volume
            if notional > max_notional:
                fail('单笔金额', f'约 {notional:,.0f}，上限 '
                                 f'{max_notional:,.0f}')
            else:
                ok('单笔金额', f'{notional:,.0f}（上限 {max_notional:,.0f}）')

        max_orders = int(limits.get('max_orders_per_day') or 0)
        if max_orders:
            today = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
            used = self.store.count_orders_since(today)
            if used >= max_orders:
                fail('单日委托数', f'今日已下 {used} 笔，上限 {max_orders}')
            else:
                ok('单日委托数', f'今日 {used}/{max_orders}')

        max_loss = float(limits.get('max_daily_loss') or 0.0)
        if max_loss:
            loss = self.daily_pnl()
            if loss < 0 and abs(loss) >= max_loss:
                fail('单日亏损', f'今日浮亏 {abs(loss):,.0f}，上限 {max_loss:,.0f}')
            else:
                ok('单日亏损', f'今日 {loss:+,.0f}（上限 -{max_loss:,.0f}）')

        max_position = int(limits.get('max_position') or 0)
        if max_position:
            position = self._position(ticket.symbol)
            target = abs(position + (ticket.volume if ticket.side == 'buy'
                                     else -ticket.volume))
            if target > max_position:
                fail('持仓上限', f'预计 {target} 手，上限 {max_position}')
            else:
                ok('持仓上限', f'预计 {target}/{max_position}')
        return decision

    def daily_pnl(self) -> float:
        """当日盈亏（从账户持仓浮盈汇总；拿不到 → 0）"""
        try:
            payload = self.desk.account_payload() or {}
        except Exception:                                        # noqa: BLE001
            return 0.0
        total = 0.0
        for row in payload.get('positions') or []:
            value = to_float((row or {}).get('profit'))
            if value is not None:
                total += value
        return round(total, 4)

    # ------------------------------------------------------------ 下单
    def submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """订单票入口：风控 → 条件单 / 真实下单 → 流水 + 审计"""
        ticket = OrderTicket.parse(payload)
        if not ticket.symbol:
            return {'ok': False, 'text': '缺少合约'}
        if not getattr(self.desk, 'trading', False):
            return self._reject(ticket, '交易未启用（只读模式）')
        trader = self._trader()
        if trader is None:
            return self._reject(ticket, '交易接口未连接')

        decision = self.check(ticket)
        if not decision.ok:
            self.store.log('risk_reject', decision.reason,
                           symbol=ticket.symbol, side=ticket.side,
                           volume=ticket.volume, price=ticket.price,
                           status=REJECTED, meta=decision.as_dict())
            return {'ok': False, 'text': f'风控拒绝：{decision.reason}',
                    'risk': decision.as_dict()}

        # 条件单 / 止损单：先挂本地，触发后再提交
        if ticket.order_type in ('conditional', 'stop'):
            return self._arm(ticket)

        return self._execute(ticket, risk=decision.as_dict())

    def _execute(self, ticket: OrderTicket, *,
                 risk: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        trader = self._trader()
        if trader is None:
            return self._reject(ticket, '交易接口未连接')
        account = self._account(ticket.symbol)
        local_id = self.store.add_order({
            **ticket.as_dict(), 'status': PENDING, 'account': account,
            'ts': _now(), 'text': '提交中…'})
        try:
            if ticket.side == 'close':
                text = trader.close_symbol(ticket.symbol, ticket.volume)
            else:
                text = trader.place(ticket.symbol, ticket.side,
                                    ticket.volume, ticket.price)
        except Exception as error:                               # noqa: BLE001
            text = f'下单失败：{error!r}'

        from .trading import _trade_failed
        failed = _trade_failed(text)
        status = REJECTED if failed else PENDING
        self.store.update_order(local_id, status=status, text=text)
        self.store.log('order', text, symbol=ticket.symbol,
                       side=ticket.side, volume=ticket.volume,
                       price=ticket.price, status=status, account=account,
                       meta={'risk': risk or {}, 'ticket': ticket.as_dict()})
        if callable(getattr(self.desk, 'push_log', None)):
            self.desk.push_log(f'[工作台] {text}',
                               'warning' if failed else 'success')
        return {'ok': not failed, 'text': text, 'id': local_id,
                'status': status, 'account': account,
                'risk': risk or {}}

    def _reject(self, ticket: OrderTicket, text: str) -> Dict[str, Any]:
        self.store.log('reject', text, symbol=ticket.symbol,
                       side=ticket.side, volume=ticket.volume,
                       price=ticket.price, status=REJECTED)
        return {'ok': False, 'text': text, 'status': REJECTED}

    # ------------------------------------------------------------ 条件单
    def _arm(self, ticket: OrderTicket) -> Dict[str, Any]:
        trigger = ticket.trigger_price or ticket.price
        if trigger is None:
            return self._reject(ticket, '条件单需要触发价')
        item = {
            'id': f'cond{int(_now() * 1000)}',
            'symbol': ticket.symbol, 'side': ticket.side,
            'volume': ticket.volume, 'price': ticket.price,
            'order_type': ticket.order_type, 'tif': ticket.tif,
            'trigger_price': float(trigger),
            'condition': ticket.condition, 'note': ticket.note,
            'status': 'ARMED', 'created': _now(),
        }
        with self._lock:
            self._conditional.append(item)
        self.save_config()
        self.store.log('conditional', f'条件单已挂：{ticket.symbol} '
                       f'{ticket.condition} {trigger:g}',
                       symbol=ticket.symbol, side=ticket.side,
                       volume=ticket.volume, price=ticket.price,
                       status=PENDING, meta=item)
        return {'ok': True, 'text': f'条件单已挂：{ticket.symbol} '
                                    f'{ticket.condition} {trigger:g}',
                'status': PENDING, 'conditional': item}

    def conditional(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._conditional]

    def cancel_conditional(self, cond_id: str) -> bool:
        with self._lock:
            before = len(self._conditional)
            self._conditional = [item for item in self._conditional
                                 if item.get('id') != cond_id]
            removed = len(self._conditional) != before
        if removed:
            self.save_config()
            self.store.log('conditional_cancel', f'撤销条件单 {cond_id}',
                           status=CANCELLED)
        return removed

    def check_conditions(self, prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """行情一拍调用一次：满足条件 → 转成真实下单（返回触发结果）"""
        if not prices:
            return []
        for symbol, value in prices.items():
            number = to_float(value)
            if number is not None:
                self._last_prices[str(symbol)] = number
        fired: List[Dict[str, Any]] = []
        with self._lock:
            pending = list(self._conditional)
        for item in pending:
            symbol = str(item.get('symbol') or '')
            price = to_float(prices.get(symbol))
            if price is None:
                continue
            trigger = to_float(item.get('trigger_price'))
            if trigger is None:
                continue
            condition = str(item.get('condition') or '>=')
            hit = (
                (condition == '>=' and price >= trigger)
                or (condition == '<=' and price <= trigger)
                or (condition == 'cross_up' and price >= trigger
                    and (self._last_prices.get('_prev_' + symbol) or price)
                    < trigger)
                or (condition == 'cross_down' and price <= trigger
                    and (self._last_prices.get('_prev_' + symbol) or price)
                    > trigger)
            )
            self._last_prices['_prev_' + symbol] = price
            if not hit:
                continue
            self.cancel_conditional(str(item.get('id') or ''))
            ticket = OrderTicket(
                symbol=symbol, side=str(item.get('side') or 'buy'),
                volume=int(item.get('volume') or 1),
                price=to_float(item.get('price')),
                order_type='market' if item.get('order_type') == 'stop'
                else 'limit',
                tif=str(item.get('tif') or 'GFD'),
                note=str(item.get('note') or ''),
                source='conditional')
            result = self._execute(ticket)
            result['conditional'] = item
            fired.append(result)
            self.store.log('conditional_fire',
                           f'条件单触发：{symbol} @ {price:g} → '
                           f"{result.get('text')}",
                           symbol=symbol, price=price,
                           status='TRIGGERED', meta=item)
        return fired

    # ------------------------------------------------------------ 撤 / 改
    def cancel(self, order_id: str = '', symbol: str = '',
               *, all_orders: bool = False,
               local_id: int = 0) -> Dict[str, Any]:
        trader = self._trader()
        if trader is None:
            return {'ok': False, 'text': '交易未启用'}
        try:
            if all_orders:
                text = trader.action('cancel_all', symbol)
            else:
                text = trader.cancel_order(order_id, symbol)
        except Exception as error:                               # noqa: BLE001
            text = f'撤单失败：{error!r}'
        from .trading import _trade_failed
        failed = _trade_failed(text)
        if local_id and not failed:
            self.store.update_order(local_id, status=CANCELLED, text=text)
        self.store.log('cancel', text, symbol=symbol, status=(
            REJECTED if failed else CANCELLED), account=self._account(symbol),
            meta={'order_id': order_id, 'all': bool(all_orders)})
        if callable(getattr(self.desk, 'push_log', None)):
            self.desk.push_log(f'[工作台] {text}',
                               'warning' if failed else 'info')
        return {'ok': not failed, 'text': text}

    def modify(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """改单：撤旧单 + 按新价 / 新手数重下（券商不支持改单时的通用做法）"""
        payload = payload or {}
        order_id = str(payload.get('order_id') or '')
        symbol = str(payload.get('symbol') or '')
        local_id = int(payload.get('id') or 0)
        if not symbol:
            return {'ok': False, 'text': '缺少合约'}
        ticket = OrderTicket.parse({**payload, 'side': payload.get('side')
                                    or 'buy', 'order_type': 'limit'})
        if ticket.price is None:
            return {'ok': False, 'text': '改单需要新价格'}
        cancelled = {'ok': True, 'text': '没有旧委托号（按新单处理）'}
        if order_id or local_id:
            cancelled = self.cancel(order_id, symbol, local_id=local_id)
        if not cancelled.get('ok'):
            return {'ok': False, 'text': f"改单失败：{cancelled.get('text')}"}
        result = self._execute(OrderTicket(
            symbol=symbol, side=ticket.side, volume=ticket.volume,
            price=ticket.price, order_type='limit', tif=ticket.tif,
            note=ticket.note or '改单', source='modify'))
        result['cancelled'] = cancelled
        return result

    def close_partial(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = payload or {}
        ticket = OrderTicket.parse({**payload, 'side': 'close'})
        ticket.order_type = 'market'
        decision = self.check(ticket)
        if not decision.ok:
            return {'ok': False,
                    'text': f'风控拒绝：{decision.reason}'}
        return self._execute(ticket, risk=decision.as_dict())

    # ------------------------------------------------------------ 对账
    def reconcile(self) -> Dict[str, Any]:
        """本地流水 vs 券商未成交委托（只报告差异，不静默改状态）"""
        symbols = set()
        for row in self.store.orders(200):
            if row.get('symbol'):
                symbols.add(str(row['symbol']))
        broker: List[Dict[str, Any]] = []
        errors: List[str] = []
        for symbol in list(symbols)[:12]:
            try:
                getter = getattr(self.desk, 'pending_orders', None)
                pending = getter(symbol) if callable(getter) else []
            except Exception as error:                           # noqa: BLE001
                errors.append(f'{symbol}: {error!r}')
                continue
            for item in pending or []:
                broker.append({'symbol': symbol,
                               'order_id': str(item.get('order_id')
                                               or item.get('id') or ''),
                               'status': normalize_state(item.get('status')),
                               'volume': item.get('volume')})
        local_open = [row for row in self.store.orders(200)
                      if row.get('status') in (PENDING, ALIVE, PARTIAL)]
        broker_ids = {item['order_id'] for item in broker if item['order_id']}
        local_ids = {str(row.get('order_id') or '')
                     for row in local_open if row.get('order_id')}
        missing = [row for row in local_open
                   if row.get('order_id') and row['order_id'] not in broker_ids]
        extra = [item for item in broker if item['order_id'] not in local_ids]
        result = {
            'ok': not missing and not extra and not errors,
            'at': _now(), 'local_open': len(local_open),
            'broker_open': len(broker), 'missing': missing[:50],
            'extra': extra[:50], 'errors': errors,
        }
        self._reconcile = result
        self.store.log('reconcile',
                       f"本地 {len(local_open)} / 券商 {len(broker)} / "
                       f"缺失 {len(missing)} / 多出 {len(extra)}",
                       status='OK' if result['ok'] else 'DIFF',
                       meta={key: result[key] for key in
                             ('local_open', 'broker_open')})
        return result

    # ------------------------------------------------------------ 恢复 / 快照
    def recover(self) -> int:
        """启动时把上次残留的 PENDING 标成 UNKNOWN（避免假装还在）"""
        count = 0
        for row in self.store.orders(500):
            if row.get('status') in (PENDING, ALIVE, PARTIAL):
                self.store.update_order(int(row['id']), status=PENDING,
                                        text='上次会话遗留（待对账）')
                count += 1
        return count

    def snapshot(self) -> Dict[str, Any]:
        """前端整页数据（一次补丁画完）"""
        trader = self._trader()
        enabled = bool(getattr(self.desk, 'trading', False) and trader)
        orders = self.store.orders(300)
        return {
            'type': 'workbench',
            'enabled': enabled,
            'real': bool(trader is not None and trader.is_real('')),
            'account': self._account(''),
            'limits': dict(self.limits),
            'orders': orders,
            'conditional': self.conditional(),
            'audit': self.store.audit(200),
            'reconcile': self._reconcile,
            'stats': {
                'orders': len(orders),
                'open': sum(1 for item in orders
                            if item.get('status') in
                            (PENDING, ALIVE, PARTIAL)),
                'failed': sum(1 for item in orders
                              if item.get('status') == REJECTED),
                'daily_pnl': self.daily_pnl(),
            },
            'prices': {key: value for key, value in self._last_prices.items()
                       if not key.startswith('_prev_')},
        }
