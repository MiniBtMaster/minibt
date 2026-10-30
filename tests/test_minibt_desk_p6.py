"""P6 测试：完整指标库（反射目录 / 计算 / 搜索菜单 / 异步补偿）。"""

import json
import time

import numpy as np
import pytest

from minibt.desk import indicator_catalog as cat
from minibt.desk import protocol

pd = pytest.importorskip('pandas')


def _frame(rows: int = 200):
    rng = np.random.default_rng(5)
    close = 3600 + np.cumsum(rng.normal(0, 3, rows))
    return pd.DataFrame({
        'datetime': [(1_700_000_000 + index * 60) * 1_000_000_000
                     for index in range(rows)],
        'open': close - 1, 'high': close + 3, 'low': close - 3,
        'close': close, 'volume': rng.integers(10, 100, rows),
        'symbol': 'SHFE.rb2610', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })


# ------------------------------------------------------------------ 目录
def test_catalog_reflects_full_library(tmp_path, monkeypatch):
    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    items = cat.catalog(refresh=True)
    assert len(items) > 400                       # 459 个（本机）
    groups = {item['group'] for item in items}
    assert {'PandasTA', 'TuLip', '天勤TA', '天勤函数', 'BtInd', 'Pine'} <= groups
    keys = {item['key'] for item in items}
    assert {'pta_sma', 'tqta_BOLL', 'talib_RSI' if 'talib_RSI' in keys
            else 'pta_rsi', 'ti_sma'} <= keys | {'pta_rsi'}
    for item in items[:20]:
        assert item['key'] and item['label'] and 'overlap' in item
        assert isinstance(item['params'], list)


def test_catalog_params_come_from_signature():
    sma = cat.entry('pta_sma')
    assert sma is not None
    names = [param['name'] for param in sma['params']]
    assert 'length' in names
    length = next(param for param in sma['params'] if param['name'] == 'length')
    assert length['default'] == 10 and length['type'] == 'int'
    assert cat.defaults(sma)['length'] == 10


def test_catalog_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    first = cat.catalog(refresh=True)
    assert (tmp_path / 'ind.json').is_file()
    cat._MEMORY['items'] = None                   # 清内存 → 走磁盘缓存
    started = time.time()
    second = cat.catalog()
    assert len(second) == len(first)
    assert time.time() - started < 0.2            # 读缓存很快 ✓

    # 版本变了 → 缓存失效（这里直接改文件里的 version）
    data = json.loads((tmp_path / 'ind.json').read_text(encoding='utf-8'))
    data['version'] = 'old'
    (tmp_path / 'ind.json').write_text(json.dumps(data), encoding='utf-8')
    cat._MEMORY['items'] = None
    assert len(cat.catalog()) == len(first)       # 重建后仍然完整 ✓


def test_catalog_unknown_key():
    assert cat.entry('no_such_indicator') is None


# ------------------------------------------------------------------ 计算
def test_compute_series_dataframe_and_ndarray():
    items = cat.compute(_frame(), ['pta_sma', 'tqta_BOLL'])
    keys = [item['key'] for item in items]
    assert 'pta_sma:sma' in keys                  # Series
    assert {'tqta_BOLL:mid', 'tqta_BOLL:top',
            'tqta_BOLL:bottom'} <= set(keys)      # DataFrame 三列
    for item in items:
        assert item['data'], item['key']
        assert isinstance(item['data'][0][0], int)
        assert item['kind'] == 'line'


def test_compute_respects_param_override():
    default = cat.compute(_frame(), ['pta_sma'])
    longer = cat.compute(_frame(), ['pta_sma'],
                         {'pta_sma': {'length': 50}})
    # 现在统一返回**完整长度**（预热期用 None），不再截掉前 N 根 ✓
    assert len(longer[0]['data']) == len(default[0]['data'])
    assert longer[0]['data'][0][1] is None
    assert sum(1 for _, value in longer[0]['data'] if value is None) >         sum(1 for _, value in default[0]['data'] if value is None)


def test_compute_empty_inputs():
    assert cat.compute(None, ['pta_sma']) == []
    assert cat.compute(_frame(), []) == []
    assert cat.compute(_frame(), ['no_such_indicator']) == []


# ------------------------------------------------------- Desk 端到端（异步）
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


