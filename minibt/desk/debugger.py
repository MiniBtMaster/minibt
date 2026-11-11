# coding: utf-8
"""desk 断点调试（v1.3.7）：`sys.settrace` + 子进程 + JSON 行协议。

设计要点（尽量简单、不侵入用户代码）：

* 调试 = **独立子进程**跑用户脚本（`python -u -m minibt.desk.debug_worker`），
  desk 进程只负责收发 JSON 行 —— 用户脚本崩了、卡了都不影响看盘 ✓；
* worker 里用 `sys.settrace` 在**用户文件**的行上停：命中断点行 → 暂停，
  把 `stack` / `locals` 发给 desk，然后阻塞等命令；
* 命令：`continue` / `next` / `step` / `out` / `eval` / `stop`；
* 所有交互都是 `json.dumps(...) + '\\n'` 一行一条（stdout 专用，用户
  `print` 会被重定向到 stderr → desk 当普通日志显示 ✓）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional

#: 单次命令的超时（秒）：worker 卡死也不把 desk 拖住 ✓
COMMAND_TIMEOUT = 30.0

def package_root() -> str:
    """minibt **包**所在目录（`…/pylightcharts`）；安装版也能算出来 ✓"""
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


#: `locals` 里最多给多少个变量 / 每个值截多长（避免 patch 太大 ✓）
MAX_LOCALS = 40
MAX_VALUE = 200


def _safe_repr(value: Any, limit: int = MAX_VALUE) -> str:
    try:
        text = repr(value)
    except Exception:                                            # noqa: BLE001
        text = f'<{type(value).__name__}>'
    return text[:limit]


def snapshot(frame) -> Dict[str, Any]:
    """把一帧变成可 JSON 的结构（栈 + 变量 ✓）"""
    stack: List[Dict[str, Any]] = []
    node = frame
    while node is not None and len(stack) < 12:
        stack.append({
            'name': str(getattr(node.f_code, 'co_name', '?')),
            'path': str(getattr(node.f_code, 'co_filename', '') or ''),
            'line': int(getattr(node, 'f_lineno', 0) or 0) - 1,
        })
        node = node.f_back
    values: Dict[str, str] = {}
    for name, value in list((frame.f_locals or {}).items())[:MAX_LOCALS]:
        if str(name).startswith('__'):
            continue
        values[str(name)] = _safe_repr(value)
    return {'stack': stack, 'locals': values}


class DebugWorker:
    """`minibt.desk.debug_worker`：真正跑用户脚本、按断点暂停 ✓"""

    def __init__(self, path: str, breakpoints: Optional[List[int]] = None,
                 cwd: str = '') -> None:
        self.path = os.path.abspath(str(path or ''))
        # ⚠ 前端（gutter）给的是 **0 基**行号，`frame.f_lineno` 是 **1 基**
        #   → 这里统一 +1，比较时直接用 f_lineno ✓
        self.lines = {int(line) + 1 for line in (breakpoints or [])}
        self.cwd = os.path.abspath(str(cwd or os.path.dirname(self.path) or '.'))

    # ------------------------------------------------------------ 协议
    def send(self, payload: Dict[str, Any]) -> None:
        sys.__stdout__.write(json.dumps(payload, ensure_ascii=False) + '\n')
        sys.__stdout__.flush()

    def wait(self) -> Dict[str, Any]:
        line = sys.stdin.readline()
        if not line:
            return {'action': 'stop'}
        try:
            data = json.loads(line)
        except ValueError:
            return {'action': 'continue'}
        return data if isinstance(data, dict) else {'action': 'continue'}

    # ------------------------------------------------------------ 主流程
    def run(self) -> int:
        import runpy

        state: Dict[str, Any] = {'mode': 'continue', 'depth': 0}

        def tracer(frame, event, arg):                            # noqa: ANN001
            if frame.f_code.co_filename != self.path:
                return tracer
            if event == 'call':
                return tracer
            if event != 'line':
                return tracer
            number = int(frame.f_lineno)
            mode = state['mode']
            hit = number in self.lines
            if mode == 'next' and int(frame.f_lineno) != state.get('line'):
                # 「单步」= 同一个 frame 的下一行
                if frame is state.get('frame'):
                    hit = True
            elif mode in ('step',):
                hit = True
            elif mode == 'out':
                if frame is not state.get('frame'):
                    hit = True
            state['mode'] = 'continue'
            if not hit:
                state['line'] = number
                state.setdefault('frame', frame)
                return tracer
            state['line'] = number
            state['frame'] = frame
            self.send({'event': 'break', 'line': number - 1,
                       'path': frame.f_code.co_filename, **snapshot(frame)})
            command = self.wait()
            action = str(command.get('action') or 'continue')
            if action == 'stop':
                raise SystemExit(0)
            if action in ('next', 'step', 'out'):
                state['mode'] = action
            if action == 'eval':
                try:
                    value = eval(str(command.get('arg') or 'None'),          # noqa: S307
                                 frame.f_globals, frame.f_locals)
                    self.send({'event': 'eval', 'value': _safe_repr(value)})
                except Exception as error:                       # noqa: BLE001
                    self.send({'event': 'eval', 'value': '',
                               'error': f'{type(error).__name__}: {error}'})
            return tracer

        self.send({'event': 'started', 'path': self.path})
        sys.settrace(tracer)
        try:
            runpy.run_path(self.path, run_name='__main__')
        except SystemExit:
            pass
        except Exception as error:                               # noqa: BLE001
            import traceback

            self.send({'event': 'error',
                       'error': f'{type(error).__name__}: {error}',
                       'traceback': traceback.format_exc()[-2000:]})
            return 1
        finally:
            sys.settrace(None)
        self.send({'event': 'finished'})
        return 0


def main(argv: Optional[List[str]] = None) -> int:
    """`python -u -m minibt.desk.debug_worker <path> [lines...]`"""
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print('usage: python -m minibt.desk.debug_worker <script.py> '
              '[line ...]', file=sys.stderr)
        return 2
    path = args[0]
    lines: List[int] = []
    for raw in args[1:]:
        for part in str(raw).split(','):
            part = part.strip()
            if part.isdigit():
                lines.append(int(part))
    # ⚠ 用户脚本的 `print` 走 stderr：stdout 只留给协议 ✓
    sys.stdout = sys.stderr
    return DebugWorker(path, lines).run()


class DebugSession:
    """desk 侧的调试会话（子进程 + 收发线程 ✓）"""

    def __init__(self, desk, path: str, breakpoints: Optional[List[int]] = None,
                 cwd: str = '') -> None:
        self.desk = desk
        self.path = os.path.abspath(str(path or ''))
        self.breakpoints = [int(line) for line in (breakpoints or [])]
        self.cwd = cwd or os.path.dirname(self.path)
        self.proc: Optional[subprocess.Popen] = None
        self.alive = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------ 生命周期
    def start(self) -> None:
        env = dict(os.environ)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUNBUFFERED'] = '1'
        # ★ 子进程 cwd 是**用户脚本目录** → 必须把 minibt 所在的目录塞进
        #   PYTHONPATH，否则 `-m minibt.desk.debug_worker` 直接找不到包 ✗
        env['PYTHONPATH'] = os.pathsep.join(
            [item for item in (package_root(),
                               env.get('PYTHONPATH', '')) if item])
        cmd = [sys.executable, '-u', '-m', 'minibt.desk.debug_worker',
               self.path, *[str(line) for line in self.breakpoints]]
        self.proc = subprocess.Popen(
            cmd, cwd=self.cwd or None, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8',
            errors='replace', bufsize=1)
        self.alive = True
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self._paused = False
        self._push({'status': 'running', 'path': self.path, 'line': -1,
                    'output': f'$ 调试启动：{os.path.basename(self.path)}'
                              f'（断点 {len(self.breakpoints)} 个）'})

    def _read_stdout(self) -> None:
        proc = self.proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            line = (line or '').strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if not isinstance(data, dict):
                continue
            event = str(data.get('event') or '')
            if event == 'break':
                self._paused = True
                self._push({'status': 'paused', 'path': data.get('path')
                            or self.path, 'line': data.get('line'),
                            'stack': data.get('stack') or [],
                            'locals': data.get('locals') or {}})
            elif event == 'eval':
                self._push({'status': 'eval',
                            'value': data.get('value') or '',
                            'error': data.get('error') or '',
                            'line': -1})
            elif event in ('finished', 'error'):
                self._paused = False
                payload = {'status': 'finished' if event == 'finished'
                           else 'error', 'line': -1,
                           'error': data.get('error') or '',
                           'traceback': data.get('traceback') or ''}
                self._push(payload)
                self.alive = False
        self.alive = False

    def _read_stderr(self) -> None:
        proc = self.proc
        if proc is None or proc.stderr is None:
            return
        for line in proc.stderr:
            text = (line or '').rstrip()
            if not text:
                continue
            try:
                self.desk.push_log(f'[调试] {text}', 'info')
            except Exception:                                    # noqa: BLE001
                pass
            # ★ 用户脚本的 print / traceback 也要出现在调试面板里 ✓
            self.log(text)

    def _push(self, payload: Dict[str, Any]) -> None:
        try:
            self.desk.push({'type': 'debug_state', **payload})
        except Exception:                                        # noqa: BLE001
            pass

    def log(self, text: str) -> None:
        """往 dock 的「输出」区写一行（用户脚本的 print 也走这里 ✓）"""
        self._push({'status': self.status(), 'line': -1,
                    'output': str(text or '')})

    def status(self) -> str:
        return 'paused' if getattr(self, '_paused', False) else (
            'running' if self.alive else 'idle')

    # ------------------------------------------------------------ 命令
    def command(self, action: str, arg: Any = None) -> None:
        if not self.alive or self.proc is None or self.proc.stdin is None:
            self._push({'status': 'idle', 'line': -1})
            return
        payload = {'action': str(action or 'continue')}
        if arg is not None:
            payload['arg'] = arg
        with self._lock:
            try:
                self.proc.stdin.write(json.dumps(payload, ensure_ascii=False)
                                      + '\n')
                self.proc.stdin.flush()
            except Exception as error:                            # noqa: BLE001
                self._push({'status': 'error', 'line': -1,
                            'error': f'发送命令失败：{error!r}'})

    def stop(self) -> None:
        self.alive = False
        proc = self.proc
        self.proc = None
        if proc is None:
            return
        try:
            if proc.stdin is not None:
                proc.stdin.write('{"action": "stop"}\n')
                proc.stdin.flush()
        except Exception:                                        # noqa: BLE001
            pass
        try:
            proc.terminate()
        except Exception:                                        # noqa: BLE001
            pass
        try:
            proc.wait(timeout=3)
        except Exception:                                        # noqa: BLE001
            try:
                proc.kill()
            except Exception:                                    # noqa: BLE001
                pass
        self._push({'status': 'stopped', 'line': -1})
