"""行情报价（新版）页：芯片 / 数据转换 / 开盘判断 / 行情合并 的离线校验。

页面本身需要真实 QtWebEngine 窗口才渲染（本机 offscreen 会原生崩溃），
这里只测数据部分和可在 offscreen 创建的芯片控件。
"""
from __future__ import annotations

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import PyQt6.QtWebEngineWidgets  # noqa: F401,E402

import pytest  # noqa: E402

pytest.importorskip('PyQt6')
preview = pytest.importorskip('miniqt.app.view.market_quote_preview')


@pytest.fixture(scope='module', autouse=True)
def _app():
    from PyQt6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def test_columns_match_quote_fields():
    keys = [c.key for c in preview._COLUMNS]
    # 代码 / 名称 + 快期那些 Quote 里有的字段
    for expected in ('symbol', 'name', 'last_price', 'bid_price1',
                     'bid_volume1', 'ask_price1', 'ask_volume1',
                     'upper_limit', 'lower_limit', 'chg', 'chg_pct',
                     'volume', 'open', 'highest', 'lowest', 'pre_close',
                     'pre_settlement', 'quote_time', 'price_tick', 'spark'):
        assert expected in keys
    # 快期有但 Quote 没有的（沉淀资金 / 资金流向）不应出现
    assert 'settle_fund' not in keys and 'fund_flow' not in keys


def test_clean_and_num():
    assert preview._clean(None) == ''
    assert preview._clean(float('nan')) == ''
    assert preview._clean('x') == 'x'
    assert preview._float('1.5') == 1.5
    assert preview._float(float('nan')) is None
    assert preview._float('x') is None
    assert preview._int('3') == 3
    assert preview._int(None) is None


def test_quote_open_uses_trading_time():
    from datetime import datetime

    class TradingTime:
        day = [['09:00:00', '10:15:00'], ['10:30:00', '11:30:00'],
               ['13:30:00', '15:00:00']]
        night = [['21:00:00', '25:00:00']]

    class Quote:
        trading_time = TradingTime()

    assert preview._quote_open(Quote(), datetime(2026, 10, 7, 10, 0))
    assert not preview._quote_open(Quote(), datetime(2026, 10, 7, 12, 0))
    # 夜盘跨 24:00：凌晨 1 点也算开盘
    assert preview._quote_open(Quote(), datetime(2026, 10, 7, 1, 0))
    assert not preview._quote_open(Quote(), datetime(2026, 10, 7, 4, 0))
    # 没有交易时段 → 不算开盘
    assert not preview._quote_open(object(), datetime(2026, 10, 7, 10, 0))


def test_chip_row_selects_and_reports_key():
    chips = preview._ChipRow()
    chips.set_items([('FUTURE', '期货'), ('STOCK', '股票')], active='FUTURE')
    assert chips.keys() == ['FUTURE', 'STOCK']
    assert chips.current_key() == 'FUTURE'
    chips.set_current('STOCK')
    assert chips.current_key() == 'STOCK'
    chips.set_items([('CONT', '主连'), ('FUTURE', '期货')])
    assert chips.current_key() == 'CONT'


def test_rows_from_frame_keeps_code_and_name_only():
    import pandas as pd

    page = preview.MarketQuotePreviewInterface.__new__(
        preview.MarketQuotePreviewInterface)
    frame = pd.DataFrame([{
        'instrument_id': 'SHFE.rb2601', 'instrument_name': '螺纹钢',
        'ins_class': 'FUTURE', 'exchange_id': 'SHFE', 'product_id': 'rb',
    }])
    rows = page._rows_from_frame(frame)
    assert len(rows) == 1
    row = rows[0]
    assert row['symbol'] == 'SHFE.rb2601'
    assert row['name'] == '螺纹钢'
    # 行情字段先留空
    assert row['last_price'] is None and row['chg'] is None
    assert page._type_by_symbol['SHFE.rb2601'] == 'FUTURE'
    assert 'SHFE.rb2601' in page._base_by_symbol


