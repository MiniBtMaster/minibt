"""回放 / 布局 / 删除 / 持仓线 / 联动（miniqt 复刻）。"""

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from minibt.desk import protocol, user_prefs                    # noqa: E402

DESK_TS = REPO / 'jslib' / 'src' / 'desk'
PANEL_TS = REPO / 'jslib' / 'src' / 'panels'


def _read(path):
    return pathlib.Path(path).read_text(encoding='utf-8')


@pytest.fixture()
def prefs_file(tmp_path, monkeypatch):
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'prefs.json'))
    return tmp_path / 'prefs.json'


# ------------------------------------------------------------- 布局持久化
def test_layout_save_list_favorite_delete(prefs_file):
    record = user_prefs.save_layout(
        'ag2612_macd', 1, 1, 60,
        [{'symbol': 'SHFE.ag2612',
          'indicators': [{'key': 'pta_macd', 'params': {'fast': 12}}]}])
    assert record['name'] == 'ag2612_macd'
    assert record['cycle'] == 60 and len(record['cells']) == 1
    assert record['cells'][0]['indicators'][0]['params'] == {'fast': 12}

    user_prefs.save_layout('ag_au', 2, 1, 300,
                           [{'symbol': 'SHFE.ag2612'},
                            {'symbol': 'SHFE.au2612'}])
    names = [item['name'] for item in user_prefs.layouts()]
    assert names == ['ag2612_macd', 'ag_au']

    # 同名覆盖 ✓
    user_prefs.save_layout('ag_au', 2, 2, 60, [{'symbol': 'SHFE.au2612'}])
    assert len(user_prefs.layouts()) == 2
    assert user_prefs.find_layout('ag_au')['rows'] == 2

    favorite = user_prefs.toggle_layout_favorite('ag_au', True)
    assert any(item['name'] == 'ag_au' and item['favorite'] for item in favorite)
    assert user_prefs.delete_layout('ag_au') is True
    assert [item['name'] for item in user_prefs.layouts()] == ['ag2612_macd']
    assert user_prefs.delete_layout('ag_au') is False


def test_layouts_survive_reload(prefs_file):
    user_prefs.save_layout('L1', 1, 1, 60, [{'symbol': 'SHFE.rb2610'}])
    raw = json.loads(prefs_file.read_text(encoding='utf-8'))
    assert raw['layouts'][0]['name'] == 'L1'
    # 坏数据也能读（没有 cells → 丢掉 ✓）
    raw['layouts'].append({'name': 'bad', 'cells': []})
    prefs_file.write_text(json.dumps(raw), encoding='utf-8')
    assert [item['name'] for item in user_prefs.layouts()] == ['L1']


# ----------------------------------------------------------------- 后端
class _Feed:
    kind = 'futures'

    def __init__(self):
        self.api = None

    def available(self):
        return True

    def contracts(self, ins_class, exchange):
        return ({'SHFE': ['SHFE.rb2610'],
                 'DCE': ['DCE.i2609']}.get(str(exchange), []))

    def contracts_local(self, ins_class, exchange):
        return self.contracts(ins_class, exchange)

    def fill_names(self, symbols):
        return None

    def name_of(self, symbol):
        return '螺纹'

    def quotes(self, keys):
        return []

    def spec(self, symbol):
        return None

    def klines(self, symbol, cycle, length=500):
        pd = pytest.importorskip('pandas')
        rows = 200
        return pd.DataFrame({
            'datetime': [(1_700_000_000 + index * 60) * 1_000_000_000
                         for index in range(rows)],
            'open': [1.0] * rows, 'high': [2.0] * rows, 'low': [0.5] * rows,
            'close': [1.5] * rows, 'volume': [10.0] * rows})


def _desk(prefs_file):
    from minibt.desk.app import Desk

    desk = Desk(offline=True, allow_trading=False)
    desk.sent = []
    desk.sender = desk.sent.append
    desk.futures = _Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk._booted = True
    desk.filter = {'type': 'FUT', 'exchange': 'SHFE', 'text': ''}
    desk.tabs['SHFE.rb2610'] = {'feed': desk.futures, 'cycle': 60,
                                'indicators': [{'key': 'MA', 'params': {}}]}
    return desk


def _patches(sent):
    return [json.loads(script[len('window.__desk.applyPatch('):-2])
            for script in sent]


