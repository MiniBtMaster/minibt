"""
pylightcharts: TradingView Lightweight Charts™ for Python

- pylightcharts embeds the official TradingView Lightweight Charts™ renderer
  in a WebView and drives it from Python, aiming at near-full API coverage
  with a pythonic interface.
- It is not a re-implementation of the charting engine: the pixels and the
  interactions come from the upstream JavaScript library, so visual fidelity
  and performance match the JS version while Python controls every option.

Core features:
- Full coverage of the Lightweight Charts v5.2.1 API (150/150 interface
  methods)
- Series types: candlestick, bar, line, area, baseline and histogram, plus
  custom series, polygon charts and numeric options / yield-curve charts
- 17 indicators, 13 drawing tools, shapes, tables, toolboxes and top bars
- v5 plugins (series markers, up/down markers, text and image watermarks),
  declarative series / pane primitives and a custom horizontal scale
- Multiple GUI backends: pywebview (default), Qt WebEngine (PySide6 / PyQt5 /
  PyQt6), wx, and browser-less targets (Jupyter, Streamlit, static / headless)
- Cheap import: no GUI toolkit is bound up front, backends are resolved on
  first attribute access (:pep:`562`), because the first Qt binding loaded
  wins for the whole process - the browser/static/headless targets
  (``pylightcharts.widgets``) do not bind Qt either, only ``QtChart`` does
- Drop-in compatibility with lightweight-charts-python
  (``pylightcharts.compat``)

Resources:
- Author: owen (MiniBtMaster)
- Version: 0.1.6
- License: MIT License (charting engine: Apache-2.0, see NOTICE)
- GitHub: https://github.com/MiniBtMaster/pylightcharts
- PyPI: https://pypi.org/project/pylightcharts/
- Documentation: see the ``docs/`` folder of the repository
- Contact: 407841129@qq.com
"""
from typing import TYPE_CHECKING

from . import (colors, compat, constants, history, indicators, overlay,
               plugins, primitives, qt, shapes, tooltips)
from .colors import color_by
from .abstract import (
    AbstractChart,
    Area,
    Bar,
    Baseline,
    BridgeSeries,
    CustomSeries,
    Window,
    set_attribution_logo,
)

if TYPE_CHECKING:
    # Explicit imports (no ``import *``) so static checkers and IDEs resolve
    # the names in ``__all__`` / ``_LAZY`` without also pulling in every module
    # global of those modules. Must be kept in sync with ``_LAZY`` below -- the
    # lazy attribute access itself happens in ``__getattr__`` at runtime.
    from .chart import Chart, WindowStartError
    from .indicators_api import IndicatorMixin
    from .numeric import (
        AbstractOptionsChart,
        AbstractYieldCurveChart,
        OptionsChart,
        YieldCurveChart,
    )
    from .plugins import (
        ImageWatermarkPlugin,
        SeriesMarkersPlugin,
        TextWatermarkPlugin,
        UpDownMarkersPlugin,
    )
    from .polygon_chart import PolygonChart
    from .price_scale import PriceLine, PriceScale
    from .primitives import PanePrimitive, SeriesPrimitive
    from .tooltips import Tooltip
    from .widgets import (
        BrowserChart,
        JupyterChart,
        QtChart,
        QtPanel,
        StaticLWC,
        StreamlitChart,
        WxChart,
    )
    from .panels.base import Panel
    from .panels.data_grid import Column, DataGrid
    from .panels.details import (BrokerRating, BrokerReviews, CompanyProfile,
                                 EconomicCalendar, FundamentalData)
    from .panels.filter_bar import FilterBar
    from .panels.heatmap import (CryptoHeatmap, EtfHeatmap, ForexHeatmap,
                                 Heatmap, StockHeatmap)
    from .panels.market import MarketData, Watchlist
    from .panels.news import NewsFeed, TopStories
    from .panels.quote import MiniChart, QuoteHeader, SymbolInfo, SymbolOverview
    from .panels.screener import Screener
    from .panels.seasonal import SeasonalChart, seasonal_monthly
    from .panels.sparkline import Sparkline
    from .panels.tabs import Tabs
    from .panels.technical import TechnicalAnalysis, ta_summary
    from .panels.text_block import TextBlock
    from .panels.ticker import (SingleTicker, Ticker, TickerTag, Tickers,
                                TickerTape)

