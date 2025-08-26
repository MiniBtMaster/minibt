# -*- coding: utf-8 -*-
import pandas_ta as pta
from pandas_ta.utils import get_offset, non_zero_range, verify_series, get_drift, is_datetime64_any_dtype
from pandas_ta.core import AnalysisIndicators, BasePandasObject, pd
# from pandas_ta.core import *
from inspect import signature, _empty
from copy import deepcopy
import numpy as np
from typing import TYPE_CHECKING, Union, Callable, Any, Sequence, Generator, Iterable, Literal, Optional
from .other import *
from . import zigzag as zig
import math
import statsmodels.api as sm
from scipy import stats as scipy_stats
import scipy.signal as scipy_signal
from functools import partial, reduce
from joblib import Parallel, delayed
from numpy.lib.stride_tricks import as_strided
from numpy.version import version as npVersion
from numpy_ext import prepend_na, rolling
from numpy import array as npArray
from numpy.random import RandomState
from .ta_ import LazyImport
if npVersion >= "1.20.0":
    from numpy.lib.stride_tricks import sliding_window_view
np.seterr(divide='ignore', invalid='ignore')
npInf = np.inf


def pad_array_to_match(array: np.ndarray, length):
    len_diff = length-len(array)
    if len_diff <= 0:
        return array
    if array.ndim == 1:
        return np.concatenate((np.full(len_diff, np.nan), array))
    else:
        return np.vstack((np.full((len_diff, array.shape[1]), np.nan), array))


def Any_(*args, **kwargs):
    assert args, "请传入参数"
    if len(args) == 1:
        return args[0]
    return reduce(lambda x, y: x | y, args)


def All_(*args, **kwargs):
    assert args, "请传入参数"
    if len(args) == 1:
        return args[0]
    return reduce(lambda x, y: x & y, args)


def cum(series: pd.Series, length=10, **kwargs) -> pd.Series:
    return series.rolling(length).sum()


def ZeroDivision(a: np.ndarray, b: np.ndarray = 1., dtype=np.float32, **kwargs) -> np.ndarray:
    if hasattr(a, "values"):
        a = a.values
    if hasattr(b, "values"):
        b = b.values
    if isinstance(a, np.ndarray):
        a = a.astype(dtype)
    if isinstance(b, np.ndarray):
        b = b.astype(dtype)
    return np.divide(a, b, out=np.zeros_like(a), where=b != 0., dtype=dtype)


def _linreg(close, length=None, offset=None, **kwargs):
    """Indicator: Linear Regression"""
    # Validate arguments
    length = int(length) if length and length > 0 else 14
    close = verify_series(close, length)
    offset = get_offset(offset)
    angle = kwargs.pop("angle", False)
    intercept = kwargs.pop("intercept", False)
    degrees = kwargs.pop("degrees", False)
    r = kwargs.pop("r", False)
    slope = kwargs.pop("slope", False)
    tsf = kwargs.pop("tsf", False)

    if close is None:
        return

    # Calculate Result
    x = range(1, length + 1)  # [1, 2, ..., n] from 1 to n keeps Sum(xy) low
    x_sum = 0.5 * length * (length + 1)
    x2_sum = x_sum * (2 * length + 1) / 3
    divisor = length * x2_sum - x_sum * x_sum

    def linear_regression(series):
        if (series == None).any():
            series = pd.Series(series).fillna(method='bfill')
            series = series.values
        y_sum = series.sum()
        xy_sum = (x * series).sum()

        m = (length * xy_sum - x_sum * y_sum) / divisor
        if slope:
            return m
        b = (y_sum * x2_sum - x_sum * xy_sum) / divisor
        if intercept:
            return b

        if angle:
            theta = np.arctan(m)
            if degrees:
                theta *= 180 / np.pi
            return theta

        if r:
            y2_sum = (series * series).sum()
            rn = length * xy_sum - x_sum * y_sum
            rd = (divisor * (length * y2_sum - y_sum * y_sum)) ** 0.5
            return rn / rd

        return m * length + b if tsf else m * (length - 1) + b

    def rolling_window(array, length):
        """https://github.com/twopirllc/pandas-ta/issues/285"""
        strides = array.strides + (array.strides[-1],)
        shape = array.shape[:-1] + (array.shape[-1] - length + 1, length)
        return as_strided(array, shape=shape, strides=strides)

    if npVersion >= "1.20.0":
        linreg_ = [linear_regression(
            _) for _ in sliding_window_view(npArray(close), length)]
    else:
        linreg_ = [linear_regression(_)
                   for _ in rolling_window(npArray(close), length)]

    linreg = pd.Series([npInf] * (length - 1) + linreg_, index=close.index)

    # Offset
    if offset != 0:
        linreg = linreg.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        linreg.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        linreg.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    linreg.name = f"LR"
    if slope:
        linreg.name += "m"
    if intercept:
        linreg.name += "b"
    if angle:
        linreg.name += "a"
    if r:
        linreg.name += "r"

    linreg.name += f"_{length}"
    linreg.category = "overlap"

    return linreg


pta.linreg = _linreg


def _rolling_window_2D(v: np.ndarray, window: int = 1) -> list[np.ndarray]:
    """2维滚动数据"""
    # dim0, dim1 = v.shape
    # stride0, stride1 = v.strides
    # 同步滚动长度,不足的补nan值
    datas = []
    for j in range(v.shape[1]):
        # if window > 1:
        #     redata = []
        #     for i in range(window-1):
        #         d = v[:i+1, :]
        #         nad = np.full((window-i-1, dim1), np.nan)
        #         redata.append(np.vstack((nad, d)))
        #     print(redata)
        # data = as_strided(v, (dim0-(window-1), window, dim1),
        #                   (stride0, stride0, stride1))
        # data_ = np.vstack((np.array(redata), data)) if window > 1 else data
        datas.append(_rolling_window_1D(v[:, j], window))
    # print(data_.shape
    return datas


def _rolling_window_1D(v: np.ndarray, window: int = 1) -> np.ndarray:
    """1维滚动数据"""
    dim0, = v.shape
    stride0, = v.strides
    # 同步滚动长度,不足的补nan值
    if window > 1:
        redata = []
        for i in range(window-1):
            d = v[:i+1]
            nad = np.full(window-i-1, np.nan)
            # redata.append(np.vstack((nad, d)))
            redata.append(np.append(nad, d, axis=0))
    data = as_strided(v, (dim0-(window-1), window, ),
                      (stride0, stride0, ))
    return np.vstack((np.array(redata), data)) if window > 1 else data


