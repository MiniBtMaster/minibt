"""Guards against a pandas trap that silently corrupts indicator maths.

`Series.where` / `.clip` / `.mask` route their condition through
``pandas.core.common.apply_if_callable``, which *invokes* the condition when it
looks callable::

    # pandas/core/generic.py, NDFrame._where
    cond = common.apply_if_callable(cond, self)

In pristine pandas a ``Series`` is not callable, so the boolean mask is used
as-is. Some libraries make every Series callable — minibt assigns
``pd.Series.__call__ = _call_`` so that ``df(...)`` builds a ``KLine``/``IndFrame``
— and then the mask *is* invoked. The replacement object is mis-aligned with the
frame being computed, so ``.clip()`` quietly returns wrong numbers (no exception,
no warning).

Measured on pandas 2.3.3 / numpy 2.2.6: with ``pd.Series.__call__`` returning a
Series subclass, ``(diff).clip(lower=0)`` yields a minimum of -1.65 instead of 0.
That silently corrupted ``rsi``, ``adx`` and ``mfi`` whenever minibt was imported
anywhere in the process (see the note in ``pylightcharts/indicators.py``).

The indicator maths therefore stays numpy-first, and these tests keep it that way.

minibt guards its own patch too (it refuses the positional call pandas makes, and
keeps `apply_if_callable` from ever invoking a frame); `scripts/patch_minibt.py`
applies and verifies that guard. This module deliberately simulates the trap
instead, so it holds even without minibt installed and whatever the host does.
"""
import contextlib
import pathlib

import numpy as np
import pandas as pd
import pytest

from pylightcharts import indicators as ind

ROWS = 240


@pytest.fixture(scope='module')
def frame():
    rng = np.random.default_rng(5)
    close = 100 + np.cumsum(rng.standard_normal(ROWS))
    return pd.DataFrame({
        'open': close, 'high': close + 1.2, 'low': close - 1.2, 'close': close,
        'volume': rng.integers(1_000, 9_000, ROWS),
    })


class _FrameLike(pd.Series):
    """Stands in for minibt's ``IndSeries``: a Series subclass."""

    @property
    def _constructor(self):
        return _FrameLike


def _call_like_minibt(self, *args, **kwargs):
    """What ``pd.Series.__call__ = minibt._call_`` effectively does."""
    return _FrameLike(self.to_numpy())


@contextlib.contextmanager
def _patched(callable_value):
    """Install (or remove, with ``None``) ``__call__`` on Series/DataFrame."""
    missing = object()
    targets = (pd.Series, pd.DataFrame)
    previous = [target.__dict__.get('__call__', missing) for target in targets]
    try:
        for target in targets:
            if callable_value is None:
                try:
                    del target.__call__
                except AttributeError:
                    pass
            else:
                target.__call__ = callable_value
        yield
    finally:
        # `type.__dict__` is a read-only mappingproxy, so restore with delattr
        for target, original in zip(targets, previous):
            if original is missing:
                try:
                    del target.__call__
                except AttributeError:
                    pass
            else:
                target.__call__ = original


def _pristine_apply_if_callable(maybe_callable, obj, **kwargs):
    """pandas' own implementation (``pandas/core/common.py``).

    Restored here so the trap is observable even in a process where the host
    already guards it (minibt wraps this function); these tests must depend on
    pandas alone.
    """
    if callable(maybe_callable):
        return maybe_callable(obj, **kwargs)
    return maybe_callable


@contextlib.contextmanager
def callable_frames():
    """Make every Series/DataFrame callable, as minibt does on import."""
    from pandas.core import common as pd_common

    original = pd_common.apply_if_callable
    try:
        pd_common.apply_if_callable = _pristine_apply_if_callable
        with _patched(_call_like_minibt):
            yield
    finally:
        pd_common.apply_if_callable = original


@contextlib.contextmanager
def pristine_frames():
    """Undo any ``__call__`` patch, e.g. minibt's, for the duration of a block."""
    with _patched(None):
        yield


def _snapshot(frame):
    """Every indicator, so a single trap cannot hide in one of them."""
    adx = ind.adx(frame, 14)
    return {
        'sma': ind.sma(frame['close'], 20),
        'ema': ind.ema(frame['close'], 20),
        'wma': ind.wma(frame['close'], 20),
        'rsi': ind.rsi(frame['close'], 14),
        'macd': ind.macd(frame['close'])['histogram'],
        'bollinger': ind.bollinger(frame['close'])['upper'],
        'stochastic': ind.stochastic(frame)['k'],
        'atr': ind.atr(frame, 14),
        'vwap': ind.vwap(frame),
        'donchian': ind.donchian(frame)['lower'],
        'obv': ind.obv(frame['close'], frame['volume']),
        'cci': ind.cci(frame, 20),
        'williams_r': ind.williams_r(frame, 14),
        'adx': adx['adx'],
        'plus_di': adx['plus_di'],
        'minus_di': adx['minus_di'],
        'keltner': ind.keltner(frame)['upper'],
        'roc': ind.roc(frame['close'], 12),
        'mfi': ind.mfi(frame, 14),
    }


