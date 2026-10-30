"""实时图专属工具（买卖盘 / 持仓线 / 二级报价 + 简易下单）。

* `current_kline` 按 ``{symbol}_{cycle}`` 找合约；
* **买卖盘**用 ``TargetPosTask.set_target_volume`` 交易；
* **简易下单**：开多/开空/平仓按价格框价格走 ``insert_order``（限价）——
  开多 = BUY/OPEN、开空 = SELL/OPEN、平仓 = 多头 SELL/CLOSE / 空头 BUY/CLOSE；
  **市价平仓 / 反手 / 部分平** 走 ``TargetPosTask``（市价）；
* 持仓线用 ``horizontal_line(axis_label_visible=False, label_visible=True)``
  （标签画在可视范围左边，不挤进 Y 轴）；
* 二级报价面板复刻 miniqt（合约+名称 / 5 档 / 信息栏 / 简易下单 + 市价按钮）。
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
WINDOW = REPO / 'minibt' / 'strategy' / 'strategy_window.py'
REALTIME = REPO / 'minibt' / 'strategy' / 'realtime.py'
TOOLS = REPO / 'minibt' / 'strategy' / 'live_tools.py'


class FakePos:
    pos = 2
    open_price_long = 100.0
    open_price_short = 0.0
    float_profit = 5.0


class FakeQuote:
    symbol = 'SHFE.ag2612'
    bid_price1 = 99.0
    ask_price1 = 100.0
    price_tick = 0.01
    ask_price2 = 101.0
    ask_volume1 = 3
    last_price = 100.0
    pre_settlement = 98.0
    settlement = None
    open = 99.0
    highest = 102.0
    lowest = 97.0
    volume = 12345
    open_interest = 6789


class FakeTask:
    def __init__(self, size=None):
        self.size = size
        self.target = None

    def set_target_volume(self, value):
        self.target = value


class FakeKline:
    symbol = 'SHFE.ag2612'
    cycle = 60
    name = '沪银'

    def __init__(self):
        self.quote = FakeQuote()
        self.position = FakePos()
        self.orders = []
        #: 真 ``TqObjs.TargetPosTask`` 是一个**实例**（不是工厂）—— 只拿实例，
        #: 绝不能当函数调（``'TargetPosTask' object is not callable`` ✗）
        task = FakeTask()
        self.task = task
        self.tasks = [task]
        tqobj = type('TQ', (), {'TargetPosTask': task})()
        self._tqobjs = {self.symbol: tqobj}

    def insert_order(self, **kwargs):
        self.orders.append(kwargs)


class FakeLine:
    def __init__(self):
        self.updates = []
        self.deleted = False
        self.opts = None

    def update(self, price):
        self.updates.append(price)

    def options(self, **kwargs):
        self.opts = kwargs

    def delete(self):
        self.deleted = True


class FakeChart:
    def __init__(self):
        self.lines = []
        self.scripts = []
        self.win = type('W', (), {'handlers': {}})()

    def horizontal_line(self, price, **kwargs):
        line = FakeLine()
        self.lines.append((price, kwargs, line))
        return line

    def run_script(self, script):
        self.scripts.append(script)


class FakeOwner:
    #: 这些用例测的是**实时**图表的工具（`btplot` / 回测用 `_realtime=False`，
    #: 见 `test_live_tools_are_disabled_outside_the_realtime_chart`）
    _realtime = True

    def __init__(self, strategy, chart, contract='SHFE.ag2612_60'):
        self._strategy = strategy
        self.chart = chart
        self.window = type('Win', (), {'contract': contract})()

    def _strategy_obj(self):
        return self._strategy


class FakeStrategy:
    def __init__(self, kline):
        self._btklinedataset = {'k': kline}


def _tools():
    kline = FakeKline()
    chart = FakeChart()
    strategy = FakeStrategy(kline)
    from minibt.strategy.live_tools import LiveTools

    return LiveTools(FakeOwner(strategy, chart)), kline, chart


def test_current_kline():
    from minibt.strategy.live_tools import current_kline

    kline = FakeKline()
    strategy = FakeStrategy(kline)
    assert current_kline(strategy, 'SHFE.ag2612_60') is kline
    assert current_kline(strategy, 'X_60') is None


def test_tick_decimals():
    from minibt.strategy.live_tools import _tick_decimals

    assert _tick_decimals(0.01) == 2
    assert _tick_decimals(0.5) == 1
    assert _tick_decimals(1.0) == 0


# --------------------------------------------------------------------------- #
# 限价单（简易下单：买 / 卖 / 平 按价格框价格）
# --------------------------------------------------------------------------- #
def test_place_buy_and_sell_open_limit():
    tools, kline, _chart = _tools()
    # 开多：BUY/OPEN
    assert '开多' in tools._place('long', 100.0, 2)
    assert kline.orders[-1]['direction'] == 'BUY'
    assert kline.orders[-1]['offset'] == 'OPEN'
    assert kline.orders[-1]['volume'] == 2
    assert kline.orders[-1]['limit_price'] == 100.0

    # 开空：SELL/OPEN（**不是**开多）
    assert '开空' in tools._place('short', 99.0, 1)
    assert kline.orders[-1]['direction'] == 'SELL'
    assert kline.orders[-1]['offset'] == 'OPEN'

    # 旧的 buy/sell 仍兼容
    assert '开多' in tools._place('buy', 100.0, 1)
    assert kline.orders[-1]['direction'] == 'BUY'
    assert '开空' in tools._place('sell', 99.0, 1)
    assert kline.orders[-1]['direction'] == 'SELL'


def test_depth_panel_labels_and_actions():
    """二级报价按钮：开多 / 开空 / 平仓（不再是 买入 / 卖出）。"""
    from minibt.strategy.live_tools import _DEPTH_JS
    assert '>开多<' in _DEPTH_JS
    assert '>开空<' in _DEPTH_JS
    assert '>平仓<' in _DEPTH_JS
    assert "sendOrder('long')" in _DEPTH_JS
    assert "sendOrder('short')" in _DEPTH_JS
    assert "sendOrder('close')" in _DEPTH_JS


def test_order_book_host_clickable_and_on_top():
    """买卖盘要能点（pointer-events:auto）且不被 K 线盖住（z-index）✓。"""
    from minibt.strategy.live_tools import _ORDER_BOOK_HOST_JS
    assert 'pointer-events:auto' in _ORDER_BOOK_HOST_JS
    assert 'z-index:4000' in _ORDER_BOOK_HOST_JS


def test_place_close_is_limit_at_price():
    """平仓走 insert_order（限价）：多头挂卖平、空头挂买平 ✓。"""
    tools, kline, _chart = _tools()      # 多仓 net=2
    assert '平仓' in tools._place('close', 101.0, 2)
    assert kline.orders[-1]['direction'] == 'SELL'
    assert kline.orders[-1]['offset'] == 'CLOSE'
    assert kline.orders[-1]['limit_price'] == 101.0

    # 空仓 → BUY/CLOSE（空头平仓单）
    kline.position = type('P', (), {'pos': -3})()
    assert '空头平仓' in tools._place('close', 99.0, 5)
    assert kline.orders[-1]['direction'] == 'BUY'
    assert kline.orders[-1]['offset'] == 'CLOSE'
    assert kline.orders[-1]['limit_price'] == 99.0
    assert kline.orders[-1]['volume'] == 3


def test_place_requires_price():
    tools, _kline, _chart = _tools()
    assert '请输入价格' in tools._place('buy', None, 1)


# --------------------------------------------------------------------------- #
# 市价（市价平仓 / 反手 / 部分平）—— TargetPosTask
# --------------------------------------------------------------------------- #
def test_market_close_uses_target_pos():
    tools, kline, _chart = _tools()
    assert '市价平仓' in tools._place_market('close_market', 1)
    assert kline.tasks[-1].target == 0


def test_market_reverse():
    tools, kline, _chart = _tools()      # 多仓 2 → 反手目标 -2
    assert '反手' in tools._place_market('reverse', 1)
    assert kline.tasks[-1].target == -2


def test_market_partial():
    tools, kline, _chart = _tools()      # 多仓 2，部分平 1 → 目标 1
    assert '部分平' in tools._place_market('partial', 1)
    assert kline.tasks[-1].target == 1


def test_market_no_position():
    tools, kline, _chart = _tools()
    kline.position = type('P', (), {'pos': 0})()
    assert '无持仓' in tools._place_market('reverse', 1)
    assert '无持仓' in tools._place_market('partial', 1)


# --------------------------------------------------------------------------- #
# 买卖盘 —— set_target_volume
# --------------------------------------------------------------------------- #
def test_order_book_side_uses_target_pos():
    tools, kline, _chart = _tools()      # 多仓 2
    # 左侧（卖）在多仓时 = 平仓 → 0
    tools._on_order_book_side('sell')
    assert kline.tasks[-1].target == 0
    # 右侧（买）在多仓时 = 加多 → 3
    tools._on_order_book_side('buy')
    assert kline.tasks[-1].target == 3


# --------------------------------------------------------------------------- #
# 持仓线（左标签）
# --------------------------------------------------------------------------- #
def test_position_line_uses_left_edge_label():
    tools, kline, chart = _tools()
    tools.toggle_position_line(True)
    assert len(chart.lines) == 1
    price, kwargs, line = chart.lines[0]
    assert price == 100.0
    assert kwargs['label_visible'] is True
    assert kwargs['axis_label_visible'] is False
    assert '多仓2手' in kwargs['text']

    kline.position = type('P', (), {'pos': 3, 'open_price_long': 101.0,
                                    'open_price_short': 0.0,
                                    'float_profit': -1.0})()
    tools._sync_position_line()
    assert line.updates == [101.0]
    assert '多仓3手' in (line.opts or {}).get('text', '')

    kline.position = type('P', (), {'pos': 0})()
    tools._sync_position_line()
    assert line.deleted is True


def test_position_line_on_by_default():
    """持仓线默认**开** —— 有持仓就自动画（下单后不需手动打开）✓"""
    tools, kline, chart = _tools()
    assert tools._position_line_on is True
    tools._sync_position_line()
    assert len(chart.lines) == 1


def test_position_line_off_does_nothing():
    tools, kline, chart = _tools()
    tools.toggle_position_line(False)      # 手动关掉
    tools._sync_position_line()
    assert chart.lines == []


def test_live_tools_are_disabled_outside_the_realtime_chart():
    """回测 / ``btplot`` 静态图不画实时持仓线。

    以前 ``RealtimeChart`` 无论 ``realtime`` 真假都建 ``LiveTools``，切合约时
    又必调 ``on_contract_changed()`` → `refresh()` —— 用测试数据跑 ``btplot()``
    时策略里回测出的持仓会被当成实盘持仓，打一行
    ``[live_tools] 持仓线已画`` 并在图上画一条线 ✗。
    """
    class BacktestOwner(FakeOwner):
        _realtime = False

    kline = FakeKline()
    chart = FakeChart()
    strategy = FakeStrategy(kline)
    from minibt.strategy.live_tools import LiveTools

    tools = LiveTools(BacktestOwner(strategy, chart))
    assert tools._enabled is False
    tools.refresh()                        # 策略有持仓（pos=2）也不该画
    assert chart.lines == []
    assert tools._position_line is None


# --------------------------------------------------------------------------- #
# 源码约束
# --------------------------------------------------------------------------- #
def test_window_has_live_tool_buttons_before_drawing():
    source = WINDOW.read_text(encoding='utf-8')
    assert 'live_tools: bool = False' in source
    body = source.split("self.page_bar.switcher('strategy'", 1)[1]
    orderbook = body.index("self.page_bar.button('orderbook'")
    depth = body.index("self.page_bar.button('depth'")
    drawing = body.index("self.page_bar.button('drawing'")
    assert orderbook < drawing and depth < drawing
    assert 'def _on_order_book' in source and 'def _on_depth' in source


def test_realtime_wires_live_tools():
    source = REALTIME.read_text(encoding='utf-8')
    assert 'from minibt.strategy.live_tools import LiveTools' in source
    assert 'live_tools=bool(realtime)' in source
    assert 'self.live_tools = LiveTools(self)' in source
    assert 'on_toggle_order_book' in source and 'on_toggle_depth' in source
    assert 'live_tools.refresh()' in source


def test_depth_panel_matches_miniqt():
    source = TOOLS.read_text(encoding='utf-8')
    # 信息栏字段（保留）
    for field in ('最新', '涨跌', '涨跌幅', '昨结', '结算', '今开',
                  '最高', '最低', '成交量', '持仓量'):
        assert field in source, field
    # 去掉：分笔成交 / 增仓 / 成交额
    assert '分笔' not in source
    assert '增仓' not in source
    assert '成交额' not in source
    # +/- 步进 & 市价按钮
    assert 'md-p-up' in source and 'md-v-up' in source
    assert '市价平仓' in source and '反手' in source and '部分平' in source
    # 只对显示中的面板刷新
    assert 'if not self._depth_on or not self._depth_ready' in source


def test_trade_account_picks_sim_in_multi_account():
    """多账户（TqMultiAccount）→ 下单/查持仓要带 account，优先取**模拟账号** ✓"""
    from minibt.strategy.live_tools import LiveTools

    class FakeReal:
        pass

    class FakeSim:
        pass

    class Multi:
        _account_list = [FakeReal(), FakeSim()]

    class OwnerMulti:
        def _first_api(self):
            return type('A', (), {'_account': Multi()})()

    tools = LiveTools(OwnerMulti())
    assert type(tools._trade_account()).__name__ == 'FakeSim'

    # 单账户 → 就用它自己
    class OwnerSingle:
        def _first_api(self):
            return type('A', (), {'_account': FakeReal()})()

    tools2 = LiveTools(OwnerSingle())
    assert type(tools2._trade_account()).__name__ == 'FakeReal'


def test_orders_pass_account():
    """下单（限价 insert_order / 市价 TargetPosTask）都要带 account（多账户 ✓）"""
    import inspect
    from minibt.strategy import live_tools as im

    source = inspect.getsource(im)
    assert 'account=self._trade_account()' in source
    assert 'TargetPosTask(api, symbol, account=' in source
    assert 'api.get_position(symbol, account=account)' in source


# --------------------------------------------------------------------------- #
# 买卖盘回调 + 下单（回归：点击无反应 / TargetPosTask 被当函数调用）
# --------------------------------------------------------------------------- #
def test_order_book_uses_fixed_callback_name():
    """买卖盘回调走**固定名字** ``minibt_order_book``（和二级报价按钮同一套）✓"""
    import inspect
    from minibt.strategy import live_tools as mod

    src = inspect.getsource(mod.LiveTools._ensure_order_book)
    assert "handlers['minibt_order_book'] = self._on_order_book_side" in src
    assert 'callbackName = "minibt_order_book"' in src
    # 不再依赖面板自带的 _bind_callback（key 是 window.xxx，某些桥取不到）
    assert 'on_side_click=self._on_order_book_side' not in src


def test_target_task_never_called_as_factory():
    """``TqObjs.TargetPosTask`` 是实例 —— 只能取实例，不能调（旧代码会报
    ``'TargetPosTask' object is not callable`` → 点了没反应 ✗）✓"""
    import inspect
    from minibt.strategy import live_tools as mod

    src = inspect.getsource(mod.LiveTools._target_task)
    assert 'TargetPosTask(api, symbol, account=account)' in src
    assert "getattr(tqobj, 'TargetPosTask', None)" in src
    assert 'return kline.TargetPosTask' not in src
    assert 'kline.TargetPosTask(0)' not in src


def test_depth_market_buttons_readable_in_light_theme():
    """浅色主题下「市价平仓/反手/部分平」文字要深色（CSS 权重得压过 ``color:#fff``）✓"""
    import inspect
    from minibt.strategy import live_tools as mod

    src = mod._DEPTH_JS
    # ``.d-btns button`` 把 color 设成 #fff；.d-mkt 必须更具体才盖得住
    assert '.d-btns button.d-mkt{' in src
    assert '#minibt-depth .d-mkt{' not in src