def test_empty_frame_gives_no_rows():
    page = preview.MarketQuotePreviewInterface.__new__(
        preview.MarketQuotePreviewInterface)
    assert page._rows_from_frame(None) == []


def test_live_row_merges_base_and_quote():
    page = preview.MarketQuotePreviewInterface.__new__(
        preview.MarketQuotePreviewInterface)
    page._base_by_symbol = {
        'SHFE.rb2601': {'symbol': 'SHFE.rb2601', 'name': '螺纹钢',
                        'spark': [], 'last_price': None}}
    page._spark_history = {}

    class Quote:
        last_price = 3112.0
        pre_settlement = 3090.0
        bid_price1 = 3111.0
        bid_volume1 = 3
        ask_price1 = 3112.0
        ask_volume1 = 4
        upper_limit = 3200.0
        lower_limit = 2980.0
        volume = 12345
        open = 3100.0
        highest = 3120.0
        lowest = 3080.0
        pre_close = 3095.0
        datetime = '2026-10-07 10:00:00'
        price_tick = 1.0

    row = page._live_row('SHFE.rb2601', Quote())
    assert row['symbol'] == 'SHFE.rb2601'
    assert row['name'] == '螺纹钢'
    assert row['last_price'] == 3112.0
    assert round(row['chg'], 4) == 22.0
    assert round(row['chg_pct'], 4) == round(22 / 3090 * 100, 4)
    assert row['quote_time'] == '2026-10-07 10:00:00'
    # record=False（筛选 / 重绘）不记走势
    assert row['spark'] == []
    # record=True（实时 tick）才把最新价记进走势
    row = page._live_row('SHFE.rb2601', Quote(), record=True)
    assert row['spark'] == [3112.0]


def test_spark_frames_merge_and_cap():
    page = preview.MarketQuotePreviewInterface.__new__(
        preview.MarketQuotePreviewInterface)
    page._spark_history = {}

    class _Worker:
        deleted = False

        def deleteLater(self):
            self.deleted = True

    worker = _Worker()
    page._spark_worker = worker
    page.isVisible = lambda: False
    page._render_visible = lambda: None
    long_history = list(range(100))
    page._on_spark_frames({'SHFE.rb2601': long_history})
    assert page._spark_history['SHFE.rb2601'] == \
        long_history[-preview.SPARK_POINTS:]
    # 引用必须**留到线程真正结束**（``finished``）再清：``finished_frames`` 在
    # ``run()`` 返回前就发了，提前置空会把还在收尾的 QThread 回收 →
    # ``Fatal: QThread: Destroyed while thread ... is still running`` ✗
    assert page._spark_worker is worker
    page._on_spark_finished(worker)
    assert page._spark_worker is None
    assert worker.deleted is True


def test_live_row_uses_seeded_spark_history():
    page = preview.MarketQuotePreviewInterface.__new__(
        preview.MarketQuotePreviewInterface)
    page._base_by_symbol = {'SHFE.rb2601': {'symbol': 'SHFE.rb2601',
                                            'name': '螺纹钢', 'spark': []}}
    page._spark_history = {'SHFE.rb2601': [1.0, 2.0]}

    class Quote:
        last_price = 2.0
        pre_settlement = 2.0

    row = page._live_row('SHFE.rb2601', Quote())
    assert row['spark'] == [1.0, 2.0]          # 价格没变，不追加


def test_render_visible_only_updates_current_rows():
    """切类型 / 交易所后，旧的可视行不能经 update_rows 被“加回来”。"""
    page = preview.MarketQuotePreviewInterface.__new__(
        preview.MarketQuotePreviewInterface)
    page._base_by_symbol = {}
    page._spark_history = {}
    page._quotes = {}
    page._visible_symbols = ['A', 'OLD']
    page._current_set = {'A', 'B'}
    calls = []

    class Grid:
        def update_rows(self, rows):
            calls.append([row['symbol'] for row in rows])

    page._grid = Grid()
    page._render_visible()
    assert calls == [['A']]