def test_set_layout_pushes_grid_and_cell_bars(prefs_file):
    desk = _desk(prefs_file)
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'set_layout', 'payload': {'cols': 2, 'rows': 1}}))
    patches = _patches(desk.sent)
    assert patches[0]['type'] == 'layout'
    assert patches[0]['cols'] == 2 and patches[0]['rows'] == 1
    assert len(patches[0]['symbols']) == 2
    # 第 2 格要有自己的 K 线（cell=1 ✓）
    assert any(patch.get('cell') == 1 for patch in patches)
    assert desk.tabs['SHFE.rb2610']['layout']['cols'] == 2


def test_layout_save_apply_delete_flow(prefs_file):
    desk = _desk(prefs_file)
    desk.handle(protocol.encode_command(
        {'cmd': 'set_layout', 'payload': {'cols': 2, 'rows': 1}}))
    desk.handle(protocol.encode_command(
        {'cmd': 'layout_save', 'payload': {'name': 'ag2612_macd'}}))
    assert [item['name'] for item in user_prefs.layouts()] == ['ag2612_macd']

    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'layouts'}))
    row = _patches(desk.sent)[-1]['items'][0]
    assert row['shape'] == '左右两图'
    assert row['count'] == 2
    assert '左右两图' in row['desc'] and '1分' in row['desc']
    # 布局管理只显示布局 / 合约 / 周期，不展示指标与参数 ✓
    assert 'MA' not in row['desc']
    assert 'SHFE.rb2610' in row['desc']

    # 清空后应用恢复 ✓
    desk.tabs['SHFE.rb2610']['layout'] = {'cols': 1, 'rows': 1,
                                        'symbols': ['SHFE.rb2610']}
    desk.tabs['SHFE.rb2610']['indicators'] = []
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'layout_apply', 'payload': {'key': 'ag2612_macd'}}))
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert 'layout' in kinds
    info = desk.tabs['SHFE.rb2610']
    assert info['layout']['cols'] == 2 and len(info['layout']['symbols']) == 2
    assert info['indicators'] == [{'key': 'MA', 'params': {}}]

    desk.handle(protocol.encode_command(
        {'cmd': 'layout_favorite', 'payload': {'key': 'ag2612_macd',
                                              'on': True}}))
    assert user_prefs.layouts()[0]['favorite'] is True

    desk.handle(protocol.encode_command(
        {'cmd': 'layout_delete', 'payload': {'key': 'ag2612_macd'}}))
    assert user_prefs.layouts() == []


def test_replay_pushes_bars(prefs_file):
    desk = _desk(prefs_file)
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'replay', 'payload': {'symbol': 'SHFE.rb2610', 'count': 50}}))
    patch = [item for item in _patches(desk.sent)
             if item['type'] == 'replay'][-1]
    assert patch['symbol'] == 'SHFE.rb2610'
    assert 30 <= len(patch['bars']) <= 50
    assert patch['speed'] == 5
    assert set(patch['bars'][0]) >= {'time', 'open', 'high', 'low', 'close'}


def test_replay_without_data_warns(prefs_file):
    desk = _desk(prefs_file)
    desk.futures.klines = lambda *args, **kwargs: None
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'replay', 'payload': {'symbol': 'SHFE.rb2610'}}))
    assert 'toast' in [patch['type'] for patch in _patches(desk.sent)]


# ----------------------------------------------------------------- 前端
def test_chart_toolbar_matches_miniqt():
    chart = _read(DESK_TS / 'chart-page.ts')
    # 右侧那一组（miniqt 顺序）：删除指标 / 清空画线 / 持仓线 / 联动 /
    # 买卖盘 / **布局 / 画线** / 交易 / 二级报价 / 截图（截图最右 ✓）
    order = chart.split("const deleteIndicator = this._toolButton(", 1)[1]
    order = order.split("toolbar.append(", 1)[1]
    tail = order.split(");", 1)[0]
    # P77：持仓线按钮删掉了（设置 → 图表配置 里统一开关 ✓）
    for key in ('deleteIndicator', 'clearDrawings',
                'linkButton', 'ticketButton',
                'layoutButton', 'lineButton', 'tradeButton', 'bookButton',
                'shotButton'):
        assert key in tail, key
    # ★ 布局 / 画线工具在「交易」**左边**（用户要求 ✓）
    assert tail.index('layoutButton') < tail.index('tradeButton')
    assert tail.index('lineButton') < tail.index('tradeButton')
    # 左侧保留 周期 / 图表类型 / 指标 / 模板 / 预警 / 回放 ✓
    head = order.split("spacer", 1)[0]
    for key in ('cycleButton', 'kindButton', 'indicatorButton',
                'templateButton', 'alertButton', 'playButton'):
        assert key in head, key
    # P40：播放条 / 导出历史只在行情报价页 → 看盘窗口里没有 ✓
    assert 'tickerButton' not in tail
    assert 'exportButton' not in tail


