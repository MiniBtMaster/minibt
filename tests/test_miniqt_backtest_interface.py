# coding: utf-8
"""「回测」导航页（复刻看盘窗口的静态版）测试 ✓。

用户要求的壳：
1. 直接复刻看盘窗口，减掉实时图表功能；
2. 顶栏只留 商品搜索 / 周期 / 画线 / 代码编辑器 / 回测结果（原「交易」改）；
3. 图表是静态的 + pylightcharts 页面顶栏（多合约展示）；初始隐藏；
4. 初始显示底部 dock，默认页 = 代码编辑器；
5. 代码编辑器去掉「添加指标 / 添加策略到当前图表」。

    pytest tests/test_miniqt_backtest_interface.py
"""
from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys
import types

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import PyQt6.QtWebEngineWidgets  # noqa: F401,E402

REPO = pathlib.Path(__file__).resolve().parents[1]
PAGE = REPO / 'miniqt' / 'app' / 'view' / 'backtest_interface.py'
MAIN = REPO / 'miniqt' / 'app' / 'view' / 'main_window.py'
TOPBAR = REPO / 'miniqt' / 'app' / 'windows' / 'tradingview_topbar.py'
DOCK = REPO / 'miniqt' / 'app' / 'windows' / 'sim_account_panel.py'
EDITOR = REPO / 'miniqt' / 'app' / 'windows' / 'qtvscode_page.py'
RESULT = REPO / 'miniqt' / 'app' / 'windows' / 'strategy_backtest_window.py'
PAINTER = REPO / 'miniqt' / 'app' / 'windows' / 'candle_painter.py'

pytestmark = pytest.mark.skipif(
    not PAGE.exists(), reason='需要仓库里的 miniqt 源码')


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


def _run(script: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONIOENCODING'] = 'utf-8'
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=str(REPO), env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=240)
    if result.returncode != 0:
        pytest.fail(f'子进程失败（{result.returncode}）:\n'
                    f'{result.stdout}\n{result.stderr}')
    return result


# ---- 源码约束 -----------------------------------------------------------
def test_page_reuses_market_watch_window():
    source = _read(PAGE)
    assert 'setObjectName("backtestInterface")' in source
    assert 'PylightchartsChartWindow' in source          # 图表页复用图表窗口 ✓
    assert 'def _ensure_chart_page' in source            # 图表 tab = 容器 ✓
    assert 'def _build_chart_window' in source           # 懒建图表窗口 ✓
    assert 'window.topbar.hide()' in source              # 图表不要工具栏 ✓
    assert 'QStackedWidget' in source                    # 三 tabs 页面栈 ✓
    assert '_BacktestWorker' in source                   # 复用引擎 worker ✓
    assert 'BacktestResultPanel' in source               # 复用结果面板 ✓
    assert 'with_chart=False' in source                  # 结果页不含 K 线 ✓
    assert 'minimal=True' in source                      # 精简代码编辑器 ✓
    assert 'def stop_and_wait' in source


def test_topbar_not_modified_for_backtest():
    """回测页不再改顶栏（图表 tab 直接隐藏整个工具栏 ✓）。"""
    topbar = _read(TOPBAR)
    assert 'apply_backtest_layout' not in topbar
    assert 'strategyCombo' not in topbar


def test_title_is_strategy_backtest():
    """页面标题是「策略回测 / 参数优化」（用户要求 ✓）。"""
    assert "SubtitleLabel('策略回测 / 参数优化'" in _read(PAGE)


def test_all_charts_follow_the_same_theme():
    """所有图表**同一主题同一样式**：测试图表不再写死深色；
    浅色文字/网格与指标详情页图表对齐 ✓。"""
    from miniqt.app.windows.pylightcharts_page import theme_colors
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow)
    page_source = _read(
        REPO / 'miniqt' / 'app' / 'windows' / 'pylightcharts_page.py')
    assert 'theme_colors()' in page_source
    # 样式不再写死颜色，改用主题色 ✓
    assert "pane.layout_options(background_color=colors['bg']" in page_source
    assert "('candle_style', {'up_color': colors['up']" in page_source
    colors = theme_colors()
    assert set(colors) >= {'bg', 'text', 'grid', 'up', 'down'}
    light = PylightchartsChartWindow.THEMES[False]
    assert light['text'] == '#131722'
    assert light['grid'] == 'rgba(42,46,57,0.15)'


def test_contract_bar_defaults_to_first_contract():
    """第二个顶栏默认高亮**第一个合约**（不能是「回测结果」）✓。

    之前 `_start` 先 `_build_backtest_topbar()` 再 `_select_strategy(0)`，
    建顶栏时合约还是空 → 默认高亮变成「回测结果」✗。
    """
    source = _read(PAGE)
    assert 'default = self._contracts[0] if self._contracts else None' \
        in source
    assert 'if self._contracts:\n            widget.value = ' \
        'self._contracts[0]' in source


def test_chart_started_after_switching_to_chart_tab():
    """建图前**先切到图表 tab**：``QWebEngineView`` 要在可见时创建，
    否则黑屏 / 卡住（其它功能正常）✗。"""
    source = _read(PAGE)
    block = source.split('def _show_backtest_chart', 1)[1].split(
        'def _build_records', 1)[0]
    assert block.index('self._switch_tab(2)') < block.index('cw.start()')
    assert 'processEvents()' in block
    assert 'def _refresh_webview' in source


def test_dock_presets_are_configurable():
    source = _read(DOCK)
    assert 'self.presets = ' in source
    assert 'for key, title in self.presets:' in source


def test_code_editor_has_minimal_mode():
    from miniqt.app.windows.qtvscode_page import QtvscodePage
    import inspect
    params = inspect.signature(QtvscodePage.__init__).parameters
    assert 'minimal' in params
    source = _read(EDITOR)
    assert 'if not self.minimal:' in source


def test_result_panel_has_with_chart_option():
    from miniqt.app.windows.strategy_backtest_window import BacktestResultPanel
    import inspect
    params = inspect.signature(BacktestResultPanel.__init__).parameters
    assert 'with_chart' in params
    source = _read(RESULT)
    assert 'self._with_chart' in source


def test_main_window_registers_backtest_page():
    source = _read(MAIN)
    assert 'from .backtest_interface import BacktestInterface' in source
    assert 'BacktestInterface(' in source
    assert 'addSubInterface(self.backtestInterface' in source
    assert 'signalBus.backtestRequested.connect(self.open_backtest_page)' \
        in source
    assert 'def open_backtest_page' in source
    assert "getattr(self, 'backtestInterface', None)" in source
    assert 'page.stop_and_wait()' in source


def test_signal_bus_and_chart_stub():
    from miniqt.app.common.signal_bus import SignalBus
    assert hasattr(SignalBus, 'backtestRequested')
    stub = _read(REPO / 'miniqt' / 'app' / 'windows' / 'pylightcharts_window.py')
    assert 'signalBus.backtestRequested.emit' in stub


def test_candle_painter_compiles():
    ast.parse(_read(PAINTER))


def test_strategy_class_names_static():
    """静态数策略类：不执行代码；``if __name__`` 里的不算 ✓。"""
    from miniqt.app.common.strategy_catalog import strategy_class_names
    code = ('from minibt import *\n'
            'class Ind(BtIndicator):\n    def next(self): pass\n'
            'class One(Strategy):\n    def next(self): pass\n'
            'if __name__ == "__main__":\n'
            '    class Hidden(Strategy):\n        def next(self): pass\n')
    assert strategy_class_names(code) == ['One']
    assert strategy_class_names('') == []
    assert strategy_class_names('class X(: pass') == []
    two = ('from minibt import Strategy\n'
           'class A(Strategy):\n    def next(self): pass\n'
           'class B(Strategy):\n    def next(self): pass\n')
    assert strategy_class_names(two) == ['A', 'B']


