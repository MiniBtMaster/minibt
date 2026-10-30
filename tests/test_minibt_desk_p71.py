"""P71：本地图表手数误报 0 / 模拟账户初始现金控件（下拉 + 手填）✓"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _ts(name):
    return (DESK_TS / name).read_text(encoding='utf-8')


# --------------------------------------------- ① 「价格 / 手数要大于 0」误报
def test_ticket_exposes_price_and_qty():
    ticket = _ts('replay-ticket.ts')
    assert 'qtyValue: () => {' in ticket
    # 手数为空也兜底 1（不能是 0 ✗）
    assert 'return Number.isFinite(raw) && raw > 0 ? raw : 1;' in ticket
    assert 'priceValue: () => {' in ticket


def test_local_chart_reads_shared_ticket_values():
    local = _ts('local-chart-page.ts')
    block = local.split('private _localOrder(', 1)[1].split('\n    }', 1)[0]
    assert 'this.localTicket?.priceValue()' in block
    assert 'this.localTicket?.qtyValue()' in block
    assert '|| 1;' in block
    # 手数输入框接上了（以前是 null → 永远读到 0 ✗）
    assert "const inputs = ticket.element.querySelectorAll('input[type=number]');" in local
    assert 'this.localQtyInput = (inputs[1] || null)' in local


def test_local_order_uses_one_lot_by_default(tmp_path, monkeypatch):
    """后端：手数 1 / 价格 4879 能正常成交 ✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.local_sim().set_price('rb2601', 4879.0, 0)
    desk._on_local_order({'symbol': 'rb2601', 'side': 'sell', 'qty': 1,
                          'price': 4879.0})
    last = [json.loads(item.split('applyPatch(', 1)[1].rstrip(');'))
            for item in desk.sent
            if isinstance(item, str) and '"type":"local_account"' in item][-1]
    rows = last['tables']['positions']['rows']
    assert rows[0][:3] == ['rb2601', '空', '1']
    assert not any('大于 0' in str(item) for item in desk.sent)


# --------------------------------------------- ② 初始现金：下拉 + 手填
def test_cash_presets():
    page = _ts('settings-page.ts')
    assert 'export const CASH_PRESETS' in page
    for label in ("'10 万'", "'20 万'", "'30 万'", "'50 万'", "'80 万'",
                  "'100 万'"):
        assert label in page, label
    assert 'value: 1000000' in page


def test_cash_control_select_and_manual():
    page = _ts('settings-page.ts')
    assert "custom.textContent = '自定义';" in page
    assert 'private _applyCash(value: number): void' in page
    # 选下拉 → 填进输入框 + 应用 ✓
    assert 'cash.value = String(picked);      // 选了下拉 → 填进输入框 ✓' in page
    assert "this._button('应用', () => {" in page
    # 手填回车 / 失焦也能应用 ✓
    assert "if (event.key === 'Enter') this._applyCash(Number(cash.value));" in page
    assert 'this.options.onSetting(\'sim_initial_cash\', amount);' in page


def test_backend_apply_sim_setting(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    sim = desk.local_sim()
    sim.set_price('X', 100.0, 2, bar='t1')
    sim.order('X', 'buy', 1, 100.0)

    desk.replay_symbols.add('X')
    desk._last_rows['X'] = {'last': 100.0}
    desk._on_set_setting({'key': 'sim_initial_cash', 'value': 300000})
    kinds = [json.loads(item.split('applyPatch(', 1)[1].rstrip(');'))
             .get('type') for item in desk.sent if isinstance(item, str)]
    assert 'sim_analysis' in kinds
    assert 'local_account' in kinds          # 本地图表账户也刷了 ✓
    assert 'account' in kinds                # 回放账户也刷了 ✓
    assert sim.initial_cash == 300000.0
    assert sim.positions == {}               # 换了钱 → 重置 ✓

    desk._on_set_setting({'key': 'sim_fee_mode', 'value': 'percent'})
    desk._on_set_setting({'key': 'sim_fee_value', 'value': 0.8})
    assert sim.settings()['fee_mode'] == 'percent'
    assert sim.settings()['fee_value'] == 0.8

    # 非法值：只提示，不改设置 ✓
    desk._on_set_setting({'key': 'sim_fee_value', 'value': -5})
    assert sim.settings()['fee_value'] == 0.8
    desk._on_set_setting({'key': 'sim_initial_cash', 'value': 0})
    assert sim.initial_cash == 300000.0
    toasts = [item for item in desk.sent
              if isinstance(item, str) and '"type":"toast"' in item]
    assert toasts


def test_sim_reset_uses_setting(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    up.set_setting('sim_initial_cash', 800000)
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    sim = desk.local_sim()
    assert sim.initial_cash == 800000.0
    sim.set_price('X', 100.0, 2, bar='t1')
    sim.order('X', 'buy', 1, 100.0)
    desk._on_sim_reset({})
    assert sim.positions == {}
    payload = [json.loads(item.split('applyPatch(', 1)[1].rstrip(');'))
               for item in desk.sent
               if isinstance(item, str) and '"type":"sim_analysis"' in item][-1]
    assert payload['summary']['initial_cash'] == 800000.0