__version__ = '0.1.6'
__version_info__ = (0, 1, 6)
__author__ = 'owen'
__email__ = '407841129@qq.com'
__license__ = 'MIT'
__copyright__ = 'Copyright (c) 2025 pylightcharts contributors'
__url__ = 'https://github.com/MiniBtMaster/pylightcharts'
__description__ = ('TradingView Lightweight Charts for Python '
                   '(bridged, near-full API coverage)')

#: name -> (module, attribute); imported on first use
_LAZY = {
    'BrowserChart': ('.widgets', 'BrowserChart'),
    'Chart': ('.chart', 'Chart'),
    'JupyterChart': ('.widgets', 'JupyterChart'),
    'QtChart': ('.widgets', 'QtChart'),
    'QtPanel': ('.widgets', 'QtPanel'),
    'DataGrid': ('.panels.data_grid', 'DataGrid'),
    'Column': ('.panels.data_grid', 'Column'),
    'Sparkline': ('.panels.sparkline', 'Sparkline'),
    'Panel': ('.panels.base', 'Panel'),
    'MiniChart': ('.panels.quote', 'MiniChart'),
    'Tabs': ('.panels.tabs', 'Tabs'),
    'MarketData': ('.panels.market', 'MarketData'),
    'Watchlist': ('.panels.market', 'Watchlist'),
    'Ticker': ('.panels.ticker', 'Ticker'),
    'TickerTape': ('.panels.ticker', 'TickerTape'),
    'TickerTag': ('.panels.ticker', 'TickerTag'),
    'SingleTicker': ('.panels.ticker', 'SingleTicker'),
    'Tickers': ('.panels.ticker', 'Tickers'),
    'QuoteHeader': ('.panels.quote', 'QuoteHeader'),
    'SymbolInfo': ('.panels.quote', 'SymbolInfo'),
    'SymbolOverview': ('.panels.quote', 'SymbolOverview'),
    'Screener': ('.panels.screener', 'Screener'),
    'Heatmap': ('.panels.heatmap', 'Heatmap'),
    'StockHeatmap': ('.panels.heatmap', 'StockHeatmap'),
    'CryptoHeatmap': ('.panels.heatmap', 'CryptoHeatmap'),
    'EtfHeatmap': ('.panels.heatmap', 'EtfHeatmap'),
    'ForexHeatmap': ('.panels.heatmap', 'ForexHeatmap'),
    'SeasonalChart': ('.panels.seasonal', 'SeasonalChart'),
    'seasonal_monthly': ('.panels.seasonal', 'seasonal_monthly'),
    'FilterBar': ('.panels.filter_bar', 'FilterBar'),
    'NewsFeed': ('.panels.news', 'NewsFeed'),
    'TopStories': ('.panels.news', 'TopStories'),
    'TextBlock': ('.panels.text_block', 'TextBlock'),
    'TechnicalAnalysis': ('.panels.technical', 'TechnicalAnalysis'),
    'ta_summary': ('.panels.technical', 'ta_summary'),
    'EconomicCalendar': ('.panels.details', 'EconomicCalendar'),
    'FundamentalData': ('.panels.details', 'FundamentalData'),
    'CompanyProfile': ('.panels.details', 'CompanyProfile'),
    'BrokerRating': ('.panels.details', 'BrokerRating'),
    'BrokerReviews': ('.panels.details', 'BrokerReviews'),
    'StreamlitChart': ('.widgets', 'StreamlitChart'),
    'StaticLWC': ('.widgets', 'StaticLWC'),
    'WxChart': ('.widgets', 'WxChart'),
    'WindowStartError': ('.chart', 'WindowStartError'),
    'OptionsChart': ('.numeric', 'OptionsChart'),
    'YieldCurveChart': ('.numeric', 'YieldCurveChart'),
    'AbstractOptionsChart': ('.numeric', 'AbstractOptionsChart'),
    'AbstractYieldCurveChart': ('.numeric', 'AbstractYieldCurveChart'),
    'PolygonChart': ('.polygon_chart', 'PolygonChart'),
    'PriceLine': ('.price_scale', 'PriceLine'),
    'PriceScale': ('.price_scale', 'PriceScale'),
    'IndicatorMixin': ('.indicators_api', 'IndicatorMixin'),
    'SeriesMarkersPlugin': ('.plugins', 'SeriesMarkersPlugin'),
    'UpDownMarkersPlugin': ('.plugins', 'UpDownMarkersPlugin'),
    'TextWatermarkPlugin': ('.plugins', 'TextWatermarkPlugin'),
    'ImageWatermarkPlugin': ('.plugins', 'ImageWatermarkPlugin'),
    'SeriesPrimitive': ('.primitives', 'SeriesPrimitive'),
    'PanePrimitive': ('.primitives', 'PanePrimitive'),
    'Tooltip': ('.tooltips', 'Tooltip'),
}