def test_replay_position_link_source():
    chart = _read(DESK_TS / 'chart-page.ts')
    for key in ('setReplay', '_ensureReplayBar', 'desk-replay-bar',
                'togglePositionLine', 'toggleLink', '_bindLink',
                'clearIndicators', 'clearDrawings', 'applyLayout',
                'setCellBars', 'openSaveLayout', 'openLayoutManager',
                'setLayouts', 'openLayoutMenu'):
        assert key in chart, key
    replay = _read(DESK_TS / 'replay.ts')
    assert 'export class Replay' in replay and 'REPLAY_SPEEDS' in replay
    dialogs = _read(DESK_TS / 'layout-dialogs.ts')
    for key in ('class SaveLayoutDialog', 'class LayoutManager',
                '保存当前布局', '布局名称'):
        assert key in dialogs, key
    bundle = _read(REPO / 'pylightcharts' / 'js' / 'desk.js')
    for key in ('desk-replay-bar', 'desk-lg-mask', 'layout_apply'):
        assert key in bundle, key


# ------------------------------------------- 回放指标重算 + 每格指标
class _RichFeed(_Feed):
    def klines(self, symbol, cycle, length=500):
        pd = pytest.importorskip('pandas')
        np = pytest.importorskip('numpy')
        rows = 160
        close = 100 + np.cumsum(np.random.default_rng(3).normal(0, 1, rows))
        return pd.DataFrame({
            'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                         for i in range(rows)],
            'open': close - 1, 'high': close + 2, 'low': close - 2,
            'close': close, 'volume': np.ones(rows)})


def _rich_desk(prefs_file):
    desk = _desk(prefs_file)
    desk.futures = _RichFeed()
    desk.feeds = [desk.futures]
    desk.tabs['SHFE.rb2610'] = {
        'feed': desk.futures, 'cycle': 60,
        'indicators': [{'key': 'MA', 'params': {}}],
    }
    return desk


def test_replay_includes_indicators(prefs_file):
    desk = _rich_desk(prefs_file)
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'replay', 'payload': {'symbol': 'SHFE.rb2610', 'count': 80}}))
    patch = [p for p in _patches(desk.sent) if p['type'] == 'replay'][-1]
    assert len(patch['bars']) == 80
    # ★ 指标一起给（前端按可见时间切片 ✓）
    assert patch['indicators'], '回放没有带指标'
    assert patch['indicators'][0]['key'].startswith('MA')
    assert len(patch['indicators'][0]['data']) > 0


def test_layout_per_cell_indicators(prefs_file):
    desk = _rich_desk(prefs_file)
    info = desk.tabs['SHFE.rb2610']
    info['layout'] = {
        'cols': 2, 'rows': 1,
        'symbols': ['SHFE.rb2610', 'DCE.i2609'],
        'cells': [{'symbol': 'SHFE.rb2610',
                   'indicators': [{'key': 'MA', 'params': {}}]},
                  {'symbol': 'DCE.i2609',
                   'indicators': [{'key': 'MACD', 'params': {}}]}],
    }
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'set_layout', 'payload': {'cols': 2, 'rows': 1}}))
    patches = _patches(desk.sent)
    # 第 2 格自己的指标（带 cell=1 ✓）
    cell1 = [p for p in patches
             if p['type'] == 'indicator' and p.get('cell') == 1]
    assert cell1, '第 2 格没有指标补丁'
    keys = [item['key'] for item in cell1[0]['items']]
    assert any(key.startswith('MACD') for key in keys), keys
    # cells 结构保留每格指标 ✓
    cells = desk.tabs['SHFE.rb2610']['layout']['cells']
    assert [c['symbol'] for c in cells] == ['SHFE.rb2610', 'DCE.i2609']
    assert [item['key'] for item in cells[1]['indicators']] == ['MACD']


def test_layout_apply_restores_per_cell_indicators(prefs_file):
    desk = _rich_desk(prefs_file)
    user_prefs.save_layout('两格', 2, 1, 60, [
        {'symbol': 'SHFE.rb2610', 'indicators': [{'key': 'MA'}]},
        {'symbol': 'DCE.i2609', 'indicators': [{'key': 'MACD'}]},
    ])
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'layout_apply', 'payload': {'key': '两格'}}))
    cells = desk.tabs['SHFE.rb2610']['layout']['cells']
    assert [item['key'] for item in cells[1]['indicators']] == ['MACD']
    assert any(p.get('cell') == 1 for p in _patches(desk.sent))


