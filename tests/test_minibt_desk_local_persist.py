"""本地期货模拟账户 SQLite 持久化 ✓"""
from __future__ import annotations

import os

from minibt.desk.local_data import LocalSim, default_sim_db


def _sim(db, cash=100000.0):
    sim = LocalSim(cash, db_path=str(db))
    sim.set_contract('DCE.pp2609', volume_multiple=5, price_tick=1,
                     margin_rate=0.05,
                     commission={'fixed_commission': 1.0})
    sim.set_price('DCE.pp2609', 100.0)
    return sim


def test_local_sim_persists_account_positions_and_specs(tmp_path):
    db = tmp_path / 'desk_sim.sqlite3'
    sim = _sim(db)
    assert sim.order('DCE.pp2609', 'buy', 2, 100.0)['ok']
    sim.save()

    restored = LocalSim(999999.0, db_path=str(db))
    assert restored.initial_cash == 100000.0       # 旧账户优先，不被新参数覆盖
    assert restored.cash == 99998.0                 # 2 手 × 1 元手续费
    assert restored.positions['DCE.pp2609']['long'] == 2.0
    assert len(restored.orders) == 1
    assert len(restored.trades) == 1
    assert restored.symbol_stats['DCE.pp2609']['trades'] == 1
    assert restored.multiplier('DCE.pp2609') == 5.0
    assert restored.margin_rate('DCE.pp2609') == 0.05
    assert restored.fee_rules['DCE.pp2609'] == {'mode': 'fixed', 'value': 1.0}


def test_local_sim_reset_persists_empty_account(tmp_path):
    db = tmp_path / 'desk_sim.sqlite3'
    sim = _sim(db)
    sim.order('DCE.pp2609', 'buy', 1, 100.0)
    sim.reset()

    restored = LocalSim(100000.0, db_path=str(db))
    assert restored.positions == {}
    assert restored.orders == []
    assert restored.trades == []
    assert restored.cash == 100000.0


def test_local_sim_payload_trade_count_not_capped_at_200():
    sim = LocalSim(100000.0)
    sim.symbol_stats = {'X': {'trades': 250, 'closes': 125}}
    sim.trades = [{'id': index, 'ts': '', 'symbol': 'X', 'side': 'buy',
                   'offset': '开仓', 'qty': 1.0, 'price': 100.0,
                   'status': '全部成交', 'realized': 0.0}
                  for index in range(200)]
    payload = sim.payload('X')
    assert payload['values']['trade_count'] == 250


def test_default_sim_db_env_override(monkeypatch, tmp_path):
    path = tmp_path / 'custom.sqlite3'
    monkeypatch.setenv('MINIBT_DESK_SIM_DB', str(path))
    assert default_sim_db() == str(path)


def test_desk_local_sim_uses_sqlite_path(monkeypatch, tmp_path):
    from minibt.desk.app import Desk

    path = tmp_path / 'desk.sqlite3'
    monkeypatch.setenv('MINIBT_DESK_SIM_DB', str(path))
    first = Desk(offline=True)
    sim = first.local_sim()
    sim.set_price('X', 100.0, 2)
    assert sim.order('X', 'buy', 1, 100.0)['ok']
    first.close()

    second = Desk(offline=True)
    restored = second.local_sim()
    assert restored.positions['X']['long'] == 1.0
    second.close()
