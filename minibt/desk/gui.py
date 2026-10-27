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
"""
from __future__ import annotations

import os
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


def run_desk(desk, *, browser: bool = False) -> None:
    """启动 desk（阻塞到用户关窗 ✓）"""
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
def strategy_path(strategy: Any) -> str:
    """策略**类** → 一个真实的 ``.py`` 路径（desk 只能按路径导入 ✓）

    优先用类所在模块 / 源文件；拿不到源码（交互式 ``exec`` 出来的类）时
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
    # ③ 写一份（类源码可用时；desk 需要一个真实文件才能导入 ✓）
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
