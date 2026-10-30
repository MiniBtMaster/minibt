"""Unit tests for :mod:`pylightcharts.panels` (no browser / no Qt).

A tiny fake window records the scripts a panel emits, so the serialisation and
the callback wiring can be asserted without starting a webview.
"""
import json

from pylightcharts.panels import (BrokerRating, BrokerReviews, Column,
                                  CompanyProfile, DataGrid, EconomicCalendar,
                                  FilterBar, FundamentalData, Heatmap,
                                  NewsFeed, Screener, SeasonalChart, Sparkline,
                                  TechnicalAnalysis, TextBlock, Ticker,
                                  seasonal_monthly, ta_summary)
from pylightcharts.panels.base import Panel


class FakeWindow:
    """Just enough of :class:`~pylightcharts.Window` to build panels on."""

    def __init__(self):
        self.scripts = []
        self.handlers = {}
        self._panels = []
        self._theme = None
        self.bulk_run = None

    def run_script(self, script, run_last=False):   # noqa: D401 - mimic Window
        self.scripts.append(script)


def test_column_defaults_and_overrides():
    column = Column('last', '最新', type='number', color_by='sign')
    data = column.to_dict()
    assert data['key'] == 'last'
    assert data['title'] == '最新'
    assert data['type'] == 'number'
    assert data['colorBy'] == 'sign'

    # title defaults to the key; explicit values win
    assert Column('symbol').to_dict()['title'] == 'symbol'
    assert Column('v', compact=True).to_dict()['compact'] is True


def test_datagrid_keeps_caller_field_names():
    """Panel data must **not** be camelCased (``open_interest`` stays)."""
    window = FakeWindow()
    grid = DataGrid(window, columns=[
        Column('symbol', '代码'),
        Column('open_interest', '持仓量', type='number', compact=True),
    ])
    grid.set_rows([{'symbol': 'DCE.l2609', 'open_interest': 331984}])
    joined = '\n'.join(window.scripts)
    assert 'open_interest' in joined
    assert 'openInterest' not in joined


def test_datagrid_registers_with_window():
    window = FakeWindow()
    grid = DataGrid(window, columns=[Column('symbol')])
    assert grid in window._panels
    # construction assigns a JS global at the panel handle
    assert any(script.startswith(f'{grid.id} = new Lib.DataGrid(')
               for script in window.scripts)


def test_datagrid_row_callback_dispatch():
    window = FakeWindow()
    seen = []
    grid = DataGrid(window, columns=[Column('symbol')],
                    on_row_click=lambda key: seen.append(('click', key)),
                    on_row_double_click=lambda key: seen.append(('dbl', key)))

    handler = window.handlers[grid.id]
    handler('DCE.l2609', 'rowclick')
    handler('DCE.pp2609', 'rowdblclick')
    assert seen == [('click', 'DCE.l2609'), ('dbl', 'DCE.pp2609')]
    # the JS side is told where to report row events
    assert any('callbackName' in script for script in window.scripts)


def test_datagrid_methods_emit_expected_calls():
    window = FakeWindow()
    grid = DataGrid(window, columns=[Column('symbol')])
    grid.set_filter('pp').sort('last', -1).set_cell('DCE.l2609', 'last', 8005)
    joined = '\n'.join(window.scripts)
    assert '.setFilter("pp")' in joined or ".setFilter('pp')" in joined
    assert '.sort("last", -1)' in joined or ".sort('last', -1)" in joined
    assert '.setCell("DCE.l2609", "last", 8005)' in joined


def test_datagrid_apply_theme_maps_window_spec():
    window = FakeWindow()
    grid = DataGrid(window, columns=[Column('symbol')])
    before = len(window.scripts)
    grid.apply_theme({'background': '#ffffff', 'text': '#131722',
                      'border_color': '#e0e3eb',
                      'hover_background': '#f0f3fa',
                      'table_section_background': '#f0f3fa'})
    emitted = '\n'.join(window.scripts[before:])
    assert '.setOptions(' in emitted
    assert '#ffffff' in emitted


def test_panel_delete_unregisters():
    window = FakeWindow()
    grid = DataGrid(window, columns=[Column('symbol')])
    grid.delete()
    assert grid not in window._panels
    assert any('.destroy()' in script for script in window.scripts)


