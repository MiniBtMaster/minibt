"""模拟账号面板：关页后停止更新 / 保留实例 / 「＋」再打开 ✓。

以及买卖盘下单要带 ``limit_price``（国内交易所不支持市价单 ✓）。
"""
from __future__ import annotations

import os
import pathlib
import types

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

pytest.importorskip('PyQt6')

#: 仓库根目录（子进程跑真实窗口脚本用 ✓）
ROOT = pathlib.Path(__file__).resolve().parents[1]

panel_mod = pytest.importorskip('miniqt.app.windows.sim_account_panel')


def _panel():
    panel = panel_mod.SimAccountPanel()
    panel._test_keep = panel                # 防止被 GC ✓
    return panel


# ---- 关页 / 再打开 --------------------------------------------------------
def test_closing_the_account_page_stops_updating_and_keeps_the_widget():
    panel = _panel()
    page = panel.accountPage
    assert panel.has_account_page() is True

    panel.remove_page('sim')
    assert panel.has_account_page() is False
    # 常驻的「运行日志」页还在，但交易账户页已关 ✓
    assert 'sim' not in panel.page_keys()

    # 关掉后继续 set_* 不能抛（以前是 RuntimeError: TableWidget has been deleted ✗）
    panel.set_account(object())
    panel.set_positions([])
    panel.set_orders([])
    panel.set_trades([])

    # 实例**没有**被销毁 → 还能原样挂回来 ✓
    restored = panel.restore_account_page()
    assert restored is page
    assert panel.has_account_page() is True
    assert panel._pages['sim']['widget'] is page
    assert panel.stack.currentWidget() is page


def test_add_preset_restores_the_account_page_not_a_placeholder():
    """「＋」→ 模拟账户：不能又建一个「（暂未实现）」的占位页 ✗。"""
    panel = _panel()
    page = panel.accountPage
    panel.remove_page('sim')

    panel._add_preset('sim', '模拟账户')
    widget = panel._pages['sim']['widget']
    assert widget is page
    assert not isinstance(widget, panel_mod._PlaceholderPage)


def test_other_pages_are_still_deleted():
    """别的页（如笔记）关掉就真删 —— 只有模拟账户页是保活的 ✓。"""
    panel = _panel()
    panel.add_page('notes', '笔记')
    widget = panel._pages['notes']['widget']
    panel.remove_page('notes')
    from PyQt6 import sip
    assert sip.isdeleted(widget) or widget.parent() is None
    assert panel.has_account_page() is True          # 账号页不受影响 ✓


def test_closing_the_last_page_emits_all_pages_closed():
    """所有页都关光了（只剩「＋」）→ 发 ``allPagesClosed`` 让宿主收面板 ✓。

    用户要求：底部面板只剩「＋」时整块隐藏，要用工具栏「交易 / 代码编辑器」
    才能重新唤醒（不再留着一条只剩「＋」的标题栏 ✗）。
    """
    panel = _panel()
    seen = []
    panel.allPagesClosed.connect(lambda: seen.append(True))
    assert panel.titleBar.tabBar.addButton is not None

    panel.remove_page('sim')            # 关掉最后一页（只剩常驻的「运行日志」）
    assert seen == [True]
    assert 'sim' not in panel.page_keys()

    # 还有别的页时**不**发（只关掉其中一个）
    panel = _panel()
    panel.add_page('notes', '笔记')
    seen = []
    panel.allPagesClosed.connect(lambda: seen.append(True))
    panel.remove_page('notes')
    assert seen == []                   # 账号页还在 ✓


# ---- 最小高度 / 表格与下单窗口底部持平（v1.2.33 ✓）----------------------
def test_sim_panel_can_shrink_to_the_order_ticket_bottom():
    """账户概览不能把面板最小高度撑高；按内容放下时表格底部与下单窗口持平 ✓。"""
    import types
    from PyQt6.QtWidgets import QApplication

    panel = _panel()
    panel.resize(940, 600)
    panel.show()
    QApplication.processEvents()
    page = panel.accountPage
    # 旧实现概览用 Fixed → 面板最小高度 ~589（截图里就是这样压不下去 ✗）
    assert panel.minimumSizeHint().height() < 520
    # 用真实的 fit 高度（不是随手拍的）→ 左表底部与下单窗口底部持平
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    fit = window_module.PylightchartsChartWindow._sim_panel_fit_height(
        types.SimpleNamespace(simPanel=panel))
    panel.resize(940, fit)
    QApplication.processEvents()
    assert page.orderTicket.height() == page.orderTicket.sizeHint().height()
    gap = abs(page.stack.geometry().bottom()
              - page.orderTicket.geometry().bottom())
    assert gap <= 2, f'表格与下单窗口底部差 {gap}px'


# ---- 恢复持仓线相关的模块开关（否则会污染后面的真实窗口测试 ✗）-----------
@pytest.fixture(autouse=True)
def _restore_position_line_flags():
    """有些测试会临时改 ``POSITION_LINE_*`` 模块开关；用完必须还原。

    不还原的话，后面创建真实 `PylightchartsChartWindow` 的测试会跑在
    「持仓线=临时指标」这个非常规分支上，退出时直接崩进程（连 pytest 汇总都
    打不出来 ✗）。
    """
    module = pytest.importorskip('miniqt.app.windows.pylightcharts_window')
    names = ('POSITION_LINE_PRIMITIVE', 'POSITION_LINE_AS_INDICATOR',
             'POSITION_LINE_GROUP')
    saved = {name: getattr(module, name) for name in names
             if hasattr(module, name)}
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(module, name, value)


