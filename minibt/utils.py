from __future__ import annotations
from typing import Any, Callable, Iterable, Union, Optional, Sequence, Generator, TYPE_CHECKING, overload
from functools import wraps, cache, reduce, partial
from collections import Counter
from cachetools import cachedmethod, Cache
from operator import attrgetter
import os
import logging
import colorlog
import pickle
import psutil
from retrying import retry
from addict import Addict, Dict
from pandas._libs.internals import BlockPlacement
from pandas.core import common  # 定位到函数所在的模块
from numpy.random import RandomState
import quantstats.stats as qs_stats
import quantstats.plots as qs_plot
# from .stop import BtStop
from typing_extensions import Literal
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED, ALL_COMPLETED
from copy import deepcopy
from pprint import pprint
from .constant import *
from iteration_utilities import flatten
from queue import Queue, LifoQueue
from inspect import signature, getsourcelines, stack, _empty, getsource
import ast
from pandas.core.window import Rolling
from .other import *
# import .cy.funcs as cyfuncs
# import minibt.cy as cyfuncs
# import minibt.cyfunc.utils as cy
import time as _time
from unittest.mock import patch
import sys
from io import StringIO
with patch('sys.stderr', new=StringIO()):
    from tqsdk.objs import Position, Quote
    from tqsdk.objs import Account as TqAccount
    from tqsdk import TqApi, TargetPosTask
from dataclasses import dataclass, field, fields
from collections.abc import MutableMapping
from operator import neg, pos
import warnings
from collections import OrderedDict
from sys import _getframe
from math import isfinite
# from .core import pd
import pandas as pd
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


pd.options.mode.chained_assignment = None
if TYPE_CHECKING:
    from .constant import *
    from .strategy.strategy import Strategy
    from .core import CoreFunc
    from .indicators import BtData, dataframe, series, Line
    from .bt import Bt

    class corefunc:
        """函数引导，无实际用处"""

        def __getattr__(self, name: str) -> CoreFunc: ...

# 基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _cagr(returns, rf=0.0, compounded=True, periods=252):
    """适合tick数据
    计算超额收益的年化增长率(CAGR%)

    如果rf非零，必须指定periods，此时rf被假定为年度化数据

    参数:
        returns: 收益数据，带时间索引
        rf: 无风险收益率
        compounded: 是否使用复利计算
        periods: 每年的交易周期数（默认252，适用于股票交易日）
    """

    total = qs_stats._utils._prepare_returns(returns, rf)

    # 计算总收益
    if compounded:
        total = qs_stats.comp(total)
    else:
        total = np.sum(total)

    # 计算时间跨度（年）
    try:
        # 获取时间差（天）
        time_diff_days = (returns.index[-1] - returns.index[0]).days

        # 处理时间跨度为0或负的情况
        if time_diff_days <= 0:
            # 对于单周期数据，直接返回对应周期的收益率（非年化）
            return total if not isinstance(returns, pd.DataFrame) else pd.Series(total, index=returns.columns)

        # 计算年数（避免除以零）
        years = time_diff_days / periods

        # 计算CAGR
        res = (abs(total + 1.0) ** (1.0 / years)) - 1

        # 保持返回格式与输入一致
        if isinstance(returns, pd.DataFrame):
            res = pd.Series(res)
            res.index = returns.columns

        return res

    except ZeroDivisionError:
        # 理论上已通过time_diff_days检查避免，但保留作为最后防护
        return total if not isinstance(returns, pd.DataFrame) else pd.Series(total, index=returns.columns)
    except Exception as e:
        # 处理其他可能的索引错误
        raise ValueError(f"计算CAGR时出错: {str(e)}") from e


qs_stats.cagr = _cagr


def _add_symbol_info(self: pd.DataFrame, **kwargs):
    """pd.DataFrame快速增加数据列"""
    if kwargs:
        cols = self.columns
        for k, v in kwargs.items():
            if k not in cols:
                self[k] = v


pd.DataFrame.add_info = _add_symbol_info


def __sharpe(returns, rf=0.0, periods=252, annualize=True, smart=False):
    """
    Calculates the sharpe ratio of access returns

    If rf is non-zero, you must specify periods.
    In this case, rf is assumed to be expressed in yearly (annualized) terms

    Args:
        * returns (Series, DataFrame): Input return series
        * rf (float): Risk-free rate expressed as a yearly (annualized) return
        * periods (int): Freq. of returns (252/365 for daily, 12 for monthly)
        * annualize: return annualize sharpe?
        * smart: return smart sharpe ratio
    """
    if rf != 0 and periods is None:
        raise Exception("Must provide periods if rf != 0")

    returns = qs_stats._utils._prepare_returns(returns, rf, periods)
    divisor = returns.std(ddof=1)
    if smart:
        # penalize sharpe with auto correlation
        divisor = divisor * qs_stats.autocorr_penalty(returns)
    # 原函数有BUG
    if isinstance(divisor, pd.Series):
        divisor = divisor.iloc[0]
    if divisor:
        res = returns.mean() / divisor
    else:
        return .0

    if annualize:
        return res * qs_stats._np.sqrt(1 if periods is None else periods)

    return res


qs_stats.sharpe = __sharpe

# 开盘时间
OPEN_TIME: list[time] = [time(9, 0), time(13, 0), time(21, 0)]
# CPU核心个数
MAX_WORKERS = psutil.cpu_count(logical=True)-1

#
SIGNAL_Str = np.array(['long_signal', 'exitlong_signal',
                      'short_signal', 'exitshort_signal'])

# pandas方法,除['copy', 'rolling', 'resample']copy方法返回pandas数据格式,rolling,resample作了更改,copy为原始函数
# pandas_method = (set([s for s, vs in pd.Series.__dict__.items() if not s.startswith('_') and isinstance(vs, Callable)]) | set(
#     [d for d, vd in pd.DataFrame.__dict__.items() if not d.startswith('_') and isinstance(vd, Callable)])) - set(['copy', 'rolling', 'resample', "iloc", "loc", "at", "iat"])
# for pm in ["where", "abs", "shift", "astype", "pct_change", "ffill", "bfill", "ewm", "mean", "fillna", "interpolate"]:
#     pandas_method.add(pm)


def get_public_methods(cls) -> set:
    return {
        name for name in dir(cls)
        if not name.startswith('_')  # 排除私有方法
        and callable(getattr(cls, name))  # 确保是可调用对象
        and not isinstance(getattr(cls, name), property)  # 排除属性
    }


# 收集 Series 和 DataFrame 的方法
pandas_method = get_public_methods(
    pd.Series) | get_public_methods(pd.DataFrame)
# 移除不需要的方法
exclude_methods = {'copy', 'rolling', 'resample', 'iloc', 'loc', 'at', 'iat',
                   'values', 'dtype', 'shape', 'size'}  # 补充一些非方法属性
pandas_method -= exclude_methods

# pandas下的rolling方法
rolling_method = get_public_methods(Rolling)
# rolling_method = set([r for r, vr in Rolling.__dict__.items(
# ) if not r.startswith('_') and isinstance(vr, Callable)])


def __assign(self: dataframe, **kwargs):
    # assign修改
    data = self.pandas_object if hasattr(self, "pandas_object") else self
    for k, v in kwargs.items():
        data[k] = pd.core.common.apply_if_callable(v, self)
    return data


def _assign(self, **kwargs) -> pd.DataFrame:
    keep = kwargs.pop("keep", True)
    column = list(self.columns)
    new_kwargs = {}
    params = list(signature(IndSetting.__init__).parameters.keys())[1:]
    for k, v in kwargs.items():
        if k not in params:
            new_kwargs.update({k: v})
    data = __assign(self, **new_kwargs)
    new_col = list(data.columns)
    if not keep:
        data = data[[col for col in new_col if col not in column]]
    return data


pd.DataFrame.assign = _assign

# dataframe与series数据__getitem__函数作了更改
# pd.DataFrame 与 pd.Series 原始__getitem__函数,实盘策略中需要切换(回测不需要)
# raw_dataframe_getitem_func: Callable = pd.DataFrame.__getitem__
# raw_series_getitem_func: Callable = pd.Series.__getitem__

# raw_dataframe_setitem_func: Callable = pd.DataFrame.__setitem__


class TPE:
    """Initializes a new ThreadPoolExecutor instance.
    ---
    attr:
    --
    >>> self.executor = ThreadPoolExecutor()
    method:
    ---
    >>> multi_run  策略初始化时多指标计算
        replay_run 实时播放数据多线程计算
    """
    executor: Optional[ThreadPoolExecutor]

    def __init__(self) -> None:
        self.executor = None

    def reinit(self, **kwargs):
        max_workers = kwargs.pop("max_workers", None)
        thread_name_prefix = kwargs.pop("thread_name_prefix", "")
        initializer = kwargs.pop("initializer", None)
        initargs = kwargs.pop("initargs", ())
        if max_workers is None:
            # ThreadPoolExecutor is often used to:
            # * CPU bound task which releases GIL
            # * I/O bound task (which releases GIL, of course)
            #
            # We use cpu_count + 4 for both types of tasks.
            # But we limit it to 32 to avoid consuming surprisingly large resource
            # on many core machine.
            max_workers = min(32, (os.cpu_count() or 1) + 4)
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")

        if initializer is not None and not callable(initializer):
            raise TypeError("initializer must be a callable")

        self.executor._max_workers = max_workers
        self.executor._thread_name_prefix = (thread_name_prefix or
                                             ("ThreadPoolExecutor-%d" % self.executor._counter()))
        self.executor._initializer = initializer
        self.executor._initargs = initargs

    def multi_run(self, *args, **kwargs):
        """策略初始化时多指标计算"""
        if self.executor is None:
            self.executor = ThreadPoolExecutor()
        if kwargs:
            self.reinit(**kwargs)
        assert len(args) >= 2, "传参长度大于2"
        all_task = []
        for i, arg in enumerate(args):
            if isinstance(arg, Multiply):
                func, params, data = arg.values
                if data is not None:
                    data = data,
            elif isinstance(arg, Iterable) and len(arg) >= 2:
                func, params, *data = arg
                data = (data[0],) if data else None
            else:
                raise KeyError("参数有误")
            params = {**params, "_multi_index": i}
            assert isinstance(func, Callable), "请传入指标函数"
            if data:
                all_task.append(self.executor.submit(func, *data, **params))
            else:
                all_task.append(self.executor.submit(func, **params))

        wait(all_task, return_when=FIRST_COMPLETED)
        results: list = []
        for f in as_completed(all_task):
            result = f.result()
            results.append(result)
        results = sorted(results, key=lambda x: x[0])
        return [value for _, value in results]

    def run(self, func, klines) -> np.ndarray:
        if self.executor is None:
            self.executor = ThreadPoolExecutor()
        values = []
        results = [self.executor.submit(func, i, k)
                   for i, k in enumerate(klines)]
        wait(results, return_when=ALL_COMPLETED)
        for f in as_completed(results):
            result = f.result()
            values.append(result)
        values = sorted(values, key=lambda x: x[0])
        return np.array(list(map(lambda x: x[1], values)))

    def replay_run(self, func, klines, **kwargs) -> np.ndarray:
        """实时播放数据多线程计算"""
        from joblib import Parallel, delayed, parallel_backend
        with parallel_backend('loky'):  # 正确配置后端
            results = Parallel(
                n_jobs=-1,
                prefer='processes',
                max_nbytes='16M'
            )(delayed(func)(index=i, data_=k) for i, k in enumerate(klines))

        results = sorted(results, key=lambda x: x[0])
        return np.array(list(map(lambda x: x[1], results)))


TPE = TPE()


def cyclestring(cycle) -> str:
    """周期转字符串"""
    assert cycle > 0
    return cycle < 60 and f"{cycle}S" or (
        cycle < 3600 and f"{int(cycle/60)}M" or (
            cycle < 86400 and f"{int(cycle/3600)}H" or f"{int(cycle/86400)}D"
        )
    )


class CategoryString(str):
    """指标类别字符串"""
    @property
    def iscandles(self) -> bool:
        """### 是否为蜡烛图"""
        return "candles" in self

    @property
    def isoverlap(self) -> bool:
        """### 是否为主图叠加类别"""
        return "overlap" in self


class CandlesCategory(metaclass=Meta):
    """### 蜡烛图类型

    >>> Candles: CategoryString = CategoryString("candles")
        Heikin_Ashi_Candles: CategoryString = CategoryString("heikin_ashi_candles")
        Linear_Regression_Candles: CategoryString = CategoryString(
            "linear_regression_candles")"""
    Candles: CategoryString = CategoryString("candles")
    Heikin_Ashi_Candles: CategoryString = CategoryString("heikin_ashi_candles")
    Linear_Regression_Candles: CategoryString = CategoryString(
        "linear_regression_candles")