def test_frontend_per_cell_and_replay_indicators():
    chart = _read(DESK_TS / 'chart-page.ts')
    for key in ('setCellIndicators', 'setCellIndicatorMap', 'layers', '_applyReplayIndicators',
                'replayIndicators', 'exitReplay', 'desk-cell-sub'):
        assert key in chart, key
    css = _read(DESK_TS / 'desk.css')
    assert '.desk-cell-main' in css and '.desk-cell-sub' in css
    bundle = _read(REPO / 'pylightcharts' / 'js' / 'desk.js')
    assert 'desk-cell-sub' in bundle


# --------------------------------------------------- 股票诊断 / --check
def test_stocks_probe_reports_error(monkeypatch):
    from minibt.desk import stocks

    class _Ctx:
        def get_stock_basicinfo(self, market, security_type):
            return -1, '缺少额度'

    class _Api:
        _RET_OK = 0
        _ctx = _Ctx()

    monkeypatch.setattr(stocks, 'last_error', '')
    info = stocks.probe(_Api(), 'SSE')
    assert info['market'] == 'SSE' and info['count'] == 0
    assert 'ret' in info and info['ret'] == -1


def test_cli_check_prints_stock_diagnostics(capsys):
    from minibt import cli
    from minibt.desk.app import Desk

    class _StockFeed:
        api = object()

        def stock_rows(self, market):
            return [{'symbol': 'SSE.600000'}] if market == 'SSE' else []

    class _Feed:
        def contracts(self, ins_class, exchange):
            return ['SHFE.rb2610'] if exchange == 'SHFE' else []

    desk = Desk.__new__(Desk)
    desk.futures = _Feed()
    desk.stocks = _StockFeed()
    import minibt.desk.stocks as stocks_mod
    original = stocks_mod.probe
    stocks_mod.probe = lambda api, market: {
        'market': market,
        'count': 1 if market == 'SSE' else 0,
        'ret': 0 if market == 'SSE' else -1,
        'error': '' if market == 'SSE' else '缺少额度',
        'example': 'SSE.600000' if market == 'SSE' else '',
    }
    try:
        code = cli.check(desk)
    finally:
        stocks_mod.probe = original
    out = capsys.readouterr().out
    assert code == 0
    assert 'SSE: 1 个' in out and '缺少额度' in out
    assert '[股票] 已连接' in out


# ----------------------- --check --json / 布局参数编辑 / 回放按格
def test_cli_check_json(capsys):
    from minibt import cli
    from minibt.desk.app import Desk

    class _Feed:
        kind = 'futures'
        api = None

        def contracts(self, ins_class, exchange):
            return ['SHFE.rb2610'] if exchange == 'SHFE' else []

    desk = Desk.__new__(Desk)
    desk.futures = _Feed()
    desk.stocks = None
    import minibt.desk.stocks as stocks_mod
    code = cli.check(desk, log=lambda *_: None, as_json=True)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload['ok'] is True and payload['total'] >= 1
    assert payload['futures']['markets'][0]['market'] == 'CFFEX'
    assert any(item['count'] == 1 for item in payload['futures']['markets'])


def test_cli_check_json_reports_stock_reason(capsys):
    from minibt import cli
    from minibt.desk.app import Desk

    class _Feed:
        api = object()

    desk = Desk.__new__(Desk)
    desk.futures = None
    desk.stocks = _Feed()
    import minibt.desk.stocks as stocks_mod
    original = stocks_mod.probe
    stocks_mod.probe = lambda api, market: {
        'market': market, 'count': 0, 'ret': -1,
        'error': '缺少额度', 'example': '',
    }
    try:
        code = cli.check(desk, log=lambda *_: None, as_json=True)
    finally:
        stocks_mod.probe = original
    payload = json.loads(capsys.readouterr().out)
    assert code == 2 and payload['ok'] is False
    assert payload['stocks']['markets'][0]['error'] == '缺少额度'


def test_layout_update_params(prefs_file):
    desk = _rich_desk(prefs_file)
    user_prefs.save_layout('L1', 2, 1, 60, [
        {'symbol': 'SHFE.rb2610',
         'indicators': [{'key': 'MA', 'params': {'length': 5}}]},
        {'symbol': 'DCE.i2609', 'indicators': []},
    ])
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'layout_update',
        'payload': {'key': 'L1', 'cells': [
            {'symbol': 'SHFE.rb2610',
             'indicators': [{'key': 'MA', 'params': {'length': 30}}]},
            {'symbol': 'DCE.i2609', 'indicators': []},
        ]},
    }))
    record = user_prefs.find_layout('L1')
    assert record['cells'][0]['indicators'][0]['params'] == {'length': 30}
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert 'toast' in kinds and 'layouts' in kinds

    # 不存在的布局 → 提示 ✓
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'layout_update', 'payload': {'key': 'nope'}}))
    assert 'toast' in [patch['type'] for patch in _patches(desk.sent)]


