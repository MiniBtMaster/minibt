"""一个页面只放一个策略 + 本地图表多开（本地图表1 / 2 / 3…）✓

用户 2026-10-30 反馈：

1. 一个页面只支持一个策略：重新「加到图表」（同一个 / 另一个策略）要**先清掉
   上一个策略**（含所有布局格），布局 / 指标保留；
2. 需要多策略 → **多开本地图表页面**（顶栏 ＋ → 本地图表，或首页-图表工作台
   右侧「新建本地图表」），页面依次叫「本地图表1」「本地图表2」…；
3. 图表工作台左边列出所有本地图表页，点一下就能打开；没有则不列。
"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(name: str) -> str:
    return (DESK_TS / name).read_text(encoding='utf-8')


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk._strategy_sync = True
    desk.log_to_stdout = False
    desk.log_to_ui = False
    return desk


# ---------------------------------------------------------------- 实时图表
def _fake_feed(np, pd, last=1_700_500_000):
    class Feed:
        kind = 'futures'
        api = None

        def available(self):
            return True

        def klines(self, symbol, cycle, length=500):
            rows = min(int(length), 2000)
            start = last - (rows - 1) * 60
            close = 100 + np.sin(np.arange(rows) / 9) * 3
            return pd.DataFrame({
                'datetime': [(start + i * 60) * 10 ** 9
                             for i in range(rows)],
                'open': close, 'high': close + 2, 'low': close - 2,
                'close': close, 'volume': np.ones(rows),
                'symbol': symbol, 'duration': cycle,
                'price_tick': 1.0, 'volume_multiple': 10,
            })

        def quotes(self, keys):
            return []

        def spec(self, symbol):
            return None

    return Feed()


def _strategy_file(pathlib_path, cls_name, line_name):
    pathlib_path.parent.mkdir(parents=True, exist_ok=True)
    pathlib_path.write_text('\n'.join([
        'from minibt import Strategy',
        '',
        f'class {cls_name}(Strategy):',
        '    params = dict(length=10)',
        '    def __init__(self):',
        '        self.kline = self.get_kline()',
        "        self.line = self.kline.close.rolling(10).mean(",
        f"            lines=['{line_name}'])",
        '        self.line.overlap = True',
        '',
        '    def next(self):',
        '        pass',
    ]), encoding='utf-8')
    return str(pathlib_path)


def test_realtime_replacing_strategy_clears_previous(tmp_path, monkeypatch):
    """重新加策略（另一个文件）→ 上一个策略的线 / runner 先清掉，布局保留 ✓"""
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))

    first = _strategy_file(tmp_path / 'personal' / 'strategies' / 'one.py',
                           'strategy_one', 'line_one')
    second = _strategy_file(tmp_path / 'personal' / 'strategies' / 'two.py',
                            'strategy_two', 'line_two')

    desk = _desk(tmp_path, monkeypatch)
    desk.futures = _fake_feed(np, pd)
    desk.feeds = [desk.futures]
    desk.offline = False
    tab = 'SHFE.demo01'
    desk.tabs[tab] = {'feed': desk.futures, 'cycle': 60,
                      'indicators': [{'key': 'MA'}],
                      'layout': {'cols': 2, 'rows': 1,
                                 'symbols': [tab, 'SHFE.demo02'],
                                 'cells': [{'symbol': tab,
                                            'indicators': [{'key': 'MA'}]},
                                           {'symbol': 'SHFE.demo02',
                                            'indicators': [{'key': 'RSI'}]}]}}

    desk._on_editor_add_indicator({'path': first})
    info = desk.tabs[tab]
    assert info['strategy']['name'] == 'strategy_one'
    assert info['strategy_items'], '第一个策略没加上'

    desk.sent.clear()
    desk._on_editor_add_indicator({'path': second})

    info = desk.tabs[tab]
    assert info['strategy']['name'] == 'strategy_two'
    labels = [str(item.get('label')) for item in info['strategy_items']]
    assert 'line_two' in labels, labels
    assert 'line_one' not in labels, labels           # 上一个策略清掉了 ✓
    # 布局 / 指标保留 ✓
    layout = info['layout']
    assert layout['symbols'] == [tab, 'SHFE.demo02']
    assert layout['cells'][1]['symbol'] == 'SHFE.demo02'
    assert [item['key'] for item in info['indicators']] == ['MA']
    con = ' '.join(str(item) for item in desk.sent)
    assert '"strategy":""' in con                     # 先清掉上一个策略 ✓
    assert '"cell":1' in con                          # 格 2 的策略线也清了 ✓


# ---------------------------------------------------------------- 本地图表
def test_local_page_strategy_cleared_across_cells(tmp_path, monkeypatch):
    """本地图表：本页**所有格**的旧策略都要清（布局 / 指标保留 ✓）"""
    desk = _desk(tmp_path, monkeypatch)
    desk._local_cell_names = {0: 'pta', 1: 'ma'}
    desk._local_strategies = {
        'pta': {'items': [{'key': 'editor:old:line:0'}],
                'name': 'old', 'path': '/tmp/old.py'},
        'ma': {'items': [{'key': 'editor:old:line:1'}],
               'name': 'old', 'path': '/tmp/old.py'},
        # 别的页面（不在本页格子里）→ 不能误删 ✓
        'au': {'items': [{'key': 'editor:other:line:0'}],
               'name': 'other', 'path': '/tmp/other.py'},
    }
    desk._local_strategy_of = {'pta': 'old', 'ma': 'old', 'au': 'other'}
    desk._local_runners = {'old': {'runner': object()}}
    desk._local_strategy_jobs = {'pta': 3, 'ma': 4}

    removed = desk._clear_local_page_strategies('pta')

    assert sorted(removed) == ['ma', 'pta']
    assert 'pta' not in desk._local_strategies
    assert 'ma' not in desk._local_strategies
    assert 'au' in desk._local_strategies             # 其它页面不动 ✓
    assert 'old' not in desk._local_runners
    assert 'pta' not in desk._local_strategy_of
    assert desk._local_strategy_jobs == {}
    store = desk.local_store()
    assert not (store.state.get('pta') or {}).get('strategy')
    assert not (store.state.get('ma') or {}).get('strategy')
    # 重推了空策略线（前端才会把旧线擦掉 ✓）
    con = ' '.join(str(item) for item in desk.sent)
    assert 'local_indicator' in con
    assert '"items":[]' in con
    # 自动布局会改写 `_local_cell_names` → 调用方要先取**旧**格子名 ✓
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'self._clear_local_page_strategies(name, also=page_names,' in backend


def test_local_cells_command_syncs_active_page(tmp_path, monkeypatch):
    """多开本地图表：切页时把「第几格 → 哪个 CSV」报给后端 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    desk._on_local_cells({'page': 'local:2',
                          'cells': ['pta', '', 'ma']})
    assert desk._local_cell_names == {0: 'pta', 2: 'ma'}
    desk._on_local_cells({'page': 'local:3', 'cells': {0: 'cu'}})
    assert desk._local_cell_names == {0: 'cu'}