class Category(metaclass=Meta):
    """### 指标类别

    >>> Any: CategoryString = CategoryString("any")
        Candles: CategoryString = CategoryString("candles")
        Heikin_Ashi_Candles: CategoryString = CategoryString("heikin_ashi_candles")
        Linear_Regression_Candles: CategoryString = CategoryString(
            "linear_regression_candles")
        Momentum: CategoryString = CategoryString("momentum")
        Overlap: CategoryString = CategoryString("overlap")
        Performance: CategoryString = CategoryString("performance")
        Statistics: CategoryString = CategoryString("statistics")
        Trend: CategoryString = CategoryString("trend")
        Volatility: CategoryString = CategoryString("volatility")
        Volume: CategoryString = CategoryString("volume")"""
    Any: CategoryString = CategoryString("any")
    Candles: CategoryString = CategoryString("candles")
    Heikin_Ashi_Candles: CategoryString = CategoryString("heikin_ashi_candles")
    Linear_Regression_Candles: CategoryString = CategoryString(
        "linear_regression_candles")
    Momentum: CategoryString = CategoryString("momentum")
    Overlap: CategoryString = CategoryString("overlap")
    Performance: CategoryString = CategoryString("performance")
    Statistics: CategoryString = CategoryString("statistics")
    Trend: CategoryString = CategoryString("trend")
    Volatility: CategoryString = CategoryString("volatility")
    Volume: CategoryString = CategoryString("volume")


@dataclass
class Config:
    """策略设置

    >>> value: float = 1000_000.
        margin_rate: float = 0.05
        tick_commission: float = 0.
        percent_commission: float = 0.
        fixed_commission: float = 1.
        min_start_length: int = 0
        islog: bool = False
        isplot: bool = True
        clear_gap: bool = False
        data_segments: Union[float, int] = 1.
        slip_point = 0.
        print_account: bool = True
        key: str = 'datetime'
        start_time = None
        end_time = None
        time_segments: Union[time] = None
        profit_plot: bool = True
        click_policy: Literal["hide", "mute"] = "hide"
        take_time: bool = True
        trading_mode: Literal["on_close", "on_next_open"] = 'on_close'"""
    value: float = 1000_000.
    margin_rate: float = 0.05
    tick_commission: float = 0.
    percent_commission: float = 0.
    fixed_commission: float = 0.
    min_start_length: int = 0
    islog: bool = False
    isplot: bool = True
    clear_gap: bool = False
    data_segments: Union[float, int] = 1.
    slip_point = 0.
    print_account: bool = True
    key: str = 'datetime'
    start_time = None
    end_time = None
    time_segments: Union[time] = None
    profit_plot: bool = True
    click_policy: Literal["hide", "mute"] = "hide"
    take_time: bool = True
    trading_mode: Literal["on_close", "on_next_open"] = "on_close"

    def _get_commission(self):
        comm = dict()
        if isinstance(self.percent_commission, float) and self.percent_commission >= 0.:
            return comm.update(dict(percent_commission=self.percent_commission))
        else:
            if isinstance(self.tick_commission, (float, int)) and self.tick_commission >= 0.:
                comm.update(dict(tick_commission=self.tick_commission))
            elif isinstance(self.fixed_commission, (float, int)) and self.fixed_commission >= 0.:
                comm.update(dict(fixed_commission=self.fixed_commission))
        if not comm:
            return dict(fixed_commission=0.)
        return comm


class Lines(list):
    """### 指标线列表"""

    def __init__(self, *args, **kwargs) -> None:
        if args:
            super(Lines, self).__init__(args)
        else:
            super(Lines, self).__init__()
        self._lines: Addict = Addict(**kwargs)

    def __setattr__(self, __name: str, __value: Any) -> None:
        if isinstance(__value, (pd.Series, np.ndarray)):
            self._lines[__name] = __value
        return super().__setattr__(__name, __value)

    @property
    def values(self) -> list[str]:
        """### 指标线列表"""
        return list(self)

    @property
    def items(self) -> dict[str, Union[pd.Series, np.ndarray]]:
        """### 指标线数据"""
        return self._lines


class OrderedAddict(Addict):
    """### 有序Addict字典"""

    def _converted_key(self, key: str | int) -> str:
        if isinstance(key, int):
            key = list(self.keys())[key]
        return key

    def __getitem__(self, key: str | int) -> Union[Line, series, dataframe, BtData, Strategy]:
        return super().__getitem__(self._converted_key(key))

    def __setitem__(self, name: str | int, value: Union[Line, series, dataframe, BtData, Strategy]):
        name = self._converted_key(name)
        isFrozen = (hasattr(self, '__frozen') and
                    object.__getattribute__(self, '__frozen'))
        if isFrozen and name not in super(Dict, self).keys():
            raise KeyError(name)
        super(Dict, self).__setitem__(name, value)
        try:
            p = object.__getattribute__(self, '__parent')
            key = object.__getattribute__(self, '__key')
        except AttributeError:
            p = None
            key = None
        if p is not None:
            p[key] = self
            object.__delattr__(self, '__parent')
            object.__delattr__(self, '__key')

    def add_data(self, key: str | int, value: Union[Iterable, Strategy]) -> None:
        """### 向数据集中添加数据,当键相同时直接代替原数据"""
        self[key] = value

    @property
    def num(self) -> int:
        """### 数据集中数据的个数"""
        return len(self)


class StrategyInstances(OrderedDict, OrderedAddict):
    """### 策略实例有序字典"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class BtIndicatorDataSet(OrderedDict, OrderedAddict):
    """### 策略指标数据集有序字典"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class BtDatasSet(OrderedDict, OrderedAddict):
    """### 策略BtData数据集有序字典"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def max_length(self) -> int:
        """### BtData数据最大长度"""
        return max(self.lengths)

    @property
    def lengths(self) -> list[int]:
        """### 各个数据长度"""
        return [len(value) for _, value in self.items()]

    @property
    def date_index(self) -> pd.Index:
        """### BtData数据时间日期索引,用于回测分析"""
        max_length = self.max_length
        return pd.Index(list(filter(lambda x: len(x) == max_length, self.values()))[0].datetime.values)

    @property
    def default_btdata(self) -> BtData:
        """### BtData数据默认数据,索引为0的BtData数据"""
        return self[0]

    @property
    def last_btdata(self) -> BtData:
        """### BtData数据最后添加的数据"""
        return self[-1]

    @property
    def tq_klines(self) -> list[pd.DataFrame]:
        """### 天勤K线数据集"""
        return [btdata._dataset.tq_object for _, btdata in self.items()]


class DataSetBase:
    """### 数据基类"""

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"Key '{key}' not found")

    def __setitem__(self, key: str, value: Any) -> None:
        if not hasattr(self, key):
            raise KeyError(f"Cannot set unknown key '{key}'")
        setattr(self, key, value)

    def __delitem__(self, key: str) -> None:
        if hasattr(self, key):
            raise KeyError(f"Deleting key '{key}' is not allowed")
        raise KeyError(f"Key '{key}' not found")

    def __iter__(self):
        return (field.name for field in fields(self))

    def __len__(self) -> int:
        return len(fields(self))

    def __contains__(self, key: object) -> bool:
        return hasattr(self, key) if isinstance(key, str) else False

    def keys(self) -> list[str]:
        """### 键"""
        return [field.name for field in fields(self)]

    def values(self) -> list[Any]:
        """### 值"""
        return [getattr(self, field.name) for field in fields(self)]

    def items(self) -> tuple[str, Any]:
        """### 键值"""
        return [(field.name, getattr(self, field.name)) for field in fields(self)]

    def get(self, key: str, default: Any = None) -> Any:
        """### 获取数据"""
        return getattr(self, key, default)

    def update(self, other: dict) -> None:
        """### 更新数据"""
        for key, value in other.items():
            if hasattr(self, key) and value != getattr(self, key):
                setattr(self, key, value)
            else:
                raise KeyError(f"Key '{key}' not found")

    @property
    def copy_values(self) -> dict[str, Any]:
        """### 返回深复制的属性字典"""
        return {k: deepcopy(v) for k, v in self.items()}

    def filt_values(self, *args, **kwargs) -> dict[str, Any]:
        """### 返回已过滤的属性

        args :list[str]. 要过滤（删除）属性名称.

        kwargs :dic[str,Any]. 要替换属性的名称."""
        values = self.copy_values
        if args:
            for arg in args:
                if arg in values:
                    values.pop(arg)
        if kwargs:
            values = {**values, **kwargs}
        return values

    def copy(self, **kwargs) -> Union[BtID, IndSetting, Quotes, Broker, SymbolInfo, DataFrameSet]:
        values = self.copy_values
        if kwargs:
            values = {**values, **kwargs}
        return type(self.__class__.__name__, (self.__class__,), {})(**values)

    @property
    def vars(self) -> dict[str, Any]:
        """递归转换为字典，处理嵌套的DataSetBase对象"""
        result = {}
        for field in fields(self):
            key = field.name
            value = getattr(self, key)

            # 递归处理嵌套的DataSetBase对象
            if isinstance(value, DataSetBase):
                result[key] = value.vars
            # 处理DataSetBase对象列表
            elif isinstance(value, (list, SpanList)):
                result[key] = [item.vars if isinstance(
                    item, DataSetBase) else item for item in value]
            # 处理Addict字典中的DataSetBase对象
            elif isinstance(value, dict):
                result[key] = {
                    k: v.vars if isinstance(v, DataSetBase) else v
                    for k, v in value.items()
                }
            elif isinstance(value, str):  # CategoryString
                result[key] = str(value)
            else:
                result[key] = value
        return result

    def to_dict(self) -> Addict:
        return Addict({k: v for k, v in self.items()})


@dataclass
class BtID(DataSetBase):
    """### BtID
    >>> strategy_id:int 策略实例 ID.
        plot_id:int 画图 ID,改变ID可在跨周期显示指标.
        data_id:int 数据 ID,导入数据的顺序.
        resample_id:int resample ID,原始数据的序号,即resample的数据从哪个数据转换而来的序号.
        replay_id:int replay ID,原始数据的序号,即replay的数据从哪个数据转换而来的序号.
    """
    strategy_id: int = 0
    plot_id: int = 0
    data_id: int = 0
    resample_id: Optional[int] = None
    replay_id: Optional[int] = None


@dataclass
class DefaultIndicatorConfig(DataSetBase):
    """### 默认指标配置"""
    id: BtID = field(default_factory=BtID)
    sname: str = "name"
    ind_name: str = "ind_name"
    lines: list[str] = field(default_factory=lambda: ["line",])
    category: Optional[str] = None
    isplot: bool = True
    ismain: bool = False
    isreplay: bool = False
    isresample: bool = False
    overlap: bool = False
    isindicator: bool = True
    iscustom: bool = False
    dim_math: bool = True
    heigth: int = 150


@dataclass
class CandleStyle(DataSetBase):
    """### 蜡烛图风格"""
    bear: str | Colors = Colors.tomato
    bull: str | Colors = Colors.lime


@dataclass
class LineStyle(DataSetBase):
    """### 指标线风格"""
    line_dash: str | LineDash = LineDash.solid
    line_width: int | float = 1.3
    line_color: Optional[Union[str, Colors]] = None


class LineStyleType:
    """### 设置指标线风格代理类型"""

    def __init__(self, dataframe):
        # 使用 object.__setattr__ 避免触发自定义的 __setattr__
        object.__setattr__(self, '_dataframe', dataframe)

    def __getattr__(self, name) -> LineStyle:
        # 代理属性获取到 dataframe 的 linstyle 字典
        return getattr(object.__getattribute__(self, '_dataframe')._plotinfo.linestyle, name)

    def __setattr__(self, name, value):
        # 代理属性设置到 dataframe 的 linstyle 字典
        if name in object.__getattribute__(self, '_dataframe')._plotinfo.linestyle:
            setattr(object.__getattribute__(
                self, '_dataframe')._plotinfo.linestyle, name, value)


class LineAttrType:
    """### 设置指标线属性风格代理类型"""

    def __init__(self, dataframe, attr):
        object.__setattr__(self, '_dataframe', dataframe)
        object.__setattr__(self, '_attr', attr)

    def __getattr__(self, name):
        # 返回代理对象，允许链式操作
        return LineAttrProxy(object.__getattribute__(self, '_dataframe'), name)

    def __setattr__(self, name, value):
        if name == '_dataframe':
            object.__setattr__(self, name, value)
        else:
            # 直接设置指定线条的 line_dash
            df: dataframe = object.__getattribute__(self, '_dataframe')
            attr = object.__getattribute__(self, '_attr')
            if name not in df._plotinfo.linestyle:
                df._plotinfo.linestyle[name] = LineStyle()
            setattr(df._plotinfo.linestyle[name], attr, value)


class LineAttrProxy:
    """### 代理类，支持链式赋值 d.line_dash.line = value"""

    def __init__(self, dataframe, key):
        object.__setattr__(self, '_dataframe', dataframe)
        object.__setattr__(self, '_key', key)

    def __setattr__(self, name, value):
        if name in ['_dataframe', '_key']:
            object.__setattr__(self, name, value)
        else:
            # 设置指定属性的 line_dash
            df: dataframe = object.__getattribute__(self, '_dataframe')
            key = object.__getattribute__(self, '_key')
            if key not in df._plotinfo.linestyle:
                df._plotinfo.linestyle[key] = LineStyle()
            setattr(df._plotinfo.linestyle[key], name, value)


