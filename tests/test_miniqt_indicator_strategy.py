# coding: utf-8
"""「指标和策略」页面（仿 TradingView）测试 ✓。

壳 + 假数据；这里只测页面能建起来、控件齐全、流式布局 / 数字分页 / 主题切换 ✓。
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

REPO = pathlib.Path(__file__).resolve().parents[1]
PAGE = REPO / 'miniqt' / 'app' / 'view' / 'indicator_strategy_interface.py'
DETAIL = REPO / 'miniqt' / 'app' / 'windows' / 'indicator_detail_tab.py'
CARD = REPO / 'miniqt' / 'app' / 'components' / 'indicator_card.py'
PAGER = REPO / 'miniqt' / 'app' / 'components' / 'numbered_pager.py'
MAIN = REPO / 'miniqt' / 'app' / 'view' / 'main_window.py'

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
        timeout=180)
    if result.returncode != 0:
        pytest.fail(f'子进程失败（{result.returncode}）:\n'
                    f'{result.stdout}\n{result.stderr}')
    return result


# ---- 数字分页的页码算法（纯逻辑 ✓）--------------------------------------
def test_page_items_numbers_and_ellipsis():
    from miniqt.app.components.numbered_pager import page_items
    assert page_items(1, 1) == [1]
    assert page_items(5, 3) == [1, 2, 3, 4, 5]
    assert page_items(42, 1) == [1, 2, '...', 42]
    assert page_items(42, 5) == [1, '...', 4, 5, 6, '...', 42]
    assert page_items(42, 42) == [1, '...', 41, 42]


def test_page_module_uses_qfluentwidgets_buttons():
    """qfluentwidgets 只有圆点分页，数字分页要用它自己的按钮拼 ✓。"""
    source = _read(PAGER)
    assert 'TransparentToolButton' in source
    assert 'TransparentPushButton' in source
    assert 'FluentIcon.LEFT_ARROW' in source
    assert 'FluentIcon.RIGHT_ARROW' in source


# ---- 页面 / 卡片接线（源码级 ✓）------------------------------------------
def test_page_layout_uses_scrollarea_and_flowlayout():
    source = _read(PAGE)
    assert 'class IndicatorStrategyInterface(ScrollArea)' in source
    assert 'FlowLayout' in source                 # 流式布局 ✓
    assert 'PillPushButton' in source             # 表头胶囊标签页 ✓
    assert 'LargeTitleLabel' in source            # 大标题 ✓
    # 标签页：正在关注 → 收藏 ✓
    assert '"收藏"' in source
    assert '正在关注' not in source
    assert 'FAVORITES_TAB' in source
    assert 'ComboBox' in source and 'CheckBox' in source
    assert 'NumberedPager' in source              # 数字分页 ✓
    assert 'IndicatorCard' in source
    assert 'needAni=True' in source
    # 类型下拉去掉了「教育 / 开源」✓
    assert 'TYPE_FILTERS = (TYPE_ALL, TYPE_INDICATOR, TYPE_STRATEGY)' in source
    assert 'TYPE_STRATEGY = "策略"' in source
    # 仅开源 / 关于指标和策略 / 分享：暂不可用 ✓
    assert 'self.openOnlyCheck.setEnabled(False)' in source
    assert 'self.infoButton.setEnabled(False)' in source
    assert 'self.shareButton.setEnabled(False)' in source


def test_type_filter_indicator_vs_strategy():
    """选「指标」→ 只显指标；选「策略」→ 空（暂无策略）✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.indicator_strategy_interface import (\n"
        "    IndicatorStrategyInterface, TYPE_FILTERS, TYPE_INDICATOR,\n"
        "    TYPE_STRATEGY)\n"
        "w = IndicatorStrategyInterface()\n"
        "print('FILTERS', TYPE_FILTERS)\n"
        "print('DISABLED', w.openOnlyCheck.isEnabled(),\n"
        "      w.infoButton.isEnabled(), w.shareButton.isEnabled())\n"
        "w.typeCombo.setCurrentText(TYPE_INDICATOR)\n"
        "print('IND', len(w._visible), all(\n"
        "    i.get('kind', 'indicator') == 'indicator' for i in w._visible))\n"
        "w.typeCombo.setCurrentText(TYPE_STRATEGY)\n"
        "print('STRAT', len(w._visible))\n"
        "print('STRAT_CARDS', len(w._cards))\n"
        "print('HINT', '暂无策略' in w.hintLabel.text())\n"
    )
    result = _run(script)
    assert "FILTERS ('所有类型', '指标', '策略')" in result.stdout
    assert 'DISABLED False False False' in result.stdout
    assert 'IND 114 True' in result.stdout      # minibt 指标全在 ✓
    assert 'STRAT 0' in result.stdout           # 暂无策略 ✓
    assert 'STRAT_CARDS 0' in result.stdout
    assert 'HINT True' in result.stdout


def test_card_has_preview_and_text():
    source = _read(CARD)
    assert 'class IndicatorCard' in source
    assert 'make_preview_pixmap' in source         # 卡片预览图 ✓
    assert 'titleLabel' in source and 'descLabel' in source
    assert 'authorLabel' in source and 'statsLabel' in source


def test_all_controls_are_qfluentwidgets_no_manual_theme():
    """**全部用 qfluentwidgets 控件**，不手写深/浅样式（切主题自动跟随 ✓）。"""
    for path in (PAGE, CARD, PAGER):
        source = _read(path)
        code = '\n'.join(line for line in source.splitlines()
                         if not line.strip().startswith('#'))
        # 不能有原生 QLabel / 手写颜色样式
        assert 'QLabel(' not in code, path
        assert 'setStyleSheet' not in code, path
        assert 'isDarkTheme' not in code, path
    # 滚动区背景要透明，否则切深色主题时 viewport 还是浅底 ✗
    assert 'enableTransparentBackground()' in _read(PAGE)
    # 预览图用 qfluentwidgets 的 ImageLabel ✓
    assert 'ImageLabel' in _read(CARD)