# --------------------------------------------------------------------------- #
# 二级报价下方 tabs：持仓 / 委托 / 历史成交（只针对当前合约）
# --------------------------------------------------------------------------- #
def test_depth_panel_has_account_tabs():
    """二级报价按钮下方有可切换的 tabs + 三个表格（表头对齐 miniqt ✓）"""
    from minibt.strategy.live_tools import _DEPTH_JS
    for header in ('>持仓<', '>委托<', '>历史成交<', '>总仓<', '>持仓均价<',
                   '>盈亏<', '>未成交<', '>报单价<', '>成交价<', '>撤单<'):
        assert header in _DEPTH_JS, header
    for tid in ('md-tbl-pos', 'md-tbl-ord', 'md-tbl-trd'):
        assert tid in _DEPTH_JS, tid
    assert 'renderAccounts' in _DEPTH_JS
    assert 'setTab' in _DEPTH_JS
    assert "data-tab=" in _DEPTH_JS
    # “部分平”已换成“撤单”
    assert 'md-cancel' in _DEPTH_JS and 'md-partial' not in _DEPTH_JS


def test_account_rows_positions():
    tools, kline, _chart = _tools()

    class Pos:
        pos_long = 2
        pos_short = 0
        position_price_long = 15000.0
        float_profit_long = 123.456
    tools._position = lambda: Pos()
    rows = tools._account_rows('pos', 1)
    assert rows == [{'direction': '买',
                     'cells': ['买', '2', '15000.0', '+123.46']}]

    class Both:
        pos_long = 1
        pos_short = 3
        position_price_long = 100.0
        position_price_short = 101.0
        float_profit_long = -1.0
        float_profit_short = 2.0
    tools._position = lambda: Both()
    rows = tools._account_rows('pos', 2)
    assert [r['direction'] for r in rows] == ['买', '卖']
    assert rows[1]['cells'] == ['卖', '3', '101.00', '+2.00']


