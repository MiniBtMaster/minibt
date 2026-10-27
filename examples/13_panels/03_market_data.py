"""Market Data：分组行情表（交易所 Tab）+ 顶部滚动条（Ticker Tape）。

组合了 `Tabs` + `DataGrid`（由 `MarketData` 封装）与 `TickerTape`：

- 顶栏 Ticker Tape 滚动报价；
- 下面 Market Data 按交易所分组，点 Tab 切换数据；
- 双击某行回调合约代码（miniqt 里就是开图）。

运行::

    python examples/13_panels/03_market_data.py
    python examples/13_panels/03_market_data.py --snapshot market_data.png
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BINDING = os.environ.get('PYLIGHTCHARTS_QT') or 'PySide6'
os.environ['PYLIGHTCHARTS_QT'] = BINDING

from pylightcharts.qt import prepare_qt                      # noqa: E402

prepare_qt(BINDING)
QtCore = importlib.import_module(f'{BINDING}.QtCore')
QtWidgets = importlib.import_module(f'{BINDING}.QtWidgets')

from _sample_data import group_by_exchange, make_items, make_rows   # noqa: E402
from pylightcharts import QtPanel                            # noqa: E402
from pylightcharts.panels import Column, MarketData, TickerTape  # noqa: E402


def build(panel: QtPanel):
    rows = make_rows(600)
    tape = TickerTape(panel.win, items=make_items(rows[:20]),
                      on_item_click=lambda symbol: print(f'[example] ticker {symbol}'))
    market = MarketData(
        panel.win,
        groups=group_by_exchange(rows),
        columns=[
            Column('symbol', '代码', width=1.4),
            Column('name', '名称', width=1.2),
            Column('last', '最新', type='number', color_by='sign'),
            Column('chg', '涨跌', type='change'),
            Column('chg_pct', '涨跌幅', type='percent'),
            Column('volume', '成交量', type='number', compact=True),
            Column('open_interest', '持仓量', type='number', compact=True),
            Column('spark', '走势', type='spark', width=1.4),
        ],
        on_row_double_click=lambda key: print(f'[example] 双击 {key}（这里可开图）'),
    )
    return tape, market


def main() -> None:
    parser = argparse.ArgumentParser(description='Market Data 示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()
    build(panel)
    view = panel.get_webview()

    if args.snapshot:
        view.resize(1280, 760)
        panel.win.run_script(
            "document.getElementById('container').style.height='760px';")

        def shoot() -> None:
            view.grab().save(args.snapshot)
            print(f'[example] 已保存截图: {args.snapshot}')
            app.quit()

        QtCore.QTimer.singleShot(3500, shoot)
    else:
        view.show()
    app.exec()


if __name__ == '__main__':
    main()