class SignalAttrType:
    """### 设置信号指标线属性风格代理类型"""

    def __init__(self, dataframe, attr):
        object.__setattr__(self, '_dataframe', dataframe)
        object.__setattr__(self, '_attr', attr)

    def __getattr__(self, name) -> SignalStyle:
        # 返回代理对象，允许链式操作
        return LineAttrProxy(object.__getattribute__(self, '_dataframe'), name)

    def __setattr__(self, name, value):
        if name == '_dataframe':
            object.__setattr__(self, name, value)
        else:
            # 直接设置指定线条的 line_dash
            df: dataframe = object.__getattribute__(self, '_dataframe')
            if name not in df._plotinfo.signalstyle:
                return
            if value not in df._plotinfo.lines and value not in FILED.OHLC:
                return
            attr = object.__getattribute__(self, '_attr')
            setattr(df._plotinfo.signalstyle[name], attr, value)
            setattr(df._plotinfo.signalstyle[name],
                    "overlap", value in FILED.OHLC)


class SignalAttrProxy:
    """### 代理类，支持链式赋值 d.line_dash.line = value"""

    def __init__(self, dataframe, key):
        object.__setattr__(self, '_dataframe', dataframe)
        object.__setattr__(self, '_key', key)

    def __setattr__(self, name, value):
        if name in ['_dataframe', '_key']:
            object.__setattr__(self, name, value)
        else:
            # 设置指定属性的 line_dash
            key = object.__getattribute__(self, '_key')
            df: dataframe = object.__getattribute__(self, '_dataframe')
            if key not in df._plotinfo.signallines:
                return
            if value not in df._plotinfo.lines and value not in FILED.OHLC:
                return
            setattr(df._plotinfo.signalstyle[key], name, value)
            setattr(df._plotinfo.signalstyle[key],
                    "overlap", value in FILED.OHLC)


@dataclass
class SignalStyle(DataSetBase):
    """### 信号指标线风格"""
    key: str
    color: str
    marker: str
    overlap: bool = True
    show: bool = True
    size: float | int = 12.


class SignalStyleType:
    """### 设置信号指标线风格代理类型"""

    def __init__(self, dataframe):
        # 使用 object.__setattr__ 避免触发自定义的 __setattr__
        object.__setattr__(self, '_dataframe', dataframe)

    def __getattr__(self, name) -> SignalStyle:
        # 代理属性获取到 dataframe 的 linstyle 字典
        return getattr(object.__getattribute__(self, '_dataframe')._plotinfo.signalstyle, name)

    def __setattr__(self, name, value):
        # 代理属性设置到 dataframe 的 linstyle 字典
        if name in object.__getattribute__(self, '_dataframe')._plotinfo.signalstyle:
            setattr(object.__getattribute__(
                self, '_dataframe')._plotinfo.signalstyle, name, value)


def default_signal_style(name: str, overlap: bool = True, show: bool = True, size=12.) -> SignalStyle:
    """### 默认信号指标风格

    Args:
        name (str): 信号线名称
        overlap (bool, optional): 是否显示. Defaults to True.
        show (bool, optional): 是否显示. Defaults to True.
        size (_type_, optional): 图标大小. Defaults to 12..

    Returns:
        SignalStyle
    """
    return long_signal_style(overlap, show, size) if name in ["long_signal", "exitshort_signal"] else short_signal_style(overlap, show, size)


def long_signal_style(overlap: bool = True, show: bool = True, size=12.) -> SignalStyle:
    """### 多头买入或空头平仓信号风格

    Args:
        overlap (bool, optional): 是否显示. Defaults to True.
        show (bool, optional): 是否显示. Defaults to True.
        size (_type_, optional): 图标大小. Defaults to 12..

    Returns:
        SignalStyle
    """
    return SignalStyle("low", "lime", "triangle", overlap, show, size)


def short_signal_style(overlap: bool = True, show: bool = True, size=12.) -> SignalStyle:
    """### 多头平仓或空头卖出信号风格

    Args:
        overlap (bool, optional): 是否显示. Defaults to True.
        show (bool, optional): 是否显示. Defaults to True.
        size (_type_, optional): 图标大小. Defaults to 12..

    Returns:
        SignalStyle
    """
    return SignalStyle("high", "tomato", "inverted_triangle", overlap, show, size)


@dataclass
class SpanStyle(DataSetBase):
    """### 水平线风格"""
    location: float = np.nan
    dimension: str = 'width'
    line_color: str | Colors = Colors.RGB666666  # '#666666'
    line_dash: str | LineDash = LineDash.dashed  # 'dashed'
    line_width: float = .8


def span_add(self: SpanList, other):
    if isinstance(other, (float, int)) and isfinite(other):
        other = SpanStyle(float(other))
    if isinstance(other, SpanStyle):
        if other.location not in self.locations:
            self.append(other)
    return self


def span_sub(self: SpanList, other):
    if isinstance(other, SpanStyle):
        other = other.location
    if isinstance(other, (float, int)) and isfinite(other):
        other = float(other)
        if other in self.locations:
            self.pop(self.locations.index(other))
    return self


class SpanList(list):
    __add__ = span_add
    __sub__ = span_sub
    __radd__ = span_add
    __rsub__ = span_sub
    __iadd__ = span_add
    __isub__ = span_sub

    @property
    def locations(self) -> list[float]:
        return [sapn.location for sapn in self]


@dataclass
class PlotInfo(DataSetBase, metaclass=Meta):
    """### 画图信息"""
    height: int = 150
    sname: str = "name"
    ind_name: str = "ind_name"
    lines: Lines[str] = field(
        default_factory=lambda: Lines("line"))
    signallines: list[str] = field(default_factory=list)
    category: CategoryString | str = Category.Any
    isplot: bool | dict[str, bool] = True
    overlap: bool | dict[str, bool] = False
    candlestyle: Optional[CandleStyle] = None
    linestyle: Addict[str, LineStyle] | dict[str,
                                             LineStyle] = field(default_factory=Addict)
    signalstyle: Addict[str, SignalStyle] | dict[str,
                                                 SignalStyle] = field(default_factory=Addict)
    spanstyle: SpanList[SpanStyle] | list[SpanStyle] = field(
        default_factory=SpanList)
    source: str = ""

    def __post_init__(self):
        assert isinstance(self.lines, Iterable), "lines为可迭代类型"
        self.lines = Lines(*self.lines)
        self.set_lines_plot()
        self.set_lines_overlap()
        if self.signallines:
            self.signalstyle.update(
                {string: default_signal_style(string) for string in self.signallines})
            self._set_signal_overlap()
        self.set_default_linestyle()
        [setattr(self.linestyle, line, LineStyle())
         for line in self.lines if line not in self.linestyle]
        self.set_spanstyle()
        self.category = CategoryString(self.category)

    def _set_signal_overlap(self):
        """当指标图没有画线时，禁止副图上显示，否则会有冲突"""
        for k in self.signalstyle.keys():
            if not self.isplot[k]:
                self.signalstyle[k].overlap = True

    def set_default_candles(self, value, height=300, category=Category.Candles, candlestyle=CandleStyle()) -> PlotInfo:
        """### 设置默认K线图样式"""
        self.height = height
        self.category = category
        self.candlestyle = candlestyle
        self.spanstyle = SpanList([SpanStyle(value)])
        return self

    def copy(self) -> PlotInfo:
        """### 复制"""
        values = {}
        for k, v in self.items():
            values.update({k: deepcopy(v)})
        return PlotInfo(**values)

    def set_spanstyle(self):
        """### 设置水平线样式"""
        span = self.spanstyle
        if isinstance(span, Iterable) and span and all([isinstance(s, SpanStyle)] for s in span):
            self.spanstyle = SpanList(list(span))
            return
        if isinstance(span, float):
            span = SpanList([SpanStyle(span),])
        elif isinstance(span, SpanStyle):
            span = SpanList([span,])
        else:
            span = SpanList([SpanStyle(np.nan),])
        self.spanstyle = span

    def set_default_linestyle(self):
        """### 设置默认指标线风格"""
        for line in self.lines:
            if line not in self.linestyle:
                self.linestyle.update({line: LineStyle()})

    def set_default_signalstyle(self):
        """### 设置默认信号指标线样式"""
        for line in self.signallines:
            if line not in self.signalstyle:
                self.signalstyle.update({line: default_signal_style(line)})

    def set_lines_plot(self, isplot=None):
        """### 设置指标线是否显示"""
        if isplot is None:
            isplot = self.isplot
        if len(self.lines) > 1:
            if isinstance(isplot, dict):
                isplot = [bool(isplot.get(
                    line, True)) for line in self.lines]
            elif isinstance(isplot, Iterable):
                isplot = list(isplot)
                isplot = len(self.lines) > len(isplot) and isplot + \
                    [True] * \
                    (len(self.lines) - len(isplot)
                     ) or isplot[:len(self.lines)]
                isplot = [bool(value) for value in isplot]
            else:
                isplot = [bool(isplot),]*len(self.lines)
            self.isplot = Addict(zip(self.lines, isplot))
        else:
            self.isplot = bool(isplot)

    def set_lines_overlap(self, overlap=None):
        """### 设置指标线是否为主图叠加"""
        if overlap is None:
            overlap = self.overlap
        if len(self.lines) > 1:
            default_overlap = self.category == "overlap" or overlap
            if isinstance(overlap, dict):
                overlap = [bool(overlap.get(
                    line, default_overlap)) for line in self.lines]
            elif isinstance(overlap, Iterable):
                overlap = list(overlap)
                overlap = len(self.lines) > len(overlap) and overlap + \
                    [default_overlap] * \
                    (len(self.lines) - len(overlap)
                     ) or overlap[:len(self.lines)]
                overlap = [bool(value) for value in overlap]
            else:
                overlap = [bool(overlap),]*len(self.lines)
            self.overlap = Addict(zip(self.lines, overlap))
        else:
            self.overlap = bool(overlap)

    @property
    def signal_style(self) -> Addict[str, SignalStyle]:
        return self.signalstyle

    @signal_style.setter
    def signal_style(self, value: SignalStyle):
        if self.signalstyle and isinstance(value, SignalStyle):
            key = value.key
            assert key in self.lines or key in FILED.OHLC, f"{key}需要设置在指标线{self.lines.values}或在K线图{FILED.OHLC.tolist()}上."
            if key in self.signallines:
                value.overlap = False
            else:
                value.overlap = True
            [setattr(self.signalstyle, k, value.copy())
                for k in self.signalstyle.keys()]

    @property
    def signal_key(self) -> dict[str, str]:
        return {k: v.key for k, v in self.signalstyle.items()}

    @signal_key.setter
    def signal_key(self, value):
        if value in self.lines or value in FILED.OHLC:
            for k in self.signalstyle.keys():
                setattr(self.signalstyle[k], "key", value)
                setattr(self.signalstyle[k], "overlap",
                        value not in self.signallines)

    @property
    def signal_show(self) -> dict[str, bool]:
        return {k: v.show for k, v in self.signalstyle.items()}

    @signal_show.setter
    def signal_show(self, value):
        [setattr(self.signalstyle[k], "show", bool(value))
         for k in self.signalstyle.keys()]

    @property
    def signal_color(self) -> dict[str, str]:
        return {k: v.color for k, v in self.signalstyle.items()}

    @signal_color.setter
    def signal_color(self, value):
        if value in Colors:
            [setattr(self.signalstyle[k], "color", value)
                for k in self.signalstyle.keys()]

    @property
    def signal_overlap(self) -> dict[str, bool]:
        return {k: v.overlap for k, v in self.signalstyle.items()}

    @signal_overlap.setter
    def signal_overlap(self, value):
        [setattr(self.signalstyle[k], "overlap", bool(value))
         for k in self.signalstyle.keys() if self.isplot[k]]

    @property
    def signal_size(self) -> dict[str, int]:
        return {k: v.size for k, v in self.signalstyle.items()}

    @signal_size.setter
    def signal_size(self, value):
        if isinstance(value, (int, float)):
            [setattr(self.signalstyle[k], "size", float(max(1., value)))
             for k in self.signalstyle.keys()]

    @property
    def line_style(self) -> Addict[str, LineStyle]:
        return self.linestyle

    @line_style.setter
    def line_style(self, value: LineStyle):
        if isinstance(value, LineStyle):
            [setattr(self.linestyle, k, value.copy())
             for k in self.linestyle.keys()]

    @property
    def line_dash(self) -> dict[str, str]:
        return {k: v.line_dash for k, v in self.linestyle.items()}

    @line_dash.setter
    def line_dash(self, value):
        if value in LineDash:
            [setattr(self.linestyle[k].line_dash, value)
             for k in self.linestyle.keys()]

    @property
    def line_width(self) -> dict[str, float]:
        return {k: v.line_width for k, v in self.linestyle.items()}

    @line_width.setter
    def line_width(self, value):
        if isinstance(value, (int, float)) and value > .0:
            [setattr(self.linestyle[k].line_width, float(value))
             for k in self.linestyle.keys()]

    @property
    def line_color(self) -> dict[str, Union[str, Colors]]:
        return {k: v.line_color for k, v in self.linestyle.items()}

    @line_color.setter
    def line_color(self, value):
        if value in Colors or (value and isinstance(value, str)):
            [setattr(self.linestyle[k].line_color, value)
             for k in self.linestyle.keys()]

    @property
    def span_style(self) -> SpanList[SpanStyle]:
        return self.spanstyle

    @span_style.setter
    def span_style(self, value):
        self.spanstyle += value

    @property
    def span_location(self) -> list[float]:
        return [span.location for span in self.spanstyle]

    @property
    def span_color(self) -> list[str]:
        return [span.line_color for span in self.spanstyle]

    @span_color.setter
    def span_color(self, value):
        if value in Colors or (value and isinstance(value, str)):
            [setattr(span, "line_color", value) for span in self.spanstyle]

    @property
    def span_dash(self) -> list[str]:
        return [span.line_dash for span in self.spanstyle]

    @span_dash.setter
    def span_dash(self, value):
        if value in LineDash:
            [setattr(span, "line_dash", value) for span in self.spanstyle]

    @property
    def span_width(self) -> list[str]:
        return [span.line_width for span in self.spanstyle]

    @span_width.setter
    def span_width(self, value):
        if isinstance(value, (float, int)) and value > 0.:
            [setattr(span, "line_width", float(value))
             for span in self.spanstyle]