def test_account_rows_orders_and_trades_filter_current_contract():
    tools, kline, _chart = _tools()

    class FakeApi:
        def get_order(self, account=None):
            return [
                # 天勤真实格式：instrument_id **不带**交易所，exchange_id 单独给 ✓
                {'exchange_id': 'SHFE', 'instrument_id': 'ag2612',
                 'direction': 'BUY', 'offset': 'OPEN',
                 'volume_orign': 3, 'volume_left': 1, 'limit_price': 15000.0},
                {'exchange_id': 'SHFE', 'instrument_id': 'cu2612',
                 'direction': 'SELL', 'offset': 'CLOSE',
                 'volume_orign': 1, 'volume_left': 0, 'limit_price': 70000.0},
            ]

        def get_trade(self, account=None):
            return [
                {'exchange_id': 'SHFE', 'instrument_id': 'ag2612',
                 'direction': 'SELL', 'offset': 'CLOSETODAY',
                 'price': 15001.0, 'volume': 2},
                {'exchange_id': 'SHFE', 'instrument_id': 'cu2612',
                 'direction': 'BUY', 'offset': 'OPEN',
                 'price': 70000.0, 'volume': 1},
            ]
    tools._api = lambda: FakeApi()
    tools._trade_account = lambda: 'ACC'

    orders = tools._account_rows('ord', 1)
    assert orders == [{'direction': '买',
                       'cells': ['买', '开', '3', '1', '15000.0']}]  # 铜被过滤 ✓
    trades = tools._account_rows('trd', 1)
    assert trades == [{'direction': '卖',
                       'cells': ['卖', '平今', '15001.0', '2']}]