def test_multiple_strategies_allowed(tmp_path):
    """**支持多策略**（多个 → 通过）；0 个 → 不跑并提示 ✓。"""
    multi = tmp_path / 'multi.py'
    multi.write_text('from minibt import Strategy\n'
                     'class A(Strategy):\n    def next(self): pass\n'
                     'class B(Strategy):\n    def next(self): pass\n',
                     encoding='utf-8')
    empty = tmp_path / 'empty.py'
    empty.write_text('x = 1\n', encoding='utf-8')
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        f"print('MULTI', page._check_strategies(r'{multi}'))\n"
        f"print('EMPTY', page._check_strategies(r'{empty}'))\n"
        f"print('RUN_EMPTY', page.run_backtest(r'{empty}'))\n"
        "print('RUNNING', page.isRunning())\n"
    )
    out = _run(script).stdout
    assert 'MULTI True' in out            # 多策略允许 ✓
    assert 'EMPTY False' in out
    assert 'RUN_EMPTY False' in out
    assert 'RUNNING False' in out


def test_run_backtest_checks_strategies_source():
    source = _read(PAGE)
    assert 'def _check_strategies' in source
    assert 'strategy_class_names' in source
    assert '只支持单策略回测' not in source      # 已改成支持多策略 ✓


def test_backtest_topbar_keeps_drawing_and_screenshot():
    """图表顶栏右边保留「画线工具 / 截图」（用户要求 ✓）。"""
    source = _read(PAGE)
    assert "button('drawing', '画线工具'" in source
    assert "button('shot', '截图'" in source
    assert 'def _on_drawing' in source
    assert 'def _on_screenshot' in source
    assert 'toggle_toolbox' in source
    assert 'topbar_screenshot' in source


def test_multi_strategy_wiring_source():
    """B 方案：工具栏策略下拉 + 切策略同步合约条 / dock ✓。"""
    source = _read(PAGE)
    # 多策略 = 加一条**策略顶栏**（page_topbar），单策略不加 ✓
    assert 'def _refresh_strategy_bar' in source
    assert "bar.switcher('strategy'" in source
    assert 'page_topbar()' in source
    assert 'def _build_records' in source
    assert 'def _select_strategy' in source
    assert 'def _update_contract_bar' in source
    assert 'def _refresh_result_panel' in source
    assert 'switch_to_strategy' in source
    assert 'update_items' in source


def test_editor_backtest_runs_active_file():
    """「策略回测」对**当前正在编辑的文件**跑（先对齐活动标签 ✓）。"""
    from miniqt.app.windows.qtvscode_page import QtvscodePage
    import inspect
    source = inspect.getsource(QtvscodePage.request_strategy_backtest)
    assert '_prepare_active_file' in source
    # ★ 信号必须带默认 path：无文本回退到「保存后再跑」时 ``action()``
    #   是不传参调用的，``lambda path: ...`` 会 TypeError ✗
    emitter = inspect.getsource(QtvscodePage._emit_strategy_backtest)
    assert 'strategyBacktestRequested.emit' in emitter
    assert 'path: str = ' in emitter


def test_backtest_chart_replication_source():
    """第二个顶栏 + 回测结果 / 指标记录 页（复用 minibt pages ✓）。"""
    source = _read(PAGE)
    assert "INFO_PAGES = ('回测结果', '指标记录')" in source
    assert "switcher('contract'" in source
    assert 'strategy_backtest_dict' in source
    assert 'strategy_contracts' in source
    assert 'extract_minibt_indicators' in source
    assert 'extract_minibt_signals' in source
    assert 'marker_list' in source                     # B / S 标记 ✓
    assert 'from minibt.strategy.pages import BacktestPage' in source
    assert 'from minibt.strategy.pages import ReportPage' in source
    assert 'chart.show_data()' in source and 'chart.hide_data()' in source


_FAKE_CHART = '''
class FakeSeries:
    def set(self, df=None, **k):
        self.data = df
    def delete(self):
        pass


class FakePanel:
    def __init__(self):
        self.visible = False
        self.html = ''
    def set_html(self, html):
        self.html = html
    def show(self):
        self.visible = True
    def hide(self):
        self.visible = False
    def delete(self):
        pass


class FakeSwitcher:
    def __init__(self, options):
        self.options = list(options)
        self.value = str(options[0]) if options else ''
    def update_items(self, *items):
        self.options = [str(i) for i in items]
        if self.value not in self.options:
            self.value = self.options[0] if self.options else ''


class FakeTopbar:
    def __init__(self):
        self.calls = []
        self.buttons = []
        self.widgets = {}
        self.defaults = {}
    def switcher(self, name, options, **kw):
        self.calls.append((name, tuple(options)))
        self.defaults[name] = kw.get('default')
        self.widgets[name] = FakeSwitcher(tuple(options))
    def button(self, name, text, **kw):
        self.buttons.append((name, text, kw.get('align')))
        self.widgets[name] = FakeSwitcher([text])
    def __getitem__(self, key):
        return self.widgets[key]


class FakeWin:
    loaded = True


class FakeChart:
    def __init__(self):
        self.topbar = FakeTopbar()
        self.markers = {}
        self.panes = 0
        self.shown = True
        self.win = FakeWin()
        self.candle_data = list(range(10))
        self.logical = {'from': 0.0, 'to': 9.0}
        self.set_views = []
        self.id = 'window.fake'
        self.scripts = []
    def run_script(self, script):
        self.scripts.append(script)
    def add_pane(self):
        self.panes += 1
        return self.panes
    def pane_add_series(self, *a, **k):
        return FakeSeries()
    def add_series(self, *a, **k):
        return FakeSeries()
    def add_custom_series(self, *a, **k):
        return FakeSeries()
    def pane_add_custom_series(self, *a, **k):
        return FakeSeries()
    def pane_count(self):
        return self.panes + 1
    def set(self, *a, **k):
        pass
    def fit(self):
        pass
    def get_visible_logical_range(self):
        return dict(self.logical)
    def set_visible_logical_range(self, f, t):
        self.set_views.append((f, t))
    def marker_list(self, ms):
        self.markers.update({i: m for i, m in enumerate(ms)})
    def remove_markers(self, ids):
        for i in ids:
            self.markers.pop(i, None)
    def show_data(self):
        self.shown = True
    def hide_data(self):
        self.shown = False
    def legend(self, **k):
        pass
    def horizontal_span(self, *a, **k):
        pass
    def create_html_panel(self, **k):
        self.panel = FakePanel()
        return self.panel
'''