@dataclass
class Multiply:
    """指标信息
    ---
    引用于多线程计算

    args:
    --
        >>>     func: Callable     :指标函数
            params: dict       :指标参数
            data: Any | BtData :指标数据

    example:
    --
    >>> self.ebsw, self.ma1, self.ma2, self.buy_signal, self.sell_signal, self.ema40 = self.multi_apply(
            Multiply(Ebsw, data=self.data),
            [self.data.sma, dict(length=20),],
            [self.data.sma, dict(length=30),],
            [self.test1.t1.cross_up, dict(b=self.test1.t2)],
            [self.test1.t1.cross_down, dict(b=self.test1.t2),],
            Multiply(PandasTa.ema, dict(length=40), data=self.data))
            Multiply(PandasTa.ema, dict(length=20), self.data)
    """
    func: Callable
    params: dict = field(default_factory=dict)
    data: Any = None

    @property
    def values(self) -> tuple[Callable, dict, BtData]:
        """返回计算指标信息"""
        return self.func, self.params, self.data


class _tq:
    @property
    def values(self) -> dict:
        return {k: v for k, v in vars(self).items()}


@dataclass
class tq_account(_tq):
    broker_id: str
    account_id: str
    password: str


@dataclass
class tq_auth(_tq):
    user_name: str
    password: str


def get_cycle(datetime: pd.Series) -> int:
    """获取时间序列周期

    Args:
        datetime (pd.Series): 时间序列

    Returns:
        int: 时间序列周期
    """
    if not pd.api.types.is_datetime64_any_dtype(
            datetime):
        return 0
    time_delta = list(Counter(pd.Series(
        datetime).diff().bfill().tolist()).keys())
    if not (time_delta and time_delta[0]):
        return 0
    _td = time_delta[0]
    if isinstance(_td, int):
        cycle = int(_td/1e9)
    else:
        cycle = _td.second
    return cycle


def ffillnan(arr: np.ndarray) -> np.ndarray:
    """过滤NAN值"""
    if len(arr.shape) > 1:
        arr = pd.DataFrame(arr)
    else:
        arr = pd.Series(arr)
    arr.fillna(method='ffill', inplace=True)
    return arr.values


def abc(df: pd.DataFrame, lim: float = 5., **kwargs) -> pd.DataFrame:
    """将K线范围压缩至lim个price_tick以内"""
    col = list(df.columns)
    if "price_tick" in kwargs:
        price_tick = kwargs.pop("price_tick")
    else:
        price_tick = df.price_tick.iloc[0] if 'price_tick' in col else 0.01
    col1 = FILED.OHLC.tolist()
    col2 = list(set(col)-set(col1))
    assert set(col).issuperset(col1)
    frame = pd.DataFrame(columns=col1)
    df1, df2 = df[col1], df[col2]
    for rows in df1.itertuples():
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
                    up = high-close
                    close = open+lim*price_tick
                    high = close+up
                else:
                    down = close-low
                    close = open-lim*price_tick
                    low = close-down
        else:
            if tick > lim:
                if close >= open:
                    up = high-close
                    close = open+lim*price_tick
                    high = close+up
                else:
                    down = close-low
                    close = open-lim*price_tick
                    low = close-down
        preclose = close
        frame.loc[index, :] = [open, high, low, close]
    frame = frame.astype(np.float64)
    return pd.concat([frame, df2], axis=1)[col]


@dataclass
class IndSetting(DataSetBase, metaclass=Meta):
    """### 框架指标元数据配置类（继承 DataSetBase，使用元类 Meta 管理）
        核心定位：统一存储指标的基础属性、数据维度、状态标识等元信息，为指标的创建、计算、绘图、数据联动提供标准化配置支撑，是框架内指标生命周期管理的核心数据载体

        核心作用：
        1. 指标身份标识：通过 `id` 实现指标唯一区分，避免多指标数据冲突
        2. 数据维度管理：记录指标的行/列数量（`v`/`h`）、列名映射（`line_filed`），确保数据结构一致性
        3. 状态标识控制：通过布尔属性标记指标的特殊类型（如是否为自定义数据 `iscustom`、是否为多维度 `isMDim`）
        4. 计算与联动配置：定义数据维度匹配规则（`dim_match`）、最新数据索引（`last_index`），支撑指标迭代计算


        字段说明（按功能分类）：
        一、指标唯一标识与基础状态
        1. id (BtID): 指标唯一标识对象（默认通过 `BtID` 工厂函数自动生成）
                    - 作用：区分不同指标实例，尤其在多指标并行计算、数据缓存时避免混淆
                    - 示例：两个相同参数的MA指标，通过不同 `id` 标记为独立实例

        2. is_mir (bool): MIR（多指标复用）标识（默认 False）
                        - 作用：标记指标是否支持多场景复用（如同一指标同时用于信号生成与风险控制）
                        - 说明：设为 True 时，指标会启用特殊的缓存与更新逻辑

        3. isha (bool): Heikin-Ashi（布林带K线）标识（默认 False）
                        - 作用：标记指标是否为布林带K线衍生数据（如 `ha` 方法生成的K线）
                        - 关联：与 `BtData` 的 `Heikin_Ashi_Candles` 属性联动，用于绘图样式适配

        4. isrl (bool): Linear Regression（线性回归）标识（默认 False）
                        - 作用：标记指标是否为线性回归衍生数据（如 `lrc` 方法生成的K线）
                        - 关联：与 `BtData` 的 `Linear_Regression_Candles` 属性联动，用于计算逻辑适配


        二、指标数据类型与场景标识
        5. ismain (bool): 主指标/主K线标识（默认 False）
                        - 作用：
                            - 对K线类数据：标记是否为主图K线（即显示在绘图区域的第一个图表）
                            - 对技术指标：标记是否为核心主指标（如策略依赖的关键均线）
                        - 影响：主指标会优先加载，且绘图时默认置于顶层

        6. isreplay (bool): 实时回放数据标识（默认 False）
                            - 作用：标记指标数据是否来自周期回放（如 `replay` 方法转换的低频数据）
                            - 影响：设为 True 时，指标计算会启用回放模式的时间戳同步逻辑

        7. isresample (bool): 重采样数据标识（默认 False）
                            - 作用：标记指标数据是否来自周期重采样（如 `resample` 方法转换的高频转低频数据）
                            - 影响：设为 True 时，指标会自动适配重采样后的时间粒度，避免计算偏差

        8. isindicator (bool): 技术指标标识（默认 True）
                            - 作用：区分指标数据与基础数据（如K线原始数据 `BtData` 设为 False）
                            - 影响：设为 False 时，会跳过指标专属的计算逻辑（如 `step` 方法调用）

        9. iscustom (bool): 自定义数据标识（默认 False）
                            - 作用：标记指标是否为用户手动创建的自定义数据（如通过整数长度初始化的全NaN序列）
                            - 影响：设为 True 时，数据会被存入 `_dataset.custom_object`，支持特殊的更新策略


        三、数据维度与结构配置
        10. isMDim (bool): 多维度标识（默认 True）
                        - 作用：标记指标是否为多维度数据（如 `dataframe` 多列指标设为 True，`series` 单列指标设为 False）
                        - 影响：多维度指标会启用列级独立配置（如每列单独设置线型）

        11. dim_match (bool): 维度匹配标识（默认 True）
                            - 作用：控制指标计算时是否强制与源数据维度一致（如K线数据行数）
                            - 场景：
                                - True：指标长度必须与源数据相同，避免数据错位
                                - False：允许指标长度小于源数据（如仅计算最新N期数据）

        12. v (int): 指标数据行数（默认 0）
                    - 作用：记录指标数据的时间维度长度（如100期数据则 `v=100`）
                    - 赋值：初始化时自动从输入数据的 `shape[0]` 提取，无需手动设置

        13. h (int): 指标数据列数（默认 0）
                    - 作用：记录指标数据的特征维度数量（如双均线指标 `h=2`）
                    - 赋值：初始化时自动从输入数据的 `shape[1]` 或 `lines` 长度提取

        14. last_index (int): 最新数据索引（默认 0）
                            - 作用：标记指标当前最新数据的位置（如第99期数据则 `last_index=99`）
                            - 用途：迭代计算时快速定位最新数据，避免全量遍历

        15. line_filed (list[str]): 指标列名映射列表（默认空列表）
                                    - 作用：存储指标列名的下划线前缀形式（如列名 "ma5" 对应 "_ma5"）
                                    - 用途：用于动态绑定 `Line` 实例到 `dataframe`/`series`，实现列级属性访问（如 `df._ma5`）


        使用说明：
        1. 自动初始化：通常无需用户手动创建 `IndSetting` 实例，指标类（如 `dataframe`/`series`/`BtData`）初始化时会自动生成
        2. 配置修改：可通过指标实例的 `_indsetting` 属性访问并修改配置（如 `df._indsetting.ismain = True` 设为主图指标）
        3. 关联逻辑：`IndSetting` 与 `PlotInfo`（绘图配置）联动，指标的 `isplot`/`overlap` 等可视化相关配置会同步到 `PlotInfo`


        示例：
        >>> #1. 访问指标的 IndSetting 配置
        >>> df = dataframe(raw_data, lines=["ma5", "ma10"])  # 自动生成 IndSetting 实例
        >>> print(df._indsetting.v)  # 输出指标行数（如 100）
        >>> print(df._indsetting.line_filed)  # 输出列名映射（如 ["_ma5", "_ma10"]）
        >>> 
        >>> #2. 修改配置
        >>> df._indsetting.ismain = True  # 将 dataframe 设为主图指标
        >>> df._indsetting.dim_match = False  # 允许指标长度与源数据不匹配
    """
    id: BtID = field(default_factory=BtID)  # 使用 default_factory
    is_mir: bool = False
    isha: bool = False
    isrl: bool = False
    ismain: bool = False
    isreplay: bool = False
    isresample: bool = False
    isindicator: bool = True
    iscustom: bool = False
    isMDim: bool = True
    dim_match: bool = True
    v: int = 0
    h: int = 0
    last_index: int = 0
    line_filed: list[str] = field(default_factory=list)


def get_category(category: Any) -> Optional[str]:
    """类别转换"""
    if isinstance(category, bool) and category:
        return 'overlap'
    elif isinstance(category, str):
        return category


def retry_with_different_params(params_list, times=3):
    """
    装饰器:使用retrying库,在每次重试时更换参数组合。

    参数:
        params_list (list): 参数列表

    返回:
        装饰后的函数，调用时会按顺序尝试参数列表中的参数
    """
    def decorator(func):
        # 将参数列表转换为迭代器
        params_iter = iter(params_list)

        @retry(
            stop_max_attempt_number=min(
                len(params_list), times),  # 最大尝试次数=参数个数
            retry_on_exception=lambda _: True,        # 对所有异常重试
            wrap_exception=True                       # 保留原始异常信息
        )
        def wrapped_function():
            try:
                current_params = next(params_iter)     # 获取下一个参数
            except StopIteration:
                raise ValueError("所有参数尝试均失败")

            try:
                # 根据参数类型调用函数
                return func(current_params)
            except Exception as e:
                print(f"参数 {current_params} 失败: {e}")
                raise  # 抛出异常以触发重试

        return wrapped_function
    return decorator


def check_type(datas):
    """检查数据是否为np.ndarray, pd.Series, pd.DataFrame类型"""
    if isinstance(datas, (list, tuple)):
        return all([isinstance(data, (np.ndarray, pd.Series, pd.DataFrame)) for data in datas])
    return isinstance(datas, (np.ndarray, pd.Series, pd.DataFrame))


def get_stats(func):
    """quantstats统计"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        return getattr(qs_stats, func_name)(*args, **kwargs)
    return wrapper


def qs_plots(func):
    """quantstats图表"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        return getattr(qs_plot, func_name)(*args, **kwargs)
    return wrapper


