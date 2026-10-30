"""个人指标目录（「我的脚本」）的加载 / 灰显 / 右键删除测试 ✓。

`personal_indicators` 是纯逻辑 + 一个轻量界面（``IndicatorPickerDialog``），
离屏就能跑 ✓。
"""
from __future__ import annotations

import os
import textwrap

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

pytest.importorskip('PyQt6')
from PyQt6.QtCore import Qt  # noqa: E402

personal = pytest.importorskip('miniqt.app.common.personal_indicators')
si = pytest.importorskip('miniqt.app.common.script_indicator')

SCRIPT = textwrap.dedent('''
    from minibt import BtIndicator

    class MyInd(BtIndicator):
        """我的测试指标 ✓"""
        params = {'period': 14}

        def next(self, period=14):
            return self.close
''')

CATEGORY = 'ind'


@pytest.fixture()
def config(tmp_path, monkeypatch):
    """把配置文件指到临时目录（别动用户真实的 ✓）。"""
    monkeypatch.setattr(personal, 'CONFIG_FILE', str(tmp_path / 'pi.json'),
                        raising=False)
    personal.reset_cache()
    yield tmp_path
    personal.reset_cache()
    si.SCRIPT_GROUPS.pop(CATEGORY, None)


@pytest.fixture()
def ind_dir(config):
    """``ind/myind.py``（目录名 = 类别 ✓）。"""
    folder = config / 'ind'
    folder.mkdir()
    (folder / 'myind.py').write_text(SCRIPT, encoding='utf-8')
    return folder


# ---- 添加目录 -------------------------------------------------------------
def test_add_directory_uses_the_folder_name_as_category(ind_dir):
    info = personal.add_directory(str(ind_dir))
    assert info['category'] == CATEGORY
    assert [name for name, _ in info['classes']] == ['MyInd']
    assert info['errors'] == []
    # 注册成脚本组 → indicator_holder('ind') 能拿到 ✓
    assert si.get_script_group(CATEGORY) is not None
    # 条目：组 = 类别，名 = 类名 ✓
    entries = personal.categories()[CATEGORY]
    assert entries and entries[0]['group'] == CATEGORY
    assert entries[0]['name'] == 'MyInd'
    assert entries[0]['doc'] == '我的测试指标 ✓'
    # 落盘 ✓
    saved = personal.directories()
    assert len(saved) == 1
    assert saved[0]['name'] == CATEGORY
    assert os.path.abspath(saved[0]['path']) == os.path.abspath(str(ind_dir))


def test_reload_after_restart_loads_the_saved_directory(ind_dir):
    personal.add_directory(str(ind_dir))
    personal.reset_cache()                      # 模拟重启 ✓
    si.SCRIPT_GROUPS.pop(CATEGORY, None)
    assert si.get_script_group(CATEGORY) is None
    assert personal.ensure_loaded()[CATEGORY]   # 重新读配置 → 重新注册 ✓
    assert si.get_script_group(CATEGORY) is not None


def test_remove_directory_stops_loading_next_time(ind_dir):
    personal.add_directory(str(ind_dir))
    assert personal.remove_directory(CATEGORY) is True
    assert personal.directories() == []
    assert si.get_script_group(CATEGORY) is None
    personal.reset_cache()                      # 模拟重启 ✓
    assert personal.ensure_loaded() == {}


def test_remove_directory_accepts_the_path_too(ind_dir):
    personal.add_directory(str(ind_dir))
    assert personal.remove_directory(str(ind_dir)) is True
    assert personal.ensure_loaded() == {}


def test_directory_without_btindicator_is_not_saved(config):
    folder = config / 'plain'
    folder.mkdir()
    (folder / 'helper.py').write_text('x = 1\n', encoding='utf-8')
    info = personal.add_directory(str(folder))
    assert info['classes'] == []
    assert info['errors'] == []              # 「没有指标」不算错误，直接跳过 ✓
    assert personal.directories() == []      # 没指标就不记 ✓
    assert personal.ensure_loaded() == {}


def test_scan_skips_underscore_files_and_reports_errors(ind_dir):
    (ind_dir / '_helper.py').write_text('x = 1\n', encoding='utf-8')
    (ind_dir / 'broken.py').write_text('def oops(\n', encoding='utf-8')
    info = personal.add_directory(str(ind_dir))
    assert [name for name, _ in info['classes']] == ['MyInd']
    assert any('broken.py' in item for item in info['errors'])
    assert not any('_helper' in item for item in info['errors'])


# ---- 选择器界面 -----------------------------------------------------------
DIALOGS = 'miniqt.app.windows.tradingview_indicator_dialogs'
USER_ROLE = Qt.ItemDataRole.UserRole


def _nav_key(item):
    return str(item.data(USER_ROLE) or '')


