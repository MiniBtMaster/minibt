"""应用主题（深色 / 浅色）的**在线切换**。

背景：miniqt 以前「设置 → 系统设置 → 应用主题」改完要**重启才生效**，而且切换后
有的控件深、有的浅。根因有两个：

1. ``chart_config.py`` 调了 ``qconfig.load(path, chart_cfg)``，把全局 ``qconfig._cfg``
   绑到了图表配置上；主配置 config.json 里的主题被 chart_config.json 覆盖；
2. 设置页写的是 ``cfg.pendingThemeMode``（另一个 ConfigItem），且不调 ``setTheme``，
   所以样式表根本不刷新。

修完的约束：全局 qconfig 只认主配置 config.json；``setTheme`` 立即生效；自定义控件
（标题栏 / 首页 banner / 图表 / 代码编辑器 …）在 ``MainWindow.apply_theme`` 里统一刷新。
"""
from __future__ import annotations

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# 必须在创建 QApplication 之前导入（否则 PyQt6 会报 QtWebEngineWidgets 导入太晚）
import PyQt6.QtWebEngineWidgets  # noqa: F401,E402

import pytest  # noqa: E402

pytest.importorskip('PyQt6')


@pytest.fixture(scope='module', autouse=True)
def _app():
    from PyQt6.QtWidgets import QApplication
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture
def restore_theme():
    from qfluentwidgets import Theme, setTheme
    from qfluentwidgets.common.config import qconfig
    original = qconfig.themeMode.value
    try:
        yield
    finally:
        setTheme(Theme(original), save=False)


def test_qconfig_is_bound_to_the_main_config():
    """全局 qconfig 必须绑主配置 config.json，不能被图表配置抢走。"""
    from qfluentwidgets.common.config import qconfig
    from miniqt.app.common.config import cfg
    from miniqt.app.common.chart_config import chart_cfg
    assert qconfig._cfg is cfg
    assert qconfig._cfg is not chart_cfg


def test_data_config_never_steals_the_global_qconfig():
    """数据配置也不能抢全局 qconfig。

    ``data_config.json`` 里曾残留 ``QFluentWidgets.ThemeMode="Light"``，而
    ``data_config.py`` 又调 ``qconfig.load(path, data_cfg)`` → 主配置的深色被数据配置
    的浅色覆盖，启动时本应深色却初始化成浅色 ✗。这里锁死：全局 qconfig 仍是主配置，
    数据配置也不再存 QFluentWidgets 组。
    """
    from qfluentwidgets.common.config import qconfig
    from miniqt.app.common.config import cfg
    from miniqt.app.common.data_config import data_cfg
    assert qconfig._cfg is cfg
    assert qconfig._cfg is not data_cfg
    assert 'QFluentWidgets' not in data_cfg.toDict()


def test_settheme_switches_immediately(restore_theme):
    from qfluentwidgets import Theme, isDarkTheme, setTheme
    setTheme(Theme.DARK, save=False)
    assert isDarkTheme()
    setTheme(Theme.LIGHT, save=False)
    assert not isDarkTheme()


def test_chart_config_never_stores_the_theme():
    """图表配置不再写 / 读 QFluentWidgets（主题归主配置）。"""
    from miniqt.app.common.chart_config import chart_cfg
    data = chart_cfg.toDict()
    assert 'QFluentWidgets' not in data
    assert 'Chart' in data                       # 图表自己的配置还在


def test_theme_card_signal_wiring(restore_theme):
    """设置页的接线：cfg.themeMode 改了 → cfg.themeChanged → setTheme。"""
    from qfluentwidgets import Theme, isDarkTheme, setTheme
    from qfluentwidgets.common.config import qconfig
    from miniqt.app.common.config import cfg

    cfg.themeChanged.connect(setTheme)          # 和 setting_interface 里一致
    try:
        qconfig.set(cfg.themeMode, Theme.DARK, save=False)
        assert isDarkTheme()
        qconfig.set(cfg.themeMode, Theme.LIGHT, save=False)
        assert not isDarkTheme()
    finally:
        try:
            cfg.themeChanged.disconnect(setTheme)
        except TypeError:
            pass