class Log(object):
    """
    Loggers:记录器,提供应用程序代码能直接使用的接口;
    Handlers:处理器,将记录器产生的日志发送至目的地;
    Filters:过滤器,提供更好的粒度控制,决定哪些日志会被输出;

    Formatters:格式化器,设置日志内容的组成结构和消息字段。
            %(name)s Logger的名字
            %(levelno)s 数字形式的日志级别  #日志里面的打印的对象的级别
            %(levelname)s 文本形式的日志级别 #级别的名称
            %(filename)s 调用日志输出函数的模块的文件名
            %(module)s 调用日志输出函数的模块名
            %(funcName)s 调用日志输出函数的函数名
            %(lineno)d 调用日志输出函数的语句所在的代码行
            %(asctime)s 字符串形式的当前时间。默认格式是 “2022-07-20 20:49:45,896”。逗号后面的是毫秒
            %(message)s用户输出的消息
    """
    __logger = None

    # 日志颜色
    log_colors_config = {

        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red'
    }

    @classmethod
    def get_logger(cls) -> logging.Logger:
        fileName = datetime.now().strftime('%Y-%m-%d') + '.log'
        project_directory = f'{BASE_DIR}/log/'
        if not os.path.exists(project_directory):
            os.makedirs(project_directory)
        file_handler = logging.FileHandler(
            filename=project_directory+fileName, encoding='utf8')
        # 创建logger记录器
        cls.__logger = logging.getLogger('minibt')
        # 控制台处理器
        console_handler = logging.StreamHandler()
        # 日志输出的级别设置
        cls.__logger.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.DEBUG)
        file_handler.setLevel(logging.INFO)
        # 日志文件输出
        file_formatter = logging.Formatter()  # fmt='%(message)s')
        # fmt='[%(asctime)s] %(filename)s -> %(funcName)s line:%(lineno)d [%(levelname)s] : %(message)s',
        # datefmt='%Y-%m-%d  %H:%M:%S')
        # 控制台输出
        console_formatter = colorlog.ColoredFormatter(
            # fmt='%(message)s',
            # fmt='%(log_color)s[%(asctime)s] %(filename)s -> %(funcName)s line:%(lineno)d [%(levelname)s] : %(message)s',
            # datefmt='%Y-%m-%d %H:%M:%S',
            log_colors=cls.log_colors_config
        )
        console_handler.setFormatter(console_formatter)
        file_handler.setFormatter(file_formatter)

        if not cls.__logger.handlers:
            cls.__logger.addHandler(console_handler)
            cls.__logger.addHandler(file_handler)
        console_handler.close()
        file_handler.close()

        return cls.__logger


Logger: logging.Logger = Log().get_logger()


class ArgumentParser:
    @staticmethod
    def parse_args(params: dict):
        """
        attr:
        -------
            params : dict

        NOTE:
        -------
            value不支持None
        """
        from ast import literal_eval
        from argparse import ArgumentParser
        parser = ArgumentParser()
        if params:
            for k, v in params.items():
                assert v is not None
                _type = literal_eval if isinstance(v, bool) else type(v)
                parser.add_argument(''.join(['-', k]), type=_type, default=v)

        return parser.parse_args()


def storeData(data, filename='examplePickle'):
    """读取pickle数据"""
    with open(filename, 'wb') as f:
        pickle.dump(data, f)


def loadData(filename='examplePickle'):
    """保存为pickle数据"""
    try:
        with open(filename, 'rb') as f:
            db = pickle.load(f)
        return db
    except EOFError:
        return None


def pandasdataframe(data: pd.DataFrame) -> pd.DataFrame:
    """将原始dataframe数据转为一定格式的内部数据
    时间包含date,其它的包括open,high,low,close,volume"""
    from pandas.api.types import is_datetime64_any_dtype, is_string_dtype, is_float_dtype
    data.columns = [col.lower() for col in data.columns]
    cols = data.columns
    datetime_list = [col for col in cols if is_datetime64_any_dtype(data[col])]
    if datetime_list:  # 按时间类型直接寻找时间序列
        datetime = data[datetime_list[0]]
    else:  # 在关键字符date中查找
        datetime_list = [col for col in cols if 'date' in col]
        if_fall = False
        if datetime_list:
            try:  # 将包含date字符的列进行时间转换
                datetime = data[datetime_list[0]]
                datetime = datetime.apply(time_to_datetime)
            except:
                if_fall = True
        if if_fall:  # 在列数据为字符串中查找
            datetime_list = [col for col in cols if is_string_dtype(data[col])]
            assert datetime_list, '找不到时间序列'
            datetime, if_break = None, False
            for date in datetime_list:
                try:  # 深度将字符串转为时间类型
                    datetime_ = data[date]
                    datetime = datetime_.apply(time_to_datetime)
                    if_break = True
                except:
                    ...
                if if_break:
                    break
            assert datetime is not None, '找不到时间序列'
    datas = [datetime,]
    try:
        datas.extend([data[[col for col in cols if (
            'vol' if 'vol' in filed else filed) in col][0]] for filed in FILED.OHLCV])
    except:  # 以open,high,low,close,volume首个字母来确定数据列
        datas_ = [data[[col for col in cols if col.startswith(filed)][0]] for filed in [
            'o', 'h', 'l', 'c', 'v']]
        assert all([is_float_dtype(data_) for data_ in datas_]
                   ), 'open,high,low,close,volume列中有非浮点类型数据'
        datas.extend(datas_)
        assert len(datas) < 6, '找不到时间序列'
    return pd.DataFrame(dict(zip(FILED.ALL, datas)))


class Actions(int, Enum):
    """动作
    -----

    >>> HOLD :持仓
        BUY :买入
        SELL :卖出
        Long_exit :多头平仓
        Short_exit :空头平仓
        Long_reversing :多头反手(卖出)
        Short_reversing :空头反手(买入)
    """
    HOLD = 0
    BUY = 1
    SELL = 2
    Long_exit = 3
    Short_exit = 4
    Long_reversing = 5
    Short_reversing = 6


class BtPosition(int):
    """策略内部持仓对象
    -----

    多头: BtPosition(1)

    无仓位: BtPosition(0)

    空头: BtPosition(-1)"""
    broker: Broker

    @property
    def value(self) -> int:
        return int(self)

    @property
    def pos(self) -> int:
        """
        仓位:正数为多头,负数为空头,0为无持仓
        ------
        """
        return self.broker._size*self.value

    @property
    def poses(self) -> list[int]:
        """逐笔合约成交手数
        -----"""
        return [size*self.value for size in self.broker._sizes]

    @property
    def pos_long(self) -> int:
        """
        多头持仓:正数为多头,0为无持仓
        ------
        """
        return self > 0 and self.pos or 0

    @property
    def pos_short(self) -> int:
        """
        空头持仓:正数为空头,0为无持仓
        ------
        """
        return self < 0 and self.pos or 0

    @property
    def open_price(self) -> int:
        """开仓价格"""
        return self.broker._open_price

    @property
    def open_price_long(self) -> float:
        """
        多头开仓价格:无持仓返回0.
        ------
        """
        return 0. if self <= 0 else self.broker._open_price

    @property
    def open_cost_long(self) -> float:
        """
        多头开仓成本价(包括开仓成本):无持仓返回0.
        ------
        """
        return 0. if self <= 0 else self.broker._cost_price

    @property
    def open_price_short(self) -> float:
        """
        空头开仓价格:无持仓返回0.
        ------
        """
        return 0. if self >= 0 else self.broker._open_price

    @property
    def open_cost(self) -> float:
        """
        开仓成本价
        ------
        """
        return self.broker._cost_price

    @property
    def open_cost_short(self) -> float:
        """
        空头开仓成本价(包括开仓成本):无持仓返回0.
        ------
        """
        return 0. if self >= 0 else self.broker._cost_price

    @property
    def float_profit(self) -> float:
        """
        持仓浮动盈亏:无持仓返回0.
        ------
        """
        return self.broker._float_profit

    @property
    def float_profit_long(self) -> float:
        """
        多头持仓浮动盈亏:无持仓返回0.
        ------
        """
        return self.float_profit if self > 0 else 0.

    @property
    def float_profit_short(self) -> float:
        """
        空头持仓浮动盈亏:无持仓返回0.
        ------
        """
        return self.float_profit if self < 0 else 0.

    @property
    def margin_long(self) -> float:
        """
        多头持仓保证金:无持仓返回0.
        ------
        """
        return self > 0 and self.broker._margin or 0.

    @property
    def margin_short(self) -> float:
        """
        空头持仓保证金:无持仓返回0.
        ------
        """
        return self < 0 and self.broker._margin or 0.

    @property
    def margin(self) -> float:
        """
        持仓保证金:无持仓返回0.
        ------
        """
        return self.broker._margin

    @property
    def step_margin(self) -> list[float]:
        """合约逐笔保证金
        ------"""
        return self.broker._step_margin

    def __call__(self, broker: Broker) -> Any:
        """绑定代理"""
        self.broker = broker
        return self


class TrainPosition(int, Enum):
    """强化学习动作"""
    SHORT = -1
    FLAT = 0
    LONG = 1


class PositionCreator:
    """账户内置仓位对象创建器
    -----"""
    @property
    def LONG(self):
        return BtPosition(1)

    @property
    def FLAT(self):
        return BtPosition(0)

    @property
    def SHORT(self):
        return BtPosition(-1)


@dataclass
class Quotes(DataSetBase):
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    price_tick: float
    volume_multiple: float
    tick_value: float

    @property
    def last_price(self):
        return self.close


def buy_create(datetime, price: float, size: float, comm: float, profit: float, add: bool, value: float):
    """生成买单创建信息
    Args:
        datetime: 交易时间（格式如 "2024-01-01 09:30:00"）
        price: 委托价格
        size: 委托数量（手数）
        comm: 手续费金额
        profit: 暂存参数（当前买单创建阶段暂未产生盈亏，可传0或NaN）
        add: 是否为加仓操作（True=加仓，False=初始开仓）
        value: 该笔委托的资金价值（通常为 价格×数量×合约乘数）
    Returns:
        str: 中文格式的买单创建信息字符串
    """
    return f"{datetime}：多头加仓，委托价格：{price}，委托数量：{size}，手续费：{comm}，资金价值：{value}" \
        if add else f"{datetime}：创建多头开仓委托，委托价格：{price}，委托数量：{size}，手续费：{comm}，资金价值：{value}"


def buy_executed(datetime, price: float, size: float, comm: float, profit: float, sub: bool, value: float):
    """生成买单成交（离场）信息
    Args:
        datetime: 成交时间（格式如 "2024-01-01 09:35:00"）
        price: 实际成交价格
        size: 成交数量（手数）
        comm: 实际产生的手续费金额
        profit: 该笔成交产生的盈亏金额（正数为盈利，负数为亏损）
        sub: 是否为减仓操作（True=减仓，False=全部平仓）
        value: 该笔成交的资金价值（通常为 成交价格×数量×合约乘数）
    Returns:
        str: 中文格式的买单成交（离场）信息字符串
    """
    return f"{datetime}：多头减仓成交，成交价格：{price}，成交数量：{size}，手续费：{comm}，盈亏金额：{profit}，资金价值：{value}" \
        if sub else f"{datetime}：多头平仓成交，成交价格：{price}，成交数量：{size}，手续费：{comm}，盈亏金额：{profit}，资金价值：{value}"


def sell_create(datetime, price: float, size: float, comm: float, profit: float, add: bool, value: float):
    """生成卖单创建信息
    Args:
        datetime: 交易时间（格式如 "2024-01-01 10:10:00"）
        price: 委托价格
        size: 委托数量（手数，空头委托通常用正数表示）
        comm: 手续费金额
        profit: 暂存参数（当前卖单创建阶段暂未产生盈亏，可传0或NaN）
        add: 是否为加仓操作（True=加仓，False=初始开仓）
        value: 该笔委托的资金价值（通常为 价格×数量×合约乘数）
    Returns:
        str: 中文格式的卖单创建信息字符串
    """
    return f"{datetime}：空头加仓，委托价格：{price}，委托数量：{size}，手续费：{comm}，资金价值：{value}" \
        if add else f"{datetime}：创建空头开仓委托，委托价格：{price}，委托数量：{size}，手续费：{comm}，资金价值：{value}"


def sell_executed(datetime, price: float, size: float, comm: float, profit: float, sub: bool, value: float):
    """生成卖单成交（离场）信息
    Args:
        datetime: 成交时间（格式如 "2024-01-01 10:15:00"）
        price: 实际成交价格
        size: 成交数量（手数，空头平仓通常用正数表示）
        comm: 实际产生的手续费金额
        profit: 该笔成交产生的盈亏金额（正数为盈利，负数为亏损）
        sub: 是否为减仓操作（True=减仓，False=全部平仓）
        value: 该笔成交的资金价值（通常为 成交价格×数量×合约乘数）
    Returns:
        str: 中文格式的卖单成交（离场）信息字符串
    """
    return f"{datetime}：空头减仓成交，成交价格：{price}，成交数量：{size}，手续费：{comm}，盈亏金额：{profit}，资金价值：{value}" \
        if sub else f"{datetime}：空头平仓成交，成交价格：{price}，成交数量：{size}，手续费：{comm}，盈亏金额：{profit}，资金价值：{value}"


class Base:
    """全局变量"""
    _isstart: bool = False
    _strategy_instances = StrategyInstances()
    _is_live_trading: bool = False  # 是否为真正交易
    _api: Optional[TqApi] = None
    tq: bool = False
    _base_dir: str = BASE_DIR
    _tqobjs: dict[str, TqObjs] = {}
    _tq_contracts_dict: dict = {}
    _datas: list[pd.DataFrame] = []


