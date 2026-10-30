"""P2b 测试：7 个常用指标（计算 + 菜单 + 增减）。"""

import json

import numpy as np
import pytest

from minibt.desk import indicators as ind
from minibt.desk import protocol

pd = pytest.importorskip('pandas')


def _frame(rows: int = 120):
    rng = np.random.default_rng(7)
    close = 3600 + np.cumsum(rng.normal(0, 5, rows))
    return pd.DataFrame({
        'datetime': [(1_700_000_000 + index * 60) * 1_000_000_000
                     for index in range(rows)],
        'open': close - 1, 'high': close + 5, 'low': close - 5,
        'close': close, 'volume': rng.integers(10, 100, rows),
    })


class _Feed:
    kind = 'futures'

    def __init__(self, frame=None):
        self.frame = frame if frame is not None else _frame()
        self.api = None

    def available(self):
        return True

    def contracts(self, ins_class, exchange):
        return ['SHFE.rb2610']

    def fill_names(self, symbols):
        return None

    def name_of(self, symbol):
        return '螺纹'

    def quotes(self, keys):
        return []

    def spec(self, symbol):
        return None

    def klines(self, symbol, cycle, length=500):
        return self.frame


def _desk(tmp_path, frame=None):
    from minibt.desk.app import Desk

    desk = Desk(offline=True, allow_trading=False)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = _Feed(frame)
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    desk.tabs['SHFE.rb2610'] = {'feed': desk.futures, 'cycle': 60}
    return desk


def _payload(script):
    return json.loads(script[len('window.__desk.applyPatch('):-2])


# ------------------------------------------------------------------ 计算
def test_catalog_has_seven_common_indicators():
    keys = [item['key'] for item in ind.CATALOG]
    assert keys == ['MA', 'EMA', 'BOLL', 'MACD', 'KDJ', 'RSI']
    for item in ind.CATALOG:
        assert 'label' in item and isinstance(item['params'], list)
        assert item['overlay'] in (True, False)


@pytest.mark.parametrize('key,lines,overlay', [
    ('MA', 1, True), ('EMA', 1, True), ('BOLL', 3, True),
    ('MACD', 3, False), ('KDJ', 3, False), ('RSI', 1, False),
])
def test_compute_each_indicator(key, lines, overlay):
    payload = ind.compute('SHFE.rb2610', _frame(), [{'key': key}])
    items = payload['items']
    assert payload['type'] == 'indicator'
    assert len(items) == lines
    for item in items:
        assert item['overlay'] is overlay
        assert item['data'], f'{key} 没有数据'
        assert len(item['data'][0]) == 2
        assert isinstance(item['data'][0][0], int)      # unix 秒 ✓
        if not overlay:
            assert item['pane'] == key


def test_compute_handles_empty_and_unknown():
    assert ind.compute('X', None, [{'key': 'MA'}])['items'] == []
    assert ind.compute('X', _frame(), [{'key': 'NOPE'}])['items'] == []


def test_compute_respects_params():
    short = ind.compute('X', _frame(), [{'key': 'MA',
                                         'params': {'length': 5}}])
    long = ind.compute('X', _frame(), [{'key': 'MA',
                                        'params': {'length': 30}}])
    assert short['items'][0]['label'] == 'MA5'
    assert long['items'][0]['label'] == 'MA30'
    # 周期越长，NaN 越多（点数越少）✓
    assert len(short['items'][0]['data']) > len(long['items'][0]['data'])


# -------------------------------------------------------------- 菜单 / 增减
def test_indicator_menu_command(tmp_path):
    desk = _desk(tmp_path)
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'indicator_menu', 'payload': {'symbol': 'SHFE.rb2610'}}))
    patch = _payload(desk.sent[-1])
    assert patch['type'] == 'indicator_menu'
    keys = [item['key'] for item in patch['items']]
    # 常用 6 个在最前面，后面是完整指标库（P6：459 个）✓
    assert keys[:6] == ['MA', 'EMA', 'BOLL', 'MACD', 'KDJ', 'RSI']
    assert len(keys) > 300
    assert {'group': '常用'} in [{k: item.get(k) for k in ('group',)}
                                for item in patch['items'][:1]]


