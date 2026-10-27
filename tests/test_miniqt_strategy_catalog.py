# coding: utf-8
"""交易策略目录（「交易策略」/「我的策略」）+ 指标界面左导航（P2 壳）✓。

只测**发现 / 校验 / 界面壳**，不测策略引擎（那部分还没接 ✓）。
"""
from __future__ import annotations

import os
import textwrap

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

pytest.importorskip('PyQt6')
from PyQt6.QtCore import Qt  # noqa: E402

catalog = pytest.importorskip('miniqt.app.common.strategy_catalog')
_runner_mod = pytest.importorskip('miniqt.app.common.strategy_runner')

Strategy = pytest.importorskip('minibt').Strategy


class _WithGetKline(Strategy):
    """用 get_kline 取数据（会调用 ✓）。"""
    def __init__(self):
        self.k = self.get_kline('SHFE.rb2610')
        self.ma = self.k.close.sma(5)

    def next(self):
        pass


class _WithoutGetKline(Strategy):
    """不用 get_kline，直接用 self.kline（= 第一条 K 线 ✓）。"""
    def __init__(self):
        self.ma = self.kline.close.sma(5)

    def next(self):
        pass


def test_calls_get_kline_detection():
    assert catalog.calls_get_kline(_WithGetKline) is True
    assert catalog.calls_get_kline(_WithoutGetKline) is False

def test_calls_get_kline_ignores_comments(tmp_path):
    """注释掉的 ``self.get_kline(...)`` 不算调用（用户策略踩过）✓。"""
    import importlib.util

    path = tmp_path / 'commented_get_kline.py'
    path.write_text(textwrap.dedent('''
        from minibt import Strategy

        class S(Strategy):
            def __init__(self):
                # self.data = self.get_kline("SHFE.rb2610")
                self.ma = self.kline.close.sma(20)

            def next(self):
                pass
    '''), encoding='utf-8')
    spec = importlib.util.spec_from_file_location('commented_get_kline', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert catalog.calls_get_kline(module.S) is False


def test_runner_seed_kline_without_get_kline():
    """场景 1：不调 get_kline → seed_kline=True 注一条默认 K 线，self.kline 可用 ✓。"""
    runner = _runner_mod.StrategyRunner(_WithoutGetKline, cycle=60)
    runner.prepare([_sample_frame()], seed_kline=True)
    assert runner.kline_count == 1
    assert runner.specs(0)                       # 指标算出来了 ✓

GOOD_STRATEGY = textwrap.dedent('''
    from minibt import Strategy

    class MyStrategy(Strategy):
        """我的测试策略"""
        def __init__(self):
            self.kline = self.get_kline("SHFE.rb2610")
        def next(self):
            pass
''')

NO_NEXT = textwrap.dedent('''
    from minibt import Strategy

    class NoNext(Strategy):
        def __init__(self):
            self.kline = self.get_kline("SHFE.rb2610")
''')


# ---- 静态校验 --------------------------------------------------------------
def test_analyze_strategy_ok():
    result = catalog.analyze_strategy(GOOD_STRATEGY, path='my.py')
    assert result.ok
    name, cls = result.classes[0]
    assert name == 'MyStrategy'
    ok, reason = catalog.is_loadable_strategy(cls)
    assert ok and reason == ''


def test_analyze_strategy_syntax_error_has_lineno():
    result = catalog.analyze_strategy('def broken(:\n    pass\n', path='b.py')
    assert not result.ok
    assert result.error_lineno > 0
    assert '语法错误' in result.error


def test_analyze_strategy_missing_is_not_error():
    result = catalog.analyze_strategy('x = 1\n', path='plain.py')
    assert not result.ok and result.missing


def test_is_loadable_strategy_rejects():
    assert not catalog.is_loadable_strategy(str)[0]
    result = catalog.analyze_strategy(NO_NEXT, path='no_next.py')
    assert result.ok                                  # 识别得到
    ok, reason = catalog.is_loadable_strategy(result.classes[0][1])
    assert not ok and 'next' in reason


def test_single_kline_runtime_check():
    import types

    good = types.SimpleNamespace(_btklinedataset=types.SimpleNamespace(num=1))
    assert catalog.is_single_kline_strategy(good) == (True, '')
    multi = types.SimpleNamespace(_btklinedataset=types.SimpleNamespace(num=2))
    ok, reason = catalog.is_single_kline_strategy(multi)
    assert not ok and '2' in reason
    assert not catalog.is_single_kline_strategy(object())[0]


# ---- 系统策略 --------------------------------------------------------------
def test_system_strategies_lists_mystrategy():
    entries = catalog.system_strategies()
    names = {(e['group'], e['name']) for e in entries}
    assert ('mystrategy', 'SmaCrossStrategy') in names
    entry = next(e for e in entries if e['name'] == 'SmaCrossStrategy')
    assert entry['kind'] == 'strategy'
    assert entry['category'] == catalog.SYSTEM_CATEGORY == '交易策略'
    assert entry['doc'] and not entry['doc'].startswith('#')
    assert entry['loadable'] is True


# ---- 个人策略（我的策略）---------------------------------------------------
def test_personal_strategy_directory_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, 'PERSONAL_CONFIG_FILE',
                        str(tmp_path / 'ps.json'), raising=False)
    folder = tmp_path / 'mystrat'
    folder.mkdir()
    (folder / 's1.py').write_text(GOOD_STRATEGY, encoding='utf-8')

    info = catalog.add_personal_strategy_directory(str(folder))
    assert info['category'] == 'mystrat'
    assert info['classes'] and info['classes'][0][0] == 'MyStrategy'

    loaded = catalog.personal_strategies()
    assert 'mystrat' in loaded
    entry = loaded['mystrat'][0]
    assert entry['category'] == '我的策略'
    assert entry['kind'] == 'strategy'

    assert catalog.remove_personal_strategy_directory('mystrat') is True
    assert catalog.personal_strategies() == {}