def test_tape_items_cover_all_current_symbols():
    """Ticker Tape 展示当前页所有合约（代码 / 名称 + 已缓存行情）。"""
    page = preview.MarketQuotePreviewInterface.__new__(
        preview.MarketQuotePreviewInterface)
    page._base_by_symbol = {'A': {'symbol': 'A', 'name': '甲'},
                            'B': {'symbol': 'B', 'name': '乙'}}
    page._quotes = {}
    page._tape_symbols = ['A', 'B']
    captured = []

    class Ticker:
        def set_data(self, items):
            captured.append(items)

    page._ticker = Ticker()
    page._sync_tape()
    assert [item['symbol'] for item in captured[0]] == ['A', 'B']
    assert captured[0][0]['name'] == '甲'
    assert captured[0][0]['last'] is None


def test_ticker_tape_height_is_increased():
    """Ticker Tape 高度 31（原 36 基础上矮 5，用户要求 ✓）。"""
    import inspect
    source = inspect.getsource(preview.MarketQuotePreviewInterface)
    assert 'setFixedHeight(31)' in source
    assert 'get_webview().setFixedHeight(36)' not in source


def test_row_count_moved_into_the_search_row():
    """「N 行」放在搜索栏后面；底部只放 Ticker Tape ✓。"""
    import inspect
    source = inspect.getsource(preview.MarketQuotePreviewInterface._build_ui)
    # 行数标签在搜索行里（搜索框后面）✓
    assert 'search_row' in source
    assert 'search_row.addWidget(self.statusLabel)' in source
    # 底部只剩 Ticker Tape（不再有 statusLabel）✓
    assert 'bottom' not in source
    assert 'statusLabel' not in source.split('_tapePanel', 1)[1]


# ---- 左击行情行：Symbol Overview 卡片 -------------------------------------
def test_left_click_menu_wiring_source():
    """左击行情行 → qfluentwidgets 气泡（Flyout + Symbol Overview + 倒计时）✓。

    ★ 不用 ``RoundMenu``（QMenu）—— 里面嵌 QWebEngineView 会**黑屏** ✗，
    用 ``Flyout``（顶层 Qt.Popup 窗口）才能渲染 ✓。
    """
    import inspect
    source = inspect.getsource(preview.MarketQuotePreviewInterface)
    assert 'self._grid.on_row_click(self._on_row_left_click)' in source
    assert 'def _on_row_left_click' in source
    assert 'def _ensure_overview' in source
    assert 'SymbolOverview' in source
    assert '_SymbolOverviewView' in source
    # 气泡视图：继承 FlyoutViewBase + 倒计时自动关 ✓
    view_source = inspect.getsource(preview._SymbolOverviewView)
    assert 'FlyoutViewBase' in view_source
    assert 'openChartRequested' in view_source
    assert 'def start_countdown' in view_source
    assert 'def _tick' in view_source
    # 外层的 Flyout（top-level Qt.Popup）+ 去掉阴影效果，否则 webview 可能不渲染 ✗
    assert 'Flyout(' in source
    assert 'setGraphicsEffect(None)' in source
    # 没连接天勤 → 不弹（用户要求 ✓）
    assert "getattr(self.main_window, 'tq_api', None) is None" in source


