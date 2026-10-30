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


def test_live_runner_auth_is_tqsdk_tqauth(monkeypatch):
    """子进程的 `auth` 必须是 `tqsdk.TqAuth`（不能是 minibt 的 `tq_auth`）✓

    2026-10-28 用户实测：`TqApi(target, auth=minibt.tq_auth(...))` → tqsdk 只认
    `TqAuth` / `"u,p"` 字符串，其它对象会被当成没传 → `_auth=None` →
    「请输入 auth（快期账户）参数」（快期模拟 TqKq 也要 auth ✗）。
    """
    from tqsdk import TqAuth

    from minibt.desk.live_runner import _auth

    auth = _auth('user@example.com', 'pwd')
    assert isinstance(auth, TqAuth)
    assert auth._user_name == 'user@example.com'
    assert auth._password == 'pwd'
    # 账号 / 密码缺失 → None（子进程给一句人话提示后 exit 6 ✓）
    assert _auth('', '') is None
    assert _auth('user', '') is None
    # env 兜底（父进程通过 env 传 ✓）
    monkeypatch.setenv('MINIBT_TQ_USER', 'env-user')
    monkeypatch.setenv('MINIBT_TQ_PASSWORD', 'env-pwd')
    assert isinstance(_auth('', ''), TqAuth)


def test_strategy_live_needs_tq_auth(tmp_path, monkeypatch):
    """没登录快期账号 → 启动前就说清楚（快期模拟也要 auth，不是只有实盘 ✓）"""
    from minibt.desk import user_prefs as up
    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(up, 'login', lambda: {'futures': {}})
    monkeypatch.delenv('MINIBT_TQ_USER', raising=False)
    monkeypatch.delenv('MINIBT_TQ_PASSWORD', raising=False)
    path = tmp_path / 's.py'
    path.write_text('from minibt import *\n', encoding='utf-8')
    desk = SimpleNamespace(trading=True, push_log=lambda *a, **k: None,
                           account_view=None)
    live = StrategyLive(desk, str(path))

    status = live.start()

    assert status['running'] is False
    assert '快期' in status['error'] and 'auth' in status['error']
    assert not live.running
