"""平台化 / 运维：API Token、定时任务、告警通道、策略版本回滚。

这一层是 headless / 远程访问的「壳」：
* :class:`TokenStore` —— 签发 / 校验 / 撤销带 scope 的 token（SHA-256 落盘，
  明文只在创建时返回一次）
* :class:`TaskScheduler` —— 秒级间隔任务表（可在 desk.tick 里跑；
  ``run_due`` 只跑到期任务，不阻塞主线程）
* :class:`Notifier` —— 企业微信 webhook / SMTP 邮件；配置落 JSON，
  失败也写本地审计，界面能看到「上一次发送结果」
* :class:`StrategyVersions` —— 策略文件快照 / 列表 / 回滚（带内容 hash）
* :class:`OpsService` —— 以上四件的门面，给前端 / REST 用
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
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


class TaskScheduler:
    """轻量定时任务表（间隔秒；`run_due` 由 desk.tick 调用）"""

    def __init__(self):
        self._lock = threading.RLock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []
        self._builtin: Dict[str, Callable[[], Any]] = {}

    def register_builtin(self, name: str, action: Callable[[], Any]) -> None:
        self._builtin[str(name)] = action

    def add(self, name: str, interval: int, action: str = '',
            *, payload: Any = None, enabled: bool = True,
            run_now: bool = False) -> Dict[str, Any]:
        name = str(name or '').strip()
        if not name:
            raise ValueError('任务名不能为空')
        task = {
            'name': name,
            'interval': max(1, int(interval or 60)),
            'action': str(action or name),
            'payload': payload,
            'enabled': bool(enabled),
            'created': _now(),
            'last_run': 0.0,
            'last_status': '',
            'next_run': _now() if run_now else _now() + max(1, int(interval or 60)),
            'runs': 0,
            'errors': 0,
        }
        with self._lock:
            self._tasks[name] = task
        return dict(task)

    def remove(self, name: str) -> bool:
        with self._lock:
            return self._tasks.pop(str(name), None) is not None

    def enable(self, name: str, enabled: bool = True) -> bool:
        with self._lock:
            task = self._tasks.get(str(name))
            if not task:
                return False
            task['enabled'] = bool(enabled)
            task['next_run'] = _now() + int(task.get('interval') or 60)
            return True

    def due(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        now = _now() if now is None else float(now)
        with self._lock:
            return [dict(task) for task in self._tasks.values()
                    if task.get('enabled') and float(task.get('next_run') or 0)
                    <= now]

    def run(self, name: str) -> List[Dict[str, Any]]:
        """立刻跑指定任务（不管 next_run；界面「立即执行」用）"""
        with self._lock:
            task = self._tasks.get(str(name))
            if task is None:
                return []
            task['next_run'] = 0.0
        return self.run_due()

    def run_due(self, now: Optional[float] = None,
                runner: Optional[Callable[[Dict[str, Any]], Any]] = None
                ) -> List[Dict[str, Any]]:
        """跑到期的任务；返回每个任务的执行结果（异常不抛出）"""
        results = []
        for task in self.due(now):
            name = str(task.get('name'))
            started = _now()
            error = ''
            value = None
            action = self._builtin.get(str(task.get('action')))
            try:
                if action is not None:
                    value = action(task.get('payload'))
                elif runner is not None:
                    value = runner(task)
                else:
                    raise RuntimeError(f'没有注册任务动作：{task.get("action")}')
            except Exception as exc:                             # noqa: BLE001
                error = f'{type(exc).__name__}: {exc}'
            with self._lock:
                current = self._tasks.get(name)
                if current is not None:
                    current['last_run'] = started
                    current['last_status'] = 'error' if error else 'ok'
                    current['runs'] = int(current.get('runs') or 0) + 1
                    if error:
                        current['errors'] = int(current.get('errors') or 0) + 1
                    interval = int(current.get('interval') or 60)
                    current['next_run'] = started + interval
            record = {'name': name, 'at': started, 'ok': not error,
                      'error': error, 'value': value,
                      'ms': round((_now() - started) * 1000, 1)}
            results.append(record)
            with self._lock:
                self.history = ([record] + self.history)[:200]
        return results

    def items(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(task) for task in self._tasks.values()]

    def snapshot(self) -> Dict[str, Any]:
        return {'tasks': self.items(), 'history': list(self.history[:50])}


class Notifier:
    """告警通道：企业微信 webhook / SMTP 邮件（都失败 → 只记本地历史）"""

    def __init__(self, config_file: str = ''):
        self.config_file = config_file or os.path.join(
            default_dir(), 'notify.json')
        self.config: Dict[str, Any] = {
            'wecom': {'enabled': False, 'webhook': ''},
            'email': {'enabled': False, 'host': '', 'port': 465,
                      'ssl': True, 'user': '', 'password': '',
                      'to': '', 'from': ''},
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
            for kind in ('wecom', 'email'):
                if isinstance(data.get(kind), dict):
                    self.config[kind].update(data[kind])

    def configure(self, kind: str, values: Dict[str, Any]) -> Dict[str, Any]:
        kind = 'email' if str(kind) == 'email' else 'wecom'
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

    def send(self, title: str, text: str = '', *, level: str = 'info') -> Dict[str, Any]:
        """同步发送（调用方在后台线程里用；失败返回结果不抛）"""
        message = f'[{level}] {title}\n{text}'.strip()
        results: List[Dict[str, Any]] = []
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
        self.tasks = TaskScheduler()
        self.notifier = Notifier(os.path.join(self.root, 'notify.json'))
        self.versions = StrategyVersions(os.path.join(self.root, 'versions'))
        self.started = _now()
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

        self.tasks.register_builtin('heartbeat', heartbeat)
        self.tasks.register_builtin('prune', prune)
        self.tasks.register_builtin('snapshot_quotes', snapshot_quotes)
        self.tasks.register_builtin('reconcile', reconcile)
        # 默认任务：每 5 分钟保存一次报价缓存，每天对账一次（都先禁用，
        # 由用户在「运维」页启用，避免后台悄悄跑东西 ✓）
        self.tasks.add('heartbeat', 300, 'heartbeat', enabled=False)
        self.tasks.add('reconcile', 86400, 'reconcile', enabled=False)

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

    def run_tasks(self) -> List[Dict[str, Any]]:
        return self.tasks.run_due()

    def snapshot(self) -> Dict[str, Any]:
        return {
            'type': 'ops',
            'started': self.started,
            'uptime': round(_now() - self.started, 1),
            'root': self.root,
            'tokens': self.tokens.items(),
            'tasks': self.tasks.snapshot(),
            'notify': self.notifier.snapshot(),
            'versions': self.versions.items(),
            'status': (self.desk.status()
                       if callable(getattr(self.desk, 'status', None)) else {}),
        }