def test_sparkline_creates_and_appends():
    window = FakeWindow()
    spark = Sparkline(window, width=160, height=40)
    assert spark in window._panels
    spark.set_data([1, 2, 3])
    joined = '\n'.join(window.scripts)
    assert 'new Lib.Sparkline(' in joined
    assert 'window.containerDiv' in joined
    assert '.setData([1,2,3])' in joined


def test_column_like_accepts_str_and_dict():
    window = FakeWindow()
    grid = DataGrid(window, columns=['symbol', {'key': 'last', 'type': 'number'}])
    assert grid in window._panels
    joined = '\n'.join(window.scripts)
    assert '"symbol"' in joined and '"last"' in joined


# --------------------------------------------------------------------- M2

def _rows(*symbols):
    return [{'symbol': s, 'last': 100 + i, 'chg_pct': i - 1}
            for i, s in enumerate(symbols)]


def test_tabs_callback_dispatch():
    from pylightcharts.panels import Tabs
    window = FakeWindow()
    seen = []
    tabs = Tabs(window, [('DCE', '大商所'), ('SHFE', '上期所')],
                on_change=seen.append)
    window.handlers[tabs.id]('SHFE')
    assert seen == ['SHFE']
    assert any('callbackName' in script for script in window.scripts)


def test_market_data_groups_swap():
    from pylightcharts.panels import MarketData
    window = FakeWindow()
    market = MarketData(window, groups={'DCE': _rows('DCE.l2609'),
                                        'SHFE': _rows('SHFE.rb2601')},
                        columns=['symbol', 'last'])
    assert market.active_group() == 'DCE'
    market._on_tab('SHFE')
    assert market.active_group() == 'SHFE'
    assert any('SHFE.rb2601' in script for script in window.scripts)
    # a child grid + tabs are registered, and the wrapper is a flex stack
    assert '.className=\'pylc-stack\'' in '\n'.join(window.scripts)


def test_watchlist_add_remove():
    from pylightcharts.panels import Watchlist
    window = FakeWindow()
    watch = Watchlist(window, rows=_rows('DCE.l2609'))
    assert watch.symbols() == ['DCE.l2609']
    watch.add({'symbol': 'DCE.pp2609', 'last': 8291})
    assert watch.symbols() == ['DCE.l2609', 'DCE.pp2609']
    watch.remove('DCE.l2609')
    assert watch.symbols() == ['DCE.pp2609']
    joined = '\n'.join(window.scripts)
    assert '.appendRows(' in joined and '.deleteRow(' in joined


def test_ticker_variants_layout():
    from pylightcharts.panels import TickerTag, TickerTape, SingleTicker, Tickers
    window = FakeWindow()
    TickerTape(window, [{'symbol': 'DCE.l2609'}])
    TickerTag(window, [{'symbol': 'DCE.l2609'}])
    SingleTicker(window, [{'symbol': 'DCE.l2609'}])
    Tickers(window, [{'symbol': 'DCE.l2609'}])
    joined = '\n'.join(window.scripts)
    assert joined.count('"layout":"scroll"') == 1
    assert joined.count('"layout":"wrap"') == 3
    assert 'new Lib.Ticker(' in joined


def test_symbol_overview_enables_spark():
    from pylightcharts.panels import SymbolOverview
    window = FakeWindow()
    SymbolOverview(window, {'symbol': 'DCE.l2609', 'last': 8005,
                            'spark': [1, 2, 3]})
    joined = '\n'.join(window.scripts)
    assert '"showSpark":true' in joined
    assert '"sparkWidth":240' in joined


def test_market_data_delete_removes_children():
    from pylightcharts.panels import MarketData
    window = FakeWindow()
    market = MarketData(window, columns=['symbol'])
    tabs, grid = market.tabs, market.grid
    market.delete()
    assert market not in window._panels
    assert tabs not in window._panels and grid not in window._panels


# --------------------------------------------------------------------- P2

def _last_setrows(window):
    for script in reversed(window.scripts):
        if '.setRows(' in script:
            return script
    return ''


def test_heatmap_creates_and_binds_click():
    window = FakeWindow()
    seen = []
    heat = Heatmap(window, [{'symbol': 'x', 'value': 1, 'chg_pct': 1.5}],
                   on_item_click=seen.append)
    window.handlers[heat.id]('x')
    assert seen == ['x']
    assert 'new Lib.Heatmap(' in '\n'.join(window.scripts)
    assert '"chg_pct":1.5' in '\n'.join(window.scripts)


