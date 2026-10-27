"""脚本指标（代码编辑器「添加到当前图表」）的检测 / 识别测试 ✓。

``script_indicator`` 是纯逻辑（``ast`` + ``exec``），不碰 Qt，所以离屏也能跑 ✓。
"""
from __future__ import annotations

import inspect
import os
import textwrap

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

si = pytest.importorskip('miniqt.app.common.script_indicator')

GOOD = textwrap.dedent('''
    """我的测试指标 ✓"""
    from minibt import BtIndicator

    class MyTestInd(BtIndicator):
        """测试用 BtIndicator ✓"""
        params = {'period': 14}
        lines = ('ma', 'sig')
        overlap = True

        def next(self, period=14):
            return self.close, self.close
''')

ALIASED = textwrap.dedent('''
    from minibt import BtIndicator as BtInd

    class AliasedInd(BtInd):
        params = {'length': 9}
        def next(self, length=9):
            return self.close
''')

SYNTAX_ERROR = 'x = 1\nclass Broken(BtIndicator)\n    pass\n'
RUNTIME_ERROR = textwrap.dedent('''
    from minibt import BtIndicator

    class RuntimeInd(BtIndicator):
        pass

    raise RuntimeError('导入阶段就炸了')
''')
NO_INDICATOR = textwrap.dedent('''
    def helper(a, b):
        return a + b
''')


def test_good_script_is_detected_and_registered():
    result = si.check_script(GOOD, path='/tmp/MyScript.py')
    assert result.ok, result.error
    assert result.names == ['MyTestInd']
    assert result.group == 'MyScript'
    assert result.error == '' and result.error_lineno == 0
    assert result.message() == 'MyTestInd'
    # 注册成脚本组，indicator_holder 之后就能按组名取 ✓
    assert result.group in si.script_group_names()
    assert si.get_script_group(result.group) is not None


def test_holder_group_matches_tradingview_shape():
    result = si.check_script(GOOD, path='/tmp/MyScript.py')
    holder = si.get_script_group(result.group)
    instance = holder(None)
    method = getattr(instance, 'MyTestInd')
    # 和 minibt 的 TradingView 组一样：Group(kline).Name(**params) ✓
    assert inspect.signature(method).parameters == {
        'period': inspect.Parameter('period',
                                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                    default=14)}
    assert (method.__doc__ or '').startswith('测试用 BtIndicator')
    assert si.params_of(result.classes[0][1]) == {'period': 14}


def test_aliased_import_is_detected():
    result = si.check_script(ALIASED, path='/tmp/Aliased.py')
    assert result.ok, result.error
    assert result.names == ['AliasedInd']


def test_syntax_error_reports_lineno():
    result = si.check_script(SYNTAX_ERROR, path='/tmp/Broken.py')
    assert not result.ok
    assert result.error_lineno == 2
    assert '语法错误' in result.error
    assert result.message().startswith('第 2 行')


def test_runtime_error_is_reported():
    result = si.check_script(RUNTIME_ERROR, path='/tmp/Boom.py')
    assert not result.ok
    assert '代码执行失败' in result.error
    assert 'RuntimeError' in result.error


def test_no_btindicator_gives_hint():
    result = si.check_script(NO_INDICATOR, path='/tmp/Helper.py')
    assert not result.ok
    assert 'BtIndicator' in result.error
    assert not result.classes


def test_empty_code_is_rejected():
    result = si.check_script('   \n', path='/tmp/Empty.py')
    assert not result.ok
    assert '没有代码' in result.error


def test_private_base_class_is_skipped():
    code = textwrap.dedent('''
        from minibt import BtIndicator

        class _Base(BtIndicator):
            pass

        class Real(BtIndicator):
            params = {}
            def next(self):
                return self.close
    ''')
    result = si.check_script(code, path='/tmp/Private.py')
    assert result.ok, result.error
    assert result.names == ['Real']


def test_group_name_falls_back_to_default():
    assert si.group_name_for('') == '脚本指标'
    assert si.group_name_for('/tmp/abc.py') == 'abc'


