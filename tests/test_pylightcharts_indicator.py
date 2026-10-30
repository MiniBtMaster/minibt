"""指标参数窗口（``windows/indicator_dialog.py``）与画指标的守卫测试。

覆盖：

* 指标目录能从 ``minibt.IndicatorClass`` 枚举出来（不依赖主窗口 ✓）；
* 参数默认值用 ``inspect.signature`` 自动填 ✓；
* ``kline.<指标>(**参数)`` → ``{线名: 数值}``（``IndSeries`` / ``IndFrame``）✓；
* 画图走 ``create_line(..., price_line=…, price_label=…)``（主图叠加 ✓）
  或 ``add_pane() + pane_add_series``（副图 ✓）—— **价格线/价格标签属于指标功能** ✓。

    pytest tests/test_pylightcharts_indicator.py
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import textwrap

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
DIALOG = REPO / 'miniqt' / 'app' / 'windows' / 'indicator_dialog.py'
WINDOW = REPO / 'miniqt' / 'app' / 'windows' / 'pylightcharts_window.py'
TRADINGVIEW = REPO / 'minibt' / 'indicators' / 'tradingview.py'


def _run(script: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, '-c', textwrap.dedent(script)], cwd=str(REPO),
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=300)
    if result.returncode != 0:
        pytest.fail(f'子进程失败（{result.returncode}）:\n'
                    f'{result.stdout}\n{result.stderr}')
    return result


def test_dialog_file_exists_and_has_the_api():
    assert DIALOG.exists()
    source = DIALOG.read_text(encoding='utf-8')
    for name in ('def indicator_catalog', 'def default_params',
                 'def compute_indicator', 'class IndicatorDialog'):
        assert name in source, name
    # 价格线/价格标签是这个窗口的一部分
    assert "'price_line'" in source
    assert "'price_label'" in source


def test_catalog_comes_from_minibt():
    result = _run("""
        import os
        import sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        from miniqt.app.windows.indicator_dialog import indicator_catalog
        catalog = indicator_catalog()
        print('GROUPS', len(catalog))
        total = sum(len(v) for v in catalog.values())
        print('TOTAL', total)
        print('HAS_CCI', any(n == 'CCI' for v in catalog.values()
                             for n, _ in v))
    """)
    assert 'GROUPS' in result.stdout
    groups = int(result.stdout.split('GROUPS', 1)[1].split()[0])
    assert groups >= 1, result.stdout
    assert 'HAS_CCI True' in result.stdout, result.stdout


def test_compute_indicator_returns_named_lines():
    """``minibt.TaLib(kline).BBANDS(...)`` → 1 组、3 条线、8964 个值。"""
    result = _run("""
        import os
        import sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        from minibt import LocalDatas
        from miniqt.app.windows.indicator_dialog import compute_indicator
        plot = compute_indicator(LocalDatas.test.kline, 'TaLib', 'BBANDS',
                                 {'timeperiod': 5})
        groups = plot['groups']
        print('GROUPS', len(groups))
        print('OVERLAP', groups[0]['overlap'])
        print('NAMES', ','.join(groups[0]['lines']))
        print('LEN', [len(v) for v in groups[0]['lines'].values()])
    """)
    assert 'GROUPS 1' in result.stdout, result.stdout
    assert 'OVERLAP True' in result.stdout, result.stdout
    assert 'upperband,middleband,lowerband' in result.stdout, result.stdout
    assert '8964' in result.stdout, result.stdout


def test_doubles_indicators_split_main_and_sub():
    """``BtInd.AndeanOsc`` 同时画主图 + 副图（``doubles=True``）→ 两组。"""
    result = _run("""
        import os
        import sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        from minibt import LocalDatas
        from miniqt.app.windows.indicator_dialog import compute_indicator
        plot = compute_indicator(LocalDatas.test.kline, 'BtInd', 'AndeanOsc',
                                 {'length': 14, 'signal_length': 9})
        print('COUNTS', [(g['overlap'], len(g['lines']))
                         for g in plot['groups']])
    """)
    assert '(True, 2)' in result.stdout and '(False, 3)' in result.stdout, \
        result.stdout


def test_defaults_are_read_from_the_signature():
    result = _run("""
        import os
        import sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        from minibt import LocalDatas
        from miniqt.app.windows.indicator_dialog import (
            default_params, indicator_holder)
        holder = indicator_holder(LocalDatas.test.kline, 'TaLib')
        params = default_params(getattr(holder, 'ADX'))
        print('PARAMS', params)
    """)
    assert 'PARAMS' in result.stdout
    # ADX 的 timeperiod 默认值应在里面
    assert 'timeperiod' in result.stdout, result.stdout


def test_drawing_keeps_price_line_options():
    """画指标线必须能把价格线/价格标签传下去（那是指标功能的一部分 ✓）。"""
    source = WINDOW.read_text(encoding='utf-8')
    assert 'price_line=price_line' in source
    assert 'price_label=price_label' in source
    assert 'create_line' in source                  # 主图叠加
    assert 'pane_add_series' in source              # 副图
    assert 'add_pane' in source


def test_toolbar_has_the_indicator_button():
    source = WINDOW.read_text(encoding='utf-8')
    assert 'def open_indicator_picker' in source
    topbar = (WINDOW.parent / 'tradingview_topbar.py').read_text(
        encoding='utf-8')
    assert 'indicatorButton' in topbar and 'open_indicator_picker' in topbar


def test_dialog_loads_params_from_a_kline():
    """KLine 不能被当真值判断（``if self.kline`` 会抛 pandas 的"truth value is
    ambiguous"✗）；参窗口打开后应该能把参数列出来 ✓。"""
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
        from PyQt6.QtWidgets import QApplication
        app = QApplication([])
        from minibt import LocalDatas
        from miniqt.app.windows.indicator_dialog import IndicatorDialog
        dialog = IndicatorDialog(None, kline=LocalDatas.test.kline)
        print('GROUPS', dialog.groupBox.count())
        index = [dialog.groupBox.itemText(i)
                 for i in range(dialog.groupBox.count())].index('TaLib')
        dialog.groupBox.setCurrentIndex(index)
        index = [dialog.nameBox.itemText(i)
                 for i in range(dialog.nameBox.count())].index('BBANDS')
        dialog.nameBox.setCurrentIndex(index)
        print('ROWS', dialog.paramsForm.rowCount())
    """)
    assert 'GROUPS' in result.stdout, result.stdout
    rows = int(result.stdout.split('ROWS', 1)[1].split()[0])
    assert rows >= 2, result.stdout


def test_manager_add_remove_and_refresh():
    """``add_indicator`` / ``remove_indicator`` / ``refresh_indicators``：

    * 主图多线指标 → 直接在主图（不开 pane ✓）；
    * 副图多线 → **一个指标一个 pane**，不是一个线一个 pane ✗；
    * ``doubles`` 指标 → 主图 + 副图都画 ✓；
    * 删除/刷新/清空 ✓。
    """
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
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        app = QApplication([])
        from minibt import LocalDatas
        from miniqt.app.windows.pylightcharts_page import dataset_frame
        from miniqt.app.windows.pylightcharts_window import (
            PylightchartsChartWindow)

        class FakeSeries:
            def __init__(self, name):
                self.name = name; self.data = None; self.deleted = False
            def set(self, df): self.data = df
            def delete(self): self.deleted = True
        class FakeChart:
            def __init__(self): self.lines = []; self.panes = []
            def create_line(self, name, **kw):
                s = FakeSeries(name); self.lines.append(s); return s
            def create_histogram(self, name, **kw):
                s = FakeSeries(name); self.lines.append(s); return s
            def add_pane(self):
                p = len(self.panes) + 1; self.panes.append(p); return p
            def pane_add_series(self, pane, kind, name='', **kw):
                s = FakeSeries(name); self.lines.append(s); return s

        window = PylightchartsChartWindow()
        window.chart = FakeChart()
        window._panel_frame = dataset_frame('test')
        window._defer_ms = 0
        window.indicators = []
        window._indicator_seq = 0
        window.last_panel = None
        window.panel_frames = {}
        window.kline = LocalDatas.test.kline

        def flush():
            QTimer.singleShot(30, app.quit); app.exec()

        main = window.add_indicator({'group': 'TaLib', 'name': 'BBANDS',
            'params': {'timeperiod': 5}, 'overlap': True,
            'color': '#FF9800', 'width': 2, 'price_line': True,
            'price_label': True})
        flush()
        print('MAIN', [s.name for s in main['series']], len(main['panes']))

        sub = window.add_indicator({'group': 'TaLib', 'name': 'MACD',
            'params': {}, 'overlap': False, 'color': '#2196F3',
            'width': 2, 'price_line': False, 'price_label': False})
        flush()
        print('SUB', [s.name for s in sub['series']], len(sub['panes']))

        double = window.add_indicator({'group': 'BtInd', 'name': 'AndeanOsc',
            'params': {'length': 14, 'signal_length': 9}})
        flush()
        print('DOUBLE', [s.name for s in double['series']], len(double['panes']))

        print('REFRESH', window.refresh_indicators(window._panel_frame))
        worker = getattr(window, '_indicator_worker', None)
        if worker is not None:
            worker.wait(15000)
            app.processEvents()
        applied = sum(1 for ind in window.indicator_manager.getIndicators()
                      for series in ind.indicator_lines.values()
                      if series.data is not None)
        print('APPLIED', applied)
        print('REMOVE', window.remove_indicator(sub['id']),
              len(window.indicators))
        window.clear_indicators()
        print('CLEAR', len(window.indicators))
    """)
    out = result.stdout
    assert 'MAIN' in out and 'upperband' in out, out
    assert 'SUB' in out and 'histogram' in out, out
    # 一个副图指标只有一个 pane（旧代码逐线开 pane 是错的）
    main_line = [l for l in out.splitlines() if l.startswith('MAIN')][0]
    sub_line = [l for l in out.splitlines() if l.startswith('SUB')][0]
    double_line = [l for l in out.splitlines() if l.startswith('DOUBLE')][0]
    assert main_line.strip().endswith(' 0'), main_line
    assert sub_line.strip().endswith(' 1'), sub_line
    assert double_line.strip().endswith(' 1'), double_line
    # 刷新走后台线程：返回待算的指标数，算完在主线程应用（共 11 条线）
    assert 'REFRESH 3' in out, out
    assert 'APPLIED 11' in out, out
    assert 'REMOVE True 2' in out, out
    assert 'CLEAR 0' in out, out