def test_heatmap_aliases_exist():
    from pylightcharts.panels import (CryptoHeatmap, EtfHeatmap,
                                      ForexHeatmap, StockHeatmap)
    window = FakeWindow()
    StockHeatmap(window, [{'symbol': 'a', 'value': 1, 'chg_pct': 0}])
    CryptoHeatmap(window, [{'symbol': 'BTC', 'value': 1, 'chg_pct': 0}])
    EtfHeatmap(window, [{'symbol': 'SPY', 'value': 1, 'chg_pct': 0}])
    ForexHeatmap(window, [{'symbol': 'EURUSD', 'value': 1, 'chg_pct': 0}])
    assert '\n'.join(window.scripts).count('new Lib.Heatmap(') == 4


def test_seasonal_chart_set_data_and_from_frame():
    import numpy as np
    import pandas as pd
    window = FakeWindow()
    chart = SeasonalChart(window)
    chart.set_data([1.0, -2.0], ['1月', '2月'])
    script = '\n'.join(window.scripts)
    assert '.setData([' in script and '-2.0' in script

    index = pd.date_range('2022-01-01', periods=400, freq='D')
    frame = pd.DataFrame({'time': index, 'close': 100 + np.arange(400) * 0.1})
    chart.from_frame(frame)
    assert '.setData(' in '\n'.join(window.scripts)


def test_seasonal_monthly_returns_twelve_months():
    import numpy as np
    import pandas as pd
    index = pd.date_range('2022-01-01', periods=365, freq='D')
    frame = pd.DataFrame({'time': index, 'close': 100 + np.arange(365) * 0.1})
    data = seasonal_monthly(frame)
    assert len(data['labels']) == 12 and data['labels'][0] == '1月'
    # a monotonically rising series has a positive mean return every month
    assert all(value is None or value > 0 for value in data['values'])


def test_screener_composes_conditions():
    window = FakeWindow()
    rows = [
        {'symbol': 'a', 'chg_pct': 1.0, 'volume': 5000},
        {'symbol': 'b', 'chg_pct': 3.0, 'volume': 2000},
        {'symbol': 'c', 'chg_pct': 3.5, 'volume': 20000},
    ]
    screener = Screener(window, rows,
                        columns=['symbol', 'chg_pct', 'volume'])
    screener.add_filter('chg_pct', '>', 2)
    script = _last_setrows(window)
    assert '"symbol":"b"' in script and '"symbol":"c"' in script
    assert '"symbol":"a"' not in script

    screener.add_filter('volume', '>=', 10000)
    script = _last_setrows(window)
    assert '"symbol":"c"' in script and '"symbol":"b"' not in script
    assert screener.filters() == [('chg_pct', '>', 2), ('volume', '>=', 10000)]

    screener.clear_filters()
    script = _last_setrows(window)
    assert '"symbol":"a"' in script
    assert screener.filters() == []


def test_screener_rejects_unknown_operator():
    import pytest
    window = FakeWindow()
    screener = Screener(window, [], columns=['symbol'])
    with pytest.raises(ValueError):
        screener.add_filter('x', '~', 1)


# --------------------------------------------------- Heatmap / Screener deep

def test_heatmap_set_groups():
    window = FakeWindow()
    heat = Heatmap(window, [{'symbol': 'a', 'value': 1, 'chg_pct': 0}])
    heat.set_groups([{'name': '能源',
                      'items': [{'symbol': 'a', 'value': 1, 'chg_pct': 0}]}])
    script = '\n'.join(window.scripts)
    assert '.setGroups(' in script and '"items":' in script


def test_column_colors_map():
    column = Column('importance', colors={'高': '#ef5350', '低': '#787b86'})
    assert column.to_dict()['colors'] == {'高': '#ef5350', '低': '#787b86'}


def test_screener_match_any():
    window = FakeWindow()
    rows = [{'symbol': 'a', 'x': 5, 'y': 0},
            {'symbol': 'b', 'x': 0, 'y': 5},
            {'symbol': 'c', 'x': 0, 'y': 0}]
    screener = Screener(window, rows, columns=['symbol'])
    screener.set_match('any')
    screener.add_filter('x', '>', 1)
    screener.add_filter('y', '>', 1)
    script = _last_setrows(window)
    assert '"symbol":"a"' in script and '"symbol":"b"' in script
    assert '"symbol":"c"' not in script
    assert screener.match() == 'any'


