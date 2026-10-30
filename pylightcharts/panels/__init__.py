"""TradingView-style financial panels built on the Lightweight Charts host page.

These are plain DOM/canvas components (not chart engines) driven from Python
through the same bridge as charts. They are the building blocks for the market
widgets.

.. code-block:: python

    from pylightcharts import QtPanel
    from pylightcharts.panels import Column, DataGrid, TickerTape

    panel = QtPanel()
    DataGrid(panel.win, columns=[
        Column('symbol', '代码'),
        Column('last', '最新', type='number', color_by='sign'),
        Column('chg_pct', '涨跌幅', type='percent'),
        Column('spark', '走势', type='spark'),
    ]).set_rows(rows)

    TickerTape(panel.win, items=ticker_items)

Overview of the panels:

- :class:`DataGrid` / :class:`Column` — sortable / filterable / virtualised table
- :class:`Sparkline` / :class:`MiniChart` — canvas mini charts
- :class:`Tabs` — a group switcher
- :class:`MarketData` / :class:`Watchlist` — table + tabs / self-selected list
- :class:`Ticker` (+ :class:`TickerTape`, :class:`TickerTag`,
  :class:`SingleTicker`, :class:`Tickers`) — quote strips
- :class:`QuoteHeader` (+ :class:`SymbolInfo`, :class:`SymbolOverview`) —
  symbol quote headers
"""
from .base import Panel
from .data_grid import Column, DataGrid
from .details import (BrokerRating, BrokerReviews, CompanyProfile,
                      EconomicCalendar, FundamentalData)
from .filter_bar import FilterBar
from .heatmap import (CryptoHeatmap, EtfHeatmap, ForexHeatmap, Heatmap,
                      StockHeatmap)
from .market import MarketData, Watchlist
from .news import NewsFeed, TopStories
from .order_ticket import OrderTicket
from .quote import MiniChart, QuoteHeader, SymbolInfo, SymbolOverview
from .quote_board import QuoteBoard
from .alert_dialog import AlertDialog
from .symbol_search import SymbolSearch
from .indicator_picker import IndicatorPicker, TemplatePicker
from .screener import Screener
from .seasonal import SeasonalChart, seasonal_monthly
from .sparkline import Sparkline
from .tabs import Tabs
from .technical import TechnicalAnalysis, ta_summary
from .text_block import TextBlock
from .ticker import SingleTicker, Ticker, TickerTag, Tickers, TickerTape

__all__ = [
    'Panel',
    'DataGrid', 'Column', 'Sparkline', 'MiniChart', 'Tabs',
    'MarketData', 'Watchlist', 'Screener', 'FilterBar',
    'Ticker', 'TickerTape', 'TickerTag', 'SingleTicker', 'Tickers',
    'QuoteHeader', 'SymbolInfo', 'SymbolOverview', 'QuoteBoard',
    'AlertDialog', 'SymbolSearch', 'IndicatorPicker',
    'TemplatePicker',
    'Heatmap', 'StockHeatmap', 'CryptoHeatmap', 'EtfHeatmap', 'ForexHeatmap',
    'SeasonalChart', 'seasonal_monthly',
    'NewsFeed', 'TopStories', 'TextBlock',
    'OrderTicket',
    'TechnicalAnalysis', 'ta_summary',
    'EconomicCalendar', 'FundamentalData', 'CompanyProfile',
    'BrokerRating', 'BrokerReviews',
]