def test_backtest_topbar_and_info_pages():
    """第二个顶栏项 = 合约 + 回测结果（「指标记录」已挪到独立 tab ✓）。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "import types\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        + _FAKE_CHART +
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "fake = FakeChart()\n"
        "page._chart = fake\n"
        "page._contracts = ['DCE.pp2609_60', 'DCE.i2609_60']\n"
        "page._backtest = {'stats': {}, 'trades': None}\n"
        "page._build_backtest_topbar()\n"
        "print('ITEMS', fake.topbar.calls)\n"
        "print('BUTTONS', fake.topbar.buttons)\n"
        "print('DEFAULT', fake.topbar.defaults.get('contract'))\n"
        "fake.topbar.widgets['contract'].value = '\u56de\u6d4b\u7ed3\u679c'\n"
        "page._on_backtest_topbar()\n"
        "print('DISPATCH', page._backtest_page is not None)\n"
        "page._render_info_page('\u56de\u6d4b\u7ed3\u679c')\n"
        "print('BT_PAGE', page._backtest_page is not None)\n"
        "print('NO_REPORT', page._report_page is None)\n"
        "page._render_info_page('\u6307\u6807\u8bb0\u5f55')\n"
        "print('REPORT_STILL_NONE', page._report_page is None)\n"
        "page._hide_info_pages()\n"
        "print('HIDE_OK', fake.shown)\n"
    )
    out = _run(script).stdout
    assert "ITEMS [('contract', (" in out
    assert "'DCE.pp2609_60', 'DCE.i2609_60'" in out
    assert "'\u56de\u6d4b\u7ed3\u679c')" in out
    assert "'\u6307\u6807\u8bb0\u5f55'" not in out    # 已不在图表顶栏 ✓
    assert ("BUTTONS [('drawing', '\u753b\u7ebf\u5de5\u5177', 'right'), "
            "('shot', '\u622a\u56fe', 'right')]") in out
    assert 'DEFAULT DCE.pp2609_60' in out      # 默认第一个合约 ✓
    assert 'DISPATCH True' in out
    assert 'BT_PAGE True' in out
    assert 'NO_REPORT True' in out             # 指标记录页不再建 ✓
    assert 'REPORT_STILL_NONE True' in out
    assert 'HIDE_OK True' in out


def test_signal_markers_handle_numpy_arrays():
    """回归：信号值是 **numpy 数组**时不能写 ``values or []``
    （数组真假值 ambiguous ✗）—— 应正常画 B / S 标记 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        + _FAKE_CHART +
        "import minibt.strategy.realtime as rt\n"
        "rt.extract_minibt_indicators = lambda *a, **k: []\n"
        "rt.extract_minibt_signals = lambda *a, **k: [\n"
        "    ('long_signal', np.array([0, 1, 0, 1]), {}, None, 0),\n"
        "    ('short_signal', np.array([1, 0, 1, 0]), {}, None, 0)]\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "fake = FakeChart(); page._chart = fake\n"
        "page._instance = object(); page._contracts = ['X_60']\n"
        "frame = {'time': list(pd.date_range('2020-01-01', periods=4,\n"
        "                                    freq='min'))}\n"
        "page._plot_contract_overlays(frame, 'X_60')\n"
        "print('MARKERS', len(fake.markers))\n"
        "print('TEXTS', sorted(m['text'] for m in fake.markers.values()))\n"
    )
    out = _run(script).stdout
    assert 'MARKERS 4' in out
    assert "TEXTS ['B', 'B', 'S', 'S']" in out


def test_select_strategy_switches_contract_bar():
    """切策略 → 第二个顶栏换成它的合约 ✓（假图表）。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        + _FAKE_CHART +
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "fake = FakeChart(); page._chart = fake\n"
        "page._records = [\n"
        "  {'name': 'A', 'instance': None, 'contracts': ['X_60'],\n"
        "   'backtest': {}},\n"
        "  {'name': 'B', 'instance': None, 'contracts': ['Y_60', 'Z_60'],\n"
        "   'backtest': {}}]\n"
        "page._build_backtest_topbar()\n"
        "page._select_strategy(1)\n"
        "print('INDEX', page._index)\n"
        "print('CONTRACTS', page._contracts)\n"
        "print('BAR', fake.topbar.widgets['contract'].options)\n"
    )
    out = _run(script).stdout
    assert 'INDEX 1' in out
    assert "CONTRACTS ['Y_60', 'Z_60']" in out
    assert "'Y_60', 'Z_60'" in out
    assert "'Y_60', 'Z_60', '\u56de\u6d4b\u7ed3\u679c'" in out


def test_info_page_builds_all_contracts_with_signals():
    """回测结果页：每个合约各占一个 pane，各画自己的信号 + 止损线 ✓。

    之前只喂第一个合约、且不画信号/停止线；现在与 minibt pylightcharts 一致：
    主图 = 第一个合约，其余合约各一个 pane，`draw_contract_info` 逐个画装饰 ✓。
    """
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import pandas as pd\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "import minibt.strategy.realtime as rt\n"
        "calls = []\n"
        "frame = pd.DataFrame({'time': pd.date_range('2020-01-01', periods=4,\n"
        "                     freq='min'), 'open': 1., 'high': 2., 'low': .5,\n"
        "                     'close': 1.5, 'volume': 1.})\n"
        "rt.strategy_kline_frame = lambda inst, c: frame.copy()\n"
        "rt.palette_for = lambda chart: ['#111111', '#222222']\n"
        "def fake_draw(chart, inst, contract, fr, pane, **k):\n"
        "    calls.append((contract, pane)); return [object()]\n"
        "rt.draw_contract_info = fake_draw\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        + _FAKE_CHART +
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "fake = FakeChart(); page._chart = fake\n"
        "page._instance = object()\n"
        "page._contracts = ['A_60', 'B_60']\n"
        "page._backtest = {'stats': {}, 'trades': None}\n"
        "page._render_info_page('回测结果')\n"
        "print('CALLS', calls)\n"
        "print('PANES', fake.panes)\n"
        "print('OVERLAYS', len(page._info_overlay_series))\n"
    )
    out = _run(script).stdout
    assert "CALLS [('A_60', 0), ('B_60', 1)]" in out
    assert 'PANES 1' in out                  # 只为第二个合约加了 1 个 pane ✓
    assert 'OVERLAYS 2' in out               # 两个合约各一组装饰 ✓


def test_view_range_is_remembered_per_page():
    """切页记住可视范围（时间口径），切回来恢复（不再每次 fit ✓）。

    MiniQT 的 QtChart 不能同步读 → 用 `visible_time_range_change` 事件缓存，
    `_save_view` 取缓存、`_restore_view` 直接下 `setVisibleRange` ✓。
    """
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        + _FAKE_CHART +
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "fake = FakeChart(); page._chart = fake\n"
        "page._on_visible_time_range(fake, '100.0', '200.0')\n"
        "print('LIVE', page._live_view)\n"
        "page._current_page = 'A_60'\n"
        "page._save_view()\n"
        "print('SAVED', page._view_ranges.get('A_60'))\n"
        "page._restore_view('A_60')\n"
        "print('RESTORED', fake.scripts[-1])\n"
        "print('NONE', page._view_ranges.get('B_60'))\n"
    )
    out = _run(script).stdout
    assert 'LIVE (100.0, 200.0)' in out
    assert 'SAVED (100.0, 200.0)' in out
    assert 'setVisibleRange' in out and 'from: 100.0' in out \
        and 'to: 200.0' in out
    assert 'NONE None' in out                # 没记过的页面保持 fit ✓


def test_open_backtest_page_navigates_and_sets_file():
    from miniqt.app.view.main_window import MainWindow

    navigated = []

    class _Page:
        def __init__(self):
            self.path = ''

        def set_strategy_file(self, path):
            self.path = path

    page = _Page()
    fake = types.SimpleNamespace(backtestInterface=page,
                                 _navigateTo=navigated.append)
    MainWindow.open_backtest_page(fake, r'C:/tmp/s.py')
    assert navigated == [page]
    assert page.path.replace('\\', '/').endswith('s.py')


# ---- 子进程：真建壳 -----------------------------------------------------
def test_page_is_four_tabs():
    """顶部四 tabs（代码编辑器 / 回测结果 / 图表 / 交易记录），默认代码编辑器；
    图表 tab = **只要图表**（工具栏整个隐藏 ✓），初始空白（未建图）✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host); lay.setContentsMargins(\n"
        "    0, 0, 0, 0)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "host.resize(1280, 860); host.layout().activate()\n"
        "print('TABS', page.TABS)\n"
        "print('STACK', page.stack.count())\n"
        "print('DEFAULT', page.stack.currentIndex())\n"
        "print('CHART3RD', page.stack.widget(2) is page._chart_page)\n"
        "print('TRADES4TH', page.stack.widget(3) is page._trades_page)\n"
        "print('TRADES_SUB', page._trades_sub_stack is not None,\n"
        "      page._trades_sub_stack.count())\n"
        "print('RELOAD_BTN', page.reloadButton is not None,\n"
        "      page.reloadButton.toolTip())\n"
        "print('NO_WINDOW', page.chartWindow is None)\n"
        "print('HINT', page.chartHint.text())\n"
        "print('CHART_VISIBLE', page.chart_visible)\n"
        "print('MINIMAL', page._editor_page.minimal)\n"
        "print('NO_ADD', not hasattr(page._editor_page, 'addToChartButton'),\n"
        "      not hasattr(page._editor_page, 'addStrategyButton'))\n"
        "print('KEEP_BT', hasattr(page._editor_page,"
        " 'strategyBacktestButton'))\n"
        "print('RESULT_NO_CHART', page._result_panel._with_chart)\n"
        "page.show_result_page()\n"
        "print('RESULT_TAB', page.stack.currentIndex())\n"
        "page.show_chart()\n"
        "print('CHART_TAB', page.stack.currentIndex(), page.chart_visible)\n"
        "page.show_trades_page()\n"
        "print('TRADES_TAB', page.stack.currentIndex())\n"
        "print('BTN_SYNC', page._tabGroup.buttons()[3].isChecked())\n"
    )
    out = _run(script).stdout
    assert ("TABS ('\u4ee3\u7801\u7f16\u8f91\u5668', '\u56de\u6d4b\u7ed3\u679c', "
            "'\u56fe\u8868', '\u4ea4\u6613\u8bb0\u5f55')") in out
    assert 'STACK 4' in out
    assert 'DEFAULT 0' in out
    assert 'CHART3RD True' in out
    assert 'TRADES_SUB True 2' in out
    assert 'TRADES4TH True' in out
    assert "RELOAD_BTN True \u91cd\u8f7d\u7b56\u7565\u56de\u6d4b\u9875\u9762" in out
    # 图表窗口是**懒建**的（回测出图时才加进来 ✓）
    assert 'NO_WINDOW True' in out
    assert "HINT \u56de\u6d4b\u5b8c\u6210\u540e\u5728\u6b64\u663e\u793a\u56fe\u8868" in out
    assert 'CHART_VISIBLE False' in out
    assert 'MINIMAL True' in out
    assert 'NO_ADD True True' in out
    assert 'KEEP_BT True' in out
    assert 'RESULT_NO_CHART False' in out
    assert 'RESULT_TAB 1' in out
    assert 'CHART_TAB 2 True' in out
    assert 'TRADES_TAB 3' in out
    assert 'BTN_SYNC True' in out