def test_add_and_remove_indicator(tmp_path):
    desk = _desk(tmp_path)
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'add_indicator',
        'payload': {'symbol': 'SHFE.rb2610', 'key': 'MACD'}}))
    patch = _payload(desk.sent[-1])
    assert patch['type'] == 'indicator'
    assert len(patch['items']) == 3 and patch['items'][0]['pane'] == 'MACD'
    assert [item['key'] for item in desk.tabs['SHFE.rb2610']['indicators']] == [
        'MACD']

    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'remove_indicator',
        'payload': {'symbol': 'SHFE.rb2610', 'key': '*'}}))
    assert _payload(desk.sent[-1])['items'] == []
    assert desk.tabs['SHFE.rb2610']['indicators'] == []


def test_open_chart_includes_indicators(tmp_path):
    desk = _desk(tmp_path)
    desk.tabs['SHFE.rb2610']['indicators'] = [{'key': 'MA', 'params': {}}]
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'open_chart', 'payload': {'symbol': 'SHFE.rb2610'}}))
    kinds = [_payload(script)['type'] for script in desk.sent]
    assert 'indicator' in kinds
    indicator = next(_payload(script) for script in desk.sent
                     if _payload(script)['type'] == 'indicator')
    assert indicator['items'][0]['label'] == 'MA20'


def test_indicator_refresh_throttles(tmp_path):
    desk = _desk(tmp_path)
    info = desk.tabs['SHFE.rb2610']
    info['indicators'] = [{'key': 'MA', 'params': {}}]
    bars = [{'time': 1_700_000_000, 'open': 1, 'high': 2, 'low': 0.5,
             'close': 1.5, 'volume': 10}]
    desk.sent.clear()
    desk._refresh_indicators('SHFE.rb2610', info, bars)
    desk._refresh_indicators('SHFE.rb2610', info, bars)   # 同一根 + 1 秒内 → 跳过
    kinds = [_payload(script)['type'] for script in desk.sent]
    assert kinds.count('indicator') == 1


def test_p2b_assets_built():
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[1]
    script = (repo / 'pylightcharts' / 'js' / 'desk.js').read_text(
        encoding='utf-8', errors='ignore')
    # P35：副图改成原生 pane（不再有 desk-ind-pane 小图 ✓）
    for key in ('indicator_menu', 'add_indicator', 'remove_indicator',
                'addPane'):
        assert key in script, key
    css = (repo / 'pylightcharts' / 'js' / 'desk.css').read_text(encoding='utf-8')
    assert 'desk-chart-main' in css and 'desk-pos-badge' in css
    assert (repo / 'jslib' / 'src' / 'desk' / 'indicator.ts').is_file()


def test_indicator_payload_reuses_passed_frame(tmp_path):
    desk = _desk(tmp_path)
    frame = _frame(30)
    desk.tabs['SHFE.rb2610']['indicators'] = [{'key': 'MA', 'params': {}}]

    def boom(*args, **kwargs):
        raise AssertionError('不应该再拉一次 K 线')

    desk.futures.klines = boom
    payload = desk.indicator_payload('SHFE.rb2610', frame=frame)
    assert payload['items']


def test_same_bar_indicator_updates_only_last_point(tmp_path):
    desk = _desk(tmp_path)
    frame = _frame(120)
    info = desk.tabs['SHFE.rb2610']
    info['indicators'] = [{'key': 'MA', 'params': {}}]
    desk.sent.clear()
    full = desk.indicator_payload('SHFE.rb2610', frame=frame)
    full_last = full['items'][0]['data'][-1]
    assert full_last is not None

    frame = frame.copy()
    frame.loc[frame.index[-1], 'close'] = float(frame['close'].iloc[-1]) + 1
    info['_ind_at'] = 0
    bars = [{'time': int(frame['datetime'].iloc[-1]) // 1_000_000_000,
             'close': float(frame['close'].iloc[-1])}]
    desk._refresh_indicators('SHFE.rb2610', info, bars, frame)
    last = _payload(desk.sent[-1])
    assert last['type'] == 'indicator'
    assert last['mode'] == 'last'
    assert len(last['items']) == 1
    assert len(last['items'][0]['data']) == 1
    assert last['items'][0]['data'][0][0] == full_last[0]


