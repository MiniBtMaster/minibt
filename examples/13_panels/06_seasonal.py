"""Seasonal Chart：季节性柱状图（按月平均收益）。

用多合成的多年日线价格，`SeasonalChart.from_frame()` 在 Python 侧聚合出「每月
平均涨跌幅」，再由 pylightcharts 画成红涨绿跌的柱子。

运行::

    python examples/13_panels/06_seasonal.py
    python examples/13_panels/06_seasonal.py --snapshot seasonal.png
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

BINDING = os.environ.get('PYLIGHTCHARTS_QT') or 'PySide6'
os.environ['PYLIGHTCHARTS_QT'] = BINDING

from pylightcharts.qt import prepare_qt                      # noqa: E402

prepare_qt(BINDING)
QtCore = importlib.import_module(f'{BINDING}.QtCore')
QtWidgets = importlib.import_module(f'{BINDING}.QtWidgets')

import numpy as np                                           # noqa: E402
import pandas as pd                                          # noqa: E402

from pylightcharts import QtPanel                            # noqa: E402
from pylightcharts.panels import SeasonalChart               # noqa: E402


def make_frame(years: int = 8, seed: int = 3) -> pd.DataFrame:
    """Synthetic daily prices with a yearly seasonal component."""
    rng = np.random.default_rng(seed)
    index = pd.date_range('2016-01-01', periods=365 * years, freq='D')
    steps = np.arange(len(index))
    seasonal = 0.05 * np.sin(2 * np.pi * (steps / 365.25) - 0.6)
    close = 100 * np.exp(np.cumsum(rng.standard_normal(len(index)) * 0.008) + seasonal)
    return pd.DataFrame({'time': index, 'close': close})


def build(panel: QtPanel) -> SeasonalChart:
    chart = SeasonalChart(panel.win, color_scheme='cn', percent=True, decimals=2)
    chart.from_frame(make_frame())
    return chart


def main() -> None:
    parser = argparse.ArgumentParser(description='Seasonal Chart 示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()
    build(panel)
    view = panel.get_webview()

    if args.snapshot:
        view.resize(1000, 420)
        panel.win.run_script(
            "document.getElementById('container').style.height='420px';")

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
