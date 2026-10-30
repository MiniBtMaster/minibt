"""策略**实盘 / 模拟盘常驻运行**（方案 C ✓）

desk 原来的「加到图表」只是*图上回放*（`strategy_runner.replay`）——
策略逻辑会跑、但**委托不会真的发出去**。这里补一个常驻运行器：

* 后台线程里跑 `Bt(live=True)`（minibt 自带的实盘循环：tick → 新 K 线 →
  `next()` → 下单），账号沿用 desk 已登录的**天勤账号**（快期模拟 / 实盘都行）；
* 策略的 `print` / 日志会转进 desk 的运行日志（`[策略实盘] …`）；
* 可以随时 `stop()`（置停止标志 + `bt.close()`）。

用法（Python）::

    desk.start_strategy_live(r'~/.minibt/personal/strategies/ma_reverse_test.py')
    desk.stop_strategy_live()

前端/CLI 对应命令：``strategy_live_start`` / ``strategy_live_stop``。
"""
from __future__ import annotations

import os
import subprocess
import sys as _sys
import threading
import time
from typing import Any, Dict, Optional


def _real_account(login: dict):
    """实盘账户（`TqAccount`）；信息不全返回 None（= 模拟盘）✓"""
    broker = str(login.get('broker') or '')
    account = str(login.get('account') or '')
    password = str(login.get('password') or '')
    if not (broker and account and password):
        return None
    try:
        from tqsdk import TqAccount
        return TqAccount(broker, account, password)
    except Exception:                                            # noqa: BLE001
        return None


#: 策略实盘的"单实例锁"（多个 desk 进程同时跑 → 会重复下单 ✗）
LOCK_FILE = os.path.join(os.path.expanduser('~'), '.minibt',
                         'strategy_live.lock')


def _lock_owner() -> int:
    """锁文件里的 pid（0 = 没有锁 / 读不到）"""
    try:
        with open(LOCK_FILE, encoding='utf-8') as handle:
            return int((handle.read() or '0').strip() or 0)
    except (OSError, ValueError):
        return 0


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import psutil                                   # 可选依赖
        return psutil.pid_exists(pid)
    except Exception:                                    # noqa: BLE001
        pass
    try:
        if os.name == 'nt':
            import subprocess
            out = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'],
                                 capture_output=True, text=True, timeout=5)
            return str(pid) in (out.stdout or '')
        os.kill(pid, 0)
        return True
    except Exception:                                    # noqa: BLE001
        return False


