"""``Gui.Desk``：把 minibt 的**指标 / 策略 / 回测 / 参数优化 / 实时交易**
交给 minibt desk 界面完成。

对应关系（用户 2026-10-26 的要求 ✓）：

===============  ==================================================
minibt 入口      desk 里发生的事
===============  ==================================================
``btplot`` /     **本地图表** → 把 K 线写成 CSV → 打开图表 →
``BtIndicator``  「加到图表」（指标线 / 信号直接用算好的数据 ✓）
``Bt().run()``   本地图表 →「加到图表」把策略挂上去；随后可用
                 「策略回测 / 参数优化」按钮跑（`strategy_lab` ✓）
``Bt(live=True)`` 天勤账号登录 → **实时图表**「加到图表」= 真下单；
                 多个策略 = 多个图表页（`open_chart` 每个合约一个 tab ✓）
===============  ==================================================

用法::

    from minibt import Bt, Gui
    Bt(strategy=MyStrategy).run(gui=Gui.Desk)            # 本地图表 + 策略
    Bt(strategy=MyStrategy).run(gui=Gui.Desk, mode='optimize')
    Bt(strategy=MyStrategy, live=True, account=...).run(gui=Gui.Desk)
    my_indicator.btplot(gui=Gui.Desk)                    # 本地图表 + 指标

所有函数都是「**先把 desk 准备好，再 `desk.run()`**」——`run()` 之后
Qt 事件循环会接管，`queue_ui()` 排的动作由 `Desk.tick()` 依次执行 ✓。

Jupyter
-------
真正的 notebook 里（``ZMQInteractiveShell``）自动改用**浏览器壳 + iframe**：
Qt 事件循环不能在 kernel 线程里跑，而 ``web.serve()`` 放在 daemon 线程里、
``display(IFrame(url))`` 内嵌，**不阻塞 kernel**（和 ``Gui.PylightchartsWeb``
在 notebook 里的做法一致 ✓）。
"""
from __future__ import annotations

import os
import re
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: 生成文件放这里（`Bt(strategy=类对象)` 没有源文件时用 ✓）
GENERATED_DIR = os.path.join(os.path.expanduser('~'), '.minibt', 'desk',
                             'generated')

#: 带 `step`（交易逻辑）的指标最多回放多少根（止损线历史 ✓）
DESK_REPLAY_BARS = 2000

#: 本地图表 CSV 的默认目录（desk 本来就扫这个目录 ✓）
def datas_dir() -> str:
    try:
        from ..data.tools import user_datas_dir
        return user_datas_dir()
    except Exception:                                            # noqa: BLE001
        path = os.path.join(os.path.expanduser('~'), '.minibt', 'datas')
        os.makedirs(path, exist_ok=True)
        return path


# --------------------------------------------------------------- 建 desk
def new_desk(*, browser: bool = False, theme: str = 'dark',
             title: str = 'minibt桌面端', size=(1500, 900),
             port: int = 0, offline: bool = False) -> Any:
    """建一个（还没启动的）``Desk`` ✓"""
    from .app import Desk
    return Desk(title=title, theme=theme, size=size, browser=browser,
                port=port, offline=offline)


# --------------------------------------------------------------- Jupyter
#: Jupyter 里启动过的 desk（保住引用；kernel 退出时统一 close ✓）
_JUPYTER_DESKS: List[Any] = []
_JUPYTER_ATEXIT = [False]


def in_notebook() -> bool:
    """是否**真的**在 Jupyter / IPython kernel 里（普通脚本 → ``False``）。

    不能只看 "能不能 import IPython"：普通脚本里 ``display(IFrame(...))``
    不会报错，只会打印一个 ``<IPython.lib.display.IFrame object at …>``
    —— 既没有嵌图，也没有开浏览器 ✗。

    这里**不**复用 ``strategy.strategy_window._in_notebook``：那会连带导入
    bokeh / pylightcharts，在启动早期（包还没导完）容易撞上循环导入，一旦
    抛异常就只能当成“不在 notebook 里”→ 误走 Qt 路径把 kernel 卡死 ✗。
    """
    try:
        from IPython import get_ipython
        shell = get_ipython()
    except Exception:                                            # noqa: BLE001
        return False
    return (shell is not None
            and shell.__class__.__name__ == 'ZMQInteractiveShell')


