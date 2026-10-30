"""策略实盘：**多策略**同时跑 + 策略管理里的三件套（新K线next / 运行next / 删除）✓

用户 2026-10-28 反馈：

1. 启动后「停止实盘」是禁用的 → 原因是 `app.ts::_forEditors()` 只遍历
   `LocalChartPage`，看盘窗口（`ChartPage`）的编辑器永远收不到
   `strategy_live` 状态；现在两类页面都转发 `setStrategyLive` ✓；
2. 策略实盘要能**同时跑多个**（一个文件一个子进程）；
3. 这些实盘策略要出现在「策略管理」里，并且能改「新K线next / 运行next」、
   能删除（= 停止该策略）。开关通过控制文件（`live_control`）传给子进程 ✓。
"""
from __future__ import annotations

import pathlib
import types

import pytest

from minibt.desk import live_control
from minibt.desk.app import Desk

ROOT = pathlib.Path(__file__).resolve().parents[1]
JSLIB = ROOT / 'jslib' / 'src' / 'desk'


def _read(name: str) -> str:
    return (JSLIB / name).read_text(encoding='utf-8')


# ------------------------------------------------------------------ 控制文件
@pytest.fixture()
def control(tmp_path, monkeypatch):
    target = tmp_path / 'live_control.json'
    monkeypatch.setattr(live_control, 'control_file', lambda: str(target))
    live_control._CACHE.update({'stamp': None, 'data': {}})
    yield live_control
    live_control._CACHE.update({'stamp': None, 'data': {}})


def test_control_file_roundtrip(control):
    path = 'C:/tmp/strategies/a.py'
    assert control.read(path) == {'next_on_new_bar': True, 'run_next': True}
    control.write(path, {'run_next': False})
    assert control.read(path) == {'next_on_new_bar': True, 'run_next': False}
    control.set_value(path, 'next_on_new_bar', False)
    assert control.read(path) == {'next_on_new_bar': False, 'run_next': False}
    control.clear(path)
    assert control.read(path) == {'next_on_new_bar': True, 'run_next': True}


# --------------------------------------------------------------- 子进程门控
def test_gate_honours_new_bar_and_run_next(control, tmp_path):
    """门控包的是 `_execute_live_trading()`（不是 `step`）✓

    用户策略写的是 ``def next(self)``，minibt 会把它绑定到**实例**的
    ``self.step``（`_prepare_before_strategy_start`）→ 只在类上包 `step`
    会被实例属性盖掉（2026-10-29 实测：两个开关点了没反应 ✗）。
    """
    from minibt.desk.live_runner import _install_control

    steps = []
    updates = []

    class FakeKline:
        datetime = types.SimpleNamespace(iloc=[0])

    class FakeStrategy:
        _btklinedataset = {'k1': FakeKline()}

        def _execute_live_trading(self, *args, **kwargs):
            updates.append(1)             # 指标 / K 线更新（永远都做 ✓）
            self.step()                   # 交易逻辑（受门控 ✓）
            return self

        def next(self):
            steps.append(len(steps))
            return 'ran'

    file = str(tmp_path / 'a.py')
    _install_control([FakeStrategy], file)
    strategy = FakeStrategy()
    strategy.step = strategy.next        # minibt 的实例级绑定（关键 ✓）

    # ① 新K线next（默认开）→ 同一根 K 线只跑一次 ✓
    FakeStrategy._btklinedataset['k1'].datetime = types.SimpleNamespace(
        iloc=[1700000000000000000])
    assert strategy._execute_live_trading() is strategy
    assert strategy._execute_live_trading() is strategy   # 同一根：只更新指标
    assert len(steps) == 1
    assert len(updates) == 2            # 指标更新没被跳过 ✓
    # ② 新 K 线 → 再跑一次 ✓
    FakeStrategy._btklinedataset['k1'].datetime = types.SimpleNamespace(
        iloc=[1700000060000000000])
    assert strategy._execute_live_trading() is strategy
    assert len(steps) == 2
    # ③ 运行next=False → 只算指标，不跑交易逻辑 ✓
    control.set_value(file, 'run_next', False)
    FakeStrategy._btklinedataset['k1'].datetime = types.SimpleNamespace(
        iloc=[1700000120000000000])
    assert strategy._execute_live_trading() is strategy
    assert len(steps) == 2
    assert len(updates) == 4            # 每次调用都更新指标 ✓
    # ④ 再打开 → step 已还原，能继续跑 ✓
    control.set_value(file, 'run_next', True)
    FakeStrategy._btklinedataset['k1'].datetime = types.SimpleNamespace(
        iloc=[1700000180000000000])
    assert strategy._execute_live_trading() is strategy
    assert len(steps) == 3
    # ⑤ 关掉「新K线next」→ 每个 tick 都跑 ✓
    control.set_value(file, 'next_on_new_bar', False)
    assert strategy._execute_live_trading() is strategy
    assert strategy._execute_live_trading() is strategy
    assert len(steps) == 5