def rolling_apply(
    df: Union[pd.DataFrame, pd.Series],
    func: Callable,
    window: int,
    prepend_nans: bool = True,
    n_jobs: int = 1,
    **kwargs
) -> np.ndarray:
    df = df._df if hasattr(df, "_df") else df
    df = df.pandas_object if hasattr(df, "pandas_object") else df
    filed = [k for k, v in signature(
        func).parameters.items() if v.empty]
    assert filed, f"函数{func.__name__}请设置参数"
    if not any(isinstance(window, t) for t in [int, np.integer]):
        raise TypeError(f'Wrong window type ({type(window)}) int expected')
    window = int(window)
    if isinstance(df, pd.Series):
        rolls = _rolling_window_1D(df.values, window)
        if n_jobs == 1:
            arr = list(map(func, rolls))
        else:
            arr = list(Parallel(n_jobs=n_jobs)(delayed(func)(d)
                                               for d in rolls))
        result = np.array(arr)
    elif isinstance(df, pd.DataFrame) and all([string in df.columns for string in filed]):
        if df.shape[1] == 1:
            rolls = _rolling_window_1D(df.values[:, 0], window)
            if n_jobs == 1:
                arr = list(map(func, rolls))
            else:
                arr = list(Parallel(n_jobs=n_jobs)(delayed(func)(d)
                                                   for d in rolls))
        else:
            df = df[filed]
            rolls = _rolling_window_2D(df.values, window)
            if n_jobs == 1:
                arr = list(map(func, *rolls))
            else:
                arr = list(Parallel(n_jobs=n_jobs)(delayed(func)(*d)
                           for d in zip(rolls)))
        result = np.array(arr)
    # 函数参数将数据作为整体
    else:
        datas = df.values
        arrays = [datas[:, i] for i in range(datas.shape[1])]

        def _apply_func_to_arrays(idxs):
            return func(*[array[idxs[0]:idxs[-1] + 1] for array in arrays])
        array = arrays[0]
        rolls = rolling(
            array if len(arrays) == n_jobs == 1 else np.arange(len(array)),
            window=window,
            skip_na=True
        )
        if n_jobs == 1:
            if len(arrays) == 1:
                arr = list(map(func, rolls))
            else:
                arr = list(map(_apply_func_to_arrays, rolls))
        else:
            f = delayed(_apply_func_to_arrays)
            arr = Parallel(n_jobs=n_jobs)(f(idxs[[0, -1]]) for idxs in rolls)
        result = prepend_na(
            arr, n=window - 1) if prepend_nans else np.array(arr)
    # return prepend_na(arr, n=window - 1) if prepend_nans else np.array(arr)

    if len(result.shape) > 2:
        result = result.reshape(tuple(list(result.shape)[:2]))
    return result


def _stoch(high, low, close, k=None, d=None, smooth_k=None, mamode=None, offset=None, **kwargs):
    """Indicator: Stochastic Oscillator (STOCH)"""
    # Validate arguments
    k = k if k and k > 0 else 14
    d = d if d and d > 0 else 3
    smooth_k = smooth_k if smooth_k and smooth_k > 0 else 3
    _length = max(k, d, smooth_k)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    offset = get_offset(offset)
    mamode = mamode if isinstance(mamode, str) else "sma"

    if high is None or low is None or close is None:
        return

    # Calculate Result
    lowest_low = low.rolling(k).min()
    highest_high = high.rolling(k).max()

    stoch = 100 * (close - lowest_low)
    stoch /= non_zero_range(highest_high, lowest_low)
    # pandas_ta原指标转入长度与原长度不一致
    # stoch_k = ma(mamode, stoch.loc[stoch.first_valid_index():,], length=smooth_k)
    # stoch_d = ma(mamode, stoch_k.loc[stoch_k.first_valid_index():,], length=d)
    stoch_k = pta.ma(mamode, stoch, length=smooth_k)
    stoch_d = pta.ma(mamode, stoch_k, length=d)
    # Offset
    if offset != 0:
        stoch = stoch.shift(offset)
        stoch_k = stoch_k.shift(offset)
        stoch_d = stoch_d.shift(offset)
    # Handle fills
    if "fillna" in kwargs:
        stoch.fillna(kwargs["fillna"], inplace=True)
        stoch_k.fillna(kwargs["fillna"], inplace=True)
        stoch_d.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        stoch.fillna(method=kwargs["fill_method"], inplace=True)
        stoch_k.fillna(method=kwargs["fill_method"], inplace=True)
        stoch_d.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _name = "STOCH"
    _props = f"_{k}_{d}_{smooth_k}"
    stoch_k.name = f"{_name}k{_props}"
    stoch_d.name = f"{_name}d{_props}"
    stoch_k.category = stoch_d.category = "momentum"

    # Prepare DataFrame to return
    data = {stoch.name: stoch, stoch_k.name: stoch_k, stoch_d.name: stoch_d}
    df = pd.DataFrame(data)
    df.name = f"{_name}{_props}"
    df.category = stoch_k.category
    return df


pta.stoch = _stoch


def _calc_dev(base_price, price):
    return 100 * (price - base_price) / base_price


def _zigzag_(high: pd.Series, low: pd.Series, close: pd.Series, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1.) -> pd.Series:
    if not up_thresh:
        up_thresh = multiplier * \
            pta.true_range(high, low, close).mean()/close.mean()
    return zig.PeakValleyPivots(close.values, up_thresh, down_thresh)


