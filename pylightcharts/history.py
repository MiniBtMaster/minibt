"""Infinite history - load older bars when the chart reaches its left edge.

The official
`infinite history <https://tradingview.github.io/lightweight-charts/tutorials/demos/infinite-history>`_
demo subscribes to the visible logical range and, once fewer than N bars are left
of the viewport, prepends another chunk with ``series.setData([...older, ...])``
(the engine keeps the viewport where it was).

This is the same idea with the data coming from Python. The chart's own
``events.range_change`` already reports ``barsInLogicalRange().barsBefore`` (and
is debounced), so:

.. code-block:: python

    def load(count, before=None):          # `before` is the earliest loaded bar
        return pd.read_parquet('bars.parquet').loc[:before].tail(count)

    history = chart.infinite_history(load, page=300, threshold=80)
    history.loaded          # bars currently on the chart
    history.earliest        # pd.Timestamp of the oldest bar
    history.exhausted       # the loader ran out
    history.load()          # pull a chunk by hand
    history.stop()          # stop following the range

A loader is called as ``loader(count)`` or ``loader(count, before)`` (keyword
``before=`` works too) and returns anything :meth:`SeriesCommon.set` accepts - a
DataFrame with a time column plus OHLC / value (and volume for the main chart), a
Series with a time index, or ``None`` / an empty frame to say "that was all".

Prepending goes through ``chart.set(..., keep_drawings=True)`` for the main
series, so the volume series, every computed indicator and the toolbox drawings
stay in sync; for an overlay series it re-sends that series only.
"""
from __future__ import annotations

import inspect
from typing import Callable, Optional, Union

import pandas as pd

from .util import infer_time_unit

#: column names a loader may use for its time axis
TIME_COLUMNS = ('time', 'date', 'datetime', 'timestamp')


def as_frame(data) -> pd.DataFrame:
    """Coerce `data` (DataFrame / Series / records) into a DataFrame."""
    if isinstance(data, pd.Series):
        data = data.to_frame()
    if not isinstance(data, pd.DataFrame):
        data = pd.DataFrame(data)
    return data


def time_column(frame: pd.DataFrame) -> str:
    """The frame's time column, whatever it is called (or its datetime index)."""
    for column in frame.columns:
        if str(column).lower() in TIME_COLUMNS:
            return column
    if isinstance(frame.index, pd.DatetimeIndex):
        return '__index__'
    raise ValueError(
        f'the frame needs a {" / ".join(TIME_COLUMNS)} column, '
        f'got {list(frame.columns)}')


def to_datetimes(frame: pd.DataFrame) -> pd.DataFrame:
    """Return `frame` with its time column as pandas Timestamps.

    `SeriesCommon.set` runs ``pd.to_datetime`` on the column, which reads a bare
    epoch *second* number as nanoseconds (i.e. 1970), so the unit is inferred
    here first - the same rule the marker helpers use.
    """
    frame = frame.copy()
    column = time_column(frame)
    if column == '__index__':
        frame = frame.reset_index()
        frame = frame.rename(columns={frame.columns[0]: 'time'})
    elif column != 'time':
        frame = frame.rename(columns={column: 'time'})
    values = frame['time']
    unit = infer_time_unit(values) if pd.api.types.is_numeric_dtype(values) else None
    frame['time'] = pd.to_datetime(values, unit=unit)
    return frame


