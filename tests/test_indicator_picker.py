"""指标选择器 / 模板 / 收藏 / K 线类型（pylightcharts 插件 + desk 集成）。"""

import contextlib
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from minibt.desk import protocol, user_prefs                    # noqa: E402

DESK_TS = REPO / 'jslib' / 'src' / 'desk'
PANEL_TS = REPO / 'jslib' / 'src' / 'panels'


def _read(path):
    return pathlib.Path(path).read_text(encoding='utf-8')


# ------------------------------------------------------------- 偏好持久化
@pytest.fixture()
def prefs_file(tmp_path, monkeypatch):
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'prefs.json'))
    return tmp_path / 'prefs.json'


def test_favorites_persist(prefs_file):
    assert user_prefs.load() == {'favorites': [], 'strategies': [],
                                 'templates': [], 'layouts': [],
                                 'settings': {}, 'exports': [],
                                 'login': {},
                                 'watch': {'favorites': [], 'groups': [],
                                           'pins': {}}}
    assert user_prefs.toggle_favorite('pta_macd', True) == ['pta_macd']
    assert user_prefs.favorites() == ['pta_macd']
    assert prefs_file.is_file()
    # 新顺序：后收藏的在前 ✓
    user_prefs.toggle_favorite('MA', True)
    assert user_prefs.favorites() == ['MA', 'pta_macd']
    user_prefs.toggle_favorite('MA', False)
    assert user_prefs.favorites() == ['pta_macd']
    # 策略收藏走另一个字段 ✓
    user_prefs.toggle_favorite('pi:x/Strat', True, 'strategy')
    assert user_prefs.favorites('strategy') == ['pi:x/Strat']
    assert user_prefs.favorites() == ['pta_macd']


def test_templates_crud(prefs_file):
    record = user_prefs.save_template('组合A', [{'key': 'MA',
                                                'params': {'length': 5}},
                                               {'key': 'MACD'}])
    assert record['name'] == '组合A' and len(record['items']) == 2
    assert [item['name'] for item in user_prefs.templates()] == ['组合A']
    # 同名 = 覆盖 ✓
    user_prefs.save_template('组合A', [{'key': 'RSI'}])
    assert len(user_prefs.templates()) == 1
    assert user_prefs.find_template('组合A')['items'] == [
        {'key': 'RSI', 'params': {}}]
    assert user_prefs.delete_template('组合A') is True
    assert user_prefs.templates() == []
    assert user_prefs.delete_template('组合A') is False


def test_broken_prefs_file_is_ignored(prefs_file):
    prefs_file.write_text('{not json', encoding='utf-8')
    assert user_prefs.load()['favorites'] == []


# ------------------------------------------------------- pylightcharts 面板
class FakeWin:
    def __init__(self):
        self.scripts = []
        self.handlers = {}
        self._panels = []

    def run_script(self, script):
        self.scripts.append(script)

    def invoke(self, *args, **kwargs):
        return None

    def invoke_get(self, *args, **kwargs):
        return None

    @contextlib.contextmanager
    def bulk_run(self):
        yield

    class _Gen:
        count = 0

        def generate(self):
            FakeWin._Gen.count += 1
            index = FakeWin._Gen.count

            class Handle:
                def __str__(self):
                    return f'window.pk{index}'

                def __getattr__(self, item):
                    return f'window.pk{index}.{item}'

            return Handle()

    _id_gen = _Gen()


