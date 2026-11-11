"""9.7 · 指标代理机制 —— 为什么 `kline` 上有 672 个方法

演示要点
--------
minibt 把**指标库类**（`PandasTa` / `TaLib` / `TradingView` / `TqTa` / `TqFunc` /
`TuLip` / `FinTa` / `Pair` / `Factors` / `BtInd` / `Pine`）里的每个指标方法，
在初始化时**挂到数据类**（`KLine` / `IndFrame` / `IndSeries` / `Line`）上。

于是：

| 写法 | 说明 |
| --- | --- |
| ``kline.macd()`` | **代理**调用（等价 ``kline.pta.macd()``） |
| ``kline.pta.ema(20)`` | 显式走 **PandasTa** 门面（**已绑定数据源，别再传源**） |
| ``kline.talib.EMA(timeperiod=20)`` | 显式走 **TA-Lib** 门面 |
| ``kline.tradingview.Xxx()`` | 显式走 **TradingView** 门面 |
| ``kline.close.ema(20)`` | `Line` 上也能代理调用 |

**指标登记键**（`_btindicatordataset` 的 key）= `<库前缀><指标名>`：
`pta_` / `talib_` / `ti_` / `finta_` / `pair_` / `factor_` / `tqta_` / `tqfunc_` /
`btind_` / `pine_` / `tv_`；止损线是 `stop_lines`。

运行：``python tutorials/data/07_proxy.py``
文档：``minibt_docs/docs/minibt_data/9.7_proxy.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    kline = LocalDatas.test.kline

    # ① 方法从哪来
    print('① dir(kline) 公开成员数:', len(
        [n for n in dir(kline) if not n.startswith('_')]))
    print('   kline.macd 的 qualname =', kline.macd.__qualname__,
          '（还是库里的名字）')

    # ② 12 个指标库门面
    for name in ('pta', 'talib', 'tradingview', 'tqta', 'tqfunc', 'tulip',
                 'finta', 'pine', 'btind', 'pairtrading', 'tradingsystem',
                 'ta'):
        print(f'② kline.{name:14s} -> {type(getattr(kline, name, None)).__name__}')

    # ③ 代理 vs 显式门面：结果一致（⚠ 比尾部，EMA 前 19 个是 NaN，NaN != NaN）
    a = kline.close.ema(20)          # 代理（= PandasTa.ema）
    b = kline.pta.ema(20)            # 显式 PandasTa 门面
    print('③ 代理/门面 结果一致:', list(a[-5:]) == list(b[-5:]),
          '| 类型:', type(a).__name__)

    # ④ 不同库的同一个指标（TA-Lib 版）——门面已绑定数据源，**别再传**
    c = kline.talib.EMA(timeperiod=20)
    print('④ kline.talib.EMA ->', type(c).__name__, '| len:', len(c))

    # ⑤ 指标登记键（= 库前缀 + 指标名）
    print('⑤ macd().sname =', kline.macd().sname,
          '| close.ema(20).sname =', kline.close.ema(20).sname,
          '| talib EMA 的 sname =', c.sname)

    # ⑥ 撞名：列名和 pandas/库方法同名时，属性访问拿到的是**方法**
    macd = kline.macd()
    print('⑥ macd.diff ->', type(macd.diff).__name__,
          '（pandas 的 DataFrame.diff，不是列）')
    print('   macd["macdx"] ->', type(macd['macdx']).__name__)

    # ⑦ 门面调用：数据源已经绑在门面上，只传指标参数
    rsi1 = kline.close.rsi(14)              # 代理
    rsi2 = kline.pta.rsi(length=14)         # 显式门面（等价）
    print('⑦ 两种 rsi 一致:', list(rsi1[-5:]) == list(rsi2[-5:]))


if __name__ == '__main__':
    main()