# ---- 指标界面左导航（P2 壳）-----------------------------------------------
@pytest.fixture
def owner():
    from PyQt6.QtWidgets import QWidget

    class FakeOwner(QWidget):
        def __init__(self):
            super().__init__()
            self.resize(1000, 700)
            self.added_strategies = []

        def topbar_indicator_entries(self):
            return [{'group': 'TaLib', 'name': 'CCI', 'doc': '顺势指标'},
                    {'group': 'TaLib', 'name': 'SMA', 'doc': '简单均线'}]

        def topbar_add_strategy(self, entry):
            self.added_strategies.append(dict(entry))

    return FakeOwner()


def _nav_item(dialog, key):
    for row in range(dialog.navList.count()):
        item = dialog.navList.item(row)
        if item.data(Qt.ItemDataRole.UserRole) == key:
            return item
    raise AssertionError(key)


def test_picker_nav_has_strategy_categories(owner):
    dialogs = pytest.importorskip(
        'miniqt.app.windows.tradingview_indicator_dialogs')
    dialog = dialogs.IndicatorPickerDialog(
        entries=owner.topbar_indicator_entries(), favorites=[], parent=owner)
    labels = [dialog.navList.item(i).text().strip()
              for i in range(dialog.navList.count())]
    assert '交易策略' in labels            # 内置指标下 ✓
    assert '我的策略' in labels            # 我的脚本下方 ✓


def test_picker_nav_categories_are_indented(owner):
    dialogs = pytest.importorskip(
        'miniqt.app.windows.tradingview_indicator_dialogs')
    dialog = dialogs.IndicatorPickerDialog(
        entries=owner.topbar_indicator_entries(), favorites=[], parent=owner)

    def raw(label):
        for i in range(dialog.navList.count()):
            item = dialog.navList.item(i)
            if item.text().strip() == label:
                return item
        raise AssertionError(label)

    # 类别标题（个人 / 内置指标 / 我的脚本 / 我的策略 / 交易策略）左对齐；
    # 类别里的可点项（收藏 / mystrategy …）缩进 ✓
    for header in ('个人', '内置指标', '我的脚本', '我的策略', '交易策略'):
        assert not raw(header).text().startswith(dialogs.NAV_INDENT), header
        assert raw(header).flags() == Qt.ItemFlag.NoItemFlags, header
    for item in ('收藏', 'TaLib', 'mystrategy'):
        assert raw(item).text().startswith(dialogs.NAV_INDENT), item
        assert raw(item).flags() != Qt.ItemFlag.NoItemFlags, item


def test_picker_select_strategy_marks_kind(owner):
    dialogs = pytest.importorskip(
        'miniqt.app.windows.tradingview_indicator_dialogs')
    dialog = dialogs.IndicatorPickerDialog(
        entries=owner.topbar_indicator_entries(), favorites=[], parent=owner)
    dialog.navList.setCurrentItem(_nav_item(dialog, 'strategy:mystrategy'))
    assert dialog.indicatorList.count() >= 1
    dialog._on_add(dialog.indicatorList.item(0))
    entry = dialog.selected_entry()
    assert entry and entry['kind'] == 'strategy'
    assert entry['name'] == 'SmaCrossStrategy'


def test_topbar_request_strategy_routes_to_owner(owner):
    topbar = pytest.importorskip('miniqt.app.windows.tradingview_topbar')
    bar = topbar.TradingViewTopBar(owner, owner)
    bar.request_strategy({'group': 'mystrategy', 'name': 'SmaCrossStrategy',
                          'kind': 'strategy', 'cls': object})
    assert owner.added_strategies
    assert owner.added_strategies[0]['name'] == 'SmaCrossStrategy'


