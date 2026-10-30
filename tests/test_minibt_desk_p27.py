"""P27：周期菜单（秒/分/时/天 二级 + 自定义）、布局四合一、选择器容错、索引增量 ✓"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------------ 周期菜单
def test_cycle_groups_and_labels():
    page = _read('jslib/src/desk/chart-page.ts')
    for key in ("{ label: '秒', items:", "{ label: '分', items:",
                "{ label: '时', items:", "{ label: '天', items:",
                '添加自定义周期', 'submenu:', 'export function parseCycle',
                'export function cycleLabel'):
        assert key in page, key
    # 30秒 / 1分 / 1时 / 1日 仍在（向后兼容 ✓）
    for value in ('value: 30', 'value: 60', 'value: 3600', 'value: 86400'):
        assert value in page, value


def test_cycle_label_helper_behaviour():
    """`cycleLabel` 的规则（在 JS 里；这里按同样的规则校验一下数据）"""
    page = _read('jslib/src/desk/chart-page.ts')
    assert "if (value % 86400 === 0) return `${value / 86400}天`;" in page
    assert "if (value % 3600 === 0) return `${value / 3600}时`;" in page
    assert "if (value % 60 === 0) return `${value / 60}分`;" in page
    assert 'return `${value}秒`;' in page
    # parseCycle 支持中文单位
    assert "w: 604800" in page and '月: 2592000' in page


def test_menu_supports_submenus():
    menu = _read('jslib/src/desk/menu.ts')
    for key in ('submenu?: MenuItem[]', 'buildMenu(', 'desk-menu-sub',
                'desk-menu-arrow', 'currentSubs'):
        assert key in menu, key


# ------------------------------------------------------------ 布局四合一
def test_layout_buttons_are_merged():
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'openLayoutMenu(anchor: HTMLElement)' in page
    for label in ("单图", "左右两图", "四图", '已保存的布局', '保存当前布局…',
                  '布局管理…', '导出 / 导入'):
        assert label in page, label
    # 三个旧按钮没了
    assert "'▾', (button) => {\n            this.openLayoutsMenu" not in page
    assert "this._toolButton('保存布局'" not in page
    assert "this._toolButton('布局管理'" not in page


# ------------------------------------------------------------ 选择器容错
def test_picker_command_always_responds(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, protocol, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.delenv('MINIBT_DESK_NO_INDEX', raising=False)
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True

    # 让目录构建直接爆炸 → 仍然要有回包 + error
    from minibt.desk import indicator_catalog

    def boom(*_args, **_kwargs):
        raise RuntimeError('catalog 炸了')

    monkeypatch.setattr(indicator_catalog, 'catalog', boom)
    desk.handle(protocol.encode_command({'cmd': 'indicator_picker',
                                         'payload': {}}))
    patches = [json.loads(row[len('window.__desk.applyPatch('):-2])
               for row in desk.sent if '"type":"indicator_picker"' in row]
    assert patches, '没有回包（用户看到空白 ✗）'
    patch = patches[-1]
    assert 'groups' in patch
    assert patch['total'] == len(patch['items'])
    assert 'catalog 炸了' in (patch.get('error') or '') or patch['items']


def test_picker_payload_has_counts(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, protocol, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.delenv('MINIBT_DESK_NO_INDEX', raising=False)
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.handle(protocol.encode_command({'cmd': 'indicator_picker',
                                         'payload': {}}))
    patch = [json.loads(row[len('window.__desk.applyPatch('):-2])
             for row in desk.sent if '"type":"indicator_picker"' in row][-1]
    assert patch['total'] > 650
    assert patch['counts'].get('tradingview', 0) > 80
    assert patch['counts'].get('common', 0) == 0   # P59 已删「常用」✓
    assert patch['error'] == ''


def test_picker_shows_total_and_error():
    panel = _read('jslib/src/panels/indicator-picker.ts')
    for key in ('setInfo(total: number', 'onReloadCallback', 'pylc-ip-info',
                '共 ${this.total} 个指标', '重新加载'):
        assert key in panel, key
    page = _read('jslib/src/desk/chart-page.ts')
    assert 'setInfo(Number(payload.total' in page


# ------------------------------------------------------------ 索引增量 + 报价页搜索
def test_symbol_index_incremental(tmp_path, monkeypatch):
    from minibt.desk import symbol_index as idx

    monkeypatch.setattr(idx, 'INDEX_FILE', str(tmp_path / 'i.sqlite3'))

    class Fut:
        kind = 'futures'
        api = None

        def available(self):
            return True

        def contracts(self, kind, exchange):
            return {'SHFE': ['SHFE.rb2610']}.get(exchange, [])

        def fill_names(self, names):
            pass

        def name_of(self, symbol):
            return 'rb'

    class Fut2(Fut):
        def contracts(self, kind, exchange):
            return {'SHFE': ['SHFE.rb2610', 'SHFE.rb2701']}.get(exchange, [])

    assert len(idx.build([Fut()])) == 1
    # 增量：只补新的，不丢旧的 ✓
    rows = idx.refresh([Fut2()])
    assert {row['symbol'] for row in rows} == {'SHFE.rb2610', 'SHFE.rb2701'}
    assert idx.count() == 2
    assert len(idx.load()) == 2


def test_desk_refresh_symbol_index_command(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, protocol, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.delenv('MINIBT_DESK_NO_INDEX', raising=False)
    from minibt.desk import symbol_index as idx
    monkeypatch.setattr(idx, 'INDEX_FILE', str(tmp_path / 'i.sqlite3'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    called = []
    monkeypatch.setattr(desk, 'refresh_symbol_index',
                        lambda force=False: called.append(force))
    desk.handle(protocol.encode_command({'cmd': 'symbols_refresh',
                                         'payload': {'force': True}}))
    assert called == [True]


def test_quote_page_searches_other_markets():
    page = _read('jslib/src/desk/quote-page.ts')
    for key in ('onGlobalSearch', 'onOpenSymbol', 'setGlobalResults',
                'desk-quote-global', '其他市场（点一下打开看盘）'):
        assert key in page, key
    app = _read('jslib/src/desk/app.ts')
    assert "onGlobalSearch: (text) => this.send('symbol_search', { text })" in app
    assert 'this.quotePage?.setGlobalResults(' in app