def _close_jupyter_desks() -> None:
    """kernel 退出时关闭 notebook 里启动的 desk（停天勤 / futu、落盘模拟账户 ✓）"""
    for desk in list(_JUPYTER_DESKS):
        try:
            desk.close()
        except Exception:                                        # noqa: BLE001
            pass
    _JUPYTER_DESKS.clear()


def show_in_notebook(desk, *, height: int = 860,
                     timeout: float = 30.0) -> str:
    """在 Notebook 单元格里**内嵌** desk（不阻塞 kernel ✓），返回 URL。

    做法（与 ``Gui.PylightchartsWeb`` 的 Jupyter 分支同一条思路）：

    1. 强制走**浏览器壳** —— Qt 的 ``application.exec()`` 不能在 kernel 线程里跑；
    2. ``web.serve()`` 放后台 daemon 线程，``keep_alive=True``（iframe 重绘 /
       单元格滚动造成的短暂断线不能把服务停掉 ✗）；
    3. 等 ``desk.url`` 就绪 → ``display(IFrame(url, width='100%'))``
       （高度默认 860，可用 ``MINIBT_DESK_JUPYTER_HEIGHT`` 覆盖）；
    4. kernel 退出时 ``atexit`` 统一 ``desk.close()``。

    注意：Jupyter 如果跑在 **https** 上，浏览器会拦掉 ``http://127.0.0.1`` 的
    iframe（mixed content）；这时用打印出来的地址单开一个浏览器标签即可 ✓。
    """
    import atexit

    if not _JUPYTER_ATEXIT[0]:
        _JUPYTER_ATEXIT[0] = True
        atexit.register(_close_jupyter_desks)

    desk.browser = True          # Qt 窗口 / 事件循环在 notebook 里不可用 ✓
    desk.open_browser = False    # 只在 iframe 里显示，别弹系统浏览器 ✓
    # ★ 节拍线程持续往单元格 stdout 写日志，会在 IPython 收尾时把 kernel 卡住 ✗
    #   → notebook 里日志只进 desk 的「运行日志」页（想调试可手动改回 False）
    desk._notebook_quiet = True
    failures: List[BaseException] = []

    def _serve() -> None:
        from .web import serve
        try:
            serve(desk, open_browser=False, keep_alive=True)
        except BaseException as error:                           # noqa: BLE001
            failures.append(error)

    threading.Thread(target=_serve, daemon=True,
                     name='desk-jupyter').start()

    deadline = time.monotonic() + max(1.0, float(timeout))
    url = ''
    while time.monotonic() < deadline:
        url = str(getattr(desk, 'url', '') or '')
        if url or failures:
            break
        time.sleep(0.05)
    if not url:
        detail = failures[0] if failures else TimeoutError(
            f'{float(timeout):.0f}s 内没起来')
        raise RuntimeError(f'desk 浏览器壳启动失败：{detail!r}') from detail

    # iframe 高度：默认 860，可用环境变量调（`MINIBT_DESK_JUPYTER_HEIGHT=1000`）
    try:
        height = int(os.environ.get('MINIBT_DESK_JUPYTER_HEIGHT') or height)
    except (TypeError, ValueError):
        pass

    _JUPYTER_DESKS.append(desk)
    print(f'[desk] Jupyter 内嵌：{url}'
          '（单元格里没显示时，把这个地址贴到浏览器 ✓）')
    try:
        from IPython.display import IFrame, display
        display(IFrame(url, width='100%', height=int(height)))
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] iframe 显示失败（直接用上面的地址）：{error!r}')
    # ★ 必须**在 display 之后**再写一行 stdout：
    #   notebook 单元格如果以 display_data 结尾，IPython 收尾时偶尔会卡住
    #   （nbclient 一直等不到 execute_reply ✗）；随后再发一条 stream 就正常 ✓
    print('[desk] 已内嵌；日志看 desk 的「运行日志」页（不刷单元格 ✓）',
          flush=True)
    return url


