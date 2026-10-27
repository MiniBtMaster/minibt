"""pylightcharts 图表页 & "到底在用哪个库" 的守卫测试。

背景：仓库根目录里还有两个**老库的本地副本**（``lightweight-charts-python/``、
``lwc-python/``），而 miniqt 启动时会把仓库根插进 ``sys.path``。一旦别名没装或
被绕开，``import lightweight_charts`` 就可能落到老副本上 —— 表现是"图看着还是老
图表"。这里把这件事钉死：

* ``lightweight_charts is pylightcharts``（同一个模块对象）；
* 图表类必须来自**本仓库**的 ``pylightcharts/``；
* 绝不能来自那两个老副本。

再加一条纯数据断言（不需要 GUI）：测试图表页的 K 线表必须是 **datetime64**
（整数 epoch 秒会画成"只有坐标轴、没有蜡烛"）。

    pytest tests/test_pylightcharts_page.py
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import textwrap

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
PAGE = REPO / 'miniqt' / 'app' / 'windows' / 'pylightcharts_page.py'
LEGACY_DIRS = ('lightweight-charts-python', 'lwc-python')


def _run(script: str) -> subprocess.CompletedProcess:
    """在干净子进程里跑（避免污染本测试进程的 sys.modules）。"""
    result = subprocess.run(
        [sys.executable, '-c', textwrap.dedent(script)], cwd=str(REPO),
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=300)
    if result.returncode != 0:
        pytest.fail(f'子进程失败（{result.returncode}）:\n'
                    f'{result.stdout}\n{result.stderr}')
    return result


def test_page_lives_next_to_chart_interface():
    """图表页放在 ``windows/``（和 ``chart_interface.py`` 同目录），后续照它长。"""
    assert PAGE.exists(), 'pylightcharts_page.py 不在 windows/ 下'
    assert (REPO / 'miniqt' / 'app' / 'windows'
            / 'chart_interface.py').exists()
    # 旧的 view/ 位置不该再留一份（避免两处维护）
    assert not (REPO / 'miniqt' / 'app' / 'view'
                / 'pylightcharts_interface.py').exists()


def test_lightweight_charts_alias_is_pylightcharts():
    result = _run("""
        import sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        import lightweight_charts as lwc
        import pylightcharts as plc
        print('SAME', lwc is plc)
        print('FILE', getattr(lwc, '__file__', ''))
    """)
    assert 'SAME True' in result.stdout
    assert 'pylightcharts' in result.stdout


def test_chart_class_comes_from_this_repo():
    """图表类必须来自本仓库的 ``pylightcharts/``，且不能是那两个老副本。"""
    result = _run("""
        import os
        import sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        # 必须先 import QtWebEngineWidgets：miniqt 的 config 会建出 Qt 应用，
        # 之后 PyQt6 不再允许补导入它（e2e 自检也是这个顺序）。
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        from miniqt.app.windows import chart_interface as ci
        cls = ci.get_chart_class()
        print('MODULE', cls.__module__)
        print('SOURCE', sys.modules[cls.__module__].__file__)
    """)
    assert 'MODULE pylightcharts' in result.stdout, result.stdout
    source = next(line.split(' ', 1)[1] for line in result.stdout.splitlines()
                  if line.startswith('SOURCE '))
    assert 'pylightcharts' in source.replace('\\', '/')
    for legacy in LEGACY_DIRS:
        assert legacy not in source.replace('\\', '/'), source


def test_the_page_is_one_window_with_panel_layout():
    """页面 = **一个**看盘窗口 + 面板布局（一个工具栏 ✓）。

    设计改过一轮：早先是"多合约网格 = 多个独立窗口" ✗（那会看到三个图 + 三个工具栏 ✗），
    现在按界面要求改成"同一张图里分格"（pylightcharts 的 ``chart.win.layout`` ✓）。
    """
    source = PAGE.read_text(encoding='utf-8')
    assert 'DATASETS' in source                    # 多份数据 = 多合约
    assert 'panel_layout' in source                # 走单窗口面板布局
    assert 'create_grid' not in source             # 不再是多个独立窗口
    assert 'BrowserChart' not in source
    assert 'from PyQt6.QtWebEngineWidgets' not in source   # 视图由 chart 自己给


def test_the_window_owns_the_embedding_rules():
    """嵌入三条铁律在 window 里：get_webview + 延后 set + ChartClass 位置参数。"""
    window = (REPO / 'miniqt' / 'app' / 'windows'
              / 'pylightcharts_window.py').read_text(encoding='utf-8')
    assert '(None, 1.0, 1.0, False, False)' in window
    assert 'get_webview()' in window
    assert 'QTimer.singleShot' in window           # 延后送数据
    assert 'class ChartGrid' in window             # 多合约网格


def test_contracts_are_never_inline():
    """合约必须各是各的图：网格用**独立窗口**，不许用 Layout/create_subchart。"""
    window = (REPO / 'miniqt' / 'app' / 'windows'
              / 'pylightcharts_window.py').read_text(encoding='utf-8')
    # ChartGrid 里每格都建一个独立窗口
    assert 'PylightchartsChartWindow(self)' in window
    # 并且明确写了"合约不要用内联布局"
    assert '不要用来放合约' in window


def test_the_page_frame_is_datetime64():
    """测试图表页用的 K 线表：截到 **1000 根**、``time`` 必须是 datetime64。"""
    result = _run("""
        import os
        import sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        from miniqt.app.windows.pylightcharts_page import test_kline_frame
        frame = test_kline_frame()
        print('ROWS', len(frame))
        print('DTYPE', frame['time'].dtype)
        print('COLS', ','.join(frame.columns))
    """)
    assert 'ROWS 1000' in result.stdout, result.stdout
    assert 'datetime64' in result.stdout, result.stdout
    assert 'time,open,high,low,close,volume' in result.stdout, result.stdout
