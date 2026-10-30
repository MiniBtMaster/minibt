"""配对交易回放：本地模拟账户必须**跟着回放进度**成交 / 更新现价。

用户反馈（test_2.py 双合约卡尔曼）：
* 点回放（还没点播放）就成交了一大批历史目标仓位 ✗
* 两个合约的「现价」和图表对不上、轮流跳 ✗
* 账户进度和回放进度不同步 ✗

这里用 FakeRunner 直接验证后端逻辑（不依赖具体策略 / CSV）：
1. `reset=True, advance=False` → 只对齐价格，不成交；
2. `advance=True` → 只推进到前端给的那一根；
3. 多合约目标仓位各自按**下单那根 K 线**的收盘价成交；
4. 同一根重复推送不会重复成交。
"""
from __future__ import annotations

import json

import pandas as pd


class FakeRunner:
    """最小的 StrategyRunner 替身（只实现回放用到的方法 ✓）"""

    def __init__(self, plan=None):
        self.orders = []
        self.targets = []
        self._replay_index = -1
        self.reset_calls = []
        self.steps = []
        #: ``{bar_index: [(symbol, target), …]}``
        self.plan = dict(plan or {})

    def reset_replay(self, index: int = 0) -> None:
        self.reset_calls.append(int(index))
        self.orders = []
        self.targets = []
        self._replay_index = int(index)

    def step_one(self) -> bool:
        index = int(self._replay_index) + 1
        self._replay_index = index
        self.steps.append(index)
        for symbol, target in self.plan.get(index, []):
            self.targets.append({'symbol': symbol, 'target': float(target),
                                 'index': index,
                                 'serial': len(self.targets)})
        return True


def _frame(closes):
    return pd.DataFrame({
        'datetime': pd.date_range('2026-01-01', periods=len(closes),
                                  freq='min'),
        'close': [float(value) for value in closes],
    })


