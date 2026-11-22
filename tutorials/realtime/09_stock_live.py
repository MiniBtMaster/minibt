"""11.9 · 股票实时（富途 OpenD）—— StockApi / addStockapi / 实时图表

演示要点
--------
期货用 ``tq_auth`` + ``addTqapi``；**股票完全对称**：

```python
bt = Bt(live=True)
bt.addStockapi()                 # 富途 OpenD（默认 127.0.0.1:11111）
bt.addstrategy(MyStrategy)
bt.run()                         # 实时图表（关窗 / Ctrl+C 结束）
```

| 成员 | 说明 |
| --- | --- |
| `StockApi(host, port, trade=...)` | 富途行情/交易接口（与 `TqApi` **同形**） |
| `Bt.addStockapi(api=None, host=, port=, **kw)` | 挂上 StockApi（等价 `addTqapi`） |
| `Bt.addstock(symbol, cycle)` | 可选：预先订阅一只（不调也会按需订阅） |
| `Strategy.get_kline('SH.600000', 60, 300)` | 实时 K 线（**同一个 DataFrame 原地滚动**） |
| `Strategy.set_target_size(n)` | 目标仓位 → `StockTargetPosTask` → 下单 |

⚠ **默认 `trade=False`**：只连行情，策略下单走**本地模拟成交**（不会动真钱）。
真实交易传 ``trade=True, trd_env='SIMULATE'``（先模拟盘，再 ``REAL``）。

前置：``pip install futu-api`` + 启动并登录 **FutuOpenD**（窗口底部显示「已连接」）。

运行：
     ``python tutorials/realtime/09_stock_live.py``          打开实时图表
     ``python tutorials/realtime/09_stock_live.py --check``  只检查连接（不打开图表）

文档：``minibt_docs/docs/minibt_realtime/11.6_futu.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *                                  # noqa: E402,F403

#: 演示标的（浦发银行；换成 ``000001`` / ``HK.00700`` / ``AAPL`` 也行 ✓）
SYMBOL = 'SH.600000'
CYCLE = 60          # 1 分钟


class MaCross(Strategy):
    """双均线 + 目标仓位（适合演示；**不是投资建议** ✓）"""

    params = dict(fast=5, slow=20)

    def __init__(self):
        # 实盘模式：从 StockApi 取**实时 K 线**（同一个 DataFrame 原地滚动 ✓）
        self.kline = self.get_kline(SYMBOL, CYCLE, 300)
        self.fast_ma = self.kline.close.sma(self.params.fast)
        self.slow_ma = self.kline.close.sma(self.params.slow)

    def next(self):
        if self.fast_ma.cross_up(self.slow_ma).new:
            self.set_target_size(size=100)        # 目标 100 股（够真实成交 ✓）
        elif self.fast_ma.cross_down(self.slow_ma).new:
            self.set_target_size(size=0)          # 清仓


def check() -> bool:
    """只检查连接 + 取一段 K 线（不打开图表 ✓）"""
    try:
        api = StockApi()
    except Exception as error:                           # noqa: BLE001
        print(f'✗ 连不上 FutuOpenD：{error}')
        print('  请先启动并登录 FutuOpenD（默认 127.0.0.1:11111），'
              '再 pip install futu-api')
        return False
    try:
        data = api.get_kline_serial(SYMBOL, CYCLE, 120)
        quote = api.get_quote(SYMBOL)
        print(f'✓ 已连接 | {SYMBOL} 最新 {quote.last_price} | '
              f'K 线 {len(data)} 根 | price_tick={quote.price_tick}')
        return True
    finally:
        api.close()


def main(gui=None):
    if '--check' in sys.argv[1:]:
        check()
        return

    if not check():
        return

    # ① 挂 StockApi（只行情；要真实交易：trade=True, trd_env='SIMULATE'）
    bt = Bt(live=True)
    bt.addStockapi()
    # ② 手动加策略（和期货一模一样 ✓）
    bt.addstrategy(MaCross)
    # ③ 打开实时图表（关窗 / Ctrl+C 结束）
    print('打开实时图表…（策略默认只做**本地模拟成交**，不会动真钱）')
    bt.run()


if __name__ == '__main__':
    main()