def test_favorites_menu_has_add_personal_strategy(owner):
    topbar = pytest.importorskip('miniqt.app.windows.tradingview_topbar')
    bar = topbar.TradingViewTopBar(owner, owner)
    texts = [a.text() for a in bar._build_favorites_menu().actions()
             if a.text()]
    assert '添加个人指标…' in texts
    assert '添加个人策略…' in texts
    assert texts.index('添加个人策略…') > texts.index('更多指标和策略…')


def test_window_add_strategy_is_a_shell():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    # 非法 / 空参数直接返回 None，不炸 ✓
    assert window.add_strategy_to_chart({'name': '', 'cls': None}) is None
    assert window.topbar_add_strategy({'name': 'X', 'cls': int}) is None


# ---- 策略真正加载到图表（P1）---------------------------------------------
def _sample_frame(periods: int = 80):
    import numpy as np
    import pandas as pd
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=periods, freq='min'),
        'open': np.linspace(1, 2, periods),
        'high': np.linspace(1.1, 2.1, periods),
        'low': np.linspace(0.9, 1.9, periods),
        'close': np.linspace(1, 2, periods)
        + np.sin(np.arange(periods) / 5) * 0.1,
        'volume': np.ones(periods) * 10,
    })


class _FakeSeries:
    def __init__(self):
        self.frames = []
        self.deleted = False
        self.pinned = False

    def set(self, frame):
        self.frames.append(frame)

    def delete(self):
        self.deleted = True

    def prefer_single_gap(self, value=True):
        pass

    def pin_legend_row(self, value=True):
        self.pinned = bool(value)


class _FakeStrategyChart:
    def __init__(self, chart_id='strat1'):
        self.id = chart_id
        self.series = []
        self.panes = []
        self.removed_panes = []

    def add_pane(self):
        self.panes.append(len(self.panes) + 1)
        return self.panes[-1]

    def remove_pane(self, pane):
        self.removed_panes.append(pane)

    def create_line(self, name, **kwargs):
        series = _FakeSeries()
        series.name = name
        self.series.append(series)
        return series

    def create_histogram(self, name, **kwargs):
        return self.create_line(name, **kwargs)

    def pane_add_series(self, pane, kind, **kwargs):
        name = kwargs.pop('name', kind)
        return self.create_line(name, **kwargs)

    def add_custom_series(self, name='', **kwargs):
        series = _FakeSeries()
        series.name = name
        self.series.append(series)
        return series


def test_window_loads_strategy_and_steps():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    entry = next(e for e in catalog.system_strategies()
                 if e['name'] == 'SmaCrossStrategy')
    window = window_module.PylightchartsChartWindow()
    chart = _FakeStrategyChart()
    window.chart = chart
    window.panels = lambda: [chart]
    window.contracts = ['SHFE.rb2610']
    frame = _sample_frame()
    window.panel_frames[chart.id] = frame
    window.last_panel = chart

    record = window.add_strategy_to_chart(entry)
    assert record is not None
    assert record['strategy']._btklinedataset.num == 1      # 单 K 线 ✓
    window._draw_strategy(record)                         # 延后画：手动触发一拍 ✓
    assert record['plots'][0]['series']                  # 画出了指标线 ✓
    assert all(series.frames
               for series in record['plots'][0]['series'].values())
    assert window.panel_strategy() is record

    # 同名策略 → **替换**（重新加载 = 先删旧再挂新 ✓）；不同名才被拒
    again = window.add_strategy_to_chart(entry)
    assert again is not None and again.get('id') != record.get('id')
    assert len(window._panel_strategies) == 1
    record = again                       # 后面的断言跟着**新**记录走 ✓
    window._draw_strategy(record)

    # 每拍推进：先来一次（sig 变化）→ stepped>=1；同一帧再跑不重复 ✓
    assert window._step_panel_strategies() >= 1
    assert window._step_panel_strategies() == 0
    # 刷新后指标线再 set 过一次（plot_id 不漂移 → 真的会更新 ✓）
    assert len(next(iter(record['plots'][0]['series'].values())).frames) >= 2

    # 新的一根 → 再推进 ✓
    import pandas as pd
    new_row = frame.iloc[[-1]].copy()
    new_row['time'] = frame['time'].iloc[-1] + pd.Timedelta(minutes=1)
    window.panel_frames[chart.id] = pd.concat(
        [frame, new_row], ignore_index=True)
    assert window._step_panel_strategies() >= 1

    # 删除策略：线被删、记录没了 ✓
    series_list = list(record['plots'][0]['series'].values())
    assert window.remove_strategy(record['id']) is True
    assert window.panel_strategy() is None
    assert all(series.deleted for series in series_list)
    assert window.remove_strategy(record['id']) is False


def _trade_strategy_cls():
    from minibt import Strategy

    class TradeStrategy(Strategy):
        """测试用：空仓就买一手"""
        def __init__(self):
            self.kline = self.get_kline('SHFE.rb2610')

        def next(self):
            if not self.kline.position.pos:
                self.kline.buy()

    return TradeStrategy


