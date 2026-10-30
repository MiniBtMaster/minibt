"""单页单策略的 3 个配套改进 ✓

1. 页签标签显示当前页面的策略（`本地图表1 · test`）；
2. 「复制当前页面」= 同布局 + 同数据、不带策略（A/B 对比用）；
3. **只读叠加**：策略只算线（不跑 next / 不碰账户），一页可以叠多个。
"""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(name: str) -> str:
    return (DESK_TS / name).read_text(encoding='utf-8')


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, local_data, personal, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(local_data, 'STATE_FILE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(local_data, 'FOLDERS_FILE',
                        str(tmp_path / 'folders.json'))
    monkeypatch.setattr(personal, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(personal, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    folder = tmp_path / 'personal' / 'strategies'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'test.py').write_text('\n'.join([
        'from minibt import Strategy',
        '',
        'class test(Strategy):',
        '    params = dict(fast=5, slow=20)',
        '    def __init__(self):',
        "        self.kline = self.get_kline('l2609_60')",
        '        close = self.kline.close',
        "        self.fast = close.rolling(5).mean(lines=['sma_fast'])",
        "        self.slow = close.rolling(20).mean(lines=['sma_slow'])",
        '        self.fast.overlap = self.slow.overlap = True',
        '',
        '    def next(self):',
        '        pass',
    ]), encoding='utf-8')
    personal.add_directory(str(folder), kind='strategy')

    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.log_to_stdout = False
    desk.log_to_ui = False
    return desk, str(folder / 'test.py')


def _page(desk):
    desk._on_local_cells({'page': 'local:1', 'cells': ['l2609_60']})
    desk._on_local_load({'name': 'l2609_60', 'cell': 0, 'page': 'local:1'})


# --------------------------------------------------------------- 只读叠加
def test_overlay_paints_lines_without_touching_strategy(tmp_path, monkeypatch):
    desk, path = _desk(tmp_path, monkeypatch)
    _page(desk)

    desk._on_local_add_overlay({'path': path, 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})

    assert [item['name'] for item in desk._local_overlays['local:1']] == ['test']
    # 只读叠加 ≠ 图上策略（不占「一页一策略」的名额 ✓）
    assert not desk._local_strategies
    assert not getattr(desk, '_local_runners', {})
    payload = desk._local_indicator_payload('l2609_60', 0, page='local:1')
    assert [item['name'] for item in payload['overlays']] == ['test']
    assert payload['strategy'] == ''
    keys = [item['key'] for item in payload['items']]
    assert keys == ['editor:sma_fast:line:0', 'editor:sma_slow:line:1']
    assert all(item['source'] == 'editor:test' for item in payload['items'])


def test_overlay_and_strategy_coexist(tmp_path, monkeypatch):
    """交易策略 + 只读叠加：线都在，但账户 / runner 只属于策略 ✓"""
    desk, path = _desk(tmp_path, monkeypatch)
    _page(desk)
    desk._local_strategies['local:1'] = {
        'items': [{'key': 'editor:S:line:0'}],
        'groups': {'l2609_60': [{'key': 'editor:S:line:0'}]},
        'name': 'S', 'path': path, 'symbol': 'l2609_60',
        'page': 'local:1', 'contracts': ['l2609_60'],
    }
    desk._on_local_add_overlay({'path': path, 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})

    payload = desk._local_indicator_payload('l2609_60', 0, page='local:1')
    assert payload['strategy'] == {'name': 'S'}
    assert [item['name'] for item in payload['overlays']] == ['test']
    sources = [item['source'] for item in payload['items']]
    assert 'editor:test' in sources and 'editor:S' in sources
    # 叠加不进 runner / 策略记录 ✓
    assert list(desk._local_strategies) == ['local:1']


def test_same_overlay_reloads_instead_of_duplicating(tmp_path, monkeypatch):
    """同一个策略（同一个文件 / 同名）再「只读叠加」→ **重新加载（替换）** ✓"""
    desk, path = _desk(tmp_path, monkeypatch)
    _page(desk)
    desk._on_local_add_overlay({'path': path, 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})
    desk._on_local_add_overlay({'path': path, 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})
    assert [item['name'] for item in desk._local_overlays['local:1']] == ['test']
    # toast 里能看出是「重新加载」而不是又加了一条 ✓
    assert any('只读叠加已重新加载' in str(item) for item in desk.sent)
    # 不同策略 → 追加 ✓
    folder = pathlib.Path(path).parent
    other = folder / 'other.py'
    other.write_text(pathlib.Path(path).read_text(encoding='utf-8')
                     .replace('class test(', 'class other(')
                     .replace("lines=['sma_fast']", "lines=['o_fast']")
                     .replace("lines=['sma_slow']", "lines=['o_slow']"),
                     encoding='utf-8')
    from minibt.desk import personal
    personal.add_directory(str(folder), kind='strategy')
    desk._on_local_add_overlay({'path': str(other), 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})
    assert sorted(item['name'] for item in desk._local_overlays['local:1'])         == ['other', 'test']


def test_overlay_identity_is_path_plus_class(tmp_path, monkeypatch):
    """「同一个策略」= **（绝对路径, 类名）**：同文件不同类互不覆盖 ✓"""
    desk, path = _desk(tmp_path, monkeypatch)
    _page(desk)
    # 同一个文件里再写一个 Strategy 子类 ✓
    text = pathlib.Path(path).read_text(encoding='utf-8')
    extra = pathlib.Path(path).with_name('two.py')
    extra.write_text(text.replace('class test(', 'class two(')
                     .replace("lines=['sma_fast']", "lines=['t_fast']")
                     .replace("lines=['sma_slow']", "lines=['t_slow']"),
                     encoding='utf-8')
    from minibt.desk import personal
    personal.add_directory(str(pathlib.Path(path).parent), kind='strategy')

    desk._on_local_add_overlay({'path': path, 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})
    desk._on_local_add_overlay({'path': str(extra), 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})
    # 不同文件 → 2 条叠加 ✓
    assert sorted(item['name'] for item in desk._local_overlays['local:1'])         == ['test', 'two']

    # 再点同一个（同一文件同一类）→ 替换，不新增 ✓
    desk._on_local_add_overlay({'path': path, 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})
    assert sorted(item['name'] for item in desk._local_overlays['local:1'])         == ['test', 'two']


def test_overlay_toggle_is_ignored(tmp_path, monkeypatch):
    """只读叠加没有 next 开关（后端兜底：收到 toggle 直接忽略 ✓）"""
    desk, path = _desk(tmp_path, monkeypatch)
    _page(desk)
    desk._on_local_add_overlay({'path': path, 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})
    desk.sent.clear()
    desk._on_strategy_manage_update({'action': 'toggle', 'local': True,
                                     'overlay': True, 'key': 'test',
                                     'symbol': 'l2609_60',
                                     'key_name': 'run_next', 'key': 'run_next',
                                     'value': False})
    # 没有改任何 tab 配置 ✓
    assert all(not (info or {}).get('strategy_config')
               for info in desk.tabs.values())


def test_remove_overlay_keeps_strategy_and_indicators(tmp_path, monkeypatch):
    desk, path = _desk(tmp_path, monkeypatch)
    _page(desk)
    desk._local_set_items('l2609_60', 0, [{'key': 'MA', 'params': {}}],
                          'local:1')
    desk._on_local_add_overlay({'path': path, 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})

    key = desk._local_overlays['local:1'][0]['key']
    desk._on_local_remove_indicator({'symbol': 'l2609_60', 'key': key,
                                     'kind': 'overlay', 'local': True,
                                     'page': 'local:1'})

    assert 'local:1' not in desk._local_overlays
    payload = desk._local_indicator_payload('l2609_60', 0, page='local:1')
    assert payload['overlays'] == []
    assert not [item for item in payload['items']
                if item['source'] == 'editor:test']
    assert [item['key'] for item in desk._local_items('l2609_60', 0,
                                                      'local:1')] == ['MA']


def test_overlay_listed_in_strategy_manager(tmp_path, monkeypatch):
    desk, path = _desk(tmp_path, monkeypatch)
    _page(desk)
    desk._on_local_add_overlay({'path': path, 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})
    rows = [row for row in desk._strategy_manage_rows() if row.get('overlay')]
    assert rows and rows[0]['name'].endswith('（只读叠加）')
    assert rows[0]['key'].endswith('|test') and rows[0]['local'] is True

    desk._on_strategy_manage_update({'action': 'delete', 'local': True,
                                     'overlay': True, 'key': rows[0]['key']})
    assert 'local:1' not in desk._local_overlays


def test_overlay_dropped_when_page_closes(tmp_path, monkeypatch):
    desk, path = _desk(tmp_path, monkeypatch)
    _page(desk)
    desk._on_local_add_overlay({'path': path, 'symbol': 'l2609_60',
                               'cell': 0, 'local': True, 'page': 'local:1'})
    desk._on_local_cells({'page': 'local:1', 'closed': True, 'cells': []})
    assert not desk._local_overlays


# ------------------------------------------------------------------ 前端
def test_frontend_overlay_row_has_disabled_run_toggles():
    """策略管理里「只读叠加」那一行：两个运行开关**禁用**（不跑 next ✓）"""
    dialogs = (DESK_TS / 'layout-dialogs.ts').read_text(encoding='utf-8')
    assert 'const overlay = (row as unknown as { overlay?: boolean }).overlay;'         in dialogs
    assert 'if (overlay) {' in dialogs
    block = dialogs.split('if (overlay) {', 1)[1].split('} else {', 1)[0]
    assert 'button.disabled = true;' in block
    assert '只读叠加：不运行 next' in block
    assert 'item.append(text, newBar, runNext, drop);' in block


def test_frontend_editor_has_overlay_button():
    panel = _read('editor-panel.ts')
    assert "this._button('只读叠加'" in panel
    assert 'overlay: !!overlay,' in panel
    assert '只读叠加目前只支持本地图表' in panel
    page = _read('local-chart-page.ts')
    assert 'private overlayItems: Array<{ name: string; key: string }> = [];' in page
    assert '只读叠加 · ${item.name}（删除）' in page
    assert "kind: 'overlay'" in page


def test_frontend_duplicate_local_page():
    app = _read('app.ts')
    assert 'duplicateLocalChart(id = \'\'): string {' in app
    assert "this.send('local_load', { name, cell, page: newId });" in app
    assert '复制当前本地图表页' in app
    local = _read('local-chart-page.ts')
    assert '复制当前页面（A/B 对比）' in local
    assert "this.options.onCommand?.('duplicate_local_chart', {" in local
    assert 'get layoutSpec(): DeskLayoutSpec {' in local


def test_frontend_tab_label_shows_strategy():
    app = _read('app.ts')
    assert 'private _syncTabStrategy(id: string, name: string): void {' in app
    assert 'baseLabel?: string;' in app
    assert 'this.tabLabels.set(tab.id, label);' in app
    # 补丁里带 `strategy` → 更新页签（实时 / 本地都接 ✓）
    assert "if ('strategy' in patch) {" in app
    assert 'this._syncTabStrategy(page.pageId, name);' in app
