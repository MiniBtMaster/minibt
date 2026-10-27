# coding: utf-8
"""minibt 股票实时接口（``StockApi`` 接富途 OpenD）回归测试。

用户需求：

* 像 ``TqApi`` 那样给 minibt 提供一个 ``StockApi``（富途）；
* ``Bt.addStockapi(...)`` 与 ``addTqapi`` 对称；
* 手动加策略 + 打开实时图表的用法不变；
* 未启动 FutuOpenD 时**直接报错**。

    pytest tests/test_minibt_stock_api.py
"""
from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
STOCK_API = REPO / 'minibt' / 'stock_api.py'
BT = REPO / 'minibt' / 'bt.py'
UTILS = REPO / 'minibt' / 'utils.py'
BASE = REPO / 'minibt' / 'strategy' / 'base.py'
INIT = REPO / 'minibt' / '__init__.py'
PYPROJECT = REPO / 'minibt' / 'pyproject.toml'
REQUIREMENTS = REPO / 'minibt' / 'requirements.txt'

pytestmark = pytest.mark.skipif(
    not STOCK_API.exists(), reason='需要仓库里的 minibt 源码')


# ------------------------------------------------------------ 基础映射
def test_futu_code_mapping():
    from minibt import futu_code

    assert futu_code('600000') == 'SH.600000'
    assert futu_code('000001') == 'SZ.000001'
    assert futu_code('300750') == 'SZ.300750'
    assert futu_code('00700') == 'HK.00700'
    assert futu_code('AAPL') == 'US.AAPL'
    assert futu_code('SH.600000') == 'SH.600000'
    assert futu_code('600000.SH') == 'SH.600000'
    with pytest.raises(ValueError):
        futu_code('1234')


def test_period_mapping():
    from minibt.stock_api import PERIOD_TO_KLTYPE

    assert PERIOD_TO_KLTYPE[60] == 'K_1M'
    assert PERIOD_TO_KLTYPE[300] == 'K_5M'
    assert PERIOD_TO_KLTYPE[86400] == 'K_DAY'
    assert PERIOD_TO_KLTYPE[604800] == 'K_WEEK'


# ------------------------------------------------------------ 对外导出 / 接线
def test_stock_api_is_exported():
    import minibt

    for name in ('StockApi', 'StockTargetPosTask', 'futu_code'):
        assert name in minibt.__all__, name
        assert hasattr(minibt, name), name


def test_bt_has_add_stock_api():
    bt_source = _read(BT)
    assert 'def addStockapi(' in bt_source
    assert 'def addstock(' in bt_source
    assert 'add_stockapi = addStockapi' in bt_source
    assert '_stock_api' in bt_source


def test_tqobjs_prefers_stock_target_pos_task():
    utils = _read(UTILS)
    assert "getattr(self._api, 'target_pos_task', None)" in utils
    assert 'factory(self.symbol)' in utils
    # 兼容 StockApi 的 _loop.is_closed()（tqsdk 也有）
    assert "getattr(self._api, '_loop', None)" in utils


def test_live_chart_uses_the_same_tq_api_contract():
    """实时图表只认这几个方法 —— StockApi 都实现了 ✓"""
    api = _read(STOCK_API)
    for name in ('get_kline_serial', 'get_tick_serial', 'get_quote',
                 'wait_update', 'is_changing', 'insert_order',
                 'cancel_order', 'get_order', 'get_position', 'get_account',
                 'target_pos_task', 'close'):
        assert f'def {name}(' in api, name


def test_no_opend_raises(monkeypatch):
    """OpenD 没启动 → RuntimeError（不会静默返回空数据 ✓）"""
    from minibt import StockApi

    with pytest.raises((RuntimeError, ImportError)) as info:
        StockApi(host='127.0.0.1', port=1, timeout=1)
    message = str(info.value)
    assert 'FutuOpenD' in message or 'futu-api' in message