def test_price_alert_latching():
    """价格预警：上/下破各触发一次，回到区间内解除锁定后再触发 ✓。"""
    result = _run("""
        import os, tempfile, pathlib
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        import sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        from PyQt6.QtWidgets import QApplication
        app = QApplication([])
        from miniqt.app.common import chart_data as cd
        tmp = pathlib.Path(tempfile.mkdtemp()) / 'chart_data.json'
        cd.chart_data_manager = cd.ChartDataManager(str(tmp))

        from miniqt.app.windows import pylightcharts_window as pw
        class FakeInfoBar:
            calls = []
            @classmethod
            def info(cls, *a, **k): cls.calls.append(('info', a))
            @classmethod
            def warning(cls, *a, **k): cls.calls.append(('warning', a))
        pw.InfoBar = FakeInfoBar

        window = pw.PylightchartsChartWindow.__new__(pw.PylightchartsChartWindow)
        window.chart = None          # 没建图（load 里有 map 查 chart，未 init 的 Qt 对象会炸）
        window._closing = False
        window._alert_fired = set()
        window.price_alert = {}
        window._drawing_tag = lambda: 'TEST|60'
        window.load_price_alert()
        window.apply_price_alert({'enabled': True, 'alert_type': 'both',
                                  'up_price': 100.0, 'down_price': 90.0})
        print('BEFORE', len(FakeInfoBar.calls))
        window.check_price_alert(101.0); print('UP', len(FakeInfoBar.calls))
        window.check_price_alert(102.0); print('UP2', len(FakeInfoBar.calls))
        window.check_price_alert(95.0);  print('BACK', len(FakeInfoBar.calls))
        window.check_price_alert(89.0);  print('DOWN', len(FakeInfoBar.calls))
        window.check_price_alert(100.5)
        window.check_price_alert(102.0); print('REUP', len(FakeInfoBar.calls))
        print('SAVED', cd.chart_data_manager.get_price_alerts('TEST|60'))
    """)
    out = result.stdout
    assert 'BEFORE 1' in out, out      # apply 时一条 info
    assert 'UP 2' in out, out          # 上破触发
    assert 'UP2 2' in out, out         # 已锁定，不再触发
    assert 'BACK 2' in out, out        # 回到区间内（解除锁定）
    assert 'DOWN 3' in out, out        # 下破触发
    assert 'REUP 4' in out, out        # 再回区间后又上破 → 再次触发
    assert "'up_price': 100.0" in out or "100.0" in out, out