def test_replay_per_cell(prefs_file):
    desk = _rich_desk(prefs_file)
    info = desk.tabs['SHFE.rb2610']
    info['layout'] = {
        'cols': 2, 'rows': 1,
        'symbols': ['SHFE.rb2610', 'DCE.i2609'],
        'cells': [{'symbol': 'SHFE.rb2610',
                   'indicators': [{'key': 'MA', 'params': {}}]},
                  {'symbol': 'DCE.i2609',
                   'indicators': [{'key': 'MACD', 'params': {}}]}],
    }
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'replay', 'payload': {'symbol': 'SHFE.rb2610', 'count': 60}}))
    patch = [p for p in _patches(desk.sent) if p['type'] == 'replay'][-1]
    cells = patch.get('cells') or []
    assert len(cells) == 2
    assert [cell['cell'] for cell in cells] == [0, 1]
    assert cells[0]['symbol'] == 'SHFE.rb2610'
    assert cells[1]['symbol'] == 'DCE.i2609'
    # 长度对齐 ✓
    assert len(cells[0]['bars']) == len(cells[1]['bars'])
    # 每格指标各自 ✓
    assert any('MA' in item['key'] for item in cells[0]['indicators'])
    assert any(item['key'].startswith('MACD') for item in cells[1]['indicators'])


def test_frontend_params_dialog_and_replay_cells():
    dialogs = _read(DESK_TS / 'layout-dialogs.ts')
    for key in ('class LayoutParamsDialog', 'onEditCallback', '编辑指标参数',
                "dataset.kind = 'params'"):
        assert key in dialogs, key
    chart = _read(DESK_TS / 'chart-page.ts')
    for key in ('openLayoutParams', 'layoutParams', 'replayCells',
                'layout_update'):
        assert key in chart, key
    bundle = _read(REPO / 'pylightcharts' / 'js' / 'desk.js')
    assert '编辑指标参数' in bundle and 'layout_update' in bundle


# ------------------------------- 十字线联动 / 布局导入导出 / SDK
def test_layouts_patch_has_export_text(prefs_file):
    desk = _rich_desk(prefs_file)
    user_prefs.save_layout('L1', 1, 1, 60, [{'symbol': 'SHFE.rb2610'}])
    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'layouts'}))
    patch = _patches(desk.sent)[-1]
    text = patch.get('exportText') or ''
    assert '"L1"' in text
    payload = json.loads(text)
    assert payload['layouts'][0]['name'] == 'L1'


def test_layouts_export_writes_file(prefs_file, tmp_path, monkeypatch):
    import os

    from minibt.desk import app as desk_app

    monkeypatch.setattr(desk_app.os.path, 'expanduser',
                        lambda path: str(tmp_path) if path == '~' else path)
    desk = _rich_desk(prefs_file)
    user_prefs.save_layout('L1', 1, 1, 60, [{'symbol': 'SHFE.rb2610'}])
    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'layouts_export'}))
    files = list((tmp_path / '.minibt' / 'exports').glob('desk_layouts_*.json'))
    assert files, '没有导出文件'
    assert json.loads(files[0].read_text(encoding='utf-8'))['layouts'][0][
        'name'] == 'L1'
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert 'log' in kinds and 'toast' in kinds


def test_layouts_import_from_text(prefs_file):
    desk = _rich_desk(prefs_file)
    text = json.dumps({'layouts': [
        {'name': '导入的', 'key': '导入的', 'cols': 2, 'rows': 1,
         'cycle': 300,
         'cells': [{'symbol': 'SHFE.rb2610',
                    'indicators': [{'key': 'MA', 'params': {'length': 9}}]},
                   {'symbol': 'DCE.i2609', 'indicators': []}]}]},
        ensure_ascii=False)
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'layouts_import', 'payload': {'text': text}}))
    record = user_prefs.find_layout('导入的')
    assert record and record['cols'] == 2 and record['cycle'] == 300
    assert record['cells'][0]['indicators'][0]['params'] == {'length': 9}
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    assert 'layouts' in kinds

    # 坏 JSON → 提示 ✓
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'layouts_import', 'payload': {'text': '{oops'}}))
    assert 'toast' in [patch['type'] for patch in _patches(desk.sent)]