def test_mainwindow_apply_theme_sweeps_custom_widgets():
    """apply_theme 会**分拍**遍历子控件调用它们的主题刷新方法（带参 / 无参都行）。"""
    from PyQt6.QtWidgets import QApplication, QWidget
    from miniqt.app.view.main_window import MainWindow

    class Patchy(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def apply_theme(self, dark=None):
            self.calls.append(dark)

    class Booly(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def setTheme(self, is_dark):
            self.calls.append(is_dark)

    class NoArg(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = [0]

        def apply_theme(self):
            self.calls[0] += 1

    class Toggle(QWidget):
        """无参 setTheme（旧回放窗口是 toggle 语义）—— sweep 不该调它 ✗。"""

        def __init__(self):
            super().__init__()
            self.calls = [0]

        def setTheme(self):
            self.calls[0] += 1

    holder = QWidget()
    patchy, booly, no_arg, toggle = Patchy(), Booly(), NoArg(), Toggle()
    for widget in (patchy, booly, no_arg, toggle):
        widget.setParent(holder)
    MainWindow.apply_theme(holder, True)
    # 分拍刷新：把事件循环跑起来直到队列排空（避免一次性卡住 UI ✓）
    app = QApplication.instance()
    for _ in range(30):
        app.processEvents()
        if getattr(holder, '_theme_queue', None) is None:
            break
    assert patchy.calls == [True]
    assert booly.calls == [True]
    assert no_arg.calls == [1]
    assert toggle.calls == [0], '无参 setTheme 是 toggle，不能调用'


def test_home_banner_reloads_on_theme():
    from qfluentwidgets import isDarkTheme
    from miniqt.app.view.home_interface import HomeInterface

    home = HomeInterface()
    home.setTheme(True)
    home.setTheme(False)
    assert home.banner.banner is not None
    assert not home.banner.banner.isNull() or not isDarkTheme()


def test_vscode_theme_follows_the_app(tmp_path, restore_theme):
    """qtvscode 的 workbench.colorTheme 要跟随应用主题（初始 + 在线 ✓）。"""
    import json
    from qfluentwidgets import Theme, setTheme
    from miniqt.app.view.qtvscode_interface import (DARK_COLOR_THEMES,
                                                    LIGHT_COLOR_THEMES,
                                                    apply_vscode_theme,
                                                    preferred_color_theme)

    setTheme(Theme.LIGHT, save=False)
    assert preferred_color_theme() in LIGHT_COLOR_THEMES
    apply_vscode_theme(str(tmp_path))
    path = tmp_path / 'User' / 'settings.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['workbench.colorTheme'] in LIGHT_COLOR_THEMES

    setTheme(Theme.DARK, save=False)
    assert preferred_color_theme() in DARK_COLOR_THEMES
    apply_vscode_theme(str(tmp_path))
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['workbench.colorTheme'] in DARK_COLOR_THEMES


def test_vscode_theme_write_keeps_other_settings(tmp_path, restore_theme):
    """改主题只动 workbench.colorTheme，不能把其它设置抹掉 ✓。"""
    import json
    from miniqt.app.view.qtvscode_interface import (LIGHT_COLOR_THEMES,
                                                    apply_vscode_theme)

    user = tmp_path / 'User'
    user.mkdir(parents=True)
    path = user / 'settings.json'
    path.write_text(json.dumps({'editor.fontSize': 15,
                                'workbench.colorTheme': 'Dark 2026'}),
                    encoding='utf-8')
    apply_vscode_theme(str(tmp_path), dark=False)
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['editor.fontSize'] == 15
    assert data['workbench.colorTheme'] in LIGHT_COLOR_THEMES


def test_apply_vscode_theme_reports_change(tmp_path, restore_theme):
    """``apply_vscode_theme`` 返回是否真的改了主题（调用方据此决定要不要重载 ✓）。"""
    from qfluentwidgets import Theme, setTheme
    from miniqt.app.view.qtvscode_interface import apply_vscode_theme

    setTheme(Theme.LIGHT, save=False)
    assert apply_vscode_theme(str(tmp_path)) is True      # 第一次写
    assert apply_vscode_theme(str(tmp_path)) is False     # 没变
    setTheme(Theme.DARK, save=False)
    assert apply_vscode_theme(str(tmp_path)) is True      # 变了


def test_qtvscode_settings_api(tmp_path):
    """qtvscode 层提供「初始化基本设置 + 运行时改主题」的接口（合并写入 ✓）。"""
    from miniqt.app.view.qtvscode_interface import ensure_qtvscode_importable
    ensure_qtvscode_importable()
    from qtvscode import (font_settings, read_user_settings,
                          resolve_color_theme, update_user_settings)

    # 'dark'/'light'（也认中文）→ 内置主题 id；具体主题名原样透传
    assert resolve_color_theme('dark') == 'Dark 2026'
    assert resolve_color_theme('DARK') == 'Dark 2026'
    assert resolve_color_theme('深色') == 'Dark 2026'
    assert resolve_color_theme('light') == 'Light 2026'
    assert resolve_color_theme('浅色') == 'Light 2026'
    assert resolve_color_theme('qtvscode Dark') == 'qtvscode Dark'
    assert resolve_color_theme(None) is None

    fs = font_settings('Consolas', 14)
    assert fs['editor.fontFamily'] == 'Consolas'
    assert fs['terminal.integrated.fontFamily'] == 'Consolas'
    assert fs['editor.fontSize'] == 14

    update_user_settings(str(tmp_path),
                         {'editor.fontSize': 15,
                          'workbench.activityBar.location': 'hidden'},
                         theme='light')
    data = read_user_settings(str(tmp_path))
    assert data['workbench.colorTheme'] == 'Light 2026'
    # 再切深色：主题变了，其它键保留 ✓
    update_user_settings(str(tmp_path), theme='dark')
    data = read_user_settings(str(tmp_path))
    assert data['workbench.colorTheme'] == 'Dark 2026'
    assert data['editor.fontSize'] == 15
    assert data['workbench.activityBar.location'] == 'hidden'


def test_futures_history_length_setting():
    """新增「期货历史长度」（默认 2000）；选项都必须 >= 数据长度默认值 ✓。"""
    from miniqt.app.common.chart_config import chart_cfg
    assert chart_cfg.DEFAULT_CONFIG['FuturesHistoryLength'] == 2000
    # 用户持久化的 chart_config.json 可能改成别的值（合法），这里只校验默认值 ✓
    assert chart_cfg.futuresHistoryLength.defaultValue == 2000
    options = list(chart_cfg.futuresHistoryLength.validator.options)
    assert 2000 in options and 50000 in options
    assert min(options) >= 1000        # 历史长度 >= 数据长度默认值 ✓


def test_settings_history_card_is_above_the_data_length_card():
    """「期货历史长度」卡片在「期货数据长度」卡片上方（用户要求 ✓）。"""
    import inspect
    from miniqt.app.view import setting_interface as si
    source = inspect.getsource(si)
    assert (source.index('futuresHistoryLengthCard')
            < source.index('futuresDataLengthCard'))


# ---------------------------------------------------------------------------
# 标题栏「主题快捷切换」按钮（最小化按钮左边、无菜单 ✓）
# ---------------------------------------------------------------------------
def _make_title_bar():
    """造一个能成立的 ``CustomTitleBar``（带假 MainWindow，不跑完整 GUI ✓）。"""
    from PyQt6.QtWidgets import QStackedWidget, QWidget
    from miniqt.app.view.main_window import CustomTitleBar

    class _FakeMain(QWidget):
        base_dir = os.getcwd()

        def __init__(self):
            super().__init__()
            self.stackedWidget = QStackedWidget(self)
            self.marketQuotePreviewInterface = None
            self.homeInterface = None

    main = _FakeMain()
    bar = CustomTitleBar(main, 36)
    return main, bar


def test_titlebar_theme_button_source_structure():
    """源码约束：图标按钮、在 buttonLayout 第 0 位（最小化左边）、tooltip、无菜单 ✓。"""
    import inspect
    from miniqt.app.view.main_window import CustomTitleBar
    source = inspect.getsource(CustomTitleBar)
    assert 'FluentTitleBarButton' in source
    assert 'self.buttonLayout.insertWidget(0, self.themeButton)' in source
    assert "setToolTip('深色/浅色主题切换')" in source
    assert 'FluentIcon.BRIGHTNESS' in source        # 深色 → ☀ ✓
    assert 'FluentIcon.QUIET_HOURS' in source       # 浅色 → 🌙 ✓
    # 切换函数里**不能**有菜单（用户要求「没有菜单」✓）
    toggle = inspect.getsource(CustomTitleBar._toggle_theme)
    assert 'Menu' not in toggle and 'menu' not in toggle


def test_titlebar_theme_button_left_of_minimize():
    """主题按钮在标题栏按钮行的**第一位**（最小化按钮左边）✓。"""
    main, bar = _make_title_bar()
    try:
        order = [type(bar.buttonLayout.itemAt(i).widget()).__name__
                 for i in range(bar.buttonLayout.count())]
        assert order[0] == 'FluentTitleBarButton'
        assert order[1:4] == ['MinimizeButton', 'MaximizeButton',
                              'CloseButton']
        assert bar.themeButton.toolTip() == '深色/浅色主题切换'
    finally:
        bar.deleteLater()
        main.deleteLater()


def test_titlebar_theme_toggle_direction(restore_theme, monkeypatch):
    """点一下即可切；「使用系统设置」（AUTO）视作**浅色** → 切深色 ✓。"""
    import miniqt.app.view.main_window as mwmod
    from qfluentwidgets import Theme
    from miniqt.app.common.config import cfg

    calls = []

    def fake_set_theme(theme, save=False, lazy=False):
        calls.append((theme, save))
        cfg.set(cfg.themeMode, theme)           # 只改内存，**不写**配置文件 ✓

    monkeypatch.setattr(mwmod, 'setTheme', fake_set_theme)
    main, bar = _make_title_bar()
    try:
        for start, expect in ((Theme.AUTO, Theme.DARK),
                              (Theme.LIGHT, Theme.DARK),
                              (Theme.DARK, Theme.LIGHT)):
            calls.clear()
            cfg.set(cfg.themeMode, start)
            bar._toggle_theme()
            assert calls == [(expect, True)], f'{start} -> {calls}'
            # 设置页读的也是同一个 cfg.themeMode → 两处互相同步 ✓
            assert cfg.get(cfg.themeMode) == expect
    finally:
        bar.deleteLater()
        main.deleteLater()
