"""``minibt`` 命令行入口。

    minibt desk                          # 股票（OpenD 已开）；都没连上 → 离线本地图表
    minibt desk --user 账号 --password 密码   # 期货 + 股票
    minibt desk --user 账号 --password 密码 --no-stocks
    minibt desk --offline                # 离线：直接打开本地图表 ✓
    minibt desk --browser                # 浏览器壳

连接规则（4 种情况）：

| 期货 | 股票 | 结果 |
| --- | --- | --- |
| ✅ | ✅ | 两个都进（报价页可切「股票」） |
| ✅ | ❌ | 只期货（股票 chips 无数据，会有提示） |
| ❌ | ✅ | 只股票（期货页无数据） |
| ❌ | ❌ | **离线模式**：不加载首页 / 行情，直接打开本地图表 |

> 富途网关**不需要账号**（只要打开并登录 FutuOpenD，默认 127.0.0.1:11111）——
> 所以不输天勤账号也能看股票行情。
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, List, Optional, Tuple


#: 环境变量 → ``(参数名, 对应的命令行开关)``
#:
#: VS Code 扩展 / CI 用：**密码走环境变量**（不出现在命令行 / `ps` 里 ✓）。
#: 命令行给了的参数**永远优先**（这里只补没给的那些 ✓）。
ENV_ARGS = (
    ('MINIBT_TQ_USER', 'user', ('--user', '--天勤账号')),
    ('MINIBT_TQ_ACCOUNT', 'user', ('--user', '--天勤账号')),
    ('MINIBT_TQ_PASSWORD', 'password', ('--password', '--天勤密码')),
    ('MINIBT_FUTU_HOST', 'futu_host', ('--futu-host',)),
    ('MINIBT_FUTU_PORT', 'futu_port', ('--futu-port',)),
    ('MINIBT_DESK_TITLE', 'title', ('--title',)),
    ('MINIBT_DESK_THEME', 'theme', ('--theme',)),
    ('MINIBT_DESK_PORT', 'port', ('--port',)),
    ('MINIBT_DESK_BROWSER', 'browser', ('--browser',)),
    ('MINIBT_DESK_NO_BROWSER', 'no_browser', ('--no-browser',)),
    ('MINIBT_DESK_OFFLINE', 'offline', ('--offline',)),
    ('MINIBT_DESK_NO_STOCKS', 'no_stocks', ('--no-stocks',)),
)

#: 布尔型参数（环境变量里 `1/true/yes/on` 都算真 ✓）
ENV_FLAGS = ('browser', 'offline', 'no_stocks', 'no_browser')

#: 整型参数
ENV_INTS = ('futu_port', 'port')


def _truthy(text) -> bool:
    return str(text or '').strip().lower() in ('1', 'true', 'yes', 'on', 'y')


def apply_env_defaults(args, environ=None, argv=None) -> None:
    """把环境变量填进**命令行没给**的参数（命令行优先级更高 ✓）

    用途：VS Code 扩展把账号放 settings、密码放 SecretStorage，然后**通过
    环境变量**传给子进程 —— 这样密码不会出现在命令行 / `ps` 列表里 ✓

    Args:
        args: :func:`build_parser` 解析出来的命名空间
        environ: 环境变量字典（默认 ``os.environ``，测试可注入）
        argv: 原始命令行（用来判断“用户到底有没有显式给这个开关”）
    """
    import os

    env = os.environ if environ is None else environ
    given = set(argv or ())
    for name, attr, flags in ENV_ARGS:
        value = env.get(name)
        if value is None or value == '':
            continue
        if any(flag in given for flag in flags):
            continue                     # 命令行显式指定 → 不覆盖 ✓
        if attr in ENV_FLAGS:
            if not getattr(args, attr, False) and _truthy(value):
                setattr(args, attr, True)
            continue
        if attr in ENV_INTS:
            try:
                setattr(args, attr, int(value))
            except (TypeError, ValueError):
                pass
            continue
        setattr(args, attr, value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='minibt', description='minibt 命令行')
    sub = parser.add_subparsers(dest='command')
    desk = sub.add_parser(
        'desk', help='行情终端（报价 + 看盘），UI 全在 JS/TS')
    desk.add_argument('--user', '--天勤账号', dest='user', default='',
                      help='天勤账号（快期）；不给则只连股票')
    desk.add_argument('--password', '--天勤密码', dest='password', default='',
                      help='天勤密码')
    desk.add_argument('--futu-host', default='127.0.0.1',
                      help='FutuOpenD 地址（默认 127.0.0.1，**不需要账号**）')
    desk.add_argument('--futu-port', type=int, default=11111,
                      help='FutuOpenD 端口（默认 11111）')
    desk.add_argument('--no-stocks', action='store_true',
                      help='不连股票（只期货）')
    desk.add_argument('--offline', action='store_true',
                      help='离线：直接打开本地图表（不连任何网关）')
    desk.add_argument('--browser', action='store_true', help='浏览器壳')
    desk.add_argument('--no-browser', dest='no_browser', action='store_true',
                      help='浏览器壳：**不自动打开系统浏览器**'
                           '（VS Code 扩展等自己托管页面时用）')
    desk.add_argument('--port', type=int, default=0,
                      help='浏览器壳端口（0=随机）')
    desk.add_argument('--theme', choices=('dark', 'light'), default='dark')
    desk.add_argument('--check', action='store_true',
                      help='只检查连接与合约数量（不打开窗口，排查数据问题）')
    desk.add_argument('--json', action='store_true',
                      help='输出 JSON（--check 的体检报告 / 就绪信息，'
                           '方便脚本与 VS Code 扩展采集）')
    desk.add_argument('--quiet', action='store_true',
                      help='运行日志不再打印到终端（默认打印，方便排查 ✓）')
    desk.add_argument('--no-ui-log', dest='no_ui_log', action='store_true',
                      help='运行日志不推到界面（只在终端打印；界面卡时用 ✓）')
    desk.add_argument('--title', default='minibt桌面端')
    return parser


def build_desk(args, *, log=print) -> Tuple[Any, bool, bool]:
    """按参数建好 :class:`~minibt.desk.app.Desk` → ``(desk, 期货?, 股票?)``

    只建连接，**不启动窗口**（方便测试 / 其他程序嵌入 ✓）。
    """
    from .desk.app import Desk

    desk = Desk(title=args.title, theme=args.theme, browser=args.browser,
                port=args.port, offline=bool(args.offline),
                allow_trading=True)
    # 由 VS Code 扩展 / 自己的外壳托管页面时，别再弹系统浏览器 ✓
    desk.open_browser = not bool(getattr(args, 'no_browser', False))
    # ★ 运行日志默认**同时打印到终端**（界面卡住也能复制 ✓）
    desk.log_to_stdout = not bool(getattr(args, 'quiet', False))
    desk.log_to_ui = not bool(getattr(args, 'no_ui_log', False))
    # 启动就打印「实际跑的代码在哪」——排查「改了代码没生效」最快 ✓
    for line in desk.code_info().splitlines():
        log(f'[minibt desk] {line}')
    if args.offline:
        log('[minibt desk] 离线演示模式（不连任何网关）')
        return desk, False, False

    futures_ok = False
    if args.user and args.password:
        try:
            from .utils import tq_auth
            desk.add_futures(tq_auth=tq_auth(args.user, args.password))
            futures_ok = True
            desk.home_on_boot = True      # 命令行带账号 → 启动显示首页 ✓
            log('[minibt desk] 期货已连接（快期模拟）')
        except Exception as error:                               # noqa: BLE001
            log(f'[minibt desk] 期货连接失败：{error!r}')
    else:
        log('[minibt desk] 未提供天勤账号 → 跳过期货')

    stocks_ok = False
    if not args.no_stocks:
        try:
            desk.add_stocks(host=args.futu_host, port=args.futu_port)
            stocks_ok = True
            log(f'[minibt desk] 股票已连接（FutuOpenD '
                f'{args.futu_host}:{args.futu_port}）')
        except Exception as error:                               # noqa: BLE001
            log(f'[minibt desk] 股票连接失败（FutuOpenD 没开？）：{error!r}')
    else:
        log('[minibt desk] --no-stocks → 跳过股票')

    if not futures_ok and not stocks_ok:
        # ★ 无服务（天勤没账号 + FutuOpenD 没开）不退出：前端会打开
        #   「本地图表」作为离线首页；不要塞 offline_rows 假数据 ✓
        desk.offline = False
        desk.no_service = True
        log('[minibt desk] 未连接行情源 → 离线模式（本地图表）')
    return desk, futures_ok, stocks_ok


def check(desk, log=print, as_json: bool = False) -> int:
    """打印行情连通性 + 每个类型/交易所的合约数量（`--check` ✓）

    Args:
        as_json: ``True`` → 直接输出 JSON（`--check --json`，给脚本用 ✓）

    Returns:
        0 = 至少有一路有数据；2 = 全都没有
    """
    from .desk import symbols as _symbols

    report = {'minibt': None, 'futures': None, 'stocks': None,
              'total': 0, 'indicators': None}
    try:
        import minibt as _pkg
        path = getattr(_pkg, '__file__', None) or '?'
        report['minibt'] = {'path': path,
                            'version': str(getattr(_pkg, '__version__', '?'))}
        log(f'[minibt] {path}（v{report["minibt"]["version"]}）')
    except Exception as error:                                   # noqa: BLE001
        log(f'[minibt] 导入失败 {error!r}')
    total = 0
    # 指标模块自检（安装不完整时这里直接告诉用户怎么修 ✓）
    try:
        from .desk import indicator_catalog as _cat
        ind = _cat.diagnose()
        report['indicators'] = ind
        if ind['ok']:
            log(f"[指标] 就绪　{len(ind['files'])} 个模块（{ind['root']}）")
        else:
            log('[指标] [!] 缺少：' + ', '.join(ind['missing']))
            log('[指标] 修复：cd <repo>/minibt && python -m pip install -e .')
    except Exception as error:                                   # noqa: BLE001
        log(f'[指标] 自检失败 {error!r}')
    if getattr(desk, 'futures', None) is not None:
        feed = desk.futures
        log('[期货] 已连接')
        for kind, label in (('FUT', '期货'), ('CONT', '主连')):
            for exchange, name in _symbols.DEFAULT_EXCHANGES.get(kind, []):
                try:
                    rows = feed.contracts(kind, exchange)
                except Exception as error:                       # noqa: BLE001
                    log(f'  {label}/{name}: 失败 {error!r}')
                    continue
                total += len(rows)
                head = rows[0] if rows else '-'
                report['futures'] = report['futures'] or {'markets': []}
                report['futures']['markets'].append(
                    {'kind': kind, 'market': exchange, 'name': name,
                     'count': len(rows), 'example': head if rows else ''})
                log(f'  {label}/{name}: {len(rows)} 个（例：{head}）')
    else:
        log('[期货] 未连接')

    if getattr(desk, 'stocks', None) is not None:
        from .desk import stocks as _stocks
        api = getattr(desk.stocks, 'api', None)
        report['stocks'] = {'info': _stocks.connection_info(api),
                            'markets': []}
        log(f'[股票] 已连接　{_stocks.connection_info(api)}')
        for market in ('SSE', 'SZSE', 'HK', 'US'):
            try:
                info = _stocks.probe(api, market)
            except Exception as error:                           # noqa: BLE001
                log(f'  {market}: 失败 {error!r}')
                continue
            total += info['count']
            report['stocks']['markets'].append(info)
            line = f"  {market}: {info['count']} 个"
            if info['example']:
                line += f"（例：{info['example']}）"
            if info['error']:
                line += f"　[!] {info['error']}"
            log(line)
        if getattr(_stocks, 'last_error', ''):
            log(f'  [!] 最近一次失败原因：{_stocks.last_error}')
            log('  （A 股基础信息需要富途「行情权限/额度」；'
                '打开 FutuOpenD 后用它的行情权限页确认）')
    else:
        log('[股票] 未连接')

    report['total'] = total
    report['ok'] = bool(total)
    if as_json:
        import json as _json
        print(_json.dumps(report, ensure_ascii=False, indent=2))
    else:
        log(f'\n[结论] 合约总数 = {total}'
            + ('（有数据 [OK]）' if total else '（没有数据 [X] 检查网关/账号/权限）'))
    return 0 if total else 2


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # ★ 友好兜底：`minibt --check`（漏了 `desk`）也当成 `minibt desk --check` ✓
    if argv and argv[0].startswith('-') and argv[0] not in ('-h', '--help'):
        if any(item in ('--check', '--json') or item.startswith('--user')
               or item.startswith('--天勤') or item in ('--browser', '--offline')
               for item in argv):
            argv = ['desk'] + argv
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != 'desk':
        parser.print_help()
        return 0
    apply_env_defaults(args, argv=argv)   # 环境变量兜底（命令行优先 ✓）

    desk, futures_ok, stocks_ok = build_desk(args)
    if getattr(args, 'check', False):
        return check(desk, as_json=bool(getattr(args, 'json', False)))
    if not futures_ok and stocks_ok:
        print('[minibt desk] 只有股票行情（期货页无数据）')
    if futures_ok and not stocks_ok:
        print('[minibt desk] 只有期货行情（股票页无数据）')
    try:
        desk.run(as_json=bool(getattr(args, 'json', False)))
    finally:
        close = getattr(desk, 'close', None)
        if callable(close):
            close()               # 再兜一次（幂等）：别留 tqsdk pending 任务 ✓
    return 0


if __name__ == '__main__':                                    # pragma: no cover
    sys.exit(main())
