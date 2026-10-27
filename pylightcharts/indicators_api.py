"""Indicator plumbing: keeps computed series in sync with the chart data.

The `add_*` helpers live here as a mixin so `abstract.py` stays focused on the
chart itself. `compute(frame) -> pd.Series` is the contract; see
:mod:`pylightcharts.indicators` for the maths.
"""
from __future__ import annotations

import sys
from typing import Callable, List, Optional, Union

import pandas as pd

from . import indicators


class _IndicatorBinding:
    """Keeps a computed series in sync with the chart's source data.

    On a full refresh the whole series is re-sent; on an incremental refresh only
    the last point is pushed, computed from a warm-up window so recursive
    indicators (EMA/RSI/ATR/MACD) stay numerically identical to a full run.
    """

    def __init__(self, series: 'BridgeSeries', name: str, compute: Callable,
                 extra: Optional[Callable] = None, full_only: bool = False,
                 tail_window: int = 1000):
        self.series = series
        self.name = name
        self.compute = compute          # frame -> time-indexed pd.Series
        self.extra = extra              # frame -> {column: values}
        self.full_only = full_only
        self.tail_window = tail_window

    def _values(self, frame) -> pd.Series:
        values = self.compute(frame).copy()
        values.index = frame['time'].to_numpy()
        return values

    def refresh(self, frame, full: bool):
        incremental = (not full) and (not self.full_only) and len(frame) > self.tail_window
        if not incremental:
            values = self._values(frame)
            data = pd.DataFrame({'time': values.index, self.name: values.to_numpy()})
            if self.extra is not None:
                for column, column_values in self.extra(frame).items():
                    data[column] = list(column_values)
            self.series.set(data, format_cols=False)
            return

        source = frame.iloc[-self.tail_window:]
        values = self._values(source)
        point: dict = {'time': source['time'].to_numpy()[-1], 'value': values.to_numpy()[-1]}
        if self.extra is not None:
            for column, column_values in self.extra(source).items():
                point[column] = list(column_values)[-1]
        self.series.update_raw(point)