def test_the_pandas_trap_is_still_there(frame):
    """Documents the trap itself, so the numpy-first rule keeps its reason.

    If this ever stops reproducing, pandas has fixed the behaviour and the
    comment in ``pylightcharts/indicators.py`` can be revisited.
    """
    with pristine_frames():
        assert not callable(frame['close']), 'a plain Series must not be callable'
        delta = frame['close'].diff().iloc[1:]
        assert np.isclose(delta.clip(lower=0.0).min(), 0.0)
    with callable_frames():
        assert callable(frame['close'])
        trapped = frame['close'].diff().iloc[1:].clip(lower=0.0).min()
    assert not np.isclose(trapped, 0.0), \
        'pandas no longer mishandles a callable where() condition; the numpy-first ' \
        'rule in pylightcharts/indicators.py can be revisited'


def test_indicators_survive_callable_frames(frame):
    """The real guard: every indicator must be immune to the trap."""
    expected = _snapshot(frame)
    with callable_frames():
        got = _snapshot(frame)

    for name, series in expected.items():
        assert np.allclose(np.asarray(got[name], dtype=float),
                           np.asarray(series, dtype=float), equal_nan=True), \
            f'{name} changed when Series became callable'


def test_callable_frames_do_not_leak(frame):
    """The context managers must restore pandas exactly (note that pandas may
    already define `__call__`, so only the *value* is compared)."""
    from pandas.core import common as pd_common

    before = (pd.Series.__dict__.get('__call__'), pd.DataFrame.__dict__.get('__call__'),
              pd_common.apply_if_callable)
    with callable_frames():
        pass
    after = (pd.Series.__dict__.get('__call__'), pd.DataFrame.__dict__.get('__call__'),
             pd_common.apply_if_callable)
    assert before == after
    if before[0] is None:
        assert not callable(frame['close'])


def test_rsi_is_bounded_even_with_callable_frames(frame):
    """RSI is in 0..100 by construction; the trap pushed it to -991/395."""
    with callable_frames():
        values = ind.rsi(frame['close'], 14).dropna()
    assert values.min() >= 0.0
    assert values.max() <= 100.0


def test_indicators_do_not_write_into_the_input(frame):
    """No indicator may mutate the caller's frame (pandas CoW / views)."""
    before = frame.copy(deep=True)
    _snapshot(frame)
    pd.testing.assert_frame_equal(frame, before)


# --------------------------------------------------------------------------
# the script that guards a minibt checkout
# --------------------------------------------------------------------------

#: the tail of minibt/indicators/core.py that creates the trap
ORIGINAL_TAIL = '''def _call_(self:pd.DataFrame | pd.Series, *args, **kwargs)->KLine | IndFrame | IndSeries:
    if self.ndim == 1:
        return IndSeries(self,**kwargs)
    else:
        lines=list(self.columns)
        if set(lines).issuperset(FILED.ALL):
            return KLine(self[FILED.ALL],**kwargs)
        else:
            return IndFrame(self,lines=lines,**kwargs)

pd.DataFrame.__call__ = _call_
pd.Series.__call__ = _call_
'''


def _patch_script():
    import importlib.util

    path = pathlib.Path(__file__).resolve().parents[1] / 'scripts' / 'patch_minibt.py'
    spec = importlib.util.spec_from_file_location('patch_minibt_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_patch_script_guards_minibt_and_is_idempotent():
    """minibt ships without version control here, so the script has to be re-runnable."""
    module = _patch_script()
    patched, changed = module.patch_source(ORIGINAL_TAIL)

    assert changed is True
    assert module.MARKER in patched
    assert patched.startswith(ORIGINAL_TAIL.rstrip('\n')[:40])
    assert module.patch_source(patched)[1] is False, 'must be idempotent'


def test_patch_script_refuses_an_unexpected_file():
    module = _patch_script()
    with pytest.raises(SystemExit, match='core.py'):
        module.patch_source('def something_else():\n    pass\n')


def test_the_generated_guard_neutralises_a_live_trap(frame):
    """The guard the script writes is what actually fixes the host, so prove it
    against a live trap rather than just asserting on the text."""
    module = _patch_script()
    delta = frame['close'].diff().iloc[1:]

    with callable_frames():                     # pristine pandas + the trap
        assert delta.clip(lower=0.0).min() < 0, 'the trap must be active'
        exec(module.GUARD, {'pd': pd})          # exactly what the script appends
        assert np.isclose(delta.clip(lower=0.0).min(), 0.0)

    # callable_frames() restored pandas, so nothing leaked into the next test
    assert np.isclose(delta.clip(lower=0.0).min(), 0.0)
