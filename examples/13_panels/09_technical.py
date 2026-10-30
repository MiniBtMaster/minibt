"""Technical Analysis：买卖仪表盘 + 振荡器/均线汇总表。

`ta_summary(frame)` 在 Python 侧把价格序列算成 TradingView 风格的汇总
（7 个振荡器 + 12 条均线 → 评分 / 计数 / 明细），组件只负责渲染。

运行::

    python examples/13_panels/09_technical.py
    python examples/13_panels/09_technical.py --snapshot technical.png
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
from pylightcharts.panels import TechnicalAnalysis, ta_summary  # noqa: E402


def make_frame(rows: int = 400, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.6)
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': close + rng.standard_normal(rows) * 0.3,
        'high': close + np.abs(rng.standard_normal(rows)) * 0.8,
        'low': close - np.abs(rng.standard_normal(rows)) * 0.8,
        'close': close,
        'volume': rng.integers(1_000, 20_000, rows)})


def build(panel: QtPanel) -> TechnicalAnalysis:
    return TechnicalAnalysis(panel.win, ta_summary(make_frame()))


def main() -> None:
    parser = argparse.ArgumentParser(description='Technical Analysis 示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()
    build(panel)
    view = panel.get_webview()

    if args.snapshot:
        view.resize(900, 420)
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