def test_window_strategy_position_line(monkeypatch):
    """P2：策略模拟持仓画成副图阶梅线（默认关，需 MINIQT_STRATEGY_POSITION=1 ✓）。"""
    monkeypatch.setenv('MINIQT_STRATEGY_POSITION', '1')
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    chart = _FakeStrategyChart()
    window.chart = chart
    window.panels = lambda: [chart]
    window.contracts = ['SHFE.rb2610']
    frame = _sample_frame()
    window.panel_frames[chart.id] = frame
    window.last_panel = chart

    cls = _trade_strategy_cls()
    record = window.add_strategy_to_chart(
        {'group': 'test', 'name': 'TradeStrategy', 'cls': cls})
    assert record is not None
    assert record['runner'].position_size() == 0        # 还没跑 next

    assert window._step_panel_strategies() >= 1
    assert record['runner'].position_size() == 1        # 买入了 ✓
    assert record['plots'][0].get('pos_series') is not None   # 持仓副图已建 ✓
    assert record['plots'][0]['pos_series'].frames[-1][
        '策略持仓'].iloc[-1] == 1

    # 删除时持仓副图序列也删掉 ✓
    pos = record['plots'][0]['pos_series']
    assert window.remove_strategy(record['id']) is True
    assert pos.deleted


def test_window_strategy_persistence_roundtrip():
    """P3：策略落盘 → 清内存 → 重启恢复 ✓。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    from miniqt.app.common.chart_data import chart_data_manager
    entry = next(e for e in catalog.system_strategies()
                 if e['name'] == 'SmaCrossStrategy')
    window = window_module.PylightchartsChartWindow()
    chart = _FakeStrategyChart()
    window.chart = chart
    window.panels = lambda: [chart]
    window.contracts = ['SHFE.rb2610']
    frame = _sample_frame()
    window.panel_frames[chart.id] = frame
    window.last_panel = chart
    key = window._indicator_key(chart)
    try:
        record = window.add_strategy_to_chart(entry)
        assert record is not None
        specs = chart_data_manager.get_strategies(key)
        assert specs and specs[0]['name'] == 'SmaCrossStrategy'
        assert specs[0]['group'] == 'mystrategy'

        # 清内存记录 → 模拟重启后再加载 ✓
        window._panel_strategies.clear()
        assert window.panel_strategy(chart) is None
        assert window.load_strategies(chart, frame=frame) == 1
        restored = window.panel_strategy(chart)
        assert restored is not None
        assert restored['cls_name'] == 'SmaCrossStrategy'

        # 再删就把盘上的也清了 ✓
        window.remove_strategy(restored['id'])
        assert chart_data_manager.get_strategies(key) == []
    finally:
        for sid in [r.get('id') for r in
                    list(window._panel_strategies.values())]:
            window.remove_strategy(sid)


# ---- P4：多 K 线 / 多合约策略 -------------------------------------------
def _multi_strategy_cls():
    from minibt import Strategy

    class MultiStrategy(Strategy):
        """测试用：两个合约各一条均线（多 K 线 ✓）"""
        def __init__(self):
            self.k1 = self.get_kline('aaa2601')
            self.k2 = self.get_kline('bbb2601')
            self.ma1 = self.k1.close.sma(5)
            self.ma2 = self.k2.close.sma(5)

        def next(self):
            pass

    return MultiStrategy


def test_window_multi_kline_strategy_maps_panels():
    """P4：多 K 线策略按合约名映射到对应面板 ✓。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    c1 = _FakeStrategyChart('s1')
    c2 = _FakeStrategyChart('s2')
    window.chart = c1
    window.panels = lambda: [c1, c2]
    window.contracts = ['SHFE.aaa2601', 'DCE.bbb2601']
    window.panel_frames[c1.id] = _sample_frame()
    window.panel_frames[c2.id] = _sample_frame()
    window.last_panel = c1

    cls = _multi_strategy_cls()
    record = window.add_strategy_to_chart(
        {'group': 'test', 'name': 'MultiStrategy', 'cls': cls})
    assert record is not None
    assert record['runner'].kline_count == 2
    assert len(record['plots']) == 2
    assert {plot['chart_id'] for plot in record['plots']} == {'s1', 's2'}
    window._draw_strategy(record)                         # 延后画：手动触发一拍 ✓
    assert all(plot['series'] for plot in record['plots'])   # 两格都画了 ✓

    # 每拍推进（两个合约都更新）；策略记录在两格都能查到 ✓
    assert window._step_panel_strategies() >= 1
    assert window.panel_strategy(c1) is record
    assert window.panel_strategy(c2) is record
    # 多 K 线策略在多个 key 下，但只跑一次（值不会重复 step）✓
    assert window._step_panel_strategies() == 0

    # 删除 → 两格都清掉 ✓
    assert window.remove_strategy(record['id']) is True
    assert window.panel_strategy(c1) is None
    assert window.panel_strategy(c2) is None


