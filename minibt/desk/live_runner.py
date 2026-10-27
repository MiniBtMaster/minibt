"""策略实盘的**子进程**入口（`python -m minibt.desk.live_runner <file>`）

为什么要独立进程（P206）：

* `Bt(live=True).run()` 在**后台线程**里会把解释器卡住（tqsdk 的 asyncio +
  全局锁）→ 主线程的日志/停止动作全被挡住，关掉界面也停不下来，
  还会继续下单 ✗
* 放到子进程后：**停止 = terminate（进程级，100% 停得掉）**，
  desk 主线程完全不受影响；策略崩了也不会带崩界面 ✓

用法（由 `StrategyLive` 自动 spawn，一般不用手敲）::

    python -m minibt.desk.live_runner --file <策略.py> [--user u --password p]

日志：所有 stdout/stderr 直接输出（父进程逐行读走 → desk 运行日志）。
"""
from __future__ import annotations

import argparse
import os
import sys


def _auth(user: str, password: str):
    """天勤认证：优先用 desk 记住的账号（父进程通过 env 传进来）✓"""
    user = user or os.environ.get('MINIBT_TQ_USER', '')
    password = password or os.environ.get('MINIBT_TQ_PASSWORD', '')
    if not (user and password):
        return None
    from minibt.utils import tq_auth
    return tq_auth(user, password)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='minibt.desk.live_runner')
    parser.add_argument('--file', required=True, help='策略文件（.py）')
    parser.add_argument('--user', default='', help='天勤账号（也可用 env）')
    parser.add_argument('--password', default='', help='天勤密码（也可用 env）')
    parser.add_argument('--real', action='store_true',
                        help='连实盘账户（默认快期模拟）')
    parser.add_argument('--account-index', type=int, default=0,
                        help='账户页选中的账户下标（0=快期模拟，1=实盘）')
    args = parser.parse_args(argv)

    file = os.path.abspath(args.file)
    if not os.path.isfile(file):
        print(f'[实盘] 策略文件不存在：{file}', flush=True)
        return 2

    print(f'[实盘] 启动子进程 PID {os.getpid()}：{os.path.basename(file)}',
          flush=True)
    from minibt.bt import Bt
    from tqsdk import TqApi, TqAccount, TqKq, TqMultiAccount

    broker = os.environ.get('MINIBT_TQ_BROKER', '')
    account_id = os.environ.get('MINIBT_TQ_ACCOUNT', '')
    trade_password = os.environ.get('MINIBT_TQ_TRADE_PASSWORD', '')
    account_index = max(0, int(args.account_index or 0))
    auth = _auth(args.user, args.password)
    accounts = [TqKq()]
    if args.real:
        if not (broker and account_id and trade_password):
            print('[实盘] 缺少实盘公司 / 资金账号 / 交易密码，无法连接实盘账户',
                  flush=True)
            return 4
        accounts.append(TqAccount(broker, account_id, trade_password))
    if account_index >= len(accounts):
        print(f'[实盘] 账户下标 {account_index} 不存在（共 {len(accounts)} 个）',
              flush=True)
        return 5
    if auth is None:
        print('[实盘] 没有天勤账号 → 无法连接', flush=True)
        return 6
    target = TqMultiAccount(accounts) if len(accounts) > 1 else accounts[0]
    api = TqApi(target, auth=auth)

    bt = Bt(live=True)
    bt.addTqapi(api=api)
    selected = accounts[account_index]
    print(f'[实盘] 账户：{type(selected).__name__}'
          f'（index={account_index}，共 {len(accounts)} 个）', flush=True)
    bt.addstrategy(file, account=selected)
    if not bt.strategies:
        print('[实盘] 文件里没有 Strategy 子类', flush=True)
        return 3
    print('[实盘] 策略：%s' % ', '.join(c.__name__ for c in bt.strategies),
          flush=True)
    try:
        bt.run(isplot=False)
    except KeyboardInterrupt:
        print('[实盘] 收到中断，退出', flush=True)
    finally:
        try:
            bt.close()
        except Exception:                                        # noqa: BLE001
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
