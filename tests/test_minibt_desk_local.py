"""本地图表（静态 CSV + 本地模拟账户）+ 本轮 UI 修复的回归测试。

覆盖：

* `LocalStore` 读取 minibt 内置 CSV / 添加文件夹 / 表头校验；
* `LocalSim` 买卖 / 平仓 / 账户补丁；
* `Desk` 的 `local_*` 命令；
* 切换合约时指标按新合约重算（清掉旧的后台签名）；
* 画线工具箱跟随主题（`Handler.setRootStyles`）；
* 顶栏 LOGO 两套（深色 / 浅色）；
* 回放：蜡烛图真的更新 + 按初始比例收可见范围；
* 本地图表页是 `chart-page.ts` 的独立副本。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

DESK = REPO / 'minibt' / 'desk'
JSLIB = REPO / 'jslib' / 'src' / 'desk'


@pytest.fixture()
def store(tmp_path, monkeypatch):
    from minibt.desk import local_data
    monkeypatch.setattr(local_data, 'FOLDERS_FILE',
                        str(tmp_path / 'folders.json'))
    monkeypatch.setattr(local_data, 'STATE_FILE',
                        str(tmp_path / 'state.json'))
    # 隔离 `~/.minibt/datas_external.json` 的全局登记，避免别的测试
    # 添加的临时目录混进「内置」列表 ✓
    from minibt.data import tools as _tools
    monkeypatch.setattr(_tools, 'external_paths', lambda: [])
    return local_data.LocalStore()


def test_store_lists_three_builtins(store):
    items = store.items()
    names = [item['name'] for item in items]
    builtin_names = {'l2609_60', 'pp2609_60', 'test'}
    assert builtin_names <= set(names)
    # ⚠ `~/.minibt/datas` 是**用户目录**：`Gui.Desk` / btplot 会往里面写
    #   `<合约>_<周期>.csv`（source='用户'）→ 只检查内置那几个 ✓
    for item in items:
        if item['name'] not in builtin_names:
            continue
        assert item['source'] == '内置'
        assert item['duration'] > 0
        # 列表页不加载整表，但文件大小 / 路径要有 ✓
        assert item['size'] > 0 and item['path'].endswith('.csv')


def test_store_reads_minibt_frame(store):
    frame = store.frame('test')
    assert len(frame) > 100
    assert frame['datetime'].dtype == 'int64'     # minibt 指标吃纳秒 ✓
    for column in ('open', 'high', 'low', 'close', 'volume',
                   'symbol', 'duration', 'price_tick'):
        assert column in frame.columns
    bars = store.bars('test')
    assert bars and {'time', 'open', 'high', 'low', 'close'} <= set(bars[0])
    assert bars[-1]['time'] == int(frame['datetime'].iloc[-1]) // 1_000_000_000


def test_store_accepts_date_and_vol_aliases(tmp_path, store):
    path = tmp_path / 'aliased.csv'
    pd.DataFrame({
        'date': ['2026-01-01 09:00', '2026-01-01 09:01'],
        'open': [1, 2], 'high': [2, 3], 'low': [0, 1], 'close': [1.5, 2.5],
        'vol': [10, 20],
    }).to_csv(path, index=False)
    store.add_folder(str(tmp_path))
    frame = store.frame('aliased')
    assert len(frame) == 2
    assert frame['volume'].tolist() == [10, 20]


def test_store_skips_csv_without_ohlc(tmp_path, store):
    bad = tmp_path / 'bad.csv'
    bad.write_text('datetime,value\n2026-01-01,1\n', encoding='utf-8')
    store.add_folder(str(tmp_path))
    assert all(item['name'] != 'bad' for item in store.items())


def test_local_sim_buy_close_and_payload():
    from minibt.desk.local_data import LocalSim
    sim = LocalSim()
    sim.set_price('X', 100.0, 2)
    assert sim.order('X', 'buy', 2, 100.0)['ok']
    sim.set_price('X', 110.0, 2)
    payload = sim.payload('X')
    assert payload['values']['balance'] == pytest.approx(100020.0)
    assert payload['values']['float_profit'] == pytest.approx(20.0)
    assert payload['tables']['positions']['rows'][0][:3] == ['X', '多', '2']
    assert sim.order('X', 'sell', 1, 110.0, close=True)['ok']
    payload = sim.payload('X')
    assert payload['values']['realized_pnl'] == pytest.approx(10.0)
    assert payload['values']['position_count'] == 1
    assert sim.order('X', 'sell', 1, 110.0, close=True)['ok']
    assert sim.payload('X')['values']['position_count'] == 0


def _desk_with_capture():
    from minibt.desk.app import Desk
    desk = Desk(offline=True, browser=True)
    patches = []
    desk.sender = lambda script: patches.append(script)
    desk._booted = True
    return desk, patches


def test_desk_local_list_load_indicator_order():
    desk, patches = _desk_with_capture()
    # 测试隔离：不要读到用户机器上真实保存的指标选择 ✓
    desk._local_set_items('test', 0, [])
    desk.handle('desk_~_' + json.dumps({'cmd': 'local_list'}))
    assert any('"type":"local_data"' in item for item in patches)
    patches.clear()

    desk.handle('desk_~_' + json.dumps(
        {'cmd': 'local_load', 'payload': {'name': 'test'}}))
    assert any('"type":"local_kline"' in item for item in patches)
    assert any('"type":"local_account"' in item for item in patches)
    patches.clear()

    desk.handle('desk_~_' + json.dumps({
        'cmd': 'local_add_indicator',
        'payload': {'symbol': 'test', 'key': 'MA', 'params': {'length': 10}},
    }))
    indicator = [item for item in patches if '"type":"local_indicator"' in item]
    assert indicator and '"MA10"' in indicator[-1]
    assert desk._local_items('test', 0)[0]['key'] == 'MA'
    patches.clear()

    desk.handle('desk_~_' + json.dumps({
        'cmd': 'local_order',
        'payload': {'symbol': 'test', 'side': 'buy', 'qty': 1,
                    'price': 5000},
    }))
    account = [item for item in patches if '"type":"local_account"' in item]
    assert account and '"trade_count":1' in account[-1]
    desk.local_sim().reset()


def test_local_indicators_are_per_cell(tmp_path, monkeypatch):
    """多布局：格 1 / 格 2 各存各的指标，互不覆盖（用户实测串格 ✗）"""
    from minibt.desk import local_data
    monkeypatch.setattr(local_data, 'STATE_FILE',
                        str(tmp_path / 'local_state.json'))
    desk, patches = _desk_with_capture()
    desk._local_set_items('test', 0, [])
    desk._local_set_items('test', 1, [])
    desk.handle('desk_~_' + json.dumps({
        'cmd': 'local_add_indicator',
        'payload': {'symbol': 'test', 'key': 'MA', 'cell': 1},
    }))
    desk.handle('desk_~_' + json.dumps({
        'cmd': 'local_add_indicator',
        'payload': {'symbol': 'test', 'key': 'RSI', 'cell': 0},
    }))
    assert [item['key'] for item in desk._local_items('test', 0)] == ['RSI']
    assert [item['key'] for item in desk._local_items('test', 1)] == ['MA']
    cell0 = [p for p in patches if '"type":"local_indicator"' in p
             and '"cell":0' in p]
    cell1 = [p for p in patches if '"type":"local_indicator"' in p
             and '"cell":1' in p]
    assert cell0 and cell1
    assert 'RSI' in cell0[-1] and '"source":"MA"' not in cell0[-1]
    assert '"source":"MA"' in cell1[-1] and 'RSI' not in cell1[-1]


def test_local_strategy_signals_drive_local_sim_and_position_line():
    """本地回放策略信号 -> 本地模拟账户，并推 local 持仓线 ✓"""
    desk, patches = _desk_with_capture()
    sim = desk.local_sim()
    sim.reset()
    sim.set_price('test', 100.0, 2)
    buy = {'id': 'buy-1', 'time': 100, 'side': 'buy',
           'price': 90, 'close': False}
    sell = {'id': 'sell-1', 'time': 150, 'side': 'sell',
            'price': 110, 'close': False}
    desk._on_local_strategy_trade({
        'symbol': 'test', 'reset': True, 'until': 100,
        'signals': [buy],
    })
    book = sim.positions.get('test') or {}
    assert book.get('long') == 1
    assert any('"type":"position"' in item and '"local":true' in item
               for item in patches)
    # 重复发送同一个信号不会重复成交 ✓
    desk._on_local_strategy_trade({
        'symbol': 'test', 'reset': False, 'until': 100,
        'signals': [buy],
    })
    assert sim.positions['test']['long'] == 1
    # 下一根出现 sell：先平 long，再开空 1 ✓
    desk._on_local_strategy_trade({
        'symbol': 'test', 'reset': False, 'until': 150,
        'signals': [sell],
    })
    assert sim.positions['test']['long'] == 0
    assert sim.positions['test']['short'] == 1


def test_local_trade_ticket_and_strategy_auto_source():
    page = _read(JSLIB / 'local-chart-page.ts')
    assert "onOrder: (side, close) => this._localOrder(side, close)" in page
    assert 'this._on_local_strategy_trade' not in page
    assert 'local_strategy_trade' in page
    assert 'private _syncStrategyTrades()' in page
    assert 'markers?: Array' in page


def test_switch_symbol_clears_old_indicators_before_new_contract():
    class FakeFeed:
        kind = 'futures'
        api = None

        def available(self):
            return True

        def name_of(self, symbol):
            return symbol

        def spec(self, _symbol):
            return None

        def klines(self, symbol, _cycle, _length=500):
            base = 100.0 if symbol == 'A' else 200.0
            return pd.DataFrame({
                'datetime': [1_700_000_000_000_000_000 + index * 60_000_000_000
                             for index in range(60)],
                'open': [base + index for index in range(60)],
                'high': [base + index + 1 for index in range(60)],
                'low': [base + index - 1 for index in range(60)],
                'close': [base + index + 0.5 for index in range(60)],
                'volume': [1.0] * 60,
            })

    desk, patches = _desk_with_capture()
    feed = FakeFeed()
    desk.futures = feed
    desk.feeds = [feed]
    desk.tabs['A'] = {
        'feed': feed, 'cycle': 60,
        'indicators': [{'key': 'MA', 'params': {'length': 5}}],
        '_ind_sig': 'stale', '_ind_gen': 3,
    }
    desk.handle('desk_~_' + json.dumps({
        'cmd': 'switch_symbol', 'payload': {'from': 'A', 'to': 'B'},
    }))
    indicator = [item for item in patches if '"type":"indicator"' in item]
    assert indicator, '切换合约后应重推指标'
    assert '"symbol":"B"' in indicator[-1]
    # 切换合约必须清掉旧合约的指标（用户要求：旧线 / 旧价位不能带过去 ✓）；
    # 前端 resetIndicators() 后由用户在新合约上重新加指标。
    assert '"items":[]' in indicator[-1]
    assert '202.5' not in indicator[-1] and '102.5' not in indicator[-1]
    assert desk.tabs['B']['indicators'] == []
    assert '_ind_sig' not in desk.tabs['B']


def test_local_sim_trade_count_is_not_capped_at_200():
    """成交次数不能用明细列表长度（只保留最近 200 条 ✗）"""
    from minibt.desk.local_data import LocalSim

    sim = LocalSim(initial_cash=1_000_000, fee_mode='fixed', fee_value=0)
    sim.set_price('X', 100.0, 2)
    for _ in range(250):
        sim.order('X', 'buy', 1, 100.0, False, force=True)
        sim.order('X', 'sell', 1, 101.0, True, force=True)
    analysis = sim.analysis()
    assert len(sim.trades) == 200          # 明细仍只留 200 条（UI 用）
    assert analysis['summary']['trades'] == 500
    assert analysis['summary']['closes'] == 250
    assert analysis['summary']['wins'] == 250


def test_local_cci_stop_lines_keep_full_history():
    """停止线不能只剩最后一根 / 与时间戳错位（截图显示 0 的根因）"""
    import importlib.util
    from minibt.desk.local_data import LocalStore
    from minibt.desk.strategy_overlay import classes_of, run_overlay

    spec = importlib.util.spec_from_file_location(
        'cci_tutorial', str(REPO / 'tutorials' / 'cci.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cls = classes_of(module)['strategy'][0]
    frame = LocalStore().frame('pp2609_60')
    result = run_overlay(frame, cls, 'pp2609_60', 60,
                         replay=True, replay_bars=0)
    assert result['ok'], result.get('error')
    stops = next(item for item in result['items']
                 if item['key'] == 'editor:stop_price:line:1')
    assert len(stops['data']) == len(frame)
    valid = [value for _, value in stops['data'] if value is not None]
    assert len(valid) > 100                # 持仓期间逐根都有值 ✓
    # 回放窗口必须覆盖完整历史：截图里的 32% 位置也要有停止线 ✓
    assert stops['data'][3200][1] is not None


# ---------------------------------------------------------------- 前端源码
def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


def test_local_replay_end_waits_for_manual_exit():
    """最后一根只暂停 / 隐藏底条，不自动退出；手动退出恢复原数据 ✓"""
    page = _read(JSLIB / 'local-chart-page.ts')
    block = page.split('if (finished) {', 1)[1].split('onState:', 1)[0]
    assert 'this.replayEnded = true' in block
    assert 'this.exitReplay()' not in block
    assert 'this.replayBar?.classList.remove' in block
    assert 'private restoringReplay' in page
    assert 'if (this.restoringReplay) return;' in page
    assert 'this.replayEnded = false;' in page.split('exitReplay(): void', 1)[1][:400]


def test_local_multi_side_position_lines():
    page = _read(JSLIB / 'local-chart-page.ts')
    block = page.split('setPosition(payload', 1)[1].split('positionLineKey', 1)[0]
    assert 'for (const side of sides)' in block
    assert 'this.positionLinesByCell.set(cell, bucket)' in block
    assert 'this._addPositionBadge' in block
    assert 'this.positionBadges.push' in page
    chart = _read(JSLIB / 'chart-page.ts')
    # ★ 多布局：每格一份持仓线（`positionLinesByCell`），不再只有第 1 格 ✓
    assert 'private readonly positionLinesByCell' in chart
    assert 'for (const side of sides)' in chart.split('setPosition(payload', 1)[1]


def test_local_strategy_stop_lines_replay_is_full_and_fast():
    overlay = _read(REPO / 'minibt' / 'desk' / 'strategy_overlay.py')
    runner = _read(REPO / 'minibt' / 'desk' / 'strategy_runner.py')
    app = _read(REPO / 'minibt' / 'desk' / 'app.py')
    assert 'replay: bool = False' in overlay
    assert 'runner.replay(frame, bars)' in overlay
    assert 'def _update_stops' in runner
    assert 'self._update_stops()' in runner
    # CCI 等策略逐根全量重算时，不能把 10000 根全部塞在主线程里跑 ✗
    assert 'LOCAL_STRATEGY_REPLAY_BARS = 0' in app   # 0 = 全量
    assert 'replay_bars=LOCAL_STRATEGY_REPLAY_BARS' in app
    # 回放必须保持 KLine 全量、只推进 btindex：
    # 每根截前缀会让 stop_lines 在第一次 buy 时只有半截长度 → 停止线错位 ✗
    assert 'self.strategy._btindex = index' in runner
    assert 'sub = frame.iloc[:index + 1]' not in runner
    # 回放放后台线程，点击后立刻返回（界面不「未响应」✓）
    assert 'def _run_local_strategy_overlay' in app
    assert 'threading.Thread(' in app
    assert "name=f'local-strategy-{name}'" in app


def test_local_replay_filters_native_markers_and_shape_rows():
    """回放必须同时裁 markers / shapeRows，否则未来信号会堆在最新一根 ✓"""
    page = _read(JSLIB / 'local-chart-page.ts')
    block = page.split('private _applyReplayIndicators', 1)[1].split(
        '退出回放', 1)[0]
    assert 'markers: markers.filter' in block
    assert 'shapeRows: rows.filter' in block
    assert 'inside(row.time)' in block


def test_toolbox_follows_desk_theme():
    """画线工具箱用根 CSS 变量；desk 必须按主题调用 setRootStyles ✓"""
    theme = _read(JSLIB / 'theme.ts')
    assert 'export interface UiPalette' in theme
    assert 'export function uiPalette' in theme
    assert 'UI_DARK' in theme and 'UI_LIGHT' in theme

    chart = _read(JSLIB / 'chart-page.ts')
    assert 'Handler.setRootStyles' in chart
    assert 'uiPalette(theme)' in chart
    # applyTheme 里也要刷（切主题时工具箱跟着变 ✓）
    apply_block = chart.split('applyTheme(theme', 1)[1].split('\n    }', 1)[0]
    assert '_applyRootStyles(theme)' in apply_block


def test_topbar_has_two_logo_variants():
    logo = _read(JSLIB / 'logo.ts')
    assert 'DESK_LOGO_DARK' in logo and 'DESK_LOGO_LIGHT' in logo
    assert 'aria-label="minibt desk"' in logo
    assert 'minibt</text>' in logo and 'desk</text>' in logo

    app = _read(JSLIB / 'app.ts')
    assert "import { deskLogo } from './logo'" in app
    assert 'desk-logo' in app and 'this.logo.innerHTML = deskLogo' in app
    css = _read(JSLIB / 'desk.css')
    assert '.desk-logo' in css


def test_replay_updates_candles_and_respects_initial_seek():
    chart = _read(JSLIB / 'chart-page.ts')
    on_bars = chart.split('onBars: (visible, finished)', 1)[1]
    on_bars = on_bars.split('onState:', 1)[0]
    assert '_applyCellBars(index)' in on_bars
    assert '_syncReplayViewport(visible.length' in on_bars
    viewport = chart.split('_syncReplayViewport(_length', 1)[1].split(
        '\n    }', 1)[0]
    assert 'setVisibleLogicalRange' in viewport
    # P60：首次/seek 摆窗口（整段 + 右侧留白），播放阶段不碰视窗 ✓
    assert 'REPLAY_WINDOW' in viewport and 'REPLAY_PADDING' in viewport
    assert 'setRange.call(scale' in viewport
    assert 'scrollToRealTime' not in viewport


def test_switch_symbol_clears_frontend_indicator_layers():
    app = _read(JSLIB / 'app.ts')
    rename = app.split('private _renameChart', 1)[1].split('\n    }', 1)[0]
    assert 'page.resetIndicators()' in rename
    chart = _read(JSLIB / 'chart-page.ts')
    assert 'resetIndicators(): void' in chart


def test_local_chart_page_is_an_independent_copy():
    local = _read(JSLIB / 'local-chart-page.ts')
    # 独立副本（不是继承 / 复用 ChartPage）✓
    assert 'class LocalChartPage' in local
    assert 'class LocalChartPage extends' not in local
    # 静态图表的差异
    assert 'openLocalDataMenu' in local
    assert 'setLocalBars' in local
    assert 'setLocalAccount' in local
    assert '_buildLocalTicket' in local
    assert 'desk-tool-disabled' in local        # 周期按钮禁用
    assert 'local_add_folder' in local
    # 二级报价按钮不再进工具栏
    toolbar_append = local.split('toolbar.append(', 1)[1].split(');', 1)[0]
    assert 'bookButton' in toolbar_append       # 二级报价按钮（本地图表也可用 ✓）
    # P50：本地图表也补了「联动 / 买卖盘 / 布局」✓
    for name in ('linkButton', 'ticketButton', 'layoutButton'):
        assert name in toolbar_append, name
    # 回放用本地数据，不再请求后端
    start = local.split('startReplay(options', 1)[1].split(
        '/** 进入回放', 1)[0]
    assert 'this.cellBars.map' in start
    assert 'cells,' in start
    assert "onCommand?.('replay'" not in start


def test_account_dock_has_ticket_slot():
    dock = _read(JSLIB / 'account-dock.ts')
    assert 'ticketHost' in dock
    assert 'setTicket(element' in dock
    css = _read(JSLIB / 'desk.css')
    assert '.desk-dock-ticket' in css
    assert '.desk-local-ticket-buttons' in css


def test_plus_menu_has_local_chart_and_routes():
    app = _read(JSLIB / 'app.ts')
    assert "label: '本地图表（minibt 内置数据 / CSV）'" in app
    assert 'openLocalChart' in app
    assert "case 'local_data'" in app
    assert "case 'local_kline'" in app
    assert "case 'local_indicator'" in app
    assert "case 'local_account'" in app
    assert "kind: 'home' | 'quote' | 'chart' | 'local'" in app


def test_local_cell_context_menu_uses_mouse_cell_and_title():
    page = _read(JSLIB / 'local-chart-page.ts')
    assert 'private _activateCell(index: number): void' in page
    assert 'this._activateCell(index);' in page
    assert 'this.closeCell(this.activeCell);' in page
    assert 'cellLegendTitles' in page
    assert '_updateLegendTitle(cell);' in page
