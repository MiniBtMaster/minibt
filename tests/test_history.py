"""Infinite history: `chart.infinite_history(loader)`.

The official demo prepends a chunk of bars whenever the viewport reaches the left
edge; here the chunk comes from Python (driven by the chart's own
`events.range_change`, which reports `barsInLogicalRange().barsBefore`).
"""
import pandas as pd
import pytest

from pylightcharts import Window
from pylightcharts.abstract import AbstractChart
from pylightcharts.history import InfiniteHistory, to_datetimes

START = pd.Timestamp('2024-06-01')


def bars(days, end=START, step=1):
    """`days` bars ending just before `end`, oldest first."""
    times = [end - pd.Timedelta(days=step * (days - i)) for i in range(days)]
    return pd.DataFrame({
        'time': times,
        'open': [90.0] * days, 'high': [91.0] * days,
        'low': [89.0] * days, 'close': [90.5] * days,
        'volume': [3] * days,
    })


@pytest.fixture()
def chart():
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    chart.set(pd.DataFrame({
        'time': [START + pd.Timedelta(days=i) for i in range(60)],
        'open': [100.0] * 60, 'high': [101.0] * 60,
        'low': [99.0] * 60, 'close': [100.5] * 60,
        'volume': [5] * 60,
    }))
    chart.captured.clear()
    return chart


@pytest.fixture()
def loader():
    calls = []

    def load(count, before=None):
        calls.append((count, before))
        return bars(count, end=before)

    load.calls = calls
    return load


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------

def test_it_starts_from_the_data_already_on_the_chart(chart, loader):
    history = chart.infinite_history(loader, page=10, threshold=5)
    assert history.loaded == 60
    assert history.earliest == START
    assert history.latest == START + pd.Timedelta(days=59)
    assert history.exhausted is False and history.requests == 0
    assert 'InfiniteHistory' in repr(history)


def test_infinite_history_needs_a_loader(chart):
    with pytest.raises(ValueError, match='loader'):
        chart.infinite_history()


def test_the_range_change_is_subscribed(chart, loader):
    history = chart.infinite_history(loader)
    names = [name for name in chart.win.handlers if name.startswith('range_change')]
    assert names, 'the range change event has to feed the history'
    assert history._subscribed is True
    name = chart.events.range_change._name
    assert name in chart.win.handlers
    history.stop()
    assert history._subscribed is False
    # `Window.handlers` is shared by every window, so check *this* entry
    assert name not in chart.win.handlers


def test_the_event_handler_forwards_bars_before(chart, loader):
    history = chart.infinite_history(loader, page=5, threshold=8)
    history._on_range(chart, 3, 100)
    assert history.loaded == 66            # enough bars to reach the threshold


# --------------------------------------------------------------------------
# the trigger
# --------------------------------------------------------------------------

def test_a_view_far_from_the_edge_does_not_load(chart, loader):
    history = chart.infinite_history(loader, page=10, threshold=20)
    assert history.check(50) == 0
    assert history.loaded == 60 and loader.calls == []


def test_a_view_at_the_edge_loads_enough_bars(chart, loader):
    """At least a page, and enough to put `threshold` bars back on the left."""
    history = chart.infinite_history(loader, page=10, threshold=20)
    assert history.check(5) == 16          # 20 - 5 + 1
    assert history.loaded == 76
    assert loader.calls == [(16, START)]
    assert history.requests == 1


def test_scrolling_past_the_first_bar_loads_more(chart, loader):
    """`barsBefore` goes negative once the viewport is left of the data."""
    history = chart.infinite_history(loader, page=10, threshold=20)
    assert history.check(-4) == 25          # 20 - (-4) + 1
    assert history.loaded == 85


def test_it_loads_the_older_bars_in_front(chart, loader):
    history = chart.infinite_history(loader, page=10, threshold=20)
    chart.captured.clear()
    history.check(0)
    script = chr(10).join(chart.captured)
    # the frame that reaches the engine is sorted, so the oldest bar is first
    assert script.index('"open":90.0') < script.index('"open":100.0')
    assert history.data['time'].is_monotonic_increasing


def test_the_loader_can_take_before_as_a_keyword(chart):
    seen = {}

    def load(count, before=None):
        seen['count'], seen['before'] = count, before
        return bars(count, end=before)

    history = chart.infinite_history(load, page=4, threshold=10)
    history.check(0)
    assert seen['count'] == 11 and seen['before'] == START
    assert history.earliest == START - pd.Timedelta(days=11)