class Broker(Base):
    """### 框架交易代理核心类（继承 Base 类）
        核心定位：作为 `BtData` 与 `BtAccount` 之间的中间层，统一处理交易执行、仓位管理、手续费计算、保证金核算、盈亏统计等量化交易核心逻辑，是回测与模拟交易的核心控制单元

        核心职责：
        1. 交易生命周期管理：处理开仓（加仓）、平仓（减仓）、反手等完整交易流程，包含资金充足性校验
        2. 仓位与订单记录：通过队列维护逐笔交易详情（保证金、价格、手数、手续费），支持仓位均价、浮动盈亏计算
        3. 成本与风险控制：实现三种手续费计算模式，动态核算保证金（逐笔/总保证金），确保交易符合风险规则
        4. 账户联动更新：实时同步交易结果到关联的 `BtAccount`（如可用资金、总盈亏、累计手续费）
        5. 交易日志生成：支持开启交易日志（`islog=True`），自动生成中文格式的开仓/平仓记录


        核心特性：
        1. 灵活的手续费体系：
        - 支持三种手续费类型：按 tick 价值（`tick_commission`）、固定金额（`fixed_commission`）、按成交金额百分比（`percent_commission`）
        - 通过 `_setcommission` 自动绑定对应计算函数，交易时实时计算手续费
        2. 精细化仓位管理：
        - 依赖 `PositionCreator` 生成仓位状态（`LONG` 多头/`SHORT` 空头/`FLAT` 平仓）
        - 用 `LifoQueue`（后进先出队列）记录逐笔交易信息，支持部分平仓、逐笔保证金核算
        3. 实时盈亏与成本计算：
        - 动态计算开仓均价（`_open_price`）、持仓成本价（`_cost_price`）
        - 实时更新浮动盈亏（`_float_profit`）、累计盈亏（`cum_profits`）
        4. 资金风险校验：
        - 开仓/加仓前校验可用资金是否覆盖「保证金+手续费」，不足时触发交易失败（调用 `account._fail_to_trade`）
        - 支持保证金率（`margin_rate`）配置，动态计算所需保证金
        5. 多场景适配：
        - 与 `BtData` 强关联，从 `BtData` 获取当前价格（`current_close`）、时间（`current_datetime`）、合约信息（最小变动单位、乘数）
        - 与 `BtAccount` 实时联动，更新账户资金状态（可用资金、总手续费、总盈亏）


        初始化参数说明：
        Args:
            btdata (BtData): 关联的K线数据实例（必须包含合约信息、账户对象 `account`）
            **kwargs: 额外配置参数（优先级：kwargs > BtData策略配置 > 框架默认）：
                    - config (Config): 策略配置对象（默认从 `btdata.strategy_instance.config` 获取，无则使用框架默认 `btconfig`）
                    - margin_rate (float): 保证金率（默认从 config 获取，框架默认通常为 0.08，即8%）
                    - commission (dict): 手续费配置（键为 `commission_keys` 中的类型，值为费率/金额，默认从 config 获取）
                    - slip_point (float): 滑点（每笔交易额外成本，默认从 config 获取，单位：最小变动单位）
                    - islog (bool): 是否开启交易日志（默认 False，开启后生成中文交易记录）
                    - index: 账户中 broker 的索引标识（默认 None，用于多 broker 场景区分）


        核心属性说明（按功能分类）：
        一、基础关联与标识
        1. btdata (BtData): 关联的K线数据实例，提供价格、时间、合约信息（`price_tick`/`volume_multiple`）
        2. account (BtAccount): 关联的账户实例，用于更新资金状态（可用资金、总盈亏等）
        3. symbol (str): 合约名称（从 `btdata.symbol_info` 获取）
        4. __name__ (str): Broker 唯一名称（格式：`合约名_周期_broker`，如 "SHFE.rb2410_60_broker"）
        5. islog (bool): 交易日志开关（True 时生成开仓/平仓中文日志）

        二、手续费与滑点配置
        1. commission_keys (list[str]): 支持的手续费类型列表（["tick_commission", "fixed_commission", "percent_commission"]）
        2. commission (dict): 手续费配置字典（键为类型，值为对应参数，如 {"fixed_commission": 1.5} 表示每手固定1.5元）
        3. commission_value (float): 当前手续费类型的参数值（如固定手续费1.5元则为1.5）
        4. commission_func (Callable): 手续费计算函数（自动绑定，如 `_get_comm_fixed` 对应固定手续费）
        5. slip_point (float): 滑点（每笔交易额外增加的成本，单位：最小变动单位）

        三、保证金与成本
        1. margin_rate (float): 保证金率（如 0.08 表示需缴纳成交金额8%的保证金）
        2. _step_margin (list[float]): 逐笔交易保证金列表（从 `mpsc` 队列提取，每笔对应一笔开仓的保证金）
        3. _margin (float): 总保证金（所有未平仓交易的保证金总和）
        4. cost_price (float): 持仓成本价（逐笔开仓成本加权平均，含手续费）
        5. tick_value (float): 每 tick 价值（= `volume_multiple`，即1个最小变动单位对应的资金价值）

        四、仓位与交易数据
        1. poscreator (PositionCreator): 仓位创建器，生成 `LONG`/`SHORT`/`FLAT` 三种仓位状态
        2. position (BtPosition): 当前仓位状态（多头/空头/平仓）
        3. mpsc (LifoQueue): 逐笔交易队列（后进先出，存储每笔开仓的 [保证金, 开仓价, 手数, 手续费]）
        4. history_queue (Queue): 交易历史队列（存储所有已完成的交易记录）
        5. _size (int): 当前总持仓手数（所有未平仓交易的手数总和）
        6. _open_price (float): 平均开仓价（逐笔开仓价按手数加权平均）
        7. _float_profit (float): 当前浮动盈亏（按最新收盘价计算所有未平仓仓位的盈亏）

        五、盈亏与统计
        1. profit (float): 单笔交易盈亏（每次开仓/平仓后更新）
        2. cum_profits (float): 累计盈亏（所有交易的盈亏总和）
        3. length (int): 关联K线数据的总周期数（从 `btdata.length` 获取）


        核心方法说明：
        1. __init__(self, btdata: BtData, **kwargs):
        - 初始化 Broker 实例，关联 BtData 与 BtAccount，加载手续费、保证金、滑点等配置
        - 初始化仓位状态（默认平仓 `FLAT`）、交易队列（`mpsc`/`history_queue`）

        2. _setcommission(self, commission: dict):
        - 配置手续费类型与计算函数
        - 校验手续费类型是否在 `commission_keys` 中，无效时默认设为固定手续费（0元）
        - 绑定对应计算函数（如 `tick_commission` 绑定 `_get_comm_tick`）

        3. update(self, size: int, long: bool = True) -> None:
        - 核心交易执行方法，处理开仓、加仓、平仓、反手逻辑：
            1. 开仓（无持仓时）：校验可用资金，计算保证金与手续费，更新仓位与账户资金
            2. 平仓（持仓方向相反时）：支持部分/全部平仓，计算盈亏，同步账户资金，处理反手（若平仓后仍有剩余手数）
            3. 加仓（持仓方向相同时）：校验可用资金，追加保证金与手续费，更新逐笔交易队列
        - 开启日志时（`islog=True`），调用账户 `_optional_msg` 生成中文交易记录

        4. reset(self):
        - 重置 Broker 状态：恢复仓位为平仓（`FLAT`），清空逐笔交易队列（`mpsc`）与交易历史队列（`history_queue`）
        - 用于策略重新运行或多轮回测场景

        5. factor_analyzer(self, num: int):
        - 因子分析专用初始化方法：创建多组仓位记录、历史队列，预计算价格变动对应的资金价值（`diff_value`）
        - 用于多因子策略中多组仓位的并行回测与分析

        6. factor_update(self, index: Optional[int] = None, enter: bool = False, exit: bool = False, long=True):
        - 因子分析场景下的仓位与盈亏更新方法：根据开仓/平仓信号更新指定组的仓位，计算实时盈亏
        - 同步更新历史队列中的盈亏记录


        关键计算逻辑说明：
        1. 手续费计算：
        - 按 tick 价值：`_get_comm_tick` → 手续费 = 合约乘数 × (手续费参数 + 滑点)
        - 固定金额：`_get_comm_fixed` → 手续费 = 固定金额 + 滑点 × 合约乘数
        - 按百分比：`_get_comm_percent` → 手续费 = (成交价格 × 百分比参数 + 滑点) × 合约乘数
        2. 保证金计算：
        - 单笔保证金 = 成交价格 × 保证金率 × 合约乘数 × 手数
        - 总保证金 = 所有未平仓单笔保证金之和
        3. 浮动盈亏计算：
        - 多头仓位：(当前收盘价 - 开仓价) × 手数 × 合约乘数 - 手续费
        - 空头仓位：(开仓价 - 当前收盘价) × 手数 × 合约乘数 - 手续费


        使用示例：
        >>> #1. 关联 BtData 初始化 Broker
        >>> btdata = BtData(raw_kline_data)  # 已初始化的 BtData 实例
        >>> #配置固定手续费1.5元/手，保证金率8%，滑点1个tick
        >>> broker = Broker(
        ...     btdata,
        ...     commission={"fixed_commission": 1.5},
        ...     margin_rate=0.08,
        ...     slip_point=1,
        ...     islog=True  # 开启交易日志
        ... )
        >>> 
        >>> #2. 执行多头开仓（2手）
        >>> broker.update(size=2, long=True)  # 校验资金后开仓，生成"创建多头开仓委托"日志
        >>> 
        >>> #3. 执行多头加仓（1手）
        >>> broker.update(size=1, long=True)  # 同方向加仓，生成"多头加仓"日志
        >>> 
        >>> #4. 执行多头平仓（3手，全部平仓）
        >>> broker.update(size=3, long=False)  # 反向交易平仓，计算盈亏，生成"多头平仓成交"日志
        >>> 
        >>> #5. 查看当前状态
        >>> print(broker.position)  # 输出 FLAT（已平仓）
        >>> print(broker.cum_profits)  # 输出累计盈亏
        >>> print(broker._margin)  # 输出总保证金（平仓后为0）"""
    poscreator = PositionCreator()
    cols = ["total_profit", "positions",
            "sizes", "float_profits", "cum_profits"]
    commission_keys: list[str] = ["tick_commission",
                                  "fixed_commission", "percent_commission"]
    commission_value: float
    commission: dict[str, float]
    cost_fixed: float
    # 成本的最小波动单位形式
    cost_tick: float
    cost_percent: float
    # 成本的价值形式
    cost_value: float
    # 成本的价格形式
    cost_price: float

    def __init__(self, btdata: BtData, **kwargs):
        self.btdata = btdata
        try:
            config: Config = kwargs.pop(
                "config", btdata.strategy_instance.config)
        except:
            from .utils import Config as btconfig
            config = btconfig()
        self.account: BtAccount = btdata.account
        self.account.add_broker(self, kwargs.pop("index", None))
        self.margin_rate: float = kwargs.pop(
            "margin_rate", config.margin_rate)
        commission: dict = kwargs.pop(
            "commission", config._get_commission())
        self.slip_point: float = kwargs.pop(
            "slip_point", config.slip_point)
        self.islog: bool = kwargs.pop("islog", False)
        symbol_info = btdata.symbol_info
        self.symbol = symbol_info.symbol
        self.__name__ = f"{self.symbol}_{symbol_info.cycle}_broker"
        self.price_tick = symbol_info.price_tick
        self.volume_multiple = symbol_info.volume_multiple
        self.tick_value = symbol_info.volume_multiple
        self.close = self.btdata.current_close
        self.datetime = self.btdata.current_datetime
        self._setcommission(commission)
        self.profit = 0.
        self.cum_profits = 0.
        self.position: BtPosition = self.poscreator.FLAT(self)
        # 每笔交易的保证金margin，方向positon，手数size和成交价close的存放
        self.mpsc = LifoQueue()
        self.history_queue = Queue()
        self.length = self.btdata.length

    def factor_analyzer(self, num: int):
        self.positions: list[BtPosition] = [
            self.poscreator.FLAT(self) for _ in range(num)]
        self.last_trade_prices: list[float] = [0. for _ in range(num)]
        self.history_queues: LifoQueue = LifoQueue()
        self.diff_value = self.btdata.pandas_object.close.diff().values * \
            self.volume_multiple
        self.diff_value[0] = 0.

    @property
    def btindex(self) -> int:
        return self.btdata.btindex

    def reset(self):
        self.position: BtPosition = self.poscreator.FLAT(self)
        self.mpsc = LifoQueue()
        self.history_queue = Queue()

    def _setcommission(self, commission: dict):
        """设置手续费用"""
        if not commission:
            commission = {"fixed_commission": 0.}
        for key, value in commission.items():
            break
        if key not in self.commission_keys:
            commission = {"fixed_commission": 0.}
        for k in self.commission_keys:
            com_key = k.split("_")[0]
            if k == key:
                self.commission = commission
                self.commission_value = value
                self.commission_func = getattr(self, f"_get_comm_{com_key}")
                break

    @property
    def _sizes(self) -> list[int]:
        """逐笔合约成交手数"""
        return [0,] if self.mpsc.empty() else list(map(lambda x: x[2], self.mpsc.queue))

    @property
    def _size(self) -> int:
        """合约成交手数"""
        return sum(self._sizes)

    def commission_func(self, close) -> float:
        ...

    @cache
    def _get_comm_tick(self, close):
        return self.volume_multiple*(self.commission_value + self.slip_point)

    @cache
    def _get_comm_fixed(self, close):
        return self.commission_value+self.slip_point*self.volume_multiple

    def _get_comm_percent(self, close):
        return (self.commission_value*close+self.slip_point)*self.volume_multiple

    @property
    def LONG(self) -> BtPosition:
        return self.poscreator.LONG

    @property
    def SHORT(self) -> BtPosition:
        return self.poscreator.SHORT

    @property
    def FLAT(self) -> BtPosition:
        return self.poscreator.FLAT

    @property
    def _diff_price(self) -> Callable:
        return pos if self.position > 0 else neg

    @property
    def _open_price(self) -> float:
        return 0. if self.mpsc.empty() else sum(list(map(lambda x: x[1]*x[2], self.mpsc.queue)))/sum(list(map(lambda x: x[2], self.mpsc.queue)))

    @property
    def _cost_price(self) -> float:
        return 0. if self.mpsc.empty() else sum(list(map(lambda x: x[1]*x[2]-x[3], self.mpsc.queue)))/sum(list(map(lambda x: x[2], self.mpsc.queue)))

    @property
    def _float_profit(self) -> float:
        return sum(list(map(lambda x: (self._diff_price(self.current_close-x[1]))*x[2]*self.volume_multiple-x[3], self.mpsc.queue)))

    def __getmargin(self, close) -> float:
        """获取保证金"""
        return close*self.margin_rate*self.volume_multiple

    @property
    def _step_margin(self) -> list[float]:
        """合约逐笔保证金"""
        return [0,] if self.mpsc.empty() else list(map(lambda x: x[0], self.mpsc.queue))

    @property
    def _margin(self) -> float:
        """合约保证金"""
        return sum(self._step_margin)

    @property
    def current_close(self) -> float:
        return self.btdata.current_close

    @property
    def current_datetime(self) -> str:
        return self.btdata.current_datetime

    @property
    def current_diff_value(self) -> float:
        return self.diff_value[self.btindex]

    def factor_update(self, index: Optional[int] = None, enter: bool = False, exit: bool = False, long=True):
        close = self.current_close
        comm = 0.
        if index is not None:
            if enter or exit:
                comm = -self.commission_func(close)
            if enter:
                self.positions[index] = long and 1 or -1
            elif exit:
                self.positions[index] = 0
        history = []
        diff = 0.
        queue = self.history_queues.queue[-1]
        for i, (pos, value) in enumerate(zip(self.positions, queue)):
            if pos > 0:
                diff = self.current_diff_value
            elif pos < 0:
                diff = -self.current_diff_value
            value += diff
            if index == i:
                value += comm
            history.append(value)
        self.history_queues.put(history)

    def update(self, size: int, long: bool = True) -> None:
        """更新账户交易"""
        if self.btindex < self.length:
            close = self.current_close
            if self.islog:
                datetime = self.current_datetime
            current_position = self.position
            (pos_stats1, pos_stats2) = (self.LONG, self.SHORT) if long else (
                self.SHORT, self.LONG)
            available = self.account._available
            if not current_position:
                margin = size*self.__getmargin(close)
                comm = size*self.commission_func(close)
                if available < margin+comm:
                    return self.account._fail_to_trade(datetime)
                self.position = pos_stats1(self)
                self.profit = -comm
                # 逐笔记录
                self.mpsc.put([margin, close, size, comm])
                self.account._available -= margin+comm
                self.account._total_commission += comm
                self.account._total_profit -= comm
                if self.islog:
                    args = (datetime, close, size, comm,
                            0., False, self.account.balance)
                    self.account._optional_msg(
                        'buy_create' if long else 'sell_create', None, *args)
            elif current_position == pos_stats2:
                # 逐笔平仓
                value, comm, margin, total_close_size = 0., 0., 0., 0
                for _ in range(self.mpsc.qsize()):
                    if size > 0:
                        m, p, s, _ = self.mpsc.get()  # s:1
                        # 本次平仓手数,可能减仓
                        close_size = min(size, s)  # 1
                        # 累计平仓手数
                        total_close_size += close_size  # 1
                        # 剩余手数
                        size -= s  # 0
                        diff_price = close-p if not long else p-close
                        value += close_size*diff_price * \
                            self.btdata.volume_multiple
                        comm += close_size*self.commission_func(close)
                        if close_size == s:  # 本次全部平仓
                            margin += m
                        elif s > close_size:  # 部分平仓
                            out_margin = m*close_size/s
                            margin += out_margin
                            self.mpsc.put(
                                [m-out_margin, p, s-close_size, comm])
                            break
                # size>0:反手 size<0:减仓 size=0:清仓
                if size == 0:
                    self.position = self.FLAT(self)
                value -= comm
                self.account._available += value+margin
                self.profit = value
                self.account._total_commission += comm
                self.account._total_profit += value
                if self.islog:
                    args = (datetime, close, total_close_size,
                            comm, value, size < 0, self.account.balance)
                    self.account._optional_msg(
                        'sell_executed' if not long else 'buy_executed', value, *args)
                # 反手
                if size > 0:
                    margin = size*self.__getmargin(close)
                    comm = size*self.commission_func(close)
                    if available < margin+comm:
                        self.account._fail_to_trade(datetime)
                    else:
                        self.profit = -comm
                        self.position = pos_stats1(self)
                        self.mpsc.put([margin, close, size, comm])
                        self.account._available -= margin+comm
                        value -= comm
                        self.account._total_commission += comm
                        self.account._total_profit += value
                        if self.islog:
                            args = (datetime, close, size,
                                    comm, 0., False, self.account.balance)
                            self.account._optional_msg(
                                'buy_create' if long else 'sell_create', None, *args)
            # 加仓
            else:
                margin = size*self.__getmargin(close)
                comm = size*self.commission_func(close)
                if available < margin+comm:
                    return self.account._fail_to_trade(datetime)
                self.profit = -comm
                self.mpsc.put([margin, close, size, comm])
                self.account._available -= margin+comm
                self.account._total_commission += comm
                self.account._total_profit -= comm
                if self.islog:
                    args = (datetime, close, size, comm,
                            0., True, self.account.balance)
                    self.account._optional_msg(
                        'buy_create' if long else 'sell_create', None, *args)
            if self.profit:
                self.cum_profits += self.profit