def test_fit_preview_pixmap_scales_into_box():
    """大截图会被缩放到预览框大小（不能溢出整张卡片 ✗）✓。"""
    pytest.importorskip('PyQt6')
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QColor, QPixmap
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from miniqt.app.components.indicator_card import (
        fit_preview_pixmap, make_placeholder_pixmap, PREVIEW_WIDTH,
        PREVIEW_HEIGHT)
    from miniqt.app.components.indicator_card import IndicatorCard

    big = QPixmap(900, 500)
    big.fill(QColor('#123456'))
    out = fit_preview_pixmap(big)
    assert out.size() == QSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
    # 占位图本来就是这个尺寸 ✓
    assert make_placeholder_pixmap().size() == QSize(PREVIEW_WIDTH,
                                                     PREVIEW_HEIGHT)

    # 卡片：塞大图后预览标签仍保持预览框大小（之前会 setFixedSize(900,500) ✗）
    card = IndicatorCard({'name': 'X', 'title': 'X'})
    assert card.previewLabel.size() == QSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
    card.set_preview_pixmap(big)
    assert card.previewLabel.size() == QSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
    card.deleteLater()


def test_main_window_registers_the_page():
    source = _read(MAIN)
    assert 'IndicatorStrategyInterface(self)' in source
    assert 'FIF.MARKET' in source
    assert '"指标和策略"' in source


def test_card_click_opens_detail_tab():
    """点卡片 → `indicatorSelected` → 主窗口在标题栏开详情页 ✓。"""
    page = _read(PAGE)
    assert 'indicatorSelected = pyqtSignal(dict)' in page
    assert 'self.indicatorSelected.emit(' in page

    main = _read(MAIN)
    assert 'indicatorSelected.connect(' in main
    assert 'def open_indicator_detail_tab' in main
    assert 'IndicatorDetailTab' in main
    assert 'self.titleBar.addTab(tab)' in main


def test_detail_tab_structure():
    """详情页壳：表头 + 图表/原始码 标签页 + 静态图表 + 静态代码编辑器 ✓。"""
    source = _read(DETAIL)
    # 表头：OPEN-SOURCE MINIBT / 大标题 / 添加到收藏
    assert 'OPEN-SOURCE MINIBT' in source
    assert 'OPEN-SOURCE SCRIPT' not in source
    assert 'LargeTitleLabel' in source
    assert '添加到收藏' in source
    # 图表 / 原始码 两个标签页
    assert '("图表", "原始码")' in source
    assert 'QSplitter' in source and 'QStackedWidget' in source
    # 分隔条：高度 3 + 中性灰背景（深/浅都能用 ✓）
    assert 'setHandleWidth(3)' in source
    assert 'QSplitter::handle' in source
    # 图表 = pylightcharts 静态图（minibt 本地数据）+ **对应的指标**
    assert 'PylightchartsChartWindow' in source
    assert 'dataset_frame' in source
    assert 'add_indicator_to_manager' in source
    # 初始化就收起下方简介（图表更大 → 截图更大）✓
    assert 'self._minimized = True' in source
    assert 'self.belowSection.hide()' in source
    # 打开就只看**最后 200 根**（自动截图也是这个范围）✓
    assert 'def _show_last_bars' in source
    assert 'AUTO_SHOT_BARS = 200' in source
    assert 'self._show_last_bars(' in source
    assert 'set_visible_logical_range' in source
    # 截图按钮 + 异步截图（同步会堵死主线程 ✗）
    assert 'FluentIcon.CAMERA' in source
    assert 'def _manual_screenshot' in source
    assert 'def _auto_screenshot' in source
    assert 'def _capture_chart' in source
    assert 'runJavaScript(' in source and 'takeScreenshot' in source
    assert 'has_preview' in source and 'save_preview' in source
    # 手动截图按钮在最小化按钮的**左侧** ✓
    assert source.index('tabsRow.addWidget(self.shotButton)') < \
        source.index('tabsRow.addWidget(self.minButton)')
    # 代码 = qtvscode 静态编辑器
    assert 'from qtvscode import CodeEditor' in source
    assert 'read_only=True' in source
    # 合约搜索框（复刻看盘窗口工具栏）+ 数据前置重载 ✓
    assert 'def _open_symbol_search' in source
    assert 'def _load_symbol' in source
    assert 'def _on_symbol_frame' in source
    assert 'def _reload_chart_with' in source
    assert 'def _setup_detail_history' in source
    assert 'def _refresh_symbol_box' in source
    assert '_DetailFrameWorker' in source and 'fetch_symbol_frame' in source
    assert 'self.symbolBox' in source
    # 搜索数据要能从**数据库**回退读取（新报价预览没有 symbol_search_data ✓）
    assert 'def _contract_rows_from_db' in source
    assert 'get_search_table()' in source
    assert '连接天勤更换其它品种' in source          # 搜索框 tooltip ✓
    # 换合约后按设置取历史长度 / 数据长度，并具备无限历史 ✓
    assert 'INITIAL_FRAME_MAX' in source
    assert 'futuresHistoryLength' in source and 'futuresDataLength' in source
    assert 'def _setup_detail_history' in source
    # 周期按钮（复刻看盘窗口工具栏的周期菜单）✓
    assert '_IntervalButton' in source
    assert 'def _build_interval_menu' in source
    assert 'def _change_cycle' in source
    assert 'INTERVAL_GROUPS' in source and 'CustomIntervalDialog' in source
    assert 'self.cycleButton' in source
    # 操作条 / 简介 / 右侧信息卡
    assert '在图表上使用' in source
    assert 'self.useButton.clicked.connect(self._use_on_chart)' in source
    # 「在图表上使用」：已开图表→第 1 格；没开→当前报价第一个合约 1 分钟；
    # 没登录→弹登录窗并等登录后再开 ✓
    # 删除所有评论：图标按钮（同「删除图表」的 trash 图标）+ 文字放 tooltip ✓
    assert 'self.deleteCommentsButton = TransparentToolButton(' in source
    assert 'FluentIcon.DELETE' in source
    assert 'setToolTip("删除所有评论")' in source
    assert 'def _use_on_chart' in source
    assert 'def _attach_to_market_watch' in source
    assert 'def _current_quote_target' in source
    assert 'def _wait_for_login' in source
    assert 'start_minibt_chart(' in source
    assert 'panels()[0]' in source or 'panels[0]' in source
    assert '开源脚本' in source
    # 主题跟随：图表 + 编辑器都要跟 ✓
    assert 'def apply_theme' in source
    assert 'def _apply_chart_theme' in source
    assert 'dark=self._dark' in source
    # 最小化 / 最大化放在「图表 / 原始码」那一行最右边（总是可见）✓
    assert 'FluentIcon.MINIMIZE' in source
    assert 'FluentIcon.FULL_SCREEN' in source
    assert 'tabsRow.addWidget(self.minButton)' in source
    assert 'tabsRow.addWidget(self.maxButton)' in source
    assert 'def _toggle_minimize' in source
    assert 'def _toggle_maximize' in source
    assert 'def _on_escape' in source
    assert 'QShortcut' in source
    # 功能仍是：最小化/最大化**下方简介**那一格 ✓
    assert 'belowSection.hide()' in source
    assert 'mainSection.hide()' in source
    # 滚动区透明必须在 setWidget 之后（否则 viewport 还是原生浅底 ✗）
    assert source.index('scroll.setWidget(body)') < \
        source.index('scroll.enableTransparentBackground()')
    # 下方内容**固定宽度居中**：单列（开源脚本 + 类注释 + 免责声明 + 评论）✓
    assert 'CONTENT_MAX_WIDTH' in source
    assert 'class _CenteredBody' in source
    assert 'self.column.setFixedWidth(' in source
    assert 'row.addWidget(self._build_description(content))' in source
    assert '_build_sidebar' not in source          # 不再两栏并排 ✓
    # 合并顺序：开源脚本 → 标签 → 类注释 → 免责声明 → 评论 ✓
    order = [
        source.index('open_note = BodyLabel'),
        source.index('tagsRow.addWidget(PillPushButton'),
        source.index('box.addWidget(CaptionLabel("免责声明"'),
        source.index('self.commentTitle = SubtitleLabel'),
        source.index('self.postButton = PrimaryPushButton'),
    ]
    assert order == sorted(order)
    # 全部 qfluentwidgets，无原生 QLabel（分隔条的中性色 = 唯一允许的样式 ✓）
    code = '\n'.join(line for line in source.splitlines()
                     if not line.strip().startswith('#'))
    assert 'QLabel(' not in code
    assert 'rgba(140,140,140,0.35)' in code        # 中性灰，深/浅都能用 ✓