def run_desk(desk, *, browser: bool = False) -> None:
    """启动 desk。

    * 普通脚本：阻塞到用户关窗（Qt 窗口 / ``browser=True`` 的浏览器壳 ✓）；
    * **Jupyter**：改用浏览器壳 + iframe 内嵌，**立即返回**、不阻塞 kernel ✓
      （``browser`` 参数在 notebook 里无意义 —— 一定是浏览器壳）。
    """
    if in_notebook():
        show_in_notebook(desk)
        return
    try:
        desk.browser = bool(browser or getattr(desk, 'browser', False))
        desk.run()
    finally:
        try:
            desk.close()
        except Exception:                                        # noqa: BLE001
            pass


# --------------------------------------------------------------- 本地数据
def save_frame(frame, name: str, *, path: str = '') -> str:
    """DataFrame → ``~/.minibt/datas/<name>.csv``（desk 本地图表能直接列出来 ✓）"""
    name = str(name or '').strip()
    if not name:
        raise ValueError('save_frame 需要名字')
    target = path or os.path.join(datas_dir(), f'{name}.csv')
    os.makedirs(os.path.dirname(target), exist_ok=True)
    frame.to_csv(target, index=False)
    return target


def frame_of_kline(kline) -> Tuple[Any, str]:
    """minibt ``KLine`` → ``(DataFrame, 名字)``（名字 = `symbol_duration` ✓）"""
    import pandas as pd
    columns: Dict[str, Any] = {}
    for key in ('datetime', 'open', 'high', 'low', 'close', 'volume'):
        value = getattr(kline, key, None)
        if value is None:
            continue
        try:
            columns[key] = list(value)
        except TypeError:
            continue
    if not columns:
        raise ValueError('KLine 没有可用的 OHLC 数据')
    frame = pd.DataFrame(columns)
    symbol = str(getattr(kline, 'symbol', '') or 'kline')
    duration = int(getattr(kline, 'duration', 0) or 0)
    if duration <= 0 and len(frame) > 1:
        try:
            diff = frame['datetime'].diff().dropna()
            duration = max(1, int(round(diff.median() / 1_000_000_000)))
        except Exception:                                        # noqa: BLE001
            duration = 60
    frame['symbol'] = symbol
    frame['duration'] = int(duration or 60)
    name = f'{symbol}_{int(duration or 60)}'
    return frame, name


def ensure_local_data(frame, name: str) -> str:
    """把 K 线写成 CSV（同名覆盖）→ 返回名字 ✓"""
    save_frame(frame, name)
    return name


# --------------------------------------------------------------- 指标
def items_from_strategy_class(cls, frame, symbol: str = '', cycle: int = 60,
                              *, replay: bool = False,
                              replay_bars: int = 0) -> List[dict]:
    """策略/指标壳 → desk 指标线（`strategy_overlay` 同一条路径 ✓）

    `btplot` / `BtIndicator` 都是「K 线 + 指标」的组合，用
    ``btplot._make_step_strategy()`` 造一个临时策略壳就能直接复用 desk 的
    转换（颜色 / 虚线 / 主副图 / 买卖信号 / 止损线全部保留 ✓）。
    """
    from . import strategy_overlay as _overlay
    try:
        result = _overlay.run_overlay(
            frame, cls, str(symbol or ''), int(cycle or 60),
            replay=bool(replay), replay_bars=int(replay_bars or 0))
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] 指标转换成图表线失败：{error!r}')
        return []
    if not result.get('ok'):
        print(f'[desk] 指标运行失败：{result.get("error")}')
        return []
    return list(result.get('items') or [])


