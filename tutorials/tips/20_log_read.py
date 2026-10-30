"""5.20 · 交易日志解读 —— logger / results / stats / qs_metrics

演示要点
--------
| 对象 | 是什么 | 怎么读 |
| --- | --- | --- |
| `bt.get_results()` | `list[策略] -> list[腿] -> DataFrame` | 列：`total_profit/positions/sizes/float_profits/cum_profits/total_fee` |
| `strategy.stats` | 逐 bar **权益**序列（pandas Series） | 自己算回撤 / 收益曲线 |
| `strategy.logger.stats` | 交易统计 dict（`islog=True` 才有数） | `total_trades / winning_trades / total_pnl / max_profit / max_loss` |
| `strategy.logger.trade_history` | 逐笔记录（开/平都记） | 复盘用；不是逐 bar |
| `bt.qs_metrics()` | QuantStats 统计表（**直接打印**） | `Sharpe / Max Drawdown / Profit Factor …` |

运行：``python tutorials/tips/20_log_read.py``
文档：``minibt_docs/docs/minibt_tips/5.20_log_read.md``
"""

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'tutorials', 'orders'))

from _shared import account_snapshot, run_cross      # noqa: E402
from minibt import *                                  # noqa: E402,F403


def main(gui=None):
    # ① 回测结果：list[策略] -> list[腿] -> DataFrame
    bt = run_cross(lambda d, s: getattr(d, s)())
    results = bt.get_results()
    legs = results[0]
    df = legs[0]
    print('① bt.get_results():', type(results).__name__, '->',
          len(results), '个策略 ->', len(legs), '条腿')
    print('   列:', list(df.columns), '| 行数:', len(df))
    print('   累计平仓盈亏 cum_profits 末值:',
          round(float(df['cum_profits'].iloc[-1]), 2))
    print('   总手续费 total_fee 末值:',
          round(float(df['total_fee'].iloc[-1]), 2))

    # ② 权益曲线 + 最大回撤（strategy.stats 是逐 bar 权益）
    strategy = bt.strategies[0]
    equity = strategy.stats
    print('② strategy.stats:', type(equity).__name__,
          '| 名称', equity.name, '| 长度', len(equity))
    drawdown = equity / equity.cummax() - 1.0
    print('   起始权益 %.2f → 结束权益 %.2f' % (equity.iloc[0], equity.iloc[-1]))
    print('   最大回撤 %.4f%%' % (drawdown.min() * 100))
    snap = account_snapshot(bt)
    print('   账户快照: balance=%.2f | total_profit=%.2f | risk_ratio=%.4f'
          % (snap['balance'], snap['total_profit'], snap['risk_ratio']))

    # ③ 打开日志：会打印每笔委托/成交（这里捕获起来，只统计不刷屏）
    cfg = Config(islog=True, islogorder=True, print_account=False,
                 pprint=False, log_to_file=False, isplot=False)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        bt_log = run_cross(lambda d, s: getattr(d, s)(), config=cfg)
    lines = buffer.getvalue().splitlines()
    print('③ islog=True 产生的日志行数:', len(lines))
    print('   前 3 行（节选）:')
    for line in lines[:3]:
        print('     ', line[:70])

    logger = bt_log.strategies[0].logger
    print('   logger.stats:', {k: logger.stats[k] for k in
                               ('total_trades', 'winning_trades',
                                'losing_trades', 'total_pnl',
                                'max_profit', 'max_loss')})
    print('   logger.trade_history:', len(logger.trade_history),
          '条（开/平都记）')
    print('   logger 常用方法:', [n for n in
                                 ('show_stats', 'show_recent_trades',
                                  'trade_history', 'log_file', 'stats')
                                 if hasattr(logger, n)])
    print('   日志文件:', os.path.basename(str(logger.log_file)))

    # ④ QuantStats：qs_metrics() 直接打印统计表（也捕获起来看前几行）
    qs = io.StringIO()
    with contextlib.redirect_stdout(qs):
        bt.qs_metrics()
    qs_lines = [line for line in qs.getvalue().splitlines() if line.strip()]
    print('④ bt.qs_metrics() 输出前 8 行:')
    for line in qs_lines[:8]:
        print('     ', line)
    print('   （qs_metrics() 返回 bt 自身，可链式调用）')


if __name__ == '__main__':
    main()
