"""加载指标 / 策略时的**后台计算**（界面不卡 ✓）

用户 2026-10-30 实盘反馈：加 `KalmanFilterStrategy`（Python 循环几秒~几十秒）
时整个界面卡住 → 要求「先有 K 线数据，计算放后台，算完再上图」。

* 实时图表「加到图表」：`_prepare_realtime_strategy()` 先推布局 / K 线 →
  `run_overlay()` 放后台线程 → 结果由 `_drain_strategy_results()` 在主线程应用；
* 格 2..N 的完整库指标（TradingView / TA-Lib…）：内置/个人先推，完整库后台算；
* 后台任务期间 `tick()` **不碰 tqsdk**（tqsdk 不是线程安全的 ✓）。
"""
import json
import pathlib
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, local_data, personal, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(local_data, 'STATE_FILE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(local_data, 'FOLDERS_FILE',
                        str(tmp_path / 'folders.json'))
    monkeypatch.setattr(personal, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(personal, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    folder = tmp_path / 'personal' / 'strategies'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'slow.py'
    path.write_text('\n'.join([
        'import time',
        'from minibt import Strategy',
        '',
        'class slow(Strategy):',
        '    def __init__(self):',
        "        self.kline = self.get_kline('SHFE.ag2612')",
        '        time.sleep(0.6)          # 模拟很重的 __init__ ✓',
        "        self.line = self.kline.close.sma(5, overlap=True)",
        '',
        '    def next(self):',
        '        pass',
    ]), encoding='utf-8')
    personal.add_directory(str(folder), kind='strategy')

    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.log_to_stdout = False
    desk.log_to_ui = False
    # 假行情源没有天勤报价 → 跳过「合约是否可交易」的校验 ✓
    desk._validate_realtime_contracts = lambda names: []
    return desk, str(path)


def _patches(desk):
    out = []
    for script in desk.sent:
        text = str(script)
        if text.startswith('window.__desk.applyPatch('):
            out.append(json.loads(text[len('window.__desk.applyPatch('):-2]))
    return out


class _Feed:
    kind = 'futures'
    api = None

    def __init__(self, frame):
        self.frame = frame

    def available(self):
        return True

    def quotes(self, keys):
        return []

    def spec(self, symbol):
        return None

    def klines(self, symbol, cycle, length=500):
        return self.frame


def _frame(np, pd, rows=200):
    close = 100 + np.sin(np.arange(rows) / 9) * 3
    return pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                     for i in range(rows)],
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': np.ones(rows), 'symbol': 'X', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })


# ------------------------------------------------ 实时图表策略：后台计算
def test_realtime_strategy_computes_in_background(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    desk, path = _desk(tmp_path, monkeypatch)
    desk.futures = _Feed(_frame(np, pd))
    desk.feeds = [desk.futures]
    desk.offline = False
    tab = 'SHFE.ag2612'
    desk.tabs[tab] = {'cycle': 60, 'indicators': [], 'feed': desk.futures}

    started = time.monotonic()
    desk._on_editor_add_indicator({'path': path, 'symbol': tab, 'cell': 0})
    cost = time.monotonic() - started

    # ★ 立刻返回（不再等策略算完）——界面不卡 ✓
    assert cost < 0.5, cost
    assert desk._heavy_jobs == 1
    assert not (desk.tabs[tab].get('strategy') or {}).get('name')
    # K 线 / 布局已经先推给前端了（先有数据 ✓）
    assert any(item['type'] == 'kline' for item in _patches(desk))

    # 等后台算完 → 主线程应用
    assert desk.wait_strategy_results(30)
    assert desk.tabs[tab]['strategy']['name'] == 'slow'
    assert desk.tabs[tab]['strategy_items']
    assert desk._heavy_jobs == 0
    assert any(item['type'] == 'indicator' and item.get('strategy')
               for item in _patches(desk))


def test_second_strategy_cancels_previous_result(tmp_path, monkeypatch):
    """算的过程中又加了别的策略 → 旧结果作废 ✓"""
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    desk, path = _desk(tmp_path, monkeypatch)
    desk.futures = _Feed(_frame(np, pd))
    desk.feeds = [desk.futures]
    desk.offline = False
    tab = 'SHFE.ag2612'
    desk.tabs[tab] = {'cycle': 60, 'indicators': [], 'feed': desk.futures}

    desk._on_editor_add_indicator({'path': path, 'symbol': tab, 'cell': 0})
    job = desk.tabs[tab]['_strat_job']
    desk.tabs[tab]['_strat_job'] = int(job) + 1     # 模拟「又点了一次」
    assert desk.wait_strategy_results(30)
    # 旧 job 的结果被丢掉 → 图上没有策略 ✓
    assert not (desk.tabs[tab].get('strategy') or {}).get('name')


# ------------------------------------------------ 格 2..N 的完整库指标后台算
def test_cell_custom_indicator_is_deferred(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    desk, _path = _desk(tmp_path, monkeypatch)
    desk.futures = _Feed(_frame(np, pd))
    desk.feeds = [desk.futures]
    desk.offline = False
    tab = 'SHFE.ag2612'
    desk.tabs[tab] = {
        'cycle': 60, 'feed': desk.futures, 'indicators': [],
        'layout': {'cols': 2, 'rows': 1,
                   'symbols': [tab, 'SHFE.au2612'],
                   'cells': [{'symbol': tab, 'indicators': []},
                             {'symbol': 'SHFE.au2612', 'indicators': []}]},
    }

    started = time.monotonic()
    desk._on_add_indicator({'symbol': 'SHFE.au2612', 'key': 'talib_SMA',
                            'cell': 1})
    assert time.monotonic() - started < 0.5        # 不在主线程里算 ✓
    first = [item for item in _patches(desk) if item['type'] == 'indicator']
    assert first and first[-1].get('pending') is True
    assert not [item for item in first[-1]['items']
                if str(item['key']).startswith('talib_')]

    # 后台算完 → 再推一份（pending=False + 带 talib_SMA 的线 ✓）
    deadline = time.monotonic() + 30
    merged = []
    while time.monotonic() < deadline:
        desk.flush_outbox()
        merged = [item for item in _patches(desk)
                  if item['type'] == 'indicator'
                  and item.get('pending') is False
                  and any(str(line['key']).startswith('talib_SMA')
                          for line in item.get('items') or [])]
        if merged:
            break
        time.sleep(0.05)
    assert merged, '完整库指标没有后台补推'
    assert merged[-1]['cell'] == 1
    assert merged[-1]['symbol'] == tab
