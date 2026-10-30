# coding: utf-8
"""共享 VS Code 编辑器 + 退出清理的测试 ✓。

看盘 / 回测的代码编辑器原来各起一套 Node server，抢同一个 user-data-dir /
token 文件 → 后开的静默打不开；退出时还会留下孤儿 node.exe。这里锁住修复：

* ``QtvscodePage`` 只借入**进程内共享**的编辑器（不再自己 new 一套）；
* ``SharedVscodeEditor.acquire/release`` 谁在用就 reparent 给谁，其余放回停车位；
* 退出时 ``main_window`` 统一回收共享实例；``QtVscodeServer.stop`` 杀整棵进程树。
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
PAGE = REPO / 'miniqt' / 'app' / 'windows' / 'qtvscode_page.py'
MAIN = REPO / 'miniqt' / 'app' / 'view' / 'main_window.py'
SHARED = REPO / 'miniqt' / 'app' / 'common' / 'qtvscode_shared.py'
SERVER = REPO / 'qtvscode' / 'qtvscode' / 'server.py'

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


# ---- 源码约束 -----------------------------------------------------------
def test_code_page_reuses_the_shared_editor():
    """同目录模式（默认）下 ``QtvscodePage`` 借入共享实例，不自建 ✓。

    ★ 关闭「同目录编辑器」时会走 ``_start_own_editor``（各页自建）——
    所以 ``QtvscodeBridge(`` / ``QtVscodeWidget(`` 仍在源码里（只在 OFF 分支）✓。
    """
    source = _read(PAGE)
    assert 'shared_editor()' in source
    assert 'shared.acquire(' in source
    assert 'def _start_shared_editor' in source
    assert 'def _start_own_editor' in source
    # 隐藏 / 关闭只是归还（ON 模式）
    assert 'def _release_editor' in source
    assert 'shared.release(self)' in source


def test_shared_module_is_the_single_instance():
    source = _read(SHARED)
    assert 'class SharedVscodeEditor' in source
    assert 'def acquire(' in source and 'def release(' in source
    assert 'def stop(' in source and 'def restart(' in source
    assert '_SHARED' in source
    assert 'DOCK_SETTINGS' in source


def test_main_window_stops_the_shared_editor():
    source = _read(MAIN)
    assert 'shared_editor().stop()' in source


def test_server_kills_the_whole_process_tree():
    """Windows 的 terminate 不杀子进程 → stop 要 taskkill /T 整棵树 ✓。"""
    source = _read(SERVER)
    assert 'def kill_process_tree(' in source
    assert 'taskkill' in source and '/T' in source
    assert 'kill_process_tree(pid)' in source


# ---- 功能：借用 / 归还 --------------------------------------------------
def test_shared_editor_acquire_and_release_reparents():
    """两个宿主轮流借用：编辑器 reparent 给当前宿主，归还后回停车位 ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout)\n"
        "app = QApplication([])\n"
        "from miniqt.app.common.qtvscode_shared import shared_editor\n"
        "s = shared_editor()\n"
        "from PyQt6.QtWidgets import QLabel\n"
        "fake = QLabel('editor')          # 代替真正的 QtVscodeWidget\n"
        "fake.view = None\n"
        "s._widget = fake\n"
        "s._workspace = 'WS'\n"
        "s._ready = True\n"
        "parking = QWidget(); lp = QVBoxLayout(parking)\n"
        "print('PARKING', parking is not None)\n"
        "s._parking = parking\n"
        "a = QWidget(); la = QVBoxLayout(a)\n"
        "b = QWidget(); lb = QVBoxLayout(b)\n"
        "s.acquire(a, la, workspace='WS')\n"
        "print('OWNER_A', s.owner is a, fake.parent() is a)\n"
        "s.acquire(b, lb, workspace='WS')\n"
        "print('OWNER_B', s.owner is b, fake.parent() is b)\n"
        "s.release(a)                     # 不是持有者 → 无操作\n"
        "print('AFTER_STALE_RELEASE', s.owner is b)\n"
        "s.release(b)\n"
        "print('RELEASED', s.owner is None, fake.parent() is not b)\n"
    )
    out = _run(script).stdout
    assert 'OWNER_A True True' in out
    assert 'OWNER_B True True' in out
    assert 'AFTER_STALE_RELEASE True' in out
    assert 'RELEASED True True' in out