def test_a_loader_without_before_is_called_with_the_count(chart):
    calls = []
    history = chart.infinite_history(
        lambda count: calls.append(count) or bars(count), page=4, threshold=10)
    history.check(0)
    assert calls == [11]


# --------------------------------------------------------------------------
# exhaustion and guards
# --------------------------------------------------------------------------

def test_a_loader_with_nothing_left_marks_it_exhausted(chart):
    seen = []
    history = chart.infinite_history(
        lambda count: None, page=10, threshold=10,
        on_exhausted=seen.append)
    assert history.check(0) == 0
    assert history.exhausted is True and seen == [history]
    # and it stops asking
    assert history.check(0) == 0 and history.load() == 0


def test_max_requests_stops_it(chart, loader):
    history = chart.infinite_history(loader, page=5, threshold=10,
                                     max_requests=2)
    history.check(0)
    history.check(0)
    assert history.requests == 2
    assert history.check(0) == 0 and history.exhausted is True


def test_a_load_in_progress_is_not_repeated(chart):
    seen = []

    def load(count):
        seen.append(history.loading)
        # a nested call (the event can fire while the loader runs)
        assert history.load(5) == 0
        return bars(count)

    history = chart.infinite_history(load, page=5, threshold=10)
    history.check(0)
    assert seen == [True]


def test_on_load_reports_the_new_bars(chart, loader):
    seen = []
    history = chart.infinite_history(loader, page=6, threshold=10,
                                     on_load=lambda h, added: seen.append(added))
    history.check(0)
    assert seen == [11] and history.loaded == 71


def test_the_spinner_wraps_the_loader(chart):
    state = []

    def load(count):
        state.append(chart.captured[-1])
        return bars(count)

    history = chart.infinite_history(load, page=5, threshold=10, spinner=True)
    chart.captured.clear()
    history.check(0)
    script = chr(10).join(chart.captured)
    assert 'setSpinner' in state[0]
    assert '"setSpinner", [true]' in state[0]
    assert '"setSpinner", [false]' in script


def test_the_selection_is_only_read_from_a_live_series(chart, loader):
    history = chart.infinite_history(loader, autostart=False)
    assert history.loading is False
    assert history.check(None) == 0          # no range yet
    assert history.load() == 200             # a manual pull still works
    assert history.loaded == 260


# --------------------------------------------------------------------------
# data shapes
# --------------------------------------------------------------------------

def test_overlapping_bars_are_not_duplicated(chart):
    # one bar we already have (its value is tampered with), one that is new
    overlap = bars(2, end=START + pd.Timedelta(days=1))
    overlap.loc[overlap['time'] == START, 'close'] = 111.0

    history = chart.infinite_history(lambda count: overlap, page=2)
    added = history.load(2)
    assert added == 1                                # the known bar is skipped
    assert history.loaded == 61
    assert history.data['time'].is_unique
    # the bars already on the chart win over the incoming copy (`data` is what
    # the engine holds: epoch seconds)
    known = history.data[history.data['time'] == int(START.timestamp())]
    assert known['close'].iloc[0] == 100.5


def test_epoch_seconds_are_not_read_as_nanoseconds(chart):
    """`set` runs `pd.to_datetime`, which would make a bare second number 1970."""
    seconds = int(START.timestamp())
    frame = pd.DataFrame({'time': [seconds - 86400, seconds - 2 * 86400],
                          'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
                          'volume': 1})
    history = chart.infinite_history(lambda count: frame, page=2)
    history.load(2)
    assert history.earliest == START - pd.Timedelta(days=2)
    assert history.data['time'].iloc[0] == pytest.approx(
        (START - pd.Timedelta(days=2)).timestamp())


def test_epoch_milliseconds_and_strings_are_inferred():
    milliseconds = int(START.timestamp() * 1000)
    assert to_datetimes(pd.DataFrame({'time': [milliseconds]}))['time'].iloc[0] \
        == START
    assert to_datetimes(
        pd.DataFrame({'date': ['2024-06-01']}))['time'].iloc[0] == START