def test_supertrend_family_loops_use_numpy_and_run_fast():
    """``SuperTrend_STRATEGY`` / ``Chandelier_Exit`` 曾经在循环里写 IndSeries
    （``self.ones``/``self.full()``），每根 4 次 pandas ``__setitem__``（~0.1ms）
    → 8964 根要 ~3s，主线程加载直接卡死 ✗。改成 numpy 数组后 ~0.02s ✓。
    """
    source = TRADINGVIEW.read_text(encoding='utf-8')
    for cls in ('SuperTrend_STRATEGY', 'Chandelier_Exit'):
        body = source.split(f'class {cls}', 1)[1].split('\nclass ', 1)[0]
        # 去掉注释行再查（注释里会提到旧写法 ✓）
        code = '\n'.join(l for l in body.splitlines()
                         if not l.lstrip().startswith('#'))
        assert 'np.ones(size)' in code and 'np.full(size, np.nan)' in code, cls
        assert 'dir = self.ones' not in code, cls
        assert 'up = self.full()' not in code, cls

    result = _run("""
        import os, sys, time
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        import numpy as np
        from minibt import LocalDatas
        from miniqt.app.windows.indicator_dialog import compute_indicator
        jobs = [('SuperTrend_STRATEGY',
                 {'Periods': 22, 'Multiplier': 3.0, 'changeATR': True}),
                ('Chandelier_Exit',
                 {'length': 22, 'mult': 3.0, 'useClose': True})]
        for name, params in jobs:                       # 预热
            compute_indicator(LocalDatas.test.kline, 'TradingView', name, params)
        for name, params in jobs:
            t = time.time()
            plot = compute_indicator(LocalDatas.test.kline, 'TradingView',
                                     name, params)
            dt = time.time() - t
            lines = plot['groups'][0]['lines']
            finite = [int(np.isfinite(np.asarray(lines[k], dtype=float)).sum())
                      for k in ('up', 'dn') if k in lines]
            print('SECONDS', name, round(dt, 3))
            print('FINITE', name, finite)
    """)
    for cls in ('SuperTrend_STRATEGY', 'Chandelier_Exit'):
        seconds = float(result.stdout.split(f'SECONDS {cls}', 1)[1].split()[0])
        assert seconds < 1.0, result.stdout            # 原来 ~3s ✗
        finite = result.stdout.split(f'FINITE {cls}', 1)[1].split(']')[0]
        numbers = [int(x) for x in
                   finite.replace('[', ' ').replace(',', ' ').split()]
        assert numbers and all(n > 0 for n in numbers), result.stdout    # 两条线都有数据 ✓