def test_cancel_orders_only_current_contract_pending():
    """撤单：只撤**当前合约**还有未成交手数的挂单（别的合约 / 已完不动）✓"""
    tools, kline, _chart = _tools()

    class FakeApi:
        def __init__(self):
            self.cancelled = []

        def get_order(self, account=None):
            return [
                {'exchange_id': 'SHFE', 'instrument_id': 'ag2612',
                 'order_id': 'o1', 'status': 'ALIVE', 'volume_left': 1},
                {'exchange_id': 'SHFE', 'instrument_id': 'ag2612',
                 'order_id': 'o2', 'status': 'FINISHED', 'volume_left': 0},
                {'exchange_id': 'SHFE', 'instrument_id': 'cu2612',
                 'order_id': 'o3', 'status': 'ALIVE', 'volume_left': 2},
            ]

        def cancel_order(self, order_id, account=None):
            self.cancelled.append(order_id)
    api = FakeApi()
    tools._api = lambda: api
    tools._trade_account = lambda: 'ACC'

    message = tools._cancel_orders()
    assert api.cancelled == ['o1']       # 只撤当前合约还有量的 ✓
    assert '已撤单 1' in message


def test_account_rows_accepts_full_symbol_form():
    """有些接口直接给全称 ``SHFE.ag2612`` —— 两种形式都得认 ✓"""
    tools, kline, _chart = _tools()

    class FakeApi:
        def get_trade(self, account=None):
            return [{'instrument_id': 'SHFE.ag2612', 'direction': 'BUY',
                     'offset': 'OPEN', 'price': 1.0, 'volume': 1}]
    tools._api = lambda: FakeApi()
    tools._trade_account = lambda: None
    assert tools._account_rows('trd', 1) == [
        {'direction': '买', 'cells': ['买', '开', '1.0', '1']}]


def test_account_rows_accept_dataframe_source():
    """tqsdk 不带参数返回的是 DataFrame，`_records` 要能转成行 ✓"""
    import pandas as pd
    tools, kline, _chart = _tools()

    class FakeApi:
        def get_trade(self, account=None):
            return pd.DataFrame([
                {'instrument_id': 'SHFE.ag2612', 'direction': 'BUY',
                 'offset': 'OPEN', 'price': 15000.0, 'volume': 1},
            ])
    tools._api = lambda: FakeApi()
    tools._trade_account = lambda: 'ACC'
    assert tools._account_rows('trd', 1) == [
        {'direction': '买', 'cells': ['买', '开', '15000.0', '1']}]


# ---------------------------------------------------------- 账户总览
class _FakeAccount:
    balance = 100000.0
    available = 80000.0
    float_profit = 1200.5
    close_profit = -300.0
    margin = 20000.0
    market_value = 0.0
    commission = 0.0
    risk_ratio = 0.2


class _FakeFuturesApi:
    def get_account(self, **kwargs):
        return _FakeAccount()

    def get_position(self, **kwargs):
        return [type('P', (), {'pos': 0})(),
                type('P', (), {'pos': 2})()]

    def get_order(self, **kwargs):
        return [type('O', (), {'status': 'ALIVE'})(),
                type('O', (), {'status': 'FINISHED'})()]


class _FakeStockAccount:
    balance = 105000.0
    available = 95000.0
    float_profit = 500.0
    close_profit = 0.0
    margin = 0.0
    market_value = 10000.0
    commission = 3.5
    risk_ratio = 0.0


class _FakeStockApi:
    def get_account(self, **kwargs):
        return _FakeStockAccount()

    def get_position_list(self):
        return [type('P', (), {'pos': 500})()]

    def get_order(self, **kwargs):
        return [type('O', (), {'status': 'FINISHED'})()]


class _FakeStockApiNamed(_FakeStockApi):
    """``_account_summary`` 靠类名判断是不是股票 ✓"""


_FakeStockApiNamed.__name__ = 'StockApi'


def test_account_summary_futures():
    tools, _kline, _chart = _tools()
    tools._api = lambda: _FakeFuturesApi()
    tools._trade_account = lambda: None
    summary = tools._account_summary()
    assert summary['kind'] == '期货'
    assert summary['balance'] == 100000.0
    assert summary['available'] == 80000.0
    assert summary['float_profit'] == 1200.5
    assert summary['close_profit'] == -300.0
    assert summary['extra_label'] == '保证金'
    assert summary['extra'] == 20000.0
    assert summary['ratio_label'] == '风险度'
    assert summary['ratio'] == 20.0          # 0.2 → 20%
    assert summary['ratio_percent'] is True
    assert summary['positions'] == 1          # 只有 pos=2 那一条
    assert summary['orders'] == 1             # 只有 ALIVE


def test_account_summary_stock():
    tools, _kline, _chart = _tools()
    tools._api = lambda: _FakeStockApiNamed()
    tools._trade_account = lambda: None
    summary = tools._account_summary()
    assert summary['kind'] == '股票'
    assert summary['extra_label'] == '市值'
    assert summary['extra'] == 10000.0
    assert summary['ratio_label'] == '手续费'
    assert summary['ratio'] == 3.5
    assert summary['ratio_percent'] is False   # 手续费是金额，不是百分比
    assert summary['positions'] == 1
    assert summary['orders'] == 0


def test_account_summary_without_api_is_empty():
    tools, _kline, _chart = _tools()
    assert tools._account_summary() == {}


def test_depth_panel_has_no_account_overview():
    """P35：账户总览 / 顶栏账户条都移除（信息统一去「账户」页 ✓）"""
    source = TOOLS.read_text(encoding='utf-8')
    for key in ('d-acc-grid', 'md-acc-balance', '账户总览'):
        assert key not in source, key
    # 顶栏迷你账户条也不再插入（方法保留但直接返回 ✓）
    assert 'minibt-accbar' in source        # 样式常量还在（无害）
    assert source.count('def _sync_account_bar') == 1
    assert '_account_summary' in source     # 账户页仍然用它 ✓