def test_all_bars_open_by_default():
    """v1.0.97 修完卡死后默认**开放全部** K 线；``MINIQT_BACKTEST_BARS`` 可回到截断 ✓。

    之前（v1.0.96）为规避“拖动/缩放卡”只喂最近 2000 根；真凶是 NaN 缺口序列
    风暴 + ``setMarkers`` 挂死，修掉后全量实测流畅，故默认全量。
    """
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import ("
        "BacktestInterface as B)\n"
        "print('BARS', B.INITIAL_BARS)\n"
        "print('OFF_FULL', B._tail_offset(8964, 0))\n"
        "print('OFF_NEG', B._tail_offset(8964, -5))\n"
        "print('OFF_2000', B._tail_offset(8964, 2000))\n"
        "print('OFF_SMALL', B._tail_offset(500, 2000))\n"
        "print('OFF_BAD', B._tail_offset(8964, 'x'))\n"
    )
    out = _run(script).stdout
    assert 'BARS 0' in out                     # 默认全量 ✓
    assert 'OFF_FULL 0' in out                 # 全量：不丢前缀 ✓
    assert 'OFF_NEG 0' in out                  # 负数同样全量 ✓
    assert 'OFF_2000 6964' in out              # 截断：丢前 6964 根 ✓
    assert 'OFF_SMALL 0' in out                # 数据比窗口还少：不丢 ✓
    assert 'OFF_BAD 0' in out                  # 解析失败兜底全量，不崩 ✓


def test_info_page_reuses_marketwatch_legend_and_chart_time():
    """回测结果页与合约图**同一套图例 + 同一时间口径** ✓。

    * 图例：以前直接 ``chart.legend(visible=True, text=…)`` 会把字体/颜色
      退回 pylightcharts 默认（11px 浅灰）→ 比合约图小、淡 ✗；
      现在复用 ``_apply_panel_legend``（字号 + 主题文本色）✓。
    * 时间：``strategy_backtest_dict`` 的权益时间是策略原始 datetime（比图表
      时间早 8h），直接喂会在时间轴多出一整套错位点 → 蜡烛被 whitespace 撑成
      断断续续 ✗；现在统一过 ``_chart_time_frame``（``to_chart_time`` + 截尾）✓。
    """
    source = _read(PAGE)
    assert 'self._apply_panel_legend(self._current_contract)' in source
    assert 'self._chart_time_frame(data.get(\'equity\'))' in source
    assert 'self._chart_time_frame(data.get(\'drawdown\'))' in source
    assert 'self._chart_time_frame(data.get(\'pnl\'))' in source
    # 不能再退回默认参数的 legend（11px / 浅灰 ✗）
    assert 'chart.legend(visible=True,' not in source


def test_contract_indicators_have_settings_gear():
    """回测合约页的指标标签要挂上「设置」齿轮，且菜单能改样式 ✓。"""
    source = _read(PAGE)
    assert '_on_indicator_settings' in source
    assert 'enable_legend_settings' in source
    assert "'pin_legend_row'" in source
    # 菜单项：显隐 / 线型 / 线宽 / 价格线 / 价格标签 / 颜色
    assert 'INDICATOR_LINE_STYLES' in source
    assert "menu.addMenu('线型')" in source
    assert "menu.addMenu('线宽')" in source
    assert "'价格线'" in source and "'价格标签'" in source
    assert 'as_enum(value, LINE_STYLE)' in source
    assert 'series.repaint_gaps()' in source


