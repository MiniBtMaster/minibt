"""多布局：格 2..N 的指标 / K 线增量 + 收盘后不空转 ✓

用户 2026-10-30 实盘反馈：

1. 横排 3 图、前 2 格加载策略后，在**格 3** 加第一个收藏指标（sma）**不显示**，
   再加 adx 时两个一起出现 ✗
   —— 根因：格 3 的合约当时还是天勤的**占位 K 线**（datetime=0 / 全 NaN），
   算出来的指标数据是空的；而且格 2..N 的指标**从来没有增量刷新**，
   所以不重新加一次就永远不显示 ✗
2. 收盘后日志还在刷 `[性能] 看盘 tab 耗时 0.4xs` —— 数据没变还在重算 ✗
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, local_data, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(local_data, 'STATE_FILE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(local_data, 'FOLDERS_FILE',
                        str(tmp_path / 'folders.json'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.log_to_stdout = False
    desk.log_to_ui = False
    return desk


def _patches(desk):
    out = []
    for script in desk.sent:
        text = str(script)
        if text.startswith('window.__desk.applyPatch('):
            out.append(json.loads(text[len('window.__desk.applyPatch('):-2]))
    return out


def _frame(np, pd, rows=120, last=None, close=None):
    import time as _time
    start = int(_time.time()) - rows * 60      # 默认是「刚刚」的行情 ✓
    close = close if close is not None else (
        100 + np.sin(np.arange(rows) / 9) * 3)
    return pd.DataFrame({
        'datetime': [(start + i * 60) * 10 ** 9 for i in range(rows)],
        'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
        'volume': np.ones(rows), 'symbol': 'X', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })


class _Feed:
    kind = 'futures'
    api = None

    def __init__(self, frame=None):
        self.frame = frame
        self.calls = 0

    def available(self):
        return True

    def quotes(self, keys):
        return []

    def spec(self, symbol):
        return None

    def klines(self, symbol, cycle, length=500):
        self.calls += 1
        return self.frame


def _two_cell(desk, cell_indicators):
    tab = 'SHFE.ag2612'
    feed = desk.feeds[0] if desk.feeds else None
    desk.tabs[tab] = {
        'cycle': 60, 'feed': feed,
        'indicators': [],
        'layout': {'cols': 2, 'rows': 1,
                   'symbols': [tab, 'SHFE.au2612'],
                   'cells': [{'symbol': tab, 'indicators': []},
                             {'symbol': 'SHFE.au2612',
                              'indicators': list(cell_indicators)}]},
    }
    return tab


# ------------------------------------------------ 格 2..N 的 K 线 / 指标增量
def test_cell_bars_and_indicators_update_only_when_data_changes(
        tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    desk = _desk(tmp_path, monkeypatch)
    feed = _Feed(_frame(np, pd))
    desk.futures = feed
    desk.feeds = [feed]
    desk.offline = False
    tab = _two_cell(desk, [{'key': 'MA', 'params': {}}])
    info = desk.tabs[tab]
    info['layout']['symbols'] = [tab, 'SHFE.au2612']

    desk._push_cell_bars(tab, info)
    first = _patches(desk)
    assert any(item['type'] == 'kline' and item.get('cell') == 1
               for item in first), '第一次要推格 2 的 K 线 ✓'
    assert any(item['type'] == 'indicator' and item.get('cell') == 1
               and item.get('items') for item in first), \
        '格 2 自己的指标也要推（以前从不刷新 ✗）'

    # 数据没变 → 什么都不推（收盘后不空转 ✓）
    desk.sent.clear()
    desk._push_cell_bars(tab, info)
    assert not [item for item in _patches(desk)
                if item['type'] in ('kline', 'indicator')]

    # close 变了 → 推增量 K 线 + 重算指标（节流：把上次时间调老 ✓）
    close = np.array(_frame(np, pd)['close'], dtype=float)
    close[-1] += 1.5
    feed.frame = _frame(np, pd, close=close)
    info['_cell_ind_at'] = {1: 0.0}
    desk.sent.clear()
    desk._push_cell_bars(tab, info)
    again = _patches(desk)
    assert any(item['type'] == 'kline' and item.get('cell') == 1
               for item in again)
    assert any(item['type'] == 'indicator' and item.get('cell') == 1
               for item in again)


def test_cell_placeholder_data_pushes_nothing(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    desk = _desk(tmp_path, monkeypatch)
    placeholder = _frame(np, pd)
    placeholder['datetime'] = [0] * len(placeholder)
    feed = _Feed(placeholder)
    desk.futures = feed
    desk.feeds = [feed]
    desk.offline = False
    tab = _two_cell(desk, [{'key': 'MA', 'params': {}}])

    desk._push_cell_bars(tab, desk.tabs[tab])
    assert not [item for item in _patches(desk)
                if item['type'] in ('kline', 'indicator')]


# --------------------------------------- 加第一个指标时数据没准备好 → 等一拍
def test_add_indicator_waits_for_cell_data(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    desk = _desk(tmp_path, monkeypatch)
    placeholder = _frame(np, pd)
    placeholder['datetime'] = [0] * len(placeholder)
    feed = _Feed(placeholder)
    desk.futures = feed
    desk.feeds = [feed]
    desk.offline = False
    tab = _two_cell(desk, [])

    desk.sent.clear()
    desk._on_add_indicator({'symbol': 'SHFE.au2612', 'key': 'MA', 'cell': 1})

    # 指标**登记**了，但**不推空补丁**（推了会把原有线清掉 ✗）
    assert [item['key'] for item in
            desk.tabs[tab]['layout']['cells'][1]['indicators']] == ['MA']
    assert not [item for item in _patches(desk)
                if item['type'] == 'indicator']

    # 数据到了 → 节拍器自动补推（用户不用再加一次 ✓）
    feed.frame = _frame(np, pd)
    desk.sent.clear()
    desk._push_cell_bars(tab, desk.tabs[tab])
    pushed = [item for item in _patches(desk)
              if item['type'] == 'indicator' and item.get('cell') == 1]
    assert pushed and pushed[-1]['items']


# ------------------------------------------------------- 收盘后不再重算策略
def test_strategy_skips_when_bar_unchanged(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    desk = _desk(tmp_path, monkeypatch)
    calls = []

    class Runner:
        strategy = object()

        def advance(self, frames=None):
            calls.append(1)
            return True

        def update_symbols(self):
            return []

    tab = _two_cell(desk, [])
    info = desk.tabs[tab]
    info['strategy'] = {'name': 'S', 'path': '/tmp/s.py'}
    info['strategy_items'] = [{'key': 'editor:S:line:0'}]
    info['strategy_runner'] = Runner()
    frame = _frame(np, pd)

    desk._update_strategy_items(tab, info, frame, main_symbol=tab)
    assert len(calls) == 1                  # 第一次算 ✓
    # 同一根再说一次 → 不算（收盘后不空转 ✓）
    info['_strat_at'] = 0.0
    desk._update_strategy_items(tab, info, frame, main_symbol=tab)
    assert len(calls) == 1
    # close 变了 → 再算 ✓
    close = np.array(frame['close'], dtype=float)
    close[-1] += 2
    info['_strat_at'] = 0.0
    desk._update_strategy_items(tab, info, _frame(np, pd, close=close),
                                main_symbol=tab)
    assert len(calls) == 2


def test_strategy_suspends_when_market_idle(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    desk = _desk(tmp_path, monkeypatch)
    calls = []

    class Runner:
        strategy = object()

        def advance(self, frames=None):
            calls.append(1)
            return True

        def update_symbols(self):
            return []

    tab = _two_cell(desk, [])
    info = desk.tabs[tab]
    info['strategy'] = {'name': 'S'}
    info['strategy_runner'] = Runner()
    old = _frame(np, pd)
    # 把最后一根挪到 3 小时前（收盘了 ✓）
    stamps = np.array(old['datetime'], dtype='int64')
    old['datetime'] = (stamps - 4 * 3600 * 10 ** 9).tolist()
    desk.sent.clear()
    desk._update_strategy_items(tab, info, old, main_symbol=tab)
    assert not calls                        # 直接挂起 ✓
