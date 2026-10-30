"""P65：回放长度跟随图表 / 策略引擎改为 minibt 自带（不依赖 miniqt）✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(path):
    return (ROOT / path).read_text(encoding='utf-8')


# ------------------------------------------------------- ① 回放总长度
def test_replay_length_follows_chart_history(tmp_path, monkeypatch):
    """回放总根数以前写死 300 → 现在跟随「图表历史长度」✓"""
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    up.set_setting('chart_data_length', 1000)
    up.set_setting('chart_history', 1000)

    last = 1_700_500_000

    class Feed:
        kind = 'futures'
        api = None

        def available(self):
            return True

        def klines(self, symbol, cycle, length=500):
            rows = min(int(length), 5000)
            start = last - (rows - 1) * 60
            close = 100 + np.sin(np.arange(rows) / 9) * 3
            return pd.DataFrame({
                'datetime': [(start + i * 60) * 10 ** 9
                             for i in range(rows)],
                'open': close + 0.4, 'high': close + 2, 'low': close - 2,
                'close': close, 'volume': np.ones(rows),
                'symbol': symbol, 'duration': cycle,
                'price_tick': 1.0, 'volume_multiple': 10,
            })

        def quotes(self, keys):
            return []

        def spec(self, symbol):
            return None

    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.futures = Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk.tabs['SHFE.demo01'] = {'feed': desk.futures, 'cycle': 60,
                               'indicators': []}
    desk._on_replay({'symbol': 'SHFE.demo01', 'cycle': 60,
                     'seek': 0.3, 'speed': 5})
    import json
    payload = None
    for row in desk.sent:
        if '"type":"replay"' in row:
            payload = json.loads(row[len('window.__desk.applyPatch('):-2])
    assert payload is not None
    assert len(payload['bars']) == desk.candles_length() == 1000
    assert payload['seek'] == 0.3


# ------------------------------------------------------- ② 策略引擎（自带）
def test_strategy_runner_is_local():
    """不再 import miniqt（用户要求：装 minibt 就能跑 ✓）"""
    overlay = _read('minibt/desk/strategy_overlay.py')
    runner = _read('minibt/desk/strategy_runner.py')
    assert 'from miniqt' not in overlay
    assert 'from miniqt' not in runner
    assert 'import miniqt' not in overlay + runner
    assert 'from . import strategy_runner as _runner' in overlay
    # 关键步骤都搬过来了 ✓
    for key in ('def prepare(', 'def advance(', 'def specs(', 'def signals(',
                '_inplace_values()', '_strategy_init()', 'strategy.step()',
                '_refresh_klinesetting(', '_safe_btindex('):
        assert key in runner, key
    assert 'extract_minibt_indicators' in runner
    assert 'extract_minibt_signals' in runner


def test_local_runner_runs_a_strategy(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))

    rows = 200
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 10 ** 9 for i in range(rows)],
        'open': 100 + np.arange(rows, dtype=float),
        'high': 102 + np.arange(rows, dtype=float),
        'low': 99 + np.arange(rows, dtype=float),
        'close': 101 + np.sin(np.arange(rows) / 7) * 3
                 + np.arange(rows) * 0.02,
        'volume': np.ones(rows) * 10, 'symbol': 'SHFE.demo01',
        'duration': 60, 'price_tick': 1.0, 'volume_multiple': 10,
    })
    made = pi.create_file('strategy', 'st_local')
    module = pi._import_file(made['path'])
    from minibt.desk import strategy_overlay as overlay

    found = overlay.classes_of(module)
    assert [c.__name__ for c in found['strategy']] == ['st_local']
    result = overlay.run_overlay(frame, found['strategy'][0],
                                 'SHFE.demo01', 60)
    assert result['ok'], result.get('error')
    assert result['items']
    assert all(item['key'].startswith('editor:') for item in result['items'])