def _sample_kline():
    """一份最小的 minibt ``KLine``（脚本指标直接就能算 ✓）。"""
    pd = pytest.importorskip('pandas')
    import minibt
    from minibt.indicators.core import FILED

    n = 40
    frame = pd.DataFrame({
        'datetime': pd.date_range('2024-01-01', periods=n, freq='min'),
        'open': [1 + i * 0.01 for i in range(n)],
        'high': [1.1 + i * 0.01 for i in range(n)],
        'low': [0.9 + i * 0.01 for i in range(n)],
        'close': [1 + i * 0.01 for i in range(n)],
        'volume': [1.0] * n,
    })
    return minibt.KLine(frame[list(FILED.ALL)])


def test_script_group_computes_a_plot():
    """端到端：``check_script`` → ``compute_indicator`` 能拿到可画的数据 ✓。"""
    dialog = pytest.importorskip('miniqt.app.windows.indicator_dialog')
    result = si.check_script(GOOD, path='/tmp/MyScript.py')
    assert result.ok, result.error
    plot = dialog.compute_indicator(_sample_kline(), result.group,
                                    'MyTestInd', {'period': 5})
    assert plot['name'] == 'MyTestInd'
    groups = plot['groups']
    assert groups and list(groups[0]['lines']) == ['ma', 'sig']
    assert groups[0].get('overlap') is True


def test_unknown_group_returns_none_or_raises():
    dialog = pytest.importorskip('miniqt.app.windows.indicator_dialog')
    kline = _sample_kline()
    # 不存在的组 → ``indicator_holder`` 返回 None → compute_indicator 报 AttributeError
    with pytest.raises(AttributeError):
        dialog.compute_indicator(kline, 'NoSuchGroup', 'Whatever', {})


# ---- 重启后按脚本文件重新注册（持久化 ✓）--------------------------------
def test_ensure_group_registers_after_restart(tmp_path):
    path = tmp_path / 'Persisted.py'
    path.write_text(GOOD, encoding='utf-8')
    result = si.check_script(GOOD, path=str(path))
    assert result.ok, result.error
    group = result.group
    si.SCRIPT_GROUPS.clear()                 # 模拟重启：注册表是空的 ✓
    assert si.get_script_group(group) is None
    again = si.ensure_group(str(path), group)
    assert again is not None and again.ok
    assert again.group == group
    assert si.get_script_group(group) is not None


def test_ensure_group_skips_when_already_registered(tmp_path):
    path = tmp_path / 'Once.py'
    path.write_text(GOOD, encoding='utf-8')
    result = si.check_script(GOOD, path=str(path))
    assert si.ensure_group(str(path), result.group) is None      # 已注册→不重读 ✓
    assert si.ensure_group(str(tmp_path / 'missing.py'), 'nope') is None
    assert si.ensure_group('', 'nope') is None


def test_window_persists_and_restores_the_script_path():
    """源码级：脚本指标要存 script_path，恢复时按它重新注册组 ✓。"""
    import pathlib

    window = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app'
              / 'windows' / 'pylightcharts_window.py')
    src = window.read_text(encoding='utf-8')
    assert "spec['script_path'] = script_path" in src
    assert 'script_indicator.ensure_group(script_path, group)' in src
    # 编辑器那条路：spec 里既有脚本路径 ✓，也有「图例开关」✓（后者在
    # `add_script_to_chart` 里从类的 `legend` 属性取，v1.2.18 ✓）
    assert "'script_path': path," in src
    assert "'legend': (bool(class_legend)" in src
    assert "indicator.script_path = str(" in src


