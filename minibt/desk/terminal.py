# coding: utf-8
"""desk 编辑器里的**终端**（v1.3.7-2）：跑 shell 命令、流式输出。

为什么是「命令 + 流式输出」而不是完整 PTY：

* 不加新依赖（Windows 上没有随包发布的 `pywinpty`）；
* 对量化日常够用：`pip install`、`python -m pytest`、`git status`、
  以及**启动 AI CLI**（`pi` / `claude` / `codex` / `ollama run …`）——
  这些都能靠「stdout 流 + stdin 行」交互 ✓；
* 需要真正全屏 TUI 的场景，用户直接用系统终端（`terminal_open` 支持
  `open: true` 用系统终端打开同一目录 ✓）。

协议（全部 JSON 行 → desk 补丁）：

| 命令 | 作用 |
| --- | --- |
| `terminal_open` | 起子进程（默认 cwd = 资源管理器根目录） |
| `terminal_input` | 往 stdin 写一行（回车由前端补） |
| `terminal_signal` | `ctrl-c`（Windows 用 `CTRL_BREAK_EVENT`）/ `stop` |
| `terminal_restart` | 杀掉重开 |
| `terminal_clear` | 只清前端输出 |
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional

from .agent import decode_bytes

#: 单个子进程最多缓存多少行输出（防止内存涨；前端也会截断 ✓）
MAX_LINES = 4000


def default_shell() -> List[str]:
    """当前系统的 shell 命令（`/bin/bash -lc` 或 `cmd.exe /Q /K` ✓）"""
    if os.name == 'nt':
        comspec = os.environ.get('COMSPEC') or 'cmd.exe'
        return [comspec, '/Q', '/K']
    shell = os.environ.get('SHELL') or '/bin/bash'
    return [shell, '-l']


class TerminalSession:
    """一个常驻 shell 子进程（流式输出 + 行输入 ✓）"""

    def __init__(self, desk, cwd: str = '', shell: str = '',
                 env: Optional[Dict[str, str]] = None) -> None:
        self.desk = desk
        self.cwd = os.path.abspath(str(cwd or os.getcwd()))
        self.shell = str(shell or '')
        self.extra_env = dict(env or {})
        self.proc: Optional[subprocess.Popen] = None
        self.lines: List[str] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------ 生命周期
    def start(self) -> None:
        env = dict(os.environ)
        env.update(self.extra_env)
        env.setdefault('PYTHONIOENCODING', 'utf-8')
        env.setdefault('PYTHONUNBUFFERED', '1')
        cmd = shlex.split(self.shell) if self.shell else default_shell()
        creation = 0
        if os.name == 'nt':
            # 独立进程组 → 以后能发 `CTRL_BREAK_EVENT` 当 Ctrl+C 用 ✓
            creation = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=self.cwd or None, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                errors='replace', bufsize=1, creationflags=creation)
        except Exception as error:                               # noqa: BLE001
            self._push(f'⚠ 终端启动失败：{error!r}')
            return
        self._push(f'$ cd {self.cwd}')
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        proc = self.proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            self._push(line.rstrip('\n'))
        self._push(f'（终端已退出，退出码 '
                   f'{proc.poll() if proc.poll() is not None else "?"}）')

    def _push(self, text: str) -> None:
        text = str(text or '')
        with self._lock:
            self.lines.append(text)
            if len(self.lines) > MAX_LINES:
                self.lines = self.lines[-MAX_LINES:]
        try:
            self.desk.push({'type': 'terminal_output', 'text': text})
        except Exception:                                        # noqa: BLE001
            pass

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    # ------------------------------------------------------------ 交互
    def write(self, text: str) -> None:
        """写一行（命令 / 交互输入 ✓）；末尾自动补换行"""
        if not self.alive() or self.proc is None or self.proc.stdin is None:
            return
        line = str(text or '')
        # 回显（shell 自己不一定回显，尤其是 Windows）
        self._push(f'> {line}')
        try:
            self.proc.stdin.write(line + '\n')
            self.proc.stdin.flush()
        except Exception as error:                               # noqa: BLE001
            self._push(f'⚠ 写入失败：{error!r}')

    def signal(self, kind: str = 'ctrl-c') -> None:
        """`ctrl-c`：尽量发中断；`stop`：直接结束进程 ✓"""
        proc = self.proc
        if proc is None:
            return
        if str(kind) == 'stop' or not self.alive():
            self.stop()
            return
        if os.name == 'nt':
            try:
                proc.send_signal(
                    getattr(__import__('signal'), 'CTRL_BREAK_EVENT'))
                self._push('（已发送 Ctrl+Break）')
                return
            except Exception:                                    # noqa: BLE001
                pass
        try:
            proc.terminate()
            self._push('（已结束当前命令）')
        except Exception:                                        # noqa: BLE001
            pass

    def restart(self) -> None:
        self.stop(quiet=True)
        self.start()

    def stop(self, quiet: bool = False) -> None:
        proc = self.proc
        self.proc = None
        if proc is None:
            return
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except Exception:                                        # noqa: BLE001
            pass
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:                                        # noqa: BLE001
            try:
                proc.kill()
            except Exception:                                # noqa: BLE001
                pass
        if not quiet:
            self._push('（终端已关闭）')


def open_system_terminal(cwd: str, shell: str = '') -> Dict[str, Any]:
    """用**系统终端**打开目录（需要真 TUI 时的兜底 ✓）"""
    cwd = os.path.abspath(str(cwd or os.getcwd()))
    try:
        if os.name == 'nt':
            subprocess.Popen(['cmd', '/c', 'start', '', 'cmd', '/K'],
                             cwd=cwd, shell=False)
        else:
            subprocess.Popen([shell or os.environ.get('SHELL', 'bash')],
                             cwd=cwd)
    except Exception as error:                                   # noqa: BLE001
        return {'ok': False, 'error': f'{error!r}'}
    return {'ok': True, 'cwd': cwd}


def python_env() -> Dict[str, str]:
    """子进程默认环境：确保能 `import minibt`（编辑器的目录可能不在 path）✓"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    current = os.environ.get('PYTHONPATH', '')
    return {'PYTHONPATH': os.pathsep.join(
        [item for item in (root, current) if item])}


__all__ = ['TerminalSession', 'default_shell', 'open_system_terminal',
           'python_env', 'MAX_LINES']

if __name__ == '__main__':                                       # pragma: no cover
    print('terminal module', sys.version.split()[0])