class ZigZag:

    @staticmethod
    def zigzag(high: pd.Series, low: pd.Series, close: pd.Series, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> pd.Series:
        # high, low = high.values, low.values
        pvp = _zigzag_(high, low, close, up_thresh, down_thresh, multiplier)
        pvp = np.where(pvp > 0., high, 0.)+np.where(pvp < 0., low, 0.)
        pvp = pd.Series(pvp).apply(lambda x: x if x else np.nan)
        return pvp

    @staticmethod
    def zigzag_full(high: pd.Series, low: pd.Series, close: pd.Series, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> pd.Series:
        return ZigZag.zigzag(high, low, close, up_thresh, down_thresh, multiplier, **kwargs).interpolate(method="linear")

    @staticmethod
    def zigzag_modes(high: pd.Series, low: pd.Series, close: pd.Series, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> pd.Series:
        return pd.Series(zig.PivotsToModes(_zigzag_(high, low, close, up_thresh, down_thresh, multiplier)))

    @staticmethod
    def zigzag_returns(high: pd.Series, low: pd.Series, close: pd.Series, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., limit: bool = True, **kwargs) -> pd.Series:
        pvp = ZigZag.zigzag(high, low, close, up_thresh,
                            down_thresh, multiplier, **kwargs).values
        _close = close.values
        size = _close.size
        result = np.zeros(size)
        last = _close[-1]
        pre = pvp[0]
        for (i,), p in np.ndenumerate(pvp[:-1]):
            if not np.isnan(p):
                result[i] = (p-pre)/pre
                pre = p
            else:
                result[i] = (_close[i]-pre)/pre
        else:
            result[-1] = (last-pre)/pre
        return pd.Series(result)


def abc(df: pd.DataFrame, lim: float = 5., price_tick: float = 0.01, **kwargs) -> pd.DataFrame:
    # df=pd.DataFrame(dict(open=open,high=high,low=low,close=close))
    col = FILED.OHLC.tolist()
    df = df[col]
    frame = pd.DataFrame(columns=col)
    max_line = lim*price_tick
    for rows in df.itertuples():
        index, open, high, low, close = rows
        tick = abs(open-close)/price_tick
        if index:
            diff = open-preclose
            open -= diff
            high -= diff
            low -= diff
            close -= diff

            if tick > lim:
                if close >= open:
                    up = min(high-close, max_line)
                    close = open+lim*price_tick
                    high = close+up
                else:
                    down = min(close-low, max_line)
                    close = open-lim*price_tick
                    low = close-down
        else:
            if tick > lim:
                if close >= open:
                    up = min(high-close, max_line)
                    close = open+lim*price_tick
                    high = close+up
                else:
                    down = min(close-low, max_line)
                    close = open-lim*price_tick
                    low = close-down
        preclose = close
        frame.loc[index, :] = [open, high, low, close]
    frame = frame.astype(np.float64)
    frame.category = 'candles'
    return frame


def insidebar(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 10, **kwargs):
    length = int(length) if length and length > 0 else 10
    high = high.rolling(length).max().values
    low = low.rolling(length).min().values
    size = close.size
    close = close.values
    thrend = np.full((size,), np.nan)
    line = np.full((size,), np.nan)
    thrend[length-1] = 1.
    for i in range(length, size):
        _close, _low, _high = close[i], low[i-1], high[i-1]
        diff = _high-_low
        if close[i] > _high:
            thrend[i] = 1.
        elif close[i] < _low:
            thrend[i] = -1.
        else:
            thrend[i] = thrend[i-1]
        if thrend[i] > 0.:
            line[i] = (_close-_low)/diff
        else:
            line[i] = (_close-_high)/diff
    return pd.DataFrame(dict(thrend=thrend, line=line))


def line_trhend(data: pd.Series, length: int = 1, **kwargs):
    size = data.size
    line = np.zeros(size)
    lennan = len(line[np.isnan(line)])
    value = data.values
    pre = value[lennan]
    for i in range(lennan+length, size):
        v = value[i]
        if pre < v:
            line[i] = 1.
        elif pre > v:
            line[i] = -1.
        else:
            line[i] = line[i-1]
        pre = value[i+1-length]
    return pd.Series(line)


def smoothrng(x: pd.Series, t: int, m: float = 1.):
    """平滑平均范围"""
    wper = t*2 - 1
    avrng = pta.ema((x - x.shift(1)).apply(abs), t)
    smoothrng = pta.ema(avrng, wper)*m
    return smoothrng


def rngfilt(x: pd.Series, r: pd.Series):
    """过滤范围"""
    _add = (x+r).values
    _diff = (x-r).values
    x = x.values
    m = len(_add[pd.isna(_add)])
    rngfilt = np.array([np.nan]*m)
    rngfilt = np.insert(rngfilt, m, x[m])
    dir = np.array([np.nan]*m)
    dir = np.insert(dir, m, 1.)
    # lennan = max(len(x[isnan(x)]), len(r[isnan(r)]))
    for i in range(m+1, x.size):
        pre_rngfilt = rngfilt[i-1]
        add, diff = _add[i], _diff[i]
        # 向上突破时时候保持收盘价与目标线在一个r值距离，如果收盘价上涨小于r值，则没突破，维持原值
        y = pre_rngfilt if diff < pre_rngfilt else diff
        # 向下突破时时候保持收盘价与目标线在一个r值距离，如果收盘价下跌小于r值，则没突破，维持原值
        z = pre_rngfilt if add > pre_rngfilt else add
        # 收盘价在前一值之上，则有可能向上突破，则取y，之下则有可能向下突破，取z
        pre_dir = dir[i-1]
        next_rngfilt = y if x[i] > pre_rngfilt else z
        next_dir = pre_dir if pre_rngfilt == next_rngfilt else (
            1. if next_rngfilt > pre_rngfilt else -1.)
        rngfilt = np.insert(rngfilt, i, next_rngfilt)
        dir = np.insert(dir, i, next_dir)
    return pd.Series(rngfilt), pd.Series(dir)

# 自定义内置指标


class Candles:

    def Heikin_Ashi_Candles(df: pd.DataFrame, length=0) -> pd.DataFrame:
        length = length if length and length >= 0 else 0
        if length:
            df_ls = [df.shift(i).fillna(method="backfill")
                     if i else df for i in range(length+1)]
            _open = df_ls[-1].open
            _close = df.close
            _low = reduce(np.minimum, [data.low for data in df_ls])
            _high = reduce(np.maximum, [data.high for data in df_ls])
            dframe = pta.ha(_open, _high, _low, _close)
        else:
            dframe = pta.ha(df.open, df.high, df.low, df.close)
        dframe.columns = FILED.OHLC.tolist()
        # dframe = pd.concat([df[["datetime", "volume"]], dframe], axis=1)
        # print(dframe.head())
        # dframe=pd.DataFrame(dict(datetime=df.datetime,open=dframe.HA_open,high=dframe.HA_high,low=dframe.HA_low,close=dframe.HA_close,volume=df.volume))
        dframe["datetime"] = df.datetime
        dframe["volume"] = df.volume
        dframe = dframe[FILED.ALL]
        dframe.category = 'candles'
        return dframe

    def Linear_Regression_Candles(df: pd.DataFrame, length=11) -> pd.DataFrame:
        lr_open = pta.linreg(df.open, length)
        lr_high = pta.linreg(df.high, length)
        lr_low = pta.linreg(df.low, length)
        lr_close = pta.linreg(df.close, length)
        dframe = pd.DataFrame(
            dict(datetime=df.datetime, open=lr_open, high=lr_high, low=lr_low, close=lr_close, volume=df.volume))
        dframe.loc[:length, FILED.OHLC] = df.loc[:length, FILED.OHLC]
        dframe.category = 'candles'
        return dframe


class BtFunc(LazyImport):

    def open(open, **kwargs):
        return open

    def high(high, **kwargs):
        return high

    def low(low, **kwargs):
        return low

    def close(close, **kwargs):
        return close

    def smoothrng(close: pd.Series, length: int = 14, mult: float = 1., **kwargs):
        """平滑平均范围"""
        wper = length*2 - 1
        avrng = pta.ema((close - close.shift(1)).apply(abs), length)
        smoothrng = pta.ema(avrng, wper)*mult
        return smoothrng

    def rngfilt(close: pd.Series, r: pd.Series = None, **kwargs):
        """过滤范围"""
        _add = (close+r).values
        _diff = (close-r).values
        x = close.values
        m = len(_add[pd.isna(_add)])
        rngfilt = np.array([np.nan]*m)
        rngfilt = np.insert(rngfilt, m, x[m])
        dir = np.array([np.nan]*m)
        dir = np.insert(dir, m, 1.)
        # lennan = max(len(x[isnan(x)]), len(r[isnan(r)]))
        for i in range(m+1, x.size):
            pre_rngfilt = rngfilt[i-1]
            add, diff = _add[i], _diff[i]
            # 向上突破时时候保持收盘价与目标线在一个r值距离，如果收盘价上涨小于r值，则没突破，维持原值
            y = pre_rngfilt if diff < pre_rngfilt else diff
            # 向下突破时时候保持收盘价与目标线在一个r值距离，如果收盘价下跌小于r值，则没突破，维持原值
            z = pre_rngfilt if add > pre_rngfilt else add
            # 收盘价在前一值之上，则有可能向上突破，则取y，之下则有可能向下突破，取z
            pre_dir = dir[i-1]
            next_rngfilt = y if x[i] > pre_rngfilt else z
            next_dir = pre_dir if pre_rngfilt == next_rngfilt else (
                1. if next_rngfilt > pre_rngfilt else -1.)
            rngfilt = np.insert(rngfilt, i, next_rngfilt)
            dir = np.insert(dir, i, next_dir)
        df = pd.concat([rngfilt, dir], axis=1)
        df.category = 'overlap'
        return df

    def alerts(close, length=None, mult=None, **kwargs):
        """alerts指标
        https://cn.tradingview.com/script/ETB76oav/"""
        length = int(length) if length and length > 0 else 14
        mult = mult if mult and mult > 0. else 0.6185
        # close=Series(self.close.values)
        smrng = smoothrng(close, length, mult)
        filt, dir = rngfilt(close, smrng)
        hband = filt + smrng
        lband = filt - smrng
        df = pd.concat([filt, hband, lband, dir], axis=1)
        df.category = 'overlap'
        return df

    # price density 价格密度函数

    def noises_density(high: pd.Series, low: pd.Series, length: int = 10, **kwargs) -> pd.Series:
        length = int(length) if length >= 1 else 10
        direction = (high-low).rolling(length).sum()
        volatility = high.rolling(length).max()-low.rolling(length).min()
        return direction/volatility

    # ER效率系数

    def noises_er(close: pd.Series, length: int, **kwargs) -> pd.Series:
        length = int(length) if length >= 1 else 10
        direction = close.diff(length).abs()  # 方向性
        volatility = close.diff().abs().rolling(length).sum()  # 波动性
        return direction/volatility
    # fractal dimension 分型维度

    def noises_fd(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 10, **kwargs) -> pd.Series:
        n = int(length) if length >= 1 else 10
        direction = close.diff().abs()
        volatility = high.rolling(n).max()-low.rolling(n).min()
        l = (pow(1./n, 2)+direction/volatility).apply(lambda x: np.sqrt(x)
                                                      ).rolling(n).sum().apply(lambda x: np.log(x))
        return (l+np.log(2))/np.log(2.*n)

    def kama(close: pd.Series, length=None, fast=None, slow=None, drift=None, offset=None, **kwargs):
        """Indicator: Kaufman's Adaptive Moving Average (KAMA)"""
        # Validate Arguments
        length = int(length) if length and length > 0 else 10
        fast = int(fast) if fast and fast > 0 else 2
        slow = int(slow) if slow and slow > 0 else 30
        close = verify_series(close, max(fast, slow, length))
        drift = get_drift(drift)
        offset = get_offset(offset)

        if close is None:
            return

        # Calculate Result
        def weight(length: int) -> float:
            return 2 / (length + 1)

        fr = weight(fast)
        sr = weight(slow)

        abs_diff = non_zero_range(close, close.shift(length)).abs()
        peer_diff = non_zero_range(close, close.shift(drift)).abs()
        peer_diff_sum = peer_diff.rolling(length).sum()
        er = np.divide(abs_diff, peer_diff_sum, out=np.zeros_like(
            abs_diff, dtype=np.float32), where=peer_diff_sum != 0.)
        x = er * (fr - sr) + sr
        sc = x * x

        m = close.size
        result = [np.nan for _ in range(0, length - 1)] + [0]
        for i in range(length, m):
            result.append(sc.iloc[i] * close.iloc[i] +
                          (1 - sc.iloc[i]) * result[i - 1])

        kama = pd.Series(result, index=close.index)

        # Offset
        if offset != 0:
            kama = kama.shift(offset)

        # Handle fills
        if "fillna" in kwargs:
            kama.fillna(kwargs["fillna"], inplace=True)
        if "fill_method" in kwargs:
            kama.fillna(method=kwargs["fill_method"], inplace=True)

        # Name & Category
        kama.name = f"KAMA_{length}_{fast}_{slow}"
        kama.category = 'overlap'

        return kama

    def mama(close: pd.Series, fastlimit=0.6185, slowlimit=0.06185, **kwargs):
        mama, fama = BtFunc.talib.MAMA(close, fastlimit, slowlimit)
        df = pd.concat([mama, fama], axis=1)
        df.category = "overlap"
        return df

    def pmax(close: pd.Series, length=None, mult=None, mode='hma', dev='stdev', **kwargs):
        # Validate Arguments
        length = (int(length) if length > 0 else 10) if length else 10
        mult = (float(mult) if mult > 0 else 0.6185) if mult else 0.6185
        mode = mode if mode else 'hma'
        # Calculate Results
        line = getattr(pta, mode)(close, length)
        std = getattr(pta, dev)(close, length)
        longStop = line-mult*std
        shortStop = line+mult*std
        line, longStop, shortStop = line.values, longStop.values, shortStop.values
        lennan = max(len(line[np.isnan(line)]), len(
            longStop[np.isnan(longStop)]), len(shortStop[np.isnan(shortStop)]))
        maxlong = longStop[lennan]
        minshort = shortStop[lennan]
        long = np.zeros(len(line))
        short = np.zeros(len(line))
        thrend = np.zeros(len(line))
        dir = 1
        for i in range(len(line)):
            if i < lennan:
                long[i] = np.nan
                short[i] = np.nan
                thrend[i] = 0
            else:
                x = -1 if dir == 1 and line[i] < maxlong else dir
                dir = 1 if dir == -1 and line[i] > minshort else x
                if dir == 1:
                    maxlong = max(maxlong, longStop[i])
                    minshort = shortStop[i]
                    long[i] = maxlong
                    short[i] = np.nan
                else:
                    minshort = min(minshort, shortStop[i])
                    maxlong = longStop[i]
                    long[i] = np.nan
                    short[i] = minshort
                thrend[i] = dir
        df = pd.DataFrame(dict(long=long, short=short, thrend=thrend))
        df.category = "overlap"
        return df

    def pv(close: pd.Series, length=10, **kwargs):
        result = close.pct_change(length)
        result.name = f"pv_{length}"
        return result

    def AndeanOsc(open: pd.Series, close: pd.Series, length: int = 14, signal_length: int = 9, **kwargs):
        '''
            Inputs
            ------
            close : Closing price (Array)
            open  : Opening price (Array)

            Settings
            --------
            length        : Indicator period (float)
            signal_length : Signal line period (float)

            Returns
            -------
            Bull   : Bullish component (Array)
            Bear   : Bearish component (Array)
            Signal : Signal line (Array)

            Example
            -------
            bull,bear,signal = AndeanOsc(close,open,14,9)
            '''
        N = len(close)

        alpha = 2/(length+1)
        alpha_signal = 2/(signal_length+1)

        up1, up2, dn1, dn2, bull, bear, signal = np.zeros((7, N))

        up1[0] = dn1[0] = signal[0] = close[0]
        up2[0] = dn2[0] = close[0]**2

        for i in range(1, N):
            up1[i] = max(close[i], open[i], up1[i-1] -
                         alpha*(up1[i-1] - close[i]))
            dn1[i] = min(close[i], open[i], dn1[i-1] +
                         alpha*(close[i] - dn1[i-1]))

            up2[i] = max(close[i]**2, open[i]**2, up2[i-1] -
                         alpha*(up2[i-1] - close[i]**2))
            dn2[i] = min(close[i]**2, open[i]**2, dn2[i-1] +
                         alpha*(close[i]**2 - dn2[i-1]))

            bull[i] = np.sqrt(dn2[i] - dn1[i]**2)
            bear[i] = np.sqrt(up2[i] - up1[i]**2)

            signal[i] = signal[i-1] + alpha_signal * \
                (np.maximum(bull[i], bear[i]) - signal[i-1])
        result = pd.DataFrame(
            dict(up=up1, dn=dn1, bull=bull, bear=bear, signal=signal))
        result.overlap = dict(up=True, dn=True, bull=False,
                              bear=False, signal=False)
        return result

    def Coral_Trend_Candles(close: pd.Series, smooth: int = 9., mult: float = .4, **kwargs) -> pd.Series:
        # string GROUP_3 = 'Config » Coral Trend Candles'
        size = len(close)
        src = close.values
        _sm = smooth if smooth and smooth > 0. else 9.
        cd = mult if mult and mult > 0. else .4
        di = (_sm) / 2.0 + 1.0
        c1 = 2. / (di + 1.0)
        c2 = 1. - c1
        c3 = 3.0 * (cd * cd + cd * cd * cd)
        c4 = -3.0 * (2.0 * cd * cd + cd + cd * cd * cd)
        c5 = 3.0 * cd + 1.0 + cd * cd * cd + 3.0 * cd * cd
        i1 = np.zeros(size)
        i2 = np.zeros(size)
        i3 = np.zeros(size)
        i4 = np.zeros(size)
        i5 = np.zeros(size)
        i6 = np.zeros(size)
        bfr = np.zeros(size)
        for i in range(1, size):
            i1[i] = c1 * src[i] + c2 * i1[i-1]
            i2[i] = c1 * i1[i] + c2 * i2[i-1]
            i3[i] = c1 * i2[i] + c2 * i3[i-1]
            i4[i] = c1 * i3[i] + c2 * i4[i-1]
            i5[i] = c1 * i4[i] + c2 * i5[i-1]
            i6[i] = c1 * i5[i] + c2 * i6[i-1]
            bfr[i] = -cd * cd * cd * i6[i] + c3 * \
                i5[i] + c4 * i4[i] + c5 * i3[i]
        return pd.Series(bfr)

    def rsrs(high: pd.Series, low: pd.Series, volume: pd.Series, length: int = 10, method='r1', weights=True, **kwargs):
        # https://zhuanlan.zhihu.com/p/631688107?utm_id=0
        model = sm.WLS if weights else sm.OLS
        size = high.size
        rs = np.zeros(size)
        r2 = np.zeros(size)
        high = high.values
        low = low.values
        volume = volume.values
        for i in range(length-1, size):
            h = high[i-length+1:i+1]
            l = low[i-length+1:i+1]
            _l = sm.add_constant(l).astype(np.float64)
            _h = sm.add_constant(h).astype(np.float64)
            if weights:
                v = volume[i-length+1:i+1].astype(np.float64)
                model1 = model(h, _l, weights=v).fit()
                model2 = model(l, _h, weights=v).fit()
            else:
                model1 = model(h, _l).fit()
                model2 = model(l, _h).fit()
            rs[i] = model1.params[1]
            r2[i] = model2.params[1]  # rsquared

        if method == 'r1':
            return pd.DataFrame(dict(rshl=rs, rslh=r2))
        elif method == 'r2':
            return pta.zscore(pd.Series(rs), 2*length)
        elif method == 'r3':
            return pta.zscore(pd.Series(rs), 2*length)*r2
        return pd.Series(pta.zscore(pd.Series(rs), 2*length).values*r2*rs)

    def realized(close: pd.Series, length: int = 10, **kwargs):
        ret = close.apply(math.log).diff()
        return ret.rolling(window=length).apply(lambda x: np.sqrt(np.sum(x**2)))

    def moving_average(interval: pd.Series, windowsize: int = 10, mode='same'):
        """mode:'same','full','valid'"""
        window = np.ones(int(windowsize)) / float(windowsize)
        re = np.convolve(interval.values, window, mode)
        return re

    def savitzky_golay(close: pd.Series, window_length: Any, polyorder: Any, deriv: int = 0, delta: float = 1, axis: int = -1, mode: str = 'interp', cval: float = 0, **kwargs):
        return pd.Series(scipy_signal.savgol_filter(close.values, window_length, polyorder, deriv, delta, axis, mode, cval))

    def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, length=14, multiplier=2., weights=2., offset=None, **kwargs):
        """Indicator: Supertrend"""
        # Validate Arguments
        length = int(length) if length and length > 0 else 7
        multiplier = float(
            multiplier) if multiplier and multiplier > 0 else 3.0
        offset = get_offset(offset)

        # Calculate Results
        m = close.size
        dir_, trend = [1] * m, [0] * m
        long, short = [npInf] * m, [npInf] * m

        hhv = (weights*high+low)/(weights+1.)
        llv = (weights*low+high)/(weights+1.)
        matr = multiplier * pta.atr(high, low, close, length)
        upperband = llv + matr
        lowerband = hhv - matr

        for i in range(1, m):
            if close.iloc[i] > upperband.iloc[i - 1]:
                dir_[i] = 1
            elif close.iloc[i] < lowerband.iloc[i - 1]:
                dir_[i] = -1
            else:
                dir_[i] = dir_[i - 1]
                if dir_[i] > 0 and lowerband.iloc[i] < lowerband.iloc[i - 1]:
                    lowerband.iloc[i] = lowerband.iloc[i - 1]
                if dir_[i] < 0 and upperband.iloc[i] > upperband.iloc[i - 1]:
                    upperband.iloc[i] = upperband.iloc[i - 1]

            if dir_[i] > 0:
                trend[i] = long[i] = lowerband.iloc[i]
            else:
                trend[i] = short[i] = upperband.iloc[i]

        # Prepare DataFrame to return
        _props = f"_{length}_{multiplier}"
        df = pd.DataFrame({
            f"SUPERT{_props}": trend,
            f"SUPERTd{_props}": dir_,
            f"SUPERTl{_props}": long,
            f"SUPERTs{_props}": short,
        }, index=close.index)

        df.name = f"SUPERT{_props}"
        df.category = "overlap"

        # Apply offset if needed
        if offset != 0:
            df = df.shift(offset)

        # Handle fills
        if "fillna" in kwargs:
            df.fillna(kwargs["fillna"], inplace=True)

        if "fill_method" in kwargs:
            df.fillna(method=kwargs["fill_method"], inplace=True)

        return df

    def argrelextrema(high: pd.Series, low: pd.Series, order: int = 5, mode='clip', **kwargs):
        """mode:[clip,wrap]"""
        maximum, _ = scipy_signal.argrelextrema(
            high.values, np.greater, order=order, mode=mode)
        minimum, _ = scipy_signal.argrelextrema(
            low.values, np.less, order=order, mode=mode)
        zig = np.full(high.size, np.nan)
        zig[maximum] = high[maximum]
        zig[minimum] = low[minimum]
        zig = pd.Series(zig, name='argrelextrema')
        return zig

    def dkx(open, high, low, close, num=None, length=None, offset=None, **kwargs):
        length = int(length) if length > 0 else 10
        num = int(num) if num >= 2 else 20
        mid = (3*close+open+high+low)/6.0
        dk = num*mid
        for i in range(1, num):
            dk += (num-i)*mid.shift(i)
        dk = dk/sum(list(range(1, num+1)))
        df = pd.concat([dk, pta.sma(dk, length)], axis=1)
        df.columns = [f"{n}_{str(num)}_{str(length)}" for n in [
            "Dkx", "MaDkx"]]
        return df

    def emsa(close: pd.Series, bar: int = 10, length: int = 48, al=True):
        if al:
            alpha = (1 - np.sin(360 / length)) / np.cos(360 / length)
        else:
            alpha = (np.cos(360/length)+np.sin(360/length)-1) / \
                np.cos(360/length)

        deta = 1-alpha/2
        a = np.exp(-np.sqrt(2)*np.pi/bar)
        b = 2*a*np.cos(np.sqrt(2)*180/bar)
        c2, c3 = b, -a**2
        c1 = 1-c2-c3

        diff = close-2*close.shift(1)+close.shift(2)
        filt = np.zeros(close.size)
        hp = np.zeros(close.size)
        em = np.zeros(close.size)
        for i in range(close.size):
            if i > 1:
                hp[i] = deta*deta*diff.iloc[i]+2 * \
                    (1-alpha)*hp[i-1]-(1-alpha)*(1-alpha)*hp[i-2]
                filt[i] = c1*(hp[i]+hp[i-1])/2.+c2*filt[i-1]+c3*filt[i-2]
                wave = (filt[i]+filt[i-1]+filt[i-2])/3.
                pwr = (filt[i]*filt[i]+filt[i-1] *
                       filt[i-1]+filt[i-2]*filt[i-2])/3.
                em[i] = pwr if pwr == 0 else wave/np.sqrt(pwr)

        return pd.Series(em)

    def highpassfilter(close: pd.Series, length: int = 10):
        a = np.cos(.707*360/48)
        alpha = (a+np.sin(.707*360/48)-1)/a
        deta = 1-alpha/2
        src = close-2*close.shift(1)+close.shift(2)
        hp = np.zeros(close.size)
        for i in range(close.size):
            if i > 1:
                hp[i] = deta*deta*src.iloc[i]+2 * \
                    (1-alpha)*hp[i-1]-(1-alpha)*(1-alpha)*hp[i-2]
        hp = pd.Series(hp)

        a = np.exp(-1.414*np.pi/length)
        b = 2*a*np.cos(1.414*180/length)
        c2, c3 = b, -a**2
        c1 = 1-c2-c3
        src = (hp+hp.shift(1))/2.
        filt = np.zeros(close.size)
        for i in range(close.size):
            if i > 1:
                filt[i] = c1*src.iloc[i]+c2*filt[i-1]+c3*filt[i-2]
        return pd.Series(filt)

    def mcd(open, high, low, close, volume, length: int):
        data = np.column_stack(
            (open.values, high.values, low.values, close.values, volume.values))

        size = data.shape[0]
        delta = np.zeros(size)
        _mcd = np.zeros(size)
        for i in range(size):
            sro, srh, srl, src, srv = data[i]
            if src >= sro:
                de = src-sro+2*(srh-src)+2*(sro-srl)
                if de > 0:
                    delta[i] = srv*(srh-srl)/de
            else:
                de = sro-src+2*(srh-sro)+2*(src-srl)
                if de > 0:
                    delta[i] = -srv*(srh-srl)/de
            if i >= length-1:
                _mcd[i] = delta[i-length+1:i+1].sum()
        return pd.Series(_mcd)

    def rsj(close: pd.Series, length: int):
        rt = close/close.shift()-1.
        RSJ = np.zeros(close.size)
        PositiveRt = np.zeros(close.size)
        NegativeRt = np.zeros(close.size)

        for i in range(close.size):
            if i > 0:
                rt_ = rt.iloc[i]
                if rt_ > 0:
                    PositiveRt[i] = rt_
                else:
                    NegativeRt[i] = rt_
            if i > length-1:
                PositiveRV = np.power(PositiveRt[i-length+1:i+1], 2).sum()
                NegativeRV = np.power(NegativeRt[i-length+1:i+1], 2).sum()
                RSJ[i] = (PositiveRV-NegativeRV) / \
                    np.power(rt.iloc[i-length+1:i+1].values, 2).sum()
        return pd.Series(RSJ)

    def superbandpassfilter(close: pd.Series, length: int = 10):
        def func(x: pd.Series):
            return np.sqrt(x.mean())
        a, b = 5/35, 5/65
        pb = np.zeros(close.size)
        for i in range(close.size):
            if i > 1:
                pb[i] = (a-b)*close.iloc[i]+(b*(1-a)-a*(1-b)) * \
                    close.iloc[i-1]+(2-a-b)*pb[i-1]-(1-a)*(1-b)*pb[i-2]
        pb = pd.Series(pb)
        return pb, pb.rolling(length).apply(lambda x: func(x*x))

    def supersmootherfilter(close: pd.Series, length: int):
        a = np.exp(-1.414*np.pi/length)
        b = 2*a*np.cos(1.414*180/length)
        c2, c3 = b, -a**2
        c1 = 1-c2-c3
        src = (close+close.shift(1))/2.
        filt = np.zeros(close.size)
        for i in range(close.size):
            if i > 1:
                filt[i] = c1*src.iloc[i]+c2*filt[i-1]+c3*filt[i-2]
        return pd.Series(filt)

    def vwap(close: pd.Series, volume: pd.Series, length: int, mult: float = 2.):
        cv = (close*volume).rolling(length).apply(lambda x: x.sum())
        sv = volume.rolling(length).apply(lambda x: x.sum())
        vwap = cv/sv
        std = (close-vwap).abs().rolling(length).apply(lambda x: x.std())
        sdup, sddn = vwap+mult*std, vwap-mult*std
        vwapr = 100*(close-sddn)/(2*mult*std)
        return vwap, sdup, sddn, vwapr

    def lowpass(close: pd.Series, length: int):
        lp = np.zeros(close.size)
        a = 2/(1+length)
        powa = a*a
        for i in range(close.size):
            if i >= length-1:
                lp[i] = (a-powa/4)*close.iloc[i]+powa*close.iloc[i-1]/2 - \
                    (a-3*powa/4)*close.iloc[i-2]+2 * \
                    (1-a)*lp[i-1]-(1-a)*(1-a)*lp[i-2]
        return pd.Series(lp)

    def rsrs(low: pd.Series, high: pd.Series, close: pd.Series, vol: pd.Series, length: int = None, weights: bool = False):
        length = length if length and length > 0 else 18
        size = low.size
        rs = np.full(size, np.nan)
        if weights:
            for i in range(size):
                if i >= length-1:
                    weights = vol.iloc[i-length+1:i+1].values
                    h = high.iloc[i-length+1:i+1].values
                    l = low.iloc[i-length+1:i+1].values
                    l = sm.add_constant(l)
                    model = sm.WLS(h, l, weights=weights).fit()
                    rs[i] = model.params[1]
        else:
            for i in range(size):
                if i >= length-1:
                    h = high.iloc[i-length+1:i+1].values
                    l = low.iloc[i-length+1:i+1].values
                    l = sm.add_constant(l)
                    model = sm.OLS(h, l).fit()
                    rs[i] = model.params[1]

        return pd.Series(rs)

    def z_rsrs(low: pd.Series, high: pd.Series, close: pd.Series, vol: pd.Series, length: int = None):
        length = length if length and length > 0 else 18
        size = low.size
        rs = np.full(size, np.nan)
        zrs = np.full(size, np.nan)
        for i in range(size):
            if i >= length-1:
                weights = vol.iloc[i-length+1:i+1].values
                h = high.iloc[i-length+1:i+1].values
                l = low.iloc[i-length+1:i+1].values
                l = sm.add_constant(l)
                model = sm.WLS(h, l, weights=weights).fit()
                rs[i] = model.params[1]
            if i >= 2*length-1:
                mean = rs[i-length+1:i+1].mean()
                std = rs[i-length+1:i+1].std()
                zrs[i] = (rs[i]-mean)/std

        return pd.Series(zrs)

    def cor_rsrs(low: pd.Series, high: pd.Series, close: pd.Series, vol: pd.Series, length: int = None, right_avertence: bool = False):
        length = length if length and length > 0 else 18
        size = low.size
        rs = np.full(size, np.nan)
        zrs = np.full(size, np.nan)
        for i in range(size):
            if i >= length-1:
                weights = vol.iloc[i-length+1:i+1].values
                h = high.iloc[i-length+1:i+1].values
                l = low.iloc[i-length+1:i+1].values
                l = sm.add_constant(l)
                model = sm.WLS(h, l, weights=weights).fit()
                rs[i] = model.params[1]
            if i >= 2*length-1:
                mean = rs[i-length+1:i+1].mean()
                std = rs[i-length+1:i+1].std()
                zrs[i] = (rs[i]-mean)/std

        return pd.Series(zrs*rs*rs) if right_avertence else pd.Series(zrs*rs)

    def pass_rsrs(low: pd.Series, high: pd.Series, close: pd.Series, vol: pd.Series, length: int = None):
        length = length if length and length > 0 else 18
        size = low.size
        rs = np.full(size, np.nan)
        zrs = np.full(size, np.nan)
        rsquared = np.full(size, np.nan)
        stdpercent = np.full(size, np.nan)
        for i in range(size):
            if i >= length-1:
                weights = vol.iloc[i-length+1:i+1].values
                h = high.iloc[i-length+1:i+1].values
                l = low.iloc[i-length+1:i+1].values
                l = sm.add_constant(l)
                model = sm.WLS(h, l, weights=weights).fit()
                rs[i] = model.params[1]
                rsquared[i] = model.rsquared
                stdpercent[i] = scipy_stats.percentileofscore(
                    weights, weights[-1])/100.0
            if i >= 2*length-1:
                mean = rs[i-length+1:i+1].mean()
                std = rs[i-length+1:i+1].std()
                zrs[i] = (rs[i]-mean)/std

        return pd.Series(zrs*rsquared*rsquared*stdpercent)

    def ols(high: pd.Series, low: pd.Series, n: int = 35):
        '''差价回归买卖信号'''
        size = high.size
        high, low = high.values, low.values
        rs = np.zeros(size)
        rsquared = np.zeros(size)
        for i in range(size):
            if i < n-1:
                rs[i] = np.nan
                rsquared[i] = np.nan
            else:
                x, y = low[i+1-n:i+1], high[i+1-n:i+1]
                X = sm.add_constant(x, prepend=True)
                model = np.dot((np.dot(np.linalg.inv(np.dot(X.T, X)), X.T)), y)
                rsquared[i], rs[i] = model
        return pd.DataFrame(dict(rs=rs, rsquared=rsquared))

    def _func(close: pd.Series, up: pd.Series, dn: pd.Series, count_length: int):
        p, m = np.where(close.iloc[-count_length:] > dn.iloc[-count_length:], 1,
                        0), np.where(close.iloc[-count_length:] < up.iloc[-count_length:], 1, 0)
        return p.sum()-m.sum()

    def tpr(close: pd.Series, length: int, mult: float = 0.6185, mode='dema', count_length: int = None):
        """meoth (str):dema, ema, fwma, hma, linreg, midpoint, pwma, rma,
            sinwma, sma, swma, t3, tema, trima, vidya, wma, zlma"""
        length = length if length and length > 1 else 30
        count_length = min(
            count_length, length) if count_length and count_length > 1 else length
        ma_, std = pta.ma(mode, close, length=length), pta.stdev(close, length)
        up, dn = ma_+mult*std, ma_-mult*std
        return close.rolling(length).apply(
            lambda x: BtFunc._func(x, up[x.index], dn[x.index], count_length))

    def tpr(close: pd.Series, length: int, angle: float = 5):
        _slope = pta.slope(close, length, as_angle=True, to_degrees=True)

        def func(slope: pd.Series, angle: float):
            p = np.where(slope > angle, 1, 0)
            m = np.where(slope < -angle, 1, 0)
            return 100.*abs(p.sum()-m.sum())
        return _slope.rolling(length).apply(lambda x: func(x, angle)/length)

    def _correl(close: pd.Series):
        sx, sy, sxx, sxy, syy = 0, 0, 0, 0, 0
        size = close.size
        for i in range(size):
            x = close.iloc[i]
            y = -i
            sx += x
            sy += y
            sxx += x*x
            sxy += x*y
            syy += y*y
        t1, t2 = size*sxx-sx*sx, size*syy-sy*sy
        if t1 > 0 and t2 > 0:
            return (size*sxy-sx*sy)/np.sqrt(t1*t2)
        else:
            return .0

    def cti(close: pd.Series, length: int):
        return close.rolling(length).apply(lambda x: BtFunc._correl(x))

    def fft_theta(close: pd.Series):
        sp = np.fft.fft(close.values)
        return pd.Series(np.arctan(sp.imag/sp.real))

    def _tma(close: pd.Series):
        size = close.size
        index = np.arange(1, size+1)
        return (close.values*index).sum()/index.sum()

    def tma(high, low, close: pd.Series, length=151, artlength=151, mult=2.5):
        mid = close.rolling(length).apply(lambda x: BtFunc._tma(x))
        range_ = pta.atr(high, low, close, artlength)
        higher = mid+mult*range_
        lower = mid-mult*range_
        df = pd.concat([mid, higher, lower], axis=1)
        df.columns = ['mid', 'higher', 'lower']
        return df

    def variance_calculator(close: pd.Series, _sma: pd.Series, length):
        temp = close.subtract(_sma)  # Difference a-b
        temp2 = temp.apply(lambda x: x**2)  # Square them.. (a-b)^2
        # Summation (a-b)^2 / (length - 1)
        temp3 = temp2.rolling(length - 1).mean()
        sigma = temp3.apply(lambda x: math.sqrt(x))
        return sigma

    def PCR(close: pd.Series, length: int = 20, k: float = 1.5, l: float = 2):
        _sma = pta.sma(close)
        sigma = BtFunc.variance_calculator(close, _sma, length)
        k_sigma = k * sigma
        l_sigma = l * sigma
        UBB = _sma.add(k_sigma)  # Upper Bollinger Band
        LBB = _sma.subtract(k_sigma)  # Lower Bollinger Band
        USL = _sma.add(l_sigma)  # Upper Stoploss Band
        LSL = _sma.subtract(l_sigma)  # Lower Stoploss Band
        long_signal = pta.cross(close, UBB)
        short_signal = pta.cross(close, LBB, above=False)
        up = pta.cross(close, _sma)
        down = pta.cross(close, _sma, False)
        les = pta.cross(close, USL)
        ses = pta.cross(close, LSL, False)
        exitlong_signal = (les | down).astype(np.float32)
        exitshort_signal = (ses | up).astype(np.float32)
        return pd.DataFrame(dict(
            ubb=UBB,
            lbb=LBB,
            usl=USL,
            lsl=LSL,
            long_signal=long_signal,
            exitlong_signal=exitlong_signal,
            short_signal=short_signal,
            exitshort_signal=exitshort_signal,
        ))

    def TRIN(close: pd.Series, volume: pd.Series, length: int = 20, pct_length: int = 1, k: float = 1.5, l: float = 2):
        ratio = close.divide(close.shift(pct_length))
        vol = volume.divide(volume.shift(pct_length))
        trin = ratio.divide(vol)
        _sma = pta.sma(trin)
        sigma = BtFunc.variance_calculator(trin, _sma, length)
        k_sigma = k * sigma
        l_sigma = l * sigma
        UBB = _sma.add(k_sigma)  # Upper Bollinger Band
        LBB = _sma.subtract(k_sigma)  # Lower Bollinger Band
        USL = _sma.add(l_sigma)  # Upper Stoploss Band
        LSL = _sma.subtract(l_sigma)  # Lower Stoploss Band
        long_signal = pta.cross(close, UBB)
        short_signal = pta.cross(close, LBB, above=False)
        up = pta.cross(close, _sma)
        down = pta.cross(close, _sma, False)
        les = pta.cross(close, USL)
        ses = pta.cross(close, LSL, False)
        exitlong_signal = (les | down).astype(np.float32)
        exitshort_signal = (ses | up).astype(np.float32)
        return pd.DataFrame(dict(
            trin=trin,
            ubb=UBB,
            lbb=LBB,
            usl=USL,
            lsl=LSL,
            long_signal=long_signal,
            exitlong_signal=exitlong_signal,
            short_signal=short_signal,
            exitshort_signal=exitshort_signal,
        ))


# 天勤指标


class TqFunc:

    def ref(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        m = close.shift(length)
        m.name = f"tq_ref_{length}"
        m.category = 'overlap'
        return m

    def std(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        m = close.rolling(length).std()
        m.name = f"tq_std_{length}"
        return m

    def ma(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        ma_data = close.rolling(length).mean()
        ma_data.name = f"tq_ma_{length}"
        ma_data.category = "overlap"
        return ma_data

    def sma(close: pd.Series, n: int = 10, m: int = 2, **kwargs):
        n = int(n) if n >= 1 else 10
        m = int(m) if m >= 0 else 2
        assert n > m, '周期n必须大于权重m'
        sma_data = close.ewm(alpha=m / n, adjust=False).mean()
        sma_data.naem = f"tq_sma_{n}_{m}"
        sma_data.category = "overlap"
        return sma_data

    def ema(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        ema_data = close.ewm(span=length, adjust=False).mean()
        ema_data.name = f"tq_ema_{length}"
        ema_data.category = "overlap"
        return ema_data

    def ema2(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        weights = list(i for i in range(1, length + 1))  # 对应的权值列表

        def average(elements):
            return np.average(elements, weights=weights)

        ema2 = close.rolling(window=length).apply(average, raw=True)
        ema2.name = f"tq_ema2_{length}"
        ema2.category = "overlap"
        return ema2

    def crossup(close: pd.Series, b: pd.Series = None, **kwargs):
        crossup_data = pd.Series(
            np.where((close > b) & (close.shift(1) <= b.shift(1)), 1, 0))
        crossup_data.name = "tq_crossup"
        return crossup_data

    def crossdown(close: pd.Series, b: pd.Series = None, **kwargs):
        crossdown_data = pd.Series(
            np.where((close < b) & (close.shift(1) >= b.shift(1)), 1, 0))
        crossdown_data.name = "tq_crossdown"
        return crossdown_data

    def count(cond: pd.Series = None, length: int = 10, **kwargs):
        length = int(length) if length >= 0 else 10
        if length == 0:  # 从第一个有效值开始统计
            count_data = pd.Series(np.where(cond, 1, 0).cumsum())
        else:  # 统计每个n周期
            count_data = pd.Series(
                pd.Series(np.where(cond, 1, 0)).rolling(length).sum())
        return count_data

    def trma(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        if length % 2 == 0:
            n1 = int(length / 2)
            n2 = int(length / 2 + 1)
        else:
            n1 = n2 = int((length + 1) / 2)
        ma_half = TqFunc.ma(close, n1)
        trma_data = TqFunc.ma(ma_half, n2)
        trma_data.name = f"tq_trma_{length}"
        trma_data.category = "overlap"
        return trma_data

    def harmean(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        harmean_data = length / ((1 / close).rolling(length).sum())
        harmean_data.name = f"tq_harmean_{length}"
        harmean_data.category = "overlap"
        return harmean_data

    def numpow(close: pd.Series, n: int = 10, m: int = 2, **kwargs):
        n = int(n) if n >= 1 else 10
        m = int(m) if m >= 1 else 2
        numpow_data = sum((n - i) ** m * close.shift(i) for i in range(n))
        numpow_data.name = f"tq_numpow_{n}_{m}"
        return numpow_data

    def abs(close: pd.Series, **kwargs):
        abs_data = pd.Series(np.absolute(close))
        abs_data.name = 'tq_abs'
        return abs_data

    def min(close: pd.Series, b: pd.Series = None, **kwargs):
        if isinstance(close, pd.Series):
            close = close.values
        if isinstance(b, pd.Series):
            b = b.values
        min_data = pd.Series(np.minimum(close, b))
        min_data.name = 'tq_min'
        min_data.category = "overlap"
        return min_data

    def max(close: pd.Series, b: pd.Series = None, **kwargs):
        if isinstance(close, pd.Series):
            close = close.values
        if isinstance(b, pd.Series):
            b = b.values
        max_data = pd.Series(np.maximum(close, b))
        max_data.name = 'tq_max'
        max_data.category = "overlap"
        return max_data

    def median(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        median_data = close.rolling(length).median()
        median_data.name = f"tq_median_{length}"
        median_data.category = 'overlap'
        return median_data

    def exist(cond: pd.Series = None, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        exist_data = pd.Series(
            np.where(pd.Series(np.where(cond, 1, 0)).rolling(length).sum() > 0, 1, 0))
        exist_data.name = f"tq_exist_{length}"
        return exist_data

    def every(cond: pd.Series = None, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        every_data = pd.Series(
            np.where(pd.Series(np.where(cond, 1, 0)).rolling(length).sum() == length, 1, 0))
        every_data.name = f"tq_every_{length}"
        return every_data

    def hhv(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        hhv_data = close.rolling(length).max()
        hhv_data.name = f"tq_hhv_{length}"
        hhv_data.category = 'overlap'
        return hhv_data

    def llv(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10
        llv_data = close.rolling(length).min()
        llv_data.name = f"tq_llv_{length}"
        llv_data.category = 'overlap'
        return llv_data

    def avedev(close: pd.Series, length: int = 10, **kwargs):
        length = int(length) if length >= 1 else 10

        def mad(x):
            return np.fabs(x - x.mean()).mean()
        avedev_data = close.rolling(window=length).apply(mad, raw=True)
        avedev_data.name = f"tq_avedev_{length}"
        return avedev_data

    def barlast(cond: pd.Series = None, **kwargs):
        # cond = cond.astype(np.int8)
        # index = pd.Series(cond.index)
        # index_ = index.where(cond > 0)
        # index_ = index_.fillna(method="ffill")
        # return index-index_
        cond = cond.to_numpy()
        v = np.array(~cond, dtype=int)
        c = np.cumsum(v)
        x = c[cond]
        d = np.diff(np.concatenate(([0], x)))
        if len(d) == 0:  # 如果cond长度为0或无True
            return pd.Series([-1] * len(cond))
        v[cond] = -d
        r = np.cumsum(v)
        r[:x[0]] = -1
        return pd.Series(r)

    def cum_counts(cond: pd.Series = None, **kwargs):
        return cond * (cond.groupby((cond != cond.shift()).cumsum()).cumcount() + 1)
