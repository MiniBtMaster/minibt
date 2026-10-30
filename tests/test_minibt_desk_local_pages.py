"""本地图表副本互相独立 + 加载数据只要 K 线 ✓

用户 2026-10-30 反馈：

1. 两个本地图表加载**同一份 CSV** 时，一个页面加指标，另一个页面也出现同样
   的指标 ✗ —— 指标应该属于**页面**（各自独立的副本）；
2. 加载（重新打开）本地数据时，把上次加过的指标又带出来了 ✗ ——
   加载数据只加载 K 线，指标要重新加 / 用指标模板。
"""
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


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


def _patches(desk):
    out = []
    for script in desk.sent:
        text = str(script)
        if text.startswith('window.__desk.applyPatch('):
            out.append(json.loads(text[len('window.__desk.applyPatch('):-2]))
    return out


def _keys(desk, name, cell=0, page=''):
    return [item['key'] for item in desk._local_items(name, cell, page)]


def test_two_local_pages_same_csv_are_independent(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)

    # 页 1 加载 test → 加 MA
    desk._on_local_cells({'page': 'local:1', 'cells': ['test']})
    desk._on_local_load({'name': 'test', 'cell': 0, 'page': 'local:1'})
    desk._on_local_add_indicator({'symbol': 'test', 'key': 'MA',
                                 'cell': 0, 'page': 'local:1'})
    assert _keys(desk, 'test', 0, 'local:1') == ['MA']

    # 页 2 加载**同一份 CSV** → 干净（不带页 1 的指标 ✓）
    desk._on_local_cells({'page': 'local:2', 'cells': ['test']})
    desk._on_local_load({'name': 'test', 'cell': 0, 'page': 'local:2'})
    assert _keys(desk, 'test', 0, 'local:2') == []

    # 页 2 加 RSI → 页 1 不受影响 ✓
    desk._on_local_add_indicator({'symbol': 'test', 'key': 'RSI',
                                 'cell': 0, 'page': 'local:2'})
    assert _keys(desk, 'test', 0, 'local:1') == ['MA']
    assert _keys(desk, 'test', 0, 'local:2') == ['RSI']

    # 各页自己的补丁里只带自己的指标 ✓
    patches = [item for item in _patches(desk)
               if item['type'] == 'local_indicator']
    assert any(item.get('page') == 'local:1' for item in patches)
    assert any(item.get('page') == 'local:2' for item in patches)


def test_local_load_only_brings_kline(tmp_path, monkeypatch):
    """加载数据不要带出上次的指标（同一页重新打开也一样 ✓）"""
    desk = _desk(tmp_path, monkeypatch)
    desk._on_local_cells({'page': 'local:1', 'cells': ['test']})
    desk._on_local_load({'name': 'test', 'cell': 0, 'page': 'local:1'})
    desk._on_local_add_indicator({'symbol': 'test', 'key': 'MA',
                                 'cell': 0, 'page': 'local:1'})
    assert _keys(desk, 'test', 0, 'local:1') == ['MA']

    desk.sent.clear()
    desk._on_local_load({'name': 'test', 'cell': 0, 'page': 'local:1'})

    assert _keys(desk, 'test', 0, 'local:1') == []          # 指标清掉了 ✓
    patches = _patches(desk)
    kinds = [item['type'] for item in patches]
    assert 'local_kline' in kinds                           # K 线照常 ✓
    indicator = [item for item in patches
                 if item['type'] == 'local_indicator']
    assert indicator and indicator[-1]['items'] == []        # 图上没有线 ✓


