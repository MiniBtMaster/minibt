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
from typing import Any, Dict, List, Optional


def _auth(user: str, password: str):
    """天勤认证：优先用 desk 记住的账号（父进程通过 env 传进来）✓

    ⚠ 必须返回 **`tqsdk.TqAuth`**：`TqApi(auth=...)` 只认 `TqAuth` 实例或
    ``"用户名,密码"`` 字符串，其它对象会被当成“没传” → `self._auth = None` →
    直接抛「请输入 auth（快期账户）参数」✗。
    （`minibt.tq_auth` 是数据类，只能给 `Bt.addTqapi(tq_auth=...)` 用，
    内部会 `TqAuth(**values)`；直接塞给 `TqApi` 是不行的 ✓）
    """
    user = (user or os.environ.get('MINIBT_TQ_USER', '') or '').strip()
    password = password or os.environ.get('MINIBT_TQ_PASSWORD', '') or ''
    if not (user and password):
        return None
    from tqsdk import TqAuth
    return TqAuth(user, password)


def _bar_stamp(strategy) -> Optional[int]:
    """策略当前**最后一根 K 线**的时间戳（判断“新K线”用）✓

    取所有 KLine 数据集里最大的 ``datetime``（多合约策略：任一合约出新 K 线
    都算新 K 线 ✓）；拿不到就返回 None（= 不做新 K 线门控）。
    """
    stamps: List[int] = []
    try:
        datasets = getattr(strategy, '_btklinedataset', None) or {}
        rows = datasets.values() if hasattr(datasets, 'values') else []
    except Exception:                                            # noqa: BLE001
        rows = []
    for item in rows:
        try:
            last = item.datetime.iloc[-1]
        except Exception:                                        # noqa: BLE001
            continue
        try:
            # pandas.Timestamp 有 `.value`（ns）；纯数字（测试 / 自定义数据）直接转 ✓
            stamps.append(int(getattr(last, 'value', last)))
        except (TypeError, ValueError):
            continue
    return max(stamps) if stamps else None


def _stop_step_for_tick(strategy) -> None:
    """把这一次的 `step()` 换成 no-op（只算指标、不跑交易逻辑 ✓）"""
    try:
        strategy.step = lambda *args, **kwargs: None
    except Exception:                                            # noqa: BLE001
        pass


def _install_control(strategies, file: str) -> None:
    """把「新K线next / 运行next」两个开关接到**实盘循环**上 ✓

    用户 2026-10-29 实测：两个开关点了没反应（策略还是每 2 秒跑一次 `next`）。

    坑在这里：用户策略写的是 ``def next(self)``，而 minibt 在
    `_prepare_before_strategy_start()` 里把 **实例的** ``self.step = self.next``
    绑定了 —— 以前只包**类**上的 `step`，被这个实例属性整个盖掉 → 门控从来没生效 ✗。

    现在改包 ``_execute_live_trading()``（每个 tick 必经、且无论 `next` / `step`
    哪种写法都走它）：

    * ``run_next=False`` → 照常更新 K 线 / 指标（`_strategy_init`），
      但把这一次的 `step()` 换成 no-op（= 只算指标 ✓）；
    * ``next_on_new_bar=True`` → 只有**出现新 K 线**才跑交易逻辑，
      同一根 K 线上来的重复 tick 只更新指标 ✓；
    * 开关由 desk 写进控制文件（`live_control`），这里每个 tick 读一次
      （按 mtime 缓存，开销可忽略）—— 也就是父子进程之间的控制通道 ✓。

    「最后一根 K 线」记在**文件级**（不是 `id(instance)`）：minibt 实盘有时会
    重建策略实例，按实例记会每拍都当成“新 K 线” ✗。
    """
    from . import live_control

    state: Dict[str, Any] = {'stamp': None, 'settings': None}

    def _wrap(cls):
        original = getattr(cls, '_execute_live_trading', None)
        if not callable(original):
            return

        def execute(self, *args, **kwargs):
            settings = live_control.read(file)
            # 开关变化时打一行（用户在「运行日志」里能确认子进程收到了 ✓）
            if settings != state['settings']:
                state['settings'] = dict(settings)
                try:
                    print('[实盘] 控制：next_on_new_bar='
                          f'{settings.get("next_on_new_bar")}, '
                          f'run_next={settings.get("run_next")}', flush=True)
                except Exception:                                # noqa: BLE001
                    pass
            run_next = settings.get('run_next', True) is not False
            new_bar = True
            if settings.get('next_on_new_bar', True) is not False:
                stamp = _bar_stamp(self)
                if stamp is not None:
                    new_bar = state['stamp'] != stamp
                    if new_bar:
                        state['stamp'] = stamp
            if run_next and new_bar:
                return original(self, *args, **kwargs)
            # 只算指标：保留 K 线 / 指标更新，跳过这一次的交易逻辑 ✓
            # ⚠ 用完必须把 `step` 还原，否则之后开「运行next」也永远跑不起来了 ✗
            saved = getattr(self, 'step', None)
            _stop_step_for_tick(self)
            try:
                return original(self, *args, **kwargs)
            finally:
                if saved is not None:
                    try:
                        self.step = saved
                    except Exception:                        # noqa: BLE001
                        pass

        execute.__name__ = '_execute_live_trading'
        setattr(cls, '_execute_live_trading', execute)

    for cls in list(strategies or []):
        _wrap(cls)


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
        # ★ 快期模拟（TqKq）**同样**需要快期账号 auth，不是只有实盘才要 ✓
        print('[实盘] 缺少天勤（快期）账号 / 密码 → 无法连接；'
              '快期模拟（TqKq）也需要 auth：请先在 desk「登录」里登录快期账号',
              flush=True)
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
    # ★ 运行开关（策略管理弹窗里的「新K线next / 运行next」）✓
    _install_control(bt.strategies, file)
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