def show_indicator_items(items, name: str, *, cell: int = 0,
                         desk=None, browser: bool = False) -> Any:
    """把**算好的**指标线画到 desk 本地图表（btplot 用 ✓）"""
    desk = desk or new_desk(browser=browser)
    desk.set_local_plot_items(name, items, cell)
    desk.queue_ui('open_local_chart', name=name, cell=cell)
    # 页面刚建时再加载一次（`_local_indicator_payload` 会把预计算线一起带上）；
    # 最后再推一次，防止浏览器 / Qt 首屏比队列慢一拍导致补丁丢掉 ✓
    desk.queue_ui('local_load', name=name, cell=cell)
    desk.queue_ui('push_plot_items', name=name, cell=cell)
    return desk


# --------------------------------------------------------------- 策略
def _cell_source(target: Any) -> str:
    """Notebook 里取**整个单元格**源码（策略依赖同格的指标类才带得上 ✓）。

    ``inspect.getsource(cls)`` 只返回这一个类 —— 而 notebook 里常见
    ``class DeskMa(BtIndicator)`` + ``class MyStrategy(Strategy)`` 写在同一格，
    只拷策略类会 ``NameError: DeskMa is not defined`` ✗。
    """
    name = str(getattr(target, '__name__', '') or '')
    if not name:
        return ''
    try:
        from IPython import get_ipython
        shell = get_ipython()
    except Exception:                                            # noqa: BLE001
        return ''
    if shell is None:
        return ''
    cells = getattr(shell, 'user_ns', {}).get('In') or []
    pattern = re.compile(r'^[ \t]*class[ \t]+' + re.escape(name) + r'\b',
                         re.MULTILINE)
    for cell in reversed([str(item) for item in cells if item]):
        if pattern.search(cell):
            return cell
    return ''


