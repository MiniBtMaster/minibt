"""交易工作台：订单状态机 / 风控 / 条件单 / 对账 / 审计。"""
from __future__ import annotations

import csv
import os

import pytest

from minibt.desk.workbench import (ALIVE, CANCELLED, FINISHED, PARTIAL,
                                   PENDING, REJECTED, AuditStore, OrderTicket,
                                   Workbench, normalize_state)


class FakeTrader:
    def __init__(self):
        self.calls = []
        self.fail = False

    def account_label(self, symbol=''):
        return '测试账户'

    def is_real(self, symbol=''):
        return False

    def ready(self, symbol=''):
        return True

    def place(self, symbol, side, volume, price=None):
        self.calls.append(('place', symbol, side, volume, price))
        return '下单失败：拒单' if self.fail else (
            f'下单成功 {symbol} {side} {volume}')

    def close_symbol(self, symbol, volume=0):
        self.calls.append(('close', symbol, volume))
        return f'平仓成功 {symbol} {volume}'

    def cancel_order(self, order_id, symbol=''):
        self.calls.append(('cancel', order_id, symbol))
        return f'已撤 {order_id}'

    def action(self, action, symbol=''):
        self.calls.append(('action', action, symbol))
        return f'动作 {action} 完成'


class FakeDesk:
    def __init__(self):
        self.trading = True
        self._last_rows = {'SHFE.ag2612': {'last': 7000.0}}
        self.trader = FakeTrader()
        self.logs = []
        self.pending = []

    def trading_view(self):
        return self.trader

    def push_log(self, text, level='info'):
        self.logs.append((level, text))

    def position_payload(self, symbol):
        return {'long': {'volume': 2}, 'short': {}}

    def account_payload(self, limit=100, symbol=''):
        return {'positions': [{'profit': -100.0}, {'profit': 30.0}]}

    def pending_orders(self, symbol='', local=False):
        return [item for item in self.pending
                if not symbol or item.get('symbol') == symbol]


@pytest.fixture()
def bench(tmp_path):
    desk = FakeDesk()
    work = Workbench(desk, db_path=str(tmp_path / 'audit.db'),
                     config_file=str(tmp_path / 'config.json'))
    return desk, work


def test_normalize_state_covers_exchange_statuses():
    assert normalize_state('SUBMITTED') == PENDING
    assert normalize_state('ALIVE') == ALIVE
    assert normalize_state('partially_filled') == PARTIAL
    assert normalize_state('FILLED') == FINISHED
    assert normalize_state('canceled') == CANCELLED
    assert normalize_state('REJECT') == REJECTED
    assert normalize_state('??') == PENDING


def test_order_ticket_parses_aliases():
    ticket = OrderTicket.parse({'symbol': 'SHFE.ag2612', 'action': 'sell',
                                'qty': '3', 'type': 'limit',
                                'price': '7010', 'tif': 'ioc'})
    assert ticket.side == 'sell'
    assert ticket.volume == 3
    assert ticket.order_type == 'limit'
    assert ticket.price == 7010.0
    assert ticket.tif == 'IOC'


def test_submit_records_order_and_audit(bench):
    desk, work = bench
    result = work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy',
                          'volume': 2, 'price': 7000,
                          'order_type': 'limit'})
    assert result['ok'] is True
    assert result['status'] == PENDING
    assert desk.trader.calls[-1] == ('place', 'SHFE.ag2612', 'buy', 2, 7000.0)
    orders = work.store.orders()
    assert orders and orders[0]['status'] == PENDING
    assert orders[0]['tif'] == 'GFD'
    assert any(item['kind'] == 'order' for item in work.store.audit())
    snapshot = work.snapshot()
    assert snapshot['type'] == 'workbench'
    assert snapshot['stats']['orders'] == 1
    assert snapshot['account'] == '测试账户'


def test_rejected_order_is_marked_and_audited(bench):
    desk, work = bench
    desk.trader.fail = True
    result = work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy',
                          'volume': 1})
    assert result['ok'] is False
    assert work.store.orders()[0]['status'] == REJECTED
    assert any(item['kind'] == 'order' and item['status'] == REJECTED
               for item in work.store.audit())