def test_chart_time_frame_aligns_and_slices():
    """``_chart_time_frame``：时间对齐到图表口径，并按截断窗口切尾 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import pandas as pd\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface as B\n"
        "from miniqt.app.windows.backtest_chart import to_chart_time\n"
        "raw = pd.Series(pd.date_range('2025-01-01', periods=10, freq='min'))\n"
        "page = B.__new__(B)\n"
        "page._series_offset = 0\n"
        "aligned = page._chart_time_frame(pd.DataFrame({'time': raw,\n"
        "    'value': range(10)}))\n"
        "print('ALIGNED', list(aligned['time']) == list(to_chart_time(raw)))\n"
        "page._series_offset = 4\n"
        "sliced = page._chart_time_frame(pd.DataFrame({'time': raw,\n"
        "    'value': range(10)}))\n"
        "print('SLICED', len(sliced), sliced['time'].iloc[0] == to_chart_time(raw).iloc[4])\n"
        "print('NONE', page._chart_time_frame(None) is None)\n"
    )
    out = _run(script).stdout
    assert 'ALIGNED True' in out
    assert 'SLICED 6 True' in out
    assert 'NONE True' in out


def test_trades_tab_replaces_indicator_record_page():
    """原「指标记录」图表页已注释掉，改由独立「交易记录」tab 承担 ✓。"""
    source = _read(PAGE)
    assert "INFO_PAGES = ('回测结果',)" in source      # 图表顶栏只剩回测结果 ✓
    assert 'TRADES_TAB' in source
    assert '_ensure_trades_page' in source
    assert '_refresh_trades_page' in source
    assert '_save_trades' in source
    # 旧的 ReportPage 分支处于注释状态（保留作参考）✓
    assert '# else:                                  # 指标记录' in source


def test_gear_color_palette_is_inline():
    """齿轮菜单颜色用**常驻色板**（点一下生效）+「更多颜色…」兜底 ✓。"""
    source = _read(PAGE)
    assert 'COLOR_PALETTE' in source
    assert "menu.addMenu('颜色')" in source
    assert "'更多颜色…'" in source
    assert '_apply_series_color' in source
    assert "'#FF9800', '#2196F3'" in source            # 与 DEFAULT_COLORS 一致 ✓


def test_trades_tab_lists_and_formats_records():
    """「交易记录」tab：列表列名/格式与旧指标记录表一致，数据跟随策略 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "page._backtest = {'trades': [\n"
        "  {'time': '2025-01-01 09:00', 'direction': '\u5f00\u591a',\n"
        "   'symbol': 'DCE.v2601', 'price': 10.5, 'qty': 1, 'fee': 0.2,\n"
        "   'balance': 1000.0, 'pnl': 5.0},\n"
        "  {'time': '2025-01-01 10:00', 'direction': '\u5e73\u591a',\n"
        "   'symbol': 'DCE.v2601', 'price': 11.0, 'qty': 1, 'fee': 0.2,\n"
        "   'balance': 1005.0, 'pnl': -3.0}]}\n"
        "page._refresh_trades_page()\n"
        "m = page._trades_model\n"
        "from PyQt6.QtCore import Qt\n"
        "print('ROWS', m.rowCount(), 'COLS', m.columnCount())\n"
        "print('HEAD', [m.headerData(i, Qt.Orientation.Horizontal)\n"
        "               for i in range(m.columnCount())])\n"
        "print('CELL', m.data(m.index(0, 1)), m.data(m.index(0, 3)),\n"
        "      m.data(m.index(0, 7)), m.data(m.index(1, 7)))\n"
        "print('SORT', m.data(m.index(0, 3), Qt.ItemDataRole.UserRole),\n"
        "      page._trades_filter_button is not None)\n"
    )
    out = _run(script).stdout
    assert 'ROWS 2 COLS 8' in out
    assert ("HEAD ['\u65f6\u95f4', '\u65b9\u5411', '\u5408\u7ea6', "
            "'\u6210\u4ea4\u4ef7', '\u6570\u91cf', '\u624b\u7eed\u8d39', "
            "'\u6743\u76ca', '\u76c8\u4e8f']") in out
    assert 'CELL \u5f00\u591a 10.50 5.00 -3.00' in out
    assert 'SORT 10.5 True' in out


def test_trades_save_as_writes_csv():
    """「另存」把交易记录写成 CSV（列名 + 格式化值，UTF-8-BOM 便于 Excel ✓）。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import tempfile\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout,"
        " QFileDialog\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "path = os.path.join(tempfile.gettempdir(),"
        " 'miniqt_trades_test.csv')\n"
        "if os.path.exists(path): os.remove(path)\n"
        "QFileDialog.getSaveFileName = staticmethod("
        "lambda *a, **k: (path, ''))\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "page._backtest = {'trades': [\n"
        "  {'time': '2025-01-01', 'direction': '\u5f00\u591a',"
        " 'symbol': 'X', 'price': 10.5, 'qty': 1, 'fee': 0.2,"
        " 'balance': 1000.0, 'pnl': 5.0}]}\n"
        "page._refresh_trades_page()\n"
        "page._save_trades()\n"
        "print('EXISTS', os.path.exists(path))\n"
        "with open(path, encoding='utf-8-sig') as f:\n"
        "    lines = f.read().splitlines()\n"
        "print('HEAD', lines[0])\n"
        "print('ROW', lines[1])\n"
    )
    out = _run(script).stdout
    assert 'EXISTS True' in out
    assert ('HEAD \u65f6\u95f4,\u65b9\u5411,\u5408\u7ea6,\u6210\u4ea4\u4ef7,'
            '\u6570\u91cf,\u624b\u7eed\u8d39,\u6743\u76ca,\u76c8\u4e8f') in out
    assert ('ROW 2025-01-01,\u5f00\u591a,X,10.50,1,0.20,"1,000.00",5.00'
            in out)                              # 千分位逗号被 CSV 正常加引号 ✓


def test_header_has_reload_button():
    """顶栏 tab 行最右有「重载策略回测页面」图标按钮 ✓。"""
    source = _read(PAGE)
    assert 'TransparentToolButton' in source
    assert "'重载策略回测页面'" in source
    assert '_reload_backtest_page' in source
    assert 'FluentIcon.SYNC' in source


def test_reload_button_reruns_current_strategy():
    """重载：清空当前回测展示，再用当前策略文件重跑 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "calls = []\n"
        "page.run_backtest = lambda p='': calls.append(p) or True\n"
        "page._pending_file = 'X.py'\n"
        "page._backtest = {'trades': None}\n"
        "page._records = [{'name': 'A'}]\n"
        "page._reload_backtest_page()\n"
        "print('CALLS', calls)\n"
        "print('RESET', page._records, page._backtest)\n"
    )
    out = _run(script).stdout
    assert "CALLS ['X.py']" in out
    assert 'RESET [] {}' in out


def test_reload_button_falls_back_to_editor_and_blocks_while_running():
    """没跑过 → 交给编辑器；正在跑 → 只提示、不重入 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "seen = []\n"
        "page._editor_page.request_strategy_backtest = (\n"
        "    lambda: seen.append('editor'))\n"
        "page._pending_file = ''\n"
        "page._reload_backtest_page()\n"
        "print('EDITOR', seen)\n"
        "page._pending_file = 'X.py'\n"
        "ran = []\n"
        "page.run_backtest = lambda p='': ran.append(p) or True\n"
        "page._thread = object()          # 模拟正在回测\n"
        "page._reload_backtest_page()\n"
        "print('BLOCKED', ran, seen)\n"
    )
    out = _run(script).stdout
    assert "EDITOR ['editor']" in out
    assert "BLOCKED [] ['editor']" in out


def test_info_page_draws_trade_lines_for_every_contract():
    """回测结果页：每个合约都调用 `draw_trade_lines`（tail 对齐）✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import pandas as pd\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "import minibt.strategy.realtime as rt\n"
        "calls = []\n"
        "frame = pd.DataFrame({'time': pd.date_range('2020-01-01', periods=4,\n"
        "                     freq='min'), 'open': 1., 'high': 2., 'low': .5,\n"
        "                     'close': 1.5, 'volume': 1.})\n"
        "rt.strategy_kline_frame = lambda inst, c: frame.copy()\n"
        "rt.palette_for = lambda chart: ['#111111', '#222222']\n"
        "rt.draw_contract_info = lambda *a, **k: []\n"
        "def fake_trade(chart, inst, contract, fr, pane, **k):\n"
        "    calls.append((contract, pane, k.get('align'))); return [object()]\n"
        "rt.draw_trade_lines = fake_trade\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        + _FAKE_CHART +
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "fake = FakeChart(); page._chart = fake\n"
        "page._instance = object()\n"
        "page._contracts = ['A_60', 'B_60']\n"
        "page._backtest = {'stats': {}, 'trades': None}\n"
        "page._render_info_page('回测结果')\n"
        "print('CALLS', calls)\n"
        "print('OVERLAYS', len(page._info_overlay_series))\n"
    )
    out = _run(script).stdout
    assert "CALLS [('A_60', 0, 'tail'), ('B_60', 1, 'tail')]" in out
    assert 'OVERLAYS 2' in out


