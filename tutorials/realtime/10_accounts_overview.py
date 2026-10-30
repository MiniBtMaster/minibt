"""11.9 · 多账户总览：把**落盘**的期货账户权益/成交汇总对比

演示要点
--------
期货账户默认会**自动落盘**（`LiveTools` 每 5 秒写一条权益点 + 增量成交）：

```python
bt = Bt(live=True)
bt.addTqapi(api=TqApi(TqMultiAccount([...])))   # 多账户
bt.addstrategy(Alpha, account='H宏源期货')       # ★ 策略绑定账户
bt.run()                                        # 关闭后数据还在
```

落盘位置：``~/.minibt/tq_accounts.sqlite3``（可用 ``TqAccountStore(path=...)`` 换）。

本脚本**不需要**连天勤、不需要 tqsdk 登录，只读 sqlite：

* 打印每个账户的最新权益 / 区间收益 / 成交笔数
* 画一张多账户权益曲线对比图（matplotlib，存 PNG）

| 方法 | 说明 |
| --- | --- |
| `TqAccountStore()` | 打开默认库（`~/.minibt/tq_accounts.sqlite3`） |
| `store.names()` | 记录过的账户名（最近有数据的在前） |
| `store.equity(name)` | `[(ts, balance), ...]`；`since=` 可按时间过滤 |
| `store.trades(name, limit=)` | 最近成交（新的在前） |
| `store.overview()` | 每账户一条快照（首/末权益、区间收益、点数） |
| `store.reset(name=None)` | 清空（调试用） |

运行：
    python tutorials/realtime/10_accounts_overview.py            # 打印 + 存 PNG
    python tutorials/realtime/10_accounts_overview.py --check    # 只打印
    python tutorials/realtime/10_accounts_overview.py --db 自定义.sqlite3

文档：``minibt_docs/docs/minibt_realtime/11.9_multi_account.md``
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import TqAccountStore, TQ_ACCOUNT_DB            # noqa: E402


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return '--'
    return f'{float(value):,.{digits}f}'


def print_overview(store: TqAccountStore) -> list:
    """打印汇总表（返回 overview 行，方便下面画图 ✓）"""
    rows = store.overview()
    print(f'库文件：{store.path}')
    if not rows:
        print('\n（还没有数据）')
        print('跑一个实时策略（`python tutorials/realtime/09_stock_live.py` 的期货版，'
              '或自己的 `Bt(live=True)` 脚本）停留几秒即可落盘 ✓')
        return []
    print(f'\n{"账户":28} {"权益":>14} {"区间收益":>14} {"点数":>7} '
          f'{"最近更新":>20}')
    print('-' * 88)
    for row in rows:
        print(f'{row["name"][:28]:28} {_fmt(row["last"]):>14} '
              f'{_fmt(row["profit"]):>14} {row["count"]:>7} '
              f'{str(row["last_ts"] or "--"):>20}')
    for row in rows:
        trades = store.trades(row['name'], limit=5)
        if not trades:
            continue
        print(f'\n[{row["name"]}] 最近成交 {len(trades)} 笔：')
        for trade in trades:
            print('   {ts}  {symbol:12} {direction:4} {offset:4} '
                  '{volume:>6} @ {price:>10}'.format(
                      ts=str(trade['ts'] or '')[:19],
                      symbol=str(trade['symbol'] or ''),
                      direction=str(trade['direction'] or ''),
                      offset=str(trade['offset'] or ''),
                      volume=trade['volume'] or 0,
                      price=_fmt(trade['price'], 3)))
    return rows


def draw_overview(store: TqAccountStore, rows: list,
                  path: str = '') -> str:
    """多账户权益曲线 → PNG（matplotlib Agg，不弹窗 ✓）"""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import StrMethodFormatter

    path = path or os.path.join(os.path.expanduser('~'), '.minibt', 'exports',
                                'accounts_overview.png')
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    figure = Figure(figsize=(10.0, 4.0), dpi=120)
    FigureCanvasAgg(figure)
    axes = figure.add_subplot(111)
    drawn = 0
    for index, row in enumerate(rows):
        points = store.equity(row['name'])
        if len(points) < 2:
            continue
        xs = list(range(len(points)))
        ys = [value for _, value in points]
        axes.plot(xs, ys, linewidth=1.4,
                  color=['#2f9e44', '#1e88e5', '#e65100', '#8e24aa',
                         '#00838f', '#c62828'][index % 6],
                  label=f'{row["name"]} ({ys[-1]:,.0f})')
        drawn += 1
    if not drawn:
        return ''
    axes.set_title('minibt futures accounts equity', fontsize=10, loc='left')
    axes.grid(True, linestyle=':', alpha=0.35)
    axes.tick_params(labelsize=7)
    axes.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    axes.legend(fontsize=8, loc='best', frameon=False)
    figure.savefig(path, bbox_inches='tight')
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description='期货多账户总览（读 sqlite）')
    parser.add_argument('--db', default=TQ_ACCOUNT_DB, help='库文件路径')
    parser.add_argument('--check', action='store_true',
                        help='只打印，不画图（无 matplotlib 环境也安全）')
    parser.add_argument('--png', default='', help='PNG 输出路径（默认在 ~/.minibt/exports）')
    args = parser.parse_args()

    store = TqAccountStore(args.db)
    try:
        rows = print_overview(store)
        if args.check or not rows:
            return 0
        path = draw_overview(store, rows, args.png)
        if path:
            print(f'\n对比图已保存：{path}')
        else:
            print('\n（点数不足 2 个，未画图）')
        return 0
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
