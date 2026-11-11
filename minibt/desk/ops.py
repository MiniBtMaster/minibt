"""平台化 / 运维：API Token、定时任务、告警通道、策略版本回滚。

这一层是 headless / 远程访问的「壳」：
* :class:`TokenStore` —— 签发 / 校验 / 撤销带 scope 的 token（SHA-256 落盘，
  明文只在创建时返回一次）
* :class:`TaskScheduler` —— 定时任务表：**每 N 秒 / 每天 HH:MM / 仅手动**三种
  触发，动作可以是内置小函数 / **MCP 工具** / **AI 一轮对话**（落盘，重启还在 ✓）
* :class:`Holidays` —— 手工维护的休市日（`skip_holidays` 用，周一~五之外的例外）
* :class:`Notifier` —— 企业微信 webhook / SMTP 邮件；配置落 JSON，
  失败也写本地审计，界面能看到「上一次发送结果」
* :class:`StrategyVersions` —— 策略文件快照 / 列表 / 回滚（带内容 hash）
* :class:`OpsService` —— 以上四件的门面，给前端 / REST 用
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import smtplib
import threading
import time
import urllib.request
from email.message import EmailMessage
from typing import Any, Callable, Dict, List, Optional

#: token 默认有效期（秒）；0 = 永久
DEFAULT_TOKEN_TTL = 7 * 86400

#: 可用 scope（REST 命令按前缀匹配）
SCOPES = ('read', 'trade', 'research', 'data', 'ops', 'admin')


def default_dir() -> str:
    path = os.environ.get('MINIBT_DESK_OPS_DIR', '').strip()
    if path:
        return path
    return os.path.join(os.path.expanduser('~'), '.minibt', 'desk', 'ops')


def _now() -> float:
    return time.time()


def home_notify_path() -> str:
    """用户**真实**的告警配置路径（`~/.minibt/desk/ops/notify.json`）✓

    ⚠ 不能用 `default_dir()`：它会被 `MINIBT_DESK_OPS_DIR` 改掉（测试就这么隔离的），
    而这里要的是「用户自己那份」——只有它对上时，pytest 才需要静音。
    """
    return os.path.join(os.path.expanduser('~'), '.minibt', 'desk', 'ops',
                        'notify.json')


def _hash(token: str) -> str:
    return hashlib.sha256(str(token).encode('utf-8')).hexdigest()


class TokenStore:
    """API Token（文件里只存 hash；支持 scope + 过期 + 撤销）"""

    def __init__(self, path: str = ''):
        self.path = path or os.path.join(default_dir(), 'tokens.json')
        self._lock = threading.RLock()
        self._items: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if isinstance(data, list):
            self._items = [item for item in data if isinstance(item, dict)]

    def _save(self) -> None:
        folder = os.path.dirname(self.path)
        try:
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as handle:
                json.dump(self._items, handle, ensure_ascii=False, indent=2)
        except OSError as error:
            print(f'[desk] 保存 token 失败: {error!r}')

    def issue(self, name: str = '', *, scopes: Any = ('read',),
              ttl: int = DEFAULT_TOKEN_TTL,
              note: str = '') -> Dict[str, Any]:
        scope_list = [str(item) for item in (
            scopes if isinstance(scopes, (list, tuple, set))
            else str(scopes).replace(',', ' ').split()) if str(item)]
        scope_list = [item for item in scope_list if item in SCOPES] or ['read']
        token = secrets.token_urlsafe(32)
        item = {
            'id': secrets.token_hex(6),
            'name': str(name or 'api'),
            'hash': _hash(token),
            'scopes': scope_list,
            'created': _now(),
            'expires': (_now() + int(ttl)) if int(ttl or 0) > 0 else 0,
            'revoked': False,
            'last_used': 0.0,
            'note': str(note or ''),
        }
        with self._lock:
            self._items.append(item)
            self._save()
        public = {key: value for key, value in item.items() if key != 'hash'}
        public['token'] = token          # ★ 只在这里返回一次
        return public

    def verify(self, token: str, scope: str = 'read') -> bool:
        token = str(token or '')
        if not token:
            return False
        digest = _hash(token)
        wanted = str(scope or 'read')
        with self._lock:
            for item in self._items:
                if item.get('revoked'):
                    continue
                if not hmac.compare_digest(str(item.get('hash') or ''), digest):
                    continue
                expires = float(item.get('expires') or 0)
                if expires and expires < _now():
                    return False
                scopes = item.get('scopes') or []
                if 'admin' in scopes or wanted in scopes:
                    item['last_used'] = _now()
                    self._save()
                    return True
                return False
        return False

    def revoke(self, token_id: str) -> bool:
        with self._lock:
            hit = False
            for item in self._items:
                if str(item.get('id')) == str(token_id):
                    item['revoked'] = True
                    hit = True
            if hit:
                self._save()
            return hit

    def revoke_all(self) -> int:
        with self._lock:
            count = 0
            for item in self._items:
                if not item.get('revoked'):
                    item['revoked'] = True
                    count += 1
            self._save()
            return count

    def items(self) -> List[Dict[str, Any]]:
        with self._lock:
            out = []
            for item in self._items:
                public = {key: value for key, value in item.items()
                          if key != 'hash'}
                expires = float(item.get('expires') or 0)
                public['expired'] = bool(expires and expires < _now())
                out.append(public)
            return out


#: ★ v1.3.7-92：可以推送到手机的**事件目录**（界面「告警规则」直接用 ✓）
ALERT_CATALOG: List[Dict[str, Any]] = [
    {'id': 'trade_reject', 'source': '交易', 'label': '拒单 / 下单失败',
     'desc': '保证金不足、平仓超量、被柜台拒绝 —— 最需要立刻知道的一条',
     'level': 'warning', 'enabled': True, 'min_interval': 0},
    {'id': 'trade_fill', 'source': '交易', 'label': '成交回报',
     'desc': '成交 / 部分成交（做日内的话建议开，长线可以关）',
     'level': 'info', 'enabled': False, 'min_interval': 0},
    {'id': 'price_alert', 'source': '预警', 'label': '价格 / 指标预警',
     'desc': '预警中心里「到价 / 上穿下穿 / 指标信号」命中',
     'level': 'info', 'enabled': True, 'min_interval': 0},
    {'id': 'data_stale', 'source': '行情', 'label': '行情停更 / 断线',
     'desc': '交易时段里 K 线 N 秒没更新（登录掉线最常见）',
     'level': 'warning', 'enabled': True, 'min_interval': 600},
    {'id': 'task_error', 'source': '定时任务', 'label': '定时任务失败',
     'desc': '不看界面也能知道任务挂了（推送里带错误原文）',
     'level': 'warning', 'enabled': True, 'min_interval': 0},
    {'id': 'position_risk', 'source': '持仓', 'label': '持仓浮亏超阈值',
     'desc': '单个持仓浮亏占市值超过阈值（默认 5%）—— 该减仓时提醒你',
     'level': 'warning', 'enabled': True, 'min_interval': 1800,
     'threshold': 5.0, 'threshold_label': '浮亏占市值',
     'threshold_unit': '%'},
    {'id': 'order_stale', 'source': '交易', 'label': '挂单超时未成交',
     'desc': '限价单挂了 N 分钟还没成交（默认 10 分钟）',
     'level': 'info', 'enabled': False, 'min_interval': 0,
     'threshold': 10, 'threshold_label': '等待时长', 'threshold_unit': '分钟'},
    {'id': 'login_lost', 'source': '交易', 'label': '交易连接掉线',
     'desc': '天勤 / 富途从「已连接」变成断开（下单会失败，先提醒你）',
     'level': 'warning', 'enabled': True, 'min_interval': 300},
    {'id': 'strategy_live', 'source': '策略', 'label': '策略实盘启停',
     'desc': '启动 / 停止策略实盘时推一条（确认"到底有没有跑起来"）',
     'level': 'info', 'enabled': True, 'min_interval': 0},
    {'id': 'strategy_error', 'source': '策略', 'label': '策略实盘异常',
     'desc': '子进程报错 / 异常退出 / 启动失败（带错误原文）',
     'level': 'warning', 'enabled': True, 'min_interval': 60},
    {'id': 'strategy_drawdown', 'source': '策略', 'label': '策略回撤超阈值',
     'desc': '实盘净值回撤超过阈值（默认 10%，需要账户有净值数据）',
     'level': 'warning', 'enabled': False, 'min_interval': 3600,
     'threshold': 10.0, 'threshold_label': '回撤',
     'threshold_unit': '%'},
    {'id': 'backtest_done', 'source': '策略', 'label': '回测完成',
     'desc': '单策略回测跑完推一条（长回测时可以去干别的）',
     'level': 'info', 'enabled': False, 'min_interval': 0},
    {'id': 'optimize_done', 'source': '策略', 'label': '参数优化完成',
     'desc': '参数优化 / 网格搜完推一条（带最优组的核心指标）',
     'level': 'info', 'enabled': False, 'min_interval': 0},
    {'id': 'news_macro', 'source': '资讯', 'label': '重要宏观临近',
     'desc': '财经日历里「重要」事件 N 分钟内开始（默认 15 分钟）',
     'level': 'info', 'enabled': False, 'min_interval': 0,
     'threshold': 15, 'threshold_label': '提前', 'threshold_unit': '分钟'},
    {'id': 'news_keyword', 'source': '资讯', 'label': '自选 / 持仓相关新闻',
     'desc': '快讯 / 要闻里命中自选或持仓的标题（同一 条只推一次）',
     'level': 'info', 'enabled': False, 'min_interval': 0},
    {'id': 'system_error', 'source': '系统', 'label': '后台异常',
     'desc': '刷新失败 / 索引重建失败等内部错误',
     'level': 'error', 'enabled': False, 'min_interval': 300},
]


#: 静默时段 / 每日汇总的默认值（都是**默认关** ✓ v1.3.7-94）
ALERT_SETTINGS_DEFAULTS: Dict[str, Any] = {
    # 静默时段：这段时间里只推 `error`（严重）级别
    'quiet': {'enabled': False, 'start': '23:00', 'end': '08:00',
              'allow_level': 'error'},
    # 每日汇总：一天一条，把期间命中 / 被压制的告警汇总发一次
    'digest': {'enabled': False, 'at': '16:00'},
    # ★ v1.3.7-95：自定义资讯关键词（不依赖自选 / 持仓）✓
    'keywords': [],
}


class EquityStore:
    """账户 / 策略**净值序列**（SQLite，滚动保留；给回撤告警 + 曲线用 ✓）

    v1.3.7-95：以前「回撤告警」只有一个内存里的峰值，重启就丢、也画不出曲线；
    现在每 60s 采一条 `{ts, equity, balance, pnl}`，按 `key`（账户标签）分组。
    """

    KEEP_DAYS = 400
    SAMPLE_GAP = 55.0          # 同一 key 至少隔这么久才再记一条 ✓

    def __init__(self, path: str = ''):
        self.path = str(path or '')
        self._lock = threading.RLock()
        self._last: Dict[str, float] = {}
        self._ensure()

    def _connect(self):
        import sqlite3
        folder = os.path.dirname(self.path) or '.'
        os.makedirs(folder, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5)
        conn.execute('PRAGMA journal_mode=WAL')
        return conn

    def _ensure(self) -> None:
        if not self.path:
            return
        try:
            with self._lock:
                conn = self._connect()
                try:
                    conn.execute(
                        'CREATE TABLE IF NOT EXISTS equity ('
                        'ts REAL, key TEXT, equity REAL, balance REAL, '
                        'pnl REAL)')
                    conn.execute(
                        'CREATE INDEX IF NOT EXISTS idx_equity '
                        'ON equity(key, ts)')
                    conn.commit()
                finally:
                    conn.close()
        except Exception:                                        # noqa: BLE001
            pass

    def add(self, key: str, equity: float, balance: float = 0.0,
            pnl: float = 0.0) -> bool:
        """记一条（同一 key 55 秒内只记一次 ✓）"""
        if not self.path or equity in (None, ''):
            return False
        key = str(key or 'account')
        now = _now()
        if now - float(self._last.get(key) or 0) < self.SAMPLE_GAP:
            return False
        try:
            equity = float(equity)
        except (TypeError, ValueError):
            return False
        self._last[key] = now
        try:
            with self._lock:
                conn = self._connect()
                try:
                    conn.execute(
                        'INSERT INTO equity (ts, key, equity, balance, pnl)'
                        ' VALUES (?,?,?,?,?)',
                        (now, key, equity, float(balance or 0.0),
                         float(pnl or 0.0)))
                    # 老的顺手裁掉（避免库越来越大 ✓）
                    conn.execute('DELETE FROM equity WHERE ts < ?',
                                 (now - self.KEEP_DAYS * 86400,))
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception:                                        # noqa: BLE001
            return False

    def series(self, key: str = 'account', days: int = 30,
               limit: int = 2000) -> List[Dict[str, Any]]:
        if not self.path or not os.path.exists(self.path):
            return []
        since = _now() - max(1, int(days or 30)) * 86400
        try:
            with self._lock:
                conn = self._connect()
                try:
                    rows = conn.execute(
                        'SELECT ts, equity, balance, pnl FROM equity '
                        'WHERE key = ? AND ts >= ? ORDER BY ts ASC LIMIT ?',
                        (str(key or 'account'), since,
                         max(1, int(limit or 2000)))).fetchall()
                finally:
                    conn.close()
        except Exception:                                        # noqa: BLE001
            return []
        return [{'ts': row[0], 'equity': row[1], 'balance': row[2],
                 'pnl': row[3]} for row in rows]

    def stats(self, key: str = 'account', days: int = 30
              ) -> Dict[str, Any]:
        """峰值 / 当前 / 回撤 / 最大回撤 / 当日盈亏（没数据 → 空壳 ✓）"""
        rows = self.series(key, days)
        if not rows:
            return {'key': key, 'points': 0, 'peak': 0.0, 'current': 0.0,
                    'drawdown': 0.0, 'max_drawdown': 0.0, 'today_pnl': 0.0,
                    'days': int(days or 30), 'points_list': []}
        values = [float(row['equity'] or 0) for row in rows]
        peak = max(values)
        current = values[-1]
        drawdown = ((peak - current) / peak * 100.0) if peak else 0.0
        max_dd = 0.0
        run_peak = values[0]
        for value in values:
            run_peak = max(run_peak, value)
            if run_peak:
                max_dd = max(max_dd, (run_peak - value) / run_peak * 100.0)
        today = time.strftime('%Y-%m-%d')
        first_today = None
        for row in rows:
            if time.strftime('%Y-%m-%d', time.localtime(row['ts'])) == today:
                first_today = float(row['equity'] or 0)
                break
        today_pnl = (current - first_today) if first_today is not None else 0.0
        return {'key': key, 'points': len(rows), 'peak': round(peak, 2),
                'current': round(current, 2),
                'drawdown': round(drawdown, 2),
                'max_drawdown': round(max_dd, 2),
                'today_pnl': round(today_pnl, 2),
                'days': int(days or 30),
                # 曲线用（最多 400 点，够画一张 sparkline ✓）
                'points_list': [[round(row['ts'], 0),
                                 round(float(row['equity'] or 0), 2)]
                                for row in rows[-400:]]}


class AlertLog:
    """**告警记录**（SQLite；给「告警中心」页做列表 / 时间轴 / 搜索 ✓）

    v1.3.7-97：以前 `Notifier.history` 只在内存里（重启就没），也没法搜索；
    现在每条命中（含被静默压制的）都落库，界面能按等级 / 规则 / 关键词筛。
    """

    KEEP_DAYS = 180

    def __init__(self, path: str = ''):
        self.path = str(path or '')
        self._lock = threading.RLock()
        self._ensure()

    def _connect(self):
        import sqlite3
        folder = os.path.dirname(self.path) or '.'
        os.makedirs(folder, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5)
        conn.execute('PRAGMA journal_mode=WAL')
        return conn

    def _ensure(self) -> None:
        if not self.path:
            return
        try:
            with self._lock:
                conn = self._connect()
                try:
                    conn.execute(
                        'CREATE TABLE IF NOT EXISTS alerts ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, '
                        'rule TEXT, level TEXT, title TEXT, text TEXT, '
                        'channel TEXT, ok INTEGER, symbol TEXT)')
                    conn.execute('CREATE INDEX IF NOT EXISTS idx_alert_ts '
                                 'ON alerts(ts)')
                    # ★ v1.3.7-98：老库补 `symbol` 列（告警中心「一键复现」用 ✓）
                    cols = [row[1] for row in conn.execute(
                        'PRAGMA table_info(alerts)').fetchall()]
                    if 'symbol' not in cols:
                        conn.execute('ALTER TABLE alerts '
                                     'ADD COLUMN symbol TEXT')
                    conn.commit()
                finally:
                    conn.close()
        except Exception:                                        # noqa: BLE001
            pass

    def add(self, rule: str, level: str, title: str, text: str = '',
            channel: str = '', ok: bool = True, symbol: str = '') -> bool:
        if not self.path:
            return False
        now = _now()
        try:
            with self._lock:
                conn = self._connect()
                try:
                    conn.execute(
                        'INSERT INTO alerts (ts, rule, level, title, text,'
                        ' channel, ok, symbol) VALUES (?,?,?,?,?,?,?,?)',
                        (now, str(rule or ''), str(level or 'info'),
                         str(title or '')[:300], str(text or '')[:2000],
                         str(channel or '')[:200], 1 if ok else 0,
                         str(symbol or '')[:40]))
                    conn.execute('DELETE FROM alerts WHERE ts < ?',
                                 (now - self.KEEP_DAYS * 86400,))
                    conn.commit()
                finally:
                    conn.close()
            return True
        except Exception:                                        # noqa: BLE001
            return False

    def query(self, query: str = '', level: str = '', rule: str = '',
              limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """按关键词 / 等级 / 规则筛（关键词搜标题 + 正文 ✓）"""
        if not self.path or not os.path.exists(self.path):
            return {'items': [], 'total': 0, 'limit': int(limit)}
        where = []
        args: List[Any] = []
        if str(query or '').strip():
            where.append('(title LIKE ? OR text LIKE ? OR rule LIKE ?)')
            like = '%' + str(query).strip() + '%'
            args.extend([like, like, like])
        if str(level or '').strip():
            where.append('level = ?')
            args.append(str(level).strip())
        if str(rule or '').strip():
            where.append('rule = ?')
            args.append(str(rule).strip())
        clause = (' WHERE ' + ' AND '.join(where)) if where else ''
        try:
            with self._lock:
                conn = self._connect()
                try:
                    total = conn.execute(
                        'SELECT COUNT(*) FROM alerts' + clause,
                        tuple(args)).fetchone()[0]
                    rows = conn.execute(
                        'SELECT id, ts, rule, level, title, text, channel, ok,'
                        ' symbol FROM alerts' + clause
                        + ' ORDER BY ts DESC LIMIT ? OFFSET ?',
                        tuple(args) + (max(1, min(int(limit or 50), 500)),
                                       max(0, int(offset or 0)))).fetchall()
                finally:
                    conn.close()
        except Exception:                                        # noqa: BLE001
            return {'items': [], 'total': 0, 'limit': int(limit)}
        items = [{'id': row[0], 'ts': row[1], 'rule': row[2],
                  'level': row[3], 'title': row[4], 'text': row[5],
                  'channel': row[6], 'ok': bool(row[7]),
                  'symbol': row[8] or ''}
                 for row in rows]
        return {'items': items, 'total': int(total),
                'limit': int(limit), 'offset': int(offset or 0)}

    def stats(self) -> Dict[str, Any]:
        """总数 / 今天几条 / 各等级与规则条数（页面顶部小结 ✓）"""
        empty = {'total': 0, 'today': 0, 'by_level': {}, 'by_rule': {}}
        if not self.path or not os.path.exists(self.path):
            return empty
        try:
            with self._lock:
                conn = self._connect()
                try:
                    total = conn.execute('SELECT COUNT(*) FROM alerts'
                                         ).fetchone()[0]
                    today = time.strftime('%Y-%m-%d')
                    start = time.mktime(time.strptime(today, '%Y-%m-%d'))
                    recent = conn.execute(
                        'SELECT COUNT(*) FROM alerts WHERE ts >= ?',
                        (start,)).fetchone()[0]
                    by_level = dict(conn.execute(
                        'SELECT level, COUNT(*) FROM alerts '
                        'GROUP BY level').fetchall())
                    by_rule = dict(conn.execute(
                        'SELECT rule, COUNT(*) FROM alerts '
                        'GROUP BY rule ORDER BY COUNT(*) DESC LIMIT 20'
                    ).fetchall())
                finally:
                    conn.close()
        except Exception:                                        # noqa: BLE001
            return empty
        return {'total': int(total), 'today': int(recent),
                'by_level': by_level, 'by_rule': by_rule}

    def daily(self, days: int = 14) -> List[Dict[str, Any]]:
        """近 N 天每天各等级的条数（柱状图用 ✓ v1.3.7-98）"""
        days = max(1, min(int(days or 14), 60))
        if not self.path or not os.path.exists(self.path):
            return []
        today = time.localtime()
        buckets = []
        for offset in range(days - 1, -1, -1):
            stamp = time.mktime((today.tm_year, today.tm_mon,
                                 today.tm_mday - offset, 0, 0, 0, 0, 0, -1))
            buckets.append({'day': time.strftime('%Y-%m-%d',
                                                 time.localtime(stamp)),
                            'start': stamp, 'total': 0, 'error': 0,
                            'warning': 0, 'info': 0})
        start = buckets[0]['start'] if buckets else _now()
        try:
            with self._lock:
                conn = self._connect()
                try:
                    rows = conn.execute(
                        'SELECT ts, level FROM alerts WHERE ts >= ?',
                        (start,)).fetchall()
                finally:
                    conn.close()
        except Exception:                                        # noqa: BLE001
            return buckets
        index = {row['day']: row for row in buckets}
        for ts, level in rows:
            day = time.strftime('%Y-%m-%d', time.localtime(ts))
            bucket = index.get(day)
            if bucket is None:
                continue
            bucket['total'] = int(bucket['total']) + 1
            key = str(level or 'info')
            if key in ('error', 'warning', 'info'):
                bucket[key] = int(bucket[key]) + 1
        return buckets

    def clear(self) -> int:
        if not self.path:
            return 0
        try:
            with self._lock:
                conn = self._connect()
                try:
                    count = conn.execute('SELECT COUNT(*) FROM alerts'
                                         ).fetchone()[0]
                    conn.execute('DELETE FROM alerts')
                    conn.commit()
                finally:
                    conn.close()
            return int(count)
        except Exception:                                        # noqa: BLE001
            return 0


class AlertRules:
    """告警规则（`{id: {enabled, level, min_interval}}` + 静默 / 汇总）"""

    def __init__(self, path: str = ''):
        self.path = str(path or '')
        self._lock = threading.RLock()
        self._rows: Dict[str, Dict[str, Any]] = {}
        self._settings: Dict[str, Any] = json.loads(
            json.dumps(ALERT_SETTINGS_DEFAULTS))
        self._load()

    def _load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:                                        # noqa: BLE001
            return
        rows = data.get('rules') if isinstance(data, dict) else data
        if isinstance(data, dict):
            for key in ('quiet', 'digest'):
                block = data.get(key)
                if isinstance(block, dict):
                    self._settings[key].update(block)
            words = data.get('keywords')
            if isinstance(words, list):
                self._settings['keywords'] = [
                    str(item).strip() for item in words
                    if str(item).strip()][:50]
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            key = str(row.get('id') or '')
            if key:
                self._rows[key] = dict(row)

    def _save(self) -> None:
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as handle:
                json.dump({'rules': list(self._rows.values()),
                           'quiet': self._settings['quiet'],
                           'digest': self._settings['digest'],
                           'keywords': self._settings['keywords']},
                          handle, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def items(self) -> List[Dict[str, Any]]:
        """目录 + 用户设置合并（没存过的用默认值 ✓）"""
        out = []
        with self._lock:
            for row in ALERT_CATALOG:
                item = dict(row)
                item.update(self._rows.get(row['id']) or {})
                item['id'] = row['id']
                out.append(item)
        return out

    def get(self, rule_id: str) -> Optional[Dict[str, Any]]:
        for row in self.items():
            if row['id'] == str(rule_id):
                return row
        return None

    def settings(self) -> Dict[str, Any]:
        """静默时段 / 每日汇总的当前值（带上默认值 ✓）"""
        return json.loads(json.dumps(self._settings))

    def save_settings(self, values: Dict[str, Any]) -> Dict[str, Any]:
        quiet = (values or {}).get('quiet')
        digest = (values or {}).get('digest')
        with self._lock:
            if isinstance(quiet, dict):
                block = self._settings['quiet']
                if 'enabled' in quiet:
                    block['enabled'] = bool(quiet['enabled'])
                for key in ('start', 'end'):
                    if quiet.get(key):
                        block[key] = str(quiet[key])
                if quiet.get('allow_level') in ('info', 'warning', 'error'):
                    block['allow_level'] = str(quiet['allow_level'])
            if isinstance(digest, dict):
                block = self._settings['digest']
                if 'enabled' in digest:
                    block['enabled'] = bool(digest['enabled'])
                if digest.get('at'):
                    block['at'] = str(digest['at'])
            words = (values or {}).get('keywords')
            if words is not None:
                if isinstance(words, str):
                    words = [item for item in words.replace('，', ',')
                             .split(',')]
                rows = []
                for item in words or []:
                    word = str(item).strip()
                    if len(word) >= 2 and word not in rows:
                        rows.append(word[:30])
                self._settings['keywords'] = rows[:50]
            self._save()
        return self.settings()

    def reset(self) -> List[Dict[str, Any]]:
        """恢复默认（清掉用户改过的值 ✓）"""
        with self._lock:
            self._rows = {}
            self._settings = json.loads(json.dumps(ALERT_SETTINGS_DEFAULTS))
            try:
                if self.path and os.path.exists(self.path):
                    os.remove(self.path)
            except OSError:
                pass
        return self.items()

    def save(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        known = {row['id'] for row in ALERT_CATALOG}
        with self._lock:
            for row in rows or []:
                key = str((row or {}).get('id') or '')
                if key not in known:
                    continue
                current = self._rows.get(key, {})
                current['id'] = key                 # ★ 落盘必须带 id ✓
                if 'enabled' in row:
                    current['enabled'] = bool(row['enabled'])
                if 'level' in row:
                    level = str(row['level'] or '').lower()
                    if level in ('info', 'warning', 'error'):
                        current['level'] = level
                if 'min_interval' in row:
                    current['min_interval'] = max(
                        0, int(row['min_interval'] or 0))
                if 'threshold' in row:
                    try:
                        current['threshold'] = float(row['threshold'] or 0)
                    except (TypeError, ValueError):
                        pass
                self._rows[key] = current
            self._save()
        return self.items()


#: 触发方式（`interval` 每 N 秒 / `daily` 每天某时刻 / `manual` 只手动 ✓）
TRIGGERS = ('interval', 'daily', 'manual', 'after')
#: `trigger.kind='after'`：前列任务**成功后**才跑（DAG ✓ v1.3.7-82）
#: 动作类型（内置小函数 / MCP 工具 / 多步串联 / AI 对话 ✓）
ACTIONS = ('builtin', 'tool', 'sequence', 'ai')

#: 任务模板库（界面「从模板新建」/ `desk_ops{action:"task_templates"}` ✓）
TEMPLATES: List[Dict[str, Any]] = [
    {'name': '开盘前简报', 'desc': '每周一到五 08:55，AI 汇总自选/持仓 + 隔夜资讯',
     'action': {'kind': 'ai', 'allow_write': False,
                'prompt': '汇总我的自选与持仓、隔夜外盘与资讯、今天的重要宏观事件，'
                          '给出今天三条关注点（每条一句话，带理由）'},
     'trigger': {'kind': 'daily', 'at': '08:55', 'days': 'mon-fri'},
     'guard': {'skip_holidays': True, 'max_runs_per_day': 1}},
    {'name': '收盘复盘', 'desc': '每个交易日 15:10，AI 写当日复盘并总结得失',
     'action': {'kind': 'ai', 'allow_write': False,
                'prompt': '用今天的分时与成交回顾我的持仓与自选，'
                          '指出今天做得好的一个决定和可以改进的一个决定'},
     'trigger': {'kind': 'daily', 'at': '15:10', 'days': 'mon-fri'},
     'guard': {'skip_holidays': True, 'max_runs_per_day': 1}},
    {'name': '资讯刷新', 'desc': '每 10 分钟刷新快讯 + 日历（纯确定性，不花钱）',
     'action': {'kind': 'sequence', 'steps': [
         {'tool': 'desk_news', 'args': {'kind': 'flash', 'refresh': True}},
         {'tool': 'desk_calendar', 'args': {'days': 2}}]},
     'trigger': {'kind': 'interval', 'every': 600},
     'guard': {'only_trading_hours': True, 'skip_if_running': True}},
    {'name': '持仓风险巡检', 'desc': '每 30 分钟看一次持仓，有持仓才让 AI 点评',
     'action': {'kind': 'ai', 'allow_write': False,
                'prompt': '看我的持仓：逐个说风险（浮亏、集中度、临近到期），只列要点'},
     'trigger': {'kind': 'interval', 'every': 1800},
     'when': {'tool': 'desk_positions', 'args': {}, 'path': 'positions',
              'op': 'count', 'cmp': '>', 'value': 0},
     'guard': {'only_trading_hours': True, 'skip_holidays': True}},
    {'name': '每日清理', 'desc': '每天 06:00 清空会话 / 缓存（省空间）',
     'action': {'kind': 'builtin', 'name': 'pi_cleanup'},
     'trigger': {'kind': 'daily', 'at': '06:00', 'days': 'everyday'},
     'guard': {'max_runs_per_day': 1}},
    {'name': '行情快照落库', 'desc': '每 5 分钟把报价缓存落盘（收盘后也有历史）',
     'action': {'kind': 'builtin', 'name': 'snapshot_quotes'},
     'trigger': {'kind': 'interval', 'every': 300},
     'guard': {'only_trading_hours': True}},
]
#: 「周几」预设（Python 的 weekday：周一=0 ✓）
DAYS = {'everyday': (0, 1, 2, 3, 4, 5, 6),
        'mon-fri': (0, 1, 2, 3, 4),
        'trading': (0, 1, 2, 3, 4),
        'weekend': (5, 6)}

#: 任务默认保护（可在任务上单独改 ✓）
GUARD_DEFAULTS = {'skip_if_running': True, 'max_errors': 3,
                  'max_runs_per_day': 0, 'only_trading_hours': False,
                  'skip_holidays': False, 'timeout': 0,
                  # ★ v1.3.7-81：失败重试次数 / 停机回补 / 推送策略
                  'retries': 0, 'catch_up': False}

#: 推送策略（`error` = 只在失败时推；`always` 成功也推）
NOTIFY_MODES = ('error', 'always', 'never')

#: 停机回补的时间窗（超过就不补了，避免开机瞬间跑一堆 ✓）
CATCH_UP_WINDOW = 6 * 3600


def parse_hhmm(text: str):
    """``'08:55'`` → ``(8, 55)``；格式不对返回 ``None`` ✓"""
    match = re.match(r'^(\d{1,2})[:：](\d{1,2})$', str(text or '').strip())
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def next_after(task: Dict[str, Any], now: Optional[float] = None) -> float:
    """下一次该跑的时间戳（``0`` = 不再自动跑 ✓）"""
    now = _now() if now is None else float(now)
    trigger = task.get('trigger') or {}
    kind = str(trigger.get('kind') or 'interval').lower()
    if kind == 'manual':
        return 0.0
    if kind == 'after':
        # `after` 没有时钟：**-1 = 等上游点名**（0 是"立刻到期"，别混 ✓）
        return -1.0
    if kind == 'daily':
        hhmm = parse_hhmm(trigger.get('at')) or (9, 0)
        days = DAYS.get(str(trigger.get('days') or 'everyday'),
                        DAYS['everyday'])
        base = _dt.datetime.fromtimestamp(now)
        for step in range(0, 9):
            day = (base + _dt.timedelta(days=step)).date()
            if day.weekday() not in days:
                continue
            moment = _dt.datetime.combine(day, _dt.time(*hhmm))
            if moment.timestamp() > now + 0.5:
                return moment.timestamp()
        return now + 86400
    interval = max(1, int(trigger.get('every') or task.get('interval') or 60))
    return now + interval


class Holidays:
    """手工维护的**休市日**（默认只跳过周末；节假日用户自己勾 ✓）"""

    def __init__(self, path: str = ''):
        self.path = str(path or '')
        self._days: List[str] = []
        self._load()

    def _load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding='utf-8') as handle:
                data = json.load(handle)
            days = data.get('days') if isinstance(data, dict) else data
            self._days = sorted({str(item) for item in (days or [])
                                 if re.match(r'^\d{4}-\d{2}-\d{2}$',
                                             str(item))})
        except Exception:                                        # noqa: BLE001
            self._days = []

    def _save(self) -> None:
        if not self.path:
            return
        tmp = f'{self.path}.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as handle:
                json.dump({'days': self._days}, handle, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def items(self) -> List[str]:
        return list(self._days)

    def add(self, day: str) -> Dict[str, Any]:
        day = str(day or '').strip()
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', day):
            raise ValueError('日期格式要是 YYYY-MM-DD')
        if day not in self._days:
            self._days = sorted(self._days + [day])
            self._save()
        return {'days': self.items()}

    def remove(self, day: str) -> Dict[str, Any]:
        day = str(day or '').strip()
        self._days = [item for item in self._days if item != day]
        self._save()
        return {'days': self.items()}

    def toggle(self, day: str = '') -> Dict[str, Any]:
        day = str(day or '').strip() or _dt.date.today().isoformat()
        if day in self._days:
            return self.remove(day)
        return self.add(day)

    def is_holiday(self, now: Optional[float] = None) -> bool:
        stamp = _dt.datetime.fromtimestamp(_now() if now is None else float(now))
        return stamp.date().isoformat() in self._days


def normalize_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """老 schema（``interval`` + ``action:'heartbeat'``）→ 新 schema ✓"""
    row = dict(task or {})
    name = str(row.get('name') or '').strip()
    if not name:
        raise ValueError('任务名不能为空')
    action = row.get('action')
    if isinstance(action, str) or action is None:
        action = {'kind': 'builtin', 'name': str(action or name)}
    elif not isinstance(action, dict):
        action = {'kind': 'builtin', 'name': name}
    action = dict(action)
    action['kind'] = str(action.get('kind') or 'builtin').lower()
    if action['kind'] not in ACTIONS:
        action['kind'] = 'builtin'
    trigger = row.get('trigger')
    if not isinstance(trigger, dict) or not trigger.get('kind'):
        trigger = {'kind': 'interval',
                   'every': max(1, int(row.get('interval') or 60))}
    trigger = dict(trigger)
    trigger['kind'] = str(trigger.get('kind') or 'interval').lower()
    if trigger['kind'] not in TRIGGERS:
        trigger['kind'] = 'interval'
    if trigger['kind'] == 'after':
        after = trigger.get('after') or row.get('after') or []
        if isinstance(after, str):
            after = [item.strip() for item in after.split(',') if item.strip()]
        trigger['after'] = [str(item).strip() for item in after
                            if str(item).strip()]
    guard = dict(GUARD_DEFAULTS)
    guard.update({key: value for key, value in (row.get('guard') or {}).items()
                  if value is not None})
    # 定时任务也可以要求「前置任务成功过」（窗口内）✓
    depends = (row.get('guard') or {}).get('depends_on') \
        or row.get('depends_on') or []
    if isinstance(depends, str):
        depends = [item.strip() for item in depends.split(',') if item.strip()]
    guard['depends_on'] = [str(item).strip() for item in depends
                           if str(item).strip()]
    guard['depends_window'] = int(guard.get('depends_window') or 86400)
    return {
        'name': name,
        'enabled': bool(row.get('enabled')),
        'interval': max(1, int(row.get('interval') or
                               trigger.get('every') or 60)),
        'trigger': trigger,
        'action': action,
        'guard': guard,
        #: 推送策略：error（默认）/ always / never ✓
        'notify': (str(row.get('notify') or 'error').lower()
                   if str(row.get('notify') or 'error').lower()
                   in NOTIFY_MODES else 'error'),
        'description': str(row.get('description') or ''),
        # `when`：跑之前先跑一个只读工具，条件成立才继续 ✓ v1.3.7-80
        'when': dict(row.get('when') or {}),
        'payload': row.get('payload'),
        'created': float(row.get('created') or _now()),
        'last_run': float(row.get('last_run') or 0),
        'last_status': str(row.get('last_status') or ''),
        'last_error': str(row.get('last_error') or ''),
        'last_ms': float(row.get('last_ms') or 0),
        'next_run': float(row.get('next_run') or 0),
        'runs': int(row.get('runs') or 0),
        'errors': int(row.get('errors') or 0),
        'streak': int(row.get('streak') or 0),
        'runs_day': str(row.get('runs_day') or ''),
        'runs_today': int(row.get('runs_today') or 0),
        'disabled_reason': str(row.get('disabled_reason') or ''),
    }


#: ★ v1.3.7-86：内置任务说明（界面「内置」下拉的注释 + 帮助面板 ✓）
BUILTIN_DOCS: Dict[str, Dict[str, Any]] = {
    'heartbeat': {
        'label': '心跳',
        'description': '只记一条"调度还活着"的时间戳，不碰任何数据。',
        'usage': '排查"定时任务到底有没有在跑"；建议每 5 分钟、平时可关。',
        'payload': '{}',
    },
    'prune': {
        'label': '清理',
        'description': '轻量清理：给以后的缓存 / 日志轮转留的钩子（当前只回 ok）。',
        'usage': '每天一次即可；以后接缓存清理时不用再改任务。',
        'payload': '{}',
    },
    'snapshot_quotes': {
        'label': '报价快照落盘',
        'description': '把当前报价缓存立刻写盘（收盘后也留着当日快照）。',
        'usage': '交易时段每 5 分钟跑一次；收盘前 15:00 再跑一次最有用。',
        'payload': '{}',
    },
    'reconcile': {
        'label': '对账',
        'description': '用工作台的本地流水与券商回执对一遍账，差异写进审计。',
        'usage': '每个交易日收盘后 15:10 跑；要求先打开过工作台。',
        'payload': '{}',
    },
    'pi_cleanup': {
        'label': '清理 PI 空会话',
        'description': '删掉 PI 里的空会话 / 重复会话（同一标题只留一条）。',
        'usage': '每天凌晨跑一次，避免会话列表越来越长。',
        'payload': '{}',
    },
}


class TaskScheduler:
    """定时任务表（落盘；``run_due`` 由 desk.tick 调用 ✓）

    * 触发：``interval``（每 N 秒）/ ``daily``（每天 HH:MM，可按周一~五）/
      ``manual``（只手动，或被 AI 调用）
    * 动作：``builtin``（注册的小函数）/ ``tool``（**MCP 工具**）/
      ``ai``（发一轮对话给 AI）
    * 保护：上一轮没跑完就跳过、连续失败自动停用、每天次数上限、
      只在交易时段跑、跳过手工标记的节假日
    """

    def __init__(self, path: str = ''):
        self.path = str(path or '')
        self._lock = threading.RLock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []
        self._builtin: Dict[str, Callable[[Any], Any]] = {}
        self._running: set = set()
        self.holidays = Holidays()
        #: 判断"现在像不像交易时段"（由 OpsService 注入 ✓）
        self.in_session: Optional[Callable[[], bool]] = None
        self._load()

    # ------------------------------------------------------------ 落盘
    def _load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:                                        # noqa: BLE001
            return
        if not isinstance(data, dict):
            return
        for row in data.get('tasks') or []:
            try:
                task = normalize_task(row)
            except Exception:                                    # noqa: BLE001
                continue
            missed = float(task.get('next_run') or 0)
            catch_up = bool((task.get('guard') or {}).get('catch_up'))
            now = _now()
            if (catch_up and task.get('enabled') and missed
                    and missed <= now and now - missed <= CATCH_UP_WINDOW):
                # ★ 停机期间错过的那一次 → 开机就补跑一次 ✓
                task['next_run'] = now
                task['caught_up'] = missed
            else:
                task['next_run'] = next_after(task, now)
            self._tasks[task['name']] = task
        self.history = [dict(item) for item in (data.get('history') or [])][:200]

    def save(self) -> None:
        if not self.path:
            return
        payload = {'version': 2,
                   'tasks': [dict(task) for task in self._tasks.values()],
                   'history': list(self.history[:200])}
        tmp = f'{self.path}.tmp'
        try:
            os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
            with open(tmp, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass

    # ------------------------------------------------------------ 增删改查
    def register_builtin(self, name: str, action: Callable[[Any], Any]) -> None:
        self._builtin[str(name)] = action

    def builtin_names(self) -> List[str]:
        return sorted(self._builtin)

    def add(self, name: str, interval: int = 60, action: str = '',
            *, payload: Any = None, enabled: bool = True,
            run_now: bool = False, trigger: Optional[Dict[str, Any]] = None,
            guard: Optional[Dict[str, Any]] = None,
            description: str = '', notify: str = 'error') -> Dict[str, Any]:
        row = normalize_task({
            'name': name, 'interval': interval,
            'action': action or name, 'payload': payload,
            'enabled': enabled, 'trigger': trigger, 'guard': guard,
            'description': description, 'notify': notify,
        })
        cycle = self.missing_dependencies(
            row['name'], [str(item) for item in
                          ((row.get('trigger') or {}).get('after') or [])
                          + ((row.get('guard') or {}).get('depends_on') or [])])
        if cycle:
            raise ValueError('前置任务会绕成环：' + '、'.join(cycle))
        row['next_run'] = (_now() if run_now
                           else next_after(row))
        with self._lock:
            self._tasks[row['name']] = row
        self.save()
        return dict(row)

    def update(self, name: str, **fields: Any) -> Dict[str, Any]:
        """改任务字段（``trigger`` / ``action`` / ``guard`` / ``enabled``…）"""
        with self._lock:
            current = self._tasks.get(str(name))
            if current is None:
                raise KeyError(f'任务不存在：{name}')
            row = dict(current)
        row.update(fields)
        row = normalize_task(row)
        cycle = self.missing_dependencies(
            row['name'], [str(item) for item in
                          ((row.get('trigger') or {}).get('after') or [])
                          + ((row.get('guard') or {}).get('depends_on') or [])])
        if cycle:
            raise ValueError('前置任务会绕成环：' + '、'.join(cycle))
        row['next_run'] = next_after(row)
        with self._lock:
            self._tasks[row['name']] = row
        self.save()
        return dict(row)

    def remove(self, name: str) -> bool:
        with self._lock:
            ok = self._tasks.pop(str(name), None) is not None
        if ok:
            self.save()
        return ok

    def enable(self, name: str, enabled: bool = True) -> bool:
        with self._lock:
            task = self._tasks.get(str(name))
            if not task:
                return False
            task['enabled'] = bool(enabled)
            task['streak'] = 0 if enabled else task.get('streak', 0)
            if enabled:
                task['disabled_reason'] = ''
            task['next_run'] = (next_after(task) if enabled else 0.0)
        self.save()
        return True

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(str(name))
            return dict(task) if task else None

    # ------------------------------------------------------------ 到期判断
    def due(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        now = _now() if now is None else float(now)
        with self._lock:
            return [dict(task) for task in self._tasks.values()
                    if task.get('enabled')
                    and float(task.get('next_run') or 0) >= 0
                    and float(task.get('next_run') or 0) <= now]

    def run(self, name: str) -> List[Dict[str, Any]]:
        """立刻跑指定任务（不管 next_run；界面「立即执行」用）"""
        with self._lock:
            task = self._tasks.get(str(name))
            if task is None:
                return []
            task['next_run'] = 0.0
        return self.run_due()

    def dependencies(self, task: Dict[str, Any]) -> List[str]:
        """这个任务的前置任务名（`after` 触发 / `guard.depends_on` ✓）"""
        trigger = task.get('trigger') or {}
        if str(trigger.get('kind') or '') == 'after':
            return [str(item) for item in (trigger.get('after') or [])]
        guard = task.get('guard') or {}
        return [str(item) for item in (guard.get('depends_on') or [])]

    def dependency_state(self, task: Dict[str, Any],
                         now: Optional[float] = None) -> List[Dict[str, Any]]:
        """每个前置任务的现状（`ok` / `age` 秒）——界面和判断都用它 ✓"""
        now = _now() if now is None else float(now)
        window = int((task.get('guard') or {}).get('depends_window') or 86400)
        rows = []
        for name in self.dependencies(task):
            dep = self.get(name) or {}
            last = float(dep.get('last_run') or 0)
            age = now - last if last else -1.0
            rows.append({
                'name': name,
                'found': bool(dep),
                'status': str(dep.get('last_status') or ''),
                'age': round(age, 1),
                'ok': bool(dep) and str(dep.get('last_status')) == 'ok'
                      and 0 <= age <= window,
            })
        return rows

    def missing_dependencies(self, name: str,
                             depends: List[str]) -> List[str]:
        """做环检查：新依赖会不会绕回自己（A→B→A）✓"""
        name = str(name or '')
        edges = {task_name: self.dependencies(task)
                 for task_name, task in
                 {item['name']: item for item in self.items()}.items()}
        edges[name] = list(depends)

        def walk(node: str, seen: set) -> bool:
            if node == name:
                return True
            if node in seen:
                return False
            seen.add(node)
            return any(walk(child, seen) for child in edges.get(node, []))

        bad = []
        for dep in depends:
            if dep == name or walk(dep, set()):
                bad.append(dep)
        return bad

    def _skip_reason(self, task: Dict[str, Any], now: float) -> str:
        guard = task.get('guard') or {}
        if guard.get('skip_holidays') and self.holidays.is_holiday(now):
            return '今天是手工标记的休市日'
        if guard.get('only_trading_hours'):
            check = self.in_session
            if check is not None:
                try:
                    if not check():
                        return '不在交易时段'
                except Exception:                                # noqa: BLE001
                    pass
        deps = self.dependency_state(task, now)
        broken = [row for row in deps if not row['ok']]
        if broken:
            names = '、'.join(
                row['name'] + ('（没跑过）' if not row['found'] else
                               ('（上次失败）' if row['status'] == 'error'
                                else '（结果过期）'))
                for row in broken)
            return f'前置任务没成功：{names}'
        condition = task.get('when') or {}
        if condition.get('tool'):
            ok, detail = self._check_when(condition)
            if not ok:
                return detail
        limit = int(guard.get('max_runs_per_day') or 0)
        if limit > 0:
            day = _dt.datetime.fromtimestamp(now).date().isoformat()
            if str(task.get('runs_day') or '') == day \
                    and int(task.get('runs_today') or 0) >= limit:
                return f'今天已经跑满 {limit} 次'
        return ''

    #: `when` 用的工具调用器（OpsService 注入；没注入就跳过判断 ✓）
    when_runner: Optional[Callable[[str, Dict[str, Any]], Any]] = None

    @staticmethod
    def _compare(value: Any, want: Any, op: str) -> bool:
        """数值优先，其次字符串；**任何比较异常都当不成立**（不炸任务 ✓）"""
        pairs: List[Any] = []
        try:
            pairs.append((float(value), float(want)))
        except (TypeError, ValueError):
            pass
        if op in ('==', '!=', 'contains'):
            # 大小比较对字符串没意义（'abc' > 0 → True 是坑 ✗）
            pairs.append((str(value if value is not None else ''),
                          str(want if want is not None else '')))
        for left, right in pairs:
            try:
                if op == '>':
                    return bool(left > right)
                if op == '>=':
                    return bool(left >= right)
                if op == '<':
                    return bool(left < right)
                if op == '<=':
                    return bool(left <= right)
                if op == '==':
                    return bool(left == right)
                if op == '!=':
                    return bool(left != right)
                if op == 'contains':
                    return str(right) in str(left)
            except TypeError:
                continue
        return False

    def _check_when(self, condition: Dict[str, Any]) -> Any:
        """`when` 条件：跑一个只读工具取数值，再按 op 比一下 ✓"""
        runner = self.when_runner
        if runner is None:
            return True, ''
        tool = str(condition.get('tool') or '')
        try:
            data = runner(tool, dict(condition.get('args') or {}))
        except Exception as error:                           # noqa: BLE001
            return True, ''      # 判断失败不该拦住任务（宁可跑一次 ✓）
        value: Any = data
        for part in [item for item in
                     str(condition.get('path') or '').split('.') if item]:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list):
                try:
                    value = value[int(part)]
                except (ValueError, IndexError):
                    value = None
            else:
                value = None
        op = str(condition.get('op') or '>').strip()
        want = condition.get('value')
        hit = False
        if op in ('truthy', 'falsy', 'empty', 'nonempty'):
            truth = bool(value)
            hit = truth if op in ('truthy', 'nonempty') else not truth
        elif op == 'count':                 # 列表 / 字典的元素个数比较 ✓
            size = len(value) if isinstance(value, (list, dict, str)) else 0
            hit = self._compare(size, want, condition.get('cmp') or '>')
        else:
            hit = self._compare(value, want, op)
        if hit:
            return True, ''
        return False, (f'条件不成立（{tool}.{condition.get("path") or ""}'
                       f' {op} {want} 实际 {value}）')

    def run_due(self, now: Optional[float] = None,
                runner: Optional[Callable[[Dict[str, Any]], Any]] = None
                ) -> List[Dict[str, Any]]:
        """跑到期的任务；返回每个任务的执行结果（**异常不抛出** ✓）"""
        now = _now() if now is None else float(now)
        results = []
        for task in self.due(now):
            results.append(self._run_one(task, now, runner))
        return results

    def _run_one(self, task: Dict[str, Any], now: float,
                 runner: Optional[Callable[[Dict[str, Any]], Any]] = None
                 ) -> Dict[str, Any]:
        name = str(task.get('name'))
        guard = task.get('guard') or {}
        started = _now()
        value: Any = None
        error = ''
        skipped = ''
        action = task.get('action') or {}
        kind = str(action.get('kind') or 'builtin')

        if guard.get('skip_if_running', True) and name in self._running:
            skipped = '上一轮还没跑完'
        if not skipped:
            skipped = self._skip_reason(task, now)
        if not skipped:
            self._running.add(name)
            attempts = max(0, int(guard.get('retries') or 0)) + 1
            try:
                for attempt in range(attempts):
                    try:
                        if kind == 'builtin':
                            handler = self._builtin.get(
                                str(action.get('name') or ''))
                            if handler is None:
                                raise RuntimeError(
                                    '没有注册任务动作：'
                                    + str(action.get('name')))
                            value = handler(task.get('payload'))
                        elif runner is not None:
                            value = runner(task)
                        else:
                            raise RuntimeError(
                                f'没有执行器，跑不了 {kind} 动作')
                        if not (isinstance(value, dict)
                                and value.get('ok') is False):
                            error = ''
                            break
                        error = str(value.get('error') or value.get('detail')
                                    or '动作返回失败')
                    except Exception as exc:                     # noqa: BLE001
                        error = f'{type(exc).__name__}: {exc}'
                    if attempt + 1 < attempts:
                        # 重试之间稍微等一下（同一拍里连打没意义 ✓）
                        time.sleep(min(2.0, 0.5 * (attempt + 1)))
            finally:
                self._running.discard(name)

        ok = not error and not skipped
        output = ''
        summary = ''
        if isinstance(value, dict):
            if value.get('ok') is False and not error:
                ok = False
                error = str(value.get('error') or value.get('detail')
                            or '动作返回失败')
            summary = str(value.get('summary') or '')[:400]
            output = str(value.get('output') or '')[:6000]
        elif value is not None:
            summary = str(value)[:400]

        day = _dt.datetime.fromtimestamp(started).date().isoformat()
        with self._lock:
            current = self._tasks.get(name)
            if current is not None:
                current['last_run'] = started
                current['last_status'] = ('skipped' if skipped
                                          else ('error' if not ok else 'ok'))
                current['last_error'] = error or skipped
                current['last_ms'] = round((_now() - started) * 1000, 1)
                if not skipped:
                    current['runs'] = int(current.get('runs') or 0) + 1
                    current['runs_day'] = day
                    current['runs_today'] = (int(current.get('runs_today') or 0)
                                             + 1
                                             if str(current.get('runs_day')
                                                    or '') == day else 1)
                if not skipped and not ok:
                    current['errors'] = int(current.get('errors') or 0) + 1
                    current['streak'] = int(current.get('streak') or 0) + 1
                elif not skipped:
                    current['streak'] = 0
                current['next_run'] = (next_after(current, started)
                                       if current.get('enabled') else 0.0)
                limit = int(guard.get('max_errors') or 3)
                if limit > 0 and int(current.get('streak') or 0) >= limit:
                    current['enabled'] = False
                    current['next_run'] = 0.0
                    current['disabled_reason'] = (
                        f'连续失败 {current["streak"]} 次，已自动停用')

        if ok and not skipped:
            # ★ 上游成功 → 把「等它」的任务立刻排上 ✓
            for item in self.items():
                trigger = item.get('trigger') or {}
                if str(trigger.get('kind') or '') != 'after':
                    continue
                if name not in [str(x) for x in (trigger.get('after') or [])]:
                    continue
                if not item.get('enabled'):
                    continue
                with self._lock:
                    current = self._tasks.get(str(item.get('name')))
                    if current is not None:
                        current['next_run'] = _now()
                        current['triggered_by'] = name
        record = {'name': name, 'at': started, 'ok': ok,
                  'kind': kind, 'skipped': skipped, 'error': error,
                  'summary': summary, 'output': output,
                  'ms': round((_now() - started) * 1000, 1)}
        with self._lock:
            self.history = ([record] + self.history)[:200]
        self.save()
        return record

    # ------------------------------------------------------------ 快照
    def items(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(task) for task in self._tasks.values()]

    def snapshot(self) -> Dict[str, Any]:
        tasks = self.items()
        with self._lock:
            history = [dict(item) for item in self.history[:50]]
        return {'tasks': tasks, 'history': history,
                'notify_modes': list(NOTIFY_MODES),
                'builtins': self.builtin_names(),
                'templates': [{'name': row['name'], 'desc': row['desc']}
                              for row in TEMPLATES],
                'triggers': list(TRIGGERS), 'actions': list(ACTIONS),
                'holidays': self.holidays.items(),
                'running': sorted(self._running)}


#: xtuis 公众号推送默认入口（关注公众号 `xtuis` 拿 token；`{token}` 会被替换 ✓）
#: ⚠ 必须是 **wx.**xtuis.cn：写成 `xtuis.cn` 会命中官网首页（返回 HTML，
#:   看着 HTTP 200 但**手机收不到** —— 用户 2026-11-11 实测踩过 ✗）
XTUIS_URL = 'https://wx.xtuis.cn/{token}.send'

#: 可用的告警通道
NOTIFY_CHANNELS = ('wecom', 'xtuis', 'email', 'webhook')


class Notifier:
    """告警通道：企业微信 webhook / **公众号（xtuis）** / SMTP 邮件 / 自定义 webhook
    （都失败 → 只记本地历史 ✓）
    """

    def __init__(self, config_file: str = ''):
        self.config_file = config_file or os.path.join(
            default_dir(), 'notify.json')
        #: 是不是**用户真实**的那份配置（`~/.minibt/desk/ops/notify.json`）
        #: ★ v1.3.7-101：测试里跑出来的通知**绝不能真推到用户微信** ✗
        self._real_config = os.path.abspath(self.config_file) == os.path.abspath(
            home_notify_path())
        self.config: Dict[str, Any] = {
            'wecom': {'enabled': False, 'webhook': ''},
            # ★ v1.3.7-84：微信公众号推送（关注公众号 → 拿 token → 手机收到 ✓）
            'xtuis': {'enabled': False, 'token': '', 'url': ''},
            'email': {'enabled': False, 'host': '', 'port': 465,
                      'ssl': True, 'user': '', 'password': '',
                      'to': '', 'from': ''},
            # 通用 webhook（Server酱 / PushPlus / 钉钉 / 自建网关 …）
            'webhook': {'enabled': False, 'url': '', 'method': 'POST',
                        'template': ''},
        }
        self.history: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        try:
            with open(self.config_file, encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            for kind in NOTIFY_CHANNELS:
                if isinstance(data.get(kind), dict):
                    self.config[kind].update(data[kind])

    def configure(self, kind: str, values: Dict[str, Any]) -> Dict[str, Any]:
        """保存某个通道的配置（`wecom / xtuis / email / webhook` ✓）"""
        name = str(kind or 'wecom').strip().lower()
        kind = name if name in self.config else 'wecom'
        block = self.config[kind]
        for key in list(block):
            if key in (values or {}):
                value = values[key]
                if key in ('enabled', 'ssl'):
                    block[key] = bool(value)
                elif key == 'port':
                    try:
                        block[key] = int(value or 0)
                    except (TypeError, ValueError):
                        pass
                else:
                    block[key] = str(value or '')
        with self._lock:
            folder = os.path.dirname(self.config_file)
            try:
                if folder:
                    os.makedirs(folder, exist_ok=True)
                with open(self.config_file, 'w', encoding='utf-8') as handle:
                    json.dump(self.config, handle, ensure_ascii=False, indent=2)
            except OSError as error:
                print(f'[desk] 保存告警配置失败: {error!r}')
        return dict(block)

    def _muted(self) -> str:
        """要不要静音（返回原因；空 = 正常发 ✓）

        * `MINIBT_DESK_NO_NOTIFY=1`：用户 / 脚本显式关掉；
        * 在 pytest 里 + 用的是**真实配置** → 静音（否则跑测试会真发微信 ✗）
        """
        if str(os.environ.get('MINIBT_DESK_NO_NOTIFY') or '').strip().lower()                 in ('1', 'true', 'on', 'yes'):
            return '已关闭推送（MINIBT_DESK_NO_NOTIFY）'
        if self._real_config and os.environ.get('PYTEST_CURRENT_TEST'):
            return '测试环境不发送（pytest）'
        return ''

    def send(self, title: str, text: str = '', *, level: str = 'info') -> Dict[str, Any]:
        """同步发送（调用方在后台线程里用；失败返回结果不抛）"""
        message = f'[{level}] {title}\n{text}'.strip()
        results: List[Dict[str, Any]] = []
        muted = self._muted()
        if muted:
            record = {'at': _now(), 'title': str(title), 'text': str(text),
                      'level': str(level), 'muted': True,
                      'results': [{'channel': 'local', 'ok': True,
                                   'detail': muted}]}
            with self._lock:
                self.history = ([record] + self.history)[:100]
            return record
        wecom = self.config.get('wecom') or {}
        if wecom.get('enabled') and wecom.get('webhook'):
            try:
                body = json.dumps({'msgtype': 'text', 'text': {
                    'content': message}}, ensure_ascii=False).encode('utf-8')
                request = urllib.request.Request(
                    str(wecom['webhook']), data=body,
                    headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=8) as response:
                    results.append({'channel': 'wecom', 'ok': True,
                                    'detail': f'HTTP {response.status}'})
            except Exception as error:                           # noqa: BLE001
                results.append({'channel': 'wecom', 'ok': False,
                                'detail': f'{type(error).__name__}: {error}'})
        # ★ 公众号推送（xtuis：关注公众号 → 手机收消息，最省事的通道 ✓）
        xtuis = self.config.get('xtuis') or {}
        if xtuis.get('enabled'):
            try:
                from urllib.parse import urlencode
                pattern = str(xtuis.get('url') or '').strip() or XTUIS_URL
                endpoint = pattern.replace('{token}',
                                           str(xtuis.get('token') or ''))
                if '{token}' in pattern and not xtuis.get('token'):
                    raise ValueError('还没填 token（关注公众号 xtuis 后回复'
                                     '"token" 获取）')
                query = urlencode({'text': str(title)[:200],
                                   'desp': message[:1000]})
                url = endpoint + ('&' if '?' in endpoint else '?') + query
                request = urllib.request.Request(
                    url, headers={'User-Agent': 'minibt-desk/1.0'})
                with urllib.request.urlopen(request, timeout=8) as response:
                    body = response.read(400).decode('utf-8', 'ignore')
                    head = body.lstrip()[:60].lower()
                    if head.startswith('<!doctype') or head.startswith('<html'):
                        # 命中了网站首页 / 错误页 → 实际没推送到微信 ✗
                        raise RuntimeError(
                            '返回的是网页而不是推送结果：推送地址要写成 '
                            'https://wx.xtuis.cn/{token}.send（注意 wx.）')
                    results.append({'channel': 'xtuis', 'ok': True,
                                    'detail': (f'HTTP {response.status} '
                                               + body.strip()[:60])})
            except Exception as error:                           # noqa: BLE001
                results.append({'channel': 'xtuis', 'ok': False,
                                'detail': f'{type(error).__name__}: {error}'})
        email = self.config.get('email') or {}
        if email.get('enabled') and email.get('host') and email.get('to'):
            try:
                note = EmailMessage()
                note['Subject'] = f'[minibt desk] {title}'
                note['From'] = str(email.get('from') or email.get('user') or '')
                note['To'] = str(email.get('to'))
                note.set_content(message)
                port = int(email.get('port') or 465)
                if email.get('ssl', True):
                    server = smtplib.SMTP_SSL(str(email['host']), port,
                                              timeout=10)
                else:
                    server = smtplib.SMTP(str(email['host']), port, timeout=10)
                try:
                    if email.get('user'):
                        server.login(str(email['user']),
                                     str(email.get('password') or ''))
                    server.send_message(note)
                finally:
                    try:
                        server.quit()
                    except Exception:                            # noqa: BLE001
                        pass
                results.append({'channel': 'email', 'ok': True,
                                'detail': 'sent'})
            except Exception as error:                           # noqa: BLE001
                results.append({'channel': 'email', 'ok': False,
                                'detail': f'{type(error).__name__}: {error}'})
        webhook = self.config.get('webhook') or {}
        if webhook.get('enabled') and webhook.get('url'):
            try:
                from urllib.parse import urlencode
                method = str(webhook.get('method') or 'POST').upper()
                url = str(webhook['url'])
                template = str(webhook.get('template') or '')
                if method == 'GET':
                    params = {'title': str(title), 'text': str(text),
                              'level': str(level)}
                    body = None
                    url = url + ('&' if '?' in url else '?') \
                        + urlencode(params)
                else:
                    if template:
                        payload = (template.replace('{title}', str(title))
                                   .replace('{text}', str(text))
                                   .replace('{level}', str(level)))
                    else:
                        payload = json.dumps({'title': str(title),
                                              'text': str(text),
                                              'level': str(level)},
                                             ensure_ascii=False)
                    body = payload.encode('utf-8')
                    url = (url.replace('{title}', str(title))
                           .replace('{text}', str(text))
                           .replace('{level}', str(level)))
                request = urllib.request.Request(
                    url, data=body,
                    headers={'Content-Type': 'application/json',
                             'User-Agent': 'minibt-desk/1.0'})
                with urllib.request.urlopen(request, timeout=8) as response:
                    results.append({'channel': 'webhook', 'ok': True,
                                    'detail': f'HTTP {response.status}'})
            except Exception as error:                           # noqa: BLE001
                results.append({'channel': 'webhook', 'ok': False,
                                'detail': f'{type(error).__name__}: {error}'})
        if not results:
            results = [{'channel': 'local', 'ok': True,
                        'detail': '没有启用通道，仅记录'}]
        record = {'at': _now(), 'title': str(title), 'text': str(text),
                  'level': str(level), 'results': results}
        with self._lock:
            self.history = ([record] + self.history)[:100]
        return record

    def snapshot(self) -> Dict[str, Any]:
        return {'config': json.loads(json.dumps(self.config)),
                'history': list(self.history[:30])}


class StrategyVersions:
    """策略版本快照 / 回滚（每次保存前打一个点）"""

    def __init__(self, root: str = ''):
        self.root = root or os.path.join(default_dir(), 'versions')
        self._lock = threading.RLock()

    def _folder(self, path: str) -> str:
        stem = os.path.splitext(os.path.basename(str(path)))[0] or 'strategy'
        safe = ''.join(ch if ch.isalnum() or ch in '-_' else '_'
                       for ch in stem)
        return os.path.join(self.root, safe)

    def snapshot(self, path: str, note: str = '') -> Dict[str, Any]:
        path = str(path or '')
        if not os.path.isfile(path):
            raise FileNotFoundError(f'策略文件不存在：{path}')
        folder = self._folder(path)
        os.makedirs(folder, exist_ok=True)
        with open(path, 'rb') as handle:
            data = handle.read()
        digest = hashlib.sha256(data).hexdigest()[:12]
        stamp = time.strftime('%Y%m%d-%H%M%S')
        target = os.path.join(folder, f'{stamp}_{digest}.py')
        suffix = 1
        while os.path.exists(target):
            target = os.path.join(folder, f'{stamp}_{digest}_{suffix}.py')
            suffix += 1
        with self._lock:
            shutil.copyfile(path, target)
            meta_path = os.path.join(folder, 'versions.json')
            items = []
            try:
                with open(meta_path, encoding='utf-8') as handle:
                    items = json.load(handle)
            except (OSError, ValueError):
                items = []
            record = {'version': os.path.basename(target), 'path': target,
                      'source': path, 'hash': digest, 'note': str(note),
                      'at': _now(), 'size': len(data)}
            items = ([record] + [item for item in items
                                 if item.get('version') != record['version']])
            with open(meta_path, 'w', encoding='utf-8') as handle:
                json.dump(items[:200], handle, ensure_ascii=False, indent=2)
        return record

    def items(self, path: str = '') -> List[Dict[str, Any]]:
        if path:
            folder = self._folder(path)
        else:
            folder = self.root
        meta_path = os.path.join(folder, 'versions.json')
        try:
            with open(meta_path, encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return []
        return [item for item in data if isinstance(item, dict)]

    def rollback(self, path: str, version: str = '') -> Dict[str, Any]:
        """回滚到指定版本；不传 version → 最近一版。回滚前先给自己打点。"""
        items = self.items(path)
        if not items:
            raise ValueError('这个策略还没有版本快照')
        target = None
        if version:
            target = next((item for item in items
                           if item.get('version') == version), None)
        target = target or items[0]
        source = str(target.get('path') or '')
        if not os.path.isfile(source):
            raise FileNotFoundError(f'版本文件丢失：{source}')
        backup = None
        try:
            backup = self.snapshot(path, note='回滚前自动备份')
        except FileNotFoundError:
            backup = None
        shutil.copyfile(source, str(path))
        return {'ok': True, 'version': target.get('version'),
                'path': str(path), 'backup': backup}


class OpsService:
    """运维门面（一个 desk 一个实例）"""

    def __init__(self, desk=None, *, root: str = ''):
        self.desk = desk
        self.root = root or default_dir()
        os.makedirs(self.root, exist_ok=True)
        self.tokens = TokenStore(os.path.join(self.root, 'tokens.json'))
        self.tasks = TaskScheduler(os.path.join(self.root, 'scheduler.json'))
        self.tasks.holidays = Holidays(os.path.join(self.root,
                                                    'holidays.json'))
        self.notifier = Notifier(os.path.join(self.root, 'notify.json'))
        #: ★ v1.3.7-92：告警规则（交易回执 / 预警 / 行情 / 任务失败 ✓）
        self.alert_rules = AlertRules(os.path.join(self.root, 'alerts.json'))
        #: ★ v1.3.7-95：账户净值序列（回撤告警 + 曲线）
        self.equity = EquityStore(os.path.join(self.root, 'equity.db'))
        #: ★ v1.3.7-97：告警记录（告警中心页的数据源）
        self.alert_log = AlertLog(os.path.join(
            self.root, 'alerts_log.db'))
        self.equity_keys: List[str] = []
        self._alert_sent: Dict[str, float] = {}
        self.versions = StrategyVersions(os.path.join(self.root, 'versions'))
        self.started = _now()
        #: 任务里的「只在交易时段」判断（desk 注入 ✓）
        self.tasks.in_session = self._in_session
        #: `when` 条件用的只读工具调用器 ✓
        self.tasks.when_runner = self._probe_tool
        #: 结果回调（desk 用它推补丁；线程安全由 desk.push 保证 ✓）
        self.on_result: Optional[Callable[[List[Dict[str, Any]]], None]] = None
        self._pool = None
        self._pool_lock = threading.Lock()
        self._register_builtins()

    def _register_builtins(self) -> None:
        def heartbeat(payload=None):
            return {'ok': True, 'at': _now()}

        def prune(payload=None):
            return {'ok': True}

        def snapshot_quotes(payload=None):
            saver = getattr(self.desk, '_save_quote_cache_step', None)
            if callable(saver):
                saver()
                return {'ok': True, 'saved': True}
            return {'ok': True, 'saved': False}

        def reconcile(payload=None):
            getter = getattr(self.desk, 'workbench_view', None)
            bench = getter() if callable(getter) else None
            if bench is None:
                return {'ok': False, 'detail': '工作台不可用'}
            return bench.reconcile()

        def pi_cleanup(payload=None):
            cleaner = getattr(self.desk, 'pi_cleanup', None)
            if callable(cleaner):
                return {'ok': True, 'detail': str(cleaner() or '已清理')}
            inner = getattr(self.desk, 'agent', None)
            cleaner = getattr(inner, 'cleanup_sessions', None)
            if callable(cleaner):
                return {'ok': True, 'detail': str(cleaner() or '已清理')}
            return {'ok': False, 'detail': '没有可用的清理入口'}

        self.tasks.register_builtin('pi_cleanup', pi_cleanup)
        self.tasks.register_builtin('heartbeat', heartbeat)
        self.tasks.register_builtin('prune', prune)
        self.tasks.register_builtin('snapshot_quotes', snapshot_quotes)
        self.tasks.register_builtin('reconcile', reconcile)
        # 默认任务：都先**停用**，由用户在「运维 → 定时任务」里启用 ✓
        if not self.tasks.items():
            self.tasks.add(
                'heartbeat', 300, 'heartbeat', enabled=False,
                trigger={'kind': 'interval', 'every': 300},
                description='每 5 分钟记一次心跳（排查"调度还在不在"）')
            self.tasks.add(
                'reconcile', 86400, 'reconcile', enabled=False,
                trigger={'kind': 'daily', 'at': '15:10',
                         'days': 'mon-fri'},
                guard={'skip_holidays': True},
                description='每个交易日收盘后对账一次')

    def check_token(self, token: str, scope: str = 'read') -> bool:
        return self.tokens.verify(token, scope)

    def notify(self, title: str, text: str = '', *, level: str = 'info'
               ) -> Dict[str, Any]:
        record = self.notifier.send(title, text, level=level)
        try:
            self.desk.push_log(f'[告警] {title}', level)
        except Exception:                                        # noqa: BLE001
            pass
        return record

    # ------------------------------------------------------------ 执行器
    def _in_session(self) -> bool:
        checker = getattr(self.desk, '_looks_like_session', None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:                                    # noqa: BLE001
                return True
        return True

    def _executor(self):
        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    from concurrent.futures import ThreadPoolExecutor
                    self._pool = ThreadPoolExecutor(
                        max_workers=2, thread_name_prefix='desk-sched')
        return self._pool

    def _run_tool(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """`tool` 动作：**直接调 MCP 工具**（确定性任务 ✓）"""
        from . import tools as _tools
        action = task.get('action') or {}
        name = str(action.get('tool') or '').strip()
        if not name:
            return {'ok': False, 'error': '没有指定工具（action.tool）'}
        args = dict(action.get('args') or {})
        if name in _tools.DANGEROUS:
            if not action.get('allow_dangerous'):
                return {'ok': False,
                        'error': (name + ' 会真实下单 / 实盘，定时任务默认不允许'
                                  '自动确认；要跑请在该任务上勾「允许危险工具」')}
            args['confirm'] = True
            try:
                _tools.audit(name, args, 'scheduler-confirm', 'scheduler')
            except Exception:                                # noqa: BLE001
                pass
        text_result = _tools.call(name, args, self.desk,
                                  session='scheduler:' + str(task.get('name')))
        try:
            data = json.loads(text_result)
        except Exception:                                    # noqa: BLE001
            data = {'ok': True, 'output': text_result}
        if not isinstance(data, dict):
            data = {'ok': True, 'output': text_result}
        ok = bool(data.get('ok', True))
        summary = ''
        for key in ('message', 'detail', 'error', 'summary'):
            if data.get(key):
                summary = str(data.get(key))[:300]
                break
        return {'ok': ok, 'summary': summary or ('工具已执行' if ok else '失败'),
                'error': '' if ok else str(data.get('error')
                                           or data.get('detail') or '失败'),
                'output': text_result[:6000]}

    def _run_ai(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """`ai` 动作：把提示词发给 AI 跑**一轮**（权限按任务上的勾 ✓）"""
        from . import agent as _agent
        action = task.get('action') or {}
        prompt = str(action.get('prompt') or '').strip()
        if not prompt:
            return {'ok': False, 'error': '没有写提示词（action.prompt）'}
        session_id = str(action.get('session_id') or '').strip()
        session = _agent.load_session(session_id) if session_id else None
        if session is None:
            root_fn = getattr(self.desk, 'explorer_root', None)
            root = str(root_fn() if callable(root_fn) else '') or os.getcwd()
            session = _agent.create_session(
                root, title='定时：' + str(task.get('name')))
            session_id = str(session.get('id') or '')
            try:
                self.tasks.update(str(task.get('name')),
                                  action={**action,
                                          'session_id': session_id})
            except Exception:                                # noqa: BLE001
                pass
        original_options = dict(session.get('options') or {})
        options = dict(original_options)
        # ★ 「允许写操作」没勾 → 只读档：只能看，改不了界面 / 下不了单 ✓
        options['permission'] = ('desk' if action.get('allow_write')
                                 else 'readonly')
        if action.get('model'):
            options['model'] = str(action.get('model'))
        session['options'] = options
        # ★ v1.3.7-87：模型配置**先按 PI 的来**（用户在 PI「模型」页配的
        #   供应商 / API Key 在 `pi/models.json` 里，跟内置 AI 页的
        #   `ai_base_url / ai_key` 是两套 —— 以前只用后者，所以定时任务
        #   一直报"还没配置 API Key"，但 PI 页面明明能用 ✗）
        config, event_type = self._resolve_ai_config(session)
        if not config.get('base'):
            return {'ok': False,
                    'error': ('还没配置模型：在 PI 页面左下「模型」里选供应商'
                              '并填 API Key（或设置 → AI 助手 → API Key / '
                              '环境变量 MINIBT_AI_KEY）')}
        if not config.get('key') and not str(config.get('base')).startswith(
                ('http://127.0.0.1', 'http://localhost',
                 'https://127.0.0.1', 'https://localhost')):
            return {'ok': False,
                    'error': ('这个供应商还没填 API Key（PI 页面左下「模型」→ '
                              '填 API Key）')}
        errors: List[str] = []

        class _Recorder:
            """包一层 desk：顺手记下 AI 报的错（AgentRun 只用 push 报错）"""

            def __init__(inner_self, desk, sink):
                inner_self._desk = desk
                inner_self._sink = sink

            def __getattr__(inner_self, name):
                return getattr(inner_self._desk, name)

            def push(inner_self, patch):
                if isinstance(patch, dict) and patch.get('event') == 'error':
                    inner_self._sink.append(
                        str(patch.get('error') or '未知错误'))
                return inner_self._desk.push(patch)

        run = _agent.AgentRun(_Recorder(self.desk, errors), session, config,
                              prompt, event_type=event_type)
        try:
            _agent.register(run)      # 这样 PI 的「停止」也能停掉定时任务 ✓
        except Exception:                                    # noqa: BLE001
            pass
        try:
            run.run()
        finally:
            # ★ 只读是**这一轮**的限制，别写死进会话 —— 否则用户回头手动
            #   打开这条会话，权限也变成只读了 ✗（v1.3.7-87）
            session['options'] = original_options
            try:
                _agent.save_session(session)
            except Exception:                                # noqa: BLE001
                pass
        # ★ 跑完刷新 PI 会话列表（界面里能看到这条对话 / 结果 ✓）
        if event_type == 'pi_event':
            try:
                pusher = getattr(self.desk, '_push_pi_sessions', None)
                if callable(pusher):
                    pusher()
                builder = getattr(self.desk, '_pi_session_payload', None)
                if callable(builder):
                    self.desk.push({'type': 'pi_session',
                                    'session': builder(session)})
            except Exception:                                # noqa: BLE001
                pass
        if errors:
            return {'ok': False, 'error': errors[0][:300],
                    'output': chr(10).join(errors)[:2000]}
        reply = ''
        for message in reversed(session.get('messages') or []):
            if str(message.get('role')) == 'assistant':
                reply = str(message.get('content') or '')
                break
        head = ' '.join(reply.split())[:200]
        return {'ok': True, 'summary': head or 'AI 已回复',
                'output': reply[:6000], 'session': session_id}

    def _resolve_ai_config(self, session: Dict[str, Any]) -> Any:
        """按会话的「供应商 / 模型」取配置：**PI（models.json）优先**，其次内置 AI ✓

        返回 `(config, event_type)`；`event_type` 决定前端用哪个页面接收事件：
        PI 会话用 `pi_event`，否则用 `ai_event`（以前一律 `ai_event` → PI 页面
        收不到流式补丁，看起来"发了没反应" ✗）。
        """
        options = session.get('options') or {}
        provider = str(options.get('provider') or '')
        model = str(options.get('model') or '')
        candidates: List[Any] = []
        try:
            from . import pi as _pi
            config = dict(_pi.model_config(_pi.load_models(), provider, model))
            candidates.append((config, 'pi_event'))
        except Exception:                                    # noqa: BLE001
            pass
        builder = getattr(self.desk, '_ai_config', None)
        if callable(builder):
            try:
                builder_result = dict(builder({}) or {})
                candidates.append((builder_result, 'ai_event'))
            except Exception:                                # noqa: BLE001
                pass

        def usable(config: Dict[str, Any]) -> bool:
            if not config.get('base'):
                return False
            return bool(config.get('key')) or str(config.get('base')).startswith(
                ('http://127.0.0.1', 'http://localhost',
                 'https://127.0.0.1', 'https://localhost'))

        for config, event_type in candidates:      # 谁有 key 用谁（PI 优先）✓
            if usable(config):
                return config, event_type
        for config, event_type in candidates:      # 都没 key → 返回能用的那个报错
            if config.get('base'):
                return config, event_type
        return {}, 'ai_event'

    def _probe_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """`when` 用：跑一个工具并返回**解析后的 JSON**（失败给空 dict ✓）"""
        from . import tools as _tools
        text_result = _tools.call(name, dict(args or {}), self.desk,
                                  session='scheduler:when')
        try:
            data = json.loads(text_result)
        except Exception:                                    # noqa: BLE001
            data = {}
        return data if isinstance(data, dict) else {}

    def _run_sequence(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """`sequence` 动作：按顺序跑多个工具，支持 `$0.xxx` 取值 ✓"""
        from . import tools as _tools
        action = task.get('action') or {}
        steps = list(action.get('steps') or [])
        if not steps:
            return {'ok': False, 'error': '没有步骤（action.steps）'}
        results: List[Dict[str, Any]] = []
        lines: List[str] = []
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                return {'ok': False, 'error': f'第 {index + 1} 步格式不对'}
            name = str(step.get('tool') or '').strip()
            if not name:
                return {'ok': False, 'error': f'第 {index + 1} 步没写工具名'}
            args = _tools._resolve_refs(dict(step.get('args') or {}),
                                        results) if results else                 dict(step.get('args') or {})
            text_result = _tools.call(
                name, args, self.desk,
                session='scheduler:' + str(task.get('name')))
            try:
                data = json.loads(text_result)
            except Exception:                                # noqa: BLE001
                # 不是 JSON：多半是工具名写错 / 参数不对 → 按失败 ✓
                data = {'ok': False, 'error': str(text_result)[:300]}
            if not isinstance(data, dict):
                data = {'ok': False, 'error': str(text_result)[:300]}
            results.append({'tool': name, 'args': args, 'result': data})
            ok = bool(data.get('ok', True))
            head = str(data.get('message') or data.get('detail')
                       or data.get('error') or '')[:120]
            lines.append(f'{index + 1}. {name} {"✓" if ok else "✗"}'
                         + (f' {head}' if head else ''))
            if not ok and not step.get('continue_on_error'):
                return {'ok': False,
                        'error': f'第 {index + 1} 步 {name} 失败：'
                                 + str(data.get('error')
                                       or data.get('detail') or '失败'),
                        'summary': ' / '.join(lines)[:300],
                        'output': '\n'.join(lines)[:4000]}
        return {'ok': True, 'summary': ' / '.join(lines)[:300],
                'output': chr(10).join(lines)[:4000],
                'steps': len(steps)}

    def _execute(self, task: Dict[str, Any]) -> Any:
        kind = str((task.get('action') or {}).get('kind') or 'builtin')
        if kind == 'tool':
            return self._run_tool(task)
        if kind == 'sequence':
            return self._run_sequence(task)
        if kind == 'ai':
            return self._run_ai(task)
        return None

    # ------------------------------------------------------------ 模板 / 导入导出
    def templates(self) -> List[Dict[str, Any]]:
        return [dict(row) for row in TEMPLATES]

    def add_from_template(self, name: str, task_name: str = '',
                          enabled: bool = False) -> Dict[str, Any]:
        """按模板新建任务（模板里的动作 / 触发 / 保护原样复制 ✓）"""
        row = next((item for item in TEMPLATES
                    if item['name'] == str(name or '').strip()), None)
        if row is None:
            raise KeyError(f'没有这个模板：{name}')
        target = str(task_name or row['name']).strip()
        self.tasks.add(target, 60, '',
                       trigger=dict(row.get('trigger') or {}),
                       guard=dict(row.get('guard') or {}),
                       enabled=enabled,
                       description=str(row.get('desc') or ''))
        fields: Dict[str, Any] = {'action': dict(row['action']),
                                  'trigger': dict(row.get('trigger') or {}),
                                  'guard': dict(row.get('guard') or {})}
        if row.get('when'):
            fields['when'] = dict(row['when'])
        return self.tasks.update(target, **fields)

    def export_tasks(self) -> Dict[str, Any]:
        """导出任务（JSON 文本 + 结构，方便备份 / 传给别的机器 ✓）"""
        rows = []
        for task in self.tasks.items():
            rows.append({'name': task.get('name'),
                         'enabled': bool(task.get('enabled')),
                         'trigger': task.get('trigger'),
                         'action': task.get('action'),
                         'guard': task.get('guard'),
                         'when': task.get('when') or {},
                         'description': task.get('description') or ''})
        return {'version': 2, 'tasks': rows}

    def import_tasks(self, data: Any, overwrite: bool = False
                     ) -> Dict[str, Any]:
        """导入任务（`overwrite=False` → 同名跳过 ✓）"""
        payload = data
        if isinstance(payload, str):
            payload = json.loads(payload)
        rows = payload.get('tasks') if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError('导入内容要是 {"tasks": [...]} 或任务数组')
        added, skipped, failed = [], [], []
        for row in rows:
            try:
                name = str((row or {}).get('name') or '').strip()
                if not name:
                    failed.append('（没有名字的任务）')
                    continue
                if self.tasks.get(name) and not overwrite:
                    skipped.append(name)
                    continue
                self.tasks.add(name, 60, '',
                               trigger=dict(row.get('trigger') or {}),
                               guard=dict(row.get('guard') or {}),
                               enabled=bool(row.get('enabled')),
                               description=str(row.get('description') or ''))
                fields = {'action': dict(row.get('action') or {}),
                          'trigger': dict(row.get('trigger') or {}),
                          'guard': dict(row.get('guard') or {}),
                          'enabled': bool(row.get('enabled'))}
                if row.get('when'):
                    fields['when'] = dict(row['when'])
                self.tasks.update(name, **fields)
                added.append(name)
            except Exception as error:                       # noqa: BLE001
                failed.append(f'{row}: {error}')
        return {'ok': True, 'added': added, 'skipped': skipped,
                'failed': failed}

    # ------------------------------------------------------------ 对外
    def notify_rule(self, rule_id: str, title: str, text: str = '',
                    level: str = '', key: str = '',
                    symbol: str = '') -> Optional[Dict[str, Any]]:
        """按「告警规则」推一条（规则关了 / 去重窗口内 → 直接返回 None ✓）

        调用点在后台线程里（回执轮询 / tick / 定时任务），`Notifier.send` 是
        同步网络请求 —— 所以**失败只记日志**，绝不影响主流程。
        """
        try:
            rule = self.alert_rules.get(rule_id)
        except Exception:                                        # noqa: BLE001
            rule = None
        if not rule or not rule.get('enabled'):
            return None
        window = max(0, int(rule.get('min_interval') or 0))
        cache_key = f'{rule_id}:{key or ""}'
        now = _now()
        # ★ 静默时段：只放行 allow_level（默认只放「严重」）✓ v1.3.7-94
        settings = self.alert_rules.settings()
        quiet = settings.get('quiet') or {}
        if quiet.get('enabled') and self._in_quiet(quiet, now):
            allow = str(quiet.get('allow_level') or 'error')
            rank = {'info': 1, 'warning': 2, 'error': 3}
            level_now = str(level or rule.get('level') or 'info')
            if rank.get(level_now, 1) < rank.get(allow, 3):
                self._digest_add(rule_id, str(title), 'quiet')
                self.alert_log.add(rule_id, level_now, str(title), str(text),
                                   channel='quiet(静默)', ok=True,
                                   symbol=str(symbol or key or ''))
                return None
        if window:
            last = float(self._alert_sent.get(cache_key) or 0)
            if last and now - last < window:
                return None
        self._alert_sent[cache_key] = now
        self._digest_add(rule_id, str(title), 'hit')
        use_level = str(level or rule.get('level') or 'info')
        try:
            record = self.notifier.send(title, text, level=use_level)
        except Exception as error:                               # noqa: BLE001
            try:
                self.desk.push_log(f'[告警] 推送失败：{error}', 'warning')
            except Exception:                                    # noqa: BLE001
                pass
            return None
        results = (record or {}).get('results') or []
        channel = '、'.join(f"{item.get('channel')}:"
                           f"{'ok' if item.get('ok') else 'fail'}"
                           for item in results) or 'local'
        self.alert_log.add(rule_id, use_level, str(title), str(text),
                           channel=channel,
                           ok=bool(results) and all(bool(item.get('ok'))
                                                    for item in results),
                           symbol=str(symbol or key or ''))
        try:
            self.desk.push_log(f'[告警] {title}', use_level)
        except Exception:                                        # noqa: BLE001
            pass
        return record

    @staticmethod
    def _in_quiet(quiet: Dict[str, Any], now: float) -> bool:
        """现在是否落在静默时段（支持跨零点，如 23:00–08:00 ✓）"""
        start = str(quiet.get('start') or '23:00')
        end = str(quiet.get('end') or '08:00')
        try:
            sh, sm = [int(item) for item in start.split(':')[:2]]
            eh, em = [int(item) for item in end.split(':')[:2]]
        except Exception:                                        # noqa: BLE001
            return False
        stamp = time.localtime(now)
        minutes = stamp.tm_hour * 60 + stamp.tm_min
        start_m, end_m = sh * 60 + sm, eh * 60 + em
        if start_m == end_m:
            return False
        if start_m < end_m:
            return start_m <= minutes < end_m
        return minutes >= start_m or minutes < end_m

    def _digest_add(self, rule_id: str, title: str, kind: str) -> None:
        """记一笔给「每日汇总」用（内存里滚动保存 ✓）"""
        stats = getattr(self, '_digest_stats', None)
        if not isinstance(stats, dict):
            stats = self._digest_stats = {}
        label = str(rule_id or '')
        block = stats.setdefault(label, {'hit': 0, 'quiet': 0, 'last': ''})
        block[kind] = int(block.get(kind) or 0) + 1
        block['last'] = title[:80]

    def maybe_digest(self, now: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """到点发「每日汇总」（默认关；一天最多一次 ✓）"""
        settings = self.alert_rules.settings()
        digest = settings.get('digest') or {}
        if not digest.get('enabled'):
            return None
        now = _now() if now is None else float(now)
        stamp = time.localtime(now)
        at = str(digest.get('at') or '16:00')
        try:
            hour, minute = [int(item) for item in at.split(':')[:2]]
        except Exception:                                        # noqa: BLE001
            return None
        if (stamp.tm_hour, stamp.tm_min) < (hour, minute):
            return None
        today = time.strftime('%Y-%m-%d', stamp)
        sent = getattr(self, '_digest_day', '')
        if sent == today:
            return None
        stats = getattr(self, '_digest_stats', None) or {}
        if not stats:
            self._digest_day = today
            return None
        rules = {row['id']: row for row in self.alert_rules.items()}
        lines = []
        for rule_id, block in sorted(stats.items()):
            label = str((rules.get(rule_id) or {}).get('label') or rule_id)
            quiet = int(block.get('quiet') or 0)
            lines.append(f'{label}：{int(block.get("hit") or 0)} 条'
                         + (f'（静默时段压制 {quiet} 条）' if quiet else ''))
        text = chr(10).join(lines)
        try:
            record = self.notifier.send(f'每日告警汇总 {today}', text,
                                        level='info')
        except Exception:                                        # noqa: BLE001
            return None
        self._digest_day = today
        self._digest_stats = {}
        try:
            self.desk.push_log(f'[告警] 已发送每日汇总（{len(lines)} 类）', 'info')
        except Exception:                                        # noqa: BLE001
            pass
        return record

    def run_tasks(self) -> List[Dict[str, Any]]:
        """**同步**跑到期任务（测试 / 命令行 ✓）"""
        return self.tasks.run_due(runner=self._execute)

    def submit_due(self, now: Optional[float] = None) -> int:
        """**异步**提交到期任务（tick 里调用，不卡界面 ✓）"""
        if not self.scheduler_enabled():
            return 0
        due = self.tasks.due(now)
        for task in due:
            name = str(task.get('name'))
            with self.tasks._lock:                          # noqa: SLF001
                current = self.tasks._tasks.get(name)       # noqa: SLF001
                if current is not None:
                    current['next_run'] = next_after(current)
            self._executor().submit(self._run_async, task)
        return len(due)

    def run_task(self, name: str) -> Dict[str, Any]:
        """立即执行某个任务（异步，结果走 on_result ✓）"""
        task = self.tasks.get(name)
        if task is None:
            return {'ok': False, 'error': '任务不存在：' + str(name)}
        self._executor().submit(self._run_async, task)
        return {'ok': True, 'name': str(name), 'started': True}

    def _notify_task(self, task: Dict[str, Any],
                     record: Dict[str, Any]) -> None:
        """按任务的推送策略把结果推到 IM（error / always / never ✓）"""
        mode = str(task.get('notify') or 'error').lower()
        if mode == 'never':
            return
        ok = bool(record.get('ok'))
        skipped = bool(record.get('skipped'))
        if mode == 'error' and (ok or skipped):
            return
        if skipped and mode != 'always':
            return
        name = str(record.get('name') or task.get('name') or '')
        if skipped:
            title = f'[定时任务] {name} 跳过'
            body = str(record.get('skipped') or '')
            level = 'info'
        elif ok:
            title = f'[定时任务] {name} 完成'
            body = (f"耗时 {record.get('ms')}ms\n"
                    f"{record.get('summary') or ''}")
            level = 'info'
        else:
            title = f'[定时任务] {name} 失败'
            body = (f"错误：{record.get('error') or ''}\n"
                    f"{record.get('summary') or ''}")
            level = 'warning'
        try:
            self.notifier.send(title, body.strip(), level=level)
            self.desk.push({'type': 'ops_notify',
                            'notify': self.notifier.snapshot()})
        except Exception as error:                           # noqa: BLE001
            try:
                self.desk.push_log(f'[定时] 推送失败：{error}', 'warning')
            except Exception:                                # noqa: BLE001
                pass

    def _run_async(self, task: Dict[str, Any]) -> None:
        try:
            record = self.tasks._run_one(task, _now(), self._execute)
        except Exception as error:                           # noqa: BLE001
            record = {'name': str(task.get('name')), 'ok': False,
                      'kind': '', 'error': type(error).__name__ + ': '
                      + str(error), 'ms': 0, 'at': _now(), 'summary': '',
                      'output': ''}
        if not record.get('ok') and not record.get('skipped'):
            self.notify_rule('task_error', f'定时任务失败：{record.get("name")}',
                             str(record.get('error') or ''),
                             key=str(record.get('name') or ''))
        self._notify_task(task, record)
        callback = self.on_result
        if callable(callback):
            try:
                callback([record])
            except Exception:                                # noqa: BLE001
                pass

    def task_snapshot(self) -> Dict[str, Any]:
        """界面用的任务快照：**带上 tools / builtins / enabled** ✓

        （以前各处只推 `tasks.snapshot()`，里面没有工具清单 → 定时任务页的
        「工具」下拉是空的 ✗ v1.3.7-89）
        """
        return {**self.tasks.snapshot(),
                'tools': self._tool_names(),
                'enabled': self.scheduler_enabled()}

    def _tool_names(self) -> List[str]:
        try:
            from . import tools as _tools
            return list(_tools.NAMES)
        except Exception:                                    # noqa: BLE001
            return []

    def scheduler_enabled(self) -> bool:
        """全局开关 `scheduler_enabled`（设置页可关；默认开 ✓）"""
        try:
            from . import user_prefs
            data = user_prefs.settings() or {}
            return data.get('scheduler_enabled') is not False
        except Exception:                                    # noqa: BLE001
            return True

    def snapshot(self) -> Dict[str, Any]:
        return {
            'type': 'ops',
            'started': self.started,
            'uptime': round(_now() - self.started, 1),
            'root': self.root,
            'tokens': self.tokens.items(),
            'tasks': self.task_snapshot(),
            'holidays': self.tasks.holidays.items(),
            'notify': self.notifier.snapshot(),
            'alert_rules': self.alert_rules.items(),
            'alert_settings': self.alert_rules.settings(),
            'equity': self.equity.stats(),
            'alert_log': self.alert_log.stats(),
            'versions': self.versions.items(),
            'status': (self.desk.status()
                       if callable(getattr(self.desk, 'status', None)) else {}),
        }
