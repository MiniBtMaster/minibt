"""``Desk``：行情终端（报价 + 看盘）的脚本入口。

    from minibt import Desk
    desk = Desk()
    desk.add_futures(tq_auth=tq_auth('账号', '密码'))
    desk.add_stocks()
    desk.run()            # Qt 窗口（默认）/ browser=True → 浏览器

内部只有三件事：

* :mod:`minibt.desk.feeds` —— 期货/股票两路行情；
* :mod:`minibt.desk.protocol` —— 补丁下发 + 命令分发；
* 本节 —— Qt 窗口（``DeskWindow``，继承 ``pylightcharts.QtPanel``）/
  浏览器壳（:mod:`minibt.desk.web`）与 ~500ms 的刷新节拍。
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from . import protocol as _protocol
from . import symbols as _symbols
from .feeds import (BaseFeed, FuturesFeed, StockFeed, offline_rows,
                    pick_feed)

def resolve_desk_html(candidates=None) -> str:
    """找 desk 宿主页（``desk.html``）——**找不到就返回第一个候选**（报错信息用 ✓）

    顺序：仓库内路径 → 已安装 ``pylightcharts/js/`` → ``~/.minibt/desk/``。
    这样 minibt 是 editable（仓库）还是 PyPI 安装（site-packages）都能用。
    """
    if candidates is None:
        repo = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))), 'pylightcharts',
            'js', 'desk.html')
        candidates = [repo]
        try:
            import importlib.util as _util
            spec = _util.find_spec('pylightcharts')
            if spec is not None and spec.origin:
                candidates.append(os.path.join(
                    os.path.dirname(spec.origin), 'js', 'desk.html'))
        except Exception:                                        # noqa: BLE001
            pass
        candidates.append(os.path.join(os.path.expanduser('~'), '.minibt',
                                       'desk', 'desk.html'))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0] if candidates else ''


#: desk 的宿主页（由 `jslib` 构建产出；按上面顺序解析 ✓）
DESK_HTML = resolve_desk_html()


def build_fingerprint() -> str:
    """这次运行用的**代码 / 前端版本**（启动时写进运行日志 ✓）

    排查「改了没生效」最省事的一行：
    ``minibt 1.3.4 @ <minibt 目录> · pylightcharts <目录> · desk.js v=xxxx``
    —— Python 模块是启动时导入的、前端 bundle 也是页面加载时抓的，
    **改了代码必须重启 desk / 刷新页面**（这里是判断「是不是旧进程」的指纹 ✓）。
    """
    parts = []
    try:
        import minibt as _minibt
        parts.append(f'minibt {getattr(_minibt, "__version__", "?")}'
                     f' @ {os.path.dirname(os.path.abspath(_minibt.__file__))}')
    except Exception:                                            # noqa: BLE001
        parts.append('minibt ?')
    try:
        import pylightcharts as _pyl
        parts.append('pylightcharts @ '
                     f'{os.path.dirname(os.path.abspath(_pyl.__file__))}')
    except Exception:                                            # noqa: BLE001
        pass
    version = ''
    try:
        import re as _re
        with open(DESK_HTML, encoding='utf-8') as handle:
            found = _re.search(r'desk\.js\?v=([\w.-]+)', handle.read())
        if found:
            version = found.group(1)
    except Exception:                                            # noqa: BLE001
        pass
    parts.append(f'desk.js v={version or "?"}（{DESK_HTML}）')
    return ' · '.join(parts)

#: 刷新节拍（毫秒）：可见行报价 + 图表增量
TICK_MS = 500

#: 本地图表「加到图表」策略逐根回放根数：``0`` = 全量（默认）。
#: 回放已在后台线程，且 KLine 保持全量、只推进 btindex → CCI 10000 根
#: 约 3 秒；这样停止线 / 信号在所有可见历史区间都完整 ✓
LOCAL_STRATEGY_REPLAY_BARS = 0

#: 期货行情时间按**东八区**显示（天勤是 UTC ✓）
TZ_HOURS = int(os.environ.get('MINIBT_DESK_TZ', '8') or 8)

#: 首页「市场全景」= **主力 · 中金所**前 4 个（IF / IC / IH / IM；用户要求 ✓）
HOME_FUTURES_INDICES = (
    ('KQ.m@CFFEX.IF', '沪深'),
    ('KQ.m@CFFEX.IC', '中证'),
    ('KQ.m@CFFEX.IH', '上证'),
    ('KQ.m@CFFEX.IM', 'IM'),
)
HOME_FUTURES_WATCH = (
    ('KQ.m@SHFE.rb', '螺纹钢'),
    ('KQ.m@DCE.i', '铁矿石'),
    ('KQ.m@DCE.jm', '焦煤'),
    ('KQ.m@SHFE.cu', '沪铜'),
    ('KQ.m@SHFE.au', '沪金'),
    ('KQ.m@CFFEX.IF', '沪深300'),
    ('KQ.m@INE.sc', '原油'),
    ('KQ.m@DCE.m', '豆粕'),
    ('KQ.m@CFFEX.T', '十年国债'),
    ('KQ.m@SHFE.ag', '沪银'),
    ('KQ.m@CZCE.MA', '甲醇'),
    ('KQ.m@DCE.pp', '聚丙烯'),
)
HOME_STOCK_INDICES = (
    ('SSE.000300', '沪深300'),
    ('SZSE.399001', '深证成指'),
    ('SSE.000001', '上证指数'),
    ('SZSE.399006', '创业板指'),
)
HOME_STOCK_WATCH = (
    ('SSE.600519', '贵州茅台'),
    ('SZSE.000858', '五粮液'),
    ('SSE.601318', '中国平安'),
    ('SZSE.300750', '宁德时代'),
    ('SSE.600036', '招商银行'),
    ('SZSE.000333', '美的集团'),
    ('SSE.601899', '紫金矿业'),
    ('SSE.600900', '长江电力'),
)


def qt_argv(argv=None) -> list:
    """给 ``QApplication`` 用的 argv（**必须非空** ✓）

    ``QApplication([])`` 会让 QtWebEngine 报
    ``Argument list is empty, the program name is not passed to QCoreApplication``
    （Chromium 的 ``base::CommandLine`` 拿不到程序名）→ 页面渲染不出来。
    这里保证至少有一个程序名。
    """
    items = list(sys.argv if argv is None else argv)
    items = [str(item) for item in items if item is not None]
    return items or ['minibt-desk']


#: tkinter 文件夹框同一时间只允许一个（多线程同时建 Tk 会崩 ✗）
_PICK_LOCK = threading.Lock()


def _tk_choose_directory(title: str = '选择文件夹',
                         start: str = '') -> str:
    """用 tkinter 弹**系统**文件夹选择框（Qt 壳没注入 picker 时的兜底 ✓）

    浏览器壳 / VS Code 扩展里 Python 进程依然在本机跑 → 弹 Windows / macOS
    原生框，用户**不用手输路径**（用户要求 ✓）。
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:                                            # noqa: BLE001
        return ''
    folder = ''
    with _PICK_LOCK:
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            try:
                root.attributes('-topmost', True)
            except Exception:                                    # noqa: BLE001
                pass
            folder = filedialog.askdirectory(
                parent=root, title=title or '选择文件夹',
                initialdir=start or os.path.expanduser('~'),
                mustexist=True)
        except Exception:                                        # noqa: BLE001
            folder = ''
        finally:
            try:
                root.destroy()          # type: ignore[union-attr]
            except Exception:                                    # noqa: BLE001
                pass
    return str(folder or '')


def _pick_strategy_class(strategies, wanted: str = ''):
    """一个文件有多个 Strategy 时按名字选（08 多策略示例 ✓）"""
    wanted = str(wanted or '').strip()
    if wanted:
        for item in strategies or []:
            if str(getattr(item, '__name__', '') or '') == wanted:
                return item
    return (strategies or [None])[0]


class Desk:
    """行情终端（报价窗口 + 看盘窗口）"""

    def __init__(self, *, title: str = 'minibt桌面端', theme: str = 'dark',
                 size=(1500, 900), browser: bool = False, port: int = 0,
                 offline: bool = False, address: str = '127.0.0.1',
                 allow_trading: bool = True):
        self.title = title
        self.theme = theme if theme in ('light', 'dark') else 'dark'
        self.size = tuple(size)
        self.browser = bool(browser)
        self.port = int(port)
        self.offline = bool(offline)
        #: 运行日志是否同时打印到终端（`--quiet` 关掉 ✓）
        self.log_to_stdout = True
        #: 是否还推给前端（日志页 / 底部面板；`--no-ui-log` 关掉 ✓）
        self.log_to_ui = True
        #: 期货 / 股票都没连上（`minibt desk` 直接启动）→ 首页不加载，
        #: 初始化打开本地图表 ✓（不要和 `--offline` 演示数据混在一起）
        self.no_service = False
        #: 首页当前是否可见（可见才刷新 home 补丁 ✓）
        self._home_active = False
        #: 首页账户卡当前选中的模拟账户：futures / stocks
        self._home_account_kind = 'futures'
        self._home_at = 0.0
        #: 首页「主力」点开时天勤合约还没就绪 → 2 秒后自动重查 ✓
        self._home_main_retry_exchange = ''
        self._home_main_retry_at = 0.0
        #: 登录线程建好 api 后把「连上之后要刷什么」交给主线程（tick 执行 ✓）
        self._after_connect_pending = None
        #: 收藏 / 手动加入自选的合约（每次首页刷新都带上 ✓）
        self._home_extra: List[str] = []
        #: 本地 LSP 服务（jedi；编辑器第一次打开时懒启动 ✓）
        self._lsp = None
        #: 后台策略计算的**结果队列**（主线程 `tick` 里应用 ✓）
        #: 策略的 `__init__` 可能很重（Kalman 的 Python 循环）→ 不能占主线程 ✗
        self._strategy_results: List[dict] = []
        #: 正在后台跑的策略任务数（>0 时 tick **不碰 tqsdk**，避免跨线程 ✗）
        self._heavy_jobs = 0
        #: 本地图表：**只读策略叠加**（页签 id → [record]）
        #: `record = {name, path, items, groups, symbol, page}`；
        #: 只算 `__init__`（静态线），不跑 `next`、不碰账户 ✓
        self._local_overlays: Dict[str, List[dict]] = {}
        #: 本地图表：**按页**存的指标（页签 id → 格 → 指标列表 ✓）
        #: 多开本地图表时，两份副本加载同一份 CSV 也各自独立 ✓
        self._local_indicators: Dict[str, Dict[int, List[dict]]] = {}
        #: 本地图表上「加到图表」的策略（CSV 名 → {items,name,path}）✓
        self._local_strategies: Dict[str, Dict[str, Any]] = {}
        #: 本地图表：策略信号自动交易已执行的信号 id（按 CSV 名）
        self._local_strategy_done: Dict[str, set] = {}
        #: 启动时是否直接打开「首页」（只有命令行带账号登录才为 True ✓）
        self.home_on_boot = False
        #: 实盘账户？（实盘的 `get_kline_serial` 会卡几十秒 → spark 等先跳过 ✓）
        self._real_account = False
        #: 行情页拿到的「主力 · 中金所」前 4 个（首页市场全景用 ✓）
        self._main_indices: List[tuple] = []
        #: 正在登录（主线程此时不要碰 tqsdk，否则抢锁卡死 ✗）
        self._login_busy = False
        #: 待连接的行情源（**主线程**执行：tqsdk / futu 只能在创建线程用 ✓）
        self._connect_pending = None
        #: 取数超时后的「冷静期」（避免每拍都卡在超时上 ✓）
        self._quotes_block_until = 0.0
        self._timeout_seen = 0
        #: 登录连上的 api 专属线程（退出时 close ✓）
        #: 数据请求慢时的「冷静期」（避免每拍都卡在阻塞调用上 ✓）
        self._slow_until = 0.0
        #: 正在回放的合约（这些合约的交易走**本地模拟账户** ✓）
        self.replay_symbols: set = set()
        #: 浏览器壳是否自动打开系统浏览器（`--no-browser` / 扩展托管时设 False ✓）
        self.open_browser = True
        #: 是否允许下单：``allow_trading=False`` 或没接 api → 前端按钮禁用 ✓
        self.trading = bool(allow_trading)
        #: 交易执行器（惰性；P4）
        self.trader = None
        #: 账户面板（11 卡 + 4 表 + 多账户）；惰性建
        self.accounts = None
        #: 合约搜索池（``[{symbol, name, exchange, type}]``；惰性建 ✓）
        self._search_pool: List[dict] = []
        #: 价格预警：``[{id, symbol, price, action, qty, fired}]``
        self.alerts: List[dict] = []
        self._alert_seq = 0
        self._dock_at = 0.0
        self.address = address

        self.feeds: List[BaseFeed] = []
        self.futures: Optional[FuturesFeed] = None
        self.stocks: Optional[StockFeed] = None
        self.watchlist: List[str] = []

        #: 当前筛选（类型/交易所/搜索）
        self.filter: Dict[str, str] = {'type': 'FUT', 'exchange': '', 'text': ''}
        #: 前端上报的可见行（增量刷新只推这些 ✓）
        self.visible: List[str] = []
        #: 已打开的看盘 tab → (feed, cycle)
        self.tabs: Dict[str, Dict[str, Any]] = {}
        #: 后台启动中（不发补丁 → 先攒着）
        self._booted = False
        self._pending: List[str] = []
        self._tick_at = 0.0
        self._rows_at = 0.0
        #: 首屏/切筛选的取数是否还欠着（flush 之后由 tick 执行 ✓）
        self._reload_pending = False
        #: 合约清单**后台线程**加载（`(generation, rows, error)` ✓）
        self._rows_gen = 0
        self._rows_loading = False
        self._rows_pending = False
        self._rows_label = ''
        self._rows_result = None
        #: 取不到合约的 (类型, 交易所) → 跳过，不再反复请求（用户要求 ✓）
        self._skip_markets: set = set()
        #: 天勤刚登录时符号字典还没下来 → 2 秒后自动重试（不要永久跳过 ✗）
        self._empty_rows_retry_at = 0.0
        self._empty_rows_retry_key = ''
        #: 后台线程正在查合约（`query_quotes` 会阻塞 30 秒）→ 主线程别碰 api ✓
        self._api_exclusive = False
        #: 待补名称的合约（每拍补一小批，避免 query_symbol_info 卡界面 ✓）
        self._name_queue: List[str] = []
        self._name_at = 0.0
        self._last_rows: Dict[str, dict] = {}
        #: `Gui.Desk` 排队的界面动作 / 预计算的指标线（btplot ✓）
        self._ui_queue: List[dict] = []
        self._ui_next_at = 0.0
        self._local_plot_items: Dict[Any, List[dict]] = {}
        # ★ 报价快照缓存：切到首页/报价页时**先推缓存**（有数就能点 ✓），
        #   后台再慢慢更新（实盘 query_quotes 可能卡 2~30 秒 ✗）
        self._quote_cache: Dict[str, dict] = self._load_quote_cache()
        self._quote_cache_dirty = False
        self._quote_cache_at = 0.0
        #: 合约清单缓存（sqlite；当天有效 ✓）；建库失败 → None（不影响行情）
        self._cache = None
        self._cache_ready = False
        #: 走势 spark 缓存：``{symbol: [close, …]}``（气泡按需拉 ✓）
        self._spark: Dict[str, list] = {}
        #: 走势列（spark）填充分配：每 5 秒最多补 12 只可见行 ✓
        self._spark_at = 0.0
        self._spark_budget = 6
        self._window = None

        #: 补丁发送钩子（Qt / 浏览器壳注入 ✓）
        self.sender = None
        #: **后台线程 → 主线程的发件箱**：`runJavaScript` 不是线程安全的，
        #: 后台线程（指标计算 / 索引构建）直接推补丁会让进程**硬崩且无 traceback**
        #: （用户实测：点指标就闪退 ✗）。非主线程的补丁先进队列，
        #: 由主线程（`tick()` / `DeskWindow` 的小定时器）`flush_outbox()` 发出去 ✓
        self._outbox: List[Dict[str, Any]] = []
        #: 创建 desk 的线程（= GUI 主线程）
        self._main_thread = threading.current_thread()
        #: 「本地图表」：CSV 数据 + 本地模拟账户（惰性 ✓）
        self._local_store = None
        self._local_sim = None
        #: 策略回测 / 参数优化会话（P118+；每个浏览器 Tab 一个 ✓）
        self._strategy_labs: Dict[str, Any] = {}
        self._strategy_seq = 0
        #: 本地图表策略回放：放到后台线程，避免 CCI 这类重计算把
        #: Qt / 浏览器主线程卡成「未响应」✗（用户实测）
        self._local_strategy_seq = 0
        self._local_strategy_jobs: Dict[str, int] = {}
        self._local_strategy_worker = threading.Lock()

        # ---- 扩展功能（交易工作台 / 研究平台 / 数据平台 / 运维）----
        # 全部**惰性创建**：没打开对应页面就不建 SQLite、不加载数据 ✓
        self._workbench = None
        self._research = None
        self._datahub = None
        self._ops = None
        self._suite_at = 0.0
        #: K 线历史还没下来时，策略「没有指标线」的延迟重试队列 ✓
        self._strategy_retries: List[dict] = []

    # ======================================================== 行情源
    def add_futures(self, tq_auth=None, tq_account=None, api=None,
                    **kwargs) -> 'Desk':
        """接期货（天勤）。

        Args:
            tq_auth: 天勤账号（``minibt.tq_auth`` 或 dict）
            tq_account: 实盘账户（``minibt.tq_account``）；不给 → 快期模拟
            api: 已建好的 ``TqApi``（直接复用；多账户就传 ``TqMultiAccount`` 的）
        """
        if api is None:
            try:
                from tqsdk import TqAccount, TqApi, TqAuth, TqKq
            except ImportError as error:                         # noqa: BLE001
                raise ImportError(
                    '期货行情需要 tqsdk： pip install tqsdk') from error
            auth_values = getattr(tq_auth, 'values', None) or (
                tq_auth if isinstance(tq_auth, dict) else None)
            acc_values = getattr(tq_account, 'values', None) or (
                tq_account if isinstance(tq_account, dict) else None)
            auth = TqAuth(**auth_values) if auth_values else None
            target = TqAccount(**acc_values) if acc_values else TqKq()
            api = TqApi(target, auth=auth) if auth is not None else TqApi(target)
            self._real_account = bool(acc_values)
        self.futures = FuturesFeed(api, 'futures')
        self.feeds.append(self.futures)
        return self

    def add_stocks(self, host: str = '127.0.0.1', port: int = 11111,
                   sim_account: str = 'desk', trade: bool = False,
                   **kwargs) -> 'Desk':
        """接股票（富途 OpenD）。连不上只影响股票页，期货照常 ✓

        Args:
            sim_account: 本地模拟盘账本名（默认 ``'desk'``，与别的工具分开）
            trade: ``False``（默认）= 只行情 + 本地模拟成交；``True`` = 真实交易
        """
        from ..stock_api import StockApi
        api = StockApi(host=host, port=port, trade=trade,
                       sim_account=sim_account, **kwargs)
        self.stocks = StockFeed(api, 'stocks')
        self.feeds.append(self.stocks)
        return self

    def watch(self, symbols) -> 'Desk':
        """预订阅：默认把这些合约加到"自选"（P1 用）"""
        self.watchlist = [str(item) for item in (symbols or [])]
        return self

    # ======================================================== 启动
    def run(self, *, as_json: bool = False) -> None:
        """阻塞运行（关窗 / Ctrl+C 结束 ✓）

        Args:
            as_json: ``True`` → 启动后先打一行 ``{"ready": true, "url": …}``
                的 JSON（浏览器壳），方便 VS Code 扩展 / 脚本读就绪信息 ✓

        Jupyter：**不开 Qt**（kernal 线程里 ``application.exec()`` 会卡死），
        自动降级到浏览器壳 + iframe 内嵌（由 :func:`minibt.desk.gui.
        show_in_notebook` 处理，并且**不阻塞** kernel ✓）。
        """
        if self.offline and not self.feeds:
            self.offline = True
        if not self.browser:
            try:
                from .gui import in_notebook
                notebook = in_notebook()
            except Exception:                                    # noqa: BLE001
                notebook = False
            if notebook:
                self.browser = True
                self.open_browser = False
                from . import gui as _gui
                _gui.show_in_notebook(self)   # 起服务 + display(IFrame) ✓
                return
        if self.browser:
            from .web import serve
            # `open_browser=False`：被 VS Code 扩展 / 自己的外壳托管时别再弹浏览器 ✓
            try:
                serve(self,
                      open_browser=bool(getattr(self, 'open_browser', True)),
                      as_json=as_json)
            finally:
                self.close()          # 关 tqsdk / futu 的 api，别留 pending 任务 ✓
        else:
            if as_json:
                import json as _json
                print(_json.dumps({'ready': True, 'shell': 'qt',
                                   'title': self.title, 'theme': self.theme},
                                  ensure_ascii=False), flush=True)
            try:
                self._run_qt()
            finally:
                self.close()

    def code_info(self) -> str:
        """当前**实际运行**的代码路径 + 构建标记（排查「改了没生效」✓）"""
        try:
            import minibt as _minibt
            version = getattr(_minibt, '__version__', '?')
            root = getattr(_minibt, '__file__', '?')
        except Exception:                                        # noqa: BLE001
            version, root = '?', '?'
        try:
            build = os.path.abspath(__file__)
        except Exception:                                        # noqa: BLE001
            build = '?'
        return chr(10).join([
            f'minibt {version} · {root}',
            f'desk   {build}',
        ])

    def status(self) -> Dict[str, Any]:
        """连接状态快照（`/healthz` 与 `--json` 共用 ✓）"""
        try:
            futures = bool(self.futures and self.futures.available())
        except Exception:                                        # noqa: BLE001
            futures = bool(self.futures)
        try:
            stocks = bool(self.stocks and self.stocks.available())
        except Exception:                                        # noqa: BLE001
            stocks = bool(self.stocks)
        return {'ready': True, 'title': self.title, 'theme': self.theme,
                'offline': bool(self.offline or self.no_service),
                'no_service': bool(self.no_service),
                'futures': futures, 'stocks': stocks,
                'tabs': list(self.tabs), 'python': sys.version.split()[0]}

    def api_snapshot(self) -> Dict[str, Any]:
        """REST / headless 用的只读快照（不主动创建重对象）✓"""
        payload: Dict[str, Any] = {
            'status': self.status(),
            'markets': self.market_map(),
            'tabs': list(self.tabs),
            'alerts': list(self.alerts),
            'suite': {},
        }
        bench = getattr(self, '_workbench', None)
        if bench is not None:
            try:
                payload['suite']['workbench'] = bench.snapshot()
            except Exception as error:                           # noqa: BLE001
                payload['suite']['workbench'] = {'error': repr(error)}
        lab = getattr(self, '_research', None)
        if lab is not None:
            try:
                payload['suite']['research'] = lab.snapshot()
            except Exception as error:                           # noqa: BLE001
                payload['suite']['research'] = {'error': repr(error)}
        hub = getattr(self, '_datahub', None)
        if hub is not None:
            try:
                payload['suite']['datahub'] = hub.snapshot()
            except Exception as error:                           # noqa: BLE001
                payload['suite']['datahub'] = {'error': repr(error)}
        ops = getattr(self, '_ops', None)
        if ops is not None:
            try:
                payload['suite']['ops'] = ops.snapshot()
            except Exception as error:                           # noqa: BLE001
                payload['suite']['ops'] = {'error': repr(error)}
        return payload

    def export_static(self, target: str, *, config: bool = True) -> str:
        """把 desk 前端**导出成静态目录**（供 minibt-charts / 自己的后端嵌入 ✓）

        产物::

            <target>/desk.html     宿主页（transport 由调用方注入）
            <target>/desk.js       TS 应用（IIFE，全局 ``Desk``）
            <target>/desk.css      样式
            <target>/styles.css    pylightcharts 图表样式
            <target>/lightweight-charts.js
            <target>/config.json   {transport, theme, title}（可选）

        嵌入方式（minibt-charts）：页面里加载 ``desk.js``，然后
        ``window.__deskConfig = {transport: 'rest', endpoint: '/api/desk'}``，
        再实现 ``DeskTransport`` 的后端即可（详见文档 13.1 第 7 节）。
        """
        import json as _json
        import shutil

        source = os.path.dirname(DESK_HTML)
        os.makedirs(target, exist_ok=True)
        copied = []
        for name in ('desk.html', 'desk.js', 'desk.css', 'styles.css',
                     'lightweight-charts.js'):
            origin = os.path.join(source, name)
            if not os.path.isfile(origin):
                continue
            shutil.copyfile(origin, os.path.join(target, name))
            copied.append(name)
        if not os.path.isfile(os.path.join(target, 'desk.html')):
            raise FileNotFoundError(
                f'没找到 desk 前端产物（{DESK_HTML}）；先在 jslib 执行 '
                '`npm run build`')
        if config:
            with open(os.path.join(target, 'config.json'), 'w',
                      encoding='utf-8') as handle:
                _json.dump({'transport': 'rest', 'theme': self.theme,
                            'title': self.title}, handle, ensure_ascii=False,
                           indent=2)
            copied.append('config.json')
        return target

    # -------------------------------------------------------- Qt 壳
    def _run_qt(self) -> None:
        from pylightcharts.qt import prepare_qt
        prepare_qt('PyQt6')
        from PyQt6.QtWidgets import QApplication
        from .app_window import DeskWindow

        # ★ argv 必须非空（否则 QtWebEngine 初始化失败，窗口白屏 ✓）
        application = QApplication.instance() or QApplication(qt_argv())
        try:
            application.setApplicationName('minibt desk')
        except Exception:                                        # noqa: BLE001
            pass
        window = DeskWindow(self)
        window.resize(*self.size)
        window.show()
        self._window = window
        self.start_timer()
        try:
            application.exec()
        finally:
            self.close()

    def close(self) -> None:
        """退出前**优雅关闭**：停节拍 + 关行情连接（tqsdk / futu）✓

        不关的话 tqsdk 的 asyncio 任务没被 cancel，退出时刷一屏
        ``Task was destroyed but it is pending`` / ``Event loop is closed`` ✗
        幂等：`Desk.run()` 的 finally 和 `cli` 的 finally 都会调一次 ✓
        """
        if getattr(self, '_closed', False):
            return
        self._closed = True
        holder = getattr(self, '_timer', None)
        timer = (holder or {}).get('timer') if isinstance(holder, dict) else None
        stop_timer = getattr(timer, 'stop', None)
        if callable(stop_timer):
            try:
                stop_timer()
            except Exception:                                    # noqa: BLE001
                pass
        if getattr(self, '_lsp', None) is not None:
            try:
                self._lsp.stop()
            except Exception:                                    # noqa: BLE001
                pass
        # ★ 浏览器壳 / Desk.close() 也必须停策略实盘：Qt 的 DeskWindow
        #   会调，但 browser 模式原来没有 → 关页面后子进程仍可能下单 ✗
        if (getattr(self, '_strategy_lives', None)
                or getattr(self, '_strategy_live', None) is not None):
            try:
                self.stop_strategy_live()
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 停止策略实盘失败：{error!r}', flush=True)
        for lab in list(getattr(self, '_strategy_labs', {}).values()):
            try:
                lab.cancel()
            except Exception:                                    # noqa: BLE001
                pass
        # 本地模拟账户落盘（有 db_path 时；纯内存测试对象是 no-op ✓）
        sim = getattr(self, '_local_sim', None)
        if sim is not None:
            try:
                sim.save()
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 保存本地模拟账户失败：{error!r}', flush=True)
        # 扩展功能的 SQLite（工作台审计 / 实验库）也一起关掉 ✓
        for owner in (getattr(self, '_workbench', None),
                      getattr(self, '_research', None)):
            store = getattr(owner, 'store', None)
            closer = getattr(store, 'close', None)
            if callable(closer):
                try:
                    closer()
                except Exception:                            # noqa: BLE001
                    pass
        for feed in list(getattr(self, 'feeds', []) or []):
            closer = getattr(feed, 'close', None)     # `BaseFeed.close` ✓
            if callable(closer):
                try:
                    closer()
                    continue
                except Exception as error:                       # noqa: BLE001
                    print(f'[desk] 关闭行情源失败：{error!r}', flush=True)
            api = getattr(feed, 'api', None)          # 兜底：直接关 api
            close_api = getattr(api, 'close', None)
            if callable(close_api):
                try:
                    close_api()
                except Exception as error:                       # noqa: BLE001
                    print(f'[desk] 关闭 {type(api).__name__} 失败: {error!r}')
        task_cache = getattr(self, '_tasks', None)
        if isinstance(task_cache, dict):
            task_cache.clear()
        self._window = None

    # -------------------------------------------------------- 节拍
    def start_timer(self) -> None:
        """500ms 一拍：可见行报价 + 打开的图表增量 ✓"""
        from .app_window import qt_timer
        holder = {}

        def tick():
            self.tick()
            holder['timer'] = qt_timer(TICK_MS, tick)

        holder['timer'] = qt_timer(TICK_MS, tick)
        self._timer = holder

    #: 每次泵最多等多久（秒）—— tqsdk 的 `deadline` 是**绝对时间戳**，
    #: 传 0 等于“早就过期”，会给 loop 留下的窗口太小（偶尔收不到新包 ✗）
    PUMP_DEADLINE = 0.05

    def pump(self, timeout: float = None) -> None:
        """驱动天勤内部 loop（**行情实时更新的前提** ✓）

        tqsdk 是同步 API：不调 ``TqApi.wait_update()`` 就**永远收不到新 tick**
        （用户实测：报价和图表都冻在打开那一刻 10:30 ✗）。

        ⚠ ``deadline`` 是 **unix 时间戳**（``time.time()``），不是“等多少秒”！
        所以这里传 ``time.time() + PUMP_DEADLINE``（默认 50ms），
        给 socket 留一点收包窗口；不阻塞 UI，等价 miniqt 的 ``TqApiQTimer`` ✓
        """
        if getattr(self, '_login_busy', False):
            # ★ 登录线程正在建 TqApi / 用 api → 主线程**别碰**（会卡死 ✗）
            return
        api = getattr(getattr(self, 'futures', None), 'api', None)
        if api is None:
            return

        wait = getattr(api, 'wait_update', None)
        if not callable(wait):
            return
        span = self.PUMP_DEADLINE if timeout is None else float(timeout)
        try:
            wait(deadline=time.time() + span)
        except Exception as error:                               # noqa: BLE001
            # ★ TqSdk 对“不存在的合约”会抛 GraphQL 错误；如果只 catch
            #   不清理，这个订阅会每拍继续把行情泵打断 → 首页 / 报价全空 ✗。
            #   从错误里取出合约代码，取消它的订阅，再让 pump 继续 ✓
            text = str(error)
            for bad in re.findall(r'\[([A-Za-z0-9_.]+)\]', text) + \
                    re.findall(r'instrument:\s*([A-Za-z0-9_.]+)', text):
                # ★ 天勤的报错里经常只有**裸代码**（`ag2612` / `rb2701`）。
                #   先在服务端合约字典里查一下：这个品种真有该合约 →
                #   说明报错来自别处（例如拿裸代码建 TargetPosTask），
                #   **不能**把合法的 `SHFE.ag2612` 拉黑 / 从缓存删掉 ✗
                if '.' not in str(bad) and self._contract_exists(bad):
                    continue
                feed = getattr(self, 'futures', None)
                drop = getattr(feed, 'drop_symbol', None)
                if callable(drop):
                    try:
                        drop(bad)
                    except Exception:                        # noqa: BLE001
                        pass
                self._purge_bad_symbol(bad)
            if not getattr(self, '_pump_warned', False):
                self._pump_warned = True
                self.push_log(f'行情泵异常（已移除无效订阅，稍后重试）：{error!r}',
                              'warning')
        else:
            self._pump_warned = False

    def _contract_exists(self, symbol: str) -> bool:
        """服务端合约字典 / 本地合约缓存里是否有这个合约（裸代码也能查 ✓）

        `symbol` 不带交易所时就按后缀找（`ag2612` → `SHFE.ag2612`）。
        用于区分「真·不存在的合约」和「别处传了裸代码导致的报错」✓
        """
        symbol = str(symbol or '')
        if not symbol:
            return False
        keys: List[str] = []
        try:
            feed = getattr(self, 'futures', None)
            api = getattr(feed, 'api', None)
            data = getattr(api, '_data', None)
            symbols = data.get('symbols') if isinstance(data, dict) else None
            if isinstance(symbols, dict):
                keys.extend(str(key) for key in symbols)
        except Exception:                                        # noqa: BLE001
            pass
        if not keys:
            keys.extend(str(key) for key in (self._last_rows or {}))
        if '.' in symbol:
            return symbol in keys
        return any(key == symbol or key.endswith('.' + symbol)
                   for key in keys)

    # ================================================ 外部脚本驱动界面
    #: `Gui.Desk`（btplot / Bt / 自己的脚本）排队的界面动作：
    #: ``[{'action': …, **payload}, …]`` —— 一拍执行一条，保证顺序 ✓
    def _run_strategy_retries(self) -> None:
        """K 线首屏只有占位行时，等历史下来后再挂一次策略 ✓"""
        if not self._strategy_retries:
            return
        now = time.monotonic()
        due = [item for item in self._strategy_retries
               if float(item.get('at') or 0.0) <= now]
        if not due:
            return
        self._strategy_retries = [item for item in self._strategy_retries
                                  if item not in due]
        for item in due:
            try:
                self._on_editor_add_indicator(dict(item.get('payload') or {}))
            except Exception as error:                           # noqa: BLE001
                self.push_log(f'策略延迟重试失败：{error!r}', 'warning')

    def queue_ui(self, action: str, *, delay: float = 0.0,
                 **payload) -> 'Desk':
        """排队一个**界面动作**（前端 `ui_action` 补丁 ✓）

        典型用法（`Gui.Desk`）::

            desk.queue_ui('open_local_chart', name='pp2609_60')
            desk.queue_ui('open_strategy_lab', file=r'C:/x/s.py', mode='backtest')
            desk.queue_ui('open_chart', symbol='SHFE.ag2612')

        排队而不是立刻 push：页面是**前端**建的（`openLocalChart` /
        `openStrategyLab`），必须等它 boot 完、而且一次只做一个，否则
        K 线 / 指标补丁会打在还不存在的页面上（静默丢失 ✗）。
        """
        action = str(action or '').strip()
        if not action:
            return self
        queue = getattr(self, '_ui_queue', None)
        if queue is None:
            queue = self._ui_queue = []
        item = {'action': action, **payload}
        if float(delay or 0.0) > 0:
            item['_at'] = time.monotonic() + float(delay)
        queue.append(item)
        self._ui_next_at = 0.0            # 下一拍就可以执行 ✓
        return self

    @property
    def pending_ui(self) -> List[dict]:
        """还没执行的界面动作（排查 / 测试用 ✓）"""
        return list(getattr(self, '_ui_queue', []) or [])

    def _run_ui_queue(self) -> None:
        """每拍执行**一条**排队的界面动作（前端 boot 完才开始 ✓）"""
        queue = getattr(self, '_ui_queue', None)
        if not queue or not getattr(self, '_booted', False):
            return
        now = time.monotonic()
        if now < float(getattr(self, '_ui_next_at', 0.0) or 0.0):
            return
        # 队首是延迟动作 → 等到时间；后面的动作也一起等，保证“先开完全部
        # 图表，再挂策略”的顺序 ✓
        head_at = float(queue[0].get('_at') or 0.0)
        if head_at and now < head_at:
            self._ui_next_at = head_at
            return
        item = dict(queue.pop(0))
        item.pop('_at', None)
        action = str(item.pop('action', ''))
        # 动作之间留一点时间给前端建页面 / 后端回填数据 ✓
        self._ui_next_at = time.monotonic() + 0.6
        try:
            self._apply_ui_action(action, item)
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'界面动作 {action} 失败：{error!r}', 'warning')

    def _apply_ui_action(self, action: str, payload: dict) -> None:
        """界面动作 → 前端补丁 / 后端命令 ✓"""
        if action == 'open_local_chart':
            name = str(payload.get('name') or '')
            # ★ name='' 也要让前端开一个**空白本地图表页**（Gui.Desk 的策略
            #   先在空白页上自动选 CSV；以前这里直接 return → 后续 K 线 /
            #   策略补丁全打在还不存在的页面上，看起来“只打开图表、没加载”✗）
            self.push({'type': 'ui_action', 'action': 'open_local_chart',
                       'name': name,
                       'cell': int(payload.get('cell') or 0)})
        elif action == 'open_strategy_lab':
            file = str(payload.get('file') or '')
            if file:
                self.push({'type': 'ui_action',
                           'action': 'open_strategy_lab', 'file': file,
                           'mode': str(payload.get('mode') or 'backtest')})
        elif action == 'open_chart':
            symbol = str(payload.get('symbol') or '')
            if symbol:
                self._on_open_chart({'symbol': symbol,
                                     'name': str(payload.get('name') or ''),
                                     'cycle': payload.get('cycle')})
        elif action == 'local_load':
            self._on_local_load(payload)
        elif action == 'add_local_indicator':
            self._on_local_add_indicator(payload)
        elif action == 'add_strategy':
            self._on_editor_add_indicator(payload)
        elif action == 'push_plot_items':
            self.push_local_plot_items(str(payload.get('name') or ''),
                                       cell=int(payload.get('cell') or 0))
        else:
            self.push_log(f'未知的界面动作：{action}', 'warning')

    # ---- 预计算指标线（btplot / 外部指标已经有数据，不用 desk 再算 ✓） ----
    def set_local_plot_items(self, name: str, items, cell: int = 0) -> None:
        """直接塞**算好的**指标线（`btplot(gui='Gui.Desk')` 用 ✓）

        desk 的本地图表平时按目录 key 重算指标；但 btplot / BtIndicator
        的线是**已经算好**的（还带 PlotInfo 的颜色 / 虚线 / 信号），
        所以这里按 (CSV, 格) 存一份，`_local_indicator_payload()` 会把它
        们一起推给前端 ✓
        """
        name = str(name or '')
        if not name:
            return
        store = getattr(self, '_local_plot_items', None)
        if store is None:
            store = self._local_plot_items = {}
        store[(name, max(0, int(cell or 0)))] = [
            dict(item) for item in (items or []) if isinstance(item, dict)]

    def push_local_plot_items(self, name: str, cell: int = 0) -> None:
        """把预计算的那份指标线推给前端（页面已经打开时用 ✓）"""
        if not name:
            return
        self.push(self._local_indicator_payload(
            name, max(0, int(cell or 0))))

    def _purge_bad_symbol(self, symbol: str) -> None:
        """把服务端确认不存在的合约从本地合约缓存 / 首页自选里删掉 ✓

        否则下次启动还会从 sqlite 读回 `SHFE.rb2701`，再次订阅、
        再次把行情泵打断（用户看到的就是“每次登录都没数据”）。
        """
        symbol = str(symbol or '')
        if not symbol:
            return
        # ★ 裸代码（`ag2612`）**不能**按后缀模糊匹配：那样会把合法的
        #   `SHFE.ag2612` 一起删掉（用户实测：报价表少一行 / 图表打不开 ✗）
        exact_only = '.' not in symbol

        def match(value: str) -> bool:
            value = str(value or '')
            if exact_only:
                return value == symbol
            return value == symbol or value.endswith('.' + symbol)
        self._last_rows = {key: row for key, row in self._last_rows.items()
                           if not match(key)}
        self._home_extra = [item for item in (self._home_extra or [])
                            if not match(item)]
        cache = None
        try:
            cache = self.symbol_cache()
        except Exception:                                    # noqa: BLE001
            cache = None
        if cache is None:
            return
        try:
            keys = list(cache.keys())
        except Exception:                                    # noqa: BLE001
            return
        for key in keys:
            try:
                rows = cache.get(key)
            except Exception:                                # noqa: BLE001
                continue
            if not rows:
                continue
            cleaned = [row for row in rows
                       if not match(str((row or {}).get('symbol') or ''))]
            if len(cleaned) != len(rows):
                try:
                    cache.put(key, cleaned)
                except Exception:                            # noqa: BLE001
                    pass

    def tick(self) -> None:
        if getattr(self, '_closed', False):
            return
        now = time.monotonic()
        if now - self._tick_at < TICK_MS / 1000.0 * 0.9:
            return
        self._tick_at = now
        started = time.monotonic()
        slowest = ['', 0.0]

        def step(name, fn):
            """跑一步并记耗时（>0.4s 记一笔，总耗时 >1.2s 报警 ✓）"""
            self._tick_step = name          # 出错时能说出是哪一步 ✓
            before = time.monotonic()
            fn()
            span = time.monotonic() - before
            if span > slowest[1]:
                slowest[0], slowest[1] = name, span
            # 「走势 spark」本来就低频（5 秒节流 + 结果缓存）→ 不报性能警告 ✓
            if span > 0.4 and name not in ('走势 spark',):
                self.push_log(f'[性能] {name} 耗时 {span:.2f}s', 'warning')

        # ★ 有后台策略正在计算 → 主线程**不碰 tqsdk**（行情泵 / 报价 / K 线）：
        #   tqsdk 不是线程安全的，跨线程会和后台任务抢锁（会卡死 ✗）
        busy = int(getattr(self, '_heavy_jobs', 0)) > 0
        try:
            # ★ 每一步都计时：卡顿时日志会写「[性能] 哪一步 多少秒」✓
            step('下发补丁', self.flush_outbox)
            step('策略结果', self._drain_strategy_results)
            if not busy:
                step('登录连接', self._run_connect)
                step('登录后刷新', self._run_after_connect)
            step('合约结果', self._drain_rows_result)
            step('空合约重试', self._retry_empty_rows)
            if not busy:
                step('行情泵', self.pump)
            step('外部界面动作', self._run_ui_queue)
            step('策略延迟重试', self._run_strategy_retries)

            def maybe_reload() -> None:
                if self._reload_pending:
                    self._reload_pending = False
                    self.reload_rows()

            step('加载合约清单', maybe_reload)
            if not busy:
                if self._quotes_visible():
                    step('报价快照落盘', self._save_quote_cache_step)
                    step('可见行报价', self._refresh_visible)
                if self._quotes_visible():
                    step('补小数位', self._fill_decimals_step)
                step('全市场索引', self._index_step)

                if self._quotes_visible():
                    step('走势 spark', self._refresh_sparks)
                if self._quotes_visible():
                    step('首页刷新', self._refresh_home)
                step('看盘 tab', self._refresh_tabs)
            step('账户面板', self._refresh_docks)
            if not busy:
                step('价格预警', self.check_alerts)
            step('工作台 / 定时任务', self._suite_tick)
            total = time.monotonic() - started
            if total > 1.2:
                # 界面卡顿排查：把最慢的一步写进运行日志 ✓
                self.push_log(
                    f'[性能] 这一拍共 {total:.2f}s，最慢：{slowest[0] or "?"} '
                    f'{slowest[1]:.2f}s', 'warning')
        except Exception as error:                               # noqa: BLE001
            where = getattr(self, '_tick_step', '') or '?'
            self.push_log(f'刷新失败（{where}）：{error!r}', 'error')
            self.push(_protocol.patch_toast(
                f'刷新失败（{where}）: {error!r}', 'error'))

    # ======================================================== 发送
    def push(self, patch: Dict[str, Any]) -> None:
        """下发一个补丁（**线程安全** ✓）

        如果当前不在创建 desk 的那个线程（＝后台指标线程 / 索引线程），
        先用 ``dispatcher`` 切回主线程再真正发送 —— Qt WebEngine 的
        ``runJavaScript`` 只能在 GUI 线程调用，跨线程调用会**直接崩进程**
        且不打印任何 traceback（用户实测：点指标就闪退 ✗）
        """
        if threading.current_thread() is not self._main_thread:
            # 后台线程：放进发件箱，主线程下一拍统一发（线程安全 ✓）
            self._outbox.append(patch)
            return
        self._push_now(patch)

    def flush_outbox(self) -> None:
        """把后台线程产生的补丁发出去（**只能在主线程调用** ✓）"""
        if not self._outbox:
            return
        pending = self._outbox
        self._outbox = []
        for patch in pending:
            try:
                self._push_now(patch)
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 补丁发送失败: {error!r}')

    def _push_now(self, patch: Dict[str, Any]) -> None:
        """真正发送（只允许在主线程 / HTTP 线程外被 dispatcher 调用 ✓）"""
        script = _protocol.encode_patch(patch)
        if not self._booted:
            self._pending.append(script)
            return
        if self.sender is not None:
            self.sender(script)

    def flush(self) -> None:
        """JS 就绪（``ready``）→ 先推界面骨架，**取数推迟到 tick** ✓

        ⚠ 以前在这里直接 ``query_quotes``（网络 1~3 秒）→ 窗口还没画完就卡住，
        前端一直显示「正在加载合约…」（用户实测的坑）。
        """
        self._booted = True
        # ★ 「改了没生效」排查用：这次跑的是哪份 minibt / 哪个前端 bundle ✓
        self.push_log_once('build', f'版本：{build_fingerprint()}')
        self.push(_protocol.patch_boot(self.theme, self.title,
                                       self.market_map(),
                                       home=bool(self.home_on_boot)))
        from . import user_prefs as _prefs
        values = _prefs.settings()
        self.push({'type': 'settings', 'settings': values})
        self._apply_log_settings(values)
        watch = _prefs.watch()
        self.push({'type': 'watch', **watch})
        self._home_extra = _watch_symbols(watch)[:120]
        if self.no_service:
            # ★ 无行情源：**报价页照样能打开**（只摆本地缓存的合约，不联网 ✓）
            #   连上行情（新建 → 登录期货 / 连接股票）后自动换成实时数据 ✓
            self.push(_protocol.patch_chips(
                _symbols.chips(_symbols.DEFAULT_FUTURES_TYPES),
                self.filter['type']))
            exchanges = self._exchanges_for(self.filter['type'])
            self.filter['exchange'] = exchanges[0][0] if exchanges else ''
            self.push(_protocol.patch_chips(
                _symbols.chips(exchanges), self.filter['exchange'],
                exchanges=True))
            self.push(_protocol.patch_rows_loading())
            self.push(_protocol.patch_status('离线 · 本地数据（未连接行情）'))
            self._reload_pending = True       # tick 里按本地缓存加载 ✓
            for script in self._pending:
                if self.sender is not None:
                    self.sender(script)
            self._pending.clear()
            return
        self.push(_protocol.patch_chips(
            _symbols.chips(_symbols.DEFAULT_FUTURES_TYPES),
            self.filter['type']))
        exchanges = self._exchanges_for(self.filter['type'])
        self.filter['exchange'] = exchanges[0][0] if exchanges else ''
        self.push(_protocol.patch_chips(_symbols.chips(exchanges),
                                        self.filter['exchange'], exchanges=True))
        self.push(_protocol.patch_rows_loading())
        self.push(_protocol.patch_status(
            f'{self.filter["type"]} · {self.filter["exchange"]} · 加载中…'))
        self._reload_pending = True          # 交给 tick() 去真正取数 ✓
        # 全市场合约索引：后台预热（过期才重建 ✓）
        try:
            self.symbol_index()
        except Exception:                                        # noqa: BLE001
            pass
        for script in self._pending:
            if self.sender is not None:
                self.sender(script)
        self._pending.clear()

    @staticmethod
    def _exchanges_for(kind: str) -> list:
        """类型 → 交易所列表（永远返回具体列表，别是空的 ✓）"""
        exchanges = _symbols.DEFAULT_EXCHANGES.get(kind or 'FUT') or []
        return exchanges or [('SHFE', '上期所')]

    def market_map(self) -> Dict[str, Any]:
        """告诉前端哪些行情源可用（股票不可用 → chips 置灰 ✓）"""
        return {
            'futures': bool(self.futures and self.futures.available()),
            'stocks': bool(self.stocks and self.stocks.available()),
            'offline': bool(self.offline or self.no_service),
            'no_service': bool(self.no_service),
        }

    # ======================================================== 首页
    def _home_pairs(self):
        """首页指数 / 自选合约：**优先直接用行情报价里的合约**（用户要求 ✓）

        以前用写死的 `KQ.m@…`（主连）+ 固定清单：
        * 主连不能交易、实盘还打不开图 ✗
        * 首页要再发一轮报价请求（慢 / 会卡）✗
        现在直接用「行情报价当前列表」里**已经有报价**的合约（同源 ✓）：
        按成交量取前几个做「市场全景」，其余做「自选」；列表为空才回退写死清单。
        """
        markets = self.market_map()
        # ★ 市场全景：期货 = **主力 · 中金所**前 4 个（用户要求 ✓）
        #   只有股票时用股票指数 / 龙头 ✓
        if markets['futures']:
            indices = (tuple(self._main_indices)
                       or self._live_main_indices()
                       or self._cached_main_indices()
                       or HOME_FUTURES_INDICES)
            source = 'futures'
        elif markets['stocks']:
            indices = HOME_STOCK_INDICES
            source = 'stocks'
        else:
            return '', (), ()
        # ★ 自选**不再**用后端默认清单（用户要求：除收藏 / 最近打开外，
        #   所有自选都由用户在「行情报价 → 右键 → 加入自选」里添加 ✓）
        #   自选行由 `_home_extra`（收藏 + 用户加入的）补 ✓
        return source, indices[:4], ()

    def _home_rows(self, pairs, *, full: bool = False,
                   allow_spark: bool = None,
                   limit: int = 200,
                   refresh: bool = True) -> List[dict]:
        """首页行：**先用行情报价里已取到的报价**，没有再补拉（最多 12 个 ✓）

        这样首页和「行情报价」是同一份数据（用户要求），也不会因为再发一轮
        请求把实盘卡住 ✓
        """
        pairs = [(str(symbol), str(name or '')) for symbol, name in pairs]
        if not pairs:
            return []
        by_symbol: Dict[str, dict] = {}
        if not refresh:
            for symbol, _ in pairs:
                cached = self._last_rows.get(symbol)
                if cached and cached.get('last') is not None:
                    by_symbol[symbol] = dict(cached)
        # ★ 首页自选每 2 秒刷新时必须重新取行情；以前全部命中
        #   `_last_rows` 缓存 → 股票自选永远停在第一次报价 ✗
        missing = [(symbol, name) for symbol, name in pairs
                   if refresh or symbol not in by_symbol]
        missing = missing[:max(0, int(limit))]
        if missing:
            buckets: Dict[Any, List[tuple]] = {}
            for symbol, name in missing:
                feed = pick_feed(self.feeds, symbol) or self.current_feed()
                buckets.setdefault(feed, []).append((symbol, name))
            for feed, items in buckets.items():
                if feed is None:
                    continue
                try:
                    quotes = feed.quotes([symbol for symbol, _ in items])
                except Exception:                                # noqa: BLE001
                    quotes = []
                for item in quotes or []:
                    if not item:
                        continue
                    symbol = str(item.get('symbol') or '')
                    by_symbol[symbol] = item
                    # ★ 顺手缓存 → 下次只补**还没报价**的 12 个（否则永远
                    #   在补同一批 ✗，主力 40 个合约要滚很久才有价格）
                    if symbol and item.get('last') is not None:
                        self._last_rows[symbol] = item
        rows = []
        for symbol, fallback_name in pairs:
            item = dict(by_symbol.get(symbol) or {})
            name = str(item.get('name') or fallback_name or '')
            if not name:
                name = self._name_of(symbol) or symbol
            item['symbol'] = symbol
            item['name'] = name
            if item.get('decimals') is None:
                item['decimals'] = self.decimals_of(symbol)
            spark = self._spark.get(symbol)
            # ★ 只在**首页可见**时才现算 spark，且最多 4 个（实测：实盘给
            #   16 个合约拉 K 线会卡很久 ✗）；其余用缓存 ✓
            #   `allow_spark` 由调用方决定：**市场全景 4 张卡**即使实盘也允许
            #   （实测每个 0.1~0.2 秒 ✓），自选行则实盘不拉 ✓
            allow = (not getattr(self, '_real_account', False)
                     if allow_spark is None else bool(allow_spark))
            if full and not spark and len(by_symbol) <= 4 and allow:
                try:
                    spark = self.spark_values(symbol, 32)
                except Exception:                                # noqa: BLE001
                    spark = []
            if spark:
                item['spark'] = spark
            rows.append(item)
        return rows

    def home_signals(self, rows: List[dict]) -> List[dict]:
        """首页「今日信号」：用真实涨跌幅 / 成交量生成，不编造策略信号 ✓"""
        valid = [item for item in rows
                 if item.get('last') is not None
                 and item.get('chg_pct') is not None]
        if not valid:
            return []
        ranked = sorted(valid, key=lambda item: float(item.get('chg_pct') or 0))
        picked: List[dict] = []
        seen = set()

        def add(item, tone, badge, text):
            symbol = str(item.get('symbol') or '')
            if symbol in seen:
                return
            seen.add(symbol)
            picked.append({
                'tone': tone, 'badge': badge, 'symbol': symbol,
                'name': str(item.get('name') or ''),
                'text': text,
                'meta': f"{item.get('chg_pct', 0):+.2f}% · 成交 "
                        f"{_compact_num(item.get('volume'))}",
                'time': str(item.get('quote_time') or ''),
            })

        for item in ranked[-2:][::-1]:
            add(item, 'blue', '强势',
                f"涨幅 {float(item.get('chg_pct') or 0):+.2f}%")
        if ranked:
            add(ranked[0], 'amber', '回落',
                f"跌幅 {float(ranked[0].get('chg_pct') or 0):+.2f}%")
        vol = sorted(valid, key=lambda item: -float(item.get('volume') or 0))
        if vol:
            add(vol[0], 'violet', '活跃',
                f"成交量 {_compact_num(vol[0].get('volume'))}")
        return picked[:3]

    @staticmethod
    def home_events() -> List[dict]:
        return [
            {'time': '20:30', 'text': '美国初请失业金人数', 'tail': '宏观',
             'tone': 'amber'},
            {'time': '22:00', 'text': '欧洲央行利率决议', 'tail': '宏观',
             'tone': 'blue'},
        ]

    def home_account(self) -> Dict[str, Any]:
        """首页账户卡：快期模拟 / 富途模拟可切换 ✓

        两个账户可能同时在线；账户卡用 `home_account_kind` 决定显示哪个。
        没登录的那个选项不可用（前端置灰）。
        """
        futures_on = bool(self.futures and self.futures.available())
        stocks_on = bool(self.stocks and self.stocks.available())
        choices = [
            {'kind': 'futures', 'label': '快期模拟', 'available': futures_on},
            {'kind': 'stocks', 'label': '富途模拟', 'available': stocks_on},
        ]
        selected = str(getattr(self, '_home_account_kind', 'futures')
                       or 'futures')
        available = {item['kind'] for item in choices if item['available']}
        if selected not in available:
            selected = ('futures' if futures_on else
                        ('stocks' if stocks_on else 'futures'))
        self._home_account_kind = selected
        view = self.account_view()
        summary: Dict[str, Any] = {}
        if view is not None:
            try:
                if selected == 'futures':
                    symbol = next((name for name in self.tabs
                                   if not _is_stock(name)),
                                  HOME_FUTURES_INDICES[0][0])
                    summary = view.summary(symbol)
                else:
                    symbol = next((name for name in self.tabs
                                   if _is_stock(name)), 'SH.600000')
                    summary = view.summary(symbol)
            except Exception:                                    # noqa: BLE001
                summary = {}
        label = next((item['label'] for item in choices
                      if item['kind'] == selected), '快期模拟')
        result = dict(summary or {})
        result.update({
            'kind': selected,
            'label': label,
            'labels': [item['label'] for item in choices],
            'index': 0 if selected == 'futures' else 1,
            'choices': choices,
        })
        return result

    def _on_home_account_kind(self, payload=None) -> None:
        """首页账户卡切换快期模拟 / 富途模拟 ✓"""
        kind = str((payload or {}).get('kind') or '').lower()
        if kind not in ('futures', 'stocks'):
            return
        if kind == 'futures' and not (self.futures and self.futures.available()):
            return
        if kind == 'stocks' and not (self.stocks and self.stocks.available()):
            return
        self._home_account_kind = kind
        self.push({'type': 'home_account', 'account': self.home_account()})

    def home_payload(self, *, full: bool = True,
                     symbols=None) -> Dict[str, Any]:
        """首页补丁：连接状态 + 指数 + 自选 + 信号 + 账户 ✓"""
        markets = self.market_map()
        if symbols is not None:
            rows = self._home_rows([(str(item), '') for item in symbols],
                                   full=False)
            return {'type': 'home_symbols', 'rows': rows}
        source, index_pairs, watch_pairs = self._home_pairs()
        if not source:
            return {'type': 'home', 'markets': markets, 'empty': True,
                    'indices': [], 'watchlist': [], 'signals': [],
                    'events': self.home_events(), 'account': {}}
        indices = self._home_rows(index_pairs, full=full,
                                  allow_spark=True)
        watchlist = self._home_rows(watch_pairs, full=full)
        # ★ 收藏 / 各分组手动加入的合约也并进自选（实时跟着刷 ✓）
        if self._home_extra:
            known = {str(item.get('symbol')) for item in watchlist}
            extra_pairs = [(symbol, '') for symbol in self._home_extra
                           if symbol not in known][:60]
            if extra_pairs:
                watchlist = watchlist + self._home_rows(extra_pairs,
                                                        full=full)
        if source == 'stocks' and indices and not any(
                item.get('last') is not None for item in indices):
            indices = watchlist[:4]
        payload = {
            'type': 'home',
            'markets': markets,
            'source': source,
            'indices': indices,
            'watchlist': watchlist,
            # 自选为空时（默认）用**市场全景**的行情算信号 ✓
            'signals': self.home_signals(watchlist or indices),
            'events': self.home_events(),
            'account': self.home_account(),
            'empty': False,
        }
        return payload

    def _live_main_indices(self) -> tuple:
        """从天勤合约清单取「主力 · 中金所」前 4 个**真实合约** ✓

        首页不再优先用 `KQ.m@CFFEX.IF` 这种主连：某些时点天勤会把主连
        映射到服务端不存在的标的（`rb2701` 实测），订阅后整个行情泵报错。
        合约清单是异步的，第一次可能为空 → 下一拍首页刷新再取 ✓。
        """
        feed = getattr(self, 'futures', None)
        if feed is None or not getattr(feed, 'available', lambda: False)():
            return ()
        getter = getattr(feed, 'contracts', None)
        if not callable(getter):
            return ()
        try:
            rows = list(getter('CONT_MAIN', 'CFFEX') or [])
        except Exception:                                        # noqa: BLE001
            rows = []
        picks = []
        for symbol in rows[:4]:
            symbol = str(symbol or '')
            if not symbol:
                continue
            name = ''
            try:
                name = str(feed.name_of(symbol) or '')
            except Exception:                                    # noqa: BLE001
                name = ''
            picks.append((symbol, name))
        if len(picks) >= 4:
            self._main_indices = picks
            return tuple(picks)
        return ()

    def _cached_main_indices(self) -> tuple:
        """从合约缓存里读「主力 · 中金所」前 4 个（不用联网 ✓）

        这样**刚启动、还没打开行情报价**时，市场全景也是真实主力合约
        （`CFFEX.IC2612` 这种），和行情报价「主力 · 中金所」一致 ✓
        """
        try:
            cache = self.symbol_cache()
            rows = cache.get('CONT_MAIN:CFFEX') if cache is not None else None
        except Exception:                                        # noqa: BLE001
            rows = None
        picks = [(str(row.get('symbol')), str(row.get('name') or ''))
                 for row in rows or []
                 if str(row.get('symbol') or '').upper().startswith('CFFEX.')]
        return tuple(picks[:4]) if len(picks) >= 4 else ()

    def _remember_main_indices(self, rows: List[dict]) -> None:
        """行情页拉到「主力」时，记下**中金所前 4 个**（首页市场全景 ✓）"""
        if (self.filter.get('type') or '') != 'CONT_MAIN':
            return
        picks = [(str(row.get('symbol')), str(row.get('name') or ''))
                 for row in rows or []
                 if str(row.get('symbol') or '').upper().startswith('CFFEX.')]
        if len(picks) >= 4:
            self._main_indices = picks[:4]

    def _quotes_blocked(self) -> bool:
        """数据请求是否处于「冷静期」（慢请求 → 先停几秒 ✓）

        实盘里给**没订阅 / 没权限**的合约取报价，tqsdk 会阻塞到超时；
        目前只在「慢请求」时生效（保留给以后的代理层用 ✓）。
        """
        seen = getattr(self, '_timeout_seen', 0)
        for feed in self.feeds:
            api = getattr(feed, 'api', None)
            timeouts = getattr(api, 'timeouts', None)
            if not timeouts:
                continue
            if len(timeouts) != seen:
                self._timeout_seen = len(timeouts)
                self._quotes_block_until = time.monotonic() + 5.0
                self.push_log(
                    f'行情取数超时：{getattr(api, "last_timeout", "")}'
                    '→ 暂停 5 秒再试', 'warning')
                return True
        return time.monotonic() < getattr(self, '_quotes_block_until', 0.0)

    def _refresh_home(self) -> None:
        """首页可见时，每 2 秒更新一次价格 / 信号（不拉全市场）✓"""
        if not self._home_active:
            return
        now = time.monotonic()
        if now - self._home_at < 2.0:
            return
        self._home_at = now
        # 主力列表当时为空（TqSdk symbols 还没下来）→ 自动补查一次 ✓
        retry = str(getattr(self, '_home_main_retry_exchange', '') or '')
        if retry and now >= float(
                getattr(self, '_home_main_retry_at', 0.0) or 0.0):
            self._home_main_retry_exchange = ''
            self._home_main_retry_at = 0.0
            try:
                self._on_home_main({'exchange': retry})
            except Exception:                                    # noqa: BLE001
                pass
        payload = self.home_payload(full=False)
        payload['type'] = 'home_update'
        self.push(payload)

    # ======================================================== 数据
    def symbol_cache(self):
        """合约清单缓存（惰性建库；失败 → ``None`` 而不是抛错 ✓）"""
        if not self._cache_ready:
            self._cache_ready = True
            try:
                from .symbol_cache import SymbolCache
                self._cache = SymbolCache()
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 合约缓存不可用: {error!r}')
                self._cache = None
        return self._cache

    def api_ready(self) -> bool:
        """当前行情源有没有 api（下单/账户都靠它 ✓）"""
        feed = self.current_feed()
        return bool(feed is not None and getattr(feed, 'api', None) is not None)

    def current_feed(self) -> Optional[BaseFeed]:
        """当前筛选对应的行情源 ✓"""
        kind = self.filter.get('type') or 'FUT'
        if kind == 'STOCK':
            return self.stocks
        return self.futures or self.stocks

    def feed_of(self, symbol: str = ''):
        """某合约所属的行情源（**下单 / 账户以它为准** ✓）

        以前 `Trading` / `AccountView` 都用 `current_feed()` —— 那个只跟着
        **报价页的类型筛选**走：报价页停在「股票」时，在看盘页给期货合约下单
        会被发到**股票本地模拟盘**（日志显示下单成功、成交，但天勤账户没持仓 ✗）。
        现在优先按合约前缀选行情源 ✓
        """
        symbol = str(symbol or '').strip()
        if symbol:
            feed = pick_feed(self.feeds, symbol)
            if feed is not None and getattr(feed, 'api', None) is not None:
                return feed
        # 没有符号 → 用当前**打开着的看盘 tab**（再退回报价页筛选）
        for key in list(self.tabs):
            feed = pick_feed(self.feeds, key)
            if feed is not None and getattr(feed, 'api', None) is not None:
                return feed
        return self.current_feed()

    def reload_rows(self) -> None:
        """按当前筛选重新加载（合约清单走缓存，首屏**分块**推送 ✓）"""
        label = f'{self.filter.get("type") or ""} · ' \
                f'{self.filter.get("exchange") or ""}'
        if self.no_service:
            # 离线：只摆**本地缓存**的合约（连上行情后自动换成实时数据 ✓）
            rows = self._cached_rows()
            for index, block in enumerate(_protocol.chunked(rows)):
                self.push(_protocol.patch_rows(block, replace=index == 0))
            if not rows:
                self.push(_protocol.patch_rows([], replace=True))
            self._last_rows = {str(item.get('symbol')): item for item in rows}
            self._search_pool = []
            self._rows_at = time.monotonic()
            if rows:
                self.push(_protocol.patch_status(
                    f'{label} · {len(rows)} 行（离线 · 本地缓存）'))
                self.push_log(
                    f'{label}：离线显示本地缓存的 {len(rows)} 个合约'
                    '（行情不更新，登录后自动刷新）', 'info')
            else:
                self.push(_protocol.patch_status(
                    f'{label} · 0 行（离线 · 无本地缓存）'))
                self.push_log(
                    '离线：还没有本地合约缓存 →「新建 → 登录期货 / 连接股票」'
                    '连上行情后自动加载', 'warning')
            return
        # ★ 合约清单在**主线程**拉：名称已改成小批补（不再一次
        #   `query_symbol_info` 几千个）→ 这里只剩 `query_quotes`（本地
        #   缓存，**不会卡界面**）。反过来，放到后台线程会跨线程碰 tqsdk
        #   → 主线程 `pump()` 抢锁卡死（实盘实测 ✗）
        key = (self.filter.get('type') or '', self.filter.get('exchange') or '')
        bust = bool(getattr(self, '_cache_bust', False))
        if (getattr(self, '_real_account', False) and not bust
                and not self._cached_rows()):
            # ★ 实盘：后台**不主动**查合约（`query_quotes` 会卡 30 秒 ✗）
            #   第一次请点「刷新」；之后再进来自动用缓存 ✓
            self.push(_protocol.patch_rows([], replace=True))
            self.push(_protocol.patch_status(
                f'{label} · 0 行（点「刷新」加载合约）'))
            self.push_log_once(f'contracts-manual-{label}',
                               f'{label}：实盘不自动查合约，请点「刷新」加载一次'
                               '（之后会缓存 ✓）', 'info')
            return
        # ★ miniqt 同款：换类型 / 交易所先秒开本地缓存，再在后台更新
        #   （合约清单每天更新一次；不能因为网络查询没回来就让页面空着 ✗）
        fresh_rows = ([] if getattr(self, '_cache_bust', False)
                      else self._cached_rows())
        stale_rows = ([] if fresh_rows or getattr(self, '_cache_bust', False)
                      else self._cached_rows(allow_stale=True))
        cached = fresh_rows or stale_rows
        if (key in self._skip_markets
                and not getattr(self, '_cache_bust', False) and not cached):
            # 这个组合之前取不到 → 直接给空表（不再请求 ✓）
            self.push(_protocol.patch_rows([], replace=True))
            self.push(_protocol.patch_status(f'{label} · 0 行（已跳过）'))
            return
        # 缓存当天有效：新鲜缓存只秒开，不再每次切筛选都发网络查询；
        # 过期 / 手动刷新 / 没有缓存才联网更新 ✓
        fresh = False
        try:
            cache_obj = self.symbol_cache()
            age_fn = getattr(cache_obj, 'age', None) if cache_obj else None
            age = age_fn(self._cache_key()) if callable(age_fn) else None
            # 老缓存对象没有 age()（测试 / 外部实现）→ 仍按命中缓存处理 ✓
            fresh = bool(fresh_rows and (age is None or age <= float(
                getattr(cache_obj, 'ttl', 0) or 0)))
        except Exception:                                    # noqa: BLE001
            fresh = False
        self._rows_from_cache = bool(cached and not fresh)
        if cached:
            for index, block in enumerate(_protocol.chunked(cached)):
                self.push(_protocol.patch_rows(block, replace=index == 0))
            self._last_rows = {str(item.get('symbol')): item for item in cached}
            self._search_pool = []
            self._rows_at = time.monotonic()
            self.push(_protocol.patch_status(
                f'{label} · {len(cached)} 行（本地缓存 · 更新中）'))
            self._refresh_ticker(cached)
            if fresh:
                self.push(_protocol.patch_status(
                    f'{label} · {len(cached)} 行（本地缓存）'))
                return
        else:
            self.push(_protocol.patch_rows_loading(f'正在加载 {label} 合约…'))
            self.push(_protocol.patch_status(f'{label} · 加载中…'))
        self._rows_gen += 1
        gen = self._rows_gen
        self._rows_label = label
        try:
            rows = self._rows_for_filter(force=bool(cached))
            error = None
        except Exception as error_:                              # noqa: BLE001
            rows = []
            error = error_

        self._rows_result = (gen, rows, error)
        self._drain_rows_result()

    def _retry_empty_rows(self) -> None:
        """登录后 TqSdk 符号字典/异步查询还没好 → 2 秒后自动重试 ✓

        以前第一次 `CONT_MAIN · DCE` 取空就写进 `_skip_markets`，之后
        永远不再请求，只能手动点「刷新」→ 用户看到期货一直没数据 ✗。
        `_fast_call` 已保证请求不阻塞，所以这里自动重试。
        """
        at = float(getattr(self, '_empty_rows_retry_at', 0.0) or 0.0)
        if not at or time.monotonic() < at:
            return
        self._empty_rows_retry_at = 0.0
        if self._rows_loading or not self.futures:
            return
        # 只有当前确实是期货筛选才重试（股票空表不要误刷）
        feed = self.current_feed()
        if getattr(feed, 'kind', '') != 'futures':
            return
        key = (self.filter.get('type') or '',
               self.filter.get('exchange') or '')
        self._skip_markets.discard(key)
        # ★ 不要每 2 秒重置异步查询：miniqt 实测 DCE 的 query_quotes
        #   可能要 1~2 分钟才回；自动重试只读 pending，手动刷新才 force ✓
        self.reload_rows()

    def _drain_rows_result(self) -> None:
        """主线程：把后台拉回来的合约推给前端（`tick()` 里调用 ✓）"""
        result = self._rows_result
        if result is None:
            return
        self._rows_result = None
        gen, rows, error = result
        self._rows_loading = False
        label = self._rows_label or ''
        if gen != self._rows_gen:
            # 期间切过筛选 → 这份结果过期了，用最新的一次 ✓
            if self._rows_pending:
                self._rows_pending = False
                self._reload_pending = True
            return
        from_cache = bool(getattr(self, '_rows_from_cache', False))
        if error is not None or (not rows and from_cache):
            # 网络刷新失败 / 异步查询还没回来：**保留刚推的本地缓存**，
            # 不把列表清空；2 秒后再试 ✓
            self._rows_from_cache = False
            if from_cache:
                self._empty_rows_retry_at = time.monotonic() + 2.0
                self.push(_protocol.patch_status(
                    f'{label} · 本地缓存 · 行情更新中…'))
                if self._empty_rows_retry_key != label:
                    self._empty_rows_retry_key = label
                    self.push_log(f'{label}：本地缓存已显示，行情更新稍后重试…',
                                  'info')
                return
            self.push_log(f'加载合约失败（{label}）：{error!r}', 'error')
            self.push(_protocol.patch_toast(
                f'加载合约失败：{error!r}', 'error'))
            self.push(_protocol.patch_rows([], replace=True))
            self.push(_protocol.patch_status(f'{label} · 加载失败'))
        else:
            self._rows_from_cache = False
            chunks = _protocol.chunked(rows)
            for index, block in enumerate(chunks):
                self.push(_protocol.patch_rows(block, replace=index == 0))
            if not chunks:
                self.push(_protocol.patch_rows([], replace=True))
            self._last_rows = {str(item.get('symbol')): item for item in rows}
            self._search_pool = []      # 合约集合变了 → 搜索池重建 ✓
            self._rows_at = time.monotonic()
            self._refresh_ticker(rows)
            if not rows and self.futures is not None and not self.offline:
                # ★ 天勤刚登录时 symbols 可能还没到 → **不要永久跳过**；
                #   2 秒后自动重试（之前会一直 0 行，只能手动刷新 ✗）
                key = (self.filter.get('type') or '',
                       self.filter.get('exchange') or '')
                self._skip_markets.discard(key)
                self._empty_rows_retry_at = time.monotonic() + 2.0
                if self._empty_rows_retry_key != str(key):
                    self._empty_rows_retry_key = str(key)
                    self.push_log(
                        f'{label}：行情源初始化中，2 秒后自动重试…', 'info')
            elif rows:
                self._skip_markets.discard(
                    (self.filter.get('type') or '',
                     self.filter.get('exchange') or ''))
                self._remember_main_indices(rows)
            if rows:
                self.push(_protocol.patch_status(
                    f'{label} · {len(rows)} 行'))
            else:
                detail = '该类型/交易所暂无合约' if not self.offline                     else '离线演示数据为空'
                self.push(_protocol.patch_status(
                    f'{label} · 0 行（{detail}）'))
                # 说明：上面已经写过一条「清单为空」，这里不再重复刷屏 ✓
                pass
        if self._rows_pending:
            self._rows_pending = False
            self._reload_pending = True

    def _cache_key(self) -> str:
        """当前筛选 → 缓存 key（和 `_rows_for_filter` 保持一致 ✓）"""
        feed = self.current_feed()
        kind = 'stock' if (feed is not None and feed.kind == 'stocks') else 'fut'
        if kind == 'stock':
            return 'stock:' + (self.filter.get('exchange') or '')
        return '%s:%s' % (self.filter.get('type') or 'FUT',
                          self.filter.get('exchange') or '')

    def _queue_missing_names(self, rows: List[dict]) -> None:
        """把没有名称的行排队（主线程小批补 ✓；缓存里名称常常是空）"""
        if getattr(self.current_feed(), 'kind', '') != 'futures':
            return
        missing = [str(item.get('symbol')) for item in rows or []
                   if item.get('symbol') and not item.get('name')]
        if missing:
            self._name_queue = missing[:3000]

    def _valid_rows(self, rows: List[dict]) -> List[dict]:
        """丢掉**明显属于别的交易所**的缓存行（脏缓存会让列表只剩一条 ✗）

        只对「已知交易所前缀」做校验：`CACHED.1` 这种不认识的照旧保留 ✓
        """
        exchange = (self.filter.get('exchange') or '').upper()
        if not exchange:
            return list(rows)
        known = _symbols.known_exchanges()
        out = []
        for item in rows or []:
            symbol = str(item.get('symbol') or '')
            prefix = symbol.split('.')[0].upper() if '.' in symbol else ''
            if prefix and prefix in known and prefix != exchange:
                continue          # 别的交易所的脏行 → 丢掉 ✓
            out.append(item)
        return out

    def _cached_rows(self, allow_stale: bool = False) -> List[dict]:
        """本地缓存的合约（`allow_stale=True` = 过期也显示，先兜底 ✓）"""
        cache = self.symbol_cache()
        if cache is None:
            return []
        try:
            getter = getattr(cache, 'get_any' if allow_stale else 'get')
            return self._valid_rows(list(getter(self._cache_key()) or []))
        except Exception:                                        # noqa: BLE001
            return []

    def _rows_for_filter(self, force: bool = False) -> List[dict]:
        """当前筛选的合约行（缓存优先；过期 / force 才联网 ✓）"""
        feed = self.current_feed()
        kind = 'stock' if (feed is not None and feed.kind == 'stocks') else 'fut'
        key = ('stock:' + (self.filter.get('exchange') or '')
               if kind == 'stock'
               else '%s:%s' % (self.filter.get('type') or 'FUT',
                               self.filter.get('exchange') or ''))
        if self.no_service:
            return self._cached_rows(allow_stale=True)  # 离线：旧缓存也显示 ✓
        if self.offline or feed is None or not feed.available():
            return offline_rows(60)
        bust = bool(getattr(self, '_cache_bust', False))
        self._cache_bust = False
        cache = self.symbol_cache()
        if cache is not None and not bust and not force:
            cached = cache.get(key)
            if cached:
                # ★ 缓存里混了别的交易所（脏数据 / 换 key 规则）→ 当作未命中 ✗
                cleaned = self._valid_rows(list(cached))
                if cleaned:
                    self._queue_missing_names(cleaned)
                    return cleaned
        rows = self._fetch_rows(feed, bust=bust)
        if cache is not None and rows:
            try:
                cache.put(key, rows)
            except Exception:                                    # noqa: BLE001
                pass
        return rows

    def _fetch_rows(self, feed, bust: bool = False) -> List[dict]:
        """联网拉一次合约清单（期货补名称；股票自带名称 ✓）"""
        if feed.kind == 'stocks':
            market = self.filter.get('exchange') or 'SSE'
            rows = feed.stock_rows(market)
            if not rows:
                from . import stocks as _stocks
                reason = getattr(_stocks, 'last_error', '') or \
                    'FutuOpenD 未返回数据（检查是否登录 / 是否有行情权限）'
                self.push_log(f'股票清单为空（{market}）：{reason}', 'warning')
                self.push(_protocol.patch_toast(
                    f'股票清单为空：{reason}', 'warning'))
            return rows
        ins_class = self.filter.get('type') or 'FUT'
        exchange = self.filter.get('exchange') or 'SHFE'
        # ★ 先读本地符号（`TqApi` 启动时已下载）；没有再退回联网接口。
        #   联网接口（`query_quotes` / `query_cont_quotes`）在实盘里可能
        #   阻塞 30 秒 → 先用手上有的，别让界面卡住 ✗
        if isinstance(feed, FuturesFeed):
            # ① 本地符号字典（`query_quotes` 之后才有的缓存）✓
            symbols = list(feed.contracts_local(ins_class, exchange) or [])
            if not symbols:
                cached = self._cached_rows()
                if cached and not bust:
                    return cached
            # ② 都没有 → 主线程查（`expired=False` 只要未下市合约，实测 0.02s ✓）
            if not symbols:
                try:
                    symbols = list(feed.contracts(ins_class, exchange) or [])
                except Exception as error:                       # noqa: BLE001
                    self.push_log(
                        f'{ins_class}/{exchange} 取合约失败：{error!r}',
                        'warning')
                    if '超时' in str(error) or 'Timeout' in type(
                            error).__name__:
                        self.push(_protocol.patch_toast(
                            '查询合约超时（tqsdk 30 秒）→ 再点一次「刷新」'
                            '，或直接打开图表', 'warning'))
                    symbols = []
        else:
            symbols = feed.contracts(ins_class, exchange)
        rows = []
        missing: List[str] = []
        for symbol in symbols:
            name = feed.name_of(symbol) or self._name_of(symbol)
            if not name:
                missing.append(symbol)
            rows.append(_symbols.row(symbol=symbol, name=name))
        # ★ 名称**不再查** `query_symbol_info`（会把 tqsdk 的 ins_query
        #   通道搞乱 → 之后所有查询 30 秒超时，实盘实测 ✗）：
        #   报价里自带 `instrument_name`，行情一刷名称就补上了 ✓
        return rows

    def _fill_names_step(self, batch: int = 120) -> None:
        if self._quotes_blocked():
            return
        """把缺名称的合约**分小批**补上（太大会让切报价页卡死 ✗）"""
        if not self._name_queue:
            return
        now = time.monotonic()
        if now - self._name_at < 0.4:
            return
        self._name_at = now
        feed = self.current_feed()
        if feed is None or getattr(feed, 'kind', '') != 'futures':
            self._name_queue = []
            return
        items = self._name_queue[:batch]
        self._name_queue = self._name_queue[batch:]
        try:
            feed.fill_names(items)
        except Exception:                                        # noqa: BLE001
            return
        updated = []
        for symbol in items:
            name = feed.name_of(symbol)
            if not name:
                continue
            row = self._last_rows.get(symbol)
            if row is None or row.get('name') == name:
                continue
            row['name'] = name
            updated.append(_symbols.row(**row))
        if updated:
            self.push(_protocol.patch_rows_update(updated))

    def _name_of(self, symbol: str) -> str:
        """从**全市场索引**里兜底取名称（缓存/接口都可能缺 ✓）"""
        try:
            for row in self.symbol_index() or []:
                if row.get('symbol') == symbol:
                    return str(row.get('name') or '')
        except Exception:                                        # noqa: BLE001
            return ''
        return ''

    # -------------------------------------------------------- 播放条
    def _ticker_only_quoted(self) -> bool:
        """播放条是否只显示**有报价**的合约（`settings.ticker_only_quoted` ✓）"""
        from . import user_prefs as _prefs
        value = _prefs.settings().get('ticker_only_quoted')
        return value is True or value == 1 or value == 'true'

    def _refresh_ticker(self, rows: List[dict], limit: int = 12) -> None:
        """底部播放条（Ticker-Tape）：按成交量取前 N ✓

        ⚠ 合约清单里的行**没有** `last` / `chg_pct`（那是报价才有的）——
        直接用它们会导致播放条只显示名字（用户实测 ✗）。
        这里把 ``self._last_rows``（最新报价）合并进来，价格 / 涨跌幅就有了 ✓
        """
        if not rows:
            return
        self._ticker_source = list(rows)      # 开关切换时重推用 ✓
        # 记一下「代码 → 中文名」（报价行可能没有名字 ✓）
        names = getattr(self, '_ticker_names', None)
        if names is None:
            names = self._ticker_names = {}
        for row in rows:
            symbol = str(row.get('symbol') or '')
            if symbol and str(row.get('name') or '').strip():
                names[symbol] = str(row['name'])
        merged = []
        for row in rows:
            symbol = str(row.get('symbol') or '')
            latest = self._last_rows.get(symbol) or {}
            item = dict(row)
            for key in ('last', 'chg', 'chg_pct', 'volume', 'decimals'):
                if latest.get(key) is not None:
                    item[key] = latest[key]
            # 报价行里的 name 可能是空 / 就是代码 → 保留清单里的中文名 ✓
            if not str(item.get('name') or '').strip()                     or item.get('name') == item.get('symbol'):
                item['name'] = (row.get('name')
                                or names.get(str(item.get('symbol') or ''))
                                or '')
            merged.append(item)
        if self._ticker_only_quoted():
            merged = [item for item in merged
                      if item.get('last') is not None]
        if not merged:
            return
        ranked = sorted(merged, key=lambda item: -(item.get('volume') or 0.0))
        items = [{'symbol': str(item.get('symbol') or ''),
                  'name': str(item.get('name') or ''),
                  'last': item.get('last'),
                  'chg': item.get('chg'),
                  'chg_pct': item.get('chg_pct'),
                  'decimals': item.get('decimals')}
                 for item in ranked[:limit] if item.get('symbol')]
        if items:
            self.push(_protocol.patch_ticker(items))

    # -------------------------------------------------------- 小数位
    def chart_lengths(self) -> tuple:
        """`(history, data_length)` —— 设置页「图表配置」的两个根数 ✓

        * ``history``：最多加载多少根（往左能翻多远）
        * ``data_length``：初始显示多少根（右侧偏移）
        """
        from . import user_prefs as _prefs
        values = _prefs.settings()

        def _num(key: str, default: int) -> int:
            try:
                return max(100, min(20000, int(values.get(key) or default)))
            except (TypeError, ValueError):
                return default

        history = _num('chart_history', 1000)
        data_length = _num('chart_data_length', 1000)
        return history, min(data_length, history)

    def data_length(self) -> int:
        """首屏加载多少根（`chart_data_length`；无限历史开启时 < 历史长度 ✓）"""
        return int(self.chart_lengths()[1])

    def candles_length(self) -> int:
        """请求 K 线用多少根（`chart_history` ✓）"""
        return int(self.chart_lengths()[0])

    def tab_length(self, info: dict = None) -> int:
        """当前图表应使用的 K 线长度。

        初始 = **设置 → 图表配置 → 期货数据长度**（`chart_data_length`）；
        用户向左加载无限历史后 = 已加载根数（至少仍是该设置值）。
        指标 / 策略 / K 线必须共用这个长度，否则左侧会出现“只有指标线”✗。
        """
        try:
            loaded = int((info or {}).get('loaded_len') or 0)
        except (TypeError, ValueError):
            loaded = 0
        return max(int(self.data_length() or 0), loaded)

    # ---- K 线「已推了什么」的状态（全量 / 增量判断用 ✓）----
    @staticmethod
    def _note_kline_state(info: dict, bars, frame_len: int = 0) -> None:
        """刚给前端**全量**推了一帧 → 记下根数 / 首尾时间 ✓

        ⚠ `_kline_bars_len` 存的是**有数据的根数**（占位行不算）；
        `frame_len` 只是天勤那张表的原始长度（定长，仅排查用）。
        下次 `_refresh_tabs` 用它们判断要不要再全量替换 ✓。
        """
        bars = list(bars or [])
        info['_kline_frame_len'] = int(frame_len or 0)
        info['_kline_bars_len'] = len(bars)
        info['_kline_first_time'] = int(
            (bars[0].get('time') if bars else 0) or 0)
        info['_kline_time'] = int((bars[-1].get('time') if bars else 0) or 0)
        info['_kline_close'] = float(
            (bars[-1].get('close') if bars else 0.0) or 0.0)
        info['_kline_at'] = time.monotonic()

    @staticmethod
    def _reset_kline_state(info: dict) -> None:
        """下一拍必须**全量**重推（切周期 / 换合约 / 重登行情源 ✓）"""
        for key in ('_kline_frame_len', '_kline_bars_len', '_kline_first_time',
                    '_kline_time', '_kline_close', '_kline_at'):
            info.pop(key, None)

    def decimals_of(self, symbol: str, default: int = 2) -> int:
        """合约小数位（**全站唯一来源**：报价页 / 二级报价 / 买卖盘 /
        气泡 / 持仓表 / 预警 都走它 ✓）

        依次尝试：最近报价行的 `price_tick` → `feed.spec()` 的 `price_tick`
        → `default`（股票 2 位 ✓）。结果缓存在 `self._decimals_cache`。
        """
        symbol = str(symbol or '')
        if not symbol:
            return default
        cache = getattr(self, '_decimals_cache', None)
        if cache is None:
            cache = self._decimals_cache = {}
        if symbol in cache:
            return cache[symbol]
        tick = _num_local((self._last_rows.get(symbol) or {}).get('price_tick'))
        if not tick:
            # 报价行里找同合约（持仓给的是 `rb2610`，报价行键是 `SHFE.rb2610` ✓）
            bare = symbol.split('.')[-1]
            for key, item in self._last_rows.items():
                if key == symbol or str(key).split('.')[-1] == bare:
                    tick = _num_local((item or {}).get('price_tick'))
                    if tick:
                        break
        if not tick:
            # ★ 以前这里会 `feed.spec()` → `api.get_quote(symbol)`：
            #   在**实盘**下会给主连等合约发订阅请求，把 tqsdk 的
            #   ins_query 通道弄坏 → 之后的 `query_quotes` 全部 30 秒超时 ✗
            #   现在只用**缓存**，缺的排进 `_decimals_queue` 由 tick 小批补 ✓
            queue = getattr(self, '_decimals_queue', None)
            if queue is None:
                queue = self._decimals_queue = []
            if symbol not in queue and len(queue) < 500:
                queue.append(symbol)
            return default
        value = _symbols.decimals_from_tick(tick) if tick else default
        cache[symbol] = value
        return value

    def _fill_decimals_step(self, batch: int = 5) -> None:
        """小批补合约小数位（**不阻塞**：每次最多 5 个，独占时不跑 ✓）"""
        queue = getattr(self, '_decimals_queue', None)
        if not queue or getattr(self, '_api_exclusive', False):
            return
        if getattr(self, '_real_account', False):
            # 实盘：`get_quote` 也可能阻塞 → 小数位先用默认值 ✓
            self._decimals_queue = []
            return
        now = time.monotonic()
        if now - getattr(self, '_decimals_at', 0.0) < 0.5:
            return
        self._decimals_at = now
        feed = self.current_feed()
        spec = getattr(feed, 'spec', None)
        if not callable(spec):
            self._decimals_queue = []
            return
        cache = getattr(self, '_decimals_cache', None) or {}
        for symbol in queue[:batch]:
            try:
                quote = spec(symbol)
            except Exception:                                    # noqa: BLE001
                quote = None
            tick = _num_local(_field_local(quote, 'price_tick'))
            if tick:
                cache[symbol] = _symbols.decimals_from_tick(tick)
                price = _num_local(_field_local(quote, 'last_price'))
                if price:
                    self._last_rows.setdefault(symbol, {})['price_tick'] = tick
        self._decimals_cache = cache
        self._decimals_queue = queue[batch:]

    # -------------------------------------------------------- 走势 / 气泡
    def spark_values(self, symbol: str, points: int = 40) -> list:
        """走势 spark：最近 ``points`` 个 **1 分钟**收盘（有缓存 ✓）"""
        cached = self._spark.get(symbol)
        if cached:
            return cached
        # 取过但没数据（停牌 / 没权限）→ 2 分钟内不再重试 ✓
        miss = self.__dict__.setdefault('_spark_miss', {})
        if time.monotonic() - float(miss.get(symbol) or 0) < 120:
            return []
        feed = pick_feed(self.feeds, symbol) or self.current_feed()
        if feed is None or not feed.available():
            return []
        # ★ 股票：优先用**已订阅的缓存帧**（`stock_api._frames`），不额外请求
        #   —— 以前股票直接 `return`，行情页那列永远是空的（用户反馈 ✗）
        if getattr(feed, 'kind', '') == 'stocks' and _is_stock(symbol):
            frames = getattr(feed.api, '_frames', None) or {}
            from .stocks import to_futu_code as _to_code
            code = _to_code(symbol)
            # ⚠ 不能用 `a or b`：DataFrame 的 bool 会抛
            #   "truth value of a DataFrame is ambiguous" ✗
            frame = frames.get((code, 60))
            for period in (300, 900, 1800, 86400):
                if frame is not None and len(frame):
                    break
                frame = frames.get((code, period))
            if frame is None or not len(frame):
                # 缓存里没有 → 走**历史额度**拉日线（不占 100 个订阅额度 ✓）
                getter = getattr(getattr(feed, 'api', None), 'history_bars', None)
                if callable(getter):
                    try:
                        frame = getter(symbol, 86400, 120)
                    except Exception:                            # noqa: BLE001
                        frame = None
                    if frame is None or not len(frame):
                        miss[symbol] = time.monotonic()
            # ⚠ 不再为了 spark 去订阅 K 线：富途正股**订阅额度只有 100**，
            #   每只股票拉一次日线会瞬间把额度用光（用户实测：浏览列表时
            #   `订阅额度不足 100/100` 刷屏 ✗）→ 只用**已订阅的缓存帧** ✓
        else:
            frame = feed.klines(symbol, 60, 120)
        closes: list = []
        try:
            if frame is not None and len(frame):
                closes = [float(value) for value in
                          frame['close'].tail(120).tolist()
                          if value == value]
        except Exception:                                        # noqa: BLE001
            closes = []
        if len(closes) > points:      # 等间隔抽稀（末位对齐最新一根 ✓）
            step = len(closes) / float(points)
            closes = [closes[min(int(index * step), len(closes) - 1)]
                      for index in range(points - 1)] + [closes[-1]]
        if closes:
            self._spark[symbol] = closes
        return closes

    # -------------------------------------------------------- 刷新
    def stock_pool_codes(self, limit: int = 40) -> List[str]:
        """「全局股票池」= 自选 / 收藏里的**股票**（miniqt 同款 ✓）

        期货不需要富途订阅（走天勤），所以这里只挑股票；数量按 `limit`
        截断，避免把 100 个正股额度吃满 ✓
        """
        try:
            from . import user_prefs as _prefs
            watch = _prefs.watch() or {}
        except Exception:                                        # noqa: BLE001
            return []
        codes: List[str] = []
        for symbol in watch.get('favorites') or []:
            if _is_stock(symbol) and symbol not in codes:
                codes.append(str(symbol))
        for group in watch.get('groups') or []:
            for symbol in (group or {}).get('symbols') or []:
                if _is_stock(symbol) and symbol not in codes:
                    codes.append(str(symbol))
        return codes[:max(0, int(limit))]

    def _sync_stock_pool(self, feed) -> None:
        """把「自选股票」灌进订阅池的 `pool` 来源（进池即订阅 ✓）"""
        from .stocks import to_futu_code as _to_code
        pool = getattr(self, '_stock_pool', None)
        if pool is None or pool.api is not getattr(feed, 'api', None):
            from .stocks import SubscriptionPool as _Pool
            pool = _Pool(getattr(feed, 'api', None))
            self._stock_pool = pool
        # 自选可能会变（首页加/删自选）→ 每 5 秒才重算一次 ✓
        now = time.monotonic()
        if now - float(getattr(self, '_pool_at', 0) or 0) < 5.0:
            return
        self._pool_at = now
        try:
            pool.set_owner('pool', [_to_code(code)
                                    for code in self.stock_pool_codes()])
        except Exception:                                        # noqa: BLE001
            pass

    def _refresh_visible(self) -> None:
        if self._quotes_blocked():
            return
        """只更新**可见行**（6496 行的表也扛得住 ✓）

        ⚠ 以前直接用前端上报的 `visible`（可能是**上一个筛选**留下的）→
        主力表里会混进别的交易所的合约 ✗。现在只认**当前清单里**的合约 ✓
        """
        feed = self.current_feed()
        known = self._last_rows
        keys = [key for key in (self.visible or [])
                if not known or key in known]
        # 诊断（**已注释**：排查订阅问题时再打开 ✓）
        # if len(keys) != getattr(self, '_pool_dbg_n', -1):
        #     self._pool_dbg_n = len(keys)
        #     print(f'[pool] 可见行 {len(keys)} 只 | 前几: {keys[:4]}',
        #           flush=True)
        if not keys:
            # ★ 股票：报价页不可见 → 清空富途 `visible` 订阅，避免占满额度 ✓
            # ★ 期货：前端可见集合偶尔为空（切表 / 首屏）时不能直接不刷新；
            #   miniqt 行情报价也是按当前表刷新，不受虚拟滚动影响。取前
            #   200 个缓存合约兜底，价格能继续更新 ✓
            if getattr(feed, 'kind', '') != 'futures':
                pool = getattr(self, '_stock_pool', None)
                if pool is not None:
                    pool.set_owner('visible', [])
                return
            keys = list(known)[:200]
            if not keys:
                return
        if feed is None or not feed.available():
            return
        if getattr(feed, 'kind', '') == 'stocks':
            self._sync_stock_pool(feed)
            # ★ 可见范围内的股票 → **订阅池**（miniqt 同款：滚出屏幕就退订，
            #   但图表正在用的不退 ✓）
            try:
                from .stocks import to_futu_code as _to_code
                pool = getattr(self, '_stock_pool', None)
                if pool is None or pool.api is not getattr(feed, 'api', None):
                    from .stocks import SubscriptionPool as _Pool
                    pool = _Pool(getattr(feed, 'api', None))
                    self._stock_pool = pool
                pool.set_owner('visible', [_to_code(key) for key in keys
                                           if _is_stock(key)])
                if not keys:                     # 报价页不可见 → 全退订 ✓
                    pool.set_owner('visible', [])
                pool.set_charts([
                    _to_code(str(info.get('symbol') or symbol))
                    for symbol, info in (self.tabs or {}).items()
                    if _is_stock(str(info.get('symbol') or symbol))])
            except Exception as error:                           # noqa: BLE001
                self.push_log_once('stock-pool', f'订阅池不可用：{error!r}',
                                   'warning')
        quotes = feed.quotes(keys)
        if not quotes:
            # ★ 连续取空 → 大概率是「连接断了 / 没有行情权限」
            self._empty_quotes = getattr(self, '_empty_quotes', 0) + 1
            if self._empty_quotes >= 20:
                # ★ 连续取空（实盘常见：没权限 / 连接慢）→ 暂停 10 秒再试，
                #   避免每 0.5 秒都去撞一次（每次可能卡 30 秒 ✗）
                self._quotes_block_until = time.monotonic() + 10.0
            if self._empty_quotes in (30, 100, 300):
                self.push_log(
                    f'行情取数为空（连续 {self._empty_quotes} 次）：'
                    '可能是实盘账户没有该合约的行情权限，或行情连接已断开；'
                    '可试「重新登录」', 'warning')
            return
        self._empty_quotes = 0
        # ★ 天勤的**盘前 / 休市 / 夜盘未开盘**：行情对象里 ``last_price`` 等
        #   动态字段就是 NaN（只有涨跌停 / 昨收 / 昨结有值），以前前端直接
        #   显示成「NaN」→ 看着像行情挂了（用户实测 ✗）。这里只给一条**提示**，
        #   不影响推真正的报价（开盘后自动就有价 ✓）。股票逻辑不动 ✗。
        if getattr(feed, 'kind', '') == 'futures' and self._quotes_all_empty(quotes):
            label = '%s · %s' % (self.filter.get('type') or 'FUT',
                                 self.filter.get('exchange') or '')
            self.push_log_once(
                'empty-quotes-%s' % label,
                '%s：当前没有最新价（盘前 / 休市 / 夜盘未开盘），'
                '开盘后会自动恢复；昨收 / 昨结算 / 涨跌停价仍来自行情源 ✓'
                % label, 'info')
        # 报价行没有 spark → 带上已算好的走势，否则前端每 0.5 秒被清空 ✗
        for item in quotes:
            spark = self._spark.get(str(item.get('symbol') or ''))
            if spark:
                item['spark'] = spark
        self.push(_protocol.patch_rows_update(quotes))
        self._remember_quotes(quotes)          # ★ 写快照（下次首屏用 ✓）
        for item in quotes:
            self._last_rows[str(item.get('symbol'))] = item
        # 播放条跟着报价走（价格 / 涨跌幅 ✓，1 秒最多一次）
        import time as _time
        now = _time.monotonic()
        if now - float(getattr(self, '_ticker_at', 0.0)) >= 1.0:
            self._ticker_at = now
            self._refresh_ticker(list(self._last_rows.values()))

    @staticmethod
    def _quotes_all_empty(quotes) -> bool:
        """这批报价里**没有一个是有效的最新价**（盘前 / 休市 / 无行情权限 ✓）"""
        rows = [item for item in (quotes or []) if item]
        if not rows:
            return False
        for item in rows:
            if item.get('last') is not None:
                return False
        return True

    def _refresh_sparks(self) -> None:
        """给**可见行**补「走势」spark（每 5 秒 ≤12 只，避免一次拉爆 ✓）

        期货：拉 120 根 1 分钟线取收盘（结果会缓存）；
        股票：暂不拉（A 股 6500 行，按需在气泡里看，P5 再补）。
        """
        now = time.monotonic()
        if now - self._spark_at < 5.0:
            return
        self._spark_at = now
        feed = self.current_feed()
        if feed is None or not feed.available():
            return
        if feed.kind not in ('futures', 'stocks'):
            return
        if getattr(self, '_real_account', False):
            # ★ 实盘：`get_kline_serial` 会阻塞几十秒（实测 85 秒/拍 ✗）
            #   → 「走势」小图先不刷新（只是列表里那条迷你折线，不影响行情 ✓）
            self.push_log_once(
                'spark-real-skip',
                '实盘账户：行情列表的「走势」小图暂不刷新（避免卡顿）', 'info')
            return
        if self._name_queue:
            return                       # 先补名称（列表可读性优先 ✓）
        # ★ 首页「收藏 / 加入自选」的合约也要有 spark（迷你图 ✓）
        pool = list(self.visible or [])
        for symbol in getattr(self, '_home_extra', []) or []:
            if symbol not in pool:
                pool.append(symbol)
        pending = [key for key in pool
                   if key not in self._spark][:self._spark_budget]
        if not pending:
            return
        updates = []
        for symbol in pending:
            values = self.spark_values(symbol)
            if values:
                updates.append({'symbol': symbol, 'spark': values})
        if updates:
            self.push(_protocol.patch_rows_update(updates))

    def _refresh_tabs(self) -> None:
        if self._quotes_blocked():
            return
        """已打开的看盘 tab：K 线增量 + 二级报价 + 持仓 ✓"""
        profile = os.environ.get('MINIBT_DESK_PROFILE') == '1'
        timings = {}

        def timed(name, fn):
            if not profile:
                return fn()
            before = time.perf_counter()
            value = fn()
            timings[name] = time.perf_counter() - before
            return value

        for symbol in list(self.tabs):
            info = self.tabs[symbol] or {}
            layout = dict(info.get('layout') or {})
            layout_symbols = [str(item or '') for item
                              in (layout.get('symbols') or [])]
            # ★ 自动布局后，第 1 格可能是策略里的另一个合约（≠ tab 名）
            #   → 第 1 格也按 layout.symbols[0] 取数，否则图上还是旧合约 ✗
            cell0_symbol = layout_symbols[0] if layout_symbols else symbol
            feed = (pick_feed(self.feeds, cell0_symbol)
                    or info.get('feed') or self.current_feed())
            if feed is None:
                continue
            length = self.tab_length(info)
            frame = timed('klines', lambda: feed.klines(
                cell0_symbol, info.get('cycle') or 60, length))
            frame_len = len(frame) if frame is not None else 0
            # ★ 「根数」必须数**真正有数据的**行：天勤的 `get_kline_serial`
            #   在历史还没下载完时返回的是**定长占位表**（`datetime = 0`、
            #   OHLC 全 NaN），`len(frame)` 从头到尾都等于请求宽度 → 以前
            #   永远判不出「长度变了」→ 只推增量 2 根 → 图表打开只剩 2 根
            #   K 线（用户实测 ✗）。
            count, first_time, _last = timed(
                'kline_sig', lambda: _kline_signature(frame))
            full_replace = bool(count and (
                count != int(info.get('_kline_bars_len') or 0)
                or first_time != int(info.get('_kline_first_time') or 0)))
            bars = timed('bars', lambda: _protocol.bars_from_frame(
                frame, 0 if full_replace else 2))
            if bars:
                # 正常增量只推「上一根 + 最后一根」；首次 / 新 K 线后第一拍
                # 用 full_replace 把完整历史补上 ✓
                last_time = int(bars[-1].get('time') or 0)
                last_close = float(bars[-1].get('close') or 0.0)
                if full_replace or (last_time != info.get('_kline_time')
                        or last_close != info.get('_kline_close')
                        or time.monotonic()
                        - float(info.get('_kline_at') or 0) >= 1.0):
                    if full_replace:
                        self._note_kline_state(info, bars, frame_len)
                    else:
                        info['_kline_time'] = last_time
                        info['_kline_close'] = last_close
                        info['_kline_at'] = time.monotonic()
                    payload = _protocol.patch_kline(
                        symbol, bars if full_replace else bars[-2:],
                        replace=full_replace)
                    if cell0_symbol != symbol:
                        payload['cell'] = 0
                    timed('kline_push', lambda: self.push(payload))
            book = timed('book', lambda: self.book_payload(cell0_symbol, feed))
            timed('book_push', lambda: self.push(book))
            position = timed('position', lambda: self.position_payload(
                cell0_symbol, feed))
            position['cell'] = 0           # 多布局：第 1 格 ✓
            timed('position_push', lambda: self.push(position))
            if symbol not in self.replay_symbols:
                def push_cell0_orders() -> None:
                    """第 1 格的挂单线（`symbol` 用主 tab 找 page，
                    数据按 `cell0_symbol` 筛 ✓）"""
                    payload = self.orders_payload(cell0_symbol)
                    payload['symbol'] = symbol
                    payload['cell'] = 0
                    self.push(payload)

                timed('orders', push_cell0_orders)
            timed('cell_bars', lambda: self._push_cell_bars(symbol, info))
            timed('strategy', lambda: self._update_strategy_items(
                symbol, info, frame, main_symbol=cell0_symbol))
            timed('indicator', lambda: self._refresh_indicators(
                symbol, info, bars, frame))
        if profile and timings:
            detail = ' '.join(f'{name}={value:.3f}s'
                              for name, value in sorted(
                                  timings.items(),
                                  key=lambda item: item[1], reverse=True))
            self.push_log(f'[性能] 看盘 tab 明细：{detail}', 'info')

    # -------------------------------------------------------- 交易
    # ------------------------------------------------ 扩展功能（门面）
    def workbench_view(self):
        """交易工作台（惰性；失败 → None ✓）"""
        if self._workbench is None:
            try:
                from .workbench import Workbench
                self._workbench = Workbench(self)
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 交易工作台不可用: {error!r}')
                return None
        return self._workbench

    def research_view(self):
        """策略研究平台（惰性；失败 → None ✓）"""
        if self._research is None:
            try:
                from .research import ResearchLab
                self._research = ResearchLab(self)
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 研究平台不可用: {error!r}')
                return None
        return self._research

    def datahub_view(self):
        """本地数据平台（惰性；失败 → None ✓）"""
        if self._datahub is None:
            try:
                from .datahub import DataCatalog, default_folders
                folders = default_folders()
                # 本地图表里手动添加过的文件夹也一起扫 ✓
                store = getattr(self, '_local_store', None)
                for folder in list(getattr(store, 'folders', []) or []):
                    if str(folder) not in folders:
                        folders.append(str(folder))
                self._datahub = DataCatalog(folders)
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 数据平台不可用: {error!r}')
                return None
        return self._datahub

    def ops_view(self):
        """平台化 / 运维门面（惰性；失败 → None ✓）"""
        if self._ops is None:
            try:
                from .ops import OpsService
                self._ops = OpsService(self)
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 运维服务不可用: {error!r}')
                return None
        return self._ops

    def _risk_guard(self, symbol: str, side: str, volume: int,
                    price: float = None) -> Dict[str, Any]:
        """给**旧的下单入口**加一道风控（工作台没打开 → 不拦，保持旧行为）"""
        bench = self._workbench
        if bench is None:
            # 上次在界面里启用过风控 → 重启后旧的交易入口也要受限制 ✓
            # （没配置过就不建 SQLite，保持 desk 旧行为）
            try:
                from .workbench import default_config_file
                if not os.path.isfile(default_config_file()):
                    return {'ok': True}
            except Exception:                                    # noqa: BLE001
                return {'ok': True}
            bench = self.workbench_view()
        if bench is None or not bench.limits.get('enabled'):
            return {'ok': True}
        try:
            from .workbench import OrderTicket
            ticket = OrderTicket(symbol=str(symbol),
                                 side=str(side).lower(),
                                 volume=max(1, int(volume or 1)),
                                 price=price,
                                 order_type='limit' if price else 'market')
            decision = bench.check(ticket)
        except Exception:                                        # noqa: BLE001
            return {'ok': True}
        if not decision.ok:
            bench.store.log('risk_reject', decision.reason, symbol=symbol,
                            side=side, volume=volume, price=price,
                            status='REJECTED', meta=decision.as_dict())
            return {'ok': False,
                    'text': f'风控拒绝：{decision.reason}',
                    'risk': decision.as_dict()}
        return {'ok': True}

    def _audit_action(self, kind: str, text: str, **fields) -> None:
        """旧交易入口的审计（工作台没打开 → 什么也不做 ✓）"""
        bench = self._workbench
        if bench is None:
            return
        try:
            bench.store.log(kind, text, **fields)
        except Exception:                                        # noqa: BLE001
            pass

    def _suite_tick(self) -> None:
        """每 1 秒：条件单触发 + 定时任务（都只在页面打开后才有对象）"""
        now = time.monotonic()
        if now - self._suite_at < 1.0:
            return
        self._suite_at = now
        bench = self._workbench
        if bench is not None and bench.conditional():
            prices = {}
            for symbol in {str(item.get('symbol') or '')
                           for item in bench.conditional()}:
                if not symbol:
                    continue
                row = (self._last_rows or {}).get(symbol) or {}
                value = row.get('last')
                if value is not None:
                    prices[symbol] = value
            try:
                fired = bench.check_conditions(prices)
            except Exception as error:                           # noqa: BLE001
                self.push_log(f'[工作台] 条件单检查失败：{error!r}', 'warning')
                fired = []
            for item in fired:
                self.push(_protocol.patch_toast(
                    str(item.get('text') or '条件单已触发'),
                    'success' if item.get('ok') else 'warning'))
            if fired:
                self.push(bench.snapshot())
                self.push(self.account_payload(symbol=next(iter(self.tabs), '')))
        ops = self._ops
        if ops is not None:
            try:
                results = ops.run_tasks()
            except Exception as error:                           # noqa: BLE001
                self.push_log(f'[运维] 定时任务失败：{error!r}', 'warning')
                results = []
            if results:
                self.push({'type': 'ops_tasks', 'results': results,
                           'tasks': ops.tasks.snapshot()})
                failed = [item for item in results if not item.get('ok')]
                if failed:
                    self.push_log(
                        f'[运维] {len(failed)} 个定时任务失败：'
                        + '；'.join(str(item.get('name')) for item in failed),
                        'warning')

    def trading_view(self):
        """下单执行器（惰性；建不起来 → None ✓）"""
        if self.trader is None:
            try:
                from .trading import Trading
                self.trader = Trading(self)
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 交易执行器不可用: {error!r}')
                return None
        return self.trader

    def trading_state(self, symbol: str = '') -> Dict[str, Any]:
        """前端要知道：能不能下单 / 是不是实盘（要二次确认）/ 打到哪个账户 ✓

        约定：**股票 → 本地模拟盘；期货 → 天勤账号**（用户明确要求分开 ✓）
        """
        symbol = symbol or next(iter(self.tabs), '')
        if self.is_replaying(symbol):
            return {'type': 'trading', 'symbol': symbol, 'enabled': True,
                    'real': False, 'kind': 'replay',
                    'account': '本地模拟（回放）'}
        trader = self.trading_view()
        feed = self.feed_of(symbol) if symbol else self.current_feed()
        enabled = bool(trader is not None and trader.ready(symbol))
        return {'type': 'trading', 'symbol': symbol, 'enabled': enabled,
                'real': bool(trader is not None and trader.is_real(symbol)),
                'kind': 'stocks' if getattr(feed, 'kind', '') == 'stocks'
                        else 'futures',
                'account': trader.account_label(symbol) if trader else ''}

    # -------------------------------------------------------- 账户面板
    def account_view(self):
        """账户面板视图（惰性建；失败 → None ✓）"""
        if self.accounts is None:
            try:
                from .accounts import AccountView
                self.accounts = AccountView(self)
                # 登录实盘 → 默认选中 index 1（快期模拟是 0）
                preferred = int(getattr(self, '_preferred_account_index', 0))
                try:
                    self.accounts.index = max(
                        0, min(preferred, len(self.accounts.labels()) - 1))
                except Exception:                            # noqa: BLE001
                    pass
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 账户面板不可用: {error!r}')
                return None
        return self.accounts

    def account_payload(self, limit: int = 100, symbol: str = ''):
        """账户 / 持仓 / 委托 / 成交（跟**看盘 tab 的合约**走 ✓）

        以前没有 `symbol` → `AccountView.api()` 用报价页筛选：
        报价页停在「股票」时会显示股票账户，天勤刚下的单自然看不到 ✗
        """
        # ★ 回放中：账户面板显示**本地模拟账户**（和本地图表一样 ✓）
        if self.is_replaying(symbol):
            try:
                return self.replay_account_payload(symbol)
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 回放账户失败: {error!r}')
        view = self.account_view()
        if view is None:
            return {'type': 'account', 'empty': True}
        try:
            return view.payload(limit, symbol)
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] 账户数据失败: {error!r}')
            return {'type': 'account', 'empty': True}

    def _refresh_docks(self) -> None:
        """有看盘 tab 才推账户面板（每 1 秒一次，别把 tqsdk 拉爆 ✓）"""
        if not self.tabs:
            return
        now = time.monotonic()
        if now - self._dock_at < 1.0:
            return
        self._dock_at = now
        self.push(self.account_payload(symbol=next(iter(self.tabs), '')))
        # ★ 挂单线：看盘窗口里每个 tab 的合约都推一次（上限 6 个 ✓）
        for symbol in list(self.tabs)[:6]:
            if symbol in self.replay_symbols:
                continue
            self._push_orders(symbol)

    def push_log_once(self, key: str, text: str,
                      level: str = 'info') -> bool:
        """同一 key 只记一次（避免每拍刷屏 ✓）

        返回：这次真的记了吗（调用方据此决定要不要**同时弹窗** ✓）
        """
        seen = getattr(self, '_once_logs', None)
        if seen is None:
            seen = self._once_logs = set()
        if key in seen:
            return False
        seen.add(key)
        self.push_log(text, level)
        return True

    def push_log(self, text: str, level: str = 'info') -> None:
        """运行日志：**终端（stdout）+ 前端**都输出 ✓

        ⚠ 界面卡住时前端日志复制不了（用户实测）→ 这里一律再 `print` 一份到
        启动 `minibt desk` 的终端（`flush=True` 立刻可见）。
        `Desk(log_to_stdout=False)` 可关掉（`--quiet` ✓）。

        Jupyter 内嵌（``gui.show_in_notebook``）时标了 ``_notebook_quiet``：
        节拍线程持续往单元格 stdout 写，会在 IPython 收尾时把 kernel 卡住 ✗
        → 日志只进 desk 的「运行日志」页，不刷单元格（``log_to_ui`` 照旧）✓
        """
        stamp = time.strftime('%H:%M:%S')
        if (getattr(self, 'log_to_stdout', True)
                and not getattr(self, '_notebook_quiet', False)):
            try:
                print(f'[{stamp}] {str(level).upper():7s} {text}', flush=True)
            except Exception:                                    # noqa: BLE001
                pass
        if getattr(self, 'log_to_ui', True):
            self.push({'type': 'log', 'text': str(text),
                       'level': str(level), 'ts': stamp})

    def _strategy_update_frames(self, runner, symbol: str, info: dict,
                                frame):
        """实时策略每拍要灌的 frames（多合约 → `{合约: frame}` ✓）"""
        try:
            symbols = list(runner.update_symbols())
        except Exception:                                        # noqa: BLE001
            symbols = []
        if len(symbols) <= 1:
            return [frame]
        from .strategy_runner import _same_contract
        cache = info.setdefault('_strat_frame_cache', {})
        now = time.monotonic()
        frame_map: Dict[str, Any] = {}
        main_key = ''
        for name in symbols:
            if _same_contract(name, symbol):
                frame_map[name] = frame
                main_key = name
                continue
            item = cache.get(name)
            fetched = None
            if item and now - float(item[0]) < 0.8:
                fetched = item[1]
            else:
                fetched = self._strategy_frame(name, info)
                if fetched is not None:
                    cache[name] = (now, fetched)
                elif item:
                    fetched = item[1]        # 没取到 → 用上一拍缓存 ✓
                else:
                    self.push_log_once(
                        f'strategy-frame-{name}',
                        f'多合约策略：暂时取不到 {name} 的 K 线（稍后重试）',
                        'warning')
            if fetched is not None:
                frame_map[name] = fetched
        if not main_key:
            frame_map[str(symbol)] = frame
        return frame_map

    def _report_strategy_runtime_error(self, symbol: str, info: dict,
                                       runner=None, error: str = '') -> None:
        """策略 `next()` 运行出错：**图表 / 指标不受影响** ✓

        用户要求（2026-10-30）：策略跑起来后 `next()` 报错不能把图表关掉、
        也不能把图上的线清掉 ——
        * **第一次**：弹窗（带错误信息 + 怎么恢复）+ 运行日志；
        * **之后**：只在终端 / 日志里提醒（每 10 秒最多一条，不刷屏），
          让用户去「删除策略 → 改代码 → 重新加到图表」。
        """
        text = str(error or getattr(runner, 'error', '') or '')
        if not text:
            return
        name = str((info.get('strategy') or {}).get('name') or '策略')
        trace = str(getattr(runner, 'traceback', '') or '')
        tail = ''
        if trace:
            lines = [line for line in trace.strip().splitlines()
                     if line.strip()]
            tail = lines[-1] if lines else ''
        info['_strat_error'] = text
        now = time.monotonic()
        if not info.get('_strat_error_shown'):
            info['_strat_error_shown'] = True
            info['_strat_error_at'] = now
            info['_strat_error_last'] = text
            self.push_log(
                f'策略 {name} 的 next() 运行出错（图表不受影响）：{text}',
                'error')
            self.push_alert(
                f'策略 {name} 运行出错',
                text,
                detail=chr(10).join(filter(None, [
                    tail,
                    '图表 / 指标不受影响，策略线停在最后一次成功的状态。',
                    '修好后：先删除策略（工具栏 🗑 → 1 editor.xxx / '
                    '「策略管理」），再重新「加到图表」。'])),
                level='error')
            return
        # 之后：终端打印 + 日志节流提醒（同一错误不刷屏 ✓）
        print(f'[desk] 策略 {name} 的 next() 仍然报错：{text}')
        if now - float(info.get('_strat_error_at') or 0.0) >= 10.0:
            info['_strat_error_at'] = now
            info['_strat_error_last'] = text
            self.push_log(
                f'策略 {name} 的 next() 仍然报错（已跳过这一拍）：{text}',
                'warning')

    def _update_strategy_items(self, symbol: str, info: dict, frame,
                               main_symbol: str = '') -> None:
        """**策略指标增量更新**（每拍一次，最多 1 秒 ✓）

        `symbol` = tab 键（前端 page 路由）；`main_symbol` = 第 1 格真实合约
        （自动布局后可能 ≠ tab 键）✓
        """
        runner = info.get('strategy_runner')
        if runner is None or not getattr(runner, 'strategy', None):
            return
        focus = str(main_symbol or symbol or '')
        # ★ 策略 __init__（指标）与普通指标共用同一个更新频率；
        #   next 是否真正运行由 runner 根据「新K线next / on_close」决定 ✓
        now = time.monotonic()
        interval = self._chart_update_interval_ms() / 1000.0
        if now - float(info.get('_strat_at') or 0.0) < interval:
            return
        # ★ 数据没变（同一根 K 线重复 / 收盘后行情不动）→ **不重算** ✓
        #   `advance()` 每次都会重跑 `__init__`（全部指标），收盘后每秒算一遍
        #   纯属浪费（用户实测「收盘了后台还在算」✗）
        stamp = self._frame_stamp(frame) if frame is not None else 0
        try:
            last_close = (round(float(frame['close'].iloc[-1]), 6)
                          if frame is not None and len(frame) else 0.0)
        except Exception:                                        # noqa: BLE001
            last_close = 0.0
        bar_key = (stamp, last_close,
                   len(frame) if frame is not None else 0)
        if info.get('_strat_bar') == bar_key:
            return
        info['_strat_bar'] = bar_key
        # ★ 行情很久没更新（收盘 / 停牌）→ 挂起，等新数据自动恢复 ✓
        if stamp:
            idle = time.time() - stamp / 1_000_000_000.0
            cycle = max(1, int(info.get('cycle') or 60))
            if idle > max(600.0, cycle * 5):
                if not info.get('_strat_idle'):
                    info['_strat_idle'] = True
                    self.push_log(
                        f'行情 {int(idle // 60)} 分钟没有新 K 线（可能已收盘）'
                        ' → 策略计算已挂起，有新数据会自动恢复 ✓', 'info')
                return
            if info.get('_strat_idle'):
                info['_strat_idle'] = False
                self.push_log('检测到新 K 线 → 策略计算已恢复 ✓', 'info')
        info['_strat_at'] = now
        try:
            frames = self._strategy_update_frames(runner, focus, info, frame)
            if not runner.advance(frames):
                # ★ `next()` 报错：**图表保持不动**（不清线 / 不删策略），
                #   第一次弹窗 + 之后只写日志（用户要求 ✓）
                self._report_strategy_runtime_error(symbol, info, runner)
                return
            from . import strategy_overlay as _overlay
            result = _overlay.collect(runner, frame, None)
            items = result.get('items') or []
            groups = dict(result.get('groups') or {})
            info['strategy_groups'] = groups
        except Exception as error:                               # noqa: BLE001
            self._report_strategy_runtime_error(
                symbol, info, runner,
                error=f'{type(error).__name__}: {error}')
            return
        if not items:
            return
        # ★ 主图这一格用**属于主图合约**的那一组（不是“线最多的一组”）✓
        try:
            from .strategy_runner import _same_contract, _same_underlying
            for key, group in (groups or {}).items():
                if (_same_contract(key, focus)
                        or _same_underlying(key, focus)):
                    items = group
                    break
        except Exception:                                        # noqa: BLE001
            pass
        info['strategy_items'] = list(items)
        self.push(self.indicator_payload(symbol))
        # ★ 多布局：第 2..N 格各自的策略线（按组合约对回格子 ✓）
        self._push_strategy_cells(symbol, info, groups)

    def _push_strategy_cells(self, symbol: str, info: dict,
                             groups=None) -> None:
        """多布局：把策略线按合约推到第 2..N 格 ✓

        * `groups` = `{合约: 线}`（不传就用 `info['strategy_groups']`）；
        * 策略合约数 **小于** 格子数时，多出来的格子**不画策略线**
          （用户要求：多余格保持原样 ✓）。
        """
        cells = (info.get('layout') or {}).get('cells') or []
        if len(cells) <= 1:
            return
        groups = dict(groups or info.get('strategy_groups') or {})
        strat_name = str((info.get('strategy') or {}).get('name') or '')
        contracts = [str(item) for item in
                     (info.get('strategy_contracts') or [])]
        try:
            from .strategy_runner import (_same_contract as _same_c,
                                          _same_underlying as _same_u)
        except Exception:                                    # noqa: BLE001
            _same_c = _same_u = lambda *_a: False           # type: ignore
        for index, cell in enumerate(cells):
            if index == 0 or not isinstance(cell, dict):
                continue
            cell_symbol = str(cell.get('symbol') or symbol)
            group = []
            if not contracts or index < len(contracts):
                for key, value in groups.items():
                    if _same_c(key, cell_symbol) or _same_u(key, cell_symbol):
                        group = value
                        break
            self.push({
                'type': 'indicator', 'symbol': symbol, 'cell': index,
                'items': list(group or []), 'strategy': strat_name,
                'strategyOnly': True,
                'strategyContracts': contracts,
            })

    def _indicator_intervals(self):
        """图表指标 / 策略 __init__ 的统一更新频率（ms）+ 自定义指标新股开关 ✓"""
        from . import user_prefs as _prefs
        values = _prefs.settings()

        def ms(key: str, default: int) -> int:
            try:
                number = int(float(values.get(key, default)))
            except (TypeError, ValueError):
                number = default
            return max(10, min(3000, number))

        return (ms('indicator_refresh_interval_ms', 1000),
                bool(values.get('indicator_custom_new_bar', False)))

    def _chart_update_interval_ms(self) -> int:
        """指标 / 策略共用的图表更新间隔（毫秒）✓"""
        return int(self._indicator_intervals()[0])

    def _indicator_groups(self, info: dict):
        """按「主图叠加 / 副图 / 完整库（VP / 表格）」分组已选指标 ✓"""
        from . import indicators as _ind
        selected = info.get('indicators') or []
        known = {entry['key'] for entry in _ind.CATALOG}
        cache = info.get('_ind_cache') or {}
        cached = {str(item.get('key')): item
                  for item in (cache.get('items') or [])}
        main: List[str] = []
        sub: List[str] = []
        custom: List[str] = []
        for entry in selected:
            key = str(entry.get('key') or '')
            if not key:
                continue
            if str(key).upper() in known or key.startswith('pi:'):
                found = None
                for item_key, item in cached.items():
                    if (item_key == key or item_key.startswith(key + ':')
                            or str(item.get('source') or '') == key):
                        found = item
                        break
                if found is not None and found.get('overlay'):
                    main.append(key)
                elif found is not None:
                    sub.append(key)
                elif entry.get('overlay') is not None:
                    (main if entry.get('overlay') else sub).append(key)
                else:
                    sub.append(key)
            else:
                custom.append(key)
        return main, sub, custom

    def _refresh_indicators(self, symbol: str, info: dict, bars: list,
                            frame=None) -> None:
        """最后一根 K 线**变了**才重算指标（新 K 线全量；同根只推最后一点）✓

        以前只比较「最后一根的时间」→ 同一根内条件很快失效、**每秒重算**；
        现在：
        * 同一根 K 线内 close 变化 → 只算尾部，只推最后 1 点；
        * 新 K 线 → 至少推最后 2 点；断线重连按周期 / 时间差推缺口；
        * 缺口太大 / 自定义完整库 → 退回完整重算；
        * 没变化 / 半秒内重复 → 直接跳过。
        """
        if not info or not info.get('indicators') or not bars:
            return
        last_bar = bars[-1] or {}
        stamp = int(last_bar.get('time') or 0)
        try:
            close = round(float(last_bar.get('close') or 0.0), 6)
        except (TypeError, ValueError):
            close = 0.0
        key = (stamp, close)
        # 兼容不传 frame 的旧调用（测试 / 其它模块）：保持 1 秒节流 ✓
        if frame is None:
            if info.get('_ind_bar') == key and \
                    time.monotonic() - float(info.get('_ind_at') or 0.0) < 1.0:
                return
            info['_ind_bar'] = key
            info['_ind_at'] = time.monotonic()
            self.push(self.indicator_payload(symbol))
            return
        cache = info.get('_ind_cache') or {}
        cache_time = self._frame_stamp(frame) if frame is not None else 0
        same_sig = bool(
            cache and cache.get('sig') == self._indicator_sig(
                info.get('indicators') or []))
        same_bar = bool(
            cache
            and cache_time
            and cache.get('time') == cache_time
            and cache.get('length') == (len(frame) if frame is not None else 0)
            and same_sig)
        if same_bar and cache.get('close') == close:
            return
        now = time.monotonic()
        # 新 K 线（或断线重连后补了几根）→ 至少推最后 2 根；按周期与时间
        # 差推算缺口。缺口太大 / 缓存签名不对 → 退回完整重算 ✓
        if cache and frame is not None and same_sig and not same_bar:
            # 完整库（custom）可能依赖整段历史；新 K 线直接走完整重算分支，
            # 避免只更新内置指标而把自定义指标落下 ✓
            _main, _sub, custom_keys = self._indicator_groups(info)
            count = (None if custom_keys else
                     self._indicator_tail_count(cache, frame, info))
            if count is not None:
                info['_ind_bar'] = key
                info['_ind_at'] = now
                if self._refresh_indicator_last(
                        symbol, info, frame, count=count):
                    return
        if same_bar and frame is not None:
            # ★ 主图 / 副图 / VP / 表格 / 策略 __init__ 共用一个更新频率 ✓
            main, sub, custom = self._indicator_groups(info)
            interval_ms, custom_new_bar = self._indicator_intervals()
            if now - float(info.get('_ind_at') or 0.0) < interval_ms / 1000.0:
                return
            info['_ind_bar'] = key
            info['_ind_at'] = now
            # VP / 表格需要完整重算（后台线程）→ 与其它指标同一频率
            if custom and not custom_new_bar:
                self.push(self.indicator_payload(symbol, frame=frame))
                return
            # 没有完整库（或开启「只在新 K 线」）→ 主/副图只推最后一点
            due = list(main) + list(sub)
            if due and self._refresh_indicator_last(
                    symbol, info, frame, keys=set(due)):
                return
            # 缓存不匹配 / 自定义指标只在新股更新 → 下一拍再试
            if custom and custom_new_bar:
                return
            # 分组增量失败 → 退回完整重算
        info['_ind_bar'] = key
        info['_ind_at'] = now
        self.push(self.indicator_payload(symbol, frame=frame))
    # -------------------------------------------------------- 二级报价
    # -------------------------------------------------------- 二级报价
    def book_payload(self, symbol: str, feed=None) -> Dict[str, Any]:
        """5 档买卖 + 12 个字段 + 分笔（股票只有 1 档 ✓）"""
        feed = feed or pick_feed(self.feeds, symbol) or self.current_feed()
        payload: Dict[str, Any] = {
            'type': 'book', 'symbol': symbol, 'levels': 1 if _is_stock(symbol) else 5,
            'depth': 1 if _is_stock(symbol) else 5,
            'asks': [], 'bids': [], 'info': {}, 'ticks': [],
            # ★ 用**该合约所属的行情源**判断能不能下单，不能用报价页当前的
            #   类型筛选（`api_ready()`）—— 报价页停在股票时，期货看盘页的
            #   二级报价 / 市价平仓 / 反手 / 撤单会全部变灰（用户实测 ✗）
            'trading': bool(self.trading
                            and getattr(feed, 'api', None) is not None),
        }
        # 自定义行情源可能没有 spec / get_position → 空面板即可（不炸 ✓）
        spec = getattr(feed, 'spec', None)
        quote = spec(symbol) if callable(spec) else None
        if quote is None:
            return payload
        # ★ 价格小数位：由合约最小变动价位（price_tick）推出来 ✓
        payload['decimals'] = _decimals_from_tick(
            _field_local(quote, 'price_tick') or _field_local(quote, 'tick'))
        payload['price_tick'] = _num_local(_field_local(quote, 'price_tick'))
        levels = payload['levels']

        def pair(price_key, volume_key):
            return [_book_pair(getattr(quote, price_key % index, None),
                               getattr(quote, volume_key % index, None))
                    for index in range(1, levels + 1)]

        if levels == 1:
            payload['asks'] = pair('ask_price%d', 'ask_volume%d')
            payload['bids'] = pair('bid_price%d', 'bid_volume%d')
        else:
            payload['asks'] = pair('ask_price%d', 'ask_volume%d')
            payload['bids'] = pair('bid_price%d', 'bid_volume%d')
        payload['info'] = _book_info(quote)
        payload['ticks'] = self._book_ticks(feed, symbol)
        return payload

    def _book_ticks(self, feed, symbol: str, limit: int = 14) -> List[dict]:
        """分笔成交（**现手** = 相邻两笔累计成交量的差 ✓）

        ⚠ 天勤 `get_tick_serial` 的 `volume` 是**当日累计成交量**，
        直接显示会变成“每笔都在累加”（用户实测 ✗）。
        这里和 miniqt 一致：`现手 = volume[i] - volume[i-1]`，
        第一笔算不出差值 → 跳过；差值 <= 0 → 不是成交 → 跳过 ✓
        """
        api = getattr(feed, 'api', None)
        getter = getattr(api, 'get_tick_serial', None)
        if not callable(getter):
            return []
        try:
            frame = getter(symbol)
        except Exception:                                        # noqa: BLE001
            return []
        if frame is None:
            return []
        if not hasattr(frame, 'to_dict'):
            # ⚠ 富途股票的 `get_tick_serial` 返回的是**单个 tick 对象**
            #   （`SimpleNamespace`）→ `len(frame)` 抛 TypeError，
            #   整个「看盘 tab」步骤每拍失败一次（用户实测 ✗）
            #   这里把它当成"一条分笔"处理 ✓
            price = _num_local(getattr(frame, 'last_price', None))
            if price is None:
                return []
            return [{
                'time': _clock_of(getattr(frame, 'datetime', '')),
                'price': price,
                'volume': int(_num_local(getattr(frame, 'volume', None)) or 0),
            }]
        if len(frame) == 0:
            return []
        rows: List[dict] = []
        try:
            last_volume = None
            last_price = None
            for item in frame.tail(max(limit * 4, 40)).to_dict('records'):
                stamp = item.get('datetime')
                price = _num_local(item.get('last_price'))
                if price is None:
                    continue
                volume = _num_local(item.get('volume'))
                previous_price = last_price
                last_price = price
                if volume is None:
                    continue
                delta = None if last_volume is None else volume - last_volume
                last_volume = volume
                if delta is None or delta <= 0:      # 第一笔 / 无成交 → 跳过 ✓
                    continue
                rows.append({
                    'time': _clock_of(stamp, shift_hours=(
                        TZ_HOURS if getattr(feed, 'kind', '') == 'futures'
                        else 0)),
                    'price': price,
                    'volume': delta,
                    'direction': _tick_side(item, price)
                                 or _tick_side_by_pair(price, previous_price),
                })
        except Exception:                                        # noqa: BLE001
            return []
        rows.reverse()                                # 最新的在最上面 ✓
        return rows[:limit]
    # -------------------------------------------------------- 持仓
    def position_payload(self, symbol: str, feed=None) -> Dict[str, Any]:
        """持仓线数据（多/空手数 + 均价 + 浮盈）✓"""
        feed = feed or pick_feed(self.feeds, symbol) or self.current_feed()
        payload: Dict[str, Any] = {'type': 'position', 'symbol': symbol,
                                   'long': None, 'short': None}
        tradeable = _symbols.is_tradeable(symbol)
        payload['tradeable'] = tradeable
        if not tradeable:
            # ★ 主连 / 指数：只有行情，**不要**去查持仓 / 委托（实盘会卡 ✗）
            return payload
        api = getattr(feed, 'api', None)
        getter = getattr(api, 'get_position', None)
        if not callable(getter):
            return payload
        row = None
        # ★ 多账户（TqMultiAccount）：账户面板显示的是**当前选中的账户**，
        #   这里也必须带 `account=`，否则查的是默认账户 → 有仓但无持仓线 ✗
        kwargs = {}
        view = self.account_view()
        if view is not None:
            try:
                kwargs = view.account_kwargs(symbol)
            except Exception:                                    # noqa: BLE001
                kwargs = {}
        try:
            try:
                row = getter(symbol, **kwargs) if kwargs else getter(symbol)
            except TypeError:
                row = getter(symbol)
        except Exception:                                        # noqa: BLE001
            return payload
        if row is None:
            return payload
        long_volume = _num_local(_field_any_local(
            row, ('pos_long', 'volume_long'))) or 0.0
        short_volume = _num_local(_field_any_local(
            row, ('pos_short', 'volume_short'))) or 0.0
        if long_volume <= 0 and short_volume <= 0:
            return payload
        payload['long'] = _position_side(
            row, long_volume, ('open_price_long', 'position_price_long'),
            ('float_profit_long', 'position_profit_long'), '多')
        payload['short'] = _position_side(
            row, short_volume, ('open_price_short', 'position_price_short'),
            ('float_profit_short', 'position_profit_short'), '空')
        # ★ 某些账户/交易所的持仓成本字段会是 NaN / 0（尤其刚成交那拍）
        #   → 前端 `!!side.avg` 会把整条持仓线过滤掉。这里退回最新价，
        #   保证「有持仓就一定有持仓线」（标签仍显示多/空 + 手数）✓
        fallback = _num_local((self._last_rows.get(symbol) or {}).get('last'))
        if fallback:
            for side in (payload.get('long'), payload.get('short')):
                if side and not side.get('avg'):
                    side['avg'] = fallback
        return payload

    # ======================================================== 命令
    def commands(self) -> Dict[str, Any]:
        return {
            'ready': self._on_ready,
            'home': self._on_home,                 # 首页显示 / 隐藏
            'home_refresh': self._on_home_refresh,  # 首页手动刷新
            'home_symbols': self._on_home_symbols,  # 自定义分组的合约
            'home_account_kind': self._on_home_account_kind,
            'strategy_start': self._on_strategy_start,   # 策略回测 / 优化
            'strategy_select': self._on_strategy_select,  # 切策略 / 合约
            'strategy_indicator_params': self._on_strategy_indicator_params,
            'strategy_cancel': self._on_strategy_cancel,  # 取消
            'strategy_trial_run': self._on_strategy_trial_run,  # 用 trial 回测
            'strategy_chart_file': self._on_strategy_chart_file,  # Qt/file:// 图表
            'home_preview': self._on_home_preview,  # 首页迷你 K 线 ✓
            'default_realtime': self._on_default_realtime,  # 实时图表默认合约 ✓
            'home_main': self._on_home_main,        # 首页「主力」按交易所 ✓
            'visible': self._on_visible,
            'table_row_at': self._on_table_row_at,   # 表格跟随鼠标 ✓
            'ui_state': self._on_ui_state,   # 可见页面（按需拉行情 ✓）
            'filter': self._on_filter,
            'open_chart': self._on_open_chart,
            'close_chart': self._on_close_chart,
            'set_cycle': self._on_set_cycle,
            'row_click': self._on_row_click,
            'context_menu': self._on_context_menu,
            'book': self._on_book,                    # 前端要求立刻刷一次
            'account': self._on_account,              # 前端要求立刻刷一次
            'reload_contracts': self._on_reload_contracts,
            'quote_chips': self._on_quote_chips,
            'trading_state': self._on_trading_state,
            'set_theme': self._on_set_theme,
            'layouts': self._on_layouts,
            'layout_sync': self._on_layout_sync,   # 前端切布局 → 记每格合约 ✓
            'layout_save': self._on_layout_save,
            'layout_update': self._on_layout_update,
            'export_csv': self._on_export_csv,
            'open_export': self._on_open_export,
            'export_remove': self._on_export_remove,
            'exports_clear': self._on_exports_clear,
            'exports': self._on_exports,
            'layouts_export': self._on_layouts_export,
            'layouts_import': self._on_layouts_import,
            'layout_apply': self._on_layout_apply,
            'layout_delete': self._on_layout_delete,
            'layout_favorite': self._on_layout_favorite,
            'set_layout': self._on_set_layout,
            'replay': self._on_replay,
            'replay_exit': self._on_replay_exit,
            'toast_local': self._on_toast_local,
            'indicator_picker': self._on_indicator_picker,
            'toggle_favorite': self._on_toggle_favorite,
            'favorites': self._on_favorites,
            'templates': self._on_templates,
            'save_template': self._on_save_template,
            'apply_template': self._on_apply_template,
            'delete_template': self._on_delete_template,
            'symbol_search': self._on_symbol_search,
            'sprite_search': self._on_sprite_search,
            'switch_symbol': self._on_switch_symbol,
            'alerts': self._on_alerts,
            'add_alert': self._on_add_alert,
            'drop_alert': self._on_drop_alert,
            'clear_alerts': self._on_clear_alerts,
            'personal_menu': self._on_personal_menu,
            # ---- 代码编辑器（个人指标 / 策略，P46）----
            'editor_list': self._on_editor_list,
            'editor_open': self._on_editor_open,
            'editor_restore': self._on_editor_restore,   # 恢复上次的文件 ✓
            'editor_save': self._on_editor_save,
            'editor_check': self._on_editor_check,
            'editor_new': self._on_editor_new,
            'editor_delete': self._on_editor_delete,
            'remove_strategy': self._on_remove_strategy,  # 删策略（P66 ✓）
            # ---- 画线持久化（键 = 合约|周期 ✓）----
            'drawings': self._on_drawings,
            'save_drawings': self._on_save_drawings,
            'clear_drawings': self._on_clear_drawings,
            'strategy_manage': self._on_strategy_manage,      # 策略管理弹窗 ✓
            'strategy_manage_update': self._on_strategy_manage_update,
            'strategy_live_start': self._on_strategy_live_start,
            'strategy_live_stop': self._on_strategy_live_stop,
            'replay_price': self._on_replay_price,        # 回放价格（模拟盘 ✓）
            'sim_analysis': self._on_sim_analysis,        # 模拟账户曲线 / 统计 ✓
            'sim_reset': self._on_sim_reset,              # 重置模拟账户 ✓
            'replay_order': self._on_replay_order,        # 回放下单（本地模拟 ✓）
            'replay_action': self._on_replay_action,      # 平 / 反 / 全 ✓
            'history_load': self._on_history_load,       # 无限历史（往左翻 ✓）
            'editor_format': self._on_editor_format,     # 右键「格式化」✓
            'editor_add_indicator': self._on_editor_add_indicator,
            # ---- 资源管理器（P57）----
            'explorer_list': self._on_explorer_list,
            'explorer_pick': self._on_explorer_pick,
            'explorer_op': self._on_explorer_op,
            'explorer_system_dir': self._on_explorer_system_dir,  # 系统目录 ▾
            'strategy_check': self._on_strategy_check,   # 回测 / 优化前体检 ✓
            'editor_help': self._on_editor_help,         # 编辑器「帮助」✓
            'clipboard_set': self._on_clipboard_set,     # 复制地址（系统剪贴板 ✓）
            'web_page': self._on_web_page,               # 网页 tab（后端代理抓取 ✓）
            'lsp_start': self._on_lsp_start,             # LSP（jedi）服务 ✓
            'lsp_stop': self._on_lsp_stop,
            'explorer_set_root': self._on_explorer_set_root,   # 兼容旧调用
            'personal_add_dir': self._on_personal_add_dir,     # 兼容旧调用
            'explorer_check_personal': self._on_explorer_check_personal,
            # （`personal_refresh` 已按用户要求删除：目录在打开菜单时才扫 ✓）
            'pick_personal': self._on_pick_personal,
            'drop_personal': self._on_drop_personal,
            'indicator_menu': self._on_indicator_menu,
            'add_indicator': self._on_add_indicator,
            'remove_indicator': self._on_remove_indicator,
            'place_order': self._on_place_order,
            'account_action': self._on_account_action,
            # ★ 底部面板：**按行**的右键操作（持仓 → 平/反；委托 → 撤 ✓）
            'position_action': self._on_position_action,
            'order_action': self._on_order_action,
            'switch_account': self._on_switch_account,
            'set_chart_type': self._on_set_chart_type,
            'set_setting': self._on_set_setting,
            'open_url': self._on_open_url,          # 设置页「帮助 / 反馈」✓
            # ---- 登录（离线也能连上服务 ✓）----
            'login_info': self._on_login_info,        # 读记住的账号（预填 ✓）
            # ---- 收藏 / 自选分组（落盘到 prefs，重启还在 ✓）----
            'watch_get': self._on_watch_get,
            'watch_set': self._on_watch_set,
            'connect_futures': self._on_connect_futures,
            'connect_stocks': self._on_connect_stocks,
            'test_futu': self._on_test_futu,          # 测 FutuOpenD 网关 ✓
            'open_data_dir': self._on_open_data_dir,  # 设置页「本地文件」✓
            'symbols_refresh': self._on_symbols_refresh,
            'ticker_refresh': self._on_ticker_refresh,
            'ticket_order': self._on_ticket_order,
            'focus_chart': self._on_focus_chart,
            # ---- 本地图表（静态 CSV + 本地模拟账户）----
            'local_list': self._on_local_list,
            'local_add_folder': self._on_local_add_folder,
            'local_remove_folder': self._on_local_remove_folder,
            'local_load': self._on_local_load,
            'local_cells': self._on_local_cells,   # 切本地图表页 → 同步每格 CSV ✓
            'local_add_indicator': self._on_local_add_indicator,
            'local_remove_indicator': self._on_local_remove_indicator,
            'local_strategy_trade': self._on_local_strategy_trade,
            'local_order': self._on_local_order,
            'local_account': self._on_local_account,
            'local_active': self._on_local_active,   # 点格子→切合约 ✓
            'local_account_action': self._on_local_account_action,
            'local_reset': self._on_local_reset,
            # ---- 扩展功能：交易工作台 ----
            'workbench': self._on_workbench,
            'workbench_submit': self._on_workbench_submit,
            'workbench_cancel': self._on_workbench_cancel,
            'workbench_modify': self._on_workbench_modify,
            'workbench_close_partial': self._on_workbench_close_partial,
            'workbench_limits': self._on_workbench_limits,
            'workbench_conditional_cancel':
                self._on_workbench_conditional_cancel,
            'workbench_reconcile': self._on_workbench_reconcile,
            'workbench_export': self._on_workbench_export,
            # ---- 扩展功能：策略研究平台 ----
            'research': self._on_research,
            'research_start': self._on_research_start,
            'research_cancel': self._on_research_cancel,
            'research_report': self._on_research_report,
            'research_delete': self._on_research_delete,
            # ---- 扩展功能：本地数据平台 ----
            'datahub': self._on_datahub,
            'datahub_refresh': self._on_datahub_refresh,
            'datahub_quality': self._on_datahub_quality,
            'datahub_resample': self._on_datahub_resample,
            'datahub_roll': self._on_datahub_roll,
            'datahub_ticks': self._on_datahub_ticks,
            'datahub_query': self._on_datahub_query,
            'datahub_export': self._on_datahub_export,
            # ---- 扩展功能：平台化 / 运维 ----
            'ops': self._on_ops,
            'ops_token_issue': self._on_ops_token_issue,
            'ops_token_revoke': self._on_ops_token_revoke,
            'ops_token_revoke_all': self._on_ops_token_revoke_all,
            'ops_task_add': self._on_ops_task_add,
            'ops_task_remove': self._on_ops_task_remove,
            'ops_task_toggle': self._on_ops_task_toggle,
            'ops_task_run': self._on_ops_task_run,
            'ops_notify_config': self._on_ops_notify_config,
            'ops_notify_test': self._on_ops_notify_test,
            'ops_version_snapshot': self._on_ops_version_snapshot,
            'ops_version_rollback': self._on_ops_version_rollback,
            'ops_versions': self._on_ops_versions,
        }

    def handle(self, message: str) -> Any:
        """``desk_~_{…}`` → 分发（Qt 回调 / HTTP POST 都走这里 ✓）"""
        payload = _protocol.decode_command(message)
        if not payload:
            return None
        handler = self.commands().get(str(payload.get('cmd') or ''))
        if handler is None:
            return None
        return handler(payload.get('payload') or {})

    #: 「设置 → 关于」里的链接（帮助 / 反馈 / 官网）
    HOME_URL = 'https://www.minibt.cn'
    DOCS_URL = 'https://www.minibt.cn'
    ISSUE_URL = 'https://github.com/MiniBtMaster/minibt/issues'

    def _on_open_url(self, payload) -> None:
        """用系统浏览器打开一个网址（Qt / 浏览器壳都走 `_open_path` ✓）"""
        url = str(payload.get('url') or '').strip() or self.HOME_URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        error = _open_path(url)
        if error:
            self.push_log(f'打开网页失败：{url}', 'warning')
            self.push(_protocol.patch_toast(f'打开网页失败：{url}', 'warning'))

    def _on_open_data_dir(self, payload) -> None:
        """打开 minibt 的本地数据目录（`~/.minibt`，没有就建 ✓）"""
        folder = str(payload.get('path') or '').strip()
        if not folder:
            folder = os.path.join(os.path.expanduser('~'), '.minibt')
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'创建数据目录失败：{error!r}', 'warning')
        error = _open_path(folder)
        if error:
            self.push(_protocol.patch_toast(f'数据目录：{folder}（{error}）', 'info'))
        else:
            self.push(_protocol.patch_toast(f'已打开数据目录：{folder}', 'success'))
        self.push_log(f'数据目录：{folder}', 'info')

    # ------------------------------------------------------------- 登录
    #: FutuOpenD 默认网关（和 miniqt / `--futu-host` 一致 ✓）
    FUTU_HOST = '127.0.0.1'
    FUTU_PORT = 11111

    def login_payload(self, kind: str = 'futures') -> Dict[str, Any]:
        """记住的登录信息（打开登录框时预填；**密码只在记住时才有** ✓）"""
        from . import user_prefs as _prefs
        kind = 'stocks' if str(kind) == 'stocks' else 'futures'
        return dict(_prefs.login().get(kind) or {})

    def _on_watch_get(self, _payload=None) -> None:
        """前端启动时拉一次收藏 / 自选分组（localStorage 会丢 ✗）"""
        from . import user_prefs as _prefs
        self.push({'type': 'watch', **_prefs.watch()})

    def _on_watch_set(self, payload) -> None:
        """前端改完（★ / 加入自选 / 新建分组）→ 整份落盘 ✓"""
        from . import user_prefs as _prefs
        value = _prefs.set_watch(payload or {})
        self.push({'type': 'watch', **value})
        # 这些合约也要跟着刷（首页自选行 / 迷你图 ✓）
        self._home_extra = _watch_symbols(value)[:120]

    def _on_login_info(self, payload) -> None:
        """前端打开登录框 → 把记住的账号推过去 ✓"""
        kind = str((payload or {}).get('kind') or 'futures')
        self.push(_protocol.patch_login(kind, 'info',
                                        saved=self.login_payload(kind)))

    def _login_saved(self, kind: str, values: Dict[str, Any]) -> None:
        """落盘记住的信息（失败不影响登录 ✓）"""
        try:
            from . import user_prefs as _prefs
            _prefs.save_login(kind, values)
        except Exception:                                        # noqa: BLE001
            pass

    def _login_failed(self, kind: str, text: str) -> None:
        """登录失败：登录框 + 运行日志 + toast 都说清楚 ✓"""
        self.push(_protocol.patch_login(kind, 'error', ok=False, text=text))
        self.push_log(text, 'error')
        self.push(_protocol.patch_toast(text, 'error'))

    def _after_connect(self, kind: str, text: str) -> None:
        """连上行情源之后：菜单 / 首页 / 报价 / 图表 / 账户 全刷一遍 ✓

        ⚠ **必须在主线程跑**：天勤的 `TqApi` 不是线程安全的，登录线程里再调
        `get_kline_serial` / `get_position` 会和主线程的 `pump()` 抢锁 →
        界面直接卡死（用户实测：登录后点换主题就转圈 ✗）。
        → 登录线程只负责建连，重活交给 `tick()` 里的 `_after_connect_job`。
        """
        self.no_service = False
        self.offline = False
        self.trader = None                 # 交易执行器按新 feeds 重建 ✓
        self.accounts = None               # 账户面板同上
        self.no_service = False
        self.offline = False
        self.trader = None                 # 交易执行器按新 feeds 重建 ✓
        self.accounts = None               # 账户面板同上
        self.push(_protocol.patch_markets(self.market_map()))
        self.push(_protocol.patch_login(kind, 'ok', ok=True, text=text))
        self.push_log(text, 'success')
        self.push(_protocol.patch_toast(text, 'success'))
        self._reload_pending = True        # 报价页：缓存 → 实时 ✓
        if self._home_active:
            try:
                self.push(self.home_payload())
            except Exception:                                    # noqa: BLE001
                pass
        try:
            self.push(self.account_payload())
        except Exception:                                        # noqa: BLE001
            pass
        self.push(self.trading_state(next(iter(self.tabs), '')))
        if self.tabs:                      # 离线时打开的图：补上数据 ✓
            self._reload_klines()

    def _run_connect(self) -> None:
        """在**主线程**建立行情连接（`TqApi` / `StockApi` 只能在创建线程用 ✓）

        * 登录框已推 `pending` 状态，这里同步连（tqsdk 连接通常 1~3 秒）；
        * 连上后把刷新任务交给 `_after_connect`（同一个线程 ✓）；
        * 失败只弹提示，不影响界面。
        """
        job = self._connect_pending
        self._connect_pending = None
        if not job:
            return
        kind, params = job
        self._login_busy = True
        # ★ 连接（tqsdk `TqApi(...)`）会阻塞 4~10 秒 → 先把"正在连接"刷到界面上，
        #   否则 Windows 直接给窗口标「未响应」（用户实测 ✗）
        try:
            self.push(_protocol.patch_login(kind, 'busy',
                                            text='正在连接，请稍候…'))
            pump = getattr(self, 'pump_events', None)
            if callable(pump):
                pump()
        except Exception:                                    # noqa: BLE001
            pass
        try:
            if kind == 'futures':
                # ★ 主线程建 api（tqsdk 只能在创建线程用 ✓）；合约清单已经
                #   改成读本地已下载的符号字典 → 不会再触发阻塞请求 ✓
                from tqsdk import (TqAccount, TqApi, TqAuth, TqKq,
                                   TqMultiAccount)
                auth = TqAuth(params['username'], params['password'])
                # ★ 实盘登录时**同时挂快期模拟 + 实盘**：
                #   账户面板可切换，图表策略 / 策略实盘都跟随当前账户 ✓
                self._preferred_account_index = (
                    1 if params.get('real') else 0)
                if params.get('real'):
                    accounts = [
                        TqKq(),
                        TqAccount(params['broker'], params['account'],
                                  params['trade_password']),
                    ]
                    target = TqMultiAccount(accounts)
                else:
                    target = TqKq()
                api = TqApi(target, auth=auth)
                self._real_account = bool(params.get('real'))
                # 实盘登录默认选中实盘账户（index 1）；仍可在账户页切回模拟
                self._preferred_account_index = (
                    1 if params.get('real') else 0)
                self.accounts = None
                feed = FuturesFeed(api, 'futures')
                self.futures = feed
                self.feeds.insert(0, feed)
                # 新连接：清掉上一轮“空合约跳过”的缓存，允许自动重试 ✓
                try:
                    self._skip_markets.clear()
                    self._empty_rows_retry_at = 0.0
                except Exception:                            # noqa: BLE001
                    pass
                label = (f"实盘 {params['broker']} {params['account']}"
                         if params.get('real') else '快期模拟')
                self._after_connect_pending = (
                    'futures', f"天勤已连接：{params['username']}（{label}）")
            else:
                from ..stock_api import StockApi
                api = StockApi(host=params['host'], port=params['port'],
                               trade=bool(params.get('trade')),
                               trd_env=str(params.get('trd_env') or 'SIMULATE'),
                               trd_market=str(params.get('trd_market')
                                              or 'CN'),
                               sim_account='desk')
                feed = StockFeed(api, 'stocks')
                self.stocks = feed
                self.feeds.append(feed)
                self._after_connect_pending = (
                    'stocks', f"富途行情已连接：{params['host']}:{params['port']}")
        except Exception as error:                               # noqa: BLE001
            text = str(error) or repr(error)
            if kind == 'futures':
                self._login_failed(
                    'futures', f'天勤登录失败：{text}'
                    '（检查账号密码 / 网络 / tqsdk 是否安装 ✓）')
            else:
                self._login_failed(
                    'stocks', f'股票连接失败：{text}（先启动并登录 FutuOpenD ✓）')
        finally:
            self._login_busy = False

    def _run_after_connect(self) -> None:
        """登录线程建好 api → 主线程这里统一刷新（**不要**在登录线程里调 tqsdk ✗）"""
        job = self._after_connect_pending
        self._after_connect_pending = None
        if not job:
            return
        self._login_busy = False          # 主线程接管 api ✓
        kind, text = job
        try:
            self._after_connect(kind, text)
        except Exception as error:                               # noqa: BLE001
            where = getattr(self, '_tick_step', '') or '?'
            self.push_log(f'刷新失败（{where}）：{error!r}', 'error')
            self.push(_protocol.patch_toast(
                f'已连接，但刷新界面失败：{error!r}', 'warning'))

    def _on_connect_futures(self, payload) -> None:
        """登录天勤（快期模拟 / 实盘）—— 离线启动后也能接入 ✓"""
        payload = payload or {}
        username = str(payload.get('username') or '').strip()
        password = str(payload.get('password') or '')
        real = bool(payload.get('real'))
        broker = str(payload.get('broker') or '').strip()
        account = str(payload.get('account') or '').strip()
        trade_password = str(payload.get('trade_password') or '')
        if not username or not password:
            self._login_failed('futures', '天勤账号和密码都要填 ✓')
            return
        if real and not (broker and account and trade_password):
            self._login_failed('futures', '实盘账户需要期货公司 / 资金账号 / 交易密码')
            return
        if self.futures is not None and self.futures.available():
            self.push(_protocol.patch_login(
                'futures', 'ok', ok=True, text='期货已经连上了（无需重复登录）'))
            return
        login_values = {
            'username': username, 'password': password,
            'remember': bool(payload.get('remember')),
            'real': real, 'broker': broker, 'account': account,
            'trade_password': trade_password,
        }
        self._login_futures = dict(login_values)
        self._login_saved('futures', login_values)
        self.push(_protocol.patch_login('futures', 'pending',
                                        text='正在登录天勤…（首次连接要 3~10 秒）'))
        self.push_log(f'正在登录天勤：{username}', 'info')
        # ★ **必须建在主线程**：tqsdk 的 TqApi 只能在创建它的线程里用，
        #   `close()` 还不能在协程里调用（用户实测：登录后数据不更新 +
        #   「不能在协程中调用 close」✗）。这里只登记，真正连接由 tick 执行 ✓
        self._connect_pending = ('futures', {
            'username': username, 'password': password, 'real': real,
            'broker': broker, 'account': account,
            'trade_password': trade_password,
        })

    def _on_connect_stocks(self, payload) -> None:
        """连接富途 OpenD 网关（不需要账号，只要网关开着 ✓）"""
        payload = payload or {}
        host = str(payload.get('host') or '').strip() or self.FUTU_HOST
        try:
            port = int(payload.get('port') or self.FUTU_PORT)
        except (TypeError, ValueError):
            self._login_failed('stocks', '网关端口要是数字 ✓')
            return
        trade = bool(payload.get('trade'))
        trd_env = str(payload.get('trd_env') or 'SIMULATE').upper()
        if trd_env not in ('SIMULATE', 'REAL'):
            trd_env = 'SIMULATE'
        trd_market = str(payload.get('trd_market') or 'CN').upper()
        if trd_market not in ('CN', 'HK', 'US', 'JP'):
            trd_market = 'CN'
        if self.stocks is not None and self.stocks.available():
            api = getattr(self.stocks, 'api', None)
            same = (bool(getattr(api, '_trade_enabled', False)) == trade
                    and (not trade or str(getattr(api, 'trd_market', '')
                                          or '').upper() == trd_market))
            if same:
                self.push(_protocol.patch_login(
                    'stocks', 'ok', ok=True,
                    text='股票行情已经连上了（无需重复连接）'))
                return
            # ★ 已连行情 / 别的市场 → 先关旧连接，再按新参数重连
            try:
                self.stocks.close()
            except Exception:                                # noqa: BLE001
                pass
            try:
                self.feeds = [feed for feed in self.feeds
                              if feed is not self.stocks]
            except Exception:                                # noqa: BLE001
                pass
            self.stocks = None
            self.accounts = None
            self.trader = None
        self._login_saved('stocks', {'host': host, 'port': port,
                                     'trade': trade, 'trd_env': trd_env,
                                     'trd_market': trd_market})
        self.push(_protocol.patch_login(
            'stocks', 'pending',
            text=f'正在连接 FutuOpenD {host}:{port}'
                 f'（交易：{trd_env if trade else "关闭"}'
                 f'，市场：{trd_market}）…'))
        self.push_log(f'正在连接 FutuOpenD：{host}:{port}'
                      f'（trade={trade}, env={trd_env}, market={trd_market}）',
                      'info')
        # ★ 同样交给主线程（StockApi 的 futu 上下文不是线程安全的 ✓）
        self._connect_pending = ('stocks', {
            'host': host, 'port': port, 'trade': trade,
            'trd_env': trd_env, 'trd_market': trd_market})

    def _on_test_futu(self, payload) -> None:
        """「测试连接」：只探端口（不建行情上下文，几毫秒出结果 ✓）"""
        payload = payload or {}
        host = str(payload.get('host') or '').strip() or self.FUTU_HOST
        try:
            port = int(payload.get('port') or self.FUTU_PORT)
        except (TypeError, ValueError):
            port = self.FUTU_PORT
        self.push(_protocol.patch_login('stocks', 'test',
                                        text=f'正在检测 {host}:{port} …'))

        def work() -> None:
            import socket
            try:
                with socket.create_connection((host, port), timeout=3):
                    pass
            except OSError as error:                             # noqa: PERF203
                self.push(_protocol.patch_login(
                    'stocks', 'test', ok=False,
                    text=f'连不上 {host}:{port}（{error}）'
                         '（请先启动并登录 FutuOpenD）'))
                return
            self.push(_protocol.patch_login(
                'stocks', 'test', ok=True,
                text=f'网关可用：{host}:{port} → 可以点「连接」✓'))

        threading.Thread(target=work, daemon=True,
                         name='desk-test-futu').start()

    def _on_set_setting(self, payload) -> None:
        """偏好设置（`ticket_click_orders` 等）→ 落盘 + 回推 ✓"""
        from . import user_prefs as _prefs
        key = str(payload.get('key') or '').strip()
        if not key:
            return
        if key == 'chart_reset':
            values = _prefs.reset_chart_settings()
            self.push({'type': 'settings', 'settings': values})
            self._reload_klines()
            self.push_log('图表配置已恢复默认值', 'info')
            return
        values = _prefs.set_setting(key, payload.get('value'))
        self.push({'type': 'settings', 'settings': values})
        # 「模拟账户」设置 → 立刻作用到本地模拟账户 ✓
        if key in ('sim_initial_cash', 'sim_fee_mode', 'sim_fee_value'):
            self._apply_sim_setting(key, payload.get('value'))
        if key in ('log_terminal', 'log_ui'):
            self._apply_log_settings(values)
        # 「图表配置」里的根数变了 → 重新拉一次 K 线（否则要重开图才生效 ✓）
        if key in ('chart_history', 'chart_data_length'):
            self._reload_klines()

    def _apply_log_settings(self, values: Dict[str, Any] = None) -> None:
        """「运行日志」输出开关（终端 / 程序内）✓

        默认：**终端输出** + 程序内都开；用户可以在
        「设置 → 系统设置 → 运行日志」里单独关掉 ✓
        """
        values = values or {}
        terminal = values.get('log_terminal')
        ui = values.get('log_ui')
        self.log_to_stdout = True if terminal is None else bool(terminal)
        self.log_to_ui = True if ui is None else bool(ui)

    def _apply_sim_setting(self, key: str, value: Any) -> None:
        """改一项模拟账户设置：配置 → 推账户 + 分析（各页面都刷 ✓）"""
        def number(raw: Any) -> Optional[float]:
            try:
                return float(raw)
            except (TypeError, ValueError):
                return None

        sim = self.local_sim()
        if key == 'sim_initial_cash':
            amount = number(value)
            if amount is None or amount <= 0:
                self.push(_protocol.patch_toast('初始现金要大于 0', 'warning'))
                return
            sim.configure(initial_cash=amount)
            self.push_log(f'模拟账户初始现金 → {amount:,.2f}（账户已重置）',
                          'info')
        elif key == 'sim_fee_mode':
            sim.configure(fee_mode=str(value or 'fixed'))
        else:
            amount = number(value)
            if amount is None or amount < 0:
                self.push(_protocol.patch_toast('手续费不能小于 0', 'warning'))
                return
            sim.configure(fee_value=amount)
            self.push_log(
                f"模拟账户手续费 → {'成交额 ' + f'{amount:g}%'
                                   if sim.fee_mode == 'percent'
                                   else f'每手 {amount:g} 元'}", 'info')
        self._push_sim_analysis()
        self._push_sim_accounts()
        self._push_all_sim_positions()

    def sim_position(self, symbol: str,
                     local: bool = False) -> Dict[str, Any]:
        """本地模拟账户的持仓 → `position` 补丁（前端画持仓线 ✓）

        `local=True` → 给「本地图表」用（`app.ts` 路由到本地页）；
        否则给看盘窗口（回放时用 ✓）。没有持仓 → 只有 `symbol`，前端删线。
        """
        payload: Dict[str, Any] = {'type': 'position', 'symbol': symbol}
        if local:
            payload['local'] = True
            # ★ 多布局：告诉前端是**哪一格**（否则只画在"当前格"上 ✗）
            for cell_index, cell_name in (
                    getattr(self, '_local_cell_names', {}) or {}).items():
                if str(cell_name) == str(symbol):
                    payload['cell'] = int(cell_index)
                    break
        try:
            sim = self.local_sim()
        except Exception:                                        # noqa: BLE001
            return payload
        book = (sim.positions or {}).get(symbol) or {}
        long_qty = float(book.get('long') or 0.0)
        short_qty = float(book.get('short') or 0.0)
        if long_qty <= 0 and short_qty <= 0:
            return payload                         # 空 → 前端移除持仓线 ✓
        last = sim._price(symbol)
        if long_qty > 0:
            avg = float(book.get('avg_long') or 0.0) or float(last or 0.0)
            payload['long'] = {
                'side': '多', 'volume': long_qty, 'avg': avg,
                'profit': (last - avg) * long_qty if last else 0.0,
            }
        if short_qty > 0:
            avg = float(book.get('avg_short') or 0.0) or float(last or 0.0)
            payload['short'] = {
                'side': '空', 'volume': short_qty, 'avg': avg,
                'profit': (avg - last) * short_qty if last else 0.0,
            }
        return payload

    def pending_orders(self, symbol: str = '',
                       local: bool = False) -> List[dict]:
        """挂单（未成交委托）→ 挂单线数据 ✓

        * ``local=True`` / 回放 / 没有行情源 → **本地模拟账户**；
        * 否则 → 天勤模拟（或实盘）账户的 ``ALIVE`` 委托 ✓
        """
        if symbol and not local and not _symbols.is_tradeable(symbol):
            return []                       # 主连 / 指数没有委托 ✓
        if local or not self.feeds or symbol in self.replay_symbols:
            try:
                return list(self.local_sim().pending_orders(symbol))
            except Exception:                                    # noqa: BLE001
                return []
        view = self.account_view()
        if view is None:
            return []
        try:
            return list(view.pending_orders(symbol))
        except Exception:                                        # noqa: BLE001
            return []

    def orders_payload(self, symbol: str = '',
                       local: bool = False) -> Dict[str, Any]:
        """`orders` 补丁（挂单线：价格 + 买/卖 + 手数 ✓）"""
        payload: Dict[str, Any] = {'type': 'orders', 'symbol': symbol,
                                   'items': self.pending_orders(symbol, local)}
        if local:
            payload['local'] = True
            # ★ 多布局：告诉前端是**哪一格**（同 `sim_position` ✓）
            for cell_index, cell_name in (
                    getattr(self, '_local_cell_names', {}) or {}).items():
                if str(cell_name) == str(symbol):
                    payload['cell'] = int(cell_index)
                    break
        return payload

    def _push_orders(self, symbol: str = '', local: bool = False,
                     cell: int = None) -> None:
        """推一次挂单线（没有挂单 → 空列表 = 前端删线 ✓）

        ``cell``：多布局的格号（多张图各自的挂单线 ✓）
        """
        if not symbol:
            return
        payload = self.orders_payload(symbol, local)
        if cell is not None:
            payload['cell'] = int(cell)
        self.push(payload)

    def _push_sim_position(self, symbol: str, local: bool = False) -> None:
        """推一根持仓线补丁（没有持仓 → 空补丁 = 让前端清掉 ✓）"""
        if not symbol:
            return
        self.push(self.sim_position(symbol, local=local))

    def _push_all_sim_positions(self) -> None:
        """本地图表 + 回放里的持仓线一起刷（重置 / 改设置后用 ✓）"""
        # ★ 多布局：每个已加载的本地 CSV 都推一次（不能只推当前格）
        seen = set()
        for cell_name in ((getattr(self, '_local_cell_names', {}) or {})
                          .values()):
            name = str(cell_name or '')
            if name and name not in seen:
                seen.add(name)
                self._push_sim_position(name, local=True)
        last = str(getattr(self, 'last_symbol', '') or '')
        if last and last not in seen:
            self._push_sim_position(last, local=True)
        for symbol in list(self.replay_symbols)[:4]:
            self._push_sim_position(symbol)

    def _push_sim_accounts(self) -> None:
        """把模拟账户余额 / 持仓推到「本地图表」和「回放」的账户页 ✓"""
        sim = self.local_sim()
        self.push(sim.payload(str(getattr(self, 'last_symbol', '') or '')))
        for symbol in list(self.replay_symbols)[:4]:
            try:
                self.push(self.replay_account_payload(symbol))
            except Exception:                                    # noqa: BLE001
                continue

    def _reload_klines(self) -> None:
        """按新的 `chart_history` 重新拉一遍已打开 tab 的 K 线 ✓"""
        for symbol, info in list(self.tabs.items()):
            feed = info.get('feed') or pick_feed(self.feeds, symbol)
            if feed is None:
                continue
            length = self.data_length()
            frame = feed.klines(symbol, info.get('cycle') or 60, length)
            info['loaded_len'] = length
            self._reset_kline_state(info)     # 长度变了 → 全量重推 ✓
            bars = _protocol.bars_from_frame(frame)
            self._note_kline_state(
                info, bars, len(frame) if frame is not None else 0)
            if bars:
                self.push(dict(_protocol.patch_kline(symbol, bars, True),
                               length=length,
                               data_length=self.chart_lengths()[1]))
        # 说明：恢复默认 / 改数据长度会各触发一次刷新，原日志会重复刷屏；
        #       只在需要排查时打开（用户要求默认静默 ✓）。
        # self.push_log(f'图表数据长度 → {self.candles_length()} 根', 'info')

    def _on_ready(self, _payload) -> None:
        self.flush()
        self._warm_web_cache()

    def _warm_web_cache(self) -> None:
        """启动时在后台把**官网首页**抓进缓存（第一次点也秒开 ✓）"""
        import threading as _threading
        from . import web as _web

        def run() -> None:
            try:
                _web.page_html('https://www.minibt.cn')
            except Exception:                                # noqa: BLE001
                pass

        _threading.Thread(target=run, name='desk-web-warm',
                          daemon=True).start()

    # -------------------------------------------------------- 策略实验室
    def push_alert(self, title: str, message: str, detail: str = '',
                   level: str = 'warning') -> None:
        """弹一个**模态提醒**（体检不通过 / 加到图表失败 等 ✓）

        只有顶部 toast 的话一闪就没，用户实测"没有提醒"✗ —— 这种需要用户
        知道并去改代码的错误，统一走弹窗。
        """
        self.push({'type': 'alert', 'level': str(level or 'warning'),
                   'title': str(title or '提示'),
                   'message': str(message or ''),
                   'detail': str(detail or '')})

    def _on_strategy_check(self, payload) -> None:
        """回测 / 参数优化前的**体检**（语法 / 是否有 Strategy / 有没有 op_config）✓

        前端点「策略回测 / 参数优化」先发这个命令；通过才真的开策略 Tab，
        否则只在顶部中间弹一条提示（不再白开一个空 Tab ✗）。
        """
        from . import personal as _pi
        payload = payload or {}
        path = str(payload.get('path') or '')
        mode = 'optimize' if str(payload.get('mode')) == 'optimize' else 'backtest'
        result = _pi.check_strategy_file(path)
        ok = bool(result.get('ok'))
        reason = str(result.get('reason') or '')
        kind = str(result.get('mode') or 'strategy')       # strategy / indicator
        if ok and mode == 'optimize' and not result.get('has_op_config'):
            if kind == 'indicator':
                # 指标信号：没写 op_config 时后端会**按 params 自动生成网格** ✓
                pass
            else:
                ok = False
                reason = ('这个策略没有 `op_config`，无法做参数优化 → '
                          '在策略类里加一行 `op_config = dict(...)` 再试')
        if not ok:
            self.push_log(f'[体检] {path}: {reason}', 'warning')
            # ★ 不能只有顶部 toast（一闪就没了，用户说"没有弹窗信息提醒"✗）
            title = ('参数优化前体检没通过' if mode == 'optimize'
                     else '回测前体检没通过')
            self.push_alert(title, reason,
                            detail=f'{os.path.basename(path)}  ·  {mode}')
        self.push({
            'type': 'strategy_check', 'id': str(payload.get('id') or ''),
            'path': path, 'mode': mode, 'ok': ok, 'reason': reason,
            'strategies': result.get('strategies') or [],
            'has_op_config': bool(result.get('has_op_config')),
            'kind': kind,                     # strategy / indicator ✓
        })

    #: 编辑器「帮助」文本（用户给定的内容 ✓）
    EDITOR_HELP = """编辑帮助（minibt desk 代码编辑器）

【指标】

1. 添加指标的图表对象，以鼠标最后点击过的那个图表为准。
2. 图表中添加指标以「指标名称」进行区分：当添加相同名称的指标时，系统会替换前一个指标。
3. 图表中可以添加多个不同名称的指标。
4. 本地图表按当前 CSV 重算；看盘窗口按当前合约重算。
5. BtIndicator 可以写 PlotInfo 样式（linestyle / bandstyle / signalstyle /
   tablestyle / spanstyle / candlestyle / vpstyle / watermark）；
   函数式指标只能自动配色，写不了这些样式。
6. 本地图表的每个页面都是**独立副本**：指标 / 策略按「页面」存，
   两个页面加载**同一份 CSV** 也互不影响；**加载数据只加载 K 线**
   （不会带回上次加过的指标），要指标请重新添加或用指标模板。
7. 指标类写 pair_klines = (腿A, 腿B) 时，回测 / 参数优化会自动走
   pair_backtest，并保留两条真实合约的 K 线；单腿指标走 signal_backtest。

【加到图表】

一、指标
    1. 加到鼠标最后点击的图表；同名替换，不同名共存。
    2. 文件解析顺序：有 Strategy → 策略；否则有 BtIndicator + 交易信号 →
       指标信号；否则按普通指标。
    3. 加到图表只计算一次，不会下单；回放播放 / 单步才推进策略 next。

二、策略：智能添加
    1. 写法 1：get_kline(LocalDatas.xxx) / get_kline("SHFE.xxx")
       - 扫描策略源码里的合约，按合约数量自动选布局：
         1 个 → 单图；2 个 → 左右两图；3 个 → 横排三图；
         4 个 → 2×2 四图。
       - 本地图表：按名字加载本地 CSV / LocalDatas；
         看盘窗口：先到天勤报价校验（存在、未下市、可交易），
         通过后再加载 K 线。
       - 数据缺失 / 合约不存在 / 已下市 → 弹窗并保持原布局不变。
       - 自动布局目前最多 4 个合约；更多请先手动打开对应图表。
    2. 写法 2：self.klines1 / klines2 / ...
       - 这种写法没有合约名，系统无法自动知道要加载什么；
       - 必须先手动选好布局，并加载 >= 用到的最大编号的合约 / CSV；
       - 数量不足会弹窗；多出来的 klinesN 是 None，.close 会报错。
    3. 一个图表只放一个策略；再放 = 替换；策略线优先于指标。
       ★ 本地图表 / 实时图表的**一个页面只支持一个策略**：
         - 重新「加到图表」（同一个或另一个策略都一样）会先把上一个策略
           清掉（所有布局格一起清），再加载新策略；
           布局 / 指标 / 画线都保留，不会被重置。
         - 需要同时看 / 跑多个策略 → **多开本地图表页面**：
           顶栏 ＋ → 本地图表，或首页-图表工作台右侧「新建本地图表」，
           页面依次叫「本地图表1」「本地图表2」…；
           每个页面各放一个策略（同一个 CSV 可以同时开多个页面）。
         - 或者用「策略实盘」（Bt(live=True)）：它不占图表页面，
           可以同时跑多个（编辑器「策略实盘」按钮，显示「运行中 ×N」）。
    4. 配对策略用两个 get_kline 分别取两条腿；本地图表自动左右两图。
    5. 策略文件改了要重新「加到图表」，不会热更新。
    6. 策略跑起来以后 next() 报错**不会影响图表**（不关页、不清线）：
       第一次弹窗提醒，之后只在终端 / 「运行日志」里提醒（每 10 秒最多一条）。
       修好后：先删掉策略（工具栏 🗑 → 1 editor.xxx /「策略管理」），
       再重新「加到图表」。
    7. 指标算不出来（参数非法 / 数据不够 / 脚本报错）→ 弹窗提醒，
       并且**指标不会加到图上**（自动撤回去）。

【策略】

一、单合约策略
    1. 当策略中指定了合法的合约及其周期时，优先使用策略指定的合约与周期作为 K 线数据。
    2. 当策略中没有指定合约时，默认以图表中第一个图表的合约与周期作为 K 线数据；
       策略中可直接使用 self.kline 作为 K 线数据源。
    3. 当策略中指定的合约不合法时，默认使用图表中第一个图表的合约与周期作为 K 线数据。

二、多合约策略
    1. 多合约策略必须指定合法的合约及其周期，并在策略中使用 self.get_kline
       获取到合法数据后才可以使用。
    2. 配对策略（两条腿）就是多合约策略：分别 get_kline 两条腿，
       再用 IndFrame 组合价差 / 信号。
    3. 多布局时，策略里的 self.klines1/2/... 依次对应第 1/2/... 张图；
       用到的最大编号不能超过当前已加载的图表数。

三、策略回放 / 本地模拟账户
    1. 点「加到图表」不下单；进入回放（▶▶）也不下单；
       只有播放 / 单步推进 next() 时，才会自动交易本地模拟账户。
    2. 有策略时，本地模拟账户按 minibt 内置账户参数重置：
       初始资金 = Strategy.config.value；保证金率 / 手续费 / 滑点来自
       config 和每条 KLine / Broker。单合约手续费可在策略里覆盖：
           self.data.fixed_commission = 1.
    3. 没有策略的手动买 / 卖，仍使用「设置 → 模拟账户」。
    4. 盈亏 / 手续费会乘合约乘数；期货按占用保证金计算可用资金。

【策略回测 / 参数优化】

代码编辑器顶栏的「策略回测」和「参数优化」都对当前正在编辑的文件生效。

一、策略回测
    1. 文件里要有 1 个（或多个）继承 minibt.Strategy 的策略类；
       点「策略回测」→ 后台跑一次正常回测 → 出图 + 交易记录。
    2. 文件里没有 Strategy、但有 BtIndicator + 交易信号时，走
       signal_backtest(...)（单合约）。
    3. 指标类有 pair_klines = (腿A, 腿B) 时，走 pair_backtest(...)，
       回测后保留两条真实合约。
    4. 回测使用 minibt 自己的账户，不是本地图表的 desk 模拟账户。

二、参数优化（策略）
    1. 策略类里写 op_config，例如：

           class MyStrategy(Strategy):
               params = dict(length=10)
               op_config = OpConfig(
                   target=['sharpe'],
                   weights=(1.,),
                   opconfig=OptunaConfig(n_trials=100),
                   op_method='optuna',
                   params=dict(length=(5, 30, 1)))

    2. 点「参数优化」→ 后台优化 → 底部进度条 → 自动用最优参数再回测一次；
    3. 「交易记录」页的「参数优化」子页里有：优化参数列表（可筛选/排序）、
       另存优化结果、优化图表（Optuna 可视化）、用选中解回测、写回最优参数。

三、参数优化（指标信号）
    1. 文件里要有继承 minibt.BtIndicator 的类，且带完整的交易信号：
       long_signal + exitlong_signal，或 short_signal + exitshort_signal，
       或双向都有（信号名写在 lines 里即可）；
    2. 用类属性 data 指定数据（支持 LocalDatas）：

           class MyMA(BtIndicator):
               data = LocalDatas.test
               lines = ['ma1', 'ma2', 'long_signal', 'short_signal',
                        'exitlong_signal', 'exitshort_signal']
               params = dict(length1=10, length2=20)
               op_config = OptimizeConfig(
                   params=dict(length1=(5, 30, 2), length2=(30, 60, 2)),
                   target=['final_equity', 'sharpe'], method='optuna',
                   config={'n_trials': 100})

               def next(self):
                   ...

    3. 类里没写 op_config 时，点「参数优化」会弹窗让你填参数范围 / 目标 / 方法；
    4. 优化完成后的界面与策略优化完全一致（列表 / 图表 / 写回参数 / 选中解回测）；
    5. 信号回测 / 优化没有 result 目标，权益目标请写 final_equity；
    6. 配对指标再加上 pair_klines 和 pair_backtest_kwargs，
       优化会自动走 pair_backtest，图表保留两条腿；
    7. 检测顺序：先用「有 op_config 的策略」，没有再用「有信号的指标」，
       两者都不满足会提示。"""

    def _on_editor_help(self, payload=None) -> None:
        """编辑器「帮助」→ 指标 / 策略 / 回测 / 参数优化 的使用说明 ✓"""
        self.push({'type': 'editor_help', 'text': self.EDITOR_HELP})

    def _on_clipboard_set(self, payload=None) -> None:
        """把文本写进系统剪贴板（编辑器「复制地址」用 ✓）

        Qt 壳是 `file://`，浏览器里 `navigator.clipboard` 需要安全上下文 →
        经常直接 reject（用户实测「复制地址不可用」✗），所以走后端剪贴板 ✓
        """
        text = str((payload or {}).get('text') or '')
        if not text:
            return
        ok = False
        try:
            from PyQt6.QtWidgets import QApplication
            board = QApplication.clipboard()
            if board is not None:
                board.setText(text)
                ok = True
        except Exception:                                    # noqa: BLE001
            ok = False
        if not ok:
            try:
                import tkinter
                root = tkinter.Tk()
                root.withdraw()
                root.clipboard_clear()
                root.clipboard_append(text)
                root.update()
                root.destroy()
                ok = True
            except Exception:                                # noqa: BLE001
                ok = False
        self.push({'type': 'clipboard', 'ok': ok, 'text': text})
        if not ok:
            self.push_log('复制失败：系统剪贴板不可用', 'warning')

    def _on_web_page(self, payload=None) -> None:
        """「网页 tab」：后端抓 HTML 再塞给 iframe（**绕开 X-Frame-Options** ✓）

        * 官网 / 文档站点常带 `X-Frame-Options: SAMEORIGIN` 或 CDN 的
          「禁止嵌入」策略 → 直接 `<iframe src>` 会被拦（用户实测：首页能开、
          点进文档页就被拦 ✗）；
        * 后端 `urllib` 抓成 HTML（带浏览器 UA），补 `<base>` + 站内链接钩子，
          前端用 `srcdoc` 显示 —— 静态文档站完全够用 ✓
        * 抓取放在**后台线程**做（最长 12 秒），不阻塞节拍 ✓
        """
        import threading as _threading
        from . import web as _web
        payload = payload or {}
        url = str(payload.get('url') or '')
        tab_id = str(payload.get('id') or '')

        def run() -> None:
            # `page_html` 自带缓存（同一 URL 10 分钟内**秒开** ✓）
            result = _web.page_html(url)
            patch = {'type': 'web_page', 'id': tab_id, 'url': url}
            if result.get('ok'):
                patch.update({
                    'ok': True,
                    'final': str(result.get('url') or url),
                    'cached': bool(result.get('cached')),
                    'html': str(result.get('html') or ''),
                })
            else:
                patch.update({'ok': False,
                              'error': str(result.get('error') or '抓取失败')})
            self.push(patch)

        _threading.Thread(target=run, name='desk-web-page',
                          daemon=True).start()

    def _on_lsp_start(self, payload=None) -> None:
        """起一个**本地 jedi LSP**（`ws://127.0.0.1:<随机端口>`）✓

        编辑器用它做 补全 / 悬停 / 跳转定义 / 引用 / 签名 / 大纲 / 折叠 /
        格式化 / 重命名 / **语法 + ruff 诊断**。
        重复调用只会返回同一个服务（幂等 ✓）；jedi 缺失时返回 `status=missing`
        并带上安装提示，前端只在状态栏显示，不影响编辑 ✓
        """
        from . import lsp as _lsp
        if self._lsp is None:
            from . import personal as _pi
            try:
                _pi.ensure_directories()
            except Exception:                                # noqa: BLE001
                pass
            self._lsp = _lsp.LspService(root=_pi.PERSONAL_ROOT)
        info = self._lsp.start()
        if info.get('status') == 'ready':
            self.push_log(f'LSP 已启动：{info.get("url")}（jedi '
                          f'{info.get("jedi")}）', 'info')
        elif info.get('status') == 'missing':
            self.push_log(f'LSP 不可用：{info.get("error")}', 'warning')
        self.push(info)

    def _on_lsp_stop(self, payload=None) -> None:
        """关掉 LSP（编辑器关 / 应用退出时 ✓）"""
        if self._lsp is None:
            return
        self._lsp.stop()
        self.push(self._lsp.info())

    def _on_strategy_start(self, payload) -> None:
        from .strategy_lab import StrategyLab
        payload = payload or {}
        session_id = str(payload.get('id') or '')
        if not session_id:
            self._strategy_seq += 1
            session_id = f'strategy_{self._strategy_seq}'
        lab = self._strategy_labs.get(session_id)
        if lab is None:
            lab = StrategyLab(self, session_id)
            self._strategy_labs[session_id] = lab
        lab.start(payload)

    def _on_strategy_indicator_params(self, payload) -> None:
        """回测图图例齿轮 → 指标参数（重算 + 刷新图表 ✓）"""
        lab = self._strategy_labs.get(str((payload or {}).get('id') or ''))
        if lab is not None:
            lab.indicator_params(payload or {})

    def _on_strategy_select(self, payload) -> None:
        lab = self._strategy_labs.get(str((payload or {}).get('id') or ''))
        if lab is not None:
            lab.select(payload or {})

    def _on_strategy_cancel(self, payload) -> None:
        lab = self._strategy_labs.get(str((payload or {}).get('id') or ''))
        if lab is not None:
            lab.cancel()

    def _on_strategy_trial_run(self, payload) -> None:
        payload = payload or {}
        lab = self._strategy_labs.get(str(payload.get('id') or ''))
        if lab is None:
            return
        lab.start({'file': lab.file, 'mode': 'backtest',
                   'params': payload.get('params') or {},
                   'id': lab.id})

    def strategy_chart_html(self, session_id: str, key: str,
                            theme: str = 'dark') -> str:
        """浏览器壳 iframe 用：返回 MiniQT 图表 HTML ✓"""
        lab = self._strategy_labs.get(str(session_id or ''))
        if lab is None:
            raise RuntimeError('策略会话不存在')
        return lab.chart_html(key, theme)

    def _on_strategy_chart_file(self, payload) -> None:
        """Qt/file:// 壳：生成真实 HTML 文件，返回 file URL 给 iframe ✓"""
        payload = payload or {}
        session_id = str(payload.get('id') or '')
        lab = self._strategy_labs.get(session_id)
        if lab is None:
            self.push({'type': 'strategy_error', 'id': session_id,
                       'message': '策略会话不存在'})
            return
        key = str(payload.get('key') or '')
        theme = str(payload.get('theme') or 'dark')
        try:
            url = lab.chart_file(key, theme)
        except Exception as error:                               # noqa: BLE001
            self.push({'type': 'strategy_error', 'id': session_id,
                       'message': f'{type(error).__name__}: {error}'})
            return
        self.push({'type': 'strategy_chart_file', 'id': session_id,
                   'key': key, 'url': url})

    def _on_default_realtime(self, payload=None) -> None:
        """「＋ → 实时图表」没有合约时：取主力 + 上期所第一个合约 ✓

        优先读全市场索引（本地 sqlite，秒回）；索引还没好时读 symbol_cache；
        最后兜底到上期所主力螺纹 `KQ.m@SHFE.rb`，保证不会打开空白页。
        """
        # 实时图表只有在**天勤已连接**时才能正常拉 K 线；没连 → 空白图表
        futures = getattr(self, 'futures', None)
        if futures is None or not getattr(futures, 'available', lambda: False)():
            self.push({'type': 'default_realtime', 'symbol': '', 'name': ''})
            return
        symbol = ''
        name = ''
        try:
            rows = self.symbol_index() or []
        except Exception:                                        # noqa: BLE001
            rows = []
        for row in rows:
            if str(row.get('type') or '').upper() != 'CONT_MAIN':
                continue
            if str(row.get('exchange') or '').upper() != 'SHFE':
                continue
            symbol = str(row.get('symbol') or '')
            name = str(row.get('name') or '')
            if symbol:
                break
        if not symbol:
            cache = self.symbol_cache()
            if cache is not None:
                try:
                    cached = cache.get('CONT_MAIN:SHFE') or []
                except Exception:                                # noqa: BLE001
                    cached = []
                for row in cached:
                    symbol = str(row.get('symbol') or '')
                    name = str(row.get('name') or '')
                    if symbol:
                        break
        if not symbol:
            feed = self.futures
            getter = getattr(feed, 'contracts', None)
            if callable(getter):
                try:
                    candidates = list(getter('CONT_MAIN', 'SHFE') or [])
                except Exception:                                # noqa: BLE001
                    candidates = []
                if candidates:
                    symbol = str(candidates[0])
                    try:
                        name = str(feed.name_of(symbol) or '')
                    except Exception:                            # noqa: BLE001
                        name = ''
        if not symbol:
            # ★ 不要再用 `KQ.m@SHFE.rb` 兜底：天勤某些时点会把它映射到
            #   服务端已不存在的 `rb2701`，订阅后 wait_update 直接抛
            #   GraphQL 错误 → 整个行情泵被拖死（本轮实测 ✗）。
            #   实在没有合约就打开空白图表 + 商品搜索。
            self.push({'type': 'default_realtime', 'symbol': '',
                       'name': ''})
            return
        self.push({'type': 'default_realtime', 'symbol': symbol,
                   'name': name})

    # -------------------------------------------------------- 首页
    def _on_home(self, payload) -> None:
        """首页可见性：可见才推 home 补丁（不可见时 tick 不刷）✓"""
        self._home_active = bool((payload or {}).get('active', True))
        if self._home_active:
            self._home_at = 0.0
            self.push(self.home_payload(full=True))

    def _on_home_main(self, payload) -> None:
        """首页「主力」分类：某交易所的主力合约（**先读缓存**，没有再查 ✓）

        `query_cont_quotes` 在实盘会阻塞 → 缓存优先；查到的结果写回缓存，
        下次秒开 ✓
        """
        exchange = str((payload or {}).get('exchange') or 'CFFEX').upper()
        cache = self.symbol_cache()
        key = f'CONT_MAIN:{exchange}'
        rows = []
        if cache is not None:
            try:
                rows = list(cache.get(key) or [])
            except Exception:                                    # noqa: BLE001
                rows = []
        if not rows:
            # ★ 市场全景 / 主力始终由**天勤**负责；不能跟报价页筛选
            #   （股票页时 current_feed 是富途，会取不到主力 ✗）
            feed = self.futures or self.current_feed()
            getter = getattr(feed, 'contracts', None)
            if callable(getter):
                try:
                    symbols = list(getter('CONT_MAIN', exchange) or [])
                except Exception as error:                       # noqa: BLE001
                    self.push_log(f'主力（{exchange}）取合约失败：{error!r}',
                                  'warning')
                    symbols = []
                rows = [_symbols.row(symbol=symbol,
                                     name=getattr(feed, 'name_of', lambda s: '')(
                                         symbol) or '')
                        for symbol in symbols]
                if rows and cache is not None:
                    try:
                        cache.put(key, rows)
                    except Exception:                            # noqa: BLE001
                        pass
        self._remember_main_indices(rows)
        if not rows and self.futures is not None:
            self._home_main_retry_exchange = exchange
            self._home_main_retry_at = time.monotonic() + 2.0
        else:
            self._home_main_retry_exchange = ''
            self._home_main_retry_at = 0.0
        # ★ 带上报价（复用 `_last_rows` 缓存；缺的最多补拉 12 个 ✓）
        pairs = [(str(row.get('symbol') or ''), str(row.get('name') or ''))
                 for row in rows]
        quoted = self._home_rows(
            pairs, full=False, allow_spark=False,
            limit=12 if self._real_account else 200)
        # 这些合约也并进首页刷新（每 2 秒更新价格 ✓）
        extra = [symbol for symbol, _ in pairs if symbol]
        self._home_extra = list(dict.fromkeys(
            [item for item in (self._home_extra or [])
             if item not in extra] + extra))[:120]
        self.push({'type': 'home_main', 'exchange': exchange,
                   'rows': quoted})

    def _on_home_preview(self, payload) -> None:
        """首页「迷你图」：返回该合约最近 80 根 K 线（改成 K 线图 ✓）"""
        symbol = str((payload or {}).get('symbol') or '')
        if not symbol:
            return
        feed = pick_feed(self.feeds, symbol) or self.current_feed()
        bars: List[dict] = []
        try:
            cycle = int((payload or {}).get('cycle') or 300)
        except (TypeError, ValueError):
            cycle = 300
        cycle = cycle if cycle > 0 else 300
        if feed is not None and feed.available():
            try:
                frame = feed.klines(symbol, cycle, 200)
                bars = _protocol.bars_from_frame(frame)
            except Exception:                                    # noqa: BLE001
                bars = []
        self.push({'type': 'home_preview', 'symbol': symbol,
                   'cycle': cycle, 'bars': bars[-200:],
                   # ★ `pending` = 数据还没到（天勤刚订阅时是占位表）→
                   #   前端会 1.5 秒后自动重试，不会永远停在迷你折线 ✓
                   'pending': not bars})

    def _on_home_refresh(self, _payload=None) -> None:
        self._home_at = 0.0
        self.push(self.home_payload(full=True))

    def _on_home_symbols(self, payload) -> None:
        symbols = (payload or {}).get('symbols') or []
        if not isinstance(symbols, (list, tuple)):
            symbols = [symbols]
        # ★ 收藏 / 各分组加入的合约 → 记住，之后每 2 秒跟着首页刷新 ✓
        self._home_extra = [str(item) for item in symbols if item][:120]
        items = [str(item).strip() for item in symbols if str(item).strip()]
        if not items:
            return
        self.push(self.home_payload(symbols=items))

    def _on_table_row_at(self, payload) -> None:
        """鼠标移动到某根 K 线 → 用**那一行**重算动态表格 ✓

        minibt 的语义：`table_rows(index=None)` 不给 index 就是最后一根；
        这里鼠标优先，鼠标离开（`index=None`）→ 回到实时 ✓
        """
        payload = payload or {}
        key = str(payload.get('key') or '')
        if not key:
            return
        raw = payload.get('index')
        index = None if raw is None else int(raw)
        try:
            from .indicator_catalog import TABLE_HOOKS, table_rows_at
            if key not in TABLE_HOOKS:
                # 诊断：静态表格不该跟随（但要看得到"命令到了 ✓"）
                self.push_log_once(f'table-at-{key}',
                                  f'表格 {key} 是静态表（不跟随鼠标）', 'info')
                return
            self.push_log_once(f'table-at-{key}',
                              f'表格 {key} 跟随鼠标：index={index}', 'info')
            rows = table_rows_at(key, index)
        except Exception:                                    # noqa: BLE001
            return
        self.push({'type': 'table_rows', 'key': key, 'rows': rows,
                   'index': index})

    def _on_ui_state(self, payload) -> None:
        """前端上报**当前可见的页面**（首页 / 报价 / 看盘…）✓

        行情类页面（首页 / 行情报价）没打开时**不拉报价**：
        实盘 `query_quotes` 一次可能卡好几秒，后台空转会把界面拖住
        （用户反馈"登录时页面卡住"）✓
        """
        payload = payload or {}
        try:
            self.ui_state = {
                'home': bool(payload.get('home')),
                'quote': bool(payload.get('quote')),
                'chart': bool(payload.get('chart')),
            }
        except Exception:                                    # noqa: BLE001
            self.ui_state = {'home': False, 'quote': False, 'chart': False}

    def _quotes_visible(self) -> bool:
        """首页 / 行情报价 是否可见（不可见就不拉报价 ✓）"""
        state = getattr(self, 'ui_state', None) or {}
        if not state:
            return True          # 没上报过 → 按旧行为（都刷）
        return bool(state.get('home') or state.get('quote'))

    # ------------------------------------------------- 报价缓存（首屏）
    QUOTE_CACHE_FILE = os.path.join(os.path.expanduser('~'), '.minibt',
                                    'quote_cache.json')

    @classmethod
    def _load_quote_cache(cls) -> Dict[str, dict]:
        """读上次的快照（坏了就当没有 ✓）"""
        try:
            with open(cls.QUOTE_CACHE_FILE, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            if isinstance(data, dict):
                return {str(k): v for k, v in data.items()
                        if isinstance(v, dict)}
        except Exception:                                        # noqa: BLE001
            pass
        return {}

    def _push_cached_quotes(self, keys) -> None:
        """先把**缓存**的报价推给前端（首屏立刻有数 ✓）"""
        rows = [self._quote_cache[str(key)] for key in keys
                if str(key) in self._quote_cache]
        if not rows:
            return
        for item in rows:
            item = dict(item)
            spark = self._spark.get(str(item.get('symbol') or ''))
            if spark:
                item['spark'] = spark
            self.push(_protocol.patch_rows_update([item]))

    def _remember_quotes(self, quotes) -> None:
        """更新缓存（最多 3000 行；由 `_save_quote_cache_step` 落盘 ✓）"""
        for item in quotes or []:
            key = str(item.get('symbol') or '')
            if key:
                self._quote_cache[key] = dict(item)
        if len(self._quote_cache) > 3000:
            for key in list(self._quote_cache)[:500]:
                self._quote_cache.pop(key, None)
        self._quote_cache_dirty = True

    def _save_quote_cache_step(self) -> None:
        """每 30 秒最多落盘一次（写完覆盖，文件很小 ✓）"""
        if not self._quote_cache_dirty:
            return
        now = time.monotonic()
        if now - float(self._quote_cache_at) < 30.0:
            return
        self._quote_cache_at = now
        self._quote_cache_dirty = False
        try:
            os.makedirs(os.path.dirname(self.QUOTE_CACHE_FILE), exist_ok=True)
            tmp = self.QUOTE_CACHE_FILE + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as fp:
                json.dump(self._quote_cache, fp, ensure_ascii=False)
            os.replace(tmp, self.QUOTE_CACHE_FILE)
        except Exception:                                        # noqa: BLE001
            pass

    def _on_visible(self, payload) -> None:
        keys = payload.get('keys') or []
        # ★ 前端切走（离开报价页 / 换交易所）时会传空列表或 hidden=True →
        #   可见集合必须清空，否则那些股票会一直占着富途订阅额度 ✗
        if (payload or {}).get('hidden'):
            keys = []
        self.visible = [str(item) for item in keys]
        if not keys:
            pool = getattr(self, '_stock_pool', None)
            if pool is not None:
                pool.set_owner('visible', [])       # 立刻退订 ✓
        if not self._rows_at:
            self.reload_rows()
        # ★ 首屏用缓存（切过去立刻有数，不等 query_quotes ✓）
        if self.visible:
            self._push_cached_quotes(self.visible)

    def _on_quote_chips(self, payload=None) -> None:
        """重新下发报价页的类型 / 交易所 chips。

        报价页关闭再打开时（尤其是右上角全局搜索进入），`flush()` 只在启动
        时发过一次 chips → 新页面会没有类型 / 交易所按钮。这里按当前
        `self.filter` 重发一份 ✓
        """
        kind = str(self.filter.get('type') or 'FUT')
        self.push(_protocol.patch_chips(
            _symbols.chips(_symbols.DEFAULT_FUTURES_TYPES), kind))
        exchanges = self._exchanges_for(kind)
        current = str(self.filter.get('exchange') or '') or (
            exchanges[0][0] if exchanges else '')
        self.filter['exchange'] = current
        self.push(_protocol.patch_chips(
            _symbols.chips(exchanges), current, exchanges=True))

    def _on_filter(self, payload) -> None:
        kind = str(payload.get('type') or self.filter.get('type') or 'FUT')
        changed_type = kind != self.filter.get('type')
        self.filter.update({'type': kind,
                            'exchange': str(payload.get('exchange') or ''),
                            'text': str(payload.get('text') or '')})
        if changed_type:
            exchanges = self._exchanges_for(kind)
            self.filter['exchange'] = exchanges[0][0] if exchanges else ''
            self.push(_protocol.patch_chips(_symbols.chips(exchanges),
                                            self.filter['exchange'],
                                            exchanges=True))
        elif not self.filter['exchange']:
            exchanges = self._exchanges_for(kind)
            self.filter['exchange'] = exchanges[0][0] if exchanges else ''
        self.reload_rows()

    # -------------------------------------------------------- 指标
    def _on_indicator_menu(self, payload) -> None:
        """工具栏「指标」→ 常用 6 个 + **完整指标库**（459 个，可搜索 ✓）"""
        from . import indicators as _ind
        symbol = str(payload.get('symbol') or '')
        items = [{'key': item['key'], 'label': item['label'],
                  'group': '常用', 'overlap': item['overlay'],
                  'params': [{'name': param['name'],
                              'label': param.get('label', param['name']),
                              'default': param['default'],
                              'type': param.get('type', 'float')}
                             for param in item.get('params', [])]}
                 for item in _ind.CATALOG]
        try:
            from . import indicator_catalog as _cat
            items.extend(_cat.catalog())
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'指标目录加载失败: {error!r}', 'warning')
        try:
            from . import personal as _pi
            items.extend(_pi.scan('indicator'))
            items.extend(_pi.scan('strategy'))       # 策略只登记展示 ✓
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'个人指标加载失败: {error!r}', 'warning')
        self.push({'type': 'indicator_menu', 'symbol': symbol,
                   'items': items})

    def _on_add_indicator(self, payload) -> None:
        from . import indicators as _ind
        # ★ 多布局：前端发的是**该格合约**（`symbolForCell(cell)`），不是 tab 名。
        #   不解析就会 `setdefault(格子合约)` 建出一个幽灵 tab → 指标落到那个
        #   空 tab 的第 1 格上，页面上什么也看不到（用户 2026-10-30 反馈 ✗）。
        #   `_on_remove_indicator` / `_on_layout_sync` 早就这么做了 ✓
        symbol = self._resolve_tab_symbol(str(payload.get('symbol') or ''))
        key = str(payload.get('key') or '')
        known = {item['key'] for item in _ind.CATALOG}
        if not symbol or not key:
            return
        if key.upper() in known:
            key = key.upper()
        elif key.startswith('pi:'):
            from . import personal as _pi
            entries = {item['key']: item for item in _pi.scan('indicator')}
            if key not in entries:
                message = (f'加指标失败：{key} 不在「我的脚本」里'
                           '（目录没收录 / 没有 BtIndicator 类或函数 / 语法错误）')
                self.push_log(message, 'error')          # 运行日志里能看到 ✓
                self.push(_protocol.patch_toast(message, 'warning'))
                return
        else:
            from . import indicator_catalog as _cat
            if _cat.entry(key) is None:
                self.push(_protocol.patch_toast(f'未知指标 {key}', 'warning'))
                return
        info = self.tabs.setdefault(symbol, {})
        cell = max(0, int(payload.get('cell') or 0))
        layout = dict(info.get('layout') or {})
        cells = [dict(item) for item in (layout.get('cells') or [])]
        # ★ 只登记了 `symbols`（前端 `layout_sync` 之前 / 老布局）→ 按 symbols
        #   补齐 `cells`：否则 `cell >= len(cells)` 会把第 2 格静音退回第 1 格 ✗
        names = [str(item or '') for item in (layout.get('symbols') or [])]
        if names and len(cells) < len(names):
            cells += [{'symbol': names[index], 'indicators': []}
                      for index in range(len(cells), len(names))]
        if cell >= len(cells):
            # 布局未建 / 非法 cell → 退回第 1 格，避免越界
            cell = 0
        # ★ 指标和策略**共存**（P66）：加指标不动策略 ✓
        if cell > 0:
            cell_record = cells[cell] if cells else {}
            selected = [item for item in (cell_record.get('indicators') or [])
                        if item.get('key') != key]
        else:
            selected = [item for item in info.get('indicators', [])
                        if item.get('key') != key]
        entry = {'key': key, 'params': _as_params(payload.get('params'))}
        if payload.get('overlay') is not None:
            entry['overlay'] = bool(payload.get('overlay'))
        selected.append(entry)
        if cell == 0:
            info['indicators'] = selected
        if cells:
            cells[cell] = dict(cells[cell] if cell < len(cells) else {},
                               indicators=list(selected))
            layout['cells'] = cells
            info['layout'] = layout

        # ★ 指标算不出来（参数非法 / 数据不够 / 脚本报错）→ **不加载上图表**：
        #   先把刚加的那一条撤回去，再弹窗 + 写日志（用户要求 ✓）
        errors: Dict[str, str] = {}
        buffered: list = []
        if cell == 0:
            payload_out = self.indicator_payload(symbol, errors=errors)
        else:
            cell_symbol = str(cells[cell].get('symbol') or symbol)
            payload_out = self._indicator_payload_for(
                cell_symbol, selected, errors=errors, defer_custom=True,
                tab_symbol=symbol, cell=cell)
            # ★ `symbol` 必须是**主 tab**（前端 `pages.get('chart:<symbol>')`
            #   按它找页面）；`cell` 指定格子 —— 和 `_push_cell_indicators` 一致 ✓
            payload_out['symbol'] = symbol
            payload_out['cell'] = cell
        buffered = [payload_out]
        if payload_out.get('dataMissing') and cell > 0:
            # ★ 这一格的行情还是占位表（刚切合约 / 开盘前）→ 先别推空补丁
            #   （推了会把原有指标线一起清掉 ✗）；数据到了节拍器会自动补推 ✓
            self.push_log(
                f'指标 {key.split(":")[0]} 已登记，等这一格的 K 线就绪后自动显示',
                'info')
            return
        reason = errors.get(key) or errors.get(str(key).upper())
        if reason:
            reverted = [item for item in selected
                        if item.get('key') != key]
            if cell == 0:
                info['indicators'] = reverted
            if cells:
                cells[cell] = dict(cells[cell], indicators=list(reverted))
                info['layout'] = layout
            message = f'指标 {key.split(":")[0]} 加不上图：{reason}'
            self.push_log(message, 'error')
            self.push(_protocol.patch_toast(
                f'指标加不上图：{key.split(":")[0]}', 'error',
                detail=str(reason)[:300]))
            # 撤掉之后再推一次（图上干净，和没点过一样 ✓）
            if cell == 0:
                self.push(self.indicator_payload(symbol))
            else:
                again = self._indicator_payload_for(
                    str(cells[cell].get('symbol') or symbol), reverted)
                again['symbol'] = symbol
                again['cell'] = cell
                self.push(again)
            return
        for item in buffered:
            self.push(item)

    def _on_remove_indicator(self, payload) -> None:
        """删指标（**支持按格** ✓）

        `cell` 缺省 = 0（第 1 格，也就是 tab 的指标列表）；`cell>0` 删该格
        自己的那份（多布局各格指标独立 ✓）；`key='*'` 清空（`cell` 缺省时
        清 **所有** 格，即工具栏「删除全部指标」✓）。
        """
        symbol = str(payload.get('symbol') or '')
        key = str(payload.get('key') or '')
        if key.upper() in ('*', 'ALL'):
            key = '*'
        # ★ 删策略（`kind='strategy'` / key = st|strategy ✓）
        if str(payload.get('kind') or '') == 'strategy' or key in (
                'st', 'strategy'):
            self._remove_strategy_of(symbol)
            return
        symbol = self._resolve_tab_symbol(symbol)
        info = self.tabs.setdefault(symbol, {})
        cell = int(payload.get('cell') or 0)
        layout = dict(info.get('layout') or {})
        cells = [dict(item) for item in (layout.get('cells') or [])]
        if key == '*':
            if payload.get('cell') is None:
                # 策略也一起删（含 runner / 所有格的策略线 ✓）
                self._remove_strategy_of(symbol)
                info = self.tabs.setdefault(symbol, {})
                layout = dict(info.get('layout') or {})
                cells = [dict(item) for item in (layout.get('cells') or [])]
                info['indicators'] = []                # 全部移除（所有格 ✓）
                for index in range(len(cells)):
                    cells[index]['indicators'] = []
            else:
                self._drop_cell_indicators(info, cells, cell, '')
        elif cell > 0:
            self._drop_cell_indicators(info, cells, cell, key)
        else:
            info['indicators'] = [item for item in info.get('indicators', [])
                                  if item.get('key') != key]
            if cells:
                cells[0] = dict(cells[0], indicators=[
                    dict(item) for item in info['indicators']])
        if cells:
            layout['cells'] = cells
            info['layout'] = layout
        self.push(self.indicator_payload(symbol))
        self._push_cell_indicators(symbol, info)
        # 某格删空了 → 前端要收到「空补丁」才会把那格的线清掉 ✓
        if key == '*' and payload.get('cell') is None:
            for index in range(1, len(cells)):
                self.push({'type': 'indicator', 'symbol': symbol,
                           'cell': index, 'items': []})
        elif payload.get('cell') is not None and int(
                payload.get('cell') or 0) > 0:
            self.push({'type': 'indicator', 'symbol': symbol, 'items': [],
                       'cell': int(payload.get('cell') or 0)})

    @staticmethod
    def _drop_cell_indicators(info: dict, cells: list, cell: int,
                              key: str) -> None:
        """删某格里的指标（`key=''` = 清空该格 ✓）"""
        if cell < 0 or cell >= len(cells):
            return
        cell_record = dict(cells[cell])
        kept = [] if not key else [
            dict(item) for item in (cell_record.get('indicators') or [])
            if str(item.get('key')) != key]
        cell_record['indicators'] = kept
        cells[cell] = cell_record
        if cell == 0:
            info['indicators'] = [dict(item) for item in kept]

    #: 同根 K 线内更新指标时只重算尾部多少根（EMA / MACD 等留足 warmup ✓）
    INDICATOR_TAIL_BARS = 1200

    @staticmethod
    def _indicator_sig(selected) -> str:
        """指标选择 / 参数签名（用于判断是否必须完整重算 ✓）"""
        return json.dumps([
            [str(item.get('key') or ''), item.get('params') or {}]
            for item in (selected or [])],
            sort_keys=True, ensure_ascii=False, default=str)

    @staticmethod
    def _frame_stamp(frame) -> int:
        """K 线最后一根的纳秒时间戳（和 `_ind_cache` 对齐 ✓）"""
        if frame is None or len(frame) == 0:
            return 0
        try:
            value = frame['datetime'].iloc[-1]
            return int(getattr(value, 'value', value))
        except Exception:                                        # noqa: BLE001
            return 0

    def indicator_payload(self, symbol: str, frame=None,
                          errors=None) -> Dict[str, Any]:
        """算当前 tab 选中的指标（常用 6 个同步；完整库走后台 ✓）

        ``errors``：出错的指标 ``{key: 信息}``（「加到图表」据此回滚 + 弹窗 ✓）
        """
        from . import indicators as _ind
        info = self.tabs.get(symbol) or {}
        # ★ 策略和指标**共存**（P66）：策略最多 1 个，指标不限 ✓
        strategy_items = list(info.get('strategy_items') or [])
        strategy_name = (info.get('strategy') or {}).get('name', '')
        selected = info.get('indicators') or []
        if not selected and not strategy_items:
            return {'type': 'indicator', 'symbol': symbol, 'items': [],
                    'strategy': '', 'strategyContracts': []}
        feed = info.get('feed') or pick_feed(self.feeds, symbol)
        if frame is None:
            frame = feed.klines(symbol, info.get('cycle') or 60,
                                self.tab_length(info)) \
                if feed is not None else None
        known = {entry['key'] for entry in _ind.CATALOG}
        builtin = [item for item in selected
                   if str(item.get('key') or '').upper() in known]
        personal = [item for item in selected
                    if str(item.get('key') or '').startswith('pi:')]
        custom = [item for item in selected
                  if str(item.get('key') or '').upper() not in known
                  and not str(item.get('key') or '').startswith('pi:')]
        # ★ `limit` 必须覆盖**全部**已加载 K 线（原来默认 600 →
        #   1000 根的图指标只画到 60% 处，看起来像“只从 1/3 开始算”✗）
        payload = _ind.compute(symbol, frame, builtin,
                               limit=max(600, len(frame) if frame is not None
                                         else 600),
                               errors=errors)
        # ★ 完整库指标（custom）是后台线程算的：同步这拍先标 `pending`，
        #   前端看到 pending 就**只加不删**（否则每秒“删了再加”副图会疯长 ✗）
        payload['pending'] = bool(custom)
        payload['items'] = list(payload.get('items') or []) \
            + self._compute_personal(frame, personal, errors)
        if custom:
            self._compute_custom(symbol, info, frame, custom, payload, errors)
        _attach_indicator_params(payload, selected)
        _apply_overlay_override(payload, selected)
        _apply_indicator_styles(payload, selected)
        if strategy_items:                     # 策略的线放最前（图例上方 ✓）
            payload['items'] = strategy_items + list(payload.get('items') or [])
        # 始终带 strategy（空字符串 = 清掉旧策略图例；不传前端会保留旧名 ✗）
        payload['strategy'] = strategy_name
        # ★ 策略需要的合约数（前端布局菜单：格数 < 这个数就禁用 ✓）
        payload['strategyContracts'] = [
            str(item) for item in (info.get('strategy_contracts') or [])
        ] if strategy_name else []
        # ★ 缓存完整结果：同一根 K 线内只更新最后一点时不用重算全历史 ✓
        if frame is not None and len(frame):
            try:
                info['_ind_cache'] = {
                    'sig': self._indicator_sig(selected),
                    'time': self._frame_stamp(frame),
                    'length': len(frame),
                    'close': float(frame['close'].iloc[-1]),
                    'items': list(payload.get('items') or []),
                }
            except Exception:                                # noqa: BLE001
                info.pop('_ind_cache', None)
        return payload

    @staticmethod
    def _compute_personal(frame, personal: list, errors=None) -> list:
        """个人指标（用户脚本）：同步算；出错填进 ``errors`` ✓"""
        from . import personal as _pi
        items = []
        for entry in personal:
            key = str(entry.get('key') or '')
            try:
                items.extend(_pi.compute(
                    frame, key, entry.get('params') or {},
                    limit=max(600, len(frame) if frame is not None else 600),
                    errors=errors))
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 个人指标 {key} 失败: {error!r}')
                if errors is not None:
                    errors[key] = f'{type(error).__name__}: {error}'
        return items

    def _indicator_tail_count(self, cache: dict, frame, info: dict):
        """新 K 线 / 重连缺口 → 需要增量更新的尾部根数。

        1 根新 K 线至少推 2 根；断线重连时按 (新时间 - 旧时间) / 周期 推算。
        超过尾部重算窗口则返回 ``None``（调用方走完整重算）。
        """
        if frame is None or len(frame) == 0:
            return None
        old_stamp = int(cache.get('time') or 0)
        new_stamp = int(self._frame_stamp(frame) or 0)
        if old_stamp <= 0 or new_stamp <= old_stamp:
            return None
        cycle = max(1, int(info.get('cycle') or 60))
        try:
            delta_seconds = (new_stamp - old_stamp) / 1_000_000_000.0
        except (TypeError, ValueError, OverflowError):
            return None
        count = max(2, int(round(delta_seconds / cycle)) + 1)
        tail_len = min(len(frame), int(self.INDICATOR_TAIL_BARS))
        return count if count <= tail_len else None

    def _refresh_indicator_last(self, symbol: str, info: dict,
                                frame, keys=None, count: int = 1) -> bool:
        """同一根 K 线内只重算尾部 + 只推最后一点（避免全历史重算/传输）✓

        返回 False 表示缓存不匹配，调用方应退回完整 ``indicator_payload``。
        """
        from . import indicators as _ind
        cache = info.get('_ind_cache') or {}
        selected = info.get('indicators') or []
        if keys is not None:
            selected = [item for item in selected
                        if str(item.get('key') or '') in keys]
        if (not cache or frame is None or len(frame) == 0
                or cache.get('sig') != self._indicator_sig(
                    info.get('indicators') or [])):
            return False
        known = {entry['key'] for entry in _ind.CATALOG}
        builtin = [item for item in selected
                   if str(item.get('key') or '').upper() in known]
        personal = [item for item in selected
                    if str(item.get('key') or '').startswith('pi:')]
        if not builtin and not personal:
            return False
        tail_len = min(len(frame), int(self.INDICATOR_TAIL_BARS))
        tail = frame.tail(tail_len)
        payload = _ind.compute(symbol, tail, builtin, limit=tail_len)
        tail_items = list(payload.get('items') or []) \
            + self._compute_personal(tail, personal)
        current = {str(item.get('key')): item
                   for item in (cache.get('items') or [])}
        updates = []
        n_tail = max(1, int(count or 1))
        for item in tail_items:
            key = str(item.get('key') or '')
            data = item.get('data') or []
            old = current.get(key)
            if not key or not data or not isinstance(old, dict):
                continue
            tail_rows = list(data[-n_tail:])
            tail_rows = [list(row) for row in tail_rows
                         if isinstance(row, (list, tuple)) and len(row) >= 2]
            if not tail_rows:
                continue
            rows = old.get('data')
            if not isinstance(rows, list):
                continue
            for row in tail_rows:
                if rows and rows[-1] and rows[-1][0] == row[0]:
                    rows[-1] = row
                elif not rows or row[0] > rows[-1][0]:
                    rows.append(row)
                else:
                    # 时间倒退 / 重复补洞：找到同时间戳覆盖，否则忽略
                    for index in range(len(rows) - 1, -1, -1):
                        if rows[index] and rows[index][0] == row[0]:
                            rows[index] = row
                            break
            updates.append({'key': key, 'kind': item.get('kind'),
                            'data': tail_rows,
                            'color': item.get('color'),
                            'base': item.get('base'),
                            'upColor': item.get('upColor'),
                            'downColor': item.get('downColor')})
        if not updates:
            return False
        try:
            cache['close'] = float(frame['close'].iloc[-1])
            cache['time'] = self._frame_stamp(frame)
            # 新 K 线是增量的，但 frame 长度已经变了；不同步会让下一拍
            # 误判为「缓存不匹配」→ 每拍都全量重算。
            cache['length'] = len(frame)
        except Exception:                                    # noqa: BLE001
            pass
        self.push({'type': 'indicator', 'symbol': symbol,
                   'mode': 'last', 'items': updates,
                   'strategy': (info.get('strategy') or {}).get('name', '')})
        return True

    def _compute_custom(self, symbol: str, info: dict, frame, custom: list,
                        payload: Dict[str, Any], errors=None) -> None:
        """完整指标库：后台线程算，算完再推一次（带 generation 防过期 ✓）

        算失败（如 TradingView 指标需要 KLine / 参数非法）→ 把该指标从
        图表上撤掉 + 弹窗提醒（用户要求：**指标不留在图上** ✓）
        """
        from . import indicator_catalog as _cat

        keys = [str(item.get('key')) for item in custom]
        params = {str(item.get('key')): (item.get('params') or {})
                  for item in custom}
        if frame is None or len(frame) == 0:
            return
        # 过期判断用**签名**（选了哪些指标 / 参数），不用自增代数 ——
        # 否则「同一根 K 线每秒重算」会把还在算的结果全丢掉
        signature = json.dumps([keys, params], sort_keys=True,
                               ensure_ascii=False, default=str)
        generation = int(info.get('_ind_gen') or 0) + 1
        info['_ind_gen'] = generation
        info['_ind_sig'] = signature
        snapshot = frame.copy()

        failed: Dict[str, str] = {}

        def work():
            try:
                items = _cat.compute(
                    snapshot, keys, params,
                    limit=max(600, len(snapshot)),
                    errors=failed)
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 完整指标计算失败: {error!r}')
                for key in keys:
                    failed.setdefault(str(key), repr(error))
                items = []
            if info.get('_ind_sig') != signature:
                return                    # 期间又改了指标 → 丢掉这批 ✓
            if failed:
                self._drop_failed_indicators(symbol, info, failed)
            if errors is not None:
                errors.update(failed)
            merged = dict(payload)
            async_items = {'items': items}
            _attach_indicator_params(async_items, custom)
            # ★ 策略可能在算的过程中才加上（P66）：这里**重新读一次**，
            #   否则这份旧快照会把策略的线和策略名一起冲掉 ✗
            latest = self.tabs.get(symbol) or {}
            strategy_items = list(latest.get('strategy_items') or [])
            strategy_name = (latest.get('strategy') or {}).get('name', '')
            merged['items'] = strategy_items + list(
                payload.get('items') or []) + list(async_items['items'] or [])
            if strategy_name:
                merged['strategy'] = strategy_name
            else:
                merged.pop('strategy', None)
            self.push(merged)

        threading.Thread(target=work, daemon=True,
                         name=f'desk-ind-{symbol}').start()

    def _drop_failed_indicators(self, symbol: str, info: dict,
                                failed: Dict[str, str]) -> None:
        """算失败的指标**不留在图上**：撤掉 + 弹窗（同一指标只提醒一次 ✓）

        `errors` 的 key 可能是目录 key（`tv:ADX_and_DI`）或线条 key
        （`pta_adx:adxx`）→ 按前缀匹配，确保 line key 也能撤掉 ✓
        """
        keys = {str(key) for key in failed}
        if not keys:
            return

        def bad(item) -> bool:
            key = str(item.get('key') or '')
            return any(key == one or key.startswith(one + ':')
                       for one in keys)

        dropped = [item for item in (info.get('indicators') or []) if bad(item)]
        info['indicators'] = [item for item in (info.get('indicators') or [])
                              if not bad(item)]
        cells = (info.get('layout') or {}).get('cells') or []
        for cell in cells:
            if isinstance(cell, dict) and cell.get('indicators'):
                cell['indicators'] = [item for item in cell['indicators']
                                      if not bad(item)]
        if not dropped:
            return
        for key, message in failed.items():
            short = str(key).split(':')[0]
            if self.push_log_once(f'ind-fail-{symbol}-{key}',
                                  f'指标 {short} 算不出来，已从图表移除：'
                                  f'{message}', 'error'):
                self.push(_protocol.patch_toast(
                    f'指标加不上图：{short}', 'error',
                    detail=str(message)[:300]))
            print(f'[desk] 指标 {short} 算不出来：{message}')

    def _on_replay_exit(self, payload) -> None:
        """退出回放 → 重新拉一次实时数据（K 线 / 指标 / 报价 / 持仓）✓"""
        symbol = str(payload.get('symbol') or '') or next(iter(self.tabs), '')
        if not symbol:
            return
        info = dict(self.tabs.get(symbol) or {})
        info.pop('_ind_bar', None)
        info.pop('_ind_at', None)
        self.tabs[symbol] = info
        feed = info.get('feed') or pick_feed(self.feeds, symbol)
        cycle = int(info.get('cycle') or 60)
        frame = feed.klines(symbol, cycle, self.tab_length(info))
        bars = _protocol.bars_from_frame(frame)
        self._reset_kline_state(info)
        self._note_kline_state(
            info, bars, len(frame) if frame is not None else 0)
        self.push(_protocol.patch_kline(symbol, bars, True))
        self.push(self.indicator_payload(symbol))
        self.push(self.book_payload(symbol, feed))
        self.push(self.position_payload(symbol, feed))
        self.replay_symbols.discard(symbol)
        # ★ 回放用的本地模拟持仓线要收起来（实时持仓线上面已经推了 ✓）
        self.push({'type': 'position', 'symbol': symbol})
        self._push_sim_position(symbol, local=True)
        self.push(self.account_payload(symbol=next(iter(self.tabs), '')))
        self.push(self.trading_state(symbol))
        self.push_log('已退出回放，回到实时', 'info')

    # -------------------------------------------------------- 本地图表
    def local_store(self):
        if self._local_store is None:
            from .local_data import LocalStore
            self._local_store = LocalStore()
        return self._local_store

    def is_replaying(self, symbol: str = '') -> bool:
        """这个合约是不是正在回放（交易要切本地模拟 ✓）"""
        if not self.replay_symbols:
            return False
        return (not symbol) or symbol in self.replay_symbols

    def replay_sim(self, symbol: str = ''):
        """回放用的本地模拟账户（优先回放合约的价格 ✓）"""
        sim = self.local_sim()
        price = None
        try:
            row = self._last_rows.get(symbol) or {}
            price = row.get('last')
        except Exception:                                        # noqa: BLE001
            price = None
        # ★ 只在「还不知道价格」时铺一次：否则会把刚开仓的价格冲掉 ✗
        if price and sim._price(symbol) <= 0:
            sim.set_price(symbol, price, self.decimals_of(symbol))
        return sim

    def replay_account_payload(self, symbol: str = '') -> Dict[str, Any]:
        """把本地模拟账户转成 `AccountDock` 的账目补丁（回放时用 ✓）"""
        sim = self.replay_sim(symbol)
        payload = sim.payload(symbol)
        values = payload.get('values') or {}
        sim_values = {
            'pre_balance': values.get('initial_cash'),
            'balance': values.get('balance'),
            'position_profit': values.get('float_profit'),
            'close_profit': values.get('realized_pnl'),
            'float_profit': values.get('float_profit'),
            'commission': values.get('commission'),
            'margin': values.get('margin', values.get('market_value')),
            'frozen_margin': 0.0,
            'frozen_commission': 0.0,
            'available': values.get('available'),
            'risk_ratio': values.get('risk_ratio', 0.0),
        }
        fields = [{'key': key, 'title': title, 'percent': percent}
                  for key, title, percent in (
                      ('pre_balance', '静态权益', False),
                      ('balance', '账户权益', False),
                      ('position_profit', '持仓盈亏', False),
                      ('close_profit', '平仓盈亏', False),
                      ('float_profit', '浮动盈亏', False),
                      ('commission', '手续费', False),
                      ('margin', '占用保证金', False),
                      ('frozen_margin', '冻结保证金', False),
                      ('frozen_commission', '冻结手续费', False),
                      ('available', '可用资金', False),
                      ('risk_ratio', '资金使用率', True))]
        tables = dict(payload.get('tables') or {})
        # 本地账户没有「未成委托」（即时成交）→ 给个空表 ✓
        unfilled = dict(tables.get('unfilled') or {})
        unfilled.setdefault('columns', (tables.get('orders') or {})
                            .get('columns') or [])
        unfilled.setdefault('rows', [])
        tables['unfilled'] = unfilled
        return {'type': 'account', 'kind': 'replay', 'index': 0,
                'labels': ['本地模拟（回放）'], 'fields': fields,
                'values': sim_values, 'tables': tables}

    def local_sim(self):
        if self._local_sim is None:
            from .local_data import LocalSim, default_sim_db
            self._local_sim = LocalSim(
                db_path=default_sim_db(), **self._sim_settings())
        return self._local_sim

    def _sim_settings(self) -> Dict[str, Any]:
        """「设置 → 模拟账户」里的初始现金 / 手续费（落盘在 prefs ✓）"""
        from . import user_prefs as _prefs
        values = _prefs.settings()

        def number(key: str, fallback: float) -> float:
            try:
                return float(values.get(key, fallback))
            except (TypeError, ValueError):
                return fallback

        mode = str(values.get('sim_fee_mode') or 'fixed')
        if mode not in ('fixed', 'percent'):
            mode = 'fixed'
        cash = number('sim_initial_cash', 100000.0)
        return {'initial_cash': cash if cash > 0 else 100000.0,
                'fee_mode': mode,
                'fee_value': max(0.0, number('sim_fee_value', 0.0))}

    def _push_sim_analysis(self) -> None:
        """设置页「模拟账户」的曲线 / 统计（每次成交后刷新 ✓）"""
        try:
            self.push(self.local_sim().analysis())
        except Exception:                                        # noqa: BLE001
            pass

    def _local_list_payload(self) -> Dict[str, Any]:
        store = self.local_store()
        return {'type': 'local_data', 'items': store.items(),
                'folders': list(store.folders)}

    def _on_local_list(self, payload=None) -> None:
        self.push(self._local_list_payload())

    def choose_directory(self, title: str = '选择文件夹',
                         start: str = '') -> str:
        """**统一的系统文件夹选择框**（所有「选择目录」都走这里 ✓）

        ① Qt 桌面壳：`pick_directory` 由 `DeskWindow` 注入（原生框）；
        ② 浏览器壳 / VS Code 扩展：`tkinter` 弹本机原生框（不用手输路径 ✓）；
        ③ 都不行（无 GUI / 无 tkinter）：返回空串 → 前端只提示，不再要路径 ✓
        """
        picker = getattr(self, 'pick_directory', None)
        if callable(picker):
            # ★ 有系统框就用它；**用户取消 → 直接返回**（别再弹第二个框 ✗）
            try:
                return str(picker(title) or '')
            except Exception as error:                           # noqa: BLE001
                self.push_log(f'选择目录失败：{error!r}', 'warning')
                return ''
        return _tk_choose_directory(title, start)

    def _on_local_add_folder(self, payload) -> None:
        path = str((payload or {}).get('path') or '').strip()
        if not path:
            path = self.choose_directory('选择 K 线 CSV 文件夹')
        if not path:
            self.push_log('未选择数据文件夹（没有系统对话框时可改用桌面版）',
                          'info')
            return
        try:
            self.local_store().add_folder(path)
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'添加文件夹失败：{error}'
                                            , 'error'))
            return
        self.push(self._local_list_payload())
        self.push(_protocol.patch_toast(f'已添加数据文件夹：{path}', 'success'))
        self.push_log(f'本地图表：添加数据文件夹 {path}', 'info')

    def _on_local_remove_folder(self, payload) -> None:
        path = str((payload or {}).get('path') or '')
        self.local_store().remove_folder(path)
        self.push(self._local_list_payload())

    @staticmethod
    def _base_indicator_entries(entries: list) -> list:
        """布局里存的是**线条 key**（`pta_sma:sma` / `tv:X:trend`），
        计算指标时要用目录/基础 key；同名指标的多条线合并成一份参数。

        例：`pta_adx:adxx / pta_adx:adxr ...` → 一条 `pta_adx`。
        样式仍由原始线条 entry 单独应用，不丢颜色 / 显隐 ✓。
        """
        out = []
        seen = {}
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get('key') or '')
            if not key:
                continue
            if key.startswith('editor:') or key.startswith('st:'):
                continue
            if key.startswith('tv:'):
                base = ':'.join(key.split(':')[:2])
            elif key.startswith('pi:'):
                # `pi:cat/name` 本身只有一个冒号，不能误剥成 `pi` ✓
                base = (key.rsplit(':', 1)[0]
                        if key.count(':') >= 2 else key)
            else:
                base = key.split(':', 1)[0]
            if base in seen:
                continue
            record = dict(entry)
            record['key'] = base
            seen[base] = record
            out.append(record)
        return out

    def _local_state_key(self, name: str = '', page: str = '') -> str:
        """本地图表的「文档 key」：有页签 id 就用它，否则退回数据名 ✓

        ★ 多开本地图表：两个页面加载**同一份 CSV** 时，指标 / 策略必须各存
        各的（以前都按 CSV 名存 → 一个页面加指标，另一个也跟着出现 ✗）
        """
        page = str(page or '')
        if page:
            return page
        return self._local_page_of(name) or str(name or '')

    def _local_items(self, name: str, cell: int = 0,
                     page: str = '') -> list:
        """某一页某一格现在的指标（**只读副本** ✓）"""
        key = self._local_state_key(name, page)
        cells = (getattr(self, '_local_indicators', {}) or {}).get(key) or {}
        return [dict(item) for item in (cells.get(max(0, int(cell))) or [])]

    def _local_set_items(self, name: str, cell: int, items: list,
                         page: str = '') -> None:
        """写某一页某一格的指标 ✓"""
        key = self._local_state_key(name, page)
        store = getattr(self, '_local_indicators', None)
        if store is None:
            store = self._local_indicators = {}
        cells = store.setdefault(key, {})
        cells[max(0, int(cell))] = [dict(item) for item in (items or [])
                                   if isinstance(item, dict)]

    def _local_indicator_payload(self, name: str, cell: int = 0,
                                 errors=None, page: str = '') -> Dict[str, Any]:
        """按本地 CSV 重算指标（常用 6 个 + 完整库 + 个人 ✓）"""
        from . import indicators as _ind
        from . import indicator_catalog as _cat
        store = self.local_store()
        cell = max(0, int(cell or 0))
        raw_selected = self._local_items(name, cell, page)
        # 布局保存的是线条 key；先还原为目录 key 再计算，避免 `entry()` 找不到
        selected = self._base_indicator_entries(raw_selected)
        payload: Dict[str, Any] = {'type': 'local_indicator', 'symbol': name,
                                   'cell': cell, 'items': []}
        # ★ 这份 CSV 只在一个本地图表页上 → 补丁带 `page`，前端就不会画到
        #   别的页面上（策略线 / 回放这种异步补丁也准 ✓）
        page_id = self._local_page_of(name)
        if page_id:
            payload['page'] = page_id
        strategies = getattr(self, '_local_strategies', {}) or {}
        strategy = strategies.get(self._local_state_key(name, page))
        if strategy is None:
            # 兼容老记录（按 CSV 名存的）：只有没绑定页面时才用 ✓
            legacy = strategies.get(str(name or ''))
            if isinstance(legacy, dict) and not legacy.get('page'):
                strategy = legacy
        if strategy is None:
            # ★ 同一个策略可能同时画在多个合约格（配对交易）→ 记录存在**主
            #   合约**的 key 上；这里按「哪条记录的 groups 里有这个 CSV」找 ✓
            #   ⚠ 但**不能跨页**：别的页面的策略记录不算（多开时要独立 ✗）
            current_page = str(page or '')
            for candidate in strategies.values():
                candidate = candidate or {}
                owner = str(candidate.get('page') or '')
                if owner and current_page and owner != current_page:
                    continue
                if name in (candidate.get('groups') or {}):
                    strategy = candidate
                    break
        if strategy:
            # 菜单显示**策略类名**（`editor.CMOStrategy` ✓）；
            # 「加到图表」时**策略优先**：文件里同时有 Strategy 和 BtIndicator
            # 就走策略路径（`_on_editor_add_indicator` 里的 strategies 分支 ✓）
            label = str(strategy.get('name') or 'strategy')
            payload['strategy'] = {'name': label}
            payload['strategyContracts'] = [
                str(item) for item in (strategy.get('contracts') or [])]
            # ★ 给每条线打上 `source = 'editor:<类名>'`：
            #   删除菜单据此把**同一指标的所有线**归到一条 `editor.CMO` 上
            #   （以前没有 source，前端只能按 key 前缀猜，菜单里就成了 5 条 ✗）
            groups = strategy.get('groups') or {}
            if groups:
                lines = groups.get(name) or []
            else:
                lines = strategy.get('items') or []
            # ★ 策略合约数 < 格数时，多出来的格子**不画策略线**（用户要求 ✓）
            contracts = [str(item) for item in
                         (strategy.get('contracts') or [])]
            if contracts and cell >= len(contracts):
                lines = []
            payload['items'] = [
                {**item, 'source': f'editor:{label}'}
                for item in lines]
            strategy_lines = list(payload['items'])
        else:
            # 没策略也要**显式清掉**（前端页签标签 / 菜单据此复位 ✓）
            strategy_lines = []
            payload['strategy'] = ''
            payload['strategyContracts'] = []
        # ★ 只读叠加（可以多个；只算线、不交易 ✓）
        overlay_lines: list = []
        overlays = (getattr(self, '_local_overlays', {}) or {}).get(
            self._local_state_key(name, page)) or []
        for record in overlays:
            groups = record.get('groups') or {}
            if groups:
                lines = groups.get(name) or []
            elif str(record.get('symbol') or '') == str(name):
                lines = record.get('items') or []
            else:
                lines = []
            overlay_lines += [
                {**item, 'source': f"editor:{record.get('name')}"}
                for item in lines]
        payload['overlays'] = [
            {'name': str(item.get('name') or ''),
             'key': str(item.get('key') or item.get('name') or '')}
            for item in overlays]
        # ★ 没有普通指标时也要带上策略线 / 只读叠加（否则「只读叠加」看不到 ✗）
        payload['items'] = list(strategy_lines) + list(overlay_lines)
        if not selected and not (getattr(self, '_local_plot_items', {})
                                or {}).get((name, cell)):
            return payload
        # ★ 数据还没加载（或 CSV 被删）→ 只推策略线 / 外部线，别抛异常
        #   （以前这里 `store.frame()` 一抛整包补丁就没了 → 图上什么都没有 ✗）
        try:
            frame = store.frame(name)
        except Exception:                                    # noqa: BLE001
            frame = None
        if frame is None or len(frame) == 0:
            return payload
        known = {entry['key'] for entry in _ind.CATALOG}
        builtin = [item for item in selected
                   if str(item.get('key') or '').upper() in known]
        personal = [item for item in selected
                    if str(item.get('key') or '').startswith('pi:')]
        custom = [item for item in selected
                  if str(item.get('key') or '').upper() not in known
                  and not str(item.get('key') or '').startswith('pi:')]
        try:
            base = _ind.compute(name, frame, builtin,
                                limit=max(1, len(frame)), errors=errors)
            items = list(base.get('items') or [])
        except Exception as error:                               # noqa: BLE001
            items = []
            self.push_log(f'本图指标计算失败：{error!r}', 'error')
        items += self._compute_personal(frame, personal, errors)
        # ★ 只用**这一格**的策略线（以前这里又把整条策略的全部线加一遍 →
        #   l2609_60 的均线跑到 pp2609_60 图上，重复出现 ✗）
        if overlay_lines:
            items = list(overlay_lines) + items
        if strategy_lines:
            items = list(strategy_lines) + items
        # ★ 外部脚本（btplot / Gui.Desk）给的**算好的**指标线 ✓
        plot_items = (getattr(self, '_local_plot_items', {}) or {}).get(
            (name, cell)) or []
        if plot_items:
            items = list(plot_items) + items
        if custom:
            keys = [str(item.get('key')) for item in custom]
            params = {str(item.get('key')): (item.get('params') or {})
                      for item in custom}
            try:
                extra = _cat.compute(frame, keys, params,
                                    limit=max(1, len(frame)), errors=errors)
                _attach_indicator_params({'items': extra}, custom)
                items += extra
            except Exception as error:                           # noqa: BLE001
                self.push_log(f'本图完整库指标计算失败：{error!r}', 'error')
        payload['items'] = items
        _attach_indicator_params(payload, selected)
        _apply_overlay_override(payload, raw_selected + selected)
        _apply_indicator_styles(payload, raw_selected + selected)
        return payload

    def _on_local_add_overlay(self, payload=None) -> None:
        """把策略以**只读叠加**的方式加进来（同一个页面可以叠多个 ✓）

        只跑一次 `__init__`（画线），**不跑 `next()`、不建 runner、不碰账户** ——
        适合「主策略 + 几个参考策略」/ A/B 对比。
        """
        from . import personal as _pi
        from . import strategy_overlay as _overlay
        payload = payload or {}
        path = str(payload.get('path') or '')
        name = str(payload.get('symbol') or '')
        cell = max(0, int(payload.get('cell') or 0))
        page = (str(payload.get('page') or '')
                or str(getattr(self, '_active_local_page', '') or ''))
        if not path or not os.path.isfile(path):
            self.push(_protocol.patch_toast('文件不存在', 'warning'))
            return
        if not name:
            self.push(_protocol.patch_toast('先选择本地数据再加只读叠加',
                                            'warning'))
            return
        module = _pi._import_file(path)
        classes = (_overlay.classes_of(module).get('strategy') or []
                   if module is not None else [])
        if not classes:
            message = ('这个文件里没有 Strategy 类（只读叠加只认策略）'
                       ' —— 普通指标请用「加到图表」')
            self.push_log(message, 'warning')
            self.push(_protocol.patch_toast(message, 'warning'))
            return
        cls = _pick_strategy_class(classes,
                                   str(payload.get('strategy') or ''))
        frames = self._local_frames_for_strategy(name, cell)
        frame = frames[0][1] if frames else None
        if frame is None or len(frame) == 0:
            self.push(_protocol.patch_toast(f'{name} 还没加载，先打开一次图表',
                                            'warning'))
            return
        try:
            result = _overlay.run_overlay(frame, cls, name, 60,
                                          replay=False,
                                          frames=frames or None)
        except Exception as error:                               # noqa: BLE001
            result = {'ok': False, 'error': repr(error)}
        if not result.get('ok'):
            message = f'只读叠加 {cls.__name__} 失败：{result.get("error")}'
            self.push_log(message, 'error')
            self.push(_protocol.patch_toast(message, 'warning'))
            return
        class_name = str(cls.__name__)
        abs_path = os.path.abspath(path)
        record = {
            # `name` 只用于显示；**身份**用下面的 `key` = 绝对路径 + 类名 ✓
            'name': str(result.get('name') or class_name),
            'class': class_name,
            'key': f'{abs_path}|{class_name}',
            'path': path,
            'items': list(result.get('items') or []),
            'groups': dict(result.get('groups') or {}),
            'symbol': name,
            'page': page,
        }
        overlays = getattr(self, '_local_overlays', None)
        if overlays is None:
            overlays = self._local_overlays = {}
        before = list(overlays.get(page) or [])

        def _same(item: dict) -> bool:
            """是不是**同一个策略**：`(绝对路径, 类名)` 都相同 ✓

            * 同一个文件 + 同一个类 → 重新加载（替换）；
            * 同一个文件里的不同类 / 不同文件里的同名类 → 各自独立 ✓
            （老记录没有 `key` → 按路径 + 类名 / 名字兜底。）
            """
            stored = str((item or {}).get('key') or '')
            if stored:
                return stored == record['key']
            item_path = str((item or {}).get('path') or '')
            item_name = str((item or {}).get('class')
                            or (item or {}).get('name') or '')
            return (item_name == class_name
                    and bool(item_path)
                    and os.path.abspath(item_path) == abs_path)

        reloaded = any(_same(item) for item in before)
        store = [item for item in before if not _same(item)]
        store.append(record)
        overlays[page] = store
        # 每一格都重推（指标 + 策略线 + 只读叠加 ✓）
        cells = dict(getattr(self, '_local_cell_names', {}) or {})
        for index, csv_name in sorted(cells.items()):
            self.push(self._local_indicator_payload(str(csv_name), int(index),
                                                    page=page))
        if not cells:
            self.push(self._local_indicator_payload(name, cell, page=page))
        verb = '已重新加载只读叠加' if reloaded else '已加只读叠加'
        self.push_log(
            f'{verb}：{record["name"]}（{len(record["items"])} 条线，'
            '只算不交易）', 'success')
        self.push(_protocol.patch_toast(
            ('只读叠加已重新加载：' if reloaded else '只读叠加：')
            + str(record['name']), 'success'))

    def _remove_local_overlay(self, name: str = '', page: str = '') -> bool:
        """删只读叠加（`name` 空 = 清掉这一页的全部 ✓）"""
        store_all = getattr(self, '_local_overlays', {}) or {}
        targets = [str(page)] if page else list(store_all)
        removed = False
        for key in targets:
            records = list(store_all.get(key) or [])
            kept = [item for item in records
                    if name and not (
                        str(item.get('key') or '') == name
                        or (not item.get('key')
                            and str(item.get('name') or '') == name))]
            if len(kept) != len(records):
                removed = True
            if kept:
                store_all[key] = kept
            else:
                store_all.pop(key, None)
        if not removed:
            return False
        cells = dict(getattr(self, '_local_cell_names', {}) or {})
        for index, csv_name in sorted(cells.items()):
            self.push(self._local_indicator_payload(str(csv_name), int(index),
                                                    page=page))
        return True

    def _local_page_of(self, name: str) -> str:
        """这份 CSV 只在一个本地图表页上 → 返回页签 id（多开时返回 '' ✓）"""
        name = str(name or '')
        if not name:
            return ''
        pages = getattr(self, '_local_pages', {}) or {}
        hits = [key for key, cells in pages.items()
                if name in (cells or {}).values()]
        return str(hits[0]) if len(hits) == 1 else ''

    def _on_local_cells(self, payload=None) -> None:
        """前端切到某个本地图表页 → 报一次「第几格 → 哪个 CSV」✓

        后端只有一份 `_local_cell_names`（活动页）。多开本地图表后，切页
        必须同步：否则策略线 / 回放补丁会按**上一页**的格号推 ✗

        `payload = {page, cells: ['pta', 'ma']}`（cells 下标 = 格号 ✓）
        """
        payload = payload or {}
        page = str(payload.get('page') or '')
        cells = payload.get('cells') or []
        mapping: Dict[int, str] = {}
        if isinstance(cells, dict):
            for key, value in cells.items():
                if value:
                    mapping[int(key)] = str(value)
        else:
            for index, value in enumerate(cells):
                if value:
                    mapping[index] = str(value)
        self._local_cell_names = mapping
        pages = getattr(self, '_local_pages', None)
        if pages is None:
            pages = self._local_pages = {}
        if payload.get('closed'):
            pages.pop(page, None)
            if getattr(self, '_active_local_page', '') == page:
                self._active_local_page = ''
            # ★ 这一页关了 → 它的策略 / 指标记录一起清（不然策略管理里会
            #   留下删不掉的「幽灵」行 ✗）
            if page:
                getattr(self, '_local_overlays', {}).pop(page, None)
                self._local_indicators.pop(page, None)
                record = (getattr(self, '_local_strategies', {}) or {}).pop(
                    page, None) or {}
                getattr(self, '_local_strategy_of', {}).pop(page, None)
                label = str((record or {}).get('name') or '')
                if label and not any(
                        str((item or {}).get('name') or '') == label
                        for item in (self._local_strategies or {}).values()):
                    getattr(self, '_local_runners', {}).pop(label, None)
            return
        if page:
            pages[page] = dict(mapping)
            self._active_local_page = page
            # ★ 切页 / 换布局后前端把每格都重建了 → 指标 + 策略线按新的
            #   「第几格 → 哪个 CSV」重推一次（以前换布局后线全没了 ✗）
            for index, name in sorted(mapping.items()):
                self.push(self._local_indicator_payload(
                    str(name), int(index), page=page))

    def _on_local_load(self, payload) -> None:
        name = str((payload or {}).get('name') or '')
        if not name:
            return
        try:
            info = self.local_store().info(name)
            bars = self.local_store().bars(name)
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'加载本地数据失败：{error}',
                                            'error'))
            return
        if not bars:
            self.push(_protocol.patch_toast(f'{name} 没有可用的 K 线',
                                            'warning'))
            return
        last = bars[-1]
        decimals = 2
        price_tick = 0.0
        volume_multiple = 1.0
        try:
            frame = self.local_store().frame(name)
            # ★ CSV 里带 `price_tick` 就用它（转 KLine 时一般会自动带，
            #   股票默认 0.01 ✓）；没有则按小数位推 ✓
            price_tick = float(frame['price_tick'].iloc[0])
            decimals = _decimals_from_tick(price_tick)
            try:
                volume_multiple = float(frame['volume_multiple'].iloc[0])
            except Exception:                                    # noqa: BLE001
                volume_multiple = 1.0
        except Exception:                                        # noqa: BLE001
            price_tick = 0.0
        if price_tick <= 0:
            price_tick = 10 ** -max(0, int(decimals))
        # ★ 期货本地模拟账户必须乘合约乘数；否则 pp/l 的盈亏会少 5 倍 ✗
        self.local_sim().set_contract(name, volume_multiple, decimals,
                                      price_tick=price_tick, source='desk')
        try:
            cache = getattr(self, '_decimals_cache', None)
            if cache is None:
                cache = self._decimals_cache = {}
            cache[name] = int(decimals)
        except Exception:                                        # noqa: BLE001
            pass
        self.local_sim().set_price(name, float(last.get('close') or 0),
                                   decimals)
        self._push_sim_position(name, local=True)   # 本地图表持仓线 ✓
        cell = int((payload or {}).get('cell') or 0)
        # ★ 发起加载的**本地图表页**（多开时按 CSV 名找不到它：这页还没加载过
        #   这份数据 ✗）→ 补丁带上 `page`，前端按页签路由 ✓
        # ★ 没带 `page` 的加载（自动布局 / 策略）→ 发给**当前活动**的本地页
        #   （`local_cells` 记下来的）✓
        page = str((payload or {}).get('page')
                   or getattr(self, '_active_local_page', '') or '')
        # ★ 记住「第几格 → 哪个 CSV」，策略多合约时要把指标落到对的格 ✓
        if not hasattr(self, '_local_cell_names'):
            self._local_cell_names = {}
        self._local_cell_names[cell] = name
        if page:
            pages = getattr(self, '_local_pages', None)
            if pages is None:
                pages = self._local_pages = {}
            pages.setdefault(page, {})[cell] = name
        patch = {'type': 'local_kline', 'name': name,
                 'symbol': info.get('symbol') or name,
                 'duration': int(info.get('duration') or 60),
                 'decimals': decimals,
                 'price_tick': price_tick,
                 'bars': bars,
                 'cell': cell}
        if page:
            patch['page'] = page
        self.push(patch)
        # ★ 加载数据 = **只要 K 线**（用户 2026-10-30 要求）：
        #   重新打开本地数据时不要再把上次加过的指标带出来 ✗
        #   指标 / 策略要单独「加到图表」或用指标模板 ✓
        self._local_set_items(name, cell, [], page)
        payload_out = self._local_indicator_payload(name, cell, page=page)
        if page:
            payload_out['page'] = page
        self.push(payload_out)
        self.push(self.local_sim().payload(name))
        self.push_log(f'本地图表：{name}（{len(bars)} 根）', 'info')

    def _on_local_add_indicator(self, payload) -> None:
        name = str((payload or {}).get('symbol') or '')
        key = str((payload or {}).get('key') or '')
        if not name or not key:
            return
        cell = max(0, int((payload or {}).get('cell') or 0))
        page = str((payload or {}).get('page') or '')
        # ★ 按「页 + 格」读写：多布局里格 1 / 格 2 是两份独立指标；
        #   多开本地图表时，两份副本加载同一份 CSV 也各存各的 ✓
        #   （以前按 CSV 名存 → 页面之间会串 ✗）
        # 旧布局存的是 `pta_adx:adxx` 线条 key；添加时统一成基础 key，
        # 避免同一指标出现“线条 key + 基础 key”两份。
        selected = [item for item in self._base_indicator_entries(
            self._local_items(name, cell, page))
            if str(item.get('key')) != key]
        entry = {'key': key, 'params': _as_params((payload or {}).get('params'))}
        if (payload or {}).get('overlay') is not None:
            entry['overlay'] = bool(payload.get('overlay'))
        selected.append(entry)
        self._local_set_items(name, cell, selected, page)

        # ★ 算不出来（脚本报错 / 数据不够 / 参数非法）→ **不加载上图表**：
        #   撤掉刚加的那条 + 弹窗提醒（用户要求 ✓）
        errors: Dict[str, str] = {}
        payload_out = self._local_indicator_payload(name, cell, errors=errors,
                                                    page=page)
        reason = errors.get(key) or errors.get(str(key).upper())
        if reason:
            reverted = [item for item in selected
                        if str(item.get('key')) != key]
            self._local_set_items(name, cell, reverted, page)
            self.push_log(f'指标 {key.split(":")[0]} 加不上图：{reason}', 'error')
            self.push(_protocol.patch_toast(
                f'指标加不上图：{key.split(":")[0]}', 'error',
                detail=str(reason)[:300]))
            self.push(self._local_indicator_payload(name, cell, page=page))
            return
        self.push(payload_out)

    def _on_local_remove_indicator(self, payload) -> None:
        name = str((payload or {}).get('symbol') or '')
        key = str((payload or {}).get('key') or '')
        if not name:
            return
        # ★ 「🗑」菜单里那条「策略 · xxx（删除）」= 只删策略（指标保留 ✓）
        #   等效于「策略管理」里的删除按钮
        if str((payload or {}).get('kind') or '') == 'overlay':
            # 「只读叠加」：按名字删（`key` = 叠加名 ✓）
            self._remove_local_overlay(
                str((payload or {}).get('key') or ''),
                str((payload or {}).get('page') or ''))
            return
        if str((payload or {}).get('kind') or '') == 'strategy':
            # ★ 记录是按**页签 id** 存的 → 先按 page 找（其次才是 CSV 名）✓
            target = str((payload or {}).get('page') or '') or name
            if self._remove_local_strategy(target):
                self.push_log(f'已删除本地图表策略：{target}', 'info')
            self.push(self._local_indicator_payload(
                name, int((payload or {}).get('cell') or 0),
                page=str((payload or {}).get('page') or '')))
            return
        # ★ 「加到图表」的策略线（`_local_strategies`）也要能删：
        #   以前只从 `local_store` 里删指标 → payload 又把策略线加回来，
        #   删完立刻"复活"（用户实测 ✗）
        # ★ 「删除全部指标」（工具栏）默认**不动策略**；
        #   右键「删除指标策略」才连策略一起删（前端传 `strategy: true`）✓
        all_strategy = bool((payload or {}).get('strategy'))
        state_key = self._local_state_key(
            name, str((payload or {}).get('page') or ''))
        strategy = (getattr(self, '_local_strategies', {}) or {}).get(state_key)
        if strategy and key.upper() in ('*', 'ALL') and not all_strategy:
            strategy = None
        # ★ 菜单给的是**策略级** key（`editor:CMOStrategy`），而每条线的 key 是
        #   `editor:cmo:line:0` → 直接比对策略名，命中就整条删掉 ✓
        drop_strategy = False
        if strategy and key.startswith('editor:'):
            name_only = key.split(':', 1)[1]
            if name_only and name_only == str(strategy.get('name') or ''):
                drop_strategy = True
        if strategy:
            items = list(strategy.get('items') or [])
            if key.upper() in ('*', 'ALL'):
                kept = []
            else:
                # 菜单只会给出「指标」这一级（`editor:cmo` / `pi:xxx`），
                # 而每条线的 key 更长（`editor:cmo:line:1`）→ **前缀匹配** ✓
                def _same(item) -> bool:
                    item_key = str(item.get('key') or '')
                    return (item_key == key or item_key.startswith(key + ':')
                            or item_key.startswith(key))
                kept = [item for item in items if not _same(item)]
            if drop_strategy:
                kept = []
            if (drop_strategy
                    or (all_strategy and key.upper() in ('*', 'ALL'))):
                # ★ 同一策略可能同时挂在多个合约格（配对交易）→ 全部删掉 ✓
                self._remove_local_strategy(name)
                self.push_log(f'已从本地图表删除策略：{key}', 'info')
            elif len(kept) != len(items):
                if kept:
                    strategy['items'] = kept
                else:
                    self._local_strategies.pop(state_key, None)
                    # ★ 策略整条删掉 → 停止它的回放下单（不然删了还在交易 ✗）
                    strategy_label = str(strategy.get('name') or '')
                    if strategy_label:
                        getattr(self, '_local_runners', {}).pop(
                            strategy_label, None)
                        self._local_strategy_of.pop(state_key, None)
                self.push_log(f'已从本地图表删除：{key}', 'info')
        cell = max(0, int((payload or {}).get('cell') or 0))
        page = str((payload or {}).get('page') or '')
        if key.upper() in ('*', 'ALL'):
            selected: list = []
        else:
            selected = [item for item in self._local_items(name, cell, page)
                        if not (str(item.get('key')) == key
                                or str(item.get('key')).startswith(key + ':'))]
        self._local_set_items(name, cell, selected, page)
        self.push(self._local_indicator_payload(name, cell, page=page))

    def _on_local_strategy_trade(self, payload) -> None:
        # 本地图表回放：策略信号 -> 本地模拟账户（初始资金 / 手续费按设置）
        # 前端发来完整 marker 列表；reset=True 时清空已处理，之后按 id 去重。
        payload = payload or {}
        symbol = str(payload.get('symbol') or '')
        if not symbol:
            return
        raw = payload.get('signals') or []
        try:
            until = float(payload.get('until'))
        except (TypeError, ValueError):
            until = float('inf')
        done = self._local_strategy_done.setdefault(symbol, set())
        if bool(payload.get('reset')):
            done.clear()
        sim = self.local_sim()
        executed = 0
        for index, signal in enumerate(raw):
            if not isinstance(signal, dict):
                continue
            try:
                stamp = float(signal.get('time'))
            except (TypeError, ValueError):
                continue
            if stamp > until:
                continue
            side = str(signal.get('side') or '').lower()
            if side not in ('buy', 'sell'):
                continue
            key = str(signal.get('id') or f'{stamp}:{side}:{index}')
            if key in done:
                continue
            try:
                price = float(signal.get('price') or sim._price(symbol))
            except (TypeError, ValueError):
                price = sim._price(symbol)
            if price <= 0:
                continue
            close_only = bool(signal.get('close'))
            book = (sim.positions or {}).get(symbol) or {}
            long_qty = float(book.get('long') or 0.0)
            short_qty = float(book.get('short') or 0.0)
            did = False
            try:
                if side == 'buy':
                    if short_qty > 0:
                        sim.order(symbol, 'buy', short_qty, price, True,
                                  touch_price=False, force=True, auto=True)
                        did = True
                    if not close_only and long_qty <= 0:
                        sim.order(symbol, 'buy', 1, price, False,
                                  touch_price=False, force=True, auto=True)
                        did = True
                else:
                    if long_qty > 0:
                        sim.order(symbol, 'sell', long_qty, price, True,
                                  touch_price=False, force=True, auto=True)
                        did = True
                    if not close_only and short_qty <= 0:
                        sim.order(symbol, 'sell', 1, price, False,
                                  touch_price=False, force=True, auto=True)
                        did = True
            except Exception as error:                           # noqa: BLE001
                self.push_log(f'策略信号下单失败：{error!r}', 'error')
            done.add(key)
            if did:
                executed += 1
        if not executed:
            return
        self.push(sim.payload(symbol))
        self._push_sim_position(symbol, local=True)
        self._push_orders(symbol, local=True)
        self._push_sim_analysis()
        self.push_log(
            f'本地策略信号自动交易：{symbol} 执行 {executed} 笔'
            '（本地模拟账户）', 'success')

    def _on_local_order(self, payload) -> None:
        payload = payload or {}
        name = str(payload.get('symbol') or '')
        result = self.local_sim().order(
            name, str(payload.get('side') or ''), payload.get('qty') or 0,
            payload.get('price') or 0, bool(payload.get('close')),
            auto=bool(payload.get('auto')))
        if not result.get('ok'):
            self.push(_protocol.patch_toast(
                f"下单失败：{result.get('error')}", 'warning'))
            return
        self.push(self.local_sim().payload(name))
        self._push_sim_position(name, local=True)
        self._push_orders(name, local=True)
        self._push_sim_analysis()
        self.push_log(
            f"本地下单：{name} {'平仓' if payload.get('close') else '开仓'} "
            f"{result['order']['qty']:g} @ {result['order']['price']:g}",
            'success')

    def _on_local_active(self, payload=None) -> None:
        """多布局：点哪一格 → **交易面板 / 商品搜索**切到那一格的合约 ✓

        `payload = {cell, symbol, name}`：
        * 记住 `last_symbol`（下单 / 搜索默认用的合约）；
        * 把该合约的模拟账户推给前端 → 交易面板显示它的持仓 / 可买手数；
        * 顺手把持仓线也刷一次 ✓
        """
        payload = payload or {}
        name = str(payload.get('name') or payload.get('symbol') or '')
        if not name:
            return
        self.last_symbol = name
        try:
            payload_out = self.local_sim().payload(name)
            # ★ 带上 `symbol` / `最新价` / `active` → 前端交易面板的**搜索框**
            #   与**价格框**一起切到这个合约（用户要求 ✓）
            payload_out['type'] = 'local_account'   # ← 没 type 前端直接丢弃 ✗
            payload_out['symbol'] = name
            payload_out['active'] = True
            price_now = float(self.local_sim()._price(name) or 0.0)
            if price_now > 0:
                payload_out['last_price'] = price_now
            self.push(payload_out)
            self._push_sim_position(name, local=True)
            # 鼠标每点一次图表都会触发；日志会刷屏，按用户要求注释 ✓
            # self.push_log(f'当前交易合约：{name}', 'info')
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'切换交易合约失败：{error!r}', 'warning')

    def _on_local_account(self, payload=None) -> None:
        symbol = str((payload or {}).get('symbol') or '')
        self.push(self.local_sim().payload(symbol))

    def _on_local_account_action(self, payload) -> None:
        """本地图表「交易账户」页的 平 / 反 / 全 / 撤 ✓"""
        payload = payload or {}
        action = str(payload.get('action') or '')
        table = str(payload.get('table') or 'positions')
        symbol = str(payload.get('symbol') or '')
        if action in ('cancel', 'cancel_all') or table in ('orders', 'unfilled'):
            # ★ 本地模拟现在也有挂单了（限价单到价才成交 ✓）
            count = self.local_sim().cancel_pending(symbol)
            if count:
                self.push_log(f'本地模拟账户：已撤 {count} 笔挂单', 'info')
            else:
                self.push(_protocol.patch_toast('没有可撤的挂单', 'info'))
            self.push(self.local_sim().payload(''))
            self._push_orders(symbol, local=True)
            return
        sim = self.local_sim()
        if action in ('close', 'close_main'):
            # ★ 主价平仓 = 按**最新价**市价平掉该合约（不按输入价 ✓）
            book = (sim.positions or {}).get(symbol) or {}
            long_volume = float(book.get('long') or 0.0)
            short_volume = float(book.get('short') or 0.0)
            if long_volume <= 0 and short_volume <= 0:
                self.push(_protocol.patch_toast(f'{symbol} 没有持仓', 'info'))
                return
            price = sim._price(symbol)
            result = sim.order(symbol, 'sell' if long_volume > 0 else 'buy',
                               long_volume or short_volume, price, True)
            if not result.get('ok'):
                self.push(_protocol.patch_toast(
                    f"平仓失败：{result.get('error')}", 'warning'))
                return
            self.push_log(f'本地模拟账户：主价平仓 {symbol} @ {price:g}', 'info')
        elif action == 'all':
            sim.close_all()
            self.push_log('本地模拟账户：市价平掉全部持仓', 'info')
        elif action == 'reverse':
            sim.reverse_all()
            self.push_log('本地模拟账户：反手（平仓 + 反向开仓）', 'info')
        else:
            return
        self.push(sim.payload(''))
        self._push_orders(symbol, local=True)
        self._push_sim_position(symbol, local=True)

    def _on_local_reset(self, payload=None) -> None:
        self.local_sim().reset()
        self.push(self.local_sim().payload(''))
        name = str((payload or {}).get('symbol') or '')
        if name:
            self._push_orders(name, local=True)
        self.push_log('本地模拟账户已重置', 'info')

    def _on_toast_local(self, payload) -> None:
        """前端本地提示（如指标没有可调参数 ✓）"""
        self.push(_protocol.patch_toast(str(payload.get('text') or ''), 'info'))

    # -------------------------------------------------------- 布局
    def _layout_cells(self, symbol: str) -> List[dict]:
        """当前 tab 的每格信息（symbol + 每格真正的指标）✓"""
        info = self.tabs.get(symbol) or {}
        layout = info.get('layout') or {}
        symbols = list(layout.get('symbols') or []) or [symbol]
        cells = layout.get('cells') or []
        out: List[dict] = []
        for index, name in enumerate(symbols):
            cell = cells[index] if index < len(cells) and isinstance(
                cells[index], dict) else {}
            indicators = cell.get('indicators')
            if indicators is None:
                indicators = info.get('indicators') if index == 0 else []
            out.append({'symbol': str(name or symbol),
                        'indicators': [dict(item) for item in
                                       (indicators or [])]})
        return out

    def _layout_view(self, record: dict) -> dict:
        """布局列表里那一行（`单图 · 1分 · SHFE.ag2612 · …` ✓）"""
        cells = record.get('cells') or []
        cols = max(1, int(record.get('cols') or 1))
        rows = max(1, int(record.get('rows') or 1))
        count = cols * rows
        names = {(1, 1): '单图', (2, 1): '左右两图', (1, 2): '上下两图',
                 (2, 2): '四图'}
        shape = names.get((cols, rows), f'{cols}×{rows}（{count} 图）')
        cycle = int(record.get('cycle') or 60)
        # 布局管理只显示：布局形状 / 合约 / 周期；指标 & 参数不展示，
        # 但仍保留在 cells 里，应用布局时照常恢复 ✓
        parts = [str(cell.get('symbol') or '') for cell in cells]
        return {'key': record.get('key') or record.get('name'),
                'name': record.get('name'),
                'favorite': bool(record.get('favorite')),
                'scope': str(record.get('scope') or 'realtime'),
                'cols': int(record.get('cols') or 1),
                'rows': int(record.get('rows') or 1),
                'cycle': cycle,
                'count': count,
                'shape': shape,
                'indicators': sum(len(cell.get('indicators') or [])
                                  for cell in cells),
                'desc': f'{shape} · {_cycle_text(cycle)} · ' + ' | '.join(parts),
                'cells': cells}

    def _on_layouts(self, payload=None) -> None:
        from . import user_prefs as _prefs
        local = bool((payload or {}).get('local'))
        scope = 'local' if local else 'realtime'
        records = _prefs.layouts(scope)
        rows = [self._layout_view(item) for item in records]
        rows.sort(key=lambda row: (not row['favorite'], row['name'].lower()))
        # 导出文本随列表一起给 → 浏览器/Qt 都能「导出」✓
        try:
            text = json.dumps({'layouts': records},
                              ensure_ascii=False, indent=2)
        except Exception:                                        # noqa: BLE001
            text = ''
        self.push({'type': 'layouts', 'items': rows,
                   'local': local, 'scope': scope, 'exportText': text})

    def _on_export_csv(self, payload=None) -> None:
        """前端导出的 CSV → 落盘到 ``~/.minibt/exports/`` 并回报**绝对路径** ✓

        Qt（QWebEngine）里 ``<a download>`` 会落到一个看不见的默认下载目录
        （用户反馈“导出点了没反应”✗），所以**统一走后端落盘**：
        路径在 toast / 运行日志里都会显示，直接双击就能打开 ✓
        """
        payload = payload or {}
        text = str(payload.get('text') or '')
        name = _safe_filename(str(payload.get('name') or 'export.csv'))
        if not text:
            self.push(_protocol.patch_toast('导出失败：内容为空', 'warning'))
            return
        path = _write_export(name, text)
        if path is None:
            self.push(_protocol.patch_toast('导出失败：写文件出错', 'warning'))
            return
        rows = max(0, len(text.splitlines()) - 1)
        from . import user_prefs as _prefs
        items = _prefs.record_export(path, name, rows)
        self.push_log(f'已导出 {rows} 行：{path}', 'success')
        self.push(_protocol.patch_toast(
            f'已导出 {rows} 行：{os.path.basename(path)}', 'success',
            actions=[{'label': '打开文件', 'cmd': 'open_export',
                      'payload': {'path': path}},
                     {'label': '打开文件夹', 'cmd': 'open_export',
                      'payload': {'path': path, 'folder': True}}],
            detail=path))
        self.push({'type': 'exports', 'items': items})

    def _on_open_export(self, payload) -> None:
        """打开导出的文件 / 所在文件夹（Qt 用 QDesktopServices ✓）"""
        payload = payload or {}
        path = str(payload.get('path') or '')
        folder = bool(payload.get('folder'))
        if not path:
            items = self._export_items()
            if not items:
                self.push(_protocol.patch_toast('还没有导出过文件', 'warning'))
                return
            path = items[0]['path']          # 没给 → 打开最近那个 ✓
        target = os.path.dirname(path) if folder else path
        if not os.path.exists(target):
            self.push(_protocol.patch_toast(f'文件不存在：{target}', 'warning'))
            return
        error = _open_path(target)
        if error:
            self.push(_protocol.patch_toast(f'打开失败：{error}', 'warning'))
        else:
            self.push_log(f'已打开：{target}', 'success')

    def _on_exports(self, payload=None) -> None:
        """导出历史（最近 20 条 ✓）"""
        self.push({'type': 'exports', 'items': self._export_items()})

    def _on_export_remove(self, payload=None) -> None:
        """删掉一条导出**记录**（文件保留 ✓）"""
        from . import user_prefs as _prefs
        path = str((payload or {}).get('path') or '')
        items = _prefs.remove_export(path)
        self.push({'type': 'exports', 'items': items})
        self.push(_protocol.patch_toast(
            f'已删除记录：{os.path.basename(path) or path}', 'info'))

    def _on_exports_clear(self, payload=None) -> None:
        """清空导出历史（**文件保留** ✓）"""
        from . import user_prefs as _prefs
        _prefs.clear_exports()
        self.push({'type': 'exports', 'items': []})
        self.push(_protocol.patch_toast('已清空导出历史（文件还在）', 'info'))

    @staticmethod
    def _export_items() -> list:
        from . import user_prefs as _prefs
        return list(_prefs.exports())

    def _on_layouts_export(self, payload=None) -> None:
        """导出当前作用域的布局（本地 / 实时分开）✓"""
        from . import user_prefs as _prefs

        local = bool((payload or {}).get('local'))
        records = _prefs.layouts('local' if local else 'realtime')
        folder = os.path.join(os.path.expanduser('~'), '.minibt', 'exports')
        try:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(
                folder, f'desk_layouts_{time.strftime("%Y%m%d_%H%M%S")}.json')
            text = json.dumps({'layouts': records},
                              ensure_ascii=False, indent=2)
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(text)
        except OSError as error:
            self.push(_protocol.patch_toast(f'导出失败：{error}', 'warning'))
            return
        self.push_log(f'已导出布局：{path}', 'success')
        self.push(_protocol.patch_toast(f'已导出：{path}', 'success'))

    def _on_layouts_import(self, payload) -> None:
        """导入布局 JSON（同名覆盖；导入到当前作用域 ✓）"""
        from . import user_prefs as _prefs

        local = bool((payload or {}).get('local'))
        scope = 'local' if local else 'realtime'
        text = payload.get('text')
        if isinstance(text, str):
            try:
                data = json.loads(text)
            except (TypeError, ValueError):
                self.push(_protocol.patch_toast('导入失败：不是合法 JSON',
                                                'warning'))
                return
        else:
            data = text or {}
        records = data.get('layouts') if isinstance(data, dict) else data
        if not isinstance(records, list):
            self.push(_protocol.patch_toast('导入失败：缺少 layouts 数组',
                                            'warning'))
            return
        added = 0
        for item in records:
            if not isinstance(item, dict) or not item.get('name'):
                continue
            cells = item.get('cells') or []
            if not cells:
                continue
            _prefs.save_layout(str(item['name']),
                               int(item.get('cols') or 1),
                               int(item.get('rows') or 1),
                               int(item.get('cycle') or 60),
                               cells, key=str(item.get('key') or ''),
                               scope=scope)
            added += 1
        self.push_log(f'已导入 {added} 个布局', 'success')
        self.push(_protocol.patch_toast(f'已导入 {added} 个布局', 'success'))
        self._on_layouts({'local': local})

    def _on_layout_save(self, payload) -> None:
        from . import user_prefs as _prefs
        if payload.get('local'):
            cells = [dict(cell) for cell in (payload.get('cells') or [])]
            if not cells:
                self.push(_protocol.patch_toast('当前布局没有可保存的格子',
                                                'warning'))
                return
            # ★ 记住每个格子当前的本地策略（path）→ 应用布局时一并恢复 ✓
            strategies = getattr(self, '_local_strategies', {}) or {}
            names = getattr(self, '_local_cell_names', {}) or {}
            for index, cell in enumerate(cells):
                name = str(cell.get('symbol') or '')
                record = strategies.get(self._local_state_key(name))
                if not record and index in names:
                    key = self._local_state_key(str(names[index]))
                    record = strategies.get(key)
                if isinstance(record, dict) and record.get('path'):
                    cell['strategy'] = {
                        'name': str(record.get('name') or ''),
                        'path': str(record.get('path') or ''),
                    }
            record = _prefs.save_layout(
                str(payload.get('name') or ''),
                max(1, int(payload.get('cols') or 1)),
                max(1, int(payload.get('rows') or 1)),
                int(payload.get('cycle') or 60), cells,
                scope='local')
            self.push_log(f'已保存本地布局：{record["name"]}', 'success')
            self.push(_protocol.patch_toast(
                f'已保存布局：{record["name"]}', 'success'))
            self._on_layouts({'local': True})
            return
        symbol = self._resolve_tab_symbol(
            str(payload.get('symbol') or '')) or next(iter(self.tabs), '')
        info = self.tabs.get(symbol) or {}
        layout = info.get('layout') or {}
        cells = [dict(cell) for cell in
                 (payload.get('cells') or self._layout_cells(symbol))]
        # ★ 实时图表的策略是 tab 级的：把策略文件路径也写进布局 ✓
        strategy = dict(info.get('strategy') or {})
        path = str(strategy.get('path') or '')
        if path and os.path.isfile(path):
            for index, cell in enumerate(cells):
                has_editor = any(str(item.get('key') or '').startswith(
                    ('editor:', 'st:')) for item in
                    (cell.get('indicators') or []) if isinstance(item, dict))
                if index == 0 or has_editor:
                    cell['strategy'] = {
                        'name': str(strategy.get('name') or ''),
                        'path': path,
                    }
        record = _prefs.save_layout(
            str(payload.get('name') or ''),
            int(layout.get('cols') or 1), int(layout.get('rows') or 1),
            int(info.get('cycle') or 60), cells,
            scope='realtime')
        self.push_log(f'已保存布局：{record["name"]}', 'success')
        self.push(_protocol.patch_toast(f'已保存布局：{record["name"]}',
                                        'success'))
        self._on_layouts({'local': False})

    def _guess_local_strategy(self, symbols: List[str]) -> str:
        """旧布局只存了 `editor:` 线、没存策略路径 → 按合约静态匹配策略文件 ✓

        只读 AST（`strategy_plan.analyze`），不 import / 不运行用户代码。
        """
        wanted = {str(item) for item in (symbols or []) if str(item)}
        if not wanted:
            return ''
        try:
            from . import personal as _pi
            from .strategy_plan import analyze as _analyze
            folders = [str(item.get('path') or '')
                       for item in _pi.directories() if item.get('path')]
        except Exception:                                        # noqa: BLE001
            return ''
        best: List[tuple] = []
        home = os.path.expanduser('~/.minibt')
        for folder in folders:
            for path in glob.glob(os.path.join(folder, '**', '*.py'),
                                  recursive=True):
                try:
                    contracts = {str(item) for item in
                                 (_analyze(path).get('contracts') or [])}
                except Exception:                                # noqa: BLE001
                    continue
                score = len(wanted & contracts)
                if not score:
                    continue
                # ★ 优先用户自己的 personal 策略，其次按修改时间（最新优先）：
                #   tutorials / 示例目录里常有很多同合约的演示策略，
                #   不能让它们和用户的 test_2.py 打平导致猜不出来 ✓
                personal = os.path.abspath(path).startswith(
                    os.path.abspath(home))
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    mtime = 0.0
                best.append((score, personal, mtime, path))
        if not best:
            return ''
        best.sort(key=lambda item: (-item[0], -int(item[1]), -item[2]))
        return best[0][3]

    def _on_layout_apply(self, payload) -> None:
        from . import user_prefs as _prefs
        local = bool(payload.get('local'))
        scope = 'local' if local else 'realtime'
        record = _prefs.find_layout(str(payload.get('key') or ''),
                                    scope=scope)
        if record is None:
            self.push(_protocol.patch_toast(
                f'没找到布局（{scope}）', 'warning'))
            return
        # ★ 加载了策略：格数不能少于策略合约数（否则策略放不下 ✗）
        if local:
            need = 0
            for rec in (getattr(self, '_local_strategies', {}) or {}).values():
                need = max(need, len((rec or {}).get('contracts') or []))
        else:
            tab = self._resolve_tab_symbol(
                str(payload.get('symbol') or '') or next(iter(self.tabs), ''))
            need = len((self.tabs.get(tab) or {}).get('strategy_contracts')
                       or [])
        target = max(1, len(record.get('cells') or []) or 1)
        if need and target < need:
            message = (f'这个布局只有 {target} 格，策略需要 {need} 格 → '
                       '不能应用（会丢掉策略的合约）')
            self.push_log(message, 'warning')
            self.push(_protocol.patch_toast(message, 'warning'))
            return
        if local:
            cells = record.get('cells') or []
            symbols = [str(cell.get('symbol') or '') for cell in cells]
            symbols = [name for name in symbols if name] or ['']
            self.push({'type': 'layout', 'local': True,
                       'symbol': symbols[0], 'key': record.get('key') or '',
                       'count': len(symbols),
                       'cols': max(1, int(record.get('cols') or 1)),
                       'rows': max(1, int(record.get('rows') or 1)),
                       'symbols': symbols,
                       'cycle': int(record.get('cycle') or 60)})
            store = self.local_store()
            strategies: Dict[str, tuple] = {}
            had_editor = False
            for index, cell in enumerate(cells):
                name = str(cell.get('symbol') or '')
                if not name:
                    continue
                # 策略线（editor:…）是派生数据，不能当普通指标再算一遍 ✓
                raw_indicators = list(cell.get('indicators') or [])
                if any(str(item.get('key') or '').startswith(
                        ('editor:', 'st:')) for item in raw_indicators
                       if isinstance(item, dict)):
                    had_editor = True
                indicators = [dict(item) for item in raw_indicators
                              if isinstance(item, dict)
                              and not str(item.get('key') or '').startswith(
                                  ('editor:', 'st:'))]
                # ★ 先加载 K 线（加载会清掉这一格的指标），再把布局里保存
                #   的指标写回去并推给前端 ✓
                self._on_local_load({'name': name, 'cell': index})
                self._local_set_items(name, index, indicators)
                self.push(self._local_indicator_payload(name, index))
                # 布局里保存了策略文件 → 应用布局时把策略也重新挂上 ✓
                strategy = cell.get('strategy')
                if not isinstance(strategy, dict) or not strategy.get('path'):
                    current = (getattr(self, '_local_strategies', {}) or {}
                               ).get(self._local_state_key(name))                         or store.strategy(name)
                    if current.get('path'):
                        strategy = current
                path = str((strategy or {}).get('path') or '')
                # 旧布局 / 测试残留可能指向已删除的临时文件 → 忽略 ✓
                if path and os.path.isfile(path):
                    strategies.setdefault(path, (name, index))
            # 旧布局（只有 editor 线、没有 strategy 路径）→ 按合约猜一次 ✓
            if not strategies and had_editor:
                guessed = self._guess_local_strategy(symbols)
                if guessed:
                    strategies[guessed] = (symbols[0], 0)
                    self.push_log(
                        f'布局没有保存策略路径，已按合约匹配：'
                        f'{os.path.basename(guessed)}', 'info')
            for path, (name, index) in strategies.items():
                try:
                    self._on_editor_add_indicator({
                        'local': True, 'path': path,
                        'symbol': name, 'cell': index,
                    })
                except Exception as error:                       # noqa: BLE001
                    self.push_log(
                        f'布局恢复策略失败（{os.path.basename(path)}）：'
                        f'{error!r}', 'warning')
            self.push_log(f'应用本地布局：{record["name"]}', 'info')
            self.push(_protocol.patch_toast(
                f'已应用布局：{record["name"]}', 'success'))
            return
        symbol = self._resolve_tab_symbol(
            str(payload.get('symbol') or '')) or next(iter(self.tabs), '')
        info = dict(self.tabs.get(symbol) or {})
        cycles = int(record.get('cycle') or info.get('cycle') or 60)
        cells = record.get('cells') or []
        symbols = [str(cell.get('symbol') or symbol) for cell in cells] or [symbol]
        # ★ 布局里的合约先自动重取一次合约清单；仍找不到就提醒并跳过该格 ✓
        bad = self._ensure_realtime_contracts(symbols)
        if bad:
            bad_symbols = {item['symbol'] for item in bad}
            self.push_alert(
                '布局中的合约无法加载',
                '已跳过：' + '、'.join(sorted(bad_symbols)),
                detail=chr(10).join(
                    f"{item['symbol']}：{item['reason']}" for item in bad),
                level='warning')
            cells = [cell for cell in cells
                     if str(cell.get('symbol') or symbol) not in bad_symbols]
            symbols = [str(cell.get('symbol') or symbol) for cell in cells]
            if not symbols:
                return
        # 策略线是派生数据，不能当普通指标重算；路径单独恢复 ✓
        strategy_path = ''
        for cell in cells:
            strategy = cell.get('strategy')
            path = str((strategy or {}).get('path') or '')
            if path and os.path.isfile(path):
                strategy_path = path
                break
        current_strategy = dict(info.get('strategy') or {})
        if not strategy_path:
            path = str(current_strategy.get('path') or '')
            if path and os.path.isfile(path):
                strategy_path = path
        clean_cells = []
        for cell in cells:
            indicators = [dict(item) for item in
                          (cell.get('indicators') or [])
                          if isinstance(item, dict)
                          and not str(item.get('key') or '').startswith(
                              ('editor:', 'st:'))]
            clean_cells.append({'symbol': str(cell.get('symbol') or symbol),
                                'indicators': indicators})
        info.update({
            'cycle': cycles,
            'layout': {'cols': int(record.get('cols') or 1),
                       'rows': int(record.get('rows') or 1),
                       'symbols': symbols,
                       # ★ 每格的指标 + 样式也一起恢复（多图各画各的 ✓）
                       'cells': clean_cells},
            'indicators': [dict(item) for item in
                           ((clean_cells[0] if clean_cells else {})
                            .get('indicators') or [])],
        })
        self.tabs[symbol] = info
        self.push_log(f'应用布局：{record["name"]}', 'info')
        self.push({'type': 'layout', 'symbol': symbol,
                   'key': str(record.get('key') or ''),
                   'count': len(symbols),
                   'cols': info['layout']['cols'],
                   'rows': info['layout']['rows'],
                   'symbols': symbols, 'cycle': cycles})
        self.push(self.indicator_payload(symbol))
        self._push_cell_bars(symbol, info)
        self._push_cell_indicators(symbol, info)
        # ★ 布局保存了实时策略 → 应用布局时重新挂上（含指标线）✓
        if strategy_path and str(current_strategy.get('path') or '') !=                 strategy_path:
            try:
                self._remove_strategy_of(symbol)
                feed = info.get('feed') or pick_feed(self.feeds, symbol)
                frame = (feed.klines(symbol, cycles, self.tab_length(info))
                         if feed is not None else None)
                if frame is not None:
                    cls_name = ''
                    for cell in cells:
                        strategy = cell.get('strategy') or {}
                        if str(strategy.get('path') or '') == strategy_path:
                            cls_name = str(strategy.get('name') or '')
                            break
                    self._add_strategy_to_chart(
                        symbol, strategy_path, frame, cycles,
                        cls_name=cls_name)
            except Exception as error:                           # noqa: BLE001
                self.push_log(
                    f'布局恢复策略失败（{os.path.basename(strategy_path)}）：'
                    f'{error!r}', 'warning')

    def _on_layout_update(self, payload) -> None:
        """布局里**指标参数**的可视化编辑结果（cells 整份回写 ✓）"""
        from . import user_prefs as _prefs
        scope = 'local' if payload.get('local') else 'realtime'
        record = _prefs.find_layout(str(payload.get('key') or ''),
                                    scope=scope)
        if record is None:
            self.push(_protocol.patch_toast('没找到布局', 'warning'))
            return
        cells = payload.get('cells') or record.get('cells') or []
        updated = _prefs.save_layout(record['name'],
                                     int(record.get('cols') or 1),
                                     int(record.get('rows') or 1),
                                     int(record.get('cycle') or 60),
                                     cells, key=record['key'],
                                     scope=scope)
        self.push_log(f'已更新布局指标参数：{updated["name"]}', 'success')
        self.push(_protocol.patch_toast('已保存指标参数', 'success'))
        self._on_layouts({'local': scope == 'local'})
        if payload.get('local'):
            return
        # 如果这个布局正好是当前图（名字/合约一致），顺手应用一次 ✓
        for symbol, info in list(self.tabs.items()):
            symbols = (info.get('layout') or {}).get('symbols') or []
            if symbols and symbols[:len(updated['cells'])] == [
                    cell.get('symbol') for cell in updated['cells']]:
                self._on_layout_apply({'key': updated['key'], 'symbol': symbol})
                break

    def _on_layout_delete(self, payload) -> None:
        from . import user_prefs as _prefs
        key = str(payload.get('key') or '')
        scope = 'local' if payload.get('local') else 'realtime'
        ok = _prefs.delete_layout(key, scope=scope)
        self.push(_protocol.patch_toast('已删除布局' if ok else '没找到布局',
                                        'success' if ok else 'warning'))
        self._on_layouts({'local': scope == 'local'})

    def _on_layout_favorite(self, payload) -> None:
        from . import user_prefs as _prefs
        local = bool(payload.get('local'))
        _prefs.toggle_layout_favorite(str(payload.get('key') or ''),
                                      bool(payload.get('on')),
                                      scope='local' if local else 'realtime')
        self._on_layouts({'local': local})

    def _on_set_layout(self, payload) -> None:
        """工具栏「布局」→ 单图 / 左右两图 / 四图 ✓"""
        symbol = str(payload.get('symbol') or '') or next(iter(self.tabs), '')
        cols = max(1, int(payload.get('cols') or 1))
        rows = max(1, int(payload.get('rows') or 1))
        info = dict(self.tabs.get(symbol) or {})
        need = len(info.get('strategy_contracts') or [])
        if need and cols * rows < need:
            message = (f'策略需要 {need} 个图表，不能切到 {cols}x{rows} 布局')
            self.push_log(message, 'warning')
            self.push(_protocol.patch_toast(message, 'warning'))
            return
        current = ((info.get('layout') or {}).get('symbols') or [])
        symbols = [current[i] if i < len(current) else symbol
                   for i in range(cols * rows)]
        # 先取旧的 cells（否则下面覆盖 layout 就丢了 ✓）
        current_cells = list((info.get('layout') or {}).get('cells') or [])
        info['layout'] = {'cols': cols, 'rows': rows, 'symbols': symbols}
        # 新格默认没有指标，第 1 格保留原来的 ✓
        cells = []
        for index, cell_symbol in enumerate(symbols):
            if index == 0:
                cells.append({'symbol': cell_symbol,
                              'indicators': list(info.get('indicators') or [])})
            elif index < len(current_cells):
                cells.append(dict(current_cells[index]))
            else:
                cells.append({'symbol': cell_symbol, 'indicators': []})
        info['layout']['cells'] = cells
        self.tabs[symbol] = info
        self.push({'type': 'layout', 'symbol': symbol, 'cols': cols,
                   'rows': rows, 'symbols': symbols,
                   'cycle': int(info.get('cycle') or 60)})
        self._push_cell_bars(symbol, info)
        self._push_cell_indicators(symbol, info)

    def _push_cell_indicators(self, symbol: str, info: dict) -> None:
        """多格：每格自己的指标（第 2 格起带 `cell` ✓）"""
        cells = (info.get('layout') or {}).get('cells') or []
        for index, cell in enumerate(cells):
            items = cell.get('indicators') or []
            if index == 0 or not items:
                continue
            payload = self._indicator_payload_for(
                str(cell.get('symbol') or symbol), items)
            # ★ `symbol` 用**主 tab**（前端按它找 page）；`cell` 指定格子 ✓
            #   以前用 cell_symbol → 前端 pages.get('chart:cell') 找不到 ✗
            payload['symbol'] = symbol
            payload['cell'] = index
            self.push(payload)

    def _indicator_payload_for(self, symbol: str, indicators: list,
                               errors=None, frame=None, thrift=False,
                               defer_custom=False, tab_symbol: str = '',
                               cell: int = 0):
        """指定指标列表 → 指标补丁（复用 indicator_payload 的分支 ✓）

        `frame`：调用方已经取到的 K 线（自己取会再查一次行情源 ✓）
        `thrift`：`limit` 只按实际长度（节拍器里每格用，省 CPU ✓）
        """
        from . import indicators as _ind
        info = self.tabs.get(symbol) or {}
        feed = info.get('feed') or pick_feed(self.feeds, symbol)
        cycle = int(info.get('cycle') or 60)
        if frame is None:
            frame = (feed.klines(symbol, cycle, 500)
                     if feed is not None else None)
        # ★ 行情还是**占位表**（刚切到新合约 / 开盘前）→ 算出来全是空的：
        #   标 `pending` 让前端先**别删**旧线，等下一拍有数据再推 ✓
        ready = bool(frame is None
                     or (len(frame) and _kline_signature(frame)[0] > 0))
        limit = (max(1, len(frame)) if (thrift and frame is not None
                                        and len(frame)) else
                 max(600, len(frame) if frame is not None else 600))
        known = {entry['key'] for entry in _ind.CATALOG}
        builtin = [item for item in indicators
                   if str(item.get('key') or '').upper() in known]
        personal = [item for item in indicators
                    if str(item.get('key') or '').startswith('pi:')]
        custom = [item for item in indicators
                  if str(item.get('key') or '').upper() not in known
                  and not str(item.get('key') or '').startswith('pi:')]
        payload = _ind.compute(symbol, frame, builtin, limit=limit,
                               errors=errors)
        payload['items'] = list(payload.get('items') or [])             + self._compute_personal(frame, personal, errors)
        if custom and frame is not None and defer_custom and ready:
            # ★ 完整库指标（TV / TA-Lib / PandasTA…）放**后台线程**算：
            #   以前在这里同步算 → 加个指标要等好几秒、界面像卡住 ✗
            payload['pending'] = True
            self._spawn_cell_custom(str(tab_symbol or symbol), symbol,
                                    int(cell), frame, custom, payload,
                                    limit=limit, errors=errors)
        elif custom and frame is not None:
            try:
                from . import indicator_catalog as _cat
                keys = [str(item.get('key')) for item in custom]
                params = {str(item.get('key')): (item.get('params') or {})
                          for item in custom}
                extra = _cat.compute(frame, keys, params, limit=limit,
                                     errors=errors)
                holder = {'items': extra}
                _attach_indicator_params(holder, custom)
                payload['items'] += list(holder.get('items') or [])
            except Exception as error:                           # noqa: BLE001
                self.push_log(f'{symbol} 指标计算失败：{error!r}',
                              'warning')
        _attach_indicator_params(payload, indicators)
        _apply_overlay_override(payload, indicators)
        _apply_indicator_styles(payload, indicators)
        payload['strategyContracts'] = [
            str(item) for item in (info.get('strategy_contracts') or [])]
        if not ready:
            # 数据没准备好（占位表）→ 标记一下，调用方**不要**推空补丁 ✓
            payload['pending'] = True
            payload['dataMissing'] = True
        return payload

    def _spawn_cell_custom(self, tab_symbol: str, cell_symbol: str,
                           cell: int, frame, custom: list,
                           payload: dict, limit: int = 600,
                           errors=None) -> None:
        """**后台线程**算某一格的完整库指标（TradingView / TA-Lib…）✓

        * 主线程只推内置 / 个人指标（很快）+ `pending=True`；
        * 算完检查「这一格选的指标没变」再推合并补丁（过期直接丢掉 ✓）；
        * 同一格同一批指标已经在算 → 不重复起线程 ✓
        """
        from . import indicator_catalog as _cat
        info = self.tabs.get(tab_symbol) or {}
        keys = [str(item.get('key')) for item in custom]
        params = {str(item.get('key')): (item.get('params') or {})
                  for item in custom}
        signature = json.dumps([keys, params], sort_keys=True,
                               ensure_ascii=False, default=str)
        busy = info.setdefault('_cell_custom_busy', {})
        if busy.get(cell) == signature:
            return
        busy[cell] = signature
        snapshot = frame.copy() if hasattr(frame, 'copy') else frame
        base_items = list(payload.get('items') or [])

        def work() -> None:
            failed: Dict[str, str] = {}
            try:
                extra = _cat.compute(snapshot, keys, params, limit=limit,
                                     errors=failed)
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 格 {cell + 1} 完整库指标失败：{error!r}')
                extra = []
            busy_now = (self.tabs.get(tab_symbol) or {}).get(
                '_cell_custom_busy') or {}
            if busy_now.get(cell) == signature:
                busy_now.pop(cell, None)
            if errors is not None:
                errors.update(failed)
            latest = (self.tabs.get(tab_symbol) or {}).get('layout') or {}
            cells = latest.get('cells') or []
            record = cells[cell] if cell < len(cells) else {}
            current = [str(item.get('key'))
                       for item in ((record or {}).get('indicators') or [])]
            if keys != current:
                return                       # 期间改了指标 → 丢弃 ✓
            holder = {'items': list(extra)}
            _attach_indicator_params(holder, custom)
            merged = dict(payload)
            merged['items'] = base_items + list(holder.get('items') or [])
            merged['pending'] = False
            merged['symbol'] = tab_symbol
            merged['cell'] = int(cell)
            self.push(merged)

        threading.Thread(target=work, daemon=True,
                         name=f'desk-cell-ind-{tab_symbol}-{cell}').start()

    def _push_cell_bars(self, symbol: str, info: dict) -> None:
        """多格：给第 2..N 格推各自的 K 线 + **持仓线 / 挂单线** ✓

        以前只推 K 线 → 多布局里只有第 1 格有持仓线 / 挂单线（用户实测 ✗）。
        持仓 / 挂单每次都查 tqsdk（本地缓存，很便宜），但**节流到 1 秒**，
        避免每 0.5 秒把两三格的账户数据全推一遍。
        """
        symbols = (info.get('layout') or {}).get('symbols') or []
        cycle = int(info.get('cycle') or 60)
        now = time.monotonic()
        push_trade = (now - float(getattr(self, '_cell_trade_at', 0.0))) >= 1.0
        if push_trade:
            self._cell_trade_at = now
        # ★ 每格「K 线有没有变」的指纹 + 指标节流（收盘后数据不变 → 什么都不做 ✓）
        state = info.setdefault('_cell_state', {})
        ind_at = info.setdefault('_cell_ind_at', {})
        ind_interval = self._chart_update_interval_ms() / 1000.0
        layout_cells = (info.get('layout') or {}).get('cells') or []
        for index, cell_symbol in enumerate(symbols[1:], start=1):
            feed = pick_feed(self.feeds, cell_symbol) or self.current_feed()
            frame = feed.klines(cell_symbol, cycle,
                            self.tab_length(info)) \
                if feed is not None else None
            count, first_time, last_time = _kline_signature(frame)
            if frame is not None and not count:
                continue                    # 占位表（刚订阅 / 开盘前）→ 不推不转 ✓
            try:
                close = round(float(frame['close'].iloc[-1]), 6)
            except Exception:                                    # noqa: BLE001
                close = 0.0
            key = (count, first_time, last_time, close)
            before = state.get(index)
            if before != key:
                state[index] = key
                full = (before is None
                        or count != int(before[0])
                        or first_time != int(before[1]))
                bars = _protocol.bars_from_frame(frame)
                if bars:
                    # ★ `symbol` 用**主 tab**（否则前端找不到 page）；`cell` 定格子 ✓
                    self.push(dict(_protocol.patch_kline(
                        symbol, bars if full else bars[-2:], full),
                        cell=index))
                # ★ 这一格自己的指标：数据变了才重算（节流到指标刷新频率）✓
                record = (layout_cells[index]
                          if index < len(layout_cells) else {})
                selected = list((record or {}).get('indicators') or [])
                if selected and now - float(ind_at.get(index) or 0.0)                         >= ind_interval:
                    ind_at[index] = now
                    payload = self._indicator_payload_for(
                        cell_symbol, selected, frame=frame, thrift=True,
                        defer_custom=True, tab_symbol=symbol, cell=index)
                    payload['symbol'] = symbol
                    payload['cell'] = index
                    self.push(payload)
            if not push_trade or not cell_symbol:
                continue
            if symbol in getattr(self, 'replay_symbols', set()):
                continue
            # ★ 每格自己的持仓线（带 `cell`）+ 挂单线（带 `cell`）✓
            try:
                position = self.position_payload(cell_symbol, feed)
                position['cell'] = index
                self.push(position)
            except Exception:                                # noqa: BLE001
                pass
            try:
                orders = self.orders_payload(cell_symbol)
                orders['symbol'] = symbol       # 前端按主 tab 找 page ✓
                orders['cell'] = index
                self.push(orders)
            except Exception:                                # noqa: BLE001
                pass

    # -------------------------------------------------------- 回放
    def _replay_indicator_items(self, symbol: str, frame) -> list:
        """回放用的指标线（**全部同步算好** ✓）

        顺序：策略的线 → 内置 → 个人 → 完整库。完整库平时走后台线程，
        它的补丁带不回放需要的「整段」数据，所以这里直接同步算一次 ✓
        """
        from . import indicator_catalog as _cat
        from . import indicators as _ind

        info = self.tabs.get(symbol) or {}
        items: list = list(info.get('strategy_items') or [])
        selected = info.get('indicators') or []
        if frame is None or len(frame) == 0:
            return items
        limit = max(600, len(frame))
        known = {entry['key'] for entry in _ind.CATALOG}
        builtin = [item for item in selected
                   if str(item.get('key') or '').upper() in known]
        personal = [item for item in selected
                    if str(item.get('key') or '').startswith('pi:')]
        custom = [item for item in selected
                  if str(item.get('key') or '').upper() not in known
                  and not str(item.get('key') or '').startswith('pi:')]
        try:
            payload = _ind.compute(symbol, frame, builtin, limit=limit)
            items.extend(payload.get('items') or [])
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] 回放内置指标失败: {error!r}')
        items.extend(self._compute_personal(frame, personal))
        if custom:
            try:
                keys = [str(item.get('key')) for item in custom]
                params = {str(item.get('key')): (item.get('params') or {})
                          for item in custom}
                extra = _cat.compute(frame, keys, params, limit=limit)
                holder = {'items': extra}
                _attach_indicator_params(holder, custom)
                items.extend(holder['items'])
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 回放完整库指标失败: {error!r}')
        _attach_indicator_params({'items': items}, selected)
        return items

    def _on_replay(self, payload) -> None:
        """回放：把一段历史 K 线交给前端逐根播放（后端不参与 ✓）"""
        symbol = str(payload.get('symbol') or '') or next(iter(self.tabs), '')
        info = self.tabs.get(symbol) or {}
        cycle = int(payload.get('cycle') or info.get('cycle') or 60)
        # ★ 回放总长度默认 = 图表历史长度（≥ 数据长度）；以前写死 300 根 ✗
        default_count = self.candles_length()
        count = int(payload.get('count') or 0) or default_count
        count = max(30, min(count, 5000))
        # ★ 有策略 → 回放开始先用策略的 minibt 账户参数重置本地模拟账户 ✓
        runner = info.get('strategy_runner')
        if runner is not None:
            self._prepare_replay_account(runner)
        # ★ 回放中：交易走**本地模拟账户**（和本地图表一样 ✓）
        self.replay_symbols.add(symbol)
        self.push(self.trading_state(symbol))
        self._push_sim_position(symbol)      # 已有持仓 → 回放里直接画线 ✓
        feed = info.get('feed') or pick_feed(self.feeds, symbol)
        frame = feed.klines(symbol, cycle, count + 200) \
            if feed is not None else None
        # ★ 回放用的本地模拟账户也要按真实合约乘数算盈亏 ✓
        multiple = 1.0
        try:
            multiple = float(frame['volume_multiple'].iloc[0])
        except Exception:                                        # noqa: BLE001
            try:
                spec = getattr(feed, 'spec', None)
                quote = spec(symbol) if callable(spec) else None
                multiple = float(getattr(quote, 'volume_multiple', 1.0))
            except Exception:                                    # noqa: BLE001
                multiple = 1.0
        self.local_sim().set_contract(symbol, multiple)
        bars = _protocol.bars_from_frame(frame)
        if not bars:
            self.push(_protocol.patch_toast('回放：没有可用的历史 K 线', 'warning'))
            return
        bars = bars[-count:]
        # ★ 指标 / 策略一起回放：这里**同步算全**（完整库平时是后台算的，
        #   那份补丁到不了回放 payload → 回放里指标线会没有 ✗）
        indicator_items: list = []
        try:
            indicator_items = self._replay_indicator_items(symbol, frame)
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] 回放指标计算失败: {error!r}')
        # ★ 多图回放：每格用自己的合约 + 指标（长度对齐到最短 ✓）
        cells_payload = []
        cells = (info.get('layout') or {}).get('cells') or []
        for index, cell in enumerate(cells):
            cell_symbol = str(cell.get('symbol') or symbol)
            if index == 0:
                cell_bars = bars
                cell_items = indicator_items
            else:
                cell_feed = info.get('feed') or pick_feed(self.feeds,
                                                          cell_symbol)
                frame = cell_feed.klines(cell_symbol, cycle, count + 200) \
                    if cell_feed is not None else None
                try:
                    self.local_sim().set_contract(
                        cell_symbol, float(frame['volume_multiple'].iloc[0]))
                except Exception:                            # noqa: BLE001
                    try:
                        spec = getattr(cell_feed, 'spec', None)
                        quote = spec(cell_symbol) if callable(spec) else None
                        self.local_sim().set_contract(
                            cell_symbol,
                            float(getattr(quote, 'volume_multiple', 1.0)))
                    except Exception:                        # noqa: BLE001
                        pass
                cell_bars = _protocol.bars_from_frame(frame)[-count:]
                try:
                    cell_items = self._indicator_payload_for(
                        cell_symbol, cell.get('indicators') or []).get(
                            'items') or []
                except Exception as error:                       # noqa: BLE001
                    print(f'[desk] 回放第 {index + 1} 格指标失败: {error!r}')
                    cell_items = []
            cells_payload.append({'cell': index, 'symbol': cell_symbol,
                                  'bars': cell_bars, 'indicators': cell_items})
        shortest = min((len(item['bars']) for item in cells_payload),
                       default=len(bars))
        for item in cells_payload:
            item['bars'] = item['bars'][-shortest:] if shortest else item['bars']
        bars = cells_payload[0]['bars'] if cells_payload else bars
        indicator_items = cells_payload[0]['indicators'] \
            if cells_payload else indicator_items
        # `seek` = 从哪开始（0.3 = 30%，前端「选择时间段」用 ✓）
        try:
            seek = float(payload.get('seek') or 0.1)
        except (TypeError, ValueError):
            seek = 0.1
        seek = min(0.95, max(0.02, seek))
        self.push({'type': 'replay', 'symbol': symbol, 'cycle': cycle,
                   'bars': bars, 'indicators': indicator_items,
                   'cells': cells_payload,
                   'seek': seek,
                   'speed': int(payload.get('speed') or 5)})
        self.push_log(f'进入回放：{symbol} {cycle // 60 or cycle}'
                      f'{"秒" if cycle < 60 else "分"} {len(bars)} 根'
                      f'（从 {round(seek * 100)}% 处开始）', 'info')

    # -------------------------------------------------------- 指标选择器
    def _picker_groups(self):
        """左栏分组（个人 / 内置指标 各库 ✓）"""
        return [
            {'key': 'personal', 'label': '个人', 'sections': [
                {'key': 'favorites', 'label': '收藏'},
                {'key': 'my_scripts', 'label': '我的脚本'},
                {'key': 'my_strategies', 'label': '我的策略'},
            ]},
            {'key': 'builtin', 'label': '内置指标', 'sections': [
                # 「常用」按用户要求删掉：全部指标都来自 minibt 指标库 ✓
                {'key': 'all', 'label': '全部指标'},
                {'key': 'tradingview', 'label': 'TradingView'},
                {'key': 'pta', 'label': 'PandasTa'},
                {'key': 'tqta', 'label': 'TqTa'},
                {'key': 'tqfunc', 'label': 'TqFunc'},
                {'key': 'ti', 'label': 'TuLip'},
                {'key': 'btind', 'label': 'BtInd'},
                {'key': 'talib', 'label': 'TA-Lib'},
                {'key': 'finta', 'label': 'FinTa'},
                {'key': 'pine', 'label': 'Pine'},
            ]},
        ]

    def picker_items(self):
        """指标选择器条目：常用 6 个 + 完整库 + 个人（带 provider / section ✓）"""
        from . import indicator_catalog as _cat
        from . import personal as _pi
        from . import user_prefs as _prefs

        favorite = set(_prefs.favorites('indicator'))
        # ★ 「常用」组已删除（P59）：选择器里只有 minibt 指标库的内容 ✓
        items = []
        try:
            catalog = _cat.catalog()
        except Exception as error:                               # noqa: BLE001
            # 目录构建失败（某个库 import 炸了）→ 记下来，别让选择器全空 ✗
            catalog = []
            self.push_log(f'指标目录构建失败：{error!r}', 'error')
        for entry in catalog:
            provider = str(entry.get('group') or '').strip()
            prefix = str(entry.get('prefix') or '').strip()
            section = _SECTION_OF.get(prefix) or _SECTION_OF.get(provider) \
                or _SECTION_OF.get(provider.lower()) or 'pta'
            items.append({'key': entry['key'], 'label': entry['label'],
                          'desc': entry.get('desc') or entry.get('name') or '',
                          'provider': provider, 'section': section,
                          # 目录里字段叫 `overlap`（常用 6 个叫 `overlay`）✓
                          'overlay': bool(entry.get('overlap',
                                                    entry.get('overlay'))),
                          'favorite': entry['key'] in favorite,
                          'params': entry.get('params') or []})
        try:
            for entry in _pi.scan('indicator'):
                items.append({'key': entry['key'],
                              'label': entry['label'],
                              'desc': entry.get('file') or '',
                              'provider': '个人',
                              'section': 'my_scripts',
                              'favorite': entry['key'] in favorite,
                              'params': entry.get('params') or []})
            for entry in _pi.scan('strategy'):
                items.append({'key': entry['key'],
                              'label': entry['label'],
                              'desc': entry.get('file') or '',
                              'provider': '个人',
                              'section': 'my_strategies',
                              'strategy': True,
                              'favorite': entry['key'] in _prefs.favorites(
                                  'strategy'),
                              'params': []})
        except Exception:                                        # noqa: BLE001
            pass
        return items

    def _on_indicator_picker(self, payload) -> None:
        """「更多指标和策略…」→ 选择器（分组 + 条目 + 收藏 ✓）

        ⚠ 必须**永远有回包**：以前 `picker_items()` 一抛异常整份选择器就空白
        （用户看到「0 个 / 没有匹配的指标」✗）；现在兜住、把错误带给前端，
        并且「只有常用 6 个」时强制重建一次目录 ✓
        """
        from . import user_prefs as _prefs
        payload = payload or {}
        try:
            items = self.picker_items()
            error = ''
        except Exception as exc:                                 # noqa: BLE001
            items = []
            error = repr(exc)
            self.push_log(f'指标选择器加载失败：{exc!r}', 'error')
            self.push(_protocol.patch_toast(f'指标选择器加载失败：{exc!r}',
                                            'error'))

        def count(rows):
            out: Dict[str, int] = {}
            for row in rows:
                key = str(row.get('section') or '')
                out[key] = out.get(key, 0) + 1
            return out

        counts = count(items)
        if not error and len(items) <= 6:
            from . import indicator_catalog as _cat
            try:
                _cat.catalog(refresh=True)
            except Exception as exc:                             # noqa: BLE001
                error = repr(exc)
            else:
                try:
                    items = self.picker_items()
                except Exception as exc:                         # noqa: BLE001
                    error = repr(exc)
                counts = count(items)
                if len(items) <= 6 and not error:
                    error = '指标目录为空（minibt.indicators 反射失败）'
        if not error:
            self.push_log('指标选择器：' + ' · '.join(
                f'{key}={value}' for key, value in sorted(counts.items())),
                'info')
        self.push({'type': 'indicator_picker',
                   'groups': self._picker_groups(),
                   'items': items,
                   'counts': counts,
                   'total': len(items),
                   'error': error,
                   'reload': bool(payload.get('reload')),
                   'favorites': _prefs.favorites('indicator'),
                   'strategyFavorites': _prefs.favorites('strategy')})

    def _on_toggle_favorite(self, payload) -> None:
        from . import user_prefs as _prefs
        kind = 'strategy' if payload.get('strategy') else 'indicator'
        keys = _prefs.toggle_favorite(str(payload.get('key') or ''),
                                      bool(payload.get('on')), kind)
        self.push({'type': 'favorites', 'kind': kind, 'keys': keys})
        self._on_favorites({})

    def _on_favorites(self, payload=None) -> None:
        """工具栏下拉：★ 收藏指标 / 收藏策略 ✓"""
        from . import user_prefs as _prefs
        index = {item['key']: item for item in self.picker_items()}
        rows = []
        for key in _prefs.favorites('indicator'):
            item = index.get(key)
            rows.append({'key': key,
                         'label': (item or {}).get('label')
                         or f'{(item or {}).get("provider", "")}.{key}',
                         'provider': (item or {}).get('provider', ''),
                         'params': (item or {}).get('params', [])})
        strategies = []
        for key in _prefs.favorites('strategy'):
            item = index.get(key) or {}
            strategies.append({
                'key': key,
                'label': item.get('label') or key,
                # `picker_items()` 的 personal strategy 把文件路径放在 desc ✓
                'path': item.get('desc') or '',
                'provider': item.get('provider') or '个人',
                'params': [],
            })
        self.push({'type': 'favorites', 'kind': 'indicator',
                   'items': rows, 'strategies': strategies})

    # -------------------------------------------------------- 模板
    def _on_templates(self, payload=None) -> None:
        from . import user_prefs as _prefs
        rows = []
        for item in _prefs.templates():
            rows.append({'key': item['key'], 'name': item['name'],
                         'count': len(item.get('items') or []),
                         'items': item.get('items') or []})
        rows.sort(key=lambda row: row['name'].lower())
        self.push({'type': 'templates', 'items': rows})

    def _on_save_template(self, payload) -> None:
        from . import user_prefs as _prefs
        if payload.get('local'):
            name = str(payload.get('symbol') or '')
            cell = max(0, int(payload.get('cell') or 0))
            # ★ 指标按「页 + 格」存（多开本地图表时各自独立 ✓）
            items = self._local_items(
                name, cell, str(payload.get('page') or '')) if name else []
            if not items:
                self.push(_protocol.patch_toast(
                    '当前图还没有指标，无法保存模板', 'warning'))
                return
            title = str(payload.get('name') or '').strip() or (
                f'{name or "本地图表"} {time.strftime("%m-%d %H:%M")}')
            record = _prefs.save_template(title, items)
            self.push_log(f'已保存本地指标模板：{record["name"]}', 'success')
            self.push(_protocol.patch_toast(
                f'已保存模板：{record["name"]}', 'success'))
            self._on_templates({})
            return
        symbol = self._resolve_tab_symbol(
            str(payload.get('symbol') or '') or next(iter(self.tabs), ''))
        info = self.tabs.get(symbol) or {}
        cell = max(0, int(payload.get('cell') or 0))
        cells = (info.get('layout') or {}).get('cells') or []
        if cell > 0 and cell < len(cells) and isinstance(cells[cell], dict):
            # ★ 右键「保存当前指标模板」= 存**鼠标最后点击的那一格** ✓
            items = list(cells[cell].get('indicators') or [])
        else:
            items = list(info.get('indicators') or [])
        if not items:
            self.push(_protocol.patch_toast('当前图上还没有指标，无法保存模板',
                                            'warning'))
            return
        name = str(payload.get('name') or '').strip()
        if not name:
            timestamp = time.strftime('%m-%d %H:%M')
            name = f'{symbol} {timestamp}'
        record = _prefs.save_template(name, items)
        self.push_log(f'已保存指标模板：{record["name"]}', 'success')
        self.push(_protocol.patch_toast(f'已保存模板：{record["name"]}',
                                        'success'))
        self._on_templates({})

    def _on_apply_template(self, payload) -> None:
        from . import user_prefs as _prefs
        key = str(payload.get('key') or '')
        template = _prefs.find_template(key)
        if template is None:
            self.push(_protocol.patch_toast(f'没找到模板 {key}', 'warning'))
            return
        overrides = payload.get('params') or {}
        entries = []
        for item in template.get('items') or []:
            entry = {'key': item.get('key'),
                     'params': dict(item.get('params') or {})}
            extra = overrides.get(str(item.get('key')) or '')
            if isinstance(extra, dict):
                entry['params'].update(extra)
            entries.append(entry)
        if payload.get('local'):
            name = str(payload.get('symbol') or '')
            cell = max(0, int(payload.get('cell') or 0))
            if not name:
                return
            self._local_set_items(name, cell, entries,
                                  str(payload.get('page') or ''))
            self.push_log(f'应用本地指标模板：{template["name"]}'
                          f'（{len(entries)} 个指标）', 'info')
            self.push(_protocol.patch_toast(
                f'已应用模板：{template["name"]}', 'success'))
            self.push(self._local_indicator_payload(
                name, cell, page=str(payload.get('page') or '')))
            return
        symbol = self._resolve_tab_symbol(
            str(payload.get('symbol') or '') or next(iter(self.tabs), ''))
        info = dict(self.tabs.get(symbol) or {})
        cell = max(0, int(payload.get('cell') or 0))
        cells = [dict(item) for item in
                 ((info.get('layout') or {}).get('cells') or [])]
        names = [str(item or '') for item in
                 ((info.get('layout') or {}).get('symbols') or [])]
        if names and len(cells) < len(names):
            cells += [{'symbol': names[index], 'indicators': []}
                      for index in range(len(cells), len(names))]
        if cell >= len(cells):
            cell = 0
        # ★ 右键「我的模板」作用在**鼠标最后点击的那一格**（cell ✓）
        if cell == 0:
            info['indicators'] = entries
            if cells:
                cells[0] = dict(cells[0],
                                indicators=[dict(item) for item in entries])
                info['layout'] = dict(info.get('layout') or {}, cells=cells)
        else:
            cells[cell] = dict(cells[cell],
                               indicators=[dict(item) for item in entries])
            info['layout'] = dict(info.get('layout') or {}, cells=cells)
        self.tabs[symbol] = info
        self.push_log(f'应用指标模板：{template["name"]}'
                      f'（{len(entries)} 个指标）', 'info')
        self.push(_protocol.patch_toast(f'已应用模板：{template["name"]}',
                                        'success'))
        if cell == 0:
            self.push(self.indicator_payload(symbol))
        else:
            cell_symbol = str(cells[cell].get('symbol') or symbol)
            out = self._indicator_payload_for(cell_symbol, entries)
            out['symbol'] = symbol
            out['cell'] = cell
            self.push(out)

    def _on_delete_template(self, payload) -> None:
        from . import user_prefs as _prefs
        key = str(payload.get('key') or '')
        ok = _prefs.delete_template(key)
        self.push(_protocol.patch_toast('已删除模板' if ok else f'没找到模板 {key}',
                                        'success' if ok else 'warning'))
        self._on_templates({})

    # -------------------------------------------------------- K 线类型
    def _on_set_chart_type(self, payload) -> None:
        """蜡烛 / 空心 / 线 / 面积 / 基准 / 柱 ✓"""
        kind = str(payload.get('kind') or 'candle').lower()
        if kind not in ('candle', 'hollow', 'line', 'area', 'baseline', 'bar'):
            return
        symbol = str(payload.get('symbol') or '') or next(iter(self.tabs), '')
        info = dict(self.tabs.get(symbol) or {})
        info['chart_type'] = kind
        self.tabs[symbol] = info
        self.push({'type': 'chart_type', 'symbol': symbol, 'kind': kind})

    # -------------------------------------------------------- 合约搜索
    # -------------------------------------------------------- 全市场索引
    def symbol_index(self) -> List[dict]:
        """全市场合约索引（**所有**类型 / 交易所 / 股票市场 ✓）

        第一次：读 sqlite 缓存；过期 → **后台线程**重建（不卡 UI）；
        重建好了再推一次 `symbol_index` 补丁，搜索框自动变全 ✓
        """
        from . import symbol_index as _index

        if getattr(self, '_symbol_rows', None):
            return self._symbol_rows
        if _index.disabled():                 # 测试 / 断网：只搜缓存 ✓
            self._symbol_rows = []
            return self._symbol_rows
        self._symbol_rows = _index.load() or []
        if _index.stale() and not getattr(self, '_symbol_building', False):
            self.start_symbol_index(force=True)   # 过期就直接重建（分批 ✓）
        return self._symbol_rows

    def start_symbol_index(self, force: bool = False) -> None:
        """开始建索引（**主线程分批**，见 `_index_step`；不跨线程碰 tqsdk ✓）"""
        self.refresh_symbol_index(force=force)

    def refresh_symbol_index(self, force: bool = False) -> None:
        """**增量更新**索引：只补新上市 / 新标的（不必整天重建 ✓）

        已有索引 → `symbol_index.refresh()`（增量）；没有 → 全量。
        `force=True` 时无视节流（命令 / `--check` 用 ✓）。
        """
        import time as _time

        from . import symbol_index as _index
        if _index.disabled():                  # 测试 / 断网：不建索引 ✓
            return
        now = _time.monotonic()
        last = getattr(self, '_symbol_refresh_at', 0.0)
        if not force and now - last < 3600:      # 一小时最多一次 ✓
            return
        if getattr(self, '_symbol_building', False):
            return
        # ★ 索引**在主线程分批建**（每拍一个市场）：跨线程碰 tqsdk 会和
        #   主线程 `pump()` 抢锁 → 界面卡死（实盘实测 ✗）
        if not hasattr(self, '_symbol_rows'):
            self._symbol_rows = _index.load() or []
        try:
            self._index_jobs = _index.batches(self.feeds)
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'合约索引准备失败：{error!r}', 'warning')
            return
        self._symbol_building = True
        self.push_log('开始建立全市场合约索引（后台分批，慢一点但不会卡 ✓）',
                      'info')

    def _index_step(self) -> None:
        if self._quotes_blocked():
            return
        """主线程：每次建一小批索引（`tick()` 里调用 ✓）"""
        if not getattr(self, '_symbol_building', False):
            return
        job = self._index_jobs
        try:
            label, rows = next(job)
        except StopIteration:
            from . import symbol_index as _index
            rows = self._symbol_rows or []
            _index.save(rows)
            self._symbol_building = False
            self._index_jobs = None
            self._symbol_rows = rows
            self.push_log(f'合约索引已更新：共 {len(rows)} 个', 'success')
            self.push({'type': 'symbol_index', 'count': len(rows),
                       'markets': _index.markets_payload()})
            return
        except Exception as error:                               # noqa: BLE001
            self._symbol_building = False
            self._index_jobs = None
            self.push_log(f'合约索引增量更新失败：{error!r}', 'warning')
            return
        before = len(self._symbol_rows or [])
        self._symbol_rows = rows
        added = max(0, len(rows) - before)
        if added:
            self.push_log(
                f'索引·{label}：新增 {added} 个，累计 {len(rows)} 个', 'info')
        else:
            self.push_log(
                f'索引·{label}：无新增（已缓存 {len(rows)} 个）', 'info')

    def search_pool(self) -> List[dict]:
        """所有类型/交易所的合约（缓存优先，不额外联网 ✓）"""
        if self._search_pool:
            return self._search_pool
        pool: List[dict] = []
        seen = set()
        cache = self.symbol_cache()
        keys = list(cache.keys()) if cache is not None else []
        for key in keys:
            try:
                rows = cache.get(key) or []
            except Exception:                                    # noqa: BLE001
                rows = []
            kind, _, exchange = key.partition(':')
            for row in rows:
                symbol = str(row.get('symbol') or '')
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                pool.append({'symbol': symbol,
                             'name': str(row.get('name') or ''),
                             'exchange': exchange,
                             'type': kind})
        for row in self._last_rows.values():
            symbol = str(row.get('symbol') or '')
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            pool.append({'symbol': symbol, 'name': str(row.get('name') or ''),
                         'exchange': str(row.get('exchange') or ''),
                         'type': str(self.filter.get('type') or '')})
        self._search_pool = pool
        return pool

    def _on_ticket_order(self, payload=None) -> None:
        """买卖盘一点下单（**市价 / 目标仓位**，复刻 minibt 实时图 ✓）

        * 多头（净仓 > 0）：左侧「买入」= 继续加多，右侧「平仓」= 全部平掉
        * 空头（净仓 < 0）：左侧「平仓」= 全部平掉，右侧「卖出」= 继续加空
        * 手数取**二级报价里的手数**（前端传 `qty` ✓）
        * 走 ``TargetPosTask.set_target_volume``（天勤），不是限价单 ✓
        """
        payload = payload or {}
        symbol = str(payload.get('symbol') or '')
        side = str(payload.get('side') or '').lower()
        if not symbol or side not in ('buy', 'sell'):
            return
        trader = self.trading_view()
        if not self.trading or trader is None or not trader.ready(symbol):
            self.push(_protocol.patch_toast('交易未启用（行情/交易接口没连上）',
                                            'warning'))
            return
        try:
            qty = max(1, int(payload.get('qty') or 1))
        except (TypeError, ValueError):
            qty = 1
        position = trader._position(symbol)                      # noqa: SLF001
        # 天勤新老版本字段名不一样（pos_long / volume_long ✓）
        long_volume = _num_local(_field_any_local(
            position, ('pos_long', 'volume_long'))) or 0.0
        short_volume = _num_local(_field_any_local(
            position, ('pos_short', 'volume_short'))) or 0.0
        net = int(long_volume - short_volume)
        if side == 'buy':
            target = 0 if net < 0 else net + qty     # 空头 → 平仓；否则加多 ✓
        else:
            target = 0 if net > 0 else net - qty     # 多头 → 平仓；否则加空 ✓
        text = trader._set_target(symbol, target)                # noqa: SLF001
        from .trading import _trade_failed as _tf
        self._audit_action('order', text, symbol=symbol,
                           side=side, volume=qty,
                           status='PENDING' if not _tf(text) else 'REJECTED')
        from .trading import _trade_failed
        ok = not _trade_failed(text)
        self.push_log(f'[买卖盘] {text}', 'success' if ok else 'warning')
        self.push(_protocol.patch_toast(text,
                                        'success' if ok else 'warning'))
        self.push(self.position_payload(symbol))
        self.push(self.book_payload(symbol))

    def _on_ticker_refresh(self, payload=None) -> None:
        """重推一次播放条（开关变化 / 手动刷新 ✓）"""
        rows = list(getattr(self, '_ticker_source', None) or [])
        if not rows:
            rows = list(self._last_rows.values())
        self._refresh_ticker(rows)

    def _on_symbols_refresh(self, payload=None) -> None:
        """手动触发索引**增量更新**（报价页「刷新」/ 搜索框也会用到 ✓）"""
        force = bool((payload or {}).get('force', True))
        self.refresh_symbol_index(force=force)
        self.push(_protocol.patch_toast('正在增量更新合约索引…', 'info'))

    #: 键盘精灵每类最多给几条（太多滚不完 ✓）
    SPRITE_LIMIT = 12

    def _on_sprite_search(self, payload) -> None:
        """键盘精灵（空格键）→ **指标 / 策略 / 合约 / 股票** 一起搜 ✓

        和 miniqt 的键盘精灵一个意思：一个输入框搜全部，回车（列表第一行）
        或双击 → 指标/策略「加到鼠标最后点击的那张图」，合约/股票「切到它」。
        """
        text = str(payload.get('text') or '').strip()
        limit = int(payload.get('limit') or self.SPRITE_LIMIT)
        lower = text.lower()
        items: List[Dict[str, Any]] = []

        def match(*values) -> bool:
            if not lower:
                return True
            return any(lower in str(value or '').lower() for value in values)

        # ★ 本地图表：键盘精灵初始先列本地 CSV（用户要求）✓
        if payload.get('local'):
            try:
                for row in self.local_store().items():
                    if match(row.get('name'), row.get('symbol'),
                             row.get('source')):
                        items.append({
                            'kind': 'symbol',
                            'key': str(row.get('name') or ''),
                            'symbol': str(row.get('name') or ''),
                            'label': str(row.get('name') or ''),
                            'name': str(row.get('source') or ''),
                            'group': '本地数据',
                        })
            except Exception as error:                           # noqa: BLE001
                print(f'[desk] 键盘精灵：本地数据不可用 {error!r}')

        # ---- ① 常用指标（6 个）+ 完整库（766 个）----
        try:
            from . import indicator_catalog as _cat
            from . import indicators as _ind
            for entry in _ind.CATALOG:
                if match(entry['key'], entry.get('label')):
                    items.append({'kind': 'indicator', 'key': entry['key'],
                                  'label': str(entry.get('label') or
                                               entry['key']),
                                  'group': '常用指标'})
            for entry in _cat.catalog():
                if match(entry['key'], entry.get('name'),
                         entry.get('label')):
                    items.append({'kind': 'indicator', 'key': entry['key'],
                                  'label': str(entry.get('label') or
                                               entry['name']),
                                  'group': str(entry.get('group') or '指标')})
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] 键盘精灵：指标目录不可用 {error!r}')

        # ---- ② 个人指标 / 个人策略（用户自己加的 ✓）----
        try:
            from . import personal as _pi
            for entry in _pi.scan('indicator'):
                if match(entry.get('key'), entry.get('name')):
                    items.append({'kind': 'indicator', 'key': entry['key'],
                                  'label': str(entry.get('name') or
                                               entry['key']),
                                  'group': '个人指标'})
            for entry in _pi.scan('strategy'):
                if match(entry.get('key'), entry.get('name')):
                    items.append({'kind': 'strategy', 'key': entry['key'],
                                  'label': str(entry.get('name') or
                                               entry['key']),
                                  'group': '个人策略'})
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] 键盘精灵：个人指标不可用 {error!r}')

        indicators = [item for item in items if item['kind'] != 'symbol']
        indicators.sort(key=lambda item: (
            0 if str(item['label']).lower().startswith(lower) else 1,
            0 if item['group'] == '常用指标' else 1,
            len(str(item['label'])), str(item['label']).lower()))

        # ---- ③ 合约 / 股票（全市场索引 ✓）----
        contracts: List[Dict[str, Any]] = []
        try:
            from . import symbol_index as _index
            rows = self.symbol_index()
            if rows:
                found = _index.search(rows, text, '')
                for row in found[:limit]:
                    contracts.append({
                        'kind': 'symbol',
                        'key': str(row.get('symbol') or ''),
                        'symbol': str(row.get('symbol') or ''),
                        'label': str(row.get('symbol') or ''),
                        'name': str(row.get('name') or ''),
                        'group': str(row.get('type_label') or
                                     row.get('market') or '合约'),
                    })
        except Exception as error:                               # noqa: BLE001
            print(f'[desk] 键盘精灵：合约索引不可用 {error!r}')

        locals_ = [item for item in items if item['kind'] == 'symbol'
                   and item.get('group') == '本地数据']
        self.push({'type': 'sprite', 'text': text,
                   'items': locals_ + indicators[:limit] + contracts,
                   'total': len(locals_) + len(indicators) + len(contracts),
                   'loading': bool(getattr(self, '_symbol_building', False))})

    def _on_symbol_search(self, payload) -> None:
        """输入框 → 匹配**全市场**合约（代码 / 名称，前缀优先 ✓）

        和 miniqt 的「商品代码搜索」一样：**不分当前报价页的类型/交易所**，
        期货（FUT / 主连 / 指数）+ 股票（沪/深/港/美）一起搜 ✓

        第一次搜索时才建全市场索引（后台线程；不在 tick 里自动建 ✓）
        """
        from . import symbol_index as _index

        self.refresh_symbol_index()

        text = str(payload.get('text') or '').strip().lower()
        market = str(payload.get('market') or '')
        rows = self.symbol_index()
        if rows:
            # 索引 ∪ 缓存池（索引可能旧 / 缺新合约，缓存里看过的也要能搜到 ✓）
            known = {row['symbol'] for row in rows}
            for item in self.search_pool():
                if item.get('symbol') and item['symbol'] not in known:
                    rows = rows + [{'symbol': item['symbol'],
                                    'name': item.get('name') or '',
                                    'exchange': item.get('exchange') or '',
                                    'type': item.get('type') or '',
                                    'market': '', 'type_label': ''}]
                    known.add(item['symbol'])
            items = _index.search(rows, text, market)
            self.push({'type': 'symbol_search',
                       'items': items,
                       'markets': _index.markets_payload(),
                       'market': market,
                       'total': len(rows),
                       'loading': bool(getattr(self, '_symbol_building',
                                               False))})
            return
        pool = self.search_pool()
        if not text:
            items = pool[:50]
        else:
            def score(item):
                symbol = item['symbol'].lower()
                name = item['name'].lower()
                if symbol.startswith(text):
                    return (0, symbol)
                if text in symbol:
                    return (1, symbol)
                if name.startswith(text):
                    return (2, name)
                if text in name:
                    return (3, name)
                return (9, symbol)

            matched = [item for item in pool if score(item)[0] < 9]
            matched.sort(key=score)
            items = matched[:50]
        from . import symbol_index as _index
        for item in items:
            item['type_label'] = _index.TYPE_LABELS.get(
                str(item.get('type') or ''), str(item.get('type') or ''))
        self.push({'type': 'symbol_search', 'items': items,
                   'markets': _index.markets_payload(),
                   'market': market,
                   'total': len(pool),
                   'loading': bool(getattr(self, '_symbol_building', False)),
                   'indexed': False})

    def _strategy_live_context(self, cls):
        """实时图表加策略：天勤已连接 + 允许交易 → 真下单 ✓

        不再要求策略类写 ``live=True``：实时图表本来只有这一种运行语义；
        本地图表 / 回测 / 参数优化仍传 ``live=False``，不会误下单。
        """
        live = bool(self.trading
                    and self.futures is not None
                    and getattr(self.futures, 'available', lambda: False)())
        api = getattr(self.futures, 'api', None) if live else None
        account = None
        if live:
            try:
                account = self.account_view().current()
            except Exception:                                    # noqa: BLE001
                account = None
        return bool(live and api is not None), api, account

    def _strategy_frame(self, symbol: str, info: dict = None,
                        cycle: int = 0):
        """取某个合约的实时 K 线（多合约策略的第二条腿 ✓）"""
        symbol = str(symbol or '')
        if not symbol:
            return None
        info = info or {}
        feed = pick_feed(self.feeds, symbol) or info.get('feed') \
            or self.current_feed()
        if feed is None:
            return None
        try:
            frame = feed.klines(symbol, int(cycle or info.get('cycle') or 60),
                                self.tab_length(info))
        except Exception:                                        # noqa: BLE001
            return None
        return frame if frame is not None and len(frame) else None

    def _strategy_frames_for_chart(self, symbol: str, info: dict,
                                   cls=None, path: str = '') -> List[Any]:
        """**klines1/2/…** 写法：只用当前**已选好的布局格**做 frames ✓

        这种写法里没有 `get_kline('合约')`，程序无法知道合约名 → 必须由用户
        先选好布局、加载好对应合约，再添加策略。这里**不会**擅自切布局 /
        补其它 tab；数量不够时由调用方提醒。
        """
        layout = dict((info or {}).get('layout') or {})
        symbols: List[str] = []
        for item in list(layout.get('symbols') or []):
            text = str(item or '')
            if text and text not in symbols:
                symbols.append(text)
        for cell in (layout.get('cells') or []):
            if isinstance(cell, dict):
                text = str(cell.get('symbol') or '')
                if text and text not in symbols:
                    symbols.append(text)
        if not symbols:
            symbols = [str(symbol or '')]
        frames: List[Any] = []
        cycle = int((info or {}).get('cycle') or 60)
        for name in symbols:
            frame = self._strategy_frame(name, info, cycle)
            if frame is not None:
                frames.append((name, frame))
        return frames

    def _fetch_strategy_frame(self, info: dict, cycle: int = 0):
        """给 runner 的 `fetch_frame` 回调（策略 get_kline 其它合约时用）

        返回 ``(真实合约, frame)``：test_2.py 的 `LocalDatas.pp2609_60`
        会按品种代码对到已打开的 `DCE.pp2609` ✓
        """
        def fetch(symbol: str, duration_seconds=None):
            from .strategy_runner import _same_contract, _same_underlying
            text = str(symbol or '')
            if not text:
                return None
            layout = dict((info or {}).get('layout') or {})
            candidates: List[str] = []
            for item in list(layout.get('symbols') or []):
                item = str(item or '')
                if item and item not in candidates:
                    candidates.append(item)
            for key in list(getattr(self, 'tabs', {}) or {}):
                key = str(key or '')
                if key and key not in candidates:
                    candidates.append(key)
            real = text
            for item in candidates:
                if _same_contract(item, text):
                    real = item
                    break
            else:
                for item in candidates:
                    if _same_underlying(item, text):
                        real = item
                        break
            frame = self._strategy_frame(real, info,
                                         int(duration_seconds or cycle or 0))
            return (real, frame) if frame is not None else None
        return fetch

    @staticmethod
    def _layout_for_count(count: int):
        """N 个合约 → 预设布局（和前端 `layoutSpecForCount` 保持一致 ✓）"""
        presets = {1: ('single', 1, 1), 2: ('h2', 2, 1),
                   3: ('h3', 3, 1), 4: ('grid4', 2, 2)}
        return presets.get(max(1, int(count or 1)), ('single', 1, 1))

    def _auto_layout_local(self, contracts: List[str],
                           current: str = '') -> None:
        """本地图表：自动切布局 + 把策略里的本地合约按顺序载入各格 ✓"""
        contracts = [str(item) for item in (contracts or []) if str(item)]
        if not contracts:
            return
        # ★ 策略合约数 ≤ 现有格数 → **保持当前布局**，只把合约装进现有格子
        #   （多余格不关，用户可以继续看别的 CSV ✓）
        existing = dict(getattr(self, '_local_cell_names', {}) or {})
        if existing and len(contracts) <= len(existing):
            try:
                from .strategy_runner import _same_contract as _same
            except Exception:                                # noqa: BLE001
                _same = lambda a, b: str(a) == str(b)        # type: ignore
            used = set()
            placements: List[tuple] = []
            for name in contracts:
                index = None
                for i in sorted(existing):
                    if i in used:
                        continue
                    try:
                        hit = _same(str(existing[i]), name)
                    except Exception:                        # noqa: BLE001
                        hit = str(existing[i]) == name
                    if hit:
                        index = i
                        break
                if index is None:
                    for i in sorted(existing):
                        if i not in used:
                            index = i
                            break
                if index is None:
                    break
                used.add(index)
                placements.append((index, name))
            if len(placements) == len(contracts):
                for index, name in placements:
                    self._on_local_load({'name': name, 'cell': index})
                    self.push_log(
                        f'策略需要本地合约 {name} → 加载到第 {index + 1} 格',
                        'info')
                self.last_symbol = contracts[0]
                return
        key, cols, rows = self._layout_for_count(len(contracts))
        symbol = str(current or contracts[0] or '')
        # 前端本地图表：`layout` 补丁（`local:true`）→ 选对应预设布局 ✓
        self.push({'type': 'layout', 'local': True, 'symbol': symbol,
                   'count': len(contracts), 'key': key,
                   'cols': cols, 'rows': rows,
                   'symbols': list(contracts)})
        for index, name in enumerate(contracts):
            self._on_local_load({'name': name, 'cell': index})
            self.push_log(
                f'策略需要本地合约 {name} → 自动加载到第 {index + 1} 格',
                'info')
        self.last_symbol = contracts[0]

    def _resolve_realtime_contract(self, name: str, info: dict) -> str:
        """本地名 / 真实代码 → 实时图表里的真实合约 ✓"""
        from .strategy_runner import _same_contract, _same_underlying
        text = str(name or '').strip()
        if not text:
            return ''
        candidates: List[str] = []
        layout = dict((info or {}).get('layout') or {})
        for item in list(layout.get('symbols') or []):
            item = str(item or '')
            if item and item not in candidates:
                candidates.append(item)
        for key in list(getattr(self, 'tabs', {}) or {}):
            key = str(key or '')
            if key and key not in candidates:
                candidates.append(key)
        for item in candidates:
            if _same_contract(item, text):
                return item
        for item in candidates:
            if _same_underlying(item, text):
                return item
        if '.' in text:
            return text                   # 已经是真实合约代码 ✓
        # `pp2609_60` 这种本地名 → 在天勤**本地合约字典**里按品种找 ✓
        feed = getattr(self, 'futures', None)
        if feed is not None:
            for exchange in ('SHFE', 'DCE', 'CZCE', 'CFFEX', 'INE', 'GFEX'):
                try:
                    symbols = feed.contracts_local('FUT', exchange) or []
                except Exception:                            # noqa: BLE001
                    symbols = []
                for symbol in symbols:
                    if _same_underlying(symbol, text):
                        return str(symbol)
        return text

    def _ensure_realtime_contracts(self, symbols: List[str]) -> List[dict]:
        """布局 / 开图用：合约不在缓存时自动重取一次；仍没有 → 返回 bad ✓"""
        feed = getattr(self, 'futures', None)
        if feed is None or not getattr(feed, 'available', lambda: False)():
            return []
        bad: List[dict] = []
        refreshed: Dict[str, set] = {}
        for symbol in symbols:
            symbol = str(symbol or '')
            if not symbol or _is_stock(symbol) or symbol.startswith('KQ.'):
                continue
            # 已经有 tab / 报价 / K 线 → 合约已在用，不需要再校验 ✓
            if symbol in self.tabs or symbol in self._last_rows:
                continue
            exchange = symbol.split('.')[0].upper()
            known = refreshed.get(exchange)
            if known is None:
                try:
                    known = {str(item) for item in
                             (feed.contracts_local('FUT', exchange) or [])}
                except Exception:                            # noqa: BLE001
                    known = set()
                if not known or symbol not in known:
                    known = self._refresh_futures_contracts(feed, exchange)
                refreshed[exchange] = known
            if symbol not in known:
                bad.append({'symbol': symbol,
                            'reason': '天勤合约列表里没有这个合约'
                                       '（已重取一次；可能已下市 / 代码过期）'})
        return bad

    def _refresh_futures_contracts(self, feed, exchange: str,
                                   wait: float = 3.0) -> set:
        """用户输入合约找不到时**强制重新取一次**合约清单（最多等 2 秒）✓

        TqSdk 刚登录 / 切交易所时 `_data['symbols']` 可能还没下载完；
        这时直接报“找不到”会误杀合法合约。先 reset 再重查一次，
        真拿不到才让调用方提示并跳过。
        """
        if feed is None or not exchange:
            return set()
        # ★ 已有异步查询在跑时**不要 reset**（reset 会把刚发起的查询清掉，
        #   反而导致永远拿不到合约）；等 pump 把它填满 ✓
        try:
            pending = getattr(feed, '_symbol_lists', {}) or {}
            if ('FUT', exchange) not in pending:
                feed.reset_symbols('FUT', exchange, force=True)
        except Exception:                                    # noqa: BLE001
            pass
        deadline = time.monotonic() + max(0.0, float(wait))
        last: set = set()
        while True:
            # ★ 必须驱动一次 TqSdk loop；否则主线程干等，查询永远不会回来 ✗
            try:
                pump = getattr(self, 'pump', None)
                if callable(pump):
                    pump(0.05)
            except Exception:                                # noqa: BLE001
                pass
            try:
                rows = feed.contracts('FUT', exchange) or []
            except Exception:                                # noqa: BLE001
                rows = []
            last = {str(item) for item in rows}
            if last or time.monotonic() >= deadline:
                return last
            time.sleep(0.1)

    def _validate_realtime_contracts(self, contracts: List[str]) -> List[dict]:
        """天勤报价里有没有这些合约（没有 → 弹出提醒并中止 ✓）"""
        bad: List[dict] = []
        known_by_exchange: Dict[str, set] = {}
        refreshed: set = set()
        feed = getattr(self, 'futures', None)
        api = getattr(feed, 'api', None) if feed is not None else None
        available = bool(feed is not None
                         and getattr(feed, 'available', lambda: False)())
        for symbol in contracts:
            symbol = str(symbol or '')
            if not symbol:
                continue
            if not available or api is None:
                bad.append({'symbol': symbol,
                            'reason': '未连接天勤行情/交易接口'})
                continue
            if not _symbols.is_tradeable(symbol):
                bad.append({'symbol': symbol,
                            'reason': '主连 / 指数不能交易，请用具体月份合约'})
                continue
            # ★ 图表已经开出来 / 有报价 / 有名称 → 合约肯定可用，
            #   不要因为合约清单慢一拍就误报“找不到” ✗
            if (symbol in self.tabs or symbol in self._last_rows
                    or feed.name_of(symbol)):
                continue
            # ★ 不要直接 `api.get_quote(ag2701)`：不存在的合约会让 TqSdk
            #   在 `wait_update` 里抛 GraphQL 错误，连累整个行情泵 ✗。
            #   改为先查合约清单（本地 symbols / query_quotes 缓存）。
            exchange = symbol.split('.')[0].upper() if '.' in symbol else ''
            known = known_by_exchange.get(exchange)
            if known is None:
                try:
                    names = (feed.contracts_local('FUT', exchange)
                             or feed.contracts('FUT', exchange) or [])
                except Exception:                            # noqa: BLE001
                    names = []
                known = {str(item) for item in names}
                known_by_exchange[exchange] = known
            # ★ 第一次找不到 → 强制重取一次（用户明确要求）；仍没有才报错 ✓
            if (not known or symbol not in known) and exchange not in refreshed:
                refreshed.add(exchange)
                known = self._refresh_futures_contracts(feed, exchange)
                known_by_exchange[exchange] = known
            if not known:
                bad.append({'symbol': symbol,
                            'reason': '天勤合约清单尚未加载，请稍后重试'
                                       '（已自动重取一次）'})
                continue
            if symbol not in known:
                bad.append({'symbol': symbol,
                            'reason': '天勤合约列表里没有这个合约'
                                       '（已重取一次；可能已下市 / 代码过期）'})
                continue
            name = str(feed.name_of(symbol) or '')
            if not name:
                # 名称不是必填；报价里会补，但这里不订阅不存在的合约 ✓
                pass
        return bad

    def _prepare_realtime_strategy(self, symbol: str, info: dict,
                                   path: str, cls, cycle: int) -> dict:
        """实时图表：按策略需要**自动选布局 + 选合约 + 载入 K 线** ✓

        返回 ``{ok, frame, frames, symbol, error, detail}``，真正运行策略仍由
        调用方做（这里只准备数据 / 界面）。
        """
        from .strategy_plan import analyze as _analyze
        plan = _analyze(path)
        contracts = [str(item) for item in (plan.get('contracts') or [])
                     if str(item)]
        # ★ 一个文件里多个策略（08_live_multi）时，plan 会把整个文件的合约
        #   都算进来；优先用**当前策略类 params 里的 symbol/leg_* ✓**
        explicit: List[str] = []
        try:
            params = getattr(cls, 'params', None) or {}
            for key in ('symbol', 'contract', 'code', 'instrument',
                        'instrument_id', 'leg_a', 'leg_b'):
                try:
                    value = (params.get(key) if hasattr(params, 'get')
                             else getattr(params, key, None))
                except Exception:                            # noqa: BLE001
                    value = None
                if isinstance(value, str) and value and value not in explicit:
                    explicit.append(value)
        except Exception:                                    # noqa: BLE001
            explicit = []
        if explicit:
            contracts = explicit
        if not contracts:
            # test_3 这种 `klines1/2`：没有明确合约名 → 用现有布局 / tab ✓
            frames = self._strategy_frames_for_chart(symbol, info, cls, path)
            need = max(1, int(plan.get('klines') or 1))
            try:
                from .strategy_runner import _same_contract
                distinct: List[str] = []
                for name, _frame in frames:
                    if not any(_same_contract(str(name), item)
                               for item in distinct):
                        distinct.append(str(name))
            except Exception:                                # noqa: BLE001
                distinct = [str(name) for name, _frame in frames]
            if len(distinct) < need:
                return {'ok': False,
                        'error': f'策略使用 klines1..klines{need} 写法（没有 '
                                 'get_kline 合约名）→ 必须先在图表里选好布局并'
                                 f'加载 {need} 个不同合约，再加策略；当前只有 '
                                 f'{len(distinct)} 个不同合约。'}
            return {'ok': True, 'frame': frames[0][1], 'frames': frames,
                    'symbol': str(frames[0][0] or symbol), 'contracts': [
                        str(name) for name, _frame in frames]}
        if len(contracts) > 4:
            return {'ok': False,
                    'error': f'策略需要 {len(contracts)} 个合约；自动布局'
                             '目前最多支持 4 个，请先手动打开对应图表。'}
        resolved = [self._resolve_realtime_contract(item, info)
                    for item in contracts]
        bad = self._validate_realtime_contracts(resolved)
        if bad:
            detail = chr(10).join(
                f'{item["symbol"]}：{item["reason"]}' for item in bad)
            return {'ok': False, 'error': '策略里的合约在天勤报价中找不到',
                    'detail': detail}
        # ★ 布局决策：策略合约数 **≤ 现有格数 → 保持当前布局**（多余格不关 ✓，
        #   用户可以继续在那些格看别的合约）；> 现有格数 才自动加格。
        layout_now = dict(info.get('layout') or {})
        current_symbols = [str(item or '') for item in
                           (layout_now.get('symbols') or [])]
        current_cells = [dict(item) if isinstance(item, dict) else {}
                         for item in (layout_now.get('cells') or [])]
        placements: List[tuple] = []          # (格号, 合约)
        push_layout = False
        if current_symbols and len(resolved) <= len(current_symbols):
            from .strategy_runner import _same_contract as _same
            symbols = list(current_symbols)
            used = set()
            for name in resolved:
                index = None
                for i, existing in enumerate(symbols):
                    if i in used:
                        continue
                    try:
                        hit = bool(existing) and _same(existing, name)
                    except Exception:                        # noqa: BLE001
                        hit = existing == name
                    if hit:
                        index = i
                        break
                if index is None:
                    for i in range(len(symbols)):
                        if i not in used:
                            index = i
                            break
                used.add(index)
                if symbols[index] != name:
                    symbols[index] = name
                    push_layout = True
                placements.append((index, name))
            if push_layout:
                for index, name in placements:
                    while len(current_cells) <= index:
                        current_cells.append({'symbol': '', 'indicators': []})
                    base = dict(current_cells[index])
                    base['symbol'] = name
                    base['indicators'] = []       # 换合约 → 清旧指标 ✓
                    current_cells[index] = base
                info['layout'] = {
                    'cols': max(1, int(layout_now.get('cols') or 1)),
                    'rows': max(1, int(layout_now.get('rows') or 1)),
                    'symbols': symbols, 'cells': current_cells,
                    'key': str(layout_now.get('key') or ''),
                }
                first = current_cells[0] if current_cells else {}
                info['indicators'] = list(first.get('indicators') or [])
                self.push({'type': 'layout', 'symbol': symbol,
                           'count': len(symbols),
                           'key': str(layout_now.get('key') or ''),
                           'cols': max(1, int(layout_now.get('cols') or 1)),
                           'rows': max(1, int(layout_now.get('rows') or 1)),
                           'symbols': symbols})
        else:
            key, cols, rows = self._layout_for_count(len(resolved))
            if current_symbols != list(resolved):
                cells = []
                for index, name in enumerate(resolved):
                    base = (dict(current_cells[index])
                            if index < len(current_cells) else {})
                    base['symbol'] = name
                    base['indicators'] = []   # 新合约 → 清掉旧指标 ✓
                    cells.append(base)
                info['layout'] = {'cols': cols, 'rows': rows,
                                  'symbols': list(resolved), 'cells': cells,
                                  'key': key}
                info['indicators'] = []
                push_layout = True
                # ① 切布局（前端 applyLayout 选左/右两张之类 ✓）
                self.push({'type': 'layout', 'symbol': symbol,
                           'count': len(resolved), 'key': key,
                           'cols': cols, 'rows': rows,
                           'symbols': list(resolved)})
            placements = list(enumerate(resolved))

        # 先取全部 K 线（取不到就不要改布局，避免只改一半 ✗）
        frames: List[Any] = []
        for _index, name in placements:
            frame = self._strategy_frame(name, info, cycle)
            if frame is None:
                return {'ok': False,
                        'error': f'取不到合约 {name} 的 K 线（检查行情连接）'}
            frames.append((name, frame))
        info.pop('_strat_frame_cache', None)
        info['_strat_stamp'] = None
        # ② 每格自己的 K 线（`patch.symbol` 用**主 tab**，`cell` 定格子 ✓）
        for (index, name), (_label, frame) in zip(placements, frames):
            bars = _protocol.bars_from_frame(frame)
            if not bars:
                continue
            payload = _protocol.patch_kline(symbol, bars, True)
            payload['cell'] = index
            self.push(payload)
            # ★ 策略初始化时已有持仓 → 立刻把持仓线推上去（不等下一拍）✓
            try:
                feed = pick_feed(self.feeds, name) or self.current_feed()
                position = self.position_payload(name, feed)
                position['symbol'] = symbol
                position['cell'] = index
                self.push(position)
            except Exception:                                # noqa: BLE001
                pass
        self.last_symbol = resolved[0]
        self.push_log(
            f'策略需要 {len(resolved)} 个合约 → '
            + ('布局已匹配，直接加载合约：' if not push_layout
               else '在当前布局里加载合约：') + '、'.join(resolved), 'success')
        return {'ok': True, 'frame': frames[0][1], 'frames': frames,
                'symbol': resolved[0], 'contracts': resolved,
                'cells': [index for index, _name in placements]}

    def _run_realtime_strategy_job(self, job: int, symbol: str, path: str,
                                   cls, prepared: dict, frames, live,
                                   api, account, fetch, cycle: int,
                                   payload=None) -> None:
        """**后台线程**：跑一遍策略（只计算；结果交回主线程应用 ✓）"""
        from . import strategy_overlay as _overlay
        started = time.monotonic()
        try:
            result = _overlay.run_overlay(
                prepared.get('frame'), cls,
                str(prepared.get('symbol') or symbol), int(cycle or 60),
                live=live, api=api, account=account,
                frames=frames or None, fetch_frame=fetch)
        except Exception as error:                               # noqa: BLE001
            result = {'ok': False, 'items': [],
                      'error': f'{type(error).__name__}: {error}'}
        try:
            self._strategy_results.append({
                'job': int(job), 'symbol': symbol, 'path': path, 'cls': cls,
                'prepared': prepared, 'result': result, 'live': live,
                'payload': dict(payload or {}),
                'cost': time.monotonic() - started,
            })
        finally:
            self._heavy_jobs = max(0, int(getattr(self, '_heavy_jobs', 0)) - 1)

    def wait_strategy_results(self, timeout: float = 60.0) -> bool:
        """等后台策略算完并应用（**测试 / 脚本用**；界面走 tick 自动应用 ✓）"""
        deadline = time.monotonic() + max(0.5, float(timeout))
        while time.monotonic() < deadline:
            self._drain_strategy_results()
            if not int(getattr(self, '_heavy_jobs', 0))                     and not getattr(self, '_strategy_results', None):
                time.sleep(0.02)
                self._drain_strategy_results()
                if not int(getattr(self, '_heavy_jobs', 0)):
                    return True
            time.sleep(0.02)
        return False

    def _drain_strategy_results(self) -> None:
        """主线程：把后台算好的策略结果应用上去（写 tab / 推补丁）✓"""
        pending = list(getattr(self, '_strategy_results', []) or [])
        if not pending:
            return
        self._strategy_results.clear()
        for item in pending:
            info = self.tabs.get(item.get('symbol')) or {}
            # 期间又加了别的策略 / 删掉了 → 这份结果作废 ✓
            if int(info.get('_strat_job') or 0) != int(item.get('job') or 0):
                continue
            try:
                self._apply_realtime_strategy_result(item)
            except Exception as error:                           # noqa: BLE001
                self.push_log(f'策略结果应用失败：{error!r}', 'error')

    def _apply_realtime_strategy_result(self, item: dict) -> None:
        """应用后台策略结果：重试 / 报错弹窗 / 成功上图 ✓（主线程）"""
        from . import strategy_overlay as _overlay
        symbol_of = str(item.get('symbol') or '')
        path = str(item.get('path') or '')
        cls = item.get('cls')
        prepared = dict(item.get('prepared') or {})
        result = dict(item.get('result') or {})
        live = bool(item.get('live'))
        payload = dict(item.get('payload') or {})
        info = self.tabs.setdefault(symbol_of, {})
        cost = float(item.get('cost') or 0.0)
        if cost >= 1.0:
            self.push_log(f'[性能] 策略计算 {cost:.2f}s', 'info')
        if not result.get('ok') and                         '没有产生可画的指标线' in str(result.get('error') or ''):
            self.push_log('策略首次计算没有产出，自动重试一次…', 'warning')
            try:
                result = _overlay.run_overlay(
                    prepared.get('frame'), cls,
                    str(prepared.get('symbol') or symbol_of), 60,
                    live=live, api=None, account=None,
                    frames=prepared.get('frames') or None,
                    fetch_frame=None)
            except Exception as error:                           # noqa: BLE001
                result = {'ok': False, 'items': [],
                          'error': f'{type(error).__name__}: {error}'}
        if not result.get('ok'):
            raw_error = str(result.get('error') or '')
            attempts = int(payload.get('_retry') or 0)
            frames_for_check = prepared.get('frames') or []
            too_short = any(
                (len(entry[1]) < 60 or _protocol.valid_bars(entry[1]) < 60)
                for entry in frames_for_check
                if isinstance(entry, tuple) and len(entry) > 1)
            if (attempts < 2 and raw_error
                    and '没有产生可画的指标线' in raw_error
                    and too_short):
                retry_payload = dict(payload or {})
                retry_payload['_retry'] = attempts + 1
                self._strategy_retries.append({
                    'at': time.monotonic() + 2.0,
                    'payload': retry_payload,
                })
                self.push_log(
                    f'策略 {getattr(cls, "__name__", "")} 的 K 线历史还没到齐，'
                    '2 秒后自动重试…', 'info')
                return
            message = f'策略 {getattr(cls, "__name__", "")} 加到图表失败：{raw_error}'
            self.push_log(message, 'error')
            none_type = ('NoneType' in raw_error and 'attribute' in raw_error)
            if none_type:
                self.push_alert(
                    '策略缺少K线数据（数据不够）',
                    '策略初始化失败：某个 `klinesN` 是 None（第 N 组 K 线不存在）',
                    detail='请先用「布局」打开对应数量的图表并加载合约'
                           '（实时图表可多格 / 多 tab；本地图表加载 CSV），'
                           '或删掉策略里用不到的 klinesN。',
                    level='error')
            else:
                self.push_alert('策略加到图表失败', raw_error,
                                detail=os.path.basename(path),
                                level='error')
            return
        # ★ 策略只保留 1 个（换策略 = 替换），指标**不动** ✓
        info['strategy_items'] = list(result['items'])
        info['strategy'] = {'name': result.get('name')
                            or getattr(cls, '__name__', '策略'),
                            'path': path}
        info['strategy_runner'] = result.get('runner')
        info['strategy_groups'] = dict(result.get('groups') or {})
        info['strategy_contracts'] = [
            str(entry) for entry in (prepared.get('contracts') or [])]
        info.pop('_strat_bar', None)
        info.pop('_strat_idle', None)
        contracts_text = '、'.join(
            str(entry) for entry in (prepared.get('contracts') or []))
        self.push_log(
            f'已把策略 {info["strategy"]["name"]} 加到图表 {symbol_of}'
            f'（{"天勤实盘/模拟" if live else "本地/回测"}）：'
            f'{len(result["items"])} 条线'
            + (f'；合约：{contracts_text}' if contracts_text else ''),
            'success')
        self.push(_protocol.patch_toast(
            f'已加策略：{info["strategy"]["name"]}', 'success'))
        self.push(self.indicator_payload(symbol_of))

    def _add_strategy_to_chart(self, symbol: str, path: str, frame,
                               cycle: int = 60, cls_name: str = '') -> bool:
        """把策略文件跑一遍并挂到**当前图表**（实时图表可 live 下单）。

        用于「加到图表」以及**切换合约后重新添加策略**。返回是否成功。
        """
        from . import personal as _pi
        from . import strategy_overlay as _overlay
        if not path or not os.path.isfile(path):
            return False
        module = _pi._import_file(path)
        if module is None:
            return False
        strategies = _overlay.classes_of(module).get('strategy') or []
        if not strategies:
            return False
        info = self.tabs.setdefault(symbol, {})
        wanted = str(cls_name or (info.get('strategy') or {}).get('name')
                     or '')
        cls = _pick_strategy_class(strategies, wanted)
        live, api, account = self._strategy_live_context(cls)
        # ★ 自动流程：按策略需要选布局 / 选合约 / 载入 K 线（本地名也按
        #   品种对到真实合约）→ 然后再运行策略 ✓
        prepared = self._prepare_realtime_strategy(
            symbol, info, path, cls, cycle)
        if not prepared.get('ok'):
            self.push_log(f'策略 {cls.__name__} 加到图表失败：'
                          f'{prepared.get("error")}', 'error')
            if prepared.get('detail'):
                self.push_alert('策略合约无法加载',
                                str(prepared.get('error')),
                                detail=str(prepared.get('detail')),
                                level='warning')
            return False
        frames = prepared.get('frames') or []
        fetch = self._fetch_strategy_frame(info, cycle) if live else None
        result = _overlay.run_overlay(
            prepared.get('frame'), cls, str(prepared.get('symbol') or symbol),
            cycle, live=live, api=api, account=account,
            frames=frames or None, fetch_frame=fetch)
        if not result.get('ok') and                 '没有产生可画的指标线' in str(result.get('error') or ''):
            # 首次切布局 / K 线缓存刚灌入时偶尔取到的是空帧 → 重试一次 ✓
            self.push_log('策略首次计算没有产出，自动重试一次…', 'warning')
            result = _overlay.run_overlay(
                prepared.get('frame'), cls,
                str(prepared.get('symbol') or symbol), cycle,
                live=live, api=api, account=account,
                frames=frames or None, fetch_frame=fetch)
        if not result.get('ok'):
            self.push_log(
                f'策略 {cls.__name__} 加到图表失败：{result.get("error")}',
                'error')
            return False
        info['strategy_items'] = list(result['items'])
        info['strategy'] = {'name': result.get('name') or cls.__name__,
                            'path': path}
        info['strategy_runner'] = result.get('runner')
        info['strategy_groups'] = dict(result.get('groups') or {})
        info['strategy_contracts'] = [
            str(item) for item in (prepared.get('contracts') or [])]
        # 新策略 → 行情指纹作废，下一拍一定重算一次 ✓
        info.pop('_strat_bar', None)
        info.pop('_strat_idle', None)
        self.push_log(
            f'已把策略 {info["strategy"]["name"]} 加到图表：'
            f'{len(result["items"])} 条线', 'success')
        return True

    def _on_switch_symbol(self, payload) -> None:
        """看盘 tab 换合约（K 线 / 报价 / 持仓 / 账户 / 指标 全部重来 ✓）

        多布局（`payload['cell']` + 该 tab 有 2 格以上）→ **只换那一格**，
        其余格的合约 / 指标 / 策略都不动（商品搜索、键盘精灵用 ✓）。

        切换合约时**先撤掉旧策略**（包括 old runner / strategy_items），
        如果旧策略有文件路径，再按新合约重新跑一遍并挂上 ✓
        """
        old = str(payload.get('from') or '')
        new = str(payload.get('to') or '')
        if not new:
            return
        # ★ 多布局：只切某一格（用户实测：以前会把所有格子都换掉 ✗）
        cell_raw = payload.get('cell')
        cell = None
        if cell_raw is not None and not isinstance(cell_raw, bool):
            try:
                cell = int(cell_raw)
            except (TypeError, ValueError):
                cell = None
        if cell is not None and old:
            # ★ 以**前端**为准：`cells` = 当前每格显示的合约（工具栏切的布局
            #   后端可能还不知道！只看 `tabs[old]['layout']` 会退回整页重开 ✗）
            given = [str(item or '') for item in (payload.get('cells') or [])]
            stored = [str(item or '') for item in
                      (((self.tabs.get(old) or {}).get('layout') or {})
                       .get('symbols') or [])]
            symbols = given or stored
            multi = bool(payload.get('multi')) or len(symbols) > 1
            if multi and (cell >= 0):
                self._switch_layout_cell(
                    old, new, cell, str(payload.get('name') or ''),
                    symbols=symbols,
                    cols=int(payload.get('cols') or 0) or None)
                return
        info = dict(self.tabs.pop(old, {}) if old else {})
        # ★ 切换的是「合约 + 该合约的指标 + 该合约的策略」：
        #   旧合约的一切都不要带过去（否则旧线 / 旧 runner 还在跑，图表会闪、
        #   出现旧价位的 K 线 / 成交量 ✗）
        info.pop('strategy_items', None)
        info.pop('strategy', None)
        info.pop('strategy_runner', None)
        info.pop('strategy_config', None)
        info.pop('_strat_stamp', None)
        info.pop('_strat_at', None)
        info['indicators'] = []
        info.pop('layout', None)
        info.pop('_layout', None)
        info.pop('_kline_time', None)
        info.pop('_kline_at', None)
        info.pop('_ind_bar', None)
        info.pop('_ind_at', None)
        info.pop('_ind_sig', None)
        info.pop('_ind_gen', None)
        info.pop('_book_stamp', None)
        if old:
            self.replay_symbols.discard(old)
        feed = pick_feed(self.feeds, new) or self.current_feed()
        cycle = int(info.get('cycle') or (86400 if _is_stock(new) else 60))
        info.update({'feed': feed, 'cycle': cycle})
        self.tabs[new] = info
        self.last_symbol = new
        name = str(payload.get('name') or '') or (
            feed.name_of(new) if feed is not None else '')
        self.push({'type': 'switch_symbol', 'old': old, 'new': new,
                   'name': name, 'cycle': cycle})
        self.push_log(f'切换合约 → {new} {name}'.strip(), 'info')
        frame = feed.klines(new, cycle,
                            self.tab_length(info)) if feed is not None else None
        self.push(_protocol.patch_kline(new,
                                        _protocol.bars_from_frame(frame), True))
        self.push(self.book_payload(new, feed))
        self.push(self.position_payload(new, feed))
        # 预警线是全局列表，但前端只画当前合约；切合约后立刻重推一次，
        # 避免旧合约的预警线 / 左侧价格块残留 ✓
        self._on_alerts({'symbol': new})
        self.push(self.account_payload(symbol=next(iter(self.tabs), '')))
        self.push(self.indicator_payload(new))

    def _on_layout_sync(self, payload=None) -> None:
        """前端切了布局（工具栏「布局」/ 关闭某一格）→ 后端记住每格合约 ✓

        以前布局只在前端生效（`chart-page.setLayoutSpec()` 纯本地）→ 后端
        `info['layout']` 还是**单格**，于是：
        * 第 2..N 格拿不到自己的 K 线 / 持仓线 / 挂单线（`_push_cell_bars`
          按 `layout.symbols` 推）→ 第 2 格显示的是**第 1 格复制过来的**数据
          （用户看到「两个图都是同一个合约、只有 2 根 K 线」✗）；
        * 商品搜索 / 键盘精灵切合约会退化成整页重开（所有格一起换 ✗）。

        这里把 `cols / rows / symbols` 存进 `info['layout']`，并立刻给
        第 2..N 格补一次全量 K 线（持仓 / 挂单由节拍器下一拍补 ✓）。
        """
        payload = payload or {}
        tab = self._resolve_tab_symbol(str(payload.get('symbol') or ''))
        info = self.tabs.get(tab)
        if not info:
            return
        symbols = [str(item or '') for item in (payload.get('symbols') or [])]
        if not symbols:
            return
        cols = max(1, int(payload.get('cols') or 1))
        rows = max(1, int(payload.get('rows') or 1))
        old_layout = dict(info.get('layout') or {})
        old_cells = [dict(item) if isinstance(item, dict) else {}
                     for item in (old_layout.get('cells') or [])]
        cells = []
        for index, symbol in enumerate(symbols):
            base = dict(old_cells[index]) if index < len(old_cells) else {}
            if str(base.get('symbol') or '') != symbol:
                # 合约变了 → 该格指标 / 策略作废（换合约不保留旧线 ✓）
                base['indicators'] = []
                base.pop('strategy', None)
                base.pop('strategy_items', None)
            base['symbol'] = symbol
            cells.append(base)
        info['layout'] = {'cols': cols, 'rows': rows,
                          'symbols': symbols, 'cells': cells}
        self.tabs[tab] = info
        # 第 2..N 格立刻补一次全量 K 线（否则前端会把第 1 格的数据复制过去，
        # 看起来「两个图同一个合约、只有 2 根」✗）
        if len(symbols) <= 1:
            return
        cycle = int(info.get('cycle') or 60)
        for index, symbol in enumerate(symbols[1:], start=1):
            if not symbol:
                continue
            feed = pick_feed(self.feeds, symbol) or self.current_feed()
            frame = (feed.klines(symbol, cycle, self.tab_length(info))
                     if feed is not None else None)
            bars = _protocol.bars_from_frame(frame) if frame is not None else []
            if bars:
                self.push(dict(_protocol.patch_kline(tab, bars, True),
                               cell=index))
        # ★ 换布局后前端把每一格都重建了 → 指标 / 策略线按新格子重推 ✓
        #   （以前不推 → 换完布局策略线全没了 / 两格变成同一个合约 ✗）
        self._push_cell_indicators(tab, info)
        if info.get('strategy') or info.get('strategy_items'):
            self.push(self.indicator_payload(tab))
            self._push_strategy_cells(tab, info)

    def _switch_layout_cell(self, tab: str, new: str, cell: int,
                            name: str = '', symbols=None,
                            cols=None) -> None:
        """多布局：只把**第 `cell` 格**换成 `new`（其余格原样 ✓）

        商品搜索 / 键盘精灵在多图布局里换合约时走这里：只清这一格的
        指标 / 策略、只推这一格的 K 线 / 持仓线 / 挂单线，tab 名不变 ✓

        ``symbols`` = 前端报的**每格合约**（工具栏切的布局后端可能不知道，
        以它为准并补登记一份 `layout` ✓）。
        """
        info = dict(self.tabs.get(tab) or {})
        layout = dict(info.get('layout') or {})
        stored = [str(item or '') for item in (layout.get('symbols') or [])]
        symbols = [str(item or '') for item in (symbols or [])] or stored
        # 前端报的格子数可能比后端记的多（手动切布局）→ 用 tab 名补齐 ✓
        while len(symbols) <= cell:
            symbols.append(stored[len(symbols)]
                           if len(symbols) < len(stored) else new)
        if cell < 0 or cell >= len(symbols):
            return
        prev = symbols[cell]
        if new == prev:
            return
        if cols:
            layout['cols'] = max(1, int(cols))
            layout['rows'] = max(1, int(round(len(symbols) / layout['cols'])))
        symbols[cell] = new
        raw_cells = layout.get('cells') or []
        cells = [dict(item) if isinstance(item, dict) else {}
                 for item in raw_cells]
        while len(cells) < len(symbols):
            index = len(cells)
            cells.append({'symbol': symbols[index]})
        cell_info = dict(cells[cell])
        cell_info['symbol'] = new
        cell_info['indicators'] = []
        cell_info.pop('strategy', None)
        cell_info.pop('strategy_items', None)
        cells[cell] = cell_info
        layout['symbols'] = symbols
        layout['cells'] = cells
        info['layout'] = layout
        # 第 1 格 = tab 的主合约 → tab 级指标 / 策略也属于它，一起清掉
        if cell == 0:
            info['indicators'] = []
            for key in ('strategy_items', 'strategy', 'strategy_runner',
                        'strategy_config', '_strat_stamp', '_strat_at',
                        '_kline_time', '_kline_at', '_kline_bars_len',
                        '_kline_first_time', '_ind_bar', '_ind_at',
                        '_ind_sig', '_ind_gen', '_book_stamp'):
                info.pop(key, None)
            if prev:
                self.replay_symbols.discard(prev)
        self.tabs[tab] = info
        feed = pick_feed(self.feeds, new) or self.current_feed()
        cycle = int(info.get('cycle') or (86400 if _is_stock(new) else 60))
        name = name or (feed.name_of(new) if feed is not None else '')
        # ① 前端：只更新这一格的标题 / 合约（tab 名不变 ✓）
        self.push({'type': 'switch_symbol', 'old': tab, 'new': new,
                   'name': name, 'cell': int(cell), 'multi': True})
        # ② 这一格的 K 线 / 持仓线 / 挂单线 / 指标（空 → 清掉旧线 ✓）
        frame = (feed.klines(new, cycle, self.tab_length(info))
                 if feed is not None else None)
        bars = _protocol.bars_from_frame(frame) if frame is not None else []
        if bars:
            self.push(dict(_protocol.patch_kline(tab, bars, True), cell=cell))
        try:
            self.push(dict(self.position_payload(new, feed),
                           symbol=tab, cell=cell))
        except Exception:                                        # noqa: BLE001
            pass
        if tab not in getattr(self, 'replay_symbols', set()):
            try:
                self.push(dict(self.orders_payload(new),
                               symbol=tab, cell=cell))
            except Exception:                                    # noqa: BLE001
                pass
        self.push({'type': 'indicator', 'symbol': tab, 'cell': int(cell),
                   'items': []})
        # ③ 第 1 格：报价面板 / 账户 / 预警按新合约刷
        if cell == 0:
            self.push(self.book_payload(new, feed))
            self.push(self.account_payload(symbol=tab))
            self._on_alerts({'symbol': new})
        self.push_log(
            f'切换格 {cell + 1} 合约 → {new} {name}'.strip(), 'info')

    # -------------------------------------------------------- 预警
    def _on_alerts(self, payload) -> None:
        """前端要预警列表（打开 tab / 对话框时 ✓）"""
        self.push({'type': 'alerts', 'symbol': str(payload.get('symbol') or ''),
                   'items': [self._alert_view(item) for item in self.alerts]})

    def _alert_view(self, alert: dict) -> dict:
        symbol = str(alert.get('symbol') or '')
        return {'id': alert.get('id'), 'symbol': symbol,
                'price': alert.get('price'), 'action': alert.get('action'),
                'qty': alert.get('qty'), 'message': alert.get('message'),
                'cross': alert.get('cross'), 'fired': alert.get('fired'),
                'line': alert.get('line', True),
                'decimals': self.decimals_of(symbol),
                'expires_at': alert.get('expires_at')}

    def _on_add_alert(self, payload) -> None:
        """加一条价格预警（方向 / 到期 / 消息 / 动作 / 手数 都存 ✓）"""
        symbol = str(payload.get('symbol') or '')
        price = payload.get('price')
        try:
            price = float(price)
        except (TypeError, ValueError):
            self.push(_protocol.patch_toast('预警价格不合法', 'warning'))
            return
        if not symbol or price <= 0:
            return
        action_map = {'买': 'buy', '卖': 'sell', '平': 'close',
                      'buy': 'buy', 'sell': 'sell', 'close': 'close'}
        action = action_map.get(str(payload.get('action') or '无操作'),
                                'none')
        try:
            expire = int(payload.get('expire') or 0)
        except (TypeError, ValueError):
            expire = 0
        self._alert_seq += 1
        alert = {
            'id': self._alert_seq, 'symbol': symbol, 'price': price,
            'cross': str(payload.get('cross') or '穿过'),
            'action': action, 'qty': int(payload.get('qty') or 1),
            'message': str(payload.get('message') or ''),
            'line': bool(payload.get('line', True)),
            'fired': False,
            'expires_at': (time.time() + expire) if expire else None,
            'prev': None,
        }
        self.alerts.append(alert)
        self.push_log(f'[预警] {symbol} {alert["cross"]} {price}'
                      f'（{alert["action"]} {alert["qty"]} 手）', 'info')
        self.push({'type': 'alerts', 'symbol': symbol,
                   'items': [self._alert_view(item) for item in self.alerts]})
        self.push(_protocol.patch_toast(
            f'已加预警：{symbol} {alert["cross"]} {price}', 'success'))

    def _on_drop_alert(self, payload) -> None:
        alert_id = payload.get('id')
        self.alerts = [item for item in self.alerts
                       if item.get('id') != alert_id]
        self.push({'type': 'alerts',
                   'items': [self._alert_view(item) for item in self.alerts]})

    def _on_clear_alerts(self, payload=None) -> None:
        """右键「清除预警」：清空该 desk 的全部预警 ✓"""
        self.alerts = []
        self.push({'type': 'alerts', 'items': []})
        self.push_log('已清除全部价格预警', 'info')

    def check_alerts(self) -> None:
        """每拍检查：按**方向**（穿过/上穿/下穿）+ **到期** 判断 ✓"""
        if not self.alerts:
            return
        now = time.time()
        for alert in self.alerts:
            if alert.get('fired'):
                continue
            expires_at = alert.get('expires_at')
            if expires_at and now >= float(expires_at):
                alert['fired'] = True
                alert['expired'] = True
                self.push_log(f'[预警] {alert["symbol"]} 预警已过期', 'info')
                continue
            symbol = alert['symbol']
            feed = pick_feed(self.feeds, symbol) or self.current_feed()
            spec = getattr(feed, 'spec', None) if feed is not None else None
            quote = spec(symbol) if callable(spec) else None
            last = _num_local(getattr(quote, 'last_price', None)) \
                if quote is not None else None
            if last is None:
                continue
            price = float(alert['price'])
            prev = alert.get('prev')
            alert['prev'] = last
            if not _alert_crossed(alert.get('cross') or '穿过', prev, last,
                                  price):
                continue
            alert['fired'] = True
            self.push_log(f'[预警] {symbol} 到价 {alert["price"]}'
                          f'（最新 {last}）', 'warning')
            self.push({'type': 'alert_fired', 'id': alert['id'],
                       'symbol': symbol, 'price': alert['price'],
                       'last': last, 'action': alert.get('action') or 'buy',
                       'decimals': self.decimals_of(symbol),
                       'qty': int(alert.get('qty') or 1)})
        self.push({'type': 'alerts',
                   'items': [self._alert_view(item) for item in self.alerts]})

    # -------------------------------------------------------- 个人指标
    # -------------------------------------------------------- 代码编辑器
    # -------------------------------------------------------- 资源管理器
    def explorer_root(self) -> str:
        """当前资源管理器根目录（存 `settings.explorer_root` ✓）"""
        from . import explorer as _fs
        from . import user_prefs as _prefs
        stored = str(_prefs.settings().get('explorer_root') or '')
        return _fs.root_of(stored)

    def _push_explorer(self, path: str = '') -> None:
        from . import explorer as _fs
        root = self.explorer_root()
        data = _fs.entries(path or root, root)
        self.push({'type': 'explorer', **data})

    def _on_explorer_list(self, payload=None) -> None:
        self._push_explorer(str((payload or {}).get('path') or ''))

    def _on_explorer_pick(self, payload=None) -> None:
        """选文件夹作为新的根目录（Qt 弹原生对话框；浏览器壳 → 提示 ✓）"""
        from . import user_prefs as _prefs
        path = self.choose_directory('选择要打开的文件夹')
        if not path:
            self.push_log('已取消选择目录', 'info')
            return
        _prefs.set_setting('explorer_root', path)
        self.push_log(f'资源管理器根目录 → {path}', 'info')
        self.push(_protocol.patch_toast(f'已切换到：{path}', 'success'))
        self._push_explorer(path)

    def _on_explorer_system_dir(self, payload=None) -> None:
        """「系统目录 ▾」→ 个人指标 / 策略目录，或它们的**根目录** ✓

        ``kind``：``indicator``（默认）/ ``strategy`` / ``all``
        —— ``all`` 打开 ``~/.minibt/personal``，指标和策略两个子目录一起看 ✓
        """
        from . import personal as _pi
        from . import user_prefs as _prefs
        raw = str((payload or {}).get('kind') or '').strip().lower()
        kind = raw if raw in ('indicator', 'strategy', 'all') else 'indicator'
        dirs = _pi.ensure_directories()          # 两个子目录都建好（幂等 ✓）
        if kind == 'all':
            path = _pi.PERSONAL_ROOT
            try:
                os.makedirs(path, exist_ok=True)
            except OSError:
                path = ''
        else:
            path = dirs.get(kind) or ''
        if not path:
            self.push(_protocol.patch_toast('系统目录创建失败', 'error'))
            return
        _prefs.set_setting('explorer_root', path)
        self.push_log(f'资源管理器 → {path}', 'info')
        self._push_explorer(path)

    def _on_explorer_set_root(self, payload=None) -> None:
        """按路径指定根目录（**命令行 / 脚本调用**用；界面一律系统对话框 ✓）"""
        from . import user_prefs as _prefs
        path = str((payload or {}).get('path') or '').strip()
        if not path:
            return
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(path):
            self.push(_protocol.patch_toast(f'目录不存在：{path}', 'warning'))
            return
        _prefs.set_setting('explorer_root', path)
        self.push_log(f'资源管理器 → {path}', 'info')
        self._push_explorer(path)

    def _on_explorer_op(self, payload=None) -> None:
        """右键操作：new_file / new_folder / rename / delete / copy / cut / paste"""
        from . import explorer as _fs
        payload = payload or {}
        root = self.explorer_root()
        result = _fs.operate(str(payload.get('action') or ''),
                             payload, root)
        if not result.get('ok'):
            self.push(_protocol.patch_toast(
                str(result.get('error') or '操作失败'), 'warning'))
        else:
            self.push_log(f'[资源管理器] {payload.get("action")} → '
                          f'{result.get("path") or ""}', 'info')
            if payload.get('action') in ('delete', 'rename', 'paste'):
                self._on_editor_list({})
                self._refresh_personal()
        self.push({'type': 'explorer_op', 'action': str(payload.get('action')),
                   'result': result})
        self._push_explorer(str(payload.get('refresh')
                                or os.path.dirname(
                                    str(result.get('path')
                                        or payload.get('path') or ''))
                                or root))

    def _on_explorer_check_personal(self, payload=None) -> None:
        """当前目录是不是「我的脚本 / 我的策略」→ 告诉前端按钮是否可用 ✓"""
        from . import explorer as _fs
        path = str((payload or {}).get('path') or '') or self.explorer_root()
        kind = _fs.is_personal(path) or ''
        self.push({'type': 'explorer_personal', 'path': path, 'kind': kind})
        if kind:
            self.push_log(f'当前目录是「{"我的脚本" if kind == "indicator" else "我的策略"}」'
                          '（可点「刷新指标策略」）', 'info')

    def _check_strategy_klines_usage(self, path: str, frames,
                                    result=None) -> bool:
        """`self.klines1 … klines9` 的个数必须 ≤ 已加载的图表数 ✓

        * 写法 2 里 `klinesN` 就是"第 N 张图表的数据"；
        * 只开了 2 张图却写 `self.klines3` → 拿到 `None` →
          `'NoneType' object has no attribute 'close'`（报错很难懂 ✗）
        * 这里在「加到图表」时按源码扫描用到的最大编号，超过就**明确提示**：
          要么少开几个 klines，要么再打开几张图表 ✓
        """
        if not path or not os.path.isfile(path):
            return True
        try:
            source = open(path, encoding='utf-8', errors='ignore').read()
        except Exception:                                        # noqa: BLE001
            return True
        import re as _re
        used = sorted({int(match) for match in _re.findall(
            r'klines([1-9])', source)})
        if not used:
            return True
        available = len(frames or [])
        highest = used[-1]
        if highest <= available:
            return True
        names = '、'.join(f'klines{index}' for index in used
                         if index > available)
        chart_text = ('、'.join(item[0] for item in (frames or []))
                      or '（当前没有加载任何图表数据）')
        message = (f'策略要用 {highest} 组 K 线（用到了 {names}），'
                   f'但当前图表只加载了 {available} 个合约：{chart_text}')
        self.push_log(message, 'warning')
        self.push_alert(
            '策略需要的K线数量不够', message,
            detail=f'策略里写了 {names}（第 {highest} 组），'
                   f'可图表只有 {available} 组 → 多出来的 `klinesN` 是 None，'
                   '`.close` 就会报错。' + chr(10) + chr(10)
                   + '两种改法：① 用多布局 / 多 tab 打开缺少的合约'
                     '（本地图表加载 CSV；实时图表分格或开对应合约）；'
                     '② 或者删掉策略里用不到的 klinesN。',
            level='warning')
        return False

    def _check_strategy_data_names(self, runner, result) -> None:
        """策略里 `get_kline(LocalDatas.xxx)` 的 xxx 必须**真的存在** ✓

        为什么要校验：`get_kline` 找不到名字时会**按位置兜底**（拿图表自己的
        数据）→ 指标照样画出来，但用的其实不是那个合约（手误极难发现 ✗）。
        这里在「加到图表」时逐个核对：数据名必须能在
        `本地图表列表（含外部文件夹）/ ~/.minibt/datas / 包内数据` 里找到。
        """
        if runner is None:
            return
        try:
            declared = [str(item[0] or '')
                        for item in (getattr(runner, '_requests', None) or [])]
        except Exception:                                        # noqa: BLE001
            declared = []
        declared = [name for name in declared if name]
        if not declared:
            return
        known = set()
        try:
            known = {str(item.get('name') or '').lower()
                     for item in self.local_store().items()}
        except Exception:                                        # noqa: BLE001
            known = set()
        try:
            from ..data.tools import list_csv_names as _csv_names
            known |= {str(name).lower() for name in _csv_names()}
        except Exception:                                        # noqa: BLE001
            pass
        missing = [name for name in declared if name.lower() not in known]
        if not missing:
            return
        # ★ 说清楚**是"合约对不上"这件事**，并给出图表里已有的合约 +
        #   最接近的正确写法（用户反馈原来的提示看不懂 ✗）
        import difflib
        chart_names = []
        try:
            chart_names = [str(item) for item in
                           (getattr(self, '_local_cell_names', {}) or {}).values()]
        except Exception:                                        # noqa: BLE001
            chart_names = []
        if not chart_names:
            try:
                chart_names = [item[0] for item in (frames or [])]
            except Exception:                                    # noqa: BLE001
                chart_names = []
        candidates = list(known) + chart_names
        hints = []
        for name in missing:
            close = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
            hints.append(f'{name} → 是不是 {close[0]} ？' if close else name)
        declared_text = '、'.join(missing)
        chart_text = ('、'.join(chart_names) or '（当前图表还没有加载合约）')
        message = (f'策略里写的合约「{declared_text}」跟图表加载的合约'
                   f'「{chart_text}」对不上 —— 这几个名字在本地数据里不存在')
        self.push_log(message, 'warning')
        self.push_alert(
            '策略合约与图表合约对不上', message,
            detail='策略里的 ' + '；'.join(hints)
            + chr(10) + chr(10)
            + '两种改法：① 把策略里的名字改成图表加载的那个合约；'
            + '② 或者用本地图表打开策略里写的那个合约。',
            level='warning')

    def _local_frames_for_strategy(self, name: str, cell: int = 0):
        """策略要用的 `[(CSV名, frame), …]`（按**格序**，格 1 在最前 ✓）

        * 只有一格 → 就是它自己；
        * 多布局多合约（配对交易）→ 每格一份，`self.klines1/2/…` 依次对应 ✓
        * 某个格子还没加载数据 → 跳过（不影响其它格）
        """
        store = self.local_store()
        cells = getattr(self, '_local_cell_names', {}) or {}
        order = []
        for index in sorted(cells):
            csv_name = str(cells[index] or '')
            if csv_name and csv_name not in order:
                order.append(csv_name)
        if name and name not in order:
            order.append(name)
        out = []
        for csv_name in order:
            try:
                csv_frame = store.frame(csv_name)
            except Exception:                                    # noqa: BLE001
                csv_frame = None
            if csv_frame is not None and len(csv_frame):
                out.append((csv_name, csv_frame))
        return out or [(name, store.frame(name))]

    def _run_local_strategy_overlay(self, name: str, cell: int, path: str,
                                    cls, frames, job: int,
                                    page: str = '',
                                    contracts=None) -> None:
        """后台跑本地图表策略（`replay` 很重，不能占主线程 ✓）。"""
        from . import strategy_overlay as _overlay
        try:
            with self._local_strategy_worker:
                if self._local_strategy_jobs.get(name) != job:
                    return
                if isinstance(frames, list) and frames:
                    main_frame = frames[0][1]
                    payload_frames = frames
                else:
                    main_frame, payload_frames = frames, [(name, frames)]
                self._pending_strategy_frames = list(payload_frames or [])
                result = _overlay.run_overlay(
                    main_frame, cls, name, 60, replay=True,
                    replay_bars=LOCAL_STRATEGY_REPLAY_BARS,
                    frames=payload_frames)
        except Exception as error:                               # noqa: BLE001
            result = {'ok': False, 'items': [],
                      'error': f'{type(error).__name__}: {error}'}
        # 同一张图又加了新策略 → 丢掉旧结果，避免旧线把新线覆盖 ✓
        if self._local_strategy_jobs.get(name) != job:
            return
        if not result.get('ok'):
            raw_error = str(result.get('error') or '')
            none_type = ('NoneType' in raw_error and 'attribute' in raw_error)
            if none_type:
                raw_error += (
                    ' · 提示：策略里用到的 `self.klinesN` 超出了图表数量'
                    '（多出来的格子没有数据 → None）')
            message = (f'策略 {cls.__name__} 加到图表失败：{raw_error}')
            self.push_log(message, 'error')
            self.push_alert('策略加到图表失败', str(result.get('error')),
                            detail=os.path.basename(path), level='error')
            return
        # ★ 校验策略里写的**数据名**是否存在（`LocalDatas.pp2609_600` 这种
        #   手误也能被 `get_kline` 兜底跑通 → 指标仍会画出来）
        #   这里明确提示，避免"以为在用 pp2609_600" ✗
        self._check_strategy_data_names(result.get('runner'), result)
        # ★ 写法 2（`self.klines1 / klines2 …`）：用到的个数**不能超过**
        #   已加载的图表数，多出来的其实是 `None` → `.close` 会报
        #   `'NoneType' object has no attribute 'close'` ✗
        self._check_strategy_klines_usage(path, frames, result)
        # ★ 一个图表只放**一个策略**（换策略 = 替换 ✓）
        strategy_name = result.get('name') or cls.__name__
        groups = result.get('groups') or {}
        if not groups:
            groups = {name: list(result['items'])}
        # ★ 按「页」存策略：多开本地图表时，两份副本加载同一份 CSV 的
        #   策略也各自独立（以前按 CSV 名存 → 一个页面加策略另一个也跟着有 ✗）
        page_key = self._local_state_key(name, page)
        # 先把这一页的旧分组清掉（同一策略重加 → 不残留旧的第二个合约 ✓）
        for old_key in list(getattr(self, '_local_strategy_of', {})):
            if (old_key == page_key
                    or self._local_strategy_of.get(old_key) == strategy_name
                    and not str(old_key).startswith('local:')):
                self._local_strategies.pop(old_key, None)
        if not hasattr(self, '_local_strategy_of'):
            self._local_strategy_of = {}
        # ★ 回放时要靠 runner 逐步推进 `next()` → 记下来（按策略名 ✓）
        runner = result.get('runner')
        if runner is not None:
            if not hasattr(self, '_local_runners'):
                self._local_runners = {}
            self._local_runners[strategy_name] = {
                'runner': runner, 'orders': 0, 'steps': 0,
                'frames': list(getattr(self, '_pending_strategy_frames', [])
                               or []), 'name': name,
            }
        total = 0
        targets = []
        page_groups: Dict[str, list] = {}
        for source, group in groups.items():
            if not group:
                continue
            target = str(source or name)
            # 名字对不上 CSV（例如策略写了别的合约）→ 落到当前图 ✓
            store_names = {item['name'] for item in self.local_store().items()}
            if target not in store_names:
                target = name
            try:
                self.local_store().set_strategy(
                    target, {'name': strategy_name, 'path': path})
            except Exception:                                # noqa: BLE001
                pass
            page_groups[target] = list(group)
            total += len(group)
            targets.append(target)
        # ★ 一条记录 = 一页（`groups` 里按 CSV 分线，图 / 回放按格取 ✓）
        self._local_strategies[page_key] = {
            'items': [line for group in page_groups.values() for line in group],
            'groups': page_groups,
            'name': strategy_name,
            'path': path,
            'symbol': str(name or ''),
            'page': page,
            # ★ 策略需要的合约（布局菜单：格数 < 这个数就禁用 ✓）
            'contracts': [str(item) for item in (contracts or targets)],
        }
        self._local_strategy_of[page_key] = strategy_name
        # 每个数据名对应的格子（多布局时可能有多格 ✓）
        cells = getattr(self, '_local_cell_names', {}) or {}
        pushed = set()
        # ★ **每一格都要推**（哪怕这一格没有策略线）：
        #   改完代码重加策略时（比如把某条线 `isplot=False`），
        #   只推"有分组"的格子 → 其它格子的旧策略线**删不掉**（用户实测 ✗）
        for cell_index, cell_name in list(cells.items()):
            if cell_index in pushed:
                continue
            pushed.add(cell_index)
            self.push(self._local_indicator_payload(cell_name, cell_index,
                                                    page=page))
        if cell not in pushed:
            self.push(self._local_indicator_payload(name, cell, page=page))
        detail = '、'.join(f'{item}({len(groups.get(item) or [])} 线)'
                          for item in targets)
        # ★ 本地模拟账户已有持仓 → 策略加载后立刻把各格持仓线补上 ✓
        try:
            self._push_all_sim_positions()
        except Exception:                                    # noqa: BLE001
            pass
        self.push_log(
            f'已把策略 {strategy_name} 加到本地图表：{total} 条线'
            f'（{detail}）', 'success')
        self.push(_protocol.patch_toast(
            f'已加策略：{strategy_name}', 'success'))

    def _on_editor_add_indicator(self, payload=None) -> None:
        """按**文件路径**把里面的指标加到图表（类 / 函数都认 ✓）

        分类名取自 `personal` 登记的目录；目录没登记就先登记一次（这样
        「打开任意文件夹 → 加指标」也能用 ✓）。
        """
        from . import personal as _pi
        path = str((payload or {}).get('path') or '')
        if not path or not os.path.isfile(path):
            self.push(_protocol.patch_toast('文件不存在', 'warning'))
            return
        folder = os.path.dirname(path)
        # ★ 「只读叠加」：策略只算线、不交易（本地图表；同一页可叠多个 ✓）
        if payload.get('overlay') and payload.get('local'):
            self._on_local_add_overlay(payload)
            return
        # ★ 本地图表：指标走 `local_add_indicator`（按 CSV 重算 ✓）
        if payload.get('local'):
            name = str(payload.get('symbol') or '')
            cell = max(0, int(payload.get('cell') or 0))
            if not name:
                # ★ 空白本地图表页（`Gui.Desk` 里 `open_local_chart` 不指定
                #   CSV）也能「加到图表」：按策略里的本地合约名自动选一个 ✓
                try:
                    from .strategy_plan import analyze as _plan
                    contracts = [str(item) for item in
                                 (_plan(path).get('contracts') or [])
                                 if str(item)]
                except Exception:                            # noqa: BLE001
                    contracts = []
                known = {str(item.get('name') or '')
                         for item in self.local_store().items()}
                for item in contracts:
                    if item in known:
                        name = item
                        break
                if not name:
                    name = str(getattr(self, 'last_symbol', '') or '')
            module = _pi._import_file(path)
            if module is not None and name:
                from . import strategy_overlay as _overlay
                found = _overlay.classes_of(module)
                strategies = found.get('strategy') or []
                if strategies:
                    # ★ 本地图表也支持策略（用 CSV 的 frame 跑一遍 ✓）
                    cls = _pick_strategy_class(
                        strategies,
                        str((payload or {}).get('strategy') or ''))
                    # ★ 本页页签 id（策略 / 指标都按「页」存 ✓）
                    page = (str((payload or {}).get('page') or '')
                            or str(getattr(self, '_active_local_page', '')
                                   or ''))
                    # ★ 记下「本页现在有哪些 CSV」：自动布局会改写
                    #   `_local_cell_names` → 清上一个策略时要用**旧**的 ✓
                    page_names = set()
                    if name:
                        page_names.add(str(name))
                    page_names.update(
                        str(value) for value in
                        (getattr(self, '_local_cell_names', {}) or {}).values()
                        if value)
                    store = self.local_store()
                    # ★ **自动流程**：策略里 get_kline(LocalDatas.x) 写到的
                    #   本地 CSV → 自动选布局 + 按顺序装到各格，再运行策略 ✓
                    from .strategy_plan import analyze as _analyze_strategy
                    plan = _analyze_strategy(path)
                    contracts = [str(item) for item
                                 in (plan.get('contracts') or [])
                                 if str(item)]
                    if contracts:
                        # ★ 恢复已保存布局时，布局里的合约已经全部加载到
                        #   `_local_cell_names` → 不要再 `_auto_layout_local`
                        #   重推 layout / 重载数据。那会打断刚恢复的指标，
                        #   用户看到“指标闪一下又消失” ✗。
                        loaded_cells = {
                            str(value) for value in
                            (getattr(self, '_local_cell_names', {}) or {}).values()
                        }
                        already_loaded = set(contracts) <= loaded_cells
                        known = {str(item.get('name') or '')
                                 for item in store.items()}
                        missing = [item for item in contracts
                                   if item not in known]
                        if missing:
                            message = (f'策略里的本地合约找不到：'
                                       f'{"、".join(missing)}')
                            self.push_log(message, 'warning')
                            self.push_alert(
                                '策略合约不在本地数据里', message,
                                detail=f'本地数据：'
                                       f'{"、".join(sorted(known)) or "（空）"}',
                                level='warning')
                            return
                        if len(contracts) > 4:
                            message = (f'策略需要 {len(contracts)} 个本地合约；'
                                       '自动布局目前最多支持 4 个')
                            self.push_log(message, 'warning')
                            self.push_alert('合约数量太多', message,
                                            level='warning')
                            return
                        if not already_loaded:
                            self._auto_layout_local(contracts, current=name)
                            name = contracts[0]
                            cell = 0
                        else:
                            # 保持已恢复的布局 / 各格指标；策略仍按当前格跑 ✓
                            cell_names = getattr(self, '_local_cell_names', {}) or {}
                            for index, cell_name in cell_names.items():
                                if str(cell_name) == str(name):
                                    cell = int(index)
                                    break
                    else:
                        preview = self._local_frames_for_strategy(name, cell)
                        need = max(1, int(plan.get('klines') or 1))
                        if need > len(preview):
                            message = (f'策略使用 klines1..klines{need} 写法'
                                       '（没有 get_kline 合约名）→ 必须先选好'
                                       '布局并加载本地合约；当前本地图表只有 '
                                       f'{len(preview)} 个合约')
                            self.push_log(message, 'warning')
                            self.push_alert(
                                '策略需要的K线数量不够', message,
                                detail='请先用「布局」切成对应格数，并在每格'
                                       '加载策略需要的本地 CSV，再加策略。',
                                level='warning')
                            return
                    try:
                        frame = store.frame(name)
                    except Exception:                        # noqa: BLE001
                        frame = None
                    if frame is None or len(frame) == 0:
                        message = f'本地数据 {name} 还没加载，先打开一次图表再试'
                        self.push_log(message, 'warning')
                        self.push_alert('本地图表没有数据', message,
                                        detail=name)
                        return
                    # ★ **多布局多合约**：把每个格子加载的 CSV 按格序一起交给
                    #   策略 → `self.klines1 / klines2 …` 分别对应格 1 / 格 2 ✓
                    frames = self._local_frames_for_strategy(name, cell)
                    # ★ 先校验 `klinesN` 数量（不通过就别跑，直接给出可读提示 ✓）
                    if not self._check_strategy_klines_usage(path, frames):
                        return
                    # 本地策略：逐根跑一遍，stop_price / target_price 才会
                    # 随策略回放产生历史值（BtStop 的止损线在主图显示）。
                    # ★ 只回放最近 LOCAL_STRATEGY_REPLAY_BARS 根：
                    #   指标 / 信号在最后一根仍按全量重算，历史线完整；
                    #   停止线保留最近 N 根。以前 replay_bars=0 会把 10000 根
                    #   全部逐根跑（CCI 每根全量重算 → 几分钟「未响应」✗）。
                    # ★ 一个页面只放一个策略：先把**本页所有格**上的上一个策略
                    #   清掉（布局 / 指标保留），再跑新策略 ✓
                    #   `page_names` 是**自动布局之前**取的旧格子名（自动布局
                    #   会改写 `_local_cell_names` → 不取旧的就清不到旧格子 ✗）
                    self._clear_local_page_strategies(name, also=page_names,
                                                      page=page)
                    self._local_strategy_seq += 1
                    job = self._local_strategy_seq
                    self._local_strategy_jobs[name] = job
                    replay_bars = LOCAL_STRATEGY_REPLAY_BARS or len(frame)
                    self.push_log(
                        f'正在回放策略 {cls.__name__}'
                        f'（{min(len(frame), replay_bars)} 根，后台计算）…',
                        'info')
                    threading.Thread(
                        target=self._run_local_strategy_overlay,
                        args=(name, cell, path, cls, frames, job, page,
                              list(contracts or [])),
                        name=f'local-strategy-{name}', daemon=True).start()
                    return
                entries = [entry for entry in _pi.scan('indicator')
                           if os.path.abspath(str(entry.get('path'))) ==
                           os.path.abspath(path)]
                if not entries:
                    # 目录没登记 → 先登记（和实时图表一致 ✓）
                    result = _pi.add_directory(folder, kind='indicator')
                    entries = [entry for entry in _pi.scan('indicator')
                               if os.path.abspath(str(entry.get('path'))) ==
                               os.path.abspath(path)]
                    _ = result
                keys = []
                for entry in entries:
                    key = str(entry.get('key') or '')
                    if key:
                        keys.append(key)
                names = [key.split('/')[-1] for key in keys]
                for key in keys:
                    self._on_local_add_indicator(
                        {'symbol': name, 'key': key, 'params': {},
                         'cell': cell})
                if keys:
                    self.push_log(f'已加到本地图表：{"、".join(names)}',
                                  'success')
                    self.push(_protocol.patch_toast(
                        f'已加指标：{"、".join(names)}', 'success'))
                else:
                    message = f'{os.path.basename(path)} 里没有可用的指标'
                    self.push_log(message, 'error')
                    self.push(_protocol.patch_toast(message, 'warning'))
                return
        requested = str((payload or {}).get('symbol') or '')
        if requested in self.tabs:
            symbol_of = requested
        else:
            symbol_of = (str(getattr(self, 'last_symbol', '') or '')
                         or next(iter(self.tabs), ''))
            if symbol_of not in self.tabs:
                symbol_of = next(iter(self.tabs), '')
        # ★ 先看这个文件里有什么类：**策略优先**（用户要求 ✓）
        module = _pi._import_file(path)
        if module is not None:
            from . import strategy_overlay as _overlay
            found = _overlay.classes_of(module)
            strategies = found.get('strategy') or []
            if strategies:
                cls = _pick_strategy_class(
                    strategies,
                    str((payload or {}).get('strategy') or ''))
                # ★ 一个页面只放一个策略：换策略（同一个 / 另一个）先把**上一个**
                #   清掉（含所有布局格），布局 / 指标保留 ✓
                self._remove_strategy_of(symbol_of)
                info = self.tabs.setdefault(symbol_of, {})
                cycle = int(info.get('cycle') or 60)
                # ★ 实时图表：天勤已连接 → 真下单（模拟盘 / 实盘看账户）；
                #   **自动流程**：按策略需要选布局 / 选合约 / 载入 K 线，
                #   再运行策略（test_4 的真实合约会先到天勤报价里校验 ✓）
                live, api, account = self._strategy_live_context(cls)
                self.push_log(
                    f'正在加载策略 {cls.__name__}（取合约 K 线 + 计算，稍等）…',
                    'info')
                _t0 = time.monotonic()
                prepared = self._prepare_realtime_strategy(
                    symbol_of, info, path, cls, cycle)
                _dt = time.monotonic() - _t0
                if _dt >= 1.0:
                    self.push_log(f'[性能] 策略取数 {_dt:.2f}s', 'info')
                if not prepared.get('ok'):
                    message = (f'策略 {cls.__name__} 加到图表失败：'
                               f'{prepared.get("error")}')
                    self.push_log(message, 'error')
                    detail = str(prepared.get('detail')
                                 or os.path.basename(path))
                    self.push_alert('策略合约无法加载',
                                    str(prepared.get('error')),
                                    detail=detail, level='warning')
                    return
                frames = prepared.get('frames') or []
                fetch = self._fetch_strategy_frame(info, cycle) if live else None
                # ★ **计算放后台线程**（`KalmanFilter` 这种 Python 循环几秒~几十秒，
                #   以前在主线程里跑 → 整个界面卡住 ✗）。K 线 / 布局已经在
                #   `_prepare_realtime_strategy()` 里推上去了 → 图上先有数据，
                #   算完再把线推上去 ✓
                job = int(info.get('_strat_job') or 0) + 1
                info['_strat_job'] = job
                if getattr(self, '_strategy_sync', False):
                    # 测试 / 脚本：**同步**跑（不用等线程，结果立刻可断言 ✓）
                    self._run_realtime_strategy_job(
                        job, symbol_of, path, cls, prepared, frames, live,
                        api, account, fetch, cycle, payload)
                    self._drain_strategy_results()
                    return
                self._heavy_jobs = int(getattr(self, '_heavy_jobs', 0)) + 1
                self.push_log(
                    f'策略 {cls.__name__} 正在后台计算（界面不卡，算完自动上图）…',
                    'info')
                threading.Thread(
                    target=self._run_realtime_strategy_job,
                    args=(job, symbol_of, path, cls, prepared, frames, live,
                          api, account, fetch, cycle, payload),
                    name=f'desk-strategy-{symbol_of}', daemon=True).start()
                return
        entries = _pi.scan('indicator')
        category = ''
        for entry in _pi.directories():
            if entry.get('kind') != 'indicator':
                continue
            base = os.path.abspath(entry.get('path') or '')
            if os.path.abspath(path).startswith(base):
                category = str(entry.get('category') or '')
                break
        if not category:
            result = _pi.add_directory(folder, kind='indicator')
            category = str(result.get('category') or _pi.category_name(folder))
            entries = _pi.scan('indicator')
        name = os.path.splitext(os.path.basename(path))[0]
        keys = [entry['key'] for entry in entries
                if str(entry.get('path')) and
                os.path.abspath(str(entry['path'])) == os.path.abspath(path)]
        if not keys:
            message = (f'{name} 里没有可用的指标（函数或 BtIndicator 类）'
                       ' —— 检查是否有语法错误（编辑器「语法检查」）')
            self.push_log(message, 'error')
            self.push(_protocol.patch_toast(message, 'warning'))
            return
        symbol = symbol_of
        for key in keys:
            self._on_add_indicator({'key': key, 'params': {},
                                    'symbol': symbol})
        added = ', '.join(key.split('/')[-1] for key in keys)
        self.push_log(f'已加到图表：{added}（分类 {category}）', 'success')
        self.push(_protocol.patch_toast(f'已加指标：{added}', 'success'))

    def _clear_local_page_strategies(self, name: str, also=None,
                                     page: str = '') -> List[str]:
        """清掉**当前本地图表页**上的策略（布局 / 指标保留 ✓）

        「一个页面只放一个策略」：重新「加到图表」（同一个或另一个策略）时
        先把上一个策略的线 / runner / 落盘记录清掉。以前只清「与新策略同名」
        的记录 → 多合约策略的画在别的格子 / 别的 CSV 上时，旧线会残留 ✗

        `also`：额外的数据名（自动布局会改写 `_local_cell_names`，所以调用方
        要先把**旧**格子名传进来，否则旧格子的策略清不到 ✓）
        """
        names = {str(name or '')}
        source = (also if also is not None
                  else (getattr(self, '_local_cell_names', {}) or {}).values())
        names.update(str(item) for item in source if item)
        if page:
            names.add(str(page))          # 按「页」存的策略记录 ✓
        strategies = getattr(self, '_local_strategies', {}) or {}
        removed = [item for item in names if item in strategies]
        if not removed:
            return []
        for item in removed:
            record = strategies.pop(item, None) or {}
            getattr(self, '_local_strategy_of', {}).pop(item, None)
            getattr(self, '_local_strategy_jobs', {}).pop(item, None)
            getattr(self, '_local_strategy_done', {}).pop(item, None)
            label = str(record.get('name') or '')
            if label:
                getattr(self, '_local_runners', {}).pop(label, None)
            try:
                self.local_store().set_strategy(item, None)
            except Exception:                                # noqa: BLE001
                pass
        # 所有格重推一次（策略线在 payload 里，清掉后自然消失 ✓）
        cells = getattr(self, '_local_cell_names', {}) or {}
        pushed = set()
        for index, cell_name in list(cells.items()):
            self.push(self._local_indicator_payload(str(cell_name),
                                                    int(index), page=page))
            pushed.add(str(cell_name))
        for item in removed:
            if item not in pushed:
                self.push(self._local_indicator_payload(
                    name, 0, page=page))
        self.push_log('已清除上一个策略：' + '、'.join(removed), 'info')
        return removed

    def _remove_local_strategy(self, target: str) -> bool:
        """删本地图表策略：**同一策略的所有合约格**一起删（指标保留）✓"""
        target = str(target or '')
        strategies = getattr(self, '_local_strategies', {}) or {}
        record = strategies.get(target) or {}
        if not record:
            # ★ 老行 / 直接传 CSV 名或策略名：按记录内容找一条 ✓
            for candidate in strategies.values():
                candidate = candidate or {}
                groups = candidate.get('groups') or {}
                if target and (target in (
                        str(candidate.get('symbol') or ''),
                        str(candidate.get('name') or ''),
                        str(candidate.get('path') or ''))
                        or target in groups):
                    record = candidate
                    break
        label = str(record.get('name') or '')
        path = str(record.get('path') or '')
        if not label and not path:
            return False
        removed = []
        removed_pages: Dict[str, str] = {}
        csv_names: List[str] = []
        for key, item in list(strategies.items()):
            item = item or {}
            if ((label and str(item.get('name') or '') == label)
                    or (path and str(item.get('path') or '') == path)):
                strategies.pop(key, None)
                removed.append(str(key))
                removed_pages[str(key)] = str((item or {}).get('page') or '')
                for csv_name in list((item or {}).get('groups') or {}):
                    if csv_name and csv_name not in csv_names:
                        csv_names.append(str(csv_name))
                symbol = str((item or {}).get('symbol') or '')
                if symbol and symbol not in csv_names:
                    csv_names.append(symbol)
                getattr(self, '_local_strategy_of', {}).pop(key, None)
        runners = getattr(self, '_local_runners', {}) or {}
        if label:
            runners.pop(label, None)
        # 作废还在后台计算的「加到图表」任务，避免删完又被回调加回来 ✓
        jobs = getattr(self, '_local_strategy_jobs', {}) or {}
        for name in csv_names:
            jobs.pop(name, None)
            getattr(self, '_local_strategy_done', {}).pop(name, None)
            try:
                self.local_store().set_strategy(name, None)
            except Exception:                                # noqa: BLE001
                pass
        if not removed:
            return False
        # 所有加载过的格子都重推（策略线在 payload 里，删掉后自然消失 ✓）
        cells = getattr(self, '_local_cell_names', {}) or {}
        pushed = set()
        for index, cell_name in cells.items():
            self.push(self._local_indicator_payload(
                cell_name, int(index),
                page=removed_pages.get(str(removed[0])) or ''))
            pushed.add(str(cell_name))
        for name in csv_names:
            if name not in pushed:
                self.push(self._local_indicator_payload(
                    name, 0, page=removed_pages.get(str(removed[0])) or ''))
        self.push_log(f'已删除本地图表策略：{label or target}', 'info')
        return True

    def _strategy_manage_rows(self) -> List[dict]:
        """所有图表（含多布局每格）上的策略 → 「策略管理」弹窗的行 ✓"""
        rows: List[dict] = []
        for symbol, info in list((self.tabs or {}).items()):
            info = info or {}
            items = list(info.get('strategy_items') or [])
            name = str((info.get('strategy') or {}).get('name') or '')
            if not items and not name:
                continue
            conf = dict(info.get('strategy_config') or {})
            rows.append({
                'symbol': str(symbol),
                'cell': 0,
                'name': name or '策略',
                'path': str((info.get('strategy') or {}).get('path') or ''),
                'lines': len(items),
                'next_on_new_bar': conf.get('next_on_new_bar', True) is not False,
                'run_next': conf.get('run_next', True) is not False,
            })
            # 多布局：每格可能有自己的策略（`layout.cells` 是 **list**：
            # `[{'symbol':…, 'indicators':…}]`；旧代码当 dict 用 → 报
            # `'list' object has no attribute 'get'` ✗）
            layout = dict(info.get('layout') or {})
            cells = layout.get('cells') or []

            def _cell_of(index: int) -> dict:
                if isinstance(cells, dict):
                    value = (cells.get(str(index)) if str(index) in cells
                             else cells.get(index))
                    return value if isinstance(value, dict) else {}
                if isinstance(cells, list) and index < len(cells):
                    value = cells[index]
                    return value if isinstance(value, dict) else {}
                return {}

            for index, cell_symbol in enumerate(layout.get('symbols') or []):
                cell_info = _cell_of(index)
                cell_items = list(cell_info.get('strategy_items') or [])
                cell_name = str((cell_info.get('strategy') or {}).get('name')
                                or '')
                if not cell_items and not cell_name:
                    continue
                rows.append({
                    'symbol': str(cell_symbol or symbol),
                    'cell': int(index),
                    'name': cell_name or '策略',
                    'path': str((cell_info.get('strategy') or {})
                                .get('path') or ''),
                    'lines': len(cell_items),
                })
        # 本地图表上的策略（`_local_strategies`）
        for key, record in list(
                getattr(self, '_local_strategies', {}).items()):
            record = record or {}
            groups = record.get('groups') or {}
            lines = sum(len(group or []) for group in groups.values())                 or len(record.get('items') or [])
            rows.append({
                # ★ `key` = `_local_strategies` 的键（页签 id / CSV 名）→
                #   删除必须用它（以前只发 symbol，页面记录删不掉 ✗）
                'key': str(key),
                'symbol': str(record.get('symbol') or key),
                'cell': 0,
                'name': str(record.get('name') or '策略'),
                'path': str(record.get('path') or ''),
                'lines': lines,
                'local': True,
            })
        # 只读叠加（`_local_overlays`）：可以删，但没有开关（不交易 ✓）
        for page_key, records in list(
                (getattr(self, '_local_overlays', {}) or {}).items()):
            for record in records or []:
                groups = record.get('groups') or {}
                rows.append({
                    'key': str(record.get('key')
                               or record.get('name') or ''),
                    'symbol': str(record.get('symbol') or ''),
                    'cell': 0,
                    'name': f"{record.get('name')}（只读叠加）",
                    'path': str(record.get('path') or ''),
                    'lines': sum(len(group or [])
                                 for group in groups.values())
                    or len(record.get('items') or []),
                    'local': True,
                    'overlay': True,
                    'page': str(page_key),
                })
        # ★ 策略实盘（`Bt(live=True)` 常驻子进程）：一个文件一行，三个按钮
        #   （新K线next / 运行next / 删除=停止）与图表上的策略完全一样 ✓
        for item in self.strategy_live_items():
            path = str(item.get('file') or '')
            rows.append({
                'symbol': str(item.get('name') or ''),
                'cell': 0,
                'name': str(item.get('name') or os.path.basename(path)),
                'path': path,
                'file': path,
                'lines': 0,
                'live': True,
                'running': bool(item.get('running')),
                'pid': int(item.get('pid') or 0),
                'next_on_new_bar': bool(item.get('next_on_new_bar', True)),
                'run_next': bool(item.get('run_next', True)),
            })
        return rows

    # ------------------------------------------------------ 画线（本地持久化）
    def _on_drawings(self, payload=None) -> None:
        """前端要某个键的画线（`合约|周期`）→ 推 `{type:'drawings'}` ✓

        `payload.key` 为空时把**全部**推一遍（切布局 / 重连后兜底 ✓）。
        """
        payload = payload or {}
        from . import drawings as _drawings
        key = str(payload.get('key') or '')
        if key:
            self.push({'type': 'drawings', 'key': key,
                       'items': _drawings.get(key)})
            return
        for name, items in _drawings.all_drawings().items():
            self.push({'type': 'drawings', 'key': name, 'items': items})

    def _on_save_drawings(self, payload=None) -> None:
        """前端画完 / 删完一条 → 存盘（键 = 合约|周期，空列表 = 删掉 ✓）"""
        payload = payload or {}
        from . import drawings as _drawings
        key = str(payload.get('key') or '')
        if not key:
            return
        items = payload.get('items')
        _drawings.save(key, items if isinstance(items, list) else [])
        self.push_log_once(f'drawings-saved:{key}',
                           f'画线已保存：{key}（{len(items or [])} 个）')

    def _on_clear_drawings(self, payload=None) -> None:
        """「清除画线」→ 删这个键（同键的图都会清 ✓）"""
        payload = payload or {}
        from . import drawings as _drawings
        key = str(payload.get('key') or '')
        _drawings.clear(key)
        self.push({'type': 'drawings', 'key': key, 'items': []})
        if key:
            self.push_log(f'已清除画线：{key}', 'info')

    def _on_strategy_manage(self, payload=None) -> None:
        """打开「策略管理」：列出所有图表的策略 + 两个运行开关 ✓"""
        from . import user_prefs as _prefs
        settings = _prefs.settings()
        self.push({
            'type': 'strategy_manage',
            'rows': self._strategy_manage_rows(),
            'next_on_new_bar': bool(
                settings.get('strategy_next_on_new_bar', True)),
            'run_next': bool(settings.get('strategy_run_next', True)),
        })

    def _on_strategy_manage_update(self, payload) -> None:
        """策略管理弹窗里的操作：改开关 / 删除某个策略 ✓"""
        payload = payload or {}
        from . import user_prefs as _prefs
        action = str(payload.get('action') or 'settings')
        # ★ 策略实盘的行：`live=True`（symbol 是策略名，`file` 才是钥匙）
        if payload.get('live'):
            self._on_strategy_live_manage(payload)
            self._on_strategy_manage({})
            return
        if action == 'toggle':
            if payload.get('overlay'):
                return               # 只读叠加没有 next 开关（前端也是禁用 ✓）
            # ★ 针对**单个策略**改两个开关（存 tab info + 通知 runner ✓）
            symbol = self._resolve_tab_symbol(
                str(payload.get('symbol') or ''))
            info = self.tabs.get(symbol) or {}
            conf = dict(info.get('strategy_config') or {})
            key = str(payload.get('key') or '')
            if key in ('next_on_new_bar', 'run_next'):
                conf[key] = bool(payload.get('value'))
                info['strategy_config'] = conf
                self.tabs[symbol] = info
                runner = info.get('strategy_runner')
                if runner is not None:
                    runner.override = dict(conf)
                self.push_log(
                    f'策略 {symbol}：{key} = {conf[key]}', 'info')
        elif action == 'delete':
            symbol = self._resolve_tab_symbol(
                str(payload.get('symbol') or ''))
            if payload.get('local'):
                if payload.get('overlay'):
                    # 只读叠加：按名字删（同名叠加在所有页一起清 ✓）
                    self._remove_local_overlay(str(payload.get('key') or ''))
                else:
                    # ★ 用行上的 `key`（页签 id / CSV 名）删；没有就退回 symbol ✓
                    self._remove_local_strategy(
                        str(payload.get('key') or symbol))
            else:
                self._remove_strategy_of(symbol)
        else:
            for key, name in (('next_on_new_bar', 'strategy_next_on_new_bar'),
                              ('run_next', 'strategy_run_next')):
                if key in payload:
                    _prefs.set_setting(name, bool(payload.get(key)))
            self.push_log('策略运行设置已更新', 'success')
        self._on_strategy_manage({})

    def _on_strategy_live_manage(self, payload: dict) -> None:
        """策略管理弹窗里**实盘**那一行：改开关 / 删除（= 停止该策略）✓"""
        from . import live_control
        action = str(payload.get('action') or 'toggle')
        file = str(payload.get('file') or payload.get('path') or '')
        key = live_control.normalize(file) if file else ''
        lives = self._live_map()
        live = lives.get(key)
        name = (os.path.basename(file) if file
                else str(payload.get('symbol') or '策略'))
        if action == 'delete':
            # 删除 = 停止该策略实盘 + 从列表 / 控制文件里摘掉 ✓
            if live is not None:
                lives.pop(key, None)
                self._strategy_live = (next(iter(lives.values()), None)
                                       if lives else None)
                try:
                    live.stop()
                except Exception as error:                   # noqa: BLE001
                    self.push_log(f'停止策略实盘失败：{error!r}', 'warning')
            try:
                live_control.clear(key)
            except Exception:                                # noqa: BLE001
                pass
            self.push_log(f'策略实盘已停止并移除：{name}', 'success')
            self._push_strategy_live()
            return
        # 改开关：写控制文件（子进程下个 tick 就生效 ✓）+ 更新内存状态
        name_key = str(payload.get('key') or '')
        if name_key in ('next_on_new_bar', 'run_next'):
            value = bool(payload.get('value'))
            if live is not None:
                setattr(live, name_key, value)
            if key:
                live_control.set_value(key, name_key, value)
            self.push_log(f'策略实盘 {name}：{name_key} = {value}', 'info')
            self._push_strategy_live()

    # ------------------------------------------------------ 策略实盘（可多个）
    def _live_map(self) -> Dict[str, Any]:
        """`file -> StrategyLive`（惰性初始化；测试里可直接塞 ✓）"""
        lives = getattr(self, '_strategy_lives', None)
        if not isinstance(lives, dict):
            lives = self._strategy_lives = {}
        return lives

    def strategy_live_items(self) -> List[dict]:
        """所有策略实盘的状态（策略管理弹窗 / 编辑器按钮都用它 ✓）"""
        items: List[dict] = []
        for live in self._live_map().values():
            try:
                items.append(live.status())
            except Exception:                                # noqa: BLE001
                continue
        items.sort(key=lambda item: str(item.get('file') or ''))
        return items

    def _push_strategy_live(self, error: str = '') -> None:
        """推一次「策略实盘」状态：`items` = 每个文件一条 ✓"""
        items = self.strategy_live_items()
        payload: Dict[str, Any] = {
            'type': 'strategy_live',
            'running': any(bool(item.get('running')) for item in items),
            'items': items,
        }
        if error:
            payload['error'] = str(error)
        self.push(payload)

    def _on_strategy_live_start(self, payload) -> None:
        """策略实盘 / 模拟盘：常驻运行（`Bt(live=True)`）✓

        ★ 支持**多个策略同时跑**：一个文件一个子进程（`_strategy_lives`）。
        同一文件重复启动 = 提示已在运行（不会起第二个进程 ✓）。
        """
        payload = payload or {}
        path = str(payload.get('file') or payload.get('path') or '')
        if not path or not os.path.isfile(path):
            self.push_log('策略实盘：文件不存在', 'warning')
            self._push_strategy_live('策略文件不存在')
            return
        # ★ 全局交易开关必须也拦策略实盘（以前只拦手动下单 ✗）
        if not bool(getattr(self, 'trading', False)):
            self.push_log('策略实盘：当前禁止交易（allow_trading=False / '
                          '未连接交易接口）', 'warning')
            self._push_strategy_live('当前禁止交易')
            return
        # ★ 二次确认：前端会弹窗；HTTP 直连也必须带 confirm ✓
        if not bool(payload.get('confirm')):
            self.push_log('策略实盘：未确认，已取消启动', 'warning')
            self._push_strategy_live('未确认启动')
            return
        from . import live_control
        from .strategy_live import StrategyLive
        key = live_control.normalize(path)
        lives = self._live_map()
        known = lives.get(key)
        if known is not None and getattr(known, 'running', False):
            self.push_log(
                f'策略实盘：{os.path.basename(path)} 已在运行', 'warning')
            self._push_strategy_live()
            return
        # 崩了是否自动重启（默认不重启；可在 payload / 设置里打开 ✓）
        try:
            from . import user_prefs as _prefs
            settings = _prefs.settings()
            default_retry = bool(settings.get('strategy_live_retry'))
        except Exception:                                    # noqa: BLE001
            settings = {}
            default_retry = False
        config = {
            'next_on_new_bar': bool(settings.get('strategy_next_on_new_bar',
                                                 True)),
            'run_next': bool(settings.get('strategy_run_next', True)),
        }
        for name in ('next_on_new_bar', 'run_next'):
            if name in payload:
                config[name] = bool(payload.get(name))
        live = StrategyLive(self, path, payload.get('params') or {},
                            config=config)
        live.retry = bool(payload.get('retry', default_retry))
        live.on_change = lambda: self._push_strategy_live()
        lives[key] = live
        self._strategy_live = live        # 兼容旧入口（最近一次启动的那个）
        status = live.start()
        if not status.get('running'):
            # 启动失败（缺账号 / 禁止交易…）：不留在列表里 ✓
            lives.pop(key, None)
            self._strategy_live = (next(iter(lives.values()), None)
                                   if lives else None)
            self._push_strategy_live(str(status.get('error') or ''))
            return
        self._push_strategy_live()

    def stop_strategy_live(self) -> None:
        """程序退出 / 关窗口时调用：停掉**所有**策略实盘（不再下单 ✓）"""
        self._on_strategy_live_stop({})

    def _on_strategy_live_stop(self, payload=None) -> None:
        """停止策略实盘：带 `file` = 只停那一个；不带 = **停止并删除全部** ✓"""
        payload = payload or {}
        from . import live_control
        file = str(payload.get('file') or payload.get('path') or '')
        key = live_control.normalize(file) if file else ''
        lives = self._live_map()
        targets = [key] if key and key in lives else list(lives)
        # 兼容旧入口：`_strategy_live` 上挂的实例（老代码 / 测试）也要停 ✓
        legacy = getattr(self, '_strategy_live', None)
        if (legacy is not None
                and all(legacy is not item for item in lives.values())):
            try:
                legacy.stop()
            except Exception:                                # noqa: BLE001
                pass
            self._strategy_live = None
        if not targets:
            self._push_strategy_live()
            return
        from . import live_control
        for name in targets:
            live = lives.pop(name, None)
            if live is not None:
                try:
                    live.stop()
                except Exception as error:                   # noqa: BLE001
                    self.push_log(f'停止策略实盘失败：{error!r}', 'warning')
            try:
                live_control.clear(name)
            except Exception:                                # noqa: BLE001
                pass
        self._strategy_live = (next(iter(lives.values()), None)
                               if lives else None)
        self.push_log(f'已停止 {len(targets)} 个策略实盘', 'success')
        self._push_strategy_live()

    def _restart_strategy_live_all(self) -> None:
        """切账户后：按新账户重启所有策略实盘 ✓"""
        for live in list(self._live_map().values()):
            if not getattr(live, 'running', False):
                continue
            try:
                live.stop()
                live.start()
            except Exception as error:                       # noqa: BLE001
                self.push_log(f'切换账户重启策略实盘失败：{error!r}', 'warning')

    def _resolve_tab_symbol(self, symbol: str) -> str:
        """多布局格子合约 → 它所属的 tab key（前端多格删指标传的是格子合约）✓"""
        text = str(symbol or '')
        if not text or text in self.tabs:
            return text
        for tab, info in list(self.tabs.items()):
            layout = dict((info or {}).get('layout') or {})
            names = [str(item or '') for item in
                     (layout.get('symbols') or [])]
            for cell in (layout.get('cells') or []):
                if isinstance(cell, dict) and cell.get('symbol'):
                    names.append(str(cell.get('symbol')))
            if text in names:
                return str(tab)
        return text

    def _remove_strategy_of(self, symbol: str) -> bool:
        """删掉某个 tab 上的策略（**所有布局格**，指标保留 ✓）"""
        symbol = self._resolve_tab_symbol(symbol)
        info = self.tabs.get(symbol) or {}
        name = str((info.get('strategy') or {}).get('name', ''))
        removed = bool(info.get('strategy_items') or info.get('strategy')
                       or info.get('strategy_runner'))
        info['strategy_items'] = []
        for key in ('strategy', 'strategy_runner', 'strategy_groups',
                    'strategy_config', '_strat_stamp', '_strat_at',
                    '_strat_frame_cache', '_strat_error',
                    '_strat_error_shown', '_strat_error_at',
                    '_strat_error_last', 'strategy_contracts',
                    '_strat_bar', '_strat_idle'):
            info.pop(key, None)
        # ★ 多布局：每格前端各自缓存了策略线；只推 cell0 会留下格 2 的线 ✗
        layout = dict(info.get('layout') or {})
        cells = layout.get('cells') or []
        if not isinstance(cells, list):
            cells = []
        cell_count = max(len(cells), len(layout.get('symbols') or []))
        for index, cell in enumerate(cells):
            if not isinstance(cell, dict):
                continue
            if any(cell.get(key) for key in (
                    'strategy', 'strategy_items', 'strategy_runner',
                    'strategy_groups', 'strategy_config')):
                removed = True
            for key in ('strategy', 'strategy_items', 'strategy_runner',
                        'strategy_groups', 'strategy_config'):
                cell.pop(key, None)
        if cells:
            layout['cells'] = cells
            info['layout'] = layout
        if removed:
            self.push_log(f'已删除图表上的策略：{name or symbol}', 'info')
        # 第 1 格：其它指标由 indicator_payload 重算；策略线已清空
        self.push(self.indicator_payload(symbol))
        # 第 2..N 格：空补丁 + strategyOnly → 只清策略线，保留普通指标
        for index in range(1, cell_count):
            self.push({'type': 'indicator', 'symbol': symbol, 'cell': index,
                       'items': [], 'strategy': '', 'strategyOnly': True})
        return removed

    def _prepare_replay_account(self, runner=None) -> None:
        """回放开始：用 minibt 策略账户重置 desk 本地模拟账户 ✓

        初始资金 = `strategy.config.value`；每合约的乘数 / 最小变动 /
        保证金率 / 手续费 / 滑点都从 KLine / Broker 快照过来。
        """
        if runner is None:
            for info in (getattr(self, '_local_runners', {}) or {}).values():
                runner = info.get('runner')
                if runner is not None:
                    break
        if runner is None:
            return
        try:
            spec = runner.account_spec()
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'读取策略账户配置失败：{error!r}', 'warning')
            return
        contracts = spec.get('contracts') or {}
        initial = spec.get('initial_cash')
        try:
            initial_value = float(initial)
        except (TypeError, ValueError):
            initial_value = None
        sim = self.local_sim()
        sim.prepare_replay(initial_value, contracts)
        self._active_account_spec = spec
        try:
            self._push_sim_analysis()
        except Exception:                                        # noqa: BLE001
            pass
        detail = []
        for name, item in list(contracts.items())[:8]:
            commission = item.get('commission') or {}
            fee_text = next((f'{key}={value}'
                             for key, value in commission.items()
                             if value), '0')
            detail.append(
                f'{name}（乘数 {item.get("volume_multiple")}，'
                f'tick {item.get("price_tick")}，'
                f'保证金率 {item.get("margin_rate")}，手续费 {fee_text}）')
        self.push_log(
            f'本地模拟账户 ← 策略配置：初始资金 {float(sim.initial_cash):,.2f}'
            + ('；' + '；'.join(detail) if detail else ''), 'info')

    def _on_replay_price(self, payload=None) -> None:
        """回放推进时把**所有格子**的最新收盘价写进本地模拟账户 ✓

        `payload` 同时兼容两种来源：

        * 看盘窗口：``{symbol, price, time}``（单合约）；
        * 本地图表多布局：``{symbol, price, time, index, cells, advance,
          reset}``，``cells=[{symbol, price, time, index}, …]``。

        关键点（用户反馈的三个问题都在这）：

        * 每个合约都用**当前回放那一根**的收盘价 → 账户「现价」= 图表现价；
        * `advance=True` 才推进策略 —— 进入回放 / 暂停 / 拖动时间轴时只
          对齐价格，**绝不成交**；
        * `reset=True`（进入回放 / 换时间段）→ 策略内部账户归零，历史
          replay 产生的 orders / targets 全部丢弃，不会"还没点播放就成交" ✗
        """
        payload = payload or {}
        symbol = str(payload.get('symbol') or '')
        price = payload.get('price')
        cells = [item for item in (payload.get('cells') or [])
                 if isinstance(item, dict)]
        updates: List[tuple] = []
        for item in cells:
            name = str(item.get('symbol') or '')
            try:
                value = float(item.get('price'))
            except (TypeError, ValueError):
                continue
            if name and value > 0:
                updates.append((name, value, item.get('time')))
        if symbol and price is not None:
            try:
                value = float(price)
            except (TypeError, ValueError):
                value = 0.0
            if symbol and value > 0 and not any(name == symbol
                                                for name, *_ in updates):
                # ★ 看盘窗口（单合约）仍然用旧的 `bar=payload.get('time')`
                sim_for_primary = self.local_sim()
                decimals = sim_for_primary.decimals.get(symbol)
                if decimals is None:
                    decimals = self.decimals_of(symbol)
                sim_for_primary.set_price(symbol, value, decimals,
                                          bar=payload.get('time'))
                updates.append((symbol, value, payload.get('time')))
        if not updates:
            return
        # ★ 进入回放 / seek：先用策略的 minibt 账户参数重置 desk 本地账户 ✓
        #   只在**本地图表**（带 cells）时做；看盘窗口回放没 runner。
        reset = bool(payload.get('reset'))
        if reset and cells and getattr(self, '_local_runners', None):
            self._prepare_replay_account()
        sim = self.local_sim()

        def sim_decimals(name: str) -> int:
            """优先用合约规格（minibt price_tick）的小数位 ✓"""
            value = sim.decimals.get(str(name))
            return self.decimals_of(name) if value is None else int(value)

        for name, value, bar in updates:
            # ★ `bar` = 当前这根 K 线：刚开仓那根不覆盖开仓价（浮盈 0 ✓）
            sim.set_price(name, value, sim_decimals(name), bar=bar)

        names = [item[0] for item in updates]
        active = str(getattr(self, 'last_symbol', '') or '')
        if active not in names:
            active = symbol or names[0]
        active_price = next((item[1] for item in updates
                             if item[0] == active), None)
        active_time = next((item[2] for item in updates
                            if item[0] == active), None)

        advance = payload.get('advance')
        if advance is None:                 # 旧前端（看盘窗口）只有 playing ✓
            advance = bool(payload.get('playing', True))
        index = payload.get('index')
        if index is None and getattr(self, '_local_runners', None):
            # ★ 只有本地图表（有策略 runner）才需要反查下标；看盘窗口回放
            #   传的时间不一定是本地 CSV，硬查还会白读文件 ✗
            index = self._replay_index_of_time(active, active_time)
        try:
            index = None if index is None else int(index)
        except (TypeError, ValueError):
            index = None

        try:
            self._local_strategy_replay_step(
                active, active_price, time_value=active_time,
                index=index, advance=bool(advance), reset=reset)
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'策略回放步进失败：{error!r}', 'warning')

        # ★ 成交会把 sim 现价改成「下单那根」；这里再对齐回当前回放根
        #   （策略按市价 / 目标手数成交时，成交价就是这根收盘价；清掉
        #    `_hold` 是为了避免"跳了几根"时停在旧成交价上 ✗）
        for name, value, bar in updates:
            try:
                sim._hold.pop(name, None)
            except Exception:                                    # noqa: BLE001
                pass
            sim.set_price(name, value, sim_decimals(name), bar=bar)

        local = symbol not in self.replay_symbols
        if local:
            self.push(sim.payload(active))
        else:
            self.push(self.replay_account_payload(active))
        for name, _value, _bar in updates:
            self._push_sim_position(name, local=local)
            self._push_orders(name, local=local)

        # ★ 设置页「模拟账户」的权益曲线 / 各品种累计盈亏也要跟着回放走：
        #   单合约原来的逻辑是「有持仓就每拍推 sim_analysis」；多合约路径
        #   之前漏了这一句 → 页面显示的还是进入回放前的旧值 ✗
        #   无持仓时权益不随价格变化，只在真正成交时由 `_on_local_order` 推 ✓
        has_position = any(
            float(book.get('long') or 0.0) > 0
            or float(book.get('short') or 0.0) > 0
            for book in (sim.positions or {}).values())
        if has_position:
            self._push_sim_analysis()

    def _replay_index_of_time(self, symbol: str,
                              time_value) -> Optional[int]:
        """回放时间 → 本地 K 线下标（前端没带 `index` 时兜底 ✓）"""
        if time_value is None or not symbol:
            return None
        try:
            import pandas as _pd
            frame = self.local_store().frame(symbol)
            if frame is None or not len(frame):
                return None
            stamps = _pd.to_datetime(frame['datetime'])
            text = str(time_value).strip()
            numeric = isinstance(time_value, (int, float)) or (
                text.lstrip('-').replace('.', '', 1).isdigit())
            moment = (_pd.to_datetime(float(time_value), unit='s')
                      if numeric else _pd.to_datetime(time_value))
            if getattr(moment, 'tzinfo', None) is not None:
                moment = moment.tz_localize(None)
            if getattr(getattr(stamps, 'dt', None), 'tz', None) is not None:
                stamps = stamps.dt.tz_localize(None)
            found = stamps[stamps <= moment]
            if not len(found):
                return 0
            return int(found.index[-1])
        except Exception:                                        # noqa: BLE001
            return None

    def _local_strategy_replay_step(self, symbol: str, price=None,
                                    time_value=None, index=None,
                                    advance=True, reset=False) -> None:
        """本地回放：把策略推进到**当前回放那一根**，并在多合约上成交 ✓

        * 不再用「自己数了几步」当进度（那会和图表脱节：seek 到 30% 时
          策略还在第 1 根 ✗）；现在按前端传来的 `index` 对齐；
        * `reset=True`（进入回放 / 换时间段）→ 策略内部账户归零，历史
          `orders` / `targets` 丢弃，**不产生任何成交**；
        * 只有 `advance=True`（播放 / 前进一根）才运行 `next()`；
        * `set_target_size` 按**目标手数**和本地账户净仓的差额成交，
          成交价用**下单那根 K 线**的收盘价 ✓
        """
        stores = getattr(self, '_local_runners', None) or {}
        if not stores:
            return
        sim = self.local_sim()
        for info in stores.values():
            runner = info.get('runner')
            if runner is None:
                continue
            frames = info.get('frames') or []
            if not frames:
                continue
            target = self._runner_bar_index(info, symbol, index, time_value)
            if target is None:
                continue
            if reset or info.get('replay_index') is None:
                # ★ 进入回放只对齐，不交易（用户要求：点回放不能成交 ✓）
                self._reset_local_runner(info, target)
                continue
            if not advance:
                # 暂停 / 重绘：同一根什么都不用做；如果**位置变了**（seek /
                # 拖动时间轴）则把策略重新对齐到新位置，不补做中间的成交 ✓
                try:
                    current = info.get('replay_index')
                except Exception:                                # noqa: BLE001
                    current = None
                if current is not None and int(current) != target:
                    self._reset_local_runner(info, target)
                    self._prepare_replay_account(info.get('runner'))
                continue
            try:
                previous = int(info.get('replay_index') or 0)
            except (TypeError, ValueError):
                previous = 0
            if target <= previous:
                # ★ 播到末尾后再点 ▶：`Replay.start()` 会直接跳回 30%
                #   （不经过 load → 没有 reset 标记）。这里把"往回跳"也当成
                #   重新开始：策略账户归零，之后从新位置继续交易 ✓
                if target < previous:
                    self._reset_local_runner(info, target)
                    self._prepare_replay_account(info.get('runner'))
                continue
            # ★ 一次播放一根；如果跳了几根（高倍速丢帧 / 前进多根），逐根
            #   补齐 —— 每根仍然只跑一次 next，成交价分别取各自 K 线 ✓
            for bar in range(previous + 1, target + 1):
                runner._replay_index = bar - 1
                try:
                    runner.step_one()
                except Exception as error:                       # noqa: BLE001
                    self.push_log(f'策略回放步进失败：{error!r}', 'warning')
                    break
                info['replay_index'] = bar
                info['steps'] = bar
            orders = list(getattr(runner, 'orders', None) or [])
            # 上一步已经应用过的条数（确定性重放 → 直接切片 ✓）
            applied = int(info.get('orders') or 0)
            if applied > len(orders):
                applied = 0
            for order in orders[applied:]:
                csv_name = str(order.get('symbol') or '')
                side = str(order.get('side') or 'buy')
                size = float(order.get('size') or 0)
                if not csv_name or size <= 0:
                    continue
                fill_price = order.get('price')
                if fill_price is None:
                    fill_price = self._runner_fill_price(
                        info, csv_name, order.get('index'))
                if not fill_price:
                    fill_price = float(sim._price(csv_name) or 0.0)
                if not fill_price:
                    fill_price = float(price or 0)
                try:
                    self._on_local_order({
                        'symbol': csv_name, 'side': side, 'qty': size,
                        'price': float(fill_price), 'auto': True})
                    self.push_log(
                        f'策略回放成交：{csv_name} {side} {size:g} 手',
                        'success')
                except Exception as error:                       # noqa: BLE001
                    self.push_log(
                        f'策略下单失败（{csv_name} {side} {size}）：'
                        f'{error!r}', 'warning')
            info['orders'] = len(orders)
            # ★ `set_target_size()` 写法：目标手数 → 与当前持仓的**差额**下单 ✓
            targets = list(getattr(runner, 'targets', None) or [])
            applied_targets = int(info.get('targets') or 0)
            if applied_targets > len(targets):
                applied_targets = 0
            for target in targets[applied_targets:]:
                csv_name = str(target.get('symbol') or '')
                if not csv_name:
                    continue
                try:
                    want = float(target.get('target') or 0)
                except (TypeError, ValueError):
                    want = 0.0
                # ★ 成交价按**下单那根 K 线**的收盘价（不是"当前价"）：
                #   同一批里可能跨了几根（开仓 / 平仓不在同一根），
                #   用当前价会让开平价相同 → 平仓盈亏恒为 0 ✗
                bar_index = int(target.get('index') or -1)
                fill_price = self._runner_fill_price(
                    info, csv_name, bar_index)
                book = (sim.positions or {}).get(csv_name) or {}
                net = (float(book.get('long') or 0.0)
                       - float(book.get('short') or 0.0))
                delta = want - net
                if abs(delta) < 1e-9:
                    continue
                side = 'buy' if delta > 0 else 'sell'
                # ★ 反手/平仓：目标是**减小**持仓 → 用 `close=True`（先平旧仓，
                #   否则本地账户会同时挂多空两边 ✗ 实测 124 多 + 124 空）
                reducing = ((net > 0 and delta < 0) or (net < 0 and delta > 0))
                # 没有持仓时**绝不能**按"平仓"下单（否则只扣手续费、
                # 不产生持仓 / 盈亏 ✗ 用户实测「只有手续费在统计」）
                if abs(net) < 1e-9:
                    reducing = False
                self.push_log(
                    f'策略目标 {want:g} 手 / 当前 {net:g} 手 → '
                    f'{side} {abs(delta):g} 手'
                    f'{"（平旧仓）" if reducing else ""}', 'info')
                # ★ 优先用**下单那根 K 线**的收盘价（一批里有跨根也不会串价 ✓）
                price_now = float(fill_price or 0.0) or float(
                    sim._price(csv_name) or 0.0)
                # ★ 走**统一的下单入口** `_on_local_order`：
                #   持仓列表 / 委托 / 账户动态 / 图表持仓线 都会一起刷新
                #   （以前直接调 `sim.order` + 手工 push → 只有设置页有数据 ✗）
                try:
                    if abs(delta) > abs(net) and abs(net) > 1e-9:
                        self._on_local_order({
                            'symbol': csv_name, 'side': side,
                            'qty': abs(net), 'price': price_now,
                            'close': True, 'auto': True})
                        rest = abs(delta) - abs(net)
                        if rest > 1e-9:
                            self._on_local_order({
                                'symbol': csv_name, 'side': side,
                                'qty': rest, 'price': price_now,
                                'auto': True})
                    else:
                        self._on_local_order({
                            'symbol': csv_name, 'side': side,
                            'qty': abs(delta), 'price': price_now,
                            'close': reducing, 'auto': True})
                    self.push_log(
                        f"策略回放成交：{csv_name} {side} {abs(delta):g} 手"
                        f"（目标 {want:g}）", 'success')
                except Exception as error:                       # noqa: BLE001
                    self.push_log(
                        f'策略目标手数下单失败（{csv_name} {want}）：'
                        f'{error!r}', 'warning')
            info['targets'] = len(targets)

    def _runner_bar_index(self, info: dict, symbol: str, index,
                          time_value) -> Optional[int]:
        """当前回放根在策略 K 线里的下标（前端 `index` 优先 ✓）"""
        target = index
        if target is None and time_value is not None:
            for name, _frame in (info.get('frames') or []):
                if str(name) == symbol:
                    target = self._replay_index_of_time(str(name), time_value)
                    break
        if target is None:
            return None
        try:
            target = int(target)
        except (TypeError, ValueError):
            return None
        lengths = []
        for _name, frame in (info.get('frames') or []):
            try:
                lengths.append(len(frame))
            except Exception:                                    # noqa: BLE001
                continue
        if lengths:
            target = max(0, min(target, max(lengths) - 1))
        return target

    def _runner_fill_price(self, info: dict, csv_name: str,
                           bar_index, fallback=None) -> float:
        """策略成交价 = **下单那根** K 线的收盘价 ✓"""
        for frame_name, frame_data in (info.get('frames') or []):
            if str(frame_name) != csv_name:
                continue
            try:
                position = max(0, min(int(bar_index), len(frame_data) - 1))
                return float(frame_data.iloc[position].get('close'))
            except (TypeError, ValueError):
                break
            except Exception:                                    # noqa: BLE001
                break
        try:
            return float(self.local_store().bars(csv_name)[-1].get('close'))
        except Exception:                                        # noqa: BLE001
            return float(fallback or 0.0)

    def _reset_local_runner(self, info: dict, index: int) -> None:
        """进入回放 / seek：策略内部账户归零 + 丢弃历史成交 ✓"""
        runner = info.get('runner')
        if runner is None:
            return
        try:
            runner.reset_replay(index)
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'策略回放重置失败：{error!r}', 'warning')
        info['replay_index'] = int(index)
        info['steps'] = int(index)
        info['orders'] = 0
        info['targets'] = 0
        info['last_time'] = None

    def _on_sim_analysis(self, payload=None) -> None:
        """设置页「模拟账户」：权益曲线 / 各品种累计盈亏 / 统计表 ✓"""
        self._push_sim_analysis()

    def _on_sim_reset(self, payload=None) -> None:
        """重置本地模拟账户（现金回到设置的初始现金 ✓）"""
        sim = self.local_sim()
        sim.configure(initial_cash=self._sim_settings()['initial_cash'])
        sim.reset()
        self._push_sim_analysis()
        self._push_sim_accounts()
        self._push_all_sim_positions()
        self.push_log(
            f"本地模拟账户已重置（初始现金 {sim.initial_cash:,.2f}）", 'info')

    def _on_replay_order(self, payload=None) -> None:
        """回放中的下单 → 本地模拟账户（和本地图表同一套 ✓）"""
        payload = payload or {}
        symbol = str(payload.get('symbol') or '')
        sim = self.replay_sim(symbol)
        side = str(payload.get('side') or '')
        qty = payload.get('qty') or 0
        price = payload.get('price') or (self._last_rows.get(symbol, {})
                                        .get('last') or 0)
        result = sim.order(symbol, side, qty, price,
                           bool(payload.get('close')))
        if not result.get('ok'):
            self.push(_protocol.patch_toast(
                f"回放下单失败：{result.get('error')}", 'warning'))
            return
        self.push(self.replay_account_payload(symbol))
        self._push_sim_position(symbol)
        self._push_orders(symbol)
        self._push_sim_analysis()
        self.push_log(f"回放模拟下单：{symbol} {'平仓' if payload.get('close') else '开仓'}",
                      'success')

    def _on_replay_action(self, payload=None) -> None:
        """回放中的 平 / 反 / 全 → 本地模拟账户（和本地图表一致 ✓）"""
        payload = payload or {}
        symbol = str(payload.get('symbol') or '')
        action = str(payload.get('action') or '').lower()
        sim = self.replay_sim(symbol)
        if action == 'all':
            sim.close_all()
            text = '回放模拟账户：平掉全部持仓'
        elif action == 'reverse':
            sim.reverse_all()
            text = '回放模拟账户：反手'
        elif action in ('close', 'close_main'):
            book = (sim.positions or {}).get(symbol) or {}
            long_volume = float(book.get('long') or 0.0)
            short_volume = float(book.get('short') or 0.0)
            if long_volume <= 0 and short_volume <= 0:
                self.push(_protocol.patch_toast(f'{symbol} 没有持仓', 'info'))
                return
            sim.order(symbol, 'sell' if long_volume > 0 else 'buy',
                      long_volume or short_volume, sim._price(symbol), True)
            text = f'回放模拟账户：主价平仓 {symbol}'
        elif action in ('cancel', 'cancel_all'):
            count = sim.cancel_pending(symbol)
            if not count:
                self.push(_protocol.patch_toast('没有未成交的挂单', 'info'))
                return
            text = f'回放模拟账户：已撤 {count} 笔挂单'
        else:
            return
        self.push(self.replay_account_payload(symbol))
        self._push_sim_position(symbol)
        self._push_orders(symbol)
        self._push_sim_analysis()
        self.push_log(text, 'info')

    def _on_remove_strategy(self, payload=None) -> None:
        """删掉图上的策略（指标保留 ✓）"""
        symbol = str((payload or {}).get('symbol') or '')
        if not self._remove_strategy_of(symbol):
            self.push(_protocol.patch_toast('图上没有策略', 'info'))
            return
        self.push(_protocol.patch_toast('已删除策略', 'success'))

    def _on_history_load(self, payload=None) -> None:
        """**无限历史**：图表往左翻到边界时补一批更早的 K 线 ✓

        上限是「设置 → 图表配置 → 期货历史长度」；和历史长度相等时
        （`chart_history == chart_data_length`）就相当于**关闭**无限历史 ✓
        """
        payload = payload or {}
        symbol = str(payload.get('symbol') or '')
        info = self.tabs.get(symbol) or {}
        if not symbol or not info:
            return
        history, data_length = self.chart_lengths()
        loaded = int(info.get('loaded_len') or data_length)
        if loaded >= history:
            self.push({'type': 'history_bars', 'symbol': symbol, 'bars': [],
                       'loaded': loaded, 'exhausted': True})
            return
        page = max(50, min(int(payload.get('page') or 500), 5000))
        want = min(history, loaded + page)
        feed = info.get('feed') or pick_feed(self.feeds, symbol)
        cycle = int(info.get('cycle') or 60)
        frame = feed.klines(symbol, cycle, want) if feed is not None else None
        bars = _protocol.bars_from_frame(frame)
        before = payload.get('before')
        older = bars
        if before is not None:
            try:
                limit = int(float(before))
                older = [bar for bar in bars
                         if int(bar.get('time') or 0) < limit]
            except (TypeError, ValueError):
                older = bars
        info['loaded_len'] = want
        self.tabs[symbol] = info
        self.push({'type': 'history_bars', 'symbol': symbol,
                   'bars': older[-page:] if len(older) > page else older,
                   'loaded': want, 'exhausted': want >= history})
        self.push_log(f'往左补历史：{symbol} → {want} 根'
                      f'（上限 {history}）', 'info')

    def _on_editor_format(self, payload=None) -> None:
        """右键「格式化」（black / yapf → 保守清理 ✓）"""
        from . import explorer as _fs
        payload = payload or {}
        result = _fs.format_python(str(payload.get('text') or ''))
        self.push({'type': 'editor_formatted',
                   'path': str(payload.get('path') or ''),
                   'text': result.get('text') or '',
                   'tool': result.get('tool') or 'basic'})

    def _on_editor_list(self, _payload=None) -> None:
        """文件树：个人指标 / 个人策略 ✓"""
        from . import personal as _pi
        try:
            data = _pi.list_files()
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'读取个人目录失败：{error!r}', 'error')
            data = {'root': _pi.PERSONAL_ROOT,
                    'indicators': [], 'strategies': [], 'error': repr(error)}
        self.push({'type': 'editor_files', **data})

    def _on_editor_open(self, payload) -> None:
        """打开一个文件（读源码 ✓）；顺便记住"上次打开的文件" ✓"""
        from . import personal as _pi
        from . import user_prefs as _prefs
        path = str(payload.get('path') or '')
        if path and os.path.isfile(path):
            _prefs.set_setting('editor_last_file', os.path.abspath(path))
        result = _pi.read_file(path)
        if not result.get('ok'):
            self.push(_protocol.patch_toast(
                str(result.get('error') or '打开失败'), 'warning'))
            return
        self.push({'type': 'editor_file', 'file': result})

    def _on_editor_restore(self, payload=None) -> None:
        """恢复上次打开的文件（资源管理器根目录已由 `explorer_root` 恢复 ✓）

        前端在编辑器第一次显示时发这个命令；文件已经不在了就静默忽略，
        不会弹错误（用户可能删了/改名了 ✓）。
        """
        from . import user_prefs as _prefs
        from . import personal as _pi
        if (payload or {}).get('path'):
            stored = str(payload.get('path'))
        else:
            stored = str(_prefs.settings().get('editor_last_file') or '')
        if not stored or not os.path.isfile(stored):
            return
        result = _pi.read_file(stored)
        if result.get('ok'):
            self.push({'type': 'editor_file', 'file': result})

    def _on_editor_check(self, payload) -> None:
        """只做语法检查（不写盘 ✓）"""
        from . import personal as _pi
        result = _pi.check_source(str(payload.get('text') or ''),
                                  str(payload.get('path') or '<editor>'))
        self.push({'type': 'editor_check', 'path': str(payload.get('path') or ''),
                   'result': result})

    def _on_editor_save(self, payload) -> None:
        """保存源码 → 校验 → **重扫个人目录**（指标立即可用 ✓）"""
        from . import personal as _pi
        path = str(payload.get('path') or '')
        text = str(payload.get('text') or '')
        # ★ 保存时自动格式化（设置里打开才做；只对 .py 且只改空白，不改语义 ✓）
        if payload.get('format') and path.lower().endswith(('.py', '.pyi')):
            from . import explorer as _fs
            formatted = _fs.format_python(text)
            if formatted.get('ok'):
                text = str(formatted.get('text') or text)
        result = _pi.write_file(path, text, root=self.explorer_root())
        if not result.get('ok'):
            self.push({'type': 'editor_check', 'path': path,
                       'result': {'ok': False,
                                  'line': int(result.get('line') or 0),
                                  'error': str(result.get('error') or '保存失败')}})
            self.push(_protocol.patch_toast(
                f'保存失败：{result.get("error")}', 'error'))
            return
        self.push({'type': 'editor_check', 'path': path,
                   'result': _pi.check_source(text, path)})
        self.push({'type': 'editor_saved', 'path': result['path'],
                   'name': result.get('name') or '',
                   'mtime': result.get('mtime'),
                   'text': text})
        self._push_explorer(os.path.dirname(result['path']))
        self.push(_protocol.patch_toast(
            f'已保存 {result.get("name") or ""}', 'success'))
        self.push_log(f'已保存个人源码：{result["path"]}', 'success')
        self._refresh_personal()

    def _on_editor_new(self, payload) -> None:
        """按模板新建（指标 / 策略 ✓）"""
        from . import personal as _pi
        kind = 'strategy' if str(payload.get('kind')) == 'strategy' \
            else 'indicator'
        result = _pi.create_file(kind, str(payload.get('name') or ''),
                                 overwrite=bool(payload.get('overwrite')))
        if not result.get('ok'):
            self.push(_protocol.patch_toast(
                str(result.get('error') or '新建失败'), 'warning'))
            return
        self.push({'type': 'editor_file', 'file': {
            'ok': True, 'path': result['path'], 'name': result['name'],
            'kind': result['kind'], 'text': result.get('text') or '',
            'mtime': 0.0, 'new': True}})
        self.push({'type': 'editor_saved', 'path': result['path'],
                   'name': result['name'], 'mtime': 0.0})
        self._push_explorer(os.path.dirname(result['path']))
        self._refresh_personal()

    def _on_editor_delete(self, payload) -> None:
        """删文件 ✓"""
        from . import personal as _pi
        result = _pi.delete_file(str(payload.get('path') or ''))
        if not result.get('ok'):
            self.push(_protocol.patch_toast(
                str(result.get('error') or '删除失败'), 'warning'))
            return
        self.push({'type': 'editor_deleted', 'path': result['path']})
        self._push_explorer(os.path.dirname(result['path']))
        self.push(_protocol.patch_toast('已删除', 'success'))
        self._on_editor_list({})
        self._refresh_personal()

    def _refresh_personal(self) -> None:
        """重扫个人目录 → 刷新指标菜单 / 选择器的「个人」分组 ✓"""
        try:
            items = []
            from . import personal as _pi
            for entry in _pi.scan('indicator'):
                items.append({'key': entry['key'], 'label': entry['name'],
                              'group': f'个人·{entry.get("category") or ""}',
                              'overlap': bool(entry.get('overlap')),
                              'params': entry.get('params') or []})
            if items:
                self.push({'type': 'indicator_menu', 'symbol': '',
                           'items': items, 'personal': True})
        except Exception as error:                               # noqa: BLE001
            self.push_log(f'刷新个人指标失败：{error!r}', 'warning')

    def _on_personal_menu(self, payload) -> None:
        """个人指标/策略的目录列表（前端「管理」用 ✓）"""
        from . import personal as _pi
        from . import explorer as _fs
        roots = {_fs._norm(item) for item in
                 (_pi.ensure_directories() or {}).values() if item}
        self.push({'type': 'personal_menu', 'items': [
            {'category': entry['category'], 'path': entry['path'],
             'kind': entry['kind'],
             'default': _fs._norm(entry['path']) in roots}
            for entry in _pi.directories()]})

    def _on_pick_personal(self, payload) -> None:
        """选目录（Qt 弹系统对话框；浏览器壳 → 提示用 CLI ✓）"""
        from . import personal as _pi
        kind = 'strategy' if str(payload.get('kind')) == 'strategy' \
            else 'indicator'
        path = self.choose_directory(
            f'选择{"策略" if kind == "strategy" else "指标"}目录')
        if not path:
            self.push_log('已取消选择目录', 'info')
            return
        result = _pi.add_directory(path, kind)
        if not result.get('ok'):
            self.push_log(f'导入目录失败：{result.get("error")}', 'error')
            self.push(_protocol.patch_toast(
                str(result.get('error') or '导入失败'), 'warning'))
            return
        self.push_log(f'已导入{("策略" if kind == "strategy" else "指标")}目录：'
                      f'{result["category"]} ({result["path"]})', 'success')
        self.push(_protocol.patch_toast(
            f'已导入 {result["category"]}（下次启动自动加载 ✓）', 'success'))
        self._on_personal_menu({})
        self._on_indicator_menu({'symbol': next(iter(self.tabs), '')})

    def _on_personal_add_dir(self, payload=None) -> None:
        """按**路径**导入个人指标 / 策略目录（浏览器壳兜底 ✓）"""
        from . import personal as _pi
        payload = payload or {}
        kind = 'strategy' if str(payload.get('kind')) == 'strategy'             else 'indicator'
        result = _pi.add_directory(str(payload.get('path') or ''), kind=kind)
        if not result.get('ok'):
            self.push_log(f'导入目录失败：{result.get("error")}', 'error')
            self.push(_protocol.patch_toast(
                str(result.get('error') or '导入失败'), 'warning'))
            return
        scanned = _pi.scan(kind)
        self.push_log(f'已收录目录 {result["category"]}：扫到 {len(scanned)} 个'
                      f'{"策略" if kind == "strategy" else "指标"}', 'info')
        self.push_log(f'已导入目录：{result["category"]} ({result["path"]})',
                      'success')
        self.push(_protocol.patch_toast(
            f'已导入 {result["category"]}（下次启动自动加载 ✓）', 'success'))
        self._on_personal_menu({})
        self._on_indicator_menu({'symbol': next(iter(self.tabs), '')})

    def _on_drop_personal(self, payload) -> None:
        """删除一个个人目录（按 category 或 path ✓）"""
        from . import personal as _pi
        key = str(payload.get('category') or payload.get('path') or '')
        if not key or not _pi.remove_directory(key):
            self.push(_protocol.patch_toast(f'没找到 {key}', 'warning'))
            return
        self.push_log(f'已移除个人脚本：{key}', 'warning')
        self.push(_protocol.patch_toast(f'已移除 {key}', 'success'))
        self._on_personal_menu({})

    def _on_set_theme(self, payload) -> None:
        """前端切主题 → 记住（下次启动沿用 ✓），并广播给所有表页"""
        theme = str(payload.get('theme') or '')
        if theme in ('light', 'dark'):
            self.theme = theme
            self.push({'type': 'theme', 'theme': theme})

    def _on_trading_state(self, payload) -> None:
        self.push(self.trading_state(next(iter(self.tabs), '')))

    def _push_tab_orders(self, symbol: str = '') -> None:
        """下单 / 撤单之后立刻刷挂单线（回放走本地模拟账户 ✓）"""
        for item in ([symbol] if symbol else list(self.tabs)[:6]):
            if not item:
                continue
            self._push_orders(item, local=item in self.replay_symbols)

    def _on_place_order(self, payload) -> None:
        """下单（前端已做过二次确认；这里只负责执行 + 结果提示 ✓）"""
        trader = self.trading_view()
        if trader is None:
            self.push(_protocol.patch_toast('交易未启用', 'warning'))
            return
        symbol = str(payload.get('symbol') or '')
        side = str(payload.get('side') or 'buy')
        # ★ 前端交易面板发的是 `qty`，以前只读 `volume` → 永远下 1 股/手 ✗
        volume = int(payload.get('volume') or payload.get('qty') or 1)
        price = payload.get('price')
        # ★ 交易面板的「平仓」按钮带 `close=true`：转成平仓方向（不是反手开仓 ✗）
        if payload.get('close'):
            side = 'close'
        guard = self._risk_guard(symbol, side, volume,
                                 float(price) if price else None)
        if not guard.get('ok'):
            self.push(_protocol.patch_toast(str(guard.get('text')),
                                            'warning'))
            return
        text = trader.place(symbol, side, volume,
                            float(price) if price else None)
        from .trading import _trade_failed
        ok = not _trade_failed(text)
        self._audit_action('order', text, symbol=symbol, side=side,
                           volume=volume, price=price,
                           status='PENDING' if ok else 'REJECTED')
        self.push(_protocol.patch_toast(text, 'success' if ok else 'warning'))
        self.push(self.account_payload(symbol=next(iter(self.tabs), '')))
        self._push_tab_orders(symbol)        # 挂单线立刻出现 ✓
        try:
            pending = self.pending_orders(symbol)
        except Exception:                                        # noqa: BLE001
            pending = []
        if pending:
            self.push_log(f'{symbol} 当前挂单 {len(pending)} 笔'
                          '（图上会画挂单线）', 'info')

    def _on_focus_chart(self, payload=None) -> None:
        """记住**鼠标最后点击的那张图**的合约（平仓/反手/撤单作用在它上面 ✓）"""
        symbol = str((payload or {}).get('symbol') or '')
        if symbol:
            self.last_symbol = symbol

    def _on_position_action(self, payload) -> None:
        """持仓行右键：平（市价平该合约）/ 反（市价平 + 反向开）/ 全（全平）✓"""
        payload = payload or {}
        action = str(payload.get('action') or '')
        symbol = str(payload.get('symbol') or '')
        try:
            volume = int(payload.get('volume') or 0)
        except (TypeError, ValueError):
            volume = 0
        trader = self.trading_view()
        if trader is None:
            self.push(_protocol.patch_toast('交易未启用', 'warning'))
            return
        if action == 'close':
            text = trader.close_symbol(symbol, volume)
        elif action == 'reverse':
            text = trader.reverse_symbol(symbol, volume)
        elif action == 'all':
            text = trader.action('all', symbol)
        else:
            return
        self._audit_action('order', text, symbol=symbol, side=action,
                           volume=volume, status='PENDING')
        from .trading import _trade_failed
        ok = not _trade_failed(text)
        self.push(_protocol.patch_toast(text, 'success' if ok else 'warning'))
        self.push(self.account_payload(symbol=next(iter(self.tabs), '')))
        if symbol:
            self.push(self.position_payload(symbol))
            self._push_orders(symbol)

    def _on_order_action(self, payload) -> None:
        """委托行右键：撤（该笔）/ 全（全撤）✓"""
        payload = payload or {}
        action = str(payload.get('action') or '')
        symbol = str(payload.get('symbol') or '')
        order_id = str(payload.get('order_id') or '')
        trader = self.trading_view()
        if trader is None:
            self.push(_protocol.patch_toast('交易未启用', 'warning'))
            return
        if action == 'cancel':
            text = trader.cancel_order(order_id, symbol)
        elif action == 'cancel_all':
            text = trader.action('cancel_all', symbol)
        else:
            return
        self._audit_action('cancel', text, symbol=symbol,
                           status='CANCELLED')
        from .trading import _trade_failed
        ok = not _trade_failed(text)
        self.push(_protocol.patch_toast(text, 'success' if ok else 'warning'))
        self.push(self.account_payload(symbol=next(iter(self.tabs), '')))
        if symbol:
            self._push_orders(symbol)

    def _on_account_action(self, payload) -> None:
        """平 / 反 / 全 / 撤 / 全撤（作用在**鼠标最后点击的图表合约**上 ✓）"""
        trader = self.trading_view()
        if trader is None:
            self.push(_protocol.patch_toast('交易未启用', 'warning'))
            return
        action = str(payload.get('action') or '')
        symbol = str(payload.get('symbol') or '') or getattr(
            self, 'last_symbol', '')
        if not symbol and self.tabs:
            symbol = next(iter(self.tabs))
        text = trader.action(action, symbol)
        self._audit_action('order', text, symbol=symbol, side=action,
                           status='PENDING')
        from .trading import _trade_failed
        ok = not _trade_failed(text)
        self.push(_protocol.patch_toast(text, 'success' if ok else 'warning'))
        self.push(self.account_payload(symbol=next(iter(self.tabs), '')))
        self._push_tab_orders()              # 撤单 / 平仓后挂单线跟着变 ✓

    # ======================================================== 扩展功能
    #: 工作台导出目录
    def _export_dir(self) -> str:
        path = os.path.join(os.path.expanduser('~'), '.minibt', 'desk',
                            'exports')
        os.makedirs(path, exist_ok=True)
        return path

    def _push_workbench(self) -> None:
        bench = self.workbench_view()
        if bench is not None:
            self.push(bench.snapshot())

    def _on_workbench(self, payload=None) -> None:
        """打开「交易工作台」：推一次完整快照 ✓"""
        self._push_workbench()

    def _on_workbench_submit(self, payload) -> None:
        """订单票下单（市价 / 限价 / 止损 / 条件单）✓"""
        bench = self.workbench_view()
        if bench is None:
            self.push(_protocol.patch_toast('交易工作台不可用', 'warning'))
            return
        result = bench.submit(payload or {})
        self.push(_protocol.patch_toast(
            str(result.get('text') or ''),
            'success' if result.get('ok') else 'warning'))
        self.push(bench.snapshot())
        symbol = str((payload or {}).get('symbol') or '')
        self.push(self.account_payload(symbol=symbol))
        if symbol:
            self._push_orders(symbol)

    def _on_workbench_cancel(self, payload) -> None:
        payload = payload or {}
        bench = self.workbench_view()
        if bench is None:
            return
        result = bench.cancel(str(payload.get('order_id') or ''),
                              str(payload.get('symbol') or ''),
                              all_orders=bool(payload.get('all')),
                              local_id=int(payload.get('id') or 0))
        self.push(_protocol.patch_toast(
            str(result.get('text') or ''),
            'success' if result.get('ok') else 'warning'))
        self.push(bench.snapshot())
        self._push_tab_orders(str(payload.get('symbol') or ''))

    def _on_workbench_modify(self, payload) -> None:
        bench = self.workbench_view()
        if bench is None:
            return
        result = bench.modify(payload or {})
        self.push(_protocol.patch_toast(
            str(result.get('text') or ''),
            'success' if result.get('ok') else 'warning'))
        self.push(bench.snapshot())

    def _on_workbench_close_partial(self, payload) -> None:
        bench = self.workbench_view()
        if bench is None:
            return
        result = bench.close_partial(payload or {})
        self.push(_protocol.patch_toast(
            str(result.get('text') or ''),
            'success' if result.get('ok') else 'warning'))
        self.push(bench.snapshot())
        self.push(self.account_payload(
            symbol=str((payload or {}).get('symbol') or '')))

    def _on_workbench_limits(self, payload) -> None:
        bench = self.workbench_view()
        if bench is None:
            return
        limits = bench.configure((payload or {}).get('limits') or payload)
        self.push(bench.snapshot())
        self.push(_protocol.patch_toast(
            '风控已更新（' + ('启用' if limits.get('enabled') else '未启用')
            + '）', 'success'))

    def _on_workbench_conditional_cancel(self, payload) -> None:
        bench = self.workbench_view()
        if bench is None:
            return
        cond_id = str((payload or {}).get('id') or '')
        removed = bench.cancel_conditional(cond_id)
        self.push(_protocol.patch_toast(
            '已撤销条件单' if removed else '找不到这个条件单',
            'info' if removed else 'warning'))
        self.push(bench.snapshot())

    def _on_workbench_reconcile(self, payload=None) -> None:
        bench = self.workbench_view()
        if bench is None:
            return
        result = bench.reconcile()
        self.push(bench.snapshot())
        self.push(_protocol.patch_toast(
            f"对账：本地 {result.get('local_open')} / 券商 "
            f"{result.get('broker_open')} / 差异 "
            f"{len(result.get('missing') or []) + len(result.get('extra') or [])}",
            'success' if result.get('ok') else 'warning'))

    def _on_workbench_export(self, payload=None) -> None:
        bench = self.workbench_view()
        if bench is None:
            return
        table = 'audit' if str((payload or {}).get('table')) == 'audit' \
            else 'orders'
        name = f'workbench_{table}_{time.strftime("%Y%m%d_%H%M%S")}.csv'
        path = bench.store.export_csv(os.path.join(self._export_dir(), name),
                                      table=table)
        self.push_log(f'工作台 {table} 已导出：{path}', 'success')
        self.push(_protocol.patch_toast(
            f'已导出 {table}：{os.path.basename(path)}', 'success',
            actions=[{'label': '打开文件', 'cmd': 'open_export',
                      'payload': {'path': path}},
                     {'label': '打开文件夹', 'cmd': 'open_export',
                      'payload': {'path': path, 'folder': True}}],
            detail=path))

    # -------------------------------------------------------- 研究平台
    def _on_research(self, payload=None) -> None:
        lab = self.research_view()
        if lab is not None:
            self.push(lab.snapshot())

    def _on_research_start(self, payload) -> None:
        lab = self.research_view()
        if lab is None:
            self.push(_protocol.patch_toast('研究平台不可用', 'warning'))
            return
        lab.start(payload or {})
        self.push(_protocol.patch_toast('研究任务已开始', 'info'))

    def _on_research_cancel(self, payload=None) -> None:
        lab = self.research_view()
        if lab is not None:
            lab.cancel()
            self.push(_protocol.patch_toast('已请求取消（当前窗口结束后停止）',
                                            'info'))

    def _on_research_report(self, payload) -> None:
        lab = self.research_view()
        if lab is None:
            return
        try:
            path = lab.report(int((payload or {}).get('experiment') or 0),
                              str((payload or {}).get('path') or ''))
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'导出报告失败：{error}',
                                            'warning'))
            return
        self.push_log(f'研究报告已导出：{path}', 'success')
        self.push(_protocol.patch_toast(
            f'报告已导出：{os.path.basename(path)}', 'success',
            actions=[{'label': '打开文件', 'cmd': 'open_export',
                      'payload': {'path': path}},
                     {'label': '打开文件夹', 'cmd': 'open_export',
                      'payload': {'path': path, 'folder': True}}],
            detail=path))
        self.push(lab.snapshot())

    def _on_research_delete(self, payload) -> None:
        lab = self.research_view()
        if lab is None:
            return
        ok = lab.store.delete(int((payload or {}).get('experiment') or 0))
        self.push(_protocol.patch_toast('实验已删除' if ok else '实验不存在',
                                        'info' if ok else 'warning'))
        self.push(lab.snapshot())

    # -------------------------------------------------------- 数据平台
    def _on_datahub(self, payload=None) -> None:
        hub = self.datahub_view()
        if hub is None:
            return
        hub.refresh()
        self.push(hub.snapshot())

    def _on_datahub_refresh(self, payload=None) -> None:
        hub = self.datahub_view()
        if hub is None:
            return
        folder = str((payload or {}).get('folder') or '')
        if folder and hub.add_folder(folder):
            self.push_log(f'数据平台已添加目录：{folder}', 'info')
        hub.refresh(force=True)
        self.push(hub.snapshot())
        self.push(_protocol.patch_toast(
            f'行情库：{len(hub.items())} 个文件', 'info'))

    def _on_datahub_quality(self, payload) -> None:
        hub = self.datahub_view()
        if hub is None:
            return
        name = str((payload or {}).get('name') or '')
        try:
            report = hub.quality(name, force=True)
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'质量检查失败：{error}',
                                            'warning'))
            return
        self.push({'type': 'datahub_quality', 'name': name,
                   'report': report})
        self.push(hub.snapshot())

    def _on_datahub_resample(self, payload) -> None:
        hub = self.datahub_view()
        if hub is None:
            return
        name = str((payload or {}).get('name') or '')
        rule = str((payload or {}).get('rule') or '5min')
        try:
            frame = hub.resample(name, rule)
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'重采样失败：{error}', 'warning'))
            return
        bars = _protocol.bars_from_frame(frame)
        self.push({'type': 'datahub_result', 'name': name,
                   'action': 'resample', 'rule': rule, 'bars': bars,
                   'rows': len(bars)})
        self.push(_protocol.patch_toast(
            f'{name} → {rule}：{len(bars)} 根', 'success'))

    def _on_datahub_roll(self, payload) -> None:
        hub = self.datahub_view()
        if hub is None:
            return
        names = (payload or {}).get('names') or []
        if isinstance(names, str):
            names = [item for item in names.replace(',', ' ').split() if item]
        mode = str((payload or {}).get('mode') or 'ratio')
        try:
            frame = hub.roll(names, mode=mode)
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'换月拼接失败：{error}',
                                            'warning'))
            return
        bars = _protocol.bars_from_frame(frame)
        self.push({'type': 'datahub_result', 'name': '+'.join(names),
                   'action': 'roll', 'mode': mode, 'bars': bars,
                   'rows': len(bars)})
        self.push(_protocol.patch_toast(
            f"换月拼接（{mode}）：{len(bars)} 根", 'success'))

    def _on_datahub_ticks(self, payload) -> None:
        hub = self.datahub_view()
        if hub is None:
            return
        name = str((payload or {}).get('name') or '')
        seconds = int((payload or {}).get('seconds') or 60)
        try:
            frame = hub.ticks(name, seconds=seconds)
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'Tick 聚合失败：{error}',
                                            'warning'))
            return
        bars = _protocol.bars_from_frame(frame)
        self.push({'type': 'datahub_result', 'name': name,
                   'action': 'ticks', 'seconds': seconds, 'bars': bars,
                   'rows': len(bars)})
        self.push(_protocol.patch_toast(
            f'{name} Tick → {seconds}s：{len(bars)} 根', 'success'))

    def _on_datahub_query(self, payload) -> None:
        hub = self.datahub_view()
        if hub is None:
            return
        sql = str((payload or {}).get('sql') or '')
        try:
            rows = hub.query(sql, limit=int((payload or {}).get('limit')
                                            or 2000))
        except Exception as error:                               # noqa: BLE001
            self.push({'type': 'datahub_query', 'ok': False,
                       'message': f'{type(error).__name__}: {error}',
                       'rows': []})
            return
        self.push({'type': 'datahub_query', 'ok': True, 'rows': rows,
                   'message': f'{len(rows)} 行'})

    def _on_datahub_export(self, payload) -> None:
        hub = self.datahub_view()
        if hub is None:
            return
        name = str((payload or {}).get('name') or '')
        target = str((payload or {}).get('path') or '')
        if not target:
            target = os.path.join(self._export_dir(), f'{name}.parquet')
        try:
            path = hub.export_parquet(name, target)
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'导出 Parquet 失败：{error}',
                                            'warning'))
            return
        self.push_log(f'Parquet 已导出：{path}', 'success')
        self.push(_protocol.patch_toast(
            f'Parquet 已导出：{os.path.basename(path)}', 'success',
            actions=[{'label': '打开文件夹', 'cmd': 'open_export',
                      'payload': {'path': path, 'folder': True}}],
            detail=path))

    # -------------------------------------------------------- 平台 / 运维
    def _on_ops(self, payload=None) -> None:
        ops = self.ops_view()
        if ops is not None:
            self.push(ops.snapshot())

    def _on_ops_token_issue(self, payload) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        item = ops.tokens.issue(
            str((payload or {}).get('name') or 'api').strip() or 'api',
            scopes=(payload or {}).get('scopes') or ['read'],
            ttl=int((payload or {}).get('ttl') or 0),
            note=str((payload or {}).get('note') or ''))
        self.push({'type': 'ops_token', 'token': item})
        self.push(ops.snapshot())
        self.push(_protocol.patch_toast(
            'Token 已生成（只显示一次，请立刻复制）', 'success',
            detail=str(item.get('token') or '')))

    def _on_ops_token_revoke(self, payload) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        ok = ops.tokens.revoke(str((payload or {}).get('id') or ''))
        self.push(_protocol.patch_toast('Token 已撤销' if ok else '找不到 token',
                                        'info' if ok else 'warning'))
        self.push(ops.snapshot())

    def _on_ops_token_revoke_all(self, payload=None) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        count = ops.tokens.revoke_all()
        self.push(_protocol.patch_toast(f'已撤销 {count} 个 token', 'info'))
        self.push(ops.snapshot())

    def _on_ops_task_add(self, payload) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        try:
            task = ops.tasks.add(
                str((payload or {}).get('name') or ''),
                int((payload or {}).get('interval') or 60),
                str((payload or {}).get('action')
                    or (payload or {}).get('name') or 'heartbeat'),
                payload=(payload or {}).get('payload'),
                enabled=bool((payload or {}).get('enabled', True)))
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'添加任务失败：{error}',
                                            'warning'))
            return
        self.push({'type': 'ops_tasks', 'results': [],
                   'tasks': ops.tasks.snapshot()})
        self.push(_protocol.patch_toast(
            f"任务 {task.get('name')} 每 {task.get('interval')}s 运行",
            'success'))
        self.push(ops.snapshot())

    def _on_ops_task_remove(self, payload) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        ok = ops.tasks.remove(str((payload or {}).get('name') or ''))
        self.push(_protocol.patch_toast('任务已删除' if ok else '任务不存在',
                                        'info' if ok else 'warning'))
        self.push(ops.snapshot())

    def _on_ops_task_toggle(self, payload) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        ok = ops.tasks.enable(str((payload or {}).get('name') or ''),
                              bool((payload or {}).get('enabled')))
        self.push(_protocol.patch_toast('已更新' if ok else '任务不存在',
                                        'info' if ok else 'warning'))
        self.push(ops.snapshot())

    def _on_ops_task_run(self, payload=None) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        name = str((payload or {}).get('name') or '').strip()
        results = ops.tasks.run(name) if name else ops.run_tasks()
        self.push({'type': 'ops_tasks', 'results': results,
                   'tasks': ops.tasks.snapshot()})
        self.push(ops.snapshot())

    def _on_ops_notify_config(self, payload) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        kind = str((payload or {}).get('kind') or 'wecom')
        block = ops.notifier.configure(kind, (payload or {}).get('values') or {})
        self.push({'type': 'ops_notify', 'kind': kind, 'values': block,
                   'notify': ops.notifier.snapshot()})
        self.push(_protocol.patch_toast('告警通道已保存', 'success'))

    def _on_ops_notify_test(self, payload=None) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        record = ops.notify('minibt desk 测试告警',
                            '这是一条测试消息；看到就说明通道可用 ✓',
                            level='info')
        ok = all(item.get('ok') for item in record.get('results') or [])
        self.push({'type': 'ops_notify', 'notify': ops.notifier.snapshot()})
        self.push(_protocol.patch_toast(
            '测试告警已发送' if ok else '测试告警部分失败（看明细）',
            'success' if ok else 'warning',
            detail='；'.join(f"{item.get('channel')}: {item.get('detail')}"
                            for item in record.get('results') or [])))

    def _on_ops_version_snapshot(self, payload) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        path = str((payload or {}).get('path') or '')
        try:
            record = ops.versions.snapshot(
                path, str((payload or {}).get('note') or ''))
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'版本快照失败：{error}',
                                            'warning'))
            return
        self.push({'type': 'ops_versions', 'path': path,
                   'items': ops.versions.items(path)})
        self.push(_protocol.patch_toast(
            f"已保存版本 {record.get('version')}", 'success'))

    def _on_ops_versions(self, payload) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        path = str((payload or {}).get('path') or '')
        self.push({'type': 'ops_versions', 'path': path,
                   'items': ops.versions.items(path)})

    def _on_ops_version_rollback(self, payload) -> None:
        ops = self.ops_view()
        if ops is None:
            return
        path = str((payload or {}).get('path') or '')
        try:
            result = ops.versions.rollback(
                path, str((payload or {}).get('version') or ''))
        except Exception as error:                               # noqa: BLE001
            self.push(_protocol.patch_toast(f'回滚失败：{error}', 'warning'))
            return
        self.push({'type': 'ops_versions', 'path': path,
                   'items': ops.versions.items(path)})
        self.push(_protocol.patch_toast(
            f"已回滚到 {result.get('version')}", 'success'))

    def _on_reload_contracts(self, payload) -> None:
        """「刷新」：**绕过缓存**重新拉当前类型/交易所的合约 ✓"""
        self._cache_bust = True
        self._skip_markets.clear()          # 用户主动重试 → 允许再试一次 ✓
        reset = getattr(self.futures, 'reset_symbols', None)
        if callable(reset):
            try:
                reset(self.filter.get('type') or '',
                      self.filter.get('exchange') or '', force=True)
            except TypeError:
                try:
                    reset(self.filter.get('type') or '',
                          self.filter.get('exchange') or '')
                except Exception:                            # noqa: BLE001
                    pass
            except Exception:                                # noqa: BLE001
                pass
        self.reload_rows()

    def _on_account(self, payload) -> None:
        """切回看盘 tab / 刷新按钮 → 立刻推一次账户面板 ✓"""
        self.push(self.account_payload(symbol=next(iter(self.tabs), '')))

    def _restart_chart_strategies_for_account(self) -> None:
        """切账户后，图表里的策略要按**新账户**重新绑定/运行 ✓

        旧 runner / TqObjs 还指向旧账户；只改 AccountView.index 不会影响它。
        这里先清掉旧策略，再用同一文件按当前合约重跑一遍。
        """
        for symbol, info in list(self.tabs.items()):
            path = str((info.get('strategy') or {}).get('path') or '')
            if not path:
                continue
            old = dict(info)
            # ★ 天勤 `Base._tqobjs` 是全局缓存（按合约名）；不删的话
            #   新账户还会复用旧账户的 TqObjs / TargetPosTask → 仍下到旧账户 ✗
            try:
                from ..utils import Base as _Base
                old_runner = info.get('strategy_runner')
                names = list(symbol)
                if old_runner is not None and hasattr(old_runner,
                                                       'update_symbols'):
                    names += list(old_runner.update_symbols())
                for name in names:
                    _Base._tqobjs.pop(str(name or ''), None)
            except Exception:                                    # noqa: BLE001
                pass
            for key in ('strategy_items', 'strategy', 'strategy_runner',
                        'strategy_config', '_strat_stamp', '_strat_at',
                        'strategy_groups', '_strat_frame_cache'):
                info.pop(key, None)
            try:
                feed = info.get('feed') or pick_feed(self.feeds, symbol)
                cycle = int(info.get('cycle') or 60)
                frame = (feed.klines(symbol, cycle, self.tab_length(info))
                         if feed is not None else None)
                if frame is not None:
                    self._add_strategy_to_chart(
                        symbol, path, frame, cycle,
                        cls_name=str((old.get('strategy') or {}).get('name')
                                     or ''))
                    self.push(self.indicator_payload(symbol))
            except Exception as error:                           # noqa: BLE001
                self.push_log(
                    f'切换账户后重绑策略 {symbol} 失败：{error!r}', 'warning')
                # 失败也别让旧策略复活
                for key in ('strategy_items', 'strategy',
                            'strategy_runner'):
                    info.pop(key, None)
                _ = old

    def _on_switch_account(self, payload) -> None:
        """账户页切换：快期模拟 / 实盘（TqMultiAccount ✓）

        切换是**全局**的：图表策略、策略实盘都跟随；旧账户已成交持仓不会自动平。
        """
        view = self.account_view()
        if view is None:
            return
        try:
            index = int(payload.get('index') or 0)
        except (TypeError, ValueError):
            index = 0
        old_index = int(view.index)
        view.switch(index)
        if old_index == view.index:
            return
        # ★ TargetPosTask 是**按 symbol 缓存**的，里面绑定了旧 account →
        #   不清的话「平/反/全」还会发到旧模拟/实盘账户 ✗
        trader = getattr(self, 'trader', None)
        if trader is not None:
            try:
                trader.clear_account_cache()
            except Exception as error:                           # noqa: BLE001
                self.push_log(f'清理旧账户目标仓缓存失败：{error!r}', 'warning')
        labels = view.labels()
        current = labels[view.index] if labels else ''
        try:
            self._real_account = bool(str(_field_any_local(
                view.current(), ('broker_id',)) or ''))
        except Exception:                                        # noqa: BLE001
            pass
        self.push_log(f'切换交易账户 → {current}', 'success')
        # 图表策略重新绑定到当前账户 ✓
        self._restart_chart_strategies_for_account()
        # 策略实盘如果正在跑：用同一文件/参数按新账户重启（**所有** ✓）
        self._restart_strategy_live_all()
        self.push(self.account_payload(symbol=next(iter(self.tabs), '')))

    def _on_book(self, payload) -> None:
        """前端刚打开 tab / 切回页面 → 立刻推一次二级报价 ✓"""
        symbol = str(payload.get('symbol') or '')
        if symbol:
            self.push(self.book_payload(symbol))

    def _on_row_click(self, payload) -> None:
        """左键 → 「合约概览」气泡（当前行数据 + 走势缓存 ✓）"""
        symbol = str(payload.get('symbol') or '')
        if not symbol:
            return
        row = dict(self._last_rows.get(symbol) or
                   _symbols.row(symbol=symbol,
                                name=str(payload.get('name') or '')))
        # ★ 首页自选行自带数字 → 合并进来（离线 / 未打开报价页也能显示 ✓）
        given = payload.get('row')
        if isinstance(given, dict):
            for key, value in given.items():
                if value is not None and row.get(key) in (None, ''):
                    row[key] = value
            for key in ('last', 'chg', 'chg_pct', 'open', 'high', 'low',
                        'pre_close', 'volume', 'name'):
                if given.get(key) is not None:
                    row[key] = given[key]
        feed = pick_feed(self.feeds, symbol) or self.current_feed()
        if not row.get('name') and feed is not None:
            row['name'] = feed.name_of(symbol)
        if not row.get('last') and feed is not None and feed.available():
            quotes = feed.quotes([symbol])
            if quotes:
                row.update({key: value for key, value in quotes[0].items()
                            if value is not None})
        data = {key: row.get(key) for key in (
            'symbol', 'name', 'last', 'chg', 'chg_pct', 'open', 'high',
            'low', 'pre_close', 'volume', 'decimals')}
        if data.get('decimals') is None:
            data['decimals'] = self.decimals_of(symbol)   # 气泡同一套小数位 ✓
        data['spark'] = self.spark_values(symbol)
        self.push(_protocol.patch_preview(data, payload.get('x') or 0,
                                          payload.get('y') or 0))

    def _on_context_menu(self, payload) -> None:
        """右键 → 周期菜单（选完前端直接开图，不用再来回一次 ✓）"""
        symbol = str(payload.get('symbol') or '')
        if not symbol:
            return
        self.push(_protocol.patch_menu(payload.get('x') or 0,
                                       payload.get('y') or 0, symbol,
                                       str(payload.get('name') or '')))

    def symbol_issue(self, symbol: str) -> str:
        """开图前的合约体检：返回**问题描述**（空串 = 没问题 ✓）

        检查：① 报文格式 `EXCHANGE.code`；② 是否在已知合约里；
        ③ 行情源在不在；④ 能不能取到 K 线。都不阻塞（只做判断 ✓）
        """
        symbol = str(symbol or '').strip()
        if not symbol:
            return '合约代码为空'
        if '.' not in symbol:
            return f'{symbol} 不是合法合约代码（应形如 SHFE.rb2601）'
        feed = pick_feed(self.feeds, symbol)
        if feed is None:
            return '当前没有连接行情源（先登录期货 / 连接股票）'
        if not feed.available():
            return '行情源未连接'
        # 合约存在性：报价行 / 缓存池 / 全市场索引 / 名称缓存 任一命中即可 ✓
        known = (symbol in self._last_rows
                 or any(str(row.get('symbol')) == symbol
                        for row in (self.search_pool() or []))
                 or bool(feed.name_of(symbol))
                 or any(str(row.get('symbol')) == symbol
                        for row in (self.symbol_index() or [])))
        if not known:
            return (f'{symbol} 不在当前合约清单里'
                    '（可能不存在 / 没有行情权限）')
        return ''

    def _on_open_chart(self, payload) -> None:
        symbol = str(payload.get('symbol') or '')
        if not symbol:
            return
        issue = ''
        try:
            issue = self.symbol_issue(symbol)
        except Exception:                                        # noqa: BLE001
            issue = ''
        feed = pick_feed(self.feeds, symbol)
        # ★ 一般桌面端开图：合约没在缓存里 → 先强制重取一次合约清单；
        #   仍找不到才提醒并跳过（用户要求：不要第一次误杀合法合约）✓
        if issue and feed is not None and getattr(
                feed, 'available', lambda: False)()                 and not _is_stock(symbol) and not symbol.startswith('KQ.'):
            exchange = symbol.split('.')[0].upper()
            known = self._refresh_futures_contracts(feed, exchange)
            if symbol in known:
                issue = ''
        if issue:
            self.push_log(f'打开图表：{issue}', 'warning')
            self.push(_protocol.patch_toast(f'打开图表：{issue}', 'warning'))
            if (feed is not None
                    and getattr(feed, 'available', lambda: False)()
                    and not _is_stock(symbol)
                    and not symbol.startswith('KQ.')):
                self.push_alert('合约不存在 / 无法加载',
                                issue, detail=symbol, level='warning')
                return
        cycle = int(payload.get('cycle') or (86400 if _is_stock(symbol) else 60))
        # 保留已有状态（指标选择、指标节流时间戳…）✓
        info = dict(self.tabs.get(symbol) or {})
        info.update({'feed': feed, 'cycle': cycle})
        self.tabs[symbol] = info
        self.push(_protocol.patch_open_tab(symbol,
                                           str(payload.get('name') or ''),
                                           cycle))
        # ★ 初始长度 = 设置 → 图表配置 → 期货数据长度（`chart_data_length`）；
        #   指标 / 策略使用同一个 `tab_length`，避免左侧只有指标线、没有 K 线 ✗
        data_length = self.data_length()
        frame = feed.klines(symbol, cycle, data_length) if feed else None
        info['loaded_len'] = data_length
        self.tabs[symbol] = info
        bars = _protocol.bars_from_frame(frame)
        self._reset_kline_state(info)
        self._note_kline_state(
            info, bars, len(frame) if frame is not None else 0)
        self.push(_protocol.patch_kline(symbol, bars, True))
        if not bars:
            # 天勤刚订阅时返回的是**定长占位表**（时间 0 / 价格 NaN）→
            # 不是“没数据”，而是历史还在路上（`_fast_call` 不等初始化 ✓），
            # 下一拍 `_refresh_tabs` 会自动全量补上 ✓
            if frame is not None and len(frame):
                self.push_log(f'{symbol} K 线加载中…', 'info')
            else:
                self.push_log(f'{symbol} 没有 K 线数据'
                              '（该合约可能没有行情权限 / 已停牌）', 'warning')
                self.push(_protocol.patch_toast(
                    f'{symbol} 没有 K 线数据（检查行情权限）', 'warning'))
        self.push(self.book_payload(symbol, feed))
        self.push(self.position_payload(symbol, feed))
        self.push(self.account_payload(symbol=next(iter(self.tabs), '')))
        self.push(self.trading_state(next(iter(self.tabs), '')))
        self.push(self.indicator_payload(symbol))
        if info.get('chart_type'):
            self.push({'type': 'chart_type', 'symbol': symbol,
                       'kind': info['chart_type']})
        layout = info.get('layout') or {}
        if layout.get('cols') or layout.get('rows'):
            self.push({'type': 'layout', 'symbol': symbol,
                       'cols': int(layout.get('cols') or 1),
                       'rows': int(layout.get('rows') or 1),
                       'symbols': list(layout.get('symbols') or [symbol]),
                       'cycle': int(info.get('cycle') or 60)})

    def _on_close_chart(self, payload) -> None:
        symbol = str(payload.get('symbol') or '')
        self.tabs.pop(symbol, None)

    def _on_set_cycle(self, payload) -> None:
        symbol = str(payload.get('symbol') or '')
        cycle = int(payload.get('cycle') or 60)
        info = self.tabs.get(symbol) or {}
        feed = info.get('feed') or pick_feed(self.feeds, symbol)
        info = dict(info)
        info.update({'feed': feed, 'cycle': cycle})
        self.tabs[symbol] = info
        frame = feed.klines(symbol, cycle, self.tab_length(info)) if feed else None
        bars = _protocol.bars_from_frame(frame)
        self._reset_kline_state(info)
        self._note_kline_state(
            info, bars, len(frame) if frame is not None else 0)
        self.push(_protocol.patch_kline(symbol, bars, True))


def _is_stock(symbol: str) -> bool:
    # ★ desk 里股票统一写**天勤风格** `SSE./SZSE.`（`SH./SZ.` 是富途写法）
    #   以前只认 `SH/SZ/HK/US` → `SSE.600007` 被当成期货：
    #   默认周期给成 1 分钟、spark 也被喂给富途（订阅失败）✗
    return str(symbol or '').split('.')[0].upper() in (
        'SH', 'SZ', 'HK', 'US', 'SSE', 'SZSE', 'BSE')


#: 兼容：从 `minibt.desk` 直接拿（惰性）
def __getattr__(name):
    if name == 'DeskWindow':
        from .app_window import DeskWindow
        return DeskWindow
    raise AttributeError(name)


# ===================================================== 小工具（P2 二级报价）
def _watch_symbols(watch: Dict[str, Any] = None) -> List[str]:
    """「收藏 + 各分组手动加入」的合约（首页自选 / 行情预热用 ✓）"""
    watch = watch or {}
    symbols: List[str] = list(watch.get('favorites') or [])
    for items in (watch.get('pins') or {}).values():
        symbols.extend(items or [])
    for group in watch.get('groups') or []:
        symbols.extend(group.get('symbols') or [])
    return [str(item) for item in dict.fromkeys(symbols) if item]


def _kline_signature(frame) -> tuple:
    """``(有效根数, 首根时间秒, 末根时间秒)`` —— **占位行不算** ✓

    天勤的 ``get_kline_serial`` 在历史还没下载完时返回的是**定长占位表**
    （``datetime = 0``、OHLC 全 NaN，长度 = 请求宽度）。desk 为了不卡 UI
    用 ``_fast_call`` 不等初始化，所以首拍拿到的就是这个 →
    “根数变没变”只能数**真正有时间的行**，不能看 ``len(frame)``
    （否则永远不变 → 永不发全量补丁 → 图表只剩增量那 2 根 ✗）。
    """
    if frame is None or not hasattr(frame, 'columns'):
        return (0, 0, 0)
    try:
        column = frame['datetime']
    except Exception:                                            # noqa: BLE001
        return (0, 0, 0)
    try:
        import numpy as np
        values = np.asarray(column, dtype='float64')
    except Exception:                                            # noqa: BLE001
        return (0, 0, 0)
    try:
        valid = np.isfinite(values) & (values > 0)
        count = int(valid.sum())
        if not count:
            return (0, 0, 0)
        stamps = values[valid].astype('int64') // 1_000_000_000
        return (count, int(stamps[0]), int(stamps[-1]))
    except Exception:                                            # noqa: BLE001
        return (0, 0, 0)


def _num_local(value):
    """安全转 float：None / 非法 / **NaN** → None ✓（NaN 会让 int() 抛异常 ✗）"""
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _compact_num(value) -> str:
    """成交量 / 金额缩写（首页信号卡用）✓"""
    number = _num_local(value)
    if number is None:
        return '--'
    absolute = abs(number)
    if absolute >= 1e8:
        return f'{number / 1e8:.2f}亿'
    if absolute >= 1e4:
        return f'{number / 1e4:.2f}万'
    return str(int(number))


def _field_local(item, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _field_any_local(item, names, default=None):
    """按**多个别名**取字段（天勤 pos_long / volume_long 都认 ✓）"""
    for name in names:
        value = _field_local(item, name)
        if value is not None:
            return value
    return default


def _book_pair(price, volume) -> Dict[str, Any]:
    return {'price': _num_local(price), 'volume': _num_local(volume)}


def _book_info(quote) -> Dict[str, Any]:
    """12 个字段（与 `quote-panel.ts` 的 INFO_FIELDS 对齐 ✓）"""
    last = _num_local(getattr(quote, 'last_price', None))
    pre_settle = _num_local(getattr(quote, 'pre_settlement', None))
    pre_close = _num_local(getattr(quote, 'pre_close', None))
    base = pre_settle if pre_settle else pre_close
    chg = (last - base) if (last is not None and base) else None
    return {
        'last': last, 'chg': chg,
        'chg_pct': (chg / base * 100.0) if (chg is not None and base) else None,
        'pre_settlement': pre_settle,
        'settlement': _num_local(getattr(quote, 'settlement', None)),
        'open': _num_local(getattr(quote, 'open', None)),
        'high': _num_local(getattr(quote, 'highest', None)),
        'low': _num_local(getattr(quote, 'lowest', None)),
        'volume': _num_local(getattr(quote, 'volume', None)),
        'open_interest': _num_local(getattr(quote, 'open_interest', None)),
        'amount': _num_local(getattr(quote, 'amount', None)),
    }


def _clock_of(stamp, shift_hours: int = 0) -> str:
    """时间戳 → ``HH:MM:SS``（**按 UTC+偏移**，不受本机时区影响 ✓）

    以前用 `time.localtime()`：在 UTC 的机器上就显示 UTC（比北京时间少 8h ✗）；
    现在固定 `gmtime(seconds + shift*3600)`，期货传 8 就是北京时间 ✓
    """
    if isinstance(stamp, str):
        head = stamp.split('.')[0]
        return head[-8:] if len(head) >= 8 else stamp
    try:
        seconds = int(stamp) // 1_000_000_000
        return time.strftime('%H:%M:%S',
                             time.gmtime(seconds + int(shift_hours) * 3600))
    except (TypeError, ValueError, OSError):
        return ''


def _tick_side(item, price) -> str:
    """分笔方向（对比买卖一；拿不到 → 空 ✓）"""
    bid = _num_local(item.get('bid_price1'))
    ask = _num_local(item.get('ask_price1'))
    if price is None:
        return ''
    if ask is not None and price >= ask:
        return '买'
    if bid is not None and price <= bid:
        return '卖'
    return ''


def _position_side(row, volume, price_keys, profit_keys, label) -> Optional[dict]:
    if not volume:
        return None
    price = None
    for key in price_keys:
        price = _num_local(_field_local(row, key))
        if price:
            break
    profit = None
    for key in profit_keys:
        profit = _num_local(_field_local(row, key))
        if profit is not None:
            break
    return {'volume': float(volume), 'avg': price, 'profit': profit,
            'side': label}


def _alert_crossed(cross: str, prev, last: float, price: float) -> bool:
    """预警方向判断（``prev`` 为 None 时退回「靠近即触发」✓）"""
    tol = max(1e-9, abs(price) * 0.0005)
    if prev is None:
        return abs(last - price) <= tol
    if cross == '上穿':
        return prev < price <= last
    if cross == '下穿':
        return prev > price >= last
    # 穿过：两侧跨过，或者落在容差内 ✓
    return (prev - price) * (last - price) <= 0 or abs(last - price) <= tol


def _cycle_text(cycle: int) -> str:
    """周期 → 中文（1分 / 5分 / 1时 / 1日 ✓）"""
    labels = {30: '30秒', 60: '1分', 120: '2分', 300: '5分', 600: '10分',
              900: '15分', 1800: '30分', 3600: '1时', 7200: '2时',
              14400: '4时', 86400: '1日', 604800: '1周'}
    return labels.get(int(cycle), f'{int(cycle)}秒')


def _attach_indicator_params(payload: dict, selected: list) -> None:
    """给指标补丁里的每条线补上 `params` 与 `source`（图例 ⚙ 用 ✓）

    * 内置（`MA` / `MACD`…）：线条 key 形如 `MA20` / `MACD_DIF`
    * 目录（`pta_sma`）：线条 key 形如 `pta_sma:sma`
    * 个人（`pi:cat/fn`）：`pi:cat/fn:label`
    """
    items = payload.get('items') or []
    if not items:
        return
    entries = {}
    for entry in selected or []:
        key = str(entry.get('key') or '')
        if key:
            entries[key] = entry
    from . import indicator_catalog as _cat
    from . import personal as _pi

    # 目录 schema 拿不到时（`pi:` 个人指标）→ 用 personal.scan 里的参数表 ✓
    personal_schema = None
    if any(key.startswith('pi:') for key in entries):
        try:
            personal_schema = {entry['key']: entry.get('params') or []
                               for entry in _pi.scan('indicator')}
        except Exception:                                        # noqa: BLE001
            personal_schema = {}

    ordered = sorted(entries, key=len, reverse=True)   # 长 key 优先 ✓
    for item in items:
        line_key = str(item.get('key') or '')
        params = None
        source = ''
        for key in ordered:
            entry = entries[key]
            tail = line_key[len(key):]
            matched = (
                line_key == key
                or line_key.startswith(key + ':')      # pta_sma:sma / pi:…
                or line_key.startswith(key + '_')      # MACD_DIF / BOLL_UP
                or (line_key.startswith(key) and tail[:1].isdigit())
            )                                          # MA30 / RSI14 / BOLL20
            if matched:
                source = key
                params = dict(entry.get('params') or {})
                break
        if params is None:
            continue
        # ★ 设置面板要有输入框：把目录默认值补上（用户没显式改过时 ✓）
        schema = (_cat.entry(source) or {}).get('params') or []
        if not schema and personal_schema:
            schema = personal_schema.get(source) or []
        defaults = {param['name']: param['default'] for param in schema}
        meta = {param['name']: {key: param[key] for key in
                                ('type', 'min', 'max', 'step')
                                if key in param}
                for param in schema}
        item['params'] = {**defaults, **params}
        item['paramMeta'] = meta
        item['source'] = source


def _as_params(value) -> Dict[str, Any]:
    """参数统一成 dict ✓

    前端有两条路：``{'length': 20}``（dict）和目录里的**参数表**
    ``[{'name': 'length', 'default': 20, 'type': 'int'}, …]``（list）——
    后者直接喂 ``dict()`` 会炸 ``dictionary update sequence element #0
    has length 4; 2 is required``（用户实测的 bug ✗），这里两种都吃 ✓
    """
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (list, tuple)):
        out: Dict[str, Any] = {}
        for item in value:
            if isinstance(item, dict) and item.get('name') is not None:
                out[str(item['name'])] = item.get('default')
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                out[str(item[0])] = item[1]
        return out
    return {}


#: 布局保存的指标样式字段（和 user_prefs.LAYOUT_INDICATOR_STYLE_KEYS 一致 ✓）
_INDICATOR_STYLE_FIELDS = (
    'overlay', 'color', 'lineWidth', 'lineStyle', 'visible',
    'priceLine', 'priceLabel', 'crosshairMarker',
)


def _apply_indicator_styles(payload: dict, selected: list) -> None:
    """把布局 / 用户设置里的样式（颜色 / 线宽 / 显隐 / 主副图）套到线条 ✓"""
    items = payload.get('items') or []
    if not items:
        return
    styles = {}
    for entry in selected or []:
        key = str(entry.get('key') or '')
        if not key:
            continue
        style = {name: entry[name] for name in _INDICATOR_STYLE_FIELDS
                 if name in entry and entry.get(name) is not None}
        if style:
            styles[key] = style
    if not styles:
        return
    for item in items:
        source = str(item.get('source') or '')
        # 线条 key 优先；布局里多线指标每根线的颜色可能不同 ✓
        style = (styles.get(str(item.get('key') or ''))
                 or styles.get(source))
        if not style:
            continue
        for name, value in style.items():
            item[name] = value


def _apply_overlay_override(payload: dict, selected: list) -> None:
    """把用户选的「主图 / 副图」覆盖到指标线条上 ✓"""
    items = payload.get('items') or []
    if not items:
        return
    overrides = {}
    for entry in selected or []:
        value = entry.get('overlay')
        if value is not None:
            overrides[str(entry.get('key') or '')] = bool(value)
    if not overrides:
        return
    for item in items:
        source = str(item.get('source') or '')
        item_key = str(item.get('key') or '')
        if item_key in overrides:
            item['overlay'] = overrides[item_key]
        elif source in overrides:
            item['overlay'] = overrides[source]


#: 目录 prefix / 分组标签 → 选择器 section ✓（中文标签也认，双保险）
_SECTION_OF = {
    'pta': 'pta', 'PandasTa': 'pta', 'PandasTA': 'pta',
    'ti': 'ti', 'TuLip': 'ti',
    'tqta': 'tqta', 'TqTa': 'tqta', '天勤TA': 'tqta',
    'tqfunc': 'tqfunc', 'TqFunc': 'tqfunc', '天勤函数': 'tqfunc',
    'btind': 'btind', 'BtInd': 'btind',
    'pine': 'pine', 'Pine': 'pine',
    'talib': 'talib', 'TaLib': 'talib', 'TA-Lib': 'talib',
    'finta': 'finta', 'FinTa': 'finta',
    'tradingview': 'tradingview', 'TradingView': 'tradingview',
}


def _decimals_from_tick(tick) -> int:
    """最小变动价位 → 小数位（实现见 `symbols.decimals_from_tick` ✓）"""
    return _symbols.decimals_from_tick(tick)


#: 导出目录（CSV / 布局 JSON 都放这里 —— Qt 里最容易找到 ✓）
EXPORTS_DIR = os.path.join(os.path.expanduser('~'), '.minibt', 'exports')

#: 文件名里不允许出现的字符（Windows + POSIX 都照顾到 ✓）
_BAD_CHARS = set('<>:"/\\|?*\n\r\t')


def _safe_filename(name: str, default: str = 'export.csv') -> str:
    """文件名清洗（保留扩展名；空 → 默认名）✓"""
    base = os.path.basename(str(name or '').strip()) or default
    cleaned = ''.join('_' if char in _BAD_CHARS else char for char in base)
    cleaned = cleaned.strip(' .')
    if not cleaned:
        cleaned = default
    if '.' not in cleaned:
        cleaned += '.csv'
    return cleaned[:120]


def _write_export(name: str, text: str) -> Optional[str]:
    """写到 ``~/.minibt/exports/``；重名自动加序号（不覆盖上次的 ✓）"""
    try:
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        path = os.path.join(EXPORTS_DIR, name)
        stem, ext = os.path.splitext(path)
        index = 2
        while os.path.exists(path):
            path = f'{stem}_{index}{ext}'
            index += 1
        with open(path, 'w', encoding='utf-8-sig', newline='') as handle:
            handle.write(text)
        return path
    except OSError as error:                                     # noqa: BLE001
        print(f'[desk] 导出失败: {error!r}')
        return None


def _open_path(target: str) -> str:
    """用系统默认程序打开文件 / 文件夹（Qt → QDesktopServices ✓）

    Returns:
        ``''`` = 成功；否则是错误描述
    """
    errors = []
    try:                                     # 1) Qt（desk 常驻环境 ✓）
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        if QDesktopServices.openUrl(QUrl.fromLocalFile(target)):
            return ''
        errors.append('QDesktopServices 返回 False')
    except Exception as error:               # noqa: BLE001
        errors.append(repr(error))
    try:                                     # 2) 系统命令
        if os.name == 'nt':
            os.startfile(target)             # noqa: S606
            return ''
        import subprocess
        opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
        subprocess.Popen([opener, target], close_fds=True)  # noqa: S603
        return ''
    except Exception as error:               # noqa: BLE001
        errors.append(repr(error))
    return '；'.join(errors[-2:])


def _tick_side_by_pair(price, previous) -> str:
    """没有买卖一档时：比上一笔价高 → 买（红），低 → 卖（绿）✓"""
    try:
        if previous is None:
            return ''
        price = float(price)
        previous = float(previous)
    except (TypeError, ValueError):
        return ''
    if price > previous:
        return '买'
    if price < previous:
        return '卖'
    return ''