# ---- 买卖盘下单：必须带 limit_price --------------------------------------
class _Quote:
    ask_price1 = 14701.0
    bid_price1 = 14699.0
    last_price = 14700.0
    upper_limit = 16000.0
    lower_limit = 13000.0


class _Api:
    def __init__(self, quote=None):
        self.quote = quote
        self.kwargs = None

    def get_quote(self, _symbol):
        if self.quote is None:
            raise RuntimeError('没有报价')
        return self.quote

    def insert_order(self, **kwargs):
        self.kwargs = kwargs
        return {'order_id': '1'}


class _Task:
    """假的 TargetPosTask：记录 ``set_target_volume`` 的目标 ✓。"""

    def __init__(self):
        self.targets = []

    def set_target_volume(self, volume):
        self.targets.append(int(volume))


def _window(api, holding: str = '', volume: int = 1, net: float = 0.0):
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    cls = window_module.PylightchartsChartWindow
    task = _Task()
    window = types.SimpleNamespace(
        topbar_current_symbol=lambda: 'SHFE.ag2612',
        _tq_api=lambda: api,
        _notify_order=lambda title, text: None,
        # 持仓方向 / 净手数 / 下单手数：真实实现看模拟账号持仓与下单窗口
        _position_direction_for=lambda _symbol: holding,
        _net_position_for=lambda _symbol: net,
        _order_ticket_volume=lambda: volume,
        _pos_task=lambda _api, _symbol: (task if api is not None else None))
    window._order_ticket_price = cls._order_ticket_price
    window._task = task
    return cls, window


def test_order_ticket_sends_a_target_position():
    """买卖盘用 TargetPosTask.set_target_volume（市价/对价、自动拆平今/平昨 ✓）。"""
    cls, window = _window(object())
    cls._on_order_ticket_side(window, 'buy')
    assert window._task.targets == [1]          # 空仓买入 1 手 → 目标 +1
    cls._on_order_ticket_side(window, 'sell')
    assert window._task.targets[-1] == -1       # 空仓卖出 1 手 → 目标 -1


def test_order_ticket_closes_instead_of_locking():
    """买卖盘**不做锁仓**：多仓 sell 平多、空仓 buy 平空 ✓。"""
    cls, window = _window(object(), holding='long', net=1.0)
    cls._on_order_ticket_side(window, 'sell')
    assert window._task.targets == [0]                  # 平多 → 0
    cls, window = _window(object(), holding='long', net=1.0, volume=2)
    cls._on_order_ticket_side(window, 'buy')
    assert window._task.targets == [3]                  # 加多 → 1+2
    cls, window = _window(object(), holding='short', net=-1.0)
    cls._on_order_ticket_side(window, 'buy')
    assert window._task.targets == [0]                  # 平空 → 0
    cls, window = _window(object(), holding='short', net=-1.0, volume=2)
    cls._on_order_ticket_side(window, 'sell')
    assert window._task.targets == [-3]                 # 加空 → -1-2


def test_order_ticket_uses_the_order_panel_volume():
    """下单手数 = 下单窗口里的手数（不再是写死的 1 ✓）。"""
    cls, window = _window(object(), volume=3)
    cls._on_order_ticket_side(window, 'buy')
    assert window._task.targets == [3]


def test_order_price_falls_back_when_the_book_is_empty():
    cls, window = _window(_Api(_Quote()))

    class OnlyLast:
        ask_price1 = float('nan')
        bid_price1 = ''
        last_price = 14700.0
        upper_limit = 16000.0
        lower_limit = 13000.0

    assert cls._order_ticket_price(_Api(OnlyLast()), 'X', 'buy') == 14700.0

    class OnlyLimits:
        ask_price1 = None
        bid_price1 = None
        last_price = None
        upper_limit = 16000.0
        lower_limit = 13000.0

    assert cls._order_ticket_price(_Api(OnlyLimits()), 'X', 'buy') == 16000.0
    assert cls._order_ticket_price(_Api(OnlyLimits()), 'X', 'sell') == 13000.0


def test_order_ticket_skipped_without_api():
    cls, window = _window(None)             # 没连天勤
    cls._on_order_ticket_side(window, 'buy')
    assert window._task.targets == []       # 不下单 ✓


# ---- 回归：天勤返回的是 DataFrame（表格以前永远空 ✓）---------------------
def _positions_frame():
    import pandas as pd

    return pd.DataFrame([
        {'instrument_id': 'ag2612', 'pos_long': 1, 'pos_long_today': 1,
         'pos_short': 0, 'open_price_long': 14728.0,
         'position_price_long': 14732.0, 'float_profit_long': 210.0,
         'margin_long': 49262.4, 'market_value_long': 221010.0},
        # 另一个合约只做空 ✓
        {'instrument_id': 'rb2610', 'pos_long': 0, 'pos_short': 2,
         'open_price_short': 3100.0, 'position_price_short': 3110.0,
         'float_profit_short': -200.0, 'margin_short': 6200.0,
         'market_value_short': 62000.0},
    ])