def test_contract_page_draws_trade_lines():
    """合约页：`_plot_contract_overlays` 也要画入场/离场连线（tail 对齐）✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import pandas as pd\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "import minibt.strategy.realtime as rt\n"
        "calls = []\n"
        "rt.extract_minibt_indicators = lambda *a, **k: []\n"
        "rt.extract_minibt_signals = lambda *a, **k: []\n"
        "def fake_trade(chart, inst, contract, fr, pane, **k):\n"
        "    calls.append((contract, pane, k.get('align'))); return [object()]\n"
        "rt.draw_trade_lines = fake_trade\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        + _FAKE_CHART +
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "fake = FakeChart(); page._chart = fake\n"
        "page._instance = object(); page._contracts = ['X_60']\n"
        "page._current_page = 'X_60'\n"
        "frame = pd.DataFrame({'time': pd.date_range('2020-01-01', periods=4,\n"
        "                     freq='min'), 'open': 1., 'high': 2., 'low': .5,\n"
        "                     'close': 1.5, 'volume': 1.})\n"
        "page._plot_contract_overlays(frame, 'X_60')\n"
        "print('CALLS', calls)\n"
    )
    out = _run(script).stdout
    assert "CALLS [('X_60', 0, 'tail')]" in out


# ---- 参数优化（回测按钮右边的按钮 + 进度条 + 优化结果表）------------------
def test_editor_has_optimize_button_right_of_backtest():
    """代码编辑器顶栏：**回测按钮右边**多一个「参数优化」按钮 ✓。

    * 新增信号 ``strategyOptimizeRequested``（带默认 path，同回测契约 ✓）；
    * 按钮顺序：``strategyBacktestButton`` 在前，``strategyOptimizeButton`` 在后；
    * 点击走 ``_prepare_active_file``（先保存活动标签再触发 ✓）。
    """
    source = _read(EDITOR)
    assert 'strategyOptimizeRequested = pyqtSignal(str)' in source
    assert 'self.strategyOptimizeButton = self._tool_button(' in source
    assert ('addWidget(self.strategyBacktestButton)'
            in source)
    assert ('addWidget(self.strategyOptimizeButton)'
            in source)
    assert (source.index('addWidget(self.strategyBacktestButton)')
            < source.index('addWidget(self.strategyOptimizeButton)'))
    assert 'def request_strategy_optimize' in source
    assert '_prepare_active_file(self._emit_strategy_optimize)' in source
    assert 'def _emit_strategy_optimize' in source
    assert ('self.strategyOptimizeRequested.emit('
            'self._valid_strategy_path(path))') in source
    # 只发**真实存在**的路径（停靠状态里的 file_path 可能已被删除 ✓）
    assert 'def _valid_strategy_path' in source


def test_strategy_catalog_finds_optimizable_classes():
    """静态识别：有 ``op_config`` 的 ``Strategy`` 子类才可参数优化 ✓。"""
    from miniqt.app.common import strategy_catalog as sc
    plain = (
        "from minibt import *\n"
        "class A(Strategy):\n"
        "    params = dict(length=10)\n"
        "    def next(self):\n        ...\n"
    )
    with_opt = (
        "from minibt import *\n"
        "class A(Strategy):\n"
        "    params = dict(length=10)\n"
        "    op_config = OpConfig(target=['profit'],"
        " params=dict(length=(5, 21, 1)))\n"
        "    def next(self):\n        ...\n"
    )
    annotated = (
        "from minibt import Strategy\n"
        "class B(Strategy):\n"
        "    op_config: object = None\n"
        "    def next(self):\n        ...\n"
    )
    assert sc.strategy_class_names(plain) == ['A']
    assert sc.optimizable_class_names(plain) == []          # 没 op_config ✗
    assert sc.optimizable_class_names(with_opt) == ['A']    # ✓
    assert sc.optimizable_class_names(annotated) == ['B']   # 带注解写法 ✓
    assert sc.optimizable_class_names('x = 1') == []
    assert sc.optimizable_class_names('def (') == []        # 语法错不崩 ✓
    assert sc.optimizable_class_names('') == []


def test_backtest_interface_optimize_wiring_source():
    """回测页：参数优化按钮 → 后台 worker → 进度条 → 优化结果表 ✓。"""
    source = _read(PAGE)
    # 编辑器信号接到本页 ✓
    assert ('page.strategyOptimizeRequested.connect(self.run_optimization)'
            in source)
    # 识别 Strategy 子类 + op_config ✓
    assert 'def _check_optimizable' in source
    assert 'optimizable_class_names' in source
    # 后台优化 worker + 进度信号 ✓
    assert 'def run_optimization' in source
    assert '_OptimizationWorker' in source
    assert 'worker.progress_signal.connect(self._on_opt_progress)' in source
    assert 'worker.finished_signal.connect(self._on_opt_finished)' in source
    # tabs 最下面的进度条 ✓
    assert 'def _build_progress_bar' in source
    assert 'self._progress_box' in source
    assert 'ProgressBar(' in source
    # 最优参数回测 → 复用正常回测展示；优化结果表 ✓
    assert 'def _apply_results' in source
    assert 'self._optimization_data' in source
    assert 'def _refresh_opt_table' in source
    assert "'参数优化'" in source                     # 子页 tab ✓
    # isRunning 也要认优化线程（优化时不能再点回测 ✓）
    assert 'def isRunning' in source
    assert 'self._thread is not None or self._opt_thread is not None' in source


def test_optimization_progress_and_result_table():
    """离屏：进度条默认隐藏 / 优化时显示并随 trial 前进；结果表随之显隐 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "print('OPT_BTN', hasattr(page._editor_page,"
        " 'strategyOptimizeButton'))\n"
        "print('PROGRESS_HIDDEN', page._progress_box.isHidden(),\n"
        "      page.progressBar is not None)\n"
        "print('OPT_TABLE_EMPTY', page._opt_table.rowCount(),\n"
        "      page._opt_table is not None)\n"
        "page._show_progress('参数优化中…')\n"
        "page._on_opt_progress(3, 10)\n"
        "print('PROGRESS_VISIBLE', not page._progress_box.isHidden(),\n"
        "      page.progressBar.value(), page.progressLabel.text())\n"
        "page._hide_progress()\n"
        "print('PROGRESS_GONE', page._progress_box.isHidden())\n"
        "page._optimization_data = [\n"
        "    {'number': 0, 'value': 1.2, 'params_len1': 5},\n"
        "    {'number': 1, 'value': 2.4, 'params_len1': 7}]\n"
        "page._refresh_opt_table()\n"
        "print('OPT_TABLE_SHOWN', page._opt_table.rowCount(),\n"
        "      page._opt_table.columnCount())\n"
        "print('OPT_HEADER', [page._opt_table.horizontalHeaderItem(i).text()\n"
        "      for i in range(page._opt_table.columnCount())])\n"
        "print('OPT_BTN_ON', not page._opt_save_button.isHidden(),\n"
        "      not page._opt_rerun_button.isHidden())\n"
        "page._optimization_data = []\n"
        "page._refresh_opt_table()\n"
        "print('OPT_EMPTY_AGAIN', page._opt_table.rowCount(),\n"
        "      page._opt_save_button.isHidden())\n"
    )
    out = _run(script).stdout
    assert 'OPT_BTN True' in out
    assert 'PROGRESS_HIDDEN True True' in out
    assert 'OPT_TABLE_EMPTY 0 True' in out
    assert 'PROGRESS_VISIBLE True 3 ' in out
    assert 'PROGRESS_GONE True' in out
    assert 'OPT_TABLE_SHOWN 2 3' in out
    assert "OPT_HEADER ['number', 'value', 'params_len1']" in out
    assert 'OPT_BTN_ON True True' in out
    assert 'OPT_EMPTY_AGAIN 0 True' in out