def test_local_remove_indicator_is_per_page(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk._on_local_cells({'page': 'local:1', 'cells': ['test']})
    desk._on_local_add_indicator({'symbol': 'test', 'key': 'MA',
                                  'cell': 0, 'page': 'local:1'})
    desk._on_local_cells({'page': 'local:2', 'cells': ['test']})
    desk._on_local_add_indicator({'symbol': 'test', 'key': 'MA',
                                  'cell': 0, 'page': 'local:2'})
    desk._on_local_remove_indicator({'symbol': 'test', 'key': 'MA',
                                     'cell': 0, 'page': 'local:2'})
    assert _keys(desk, 'test', 0, 'local:1') == ['MA']       # 只删页 2 ✓
    assert _keys(desk, 'test', 0, 'local:2') == []


def test_local_strategy_is_per_page(tmp_path, monkeypatch):
    """策略也按页面存：页 1 的策略线不会出现在页 2 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    line = {'key': 'editor:S:line:0', 'label': 'ma'}
    desk._local_strategies['local:1'] = {
        'items': [line], 'groups': {'test': [line]},
        'name': 'S', 'path': '/tmp/s.py', 'symbol': 'test', 'page': 'local:1',
    }
    desk._local_strategy_of = {'local:1': 'S'}

    first = desk._local_indicator_payload('test', 0, page='local:1')
    second = desk._local_indicator_payload('test', 0, page='local:2')
    assert first.get('strategy', {}).get('name') == 'S'
    assert any(item['key'] == 'editor:S:line:0' for item in first['items'])
    assert not second.get('strategy')                        # 页 2 没有 ✓
    assert not [item for item in second['items']
                if str(item.get('key')).startswith('editor:')]

    # 删策略只影响那一页 ✓
    desk._clear_local_page_strategies('test', also=['test'], page='local:1')
    assert not desk._local_strategies
    desk._local_strategies['local:2'] = {
        'items': [line], 'groups': {'test': [line]},
        'name': 'S2', 'path': '/tmp/s2.py', 'symbol': 'test',
        'page': 'local:2',
    }
    assert desk._local_indicator_payload(
        'test', 0, page='local:2').get('strategy', {}).get('name') == 'S2'


# ------------------------------------------- 策略线不能串格 / 策略管理删除
def _pair_page(desk):
    """一页两格（l / pp）+ 一个只在 l 上画线的策略 ✓"""
    desk._on_local_cells({'page': 'local:1',
                          'cells': ['l2609_60', 'pp2609_60']})
    line_fast = {'key': 'editor:sma_fast:line:0', 'label': 'sma_fast'}
    line_slow = {'key': 'editor:sma_slow:line:1', 'label': 'sma_slow'}
    desk._local_strategies['local:1'] = {
        'items': [line_fast, line_slow],
        'groups': {'l2609_60': [line_fast, line_slow]},
        'name': 'test',
        'path': os.path.join(str(pathlib.Path(__file__).parents[1]),
                             'test.py'),
        'symbol': 'l2609_60',
        'page': 'local:1',
        'contracts': ['l2609_60', 'pp2609_60'],
    }
    desk._local_strategy_of = {'local:1': 'test'}
    desk._local_set_items('l2609_60', 0, [{'key': 'MA', 'params': {}}],
                          'local:1')
    desk._local_set_items('pp2609_60', 1, [{'key': 'RSI', 'params': {}}],
                          'local:1')


def test_strategy_lines_do_not_leak_into_other_cell(tmp_path, monkeypatch):
    """策略只在 l2609_60 上画的均线，不能出现在 pp2609_60 那一格 ✓

    用户 2026-10-30 实测：单图加载 test.py → l 的均线重复出现在 pp 图上。
    原因：`_local_indicator_payload()` 后面又 `strategy['items'] + items`
    把所有格的线都加了一遍 ✗
    """
    desk = _desk(tmp_path, monkeypatch)
    _pair_page(desk)

    first = desk._local_indicator_payload('l2609_60', 0, page='local:1')
    second = desk._local_indicator_payload('pp2609_60', 1, page='local:1')
    first_keys = [item.get('key') for item in first['items']]
    second_keys = [item.get('key') for item in second['items']]
    assert [key for key in first_keys if str(key).startswith('editor:')]         == ['editor:sma_fast:line:0', 'editor:sma_slow:line:1']
    assert any(str(key).startswith('MA') for key in first_keys)
    assert not [key for key in second_keys
                if str(key).startswith('editor:')]        # 不串格 ✓
    assert any(str(key).startswith('RSI') for key in second_keys)


def test_remove_local_strategy_by_row_key(tmp_path, monkeypatch):
    """策略管理里删本地策略：用行上的 `key`（页签 id）→ 真的删掉 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    _pair_page(desk)

    rows = [row for row in desk._strategy_manage_rows() if row.get('local')]
    assert rows and rows[0]['key'] == 'local:1'
    assert [row['name'] for row in rows] == ['test']

    desk._on_strategy_manage_update({'action': 'delete', 'local': True,
                                     'key': 'local:1',
                                     'symbol': 'l2609_60'})
    assert not desk._local_strategies
    assert not [row for row in desk._strategy_manage_rows()
                if row.get('local')]
    payload = desk._local_indicator_payload('l2609_60', 0, page='local:1')
    assert not payload.get('strategy')
    assert 'editor:sma_fast:line:0' not in [
        item.get('key') for item in payload['items']]


def test_remove_local_strategy_accepts_csv_name(tmp_path, monkeypatch):
    """老行只给 CSV 名 / 策略名也能删（按记录内容匹配 ✓）"""
    desk = _desk(tmp_path, monkeypatch)
    _pair_page(desk)
    assert desk._remove_local_strategy('l2609_60') is True
    assert not desk._local_strategies


def test_closing_local_page_drops_its_strategy(tmp_path, monkeypatch):
    """关掉本地图表页 → 它的策略记录一起清（不留删不掉的幽灵行 ✓）"""
    desk = _desk(tmp_path, monkeypatch)
    _pair_page(desk)
    desk._on_local_cells({'page': 'local:1', 'closed': True, 'cells': []})
    assert not desk._local_strategies
    assert not desk._local_strategy_of
    assert not [row for row in desk._strategy_manage_rows()
                if row.get('local')]


def test_local_payload_survives_missing_csv(tmp_path, monkeypatch):
    """CSV 不在本地库里也不能抛异常（否则整包补丁丢了 → 图上什么都没有 ✗）"""
    desk = _desk(tmp_path, monkeypatch)
    desk._local_strategies['local:9'] = {
        'items': [{'key': 'editor:S:line:0'}],
        'groups': {'no_such_csv': [{'key': 'editor:S:line:0'}]},
        'name': 'S', 'path': '/tmp/s.py', 'symbol': 'no_such_csv',
        'page': 'local:9', 'contracts': ['no_such_csv'],
    }
    payload = desk._local_indicator_payload('no_such_csv', 0,
                                            page='local:9')
    assert payload['strategy'] == {'name': 'S'}
    assert [item['key'] for item in payload['items']]         == ['editor:S:line:0']


def test_toolbar_remove_menu_deletes_strategy(tmp_path, monkeypatch):
    """工具栏「🗑」里那条「策略 · xxx（删除）」= 只删策略（指标保留）✓

    用户 2026-10-30：删除菜单不要按格重复列策略；要能直接删策略
    （等效「策略管理」里的删除按钮）。
    """
    desk = _desk(tmp_path, monkeypatch)
    _pair_page(desk)
    assert desk._local_strategies

    # 前端「策略 · test（删除）」→ `remove_indicator` + `kind='strategy'`
    desk._on_local_remove_indicator({'symbol': 'pp2609_60', 'key': 'editor',
                                     'kind': 'strategy', 'cell': 1,
                                     'local': True, 'strategy': True,
                                     'page': 'local:1'})

    assert not desk._local_strategies
    assert not [row for row in desk._strategy_manage_rows()
                if row.get('local')]
    # 指标**保留** ✓
    assert [item['key'] for item in desk._local_items('l2609_60', 0,
                                                      'local:1')] == ['MA']
    payload = desk._local_indicator_payload('l2609_60', 0, page='local:1')
    assert not payload.get('strategy')
    assert not [item for item in payload['items']
                if str(item.get('key', '')).startswith('editor:')]


def test_frontend_remove_menu_shows_strategy_once():
    """两个图表页的「🗑」菜单：策略只出一条（页面级），每格只列指标 ✓"""
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = (pathlib.Path(__file__).parents[1] / 'jslib' / 'src' / 'desk'
                / name).read_text(encoding='utf-8')
        assert 'private strategyName = ' in page, name
        assert '`策略 · ${' in page or "'策略 · '" in page, name
        block = page.split('openRemoveMenu(anchor: HTMLElement): void {',
                           1)[1].split('showMenuBelow(anchor, items);', 1)[0]
        # 每格列表里跳过策略线 ✓
        assert "key.startsWith('editor:')" in block, name
        assert 'this.removeStrategy' in block or 'removeStrategy()' in block


def test_frontend_local_remove_strategy_command():
    page = (pathlib.Path(__file__).parents[1] / 'jslib' / 'src' / 'desk'
            / 'local-chart-page.ts').read_text(encoding='utf-8')
    block = page.split('removeStrategy(): void {', 1)[1][:400]
    assert "kind: 'strategy'" in block
    assert "local: true" in block


def test_frontend_close_last_tab_goes_home():
    """所有页面都关掉 → 回首页（以前会再新建一个本地图表 ✗）"""
    app = (pathlib.Path(__file__).parents[1] / 'jslib' / 'src' / 'desk'
           / 'app.ts').read_text(encoding='utf-8')
    assert 'else this.openHome();' in app
    tail = app.split("const fallback = [...this.tabs.keys()].pop();", 1)[1][:200]
    assert 'this.openHome()' in tail
    assert 'this.openLocalChart()' not in tail


def test_frontend_local_apply_layout_does_not_sync_cells():
    """后端推的布局（自动布局 / 应用布局）不要把前端的旧格子报回去 ✗"""
    page = (pathlib.Path(__file__).parents[1] / 'jslib' / 'src' / 'desk'
            / 'local-chart-page.ts').read_text(encoding='utf-8')
    assert 'setLayoutSpec(spec: DeskLayoutSpec, sync = true): void {' in page
    assert 'if (!same) this.setLayoutSpec(spec, false);' in page
    assert 'if (sync) {' in page


def test_frontend_sends_page_for_local_indicators():
    app = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(
        encoding='utf-8')
    # 本地图表的指标命令都带页签 id（后端按「页 + 格」存 ✓）
    assert 'page: id,' in app
    assert app.count('page: id,') >= 2