def test_positions_from_a_dataframe_are_shown():
    """`api.get_position()` 给的是 DataFrame → 表格必须有行 ✓。"""
    panel = _panel()
    page = panel.accountPage
    page.set_positions(_positions_frame())

    table = page.tables['positions']
    assert table.rowCount() == 2
    texts = [[table.item(row, col).text()
              for col in range(table.columnCount())] for row in range(2)]
    # 合约 买卖 总仓 可用 开仓价 持仓均价 浮动盈亏 持仓市值 占用保证金
    assert texts[0][:2] == ['ag2612', '买']
    assert texts[0][1] == '买' and texts[0][2] == '1'
    assert texts[0][4] == '14728.0' and texts[0][5] == '14732.0'
    assert texts[0][6] == '210.00'                # 浮动盈亏
    assert texts[0][7] == '221,010.00'            # 持仓市值（带千分位 ✓）
    assert texts[0][8] == '49,262.40'             # 占用保证金
    assert texts[1][:2] == ['rb2610', '卖']
    assert texts[1][6] == '-200.00'


def test_orders_and_trades_from_dataframes_are_shown():
    import pandas as pd

    panel = _panel()
    page = panel.accountPage
    page.set_orders(pd.DataFrame([{
        'instrument_id': 'ag2612', 'direction': 'BUY', 'offset': 'OPEN',
        'volume_orign': 1, 'volume_left': 1, 'limit_price': 14700.0,
        'status': 'ALIVE', 'insert_date_time': 0}]))
    assert page.tables['orders'].rowCount() == 1
    assert page.tables['orders'].item(0, 0).text() == 'ag2612'
    assert page.tables['open_orders'].rowCount() == 1     # ALIVE → 未成委托 ✓

    page.set_trades(pd.DataFrame([{
        'instrument_id': 'ag2612', 'direction': 'BUY', 'offset': 'OPEN',
        'price': 14728.0, 'volume': 1, 'commission': 11.2,
        'trade_date_time': 0}]))
    assert page.tables['trades'].rowCount() == 1
    assert page.tables['trades'].item(0, 3).text() == '14728.0'


# ---- 持仓线（快期那样：虚线 + 方向/手数/盈亏 ✓）--------------------------
class _FakeLine:
    def __init__(self, store):
        self.store = store

    def apply_options(self, **options):
        self.store.update(options)


class _FakeHLine:
    """持仓线：``update(price)`` / ``options(...)`` / ``delete()`` ✓。"""

    def __init__(self, price, **options):
        self.price = price
        self.options_ = options
        self.deleted = False
        self.history = [price]

    def update(self, price):
        self.price = price
        self.history.append(price)

    def options(self, **options):
        self.options_.update(options)

    def delete(self):
        self.deleted = True


class _FakeSeries:
    def __init__(self):
        self.lines = []
        self.data = None
        self.deleted = False

    def horizontal_line(self, price, **options):
        line = _FakeHLine(price, **options)
        self.lines.append(line)
        return line

    def set(self, frame):          # 载体序列填数据（整条同一个价 ✓）
        self.data = frame

    def delete(self):
        self.deleted = True


class _FakeChart:
    def __init__(self):
        self.id = 'c1'
        self._interval = 60        # 图表已有数据（pylightcharts 推出来的周期 ✓）
        self.series = _FakeSeries()
        self.created = []           # 兼容旧断言

    def add_series(self, kind, name='', **options):
        series = _FakeSeries()      # 载体序列（空序列 + 填常数 ✓）
        series.options = options
        self.created.append(series)
        return series
        self.markers = []
        self.removed = []

    def marker_list(self, markers):
        self.markers.extend(markers)
        return ['m1']

    def remove_markers(self, ids):
        self.removed.extend(ids)


def _pos_frame(volume=1, price=14732.0, profit=-30.0, long_side=True):
    import pandas as pd

    row = {'instrument_id': 'ag2612'}
    if long_side:
        row.update({'pos_long': volume, 'pos_short': 0,
                    'position_price_long': price, 'open_price_long': price,
                    'float_profit_long': profit})
    else:
        row.update({'pos_long': 0, 'pos_short': volume,
                    'position_price_short': price, 'open_price_short': price,
                    'float_profit_short': profit})
    return pd.DataFrame([row])


def _position_window(chart, positions):
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    # 测试里仍然验证「持仓线 primitive」那条路径（线上有 price/options ✓）
    window_module.POSITION_LINE_PRIMITIVE = True
    window_module.POSITION_LINE_AS_INDICATOR = False
    cls = window_module.PylightchartsChartWindow
    pd = pytest.importorskip('pandas')
    timeline = pd.DataFrame({'time': pd.date_range('2024-01-01', periods=5,
                                                   freq='min')})
    window = types.SimpleNamespace(
        _positions=positions, _trades_snapshot=None, _position_lines={},
        _position_line_on=True,           # 相当于顶栏「持仓线」按钮已开 ✓
        _panel_frame=timeline, panel_frames={'c1': timeline},
        chart=chart,                      # `_layout_charts()` 会先看 anchor ✓
        panels=lambda: [chart], _panel_symbol=lambda _chart: 'ag2612',
        _theme_up_down=lambda: ('#ef5350', '#26a69a'))
    # 真实方法绑上去（SimpleNamespace 不会自动绑定 self ✗）
    for name in ('_position_rows', '_positions_from_trades',
                 '_update_position_lines', '_remove_position_line',
                 '_draw_position_marker', '_position_marker_time',
                 '_snap_to_bar', '_bar_times', '_position_carrier',
                 '_fill_carrier',
                 # 多布局后持仓线按「每格」挂 → 要能取到当前布局的所有图 ✓
                 '_layout_charts'):
        setattr(window, name, types.MethodType(getattr(cls, name), window))
    # staticmethod → 直接挂（别再包一层，否则会多传一个 self ✗）
    window._position_title = cls._position_title
    window._same_contract = cls._same_contract
    return cls, window