# ---- 声明式 charts（兼容用法）-------------------------------------------
def test_declared_charts_parsing():
    from minibt import Strategy

    class Declared(Strategy):
        charts = [('SHFE.rb2610', 60), 'DCE.i2609', ('CZCE.SR', 0)]

        def __init__(self):
            pass

        def next(self):
            pass

    assert catalog.declared_charts(Declared) == [
        ('SHFE.rb2610', 60), ('DCE.i2609', 0), ('CZCE.SR', 0)]

    class Plain(Strategy):
        def __init__(self):
            pass

        def next(self):
            pass

    assert catalog.declared_charts(Plain) == []


def test_runner_specs_stable_after_advance():
    """反复 ``_strategy_init`` 后指标 plot_id 不能漂移（否则图表不刷新 ✓）。"""
    runner_mod = pytest.importorskip('miniqt.app.common.strategy_runner')
    entry = next(e for e in catalog.system_strategies()
                 if e['name'] == 'SmaCrossStrategy')
    runner = runner_mod.StrategyRunner(entry['cls'], cycle=60)
    runner.prepare([_sample_frame(80)])
    first = [spec.name for spec in runner.specs(0)]
    assert first                                     # 初始就有指标 ✓
    for extra in (81, 82):
        assert runner.advance([_sample_frame(extra)]) is True
        specs = runner.specs(0)
        assert [spec.name for spec in specs] == first
        # 指标长度要跟着帧增长（否则画线长度不一致 → 报错/不刷新 ✗）
        assert len(specs[0].values) == extra


def _declared_multi_cls():
    from minibt import Strategy

    class DeclaredMulti(Strategy):
        """声明式多合约：get_kline 不写合约名，靠 charts 决定 ✓"""
        charts = [('SHFE.aaa2601', 0), ('DCE.bbb2601', 0)]

        def __init__(self):
            self.k1 = self.get_kline()
            self.k2 = self.get_kline()
            self.ma1 = self.k1.close.sma(5)
            self.ma2 = self.k2.close.sma(5)

        def next(self):
            pass

    return DeclaredMulti


def test_window_declared_charts_maps_panels():
    """声明式 charts：合约名匹配面板，即使 get_kline 不写合约名 ✓。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    c1 = _FakeStrategyChart('d1')
    c2 = _FakeStrategyChart('d2')
    window.chart = c1
    window.panels = lambda: [c1, c2]
    window.contracts = ['SHFE.aaa2601', 'DCE.bbb2601']
    window.panel_frames[c1.id] = _sample_frame()
    window.panel_frames[c2.id] = _sample_frame()
    window.last_panel = c2                     # 目标格是第二格

    cls = _declared_multi_cls()
    record = window.add_strategy_to_chart(
        {'group': 'test', 'name': 'DeclaredMulti', 'cls': cls})
    assert record is not None
    assert record['runner'].kline_count == 2
    assert [p['chart_id'] for p in record['plots']] == ['d1', 'd2']
    assert record['runner'].declared == [
        ('SHFE.aaa2601', 0), ('DCE.bbb2601', 0)]
    assert window.remove_strategy(record['id']) is True


def test_editor_candidates_walks_workspace(tmp_path):
    """DOM 反查失败时，``_editor_candidates`` 仍能在 workspace 下找到同名文件 ✓。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    wrong = tmp_path / 'test.py'
    wrong.write_text('x = 1\n', encoding='utf-8')
    right = tmp_path / 'sub' / 'test.py'
    right.parent.mkdir(parents=True)
    right.write_text('from minibt import Strategy\n', encoding='utf-8')

    class _Page:
        workspace = str(tmp_path)

    window._code_editor_page = _Page()
    candidates = window._editor_candidates(str(wrong))
    assert str(right) in candidates
    assert str(wrong) not in candidates


def test_set_contracts_per_panel_cycles():
    """多合约策略可以**每格不同周期**（由 get_kline 传递 ✓）。"""
    import types
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow

    window = types.SimpleNamespace(
        contracts=[], _panel_cycles=[], panel_frames={},
        refresh_topbar=lambda: None, data_provider=None,
        cycle=60, length=1000)
    W.set_contracts(window, ['SHFE.rb2610', 'DCE.i2609'],
                    cycles=[60, 300])
    assert window.contracts == ['SHFE.rb2610', 'DCE.i2609']
    assert window._panel_cycles == [60, 300]
    # 传 cycles=None → 清空（回到全局周期 ✓）
    W.set_contracts(window, ['SHFE.rb2610', 'DCE.i2609'])
    assert window._panel_cycles == []


