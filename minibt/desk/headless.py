"""Headless server：不打开窗口，只跑 desk 后端 + 带 token 的 REST / SSE。

用法::

    # 本机（只在 127.0.0.1）
    python -m minibt.desk.headless --port 8765

    # 局域网 / 远程（一定要带 token；建议放在反向代理后面）
    python -m minibt.desk.headless --host 0.0.0.0 --port 8765 \\
        --token-name ci --token-scope read,trade

    # 只读 + 离线演示
    python -m minibt.desk.headless --offline --no-trading

鉴权
----
``--token-name`` 会现场签发一个 token 并打印（只打印一次）；也可以先在
界面「运维 → API Token」里生成。请求头任选一种::

    X-Desk-Token: <token>
    Authorization: Bearer <token>

REST 入口
---------
* ``GET  /api/status``    连接状态
* ``GET  /api/snapshot``  已创建页面的快照
* ``POST /api/rpc``       ``{"cmd": "workbench", "payload": {...}}``

SSE 入口 ``/events``（页面用；同样要 token）。
"""
from __future__ import annotations

import argparse
import json
import sys

from .app import Desk


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python -m minibt.desk.headless',
        description='minibt desk headless 服务（REST + SSE，带 token）')
    parser.add_argument('--host', default='127.0.0.1',
                        help='监听地址（默认 127.0.0.1；远程用 0.0.0.0）')
    parser.add_argument('--port', type=int, default=8765, help='端口')
    parser.add_argument('--title', default='minibt desk server')
    parser.add_argument('--offline', action='store_true',
                        help='离线演示数据（不连接行情）')
    parser.add_argument('--no-trading', action='store_true',
                        help='只读模式（拒绝所有下单）')
    parser.add_argument('--token-name', default='',
                        help='启动时签发一个 API token（名字）')
    parser.add_argument('--token-scope', default='read',
                        help='签发 token 的 scope（逗号分隔）')
    parser.add_argument('--token-ttl', type=int, default=7 * 86400,
                        help='token 有效期（秒；0=永久）')
    parser.add_argument('--json', action='store_true',
                        help='就绪后打印一行 JSON（URL / token）')
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    desk = Desk(title=args.title, theme='dark', browser=True,
                port=int(args.port), offline=bool(args.offline),
                allow_trading=not bool(args.no_trading))
    token = ''
    if args.token_name:
        ops = desk.ops_view()
        if ops is not None:
            item = ops.tokens.issue(
                args.token_name,
                scopes=str(args.token_scope or 'read'),
                ttl=int(args.token_ttl or 0))
            token = str(item.get('token') or '')
    from .web import serve

    if args.json:
        info = {'ready': True, 'host': args.host, 'port': int(args.port),
                'url': f'http://{args.host}:{args.port}/',
                'token': token, 'offline': bool(args.offline),
                'trading': not bool(args.no_trading)}
        print(json.dumps(info, ensure_ascii=False), flush=True)
    elif token:
        print(f'[desk] API token（只显示一次）：{token}', flush=True)
    try:
        serve(desk, open_browser=False, as_json=False, keep_alive=True,
              host=args.host)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            desk.close()
        except Exception:                                        # noqa: BLE001
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