# ------------------------------------------------------ 顶栏迷你账户条
def test_account_bar_html():
    tools, _kline, _chart = _tools()
    tools._api = lambda: _FakeFuturesApi()
    tools._trade_account = lambda: None
    html = tools._account_bar_html(tools._account_summary_cached())
    assert '权益' in html and '100,000.00' in html
    assert '可用' in html and '80,000.00' in html
    assert '浮盈' in html and '1,200.50' in html
    assert 'class="up"' in html            # 浮盈为正 → 涨色
    assert '持仓' in html
    # 没有账户 → 空串（不显示任何东西 ✓）
    assert tools._account_bar_html({}) == ''


def test_account_bar_is_no_longer_injected():
    """P35：顶栏迷你账户条**已移除**（账户信息统一去「账户」页 ✓）"""
    tools, _kline, _chart = _tools()
    tools._api = lambda: _FakeFuturesApi()
    tools._trade_account = lambda: None
    scripts = []

    class FakeBar:
        id = 'window.__fakebar'

        def run_script(self, text):
            scripts.append(text)

    tools._owner.window.page_bar = FakeBar()
    tools._sync_account_bar()
    assert scripts == []          # 不再往顶栏注入任何东西 ✓

def test_account_summary_is_cached_for_one_second():
    tools, _kline, _chart = _tools()
    calls = {'n': 0}

    class CountingApi(_FakeFuturesApi):
        def get_account(self, **kwargs):
            calls['n'] += 1
            return _FakeAccount()

    tools._api = lambda: CountingApi()
    tools._trade_account = lambda: None
    first = tools._account_summary_cached()
    second = tools._account_summary_cached()
    assert first is second
    assert calls['n'] == 1


def test_refresh_updates_the_account_bar():
    source = TOOLS.read_text(encoding='utf-8')
    assert '_sync_account_bar' in source
    assert '_ACCOUNT_BAR_CSS' in source
    # refresh() 里三件套：买卖盘 / 持仓线 / 二级报价 + 账户条
    refresh = source.split('    def refresh(self) -> None:', 1)[1]
    refresh = refresh.split('\n    def ', 1)[0]
    assert '_sync_account_bar()' in refresh


# ------------------------------------------------------------ 「账户」页
class _Panel:
    id = 'window.__fakePanel'

    def __init__(self):
        self.html = ''
        self.visible = False
        self.renders = 0
        self.scripts = []

    def set_html(self, html):
        self.html = html
        self.renders += 1

    def run_script(self, script):
        self.scripts.append(script)

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def delete(self):
        pass


class _HtmlChart:
    def __init__(self):
        self.panel = _Panel()

    def create_html_panel(self):
        return self.panel


def test_account_page_renders_cards_and_curve():
    from minibt.strategy.pages import AccountPage

    chart = _HtmlChart()
    page = AccountPage(chart, persist_sort=False)
    page.update(summary=_stock_summary(), curve=[
        ('09:00:00', 100000.0), ('09:05:00', 102000.0),
        ('09:10:00', 101000.0)])
    html = chart.panel.html
    assert '105,000.00' in html              # 权益
    assert '市值' in html and '手续费' in html
    assert 'class="v up"' in html            # 浮盈为正 → 涨色
    assert '<svg' in html and 'polyline' in html
    assert '最低 100,000.00' in html
    # 单点 → 提示先攒数据
    page.update(summary=_stock_summary(), curve=[])
    assert '暂无曲线数据' in chart.panel.html
    # show / hide
    page.show()
    assert chart.panel.visible is True
    page.hide()
    assert chart.panel.visible is False


def _stock_summary():
    return {'kind': '股票', 'balance': 105000.0, 'available': 95000.0,
            'float_profit': 500.0, 'close_profit': 120.0,
            'extra_label': '市值', 'extra': 10000.0,
            'ratio_label': '手续费', 'ratio': 3.5, 'ratio_percent': False,
            'positions': 2, 'orders': 0}


def test_account_page_only_updates_when_it_is_shown():
    """**没切到「账户」页 → 一次 get_account / 一次 update 都不做** ✓"""
    tools, _kline, _chart = _tools()
    calls = {'summary': 0, 'update': 0}

    class CountingApi(_FakeFuturesApi):
        def get_account(self, **kwargs):
            calls['summary'] += 1
            return _FakeAccount()

    window = type('Win', (), {})()
    window.contract = 'SHFE.ag2612'
    window.is_account_page = lambda: window.contract == '账户'
    window.update_account_page = lambda **kwargs: calls.__setitem__(
        'update', calls['update'] + 1)
    tools._owner.window = window
    tools._api = lambda: CountingApi()
    tools._trade_account = lambda: None

    tools._sync_account_page()                 # K 线页 → 什么都不做
    assert calls == {'summary': 0, 'update': 0}
    assert tools._equity_samples == []

    window.contract = '账户'                    # 切到账户页 → 更新 + 采样
    tools._sync_account_page()
    assert calls['summary'] == 1
    assert calls['update'] == 1
    assert len(tools._equity_samples) == 1

    before = dict(calls)                       # 切回 K 线 → 不再更新
    window.contract = 'SHFE.ag2612'
    tools._sync_account_page()
    assert calls == before


def test_account_page_is_wired_for_realtime_only():
    window = WINDOW.read_text(encoding='utf-8')
    assert "ACCOUNT_PAGE = '账户'" in window
    assert 'self.show_account_page' in window
    # P35：账户页不再挂到每个策略的合约栏（每换策略就多一页 ✗）
    assert 'items.append(ACCOUNT_PAGE)' not in window
    # 改成顶栏一个**全局**按钮 ✓
    assert "page_bar.button('account', '账户'" in window
    assert 'def _on_topbar_account' in window
    assert 'def set_account_page_enabled' in window
    assert 'def is_account_page' in window
    assert 'def update_account_page' in window
    realtime = REALTIME.read_text(encoding='utf-8')
    assert 'set_account_page_enabled(True, live=True)' in realtime
    tools = TOOLS.read_text(encoding='utf-8')
    assert '_is_account_page' in tools
    assert '_sync_account_page' in tools
    assert 'sim_equity_curve' in tools


