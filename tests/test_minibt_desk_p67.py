"""P67：策略线名 sname / 指标算满长度 / 回放带指标（含策略）✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


# ------------------------------------------------------- ① `lines=` 生效
def test_rolling_mean_honors_lines_kwarg():
    """`.mean(lines=['sma_fast'])` 以前被 pop 掉、写死成 `mean` ✗"""
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt import KLine

    rows = 60
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                     for i in range(rows)],
        'open': 100 + np.arange(rows, dtype=float),
        'high': 102 + np.arange(rows, dtype=float),
        'low': 99 + np.arange(rows, dtype=float),
        'close': 101 + np.arange(rows, dtype=float),
        'volume': np.ones(rows), 'symbol': 'SHFE.demo01', 'duration': 60,
    })
    kline = KLine(frame)
    default = kline.close.rolling(5).mean()
    assert list(default.lines) == ['mean']          # 默认行为不变 ✓
    named = kline.close.rolling(5).mean(lines=['sma_fast'])
    assert list(named.lines) == ['sma_fast']        # 用户命名生效 ✓
    assert named.sname == 'sma_fast'
    single = kline.close.rolling(5).mean(lines='sma_slow')
    assert list(single.lines) == ['sma_slow']


def test_strategy_overlay_uses_line_names(tmp_path, monkeypatch):
    """策略里的 `lines=['sma_fast']` 要显示成 sma_fast ✓"""
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    rows = 200
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                     for i in range(rows)],
        'open': 100 + np.arange(rows, dtype=float),
        'high': 102 + np.arange(rows, dtype=float),
        'low': 99 + np.arange(rows, dtype=float),
        'close': 101 + np.sin(np.arange(rows) / 7) * 3,
        'volume': np.ones(rows), 'symbol': 'SHFE.demo01', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })
    target = tmp_path / 'personal' / 'strategies' / 'named_st.py'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join([
        'from minibt import Strategy',
        '',
        'class named_st(Strategy):',
        '    params = dict(fast=5, slow=20)',
        '    def __init__(self):',
        '        self.kline = self.get_kline()',
        '        close = self.kline.close',
        "        self.fast = close.rolling(int(self.params.fast)).mean(",
        "            lines=['sma_fast'])",
        "        self.slow = close.rolling(int(self.params.slow)).mean(",
        "            lines=['sma_slow'])",
        '        self.fast.overlap = self.slow.overlap = True',
        '',
        '    def next(self):',
        '        pass',
    ]), encoding='utf-8')
    from minibt.desk import strategy_overlay as overlay

    module = pi._import_file(str(target))
    found = overlay.classes_of(module)
    result = overlay.run_overlay(frame, found['strategy'][0],
                                 'SHFE.demo01', 60)
    assert result['ok'], result.get('error')
    names = {item['label'] for item in result['items']}
    assert 'sma_fast' in names and 'sma_slow' in names


# ------------------------------------------------------- ② 指标算满长度
def test_indicator_limit_covers_all_bars():
    app = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    # 内置 / 个人 / 完整库 都按 `len(frame)` 出线；多格走 `limit=limit`
    # （`thrift=True` 时按实际长度，节拍器里每格用 ✓）
    assert app.count('limit=max(600, len(frame)') >= 2
    assert 'limit=max(600, len(snapshot))' in app
    assert 'limit = (max(1, len(frame)) if (thrift' in app


def test_catalog_line_has_all_points(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    rows = 1000
    close = 100 + np.sin(np.arange(rows) / 9) * 3
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                     for i in range(rows)],
        'open': close, 'high': close + 2, 'low': close - 2, 'close': close,
        'volume': np.ones(rows), 'symbol': 'SHFE.demo01', 'duration': 60,
    })
    items = cat.compute(frame, ['talib_SMA'], {}, limit=rows)
    assert items and len(items[0]['data']) > 900   # 不再是 600 ✓


# ------------------------------------------------------- ③ 回放带指标
def test_replay_payload_includes_every_indicator(tmp_path, monkeypatch):
    """回放要带上「策略 + 内置 + 个人 + 完整库」全部线（以前 pending 的没有 ✗）"""
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import indicator_catalog as cat
    from minibt.desk import personal as pi
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))

    last = 1_700_500_000

    class Feed:
        kind = 'futures'
        api = None

        def available(self):
            return True

        def klines(self, symbol, cycle, length=500):
            rows = min(int(length), 3000)
            start = last - (rows - 1) * 60
            close = 100 + np.sin(np.arange(rows) / 9) * 3
            return pd.DataFrame({
                'datetime': [(start + i * 60) * 10 ** 9
                             for i in range(rows)],
                'open': close, 'high': close + 2, 'low': close - 2,
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
    desk._strategy_sync = True
    desk.futures = Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk.tabs['SHFE.demo01'] = {'feed': desk.futures, 'cycle': 60,
                               'indicators': []}
    desk._on_editor_add_indicator(
        {'path': pi.create_file('indicator', 'q_ma')['path']})
    desk._on_editor_add_indicator(
        {'path': pi.create_file('strategy', 'q_st')['path']})
    desk.tabs['SHFE.demo01']['indicators'].append(
        {'key': 'talib_SMA', 'params': {}})     # 完整库（平时异步 ✓）

    frame = desk.futures.klines('SHFE.demo01', 60, 1000)
    items = desk._replay_indicator_items('SHFE.demo01', frame)
    keys = [item['key'] for item in items]
    assert any(key.startswith('editor:') for key in keys)       # 策略 ✓
    assert any(key.startswith('pi:') for key in keys)       # 个人 ✓
    assert any(key.startswith('talib_SMA') for key in keys)  # 完整库 ✓


def test_replay_seek_from_payload():
    page = (ROOT / 'jslib' / 'src' / 'desk' / 'chart-page.ts').read_text(
        encoding='utf-8')
    body = page.split('this.replaySpeed = Number(payload.speed)', 1)[1][:300]
    assert 'this.replaySeek = Number(payload.seek)' in body