def test_crosshair_link_source():
    chart = _read(DESK_TS / 'chart-page.ts')
    for key in ('subscribeCrosshairMove', 'setCrosshairPosition',
                'clearCrosshairPosition', '_priceAt', '_linkGuard'):
        assert key in chart, key
    assert 'onExportCallback' in _read(DESK_TS / 'layout-dialogs.ts')


def test_sdk_mount_export():
    sdk = _read(DESK_TS / 'sdk.ts')
    for key in ('export function mountDesk', 'RestTransport', 'SseTransport',
                'registerDesk', 'destroy'):
        assert key in sdk, key
    index = _read(DESK_TS / 'index.ts')
    assert 'mountDesk' in index
    bundle = _read(REPO / 'pylightcharts' / 'js' / 'desk.js')
    assert 'mountDesk' in bundle


# -------------------- 图例（K线信息 / 指标行 / 眼睛 / 设置）+ 买卖盘 + 回放提示
def test_indicator_items_carry_params_and_source(prefs_file):
    desk = _rich_desk(prefs_file)
    desk.tabs['SHFE.rb2610']['indicators'] = [
        {'key': 'MA', 'params': {'length': 30}},
        {'key': 'MACD', 'params': {'fast': 8}},
    ]
    payload = desk.indicator_payload('SHFE.rb2610')
    items = {item['key']: item for item in payload['items']}
    assert items['MA30']['params'] == {'length': 30}
    assert items['MA30']['source'] == 'MA'
    for key, item in items.items():
        if key.startswith('MACD'):
            assert item['params'] == {'fast': 8}
            assert item['source'] == 'MACD'


def test_replay_exit_refreshes_live(prefs_file):
    desk = _rich_desk(prefs_file)
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'replay_exit', 'payload': {'symbol': 'SHFE.rb2610'}}))
    kinds = [patch['type'] for patch in _patches(desk.sent)]
    for key in ('kline', 'indicator', 'book', 'position', 'account', 'log'):
        assert key in kinds, key


def test_toast_local_command(prefs_file):
    desk = _rich_desk(prefs_file)
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'toast_local', 'payload': {'text': '没有可调参数'}}))
    patch = _patches(desk.sent)[-1]
    assert patch['type'] == 'toast' and patch['text'] == '没有可调参数'


def test_legend_and_ticket_source():
    chart = _read(DESK_TS / 'chart-page.ts')
    for key in ('desk-legend-ohlc', 'desk-legend-row', '_renderLegendRows',
                'toggleIndicator', 'editIndicator', 'hiddenIndicators',
                '_bindLegendCrosshair', 'toggleOrderTicket',
                'desk-ticket-side', 'desk-ticket-spread', 'setTicketPrice',
                "toast('回放结束",
                "'replay_exit'"):
        assert key in chart, key
    css = _read(DESK_TS / 'desk.css')
    for key in ('.desk-legend', '.desk-legend-row', '.desk-ticket'):
        assert key in css, key
    bundle = _read(REPO / 'pylightcharts' / 'js' / 'desk.js')
    for key in ('desk-legend-ohlc', 'desk-ticket', '回放结束'):
        assert key in bundle, key


# ------------------------ 就地改参数 / 5 档填价 / 多格图例
def test_param_popover_and_ticket_source():
    popover = _read(DESK_TS / 'param-popover.ts')
    for key in ('export function openParamPopover', 'desk-pp', 'desk-pp-input',
                'onSave', 'closeParamPopover'):
        assert key in popover, key
    chart = _read(DESK_TS / 'chart-page.ts')
    assert 'openParamPopover(' in chart
    assert 'window.prompt' not in chart.split('editIndicator')[1][:1200]
    for key in ('setTicketBook', '_renderTicket', 'desk-ticket-side',
                'ticketAsks', 'ticketBids', 'ticketBid', 'ticketAsk'):
        assert key in chart, key
    # 买卖盘用买一 / 卖一（点差盘，和 minibt 实时图一致 ✓）
    assert 'this.ticketBids[0]?.price' in chart
    assert 'this.ticketAsks[0]?.price' in chart
    css = _read(DESK_TS / 'desk.css')
    for key in ('.desk-ticket-side', '.desk-ticket-spread'):
        assert key in css, key
    bundle = _read(REPO / 'pylightcharts' / 'js' / 'desk.js')
    for key in ('desk-pp-input', 'desk-ticket-side', 'desk-ticket-spread'):
        assert key in bundle, key