# -------------------------------------------------------- 账户页明细表
class _FakeTableApi:
    """带持仓 / 委托 / 成交的假 API（字段对齐 tqsdk ✓）"""
    NS = type('NS', (), {})

    def get_account(self, **kwargs):
        return _FakeAccount()

    def get_position(self, **kwargs):
        N = type('P', (), {})
        long_row = N()
        long_row.instrument_id = 'ag2612'
        long_row.pos_long, long_row.pos_short = 2, 0
        long_row.open_price_long = 7000.0
        long_row.float_profit_long = 120.0
        short_row = N()
        short_row.instrument_id = 'rb2610'
        short_row.pos_long, short_row.pos_short = 0, 1
        short_row.open_price_short = 3500.0
        short_row.float_profit_short = -30.0
        return [long_row, short_row]

    def get_order(self, **kwargs):
        row = type('O', (), {})()
        row.insert_date_time = 1760000000000000000
        row.instrument_id = 'ag2612'
        row.direction, row.offset = 'BUY', 'OPEN'
        row.volume_orign, row.volume_left = 2, 0
        row.limit_price, row.status = 7000.0, 'FINISHED'
        return [row]

    def get_trade(self, **kwargs):
        row = type('T', (), {})()
        row.trade_date_time = 1760000000000000000
        row.instrument_id = 'ag2612'
        row.direction, row.offset = 'BUY', 'OPEN'
        row.volume, row.price = 2, 7000.0
        return [row]


def _table_tools():
    tools, _kline, _chart = _tools()
    tools._api = lambda: _FakeTableApi()
    tools._trade_account = lambda: None
    return tools


def test_account_tables_positions_orders_trades():
    tables = _table_tools()._account_tables()
    positions = tables['positions']
    assert positions['columns'] == ('代码', '方向', '手数', '均价', '浮盈')
    assert ['ag2612', '买', '2', '7000.000', '+120.00'] in positions['rows']
    assert ['rb2610', '卖', '1', '3500.000', '-30.00'] in positions['rows']
    assert positions['total'] == 2

    orders = tables['orders']
    assert orders['columns'][-1] == '状态'
    assert orders['rows'][0][-1] == '完成'          # 状态中文化 ✓
    assert orders['rows'][0][2] == '买' and orders['rows'][0][3] == '开'

    trades = tables['trades']
    assert trades['total'] == 1
    assert trades['rows'][0][4] == '2'              # 手数


def test_account_page_renders_tables():
    from minibt.strategy.pages import AccountPage

    chart = _HtmlChart()
    page = AccountPage(chart, persist_sort=False)
    tables = _table_tools()._account_tables()
    page.update(summary=_stock_summary(),
                curve=[('09:00', 100000.0), ('09:01', 100100.0)],
                tables=tables)
    html = chart.panel.html
    assert '<table>' in html
    assert 'ag2612' in html
    assert '持仓 <span class="k">2 条' in html
    page.update(tables={})                           # 没有表数据 → 三个空提示
    assert chart.panel.html.count('（暂无）') == 3
    # 条数超出 limit 时提示“显示前 N”
    page.update(tables={'orders': {'columns': ('时间',),
                                   'rows': [['09:31:00']],
                                   'total': 150, 'limit': 100}})
    assert '150 条（显示前 100）' in chart.panel.html


def test_account_tables_are_wired_into_the_page():
    tools = TOOLS.read_text(encoding='utf-8')
    assert 'def _account_tables' in tools
    assert 'def _position_table' in tools
    assert 'def _order_table' in tools
    assert 'def _trade_table' in tools
    assert 'tables=self._account_tables()' in tools
    assert 'def _status_text' in tools
    window = WINDOW.read_text(encoding='utf-8')
    assert 'tables=None' in window
    assert 'tables=tables' in window


# ------------------------------------------------- 账户页：排序 / 导出 / 回测
def _account_page_with_rows():
    from minibt.strategy.pages import AccountPage

    chart = _HtmlChart()
    chart.win = type('W', (), {'handlers': {}})()
    page = AccountPage(chart, persist_sort=False)
    rows = [[f'C{i:03d}', '买', str(i), f'{10 + i:.3f}', f'{i * 2:+d}.00']
            for i in range(150)]
    page.update(summary={'kind': '期货', 'balance': 1.0, 'available': 1.0,
                         'float_profit': 0.0, 'close_profit': 0.0,
                         'extra_label': '保证金', 'extra': 0.0,
                         'ratio_label': '风险度', 'ratio': 0.0,
                         'ratio_percent': True, 'positions': 150,
                         'orders': 0},
                curve=[('09:00', 1.0), ('09:01', 2.0)],
                tables={'positions': {
                    'columns': ('代码', '方向', '手数', '均价', '浮盈'),
                    'rows': rows, 'total': 150, 'limit': 100}})
    return page, chart


def test_account_page_sorts_by_clicked_header():
    page, chart = _account_page_with_rows()
    body = chart.panel.html.split('<tbody>')[1]
    assert 'C000' in body                     # 默认顺序
    page._on_sort('positions', '2')           # 按「手数」升序
    body = chart.panel.html.split('<tbody>')[1]
    assert 'C000' in body and '▲' in chart.panel.html
    page._on_sort('positions', '2')           # 再点 → 降序
    body = chart.panel.html.split('<tbody>')[1]
    assert 'C149' in body and '▼' in chart.panel.html
    # 显示仍然只画前 100 行
    assert chart.panel.html.count('<tr><td>') == 100


def test_account_page_does_not_rerender_when_nothing_changed():
    page, chart = _account_page_with_rows()
    renders = chart.panel.renders
    page.update(summary=page.summary, curve=page.curve, tables=page.tables)
    assert chart.panel.renders == renders     # 内容没变 → 不重画（保住滚动） ✓


def test_account_page_exports_full_table_to_csv(monkeypatch, tmp_path):
    import minibt.strategy.pages as pages

    monkeypatch.setattr(pages, 'EXPORTS_DIR', str(tmp_path))
    page, _chart = _account_page_with_rows()
    path = page.export_csv('positions')
    assert path and pathlib.Path(path).exists()
    lines = pathlib.Path(path).read_text(encoding='utf-8-sig').splitlines()
    assert lines[0].startswith('代码,方向,手数')
    assert len(lines) == 151                  # 150 行 + 表头（不受“显示前 100”限制 ✓）
    page._on_csv('positions')
    assert '已导出' in page.notice