def test_read_only_desk_refuses_orders(bench):
    desk, work = bench
    desk.trading = False
    result = work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy',
                          'volume': 1})
    assert result['ok'] is False
    assert '未启用' in result['text']
    assert work.store.orders() == []


def test_risk_limits_block_volume_and_daily_count(bench):
    _desk, work = bench
    work.configure({'enabled': True, 'max_volume': 2,
                    'max_orders_per_day': 1, 'max_daily_loss': 100,
                    'allow_short': True})
    assert work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy',
                        'volume': 3})['ok'] is False
    first = work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy',
                         'volume': 1})
    assert first['ok'] is True
    second = work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy',
                          'volume': 1})
    assert second['ok'] is False
    assert '单日委托数' in second['text']
    # 当日浮亏 -70，超过上限 50 → 再放开单日委托数也拦
    work.configure({'enabled': True, 'max_orders_per_day': 0,
                    'max_daily_loss': 50})
    third = work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy',
                         'volume': 1})
    assert third['ok'] is False
    assert '单日亏损' in third['text']


def test_risk_limits_persist_and_reload(tmp_path):
    desk = FakeDesk()
    config = tmp_path / 'config.json'
    first = Workbench(desk, db_path=str(tmp_path / 'a.db'),
                      config_file=str(config))
    first.configure({'enabled': True, 'max_volume': 7})
    second = Workbench(desk, db_path=str(tmp_path / 'b.db'),
                       config_file=str(config))
    assert second.limits['enabled'] is True
    assert second.limits['max_volume'] == 7


def test_conditional_order_fires_when_price_crosses(bench):
    desk, work = bench
    result = work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy',
                          'volume': 1, 'order_type': 'conditional',
                          'trigger_price': 7100, 'condition': '>='})
    assert result['ok'] is True
    assert len(work.conditional()) == 1
    assert work.check_conditions({'SHFE.ag2612': 7000}) == []
    fired = work.check_conditions({'SHFE.ag2612': 7200})
    assert fired and fired[0]['ok'] is True
    assert work.conditional() == []
    assert desk.trader.calls[-1][0] == 'place'


def test_cancel_modify_and_close_partial(bench):
    desk, work = bench
    work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy', 'volume': 1,
                 'price': 7000, 'order_type': 'limit'})
    order = work.store.orders()[0]
    result = work.modify({'symbol': 'SHFE.ag2612', 'side': 'buy',
                          'volume': 1, 'price': 7010,
                          'order_id': 'broker-1', 'id': order['id']})
    assert result['ok'] is True
    assert ('cancel', 'broker-1', 'SHFE.ag2612') in desk.trader.calls
    assert work.store.orders(5)[0]['price'] == 7010.0
    assert work.store.orders(5)[0]['order_type'] == 'limit'
    partial = work.close_partial({'symbol': 'SHFE.ag2612', 'volume': 1})
    assert partial['ok'] is True
    assert ('close', 'SHFE.ag2612', 1) in desk.trader.calls


def test_reconcile_reports_local_and_broker_diff(bench):
    desk, work = bench
    work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy', 'volume': 1})
    desk.pending = [{'symbol': 'SHFE.ag2612', 'order_id': 'broker-9',
                     'status': 'ALIVE', 'volume': 1}]
    result = work.reconcile()
    assert result['local_open'] == 1
    assert result['broker_open'] == 1
    assert result['extra'] and result['extra'][0]['order_id'] == 'broker-9'
    assert result['ok'] is False


def test_audit_export_csv(bench, tmp_path):
    _desk, work = bench
    work.submit({'symbol': 'SHFE.ag2612', 'side': 'buy', 'volume': 1})
    path = work.store.export_csv(str(tmp_path / 'audit.csv'), table='audit')
    assert os.path.isfile(path)
    with open(path, encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle))
    assert rows and 'kind' in rows[0]


def test_audit_store_prune(tmp_path):
    store = AuditStore(str(tmp_path / 'a.db'))
    store.log('order', 'old')
    store._db.execute('UPDATE audit SET ts=0')
    store._db.commit()
    assert store.prune(keep_days=1) == 1
    assert store.audit() == []
