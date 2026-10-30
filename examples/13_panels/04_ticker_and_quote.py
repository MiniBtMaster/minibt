"""Ticker 家族 + 报价头：TickerTape / Tickers / SymbolInfo / SymbolOverview / MiniChart。

演示「微型行情插件」的多种形态：

- ``TickerTape`` —— 顶部滚动跑马灯；
- ``Tickers`` —— 静态多品种标签（``TickerTag`` / ``SingleTicker`` 同实现）；
- ``SymbolInfo`` —— 报价头（名称/最新/涨跌 + 开高低/量/持仓）；
- ``SymbolOverview`` —— 报价头 + 迷你走势图；
- ``MiniChart`` —— 独立迷你走势。

运行::

    python examples/13_panels/04_ticker_and_quote.py
    python examples/13_panels/04_ticker_and_quote.py --snapshot ticker.png
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

from _sample_data import make_items, make_rows               # noqa: E402
from pylightcharts import QtPanel                            # noqa: E402
from pylightcharts.panels import (MiniChart, SymbolInfo,     # noqa: E402
                                  SymbolOverview, TickerTape, Tickers)


def build(panel: QtPanel):
    rows = make_rows(24)
    items = make_items(rows)
    TickerTape(panel.win, items=items, speed=70,
               on_item_click=lambda symbol: print(f'[tape] {symbol}'))
    Tickers(panel.win, items=items[:8], show_name=True, decimals=0,
            on_item_click=lambda symbol: print(f'[tags] {symbol}'))
    SymbolInfo(panel.win, rows[0], decimals=0)
    SymbolOverview(panel.win, rows[1], decimals=0)
    MiniChart(panel.win, rows[2]['spark'], width=320, height=72)


def main() -> None:
    parser = argparse.ArgumentParser(description='Ticker / Quote 示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()
    build(panel)
    view = panel.get_webview()

    if args.snapshot:
        view.resize(1100, 560)
        panel.win.run_script(
            "document.getElementById('container').style.height='560px';")

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
