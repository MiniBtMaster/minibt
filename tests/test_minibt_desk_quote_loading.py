"""报价页加载状态（修「永远显示 正在加载合约…」）+ 分类加载。

* `flush()` 只推界面骨架（boot/types/exchanges/rows_loading），**不阻塞**取数
* 真正的取数在 `tick()` 里做；失败 / 空数据都有明确状态
* 类型/交易所永远是具体的（FUT + 第一个交易所）
* `reload_contracts` 绕过缓存
"""
import json

import pytest

from minibt.desk import protocol


class _Feed:
    kind = 'futures'

    def __init__(self, rows=None, boom=False):
        self.rows = ['SHFE.rb2610'] if rows is None else list(rows)
        self.boom = boom
        self.calls = 0

    def available(self):
        return True

    def contracts(self, ins_class, exchange):
        self.calls += 1
        if self.boom:
            raise RuntimeError('网络炸了')
        return list(self.rows)

    def fill_names(self, symbols):
        return None

    def name_of(self, symbol):
        return '螺纹'

    def quotes(self, keys):
        return []

    def spec(self, symbol):
        return None

    def klines(self, *args, **kwargs):
        return None


class _Cache:
    """可控缓存：默认永远未命中 ✓"""

    def __init__(self, hit=None):
        self.hit = hit
        self.gets = 0
        self.puts = 0

    def get(self, key):
        self.gets += 1
        return self.hit

    def put(self, key, rows):
        self.puts += 1


def _desk(feed=None, cache=None):
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = feed or _Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._cache = cache or _Cache()
    desk._cache_ready = True
    return desk


def _wait_rows(desk, timeout: float = 5.0) -> None:
    """P83：合约清单在后台线程拉 → 等它回来并在主线程应用一次 ✓"""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        desk._drain_rows_result()
        if not desk._rows_loading and desk._rows_result is None:
            if any('"type":"rows"' in script for script in desk.sent):
                return
        time.sleep(0.02)


def _patches(sent):
    return [json.loads(script[len('window.__desk.applyPatch('):-2])
            for script in sent]


def test_flush_does_not_block_on_network():
    desk = _desk()
    desk.handle(protocol.encode_command({'cmd': 'ready'}))
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert kinds[0] == 'boot'                      # boot 后可能有 settings ✓
    for name in ('types', 'exchanges'):
        assert kinds.index(name) < kinds.index('rows_loading')
    assert 'rows_loading' in kinds
    assert desk.futures.calls == 0                 # 没在回调里取数 ✓
    assert desk._reload_pending is True
    status = [patch for patch in _patches(desk.sent)
              if patch['type'] == 'status'][-1]
    assert '加载中' in status['text']


def test_filter_is_concrete_futures_exchange():
    desk = _desk()
    desk.handle(protocol.encode_command({'cmd': 'ready'}))
    assert desk.filter['type'] == 'FUT'
    assert desk.filter['exchange'] == 'CFFEX'      # 具体交易所，不是空 ✓


def test_tick_loads_rows_with_loading_then_status():
    desk = _desk()
    desk.handle(protocol.encode_command({'cmd': 'ready'}))
    desk.sent.clear()
    desk._tick_at = 0.0
    desk.tick()
    _wait_rows(desk)
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert kinds[0] == 'rows_loading'              # 先「加载中」
    assert 'rows' in kinds and 'ticker' in kinds
    assert desk.futures.calls == 1
    status = [patch for patch in _patches(desk.sent)
              if patch['type'] == 'status'][-1]
    assert '1 行' in status['text'] and 'FUT' in status['text']


def test_empty_result_reports_zero_rows_not_loading():
    desk = _desk(_Feed(rows=[]))
    desk.handle(protocol.encode_command({'cmd': 'ready'}))
    desk._tick_at = 0.0
    desk.tick()
    _wait_rows(desk)
    status = [patch for patch in _patches(desk.sent)
              if patch['type'] == 'status'][-1]
    assert '0 行' in status['text']
    assert '加载中' not in status['text']
    rows = [patch for patch in _patches(desk.sent)
            if patch['type'] == 'rows'][-1]
    assert rows['rows'] == []


def test_failure_reports_error_and_empty_rows():
    desk = _desk(_Feed(boom=True))
    desk.handle(protocol.encode_command({'cmd': 'ready'}))
    desk._tick_at = 0.0
    desk.tick()
    _wait_rows(desk)
    patches = _patches(desk.sent)
    kinds = [patch['type'] for patch in patches]
    assert 'toast' in kinds                      # 明确报错 ✓
    status = [patch for patch in patches if patch['type'] == 'status'][-1]
    assert '加载失败' in status['text']
    rows = [patch for patch in patches if patch['type'] == 'rows'][-1]
    assert rows['rows'] == []


def test_switch_type_rebuilds_exchanges_and_loads():
    desk = _desk()
    desk.handle(protocol.encode_command({'cmd': 'ready'}))
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'filter', 'payload': {'type': 'STOCK'}}))
    patches = _patches(desk.sent)
    exchanges = [patch for patch in patches if patch['type'] == 'exchanges'][0]
    labels = [item['label'] for item in exchanges['items']]
    assert '港股' in labels and '美股' in labels
    assert desk.filter['exchange'] == 'SSE'      # 股票第一个交易所 ✓


def test_reload_contracts_bypasses_cache():
    cache = _Cache(hit=[{'symbol': 'CACHED.1', 'name': '缓存'}])
    desk = _desk(cache=cache)
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    desk._booted = True
    desk.reload_rows()                           # 命中缓存 ✓
    _wait_rows(desk)
    assert 'CACHED.1' in desk._last_rows
    assert cache.gets == 1

    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'reload_contracts'}))
    _wait_rows(desk)
    assert 'SHFE.rb2610' in desk._last_rows      # 绕过缓存，拿到真实数据 ✓
    # 刷新时不会再拿缓存**内容**（`_fetch_rows` 里判空看一次，不算命中 ✓）
    assert cache.puts >= 1


def test_loading_patch_helper():
    assert protocol.patch_rows_loading('正在加载 X…')['type'] == 'rows_loading'
