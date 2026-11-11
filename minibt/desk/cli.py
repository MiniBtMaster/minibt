"""命令行操作 desk（v1.3.7-90）：不用手写 curl / 转义引号。

前置：先起一个**带 HTTP 入口**的 desk（Qt 窗口不认 token）::

    python -m minibt.desk.headless --port 8765        # 无界面常驻
    python -m minibt desk --browser --port 8765       # 浏览器壳

然后在另一个 cmd 里::

    set MINIBT_DESK_TOKEN=Xsy7...      # 运维页生成的 token（只设一次）
    python -m minibt.desk.cli status
    python -m minibt.desk.cli tasks
    python -m minibt.desk.cli run 开盘简报
    python -m minibt.desk.cli rpc ops --payload {}
    python -m minibt.desk.cli rpc ops_task_add --file add.json
    python -m minibt.desk.cli doctor          # 连不上时先跑这个 ✓

设计：**零依赖**（只用标准库），所有错误都翻译成人话（403 是 token / scope，
400 是命令白名单，连不上是服务没起）；`--json` 打原始 JSON 给脚本用。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

#: 默认地址（可用 `MINIBT_DESK_URL` / `--url` 改）
DEFAULT_URL = 'http://127.0.0.1:8765'

#: token 的三种来源（优先级从高到低）
TOKEN_ENV = ('MINIBT_DESK_TOKEN', 'MINIBT_TOKEN')

#: 这些命令只推补丁、不返回数据（`data: null` 是正常的 ✓）
PUSH_ONLY = ('ops_task_add', 'ops_task_run', 'ops_task_update',
             'ops_task_remove', 'ops_task_toggle', 'ops_task_template',
             'ops_holidays', 'ops_notify_config', 'ops_notify_test',
             'ops_version_snapshot', 'ops_version_rollback', 'layout_save',
             'layout_update', 'settings_save', 'alerts', 'ui_state')


class CliError(RuntimeError):
    """给人看的错误（main 会打成一行）"""


# ---------------------------------------------------------------- 请求
def token_of(args) -> str:
    for key in TOKEN_ENV:
        value = str(os.environ.get(key) or '').strip()
        if value:
            return value
    value = str(getattr(args, 'token', '') or '').strip()
    if value:
        return value
    path = str(getattr(args, 'token_file', '') or '').strip()
    if path:
        try:
            with open(path, encoding='utf-8') as handle:
                return handle.read().strip()
        except OSError as error:
            raise CliError(f'读不到 token 文件：{path}（{error}）') from error
    raise CliError(
        '没有 token：先设置环境变量 MINIBT_DESK_TOKEN=…（运维页 → API Token '
        '生成），或加 --token / --token-file')


def base_url(args) -> str:
    url = str(getattr(args, 'url', '') or os.environ.get('MINIBT_DESK_URL')
              or DEFAULT_URL).strip()
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    return url.rstrip('/')


def request(args, path: str, payload: Optional[Dict[str, Any]] = None
            ) -> Any:
    """发一个请求，返回解析后的 JSON（错误 → CliError 人话）"""
    url = base_url(args) + path
    data = None
    headers = {'X-Desk-Token': token_of(args),
               'Accept': 'application/json',
               'User-Agent': 'minibt-desk-cli/1.0'}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method='POST' if data else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=float(
                getattr(args, 'timeout', 15) or 15)) as response:
            body = response.read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as error:
        raw = ''
        try:
            raw = error.read().decode('utf-8', 'ignore')
        except Exception:                                    # noqa: BLE001
            raw = ''
        hint = ''
        if error.code == 403:
            hint = ('token 无效 / 过期 / 已撤销，或者**scope 不够**'
                    '（workbench→trade、research→research、datahub→data、'
                    'ops→ops，其余 read）')
        elif error.code == 400:
            hint = ('命令不在 /api/rpc 白名单里（可用前缀：workbench / '
                    'research / datahub / ops / strategy_ / local_ / quote_ / '
                    'home / alerts / symbol_search / table_* / visible / '
                    'ui_state / layout / settings / tickets）')
        elif error.code == 404:
            hint = '路径不对（这个服务是 desk 的 HTTP 入口吗？）'
        raise CliError(f'HTTP {error.code}：{raw or error.reason}'
                       + (f'　→ {hint}' if hint else '')) from error
    except urllib.error.URLError as error:
        raise CliError(
            f'连不上 {url}（{error.reason}）　→ 先在另一个窗口起服务：'
            'python -m minibt.desk.headless --port 8765'
            '（Qt 桌面窗口的 qwebchannel 不提供 HTTP 入口）') from error
    try:
        return json.loads(body or '{}')
    except ValueError as error:
        raise CliError(f'返回的不是 JSON：{body[:200]}') from error


def rpc(args, cmd: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    out = request(args, '/api/rpc', {'cmd': cmd, 'payload': payload or {}})
    if isinstance(out, dict) and out.get('ok') is False:
        raise CliError(f'{cmd} 失败：{out.get("error") or "未知错误"}')
    return out.get('data') if isinstance(out, dict) else out


# ---------------------------------------------------------------- payload
def parse_payload(args) -> Dict[str, Any]:
    """`--payload '{...}'` / `--file x.json` / `--set k=v` 三种写法 ✓"""
    payload: Dict[str, Any] = {}
    text = str(getattr(args, 'payload', '') or '').strip()
    if text:
        try:
            data = json.loads(text)
        except ValueError as error:
            raise CliError(f'--payload 不是合法 JSON：{error}') from error
        if not isinstance(data, dict):
            raise CliError('--payload 要是一个 JSON 对象，如 {"name":"x"}')
        payload.update(data)
    path = str(getattr(args, 'file', '') or '').strip()
    if path:
        try:
            with open(path, encoding='utf-8') as handle:
                data = json.load(handle)
        except OSError as error:
            raise CliError(f'读不到 {path}：{error}') from error
        except ValueError as error:
            raise CliError(f'{path} 不是合法 JSON：{error}') from error
        if isinstance(data, dict) and isinstance(data.get('payload'), dict) \
                and 'cmd' in data:
            payload.update(data['payload'])          # 整段 rpc 文件也认 ✓
        elif isinstance(data, dict):
            payload.update(data)
        else:
            raise CliError(f'{path} 里要是一个 JSON 对象')
    for item in getattr(args, 'set', None) or []:
        if '=' not in str(item):
            raise CliError(f'--set 要写成 key=value：{item}')
        key, value = str(item).split('=', 1)
        payload[key.strip()] = _typed(value)
    return payload


def _typed(text: str) -> Any:
    """`--set enabled=true` → True / 数字 → 数字 / 其余按字符串 ✓"""
    word = str(text).strip()
    if word.lower() in ('true', 'false'):
        return word.lower() == 'true'
    if word.lower() in ('null', 'none'):
        return None
    try:
        return int(word)
    except ValueError:
        pass
    try:
        return float(word)
    except ValueError:
        return word


# ---------------------------------------------------------------- 输出
def dump(data: Any, as_json: bool, title: str = '') -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return
    if title:
        print(title)
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f'  {key}: {json.dumps(value, ensure_ascii=False)[:160]}')
            else:
                print(f'  {key}: {value}')
    elif isinstance(data, list):
        for row in data[:50]:
            print('  ' + (json.dumps(row, ensure_ascii=False)
                          if not isinstance(row, str) else row))
    elif data is not None:
        print(data)


def show_tasks(args, as_json: bool) -> int:
    snap = rpc(args, 'ops') or {}
    tasks = ((snap.get('tasks') or {}).get('tasks')) or []
    if as_json:
        dump(tasks, True)
        return 0
    if not tasks:
        print('（还没有定时任务）')
        return 0
    print(f'{"名称":<16}{"动作":<22}{"触发":<18}{"状态":<8}上次')
    for row in tasks:
        action = row.get('action') or {}
        trigger = row.get('trigger') or {}
        kind = str(action.get('kind') or '')
        what = {'tool': f"工具·{action.get('tool')}",
                'sequence': f"多步·{len(action.get('steps') or [])}",
                'ai': 'AI', 'builtin': f"内置·{action.get('name')}"}.get(
                    kind, kind)
        when = ('每 %ss' % (trigger.get('every') or row.get('interval'))
                if trigger.get('kind') == 'interval'
                else ('每天 %s(%s)' % (trigger.get('at'), trigger.get('days'))
                      if trigger.get('kind') == 'daily'
                      else ('前置后' if trigger.get('kind') == 'after'
                            else '仅手动')))
        state = ('启用' if row.get('enabled') else '停用')
        status = str(row.get('last_status') or '—')
        print(f"{str(row.get('name'))[:14]:<16}{str(what)[:20]:<22}"
              f"{when:<18}{state + '/' + status:<8}"
              f"{row.get('last_error') or ''}"[:100])
    return 0


def doctor(args) -> int:
    """体检：URL / token / 连通性 / scope 够不够（一步步说清楚 ✓）"""
    url = base_url(args)
    print(f'地址：{url}')
    try:
        token = token_of(args)
    except CliError as error:
        print(f'token：✗ {error}')
        return 2
    print(f'token：✓ 已读到（{token[:6]}…{token[-4:]}，共 {len(token)} 位）')
    try:
        status = request(args, '/api/status')
    except CliError as error:
        print(f'连通性：✗ {error}')
        return 1
    print('连通性：✓ /api/status 正常')
    data = (status or {}).get('data') or {}
    print(f'  标题={data.get("title")} 离线={data.get("offline")} '
          f'页签={len(data.get("tabs") or [])}')
    try:
        rpc(args, 'ops')
        print('scope ops：✓（能读运维快照）')
    except CliError as error:
        print(f'scope ops：✗ {error}')
    return 0


# ---------------------------------------------------------------- 入口
def _add_common(target: argparse.ArgumentParser) -> None:
    """子命令也能写 `--token` / `--url`（`cli status --token x` 更顺手 ✓）

    用 `SUPPRESS` 做默认值：命令行没写就不覆盖父命令里已解析的值。
    """
    quiet = argparse.SUPPRESS
    target.add_argument('--url', default=quiet, help=argparse.SUPPRESS)
    target.add_argument('--token', default=quiet, help=argparse.SUPPRESS)
    target.add_argument('--token-file', dest='token_file', default=quiet,
                        help=argparse.SUPPRESS)
    target.add_argument('--timeout', type=float, default=quiet,
                        help=argparse.SUPPRESS)
    target.add_argument('--json', action='store_true', default=quiet,
                        help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python -m minibt.desk.cli',
        description='命令行操作 minibt desk（走带 token 的 HTTP 入口）')
    parser.add_argument('--url', default='',
                        help=f'服务地址（默认 {DEFAULT_URL}，或环境变量 '
                             'MINIBT_DESK_URL）')
    parser.add_argument('--token', default='',
                        help='API token（或环境变量 MINIBT_DESK_TOKEN）')
    parser.add_argument('--token-file', dest='token_file', default='',
                        help='从文件读 token（一行）')
    parser.add_argument('--timeout', type=float, default=15.0)
    parser.add_argument('--json', action='store_true', help='打原始 JSON')
    sub = parser.add_subparsers(dest='cmd')

    for name, help_text in (('status', '连接状态（GET /api/status）'),
                            ('snapshot', '已创建页面的快照（GET /api/snapshot）'),
                            ('doctor', '体检：地址 / token / 连通性 / scope')):
        _add_common(sub.add_parser(name, help=help_text))

    one = sub.add_parser('rpc', help='直接调一个命令（POST /api/rpc）')
    _add_common(one)
    one.add_argument('name', help='命令名，如 ops / workbench / layout')
    one.add_argument('--payload', default='', help='JSON 对象字符串')
    one.add_argument('--file', default='', help='从 JSON 文件读 payload')
    one.add_argument('--set', action='append', default=[],
                     help='key=value（可多次；true/false/数字自动转换）')

    _add_common(sub.add_parser('tasks', help='列出定时任务（ops 快照里那张表）'))
    run = sub.add_parser('run', help='立刻跑一个定时任务')
    _add_common(run)
    run.add_argument('name', help='任务名（先 cli tasks 看）')
    run.add_argument('--payload', default='', help='（一般不用）JSON 对象')
    hist = sub.add_parser('history', help='定时任务执行历史')
    _add_common(hist)
    hist.add_argument('--limit', type=int, default=10)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    as_json = bool(getattr(args, 'json', False))
    name = str(getattr(args, 'cmd', '') or '')
    try:
        if name == 'doctor':
            return doctor(args)
        if name == 'status':
            dump(request(args, '/api/status'), as_json)
            return 0
        if name == 'snapshot':
            dump(request(args, '/api/snapshot'), as_json)
            return 0
        if name == 'rpc':
            payload = parse_payload(args)
            data = rpc(args, args.name, payload)
            if data is None and args.name in PUSH_ONLY:
                print(f'{args.name}：已提交（这类命令只推补丁，界面里看效果）')
                return 0
            dump(data, as_json)
            return 0
        if name == 'tasks':
            return show_tasks(args, as_json)
        if name == 'run':
            payload = parse_payload(args)
            payload.setdefault('name', args.name)
            rpc(args, 'ops_task_run', payload)
            print(f'已提交：{args.name}（看 cli history 或界面「执行历史」）')
            return 0
        if name == 'history':
            snap = rpc(args, 'ops') or {}
            rows = ((snap.get('tasks') or {}).get('history')) or []
            limit = max(1, int(getattr(args, 'limit', 10) or 10))
            if as_json:
                dump(rows[:limit], True)
                return 0
            if not rows:
                print('（还没有执行记录）')
                return 0
            for row in rows[:limit]:
                mark = '跳过' if row.get('skipped') else (
                    '✓' if row.get('ok') else '✗')
                print(f"{mark} {row.get('name')} {row.get('ms')}ms "
                      f"{row.get('error') or row.get('summary') or ''}"[:120])
            return 0
        parser.print_help()
        return 0
    except CliError as error:
        print(f'✗ {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