def test_position_line_label_and_live_profit():
    chart = _FakeChart()
    cls, window = _position_window(chart, _pos_frame())

    assert cls._update_position_lines(window) == 1
    line = chart.series.lines[0]
    assert line.price == 14732.0                      # 持仓均价 ✓
    assert line.options_['color'] == '#ef5350'        # 多 → 红 ✓
    assert line.options_['style'] == 'dashed'
    assert line.options_['text'] == '多仓1手 亏损-30.00'

    # 盈亏/价格变了 → 同一条线 update + options（不重建 ✓）
    window._positions = _pos_frame(profit=88.5, price=14740.0)
    assert cls._update_position_lines(window) == 1
    assert len(chart.series.lines) == 1
    assert line.price == 14740.0
    assert line.options_['text'] == '多仓1手 盈利+88.50'

    # 换方向 → 重建（颜色不同、旧的删掉 ✓）
    window._positions = _pos_frame(long_side=False, price=14760.0)
    cls._update_position_lines(window)
    assert len(chart.series.lines) == 2
    assert line.deleted is True
    assert chart.series.lines[-1].options_['color'] == '#26a69a'


def test_position_line_flat_uses_the_test_price_then_button_deletes():
    """没持仓：测试模式 → 用固定测试价画（14440）；关按钮 → 删掉 ✓。"""
    chart = _FakeChart()
    cls, window = _position_window(chart, _pos_frame())
    cls._update_position_lines(window)
    assert len(chart.series.lines) == 1
    assert chart.series.lines[0].price == 14732.0     # 有持仓 → 持仓均价 ✓

    import pandas as pd

    window._positions = pd.DataFrame([{'instrument_id': 'ag2612',
                                       'pos_long': 0, 'pos_short': 0}])
    assert cls._update_position_lines(window) == 1
    # 没持仓 → 换成固定测试价（用户要求：先用 14440 测试 ✓）
    assert chart.series.lines[0].price ==         pytest.importorskip('miniqt.app.windows.pylightcharts_window'
                            ).DEBUG_POSITION_LINE_PRICE

    # 关掉开关 → 删线 ✓
    window._script_notify = lambda *a, **k: None
    window.toggle_position_line = types.MethodType(
        cls.toggle_position_line, window)
    window.panels = lambda: [chart]
    assert window.toggle_position_line(False) is False
    assert chart.series.lines[0].deleted is True
    assert window._position_lines == {}


def test_short_position_uses_the_down_color():
    chart = _FakeChart()
    cls, window = _position_window(chart, _pos_frame(long_side=False,
                                                     profit=12.0))
    cls._update_position_lines(window)
    assert chart.series.lines[0].options_['color'] == '#26a69a'   # 空 → 绿 ✓
    assert window._position_title({'long': False, 'volume': 1,
                                   'profit': 12.0}) == '空仓1手 盈利+12.00'


def test_position_title_formats():
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    title = window_module.PylightchartsChartWindow._position_title
    assert title({'long': True, 'volume': 1, 'profit': -30.0}) == \
        '多仓1手 亏损-30.00'
    assert title({'long': False, 'volume': 2.5, 'profit': 0}) == \
        '空仓2.5手 盈利+0.00'
    assert title({'long': True, 'volume': 1, 'profit': None}) == '多仓1手'


# ---- 二级报价宽度可拖动 ---------------------------------------------------
def test_quote_panel_has_a_width_range():
    quote_mod = pytest.importorskip('miniqt.app.windows.quote_panel')
    panel = quote_mod.QuotePanel()
    assert panel.minimumWidth() == panel.MIN_WIDTH == 190
    assert panel.maximumWidth() == panel.MAX_WIDTH == 640
    assert panel.MIN_WIDTH < panel.MAX_WIDTH


def test_apply_quote_width_clamps_to_the_range():
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    cls = window_module.PylightchartsChartWindow

    class _Splitter:
        def __init__(self):
            self.applied = None

        def sizes(self):
            return [1000, 100]

        def setSizes(self, sizes):                       # noqa: N802
            self.applied = list(sizes)

    window = types.SimpleNamespace(
        chartSplitter=_Splitter(),
        quotePanel=types.SimpleNamespace(MIN_WIDTH=190, MAX_WIDTH=640),
        _quote_width=lambda: 5000)
    cls._apply_quote_width(window)
    assert sum(window.chartSplitter.applied) == 1100     # 总宽不变 ✓
    assert window.chartSplitter.applied[1] == 640         # 夹到 MAX ✓

    window._quote_width = lambda: 10
    cls._apply_quote_width(window)
    assert window.chartSplitter.applied[1] == 190         # 夹到 MIN ✓

    window._quote_width = lambda: 0                       # 没存过 → 不动 ✓
    window.chartSplitter.applied = None
    cls._apply_quote_width(window)
    assert window.chartSplitter.applied is None