def test_screener_set_filters_and_on_change():
    window = FakeWindow()
    seen = []
    screener = Screener(window, [{'symbol': 'a', 'v': 1}],
                        columns=['symbol'], on_change=seen.append)
    screener.set_filters([('v', '>=', 1)])
    assert screener.filters() == [('v', '>=', 1)]
    assert seen and seen[-1] == [('v', '>=', 1)]


def test_screener_bind_filter_bar_round_trip():
    window = FakeWindow()
    rows = [{'symbol': 'a', 'chg_pct': 1}, {'symbol': 'b', 'chg_pct': 3}]
    screener = Screener(window, rows, columns=['symbol', 'chg_pct'])
    bar = FilterBar(window)
    screener.bind_filter_bar(bar)
    screener._on_bar_change([{'column': 'chg_pct', 'op': '>', 'value': 2}])
    assert screener.filters() == [('chg_pct', '>', 2)]
    script = _last_setrows(window)
    assert '"symbol":"b"' in script and '"symbol":"a"' not in script


def test_filterbar_decodes_callback():
    import base64
    import json
    window = FakeWindow()
    seen = []
    bar = FilterBar(window, on_change=seen.append)
    payload = base64.b64encode(json.dumps(
        [{'column': 'x', 'op': '>', 'value': 1}]).encode()).decode()
    window.handlers[bar.id](payload)
    assert seen == [[{'column': 'x', 'op': '>', 'value': 1}]]
    assert bar.get_filters() == [{'column': 'x', 'op': '>', 'value': 1}]


# ------------------------------------------------------------- P3 shells

def test_newsfeed_click_reports_index():
    window = FakeWindow()
    seen = []
    feed = NewsFeed(window, [{'title': 't'}], on_item_click=seen.append)
    window.handlers[feed.id]('0')
    assert seen == [0]
    assert 'new Lib.NewsFeed(' in '\n'.join(window.scripts)


def test_textblock_text_and_html():
    window = FakeWindow()
    block = TextBlock(window, html='<p>hi</p>')
    block.set_text('plain')
    script = '\n'.join(window.scripts)
    assert 'new Lib.TextBlock(' in script
    assert '.setOptions(' in script


def test_detail_shells_build():
    window = FakeWindow()
    EconomicCalendar(window, [{'time': '20:30', 'event': 'CPI', 'importance': '高'}])
    FundamentalData(window, [{'name': 'PE', 'value': 28.4}])
    BrokerRating(window, [{'broker': 'X', 'rating': '买入'}])
    BrokerReviews(window, [{'broker': 'X', 'review': '好'}])
    profile = CompanyProfile(window, {'name': '苹果'}, html='<p>desc</p>')
    assert profile.header is not None and profile.description is not None
    script = '\n'.join(window.scripts)
    assert script.count('new Lib.DataGrid(') >= 4
    assert 'pylc-stack' in script


# --------------------------------------------- Screener presets / persistence

def test_screener_presets_round_trip():
    window = FakeWindow()
    rows = [{'symbol': 'a', 'chg_pct': 1}, {'symbol': 'b', 'chg_pct': 3}]
    screener = Screener(window, rows, columns=['symbol', 'chg_pct'])
    screener.add_filter('chg_pct', '>', 2)
    screener.save_preset('up')
    screener.clear_filters()
    assert screener.presets() == {'up': [('chg_pct', '>', 2)]}
    screener.apply_preset('up')
    assert screener.filters() == [('chg_pct', '>', 2)]
    screener.delete_preset('up')
    assert screener.presets() == {}


def test_screener_persistence_round_trip():
    window = FakeWindow()
    rows = [{'symbol': 'a', 'chg_pct': 1}, {'symbol': 'b', 'chg_pct': 3}]
    screener = Screener(window, rows, columns=['symbol', 'chg_pct'])
    screener.set_match('any')
    screener.add_filter('chg_pct', '>', 2)
    screener.save_preset('up')
    screener.sort('chg_pct', -1)
    screener.set_filter('b')

    data = screener.to_dict()
    restored = Screener(window, rows, columns=['symbol', 'chg_pct'])
    restored.load_dict(data)
    assert restored.filters() == [('chg_pct', '>', 2)]
    assert restored.match() == 'any'
    assert restored.presets() == {'up': [('chg_pct', '>', 2)]}
    assert restored._sort_column == 'chg_pct'
    assert restored._sort_direction == -1
    assert restored._filter_text == 'b'


