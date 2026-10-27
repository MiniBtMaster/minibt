"""实时图「记住每个合约的可视范围，切回来恢复」✓。

回归背景：以前只在 ``_save_view`` 里**同步**调 ``get_visible_logical_range()``
（阻塞式往返）—— 在 pywebview 主线程上很容易读不到 / 超时 → 什么都存不下来，
表现为「每次切合约都回到初始视图」✗。现在改成 **事件驱动**：
``subscribeVisibleLogicalRangeChange`` 一变化就回包 ``minibt_view_range`` ✓。
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _read(*parts):
    return REPO.joinpath(*parts).read_text(encoding='utf-8')


# --------------------------------------------------------------------------- #
# 桩：只借用 StrategyWindow 上那几个纯 Python 方法（不建真窗口 ✓）
# --------------------------------------------------------------------------- #
def _stub(total: int = 1000):
    from minibt.strategy.strategy_window import StrategyWindow

    class _Data:
        def __init__(self, n):
            self.n = n

        def __len__(self):
            return self.n

    class _Chart:
        id = 'w_chart1'
        win = type('W', (), {'handlers': {}, 'loaded': True})()

        def __init__(self, n):
            self.data = _Data(n)
            self.scripts = []
            self.ranges = []

        @property
        def candle_data(self):
            return self.data

        def run_script(self, script):
            self.scripts.append(script)

        def set_visible_logical_range(self, a, b):
            self.ranges.append((a, b))

    class _Stub:
        pass

    for name in ('install_view_tracking', '_on_view_range', '_remember_view',
                 '_lock_view', '_unlock_view', '_restore_view'):
        setattr(_Stub, name, getattr(StrategyWindow, name))
    stub = _Stub()
    stub.chart = _Chart(total)
    stub.contract = 'A'
    stub._view_ranges = {}
    stub._view_lock_depth = 0
    stub._view_tracking = False
    return stub


# --------------------------------------------------------------------------- #
# 记录
# --------------------------------------------------------------------------- #
def test_remember_view_stores_length_offset_and_absolute():
    stub = _stub(1000)
    stub._on_view_range(900, 999)
    assert stub._view_ranges['A'] == (99, 0, 999)
    # 翻到历史区 → offset 为负（切回时按绝对窗口恢复 ✓）
    stub._on_view_range(100, 199)
    assert stub._view_ranges['A'] == (99, -800, 199)


def test_view_range_ignored_while_locked_or_on_info_page():
    """切合约/重建过程中的过渡态、以及信息页，都不该污染记录 ✗"""
    stub = _stub(1000)
    stub._on_view_range(900, 999)
    saved = dict(stub._view_ranges)

    stub._lock_view()
    stub._on_view_range(0, 10)          # 过渡态（fit 的全量范围）
    assert stub._view_ranges == saved, '锁定期间不该记录 ✗'
    stub._unlock_view()

    stub.contract = '回测结果'            # 信息页不记 K 线视口 ✓
    stub._on_view_range(0, 10)
    assert stub._view_ranges == saved
    stub.contract = 'A'
    stub._unlock_view()                  # 多解锁一次也不能变负
    assert stub._view_lock_depth == 0


def test_view_range_bad_payload_is_ignored():
    stub = _stub(1000)
    for bad in ((None, None), ('x', 'y'), (float('nan'), 1.0)):
        stub._on_view_range(*bad)
    assert stub._view_ranges == {}


# --------------------------------------------------------------------------- #
# 恢复
# --------------------------------------------------------------------------- #
def test_restore_follows_newest_when_left_at_right_edge():
    """离开时贴在右端 → 切回时锚定最后一根（新 K 线照常往后走 ✓）"""
    stub = _stub(1000)
    stub._on_view_range(900, 999)        # offset = 0
    stub.chart = _stub(1200).chart
    stub._restore_view('A')
    assert stub.chart.ranges[-1] == (1100, 1199)


def test_restore_absolute_window_when_scrolled_back():
    """★ 用户要的「恢复到这个可视范围」：翻到历史区也要切回**同一窗口** ✓"""
    stub = _stub(1200)
    stub._on_view_range(100, 199)        # offset = 199-1199 = -1000
    assert stub._view_ranges['A'][1] < 0
    stub.chart = _stub(1300).chart       # 新合约 K 线更多
    stub._restore_view('A')
    from_, to = stub.chart.ranges[-1]
    assert (from_, to) == (100, 199), '应恢复同一个绝对窗口（不跳最后一根）✗'
    assert to - from_ == stub._view_ranges['A'][0]   # 可见跨度不缩水 ✓


def test_restore_handles_legacy_and_short_data():
    stub = _stub(1000)
    stub._view_ranges['old'] = (50, 0)   # 旧格式 (length, offset)
    stub._restore_view('old')
    assert stub.chart.ranges[-1] == (949, 999)
    stub._view_ranges['num'] = 50        # 更旧：只存根数
    stub._restore_view('num')
    assert stub.chart.ranges[-1] == (949, 999)
    stub._view_ranges['none'] = None     # 没记录 → 不动
    before = len(stub.chart.ranges)
    stub._restore_view('none')
    assert len(stub.chart.ranges) == before


# --------------------------------------------------------------------------- #
# 接线
# --------------------------------------------------------------------------- #
def test_install_view_tracking_registers_fixed_callback():
    """JS 侧用**固定回调名** ``minibt_view_range``（和买卖盘同一套 ✓）+ 幂等 ✓"""
    stub = _stub(1000)
    stub.install_view_tracking()
    handlers = stub.chart.win.handlers
    assert list(handlers) == ['minibt_view_range']
    script = stub.chart.scripts[-1]
    assert 'subscribeVisibleLogicalRangeChange' in script
    assert "minibt_view_range_~_" in script
    assert stub._view_tracking is True
    stub.install_view_tracking()                     # 幂等：不再注入
    assert len(stub.chart.scripts) == 1


def test_save_view_prefers_event_stream_over_blocking_read():
    """★★ 核心修复：事件流已有记录时**不能**再走阻塞式同步读取 ✗"""
    stub = _stub(1000)
    stub._on_view_range(900, 999)

    calls = []

    def _boom():
        calls.append(1)
        raise AssertionError('不该走同步往返 ✗')

    stub.chart.get_visible_logical_range = _boom
    stub.window = None
    from minibt.strategy.strategy_window import StrategyWindow
    StrategyWindow._save_view(stub, 'A')
    assert calls == [], '事件流已记好却还去同步读取 ✗'
    assert stub._view_ranges['A'] == (99, 0, 999)


def test_set_contract_locks_and_restores_last():
    """``set_contract``：离开前记录 + 全程加锁 + **最后**恢复 ✓"""
    src = _read('minibt', 'strategy', 'strategy_window.py')
    start = src.index('def set_contract')
    body = src[start:src.index('def set_backtest', start)]
    assert 'self.install_view_tracking()' in body
    assert 'self._save_view(self.contract)' in body
    assert 'self._lock_view()' in body and 'self._unlock_view()' in body
    # 恢复必须在重建之后（建 pane / 加载画线都可能扰动视口）
    assert body.rindex('self._restore_view(contract)') > \
        body.index('self._apply_pane_stretch()')


def test_realtime_set_contract_locks_and_restores_last():
    """实时包装：整个切换过程加锁，并在 ``_setup_history`` 之后再恢复 ✓"""
    src = _read('minibt', 'strategy', 'realtime.py')
    start = src.index('def set_contract(contract: str, force: bool = False)')
    body = src[start:start + 4000]
    assert 'lock_view()' in body and 'unlock_view()' in body
    assert "restore(contract)" in body
    assert body.index('self._setup_history()') < body.index('restore(contract)')
