# coding: utf-8
"""e2e 自检：导航"图表"页（纯 pylightcharts）能不能真的画出图。

和 ``tests/e2e/miniqt_chart_check.py`` 一个风格：建页 → 起 Qt → 用页面 JS 数
``canvas`` / 问 K 线根数（**不靠抓图**，抓图对 GPU 合成的 canvas 不可靠）→ 存一张
PNG 备用 → 打印 ``RESULT_OK`` / 非零退出。

    python tests/e2e/pylightcharts_page_check.py
"""
from __future__ import annotations

import os
import pathlib
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pylightcharts.compat import install_alias                 # noqa: E402
install_alias()

OUT = ROOT / 'tests' / 'e2e' / 'pylightcharts_page_check.png'
STATE = {'canvas': 0, 'bars': -1}


def watchdog():
    time.sleep(120)
    print('WATCHDOG: 超时退出')
    os._exit(2)


def main():
    threading.Thread(target=watchdog, daemon=True).start()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWebEngineWidgets import QWebEngineView        # noqa: F401
    from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

    app = QApplication(sys.argv)

    # miniqt/app/common/config.py 用相对路径读 app/config/config.json
    cwd = os.getcwd()
    os.chdir(ROOT / 'miniqt')
    try:
        import miniqt.app.common.config                        # noqa: F401
    finally:
        os.chdir(cwd)

    from miniqt.app.windows.pylightcharts_page import (        # noqa: E402
        PylightchartsInterface)

    page = PylightchartsInterface()
    holder = QWidget()
    holder.setWindowTitle('pylightcharts 图表页自检')
    layout = QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(page, 1)
    holder.resize(1200, 720)
    holder.show()
    page.start()
    print('page.started:', page.grid is not None,
          '| panes:', len(page.panes))

    def probe():
        panes = list(page.panes.items())
        print('panes:', {name: type(pane.webview).__name__
                         for name, pane in panes})
        if not panes:
            finish(False)
            return
        name, pane = panes[0]
        view = pane.webview
        print('webview:', name, view.isVisible(), view.width(), view.height())

        def got(result):
            print('page  :', name, result)
            try:
                import json
                state = json.loads(result)
                STATE['canvas'] = int(state.get('canvas') or 0)
                STATE['bars'] = int(state.get('bars') or -1)
            except Exception as error:                         # noqa: BLE001
                print('解析失败:', error)
            finish(STATE['canvas'] > 0 and STATE['bars'] == 8964)

        check = f'''
        (() => {{
          const out = {{ canvas: document.querySelectorAll('canvas').length }};
          try {{ out.bars = {pane.chart.id}.series.data().length; }}
          catch (e) {{ out.bars = 'err:' + e.message; }}
          return JSON.stringify(out);
        }})()
        '''
        view.page().runJavaScript(check, got)

    def finish(ok):
        try:
            holder.grab().save(str(OUT))
            size = OUT.stat().st_size if OUT.exists() else 0
            print('screenshot:', OUT, size)
        except Exception as error:                             # noqa: BLE001
            print('抓图失败:', error)
        print('canvases:', STATE['canvas'], '| bars:', STATE['bars'])
        print('RESULT_OK' if ok else 'RESULT_FAIL')
        app.quit()

    QTimer.singleShot(12000, probe)
    QTimer.singleShot(45000, lambda: finish(False))
    app.exec()


if __name__ == '__main__':
    main()