def test_window_reloads_instead_of_adding_again():
    """源码级：同名指标再点一次要**重载**（替换）而不是又加一个 ✓。

    同一性以**指标名**为准（不看脚本文件 / 缓存文件名）→ 不同名可并存 ✓。
    """
    import pathlib

    window = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app'
              / 'windows' / 'pylightcharts_window.py')
    src = window.read_text(encoding='utf-8')
    assert 'previous = self._script_entries(target, check.names)' in src
    assert 'def _script_entries(self, target, names)' in src
    assert "verb = '已重载' if previous else '已添加'" in src
    assert 'script_indicator.merged_params(cls, saved.get(' in src
    # 重载要连旧副图一起收掉，否则会越重载越多空副图 ✗
    assert 'indicator.chart.remove_pane(pane_index)' in src


# ---- 重载时的参数合并 -----------------------------------------------------
def test_merged_params_keeps_user_values_for_kept_keys():
    class Ind:
        params = {'period': 14, 'src': 'close'}

    assert si.merged_params(Ind, {'period': 30}) == {'period': 30,
                                                     'src': 'close'}
    # 旧参数已经不在新代码里了 → 丢掉（再传会 TypeError ✗）
    assert si.merged_params(Ind, {'period': 30, 'gone': 1}) == {
        'period': 30, 'src': 'close'}
    # 新代码新加的参数用新默认值 ✓
    assert si.merged_params(Ind, {}) == {'period': 14, 'src': 'close'}


class _NoParams:
    pass


class _FreeParams:
    params = {}


def test_merged_params_falls_back_to_saved():
    assert si.merged_params(_NoParams, {'a': 1}) == {'a': 1}
    assert si.merged_params(_NoParams, None) == {}
    assert si.merged_params(_FreeParams, {'a': 1}) == {'a': 1}
    assert si.merged_params(_FreeParams, None) == {}


# ---- 重载的「找出旧指标」判定（真跑一遍 ✓）------------------------------
class _FakeIndicator:
    def __init__(self, name, group, script_path, params=None):
        self.name = name
        self.indicator_cls = group
        self.script_path = script_path
        self.params = params or {}


class _FakeHost:
    def __init__(self, entries):
        self.indicators = entries


def _entries():
    chart_a, chart_b = object(), object()
    return chart_a, chart_b, [
        {'chart': chart_a, 'indicator': _FakeIndicator(
            'adx', 'PandasTa_adx', 'C:/tmp/PandasTa_adx.py', {'p': 1})},
        {'chart': chart_a, 'indicator': _FakeIndicator(
            'sma', 'PandasTa_sma', 'C:/tmp/PandasTa_sma.py')},
        {'chart': chart_b, 'indicator': _FakeIndicator(
            'adx', 'PandasTa_adx', 'C:/tmp/PandasTa_adx.py')},
        # 内置指标：没有 script_path → 不能被当成脚本指标重载 ✗
        {'chart': chart_a, 'indicator': _FakeIndicator('CCI', 'TaLib', '')},
    ]


def _window_class():
    pytest.importorskip('PyQt6')
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    try:
        from miniqt.app.windows.pylightcharts_window import (
            PylightchartsChartWindow)
    except Exception as error:                               # pragma: no cover
        pytest.skip(f'看盘窗口不可用：{error!r}')
    return PylightchartsChartWindow


def test_script_entries_matches_by_indicator_name():
    """同一性看**指标名**：同名命中；不同名（含别的文件 / 组）不命中 ✓。"""
    window = _window_class()
    chart_a, _chart_b, entries = _entries()
    host = _FakeHost(entries)
    found = window._script_entries(host, chart_a, ['adx'])
    assert [item['indicator'].name for item in found] == ['adx']
    # 别的格子上那一份不算（各格各管各的 ✓）
    assert window._script_entries(host, object(), ['adx']) == []
    # 不存在的名字 / 空名字 → 空
    assert window._script_entries(host, chart_a, ['nope']) == []
    assert window._script_entries(host, chart_a, []) == []
    # 传单个字符串也行（都能找到同名那一条 ✓）
    assert [item['indicator'].name
            for item in window._script_entries(host, chart_a, 'sma')] == ['sma']
    # 多个名字一起找：不同名的指标全都列出来 ✓
    both = window._script_entries(host, chart_a, ['adx', 'sma'])
    assert sorted(item['indicator'].name for item in both) == ['adx', 'sma']


