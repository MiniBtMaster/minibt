"""迷你走势（Sparkline）：一个 ``<canvas>``，几百个也不卡。

行情表每一行的「走势」列、自选列表、报价头都用它。和图表不同，它**不是**一个
Lightweight Charts 实例，只是一块画布，所以：
``set_data()`` 重画、``baseline='first'`` 用「末值 vs 首值」决定红/绿。

运行::

    python examples/13_panels/02_sparkline.py
    PYLIGHTCHARTS_QT=PyQt6 python examples/13_panels/02_sparkline.py
"""
from __future__ import annotations

import importlib
import math
import os
import sys

BINDING = os.environ.get('PYLIGHTCHARTS_QT') or 'PySide6'
os.environ['PYLIGHTCHARTS_QT'] = BINDING

from pylightcharts.qt import prepare_qt                      # noqa: E402

prepare_qt(BINDING)
QtCore = importlib.import_module(f'{BINDING}.QtCore')
QtWidgets = importlib.import_module(f'{BINDING}.QtWidgets')

from pylightcharts import QtPanel                            # noqa: E402
from pylightcharts.panels import Sparkline                   # noqa: E402


def _wave(phase: float, count: int = 60) -> list:
    return [round(100 + 20 * math.sin(i / 6 + phase) + i * 0.2, 3)
            for i in range(count)]


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()
    # 放一个纵向容器，免得多个 canvas 叠在一起
    panel.win.run_script(
        "var s=document.createElement('div');"
        "s.style.cssText='position:absolute;left:24px;top:24px;"
        "display:flex;flex-direction:column;gap:18px';"
        "document.getElementById('container').appendChild(s); window.__sparks=s;")

    rising = Sparkline(panel.win, width=320, height=56, baseline='first',
                       line_width=1.6, container='window.__sparks')
    rising.set_data(_wave(0.0))

    falling = Sparkline(panel.win, width=320, height=56, baseline='first',
                        line_width=1.6, container='window.__sparks')
    falling.set_data(_wave(math.pi))

    flat = Sparkline(panel.win, width=320, height=56, baseline='none',
                     line_color='#2962ff', fill_color='rgba(41,98,255,0.15)',
                     container='window.__sparks')
    flat.set_data([100 + (i % 7) for i in range(60)])

    # 实时：定时喂新的一段（真实场景里由 update / 行情推送驱动）
    state = {'i': 0}

    def tick() -> None:
        state['i'] += 1
        rising.set_data(_wave(state['i'] / 12.0))
        falling.set_data(_wave(math.pi + state['i'] / 12.0))

    timer = QtCore.QTimer()
    timer.timeout.connect(tick)
    timer.start(120)

    panel.get_webview().resize(420, 320)
    panel.get_webview().show()
    app.exec()


if __name__ == '__main__':
    main()