def test_indicator_picker_panel():
    from pylightcharts.panels import IndicatorPicker

    window = FakeWin()
    picker = IndicatorPicker(window, groups=[{'key': 'p', 'label': '个人',
                                             'sections': [{'key': 'favorites',
                                                           'label': '收藏'}]}],
                             items=[{'key': 'MA', 'label': 'MA 均线',
                                     'section': 'common', 'favorite': True}])
    first = window.scripts[0]
    assert 'new Lib.IndicatorPicker(' in first
    assert '"key":"MA"' in first
    assert list(window.handlers) == [str(picker.id)]

    window.scripts.clear()
    picker.open('favorites')
    picker.set_favorites(['MA'])
    picker.set_items([{'key': 'MACD', 'label': 'MACD'}])
    picker.set_groups([{'key': 'g', 'label': 'G', 'sections': []}])
    picker.set_theme('light')
    joined = '\n'.join(window.scripts)
    for key in ('.open("favorites")', '.setFavorites(["MA"])',
                '.setItems([', '.setGroups([', '.setTheme("light")'):
        assert key in joined, key

    calls = []
    picker.on_pick(lambda item: calls.append(('pick', item['key'])))
    picker.on_favorite(lambda item, on: calls.append(('fav', item['key'], on)))
    picker._dispatch('pick;;;MACD')
    picker._dispatch('favorite;;;MACD;;;1')
    picker._dispatch('favorite;;;MACD;;;0')
    assert calls == [('pick', 'MACD'), ('fav', 'MACD', True),
                     ('fav', 'MACD', False)]


def test_template_picker_panel():
    from pylightcharts.panels import TemplatePicker

    window = FakeWin()
    picker = TemplatePicker(window, templates=[
        {'key': 't1', 'name': 'pta_adx', 'count': 1}])
    assert 'new Lib.TemplatePicker(' in window.scripts[0]
    assert '"name":"pta_adx"' in window.scripts[0]

    window.scripts.clear()
    picker.open()
    picker.set_templates([{'key': 't2', 'name': 'x', 'count': 2}])
    joined = '\n'.join(window.scripts)
    assert '.open()' in joined and '.setTemplates(' in joined

    calls = []
    picker.on_apply(lambda item: calls.append(('apply', item['key'])))
    picker.on_delete(lambda key: calls.append(('delete', key)))
    picker.on_save(lambda name: calls.append(('save', name)))
    picker._dispatch('apply;;;t1')
    picker._dispatch('delete;;;t1')
    picker._dispatch('save;;;我的模板')
    assert calls == [('apply', 't1'), ('delete', 't1'), ('save', '我的模板')]


def test_pickers_assets_and_example():
    for name, keys in (('indicator-picker.ts', ('pylc-ip-mask', 'pylc-ip-star',
                                                'setFavorites', 'onPickCallback')),
                       ('template-picker.ts', ('pylc-tp-mask', 'pylc-tp-row',
                                               'setTemplates',
                                               'onApplyCallback'))):
        source = _read(PANEL_TS / name)
        for key in keys:
            assert key in source, (name, key)
    index = _read(PANEL_TS / 'index.ts')
    assert "export * from './indicator-picker';" in index
    assert "export * from './template-picker';" in index
    bundle = _read(REPO / 'pylightcharts' / 'js' / 'bundle.js')
    assert 'pylc-ip-mask' in bundle and 'pylc-tp-mask' in bundle
    assert 'pylc-ip-mask' in _read(REPO / 'pylightcharts' / 'js' / 'desk.js')

    import subprocess
    script = REPO / 'examples' / '13_panels' / '14_indicator_picker.py'
    result = subprocess.run([sys.executable, str(script), '--check'],
                            capture_output=True, text=True, encoding='utf-8',
                            env={**dict(__import__('os').environ),
                                 'PYTHONIOENCODING': 'utf-8'})
    assert result.returncode == 0, result.stderr[-600:]
    assert '数据检查通过' in result.stdout


# ------------------------------------------------------------- desk 集成
class _Feed:
    kind = 'futures'

    def __init__(self):
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
        pd = pytest.importorskip('pandas')
        return pd.DataFrame({
            'datetime': [1_700_000_000_000_000_000] * 3,
            'open': [1.0, 2.0, 3.0], 'high': [2.0, 3.0, 4.0],
            'low': [0.5, 1.5, 2.5], 'close': [1.5, 2.5, 3.5],
            'volume': [10, 20, 30]})


def _desk():
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


def _patches(sent):
    return [json.loads(script[len('window.__desk.applyPatch('):-2])
            for script in sent]


