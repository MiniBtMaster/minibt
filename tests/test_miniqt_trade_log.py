"""成交/委托「进运行日志」的状态初始化（回归测试）。

bug：``_logged_trade_ids`` / ``_logged_order_ids`` / ``_log_primed`` 原来**只在切换
账户时**才创建（``_on_account_changed``），窗口一打开、只要「交易账户」页可见，
定时刷新就会报

    AttributeError("'PylightchartsChartWindow' object has no attribute '_log_primed'")

并且被 ``_refresh_docks`` 的 ``except`` 吞掉 → 每 1 秒复读一次（看着像断线，其实不是）。

修法：① ``__init__`` 里就初始化这组字段；② ``_ensure_log_state()`` 兜底补齐。
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WINDOW = REPO / 'miniqt' / 'app' / 'windows' / 'pylightcharts_window.py'


def _fake_window():
    """只借方法：Qt 基类禁止访问"未 init 实例"的属性，所以不能直接 ``__new__``。"""
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow)

    return type('FakeWindow', (object,), {
        '_log_new_trades': PylightchartsChartWindow._log_new_trades,
        '_ensure_log_state': PylightchartsChartWindow._ensure_log_state,
    })()


def test_log_new_trades_works_without_initialized_state():
    window = _fake_window()
    window._trades_snapshot = {'t1': {'trade_id': 'T1',
                                      'instrument_id': 'SHFE.ag2612',
                                      'direction': 'BUY', 'offset': 'OPEN',
                                      'volume': 1, 'price': 3600.0}}
    window._orders_snapshot = {'o1': {'order_id': 'O1',
                                      'instrument_id': 'SHFE.ag2612',
                                      'direction': 'BUY', 'offset': 'OPEN',
                                      'volume': 1, 'status': 'ALIVE'}}
    lines = []
    window._account_tag = lambda: '[模拟]'
    window._append_ui_log = lambda text: lines.append(text)

    window._log_new_trades()          # 第一次：登记历史 → 不写日志 ✓
    assert lines == []
    assert window._log_primed is True
    assert window._logged_trade_ids == {'T1'}
    assert window._logged_order_ids == {'O1'}

    window._trades_snapshot['t2'] = {'trade_id': 'T2',
                                     'instrument_id': 'SHFE.ag2612',
                                     'direction': 'SELL', 'offset': 'CLOSE',
                                     'volume': 2, 'price': 3610.0}
    window._log_new_trades()          # 新成交 → 写一条 ✓
    assert len(lines) == 1 and '[成交]' in lines[0]
    window._log_new_trades()          # 同一笔不重复写 ✓
    assert len(lines) == 1


def test_ensure_log_state_repairs_broken_values():
    window = _fake_window()
    window._logged_trade_ids = None
    window._logged_order_ids = ['T1']          # 不是 set → 重置
    window._log_primed = None
    window._ensure_log_state()
    assert window._logged_trade_ids == set()
    assert window._logged_order_ids == set()
    assert window._log_primed is False
    assert window._orders_snapshot is None
    assert window._trades_snapshot is None


def test_window_init_initializes_log_state():
    source = WINDOW.read_text(encoding='utf-8')
    # 从**主窗口类**往下找第一个 __init__（文件前面还有一堆小类 ✗）
    start = source.index('class PylightchartsChartWindow')
    start = source.index('    def __init__(self', start)
    init = source[start:start + source[start:].index('\n    def ')]
    for line in ('self._log_primed = False',
                 'self._logged_trade_ids: set = set()',
                 'self._logged_order_ids: set = set()',
                 'self._orders_snapshot = None'):
        assert line in init, f'__init__ 缺少 {line}'
    # 切换账户前也要兜底（老实例才不会炸）
    assert re.search(r'_ensure_log_state\(\)\n\s+self\._logged_trade_ids\.clear',
                     source), '切账户时没有先 _ensure_log_state()'


def test_refresh_docks_reports_each_error_once():
    """定时刷新的异常**同类只报一次**（首报带 traceback），否则每秒刷屏 ✗"""
    from miniqt.app.windows.pylightcharts_window import (
        PylightchartsChartWindow)

    lines = []
    fake = type('FakeDocks', (object,), {
        '_refresh_docks': PylightchartsChartWindow._refresh_docks,
        'quotePanel': type('Q', (), {'isHidden': lambda self: True})(),
        'simPanel': type('S', (), {'isHidden': lambda self: True})(),
        '_refresh_position_lines': lambda self, with_trades=True: None,
    })()
    fake._dock_errors = set()
    import miniqt.app.windows.pylightcharts_window as module
    original = module._log
    module._log = lambda text: lines.append(text)
    try:
        fake._refresh_docks()
        assert lines == []                       # 没异常 → 不写日志 ✓
        def boom(with_trades=True):
            raise ValueError('boom')
        fake._refresh_position_lines = boom
        fake._refresh_docks()
        fake._refresh_docks()
        fake._refresh_docks()
    finally:
        module._log = original
    assert sum('刷新报价/模拟账号失败' in line for line in lines) == 1
    assert any('ValueError: boom' in line for line in lines)     # 首报带 traceback ✓