def test_backtest_account_page_uses_equity_curve():
    import pandas as pd

    from minibt.strategy.strategy_window import StrategyWindow

    window = StrategyWindow.__new__(StrategyWindow)
    window.strategy = 'Demo'
    window.backtests = {'Demo': {
        'stats': {'final_profit': 1234.5, 'total_fee': 12.0,
                  'total_trades': 7},
        'equity': pd.DataFrame({
            'time': ['2026-10-01 09:30:00', '2026-10-01 15:00:00'],
            'value': [100000.0, 101234.5]}),
        'trades': pd.DataFrame([
            {'time': '2026-10-01 09:31:00', 'direction': '开多',
             'symbol': 'ag2612', 'price': 7000.0, 'qty': 2,
             'fee': 1.0, 'balance': 100100.0, 'pnl': 100.0}]),
    }}
    summary, curve, tables = window._backtest_account_data()
    assert summary['kind'] == '回测'
    assert summary['balance'] == 101234.5
    assert summary['close_label'] == '期末收益'
    assert summary['close_profit'] == 1234.5
    assert summary['extra_label'] == '手续费' and summary['extra'] == 12.0
    assert summary['ratio_label'] == '交易次数' and summary['ratio'] == 7.0
    assert curve == [('09:30:00', 100000.0), ('15:00:00', 101234.5)]
    rows = tables['trades']['rows']
    assert rows[0][0] == '09:31:00' and rows[0][1] == 'ag2612'
    assert rows[0][4] == '2' and rows[0][6] == '100.00'


def test_account_page_wiring_for_sort_export_and_backtest():
    pages_src = (REPO / 'minibt' / 'strategy' / 'pages.py').read_text(
        encoding='utf-8')
    for key in ('minibt_account_sort', 'minibt_account_csv',
                'def sort_by', 'def export_csv', 'def _on_csv',
                'def _signature_of'):
        assert key in pages_src, key
    window = WINDOW.read_text(encoding='utf-8')
    assert 'def _backtest_account_data' in window
    assert 'self.account_page_live' in window
    assert 'live=True' in REALTIME.read_text(encoding='utf-8')


# ------------------------------------------- 账户页：记住排序 / 导出全部
def test_account_page_remembers_sort_order(monkeypatch, tmp_path):
    import minibt.strategy.pages as pages

    monkeypatch.setattr(pages, 'SORT_FILE', str(tmp_path / 'sort.json'))

    def build(**kwargs):
        chart = _HtmlChart()
        chart.win = type('W', (), {'handlers': {}})()
        page = pages.AccountPage(chart, **kwargs)
        return page, chart

    page, _chart = build()
    page.update(tables={'positions': {
        'columns': ('代码', '方向', '手数', '均价', '浮盈'),
        'rows': [['B', '买', '2', '1.000', '+0.00'],
                 ['A', '买', '1', '1.000', '+0.00']],
        'total': 2, 'limit': 100}})
    page._on_sort('positions', '2')           # 按手数升序 → A 在前
    assert (tmp_path / 'sort.json').exists()

    page2, chart2 = build()                   # 新实例（模拟重启）
    assert page2._sort == {'positions': (2, True)}
    body = chart2.panel.html
    # 排序状态被“记住”了（表头有箭头，且不再重画也能看到）
    page2.update(tables=page.tables)
    body = chart2.panel.html.split('<tbody>')[1]
    assert 'A' in body.split('</tr>')[0]

    # persist_sort=False → 不读也不写 ✓
    page3, _chart3 = build(persist_sort=False)
    assert page3._sort == {}


def test_account_page_exports_all_tables(monkeypatch, tmp_path):
    import minibt.strategy.pages as pages

    monkeypatch.setattr(pages, 'SORT_FILE', str(tmp_path / 'sort.json'))
    monkeypatch.setattr(pages, 'EXPORTS_DIR', str(tmp_path))
    page, _chart = _account_page_with_rows()
    page.persist_sort = False
    path = page.export_all()
    assert path and pathlib.Path(path).exists()
    if path.endswith('.xlsx'):
        import pandas as pd
        sheets = pd.read_excel(path, sheet_name=None)
        assert {'持仓', '委托', '成交'} & set(sheets)
        assert len(sheets['持仓']) == 150      # 全量 ✓
    else:                                      # 没有 openpyxl / xlsxwriter
        import zipfile
        with zipfile.ZipFile(path) as bundle:
            names = bundle.namelist()
        assert any('持仓' in name for name in names)


def test_account_page_render_keeps_scroll_position():
    page, chart = _account_page_with_rows()
    assert any('scrollTop' in script for script in chart.panel.scripts)


# ------------------------------------- 账户页：刷新间隔 / 曲线区间 / 手动刷新
def _page_with_curve(persist=False):
    import time as _time

    from minibt.strategy.pages import AccountPage

    chart = _HtmlChart()
    chart.win = type('W', (), {'handlers': {}})()
    page = AccountPage(chart, persist_sort=persist)
    now = _time.time()

    def stamp(minutes):
        return _time.strftime('%Y-%m-%d %H:%M:%S',
                              _time.localtime(now - minutes * 60))

    page.update(summary={'kind': '期货', 'balance': 1.0, 'available': 1.0,
                         'float_profit': 0.0, 'close_profit': 0.0,
                         'extra_label': '保证金', 'extra': 0.0,
                         'ratio_label': '风险度', 'ratio': 0.0,
                         'ratio_percent': True, 'positions': 0,
                         'orders': 0},
                curve=[(stamp(120), 1.0), (stamp(10), 2.0),
                       (stamp(1), 3.0)],
                tables={})
    return page, chart


def test_account_page_refresh_interval_persists(monkeypatch, tmp_path):
    import minibt.strategy.pages as pages

    monkeypatch.setattr(pages, 'SORT_FILE', str(tmp_path / 'prefs.json'))
    page, _chart = _page_with_curve(persist=True)
    assert page.interval == 1.0 and page.curve_range == 'all'
    page._on_interval(2)
    page._on_range('60')
    assert (tmp_path / 'prefs.json').exists()

    page2, _chart2 = _page_with_curve(persist=True)
    assert page2.interval == 2.0
    assert page2.curve_range == '60'

    page3, _chart3 = _page_with_curve(persist=False)   # 不持久化 → 默认
    assert page3.interval == 1.0 and page3.curve_range == 'all'