def _patches_of(desk):
    import json
    out = []
    for script in desk.sent:
        text = str(script)
        if not text.startswith('window.__desk.applyPatch('):
            continue
        out.append(json.loads(text[len('window.__desk.applyPatch('):-2]))
    return out


def test_local_load_patch_carries_page(tmp_path, monkeypatch):
    """本地图表2 选 CSV → 补丁必须带 `page` ✓

    用户 2026-10-30 反馈：本地图表1 正常，**后面的副本选了数据后没有 K 线**。
    原因：`local_kline` 以前只按 CSV 名找页面，而这一页**还没加载过该 CSV**
    （`cellNames` 里没有它）→ 多开时找不到就整包丢掉 ✗
    """
    desk = _desk(tmp_path, monkeypatch)
    desk._on_local_load({'name': 'test', 'cell': 0, 'page': 'local:2'})

    patches = _patches_of(desk)
    kline = [item for item in patches if item['type'] == 'local_kline']
    assert kline and kline[0].get('page') == 'local:2'
    assert kline[0]['name'] == 'test' and kline[0]['bars']
    indicator = [item for item in patches if item['type'] == 'local_indicator']
    assert indicator and indicator[0].get('page') == 'local:2'
    assert desk._local_page_of('test') == 'local:2'

    # 没带 page 的加载（自动布局 / 策略）→ 发给当前活动的本地页 ✓
    desk._on_local_cells({'page': 'local:3', 'cells': ['pp2609_60']})
    desk.sent.clear()
    desk._on_local_load({'name': 'l2609_60', 'cell': 0})
    loaded = [item for item in _patches_of(desk)
              if item['type'] == 'local_kline']
    assert loaded and loaded[0].get('page') == 'local:3'
    desk._on_local_cells({'page': 'local:3', 'closed': True, 'cells': []})

    # 同一份 CSV 开到两个页面 → 不按页（按名字路由到两边 ✓）
    desk.sent.clear()
    desk._on_local_cells({'page': 'local:1', 'cells': ['test']})
    assert desk._local_page_of('test') == ''
    desk.sent.clear()
    desk._on_local_add_indicator({'symbol': 'test', 'key': 'MA', 'cell': 0})
    assert not any(item.get('page')
                   for item in _patches_of(desk) if item['type'] == 'local_indicator')

    # 关掉 local:2 → 又只剩一页 ✓
    desk._on_local_cells({'page': 'local:2', 'closed': True, 'cells': []})
    assert desk._local_page_of('test') == 'local:1'