class InfiniteHistory:
    """Feed a series' history lazily, in ``page`` sized chunks.

    See the module docstring for the loader contract; ``threshold`` is how close
    to the left edge (in bars) the viewport has to get before another chunk is
    asked for.
    """

    def __init__(self, series, loader: Callable, page: int = 200,
                 threshold: int = 50, spinner: bool = False,
                 on_load: Optional[Callable] = None,
                 on_exhausted: Optional[Callable] = None,
                 max_requests: Optional[int] = None,
                 autostart: bool = True):
        self._series = series
        self._chart = getattr(series, '_chart', None) or series
        self.loader = loader
        self.page = int(page)
        self.threshold = int(threshold)
        self.spinner = bool(spinner)
        self.on_load = on_load
        self.on_exhausted = on_exhausted
        self.max_requests = max_requests
        #: how many chunks the loader was asked for
        self.requests = 0
        #: True once the loader returned nothing (or `max_requests` was reached)
        self.exhausted = False
        self._loading = False
        self._subscribed = False
        self._frame = self._series_frame()
        self._earliest, self._latest = self._bounds(self._frame)
        if autostart:
            self.start()

    def __repr__(self) -> str:
        return (f'<InfiniteHistory loaded={self.loaded} page={self.page} '
                f'threshold={self.threshold} exhausted={self.exhausted}>')

    # ------------------------------------------------------------- state
    @property
    def loaded(self) -> int:
        """How many bars the series currently holds."""
        return 0 if self._frame is None else len(self._frame)

    @property
    def loading(self) -> bool:
        """True while a loader call is in flight."""
        return self._loading

    @property
    def earliest(self) -> Optional[pd.Timestamp]:
        """Time of the oldest loaded bar (what a loader continues from)."""
        return self._earliest

    @property
    def latest(self) -> Optional[pd.Timestamp]:
        """Time of the newest loaded bar."""
        return self._latest

    @property
    def data(self) -> pd.DataFrame:
        """The loaded bars, as the engine holds them (epoch seconds)."""
        return self._frame

    # ------------------------------------------------------ subscription
    def start(self) -> 'InfiniteHistory':
        """Follow the visible range (the constructor does this by default)."""
        if not self._subscribed:
            self._chart.events.range_change += self._on_range
            self._subscribed = True
        return self

    def stop(self) -> 'InfiniteHistory':
        """Stop following the visible range (``load()`` still works)."""
        if self._subscribed:
            self._chart.events.range_change.unsubscribe()
            self._subscribed = False
        return self

    def _on_range(self, chart, bars_before, bars_after):
        """`barsBefore` from `barsInLogicalRange` - the official demo's trigger."""
        self.check(bars_before)

    # ----------------------------------------------------------- loading
    def check(self, bars_before: Optional[float] = None) -> int:
        """Load a chunk when fewer than `threshold` bars are left of the view.

        This is what the range change calls; it is public so a caller can drive
        it from somewhere else (e.g. its own scroll handling).
        """
        if bars_before is None or self.exhausted or self._loading:
            return 0
        if self._frame is None or self._frame.empty:
            return 0
        if bars_before > self.threshold:
            return 0
        # like the demo: load at least a page, more when the view is scrolled
        # past the first bar (`bars_before` is negative there)
        count = max(self.page, int(self.threshold - bars_before) + 1)
        return self.load(count)

    def load(self, count: Optional[int] = None, force: bool = False) -> int:
        """Ask the loader for `count` (default `page`) older bars.

        :return: how many *new* bars were added (0 when the loader had nothing,
            everything overlapped, or a load is already running).
        """
        if self._loading or (self.exhausted and not force):
            return 0
        if self.max_requests is not None and self.requests >= self.max_requests:
            self.exhausted = True
            return 0
        count = int(count or self.page)
        self._loading = True
        if self.spinner:
            self._chart.spinner(True)
        try:
            frame = self._call_loader(count)
        finally:
            self._loading = False
            if self.spinner:
                self._chart.spinner(False)
        if frame is None or len(frame) == 0:
            self.exhausted = True
            if self.on_exhausted is not None:
                self.on_exhausted(self)
            return 0
        added = self.prepend(frame)
        self.requests += 1
        if added and self.on_load is not None:
            self.on_load(self, added)
        return added

    def _call_loader(self, count: int):
        """Call the loader with `count` and (when it accepts it) `before`."""
        loader = self.loader
        try:
            parameters = inspect.signature(loader).parameters
        except (TypeError, ValueError):          # builtins / partials
            parameters = {}
        names = list(parameters)
        keyword = 'before' in parameters and parameters['before'].kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY)
        if keyword:
            return loader(count, before=self.earliest)
        if len(names) >= 2:
            return loader(count, self.earliest)
        return loader(count)

    def prepend(self, frame) -> int:
        """Put older bars in front of the loaded data and re-send the series.

        Bars that are already loaded win over the incoming ones (a loader may
        overlap what is on the chart), and everything is sorted by time.
        """
        incoming = to_datetimes(as_frame(frame))
        current = pd.DataFrame()
        if self._frame is not None and not self._frame.empty:
            current = to_datetimes(self._frame)
        known = set(current['time']) if not current.empty else set()
        fresh = incoming[~incoming['time'].isin(known)]
        if fresh.empty:
            return 0
        combined = pd.concat([incoming, current], ignore_index=True)
        combined = combined.drop_duplicates(subset='time', keep='last')
        combined = combined.sort_values('time').reset_index(drop=True)
        self._apply(combined)
        return len(fresh)

    # ------------------------------------------------------------ engine
    def _series_frame(self) -> pd.DataFrame:
        """What the engine holds: `candle_data` for the chart, `data` otherwise."""
        frame = getattr(self._series, 'candle_data', None)
        if frame is None:
            frame = getattr(self._series, 'data', None)
        return pd.DataFrame() if frame is None else frame

    @staticmethod
    def _timestamp(value):
        if isinstance(value, pd.Timestamp):
            return value
        return pd.to_datetime(value, unit='s')

    @staticmethod
    def _bounds(frame: pd.DataFrame):
        """(earliest, latest) - by value, so a frame that arrived unsorted is fine."""
        if frame is None or frame.empty or 'time' not in frame.columns:
            return None, None
        times = frame['time']
        if pd.api.types.is_numeric_dtype(times):
            return (InfiniteHistory._timestamp(times.min()),
                    InfiniteHistory._timestamp(times.max()))
        return pd.Timestamp(times.min()), pd.Timestamp(times.max())

    def _apply(self, frame: pd.DataFrame) -> None:
        """Hand the combined frame to the series and re-read what it kept."""
        series = self._series
        target = frame
        name = getattr(series, 'name', '')
        # a single-value series matches its column by name (`set` renames the
        # column to `value` once it is in), so undo that before re-sending
        if name and 'value' in frame.columns and name not in frame.columns:
            target = frame.rename(columns={'value': name})
        if hasattr(series, 'candle_data'):
            # the chart's own series: `set` re-sends the volume, refreshes the
            # computed indicators and keeps the toolbox drawings
            series.set(target, keep_drawings=True)
        else:
            series.set(target)
        self._frame = self._series_frame()
        self._earliest, self._latest = self._bounds(self._frame)