def test_indicator_interval_settings_are_clamped(tmp_path):
    desk = _desk(tmp_path)
    from minibt.desk import user_prefs as up

    original = up.settings
    try:
        up.settings = lambda: {
            'indicator_refresh_interval_ms': 5,
            'indicator_custom_new_bar': False,
        }
        assert desk._indicator_intervals() == (10, False)
    finally:
        up.settings = original


def test_chart_reset_only_resets_chart_config(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    up.set_setting('chart_font_size', 20)
    for key in ('indicator_refresh_interval_ms',
                'indicator_custom_new_bar'):
        up.set_setting(key, 3000 if key.endswith('_ms') else True)
    up.set_setting('sim_initial_cash', 123456)
    up.set_setting('theme_accent', '#123456')
    values = up.reset_chart_settings()
    assert 'chart_font_size' not in values
    for key in ('indicator_refresh_interval_ms',
                'indicator_custom_new_bar'):
        assert key not in values
    assert values['sim_initial_cash'] == 123456
    assert values['theme_accent'] == '#123456'


def test_new_bar_indicator_updates_at_least_tail_two(tmp_path):
    desk = _desk(tmp_path)
    frame = _frame(120)
    info = desk.tabs['SHFE.rb2610']
    info['indicators'] = [{'key': 'MA', 'params': {}}]
    desk.sent.clear()
    desk.indicator_payload('SHFE.rb2610', frame=frame)

    # 追加一根新 K 线 → 至少更新「上一根 + 新一根」
    last = frame.iloc[-1].copy()
    last['datetime'] = int(frame['datetime'].iloc[-1]) + 60 * 1_000_000_000
    last['close'] = float(last['close']) + 1
    frame = pd.concat([frame, last.to_frame().T], ignore_index=True)
    bars = [{'time': int(frame['datetime'].iloc[-2]) // 1_000_000_000,
             'close': float(frame['close'].iloc[-2])},
            {'time': int(frame['datetime'].iloc[-1]) // 1_000_000_000,
             'close': float(frame['close'].iloc[-1])}]
    info['_ind_at'] = 0
    desk._refresh_indicators('SHFE.rb2610', info, bars, frame)
    payload = _payload(desk.sent[-1])
    assert payload['mode'] == 'last'
    assert len(payload['items'][0]['data']) >= 2


def test_reconnect_indicator_increment_fills_by_bar_time(tmp_path):
    desk = _desk(tmp_path)
    frame = _frame(120)
    info = desk.tabs['SHFE.rb2610']
    info['indicators'] = [{'key': 'MA', 'params': {}}]
    desk.indicator_payload('SHFE.rb2610', frame=frame)

    # 模拟断线 3 根：按 60 秒周期推算应补最后 4 根（重叠旧末根 + 3 新根）
    rows = []
    for step in range(1, 4):
        row = frame.iloc[-1].copy()
        row['datetime'] = int(frame['datetime'].iloc[-1]) + (
            step * 60 * 1_000_000_000)
        row['close'] = float(row['close']) + step
        rows.append(row)
    frame = pd.concat([frame, pd.DataFrame(rows)], ignore_index=True)
    info['_ind_at'] = 0
    desk._refresh_indicators(
        'SHFE.rb2610', info,
        [{'time': int(frame['datetime'].iloc[-1]) // 1_000_000_000,
          'close': float(frame['close'].iloc[-1])}], frame)
    payload = _payload(desk.sent[-1])
    assert payload['mode'] == 'last'
    assert len(payload['items'][0]['data']) == 4
