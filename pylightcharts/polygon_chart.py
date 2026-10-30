"""Standalone Polygon.io callback chart.

Separate from :mod:`pylightcharts.polygon` on purpose: that module is imported
by every chart (for `PolygonAPI`), and `Chart` pulls in pywebview.
"""
import datetime as dt

import pandas as pd

from .chart import Chart
from .polygon import _convert_timeframe


class PolygonChart(Chart):
    """
    A prebuilt callback chart object allowing for a standalone, plug-and-play
    experience of Polygon.io's API.

    Tickers, security types and timeframes are to be defined within the chart window.

    If using the standard `show` method, the `block` parameter must be set to True.
    `show_async` can also be used.
    """
    def __init__(
            self, api_key: str, live: bool = False, num_bars: int = 200, end_date: str = 'now', limit: int = 5_000,
            timeframe_options: tuple = ('1min', '5min', '30min', 'D', 'W'),
            security_options: tuple = ('Stock', 'Option', 'Index', 'Forex', 'Crypto'),
            toolbox: bool = True, width: int = 800, height: int = 600, x: int = None, y: int = None,
            on_top: bool = False, maximize: bool = False, debug: bool = False,
            title: str = '', screen: int = None,
    ):
        super().__init__(width, height, x, y, title, screen, on_top, maximize, debug, toolbox)

        self.num_bars = num_bars
        self.end_date = end_date
        self.limit = limit
        self.live = live
        self.win.style(
            active_background_color='rgba(91, 98, 246, 0.8)',
            muted_background_color='rgba(91, 98, 246, 0.5)'
        )
        self.polygon.api_key(api_key)
        self.events.search += self.on_search
        self.legend(True)
        self.grid(False, False)
        self.crosshair(vert_visible=False, horz_visible=False)

        self.topbar.textbox('symbol')
        self.topbar.switcher('timeframe', timeframe_options, func=self._on_timeframe_selection)
        self.topbar.switcher('security', security_options, func=self._on_security_selection)

        self.run_script(f'''
        {self.id}.search.window.style.display = "flex"
        {self.id}.search.box.focus()
        ''')

    async def _polygon(self, symbol):
        self.spinner(True)
        self.set(pd.DataFrame(), True)
        self.crosshair(vert_visible=False, horz_visible=False)

        mult, span = _convert_timeframe(self.topbar['timeframe'].value)
        delta = dt.timedelta(**{span + 's': int(mult)})
        short_delta = (delta < dt.timedelta(days=7))
        start_date = dt.datetime.now() if self.end_date == 'now' else dt.datetime.strptime(self.end_date, '%Y-%m-%d')
        remaining_bars = self.num_bars
        while remaining_bars > 0:
            start_date -= delta
            if start_date.weekday() > 4 and short_delta:  # Monday to Friday (0 to 4)
                continue
            remaining_bars -= 1
        epoch = dt.datetime.fromtimestamp(0)
        start_date = epoch if start_date < epoch else start_date
        success = await getattr(self.polygon, 'async_'+self.topbar['security'].value.lower())(
            symbol,
            timeframe=self.topbar['timeframe'].value,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=self.end_date,
            limit=self.limit,
            live=self.live
        )
        self.spinner(False)
        self.crosshair() if success else None
        return success

    async def on_search(self, chart, searched_string):
        chart.topbar['symbol'].set(searched_string if await self._polygon(searched_string) else '')

    async def _on_timeframe_selection(self, chart):
        await self._polygon(chart.topbar['symbol'].value) if chart.topbar['symbol'].value else None

    async def _on_security_selection(self, chart):
        self.precision(5 if chart.topbar['security'].value == 'Forex' else 2)
