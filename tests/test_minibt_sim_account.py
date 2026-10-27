# coding: utf-8
"""minibt 本地模拟盘持久化（``StockApi(sim_account='default')``）回归测试。

用户需求：模拟盘账户要**持久化** —— 下次打开实时图表还能读到
持仓 / 委托 / 成交 / 权益曲线。

    pytest tests/test_minibt_sim_account.py
"""
from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SIM = REPO / 'minibt' / 'sim_account.py'
STOCK_API = REPO / 'minibt' / 'stock_api.py'

pytestmark = pytest.mark.skipif(
    not SIM.exists() or not STOCK_API.exists(),
    reason='需要仓库里的 minibt 源码')


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


# ---------------------------------------------------------------- 存储层
def test_store_roundtrip(tmp_path):
    from minibt.sim_account import StockSimStore

    db = str(tmp_path / 'sim.db')
    with StockSimStore('default', db_path=db, initial_cash=50000) as store:
        assert store.load_account()['cash'] == 50000
        store.save_position('SH.600000',
                            {'long': 100, 'short': 0,
                             'avg_long': 9.7, 'avg_short': 0.0})
        store.save_account(40000.0, 0.0, 0.0)
        store.add_order('o1', 'SH.600000', 'BUY', 'OPEN', 100, 9.7)
        store.add_trade('t1', 'o1', 'SH.600000', 'BUY', 'OPEN', 100, 9.7, 0.0)
        store.add_equity(40000.0, 970.0, 40970.0, 0.0, 0.0)

    # 重新打开（= 下次启动程序）→ 数据还在 ✓
    with StockSimStore('default', db_path=db) as store:
        assert store.load_account()['cash'] == 40000
        assert store.load_positions()['SH.600000']['long'] == 100
        orders = store.recent_orders()
        assert len(orders) == 1 and orders[0]['order_id'] == 'o1'
        trades = store.recent_trades()
        assert len(trades) == 1 and trades[0]['trade_id'] == 't1'
        assert len(store.equity_curve()) == 1
        # 撤单状态也能落盘
        store.update_order('o1', 'CANCELLED')
        assert store.recent_orders()[0]['status'] == 'CANCELLED'
        # 重置 → 回到初始资金、清空持仓
        store.reset()
        assert store.load_account()['cash'] == 50000
        assert store.load_positions() == {}
        assert store.recent_orders() == []


def test_store_accounts_are_isolated(tmp_path):
    from minibt.sim_account import StockSimStore

    db = str(tmp_path / 'sim.db')
    with StockSimStore('a', db_path=db, initial_cash=10000) as store_a:
        store_a.add_order('oa', 'SH.600000', 'BUY', 'OPEN', 100, 10)
    with StockSimStore('b', db_path=db, initial_cash=20000) as store_b:
        assert store_b.recent_orders() == []
        assert store_b.load_account()['cash'] == 20000


# ---------------------------------------------------------------- 记账逻辑
def _bare_api():
    """不打 FutuOpenD 也能测 ``_apply_fill``（只用手工填好的字段 ✓）"""
    from minibt import StockApi

    api = StockApi.__new__(StockApi)
    api._positions = {}
    api._position_objs = {}
    api._orders = []
    api._trades = []
    api._prices = {'SH.600000': 10.0}
    api._cash = 100000.0
    api._realized_pnl = 0.0
    api._commission = 0.0
    api._market_value = 0.0
    api._sim = None
    api._sim_commission = 0.0
    api._trade_seq = 0
    api._trade_enabled = False
    api._trd = None
    from types import SimpleNamespace
    api._account = SimpleNamespace(
        balance=0.0, available=0.0, margin=0.0, float_profit=0.0,
        position_profit=0.0, close_profit=0.0, commission=0.0,
        risk_ratio=0.0)
    return api


def test_paper_cash_and_realized_pnl():
    api = _bare_api()

    api.insert_order('600000', 'BUY', 'OPEN', 1000)          # @10
    assert api.get_position('600000').pos == 1000
    assert api.get_account().available == pytest.approx(90000)

    api.insert_order('600000', 'SELL', 'CLOSE', 1000,
                     limit_price=11.0)                        # @11 → 赚 1000
    assert api.get_position('600000').pos == 0
    assert api.get_account().available == pytest.approx(101000)
    assert api.get_account().close_profit == pytest.approx(1000)


def test_short_open_and_cover():
    api = _bare_api()
    api.insert_order('600000', 'SELL', 'OPEN', 500)          # 卖出开空 @10
    assert api.get_position('600000').pos == -500
    api.insert_order('600000', 'BUY', 'CLOSE', 500,
                     limit_price=9.0)                         # 买回 @9 → 赚 500
    assert api.get_position('600000').pos == 0
    assert api.get_account().close_profit == pytest.approx(500)


# ---------------------------------------------------------------- 接线
def test_stock_api_defaults_to_persistent_sim_account():
    source = _read(STOCK_API)
    assert "sim_account: str | None = 'default'" in source
    assert 'def _load_sim' in source
    assert 'def _save_equity' in source
    assert 'def sim_equity_curve' in source
    assert 'def sim_trades' in source
    assert 'def sim_reset' in source
    # 纯内存模式仍可显式开启（sim_account=None）
    assert 'sim_account=None' in source