def test_a_datetime_index_is_used_as_the_time_axis():
    frame = pd.DataFrame({'close': [1.0, 2.0]},
                         index=pd.DatetimeIndex(['2024-05-01', '2024-05-02']))
    out = to_datetimes(frame)
    assert list(out['time']) == [pd.Timestamp('2024-05-01'),
                                 pd.Timestamp('2024-05-02')]


def test_a_frame_without_a_time_axis_is_rejected():
    with pytest.raises(ValueError, match='time'):
        to_datetimes(pd.DataFrame({'close': [1.0]}))


def test_it_works_on_an_overlay_series(chart):
    """An overlay keeps its own frame; the value column follows its name."""
    overlay = chart.add_symbol('ETHUSDT', bars(30, end=START), kind='candles')
    history = overlay.infinite_history(
        lambda count, before: bars(count, end=before), page=5, threshold=10)
    assert history.loaded == 30
    chart.captured.clear()
    history.check(0)
    assert '"open":90.0' in chr(10).join(chart.captured)
    assert history.loaded == 41


def test_the_chart_set_keeps_the_drawings(chart, loader):
    history = chart.infinite_history(loader, page=5, threshold=10)
    chart.captured.clear()
    history.check(0)
    script = chr(10).join(chart.captured)
    assert 'clearDrawings' not in script
    assert 'repositionOnTime' in script


def test_the_volume_frame_is_resent_for_the_chart(chart, loader):
    history = chart.infinite_history(loader, page=5, threshold=10)
    chart.captured.clear()
    history.check(0)
    assert 'volumeSeries.setData' in chr(10).join(chart.captured)


def test_an_indicator_is_recomputed_after_prepending(chart, loader):
    chart.add_sma(length=5, name='SMA 5')
    history = chart.infinite_history(loader, page=5, threshold=10)
    chart.captured.clear()
    history.check(0)
    script = chr(10).join(chart.captured)
    # the candle frame, the volume frame and the SMA are all re-sent
    assert script.count('setData') >= 3
    assert '"value":100.5' in script      # the SMA recomputed over older bars


# --------------------------------------------------------------------------
# indicators follow the history
# --------------------------------------------------------------------------

def test_a_main_pane_indicator_extends_with_the_history(chart, loader):
    """`chart.set(...)` recomputes every indicator over the older bars too."""
    sma = chart.add_sma(length=5, name='SMA 5')
    history = chart.infinite_history(loader, page=30, threshold=20)
    chart.captured.clear()
    added = history.check(0)

    assert added == 30
    # the indicator covers the prepended bars as well ...
    assert len(sma.data) == 60 + added
    assert sma.data['time'].min() == int(
        (START - pd.Timedelta(days=added)).timestamp())
    # ... and it is recomputed over them, so the bar where the history joins
    # now has a full (5 bar) window instead of starting the series
    assert sma.data['value'].notna().all()
    window = chart.candle_data[
        chart.candle_data['time'] <= int(START.timestamp())].tail(5)
    joined = sma.data[sma.data['time'] == int(START.timestamp())]['value'].iloc[0]
    assert joined == pytest.approx(window['close'].mean())
    # the engine is told about the older indicator points
    script = chr(10).join(chart.captured)
    assert str(int(sma.data['time'].min())) in script
    # candle frame + volume + the indicator
    assert script.count('setData') >= 3


def test_a_sub_pane_indicator_extends_too(chart, loader):
    rsi = chart.add_rsi(length=7, pane_index=1)
    history = chart.infinite_history(loader, page=30, threshold=20)

    chart.captured.clear()
    added = history.check(0)

    assert added == 30
    assert len(rsi.data) == 60 + added
    assert rsi._pane_index == 1                       # still in its own pane
    assert rsi.data['time'].min() == int(
        (START - pd.Timedelta(days=added)).timestamp())
    assert str(int(rsi.data['time'].min())) in chr(10).join(chart.captured)


def test_several_indicators_all_follow(chart, loader):
    sma = chart.add_sma(length=5, name='SMA 5')
    rsi = chart.add_rsi(length=7, pane_index=1)
    macd, signal, histogram = chart.add_macd(pane_index=2)
    history = chart.infinite_history(loader, page=30, threshold=20)

    history.check(0)

    oldest = int((START - pd.Timedelta(days=30)).timestamp())
    for indicator in (sma, rsi, macd, signal, histogram):
        assert indicator.data['time'].min() == oldest