def test_picker_payload_has_groups_and_items(prefs_file):
    desk = _desk()
    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'indicator_picker'}))
    patch = _patches(desk.sent)[-1]
    assert patch['type'] == 'indicator_picker'
    groups = {group['key'] for group in patch['groups']}
    assert groups == {'personal', 'builtin'}
    sections = {section['key'] for group in patch['groups']
                for section in group['sections']}
    assert {'favorites', 'my_scripts', 'pta', 'tqta', 'btind'} <= sections
    assert len(patch['items']) > 400            # 完整指标库 ✓
    # P59：「常用」组已删除 → 只剩 minibt 指标库（MA 这种内置键不再出现）✓
    assert 'common' not in sections
    assert not any(item['section'] == 'common' for item in patch['items'])
    assert any(item['key'].startswith('pta_') for item in patch['items'])
    assert patch['favorites'] == []


def test_favorite_toggle_and_menu(prefs_file):
    desk = _desk()
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'toggle_favorite', 'payload': {'key': 'pta_macd', 'on': True}}))
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert 'favorites' in kinds
    favorites = [patch for patch in _patches(desk.sent)
                 if patch['type'] == 'favorites'][-1]
    assert [item['key'] for item in favorites['items']] == ['pta_macd']

    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'favorites'}))
    patch = _patches(desk.sent)[-1]
    assert patch['type'] == 'favorites'
    assert [item['key'] for item in patch['items']] == ['pta_macd']
    assert 'strategies' in patch


def test_template_save_apply_delete(prefs_file):
    desk = _desk()
    desk.handle(protocol.encode_command(
        {'cmd': 'add_indicator', 'payload': {'symbol': 'SHFE.rb2610',
                                             'key': 'MA'}}))
    desk.handle(protocol.encode_command(
        {'cmd': 'add_indicator', 'payload': {'symbol': 'SHFE.rb2610',
                                             'key': 'MACD'}}))
    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'save_template',
                                         'payload': {'name': '组合A'}}))
    templates = user_prefs.templates()
    assert templates and templates[0]['name'] == '组合A'
    assert len(templates[0]['items']) == 2

    desk.handle(protocol.encode_command({'cmd': 'templates'}))
    patch = _patches(desk.sent)[-1]
    assert patch['items'][0]['count'] == 2

    desk.tabs['SHFE.rb2610']['indicators'] = []
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'apply_template', 'payload': {'key': '组合A'}}))
    assert [item['key'] for item in desk.tabs['SHFE.rb2610']['indicators']] == [
        'MA', 'MACD']
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert 'indicator' in kinds

    desk.handle(protocol.encode_command(
        {'cmd': 'delete_template', 'payload': {'key': '组合A'}}))
    assert user_prefs.templates() == []


def test_save_template_without_indicators_warns(prefs_file):
    desk = _desk()
    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'save_template',
                                         'payload': {'name': 'x'}}))
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert 'toast' in kinds
    assert user_prefs.templates() == []


def test_chart_type_command_and_reopen():
    desk = _desk()
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'set_chart_type', 'payload': {'kind': 'line'}}))
    patch = _patches(desk.sent)[-1]
    assert patch == {'type': 'chart_type', 'symbol': 'SHFE.rb2610',
                     'kind': 'line'}
    assert desk.tabs['SHFE.rb2610']['chart_type'] == 'line'

    # 重开 tab 也要恢复类型 ✓
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'open_chart', 'payload': {'symbol': 'SHFE.rb2610'}}))
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert 'chart_type' in kinds

    # 非法类型忽略 ✓
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'set_chart_type', 'payload': {'kind': 'nope'}}))
    assert _patches(desk.sent) == []


def test_chart_type_ui_source():
    chart = _read(DESK_TS / 'chart-page.ts')
    for key in ('_applyChartType', 'LineSeries', 'AreaSeries',
                'BaselineSeries', 'BarSeries', 'setChartType',
                'openIndicatorMenu', 'setPicker', 'openTemplatePicker',
                'setTemplates', 'setFavorites'):
        assert key in chart, key
    app = _read(DESK_TS / 'app.ts')
    for key in ("'indicator_picker'", "'templates'", "'chart_type'",
                "'favorites'"):
        assert key in app, key
    # 工具栏里有「模板」按钮 ✓
    assert "'模板'" in chart
