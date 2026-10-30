"""图表右键「我的模板 / 保存当前指标模板」（本地图表 + 实时图表 ✓）

用户 2026-10-30 要求：图表右键加两个菜单 ——
1.「我的模板」子菜单 = 工具栏「模板 → 我的模板」，点一下就把模板应用到
   **当前图表**（鼠标最后点击的那一格）；
2.「保存当前指标模板」= 工具栏「模板 → 保存当前指标为模板」。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(name: str) -> str:
    return (DESK_TS / name).read_text(encoding='utf-8')


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, local_data, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(local_data, 'STATE_FILE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(local_data, 'FOLDERS_FILE',
                        str(tmp_path / 'folders.json'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.log_to_stdout = False
    desk.log_to_ui = False
    return desk


def _two_cell(desk, tab='DCE.a2701'):
    desk.tabs[tab] = {
        'cycle': 60, 'indicators': [{'key': 'MA', 'params': {}}],
        'layout': {'cols': 2, 'rows': 1,
                   'symbols': [tab, 'DCE.m2701'],
                   'cells': [{'symbol': tab,
                              'indicators': [{'key': 'MA', 'params': {}}]},
                             {'symbol': 'DCE.m2701', 'indicators': []}]},
    }
    return tab


# --------------------------------------------------------------- 实时图表
def test_apply_template_to_clicked_cell(tmp_path, monkeypatch):
    from minibt.desk import user_prefs
    desk = _desk(tmp_path, monkeypatch)
    tab = _two_cell(desk)
    tpl = user_prefs.save_template('我的组合', [
        {'key': 'MA', 'params': {'length': 20}},
        {'key': 'RSI', 'params': {'length': 6}},
    ])

    # 右键「我的模板 → 我的组合」= 应用到**鼠标最后点击的格**（cell 1）✓
    desk._on_apply_template({'symbol': tab, 'key': tpl['key'], 'cell': 1})

    cells = desk.tabs[tab]['layout']['cells']
    assert [item['key'] for item in cells[1]['indicators']] == ['MA', 'RSI']
    assert [item['key'] for item in cells[0]['indicators']] == ['MA']   # 不动 ✓
    assert [item['key'] for item in desk.tabs[tab]['indicators']] == ['MA']


def test_save_template_from_clicked_cell(tmp_path, monkeypatch):
    from minibt.desk import user_prefs
    desk = _desk(tmp_path, monkeypatch)
    tab = _two_cell(desk)
    desk.tabs[tab]['layout']['cells'][1]['indicators'] = [
        {'key': 'RSI', 'params': {'length': 9}}]

    # 右键「保存当前指标模板」= 存**鼠标最后点击的那一格** ✓
    desk._on_save_template({'symbol': tab, 'cell': 1, 'name': '格2组合'})

    saved = [item for item in user_prefs.templates()
             if item['name'] == '格2组合']
    assert saved and [item['key'] for item in saved[0]['items']] == ['RSI']
    assert saved[0]['items'][0]['params'] == {'length': 9}


def test_save_template_empty_cell_warns(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    tab = _two_cell(desk)
    desk.sent.clear()
    desk._on_save_template({'symbol': tab, 'cell': 1, 'name': '空'})
    con = ' '.join(str(item) for item in desk.sent)
    assert '还没有指标' in con or '无法保存' in con


# --------------------------------------------------------------- 本地图表
def test_local_apply_and_save_template_keeps_page(tmp_path, monkeypatch):
    from minibt.desk import user_prefs
    desk = _desk(tmp_path, monkeypatch)
    desk._on_local_cells({'page': 'local:1', 'cells': ['test']})
    desk._on_local_load({'name': 'test', 'cell': 0, 'page': 'local:1'})
    desk._on_local_add_indicator({'symbol': 'test', 'key': 'MA',
                                 'cell': 0, 'page': 'local:1'})

    desk._on_save_template({'local': True, 'symbol': 'test', 'cell': 0,
                            'page': 'local:1', 'name': '本地组合'})
    saved = [item for item in user_prefs.templates()
             if item['name'] == '本地组合']
    assert saved and [item['key'] for item in saved[0]['items']] == ['MA']

    # 清空后应用模板 → 回到当前页 / 当前格 ✓
    desk._on_local_remove_indicator({'symbol': 'test', 'key': 'MA',
                                    'cell': 0, 'page': 'local:1'})
    assert desk._local_items('test', 0, 'local:1') == []
    desk._on_apply_template({'local': True, 'symbol': 'test', 'cell': 0,
                             'page': 'local:1', 'key': saved[0]['key']})
    assert [item['key'] for item in desk._local_items('test', 0, 'local:1')] \
        == ['MA']


# ------------------------------------------------------------------ 前端
def test_frontend_context_menu_has_template_items():
    menu = _read('chart-context-menu.ts')
    assert 'templates?: Array<Record<string, unknown>>;' in menu
    assert 'onApplyTemplate?: (key: string) => void;' in menu
    assert 'onSaveTemplate?: () => void;' in menu
    assert "{ label: '我的模板', submenu: templateItems }," in menu
    assert "label: '保存当前指标模板'," in menu
    assert '（还没有保存过模板）' in menu


def test_frontend_both_chart_pages_wire_templates():
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = _read(name)
        assert 'private templateRows: Array<Record<string, unknown>> = [];' \
            in page, name
        assert 'this.templateRows = Array.isArray(items) ? items.slice() : [];' \
            in page, name
        assert 'templates: this.templateRows,' in page, name
        assert 'onApplyTemplate: (key) => this.applyTemplate(key),' in page, name
        assert 'onSaveTemplate: () => this.saveCurrentTemplate(),' in page, name
        assert 'saveCurrentTemplate(): void {' in page, name
        # 右键菜单打开前刷一次模板列表（保证是最新的 ✓）
        assert "this.options.onCommand?.('templates', {});" in page, name


def test_frontend_templates_sent_to_every_chart_page():
    app = _read('app.ts')
    block = app.split("case 'templates': {", 1)[1].split('case ', 1)[0]
    assert 'for (const page of this.pages.values())' in block
    assert 'page instanceof ChartPage' in block
    assert 'page instanceof LocalChartPage' in block
    # 新建本地图表页时主动拉一次（右键菜单立刻能用 ✓）
    assert app.count("this.send('templates', {});") >= 2