def test_detail_tab_builds_with_code_editor():
    """子进程真建详情页：代码页用的是 qtvscode 静态编辑器 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa（miniqt 启动时已导入 ✓）\n"
        "from PyQt6.QtWidgets import QApplication, QSplitter\n"
        "app = QApplication([])\n"
        "from miniqt.app.windows.indicator_detail_tab import (\n"
        "    IndicatorDetailTab, MOCK_SOURCE)\n"
        "tab = IndicatorDetailTab({'title': 'EMA30 Band Breakout',\n"
        "                          'author': 'EL-COBER', 'likes': 377})\n"
        "print('SYMBOL_OK', tab.symbol.startswith('指标:'))\n"
        "print('STACK', tab.stack.count())\n"
        "print('EDITOR', type(tab.codeEditor).__name__)\n"
        "print('RO', tab.codeEditor.isReadOnly())\n"
        "print('SRC', tab.codeEditor.toPlainText() == MOCK_SOURCE)\n"
        "print('TABS', len(tab._tabGroup.buttons()))\n"
        "print('HANDLE', tab.findChild(QSplitter).handleWidth())\n"
    )
    result = _run(script)
    assert 'SYMBOL_OK True' in result.stdout
    assert 'HANDLE 3' in result.stdout
    assert 'STACK 2' in result.stdout
    assert 'EDITOR CodeEditor' in result.stdout      # qtvscode 静态编辑器 ✓
    assert 'RO True' in result.stdout
    assert 'SRC True' in result.stdout
    assert 'TABS 2' in result.stdout


def test_split_minimize_maximize_logic():
    """最小化/最大化/ESC 的分割逻辑（纯逻辑，不起 webview ✓）。"""
    import types

    pytest.importorskip('PyQt6')
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from miniqt.app.windows.indicator_detail_tab import IndicatorDetailTab as T

    class _Splitter:
        def __init__(self):
            self._sizes = [600, 400]

        def sizes(self):
            return list(self._sizes)

        def height(self):
            return 1000

        def setSizes(self, sizes):
            self._sizes = list(sizes)

    class _Section:
        def __init__(self):
            self.visible = True

        def hide(self):
            self.visible = False

        def show(self):
            self.visible = True

        def isVisible(self):            # noqa: N802
            return self.visible

    host = types.SimpleNamespace(
        _split_ratio=0.5, _minimized=False, _maximized=False,
        splitter=_Splitter(), mainSection=_Section(), belowSection=_Section(),
        _update_split_buttons=lambda: None,
    )
    for name in ('_record_split_ratio', '_apply_split_ratio',
                 '_restore_split'):
        setattr(host, name, types.MethodType(getattr(T, name), host))
    # 最小化 → 收起下方；恢复 → 按记录比例回来 ✓
    T._toggle_minimize(host)
    assert host._minimized is True and not host.belowSection.visible
    T._toggle_minimize(host)
    app.processEvents()
    assert host._minimized is False and host.belowSection.visible
    # 最大化 → 隐藏上面；ESC → 恢复 ✓
    T._toggle_maximize(host)
    assert host._maximized is True and not host.mainSection.visible
    T._on_escape(host)
    app.processEvents()
    assert host._maximized is False and host.mainSection.visible
    # 拖动后记录的比例恢复时用上 ✓
    host.splitter.setSizes([700, 300])
    T._record_split_ratio(host)
    assert abs(host._split_ratio - 0.7) < 1e-6
    T._apply_split_ratio(host)
    assert host.splitter.sizes() == [700, 300]


def test_centered_body_width_logic():
    """下方内容宽度：不超过固定上限；窄窗口时跟着缩并居中 ✓。"""
    pytest.importorskip('PyQt6')
    from PyQt6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])
    from miniqt.app.windows.indicator_detail_tab import (
        CONTENT_MAX_WIDTH, CONTENT_MARGIN, CONTENT_MIN_WIDTH, _CenteredBody)

    body = _CenteredBody()
    col = QWidget(body)
    body.column = col
    # 大窗口 → 固定上限 ✓
    body.resize(CONTENT_MAX_WIDTH + CONTENT_MARGIN * 2 + 800, 400)
    body.apply_column_width()
    assert col.maximumWidth() == CONTENT_MAX_WIDTH
    # 小窗口 → 跟着缩（左右各留 CONTENT_MARGIN）✓
    body.resize(700, 400)
    body.apply_column_width()
    assert col.maximumWidth() == max(CONTENT_MIN_WIDTH,
                                     700 - CONTENT_MARGIN * 2)
    body.deleteLater()


def test_auto_screenshot_saves_preview(tmp_path):
    """异步截图回调 → 解码 → 存盘（首开自动截图链路 ✓）。"""
    script = (
        "import os, base64\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.common import indicator_previews as ip\n"
        f"ip.PREVIEW_DIR = {str(tmp_path)!r}\n"
        "from miniqt.app.windows.indicator_detail_tab import (\n"
        "    IndicatorDetailTab)\n"
        "class _Page:\n"
        "    def runJavaScript(self, js, cb):\n"
        "        assert 'takeScreenshot' in js\n"
        "        cb('data:image/png;base64,'\n"
        "           + base64.b64encode(b'PNGDATA').decode())\n"
        "class _View:\n"
        "    def page(self):\n"
        "        return _Page()\n"
        "class _Chart:\n"
        "    id = 'c1'\n"
        "    def get_webview(self):\n"
        "        return _View()\n"
        "tab = IndicatorDetailTab({'name': 'Demo_Ind', 'title': 'Demo'})\n"
        "tab._chart = _Chart()\n"
        "from PyQt6.QtTest import QTest\n"
        "tab._auto_screenshot()\n"
        "QTest.qWait(1600)\n"
        "print('HAS', ip.has_preview('Demo_Ind'))\n"
        "print('SIZE', os.path.getsize(ip.preview_path('Demo_Ind')))\n"
        "print('LOAD', ip.load_preview('Demo_Ind') != '')\n"
    )
    result = _run(script)
    assert 'HAS True' in result.stdout
    assert 'SIZE 7' in result.stdout
    assert 'LOAD True' in result.stdout


def test_manual_screenshot_overwrites_auto_skips(tmp_path):
    """手动截图覆盖旧图；自动截图在已有图时**不再截** ✓。"""
    script = (
        "import os, base64\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.common import indicator_previews as ip\n"
        f"ip.PREVIEW_DIR = {str(tmp_path)!r}\n"
        "from miniqt.app.windows.indicator_detail_tab import (\n"
        "    IndicatorDetailTab)\n"
        "import miniqt.app.windows.indicator_detail_tab as mod\n"
        "class _Page:\n"
        "    def runJavaScript(self, js, cb):\n"
        "        cb('data:image/png;base64,'\n"
        "           + base64.b64encode(b'NEWIMAGE').decode())\n"
        "class _View:\n"
        "    def page(self):\n"
        "        return _Page()\n"
        "class _Chart:\n"
        "    id = 'c1'\n"
        "    def get_webview(self):\n"
        "        return _View()\n"
        "tab = IndicatorDetailTab({'name': 'Demo_Ind', 'title': 'Demo'})\n"
        "tab._chart = _Chart()\n"
        "ip.save_preview('Demo_Ind', b'OLD')\n"
        "print('OLD', open(ip.preview_path('Demo_Ind'), 'rb').read())\n"
        "from PyQt6.QtTest import QTest\n"
        "tab._auto_screenshot()          # 已有图 → 不应改\n"
        "QTest.qWait(1600)\n"
        "print('AFTER_AUTO', open(ip.preview_path('Demo_Ind'), 'rb').read())\n"
        "tab._manual_screenshot()        # 手动 → 覆盖\n"
        "print('AFTER_MANUAL', open(ip.preview_path('Demo_Ind'), 'rb').read())\n"
    )
    result = _run(script)
    assert "OLD b'OLD'" in result.stdout
    assert "AFTER_AUTO b'OLD'" in result.stdout        # 自动不覆盖 ✓
    assert "AFTER_MANUAL b'NEWIMAGE'" in result.stdout  # 手动覆盖 ✓


def test_show_last_bars_sets_logical_range():
    """自动截图前把可视范围设到最后 AUTO_SHOT_BARS 根 ✓。"""
    import types

    from miniqt.app.windows.indicator_detail_tab import (
        AUTO_SHOT_BARS, IndicatorDetailTab as T)

    calls = []

    class _Chart:
        def set_visible_logical_range(self, start, end):
            calls.append((start, end))

    host = types.SimpleNamespace(_chart=_Chart(), _frame_len=1000)
    T._show_last_bars(host)
    assert calls == [(1000 - AUTO_SHOT_BARS, 1000)]
    # 数据不足 AUTO_SHOT_BARS 根 → 从 0 开始 ✓
    calls.clear()
    host._frame_len = 50
    T._show_last_bars(host)
    assert calls == [(0, 50)]
    # 没有图表 / 没数据 → 不崩、不调用 ✓
    T._show_last_bars(types.SimpleNamespace(_chart=None, _frame_len=0))


def test_detail_tab_starts_with_below_hidden():
    """打开详情页默认收起下方简介（图表/截图更大）✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.windows.indicator_detail_tab import (\n"
        "    IndicatorDetailTab)\n"
        "tab = IndicatorDetailTab({'title': 'X'})\n"
        "print('MINIMIZED', tab._minimized)\n"
        "print('BELOW_HIDDEN', tab.belowSection.isHidden())\n"
        "print('TOOLTIP', tab.minButton.toolTip()[:2])\n"
    )
    result = _run(script)
    assert 'MINIMIZED True' in result.stdout
    assert 'BELOW_HIDDEN True' in result.stdout
    assert 'TOOLTIP 恢复' in result.stdout