def test_editor_falls_back_to_same_name_candidate(tmp_path):
    """同名文件反查选错时，应回退到**含策略**的那个 ✓（用户报的 test.py 案例）。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window = window_module.PylightchartsChartWindow()
    chart = _FakeStrategyChart('fb1')
    window.chart = chart
    window.panels = lambda: [chart]
    window.contracts = ['SHFE.rb2610']
    window.panel_frames[chart.id] = _sample_frame()
    window.last_panel = chart

    # 根目录的 test.py **没有**策略；子目录的 test.py 有 ✓
    wrong = tmp_path / 'test.py'
    wrong.write_text('x = 1\n', encoding='utf-8')
    right = tmp_path / 'sub' / 'test.py'
    right.parent.mkdir(parents=True)
    right.write_text(textwrap.dedent('''
        from minibt import Strategy

        class MyStrat(Strategy):
            def __init__(self):
                self.k = self.get_kline('')
                self.ma = self.k.close.sma(5)

            def next(self):
                pass
    '''), encoding='utf-8')

    class _Page:
        def active_candidates(self):
            return [str(wrong), str(right)]

    window._code_editor_page = _Page()
    added = window.add_strategy_from_editor(str(wrong))
    assert added == ['MyStrat']
    assert window.panel_strategy(chart) is not None


# ---- 策略合约取不到数据：单合约回落 / 多合约取消 -------------------------
class _FakeMarket:
    """假看盘窗口：只实现 ``compare_frame``（``fallback=False`` 的探测 ✓）。"""

    def __init__(self, frame=None):
        self.frame = frame
        self.calls = []

    def compare_frame(self, symbol, type_str='', cycle=None, length=None):
        self.calls.append((symbol, cycle))
        return self.frame


def test_has_contract_probe():
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    host = types.SimpleNamespace(market_watch=None)
    assert W._has_contract_probe(host) is False         # 没接看盘窗口
    host.market_watch = _FakeMarket(frame=_sample_frame())
    assert W._has_contract_probe(host) is True


def test_start_contract_probe_without_channel_is_synchronous():
    """没探测通道（离屏 / 测试）→ 直接同步回调全部 True，不拉线程 ✓。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    host = types.SimpleNamespace(market_watch=None, length=0,
                                 _has_contract_probe=lambda: False)
    seen = []
    W._start_contract_probe(host, [('X', 60)], lambda r: seen.append(r))
    assert seen == [[('X', 60, True)]]


def test_contract_key_normalization():
    """合约代码归一化：去周期后缀 / 交易所前缀，大写 ✓。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    key = window_module.PylightchartsChartWindow._contract_key
    assert key('SHFE.rb2610') == 'RB2610'
    assert key('rb2610') == 'RB2610'
    assert key('rb2610_60') == 'RB2610'
    assert key('KQ.m@SHFE.rb') == 'RB'
    assert key('') == ''


def test_quote_has_contract_searches_all_markets():
    """二级报价表搜**全部**合约：所有类型 / 所有交易所 / 股票都能查到 ✓。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    host = types.SimpleNamespace()
    host._contract_key = W._contract_key
    host._quote_contract_keys = types.MethodType(W._quote_contract_keys,
                                                 host)
    host._quote_key_cache = None
    host.topbar_search_rows = lambda: [
        ['SHFE.rb2610', '螺纹钢', 'FUTURES', 'SHFE'],
        ['000001', '平安银行', 'STOCK', 'SZ'],
        ['KQ.m@DCE.i', '铁矿石主连', 'CONT', 'DCE'],
    ]
    # 期货 / 股票 / 主连都不分市场地查到 ✓
    assert W._quote_has_contract(host, 'rb2610') is True
    assert W._quote_has_contract(host, 'SZ.000001') is True
    assert W._quote_has_contract(host, '000001') is True
    assert W._quote_has_contract(host, 'i') is True
    assert W._quote_has_contract(host, 'zzz2699') is False


def test_quote_mode_rejects_missing_instantly():
    """quote 模式：本地表里都找不到 → 直接回不合法，**不拉后台线程** ✓。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    host = types.SimpleNamespace(
        _has_contract_probe=lambda: True,
        _contract_check_mode=lambda: 'quote',
        _quote_contract_keys=lambda: {'RB2610'},   # 本地表非空 → 走快筛
        _quote_has_contract=lambda symbol: False,
    )
    seen = []
    W._start_contract_probe(host, [('zzz2699', 60)],
                            lambda r: seen.append(r))
    assert seen == [[('zzz2699', 60, False)]]


def test_quote_mode_empty_table_falls_back_to_fetch(monkeypatch):
    """本地合约表为空 → 不即时判死，退回取数确认 ✓。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow

    class _Sig:
        def connect(self, fn):
            self.fn = fn

    class _FakeTimer:
        def __init__(self, *a, **k):
            self.timeout = _Sig()

        def setInterval(self, ms):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def deleteLater(self):
            pass

    class _FakeWorker:
        def __init__(self, market, jobs, length, parent=None):
            self.jobs = list(jobs)

        def start(self):
            pass

        def isFinished(self):
            return False

        def results(self):
            return []

        def deleteLater(self):
            pass

    monkeypatch.setattr(window_module, 'QTimer', _FakeTimer)
    monkeypatch.setattr(window_module, '_ContractProbeWorker', _FakeWorker)

    def _boom(symbol):
        raise AssertionError('空表时不该调用 _quote_has_contract ✗')

    host = types.SimpleNamespace(
        market_watch=_FakeMarket(frame=_sample_frame()),
        length=1000, _compare_workers=[],
        _has_contract_probe=lambda: True,
        _contract_check_mode=lambda: 'quote',
        _quote_contract_keys=lambda: set(),          # 空表
        _quote_has_contract=_boom,
        _pause_compare_realtime=lambda: None,
        _pause_tq_qtimer=lambda: None,
        _resume_tq_qtimer=lambda: None,
        _force_resume_compare=lambda: None,
    )
    seen = []
    W._start_contract_probe(host, [('zzz2699', 60)],
                            lambda r: seen.append(r))
    assert seen == []                    # 不即时拒绝 ✓
    assert host._compare_workers         # 起了后台确认 ✓
    assert host._compare_workers[0].jobs == [('zzz2699', 60)]


