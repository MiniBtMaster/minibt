"""11.2 · tqsdk 接入 —— `tq_auth` / `addTqapi` / `wait_update`

演示要点
--------
```python
bt = Bt(live=True)
bt.addTqapi(tq_auth('账号', '密码'))          # 快期模拟：再传 tq_account=TqKq()
bt.addstrategy(MyStrategy)
bt.run()                                     # 阻塞，直到 Ctrl+C / 窗口关闭
```

| 成员 | 说明 |
| --- | --- |
| `tq_auth(user_name, password)` | 天勤账号（**不联网**，只是配置对象） |
| `Bt.addTqapi(tq_auth=..., tq_account=..., api=...)` | 挂上 TqApi；也可直接传已有 `api` |
| `Strategy.wait_update(deadline=60)` | 等下一笔行情（超时返回 False） |
| `Strategy.api` | 当前 TqApi 实例 |
| `Strategy.is_live_trading` | 是否实盘模式 |

⚠ **本页不联网、不下单**。真连需要账号 + 交易时段；测试时务必用**快期模拟**
（`TqKq()`）或只订阅不下单。

运行：``python tutorials/realtime/02_tq_auth.py``
文档：``minibt_docs/docs/minibt_realtime/11.2_tq_auth.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    # ① 账号对象（纯配置，不联网）
    auth = tq_auth('demo_user', 'demo_pass')
    print('① tq_auth ->', type(auth).__name__, '| 字段:',
          [n for n in dir(auth) if not n.startswith('_')][:5])
    print('   user_name =', auth.user_name)

    # ② 挂载到 Bt 的写法（不执行，只示意）
    print('② bt = Bt(live=True)')
    print('   bt.addTqapi(tq_auth=tq_auth("账号", "密码"))')
    print('   bt.addTqapi(tq_account=TqKq())      # 快期模拟盘')
    print('   bt.addTqapi(api=已有TqApi)           # 复用连接')

    # ③ 策略里的实时循环
    print('③ def next(self):')
    print('       if not self.wait_update(deadline=60):   # 等下一笔行情')
    print('           return')
    print('       # ... 用 self.data.current_close 等最新值做判断')

    # ④ 关键区别
    print('④ 回测是"一次跑完"；实时是 wait_update() 循环里逐笔推进，'
          '指标/图表自动增量更新')


if __name__ == '__main__':
    main()
