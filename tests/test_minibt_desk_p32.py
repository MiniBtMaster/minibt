"""P32：后台线程推补丁闪退 + 自定义指标永不显示 ✓"""
import json
import pathlib
import threading
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.delenv('MINIBT_DESK_NO_INDEX', raising=False)
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    return desk


# ------------------------------------------------------------ 线程安全
def test_push_from_thread_goes_to_outbox(tmp_path, monkeypatch):
    """后台线程直接 `runJavaScript` = 硬崩无 traceback（用户实测 ✗）"""
    desk = _desk(tmp_path, monkeypatch)
    thread = threading.Thread(
        target=lambda: desk.push({'type': 'toast', 'text': 'from-thread'}))
    thread.start()
    thread.join()
    assert desk.sent == []                  # 没直接发 ✓
    assert len(desk._outbox) == 1

    desk.flush_outbox()                     # 主线程发（Qt 定时器会调 ✓）
    assert len(desk.sent) == 1
    assert 'from-thread' in desk.sent[0]
    assert desk._outbox == []


def test_push_on_main_thread_sends_immediately(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.push({'type': 'toast', 'text': 'main'})
    assert len(desk.sent) == 1
    assert desk._outbox == []


def test_app_window_starts_outbox_timer():
    window = (ROOT / 'minibt' / 'desk' / 'app_window.py').read_text(encoding='utf-8')
    assert 'flush_outbox' in window
    assert '_start_outbox_timer' in window
    assert 'setInterval(60)' in window


# ------------------------------------------------------------ 指标重算 / 异步
def test_indicator_refresh_only_when_bar_changes(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    info = {'indicators': [{'key': 'MA', 'params': {}}]}
    bars = [{'time': 1700000000, 'close': 1.0}, {'time': 1700000060, 'close': 2.0}]
    pushes = []
    monkeypatch.setattr(desk, 'push', lambda patch: pushes.append(patch))
    monkeypatch.setattr(desk, 'indicator_payload', lambda symbol: {'ok': 1})

    desk._refresh_indicators('SHFE.demo01', info, bars)
    assert len(pushes) == 1
    desk._refresh_indicators('SHFE.demo01', info, bars)   # 同一根 + 1 秒内 → 跳过
    assert len(pushes) == 1

    # 收盘价变了 → 重算 ✓
    info['_ind_at'] = 0
    desk._refresh_indicators('SHFE.demo01', info,
                             bars[:-1] + [{'time': 1700000060, 'close': 2.5}])
    assert len(pushes) == 2


def test_custom_indicator_result_survives_recompute(tmp_path, monkeypatch):
    """以前每秒重算 → `_ind_gen` 变了就把后台算好的结果丢掉 ✗"""
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    desk = _desk(tmp_path, monkeypatch)
    rows = 120
    close = 100 + np.arange(rows, dtype=float)
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close - 1, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': np.ones(rows),
        'symbol': 'SHFE.demo01', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })
    info = {}
    custom = [{'key': 'pta_sma', 'params': {}}]
    deadline = time.time() + 20
    seen = []
    payload = {'type': 'indicator', 'symbol': 'SHFE.demo01', 'items': []}
    desk._compute_custom('SHFE.demo01', info, frame, custom, payload)
    # 模拟「同一根 K 线又算了一次」（签名不变 → 旧结果不能被丢）
    desk._compute_custom('SHFE.demo01', info, frame, custom, payload)
    while time.time() < deadline:
        desk.flush_outbox()        # 主线程发件箱（Qt 定时器干的就是这个 ✓）
        seen = [row for row in desk.sent if '"type":"indicator"' in str(row)]
        if any('pta_sma' in str(row) for row in seen):
            break
        time.sleep(0.05)
    hits = [row for row in seen if 'pta_sma' in str(row)]
    assert hits, '后台算好的指标被丢掉了（用户实测：点指标没反应 ✗）'


def test_custom_indicator_discarded_when_selection_changes(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    desk = _desk(tmp_path, monkeypatch)
    rows = 60
    close = 100 + np.arange(rows, dtype=float)
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close - 1, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': np.ones(rows),
        'symbol': 'SHFE.demo01', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })
    info = {}
    desk._compute_custom('SHFE.demo01', info, frame,
                         [{'key': 'pta_sma', 'params': {}}],
                         {'type': 'indicator', 'symbol': 'SHFE.demo01',
                          'items': []})
    # 立刻换指标 → 旧签名失效（结果应被丢弃 ✓）
    info['_ind_sig'] = 'changed'
    time.sleep(0.6)
    desk.flush_outbox()
    assert not [row for row in desk.sent if 'pta_sma' in str(row)]