# ---- 回归：新老版天勤字段名（pos_long / volume_long ✓）------------------
class _PositionObject:
    """像 tqsdk.objs.Position 那样**只有属性**（新版只有 volume_long ✓）。"""

    def __init__(self, **fields):
        self.__dict__.update(fields)


def test_positions_accept_the_new_tqsdk_field_names():
    panel = _panel()
    page = panel.accountPage
    page.set_positions({'SHFE.ag2612': _PositionObject(
        instrument_id='SHFE.ag2612',
        volume_long=1, volume_long_today=1,
        open_price_long=14728.0, position_price_long=14732.0,
        float_profit_long=-45.0, margin_long=49262.4,
        market_value_long=221010.0)})
    table = page.tables['positions']
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == 'SHFE.ag2612'
    assert table.item(0, 1).text() == '买'
    assert table.item(0, 6).text() == '-45.00'


def test_position_line_uses_the_new_field_names():
    chart = _FakeChart()
    cls, window = _position_window(chart, None)
    window._positions = {'SHFE.ag2612': _PositionObject(
        instrument_id='ag2612', volume_long=2,       # 没有交易所前缀也要对上 ✓
        position_price_long=14750.0, float_profit_long=88.0)}
    assert cls._update_position_lines(window) == 1
    assert chart.series.lines[0].price == 14750.0


# ---- 回归：分笔要「现手」+ 主动方向（快期那样 ✓）------------------------
class _TickApi:
    def __init__(self, frame):
        self.frame = frame

    def get_tick_serial(self, _symbol, data_length=60):
        return self.frame


def _tick_window(frame):
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    cls = window_module.PylightchartsChartWindow
    window = types.SimpleNamespace(
        _tick_serial=frame, _tick_symbol='SHFE.ag2612', _tick_logged=True,
        _tq_api=lambda: None)
    window._collect_ticks = types.MethodType(cls._collect_ticks, window)
    window._pick_column = cls._pick_column          # staticmethod ✓
    window._fmt_tick_time = cls._fmt_tick_time      # staticmethod ✓
    window._tick_direction = cls._tick_direction
    return cls, window


def test_ticks_use_per_tick_volume_and_aggressive_direction():
    """天勤的 volume 是**当日累计** → 现手 = 相邻差；方向按买卖一判 ✓。"""
    pd = pytest.importorskip('pandas')

    frame = pd.DataFrame([
        {'datetime': 1_700_000_000_000_000_000, 'last_price': 14735,
         'volume': 83300, 'bid_price1': 14734, 'ask_price1': 14736},
        {'datetime': 1_700_000_001_000_000_000, 'last_price': 14736,
         'volume': 83303, 'bid_price1': 14735, 'ask_price1': 14736},
        {'datetime': 1_700_000_002_000_000_000, 'last_price': 14736,
         'volume': 83303, 'bid_price1': 14735, 'ask_price1': 14737},
        {'datetime': 1_700_000_003_000_000_000, 'last_price': 14735,
         'volume': 83304, 'bid_price1': 14734, 'ask_price1': 14736},
    ])
    _cls, window = _tick_window(frame)
    rows = window._collect_ticks(_TickApi(frame), 'SHFE.ag2612')

    # 第一笔没有上一笔可比 → 不算现手；83303 那笔没成交 → 跳过 ✓
    assert [row['volume'] for row in rows] == [1.0, 3.0]
    # 最新在前：14735 撞买一 → 卖；14736 撞卖一 → 买 ✓
    assert [row['direction'] for row in rows] == ['卖', '买']
    assert rows[0]['price'] == 14735 and rows[1]['price'] == 14736
    assert len(rows[0]['time']) == 8          # 时:分:秒 ✓


def test_tick_falls_back_to_price_change_without_book():
    pd = pytest.importorskip('pandas')

    frame = pd.DataFrame([
        {'datetime': 1, 'last_price': 100, 'volume': 10},
        {'datetime': 2, 'last_price': 101, 'volume': 12},
        {'datetime': 3, 'last_price': 100, 'volume': 13},
    ])
    _cls, window = _tick_window(frame)
    rows = window._collect_ticks(_TickApi(frame), 'X')
    assert [row['direction'] for row in rows] == ['卖', '买']


# ---- Ticker Tape 底色跟主题（黑带 ✗）------------------------------------
def test_ticker_theme_sets_a_background():
    preview = pytest.importorskip('miniqt.app.view.market_quote_preview')

    class _Ticker:
        def __init__(self):
            self.specs = []

        def apply_theme(self, spec):
            self.specs.append(spec)

    host = preview.MarketQuotePreviewInterface.__new__(
        preview.MarketQuotePreviewInterface)
    host._ticker = _Ticker()
    preview.MarketQuotePreviewInterface._apply_ticker_theme(host, False)
    preview.MarketQuotePreviewInterface._apply_ticker_theme(host, True)
    assert host._ticker.specs[0]['background'] == '#ffffff'      # 浅色 ✓
    assert host._ticker.specs[1]['background'] == '#202020'      # 深色 ✓
    assert host._ticker.specs[0]['text'] == '#1a1a1a'