def test_frontend_local_load_routes_by_page_id():
    app = _read('app.ts')
    page = _read('local-chart-page.ts')
    # 补丁优先按 `page`（页签 id）路由，其次才按 CSV 名 ✓
    assert 'private _localPageById(id: string): LocalChartPage | null {' in app
    assert app.count("this._localPageById(String(patch.page || ''))") >= 2
    # 选数据 / 自动加载都要带 page ✓
    assert "this.options.onCommand?.('local_load', {" in page
    assert "page: this.options.pageId || ''," in page
    assert 'pageId?: string;' in page
    assert "page: id });" in app


# ------------------------------------------------------------------ 前端
def test_frontend_multi_local_charts():
    app = _read('app.ts')
    page = _read('local-chart-page.ts')
    # ① 副本编号「本地图表N」，从 1 开始 ✓
    assert 'private localChartSeq = 0;' in app
    assert 'const seq = ++this.localChartSeq;' in app
    assert 'const label = `本地图表${seq}`;' in app
    assert 'newLocalChart(name = \'\'): string {' in app
    # ② ＋ 菜单 / 工作台「新建本地图表」= 新建副本 ✓
    assert 'run: () => this.newLocalChart(),' in app
    assert 'onNewLocal: () => this.newLocalChart(),' in app
    # ③ 补丁按 CSV 名路由到所有本地图表页（不再按 `local:<CSV>` 找页面 ✗）
    assert 'private _localPagesFor(name: string): LocalChartPage[] {' in app
    assert app.count('this._localPagesFor(') >= 2
    assert "pages.get(`local:${patch.symbol}`)" not in app
    assert "pages.get(`local:${name}`)" not in app
    # ④ 切页同步每格 CSV 给后端 ✓
    assert "this.send('local_cells', {" in app
    assert 'cells: page.cellNames.filter((name) => !!name),' in app
    # ⑤ 页面暴露每格数据名 ✓
    assert 'get cellNames(): string[] {' in page
    assert 'return this.cellSymbols.slice();' in page


def test_frontend_workspace_lists_local_pages():
    workspace = _read('workspace-pages.ts')
    app = _read('app.ts')
    # 左侧只列本地图表页，右侧是新建入口 ✓
    assert 'desk-workspace-body' in workspace
    assert "tabs.filter((tab) => tab.kind === 'local')" in workspace
    assert 'data-work-local' in workspace
    assert "refresh(): void { this.render(); }" in workspace
    # 新建 / 关闭 tab → 工作台列表跟着刷新 ✓
    assert app.count('this.workspacePage?.refresh();') >= 2
    # 打开工作台时也刷一次 ✓
    assert "show(): void {\n        this.element.style.display = 'block';\n        this.render();" in workspace


def test_frontend_replay_lab_picks_a_local_page():
    """回放实验室的两个按钮 → 弹菜单选本地图表（没有就新建一个 ✓）"""
    app = _read('app.ts')
    lab = _read('workspace-pages.ts')
    assert 'getLocals: () => [' in app
    assert "onOpenLocal: (id) => this.activate(id)," in app
    assert 'onStartReplay: (id) => this._startReplayOf(id),' in app
    assert 'private _startReplayOf(id: string): void {' in app
    assert 'onNewLocal: () => { this.newLocalChart(); },' in app
    # 菜单：列本地图表 + 最后一项「新建本地图表…」✓
    assert "if (!locals.length) {" in lab
    assert 'showMenuBelow(anchor, items);' in lab
    assert '＋ 新建本地图表…' in lab


def test_backend_has_local_cells_command():
    app = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'local_cells': self._on_local_cells," in app
    assert 'def _on_local_cells(self, payload=None) -> None:' in app
