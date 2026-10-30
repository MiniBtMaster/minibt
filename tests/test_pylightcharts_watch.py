"""新看盘窗口（`pylightcharts_market_watch`）的数据层集成测试（mock 天勤）。

国庆期间没有实时行情，用假 `tq_api` 把「取数 → 合约/周期 → 面板」这条链路钉住：
不建 webview（不 `start()`），所以这些断言在 CI/离线也稳定 ✓。

    pytest tests/test_pylightcharts_watch.py
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import textwrap

REPO = pathlib.Path(__file__).resolve().parents[1]


def _run(script: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, '-c', textwrap.dedent(script)], cwd=str(REPO),
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=300)
    if result.returncode != 0:
        import pytest
        pytest.fail(f'子进程失败（{result.returncode}）:\n'
                    f'{result.stdout}\n{result.stderr}')
    return result


def test_data_layer_with_mock_tq_api():
    """`_frame` 走 `tq_api.get_kline_serial`，时间列是 datetime64 ✓。"""
    result = _run("""
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        import sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        import numpy as np
        import pandas as pd
        from PyQt6.QtWidgets import QApplication, QWidget
        app = QApplication([])

        class MockTqApi:
            def __init__(self):
                self.calls = []
            def get_kline_serial(self, symbol, cycle, length):
                self.calls.append((symbol, cycle, length))
                n = min(int(length or 100), 200)
                return pd.DataFrame({
                    'datetime': pd.date_range('2024-01-01', periods=n,
                                              freq='min'),
                    'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
                    'volume': 10})

        main = QWidget()
        main.tq_api = MockTqApi()
        main.login_status = {'futures': True}

        from miniqt.app.windows.pylightcharts_market_watch import (
            PylightchartsMarketWatchWindow, normalize_cycle)
        window = PylightchartsMarketWatchWindow(
            main, symbol='SHFE.rb2610', cycle=60, length=150)
        frame = window._frame('SHFE.rb2610', 60, 150)
        print('CALLS', main.tq_api.calls)
        print('COLS', list(frame.columns))
        print('DTYPE', str(frame['time'].dtype))
        print('ROWS', len(frame))
        print('CONTRACTS', window.contracts)

        # 股票周期归一化 / 类型识别（键盘精灵切合约用 ✓）
        window.switch_chart_symbol('000001', 'STOCK')
        print('STOCK', window.is_stock, window.cycle)
        window.switch_chart_symbol('SHFE.rb2610', 'FUTURES')
        print('FUTURES', window.is_stock, window.cycle)
        print('NORM', normalize_cycle(True, 400), normalize_cycle(False, 400))
    """)
    out = result.stdout
    assert "('SHFE.rb2610', 60, 150)" in out, out        # 透传到 tq_api
    assert "datetime64" in out, out                      # time 必须 datetime64
    assert 'ROWS 150' in out, out
    assert 'DTYPE datetime64' in out, out
    assert "CONTRACTS ['SHFE.rb2610']" in out, out
    assert 'STOCK True 60' in out, out                   # 股票 120 -> 60
    assert 'FUTURES False 60' in out, out
    assert 'NORM 300 400' in out, out


def test_watch_window_api_surface():
    """对外接口与旧 `MarketWatchWindow` 对齐（`start_minibt_chart` 直接替换 ✓）。"""
    watch = (REPO / 'miniqt' / 'app' / 'windows'
             / 'pylightcharts_market_watch.py').read_text(encoding='utf-8')
    for name in ('symbol', 'cycle', 'length', 'is_stock', 'main_window',
                 'set_last_clicked_widget', 'get_last_clicked_widget',
                 'active_chart_widget', 'switch_chart_symbol',
                 'show_key_elf', 'add_market_watch_window',
                 'on_period_button_clicked', 'closeEvent'):
        assert name in watch, name

    main = (REPO / 'miniqt' / 'app' / 'view' / 'main_window.py').read_text(
        encoding='utf-8')
    assert 'pylightcharts_market_watch' in main
    assert 'MINIQT_CHART_ENGINE' in main or 'engine_name' in main


def test_infinite_history_is_set_up_when_history_exceeds_data():
    """历史长度 > 数据长度 → 挂无限历史；相等/更小 → 不挂 ✓。"""
    result = _run("""
        import os, sys, types
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        import pandas as pd
        from PyQt6.QtWidgets import QApplication
        app = QApplication([])
        from miniqt.app.windows.pylightcharts_market_watch import (
            PylightchartsMarketWatchWindow as MW)

        full = pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=200, freq='min'),
            'open': 1.0, 'high': 1.0, 'low': 1.0, 'close': 1.0, 'volume': 1})
        view = full.tail(50).reset_index(drop=True)

        created = []

        class Chart:
            id = 'c1'
            def infinite_history(self, loader, page, threshold, on_load):
                created.append({'page': page, 'loader': loader,
                                'on_load': on_load})
                return types.SimpleNamespace(loaded=len(view),
                                             stop=lambda: None)

        def make(history_len):
            cached = full.tail(history_len).reset_index(drop=True)
            w = types.SimpleNamespace(
                chart_window=types.SimpleNamespace(
                    panel_frames={'c1': view}, panels=lambda: [chart_obj]),
                _panel_histories={},
                _history_frames={('SHFE.rb2610', 60): cached},
                history_length=history_len, length=50, cycle=60,
                symbol='SHFE.rb2610',
                contracts=['SHFE.rb2610'], is_stock=False)
            for name in ('_history_frame', '_setup_panel_history',
                         '_on_panel_history_load'):
                setattr(w, name, types.MethodType(getattr(MW, name), w))
            return w

        chart_obj = Chart()
        w1 = make(200)
        MW._setup_panel_history(w1, chart_obj, 'SHFE.rb2610')
        print('CREATED1', len(created), 'PAGE', created[0]['page'])
        older = created[0]['loader'](30, full['time'].iloc[100])
        print('OLDER', len(older), bool(older['time'].max()
                                        < full['time'].iloc[100]))

        # on_load → 更新 panel_frames + 刷新指标
        refreshed = []
        w1.chart_window.refresh_indicators = lambda *a, **k: refreshed.append(1)
        created[0]['on_load'](types.SimpleNamespace(loaded=120), 70)
        print('LOADED', len(w1.chart_window.panel_frames['c1']),
              'REFRESH', len(refreshed))

        # 历史 == 数据长度 → 没有更早的 → 不挂 ✓
        before = len(created)
        w2 = make(50)
        MW._setup_panel_history(w2, chart_obj, 'SHFE.rb2610')
        print('CREATED2', len(created) - before)
    """)
    out = result.stdout
    assert 'CREATED1 1' in out, out
    assert 'PAGE 50' in out, out            # 每页 = 当前视图长度
    assert 'OLDER 30 True' in out, out      # loader 能取更早的一批
    assert 'LOADED 120 REFRESH 1' in out, out
    assert 'CREATED2 0' in out, out         # 历史 == 数据 → 不挂 ✓


def test_history_is_fetched_lazily_and_only_once():
    """初始化只取**数据长度**；全量历史**懒取**（往左翻时才取一次）✓。"""
    result = _run("""
        import os, sys
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        import pandas as pd
        from PyQt6.QtWidgets import QApplication, QWidget
        app = QApplication([])

        class MockTqApi:
            def __init__(self):
                self.calls = []
            def get_kline_serial(self, symbol, cycle, length):
                self.calls.append((symbol, cycle, length))
                n = min(int(length or 100), 200)
                return pd.DataFrame({
                    'datetime': pd.date_range('2024-01-01', periods=n,
                                              freq='min'),
                    'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
                    'volume': 10})

        main = QWidget()
        main.tq_api = MockTqApi()
        main.login_status = {'futures': True}

        from miniqt.app.windows.pylightcharts_market_watch import (
            PylightchartsMarketWatchWindow)
        window = PylightchartsMarketWatchWindow(
            main, symbol='SHFE.rb2610', cycle=60, length=100,
            history_length=500)
        frame = window._frame('SHFE.rb2610', 60, 100)
        print('ROWS', len(frame))
        print('CALLS', main.tq_api.calls)
        # 初始化**不**拉全量 → 更快 ✓；往左翻时才懒取一次并缓存 ✓
        hist = window._history_frame('SHFE.rb2610', 60)
        print('HIST', len(hist))
        print('CALLS_AFTER', main.tq_api.calls)
        window._history_frame('SHFE.rb2610', 60)
        print('CALLS_THIRD', main.tq_api.calls)
    """)
    out = result.stdout
    assert 'ROWS 100' in out, out
    assert "CALLS [('SHFE.rb2610', 60, 100)]" in out, out   # 初始化只取数据长度 ✓
    assert 'HIST 200' in out, out
    # 懒取一次历史长度 ✓
    assert ("CALLS_AFTER [('SHFE.rb2610', 60, 100), "
            "('SHFE.rb2610', 60, 500)]") in out, out
    # 再取命中缓存 → 不重复订阅 ✓
    assert ("CALLS_THIRD [('SHFE.rb2610', 60, 100), "
            "('SHFE.rb2610', 60, 500)]") in out, out


def test_bootstrap_shows_kline_before_applying_a_template():
    """模板路径也要**先出 K 线**，再延后套模板（加载指标）✓。"""
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    import types
    import pandas as pd
    import pytest as _pytest
    window_module = _pytest.importorskip(
        'miniqt.app.windows.pylightcharts_market_watch')
    MW = window_module.PylightchartsMarketWatchWindow

    calls = []
    scheduled = []

    class FakeTimer:
        @staticmethod
        def singleShot(ms, fn):
            scheduled.append(fn)

    original_timer = window_module.QTimer
    window_module.QTimer = FakeTimer
    try:
        class ChartWindow:
            _defer_ms = 400

            def __init__(self):
                self.chart = types.SimpleNamespace(id='c1')
                self.panel_frames = {}

            def set_data(self, frame):
                calls.append('set_data')

            def load_layout_template(self, template):
                calls.append('load_template')

            def start_panel_realtime(self):
                calls.append('realtime')

            def probe(self, tag=''):
                calls.append('probe')

        frame = pd.DataFrame({'time': [1, 2], 'close': [1.0, 2.0]})
        window = types.SimpleNamespace(
            chart_window=ChartWindow(),
            _bootstrap_template={'name': 'ag2612_macd', 'layout': 'single'},
            symbol='SHFE.ag2612', cycle=60, length=1000,
            history_length=2000, _bootstrap_done=False,
            _setup_panel_history=lambda *a, **k: None,
            _log_stock_pool=lambda *a, **k: None)
        for name in ('_on_bootstrap_frame', '_apply_template_after_chart'):
            setattr(window, name, types.MethodType(getattr(MW, name), window))
        # 后台取数回来后：先出 K 线 + 起实时，套模板延时（先图后指标 ✓）
        MW._on_bootstrap_frame(window, frame)
        assert calls == ['set_data', 'realtime']
        assert window.chart_window.panel_frames.get('c1') is frame
        assert scheduled                          # 无限历史 + 套模板都延后 ✓
        for fn in scheduled:                      # 跑延后的回调
            fn()
        assert 'load_template' in calls
    finally:
        window_module.QTimer = original_timer


def test_bootstrap_prepares_data_before_building_chart():
    """**先取数据、再建图**（避免页面/数据竞态把图画成空图 ✗）✓。"""
    source = (REPO / 'miniqt' / 'app' / 'windows'
              / 'pylightcharts_market_watch.py').read_text(encoding='utf-8')
    start = source.index('    def _bootstrap(self)')
    guard = source.index('    def _ensure_chart_started(')
    between = source[start:guard]
    # 取数前**不**立即建图 ✓
    assert 'self.chart_window.start()' not in between
    assert 'BOOTSTRAP_FALLBACK_MS' in between           # 兜底建图 ✓
    assert 'BOOTSTRAP_TIMEOUT_MS' in between            # 超时恢复 tq 泵 ✓
    assert 'def _ensure_chart_started' in source
    assert 'def _on_bootstrap_timeout' in source
    # 数据回来后才建图 ✓
    frame = source.index('    def _on_bootstrap_frame(')
    after = source[frame:frame + 1200]
    assert 'self.chart_window.start()' in after


def test_bootstrap_timeout_resumes_pump_and_builds_chart():
    """首格取数超时 → 先把 tq 泵拉回 + 建图 + 提示（不能一直暂停泵 ✗）✓。"""
    import types
    import pytest as _pytest
    window_module = _pytest.importorskip(
        'miniqt.app.windows.pylightcharts_market_watch')
    MW = window_module.PylightchartsMarketWatchWindow

    calls = []

    class ChartWindow:
        chart = None

        def _resume_tq_qtimer(self):
            calls.append('resume')

        def start(self):
            self.chart = types.SimpleNamespace(id='c1')
            calls.append('start')

    window = types.SimpleNamespace(
        chart_window=ChartWindow(), _bootstrap_done=False,
        symbol='SHFE.ag2612',
        BOOTSTRAP_TIMEOUT_MS=MW.BOOTSTRAP_TIMEOUT_MS)
    for name in ('_on_bootstrap_timeout', '_ensure_chart_started'):
        setattr(window, name,
                types.MethodType(getattr(MW, name), window))
    window._warn_market_not_ready = lambda: calls.append('warn')

    MW._on_bootstrap_timeout(window)
    assert calls == ['resume', 'start', 'warn']
    # 已 bootstrap 完就不重复动作 ✓
    window._bootstrap_done = True
    calls.clear()
    MW._on_bootstrap_timeout(window)
    assert calls == []
