"""desk 最小示例：报价窗口 + 看盘窗口（UI 全是 JS/TS）。

运行：
    python -m minibt.desk.demo --offline          # 离线（不连网，看界面 ✓）
    python -m minibt.desk.demo                    # 期货（需要天勤账号）
    python -m minibt.desk.demo --browser          # 浏览器壳
    python -m minibt.desk.demo --futures 账号 密码 # 直连期货
    python -m minibt.desk.demo --stocks            # 加富途 OpenD（股票 chips）

文档：minibt_docs/docs/minibt_desk/13.1_desk.md
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from minibt.desk.app import Desk      # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='minibt 行情终端（desk）')
    parser.add_argument('--offline', action='store_true',
                        help='离线演示数据（不连天勤/富途）')
    parser.add_argument('--browser', action='store_true', help='浏览器壳')
    parser.add_argument('--port', type=int, default=0, help='浏览器壳端口（0=随机）')
    parser.add_argument('--theme', default='dark', choices=('dark', 'light'))
    parser.add_argument('--stocks', action='store_true', help='接富途 OpenD')
    parser.add_argument('--futures', nargs=2, metavar=('USER', 'PASSWORD'),
                        help='天勤账号（模拟盘）；不给则只做离线演示')
    args = parser.parse_args()

    desk = Desk(title='minibt桌面端', theme=args.theme, browser=args.browser,
                port=args.port, offline=args.offline)

    if args.futures:
        from minibt import tq_auth
        user, password = args.futures
        try:
            desk.add_futures(tq_auth=tq_auth(user, password))
            print('[desk] 期货已连接（快期模拟）')
        except Exception as error:                                # noqa: BLE001
            print(f'[desk] 期货连接失败，转离线演示: {error!r}')
            desk.offline = True
    else:
        desk.offline = True
        print('[desk] 未提供天勤账号 → 离线演示数据')

    if args.stocks:
        try:
            desk.add_stocks()
            print('[desk] 股票已连接（富途 OpenD）')
        except Exception as error:                                # noqa: BLE001
            print(f'[desk] 股票连接失败（只影响股票页）: {error!r}')

    desk.run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
