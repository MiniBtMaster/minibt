"""策略实盘启动安全：allow_trading / 二次确认 / 关窗停止 ✓"""
from __future__ import annotations

import pathlib
from types import SimpleNamespace

from minibt.desk.app import Desk
from minibt.desk.strategy_live import StrategyLive


def _desk(trading: bool = True) -> Desk:
    desk = Desk(offline=True, allow_trading=trading)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    return desk


def test_strategy_live_start_blocked_when_trading_disabled(tmp_path):
    path = tmp_path / 's.py'
    path.write_text('from minibt import *\n', encoding='utf-8')
    desk = _desk(trading=False)

    desk._on_strategy_live_start({'file': str(path), 'confirm': True})

    assert getattr(desk, '_strategy_live', None) is None
    assert any('禁止交易' in str(item) for item in desk.sent)


def test_strategy_live_start_requires_confirm(tmp_path):
    path = tmp_path / 's.py'
    path.write_text('from minibt import *\n', encoding='utf-8')
    desk = _desk(trading=True)

    desk._on_strategy_live_start({'file': str(path)})   # 没有 confirm

    assert getattr(desk, '_strategy_live', None) is None
    assert any('未确认' in str(item) for item in desk.sent)


def test_desk_close_stops_live_strategy():
    desk = _desk(trading=True)
    stopped = []

    class FakeLive:
        running = True

        def stop(self):
            stopped.append(True)
            self.running = False
            return {'running': False}

    desk._strategy_live = FakeLive()
    desk.close()

    assert stopped == [True]
    assert getattr(desk, '_strategy_live', None) is None


def test_strategy_live_start_has_global_trading_gate(tmp_path):
    path = tmp_path / 's.py'
    path.write_text('from minibt import *\n', encoding='utf-8')
    desk = SimpleNamespace(trading=False,
                           push_log=lambda *args, **kwargs: None)
    live = StrategyLive(desk, str(path))

    status = live.start()

    assert status['running'] is False
    assert '禁止交易' in status['error']
    assert not live.running


def test_connect_stocks_passes_trade_market_to_pending(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up
    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = _desk(trading=True)
    desk._on_connect_stocks({
        'host': '127.0.0.1', 'port': 11111,
        'trade': True, 'trd_env': 'SIMULATE', 'trd_market': 'CN',
    })
    assert desk._connect_pending == ('stocks', {
        'host': '127.0.0.1', 'port': 11111, 'trade': True,
        'trd_env': 'SIMULATE', 'trd_market': 'CN',
    })
