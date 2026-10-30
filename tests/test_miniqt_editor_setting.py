# coding: utf-8
"""编辑器设置：同目录模式开关 + 两种模式（共享 / 独立）✓。

用户要求：
* 设置页新增「编辑器设置」，一个「同目录编辑器」开关（默认开）；
* 开 = 所有代码编辑器共用一个目录 / 看盘+回测共用一个编辑器进程（省内存）；
* 关 = 每个编辑器各自独立目录 / 进程（多目录-多开销）；
* 改后**重启程序**才生效，选择时弹提醒。

    pytest tests/test_miniqt_editor_setting.py
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
CONFIG = REPO / 'miniqt' / 'app' / 'common' / 'config.py'
SETTING = REPO / 'miniqt' / 'app' / 'view' / 'setting_interface.py'
PAGE = REPO / 'miniqt' / 'app' / 'windows' / 'qtvscode_page.py'
NAV = REPO / 'miniqt' / 'app' / 'view' / 'qtvscode_interface.py'

pytestmark = pytest.mark.skipif(
    not CONFIG.exists(), reason='需要仓库里的 miniqt 源码')


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


# ---- 配置 / 设置页 ------------------------------------------------------
def test_config_has_same_dir_default_true_and_snapshot():
    source = _read(CONFIG)
    assert 'editorSameDir = ConfigItem("Editor", "SameDir", True' in source
    assert 'EDITOR_SAME_DIR_AT_STARTUP' in source
    assert 'def editor_same_dir(' in source


def test_setting_page_has_editor_interface_and_restart_hint():
    source = _read(SETTING)
    assert 'class EditorSettingInterface' in source
    assert 'cfg.editorSameDir' in source
    assert 'addSubInterface(self.editorSettingInterface' in source
    # 副标题带上「多目录多开销」；详细影响说明段落已按用户要求删除 ✓
    assert '关闭则各自独立目录（多目录多开销）' in source
    assert 'explainLabel' not in source
    # 重启提醒
    assert '重启' in source
    assert 'valueChanged.connect(self.__onSameDirChanged)' in source


def test_setting_page_has_flavor_and_manual_download():
    """编辑器后端下拉 + 手动下载环境的兵底入口。"""
    source = _read(SETTING)
    assert 'cfg.editorFlavor' in source
    assert '编辑器后端' in source
    assert "'手动下载编辑器环境'" in source
    assert 'self.downloadCard.clicked.connect(self.__onDownloadEditor)' in source
    assert 'ensure_server_with_dialog' in source
    # 先检测，只补缺失；已就绪不重复下载
    assert 'find_server_dir' in source
    assert '无需下载' in source
    assert 'missing' in source
    # 手动下载不能 force 重下（否则会反复覆盖已就绪的产物 ✗）
    assert 'ensure_server_with_dialog(flavor=target, url=url, parent=self)' in source
    # 「下载」前有「帮助」按钮 + 步骤说明（含网络失败排查）
    assert '_DownloadSettingCard' in source
    assert 'helpClicked' in source
    assert '__onDownloadHelp' in source
    assert '_EnvironmentHelpDialog' in source
    assert 'QTVSCODE_VSCODIUM_SERVER_DIR' in source
    assert 'WinError 10060' in source
    # 提醒用户：连接 VPN / 代理后可正常下载
    assert 'VPN' in source
    assert '连接 VPN / 代理后通常就可以正常下载' in source


def test_current_flavor_reads_the_config_value(monkeypatch):
    """★ 回归：`QConfig.get(item)` 返回的就是值，不能再取 `.value`。

    以前写成 `cfg.get(cfg.editorFlavor).value` → 对字符串取 `.value` 抛
    `AttributeError`，被 except 吞掉后永远回退 `vscode` —— 明明选了 VSCodium
    却启动 VS Code（用户反馈 ✗）。
    """
    from miniqt.app.view import qtvscode_interface as qi
    from miniqt.app.common import config as config_mod

    class _FakeCfg:
        editorFlavor = object()          # 只是个哨兵，get() 忽略它

        def __init__(self, value):
            self.value = value

        def get(self, item):
            return self.value

    monkeypatch.setattr(qi, '_active_flavor', None)
    monkeypatch.setattr(config_mod, 'cfg', _FakeCfg('vscodium'))
    assert qi.current_flavor() == 'vscodium'

    monkeypatch.setattr(qi, '_active_flavor', None)
    monkeypatch.setattr(config_mod, 'cfg', _FakeCfg('vscode'))
    assert qi.current_flavor() == 'vscode'


def test_backend_indicator_is_visible():
    """迷你 qt 界面要能一眼看出用的是 qtvscode 还是 VSCodium。"""
    nav = _read(NAV)
    assert 'def flavor_label(' in nav
    assert 'self.backendLabel' in nav
    page = _read(PAGE)
    assert 'self.backendBadge' in page
    assert '_refresh_backend_badge' in page
    # 徽标要显示**实际启动的** server 后端（配置与实际不一致时能看出来 ✓）
    assert 'server_flavor' in page
    assert 'server_flavor' in nav
    # VSCodium 初始化时隐藏右侧「辅助栏」（与 VS Code 一致 ✓）
    assert '_apply_initial_ui' in page
    assert 'close_auxiliary_bar' in page
    assert '_apply_initial_ui' in nav


def test_flavor_label_reports_backend():
    script = (
        "from miniqt.app.view.qtvscode_interface import flavor_label\n"
        "print('VSCODE', flavor_label('vscode'))\n"
        "print('CODIUM', flavor_label('vscodium'))\n"
    )
    out = _run(script).stdout
    assert 'VSCODE VS Code' in out
    assert 'CODIUM VSCodium' in out


# ---- 两种模式的源码约束 -------------------------------------------------
def test_dock_editor_shows_the_status_bar():
    """看盘 / 回测的代码编辑器：底部状态栏要显示（与 VS Code 一致 ✓）。"""
    shared = _read(REPO / 'miniqt' / 'app' / 'common' / 'qtvscode_shared.py')
    assert "'workbench.statusBar.visible': True" in shared
    page = _read(PAGE)
    assert '_status_shown' in page
    assert 'workbench.action.toggleStatusbarVisibility' in page


def test_miniqt_prefers_the_cwd_minibt():
    """miniqt 启动时优先用当前目录（含上级）的 minibt，没有才用仓库/系统的 ✓。"""
    src = _read(REPO / 'miniqt' / '__main__.py')
    assert '_prepend_cwd_minibt' in src
    assert "'minibt', '__init__.py'" in src


def test_titlebar_shift_keeps_editor_and_sidebar_aligned():
    """顶栏用「innerHeight+35 + workbench 上移」隐藏，不再直接改 split-view 高度 ✓。"""
    src = _read(PAGE)
    assert '__miniqtTitlebarShift' in src
    assert "margin-top" in src
    # 旧写法会把编辑器和侧栏的内层布局拆成两套 → 底部错位/空白 ✓
    assert "height','100%'" not in src
    assert '_chrome_keeper' not in src


def test_qtvscode_page_implements_both_modes():
    source = _read(PAGE)
    assert 'def _same_dir_mode(' in source
    assert 'def _own_user_data_dir(' in source
    assert 'def _start_shared_editor(' in source
    assert 'def _start_own_editor(' in source
    assert 'def _teardown_own_editor(' in source
    # OFF 模式：每页独立 user-data-dir（否则多台 server 抢目录 ✗）
    assert "'qtvscode_pages'" in source
    # 独立编辑器真的被创建 + serverReady 连接
    assert 'QtVscodeWidget(' in source
    assert 'editor.serverReady.connect(self._on_ready)' in source


def test_nav_follows_the_shared_directory():
    source = _read(NAV)
    assert 'def shared_dock_workspace(' in source
    assert 'editor_same_dir()' in source


# ---- 功能：默认开启 = 共享 ---------------------------------------------
def test_default_mode_uses_the_shared_editor():
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "import miniqt.app.windows.qtvscode_page as qp\n"
        "print('MODE', qp._same_dir_mode())\n"
        "d1 = qp._own_user_data_dir()\n"
        "d2 = qp._own_user_data_dir()\n"
        "print('UNIQUE_DIRS', d1 != d2)\n"
    )
    out = _run(script).stdout
    assert 'MODE True' in out                 # 默认同目录（共享）✓
    assert 'UNIQUE_DIRS True' in out          # OFF 模式的独立目录各不相同 ✓


# ---- 功能：关闭 = 每页自建编辑器 ---------------------------------------
def test_ensure_started_dispatches_by_mode():
    """开关开 → 用共享编辑器；关 → 走独立编辑器（``_start_own_editor``）✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "import miniqt.app.common.config as config\n"
        "config.EDITOR_SAME_DIR_AT_STARTUP = False   # 模拟“关闭后重启”\n"
        "import miniqt.app.windows.qtvscode_page as qp\n"
        "calls = []\n"
        "# 要 patch **类方法**（ensure_started 走 self.xxx，不是模块全局 ✗）\n"
        "qp.QtvscodePage._start_shared_editor = (\n"
        "    lambda self: calls.append('shared'))\n"
        "qp.QtvscodePage._start_own_editor = (\n"
        "    lambda self: calls.append('own'))\n"
        "page = qp.QtvscodePage(mode='edit')\n"
        "page.ensure_started()\n"
        "print('MODE', qp._same_dir_mode())\n"
        "print('CALLS', calls)\n"
        "config.EDITOR_SAME_DIR_AT_STARTUP = True\n"
        "calls2 = []\n"
        "qp.QtvscodePage._start_own_editor = (\n"
        "    lambda self: calls2.append('own'))\n"
        "qp.QtvscodePage._start_shared_editor = (\n"
        "    lambda self: calls2.append('shared'))\n"
        "page2 = qp.QtvscodePage(mode='edit')\n"
        "page2.ensure_started()\n"
        "print('CALLS2', calls2)\n"
        "# 独立编辑器关闭时必须真正拆掉（不依赖 _bridge 已存在）\n"
        "page2._editor = None\n"
        "page2._teardown_own_editor()\n"
        "print('TEARDOWN_OK', page2._editor is None)\n"
    )
    out = _run(script).stdout
    assert 'MODE False' in out
    assert "CALLS ['own']" in out
    assert "CALLS2 ['shared']" in out
    assert 'TEARDOWN_OK True' in out


def test_quick_input_follows_the_hidden_titlebar_offset():
    """隐藏顶栏后 Ctrl+P 的 quick input 要补一个标题栏高度，否则输入框被裁 ✓。"""
    page = _read(PAGE)
    assert '.quick-input-widget' in page
    assert '--miniqt-titlebar-shift' in page
    assert ("document.documentElement.style.setProperty("
            "'--miniqt-titlebar-shift'") in page
