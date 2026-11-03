"""指标信号回测示例（无需 Strategy 类）✓

`IndFrame.signal_backtest()` 用指标里的**交易信号**直接跑一遍快速回测：
你只要在指标里算出 `long_signal` / `short_signal`
（以及可选的 `exitlong_signal` / `exitshort_signal`），剩下的开平仓、
手续费、统计报表都由 minibt 处理。

和「策略回测」的区别：

| | 策略（`Strategy`）| 指标信号（`BtIndicator`）|
|---|---|---|
| 写法 | 类 + `next()` + `buy()/sell()` | 只算信号线 |
| 引擎 | backtrader | Cython 快速回测 |
| 参数优化 | `op_config = OpConfig(...)` | `signal_backtest(optimize=OptimizeConfig(...))` |

跑法：

    python tutorials/basic/signal_backtest.py

也可以在 **minibt desk / miniqt** 的编辑器里打开本文件，
用「策略回测 / 参数优化」按钮（指标信号与策略共用这两个按钮）。
"""
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from minibt import *                                          # noqa: F401,F403


# --------------------------------------------------------------- 指标 + 信号
class MyMACross(BtIndicator):
    """双均线交叉：金叉做多 / 死叉做空，反手时平掉旧仓 ✓"""

    lines = ['ma1', 'ma2', 'long_signal', 'short_signal',
             'exitlong_signal', 'exitshort_signal']
    params = dict(length1=10, length2=20)
    overlap = dict(ma1=True, ma2=True)
    isplot = dict(long_signal=False, short_signal=False,
                  exitlong_signal=False, exitshort_signal=False)

    def next(self):
        ma1 = self.close.sma(self.params.length1)
        ma2 = self.close.sma(self.params.length2)
        long_signal = ma1.cross_up(ma2)
        short_signal = ma1.cross_down(ma2)
        # 反手：做多信号出现时平空，做空信号出现时平多 ✓
        return ma1, ma2, long_signal, short_signal, short_signal, long_signal


def main() -> None:
    kline = LocalDatas.test.kline

    # ① 建指标（信号在 next() 里算好）
    ind = MyMACross(kline)

    # ② 快速回测：1 手、手续费按固定值、不带止损
    result = ind.signal_backtest(
        size=1,
        commission=5,          # 每笔固定手续费
        init_cash=1_000_000,
        isplot=False,          # 不弹图（脚本里只看统计）
        isreport=False,
    )

    print('=' * 64)
    print('指标信号回测：双均线交叉（ma1=%d / ma2=%d）'
          % (ind.params.length1, ind.params.length2))
    print('=' * 64)
    # 统计表格在上面已经打印过一遍（`signal_backtest` 内部 `richprint`）；
    # `pprint` 在部分版本里是 `None`（不是函数）→ 判断一下再调 ✓
    if callable(getattr(result, 'pprint', None)):
        result.pprint()

    print('\n前 5 笔成交：')
    trades = getattr(result, 'result', None)
    if trades is not None and hasattr(trades, 'head'):
        print(trades.head().to_string(index=False))

    print('\n权益曲线（最后 5 个点）：')
    profits = getattr(result, 'profits', None)
    if profits is not None:
        print(profits.tail().to_string())

    # ③ 参数优化：网格搜索"夏普最大"
    #    （desk / miniqt 里点「参数优化」按钮就是这条路径 ✓）
    from minibt import OptimizeConfig
    config = OptimizeConfig(
        params={'length1': (5, 20, 5), 'length2': (20, 40, 10)},
        target='sharpe',
        method='grid',
        n_jobs=2,
    )
    print('\n' + '=' * 64)
    print('参数优化（网格搜索 · 最大化夏普）')
    print('=' * 64)
    print('参数空间：', config.params)
    print('提示：取消下面这行的注释即可真正跑优化（会花几十秒）')
    # best = ind.signal_backtest(optimize=config)
    # best.pprint()                     # 最优参数 + 指标
    # print(best.best_params)


if __name__ == '__main__':
    main()
