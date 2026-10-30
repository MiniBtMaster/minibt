"""11.7 · 实盘调试清单

演示要点
--------
实盘出问题**九成**是这几件事，按顺序查：

1. **账号/权限**：`tq_auth` 对不对？该合约有没有交易权限？
2. **交易时段**：非交易时段 `wait_update()` 会一直阻塞（用 `deadline`）。
3. **合约代码**：`DCE.pp2609`（交易所.合约），主连是 `KQ.m@DCE.pp`。
4. **日志**：`Config(islog=True, islogorder=True)` 看委托/成交。
5. **下单参数**：`insert_order(direction=..., offset=...)` 的
   `BuyOpen/SellClose` 有没有搞反。

运行：``python tutorials/realtime/07_live_debug.py``
文档：``minibt_docs/docs/minibt_realtime/11.7_live_debug.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    print('① 实盘调试清单：')
    for i, item in enumerate((
        '账号/交易权限',
        '交易时段（非时段 wait_update 会阻塞）',
        '合约代码格式（交易所.合约 / 主连 KQ.m@...）',
        '日志（islog / islogorder）',
        '下单方向与开平（BuyOpen / SellClose …）',
    ), 1):
        print(f'   {i}. {item}')

    # ② 日志配置
    cfg = Config(islog=True, islogorder=True, print_account=True)
    print('② logger_params =', cfg.logger_params)
    print('   log_to_file =', cfg.log_to_file,
          '| auto_clean_days =', cfg.auto_clean_days)

    # ③ 账号对象自检（不联网）
    auth = tq_auth('demo_user', 'demo_password')
    print('③ tq_auth 自检: user_name =', auth.user_name,
          '| 有 password 字段:', hasattr(auth, 'password'))

    # ④ 最小自检脚本（只订阅、不下单）
    print('④ 最小自检（只订阅，不下单）：')
    print('     api = TqApi(auth=TqAuth("账号", "密码"))')
    print('     quote = api.get_quote("DCE.pp2609")')
    print('     while api.wait_update():  print(quote.last_price)')

    # ⑤ 别做的事
    print('⑤ 调试时不要：直接实盘下单、频繁撤单、跳过交易时段检查')


if __name__ == '__main__':
    main()