def _desk(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.local_sim().configure(initial_cash=100000.0, fee_mode='fixed',
                               fee_value=0.0)
    return desk


def _setup(desk, runner):
    frames = [('A', _frame([100, 101, 102, 103, 104, 105, 106, 107, 108])),
              ('B', _frame([200, 201, 202, 203, 204, 205, 206, 207, 208]))]
    desk._local_cell_names = {0: 'A', 1: 'B'}
    desk.last_symbol = 'A'
    desk._local_runners = {'S': {
        'runner': runner, 'orders': 0, 'targets': 0,
        'frames': frames, 'name': 'A',
    }}
    return frames


def _payload(index, advance, reset=False):
    frames = [('A', _frame([100, 101, 102, 103, 104, 105, 106, 107, 108])),
              ('B', _frame([200, 201, 202, 203, 204, 205, 206, 207, 208]))]
    cells = []
    for symbol, frame in frames:
        row = frame.iloc[index]
        cells.append({
            'symbol': symbol,
            'price': float(row['close']),
            'time': int(pd.Timestamp(row['datetime']).value // 10**9),
            'index': index,
        })
    return {'symbol': 'A', 'price': cells[0]['price'],
            'time': cells[0]['time'], 'index': index,
            'cells': cells, 'advance': advance, 'reset': reset}


def _patches(desk):
    return [json.loads(item.split('applyPatch(', 1)[1].rstrip(');'))
            for item in desk.sent
            if isinstance(item, str) and 'applyPatch(' in item]


def test_enter_replay_does_not_trade_but_syncs_prices(tmp_path, monkeypatch):
    """点回放 = 只对齐两个合约的现价；历史 targets 不能落地 ✗"""
    desk = _desk(tmp_path, monkeypatch)
    runner = FakeRunner()
    _setup(desk, runner)
    # 模拟 overlay 跑完整历史留下的 targets（这些必须被丢掉）
    runner.targets = [{'symbol': 'A', 'target': 5.0, 'index': 0},
                      {'symbol': 'B', 'target': -5.0, 'index': 0}]
    desk._on_replay_price(_payload(3, advance=False, reset=True))
    sim = desk.local_sim()
    assert runner.reset_calls == [3]
    assert runner.targets == []
    assert sim.trades == [] and sim.positions == {}
    # 两个合约都对齐到第 3 根收盘价 ✓
    assert sim._price('A') == 103.0
    assert sim._price('B') == 203.0
    info = desk._local_runners['S']
    assert info['replay_index'] == 3
    assert info['targets'] == 0


def test_advance_fills_at_current_replay_bar(tmp_path, monkeypatch):
    """播放/前进一根才成交；价格 = **当前回放那根**的收盘价 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    runner = FakeRunner(plan={5: [('A', 1.0)], 6: [('A', 0.0)]})
    _setup(desk, runner)
    desk._on_replay_price(_payload(3, advance=False, reset=True))
    # 同一根重复推送（暂停 / 重绘）→ 不推进、不成交
    desk._on_replay_price(_payload(3, advance=False))
    assert runner.steps == []
    desk._on_replay_price(_payload(4, advance=True))
    assert runner.steps == [4]
    assert desk.local_sim().trades == []
    # 第 5 根：开多 1 手 @ 105
    desk._on_replay_price(_payload(5, advance=True))
    sim = desk.local_sim()
    assert len(sim.trades) == 1
    assert sim.trades[0]['symbol'] == 'A'
    assert sim.trades[0]['side'] == 'buy'
    assert sim.trades[0]['price'] == 105.0
    assert sim.positions['A']['long'] == 1.0
    # 第 6 根：平仓 @ 106 → 赚 1
    desk._on_replay_price(_payload(6, advance=True))
    assert len(sim.trades) == 2
    assert sim.trades[-1]['price'] == 106.0
    assert sim.positions['A']['long'] == 0.0
    assert sim.realized == 1.0
    # 同一根再推一次（前端重绘）→ 不重复成交 ✓
    desk._on_replay_price(_payload(6, advance=True))
    assert len(sim.trades) == 2


def test_pair_targets_fill_on_their_own_bars(tmp_path, monkeypatch):
    """配对交易：同一根里 A 多 / B 空，各按自己的收盘价成交 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    runner = FakeRunner(plan={5: [('A', 2.0), ('B', -3.0)]})
    _setup(desk, runner)
    desk._on_replay_price(_payload(3, advance=False, reset=True))
    desk._on_replay_price(_payload(5, advance=True))
    sim = desk.local_sim()
    assert sim.positions['A']['long'] == 2.0
    assert sim.positions['A']['avg_long'] == 105.0
    assert sim.positions['B']['short'] == 3.0
    assert sim.positions['B']['avg_short'] == 205.0
    # 第 6 根时两个合约的「现价」都跟着回放走（不再轮流 / 停在旧值）✓
    desk._on_replay_price(_payload(6, advance=False))
    assert sim._price('A') == 106.0
    assert sim._price('B') == 206.0
    rows = sim.payload('A')['tables']['positions']['rows']
    assert rows[0][0] == 'A' and rows[0][4] == '106.00'


def test_local_active_tells_frontend_which_contract_and_price(tmp_path,
                                                              monkeypatch):
    """点格子 → 交易面板搜索框 / 价格框切到那个合约 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    _setup(desk, FakeRunner())
    desk.local_sim().set_price('B', 207.0, 2)
    desk._on_local_active({'cell': 1, 'symbol': 'B', 'name': 'B'})
    last = [item for item in _patches(desk)
            if item.get('type') == 'local_account'][-1]
    assert last['symbol'] == 'B'
    assert last['active'] is True
    assert last['last_price'] == 207.0


def test_backward_restart_resets_instead_of_catching_up(tmp_path, monkeypatch):
    """播到末尾后再点 ▶（Replay 从 30% 重来）不能补做中间几百根 ✗"""
    desk = _desk(tmp_path, monkeypatch)
    runner = FakeRunner(plan={5: [('A', 1.0)]})
    _setup(desk, runner)
    desk._on_replay_price(_payload(3, advance=False, reset=True))
    desk._on_replay_price(_payload(6, advance=True))
    assert runner.steps == [4, 5, 6]
    # 往回跳到第 2 根（模拟 start() 的内部 seek）→ 重新开始，不补 3..1
    desk._on_replay_price(_payload(2, advance=True))
    assert runner.steps == [4, 5, 6]
    assert desk._local_runners['S']['replay_index'] == 2
    desk._on_replay_price(_payload(3, advance=True))
    assert runner.steps == [4, 5, 6, 3]


def test_replay_pushes_position_lines_and_sim_analysis(tmp_path, monkeypatch):
    """两个合约的持仓线补丁都带 cell / long|short；设置页分析也要实时推 ✓"""
    desk = _desk(tmp_path, monkeypatch)
    runner = FakeRunner(plan={5: [('A', 2.0), ('B', -3.0)]})
    _setup(desk, runner)
    desk._on_replay_price(_payload(3, advance=False, reset=True))
    desk._on_replay_price(_payload(5, advance=True))
    patches = _patches(desk)
    positions = [item for item in patches if item.get('type') == 'position']
    assert any(item.get('symbol') == 'A' and item.get('cell') == 0
               and item.get('long') for item in positions)
    assert any(item.get('symbol') == 'B' and item.get('cell') == 1
               and item.get('short') for item in positions)
    sims = [item for item in patches if item.get('type') == 'sim_analysis']
    assert sims, '有持仓时必须推 sim_analysis（设置页权益实时更新）'
    balance_open = sims[-1]['summary']['balance']
    # 下一根价格变化（持仓不动）→ 权益变化，并且仍会推 sim_analysis ✓
    desk._on_replay_price(_payload(6, advance=False))
    sims = [item for item in _patches(desk)
            if item.get('type') == 'sim_analysis']
    assert sims[-1]['summary']['balance'] != balance_open
    assert sims[-1]['equity'], '权益曲线也要有数据点'