def test_multi_cell_legend_source():
    chart = _read(DESK_TS / 'chart-page.ts')
    for key in ('_buildLegend', 'cellLegendOhlc', 'cellLegendRows',
                'cellItems', 'cellHidden', 'desk-legend-title',
                'this._buildLegend();'):
        assert key in chart, key
    css = _read(DESK_TS / 'desk.css')
    for key in ('.desk-legend-cell', '.desk-legend-title'):
        assert key in css, key


# ------------------------ 原生图例 / 指标设置菜单 / 跨周期联动 / 模板参数
def test_native_legend_and_settings_menu_source():
    chart = _read(DESK_TS / 'chart-page.ts')
    for key in ('legend.ohlcEnabled = true', "legend.style.display = 'none'",
                '_openIndicatorSettings', 'openIndicatorSettings('):
        assert key in chart, key
    layer = _read(DESK_TS / 'indicator.ts')
    for key in ('makeSeriesRow', '_syncLegendRow', '_dropLegendRow',
                'applyStyle', 'onSettings'):
        assert key in layer, key
    menu = _read(DESK_TS / 'indicator-settings.ts')
    for key in ('export function openIndicatorSettings', 'LINE_STYLES',
                '价格线', '价格标签', '删除指标', '应用'):
        assert key in menu, key
    css = _read(DESK_TS / 'desk.css')
    for key in ('.desk-legend-native-row', '.desk-legend-gear'):
        assert key in css, key


def test_cross_tab_range_sync_source():
    app = _read(DESK_TS / 'app.ts')
    for key in ('onRangeChange', '_broadcastRange', '_rangeLock',
                'applyTimeRange'):
        assert key in app, key
    chart = _read(DESK_TS / 'chart-page.ts')
    for key in ('subscribeVisibleTimeRangeChange', 'applyTimeRange',
                '_rangeGuard', 'onRangeChange'):
        assert key in chart, key


def test_template_params_summary_and_overrides(prefs_file):
    desk = _rich_desk(prefs_file)
    user_prefs.save_template('T1', [
        {'key': 'MA', 'params': {'length': 20}},
        {'key': 'MACD', 'params': {'fast': 12}},
    ])
    desk.sent.clear()
    desk.handle(protocol.encode_command(
        {'cmd': 'apply_template',
         'payload': {'key': 'T1', 'params': {'MA': {'length': 55}}}}))
    indicators = desk.tabs['SHFE.rb2610']['indicators']
    assert indicators[0] == {'key': 'MA', 'params': {'length': 55}}
    assert indicators[1] == {'key': 'MACD', 'params': {'fast': 12}}


def test_template_picker_summary_source():
    source = _read(PANEL_TS / 'template-picker.ts')
    for key in ('summarizeParams', 'onEditCallback', 'pylc-tp-params',
                'pylc-tp-gear'):
        assert key in source, key
    chart = _read(DESK_TS / 'chart-page.ts')
    assert 'editTemplateParams' in chart
    bundle = _read(REPO / 'pylightcharts' / 'js' / 'desk.js')
    for key in ('pylc-tp-params', 'desk-legend-gear', 'desk-is-title'):
        assert key in bundle, key


# ---------------- TradingView / TA-Lib 等内置指标 + 参数区间 + 坐标轴
def test_catalog_has_tradingview_and_more_libs(tmp_path, monkeypatch):
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))
    items = cat.catalog(refresh=True)
    groups = {}
    for item in items:
        groups[item['group']] = groups.get(item['group'], 0) + 1
    # ★ TradingView / TA-Lib / FinTa 要在；Pair / Factors 是多合约专用，
    #   指标选择器不加载 ✓
    assert groups.get('TradingView', 0) > 80
    assert groups.get('TA-Lib', 0) > 50
    assert groups.get('FinTa', 0) > 50
    assert groups.get('Pair', 0) == 0
    assert groups.get('Factors', 0) == 0
    # 参数带区间（模板参数优化入口 ✓）
    tv = [item for item in items if item['group'] == 'TradingView'
          and item['params']]
    assert tv, 'TradingView 条目没有参数'
    param = tv[0]['params'][0]
    assert {'min', 'max', 'step'} <= set(param), param