def test_card_mouse_release_does_not_error():
    """鼠标释放不能再报 ``signal has 1 argument(s) but 0 provided`` ✓。

    基类 ``CardWidget`` 有个无参 ``clicked``，子类同名单参信号会把它盖掉；
    这里真发一次 `QMouseEvent` 验证 ✓。
    """
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "from PyQt6.QtCore import QEvent, QPointF, Qt\n"
        "from PyQt6.QtGui import QMouseEvent\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.components.indicator_card import IndicatorCard\n"
        "card = IndicatorCard({'title': 'X', 'likes': 1})\n"
        "got = []\n"
        "card.selected.connect(lambda d: got.append(d))\n"
        "ev = QMouseEvent(\n"
        "    QEvent.Type.MouseButtonRelease, QPointF(1, 1), QPointF(1, 1),\n"
        "    Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,\n"
        "    Qt.KeyboardModifier.NoModifier)\n"
        "card.mouseReleaseEvent(ev)   # 以前这里 TypeError ✗\n"
        "print('FIRED', len(got) == 1)\n"
        "print('TITLE', got[0].get('title'))\n"
    )
    result = _run(script)
    assert 'FIRED True' in result.stdout
    assert 'TITLE X' in result.stdout


def test_detail_tab_theme_following():
    """标题栏里有本页时切主题，图表 + 编辑器都要跟着变 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "from qfluentwidgets import setTheme, Theme\n"
        "app = QApplication([])\n"
        "setTheme(Theme.DARK)\n"
        "from miniqt.app.windows.indicator_detail_tab import (\n"
        "    IndicatorDetailTab)\n"
        "tab = IndicatorDetailTab({'title': 'X'})\n"
        "print('START', tab.codeEditor._highlighter.is_dark())\n"
        "tab.apply_theme(False)\n"
        "print('LIGHT', tab.codeEditor._highlighter.is_dark())\n"
        "tab.apply_theme(True)\n"
        "print('DARK', tab.codeEditor._highlighter.is_dark())\n"
        "print('CHART_METHOD', hasattr(tab, '_apply_chart_theme'))\n"
    )
    result = _run(script)
    assert 'START True' in result.stdout
    assert 'LIGHT False' in result.stdout
    assert 'DARK True' in result.stdout
    assert 'CHART_METHOD True' in result.stdout


def test_card_click_emits_selected():
    """子进程：点卡片真的发出 `indicatorSelected`（带数据 ✓）。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.indicator_strategy_interface import (\n"
        "    IndicatorStrategyInterface)\n"
        "w = IndicatorStrategyInterface()\n"
        "got = []\n"
        "w.indicatorSelected.connect(lambda d: got.append(d))\n"
        "w._cards[0].selected.emit(w._cards[0].data)\n"
        "print('FIRED', len(got) == 1)\n"
        "print('HAS_NAME', bool(got[0].get('name')))\n"
    )
    result = _run(script)
    assert 'FIRED True' in result.stdout
    assert 'HAS_NAME True' in result.stdout


