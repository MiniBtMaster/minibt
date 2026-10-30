"""Per-point ("conditional") colours.

Lightweight Charts accepts a ``color`` on every data point - and
``borderColor`` / ``wickColor`` for candles - so any condition can drive the
colours. :func:`color_by` builds those columns for you:

    from pylightcharts import color_by

    chart.set(color_by(df, df['close'] > 205, 'orange', wick_color='orange'))

The engine repaints only the parts it is given: a per-point ``color`` alone
changes the candle body, ``wickColor`` / ``borderColor`` change the wick and
the edge (the helper fills all three unless told otherwise). Rows outside the
condition keep the series style - their keys are omitted, exactly like the
JavaScript example that returns the datapoint untouched.

Works for candles (body / wick / border), and for `Line` / `Area` / `Bar` /
`Histogram` series (only ``color`` matters there).
"""
from typing import Callable, Iterable, Optional, Union

import numpy as np
import pandas as pd

ColorSpec = Optional[Union[str, Iterable[str]]]
WickSpec = Union[bool, str, None]

__all__ = ['color_by', 'condition_mask']

#: the keys the engine reads per data point
COLOR_KEYS = ('color', 'borderColor', 'wickColor')


def color_by(frame: pd.DataFrame, condition, color: ColorSpec,
             else_color: ColorSpec = None, *, wick_color: WickSpec = None,
             border_color: WickSpec = None) -> pd.DataFrame:
    """Return `frame` with per-point colours applied where `condition` holds.

    :param condition: a boolean ``Series`` / array aligned with `frame`, or a
        callable that receives `frame` and returns one.
    :param color: body colour where the condition holds (a colour, or one per
        row).
    :param else_color: colour for the other rows; ``None`` (default) leaves
        them untouched, so they keep the series style.
    :param wick_color: ``None`` (default) follows `color`/`else_color`, a
        colour string overrides it, ``False`` leaves the wick to the style.
    :param border_color: same as `wick_color`, for the candle outline.
    :return: a copy of `frame` (the input is not modified).

    Rows without a colour get no key at all - the JSON/binary encoders drop the
    ``None``s, which is what makes "colour only some bars" work.
    """
    mask = condition_mask(frame, condition)
    if len(mask) != len(frame):
        raise ValueError(
            f'condition has {len(mask)} rows but the frame has {len(frame)}')

    true_colors = _colors(frame, color, 'color')
    false_colors = (np.full(len(frame), None, dtype=object)
                    if else_color is None
                    else _colors(frame, else_color, 'else_color'))

    out = frame.copy()
    out['color'] = np.where(mask, true_colors, false_colors)
    for column, spec in (('wickColor', wick_color),
                         ('borderColor', border_color)):
        if spec is False:
            continue
        if spec is None:
            true_side, false_side = true_colors, false_colors
        else:
            if not isinstance(spec, str):
                raise ValueError(
                    f'{column} must be a colour, False or None, not {spec!r}')
            true_side = np.full(len(frame), spec, dtype=object)
            false_side = (np.full(len(frame), spec, dtype=object)
                          if else_color is not None
                          else np.full(len(frame), None, dtype=object))
        out[column] = np.where(mask, true_side, false_side)
    return out


def condition_mask(frame: pd.DataFrame, condition,
                   time_column: str = 'time') -> np.ndarray:
    """Turn a `condition` (Series / array / callable) into a boolean array.

    A `Series` shorter than `frame` is aligned on `time` (the series' index is
    matched against the frame's ``time`` column); anything else is taken
    positionally.
    """
    if callable(condition):
        condition = condition(frame)
    if isinstance(condition, pd.Series):
        if time_column in frame.columns and len(condition) != len(frame):
            condition = _align_on_time(condition, frame[time_column])
        condition = condition.to_numpy()
    mask = np.asarray(condition)
    if mask.dtype != bool:
        try:
            mask = mask.astype(bool)
        except (TypeError, ValueError):
            raise ValueError('condition must be boolean or castable to bool')
    return mask


def _align_on_time(condition: pd.Series, times: pd.Series) -> pd.Series:
    """Match a shorter condition against the frame's time column.

    The frame usually holds epoch seconds (the chart formats its data), while a
    condition built from the caller's own frame is indexed by datetimes - or
    other way round - so both spellings are tried before giving up (the length
    check in `color_by` then raises a readable error).
    """
    candidates = [times.to_numpy()]
    if pd.api.types.is_numeric_dtype(times):
        candidates.append(pd.to_datetime(times, unit='s', errors='coerce'))
    for candidate in candidates:
        try:
            aligned = condition.reindex(candidate)
        except (TypeError, ValueError):
            continue
        if aligned.notna().any():
            # rows the condition does not cover simply get no colour
            return aligned.notna() & aligned.astype('boolean').fillna(False)
    return condition


def _colors(frame: pd.DataFrame, color: ColorSpec, name: str) -> np.ndarray:
    """A single colour repeated, or the given per-row colours."""
    if isinstance(color, str):
        return np.full(len(frame), color, dtype=object)
    values = np.asarray(list(color), dtype=object)
    if len(values) != len(frame):
        raise ValueError(
            f'{name} has {len(values)} entries but the frame has {len(frame)}')
    return values