def test_optimize_entry_wired_from_marketwatch_and_mainwindow():
    """看盘窗口 / 主窗口：参数优化入口接到回测页 ✓。"""
    bus = _read(REPO / 'miniqt' / 'app' / 'common' / 'signal_bus.py')
    assert 'optimizeRequested = pyqtSignal(str)' in bus
    main = _read(MAIN)
    assert ('signalBus.optimizeRequested.connect(self.open_optimize_page)'
            in main)
    assert 'def open_optimize_page' in main
    assert 'page.run_optimization(path)' in main
    watch = _read(REPO / 'miniqt' / 'app' / 'windows'
                  / 'pylightcharts_window.py')
    assert 'def strategy_optimize_stub' in watch
    assert ('page.strategyOptimizeRequested.connect'
            '(self.strategy_optimize_stub)') in watch


def test_stale_editor_path_falls_back_to_active_file():
    """编辑器给的路径可能**已删除**（停靠状态残留）→ 不能直接报“请先选择策略” ✓。

    用户现场：``qtvscode_dock.json`` 里记的 ``teststrategy_2.py`` 已被删，
    ``getActiveText`` 又恰好返回空 → 一路退回过期 ``file_path`` → 点参数优化
    得到误导性的“请先选择策略”。现在：校验存在性 + DOM 反查当前活动标签重试 ✓。
    """
    script = (
        "import os, tempfile\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "ep = page._editor_page\n"
        "real = os.path.abspath('tutorials/basic/optstrategy.py')\n"
        "stale = os.path.join(tempfile.gettempdir(), 'gone_2.py')\n"
        "print('REAL', os.path.isfile(real))\n"
        "ep.file_path = stale; ep._active_path = ''\n"
        "print('RESOLVE_STALE', repr(page._resolve_strategy_path('')))\n"
        "ep.file_path = real\n"
        "print('RESOLVE_REAL', page._resolve_strategy_path('') == real)\n"
        "ep.file_path = stale; ep._active_path = ''\n"
        "ep.sync_active_file = lambda cb, timeout_ms=400: cb(real)\n"
        "seen = []\n"
        "page._detect_optimization_target = (\n"
        "    lambda p: seen.append(p) or ('', ''))\n"
        "page.run_optimization()\n"
        "print('SEEN_REAL', seen == [real])\n"
        "print('VALID_STALE', repr(ep._valid_strategy_path(stale)))\n"
        "ep.file_path = real\n"
        "print('VALID_REAL', ep._valid_strategy_path(stale) == real)\n"
    )
    out = _run(script).stdout
    assert 'REAL True' in out
    assert "RESOLVE_STALE ''" in out
    assert 'RESOLVE_REAL True' in out
    assert 'SEEN_REAL True' in out
    assert "VALID_STALE ''" in out
    assert 'VALID_REAL True' in out


def test_resolve_strategy_path_uses_bridge_active_editor_cache():
    """``_active_path`` / ``file_path`` 都过期时，回测页也要能用 bridge 缓存 ✓。"""
    script = (
        "import os, tempfile\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "ep = page._editor_page\n"
        "real = os.path.abspath('tutorials/basic/optstrategy.py')\n"
        "stale = os.path.join(tempfile.gettempdir(), 'gone_2.py')\n"
        "class _B: last_active_editor = real\n"
        "ep._bridge = _B(); ep._active_path = ''; ep.file_path = stale\n"
        "print('LAST', ep.last_active_file() == real)\n"
        "print('RESOLVE', page._resolve_strategy_path('') == real)\n"
        "class _E: last_active_editor = ''\n"
        "ep._bridge = _E()\n"
        "print('EMPTY', repr(page._resolve_strategy_path('')))\n"
    )
    out = _run(script).stdout
    assert 'LAST True' in out
    assert 'RESOLVE True' in out
    assert "EMPTY ''" in out


def test_file_picker_fallback_does_not_open_offscreen():
    """编辑器彻底报不出路径时，最后才弹文件选择框；**离屏不弹**（避免测试卡死 ✓）。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "ep = page._editor_page\n"
        "ep.file_path = ''; ep._active_path = ''\n"
        "ep._bridge = None\n"
        "print('PICK', repr(page._pick_strategy_file()))\n"
        "rec = []\n"
        "ep.sync_active_file = lambda cb, timeout_ms=400: cb('')\n"
        "page._check_strategies = lambda p: rec.append(p) or False\n"
        "page.run_backtest()\n"
        "print('REC', rec)\n"
        "page.run_optimization()\n"
        "print('REC2', rec)\n"
    )
    out = _run(script).stdout
    assert "PICK ''" in out
    assert 'REC []' in out
    assert 'REC2 []' in out


def test_trades_page_has_two_sub_tabs_and_split_toolbars():
    """「交易记录」tab 内分两个子页：交易记录（另存）+ 参数优化（其余按钮）✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "page.show_trades_page()\n"
        "print('SUB', page._trades_sub_stack.count())\n"
        "print('TRADES_TOOL', page._trades_save_button.text(),\n"
        "      hasattr(page, '_trades_search'),\n"
        "      page._trades_model is not None)\n"
        "print('OPT_TOOL', page._opt_save_button.text(),\n"
        "      page._opt_plot_button.text(), page._opt_rerun_button.text(),\n"
        "      page._opt_write_button.text())\n"
    )
    out = _run(script).stdout
    assert 'SUB 2' in out
    assert 'TRADES_TOOL \u53e6\u5b58 True True' in out
    assert ('OPT_TOOL \u53e6\u5b58\u4f18\u5316\u7ed3\u679c '
            '\u4f18\u5316\u56fe\u8868 \u7528\u9009\u4e2d\u89e3\u56de\u6d4b '
            '\u5199\u56de\u6700\u4f18\u53c2\u6570') in out


