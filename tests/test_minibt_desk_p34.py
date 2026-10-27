"""P34：分笔现手（累计差）+ 透明买卖盘（市价调仓）✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, user_prefs

    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.trading = True
    return desk


# ------------------------------------------------------------ 分笔「现手」
class _TickApi:
    def get_tick_serial(self, symbol):
        pd = pytest.importorskip('pandas')
        # 累计成交量 100→105→105→112→112→120（第 3、5 笔无成交）
        return pd.DataFrame({
            'datetime': [(1_700_000_000 + i * 3) * 10 ** 9 for i in range(6)],
            'last_price': [10.0, 10.1, 10.1, 10.0, 10.0, 10.2],
            'volume': [100, 105, 105, 112, 112, 120],
            'bid_price1': [9.9] * 6, 'ask_price1': [10.3] * 6,
        })


class _Feed:
    kind = 'futures'

    def __init__(self):
        self.api = _TickApi()

    def available(self):
        return True


def test_tick_volume_is_the_delta_not_cumulative(tmp_path, monkeypatch):
    """天勤 `volume` 是**当日累计** → 必须算差值（用户实测：每笔都在累加 ✗）"""
    desk = _desk(tmp_path, monkeypatch)
    rows = desk._book_ticks(_Feed(), 'SHFE.demo01')
    volumes = [row['volume'] for row in rows]
    assert volumes == [8.0, 7.0, 5.0]           # 最新的在最上面 ✓
    assert sum(volumes) == 20                    # 100 → 120 共 20 手 ✓
    assert all(0 < value < 100 for value in volumes)


def test_tick_time_uses_beijing_offset():
    from minibt.desk.app import TZ_HOURS, _clock_of

    assert TZ_HOURS == 8
    # epoch 1700000000 = 2023-11-14 22:13:20 UTC → 北京 06:13:20 ✓
    assert _clock_of(1_700_000_000 * 10 ** 9, TZ_HOURS) == '06:13:20'
    assert _clock_of(1_700_000_000 * 10 ** 9, 0) == '22:13:20'


# ------------------------------------------------------------ 买卖盘：市价调仓
class _Trader:
    def __init__(self):
        self.targets = []
        self.net = (0, 0)

    def ready(self, symbol=''):
        return True

    def _position(self, symbol):
        return {'pos_long': self.net[0], 'pos_short': self.net[1]}

    def _set_target(self, symbol, target):
        self.targets.append(target)
        return f'{symbol} 目标仓位 → {target}'

    def account_label(self, symbol=''):
        return '天勤模拟'

    def is_real(self, symbol=''):
        return False


def _order(desk, side, qty=2, long=0, short=0):
    from minibt.desk import protocol

    trader = desk.trader
    trader.targets.clear()
    trader.net = (long, short)
    desk.handle(protocol.encode_command({'cmd': 'ticket_order', 'payload': {
        'symbol': 'SHFE.ag2612', 'side': side, 'qty': qty}}))
    return trader.targets[-1] if trader.targets else None


def test_ticket_order_uses_target_position(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.trader = _Trader()
    # 无仓：买入加多 / 卖出加空 ✓
    assert _order(desk, 'buy', 2) == 2
    assert _order(desk, 'sell', 2) == -2
    # 多头：买入继续加多；卖出 = 全部平仓（目标 0 ✓）
    assert _order(desk, 'buy', 2, long=5) == 7
    assert _order(desk, 'sell', 2, long=5) == 0
    # 空头：卖出继续加空；买入 = 全部平仓 ✓
    assert _order(desk, 'sell', 2, short=3) == -5
    assert _order(desk, 'buy', 2, short=3) == 0


def test_ticket_order_requires_trading(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.trader = _Trader()
    desk.trading = False
    trader = desk.trader
    trader.targets.clear()
    from minibt.desk import protocol
    desk.handle(protocol.encode_command({'cmd': 'ticket_order', 'payload': {
        'symbol': 'SHFE.ag2612', 'side': 'buy', 'qty': 1}}))
    assert trader.targets == []
    assert any('交易未启用' in str(row) for row in desk.sent)


# ------------------------------------------------------------ 买卖盘 UI
def test_ticket_is_transparent_and_minimal():
    css = _read('jslib/src/desk/desk.css')
    block = css.split('.desk-ticket {', 1)[1].split('}', 1)[0]
    assert 'background: transparent' in block
    assert 'border: none' in block
    assert 'pointer-events: none' in block          # 不挡十字线 ✓
    row = css.split('.desk-ticket-row {', 1)[1].split('}', 1)[0]
    assert 'pointer-events: auto' in row            # 只有三格可点 ✓
    side = css.split('.desk-ticket-side {', 1)[1].split('}', 1)[0]
    assert 'background: transparent' in side

    page = _read('jslib/src/desk/chart-page.ts')
    # 只有三个格子：没有手数 / 价格 / 档位输入 ✓
    assert "box.append(row);" in page
    assert 'desk-ticket-qty' not in page
    assert 'desk-ticket-foot' not in page
    assert 'desk-ticket-click-orders' not in page
    assert "'ticket_order'" in page
    # 手数取二级报价 ✓
    assert 'const qty = this.ticket?.qtyValue() || this.orderQty' in page
    ticket = _read('jslib/src/desk/replay-ticket.ts')
    assert 'qtyValue' in ticket
