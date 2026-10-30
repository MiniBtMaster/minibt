"""在 desk 里**离线跑一遍 minibt 策略**（P65：不依赖 miniqt ✓）

miniqt 的 `strategy_runner.py` 已经把"把策略接到图表"这件事摸清了；这里只
把它需要的那部分**搬进 minibt**（去掉 Qt / miniqt 相关的部分），这样：

* 只装 minibt 的用户也能用「加到图表 → 策略」；
* 不会因为 miniqt 版本变化而报错（用户明确要求 ✓）。

原理（和 miniqt 一致）：

1. 策略以**回测模式**实例化（`_is_live_trading=False`，`buy/sell` 只改内部
   模拟账户，**不会真下单** ✓）；
2. 猴补 `strategy.get_kline`：第一次调用用图表那格的 DataFrame 建成 KLine，
   之后每次返回 `None`（minibt 的 `__setattr__` 会保留旧 KLine ✓）；
3. `advance()`：把新帧写进 KLine 的 `tq_object` → `_inplace_values()` →
   `_strategy_init()`（重跑用户 `__init__` 里的指标）→ `step()`（= `next`）；
4. `specs()` / `signals()`：用 `minibt.strategy.realtime` 的提取器拿指标线 /
   买卖信号 ✓。
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional

import pandas as pd

#: 策略 KLine 需要的完整列（含合约信息！以前只取 `FILED.ALL` →
#: `volume_multiple` / `price_tick` / `symbol` 被丢掉 → KLine 回退成
#: 1 倍合约乘数、0.01 最小变动，策略手数/盈亏全错 ✗）
try:
    from ..indicators.core import FILED as _FILED
    _ALL_FIELDS = list(_FILED.Quote)
except Exception:                                                # noqa: BLE001
    _ALL_FIELDS = ['datetime', 'open', 'high', 'low', 'close', 'volume',
                   'symbol', 'duration', 'price_tick', 'volume_multiple']

#: 缺列时的兜底值（和 minibt `default_symbol_info` 一致 ✓）
_FIELD_DEFAULTS = {'symbol': 'symbol', 'duration': 60,
                   'price_tick': 0.01, 'volume_multiple': 1.0}

_OHLCV = ('open', 'high', 'low', 'close', 'volume')


class StrategyRunError(Exception):
    """策略准备 / 步进失败。"""


def next_sid() -> int:
    """下一个 `_sid`（minibt 按**位置**索引策略实例 ✓）"""
    try:
        from minibt import Strategy as _Strategy
        return len(_Strategy._strategy_instances)
    except Exception:                                            # noqa: BLE001
        return 0


def declared_charts(cls) -> List[Any]:
    """策略类上可选的 `charts = [...]`（声明式合约表 ✓）"""
    raw = None
    for base in getattr(cls, '__mro__', [cls]):
        if 'charts' in getattr(base, '__dict__', {}):
            raw = base.__dict__['charts']
            break
    if not raw or not isinstance(raw, (list, tuple)):
        return []
    out: List[Any] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and item:
            cycle = int(item[1]) if len(item) > 1 and item[1] else 0
            out.append((str(item[0]), cycle))
        elif isinstance(item, str):
            out.append((item, 0))
    return out


def to_strategy_frame(frame) -> pd.DataFrame:
    """图表帧 → 策略帧（`datetime` + OHLCV ✓）"""
    if frame is None:
        raise StrategyRunError('没有可用的 K 线数据')
    out = frame.copy()
    missing = [col for col in _OHLCV if col not in out.columns]
    if missing:
        raise StrategyRunError(f'图表数据缺少列：{"、".join(missing)}')
    if 'datetime' not in out.columns:
        if 'time' not in out.columns:
            raise StrategyRunError('图表数据缺少 time/datetime 列')
        out['datetime'] = pd.to_datetime(out['time'])
    else:
        out['datetime'] = pd.to_datetime(out['datetime'])
    return out.reset_index(drop=True)


def fill_all_fields(frame: pd.DataFrame,
                    base: pd.DataFrame) -> pd.DataFrame:
    """补齐 minibt KLine 需要的列（含合约字段，从 `base` 广播 ✓）"""
    out = frame.copy()
    for col in _ALL_FIELDS:
        if col in out.columns:
            continue
        if col in base.columns and len(base):
            out[col] = base[col].iloc[0]
        else:
            out[col] = _FIELD_DEFAULTS.get(col, 0)
    return out[_ALL_FIELDS]


def _same_contract(a: str, b: str) -> bool:
    def norm(text):
        text = str(text or '').strip().upper()
        return text.split('.')[-1] if '.' in text else text
    return bool(a) and bool(b) and norm(a) == norm(b)


def _same_underlying(a: str, b: str) -> bool:
    """`pp2609_60`（本地CSV名）≈ `DCE.pp2609`（实时合约）✓

    test_2.py 这类策略在本地图表里写的是 `LocalDatas.pp2609_60`；
    放到实时图表时用户不可能改策略文件 → 按“去掉周期后缀后的品种代码”
    对到当前图表里的真实合约（`DCE.pp2609`），数据用实时 K 线、
    下单用真实合约代码 ✓
    """
    import re as _re

    def bare(text):
        text = str(text or '').strip().upper()
        if '.' in text:
            text = text.split('.')[-1]
        return _re.sub(r'_\d+$', '', text)

    left, right = bare(a), bare(b)
    return bool(left) and bool(right) and left == right


def _is_local_name(text: str) -> bool:
    """`pp2609_60` / `l2609_60` 这种本地 CSV 名（带周期后缀）✓"""
    import re as _re
    return bool(_re.search(r'_\d+$', str(text or '').strip()))


def _refresh_klinesetting(kline) -> None:
    """帧变长后同步 `_klinesetting`（`buy/sell` 取 `current_time[btindex]` ✓）"""
    try:
        setting = kline._klinesetting
        obj = kline.pandas_object
        for attr, values in (('current_open', obj.open.values),
                             ('current_high', obj.high.values),
                             ('current_low', obj.low.values),
                             ('current_close', obj.close.values)):
            try:
                setattr(setting, attr, values)
            except Exception:                                    # noqa: BLE001
                pass
        try:
            time_values = obj.datetime
            setattr(setting, 'current_time', time_values)
            setattr(setting, 'current_datetime',
                    time_values.dt.strftime('%Y-%m-%d %H:%M:%S').values)
        except Exception:                                        # noqa: BLE001
            pass
    except Exception:                                            # noqa: BLE001
        pass


def _safe_btindex(klines) -> int:
    """最后一个可用 `btindex`（不超数据 / `current_time` 长度 ✓）"""
    try:
        length = min(len(k) for k in klines)
    except Exception:                                            # noqa: BLE001
        return -1
    for kline in klines:
        try:
            length = min(length, len(kline._klinesetting.current_time))
        except Exception:                                        # noqa: BLE001
            pass
    return length - 1


class StrategyRunner:
    """一个策略实例的「准备 / 每拍 / 取指标」封装（**只算不画** ✓）"""

    def __init__(self, cls, params=None, symbol: str = '',
                 cycle: int = 60, *, live: bool = False,
                 api=None, account=None, fetch_frame=None):
        self.cls = cls
        self.params = dict(params or {})
        self.symbol = symbol
        self.cycle = int(cycle or 60)
        #: 实时图表 + 天勤已连接时：策略走实盘/模拟盘分支（真下单）
        self.live = bool(live and api is not None)
        self.api = api
        self.account = account
        #: `callback(symbol, cycle) -> DataFrame`：策略 `get_kline('其它合约')`
        #: 时按需取 K 线（实时图表多合约策略 ✓）
        self.fetch_frame = fetch_frame
        self.strategy = None
        self.kline = None
        self.error = ''
        #: 单个策略的开关覆盖（「策略管理」里可改 ✓）
        self.override: Dict[str, Any] = {}
        self.traceback = ''
        self.declared: List[Any] = []
        #: 与 `_klines` 一一对应的**数据合约**（实时每拍按它取 frame ✓）
        self._kline_symbols: List[str] = []
        self._kline_symbols_cache: List[str] = []
        #: 同一根 K 线内 next 只在 close 变化时运行（频率模式 ✓）
        self._last_logic_close: Any = None

    # ---------------------------------------------------------- 准备
    def prepare(self, frames, seed_kline: bool = False):
        """实例化 + 注入图表数据 + 走完 minibt 的启动准备 ✓"""
        if isinstance(frames, (list, tuple)):
            raw = list(frames)
        else:
            raw = [frames]
        if not raw:
            raise StrategyRunError('没有可用的 K 线数据')
        self._symbols: List[str] = []
        frame_list: List[pd.DataFrame] = []
        for item in raw:
            if (isinstance(item, (list, tuple)) and len(item) == 2
                    and isinstance(item[1], pd.DataFrame)):
                self._symbols.append(str(item[0] or ''))
                frame_list.append(to_strategy_frame(item[1]))
            else:
                self._symbols.append('')
                frame_list.append(to_strategy_frame(item))
        self._frames = frame_list
        self._frame = frame_list[0]
        self.declared = declared_charts(self.cls)
        # ★ **多合约（写法 2）**：策略在 `__init__` 里就写
        #   `self.klines1.close.sma(...)` → 实例化**之前**必须先有 K 线数据，
        #   否则 `self.klines1` 是 None → `'NoneType' has no attribute close` ✗
        #   办法：先用传入的 frames 建好 KLine，再 `__new__` + 注入
        #   `_btklinedataset`，最后才跑用户 `__init__` ✓
        pre_seeds: List[Any] = []
        if seed_kline and len(frame_list) > 1:
            from ..indicators.core import KLine as _PreKLine
            for position, item in enumerate(frame_list):
                prepared = fill_all_fields(item, item)
                name = (self._symbols[position]
                        if position < len(self._symbols) else '')
                if self.live and name:
                    prepared['symbol'] = str(name)
                    prepared['duration'] = int(self.cycle or 60)
                try:
                    pre_seeds.append(_PreKLine(
                        prepared, duration_seconds=int(self.cycle or 60),
                        data_length=None,
                        **(dict(account=self.account) if self.live else {})))
                except Exception as error:                        # noqa: BLE001
                    self.error = f'预建 K 线失败：{error!r}'
        try:
            kwargs = {'_sid': next_sid(), '_isplot': True}
            if self.live:
                # 必须在 Strategy.__init__ / KLine 创建之前标记，
                # 否则 KLine 会绑定回测 Broker，后面再改标志也来不及 ✓
                kwargs.update({
                    '_is_live_trading': True,
                    '_api': self.api,
                    '_live_account': self.account,
                })
            if pre_seeds:
                from ..utils import KLinesSet
                strategy = self.cls.__new__(self.cls)
                dataset = KLinesSet()
                for position, kline in enumerate(pre_seeds):
                    key = (self._symbols[position]
                           if position < len(self._symbols) else str(position))
                    dataset[str(key or position)] = kline
                strategy._btklinedataset = dataset   # ★ 用户 __init__ 前注入 ✓
                strategy.__dict__['_kline_cache'] = pre_seeds[0]
                self.cls.__init__(strategy, **kwargs)
            else:
                strategy = self.cls(**kwargs)
        except Exception as error:                               # noqa: BLE001
            raise StrategyRunError(
                f'策略实例化失败：{type(error).__name__}: {error}') from error

        original = strategy.get_kline
        runner = self
        self._klines_cache: List[Any] = []
        self._call_index = 0
        self._requests: List[Any] = []
        self._seed_kline = None

        def patched_get_kline(symbol=None, duration_seconds=None,
                              data_length=None, **kwargs):
            index = runner._call_index
            runner._call_index += 1
            if index < len(runner._klines_cache):
                # ★ 实时图表每拍会重跑用户 `__init__`（重算指标），必须把
                #   **同一个 KLine** 再发一次；以前返回 None →
                #   `self.data = self.get_kline(...)` 变成 None → 策略直接崩 ✗
                return runner._klines_cache[index]
            symbol_text = str(symbol or '')
            if not symbol_text and index < len(runner.declared):
                symbol_text = str(runner.declared[index][0] or '')
            frame = None
            matched_name = ''
            frame_index = -1
            if symbol_text:
                for pos, name in enumerate(runner._symbols):
                    if name and _same_contract(name, symbol_text):
                        frame = frame_list[pos]
                        matched_name = name
                        frame_index = pos
                        break
            # ★ 本地 CSV 名（`LocalDatas.pp2609_60`）在实时图表里按
            #   **品种代码** 对到真实合约（`DCE.pp2609`）✓
            if frame is None and runner.live and symbol_text:
                for pos, name in enumerate(runner._symbols):
                    if name and _same_underlying(name, symbol_text):
                        frame = frame_list[pos]
                        matched_name = name
                        frame_index = pos
                        break
            # ★ **实时多合约**：策略里 `get_kline('SHFE.rb2601')` 或
            #   `LocalDatas.pp2609_60`（按品种对到已打开合约）→ 现取一条 ✓
            fetch_failed = False
            if runner.live and symbol_text and frame is None:
                fetched = None
                fetched_symbol = symbol_text
                if callable(runner.fetch_frame):
                    try:
                        fetched = runner.fetch_frame(
                            symbol_text,
                            int(duration_seconds or runner.cycle or 60))
                    except Exception as error:                # noqa: BLE001
                        runner.error = f'取 {symbol_text} K线失败：{error!r}'
                # `fetch_frame` 可以返回 `(真实合约, frame)`：
                # test_2 的 `pp2609_60` → `DCE.pp2609` ✓
                if (isinstance(fetched, tuple) and len(fetched) == 2):
                    fetched_symbol, fetched = fetched
                if fetched is not None and len(fetched):
                    frame = to_strategy_frame(fetched)
                    matched_name = str(fetched_symbol or symbol_text)
                    if not any(_same_contract(name, matched_name)
                               for name in runner._symbols):
                        runner._symbols.append(matched_name)
                        frame_list.append(frame)
                    frame_index = len(frame_list) - 1
                else:
                    fetch_failed = True
            if frame is None:
                # ★ 按**调用顺序**兜底：任意本地名（`pp2609_60`）或
                #   `get_kline()` 不传合约 → 用第 index 组 frame ✓
                #   真实合约代码取不到时**不能**乱用别的合约（会下错单 ✗）
                can_index = (not runner.live) or (not symbol_text) \
                    or _is_local_name(symbol_text)
                if can_index and index < len(frame_list):
                    frame = frame_list[index]
                    frame_index = index
                    if index < len(runner._symbols):
                        matched_name = str(runner._symbols[index] or '')
                elif fetch_failed or runner.live:
                    raise StrategyRunError(
                        f'实时图表无法加载合约「{symbol_text}」的 K 线。'
                        '多合约策略请用可交易合约代码（如 SHFE.rb2601），'
                        '或先打开对应合约的图表；并确认交易接口已连接。')
                else:
                    frame = frame_list[-1]
                    frame_index = len(frame_list) - 1
                    if frame_index < len(runner._symbols):
                        matched_name = str(
                            runner._symbols[frame_index] or '')
            # 真实合约名：live 下单 / TqObjs 必须用它（不能是 pp2609_60）✓
            if matched_name:
                actual_symbol = matched_name
            elif runner.live:
                actual_symbol = str(runner.symbol or '')
            else:
                actual_symbol = (symbol_text
                                 or (runner._symbols[index]
                                     if index < len(runner._symbols) else '')
                                 or str(runner.symbol or ''))
            prepared = fill_all_fields(frame, frame)
            if runner.live:
                # ★ 必须改成**目标合约**：KLine 会据此建 TqObjs（报价/持仓/
                #   TargetPosTask），否则两个腿都会下到当前图表合约 ✗
                prepared['symbol'] = str(actual_symbol or runner.symbol)
                prepared['duration'] = int(duration_seconds
                                           or runner.cycle or 60)
                # ★ 实盘 get_kline 不能再走 `original()`：minibt 的实盘
                #   分支会调 `api.get_kline_serial(symbol, ...)` 再取一遍，
                #   而这里传入的是已经取好的 DataFrame → 报
                #   “'DataFrame' object has no attribute ... / get_kline_serial” ✗
                #   直接用 KLine 构造（带 account → TqObjs），后续每拍由
                #   `_sync_klines` 更新数据 ✓
                from ..indicators.core import KLine as _KLine
                kline = _KLine(prepared,
                               duration_seconds=int(duration_seconds
                                                    or runner.cycle or 60),
                               data_length=None, account=runner.account)
            else:
                kline = original(prepared,
                                 duration_seconds=int(duration_seconds
                                                      or runner.cycle or 60),
                                 data_length=None, **kwargs)
            runner._klines_cache.append(kline)
            runner._kline_symbols_cache.append(str(actual_symbol or ''))
            runner._requests.append(
                (str(actual_symbol if runner.live
                     else (symbol_text or actual_symbol or '')),
                 int(duration_seconds or runner.cycle or 60)))
            return kline

        try:
            strategy.get_kline = patched_get_kline
        except Exception:                                        # noqa: BLE001
            pass

        # ★ **本地回放里的策略下单**：不落到 minibt 的 Broker，而是**记录下来**
        #   交给 desk 的本地模拟账户按合约各自成交（多合约配对交易 ✓）
        #   `runner.orders` = [{symbol, side, size, price, bar}]
        self.orders: List[Dict[str, Any]] = []
        self._order_serial = 0

        def _wrap_order(original_order, side: str):
            def inner(self_strategy, data=None, size=1, exectype=None,
                      price=None, valid=None, stop=None, reverse=False,
                      reverse_size=0, **kwargs):
                # ★ 先走 minibt 原来的 buy/sell：策略自己的持仓 / Broker /
                #   BtStop 都要更新，否则 `self.data.position` 一直是 0、
                #   停止线也不会出现（CCI 回放实测 ✗）。
                #   KLine.buy() 调用的是 7 个位置参数，签名必须完整 ✓
                result = original_order(
                    data=data, size=size, exectype=exectype,
                    price=price, valid=valid, stop=stop,
                    reverse=reverse, reverse_size=reverse_size,
                    **kwargs)
                # ★ KLine 自带的 `symbol` 是内部编号（`symbol3`）✗
                #   → 用**对象身份**对回数据源名字（CSV 名 / 合约代码 ✓）
                symbol = runner.source_of_kline(data) or ''
                if not symbol:
                    symbol = str(getattr(data, 'symbol', '') or '')
                if not symbol:
                    symbol = str(runner.symbol or '')
                # 反手/停止单可能调整实际手数；优先用订单里的 size ✓
                actual = getattr(result, 'size', None)
                try:
                    actual = abs(float(actual))
                except (TypeError, ValueError):
                    actual = abs(float(size or 0)) or 0.0
                runner.orders.append({
                    'symbol': symbol, 'side': side,
                    'size': actual,
                    'price': (None if price is None else float(price)),
                    'index': int(getattr(runner, '_replay_index', -1)),
                    'serial': runner._order_serial,
                })
                runner._order_serial += 1
                return result
            return inner

        if not self.live:
            try:
                strategy.buy = _wrap_order(strategy.buy, 'buy').__get__(strategy)
                strategy.sell = _wrap_order(strategy.sell, 'sell').__get__(strategy)
            except Exception as error:                           # noqa: BLE001
                self.error = f'下单钩子安装失败：{error!r}'

        seed_done = False
        #: 预建 K 线的**名字顺序**（`self.klines1` = 第 1 个 ✓）
        self._seed_order: List[str] = [
            str((self._symbols[index] if index < len(self._symbols) else '')
                or index) for index in range(len(pre_seeds))]
        self._seed_symbols: List[str] = list(self._seed_order)
        self._seed_klines: List[Any] = list(pre_seeds)
        if pre_seeds:
            seed_done = True
            self._seed_kline = pre_seeds[0]
            try:
                strategy.kline = pre_seeds[0]
            except Exception:                                    # noqa: BLE001
                pass
            # ★ 走 `__new__` 注入时绕过了基础初始化 →
            #   这里必须补上（`_account` / `_btindicatordataset` 都在这建 ✓）
            try:
                strategy._init_basic_components_before_start()
            except Exception as error:                           # noqa: BLE001
                self.error = f'基础组件初始化失败：{error!r}'
        if seed_kline and frame_list and not seed_done:
            # 策略不用 `get_kline` → 先注一条默认 KLine（`self.kline` 可用 ✓）
            try:
                strategy._init_basic_components_before_start()
                seed = fill_all_fields(frame_list[0], frame_list[0])
                # ★ live：KLine 初始化必须带 symbol/duration（要建 TqObjs），
                #   不能再把 DataFrame 当 `get_kline(symbol=...)` 传进去 ✗
                if self.live:
                    from ..indicators.core import KLine as _KLine
                    seed['symbol'] = str(self.symbol or '')
                    seed['duration'] = int(self.cycle or 60)
                    kline = _KLine(seed, duration_seconds=int(self.cycle or 60),
                                   data_length=None, account=self.account)
                else:
                    kline = original(seed, duration_seconds=int(self.cycle or 60),
                                     data_length=None)
                strategy.kline = kline
                self._seed_kline = kline
                self._seed_klines.append(kline)
                self._seed_symbols.append(str(self.symbol or ''))
                # ★ **多合约**：每个传入的 frame 各建一条 KLine →
                #   `self.klines1 / klines2 …` 在本地多布局里可用 ✓
                for position, extra in enumerate(frame_list[1:], start=1):
                    try:
                        extra_seed = fill_all_fields(extra, extra)
                        extra_name = (self._symbols[position]
                                      if position < len(self._symbols) else '')
                        if self.live:
                            from ..indicators.core import KLine as _KLine
                            extra_seed['symbol'] = str(extra_name
                                                       or self.symbol or '')
                            extra_seed['duration'] = int(self.cycle or 60)
                            extra_kline = _KLine(
                                extra_seed,
                                duration_seconds=int(self.cycle or 60),
                                data_length=None, account=self.account)
                        else:
                            extra_kline = original(
                                extra_seed,
                                duration_seconds=int(self.cycle or 60),
                                data_length=None)
                        self._seed_klines.append(extra_kline)
                        self._seed_symbols.append(str(
                            extra_name or self.symbol or ''))
                    except Exception as error:                   # noqa: BLE001
                        self.error = f'额外 K 线准备失败：{error!r}'
                seed_done = True
            except Exception as error:                           # noqa: BLE001
                self.error = f'默认 K 线准备失败：{error!r}'
        try:
            if seed_done:
                strategy._strategy_init()
                strategy._init_strategy_data()
                strategy.start()
            else:
                strategy._prepare_before_strategy_start()
        except Exception as error:                               # noqa: BLE001
            raise StrategyRunError(
                f'策略初始化失败：{type(error).__name__}: {error}') from error

        self._klines = list(self._seed_klines) + list(self._klines_cache)
        # ★ 每个 KLine → 数据合约（实时多合约每拍按名字取 frame ✓）
        seed_symbols = list(self._seed_symbols)
        if len(seed_symbols) < len(self._seed_klines):
            seed_symbols += [''] * (len(self._seed_klines) - len(seed_symbols))
        self._kline_symbols = (seed_symbols[:len(self._seed_klines)]
                               + list(self._kline_symbols_cache))
        while len(self._kline_symbols) < len(self._klines):
            self._kline_symbols.append(str(self.symbol or ''))
        self._kline_symbols = self._kline_symbols[:len(self._klines)]
        # ★ **`set_target_size()` 写法**（配对交易常用：`self.data.set_target_size(-n)`）
        #   以前只挂了 `buy/sell` → 用 `set_target_size` 的策略一条成交都没有 ✗
        #   这里逐条 K 线包一层：**先调原方法**（策略自己的持仓/账户状态要更新），
        #   再把「目标手数」记到 `runner.targets` 交给 desk 落地到本地模拟账户 ✓
        self.targets: List[Dict[str, Any]] = []
        self._target_serial = 0
        if not self.live:
            for kline in self._klines:
                self._wrap_target_size(kline)
        if not self._klines and self._seed_kline is not None:
            self._klines = [self._seed_kline]
        if not self._klines:
            raise StrategyRunError(
                '策略没有 K 线数据（既没 get_kline，也没能注入默认 K 线）')
        self.kline = self._klines[0]
        try:
            strategy._btindex = _safe_btindex(self._klines)
        except Exception:                                        # noqa: BLE001
            pass
        try:
            strategy._get_plot_datas()
        except Exception:                                        # noqa: BLE001
            pass
        # KLine 已经按 live/backtest 创建完；把实例标记固定住，
        # 后面 Base._is_live_trading 恢复 False 也不会影响这张图的 KLine ✓
        if self.live:
            for kline in self._klines:
                try:
                    kline._is_live_trading = True
                except Exception:                            # noqa: BLE001
                    pass
        strategy._first_start = True
        # `_strategy_init()` 已在 prepare 里跑过；advance 不要再跑一次
        #（用户日志里 `进入init` 出现两次就是这个原因）
        self._inited = True
        self.strategy = strategy
        return strategy

    # ---------------------------------------------------------- 每拍
    def _sync_klines(self, frames) -> None:
        """把 `frames` 灌进策略的 K 线（`advance` / `replay` 共用 ✓）

        * list：按顺序对应 `_klines`（单合约 / 本地回放，旧行为不变 ✓）
        * dict：``{合约: frame}`` —— 实时图表多合约策略按**每个 KLine 自己的
          合约**取 frame；某个合约这拍没取到就保留旧数据，不会被主图覆盖 ✗
        """
        if isinstance(frames, dict):
            frame_map = {str(key): value for key, value in frames.items()
                         if value is not None}
            ordered: List[Any] = []
            for index, kline in enumerate(self._klines):
                symbol = (self._kline_symbols[index]
                          if index < len(self._kline_symbols) else '')
                frame = frame_map.get(symbol)
                if frame is not None:
                    frame = to_strategy_frame(frame)
                    frame_map[symbol] = frame
                if frame is None:
                    # 这个合约本次没取到 → 保留 KLine 现有数据 ✓
                    frame = getattr(kline, 'pandas_object', None)
                ordered.append(frame)
                if frame is None:
                    continue
                self._update_kline_values(kline, frame)
            if ordered:
                self._frames = [item for item in ordered if item is not None]
            return
        if not isinstance(frames, (list, tuple)):
            frames = [frames]
        frames = [to_strategy_frame(item) for item in frames]
        self._frames = frames
        for index, kline in enumerate(self._klines):
            frame = (frames[index] if index < len(frames) else frames[-1])
            self._update_kline_values(kline, frame)

    @staticmethod
    def _update_kline_values(kline, frame) -> None:
        """一个 KLine 换上新 frame（并同步 `_klinesetting` 的当前数组 ✓）"""
        base = getattr(kline, 'pandas_object', None)
        full = fill_all_fields(frame, base if base is not None else frame)
        try:
            kline._dataset.tq_object = full
            kline._inplace_values()
        except Exception:                                    # noqa: BLE001
            kline._update_replace(full)
        _refresh_klinesetting(kline)

    def update_symbols(self) -> List[str]:
        """实时策略需要每拍更新的合约（去重、保持顺序 ✓）"""
        out: List[str] = []
        for symbol in list(self._kline_symbols) + [self.symbol]:
            text = str(symbol or '')
            if not text:
                continue
            if any(_same_contract(text, item) for item in out):
                continue
            out.append(text)
        return out

    def account_spec(self) -> Dict[str, Any]:
        """快照策略的 minibt 账户 / 合约参数（供 desk LocalSim 使用 ✓）

        返回::

            {'initial_cash': 1_000_000.0,
             'contracts': {desk名: {'price_tick':…, 'volume_multiple':…,
                                    'margin_rate':…, 'slip_point':…,
                                    'commission': {'fixed_commission': 1.0},
                                    'minibt_symbol': 'DCE.pp2609'}}}

        优先级：KLine 自己的 broker（`self.data.fixed_commission = 1` 等
        用户覆盖）> 策略 `config` > 代码默认。
        """
        strategy = self.strategy
        config = getattr(strategy, 'config', None)

        def num(value, default: float) -> float:
            try:
                value = float(value)
            except (TypeError, ValueError):
                return default
            return value if value > 0 else default

        initial = num(getattr(config, 'value', None), 1_000_000.0)
        global_margin = num(getattr(config, 'margin_rate', None), 0.05)
        global_slip = num(getattr(config, 'slip_point', None), 0.0)
        try:
            global_fee = dict(config._get_commission())
        except Exception:                                    # noqa: BLE001
            global_fee = {'fixed_commission': 0.0}

        contracts: Dict[str, Dict[str, Any]] = {}
        for index, kline in enumerate(getattr(self, '_klines', None) or []):
            name = ''
            try:
                name = str(self.source_of_kline(kline) or '')
            except Exception:                                # noqa: BLE001
                name = ''
            if not name:
                if index < len(getattr(self, '_kline_symbols', []) or []):
                    name = str(self._kline_symbols[index] or '')
                else:
                    name = str(getattr(kline, 'symbol', '') or '')
            if not name or name.lower().startswith('symbol'):
                # 内部编号（symbol3）不能当 desk 合约名 ✓
                if index < len(getattr(self, '_kline_symbols', []) or []):
                    name = str(self._kline_symbols[index] or name)
            if not name:
                continue
            broker = getattr(kline, '_broker', None)
            price_tick = num(getattr(kline, 'price_tick', None), 0.01)
            multiple = num(getattr(kline, 'volume_multiple', None), 1.0)
            margin_rate = num(getattr(broker, 'margin_rate', None)
                              if broker is not None else None, global_margin)
            slip = num(getattr(broker, 'slip_point', None)
                       if broker is not None else None, global_slip)
            commission = None
            if broker is not None:
                try:
                    commission = dict(getattr(broker, 'commission', {}) or {})
                except Exception:                            # noqa: BLE001
                    commission = None
            if not commission:
                commission = dict(global_fee)
            contracts[name] = {
                'price_tick': price_tick,
                'volume_multiple': multiple,
                'margin_rate': margin_rate,
                'slip_point': slip,
                'commission': commission,
                'minibt_symbol': str(getattr(kline, 'symbol', '') or ''),
            }
        return {'initial_cash': initial, 'contracts': contracts}

    def runtime_config(self) -> Dict[str, Any]:
        """策略运行开关（单策略 override > desk 设置 > 策略 config）✓"""
        raw_cfg = getattr(getattr(self, 'strategy', None), 'config', None)
        # `Config` 是 dataclass（不是 dict）→ 不能直接 `dict(raw_cfg)` ✗
        if isinstance(raw_cfg, dict):
            cfg = dict(raw_cfg)
        elif raw_cfg is not None and hasattr(raw_cfg, '__dict__'):
            cfg = dict(vars(raw_cfg))
        else:
            try:
                cfg = dict(raw_cfg) if raw_cfg else {}
            except Exception:                                    # noqa: BLE001
                cfg = {}
        try:
            from . import user_prefs as _prefs
            settings = _prefs.settings()
        except Exception:                                        # noqa: BLE001
            settings = {}
        if 'strategy_next_on_new_bar' in settings:
            cfg['next_on_new_bar'] = bool(
                settings.get('strategy_next_on_new_bar'))
        if 'strategy_run_next' in settings:
            cfg['run_next'] = bool(settings.get('strategy_run_next'))
        try:
            cfg.update(dict(self.override or {}))
        except Exception:                                        # noqa: BLE001
            pass
        return cfg

    @property
    def next_on_new_bar(self) -> bool:
        """当前生效的「只在新 K 线下运行 next」开关 ✓"""
        return self.runtime_config().get('next_on_new_bar', True) is not False

    def _current_bar(self) -> tuple:
        """策略 K 线最后一根的 ``(stamp, close)``（归一化 ✓）"""
        sources = (getattr((self._klines or [None])[0], 'pandas_object', None),
                   (self._frames or [None])[0])
        for source in sources:
            try:
                value = source['datetime'].iloc[-1]
            except Exception:                                    # noqa: BLE001
                continue
            try:
                stamp = int(getattr(value, 'value', value))
            except Exception:                                    # noqa: BLE001
                try:
                    import pandas as _pd
                    stamp = int(_pd.Timestamp(value).value)
                except Exception:                            # noqa: BLE001
                    stamp = None
            close = None
            try:
                close = float(source['close'].iloc[-1])
            except Exception:                                    # noqa: BLE001
                close = None
            if stamp is not None:
                return stamp, close
        return None, None

    def _update_stops(self) -> None:
        """逐根推进策略时也要推进 BtStop（和 minibt 回测循环一致 ✓）。

        `Strategy.step()` 只负责 `next()`；回测主循环在每根 K 线之后还会调
        `KLine.stop.update()`。少了这一步，`stop_price` / `target_price`
        会永远保持 NaN，本地图表回放自然没有停止线 ✗。
        """
        strategy = self.strategy
        if strategy is None or not getattr(strategy, '_isstop', False):
            return
        for kline in (getattr(strategy, '_btklinedataset', {}) or {}).values():
            if not getattr(getattr(kline, '_klinesetting', None),
                           'isstop', False):
                continue
            stop = getattr(kline._klinesetting, 'stop', None)
            if stop is None:
                continue
            try:
                stop.update()
            except Exception:                                # noqa: BLE001
                # 单根止损更新失败不能中断策略回放；下一次继续尝试 ✓
                pass

    def advance(self, frames=None) -> bool:
        """推进一拍：同步 K 线 → 重算指标 → 跑 `next` ✓"""
        if self.strategy is None or not getattr(self, '_klines', None):
            return False
        try:
            if frames is not None:
                self._sync_klines(frames)
            # 清长度缓存：否则新增一根后指标长度校验不过 → 停在旧值 ✗
            try:
                dataset = self.strategy._btklinedataset
                dataset._lengths_cache = None
                dataset._max_length_cache = None
            except Exception:                                    # noqa: BLE001
                pass
            self._call_index = 0
            self.strategy._in_next_context = False
            try:
                self.strategy._btindex = _safe_btindex(self._klines)
            except Exception:                                    # noqa: BLE001
                pass
            was_live = getattr(self.strategy, '_is_live_trading', False)
            self.strategy._is_live_trading = True
            # ★ 每根新 K 线都重跑用户 `__init__`（指标重算）：
            #   策略里的 self.fast/self.slow 是在 __init__ 里算的，只跑一次
            #   会永远停在初始那一刻 → 图上均线不跟最新价格走（用户实测 ✗）。
            #   与 minibt 实盘 `_execute_live_trading` 的语义一致 ✓
            try:
                self.strategy._strategy_init()
            finally:
                self._inited = True
            self.strategy._is_live_trading = was_live
            self.strategy._in_next_context = True
            # ★ 实时图表：初始化完成后、进入 next 前再确保一次（用户要求）✓
            if self.live:
                self.strategy._is_live_trading = True
            # ★ `__init__`（指标计算）已经跑过，下面只决定**是否 / 在哪根**
            #   运行逻辑 `next`：
            #   * run_next=False → 只算指标；
            #   * next_on_new_bar=True → 只在出现新 K 线时跑一次；
            #   * next_on_new_bar=False → 每次更新频率跑，但要有新数据；
            #   * config.on_close=True（默认）→ 新 K 线时跑**上一根已完成**的
            #     next，避免拿正在生成的一字线做决策 ✓
            cfg = self.runtime_config()
            if cfg.get('run_next') is False:
                return True
            last_index = _safe_btindex(self._klines)
            if last_index < 0:
                return True
            stamp, close = self._current_bar()
            previous_stamp = getattr(self, '_last_stamp', None)
            first = previous_stamp is None
            new_bar = bool(stamp is not None and previous_stamp is not None
                           and stamp != previous_stamp)
            if stamp is not None:
                self._last_stamp = stamp
            if cfg.get('next_on_new_bar', True) is not False:
                # 首次挂策略：先按**上一根已完成**的 K 线跑一次（on_close），
                # 让策略恢复持仓 / 画信号；之后只在新 K 线时运行 ✓
                if not (new_bar or first):
                    return True                  # 同一根 K 线 → 只更新指标 ✓
                on_close = cfg.get('on_close', True) is not False
                step_index = (last_index - 1
                              if on_close and last_index > 0 else last_index)
                if step_index < 0:
                    return True
            else:
                changed = bool(first or new_bar
                               or (close is not None
                                   and close != self._last_logic_close))
                if not changed:
                    return True
                step_index = last_index
                self._last_logic_close = close
            # ★ next 前必须先有这一拍的 __init__ 结果（上面已经跑过）✓
            try:
                self.strategy._btindex = int(step_index)
            except Exception:                                    # noqa: BLE001
                pass
            self.strategy._in_next_context = True
            if self.live:
                self.strategy._is_live_trading = True
            self.strategy.step()
            self._update_stops()
            # 跑完恢复到最新一根（下一拍 _strategy_init / collect 用 ✓）
            try:
                self.strategy._btindex = int(last_index)
            except Exception:                                    # noqa: BLE001
                pass
            return True
        except Exception as error:                               # noqa: BLE001
            self.error = f'{type(error).__name__}: {error}'
            self.traceback = traceback.format_exc()
            return False

    def replay(self, frame, bars: int = 500) -> bool:
        """**逐根**推进，让策略的 `next()` 每根 K 线都跑一次 ✓

        ⚠ 关键：**不要**每根都把 KLine 截成前缀再灌进去。
        minibt 回测本来就是「KLine 全量 + `btindex` 指向当前根」——
        `Stop` / ATR 等对象在第一次 `buy(stop=...)` 时才创建；如果此时
        KLine 只有前 8000 根，后面 `stop_price.new` 会越界，停止线只剩
        第一根 / 时间错位（图上 0 ✗，用户实测）。
        这里 KLine 保持全量，逐根只改 `strategy._btindex` 再 `step()`：
        指标 / 停止器都在完整长度上创建，回放也快得多 ✓。
        """
        if self.strategy is None or frame is None or not len(frame):
            return False
        try:
            total = len(frame)
            max_index = _safe_btindex(self._klines)
            if max_index < 0:
                return False
            end = min(total, max_index + 1)
            start = max(0, int(getattr(self.strategy,
                                       'min_start_length', 0) or 0))
            start = max(start, total - max(1, int(bars)))
            start = min(start, max(0, end - 1))
            was_live = getattr(self.strategy, '_is_live_trading', False)
            self.strategy._is_live_trading = bool(self.live or was_live)
            try:
                for index in range(start, end):
                    self.strategy._btindex = index
                    self._call_index = 0
                    self.strategy._in_next_context = True
                    try:
                        self.strategy.step()
                        self._update_stops()
                    except Exception as step_error:          # noqa: BLE001
                        if not self.error:
                            self.error = (f'第 {index} 根：'
                                          f'{type(step_error).__name__}: '
                                          f'{step_error}')
                        continue
            finally:
                self.strategy._is_live_trading = was_live
            return True
        except Exception as error:                               # noqa: BLE001
            self.error = f'{type(error).__name__}: {error}'
            self.traceback = traceback.format_exc()
            return False

    def reset_replay(self, index: int = 0) -> None:
        """把策略重置到回放的起点（**从这一根重新开始交易** ✓）

        `prepare()` 里的 `replay()` 会把整个历史跑一遍 —— 那次运行只是为了
        算指标 / 信号，**不能**当成回放成交（否则一进回放就把几千根里的
        开平仓一次性灌进本地模拟账户，用户实测「还没点播放就成交了」✗）。

        这里做三件事：
        1. 清掉历史运行产生的 `orders` / `targets`（它们已属于"过去"）；
        2. 把 minibt 内部回测账户归零（`pos=0` / 可用资金回到初始值）；
        3. 把 `_btindex` / `_replay_index` 对齐到**当前回放位置**。

        注意：只重置**策略内部**账户，`LocalSim`（用户的本地模拟账户）
        不在这里 reset —— 手动下的单 / 之前的持仓要不要清由用户决定 ✓
        """
        self.orders = []
        self.targets = []
        self._order_serial = 0
        self._target_serial = 0
        self._last_stamp = None
        index = max(0, int(index or 0))
        self._replay_index = index
        self._call_index = 0
        strategy = self.strategy
        if strategy is None:
            return
        try:
            strategy._btindex = index
        except Exception:                                    # noqa: BLE001
            pass
        if self.live:
            return
        # ① 策略内部回测账户归零（多合约 = 多个 broker，一起 reset ✓）
        account = getattr(strategy, '_account', None)
        if account is not None and callable(getattr(account, 'reset', None)):
            lengths = []
            for kline in (getattr(self, '_klines', None) or []):
                try:
                    lengths.append(len(kline))
                except Exception:                            # noqa: BLE001
                    continue
            try:
                account.reset(max(1, max(lengths or [1])))
            except Exception as error:                       # noqa: BLE001
                self.error = f'回放账户重置失败：{error!r}'
        # ② K 线自己的临时状态（冷却 / 回溯游标）清掉
        for kline in (getattr(self, '_klines', None) or []):
            for attr in ('_cooldown_entry_time', '_replay_index'):
                try:
                    setattr(kline, attr, None)
                except Exception:                            # noqa: BLE001
                    pass
        # ⚠ 不要在这里调用 `strategy._strategy_init()`：
        #   元类把用户 `__init__` 改名成了 `_strategy_init`（见
        #   `StrategyMeta`），重跑它会再次 `get_kline()` —— 而 patched
        #   `get_kline` 在 cache 之后返回 None → `self.data = None` →
        #   策略在回放里直接崩掉 ✗（实测：reset 后 data/data1 都是 None）。
        #   指标对象在 prepare 时已经按**全量数据**算好了，`.new` 看的是
        #   `_btindex`，所以重置账户不需要重跑用户 __init__ ✓

    def step_one(self) -> bool:
        """回放**单根步进**：`_btindex` 前进一根 → 跑一次 `next()` ✓

        与 `replay()` 的区别：**不从头重放**，所以 minibt 内部的 broker /
        持仓 / 停止线状态是**连续的** —— 开仓在 bar k、平仓在 bar k+n，
        成交价自然不同（`replay()` 每次从 0 跑会让第 k 根又"刚开仓"，
        出现同价位开平、平仓盈亏恒为 0 ✗）

        回放推进用 `_replay_index` 对齐到**前端当前那根**（不是盲目 +1）：
        用户暂停 / 前进一根 / 从 30% 开始，策略都必须和图表同一根 ✓
        """
        if self.strategy is None:
            return False
        try:
            index = int(getattr(self, '_replay_index', -1)) + 1
            self._replay_index = index
            self.strategy._btindex = index
            self._call_index = 0
            self.strategy._in_next_context = True
            was_live = getattr(self.strategy, '_is_live_trading', False)
            self.strategy._is_live_trading = bool(self.live or was_live)
            try:
                self.strategy.step()
                self._update_stops()
            finally:
                self.strategy._is_live_trading = was_live
            return True
        except Exception as error:                               # noqa: BLE001
            self.error = f'第 {index} 根：{type(error).__name__}: {error}'
            return False

    # ---------------------------------------------------------- 结果
    def specs(self, plot_id: int = 0) -> list:
        """策略自带的指标线（`extract_minibt_indicators` ✓）"""
        if self.strategy is None:
            return []
        try:
            from minibt.strategy.realtime import extract_minibt_indicators
            return list(extract_minibt_indicators(self.strategy, plot_id) or [])
        except Exception as error:                               # noqa: BLE001
            self.error = f'提取指标失败：{error}'
            return []

    def signals(self, plot_id: int = 0) -> list:
        """策略的买卖信号（`extract_minibt_signals` ✓）"""
        if self.strategy is None:
            return []
        try:
            from minibt.strategy.realtime import extract_minibt_signals
            return list(extract_minibt_signals(self.strategy, plot_id) or [])
        except Exception as error:                               # noqa: BLE001
            self.error = f'提取信号失败：{error}'
            return []

    @property
    def ready(self) -> bool:
        return self.strategy is not None

    @property
    def kline_count(self) -> int:
        return len(getattr(self, '_klines_', None) or self._klines or [])

    def _wrap_target_size(self, kline) -> None:
        """包一层 `KLine.set_target_size`（目标手数 → 本地模拟账户 ✓）"""
        original = getattr(kline, 'set_target_size', None)
        if not callable(original):
            return
        runner = self

        def patched(size=None, *args, **kwargs):
            result = None
            try:
                result = original(size, *args, **kwargs)   # 先走原逻辑 ✓
            except Exception:                                # noqa: BLE001
                result = None
            try:
                target = float(size or 0)
            except (TypeError, ValueError):
                target = 0.0
            symbol = runner.source_of_kline(kline) or str(
                getattr(kline, 'symbol', '') or '')
            # ★ 记录**当前那根 K 线的时间**（replay 里 `len(kline.close)`
            #   是全长，用它定位价格会全部落到最后一根 ✗）
            runner.targets.append({
                'symbol': symbol, 'target': target,
                'index': int(getattr(runner, '_replay_index', -1)),
                'serial': runner._target_serial,
            })
            runner._target_serial += 1
            return result
        try:
            kline.set_target_size = patched
        except Exception:                                        # noqa: BLE001
            pass

    def source_of_kline(self, kline) -> str:
        """KLine 对象 → 数据源名字（CSV 名 / 合约代码 ✓）

        顺序与 `_klines` 一致：先 seed 的 N 条，再 `get_kline` 请求的 ✓
        """
        if kline is None:
            return ''
        klines = getattr(self, '_klines', None) or []
        for index, item in enumerate(klines):
            if item is kline:
                names = list(getattr(self, '_seed_order', None) or [])
                names += [str(request[0] or '')
                          for request in (getattr(self, '_requests', None) or [])]
                if index < len(names) and names[index]:
                    return str(names[index])
                break
        # seed 阶段 `_klines` 还没建好 → 直接在 seed 列表里找
        for index, item in enumerate(getattr(self, '_seed_klines', None) or []):
            if item is kline:
                order = getattr(self, '_seed_order', None) or []
                if index < len(order):
                    return str(order[index])
        return ''

    def _match_frame(self, frame) -> str:
        """把指标挂着的 K 线 DataFrame 对回**传入的 frame** → 数据源名字 ✓"""
        frames = getattr(self, '_frames', None) or []
        symbols = getattr(self, '_symbols', None) or []
        if frame is None:
            return ''
        for index, item in enumerate(frames):
            try:
                if len(item) != len(frame):
                    continue
                first_a = item['datetime'].iloc[0]
                first_b = frame['datetime'].iloc[0]
                last_a = item['datetime'].iloc[-1]
                last_b = frame['datetime'].iloc[-1]
                if first_a != first_b or last_a != last_b:
                    continue
                # ★ 两份数据的**时间范围可能完全一样**（同一时段的两个品种）
                #   → 再用收盘价几个采样点区分（长度 + 时间 + 价格三合一 ✓）
                sample = (0, len(item) // 2, len(item) - 1)
                close_a = [round(float(item['close'].iloc[i]), 6)
                           for i in sample]
                close_b = [round(float(frame['close'].iloc[i]), 6)
                           for i in sample]
                if close_a != close_b:
                    continue
                name = symbols[index] if index < len(symbols) else ''
                return str(name or '')
            except Exception:                                    # noqa: BLE001
                continue
        return ''

    def source_of(self, plot_id: int = 0) -> str:
        """第 `plot_id` 条 K 线**来自哪个数据源**（CSV 名 / 合约代码 ✓）

        ★ 策略里 `self.kline1 = self.get_kline(LocalDatas.a)` 会让同一个
        KLine 在 `_btklinedataset` 里出现多个别名（`kline1`/`kline`…），
        所以**不能**按名字下标猜 —— 直接拿指标挂的 `dataset.kline`
        和传入的 frame 比对（长度 + 首尾时间戳）✓
        """
        dataset = getattr(getattr(self, 'strategy', None),
                          '_btindicatordataset', None) or {}
        seeds_order = getattr(self, '_seed_order', None) or []
        has_requests = bool(getattr(self, '_requests', None))
        # ★ **写法 2**（`self.klines1.close.sma(...)`）：指标是**按注册顺序**
        #   落在 klines1 / klines2 … 上的（minibt 给的 `plot_id` 是内部编号，
        #   不是 K 线序号 → 不能直接用 ✗）。这里按"第 N 个指标数据集 →
        #   第 N 个 K 线"映射（test_3.py 实测正确 ✓）
        if seeds_order and not has_requests:
            order: List[Any] = []
            for _key, item in dataset.items():
                plot = getattr(item, 'plot_id', None)
                if plot is None or plot in order:
                    continue
                order.append(plot)
            if plot_id in order:
                position = order.index(plot_id)
                if position < len(seeds_order):
                    return str(seeds_order[position])
        for _key, item in dataset.items():
            try:
                if getattr(item, 'plot_id', None) != plot_id:
                    continue
                # ★ 指标挂在 KLine 上（`self.data.close.sma(...)`）：
                #   直接按 KLine 找回数据源，不能拿 KLine 当 DataFrame 比 ✗
                kline = getattr(item, 'kline', None)
                source = self.source_of_kline(kline)
                if source:
                    return source
                matched = self._match_frame(kline)
                if matched:
                    return matched
            except Exception:                                    # noqa: BLE001
                continue
        seeds = getattr(self, '_seed_klines', None) or []
        requests = getattr(self, '_requests', None) or []
        symbols = getattr(self, '_symbols', None) or []
        if plot_id < len(seeds):
            return str((symbols[plot_id] if plot_id < len(symbols) else '')
                       or getattr(self, 'symbol', '') or '')
        index = plot_id - len(seeds)
        if 0 <= index < len(requests):
            return str(requests[index][0] or '')
        return ''

    def plot_count(self) -> int:
        """策略里一共几条 K 线（`_btindicatordataset` 的 plot 最大编号 + 1 ✓）"""
        dataset = getattr(getattr(self, 'strategy', None),
                          '_btindicatordataset', None) or {}
        highest = -1
        for item in dataset.values():
            try:
                highest = max(highest, int(getattr(item, 'plot_id', -1)))
            except Exception:                                    # noqa: BLE001
                continue
        seeds = len(getattr(self, '_seed_klines', None) or [])
        requests = len(getattr(self, '_requests', None) or [])
        return max(1, highest + 1, seeds + requests)

    def frame(self, plot_id: int = 0):
        """第 `plot_id` 条 K 线对应的**真实 frame**（按数据源匹配 ✓）

        同一个 KLine 上的多个指标可能注册成 plot 3、4…，
        不能直接 `frames[plot_id]`（会越界后回退到**最后一个合约** ✗）。
        """
        frames = getattr(self, '_frames', None) or []
        if not frames:
            return None
        try:
            source = self.source_of(plot_id)
        except Exception:                                        # noqa: BLE001
            source = ''
        symbols = getattr(self, '_symbols', None) or []
        if source:
            for index, name in enumerate(symbols):
                if str(name) == str(source) and index < len(frames):
                    return frames[index]
            for index, name in enumerate(symbols):
                if name and _same_contract(str(name), str(source))                         and index < len(frames):
                    return frames[index]
        return frames[plot_id] if plot_id < len(frames) else frames[-1]

    def frame_at(self, index: int, plot_id: int = 0):
        """第 `plot_id` 条 K 线在 `index` 那根的数据（成交价用 ✓）"""
        frame = self.frame(plot_id)
        if frame is None or not len(frame):
            return None
        try:
            position = max(0, min(int(index), len(frame) - 1))
            return frame.iloc[position]
        except Exception:                                    # noqa: BLE001
            return None


def run(core_frame, cls, symbol: str = '', cycle: int = 60,
        params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """跑一遍策略 → `{'ok', 'items', 'error', 'name'}`（给 overlay 用 ✓）"""
    from . import strategy_overlay

    runner = StrategyRunner(cls, params=params, symbol=symbol, cycle=cycle)
    try:
        runner.prepare([core_frame], seed_kline=True)
        # ★ 逐根推进（`next()` 每根都跑）——「加到图表」也能看到成交 / 反手 ✓
        #   10000 根只跑最后 `replay_bars` 根，避免卡界面
        bars = int(getattr(cls, 'replay_bars', 0) or 0) or 500
        ok = runner.replay(core_frame, bars)
        if not ok:
            ok = runner.advance([core_frame])       # 兜底：至少算一次 ✓
    except StrategyRunError as error:
        return {'ok': False, 'items': [], 'error': str(error)}
    except Exception as error:                                   # noqa: BLE001
        return {'ok': False, 'items': [],
                'error': f'策略运行失败：{type(error).__name__}: {error}'}
    if not ok:
        return {'ok': False, 'items': [],
                'error': f'策略步进失败：{runner.error}'}
    return strategy_overlay.collect(runner, core_frame, cls)