def test_renko_signals_anchor_at_the_real_price_not_value_1():
    """``RenkoCandlesOverlay`` 的砖块只在最近几根，信号却遍布全历史。

    信号锚点（``high``/``low``）必须取**源数据的真实价格**：如果拿指标自己输出的
    ``high``/``low``（砖块上下沿，大部分 bar 是 NaN），大片历史信号会掉到
    ``value=1`` 上 ✗（用户截图：价格为 1 的一整行都是信号）。
    """
    result = _run("""
        import os, sys, types
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        import PyQt6.QtWebEngineWidgets      # noqa: F401
        import numpy as np, pandas as pd
        from minibt import LocalDatas
        from miniqt.app.windows.indicator_dialog import compute_indicator
        from miniqt.app.windows import pylightcharts_window as pw

        frame = LocalDatas.test.kline.pandas_object.copy()
        frame['time'] = pd.to_datetime(frame['datetime'])
        frame = frame.tail(2000).reset_index(drop=True)
        params = dict(mode='ATR/2', atr_period=14, brick_size=10.0,
                      percentage=0.1, period=140, brick_width=2, max_bars=285,
                      align='Repaint', mintick=None)
        plot = compute_indicator(frame, 'TradingView',
                                 'RenkoCandlesOverlay', params)
        times = list(frame['time'])

        class S:
            def __init__(self): self.data = None
            def set(self, data, shapes=None): self.data = data
            def pin_legend_row(self, *a): pass
            def delete(self): pass
        class T:
            def __init__(self): self.series = {}
            def add_custom_series(self, name, color, legend_toggle):
                s = S(); self.series[name] = s; return s

        win = types.SimpleNamespace()
        win._safe_color = pw.PylightchartsChartWindow._safe_color
        win._draw_indicator_signals = types.MethodType(
            pw.PylightchartsChartWindow._draw_indicator_signals, win)
        target = T()
        win._draw_indicator_signals(target, plot, times, frame, {})
        print('RANGE', round(float(frame['low'].min()), 1),
              round(float(frame['high'].max()), 1))
        for name, series in target.series.items():
            vals = series.data['base'].to_numpy(dtype=float)
            print('SIG', name, len(series.data), int((vals == 1).sum()),
                  round(float(np.nanmin(vals)), 1),
                  round(float(np.nanmax(vals)), 1))
    """)
    out = result.stdout
    assert 'SIG long_signal' in out and 'SIG short_signal' in out, out
    low, high = (float(x) for x in
                 out.split('RANGE', 1)[1].split()[:2])
    for line in out.splitlines():
        if not line.startswith('SIG'):
            continue
        parts = line.split()
        assert int(parts[3]) == 0, out          # 没有掉到 value=1 上的信号 ✓
        lo, hi = float(parts[4]), float(parts[5])
        assert low - 1e-6 <= lo and hi <= high + 1e-6, out   # 锚在真实价格区间内 ✓