def test_gate_survives_instance_rebuild(control, tmp_path):
    """minibt 实盘会重建策略实例 → 「最后一根 K 线」必须按**文件**记 ✓"""
    from minibt.desk.live_runner import _install_control

    steps = []

    class FakeKline:
        datetime = types.SimpleNamespace(iloc=[1])

    class FakeStrategy:
        _btklinedataset = {'k1': FakeKline()}

        def _execute_live_trading(self, *args, **kwargs):
            self.step()
            return self

        def next(self):
            steps.append(1)

    file = str(tmp_path / 'a.py')
    _install_control([FakeStrategy], file)

    for _ in range(3):                   # 每拍都新建实例（模拟 minibt 行为）
        strategy = FakeStrategy()
        strategy.step = strategy.next
        strategy._execute_live_trading()
    assert len(steps) == 1               # 同一根 K 线只跑一次 ✓

    FakeStrategy._btklinedataset['k1'].datetime = types.SimpleNamespace(iloc=[2])
    strategy = FakeStrategy()
    strategy.step = strategy.next
    strategy._execute_live_trading()
    assert len(steps) == 2               # 新 K 线 → 再跑 ✓


# --------------------------------------------------------------- 多个实盘
class FakeLive:
    """假的 StrategyLive：不真的起子进程 ✓"""

    instances: list['FakeLive'] = []

    def __init__(self, desk, file, params=None, config=None):
        self.desk = desk
        self.file = str(file)
        self.params = params or {}
        self.next_on_new_bar = bool((config or {}).get('next_on_new_bar', True))
        self.run_next = bool((config or {}).get('run_next', True))
        self.retry = False
        self.on_change = None
        self.started = 0
        self.stopped = 0
        self.running = False
        FakeLive.instances.append(self)

    def start(self):
        self.running = True
        self.started += 1
        return self.status()

    def stop(self):
        self.running = False
        self.stopped += 1
        return self.status()

    def status(self):
        return {
            'file': self.file,
            'name': pathlib.Path(self.file).stem,
            'running': self.running,
            'pid': 4321 if self.running else 0,
            'next_on_new_bar': self.next_on_new_bar,
            'run_next': self.run_next,
            'error': '',
        }


@pytest.fixture()
def desk(tmp_path, monkeypatch, control):
    monkeypatch.setattr('minibt.desk.strategy_live.StrategyLive', FakeLive)
    FakeLive.instances = []
    monkeypatch.setattr('minibt.desk.user_prefs.settings', lambda: {})
    instance = Desk(offline=True, allow_trading=True)
    instance.sent = []
    instance.sender = instance.sent.append
    instance._booted = True
    yield instance


def _strategy_file(tmp_path, name: str) -> str:
    path = tmp_path / name
    path.write_text('from minibt import *\n', encoding='utf-8')
    return str(path)


def test_multiple_live_strategies_run_together(desk, tmp_path):
    first = _strategy_file(tmp_path, 'a.py')
    second = _strategy_file(tmp_path, 'b.py')

    desk._on_strategy_live_start({'file': first, 'confirm': True})
    desk._on_strategy_live_start({'file': second, 'confirm': True})

    lives = desk._live_map()
    assert len(lives) == 2
    items = desk.strategy_live_items()
    assert len(items) == 2
    # `desk.sent` 里是 `encode_patch` 之后的 JS 脚本 → 按文本判断 ✓
    scripts = [str(item) for item in desk.sent]
    assert any('strategy_live' in text and 'items' in text
               for text in scripts)
    assert all(item['running'] for item in desk.strategy_live_items())

    # 同一文件重复启动 → 不会起第二个 ✓
    desk._on_strategy_live_start({'file': first, 'confirm': True})
    assert len(desk._live_map()) == 2
    assert len(FakeLive.instances) == 2