# ---- 动态发现 minibt 指标（纯逻辑 ✓）------------------------------------
def test_indicator_favorites_roundtrip(tmp_path, monkeypatch):
    """收藏持久化：add / remove / toggle / is_favorite ✓。"""
    mod = pytest.importorskip('miniqt.app.common.indicator_favorites')
    monkeypatch.setattr(mod, 'FAVORITES_FILE', str(tmp_path / 'fav.json'))
    mod._CACHE.clear()
    assert mod.favorites() == []
    assert mod.is_favorite('A') is False
    assert mod.toggle('A') is True
    assert mod.is_favorite('A') is True
    assert mod.add('B') is True
    assert set(mod.favorites()) == {'A', 'B'}
    assert mod.toggle('A') is False
    assert mod.favorites() == ['B']
    assert mod.remove('B') is True
    assert mod.favorites() == []
    assert mod.toggle('') is False          # 空名字不崩 ✓


def test_indicator_stats_roundtrip(tmp_path, monkeypatch):
    """点赞 / 浏览 / 评论统计持久化 ✓。"""
    mod = pytest.importorskip('miniqt.app.common.indicator_stats')
    monkeypatch.setattr(mod, 'STATS_FILE', str(tmp_path / 'stats.json'))
    mod._CACHE.clear()
    assert mod.get('A') == {'likes': 0, 'liked': False, 'views': 0,
                            'comments': []}
    assert mod.toggle_like('A') is True
    assert mod.likes('A') == 1 and mod.is_liked('A') is True
    assert mod.toggle_like('A') is False
    assert mod.likes('A') == 0 and mod.is_liked('A') is False
    assert mod.add_view('A') == 1
    assert mod.add_view('A') == 2
    assert mod.views('A') == 2
    assert mod.add_comment('A', '   ') == 0          # 空内容不加 ✓
    assert mod.add_comment('A', 'hello') == 1
    assert mod.add_comment('A', 'world') == 2
    assert mod.comments('A')[0]['text'] == 'hello'
    assert mod.delete_comments('A') == 2
    assert mod.comment_count('A') == 0


def test_card_stats_from_indicator_stats(tmp_path):
    """卡片的点赞 / 评论数与本地统计一致 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.common import indicator_stats as st\n"
        f"st.STATS_FILE = {str(tmp_path / 'stats.json')!r}\n"
        "st._CACHE.clear()\n"
        "for _ in range(5):\n"
        "    st.toggle_like('Demo_Ind')\n"
        "st.add_view('Demo_Ind')\n"
        "st.add_comment('Demo_Ind', 'a')\n"
        "st.add_comment('Demo_Ind', 'b')\n"
        "from miniqt.app.components.indicator_card import IndicatorCard\n"
        "card = IndicatorCard({'name': 'Demo_Ind', 'title': 'X'})\n"
        "print('STATS', card.statsLabel.text())\n"
    )
    result = _run(script)
    # 5 次 toggle → 点赞 1（奇数）；评论 2；浏览 1
    assert 'STATS' in result.stdout
    assert '👍 1' in result.stdout
    assert '💬 2' in result.stdout


def test_detail_stats_and_comments(tmp_path):
    """详情页：打开 +1 浏览；点赞 +1/-1；空评论不发表；删评论 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.common import indicator_stats as st\n"
        f"st.STATS_FILE = {str(tmp_path / 'stats.json')!r}\n"
        "st._CACHE.clear()\n"
        "from miniqt.app.windows.indicator_detail_tab import (\n"
        "    IndicatorDetailTab)\n"
        "tab = IndicatorDetailTab({'name': 'Demo_Ind', 'title': 'Demo'})\n"
        "print('VIEWS', st.views('Demo_Ind'))\n"
        "tab.register_view()\n"
        "print('VIEWS2', st.views('Demo_Ind'))\n"
        "tab._on_like_clicked()\n"
        "print('LIKES', st.likes('Demo_Ind'), st.is_liked('Demo_Ind'))\n"
        "tab._on_like_clicked()\n"
        "print('LIKES2', st.likes('Demo_Ind'), st.is_liked('Demo_Ind'))\n"
        "tab.commentEdit.setPlainText('   ')\n"
        "tab._on_post_comment()\n"
        "print('EMPTY', st.comment_count('Demo_Ind'))\n"
        "tab.commentEdit.setPlainText('first')\n"
        "tab._on_post_comment()\n"
        "tab.commentEdit.setPlainText('second')\n"
        "tab._on_post_comment()\n"
        "print('COMMENTS', st.comment_count('Demo_Ind'))\n"
        "print('TITLE', tab.commentTitle.text())\n"
        "print('LABEL', tab.commentCount.text())\n"
        "tab._on_delete_comments()\n"
        "print('AFTER', st.comment_count('Demo_Ind'))\n"
        "print('LABEL2', tab.commentCount.text())\n"
    )
    result = _run(script)
    assert 'VIEWS 1' in result.stdout
    assert 'VIEWS2 2' in result.stdout    # 复用标签页再浏览一次 ✓
    assert 'LIKES 1 True' in result.stdout
    assert 'LIKES2 0 False' in result.stdout
    assert 'EMPTY 0' in result.stdout
    assert 'COMMENTS 2' in result.stdout
    assert 'TITLE 2 条评论' in result.stdout
    assert 'LABEL 2' in result.stdout
    assert 'AFTER 0' in result.stdout
    assert 'LABEL2 0' in result.stdout


