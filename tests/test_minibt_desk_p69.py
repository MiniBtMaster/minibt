"""P69：回放本地模拟交易面板 / 记住视窗 / 右键「全部K线·最新K线」✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _ts(name):
    return (DESK_TS / name).read_text(encoding='utf-8')


# ---------------------------------------------------- ① 回放显示本地模拟交易
def test_shared_replay_ticket_exists():
    ticket = _ts('replay-ticket.ts')
    assert 'export function buildReplayTicket' in ticket
    for label in ("'买入'", "'卖出'", "'平仓'", "'市价平仓'",
                  "'反手'", "'撤单'"):
        assert label in ticket, label
    assert "'价格'" in ticket and "'手数'" in ticket
    # 本地图表的提示（回放时也有效 ✓）
    assert 'setPrice' in ticket and 'setNet' in ticket


def test_local_chart_uses_shared_ticket():
    local = _ts('local-chart-page.ts')
    assert "from './replay-ticket'" in local
    assert 'buildReplayTicket({' in local
    # 本地图表自己的控件不再手搓 ✗（改用共用组件 ✓）
    assert "buy.textContent = '买入'" not in local


def test_chart_page_has_shared_ticket():
    """P79：交易面板**实时也在**（本地模拟 / 天勤 / 实盘共用 ✓）"""
    page = _ts('chart-page.ts')
    assert "from './replay-ticket'" in page
    assert 'private _ensureDockTicket(' in page
    assert 'dock.setTicket(ticket.element)' in page
    # 回放 → 交易账户页 + 持仓表
    assert "this.dock.setTab('account');" in page
    # 进 / 出回放都只是换模式，不再把面板拆掉 ✓
    assert '_ensureDockTicket(true)' in page
    assert '_ensureDockTicket(false)' in page


def test_backend_replay_trade_commands():
    app = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'replay_order': self._on_replay_order" in app
    assert "'replay_action': self._on_replay_action" in app
    assert "'replay_price': self._on_replay_price" in app


def test_replay_order_and_action_flow(tmp_path, monkeypatch):
    import json
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    symbol = 'SHFE.ag2612'
    desk.replay_symbols.add(symbol)
    desk._last_rows[symbol] = {'last': 13974.0}

    def patches():
        out = []
        for item in desk.sent:
            if isinstance(item, str) and '"type":"account"' in item:
                body = item.split('applyPatch(', 1)[1].rstrip(');')
                out.append(json.loads(body))
        return out

    desk._on_replay_order({'symbol': symbol, 'side': 'buy', 'qty': 2,
                           'price': 13974.0})
    rows = patches()[-1]['tables']['positions']['rows']
    assert rows and rows[0][1] == '多' and rows[0][2] == '2'
    assert patches()[-1]['labels'] == ['本地模拟（回放）']

    desk._on_replay_action({'symbol': symbol, 'action': 'reverse'})
    rows = patches()[-1]['tables']['positions']['rows']
    assert rows and rows[0][1] == '空'          # 反手 ✓

    desk._on_replay_action({'symbol': symbol, 'action': 'all'})
    assert patches()[-1]['tables']['positions']['rows'] == []


# ---------------------------------------------------- ② 记住 / 恢复可视范围
def test_chart_page_remembers_view_range():
    page = _ts('chart-page.ts')
    assert 'private _saveViewRanges(): void' in page
    assert 'private _restoreViewRangesSoon(): void' in page
    assert 'getVisibleLogicalRange' in page
    assert 'setVisibleLogicalRange?.(range)' in page
    # 进回放记住 / 退出回放恢复 ✓
    assert 'this._saveViewRanges();           // ★' in page
    assert 'this._restoreViewRangesSoon();    // ★' in page


def test_local_chart_remembers_view_range():
    local = _ts('local-chart-page.ts')
    assert 'private _saveViewRanges(): void' in local
    assert 'private _restoreViewRangesSoon(): void' in local
    assert 'this._saveViewRanges();       // ★' in local
    # 退出回放不再 `_fitLocalRange`（那会缩成最近 300 根 ✗）
    block = local.split('    exitReplay(): void {', 1)[1].split('\n    }', 1)[0]
    assert '_restoreViewRangesSoon' in block
    assert 'this._fitLocalRange(0);' not in block


# ---------------------------------------------------- ③ 右键 全部K线/最新K线
def test_context_menu_has_fit_and_last_bars():
    menu = _ts('chart-context-menu.ts')
    assert "onFitAll?: () => void;" in menu
    assert "onLastBars?: () => void;" in menu
    assert "'全部K线'" in menu
    assert '最新K线（300 根）' in menu


def test_fit_and_last_bars_implemented():
    page = _ts('chart-page.ts')
    assert 'fitAllBars(cell = -1): void' in page
    assert 'showLastBars(count = 300, cell = -1): void' in page
    assert 'fitContent?.()' in page
    assert 'onFitAll: () => this.fitAllBars(),' in page
    assert 'onLastBars: () => this.showLastBars(),' in page

    local = _ts('local-chart-page.ts')
    assert 'fitAllBars(cell = 0): void' in local
    assert 'showLastBars(count = 300, cell = 0): void' in local
    assert 'onFitAll: () => this.fitAllBars(' in local
