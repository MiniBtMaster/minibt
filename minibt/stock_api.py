# coding: utf-8
"""富途（Futu OpenD）股票行情 / 交易接口 —— 与 tqsdk ``TqApi`` **同形**。

minibt 的实盘链路只用到 ``TqApi`` 的一小部分方法，这里按**同样的签名**实现，
所以策略 / 实时图表代码一行都不用改：

```python
from minibt import *

bt = Bt(live=True)
bt.addStockapi()                     # 默认 127.0.0.1:11111（先启动 FutuOpenD）
# 或：bt.addStockapi(host='127.0.0.1', port=11111, trade=True, trd_env='SIMULATE')
bt.addstrategy(MyStrategy)
bt.run()                             # 实时图表 / 实盘

class MyStrategy(Strategy):
    def __init__(self):
        self.data = self.get_kline('SH.600000', 60, 300)   # 实时 K 线
    def next(self):
        if self.data.close.iloc[-1] > self.data.open.iloc[-1]:
            self.buy()                 # → StockTargetPosTask → insert_order
```

实现的接口（与 ``TqApi`` 对齐）：

| 方法 | 说明 |
| --- | --- |
| `get_kline_serial(symbol, duration_seconds, data_length)` | 实时 K 线（**同一个 DataFrame 原地滚动**，长度固定） |
| `get_tick_serial(symbol)` | 最新 tick（last_price / bid / ask / volume） |
| `get_quote(symbol)` | 报价对象（`price_tick` / `volume_multiple` / `trading_time`） |
| `wait_update(deadline=60)` | 轮询网关刷新（内部 `poll_interval` 秒） |
| `is_changing(obj)` | 上一拍该 DataFrame 有没有变 |
| `insert_order` / `cancel_order` / `get_order` | 交易（`trade=True` 走富途交易；否则**本地模拟成交**） |
| `get_position(symbol)` / `get_account()` | 持仓 / 账户 |
| `target_pos_task(symbol)` | → `StockTargetPosTask`（`set_target_volume`） |
| `close()` | 退订 + 关闭网关连接 |

``trade=False``（默认）时用**本地模拟盘**（按最新价立即成交），且
**默认持久化**到 ``~/.minibt/stock_sim.sqlite3``（关掉程序再打开还能读到
持仓/委托/成交/权益曲线）：

```python
api = StockApi()                       # sim_account='default' → 持久化
api.sim_trades() / api.sim_equity_curve() / api.sim_reset()
StockApi(sim_account=None)             # 纯内存（关程序即清空）
StockApi(sim_cash=200000, sim_commission=0.0003)
```

⚠️ 未启动 FutuOpenD / 连不上时**直接抛** ``RuntimeError``（不会静默返回空数据）。
"""

from __future__ import annotations

import socket
import time
from types import SimpleNamespace
from typing import Optional

import pandas as pd

#: 周期（秒）→ futu KLType（不支持的周期回退 K_1M ✓）
PERIOD_TO_KLTYPE = {
    60: 'K_1M', 180: 'K_3M', 300: 'K_5M', 900: 'K_15M',
    1800: 'K_30M', 3600: 'K_60M', 7200: 'K_120M',
    10800: 'K_180M', 14400: 'K_240M',
    86400: 'K_DAY', 604800: 'K_WEEK', 2419200: 'K_MON',
    7776000: 'K_QUARTER', 31536000: 'K_YEAR',
}

#: 各市场交易时段（给 ``TradeTimeFilter`` / 图表判开盘用 ✓）
MARKET_SESSIONS = {
    'SH': [['09:30:00', '11:30:00'], ['13:00:00', '15:00:00']],
    'SZ': [['09:30:00', '11:30:00'], ['13:00:00', '15:00:00']],
    'HK': [['09:30:00', '12:00:00'], ['13:00:00', '16:00:00']],
    'US': [['09:30:00', '16:00:00']],
}

KLINE_COLUMNS = ('datetime', 'open', 'high', 'low', 'close', 'volume')

#: 期货交易所前缀（股票接口要拒绝这些合约 ✓）
_FUTURES_EXCHANGES = {
    'SHFE', 'DCE', 'CZCE', 'CFFEX', 'INE', 'GFEX', 'KQD',
    'HKFE', 'CME', 'COMEX', 'NYMEX', 'CBOT', 'LME', 'SGX', 'OSE',
}


def futu_code(symbol: str) -> str:
    """股票代码 → futu 代码：``600000``→``SH.600000``、``00700``→``HK.00700``

    已带前缀（``SH.600000`` / ``HK.00700`` / ``US.AAPL``）原样返回；
    ``600000.SH`` 这种后缀写法也支持 ✓
    """
    text = str(symbol or '').strip().upper()
    if not text:
        return ''
    if '.' in text:
        left, right = text.split('.', 1)
        # ★ 天勤写法 `SSE.600007` / `SZSE.000001` 也要转成富途的 `SH.` / `SZ.`
        #   —— 以前原样返回 → 富途报
        #   `format of code SSE.600007 is wrong` → 订阅 K 线全失败 ✗
        #   （desk 的 `stocks.to_futu_code()` 早就做对了，这里漏了）
        _map = {'SSE': 'SH', 'SH': 'SH', 'SZSE': 'SZ', 'SZ': 'SZ',
                'HK': 'HK', 'US': 'US', 'BSE': 'SH'}
        if left in _map:
            return f'{_map[left]}.{right}'
        if right in ('SH', 'SZ', 'HK', 'US', 'SSE', 'SZSE'):
            return f'{_map.get(right, right)}.{left}'
        return text
    if text.isdigit():
        if len(text) == 5:
            return f'HK.{text}'
        if len(text) != 6:
            raise ValueError(f'无法识别的股票代码：{symbol!r}')
        return f'SH.{text}' if text[0] in '659' else f'SZ.{text}'
    return f'US.{text}'


class _Loop:
    """``TqObjs`` 会检查 ``api._loop.is_closed()`` —— 给个同形小对象 ✓"""

    def __init__(self) -> None:
        self.closed = False

    def is_closed(self) -> bool:
        return bool(self.closed)


