"""Quote panels: Symbol Info, Symbol Overview and Mini Chart."""
from __future__ import annotations

from typing import Optional, Sequence

from .base import Panel
from .sparkline import Sparkline

_CN = ('#ef5350', '#26a69a')      # (up, down)
_TV = ('#26a69a', '#ef5350')


def _scheme_colors(color_scheme: str) -> tuple:
    return _CN if color_scheme == 'cn' else _TV


class QuoteHeader(Panel):
    """A symbol quote header.

    Shows name / code / last / change, a row of OHLC / volume / open-interest
    fields and an optional inline sparkline. ``data`` is a dict with any of
    ``symbol, name, exchange, last, chg, chg_pct, open, high, low, pre_close,
    volume, open_interest, spark``.
    """

    def __init__(
        self,
        window,
        data: Optional[dict] = None,
        *,
        decimals: int = 0,
        compact: bool = False,
        color_scheme: str = 'cn',
        fields: Optional[Sequence[str]] = None,
        show_spark: bool = False,
        spark_width: Optional[int] = None,
        spark_height: Optional[int] = None,
        theme: Optional[dict] = None,
        container: Optional[str] = None,
    ):
        super().__init__(window)
        options: dict = {
            'decimals': decimals,
            'compact': compact,
            'colorScheme': color_scheme,
            'showSpark': show_spark,
        }
        if data:
            options.update(data)
        if fields is not None:
            options['fields'] = list(fields)
        if spark_width is not None:
            options['sparkWidth'] = spark_width
        if spark_height is not None:
            options['sparkHeight'] = spark_height
        if theme:
            options['theme'] = theme
        self._create('QuoteHeader', options, container)

    def set_data(self, data: dict) -> 'QuoteHeader':
        self._set('setData', data)
        return self

    def set_options(self, **options) -> 'QuoteHeader':
        self._set('setOptions', options)
        return self

    def apply_theme(self, spec: dict) -> None:
        theme = {
            # paint the header itself so it is not left transparent over a card
            'background': spec.get('background'),
            'text': spec.get('text'),
            'muted': spec.get('crosshair'),
            'border': spec.get('border_color'),
        }
        theme = {key: value for key, value in theme.items() if value}
        if theme:
            self._set('setOptions', {'theme': theme})


class SymbolInfo(QuoteHeader):
    """Quote header without the chart (TradingView Symbol Info)."""

    def __init__(self, window, data=None, **options):
        options.setdefault('show_spark', False)
        super().__init__(window, data, **options)


class SymbolOverview(QuoteHeader):
    """Quote header with a larger sparkline (TradingView Symbol Overview)."""

    def __init__(self, window, data=None, **options):
        options.setdefault('show_spark', True)
        options.setdefault('spark_width', 240)
        options.setdefault('spark_height', 64)
        super().__init__(window, data, **options)


class MiniChart(Sparkline):
    """A standalone mini line chart (TradingView Mini Chart)."""

    def __init__(
        self,
        window,
        values: Optional[Sequence[float]] = None,
        *,
        width: int = 220,
        height: int = 64,
        color_scheme: str = 'cn',
        **options,
    ):
        up, down = _scheme_colors(color_scheme)
        options.setdefault('up_color', up)
        options.setdefault('down_color', down)
        super().__init__(window, width=width, height=height, **options)
        if values is not None:
            self.set_data(values)
