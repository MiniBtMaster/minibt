"""``Gui.Desk`` 入口的回归用例（2026-10-26 用户要求）。

对应关系：

* ``Gui.Desk`` → minibt desk 当界面；
* 指标（``btplot`` / ``BtIndicator``）→ **本地图表**「加到图表」；
* 策略 → 本地图表「加到图表」；回测 / 参数优化 → desk 的
  「策略回测 / 参数优化」页；
* ``Bt(live=True)`` → 天勤登录后的**实时图表**「加到图表」（多策略多页）。
"""
import pathlib
import textwrap

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding='utf-8')


def _desk(tmp_path, monkeypatch):
    from minibt.desk import app as appmod, local_data, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(local_data, 'STATE_FILE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(local_data, 'FOLDERS_FILE',
                        str(tmp_path / 'folders.json'))
    monkeypatch.setenv('MINIBT_DESK_SIM_DB', str(tmp_path / 'sim.sqlite3'))
    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.log_to_stdout = False
    desk.log_to_ui = False
    return desk


def _strategy_file(tmp_path) -> str:
    path = tmp_path / 'mystrat.py'
    path.write_text(textwrap.dedent('''
        from minibt import *

        class MyTestStrategy(Strategy):
            def __init__(self):
                self.k1 = self.get_kline(LocalDatas.pp2609_60)
                self.ma = self.k1.close.sma(20)
                self.ma.overlap = True

            def next(self):
                if not self.k1.position.pos:
                    self.k1.buy()
                else:
                    self.k1.sell()
        '''), encoding='utf-8')
    return str(path)


