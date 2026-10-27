"""平台化 / 运维：token / 定时任务 / 告警 / 策略版本 / headless 入口。"""
from __future__ import annotations

import os

import pytest

from minibt.desk import headless
from minibt.desk.ops import (Notifier, OpsService, StrategyVersions,
                             TaskScheduler, TokenStore)


class FakeDesk:
    def __init__(self):
        self.logs = []

    def push_log(self, text, level='info'):
        self.logs.append((level, text))

    def status(self):
        return {'ready': True, 'tabs': ['X']}


def test_token_issue_verify_scope_and_revoke(tmp_path):
    store = TokenStore(str(tmp_path / 'tokens.json'))
    item = store.issue('ci', scopes=['read', 'trade'], ttl=60)
    token = item['token']
    assert store.verify(token, 'read') is True
    assert store.verify(token, 'trade') is True
    assert store.verify(token, 'ops') is False
    assert store.verify('wrong', 'read') is False
    assert store.revoke(item['id']) is True
    assert store.verify(token, 'read') is False
    public = store.items()[0]
    assert 'hash' not in public and public['revoked'] is True


def test_token_expiry_and_admin_scope(tmp_path):
    store = TokenStore(str(tmp_path / 'tokens.json'))
    expired = store.issue('old', scopes=['read'], ttl=1)
    store._items[0]['expires'] = 1                      # noqa: SLF001
    assert store.verify(expired['token'], 'read') is False
    admin = store.issue('root', scopes=['admin'], ttl=0)
    assert store.verify(admin['token'], 'trade') is True
    assert store.verify(admin['token'], 'anything') is True


def test_scheduler_runs_due_and_records_history():
    scheduler = TaskScheduler()
    calls = []
    scheduler.register_builtin('ping', lambda payload: calls.append(payload))
    scheduler.add('ping', 1, 'ping', payload={'x': 1}, enabled=True)
    scheduler._tasks['ping']['next_run'] = 0             # noqa: SLF001
    results = scheduler.run_due()
    assert results and results[0]['ok'] is True
    assert calls == [{'x': 1}]
    assert scheduler.history
    assert scheduler.due() == []                        # 已经排到下一轮
    scheduler.enable('ping', False)
    scheduler._tasks['ping']['next_run'] = 0             # noqa: SLF001
    assert scheduler.due() == []


def test_scheduler_captures_errors():
    scheduler = TaskScheduler()

    def boom(payload=None):
        raise RuntimeError('bad')

    scheduler.register_builtin('boom', boom)
    scheduler.add('boom', 1, 'boom')
    scheduler._tasks['boom']['next_run'] = 0             # noqa: SLF001
    result = scheduler.run_due()[0]
    assert result['ok'] is False
    assert 'bad' in result['error']
    assert scheduler.items()[0]['errors'] == 1


def test_notifier_config_and_local_history(tmp_path):
    notifier = Notifier(str(tmp_path / 'notify.json'))
    record = notifier.send('测试', '没有通道')
    assert record['results'][0]['channel'] == 'local'
    block = notifier.configure('wecom', {'enabled': False,
                                         'webhook': 'https://example.invalid'})
    assert block['webhook'] == 'https://example.invalid'
    again = Notifier(str(tmp_path / 'notify.json'))
    assert again.config['wecom']['webhook'] == 'https://example.invalid'
    assert again.snapshot()['history'] == []


def test_strategy_versions_snapshot_and_rollback(tmp_path):
    versions = StrategyVersions(str(tmp_path / 'versions'))
    strategy = tmp_path / 'strategy.py'
    strategy.write_text('VALUE = 1\n', encoding='utf-8')
    first = versions.snapshot(str(strategy), note='v1')
    assert os.path.isfile(first['path'])
    assert versions.items(str(strategy))[0]['version'] == first['version']
    strategy.write_text('VALUE = 2\n', encoding='utf-8')
    second = versions.snapshot(str(strategy), note='v2')
    assert second['version'] != first['version']
    result = versions.rollback(str(strategy), first['version'])
    assert result['ok'] is True
    assert 'VALUE = 1' in strategy.read_text(encoding='utf-8')
    assert result['backup'] is not None
    # 没有版本时给明确错误
    fresh = tmp_path / 'fresh.py'
    fresh.write_text('X = 1\n', encoding='utf-8')
    with pytest.raises(ValueError):
        versions.rollback(str(fresh))


def test_ops_service_snapshot_and_tasks(tmp_path):
    desk = FakeDesk()
    service = OpsService(desk, root=str(tmp_path / 'ops'))
    snapshot = service.snapshot()
    assert snapshot['type'] == 'ops'
    assert snapshot['tokens'] == []
    assert {item['name'] for item in snapshot['tasks']['tasks']} >= {
        'heartbeat', 'reconcile'}
    service.tasks.add('hb', 1, 'heartbeat')
    service.tasks._tasks['hb']['next_run'] = 0           # noqa: SLF001
    results = service.run_tasks()
    assert any(item['name'] == 'hb' and item['ok'] for item in results)
    record = service.notify('hi', 'test')
    assert record['results']


def test_headless_parser_defaults():
    parser = headless.build_parser()
    args = parser.parse_args(['--port', '9999', '--offline',
                              '--token-name', 'ci'])
    assert args.port == 9999
    assert args.offline is True
    assert args.token_name == 'ci'
    assert args.host == '127.0.0.1'