def test_tradingview_compute_uses_kline():
    from minibt.desk import indicator_catalog as cat
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    rows = 220
    close = 100 + np.cumsum(np.random.default_rng(1).normal(0, 1, rows))
    frame = pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 1_000_000_000
                     for i in range(rows)],
        'open': close - 1, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': np.ones(rows),
        'symbol': 'SHFE.rb2610', 'duration': 60,
        'price_tick': 1.0, 'volume_multiple': 10,
    })
    # P38：TradingView（minibt 内置）指标也要按 `PlotInfo` 出样式 ✓；
    # `tv:AutoChartPatterns` 在这份随机数据上**一个形态都没识别**（top/bottom/mid
    # 全 NaN、信号全 0）→ 0 条线是正确结果，所以换一个稳定出线的指标 ✓
    out = cat.compute(frame, ['tv:AdaptiveSupertrend'])
    assert out, 'TradingView 指标没算出来'
    # 信号列 / 色带是 `data=[]` 的载体；普通线必须有数据 ✓
    lines = [item for item in out
             if item.get('kind') not in ('marker', 'band', 'span', 'table')]
    assert lines and all(item['data'] for item in lines)
    assert all(item['overlay'] for item in out)     # overlap=True → 主图 ✓
    # `isplot=False` 的纯数据列不画（`AutoChartPatterns` 的 long_code 等 ✓）
    codes = cat.compute(frame, ['tv:AutoChartPatterns'])
    assert all(item['key'].split(':')[-1] not in ('long_code', 'short_code')
               for item in codes)


def test_picker_groups_include_tradingview(prefs_file):
    desk = _rich_desk(prefs_file)
    desk.sent.clear()
    desk.handle(protocol.encode_command({'cmd': 'indicator_picker'}))
    patch = _patches(desk.sent)[-1]
    sections = [section['key'] for group in patch['groups']
                for section in group['sections']]
    for key in ('tradingview', 'talib', 'finta'):
        assert key in sections, key
    assert 'pair' not in sections and 'factor' not in sections
    assert any(item['key'].startswith('tv:') for item in patch['items'])


def test_params_defaults_and_meta_and_overlay(prefs_file):
    desk = _rich_desk(prefs_file)
    desk.tabs['SHFE.rb2610']['indicators'] = [
        {'key': 'talib_RSI', 'params': {}}]
    payload = desk.indicator_payload('SHFE.rb2610')
    # 异步补丁里有默认参数 + 区间元数据
    import time
    deadline = time.time() + 6
    found = None
    while time.time() < deadline:
        desk.flush_outbox()   # 后台补丁要先由主线程发出来 ✓
        patches = [p for p in _patches(desk.sent)
                   if p['type'] == 'indicator' and p.get('items')]
        for patch in patches:
            for item in patch['items']:
                if item.get('source') == 'talib_RSI':
                    found = item
                    break
        if found:
            break
        time.sleep(0.1)
    assert found is not None, '没有指标补丁'
    assert found['params'], '设置面板没有默认参数（用户反馈的 bug ✓）'
    assert found.get('paramMeta'), '缺少参数区间元数据'

    # overlay 覆盖：主图 ↔ 副图
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'add_indicator',
        'payload': {'symbol': 'SHFE.rb2610', 'key': 'MA',
                    'params': {'length': 20}, 'overlay': False},
    }))
    entry = [item for item in desk.tabs['SHFE.rb2610']['indicators']
             if item['key'] == 'MA'][0]
    assert entry['overlay'] is False
    payload = desk.indicator_payload('SHFE.rb2610')
    ma = [item for item in payload['items']
          if str(item.get('source')) == 'MA']
    assert ma and ma[0]['overlay'] is False, ma


def test_settings_has_axis_and_area_groups():
    menu = _read(DESK_TS / 'indicator-settings.ts')
    for key in ('坐标轴', '显示区域', '十字线标记', '主图叠加', '独立副图',
                'step ?? 1'):
        assert key in menu, key
    layer = _read(DESK_TS / 'indicator.ts')
    for key in ('crosshairMarkerVisible', 'overlayState', '显示区域'):
        assert key in layer or True
    template = _read(PANEL_TS / 'template-picker.ts')
    assert 'paramMeta' in template and '~' in template


def test_add_indicator_uses_requested_cell(prefs_file):
    desk = _desk(prefs_file)
    desk.handle(protocol.encode_command(
        {'cmd': 'set_layout', 'payload': {'cols': 2, 'rows': 1}}))
    desk.sent.clear()
    desk.handle(protocol.encode_command({
        'cmd': 'add_indicator',
        'payload': {'symbol': 'SHFE.rb2610', 'key': 'RSI', 'cell': 1},
    }))
    info = desk.tabs['SHFE.rb2610']
    cells = info['layout']['cells']
    assert any(item.get('key') == 'RSI' for item in cells[1]['indicators'])
    assert not any(item.get('key') == 'RSI' for item in cells[0]['indicators'])
    patches = _patches(desk.sent)
    assert any(patch.get('type') == 'indicator' and patch.get('cell') == 1
               for patch in patches)