# ------------------------------------------------------------ 目标仓 → 单笔下单
def test_target_pos_task_places_one_order_per_change():
    from minibt import StockTargetPosTask

    class FakeApi:
        def __init__(self):
            self.calls = []
            self.position = 0

        def _net_position(self, symbol):
            return self.position

        def insert_order(self, symbol, direction, offset='', volume=0,
                         **kwargs):
            self.calls.append((symbol, direction, offset, volume))
            self.position += volume if direction == 'BUY' else -volume
            return None

    api = FakeApi()
    task = StockTargetPosTask(api, 'SH.600000')

    task.set_target_volume(300)
    assert api.calls == [('SH.600000', 'BUY', 'OPEN', 300)]   # 一次下完 ✓

    task.set_target_volume(0)
    assert api.calls[-1] == ('SH.600000', 'SELL', 'CLOSE', 300)

    before = len(api.calls)
    task.set_target_volume(0)                                 # 已到位 → 不下单
    assert len(api.calls) == before


# ------------------------------------------------------------ 顺带修复的 bug
def test_live_buy_loop_has_no_infinite_wait():
    """``while pos != target or past deadline`` 会在超时后**死循环** ✗"""
    source = _read(BASE)
    assert 'or _time.time() > deadline' not in source
    assert source.count('and _time.time() < deadline') >= 3


# ------------------------------------------------------------ 依赖
def test_futu_api_dependency_declared():
    assert 'futu-api' in _read(PYPROJECT)
    assert 'futu-api' in _read(REQUIREMENTS)


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


def test_futu_code_accepts_tianqin_prefix():
    """天勤写法 `SSE.600007` / `SZSE.000001` 必须转成富途的 `SH.` / `SZ.` ✓

    以前原样返回 → 富途报 `format of code SSE.600007 is wrong`，
    订阅 K 线全失败 → 图表没 K 线、迷你图空白 ✗
    """
    from minibt.stock_api import futu_code
    assert futu_code('SSE.600007') == 'SH.600007'
    assert futu_code('SZSE.000001') == 'SZ.000001'
    assert futu_code('600007') == 'SH.600007'
    assert futu_code('000001') == 'SZ.000001'
    assert futu_code('600007.SH') == 'SH.600007'
    assert futu_code('00700') == 'HK.00700'
    assert futu_code('AAPL') == 'US.AAPL'


def test_bars_from_frame_ignores_non_frame():
    """`len(SimpleNamespace)` 会抛 TypeError → 刷新节拍每 0.5s 报错 ✗

    富途某些路径会把 quote 当 K 线 frame 传进来；`bars_from_frame` 现在
    先确认是表格（有 `to_dict`），否则返回空列表 ✓
    """
    from types import SimpleNamespace
    from minibt.desk.protocol import bars_from_frame
    quote = SimpleNamespace(symbol='SH.600007', last_price=10.0)
    assert bars_from_frame(quote) == []
    assert bars_from_frame(None) == []


def test_subscription_pool_keeps_chart_codes():
    """订阅池：滚出可见就退订，但**图表正在用的不退** ✓（miniqt 同款）"""
    from minibt.desk.stocks import SubscriptionPool

    class FakeApi:
        def __init__(self):
            self.subs = set()

        def subscribe_quote(self, code, period=60):
            self.subs.add(code)

        def unsubscribe_quote(self, code, period=60):
            self.subs.discard(code)

    import minibt.desk.stocks as stocks_mod
    api = FakeApi()
    pool = SubscriptionPool(api)
    pool.set_owner('visible', ['SH.600000', 'SH.600001'])
    assert api.subs == {'SH.600000', 'SH.600001'}
    pool.set_charts(['SH.600030'])
    assert 'SH.600030' in api.subs
    # 换屏：宽限期内**先不退**（富途限制不足 1 分钟不能退 ✗）
    pool.set_owner('visible', ['SZ.000001'])
    assert 'SZ.000001' in api.subs
    assert 'SH.600000' in api.subs          # 还在 65 秒宽限期里 ✓
    # 把时间推进 70 秒 → 旧的退订，图表那只仍在 ✓
    real = stocks_mod.time.monotonic
    stocks_mod.time.monotonic = lambda: real() + 70
    try:
        pool.sync()
    finally:
        stocks_mod.time.monotonic = real
    assert 'SH.600000' not in api.subs      # 宽限期到 → 退订 ✓
    assert 'SH.600030' in api.subs          # 图表不退 ✓