#: public names; the lazily resolved ones (see ``_LAZY``) and the module
#: metadata are listed too, so that static checkers, ``dir()`` and
#: ``from pylightcharts import *`` can see them
def prewarm() -> None:
    """Start the native window's renderer process **early** (≈2 s, opt-in).

    A native :class:`Chart` runs its window in a ``multiprocessing`` child
    (pywebview + WebView2 initialisation plus the page load), which costs about
    two seconds. It used to happen on the last line - ``chart.show()`` - after
    the script had already imported, computed indicators and built the chart,
    so that time was fully serial and looked like "the chart never opens".

    Call this right after the import (or as soon as you know a window will be
    needed) and those two seconds overlap with everything else:

    .. code-block:: python

        import pylightcharts

        pylightcharts.prewarm()          # <- window spins up in the background
        chart = pylightcharts.Chart()
        chart.set(frame)                 # data + indicators are built meanwhile
        chart.show(block=True)           # now instant

    Idempotent and a no-op for the browser/headless targets (they never create
    this child process).
    """
    from .chart import Chart
    Chart.WV.prewarm()


__all__ = [
    'AbstractChart', 'AbstractOptionsChart', 'AbstractYieldCurveChart', 'Area',
    'Bar', 'Baseline', 'BridgeSeries', 'BrowserChart', 'Chart', 'CustomSeries',
    'ImageWatermarkPlugin', 'IndicatorMixin', 'JupyterChart', 'OptionsChart',
    'PanePrimitive', 'PolygonChart', 'PriceLine', 'PriceScale', 'QtChart',
    'QtPanel', 'DataGrid', 'Sparkline', 'Panel', 'Column', 'MiniChart',
    'Tabs', 'MarketData', 'Watchlist', 'Ticker', 'TickerTape', 'TickerTag',
    'SingleTicker', 'Tickers', 'QuoteHeader', 'SymbolInfo', 'SymbolOverview',
    'Screener', 'Heatmap', 'StockHeatmap', 'CryptoHeatmap', 'EtfHeatmap',
    'ForexHeatmap', 'SeasonalChart', 'seasonal_monthly',
    'FilterBar', 'NewsFeed', 'TopStories', 'TextBlock',
    'TechnicalAnalysis', 'ta_summary',
    'EconomicCalendar', 'FundamentalData', 'CompanyProfile',
    'BrokerRating', 'BrokerReviews',
    'SeriesMarkersPlugin', 'SeriesPrimitive', 'StaticLWC', 'StreamlitChart',
    'TextWatermarkPlugin', 'Tooltip', 'UpDownMarkersPlugin', 'Window',
    'WxChart', 'WindowStartError',
    'YieldCurveChart', '__author__', '__copyright__', '__description__',
    '__email__', '__license__', '__url__', '__version__', '__version_info__',
    'color_by', 'colors', 'compat', 'constants', 'indicators', 'plugins',
    'prewarm',
    'history', 'overlay', 'primitives', 'qt', 'set_attribution_logo',
    'shapes',
    'tooltips',
]


def __getattr__(name):
    entry = _LAZY.get(name)
    if entry is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    from importlib import import_module

    module = import_module(entry[0], __name__)
    value = getattr(module, entry[1])
    globals()[name] = value            # cache for subsequent lookups
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY))