class StrategyLive:
    """一个策略文件的实盘线程（**可以同时跑多个**：每个文件一个 ✓）

    每个实例 = 一个子进程（`live_runner`），互不影响；父进程用
    ``desk._strategy_lives``（`file -> StrategyLive`）统一管理。
    """

    def __init__(self, desk, file: str,
                 params: Optional[Dict[str, Any]] = None,
                 config: Optional[Dict[str, Any]] = None):
        self.desk = desk
        # ★ 统一成「绝对路径 + 正斜杠」：`_strategy_lives` 的 key、控制文件、
        #   子进程命令行用的都是同一个写法（Windows 上别混反斜杠 ✓）
        try:
            from . import live_control as _control
            self.file = _control.normalize(file) or str(file or '')
        except Exception:                                    # noqa: BLE001
            self.file = str(file or '')
        self.params = dict(params or {})
        #: 运行开关（策略管理弹窗里可改；子进程读同一个控制文件 ✓）
        self.next_on_new_bar = True
        self.run_next = True
        for key in ('next_on_new_bar', 'run_next'):
            if isinstance(config, dict) and key in config:
                setattr(self, key, bool(config[key]))
        #: 状态变化回调（父进程推 `strategy_live` 补丁用 ✓）
        self.on_change = None
        self.thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        self.error = ''
        self.started_at = 0.0
        self._bt = None
        #: 子进程句柄（`stop()` 直接 terminate ✓）
        self._proc = None
        #: 崩了是否自动重启（默认**不重启**，更安全 ✓）
        self.retry = False
        #: 已自动重启次数（上限 `MAX_RETRIES`）
        self.restarts = 0
        #: 账号（从 desk 记住的登录信息里取）
        self.user = ''
        self.password = ''
        self.real = False
        #: 账户页当前选中的账户（快期模拟 / 实盘）
        self.account_index = 0
        self.account_label = ''
        self.account_real = False
        self.broker = ''
        self.account = ''
        self.trade_password = ''
        #: 已**真正执行**的 `next` 次数（策略实盘日志里能看到 ✓）
        self._bars = 0
        #: `next` 被**调用**的次数（含被门控挡掉的，用于排查 ✓）
        self._calls = 0

    # ------------------------------------------------------------ 状态
    @property
    def running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def status(self) -> Dict[str, Any]:
        proc = self._proc
        return {
            'file': self.file,
            'name': os.path.splitext(os.path.basename(self.file))[0],
            'running': self.running,
            'pid': int(getattr(proc, 'pid', 0) or 0),
            'next_on_new_bar': bool(self.next_on_new_bar),
            'run_next': bool(self.run_next),
            'retry': bool(self.retry),
            'restarts': int(self.restarts),
            'error': self.error,
            'account': self.account_label,
            'account_real': bool(self.account_real),
            'seconds': round(time.monotonic() - self.started_at, 1)
            if self.started_at else 0,
        }

    # ------------------------------------------------------------ 开/关
    def start(self) -> Dict[str, Any]:
        if self.running:
            return self.status()
        if not self.file or not os.path.isfile(self.file):
            self.error = f'策略文件不存在：{self.file}'
            return self.status()
        # ★ 全局交易开关：allow_trading=False / 未接交易接口时不允许启动
        if not bool(getattr(self.desk, 'trading', True)):
            self.error = '当前禁止交易（allow_trading=False / 未接交易接口）'
            self._log(self.error, 'warning')
            return self.status()
        # ★ 只允许**一个进程**跑策略实盘：否则关掉窗口但进程还在 →
        #   多个实例同时下单（用户实测"关了还在下单"✗）
        owner = _lock_owner()
        if owner and owner != os.getpid() and _pid_alive(owner):
            self.error = (f'已有 desk 进程（PID {owner}）在跑策略实盘 → '
                          '先停止它（或结束该进程）再启动')
            self._log(self.error, 'error')
            return self.status()
        # 账号：从 desk 记住的登录信息取（子进程通过 env 拿到 ✓）
        try:
            from . import user_prefs as _prefs
            login = dict(_prefs.login().get('futures') or {})
        except Exception:                                    # noqa: BLE001
            login = {}
        login.update(dict(getattr(self.desk, '_login_futures', {}) or {}))
        self.user = str(login.get('username') or login.get('user')
                        or login.get('account') or '')
        self.password = str(login.get('password') or '')
        # ★ 环境变量兜底（无界面的 headless / CI 用法 ✓）
        if not self.user:
            self.user = str(os.environ.get('MINIBT_TQ_USER') or '')
        if not self.password:
            self.password = os.environ.get('MINIBT_TQ_PASSWORD') or ''
        self.broker = str(login.get('broker') or '')
        self.account = str(login.get('account') or '')
        self.trade_password = str(login.get('trade_password') or '')
        # ★ 快期模拟（TqKq）**同样**需要快期账号 auth（tqsdk 的硬要求：
        #   `TqApi` 没有 auth 直接抛「请输入 auth（快期账户）参数」）——
        #   所以没登录就先说清楚，不用等子进程崩一次 ✓
        if not (self.user and self.password):
            self.error = ('缺少天勤（快期）账号 / 密码：先在 desk「登录」里登录'
                          '快期账号（快期模拟 TqKq 也需要 auth，不是只有实盘才要）')
            self._log(self.error, 'warning')
            return self.status()
        # ★ 账户页当前选择：模拟 / 实盘（不再固定看 prefs.real）
        try:
            view = self.desk.account_view()
            labels = view.labels()
            self.account_index = int(view.index)
            self.account_label = labels[self.account_index] if labels else ''
            current = view.current()
            self.account_real = bool(
                str(getattr(current, 'broker_id', '') or ''))
        except Exception:                                    # noqa: BLE001
            self.account_index = 0
            self.account_label = ''
            self.account_real = bool(login.get('real'))
        self.real = bool(self.account_real)
        try:
            os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
            with open(LOCK_FILE, 'w', encoding='utf-8') as handle:
                handle.write(str(os.getpid()))
        except OSError:
            pass
        # ★ 运行开关 → 控制文件（子进程每个 tick 读一次 ✓）
        try:
            from . import live_control
            live_control.write(self.file, {
                'next_on_new_bar': self.next_on_new_bar,
                'run_next': self.run_next,
            })
        except Exception:                                    # noqa: BLE001
            pass
        self.stop_flag.clear()
        self.error = ''
        self.started_at = time.monotonic()
        self.thread = threading.Thread(target=self._run, daemon=True,
                                       name='desk-strategy-live')
        self.thread.start()
        return self.status()

    def stop(self) -> Dict[str, Any]:
        self.stop_flag.set()          # 先置标志：不再接收日志 / 不再推进 ✓
        self._kill()                  # ★ 结束子进程（进程级，一定停得掉 ✓）
        if self.thread is not None:
            self.thread.join(timeout=3.0)
        self.thread = None
        self._bt = None
        self._release_lock()
        self._log(f'已停止（不再下单 ✓）｜next 调用 {self._calls} 次、'
                  f'实际执行 {self._bars} 次')
        return self.status()

    def _release_lock(self) -> None:
        """释放单实例锁（只删自己的锁，避免误删别的 desk 进程 ✓）

        ★ 同一个 desk 里可以同时跑**多个**策略实盘 → 还有别的在跑就不能删，
        否则第二个 desk 进程会以为没人在跑（重复下单 ✗）。
        """
        others = [item for item in
                  (getattr(self.desk, '_strategy_lives', {}) or {}).values()
                  if item is not self and getattr(item, 'running', False)]
        if others:
            return
        if _lock_owner() != os.getpid():
            return
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass

    # ------------------------------------------------------------ 子进程体
    def _log(self, text: str, level: str = 'info') -> None:
        try:
            self.desk.push_log(f'[策略实盘] {text}', level)
        except Exception:                                        # noqa: BLE001
            print(f'[策略实盘] {text}', flush=True)

    def _run(self) -> None:
        """起一个**子进程**跑 `Bt(live=True)`（P206 ✓）

        线程里跑 `Bt.run(live=True)` 会把解释器卡住（tqsdk asyncio + 全局锁）
        → 主线程被挡、停不下来、关了界面还在下单 ✗
        子进程版：停止 = `terminate()`（进程级，一定停得掉），日志逐行回传 ✓
        """
        try:
            while not self.stop_flag.is_set():
                self._run_once()
                if self.stop_flag.is_set() or not self.retry:
                    break
                if self.restarts >= self.MAX_RETRIES:
                    self._log(f'已自动重启 {self.restarts} 次，停止重试',
                              'warning')
                    break
                self.restarts += 1
                self._log(f'子进程异常退出 → {self.RETRY_DELAY:.0f} 秒后第 '
                          f'{self.restarts}/{self.MAX_RETRIES} 次自动重启',
                          'warning')
                for _ in range(int(self.RETRY_DELAY * 10)):
                    if self.stop_flag.is_set():
                        return
                    time.sleep(0.1)
        finally:
            # ★ 子进程自然退出 / 重启上限到 / 启动失败 → 锁都要清掉，
            #   否则下一次启动会被残留的 PID 锁挡住 ✓
            self._release_lock()
            # ★ 通知父进程刷「策略管理 / 停止实盘」状态（以前只在启动时推
            #   一次 → 子进程崩了界面还显示"运行中" ✗）
            try:
                if callable(self.on_change):
                    self.on_change()
            except Exception:                                # noqa: BLE001
                pass

    #: 自动重启上限 / 间隔（`retry=True` 时才用 ✓）
    MAX_RETRIES = 3
    RETRY_DELAY = 3.0

    def _run_once(self) -> None:
        """起一次子进程（崩了由 `_run` 决定是否重启 ✓）"""
        self._log(f'启动：{os.path.basename(self.file)}'
                  f'（天勤{"实盘" if self.real else "快期模拟"}'
                  f'{" · " + self.account_label if self.account_label else ""}）')
        env = dict(os.environ)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUNBUFFERED'] = '1'
        env['MINIBT_TQ_USER'] = self.user
        env['MINIBT_TQ_PASSWORD'] = self.password
        # ★ 子进程固定构造 [TqKq, TqAccount]；UI 的 account_index 可能来自
        #   另一套列表（Python API 只建了一个实盘账户 → index=0），
        #   直接把 UI 下标传过去会把实盘策略跑到快期模拟 ✗
        child_index = 1 if self.real else 0
        env['MINIBT_TQ_ACCOUNT_INDEX'] = str(child_index)
        env['MINIBT_TQ_BROKER'] = self.broker
        env['MINIBT_TQ_ACCOUNT'] = self.account
        env['MINIBT_TQ_TRADE_PASSWORD'] = self.trade_password
        cmd = [_sys.executable, '-u', '-m', 'minibt.desk.live_runner',
               '--file', self.file, '--account-index', str(child_index)]
        if self.real:
            cmd.append('--real')
        try:
            self._proc = subprocess.Popen(
                cmd, cwd=os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__)))) or None,
                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', bufsize=1,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception as error:                               # noqa: BLE001
            self.error = f'启动子进程失败：{type(error).__name__}: {error}'
            self._log(self.error, 'error')
            return
        self._log(f'子进程 PID {self._proc.pid} 已启动')
        try:
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                text = (line or '').rstrip()
                if not text:
                    continue
                if self.stop_flag.is_set():
                    break
                self._log(text)
            self._proc.wait(timeout=5)
        except Exception as error:                               # noqa: BLE001
            self.error = f'{type(error).__name__}: {error}'
        finally:
            code = None
            try:
                code = self._proc.poll() if self._proc else None
            except Exception:                                    # noqa: BLE001
                code = None
            self._kill()
            if self.stop_flag.is_set():
                self._log('子进程已结束（不再下单 ✓）')
            else:
                self._log(f'子进程退出（code={code}）', 'warning')

    def _kill(self) -> None:
        """结束子进程（进程级，一定停得掉 ✓）"""
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except Exception:                                # noqa: BLE001
                    proc.kill()
        except Exception:                                        # noqa: BLE001
            pass
        self._proc = None

    @staticmethod
    def _safe_close(bt) -> None:
        try:
            bt.close()
        except Exception:                                    # noqa: BLE001
            pass