def test_script_entries_ignores_builtin_indicators():
    """内置指标（无 script_path）永远不参与重载（别被脚本指标误删 ✓）。"""
    window = _window_class()
    chart_a, _chart_b, entries = _entries()
    host = _FakeHost(entries)
    assert window._script_entries(host, chart_a, ['CCI']) == []


def test_script_entries_matches_same_name_across_scripts():
    """不同脚本文件 / 组，只要**名字相同**就算同一个 → 一起替换 ✓。"""
    window = _window_class()
    chart_a = object()
    entries = [{'chart': chart_a, 'indicator': _FakeIndicator(
        'sma', 'other_script', 'C:/else/other_script.py')}]
    host = _FakeHost(entries)
    found = window._script_entries(host, chart_a, ['sma'])
    assert [item['indicator'].indicator_cls for item in found] == [
        'other_script']


# ---- 组内按名合并（同名替换 / 不同名并存 ✓）-----------------------------
def test_merge_script_classes_keeps_different_names():
    """连续添加不同名指标：组里两个都留着；同名则用新类覆盖 ✓。"""
    from minibt import BtIndicator

    class Sma(BtIndicator):
        def next(self):
            return self.close

    class UtBot(BtIndicator):
        def next(self):
            return self.close

    class Sma2(BtIndicator):
        def next(self):
            return self.close

    group = 'miniqt_merge_test_group'
    try:
        si.merge_script_classes(group, [('Sma', Sma)])
        holder = si.get_script_group(group)
        assert hasattr(holder, 'Sma') and not hasattr(holder, 'UtBot')
        # 加一个**不同名**的 → 两个都在（可以连续添加 ✓）
        si.merge_script_classes(group, [('UtBot', UtBot)])
        holder = si.get_script_group(group)
        assert hasattr(holder, 'Sma') and hasattr(holder, 'UtBot')
        # 再加一个**同名**的 → 用新类替换（旧的那个换了代码 ✓）
        si.merge_script_classes(group, [('Sma', Sma2)])
        assert si.SCRIPT_CLASSES[group]['Sma'] is Sma2
        assert si.SCRIPT_CLASSES[group]['UtBot'] is UtBot
        assert hasattr(si.get_script_group(group), 'UtBot')
    finally:
        si.SCRIPT_GROUPS.pop(group, None)
        si.SCRIPT_CLASSES.pop(group, None)


def test_editor_script_indicator_legend_false(tmp_path):
    """编辑器加进来的脚本指标：`legend = False` 必须解析成「不显示标签」✓。

    同时验证两个容易踩的点：
    - 类**自己**定义的 bool 才算（minibt 基类上有个同名 property ✗）；
    - 写错名字（`lenend = False` ✗）等于没设 → 仍然是 True ✓。
    """
    import types

    si = pytest.importorskip('miniqt.app.common.script_indicator')
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    cls = window_module.PylightchartsChartWindow

    correct = '''
from minibt import BtIndicator, np


class PositionLine(BtIndicator):
    isplot = True
    legend = False          # ★ 正确写法
    overlap = True

    def next(self):
        self.lines.pl = np.full(self.length, np.nan)
'''
    typo = '''
from minibt import BtIndicator, np


class PositionLine(BtIndicator):
    isplot = True
    lenend = False          # ✗ 笔误：没有这个属性，等于没设
    overlap = True

    def next(self):
        self.lines.pl = np.full(self.length, np.nan)
'''

    window = types.SimpleNamespace()

    good = si.check_script(correct, str(tmp_path / 'position_line.py'))
    assert good.ok, good.message()
    assert cls._legend_flag(window, good.group, 'PositionLine') is False

    bad = si.check_script(typo, str(tmp_path / 'typo.py'))
    assert bad.ok, bad.message()
    assert cls._legend_flag(window, bad.group, 'PositionLine') is True
