# coding: utf-8
"""desk 编辑器里的 Python REPL（v1.3.7）。

* 一个**常驻子进程**跑 `python -u -c <BOOTSTRAP>`，启动时自动 `import minibt`；
* 交互走 JSON 行（stdin）→ 输出原样从 stdout 拿回（**保留 traceback**）；
* 语义对齐标准 REPL：最后一行是表达式就打印它的值（`x = 1; x * 2` → `2`）✓；
* desk 只负责转发：`repl_eval {code}` → `{type:'repl_result', output}`；
* 卡死保护：单条命令 20 秒没回 → 杀掉重启并提示 ✓。
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional

#: 单条命令超时（秒）
TIMEOUT = 20.0

#: 输出最多回多少字符（超长截断，避免 patch 爆掉 ✓）
MAX_OUTPUT = 20000

#: 子进程里跑的 REPL 循环（`exec` 保持命名空间 + 打印最后一个表达式 ✓）
BOOTSTRAP = r'''
import ast, json, sys, traceback
import minibt
from minibt import *
# ★ `from minibt import *` 只写进本文件的 globals，而下面 `exec` 用的是
#   `namespace` —— 以前没搬过去，所以 REPL 里 `LocalDatas` 之类全是
#   NameError（用户 2026-11-08 实测 ✗）。这里逐个搬一遍 ✓
namespace = {'__name__': '__repl__', 'minibt': minibt, 'minibt_all': True}
for _name in dir(minibt):
    if _name.startswith('_'):
        continue
    try:
        namespace[_name] = getattr(minibt, _name)
    except Exception:
        pass
try:
    import numpy as _np
    import pandas as _pd
    namespace.setdefault('np', _np)
    namespace.setdefault('pd', _pd)
except Exception:
    pass
del _name
print('@@banner@@ minibt REPL 已就绪（from minibt import * 已生效，'
      + str(len([k for k in namespace if not k.startswith('_')]))
      + ' 个名字可用）')
print('@@ready@@')
sys.stdout.flush()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        payload = json.loads(line)
    except Exception:
        continue
    code = payload.get('code') or ''
    if not code:
        sys.stdout.write('@@done@@\n'); sys.stdout.flush(); continue
    try:
        tree = ast.parse(code, '<repl>', 'exec')
    except SyntaxError:
        sys.stdout.write(traceback.format_exc(limit=1))
        sys.stdout.write('@@done@@\n'); sys.stdout.flush(); continue
    try:
        value = None
        body = list(tree.body)
        last_expression = bool(body) and isinstance(body[-1], ast.Expr)
        if last_expression:
            head = ast.Module(body=body[:-1], type_ignores=[])
            exec(compile(head, '<repl>', 'exec'), namespace)
            expr = ast.Expression(body[-1].value)
            value = eval(compile(expr, '<repl>', 'eval'), namespace)
        else:
            exec(compile(tree, '<repl>', 'exec'), namespace)
        if value is not None:
            sys.stdout.write(repr(value) + '\n')
    except SystemExit:
        break
    except Exception:
        text = traceback.format_exc()
        kept, skip = [], False
        for row in text.splitlines(True):
            if row.lstrip().startswith('File "<string>"'):
                skip = True
                continue
            if skip and row.startswith("    "):
                skip = False
                continue
            skip = False
            kept.append(row)
        sys.stdout.write(''.join(kept))
    sys.stdout.write('@@done@@\n')
    sys.stdout.flush()
'''


class ReplSession:
    """常驻 REPL 子进程（懒启动 + 超时自动重启 ✓）"""

    def __init__(self, cwd: str = '') -> None:
        self.cwd = str(cwd or '')
        self.proc: Optional[subprocess.Popen] = None
        self.queue: 'queue.Queue[str]' = queue.Queue()
        #: 子进程是否已经就绪（`@@ready@@`；就绪横幅不混进命令输出 ✓）
        self.ready = False
        self.banner = ''

    @staticmethod
    def _package_root() -> str:
        """minibt 包所在目录（安装版 / 源码版都适用 ✓）"""
        return os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))

    # ------------------------------------------------------------ 生命周期
    def _start(self) -> None:
        env = dict(os.environ)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUNBUFFERED'] = '1'
        # ★ cwd 可能是任意目录 → 让子进程一定 import 得到 minibt ✓
        env['PYTHONPATH'] = os.pathsep.join(
            [item for item in (self._package_root(),
                               env.get('PYTHONPATH', '')) if item])
        self.proc = subprocess.Popen(
            [sys.executable, '-u', '-c', BOOTSTRAP],
            cwd=self.cwd or None, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding='utf-8',
            errors='replace', bufsize=1)
        self.queue = queue.Queue()
        self.ready = False
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        proc = self.proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            self.queue.put(line)
        self.queue.put('@@eof@@')

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def restart(self) -> None:
        self.stop()
        self._start()

    def stop(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:                                        # noqa: BLE001
            try:
                proc.kill()
            except Exception:                                # noqa: BLE001
                pass

    # ------------------------------------------------------------ 执行
    def run(self, code: str, timeout: float = TIMEOUT) -> Dict[str, Any]:
        """执行一段代码，返回 ``{'ok': bool, 'output': str}`` ✓"""
        text = str(code or '').strip()
        if not text:
            return {'ok': True, 'output': ''}
        if not self.alive():
            try:
                self._start()
            except Exception as error:                           # noqa: BLE001
                return {'ok': False, 'output': f'REPL 启动失败：{error!r}'}
        proc = self.proc
        assert proc is not None and proc.stdin is not None
        try:
            proc.stdin.write(json.dumps({'code': text}, ensure_ascii=False)
                             + '\n')
            proc.stdin.flush()
        except Exception as error:                               # noqa: BLE001
            self.stop()
            return {'ok': False, 'output': f'REPL 写入失败：{error!r}'}
        deadline = time.time() + float(timeout)
        rows: list = []
        while time.time() < deadline:
            try:
                line = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue
            # ★ 启动横幅只留一份（`self.banner`），不混进命令输出 ✓
            if line.startswith('@@banner@@'):
                self.banner = line[len('@@banner@@'):].strip()
                continue
            if line.startswith('@@ready@@'):
                self.ready = True
                continue
            if line in ('@@done@@\n', '@@done@@'):
                return {'ok': True, 'output': ''.join(rows)[:MAX_OUTPUT]}
            if line == '@@eof@@':
                break
            rows.append(line)
            if len(''.join(rows)) > MAX_OUTPUT:
                break
        # 超时 / 进程挂了 → 杀掉重启（下次还能用 ✓）
        self.stop()
        head = ''.join(rows)[:MAX_OUTPUT]
        extra = '（超时，REPL 已重启）' if not rows else '（REPL 已重启）'
        return {'ok': False, 'output': (head + '\n' + extra).strip()}