def test_contract_check_mode_default_is_quote():
    """默认校验方式是从二级报价里检索（设置项默认值 ✓）。"""
    cfg_mod = pytest.importorskip('miniqt.app.common.chart_config')
    assert cfg_mod.ChartConfig.DEFAULT_CONFIG['ContractCheckMode'] == 'quote'
    assert cfg_mod.chart_cfg.contractCheckMode.value in ('quote', 'server')


def test_contract_check_setting_card_wired():
    """设置-数据设置-数据源里确实挂了「合约校验方式」下拉（源码级检查 ✓）。"""
    import pathlib

    setting = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt'
               / 'app' / 'view' / 'setting_interface.py').read_text(
                   encoding='utf-8')
    assert 'chart_cfg.contractCheckMode' in setting
    assert 'self.dataSourceGroup.addSettingCard(self.contractCheckCard)' \
        in setting
    assert '从二级报价里检索' in setting and '从服务' in setting


def test_probe_contracts_logic():
    """探测纯逻辑：取到/取不到都不抛异常 → ``(symbol, cycle, ok)`` ✓。"""
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    probe = window_module.probe_contracts
    assert probe(_FakeMarket(frame=_sample_frame()),
                 [('X', 60), ('Y', 300)], None) == [
        ('X', 60, True), ('Y', 300, True)]
    # 取不到数据 → ok=False（不是异常 ✓）
    assert probe(_FakeMarket(frame=None), [('Z', 60)], None) == [
        ('Z', 60, False)]
    # 空帧也算取不到 ✓
    assert probe(_FakeMarket(frame=_sample_frame(0)), [('Z', 60)], None) == [
        ('Z', 60, False)]


def test_single_switch_probes_in_background():
    """单合约策略切合约前也会走**后台**探测（`_start_contract_probe` ✓）。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    host = types.SimpleNamespace(_has_contract_probe=lambda: True)
    jobs_seen = []
    host._start_contract_probe = \
        lambda jobs, callback: jobs_seen.append((list(jobs), callback))
    record = W._switch_and_attach_single(
        host, {'name': 'SingleStrategy'}, object(), 'SHFE.rb2610', 60, 'T')
    # 返回 pending 占位（异步）✓，且确实把探测丢给了后台 ✓
    assert record.get('pending') is True
    assert jobs_seen and jobs_seen[0][0] == [('SHFE.rb2610', 60)]


def test_single_strategy_falls_back_when_contract_unfetchable():
    """单合约策略的合约取不到数据 → **回落到当前图表合约**，不切图 ✓。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    host = types.SimpleNamespace()
    host.period_label = W.period_label
    host._panel_symbol = lambda chart: 'SHFE.rb2610'
    host._script_notify = lambda *a, **k: None
    switched, fell_back = [], []
    host._do_switch_and_attach_single = \
        lambda *a, **k: switched.append(a) or 'switched'
    host._attach_single_strategy = \
        lambda *a, **k: fell_back.append(a) or 'fallback'
    target = object()
    # 后台探测结果：zzz2699 取不到 → 不切图，回落当前图表 ✓
    result = W._apply_single_strategy_probe(
        host, {'name': 'SingleStrategy'}, object(), 'zzz2699', 60, target,
        [('zzz2699', 60, False)])
    assert result == 'fallback'
    assert not switched and len(fell_back) == 1
    # 回落用的是当前目标格，不是 zzz2699 ✓
    assert fell_back[0][2] is target