@dataclass(eq=False)
class BtAccount(Base):
    """### 框架内置账户管理类（继承 Base 类，基于 dataclass 实现）
        核心定位：统一管理量化交易中的资金、持仓、盈亏、手续费等账户核心数据，关联多个交易代理（Broker），是回测与模拟交易的资金中枢

        核心职责：
        1. 资金统筹管理：实时维护账户权益、可用现金、总保证金，动态计算盈利率、风险度等关键财务指标
        2. 交易代理联动：支持添加、替换多个 Broker（对应不同合约/策略），同步所有 Broker 的保证金、盈亏数据
        3. 历史记录追踪：初始化并更新账户历史数据（权益、仓位、盈亏等），支持事后回测结果分析与导出
        4. 交易风险控制：校验交易资金充足性，触发交易失败提醒，避免账户透支
        5. 日志与信息输出：根据交易结果生成中文日志（盈利/亏损/失败），支持账户状态打印，便于调试与复盘


        核心特性：
        1. 多代理兼容：
        - 支持关联多个 Broker（通过 `add_broker` 方法），可同时管理多合约/多策略的交易，自动汇总所有 Broker 的保证金、盈亏
        - 支持 Broker 替换（指定 index 参数），适配策略调整或合约切换场景
        2. 资金动态核算：
        - 实时计算账户权益（`balance` = 可用现金 + 总保证金），反映账户实时净值
        - 自动汇总所有 Broker 的总保证金（`_margin`）、总盈亏（`total_profit`）、总手续费（`total_commission`）
        3. 风险指标实时计算：
        - 盈利率（`net`）：反映账户整体收益水平（(当前权益 - 初始现金) / 初始现金）
        - 风险度（`risk_ratio`）：衡量账户风险暴露（总保证金 / 账户权益），用于风险控制
        4. 历史数据完整追踪：
        - 初始化历史记录（`_init_history`），按周期存储账户关键数据（权益、仓位、盈亏等）
        - 支持导出历史结果（`get_history_results`）为 DataFrame，便于回测报告生成与可视化分析
        5. 交易日志分级：
        - 根据交易结果（盈利/亏损/失败）生成不同级别日志（info/error/warning），日志内容为中文，清晰易懂
        - 支持账户状态打印（`print` 属性），格式化输出当前资金、持仓、手续费等核心信息


        初始化参数说明（dataclass 字段）：
        Args:
            cash (float): 账户初始现金（必填），作为账户的初始资金池，将自动赋值给 `_available`（可用现金）和 `_balance`（初始权益）
            islog (bool): 是否开启账户日志（默认 False，开启后将打印交易结果、失败提醒等信息）
            train (bool): 是否为强化学习训练模式（默认 False，训练模式下可能跳过部分日志与打印逻辑，优化性能）


        核心属性说明（按功能分类）：
        一、基础资金数据
        1. cash (float): 账户初始现金（dataclass 初始化字段，不可修改）
        2. _available (float): 可用现金（初始等于 cash，随交易扣减/增加，用于开仓/加仓时的资金校验）
        3. _balance (float): 账户初始权益（固定为初始 cash，用于计算盈利率）
        4. balance (float, property): 当前账户权益（动态计算 = 可用现金 + 总保证金），反映账户实时净值
        5. available (float, property): 当前可用现金（对外暴露的只读属性，避免直接修改）

        二、盈亏与手续费统计
        1. _total_profit (float): 账户总盈亏（汇总所有 Broker 的盈亏，初始为 0）
        2. total_profit (float, property): 账户总盈亏（对外暴露的只读属性）
        3. _total_commission (float): 账户总手续费（汇总所有 Broker 的手续费，初始为 0）
        4. total_commission (float, property): 账户总手续费（对外暴露的只读属性）
        5. profit (float, property): 当前周期盈亏（汇总所有 Broker 当期的单笔盈亏，周期结束后重置）
        6. net (float, property): 账户盈利率（动态计算 = (当前权益 - 初始权益) / 初始权益，正数为盈利，负数为亏损）

        三、风险与保证金
        1. _margin (float, property): 账户总保证金（汇总所有 Broker 的未平仓仓位保证金，动态更新）
        2. risk_ratio (float, property): 账户风险度（动态计算 = 总保证金 / 当前权益，值越大风险越高）

        四、交易代理与历史
        1. brokers (list[Broker]): 关联的交易代理列表（初始为空，通过 `add_broker` 方法添加）
        2. num (int, property): 关联的 Broker 数量（动态计算 = 列表长度）
        3. history (list[pd.DataFrame]): 账户历史数据列表（每个元素对应一个 Broker 的历史记录，初始为 None，通过 `_init_history` 初始化）

        五、日志与提示
        1. islog (bool): 日志开关（dataclass 字段，控制是否打印交易日志）
        2. _fail (str): 交易失败提示文案（默认 "账户现金不足,交易失败!"，用于资金不足时的提醒）
        3. print (property): 账户状态打印属性（调用时格式化输出当前权益、现金、手续费等核心信息）


        核心方法说明：
        1. __post_init__(self):
        - dataclass 后置初始化方法，自动初始化账户核心数据：
            - 可用现金（`_available`）、初始权益（`_balance`）设为初始现金（`cash`）
            - 总盈亏（`_total_profit`）、总手续费（`_total_commission`）初始化为 0
            - 初始化 Broker 列表（`brokers`）、历史记录（`history`）为空

        2. add_broker(self, broker: Broker, index=None):
        - 添加或替换交易代理（Broker）：
            - 未指定 index：将 Broker 追加到 `brokers` 列表（支持多 Broker 管理）
            - 指定 index：替换列表中对应索引的 Broker（用于策略调整或合约切换）

        3. reset(self, length):
        - 重置账户状态（用于策略重新运行或多轮回测）：
            - 恢复可用现金（`_available`）、初始权益（`_balance`）为初始现金（`cash`）
            - 重置总盈亏（`_total_profit`）、总手续费（`_total_commission`）为 0
            - 调用所有关联 Broker 的 `reset` 方法，重置其仓位与交易队列
            - 初始化历史记录（调用 `_init_history`，长度为 `length`）

        4. _init_history(self, length: int):
        - 初始化账户历史记录（按周期预填充空数据）：
            - 普通模式：为每个周期预存空的账户历史（权益、仓位、盈亏等）
            - 因子分析模式（`_is_factor_analyzer=True`）：为每个 Broker 预存多组因子分析所需的空值
            - 作用：确保策略从非0索引开始时，历史数据长度与策略周期匹配

        5. update_history(self):
        - 按周期更新账户历史记录：
            - 为每个 Broker 记录当期的账户权益、仓位状态、单笔盈亏、累计盈亏
            - 重置所有 Broker 的当期单笔盈亏（`broker.profit`），避免跨周期重复统计

        6. get_history_results(self) -> list[pd.DataFrame]:
        - 导出账户历史记录为 DataFrame 列表：
            - 每个元素对应一个 Broker 的历史数据，列名由 Broker 的 `cols` 定义（如 total_profit/positions/sizes 等）
            - 历史数据未初始化时自动创建，支持事后回测结果分析与可视化

        7. get_profits(self) -> Series:
        - 提取第一个 Broker 的历史总盈亏序列（`total_profit` 列），用于快速获取核心回测结果（如收益曲线绘制）

        8. _optional_msg(self, op, profit, *args) -> None:
        - 生成交易日志（需 `islog=True` 生效）：
            - `op`：交易操作函数名（如 "buy_create"/"sell_executed"，对应中文日志生成函数）
            - `profit`：交易盈亏（None 时打印提醒日志，盈利时打印 info 日志，亏损时打印 error 日志）
            - `*args`：日志所需参数（时间、价格、手数等）

        9. _fail_to_trade(self, datetime: str = "") -> None:
        - 触发交易失败提醒（日志级别为 warning）：
            - 打印包含时间的失败文案（如 "2024-01-01 09:30:00 ：账户现金不足,交易失败!"）
            - 用于 Broker 校验资金不足时，向用户反馈交易失败原因


        使用示例：
        >>> # 1. 初始化账户（初始现金100000元，开启日志）
        >>> account = BtAccount(cash=100000.0, islog=True)
        >>> 
        >>> # 2. 关联 Broker（假设已初始化 btdata1、btdata2 两个 K线数据实例）
        >>> broker1 = Broker(btdata1, commission={"fixed_commission": 1.5})
        >>> broker2 = Broker(btdata2, commission={"percent_commission": 0.0001})
        >>> account.add_broker(broker1)  # 添加第一个 Broker
        >>> account.add_broker(broker2)  # 添加第二个 Broker
        >>> print(account.num)  # 输出 Broker 数量：2
        >>> 
        >>> # 3. 执行交易（通过 Broker 间接触发账户资金更新）
        >>> broker1.update(size=2, long=True)  # 多头开仓2手，账户可用现金扣减保证金+手续费
        >>> broker2.update(size=1, long=False)  # 空头开仓1手，账户可用现金扣减保证金+手续费
        >>> 
        >>> # 4. 查看账户当前状态
        >>> account.print  # 格式化输出：账户权益、现金、手续费、总盈亏、持仓保证金等
        >>> print(f"当前权益：{account.balance:.2f}")  # 输出当前账户权益
        >>> print(f"总盈亏：{account.total_profit:.2f}")  # 输出账户总盈亏
        >>> print(f"风险度：{account.risk_ratio:.4f}")  # 输出账户风险度
        >>> 
        >>> # 5. 重置账户（用于重新回测，假设策略周期长度为 200）
        >>> account.reset(length=200)
        >>> print(f"重置后可用现金：{account.available:.2f}")  # 输出 100000.0（恢复初始现金）
        >>> 
        >>> # 6. 导出历史记录（回测结束后）
        >>> history_dfs = account.get_history_results()
        >>> print(history_dfs[0].head())  # 查看第一个 Broker 的前5条历史数据"""
    cash: float
    # 是否打印
    islog: bool = False
    # 强化学习训练模式
    train: bool = False

    def __post_init__(self):
        self._available = self.cash
        self._balance = self.cash
        self._total_profit = 0.
        self._total_commission = 0.
        self.brokers: list[Broker] = []
        self.history = None
        self._fail: str = '账户现金不足,交易失败!'
        self._is_factor_analyzer: bool = False

    def add_broker(self, broker: Broker, index=None):
        if index is not None:
            # 替换broker
            self.brokers[index] = broker
            return
        self.brokers.append(broker)

    def reset(self, length):
        """broker重置"""
        self._available = self.cash
        self._balance = self.cash
        self._total_profit = 0.
        self._total_commission = 0.
        self.history = None
        assert self.brokers, "无法重置"
        [broker.reset() for broker in self.brokers]
        self._init_history(length)

    @property
    def num(self) -> int:
        """broker数量"""
        return len(self.brokers)

    @property
    def balance(self) -> float:
        """权益"""
        return self._available+self._margin

    @property
    def available(self) -> float:
        """现金"""
        return self._available

    @property
    def total_profit(self) -> float:
        """总盈亏"""
        return self._total_profit

    @property
    def total_commission(self) -> float:
        """总手续费用"""
        return self._total_commission

    @property
    def _margin(self) -> float:
        """总保证金"""
        return sum([broker._margin for broker in self.brokers])

    @property
    def profit(self) -> float:
        """当前盈亏"""
        return sum([broker.profit for broker in self.brokers])

    def update_history(self):
        [broker.history_queue.put([self.balance, broker.position.value,
                                   broker.position.pos, broker.profit, broker.cum_profits]) for broker in self.brokers]
        for broker in self.brokers:
            broker.profit = 0.

    def _init_history(self, length: int):
        """策略索引从非0开始时初始化历史信息"""
        if length > 0:
            if self._is_factor_analyzer:
                for _ in range(length):
                    for broker in self.brokers:
                        broker.history_queues.put([0.,]*len(broker.positions))
                return
            for _ in range(length):
                self.update_history()

    def get_history_results(self) -> list[pd.DataFrame]:
        if not self.history:
            if self._is_factor_analyzer:
                self.history = [pd.DataFrame(
                    broker.history_queues.queue, columns=[f"values{i}" for i in len(broker.positions)]) for broker in self.brokers]
            else:
                self.history = [pd.DataFrame(
                    broker.history_queue.queue, columns=broker.cols) for broker in self.brokers]
        return self.history

    def get_profits(self) -> pd.Series:
        if self.history:
            return self.history[0]["total_profit"]

    @property
    def net(self) -> float:
        """盈利率"""
        return (self.balance-self._balance)/self._balance

    @property
    def risk_ratio(self) -> float:
        """风险度(风险度 = 保证金 / 账户权益)"""
        return self._margin/self.balance

    def _optional_msg(self, op, profit, *args) -> None:
        """操作信息"""
        if profit is None:
            return Logger.warning(eval(op)(*args))
        return Logger.error(eval(op)(*args)) if profit < 0. else Logger.info(eval(op)(*args))

    def _fail_to_trade(self, datetime: str = "") -> None:
        """交易失败提醒"""
        # print(list(self.mps[0].queue), self.available)
        Logger.warning(
            f'{datetime} :{self._fail}' if datetime else self._fail)

    @property
    def print(self):
        """账户打印"""
        pprint({"账户权益": self.balance, "现金": self.available, "手续费": self.total_commission, "收益": self.total_profit, "mpsc":
               [[] if broker.mpsc.empty() else broker.mpsc.queue for broker in self.brokers]}, sort_dicts=False)  # depth=2, width=200, sort_dicts=False)


