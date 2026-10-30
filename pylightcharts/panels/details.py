"""Symbol-detail shell panels.

These are the P3 TradingView widgets whose **content needs a data source** the
library does not ship (news / fundamentals / calendar / brokers). They are
**shells**: the UI structure and a clean data contract are here, the host feeds
the rows::

    from pylightcharts import EconomicCalendar, FundamentalData, CompanyProfile

    EconomicCalendar(my_window, rows=[
        {'time': '20:30', 'country': 'US', 'event': 'CPI 月率',
         'importance': '高', 'actual': '0.3%', 'forecast': '0.3%', 'previous': '0.4%'},
    ])

    FundamentalData(my_window, rows=[
        {'name': '市盈率(TTM)', 'value': 28.4, 'yoy': 0.12, 'period': '2024Q4'},
    ])

    profile = CompanyProfile(my_window, {'name': '苹果公司', 'symbol': 'AAPL',
                                         'exchange': 'NASDAQ', 'last': 190.2,
                                         'chg_pct': 0.8},
                             html='<p>...</p>')

The table shells reuse :class:`~pylightcharts.panels.DataGrid`, so they sort,
search and virtual-scroll for free; :class:`CompanyProfile` composes a quote
header and a text block.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

from .base import Panel
from .data_grid import Column, DataGrid
from .quote import QuoteHeader
from .text_block import TextBlock

#: importance -> colour (used by :class:`EconomicCalendar`)
IMPORTANCE_COLORS = {'高': '#ef5350', '中': '#f6c244', '低': '#787b86',
                     'high': '#ef5350', 'medium': '#f6c244', 'low': '#787b86'}

ECONOMIC_CALENDAR_COLUMNS = [
    Column('time', '时间', width=1.0),
    Column('country', '国家', width=0.8),
    Column('event', '事件', width=2.6),
    Column('importance', '重要性', width=0.9, colors=IMPORTANCE_COLORS),
    Column('actual', '今值', width=1.0),
    Column('forecast', '预期', width=1.0),
    Column('previous', '前值', width=1.0),
]

FUNDAMENTAL_COLUMNS = [
    Column('name', '指标', width=1.8),
    Column('value', '数值', type='number', width=1.0),
    Column('yoy', '同比', type='percent', width=1.0),
    Column('period', '报告期', width=1.0),
]

BROKER_RATING_COLUMNS = [
    Column('broker', '机构', width=1.6),
    Column('rating', '评级', width=1.0,
           colors={'买入': '#ef5350', '增持': '#f6c244',
                   '中性': '#787b86', '减持': '#26a69a', '卖出': '#26a69a'}),
    Column('target', '目标价', type='number', width=1.0),
    Column('upside', '上行空间', type='percent', width=1.1),
    Column('date', '日期', width=1.0),
]

BROKER_REVIEW_COLUMNS = [
    Column('broker', '机构', width=1.2),
    Column('review', '评价', width=3.0),
    Column('score', '评分', type='number', decimals=1, width=0.8),
    Column('date', '日期', width=1.0),
]


class EconomicCalendar(DataGrid):
    """Economic Calendar shell (time / country / event / importance / …)."""

    def __init__(self, window, rows: Optional[Iterable[dict]] = None,
                 columns: Optional[Sequence] = None, **options):
        super().__init__(window, columns or ECONOMIC_CALENDAR_COLUMNS, **options)
        if rows is not None:
            self.set_rows(rows)


class FundamentalData(DataGrid):
    """Fundamental Data shell (metric / value / yoy / period)."""

    def __init__(self, window, rows: Optional[Iterable[dict]] = None,
                 columns: Optional[Sequence] = None, **options):
        super().__init__(window, columns or FUNDAMENTAL_COLUMNS, **options)
        if rows is not None:
            self.set_rows(rows)


class BrokerRating(DataGrid):
    """Broker Rating shell (broker / rating / target / upside / date)."""

    def __init__(self, window, rows: Optional[Iterable[dict]] = None,
                 columns: Optional[Sequence] = None, **options):
        super().__init__(window, columns or BROKER_RATING_COLUMNS, **options)
        if rows is not None:
            self.set_rows(rows)


class BrokerReviews(DataGrid):
    """Broker Reviews shell (broker / review / score / date)."""

    def __init__(self, window, rows: Optional[Iterable[dict]] = None,
                 columns: Optional[Sequence] = None, **options):
        super().__init__(window, columns or BROKER_REVIEW_COLUMNS, **options)
        if rows is not None:
            self.set_rows(rows)


class CompanyProfile(Panel):
    """Company Profile shell: a quote header + a text/HTML description block."""

    def __init__(
        self,
        window,
        data: Optional[dict] = None,
        *,
        description: Optional[str] = None,
        html: Optional[str] = None,
        decimals: int = 0,
        color_scheme: str = 'cn',
        container: Optional[str] = None,
    ):
        super().__init__(window)
        self._stack('column', container)
        self.header = QuoteHeader(window, data, decimals=decimals,
                                  color_scheme=color_scheme, show_spark=False,
                                  container=self.id)
        self.description = TextBlock(window, text=description, html=html,
                                     container=self.id)

    def set_data(self, data: dict) -> 'CompanyProfile':
        self.header.set_data(data)
        return self

    def set_description(self, text: Optional[str] = None,
                        html: Optional[str] = None) -> 'CompanyProfile':
        if html is not None:
            self.description.set_html(html)
        elif text is not None:
            self.description.set_text(text)
        return self

    def apply_theme(self, spec: dict) -> None:
        self.header.apply_theme(spec)
        self.description.apply_theme(spec)

    def delete(self) -> None:
        self.header.delete()
        self.description.delete()
        self.run_script(f'{self.id}.remove();')
        panels = getattr(self.win, '_panels', None)
        if panels is not None and self in panels:
            panels.remove(self)