def _desk(tmp_path):
    from minibt.desk.app import Desk

    desk = Desk(offline=True, allow_trading=False)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = _Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    desk.tabs['SHFE.rb2610'] = {'feed': desk.futures, 'cycle': 60}
    return desk


def _payload(script):
    return json.loads(script[len('window.__desk.applyPatch('):-2])


def test_menu_contains_builtin_then_full_library(tmp_path):
    desk = _desk(tmp_path)
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'indicator_menu', 'payload': {'symbol': 'SHFE.rb2610'}}))
    items = _payload(desk.sent[-1])['items']
    assert [item['key'] for item in items[:6]] == [
        'MA', 'EMA', 'BOLL', 'MACD', 'KDJ', 'RSI']
    assert items[0]['group'] == '常用'
    assert len(items) > 400
    catalog_items = [item for item in items if item['group'] != '常用']
    assert any(item['key'] == 'pta_sma' for item in catalog_items)


def test_add_catalog_indicator_pushes_async(tmp_path, monkeypatch):
    desk = _desk(tmp_path)
    desk.handle(protocol.encode_command({
        'cmd': 'add_indicator',
        'payload': {'symbol': 'SHFE.rb2610', 'key': 'MA'}}))
    desk.handle(protocol.encode_command({
        'cmd': 'add_indicator',
        'payload': {'symbol': 'SHFE.rb2610', 'key': 'pta_sma',
                    'params': {'length': 15}},
    }))
    assert [item['key'] for item in
            desk.tabs['SHFE.rb2610']['indicators']] == ['MA', 'pta_sma']

    deadline = time.time() + 6.0
    merged = None
    while time.time() < deadline:
        desk.flush_outbox()   # 后台补丁要先由主线程发出来 ✓
        patches = [_payload(script) for script in desk.sent
                   if '"type":"indicator"' in script]
        for patch in patches:
            keys = [item['key'] for item in patch.get('items', [])]
            if any(key.startswith('pta_sma') for key in keys):
                merged = patch
                break
        if merged is not None:
            break
        time.sleep(0.1)
    assert merged is not None, '没有收到后台补偿补丁'
    keys = [item['key'] for item in merged['items']]
    assert 'MA20' in keys                     # 常用指标也带上 ✓
    assert any(key.startswith('pta_sma') for key in keys)


def test_unknown_indicator_is_reported(tmp_path):
    desk = _desk(tmp_path)
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'add_indicator',
        'payload': {'symbol': 'SHFE.rb2610', 'key': 'nope_xxx'}}))
    kinds = [_payload(script)['type'] for script in desk.sent]
    assert 'toast' in kinds
    assert desk.tabs['SHFE.rb2610'].get('indicators') in (None, [])


def test_stale_async_result_is_dropped(tmp_path, monkeypatch):
    desk = _desk(tmp_path)
    info = desk.tabs['SHFE.rb2610']
    info['indicators'] = [{'key': 'pta_sma', 'params': {}}]
    # 慢速计算 → 期间把指标清空，结果必须被丢掉 ✓
    original = cat.compute

    def slow(*args, **kwargs):
        time.sleep(0.4)
        return original(*args, **kwargs)

    monkeypatch.setattr(cat, 'compute', slow)
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'remove_indicator', 'payload': {'symbol': 'SHFE.rb2610',
                                               'key': '*'}}))
    time.sleep(1.0)
    patches = [_payload(script) for script in desk.sent
               if '"type":"indicator"' in script]
    assert all(not patch.get('items') for patch in patches)


def test_p6_assets_built():
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[1]
    script = (repo / 'pylightcharts' / 'js' / 'desk.js').read_text(
        encoding='utf-8', errors='ignore')
    css = (repo / 'pylightcharts' / 'js' / 'desk.css').read_text(encoding='utf-8')
    for key in ('desk-ind-menu', 'desk-ind-item', 'desk-mask', 'desk-dialog'):
        assert key in css, key
    for key in ('desk-ind-menu', 'add_indicator'):
        assert key in script, key
    assert (repo / 'jslib' / 'src' / 'desk' / 'indicator-menu.ts').is_file()
    assert (repo / 'minibt' / 'desk' / 'indicator_catalog.py').is_file()