def test_multi_strategy_aborts_when_contract_unfetchable():
    """多合约策略任一合约取不到数据 → 提示并**不加载 / 不切布局** ✓。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    host = types.SimpleNamespace()
    host.period_label = W.period_label
    host._script_notify = lambda *a, **k: None
    host._do_add_multi_contract_strategy = \
        lambda *a, **k: pytest.fail('取不到数据时不应该切布局 ✗')
    requests = [('aaa2601', 60), ('bbb2601', 60)]
    record = W._apply_multi_strategy_probe(
        host, {'name': 'MultiStrategy'}, object(), requests, object(),
        [('aaa2601', 60, False), ('bbb2601', 60, False)])
    assert record is not None and record.get('failed') is True
    # 取到数据时才继续 ✓
    host._do_add_multi_contract_strategy = lambda *a, **k: {'id': 1}
    record2 = W._apply_multi_strategy_probe(
        host, {'name': 'MultiStrategy'}, object(), requests, object(),
        [('aaa2601', 60, True), ('bbb2601', 60, True)])
    assert record2 == {'id': 1}


# ---- 「移除指标」菜单：序号从 1 + 编辑器短名 ----------------------------
def test_remove_menu_titles_use_index_and_editor_alias():
    """菜单行 = ``序号  组.指标``；组名 ``active_editor`` 显示成 ``editor`` ✓。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    host = types.SimpleNamespace(EDITOR_GROUP_NAME='active_editor',
                                 EDITOR_GROUP_ALIAS='editor')
    host._menu_group_name = types.MethodType(W._menu_group_name, host)
    adx = types.SimpleNamespace(indicator_cls='PandasTa',
                                name='adx')
    utbot = types.SimpleNamespace(indicator_cls='active_editor',
                                  name='UT_Bot_Alerts')
    # 系统指标名称不变；编辑器指标前缀显示成 editor；不再带 # ✓
    assert W._indicator_menu_title(host, 1, adx) == '1  PandasTa.adx'
    assert W._indicator_menu_title(host, 2, utbot) == \
        '2  editor.UT_Bot_Alerts'
    # 组名映射
    assert W._menu_group_name(host, 'active_editor') == 'editor'
    assert W._menu_group_name(host, 'PandasTa') == 'PandasTa'
    # 策略标题（编辑器短名）
    assert W._strategy_menu_title(
        host, {'group': 'active_editor', 'cls_name': 'CCIStrategy'}) == \
        '删除交易策略：editor.CCIStrategy'
    assert W._strategy_menu_title(
        host, {'group': 'mystrategy', 'cls_name': 'SmaCross'}) == \
        '删除交易策略：mystrategy.SmaCross'


def test_remove_indicator_menu_renumbers_remaining():
    """删掉前面几个后，菜单序号按**当前剩余指标**重新从 1 排（不用内部 id）✓。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    W = window_module.PylightchartsChartWindow
    host = types.SimpleNamespace(EDITOR_GROUP_NAME='active_editor',
                                 EDITOR_GROUP_ALIAS='editor')
    host._menu_group_name = types.MethodType(W._menu_group_name, host)
    remain = [types.SimpleNamespace(id=7, indicator_cls='PandasTa', name='i7'),
              types.SimpleNamespace(id=9, indicator_cls='active_editor',
                                    name='i9'),
              types.SimpleNamespace(id=12, indicator_cls='PandasTa', name='i12')]
    texts = [W._indicator_menu_title(host, index, indicator)
             for index, indicator in enumerate(remain, start=1)]
    assert texts == ['1  PandasTa.i7', '2  editor.i9', '3  PandasTa.i12']
    # 内部 id（7/9/12）不再出现在标题里 ✓
    assert all('#' not in text for text in texts)


def test_indicator_signal_detection():
    """静态识别 BtIndicator 子类 + 「至少一个方向入场+出场」的信号检查 ✓。"""
    code = textwrap.dedent('''
        from minibt import *

        class MyMA(BtIndicator):
            data = LocalDatas.test
            lines = ['ma1', 'ma2', 'long_signal', 'short_signal',
                     'exitlong_signal', 'exitshort_signal']
            params = dict(length1=10, length2=20)
            def next(self): ...

        class OnlyLongEntry(BtIndicator):
            lines = ['long_signal']
            def next(self): ...

        class MyStrategy(Strategy):
            op_config = OpConfig(params=dict(a=(1, 5)))
            def next(self): ...
    ''')
    assert catalog.btindicator_class_names(code) == ['MyMA', 'OnlyLongEntry']
    # 只有入场、没出场 → 不算可优化 ✓
    assert catalog.optimizable_indicator_names(code) == ['MyMA']
    assert catalog.indicator_class_has_op_config(code, 'MyMA') is False
    assert catalog.indicator_param_defaults(code, 'MyMA') == {
        'length1': '10', 'length2': '20'}
    assert catalog.indicator_param_names(code, 'MyMA') == [
        'length1', 'length2']


def test_indicator_op_config_detection():
    """指标类写了 op_config 就不再弹窗（方案 A）✓。"""
    code = textwrap.dedent('''
        from minibt import *

        class S(BtIndicator):
            lines = ['long_signal', 'exitlong_signal']
            params = dict(n=5)
            op_config = OptimizeConfig(params=dict(n=(1, 9, 1)),
                                       target='sharpe')
            def next(self): ...
    ''')
    assert catalog.optimizable_indicator_names(code) == ['S']
    assert catalog.indicator_class_has_op_config(code, 'S') is True