def _dialog():
    from PyQt6.QtWidgets import QWidget

    dialogs = pytest.importorskip(DIALOGS)
    host = QWidget()                      # MessageBoxBase 需要父窗口 ✓
    dialog = dialogs.IndicatorPickerDialog(entries=[], parent=host)
    dialog._test_host = host              # 保持引用，别被 GC ✓
    return dialog


def _nav_items(dialog):
    return [dialog.navList.item(i) for i in range(dialog.navList.count())]


def _category_item(dialog):
    for item in _nav_items(dialog):
        if _nav_key(item).startswith('script:'):
            return item
    return None


def test_scripts_header_is_grey_and_category_is_listed(config, ind_dir):
    personal.add_directory(str(ind_dir))
    dialog = _dialog()

    header = next(item for item in _nav_items(dialog)
                  if item.text().strip() == '我的脚本')
    assert header.flags() == Qt.ItemFlag.NoItemFlags      # 灰色不可点 ✓
    assert _nav_key(header) == ''                         # 不是可选项 ✓

    item = _category_item(dialog)
    assert item is not None and item.text().strip() == CATEGORY
    dialog.navList.setCurrentItem(item)                   # 点一下类别 ✓
    assert dialog.indicatorList.count() == 1
    assert dialog._nav == f'script:{CATEGORY}'


def test_picker_searches_personal_indicators(config, ind_dir):
    personal.add_directory(str(ind_dir))
    dialog = _dialog()
    dialog.searchEdit.setText('MyInd')
    assert dialog.indicatorList.count() == 1


def test_picker_removes_the_category(config, ind_dir):
    personal.add_directory(str(ind_dir))
    dialog = _dialog()
    assert _category_item(dialog) is not None

    assert dialog._remove_category(CATEGORY) is True
    assert _category_item(dialog) is None                 # 导航里没了 ✓
    assert personal.categories() == {}
    personal.reset_cache()                                # 重启也不再加载 ✓
    assert personal.ensure_loaded() == {}


def test_picker_without_personal_directories_shows_grey_header(config):
    dialog = _dialog()
    header = next(item for item in _nav_items(dialog)
                  if item.text().strip() == '我的脚本')
    assert header.flags() == Qt.ItemFlag.NoItemFlags
    assert dialog._scripts == {}


def test_personal_category_is_not_in_builtin_groups(config, ind_dir):
    """个人类别只出现在「我的脚本」下，不该混进「内置指标」✓。"""
    personal.add_directory(str(ind_dir))
    dialog = _dialog()
    assert CATEGORY not in dialog._groups
    assert CATEGORY in dialog._scripts


def test_adding_the_same_category_twice_replaces_it(config, ind_dir):
    """同名类别不叠加：再添一次就是替换（配置文件里只留一条 ✓）。"""
    personal.add_directory(str(ind_dir))
    other = config / 'ind2'
    other.mkdir()
    (other / 'myind.py').write_text(SCRIPT, encoding='utf-8')
    # 手动把它也命名成 ind（模拟同一个类别名 ✓）
    info = personal.register_directory(str(other), CATEGORY)
    assert info['classes']
    personal.add_directory(str(ind_dir))                    # 再来一次 ✓
    saved = personal.directories()
    assert len(saved) == 1
    assert os.path.abspath(saved[0]['path']) == os.path.abspath(str(ind_dir))


# ---- 回归：类别名撞上 minibt 的同名「模块」--------------------------------
DUAL_THRUST = textwrap.dedent('''
    from minibt import *

    class DualThrust(BtIndicator):
        """DualThrust ✓"""
        params = {'k': 1}
        lines = ('dt',)

        def next(self, k=1):
            return self.close
''')


def _sample_kline():
    import pandas as pd

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


def test_category_named_like_a_minibt_module_still_computes(config):
    """回归：类别叫 ``strategy``（``minibt.strategy`` 是个 **module**）也要能算 ✓。

    以前 ``indicator_holder`` 只判 ``cls is None``，拿到 module 就当找到了 →
    ``cls(kline)`` → ``TypeError: 'module' object is not callable`` ✗。
    """
    folder = config / 'strategy'
    folder.mkdir()
    (folder / 'dual_thrust.py').write_text(DUAL_THRUST, encoding='utf-8')

    info = personal.add_directory(str(folder))
    assert info['category'] == 'strategy'
    assert [name for name, _ in info['classes']] == ['DualThrust']

    dialog = pytest.importorskip('miniqt.app.windows.indicator_dialog')
    holder = dialog.indicator_holder(_sample_kline(), 'strategy')
    assert holder is not None, '不能把 minibt.strategy（module）当成指标组 ✗'
    assert hasattr(holder, 'DualThrust')

    plot = dialog.compute_indicator(_sample_kline(), 'strategy', 'DualThrust',
                                    {'k': 2})
    assert plot['groups']
    assert list(plot['groups'][0]['lines']) == ['DualThrust']