def test_account_page_curve_range_filters_points():
    import time as _time

    page, _chart = _page_with_curve()
    assert len(page._filtered_curve()) == 3          # 全部
    page.curve_range = '60'
    assert len(page._filtered_curve()) == 2          # 1 小时（去掉 120 分钟前）
    page.curve_range = '30'
    assert len(page._filtered_curve()) == 2
    page.curve_range = 'session'
    page._session_from = _time.time() - 700          # 本次会话覆盖 10 分钟前
    assert len(page._filtered_curve()) == 2


def test_account_page_manual_refresh():
    page, chart = _page_with_curve()
    calls = []
    page.on_refresh = lambda: calls.append(1)
    page._on_refresh()
    assert calls == [1]
    page._on_interval(0)                             # 0 = 手动
    assert page.interval == 0.0
    assert '手动' in chart.panel.html and '曲线区间' in chart.panel.html


def test_account_page_interval_and_range_are_wired():
    tools = TOOLS.read_text(encoding='utf-8')
    assert 'def _account_interval' in tools
    assert 'def refresh_account_page_now' in tools
    assert 'interval <= 0' in tools                  # 手动 → 不自动刷 ✓
    window = WINDOW.read_text(encoding='utf-8')
    assert 'def account_refresh_interval' in window
    assert 'on_account_refresh' in window
    realtime = REALTIME.read_text(encoding='utf-8')
    assert 'on_account_refresh' in realtime
    pages_src = (REPO / 'minibt' / 'strategy' / 'pages.py').read_text(
        encoding='utf-8')
    for key in ('def _filtered_curve', 'def _ts_of', 'minibt_account_interval',
                'minibt_account_range', 'minibt_account_refresh'):
        assert key in pages_src, key


# ------------------------------- 账户页：「本次会话」按程序启动 / 导出曲线图
def test_account_page_session_range_uses_program_start():
    import time as _time

    from minibt.strategy import pages as pages_mod

    page, _chart = _page_with_curve()
    start = pages_mod.PROGRAM_START
    fmt = lambda stamp: _time.strftime(  # noqa: E731
        '%Y-%m-%d %H:%M:%S', _time.localtime(stamp))
    page.update(curve=[(fmt(start - 3600), 1.0),      # 上次会话遗留
                       (fmt(start + 5), 2.0),
                       (fmt(start + 60), 3.0)])
    page.curve_range = 'session'
    kept = page._filtered_curve()
    assert len(kept) == 2                            # 启动前的点被排除 ✓
    page.curve_range = 'all'
    assert len(page._filtered_curve()) == 3


def test_account_page_exports_curve_png(monkeypatch, tmp_path):
    import minibt.strategy.pages as pages

    monkeypatch.setattr(pages, 'EXPORTS_DIR', str(tmp_path))
    page, chart = _page_with_curve()
    path = page.export_curve_png()
    assert path and pathlib.Path(path).exists()
    assert pathlib.Path(path).read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
    page._on_curve_png()
    assert '已导出' in page.notice
    assert '导出曲线图（PNG）' in chart.panel.html
    # 点太少 → 不导出 ✓
    page.update(curve=[('09:00:00', 1.0)])
    assert page.export_curve_png() is None
    page._on_curve_png()
    assert '至少 2 个点' in page.notice


def test_account_page_curve_and_program_start_wiring():
    pages_src = (REPO / 'minibt' / 'strategy' / 'pages.py').read_text(
        encoding='utf-8')
    assert 'from ..utils import PROGRAM_START' in pages_src
    assert 'self._session_from = PROGRAM_START' in pages_src
    assert 'minibt_account_curve' in pages_src
    assert 'def export_curve_png' in pages_src
    utils = (REPO / 'minibt' / 'utils.py').read_text(encoding='utf-8')
    assert 'PROGRAM_START = _time.time()' in utils


# --------------------------------- 账户页：基准线 + 收益/回撤 + 整页截图
def test_account_page_curve_stats_and_baseline():
    import time as _time

    page, chart = _page_with_curve()
    now = _time.time()
    fmt = lambda index: _time.strftime(  # noqa: E731
        '%Y-%m-%d %H:%M:%S', _time.localtime(now - (10 - index) * 60))
    page.update(curve=[(fmt(0), 100.0), (fmt(1), 110.0),
                       (fmt(2), 95.0), (fmt(3), 108.0)])
    stats = page._curve_stats()
    assert stats['origin'] == 100.0 and stats['latest'] == 108.0
    assert abs(stats['profit'] - 8.0) < 1e-9
    assert abs(stats['rate'] - 8.0) < 1e-9
    assert abs(stats['drawdown'] - (-13.6364)) < 1e-3
    html = chart.panel.html
    assert '期初 <b>100.00</b>' in html
    assert '最新 <b>108.00</b>' in html
    assert '最大回撤 -13.64%' in html
    assert 'class="base"' in html             # 期初基准虚线 ✓
    # 期初资金参与缩放 → 基准线不会跑出画面
    assert stats['low'] <= stats['origin'] <= stats['high']


def test_account_page_screenshot(monkeypatch, tmp_path):
    import minibt.strategy.pages as pages

    monkeypatch.setattr(pages, 'EXPORTS_DIR', str(tmp_path))
    page, chart = _page_with_curve()

    class _Pixmap:
        def save(self, path, fmt='PNG'):
            pathlib.Path(path).write_bytes(b'\x89PNG\r\n\x1a\nfoo')
            return True

    chart.win.grab = lambda: _Pixmap()
    path = page.screenshot()
    assert path and pathlib.Path(path).exists()
    assert pathlib.Path(path).name.startswith('账户_截图_')
    page._on_screenshot()
    assert '截图已导出' in page.notice

    # 拿不到窗口 → 回退曲线图 ✓
    chart.win.grab = None
    assert page.screenshot() is None
    page._on_screenshot()
    assert '曲线图' in page.notice


def test_account_page_baseline_and_screenshot_wiring():
    pages_src = (REPO / 'minibt' / 'strategy' / 'pages.py').read_text(
        encoding='utf-8')
    for key in ('def _curve_stats', 'def screenshot', 'minibt_account_shot',
                '截图（PNG）', '最大回撤', '期初 <b>'):
        assert key in pages_src, key
    assert pages_src.startswith('"""回测信息页')      # 文件头没被破坏 ✓