def test_detail_sidebar_minibt_open_source_and_disabled_follow(tmp_path):
    """侧栏：minibt 版本说明 / 免责声明换说法 / 关注按钮不可用 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.common import indicator_stats as st\n"
        f"st.STATS_FILE = {str(tmp_path / 'stats.json')!r}\n"
        "st._CACHE.clear()\n"
        "from qfluentwidgets import PushButton, BodyLabel\n"
        "from miniqt.app.windows.indicator_detail_tab import (\n"
        "    IndicatorDetailTab)\n"
        "tab = IndicatorDetailTab({'name': 'Demo_Ind', 'title': 'Demo'})\n"
        "follows = [b for b in tab.findChildren(PushButton)\n"
        "           if b.text() == '关注']\n"
        "print('FOLLOW', len(follows),\n"
        "      follows[0].isEnabled() if follows else 'none')\n"
        "body = ' '.join(b.text() for b in tab.findChildren(BodyLabel))\n"
        "print('HAS_MINIBT', 'MiniBT' in body)\n"
        "print('OLD', 'TradingView 提供或认可' in body)\n"
        "print('NEW', '仅供技术研究与学习交流' in body)\n"
    )
    result = _run(script)
    assert 'FOLLOW 1 False' in result.stdout       # 关注按钮存在且置灰 ✓
    assert 'HAS_MINIBT True' in result.stdout      # minibt 版本说明 ✓
    assert 'OLD False' in result.stdout            # 旧免责声明已换掉 ✓
    assert 'NEW True' in result.stdout             # 新免责声明（换了说法）✓


def test_detail_contract_search_data_first(tmp_path):
    """详情页合约搜索：未登录置灰 / 登录后可用；**数据前置**取回后静态重载 ✓。"""
    script = '''
import os, tempfile
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import PyQt6.QtWebEngineWidgets  # noqa
import pandas as pd
from PyQt6.QtWidgets import QApplication, QWidget
app = QApplication([])
from miniqt.app.common import indicator_stats as st
st.STATS_FILE = os.path.join(tempfile.mkdtemp(), 'stats.json')
st._CACHE.clear()
from miniqt.app.windows.indicator_detail_tab import IndicatorDetailTab


class Chart:
    id = 'c1'


class FakeChartWindow:
    def __init__(self):
        self.chart = Chart()
        self.panel_frames = {}
        self.calls = []

    def clear_indicators(self):
        self.calls.append('clear')

    def set_data(self, frame):
        self.calls.append(('set_data', len(frame)))

    def add_indicator_to_manager(self, group, name, params=None, **kw):
        self.calls.append(('add', group, name))
        return {'id': 1}


class FakeMain(QWidget):
    def __init__(self):
        super().__init__()
        self.tq_api = None
        self.titleBar = type('T', (), {'qobject': {}})()

    def start_minibt_chart(self, *a, **k):
        pass


main = FakeMain()
tab = IndicatorDetailTab(
    {'name': 'Adaptive_Trend_Filter', 'group': 'TradingView'}, main)
print('HAS_BOX', tab.symbolBox is not None)
# 周期按钮（复刻看盘窗口工具栏，默认 1分）✓
print('CYCLE0', tab.cycleButton.text(), tab._cycle)
tab._change_cycle(300)
print('CYCLE1', tab.cycleButton.text(), tab._cycle)
# 未登录 → 搜索框 + 周期按钮都置灰 ✓
tab._refresh_symbol_box()
print('DISABLED', not tab.symbolBox.isEnabled(),
      not tab.cycleButton.isEnabled())
# 登录后 → 都可用 ✓
main.tq_api = object()
tab._refresh_symbol_box()
print('ENABLED', tab.symbolBox.isEnabled(), tab.cycleButton.isEnabled())
# **数据前置**：直接喂一帧（模拟后台取数回来）→ 静态重载（不取数 / 不起实时）
fw = FakeChartWindow()
tab.chartWindow = fw
frame = pd.DataFrame({
    'time': pd.date_range('2024-01-01', periods=300, freq='min'),
    'open': [1.0] * 300, 'high': [2.0] * 300, 'low': [0.5] * 300,
    'close': [1.5] * 300, 'volume': [9] * 300})
tab._on_symbol_frame('SHFE.ag2612', False, 100, 300, frame)
print('FRAME_LEN', tab._frame_len)
# 历史长度 300 > 数据长度 100 → 整段历史都入图（往左翻就能看到 ✓）
print('SET_DATA', ('set_data', 300) in fw.calls)
print('ADD', ('add', 'TradingView', 'Adaptive_Trend_Filter') in fw.calls)
print('CLEAR', 'clear' in fw.calls)
print('PANEL_FRAME', 'c1' in fw.panel_frames and len(fw.panel_frames['c1']) == 300)
# 超大历史 → 初始入图被压到 INITIAL_FRAME_MAX（剩下靠无限历史懒加载 ✓）
fw2 = FakeChartWindow()
tab.chartWindow = fw2
big = pd.concat([frame] * 24, ignore_index=True)
big['time'] = pd.date_range('2024-01-01', periods=len(big), freq='min')
tab._on_symbol_frame('SHFE.ag2612', False, 1000, len(big), big)
print('BIG_FRAME_LEN', tab._frame_len)
print('SYMBOL', tab._symbol, tab.symbolBox.codeLabel.text())
# 没开看盘窗口 / 报价窗口时为 None → 必须回退到**数据库**才能搜到合约 ✓
rows = tab._search_rows(main)
print('SEARCH_EQ_DB', rows == tab._contract_rows_from_db())
print('SEARCH_N', len(rows) > 0)
'''
    result = _run(script)
    assert 'HAS_BOX True' in result.stdout
    assert 'CYCLE0 1分 60' in result.stdout
    assert 'CYCLE1 5分 300' in result.stdout
    assert 'DISABLED True True' in result.stdout     # 未登录都置灰 ✓
    assert 'ENABLED True True' in result.stdout      # 登录后都可用 ✓
    assert 'FRAME_LEN 300' in result.stdout
    assert 'SET_DATA True' in result.stdout
    assert 'ADD True' in result.stdout
    assert 'CLEAR True' in result.stdout
    assert 'PANEL_FRAME True' in result.stdout
    assert 'BIG_FRAME_LEN 5000' in result.stdout
    assert 'SYMBOL SHFE.ag2612 SHFE.ag2612' in result.stdout
    # 搜索数据回退到数据库（否则详情页搜不到合约 ✗）✓
    assert 'SEARCH_EQ_DB True' in result.stdout
    assert 'SEARCH_N True' in result.stdout


def test_use_on_chart_first_panel_and_open_new(tmp_path):
    """「在图表上使用」：已开图表→第 1 格；没开→当前报价第一个合约 1 分钟；
    没登录→先弹登录，登录后再自动打开 ✓。"""
    script = '''
import os, tempfile
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import PyQt6.QtWebEngineWidgets  # noqa
from PyQt6.QtWidgets import QApplication, QWidget
app = QApplication([])
from miniqt.app.common import indicator_stats as st
st.STATS_FILE = os.path.join(tempfile.mkdtemp(), 'stats.json')
st._CACHE.clear()


class Panel:
    id = 'p0'


class ChartWindow:
    def __init__(self):
        self.panel = Panel()
        self.calls = []

    def panels(self):
        return [self.panel]

    def add_indicator_to_manager(self, group, name, params=None, target=None,
                                 **kw):
        self.calls.append((group, name, target))
        return {'id': 1}


class MarketWatch:
    def __init__(self, symbol):
        self.symbol = symbol
        self.chart_window = ChartWindow()


class TitleBar:
    def __init__(self):
        self.qobject = {}
        self.current = None

    def _safe_set_current_widget(self, w):
        self.current = w


class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.titleBar = TitleBar()
        self.tq_api = object()
        self.start_calls = []
        self.preview = type('P', (), {})()
        self.preview._tape_symbols = ['DCE.i2609']
        self.preview._type_by_symbol = {'DCE.i2609': 'FUTURE'}
        # 主力合约表：上期所优先（用户要求）✓
        self.tq_object = type('T', (), {})()
        self.tq_object.exchanges = {
            '主力': {'上期所': ['SHFE.ag2612', 'SHFE.cu2610'],
                     '大商所': ['DCE.i2609']}}

    def start_minibt_chart(self, symbol, cycle=60, is_stock=False, **kw):
        self.start_calls.append((symbol, cycle, is_stock))
        mw = MarketWatch(symbol)
        self.titleBar.qobject[symbol] = mw
        return mw


class NotLoggedMain(Main):
    def __init__(self):
        super().__init__()
        self.tq_api = None
        self.tq_object = None      # 没登录也拿不到主力表 → 回退报价窗口 ✓

    def start_minibt_chart(self, symbol, cycle=60, is_stock=False, **kw):
        self.start_calls.append((symbol, cycle, is_stock))
        if self.tq_api is None:
            return None            # 模拟“弹出登录窗、未打开” ✓
        mw = MarketWatch(symbol)
        self.titleBar.qobject[symbol] = mw
        return mw


from miniqt.app.windows.indicator_detail_tab import IndicatorDetailTab
NAME = 'Demo_Ind'
DATA = {'name': NAME, 'group': 'TradingView'}

# 1) 已打开图表 → 加到第 1 格 ✓
main = Main()
opened = MarketWatch('SHFE.rb2610')
main.titleBar.qobject['SHFE.rb2610'] = opened
tab = IndicatorDetailTab(dict(DATA), main)
tab._use_on_chart()
print('KEPT', main.start_calls == [])
print('CALL', opened.chart_window.calls[0][0], opened.chart_window.calls[0][1])
print('TARGET', opened.chart_window.calls[0][2] is opened.chart_window.panel)

# 2) 没打开图表 → **上期所第一只主力合约**、1 分钟 ✓
main2 = Main()
tab2 = IndicatorDetailTab(dict(DATA), main2)
tab2._use_on_chart()
print('OPEN', main2.start_calls)
print('NEWCALL',
      main2.titleBar.qobject['SHFE.ag2612'].chart_window.calls[0][:2])

# 2b) 主力表拿不到 → 回退当前报价窗口第一个合约 ✓
main2b = Main()
main2b.tq_object = None
tab2b = IndicatorDetailTab(dict(DATA), main2b)
tab2b._use_on_chart()
print('FALLBACK', main2b.start_calls)

# 3) 没登录 → 先弹登录；登录成功后 _wait_for_login 自动打开 ✓
main3 = NotLoggedMain()
tab3 = IndicatorDetailTab(dict(DATA), main3)
tab3._use_on_chart()
print('LOGIN_WAIT', main3.start_calls)
main3.tq_api = object()
tab3._wait_for_login('TradingView', NAME, None, 'DCE.i2609', False)
print('LOGIN_OPEN', main3.start_calls)
print('LOGIN_ADD',
      main3.titleBar.qobject['DCE.i2609'].chart_window.calls[0][:2])
'''
    result = _run(script)
    assert 'KEPT True' in result.stdout              # 不再新开图 ✓
    assert 'CALL TradingView Demo_Ind' in result.stdout
    assert 'TARGET True' in result.stdout            # 第 1 格 ✓
    # 上期所第一只主力合约优先 ✓
    assert "OPEN [('SHFE.ag2612', None, False)]" in result.stdout
    assert "NEWCALL ('TradingView', 'Demo_Ind')" in result.stdout
    # 主力表拿不到 → 回退当前报价窗口 ✓
    assert "FALLBACK [('DCE.i2609', None, False)]" in result.stdout
    assert "LOGIN_WAIT [('DCE.i2609', None, False)]" in result.stdout
    assert "LOGIN_ADD ('TradingView', 'Demo_Ind')" in result.stdout


def test_favorites_tab_shows_only_favorites(tmp_path):
    """切到「收藏」标签页 → 只显示收藏的指标 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.common import indicator_favorites as fav\n"
        f"fav.FAVORITES_FILE = {str(tmp_path / 'fav.json')!r}\n"
        "fav._CACHE.clear()\n"
        "from miniqt.app.common.tradingview_indicators import (\n"
        "    list_indicators)\n"
        "names = [i['name'] for i in list_indicators()][:3]\n"
        "for n in names:\n"
        "    fav.add(n)\n"
        "from miniqt.app.view.indicator_strategy_interface import (\n"
        "    IndicatorStrategyInterface)\n"
        "w = IndicatorStrategyInterface()\n"
        "print('ALL', len(w._visible))\n"
        "w._on_tab_changed('收藏')\n"
        "print('FAV', len(w._visible))\n"
        "print('CARDS', len(w._cards))\n"
        "print('NAMES_OK',\n"
        "      {c.data['name'] for c in w._cards} <= set(names))\n"
    )
    result = _run(script)
    assert 'FAV 3' in result.stdout
    assert 'CARDS 3' in result.stdout
    assert 'NAMES_OK True' in result.stdout


