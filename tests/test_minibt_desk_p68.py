"""P68：本地图表回放视窗 / 本地图表编辑器 / 回放切本地模拟账户 ✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(path):
    return (ROOT / path).read_text(encoding='utf-8')


# ------------------------------------------------------- ① 本地图表回放视窗
def test_local_replay_viewport_matches_chart():
    local = (DESK_TS / 'local-chart-page.ts').read_text(encoding='utf-8')
    block = local.split('private _syncReplayViewport', 1)[1].split(
        '\n    private ', 1)[0]
    # 播放中不动视窗（LWC 自己跟随）；只在首次/seek 摆「整段 + 右侧留白」✓
    assert 'if (reset || prev === 0 || Math.abs(current - prev) > 1)' in block
    assert 'to: current - 1 + 3' in block
    assert 'from: range.from + 1' not in block
    assert 'scrollToRealTime' not in block


# ------------------------------------------------------- ② 本地图表编辑器
def test_local_chart_has_editor():
    local = (DESK_TS / 'local-chart-page.ts').read_text(encoding='utf-8')
    assert "import { EditorPanel } from './editor-panel';" in local
    assert 'private _ensureEditor(): EditorPanel' in local
    assert 'get editorPanel(): EditorPanel | null' in local
    # 页签回调 + 最大化 + 分隔条都在 ✓
    assert 'this.dock.onEditorOpen = () => {' in local
    assert 'this.dock.onTabChange = (tab) => {' in local
    assert 'this.dock.onToggleMaximize = () => this.toggleDockMaximize();' in local
    assert 'toggleDockMaximize(force?: boolean): boolean' in local
    assert 'private _ensureDockSplitter(): void' in local
    assert "'交易/编辑器'" in local
    # 编辑器知道自己是本地图表（加到图表走 local_add_indicator ✓）
    assert 'local: true,' in local
    assert 'symbolForCell(' in local
    app = (DESK_TS / 'app.ts').read_text(encoding='utf-8')
    assert "const page = (this.pages.get(this.activeId) || null) as" in app


def test_editor_panel_supports_local():
    panel = (DESK_TS / 'editor-panel.ts').read_text(encoding='utf-8')
    assert 'local?: boolean;' in panel
    assert 'symbol?: () => string;' in panel
    assert 'local: !!this.options.local,' in panel


def test_local_add_indicator_from_editor(tmp_path, monkeypatch):
    """本地图表「加到图表」→ `local_add_indicator`（不进实时 tabs ✓）"""
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    made = pi.create_file('indicator', 'loc_ma')

    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    calls = []
    monkeypatch.setattr(desk, '_on_local_add_indicator',
                        lambda payload=None: calls.append(payload or {}))
    desk._on_editor_add_indicator({'path': made['path'], 'local': True,
                                   'symbol': 'local_demo'})
    assert calls and calls[0]['symbol'] == 'local_demo'
    assert str(calls[0]['key']).startswith('pi:')
    assert desk.tabs == {}                       # 没碰实时 tab ✓


# ------------------------------------------------------- ③ 回放切本地模拟账户
def _desk(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.trading = True
    return desk


def test_replay_uses_local_sim_account(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    symbol = 'SHFE.ag2612'
    assert not desk.is_replaying(symbol)

    # 进入回放 → 交易账户变成本地模拟
    desk.replay_symbols.add(symbol)
    desk._last_rows[symbol] = {'last': 13974.0, 'price_tick': 1.0}
    assert desk.is_replaying(symbol)
    state = desk.trading_state(symbol)
    assert state['kind'] == 'replay' and state['enabled'] is True
    assert state['real'] is False
    assert state['account'] == '本地模拟（回放）'
    payload = desk.account_payload(symbol=symbol)
    assert payload['kind'] == 'replay'
    assert payload['labels'] == ['本地模拟（回放）']

    trader = desk.trading_view()
    assert trader.ready(symbol) and not trader.is_real(symbol)
    trader.place(symbol, 'buy', 2, 13974.0)
    payload = desk.account_payload(symbol=symbol)
    rows = payload['tables']['positions']['rows']
    assert rows and rows[0][1] == '多'          # 多单 ✓

    # 平仓 → 持仓清空
    trader.action('close', symbol)
    payload = desk.account_payload(symbol=symbol)
    assert payload['tables']['positions']['rows'] == []

    # 退出回放 → 回到天勤模拟
    desk.replay_symbols.discard(symbol)
    assert not desk.is_replaying(symbol)
    assert desk.trading_state(symbol)['account'] != '本地模拟（回放）'


def test_replay_price_feeds_sim(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    symbol = 'SHFE.ag2612'
    desk.replay_symbols.add(symbol)
    desk._on_replay_price({'symbol': symbol, 'price': 13900.0})
    sim = desk.replay_sim(symbol)
    assert sim._price(symbol) == 13900.0      # 回放价写进去了 ✓


def test_replay_price_sent_from_frontend():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    assert "onCommand?.('replay_price'" in page
    assert "'replay_price': self._on_replay_price" in _read(
        'minibt/desk/app.py')