def _load_class(path: str, name: str = 'MyTestStrategy'):
    """按**真实模块**导入策略文件（`inspect` 才拿得到源文件 ✓）"""
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location('desk_gui_test_strat', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['desk_gui_test_strat'] = module      # inspect 要能查到 ✓
    spec.loader.exec_module(module)
    return getattr(module, name)


def _patches(sent):
    import json
    out = []
    for script in sent:
        text = str(script)
        if not text.startswith('window.__desk.applyPatch('):
            continue
        try:
            out.append(json.loads(text[len('window.__desk.applyPatch('):-2]))
        except Exception:                                        # noqa: BLE001
            continue
    return out


# ---------------------------------------------------------------- 枚举
def test_gui_desk_enum():
    from minibt.utils import Gui
    assert Gui.Desk == 'desk'
    assert str(Gui.Desk) == 'desk'
    assert Gui('desk') is Gui.Desk


def test_btplot_accepts_desk_gui():
    from minibt.btplot import _resolve_btplot_gui
    from minibt.utils import Gui
    assert _resolve_btplot_gui(Gui.Desk) == 'desk'
    assert _resolve_btplot_gui('desk') == 'desk'


# ---------------------------------------------------------------- 队列
def test_ui_queue_pushes_actions_in_order(tmp_path, monkeypatch):
    from minibt.desk import gui as dgui
    desk = _desk(tmp_path, monkeypatch)
    dgui.open_strategy_lab(desk, 'C:/x/s.py', 'optimize')
    dgui.add_local_strategy(desk, 'C:/x/s.py', 'pp2609_60')
    actions = [item['action'] for item in desk.pending_ui]
    assert actions == ['open_strategy_lab', 'add_strategy']
    for _ in range(4):
        desk._ui_next_at = 0.0
        desk._run_ui_queue()
    patches = [item for item in _patches(desk.sent)
               if item.get('type') == 'ui_action']
    assert patches and patches[0]['action'] == 'open_strategy_lab'
    assert patches[0]['mode'] == 'optimize'


def test_local_chart_action_reaches_the_frontend(tmp_path, monkeypatch):
    from minibt.desk import gui as dgui
    desk = _desk(tmp_path, monkeypatch)
    dgui.show_indicator_items([], 'pp2609_60', desk=desk)
    desk._ui_next_at = 0.0
    desk._run_ui_queue()
    actions = [item for item in _patches(desk.sent)
               if item.get('type') == 'ui_action']
    assert actions[0] == {'type': 'ui_action', 'action': 'open_local_chart',
                          'name': 'pp2609_60', 'cell': 0}


# ---------------------------------------------------------------- 指标
def test_plot_items_are_merged_into_local_payload(tmp_path, monkeypatch):
    desk = _desk(tmp_path, monkeypatch)
    desk.set_local_plot_items('pp2609_60', [{
        'key': 'bt:ma:ma', 'label': 'ma', 'overlay': True, 'kind': 'line',
        'color': '#f6c343', 'data': [[1_700_000_000, 1.0]],
    }])
    # 没有任何“目录指标”也要把这份算好的线推出去 ✓
    payload = desk._local_indicator_payload('pp2609_60', 0)
    keys = [item['key'] for item in payload['items']]
    assert 'bt:ma:ma' in keys            # 算好的线在（用户的目录指标不会丢 ✓）


def test_btplot_items_convert_from_indicator_chain():
    pytest.importorskip('pandas')
    from minibt import LocalDatas
    from minibt.btplot import _make_step_strategy
    from minibt.desk import gui as dgui
    from minibt.utils import Config

    kline = LocalDatas.pp2609_60.kline
    indicator = kline.close.sma(20)
    indicator.overlap = True
    frame, name = dgui.frame_of_kline(kline)
    assert name.endswith('_60') and len(frame) == len(kline.close)
    cls = _make_step_strategy(kline, [indicator], Config(), 'btplot')
    items = dgui.items_from_strategy_class(cls, frame, name, 60)
    assert items and items[0]['overlay'] is True
    assert items[0]['data']


# ---------------------------------------------------------------- 策略
def test_local_strategy_picks_csv_automatically(tmp_path, monkeypatch):
    """空白本地图表 + 「加到图表」→ desk 按策略里的本地合约选 CSV ✓"""
    desk = _desk(tmp_path, monkeypatch)
    path = _strategy_file(tmp_path)
    desk.queue_ui('add_strategy', path=path, symbol='', cell=0, local=True)
    for _ in range(6):
        desk._ui_next_at = 0.0
        desk._run_ui_queue()
    # 本地策略在**后台线程**跑（local overlay）→ 等它算完 ✓
    import time
    deadline = time.time() + 30
    while time.time() < deadline and 'pp2609_60' not in (
            desk._local_strategies or {}):
        time.sleep(0.1)
        desk.flush_outbox()
    assert 'pp2609_60' in (desk._local_strategies or {})
    assert desk._local_cell_names.get(0) == 'pp2609_60'
    patches = _patches(desk.sent)
    assert any(item.get('type') == 'layout' and item.get('local') for
               item in patches)
    indicators = [item for item in patches
                  if item.get('type') == 'local_indicator']
    assert indicators and indicators[-1]['items']


def test_strategy_path_from_class(tmp_path, monkeypatch):
    from minibt.desk import gui as dgui
    path = _strategy_file(tmp_path)
    cls = _load_class(path)
    assert pathlib.Path(dgui.strategy_path(cls)).samefile(path)
    assert dgui.strategy_symbols(cls) == ['pp2609_60']


def test_bt_run_with_desk_gui_opens_local_chart_and_lab(tmp_path, monkeypatch):
    """``Bt(strategy=Cls).run(gui=Gui.Desk)`` → 本地图表 + 回测/优化页 ✓"""
    from minibt import Bt, Gui
    from minibt.desk import gui as dgui

    path = _strategy_file(tmp_path)
    cls = _load_class(path)

    opened = {}

    def fake_run_desk(desk, browser=False):
        opened['desk'] = desk
        opened['browser'] = browser

    monkeypatch.setattr(dgui, 'run_desk', fake_run_desk)
    Bt(strategy=cls).run(gui=Gui.Desk)
    desk = opened['desk']
    actions = [item['action'] for item in desk.pending_ui]
    assert 'add_strategy' in actions
    assert 'open_strategy_lab' in actions
    lab = [item for item in desk.pending_ui
           if item['action'] == 'open_strategy_lab'][0]
    assert lab['mode'] == 'backtest'


def test_bt_optimize_with_desk_gui_opens_optimize_page(tmp_path, monkeypatch):
    from minibt import Bt, Gui
    from minibt.desk import gui as dgui

    path = _strategy_file(tmp_path)
    cls = _load_class(path)

    opened = {}
    monkeypatch.setattr(dgui, 'run_desk',
                        lambda desk, browser=False: opened.setdefault(
                            'desk', desk))
    Bt(strategy=cls).optstrategy(
        target='profit_ratio', params={'length': [10, 20]}).run(gui=Gui.Desk)
    desk = opened['desk']
    lab = [item for item in desk.pending_ui
           if item['action'] == 'open_strategy_lab'][0]
    assert lab['mode'] == 'optimize'


# ---------------------------------------------------------------- 前端
def test_frontend_handles_ui_action():
    app = _read('jslib/src/desk/app.ts')
    assert "case 'ui_action': {" in app
    assert "action === 'open_local_chart'" in app
    assert 'this.openStrategyLab(file,' in app


def test_empty_local_chart_action_still_opens_page(tmp_path, monkeypatch):
    """`show_strategy` 先开空白本地图表；name='' 也必须发 ui_action ✓"""
    from minibt.desk import gui as dgui

    desk = _desk(tmp_path, monkeypatch)
    desk.queue_ui('open_local_chart', name='')
    for _ in range(2):
        desk._ui_next_at = 0.0
        desk._run_ui_queue()
    actions = [item for item in _patches(desk.sent)
               if item.get('type') == 'ui_action']
    assert actions and actions[0]['action'] == 'open_local_chart'
    assert actions[0]['name'] == ''


def test_show_strategy_opens_blank_page_before_add(tmp_path, monkeypatch):
    from minibt.desk import gui as dgui

    desk = _desk(tmp_path, monkeypatch)
    path = _strategy_file(tmp_path)
    dgui.show_strategy(path, desk=desk)
    actions = [item['action'] for item in desk.pending_ui]
    assert actions[:2] == ['open_local_chart', 'add_strategy']


def test_realtime_add_strategy_carries_class_name(tmp_path, monkeypatch):
    from minibt.desk import gui as dgui

    desk = _desk(tmp_path, monkeypatch)
    dgui.add_realtime_strategy(desk, 'C:/x/multi.py', 'SHFE.ag2612',
                               strategy='LiveMaAg')
    actions = desk.pending_ui
    assert [item['action'] for item in actions] == ['open_chart',
                                                    'add_strategy']
    assert actions[1]['strategy'] == 'LiveMaAg'


def test_pick_strategy_class_by_name():
    from minibt.desk.app import _pick_strategy_class

    class A:
        pass

    class B:
        pass

    assert _pick_strategy_class([A, B], 'B') is B
    assert _pick_strategy_class([A, B], 'missing') is A
