"""P61：退出时优雅关闭 tqsdk / futu（不再刷 pending 任务）✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class _FakeApi:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


# ------------------------------------------------------- Feed.close
def test_feed_close_calls_api_close_once():
    from minibt.desk.feeds import BaseFeed

    api = _FakeApi()
    feed = BaseFeed(api, 'futures')
    feed.close()
    assert api.closed == 1
    assert feed.api is None          # 再关也不会重复 ✓
    feed.close()
    assert api.closed == 1


# ------------------------------------------------------- Desk.close
def test_desk_close_closes_every_feed_and_is_idempotent():
    from minibt.desk.app import Desk
    from minibt.desk.feeds import BaseFeed

    desk = Desk(offline=True)
    api_a, api_b = _FakeApi(), _FakeApi()
    desk.feeds = [BaseFeed(api_a, 'futures'), BaseFeed(api_b, 'stocks')]
    desk.close()
    assert (api_a.closed, api_b.closed) == (1, 1)
    desk.close()                      # 幂等 ✓
    assert (api_a.closed, api_b.closed) == (1, 1)
    # 关掉之后 tick 直接返回（不会再订阅 K 线 ✓）
    desk.tick()


def test_desk_run_closes_feeds_in_browser_shell(monkeypatch):
    from minibt.desk import web

    calls = []

    def fake_serve(desk, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(web, 'serve', fake_serve)

    from minibt.desk.app import Desk
    from minibt.desk.feeds import BaseFeed

    desk = Desk(offline=True, browser=True)
    api = _FakeApi()
    desk.feeds = [BaseFeed(api, 'futures')]
    desk.run()
    assert calls and 'open_browser' in calls[0]
    assert api.closed == 1             # 退出前关掉 tqsdk ✓


def test_cli_closes_desk_in_finally():
    cli = _read('minibt/cli.py')
    body = cli.split("desk.run(as_json=bool(getattr(args, 'json', False)))", 1)[1]
    assert 'finally:' in body[:200]
    assert 'close()' in body[:400]


def test_no_pending_task_noise_in_source():
    """退出路径必须有 close（`Task was destroyed` 噪音的根因 ✗）"""
    app = _read('minibt/desk/app.py')
    assert 'def close(self) -> None:' in app
    assert 'self.close()          # 关 tqsdk / futu 的 api' in app
    assert 'if getattr(self, \'_closed\', False):\n            return' in app
    feeds = _read('minibt/desk/feeds.py')
    assert 'def close(self) -> None:' in feeds
    assert "closer = getattr(api, 'close', None)" in feeds