def test_no_len_on_tick_objects():
    """富途股票 `get_tick_serial` 返回的是单个 tick 对象 → 不能 len() ✗

    （以前 `_ticks_payload` 直接 `len(frame)` → 「看盘 tab」每拍失败一次）
    """
    source = (REPO / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    block = source.split('def _book_ticks', 1)[1][:2000]
    assert "if not hasattr(frame, 'to_dict'):" in block
    # spark：DataFrame 不能用 `or` 判断真假 ✗
    spark = source.split('def spark_values', 1)[1][:1500]
    assert 'or frames.get(' not in spark


def test_pool_reconciles_stray_subscriptions():
    """池子要**对账** `api._subs`：别人加的、已不需要的订阅必须退掉 ✓

    （否则表现就是"向下滚动时订阅数只增不减" ✗）
    """
    from minibt.desk.stocks import SubscriptionPool

    class FakeApi:
        def __init__(self):
            self._subs = {('SH.600000', 'K_1M'), ('SH.600009', 'K_DAY')}

        def subscribe_quote(self, code, period=60):
            self._subs.add((code, 'K_1M'))

        def unsubscribe_quote(self, code, period=60):
            for item in list(self._subs):
                if item[0] == code:
                    self._subs.discard(item)

    api = FakeApi()
    pool = SubscriptionPool(api)
    pool.set_owner('visible', ['SH.600000'])
    # 池子只管自己订阅的；K_DAY 这类"别处加的"在宽限期后才对账 ✓
    assert ('SH.600000', 'K_1M') in api._subs


def test_markers_class_reuses_native_arrows():
    """`Markers` 把原来的两个原生箭头（向上/向下三角）归纳成自定义序列图形 ✓"""
    from minibt.markers import Markers, marker_name
    # 箭头就是箭头（不再退化成实心三角）；三角仍保留 ✓
    assert marker_name('arrowUp') == 'arrow_up'
    assert marker_name('arrowDown') == 'arrow_down'
    assert marker_name('triangle') == 'triangle'
    assert marker_name('inverted_triangle') == 'inverted_triangle'
    rows = Markers.series([
        {'time': 10, 'price': 5.0, 'up': True, 'color': '#26a69a', 'text': 'B'},
        {'time': 20, 'price': 6.0, 'up': False, 'color': '#ef5350', 'text': 'S'},
    ])
    assert [row['shapes'][0]['marker'] for row in rows] == [
        'arrow_up', 'arrow_down']
    assert [row['shapes'][0]['color'] for row in rows] == ['#26a69a', '#ef5350']
    assert [row['value'] for row in rows] == [5.0, 6.0]      # 自动缩放用 ✓


# ------------------------------------------------------------ 真实下单失败
def _fake_real_api(ret=-1, detail='rejected by broker'):
    from types import SimpleNamespace
    from minibt.stock_api import StockApi

    class FakeTrd:
        def __init__(self):
            self.calls = []

        def place_order(self, **kwargs):
            self.calls.append(kwargs)
            return ret, detail

        def modify_order(self, **kwargs):
            self.calls.append(kwargs)
            return ret, detail

    api = StockApi.__new__(StockApi)
    api._trd = FakeTrd()
    api._futu = SimpleNamespace(
        TrdSide=SimpleNamespace(BUY='BUY', SELL='SELL'),
        OrderType=SimpleNamespace(NORMAL='NORMAL'),
        ModifyOrderOp=SimpleNamespace(CANCEL='CANCEL'))
    api._RET_OK = 0
    api._prices = {'SH.600000': 10.0}
    api._orders = []
    api._trades = []
    api._positions = {}
    api._position_objs = {}
    api._trade_seq = 0
    api._cash = 100000.0
    api._realized_pnl = 0.0
    api._commission = 0.0
    api._sim = None
    api._sim_commission = 0.0
    api._save_equity = lambda: None
    api.desk = SimpleNamespace(push_log=lambda *a, **k: None)
    api.account_label = lambda symbol='': '富途'
    return api


def test_real_stock_order_rejection_does_not_fill_locally():
    """富途拒单 → 不能本地 _apply_fill / 显示成交 ✓"""
    import pytest

    api = _fake_real_api()
    with pytest.raises(RuntimeError, match='富途下单失败'):
        api.insert_order('SH.600000', 'BUY', 'OPEN', 100, limit_price=10.0)
    assert api._orders == []
    assert api._trades == []
    assert api._positions == {}
    assert api._cash == 100000.0


def test_real_stock_cancel_failure_keeps_order_alive():
    """富途撤单失败 → 不能本地标 CANCELLED ✓"""
    import pytest
    from types import SimpleNamespace

    api = _fake_real_api()
    api._orders = [SimpleNamespace(order_id='O1', status='ALIVE')]
    with pytest.raises(RuntimeError, match='富途撤单失败'):
        api.cancel_order('O1')
    assert api._orders[0].status == 'ALIVE'


def test_real_order_is_submitted_then_polled_to_finished(monkeypatch):
    """真实订单不能本地直接 FINISHED；order_list_query 轮询成交状态 ✓"""
    from types import SimpleNamespace
    from minibt.stock_api import StockApi
    import pandas as pd

    class FakeTrd:
        status = 'SUBMITTED'

        def place_order(self, **kwargs):
            return 0, pd.DataFrame([{'order_id': 'O1'}])

        def order_list_query(self, **kwargs):
            return 0, pd.DataFrame([{
                'order_id': 'O1', 'order_status': self.status,
                'qty': 100, 'dealt_qty': 100 if self.status == 'FILLED_ALL' else 0,
                'code': 'SH.600000', 'trd_side': 'BUY',
                'price': 10.0, 'dealt_avg_price': 10.0,
            }])

        def deal_list_query(self, **kwargs):
            return 0, pd.DataFrame([])

    api = StockApi.__new__(StockApi)
    api._trd = FakeTrd()
    api._futu = SimpleNamespace(
        TrdSide=SimpleNamespace(BUY='BUY', SELL='SELL'),
        OrderType=SimpleNamespace(NORMAL='NORMAL'),
        ModifyOrderOp=SimpleNamespace(CANCEL='CANCEL'))
    api._RET_OK = 0
    api._prices = {'SH.600000': 10.0}
    api._orders = []
    api._trades = []
    api._positions = {}
    api._position_objs = {}
    api._cash = 100000.0
    api._realized_pnl = 0.0
    api._commission = 0.0
    api._sim = None
    api._sim_commission = 0.0
    api._save_equity = lambda: None
    api.desk = SimpleNamespace(push_log=lambda *a, **k: None)
    api.account_label = lambda symbol='': '富途'

    order = api.insert_order('SH.600000', 'BUY', 'OPEN', 100,
                             limit_price=10.0)
    assert order.status == 'SUBMITTED'
    assert api._positions == {}                 # 未成交不动本地账本 ✓

    FakeTrd.status = 'FILLED_ALL'
    polled = api.get_order('O1')
    assert polled.status == 'FINISHED'
    assert polled.volume_left == 0


def test_real_order_rejects_wrong_market_account():
    """CN 账户下不能下 HK 单，反之亦然（提示切换市场）"""
    import pytest

    api = _fake_real_api()
    api.trd_market = 'CN'
    api._trd.place_order = lambda **kwargs: (0, None)  # 不应到这里
    with pytest.raises(RuntimeError, match='市场'):
        api.insert_order('HK.00700', 'BUY', 'OPEN', 100, limit_price=10.0)
