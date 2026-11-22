"""9.13 · 富途额度实测 —— 额度是**按「标的」计**，不是按周期

演示要点
--------
富途历史 K 线有**账户级额度**：**100 只股票 / 7 天滚动释放**（期权单独 20 只）。

| 操作 | 是否消耗额度 |
| --- | --- |
| 取一只**新**股票（任意周期） | ✅ 消耗 1 个 |
| **同一只股票重复取**（换周期也算） | ❌ 不额外消耗 |
| 期权 | 单独 20 只额度 |

所以「A股日线免费」是**错**的 —— 免费的是**已经取过的那只股票**，
与周期无关。本例会自适应地演示这一点：

1. 先找到一只**当前可用**的股票（额度满时可能是之前取过的）；
2. 对**同一只**再取另一个周期 → 通常仍然成功（不额外消耗）；
3. 再取几只**新**股票 → 额度满时会报
   ``历史K线额度不足（已用正股额度：100/100）``。

前置条件
--------
1. ``pip install futu-api``
2. 启动并登录 **FutuOpenD**（默认 ``127.0.0.1:11111``）
3. 开通对应市场的行情权限（A股可在富途牛牛免费申请）

运行：``python tutorials/data/14_futu_quota.py``
文档：``minibt_docs/docs/minibt_data/9.8_datasource.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *

#: 候选股票池（A股 + 港股 + 美股，找第一只「当前能取」的做演示 ✓）
CANDIDATES = ('600000', '600519', '000001', '300750', '00700', 'AAPL')


def _try(strategy, label: str, symbol: str, cycle: int,
         length: int = 120):
    """取一只 → 成功返回 KLine，失败打印错误并返回 None（不中断 ✓）"""
    try:
        kline = strategy.kline_from_futu(symbol, duration_seconds=cycle,
                                        data_length=length)
        print(f'  {label:12} {symbol:10} OK  {len(kline):>4} 根 | {kline.symbol}')
        return kline
    except Exception as error:                                   # noqa: BLE001
        first = str(error).splitlines()[0]
        print(f'  {label:12} {symbol:10} ERR {type(error).__name__}: {first}')
        return None


def main(gui=None):
    strategy = Strategy()

    print('富途额度实测（需要先启动 FutuOpenD）')
    print('规则：额度 = 100 只股票 / 7 天滚动；**同一只股票重复取不额外消耗**（与周期无关）')
    print('-' * 86)

    print('① 先找一只当前可用的股票（额度满时通常是之前取过的）')
    usable = None
    for code in CANDIDATES:
        if _try(strategy, '探测', code, 86400, 60) is not None:
            usable = code
            break
    if usable is None:
        print('\n  候选池全部不可用：额度已满（新股票都取不了，7 天后滚动释放）。')
    print()

    if usable is not None:
        print(f'② 同一只股票 {usable} 换周期再取（不额外消耗额度）')
        _try(strategy, '日线', usable, 86400, 120)
        _try(strategy, '5 分钟', usable, 300, 120)
        print()

    print('③ 换几只**新**股票（每只消耗 1 个额度；满了就报错）')
    for code in CANDIDATES:
        if code == usable:
            continue
        _try(strategy, '新标的', code, 86400, 120)

    print('-' * 86)
    print('提示：报错里会写「已用正股额度：x/100」，7 天后滚动释放；')
    print('      回测批量取数时：优先用 akshare / baostock，或一次取好存 CSV 复用。')


if __name__ == '__main__':
    main()
