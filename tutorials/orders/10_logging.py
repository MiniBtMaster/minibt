"""10.10 · 交易日志 —— `Config` 开关 + `logger` + QuantStats

演示要点
--------
| `Config` 字段 | 说明 |
| --- | --- |
| `islog` | 打交易日志（开/平仓） |
| `islogorder` | 打**委托**日志（提交/成交/撤销） |
| `print_account` | 收盘打印账户表（rich 表格） |
| `pprint` | 美化打印 |
| `log_to_file` | 写日志文件（`~/.minibt/logs`？） |
| `auto_clean_days` | 自动清理多少天前的日志 |

`strategy.logger`（`Logger`）上有一组方法：`add_long` / `add_short` /
`close_long` / `close_short` / `create_long` / `create_short` / `close` /
`console` / `debug` / `critical` …

运行：``python tutorials/orders/10_logging.py``
文档：``minibt_docs/docs/minibt_orders/10.10_logging.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _shared                                        # noqa: E402
from minibt import *                                  # noqa: E402,F403


def main(gui=None):
    # ① 打开日志（会看到开/平仓 + 账户表）
    cfg = _shared.Config(islog=True, islogorder=True, print_account=True,
                         pprint=False, log_to_file=False, isplot=False)
    print('① 下面会出现交易日志 / 账户表：')
    bt = _shared.run_cross(lambda d, s: getattr(d, s)(), config=cfg)

    # ② logger 对象
    logger = bt.strategies[0].logger
    print('② logger:', type(logger).__name__)
    print('   方法:', [n for n in dir(logger) if not n.startswith('_')][:12])

    # ③ 结果 / 统计
    res = bt.get_results()
    df = res[0][0]
    print('③ bt.get_results() -> list[策略] -> list[腿] -> DataFrame')
    print('   列:', list(df.columns), '| 行数:', len(df))
    print('   累计盈亏:', round(float(df['cum_profits'].iloc[-1]), 2))

    # ④ QuantStats 报告（可选依赖）
    print('④ bt.qs_metrics() / qs_plots() / qs_html() / qs_reports()')
    print('   需要 quantstats；`richprint` 是富文本打印')


if __name__ == '__main__':
    main()