def _cell_missing_names(cell: str) -> List[str]:
    """单元格里**用到但本格没定义**的顶层名字（供 notebook 补常量 ✓）。

    ``from minibt import *`` / ``np`` / ``pd`` / 内置名字 / 本格内定义的名字
    都算“已有”；剩下的才是从**其它单元格**拿的（例如 ``SYMBOL = 'SHFE.ag2612'``）。
    """
    import ast
    import builtins
    try:
        tree = ast.parse(cell)
    except SyntaxError:
        return []
    defined = set(dir(builtins)) | {'np', 'pd', '__name__', 'self'}
    try:
        import minibt as _minibt
        names = getattr(_minibt, '__all__', None) or dir(_minibt)
        defined |= {str(item) for item in names}
    except Exception:                                            # noqa: BLE001
        pass
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == '*':
                    continue
                defined.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
    used = {node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    return sorted(name for name in used - defined
                  if not name.startswith('_'))


def _cell_constants(cell: str) -> List[str]:
    """把单元格用到的**其它格常量**写成 ``NAME = …`` 行（能 repr 回字面量才行）。

    Notebook 里常见 ``SYMBOL = 'SHFE.ag2612'`` 写在上面一格，而 ``class
    MyStrategy`` 写在下面一格；只拷类那格 → desk 导入时报
    ``NameError: name 'SYMBOL' is not defined`` ✗（实测 15_desk_live）。

    只带**纯字面量**（str / int / float / bool / None 及其 tuple / list / dict），
    不拷模块 / 类 / 函数，也不带副作用（不会把上一格的 ``TqApi(...)`` 跑一遍 ✓）。
    """
    import ast
    try:
        from IPython import get_ipython
        namespace = dict(getattr(get_ipython(), 'user_ns', {}) or {})
    except Exception:                                            # noqa: BLE001
        return []
    lines: List[str] = []
    for name in _cell_missing_names(cell):
        if name not in namespace:
            continue
        value = namespace[name]
        if not isinstance(value, (str, int, float, bool, type(None),
                                  tuple, list, dict)):
            continue
        try:
            text = repr(value)
            ast.literal_eval(text)          # 必须能还原成字面量 ✓
        except Exception:                                        # noqa: BLE001
            continue
        if len(text) > 400:
            continue
        lines.append(f'{name} = {text}')
    return lines


def strategy_path(strategy: Any) -> str:
    """策略**类** → 一个真实的 ``.py`` 路径（desk 只能按路径导入 ✓）

    优先用类所在模块 / 源文件；拿不到源码（交互式 / **notebook** 里定义的类）时
    拷一份到 ``~/.minibt/desk/generated/<类名>.py`` ✓
    """
    import inspect
    import sys
    if isinstance(strategy, str):
        return strategy
    target = strategy if isinstance(strategy, type) else type(strategy)
    # ① 类所在模块的 __file__（正常 import 的脚本最可靠 ✓）
    module = sys.modules.get(str(getattr(target, '__module__', '') or ''))
    path = str(getattr(module, '__file__', '') or '')
    if path and os.path.isfile(path):
        return path
    # ② inspect 兜底
    try:
        found = inspect.getsourcefile(target) or ''
    except Exception:                                            # noqa: BLE001
        found = ''
    if found and os.path.isfile(found):
        return found
    # ③ Notebook：拷**整个单元格**（含同格的指标类 / 常量 ✓）
    cell = _cell_source(target)
    if cell:
        os.makedirs(GENERATED_DIR, exist_ok=True)
        path = os.path.join(GENERATED_DIR, f'{target.__name__}.py')
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(chr(10).join([
                '# -*- coding: utf-8 -*-',
                '# 由 minibt desk（Gui.Desk）从 Jupyter 单元格生成 ✓',
                '# （desk 只能按真实 .py 路径导入策略）',
                'from minibt import *  # noqa: F401,F403',
                'import numpy as np  # noqa: F401',
                'import pandas as pd  # noqa: F401',
                '',
            ]))
            body = cell.replace(chr(13) + chr(10), chr(10)).rstrip()
            constants = _cell_constants(body)
            if constants:
                fp.write(chr(10).join([
                    '# —— 来自其它单元格的常量（notebook 里 SYMBOL 常写在上一格）——',
                    *constants,
                    '',
                ]))
            fp.write(body)
        return path
    # ④ 写一份（类源码可用时；desk 需要一个真实文件才能导入 ✓）
    try:
        source = inspect.getsource(target)
    except Exception as error:                                   # noqa: BLE001
        raise ValueError(
            f'拿不到 {target.__name__} 的源码，无法交给 desk；'
            '请用 ``Bt(strategy=...)`` 传**类**（在 .py 里定义的），'
            f'或者直接把策略文件路径传给 desk（{error!r}）') from error
    os.makedirs(GENERATED_DIR, exist_ok=True)
    path = os.path.join(GENERATED_DIR, f'{target.__name__}.py')
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(chr(10).join([
            '# -*- coding: utf-8 -*-',
            '# 由 minibt desk（Gui.Desk）自动生成：',
            '# 策略类交互式定义时没有源文件，desk 需要一个真实 .py ✓',
            'from minibt import *  # noqa: F401,F403',
            '',
            source.replace(chr(13) + chr(10), chr(10)),
            '',
        ]))
    return path


def add_local_strategy(desk, path: str, name: str = '', *,
                       cell: int = 0) -> Any:
    """本地图表「加到图表」：把策略挂到 CSV 上（自动多合约布局 ✓）

    `name` 为空 → desk 先打开一个空白本地图表页，再按策略里的本地合约
    自动选一份 CSV（`_on_editor_add_indicator` 里会补 ✓）。
    """
    if not name and not any(item.get('action') == 'open_local_chart'
                            for item in desk.pending_ui):
        desk.queue_ui('open_local_chart', name='')
    desk.queue_ui('add_strategy', path=str(path), symbol=str(name or ''),
                  cell=int(cell or 0), local=True)
    return desk


def open_strategy_lab(desk, path: str, mode: str = 'backtest') -> Any:
    """打开 desk 的「策略回测 / 参数优化」页（GUI 里点按钮同一套 ✓）"""
    desk.queue_ui('open_strategy_lab', file=str(path),
                  mode='optimize' if str(mode) == 'optimize' else 'backtest')
    return desk


def show_strategy(strategy: Any, *, desk=None, browser: bool = False,
                  mode: str = '', replay_bars: int = 4000) -> Any:
    """本地图表 + 策略「加到图表」；``mode`` 有值时再开回测/优化页 ✓"""
    path = strategy_path(strategy)
    desk = desk or new_desk(browser=browser)
    try:
        desk.offline = True          # 本地图表不依赖行情源 ✓
    except Exception:                                            # noqa: BLE001
        pass
    desk.queue_ui('open_local_chart', name='')       # 打开空白本地图表页
    desk.queue_ui('add_strategy', path=path, local=True,
                  replay_bars=int(replay_bars))
    if mode:
        desk.queue_ui('open_strategy_lab', file=path, mode=mode)
    return desk


# --------------------------------------------------------------- 实时（live）
def add_realtime_strategy(desk, path: str, symbol: str, **kwargs) -> Any:
    """实时图表「加到图表」：开户 + 挂策略（真下单，走 desk 的交易开关 ✓）"""
    desk.queue_ui('open_chart', symbol=symbol,
                  name=str(kwargs.get('name') or ''))
    desk.queue_ui('add_strategy', path=str(path), symbol=symbol, cell=0,
                  **kwargs)
    return desk


#: `params` 里常见的合约字段名（`params = dict(symbol='SHFE.ag2612')` ✓）
SYMBOL_KEYS = ('symbol', 'contract', 'code', 'instrument', 'leg_a', 'leg_b')


def strategy_symbols(strategy: Any) -> List[str]:
    """策略用到的合约（第一个用来开图表 tab ✓）

    ① 先看类里的 ``params``（`symbol` / `leg_a` / `leg_b` …）——一个文件里
       写多个策略时（多策略同时实时），静态分析分不清是谁的参数，类属性
       才是**准的** ✓；
    ② 再看 ``get_kline('合约')`` 的静态分析结果。
    """
    params = getattr(strategy, 'params', None)
    if params is not None:
        out: List[str] = []
        for key in SYMBOL_KEYS:
            try:
                value = params.get(key) if hasattr(params, 'get')                     else getattr(params, key, None)
            except Exception:                                    # noqa: BLE001
                value = None
            if isinstance(value, str) and value and value not in out:
                out.append(value)
        if out:
            return out
    try:
        from .strategy_plan import analyze
        plan = analyze(strategy_path(strategy))
        return [str(item) for item in (plan.get('contracts') or []) if item]
    except Exception:                                            # noqa: BLE001
        return []


def show_live(strategies: Iterable[Any], *, api=None, tq_auth=None,
              account=None, browser: bool = False,
              theme: str = 'dark') -> Any:
    """``Bt(live=True, gui=Gui.Desk)``：登录天勤 → 每个策略一个图表页 ✓"""
    desk = new_desk(browser=browser, theme=theme,
                    title='minibt桌面端 · 实时')
    try:
        desk.add_futures(tq_auth=tq_auth, tq_account=account, api=api)
    except Exception as error:                                   # noqa: BLE001
        print(f'[desk] 期货登录失败：{error!r}')
    entries = []
    for strategy in list(strategies):
        path = strategy_path(strategy)
        symbols = strategy_symbols(strategy)
        target = symbols[0] if symbols else ''
        if not target:
            # 策略没写合约名（用 klines1 / 默认合约）→ 先开空白图表 + 搜索
            desk.queue_ui('open_local_chart', name='')
            continue
        entries.append((path, target,
                        getattr(strategy, '__name__', '') or ''))
    # 先开全部图表页，再等 K 线历史到齐后逐个挂策略 ✓
    for path, target, _name in entries:
        desk.queue_ui('open_chart', symbol=target)
    for index, (path, target, name) in enumerate(entries):
        desk.queue_ui(
            'add_strategy', path=path, symbol=target, cell=0,
            strategy=name, local=False,
            delay=(3.0 if index == 0 else 0.0))
    return desk
