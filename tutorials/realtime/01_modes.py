"""11.1 · 三种运行模式 —— 回测 / 回放 / 实时

演示要点
--------
| 模式 | 入口 | 说明 |
| --- | --- | --- |
| 回测 | `Bt().run(gui=...)` | 历史数据一次跑完 |
| 回放 | `Bt(replay=True).run(...)` 或 `Config(replay=True)` | 逐根"揭开"历史，模拟实时 |
| 实时 | `Bt(live=True).addTqapi(tq_auth(...)).run()` | 接天勤实时行情 |

三种模式共用**同一套**策略/指标/图表代码 —— 换的只是入口和 `Config`。

运行：``python tutorials/realtime/01_modes.py``（**不联网**，只打印配置）
文档：``minibt_docs/docs/minibt_realtime/11.1_modes.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    # ① 三个入口
    print('① 回测： Bt().run(gui="pylightcharts")')
    print('   回放： Bt(replay=True).run(...)   # 或 config=Config(replay=True)')
    print('   实时： Bt(live=True).addTqapi(tq_auth("账号", "密码"))'
          '.addstrategy(S).run()')

    # ② Config 里的模式开关
    for kwargs in ({}, {'replay': True}, {'on_close': False}):
        cfg = Config(**kwargs)
        print(f'② Config({kwargs}) -> replay={cfg.replay} '
              f'on_close={cfg.on_close}')

    # ③ 策略能感知自己是不是实盘
    print('③ Strategy.is_live_trading 存在:',
          hasattr(Strategy, 'is_live_trading'),
          '（策略里 self.is_live_trading 判断实盘）')

    # ④ 三个图表引擎（与模式正交）
    print('④ 引擎: Gui.Pylightcharts（原生）/ Gui.PylightchartsWeb（网页）'
          ' / Gui.Bokeh')
    print('   九种组合（3 引擎 × 3 场景）见 1.29 / tutorials/plots/')

    # ⑤ 回放的两个参数
    print('⑤ 回放参数：initial_candles（开局根数）/ '
          'replay_speed_ms（每根耗时）')


if __name__ == '__main__':
    main()
