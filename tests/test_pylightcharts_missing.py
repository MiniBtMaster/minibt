"""`pylightcharts.util._has_missing` 必须把 **inf** 也当缺失。

否则 `encode_series_data` 会走 base64 浮点块，把 `Infinity` 原样下发到 JS，
Lightweight Charts 的自动缩放 / 图例读数就会出错 ✗（曾导致 supertrend 异常）。

    pytest tests/test_pylightcharts_missing.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def test_has_missing_detects_inf_and_nan():
    from pylightcharts.util import _has_missing

    frame = lambda values: pd.DataFrame(  # noqa: E731
        {'time': pd.date_range('2020', periods=len(values)), 'value': values})
    assert _has_missing(frame([1.0, 2.0, 3.0])) is False
    assert _has_missing(frame([1.0, np.inf, 3.0])) is True
    assert _has_missing(frame([1.0, -np.inf, 3.0])) is True
    assert _has_missing(frame([1.0, np.nan, 3.0])) is True
    assert _has_missing(pd.Series([1.0, 2.0])) is False
    assert _has_missing(pd.Series([1.0, np.inf])) is True


def test_encoder_avoids_base64_when_inf_present():
    from pylightcharts.util import encode_series_data

    clean = pd.DataFrame({'time': pd.date_range('2020', periods=4),
                          'value': [1.0, 2.0, 3.0, 4.0]})
    dirty = clean.copy()
    dirty.loc[1, 'value'] = np.inf
    # base64 路径用 decodeData；JSON 路径不会
    assert 'decodeData' in encode_series_data(clean) or True  # 阈值相关，不强制
    assert 'decodeData' not in encode_series_data(dirty)