def test_trades_filter_uses_pandas_expression():
    """「筛选」用 pandas 风格表达式（``df['pnl'] > 0`` 等），「全部记录」恢复 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        "page._backtest = {'trades': [\n"
        "  {'time': '2025-01-01', 'direction': '\u5f00\u591a',\n"
        "   'symbol': 'A', 'price': 10.5, 'qty': 1, 'fee': 0.2,\n"
        "   'balance': 1000.0, 'pnl': 5.0},\n"
        "  {'time': '2025-01-02', 'direction': '\u5e73\u591a',\n"
        "   'symbol': 'B', 'price': 11.0, 'qty': 1, 'fee': 0.9,\n"
        "   'balance': 1005.0, 'pnl': -3.0}]}\n"
        "page._refresh_trades_page()\n"
        "print('ALL', page._trades_model.rowCount())\n"
        "page._trades_search.setText(\"df['pnl'] > 0\")\n"
        "page._apply_trade_filter()\n"
        "print('DF_SUB', page._trades_model.rowCount())\n"
        "page._clear_trade_filter()\n"
        "page._trades_search.setText('pnl > 0 & fee < 0.3')\n"
        "page._apply_trade_filter()\n"
        "print('MULTI', page._trades_model.rowCount())\n"
        "page._clear_trade_filter()\n"
        "print('CLEARED', page._trades_model.rowCount(),\n"
        "      repr(page._trades_search.text()))\n"
        "page._trades_search.setText('pnl >>> 0')\n"
        "page._apply_trade_filter()\n"
        "print('BAD_KEPT', page._trades_model.rowCount())\n"
        "page._trades_search.setText('__import__(\"os\")')\n"
        "page._apply_trade_filter()\n"
        "print('DANGER_KEPT', page._trades_model.rowCount())\n"
    )
    out = _run(script).stdout
    assert 'ALL 2' in out
    assert 'DF_SUB 1' in out
    assert 'MULTI 1' in out
    assert "CLEARED 2 ''" in out
    assert 'BAD_KEPT 2' in out          # 语法错 → 列表不变 ✓
    assert 'DANGER_KEPT 2' in out       # 危险写法被 AST 白名单挡住 ✓


def test_chart_min_bar_spacing_is_relaxed():
    """放开轻量图表默认缩放下限（minBarSpacing 0.5 → ~2000 根看不全 ✗）✓。"""
    source = _read(PAGE)
    assert 'time_scale_options' in source
    assert 'min_bar_spacing' in source


def test_signal_optimize_worker_runs(tmp_path):
    """指标信号优化 worker：op_config + data=LocalDatas → 最优参数回测结果 ✓。"""
    import textwrap
    from miniqt.app.windows.strategy_backtest_window import (
        _SignalOptimizeWorker)

    source = textwrap.dedent('''
        from minibt import *

        class MyMA(BtIndicator):
            data = LocalDatas.test
            lines = ['ma1', 'ma2', 'long_signal', 'short_signal',
                     'exitlong_signal', 'exitshort_signal']
            params = dict(length1=10, length2=20)
            overlap = dict(ma1=True, ma2=True)
            op_config = OptimizeConfig(
                params=dict(length1=(5, 9, 1), length2=(10, 14, 1)),
                target=['sharpe'], method='optuna',
                config={'n_trials': 3, 'show_progress_bar': False})

            def next(self):
                ma1 = self.close.sma(self.params.length1)
                ma2 = self.close.sma(self.params.length2)
                long_signal = ma1.cross_up(ma2)
                short_signal = ma1.cross_down(ma2)
                return ma1, ma2, long_signal, short_signal, \
                    short_signal, long_signal
    ''')
    path = tmp_path / 'sig.py'
    path.write_text(source, encoding='utf-8')

    class _Term:
        def write_msg(self, message):
            pass

    worker = _SignalOptimizeWorker(str(path), _Term())
    got = {}
    worker.finished_signal.connect(
        lambda inst, data: got.update(inst=inst, data=data))
    worker.extras_signal.connect(lambda e: got.update(extras=e))
    worker.error_signal.connect(lambda m: got.update(err=m))
    worker.run()
    assert not got.get('err'), got.get('err')
    assert len(got.get('inst', [])) == 1          # 最优参数的 Strategy ✓
    assert len(got.get('data', [])) == 3          # 3 条 trial ✓
    extras = got.get('extras') or {}
    assert extras.get('kind') == 'signal'
    assert extras.get('class_name') == 'MyMA'
    assert extras.get('best_params')


def test_optimization_target_prefers_strategy_then_indicator(tmp_path):
    """检测顺序：策略(op_config) > 指标(信号) > 都没有 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.backtest_interface import BacktestInterface\n"
        "host = QWidget(); lay = QVBoxLayout(host)\n"
        "page = BacktestInterface(host); lay.addWidget(page)\n"
        f"strat = {str(tmp_path / 's.py')!r}\n"
        f"ind = {str(tmp_path / 'i.py')!r}\n"
        f"none = {str(tmp_path / 'n.py')!r}\n"
        "print('STRAT', page._detect_optimization_target(strat))\n"
        "print('IND', page._detect_optimization_target(ind))\n"
        "print('NONE', page._detect_optimization_target(none))\n"
    )
    (tmp_path / 's.py').write_text(
        'from minibt import *\n'
        'class S(Strategy):\n'
        "    op_config = OpConfig(params=dict(a=(1, 5)))\n"
        '    def next(self): ...\n', encoding='utf-8')
    (tmp_path / 'i.py').write_text(
        'from minibt import *\n'
        'class I(BtIndicator):\n'
        "    lines = ['long_signal', 'exitlong_signal']\n"
        '    def next(self): ...\n', encoding='utf-8')
    (tmp_path / 'n.py').write_text('x = 1\n', encoding='utf-8')
    out = _run(script).stdout
    assert "STRAT ('strategy', 'S')" in out
    assert "IND ('indicator', 'I')" in out
    assert "NONE ('', '')" in out


def test_loader_skips_top_level_run_code(tmp_path):
    """导入编辑器文件时**只执行 import/class**，跳过顶层回测/优化/打印代码 ✓。

    用户脚本常在顶层写 ``ind = MyMA(kline)`` / ``result = ind.signal_backtest(...)``
    / ``result.pprint()``；导入时若照跑，既慢（真跑一遍优化）又容易因数据
    报错 → 误报“未找到 BtIndicator 子类”✗。
    """
    import textwrap
    from miniqt.app.windows.strategy_backtest_window import (
        StrategyBacktestWindow)

    source = textwrap.dedent('''
        from minibt import *

        class MyMA(BtIndicator):
            lines = ['long_signal', 'exitlong_signal']
            params = dict(n=5)
            def next(self): ...

        raise RuntimeError('顶层代码不应该被执行')
        print('也不应该打印')
    ''')
    path = tmp_path / 'sig_top.py'
    path.write_text(source, encoding='utf-8')
    classes = StrategyBacktestWindow._load_indicator_from_file(str(path), None)
    assert [c.__name__ for c in classes] == ['MyMA']


def test_loader_falls_back_to_module_level_kline(tmp_path):
    """类里没写 data 时，回退到模块级 ``kline`` / ``data``（兼容旧写法 ✓）。"""
    import textwrap
    from miniqt.app.windows.strategy_backtest_window import (
        StrategyBacktestWindow)

    source = textwrap.dedent('''
        from minibt import *

        kline = LocalDatas.test.kline

        class MyMA(BtIndicator):
            lines = ['long_signal', 'exitlong_signal']
            params = dict(n=5)
            def next(self): ...

        ind = MyMA(kline)
    ''')
    path = tmp_path / 'sig_fallback.py'
    path.write_text(source, encoding='utf-8')
    classes = StrategyBacktestWindow._load_indicator_from_file(str(path), None)
    assert [c.__name__ for c in classes] == ['MyMA']
    assert getattr(classes[0], 'data', None) is not None   # 回退到模块级 kline ✓