class StockTargetPosTask:
    """``TargetPosTask`` 的股票版：``set_target_volume(n)`` → 差额下单 ✓"""

    def __init__(self, api: 'StockApi', symbol: str) -> None:
        self.api = api
        self.symbol = symbol

    def set_target_volume(self, volume: int) -> None:
        target = int(volume)
        current = int(self.api._net_position(self.symbol))
        delta = target - current
        if delta == 0:
            return
        direction = 'BUY' if delta > 0 else 'SELL'
        # 同向加仓 → OPEN；反向 / 减仓 → CLOSE
        offset = 'OPEN' if (current == 0 or (current > 0) == (delta > 0)) \
            else 'CLOSE'
        # ★ 股票按**股数**下单：一次把差额全下（不要 1 股 1 单 ✗）
        self.api.insert_order(self.symbol, direction, offset, abs(delta))
        print(f'[StockApi] {self.symbol} 目标仓位 {target}：'
              f'{direction} {abs(delta)} 股（{offset}）')


class StockApi:
    """富途股票行情 / 交易接口（与 tqsdk ``TqApi`` 同形 ✓）"""

    def __init__(self, host: str = '127.0.0.1', port: int = 11111,
                 *, trade: bool = False, trd_env: str = 'SIMULATE',
                 trd_market: str = 'HK', security_firm: str = 'FUTUSECURITIES',
                 timeout: int = 8, poll_interval: float = 0.2,
                 adjust_type: str = 'none',
                 sim_account: str | None = 'default',
                 sim_cash: float = 100000.0,
                 sim_commission: float = 0.0,
                 sim_db: str | None = None) -> None:
        """
        Args:
            host / port: FutuOpenD 网关（默认 ``127.0.0.1:11111``）
            trade: 是否连接**交易**（False = 只行情；下单走本地模拟成交）
            trd_env: ``'SIMULATE'``（模拟盘）/ ``'REAL'``（实盘）
            trd_market: ``'HK'`` / ``'US'`` / ``'CN'``（交易市场）
            security_firm: 券商标识（默认 ``FUTUSECURITIES``）
            timeout: 端口探测超时（秒）
            poll_interval: ``wait_update`` 的轮询间隔（秒）
            adjust_type: ``'none'``（默认，**不复权**：实盘价格与快照一致）
                / ``'qfq'`` 前复权 / ``'hfq'`` 后复权（仅回测用）
            sim_account: 本地模拟盘账户名（**默认 'default' = 持久化**；
                传 ``None`` 则纯内存、关程序即清空）
            sim_cash: 模拟盘初始资金（默认 10 万；仅首次创建该账户时生效）
            sim_commission: 模拟盘手续费率（默认 0；如 0.0003 = 万三）
            sim_db: 模拟盘 sqlite 路径（默认 ``~/.minibt/stock_sim.sqlite3``）
        """
        import os

        # ★ 兼容仓库里附带的旧版 futu（10.02，旧 protoc）：**必须在 import futu
        #   之前**设好环境变量（用 importlib.metadata 查版本，不 import protobuf
        #   否则会先把 cpp 实现锁死 ✗）——同 base.py 的处理 ✓
        if not os.environ.get('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'):
            try:
                import importlib.metadata as _metadata
                parts = [int(x) for x in
                         _metadata.version('protobuf').split('.')[:2]]
                if parts and (parts[0] > 3 or
                              (parts[0] == 3 and parts[1] >= 21)):
                    os.environ[
                        'PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'
            except Exception:                                    # noqa: BLE001
                pass

        try:
            import futu
            from futu import (AuType, KLType, OpenQuoteContext, RET_OK,
                              SubType, SysConfig)
        except ImportError as error:                             # noqa: BLE001
            raise ImportError(
                '未安装 futu-api：请先 pip install futu-api，并启动 FutuOpenD'
                '（富途 OpenAPI 网关，默认 127.0.0.1:11111）'
            ) from error

        # ① 先探端口：OpenD 没启动时给**看得懂**的提示 ✓
        try:
            with socket.create_connection((host, int(port)),
                                          timeout=int(timeout)):
                pass
        except OSError as error:
            raise RuntimeError(
                f'未检测到 FutuOpenD 网关（{host}:{port}）：{error}。\n'
                '请先启动并登录 FutuOpenD（富途 OpenAPI），再调用 '
                'Bt.addStockapi()。'
            ) from error

        self.host, self.port = host, int(port)
        self.poll_interval = max(0.05, float(poll_interval or 0.2))
        self._futu = futu
        self._KLType, self._SubType = KLType, SubType
        self._RET_OK, self._AuType = RET_OK, AuType
        self._adjust = {'none': AuType.NONE, 'hfq': AuType.HFQ}.get(
            str(adjust_type or 'qfq').lower(), AuType.QFQ)

        self._loop = _Loop()
        self._closed = False
        self._frames: dict = {}        # (code, period) -> DataFrame（原地滚动）
        self._changed: set = set()     # 上一拍变了的 key
        self._subs: set = set()        # 已订阅 (code, ktype)
        self._ticks: dict = {}         # code -> SimpleNamespace
        self._quotes: dict = {}        # code -> SimpleNamespace
        self._prices: dict = {}        # code -> 最新价
        self._orders: list = []        # 本地委托记录（_get_order 用）
        self._trades: list = []        # 本地成交记录（get_trade 用 ✓）
        self._positions: dict = {}     # code -> {'long': n, 'short': n, 'avg_*': p}
        self._position_objs: dict = {}  # code -> SimpleNamespace（原地更新 ✓）
        self._account = SimpleNamespace(
            balance=0.0, available=0.0, margin=0.0, float_profit=0.0,
            position_profit=0.0, close_profit=0.0, commission=0.0,
            risk_ratio=0.0)
        self._trade_enabled = bool(trade)
        #: 当前交易市场（HK / US / CN / JP；富途每个市场有独立模拟账户 ✓）
        self.trd_market = str(trd_market or 'HK').upper()
        self._trd = None
        #: 本地模拟盘（sqlite 持久化；None = 纯内存）
        self._sim = None
        self._sim_commission = max(0.0, float(sim_commission or 0.0))
        self._cash = 0.0
        self._realized_pnl = 0.0
        self._commission = 0.0
        self._market_value = 0.0
        self._last_equity_at = 0.0
        self._trade_seq = 0

        try:
            SysConfig.set_all_thread_daemon(True)
        except Exception:                                        # noqa: BLE001
            pass
        self._ctx = OpenQuoteContext(host=host, port=self.port)
        self._last_quote_at = 0.0
        self._quote_tick = 0

        if self._trade_enabled:
            self._open_trade(trd_env, trd_market, security_firm)
        else:
            print('[StockApi] 只连接行情（未开启交易）：策略下单走**本地模拟成交**；'
                  '真实交易请传 trade=True, trd_env="SIMULATE"/"REAL"')
            if sim_account is not None:
                self._load_sim(str(sim_account), float(sim_cash or 100000.0),
                               sim_db)
            else:
                self._cash = float(sim_cash or 100000.0)
                self._update_account_from_ledger()
                print('[StockApi] 模拟盘为**纯内存**（sim_account=None）：'
                      '关掉程序后持仓/委托/权益都会清空')

    # ---------------------------------------------------------------- 交易连接
    def _open_trade(self, trd_env: str, trd_market: str,
                    security_firm: str) -> None:
        try:
            from futu import OpenSecTradeContext, SecurityFirm, TrdEnv, TrdMarket
            firm = getattr(SecurityFirm, str(security_firm).upper(),
                           SecurityFirm.FUTUSECURITIES)
            env = getattr(TrdEnv, str(trd_env).upper(), TrdEnv.SIMULATE)
            market = getattr(TrdMarket, str(trd_market).upper(),
                             TrdMarket.HK)
            self._trd = OpenSecTradeContext(filter_trdmarket=market,
                                            host=self.host, port=self.port,
                                            security_firm=firm)
            self._trd_env = env
            self.trd_market = str(trd_market or 'HK').upper()
            print(f'[StockApi] 交易已连接（{trd_env} / {trd_market} / '
                  f'{security_firm}）')
        except Exception as error:                               # noqa: BLE001
            self._trd = None
            self._trade_enabled = False
            print(f'[StockApi] 交易连接失败（已降级为模拟成交）：{error}')

    # ---------------------------------------------------------------- 行情
    def subscribe_quote(self, code: str, period=60) -> None:
        """公开的订阅入口（订阅池调用 ✓）"""
        try:
            self._subscribe(str(code or '').upper(), period)
        except Exception:                                        # noqa: BLE001
            pass

    def unsubscribe_all(self, code: str) -> int:
        """退订这个代码的**所有**周期（池子对账用 ✓）

        ⚠ 只退 `K_1M` 是不够的：打开过图表的代码还订着 `K_DAY`，
        富途客户端里那些订阅会一直留着（用户实测：客户端 51 vs 我们 33 ✗）
        """
        target = str(code or '').upper()
        subs = getattr(self, '_subs', None)
        if not isinstance(subs, set):
            return 0
        kinds = [name for (item, name) in list(subs) if item == target]
        removed = 0
        for name in kinds:
            try:
                kind = getattr(self._SubType, name, None)
                if kind is not None:
                    ret, data = self._ctx.unsubscribe([target], [kind])
                    if ret != self._RET_OK:
                        # 退订失败要能看到原因（额度对不上时就是这里 ✗）
                        print(f'[StockApi] 退订失败 {target} {name}: {data}',
                              flush=True)
                    else:
                        removed += 1
            except Exception as error:                           # noqa: BLE001
                print(f'[StockApi] 退订异常 {target} {name}: {error!r}',
                      flush=True)
            subs.discard((target, name))
        try:
            for key in [key for key in self._frames if key[0] == target]:
                self._frames.pop(key, None)
        except Exception:                                        # noqa: BLE001
            pass
        return removed

    def unsubscribe_quote(self, code: str, period=60) -> None:
        """退订（池子里没人用了才调用 ✓）"""
        name = self._ktype_name(period)
        target = str(code or '').upper()
        if (target, name) not in getattr(self, '_subs', set()):
            return
        try:
            kind = getattr(self._SubType, name, None)
            if kind is not None:
                self._ctx.unsubscribe([target], [kind])
        except Exception:                                        # noqa: BLE001
            pass
        try:
            self._subs.discard((target, name))
            self._frames.pop((target, int(period or 60)), None)
        except Exception:                                        # noqa: BLE001
            pass

    @staticmethod
    def _ktype_name(period) -> str:
        return PERIOD_TO_KLTYPE.get(int(period or 60), 'K_1M')

    def _ktype(self, period):
        return getattr(self._KLType, self._ktype_name(period))

    def _subscribe(self, code: str, period) -> None:
        name = self._ktype_name(period)
        subtype = getattr(self._SubType, name, None)
        if subtype is None or (code, name) in self._subs:
            return
        try:
            ret, data = self._ctx.subscribe([code], [subtype])
            if ret == self._RET_OK:
                self._subs.add((code, name))
            else:
                print(f'[StockApi] 订阅失败 {code} {name}: {data}')
        except Exception as error:                               # noqa: BLE001
            print(f'[StockApi] 订阅异常 {code} {name}: {error}')

    @staticmethod
    def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
        """futu K 线 → minibt 需要的 6 列（``datetime`` = **纳秒整数** ✓）"""
        out = pd.DataFrame({
            'datetime': pd.to_datetime(frame['time_key']).astype('int64'),
            'open': pd.to_numeric(frame['open'], errors='coerce'),
            'high': pd.to_numeric(frame['high'], errors='coerce'),
            'low': pd.to_numeric(frame['low'], errors='coerce'),
            'close': pd.to_numeric(frame['close'], errors='coerce'),
            'volume': pd.to_numeric(frame['volume'],
                                    errors='coerce').fillna(0.0),
        })
        return out.astype({'open': 'float64', 'high': 'float64',
                           'low': 'float64', 'close': 'float64',
                           'volume': 'float64'}).reset_index(drop=True)

    def _fetch_history(self, code: str, ktype, wanted: int, period: int):
        """历史 K 线（**必须显式传 start/end**：futu 默认只给“一年前”那一段 ✗）"""
        from datetime import datetime, timedelta

        per_day = {60: 240, 180: 80, 300: 48, 900: 16, 1800: 8, 3600: 4,
                   7200: 2, 10800: 1.5, 14400: 1, 86400: 1, 604800: 0.2,
                   2419200: 0.05}
        rate = max(float(per_day.get(int(period), 1)), 0.01)
        days = int(max(20, min(int(wanted / rate) * 2 + 20, 3650)))
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        try:
            ret, data, _page = self._ctx.request_history_kline(
                code, start=start, end=end, ktype=ktype, autype=self._adjust,
                max_count=None)
        except Exception:                                        # noqa: BLE001
            return None
        if ret != self._RET_OK or data is None or data.empty:
            return None
        return self._normalize(data)

    def _fetch_cur(self, code: str, ktype, num: int):
        try:
            ret, data = self._ctx.get_cur_kline(
                code, int(max(1, min(int(num), 1000))), ktype, self._adjust)
        except Exception:                                        # noqa: BLE001
            return None
        if ret != self._RET_OK or data is None or data.empty:
            return None
        return self._normalize(data)

    def history_bars(self, symbol: str, period: int = 86400,
                     count: int = 120):
        """拿历史 K 线但**不订阅**（迷你走势图用 ✓）

        富途正股订阅额度只有 100，为几十只可见股票订阅会立刻爆掉；
        而 `request_history_kline` 走的是**历史额度**（100 只 / 7 天滚动），
        用来画 spark 完全够用 ✓
        """
        code = futu_code(symbol)
        if not code:
            return None
        try:
            frame = self._fetch_history(
                code, self._ktype(period), max(30, min(int(count), 1000)),
                int(period or 86400))
        except Exception:                                        # noqa: BLE001
            return None
        if frame is None or getattr(frame, 'empty', True):
            return None
        return frame

    def get_kline_serial(self, symbol: str, duration_seconds: int = 60,
                         data_length: int = 300, *args, **kwargs):
        """实时 K 线（**同一个 DataFrame 原地滚动**，长度固定 ✓）"""
        code = futu_code(symbol)
        period = int(duration_seconds or 60)
        key = (code, period)
        frame = self._frames.get(key)
        if frame is not None:
            return frame
        self._subscribe(code, period)
        ktype = self._ktype(period)
        # ⚠ desk 的 `chart_history` 可能是几万 → 富途历史接口直接不给数据 ✗
        #   截到 2000（1 分钟 ≈ 8 个交易日，够看；再多就要分页+额度）
        wanted = max(30, min(int(data_length or 300), 2000))
        # ★ 优先 ``get_cur_kline``（**实时、不耗历史额度**）：刚订阅时可能只回
        #   一部分 → 重试几次（与 miniqt 的 stock_api 同一套经验 ✓）
        fetch_n = min(wanted, 1000)
        data = None
        for _attempt in range(3):
            data = self._fetch_cur(code, ktype, fetch_n)
            if data is not None and len(data) >= min(fetch_n, 60):
                break
            time.sleep(0.15)
        # ★ 只有「要 >1000 根」才回补历史 → 设置里 `chart_data_length` 是
        #   300 时永远只拿到当天几十根（用户反馈"股票数据长度太短"✗）
        #   现在：不够 `wanted` 就回补一次历史（有额度限制，失败就算了）
        short = data is None or data.empty or len(data) < wanted
        if short and wanted > 30:
            try:
                history = self._fetch_history(code, ktype, wanted, period)
            except Exception:                                    # noqa: BLE001
                history = None
            if history is not None and not history.empty:
                if data is None or data.empty:
                    data = history
                elif len(history) > len(data):
                    data = history
        if data is None or data.empty:
            raise RuntimeError(
                f'富途未返回 {code} {self._ktype_name(period)} 的 K 线：\n'
                '请检查 ① 代码是否正确 ② 是否开通该市场行情 ③ 历史 K 线额度'
                '（股票 100 只 / 7 天滚动）。')
        if len(data) > wanted:
            data = data.tail(wanted).reset_index(drop=True)
        # ★ minibt 的 ``KLine`` 要求 ``FILED.Quote`` 列（symbol/duration/
        #   price_tick/volume_multiple）；tqsdk 自带，futu 这里手动补上 ✓
        quote = self.get_quote(code)
        data['symbol'] = code
        data['duration'] = period
        data['price_tick'] = float(
            getattr(quote, 'price_tick', 0.01) or 0.01)
        data['volume_multiple'] = float(
            getattr(quote, 'volume_multiple', 1.0) or 1.0)
        self._frames[key] = data
        self._prices[code] = float(data['close'].iloc[-1])
        return data

    def get_tick_serial(self, symbol: str, *args, **kwargs):
        code = futu_code(symbol)
        tick = self._ticks.get(code)
        if tick is None:
            price = self._last_price(code)
            tick = SimpleNamespace(
                symbol=code, last_price=price, bid_price1=price,
                ask_price1=price, bid_volume1=0, ask_volume1=0, volume=0,
                datetime=0)
            self._ticks[code] = tick
        return tick

    def get_quote(self, symbol: str, *args, **kwargs):
        code = futu_code(symbol)
        quote = self._quotes.get(code)
        if quote is None:
            quote = SimpleNamespace(
                symbol=code, last_price=self._last_price(code),
                price_tick=0.01, volume_multiple=1.0,
                trading_time=SimpleNamespace(
                    day=[list(x) for x in MARKET_SESSIONS.get(
                        code.split('.')[0], MARKET_SESSIONS['SH'])],
                    night=[]))
            self._quotes[code] = quote
            self._refresh_quote(code)
        return quote

    def _last_price(self, code: str) -> float:
        price = self._prices.get(code)
        return float(price) if price else 0.0

    def _refresh_quote(self, code: str) -> None:
        quote = self._quotes.get(code)
        if quote is None:
            return
        try:
            ret, snap = self._ctx.get_market_snapshot([code])
        except Exception:                                        # noqa: BLE001
            return
        if ret != self._RET_OK or snap is None or snap.empty:
            return
        row = snap.iloc[0]
        try:
            quote.last_price = float(row.get('last_price') or 0.0)
        except (TypeError, ValueError):
            pass
        try:
            spread = float(row.get('price_spread') or 0.0)
            if spread > 0:
                quote.price_tick = spread
        except (TypeError, ValueError):
            pass
        self._prices[code] = quote.last_price
        tick = self._ticks.get(code)
        if tick is not None:
            tick.last_price = quote.last_price
            tick.bid_price1 = float(row.get('bid_price') or 0.0)
            tick.ask_price1 = float(row.get('ask_price') or 0.0)
            tick.bid_volume1 = float(row.get('bid_vol') or 0.0)
            tick.ask_volume1 = float(row.get('ask_vol') or 0.0)
            tick.volume = float(row.get('volume') or 0.0)

    # ---------------------------------------------------------------- 刷新
    @staticmethod
    def _fingerprint(frame: pd.DataFrame):
        if frame is None or frame.empty:
            return None
        last = frame.iloc[-1]
        return (int(last['datetime']), float(last['close']),
                float(last['high']), float(last['low']),
                float(last['volume']))

    def _refresh(self) -> None:
        for (code, period), frame in list(self._frames.items()):
            if frame.empty:
                continue
            new = self._fetch_cur(code, self._ktype(period), len(frame))
            if new is None or new.empty:
                continue
            before = self._fingerprint(frame)
            tail = new.tail(len(frame))
            n = min(len(frame), len(tail))
            if n <= 0:
                continue
            # ⚠ 只覆盖 6 个 K 线列：frame 还有 symbol/duration/price_tick/
            #   volume_multiple 四列（KLine 要求），整行赋值会长度不匹配 ✗
            index = frame.index[-n:]
            tail = tail.iloc[-n:].reset_index(drop=True)
            frame.loc[index, 'datetime'] = tail['datetime'].to_numpy(
                dtype='int64')
            for column in ('open', 'high', 'low', 'close', 'volume'):
                frame.loc[index, column] = tail[column].to_numpy(
                    dtype='float64')
            if self._fingerprint(frame) != before:
                self._changed.add((code, period))
                self._prices[code] = float(frame['close'].iloc[-1])
                tick = self._ticks.get(code)
                if tick is not None:
                    tick.last_price = self._prices[code]
                    tick.datetime = int(frame['datetime'].iloc[-1])
        # 报价（买卖盘 / price_tick）每秒刷一次即可 ✓
        self._quote_tick += 1
        if self._quote_tick % max(1, int(1.0 / self.poll_interval)) == 0:
            for code in list(self._quotes):
                self._refresh_quote(code)
        if self._trd is not None:
            self._refresh_account()
            self._refresh_real_orders()
            self._refresh_real_trades()
        elif self._sim is not None and self._prices:
            now = time.time()
            if now - self._last_equity_at >= 5.0:
                self._last_equity_at = now
                self._save_equity()

    def wait_update(self, deadline: float = 60, *args, **kwargs) -> bool:
        """轮询刷新（``deadline`` 是最大等待秒数，内部按 ``poll_interval`` 轮询 ✓）"""
        if self._closed:
            return False
        try:
            wait = float(deadline)
        except (TypeError, ValueError):
            wait = 1.0
        if wait <= 0:
            wait = self.poll_interval
        time.sleep(max(0.02, min(wait, self.poll_interval)))
        self._changed.clear()
        self._refresh()
        return True

    def is_changing(self, obj=None, key=None) -> bool:
        """上一拍 ``wait_update`` 里 ``obj``（某个 K 线 DataFrame）变了吗 ✓"""
        if obj is None:
            return bool(self._changed)
        for frame_key, frame in self._frames.items():
            if frame is obj:
                return frame_key in self._changed
        return True

    # ---------------------------------------------------------------- 交易
    # ---------------------------------------------------------------- 模拟盘
    def _load_sim(self, key: str, initial_cash: float,
                  db_path=None) -> None:
        """打开/创建本地模拟盘（sqlite）并**恢复**持仓、委托、现金 ✓"""
        try:
            from .sim_account import StockSimStore
            store = StockSimStore(key, db_path=db_path,
                                  initial_cash=initial_cash)
        except Exception as error:                               # noqa: BLE001
            print(f'[StockApi] 模拟盘持久化不可用（{error}）→ 纯内存')
            self._cash = float(initial_cash)
            self._update_account_from_ledger()
            return
        self._sim = store
        account = store.load_account()
        self._cash = float(account['cash'])
        self._realized_pnl = float(account['realized_pnl'])
        self._commission = float(account['commission'])
        self._positions.update(store.load_positions())
        self._orders = [
            SimpleNamespace(
                order_id=item['order_id'], instrument_id=item['code'],
                direction=item['direction'], offset=item['offset'],
                volume=item['qty'], limit_price=item['price'],
                status=item['status'], volume_orign=item['qty'])
            for item in store.recent_orders(200)]
        self._trades = [
            SimpleNamespace(
                trade_id=item['trade_id'], order_id=item['order_id'],
                instrument_id=item['code'], direction=item['direction'],
                offset=item['offset'], price=item['price'],
                volume=item['qty'], realized_pnl=item['realized_pnl'],
                trade_date_time=item['created_at'])
            for item in store.recent_trades(500)]
        self._update_account_from_ledger()
        holding = sum(1 for book in self._positions.values()
                      if book.get('long') or book.get('short'))
        print(f'[StockApi] 本地模拟盘已加载：{store.path}')
        print(f'           账户 {key} | 现金 {self._cash:,.2f} | '
              f'持仓 {holding} | 委托 {len(self._orders)}')

    def _update_account_from_ledger(self) -> None:
        """按「现金 + 市值」重算账户（paper 模式；真实交易时被富途覆盖 ✓）"""
        market_value = 0.0
        float_profit = 0.0
        for code, book in self._positions.items():
            long_qty = float(book.get('long') or 0.0)
            short_qty = float(book.get('short') or 0.0)
            if not (long_qty or short_qty):
                continue
            avg_long = float(book.get('avg_long') or 0.0)
            avg_short = float(book.get('avg_short') or 0.0)
            price = self._last_price(code) or avg_long or avg_short
            market_value += (long_qty - short_qty) * price
            if long_qty:
                float_profit += (price - avg_long) * long_qty
            if short_qty:
                float_profit += (avg_short - price) * short_qty
        self._market_value = float(market_value)
        self._account.available = float(self._cash)
        self._account.float_profit = float(float_profit)
        self._account.position_profit = float(float_profit)
        self._account.close_profit = float(self._realized_pnl)
        self._account.commission = float(self._commission)
        self._account.market_value = float(market_value)
        self._account.risk_ratio = 0.0
        self._account.balance = float(self._cash + market_value)

    def _save_equity(self) -> None:
        """记一条权益曲线点（同一秒覆盖 ✓）"""
        if self._sim is None:
            return
        try:
            self._update_account_from_ledger()
            self._sim.add_equity(self._cash, self._market_value,
                                 self._account.balance,
                                 self._account.float_profit,
                                 self._realized_pnl)
        except Exception:                                        # noqa: BLE001
            pass

    # ---------------------------------------------------------------- 模拟盘查询
    def sim_equity_curve(self, limit: int = 1000) -> list:
        """权益曲线 ``[{ts, balance, cash, market_value, float_profit, realized_pnl}]``"""
        return self._sim.equity_curve(limit) if self._sim is not None else []

    def sim_trades(self, limit: int = 200) -> list:
        """成交历史（含已实现盈亏 ✓）"""
        return self._sim.recent_trades(limit) if self._sim is not None else []

    def sim_reset(self, initial_cash: float | None = None) -> None:
        """清空本地模拟盘（持仓 / 委托 / 成交 / 权益）→ 回到初始资金 ✓"""
        if self._sim is None:
            print('[StockApi] 当前是纯内存模拟盘（sim_account=None），直接重建即可')
            return
        self._sim.reset(initial_cash)
        self._positions.clear()
        self._position_objs.clear()
        self._orders.clear()
        self._trades.clear()
        account = self._sim.load_account()
        self._cash = float(account['cash'])
        self._realized_pnl = 0.0
        self._commission = 0.0
        self._update_account_from_ledger()
        print(f'[StockApi] 模拟盘已重置：现金 {self._cash:,.2f}')

    def _ledger(self, code: str) -> dict:
        return self._positions.setdefault(
            code, {'long': 0, 'short': 0, 'avg_long': 0.0, 'avg_short': 0.0})

    def _net_position(self, symbol: str) -> float:
        book = self._ledger(futu_code(symbol))
        return float(book['long']) - float(book['short'])

    def get_position(self, symbol: Optional[str] = None, account=None,
                     *args, **kwargs):
        """持仓（有交易连接 → 富途真实持仓；否则本地记账 ✓）

        ★ 返回的是**同一个对象**（原地刷新）：minibt 的实盘循环会反复读
          ``position.pos`` / ``float_profit``，不能每次新建 ✓
        """
        code = futu_code(symbol) if symbol else ''
        position = self._position_objs.get(code)
        if position is None:
            position = SimpleNamespace(
                symbol=code, instrument_id=code, pos=0,
                pos_long=0.0, pos_short=0.0,
                float_profit=0.0, position_profit=0.0, open_price=0.0,
                open_price_long=0.0, open_price_short=0.0)
            self._position_objs[code] = position
        if self._trd is not None:
            try:
                ret, data = self._trd.position_list_query(code=code or '', **(
                    {'trd_env': self._trd_env} if hasattr(self, '_trd_env')
                    else {}))
                if ret == self._RET_OK and data is not None:
                    self._sync_positions_from_futu(data)
            except Exception:                                    # noqa: BLE001
                pass
        self._update_position(code, position)
        return position

    def _update_position(self, code: str, position) -> None:
        """把本地账本 + 最新价 → 持仓对象的字段（原对象上改 ✓）"""
        book = self._ledger(code)
        price = self._last_price(code)
        long_qty = float(book['long'])
        short_qty = float(book['short'])
        position.pos = int(long_qty) - int(short_qty)
        position.pos_long = long_qty
        position.pos_short = short_qty
        position.open_price_long = float(book['avg_long'])
        position.open_price_short = float(book['avg_short'])
        position.open_price = position.open_price_long or             position.open_price_short
        profit = 0.0
        if long_qty and price:
            profit += (price - float(book['avg_long'])) * long_qty
        if short_qty and price:
            profit += (float(book['avg_short']) - price) * short_qty
        position.float_profit = float(profit)
        position.position_profit = float(profit)

    def _sync_positions_from_futu(self, data: pd.DataFrame) -> None:
        try:
            for _i, row in data.iterrows():
                code = str(row.get('code') or '')
                if not code:
                    continue
                long_qty = float(row.get('qty') or 0.0) if str(
                    row.get('position_side') or '').upper() in ('LONG', '') \
                    else 0.0
                short_qty = float(row.get('qty') or 0.0) if str(
                    row.get('position_side') or '').upper() == 'SHORT' else 0.0
                book = self._ledger(code)
                if long_qty or short_qty:
                    book['long'], book['short'] = long_qty, short_qty
                    book['avg_long'] = float(row.get('cost_price') or 0.0)
                    book['avg_short'] = float(row.get('cost_price') or 0.0)
        except Exception:                                        # noqa: BLE001
            pass

    def _refresh_account(self) -> None:
        try:
            ret, data = self._trd.accinfo_query(**(
                {'trd_env': self._trd_env} if hasattr(self, '_trd_env') else {}))
            if ret == self._RET_OK and data is not None and not data.empty:
                row = data.iloc[0]
                self._account.balance = float(row.get('total_assets') or 0.0)
                self._account.available = float(row.get('cash') or 0.0)
                self._account.float_profit = float(
                    row.get('unrealized_pl') or 0.0)
        except Exception:                                        # noqa: BLE001
            pass

    def _refresh_real_orders(self) -> None:
        """真实委托状态轮询（SUBMITTED → ALIVE / FINISHED / CANCELLED）"""
        if self._trd is None:
            return
        try:
            kwargs = ({'trd_env': self._trd_env}
                      if hasattr(self, '_trd_env') else {})
            ret, data = self._trd.order_list_query(**kwargs)
            if ret != self._RET_OK or data is None or data.empty:
                return
            mapping = {
                'FILLED_ALL': 'FINISHED', 'FILLED': 'FINISHED',
                'FILLED_PART': 'ALIVE', 'SUBMITTED': 'ALIVE',
                'SUBMITTING': 'ALIVE', 'WAITING_SUBMIT': 'ALIVE',
                'CANCELLED_ALL': 'CANCELLED', 'CANCELLED_PART': 'CANCELLED',
                'CANCELLED': 'CANCELLED', 'FAILED': 'REJECTED',
                'DISABLED': 'REJECTED', 'DELETED': 'CANCELLED',
            }
            for _, row in data.iterrows():
                oid = str(row.get('order_id') or '')
                if not oid:
                    continue
                status_raw = str(row.get('order_status')
                                 or row.get('status') or '').upper()
                status = mapping.get(status_raw, status_raw or 'ALIVE')
                qty = int(float(row.get('qty') or row.get('order_qty') or 0))
                dealt = int(float(row.get('dealt_qty') or 0))
                left = max(0, qty - dealt)
                current = next((item for item in self._orders
                                if str(getattr(item, 'order_id', '')) == oid),
                               None)
                if current is None:
                    current = SimpleNamespace(
                        order_id=oid,
                        instrument_id=str(row.get('code') or ''),
                        direction=str(row.get('trd_side') or ''),
                        offset=str(row.get('trd_side') or ''),
                        volume=qty, volume_orign=qty, volume_left=left,
                        limit_price=float(row.get('price') or 0.0),
                        last_price=float(row.get('dealt_avg_price') or 0.0),
                        status=status)
                    self._orders.append(current)
                else:
                    current.status = status
                    current.volume_left = left
                    current.last_price = float(
                        row.get('dealt_avg_price') or current.last_price)
        except Exception:                                        # noqa: BLE001
            pass

    def _refresh_real_trades(self) -> None:
        """真实成交轮询（成交记录从 Futu deal_list_query 来）"""
        if self._trd is None:
            return
        try:
            kwargs = ({'trd_env': self._trd_env}
                      if hasattr(self, '_trd_env') else {})
            ret, data = self._trd.deal_list_query(**kwargs)
            if ret != self._RET_OK or data is None or data.empty:
                return
            known = {str(getattr(item, 'trade_id', ''))
                     for item in self._trades}
            for _, row in data.iterrows():
                tid = str(row.get('deal_id') or row.get('trade_id') or '')
                if not tid or tid in known:
                    continue
                self._trades.append(SimpleNamespace(
                    trade_id=tid, order_id=str(row.get('order_id') or ''),
                    instrument_id=str(row.get('code') or ''),
                    direction=str(row.get('trd_side') or ''),
                    offset=str(row.get('trd_side') or ''),
                    price=float(row.get('price') or 0.0),
                    volume=float(row.get('qty') or row.get('dealt_qty') or 0.0),
                    realized_pnl=0.0,
                    trade_date_time=str(row.get('create_time') or '')))
                known.add(tid)
        except Exception:                                        # noqa: BLE001
            pass

    def get_account(self, account=None, *args, **kwargs):
        if self._trd is not None:
            self._refresh_account()
        else:
            self._update_account_from_ledger()
        return self._account

    def get_trade(self, trade_id: Optional[str] = None, account=None,
                  *args, **kwargs):
        """成交记录（持久化用户重启后也在 ✓；与 tqsdk ``get_trade`` 同形）"""
        if self._trd is not None:
            self._refresh_real_trades()
        if trade_id is None:
            return list(self._trades)
        return next((t for t in self._trades
                     if str(getattr(t, 'trade_id', '')) == str(trade_id)), None)

    def get_position_list(self, account=None, *args, **kwargs):
        """有持仓的合约列表（给「账户总览」计数用 ✓）"""
        result = []
        for code, book in self._positions.items():
            if not (book.get('long') or book.get('short')):
                continue
            result.append(self.get_position(code))
        return result

    def get_order(self, order_id: Optional[str] = None, account=None,
                  *args, **kwargs):
        if self._trd is not None:
            self._refresh_real_orders()
        if order_id is None:
            return list(self._orders)
        return next((o for o in self._orders
                     if str(getattr(o, 'order_id', '')) == str(order_id)), None)

    def cancel_order(self, order_or_order_id, account=None, *args, **kwargs):
        order_id = str(getattr(order_or_order_id, 'order_id',
                               order_or_order_id))
        if self._trd is not None:
            try:
                result = self._trd.modify_order(
                    modify_order_op=self._futu.ModifyOrderOp.CANCEL,
                    order_id=order_id, qty=0, price=0,
                    **({'trd_env': self._trd_env}
                       if hasattr(self, '_trd_env') else {}))
                # 富途返回 (ret, data)；失败时不要本地标 CANCELLED ✓
                if isinstance(result, tuple) and result:
                    ret = result[0]
                    if ret != self._RET_OK:
                        detail = result[1] if len(result) > 1 else result
                        raise RuntimeError(str(detail))
            except Exception as error:                           # noqa: BLE001
                print(f'[StockApi] 撤单失败 {order_id}: {error}', flush=True)
                raise RuntimeError(f'富途撤单失败 {order_id}: {error}')                     from error
        for order in self._orders:
            if str(getattr(order, 'order_id', '')) == order_id:
                order.status = 'CANCELLED'
        if self._sim is not None:
            try:
                self._sim.update_order(order_id, 'CANCELLED')
            except Exception:                                    # noqa: BLE001
                pass

    @staticmethod
    def _market_of_code(code: str) -> str:
        head = str(code or '').upper().split('.')[0]
        return {'SH': 'CN', 'SZ': 'CN', 'HK': 'HK', 'US': 'US',
                'JP': 'JP'}.get(head, '')

    def insert_order(self, symbol: str, direction: str, offset: str = '',
                     volume: int = 0, limit_price=None, advanced=None,
                     order_id=None, account=None, *args, **kwargs):
        """下单：``trade=True`` 走富途交易，否则**本地模拟成交**（照常更持仓 ✓）"""
        # ★ 股票接口只做股票：期货（SHFE./DCE./CFFEX.…）一律拒绝 ——
        #   否则本地模拟盘会把期货单也“成交”掉，天勤账户却没有持仓
        #   （用户实测：12:20 显示下单成功 + 成交通知，但期货没持仓 ✗）
        head = str(symbol or '').split('.')[0].upper()
        if head in _FUTURES_EXCHANGES:
            raise ValueError(
                f'{symbol} 是期货合约，股票接口不接单（期货请用天勤模拟账号）')
        code = futu_code(symbol)
        if self._trd is not None:
            wanted = self._market_of_code(code)
            current = str(getattr(self, 'trd_market', '') or '').upper()
            if wanted and current and wanted != current:
                raise RuntimeError(
                    f'当前连接的是 {current} 市场交易账户，{code} 属于 '
                    f'{wanted} 市场；请在登录框切换交易市场后重连 '
                    '（富途每个市场有独立模拟账户）')
        qty = int(volume or 0)
        side = str(direction or '').upper()
        price = float(limit_price) if limit_price else self._last_price(code)
        real_id = None
        if self._trd is not None:
            # ★ 真实下单失败必须是**失败**：以前只 print，然后照样
            #   `_apply_fill()` + `FINISHED` → 富途拒单后本地账户却扣钱、
            #   显示已成交（用户/审计实测 ✗）。
            try:
                ret, data = self._trd.place_order(
                    price=price, qty=qty, code=code,
                    trd_side=(self._futu.TrdSide.BUY
                              if side == 'BUY' else self._futu.TrdSide.SELL),
                    order_type=self._futu.OrderType.NORMAL,
                    **({'trd_env': self._trd_env}
                       if hasattr(self, '_trd_env') else {}))
                if ret != self._RET_OK or data is None or data.empty:
                    raise RuntimeError(str(data))
                real_id = str(data.iloc[0].get('order_id') or '')
            except Exception as error:                           # noqa: BLE001
                message = f'富途下单失败 {code}: {error}'
                print(f'[StockApi] {message}', flush=True)
                # 让 Trading.place / _market_order 捕获后返回失败 toast，
                # 不再继续走本地成交 ✓
                raise RuntimeError(message) from error
        offset_upper = str(offset or '').upper()
        real = self._trd is not None and real_id is not None
        order = SimpleNamespace(
            order_id=real_id or order_id or f'SL{int(time.time() * 1000)}',
            instrument_id=code, direction=side, offset=offset, volume=qty,
            limit_price=price,
            # ★ 真实订单只代表**已提交**；等 order_list_query 轮询到成交 /
            #   部分成交 / 撤单，不能本地直接 FINISHED + _apply_fill ✗
            status='SUBMITTED' if real else 'FINISHED',
            last_price=price, volume_orign=qty,
            volume_left=qty)
        if not real:
            self._apply_fill(code, side, offset_upper, qty, price,
                             order_id=order.order_id)
        self._orders.append(order)
        if self._sim is not None:
            try:
                self._sim.add_order(order.order_id, code, side, offset_upper,
                                    qty, price, order.status)
            except Exception as error:                            # noqa: BLE001
                print(f'[StockApi] 保存模拟委托失败: {error}')
        self._save_equity()
        return order

    def _apply_fill(self, code: str, side: str, offset: str, qty: int,
                    price: float, order_id: str | None = None) -> float:
        """本地记账：持仓 / 现金 / 已实现盈亏 / 手续费，并**落盘** ✓

        Returns:
            本笔成交的已实现盈亏（含手续费；开仓为 0 ✓）
        """
        if qty <= 0:
            return 0.0
        book = self._ledger(code)
        buying = side == 'BUY'
        opening = offset in ('', 'OPEN') or offset.startswith('OPEN')
        realized = 0.0
        if opening:
            key = 'long' if buying else 'short'
            avg_key = 'avg_' + key
            held = float(book[key])
            total = held + qty
            if total > 0:
                book[avg_key] = (float(book[avg_key]) * held
                                 + price * qty) / total
            book[key] = total
        else:                                    # 平仓：按均价算已实现盈亏
            key = 'long' if not buying else 'short'
            avg_key = 'avg_' + key
            held = float(book[key])
            closed = min(held, float(qty))
            avg = float(book[avg_key])
            realized = ((price - avg) if key == 'long'
                        else (avg - price)) * closed
            book[key] = max(0.0, held - qty)
            if book[key] <= 0:
                book[avg_key] = 0.0
        # 现金：买 -> 支出，卖 -> 收入；手续费按成交额比例（默认 0）
        commission = abs(qty * price) * self._sim_commission
        self._cash += (qty * price) * (-1.0 if buying else 1.0) - commission
        self._realized_pnl += realized - commission
        self._commission += commission
        self._trade_seq += 1
        trade_id = f'T{int(time.time() * 1000)}{self._trade_seq}'
        net_pnl = realized - commission
        self._trades.append(SimpleNamespace(
            trade_id=trade_id, order_id=str(order_id or ''),
            instrument_id=code, direction=side, offset=offset,
            price=float(price), volume=float(qty), realized_pnl=net_pnl,
            trade_date_time=time.strftime('%Y-%m-%d %H:%M:%S')))
        if len(self._trades) > 2000:
            del self._trades[:-2000]
        if self._sim is not None:
            try:
                self._sim.save_position(code, book)
                self._sim.save_account(self._cash, self._realized_pnl,
                                       self._commission)
                self._sim.add_trade(
                    trade_id=trade_id, order_id=str(order_id or ''),
                    code=code, direction=side, offset=offset, qty=qty,
                    price=price, realized_pnl=net_pnl)
            except Exception as error:                            # noqa: BLE001
                print(f'[StockApi] 保存模拟成交失败: {error}')
        position = self._position_objs.get(code)
        if position is not None:
            self._update_position(code, position)
        return realized - commission

    def target_pos_task(self, symbol: str) -> StockTargetPosTask:
        """``TqObjs`` 会优先用这个（股票版 ``TargetPosTask``）✓"""
        return StockTargetPosTask(self, futu_code(symbol))

    # ---------------------------------------------------------------- 收尾
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._loop.closed = True
        for _code, ktype in list(self._subs):
            try:
                self._ctx.unsubscribe([_code], [getattr(self._SubType, ktype)])
            except Exception:                                    # noqa: BLE001
                pass
        self._subs.clear()
        if self._sim is not None:
            self._save_equity()
            try:
                self._sim.close()
            except Exception:                                    # noqa: BLE001
                pass
        try:
            self._ctx.close()
        except Exception:                                        # noqa: BLE001
            pass
        if self._trd is not None:
            try:
                self._trd.close()
            except Exception:                                    # noqa: BLE001
                pass
        print('[StockApi] 已断开 FutuOpenD')