def test_kill_process_tree_is_safe_for_bad_pid():
    """``kill_process_tree`` 对空 / 非法 PID 不能抛异常（退出路径 ✓）。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from miniqt.app.view.qtvscode_interface import ("
        "ensure_qtvscode_importable)\n"
        "ensure_qtvscode_importable()\n"
        "from qtvscode.server import kill_process_tree\n"
        "kill_process_tree(0)\n"
        "kill_process_tree(-1)\n"
        "print('OK')\n"
    )
    out = _run(script).stdout
    assert 'OK' in out


def test_code_page_uses_injected_shared_editor():
    """``QtvscodePage.ensure_started`` 走共享实例；归还时只释放、不停 server ✓。"""
    script = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QLabel, QWidget\n"
        "app = QApplication([])\n"
        "import miniqt.app.windows.qtvscode_page as qp\n"
        "\n"
        "import tempfile as _tf, os as _os\n"
        "qp.STATE_FILE = _os.path.join(_tf.gettempdir(),\n"
        "                              'miniqt_test_state.json')\n"
        "if _os.path.isfile(qp.STATE_FILE): _os.remove(qp.STATE_FILE)\n"
        "\n"
        "class FakeSignal:\n"
        "    def connect(self, *a, **k):\n"
        "        pass\n"
        "\n"
        "class FakeBridge:\n"
        "    has_client = False\n"
        "    def request(self, *a, **k):\n"
        "        pass\n"
        "    def stop(self):\n"
        "        self.stopped = True\n"
        "\n"
        "class FakeShared:\n"
        "    def __init__(self):\n"
        "        self.ready = FakeSignal()\n"
        "        self.failed = FakeSignal()\n"
        "        self.bridge = FakeBridge()\n"
        "        self.owner = None\n"
        "        self.is_ready = True\n"
        "        self.failure = ''\n"
        "        self.stopped = False\n"
        "        self.workspace = 'WS'\n"
        "        self.widget = QLabel('editor')\n"
        "        self.widget.view = None\n"
        "    def acquire(self, host, layout, **k):\n"
        "        self.owner = host\n"
        "        self.acquire_ws = k.get('workspace')\n"
        "        layout.addWidget(self.widget, 1)\n"
        "        return self.widget\n"
        "    def release(self, host):\n"
        "        if self.owner is host:\n"
        "            self.owner = None\n"
        "    def stop(self):\n"
        "        self.stopped = True\n"
        "    def restart(self, ws=''):\n"
        "        pass\n"
        "\n"
        "fake = FakeShared()\n"
        "qp.shared_editor = lambda: fake\n"
        "page = qp.QtvscodePage(mode='edit')\n"
        "page.ensure_started()\n"
        "print('USES_SHARED', page._editor is fake.widget)\n"
        "print('OWNER', fake.owner is page)\n"
        "page._release_editor()\n"
        "print('RELEASED', page._editor is None, fake.owner is None)\n"
        "print('NOT_STOPPED', fake.stopped is False)\n"
        "# 共享 server 已存在时工作区以它为准（别的页可能刚换过目录）\n"
        "fake.workspace = 'NEW_DIR'\n"
        "fake.widget = QLabel('editor2')\n"
        "fake.widget.view = None\n"
        "page2 = qp.QtvscodePage(mode='edit', workspace='/stale')\n"
        "print('STALE_BEFORE', page2.workspace != 'NEW_DIR')\n"
        "page2.ensure_started()\n"
        "print('SYNCED', page2.workspace == 'NEW_DIR')\n"
        "print('ACQUIRE_WS_EMPTY', fake.acquire_ws == '')\n"
    )
    out = _run(script).stdout
    assert 'USES_SHARED True' in out
    assert 'OWNER True' in out
    assert 'RELEASED True True' in out
    assert 'NOT_STOPPED True' in out
    assert 'STALE_BEFORE True' in out     # 构造时是旧工作区 ✓
    assert 'SYNCED True' in out           # 借入后跟随共享 server，不翻回旧值 ✓
    assert 'ACQUIRE_WS_EMPTY True' in out  # 不把旧工作区传进去触发重启 ✓


@pytest.mark.skipif(sys.platform != 'win32', reason='taskkill 验证仅 Windows')
def test_kill_process_tree_kills_grandchildren():
    """杀「主进程」要连带子进程（VS Code server 会派生 extension host）✓。"""
    script = (
        "import subprocess, sys, time\n"
        "from qtvscode.qtvscode.server import kill_process_tree\n"
        "code = ('import subprocess, sys, time\\n'\n"
        "        'p = subprocess.Popen([sys.executable, \"-c\",'\n"
        "        ' \"import time; time.sleep(120)\"])\\n'\n"
        "        'print(p.pid, flush=True)\\n'\n"
        "        'time.sleep(120)\\n')\n"
        "parent = subprocess.Popen([sys.executable, '-c', code],\n"
        "    stdout=subprocess.PIPE, text=True,\n"
        "    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))\n"
        "try:\n"
        "    child = int(parent.stdout.readline().strip())\n"
        "    time.sleep(1)\n"
        "    kill_process_tree(parent.pid)\n"
        "    time.sleep(2)\n"
        "    listed = subprocess.run(['tasklist', '/FI', f'PID eq {child}',\n"
        "        '/FO', 'CSV'], capture_output=True, text=True).stdout\n"
        "    print('CHILD_GONE', str(child) not in listed)\n"
        "    print('PARENT_GONE', parent.poll() is not None)\n"
        "finally:\n"
        "    try:\n"
        "        parent.kill()\n"
        "    except Exception:\n"
        "        pass\n"
    )
    out = _run(script).stdout
    assert 'CHILD_GONE True' in out
    assert 'PARENT_GONE True' in out
