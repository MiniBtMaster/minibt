# coding: utf-8
"""天勤登录改后台 + 服务器维护时的失败/等待处理 ✓。

用户反馈：登录天勤时若服务器维护，``TqApi`` 构造会阻塞主线程（最长 60s）并连续
打印“网络连接断开 / 重新建立”，界面卡住。要求：

* 登录放**后台**（不冻结界面）；
* 收到“网络连接断开 / 登录失败 / 接收数据超时”→ 视为登录失败、**不再重试**，
  提醒稍后再试（已登录时忽略）；
* 后台连接期间，从看盘窗口等入口再触发登录时**不再弹登录窗**，只提醒
  “正在连接，请耐心等待”。

    pytest tests/test_miniqt_login_async.py
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
LOGIN = REPO / 'miniqt' / 'app' / 'login' / 'LoginWindow.py'
MAIN = REPO / 'miniqt' / 'app' / 'view' / 'main_window.py'
WATCH = REPO / 'miniqt' / 'app' / 'windows' / 'market_watch_window.py'

pytestmark = pytest.mark.skipif(
    not LOGIN.exists(), reason='需要仓库里的 miniqt 源码')


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
def test_login_uses_a_background_worker():
    source = _read(LOGIN)
    assert 'class FuturesLoginWorker' in source
    assert 'threading.Thread' in source and 'daemon=True' in source
    assert 'def start_futures_login' not in source    # 在 main_window 里
    # 期货登录分支改为后台 + 关窗
    assert 'start_futures_login' in source
    assert 'self.accept()' in source
    # 旧的“主线程建 TqApi”的 doLogin 不能再有 TqApi 构造
    assert 'def doLogin' not in source


def test_main_window_runs_login_in_the_background():
    source = _read(MAIN)
    assert 'login_pending' in source
    assert 'def is_login_pending' in source
    assert 'def start_futures_login' in source
    assert 'def _on_futures_login_failed' in source
    assert 'def _on_futures_login_success' in source
    # 后台连接期间不弹登录窗
    hook = source.split('def show_login_window', 1)[1]
    hook = hook.split('\n    def ', 1)[0]
    assert 'is_login_pending' in hook
    assert '正在连接天勤' in source
    assert '请稍后再试' in source


def test_market_watch_waits_while_connecting():
    source = _read(WATCH)
    assert "is_login_pending" in source
    assert '正在连接天勤' in source


# ---- 功能：pending 时不弹窗 + 失败后清状态 -------------------------------
def test_pending_blocks_the_dialog_and_failure_clears_it():
    script = (
        "import os, types\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "import PyQt6.QtWebEngineWidgets  # noqa\n"
        "from PyQt6.QtWidgets import QApplication, QWidget\n"
        "app = QApplication([])\n"
        "import miniqt.app.login.LoginWindow as LW\n"
        "from miniqt.app.view.main_window import MainWindow\n"
        "\n"
        "class FakeSignal:\n"
        "    def connect(self, *a, **k):\n"
        "        pass\n"
        "class FakeWorker:\n"
        "    def __init__(self, *a, **k):\n"
        "        self.login_progress = FakeSignal()\n"
        "        self.login_success = FakeSignal()\n"
        "        self.login_failed = FakeSignal()\n"
        "        self.started = False\n"
        "    def start(self):\n"
        "        self.started = True\n"
        "    def request_stop(self):\n"
        "        pass\n"
        "LW.FuturesLoginWorker = FakeWorker\n"
        "\n"
        "class Fake(QWidget):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.login_pending = {}\n"
        "        self.login_status = {}\n"
        "        self.tq_api = None\n"
        "        self.stock_api = None\n"
        "        self.pending_popup = 0\n"
        "        self.titleBar = types.SimpleNamespace(\n"
        "            login=lambda is_stock=False: None)\n"
        "    def _info_login_pending(self, parent=None):\n"
        "        self.pending_popup += 1\n"
        "    def create_tq_api_qtimer(self):\n"
        "        pass\n"
        "    def update_cont_quotes(self):\n"
        "        pass\n"
        "fake = Fake()\n"
        "for name in ('is_login_pending', 'set_login_pending',\n"
        "             'start_futures_login', 'show_login_window',\n"
        "             '_on_futures_login_progress',\n"
        "             '_on_futures_login_soft_timeout',\n"
        "             '_on_futures_login_timeout',\n"
        "             '_on_futures_login_failed', '_on_futures_login_success'):\n"
        "    setattr(fake, name,\n"
        "            types.MethodType(getattr(MainWindow, name), fake))\n"
        "print('START', fake.start_futures_login('u', 'p'))\n"
        "print('PENDING', fake.is_login_pending('futures'))\n"
        "print('SHOW_BLOCKED', fake.show_login_window())\n"
        "print('POPUP', fake.pending_popup >= 1)\n"
        "# 服务器维护：接收数据超时 → 视为失败、清 pending、不再连接\n"
        "fake._on_futures_login_failed(\n"
        "    '接收数据超时，请检查客户端及网络是否正常')\n"
        "print('AFTER_FAIL_PENDING', fake.is_login_pending('futures'))\n"
        "print('AFTER_FAIL_STATUS', fake.login_status.get('futures'))\n"
        "print('AFTER_FAIL_API', fake.tq_api)\n"
    )
    out = _run(script).stdout
    assert 'START True' in out
    assert 'PENDING True' in out
    assert 'SHOW_BLOCKED False' in out          # 不再弹登录窗 ✓
    assert 'POPUP True' in out                  # 弹“正在连接”提醒 ✓
    assert 'AFTER_FAIL_PENDING False' in out    # 失败后不再 pending ✓
    assert 'AFTER_FAIL_STATUS False' in out
    assert 'AFTER_FAIL_API None' in out
