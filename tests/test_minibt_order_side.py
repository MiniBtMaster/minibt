"""下单方向归一化 —— 回归「二级报价『开空』实际挂**开多**单」✗。

根因：``StrategyBase.insert_order`` 以前只写 ``if direction == OrderSide.Sell``，
而 ``OrderSide`` 是 **IntEnum**（``Buy=0`` / ``Sell=1``）—— 字符串 ``"SELL"``
跟它**永远不相等**（``'SELL' == OrderSide.Sell`` → ``False``）→ 一律落进
``else`` 变成 ``"BUY"`` ✗。而 ``live_tools._place`` 传的正是字符串 ``'SELL'``
→ 「开空」挂出了**开多**单 ✗（「平多」同理也会变成买 ✗）。
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _read(*parts):
    return REPO.joinpath(*parts).read_text(encoding='utf-8')


# --------------------------------------------------------------------------- #
# 纯函数
# --------------------------------------------------------------------------- #
def test_resolve_order_side_all_forms():
    from minibt.order import OrderSide, resolve_order_side

    assert resolve_order_side(OrderSide.Sell) == 'SELL'
    assert resolve_order_side(OrderSide.Buy) == 'BUY'
    assert resolve_order_side(1) == 'SELL'
    assert resolve_order_side(0) == 'BUY'
    for text in ('SELL', 'sell', 'Sell', 's', 'short'):
        assert resolve_order_side(text) == 'SELL', text
    for text in ('BUY', 'buy', 'Buy', 'b', 'long'):
        assert resolve_order_side(text) == 'BUY', text
    # 中文也认
    for text in ('卖', '卖出', '开空'):
        assert resolve_order_side(text) == 'SELL', text
    for text in ('买', '买入', '开多'):
        assert resolve_order_side(text) == 'BUY', text
    # 认不出来 → BUY（与方向默认值 OrderSide.Buy 一致 ✓）
    assert resolve_order_side(None) == 'BUY'
    assert resolve_order_side('???') == 'BUY'


def test_str_addition_is_the_bug():
    """把根因写成断言：字符串永远不等于 IntEnum 成员 ✓"""
    from minibt.order import OrderSide

    assert ('SELL' == OrderSide.Sell) is False
    assert (1 == OrderSide.Sell) is True


# --------------------------------------------------------------------------- #
# 端到端：策略层真的发出 SELL / BUY
# --------------------------------------------------------------------------- #
def test_strategy_insert_order_sends_correct_side():
    """★ 回归：``insert_order(direction='SELL')`` 必须真的发 SELL 单 ✗ 旧实现变 BUY"""
    from minibt.order import OrderSide
    from minibt.strategy.base import StrategyBase

    sent = []

    class FakeApi:
        def insert_order(self, symbol, direction, offset, volume,
                         limit_price, advanced, order_id, account):
            sent.append((symbol, direction, offset, volume))
            return None

    class FakeKLine:
        symbol = 'DCE.pp2609'

    class Stub:
        _is_live_trading = True
        _account = None
        api = FakeApi()
        _btklinedataset = type('D', (), {'default_kline': FakeKLine()})()

    call = StrategyBase.insert_order
    call(Stub(), kline=FakeKLine(), direction='SELL', offset='OPEN',
         volume=2, limit_price=8000.0)
    assert sent[-1] == ('DCE.pp2609', 'SELL', 'OPEN', 2)

    call(Stub(), kline=FakeKLine(), direction=OrderSide.Sell, offset='OPEN',
         volume=1)
    assert sent[-1][1] == 'SELL'

    call(Stub(), kline=FakeKLine(), direction='BUY', offset='OPEN', volume=1)
    assert sent[-1][1] == 'BUY'


def test_insert_order_normalizer_is_used():
    """源码约束：策略层不再自己比 ``OrderSide.Sell``，统一走 ``resolve_order_side`` ✓"""
    src = _read('minibt', 'strategy', 'base.py')
    assert 'resolve_order_side(direction)' in src
    start = src.index('def insert_order')
    body = src[start:start + 12000]
    assert 'if direction == OrderSide.Sell:' not in body


# --------------------------------------------------------------------------- #
# 二级报价三个按钮 → insert_order 的参数
# --------------------------------------------------------------------------- #
def test_depth_buttons_map_to_correct_order():
    """★★ 用户反馈的路径：二级报价「开空」= SELL/OPEN、「开多」= BUY/OPEN ✓"""
    from minibt.strategy.live_tools import LiveTools

    calls = []

    class FakeKLine:
        def insert_order(self, **kwargs):
            calls.append(kwargs)

    tools = LiveTools(object())
    tools._kline = lambda: FakeKLine()
    tools._trade_account = lambda: None
    tools._net = lambda: 0

    assert tools._place('short', 100.0, 2).startswith('开空')
    assert calls[-1]['direction'] == 'SELL', '「开空」挂成了别的方向 ✗'
    assert calls[-1]['offset'] == 'OPEN'
    assert calls[-1]['volume'] == 2
    assert calls[-1]['limit_price'] == 100.0

    assert tools._place('long', 100.0, 1).startswith('开多')
    assert calls[-1]['direction'] == 'BUY'
    assert calls[-1]['offset'] == 'OPEN'

    # 平仓：多头 → SELL/CLOSE（数量取 min(|净仓|, 输入) ✓）
    tools._net = lambda: 3
    assert tools._place('close', 100.0, 5).startswith('多头平仓')
    assert calls[-1]['direction'] == 'SELL'
    assert calls[-1]['offset'] == 'CLOSE'
    assert calls[-1]['volume'] == 3

    # 空头 → BUY/CLOSE
    tools._net = lambda: -2
    assert tools._place('close', 100.0, 5).startswith('空头平仓')
    assert calls[-1]['direction'] == 'BUY'
    assert calls[-1]['offset'] == 'CLOSE'
    assert calls[-1]['volume'] == 2

    # 无持仓 → 拒绝，不发单
    tools._net = lambda: 0
    assert tools._place('close', 100.0, 1) == '当前无持仓'
    assert len(calls) == 4


def test_depth_js_buttons_send_long_short_close():
    """JS 三个按钮的动作名必须与 Python 侧一致（long / short / close）✓"""
    from minibt.strategy.live_tools import _DEPTH_JS

    assert "sendOrder('long')" in _DEPTH_JS
    assert "sendOrder('short')" in _DEPTH_JS
    assert "sendOrder('close')" in _DEPTH_JS
    assert '>开多<' in _DEPTH_JS and '>开空<' in _DEPTH_JS