def test_shadows_builtin_only_warns_for_callable_groups(config):
    assert personal.shadows_builtin('strategy') is False   # module → 没问题 ✓
    assert personal.shadows_builtin('TaLib') is True       # 真内置组 → 警告 ✓
    assert personal.shadows_builtin('nope-not-here') is False


# ---- 导航字色跟随主题色（v1.1.68）----------------------------------------
def _section_items(dialog):
    return [dialog.navList.item(i) for i in range(dialog.navList.count())
            if dialog.navList.item(i).flags() == Qt.ItemFlag.NoItemFlags]


def test_section_headers_follow_the_theme_color(config):
    """分组标题 / 灰色不可点项都要用**程序主题色**（不再写死 #8a8f98 ✓）。"""
    from PyQt6.QtGui import QColor

    from qfluentwidgets import themeColor

    dialogs = pytest.importorskip(DIALOGS)
    expected = QColor(themeColor())
    assert expected.isValid() and expected.name() != '#8a8f98'

    from PyQt6.QtWidgets import QWidget

    host = QWidget()
    for dialog in (dialogs.IndicatorPickerDialog(entries=[], parent=host),
                   dialogs.TemplateDialog(templates=[], parent=host)):
        items = _section_items(dialog)
        assert items, '至少要有个分组标题 ✓'
        for item in items:
            assert item.foreground().color().name() == expected.name(), \
                f'{item.text()} 没跟主题色 ✓'


def test_scripts_header_uses_the_theme_color(config, ind_dir):
    from PyQt6.QtGui import QColor

    from qfluentwidgets import themeColor

    personal.add_directory(str(ind_dir))
    dialog = _dialog()
    header = next(item for item in _nav_items(dialog)
                  if item.text().strip() == '我的脚本')
    assert header.flags() == Qt.ItemFlag.NoItemFlags
    assert header.foreground().color().name() == \
        QColor(themeColor()).name()
    # 类别项是可点的 → 不跟着主题色（能区分 ✓）
    item = _category_item(dialog)
    assert item is not None
    assert item.flags() != Qt.ItemFlag.NoItemFlags


# ---- 纯策略文件跳过（不当错误）--------------------------------------------
def test_strategy_only_file_is_skipped_silently(config):
    folder = config / 'mix'
    folder.mkdir()
    (folder / 'myind.py').write_text(SCRIPT, encoding='utf-8')
    (folder / 'only_strategy.py').write_text(textwrap.dedent('''
        from minibt import *

        class MyStrategy(Strategy):
            pass
    '''), encoding='utf-8')

    info = personal.add_directory(str(folder))
    assert [name for name, _ in info['classes']] == ['MyInd']
    assert info['errors'] == []                     # 纯策略文件不算错误 ✓


# ---- 回归：模块必须注册进 sys.modules（v1.1.71）---------------------------
SYS_MODULES_SCRIPT = textwrap.dedent('''
    import sys

    from minibt import BtIndicator

    # minibt 的元类会去 sys.modules[cls.__module__] 拿模块 —— 没注册就是 None
    # → AttributeError: 'NoneType' object has no attribute '__dict__' ✗
    _module = sys.modules.get(__name__)
    _module.__dict__['_seen'] = True
    assert _seen is True

    class ModInd(BtIndicator):
        params = {}

        def next(self):
            return self.close
''')


def test_exec_registers_the_module_in_sys_modules(config):
    """tutorials/basic/signal_optimize.py 那类脚本：模块必须在 sys.modules 里 ✓。"""
    folder = config / 'reg'
    folder.mkdir()
    (folder / 'needs_module.py').write_text(SYS_MODULES_SCRIPT,
                                            encoding='utf-8')
    info = personal.add_directory(str(folder))
    assert info['errors'] == [], info['errors']
    assert [name for name, _ in info['classes']] == ['ModInd']


def test_duplicate_names_are_skipped_not_errored(config):
    """同名指标只保留第一个 —— 提示一行，不算错误 ✓。"""
    folder = config / 'dup'
    folder.mkdir()
    (folder / 'a_first.py').write_text(SCRIPT, encoding='utf-8')
    (folder / 'b_second.py').write_text(SCRIPT, encoding='utf-8')

    info = personal.add_directory(str(folder))
    assert [name for name, _ in info['classes']] == ['MyInd']
    assert info['errors'] == []                     # 不是错误 ✓
    assert info['skipped'] and 'MyInd' in info['skipped'][0]
    # 条目里只有一份 ✓
    assert len(personal.categories()['dup']) == 1