def test_screener_save_and_load_file(tmp_path):
    window = FakeWindow()
    screener = Screener(window, [{'symbol': 'a', 'v': 1}], columns=['symbol'])
    screener.add_filter('v', '>=', 1)
    screener.save_preset('p', [('v', '>', 0)])
    path = tmp_path / 'screen.json'
    screener.save(path)
    assert path.exists()

    restored = Screener(window, [{'symbol': 'a', 'v': 1}], columns=['symbol'])
    restored.load(path)
    assert restored.filters() == [('v', '>=', 1)]
    assert restored.presets() == {'p': [('v', '>', 0)]}


def test_datagrid_tracks_sort_and_filter():
    window = FakeWindow()
    grid = DataGrid(window, columns=['symbol'])
    grid.sort('last', -1).set_filter('pp')
    assert grid._sort_column == 'last'
    assert grid._sort_direction == -1
    assert grid._filter_text == 'pp'


def test_heatmap_legend_option():
    window = FakeWindow()
    Heatmap(window, [{'symbol': 'a', 'value': 1, 'chg_pct': 0}],
            show_legend=False)
    assert '"showLegend":false' in '\n'.join(window.scripts)


# ------------------------------------------------------ Technical Analysis

def _ta_frame(rows=400, seed=3):
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.6)
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': close + 0.1, 'high': close + 1.0, 'low': close - 1.0,
        'close': close, 'volume': rng.integers(1_000, 20_000, rows)})


def test_ta_summary_computes_signals():
    summary = ta_summary(_ta_frame())
    assert -1.0 <= summary['score'] <= 1.0
    assert len(summary['oscillators']) >= 6
    assert len(summary['moving_averages']) == 12      # 6 periods x (SMA + EMA)
    total = sum(summary['counts'].values())
    assert total == len(summary['oscillators']) + len(summary['moving_averages'])
    signals = {row['signal'] for row in summary['oscillators']}
    assert signals <= {'buy', 'neutral', 'sell'}


def test_ta_summary_handles_short_frame():
    import pandas as pd
    summary = ta_summary(pd.DataFrame({'close': [1.0]}))
    assert summary['oscillators'] == [] and summary['score'] == 0.0


def test_technical_analysis_creates():
    window = FakeWindow()
    TechnicalAnalysis(window, ta_summary(_ta_frame()))
    script = '\n'.join(window.scripts)
    assert 'new Lib.TechnicalAnalysis(' in script
    assert '"score":' in script and '"moving_averages":' in script


# ------------------------------------------------------ dark / light themes

def test_panels_follow_window_theme_on_creation():
    from pylightcharts.themes import resolve
    window = FakeWindow()
    window._theme = resolve('light')
    DataGrid(window, columns=['symbol'])
    script = '\n'.join(window.scripts)
    assert '"background":"#ffffff"' in script
    assert '"scrollbar":"#c9ced6"' in script
    assert 'rgba(0,0,0,0.03)' in script          # light stripes


def test_datagrid_apply_light_vs_dark():
    from pylightcharts.themes import resolve
    window = FakeWindow()
    grid = DataGrid(window, columns=['symbol'])
    before = len(window.scripts)
    grid.apply_theme(resolve('light'))
    light = '\n'.join(window.scripts[before:])
    assert '"scrollbar":"#c9ced6"' in light
    before = len(window.scripts)
    grid.apply_theme(resolve('dark'))
    dark = '\n'.join(window.scripts[before:])
    assert '"scrollbar":"#3a3f4b"' in dark


def test_heatmap_light_neutral_and_legend():
    from pylightcharts.themes import resolve
    window = FakeWindow()
    heat = Heatmap(window, [{'symbol': 'a', 'value': 1, 'chg_pct': 0}])
    before = len(window.scripts)
    heat.apply_theme(resolve('light'))
    script = '\n'.join(window.scripts[before:])
    assert '"neutral":"#c7ccd6"' in script
    assert 'legendBackground' in script


def test_sparkline_follows_theme():
    from pylightcharts.themes import resolve
    window = FakeWindow()
    spark = Sparkline(window)
    before = len(window.scripts)
    spark.apply_theme(resolve('light'))
    script = '\n'.join(window.scripts[before:])
    assert 'upColor' in script and 'downColor' in script


def test_ticker_hover_is_themed():
    from pylightcharts.themes import resolve
    window = FakeWindow()
    ticker = Ticker(window, [{'symbol': 'x'}])
    before = len(window.scripts)
    ticker.apply_theme(resolve('light'))
    script = '\n'.join(window.scripts[before:])
    assert '"hover":"#f0f3fa"' in script