def ispandasojb(data) -> bool:
    """是否为pandas对象"""
    if isinstance(data, (list, tuple)):
        return all([isinstance(d, (pd.DataFrame, pd.Series)) for d in data])
    return isinstance(data, (pd.DataFrame, pd.Series))


def _set_slice(keys: tuple, index: int, lines: list[str]) -> tuple[bool, tuple[Any]]:
    """设置切片"""
    _keys = []
    for i, key in enumerate(keys):
        if isinstance(key, int):
            _keys.append(key if i else index-key)
        elif isinstance(key, str):
            assert i, '第一个切片不能为字符串'
            _keys.append(lines.index(key))
        elif isinstance(key, Iterable):
            new_ls = [(k if isinstance(k, int) else lines.index(k)) if i else
                      (index-key) for k in key]
            _keys.append(new_ls)
        elif isinstance(key, slice):
            if i:
                _keys.append(key)
            else:
                start, stop, step = key.start, key.stop, key.step
                _keys.append(key if i else slice(
                    index-stop+1, index-start+1, step))
        else:
            raise KeyError('参数有误')
    if len(_keys) == 1:
        _keys.append(slice(None, None, None))
    return isinstance(_keys[0], int), _keys


@dataclass
class SymbolInfo(DataSetBase):
    symbol: str
    duration: int
    price_tick: float
    volume_multiple: float

    @property
    def cycle(self) -> int:
        return self.duration


@dataclass
class DataFrameSet(DataSetBase):
    """数据集
    pandas_object: Optional[pd.DataFrame] btdata对应的pandas对象
    kline_object: Optional[pd.DataFrame] btdata蜡烛图pandas对象
    source_object: Optional[pd.DataFrame] 在创建btdata最初的pandas对象"""
    pandas_object: Union[pd.DataFrame, pd.Series, corefunc]
    kline_object: Optional[Union[pd.DataFrame, corefunc]] = None
    source_object: Optional[Union[pd.DataFrame, pd.Series, corefunc]] = None
    conversion_object: Optional[Union[pd.DataFrame,
                                      pd.Series, corefunc]] = None
    custom_object: Optional[Union[pd.DataFrame, pd.Series, corefunc]] = None
    tq_object: Optional[Union[pd.DataFrame, pd.Series, corefunc]] = None
    upsample_object: Optional[Union[Line, series, dataframe]] = None


def default_symbol_info(data: pd.DataFrame) -> dict:
    cycle = data.datetime.diff().apply(lambda x: x.seconds).values.min()
    return SymbolInfo("symbol", cycle, 0.01, 1.).vars


def set_property(cls, attr: str):
    exec(f"def get_{attr}(self):return getattr(self,'_{attr}')")
    getf = eval(f"get_{attr}")
    setattr(cls, f"{attr}", property(getf))


def _same_lenght_bool(k: Iterable, v: int) -> list[bool]:
    last_index = len(k)-1
    return [bool(k[min(i, last_index)]) for i in range(v)]


@dataclass
class TqObjs(Base):
    symbol: str
    Quote: Optional[Quote] = None
    Position: Optional[Position] = None
    TargetPosTask: Optional[Union[TargetPosTask, Callable]] = None

    def __post_init__(self):
        assert self._api
        assert not self._api._loop.is_closed(), "请连接天勤API"
        self.Quote = self._api.get_quote(self.symbol)
        self.Position = self._api.get_position(self.symbol)
        self.TargetPosTask = TargetPosTask(self._api, self.symbol)


class PandasObject(metaclass=Meta):
    DataFrame = pd.DataFrame
    Series = pd.Series


def np_random(seed: Optional[int] = None) -> tuple[np.random.Generator, Any]:
    """Generates a random number generator from the seed and returns the Generator and seed.

    Args:
        seed: The seed used to create the generator

    Returns:
        The generator and resulting seed

    Raises:
        Error: Seed must be a non-negative integer or omitted
    """
    if seed is not None and not (isinstance(seed, int) and 0 <= seed):
        raise Exception(
            f"Seed must be a non-negative integer or omitted, not {seed}")

    seed_seq = np.random.SeedSequence(seed)
    np_seed = seed_seq.entropy
    rng = np.random.Generator(np.random.PCG64(seed_seq))
    return rng, np_seed


class OpConfig:
    def __new__(cls,
                worker_num: int = None,
                MU: int = 80,
                population_size: int = 100,
                ngen_size: int = 20,
                cx_prb: float = 0.9,
                show_bar: bool = True,
                ) -> dict:
        return dict(
            worker_num=worker_num,
            MU=MU,
            population_size=population_size,
            ngen_size=ngen_size,
            cx_prb=cx_prb,
            show_bar=show_bar
        )


class OptunaConfig:
    def __new__(cls,
                n_trials: int | None = 10,
                timeout: float | None = None,
                n_jobs: int | str = 1,
                catch=(),
                callbacks=None,
                gc_after_trial: bool = False,
                show_progress_bar: bool = True,

                storage=None,
                sampler: Literal['BaseSampler', 'GridSampler', 'RandomSampler', 'TPESampler', 'CmaEsSampler',
                                 'PartialFixedSampler', 'NSGAIISampler', 'NSGAIIISampler', 'MOTPESampler',
                                 'QMCSampler', 'BruteForceSampler', 'IntersectionSearchSpace',
                                 'intersection_search_space'] = 'NSGAIISampler',
                pruner: Literal['BasePruner', 'MedianPruner', 'NopPruner', 'PatientPruner',
                                'PercentilePruner', 'SuccessiveHalvingPruner', 'HyperbandPruner',
                                'ThresholdPruner'] = 'HyperbandPruner',
                study_name='test_optuna',
                direction=None,
                load_if_exists=False,
                directions=None,
                logging: bool = False,
                optunaplot: Literal['plot_rank', 'plot_pareto_front',
                                    'plot_param_importances'] = 'plot_pareto_front',
                ) -> tuple[dict]:
        return dict(
            n_trials=n_trials,
            timeout=timeout,
            n_jobs=n_jobs,
            catch=catch,
            callbacks=callbacks,
            gc_after_trial=gc_after_trial,
            show_progress_bar=show_progress_bar,), dict(
            storage=storage,
            sampler=sampler,
            pruner=pruner,
            study_name=study_name,
            direction=direction,
            load_if_exists=load_if_exists,
            directions=directions,
            logging=logging,
            optunaplot=optunaplot,
        )