class IndicatorMixin:
    """Adds `add_sma` / `add_rsi` / ... and the automatic refresh plumbing."""

    #: populated by AbstractChart.__init__
    _indicator_bindings: List['_IndicatorBinding']

    def _indicator_source(self, source: str = 'close') -> pd.Series:
        data = getattr(self, 'candle_data', None)
        if data is None or data.empty:
            raise ValueError('Set the chart data before adding indicators.')
        if source not in data.columns:
            raise NameError(f'No column named "{source}".')
        values = data[source].astype(float)
        values.index = data['time'].values
        return values

    def _indicator_frame(self) -> pd.DataFrame:
        data = self.candle_data.copy()
        data.index = data['time'].values
        return data

    def add_indicator(self, values: pd.Series, name: str, kind: str = 'Line',
                      pane_index: Optional[Union[int, str]] = None,
                      extra: Optional[dict] = None, legend_toggle: bool = True,
                      **options) -> BridgeSeries:
        """Add a *static* computed series from a time-indexed Series.

        `extra` adds columns to the data (e.g. per-point `color` for histograms).
        The series is not recomputed when the chart data changes; use
        :meth:`add_computed_series` for that.
        """
        frame = pd.DataFrame({'time': values.index, name: values.values})
        if extra:
            for column, column_values in extra.items():
                frame[column] = list(column_values)
        series = self.add_series(kind, name=name, pane_index=self._resolve_pane(pane_index),
                                 legend_toggle=legend_toggle, **options)
        # time is already epoch seconds (taken from candle_data), skip reformatting
        series.set(frame, format_cols=False)
        return series

    def add_computed_series(self, compute: Callable, name: str, kind: str = 'Line',
                            pane_index: Optional[Union[int, str]] = None,
                            extra: Optional[Callable] = None, full_only: bool = False,
                            tail_window: int = 1000, legend_toggle: bool = True,
                            **options) -> BridgeSeries:
        """Add a series that is recomputed whenever the chart data changes.

        `compute(frame) -> pd.Series` and optionally `extra(frame) -> {column: values}`.
        On incremental updates only the last point is pushed, recomputed from a
        warm-up window of `tail_window` bars (so recursive indicators stay exact).
        """
        series = self.add_series(kind, name=name, pane_index=self._resolve_pane(pane_index),
                                 legend_toggle=legend_toggle, **options)
        frame = getattr(self, 'candle_data', None)
        if frame is None or frame.empty:
            raise ValueError('Set the chart data before adding indicators.')
        binding = _IndicatorBinding(series, name, compute, extra=extra,
                                    full_only=full_only, tail_window=tail_window)
        binding.refresh(frame, full=True)       # raises on an unknown source column
        self._indicator_bindings.append(binding)
        return series

    def _refresh_indicators(self, full: bool = True):
        """Recompute every registered indicator from the current chart data."""
        frame = getattr(self, 'candle_data', None)
        if frame is None or frame.empty or not self._indicator_bindings:
            return
        for binding in self._indicator_bindings:
            try:
                binding.refresh(frame, full)
            except Exception as error:      # a broken indicator must not kill the chart
                print(f'[pylightcharts] indicator refresh failed: {error}', file=sys.stderr)

    @staticmethod
    def _compute(source: str, func: Callable) -> Callable:
        """Wrap `func(float_series) -> Series` into a `frame -> Series` compute."""
        def compute(frame):
            if source not in frame.columns:
                raise NameError(f'No column named "{source}".')
            return func(frame[source].astype(float))
        return compute

    @staticmethod
    def _compute_frame(func: Callable) -> Callable:
        """Wrap `func(frame) -> Series` into a compute (identity)."""
        def compute(frame):
            return func(frame)
        return compute

    def add_sma(self, source: str = 'close', length: int = 20, name: Optional[str] = None,
                pane_index: Optional[Union[int, str]] = None, **options) -> BridgeSeries:
        return self.add_computed_series(
            self._compute(source, lambda series: indicators.sma(series, length)),
            name or f'SMA {length}', pane_index=pane_index, **options)

    def add_ema(self, source: str = 'close', length: int = 20, name: Optional[str] = None,
                pane_index: Optional[Union[int, str]] = None, **options) -> BridgeSeries:
        return self.add_computed_series(
            self._compute(source, lambda series: indicators.ema(series, length)),
            name or f'EMA {length}', pane_index=pane_index, **options)

    def add_wma(self, source: str = 'close', length: int = 20, name: Optional[str] = None,
                pane_index: Optional[Union[int, str]] = None, **options) -> BridgeSeries:
        return self.add_computed_series(
            self._compute(source, lambda series: indicators.wma(series, length)),
            name or f'WMA {length}', pane_index=pane_index, **options)

    def add_bollinger(self, source: str = 'close', length: int = 20, std: float = 2,
                      pane_index: Optional[Union[int, str]] = None, line_width: int = 1,
                      upper_color: str = 'rgba(41, 98, 255, 0.6)',
                      middle_color: str = 'rgba(255, 152, 0, 0.9)',
                      lower_color: str = 'rgba(41, 98, 255, 0.6)',
                      legend_toggle: bool = True) -> tuple:
        """Bollinger bands: returns ``(upper, middle, lower)``."""
        def side(key, color):
            compute = self._compute(source, lambda series: indicators.bollinger(series, length, std)[key])
            return self.add_computed_series(compute, f'BB {key} {length}', pane_index=pane_index,
                                            color=color, line_width=line_width,
                                            legend_toggle=legend_toggle)
        return (side('upper', upper_color), side('middle', middle_color), side('lower', lower_color))

    def add_donchian(self, length: int = 20, pane_index: Optional[Union[int, str]] = None,
                     line_width: int = 1, upper_color: str = 'rgba(0, 150, 136, 0.7)',
                     middle_color: str = 'rgba(255, 255, 255, 0.4)',
                     lower_color: str = 'rgba(239, 83, 80, 0.7)',
                     legend_toggle: bool = True) -> tuple:
        """Donchian channel: returns ``(upper, middle, lower)``."""
        def side(key, color):
            compute = self._compute_frame(lambda frame: indicators.donchian(frame, length)[key])
            return self.add_computed_series(compute, f'DC {key} {length}', pane_index=pane_index,
                                            color=color, line_width=line_width,
                                            legend_toggle=legend_toggle)
        return (side('upper', upper_color), side('middle', middle_color), side('lower', lower_color))

    def add_vwap(self, pane_index: Optional[Union[int, str]] = None,
                 color: str = '#00BCD4',
                 legend_toggle: bool = True) -> BridgeSeries:
        # VWAP accumulates from the first bar, so it cannot be tail-recomputed
        return self.add_computed_series(self._compute_frame(indicators.vwap), 'VWAP',
                                        pane_index=pane_index, color=color, full_only=True,
                                        legend_toggle=legend_toggle)

    def add_rsi(self, length: int = 14, source: str = 'close',
                pane_index: Optional[Union[int, str]] = 'new', color: str = '#7E57C2',
                overbought: Optional[float] = 70, oversold: Optional[float] = 30,
                legend_toggle: bool = True) -> BridgeSeries:
        """RSI in its own pane, with optional overbought/oversold guide lines."""
        series = self.add_computed_series(
            self._compute(source, lambda values: indicators.rsi(values, length)),
            f'RSI {length}', pane_index=pane_index, color=color,
            legend_toggle=legend_toggle)
        if overbought is not None:
            series.horizontal_line(overbought, color='rgba(255, 255, 255, 0.2)', width=1)
        if oversold is not None:
            series.horizontal_line(oversold, color='rgba(255, 255, 255, 0.2)', width=1)
        return series

    def add_macd(self, source: str = 'close', fast: int = 12, slow: int = 26, signal: int = 9,
                 pane_index: Optional[Union[int, str]] = 'new', macd_color: str = '#2962FF',
                 signal_color: str = '#FF6D00', up_color: str = 'rgba(0, 150, 136, 0.7)',
                 down_color: str = 'rgba(239, 83, 80, 0.7)', histogram: bool = True,
                 legend_toggle: bool = True) -> tuple:
        """MACD in its own pane: returns ``(macd, signal, histogram_or_None)``."""
        def result(frame):
            return indicators.macd(frame[source].astype(float), fast, slow, signal)

        def part(key):
            return self._compute_frame(lambda frame: result(frame)[key])

        pane = self._resolve_pane(pane_index)
        macd_series = self.add_computed_series(
            part('macd'), f'MACD {fast},{slow}', pane_index=pane,
            color=macd_color, legend_toggle=legend_toggle)
        signal_series = self.add_computed_series(
            part('signal'), f'MACD signal {signal}', pane_index=pane,
            color=signal_color, legend_toggle=legend_toggle)
        histogram_series = None
        if histogram:
            def colors(frame):
                values = result(frame)['histogram'].fillna(0)
                return {'color': [up_color if value >= 0 else down_color for value in values]}

            histogram_series = self.add_computed_series(
                part('histogram'), 'MACD histogram', kind='Histogram',
                pane_index=pane, extra=colors, legend_toggle=legend_toggle)
        return macd_series, signal_series, histogram_series

    def add_stochastic(self, k: int = 14, d: int = 3, smooth: int = 3,
                       pane_index: Optional[Union[int, str]] = 'new',
                       k_color: str = '#2962FF', d_color: str = '#FF6D00',
                       legend_toggle: bool = True) -> tuple:
        """Stochastic oscillator in its own pane: returns ``(%K, %D)``."""
        def part(key, color):
            compute = self._compute_frame(lambda frame: indicators.stochastic(frame, k, d, smooth)[key])
            return self.add_computed_series(compute, '%' + key.upper() + f' {k if key == "k" else d}',
                                            pane_index=pane_index, color=color,
                                            legend_toggle=legend_toggle)
        return (part('k', k_color), part('d', d_color))

    def add_atr(self, length: int = 14, pane_index: Optional[Union[int, str]] = 'new',
                color: str = '#FF6D00',
                legend_toggle: bool = True) -> BridgeSeries:
        return self.add_computed_series(
            self._compute_frame(lambda frame: indicators.atr(frame, length)),
            f'ATR {length}', pane_index=pane_index, color=color,
            legend_toggle=legend_toggle)

    def add_obv(self, pane_index: Optional[Union[int, str]] = 'new',
                color: str = '#2962FF',
                legend_toggle: bool = True) -> BridgeSeries:
        """On Balance Volume (needs a ``volume`` column)."""
        def compute(frame):
            if 'volume' not in frame.columns:
                raise NameError('No column named "volume".')
            return indicators.obv(frame['close'].astype(float), frame['volume'])
        return self.add_computed_series(compute, 'OBV', pane_index=pane_index, color=color,
                                        legend_toggle=legend_toggle)

    def add_roc(self, source: str = 'close', length: int = 12,
                pane_index: Optional[Union[int, str]] = 'new',
                color: str = '#2962FF',
                legend_toggle: bool = True) -> BridgeSeries:
        """Rate of Change in percent."""
        return self.add_computed_series(
            self._compute(source, lambda series: indicators.roc(series, length)),
            f'ROC {length}', pane_index=pane_index, color=color,
            legend_toggle=legend_toggle)

    def add_williams_r(self, length: int = 14, pane_index: Optional[Union[int, str]] = 'new',
                       color: str = '#7E57C2',
                       legend_toggle: bool = True) -> BridgeSeries:
        """Williams %R."""
        return self.add_computed_series(
            self._compute_frame(lambda frame: indicators.williams_r(frame, length)),
            f'%R {length}', pane_index=pane_index, color=color,
            legend_toggle=legend_toggle)

    def add_cci(self, length: int = 20, pane_index: Optional[Union[int, str]] = 'new',
                color: str = '#2962FF',
                legend_toggle: bool = True) -> BridgeSeries:
        """Commodity Channel Index."""
        return self.add_computed_series(
            self._compute_frame(lambda frame: indicators.cci(frame, length)),
            f'CCI {length}', pane_index=pane_index, color=color,
            legend_toggle=legend_toggle)

    def add_mfi(self, length: int = 14, pane_index: Optional[Union[int, str]] = 'new',
                color: str = '#26A69A',
                legend_toggle: bool = True) -> BridgeSeries:
        """Money Flow Index (needs a ``volume`` column)."""
        return self.add_computed_series(
            self._compute_frame(lambda frame: indicators.mfi(frame, length)),
            f'MFI {length}', pane_index=pane_index, color=color,
            legend_toggle=legend_toggle)

    def add_keltner(self, length: int = 20, multiplier: float = 2.0, atr_length: int = 10,
                    pane_index: Optional[Union[int, str]] = None, line_width: int = 1,
                    upper_color: str = 'rgba(0, 150, 136, 0.7)',
                    middle_color: str = 'rgba(255, 255, 255, 0.4)',
                    lower_color: str = 'rgba(239, 83, 80, 0.7)',
                    legend_toggle: bool = True) -> tuple:
        """Keltner channel: returns ``(upper, middle, lower)``."""
        def side(key, color):
            compute = self._compute_frame(
                lambda frame: indicators.keltner(frame, length, multiplier, atr_length)[key])
            return self.add_computed_series(compute, f'KC {key} {length}', pane_index=pane_index,
                                            color=color, line_width=line_width,
                                            legend_toggle=legend_toggle)
        return (side('upper', upper_color), side('middle', middle_color), side('lower', lower_color))

    def add_adx(self, length: int = 14, pane_index: Optional[Union[int, str]] = 'new',
                adx_color: str = '#2962FF', plus_color: str = '#26A69A',
                minus_color: str = '#EF5350',
                legend_toggle: bool = True) -> tuple:
        """ADX in its own pane: returns ``(adx, plus_di, minus_di)``."""
        def part(key, color, label):
            compute = self._compute_frame(lambda frame: indicators.adx(frame, length)[key])
            return self.add_computed_series(
                compute, label, pane_index=pane_index, color=color,
                legend_toggle=legend_toggle)
        return (part('adx', adx_color, f'ADX {length}'),
                part('plus_di', plus_color, f'+DI {length}'),
                part('minus_di', minus_color, f'-DI {length}'))
