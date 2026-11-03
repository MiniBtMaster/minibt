"""9.9 · resample / replay —— 周期转换

演示要点
--------
| 方法 | 方向 | 规则 |
| --- | --- | --- |
| ``kline.resample(cycle)`` | 低 → 高 | `cycle` 必须是主周期的**整数倍**，且 > 主周期 |
| ``strategy.resample(cycle, data=...)`` | 同上 | 同上；`rule='D'/'W'/'M'` 用于日以上 |
| ``strategy.replay(cycle, data=...)`` | 回放用 | 同上（`cycle` 必须是主周期倍数） |

常见 cycle（秒）：`300`(5分) / `900`(15分) / `1800`(30分) / `3600`(1时) /
`86400`(日) / `604800`(周) / `2592000`(月)。

⚠️ `get_kline(..., data_length=…)` 返回的 `datetime` 是 **tz-aware(UTC)**，
`resample` 以前会因此报 `Cannot mix tz-aware with tz-naive` —— **已修**
（在 `resample` 里统一去掉 tz）。本例最后一行就是验证。

运行：``python tutorials/data/09_resample.py``
文档：``minibt_docs/docs/minibt_data/9.9_resample.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline
    print('主周期:', kline.cycle, '秒 |', len(kline), '根')

    # ① KLine 上直接转
    r900 = kline.resample(900)
    print('① kline.resample(900)  ->', len(r900), '根 | cycle', r900.cycle)
    r3600 = kline.resample(3600)
    print('   kline.resample(3600) ->', len(r3600), '根 | cycle', r3600.cycle)

    # ② 非整数倍 / 低于主周期 → 报错
    for bad in (450, 60):
        try:
            kline.resample(bad)
        except AssertionError as error:
            print(f'② resample({bad}) → 预期报错: {error}')

    # ③ Strategy 上的 resample（⚠ 要求策略已初始化：先取一次数据）
    strategy = Strategy()
    base = strategy.get_kline(LocalDatas.test, duration_seconds=300,
                              data_length=2000)
    rs = strategy.resample(900, data=base)
    print('③ strategy.resample(900, data=base) ->', len(rs), '根')
    print("   （日以上用 rule='D'/'W'/'M'："
          "strategy.resample(86400, data=..., rule='D')）")

    # ④ replay（回放用，规则同上）
    rp = strategy.replay(900, data=base)
    print('④ strategy.replay(900) ->', len(rp), '根 | cycle', rp.cycle)

    # ⑤ tz-aware 的 K 线也能 resample（以前会 ValueError）
    sliced = strategy.get_kline(LocalDatas.test, duration_seconds=300,
                                data_length=1000)
    print('⑤ get_kline 的 datetime tz:', sliced.datetime.dt.tz,
          '| resample(900) ->', len(sliced.resample(900)), '根')


if __name__ == '__main__':
    main()