def test_btind_supertrend_marks_the_unused_side_as_nan():
    """`BtInd.supertrend` 的 long/short 未确定方向的一侧必须是 **NaN**，不能是 inf。

    `inf` 会走 base64 下发成 JS `Infinity` → 自动缩放 / 图例读数异常 ✗
    （pandas_ta 原版就是 `[nan]*m`；minibt 曾误写成 `[npInf]*m`）。
    """
    result = _run("""
        import os, sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        import numpy as np
        from minibt import LocalDatas
        from miniqt.app.windows.indicator_dialog import compute_indicator
        plot = compute_indicator(LocalDatas.test.kline, 'BtInd', 'supertrend',
                                 {'length': 14, 'multiplier': 2.0,
                                  'weights': 2.0})
        for name, values in plot['groups'][0]['lines'].items():
            a = np.asarray(values, dtype=float)
            print('LINE', name, int(np.isinf(a).sum()))
    """)
    out = result.stdout
    assert 'LINE long 0' in out and 'LINE short 0' in out, out


def test_history_load_refreshes_bands_and_signals():
    """无限历史往左补数据后，色带的**隐藏边** + 信号也要按新长度重画 ✓。

    否则「历史段没有色带/信号」（用户截图 tradingview/历史数据段没有加载...png）。
    """
    result = _run("""
        import os, types
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        import sys
        sys.path.insert(0, '.')
        from pylightcharts.compat import install_alias
        install_alias()
        os.chdir('miniqt')
        import miniqt.app.common.config      # noqa: F401
        os.chdir('..')
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        app = QApplication([])
        import pandas as pd
        from minibt import LocalDatas
        from miniqt.app.windows.pylightcharts_page import dataset_frame
        from miniqt.app.windows.pylightcharts_window import (
            PylightchartsChartWindow)

        class FakeFill:
            def delete(self): pass
        class FakeSeries:
            def __init__(self, name):
                self.name = name; self.data = None; self.set_count = 0
            def set(self, df, shapes=None):
                self.data = df; self.set_count += 1
            def delete(self): pass
            def fill_between(self, other, **kw): return FakeFill()
            def pin_legend_row(self, *a, **k): pass
            def enable_legend_settings(self, *a, **k): pass
            def remove_legend_row(self): pass
            def skip_gap_segments(self, value=True):
                self.skip_gap = value; return self
        class FakeChart:
            def __init__(self): self.lines = []; self.custom = []
            def create_line(self, name, **kw):
                s = FakeSeries(name); self.lines.append(s); return s
            def create_histogram(self, name, **kw):
                s = FakeSeries(name); self.lines.append(s); return s
            def add_series(self, kind, name='', **kw):
                s = FakeSeries(name); self.lines.append(s); return s
            def pane_add_series(self, pane, kind, name='', **kw):
                s = FakeSeries(name); self.lines.append(s); return s
            def add_custom_series(self, name, **kw):
                s = FakeSeries(name); self.custom.append(s); return s
            def add_pane(self): return 1

        window = PylightchartsChartWindow()
        window.chart = FakeChart()
        window._panel_frame = dataset_frame('test')
        window._defer_ms = 0
        window.indicators = []
        window.last_panel = None
        window.panel_frames = {}
        window.kline = LocalDatas.test.kline

        def flush():
            QTimer.singleShot(30, app.quit); app.exec()

        entry = window.add_indicator({'group': 'TradingView',
            'name': 'HemaTrendLevels', 'params': {}})
        flush()
        edges = entry.get('band_edges') or {}
        sig = entry.get('signal_series') or {}
        print('BASE', len(window._panel_frame))
        print('EDGE_BEFORE', max((len(s.data) for s in edges.values()
                                  if s.data is not None), default=0))
        print('SKIP', all(getattr(s, 'skip_gap', False)
                          for s in edges.values()))
        print('FILLS_BEFORE', len(entry.get('fills') or []))
        print('SIGSET_BEFORE', sum(s.set_count for s in sig.values()))

        # 模拟无限历史补数据：换 2000 根的帧，直接走 _apply_indicator_results
        from miniqt.app.windows.indicator_dialog import compute_indicator
        full = LocalDatas.test.kline.pandas_object.copy()
        full['time'] = pd.to_datetime(full['datetime'])
        long_frame = full.tail(2000).reset_index(drop=True)
        window._panel_frame = long_frame
        plot = compute_indicator(long_frame, 'TradingView',
                                 'HemaTrendLevels', {})
        lines = {}
        for group_info in plot['groups']:
            lines.update(group_info['lines'])
        window._apply_indicator_results(
            [(entry['id'], lines, list(long_frame['time']), False, plot,
              long_frame)])

        print('EDGE_AFTER', max((len(s.data) for s in edges.values()
                                 if s.data is not None), default=0))
        print('FILLS_AFTER', len(entry.get('fills') or []))
        print('SIGSET_AFTER', sum(s.set_count for s in sig.values()))
    """)
    out = result.stdout
    assert 'BASE 1000' in out, out
    assert 'EDGE_BEFORE 1000' in out, out
    assert 'SKIP True' in out, out             # 隐藏色带边跳过断点 ✓
    assert 'EDGE_AFTER 2000' in out, out          # 隐藏色带边跟上了新长度 ✓
    assert 'FILLS_BEFORE 4' in out and 'FILLS_AFTER 4' in out, out   # 不重复建 ✓
    before = int(out.split('SIGSET_BEFORE', 1)[1].split()[0])
    after = int(out.split('SIGSET_AFTER', 1)[1].split()[0])
    assert after > before, out                    # 信号也刷新了 ✓


def test_finite_last_point_skips_nan_and_inf():
    """对齐 minibt `realtime.py::update_last`：最后一点是 NaN/inf 就不推 ✓。"""
    result = _run("""
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        import sys
        sys.path.insert(0, '.')
        import PyQt6.QtWebEngineWidgets      # noqa: F401
        import numpy as np
        from miniqt.app.windows.pylightcharts_window import (
            PylightchartsChartWindow as W)
        f = W._finite_last_point
        print('FIN', f(np.array([1.0, 2.0])), f(np.array([1.0, np.nan])),
              f(np.array([1.0, np.inf])), f(np.array([1.0, -np.inf])),
              f([]))
    """)
    assert 'FIN 2.0 None None None None' in result.stdout, result.stdout