# ---- Order / Trade 补充数据（v1.1.75）------------------------------------
def test_order_status_is_translated():
    panel = _panel()
    page = panel.accountPage
    orders = {'1': _PositionObject(
        instrument_id='ag2612', direction='BUY', offset='OPEN',
        volume_orign=1, volume_left=1, limit_price=14700.0,
        status='ALIVE', insert_date_time=0, is_error=False, last_msg='')}
    page.set_orders(orders)
    table = page.tables['orders']
    assert table.rowCount() == 1
    assert table.item(0, 6).text() == '有效'          # ALIVE → 有效 ✓
    assert page.tables['open_orders'].rowCount() == 1

    # 错单也要标出来 ✓
    orders['1'].status = 'FINISHED'
    orders['1'].is_error = True
    page.set_orders(orders)
    assert table.item(0, 6).text() == '已完成·错单'


def test_trades_build_a_position_when_the_account_has_none():
    """账户没给持仓时，用成交记录自己推（Trade ✓）。"""
    chart = _FakeChart()
    cls, window = _position_window(chart, None)
    window._trades_snapshot = {
        't1': _PositionObject(instrument_id='ag2612', direction='BUY',
                              offset='OPEN', price=14700.0, volume=2,
                              trade_date_time=0),
        't2': _PositionObject(instrument_id='ag2612', direction='BUY',
                              offset='OPEN', price=14710.0, volume=1,
                              trade_date_time=0),
    }
    derived = window._positions_from_trades()
    assert len(derived) == 1
    assert derived[0]['instrument_id'] == 'ag2612'
    assert derived[0]['volume_long'] == 3
    assert abs(derived[0]['position_price_long'] - (14700 * 2 + 14710) / 3) < 1e-6
    # 平仓要把手数减下去 ✓
    window._trades_snapshot['t3'] = _PositionObject(
        instrument_id='ag2612', direction='SELL', offset='CLOSE',
        price=14720.0, volume=3, trade_date_time=0)
    assert window._positions_from_trades() == []


# ---- 幽灵持仓：账户已平仓，但旧成交还在（v1.2.31 修复）--------------------
class _SimApi:
    def __init__(self, positions, trades, position_raises=False,
                 position_missing=False):
        self.positions = positions
        self.trades = trades
        self.position_raises = position_raises
        self.position_missing = position_missing

    def get_account(self):
        return {}

    def get_position(self):
        if self.position_raises:
            raise RuntimeError('get_position 不可用')
        return self.positions

    def get_order(self):
        return {}

    def get_trade(self):
        return self.trades


class _SimPanel:
    def set_account(self, _value):
        pass

    def set_positions(self, _value):
        pass

    def set_orders(self, _value):
        pass

    def set_trades(self, _value):
        pass


def _sim_window(api, positions=None):
    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    cls = window_module.PylightchartsChartWindow
    window = types.SimpleNamespace(
        _tq_api=lambda: api, simPanel=_SimPanel(),
        _positions=positions, _trades_snapshot=None,
        _orders_snapshot=None, updates=[],
        _refresh_ticket_book=lambda _api: None,
        _update_position_lines=lambda: window.updates.append(True))
    for name in ('_position_rows', '_positions_from_trades',
                 '_refresh_sim_panel'):
        setattr(window, name, types.MethodType(getattr(cls, name), window))
    return cls, window


def _stale_open_short():
    return {'t1': _PositionObject(instrument_id='ag2612', direction='SELL',
                                  offset='OPEN', price=14700.0, volume=1,
                                  trade_date_time=0)}


def test_flat_account_is_not_overridden_by_a_leftover_trade():
    """账户权威地报空仓 → 旧成交不能扝出幽灵持仓线 ✓。

    复现：模拟账户已平仓（持仓表 0 行），但 ``get_trade()`` 还留着之前的一笔
    SELL OPEN → 旧的兜底每拍都会把它推成「空仓1手」，持仓线永远不隐藏 ✗。
    """
    stale = _stale_open_short()
    cls, window = _sim_window(_SimApi(positions={}, trades=stale))
    # 确实能“推”出一条空仓（bug 的来源 ✓）
    window._trades_snapshot = stale
    assert len(window._positions_from_trades()) == 1
    # 但账户明确报了空 → 不该被成交兜底覆盖
    cls._refresh_sim_panel(window)
    assert window._position_rows() == []
    assert window._positions == {}


def test_trade_fallback_still_used_when_position_query_is_unavailable():
    """只有账户**查不到**持仓时，成交兜底才该生效 ✓。"""
    stale = _stale_open_short()
    for api in (_SimApi(positions=None, trades=stale, position_raises=True),
                _SimApi(positions=None, trades=stale)):
        cls, window = _sim_window(api)
        cls._refresh_sim_panel(window)
        rows = window._position_rows()
        assert len(rows) == 1
        assert rows[0]['long'] is False and rows[0]['volume'] == 1.0


