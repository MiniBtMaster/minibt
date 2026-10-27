"""Heatmap：树状热力图（treemap），面积=权重、颜色=涨跌幅。

对应 TradingView 的 Stock / Crypto / ETF / Forex Heatmap —— 同一个组件、不同数据。

运行::

    python examples/13_panels/05_heatmap.py
    python examples/13_panels/05_heatmap.py --snapshot heatmap.png
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

from _sample_data import make_rows                           # noqa: E402
from pylightcharts import QtPanel                            # noqa: E402
from pylightcharts.panels import Heatmap                     # noqa: E402


def build(panel: QtPanel) -> Heatmap:
    rows = make_rows(48)
    items = [{'symbol': row['name'], 'value': row['open_interest'] or 1,
              'chg_pct': row['chg_pct']} for row in rows]
    return Heatmap(panel.win, items, color_scheme='cn', max_shock=5, show_labels=True,
                   on_item_click=lambda symbol: print(f'[example] 点击 {symbol}'))


def main() -> None:
    parser = argparse.ArgumentParser(description='Heatmap 示例')
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