def test_overview_data_maps_row_fields():
    """行（基础 + Quote）→ SymbolOverview 的 data（键名对齐插件 ✓）。"""
    from types import SimpleNamespace

    cls = preview.MarketQuotePreviewInterface
    fake = SimpleNamespace(
        _exchangeChips=SimpleNamespace(current_key=lambda: 'SHFE'))
    row = {
        'symbol': 'SHFE.ag2612', 'name': '白银', 'last_price': 14716.0,
        'chg': 12.0, 'chg_pct': 0.08, 'open': 14700.0, 'highest': 14750.0,
        'lowest': 14690.0, 'pre_close': 14704.0, 'volume': 1234,
        'spark': [1.0, 2.0, 3.0],
    }
    data = cls._overview_data(fake, row)
    assert data['symbol'] == 'SHFE.ag2612'
    assert data['name'] == '白银'
    assert data['exchange'] == 'SHFE'
    assert data['last'] == 14716.0
    assert data['high'] == 14750.0            # highest → high ✓
    assert data['low'] == 14690.0             # lowest → low ✓
    assert data['pre_close'] == 14704.0
    assert data['spark'] == [1.0, 2.0, 3.0]


def test_stock_snapshot_runs_off_main_thread():
    """报价快照走**后台线程**（futu ``get_market_snapshot`` 不阻塞主线程）✓"""
    assert hasattr(preview, '_QuoteFetchWorker')
    import inspect
    source = inspect.getsource(preview)
    assert 'self._api.get_quote_list(' in source
    # 主线程只连信号、收结果，不在主线程直接 get_quote_list
    assert 'worker.fetched_quotes.connect(self._on_quotes_fetched)' in source
    assert 'def _on_quotes_fetched' in source
    # 完成回调里先摘列表再 deleteLater（不能再用 isFinished() 修剪，会访问已删对象 ✗）
    assert 'def _on_quote_worker_done' in source
    assert 'for w in workers if not w.isFinished()' not in source


def test_release_offpage_subs_keeps_only_overview_symbol():
    """股票走势订阅只保留**气泡当前选中**那个（按「可见」保留会打满 futu 额度 ✗）"""
    import inspect
    from miniqt.app.view import market_quote_preview as mod

    src = inspect.getsource(mod.MarketQuotePreviewInterface._release_offpage_subs)
    # 不再按「可见」保留
    assert "keep = {str(s) for s in (visible" not in src
    assert "keep = set()" in src
    assert "keep.add(overview)" in src


def test_stock_spark_is_single_symbol():
    """股票分时走势只给气泡那一个拉（60s × 120），不给整页可见行 ✓"""
    import inspect
    from miniqt.app.view import market_quote_preview as mod

    src = inspect.getsource(mod.MarketQuotePreviewInterface._seed_stock_spark)
    assert "_KlineFetchWorker(api, [symbol])" in src
    # 批量走势对 futu 供数的合约（股票 / 港美股期权）直接跳过（避免订阅额度打满）
    bulk = inspect.getsource(mod.MarketQuotePreviewInterface._maybe_fetch_spark)
    assert "_is_futu_symbol(s)" in bulk


def test_left_click_is_deferred_so_double_click_opens_chart():
    """双击要能开图：左击气泡必须**延后**弹，不能第一下单击就弹（否则模态气泡
    会吃掉第二下点击 → ``dblclick`` 永远到不了 ✗）。"""
    import inspect
    from miniqt.app.view import market_quote_preview as mod

    cls = mod.MarketQuotePreviewInterface
    click = inspect.getsource(cls._on_row_left_click)
    # 单击只起定时器，不再直接 _show_row_left_menu
    assert "_show_row_left_menu" not in click
    assert "_left_click_timer.start()" in click
    # 定时器到点才真的弹
    assert hasattr(cls, "_fire_left_click")
    fire = inspect.getsource(cls._fire_left_click)
    assert "_show_row_left_menu" in fire
    # 双击开图时取消待弹的左击气泡
    open_src = inspect.getsource(cls._open_chart)
    assert "_left_click_timer.stop()" in open_src
    # 延时取系统双击间隔（拿不到再用常量）
    assert "doubleClickInterval" in inspect.getsource(cls.__init__)
    assert mod.LEFT_CLICK_DELAY_MS > 0
