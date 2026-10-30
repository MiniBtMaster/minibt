"""P35：原生 pane 副图 / 布局分隔条 / 二级报价三按钮 / 实时图账户页收敛 ✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


# ------------------------------------------------------------ 副图 = 原生 pane
def test_sub_panes_use_native_pane_api():
    layer = _read('jslib/src/desk/indicator.ts')
    # 不再自建 chart
    assert 'createChart' not in layer
    assert 'desk-ind-pane' not in layer
    # 原生 pane：addPane + addSeries(..., paneIndex)
    assert 'private _addPane(' in layer
    assert 'private _addSeriesToPane(' in layer
    assert 'add.call(chart, false)' in layer   # P36：不留空 pane ✓
    assert 'chart.panes().length - 1' in layer
    assert 'add(definition, options, handle.index)' in layer
    # 副图高度可设（分隔条拖动由 LWC 负责）
    assert 'setHeight' in layer


def test_legend_single_and_top_left():
    """一个图例（不是每个副图一个）→ 由主图 `handler.legend` 统一渲染 ✓"""
    layer = _read('jslib/src/desk/indicator.ts')
    assert 'getLegend' in layer
    assert 'makeSeriesRow' in layer


# ------------------------------------------------------------ 布局分隔条
def test_layout_splitters_are_draggable():
    page = _read('jslib/src/desk/chart-page.ts')
    for key in ('colSizes', 'rowSizes', '_applyGridTracks',
                '_buildSplitters', 'desk-grid-splitter',
                "axis: 'col' | 'row'", 'this.resize();'):
        assert key in page, key
    css = _read('jslib/src/desk/desk.css')
    for key in ('.desk-grid-splitters', '.desk-grid-splitter.col',
                '.desk-grid-splitter.row', 'cursor: col-resize',
                'cursor: row-resize'):
        assert key in css, key


# ------------------------------------------------------------ 二级报价三按钮
def test_depth_panel_has_close_reverse_cancel():
    panel = _read('jslib/src/desk/replay-ticket.ts')
    for key in ("['close_main', '市价平仓', 'flat'", "['reverse', '反手'",
                "['cancel', '撤单'", 'onAction'):
        assert key in panel, key
    page = _read('jslib/src/desk/chart-page.ts')
    assert "this.options.onCommand?.('account_action', payload)" in page
    # 用「鼠标最后点击的图表」的合约 ✓
    assert "'focus_chart'" in page
    app = _read('minibt/desk/app.py')
    assert "'focus_chart': self._on_focus_chart" in app
    assert "getattr(\n            self, 'last_symbol', '')" in app


# ------------------------------------------------------------ minibt 实时图收敛
def test_realtime_account_bar_removed():
    tools = _read('minibt/strategy/live_tools.py')
    body = tools.split('def _sync_account_bar', 1)[1][:600]
    assert 'return' in body.split('\n')[0:6][-1] or 'return' in body
    assert '用户要求（P35）' in body


def test_depth_panel_account_overview_removed():
    tools = _read('minibt/strategy/live_tools.py')
    assert '账户总览' not in tools
    assert 'md-acc-balance' not in tools
    assert 'var renderAccount = function (acc) { void acc; };' in tools


def test_single_global_account_page_in_topbar():
    window = _read('minibt/strategy/strategy_window.py')
    assert 'items.append(ACCOUNT_PAGE)' not in window     # 不再每个策略一页 ✓
    assert "page_bar.button('account', '账户'" in window
    assert 'def _on_topbar_account' in window
    assert "self.set_contract(ACCOUNT_PAGE, force=True)" in window