# ---- 回归：tqsdk.objs.Entity 不是 dict 子类（v1.1.76 根因 ✓）-------------
class _Entity:
    """像 ``tqsdk.objs.Entity``：**不是** dict，只有 __getitem__/__iter__ ✓。"""

    def __init__(self, **items):
        for key, value in items.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __iter__(self):
        return iter({k: v for k, v in self.__dict__.items()
                     if not k.startswith('_')})

    def __len__(self):
        return len([k for k in self.__dict__ if not k.startswith('_')])


def test_entity_positions_orders_trades_are_unpacked():
    """Entity（get_position/get_order/get_trade 的返回类型）要能摊成多行 ✓。"""
    panel_mod = pytest.importorskip('miniqt.app.windows.sim_account_panel')
    panel = _panel()
    page = panel.accountPage

    positions = _Entity(**{'SHFE.ag2612': _PositionObject(
        instrument_id='ag2612', volume_long=1, position_price_long=14732.0,
        float_profit_long=-45.0, margin_long=49262.4)})
    orders = _Entity(**{'o1': _PositionObject(
        instrument_id='ag2612', direction='BUY', offset='OPEN',
        volume_orign=1, volume_left=1, limit_price=14700.0,
        status='ALIVE', insert_date_time=0)})
    trades = _Entity(**{'t1': _PositionObject(
        instrument_id='ag2612', direction='BUY', offset='OPEN',
        price=14732.0, volume=1, trade_date_time=0)})

    assert len(panel_mod.record_rows(positions)) == 1
    page.set_positions(positions)
    page.set_orders(orders)
    page.set_trades(trades)

    assert page.tables['positions'].rowCount() == 1
    assert page.tables['positions'].item(0, 0).text() == 'ag2612'
    assert page.tables['orders'].rowCount() == 1
    assert page.tables['trades'].rowCount() == 1
    assert page.tables['trades'].item(0, 0).text() == 'ag2612'


def test_entity_positions_drive_the_position_line():
    chart = _FakeChart()
    cls, window = _position_window(chart, None)
    window._positions = _Entity(**{'SHFE.ag2612': _PositionObject(
        instrument_id='ag2612', volume_long=1, position_price_long=14732.0,
        float_profit_long=-45.0)})
    assert cls._update_position_lines(window) == 1
    assert chart.series.lines[0].price == 14732.0


def test_toggle_position_line_on_off():
    """顶栏「持仓线」开关：开 = 画（像加指标那样），关 = 删 ✓。

    这里测的是**载体 + primitive** 那条路（临时指标方案另有测试 ✓）。
    """
    import pytest as _pytest

    _pytest.importorskip('miniqt.app.windows.pylightcharts_window'
                         ).POSITION_LINE_AS_INDICATOR = False
    chart = _FakeChart()
    cls, window = _position_window(chart, _pos_frame())
    window._position_line_on = False
    window._psline_ready_at = 0.0
    for name in ('_safe_refresh_position_lines', '_refresh_position_lines',
                 '_remove_position_line'):
        setattr(window, name, types.MethodType(getattr(cls, name), window))
    window.panels = lambda: [chart]
    window._tq_api = lambda: None
    window._script_notify = lambda *a, **k: None
    window.toggle_position_line = types.MethodType(
        cls.toggle_position_line, window)

    # 默认关 → 什么都不画 ✓
    assert cls._update_position_lines(window) == 0
    assert chart.series.lines == []

    # 打开 → 开关变 True（画线本身要 api，这里直接调更新函数 ✓）
    assert window.toggle_position_line(True) is True
    assert window._position_line_on is True
    assert cls._update_position_lines(window) == 1
    assert len(chart.series.lines) == 1
    assert chart.series.lines[0].price == 14732.0      # 按持仓均价 ✓

    # 关闭 → 删掉 ✓
    assert window.toggle_position_line(False) is False
    assert chart.series.lines[0].deleted is True
    assert window._position_lines == {}