def test_detail_fav_buttons_synced(tmp_path):
    """详情页两个收藏按钮同步（右上角 + 图表/编辑器下方）✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.common import indicator_favorites as fav\n"
        f"fav.FAVORITES_FILE = {str(tmp_path / 'fav.json')!r}\n"
        "fav._CACHE.clear()\n"
        "from miniqt.app.windows.indicator_detail_tab import (\n"
        "    IndicatorDetailTab)\n"
        "tab = IndicatorDetailTab({'name': 'Demo_Ind', 'title': 'Demo'})\n"
        "print('START', tab.favButton.isChecked(),\n"
        "      tab.favButton2.isChecked())\n"
        "tab.favButton.setChecked(True)\n"
        "print('AFTER1', tab.favButton.isChecked(),\n"
        "      tab.favButton2.isChecked(), fav.is_favorite('Demo_Ind'))\n"
        "tab.favButton2.setChecked(False)\n"
        "print('AFTER2', tab.favButton.isChecked(),\n"
        "      tab.favButton2.isChecked(), fav.is_favorite('Demo_Ind'))\n"
    )
    result = _run(script)
    assert 'START False False' in result.stdout
    assert 'AFTER1 True True True' in result.stdout
    assert 'AFTER2 False False False' in result.stdout


def test_tradingview_indicators_discovery():
    mod = pytest.importorskip('miniqt.app.common.tradingview_indicators')
    items = mod.list_indicators()
    assert len(items) > 50                       # tradingview.py 里上百个 ✓
    keys = {'group', 'name', 'title', 'desc', 'doc', 'source', 'path',
            'params', 'seed'}
    for item in items[:5]:
        assert keys <= set(item)
        assert item['group'] == 'TradingView'
        assert item['name'] and item['title']
        assert item['source'].startswith('# coding: utf-8')
        # 编辑器里：先 from minibt import BtIndicator，空 2 行，再接指标类 ✓
        assert 'from minibt import BtIndicator\n\n\nclass ' in item['source']
        assert item['path'].endswith('tradingview.py')
    assert mod.get_indicator(items[0]['name'])['name'] == items[0]['name']
    assert mod.get_indicator('no_such_indicator') == {}


def test_indicator_previews_roundtrip(tmp_path, monkeypatch):
    mod = pytest.importorskip('miniqt.app.common.indicator_previews')
    monkeypatch.setattr(mod, 'PREVIEW_DIR', str(tmp_path / 'prev'))
    assert mod.has_preview('X') is False
    assert mod.load_preview('X') == ''
    path = mod.save_preview('X', b'\x89PNG\r\n\x1a\n data')
    assert path and mod.has_preview('X') is True
    assert mod.load_preview('X') == path
    assert mod.save_preview('X', b'') == ''       # 空数据不存 ✓
    mod.clear('X')
    assert mod.has_preview('X') is False


# ---- 真建页面（子进程 ✓）-------------------------------------------------
def test_interface_loads_tradingview_indicators():
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.indicator_strategy_interface import (\n"
        "    IndicatorStrategyInterface, PAGE_SIZE)\n"
        "w = IndicatorStrategyInterface()\n"
        "print('TOTAL', len(w._items))\n"
        "print('PAGESIZE', PAGE_SIZE)\n"
        "print('PAGE1', len(w._cards) <= PAGE_SIZE)\n"
        "print('FLOW', w.flowLayout.count() == len(w._cards))\n"
        "print('TABS', len(w._tabGroup.buttons()))\n"
        "print('PAGER', w.pager.total_pages() > 1)\n"
        "w.pager.set_current_page(w.pager.total_pages())\n"
        "print('LASTPAGE', len(w._cards) > 0)\n"
        "w.resize(1400, 900)\n"
        "w.flowLayout.activate()\n"
        "print('TRANSPARENT', 'transparent' in w.styleSheet())\n"
    )
    result = _run(script)
    assert 'TOTAL 114' in result.stdout
    assert 'PAGESIZE 20' in result.stdout
    assert 'PAGE1 True' in result.stdout
    assert 'FLOW True' in result.stdout
    assert 'TABS 2' in result.stdout        # 市场 / 编辑精选暂时注释 ✓
    assert 'PAGER True' in result.stdout
    assert 'LASTPAGE True' in result.stdout
    assert 'TRANSPARENT True' in result.stdout


def test_detail_tab_uses_indicator_source_and_doc():
    """详情页：编辑器读指标类源码、简介用类注释 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.common.tradingview_indicators import (\n"
        "    get_indicator)\n"
        "from miniqt.app.windows.indicator_detail_tab import (\n"
        "    IndicatorDetailTab, _doc_paragraphs)\n"
        "item = get_indicator('UT_Bot_Alerts')\n"
        "tab = IndicatorDetailTab(item)\n"
        "print('SRC', tab.codeEditor.toPlainText() == item['source'])\n"
        "print('DOC', len(_doc_paragraphs(item['doc'])) > 0)\n"
    )
    result = _run(script)
    assert 'SRC True' in result.stdout
    assert 'DOC True' in result.stdout