def test_stop_all_stops_and_removes_every_strategy(desk, tmp_path):
    first = _strategy_file(tmp_path, 'a.py')
    second = _strategy_file(tmp_path, 'b.py')
    desk._on_strategy_live_start({'file': first, 'confirm': True})
    desk._on_strategy_live_start({'file': second, 'confirm': True})
    instances = list(FakeLive.instances)

    # 不带 file = 停止并删除**全部**（编辑器「停止实盘」按钮 ✓）
    desk._on_strategy_live_stop({})

    assert desk._live_map() == {}
    assert all(item.stopped == 1 and not item.running
               for item in instances)
    assert desk.strategy_live_items() == []
    assert any('strategy_live' in str(item) for item in desk.sent)


def test_stop_single_strategy_keeps_others_running(desk, tmp_path):
    first = _strategy_file(tmp_path, 'a.py')
    second = _strategy_file(tmp_path, 'b.py')
    desk._on_strategy_live_start({'file': first, 'confirm': True})
    desk._on_strategy_live_start({'file': second, 'confirm': True})

    desk._on_strategy_live_stop({'file': first})

    assert len(desk._live_map()) == 1
    assert [pathlib.Path(item['file']).name
            for item in desk.strategy_live_items()] == ['b.py']


def test_manage_rows_include_live_strategies(desk, tmp_path, control):
    first = _strategy_file(tmp_path, 'a.py')
    desk._on_strategy_live_start({'file': first, 'confirm': True})

    rows = desk._strategy_manage_rows()
    live = [row for row in rows if row.get('live')]
    assert len(live) == 1
    row = live[0]
    assert row['name'] == 'a'
    assert row['running'] is True
    assert row['next_on_new_bar'] is True
    assert row['run_next'] is True
    assert row['file'].endswith('a.py')


def test_manage_toggle_writes_control_file(desk, tmp_path, control):
    file = _strategy_file(tmp_path, 'a.py')
    desk._on_strategy_live_start({'file': file, 'confirm': True})

    desk._on_strategy_manage_update({
        'action': 'toggle', 'live': True, 'file': file,
        'key': 'run_next', 'value': False,
    })

    key = live_control.normalize(file)
    assert control.read(key)['run_next'] is False
    assert desk._live_map()[key].run_next is False


def test_manage_delete_stops_only_that_live_strategy(desk, tmp_path, control):
    first = _strategy_file(tmp_path, 'a.py')
    second = _strategy_file(tmp_path, 'b.py')
    desk._on_strategy_live_start({'file': first, 'confirm': True})
    desk._on_strategy_live_start({'file': second, 'confirm': True})
    before = len(FakeLive.instances)

    desk._on_strategy_manage_update({
        'action': 'delete', 'live': True, 'file': first,
    })

    assert len(desk._live_map()) == 1
    assert FakeLive.instances[0].stopped == 1
    assert FakeLive.instances[1].stopped == 0
    assert len(FakeLive.instances) == before
    assert control.read(live_control.normalize(first)) == {
        'next_on_new_bar': True, 'run_next': True}


# ------------------------------------------------------------------ 前端
def test_editor_state_reaches_realtime_chart(desk):
    """看盘窗口（ChartPage）也必须转发 `strategy_live` 状态 ✓"""
    app = _read('app.ts')
    chart = _read('chart-page.ts')
    local = _read('local-chart-page.ts')
    # `_forEditors` 同时遍历两类页面（以前只有 LocalChartPage → 停止按钮禁用 ✗）
    for_editors = app.split('private _forEditors', 1)[1].split('_showEditorHelp', 1)[0]
    assert 'page instanceof ChartPage' in for_editors
    assert 'page instanceof LocalChartPage' in for_editors
    # 两个页面都把状态转给编辑器面板 ✓
    for source in (chart, local):
        assert 'setStrategyLive(patch: Record<string, any>): void {' in source
        assert 'setStrategyLive?.(patch)' in source


def test_editor_stop_button_stops_all_and_shows_count():
    panel = _read('editor-panel.ts')
    assert "this.options.onCommand('strategy_live_stop', {})" in panel
    assert 'const items: Array<Record<string, any>> = Array.isArray(patch.items)' in panel
    assert 'this.stopLiveButton.disabled = !running;' in panel
    assert '运行中${count > 1 ? ` ×${count}`' in panel


def test_strategy_manager_renders_live_rows():
    dialog = _read('layout-dialogs.ts')
    assert 'live?: boolean;' in dialog
    assert "'● '" in dialog and '实盘 · ' in dialog   # 运行中标记 ✓
    assert '停止并移除这个策略实盘' in dialog
    app = _read('app.ts')
    assert "live: !!row.live, file: row.file || row.path || ''" in app