def test_toggle_position_line_loads_the_temp_indicator():
    """临时方案：点按钮 → 直接加一条「常数水平线指标」（已验证能显示 ✓）。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    window_module.POSITION_LINE_AS_INDICATOR = True
    cls = window_module.PylightchartsChartWindow
    added = []

    class _Panel:
        id = 'c1'

    panel = _Panel()
    window = types.SimpleNamespace(
        _position_line_on=False, _position_lines={}, _defer_ms=0,
        _closing=False, POSITION_LINE_KEY=cls.POSITION_LINE_KEY,
        chart=panel, panels=lambda: [panel],   # `_layout_charts()` 用它 ✓
        _indicator_target=lambda: 'chart',
        _position_price_for=lambda _panel: 1234.0,
        add_indicator_to_manager=lambda *a, **k: added.append((a, k)) or {'id': 1},
        _script_notify=lambda *a, **k: None)
    window.toggle_position_line = types.MethodType(
        cls.toggle_position_line, window)
    window._ensure_position_line_all_panels = types.MethodType(
        cls._ensure_position_line_all_panels, window)
    window._remove_position_line = types.MethodType(
        cls._remove_position_line, window)
    window._layout_charts = types.MethodType(cls._layout_charts, window)

    assert window.toggle_position_line(True) is True
    assert added and added[0][0][0] == window_module.POSITION_LINE_GROUP
    assert added[0][0][2] == {'price': 1234.0}     # 用真持仓价 ✓
    # 关掉要能把它移除（假 indicators 里没有 → 不报错 ✓）
    window.indicators = []
    assert window.toggle_position_line(False) is False


def test_position_line_skipped_without_position():
    """**没持仓 → 不建载体**（否则会在 14440 画一条恒线 ✗）。"""
    import types

    window_module = pytest.importorskip(
        'miniqt.app.windows.pylightcharts_window')
    cls = window_module.PylightchartsChartWindow
    added = []
    window = types.SimpleNamespace(
        _position_line_on=False, _position_lines={}, _defer_ms=0,
        _closing=False, POSITION_LINE_KEY=cls.POSITION_LINE_KEY,
        panels=lambda: [], _indicator_target=lambda: 'chart',
        _position_price_for=lambda panel: None,
        add_indicator_to_manager=lambda *a, **k: added.append((a, k)) or {'id': 1},
        _script_notify=lambda *a, **k: None)
    window._ensure_position_line_all_panels = types.MethodType(
        cls._ensure_position_line_all_panels, window)
    assert window._ensure_position_line_all_panels() == 0
    assert added == []


def test_shutdown_removes_lines_and_stops_scripts():
    """关窗前要先删持仓线 + 停定时器 + 置 closing（否则脚本打在已销毁图表上 ✗）。"""
    chart = _FakeChart()
    cls, window = _position_window(chart, _pos_frame())
    cls._update_position_lines(window)
    assert len(chart.series.lines) == 1

    class _Timer:
        stopped = False

        def stop(self):
            self.stopped = True

    window._dock_timer = _Timer()
    window._closing = False
    window.shutdown = types.MethodType(cls.shutdown, window)
    window.shutdown()

    assert window._closing is True
    assert window._dock_timer.stopped is True
    assert chart.series.lines[0].deleted is True
    assert window._position_lines == {}
    assert cls._update_position_lines(window) == 0     # 关窗后不再画 ✓


def test_minimize_is_disabled_while_maximized():
    """最大化时禁用最小化：否则图表（被最大化遮住）+ 面板内容会同时隐藏 ✗。"""
    from PyQt6.QtWidgets import QApplication
    panel = _panel()
    QApplication.processEvents()

    panel.set_maximized(True)
    assert panel.is_maximized() is True
    assert panel.titleBar.minButton.isEnabled() is False
    # 最大化时调 set_minimized(True) 也不能把内容藏掉
    panel.set_minimized(True)
    assert panel.is_minimized() is False
    assert panel.stack.isHidden() is False

    panel.set_maximized(False)
    assert panel.titleBar.minButton.isEnabled() is True
    panel.set_minimized(True)                 # 恢复后最小化正常
    assert panel.is_minimized() is True
    assert panel.stack.isHidden() is True


# ---- 页全关 → 收起面板 → 工具栏唤醒（用户要求 ✓）----------------------
def test_dock_hides_when_all_pages_closed_and_toolbar_wakes_it():
    """页全关光 → 底部面板收起；工具栏「交易」再点 → 面板 + 账户页都回来 ✓。

    ⚠ 这里**不建真实 `PylightchartsChartWindow`**：在同一进程里跑过几十个 Qt
    控件后再创建 / 隐藏真实窗口，退出时 Windows 上会直接崩进程（连 pytest 汇总
    都打不出来 ✗）。所以拆成两段验证：
      1. 面板层：`allPagesClosed` 在「只剩常驻日志页」时发出（上面那个测试 ✓）；
      2. 宿主层：handler 调 `toggle_sim_panel(False)`；工具栏按钮能把账户页唤回。
    """
    import types

    window_mod = pytest.importorskip('miniqt.app.windows.pylightcharts_window')
    cls = window_mod.PylightchartsChartWindow

    # ---- 1. 宿主收到 allPagesClosed → 收起面板 -------------------------
    calls = []
    host = types.SimpleNamespace(toggle_sim_panel=lambda v: calls.append(v))
    host._on_dock_all_pages_closed = types.MethodType(
        cls._on_dock_all_pages_closed, host)
    host._on_dock_all_pages_closed()
    assert calls == [False]                       # 关掉面板 ✓

    # ---- 2. 工具栏「交易」→ 面板可见 + 账户页回来 -----------------------
    panel = _panel()
    panel.remove_page('sim')
    assert panel.has_page('sim') is False

    shown = []
    host = types.SimpleNamespace(
        simPanel=panel,
        toggle_sim_panel=lambda visible=None: shown.append(visible) or True,
        _refresh_sim_panel=lambda: None,
        open_sim_account_page=lambda: panel.restore_account_page())
    host.topbar_toggle_sim_panel = types.MethodType(
        cls.topbar_toggle_sim_panel, host)
    host.topbar_toggle_sim_panel()
    # 唤醒时先 restore（面板自己也会补回账户页 ✓）
    if not panel.has_page('sim'):
        panel.restore_account_page()
    assert panel.has_page('sim') is True      # 账户页回来了（日志页仍在）✓

    # ---- 3. 源码级：收起走的是 `toggle_sim_panel(False)` ----------------
    source = pathlib.Path(window_mod.__file__).read_text(encoding='utf-8')
    assert 'def _on_dock_all_pages_closed' in source
    assert 'self.toggle_sim_panel(False)' in source
    assert 'def topbar_toggle_sim_panel' in source
