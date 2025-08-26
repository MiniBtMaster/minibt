from __future__ import annotations
from .utils import \
    (TYPE_CHECKING, PlotInfo, np, pd, wraps, Union, Callable, BtID, retry_with_different_params,
     partial, Iterable, Lines, Base, Meta, check_type, LineStyle, IndSetting, SymbolInfo, Broker,
     DataFrameSet, Optional, Addict, Any, cachedmethod, attrgetter, common, LineDash,
     Multiply, get_lennan, BlockPlacement, ispandasojb, pandas_method, reduce, Literal, LineStyleType,
     RandomState, Category, SIGNAL_Str, set_property, Cache, _assign, FILED, isfinite, SignalStyleType,
     default_symbol_info, CandlesCategory, Quotes, Quote, BtAccount, TqAccount, Position,
     BtPosition, getsourcelines, Enum, StrategyInstances, TPE, TqObjs, SpanStyle, default_signal_style, DataSetBase,
     time_to_datetime, PandasObject, Rolling, rolling_method, CandleStyle, SignalStyle, LineAttrType,
     dataclass, DefaultIndicatorConfig, SignalAttrType, CategoryString, SpanList, Sequence)
# _set_slice,, _same_lenght_bool, cache
from pandas.core.indexing import _iLocIndexer, _LocIndexer, _AtIndexer, _iAtIndexer
import os
os.environ["SHINNY_SILENT"] = "1"


if TYPE_CHECKING:
    from .constant import *
    from .strategy.strategy import Strategy
    from .core import CoreFunc
    from .bt import Bt

    class corefunc:
        """函数引导，无实际用处"""

        def __getattr__(self, name: str) -> CoreFunc: ...

# 保存原始函数（可选，用于后续恢复）
original_apply_if_callable = common.apply_if_callable


def apply_if_callable_(maybe_callable, obj, **kwargs):
    """自定义的apply_if_callable函数"""
    if callable(maybe_callable):
        # 你的特殊判断逻辑
        if type(maybe_callable) in BtIndType:
            return maybe_callable
        return maybe_callable(obj, ** kwargs)
    return maybe_callable


# 替换pandas模块中的函数
common.apply_if_callable = apply_if_callable_


def pandas_to_btind(data: Union[pd.Series, pd.DataFrame], key, length, kwargs: Addict):
    """pandas数据转换为指标数据"""
    data = data.copy(deep=True)
    dim_match = length == len(data)
    id = BtID(**kwargs.id)
    if not dim_match:
        data.reset_index(drop=True, inplace=True)
    if isinstance(key, slice):
        key = kwargs.lines
    if len(data.shape) == 1 or data.shape[1] == 1:
        data = data.values
        if isinstance(key, (list, tuple)):
            key = key[0]
        if len(data.shape) != 1:
            data = data[:, 0]
        sname = key
        ind_name = key
        lines = [key,]
        isplot = kwargs.isplot
        if isinstance(isplot, dict):
            isplot = isplot.get(key, True)
        overlap = kwargs.overlap
        if isinstance(overlap, dict):
            overlap = overlap.get(key, False)
        config = DefaultIndicatorConfig(
            id,
            sname,
            ind_name,
            lines,
            None,
            isplot,
            kwargs.ismain,
            kwargs.isreplay,
            kwargs.isresample,
            overlap,
            True,
            False,
            dim_math=dim_match,
        )
        return series(data, **config.to_dict())
    else:
        lines = key
        isplot = kwargs.isplot
        if isinstance(isplot, dict):
            new_isplot = isplot.copy()
            for k, _ in isplot.items():
                if k not in key:
                    new_isplot.pop(k)
            isplot = new_isplot
        overlap = kwargs.overlap
        if isinstance(overlap, dict):
            new_overlap = overlap.copy()
            for k, _ in overlap.items():
                if k not in key:
                    new_overlap.pop(k)
            overlap = new_overlap
        config = DefaultIndicatorConfig(
            id,
            kwargs.sname,
            kwargs.ind_name,
            lines,
            None,
            isplot,
            kwargs.ismain,
            kwargs.isreplay,
            kwargs.isresample,
            overlap,
            True,
            False,
            dim_math=dim_match,
        )
        return dataframe(data.values, **config.to_dict())


def set_lines(btind: Union[BtData, dataframe], key):
    """多维指标数据更改后,内置Line数据同步更改"""
    if isinstance(key, slice):
        data = btind.pandas_object.values
        for i, line in enumerate(btind._indsetting.line_filed):
            line = getattr(btind, line)
            btind._set_data_object(line, data[:, i])
        return
    if isinstance(key, str):
        key = [key,]
    for k in key:
        line = f"_{k}"
        data = btind.pandas_object[k].values
        if line in btind._indsetting.line_filed:
            line = getattr(btind, line)
            btind._set_data_object(line, data)
        else:
            btind._indsetting.line_filed.append(line)
            btind.lines.append(k)
            if isinstance(btind.isplot, dict):
                btind.isplot.update({k: True})
            if isinstance(btind.overlap, dict):
                btind.overlap.update({k, False})
            setattr(btind, line, Line(btind, data,
                    iscustom=btind.iscustom, id=btind.id, sname=k,
                    ind_name=btind.ind_name, lines=[
                        k,], category=btind.category,
                    isplot=btind.isplot[k
                                        ], ismain=btind.ismain, isreplay=btind.isreplay,
                    isresample=btind.isresample, overlap=btind.overlap[k]))
            # 邦定property函数,dataframe每列返回的是Line指标数据
            set_property(btind.__class__, btind._indsetting.line_filed[-1])


class seriesType:
    def __init__(self, dataframe: dataframe):
        self.dataframe = dataframe

    def __getattr__(self, key) -> series:
        id = self.dataframe.id.copy()
        sname = key
        ind_name = key
        lines = Lines(key)
        isplot = self.dataframe.isplot
        if isinstance(isplot, dict):
            isplot = isplot.get(key, True)
        overlap = self.dataframe.overlap
        if isinstance(overlap, dict):
            overlap = overlap.get(key, False)
        config = DefaultIndicatorConfig(
            id,
            sname,
            ind_name,
            lines,
            None,
            isplot,
            self.dataframe.ismain,
            self.dataframe.isreplay,
            self.dataframe.isresample,
            overlap,
            True,
            False,
        )
        return series(getattr(self.dataframe, key).values, **config.to_dict())


class IndexerBase:
    obj: IndicatorsBase

    def __init__(self, name: str, obj: IndicatorsBase):
        super().__init__(name, obj)

    def __getitem__(self, key) -> Union[Line, series, dataframe, BtData, Any]:
        """处理索引操作并返回结果"""
        data = super().__getitem__(key)  # 调用父类索引逻辑
        if isinstance(data, (pd.Series, pd.DataFrame)):
            if isinstance(key, tuple) and len(key) > 1:
                key = key[1]
                if isinstance(key, int):
                    key = self.obj.lines[key]
            return pandas_to_btind(data, key, self.obj.V, self.obj.get_indicator_kwargs(isindicator=True))
        return data

    def __setitem__(self, key, value):
        result = super().__setitem__(key, value)
        if self.obj._dataset.upsample_object is not None:
            setattr(self.obj.strategy_instance, self.obj._upsample_name, self.obj.upsample(
                reset=True))
        if self.obj.isMDim:
            set_lines(self.obj, key)
        return result


# 自定义索引器类

class iLocIndexer(IndexerBase, _iLocIndexer):
    ...


class LocIndexer(IndexerBase, _LocIndexer):
    ...


class AtIndexer(IndexerBase, _AtIndexer):
    ...


class iAtIndexer(IndexerBase, _iAtIndexer):
    ...


def tobtind(lines: list[str] | dict[str, bool] | None = None, overlap: dict | bool = False, isplot: bool = True, category: str | None = None, **kwargs_):
    """指标装饰器
    --------

    Note:
    --------
        自定义指标lib为None

    Args:
    --------
        >>> lines (List[str], optional): dataframe指标需要设置列名lines,series指标默认为None. Defaults to None.
            overlap (dict | bool) 是否为主图指标. Defaults to False.
            isplot (bool): 是否画图. Defaults to True.
            ismain (bool, optional): 是否为主周期指标(多周期指标在主周期中显示). Defaults to False.
            category (Optional[str], bool): 'overlap':主图叠加,'candles':蜡烛图,None,无类别,默认副图,True:为'overlap'. Defaults to False.

    """
    _isplot = isplot
    _lines = lines
    _overlap = overlap
    _category = category
    _lib = kwargs_.pop('lib', "pta")
    _isindicator = kwargs_.pop('isindicator', False)
    _index = kwargs_.pop('_multi_index', None)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs) -> Union[series, dataframe]:
            # 指标名称
            func_name = func.__name__
            # 数据源,指标计算的数据对象
            source: Union[Line, series, dataframe, BtData] = args[0]
            source_type = type(source)
            if source_type in IndicatorClass:
                # DataFrameIndicators,SeriesIndicators 数据, 含PandasTa,BtInd,TqFunc,TaLib,FinTa,AutoTrader,SignalFeatures
                source = source._df  # Btdata数据
                source_type = type(source)

            # 指标属性
            source_indsetting = source.get_indicator_kwargs(isindicator=True) if hasattr(
                source, "_indsetting") else {}

            # 是否为自定义指标
            myself = kwargs_.pop('myself', False)
            if myself:
                func_name = myself
            else:
                # if source_type == BtData and not source.follow:
                #     source = source.kline_object
                # elif source_type == Line and not source.follow:
                #     source = source.source.kline_object
                # elif hasattr(source, "_dataset"):
                #     source = source.pandas_object
                # elif hasattr(source, "_df"):
                #     source = source._df
                func_name = f"{_lib}_{func_name}"
                ind_func: Callable = getattr(getattr(source, "ta"), func_name)

            category = kwargs.pop('category', _category)
            isplot = kwargs.pop('isplot',  _isplot)
            ismain = kwargs.pop('ismain', False)
            lines = kwargs.pop('lines',  _lines)
            light_chart = kwargs.pop("light_chart",  False)
            index = kwargs.get("_multi_index",  _index)
            isindicator = kwargs.get("isindicator",  _isindicator)
            iscustom = kwargs.get("iscustom",  False)
            # 继承id
            id = kwargs.get("id", source_indsetting.get("id", BtID()))

            isresample = source_indsetting.get(
                "isresample", kwargs.get("isresample", False))
            # if hasattr(source, "ind_setting") and not source.ind_setting.isindicator:
            #     # BtData继承isresample和isreplay
            #     isreplay = kwargs.get("isreplay", source_indsetting.get(
            #         "isreplay", default_isreplay))  # 是否为实时数据
            # else:
            #     isreplay = kwargs.get("isreplay", default_isreplay)
            isreplay = source_indsetting.get(
                "isreplay", kwargs.get("isreplay", False))

            ind_params = list(args[1:])  # 指标参数

            if isreplay:
                num_cols = len(_lines) if _lines else 1
                nan_data = [np.nan]*num_cols if _lines else np.nan
                replay_length = 100
            #     # 调整数据长度
                if kwargs:
                    for _, v in kwargs.items():
                        if isinstance(v, int):
                            replay_length = max(replay_length, v)
                v = [arg for arg in ind_params if isinstance(arg, int)]
                if v:
                    replay_length = max(v)
                else:
                    replay_length = 100
            #     # 重放数据核心计算函数
                length_ls = [replay_length + 100 *
                             i for i in range(1, int(len(source)/100))]

                # task_params = kwargs.copy()
                # task_params.update(dict(
                #     start_length=replay_length,
                #     ind_params=ind_params,
                #     func_name=func_name,
                #     myself=myself,
                # ))

                # class Task(QuantTask):
                #     def run(self):
                #         params = self.params.copy()
                #         start_length = params.pop("start_length")
                #         ind_params = params.pop("ind_params")
                #         func_name = params.pop("func_name")
                #         myself = params.pop("myself")
                #         if len(self.data) < start_length:
                #             return np.nan
                #         if myself:
                #             _args = [self.data,]
                #             _args.extend(ind_params)
                #             result = func(*_args, **params).values[-1]
                #         else:
                #             result = getattr(getattr(self.data, "ta"), func_name)(
                #                 *ind_params, **params).values[-1]
                #         return {
                #             'task_id': self.task_id,
                #             'result': result,
                #         }

                def core(index=0, data_=None, length=100):
                    if len(data_) < length:
                        return index, nan_data
                    if myself:
                        _args = [data_,]
                        _args.extend(ind_params)
                        return index, func(*_args, **kwargs).values[-1]
                    else:
                        # print(type(data_), hasattr(data_, "ta"))
                        return index, getattr(getattr(data_, "ta"), func_name)(*ind_params, **kwargs).values[-1]
                        # return index, getattr(data_.btta, func_name)(*ind_params, **kwargs).values[-1]

                klines = source.source._replay_datas(source.ind_name) if type(
                    source) == Line else source._replay_datas()
                # from .QuantMultiProcessFramework import QuantMultiProcessFramework, ReplayTask
                # framework = QuantMultiProcessFramework(num_workers=4)
                # tasks = QuantMultiProcessFramework.create_tasks_from_datas(
                #     func=None,
                #     data_list=klines,
                #     params=task_params,
                #     task_class=ReplayTask
                # )
                # ind_data = np.array(framework.run_tasks(tasks))

                @retry_with_different_params(length_ls)
                def retry(length):
                    return TPE.run(partial(core, length=length), klines, **kwargs)
                ind_data = retry()
            else:
                if myself:
                    _args = [source,]
                    _args.extend(ind_params)
                    ind_data = func(*_args, **kwargs)
                    if not isinstance(ind_data, (tuple, list)):
                        ind_data = [ind_data,]
                    assert check_type(
                        ind_data), "返回数据格式为(pd.DataFrame,pd.Series,np.ndarray)"
                    ind_data = list(ind_data)
                    lines_num = sum(
                        [1 if len(d.shape) == 1 else d.shape[1] for d in ind_data])
                    # print(lines, lines_num)
                    # 指标设置的lines与数据返回指标线数量不一致的时候，尝试获取指标线名称
                    # 返回pd.DataFrame,pd.Series,np.ndarray兼并的数据
                    if lines and len(
                            lines) != lines_num:
                        try:
                            if any([isinstance(idata, pd.DataFrame)
                                    for idata in ind_data]):
                                _new_lines = []
                                for l, idata in zip(lines, ind_data):
                                    if isinstance(idata, pd.DataFrame):
                                        _new_lines.extend(list(idata.columns))
                                    else:
                                        _new_lines.append(l)
                                lines = _new_lines
                        except:
                            ...

                    # 通过lines设置指标线，next函数中不需要返回数据
                    if type(source.lines) == Lines and source.lines._lines:
                        _keys_ = list(source.lines._lines.keys())
                        lines.extend(_keys_)
                        _values_ = list(source.lines._lines.values())
                        ind_data.extend(_values_)
                    # 检查数据
                    assert ind_data is not None or source.lines._lines, "无设定指标数据"
                    assert lines and len(
                        lines) == lines_num, f"请设置{func_name}的指标线名称"
                else:
                    ind_data = ind_func(*ind_params, **kwargs)
                    if isinstance(ind_data, pd.DataFrame):
                        if lines is None or (isinstance(lines, Iterable) and len(lines) != ind_data.shape[1]):
                            lines = list(ind_data.columns)

            assert check_type(ind_data), \
                f'指标返回非合法数据类型:{type(ind_data)},必须为pd.DataFrame or pd.Series or np.ndarry'
            category = getattr(
                ind_data, 'category', category)
            if hasattr(ind_data, "overlap"):
                overlap = bool(ind_data.overlap)
            else:
                overlap = kwargs.pop('overlap', category ==
                                     'overlap' and True or _overlap)

            if not isinstance(overlap, (bool, dict)):
                overlap = False
            if lines and isinstance(lines, dict):
                lines = [lines.get(l, l) for l in lines]
            if isinstance(ind_data, (list, tuple)):
                if len(ind_data) == 1:
                    data = ind_data[0]
                else:
                    data = np.c_[tuple([data if isinstance(data, np.ndarray) else
                                        data.values for data in ind_data])]
            else:
                data = ind_data if isinstance(
                    ind_data, np.ndarray) else ind_data.values
            if len(data.shape) > 1 and data.shape[1] == 1:
                data = data[:, 0]

            if len(data.shape) > 1:
                if not lines:
                    lines = [f"line{i}" for i in range(data.shape[1])]
                data = dataframe(data, id=id, sname=func_name, ind_name=func_name, lines=Lines(*lines), category=category,
                                 isplot=isplot, ismain=ismain, isreplay=isreplay, isresample=isresample,
                                 overlap=overlap, isindicator=isindicator, iscustom=iscustom)
            else:

                data = series(data, id=id, sname=func_name, ind_name=func_name, lines=Lines(func_name), category=category,
                              isplot=isplot, ismain=ismain, isreplay=isreplay, isresample=isresample,
                              overlap=overlap, isindicator=isindicator, iscustom=iscustom)
            if light_chart:
                data = pd.concat([source.datetime, data], axis=1)
                data.rename(columns=dict(datetime="time"), inplace=True)
                data.category = category
                data.overlap = overlap
            if index is not None:
                return index, data
            return data

        return wrapper
    return decorator


class BtRolling(Rolling):
    """
    量化回测框架中的滚动窗口（Rolling）增强类，继承自基础 Rolling 类
    核心功能：
    1. 封装 Pandas 的 Rolling 功能，限制输入数据类型为框架支持的 series/dataframe/Line
    2. 重写属性访问逻辑，将 Pandas Rolling 原生方法（如 mean、std）的返回结果
       自动转换为框架内置的 series/dataframe 类型（而非原生 Pandas 对象）
    3. 自动补充指标配置参数（如名称、计算设置），适配回测策略的指标管理体系
    """

    def __init__(self,
                 obj: Union[dataframe, series, Line],
                 window=None,
                 min_periods=None,
                 center=False,
                 win_type=None,
                 on=None,
                 axis=0,
                 closed=None,
                 step=None,
                 method='single',
                 ):
        """
        初始化 BtRolling 实例（滚动窗口配置）

        Args:
            obj: 输入数据对象（必须是框架自定义的 dataframe/series/Line 类型，需包含 pandas_object 属性）
            window: 滚动窗口大小（如 5 表示 5 期窗口，支持 int/offset 等 Pandas 兼容类型）
            min_periods: 窗口内最小非空值数量（低于此数量则结果为 NaN，默认 None 即等于 window 大小）
            center: 是否将窗口结果对齐到窗口中心（默认 False，对齐到窗口末尾）
            win_type: 窗口权重类型（默认 None 为等权重，支持 'boxcar'/'triang' 等 Pandas 支持类型）
            on: 用于滚动计算的列名（仅 dataframe 有效，默认 None 表示用所有列）
            axis: 滚动轴方向（0 为按行滚动/时间维度，1 为按列滚动/特征维度，默认 0）
            closed: 窗口闭合方式（如 'right' 表示包含右边界，默认 None 跟随 Pandas 规则）
            step: 窗口步长（默认 None 为 1，即每步滑动 1 个单位）
            method: 计算方法（默认 'single'，预留参数用于扩展批量计算逻辑）

        关键逻辑：
        - 校验输入数据对象必须包含 'pandas_object' 属性（存储原生 Pandas 对象，如 pd.Series/pd.DataFrame）
        - 调用父类 Rolling 的初始化方法，传入原生 Pandas 对象和滚动参数
        """
        # 保存输入数据对象（框架自定义类型）
        self._obj = obj

        # 断言校验：输入对象必须包含 'pandas_object' 属性（确保是框架支持的数据类型）
        # pandas_object 用于存储原生 Pandas Series/DataFrame，供后续滚动计算使用
        assert hasattr(
            self._obj, 'pandas_object'), 'BtRolling数据对象必须是series、dataframe或Line类型（需包含pandas_object属性）'

        # 调用父类 Rolling 的构造方法，初始化滚动窗口（传入原生 Pandas 对象和配置参数）
        super().__init__(
            self._obj.pandas_object,  # 父类需要原生 Pandas 对象进行滚动计算
            window=window,
            min_periods=min_periods,
            center=center,
            win_type=win_type,
            on=on,
            axis=axis,
            closed=closed,
            step=step,
            method=method
        )

    def rolling_object_method(self, func) -> series | dataframe | Any:
        """
        类装饰器：将 Pandas Rolling 原生方法的返回结果，转换为框架内置的指标数据类型
        作用：
        1. 保留原生方法的计算逻辑，仅增强返回结果的类型适配
        2. 自动补充指标配置参数（如名称、计算设置），便于策略管理指标
        3. 根据返回数据的维度（Series/DataFrame），生成对应的框架数据类型

        Args:
            func: 待装饰的函数（Pandas Rolling 原生方法，如 mean、std、sum 等）

        Returns:
            装饰后的函数：返回框架内置的 series/dataframe 类型，或原结果（非 Pandas 对象时）
        """
        # wraps 装饰器：保留原函数的元信息（如 __name__、__doc__），便于调试和日志
        @wraps(func)
        def wrapper(*args, **kwargs):
            """
            装饰器内部包装函数：执行原生计算并转换返回类型
            """
            # 1. 调用原生 Pandas Rolling 方法，获取计算结果（原生 pd.Series/pd.DataFrame 或其他类型）
            data: pd.Series | pd.DataFrame = func(*args, **kwargs)

            # 2. 策略未初始化时，直接返回原生数据（避免初始化阶段的类型转换逻辑干扰）
            # _isinit 是策略实例的状态标识，标记策略是否完成初始化
            if self._obj.strategy_instance._isinit:
                return data

            # 3. 若结果是 Pandas 对象（Series/DataFrame），转换为框架内置类型
            if isinstance(data, (pd.DataFrame, pd.Series)):
                # 3.1 补充默认参数：若未指定 overlap（是否允许窗口重叠），默认设为 True（重叠滚动）
                # 注：原代码中 'overlpa' 疑似拼写错误（应为 'overlap'），保留原逻辑不修改
                if "overlap" not in kwargs:
                    kwargs.update(dict(overlpa=True))

                # 3.2 获取当前指标的配置参数（从输入数据对象 _obj 中获取）
                # isindicator=True 表示获取的是指标专用配置（如名称、周期等）
                setting = self._obj.get_indicator_kwargs(isindicator=True)
                # 移除 'lines' 配置（lines 用于定义指标输出列，后续按需重新设置）
                setting.pop('lines')

                # 3.3 合并配置参数：优先级为 kwargs（调用时传入）> setting（指标默认配置）
                kwargs = {**setting, **kwargs}
                new_kwargs = {**setting, **kwargs}  # 用于最终生成新指标的配置

                # 3.4 设置新指标的名称：格式为 "Rolling方法名_原指标名"（如 mean_Close 表示收盘价的5期均值）
                new_kwargs['name'] = f"{func.__name__}_{setting['name']}"

                # 3.5 处理 DataFrame 类型结果（多列数据）
                if len(data.shape) > 1:  # shape 长度>1 表示是 DataFrame（行×列）
                    # 若未指定 lines（输出列名），默认使用 DataFrame 的列名
                    if "lines" not in new_kwargs:
                        new_kwargs["lines"] = list(data.columns)
                    # 转换为框架自定义的 dataframe 类型并返回
                    return dataframe(data, **kwargs)

                # 3.6 处理 Series 类型结果（单列数据）
                else:
                    # 若未指定 lines，默认使用原指标名作为唯一列名
                    if "lines" not in new_kwargs:
                        new_kwargs['lines'] = [setting['name'],]
                    # 转换为框架自定义的 series 类型并返回
                    return series(data, **kwargs)

            # 4. 若结果不是 Pandas 对象（如数值、None），直接返回原结果
            else:
                return data

        # 返回装饰后的包装函数
        return wrapper

    def __getattribute__(self, item) -> series | dataframe | pd.Series | pd.DataFrame | Any:
        """
        重写属性访问方法：拦截对 Pandas Rolling 原生方法的调用，自动应用装饰器
        作用：当访问的属性是 Rolling 方法（如 'mean'、'std'）时，先通过 rolling_object_method 装饰器处理
             再返回装饰后的方法，实现返回类型的自动转换

        Args:
            item: 要访问的属性名（如 'mean'、'std'、'sum' 或其他属性）

        Returns:
            若属性是 Rolling 方法：返回装饰后的方法（自动转换返回类型）
            其他属性：直接调用父类的 __getattribute__ 获取（如 _obj、window 等）
        """
        # rolling_method 是预设的 Pandas Rolling 方法列表（如 ['mean', 'std', 'sum', 'max', 'min'] 等）
        # 若访问的属性在 rolling_method 中，说明是需要装饰的 Rolling 方法
        if item in rolling_method:
            # 1. 调用父类的 __getattribute__ 获取原生 Rolling 方法
            # 2. 应用 rolling_object_method 装饰器，返回装饰后的方法
            return self.rolling_object_method(super().__getattribute__(item))

        # 若访问的是其他属性（如 _obj、window、min_periods 等），直接返回父类处理结果
        return super().__getattribute__(item)


def _create_operator_func(op: str, reverse: bool = False, isbool: bool = False) -> Callable:
    def func(self: IndicatorsBase, other):
        return self._apply_operator(other, op, reverse, isbool)
    return func


def _create_unary_func(expr: str) -> Callable:
    def func(self: IndicatorsBase):
        return self._apply_operate_string(expr)
    return func


@dataclass
class BtDataSetting(DataSetBase):
    symbol_info: SymbolInfo
    current_close: np.ndarray
    current_datetime: np.ndarray
    isstop: bool = False
    stop: Optional[Stop] = None
    stop_lines: Optional[dataframe] = None
    tradable: bool = True
    istrader: bool = False
    follow: bool = True
    plot_index: Optional[list[int]] = None

    def set_default_stop_lines(self, id: BtID):
        self.stop_lines = dataframe((len(self.current_close), 2), id=id.copy(), isplot=True, overlap=True, lines=[
            'stop_price', 'target_price'], sname="stop_lines", ind_name="stop_lines")
        self.stop_lines.plotinfo.spanstyle = SpanList()


class IndicatorsBase(Base):
    """
    量化指标基类（所有指标/数据对象的父类）
    核心定位：统一封装指标与K线数据的共性能力，包括数据访问、运算支持、绘图配置、多周期处理等，
    为子类（如Line、series、dataframe、BtData）提供标准化接口，实现指标与数据的无缝交互。

    核心设计：
    1. 多类型兼容：支持单值（Line）、一维（series）、多维（dataframe）数据，统一接口操作
    2. 运算重载：内置算术/比较/逻辑运算符，支持指标间直接运算（如ma5 + ma10）
    3. 绘图配置：集成PlotInfo管理绘图属性（线型、颜色、是否主图叠加等）
    4. 多周期处理：支持数据上采样（resample）、跨周期关联，适配多周期策略
    5. 信号集成：内置交易信号字段（开多/平多/开空/平空），支持策略自动识别信号
    """
    # ------------------------------
    # 核心属性（控制数据类型与行为）
    # ------------------------------
    # 是否为多维数据（True=dataframe，False=series/Line）
    # _isMDim: bool
    # 指标数据与原数据维度是否一致（True=自动被策略收集，False=仅内置使用）
    _dim_match: bool
    # 上采样数据中用于关联原数据的名称（多周期处理用）
    _upsample_name: str = ""
    # 交易信号标识列表（记录当前指标包含的信号类型）
    _issignal: list[str]
    # 交易信号字段（初始为None，策略运行中动态生成）
    _long_signal: series | None = None  # 开多信号
    _exitlong_signal: series | None = None  # 平多信号
    _short_signal: series | None = None  # 开空信号
    _exitshort_signal: series | None = None  # 平空信号
    # dataframe数据中的Line字段列表（记录多维指标的列名）
    # _filed: list[str]
    # 线型配置（如实线、虚线，关联LineStyle类）
    # _lineinfo: LineStyle
    # 颜色配置（键为Line名，值为颜色值）
    # _color: dict
    # 指标核心设置（包含ID、维度、是否指标等元信息）
    _indsetting: IndSetting
    # 最后的有效索引（用于非维度匹配数据的边界控制）
    # _bt_last_index: int
    # 绘图配置（包含线型、颜色、是否显示等）
    _plotinfo: PlotInfo
    # 底层数值数组（快速访问用，与pandas_object同步）
    values: np.ndarray
    # 数据形状（行数×列数，如(1000,5)表示1000行5列）
    shape: tuple
    # 转换ID（上采样/下采样的标识）
    _resample_id: int
    # 转换索引（多周期数据对应的原数据索引）
    _resample_index: int
    # 转换后的数据（上采样/下采样后的完整数据）
    _resample_data: pd.DataFrame
    # 转换次数（记录数据被转换的次数）
    _resample_times: int
    # 因子数据框（存储指标衍生的因子数据）
    factors_df: pd.DataFrame
    # 合约信息（关联SymbolInfo，包含合约乘数、最小变动等）
    _symbol_info: SymbolInfo
    # 停止线（如止损线、止盈线，关联dataframe）
    _stop_lines: dataframe
    # 交易代理（关联Broker，处理下单、手续费计算等）
    _broker: Broker
    # 指标内置数据集（管理原始数据、转换数据等）
    _dataset: DataFrameSet
    _tqobj: TqObjs
    # 行/列数量（V=rows，H=columns）
    # _v: int  # 行
    # _h: int  # 列

    # ------------------------------
    # 运算符重载（支持指标间直接运算）
    # ------------------------------
    # 比较运算符（<, <=, ==, !=, >, >=）
    __lt__ = _create_operator_func('<')
    __le__ = _create_operator_func('<=')
    __eq__ = _create_operator_func('==')
    __ne__ = _create_operator_func('!=')
    __gt__ = _create_operator_func('>')
    __ge__ = _create_operator_func('>=')

    # 反向比较运算符（如a < b 等效于 b > a）
    __rlt__ = _create_operator_func('<', True)
    __rle__ = _create_operator_func('<=', True)
    __req__ = _create_operator_func('==', True)
    __rne__ = _create_operator_func('!=', True)
    __rgt__ = _create_operator_func('>', True)
    __rge__ = _create_operator_func('>=', True)

    # 一元运算符（将布尔值转换为float，支持数值运算）
    __pos__ = _create_unary_func(
        'value=+(self.pandas_object.astype(np.float32))')  # 正号（+x）
    __neg__ = _create_unary_func(
        'value=-(self.pandas_object.astype(np.float32))')  # 负号（-x）
    __abs__ = _create_unary_func(
        'value=self.pandas_object.astype(np.float32).abs()')  # 绝对值（abs(x)）
    __invert__ = _create_unary_func(
        'value=~self.pandas_object.astype(np.bool_)')  # 按位取反（~x，仅布尔值）

    # 二元算术运算符（+, -, *, /, //, %, **）
    __add__ = _create_operator_func('+')  # 加法
    __sub__ = _create_operator_func('-')  # 减法
    __mul__ = _create_operator_func('*')  # 乘法
    __truediv__ = _create_operator_func('/')  # 真除法
    __floordiv__ = _create_operator_func('//')  # 地板除法
    __mod__ = _create_operator_func('%')  # 取模
    __pow__ = _create_operator_func('**')  # 幂运算

    # 二元逻辑运算符（&, |，仅布尔值）
    __and__ = _create_operator_func('&', isbool=True)  # 按位与
    __or__ = _create_operator_func('|', isbool=True)   # 按位或

    # 反向二元运算符（如a + b 等效于 b + a）
    __radd__ = _create_operator_func('+', True)
    __rsub__ = _create_operator_func('-', True)
    __rmul__ = _create_operator_func('*', True)
    __rtruediv__ = _create_operator_func('/', True)
    __rfloordiv__ = _create_operator_func('//', True)
    __rmod__ = _create_operator_func('%', True)
    __rpow__ = _create_operator_func('**', True)
    __rand__ = _create_operator_func('&', True, True)
    __ror__ = _create_operator_func('|', True, True)

    # 原地运算符（如a += b，直接修改a的值）
    __iadd__ = _create_operator_func('+')
    __isub__ = _create_operator_func('-')
    __imul__ = _create_operator_func('*')
    __itruediv__ = _create_operator_func('/')
    __ifloordiv__ = _create_operator_func('//')
    __imod__ = _create_operator_func('%')
    __ipow__ = _create_operator_func('**')
    __iand__ = _create_operator_func('&', isbool=True)
    __ior__ = _create_operator_func('|', isbool=True)

    # ------------------------------
    # 核心属性接口（关联BtData与策略）
    # ------------------------------

    @property
    def btdata(self) -> BtData:
        """
        获取当前指标关联的BtData数据（属性接口）
        非指标对象（如BtData自身）返回自身，指标对象通过data_id关联到对应的BtData

        Returns:
            BtData: 关联的K线数据对象
        """
        """### 指标对应的BtData数据"""
        if not self.isindicator:
            return self
        return self._get_btdata(self.data_id)

    @cachedmethod(attrgetter('cache'))
    def _get_btdata(self, btdata_id: int):
        """
        缓存并获取BtData数据（内部方法，供btdata属性调用）
        基于data_id从策略的_btdatasset中获取对应的BtData，缓存结果避免重复查找

        Args:
            btdata_id (int): BtData的唯一标识ID

        Returns:
            BtData: 对应的K线数据对象
        """
        """### 缓存BtData数据"""
        return self.strategy_instance._btdatasset[btdata_id]

    # ------------------------------
    # 交易逻辑与配置接口
    # ------------------------------
    def setp(self):
        """
        交易逻辑扩展接口（抽象方法，可被子类重写）
        用于在指标内部嵌入交易逻辑（如基于指标值自动下单），策略运行时会自动调用

        示例：
        >>> class The_Flash_Strategy_(BtIndicator):
            params = dict(length=10, period=10, mult=3.,
                        pmax_length=12, pmax_mult=3., mom_rsi_val=60.)
            overlap = False
            def next(self):
                mom = self.close-self.close.shift(self.params.length)
                rsi_mom = mom.rsi(self.params.length)
                supertrend, direction = self.supertrend(
                    self.params.period, self.params.length).to_lines("trend", "dir")
                pmax_thrend = self.close.btind.pmax(
                    self.params.pmax_length, self.params.pmax_mult, mode="ema").thrend
                long_signal = pmax_thrend > 0.
                long_signal &= direction < 0.
                long_signal &= rsi_mom > self.params.mom_rsi_val
                exitlong_signal = self.close.cross_down(supertrend)
                short_signal = pmax_thrend < 0.
                short_signal &= direction > 0.
                short_signal &= rsi_mom > self.params.mom_rsi_val
                exitshort_signal = self.close.cross_up(supertrend)
                return long_signal, exitlong_signal, short_signal, exitshort_signal
            def step(self):
                if not self.btdata.position.pos:
                    if self.long_signal.new:
                        self.btdata.buy()
                    elif self.short_signal.new:
                        self.btdata.sell()
                else:
                    if self.short_signal.new:
                        self.btdata.set_target_size(-1)
                    elif self.long_signal.new:
                        self.btdata.set_target_size(1)
        """
        """### 可添加交易逻辑"""
        ...

    def get_indicator_kwargs(self, **kwargs) -> dict[str, Any]:
        """
        整合指标配置参数（内部方法，供指标初始化用）
        合并_indsetting（指标设置）、_plotinfo（绘图配置）与用户传入的kwargs，返回统一参数字典

        Args:
            **kwargs: 用户传入的额外参数（优先级最高，覆盖默认配置）

        Returns:
            dict[str, Any]: 整合后的指标参数字典（Addict类型，支持属性式访问）
        """
        try:
            # 合并配置：指标设置 → 绘图配置 → 用户参数（优先级递增）
            return Addict({**self._indsetting.vars, **self._plotinfo.vars, **kwargs})
        except:
            # 配置合并失败时，返回用户参数（降级处理）
            return kwargs

    def time_to_datetime(self) -> Optional[series]:
        """### 将时间字段转换为datetime.datetime类型（方法接口）
        支持多种时间格式输入，统一转换为标准datetime类型，便于时间筛选与计算

        支持的输入格式：
        - int: 秒级/纳秒级时间戳（如1571103122 → 2019-10-14 14:12:02）
        - float: 秒级/纳秒级时间戳（如1.57103449e+18 → 2019-10-14 14:28:10）
        - str: 时间字符串（如"2019-10-14 14:26:01.000000"）

        Returns:
            Optional[series]: 转换后的datetime类型序列（非多维数据时有效，否则返回None）

        Raises:
            Exception: 转换失败时打印错误信息，返回None
        """
        """### 将时间类型转换为 datetime.datetime 类型

        Args:
            >>> series
            (int  float  str).
            需要转换的时间:
            * int: int 类型的纳秒级或秒级时间戳 (eg. 1571103122)
            * float: float 类型的纳秒级或秒级时间戳,如K线或tick的datetime字段 (eg. 1.57103449e+18)
            * str: str 类型的时间,如Quote行情时间的 datetime 字段 (eg. 2019-10-14 14:26:01.000000)

        Returns:
        >>> datetime.datetime : datetime 模块中的 datetime 类型时间

        Example:
        >>> print(series.time_to_datetime())  # 将纳秒级时间戳转为datetime.datetime时间
            print(series.time_to_datetime())  # 将秒级时间戳转为datetime.datetime时间
            # 将%Y-%m-%d %H:%M:%S.%f 格式的str类型时间转为datetime.datetime时间
            print(series.time_to_datetime())
        """
        if not self._indsetting.isMDim:
            try:
                return self.apply(time_to_datetime)
            except Exception as e:
                print(e)

    @staticmethod
    def get_max_missing_count(*args: tuple[pd.Series, np.ndarray]) -> int:
        """
        计算输入数据中缺失值数量的最大值（静态方法）
        仅处理np.ndarray或pd.Series类型，用于指标计算前的数据源质量校验

        Args:
            *args: 可变参数，每个参数为np.ndarray或pd.Series

        Returns:
            int: 所有输入数据中缺失值数量的最大值（无输入时返回0）
        """
        """参数必须为np.ndarray或pandas.Series，返回输入中缺失值数量的最大值"""
        if not args:
            return 0
        # 计算每个输入的缺失值数量
        result = [len(arg[pd.isnull(arg)])
                  for arg in args if isinstance(arg, (pd.Series, np.ndarray))]
        if len(result) == 1:
            return result[0]
        return max(result) if result else 0

    # ------------------------------
    # 名称与ID配置接口（标识与关联）
    # ------------------------------
    @property
    def sname(self) -> str:
        """
        获取策略赋值的指标名称（属性接口）
        用于策略中标识指标（如self.ma5的sname为"ma5"），关联_plotinfo的sname字段

        Returns:
            str: 指标的策略内名称
        """
        """### 名称
        策略赋值的指标名称"""
        return self._plotinfo.sname

    @sname.setter
    def sname(self, value) -> None:
        """
        设置策略赋值的指标名称（属性接口）
        仅接受非空字符串，用于自定义指标在策略中的标识

        Args:
            value (str): 新的指标名称
        """
        if value and isinstance(value, str):
            self._plotinfo.sname = value

    @property
    def ind_name(self) -> str:
        """
        获取指标自身名称（属性接口）
        用于标识指标类型（如"MA"、"RSI"），关联_plotinfo的ind_name字段

        Returns:
            str: 指标的类型名称
        """
        """### 指标名称"""
        return self._plotinfo.ind_name

    @ind_name.setter
    def ind_name(self, value) -> None:
        """
        设置指标自身名称（属性接口）
        仅接受非空字符串，用于自定义指标的类型标识

        Args:
            value (str): 新的指标类型名称
        """
        if value and isinstance(value, str):
            self._plotinfo.ind_name = value

    @property
    def id(self) -> BtID:
        """
        获取指标的唯一标识（属性接口）
        BtID包含策略ID、数据ID、绘图ID等，用于多策略、多数据的关联

        Returns:
            BtID: 指标的唯一标识对象
        """
        """### BtID"""
        return self._indsetting.id

    @id.setter
    def id(self, value) -> None:
        """
        设置指标的唯一标识（属性接口）
        仅接受BtID类型，用于关联指标到特定策略与数据

        Args:
            value (BtID): 新的BtID对象
        """
        if value and isinstance(value, BtID):
            self._indsetting.id = value

    # ------------------------------
    # BtID分解接口（快速获取ID组件）
    # ------------------------------
    @property
    def strategy_id(self) -> int:
        """
        获取策略ID（属性接口，BtID分解）
        从_indsetting.id中提取strategy_id，用于关联到特定策略实例

        Returns:
            int: 策略的唯一标识ID
        """
        """### 策略ID"""
        return self._indsetting.id.strategy_id

    @property
    def sid(self) -> int:
        """
        获取策略ID（属性接口，与strategy_id功能一致，兼容简写）

        Returns:
            int: 策略的唯一标识ID
        """
        """### 策略ID"""
        return self._indsetting.id.strategy_id

    @property
    def plot_id(self) -> int:
        """
        获取绘图ID（属性接口，BtID分解）
        用于标识指标在绘图中的分组（如多合约绘图时区分不同子图）

        Returns:
            int: 绘图分组ID
        """
        """### 画图ID"""
        return self._indsetting.id.plot_id

    @property
    def data_id(self) -> int:
        """
        获取数据ID（属性接口，BtID分解）
        关联到对应的BtData数据，用于指标与K线数据的绑定

        Returns:
            int: 关联的BtDataID
        """
        """### 数据ID"""
        return self._indsetting.id.data_id

    @property
    def resample_id(self) -> int:
        """
        获取转换ID（属性接口，BtID分解）
        用于标识上采样/下采样后的数据，支持多周期数据关联

        Returns:
            int: 数据转换ID
        """
        """### 转换ID"""
        return self._indsetting.id.resample_id

    @property
    def replay_id(self) -> int:
        """
        获取播放ID（属性接口，BtID分解）
        用于回放数据的标识，支持历史数据回放功能

        Returns:
            int: 数据回放ID
        """
        """### 播放ID"""
        return self._indsetting.id.replay_id

    # ------------------------------
    # 指标线配置接口（绘图与显示）
    # ------------------------------
    @property
    def lines(self) -> Lines:
        """
        获取指标线配置（属性接口）
        管理指标的所有线条（如MA5、MA10），支持字符串、列表、Lines对象赋值

        Returns:
            Lines: 指标线配置对象（包含所有线条名称与属性）
        """
        """### 指标线

        可设置value:
        >>> str,Iterable,Lines"""
        return self._plotinfo.lines

    @property
    def line(self) -> list[Line]:
        """
        获取多维指标的Line对象列表（属性接口）
        仅对多维数据（isMDim=True）有效，返回所有列对应的Line实例

        Returns:
            list[Line]: Line对象列表（非多维数据返回空列表）
        """
        if not self._indsetting.isMDim:
            return []
        # 从指标设置的line_filed中提取Line对象
        return [getattr(self, filed) for filed in self._indsetting.line_filed]

    @lines.setter
    def lines(self, value) -> None:
        """
        设置指标线配置（属性接口）
        自动转换输入格式为Lines对象，支持字符串（单线条）、列表/元组（多线条）

        Args:
            value (str | Iterable | Lines): 指标线配置
                - str: 单线条名称（如"MA5"）
                - Iterable: 多线条名称列表（如["MA5", "MA10"]）
                - Lines: 已构建的Lines对象

        Raises:
            ValueError: 输入格式不支持时触发
        """
        if value:
            # 格式转换：统一转为Lines对象
            if type(value) != Lines:
                if isinstance(value, str) and self.H == 1:
                    # 单线条字符串 → Lines
                    value = Lines(value)
                elif type(value) in [list, tuple]:
                    # 列表/元组 → Lines
                    value = Lines(*value)
                elif isinstance(value, Iterable):
                    # 可迭代对象 → 列表 → Lines
                    value = list(value)
                    value = Lines(*value)
                else:
                    raise ValueError("请设置正确指标线（支持str、list、tuple、Lines）")
            # 更新绘图配置的指标线
            self._plotinfo.lines = value

    # ------------------------------
    # 绘图分类与样式接口
    # ------------------------------
    @property
    def category(self) -> Union[CategoryString, str]:
        """
        获取指标绘图分类（属性接口）
        标识指标的绘图类型（如"Candles"=蜡烛图、"MA"=均线、"RSI"=震荡指标）

        Returns:
            Union[CategoryString, str]: 绘图分类（支持CategoryString枚举或字符串）
        """
        """### 类别"""
        return self._plotinfo.category

    @category.setter
    def category(self, value) -> None:
        """
        设置指标绘图分类（属性接口）
        自动注册新分类到Category枚举，支持自定义分类名称

        Args:
            value (str): 新的绘图分类名称（如"CustomIndicator"）
        """
        if value and isinstance(value, str):
            # 转换为CategoryString对象（兼容枚举）
            category = CategoryString(value)
            self._plotinfo.category = category
            # 若分类不在默认Category中，动态添加
            if category not in Category:
                setattr(Category, value.capitalize(), category)

    @property
    def iscandles(self) -> bool:
        """
        判断是否为蜡烛图类型（属性接口）
        基于category是否为"Candles"，用于绘图时区分K线与普通指标

        Returns:
            bool: True=蜡烛图，False=普通指标
        """
        """### 是否为蜡烛图"""
        return self._plotinfo.category.iscandles

    @property
    def isplot(self) -> Union[dict, bool]:
        """
        获取指标的绘图开关（属性接口）
        控制指标是否显示在图表中，支持单值（bool）或多线条配置（dict）

        Returns:
            Union[dict, bool]: 
                - bool: 单线条指标的绘图开关
                - dict: 多线条指标的绘图开关（键为线条名，值为bool）
        """
        """### 是否画图

        可设置value:
        >>> series:bool
            dataframe:bool,list[bool],tuple[bool],dict[str,bool]"""
        return self._plotinfo.isplot

    @isplot.setter
    def isplot(self, value) -> None:
        """
        设置指标的绘图开关（属性接口）
        批量控制所有线条的显示状态，自动同步信号叠加配置

        Args:
            value (bool | list[bool] | tuple[bool] | dict[str, bool]): 
                - bool: 所有线条统一开关
                - list/tuple: 按线条顺序设置开关（长度需与线条数一致）
                - dict: 按线条名设置开关（键为线条名，值为bool）
        """
        # 批量设置线条的绘图开关
        self._plotinfo.set_lines_plot(value)
        # 同步更新信号的叠加配置
        self._plotinfo._set_signal_overlap()

    @property
    def height(self) -> int:
        """
        获取指标绘图高度（属性接口）
        控制指标在图表中的显示高度（像素），默认最小值20

        Returns:
            int: 绘图高度（像素）
        """
        """### 画图高度"""
        return self._plotinfo.height

    @height.setter
    def height(self, value: int) -> None:
        """
        设置指标绘图高度（属性接口）
        仅接受大于19的整数，确保绘图区域可见

        Args:
            value (int | float): 新的绘图高度（自动转换为整数）
        """
        if isinstance(value, (int, float)) and value > 19:
            self._plotinfo.height = int(value)

    @property
    def overlap(self) -> Union[dict, bool]:
        """
        获取指标是否主图叠加（属性接口）
        控制指标是否显示在主图（K线图）上，支持单值或多线条配置

        Returns:
            Union[dict, bool]: 
                - bool: 单线条指标的叠加开关
                - dict: 多线条指标的叠加开关（键为线条名，值为bool）
        """
        """### 是否为主图叠加

        可设置value:
        >>> series:bool
            dataframe:bool,list[bool],tuple[bool],dict[str,bool]"""
        return self._plotinfo.overlap

    @overlap.setter
    def overlap(self, value) -> None:
        """
        设置指标是否主图叠加（属性接口）
        批量控制所有线条的主图叠加状态

        Args:
            value (bool | list[bool] | tuple[bool] | dict[str, bool]): 
                - bool: 所有线条统一叠加开关
                - list/tuple: 按线条顺序设置叠加（长度需与线条数一致）
                - dict: 按线条名设置叠加（键为线条名，值为bool）
        """
        self._plotinfo.set_lines_overlap(value)

    @property
    def plotinfo(self) -> PlotInfo:
        """
        获取完整的绘图配置（属性接口）
        返回PlotInfo对象，包含所有绘图相关配置，**不可直接赋值**

        Returns:
            PlotInfo: 绘图配置对象
        """
        """### 画图信息,不可赋值"""
        return self._plotinfo

    @property
    def signallines(self) -> list[str]:
        """
        获取信号线条名称列表（属性接口）
        从plotinfo中提取所有标记为信号的线条名称，用于策略识别交易信号

        Returns:
            list[str]: 信号线条名称列表
        """
        return self._plotinfo.signallines

    @property
    def issignal(self) -> bool:
        """
        判断指标是否包含交易信号（属性接口）
        基于signallines是否非空，用于策略筛选信号指标

        Returns:
            bool: True=包含信号，False=不包含信号
        """
        return bool(self._plotinfo.signallines)

    @property
    def candle_style(self) -> Optional[CandleStyle]:
        """
        获取蜡烛图样式（属性接口）
        仅对非指标对象（如BtData）有效，包含蜡烛图颜色、线型等配置

        Returns:
            Optional[CandleStyle]: 蜡烛图样式对象（非蜡烛图返回None）
        """
        return self._plotinfo.candlestyle

    @candle_style.setter
    def candle_style(self, value):
        """
        设置蜡烛图样式（属性接口）
        仅对非指标对象有效，自动将category设为"Candles"

        Args:
            value (CandleStyle): 蜡烛图样式对象
        """
        if not self.isindicator and isinstance(value, CandleStyle):
            self._plotinfo.candlestyle = value
            self._plotinfo.category = Category.Candles

    # ------------------------------
    # 多周期与数据类型接口
    # ------------------------------
    @property
    def ismain(self) -> bool:
        """
        判断跨周期指标是否在主周期显示（属性接口）
        用于多周期策略中，控制子周期指标是否在主周期图表中显示

        Returns:
            bool: True=主周期显示，False=子周期单独显示
        """
        """### 跨周期指标在主周期中显示"""
        return self._indsetting.ismain

    @ismain.setter
    def ismain(self, value) -> None:
        """
        设置跨周期指标是否在主周期显示（属性接口）
        自动同步plot_id与策略属性，确保主周期显示时数据关联正确

        Args:
            value (bool): 主周期显示开关
        """
        value = bool(value)
        self._indsetting.ismain = value
        if value:
            # 回放数据：plot_id同步为replay_id
            if self.isreplay:
                self.id.plot_id = self.id.replay_id
            # 转换数据：将指标注册为策略属性
            elif self.isresample:
                setattr(self.strategy_instance, self.sname, self())

    @property
    def isreplay(self) -> bool:
        """
        判断是否为回放数据（属性接口）
        用于历史数据回放功能，标识数据是否为回放模式

        Returns:
            bool: True=回放数据，False=实时/历史数据
        """
        """### 是否为播放数据"""
        return self._indsetting.isreplay

    @isreplay.setter
    def isreplay(self, value) -> None:
        """
        设置是否为回放数据（属性接口）
        仅接受布尔值，用于切换数据的回放状态

        Args:
            value (bool): 回放数据开关
        """
        self._indsetting.isreplay = bool(value)

    @property
    def isresample(self) -> bool:
        """
        判断是否为转换数据（属性接口）
        标识数据是否经过上采样/下采样（如1分钟→5分钟）

        Returns:
            bool: True=转换数据，False=原始数据
        """
        """### 是否为转换数据"""
        return self._indsetting.isresample

    @isresample.setter
    def isresample(self, value) -> None:
        """
        设置是否为转换数据（属性接口）
        仅接受布尔值，用于标记数据的转换状态

        Args:
            value (bool): 转换数据开关
        """
        self._indsetting.isresample = bool(value)

    @property
    def isMDim(self) -> bool:
        """
        判断是否为多维数据（属性接口）
        区分数据类型：True=dataframe（多列），False=series/Line（单列）

        Returns:
            bool: True=多维数据，False=一维数据
        """
        """### 是否为多维数据"""
        return self._indsetting.isMDim

    # ------------------------------
    # 水平线配置接口（绘图辅助）
    # ------------------------------
    @property
    def span_style(self) -> SpanList:
        """
        获取水平线样式列表（属性接口）
        管理指标的水平线配置（如RSI的20/80分界线），支持批量添加

        Returns:
            SpanList: 水平线样式列表对象
        """
        """### 水平线"""
        return self._plotinfo.spanstyle

    @span_style.setter
    def span_style(self, value) -> None:
        """
        添加水平线样式（属性接口）
        批量添加水平线配置，支持单个样式或样式列表

        Args:
            value (SpanStyle | list[SpanStyle]): 水平线样式（单个或列表）
        """
        self._plotinfo.spanstyle += value

    @property
    def span_location(self) -> list[float]:
        """
        获取水平线位置列表（属性接口）
        返回所有水平线的Y轴位置（如[20.0, 80.0]）

        Returns:
            list[float]: 水平线位置列表
        """
        return self._plotinfo.span_location

    @span_location.setter
    def span_location(self, value):
        """
        设置水平线位置（属性接口）
        批量添加水平线位置，自动同步到span_style

        Args:
            value (float | list[float]): 水平线位置（单个或列表）
        """
        self._plotinfo.spanstyle += value

    @property
    def span_color(self) -> list[str, Colors]:
        """
        获取水平线颜色列表（属性接口）
        返回所有水平线的颜色配置（如["red", "green"]）

        Returns:
            list[str | Colors]: 水平线颜色列表
        """
        return self._plotinfo.span_color

    @span_color.setter
    def span_color(self, value):
        """
        设置水平线颜色（属性接口）
        批量更新所有水平线的颜色，支持字符串或Colors枚举

        Args:
            value (str | Colors | list[str | Colors]): 颜色配置（单个或列表）
        """
        self._plotinfo.span_color = value

    @property
    def span_dash(self) -> list[str, LineDash]:
        """
        获取水平线线型列表（属性接口）
        返回所有水平线的线型配置（如["solid", "dashed"]）

        Returns:
            list[str | LineDash]: 水平线线型列表
        """
        return self._plotinfo.span_dash

    @span_dash.setter
    def span_dash(self, value):
        """
        设置水平线线型（属性接口）
        批量更新所有水平线的线型，支持字符串或LineDash枚举

        Args:
            value (str | LineDash | list[str | LineDash]): 线型配置（单个或列表）
        """
        self._plotinfo.span_dash = value

    @property
    def span_width(self) -> list[float]:
        """
        获取水平线宽度列表（属性接口）
        返回所有水平线的宽度配置（如[1.0, 2.0]）

        Returns:
            list[float]: 水平线宽度列表
        """
        return self._plotinfo.span_width

    @span_width.setter
    def span_width(self, value):
        """
        设置水平线宽度（属性接口）
        批量更新所有水平线的宽度，支持浮点数或列表

        Args:
            value (float | list[float]): 宽度配置（单个或列表）
        """
        self._plotinfo.span_width = value

    # ------------------------------
    # 数据类型标识接口
    # ------------------------------
    @property
    def isindicator(self) -> bool:
        """
        判断是否为指标对象（属性接口）
        区分指标（如MA、RSI）与原始数据（如BtData）

        Returns:
            bool: True=指标对象，False=原始数据
        """
        """### 是否为指标,反之为BtData数据"""
        return self._indsetting.isindicator

    @isindicator.setter
    def isindicator(self, value) -> None:
        """
        设置是否为指标对象（属性接口）
        仅接受布尔值，用于标记数据的类型

        Args:
            value (bool): 指标标识开关
        """
        self._indsetting.isindicator = bool(value)

    @property
    def iscustom(self) -> bool:
        """
        判断是否为自定义数据（属性接口）
        标识数据是否为用户自定义（非系统生成）

        Returns:
            bool: True=自定义数据，False=系统数据
        """
        """### 是否为自定义数据"""
        return self._indsetting.iscustom

    @iscustom.setter
    def iscustom(self, value) -> None:
        """
        设置是否为自定义数据（属性接口）
        仅接受布尔值，用于标记数据的来源

        Args:
            value (bool): 自定义数据开关
        """
        self._indsetting.iscustom = bool(value)

    # ------------------------------
    # 数据集与工具接口
    # ------------------------------
    @property
    def ind_setting(self) -> IndSetting:
        """
        获取指标完整设置（属性接口）
        返回_indsetting对象，包含指标的所有元信息（ID、维度、类型等）

        Returns:
            IndSetting: 指标设置对象
        """
        """### 返回指标设置"""
        return self._indsetting

    @property
    def dataset(self) -> DataFrameSet:
        """
        获取指标内置数据集（属性接口）
        管理原始数据、转换数据、上采样数据等，支持多版本数据存储

        Returns:
            DataFrameSet: 数据集对象
        """
        """### 数据集"""
        return self._dataset

    @property
    def pandas_object(self) -> pd.DataFrame | pd.Series | corefunc:
        """
        获取底层Pandas对象（属性接口）
        返回指标对应的原生Pandas对象（DataFrame/Series），用于高级数据操作

        Returns:
            pd.DataFrame | pd.Series | corefunc: 原生Pandas对象
        """
        """### pandas数据"""
        return self._dataset.pandas_object

    @property
    def kline_object(self) -> Optional[Union[pd.DataFrame, corefunc]]:
        """
        获取转换前的原始K线数据（属性接口）
        无论数据是否经过转换（如HA K线、线性回归K线），始终返回最原始的K线数据

        Returns:
            Optional[Union[pd.DataFrame, corefunc]]: 原始K线数据（无则返回None）
        """
        """### BtData为其它类型蜡烛图时,kline_object返回转换前的pandas数据,即无论BtData数据怎么变换,kline_object为最原始的pandas数据"""
        return self._dataset.kline_object

    @property
    def source_object(self) -> Optional[Union[pd.DataFrame, pd.Series, corefunc]]:
        """
        获取最原始的数据源（属性接口）
        多周期场景中，返回最顶层的原始数据（非转换/上采样数据）

        Returns:
            Optional[Union[pd.DataFrame, pd.Series, corefunc]]: 原始数据源（无则返回None）
        """
        """### 原始pandas数据,多周期中最原始的pandas数据"""
        return self._dataset.source_object

    @property
    def conversion_object(self) -> Optional[Union[pd.DataFrame, pd.Series, corefunc]]:
        """
        获取转换前的数据（属性接口）
        返回数据转换（如HA、线性回归）前的原始数据，用于对比分析

        Returns:
            Optional[Union[pd.DataFrame, pd.Series, corefunc]]: 转换前数据（无则返回None）
        """
        """### 转换前的pandas数据"""
        return self._dataset.conversion_object

    @property
    def custom_object(self) -> Optional[Union[pd.DataFrame, pd.Series, corefunc]]:
        """
        获取自定义数据（属性接口）
        返回用户自定义的数据（如手动计算的指标），用于扩展分析

        Returns:
            Optional[Union[pd.DataFrame, pd.Series, corefunc]]: 自定义数据（无则返回None）
        """
        """### 自定义pandas数据"""
        return self._dataset.custom_object

    # ------------------------------
    # 数据维度与长度接口
    # ------------------------------
    @property
    def V(self) -> int:
        """
        获取数据行数（属性接口，简写）
        等同于_length，返回数据的时间步数量

        Returns:
            int: 数据行数（时间步数量）
        """
        """### 行"""
        return self._indsetting.v

    @property
    def length(self) -> int:
        """
        获取数据长度（属性接口，与V功能一致）
        返回数据的时间步数量，用于循环迭代与切片

        Returns:
            int: 数据长度（时间步数量）
        """
        """### 数据长度"""
        return self._indsetting.v

    @property
    def H(self) -> int:
        """
        获取数据列数（属性接口，简写）
        返回数据的特征维度数量（如MA5+MA10为2列）

        Returns:
            int: 数据列数（特征维度）
        """
        """###  列"""
        return self._indsetting.h

    # ------------------------------
    # 第三方指标库接口（集成常用工具）
    # ------------------------------
    @property
    def pta(self) -> PandasTa:
        """
        获取PandasTA指标库接口（属性接口）
        集成PandasTA的所有指标（如SMA、RSI、MACD），支持链式调用

        Returns:
            PandasTa: PandasTA指标包装对象
        """
        """### pandas_ta指标"""
        return PandasTa(self)

    @property
    def talib(self) -> TaLib:
        """
        获取TA-Lib指标库接口（属性接口）
        集成TA-Lib的所有指标，支持高性能计算

        Returns:
            TaLib: TA-Lib指标包装对象
        """
        """### Ta_Lib指标"""
        return TaLib(self)

    @property
    def tulip(self) -> TuLip:
        """
        获取Tulip指标库接口（属性接口）
        集成Tulip Indicators的所有指标，支持小众但实用的指标

        Returns:
            TuLip: Tulip指标包装对象
        """
        """### tulip指标"""
        return TuLip(self)

    @property
    def btind(self) -> BtInd:
        """
        获取内置指标接口（属性接口）
        集成框架自定义的内置指标（如自定义MA、止损线）

        Returns:
            BtInd: 内置指标包装对象
        """
        """### 内置指标"""
        return BtInd(self)

    @property
    def finta(self) -> FinTa:
        """
        获取FinTa指标库接口（属性接口）
        集成FinTa的所有指标，专注于金融技术分析

        Returns:
            FinTa: FinTa指标包装对象
        """
        """### Finta指标"""
        return FinTa(self)

    @property
    def autotrader(self) -> AutoTrader:
        """
        获取AutoTrader指标接口（属性接口）
        集成AutoTrader相关的策略指标，支持自动化交易逻辑

        Returns:
            AutoTrader: AutoTrader指标包装对象
        """
        """### autotrader指标"""
        return AutoTrader(self)

    @property
    def tqfunc(self) -> TqFunc:
        """
        获取天勤指标接口（属性接口）
        集成TQSDK特有的指标与工具函数，适配期货实盘

        Returns:
            TqFunc: 天勤指标包装对象
        """
        """### 天勤指标"""
        return TqFunc(self)

    @property
    def sf(self) -> SignalFeatures:
        """
        获取信号特征接口（属性接口）
        生成交易信号相关的特征（如交叉信号、突破信号），用于策略输入

        Returns:
            SignalFeatures: 信号特征包装对象
        """
        """### 特征指标"""
        return SignalFeatures(self)

    @property
    def pairtrading(self) -> Pair:
        """
        获取配对交易指标接口（属性接口）
        集成配对交易相关指标（如协整检验、价差计算）

        Returns:
            Pair: 配对交易指标包装对象
        """
        """### 配对交易指标"""
        return Pair(self)

    @property
    def factors(self) -> Factors:
        """
        获取因子分析接口（属性接口）
        生成与管理因子数据（如动量因子、价值因子），用于多因子策略

        Returns:
            Factors: 因子分析包装对象
        """
        """### 因子"""
        return Factors(self)

    # ------------------------------
    # 策略与回测状态接口
    # ------------------------------
    @property
    def btindex(self) -> int:
        """
        获取当前回测索引（属性接口）
        同步策略的_btindex，标识当前处理到的K线位置

        Returns:
            int: 回测当前索引（从-1开始）
        """
        """### 索引"""
        return self.strategy_instance._btindex

    @property
    def islivetrading(self) -> bool:
        """
        判断是否为实盘交易（属性接口）
        同步策略的_is_live_trading状态，用于区分回测与实盘逻辑

        Returns:
            bool: True=实盘交易，False=回测
        """
        """### 是否实盘交易"""
        return self._is_live_trading

    @property
    def new(self) -> float | int | bool | np.ndarray | Any:
        """
        获取最新数据（属性接口）
        等同于self.values[self.btindex]，快速访问当前K线的指标值

        Returns:
            float | int | bool | np.ndarray | Any: 最新数据（单值或数组）
        """
        """### 最新数据
            >>> 等同于self.XXX.values[self.btindex]"""
        return self.history()

    @new.setter
    def new(self, value: float | list[float]) -> None:
        """
        设置最新数据（属性接口）
        直接修改当前K线的指标值，支持单值（一维数据）或列表（多维数据）

        Args:
            value (float | list[float]): 新的最新数据值
        """
        if self.iscustom:
            if len(self.shape) == 1:
                # 一维数据：直接修改当前索引值
                self._mgr.blocks[0].values[self.btindex] = value
                # Line类型：同步更新源数据
                if type(self) == Line:
                    self.source._mgr.blocks[0].values[self.source.lines.index(
                        self.lines[0])][self.btindex] = value
            else:
                # 多维数据：按列更新当前索引值
                self._mgr.blocks[0].values[:, self.btindex] = value
                # 同步更新各Line字段
                for filed, v in zip(self._indsetting.line_filed, value):
                    line = getattr(self, filed)
                    line._mgr.blocks[0].values[self.btindex] = v

    @property
    def prev(self) -> float | int | bool | np.ndarray | Any:
        """
        获取前一周期数据（属性接口）
        等同于self.values[self.btindex-1]，快速访问上一根K线的指标值

        Returns:
            float | int | bool | np.ndarray | Any: 前一周期数据（单值或数组）
        """
        """### 前一数据
            >>> 等同于self.XXX.values[self.btindex-1]"""
        return self.history(1)

    def history(self, lookback: int = 0, size: int = 1) -> float | int | bool | np.ndarray | Any:
        """
        获取历史数据（方法接口）
        支持灵活的历史数据查询，可指定偏移量与数据长度，支持缓存优化

        Args:
            lookback (int, optional): 时间偏移量（0=最新，1=前一周期，依此类推）. Defaults to 0.
            size (int, optional): 数据长度（1=单值，>1=数组）. Defaults to 1.

        Returns:
            float | int | bool | np.ndarray | Any: 
                - 单值：size=1时返回
                - 数组：size>1时返回（形状为(size,)）

        示例说明：
        >>> self.ma5.history(0)        # 最新MA5值（等同于self.ma5.new）
            self.ma5.history(1)        # 前一周期MA5值（等同于self.ma5.prev）
            self.ma5.history(10)       # 10周期前的MA5值
            self.ma5.history(0, 10)    # 最近10周期MA5值（含最新）
            self.ma5.history(10, 10)   # 10-20周期前的MA5值（不含最新）
        """
        """## 历史数据

        Args:
            lookback (int, optional): 偏移量. Defaults to 0.
            size (int, optional): 个数. Defaults to 1.

        Returns:
            float | int | bool | np.ndarray | Any

        Example:
        >>> self.XXX.history(0)等同于self.XXX.new等同于self.XXX.values[self.btindex]
            self.XXX.history(1)等同于self.XXX.prev等同于self.XXX.values[self.btindex-1]
            self.XXX.history(10)等同于self.XXX.values[self.btindex-10]
            self.XXX.history(0,10)等同于self.XXX.values[self.btindex+1-10:self.btindex+1]
            self.XXX.history(10,10)等同于self.XXX.values[self.btindex+1-10-10:self.btindex+1-10]
        """
        return self.__history(lookback, size, self.btindex)

    @cachedmethod(attrgetter('cache'))
    def __history(self, lookback=0, size=1, btindex=0):
        """
        缓存历史数据查询结果（内部方法，供history调用）
        计算实际索引位置，处理非维度匹配数据的边界，避免越界访问

        Args:
            lookback (int): 时间偏移量
            size (int): 数据长度
            btindex (int): 当前回测索引

        Returns:
            float | np.ndarray: 历史数据（单值或数组）
        """
        # 计算实际数据索引（当前索引 - 偏移量）
        index = btindex - lookback
        # 非维度匹配数据：限制索引不超过最后有效索引
        if not self._indsetting.dim_match:
            index = min(self._indsetting.last_index, index)
        # 多数据点：返回切片（size个数据）
        if size > 1:
            return self.values[index + 1 - size:index + 1]
        # 单数据点：返回指定索引值
        return self.values[index]

    # ------------------------------
    # Pandas数据转换接口
    # ------------------------------
    def to_pandas(self, filed: Optional[Union[str, list[str]]] = None, length: Optional[int] = None, offset: int = 0) -> pd.Series | pd.DataFrame:
        """
        转换为Pandas对象（方法接口）
        返回指定字段、长度的Pandas数据，支持偏移量控制，用于外部分析

        Args:
            filed (Optional[Union[str, list[str]]]): 字段名称（多维数据时有效）. Defaults to None.
            length (Optional[int]): 返回数据长度（None=全部）. Defaults to None.
            offset (int): 时间偏移量（0=最新，1=排除最新1个，依此类推）. Defaults to 0.

        Returns:
            pd.Series | pd.DataFrame: 
                - pd.Series: 一维数据或指定单个字段
                - pd.DataFrame: 多维数据或指定多个字段

        示例：
        >>> # 一维数据：返回最新100个数据
            self.ma5.to_pandas(length=100)
            # 多维数据：返回"high"和"low"字段，排除最新1个数据
            self.data.to_pandas(filed=["high", "low"], offset=1)
        """
        """### 返回最新的pandas数据

        #### args:
        >>> filed (Optional[Union[str, list[str]]]),如果是多维数据返回指定字段列.
            length (int):返回长度.
            offset (int):偏移量.默认0,无偏移.

        >>> return
            self.pandas_object.iloc[:self.btindex+1-offset]
            self.pandas_object.loc[:self.btindex+1-offset, filed]
            """
        # 多维数据且指定字段：按字段筛选
        if self._indsetting.isMDim and filed:
            data = self.pandas_object.loc[:self.btindex + 1 - offset, filed]
        # 其他情况：按行筛选（到当前索引-偏移量）
        else:
            data = self.pandas_object.iloc[:self.btindex + 1 - offset]
        # 指定长度：取最后N个数据，重置索引
        if length and length > 0:
            data = data.iloc[-length:]
            data.reset_index(drop=True, inplace=True)
        return data

    # ------------------------------
    # 多周期数据处理接口（上采样）
    # ------------------------------
    def upsample(self, **kwargs) -> Union[Line, series, dataframe]:
        """
        指标上采样（方法接口）
        将低周期数据转换为高周期（如1分钟→5分钟），支持缓存与参数重置

        Args:
            **kwargs: 上采样参数
                - reset (bool): 是否重置缓存（True=重新计算，False=使用缓存）. Defaults to False.
                - 其他参数：指标配置（如length=20）

        Returns:
            Union[Line, series, dataframe]: 上采样后的指标数据

        示例：
        >>> # 将1分钟MA5上采样为5分钟MA5
            self.ma5_5min = self.ma5.upsample(reset=True, length=20)
        """
        """### 指标上采样

        Kwargs:
        ---
            >>> kwargs (dict): 指标参数设置.

        Examples:
            >>> self.pmax()

        Returns:
        ---
            >>> Line | series | dataframe"""
        # 转换数据：优先使用缓存（reset=False时）
        if self.isresample:
            if not kwargs.pop("reset", False):
                if self._dataset.upsample_object is not None:
                    return self._dataset.upsample_object
            # 多策略指标转换：获取转换后的数据
            data = self.strategy_instances[self.sid]._multi_indicator_resample(
                self)
            if data is None:
                return self
            # 合并参数：指标设置 → 用户参数
            kwargs = {**self.ind_setting.copy_values, **kwargs}
            # 配置ID：同步转换ID
            kwargs.update(
                dict(
                    ismain=True,
                    _is_mir=True,
                    id=BtID(**self.id.filt_values(plot_id=self.resample_id))
                )
            )
            # 生成上采样数据对象（多维→dataframe，一维→series）
            if data.shape[1] != 1:
                data = dataframe(data, ** kwargs)
            else:
                data = series(data[:, 0], **kwargs)
            # 缓存上采样数据
            self._dataset.upsample_object = data
            data._upsample_name = "upsample"
            return data

        # 非转换数据：直接生成指标（用户参数覆盖默认）
        if kwargs:
            kwargs = {**self._indsetting.copy_values,
                      **self._plotinfo.copy_values, **kwargs}
            return type(self)(self.values, **kwargs)
        return self

    def __call__(self, **kwargs) -> Line | series | dataframe:
        """
        调用运算符重载（方法接口，与upsample功能一致）
        支持通过函数调用方式进行上采样（如self.ma5()等同于self.ma5.upsample()）

        Args:
            **kwargs: 上采样参数（同upsample）

        Returns:
            Union[Line, series, dataframe]: 上采样后的指标数据

        示例：
        >>> # 简化上采样调用
            self.ma5_5min = self.ma5(length=20)
        """
        """### 返回指标上采样数据
        ---

        Kwargs:
        ---
            >>> kwargs (dict): 指标设置.

        Example:
            >>> self.pmax()

        Returns:
        ---
            >>> Line | series | dataframe
        """
        return self.upsample(**kwargs)

    # ------------------------------
    # 多指标并行计算接口
    # ------------------------------
    def multi_apply(self, *args: Union[list[Callable, dict, dataframe], Multiply], **kwargs) -> tuple[series, dataframe]:
        """
        多指标并行计算（方法接口）
        支持批量计算多个指标，利用多线程提升效率，支持复杂指标组合

        Args:
            *args: 指标计算参数，每个参数为以下类型之一：
                - Multiply: 复杂指标组合（如Multiply(Ebsw, data=self.data)）
                - list: 简单指标配置（如[self.data.sma, dict(length=20)]）
            **kwargs: 并行计算参数：
                - max_workers: 最大线程数. Defaults to None.
                - thread_name_prefix: 线程名称前缀. Defaults to "".
                - initializer: 线程初始化函数. Defaults to None.
                - initargs: 初始化函数参数. Defaults to ().

        Returns:
            tuple[series, dataframe]: 计算后的指标列表（按输入顺序）

        示例：
        >>> # 批量计算多个指标
            self.ebsw, self.ma1, self.ma2 = self.multi_apply(
                Multiply(Ebsw, data=self.data),  # 复杂指标
                [self.data.sma, dict(length=20)], # 简单指标1
                [self.data.sma, dict(length=30)]  # 简单指标2
            )
        """
        """### 多指标计算
        >>> self.ebsw, self.ma1, self.ma2, self.buy_signal, self.sell_signal, self.ema40 = self.multi_apply(
                Multiply(Ebsw, data=self.data),
                [self.data.sma, dict(length=20),],
                [self.data.sma, dict(length=30),],
                [self.test1.t1.cross_up, dict(b=self.test1.t2)],
                [self.test1.t1.cross_down, dict(b=self.test1.t2),],
                Multiply(PandasTa.ema, dict(length=40), data=self.data))

        >>> kwargs:
                max_workers=kwargs.pop("max_workers",None)
                thread_name_prefix=kwargs.pop("thread_name_prefix","")
                initializer=kwargs.pop("initializer",None)
                initargs=kwargs.pop("initargs",())
        """
        return TPE.multi_run(*args, **kwargs)

    # ------------------------------
    # 数据迭代接口
    # ------------------------------
    def enumerate(self, *args: tuple[np.ndarray], start: Optional[int] = None, offset: int = 1) -> zip[tuple[Any, ...]]:
        """
        带索引的多数组迭代（方法接口）
        同步迭代多个可迭代对象，返回索引与对应值，支持偏移量控制

        Args:
            *args: 可迭代对象（需长度一致）.
            start (Optional[int]): 起始索引（None=从0开始）. Defaults to None.
            offset (int): 索引偏移量（如offset=1表示索引从1开始）. Defaults to 1.

        Returns:
            zip[tuple[Any, ...]]: 迭代器，每个元素为(index, val1, val2, ...)

        Raises:
            AssertionError: 输入非可迭代对象或长度不一致时触发

        示例：
        >>> # 迭代close和volume数组，索引从1开始
            for idx, close, vol in self.enumerate(self.close.values, self.volume.values, offset=1):
                print(f"索引{idx}: 收盘价{close}, 成交量{vol}")
        """
        """index,values...
        offset :int 偏移量"""
        # 校验输入：必须为可迭代对象
        assert all([isinstance(arg, Iterable) for arg in args]), "参数必须为可迭代对象"
        # 校验长度：所有输入必须长度一致
        assert len(set([len(arg) for arg in args])) == 1, "参数长度必须一致"
        # 确定迭代长度：start或数组长度
        length = start if isinstance(
            start, int) and start >= 0 else get_lennan(*args)
        # 构建迭代器：索引 + 所有输入数组
        result = [range(length + offset, len(args[0])),]
        result.extend(list(args))
        return zip(*result)

    # ------------------------------
    # 策略实例关联接口
    # ------------------------------
    @property
    def strategy_instances(self) -> StrategyInstances:
        """
        获取所有策略实例（属性接口）
        返回StrategyInstances对象，管理当前进程中的所有策略实例

        Returns:
            StrategyInstances: 策略实例集合
        """
        """### 所有策略实例"""
        return self._strategy_instances

    @property
    def strategy_instance(self) -> Strategy:
        """
        获取当前关联的策略实例（属性接口）
        基于strategy_id从strategy_instances中获取对应的策略实例

        Returns:
            Strategy: 关联的策略实例
        """
        """### 策略实例"""
        return self._strategy_instances[self.id.strategy_id]

    # ------------------------------
    # 底层数据操作接口（谨慎使用）
    # ------------------------------
    def _apply_operate_string(self, string: str) -> series | dataframe:
        """
        通过字符串执行数据操作（内部方法，供运算符重载用）
        动态执行字符串中的代码，修改底层数据，返回新的指标对象

        Args:
            string (str): 执行的代码字符串（需定义'value'变量）

        Returns:
            series | dataframe: 操作后的指标对象

        示例：
        >>> # 执行a + b操作
            self._apply_operate_string('value = self.pandas_object + other')
        """
        """
        pandas.core.internals.SingleBlockManager.set_values
        Set the values of the single block in place.

        Use at your own risk! This does not check if the passed values are
        valid for the current Block/SingleBlockManager (length, dtype, etc).
        """
        # 执行代码字符串（定义value变量）
        exec(string)
        # 获取执行结果
        data = locals()['value']
        # 转换为指标对象并返回
        return self.__set_data(data.values)

    def _set_data_object(self, data, values: np.ndarray):
        """
        直接设置数据对象的底层值（内部方法）
        修改Pandas对象的BlockManager，同步values数组，不触发数据校验

        Args:
            data: 目标数据对象（series/dataframe）
            values (np.ndarray): 新的数值数组（需与数据形状匹配）
        """
        # 修改Block的values与位置信息
        data._mgr.blocks[0].values = values
        data._mgr.blocks[0]._mgr_locs = BlockPlacement(slice(len(values)))

    def _set_object(self, values: np.ndarray):
        """
        直接设置当前对象的底层值（内部方法）
        修改自身的BlockManager，同步values数组，不触发数据校验

        Args:
            values (np.ndarray): 新的数值数组（需与数据形状匹配）
        """
        self._mgr.blocks[0].values = values
        self._mgr.blocks[0]._mgr_locs = BlockPlacement(slice(len(values)))

    def _inplace_pandas_object_values(self, data: pd.DataFrame | pd.Series) -> None:
        """
        原地替换Pandas对象的底层数据（内部方法，供inplace_values调用）
        处理多Block场景（如DataFrame含不同类型字段），同步数据类型与形状

        Args:
            data (pd.DataFrame | pd.Series): 新的Pandas对象（需与原数据形状匹配）
        """
        """
        Set the values of the single block in place.

        Use at your own risk! This does not check if the passed values are
        valid for the current Block/SingleBlockManager (length, dtype, etc).
        """
        # 更新数据集的Pandas对象
        self._dataset.pandas_object = data
        # 获取新数据的values数组
        values = data.values
        index = 0
        # 遍历所有Block，逐个替换值
        for block in self._mgr.blocks:
            existing_values = block.values
            shape = existing_values.shape
            target_dtype = existing_values.dtype

            # 提取当前Block对应的values（处理一维/二维）
            if len(values.shape) == 1:
                value = values
            else:
                if shape[0] == 1:
                    # 单行数据：按列提取
                    value = values[:, index]
                    value = value.reshape(shape)
                else:
                    # 多行数据：按列范围提取并转置
                    value = values[:, index:index + shape[0]].T

            # 处理datetime类型（确保类型匹配）
            if np.issubdtype(target_dtype, np.datetime64):
                value = value.astype(target_dtype)
            else:
                # 非datetime类型：转换为目标 dtype
                value = np.asarray(value, dtype=target_dtype)

            # 执行原地替换（优先处理有_ndarray属性的Block）
            if hasattr(existing_values, '_ndarray'):
                existing_values._ndarray[:] = value
            elif hasattr(existing_values, 'values'):
                np.copyto(existing_values.values, value)
            else:
                np.copyto(existing_values, value)

            # 更新Block索引（处理下一个Block）
            index += shape[0]

    def inplace_values(self, data: Union[pd.DataFrame, pd.Series]) -> None:
        """
        原地替换底层数据（方法接口）
        直接修改当前指标的底层数据，不创建新对象，**谨慎使用**（无数据校验）

        Args:
            data (pd.DataFrame | pd.Series): 新的Pandas数据（需与原数据形状一致）

        注意：
        - 仅支持Pandas对象输入
        - 形状不匹配时不执行操作
        - 可能导致数据一致性问题，建议仅在性能敏感场景使用
        """
        """### 替换底层数据，谨慎使用"""
        if type(data) not in PandasObject:
            return
        if self.shape != data.shape:
            return
        self._inplace_pandas_object_values(data)

    # ------------------------------
    # 运算符核心实现（内部方法）
    # ------------------------------
    def _apply_operator(self, other: series | dataframe | Any, op: str, reverse: bool = False, isbool: bool = False) -> series | dataframe | np.ndarray | Any:
        """
        执行运算符操作（内部方法，供重载运算符调用）
        处理指标与指标/标量的运算，支持反向运算与布尔值转换

        Args:
            other (series | dataframe | Any): 运算对象（指标或标量）
            op (str): 运算符（如'+', '>', '&'）
            reverse (bool, optional): 是否反向运算（如a - b 反向为 b - a）. Defaults to False.
            isbool (bool, optional): 是否为布尔运算（自动转换为bool类型）. Defaults to False.

        Returns:
            series | dataframe | np.ndarray | Any: 运算结果（指标对象或原生类型）
        """
        """### 操作运算返回内置指标数据"""
        # 处理运算对象：提取Pandas对象（若为指标）
        other = other.pandas_object if hasattr(
            other, 'pandas_object') else other

        # 布尔运算：自动转换为bool类型
        if isbool:
            if ispandasojb(other):
                # 双方均为Pandas对象：都转为bool
                str1, str2 = reverse and [
                    'other.astype(np.bool_)', 'self.pandas_object.astype(np.bool_)'] or [
                    'self.pandas_object.astype(np.bool_)', 'other.astype(np.bool_)']
            else:
                # 单方为Pandas对象：仅转换自身为bool
                str1, str2 = reverse and [
                    'other', 'self.pandas_object.astype(np.bool_)'] or [
                    'self.pandas_object.astype(np.bool_)', 'other']
        # 算术运算：保持原始类型
        else:
            str1, str2 = reverse and [
                'other', 'self.pandas_object'] or [
                'self.pandas_object', 'other']

        # 构建运算代码字符串并执行
        string = f'value=({str1} {op} {str2})'
        exec(string)
        data = locals()['value']

        # 转换为指标
        return self.__set_data(data.values)

    def __set_data(self, data: np.ndarray) -> series | dataframe:
        """
        将numpy数组转换为框架内置指标对象（内部方法，供运算/数据处理调用）
        根据输入数组维度自动选择返回series（一维）或dataframe（多维），
        并继承当前指标的配置参数（如ID、绘图信息），确保数据一致性。

        Args:
            data (np.ndarray): 待转换的numpy数组（需与原数据长度匹配）

        Returns:
            series | dataframe: 转换后的框架内置指标对象
                - series：输入为一维数组（shape=(N,)）时返回
                - dataframe：输入为多维数组（shape=(N, M)）时返回

        核心逻辑：
        1. 检测数组维度：通过shape判断是否为多维数据
        2. 继承配置参数：调用get_indicator_kwargs获取当前指标的配置（ID、绘图信息等）
        3. 生成指标对象：根据维度生成对应类型的内置指标，确保属性一致
        """
        if len(data.shape) > 1:
            # 多维数组（如N行M列）→ 转换为dataframe对象
            return dataframe(data, **self.get_indicator_kwargs(isindicator=True))
        else:
            # 一维数组（如N行1列）→ 转换为series对象
            return series(data, **self.get_indicator_kwargs(isindicator=True))

    # ------------------------------
    # Pandas方法适配装饰器
    # ------------------------------
    def __pandas_object_method(self, func: Callable) -> Callable:
        """
        类装饰器：将Pandas原生方法的返回结果自动转为框架内置指标类型
        解决Pandas方法（如mean、std、rolling）返回原生DataFrame/Series，
        与框架内置指标对象不兼容的问题，实现"Pandas方法调用→指标对象返回"的无缝衔接。

        Args:
            func (Callable): 待装饰的Pandas方法（如pd.Series.mean）

        Returns:
            Callable: 装饰后的方法（返回框架内置指标对象）

        核心逻辑：
        1. 异常捕获与重试：支持直接调用、通过pandas_object调用、参数转换后调用三级重试，
           确保在指标对象/原生Pandas对象混合输入时仍能正常执行。
        2. 结果转换：若返回结果为Pandas对象（DataFrame/Series），自动转换为框架内置指标，
           继承当前指标的ID、名称、绘图配置；若为标量/其他类型，直接返回。
        3. 配置补全：自动补全指标配置（如默认主图叠加、线条名称），减少用户配置成本。
        """
        """### 类装饰器:pandas方法返回的数据转为指标数据"""
        @wraps(func)  # 保留原方法的元信息（如名称、文档字符串）
        def wrapper(*args, **kwargs):

            try:
                # 一级尝试：直接调用原方法（适用于指标对象已实现该方法的场景）
                data: pd.Series | pd.DataFrame | Any = func(*args, **kwargs)
            except:
                try:
                    # 二级尝试：通过底层pandas_object调用（适用于指标对象未实现该方法的场景）
                    data = getattr(self.pandas_object, func.__name__)(
                        *args, **kwargs)
                except:
                    # 三级尝试：转换所有参数为Pandas对象（适用于参数含指标对象的场景）
                    # 处理位置参数：将指标对象转为Pandas对象
                    args = list(args)
                    for i, arg in enumerate(args):
                        if type(arg) in BtIndType:
                            args[i] = arg.pandas_object
                    # 处理关键字参数：将指标对象转为Pandas对象
                    for k, v in kwargs.items():
                        if type(v) in BtIndType:
                            kwargs[k] = v.pandas_object
                    # 重新调用Pandas方法
                    data = getattr(self.pandas_object, func.__name__)(
                        *args, **kwargs)

            # 结果转换：Pandas对象→框架内置指标
            if isinstance(data, (pd.DataFrame, pd.Series)):
                # 补全默认配置：未指定overlap时默认主图叠加
                if "overlap" not in kwargs:
                    kwargs.update(dict(overlap=True))  # 原代码笔误"overlpa"已修正
                # 继承ID：复制当前指标的ID，确保关联关系一致
                id = self.id.copy()
                # 指标名称：默认使用Pandas方法名（如"mean"、"rolling"）
                ind_name = func.__name__

                # 多维结果（DataFrame）→ dataframe对象
                if len(data.shape) > 1:
                    # 线条名称：优先从kwargs获取，否则使用DataFrame列名
                    lines = kwargs.get("lines", list(data.columns))
                    # 校验：线条数量需与列数一致
                    assert lines and len(lines) == data.shape[1], \
                        f"线条数量（{len(lines)}）与数据列数（{data.shape[1]}）不匹配"
                    return dataframe(
                        data,
                        id=id,
                        sname=ind_name,  # 策略内名称=方法名
                        ind_name=ind_name,  # 指标类型名=方法名
                        lines=lines,
                        **kwargs
                    )
                # 一维结果（Series）→ series对象
                else:
                    # 线条名称：优先从kwargs获取，否则使用当前指标的sname
                    if "lines" not in kwargs:
                        lines = kwargs.get("lines", [self.sname,])
                    # 校验：线条数量需与一维数据匹配（仅1个）
                    assert lines and len(lines) == len(data.shape), \
                        f"线条数量（{len(lines)}）与一维数据不匹配"
                    return series(
                        data,
                        id=id,
                        sname=ind_name,
                        ind_name=ind_name,
                        lines=lines,
                        **kwargs
                    )
            # 非Pandas结果（如标量、numpy数组）→ 直接返回
            else:
                return data
        return wrapper

    # ------------------------------
    # 多条件批量数据更新
    # ------------------------------
    def ifs(self, *args, other: Union[pd.Series, np.ndarray, Any] = None, filed: Optional[str] = "") -> Optional[series]:
        """
        多条件批量数据更新（方法接口）
        类似Excel的IFS函数，按顺序处理多组「条件-值」对，
        满足条件时替换目标序列的值，不满足则保持原值，最终返回处理后的指标对象。

        核心场景：
        - 策略信号生成（如突破均线开多、跌破均线平仓）
        - 数据清洗（如异常值替换、区间划分）
        - 动态参数调整（如不同行情下使用不同周期的MA）

        Args:
            *args: 可变参数，需为偶数个，格式为(cond1, value1, cond2, value2, ...)
                cond (np.ndarray | pd.Series | series): 布尔条件（长度需与目标序列一致）
                value (Any): 满足cond时替换的值（支持标量、数组，需与序列元素类型兼容）
            other (Union[pd.Series, np.ndarray, Any], optional): 待处理的目标序列. Defaults to None.
                - 未指定时：自动从当前指标提取（多维取指定字段，一维取自身）
                - 标量/可迭代对象：自动转换为与当前指标长度一致的Series
            filed (Optional[str], optional): 多维指标的目标字段名. Defaults to "".
                - other未指定且为多维指标时，用于指定待处理的字段（如"close"、"ma5"）
                - 为空或字段不存在时，默认使用第一个线条（self.lines[0]）

        Returns:
            Optional[series]: 处理后的框架内置series对象；参数不合法时返回None

        关键逻辑：
        1. 参数校验：确保args为偶数个（成对的条件-值），避免逻辑错误
        2. 目标序列初始化：统一将other转换为Pandas Series，确保处理逻辑一致
        3. 条件迭代执行：按顺序应用每组条件，后执行的条件会覆盖先执行的结果（优先级更高）
        4. 结果转换：将处理后的Series转为框架内置series对象，保持指标属性一致性

        示例：
        >>> # 1. 策略信号生成：MA5上穿MA10开多，MA5下穿MA10平多
            ma5_cross_up_ma10 = self.ma5.cross_up(self.ma10)  # 开多条件
            ma5_cross_down_ma10 = self.ma5.cross_down(self.ma10)  # 平多条件
            self.long_signal = self.ifs(
                ma5_cross_up_ma10, 1,    # 满足开多条件→设为1（开多信号）
                ma5_cross_down_ma10, 0,  # 满足平多条件→设为0（平多信号）
                other=0  # 初始值为0（无信号）
            )

        >>> # 2. 数据清洗：替换收盘价异常值（>3倍标准差设为均值，<0设为0）
            close = self.data.close
            cond1 = close > close.mean() + 3 * close.std()  # 上异常值
            cond2 = close < 0  # 负价格（无效）
            self.clean_close = self.ifs(
                cond1, close.mean(),  # 上异常值→替换为均值
                cond2, 0,             # 负价格→替换为0
                other=close           # 目标序列为原始收盘价
            )
        """
        # 参数校验：args必须为偶数个（成对的条件-值）
        if args and len(args) % 2 == 0:
            args = list(args)
            # 目标序列初始化：处理other的不同输入类型
            if isinstance(other, (bool, int, float)):
                # 标量→转换为与当前指标长度一致的Series（填充标量值）
                other = pd.Series(self.full(other))
            # 原代码笔误"len(other=self.V)"已修正
            elif isinstance(other, Iterable) and len(other) == self.V:
                # 可迭代对象（长度匹配）→ 转换为Series
                other = pd.Series(other)
            else:
                # 未指定other→从当前指标提取目标序列
                if self.H != 1:
                    # 多维指标：按filed提取字段，默认取第一个线条
                    if filed not in self.lines:
                        filed = self.lines[0]
                    other = getattr(self, filed)
                else:
                    # 一维指标：直接取自身
                    other = self
                # 转换为Pandas Series（统一处理格式）
                other = other.pandas_object

            # 迭代执行多组条件-值对（后条件覆盖前条件）
            for i in range(0, len(args), 2):
                cond, value = args[i], args[i+1]
                # 核心逻辑：满足cond时用value替换，否则保持other原值
                # 注：原代码other.where(cond, value)逻辑反了，已修正为np.where
                other = np.where(cond, value, other)

            # 转换为框架内置series对象并返回
            return series(other)
        # 参数不合法（如args为奇数个）→ 返回None

    # ------------------------------
    # 便捷数据生成接口
    # ------------------------------
    @property
    def ones(self) -> series:
        """
        生成全1序列（属性接口）
        返回与当前指标长度一致的全1 series对象，用于权重计算、信号标记等场景。

        Returns:
            series: 全1序列（长度=self.V）

        示例：
        >>> # 等权重组合2个指标
            weight = self.ones * 0.5  # 权重=0.5
            combined_ind = self.ma5 * weight + self.ma10 * weight
        """
        return series(np.ones(self.V))

    def full(self, value=np.nan) -> series:
        """
        生成填充指定值的序列（方法接口）
        返回与当前指标长度一致、所有元素为指定值的series对象，
        用于初始化、缺失值填充、固定阈值标记等场景。

        Args:
            value (Any, optional): 填充值（支持标量、np.nan）. Defaults to np.nan.

        Returns:
            series: 填充后的序列（长度=self.V）

        示例：
        >>> # 初始化空信号序列（默认值np.nan）
            self.signal = self.full()
            # 生成固定止损阈值序列（值=1000）
            self.stop_loss = self.full(1000)
        """
        return series(np.full(self.V, value))

    @property
    def zeros(self) -> series:
        """
        生成全0序列（属性接口）
        返回与当前指标长度一致的全0 series对象，用于初始化、无信号标记等场景。

        Returns:
            series: 全0序列（长度=self.V）

        示例：
        >>> # 初始化收益序列（默认值0）
            self.daily_return = self.zeros
        """
        return series(np.zeros(self.V))

    # ------------------------------
    # 哈希与比较方法（确保实例可哈希）
    # ------------------------------
    def __eq__(self, other):
        """
        重写相等比较方法（内部方法）
        确保指标实例可通过身份（内存地址）比较相等性，而非值比较，
        避免因值相同导致的哈希冲突（如两个MA5指标值相同但属于不同合约）。

        Args:
            other (Any): 比较对象

        Returns:
            bool: True=对象身份相同，False=对象身份不同
        """
        """### 比较"""
        return object().__eq__(other)

    def __hash__(self):
        """
        重写哈希方法（内部方法）
        基于对象身份（内存地址）生成哈希值，确保指标实例可放入set/dict等哈希容器，
        支持多指标的去重、关联等操作（如多策略共享指标）。

        Returns:
            int: 对象的哈希值（与内存地址关联）
        """
        """### 确保实例可哈希"""
        return object.__hash__(self)

    # ------------------------------
    # 属性访问拦截（Pandas方法自动适配）
    # ------------------------------
    def __getattribute__(self, item) -> Line | series | dataframe | pd.Series | pd.DataFrame | Any:
        """
        重写属性访问方法（内部方法）
        拦截Pandas方法的访问请求，自动应用__pandas_object_method装饰器，
        实现"调用指标的Pandas方法→返回框架内置指标对象"的无缝衔接，无需手动转换。

        Args:
            item (str): 属性/方法名称（如"mean"、"rolling"、"sname"）

        Returns:
            Any: 
                - 若为Pandas方法：返回装饰后的方法（返回指标对象）
                - 若为普通属性/方法：返回原始结果（如sname、btindex）
        """
        """### 将pandas自身函数计算的结果转为内置指标类型"""
        # 拦截Pandas方法：自动装饰并返回
        if item in pandas_method:
            return self.__pandas_object_method(super().__getattribute__(item))
        # 普通属性/方法：直接返回原始结果
        return super().__getattribute__(item)

    # ------------------------------
    # 滚动窗口计算接口
    # ------------------------------
    def rolling(
        self,
        window=None,
        min_periods=None,
        center=False,
        win_type=None,
        on=None,
        axis=0,
        closed=None,
        step=None,
        method="single",
    ) -> BtRolling:
        """
        滚动窗口计算（方法接口）
        与Pandas的rolling方法用法完全一致，但返回框架自定义的BtRolling对象，
        支持后续调用rolling_apply、mean、std等方法时直接返回内置指标对象，
        无需手动转换Pandas结果。

        核心场景：
        - 技术指标计算（如滚动均线MA、滚动标准差Bollinger Band）
        - 风险指标计算（如滚动最大回撤、滚动夏普比率）
        - 特征工程（如滚动成交量均值、滚动价格波动）

        Args:
            window (int | str | pd.Timedelta, optional): 窗口大小. Defaults to None.
                - 整数：固定窗口长度（如5=5个时间步）
                - 字符串：时间窗口（如"5D"=5天，需数据含datetime索引）
                - pd.Timedelta：时间窗口（如pd.Timedelta(days=5)）
            min_periods (int, optional): 窗口内最小非缺失值数量. Defaults to None.
                - 小于该数量时结果为NaN，默认等于window（需窗口完全填充）
            center (bool, optional): 是否将窗口中心作为结果位置. Defaults to False.
                - True：结果对齐窗口中心，False：结果对齐窗口右侧（默认）
            win_type (str, optional): 窗口权重类型. Defaults to None.
                - 如"boxcar"（矩形窗，默认）、"hanning"（汉宁窗）、"blackman"（布莱克曼窗）
            on (str, optional): 用于滚动的列名（仅DataFrame有效）. Defaults to None.
            axis (int, optional): 滚动轴（0=行方向，1=列方向）. Defaults to 0.
            closed (str, optional): 窗口闭合方式（仅整数窗口有效）. Defaults to None.
                - "right"（右闭，默认）、"left"（左闭）、"both"（两端闭）、"neither"（两端开）
            step (int, optional): 窗口步长（每step个数据计算一次）. Defaults to None.
                - 默认1（每个数据都计算）
            method (str, optional): 计算方法（"single"=单线程，"table"=矢量化）. Defaults to "single".

        Returns:
            BtRolling: 框架自定义的滚动窗口对象，支持链式调用后续计算方法

        示例：
        >>> # 1. 计算5日滚动均线（MA5）
            self.ma5 = self.data.close.rolling(window=5).mean()  # 返回series对象

        >>> # 2. 计算20日滚动标准差（用于布林带）
            self.std20 = self.data.close.rolling(window=20).std()  # 返回series对象

        >>> # 3. 多列同时计算滚动均值（DataFrame）
            self.rolling_mean = self.data.loc[:, ["open", "high", "low", "close"]].rolling(window=10).mean()  # 返回dataframe对象
        """
        """### 与pandas数据rolling方法使用一致,返回的是dataframe或series数据"""
        return BtRolling(
            self,
            window=window,
            min_periods=min_periods,
            center=center,
            win_type=win_type,
            on=on,
            axis=axis,
            closed=closed,
            step=step,
            method=method
        )

    # ------------------------------
    # 滚动窗口自定义函数计算
    # ------------------------------
    @tobtind(lib="pta")
    def rolling_apply(self, func: Callable, window: int, prepend_nans: bool = True, n_jobs: int = 1, **kwargs) -> series | dataframe:
        """
        滚动窗口自定义函数计算（方法接口）
        在滚动窗口上应用自定义函数，支持并行计算，结果自动转为框架内置指标对象，
        解决Pandas rolling.apply不支持多输出、效率低的问题，适用于复杂指标计算。

        核心优势：
        - 多输出支持：自定义函数可返回多个值（如同时计算均值、标准差），自动生成多线条指标
        - 并行加速：通过n_jobs控制并行线程数，处理大规模数据时提升效率
        - 类型兼容：自动适配一维（series）/多维（dataframe）输入，返回对应类型的指标对象

        Args:
            func (Callable): 应用于每个滚动窗口的自定义函数
                - 输入：窗口内的数据（series→1D np.ndarray，dataframe→2D np.ndarray或多参数1D数组）
                - 输出：单个值或多个值（如返回(mean, std)生成两个线条）
            window (int): 滚动窗口大小（整数，必须>0）
            prepend_nans (bool, optional): 是否在结果前填充NaN. Defaults to True.
                - True：前window-1个位置填充NaN（默认，符合技术指标习惯）
                - False：从第一个窗口开始返回结果（前window-1个位置丢弃）
            n_jobs (int, optional): 并行计算的线程数. Defaults to 1.
                - 1：单线程（默认，避免线程开销）
                - >1：多线程（需func线程安全，适合CPU密集型计算）
                - -1：使用所有可用CPU核心
            **kwargs: 扩展参数（如lines=[]指定线条名称、overlap=True设置主图叠加）

        Returns:
            series | dataframe: 
                - series：func返回单个值时（1D结果）
                - dataframe：func返回多个值时（2D结果）

        示例详解：
        #### 1. 一维输入（series）→ 多输出（两个线条）
        >>> #自定义函数：计算窗口内收盘价的最小值和最大值
            def calc_window_min_max(close: np.ndarray) -> tuple[float, float]:
                \"\"\"
                close: 窗口内收盘价（1D np.ndarray，长度=window）
                返回：窗口内最小值、最大值
                \"\"\"
                return close.min(), close.max()
            #调用rolling_apply：5日窗口，生成两个线条（"close_min"、"close_max"）
            self.window_min_max = self.data.close.rolling_apply(
                func=calc_window_min_max,
                window=5,
                lines=["close_min", "close_max"],  # 指定线条名称
                overlap=True  # 主图叠加（与K线同图显示）
            )
            #返回结果：dataframe对象，含"close_min"和"close_max"两列

        #### 2. 多维输入（dataframe多列）→ 多输出（两个线条）
        >>> #自定义函数：计算窗口内最高价均值和最低价标准差（多参数输入）
            def calc_high_mean_low_std(high: np.ndarray, low: np.ndarray, a: int = 1) -> tuple[float, float]:
                \"\"\"
                high：窗口内最高价（1D np.ndarray）
                low：窗口内最低价（1D np.ndarray）
                a：自定义参数（示例用，无实际意义）
                返回：最高价均值、最低价标准差
                \"\"\"
                return high.mean() * a, low.std()
            #调用rolling_apply：3日窗口，指定输入列，生成两个线条
            self.high_low_stats = self.data.rolling_apply(
                func=calc_high_mean_low_std,
                window=3,
                lines=["high_mean", "low_std"],  # 线条名称
                overlap=dict(high_mean=True, low_std=False),  # 分别设置叠加（high_mean主图，low_std副图）
                a=2  # 传递自定义参数a=2
            )
            #返回结果：dataframe对象，含"high_mean"和"low_std"两列

        #### 3. 多维输入（dataframe）→ 多输出（两个线条，单参数接收）
        >>> #自定义函数：接收2D数组（所有列），计算均值和标准差
            def calc_df_mean_std(df: np.ndarray) -> tuple[float, float]:
                \"\"\"
                df：窗口内所有列的数据（2D np.ndarray，形状=(window, 列数)）
                返回：所有元素的均值、所有元素的标准差
                \"\"\"
                return df.mean(), df.std()
            #调用rolling_apply：3日窗口，输入OHLC四列
            self.ohlc_stats = self.data.loc[:, FILED.OHLC].rolling_apply(
                func=calc_df_mean_std,
                window=3,
                lines=["ohlc_mean", "ohlc_std"],
                overlap=dict(ohlc_mean=True, ohlc_std=False)
            )
            #返回结果：dataframe对象，含"ohlc_mean"和"ohlc_std"两列
        """
        ...  # 方法实现细节（如并行计算、窗口滑动、结果拼接）省略，需结合框架底层逻辑补充

    # ------------------------------
    # 绘图数据组装（供前端渲染）
    # ------------------------------

    def _get_plot_datas(self, key: str) -> tuple:
        """
        组装绘图所需的完整数据（内部方法，供策略绘图模块调用）
        整合指标的配置信息（ID、线条、颜色）与数值数据，生成前端可直接渲染的结构化数据，
        支持主图叠加/副图显示、多线条分类、自定义水平线等功能。

        Args:
            key (str): 绘图标识（如合约代码、指标分组名，用于区分不同绘图对象）

        Returns:
            tuple: 绘图结构化数据，包含13个元素：
                1. plot_id (int): 绘图分组ID（用于多子图区分）
                2. isplot (list[bool] | bool): 线条显示开关（多线条为列表，单线条为bool）
                3. name (str | list[str]): 指标策略内名称（多分组为列表）
                4. lines (list[str]): 线条标识名（含key前缀，避免重复）
                5. _lines (list[str]): 线条原始名称（无前缀）
                6. ind_names (str | list[str]): 指标类型名（多分组为列表）
                7. overlaps (bool | list[bool]): 主图叠加开关（多分组为列表）
                8. categorys (CategoryString | list[CategoryString]): 绘图分类（多分组为列表）
                9. indicators (np.ndarray): 指标数值数据（形状适配绘图需求）
                10. doubles (list[int] | bool): 多分组线条索引（无分组为False）
                11. _ind_plotinfo (dict): 指标绘图配置（颜色、线型、水平线等）
                12. span (dict): 水平线样式配置（如RSI的20/80分界线）
                13. _signal (dict): 交易信号样式配置（如开多信号的颜色、标记）

        核心逻辑：
        1. 基础信息提取：获取plot_id、数据维度、数值数组等基础信息
        2. 多分组处理：当部分线条主图叠加、部分副图显示时，拆分为两个分组（主图组+副图组）
        3. 数据适配：统一数值数组形状（确保前端渲染兼容），生成线条标识名（避免多指标重名）
        4. 配置整合：合并绘图配置（颜色、线型）、水平线、信号样式，生成完整配置字典
        5. 自定义指标标记：记录自定义指标的名称与长度，供前端特殊处理
        """
        """### 获取内置指标画图数据"""
        # 1. 基础信息提取
        plot_id = self.id.plot_id  # 绘图分组ID（多子图区分）
        isndim = self._indsetting.isMDim  # 是否为多维数据（dataframe/series）
        # 数值数组适配：多维直接使用，一维转为(N,1)形状（统一前端处理）
        value = self.values if isndim else self.values.reshape((self.V, 1))
        overlap = self.overlap  # 主图叠加配置（bool/dict）
        overlap_isbool = isinstance(overlap, bool)  # 是否为统一叠加开关
        # 线条名称提取：支持Lines对象或普通列表
        vlines = self.lines.values if hasattr(
            self.lines, "values") else self.lines

        # 2. 多分组处理（部分线条主图、部分副图）
        if not overlap_isbool and len(set(overlap.values())) > 1:
            # 提取主图/副图线条索引
            values = list(overlap.values())
            index1 = [ix for ix, vx in enumerate(values) if vx]  # 主图叠加线条索引
            index2 = [ix for ix, vx in enumerate(values) if not vx]  # 副图线条索引

            # 组装多分组数据（主图组+副图组）
            # 显示开关：按分组提取对应线条的isplot
            isplot = [
                [p for ix, p in enumerate(self.isplot.values()) if ix in index]
                for index in [index1, index2]
            ]
            # 指标名称：每个分组复用当前指标的sname
            name = [self.sname] * 2
            # 线条标识名：添加key前缀（避免多指标重名，如"BTC/USDT_ma5"）
            lines = [
                ["_".join([key, n])
                 for ix, n in enumerate(vlines) if ix in index]
                for index in [index1, index2]
            ]
            # 线条原始名称：无前缀，用于显示
            _lines = [
                [n for ix, n in enumerate(vlines) if ix in index]
                for index in [index1, index2]
            ]
            # 指标类型名：每个分组复用当前指标的ind_name
            ind_names = [key, ] * 2
            # 叠加开关：主图组=True，副图组=False
            overlaps = [True, False]
            # 绘图分类：每个分组复用当前指标的category
            categorys = [str(self.category), ] * 2
            # 数值数据：按分组提取对应列
            indicators = [value[:, index] for index in [index1, index2]]
            # 多分组标记：记录所有线条的索引（用于前端关联）
            doubles = index1 + index2

        # 3. 单分组处理（所有线条统一主图/副图）
        else:
            doubles = False  # 无多分组
            # 统一叠加开关：dict取所有值的逻辑与（全True才主图），bool直接使用
            _overlap = overlap if overlap_isbool else all(overlap.values())
            # 显示开关：多维为列表（每列一个开关），一维为单bool
            isplot = isndim and list(self.isplot.values()) or [self.isplot, ]
            # 指标名称：单分组直接使用当前指标的sname
            name = self.sname
            # 线条标识名：主图叠加或多线条时添加key前缀，否则直接用key
            lines = (["_".join([key, n]) for n in vlines]
                     ) if _overlap or len(vlines) > 1 else [key, ]
            # 线条原始名称：直接使用vlines
            _lines = vlines
            # 指标类型名：单分组直接使用key
            ind_names = key
            # 叠加开关：统一开关值
            overlaps = _overlap
            # 绘图分类：单分组直接使用当前指标的category
            categorys = str(self.category)
            # 数值数据：直接使用适配后的value
            indicators = value

        # 4. 自定义指标标记：记录自定义指标的名称与长度（供前端特殊处理）
        if self.iscustom:
            self.strategy_instance._custom_ind_name.update(
                {key: len(name[self.plot_id]) - 1})

        # 5. 绘图配置整合
        # 基础绘图配置：优先取plotinfo的vars，无则取plotinfo自身
        v_plotinfo = self._plotinfo.vars if hasattr(
            self.plotinfo, "vars") else self._plotinfo
        # 蜡烛图特殊处理：添加数据源标识（key）
        if self.category == 'candles':
            v_plotinfo.update(dict(source=key))
        # 完整绘图配置
        _ind_plotinfo = v_plotinfo
        # 水平线配置：从plotinfo获取spanstyle
        span = v_plotinfo.get("spanstyle", {})
        # 信号样式配置：有交易信号时从plotinfo获取signalstyle
        _signal = v_plotinfo.get("signalstyle", {}) if hasattr(
            self, "_issignal") else {}

        # 返回结构化绘图数据
        return (
            plot_id, isplot, name, lines, _lines, ind_names, overlaps,
            categorys, indicators, doubles, _ind_plotinfo, span, _signal
        )

    # ------------------------------
    # 索引访问重载（支持[]操作符）
    # ------------------------------
    def __getitem__(self, key) -> Union[Line, series, dataframe, Any]:
        """
        重载索引访问（[]操作符，内部方法）
        支持通过索引/字段名获取数据，自动将返回的Pandas对象转为框架内置指标，
        确保索引操作后仍保持指标对象的一致性（如属性、配置、运算能力）。

        支持的索引类型：
        - 整数（如self.data[0] → 第一行数据）
        - 切片（如self.data[10:20] → 第11-20行数据）
        - 字符串（如self.data["close"] → "close"字段）
        - 布尔数组（如self.data[self.data.close > 10000] → 收盘价>10000的行）
        - 元组（如self.data[:, "close"] → 所有行的"close"字段）

        Args:
            key (int | slice | str | np.ndarray | tuple): 索引键

        Returns:
            Union[Line, series, dataframe, Any]: 
                - 若返回Pandas对象（DataFrame/Series）→ 转为框架内置指标
                - 若返回标量/其他类型 → 直接返回

        核心逻辑：
        1. 调用父类索引方法：获取原始结果（Pandas对象/标量）
        2. 结果转换：若为Pandas对象，调用pandas_to_btind转为内置指标，
           继承当前指标的配置（ID、长度、绘图信息），确保属性一致
        3. 特殊处理：元组索引（如多维数据的行列选择）时，提取正确的字段名，
           确保线条名称与原始字段匹配
        """
        # 1. 调用父类方法获取原始索引结果
        data = super().__getitem__(key)

        # 2. 转换Pandas对象为框架内置指标
        if isinstance(data, (pd.Series, pd.DataFrame)):
            # 处理元组索引（如(dataframe[:, "close"]) → 提取字段名"close"）
            if isinstance(key, tuple) and len(key) > 1:
                key = key[1]  # 取元组的第二个元素（字段名/列索引）
                # 列索引为整数时，转为对应的线条名称（如0→self.obj.lines[0]）
                if isinstance(key, int):
                    key = self.obj.lines[key]
            # 调用工具函数转为内置指标，继承当前指标的配置
            return pandas_to_btind(
                data,
                key=key,  # 线条/字段名称
                length=self.V,  # 数据长度（与当前指标一致）
                kwargs=self.get_indicator_kwargs()  # 继承配置（ID、绘图信息等）
            )
        # 3. 非Pandas对象（如标量）→ 直接返回
        return data

    def __setitem__(self, key, value):
        """
        重载索引赋值（[]=操作符，内部方法）
        支持通过索引/字段名修改数据，同步更新底层Pandas对象与上采样数据，
        确保数据修改后所有关联对象的一致性（如多周期指标、绘图数据）。

        Args:
            key (int | slice | str | np.ndarray | tuple): 索引键（同__getitem__）
            value (Any): 待赋值的数据（支持标量、数组、Pandas对象、指标对象）

        核心逻辑：
        1. 父类赋值：调用父类方法修改当前指标的底层数据
        2. 同步Pandas对象：更新_dataset.pandas_object，确保底层数据一致
        3. 上采样数据更新：若存在上采样数据，重新计算并更新，避免数据不一致
        4. 多维指标处理：若为dataframe，重新设置Line对象，确保线条与数据匹配
        """
        # 1. 调用父类方法执行赋值操作
        super().__setitem__(key, value)
        # 2. 同步更新底层Pandas对象（确保数据一致性）
        self._dataset.pandas_object.__setitem__(key, value)
        # 3. 上采样数据更新：若存在上采样数据，重置并重新计算
        if self._dataset.upsample_object is not None:
            setattr(
                self.strategy_instances[self.sid],  # 获取关联的策略实例
                self._upsample_name,  # 上采样数据的策略内名称
                self.upsample(reset=True)  # 重置并重新计算上采样数据
            )
        # 4. 多维指标处理：重新设置Line对象，确保线条与修改后的数据匹配
        if self._indsetting.isMDim:
            set_lines(self, key)  # 重新绑定Line对象到修改后的字段

    @property
    def iloc(self) -> iLocIndexer:
        """
        ### 基于**整数位置**的索引器（按行/列的位置序号选择数据）

        核心特点：
        - 位置从 0 开始（如第 1 行对应 0，第 2 列对应 1）
        - 支持切片、整数列表、布尔数组等输入（详见示例）
        - 越界索引会报错（切片除外，兼容 Python 切片语义）

        允许的输入类型：
        1. 单个整数（如 5 → 选择第 6 行/列）
        2. 整数列表/数组（如 [4,3,0] → 按顺序选择第 5、4、1 行/列）
        3. 切片（如 1:7 → 选择第 2 到第 7 行/列，包含边界）
        4. 布尔数组（长度需与行/列数一致，True 表示选择）
        5. 元组（如 (0,1) → 选择第 1 行第 2 列）

        返回值：
        - 框架内置指标数据（单个值/`series`/`dataframe`，非原生 Pandas 对象）

        示例：
        >>> df.iloc[0]          # 选择第 1 行（返回 series 类型）
        >>> df.iloc[[0,2], [1]] # 选择第 1、3 行，第 2 列（返回 dataframe 类型）
        """
        return iLocIndexer("iloc", self)

    @property
    def loc(self) -> LocIndexer:
        """
        ### 基于**标签（名称）** 的索引器（按行/列的标签选择数据）

        核心特点：
        - 依赖索引标签（如行标签 'cobra'、列标签 'max_speed'）
        - 切片包含首尾边界（与 Python 原生切片不同）
        - 支持条件筛选（如按列值过滤行）

        允许的输入类型：
        1. 单个标签（如 'a' 或 5 → 选择标签为 'a'/5 的行/列）
        2. 标签列表/数组（如 ['a','b'] → 按顺序选择指定标签）
        3. 标签切片（如 'a':'f' → 选择标签从 'a' 到 'f' 的行/列，包含边界）
        4. 布尔数组/Series（长度/索引需与行/列匹配）
        5. 函数（输入为当前对象，返回上述合法输入）

        返回值：
        - 框架内置指标数据（单个值/`series`/`dataframe`，非原生 Pandas 对象）

        示例：
        >>> df.loc['viper']          # 选择行标签 'viper'（返回 series 类型）
        >>> df.loc[df['shield']>6]   # 选择 'shield' 列值大于 6 的行（返回 dataframe 类型）
        """
        return LocIndexer("loc", self)

    @property
    def at(self) -> AtIndexer:
        """
        ### 快速访问**单个值**的标签索引器（按行+列标签定位单个数据）

        核心特点：
        - 仅用于获取/设置「单个值」（比 loc 更高效）
        - 完全基于标签（非位置），需同时指定行和列标签

        注意事项：
        - 标签不存在会报 KeyError
        - 仅支持标量标签（不支持列表/切片）

        返回值：
        - 框架内置指标数据（单个值，非 Pandas 对象）

        示例：
        >>> df.at[4, 'B']    # 选择行标签 4、列标签 'B' 的值（返回单个数值）
        >>> df.at[4, 'B'] = 10  # 设置该位置的值为 10
        """
        return AtIndexer("at", self)

    @property
    def iat(self) -> iAtIndexer:
        """
        ### 快速访问**单个值**的位置索引器（按行+列的整数位置定位单个数据）

        核心特点：
        - 仅用于获取/设置「单个值」（比 iloc 更高效）
        - 完全基于整数位置（从 0 开始）

        注意事项：
        - 位置越界会报 IndexError
        - 仅支持标量位置（不支持列表/切片）

        返回值：
        - 框架内置指标数据（单个值，非 Pandas 对象）

        示例：
        >>> df.iat[1, 2]    # 选择第 2 行、第 3 列的值（返回单个数值）
        >>> df.iat[1, 2] = 10  # 设置该位置的值为 10
        """
        return iAtIndexer("iat", self)


class PandasTa:
    """### pandas_ta指标指引
    pandas_ta 指标适配类，用于将 pandas_ta 库中的技术指标计算结果转换为框架内置的指标数据类型（series/dataframe）

    核心功能：
    - 封装 pandas_ta 库的各类技术指标，提供统一的调用接口
    - 通过 @tobtind 装饰器自动处理指标参数校验、计算逻辑调用和返回值转换，确保输出为框架兼容的 series 或 dataframe
    - 支持多维度技术分析场景，覆盖蜡烛图形态、趋势跟踪、动量判断、波动率计算等量化交易核心需求
    - 内置指标分类体系，便于按业务场景快速定位和调用目标指标

    指标分类与包含列表：
    该类支持的指标按功能划分为以下 9 大类，具体包含指标如下：

    1. 蜡烛图分析（Candles）
       - 功能：蜡烛图形态识别、特殊蜡烛图转换（如布林带K线、Z评分标准化蜡烛图）
       - 包含指标：cdl_pattern（蜡烛图形态识别）、cdl_z（Z评分标准化蜡烛图）、ha（Heikin-Ashi布林带K线）

    2. 周期分析（Cycles）
       - 功能：识别市场价格的周期性规律，辅助判断趋势转折节点
       - 包含指标：ebsw（周期检测指标）

    3. 动量指标（Momentum）
       - 功能：衡量价格变化的速度和力度，判断趋势强度与潜在反转
       - 包含指标：ao、apo、bias、bop、brar、cci、cfo、cg、cmo、coppock、cti、er、eri、fisher、inertia、kdj、kst、macd、mom、pgo、ppo、psl、pvo、qqe、roc、rsi、rsx、rvgi、slope、smi、squeeze、squeeze_pro、stc、stoch、stochrsi、td_seq、trix、tsi、uo、willr

    4. 重叠指标（Overlap）
       - 功能：通过价格平滑、均线拟合等方式，凸显价格趋势方向
       - 包含指标：alma、dema、ema、fwma、hilo、hl2、hlc3、hma、ichimoku、jma、kama、linreg、mcgd、midpoint、midprice、ohlc4、pwma、rma、sinwma、sma、ssf、supertrend、swma、t3、tema、trima、vidya、vwap、vwma、wcp、wma、zlma

    5. 收益指标（Performance）
       - 功能：计算资产的收益情况，量化投资回报表现
       - 包含指标：log_return（对数收益）、percent_return（百分比收益）

    6. 统计指标（Statistics）
       - 功能：基于统计方法分析价格分布特征、离散程度等
       - 包含指标：entropy（熵值）、kurtosis（峰度）、mad（平均绝对偏差）、median（中位数）、quantile（分位数）、skew（偏度）、stdev（标准差）、tos_stdevall（全维度标准差）、variance（方差）、zscore（Z评分）

    7. 趋势指标（Trend）
       - 功能：识别和确认价格趋势方向、强度及持续时间
       - 包含指标：adx、amat、aroon、chop、cksp、decay、decreasing（下跌趋势）、dpo、increasing（上涨趋势）、long_run（长期趋势）、psar、qstick、short_run（短期趋势）、tsignals（趋势信号）、ttm_trend、vhf、vortex、xsignals（扩展趋势信号）

    8. 波动率指标（Volatility）
       - 功能：衡量价格波动的剧烈程度，评估市场风险
       - 包含指标：aberration、accbands、atr（平均真实波幅）、bbands（布林带）、donchian（唐奇安通道）、hwc、kc（肯特纳通道）、massi、natr（归一化平均真实波幅）、pdist、rvi、thermo、true_range（真实波幅）、ui

    9. 成交量指标（Volume）
       - 功能：结合成交量数据分析资金流向，辅助判断价格走势的有效性
       - 包含指标：ad（积累/派发指标）、adosc（震荡指标）、aobv（绝对OBV）、cmf（资金流向指数）、efi（资金效率指标）、eom（资金流动指数）、kvo（成交量震荡指标）、mfi（资金流量指标）、nvi（负成交量指数）、obv（能量潮指标）、pvi（正成交量指数）、pvol（价格成交量指标）、pvr（价格成交量比率）、pvt（价格成交量趋势）


    使用说明：
    1. 初始化：传入框架支持的 series 或 dataframe 数据对象（需包含指标计算所需的基础字段，如 open、high、low、close、volume 等）
       >>> data = dataframe(...)  # 框架内置数据对象（含OHLCV等基础字段）
       >>> ta = PandasTa(data)

    2. 指标调用：直接调用对应指标方法，传入必要参数（默认参数已适配常见场景，可按需调整）
       >>> #示例1：识别十字星蜡烛图形态
       >>> doji_result = self.data.cdl_pattern(name="doji")  # 返回框架内置dataframe，含十字星形态识别结果
       >>> #示例2：计算Heikin-Ashi布林带K线
       >>> ha_candles = self.data.ha()  # 返回框架内置dataframe，含HA蜡烛图的open、high、low、close字段
       >>> #示例3：计算14期RSI动量指标
       >>> rsi_14 = self.data.close.rsi(length=14)  # 返回框架内置series，含14期RSI值

    3. 返回值特性：所有方法返回框架内置的 series 或 dataframe 类型，可直接用于后续策略逻辑（如信号生成、风险控制），无需额外类型转换


    注意事项：
    - 部分指标需特定基础字段（如成交量指标需 volume 字段），调用前确保输入数据包含所需字段
    - 指标参数（如 length 周期）可通过方法参数调整，未指定时使用 pandas_ta 默认值
    - 可通过 @tobtind 装饰器的 kwargs 参数配置填充缺失值（fillna）、数据偏移（offset）等辅助功能
    """
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    @tobtind(lines=None, lib='pta')
    def cum(self, length=10, **kwargs) -> series:
        "pd.Series.rolling(length).sum()"
        ...

    @tobtind(lines=None, lib='pta')
    def ZeroDivision(self, b=1., **kwargs) -> series | dataframe:
        """float division by zero"""
        ...

    # @tobtind(lines=None, lib='pta')
    # def multi_apply(self, *args):
    #     ...

    @tobtind(lines=None, lib='pta')
    def strategy(self, *args, **kwargs):
        """不可用"""
        ...

    # Public DataFrame Methods: Indicators and Utilities
    # Candles
    @tobtind(lib='pta')
    def cdl_pattern(self, name="all", offset=0, **kwargs) -> dataframe:
        """
        Candle Pattern
        ---------
            A wrapper around all candle patterns.
            >>> args : open, high, low, close

        Note:
        ---------
            不可用于replay

        Returns:
        ---------
            >>> args : open, high, low, close
            >>> dataframe: one column for each pattern.
            >>> ['cdl_2crows', 'cdl_3blackcrows', 'cdl_3inside', 'cdl_3linestrike', 'cdl_3outside',
                'cdl_3starsinsouth', 'cdl_3whitesoldiers', 'cdl_abandonedbaby', 'cdl_advanceblock',
                'cdl_belthold', 'cdl_breakaway', 'cdl_closingmarubozu', 'cdl_concealbabyswall',
                'cdl_counterattack', 'cdl_darkcloudcover', 'cdl_doji', 'cdl_dojistar', 'cdl_dragonflydoji',
                'cdl_engulfing', 'cdl_eveningdojistar', 'cdl_eveningstar', 'cdl_gapsidesidewhite',
                'cdl_gravestonedoji', 'cdl_hammer', 'cdl_hangingman', 'cdl_harami', 'cdl_haramicross',
                'cdl_highwave', 'cdl_hikkake', 'cdl_hikkakemod', 'cdl_homingpigeon', 'cdl_identical3crows',
                'cdl_inneck', 'cdl_inside', 'cdl_invertedhammer', 'cdl_kicking', 'cdl_kickingbylength',
                'cdl_ladderbottom', 'cdl_longleggeddoji', 'cdl_longline', 'cdl_marubozu', 'cdl_matchinglow',
                'cdl_mathold', 'cdl_morningdojistar', 'cdl_morningstar', 'cdl_onneck', 'cdl_piercing',
                'cdl_rickshawman', 'cdl_risefall3methods', 'cdl_separatinglines', 'cdl_shootingstar',
                'cdl_shortline', 'cdl_spinningtop', 'cdl_stalledpattern', 'cdl_sticksandwich', 'cdl_takuri',
                'cdl_tasukigap', 'cdl_thrusting', 'cdl_tristar', 'cdl_unique3river', 'cdl_upsidegap2crows',
                'cdl_xsidegap3methods']

        Examples:
        ---------

        Get all candle patterns (This is the default behaviour)
        >>> df = df.ta.cdl_pattern(name="all")
        Or
        >>> df.ta.cdl("all")

        Get only one pattern
        >>> df = df.ta.cdl_pattern(name="doji")
        Or
        >>> df.ta.cdl("doji")

        Get some patterns
        >>> df = df.ta.cdl_pattern(name=["doji", "inside"])
        Or
        >>> df.ta.cdl(["doji", "inside"])

        Args :
        ---------
            >>> open_ (pd.Series): Series of 'open's
                high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                name: (Union[str, Sequence[str]]): name of the patterns
                scalar (float): How much to magnify. Default: 100
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['open_z', 'high_z', 'low_z', 'close_z'], lib='pta')
    def cdl_z(self, full=None, offset=0, **kwargs) -> dataframe:
        """
        Candle Type: Z
        ---------
            Normalizes OHLC Candles with a rolling Z Score.

        Returns:
        ---------
            >>> dataframe: open_z,high_z,low_z,close_z column.
                args : open, high, low, close

        Source:
        ---------
            Kevin Johnson

        Calculation:
        ---------
            Default values:
            >>> length=30, full=False, ddof=1
                Z = ZSCORE

            >>> open  = Z( open, length, ddof)
                high  = Z( high, length, ddof)
                low   = Z(  low, length, ddof)
                close = Z(close, length, ddof)

        Args :
        ---------
            >>> open_ (pd.Series): Series of 'open's
                high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): The period. Default: 10

        Kwargs:
        ---------
            >>> naive (bool, optional): If True, prefills potential Doji less than
                    the length if less than a percentage of it's high-low range.
                    Default: False
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['open', 'high', 'low', 'close'], overlap=True, lib='pta')
    def ha(self, length=0, offset=0, **kwargs) -> dataframe:
        """
        Heikin Ashi Candles (HA)
        ---------

        Returns:
        ---------
            >>> dataframe: open,high,low,close columns.
            >>> args : open, high, low, close

        The Heikin-Ashi technique averages price data to create a Japanese
        candlestick chart that filters out market noise. Heikin-Ashi charts,
        developed by Munehisa Homma in the 1700s, share some characteristics
        with standard candlestick charts but differ based on the values used
        to create each candle. Instead of using the open, high, low, and close
        like standard candlestick charts, the Heikin-Ashi technique uses a
        modified formula based on two-period averages. This gives the chart a
        smoother appearance, making it easier to spots trends and reversals,
        but also obscures gaps and some price data.

        Sources:
        ---------
            https://www.investopedia.com/terms/h/heikinashi.asp

        Calculation:
        ---------
            >>> HA_OPEN[0] = (open[0] + close[0]) / 2
                HA_CLOSE = (open[0] + high[0] + low[0] + close[0]) / 4
                for i > 1 in df.index:
                    HA_OPEN = (HA_OPEN[i−1] + HA_CLOSE[i−1]) / 2
                HA_HIGH = MAX(HA_OPEN, HA_HIGH, HA_CLOSE)
                HA_LOW = MIN(HA_OPEN, HA_LOW, HA_CLOSE)

            How to Calculate Heikin-Ashi

            Use one period to create the first Heikin-Ashi (HA) candle, using
            the formulas. For example use the high, low, open, and close to
            create the first HA close price. Use the open and close to create
            the first HA open. The high of the period will be the first HA high,
            and the low will be the first HA low. With the first HA calculated,
            it is now possible to continue computing the HA candles per the formulas.

        Args :
        ---------
            >>> open_ (pd.Series): Series of 'open's
                high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['open', 'high', 'low', 'close'], overlap=True, lib='pta')
    def lrc(self, length=11, **kwargs) -> dataframe:
        """# Linear_Regression_Candles
            Utilizing Linear Regression to Enhance Chart Interpretation in Trading
            In the world of trading, accurate interpretation of charts is paramount to making informed decisions. Among the plethora of tools and techniques available, linear regression stands out for its simplicity and efficacy.
            Linear regression, a fundamental statistical method, helps traders identify the underlying trend of a security’s price by fitting a straight line through the data points. This line, known as the regression line, represents the best estimate of the future price movement, providing a clearer picture of the trend’s direction, strength, and volatility.
            By reducing the noise in price data, linear regression makes it easier to spot trends and reversals, offering a solid foundation for both technical analysis and trading strategy development.
            Linear Regression Candles Indicator
            At its core, the indicator recalibrates standard candlestick data using linear regression, creating candles that better reflect the underlying trend’s direction.
            Its ability to filter out market noise and present a cleaner trend analysis can significantly enhance decision-making in various trading strategies, including:
            Trend Following: Traders can use the indicator to confirm the presence of a strong trend and enter trades in the direction of that trend.
            Reversal Detection: The crossover of candles with the signal line can indicate potential trend reversals, providing early entries for counter-trend strategies.
            Risk Management: By understanding the trend’s strength and direction, traders can set more informed stop-loss and take-profit levels, improving their risk-to-reward ratios.
            The Linear Regression Candles indicator exemplifies how statistical techniques like linear regression can be innovatively applied to enhance traditional trading tools.
            By offering a clearer view of the market trend and smoothing out price volatility, this indicator aids traders in navigating the complexities of the financial markets with greater confidence.
            Whether for trend identifica

            # Args:
                df (pd.DataFrame): K线数据
                length (int, optional): 长度. Defaults to 11.

            # Returns:
                >>> pd.DataFrame"""
        ...

    # Cycles
    @tobtind(lines=None, lib='pta')
    def ebsw(self, length=40, bars=10, offset=0, **kwargs) -> series:
        """Even Better SineWave (EBSW) *beta*
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
            >>> args : close

        This indicator measures market cycles and uses a low pass filter to remove noise.
        Its output is bound signal between -1 and 1 and the maximum length of a detected
        trend is limited by its length input.

        Written by rengel8 for Pandas TA based on a publication at 'prorealcode.com' and
        a book by J.F.Ehlers.

        * This implementation seems to be logically limited. It would make sense to
        implement exactly the version from prorealcode and compare the behaviour.


        Sources:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/even-better-sinewave/
            J.F.Ehlers 'Cycle Analytics for Traders', 2014

        Calculation:
        ---------
            refer to 'sources' or implementation

        Args :
        ---------
        >>> close (pd.Series): Series of 'close's
            length (int): It's max cycle/trend period. Values between 40-48 work like
                expected with minimum value: 39. Default: 40.
            bars (int): Period of low pass filtering. Default: 10
            drift (int): The difference period. Default: 1
            offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
        >>> fillna (value, optional): pd.DataFrame.fillna(value)
            fill_method (value, optional): Type of fill method
        """
        ...

    # Momentum
    @tobtind(lines=None, lib='pta')
    def ao(self, fast=5, slow=34, offset=0, **kwargs) -> series:
        """Awesome Oscillator (AO)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low

        The Awesome Oscillator is an indicator used to measure a security's momentum.
        AO is generally used to affirm trends or to anticipate possible reversals.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Awesome_Oscillator_(AO)
            https://www.ifcm.co.uk/ntx-indicators/awesome-oscillator

        Calculation:
        ---------
            >>> Default Inputs:
                fast=5, slow=34
                SMA = Simple Moving Average
                median = (high + low) / 2
                AO = SMA(median, fast) - SMA(median, slow)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                fast (int): The short period. Default: 5
                slow (int): The long period. Default: 34
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def apo(self, fast=12, slow=26, mamode='sma', offset=0, **kwargs) -> series:
        """Absolute Price Oscillator (APO)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Absolute Price Oscillator is an indicator used to measure a security's
        momentum.  It is simply the difference of two Exponential Moving Averages
        (EMA) of two different periods. Note: APO and MACD lines are equivalent.

        Sources:
        ---------
            https://www.tradingtechnologies.com/xtrader-help/x-study/technical-indicator-definitions/absolute-price-oscillator-apo/

        Calculation:
        ---------
            >>> Default Inputs:
            >>> fast=12, slow=26
                SMA = Simple Moving Average
                APO = SMA(close, fast) - SMA(close, slow)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                fast (int): The short period. Default: 12
                slow (int): The long period. Default: 26
                mamode (str): See ```help(ta.ma)```. Default: 'sma'
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def bias(self, length=26, mamode="sma", offset=0, **kwargs) -> series:
        """Bias (BIAS)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Rate of change between the source and a moving average.

        Sources:
        ---------
            Few internet resources on definitive definition.
            Request by Github user homily, issue #46

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=26, MA='sma'
            >>> BIAS = (close - MA(close, length)) / MA(close, length)
                = (close / MA(close, length)) - 1

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): The period. Default: 26
                mamode (str): See ```help(ta.ma)```. Default: 'sma'
                drift (int): The short period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def bop(self, scalar=1, talib=True, offset=0, **kwargs) -> series:
        """Balance of Power (BOP)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : open, high, low, close

        Balance of Power measure the market strength of buyers against sellers.

        Sources:
        ---------
            http://www.worden.com/TeleChartHelp/Content/Indicators/Balance_of_Power.htm

        Calculation:
        ---------
            >>> BOP = scalar * (close - open) / (high - low)

        Args :
        ---------
            >>> open (pd.Series): Series of 'open's
                high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                scalar (float): How much to magnify. Default: 1
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['ar', 'br'], lib='pta')
    def brar(self, length=26, scalar=100, drift=1, offset=0, **kwargs) -> dataframe:
        """BRAR (BRAR)
        ---------

        Returns:
        ---------
            >>> dataframe: ar, br columns.
                args : open, high, low, close

        BR and AR

        Sources:
        ---------
            No internet resources on definitive definition.
            Request by Github user homily, issue #46

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=26, scalar=100
                SUM = Sum

            >>> HO_Diff = high - open
                OL_Diff = open - low
                HCY = high - close[-1]
                CYL = close[-1] - low
                HCY[HCY < 0] = 0
                CYL[CYL < 0] = 0
                AR = scalar * SUM(HO, length) / SUM(OL, length)
                BR = scalar * SUM(HCY, length) / SUM(CYL, length)

        Args :
        ---------
            >>> open_ (pd.Series): Series of 'open's
                high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): The period. Default: 26
                scalar (float): How much to magnify. Default: 100
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cci(self, length=14, c=0.015, offset=0, **kwargs) -> series:
        """Commodity Channel Index (CCI)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low, close

        Commodity Channel Index is a momentum oscillator used to primarily identify
        overbought and oversold levels relative to a mean.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Commodity_Channel_Index_(CCI)

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=14, c=0.015
                SMA = Simple Moving Average
                MAD = Mean Absolute Deviation
                tp = typical_price = hlc3 = (high + low + close) / 3
                mean_tp = SMA(tp, length)
                mad_tp = MAD(tp, length)
                CCI = (tp - mean_tp) / (c * mad_tp)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                c (float): Scaling Constant. Default: 0.015
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cfo(self, length=9, scalar=100., drift=1, offset=0, **kwargs) -> series:
        """Chande Forcast Oscillator (CFO)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Forecast Oscillator calculates the percentage difference between the actual
        price and the Time Series Forecast (the endpoint of a linear regression line).

        Sources:
        ---------
            https://www.fmlabs.com/reference/default.htm?url=ForecastOscillator.htm

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=9, drift=1, scalar=100
                LINREG = Linear Regression

            >>> CFO = scalar * (close - LINERREG(length, tdf=True)) / close

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): The period. Default: 9
                scalar (float): How much to magnify. Default: 100
                drift (int): The short period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cg(self, length=10, offset=0, **kwargs) -> series:
        """Center of Gravity (CG)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Center of Gravity Indicator by John Ehlers attempts to identify turning
        points while exhibiting zero lag and smoothing.

        Sources:
        ---------
            http://www.mesasoftware.com/papers/TheCGOscillator.pdf

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=10

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): The length of the period. Default: 10
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cmo(self, length=14, scalar=100., talib=True, drift=1, offset=0, **kwargs) -> series:
        """Chande Momentum Oscillator (CMO)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Attempts to capture the momentum of an asset with overbought at 50 and
        oversold at -50.

        Sources:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/chande-momentum-oscillator-cmo/
            https://www.tradingview.com/script/hdrf0fXV-Variable-Index-Dynamic-Average-VIDYA/

        Calculation:
        ---------
            >>> Default Inputs:
            >>> drift=1, scalar=100

            # Same Calculation as RSI except for this step
            >>> CMO = scalar * (PSUM - NSUM) / (PSUM + NSUM)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                scalar (float): How much to magnify. Default: 100
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. If TA Lib is not installed but talib is True, it runs the Python
                    version TA Lib. Default: True
                drift (int): The short period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            talib (bool): If True, uses TA-Libs implementation. Otherwise uses EMA version. Default: True
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def coppock(self, length=10, fast=11, slow=14, offset=0, **kwargs) -> series:
        """Coppock Curve (COPC)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Coppock Curve (originally called the "Trendex Model") is a momentum indicator
        is designed for use on a monthly time scale.  Although designed for monthly
        use, a daily calculation over the same period can be made, converting the
        periods to 294-day and 231-day rate of changes, and a 210-day weighted
        moving average.

        Sources:
        ---------
            https://en.wikipedia.org/wiki/Coppock_curve

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=10, fast=11, slow=14
                SMA = Simple Moving Average
                MAD = Mean Absolute Deviation
                tp = typical_price = hlc3 = (high + low + close) / 3
                mean_tp = SMA(tp, length)
                mad_tp = MAD(tp, length)
                CCI = (tp - mean_tp) / (c * mad_tp)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): WMA period. Default: 10
                fast (int): Fast ROC period. Default: 11
                slow (int): Slow ROC period. Default: 14
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cti(self, length=12, offset=0, **kwargs) -> series:
        """Correlation Trend Indicator (CTI)
        ---------

        Returns:
        ---------
            >>> series: Series of the CTI values for the given period.
                args : close

        The Correlation Trend Indicator is an oscillator created by John Ehler in 2020.
        It assigns a value depending on how close prices in that range are to following
        a positively- or negatively-sloping straight line. Values range from -1 to 1.
        This is a wrapper for ta.linreg(close, r=True).

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 12
                offset (int): How many periods to offset the result. Default: 0
        """
        ...

    @tobtind(lines=['dmp', 'dmn'], lib='pta')
    def dm(self, length=14, mamode="rma", talib=True, drift=1, offset=0, **kwargs) -> dataframe:
        """Directional Movement (DM)
        ---------

        Returns:
        ---------
            >>> dataframe: dmp (+DM) and dmn (-DM) columns.
                args : high, low

        The Directional Movement was developed by J. Welles Wilder in 1978 attempts to
        determine which direction the price of an asset is moving. It compares prior
        highs and lows to yield to two series +DM and -DM.

        Sources:
        ---------
            https://www.tradingview.com/pine-script-reference/#fun_dmi
            https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=24&Name=Directional_Movement_Index

        Calculation:
        ---------
            >>> Default Inputs:
                >>> length=14, mamode="rma", drift=1
                    up = high - high.shift(drift)
                    dn = low.shift(drift) - low
                    pos_ = ((up > dn) & (up > 0)) * up
                    neg_ = ((dn > up) & (dn > 0)) * dn
                    pos_ = pos_.apply(zero)
                    neg_ = neg_.apply(zero)

                # Not the same values as TA Lib's -+DM
                >>> pos = ma(mamode, pos_, length=length)
                    neg = ma(mamode, neg_, length=length)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                mamode (str): See ```help(ta.ma)```.  Default: 'rma'
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0
        """
        ...

    @tobtind(lines=None, lib='pta')
    def er(self, length=14, drift=1, offset=0, **kwargs) -> series:
        """Efficiency Ratio (ER)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Efficiency Ratio was invented by Perry J. Kaufman and presented in his book "New Trading Systems and Methods". It is designed to account for market noise or volatility.

        It is calculated by dividing the net change in price movement over N periods by the sum of the absolute net changes over the same N periods.

        Sources:
        ---------
            https://help.tc2000.com/m/69404/l/749623-kaufman-efficiency-ratio

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=10
                ABS = Absolute Value
                EMA = Exponential Moving Average
                abs_diff = ABS(close.diff(length))
                volatility = ABS(close.diff(1))
                ER = abs_diff / SUM(volatility, length)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['bullp', 'bearp'], lib='pta')
    def eri(self, length=14, offset=0, **kwargs) -> dataframe:
        """Elder Ray Index (ERI)
        ---------

        Returns:
        ---------
            >>> dataframe: bullp and bearp columns.
                args : high, low, close

        Elder's Bulls Ray Index contains his Bull and Bear Powers. Which are useful ways
        to look at the price and see the strength behind the market. Bull Power
        measures the capability of buyers in the market, to lift prices above an average
        consensus of value.

        Bears Power measures the capability of sellers, to drag prices below an average
        consensus of value. Using them in tandem with a measure of trend allows you to
        identify favourable entry points. We hope you've found this to be a useful
        discussion of the Bulls and Bears Power indicators.

        Sources:
        ---------
            https://admiralmarkets.com/education/articles/forex-indicators/bears-and-bulls-power-indicator

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=13
                EMA = Exponential Moving Average
                BULLPOWER = high - EMA(close, length)
                BEARPOWER = low - EMA(close, length)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['fisher', 'fishers'], lib='pta')
    def fisher(self, length=9, signal=1, offset=0, **kwargs) -> dataframe:
        """Fisher Transform (FISHT)
        ---------

        Returns:
        ---------
            >>> dataframe:fisher and fishers columns.
                args : high, low

        Attempts to identify significant price reversals by normalizing prices over a
        user-specified number of periods. A reversal signal is suggested when the the
        two lines cross.

        Sources:
        ---------
            TradingView (Correlation >99%)

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=9, signal=1
                HL2 = hl2(high, low)
                HHL2 = HL2.rolling(length).max()
                LHL2 = HL2.rolling(length).min()
                HLR = HHL2 - LHL2
                HLR[HLR < 0.001] = 0.001
                position = ((HL2 - LHL2) / HLR) - 0.5
                v = 0
                m = high.size
                FISHER = [np.nan for _ in range(0, length - 1)] + [0]
                for i in range(length, m):
                    v = 0.66 * position[i] + 0.67 * v
                    if v < -0.99: v = -0.999
                    if v >  0.99: v =  0.999
                    FISHER.append(
                        0.5 * (nplog((1 + v) / (1 - v)) + FISHER[i - 1]))
                SIGNAL = FISHER.shift(signal)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                length (int): Fisher period. Default: 9
                signal (int): Fisher Signal period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def inertia(self, length=20, rvi_length=14, scalar=100., refined=False, thirds=False, mamode="ema", drift=1, offset=0, **kwargs) -> series:
        """Inertia (INERTIA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close, high, low

        Inertia was developed by Donald Dorsey and was introduced his article
        in September, 1995. It is the Relative Vigor Index smoothed by the Least
        Squares Moving Average. Postive Inertia when values are greater than 50,
        Negative Inertia otherwise.

        Sources:
        ---------
            https://www.investopedia.com/terms/r/relative_vigor_index.asp

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=14, ma_length=20
                LSQRMA = Least Squares Moving Average
                INERTIA = LSQRMA(RVI(length), ma_length)

        Args :
        ---------
            >>> open_ (pd.Series): Series of 'open's
                high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 20
                rvi_length (int): RVI period. Default: 14
                refined (bool): Use 'refined' calculation. Default: False
                thirds (bool): Use 'thirds' calculation. Default: False
                mamode (str): See ```help(ta.ma)```. Default: 'ema'
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['k', 'd', 'j'], lib='pta')
    def kdj(self, length=9, signal=3, offset=0, **kwargs) -> dataframe:
        """KDJ (KDJ)
        ---------

        Returns:
        ---------
            >>> dataframe: k , d and j columns.
                args : high, low

        The KDJ indicator is actually a derived form of the Slow
        Stochastic with the only difference being an extra line
        called the J line. The J line represents the divergence
        of the %D value from the %K. The value of J can go
        beyond [0, 100] for %K and %D lines on the chart.

        Sources:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/kdj/
            https://docs.anychart.com/Stock_Charts/Technical_Indicators/Mathematical_Description#kdj

        Calculation:
        ---------
            >>> Default Inputs:
                length=9, signal=3
                LL = low for last 9 periods
                HH = high for last 9 periods
                FAST_K = 100 * (close - LL) / (HH - LL)
                K = RMA(FAST_K, signal)
                D = RMA(K, signal)
                J = 3K - 2D

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): Default: 9
                signal (int): Default: 3
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['kst', 'ksts'], lib='pta')
    def kst(self, roc1=10, roc2=15, roc3=20, roc4=30, sma1=10, sma2=10, sma3=10, sma4=15, signal=9, drift=1, offset=0, **kwargs) -> dataframe:
        """'Know Sure Thing' (KST)
        ---------

        Returns:
        ---------
            >>> dataframe: kst and ksts columns
                args : close

        The 'Know Sure Thing' is a momentum based oscillator and based on ROC.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Know_Sure_Thing_(KST)
            https://www.incrediblecharts.com/indicators/kst.php

        Calculation:
        ---------
            >>> Default Inputs:
            >>> roc1=10, roc2=15, roc3=20, roc4=30,
                sma1=10, sma2=10, sma3=10, sma4=15, signal=9, drift=1
                ROC = Rate of Change
                SMA = Simple Moving Average
                rocsma1 = SMA(ROC(close, roc1), sma1)
                rocsma2 = SMA(ROC(close, roc2), sma2)
                rocsma3 = SMA(ROC(close, roc3), sma3)
                rocsma4 = SMA(ROC(close, roc4), sma4)
                KST = 100 * (rocsma1 + 2 * rocsma2 + 3 * rocsma3 + 4 * rocsma4)
                KST_Signal = SMA(KST, signal)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                roc1 (int): ROC 1 period. Default: 10
                roc2 (int): ROC 2 period. Default: 15
                roc3 (int): ROC 3 period. Default: 20
                roc4 (int): ROC 4 period. Default: 30
                sma1 (int): SMA 1 period. Default: 10
                sma2 (int): SMA 2 period. Default: 10
                sma3 (int): SMA 3 period. Default: 10
                sma4 (int): SMA 4 period. Default: 15
                signal (int): It's period. Default: 9
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['macdx', 'macdh', 'macds'], lib='pta')
    def macd(self, fast=12, slow=26, signal=9, talib=True, offset=0, **kwargs) -> dataframe:
        """Moving Average Convergence Divergence (MACD)
        ---------

        Returns:
        ---------
           >>> dataframe: macdx, macdh, macds columns.
                args : close

        The MACD is a popular indicator to that is used to identify a security's trend.
        While APO and MACD are the same calculation, MACD also returns two more series
        called Signal and Histogram. The Signal is an EMA of MACD and the Histogram is
        the difference of MACD and Signal.

        Sources:
        ---------
            https://www.tradingview.com/wiki/MACD_(Moving_Average_Convergence/Divergence)
            AS Mode: https://tr.tradingview.com/script/YFlKXHnP/

        Calculation:
        ---------
            >>> Default Inputs:
            >>> fast=12, slow=26, signal=9
                EMA = Exponential Moving Average
                MACD = EMA(close, fast) - EMA(close, slow)
                Signal = EMA(MACD, signal)
                Histogram = MACD - Signal
                if asmode:
                    MACD = MACD - Signal
                    Signal = EMA(MACD, signal)
                    Histogram = MACD - Signal

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                fast (int): The short period. Default: 12
                slow (int): The long period. Default: 26
                signal (int): The signal period. Default: 9
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            asmode (value, optional): When True, enables AS version of MACD.
                Default: False
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def mom(self, length=10, talib=True, offset=0, **kwargs) -> series:
        """Momentum (MOM)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Momentum is an indicator used to measure a security's speed (or strength) of
        movement.  Or simply the change in price.

        Sources:
        ---------
            http://www.onlinetradingconcepts.com/TechnicalAnalysis/Momentum.html

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=1
                MOM = close.diff(length)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pgo(self, length=14, offset=0, **kwargs) -> series:
        """Pretty Good Oscillator (PGO)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low, close

        The Pretty Good Oscillator indicator was created by Mark Johnson to measure the distance of the current close from its N-day Simple Moving Average, expressed in terms of an average true range over a similar period. Johnson's approach was to
        use it as a breakout system for longer term trades. Long if greater than 3.0 and
        short if less than -3.0.

        Sources:
        ---------
            https://library.tradingtechnologies.com/trade/chrt-ti-pretty-good-oscillator.html

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=14
                ATR = Average True Range
                SMA = Simple Moving Average
                EMA = Exponential Moving Average
                PGO = (close - SMA(close, length)) / \
                       EMA(ATR(high, low, close, length), length)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['ppo', 'ppoh', 'ppos'], lib='pta')
    def ppo(self, fast=12, slow=26, signal=9, scalar=100., mamode="sma", talib=True, **kwargs) -> dataframe:
        """Percentage Price Oscillator (PPO)
        ---------

        Returns:
        ---------
            >>> dataframe: ppo, ppoh, ppos columns
                args : close

        The Percentage Price Oscillator is similar to MACD in measuring momentum.

        Sources:
        ---------
            https://www.tradingview.com/wiki/MACD_(Moving_Average_Convergence/Divergence)

        Calculation:
        ---------
            >>> Default Inputs:
            >>> fast=12, slow=26
                SMA = Simple Moving Average
                EMA = Exponential Moving Average
                fast_sma = SMA(close, fast)
                slow_sma = SMA(close, slow)
                PPO = 100 * (fast_sma - slow_sma) / slow_sma
                Signal = EMA(PPO, signal)
                Histogram = PPO - Signal

        Args :
        ---------
            >>> close(pandas.Series): Series of 'close's
                fast(int): The short period. Default: 12
                slow(int): The long period. Default: 26
                signal(int): The signal period. Default: 9
                scalar (float): How much to magnify. Default: 100
                mamode (str): See ```help(ta.ma)```. Default: 'sma'
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset(int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def psl(self, length=12, scalar=100., drift=1, offset=0, **kwargs) -> series:
        """Psychological Line (PSL)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Psychological Line is an oscillator-type indicator that compares the
        number of the rising periods to the total number of periods. In other
        words, it is the percentage of bars that close above the previous
        bar over a given period.

        Sources:
        ---------
            https://www.quantshare.com/item-851-psychological-line

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=12, scalar=100, drift=1
                IF NOT open:
                    DIFF = SIGN(close - close[drift])
                ELSE:
                    DIFF = SIGN(close - open)
                DIFF.fillna(0)
                DIFF[DIFF <= 0] = 0
                PSL = scalar * SUM(DIFF, length) / length

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                open_ (pd.Series, optional): Series of 'open's
                length (int): It's period. Default: 12
                scalar (float): How much to magnify. Default: 100
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['pvo', 'pvoh', 'pvos'], overlap=False, lib='pta')
    def pvo(self, fast=12, slow=26, signal=9, scalar=100., offset=0, **kwargs) -> dataframe:
        """Percentage Volume Oscillator (PVO)
        ---------

        Returns:
        ---------
            >>> dataframe: pvo, pvoh, pvos columns.
                args : volume

        Percentage Volume Oscillator is a Momentum Oscillator for Volume.

        Sources:
        ---------
            https://www.fmlabs.com/reference/default.htm?url=PVO.htm

        Calculation:
        ---------
            >>> Default Inputs:
            >>> fast=12, slow=26, signal=9
                EMA = Exponential Moving Average
                PVO = (EMA(volume, fast) - EMA(volume, slow)) / \
                       EMA(volume, slow)
                Signal = EMA(PVO, signal)
                Histogram = PVO - Signal

        Args :
        ---------
            >>> volume (pd.Series): Series of 'volume's
                fast (int): The short period. Default: 12
                slow (int): The long period. Default: 26
                signal (int): The signal period. Default: 9
                scalar (float): How much to magnify. Default: 100
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['qqe', 'rsi_ma' 'qqel', 'qqes'], lib='pta')
    def qqe(self, length=14, smooth=5, factor=4.236, mamode="sma", drift=1, offset=0, **kwargs) -> dataframe:
        """Quantitative Qualitative Estimation (QQE)
        ---------

        Returns:
        ---------
            >>> dataframe: QQE, RSI_MA (basis), QQEl (long), and QQEs (short) columns.
                dataframe : qqe ,rsi_ma qqel ,qqes columns.
                args : close

        The Quantitative Qualitative Estimation (QQE) is similar to SuperTrend but uses a Smoothed RSI with an upper and lower bands. The band width is a combination of a one period True Range of the Smoothed RSI which is double smoothed using Wilder's smoothing length (2 * rsiLength - 1) and multiplied by the default factor of 4.236. A Long trend is determined when the Smoothed RSI crosses the previous upperband and a Short trend when the Smoothed RSI crosses the previous lowerband.

        Based on QQE.mq5 by EarnForex Copyright © 2010, based on version by Tim Hyder (2008), based on version by Roman Ignatov (2006)

        Sources:
        ---------
            https://www.tradingview.com/script/IYfA9R2k-QQE-MT4/
            https://www.tradingpedia.com/forex-trading-indicators/quantitative-qualitative-estimation
            https://www.prorealcode.com/prorealtime-indicators/qqe-quantitative-qualitative-estimation/

        Calculation:
        ---------
            >>> Default Inputs:
                >>> length=14, smooth=5, factor=4.236, mamode="ema", drift=1

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): RSI period. Default: 14
                smooth (int): RSI smoothing period. Default: 5
                factor (float): QQE Factor. Default: 4.236
                mamode (str): See ```help(ta.ma)```. Default: 'sma'
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def roc(self, length=10, scalar=100., talib=True, offset=0, **kwargs) -> series:
        """Rate of Change (ROC)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Rate of Change is an indicator is also referred to as Momentum (yeah, confusingly).
        It is a pure momentum oscillator that measures the percent change in price with the
        previous price 'n' (or length) periods ago.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Rate_of_Change_(ROC)

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=1
                MOM = Momentum
                ROC = 100 * MOM(close, length) / close.shift(length)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                scalar (float): How much to magnify. Default: 100
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def rsi(self, length=14, scalar=100., talib=True, drift=1, offset=0, **kwargs) -> series:
        """Relative Strength Index (RSI)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Relative Strength Index is popular momentum oscillator used to measure the
        velocity as well as the magnitude of directional price movements.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Relative_Strength_Index_(RSI)

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=14, scalar=100, drift=1
                ABS = Absolute Value
                RMA = Rolling Moving Average
                diff = close.diff(drift)
                positive = diff if diff > 0 else 0
                negative = diff if diff < 0 else 0
                pos_avg = RMA(positive, length)
                neg_avg = ABS(RMA(negative, length))
                RSI = scalar * pos_avg / (pos_avg + neg_avg)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                scalar (float): How much to magnify. Default: 100
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def rsx(self, length=14, drift=1, offset=0, **kwargs) -> series:
        """Relative Strength Xtra (rsx)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Relative Strength Xtra is based on the popular RSI indicator and inspired
        by the work Jurik Research. The code implemented is based on published code
        found at 'prorealcode.com'. This enhanced version of the rsi reduces noise and
        provides a clearer, only slightly delayed insight on momentum and velocity of
        price movements.

        Sources:
        ---------
            http://www.jurikres.com/catalog1/ms_rsx.htm
            https://www.prorealcode.com/prorealtime-indicators/jurik-rsx/

        Calculation:
        ---------
            Refer to the sources above for information as well as code example.

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['rvgi', 'rvgs'], lib='pta')
    def rvgi(self, length=14, swma_length=4, offset=0, **kwargs) -> dataframe:
        """Relative Vigor Index (RVGI)
        ---------

        Returns:
        ---------
            >>> dataframe: rvgi,rvgs columns.
                args : open, high, low, close

        The Relative Vigor Index attempts to measure the strength of a trend relative to
        its closing price to its trading range.  It is based on the belief that it tends
        to close higher than they open in uptrends or close lower than they open in
        downtrends.

        Sources:
        ---------
            https://www.investopedia.com/terms/r/relative_vigor_index.asp

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=14, swma_length=4
                SWMA = Symmetrically Weighted Moving Average
                numerator = SUM(SWMA(close - open, swma_length), length)
                denominator = SUM(SWMA(high - low, swma_length), length)
                RVGI = numerator / denominator

        Args :
        ---------

            >>> open_ (pd.Series): Series of 'open's
                high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                swma_length (int): It's period. Default: 4
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def slope(self, length=10, as_angle=False, to_degrees=False, vertical=None, offset=0, **kwargs) -> series:
        """Slope
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Returns the slope of a series of length n. Can convert the slope to angle.
        Default: slope.

        Sources:
        --------- Algebra I

        Calculation:
        ---------
            >>> Default Inputs:
            >>> length=1
                slope = close.diff(length) / length
                if as_angle:
                    slope = slope.apply(atan)
                    if to_degrees:
                        slope *= 180 / PI

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period.  Default: 10
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> as_angle (value, optional): Converts slope to an angle. Default: False
                to_degrees (value, optional): Converts slope angle to degrees. Default: False
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['smi', 'smis', 'smios'], lib='pta')
    def smi(self, fast=5, slow=20, signal=5, scalar=1., offset=0, **kwargs) -> dataframe:
        """SMI Ergodic Indicator (SMI)
        ---------

        Returns:
        ---------
            >>> dataframe: smi, smis, smios columns.
                args : close

        The SMI Ergodic Indicator is the same as the True Strength Index (TSI) developed
        by William Blau, except the SMI includes a signal line. The SMI uses double
        moving averages of price minus previous price over 2 time frames. The signal
        line, which is an EMA of the SMI, is plotted to help trigger trading signals.
        The trend is bullish when crossing above zero and bearish when crossing below
        zero. This implementation includes both the SMI Ergodic Indicator and SMI
        Ergodic Oscillator.

        Sources:
        ---------
            https://www.motivewave.com/studies/smi_ergodic_indicator.htm
            https://www.tradingview.com/script/Xh5Q0une-SMI-Ergodic-Oscillator/
            https://www.tradingview.com/script/cwrgy4fw-SMIIO/

        Calculation:
        ---------
            >>> Default Inputs:
            >>> fast=5, slow=20, signal=5
                TSI = True Strength Index
                EMA = Exponential Moving Average
                ERG = TSI(close, fast, slow)
                Signal = EMA(ERG, signal)
                OSC = ERG - Signal

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                fast (int): The short period. Default: 5
                slow (int): The long period. Default: 20
                signal (int): The signal period. Default: 5
                scalar (float): How much to magnify. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['sqz_on', 'sqz_off', 'sqz_no'])
    def squeeze(self, bb_length=20, bb_std=2., kc_length=20, kc_scalar=1.5,
                mom_length=12, mom_smooth=6, use_tr=True, mamode="sma", offset=0, **kwargs) -> dataframe:
        """Squeeze PRO(SQZPRO)
        ---------

        Returns:
        ---------
            >>> dataframe:
                detailed is false : sqz_on,sqz_off,sqz_no columns.
                detailed is true : sqz_inc ,sqz_dec, pos_inc ,pos_dec ,neg_dec ,neg_inc columns.
                args : high, low, close
        This indicator is an extended version of "TTM Squeeze" from John Carter.
        The default is based on John Carter's "TTM Squeeze" indicator, as discussed
        in his book "iding the Trade" (chapter 11). The Squeeze indicator attempts
        to capture the relationship between two studies: Bollinger Bands® and Keltner's
        Channels. When the volatility increases, so does the distance between the bands,
        conversely, when the volatility declines, the distance also decreases. It finds
        sections of the Bollinger Bands® study which fall inside the Keltner's Channels.

        Sources:
        ---------
            https://usethinkscript.com/threads/john-carters-squeeze-pro-indicator-for-thinkorswim-free.4021/
            https://www.tradingview.com/script/TAAt6eRX-Squeeze-PRO-Indicator-Makit0/

        Calculation:
        ---------
            >>> Default Inputs:
                >>> bb_length=20, bb_std=2, kc_length=20, kc_scalar_wide=2,
                    kc_scalar_normal=1.5, kc_scalar_narrow=1, mom_length=12,
                    mom_smooth=6, tr=True,
                    BB = Bollinger Bands
                    KC = Keltner Channels
                    MOM = Momentum
                    SMA = Simple Moving Average
                    EMA = Exponential Moving Average
                    TR = True Range

                >>> RANGE = TR(high, low, close) if using_tr else high - low
                    BB_LOW, BB_MID, BB_HIGH = BB(close, bb_length, std=bb_std)
                    KC_LOW_WIDE, KC_MID_WIDE, KC_HIGH_WIDE = KC(
                        high, low, close, kc_length, kc_scalar_wide, TR)
                    KC_LOW_NORMAL, KC_MID_NORMAL, KC_HIGH_NORMAL = KC(
                        high, low, close, kc_length, kc_scalar_normal, TR)
                    KC_LOW_NARROW, KC_MID_NARROW, KC_HIGH_NARROW = KC(
                        high, low, close, kc_length, kc_scalar_narrow, TR)

                >>> MOMO = MOM(close, mom_length)
                    if mamode == "ema":
                        SQZPRO = EMA(MOMO, mom_smooth)
                    else:
                        SQZPRO = EMA(momo, mom_smooth)

                >>> SQZPRO_ON_WIDE  = (BB_LOW > KC_LOW_WIDE) and (BB_HIGH < KC_HIGH_WIDE)
                    SQZPRO_ON_NORMAL  = (BB_LOW > KC_LOW_NORMAL) and (
                        BB_HIGH < KC_HIGH_NORMAL)
                    SQZPRO_ON_NARROW  = (BB_LOW > KC_LOW_NARROW) and (
                        BB_HIGH < KC_HIGH_NARROW)
                    SQZPRO_OFF_WIDE = (BB_LOW < KC_LOW_WIDE) and (
                        BB_HIGH > KC_HIGH_WIDE)
                    SQZPRO_NO = !SQZ_ON_WIDE and !SQZ_OFF_WIDE

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                bb_length (int): Bollinger Bands period. Default: 20
                bb_std (float): Bollinger Bands Std. Dev. Default: 2
                kc_length (int): Keltner Channel period. Default: 20
                kc_scalar_wide (float): Keltner Channel scalar for wider channel. Default: 2
                kc_scalar_normal (float): Keltner Channel scalar for normal channel. Default: 1.5
                kc_scalar_narrow (float): Keltner Channel scalar for narrow channel. Default: 1
                mom_length (int): Momentum Period. Default: 12
                mom_smooth (int): Smoothing Period of Momentum. Default: 6
                mamode (str): Only "ema" or "sma". Default: "sma"
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> tr (value, optional): Use True Range for Keltner Channels. Default: True
                asint (value, optional): Use integers instead of bool. Default: True
                mamode (value, optional): Which MA to use. Default: "sma"
                detailed (value, optional): Return additional variations of SQZ for
                    visualization. Default: False
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['sqzpro', 'sqz_onwide', 'sqz_onnormal', 'sqz_onnarrow', 'sqzpro_off', 'sqzpro_no'])
    def squeeze_pro(self, bb_length=20, bb_std=2., kc_length=20,
                    kc_scalar_wide=2., kc_scalar_normal=1.5,
                    kc_scalar_narrow=1., mom_length=12, mom_smooth=6,
                    use_tr=True, mamode="sma", offset=0, **kwargs) -> dataframe:
        """Squeeze (SQZ)
        ---------

        Returns:
        ---------
            >>> dataframe:
                detailed is false : sqzpro, sqz_onwide, sqz_onnormal, sqz_onnarrow,sqzpro_off,sqzpro_no columns.
                detailed is true : sqzpro_inc ,sqzpro_dec, pospro_inc ,pospro_dec ,negpro_dec ,negpro_inc columns.
                args : high, low, close
        The default is based on John Carter's "TTM Squeeze" indicator, as discussed
        in his book "iding the Trade" (chapter 11). The Squeeze indicator attempts
        to capture the relationship between two studies: Bollinger Bands® and Keltner's
        Channels. When the volatility increases, so does the distance between the bands,
        conversely, when the volatility declines, the distance also decreases. It finds
        sections of the Bollinger Bands® study which fall inside the Keltner's Channels.

        Sources:
        ---------
            https://tradestation.tradingappstore.com/products/TTMSqueeze
            https://www.tradingview.com/scripts/lazybear/
            https://tlc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/T-U/TTM-Squeeze

        Calculation:
        ---------
            >>> Default Inputs:
                bb_length=20, bb_std=2, kc_length=20, kc_scalar=1.5, mom_length=12,
                mom_smooth=12, tr=True, lazybear=False,
                BB = Bollinger Bands
                KC = Keltner Channels
                MOM = Momentum
                SMA = Simple Moving Average
                EMA = Exponential Moving Average
                TR = True Range
                RANGE = TR(high, low, close) if using_tr else high - low
                BB_LOW, BB_MID, BB_HIGH = BB(close, bb_length, std=bb_std)
                KC_LOW, KC_MID, KC_HIGH = KC(
                    high, low, close, kc_length, kc_scalar, TR)
                if lazybear:
                    HH = high.rolling(kc_length).max()
                    LL = low.rolling(kc_length).min()
                    AVG  = 0.25 * (HH + LL) + 0.5 * KC_MID
                    SQZ = linreg(close - AVG, kc_length)
                else:
                    MOMO = MOM(close, mom_length)
                    if mamode == "ema":
                        SQZ = EMA(MOMO, mom_smooth)
                    else:
                        SQZ = EMA(momo, mom_smooth)
                SQZ_ON  = (BB_LOW > KC_LOW) and (BB_HIGH < KC_HIGH)
                SQZ_OFF = (BB_LOW < KC_LOW) and (BB_HIGH > KC_HIGH)
                NO_SQZ = !SQZ_ON and !SQZ_OFF

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                bb_length (int): Bollinger Bands period. Default: 20
                bb_std (float): Bollinger Bands Std. Dev. Default: 2
                kc_length (int): Keltner Channel period. Default: 20
                kc_scalar (float): Keltner Channel scalar. Default: 1.5
                mom_length (int): Momentum Period. Default: 12
                mom_smooth (int): Smoothing Period of Momentum. Default: 6
                mamode (str): Only "ema" or "sma". Default: "sma"
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> tr (value, optional): Use True Range for Keltner Channels. Default: True
                asint (value, optional): Use integers instead of bool. Default: True
                mamode (value, optional): Which MA to use. Default: "sma"
                lazybear (value, optional): Use LazyBear's TradingView implementation.
                    Default: False
                detailed (value, optional): Return additional variations of SQZ for
                    visualization. Default: False
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['stc', 'stcmacd', 'stcstoch'], lib='pta')
    def stc(self, tclength=10, fast=12, slow=26, factor=0.5, offset=0, **kwargs) -> dataframe:
        """Schaff Trend Cycle (STC)
        ---------

        Returns:
        ---------
            >>> dataframe: stc, stcmacd, stcstoch
                args : close

        The Schaff Trend Cycle is an evolution of the popular MACD incorportating two
        cascaded stochastic calculations with additional smoothing.

        The STC returns also the beginning MACD result as well as the result after the
        first stochastic including its smoothing. This implementation has been extended
        for Pandas TA to also allow for separatly feeding any other two moving Averages
        (as ma1 and ma2) or to skip this to feed an oscillator (osc), based on which the
        Schaff Trend Cycle should be calculated.

        Feed external moving averages:
        Internally calculation..
            stc = ta.stc(close=df["close"], tclen=stc_tclen,
                         fast=ma1_interval, slow=ma2_interval, factor=stc_factor)
        becomes..
            extMa1 = df.ta.zlma(close=df["close"],
                                length=ma1_interval, append=True)
            extMa2 = df.ta.ema(close=df["close"],
                               length=ma2_interval, append=True)
            stc = ta.stc(close=df["close"], tclen=stc_tclen,
                         ma1=extMa1, ma2=extMa2, factor=stc_factor)

        The same goes for osc=, which allows the input of an externally calculated oscillator, overriding ma1 & ma2.


        Sources:
        ---------
            Implemented by rengel8 based on work found here:
            https://www.prorealcode.com/prorealtime-indicators/schaff-trend-cycle2/

        Calculation:
        ---------
            >>> STCmacd = Moving Average Convergance/Divergance or Oscillator
                STCstoch = Intermediate Stochastic of MACD/Osc.
                2nd Stochastic including filtering with results in the
                STC = Schaff Trend Cycle

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's, used for indexing Series, mandatory
                tclen (int): SchaffTC Signal-Line length.  Default: 10 (adjust to the half of cycle)
                fast (int): The short period.   Default: 12
                slow (int): The long period.   Default: 26
                factor (float): smoothing factor for last stoch. calculation.   Default: 0.5
                offset (int): How many periods to offset the result.  Default: 0

        Kwargs:
        ---------
            >>> ma1: 1st moving average provided externally (mandatory in conjuction with ma2)
                ma2: 2nd moving average provided externally (mandatory in conjuction with ma1)
                osc: an externally feeded osillator
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['stochs', 'stoch_k', 'stoch_d'], lib='pta')
    def stoch(self, k=14, d=3, smooth_k=3, mamode="sma", offset=0, **kwargs) -> dataframe:
        """Stochastic (STOCH)
        ---------

        Returns:
        ---------
            >>> dataframe: stochs,stoch_k ,stoch_d columns.
                args : high, low, close

        The Stochastic Oscillator (STOCH) was developed by George Lane in the 1950's.
        He believed this indicator was a good way to measure momentum because changes in
        momentum precede changes in price.

        It is a range-bound oscillator with two lines moving between 0 and 100.
        The first line (%K) displays the current close in relation to the period's
        high/low range. The second line (%D) is a Simple Moving Average of the %K line.
        The most common choices are a 14 period %K and a 3 period SMA for %D.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Stochastic_(STOCH)
            https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=332&Name=KD_-_Slow

        Calculation:
        ---------
            >>> Default Inputs:
                k=14, d=3, smooth_k=3
                SMA = Simple Moving Average
                LL  = low for last k periods
                HH  = high for last k periods
                STOCH = 100 * (close - LL) / (HH - LL)
                STOCHk = SMA(STOCH, smooth_k)
                STOCHd = SMA(FASTK, d)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                k (int): The Fast %K period. Default: 14
                d (int): The Slow %K period. Default: 3
                smooth_k (int): The Slow %D period. Default: 3
                mamode (str): See ```help(ta.ma)```. Default: 'sma'
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['stochrsi_k', 'stochrsi_d'], lib='pta')
    def stochrsi(self, length=14, rsi_length=14, k=3, d=3, mamode="sma", offset=0, **kwargs) -> dataframe:
        """Stochastic (STOCHRSI)
        ---------

        Returns:
        ---------
            >>> dataframe: stochrsi_k ,stochrsi_d columns.
                args : close

        "Stochastic RSI and Dynamic Momentum Index" was created by Tushar Chande and Stanley Kroll and published in Stock & Commodities V.11:5 (189-199)

        It is a range-bound oscillator with two lines moving between 0 and 100.
        The first line (%K) displays the current RSI in relation to the period's
        high/low range. The second line (%D) is a Simple Moving Average of the %K line.
        The most common choices are a 14 period %K and a 3 period SMA for %D.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Stochastic_(STOCH)

        Calculation:
        ---------
            >>> Default Inputs:
                length=14, rsi_length=14, k=3, d=3
                RSI = Relative Strength Index
                SMA = Simple Moving Average
                RSI = RSI(high, low, close, rsi_length)
                LL  = lowest RSI for last rsi_length periods
                HH  = highest RSI for last rsi_length periods
                STOCHRSI  = 100 * (RSI - LL) / (HH - LL)
                STOCHRSIk = SMA(STOCHRSI, k)
                STOCHRSId = SMA(STOCHRSIk, d)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): The STOCHRSI period. Default: 14
                rsi_length (int): RSI period. Default: 14
                k (int): The Fast %K period. Default: 3
                d (int): The Slow %K period. Default: 3
                mamode (str): See ```help(ta.ma)```. Default: 'sma'
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['td_seq_up', 'td_seq_dn'], lib='pta')
    def td_seq(self, asint=False, offset=0, show_all=True, **kwargs) -> dataframe:
        """TD Sequential (TD_SEQ)
        ---------

        Returns:
        ---------
            >>> dataframe: td_seq_up ,td_seq_dn columns.
                args : close

        Tom DeMark's Sequential indicator attempts to identify a price point where an
        uptrend or a downtrend exhausts itself and reverses.

        Sources:
        ---------
            https://tradetrekker.wordpress.com/tdsequential/

        Calculation:
        ---------
            Compare current close price with 4 days ago price, up to 13 days. For the
            consecutive ascending or descending price sequence, display 6th to 9th day
            value.

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                asint (bool): If True, fillnas with 0 and change type to int. Default: False
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            show_all (bool): Show 1 - 13. If set to False, show 6 - 9. Default: True
                fillna (value, optional): pd.DataFrame.fillna(value)
        """
        ...

    @tobtind(lines=['trix ', 'trixs'], lib='pta')
    def trix(self, length=18, signal=9, scalar=100., drift=1, offset=0, **kwargs) -> dataframe:
        """Trix (TRIX)
        ---------

        Returns:
        ---------
            >>> dataframe: trix ,trixs columns.
                args : close

        TRIX is a momentum oscillator to identify divergences.

        Sources:
        ---------
            https://www.tradingview.com/wiki/TRIX

        Calculation:
        ---------
            >>> Default Inputs:
                    length=18, drift=1
                EMA = Exponential Moving Average
                ROC = Rate of Change
                ema1 = EMA(close, length)
                ema2 = EMA(ema1, length)
                ema3 = EMA(ema2, length)
                TRIX = 100 * ROC(ema3, drift)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 18
                signal (int): It's period. Default: 9
                scalar (float): How much to magnify. Default: 100
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['tsir', 'tsis'], lib='pta')
    def tsi(self, fast=13, slow=25, signal=13, scalar=100., mamode="ema", drift=1,  offset=0, **kwargs) -> dataframe:
        """True Strength Index (TSI)
        ---------

        Returns:
        ---------
            >>> dataframe: tsir, tsis columns.
                args : close

        The True Strength Index is a momentum indicator used to identify short-term
        swings while in the direction of the trend as well as determining overbought
        and oversold conditions.

        Sources:
        ---------
            https://www.investopedia.com/terms/t/tsi.asp

        Calculation:
        ---------
            >>> Default Inputs:
                    fast=13, slow=25, signal=13, scalar=100, drift=1
                EMA = Exponential Moving Average
                diff = close.diff(drift)
                slow_ema = EMA(diff, slow)
                fast_slow_ema = EMA(slow_ema, slow)
                abs_diff_slow_ema = absolute_diff_ema = EMA(ABS(diff), slow)
                abema = abs_diff_fast_slow_ema = EMA(abs_diff_slow_ema, fast)
                TSI = scalar * fast_slow_ema / abema
                Signal = EMA(TSI, signal)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                fast (int): The short period. Default: 13
                slow (int): The long period. Default: 25
                signal (int): The signal period. Default: 13
                scalar (float): How much to magnify. Default: 100
                mamode (str): Moving Average of TSI Signal Line.
                    See ```help(ta.ma)```. Default: 'ema'
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def uo(self, fast=7, medium=14, slow=28, fast_w=4., medium_w=2.,
           slow_w=1., talib=True, drift=1, offset=0, **kwargs) -> series:
        """Ultimate Oscillator (UO)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low, close

        The Ultimate Oscillator is a momentum indicator over three different
        periods.  It attempts to correct false divergence trading signals.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Ultimate_Oscillator_(UO)

        Calculation:
        ---------
            >>> Default Inputs:
                    fast=7, medium=14, slow=28,
                    fast_w=4.0, medium_w=2.0, slow_w=1.0, drift=1
                min_low_or_pc  = close.shift(drift).combine(low, min)
                max_high_or_pc = close.shift(drift).combine(high, max)
                bp = buying pressure = close - min_low_or_pc
                tr = true range = max_high_or_pc - min_low_or_pc
                fast_avg = SUM(bp, fast) / SUM(tr, fast)
                medium_avg = SUM(bp, medium) / SUM(tr, medium)
                slow_avg = SUM(bp, slow) / SUM(tr, slow)
                total_weight = fast_w + medium_w + slow_w
                weights = (fast_w * fast_avg) + (medium_w * \
                           medium_avg) + (slow_w * slow_avg)
                UO = 100 * weights / total_weight

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                fast (int): The Fast %K period. Default: 7
                medium (int): The Slow %K period. Default: 14
                slow (int): The Slow %D period. Default: 28
                fast_w (float): The Fast %K period. Default: 4.0
                medium_w (float): The Slow %K period. Default: 2.0
                slow_w (float): The Slow %D period. Default: 1.0
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def willr(self, length=14, talib=True, offset=0, **kwargs) -> series:
        """William's Percent R (WILLR)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low, close

        William's Percent R is a momentum oscillator similar to the RSI that
        attempts to identify overbought and oversold conditions.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Williams_%25R_(%25R)

        Calculation:
        ---------
            >>> Default Inputs:
                    length=20
                LL = low.rolling(length).min()
                HH = high.rolling(length).max()
                WILLR = 100 * ((close - LL) / (HH - LL) - 1)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    # Overlap
    @tobtind(lines=None, overlap=True, lib='pta')
    def alma(self, length=10, sigma=6., distribution_offset=0.85, offset=0, **kwargs) -> series:
        """Arnaud Legoux Moving Average (ALMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The ALMA moving average uses the curve of the Normal (Gauss) distribution, which
        can be shifted from 0 to 1. This allows regulating the smoothness and high
        sensitivity of the indicator. Sigma is another parameter that is responsible for
        the shape of the curve coefficients. This moving average reduces lag of the data
        in conjunction with smoothing to reduce noise.

        Implemented for Pandas TA by rengel8 based on the source provided below.

        Sources:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/alma-arnaud-legoux-moving-average/

        Calculation:
        ---------
            refer to provided source

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period, window size. Default: 10
                sigma (float): Smoothing value. Default 6.0
                distribution_offset (float): Value to offset the distribution min 0
                    (smoother), max 1 (more responsive). Default 0.85
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def dema(self, length=10, talib=True, offset=0, **kwargs) -> series:
        """Double Exponential Moving Average (DEMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Double Exponential Moving Average attempts to a smoother average with less
        lag than the normal Exponential Moving Average (EMA).

        Sources:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/double-exponential-moving-average-dema/

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                EMA = Exponential Moving Average
                ema1 = EMA(close, length)
                ema2 = EMA(ema1, length)
                DEMA = 2 * ema1 - ema2

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def ema(self, length=10, talib=True, offset=0, **kwargs) -> series:
        """Exponential Moving Average (EMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Exponential Moving Average is more responsive moving average compared to the
        Simple Moving Average (SMA).  The weights are determined by alpha which is
        proportional to it's length.  There are several different methods of calculating
        EMA.  One method uses just the standard definition of EMA and another uses the
        SMA to generate the initial value for the rest of the calculation.

        Sources:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:moving_averages
            https://www.investopedia.com/ask/answers/122314/what-exponential-moving-average-ema-formula-and-how-ema-calculated.asp

        Calculation:
        ---------
            >>> Default Inputs:
                length=10, adjust=False, sma=True
                if sma:
                    sma_nth = close[0:length].sum() / length
                    close[:length - 1] = np.NaN
                    close.iloc[length - 1] = sma_nth
                EMA = close.ewm(span=length, adjust=adjust).mean()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> adjust (bool, optional): Default: False
                sma (bool, optional): If True, uses SMA for initial value. Default: True
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def fwma(self, length=10, asc=True, offset=0, **kwargs) -> series:
        """Fibonacci's Weighted Moving Average (FWMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Fibonacci's Weighted Moving Average is similar to a Weighted Moving Average
        (WMA) where the weights are based on the Fibonacci Sequence.

        Source: Kevin Johnson

        Calculation:
        ---------
            >>> Default Inputs:
                length=10,
                def weights(w):
                    def _compute(x):
                        return np.dot(w * x)
                    return _compute
                fibs = utils.fibonacci(length - 1)
                FWMA = close.rolling(length)_.apply(weights(fibs), raw=True)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                asc (bool): Recent values weigh more. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['hilo', 'hilol', 'hilos'], overlap=True, lib='pta')
    def hilo(self, high_length=13, low_length=21, mamode="sma", offset=0, **kwargs) -> dataframe:
        """Gann HiLo Activator(HiLo)
        ---------

        Returns:
        ---------
            >>> dataframe: hilo ,hilol(long) ,hilos(short) columns.
                args : high, low, close

        The Gann High Low Activator Indicator was created by Robert Krausz in a 1998
        issue of Stocks & Commodities Magazine. It is a moving average based trend
        indicator consisting of two different simple moving averages.

        The indicator tracks both curves (of the highs and the lows). The close of the
        bar defines which of the two gets plotted.

        Increasing high_length and decreasing low_length better for short trades,
        vice versa for long positions.

        Sources:
        ---------
            https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=447&Name=Gann_HiLo_Activator
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/simple-moving-average-sma/
            https://www.tradingview.com/script/XNQSLIYb-Gann-High-Low/

        Calculation:
        ---------
            >>> Default Inputs:
                high_length=13, low_length=21, mamode="sma"
                EMA = Exponential Moving Average
                HMA = Hull Moving Average
                SMA = Simple Moving Average # Default
                if "ema":
                    high_ma = EMA(high, high_length)
                    low_ma = EMA(low, low_length)
                elif "hma":
                    high_ma = HMA(high, high_length)
                    low_ma = HMA(low, low_length)
                else: # "sma"
                    high_ma = SMA(high, high_length)
                    low_ma = SMA(low, low_length)
                # Similar to Supertrend MA selection
                hilo = Series(np.nan, index=close.index)
                for i in range(1, m):
                    if close.iloc[i] > high_ma.iloc[i - 1]:
                        hilo.iloc[i] = low_ma.iloc[i]
                    elif close.iloc[i] < low_ma.iloc[i - 1]:
                        hilo.iloc[i] = high_ma.iloc[i]
                    else:
                        hilo.iloc[i] = hilo.iloc[i - 1]

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                high_length (int): It's period. Default: 13
                low_length (int): It's period. Default: 21
                mamode (str): See ```help(ta.ma)```. Default: 'sma'
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> adjust (bool): Default: True
                presma (bool, optional): If True, uses SMA for initial value.
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def hl2(self, offset=0, **kwargs) -> series:
        """Indicator: HL2
        ---------

            >>> args : high, low
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def hlc3(self, talib=True, offset=0, **kwargs) -> series:
        """Indicator: HLC3
        ---------

            >>> args : high, low
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def hma(self, length=10, offset=0, **kwargs) -> series:
        """Hull Moving Average (HMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Hull Exponential Moving Average attempts to reduce or remove lag in moving
        averages.

        Sources:
        ---------
            https://alanhull.com/hull-moving-average

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                WMA = Weighted Moving Average
                half_length = int(0.5 * length)
                sqrt_length = int(sqrt(length))
                wmaf = WMA(close, half_length)
                wmas = WMA(close, length)
                HMA = WMA(2 * wmaf - wmas, sqrt_length)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def hwma(self, na=0.2, nb=0.1, nc=0.1, offset=0, **kwargs) -> series:
        """HWMA (Holt-Winter Moving Average)
        ---------

        Returns:
        ---------
            >>> series: hwma
                args : close

        Indicator HWMA (Holt-Winter Moving Average) is a three-parameter moving average
        by the Holt-Winter method; the three parameters should be selected to obtain a
        forecast.

        This version has been implemented for Pandas TA by rengel8 based
        on a publication for MetaTrader 5.

        Sources:
        ---------
            https://www.mql5.com/en/code/20856

        Calculation:
        ---------
            HWMA[i] = F[i] + V[i] + 0.5 * A[i]
            where..
            F[i] = (1-na) * (F[i-1] + V[i-1] + 0.5 * A[i-1]) + na * Price[i]
            V[i] = (1-nb) * (V[i-1] + A[i-1]) + nb * (F[i] - F[i-1])
            A[i] = (1-nc) * A[i-1] + nc * (V[i] - V[i-1])

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                na (float): Smoothed series parameter (from 0 to 1). Default: 0.2
                nb (float): Trend parameter (from 0 to 1). Default: 0.1
                nc (float): Seasonality parameter (from 0 to 1). Default: 0.1
                close (pd.Series): Series of 'close's

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def jma(self, length=7, phase=0., offset=0, **kwargs) -> series:
        """Jurik Moving Average Average (JMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Mark Jurik's Moving Average (JMA) attempts to eliminate noise to see the "true"
        underlying activity. It has extremely low lag, is very smooth and is responsive
        to market gaps.

        Sources:
        ---------
            https://c.mql5.com/forextsd/forum/164/jurik_1.pdf
            https://www.prorealcode.com/prorealtime-indicators/jurik-volatility-bands/

        Calculation:
        ---------
            >>> Default Inputs:
                length=7, phase=0

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): Period of calculation. Default: 7
                phase (float): How heavy/light the average is [-100, 100]. Default: 0
                offset (int): How many lengths to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def kama(self, length=10, fast=2, slow=30, drift=1, offset=0, **kwargs) -> series:
        """Kaufman's Adaptive Moving Average (KAMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Developed by Perry Kaufman, Kaufman's Adaptive Moving Average (KAMA) is a moving average
        designed to account for market noise or volatility. KAMA will closely follow prices when
        the price swings are relatively small and the noise is low. KAMA will adjust when the
        price swings widen and follow prices from a greater distance. This trend-following indicator
        can be used to identify the overall trend, time turning points and filter price movements.

        Sources:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:kaufman_s_adaptive_moving_average
            https://www.tradingview.com/script/wZGOIz9r-REPOST-Indicators-3-Different-Adaptive-Moving-Averages/

        Calculation:
        ---------
            >>> Default Inputs:
                length=10

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                fast (int): Fast MA period. Default: 2
                slow (int): Slow MA period. Default: 30
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['spana', 'spanb', 'tenkan_sen', 'kijun_sen', 'chikou_span'], overlap=True, lib="pta")
    def ichimoku(self, tenkan=9, kijun=26, senkou=52, include_chikou=True, offset=0, **kwargs) -> dataframe:
        """Ichimoku Kinkō Hyō (ichimoku)
        ---------

        Returns:
        ---------
            >>> dataframe:  spana, spanb, tenkan_sen, kijun_sen,and chikou_span columns
                args : high, low, close

        Developed Pre WWII as a forecasting model for financial markets.

        Sources:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/ichimoku-ich/

        Calculation:
        ---------
            >>> Default Inputs:
                tenkan=9, kijun=26, senkou=52
                MIDPRICE = Midprice
                TENKAN_SEN = MIDPRICE(high, low, close, length=tenkan)
                KIJUN_SEN = MIDPRICE(high, low, close, length=kijun)
                CHIKOU_SPAN = close.shift(-kijun)
                SPAN_A = 0.5 * (TENKAN_SEN + KIJUN_SEN)
                SPAN_A = SPAN_A.shift(kijun)
                SPAN_B = MIDPRICE(high, low, close, length=senkou)
                SPAN_B = SPAN_B.shift(kijun)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                tenkan (int): Tenkan period. Default: 9
                kijun (int): Kijun period. Default: 26
                senkou (int): Senkou period. Default: 52
                include_chikou (bool): Whether to include chikou component. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def linreg(self, length=10, offset=0, **kwargs) -> series:
        """Linear Regression Moving Average (linreg)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Linear Regression Moving Average (LINREG). This is a simplified version of a
        Standard Linear Regression. LINREG is a rolling regression of one variable. A
        Standard Linear Regression is between two or more variables.

        Source: TA Lib

        Calculation:
        ---------
            >>> Default Inputs:
                length=14
                x = [1, 2, ..., n]
                x_sum = 0.5 * length * (length + 1)
                x2_sum = length * (length + 1) * (2 * length + 1) / 6
                divisor = length * x2_sum - x_sum * x_sum
                lr(series):
                    y_sum = series.sum()
                    y2_sum = (series* series).sum()
                    xy_sum = (x * series).sum()
                    m = (length * xy_sum - x_sum * y_sum) / divisor
                    b = (y_sum * x2_sum - x_sum * xy_sum) / divisor
                    return m * (length - 1) + b
                linreg = close.rolling(length).apply(lr)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period.  Default: 10
                offset (int): How many periods to offset the result.  Default: 0

        Kwargs:
        ---------
            >>> angle (bool, optional): If True, returns the angle of the slope in radians.
                    Default: False.
                degrees (bool, optional): If True, returns the angle of the slope in
                    degrees. Default: False.
                intercept (bool, optional): If True, returns the angle of the slope in
                    radians. Default: False.
                r (bool, optional): If True, returns it's correlation 'r'. Default: False.
                slope (bool, optional): If True, returns the slope. Default: False.
                tsf (bool, optional): If True, returns the Time Series Forecast value.
                    Default: False.
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def mcgd(self, length=10, offset=0, c=1., **kwargs) -> series:
        """McGinley Dynamic Indicator
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The McGinley Dynamic looks like a moving average line, yet it is actually a
        smoothing mechanism for prices that minimizes price separation, price whipsaws,
        and hugs prices much more closely. Because of the calculation, the Dynamic Line
        speeds up in down markets as it follows prices yet moves more slowly in up
        markets. The indicator was designed by John R. McGinley, a Certified Market
        Technician and former editor of the Market Technicians Association's Journal
        of Technical Analysis.

        Sources:
        ---------
            https://www.investopedia.com/articles/forex/09/mcginley-dynamic-indicator.asp

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                offset=0
                c=1
                def mcg_(series):
                    denom = (constant * length * \
                             (series.iloc[1] / series.iloc[0]) ** 4)
                    series.iloc[1] = (
                        series.iloc[0] + ((series.iloc[1] - series.iloc[0]) / denom))
                    return series.iloc[1]
                mcg_cell = close[0:].rolling(
                    2, min_periods=2).apply(mcg_, raw=False)
                mcg_ds = close[:1].append(mcg_cell[1:])

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): Indicator's period. Default: 10
                offset (int): Number of periods to offset the result. Default: 0
                c (float): Multiplier for the denominator, sometimes set to 0.6. Default: 1

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def midpoint(self, length=2, talib=True, offset=0, **kwargs) -> series:
        """Indicator: Midpoint
        ---------

            >>> args : close
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def midprice(self, length=2, talib=True, offset=0, **kwargs) -> series:
        """Indicator: Midprice
        ---------

            >>> args : high, low
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def ohlc4(self, offset=0, **kwargs) -> series:
        """Indicator: OHLC4
        ---------

            >>> args : open, high, low, close
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def pwma(self, length=10, asc=True, offset=0, **kwargs) -> series:
        """Pascal's Weighted Moving Average (PWMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Pascal's Weighted Moving Average is similar to a symmetric triangular window
        except PWMA's weights are based on Pascal's Triangle.

        Source: Kevin Johnson

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                def weights(w):
                    def _compute(x):
                        return np.dot(w * x)
                    return _compute
                triangle = utils.pascals_triangle(length + 1)
                PWMA = close.rolling(length)_.apply(weights(triangle), raw=True)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period.  Default: 10
                asc (bool): Recent values weigh more. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def ma(self, name: str = "sma", length: int = 10, **kwargs) -> series:
        """Simple MA Utility for easier MA selection

        Available MAs:
            dema, ema, fwma, hma, linreg, midpoint, pwma, rma,
            sinwma, sma, swma, t3, tema, trima, vidya, wma, zlma

        Examples:
            ema8 = ta.ma("ema", df.close, length=8)
            sma50 = ta.ma("sma", df.close, length=50)
            pwma10 = ta.ma("pwma", df.close, length=10, asc=False)

        Args:
            name (str): One of the Available MAs. Default: "ema"
            source (pd.Series): The 'source' Series.

        Kwargs:
            Any additional kwargs the MA may require.

        Returns:
            pd.Series: New feature generated.
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def rma(self, length=10, offset=0, **kwargs) -> series:
        """wildeR's Moving Average (RMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The WildeR's Moving Average is simply an Exponential Moving Average (EMA) with
        a modified alpha = 1 / length.

        Sources:
        ---------
            https://tlc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/V-Z/WildersSmoothing
            https://www.incrediblecharts.com/indicators/wilder_moving_average.php

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                EMA = Exponential Moving Average
                alpha = 1 / length
                RMA = EMA(close, alpha=alpha)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def sinwma(self, length=10, offset=0, **kwargs) -> series:
        """Sine Weighted Moving Average (SWMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        A weighted average using sine cycles. The middle term(s) of the average have the
        highest weight(s).

        Source:
            https://www.tradingview.com/script/6MWFvnPO-Sine-Weighted-Moving-Average/
            Author: Everget (https://www.tradingview.com/u/everget/)

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                def weights(w):
                    def _compute(x):
                        return np.dot(w * x)
                    return _compute
                sines = Series([sin((i + 1) * pi / (length + 1))
                               for i in range(0, length)])
                w = sines / sines.sum()
                SINWMA = close.rolling(length, min_periods=length).apply(
                    weights(w), raw=True)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def sma(self, length=10, talib=True, offset=0, **kwargs) -> series:
        """Simple Moving Average (SMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Simple Moving Average is the classic moving average that is the equally
        weighted average over n periods.

        Sources:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/simple-moving-average-sma/

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                SMA = SUM(close, length) / length

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> adjust (bool): Default: True
                presma (bool, optional): If True, uses SMA for initial value.
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def ssf(self, length=10, poles=2, offset=0, **kwargs) -> series:
        """Ehler's Super Smoother Filter (SSF) © 2013
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        John F. Ehlers's solution to reduce lag and remove aliasing noise with his
        research in aerospace analog filter design. This indicator comes with two
        versions determined by the keyword poles. By default, it uses two poles but
        there is an option for three poles. Since SSF is a (Resursive) Digital Filter,
        the number of poles determine how many prior recursive SSF bars to include in
        the design of the filter. So two poles uses two prior SSF bars and three poles
        uses three prior SSF bars for their filter calculations.

        Sources:
        ---------
            http://www.stockspotter.com/files/PredictiveIndicators.pdf
            https://www.tradingview.com/script/VdJy0yBJ-Ehlers-Super-Smoother-Filter/
            https://www.mql5.com/en/code/588
            https://www.mql5.com/en/code/589

        Calculation:
        ---------
            >>> Default Inputs:
                length=10, poles=[2, 3]
                See the source code or Sources listed above.

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                poles (int): The number of poles to use, either 2 or 3. Default: 2
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['trend', 'dir', 'long', 'short'], overlap=True, lib='pta')
    def supertrend(self, length=7, multiplier=3., offset=0, **kwargs) -> dataframe:
        """Supertrend (supertrend)
        ---------

        Returns:
        ---------
            >>> dataframe: trend, dir, long, short columns.
                args : high, low, close
        Supertrend is an overlap indicator. It is used to help identify trend
        direction, setting stop loss, identify support and resistance, and/or
        generate buy & sell signals.

        Sources:
        ---------
            http://www.freebsensetips.com/blog/detail/7/What-is-supertrend-indicator-its-calculation

        Calculation:
        ---------
            >>> Default Inputs:
                length=7, multiplier=3.0
                Default Direction:
                Set to +1 or bullish trend at start
                MID = multiplier * ATR
                LOWERBAND = HL2 - MID
                UPPERBAND = HL2 + MID
                if UPPERBAND[i] < FINAL_UPPERBAND[i-1] and close[i-1] > FINAL_UPPERBAND[i-1]:
                    FINAL_UPPERBAND[i] = UPPERBAND[i]
                else:
                    FINAL_UPPERBAND[i] = FINAL_UPPERBAND[i-1])
                if LOWERBAND[i] > FINAL_LOWERBAND[i-1] and close[i-1] < FINAL_LOWERBAND[i-1]:
                    FINAL_LOWERBAND[i] = LOWERBAND[i]
                else:
                    FINAL_LOWERBAND[i] = FINAL_LOWERBAND[i-1])
                if close[i] <= FINAL_UPPERBAND[i]:
                    SUPERTREND[i] = FINAL_UPPERBAND[i]
                else:
                    SUPERTREND[i] = FINAL_LOWERBAND[i]

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int) : length for ATR calculation. Default: 7
                multiplier (float): Coefficient for upper and lower band distance to
                    midrange. Default: 3.0
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def swma(self, length=10, asc=True, offset=0, **kwargs) -> series:
        """Symmetric Weighted Moving Average (SWMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Symmetric Weighted Moving Average where weights are based on a symmetric
        triangle.  For example: n=3 -> [1, 2, 1], n=4 -> [1, 2, 2, 1], etc...
        This moving average has variable length in contrast to TradingView's fixed
        length of 4.

        Source:
            https://www.tradingview.com/study-script-reference/#fun_swma

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                def weights(w):
                    def _compute(x):
                        return np.dot(w * x)
                    return _compute
                triangle = utils.symmetric_triangle(length - 1)
                SWMA = close.rolling(length)_.apply(weights(triangle), raw=True)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                asc (bool): Recent values weigh more. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def t3(self, length=10, a=0.7, talib=True, offset=0, **kwargs) -> series:
        """Tim Tillson's T3 Moving Average (T3)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Tim Tillson's T3 Moving Average is considered a smoother and more responsive
        moving average relative to other moving averages.

        Sources:
        ---------
            http://www.binarytribune.com/forex-trading-indicators/t3-moving-average-indicator/

        Calculation:
        ---------
            >>> Default Inputs:
                length=10, a=0.7
                c1 = -a^3
                c2 = 3a^2 + 3a^3 = 3a^2 * (1 + a)
                c3 = -6a^2 - 3a - 3a^3
                c4 = a^3 + 3a^2 + 3a + 1
                ema1 = EMA(close, length)
                ema2 = EMA(ema1, length)
                ema3 = EMA(ema2, length)
                ema4 = EMA(ema3, length)
                ema5 = EMA(ema4, length)
                ema6 = EMA(ema5, length)
                T3 = c1 * ema6 + c2 * ema5 + c3 * ema4 + c4 * ema3

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                a (float): 0 < a < 1. Default: 0.7
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> adjust (bool): Default: True
                presma (bool, optional): If True, uses SMA for initial value.
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def tema(self, length=10, talib=True, offset=0, **kwargs) -> series:
        """Triple Exponential Moving Average (TEMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        A less laggy Exponential Moving Average.

        Sources:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/triple-exponential-moving-average-tema/

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                EMA = Exponential Moving Average
                ema1 = EMA(close, length)
                ema2 = EMA(ema1, length)
                ema3 = EMA(ema2, length)
                TEMA = 3 * (ema1 - ema2) + ema3

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> adjust (bool): Default: True
                presma (bool, optional): If True, uses SMA for initial value.
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def trima(self, length=10, talib=True, offset=0, **kwargs) -> series:
        """Triangular Moving Average (TRIMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        A weighted moving average where the shape of the weights are triangular and the
        greatest weight is in the middle of the period.

        Sources:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/triangular-moving-average-trima/
            tma = sma(sma(src, ceil(length / 2)),
                      floor(length / 2) + 1)  # Tradingview
            trima = sma(sma(x, n), n)  # Tradingview

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                SMA = Simple Moving Average
                half_length = round(0.5 * (length + 1))
                SMA1 = SMA(close, half_length)
                TRIMA = SMA(SMA1, half_length)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> adjust (bool): Default: True
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def vidya(self, length=14, drift=1, offset=0, **kwargs) -> series:
        """Variable Index Dynamic Average (VIDYA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Variable Index Dynamic Average (VIDYA) was developed by Tushar Chande. It is
        similar to an Exponential Moving Average but it has a dynamically adjusted
        lookback period dependent on relative price volatility as measured by Chande
        Momentum Oscillator (CMO). When volatility is high, VIDYA reacts faster to
        price changes. It is often used as moving average or trend identifier.

        Sources:
        ---------
            https://www.tradingview.com/script/hdrf0fXV-Variable-Index-Dynamic-Average-VIDYA/
            https://www.perfecttrendsystem.com/blog_mt4_2/en/vidya-indicator-for-mt4

        Calculation:
        ---------
            >>> Default Inputs:
                length=10, adjust=False, sma=True
                if sma:
                    sma_nth = close[0:length].sum() / length
                    close[:length - 1] = np.NaN
                    close.iloc[length - 1] = sma_nth
                EMA = close.ewm(span=length, adjust=adjust).mean()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> adjust (bool, optional): Use adjust option for EMA calculation. Default: False
                sma (bool, optional): If True, uses SMA for initial value for EMA calculation. Default: True
                talib (bool): If True, uses TA-Libs implementation for CMO. Otherwise uses EMA version. Default: True
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def vwap(self, anchor="D", offset=0, **kwargs) -> series:
        """Volume Weighted Average Price (VWAP)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low, close, volume

        The Volume Weighted Average Price that measures the average typical price
        by volume.  It is typically used with intraday charts to identify general
        direction.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Volume_Weighted_Average_Price_(VWAP)
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/volume-weighted-average-price-vwap/
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:vwap_intraday

        Calculation:
        ---------
            tp = typical_price = hlc3(high, low, close)
            tpv = tp * volume
            VWAP = tpv.cumsum() / volume.cumsum()

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                anchor (str): How to anchor VWAP. Depending on the index values, it will
                    implement various Timeseries Offset Aliases as listed here:
                    https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#timeseries-offset-aliases
                    Default: "D".
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def vwma(self, length=10, offset=0, **kwargs) -> series:
        """Volume Weighted Moving Average (VWMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close, volume

        Volume Weighted Moving Average.

        Sources:
        ---------
            https://www.motivewave.com/studies/volume_weighted_moving_average.htm

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                SMA = Simple Moving Average
                pv = close * volume
                VWMA = SMA(pv, length) / SMA(volume, length)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                length (int): It's period. Default: 10
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def wcp(self, talib=True, offset=0, **kwargs) -> series:
        """Weighted Closing Price (WCP)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low, close

        Weighted Closing Price is the weighted price given: high, low
        and double the close.

        Sources:
        ---------
            https://www.fmlabs.com/reference/default.htm?url=WeightedCloses.htm

        Calculation:
        ---------
            WCP = (2 * close + high + low) / 4

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def wma(self, length=10, asc=True, talib=True, offset=0, **kwargs) -> series:
        """Weighted Moving Average (WMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Weighted Moving Average where the weights are linearly increasing and
        the most recent data has the heaviest weight.

        Sources:
        ---------
            https://en.wikipedia.org/wiki/Moving_average#Weighted_moving_average

        Calculation:
        ---------
            >>> Default Inputs:
                length=10, asc=True
                total_weight = 0.5 * length * (length + 1)
                weights_ = [1, 2, ..., length + 1]  # Ascending
                weights = weights if asc else weights[::-1]
                def linear_weights(w):
                    def _compute(x):
                        return (w * x).sum() / total_weight
                    return _compute
                WMA = close.rolling(length)_.apply(linear_weights(weights), raw=True)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                asc (bool): Recent values weigh more. Default: True
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def zlma(self, length=10, mamode="ema", offset=0, **kwargs) -> series:
        """Zero Lag Moving Average (ZLMA)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        The Zero Lag Moving Average attempts to eliminate the lag associated
        with moving averages.  This is an adaption created by John Ehler and Ric Way.

        Sources:
        ---------
            https://en.wikipedia.org/wiki/Zero_lag_exponential_moving_average

        Calculation:
        ---------
            >>> Default Inputs:
                length=10, mamode=EMA
                EMA = Exponential Moving Average
                lag = int(0.5 * (length - 1))
                SOURCE = 2 * close - close.shift(lag)
                ZLMA = MA(kind=mamode, SOURCE, length)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                mamode (str): Options: 'ema', 'hma', 'sma', 'wma'. Default: 'ema'
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    # Performance
    @tobtind(lines=None, lib='pta')
    def log_return(self, length=20, cumulative=False, offset=0, **kwargs) -> series:
        """Log Return
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Calculates the logarithmic return of a Series.
        See also: help(df.ta.log_return) for additional **kwargs a valid 'df'.

        Sources:
        ---------
            https://stackoverflow.com/questions/31287552/logarithmic-returns-in-pandas-dataframe

        Calculation:
        ---------
            >>> Default Inputs:
                length=1, cumulative=False
                LOGRET = log( close.diff(periods=length) )
                CUMLOGRET = LOGRET.cumsum() if cumulative

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 20
                cumulative (bool): If True, returns the cumulative returns. Default: False
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def percent_return(self, length=20, cumulative=False, offset=0, **kwargs) -> series:
        """Percent Return
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Calculates the percent return of a Series.
        See also: help(df.ta.percent_return) for additional **kwargs a valid 'df'.

        Sources:
        ---------
            https://stackoverflow.com/questions/31287552/logarithmic-returns-in-pandas-dataframe

        Calculation:
        ---------
            >>> Default Inputs:
                length=1, cumulative=False
                PCTRET = close.pct_change(length)
                CUMPCTRET = PCTRET.cumsum() if cumulative

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 20
                cumulative (bool): If True, returns the cumulative returns. Default: False
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    # Statistics
    @tobtind(lines=None, lib='pta')
    def entropy(self, length=10, base=2., offset=0, **kwargs) -> series:
        """Entropy (ENTP)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Introduced by Claude Shannon in 1948, entropy measures the unpredictability
        of the data, or equivalently, of its average information. A die has higher
        entropy (p=1/6) versus a coin (p=1/2).

        Sources:
        ---------
            https://en.wikipedia.org/wiki/Entropy_(information_theory)

        Calculation:
        ---------
            >>> Default Inputs:
                length=10, base=2
                P = close / SUM(close, length)
                E = SUM(-P * npLog(P) / npLog(base), length)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                base (float): Logarithmic Base. Default: 2
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def kurtosis_(self, length=30, offset=0, **kwargs) -> series:
        """Rolling Kurtosis
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Sources:
        ---------

        Calculation:
        ---------
            >>> Default Inputs:
                length=30
                KURTOSIS = close.rolling(length).kurt()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 30
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def mad(self, length=30, offset=0, **kwargs) -> series:
        """Rolling Mean Absolute Deviation
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Sources:
        ---------

        Calculation:
        ---------
            >>> Default Inputs:
                length=30
                mad = close.rolling(length).mad()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 30
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def median(self, length=30, offset=0, **kwargs) -> series:
        """Rolling Median
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Rolling Median of over 'n' periods. Sibling of a Simple Moving Average.

        Sources:
        ---------
            https://www.incrediblecharts.com/indicators/median_price.php

        Calculation:
        ---------
            >>> Default Inputs:
                length=30
                MEDIAN = close.rolling(length).median()
f
        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 30
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def quantile_(self, length=30, q=0.5, offset=0, **kwargs) -> series:
        """Rolling Quantile
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Sources:
        ---------

        Calculation:
        ---------
            >>> Default Inputs:
                length=30, q=0.5
                QUANTILE = close.rolling(length).quantile(q)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 30
                q (float): The quantile. Default: 0.5
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def skew_(self, length=30, offset=0, **kwargs) -> series:
        """Rolling Skew
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Sources:
        ---------

        Calculation:
        ---------
            >>> Default Inputs:
                length=30
                SKEW = close.rolling(length).skew()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 30
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def stdev(self, length=30, ddof=1, talib=True, offset=0, **kwargs) -> series:
        """Rolling Standard Deviation
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Sources:
        ---------

        Calculation:
        ---------
            >>> Default Inputs:
                length=30
                VAR = Variance
                STDEV = variance(close, length).apply(np.sqrt)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 30
                ddof (int): Delta Degrees of Freedom.
                            The divisor used in calculations is N - ddof,
                            where N represents the number of elements. Default: 1
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['toslr', 'tosl1', 'tosu1', 'tosl2', 'tosu2', 'tosl3', 'tosu3'], lib='pta')
    def tos_stdevall(self, length=30, stds=[1, 2, 3], ddof=1, offset=0, **kwargs) -> dataframe:
        """TD Ameritrade's Think or Swim Standard Deviation All (TOS_STDEV)
        ---------

        Returns:
        ---------
            >>> dataframe: toslr ,tosl1(Lower),tosu1(Upper) ,tosl2,tosu2 ,tosl3, tosu3 columns.
            >>> dataframe: Central LR, Pairs of Lower and Upper LR Lines based on
                mulitples of the standard deviation. Default: returns 7 columns.
                args : close
        A port of TD Ameritrade's Think or Swim Standard Deviation All indicator which
        returns the standard deviation of data for the entire plot or for the interval
        of the last bars defined by the length parameter.

        Sources:
        ---------
            https://tlc.thinkorswim.com/center/reference/thinkScript/Functions/Statistical/StDevAll

        Calculation:
        ---------
            >>> Default Inputs:
                length=None (All), stds=[1, 2, 3], ddof=1
                LR = Linear Regression
                STDEV = Standard Deviation
                LR = LR(close, length)
                STDEV = STDEV(close, length, ddof)
                for level in stds:
                    LOWER = LR - level * STDEV
                    UPPER = LR + level * STDEV

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): Bars from current bar. Default: None
                stds (list): List of Standard Deviations in increasing order from the
                            central Linear Regression line. Default: [1,2,3]
                ddof (int): Delta Degrees of Freedom.
                            The divisor used in calculations is N - ddof,
                            where N represents the number of elements. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def variance(self, length=30, ddof=1, talib=True, offset=0, **kwargs) -> series:
        """Rolling Variance
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Sources:
        ---------

        Calculation:
        ---------
            >>> Default Inputs:
                length=30
                VARIANCE = close.rolling(length).var()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 30
                ddof (int): Delta Degrees of Freedom.
                            The divisor used in calculations is N - ddof,
                            where N represents the number of elements. Default: 0
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def zscore(self, length=30, std=1., offset=0, **kwargs) -> series:
        """Rolling Z Score
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Sources:
        ---------

        Calculation:
        ---------
            >>> Default Inputs:
                length=30, std=1
                SMA = Simple Moving Average
                STDEV = Standard Deviation
                std = std * STDEV(close, length)
                mean = SMA(close, length)
                ZSCORE = (close - mean) / std

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 30
                std (float): It's period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    # Trend
    @tobtind(lines=['adxx', 'dmp', 'dmn'], lib='pta')
    def adx(self, length=14, lensig=14, scalar=100, mamode="rma", drift=1, offset=0, **kwargs) -> dataframe:
        """Average Directional Movement (ADX)
        ---------

        Returns:
        ---------
            >>> dataframe: adxx, dmp, dmn columns.
                args : high, low, close

        Average Directional Movement is meant to quantify trend strength by measuring
        the amount of movement in a single direction.

        Sources:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/average-directional-movement-adx/
            TA Lib Correlation: >99%

        Calculation:
        ---------
            >>> DMI ADX TREND 2.0 by @TraderR0BERT, NETWORTHIE.COM
                //Created by @TraderR0BERT, NETWORTHIE.COM, last updated 01/26/2016
                //DMI Indicator
                //Resolution input option for higher/lower time frames
                study(title="DMI ADX TREND 2.0", shorttitle="ADX TREND 2.0")
                adxlen = input(14, title="ADX Smoothing")
                dilen = input(14, title="DI Length")
                thold = input(20, title="Threshold")
                threshold = thold
                //Script for Indicator
                dirmov(len) =>
                    up = change(high)
                    down = -change(low)
                    truerange = rma(tr, len)
                    plus = fixnan(100 * rma(up > down and up > 0 ? up : 0, len) / truerange)
                    minus = fixnan(100 * rma(down > up and down > 0 ? down : 0, len) / truerange)
                    [plus, minus]
                adx(dilen, adxlen) =>
                    [plus, minus] = dirmov(dilen)
                    sum = plus + minus
                    adx = 100 * rma(abs(plus - minus) / (sum == 0 ? 1 : sum), adxlen)
                    [adx, plus, minus]
                [sig, up, down] = adx(dilen, adxlen)
                osob=input(40,title="Exhaustion Level for ADX, default = 40")
                col = sig >= sig[1] ? green : sig <= sig[1] ? red : gray
                //Plot Definitions Current Timeframe
                p1 = plot(sig, color=col, linewidth = 3, title="ADX")
                p2 = plot(sig, color=col, style=circles,
                          linewidth=3, title="ADX")
                p3 = plot(up, color=blue, linewidth = 3, title="+DI")
                p4 = plot(up, color=blue, style=circles,
                          linewidth=3, title="+DI")
                p5 = plot(down, color=fuchsia, linewidth = 3, title="-DI")
                p6 = plot(down, color=fuchsia, style=circles,
                          linewidth=3, title="-DI")
                h1 = plot(threshold, color=black,
                          linewidth =3, title="Threshold")
                trender = (sig >= up or sig >= down) ? 1 : 0
                bgcolor(trender>0?black:gray, transp=85)
                //Alert Function for ADX crossing Threshold
                Up_Cross = crossover(up, threshold)
                alertcondition(Up_Cross, title="DMI+ cross",
                               message="DMI+ Crossing Threshold")
                Down_Cross = crossover(down, threshold)
                alertcondition(Down_Cross, title="DMI- cross",
                               message="DMI- Crossing Threshold")

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                lensig (int): Signal Length. Like TradingView's default ADX. Default: length
                scalar (float): How much to magnify. Default: 100
                mamode (str): See ```help(ta.ma)```. Default: 'rma'
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['amatl', 'amats'], lib='pta')
    def amat(self, fast=8, slow=21, lookback=2, mamode="ema", offset=0, **kwargs) -> dataframe:
        """Indicator: Archer Moving Averages Trends (AMAT)
        ---------

        Returns:
        ---------
            >>> dataframe : amatl ,amats columns.
                args : close
        """
        ...

    @tobtind(lines=['aroon_up', 'aroon_down', 'aroon_osc'], lib='pta')
    def aroon(self, length=14, scalar=100, talib=True, offset=0, **kwargs) -> dataframe:
        """Aroon & Aroon Oscillator (AROON)
        ---------

        Returns:
        ---------
            >>> dataframe: aroon_up, aroon_down, aroon_osc columns.
                args : high, low

        Aroon attempts to identify if a security is trending and how strong.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Aroon
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/aroon-ar/

        Calculation:
        ---------
            >>> Default Inputs:
                length=1, scalar=100
                recent_maximum_index(x): return int(np.argmax(x[::-1]))
                recent_minimum_index(x): return int(np.argmin(x[::-1]))
                periods_from_hh = high.rolling(
                    length + 1).apply(recent_maximum_index, raw=True)
                AROON_UP = scalar * (1 - (periods_from_hh / length))
                periods_from_ll = low.rolling(
                    length + 1).apply(recent_minimum_index, raw=True)
                AROON_DN = scalar * (1 - (periods_from_ll / length))
                AROON_OSC = AROON_UP - AROON_DN

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                scalar (float): How much to magnify. Default: 100
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def chop(self, length=14, atr_length=1., ln=False, scalar=100, drift=1, offset=0, **kwargs) -> series:
        """Choppiness Index (CHOP)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low, close

        The Choppiness Index was created by Australian commodity trader
        E.W. Dreiss and is designed to determine if the market is choppy
        (trading sideways) or not choppy (trading within a trend in either
        direction). Values closer to 100 implies the underlying is choppier
        whereas values closer to 0 implies the underlying is trending.

        Sources:
        ---------
            https://www.tradingview.com/scripts/choppinessindex/
            https://www.motivewave.com/studies/choppiness_index.htm

        Calculation:
        ---------
            >>> Default Inputs:
                length=14, scalar=100, drift=1
                HH = high.rolling(length).max()
                LL = low.rolling(length).min()
                ATR_SUM = SUM(ATR(drift), length)
                CHOP = scalar * (LOG10(ATR_SUM) - LOG10(HH - LL))
                CHOP /= LOG10(length)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                atr_length (int): Length for ATR. Default: 1
                ln (bool): If True, uses ln otherwise log10. Default: False
                scalar (float): How much to magnify. Default: 100
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['cksp_long', 'cksp_short'], lib='pta')
    def cksp(self, p=10, x=3, q=20, tvmode=True, offset=0, **kwargs) -> dataframe:
        """Chande Kroll Stop (CKSP)
        ---------

        Returns:
        ---------
            >>> dataframe: cksp_long and cksp_short columns.
                args : high, low, close

        The Tushar Chande and Stanley Kroll in their book
        “The New Technical Trader”. It is a trend-following indicator,
        identifying your stop by calculating the average true range of
        the recent market volatility. The indicator defaults to the implementation
        found on tradingview but it provides the original book implementation as well,
        which differs by the default periods and moving average mode. While the trading
        view implementation uses the Welles Wilder moving average, the book uses a
        simple moving average.

        Sources:
        ---------
            https://www.multicharts.com/discussion/viewtopic.php?t=48914
            "The New Technical Trader", Wikey 1st ed. ISBN 9780471597803, page 95

        Calculation:
        ---------
            >>> Default Inputs:
                p=10, x=1, q=9, tvmode=True
                ATR = Average True Range
                LS0 = high.rolling(p).max() - x * ATR(length=p)
                LS = LS0.rolling(q).max()
                SS0 = high.rolling(p).min() + x * ATR(length=p)
                SS = SS0.rolling(q).min()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                p (int): ATR and first stop period. Default: 10 in both modes
                x (float): ATR scalar. Default: 1 in TV mode, 3 otherwise
                q (int): Second stop period. Default: 9 in TV mode, 20 otherwise
                tvmode (bool): Trading View or book implementation mode. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def decay(self, kind="exponential", length=5, mode="linear", offset=0, **kwargs) -> series:
        """Decay
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Creates a decay moving forward from prior signals like crosses. The default is
        "linear". Exponential is optional as "exponential" or "exp".

        Sources:
        ---------
            https://tulipindicators.org/decay

        Calculation:
        ---------
            >>> Default Inputs:
                length=5, mode=None
                if mode == "exponential" or mode == "exp":
                    max(close, close[-1] - exp(-length), 0)
                else:
                    max(close, close[-1] - (1 / length), 0)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 1
                mode (str): If 'exp' then "exponential" decay. Default: 'linear'
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def decreasing(self, length=1, strict=False, asint=True, percent=None, drift=1, offset=0, **kwargs) -> series:
        """Decreasing
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Returns True if the series is decreasing over a period, False otherwise.
        If the kwarg 'strict' is True, it returns True if it is continuously decreasing
        over the period. When using the kwarg 'asint', then it returns 1 for True
        or 0 for False.

        Calculation:
        ---------
            if strict:
                decreasing = all(i > j for i, j in zip(
                    close[-length:], close[1:]))
            else:
                decreasing = close.diff(length) < 0

            if asint:
                decreasing = decreasing.astype(int)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 1
                strict (bool): If True, checks if the series is continuously decreasing over the period. Default: False
                percent (float): Percent as an integer. Default: None
                asint (bool): Returns as binary. Default: True
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def dpo(self, length=20, centered=True, offset=0, **kwargs) -> series:
        """Detrend Price Oscillator (DPO)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Is an indicator designed to remove trend from price and make it easier to
        identify cycles.

        Sources:
        ---------
            https://www.tradingview.com/scripts/detrendedpriceoscillator/
            https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/dpo
            http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:detrended_price_osci

        Calculation:
        ---------
            >>> Default Inputs:
                length=20, centered=True
                SMA = Simple Moving Average
                t = int(0.5 * length) + 1
                DPO = close.shift(t) - SMA(close, length)
                if centered:
                    DPO = DPO.shift(-t)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 20
                centered (bool): Shift the dpo back by int(0.5 * length) + 1. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def increasing(self, length=1, strict=False, asint=True, percent=None, drift=1, offset=0, **kwargs) -> series:
        """Increasing
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        Returns True if the series is increasing over a period, False otherwise.
        If the kwarg 'strict' is True, it returns True if it is continuously increasing
        over the period. When using the kwarg 'asint', then it returns 1 for True
        or 0 for False.

        Calculation:
        ---------
            if strict:
                increasing = all(i < j for i, j in zip(
                    close[-length:], close[1:]))
            else:
                increasing = close.diff(length) > 0

            if asint:
                increasing = increasing.astype(int)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): It's period. Default: 1
                strict (bool): If True, checks if the series is continuously increasing over the period. Default: False
                percent (float): Percent as an integer. Default: None
                asint (bool): Returns as binary. Default: True
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def long_run(self, fast=None, slow=None, length=2, offset=0, **kwargs) -> series:
        """Indicator: Long Run
        ---------

            >>> args : self
        """
        ...

    @tobtind(lines=['psarl', 'psars', 'psaraf', 'psarr'], lib='pta')
    def psar(self, af0=0.02, af=0.02, max_af=0.2, offset=0, **kwargs) -> dataframe:
        """Parabolic Stop and Reverse (psar)
        ---------

        Returns:
        ---------
           >>> dataframe: psarl(long), psars(short), psaraf(af), and psarr(reversal) columns.
                args : high, low, close
        Parabolic Stop and Reverse (PSAR) was developed by J. Wells Wilder, that is used
        to determine trend direction and it's potential reversals in price. PSAR uses a
        trailing stop and reverse method called "SAR," or stop and reverse, to identify
        possible entries and exits. It is also known as SAR.

        PSAR indicator typically appears on a chart as a series of dots, either above or
        below an asset's price, depending on the direction the price is moving. A dot is
        placed below the price when it is trending upward, and above the price when it
        is trending downward.

        Sources:
        ---------
            https://www.tradingview.com/pine-script-reference/#fun_sar
            https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=66&Name=Parabolic

        Calculation:
        ---------
            >>> Default Inputs:
                af0=0.02, af=0.02, max_af=0.2

            See Source links

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series, optional): Series of 'close's. Optional
                af0 (float): Initial Acceleration Factor. Default: 0.02
                af (float): Acceleration Factor. Default: 0.02
                max_af (float): Maximum Acceleration Factor. Default: 0.2
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def qstick(self, length=10, ma="sma", offset=0, **kwargs) -> series:
        """Q Stick
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : open, close

        The Q Stick indicator, developed by Tushar Chande, attempts to quantify and
        identify trends in candlestick charts.

        Sources:
        ---------
            https://library.tradingtechnologies.com/trade/chrt-ti-qstick.html

        Calculation:
        ---------
            >>> Default Inputs:
                length=10
                xMA is one of: sma (default), dema, ema, hma, rma
                qstick = xMA(close - open, length)

        Args :
        ---------
            >>> open (pd.Series): Series of 'open's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                ma (str): The type of moving average to use. Default: None, which is 'sma'
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def short_run(self, fast=None, slow=None, length=None, offset=0, **kwargs) -> series:
        """Indicator: Short Run
        ---------

            >>> args : self
        """
        ...

    @tobtind(lines=['ts_trends', 'ts_trades', 'ts_entries', 'ts_exits'], lib='pta')
    def tsignals(self, trend=None, asbool=None, trend_reset=None, trend_offset=0,
                 offset=0, **kwargs) -> dataframe:
        """Trend Signals
        ---------

        Returns:
        ---------
            >>> dataframe with columns:
                args : self
                ts_trends,ts_trades,ts_entries,ts_exits columns.
                Trends (trend: 1, no trend: 0), Trades (Enter: 1, Exit: -1, Otherwise: 0),
                Entries (entry: 1, nothing: 0), Exits (exit: 1, nothing: 0)

        Given a Trend, Trend Signals returns the Trend, Trades, Entries and Exits as
        boolean integers. When 'asbool=True', it returns Trends, Entries and Exits as
        boolean values which is helpful when combined with the vectorbt backtesting
        package.

        A Trend can be a simple as: 'close' > 'moving average' or something more complex
        whose values are boolean or integers (0 or 1).

        Examples:
        ta.tsignals(close > ta.sma(close, 50), asbool=False)
        ta.tsignals(ta.ema(close, 8) > ta.ema(close, 21), asbool=True)

        Source: Kevin Johnson

        Calculation:
        ---------
            >>> Default Inputs:
                asbool=False, trend_reset=0, trade_offset=0, drift=1
                trades = trends.diff().shift(trade_offset).fillna(0).astype(int)
                entries = (trades > 0).astype(int)
                exits = (trades < 0).abs().astype(int)

        Args :
        ---------
            >>> trend (pd.Series): Series of 'trend's. The trend can be either a boolean or
                    integer series of '0's and '1's
                asbool (bool): If True, it converts the Trends, Entries and Exits columns to
                    booleans. When boolean, it is also useful for backtesting with
                    vectorbt's Portfolio.from_signal(close, entries, exits) Default: False
                trend_reset (value): Value used to identify if a trend has ended. Default: 0
                trade_offset (value): Value used shift the trade entries/exits Use 1 for
                    backtesting and 0 for live. Default: 0
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['ttm_trend',], lib='pta')
    def ttm_trend(self, length=6, offset=0, **kwargs) -> dataframe:
        """TTM Trend (TTM_TRND)
        ---------

        Returns:
        ---------
            >>> dataframe: ttm_trend.
                args : high, low, close

        This indicator is from John Carters book “iding the Trade” and plots the
        bars green or red. It checks if the price is above or under the average price of
        the previous 5 bars. The indicator should hep you stay in a trade until the
        colors chance. Two bars of the opposite color is the signal to get in or out.

        Sources:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/ttm-trend-price/

        Calculation:
        ---------
            >>> Default Inputs:
                length=6
                averageprice = (((high[5]+low[5])/2)+((high[4]+low[4])/2)+((high[3]+low[3])/2)+(
                    (high[2]+low[2])/2)+((high[1]+low[1])/2)+((high[6]+low[6])/2)) / 6
                if close > averageprice:
                    drawcandle(open,high,low,close) coloured(0,255,0)
                if close < averageprice:
                    drawcandle(open,high,low,close) coloured(255,0,0)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 6
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def vhf(self, length=28, drift=None, offset=0, **kwargs) -> series:
        """Vertical Horizontal Filter (VHF)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close

        VHF was created by Adam White to identify trending and ranging markets.

        Sources:
        ---------
            https://www.incrediblecharts.com/indicators/vertical_horizontal_filter.php

        Calculation:
        ---------
            >>> Default Inputs:
                length = 28
                HCP = Highest Close Price in Period
                LCP = Lowest Close Price in Period
                Change = abs(Ct - Ct-1)
                VHF = (HCP - LCP) / RollingSum[length] of Change

        Args :
        ---------
            >>> source (pd.Series): Series of prices (usually close).
                length (int): The period length. Default: 28
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['vip', 'vim'], lib='pta')
    def vortex(self, length=14, drift=1, offset=0, **kwargs) -> dataframe:
        """Vortex
        ---------

        Returns:
        ---------
            >>> dataframe: vip and vim columns
                args : high, low, close

        Two oscillators that capture positive and negative trend movement.

        Sources:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:vortex_indicator

        Calculation:
        ---------
            >>> Default Inputs:
                length=14, drift=1
                TR = True Range
                SMA = Simple Moving Average
                tr = TR(high, low, close)
                tr_sum = tr.rolling(length).sum()
                vmp = (high - low.shift(drift)).abs()
                vmn = (low - high.shift(drift)).abs()
                VIP = vmp.rolling(length).sum() / tr_sum
                VIM = vmn.rolling(length).sum() / tr_sum

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): ROC 1 period. Default: 14
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['xs_long', 'xs_short'], lib='pta')
    def xsignals(self, signal=None, xa=None, xb=None, above=None, long=None, asbool=None, trend_reset=None,
                 trend_offset=0, offset=0, **kwargs) -> dataframe:
        """Cross Signals (XSIGNALS)
        ---------

        Returns:
        ---------
            pd.DataFrame with columns:
            xs_long,xs_short columns.
            Trends (trend: 1, no trend: 0), Trades (Enter: 1, Exit: -1, Otherwise: 0),
            Entries (entry: 1, nothing: 0), Exits (exit: 1, nothing: 0)
            args : self

        Cross Signals returns Trend Signal (TSIGNALS) results for Signal Crossings. This
        is useful for indicators like RSI, ZSCORE, et al where one wants trade Entries
        and Exits (and Trends).

        Cross Signals has two kinds of modes: above and long.

        The first mode 'above', default True, xsignals determines if the signal first
        crosses above 'xa' and then below 'xb'. If 'above' is False, xsignals determines
        if the signal first crosses below 'xa' and then above 'xb'.

        The second mode 'long', default True, passes the long trend result into
        tsignals so it can determine the appropriate Entries and Exits. When 'long' is
        False, it does the same but for the short side.

        Example:
        # These are two different outcomes and depends on the indicator and it's
        # characteristics. Please check BOTH outcomes BEFORE making an Issue.
        rsi = df.ta.rsi()
        # Returns tsignal DataFrame when RSI crosses above 20 and then below 80
        ta.xsignals(rsi, 20, 80, above=True)
        # Returns tsignal DataFrame when RSI crosses below 20 and then above 80
        ta.xsignals(rsi, 20, 80, above=False)

        Source: Kevin Johnson

        Calculation:
        ---------
            >>> Default Inputs:
                asbool=False, trend_reset=0, trade_offset=0, drift=1
                trades = trends.diff().shift(trade_offset).fillna(0).astype(int)
                entries = (trades > 0).astype(int)
                exits = (trades < 0).abs().astype(int)

        Args :
        ---------
            >>> above (bool): When the signal crosses above 'xa' first and then 'xb'. When
                    False, then when the signal crosses below 'xa' first and then 'xb'.
                    Default: True
                long (bool): Passes the long trend into tsignals' trend argument. When
                    False, it passes the short trend into tsignals trend argument.
                    Default: True
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

                # TSIGNAL Passthrough arguments
                asbool (bool): If True, it converts the Trends, Entries and Exits columns to
                    booleans. When boolean, it is also useful for backtesting with
                    vectorbt's Portfolio.from_signal(close, entries, exits) Default: False
                trend_reset (value): Value used to identify if a trend has ended. Default: 0
                trade_offset (value): Value used shift the trade entries/exits Use 1 for
                    backtesting and 0 for live. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    # Utility
    @tobtind(lib='pta')
    def above(self, b=None, asint=True, offset=0, **kwargs) -> series:
        """序列a大于或等于序列b,序列a大于或等于一个数值
        ---------

        Args :
        ---------
            >>> args : a(self),b
            >>> a(self : pd.Series): 序列a,dataframelf默认close,series为其本身
                b (Union[Series,float,int]): 序列b或float
                asint (bool, optional): 是否转为整数. Defaults to True.
                offset (int, optional): 数据偏移. Defaults to None.

        Returns:
            series
        """
        ...

    @tobtind(lib='pta')
    def below(self, b=None, asint=True, offset=0, **kwargs) -> series:
        """序列a小于或等于序列b
        ---------

        Args :
        ---------
            >>> args : a(self),b
            >>> a(self : pd.Series): 序列a,dataframelf默认close,series为其本身
                b (Union[Series,float,int]): int或float
                asint (bool, optional): 是否转为整数. Defaults to True.
                offset (int, optional): 数据偏移. Defaults to None.

        Returns:
            series
        """
        ...

    @tobtind(lib='pta')
    def cross(self, b=None, above=True, asint=True, offset=0, **kwargs) -> series:
        """序列a上穿序列b,序列a上穿一个数值
        ---------

        Args :
        ---------
            >>> args : a(self),b
            >>> a(self : pd.Series): 序列a,dataframelf默认close,series为其本身
                b (pd.Series): 序列b,
                asint (bool, optional): 是否转为整数. Defaults to True.
                offset (int, optional): 数据偏移. Defaults to None.

        Returns:
            >>> series
        """
        ...

    @tobtind(lib='pta')
    def cross_up(self, b=None, asint=True, offset=0, **kwargs) -> series:
        """序列a上穿序列b,序列a上穿一个数值
        ---------

        Args :
        ---------
            >>> args : a(self),b
            >>> a(self : pd.Series): 序列a,dataframelf默认close,series为其本身
                b (pd.Series): 序列b,
                asint (bool, optional): 是否转为整数. Defaults to True.
                offset (int, optional): 数据偏移. Defaults to None.

        Returns:
            >>> series
        """
        ...

    @tobtind(lib='pta')
    def cross_down(self, b=None, asint=True, offset=0, **kwargs) -> series:
        """序列a下穿序列b,序列a下穿一个数值
        ---------

        Args :
        ---------
            >>> args : a(self),b
            >>> a(self : pd.Series): 序列a,dataframelf默认close,series为其本身
                b (pd.Series): 序列b,
                asint (bool, optional): 是否转为整数. Defaults to True.
                offset (int, optional): 数据偏移. Defaults to None.

        Returns:
            >>> series
        """
        ...

    # Volatility
    @tobtind(lines=['aber_zg', 'aber_sg', 'aber_xg', 'aber_atr'], lib='pta')
    def aberration(self, length=5, atr_length=15, offset=0, **kwargs) -> dataframe:
        """Aberration
        ---------

        Returns:
        ---------
            >>> dataframe: aber_zg, aber_sg, aber_xg, aber_atr columns.
                args : high, low, close

        A volatility indicator similar to Keltner Channels.

        Sources:
        ---------
            Few internet resources on definitive definition.
            Request by Github user homily, issue

        Calculation:
        ---------
            >>> Default Inputs:
                length=5, atr_length=15
                ATR = Average True Range
                SMA = Simple Moving Average

            >>> ATR = ATR(length=atr_length)
                JG = TP = HLC3(high, low, close)
                ZG = SMA(JG, length)
                SG = ZG + ATR
                XG = ZG - ATR

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): The short period. Default: 5
                atr_length (int): The short period. Default: 15
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['acc_lower', 'acc_mid', 'acc_upper'], lib='pta')
    def accbands(self, length=10, c=4, drift=1, mamode="sma", offset=0, **kwargs) -> dataframe:
        """Acceleration Bands (ACCBANDS)
        ---------

        Returns:
        ---------
            >>> dataframe: acc_lower, acc_mid, acc_upper columns.
                args : high, low, close

        Acceleration Bands created by Price Headley plots upper and lower envelope
        bands around a simple moving average.

        Sources:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/acceleration-bands-abands/

        Calculation:
        ---------
            >>> Default Inputs:
                length=10, c=4
                EMA = Exponential Moving Average
                SMA = Simple Moving Average
                HL_RATIO = c * (high - low) / (high + low)
                LOW = low * (1 - HL_RATIO)
                HIGH = high * (1 + HL_RATIO)
                if 'ema':
                    LOWER = EMA(LOW, length)
                    MID = EMA(close, length)
                    UPPER = EMA(HIGH, length)
                else:
                    LOWER = SMA(LOW, length)
                    MID = SMA(close, length)
                    UPPER = SMA(HIGH, length)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 10
                c (int): Multiplier. Default: 4
                mamode (str): See ```help(ta.ma)```. Default: 'sma'
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def atr(self, length=14, mamode="rma", talib=True, drift=1, offset=0, **kwargs) -> series:
        """Average True Range (ATR)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low, close

        Averge True Range is used to measure volatility, especially volatility caused by
        gaps or limit moves.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Average_True_Range_(ATR)

        Calculation:
        ---------
            >>> Default Inputs:
                length=14, drift=1, percent=False
                EMA = Exponential Moving Average
                SMA = Simple Moving Average
                WMA = Weighted Moving Average
                RMA = WildeR's Moving Average
                TR = True Range
                tr = TR(high, low, close, drift)
                if 'ema':
                    ATR = EMA(tr, length)
                elif 'sma':
                    ATR = SMA(tr, length)
                elif 'wma':
                    ATR = WMA(tr, length)
                else:
                    ATR = RMA(tr, length)
                if percent:
                    ATR *= 100 / close

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): It's period. Default: 14
                mamode (str): See ```help(ta.ma)```. Default: 'rma'
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> percent (bool, optional): Return as percentage. Default: False
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['bb_lower', 'bb_mid', 'bb_upper', 'bb_width', 'bb_percent'], overlap=True, lib='pta')
    def bbands(self, length=10, std=2., ddof=0, mamode="sma", talib=True, offset=0, **kwargs) -> dataframe:
        """Bollinger Bands (BBANDS)
        ---------

        Returns:
        ---------
            >>> dataframe: bb_lower, bb_mid, bb_upper, bb_width, and bb_percent columns.
                args : close

        A popular volatility indicator by John Bollinger.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Bollinger_Bands_(BB)

        Calculation:
        ---------
            >>> Default Inputs:
                length=5, std=2, mamode="sma", ddof=0
                EMA = Exponential Moving Average
                SMA = Simple Moving Average
                STDEV = Standard Deviation
                stdev = STDEV(close, length, ddof)
                if "ema":
                    MID = EMA(close, length)
                else:
                    MID = SMA(close, length)
                LOWER = MID - std * stdev
                UPPER = MID + std * stdev
                BANDWIDTH = 100 * (UPPER - LOWER) / MID
                PERCENT = (close - LOWER) / (UPPER - LOWER)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                length (int): The short period. Default: 5
                std (int): The long period. Default: 2
                ddof (int): Degrees of Freedom to use. Default: 0
                mamode (str): See ```help(ta.ma)```. Default: 'sma'
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['dc_lower', 'dc_mid', 'dc_upper'], lib='pta')
    def donchian(self, lower_length=20, upper_length=20, offset=0, **kwargs) -> dataframe:
        """Donchian Channels (DC)
        ---------

        Returns:
        ---------
            >>> dataframe: dc_lower, dc_mid, dc_upper columns.
                args : high, low

        Donchian Channels are used to measure volatility, similar to
        Bollinger Bands and Keltner Channels.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Donchian_Channels_(DC)

        Calculation:
        ---------
            >>> Default Inputs:
                lower_length=upper_length=20
                LOWER = low.rolling(lower_length).min()
                UPPER = high.rolling(upper_length).max()
                MID = 0.5 * (LOWER + UPPER)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                lower_length (int): The short period. Default: 20
                upper_length (int): The short period. Default: 20
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['hwc', 'hwc_upper', 'hwc_lower'], lib='pta')
    def hwc(self, na=0.2, nb=0.1, nc=0.1, nd=0.1, scalar=1., channel_eval=False, offset=0, **kwargs) -> dataframe:
        """HWC (Holt-Winter Channel)
        ---------

        Returns:
        ---------
            >>> dataframe:
            channel_eval is true : hwc,hwc_upper,hwc_lower  columns.
            channel_eval is false :  hwc,hwc_upper,hwc_lower,hwc_width, hwc_pctwidth columns.
            args : close

        Channel indicator HWC (Holt-Winters Channel) based on HWMA - a three-parameter
        moving average calculated by the method of Holt-Winters.

        This version has been implemented for Pandas TA by rengel8 based on a
        publication for MetaTrader 5 extended by width and percentage price position
        against width of channel.

        Sources:
        ---------
            https://www.mql5.com/en/code/20857

        Calculation:
        ---------
            HWMA[i] = F[i] + V[i] + 0.5 * A[i]
            where..
            F[i] = (1-na) * (F[i-1] + V[i-1] + 0.5 * A[i-1]) + na * Price[i]
            V[i] = (1-nb) * (V[i-1] + A[i-1]) + nb * (F[i] - F[i-1])
            A[i] = (1-nc) * A[i-1] + nc * (V[i] - V[i-1])

            Top = HWMA + Multiplier * StDt
            Bottom = HWMA - Multiplier * StDt
            where..
            StDt[i] = Sqrt(Var[i-1])
            Var[i] = (1-d) * Var[i-1] + nD * (Price[i-1] - \
                      HWMA[i-1]) * (Price[i-1] - HWMA[i-1])

        Args :
        ---------
            >>> na - parameter of the equation that describes a smoothed series (from 0 to 1)
                nb - parameter of the equation to assess the trend (from 0 to 1)
                nc - parameter of the equation to assess seasonality (from 0 to 1)
                nd - parameter of the channel equation (from 0 to 1)
                scaler - multiplier for the width of the channel calculated
                channel_eval - boolean to return width and percentage price position against price
                close (pd.Series): Series of 'close's

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['kc_lower', 'kc_basis', 'kc_upper'], lib='pta')
    def kc(self, length=20, scalar=2., mamode="ema", offset=0, **kwargs) -> dataframe:
        """Keltner Channels (KC)
        ---------

        Returns:
        ---------
            >>> dataframe: kc_lower, kc_basis, kc_upper columns.
                args : high, low, close

        A popular volatility indicator similar to Bollinger Bands and
        Donchian Channels.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Keltner_Channels_(KC)

        Calculation:
        ---------
            >>> Default Inputs:
                length=20, scalar=2, mamode=None, tr=True
                TR = True Range
                SMA = Simple Moving Average
                EMA = Exponential Moving Average
                if tr:
                    RANGE = TR(high, low, close)
                else:
                    RANGE = high - low
                if mamode == "ema":
                    BASIS = sma(close, length)
                    BAND = sma(RANGE, length)
                elif mamode == "sma":
                    BASIS = sma(close, length)
                    BAND = sma(RANGE, length)
                LOWER = BASIS - scalar * BAND
                UPPER = BASIS + scalar * BAND

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): The short period.  Default: 20
                scalar (float): A positive float to scale the bands. Default: 2
                mamode (str): See ```help(ta.ma)```. Default: 'ema'
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> tr (bool): When True, it uses True Range for calculation. When False, use a
                    high - low as it's range calculation. Default: True
                fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def massi(self, fast=9, slow=25, offset=0, **kwargs) -> series:
        """Mass Index (MASSI)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low

        The Mass Index is a non-directional volatility indicator that utilitizes the
        High-Low Range to identify trend reversals based on range expansions.

        Sources:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:mass_index
            mi = sum(ema(high - low, 9) / ema(ema(high - low, 9), 9), length)

        Calculation:
        ---------
            >>> Default Inputs:
                fast: 9, slow: 25
                EMA = Exponential Moving Average
                hl = high - low
                hl_ema1 = EMA(hl, fast)
                hl_ema2 = EMA(hl_ema1, fast)
                hl_ratio = hl_ema1 / hl_ema2
                MASSI = SUM(hl_ratio, slow)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                fast (int): The short period. Default: 9
                slow (int): The long period. Default: 25
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def natr(self, length=20, scalar=100., mamode="ema", talib=True, drift=1, offset=0, **kwargs) -> series:
        """Normalized Average True Range (NATR)
        ---------

        Returns:
        ---------
            >>> series: New feature
                args : high, low, close

        Normalized Average True Range attempt to normalize the average true range.

        Sources:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/normalized-average-true-range-natr/

        Calculation:
        ---------
            >>> Default Inputs:
                length=20
                ATR = Average True Range
                NATR = (100 / close) * ATR(high, low, close)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): The short period. Default: 20
                scalar (float): How much to magnify. Default: 100
                mamode (str): See ```help(ta.ma)```. Default: 'ema'
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pdist(self, drift=10, offset=0, **kwargs) -> series:
        """Price Distance (PDIST)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : open, high, low, close

        Measures the "distance" covered by price movements.

        Sources:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/pricedistance/

        Calculation:
        ---------
            >>> Default Inputs:
                drift=1
                PDIST = 2(high - low) - ABS(close - open) + \
                          ABS(open - close[drift])

        Args :
        ---------
            >>> open_ (pd.Series): Series of 'opens's
                high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def rvi(self, length=14, scalar=100., refined=False, thirds=False, mamode="ema",
            drift=1, offset=0, **kwargs) -> series:
        """Relative Volatility Index (RVI)
        ---------

        Returns:
        ---------
            >>> dataframe: lower, basis, upper columns.
                args : high, low, close

        The Relative Volatility Index (RVI) was created in 1993 and revised in 1995.
        Instead of adding up price changes like RSI based on price direction, the RVI
        adds up standard deviations based on price direction.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Keltner_Channels_(KC)

        Calculation:
        ---------
            >>> Default Inputs:
                length=14, scalar=100, refined=None, thirds=None
                EMA = Exponential Moving Average
                STDEV = Standard Deviation
                UP = STDEV(src, length) IF src.diff() > 0 ELSE 0
                DOWN = STDEV(src, length) IF src.diff() <= 0 ELSE 0
                UPSUM = EMA(UP, length)
                DOWNSUM = EMA(DOWN, length
                RVI = scalar * (UPSUM / (UPSUM + DOWNSUM))

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                length (int): The short period. Default: 14
                scalar (float): A positive float to scale the bands. Default: 100
                refined (bool): Use 'refined' calculation which is the average of
                    RVI(high) and RVI(low) instead of RVI(close). Default: False
                thirds (bool): Average of high, low and close. Default: False
                mamode (str): See ```help(ta.ma)```. Default: 'ema'
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['thermo', 'thermo_ma', 'thermo_long', 'thermo_short'], lib='pta')
    def thermo(self, length=20, long=2., short=0.5, mamode="ema", drift=1, offset=0, **kwargs) -> dataframe:
        """Elders Thermometer (THERMO)
        ---------

        Returns:
        ---------
            >>> dataframe: thermo, thermo_ma, thermo_long, thermo_short columns.
                args : high, low

        Elder's Thermometer measures price volatility.

        Sources:
        ---------
            https://www.motivewave.com/studies/elders_thermometer.htm
            https://www.tradingview.com/script/HqvTuEMW-Elder-s-Market-Thermometer-LazyBear/

        Calculation:
        ---------
            >>> Default Inputs:
                length=20, drift=1, mamode=EMA, long=2, short=0.5
                EMA = Exponential Moving Average
                thermoL = (low.shift(drift) - low).abs()
                thermoH = (high - high.shift(drift)).abs()
                thermo = np.where(thermoH > thermoL, thermoH, thermoL)
                thermo_ma = ema(thermo, length)
                thermo_long = thermo < (thermo_ma * long)
                thermo_short = thermo > (thermo_ma * short)
                thermo_long = thermo_long.astype(int)
                thermo_short = thermo_short.astype(int)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                long(int): The buy factor
                short(float): The sell factor
                length (int): The  period. Default: 20
                mamode (str): See ```help(ta.ma)```. Default: 'ema'
                drift (int): The diff period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def true_range(self, drift=1, offset=0, **kwargs) -> series:
        """True Range
        ---------

        Returns:
        ---------
            >>> series: New feature
                args : high, low, close

        An method to expand a classical range (high minus low) to include
        possible gap scenarios.

        Sources:
        ---------
            https://www.macroption.com/true-range/

        Calculation:
        ---------
            >>> Default Inputs:
                drift=1
                ABS = Absolute Value
                prev_close = close.shift(drift)
                TRUE_RANGE = ABS(
                    [high - low, high - prev_close, low - prev_close])

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                drift (int): The shift period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def ui(self, length=14, scalar=100., offset=0, **kwargs) -> series:
        """Ulcer Index (UI)
        ---------

        Returns:
        ---------
            >>> series: New feature
                args : close

        The Ulcer Index by Peter Martin measures the downside volatility with the use of
        the Quadratic Mean, which has the effect of emphasising large drawdowns.

        Sources:
        ---------
            https://library.tradingtechnologies.com/trade/chrt-ti-ulcer-index.html
            https://en.wikipedia.org/wiki/Ulcer_index
            http://www.tangotools.com/ui/ui.htm

        Calculation:
        ---------
            >>> Default Inputs:
                length=14, scalar=100
                HC = Highest Close
                SMA = Simple Moving Average
                HCN = HC(close, length)
                DOWNSIDE = scalar * (close - HCN) / HCN
                if kwargs["everget"]:
                    UI = SQRT(SMA(DOWNSIDE^2, length) / length)
                else:
                    UI = SQRT(SUM(DOWNSIDE^2, length) / length)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                close (pd.Series): Series of 'close's
                length (int): The short period.  Default: 14
                scalar (float): A positive float to scale the bands. Default: 100
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
                everget (value, optional): TradingView's Evergets SMA instead of SUM
                    calculation. Default: False
        """
        ...

    # Volume
    @tobtind(lines=None, lib='pta')
    def ad(self, open_=None, talib=True, offset=0, **kwargs) -> series:
        """Accumulation/Distribution (AD)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : open, high, low, close

        Accumulation/Distribution indicator utilizes the relative position
        of the close to it's High-Low range with volume.  Then it is cumulated.

        Sources:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/accumulationdistribution-ad/

        Calculation:
        ---------
            CUM = Cumulative Sum
            if 'open':
                AD = close - open
            else:
                AD = 2 * close - high - low

            hl_range = high - low
            AD = AD * volume / hl_range
            AD = CUM(AD)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                open (pd.Series): Series of 'open's
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def adosc(self, open_=None, fast=12, slow=26, talib=True, offset=0, **kwargs) -> series:
        """Accumulation/Distribution Oscillator or Chaikin Oscillator
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : open, high, low, close

        Accumulation/Distribution Oscillator indicator utilizes
        Accumulation/Distribution and treats it similarily to MACD
        or APO.

        Sources:
        ---------
            https://www.investopedia.com/articles/active-trading/031914/understanding-chaikin-oscillator.asp

        Calculation:
        ---------
            >>> Default Inputs:
                fast=12, slow=26
                AD = Accum/Dist
                ad = AD(high, low, close, open)
                fast_ad = EMA(ad, fast)
                slow_ad = EMA(ad, slow)
                ADOSC = fast_ad - slow_ad

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                open (pd.Series): Series of 'open's
                volume (pd.Series): Series of 'volume's
                fast (int): The short period. Default: 12
                slow (int): The long period. Default: 26
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['obv_min', 'obv_max', 'obv_maf', 'obv_mas', 'obv_long', 'obv_short'], lib='pta')
    def aobv(self, fast=4, slow=12, max_lookback=2, min_lookback=2, mamode="ema", offset=0, **kwargs) -> dataframe:
        """Indicator: Archer On Balance Volume (AOBV)
        ---------

        Returns:
        ---------
            dataframe : obv_min,obv_max,obv_maf,obv_mas,obv_long,obv_short columns.
            args : close, volume
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cmf(self, open_=None, length=20, offset=0, **kwargs) -> series:
        """Chaikin Money Flow (CMF)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : open, high, low, close, volume

        Chailin Money Flow measures the amount of money flow volume over a specific
        period in conjunction with Accumulation/Distribution.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Chaikin_Money_Flow_(CMF)
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:chaikin_money_flow_cmf

        Calculation:
        ---------
            >>> Default Inputs:
                length=20
                if 'open':
                    ad = close - open
                else:
                    ad = 2 * close - high - low
                hl_range = high - low
                ad = ad * volume / hl_range
                CMF = SUM(ad, length) / SUM(volume, length)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                open_ (pd.Series): Series of 'open's. Default: None
                length (int): The short period. Default: 20
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def efi(self, length=13, mamode="ema", drift=1, offset=0, **kwargs) -> series:
        """Elder's Force Index (EFI)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close, volume

        Elder's Force Index measures the power behind a price movement using price
        and volume as well as potential reversals and price corrections.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Elder%27s_Force_Index_(EFI)
            https://www.motivewave.com/studies/elders_force_index.htm

        Calculation:
        ---------
            >>> Default Inputs:
                length=20, drift=1, mamode=None
                EMA = Exponential Moving Average
                SMA = Simple Moving Average
                pv_diff = close.diff(drift) * volume
                if mamode == 'sma':
                    EFI = SMA(pv_diff, length)
                else:
                    EFI = EMA(pv_diff, length)

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                length (int): The short period. Default: 13
                drift (int): The diff period. Default: 1
                mamode (str): See ```help(ta.ma)```. Default: 'ema'
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def eom(self, length=14, divisor=100, drift=1, offset=0, **kwargs) -> series:
        """Ease of Movement (EOM)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low, close, volume

        Ease of Movement is a volume based oscillator that is designed to measure the
        relationship between price and volume flucuating across a zero line.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Ease_of_Movement_(EOM)
            https://www.motivewave.com/studies/ease_of_movement.htm
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ease_of_movement_emv

        Calculation:
        ---------
            >>> Default Inputs:
                length=14, divisor=100000000, drift=1
                SMA = Simple Moving Average
                hl_range = high - low
                distance = 0.5 * (high - high.shift(drift) + \
                                  low - low.shift(drift))
                box_ratio = (volume / divisor) / hl_range
                eom = distance / box_ratio
                EOM = SMA(eom, length)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                length (int): The short period. Default: 14
                drift (int): The diff period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['kvo', 'kvos'], lib='pta')
    def kvo(self, fast=34, slow=55, signal=13, mamode="ema", drift=1, offset=0, **kwargs) -> dataframe:
        """Klinger Volume Oscillator (KVO)
        ---------

        Returns:
        ---------
            >>> dataframe: kvo and kvos columns.
                args : high, low, close, volume

        This indicator was developed by Stephen J. Klinger. It is designed to predict
        price reversals in a market by comparing volume to price.

        Sources:
        ---------
            https://www.investopedia.com/terms/k/klingeroscillator.asp
            https://www.daytrading.com/klinger-volume-oscillator

        Calculation:
        ---------
            >>> Default Inputs:
                fast=34, slow=55, signal=13, drift=1
                EMA = Exponential Moving Average
                SV = volume * signed_series(HLC3, 1)
                KVO = EMA(SV, fast) - EMA(SV, slow)
                Signal = EMA(KVO, signal)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                fast (int): The fast period. Default: 34
                long (int): The long period. Default: 55
                length_sig (int): The signal period. Default: 13
                mamode (str): See ```help(ta.ma)```. Default: 'ema'
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def mfi(self, length=14, talib=True, drift=1, offset=0, **kwargs) -> series:
        """Money Flow Index (MFI)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : high, low, close, volume

        Money Flow Index is an oscillator indicator that is used to measure buying and
        selling pressure by utilizing both price and volume.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Money_Flow_(MFI)

        Calculation:
        ---------
            >>> Default Inputs:
                length=14, drift=1
                tp = typical_price = hlc3 = (high + low + close) / 3
                rmf = raw_money_flow = tp * volume
                pmf = pos_money_flow = SUM(
                    rmf, length) if tp.diff(drift) > 0 else 0
                nmf = neg_money_flow = SUM(
                    rmf, length) if tp.diff(drift) < 0 else 0
                MFR = money_flow_ratio = pmf / nmf
                MFI = money_flow_index = 100 * pmf / (pmf + nmf)

        Args :
        ---------
            >>> high (pd.Series): Series of 'high's
                low (pd.Series): Series of 'low's
                close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                length (int): The sum period. Default: 14
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                drift (int): The difference period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def nvi(self, length=13, initial=1000, offset=0, **kwargs) -> series:
        """Negative Volume Index (NVI)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close, volume

        The Negative Volume Index is a cumulative indicator that uses volume change in
        an attempt to identify where smart money is active.

        Sources:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:negative_volume_inde
            https://www.motivewave.com/studies/negative_volume_index.htm

        Calculation:
        ---------
            >>> Default Inputs:
                length=1, initial=1000
                ROC = Rate of Change
                roc = ROC(close, length)
                signed_volume = signed_series(volume, initial=1)
                nvi = signed_volume[signed_volume < 0].abs() * roc_
                nvi.fillna(0, inplace=True)
                nvi.iloc[0]= initial
                nvi = nvi.cumsum()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                length (int): The short period. Default: 13
                initial (int): The short period. Default: 1000
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def obv(self, talib=True, offset=0, **kwargs) -> series:
        """On Balance Volume (OBV)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close, volume

        On Balance Volume is a cumulative indicator to measure buying and selling
        pressure.

        Sources:
        ---------
            https://www.tradingview.com/wiki/On_Balance_Volume_(OBV)
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/on-balance-volume-obv/
            https://www.motivewave.com/studies/on_balance_volume.htm

        Calculation:
        ---------
            signed_volume = signed_series(close, initial=1) * volume
            obv = signed_volume.cumsum()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
                    version. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pvi(self, length=13, initial=1000, offset=0, **kwargs) -> series:
        """Positive Volume Index (PVI)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close, volume

        The Positive Volume Index is a cumulative indicator that uses volume change in
        an attempt to identify where smart money is active.
        Used in conjunction with NVI.

        Sources:
        ---------
            https://www.investopedia.com/terms/p/pvi.asp

        Calculation:
        ---------
            >>> Default Inputs:
                length=1, initial=1000
                ROC = Rate of Change
                roc = ROC(close, length)
                signed_volume = signed_series(volume, initial=1)
                pvi = signed_volume[signed_volume > 0].abs() * roc_
                pvi.fillna(0, inplace=True)
                pvi.iloc[0]= initial
                pvi = pvi.cumsum()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                length (int): The short period. Default: 13
                initial (int): The short period. Default: 1000
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pvol(self, offset=0, **kwargs) -> series:
        """Price-Volume (PVOL)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close, volume

        Returns a series of the product of price and volume.

        Calculation:
        ---------
            if signed:
                pvol = signed_series(close, 1) * close * volume
            else:
                pvol = close * volume

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                signed (bool): Keeps the sign of the difference in 'close's. Default: True
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pvr(self, **kwargs) -> series:
        """Price Volume Rank
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close, volume

        The Price Volume Rank was developed by Anthony J. Macek and is described in his
        article in the June, 1994 issue of Technical Analysis of Stocks & Commodities
        Magazine. It was developed as a simple indicator that could be calculated even
        without a computer. The basic interpretation is to buy when the PV Rank is below
        2.5 and sell when it is above 2.5.

        Sources:
        ---------
            https://www.fmlabs.com/reference/default.htm?url=PVrank.htm

        Calculation:
        ---------
            return 1 if 'close change' >= 0 and 'volume change' >= 0
            return 2 if 'close change' >= 0 and 'volume change' < 0
            return 3 if 'close change' < 0 and 'volume change' >= 0
            return 4 if 'close change' < 0 and 'volume change' < 0

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pvt(self, drift=1, offset=0, **kwargs) -> series:
        """Price-Volume Trend (PVT)
        ---------

        Returns:
        ---------
            >>> series: New feature generated.
                args : close, volume

        The Price-Volume Trend utilizes the Rate of Change with volume to
        and it's cumulative values to determine money flow.

        Sources:
        ---------
            https://www.tradingview.com/wiki/Price_Volume_Trend_(PVT)

        Calculation:
        ---------
            >>> Default Inputs:
                drift=1
                ROC = Rate of Change
                pv = ROC(close, drift) * volume
                PVT = pv.cumsum()

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                drift (int): The diff period. Default: 1
                offset (int): How many periods to offset the result. Default: 0

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
        """
        ...

    @tobtind(lines=['low_price', 'mean_price', 'high_price', 'pos_volume', 'neg_volume', 'total_volume'], lib='pta')
    def vp(self, width=10, **kwargs) -> dataframe:
        """Volume Profile (VP)
        ---------

        Returns:
        ---------
            >>> dataframe: low_price,mean_price,high_price,pos_volume,neg_volume ,total_volume columns.
                args : close, volume
        Calculates the Volume Profile by slicing price into ranges.
        Note: Value Area is not calculated.

        Sources:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:volume_by_price
            https://www.tradingview.com/wiki/Volume_Profile
            http://www.ranchodinero.com/volume-tpo-essentials/
            https://www.tradingtechnologies.com/blog/2013/05/15/volume-at-price/

        Calculation:
        ---------
            >>> Default Inputs:
                width=10
                vp = pd.concat([close, pos_volume, neg_volume], axis=1)
                if sort_close:
                    vp_ranges = cut(vp[close_col], width)
                    result = ({range_left, mean_close, range_right, pos_volume, neg_volume} foreach range in vp_ranges
                else:
                    vp_ranges = np.array_split(vp, width)
                    result = ({low_close, mean_close, high_close, pos_volume, neg_volume} foreach range in vp_ranges
                vpdf = pd.DataFrame(result)
                vpdf['total_volume'] = vpdf['pos_volume'] + vpdf['neg_volume']

        Args :
        ---------
            >>> close (pd.Series): Series of 'close's
                volume (pd.Series): Series of 'volume's
                width (int): How many ranges to distrubute price into. Default: 10

        Kwargs:
        ---------
            >>> fillna (value, optional): pd.DataFrame.fillna(value)
                fill_method (value, optional): Type of fill method
                sort_close (value, optional): Whether to sort by close before splitting
                    into ranges. Default: False
        """
        ...

    @tobtind(lines=None, lib="pta")
    def Any(self, *args, keep=True, **kwargs) -> series:
        """# any (|)

        Attr
        ----
            >>> args : (np.ndarray | series | pd.Series)
                keep (bool):default True.keep为真时自身数据也参与
                kwargs : (dict | IndSetting)

        Returns:
        ----
            series
        """
        # assert args, "请添加数据"
        # if len(args) == 1:
        #     data = args[0]
        # else:
        #     data = reduce(lambda x, y: x | y, args)
        # if type(data) == series:
        #     if kwargs:
        #         return series(data, **{**data.ind_setting, **kwargs})
        #     return data
        # else:
        #     if kwargs:
        #         return series(data, **{**self._indsetting.copy_values, **kwargs})
        #     return series(data, **self.ind_setting)
    @tobtind(lines=None, lib="pta")
    def All(self, *args, **kwargs) -> series:
        """# all (&)

        Attr
        ----
            >>> args : (np.ndarray | series | pd.Series)
                keep (bool):default True.keep为真时自身数据也参与
                kwargs : (dict | IndSetting)

        Returns:
        ----
            series
        """
        # assert args, "请添加数据"
        # if len(args) == 1:
        #     data = args[0]
        # else:
        #     data = reduce(lambda x, y: x & y, args)
        # if type(data) == series:
        #     if kwargs:
        #         return series(data, **{**data.ind_setting, **kwargs})
        #     return data
        # else:
        #     if kwargs:
        #         return series(data, **{**self.ind_setting, **kwargs})
        #     return series(data, **self.ind_setting)

    @tobtind(lines=None, lib="pta")
    def Where(self, cond, x=None, y=.0, **kwargs) -> series:
        """np.where
        符合条件cond的返回x,反之返回数据y
        当x=None时,条件成立时返回自身数据"""
        ...
        # data = self
        # if hasattr(self, "_df"):
        #     data = self._df
        # data = data.where(cond, y)
        # if type(data) == series:
        #     if kwargs:
        #         return series(data, **{**data.ind_setting, **kwargs})
        #     return data
        # else:
        #     if kwargs:
        #         return series(data, **{**self.ind_setting, **kwargs})
        #     return series(data, **self.ind_setting)

    @tobtind(lines=None, lib="pta")
    def line_trhend(self, period: int = 1, **kwargs) -> series:
        """指标线趋势
        ---
        与前period数据对比,比前值大为1.,持平为0.,小为-1.

        Args:
            length (int, optional): Defaults to 1.

        Returns:
            series
        """
        ...
        # return series(self.pandas_object.ta.line_trhend(period), **{**self.ind_setting, **kwargs})

    @tobtind(lines=['open', 'high', 'low', 'close'], category='candles')
    def abc(self, lim: float = 5., **kwargs) -> dataframe:
        """args open,high,low,close
        lines = ('open', 'high', 'low', 'close')"""
        ...

    @tobtind(lines=['thrend', 'line'])
    def insidebar(self, length: int = 10, **kwargs) -> dataframe:
        """args high,low,close
        lines = ('thrend','line')"""
        ...


class BtInd:
    """### 自定义指标指引
    自定义指标类，用于封装项目中自定义的基础指标计算逻辑，提供框架兼容的指标访问接口

    核心功能：
    - 基于输入的基础数据（series/dataframe）提供自定义指标的计算与访问
    - 通过 @tobtind 装饰器将原生数据转换为框架内置的指标数据类型（series/dataframe）
    - 支持基础行情数据（开盘价、最高价、最低价等）的直接访问与指标化处理

    使用说明：
    1. 初始化：传入框架支持的基础数据对象（需包含对应的原始字段）
       >>> ind = self.data.btind.alerts()"""
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    @tobtind(overlap=True, lib='btind')
    def open(self, **kwargs):
        ...

    @tobtind(overlap=True, lib='btind')
    def high(self, **kwargs):
        ...

    @tobtind(overlap=True, lib='btind')
    def low(self, **kwargs):
        ...

    @tobtind(overlap=True, lib='btind')
    def close(self, **kwargs):
        ...

    @tobtind(overlap=True, lib='btind')
    def smoothrng(self, length: int = 14, mult: float = 1., **kwargs):
        """平滑平均范围"""
        ...

    @tobtind(overlap=True, lib='btind')
    def rngfilt(self, r: pd.Series = None, **kwargs):
        """过滤范围"""
        ...

    @tobtind(lines=['filt', 'hband', 'lband', 'dir'], lib='btind')
    def alerts(self, length: int = 14, mult: float = 2., **kwargs) -> dataframe:
        """alerts

            Args:
                data (dataframe): 数据
                length (int, optional): 长度. Defaults to None.
                mult (float, optional): 乘数. Defaults to None.

            Returns:
                Union[dataframe]: cols=['filt', 'hband', 'lband','dir']
        """
        ...

    @tobtind(lib='btind')
    def noises_density(self, length: int = 10, **kwargs) -> series:
        """价格密度函数
        args : high,low"""
        ...

    @tobtind(lib='btind')
    def noises_er(self, length: int = 10, **kwargs) -> series:
        """ER效率系数
        args : close"""
        ...

    @tobtind(lib='btind')
    def noises_fd(self, length: int = 10, **kwargs) -> series:
        """fractal dimension 分型维度
        args : high,low,close"""
        ...

    @tobtind(lines=None, lib='btind',)
    def kama(self, length=None, fast=None, slow=None, drift=None, offset=0, **kwargs) -> series | dataframe:
        ...

    @tobtind(lines=['mama', 'fama'], lib='btind',)
    def mama(self, fastlimit: float = 0.6185, slowlimit: float = 0.06185, **kwargs) -> dataframe:
        """mama

        Args:
            close (series): 数据
            fastlimit (float, optional): 快线参数. Defaults to 0.6185.
            slowlimit (float, optional): 慢线参数. Defaults to 0.06185.

        Returns:
            dataframe: cols=['mama', 'fama']
        """
        ...

    @tobtind(lines=['long', 'short', 'thrend'], overlap=True, lib='btind',)
    def pmax(self, length: int = 14, mult: float = 1.6185, mode: Literal[
        "dema", "ema", "fwma", "hma", "linreg", "midpoint", "pwma", "rma",
        "sinwma", "sma", "swma", "t3", "tema", "trima", "vidya", "wma", "zlma"
    ] = 'hma', dev: Literal["stdev", "art", "variance", "smoothrng"] = "stdev", **kwargs) -> dataframe:
        """pmax

            Args:
                close (series): 数据
                length (int, optional): 长度. Defaults to None.
                mult (float, optional): 乘数. Defaults to None.
                ind (str, optional): 指标名称. Defaults to None.

            Returns:
                dataframe: cols=['long','short','thrend']
        """
        ...

    @tobtind(lib='btind')
    def pv(self, length=10, **kwargs) -> series:
        ...

    @tobtind(lib='btind')
    def realized(self, length: int = 10, **kwargs):
        """args : close"""
        ...

    @tobtind(lines=['rshl', 'rslh'], lib='btind')
    def rsrs(self, length: int = 10, method: Literal['r1', 'r2', 'r3'] = 'r1', weights=True, **kwargs) -> dataframe:
        """args high,low,volume
        lines = (rshl,rslh)"""
        ...

    @tobtind(overlap=True, lib='btind')
    def savitzky_golay(self, window_length: Any = 10, polyorder: Any = 2, deriv: int = 0, delta: float = 1, axis: int = -1, mode: str = 'interp', cval: float = 0, **kwargs):
        """ Apply a Savitzky-Golay filter to an array.

        This is a 1-D filter. If `x`  has dimension greater than 1, `axis`
        determines the axis along which the filter is applied.

        Parameters
        ----------
        x : array_like
            The data to be filtered. If `x` is not a single or double precision
            floating point array, it will be converted to type ``numpy.float64``
            before filtering.
        window_length : int
            The length of the filter window (i.e., the number of coefficients).
            If `mode` is 'interp', `window_length` must be less than or equal
            to the size of `x`.
        polyorder : int
            The order of the polynomial used to fit the samples.
            `polyorder` must be less than `window_length`.
        deriv : int, optional
            The order of the derivative to compute. This must be a
            nonnegative integer. The default is 0, which means to filter
            the data without differentiating.
        delta : float, optional
            The spacing of the samples to which the filter will be applied.
            This is only used if deriv > 0. Default is 1.0.
        axis : int, optional
            The axis of the array `x` along which the filter is to be applied.
            Default is -1.
        mode : str, optional
            Must be 'mirror', 'constant', 'nearest', 'wrap' or 'interp'. This
            determines the type of extension to use for the padded signal to
            which the filter is applied.  When `mode` is 'constant', the padding
            value is given by `cval`.  See the Notes for more details on 'mirror',
            'constant', 'wrap', and 'nearest'.
            When the 'interp' mode is selected (the default), no extension
            is used.  Instead, a degree `polyorder` polynomial is fit to the
            last `window_length` values of the edges, and this polynomial is
            used to evaluate the last `window_length // 2` output values.
        cval : scalar, optional
            Value to fill past the edges of the input if `mode` is 'constant'.
            Default is 0.0.

        Returns
        -------
        y : ndarray, same shape as `x`
            The filtered data.

        See Also
        --------
        savgol_coeffs

        Notes
        -----
        Details on the `mode` options:

            'mirror':
                Repeats the values at the edges in reverse order. The value
                closest to the edge is not included.
            'nearest':
                The extension contains the nearest input value.
            'constant':
                The extension contains the value given by the `cval` argument.
            'wrap':
                The extension contains the values from the other end of the array.

        For example, if the input is [1, 2, 3, 4, 5, 6, 7, 8], and
        `window_length` is 7, the following shows the extended data for
        the various `mode` options (assuming `cval` is 0)::

            mode       |   Ext   |         Input          |   Ext
            -----------+---------+------------------------+---------
            'mirror'   | 4  3  2 | 1  2  3  4  5  6  7  8 | 7  6  5
            'nearest'  | 1  1  1 | 1  2  3  4  5  6  7  8 | 8  8  8
            'constant' | 0  0  0 | 1  2  3  4  5  6  7  8 | 0  0  0
            'wrap'     | 6  7  8 | 1  2  3  4  5  6  7  8 | 1  2  3

        .. versionadded:: 0.14.0

        Examples
        --------
        >>> from scipy.signal import savgol_filter
        >>> np.set_printoptions(precision=2)  # For compact display.
        >>> x = np.array([2, 2, 5, 2, 1, 0, 1, 4, 9])

        Filter with a window length of 5 and a degree 2 polynomial.  Use
        the defaults for all other parameters.

        >>> savgol_filter(x, 5, 2)
        array([1.66, 3.17, 3.54, 2.86, 0.66, 0.17, 1.  , 4.  , 9.  ])

        Note that the last five values in x are samples of a parabola, so
        when mode='interp' (the default) is used with polyorder=2, the last
        three values are unchanged. Compare that to, for example,
        `mode='nearest'`:

        >>> savgol_filter(x, 5, 2, mode='nearest')
        array([1.74, 3.03, 3.54, 2.86, 0.66, 0.17, 1.  , 4.6 , 7.97])

        """
    ...

    @tobtind(lines=['thrend', 'dir', 'long', 'short'], overlap=True, lib='btind')
    def SuperTrend(self, length=14, multiplier=2., weights=2., **Kwargs) -> series:
        """args:high, low, close
        Returns:
        ---------
            >>> dataframe: trend, dir, long, short columns."""
        ...

    @tobtind(category="overlap", lib='btind')
    def zigzag(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> series:
        """
        Find the peaks and valleys of a series.
        zigzag:含nan数据
        zigzag_full:无nan数据
        # args:
        >>> param X: the series to analyze
            param up_thresh: minimum relative change necessary to define a peak
            param down_thesh: minimum relative change necessary to define a valley
            return: an array with 0 indicating no pivot and -1 and 1 indicating
            valley and peak


        The First and Last Elements
        ---------------------------
        The first and last elements are guaranteed to be annotated as peak or
        valley even if the segments formed do not have the necessary relative
        changes. This is a tradeoff between technical correctness and the
        propensity to make mistakes in data analysis. The possible mistake is
        ignoring data outside the fully realized segments, which may bias
        analysis.
        """
        ...

    @tobtind(category="overlap", lib='btind')
    def zigzag_full(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> series:
        """
        Find the peaks and valleys of a series.
        zigzag:含nan数据
        zigzag_full:无nan数据
        # args:
        >>> param X: the series to analyze
            param up_thresh: minimum relative change necessary to define a peak
            param down_thesh: minimum relative change necessary to define a valley
            return: an array with 0 indicating no pivot and -1 and 1 indicating
            valley and peak


        The First and Last Elements
        ---------------------------
        The first and last elements are guaranteed to be annotated as peak or
        valley even if the segments formed do not have the necessary relative
        changes. This is a tradeoff between technical correctness and the
        propensity to make mistakes in data analysis. The possible mistake is
        ignoring data outside the fully realized segments, which may bias
        analysis.
        """
        ...

    @tobtind(lib='btind')
    def zigzag_modes(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> series:
        """
        Translate pivots into trend modes.

        :param pivots: the result of calling ``peak_valley_pivots``
        :return: numpy array of trend modes. That is, between (VALLEY, PEAK] it
        is 1 and between (PEAK, VALLEY] it is -1.
        """
        ...

    @tobtind(lib='btind')
    def zigzag_returns(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., limit: bool = True, **kwargs) -> series:
        """
        :return: numpy array of the pivot-to-pivot returns for each segment."""
        ...

    @tobtind(lines=["up", "dn", "bull", "bear", "signal"], lib="btind")
    def AndeanOsc(self, length: int = 14, signal_length: int = 9, **kwargs) -> dataframe:
        """# Andean Oscillator
        A New Technical Indicator Based on An Online Algorithm For Trend Analysis

        args:open,close.

        return: datafram for up,dn,bull,bear,signal columns.

        https://alpaca.markets/learn/andean-oscillator-a-new-technical-indicator-based-on-an-online-algorithm-for-trend-analysis

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
        bull,bear,signal = AndeanOsc(close,open,14,9)"""
        ...

    @tobtind(lib="btind")
    def Coral_Trend_Candles(self, smooth: int = 9., mult: float = .4, **kwargs) -> series:
        """# Coral_Trend_Candles
        args:close

        >>> return:series
        """
        ...


class TuLip:
    """## Tulip Indicators
    https://tulipindicators.org/"""
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    @tobtind(lib="ti")
    def abs(self, **kwargs) -> series:
        """### Vector Absolute Value
        https://tulipindicators.org/abs
        >>> args:close
            return series
        """
        ...

    @tobtind(lib="ti")
    def acos(self, **kwargs) -> series:
        """### Vector Arccosine
        https://tulipindicators.org/acos
        >>> args:close
            return series
        """
        ...

    @tobtind(lib="ti")
    def ad(self, **kwargs) -> series:
        """### Accumulation/Distribution Line
        https://tulipindicators.org/ad
        >>> args:high, low, close, volume (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def add(self, series=None, **kwargs) -> series:
        """### Vector Addition
        https://tulipindicators.org/add
        >>> args:close (series)
                 series (int | float | seires | np.ndarray)
            return series
        """
        ...

    @tobtind(lib="ti")
    def adosc(self, short_period=10, long_period=10, **kwargs) -> series:
        """### Accumulation/Distribution Oscillator
        https://tulipindicators.org/adosc
        >>> args:high, low, close, volume (series)
                 short_period (int):default 10
                 long_period  (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def adx(self, period=10, **kwargs) -> series:
        """
        ### Average Directional Movement Index
        https://tulipindicators.org/adx
        >>> args:high, low, close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def adxr(self, period=10, **kwargs) -> series:
        """### Average Directional Movement Rating
        https://tulipindicators.org/adxr
        >>> args:high, low, close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def ao(self, **kwargs) -> series:
        """### Awesome Oscillator
        https://tulipindicators.org/ao
        >>> args:high, low (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def apo(self, short_period=10, long_period=10, **kwargs) -> series:
        """### Absolute Price Oscillator
        https://tulipindicators.org/apo
        >>> args:close (series)
                 short_period (int):default 10
                 long_period  (int):default 10
            return series
        """
        ...

    @tobtind(lines=["aroondown", "aroonup"], lib="ti")
    def aroon(self, period=10, **kwargs) -> dataframe:
        """### Aroon
        https://tulipindicators.org/aroon
        >>> args:high, low (series)
                 period (int):default 10
            lines:aroondown, aroonup
            return datafram
        """
        ...

    @tobtind(lib="ti")
    def aroonosc(self, period=10, **kwargs) -> series:
        """### Aroon Oscillator
        https://tulipindicators.org/aroonosc
        >>> args:high, low (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def asin(self, **kwargs) -> series:
        """### Vector Arcsine
        https://tulipindicators.org/asin
        >>> args:close
            return series
        """
        ...

    @tobtind(lib="ti")
    def atan(self, **kwargs) -> series:
        """### Vector Arctangent
        https://tulipindicators.org/atan
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def atr(self, period=10, **kwargs) -> series:
        """### Average True Range
        https://tulipindicators.org/atr
        >>> args:high, low, close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def avgprice(self, **kwargs) -> series:
        """### Average Price
        https://tulipindicators.org/avgprice
        >>> args:open, high, low, close (series)
            return series
        """
        ...

    @tobtind(lines=["upperband", "middleband", "lowerband"], lib="ti")
    def bbands(self, period=10, stddev=1., **kwargs) -> series:
        """### Bollinger Bands
        https://tulipindicators.org/bbands
        >>> args:close (series)
                 period (int):default 10
                 stddev (float):default 1.
            lines:upperband, middleband, lowerband
            return dataframe
        """
        ...

    @tobtind(lib="ti")
    def bop(self, **kwargs) -> series:
        """### Balance of Power
        https://tulipindicators.org/bop
        >>> args:open, high, low, close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def cci(self, period=10, **kwargs) -> series:
        """### Commodity Channel Index
        https://tulipindicators.org/cci
        >>> args:high, low, close
            return series
        """
        ...

    @tobtind(lib="ti")
    def ceil(self, **kwargs) -> series:
        """### Vector Ceiling
        https://tulipindicators.org/ceil
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def cmo(self, period=10, **kwargs) -> series:
        """### Chande Momentum Oscillator
        https://tulipindicators.org/cmo
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def cos(self, **kwargs) -> series:
        """### Vector Cosine
        https://tulipindicators.org/cos
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def cosh(self, **kwargs) -> series:
        """### Vector Hyperbolic Cosine
        https://tulipindicators.org/cosh
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def crossany(self, series=None, **kwargs) -> series:
        """### Crossany
        https://tulipindicators.org/crossany
        >>> args:close (series)
                 series (series | np.ndarray | int | float)
            return series
        """
        ...

    @tobtind(lib="ti")
    def crossover(self, series=None, **kwargs) -> series:
        """### Crossover
        https://tulipindicators.org/crossover
        >>> args:close (series)
                 series (series | np.ndarray | int | float)
            return series
        """
        ...

    @tobtind(lib="ti")
    def cvi(self, period=10, **kwargs) -> series:
        """### Chaikins Volatility
        https://tulipindicators.org/cvi
        >>> args:high, low (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def decay(self, period=10, **kwargs) -> series:
        """### Linear Decay
        https://tulipindicators.org/decay
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def dema(self, period=10, **kwargs) -> series:
        """### Double Exponential Moving Average
        https://tulipindicators.org/dema
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lines=["plus_di", "minus_di"], lib="ti")
    def di(self, period=10, **kwargs) -> dataframe:
        """### Directional Indicator
        https://tulipindicators.org/di
        >>> args:high, low, close (series)
                 period (int):default 10
            lines:plus_di,minus_di
            return dataframe
        """
        ...

    @tobtind(lib="ti")
    def div(self, series=None, **kwargs) -> series:
        """### Vector Division
        https://tulipindicators.org/div
        >>> args:close (series)
                 series (series | np.ndarray | int | float)
            return series
        """
        ...

    @tobtind(lines=['dmp', 'dmn'], lib="ti")
    def dm(self, period=10, **kwargs) -> dataframe:
        """### Directional Movement
        https://tulipindicators.org/dm
        >>> args:high, low (series)
                 period (int):default 10
            lines:dmp, dmn
            return:dataframe
        """
        ...

    @tobtind(lib="ti")
    def dpo(self, period=10, **kwargs) -> series:
        """### Detrended Price Oscillator
        https://tulipindicators.org/dpo
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def dx(self, period=10, **kwargs) -> series:
        """### Directional Movement Index
        https://tulipindicators.org/dx
        >>> args:high, low, close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def edecay(self, period=10, **kwargs) -> series:
        """### Exponential Decay
        https://tulipindicators.org/edecay
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def ema(self, period=10, **kwargs) -> series:
        """### Exponential Moving Average
        https://tulipindicators.org/ema
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def emv(self, **kwargs) -> series:
        """### Ease of Movement
        https://tulipindicators.org/emv
        >>> args:high, low, volume (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def exp(self, **kwargs) -> series:
        """### Vector Exponential
        https://tulipindicators.org/exp
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lines=['fisher', 'fishers'], lib="ti")
    def fisher(self, period=10, **kwargs) -> dataframe:
        """### Fisher Transform
        https://tulipindicators.org/fisher
        >>> args:high, low (series)
                 period (int):default 10
            lines:fisher, fishers
            return:dataframe
        """
        ...

    @tobtind(lib="ti")
    def floor(self, **kwargs) -> series:
        """### Vector Floor
        https://tulipindicators.org/floor
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def fosc(self, period=10, **kwargs) -> series:
        """### Forecast Oscillator
        https://tulipindicators.org/fosc
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def hma(self, period=10, **kwargs) -> series:
        """### Hull Moving Average
        https://tulipindicators.org/hma
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def kama(self, period=10, **kwargs) -> series:
        """### Kaufman Adaptive Moving Average
        https://tulipindicators.org/kama
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def kvo(self, short_period=10, long_period=10, **kwargs) -> series:
        """### Klinger Volume Oscillator
        https://tulipindicators.org/kvo
        >>> args:high, low, close, volume (series)
                 short_period (int):default 10
                 long_period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def lag(self, period=10, **kwargs) -> series:
        """### Lag
        https://tulipindicators.org/lag
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def linreg(self, period=10, **kwargs) -> series:
        """### Linear Regression
        https://tulipindicators.org/linreg
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def linregintercept(self, period=10, **kwargs) -> series:
        """### Linear Regression Intercept
        https://tulipindicators.org/linregintercept
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def linregslope(self, period=10, **kwargs) -> series:
        """### Linear Regression Slope
        https://tulipindicators.org/linregslope
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def ln(self, **kwargs) -> series:
        """### Vector Natural Log
        https://tulipindicators.org/ln
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def log10(self, **kwargs) -> series:
        """### Vector Base-10 Log
        https://tulipindicators.org/log10
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lines=["macdx", "macdh", "macds"], lib="ti")
    def macd(self, short_period=12, long_period=26, signal_period=9, **kwargs) -> dataframe:
        """### Moving Average Convergence/Divergence
        https://tulipindicators.org/macd
        >>> args:close (series)
                 short_period (int):default 12
                 long_period (int):default 26
                 signal_period (int):default 9
            lines:macdx, macdh, macds
            return:dataframe
        """
        ...

    @tobtind(lib="ti")
    def marketfi(self, **kwargs) -> series:
        """### Market Facilitation Index
        https://tulipindicators.org/marketfi
        >>> args:high, low, volume (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def mass(self, period=10, **kwargs) -> series:
        """### Mass Index
        https://tulipindicators.org/mass
        >>> args:high, low (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def max(self, period=10, **kwargs) -> series:
        """### Maximum In Period
        https://tulipindicators.org/max
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def md(self, period=10, **kwargs) -> series:
        """### Mean Deviation Over Period
        https://tulipindicators.org/md
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def medprice(self, **kwargs) -> series:
        """### Median Price
        https://tulipindicators.org/medprice
        >>> args:high, low (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def mfi(self, period=10, **kwargs) -> series:
        """### Money Flow Index
        https://tulipindicators.org/mfi
        >>> args:high, low, close, volume (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def min(self, period=10, **kwargs) -> series:
        """### Minimum In Period
        https://tulipindicators.org/min
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def mom(self, period=10, **kwargs) -> series:
        """### Momentum
        https://tulipindicators.org/min
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lines=["msw_sine", "msw_lead"], lib="ti")
    def msw(self, period=10, **kwargs) -> dataframe:
        """### Mesa Sine Wave
        https://tulipindicators.org/msw
        args:close (series)
        return:msw_sine,msw_lead
                 period (int):default 10
            return dataframe
        """
        ...

    @tobtind(lib="ti")
    def mul(self, series=None, **kwargs) -> series:
        """### Vector Multiplication
        https://tulipindicators.org/mul
        >>> args:close (series)
                 series (series | np.ndarray | int | float)
            return series
        """
        ...

    @tobtind(lib="ti")
    def natr(self, period=10, **kwargs) -> series:
        """### Normalized Average True Range
        https://tulipindicators.org/natr
        >>> args:high, low, close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def nvi(self, **kwargs) -> series:
        """### Negative Volume Index
        https://tulipindicators.org/nvi
        >>> args:close, volume (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def obv(self, **kwargs) -> series:
        """### On Balance Volume
        https://tulipindicators.org/obv
        >>> args:close, volume (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def ppo(self, short_period=10, long_period=10, **kwargs) -> series:
        """### Percentage Price Oscillator
        https://tulipindicators.org/ppo
        >>> args:close (series)
                 short_period (int):default 10
                 long_period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def psar(self, acceleration_factor_step=0.06185, acceleration_factor_maximum=0.6185, **kwargs):
        """### Parabolic SAR
        https://tulipindicators.org/psar
        >>> args:high, low (series)
                 acceleration_factor_step (int):default 0.06185
                 acceleration_factor_maximum (int):default 0.6185
            return series
        """
        ...

    @tobtind(lib="ti")
    def qstick(self, period=10, **kwargs) -> series:
        """### Qstick
        https://tulipindicators.org/qstick
        >>> args:open, close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def roc(self, period=10, **kwargs) -> series:
        """### Rate of Change
        https://tulipindicators.org/roc
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def rocr(self, period=10, **kwargs) -> series:
        """### Rate of Change Ratio
        https://tulipindicators.org/rocr
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def round(self, **kwargs) -> series:
        """### Vector Round
        https://tulipindicators.org/round
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def rsi(self, period=10, **kwargs) -> series:
        """### Relative Strength Index
        https://tulipindicators.org/rsi
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def sin(self, **kwargs) -> series:
        """### Vector Sine
        https://tulipindicators.org/sin
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def sinh(self, **kwargs) -> series:
        """### Vector Hyperbolic Sine
        https://tulipindicators.org/sinh
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def sma(self, period=10, **kwargs) -> series:
        """### Simple Moving Average
        https://tulipindicators.org/sma
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def sqrt(self, **kwargs) -> series:
        """### Vector Square Root
        https://tulipindicators.org/sqrt
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def stddev(self, period=10, **kwargs) -> series:
        """### Standard Deviation Over Period
        https://tulipindicators.org/stddev
        >>> args:close (series)
                 period (int):default 10
            return series"""
        ...

    @tobtind(lib="ti")
    def stderr(self, period=10, **kwargs) -> series:
        """###Standard Error Over Period
        https://tulipindicators.org/stderr
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lines=["stoch_k", "stoch_d"], lib="ti")
    def stoch(self, pct_k_period=5, pct_k_slowing_period=3, pct_d_period=3, **kwargs) -> dataframe:
        """### Stochastic Oscillator
        https://tulipindicators.org/stoch
        >>> args:high, low, close (series)
                 pct_k_period (int):default 5
                 pct_k_slowing_period (int):default 3
                 pct_d_period (int):default 3
            lines:stoch_k,stoch_d
            return:dataframe
        """
        ...

    @tobtind(lib="ti")
    def stochrsi(self, period=10, **kwargs) -> series:
        """### Stochastic RSI
        https://tulipindicators.org/stochrsi
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def sub(self, series=None, **kwargs) -> series:
        """### Vector Subtraction
        https://tulipindicators.org/sub
        >>> args:close (series)
                 series (series | np.ndarray | int | float)
            return series
        """
        ...

    @tobtind(lib="ti")
    def sum(self, period=10, **kwargs) -> series:
        """### Sum Over Period
        https://tulipindicators.org/sum
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def tan(self, **kwargs) -> series:
        """### Vector Tangent
        https://tulipindicators.org/tan
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def tanh(self, **kwargs) -> series:
        """### Vector Hyperbolic Tangent
        https://tulipindicators.org/tanh
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def tema(self, period=10, **kwargs) -> series:
        """### Triple Exponential Moving Average
        https://tulipindicators.org/tema
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def todeg(self, **kwargs) -> series:
        """### Vector Degree Conversion
        https://tulipindicators.org/todeg
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def torad(self, **kwargs) -> series:
        """### Vector Radian Conversion
        https://tulipindicators.org/torad
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def tr(self, **kwargs) -> series:
        """### True Range
        https://tulipindicators.org/tr
        >>> args:high, low, close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def trima(self, period=10, **kwargs) -> series:
        """### Triangular Moving Average
        https://tulipindicators.org/trima
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def trix(self, period=10, **kwargs) -> series:
        """### Trix
        https://tulipindicators.org/trix
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def trunc(self, **kwargs) -> series:
        """### Vector Truncate
        https://tulipindicators.org/trunc
        >>> args:close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def tsf(self, period=10, **kwargs) -> series:
        """### Time Series Forecast
        https://tulipindicators.org/tsf
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def typprice(self, **kwargs) -> series:
        """### Typical Price
        https://tulipindicators.org/typprice
        >>> args:high, low, close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def ultosc(self, short_period=2, medium_period=3, long_period=5, **kwargs) -> series:
        """### Ultimate Oscillator
        https://tulipindicators.org/ultosc
        >>> args:high, low, close (series)
                 short_period (int):default 2
                 medium_period (int):default 3
                 long_period (int):default 5
            return series
        """
        ...

    @tobtind(lib="ti")
    def var(self, period=10, **kwargs) -> series:
        """### Variance Over Period
        https://tulipindicators.org/var
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def vhf(self, period=10, **kwargs) -> series:
        """### Vertical Horizontal Filter
        https://tulipindicators.org/vhf
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def vidya(self, short_period=2, long_period=5, alpha=0.2) -> series:
        """### Variable Index Dynamic Average
        https://tulipindicators.org/vidya
        >>> args:close (series)
                 short_period (int):default 2
                 long_period (int):default 5
                 alpha (float):default 0.2
            return series
        """
        ...

    @tobtind(lib="ti")
    def volatility(self, period=10, **kwargs) -> series:
        """### Annualized Historical Volatility
        https://tulipindicators.org/volatility
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def vosc(self, short_period=2, long_period=5, **kwargs) -> series:
        """### Volume Oscillator
        https://tulipindicators.org/vosc
        >>> args:volume (series)
                 short_period (int):default 2
                 long_period (int):default 5
            return series"""
        ...

    @tobtind(lib="ti")
    def vwma(self, period=10, **kwargs) -> series:
        """### Volume Weighted Moving Average
        https://tulipindicators.org/vwma
        >>> args:close, volume (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def wad(self, **kwargs) -> series:
        """### Williams Accumulation/Distribution
        https://tulipindicators.org/wad
        >>> args:high, low, close (series)
            return series"""
        ...

    @tobtind(lib="ti")
    def wcprice(self, **kwargs) -> series:
        """### Weighted Close Price
        https://tulipindicators.org/wcprice
        >>> args:high, low, close (series)
            return series
        """
        ...

    @tobtind(lib="ti")
    def wilders(self, period=10, **kwargs) -> series:
        """### Wilders Smoothing
        https://tulipindicators.org/wilders
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def willr(self, period=10, **kwargs) -> series:
        """### Williams %R
        https://tulipindicators.org/willr
        >>> args:high, low, close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def wma(self, period=10, **kwargs) -> series:
        """### Weighted Moving Average
        https://tulipindicators.org/wma
        >>> args:close (series)
                 period (int):default 10
            return series
        """
        ...

    @tobtind(lib="ti")
    def zlema(self, period=10, **kwargs) -> series:
        """### Zero-Lag Exponential Moving Average
        https://tulipindicators.org/zlema
        >>> args:close (series)
                 period (int):default 10
            return series"""
        ...


class TqFunc:
    """天勤指标指引"""
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    @tobtind(lib='tq')
    def ref(self, length=10, **kwargs) -> series:
        """
        简单移动: 求series序列位移n个周期的结果

            注意: 当n为0, 函数返回原序列; 当n为有效值但当前的series序列元素个数不足 n + 1 个, 函数返回 NaN 序列

        Args:
            series (pandas.Series): 数据序列

            n (int): 位移周期

        Returns:
            pandas.Series: 位移后的序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            pre_close = tafunc.ref(klines.close, 1)  # 将收盘价序列右移一位, 得到昨收盘序列
            change = klines.close - pre_close        # 收盘价序列 - 昨收盘序列, 得到涨跌序列
            print(list(change))
        """
        ...

    @tobtind(lib='tq')
    def std(self, length: int = 10, **kwargs) -> series:
        """
        标准差: 求series序列每n个周期的标准差

            注意: n为0的情况下, 或当n为有效值但当前的series序列元素个数不足n个, 函数返回 NaN 序列

        Args:
            series (pandas.Series): 数据序列

            n (int): 标准差的周期

        Returns:
            pandas.Series: 标准差序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            std = tafunc.std(klines.close, 5)  # 收盘价序列每5项计算一个标准差
            print(list(std))
        """
        ...

    @tobtind(lib='tq')
    def ma(self, length: int = 10, **kwargs) -> series:
        """
        简单移动平均线: 求series序列n周期的简单移动平均

            计算公式:
            ma(x, 5) = (x(1) + x(2) + x(3) + x(4) + x(5)) / 5

            注意:
            1. 简单移动平均线将设定周期内的值取平均值, 其中各元素的权重都相等
            2. n为0的情况下, 或当n为有效值但当前的series序列元素个数不足n个, 函数返回 NaN 序列

        Args:
            series (pandas.Series): 数据序列

            n (int): 周期

        Returns:
            pandas.Series: 简单移动平均值序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            ma = tafunc.ma(klines.close, 5)
            print(list(ma))
        """
        ...

    @tobtind(lib='tq')
    def sma(self, n: int = 10, m: int = 2, **kwargs) -> series:
        """
        扩展指数加权移动平均: 求series序列n周期的扩展指数加权移动平均

            计算公式:
            sma(x, n, m) = sma(x, n, m).shift(1) * (n - m) / n + x(n) * m / n

            注意: n必须大于m

        Args:
            series (pandas.Series): 数据序列

            n (int): 周期

            m (int): 权重

        Returns:
            pandas.Series: 扩展指数加权移动平均序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            sma = tafunc.sma(klines.close, 5, 2)  # 收盘价序列每5项计算一个扩展指数加权移动平均值
            print(list(sma))
        """
        ...

    @tobtind(lib='tq')
    def ema(self, length: int = 10, **kwargs) -> series:
        """
        指数加权移动平均线: 求series序列n周期的指数加权移动平均

            计算公式:
                ema(x, n) = 2 * x / (n + 1) + (n - 1) * ema(x, n).shift(1) / (n + 1)

            注意:
                1. n 需大于等于1
                2. 对距离当前较近的k线赋予了较大的权重

        Args:
            series (pandas.Series): 数据序列

            n (int): 周期

        Returns:
            pandas.Series: 指数加权移动平均线序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            ema = tafunc.ema(klines.close, 5)
            print(list(ema))
        """
        ...

    @tobtind(lib='tq')
    def ema2(self, length: int = 10, **kwargs) -> series:
        """
        线性加权移动平均: 求series值的n周期线性加权移动平均 (也称WMA)

            计算公式:
                ema2(x, n) = [n * x(0) + (n - 1) * x(1) + (x - 2) * x(2) + ... + 1 * x(n - 1)] / [n + (n - 1) + (n - 2) + ... + 1]

            注意: 当n为有效值但当前的series序列元素个数不足n个, 函数返回 NaN 序列

        Args:
            series (pandas.Series): 数据序列

            n (int): 周期

        Returns:
            pandas.Series: 线性加权移动平均线序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            ema2 = tafunc.ema2(klines.close, 5)  # 求收盘价在5个周期的线性加权移动平均值
            print(list(ema2))
        """
        ...

    @tobtind(lib='tq')
    def crossup(self, b=None, **kwargs) -> series:
        """
        向上穿越: 表当a从下方向上穿过b, 成立返回1, 否则返回0

        Args:
            a (pandas.Series): 数据序列1

            b (pandas.Series): 数据序列2

        Returns:
            pandas.Series: 上穿标志序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            crossup = tafunc.crossup(
                tafunc.ma(klines.close, 5), tafunc.ma(klines.close, 10))
            print(list(crossup))
        """
        ...

    @tobtind(lib='tq')
    def crossdown(self, b=None, **kwargs) -> series:
        """
        向下穿越: 表示当a从上方向下穿b,成立返回1, 否则返回0

        Args:
            a (pandas.Series): 数据序列1

            b (pandas.Series): 数据序列2

        Returns:
            pandas.Series: 下穿标志序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            crossdown = tafunc.crossdown(
                tafunc.ma(klines.close, 5), tafunc.ma(klines.close, 10))
            print(list(crossdown))
        """
        ...

    @tobtind(lib='tq')
    def count(self, cond=None, length: int = 10, **kwargs) -> series:
        """
        统计n周期中满足cond条件的个数

            注意: 如果n为0, 则从第一个有效值开始统计

        Args:
            cond (array_like): 条件

            n (int): 周期

        Returns:
            pandas.Series: 统计值序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            # 统计从申请到的行情数据以来到当前这段时间内, 5周期均线上穿10周期均线的次数:
            count = tafunc.count(tafunc.crossup(
                tafunc.ma(klines.close, 5), tafunc.ma(klines.close, 10)), 0)
            print(list(count))
        """
        ...

    @tobtind(lib='tq')
    def trma(self, length: int = 10, **kwargs) -> series:
        """
        三角移动平均: 求series的n周期三角移动平均值

            计算方法:
                三角移动平均线公式, 是采用算数移动平均, 并且对第一个移动平均线再一次应用算数移动平均

            注意: n为0的情况下, 或当n为有效值但当前的series序列元素个数不足n个, 函数返回 NaN 序列

        Args:
            series (pandas.Series): 数据序列

            n (int): 周期

        Returns:
            pandas.Series: 三角移动平均值序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            trma = tafunc.trma(klines.close, 10)
            print(list(trma))
        """
        ...

    @tobtind(lib='tq')
    def harmean(self, length: int = 10, **kwargs) -> series:
        """
        调和平均值: 求series在n个周期内的调和平均值

            计算方法:
                harmean(x, 5) = 1 / [(1 / x(1) + 1 / x(2) + 1 / x(3) + 1 / x(4) + 1 / x(5)) / 5]

            注意:
            1. 调和平均值与倒数的简单平均值互为倒数
            2. 当n为0, 或当n为有效值但当前的series序列元素个数不足n个, 函数返回 NaN 序列

        Args:
            series (pandas.Series): 数据序列

            n (int): 周期

        Returns:
            pandas.Series: 调和平均值序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            harmean = tafunc.harmean(klines.close, 5)  # 求5周期收盘价的调和平均值
            print(list(harmean))
        """
        ...

    @tobtind(lib='tq')
    def numpow(self, n: int = 5, m: int = 2, **kwargs) -> series:
        """
        自然数幂方和

            计算方法:
                numpow(x, n, m) = n ^ m * x + (n - 1) ^ m * x.shift(1) + (n - 2) ^ m * x.shift(2) + ... + 2 ^ m * x.shift(n - 2) + 1 ^ m * x.shift(n - 1)

            注意: 当n为有效值但当前的series序列元素个数不足n个, 函数返回 NaN 序列

        Args:
            series (pandas.Series): 数据序列

            n (int): 自然数

            m (int): 实数

        Returns:
            pandas.Series: 幂方和序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            numpow = tafunc.numpow(klines.close, 5, 2)
            print(list(numpow))
        """
        ...

    @tobtind(lib='tq')
    def abs(self, **kwargs) -> series:
        """
        获取series的绝对值

            注意: 正数的绝对值是它本身, 负数的绝对值是它的相反数, 0的绝对值还是0

        Args:
            series (pandas.Series): 数据序列

        Returns:
            pandas.Series: 绝对值序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            abs = tafunc.abs(klines.close)
            print(list(abs))
        """
        ...

    @tobtind(lib='tq')
    def min(self, b=None, **kwargs) -> series:
        """
        获取series1和series2中的最小值

        Args:
            a (pandas.Series): 数据序列1

            b (pandas.Series): 数据序列2

        Returns:
            pandas.Series: 最小值序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            min = tafunc.min(klines.close, klines.open)
            print(list(min))
        """
        ...

    @tobtind(lib='tq')
    def max(self, b=None, **kwargs) -> series:
        """
        获取series1和series2中的最大值

        Args:
            series1 (pandas.Series): 数据序列1

            series2 (pandas.Series): 数据序列2

        Returns:
            pandas.Series: 最大值序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            max = tafunc.max(klines.close, klines.open)
            print(list(max))
        """
        ...

    @tobtind(lib='tq')
    def median(self, length: int = 10, **kwargs) -> series:
        """
        中位数: 求series在n个周期内居于中间的数值

            注意:
                1. 当n为有效值但当前的series序列元素个数不足n个, 函数返回 NaN 序列
                2. 对n个周期内所有series排序后, 若n为奇数, 则选择第(n + 1) / 2个为中位数, 若n为偶数, 则中位数是(n / 2)以及(n / 2 + 1)的平均数

        Args:
            close (pandas.Series): 数据序列

            n (int): 周期

        Returns:
            pandas.Series: 中位数序列

        Example::

            例1:
                # 假设最近3日的收盘价为2727, 2754, 2748, 那么当前 median(df["close"], 3) 的返回值是2748
                median3 = tafunc.median(df["close"], 3)

            例2:
                # 假设最近4日的开盘价为2752, 2743, 2730, 2728, 那么当前 median(df["open"], 4) 的返回值是2736.5
                median4 = tafunc.median(df["open"], 4)
        """
        ...

    @tobtind(lib='tq')
    def exist(self, cond=None, length: int = 10, **kwargs) -> series:
        """
        判断n个周期内, 是否有满足cond的条件, 若满足则值为1, 不满足为0

        Args:
            cond (array_like): 条件

            n (int): 周期

        Returns:
            pandas.Series: 判断结果序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            # 判断4个周期中是否存在收盘价大于前一个周期的最高价, 存在返回1, 不存在则返回0
            exist = tafunc.exist(klines.close > klines.high.shift(1), 4)
            print(list(exist))
        """
        ...

    @tobtind(lib='tq')
    def every(self, cond=None, length: int = 3, **kwargs) -> series:
        """
        判断n个周期内, 是否一直满足cond条件, 若满足则值为1, 不满足为0

        Args:
            cond (array_like): 条件

            n (int): 周期

        Returns:
            pandas.Series: 判断结果序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            # 判断在4周期内, 3周期的简单移动平均是否一直大于5周期的简单移动平均
            every = tafunc.every(tafunc.ma(klines.close, 3)
                                 > tafunc.ma(klines.close, 5), 4)
            print(list(every))
        """
        ...

    @tobtind(lib='tq')
    def hhv(self, length: int = 10, **kwargs) -> series:
        """
        求series在n个周期内的最高值

            注意: n为0的情况下, 或当n为有效值但当前的series序列元素个数不足n个, 函数返回 NaN 序列

        Args:
            series (pandas.Series): 数据序列

            n (int): 周期

        Returns:
            pandas.Series: 最高值序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            hhv = tafunc.hhv(klines.high, 4)  # 求4个周期最高价的最大值, 即4周期高点(包含当前k线)
            print(list(hhv))
        """
        ...

    @tobtind(lib='tq')
    def llv(self, length: int = 10, **kwargs) -> series:
        """
        求在n个周期内的最小值

            注意: n为0的情况下, 或当n为有效值但当前的series序列元素个数不足n个, 函数返回 NaN 序列

        Args:
            series (pandas.Series): 数据序列

            n (int): 周期

        Returns:
            pandas.Series: 最小值序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            llv = tafunc.llv(klines.low, 5)  # 求5根k线最低点(包含当前k线)
            print(list(llv))
        """
        ...

    @tobtind(lib='tq')
    def avedev(self, length: int = 10, **kwargs) -> series:
        """
        平均绝对偏差: 求series在n周期内的平均绝对偏差

            算法:
                计算avedev(df["close"],3)在最近一根K线上的值:
                (abs(df["close"] - (df["close"] + df["close"].shift(1) + df["close"].shift(2)) / 3) + abs(
                df["close"].shift(1) - (df["close"] + df["close"].shift(1) + df["close"].shift(2)) / 3) + abs(
                df["close"].shift(2) - (df["close"] + df["close"].shift(1) + df["close"].shift(2)) / 3)) / 3

            注意: n为0的情况下, 或当n为有效值但当前的series序列元素个数不足n个, 函数返回 NaN 序列

        Args:
            series (pandas.Series): 数据序列

            n (int): 周期

        Returns:
            pandas.Series: 平均绝对偏差序列

        Example::

            from tqsdk import TqApi, TqAuth, TqSim, tafunc

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("CFFEX.IF1908", 24 * 60 * 60)
            # 计算收盘价在5周期内的平均绝对偏差, 表示5个周期内每个周期的收盘价与5周期收盘价的平均值的差的绝对值的平均值, 判断收盘价与其均值的偏离程度:
            avedev = tafunc.avedev(klines.close, 5)
            print(list(avedev))
        """
        ...

    @tobtind(lib='tq')
    def barlast(self, cond=None, **kwargs) -> series:
        """
        返回一个序列,其中每个值表示从上一次条件成立到当前的周期数

        (注: 如果从cond序列第一个值到某个位置之间没有True,则此位置的返回值为 -1; 条件成立的位置上的返回值为0)


        Args:
            cond (pandas.Series): 条件序列(序列中的值需为 True 或 False)

        Returns:
            pandas.Series : 周期数序列(其长度和 cond 相同;最后一个值即为最后一次条件成立到最新一个数据的周期数)

        Example::

            from tqsdk import TqApi, TqAuth
            from tqsdk.tafunc import barlast

            api = TqApi(auth=TqAuth("信易账户", "账户密码"))
            klines = api.get_kline_serial("SHFE.cu1912", 60)
            # print(list(klines.close))
            # print(list(klines.open))
            # print(list(klines.close > klines.open))
            n = barlast(klines.close > klines.open)  # 获取周期数序列
            print(list(n))
            print(n.iloc[-1])  # 获取最后一根k线到上一次满足 "收盘价大于开盘价" 条件的k线的周期数
            api.close()

        """
        ...

    @tobtind(lib='tq')
    def cum_counts(self, cond=None, **kwargs) -> series:
        """
        统计连续为1的个数, 用于计算最大连续盈利/亏损天数
        input:  [0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 0,
            1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 0]
        output: [0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 2, 0, 1, 0, 0,
            1, 2, 3, 4, 0, 1, 2, 3, 4, 5, 0, 1, 2, 3, 0, 0]
        """
        ...


class TaLib:
    """Ta-Lib指标指引"""
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    # Cycle Indicator Functions
    @tobtind(category='Cycle Indicator Functions', lib='talib')
    def HT_DCPERIOD(self, **kwargs) -> series:
        """HT_DCPERIOD - Hilbert Transform - Dominant Cycle Period
            ---
            args : close
            名称: 希尔伯特变换-主导周期

            简介:将价格作为信息信号,计算价格处在的周期的位置,作为择时的依据。
        """
        ...

    @tobtind(category='Cycle Indicator Functions', lib='talib')
    def HT_DCPHASE(self, **kwargs) -> series:
        """HT_DCPHASE - Hilbert Transform - Dominant Cycle Phase
        ---
        args:close

        名称: 希尔伯特变换-主导循环阶段 """
        ...

    @tobtind(lines=["inphase", "quadrature"], category='Cycle Indicator Functions', lib='talib')
    def HT_PHASOR(self, **kwargs) -> dataframe:
        """HT_PHASOR - Hilbert Transform - Phasor Components
        ---
        args:close

        lines=inphase, quadrature

        名称: 希尔伯特变换-希尔伯特变换相量分量 """
        ...

    @tobtind(lines=["sine", "leadsine"], category='Cycle Indicator Functions', lib='talib')
    def HT_SINE(self, **kwargs) -> dataframe:
        """HT_SINE - Hilbert Transform - SineWave
        ---
        args:close

        lines=sine, leadsine

        名称: 希尔伯特变换-正弦波
        """
        ...

    @tobtind(category='Cycle Indicator Functions', lib='talib')
    def HT_TRENDMODE(self, **kwargs) -> series:
        """HT_TRENDMODE - Hilbert Transform - Trend vs Cycle Mode
        ---
        args:close

        名称: 希尔伯特变换-趋势与周期模式 """
        ...

    # Math Operator Functions
    @tobtind(category="Math Operator Functions", lib='talib')
    def ADD(self, **kwargs) -> series:
        """ADD - Vector Arithmetic Add
        ---
        args:high,low

        名称:向量加法运算"""
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def DIV(self, **kwargs) -> series:
        """DIV - Vector Arithmetic Div
        ---
        args:high,low

        名称:向量除法运算"""
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def MAX(self, timeperiod=30, **kwargs) -> series:
        """MAX - Highest value over a specified period
        ---
        args:close

        名称:周期内最大值"""
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def MAXINDEX(self, timeperiod=30, **kwargs) -> series:
        """MAXINDEX - Index of highest value over a specified period
        ---
        args:close

        名称:周期内最大值的索引 """
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def MIN(self, timeperiod=30, **kwargs) -> series:
        """MIN - Lowest value over a specified period
        ---
        args:close

        名称:周期内最小值 """
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def MININDEX(self, timeperiod=30, **kwargs) -> series:
        """MININDEX - Index of lowest value over a specified period
        ---
        args:close

        名称:周期内最小值的索引 """
        ...

    @tobtind(lines=["min", "max"], category="Math Operator Functions", lib='talib')
    def MINMAX(self, timeperiod=30, **kwargs) -> dataframe:
        """MINMAX - Lowest and highest values over a specified period
        ---
        args:close

        lines:min , max

        名称:周期内最小值和最大值"""
        ...

    @tobtind(lines=["minidx", "maxidx"], category="Math Operator Functions", lib='talib')
    def MINMAXINDEX(self, timeperiod=30, **kwargs) -> dataframe:
        """MINMAXINDEX - Indexes of lowest and highest values over a specified period
        ---
        args:close

        lines:minidx , maxidx

        名称:周期内最小值和最大值"""
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def MULT(self, **kwargs) -> series:
        """MULT - Vector Arithmetic Mult
        ---
        args:high,low

        名称:向量乘法运算"""
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def SUB(self, **kwargs) -> series:
        """SUB - Vector Arithmetic Substraction
        ---
        args:high,low

        名称:向量减法运算"""
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def SUM(self, timeperiod=30, **kwargs) -> series:
        """SUM - Summation
        ---
        args:close

        名称:周期内求和"""
        ...

    # Math Transform Functions
    @tobtind(category="Math Transform Functions", lib='talib')
    def ACOS(self, **kwargs) -> series:
        """ACOS - Vector Trigonometric ACos
        ---
        args:close

        名称:acos函数是反余弦函数,三角函数 """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def ASIN(self, **kwargs) -> series:
        """ASIN - Vector Trigonometric ASin
        ---
        args:close

        名称:反正弦函数,三角函数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def ATAN(self, **kwargs) -> series:
        """ATAN - Vector Trigonometric ATan
        ---
        args:close

        名称:数字的反正切值,三角函数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def CEIL(self, **kwargs) -> series:
        """CEIL - Vector Ceil
        ---
        args:close

        简介:向上取整数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def COS(self, **kwargs) -> series:
        """COS - Vector Trigonometric Cos
        ---
        args:close

        名称:余弦函数,三角函数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def COSH(self, **kwargs) -> series:
        """COSH - Vector Trigonometric Cosh
        ---
        args:close

        名称:双曲正弦函数,三角函数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def EXP(self, **kwargs) -> series:
        """EXP - Vector Arithmetic Exp
        ---
        args:close

        名称:指数曲线,三角函数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def FLOOR(self, **kwargs) -> series:
        """FLOOR - Vector Floor
        ---
        args:close

        名称:向下取整数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def LN(self, **kwargs) -> series:
        """LN - Vector Log Natural
        ---
        args:close

        名称:自然对数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def LOG10(self, **kwargs) -> series:
        """LOG10 - Vector Log10
        ---
        args:close

        名称:对数函数log
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def SIN(self, **kwargs) -> series:
        """SIN - Vector Trigonometric Sin
        ---
        args:close

        名称:正弦函数,三角函数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def SINH(self, **kwargs) -> series:
        """SINH - Vector Trigonometric Sinh
        ---
        args:close

        名称:双曲正弦函数,三角函数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def SQRT(self, **kwargs) -> series:
        """SQRT - Vector Square Root
        ---
        args:close

        名称:非负实数的平方根"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def TAN(self, **kwargs) -> series:
        """TAN - Vector Trigonometric Tan
        ---
        args:close

        名称:正切函数,三角函数"""
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def TANH(self, **kwargs) -> series:
        """TANH - Vector Trigonometric Tanh
        ---
        args:close

        名称:双曲正切函数,三角函数"""
        ...

    # Momentum Indicator Functions
    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ADX(self, timeperiod=14, **kwargs) -> series:
        """ADX - Average Directional Movement Index
        ---
        args:high, low, close

        名称:平均趋向指数
        简介:使用ADX指标,指标判断盘整、振荡和单边趋势。
        #### 公式:
        一、先决定股价趋势(Directional Movement,DM)是上涨或下跌:
        “所谓DM值,今日股价波动幅度大于昨日股价波动幅部分的最大值,可能是创高价的部分或创低价的部分;如果今日股价波动幅度较前一日小,则DM = 0。”
        若股价高点持续走高,为上涨趋势,记作 +DM。
        若为下跌趋势,记作 -DM。-DM的负号(–)是表示反向趋势(下跌),并非数值为负数。
        其他状况:DM = 0。
        二、寻找股价的真实波幅(True Range,TR):
        所谓真实波幅(TR)是以最高价,最低价,及前一日收盘价三个价格做比较,求出当日股价波动的最大幅度。
        三、趋势方向需经由一段时间来观察,研判上才有意义。一般以14天为指标的观察周期:
        先计算出 +DM、–DM及TR的14日算术平均数,得到 +DM14、–DM14及TR14三组数据作为起始值,再计算各自的移动平均值(EMA)。
        ```
            +DI14 = +DM/TR14*100
            -DI14 = +DM/TR14*100

            DX = |(+DI14)-(-DI14)| / |(+DI14)+(-DI14)|

            DX运算结果取其绝对值,再将DX作移动平均,得到ADX。
        ```

        #### 特点:
        * ADX无法告诉你趋势的发展方向。
        * 如果趋势存在,ADX可以衡量趋势的强度。不论上升趋势或下降趋势,ADX看起来都一样。
        * ADX的读数越大,趋势越明显。衡量趋势强度时,需要比较几天的ADX 读数,观察ADX究竟是上升或下降。ADX读数上升,代表趋势转强;如果ADX读数下降,意味着趋势转弱。
        * 当ADX曲线向上攀升,趋势越来越强,应该会持续发展。如果ADX曲线下滑,代表趋势开始转弱,反转的可能性增加。
        * 单就ADX本身来说,由于指标落后价格走势,所以算不上是很好的指标,不适合单就ADX进行操作。可是,如果与其他指标配合运用,ADX可以确认市场是否存在趋势,并衡量趋势的强度。

        #### 指标应用:
        * +DI与–DI表示多空相反的二个动向,当据此绘出的两条曲线彼此纠结相缠时,代表上涨力道与下跌力道相当,多空势均力敌。当 +DI与–DI彼此穿越时,由下往上的一方其力道开始压过由上往下的另一方,此时出现买卖讯号。
        * ADX可作为趋势行情的判断依据,当行情明显朝多空任一方向进行时,ADX数值都会显著上升,趋势走强。若行情呈现盘整格局时,ADX会低于 +DI与–DI二条线。若ADX数值低于20,则不论DI表现如何,均显示市场没有明显趋势。
        * ADX持续偏高时,代表“超买”(Overbought)或“超卖”(Oversold)的现象,行情反转的机会将增加,此时则不适宜顺势操作。当ADX数值从上升趋势转为下跌时,则代表行情即将反转;若ADX数值由下跌趋势转为上升时,行情将止跌回升。
        * 总言之,DMI指标包含4条线:+DI、-DI、ADX和ADXR。+DI代表买盘的强度、-DI代表卖盘的强度;ADX代表趋势的强度、ADXR则为ADX的移动平均。"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ADXR(self, timeperiod=14, **kwargs) -> series:
        """ADXR- Average Directional Movement Index Rating
        ---
        args:high, low, close

        名称:平均趋向指数的趋向指数

        简介:使用ADXR指标,指标判断ADX趋势。"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def APO(self, fastperiod=12, slowperiod=26, matype=0, **kwargs) -> series:
        """APO - Absolute Price Oscillator
        ---
        args: close"""
        ...

    @tobtind(lines=["aroondown", "aroonup"], category="Momentum Indicator Functions", lib='talib')
    def AROON(self, timeperiod=14, **kwargs) -> series:
        """AROON - Aroon
        ---
        args:high, low
        lines:aroondown, aroonup

        名称:阿隆指标
        简介:该指标是通过计算自价格达到近期最高值和最低值以来所经过的期间数,阿隆指标帮助你预测价格趋势到趋势区域(或者反过来,从趋势区域到趋势)的变化。
        #### 计算公式:
        ```
        Aroon(上升)=[(计算期天数-最高价后的天数)/计算期天数]*100
        Aroon(下降)=[(计算期天数-最低价后的天数)/计算期天数]*100
        ```
        #### 指数应用
        1、极值0和100
        当UP线达到100时,市场处于强势;如果维持在70~100之间,表示一个上升趋势。同样,如果Down线达到0,表示处于弱势,如果维持在0~30之间,表示处于下跌趋势。如果两条线同处于极值水平,则表明一个更强的趋势。
        2、平行运动
        如果两条线平行运动时,表明市场趋势被打破。可以预期该状况将持续下去,只到由极值水平或交叉穿行西安市出方向性运动为止。
        3、交叉穿行
        当下行线上穿上行线时,表明潜在弱势,预期价格开始趋于下跌。反之,表明潜在强势,预期价格趋于走高。"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def AROONOSC(self, timeperiod=14, **kwargs) -> series:
        """AROONOSC - Aroon Oscillator
        ---
        args:high, low

        名称:阿隆振荡  """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def BOP(self, **kwargs) -> series:
        """BOP - Balance Of Power 均势
        ---
        args:open,high, low,close"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def CCI(self, timeperiod=14, **kwargs) -> series:
        """CCI - Commodity Channel Index
        ---
        args:high, low,close

        名称:顺势指标
        简介:CCI指标专门测量股价是否已超出常态分布范围

        #### 指标应用
        * 1.当CCI指标曲线在+100线～-100线的常态区间里运行时,CCI指标参考意义不大,可以用KDJ等其它技术指标进行研判。
        * 2.当CCI指标曲线从上向下突破+100线而重新进入常态区间时,表明市场价格的上涨阶段可能结束,将进入一个比较长时间的震荡整理阶段,应及时平多做空。
        * 3.当CCI指标曲线从上向下突破-100线而进入另一个非常态区间(超卖区)时,表明市场价格的弱势状态已经形成,将进入一个比较长的寻底过程,可以持有空单等待更高利润。如果CCI指标曲线在超卖区运行了相当长的一段时间后开始掉头向上,表明价格的短期底部初步探明,可以少量建仓。CCI指标曲线在超卖区运行的时间越长,确认短期的底部的准确度越高。
        * 4.CCI指标曲线从下向上突破-100线而重新进入常态区间时,表明市场价格的探底阶段可能结束,有可能进入一个盘整阶段,可以逢低少量做多。
        * 5.CCI指标曲线从下向上突破+100线而进入非常态区间(超买区)时,表明市场价格已经脱离常态而进入强势状态,如果伴随较大的市场交投,应及时介入成功率将很大。
        * 6.CCI指标曲线从下向上突破+100线而进入非常态区间(超买区)后,只要CCI指标曲线一直朝上运行,表明价格依然保持强势可以继续持有待涨。但是,如果在远离+100线的地方开始掉头向下时,则表明市场价格的强势状态将可能难以维持,涨势可能转弱,应考虑卖出。如果前期的短期涨幅过高同时价格回落时交投活跃,则应该果断逢高卖出或做空。
        * CCI主要是在超买和超卖区域发生作用,对急涨急跌的行情检测性相对准确。非常适用于股票、外汇、贵金属等市场的短期操作。"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def CMO(self, timeperiod=14, **kwargs) -> series:
        """CMO - Chande Momentum Oscillator 钱德动量摆动指标
        ---
        args:close

        名称:钱德动量摆动指标
        简介:与其他动量指标摆动指标如相对强弱指标(RSI)和随机指标(KDJ)不同,钱德动量指标在计算公式的分子中采用上涨日和下跌日的数据。
        计算公式:CMO=(Su－Sd)*100/(Su+Sd)
        其中:Su是今日收盘价与昨日收盘价(上涨日)差值加总。若当日下跌,则增加值为0;Sd是今日收盘价与做日收盘价(下跌日)差值的绝对值加总。若当日上涨,则增加值为0;


        #### 指标应用
        * 本指标类似RSI指标。
        * 当本指标下穿-50水平时是买入信号,上穿+50水平是卖出信号。
        * 钱德动量摆动指标的取值介于-100和100之间。
        * 本指标也能给出良好的背离信号。
        * 当股票价格创出新低而本指标未能创出新低时,出现牛市背离;
        * 当股票价格创出新高而本指标未能创出新高时,当出现熊市背离时。
        * 我们可以用移动均值对该指标进行平滑。"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def DX(self, timeperiod=14, **kwargs) -> series:
        """DX - Directional Movement Index DMI指标又叫动向指标或趋向指标
        ---
        args:high, low,close

        名称:动向指标或趋向指标
        简介:通过分析股票价格在涨跌过程中买卖双方力量均衡点的变化情况,即多空双方的力量的变化受价格波动的影响而发生由均衡到失衡的循环过程,从而提供对趋势判断依据的一种技术指标。
        分析和应用:[百度百科](https://baike.baidu.com/item/DMI%E6%8C%87%E6%A0%87/3423254?fr=aladdin)
        [维基百科](https://zh.wikipedia.org/wiki/%E5%8B%95%E5%90%91%E6%8C%87%E6%95%B8)
        [同花顺学院](http://www.iwencai.com/school/search?cg=100&w=DMI) """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def MACD(self, fastperiod=12, slowperiod=26, signalperiod=9, **kwargs) -> dataframe:
        """MACD - Moving Average Convergence/Divergence
        ---
        args:close
        lines:dif, dem, histogram

        名称:平滑异同移动平均线
        简介:利用收盘价的短期(常用为12日)指数移动平均线与长期(常用为26日)指数移动平均线之间的聚合与分离状况,对买进、卖出时机作出研判的技术指标。
        分析和应用:[百度百科](https://baike.baidu.com/item/MACD%E6%8C%87%E6%A0%87?fromtitle=MACD&fromid=3334786)
        [维基百科](https://zh.wikipedia.org/wiki/MACD)
        [同花顺学院](http://www.iwencai.com/school/search?cg=100&w=MACD)  """
        ...

    @tobtind(lines=["dif", "dem", "histogram"], category="Momentum Indicator Functions", lib='talib')
    def MACDEXT(self, fastperiod=12, fastmatype=0, slowperiod=26, slowmatype=0, signalperiod=9, signalmatype=0, **kwargs) -> dataframe:
        """MACDEXT - MACD with controllable MA type
        ---
        args:close
        lines:dif, dem, histogram

        名称:平滑异同移动平均线(可控制移动平均算法)
        简介:同MACD函数(固定使用EMA作为matype),并提供参数控制计算DIF, DEM时使用的移动平均算法。计算DIF时使用fastmatype与slowmatype,计算DEM时使用signalmatype,`Histogram = DIF - DEM`。matype参数详见`talib.MA_Type`与`Overlap Studies Functions 重叠研究指标`文档。
        分析和应用:[百度百科](https://baike.baidu.com/item/MACD%E6%8C%87%E6%A0%87?fromtitle=MACD&fromid=3334786)
        [维基百科](https://zh.wikipedia.org/wiki/MACD)
        [同花顺学院](http://www.iwencai.com/school/search?cg=100&w=MACD) """
        ...

    @tobtind(lines=["dif", "dem", "histogram"], category="Momentum Indicator Functions", lib='talib')
    def MACDFIX(self, signalperiod=9, **kwargs) -> dataframe:
        """MACDFIX - Moving Average Convergence/Divergence Fix 12/26
        ---
        args:close
        lines:dif, dem, histogram

        名称:平滑异同移动平均线(固定快慢均线周期为12/26)
        简介:同MACD函数, 固定快均线周期fastperiod=12, 慢均线周期slowperiod=26. """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def MFI(self, timeperiod=14, **kwargs) -> series:
        """MFI - Money Flow Index 资金流量指标
        ---
        args:high, low,close,volume

        名称:资金流量指标
        简介:属于量价类指标,反映市场的运行趋势
        分析和应用:[百度百科](https://baike.baidu.com/item/mfi/7429225?fr=aladdin)
        [同花顺学院](http://www.iwencai.com/school/search?cg=100&w=MFI) """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def MINUS_DI(self, timeperiod=14, **kwargs) -> series:
        """MINUS_DI - Minus Directional Indicator
        ---
        args:high, low,close

        名称:下升动向值
        简介:通过分析股票价格在涨跌过程中买卖双方力量均衡点的变化情况,即多空双方的力量的变化受价格波动的影响而发生由均衡到失衡的循环过程,从而提供对趋势判断依据的一种技术指标。
        分析和应用:[百度百科](https://baike.baidu.com/item/DMI%E6%8C%87%E6%A0%87/3423254?fr=aladdin)
        [维基百科](https://zh.wikipedia.org/wiki/%E5%8B%95%E5%90%91%E6%8C%87%E6%95%B8)
        [同花顺学院](http://www.iwencai.com/school/search?cg=100&w=DMI) """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def MINUS_DM(self, timeperiod=14, **kwargs) -> series:
        """MINUS_DM - Minus Directional Movement
        ---
        args:high, low

        名称: 上升动向值 DMI中的DM代表正趋向变动值即上升动向值
        简介:通过分析股票价格在涨跌过程中买卖双方力量均衡点的变化情况,即多空双方的力量的变化受价格波动的影响而发生由均衡到失衡的循环过程,从而提供对趋势判断依据的一种技术指标。
        分析和应用:[百度百科](https://baike.baidu.com/item/DMI%E6%8C%87%E6%A0%87/3423254?fr=aladdin)
        [维基百科](https://zh.wikipedia.org/wiki/%E5%8B%95%E5%90%91%E6%8C%87%E6%95%B8)
        [同花顺学院](http://www.iwencai.com/school/search?cg=100&w=DMI) """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def MOM(self, timeperiod=10, **kwargs) -> series:
        """MOM - Momentum  动量
        ---
        args:close

        名称: 上升动向值
        简介:投资学中意思为续航,指股票(或经济指数)持续增长的能力。研究发现,赢家组合在牛市中存在着正的动量效应,输家组合在熊市中存在着负的动量效应。
        分析和应用:
        [维基百科](https://zh.wikipedia.org/wiki/%E5%8B%95%E9%87%8F%E6%8C%87%E6%A8%99)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/cb18b2dbe2f455e6) """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def PLUS_DI(self, timeperiod=14, **kwargs) -> series:
        """PLUS_DI - Plus Directional Indicator
        ---
        args:high, low,close"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def PLUS_DM(self, timeperiod=14, **kwargs) -> series:
        """PLUS_DM - Plus Directional Movement
        ---
        args:high, low"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def PPO(self, fastperiod=12, slowperiod=26, matype=0, **kwargs) -> series:
        """PPO - Percentage Price Oscillator 价格震荡百分比指数
        ---
        args:close

        名称: 价格震荡百分比指数
        简介:价格震荡百分比指标(PPO)是一个和MACD指标非常接近的指标。
        PPO标准设定和MACD设定非常相似:12,26,9和PPO,和MACD一样说明了两条移动平均线的差距,但是它们有一个差别是PPO是用百分比说明。
        分析和应用:
        [参考](http://blog.sina.com.cn/s/blog_7542a31c0101aux9.html)"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ROC(self, timeperiod=10, **kwargs) -> series:
        """ROC - Rate of change : ((price/prevPrice)-1)*100  变动率指标
        ---
        args:close

        名称: 变动率指标
        简介:ROC是由当天的股价与一定的天数之前的某一天股价比较,其变动速度的大小,来反映股票市变动的快慢程度
        分析和应用:[百度百科](https://baike.baidu.com/item/ROC%E6%8C%87%E6%A0%87/3081705?fr=aladdin)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/6ac184fdb20d2f59)   """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ROCP(self, timeperiod=10, **kwargs) -> series:
        """ROCP - Rate of change Percentage: (price-prevPrice)/prevPrice
        ---
        args:close"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ROCR(self, timeperiod=10, **kwargs) -> series:
        """ROCR - Rate of change ratio: (price/prevPrice)
        ---
        args:close"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ROCR100(self, timeperiod=10, **kwargs) -> series:
        """ROCR100 - Rate of change ratio 100 scale: (price/prevPrice)*100
        ---
        args:close"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def RSI(self, timeperiod=14, **kwargs) -> series:
        """RSI - Relative Strength Index  相对强弱指数
        ---
        args:close

        名称:相对强弱指数
        简介:是通过比较一段时期内的平均收盘涨数和平均收盘跌数来分析市场买沽盘的意向和实力,从而作出未来市场的走势。
        分析和应用:[百度百科](https://baike.baidu.com/item/RSI/6130115)
        [维基百科](https://zh.wikipedia.org/wiki/%E7%9B%B8%E5%B0%8D%E5%BC%B7%E5%BC%B1%E6%8C%87%E6%95%B8)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/6a280c6cebcf140a) """
        ...

    @tobtind(lines=["slowk", "slowd"], category="Momentum Indicator Functions", lib='talib')
    def STOCH(self, fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0, **kwargs) -> dataframe:
        """STOCH - Stochastic 随机指标,俗称KD
        ---
        args:high, low,close
        lines:slowk, slowd

        名称:随机指标,俗称KD """
        ...

    @tobtind(lines=["fastk", "fastd"], category="Momentum Indicator Functions", lib='talib')
    def STOCHF(self, fastk_period=5, fastd_period=3, fastd_matype=0, **kwargs) -> dataframe:
        """STOCHF - Stochastic Fast
        ---
        args:high, low,close
        lines:fastk, fastd """
        ...

    @tobtind(lines=["fastk", "fastd"], category="Momentum Indicator Functions", lib='talib')
    def STOCHRSI(self, timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0, **kwargs) -> dataframe:
        """STOCHRSI - Stochastic Relative Strength Index
        ---
        args:close
        lines:fastk, fastd """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def TRIX(self, timeperiod=30, **kwargs) -> series:
        """TRIX - 1-day Rate-Of-Change (ROC) of a Triple Smooth EMA
        ---
        args:close"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ULTOSC(self, timeperiod1=7, timeperiod2=14, timeperiod3=28, **kwargs) -> series:
        """ULTOSC - Ultimate Oscillator 终极波动指标
        ---
        args:high, low,close

        名称:终极波动指标
        简介:UOS是一种多方位功能的指标,除了趋势确认及超买超卖方面的作用之外,它的“突破”讯号不仅可以提供最适当的交易时机之外,更可以进一步加强指标的可靠度。
        分析和应用:[百度百科](https://baike.baidu.com/item/%E7%BB%88%E6%9E%81%E6%B3%A2%E5%8A%A8%E6%8C%87%E6%A0%87/1982936?fr=aladdin&fromid=12610066&fromtitle=%E7%BB%88%E6%9E%81%E6%8C%87%E6%A0%87)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/e89b98d39da975e4)"""
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def WILLR(self, timeperiod=14, **kwargs) -> series:
        """WILLR - Williams' %R 威廉指标
        ---
        args:high, low,close

        名称:威廉指标
        简介:WMS表示的是市场处于超买还是超卖状态。股票投资分析方法主要有如下三种:基本分析、技术分析、演化分析。在实际应用中,它们既相互联系,又有重要区别。
        分析和应用:[百度百科](https://baike.baidu.com/item/%E5%A8%81%E5%BB%89%E6%8C%87%E6%A0%87?fr=aladdin)
        [维基百科](https://zh.wikipedia.org/wiki/%E5%A8%81%E5%BB%89%E6%8C%87%E6%A8%99)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/967febb0316c57c1) """
        ...

    # Overlap Studies Functions
    @tobtind(lines=["upperband", "middleband", "lowerband"], overlap=True, category="overlap", lib='talib')
    def BBANDS(self, timeperiod=5, nbdevup=2, nbdevdn=2, matype=0, **kwargs) -> dataframe:
        """BBANDS - Bollinger Bands
        ---
        args:close
        lines:upperband, middleband, lowerband

        名称: 布林线指标
        简介:其利用统计原理,求出股价的标准差及其信赖区间,从而确定股价的波动范围及未来走势,利用波带显示股价的安全高低价位,因而也被称为布林带。
        分析和应用:
        [百度百科](https://baike.baidu.com/item/bollinger%20bands/1612394?fr=aladdin)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/56d0d9be66b4f7a0?rid=53) """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def DEMA(self, timeperiod=30, **kwargs) -> series:
        """DEMA - Double Exponential Moving Average  双移动平均线
        ---
        args:close

        名称: 双移动平均线
        简介:两条移动平均线来产生趋势信号,较长期者用来识别趋势,较短期者用来选择时机。正是两条平均线及价格三者的相互作用,才共同产生了趋势信号。
        分析和应用:
        [百度百科](https://baike.baidu.com/item/%E5%8F%8C%E7%A7%BB%E5%8A%A8%E5%B9%B3%E5%9D%87%E7%BA%BF/1831921?fr=aladdin)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/a04d723659318237) """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def EMA(self, timeperiod=30, **kwargs) -> series:
        """EMA - Exponential Moving Average
        ---
        args:close

        名称: 指数平均数
        简介:是一种趋向类指标,其构造原理是仍然对价格收盘价进行算术平均,并根据计算结果来进行分析,用于判断价格未来走势的变动趋势。
        [百度百科](https://baike.baidu.com/item/EMA/12646151)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/b7a39d74783ad689?rid=589)   """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def HT_TRENDLINE(self, **kwargs) -> series:
        """HT_TRENDLINE - Hilbert Transform - Instantaneous Trendline
        ---
        args:close

        名称: 希尔伯特瞬时变换
        简介:是一种趋向类指标,其构造原理是仍然对价格收盘价进行算术平均,并根据计算结果来进行分析,用于判断价格未来走势的变动趋势。
        [百度文库](https://wenku.baidu.com/view/0e35f6eead51f01dc281f18e.html) """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def KAMA(self, timeperiod=30, **kwargs) -> series:
        """KAMA - Kaufman Adaptive Moving Average 考夫曼的自适应移动平均线
        ---
        args:close

        名称: 考夫曼的自适应移动平均线
        简介:短期均线贴近价格走势,灵敏度高,但会有很多噪声,产生虚假信号;长期均线在判断趋势上一般比较准确
        ,但是长期均线有着严重滞后的问题。我们想得到这样的均线,当价格沿一个方向快速移动时,短期的移动
        平均线是最合适的;当价格在横盘的过程中,长期移动平均线是合适的。
        [参考1](http://blog.sina.com.cn/s/blog_62d0bbc701010p7d.html)
        [参考2](https://wenku.baidu.com/view/bc4bc9c59ec3d5bbfd0a7454.html?from=search)"""
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def MA(self, timeperiod=30, matype=0, **kwargs) -> series:
        """MA - Moving average  移动平均线
        ---
        args:close

        名称: 移动平均线
        简介:移动平均线,Moving Average,简称MA,原本的意思是移动平均,由于我们将其制作成线形,所以一般称之为移动平均线,简称均线。它是将某一段时间的收盘价之和除以该周期。 比如日线MA5指5天内的收盘价除以5 。
        [百度百科](https://baike.baidu.com/item/%E7%A7%BB%E5%8A%A8%E5%B9%B3%E5%9D%87%E7%BA%BF/217887?fromtitle=MA&fromid=1511750#viewPageContent)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/a04d723659318237?rid=96)   """
        ...

    @tobtind(lines=["mama", "fama"], overlap=True, category="overlap", lib='talib')
    def MAMA(self, fastlimit=0, slowlimit=0, **kwargs) -> dataframe:
        """MAMA - MESA Adaptive Moving Average
        ---
        args:close
        lines:mama, fama"""
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def MAVP(self, periods=14, minperiod=2, maxperiod=30, matype=0, **kwargs) -> series:
        """MAVP - Moving average with variable period
        ---
        args:close"""
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def MIDPOINT(self, timeperiod=14, **kwargs) -> series:
        """MIDPOINT - MidPoint over period
        ---
        args:close"""
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def MIDPRICE(self, timeperiod=14, **kwargs) -> series:
        """MIDPRICE - Midpoint Price over period
        ---
        args:high, low,"""
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def SAR(self, acceleration=0, maximum=0, **kwargs) -> series:
        """SAR - Parabolic SAR  抛物线指标
        ---
        args:high, low

        名称: 抛物线指标
        简介:抛物线转向也称停损点转向,是利用抛物线方式,随时调整停损点位置以观察买卖点。由于停损点(又称转向点SAR)以弧形的方式移动,故称之为抛物线转向指标    。
        [百度百科](https://baike.baidu.com/item/SAR/2771135#viewPageContent)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/d9d94e65be7f6b5e) """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def SAREXT(self, startvalue=0, offsetonreverse=0, accelerationinitlong=0, accelerationlong=0, accelerationmaxlong=0, accelerationinitshort=0, accelerationshort=0, accelerationmaxshort=0, **kwargs) -> series:
        """SAREXT - Parabolic SAR - Extended
        ---
        args:high, low,"""
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def SMA(self, timeperiod=30, **kwargs) -> series:
        """SMA - Simple Moving Average 简单移动平均线
        ---
        args:close

        名称: 简单移动平均线
        简介:移动平均线,Moving Average,简称MA,原本的意思是移动平均,由于我们将其制作成线形,所以一般称之为移动平均线,简称均线。它是将某一段时间的收盘价之和除以该周期。 比如日线MA5指5天内的收盘价除以5 。
        [百度百科](https://baike.baidu.com/item/%E7%A7%BB%E5%8A%A8%E5%B9%B3%E5%9D%87%E7%BA%BF/217887?fromtitle=MA&fromid=1511750#viewPageContent)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/a04d723659318237?rid=96)   """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def T3(self, timeperiod=5, vfactor=0, **kwargs) -> series:
        """T3 - Triple Exponential Moving Average (T3) 三重指数移动平均线
        ---
        args:close

        名称:三重指数移动平均线
        简介:TRIX长线操作时采用本指标的讯号,长时间按照本指标讯号交易,获利百分比大于损失百分比,利润相当可观。 比如日线MA5指5天内的收盘价除以5 。
        [百度百科](https://baike.baidu.com/item/%E4%B8%89%E9%87%8D%E6%8C%87%E6%95%B0%E5%B9%B3%E6%BB%91%E5%B9%B3%E5%9D%87%E7%BA%BF/15749345?fr=aladdin)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/6c22c15ccbf24e64?rid=80)   """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def TEMA(self, timeperiod=30, **kwargs) -> series:
        """TEMA - Triple Exponential Moving Average
        ---
        args:close

        名称:三重指数移动平均线  """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def TRIMA(self, timeperiod=30, **kwargs) -> series:
        """TRIMA - Triangular Moving Average
        ----
        args:close"""
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def WMA(close, timeperiod=30, **kwargs) -> series:
        """WMA - Weighted Moving Average 移动加权平均法
        ---
        args:close

        名称:加权移动平均线
        简介:移动加权平均法是指以每次进货的成本加上原有库存存货的成本,除以每次进货数量与原有库存存货的数量之和,据以计算加权平均单位成本,以此为基础计算当月发出存货的成本和期末存货的成本的一种方法。
        [百度百科](https://baike.baidu.com/item/%E7%A7%BB%E5%8A%A8%E5%8A%A0%E6%9D%83%E5%B9%B3%E5%9D%87%E6%B3%95/10056490?fr=aladdin&fromid=16799870&fromtitle=%E5%8A%A0%E6%9D%83%E7%A7%BB%E5%8A%A8%E5%B9%B3%E5%9D%87)
        [同花顺学院](http://www.iwencai.com/yike/detail/auid/262b1dfd1c68ee30)"""
        ...

    # Pattern Recognition Functions 形态识别
    @tobtind(category="Pattern Recognition Functions", lib='talib')
    def PatternRecognition(self, name: Literal["CDL2CROWS", "CDL3BLACKCROWS", "CDL3INSIDE",
                                               "CDL3LINESTRIKE", "CDL3OUTSIDE", "CDL3STARSINSOUTH",
                                               "CDL3WHITESOLDIERS", "CDLABANDONEDBABY", "CDLADVANCEBLOCK",
                                               "CDLBELTHOLD", "CDLBREAKAWAY", "CDLCLOSINGMARUBOZU",
                                               "CDLCONCEALBABYSWALL", "CDLCOUNTERATTACK", "CDLDARKCLOUDCOVER",
                                               "CDLDOJI", "CDLDOJISTAR", "CDLDRAGONFLYDOJI", "CDLENGULFING",
                                               "CDLEVENINGDOJISTAR", "CDLEVENINGSTAR", "CDLGAPSIDESIDEWHITE",
                                               "CDLGRAVESTONEDOJI", "CDLHAMMER", "CDLHANGINGMAN", "CDLHARAMI",
                                               "CDLHARAMICROSS", "CDLHIGHWAVE", "CDLHIKKAKE", "CDLHIKKAKEMOD",
                                               "CDLHOMINGPIGEON", "CDLIDENTICAL3CROWS", "CDLINNECK",
                                               "CDLINVERTEDHAMMER", "CDLKICKING", "CDLKICKINGBYLENGTH",
                                               "CDLLADDERBOTTOM", "CDLLONGLEGGEDDOJI", "CDLLONGLINE",
                                               "CDLMARUBOZU", "CDLMATCHINGLOW", "CDLMATHOLD", "CDLMORNINGDOJISTAR",
                                               "CDLMORNINGSTAR", "CDLONNECK", "CDLPIERCING", "CDLRICKSHAWMAN",
                                               "CDLRISEFALL3METHODS", "CDLSEPARATINGLINES", "CDLSHOOTINGSTAR",
                                               "CDLSHORTLINE", "CDLSPINNINGTOP", "CDLSTALLEDPATTERN",
                                               "CDLSTICKSANDWICH", "CDLTAKURI", "CDLTASUKIGAP", "CDLTHRUSTING",
                                               "CDLTRISTAR", "CDLUNIQUE3RIVER", "CDLUPSIDEGAP2CROWS",
                                               "CDLXSIDEGAP3METHODS",] = "CDL2CROWS", penetration=0, **kwargs) -> series:
        """Pattern Recognition Functions 形态识别
        ---
        >>> args:open, high, low, close

            >>> "CDL2CROWS"两只乌鸦 , "CDL3BLACKCROWS"三只乌鸦 , "CDL3INSIDE"三内部上涨和下跌,
                "CDL3LINESTRIKE"三线打击, "CDL3OUTSIDE"三外部上涨和下跌, "CDL3STARSINSOUTH"南方三星,
                "CDL3WHITESOLDIERS"三个白兵, "CDLABANDONEDBABY"弃婴, "CDLADVANCEBLOCK"大敌当前,
                "CDLBELTHOLD"捉腰带线, "CDLBREAKAWAY"脱离, "CDLCLOSINGMARUBOZU"收盘缺影线,
                "CDLCONCEALBABYSWALL"藏婴吞没, "CDLCOUNTERATTACK"反击线, "CDLDARKCLOUDCOVER"乌云压顶,
                "CDLDOJI"十字, "CDLDOJISTAR"十字星, "CDLDRAGONFLYDOJI"蜻蜓十字/T形十字, "CDLENGULFING"吞噬模式,
                "CDLEVENINGDOJISTAR"十字暮星, "CDLEVENINGSTAR"暮星, "CDLGAPSIDESIDEWHITE"向上/下跳空并列阳线 ,
                "CDLGRAVESTONEDOJI"墓碑十字/倒T十字, "CDLHAMMER"锤头, "CDLHANGINGMAN"上吊线, "CDLHARAMI"母子线 ,
                "CDLHARAMICROSS"十字孕线, "CDLHIGHWAVE"风高浪大线, "CDLHIKKAKE"陷阱, "CDLHIKKAKEMOD"修正陷阱,
                "CDLHOMINGPIGEON"家鸽, "CDLIDENTICAL3CROWS"三胞胎乌鸦, "CDLINNECK"颈内线,
                "CDLINVERTEDHAMMER"倒锤头, "CDLKICKING"反冲形态, "CDLKICKINGBYLENGTH"由较长缺影线决定的反冲形态,
                "CDLLADDERBOTTOM"梯底, "CDLLONGLEGGEDDOJI"长脚十字, "CDLLONGLINE"长蜡烛,
                "CDLMARUBOZU"光头光脚/缺影线, "CDLMATCHINGLOW"相同低价, "CDLMATHOLD"铺垫, "CDLMORNINGDOJISTAR"十字晨星 ,
                "CDLMORNINGSTAR"晨星, "CDLONNECK"颈上线, "CDLPIERCING"刺透形态, "CDLRICKSHAWMAN"黄包车夫,
                "CDLRISEFALL3METHODS"上升/下降三法, "CDLSEPARATINGLINES"分离线, "CDLSHOOTINGSTAR"射击之星,
                "CDLSHORTLINE"短蜡烛, "CDLSPINNINGTOP"纺锤, "CDLSTALLEDPATTERN"停顿形态,
                "CDLSTICKSANDWICH"条形三明治 , "CDLTAKURI"探水竿, "CDLTASUKIGAP"跳空并列阴阳线, "CDLTHRUSTING"插入,
                "CDLTRISTAR"三星, "CDLUNIQUE3RIVER"奇特三河床, "CDLUPSIDEGAP2CROWS"向上跳空的两只乌鸦,
                "CDLXSIDEGAP3METHODS"上升/下降跳空三法"""
        ...

    # Price Transform Functions
    @tobtind(overlap=True, category="Price Transform Functions", lib='talib')
    def AVGPRICE(self, **kwargs) -> series:
        """AVGPRICE - Average Price
        ---
        args:open, high, low, close

        名称:平均价格函数"""
        ...

    @tobtind(overlap=True, category="Price Transform Functions", lib='talib')
    def MEDPRICE(self, **kwargs) -> series:
        """MEDPRICE - Median Price
        ---
        args:high, low

        名称:中位数价格"""
        ...

    @tobtind(overlap=True, category="Price Transform Functions", lib='talib')
    def TYPPRICE(self, **kwargs) -> series:
        """TYPPRICE - Typical Price
        ---
        args:high, low, close

        名称:代表性价格"""
        ...

    @tobtind(overlap=True, category="Price Transform Functions", lib='talib')
    def WCLPRICE(self, **kwargs) -> series:
        """WCLPRICE - Weighted Close Price
        ---
        args:high, low, close

        名称:加权收盘价"""
        ...

    # Statistic Functions 统计学指标
    @tobtind(category="Price Transform Functions", lib='talib')
    def BETA(self, timeperiod=5, **kwargs) -> series:
        """BETA - Beta
        ---
        args:high, low

        名称:β系数也称为贝塔系数
        简介:一种风险指数,用来衡量个别股票或
        股票基金相对于整个股市的价格波动情况
        贝塔系数衡量股票收益相对于业绩评价基准收益的总体波动性,是一个相对指标。 β 越高,意味着股票相对于业绩评价基准的波动性越大。 β 大于 1 ,
        则股票的波动性大于业绩评价基准的波动性。反之亦然。
        用途:
        1)计算资本成本,做出投资决策(只有回报率高于资本成本的项目才应投资);
        2)计算资本成本,制定业绩考核及激励标准;
        3)计算资本成本,进行资产估值(Beta是现金流贴现模型的基础);
        4)确定单个资产或组合的系统风险,用于资产组合的投资管理,特别是股指期货或其他金融衍生品的避险(或投机)  """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def CORREL(self, timeperiod=30, **kwargs) -> series:
        """CORREL - Pearson's Correlation Coefficient (r)
        ---
        args:high, low

        名称:皮尔逊相关系数
        简介:用于度量两个变量X和Y之间的相关(线性相关),其值介于-1与1之间
        皮尔逊相关系数是一种度量两个变量间相关程度的方法。它是一个介于 1 和 -1 之间的值,
        其中,1 表示变量完全正相关, 0 表示无关,-1 表示完全负相关。"""
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def LINEARREG(self, timeperiod=14, **kwargs) -> series:
        """LINEARREG - Linear Regression
        ---
        args:close

        名称:线性回归
        简介:来确定两种或两种以上变量间相互依赖的定量关系的一种统计分析方法
        其表达形式为y = w'x+e,e为误差服从均值为0的正态分布。
        直线回归方程:当两个变量x与y之间达到显著地线性相关关系时,应用最小二乘法原理确定一条最优直线的直线方程y=a+bx,这条回归直线与个相关点的距离比任何其他直线与相关点的距离都小,是最佳的理想直线.
        回归截距a:表示直线在y轴上的截距,代表直线的起点.
        回归系数b:表示直线的斜率,他的实际意义是说明x每变化一个单位时,影响y平均变动的数量.
        即x每增加1单位,y变化b个单位.  """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def LINEARREG_ANGLE(self, timeperiod=14, **kwargs) -> series:
        """LINEARREG_ANGLE - Linear Regression Angle
        ---
        args:close

        名称:线性回归的角度
        简介:来确定价格的角度变化. """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def LINEARREG_INTERCEPT(self, timeperiod=14, **kwargs) -> series:
        """LINEARREG_INTERCEPT - Linear Regression Intercept
        ---
        args:close

        名称:线性回归截距  """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def LINEARREG_SLOPE(self, timeperiod=14, **kwargs) -> series:
        """LINEARREG_SLOPE - Linear Regression Slope
        ---
        args:close

        名称:线性回归斜率指标"""
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def STDDEV(self, timeperiod=5, nbdev=1, **kwargs) -> series:
        """STDDEV - Standard Deviation
        ---
        args:close

        名称:标准偏差
        简介:种量度数据分布的分散程度之标准,用以衡量数据值偏离算术平均值的程度。标准偏差越小,这些值偏离平均值就越少,反之亦然。标准偏差的大小可通过标准偏差与平均值的倍率关系来衡量。"""
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def TSF(self, timeperiod=14, **kwargs) -> series:
        """TSF - Time Series Forecast
        ---
        args:close

        名称:时间序列预测
        简介:一种历史资料延伸预测,也称历史引伸预测法。是以时间数列所能反映的社会经济现象的发展过程和规律性,进行引伸外推,预测其发展趋势的方法"""
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def VAR(self, timeperiod=5, nbdev=1, **kwargs) -> series:
        """VAR - VAR
        ---
        args:close

        名称:方差
        简介:方差用来计算每一个变量(观察值)与总体均数之间的差异。为避免出现离均差总和为零,离均差平方和受样本含量的影响,统计学采用平均离均差平方和来描述变量的变异程度"""
        ...

    # Volatility Indicator Functions 波动率指标函数
    @tobtind(category="Volatility Indicator Functions", lib='talib')
    def ATR(self, timeperiod=14, **kwargs) -> series:
        """ATR - Average True Range
        ---
        args:high, low, close

        名称:真实波动幅度均值
        简介:真实波动幅度均值(ATR)是
        以 N 天的指数移动平均数平均後的交易波动幅度。
        计算公式:一天的交易幅度只是单纯地 最大值 - 最小值。
        而真实波动幅度则包含昨天的收盘价,若其在今天的幅度之外:
        真实波动幅度 = max(最大值,昨日收盘价) − min(最小值,昨日收盘价) 真实波动幅度均值便是「真实波动幅度」的 N 日 指数移动平均数。

        特性::
        * 波动幅度的概念表示可以显示出交易者的期望和热情。
        * 大幅的或增加中的波动幅度表示交易者在当天可能准备持续买进或卖出股票。
        * 波动幅度的减少则表示交易者对股市没有太大的兴趣。 """
        ...

    @tobtind(category="Volatility Indicator Functions", lib='talib')
    def NATR(self, timeperiod=14, **kwargs) -> series:
        """NATR - Normalized Average True Range
        ---
        args:high, low, close

        名称:归一化波动幅度均值"""
        ...

    @tobtind(category="Volatility Indicator Functions", lib='talib')
    def TRANGE(self, **kwargs) -> series:
        """TRANGE - True Range
        ---
        args:high, low, close

        名称:真正的范围 """
        ...

    # Volume Indicators 成交量指标
    @tobtind(category="Volume Indicators Functions", lib='talib')
    def AD(self, **kwargs) -> series:
        """AD - Chaikin A/D Line 量价指标
        ---
        args:high, low, close, volume

        名称:Chaikin A/D Line 累积/派发线(Accumulation/Distribution Line)
        简介:Marc Chaikin提出的一种平衡交易量指标,以当日的收盘价位来估算成交流量,用于估定一段时间内该证券累积的资金流量。
        计算公式:
        ``` A/D = 昨日A/D + 多空对比 * 今日成交量
        多空对比 = [(收盘价- 最低价) - (最高价 - 收盘价)] / (最高价 - 最低价)
        ```
        若最高价等于最低价: 多空对比 = (收盘价 / 昨收盘) - 1
        研判:
        1、A/D测量资金流向,向上的A/D表明买方占优势,而向下的A/D表明卖方占优势
        2、A/D与价格的背离可视为买卖信号,即底背离考虑买入,顶背离考虑卖出
        3、应当注意A/D忽略了缺口的影响,事实上,跳空缺口的意义是不能轻易忽略的
        A/D指标无需设置参数,但在应用时,可结合指标的均线进行分析"""
        ...

    @tobtind(category="Volume Indicators Functions", lib='talib')
    def ADOSC(self, fastperiod=3, slowperiod=10, **kwargs) -> series:
        """ADOSC - Chaikin A/D Oscillator
        ---
        args:high, low, close, volume

        名称:Chaikin A/D Oscillator Chaikin震荡指标
        简介:将资金流动情况与价格行为相对比,检测市场中资金流入和流出的情况
        计算公式:fastperiod A/D - slowperiod A/D
        研判:
        1、交易信号是背离:看涨背离做多,看跌背离做空
        2、股价与90天移动平均结合,与其他指标结合
        3、由正变负卖出,由负变正买进  """
        ...

    @tobtind(category="Volume Indicators Functions", lib='talib')
    def OBV(self, **kwargs) -> series:
        """OBV - On Balance Volume
        ---
        args:close, volume

        名称:On Balance Volume 能量潮
        简介:Joe Granville提出,通过统计成交量变动的趋势推测股价趋势
        计算公式:以某日为基期,逐日累计每日上市股票总成交量,若隔日指数或股票上涨
        ,则基期OBV加上本日成交量为本日OBV。隔日指数或股票下跌,
        则基期OBV减去本日成交量为本日OBV
        研判:
        1、以“N”字型为波动单位,一浪高于一浪称“上升潮”,下跌称“跌潮”;上升潮买进,跌潮卖出
        2、须配合K线图走势
        3、用多空比率净额法进行修正,但不知TA-Lib采用哪种方法
        计算公式: 多空比率净额= [(收盘价－最低价)－(最高价-收盘价)] ÷( 最高价－最低价)×成交量"""
        ...


class FinTa:
    """finta指标指引"""
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    @tobtind(overlap=True, lib='finta')
    def SMA(self, period: int = 41, **kwargs) -> series:
        """args:close,kwargs:filed
        Simple moving average - rolling mean in pandas lingo. Also known as 'MA'.
        The simple moving average (SMA) is the most basic of the moving averages used for trading.
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def SMM(self, period: int = 9, **kwargs):
        """args:close,kwargs:filed
        Simple moving median, an alternative to moving average. SMA, when used to estimate the underlying trend in a time series,
        is susceptible to rare events such as rapid shocks or other anomalies. A more robust estimate of the trend is the simple moving median over n time periods.
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def SSMA(self, period: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed
        Smoothed simple moving average.

        :param ohlc: data
        :param period: range
        :param column: open/close/high/low column of the DataFrame
        :return: result Series
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def EMA(self, period: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed
        Exponential Weighted Moving Average - Like all moving average indicators, they are much better suited for trending markets.
        When the market is in a strong and sustained uptrend, the EMA indicator line will also show an uptrend and vice-versa for a down trend.
        EMAs are commonly used in conjunction with other indicators to confirm significant market moves and to gauge their validity.
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def DEMA(self, period: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed
        Double Exponential Moving Average - attempts to remove the inherent lag associated to Moving Averages
         by placing more weight on recent values. The name suggests this is achieved by applying a double exponential
        smoothing which is not the case. The name double comes from the fact that the value of an EMA (Exponential Moving Average) is doubled.
        To keep it in line with the actual data and to remove the lag the value 'EMA of EMA' is subtracted from the previously doubled EMA.
        Because EMA(EMA) is used in the calculation, DEMA needs 2 * period -1 samples to start producing values in contrast to the period
        samples needed by a regular EMA
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def TEMA(self, period: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed
        Triple exponential moving average - attempts to remove the inherent lag associated to Moving Averages by placing more weight on recent values.
        The name suggests this is achieved by applying a triple exponential smoothing which is not the case. The name triple comes from the fact that the
        value of an EMA (Exponential Moving Average) is triple.
        To keep it in line with the actual data and to remove the lag the value 'EMA of EMA' is subtracted 3 times from the previously tripled EMA.
        Finally 'EMA of EMA of EMA' is added.
        Because EMA(EMA(EMA)) is used in the calculation, TEMA needs 3 * period - 2 samples to start producing values in contrast to the period samples
        needed by a regular EMA.
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def TRIMA(self, period: int = 18, **kwargs):
        """args:close,kwargs:filed
        The Triangular Moving Average (TRIMA) [also known as TMA] represents an average of prices,
        but places weight on the middle prices of the time period.
        The calculations double-smooth the data using a window width that is one-half the length of the series.
        source: https://www.thebalance.com/triangular-moving-average-tma-description-and-uses-1031203
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def TRIX(self, period: int = 20, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed
        The TRIX indicator calculates the rate of change of a triple exponential moving average.
        The values oscillate around zero. Buy/sell signals are generated when the TRIX crosses above/below zero.
        A (typically) 9 period exponential moving average of the TRIX can be used as a signal line.
        A buy/sell signals are generated when the TRIX crosses above/below the signal line and is also above/below zero.

        The TRIX was developed by Jack K. Hutson, publisher of Technical Analysis of Stocks & Commodities magazine,
        and was introduced in Volume 1, Number 5 of that magazine.
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def LWMA(self, period: int, **kwargs):
        """args:close,kwargs:filed
        Linear Weighted Moving Average
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def VAMA(self, period: int = 8, **kwargs):
        """args:ohlcv,kwargs:filed
        Volume Adjusted Moving Average
        """
        ...

    @tobtind(lib='finta')
    def VIDYA(self, period: int = 9, smoothing_period: int = 12, **kwargs):
        """args:close,kwargs:filed
        Vidya (variable index dynamic average) indicator is a modification of the traditional Exponential Moving Average (EMA) indicator.
        The main difference between EMA and Vidya is in the way the smoothing factor F is calculated.
        In EMA the smoothing factor is a constant value F=2/(period+1);
        in Vidya the smoothing factor is variable and depends on bar-to-bar price movements."""
        ...

    @tobtind(lib='finta')
    def ER(self, period: int = 10, **kwargs):
        """args:close,kwargs:filed
        The Kaufman Efficiency indicator is an oscillator indicator that oscillates between +100 and -100, where zero is the center point.
         +100 is upward forex trending market and -100 is downwards trending markets."""
        ...

    @tobtind(overlap=True, lib='finta')
    def KAMA(self, er: int = 10, ema_fast: int = 2, ema_slow: int = 30, period: int = 20, **kwargs):
        """args:close,kwargs:filed
        Developed by Perry Kaufman, Kaufman's Adaptive Moving Average (KAMA) is a moving average designed to account for market noise or volatility.
        Its main advantage is that it takes into consideration not just the direction, but the market volatility as well."""
        ...

    @tobtind(overlap=True, lib='finta')
    def ZLEMA(self, period: int = 26, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed
        ZLEMA is an abbreviation of Zero Lag Exponential Moving Average. It was developed by John Ehlers and Rick Way.
        ZLEMA is a kind of Exponential moving average but its main idea is to eliminate the lag arising from the very nature of the moving averages
        and other trend following indicators. As it follows price closer, it also provides better price averaging and responds better to price swings."""
        ...

    @tobtind(overlap=True, lib='finta')
    def WMA(self, period: int = 9, **kwargs):
        """args:close,kwargs:filed
        WMA stands for weighted moving average. It helps to smooth the price curve for better trend identification.
        It places even greater importance on recent data than the EMA does.

        :period: Specifies the number of Periods used for WMA calculation
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def HMA(self, period: int = 16, **kwargs):
        """args:close,kwargs:filed
        HMA indicator is a common abbreviation of Hull Moving Average.
        The average was developed by Allan Hull and is used mainly to identify the current market trend.
        Unlike SMA (simple moving average) the curve of Hull moving average is considerably smoother.
        Moreover, because its aim is to minimize the lag between HMA and price it does follow the price activity much closer.
        It is used especially for middle-term and long-term trading.
        :period: Specifies the number of Periods used for WMA calculation
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def EVWMA(self, period: int = 20, **kwargs):
        """args:ohlcv,kwargs:filed
        The eVWMA can be looked at as an approximation to the
        average price paid per share in the last n periods.

        :period: Specifies the number of Periods used for eVWMA calculation
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def VWAP(self, **kwargs):
        """args:ohlcv,kwargs:filed"""
        ...

    @tobtind(overlap=True, lib='finta')
    def SMMA(self, period: int = 42, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed
        The volume weighted average price (VWAP) is a trading benchmark used especially in pension plans.
        VWAP is calculated by adding up the dollars traded for every transaction (price multiplied by number of shares traded) and then dividing
        by the total shares traded for the day.
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def ALMA(self, period: int = 9, sigma: int = 6, offset: int = 0.85, **kwargs):
        """args:close,kwargs:filed
        Arnaud Legoux Moving Average."""

        """dataWindow = _.last(data, period)
        size = _.size(dataWindow)
        m = offset * (size - 1)
        s = size / sigma
        sum = 0
        norm = 0
        for i in [size-1..0] by -1
        coeff = Math.exp(-1 * (i - m) * (i - m) / 2 * s * s)
        sum = sum + dataWindow[i] * coeff
        norm = norm + coeff
        return sum / norm"""
        ...

    @tobtind(overlap=True, lib='finta')
    def MAMA(self, period: int = 16, **kwargs):
        """args:close,kwargs:filed
        MESA Adaptive Moving Average"""
        ...

    @tobtind(overlap=True, lib='finta')
    def FRAMA(self, period: int = 16, batch: int = 10, **kwargs):
        """args:close,kwargs:filed
        Fractal Adaptive Moving Average
        Source: http://www.stockspotter.com/Files/frama.pdf
        Adopted from: https://www.quantopian.com/posts/frama-fractal-adaptive-moving-average-in-python

        :period: Specifies the number of periods used for FRANA calculation
        :batch: Specifies the size of batches used for FRAMA calculation
        """
        ...

    @tobtind(lib='finta')
    def MACD(self, period_fast: int = 12, period_slow: int = 26, signal: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed
        MACD, MACD Signal and MACD difference.
        The MACD Line oscillates above and below the zero line, which is also known as the centerline.
        These crossovers signal that the 12-day EMA has crossed the 26-day EMA. The direction, of course, depends on the direction of the moving average cross.
        Positive MACD indicates that the 12-day EMA is above the 26-day EMA. Positive values increase as the shorter EMA diverges further from the longer EMA.
        This means upside momentum is increasing. Negative MACD values indicates that the 12-day EMA is below the 26-day EMA.
        Negative values increase as the shorter EMA diverges further below the longer EMA. This means downside momentum is increasing.

        Signal line crossovers are the most common MACD signals. The signal line is a 9-day EMA of the MACD Line.
        As a moving average of the indicator, it trails the MACD and makes it easier to spot MACD turns.
        A bullish crossover occurs when the MACD turns up and crosses above the signal line.
        A bearish crossover occurs when the MACD turns down and crosses below the signal line.
        """
        ...

    @tobtind(lib='finta')
    def PPO(self, period_fast: int = 12, period_slow: int = 26, signal: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed
        Percentage Price Oscillator
        PPO, PPO Signal and PPO difference.
        As with MACD, the PPO reflects the convergence and divergence of two moving averages.
        While MACD measures the absolute difference between two moving averages, PPO makes this a relative value by dividing the difference by the slower moving average
        """
        ...

    @tobtind(lib='finta')
    def VW_MACD(self, period_fast: int = 12, period_slow: int = 26, signal: int = 9, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed
        Volume-Weighted MACD" is an indicator that shows how a volume-weighted moving average can be used to calculate moving average convergence/divergence (MACD).
        This technique was first used by Buff Dormeier, CMT, and has been written about since at least 2002."""
        ...

    @tobtind(lib='finta')
    def EV_MACD(self, period_fast: int = 20, period_slow: int = 40, signal: int = 9, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed
        Elastic Volume Weighted MACD is a variation of standard MACD,
        calculated using two EVWMA's.

        :period_slow: Specifies the number of Periods used for the slow EVWMA calculation
        :period_fast: Specifies the number of Periods used for the fast EVWMA calculation
        :signal: Specifies the number of Periods used for the signal calculation
        """
        ...

    @tobtind(lib='finta')
    def MOM(self, period: int = 10, **kwargs):
        """args:close,kwargs:filed
        Market momentum is measured by continually taking price differences for a fixed time interval.
        To construct a 10-day momentum line, simply subtract the closing price 10 days ago from the last closing price.
        This positive or negative value is then plotted around a zero line."""
        ...

    @tobtind(lib='finta')
    def ROC(self, period: int = 12, **kwargs):
        """args:close,kwargs:filed
        The Rate-of-Change (ROC) indicator, which is also referred to as simply Momentum,
        is a pure momentum oscillator that measures the percent change in price from one period to the next.
        The ROC calculation compares the current price with the price “n” periods ago."""
        ...

    @tobtind(lib='finta')
    def VBM(self, roc_period: int = 12, atr_period: int = 26, **kwargs):
        """args:close,kwargs:filedThe Volatility-Based-Momentum (VBM) indicator, The calculation for a volatility based momentum (VBM)
        indicator is very similar to ROC, but divides by the security’s historical volatility instead.
        The average true range indicator (ATR) is used to compute historical volatility.
        VBM(n,v) = (Close — Close n periods ago) / ATR(v periods)
        """
        ...

    @tobtind(lib='finta')
    def RSI(self, period: int = 14, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed
        Relative Strength Index (RSI) is a momentum oscillator that measures the speed and change of price movements.
        RSI oscillates between zero and 100. Traditionally, and according to Wilder, RSI is considered overbought when above 70 and oversold when below 30.
        Signals can also be generated by looking for divergences, failure swings and centerline crossovers.
        RSI can also be used to identify the general trend."""
        ...

    @tobtind(lib='finta')
    def IFT_RSI(self, rsi_period: int = 5, wma_period: int = 9, **kwargs):
        """args:close,kwargs:filed
        Modified Inverse Fisher Transform applied on RSI.
        Suggested method to use any IFT indicator is to buy when the indicator crosses over –0.5 or crosses over +0.5
        if it has not previously crossed over –0.5 and to sell short when the indicators crosses under +0.5 or crosses under –0.5
        if it has not previously crossed under +0.5."""
        ...

    @tobtind(lib='finta')
    def SWI(self, period: int = 16, **kwargs):
        """args:close,kwargs:filed

        Sine Wave indicator"""
        ...

    @tobtind(lib='finta')
    def DYMI(self, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed

        The Dynamic Momentum Index is a variable term RSI. The RSI term varies from 3 to 30. The variable
        time period makes the RSI more responsive to short-term moves. The more volatile the price is,
        the shorter the time period is. It is interpreted in the same way as the RSI, but provides signals earlier.
        Readings below 30 are considered oversold, and levels over 70 are considered overbought. The indicator
        oscillates between 0 and 100.
        https://www.investopedia.com/terms/d/dynamicmomentumindex.asp
        """

    @tobtind(lib='finta')
    def TR(self, **kwargs):
        """args:ohlcv,kwargs:filed

        True Range is the maximum of three price ranges.
        Most recent period's high minus the most recent period's low.
        Absolute value of the most recent period's high minus the previous close.
        Absolute value of the most recent period's low minus the previous close."""
        ...

    @tobtind(lib='finta')
    def ATR(self, period: int = 14, **kwargs):
        """args:ohlcv,kwargs:filed

        Average True Range is moving average of True Range."""
        ...

    @tobtind(overlap=True, lib='finta')
    def SAR(self, af: int = 0.02, amax: int = 0.2, **kwargs):
        """args:ohlcv,kwargs:filed

        SAR stands for “stop and reverse,” which is the actual indicator used in the system.
        SAR trails price as the trend extends over time. The indicator is below prices when prices are rising and above prices when prices are falling.
        In this regard, the indicator stops and reverses when the price trend reverses and breaks above or below the indicator."""
        ...

    @tobtind(overlap=True, lib='finta')
    def PSAR(self, iaf: int = 0.02, maxaf: int = 0.2, **kwargs):
        """args:ohlcv,kwargs:filed

        The parabolic SAR indicator, developed by J. Wells Wilder, is used by traders to determine trend direction and potential reversals in price.
        The indicator uses a trailing stop and reverse method called "SAR," or stop and reverse, to identify suitable exit and entry points.
        Traders also refer to the indicator as the parabolic stop and reverse, parabolic SAR, or PSAR.
        https://www.investopedia.com/terms/p/parabolicindicator.asp
        https://virtualizedfrog.wordpress.com/2014/12/09/parabolic-sar-implementation-in-python/
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def BBANDS(self, period: int = 20, MA: series = None, std_multiplier: float = 2, **kwargs):
        """args:close,kwargs:filed

         Developed by John Bollinger, Bollinger Bands® are volatility bands placed above and below a moving average.
         Volatility is based on the standard deviation, which changes as volatility increases and decreases.
         The bands automatically widen when volatility increases and narrow when volatility decreases.

         This method allows input of some other form of moving average like EMA or KAMA around which BBAND will be formed.
         Pass desired moving average as <MA> argument. For example BBANDS(MA=TA.KAMA(20)).
         """
        ...

    @tobtind(lib='finta')
    def MOBO(self, period: int = 10, std_multiplier: float = 0.8, **kwargs):
        """args:close,kwargs:filed

        "MOBO bands are based on a zone of 0.80 standard deviation with a 10 period look-back"
        If the price breaks out of the MOBO band it can signify a trend move or price spike
        Contains 42% of price movements(noise) within bands.
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def BBWIDTH(self, period: int = 20, MA: series = None, **kwargs):
        """args:close,kwargs:filed

        Bandwidth tells how wide the Bollinger Bands are on a normalized basis."""
        ...

    @tobtind(lib='finta')
    def PERCENT_B(self, period: int = 20, MA: series = None, **kwargs):
        """args:close,kwargs:filed

        %b (pronounced 'percent b') is derived from the formula for Stochastics and shows where price is in relation to the bands.
        %b equals 1 at the upper band and 0 at the lower band.
        """
        ...

    @tobtind(lib='finta')
    def KC(self, period: int = 20, atr_period: int = 10, MA: series = None, kc_mult: float = 2, **kwargs):
        """args:ohlcv,kwargs:filed

        Keltner Channels [KC] are volatility-based envelopes set above and below an exponential moving average.
        This indicator is similar to Bollinger Bands, which use the standard deviation to set the bands.
        Instead of using the standard deviation, Keltner Channels use the Average True Range (ATR) to set channel distance.
        The channels are typically set two Average True Range values above and below the 20-day EMA.
        The exponential moving average dictates direction and the Average True Range sets channel width.
        Keltner Channels are a trend following indicator used to identify reversals with channel breakouts and channel direction.
        Channels can also be used to identify overbought and oversold levels when the trend is flat."""
        ...

    @tobtind(lib='finta')
    def DO(self, upper_period: int = 20, lower_period: int = 5, **kwargs):
        """args:ohlcv,kwargs:filed

        Donchian Channel, a moving average indicator developed by Richard Donchian.
        It plots the highest high and lowest low over the last period time intervals."""
        ...

    @tobtind(lib='finta')
    def DMI(self, period: int = 14, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed

        The directional movement indicator (also known as the directional movement index - DMI) is a valuable tool
         for assessing price direction and strength. This indicator was created in 1978 by J. Welles Wilder, who also created the popular
         relative strength index. DMI tells you when to be long or short.
         It is especially useful for trend trading strategies because it differentiates between strong and weak trends,
         allowing the trader to enter only the strongest trends.
        #CALCULATION
        source: https://www.tradingview.com/wiki/Directional_Movement_(DMI)

        :period: Specifies the number of Periods used for DMI calculation
        """
        ...

    @tobtind(lib='finta')
    def ADX(self, period: int = 14, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed

        The A.D.X. is 100 * smoothed moving average of absolute value (DMI +/-) divided by (DMI+ + DMI-). ADX does not indicate trend direction or momentum,
        only trend strength. Generally, A.D.X. readings below 20 indicate trend weakness,
        and readings above 40 indicate trend strength. An extremely strong trend is indicated by readings above 50"""
        ...

    @tobtind(lib='finta')
    def PIVOT(self, **kwargs):
        """args:ohlcv,kwargs:filed

        Pivot Points are significant support and resistance levels that can be used to determine potential trades.
        The pivot points come as a technical analysis indicator calculated using a financial instrument’s high, low, and close value.
        The pivot point’s parameters are usually taken from the previous day’s trading range.
        This means you’ll have to use the previous day’s range for today’s pivot points.
        Or, last week’s range if you want to calculate weekly pivot points or, last month’s range for monthly pivot points and so on.
        """
        ...

    @tobtind(lib='finta')
    def PIVOT_FIB(self, **kwargs):
        """args:ohlcv,kwargs:filed

        Fibonacci pivot point levels are determined by first calculating the classic pivot point,
        then multiply the previous day’s range with its corresponding Fibonacci level.
        Most traders use the 38.2%, 61.8% and 100% retracements in their calculations.
        """
        ...

    @tobtind(lib='finta')
    def STOCH(self, period: int = 14, **kwargs):
        """args:ohlcv,kwargs:filed

        Stochastic oscillator %K
         The stochastic oscillator is a momentum indicator comparing the closing price of a security
         to the range of its prices over a certain period of time.
         The sensitivity of the oscillator to market movements is reducible by adjusting that time
         period or by taking a moving average of the result.
        """
        ...

    @tobtind(lib='finta')
    def STOCHD(self, period: int = 3, stoch_period: int = 14, **kwargs):
        """args:ohlcv,kwargs:filed

        Stochastic oscillator %D
        STOCH%D is a 3 period simple moving average of %K.
        """
        ...

    @tobtind(lines=["STOCHRSI"], lib='finta')
    def STOCHRSI(self, rsi_period: int = 14, stoch_period: int = 14, **kwargs):
        """args:ohlcv,kwargs:filed

        StochRSI is an oscillator that measures the level of RSI relative to its high-low range over a set time period.
        StochRSI applies the Stochastics formula to RSI values, instead of price values. This makes it an indicator of an indicator.
        The result is an oscillator that fluctuates between 0 and 1."""
        ...

    @tobtind(lib='finta')
    def WILLIAMS(self, period: int = 14, **kwargs):
        """args:ohlcv,kwargs:filed

        Williams %R, or just %R, is a technical analysis oscillator showing the current closing price in relation to the high and low
         of the past N days (for a given N). It was developed by a publisher and promoter of trading materials, Larry Williams.
         Its purpose is to tell whether a stock or commodity market is trading near the high or the low, or somewhere in between,
         of its recent trading range.
         The oscillator is on a negative scale, from −100 (lowest) up to 0 (highest).
        """
        ...

    @tobtind(lib='finta')
    def UO(self, **kwargs):
        """args:close,kwargs:filed

        Ultimate Oscillator is a momentum oscillator designed to capture momentum across three different time frames.
        The multiple time frame objective seeks to avoid the pitfalls of other oscillators.
        Many momentum oscillators surge at the beginning of a strong advance and then form bearish divergence as the advance continues.
        This is because they are stuck with one time frame. The Ultimate Oscillator attempts to correct this fault by incorporating longer
        time frames into the basic formula."""
        ...

    @tobtind(lib='finta')
    def AO(self, slow_period: int = 34, fast_period: int = 5, **kwargs):
        """args:ohlcv,kwargs:filed

        Awesome Oscillator is an indicator used to measure market momentum. AO calculates the difference of a 34 Period and 5 Period Simple Moving Averages.
        The Simple Moving Averages that are used are not calculated using closing price but rather each bar's midpoints.
        AO is generally used to affirm trends or to anticipate possible reversals. """
        ...

    @tobtind(lib='finta')
    def MI(self, period: int = 9, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed

        Developed by Donald Dorsey, the Mass Index uses the high-low range to identify trend reversals based on range expansions.
        In this sense, the Mass Index is a volatility indicator that does not have a directional bias.
        Instead, the Mass Index identifies range bulges that can foreshadow a reversal of the current trend."""
        ...

    @tobtind(lib='finta')
    def BOP(self, **kwargs):
        """args:ohlcv,kwargs:filed

        Balance Of Power indicator"""
        ...

    @tobtind(lib='finta')
    def VORTEX(self, period: int = 14, **kwargs):
        """args:ohlcv,kwargs:filed

        The Vortex indicator plots two oscillating lines, one to identify positive trend movement and the other
         to identify negative price movement.
         Indicator construction revolves around the highs and lows of the last two days or periods.
         The distance from the current high to the prior low designates positive trend movement while the
         distance between the current low and the prior high designates negative trend movement.
         Strongly positive or negative trend movements will show a longer length between the two numbers while
         weaker positive or negative trend movement will show a shorter length."""
        ...

    @tobtind(lib='finta')
    def KST(self, r1: int = 10, r2: int = 15, r3: int = 20, r4: int = 30, **kwargs):
        """args:ohlcv,kwargs:filed

        Know Sure Thing (KST) is a momentum oscillator based on the smoothed rate-of-change for four different time frames.
        KST measures price momentum for four different price cycles. It can be used just like any momentum oscillator.
        Chartists can look for divergences, overbought/oversold readings, signal line crossovers and centerline crossovers."""
        ...

    @tobtind(lib='finta')
    def TSI(self, long: int = 25, short: int = 13, signal: int = 13, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed

        True Strength Index (TSI) is a momentum oscillator based on a double smoothing of price changes."""
        ...

    @tobtind(lib='finta')
    def TP(self, **kwargs):
        """args:ohlcv,kwargs:filed

        Typical Price refers to the arithmetic average of the high, low, and closing prices for a given period."""
        ...

    @tobtind(lib='finta')
    def ADL(self, **kwargs):
        """args:ohlcv,kwargs:filed

        The accumulation/distribution line was created by Marc Chaikin to determine the flow of money into or out of a security.
        It should not be confused with the advance/decline line. While their initials might be the same, these are entirely different indicators,
        and their uses are different as well. Whereas the advance/decline line can provide insight into market movements,
        the accumulation/distribution line is of use to traders looking to measure buy/sell pressure on a security or confirm the strength of a trend."""
        ...

    @tobtind(lib='finta')
    def CHAIKIN(self, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed

        Chaikin Oscillator, named after its creator, Marc Chaikin, the Chaikin oscillator is an oscillator that measures the accumulation/distribution
         line of the moving average convergence divergence (MACD). The Chaikin oscillator is calculated by subtracting a 10-day exponential moving average (EMA)
         of the accumulation/distribution line from a three-day EMA of the accumulation/distribution line, and highlights the momentum implied by the
         accumulation/distribution line."""
        ...

    @tobtind(lib='finta')
    def MFI(self, period: int = 14, **kwargs):
        """args:ohlcv,kwargs:filed

        The money flow index (MFI) is a momentum indicator that measures
        the inflow and outflow of money into a security over a specific period of time.
        MFI can be understood as RSI adjusted for volume.
        The money flow indicator is one of the more reliable indicators of overbought and oversold conditions, perhaps partly because
        it uses the higher readings of 80 and 20 as compared to the RSI's overbought/oversold readings of 70 and 30"""
        ...

    @tobtind(lib='finta')
    def OBV(self, **kwargs):
        """args:close,kwargs:filed

        On Balance Volume (OBV) measures buying and selling pressure as a cumulative indicator that adds volume on up days and subtracts volume on down days.
        OBV was developed by Joe Granville and introduced in his 1963 book, Granville's New Key to Stock Market Profits.
        It was one of the first indicators to measure positive and negative volume flow.
        Chartists can look for divergences between OBV and price to predict price movements or use OBV to confirm price trends.

        source: https://en.wikipedia.org/wiki/On-balance_volume#The_formula

        :param pd.DataFrame ohlc: 'open, high, low, close' pandas DataFrame
        :return pd.Series: result is pandas.Series
        """
        ...

    @tobtind(lib='finta')
    def WOBV(self, **kwargs):
        """args:ohlcv,kwargs:filed

        Weighted OBV
        Can also be seen as an OBV indicator that takes the price differences into account.
        In a regular OBV, a high volume bar can make a huge difference,
        even if the price went up only 0.01, and it it goes down 0.01
        instead, that huge volume makes the OBV go down, even though
        hardly anything really happened.
        """
        ...

    @tobtind(lib='finta')
    def VZO(self, period: int = 14, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed

        VZO uses price, previous price and moving averages to compute its oscillating value.
        It is a leading indicator that calculates buy and sell signals based on oversold / overbought conditions.
        Oscillations between the 5% and 40% levels mark a bullish trend zone, while oscillations between -40% and 5% mark a bearish trend zone.
        Meanwhile, readings above 40% signal an overbought condition, while readings above 60% signal an extremely overbought condition.
        Alternatively, readings below -40% indicate an oversold condition, which becomes extremely oversold below -60%."""
        ...

    @tobtind(lib='finta')
    def PZO(self, period: int = 14, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed

        The formula for PZO depends on only one condition: if today's closing price is higher than yesterday's closing price,
        then the closing price will have a positive value (bullish); otherwise it will have a negative value (bearish).
        source: http://traders.com/Documentation/FEEDbk_docs/2011/06/Khalil.html

        :period: Specifies the number of Periods used for PZO calculation
        """
        ...

    @tobtind(lib='finta')
    def EFI(self, period: int = 13, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed

        Elder's Force Index is an indicator that uses price and volume to assess the power
         behind a move or identify possible turning points."""
        ...

    @tobtind(lib='finta')
    def CFI(self, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed

        Cummulative Force Index.
        Adopted from  Elder's Force Index.
        """
        ...

    @tobtind(lib='finta')
    def EBBP(self, **kwargs):
        """args:ohlcv,kwargs:filed

        Bull power and bear power by Dr. Alexander Elder show where today’s high and low lie relative to the a 13-day EMA"""
        ...

    @tobtind(lib='finta')
    def EMV(self, period: int = 14, **kwargs):
        """args:ohlcv,kwargs:filed

        Ease of Movement (EMV) is a volume-based oscillator that fluctuates above and below the zero line.
        As its name implies, it is designed to measure the 'ease' of price movement.
        prices are advancing with relative ease when the oscillator is in positive territory.
        Conversely, prices are declining with relative ease when the oscillator is in negative territory."""
        ...

    @tobtind(lib='finta')
    def CCI(self, period: int = 20, constant: float = 0.015, **kwargs):
        """args:ohlcv,kwargs:filed

        Commodity Channel Index (CCI) is a versatile indicator that can be used to identify a new trend or warn of extreme conditions.
        CCI measures the current price level relative to an average price level over a given period of time.
        The CCI typically oscillates above and below a zero line. Normal oscillations will occur within the range of +100 and −100.
        Readings above +100 imply an overbought condition, while readings below −100 imply an oversold condition.
        As with other overbought/oversold indicators, this means that there is a large probability that the price will correct to more representative levels.

        source: https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:commodity_channel_index_cci

        :param pd.DataFrame ohlc: 'open, high, low, close' pandas DataFrame
        :period: int - number of periods to take into consideration
        :factor float: the constant at .015 to ensure that approximately 70 to 80 percent of CCI values would fall between -100 and +100.
        :return pd.Series: result is pandas.Series
        """
        ...

    @tobtind(lib='finta')
    def COPP(self, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed

        The Coppock Curve is a momentum indicator, it signals buying opportunities when the indicator moved from negative territory to positive territory."""
        ...

    @tobtind(lib='finta')
    def BASP(self, period: int = 40, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed

        BASP indicator serves to identify buying and selling pressure."""
        ...

    @tobtind(lib='finta')
    def BASPN(self, period: int = 40, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed

        Normalized BASP indicator
        """
        ...

    @tobtind(lib='finta')
    def CMO(self, period: int = 9, factor: int = 100, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed

        Chande Momentum Oscillator (CMO) - technical momentum indicator invented by the technical analyst Tushar Chande.
        It is created by calculating the difference between the sum of all recent gains and the sum of all recent losses and then
        dividing the result by the sum of all price movement over the period.
        This oscillator is similar to other momentum indicators such as the Relative Strength Index and the Stochastic Oscillator
        because it is range bounded (+100 and -100)."""
        ...

    @tobtind(lib='finta')
    def CHANDELIER(self, short_period: int = 22, long_period: int = 22, k: int = 3, **kwargs):
        """args:ohlcv,kwargs:filed

        Chandelier Exit sets a trailing stop-loss based on the Average True Range (ATR).

        The indicator is designed to keep traders in a trend and prevent an early exit as long as the trend extends.

        Typically, the Chandelier Exit will be above prices during a downtrend and below prices during an uptrend.
        """
        ...

    @tobtind(lib='finta')
    def QSTICK(self, period: int = 14, **kwargs):
        """args:ohlcv,kwargs:filed

        QStick indicator shows the dominance of black (down) or white (up) candlesticks, which are red and green in Chart,
        as represented by the average open to close change for each of past N days."""
        ...

    @tobtind(lib='finta')
    def TMF(self, period: int = 21, **kwargs):
        """args:ohlcv,kwargs:filed

        Indicator by Colin Twiggs which improves upon CMF.
        source: https://user42.tuxfamily.org/chart/manual/Twiggs-Money-Flow.html"""
        ...

    @tobtind(lib='finta')
    def WTO(self, channel_length: int = 10, average_length: int = 21, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed

        Wave Trend Oscillator
        source: http://www.fxcoaching.com/WaveTrend/
        """
        ...

    @tobtind(lib='finta')
    def FISH(self, period: int = 10, adjust: bool = True, **kwargs):
        """
        args:ohlcv,kwargs:filed

        Fisher Transform was presented by John Ehlers. It assumes that price distributions behave like square waves.
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def ICHIMOKU(self, tenkan_period: int = 9, kijun_period: int = 26, senkou_period: int = 52, chikou_period: int = 26, **kwargs):
        """args:ohlcv,kwargs:filed

        The Ichimoku Cloud, also known as Ichimoku Kinko Hyo, is a versatile indicator that defines support and resistance,
        identifies trend direction, gauges momentum and provides trading signals.

        Ichimoku Kinko Hyo translates into “one look equilibrium chart”.
        """
        ...

    @tobtind(lib='finta')
    def APZ(self, period: int = 21, dev_factor: int = 2, MA: series = None, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed

        The adaptive price zone (APZ) is a technical indicator developed by Lee Leibfarth.

        The APZ is a volatility based indicator that appears as a set of bands placed over a price chart.

        Especially useful in non-trending, choppy markets,

        the APZ was created to help traders find potential turning points in the markets.
        """
        ...

    @tobtind(lib='finta')
    def SQZMI(self, period: int = 20, MA: series = None, **kwargs):
        """args:ohlcv,kwargs:filed

        Squeeze Momentum Indicator

        The Squeeze indicator attempts to identify periods of consolidation in a market.
        In general the market is either in a period of quiet consolidation or vertical price discovery.
        By identifying these calm periods, we have a better opportunity of getting into trades with the potential for larger moves.
        Once a market enters into a “squeeze”, we watch the overall market momentum to help forecast the market direction and await a release of market energy.

        :param pd.DataFrame ohlc: 'open, high, low, close' pandas DataFrame
        :period: int - number of periods to take into consideration
        :MA pd.Series: override internal calculation which uses SMA with moving average of your choice
        :return pd.Series: indicator calcs as pandas Series

        SQZMI['SQZ'] is bool True/False, if True squeeze is on. If false, squeeeze has fired.
        """
        ...

    @tobtind(lib='finta')
    def VPT(self, **kwargs):
        """args:ohlcv,kwargs:filed

        Volume Price Trend
        The Volume Price Trend uses the difference of price and previous price with volume and feedback to arrive at its final form.
        If there appears to be a bullish divergence of price and the VPT (upward slope of the VPT and downward slope of the price) a buy opportunity exists.
        Conversely, a bearish divergence (downward slope of the VPT and upward slope of the price) implies a sell opportunity.
        """
        ...

    @tobtind(lib='finta')
    def FVE(self, period: int = 22, factor: int = 0.3, **kwargs):
        """args:ohlcv,kwargs:filed

        FVE is a money flow indicator, but it has two important innovations: first, the F VE takes into account both intra and
        interday price action, and second, minimal price changes are taken into account by introducing a price threshold.
        """
        ...

    @tobtind(lib='finta')
    def VFI(self, period: int = 130, smoothing_factor: int = 3, factor: int = 0.2, vfactor: int = 2.5, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed

        This indicator tracks volume based on the direction of price
        movement. It is similar to the On Balance Volume Indicator.
        For more information see "Using Money Flow to Stay with the Trend",
        and "Volume Flow Indicator Performance" in the June 2004 and
        July 2004 editions of Technical Analysis of Stocks and Commodities.

        :period: Specifies the number of Periods used for VFI calculation
        :factor: Specifies the fixed scaling factor for the VFI calculation
        :vfactor: Specifies the cutoff for maximum volume in the VFI calculation
        :smoothing_factor: Specifies the number of periods used in the short moving average
        """
        ...

    @tobtind(lib='finta')
    def MSD(self, period: int = 21, **kwargs):
        """args:close,kwargs:filed

        Standard deviation is a statistical term that measures the amount of variability or dispersion around an average.
        Standard deviation is also a measure of volatility. Generally speaking, dispersion is the difference between the actual value and the average value.
        The larger this dispersion or variability is, the higher the standard deviation.
        Standard Deviation values rise significantly when the analyzed contract of indicator change in value dramatically.
        When markets are stable, low Standard Deviation readings are normal.
        Low Standard Deviation readings typically tend to come before significant upward changes in price.
        Analysts generally agree that high volatility is part of major tops, while low volatility accompanies major bottoms.

        :period: Specifies the number of Periods used for MSD calculation
        """
        ...

    @tobtind(lib='finta')
    def STC(self, period_fast: int = 23, period_slow: int = 50, k_period: int = 10, d_period: int = 3, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed

        The Schaff Trend Cycle (Oscillator) can be viewed as Double Smoothed
        Stochastic of the MACD.

        Schaff Trend Cycle - Three input values are used with the STC:
        – Sh: shorter-term Exponential Moving Average with a default period of 23
        – Lg: longer-term Exponential Moving Average with a default period of 50
        – Cycle, set at half the cycle length with a default value of 10. (Stoch K-period)
        - Smooth, set at smoothing at 3 (Stoch D-period)

        The STC is calculated in the following order:
        EMA1 = EMA (Close, fast_period);
        EMA2 = EMA (Close, slow_period);
        MACD = EMA1 – EMA2.
        Second, the 10-period Stochastic from the MACD values is calculated:
        STOCH_K, STOCH_D  = StochasticFull(MACD, k_period, d_period)  // Stoch of MACD
        STC =  average(STOCH_D, d_period) // second smoothed

        In case the STC indicator is decreasing, this indicates that the trend cycle
        is falling, while the price tends to stabilize or follow the cycle to the downside.
        In case the STC indicator is increasing, this indicates that the trend cycle
        is up, while the price tends to stabilize or follow the cycle to the upside.
        """
        ...

    @tobtind(lib='finta')
    def EVSTC(self, period_fast: int = 12, period_slow: int = 30, k_period: int = 10, d_period: int = 3, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed
        Modification of Schaff Trend Cycle using EVWMA MACD for calculation"""
        ...

    @tobtind(lib='finta')
    def WILLIAMS_FRACTAL(self, period: int = 2, **kwargs):
        """args:ohlcv,kwargs:filed

        Williams Fractal Indicator
        Source: https://www.investopedia.com/terms/f/fractal.asp

        :param DataFrame ohlc: data
        :param int period: how many lower highs/higher lows the extremum value should be preceded and followed.
        :return DataFrame: fractals identified by boolean
        """
        ...

    @tobtind(lib='finta')
    def VC(self, period: int = 5, **kwargs):
        """args:ohlcv,kwargs:filed"""
        ...

    @tobtind(lib='finta')
    def WAVEPM(self, period: int = 14, lookback_period: int = 100, **kwargs):
        """args:ohlcv,kwargs:filed"""
        ...


class AutoTrader:
    """AutoTrader指标指引"""
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    @tobtind(lines=["uptrend", "downtrend", "trend"], overlap=True, lib="autotrader")
    def supertrend(self, period: int = 10, multiplier: float = 3.0, source: pd.Series = None, **kwargs) -> dataframe:
        """args:ohlcv
        lines:uptrend,downtrend,trend
        """
        ...

    def halftrend(self, amplitude: int = 2, channel_deviation: float = 2, **kwargs):
        """args:ohlcv
        lines:halftrend,atrHigh,atrLow,buy,sell
        """
        ...

    def range_filter(self, range_qty: float = 2.618, range_period: int = 14, smooth_range: bool = True, smooth_period: int = 27,
                     av_vals: bool = False, av_samples: int = 2, mov_source: str = "body", filter_type: int = 1, **kwargs):
        """args:ohlcv
        lines:upper,lower,rf,fdir
        """
        ...

    def bullish_engulfing(self, detection: str = None, **kwargs):
        """args:ohlcv
        detection:SMA50,SMA50/200
        """
        ...

    def bearish_engulfing(self, detection: str = None, **kwargs):
        """args:ohlcv
        detection:SMA50,SMA50/200
        """
        ...

    def find_swings(self, n: int = 2, **kwargs):
        """args:ohlcv
        lines:Highs,Lows,Last,Trend
        """
        ...

    def classify_swings(self, tol: int = 0, **kwargs):
        """args:swing_df  The dataframe returned by self.data.find_swings.
        lines:CSLS,Support,Resistance,Strong_lows,Strong_highs,FSL,FSH,LL,HL,HH,LH
        """
        ...

    def detect_divergence(self, classified_price_swings: pd.DataFrame, classified_indicator_swings: pd.DataFrame, tol: int = 2, method: int = 0, **kwargs):
        """
        classified_price_swings : pd.DataFrame
            The output from classify_swings using OHLC data.

        classified_indicator_swings : pd.DataFrame
            The output from classify_swings using indicator data.
        lines:regularBull,regularBear,hiddenBull,hiddenBear
        """
        # data = self._finta_get_data(**kwargs)
        ...

    def autodetect_divergence(self, indicator_data: pd.DataFrame, tolerance: int = 1, method: int = 0, **kwargs):
        """args:ohlcv
        indicator_data:dataframe of indicator data. self.data.detect_divergence
        lines:regularBull,regularBear,hiddenBull,hiddenBear
        """
        ...

    def heikin_ashi(self, **kwargs):
        """args:ohlcv
        lines:open,high,low,close
        """
        ...

    def ha_candle_run(self, **kwargs):
        """args:ha_data
        lines:up,dn
        """
        ...

    def N_period_high(self, N: int, **kwargs):
        """args:high"""
        ...

    def N_period_low(self, N: int, **kwargs):
        """args: low."""
        ...

    def crossover(self, ts2: pd.Series, **kwargs):
        """args:close
        """
        ...

    def cross_values(self, ts2: pd.Series, **kwargs):
        """args:close
        """
        ...

    def candles_between_crosses(self, crosses: Union[list, pd.Series], initial_count: int = 0, **kwargs):
        """args:None
        """
        ...

    def rolling_signal_list(self, signals: Union[list, pd.Series], **kwargs):
        """args:None

        """
        ...

    def unroll_signal_list(self, signals: Union[list, pd.Series], **kwargs):
        """args:None
        """
        ...

    def merge_signals(self, signal_1: list, signal_2: list, **kwargs):
        """args:None
        """
        ...

    def build_grid_price_levels(self, grid_origin: float, grid_space: float, grid_levels: int, grid_price_space: float = None, pip_value: float = 0.0001, **kwargs) -> np.array:
        """Generates grid price levels."""
        ...

    def build_grid(self, grid_origin: float, grid_space: float, grid_levels: int, order_direction: int, order_type: str = "stop-limit",
                   grid_price_space: float = None, pip_value: float = 0.0001, take_distance: float = None, stop_distance: float = None, stop_type: str = None, **kwargs) -> dict:
        """Generates a grid of orders.
        dict:dict[int,dict]"""
        ...

    def merge_grid_orders(self, grid_1: np.array, grid_2: np.array, **kwargs) -> np.array:
        """Merges grid dictionaries into one and re-labels order numbers so each
        order number is unique.
        """
        ...

    def last_level_crossed(self, base: float, **kwargs):
        """args:ohlcv"""
        ...

    def build_multiplier_grid(self, origin: float, direction: int, multiplier: float, no_levels: int, precision: int, spacing: float, **kwargs):
        """args:None
        """
        ...

    def last_level_touched(self, grid: np.array, **kwargs) -> np.array:
        """args:ohlcv"""
        ...

    def stoch_rsi(self, K_period: int = 3, D_period: int = 3, RSI_length: int = 14, Stochastic_length: int = 14, **kwargs):
        """args:ohlcv
        lines:k,d"""
        ...

    def stochastic(self, period: int = 14, **kwargs) -> pd.Series:
        """args:ohlcv"""
        ...

    def sma(self, period: int = 14, **kwargs):
        """args:close"""
        ...

    def ema(self, period: int = 14, smoothing: int = 2, **kwargs):
        """args:close"""
        ...

    def true_range(self, period: int = 14, **kwargs):
        """args:ohlcv"""
        ...

    def atr(self, period: int = 14, **kwargs):
        """args:ohlcv"""
        ...

    def create_bricks(self, brick_size: float = 0.002, column: str = "close", **kwargs):
        """args:ohlcw
        lines:open,close"""
        ...

    def chandelier_exit(self, length: int = 22, mult: float = 3.0, use_close: bool = False, **kwargs):
        """args:ohlcv
        lines:longstop,shortstop,direction,signal"""
        ...


class SignalFeatures:
    """特征工程指标指引"""
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    @tobtind(lib="sf")
    def Binarizer(self, y: Optional[Iterable] = None, threshold: float = 0.0, copy: bool = True, fit_params: dict = {}, **kwargs) -> series | dataframe:
        """Binarize data (set feature values to 0 or 1) according to a threshold.

        Values greater than the threshold map to 1, while values less than
        or equal to the threshold map to 0. With the default threshold of 0,
        only positive values map to 1.

        Binarization is a common operation on text count data where the
        analyst can decide to only consider the presence or absence of a
        feature rather than a quantified number of occurrences for instance.

        It can also be used as a pre-processing step for estimators that
        consider boolean random variables (e.g. modelled using the Bernoulli
        distribution in a Bayesian setting).

        Read more in the :ref:`User Guide <preprocessing_binarization>`.

        Parameters
        ----------
        threshold : float, default=0.0
            Feature values below or equal to this are replaced by 0, above it by 1.
            Threshold may not be less than 0 for operations on sparse matrices.

        copy : bool, default=True
            Set to False to perform inplace binarization and avoid a copy (if
            the input is already a numpy array or a scipy.sparse CSR matrix).

        Attributes
        ----------
        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        See Also
        --------
        binarize : Equivalent function without the estimator API.
        KBinsDiscretizer : Bin continuous data into intervals.
        OneHotEncoder : Encode categorical features as a one-hot numeric array.

        Notes
        -----
        If the input is a sparse matrix, only the non-zero values are subject
        to update by the Binarizer class.

        This estimator is stateless (besides constructor parameters), the
        fit method does nothing but is useful when used in a pipeline.

        Examples
        --------
        >>> from sklearn.preprocessing import Binarizer
        >>> X = [[ 1., -1.,  2.],
        ...      [ 2.,  0.,  0.],
        ...      [ 0.,  1., -1.]]
        >>> transformer = Binarizer().fit(X)  # fit does nothing.
        >>> transformer
        Binarizer()
        >>> transformer.transform(X)
            array([[1., 0., 1.],
                [1., 0., 0.],
                [0., 1., 0.]])
            """
        ...

        @tobtind(lib="sf")
        def FunctionTransformer(
            self,
            y: Optional[Iterable] = None,
            func: Callable = None,
            inverse_func: Callable = None,
            validate: bool = False,
            accept_sparse: bool = False,
            check_inverse: bool = True,
            feature_names_out: Optional[str] = None,
            kw_args: Optional[dict] = None,
            inv_kw_args: Optional[dict] = None,
            fit_params: dict = {},
            **kwargs
        ) -> series | dataframe:
            """Constructs a transformer from an arbitrary callable.

            A FunctionTransformer forwards its X (and optionally y) arguments to a
            user-defined function or function object and returns the result of this
            function. This is useful for stateless transformations such as taking the
            log of frequencies, doing custom scaling, etc.

            Note: If a lambda is used as the function, then the resulting
            transformer will not be pickleable.

            .. versionadded:: 0.17

            Read more in the :ref:`User Guide <function_transformer>`.

            Parameters
            ----------
            func : callable, default=None
                The callable to use for the transformation. This will be passed
                the same arguments as transform, with args and kwargs forwarded.
                If func is None, then func will be the identity function.

            inverse_func : callable, default=None
                The callable to use for the inverse transformation. This will be
                passed the same arguments as inverse transform, with args and
                kwargs forwarded. If inverse_func is None, then inverse_func
                will be the identity function.

            validate : bool, default=False
                Indicate that the input X array should be checked before calling
                ``func``. The possibilities are:

                - If False, there is no input validation.
                - If True, then X will be converted to a 2-dimensional NumPy array or
                sparse matrix. If the conversion is not possible an exception is
                raised.

                .. versionchanged:: 0.22
                The default of ``validate`` changed from True to False.

            accept_sparse : bool, default=False
                Indicate that func accepts a sparse matrix as input. If validate is
                False, this has no effect. Otherwise, if accept_sparse is false,
                sparse matrix inputs will cause an exception to be raised.

            check_inverse : bool, default=True
            Whether to check that or ``func`` followed by ``inverse_func`` leads to
            the original inputs. It can be used for a sanity check, raising a
            warning when the condition is not fulfilled.

            .. versionadded:: 0.20

            feature_names_out : callable, 'one-to-one' or None, default=None
                Determines the list of feature names that will be returned by the
                `get_feature_names_out` method. If it is 'one-to-one', then the output
                feature names will be equal to the input feature names. If it is a
                callable, then it must take two positional arguments: this
                `FunctionTransformer` (`self`) and an array-like of input feature names
                (`input_features`). It must return an array-like of output feature
                names. The `get_feature_names_out` method is only defined if
                `feature_names_out` is not None.

                See ``get_feature_names_out`` for more details.

                .. versionadded:: 1.1

            kw_args : dict, default=None
                Dictionary of additional keyword arguments to pass to func.

                .. versionadded:: 0.18

            inv_kw_args : dict, default=None
                Dictionary of additional keyword arguments to pass to inverse_func.

                .. versionadded:: 0.18

            Attributes
            ----------
            n_features_in_ : int
                Number of features seen during :term:`fit`. Defined only when
                `validate=True`.

                .. versionadded:: 0.24

            feature_names_in_ : ndarray of shape (`n_features_in_`,)
                Names of features seen during :term:`fit`. Defined only when `validate=True`
                and `X` has feature names that are all strings.

                .. versionadded:: 1.0

            See Also
            --------
            MaxAbsScaler : Scale each feature by its maximum absolute value.
            StandardScaler : Standardize features by removing the mean and
                scaling to unit variance.
            LabelBinarizer : Binarize labels in a one-vs-all fashion.
            MultiLabelBinarizer : Transform between iterable of iterables
                and a multilabel format.

            Examples
            --------
            >>> import numpy as np
            >>> from sklearn.preprocessing import FunctionTransformer
            >>> transformer = FunctionTransformer(np.log1p)
            >>> X = np.array([[0, 1], [2, 3]])
            >>> transformer.transform(X)
                array([[0.       , 0.6931...],
                    [1.0986..., 1.3862...]])
            """
        ...

    @tobtind(lib="sf")
    def KBinsDiscretizer(
        self,
        y: Optional[Iterable] = None,
        n_bins=5,
        encode: Literal['onehot', 'onehot-dense', 'ordinal'] = "onehot",
        strategy: Literal['uniform', 'quantile', 'kmeans'] = "quantile",
        dtype: Optional[float] = None,
        subsample: Optional[Union[int, Literal['warn']]] = "warn",
        random_state: Optional[Union[int, RandomState]] = None,
        fit_params: dict = {},
        **kwargs
    ) -> series | dataframe:
        """
        Bin continuous data into intervals.

        Read more in the :ref:`User Guide <preprocessing_discretization>`.

        .. versionadded:: 0.20

        Parameters
        ----------
        n_bins : int or array-like of shape (n_features,), default=5
            The number of bins to produce. Raises ValueError if ``n_bins < 2``.

        encode : {'onehot', 'onehot-dense', 'ordinal'}, default='onehot'
            Method used to encode the transformed result.

            - 'onehot': Encode the transformed result with one-hot encoding
            and return a sparse matrix. Ignored features are always
            stacked to the right.
            - 'onehot-dense': Encode the transformed result with one-hot encoding
            and return a dense array. Ignored features are always
            stacked to the right.
            - 'ordinal': Return the bin identifier encoded as an integer value.

        strategy : {'uniform', 'quantile', 'kmeans'}, default='quantile'
            Strategy used to define the widths of the bins.

            - 'uniform': All bins in each feature have identical widths.
            - 'quantile': All bins in each feature have the same number of points.
            - 'kmeans': Values in each bin have the same nearest center of a 1D
            k-means cluster.

        dtype : {np.float32, np.float64}, default=None
            The desired data-type for the output. If None, output dtype is
            consistent with input dtype. Only np.float32 and np.float64 are
            supported.

            .. versionadded:: 0.24

        subsample : int or None (default='warn')
            Maximum number of samples, used to fit the model, for computational
            efficiency. Used when `strategy="quantile"`.
            `subsample=None` means that all the training samples are used when
            computing the quantiles that determine the binning thresholds.
            Since quantile computation relies on sorting each column of `X` and
            that sorting has an `n log(n)` time complexity,
            it is recommended to use subsampling on datasets with a
            very large number of samples.

            .. deprecated:: 1.1
            In version 1.3 and onwards, `subsample=2e5` will be the default.

        random_state : int, RandomState instance or None, default=None
            Determines random number generation for subsampling.
            Pass an int for reproducible results across multiple function calls.
            See the `subsample` parameter for more details.
            See :term:`Glossary <random_state>`.

            .. versionadded:: 1.1

        Attributes
        ----------
        bin_edges_ : ndarray of ndarray of shape (n_features,)
            The edges of each bin. Contain arrays of varying shapes ``(n_bins_, )``
            Ignored features will have empty arrays.

        n_bins_ : ndarray of shape (n_features,), dtype=np.int_
            Number of bins per feature. Bins whose width are too small
            (i.e., <= 1e-8) are removed with a warning.

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        See Also
        --------
        Binarizer : Class used to bin values as ``0`` or
            ``1`` based on a parameter ``threshold``.

        Notes
        -----
        In bin edges for feature ``i``, the first and last values are used only for
        ``inverse_transform``. During transform, bin edges are extended to::

        np.concatenate([-np.inf, bin_edges_[i][1:-1], np.inf])

        You can combine ``KBinsDiscretizer`` with
        :class:`~sklearn.compose.ColumnTransformer` if you only want to preprocess
        part of the features.

        ``KBinsDiscretizer`` might produce constant features (e.g., when
        ``encode = 'onehot'`` and certain bins do not contain any data).
        These features can be removed with feature selection algorithms
        (e.g., :class:`~sklearn.feature_selection.VarianceThreshold`).

        Examples
        --------
        >>> from sklearn.preprocessing import KBinsDiscretizer
        >>> X = [[-2, 1, -4,   -1],
        ...      [-1, 2, -3, -0.5],
        ...      [ 0, 3, -2,  0.5],
        ...      [ 1, 4, -1,    2]]
        >>> est = KBinsDiscretizer(n_bins=3, encode='ordinal', strategy='uniform')
        >>> est.fit(X)
        KBinsDiscretizer(...)
        >>> Xt = est.transform(X)
        >>> Xt  # doctest: +SKIP
            array([[ 0., 0., 0., 0.],
                [ 1., 1., 1., 0.],
                [ 2., 2., 2., 1.],
                [ 2., 2., 2., 2.]])

        Sometimes it may be useful to convert the data back into the original
        feature space. The ``inverse_transform`` function converts the binned
        data into the original feature space. Each value will be equal to the mean
        of the two bin edges.

        >>> est.bin_edges_[0]
            array([-2., -1.,  0.,  1.])
        >>> est.inverse_transform(Xt)
            array([[-1.5,  1.5, -3.5, -0.5],
                [-0.5,  2.5, -2.5, -0.5],
                [ 0.5,  3.5, -1.5,  0.5],
                [ 0.5,  3.5, -1.5,  1.5]])
            """
        ...

    @tobtind(lib="sf")
    def KernelCenterer(self, y: Optional[Iterable] = None, fit_params: dict = {}, **kwargs) -> series | dataframe:
        """Center an arbitrary kernel matrix :math:`K`.

        Let define a kernel :math:`K` such that:

        .. math::
            K(X, Y) = \phi(X) . \phi(Y)^{T}

        :math:`\phi(X)` is a function mapping of rows of :math:`X` to a
        Hilbert space and :math:`K` is of shape `(n_samples, n_samples)`.

        This class allows to compute :math:`\tilde{K}(X, Y)` such that:

        .. math::
            \tilde{K(X, Y)} = \tilde{\phi}(X) . \tilde{\phi}(Y)^{T}

        :math:`\tilde{\phi}(X)` is the centered mapped data in the Hilbert
        space.

        `KernelCenterer` centers the features without explicitly computing the
        mapping :math:`\phi(\cdot)`. Working with centered kernels is sometime
        expected when dealing with algebra computation such as eigendecomposition
        for :class:`~sklearn.decomposition.KernelPCA` for instance.

        Read more in the :ref:`User Guide <kernel_centering>`.

        Attributes
        ----------
        K_fit_rows_ : ndarray of shape (n_samples,)
            Average of each column of kernel matrix.

        K_fit_all_ : float
            Average of kernel matrix.

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        See Also
        --------
        sklearn.kernel_approximation.Nystroem : Approximate a kernel map
            using a subset of the training data.

        References
        ----------
        .. [1] `Schölkopf, Bernhard, Alexander Smola, and Klaus-Robert Müller.
        "Nonlinear component analysis as a kernel eigenvalue problem."
        Neural computation 10.5 (1998): 1299-1319.
        <https://www.mlpack.org/papers/kpca.pdf>`_

        Examples
        --------
        >>> from sklearn.preprocessing import KernelCenterer
        >>> from sklearn.metrics.pairwise import pairwise_kernels
        >>> X = [[ 1., -2.,  2.],
        ...      [ -2.,  1.,  3.],
        ...      [ 4.,  1., -2.]]
        >>> K = pairwise_kernels(X, metric='linear')
        >>> K
            array([[  9.,   2.,  -2.],
                [  2.,  14., -13.],
                [ -2., -13.,  21.]])
        >>> transformer = KernelCenterer().fit(K)
        >>> transformer
            KernelCenterer()
        >>> transformer.transform(K)
            array([[  5.,   0.,  -5.],
                [  0.,  14., -14.],
                [ -5., -14.,  19.]])
            """
        ...

    @tobtind(lib="sf")
    def LabelBinarizer(self, y: Optional[Iterable] = None, neg_label: int = 0, pos_label: int = 1, sparse_output: bool = False, **kwargs) -> Union[series, dataframe]:
        """Binarize labels in a one-vs-all fashion.

        Several regression and binary classification algorithms are
        available in scikit-learn. A simple way to extend these algorithms
        to the multi-class classification case is to use the so-called
        one-vs-all scheme.

        At learning time, this simply consists in learning one regressor
        or binary classifier per class. In doing so, one needs to convert
        multi-class labels to binary labels (belong or does not belong
        to the class). LabelBinarizer makes this process easy with the
        transform method.

        At prediction time, one assigns the class for which the corresponding
        model gave the greatest confidence. LabelBinarizer makes this easy
        with the inverse_transform method.

        Read more in the :ref:`User Guide <preprocessing_targets>`.

        Parameters
        ----------
        neg_label : int, default=0
            Value with which negative labels must be encoded.

        pos_label : int, default=1
            Value with which positive labels must be encoded.

        sparse_output : bool, default=False
            True if the returned array from transform is desired to be in sparse
            CSR format.

        Attributes
        ----------
        classes_ : ndarray of shape (n_classes,)
            Holds the label for each class.

        y_type_ : str
            Represents the type of the target data as evaluated by
            utils.multiclass.type_of_target. Possible type are 'continuous',
            'continuous-multioutput', 'binary', 'multiclass',
            'multiclass-multioutput', 'multilabel-indicator', and 'unknown'.

        sparse_input_ : bool
            True if the input data to transform is given as a sparse matrix, False
            otherwise.

        See Also
        --------
        label_binarize : Function to perform the transform operation of
            LabelBinarizer with fixed classes.
        OneHotEncoder : Encode categorical features using a one-hot aka one-of-K
            scheme.

        Examples
        --------
        >>> from sklearn import preprocessing
        >>> lb = preprocessing.LabelBinarizer()
        >>> lb.fit([1, 2, 6, 4, 2])
        LabelBinarizer()
        >>> lb.classes_
        array([1, 2, 4, 6])
        >>> lb.transform([1, 6])
        array([[1, 0, 0, 0],
            [0, 0, 0, 1]])

        Binary targets transform to a column vector

        >>> lb = preprocessing.LabelBinarizer()
        >>> lb.fit_transform(['yes', 'no', 'no', 'yes'])
        array([[1],
            [0],
            [0],
            [1]])

        Passing a 2D matrix for multilabel classification

        >>> import numpy as np
        >>> lb.fit(np.array([[0, 1, 1], [1, 0, 0]]))
            LabelBinarizer()
        >>> lb.classes_
            array([0, 1, 2])
        >>> lb.transform([0, 1, 2, 1])
            array([[1, 0, 0],
                [0, 1, 0],
                [0, 0, 1],
                [0, 1, 0]])
            """
        ...

    @tobtind(lib="sf")
    def LabelEncoder(self, y: Optional[Iterable] = None, **kwargs) -> Union[series, dataframe]:
        """Encode target labels with value between 0 and n_classes-1.

        This transformer should be used to encode target values, *i.e.* `y`, and
        not the input `X`.

        Read more in the :ref:`User Guide <preprocessing_targets>`.

        .. versionadded:: 0.12

        Attributes
        ----------
        classes_ : ndarray of shape (n_classes,)
            Holds the label for each class.

        See Also
        --------
        OrdinalEncoder : Encode categorical features using an ordinal encoding
            scheme.
        OneHotEncoder : Encode categorical features as a one-hot numeric array.

        Examples
        --------
        `LabelEncoder` can be used to normalize labels.

        >>> from sklearn import preprocessing
        >>> le = preprocessing.LabelEncoder()
        >>> le.fit([1, 2, 2, 6])
        LabelEncoder()
        >>> le.classes_
        array([1, 2, 6])
        >>> le.transform([1, 1, 2, 6])
        array([0, 0, 1, 2]...)
        >>> le.inverse_transform([0, 0, 1, 2])
            array([1, 1, 2, 6])

        It can also be used to transform non-numerical labels (as long as they are
        hashable and comparable) to numerical labels.

        >>> le = preprocessing.LabelEncoder()
        >>> le.fit(["paris", "paris", "tokyo", "amsterdam"])
            LabelEncoder()
        >>> list(le.classes_)
            ['amsterdam', 'paris', 'tokyo']
        >>> le.transform(["tokyo", "tokyo", "paris"])
            array([2, 2, 1]...)
        >>> list(le.inverse_transform([2, 2, 1]))
            ['tokyo', 'tokyo', 'paris']
        """
        ...

    @tobtind(lib="sf")
    def MultiLabelBinarizer(self, y: Optional[Iterable] = None, classes=Optional[np.ndarray], sparse_output: bool = False, **kwargs) -> Union[series, dataframe]:
        """Transform between iterable of iterables and a multilabel format.

        Although a list of sets or tuples is a very intuitive format for multilabel
        data, it is unwieldy to process. This transformer converts between this
        intuitive format and the supported multilabel format: a (samples x classes)
        binary matrix indicating the presence of a class label.

        Parameters
        ----------
        classes : array-like of shape (n_classes,), default=None
            Indicates an ordering for the class labels.
            All entries should be unique (cannot contain duplicate classes).

        sparse_output : bool, default=False
            Set to True if output binary array is desired in CSR sparse format.

        Attributes
        ----------
        classes_ : ndarray of shape (n_classes,)
            A copy of the `classes` parameter when provided.
            Otherwise it corresponds to the sorted set of classes found
            when fitting.

        See Also
        --------
        OneHotEncoder : Encode categorical features using a one-hot aka one-of-K
            scheme.

        Examples
        --------
        >>> from sklearn.preprocessing import MultiLabelBinarizer
        >>> mlb = MultiLabelBinarizer()
        >>> mlb.fit_transform([(1, 2), (3,)])
            array([[1, 1, 0],
                [0, 0, 1]])
        >>> mlb.classes_
            array([1, 2, 3])

        >>> mlb.fit_transform([{'sci-fi', 'thriller'}, {'comedy'}])
            array([[0, 1, 1],
                [1, 0, 0]])
        >>> list(mlb.classes_)
            ['comedy', 'sci-fi', 'thriller']

        A common mistake is to pass in a list, which leads to the following issue:

        >>> mlb = MultiLabelBinarizer()
        >>> mlb.fit(['sci-fi', 'thriller', 'comedy'])
            MultiLabelBinarizer()
        >>> mlb.classes_
            array(['-', 'c', 'd', 'e', 'f', 'h', 'i', 'l', 'm', 'o', 'r', 's', 't',
                'y'], dtype=object)

        To correct this, the list of labels should be passed in as:

        >>> mlb = MultiLabelBinarizer()
        >>> mlb.fit([['sci-fi', 'thriller', 'comedy']])
            MultiLabelBinarizer()
        >>> mlb.classes_
            array(['comedy', 'sci-fi', 'thriller'], dtype=object)
        """
        ...

    @tobtind(lib="sf")
    def MinMaxScaler(self, y: Optional[Iterable] = None, feature_range: tuple[int] = (0, 1), copy: bool = True, clip: bool = False, fit_params: dict = {}, **kwargs) -> Union[series, dataframe]:
        """Transform features by scaling each feature to a given range.

        This estimator scales and translates each feature individually such
        that it is in the given range on the training set, e.g. between
        zero and one.

        The transformation is given by::

            X_std = (X - X.min(axis=0)) / (X.max(axis=0) - X.min(axis=0))
            X_scaled = X_std * (max - min) + min

        where min, max = feature_range.

        This transformation is often used as an alternative to zero mean,
        unit variance scaling.

        Read more in the :ref:`User Guide <preprocessing_scaler>`.

        Parameters
        ----------
        feature_range : tuple (min, max), default=(0, 1)
            Desired range of transformed data.

        copy : bool, default=True
            Set to False to perform inplace row normalization and avoid a
            copy (if the input is already a numpy array).

        clip : bool, default=False
            Set to True to clip transformed values of held-out data to
            provided `feature range`.

            .. versionadded:: 0.24

        Attributes
        ----------
        min_ : ndarray of shape (n_features,)
            Per feature adjustment for minimum. Equivalent to
            ``min - X.min(axis=0) * self.scale_``

        scale_ : ndarray of shape (n_features,)
            Per feature relative scaling of the data. Equivalent to
            ``(max - min) / (X.max(axis=0) - X.min(axis=0))``

            .. versionadded:: 0.17
            *scale_* attribute.

        data_min_ : ndarray of shape (n_features,)
            Per feature minimum seen in the data

            .. versionadded:: 0.17
            *data_min_*

        data_max_ : ndarray of shape (n_features,)
            Per feature maximum seen in the data

            .. versionadded:: 0.17
            *data_max_*

        data_range_ : ndarray of shape (n_features,)
            Per feature range ``(data_max_ - data_min_)`` seen in the data

            .. versionadded:: 0.17
            *data_range_*

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        n_samples_seen_ : int
            The number of samples processed by the estimator.
            It will be reset on new calls to fit, but increments across
            ``partial_fit`` calls.

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        See Also
        --------
        minmax_scale : Equivalent function without the estimator API.

        Notes
        -----
        NaNs are treated as missing values: disregarded in fit, and maintained in
        transform.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        Examples
        --------
        >>> from sklearn.preprocessing import MinMaxScaler
        >>> data = [[-1, 2], [-0.5, 6], [0, 10], [1, 18]]
        >>> scaler = MinMaxScaler()
        >>> print(scaler.fit(data))
            MinMaxScaler()
        >>> print(scaler.data_max_)
            [ 1. 18.]
        >>> print(scaler.transform(data))
            [[0.   0.  ]
            [0.25 0.25]
            [0.5  0.5 ]
            [1.   1.  ]]
        >>> print(scaler.transform([[2, 2]]))
            [[1.5 0. ]]
        """
        ...

    @tobtind(lib="sf")
    def MaxAbsScaler(self, y: Optional[Iterable] = None, copy: bool = True, fit_params: dict = {}, **kwargs) -> Union[series, dataframe]:
        """Scale each feature by its maximum absolute value.

        This estimator scales and translates each feature individually such
        that the maximal absolute value of each feature in the
        training set will be 1.0. It does not shift/center the data, and
        thus does not destroy any sparsity.

        This scaler can also be applied to sparse CSR or CSC matrices.

        .. versionadded:: 0.17

        Parameters
        ----------
        copy : bool, default=True
            Set to False to perform inplace scaling and avoid a copy (if the input
            is already a numpy array).

        Attributes
        ----------
        scale_ : ndarray of shape (n_features,)
            Per feature relative scaling of the data.

            .. versionadded:: 0.17
            *scale_* attribute.

        max_abs_ : ndarray of shape (n_features,)
            Per feature maximum absolute value.

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        n_samples_seen_ : int
            The number of samples processed by the estimator. Will be reset on
            new calls to fit, but increments across ``partial_fit`` calls.

        See Also
        --------
        maxabs_scale : Equivalent function without the estimator API.

        Notes
        -----
        NaNs are treated as missing values: disregarded in fit, and maintained in
        transform.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        Examples
        --------
        >>> from sklearn.preprocessing import MaxAbsScaler
        >>> X = [[ 1., -1.,  2.],
        ...      [ 2.,  0.,  0.],
        ...      [ 0.,  1., -1.]]
        >>> transformer = MaxAbsScaler().fit(X)
        >>> transformer
            MaxAbsScaler()
        >>> transformer.transform(X)
            array([[ 0.5, -1. ,  1. ],
                [ 1. ,  0. ,  0. ],
                [ 0. ,  1. , -0.5]])
        """
        ...

    @tobtind(lib="sf")
    def QuantileTransformer(
        self,
        y: Optional[Iterable] = None,
        n_quantiles: int = 1000,
        output_distribution: Literal['uniform', 'normal'] = "uniform",
        ignore_implicit_zeros: bool = False,
        subsample: int = int(1e5),
        random_state: int | RandomState | None = None,
        copy: bool = True,
        fit_params: dict = {},
        **kwargs
    ) -> Union[series, dataframe]:
        """Transform features using quantiles information.

        This method transforms the features to follow a uniform or a normal
        distribution. Therefore, for a given feature, this transformation tends
        to spread out the most frequent values. It also reduces the impact of
        (marginal) outliers: this is therefore a robust preprocessing scheme.

        The transformation is applied on each feature independently. First an
        estimate of the cumulative distribution function of a feature is
        used to map the original values to a uniform distribution. The obtained
        values are then mapped to the desired output distribution using the
        associated quantile function. Features values of new/unseen data that fall
        below or above the fitted range will be mapped to the bounds of the output
        distribution. Note that this transform is non-linear. It may distort linear
        correlations between variables measured at the same scale but renders
        variables measured at different scales more directly comparable.

        Read more in the :ref:`User Guide <preprocessing_transformer>`.

        .. versionadded:: 0.19

        Parameters
        ----------
        n_quantiles : int, default=1000 or n_samples
            Number of quantiles to be computed. It corresponds to the number
            of landmarks used to discretize the cumulative distribution function.
            If n_quantiles is larger than the number of samples, n_quantiles is set
            to the number of samples as a larger number of quantiles does not give
            a better approximation of the cumulative distribution function
            estimator.

        output_distribution : {'uniform', 'normal'}, default='uniform'
            Marginal distribution for the transformed data. The choices are
            'uniform' (default) or 'normal'.

        ignore_implicit_zeros : bool, default=False
            Only applies to sparse matrices. If True, the sparse entries of the
            matrix are discarded to compute the quantile statistics. If False,
            these entries are treated as zeros.

        subsample : int, default=1e5
            Maximum number of samples used to estimate the quantiles for
            computational efficiency. Note that the subsampling procedure may
            differ for value-identical sparse and dense matrices.

        random_state : int, RandomState instance or None, default=None
            Determines random number generation for subsampling and smoothing
            noise.
            Please see ``subsample`` for more details.
            Pass an int for reproducible results across multiple function calls.
            See :term:`Glossary <random_state>`.

        copy : bool, default=True
            Set to False to perform inplace transformation and avoid a copy (if the
            input is already a numpy array).

        Attributes
        ----------
        n_quantiles_ : int
            The actual number of quantiles used to discretize the cumulative
            distribution function.

        quantiles_ : ndarray of shape (n_quantiles, n_features)
            The values corresponding the quantiles of reference.

        references_ : ndarray of shape (n_quantiles, )
            Quantiles of references.

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        See Also
        --------
        quantile_transform : Equivalent function without the estimator API.
        PowerTransformer : Perform mapping to a normal distribution using a power
            transform.
        StandardScaler : Perform standardization that is faster, but less robust
            to outliers.
        RobustScaler : Perform robust standardization that removes the influence
            of outliers but does not put outliers and inliers on the same scale.

        Notes
        -----
        NaNs are treated as missing values: disregarded in fit, and maintained in
        transform.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        Examples
        --------
        >>> import numpy as np
        >>> from sklearn.preprocessing import QuantileTransformer
        >>> rng = np.random.RandomState(0)
        >>> X = np.sort(rng.normal(loc=0.5, scale=0.25, size=(25, 1)), axis=0)
        >>> qt = QuantileTransformer(n_quantiles=10, random_state=0)
        >>> qt.fit_transform(X)
            array([...])
        """
        ...

    @tobtind(lib="sf")
    def Normalizer(self, y: Optional[Iterable] = None, norm: Literal['l1', 'l2', 'max'] = "l2", copy: bool = True, fit_params: dict = {}, **kwargs) -> Union[series, dataframe]:
        """Normalize samples individually to unit norm.

        Each sample (i.e. each row of the data matrix) with at least one
        non zero component is rescaled independently of other samples so
        that its norm (l1, l2 or inf) equals one.

        This transformer is able to work both with dense numpy arrays and
        scipy.sparse matrix (use CSR format if you want to avoid the burden of
        a copy / conversion).

        Scaling inputs to unit norms is a common operation for text
        classification or clustering for instance. For instance the dot
        product of two l2-normalized TF-IDF vectors is the cosine similarity
        of the vectors and is the base similarity metric for the Vector
        Space Model commonly used by the Information Retrieval community.

        Read more in the :ref:`User Guide <preprocessing_normalization>`.

        Parameters
        ----------
        norm : {'l1', 'l2', 'max'}, default='l2'
            The norm to use to normalize each non zero sample. If norm='max'
            is used, values will be rescaled by the maximum of the absolute
            values.

        copy : bool, default=True
            Set to False to perform inplace row normalization and avoid a
            copy (if the input is already a numpy array or a scipy.sparse
            CSR matrix).

        Attributes
        ----------
        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        See Also
        --------
        normalize : Equivalent function without the estimator API.

        Notes
        -----
        This estimator is stateless (besides constructor parameters), the
        fit method does nothing but is useful when used in a pipeline.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        Examples
        --------
        >>> from sklearn.preprocessing import Normalizer
        >>> X = [[4, 1, 2, 2],
        ...      [1, 3, 9, 3],
        ...      [5, 7, 5, 1]]
        >>> transformer = Normalizer().fit(X)  # fit does nothing.
        >>> transformer
            Normalizer()
        >>> transformer.transform(X)
            array([[0.8, 0.2, 0.4, 0.4],
                [0.1, 0.3, 0.9, 0.3],
                [0.5, 0.7, 0.5, 0.1]])
        """
        ...

    @tobtind(lib="sf")
    def OneHotEncoder(
        self,
        y: Optional[Iterable] = None,
        categories: Sequence[np.ndarray] | Literal['auto'] = "auto",
        drop: Optional[np.ndarray] = None,
        sparse: str | bool = True,
        dtype=np.float64,
        handle_unknown="error",
        min_frequency=None,
        max_categories=None,
        fit_params: dict = {},
        **kwargs
    ) -> Union[series, dataframe]:
        """
        Encode categorical features as a one-hot numeric array.

        The input to this transformer should be an array-like of integers or
        strings, denoting the values taken on by categorical (discrete) features.
        The features are encoded using a one-hot (aka 'one-of-K' or 'dummy')
        encoding scheme. This creates a binary column for each category and
        returns a sparse matrix or dense array (depending on the ``sparse``
        parameter)

        By default, the encoder derives the categories based on the unique values
        in each feature. Alternatively, you can also specify the `categories`
        manually.

        This encoding is needed for feeding categorical data to many scikit-learn
        estimators, notably linear models and SVMs with the standard kernels.

        Note: a one-hot encoding of y labels should use a LabelBinarizer
        instead.

        Read more in the :ref:`User Guide <preprocessing_categorical_features>`.

        Parameters
        ----------
        categories : 'auto' or a list of array-like, default='auto'
            Categories (unique values) per feature:

            - 'auto' : Determine categories automatically from the training data.
            - list : ``categories[i]`` holds the categories expected in the ith
            column. The passed categories should not mix strings and numeric
            values within a single feature, and should be sorted in case of
            numeric values.

            The used categories can be found in the ``categories_`` attribute.

            .. versionadded:: 0.20

        drop : {'first', 'if_binary'} or an array-like of shape (n_features,), \
                default=None
            Specifies a methodology to use to drop one of the categories per
            feature. This is useful in situations where perfectly collinear
            features cause problems, such as when feeding the resulting data
            into an unregularized linear regression model.

            However, dropping one category breaks the symmetry of the original
            representation and can therefore induce a bias in downstream models,
            for instance for penalized linear classification or regression models.

            - None : retain all features (the default).
            - 'first' : drop the first category in each feature. If only one
            category is present, the feature will be dropped entirely.
            - 'if_binary' : drop the first category in each feature with two
            categories. Features with 1 or more than 2 categories are
            left intact.
            - array : ``drop[i]`` is the category in feature ``X[:, i]`` that
            should be dropped.

            .. versionadded:: 0.21
            The parameter `drop` was added in 0.21.

            .. versionchanged:: 0.23
            The option `drop='if_binary'` was added in 0.23.

            .. versionchanged:: 1.1
                Support for dropping infrequent categories.

        sparse : bool, default=True
            Will return sparse matrix if set True else will return an array.

        dtype : number type, default=float
            Desired dtype of output.

        handle_unknown : {'error', 'ignore', 'infrequent_if_exist'}, \
                        default='error'
            Specifies the way unknown categories are handled during :meth:`transform`.

            - 'error' : Raise an error if an unknown category is present during transform.
            - 'ignore' : When an unknown category is encountered during
            transform, the resulting one-hot encoded columns for this feature
            will be all zeros. In the inverse transform, an unknown category
            will be denoted as None.
            - 'infrequent_if_exist' : When an unknown category is encountered
            during transform, the resulting one-hot encoded columns for this
            feature will map to the infrequent category if it exists. The
            infrequent category will be mapped to the last position in the
            encoding. During inverse transform, an unknown category will be
            mapped to the category denoted `'infrequent'` if it exists. If the
            `'infrequent'` category does not exist, then :meth:`transform` and
            :meth:`inverse_transform` will handle an unknown category as with
            `handle_unknown='ignore'`. Infrequent categories exist based on
            `min_frequency` and `max_categories`. Read more in the
            :ref:`User Guide <one_hot_encoder_infrequent_categories>`.

            .. versionchanged:: 1.1
                `'infrequent_if_exist'` was added to automatically handle unknown
                categories and infrequent categories.

        min_frequency : int or float, default=None
            Specifies the minimum frequency below which a category will be
            considered infrequent.

            - If `int`, categories with a smaller cardinality will be considered
            infrequent.

            - If `float`, categories with a smaller cardinality than
            `min_frequency * n_samples`  will be considered infrequent.

            .. versionadded:: 1.1
                Read more in the :ref:`User Guide <one_hot_encoder_infrequent_categories>`.

        max_categories : int, default=None
            Specifies an upper limit to the number of output features for each input
            feature when considering infrequent categories. If there are infrequent
            categories, `max_categories` includes the category representing the
            infrequent categories along with the frequent categories. If `None`,
            there is no limit to the number of output features.

            .. versionadded:: 1.1
                Read more in the :ref:`User Guide <one_hot_encoder_infrequent_categories>`.

        Attributes
        ----------
        categories_ : list of arrays
            The categories of each feature determined during fitting
            (in order of the features in X and corresponding with the output
            of ``transform``). This includes the category specified in ``drop``
            (if any).

        drop_idx_ : array of shape (n_features,)
            - ``drop_idx_[i]`` is the index in ``categories_[i]`` of the category
            to be dropped for each feature.
            - ``drop_idx_[i] = None`` if no category is to be dropped from the
            feature with index ``i``, e.g. when `drop='if_binary'` and the
            feature isn't binary.
            - ``drop_idx_ = None`` if all the transformed features will be
            retained.

            If infrequent categories are enabled by setting `min_frequency` or
            `max_categories` to a non-default value and `drop_idx[i]` corresponds
            to a infrequent category, then the entire infrequent category is
            dropped.

            .. versionchanged:: 0.23
            Added the possibility to contain `None` values.

        infrequent_categories_ : list of ndarray
            Defined only if infrequent categories are enabled by setting
            `min_frequency` or `max_categories` to a non-default value.
            `infrequent_categories_[i]` are the infrequent categories for feature
            `i`. If the feature `i` has no infrequent categories
            `infrequent_categories_[i]` is None.

            .. versionadded:: 1.1

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 1.0

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        See Also
        --------
        OrdinalEncoder : Performs an ordinal (integer)
        encoding of the categorical features.
        sklearn.feature_extraction.DictVectorizer : Performs a one-hot encoding of
        dictionary items (also handles string-valued features).
        sklearn.feature_extraction.FeatureHasher : Performs an approximate one-hot
        encoding of dictionary items or strings.
        LabelBinarizer : Binarizes labels in a one-vs-all
        fashion.
        MultiLabelBinarizer : Transforms between iterable of
        iterables and a multilabel format, e.g. a (samples x classes) binary
        matrix indicating the presence of a class label.

        Examples
        --------
        Given a dataset with two features, we let the encoder find the unique
        values per feature and transform the data to a binary one-hot encoding.

        >>> from sklearn.preprocessing import OneHotEncoder

        One can discard categories not seen during `fit`:

        >>> enc = OneHotEncoder(handle_unknown='ignore')
        >>> X = [['Male', 1], ['Female', 3], ['Female', 2]]
        >>> enc.fit(X)
            OneHotEncoder(handle_unknown='ignore')
        >>> enc.categories_
            [array(['Female', 'Male'], dtype=object),
                   array([1, 2, 3], dtype=object)]
        >>> enc.transform([['Female', 1], ['Male', 4]]).toarray()
            array([[1., 0., 1., 0., 0.],
                [0., 1., 0., 0., 0.]])
        >>> enc.inverse_transform([[0, 1, 1, 0, 0], [0, 0, 0, 1, 0]])
            array([['Male', 1],
                [None, 2]], dtype=object)
        >>> enc.get_feature_names_out(['gender', 'group'])
            array(['gender_Female', 'gender_Male',
                  'group_1', 'group_2', 'group_3'], ...)

        One can always drop the first column for each feature:

        >>> drop_enc = OneHotEncoder(drop='first').fit(X)
        >>> drop_enc.categories_
            [array(['Female', 'Male'], dtype=object),
                   array([1, 2, 3], dtype=object)]
        >>> drop_enc.transform([['Female', 1], ['Male', 2]]).toarray()
            array([[0., 0., 0.],
                [1., 1., 0.]])

        Or drop a column for feature only having 2 categories:

        >>> drop_binary_enc = OneHotEncoder(drop='if_binary').fit(X)
        >>> drop_binary_enc.transform([['Female', 1], ['Male', 2]]).toarray()
            array([[0., 1., 0., 0.],
                [1., 0., 1., 0.]])

        Infrequent categories are enabled by setting `max_categories` or `min_frequency`.

        >>> import numpy as np
        >>> X = np.array([["a"] * 5 + ["b"] * 20 + ["c"] * 10 + ["d"] * 3], dtype=object).T
        >>> ohe = OneHotEncoder(max_categories=3, sparse=False).fit(X)
        >>> ohe.infrequent_categories_
            [array(['a', 'd'], dtype=object)]
        >>> ohe.transform([["a"], ["b"]])
            array([[0., 0., 1.],
                [1., 0., 0.]])
        """
        ...

    @tobtind(lib="sf")
    def OrdinalEncoder(
        self,
        y: Optional[Iterable] = None,
        categories="auto",
        dtype=np.float64,
        handle_unknown="error",
        unknown_value=None,
        encoded_missing_value=np.nan,
        fit_params: dict = {},
        **kwargs
    ) -> Union[series, dataframe]:
        """
        Encode categorical features as an integer array.

        The input to this transformer should be an array-like of integers or
        strings, denoting the values taken on by categorical (discrete) features.
        The features are converted to ordinal integers. This results in
        a single column of integers (0 to n_categories - 1) per feature.

        Read more in the :ref:`User Guide <preprocessing_categorical_features>`.

        .. versionadded:: 0.20

        Parameters
        ----------
        categories : 'auto' or a list of array-like, default='auto'
            Categories (unique values) per feature:

            - 'auto' : Determine categories automatically from the training data.
            - list : ``categories[i]`` holds the categories expected in the ith
            column. The passed categories should not mix strings and numeric
            values, and should be sorted in case of numeric values.

            The used categories can be found in the ``categories_`` attribute.

        dtype : number type, default np.float64
            Desired dtype of output.

        handle_unknown : {'error', 'use_encoded_value'}, default='error'
            When set to 'error' an error will be raised in case an unknown
            categorical feature is present during transform. When set to
            'use_encoded_value', the encoded value of unknown categories will be
            set to the value given for the parameter `unknown_value`. In
            :meth:`inverse_transform`, an unknown category will be denoted as None.

            .. versionadded:: 0.24

        unknown_value : int or np.nan, default=None
            When the parameter handle_unknown is set to 'use_encoded_value', this
            parameter is required and will set the encoded value of unknown
            categories. It has to be distinct from the values used to encode any of
            the categories in `fit`. If set to np.nan, the `dtype` parameter must
            be a float dtype.

            .. versionadded:: 0.24

        encoded_missing_value : int or np.nan, default=np.nan
            Encoded value of missing categories. If set to `np.nan`, then the `dtype`
            parameter must be a float dtype.

            .. versionadded:: 1.1

        Attributes
        ----------
        categories_ : list of arrays
            The categories of each feature determined during ``fit`` (in order of
            the features in X and corresponding with the output of ``transform``).
            This does not include categories that weren't seen during ``fit``.

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 1.0

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        See Also
        --------
        OneHotEncoder : Performs a one-hot encoding of categorical features.
        LabelEncoder : Encodes target labels with values between 0 and
            ``n_classes-1``.

        Examples
        --------
        Given a dataset with two features, we let the encoder find the unique
        values per feature and transform the data to an ordinal encoding.

        >>> from sklearn.preprocessing import OrdinalEncoder
        >>> enc = OrdinalEncoder()
        >>> X = [['Male', 1], ['Female', 3], ['Female', 2]]
        >>> enc.fit(X)
            OrdinalEncoder()
        >>> enc.categories_
            [array(['Female', 'Male'], dtype=object),
                   array([1, 2, 3], dtype=object)]
        >>> enc.transform([['Female', 3], ['Male', 1]])
            array([[0., 2.],
                [1., 0.]])

        >>> enc.inverse_transform([[1, 0], [0, 1]])
            array([['Male', 1],
                ['Female', 2]], dtype=object)

        By default, :class:`OrdinalEncoder` is lenient towards missing values by
        propagating them.

        >>> import numpy as np
        >>> X = [['Male', 1], ['Female', 3], ['Female', np.nan]]
        >>> enc.fit_transform(X)
            array([[ 1.,  0.],
                [ 0.,  1.],
                [ 0., nan]])

        You can use the parameter `encoded_missing_value` to encode missing values.

        >>> enc.set_params(encoded_missing_value=-1).fit_transform(X)
            array([[ 1.,  0.],
                [ 0.,  1.],
                [ 0., -1.]])
        """
        ...

    @tobtind(lib="sf")
    def PowerTransformer(self, y: Optional[Iterable] = None, method="yeo-johnson", standardize=True, copy=True, **kwargs) -> Union[series, dataframe]:
        """Apply a power transform featurewise to make data more Gaussian-like.

        Power transforms are a family of parametric, monotonic transformations
        that are applied to make data more Gaussian-like. This is useful for
        modeling issues related to heteroscedasticity (non-constant variance),
        or other situations where normality is desired.

        Currently, PowerTransformer supports the Box-Cox transform and the
        Yeo-Johnson transform. The optimal parameter for stabilizing variance and
        minimizing skewness is estimated through maximum likelihood.

        Box-Cox requires input data to be strictly positive, while Yeo-Johnson
        supports both positive or negative data.

        By default, zero-mean, unit-variance normalization is applied to the
        transformed data.

        Read more in the :ref:`User Guide <preprocessing_transformer>`.

        .. versionadded:: 0.20

        Parameters
        ----------
        method : {'yeo-johnson', 'box-cox'}, default='yeo-johnson'
            The power transform method. Available methods are:

            - 'yeo-johnson' [1]_, works with positive and negative values
            - 'box-cox' [2]_, only works with strictly positive values

        standardize : bool, default=True
            Set to True to apply zero-mean, unit-variance normalization to the
            transformed output.

        copy : bool, default=True
            Set to False to perform inplace computation during transformation.

        Attributes
        ----------
        lambdas_ : ndarray of float of shape (n_features,)
            The parameters of the power transformation for the selected features.

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        See Also
        --------
        power_transform : Equivalent function without the estimator API.

        QuantileTransformer : Maps data to a standard normal distribution with
            the parameter `output_distribution='normal'`.

        Notes
        -----
        NaNs are treated as missing values: disregarded in ``fit``, and maintained
        in ``transform``.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        References
        ----------

        .. [1] I.K. Yeo and R.A. Johnson, "A new family of power transformations to
            improve normality or symmetry." Biometrika, 87(4), pp.954-959,
            (2000).

        .. [2] G.E.P. Box and D.R. Cox, "An Analysis of Transformations", Journal
            of the Royal Statistical Society B, 26, 211-252 (1964).

        Examples
        --------
        >>> import numpy as np
        >>> from sklearn.preprocessing import PowerTransformer
        >>> pt = PowerTransformer()
        >>> data = [[1, 2], [3, 2], [4, 5]]
        >>> print(pt.fit(data))
            PowerTransformer()
        >>> print(pt.lambdas_)
            [ 1.386... -3.100...]
        >>> print(pt.transform(data))
            [[-1.316... -0.707...]
            [ 0.209... -0.707...]
            [ 1.106...  1.414...]]
        """
        ...

    @tobtind(lib="sf")
    def RobustScaler(
        self,
        y: Optional[Iterable] = None,
        with_centering: bool = True,
        with_scaling: bool = True,
        quantile_range: tuple[float] = (25.0, 75.0),
        copy: bool = True,
        unit_variance: bool = False,
        fit_params: dict = {},
        **kwargs
    ) -> Union[series, dataframe]:
        """Scale features using statistics that are robust to outliers.

        This Scaler removes the median and scales the data according to
        the quantile range (defaults to IQR: Interquartile Range).
        The IQR is the range between the 1st quartile (25th quantile)
        and the 3rd quartile (75th quantile).

        Centering and scaling happen independently on each feature by
        computing the relevant statistics on the samples in the training
        set. Median and interquartile range are then stored to be used on
        later data using the :meth:`transform` method.

        Standardization of a dataset is a common requirement for many
        machine learning estimators. Typically this is done by removing the mean
        and scaling to unit variance. However, outliers can often influence the
        sample mean / variance in a negative way. In such cases, the median and
        the interquartile range often give better results.

        .. versionadded:: 0.17

        Read more in the :ref:`User Guide <preprocessing_scaler>`.

        Parameters
        ----------
        with_centering : bool, default=True
            If `True`, center the data before scaling.
            This will cause :meth:`transform` to raise an exception when attempted
            on sparse matrices, because centering them entails building a dense
            matrix which in common use cases is likely to be too large to fit in
            memory.

        with_scaling : bool, default=True
            If `True`, scale the data to interquartile range.

        quantile_range : tuple (q_min, q_max), 0.0 < q_min < q_max < 100.0, \
            default=(25.0, 75.0)
            Quantile range used to calculate `scale_`. By default this is equal to
            the IQR, i.e., `q_min` is the first quantile and `q_max` is the third
            quantile.

            .. versionadded:: 0.18

        copy : bool, default=True
            If `False`, try to avoid a copy and do inplace scaling instead.
            This is not guaranteed to always work inplace; e.g. if the data is
            not a NumPy array or scipy.sparse CSR matrix, a copy may still be
            returned.

        unit_variance : bool, default=False
            If `True`, scale data so that normally distributed features have a
            variance of 1. In general, if the difference between the x-values of
            `q_max` and `q_min` for a standard normal distribution is greater
            than 1, the dataset will be scaled down. If less than 1, the dataset
            will be scaled up.

            .. versionadded:: 0.24

        Attributes
        ----------
        center_ : array of floats
            The median value for each feature in the training set.

        scale_ : array of floats
            The (scaled) interquartile range for each feature in the training set.

            .. versionadded:: 0.17
            *scale_* attribute.

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        See Also
        --------
        robust_scale : Equivalent function without the estimator API.
        sklearn.decomposition.PCA : Further removes the linear correlation across
            features with 'whiten=True'.

        Notes
        -----
        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        https://en.wikipedia.org/wiki/Median
        https://en.wikipedia.org/wiki/Interquartile_range

        Examples
        --------
        >>> from sklearn.preprocessing import RobustScaler
        >>> X = [[ 1., -2.,  2.],
        ...      [ -2.,  1.,  3.],
        ...      [ 4.,  1., -2.]]
        >>> transformer = RobustScaler().fit(X)
        >>> transformer
            RobustScaler()
        >>> transformer.transform(X)
            array([[ 0. , -2. ,  0. ],
                [-1. ,  0. ,  0.4],
                [ 1. ,  0. , -1.6]])
        """
        ...

    @tobtind(lib="sf")
    def SplineTransformer(
        self,
        y: Optional[Iterable] = None,
        n_knots=5,
        degree=3,
        knots="uniform",
        extrapolation="constant",
        include_bias=True,
        order="C",
        fit_params: dict = {},
        **kwargs
    ) -> Union[series, dataframe]:
        """Generate univariate B-spline bases for features.

        Generate a new feature matrix consisting of
        `n_splines=n_knots + degree - 1` (`n_knots - 1` for
        `extrapolation="periodic"`) spline basis functions
        (B-splines) of polynomial order=`degree` for each feature.

        Read more in the :ref:`User Guide <spline_transformer>`.

        .. versionadded:: 1.0

        Parameters
        ----------
        n_knots : int, default=5
            Number of knots of the splines if `knots` equals one of
            {'uniform', 'quantile'}. Must be larger or equal 2. Ignored if `knots`
            is array-like.

        degree : int, default=3
            The polynomial degree of the spline basis. Must be a non-negative
            integer.

        knots : {'uniform', 'quantile'} or array-like of shape \
            (n_knots, n_features), default='uniform'
            Set knot positions such that first knot <= features <= last knot.

            - If 'uniform', `n_knots` number of knots are distributed uniformly
            from min to max values of the features.
            - If 'quantile', they are distributed uniformly along the quantiles of
            the features.
            - If an array-like is given, it directly specifies the sorted knot
            positions including the boundary knots. Note that, internally,
            `degree` number of knots are added before the first knot, the same
            after the last knot.

        extrapolation : {'error', 'constant', 'linear', 'continue', 'periodic'}, \
            default='constant'
            If 'error', values outside the min and max values of the training
            features raises a `ValueError`. If 'constant', the value of the
            splines at minimum and maximum value of the features is used as
            constant extrapolation. If 'linear', a linear extrapolation is used.
            If 'continue', the splines are extrapolated as is, i.e. option
            `extrapolate=True` in :class:`scipy.interpolate.BSpline`. If
            'periodic', periodic splines with a periodicity equal to the distance
            between the first and last knot are used. Periodic splines enforce
            equal function values and derivatives at the first and last knot.
            For example, this makes it possible to avoid introducing an arbitrary
            jump between Dec 31st and Jan 1st in spline features derived from a
            naturally periodic "day-of-year" input feature. In this case it is
            recommended to manually set the knot values to control the period.

        include_bias : bool, default=True
            If True (default), then the last spline element inside the data range
            of a feature is dropped. As B-splines sum to one over the spline basis
            functions for each data point, they implicitly include a bias term,
            i.e. a column of ones. It acts as an intercept term in a linear models.

        order : {'C', 'F'}, default='C'
            Order of output array. 'F' order is faster to compute, but may slow
            down subsequent estimators.

        Attributes
        ----------
        bsplines_ : list of shape (n_features,)
            List of BSplines objects, one for each feature.

        n_features_in_ : int
            The total number of input features.

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        n_features_out_ : int
            The total number of output features, which is computed as
            `n_features * n_splines`, where `n_splines` is
            the number of bases elements of the B-splines,
            `n_knots + degree - 1` for non-periodic splines and
            `n_knots - 1` for periodic ones.
            If `include_bias=False`, then it is only
            `n_features * (n_splines - 1)`.

        See Also
        --------
        KBinsDiscretizer : Transformer that bins continuous data into intervals.

        PolynomialFeatures : Transformer that generates polynomial and interaction
            features.

        Notes
        -----
        High degrees and a high number of knots can cause overfitting.

        See :ref:`examples/linear_model/plot_polynomial_interpolation.py
        <sphx_glr_auto_examples_linear_model_plot_polynomial_interpolation.py>`.

        Examples
        --------
        >>> import numpy as np
        >>> from sklearn.preprocessing import SplineTransformer
        >>> X = np.arange(6).reshape(6, 1)
        >>> spline = SplineTransformer(degree=2, n_knots=3)
        >>> spline.fit_transform(X)
            array([[0.5 , 0.5 , 0.  , 0.  ],
                [0.18, 0.74, 0.08, 0.  ],
                [0.02, 0.66, 0.32, 0.  ],
                [0.  , 0.32, 0.66, 0.02],
                [0.  , 0.08, 0.74, 0.18],
                [0.  , 0.  , 0.5 , 0.5 ]])
        """
        ...

    @tobtind(lib="sf")
    def StandardScaler(self, y: Optional[Iterable] = None, copy: bool = True, with_mean: bool = True, with_std: bool = True, fit_params: dict = {}, **kwargs) -> Union[series, dataframe]:
        """Standardize features by removing the mean and scaling to unit variance.

        The standard score of a sample `x` is calculated as:

            z = (x - u) / s

        where `u` is the mean of the training samples or zero if `with_mean=False`,
        and `s` is the standard deviation of the training samples or one if
        `with_std=False`.

        Centering and scaling happen independently on each feature by computing
        the relevant statistics on the samples in the training set. Mean and
        standard deviation are then stored to be used on later data using
        :meth:`transform`.

        Standardization of a dataset is a common requirement for many
        machine learning estimators: they might behave badly if the
        individual features do not more or less look like standard normally
        distributed data (e.g. Gaussian with 0 mean and unit variance).

        For instance many elements used in the objective function of
        a learning algorithm (such as the RBF kernel of Support Vector
        Machines or the L1 and L2 regularizers of linear models) assume that
        all features are centered around 0 and have variance in the same
        order. If a feature has a variance that is orders of magnitude larger
        than others, it might dominate the objective function and make the
        estimator unable to learn from other features correctly as expected.

        This scaler can also be applied to sparse CSR or CSC matrices by passing
        `with_mean=False` to avoid breaking the sparsity structure of the data.

        Read more in the :ref:`User Guide <preprocessing_scaler>`.

        Parameters
        ----------
        copy : bool, default=True
            If False, try to avoid a copy and do inplace scaling instead.
            This is not guaranteed to always work inplace; e.g. if the data is
            not a NumPy array or scipy.sparse CSR matrix, a copy may still be
            returned.

        with_mean : bool, default=True
            If True, center the data before scaling.
            This does not work (and will raise an exception) when attempted on
            sparse matrices, because centering them entails building a dense
            matrix which in common use cases is likely to be too large to fit in
            memory.

        with_std : bool, default=True
            If True, scale the data to unit variance (or equivalently,
            unit standard deviation).

        Attributes
        ----------
        scale_ : ndarray of shape (n_features,) or None
            Per feature relative scaling of the data to achieve zero mean and unit
            variance. Generally this is calculated using `np.sqrt(var_)`. If a
            variance is zero, we can't achieve unit variance, and the data is left
            as-is, giving a scaling factor of 1. `scale_` is equal to `None`
            when `with_std=False`.

            .. versionadded:: 0.17
            *scale_*

        mean_ : ndarray of shape (n_features,) or None
            The mean value for each feature in the training set.
            Equal to ``None`` when ``with_mean=False``.

        var_ : ndarray of shape (n_features,) or None
            The variance for each feature in the training set. Used to compute
            `scale_`. Equal to ``None`` when ``with_std=False``.

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        n_samples_seen_ : int or ndarray of shape (n_features,)
            The number of samples processed by the estimator for each feature.
            If there are no missing samples, the ``n_samples_seen`` will be an
            integer, otherwise it will be an array of dtype int. If
            `sample_weights` are used it will be a float (if no missing data)
            or an array of dtype float that sums the weights seen so far.
            Will be reset on new calls to fit, but increments across
            ``partial_fit`` calls.

        See Also
        --------
        scale : Equivalent function without the estimator API.

        :class:`~sklearn.decomposition.PCA` : Further removes the linear
            correlation across features with 'whiten=True'.

        Notes
        -----
        NaNs are treated as missing values: disregarded in fit, and maintained in
        transform.

        We use a biased estimator for the standard deviation, equivalent to
        `numpy.std(x, ddof=0)`. Note that the choice of `ddof` is unlikely to
        affect model performance.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        Examples
        --------
        >>> from sklearn.preprocessing import StandardScaler
        >>> data = [[0, 0], [0, 0], [1, 1], [1, 1]]
        >>> scaler = StandardScaler()
        >>> print(scaler.fit(data))
            StandardScaler()
        >>> print(scaler.mean_)
            [0.5 0.5]
        >>> print(scaler.transform(data))
            [[-1. -1.]
            [-1. -1.]
            [ 1.  1.]
            [ 1.  1.]]
        >>> print(scaler.transform([[2, 2]]))
            [[3. 3.]]
        """
        ...

    @tobtind(lib="sf")
    def add_dummy_feature(self, value: float = 1., **kwargs) -> Union[series, dataframe]:
        """Augment dataset with an additional dummy feature.

        This is useful for fitting an intercept term with implementations which
        cannot otherwise fit it directly.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            Data.

        value : float
            Value to use for the dummy feature.

        Returns
        -------
        X : {ndarray, sparse matrix} of shape (n_samples, n_features + 1)
            Same data with dummy feature added as first column.

        Examples
        --------
        >>> from sklearn.preprocessing import add_dummy_feature
        >>> add_dummy_feature([[0, 1], [1, 0]])
            array([[1., 0., 1.],
                [1., 1., 0.]])
        """
        ...

    @tobtind(lib="sf")
    def PolynomialFeatures(self, y: Optional[Iterable] = None, degree: int | tuple[int, int] = 2,
                           interaction_only: bool = False, include_bias: bool = True, order: Literal['C', 'F'] = "C", fit_params: dict = {}, **kwargs) -> Union[series, dataframe]:
        """Generate polynomial and interaction features.

        Generate a new feature matrix consisting of all polynomial combinations
        of the features with degree less than or equal to the specified degree.
        For example, if an input sample is two dimensional and of the form
        [a, b], the degree-2 polynomial features are [1, a, b, a^2, ab, b^2].

        Read more in the :ref:`User Guide <polynomial_features>`.

        Parameters
        ----------
        degree : int or tuple (min_degree, max_degree), default=2
            If a single int is given, it specifies the maximal degree of the
            polynomial features. If a tuple `(min_degree, max_degree)` is passed,
            then `min_degree` is the minimum and `max_degree` is the maximum
            polynomial degree of the generated features. Note that `min_degree=0`
            and `min_degree=1` are equivalent as outputting the degree zero term is
            determined by `include_bias`.

        interaction_only : bool, default=False
            If `True`, only interaction features are produced: features that are
            products of at most `degree` *distinct* input features, i.e. terms with
            power of 2 or higher of the same input feature are excluded:

                - included: `x[0]`, `x[1]`, `x[0] * x[1]`, etc.
                - excluded: `x[0] ** 2`, `x[0] ** 2 * x[1]`, etc.

        include_bias : bool, default=True
            If `True` (default), then include a bias column, the feature in which
            all polynomial powers are zero (i.e. a column of ones - acts as an
            intercept term in a linear model).

        order : {'C', 'F'}, default='C'
            Order of output array in the dense case. `'F'` order is faster to
            compute, but may slow down subsequent estimators.

            .. versionadded:: 0.21

        Attributes
        ----------
        powers_ : ndarray of shape (`n_output_features_`, `n_features_in_`)
            `powers_[i, j]` is the exponent of the jth input in the ith output.

        n_input_features_ : int
            The total number of input features.

            .. deprecated:: 1.0
                This attribute is deprecated in 1.0 and will be removed in 1.2.
                Refer to `n_features_in_` instead.

        n_features_in_ : int
            Number of features seen during :term:`fit`.

            .. versionadded:: 0.24

        feature_names_in_ : ndarray of shape (`n_features_in_`,)
            Names of features seen during :term:`fit`. Defined only when `X`
            has feature names that are all strings.

            .. versionadded:: 1.0

        n_output_features_ : int
            The total number of polynomial output features. The number of output
            features is computed by iterating over all suitably sized combinations
            of input features.

        See Also
        --------
        SplineTransformer : Transformer that generates univariate B-spline bases
            for features.

        Notes
        -----
        Be aware that the number of features in the output array scales
        polynomially in the number of features of the input array, and
        exponentially in the degree. High degrees can cause overfitting.

        See :ref:`examples/linear_model/plot_polynomial_interpolation.py
        <sphx_glr_auto_examples_linear_model_plot_polynomial_interpolation.py>`

        Examples
        --------
        >>> import numpy as np
        >>> from sklearn.preprocessing import PolynomialFeatures
        >>> X = np.arange(6).reshape(3, 2)
        >>> X
            array([[0, 1],
                [2, 3],
                [4, 5]])
        >>> poly = PolynomialFeatures(2)
        >>> poly.fit_transform(X)
            array([[ 1.,  0.,  1.,  0.,  0.,  1.],
                [ 1.,  2.,  3.,  4.,  6.,  9.],
                [ 1.,  4.,  5., 16., 20., 25.]])
        >>> poly = PolynomialFeatures(interaction_only=True)
        >>> poly.fit_transform(X)
            array([[ 1.,  0.,  1.,  0.],
                [ 1.,  2.,  3.,  6.],
                [ 1.,  4.,  5., 20.]])
        """
        ...

    @tobtind(lib="sf")
    def binarize(self, threshold: float = 0.0, copy: bool = True, **kwargs) -> Union[series, dataframe]:
        """Boolean thresholding of array-like or scipy.sparse matrix.

        Read more in the :ref:`User Guide <preprocessing_binarization>`.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            The data to binarize, element by element.
            scipy.sparse matrices should be in CSR or CSC format to avoid an
            un-necessary copy.

        threshold : float, default=0.0
            Feature values below or equal to this are replaced by 0, above it by 1.
            Threshold may not be less than 0 for operations on sparse matrices.

        copy : bool, default=True
            Set to False to perform inplace binarization and avoid a copy
            (if the input is already a numpy array or a scipy.sparse CSR / CSC
            matrix and if axis is 1).

        Returns
        -------
        X_tr : {ndarray, sparse matrix} of shape (n_samples, n_features)
            The transformed data.

        See Also
        --------
        Binarizer : Performs binarization using the Transformer API
            (e.g. as part of a preprocessing :class:`~sklearn.pipeline.Pipeline`).
        """
        ...

    @tobtind(lib="sf")
    def normalize(self, norm: Literal['l1', 'l2', 'max'] = "l2", axis: int = 1, copy: bool = True, return_norm: bool = False, **kwargs) -> Union[series, dataframe]:
        """Scale input vectors individually to unit norm (vector length).

        Read more in the :ref:`User Guide <preprocessing_normalization>`.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            The data to normalize, element by element.
            scipy.sparse matrices should be in CSR format to avoid an
            un-necessary copy.

        norm : {'l1', 'l2', 'max'}, default='l2'
            The norm to use to normalize each non zero sample (or each non-zero
            feature if axis is 0).

        axis : {0, 1}, default=1
            Define axis used to normalize the data along. If 1, independently
            normalize each sample, otherwise (if 0) normalize each feature.

        copy : bool, default=True
            Set to False to perform inplace row normalization and avoid a
            copy (if the input is already a numpy array or a scipy.sparse
            CSR matrix and if axis is 1).

        return_norm : bool, default=False
            Whether to return the computed norms.

        Returns
        -------
        X : {ndarray, sparse matrix} of shape (n_samples, n_features)
            Normalized input X.

        norms : ndarray of shape (n_samples, ) if axis=1 else (n_features, )
            An array of norms along given axis for X.
            When X is sparse, a NotImplementedError will be raised
            for norm 'l1' or 'l2'.

        See Also
        --------
        Normalizer : Performs normalization using the Transformer API
            (e.g. as part of a preprocessing :class:`~sklearn.pipeline.Pipeline`).

        Notes
        -----
        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.
        """
        ...

    @tobtind(lib="sf")
    def scale(self, axis=0, with_mean: bool = True, with_std: bool = True, copy=True, **kwargs) -> Union[series, dataframe]:
        """Standardize a dataset along any axis.

        Center to the mean and component wise scale to unit variance.

        Read more in the :ref:`User Guide <preprocessing_scaler>`.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            The data to center and scale.

        axis : int, default=0
            axis used to compute the means and standard deviations along. If 0,
            independently standardize each feature, otherwise (if 1) standardize
            each sample.

        with_mean : bool, default=True
            If True, center the data before scaling.

        with_std : bool, default=True
            If True, scale the data to unit variance (or equivalently,
            unit standard deviation).

        copy : bool, default=True
            set to False to perform inplace row normalization and avoid a
            copy (if the input is already a numpy array or a scipy.sparse
            CSC matrix and if axis is 1).

        Returns
        -------
        X_tr : {ndarray, sparse matrix} of shape (n_samples, n_features)
            The transformed data.

        Notes
        -----
        This implementation will refuse to center scipy.sparse matrices
        since it would make them non-sparse and would potentially crash the
        program with memory exhaustion problems.

        Instead the caller is expected to either set explicitly
        `with_mean=False` (in that case, only variance scaling will be
        performed on the features of the CSC matrix) or to call `X.toarray()`
        if he/she expects the materialized dense array to fit in memory.

        To avoid memory copy the caller should pass a CSC matrix.

        NaNs are treated as missing values: disregarded to compute the statistics,
        and maintained during the data transformation.

        We use a biased estimator for the standard deviation, equivalent to
        `numpy.std(x, ddof=0)`. Note that the choice of `ddof` is unlikely to
        affect model performance.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        .. warning:: Risk of data leak

            Do not use :func:`~sklearn.preprocessing.scale` unless you know
            what you are doing. A common mistake is to apply it to the entire data
            *before* splitting into training and test sets. This will bias the
            model evaluation because information would have leaked from the test
            set to the training set.
            In general, we recommend using
            :class:`~sklearn.preprocessing.StandardScaler` within a
            :ref:`Pipeline <pipeline>` in order to prevent most risks of data
            leaking: `pipe = make_pipeline(StandardScaler(), LogisticRegression())`.

        See Also
        --------
        StandardScaler : Performs scaling to unit variance using the Transformer
            API (e.g. as part of a preprocessing
            :class:`~sklearn.pipeline.Pipeline`).

        """
        ...

    @tobtind(lib="sf")
    def robust_scale(
        self,
        axis: int = 0,
        with_centering: bool = True,
        with_scaling: bool = True,
        quantile_range: tuple[float, float] = (25.0, 75.0),
        copy: bool = True,
        unit_variance: bool = False,
        **kwargs
    ) -> Union[series, dataframe]:
        """Standardize a dataset along any axis.

        Center to the median and component wise scale
        according to the interquartile range.

        Read more in the :ref:`User Guide <preprocessing_scaler>`.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_sample, n_features)
            The data to center and scale.

        axis : int, default=0
            Axis used to compute the medians and IQR along. If 0,
            independently scale each feature, otherwise (if 1) scale
            each sample.

        with_centering : bool, default=True
            If `True`, center the data before scaling.

        with_scaling : bool, default=True
            If `True`, scale the data to unit variance (or equivalently,
            unit standard deviation).

        quantile_range : tuple (q_min, q_max), 0.0 < q_min < q_max < 100.0,\
            default=(25.0, 75.0)
            Quantile range used to calculate `scale_`. By default this is equal to
            the IQR, i.e., `q_min` is the first quantile and `q_max` is the third
            quantile.

            .. versionadded:: 0.18

        copy : bool, default=True
            Set to `False` to perform inplace row normalization and avoid a
            copy (if the input is already a numpy array or a scipy.sparse
            CSR matrix and if axis is 1).

        unit_variance : bool, default=False
            If `True`, scale data so that normally distributed features have a
            variance of 1. In general, if the difference between the x-values of
            `q_max` and `q_min` for a standard normal distribution is greater
            than 1, the dataset will be scaled down. If less than 1, the dataset
            will be scaled up.

            .. versionadded:: 0.24

        Returns
        -------
        X_tr : {ndarray, sparse matrix} of shape (n_samples, n_features)
            The transformed data.

        See Also
        --------
        RobustScaler : Performs centering and scaling using the Transformer API
            (e.g. as part of a preprocessing :class:`~sklearn.pipeline.Pipeline`).

        Notes
        -----
        This implementation will refuse to center scipy.sparse matrices
        since it would make them non-sparse and would potentially crash the
        program with memory exhaustion problems.

        Instead the caller is expected to either set explicitly
        `with_centering=False` (in that case, only variance scaling will be
        performed on the features of the CSR matrix) or to call `X.toarray()`
        if he/she expects the materialized dense array to fit in memory.

        To avoid memory copy the caller should pass a CSR matrix.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        .. warning:: Risk of data leak

            Do not use :func:`~sklearn.preprocessing.robust_scale` unless you know
            what you are doing. A common mistake is to apply it to the entire data
            *before* splitting into training and test sets. This will bias the
            model evaluation because information would have leaked from the test
            set to the training set.
            In general, we recommend using
            :class:`~sklearn.preprocessing.RobustScaler` within a
            :ref:`Pipeline <pipeline>` in order to prevent most risks of data
            leaking: `pipe = make_pipeline(RobustScaler(), LogisticRegression())`.
        """
        ...

    @tobtind(lib="sf")
    def maxabs_scale(self, axis: int = 0, copy: bool = True, **kwargs) -> Union[series, dataframe]:
        """Scale each feature to the [-1, 1] range without breaking the sparsity.

        This estimator scales each feature individually such
        that the maximal absolute value of each feature in the
        training set will be 1.0.

        This scaler can also be applied to sparse CSR or CSC matrices.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            The data.

        axis : int, default=0
            axis used to scale along. If 0, independently scale each feature,
            otherwise (if 1) scale each sample.

        copy : bool, default=True
            Set to False to perform inplace scaling and avoid a copy (if the input
            is already a numpy array).

        Returns
        -------
        X_tr : {ndarray, sparse matrix} of shape (n_samples, n_features)
            The transformed data.

        .. warning:: Risk of data leak

            Do not use :func:`~sklearn.preprocessing.maxabs_scale` unless you know
            what you are doing. A common mistake is to apply it to the entire data
            *before* splitting into training and test sets. This will bias the
            model evaluation because information would have leaked from the test
            set to the training set.
            In general, we recommend using
            :class:`~sklearn.preprocessing.MaxAbsScaler` within a
            :ref:`Pipeline <pipeline>` in order to prevent most risks of data
            leaking: `pipe = make_pipeline(MaxAbsScaler(), LogisticRegression())`.

        See Also
        --------
        MaxAbsScaler : Performs scaling to the [-1, 1] range using
            the Transformer API (e.g. as part of a preprocessing
            :class:`~sklearn.pipeline.Pipeline`).

        Notes
        -----
        NaNs are treated as missing values: disregarded to compute the statistics,
        and maintained during the data transformation.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.
        """
        ...

    @tobtind(lib="sf")
    def minmax_scale(self, feature_range: tuple[int, int] = (0, 1), axis: int = 0, copy: bool = True, **kwargs) -> Union[series, dataframe]:
        """Transform features by scaling each feature to a given range.

        This estimator scales and translates each feature individually such
        that it is in the given range on the training set, i.e. between
        zero and one.

        The transformation is given by (when ``axis=0``)::

            X_std = (X - X.min(axis=0)) / (X.max(axis=0) - X.min(axis=0))
            X_scaled = X_std * (max - min) + min

        where min, max = feature_range.

        The transformation is calculated as (when ``axis=0``)::

        X_scaled = scale * X + min - X.min(axis=0) * scale
        where scale = (max - min) / (X.max(axis=0) - X.min(axis=0))

        This transformation is often used as an alternative to zero mean,
        unit variance scaling.

        Read more in the :ref:`User Guide <preprocessing_scaler>`.

        .. versionadded:: 0.17
        *minmax_scale* function interface
        to :class:`~sklearn.preprocessing.MinMaxScaler`.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            The data.

        feature_range : tuple (min, max), default=(0, 1)
            Desired range of transformed data.

        axis : int, default=0
            Axis used to scale along. If 0, independently scale each feature,
            otherwise (if 1) scale each sample.

        copy : bool, default=True
            Set to False to perform inplace scaling and avoid a copy (if the input
            is already a numpy array).

        Returns
        -------
        X_tr : ndarray of shape (n_samples, n_features)
            The transformed data.

        .. warning:: Risk of data leak

            Do not use :func:`~sklearn.preprocessing.minmax_scale` unless you know
            what you are doing. A common mistake is to apply it to the entire data
            *before* splitting into training and test sets. This will bias the
            model evaluation because information would have leaked from the test
            set to the training set.
            In general, we recommend using
            :class:`~sklearn.preprocessing.MinMaxScaler` within a
            :ref:`Pipeline <pipeline>` in order to prevent most risks of data
            leaking: `pipe = make_pipeline(MinMaxScaler(), LogisticRegression())`.

        See Also
        --------
        MinMaxScaler : Performs scaling to a given range using the Transformer
            API (e.g. as part of a preprocessing
            :class:`~sklearn.pipeline.Pipeline`).

        Notes
        -----
        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.
        """
        ...

    @tobtind(lib="sf")
    def label_binarize(self, classes: np.ndarray, neg_label: int = 0, pos_label: int = 1, sparse_output: bool = False, *kwargs) -> Union[series, dataframe]:
        """Binarize labels in a one-vs-all fashion.

        Several regression and binary classification algorithms are
        available in scikit-learn. A simple way to extend these algorithms
        to the multi-class classification case is to use the so-called
        one-vs-all scheme.

        This function makes it possible to compute this transformation for a
        fixed set of class labels known ahead of time.

        Parameters
        ----------
        y : array-like
            Sequence of integer labels or multilabel data to encode.

        classes : array-like of shape (n_classes,)
            Uniquely holds the label for each class.

        neg_label : int, default=0
            Value with which negative labels must be encoded.

        pos_label : int, default=1
            Value with which positive labels must be encoded.

        sparse_output : bool, default=False,
            Set to true if output binary array is desired in CSR sparse format.

        Returns
        -------
        Y : {ndarray, sparse matrix} of shape (n_samples, n_classes)
            Shape will be (n_samples, 1) for binary problems. Sparse matrix will
            be of CSR format.

        See Also
        --------
        LabelBinarizer : Class used to wrap the functionality of label_binarize and
            allow for fitting to classes independently of the transform operation.

        Examples
        --------
        >>> from sklearn.preprocessing import label_binarize
        >>> label_binarize([1, 6], classes=[1, 2, 4, 6])
        array([[1, 0, 0, 0],
            [0, 0, 0, 1]])

        The class ordering is preserved:

        >>> label_binarize([1, 6], classes=[1, 6, 4, 2])
        array([[1, 0, 0, 0],
            [0, 1, 0, 0]])

        Binary targets transform to a column vector

        >>> label_binarize(['yes', 'no', 'no', 'yes'], classes=['no', 'yes'])
        array([[1],
            [0],
            [0],
            [1]])
        """
        ...

    @tobtind(lib="sf")
    def quantile_transform(
        self,
        axis: int = 0,
        n_quantiles: int = 1000,
        output_distribution: Literal['uniform', 'normal'] = "uniform",
        ignore_implicit_zeros: bool = False,
        subsample: int = int(1e5),
        random_state: int | RandomState | None = None,
        copy: bool = True,
        **kwargs
    ) -> Union[series, dataframe]:
        """Transform features using quantiles information.

        This method transforms the features to follow a uniform or a normal
        distribution. Therefore, for a given feature, this transformation tends
        to spread out the most frequent values. It also reduces the impact of
        (marginal) outliers: this is therefore a robust preprocessing scheme.

        The transformation is applied on each feature independently. First an
        estimate of the cumulative distribution function of a feature is
        used to map the original values to a uniform distribution. The obtained
        values are then mapped to the desired output distribution using the
        associated quantile function. Features values of new/unseen data that fall
        below or above the fitted range will be mapped to the bounds of the output
        distribution. Note that this transform is non-linear. It may distort linear
        correlations between variables measured at the same scale but renders
        variables measured at different scales more directly comparable.

        Read more in the :ref:`User Guide <preprocessing_transformer>`.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            The data to transform.

        axis : int, default=0
            Axis used to compute the means and standard deviations along. If 0,
            transform each feature, otherwise (if 1) transform each sample.

        n_quantiles : int, default=1000 or n_samples
            Number of quantiles to be computed. It corresponds to the number
            of landmarks used to discretize the cumulative distribution function.
            If n_quantiles is larger than the number of samples, n_quantiles is set
            to the number of samples as a larger number of quantiles does not give
            a better approximation of the cumulative distribution function
            estimator.

        output_distribution : {'uniform', 'normal'}, default='uniform'
            Marginal distribution for the transformed data. The choices are
            'uniform' (default) or 'normal'.

        ignore_implicit_zeros : bool, default=False
            Only applies to sparse matrices. If True, the sparse entries of the
            matrix are discarded to compute the quantile statistics. If False,
            these entries are treated as zeros.

        subsample : int, default=1e5
            Maximum number of samples used to estimate the quantiles for
            computational efficiency. Note that the subsampling procedure may
            differ for value-identical sparse and dense matrices.

        random_state : int, RandomState instance or None, default=None
            Determines random number generation for subsampling and smoothing
            noise.
            Please see ``subsample`` for more details.
            Pass an int for reproducible results across multiple function calls.
            See :term:`Glossary <random_state>`.

        copy : bool, default=True
            Set to False to perform inplace transformation and avoid a copy (if the
            input is already a numpy array). If True, a copy of `X` is transformed,
            leaving the original `X` unchanged

            ..versionchanged:: 0.23
                The default value of `copy` changed from False to True in 0.23.

        Returns
        -------
        Xt : {ndarray, sparse matrix} of shape (n_samples, n_features)
            The transformed data.

        See Also
        --------
        QuantileTransformer : Performs quantile-based scaling using the
            Transformer API (e.g. as part of a preprocessing
            :class:`~sklearn.pipeline.Pipeline`).
        power_transform : Maps data to a normal distribution using a
            power transformation.
        scale : Performs standardization that is faster, but less robust
            to outliers.
        robust_scale : Performs robust standardization that removes the influence
            of outliers but does not put outliers and inliers on the same scale.

        Notes
        -----
        NaNs are treated as missing values: disregarded in fit, and maintained in
        transform.

        .. warning:: Risk of data leak

            Do not use :func:`~sklearn.preprocessing.quantile_transform` unless
            you know what you are doing. A common mistake is to apply it
            to the entire data *before* splitting into training and
            test sets. This will bias the model evaluation because
            information would have leaked from the test set to the
            training set.
            In general, we recommend using
            :class:`~sklearn.preprocessing.QuantileTransformer` within a
            :ref:`Pipeline <pipeline>` in order to prevent most risks of data
            leaking:`pipe = make_pipeline(QuantileTransformer(),
            LogisticRegression())`.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        Examples
        --------
        >>> import numpy as np
        >>> from sklearn.preprocessing import quantile_transform
        >>> rng = np.random.RandomState(0)
        >>> X = np.sort(rng.normal(loc=0.5, scale=0.25, size=(25, 1)), axis=0)
        >>> quantile_transform(X, n_quantiles=10, random_state=0, copy=True)
            array([...])
        """
        ...

    @tobtind(lib="sf")
    def power_transform(self, method: Literal['yeo-johnson', 'box-cox'] = "yeo-johnson", standardize: bool = True, copy: bool = True, **kwargs) -> Union[series, dataframe]:
        """Parametric, monotonic transformation to make data more Gaussian-like.

        Power transforms are a family of parametric, monotonic transformations
        that are applied to make data more Gaussian-like. This is useful for
        modeling issues related to heteroscedasticity (non-constant variance),
        or other situations where normality is desired.

        Currently, power_transform supports the Box-Cox transform and the
        Yeo-Johnson transform. The optimal parameter for stabilizing variance and
        minimizing skewness is estimated through maximum likelihood.

        Box-Cox requires input data to be strictly positive, while Yeo-Johnson
        supports both positive or negative data.

        By default, zero-mean, unit-variance normalization is applied to the
        transformed data.

        Read more in the :ref:`User Guide <preprocessing_transformer>`.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            The data to be transformed using a power transformation.

        method : {'yeo-johnson', 'box-cox'}, default='yeo-johnson'
            The power transform method. Available methods are:

            - 'yeo-johnson' [1]_, works with positive and negative values
            - 'box-cox' [2]_, only works with strictly positive values

            .. versionchanged:: 0.23
                The default value of the `method` parameter changed from
                'box-cox' to 'yeo-johnson' in 0.23.

        standardize : bool, default=True
            Set to True to apply zero-mean, unit-variance normalization to the
            transformed output.

        copy : bool, default=True
            Set to False to perform inplace computation during transformation.

        Returns
        -------
        X_trans : ndarray of shape (n_samples, n_features)
            The transformed data.

        See Also
        --------
        PowerTransformer : Equivalent transformation with the
            Transformer API (e.g. as part of a preprocessing
            :class:`~sklearn.pipeline.Pipeline`).

        quantile_transform : Maps data to a standard normal distribution with
            the parameter `output_distribution='normal'`.

        Notes
        -----
        NaNs are treated as missing values: disregarded in ``fit``, and maintained
        in ``transform``.

        For a comparison of the different scalers, transformers, and normalizers,
        see :ref:`examples/preprocessing/plot_all_scaling.py
        <sphx_glr_auto_examples_preprocessing_plot_all_scaling.py>`.

        References
        ----------

        .. [1] I.K. Yeo and R.A. Johnson, "A new family of power transformations to
            improve normality or symmetry." Biometrika, 87(4), pp.954-959,
            (2000).

        .. [2] G.E.P. Box and D.R. Cox, "An Analysis of Transformations", Journal
            of the Royal Statistical Society B, 26, 211-252 (1964).

        Examples
        --------
        >>> import numpy as np
        >>> from sklearn.preprocessing import power_transform
        >>> data = [[1, 2], [3, 2], [4, 5]]
        >>> print(power_transform(data, method='box-cox'))
            [[-1.332... -0.707...]
            [ 0.256... -0.707...]
            [ 1.076...  1.414...]]

        .. warning:: Risk of data leak.
            Do not use :func:`~sklearn.preprocessing.power_transform` unless you
            know what you are doing. A common mistake is to apply it to the entire
            data *before* splitting into training and test sets. This will bias the
            model evaluation because information would have leaked from the test
            set to the training set.
            In general, we recommend using
            :class:`~sklearn.preprocessing.PowerTransformer` within a
            :ref:`Pipeline <pipeline>` in order to prevent most risks of data
            leaking, e.g.: `pipe = make_pipeline(PowerTransformer(),
            LogisticRegression())`.
        """
        ...


class Pair:
    """## 配对交易

    ### method:
    #### 基础方法：
    >>> bollinger_bands_strategy:布林带
        percentage_deviation_strategy:百分比偏差
        rolling_quantile_strategy:移动窗口分位数
        z_score_strategy:Z-score

    #### 高级方法:
    >>> hurst_filter_strategy:Hurst指数过滤
        kalman_filter_strategy:卡尔曼滤波
        garch_volatility_adjusted_signals:GARCH模型
        vecm_based_signals:VECM模型"""
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    @tobtind(lines=["spread", "upper_band", "lower_band", "signals"], lib="pair")
    def bollinger_bands(self, window=60, num_std=2., **kwargs) -> dataframe:
        """使用布林带生成交易信号"""
        ...

    @tobtind(lines=["pct_deviation", "signals"], lib="pair")
    def percentage_deviation(self, window=60, threshold=0.1, **kwargs) -> dataframe:
        """使用百分比偏差生成交易信号"""
        ...

    @tobtind(lines=["spread", "upper_threshold", "lower_threshold", "signals"], lib="pair")
    def rolling_quantile(self, window=60, upper_quantile=0.95, lower_quantile=0.05, **kwargs) -> dataframe:
        """使用移动窗口分位数生成交易信号"""
        ...

    @tobtind(lines=["z_score", "signals"], lib="pair")
    def z_score(self, window=60, z_threshold=2.0, **kwargs) -> dataframe:
        """使用Z-score生成交易信号"""
        ...

    @tobtind(lines=["z_score", "signals"], lib="pair")
    def hurst_filter(self, hurst_threshold=0.5, z_threshold=2.0, **kwargs) -> dataframe:
        """使用Hurst指数过滤交易信号"""
        ...

    @tobtind(lines=["dynamic_spread", "hedge_ratios", "z_score", "signals"], lib="pair")
    def kalman_filter(self, y_series=None, z_threshold=2., **kwargs) -> dataframe:
        """使用卡尔曼滤波生成动态价差和交易信号"""
        ...

    @tobtind(lines=["volatility", "garch_z_score", "signals"], lib="pair")
    def garch_volatility_adjusted(self, z_threshold=2.0, **kwargs) -> dataframe:
        """使用GARCH模型调整波动率"""
        ...

    @tobtind(lines=["ect", "signals"], lib="pair")
    def vecm_based(self, y_series=None, window=60, lag=2, **kwargs) -> dataframe:
        """VECM模型"""
        ...


class Factors:
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    @tobtind(lines=["combined_score", "signals"], lib="factor")
    def single_asset_multi_factor_strategy(self, *factors: pd.DataFrame, window=10, top_pct=0.2, bottom_pct=0.2, isstand=True, **kwargs):
        ...

    @tobtind(lib="factor")
    def pca_trend_indicator(self, *factors: pd.DataFrame, n_components=2,
                            dynamic_sign=True, filter_low_variance=True):
        ...

    @tobtind(overlap=True, lib="factor")
    def adaptive_weight_trend(self, windows=[5, 20, 50], lookback=10, **kwargs):
        ...

    @tobtind(lines=["merged_factor", "signals"], lib="factor")
    def factor_optimizer(self, *factors: pd.DataFrame,
                         max_weight: float = 0.8, l2_reg: float = 0.0001,
                         min_ic_abs: float = 0.03, n_init_points: int = 10,
                         optimization_model: str = "scipy", **kwargs):
        ...


class CoreIndicators:
    """核心指标"""
    _df: series | dataframe

    def __init__(self, data):
        self._df = data

    @property
    def indicators(self) -> CoreFunc:
        return self._df.ta


class dataframe(IndicatorsBase, pd.DataFrame, PandasTa, TaLib):
    """
        # 框架内置指标数据容器类（dataframe 类型）
        核心定位：继承 pandas.DataFrame 并整合指标计算、可视化配置、交易信号管理能力，作为系统统一的多列指标数据格式

        核心特性：
        1. 多父类融合：
        - 继承 `pd.DataFrame`：保留原生 DataFrame 的数据存储与计算能力（如索引、切片、列操作）
        - 继承 `IndicatorsBase`：获得指标基础属性与方法（如指标ID、分类标识）
        - 继承 `PandasTa`/`TaLib`：直接调用 pandas_ta、TaLib 库的技术指标计算接口
        2. 指标化增强：
        - 将每列数据自动封装为 `Line` 类型（框架内置单指标序列），支持指标属性（如绘图样式、信号标记）
        - 内置指标元数据管理（`_plotinfo` 绘图配置、`_indsetting` 指标设置），无需额外定义
        3. 交易信号原生支持：
        - 内置多头/空头开仓/离场信号（`long_signal`/`short_signal`/`exitlong_signal`/`exitshort_signal`）
        - 支持信号样式自定义（颜色、标记、大小等），直接关联绘图逻辑
        4. 可视化配置集成：
        - 支持线型（`line_style`）、信号样式（`signal_style`）的批量/单独设置
        - 自动适配框架绘图模块，无需手动传递绘图参数
        5. 数据兼容性：
        - 支持多种输入数据类型（`pd.DataFrame`/`np.ndarray`/列表/元组/字典），自动转换为标准格式
        - 提供 `to_lines()`/`to_ndarray()` 方法，便捷转换为 `Line` 序列或 numpy 数组


        初始化参数说明：
        Args:
            data: 输入数据，支持以下类型：
                - pd.DataFrame：直接使用已有 DataFrame，列名自动作为指标线名称
                - np.ndarray：numpy 数组，需通过 `kwargs` 指定 `lines`（指标线名称）
                - tuple/list：整数序列（如 (100, 3) 表示 100 行 3 列），自动生成全 NaN 数组（标记为自定义数据）
                - dict：键为列名、值为数据的字典，自动转换为 DataFrame
            **kwargs: 额外配置参数（核心参数如下）：
                - lines (list[str]): 指标线名称列表，未指定时自动读取 DataFrame 列名
                - id (BtID): 指标唯一标识（默认自动生成），用于指标区分与管理
                - isplot (bool/dict): 是否绘图（True/False 或按列名配置的字典），默认 True
                - category (str): 指标分类（如 "candles"/"momentum"，默认 Category.Any）
                - overlap (bool): 是否与主图重叠显示（默认 False）
                - isha/islr (bool): 是否为 Heikin-Ashi 蜡烛图/线性回归指标（默认 False）
                - ismain (bool): 是否为主图指标（默认 False）
                - isindicator (bool): 是否为技术指标（默认 True，非指标数据设为 False）
                - iscustom (bool): 是否为自定义数据（默认 False，列表/元组输入时自动设为 True）
                - height (int): 指标绘图高度（蜡烛图默认 300，其他默认 150）


        核心属性说明：
        1. 数据与指标基础属性：
        - series: 转换为框架内置 `seriesType`（单列指标容器）
        - _plotinfo: `PlotInfo` 实例，存储绘图配置（如高度、线型、信号样式、指标分类）
        - _indsetting: `IndSetting` 实例，存储指标元数据（如指标ID、维度、自定义标识）
        - _dataset: `DataFrameSet` 实例，管理数据副本与缓存
        2. 交易信号属性（支持赋值与读取）：
        - long_signal: 多头开仓信号（需为与数据长度一致的可迭代对象）
        - exitlong_signal: 多头离场信号
        - short_signal: 空头开仓信号
        - exitshort_signal: 空头离场信号
        3. 样式配置属性（支持批量/单独设置）：
        - signal_style: 信号样式（标记、颜色、大小等），返回 `SignalStyleType` 实例
        - line_style: 指标线型（线型、线宽、颜色等），返回 `LineStyleType` 实例
        - signal_color/line_color: 单独设置信号/线型颜色，返回 `SignalAttrType`/`LineAttrType` 实例
        - 其他样式属性：signal_key（信号位置）、signal_size（信号大小）、line_dash（线型虚实）等


        核心方法说明：
        1. assign(**kwargs): 扩展列并返回新的 `dataframe` 实例，支持保留原数据（`keep=True`）
        2. to_lines(*args): 将指定列（整数索引或列名）转换为 `Line` 序列，返回元组
        3. to_ndarray(): 将所有列转换为 numpy 数组，返回元组


        使用示例：
        >>> # 1. 从 DataFrame 初始化指标 dataframe
        >>> raw_df = pd.DataFrame({"close": [100, 101, 102, 103], "ma5": [99, 100, 101, 102]})
        >>> ind_df = dataframe(raw_df, category="overlap", isplot=True)
        >>> 
        >>> # 2. 设置多头信号
        >>> ind_df.long_signal = [0, 1, 0, 1]  # 第2、4期为多头开仓信号
        >>> 
        >>> # 3. 自定义信号样式
        >>> ind_df.signal_style.long_signal = SignalStyle("low", Colors.blue, Markers.circle_dot, size=25)
        >>> 
        >>> # 4. 转换为 Line 序列
        >>> close_line, ma5_line = ind_df.to_lines("close", "ma5")
        >>> 
        >>> # 5. 调用 pandas_ta 指标（继承自 PandasTa）
        >>> rsi_df = ind_df.rsi(length=14)
        """

    def __init__(self, data: pd.DataFrame | np.ndarray | tuple[int] | list[int] | dict, **kwargs) -> None:
        if isinstance(data, dict):  # 字典
            data = pd.DataFrame(data)
        if isinstance(data, (tuple, list)):  # 自定义数据
            assert len(data) > 1, "维度shape的长度必须大于1"
            assert all([isinstance(num, int)
                       for num in data]), "传入数据为数组时元素必须为整数"
            # lines = [f"lines{i}" for i in range(data[1])]
            data = np.full(data, np.nan)
            kwargs.update(dict(iscustom=True))  # , lines=lines))
        if 'lines' not in kwargs:
            # 没定义lines时采用pd.DataFrame的列名
            if isinstance(data, pd.DataFrame):
                kwargs['lines'] = list(data.columns)

        super().__init__(data, columns=kwargs.pop("lines"))
        # assert lines in kwargs
        btid = kwargs.pop("id", BtID())
        if isinstance(btid, dict):
            btid = BtID(**btid)
        if not isinstance(btid, BtID):
            btid = BtID()
        lines: list[str] = list(self.columns)
        isplot: bool | dict = kwargs.pop('isplot', True)
        if not isinstance(isplot, (bool, dict)):
            isplot = True
        category = kwargs.pop('category', Category.Any)
        if not isinstance(category, str) or not category:
            category = Category.Any
        overlap = kwargs.pop('overlap', False)
        isha: bool = kwargs.pop('isha', False)
        islr: bool = kwargs.pop('islr', False)
        iscandles = "candles" in category
        sname = kwargs.pop('sname', 'name')
        ind_name = kwargs.pop("ind_name", "ind_name")
        candlestyle = iscandles and CandleStyle() or None
        is_mir = kwargs.pop('_is_mir', False)
        ismain = bool(kwargs.pop('ismain', False))
        isreplay = bool(kwargs.pop('isreplay', False))
        isresample = bool(kwargs.pop('isresample', False))
        isindicator = bool(kwargs.pop('isindicator', True))
        iscustom = bool(kwargs.pop('iscustom', False))
        height = kwargs.pop("height", iscandles and 300 or 150)
        linestyle = kwargs.pop("linestyle", {})
        signalstyle = kwargs.pop("signalstyle", {})
        spanstyle = kwargs.pop("spanstyle", {})
        isMDim = True
        v, h = self.shape
        dim_match = kwargs.pop("dim_match", True)
        span = kwargs.pop("spanstyle", np.nan)
        # if isresample:
        #     btid.resample_id = btid.data_id
        # if isreplay:
        #     btid.replay_id = btid.data_id
        # 指标是否有交易信号
        signallines = [string for string in SIGNAL_Str if string in lines]
        # 将dataframe每列设置为Line
        line_filed: list[str] = list(map(lambda x: '_'+x, lines))
        self._plotinfo = PlotInfo(
            height=height,
            sname=sname,
            ind_name=ind_name,
            lines=lines,
            signallines=signallines,
            category=category,
            isplot=isplot,
            overlap=overlap,
            candlestyle=candlestyle,
            linestyle=linestyle,
            signalstyle=signalstyle,
            spanstyle=span,
        )

        self._indsetting = IndSetting(
            btid,
            is_mir,
            isha,
            islr,
            ismain,
            isreplay,
            isresample,
            isindicator,
            iscustom,
            isMDim,
            dim_match,
            v,
            h,
            v-1,
            line_filed
        )
        # 名称前加下划线,定义每列数据为Line数据
        for i, line in enumerate(line_filed):
            setattr(self, line, Line(
                self, self.values[:,
                    i], iscustom=iscustom, id=btid.copy(), sname=lines[i],
                    ind_name=ind_name, lines=[
                        lines[i],], category=Category.Any,
                    isplot=self._plotinfo.isplot[lines[i]
                                                 ], ismain=ismain, isreplay=isreplay,
                    isresample=isresample, overlap=self._plotinfo.overlap[lines[i]]))
        # 邦定property函数,dataframe每列返回的是Line指标数据
        [set_property(self.__class__, attr) for attr in lines]

        self._dataset = DataFrameSet(self.copy())
        if self._indsetting.iscustom:
            self._dataset.custom_object = self.values
        self.cache = Cache(maxsize=np.inf)

    @property
    def series(self) -> seriesType:
        return seriesType(self)

    def assign(self, keep=True, **kwargs) -> dataframe:
        """Assign new columns to a DataFrame.

        Returns a new object with all original columns in addition to new ones.
        Existing columns that are re-assigned will be overwritten.

        Parameters
        ----------
        keep : bool,default True.

        **kwargs : dict of {str: callable or Series}
            The column names are keywords. If the values are
            callable, they are computed on the DataFrame and
            assigned to the new columns. The callable must not
            change input DataFrame (though pandas doesn't check it).
            If the values are not callable, (e.g. a Series, scalar, or array),
            they are simply assigned.

        Returns
        -------
        DataFrame
            A new DataFrame with the new columns in addition to
            all the existing columns.
        """
        kwargs.update(dict(keep=keep))
        return _assign(self, **kwargs)

    def __set_signal_line(self, name, value):
        signal = Line(self, np.ndarray(value), iscustom=self.iscustom, id=self.id.copy(), sname=name,
                      ind_name=self.ind_name, lines=[
            name,], category=self.category,
            isplot=True, ismain=self.ismain, isreplay=self.isreplay,
            isresample=self.isresample, overlap=True)
        signal._plotinfo.signalstyle.update(
            {name: default_signal_style(name)})
        setattr(self, f"_{name}", signal)
        if name not in self._plotinfo.signallines:
            self.lines.append(name)
            self.isplot.update({name: True})
            self.overlap.update({name: True})
            self._indsetting.line_filed.append(f"_{name}")
            set_property(self.__class__, name)

    @property
    def long_signal(self) -> Line | None:
        """### 多头交易信号"""
        return getattr(self, "_long_signal")

    @long_signal.setter
    def long_signal(self, value) -> None:
        if isinstance(value, Iterable) and len(value) == self.V:
            self.__set_signal_line("long_signal", value)

    @property
    def exitlong_signal(self) -> Line | None:
        """### 多头离场交易信号"""
        return getattr(self, "_exitlong_signal")

    @exitlong_signal.setter
    def exitlong_signal(self, value) -> None:
        if isinstance(value, Iterable) and len(value) == self.V:
            self.__set_signal_line("exitlong_signal", value)

    @property
    def short_signal(self) -> series | None:
        """### 空头交易信号"""
        return getattr(self, "_short_signal")

    @short_signal.setter
    def short_signal(self, value) -> None:
        if isinstance(value, Iterable) and len(value) == self.V:
            self.__set_signal_line("short_signal", value)

    @property
    def exitshort_signal(self) -> series | None:
        """### 空头离场交易信号"""
        return getattr(self, "_exitshort_signal")

    @exitshort_signal.setter
    def exitshort_signal(self, value) -> None:
        if isinstance(value, Iterable) and len(value) == self.V:
            self.__set_signal_line("exitshort_signal", value)

    @property
    def signal_style(self) -> SignalStyleType:
        """### 信号指标线型设置

        Returns:
            SignalStyleType: 将指定指标线设置SignalStyle

        Example:
        >>> self.test.signal_style.long_signal = SignalStyle(
                "low", Colors.blue, Markers.circle_dot, size=25)

        ### Setter:将所有指标线设置统一SignalStyle
        >>> self.test.signal_style = SignalStyle(
                "low", Colors.blue, Markers.circle_dot, size=25)
        """
        return SignalStyleType(self)

    @signal_style.setter
    def signal_style(self, value):
        self._plotinfo.signal_style = value

    @property
    def signal_key(self) -> SignalAttrType:
        """### 信号指标属性key设置


        Returns:
            SignalAttrType: 将指定信号指标线SignalStyle设置属性key

        Example:
        >>> self.test.signal_key.long_signal = "low"

        ### Setter:将所有指标线LineStyle属性line_color统一设置
        >>> self.test.line_color = Colors.red
        """
        return SignalAttrType(self, "key")

    @signal_key.setter
    def signal_key(self, value):
        self._plotinfo.signal_key = value

    @property
    def signal_show(self) -> SignalAttrType:
        return SignalAttrType(self, "show")

    @signal_show.setter
    def signal_show(self, value):
        self._plotinfo.signal_show = value

    @property
    def signal_color(self) -> SignalAttrType:
        return SignalAttrType(self, "color")

    @signal_color.setter
    def signal_color(self, value):
        self._plotinfo.signal_color = value

    @property
    def signal_overlap(self) -> SignalAttrType:
        return SignalAttrType(self, "overlap")

    @signal_overlap.setter
    def signal_overlap(self, value):
        self._plotinfo.signal_overlap = value

    @property
    def signal_size(self) -> SignalAttrType:
        return SignalAttrType(self, "size")

    @signal_size.setter
    def signal_size(self, value):
        self._plotinfo.signal_size = value

    @property
    def line_style(self) -> LineStyleType:
        """### 线型设置

        Returns:
            LineStyleType: 将指定指标线设置LineStyle

        Example:
        >>> self.test.line_style.long_signal = LineStyle(
                LineDash.dashdot, 3, Colors.red)

        ### Setter:将所有指标线设置统一LineStyle
        >>> self.test.line_style = LineStyle(
                LineDash.dashdot, 3, Colors.red)
        """
        return LineStyleType(self)

    @line_style.setter
    def line_style(self, value):
        if self.isindicator:
            self._plotinfo.line_style = value
            if self._indsetting.isMDim:
                for line in self.line:
                    line._plotinfo.line_style = value

    @property
    def line_dash(self) -> LineAttrType:
        """### 线型属性line_dash设置

        Returns:
            LineAttrType: 将指定指标线LineStyle设置属性line_dash

        Example:
        >>> self.test.line_dash.long_signal = LineDash.solid

        ### Setter:将所有指标线LineStyle属性line_dash统一设置
        >>> self.test.line_dash = LineDash.dashdot
        """
        return LineAttrType(self, "line_dash")

    @line_dash.setter
    def line_dash(self, value):
        if self.isindicator:
            self._plotinfo.line_dash = value
            if self._indsetting.isMDim:
                for line in self.line:
                    line._plotinfo.line_dash = value

    @property
    def line_width(self) -> LineAttrType:
        """### 线型属性line_width设置


        Returns:
            LineAttrType: 将指定指标线LineStyle设置属性line_width

        Example:
        >>> self.test.line_width.long_signal = 3

        ### Setter:将所有指标线LineStyle属性line_width统一设置
        >>> self.test.line_width = 3
        """
        return LineAttrType(self, "line_width")

    @line_width.setter
    def line_width(self, value):
        if self.isindicator:
            self._plotinfo.line_width = value
            if self._indsetting.isMDim:
                for line in self.line:
                    line._plotinfo.line_width = value

    @property
    def line_color(self) -> LineAttrType:
        """### 线型属性line_color设置


        Returns:
            LineAttrType: 将指定指标线LineStyle设置属性line_color

        Example:
        >>> self.test.line_color.long_signal = 3

        ### Setter:将所有指标线LineStyle属性line_color统一设置
        >>> self.test.line_color = Colors.red
        """
        return LineAttrType(self, "line_color")

    @line_color.setter
    def line_color(self, value):
        if self.isindicator:
            self._plotinfo.line_color = value
            if self._indsetting.isMDim:
                for line in self.line:
                    line._plotinfo.line_color = value

    def to_lines(self, *args: Union[int, str]) -> tuple[Union[series, Line]]:
        """## 返回多列series"""
        if not args:
            args = self._indsetting.line_filed
        else:
            assert all([isinstance(arg, (int, str))
                        for arg in args]), f"参数为整数或字符串并在{self._indsetting.line_filed}中"
        return (getattr(self, arg if isinstance(arg, str) else self._indsetting.line_filed) for arg in args)

    def to_ndarray(self) -> tuple[np.ndarray]:
        """返回多列np.ndarray"""
        return (line.values for line in self.to_lines())


class BtData(dataframe):
    """### 框架内置K线数据核心类（继承 dataframe 类）
        核心定位：封装标准化K线数据（OHLCV等），整合合约信息、交易执行、风险控制、周期转换等量化交易全流程能力，是回测与实盘的核心数据载体

        核心特性：
        1. K线数据标准化：
        - 强制要求输入数据包含 `FILED.ALL` 定义的所有核心字段（datetime/open/high/low/close/volume/symbol等）
        - 自动补充合约基础信息（最小变动单位 `price_tick`、合约乘数 `volume_multiple` 等），实盘模式自动从TqApi获取，回测模式用默认配置
        2. 多模式兼容：
        - 回测模式：关联 `Broker` 类管理虚拟账户、持仓、手续费、保证金等
        - 实盘模式：对接天勤TqApi，自动关联 `TqObjs`（合约报价、持仓、目标仓位任务）
        3. 交易能力原生集成：
        - 直接提供开仓（`buy`/`sell`）、目标仓位设置（`set_target_size`）等交易接口
        - 内置手续费（固定/百分比/按tick）、滑点（`slip_point`）、保证金率（`margin_rate`）配置
        4. 风险控制工具：
        - 支持止损止盈（`_set_stop` 绑定 `Stop` 停止器），自动生成止损止盈线（`stop_lines`）
        - 实时计算持仓浮动盈亏（`float_profit`）、持仓成本（`cost_price`）、保证金（`margin`）等风险指标
        5. 数据增强与转换：
        - 支持K线周期转换（`resample` 重采样、`replay` 回放），回测模式下可自定义周期规则
        - 内置特殊K线生成（Heikin-Ashi布林带K线、Linear Regression线性回归K线）
        6. 因子分析支持：
        - 提供 `factors_analyzer` 方法，支持多因子（如技术指标）的标准化、去极值处理，以及与收益率的关联分析
        7. 可视化配置：
        - 继承 `dataframe` 的绘图配置能力，自动适配蜡烛图样式（涨跌颜色 `bull_color`/`bear_color`）
        - 实盘/回测模式下自动同步K线绘图数据，无需额外配置


        初始化参数说明：
        Args:
            data (pd.DataFrame): 输入K线数据，必须满足：
                                - 类型为 pd.DataFrame
                                - 列名包含 `FILED.ALL` 定义的所有核心字段（如 datetime、open、high、low、close、volume、symbol、duration 等）
            **kwargs: 额外配置参数（核心参数如下）：
                    - follow (bool): 是否跟随主图显示（默认 True，蜡烛图类指标生效）
                    - plot_index (list[int]): 绘图时的索引范围（默认 None，显示全部数据）
                    - kline_object/source_object/conversion_object: 数据副本分类（分别存储原始K线、源数据、转换后数据，默认自动生成）
                    - tq_object: 实盘模式下的TqApi数据对象（默认 None，自动关联）
                    - isindicator (bool): 是否标记为指标（固定为 False，因 BtData 是K线数据而非指标）


        核心属性说明：
        1. 基础K线数据（自动从输入数据封装为 `series` 类型）：
        - datetime: 时间序列（格式统一为 "%Y-%m-%d %H:%M:%S"）
        - open/high/low/close: 开盘价/最高价/最低价/收盘价序列
        - volume: 成交量序列
        2. 合约信息（`symbol_info` 为 `SymbolInfo` 实例）：
        - symbol: 合约名称（如 "SHFE.rb2410"）
        - cycle: K线周期（单位：秒，如 60 表示1分钟线）
        - price_tick: 最小变动单位（如 0.01 元/吨）
        - volume_multiple: 合约乘数（每手对应标的物数量，如 10 吨/手）
        3. 交易与风险相关：
        - account: 关联的账户对象（回测为 `BtAccount`，实盘为 `TqAccount`）
        - broker: 回测模式下的交易代理（`Broker` 实例，管理订单、持仓、手续费）
        - position: 持仓对象（回测为 `BtPosition`，实盘为 `TqPosition`）
        - stop: 止损止盈停止器（`Stop` 实例，需通过 `_set_stop` 绑定）
        - stop_lines: 止损止盈线数据（`dataframe` 类型，含 stop_price/target_price 列）
        4. 实盘专属属性：
        - quote: 实盘实时报价（`Quote` 实例，含最新价格、买一卖一等）
        - TargetPosTask: 实盘目标仓位任务（需传入仓位大小，返回 TqApi 的 TargetPosTask 实例）
        5. 状态与配置：
        - current_close/current_datetime: 当前周期的收盘价/时间（随回测/实盘进度动态更新）
        - Heikin_Ashi_Candles/Linear_Regression_Candles: 是否启用特殊K线（布尔值，赋值后自动生成对应K线）


        核心方法说明：
        1. 交易执行：
        - buy(size=1, stop=None, **kwargs): 多头开仓（size为手数，stop为绑定的止损器）
        - sell(size=1, stop=None, **kwargs): 空头开仓/多头平仓（逻辑由策略实例统一管理）
        - set_target_size(size=0, stop=None): 设置目标仓位（0 表示平仓，正数为多仓，负数为空仓）
        2. 数据转换：
        - resample(cycle, rule=None, **kwargs): K线周期重采样（如1分钟线转5分钟线，回测模式生效）
        - replay(cycle, rule=None, **kwargs): K线周期回放（模拟实时数据推送，回测模式生效）
        3. 因子分析：
        - factors_analyzer(*factors, periods=[1,3,5,10], n_groups=5, **kwargs): 多因子分析（支持去极值、标准化，输出因子与收益率关联数据）
        4. 快速启动：
        - run(*args, **kwargs): 快速创建策略并启动回测（传入指标配置、交易逻辑 `next` 函数，返回 `Bt` 实例）


        使用示例：
        >>> #1. 回测模式：从本地数据初始化K线
        >>> self.data = self.get_data(LocalDatas.test)

        >>> #2. 配置手续费与保证金
        >>> btdata.fixed_commission = 1.5  # 每手固定手续费1.5元
        >>> btdata.margin_rate = 0.08      # 保证金率8%

        >>> #3. 绑定止损器（假设Stop为自定义停止器类）
        >>> self.data.buy(stop=BBtStop.TimeSegmentationTracking)

        >>> # 4. 实盘模式：通过TqApi关联合约（需先初始化TqApi）
        >>> self.data.set_target_size(2)  # 实盘设置目标多仓2手

        >>> # 5. 快速启动回测
        >>> def next(strategy):
        ...     # 简单均线交叉策略：5日线穿10日线开多
        ...     if strategy.ma5.new > strategy.ma10.new and strategy.ma5.prev < strategy.ma10.prev:
        ...         strategy.btdata.buy(size=1)
        >>> # 初始化并启动
        >>> bt = btdata.run(
        ...     ["ma5", Multiply(PandasTa.sma, dict(length=5))],
        ...     ["ma10", Multiply(PandasTa.sma, dict(length=10))],
        ...     next=next
        ... )

        """
    _btdata_setting: BtDataSetting

    def __init__(self, data: pd.DataFrame, **kwargs) -> None:
        assert isinstance(data, pd.DataFrame), "参数data数据只能为pd.DataFrame"
        assert set(data.columns).issuperset(
            FILED.ALL), f"data数据列名至少包括{FILED.ALL}"
        if self._is_live_trading:
            *_, symbol, duration = data.loc[0]
            if symbol not in self._tqobjs:
                self._tqobjs.update({symbol: TqObjs(symbol)})
            tqobj = self._tqobjs[symbol]
            data.add_info(**SymbolInfo(
                symbol, int(duration), tqobj.Quote.price_tick, tqobj.Quote.volume_multiple).vars)
        elif not set(data.columns).issuperset(FILED.Quote):
            data.add_info(**default_symbol_info(data))
        data = data[FILED.Quote]
        kwargs.update(dict(isindicator=False))
        super().__init__(data[FILED.ALL], **kwargs)
        * _, symbol, cycle, price_tick, volume_multiple = data.loc[0]
        symbol_info = SymbolInfo(
            symbol, cycle, price_tick, volume_multiple)
        isstop: bool = False
        stop: Stop = None
        stop_lines = None
        # stop_lines: dataframe = dataframe((self.shape[0], 2), id=self.id.copy(), isplot=True, overlap=True, lines=[
        #     'stop_price', 'target_price'], sname="stop_lines", ind_name="stop_lines")
        current_close = self.pandas_object.close.values
        current_datetime = self.pandas_object.datetime.dt.strftime(
            "%Y-%m-%d %H:%M:%S").values
        tradable: bool = True
        istrader: bool = False
        follow: bool = kwargs.pop("follow", True)
        plot_index: Optional[list[int]] = kwargs.pop("plot_index", None)
        self._btdatasetting = BtDataSetting(
            symbol_info,
            current_close,
            current_datetime,
            isstop,
            stop,
            stop_lines,
            tradable,
            istrader,
            follow,
            plot_index,
        )

        self._dataset = DataFrameSet(data, kline_object=kwargs.pop("kline_object", None), source_object=kwargs.pop(
            "source_object", data.copy()), conversion_object=kwargs.pop("conversion_object", None), custom_object=kwargs.pop("custom_object", None), tq_object=kwargs.pop("tq_object", None))
        self._plotinfo.set_default_candles(current_close[-1])
        kw = {"index": kwargs.pop("index")} if "index" in kwargs else {}
        if self._dataset.kline_object is not None:
            kw = dict(index=self.id.data_id)
        if not self._is_live_trading and self._strategy_instances:
            self._broker = Broker(self, **kw)

    def factors_analyzer(self, *factors: BtIndType, periods=[1, 3, 5, 10], n_groups=5, winsorize=True, standardize=True, **kwargs):
        if not factors:
            return
        factors_df = pd.DataFrame()
        factors_df["datetime"] = pd.to_datetime(self.pandas_object.datetime)
        for factor in factors:
            if type(factor) in BtIndType:
                lines = factor.lines
                if len(lines) == 1:
                    factors_df[lines[0]] = factor.values
                else:
                    factors_df = pd.concat([factors_df, factor], axis=1)

        if len(factors_df.columns) <= 1:
            return
        single = False
        lines = list(factors_df.columns)
        lines.pop(0)
        analysis_type = 'multi'
        if len(lines) == 1:
            single = True
            lines = lines[0]
            analysis_type = 'single'

        prices = self.close.values
        returns = pd.Series(prices).pct_change()
        factors_df['return'] = returns.values
        factors_df.fillna(0., inplace=True)
        fitl_cols = ["datetime", "return"]
        if winsorize or standardize:
            factors_df = factors_df.copy()
            # 去极值（Winsorization）
            if winsorize:
                for col in factors_df.columns:
                    if col not in fitl_cols:
                        q_low = factors_df[col].quantile(0.05)
                        q_high = factors_df[col].quantile(0.95)
                        factors_df.loc[:, col] = factors_df[col].clip(
                            q_low, q_high)

            # 标准化
            if standardize:
                from sklearn.preprocessing import StandardScaler
                scaler = StandardScaler()
                factor_cols = [
                    col for col in factors_df.columns if col not in fitl_cols]
                factors_df.loc[:, factor_cols] = scaler.fit_transform(
                    factors_df[factor_cols])
        factors_df.lines = lines
        factors_df.analysis_type = analysis_type
        factors_df.periods = periods
        factors_df.n_groups = n_groups
        self.factors_df = factors_df

    def _inplace_values(self):
        """内部函数不要使用"""
        new_datas = self._dataset.tq_object.copy()[FILED.ALL]
        new_datas.datetime = new_datas.datetime.apply(time_to_datetime)
        self._inplace_pandas_object_values(new_datas)
        cols = list(new_datas.columns)
        for i, line in enumerate(self._indsetting.line_filed):
            line: Line = getattr(self, line)
            line._inplace_pandas_object_values(new_datas[cols[i]])

    @property
    def follow(self) -> bool:
        if not self.category in CandlesCategory:
            return True
        return self._btdatasetting.follow

    @follow.setter
    def follow(self, value: bool):
        self._btdatasetting.follow = bool(value)

    @property
    def current_close(self) -> Optional[float]:
        """### 当前收盘价"""
        if self.btindex < self.length:
            return self._btdatasetting.current_close[self.btindex]

    @property
    def current_datetime(self) -> Optional[str]:
        """### 当前日期"""
        if self.btindex < self.length:
            return self._btdatasetting.current_datetime[self.btindex]

    @property
    def symbol_info(self) -> SymbolInfo:
        """### 合约信息"""
        return self._btdatasetting.symbol_info

    @property
    def symbol(self) -> str:
        """### 合约名称"""
        return self._btdatasetting.symbol_info.symbol

    @property
    def cycle(self) -> int:
        """### 合约周期"""
        return self._btdatasetting.symbol_info.cycle

    @property
    def price_tick(self) -> float:
        """### 合约最小变动单位"""
        return self._btdatasetting.symbol_info.price_tick

    @price_tick.setter
    def price_tick(self, value: float):
        """### 合约最小变动单位"""
        if isinstance(value, (float, int)) and value > 0.:
            self._btdatasetting.symbol_info.price_tick = float(value)
            self._broker.price_tick = float(value)

    @property
    def volume_multiple(self) -> float:
        """### 合约剩数,即合约最小波动单位的价值"""
        return self._btdatasetting.symbol_info.volume_multiple

    @volume_multiple.setter
    def volume_multiple(self, value: float):
        """### 合约剩数,即合约最小波动单位的价值"""
        if isinstance(value, (float, int)) and value > 0.:
            self._btdatasetting.symbol_info.volume_multiple = float(value)
            self._broker.volume_multiple = float(value)

    @property
    def kline(self) -> pd.DataFrame:
        """### 原始K线数据"""
        return self._dataset.source_object

    @property
    def quote(self) -> Quotes | Quote:
        if self.islivetrading:
            return self._tqobjs[self.symbol].Quote
        else:
            return Quotes(self.datetime.new, self.open.new, self.high.new, self.low.new, self.close.new, self.volume.new, self.price_tick, self.volume_multiple, self.tick_value)

    def TargetPosTask(self, size: int):
        """## 实盘时使用"""
        if self._is_live_trading:
            return self._tqobjs[self.symbol].TargetPosTask(size)

    @property
    def commission(self) -> dict:
        """### 手续费"""
        return self._broker.commission

    @property
    def tick_commission(self, value: float) -> Optional[float]:
        """### 每手手续费为波动一个点的价值的倍数"""
        return self._broker.commission.get("tick_commission", None)

    @tick_commission.setter
    def tick_commission(self, value: float):
        if isinstance(value, (float, int)) and value >= 0.:
            self._broker._setcommission(dict(tick_commission=float(value)))

    @property
    def percent_commission(self, value: float) -> Optional[float]:
        """### 每手手续费为每手价值的百分比"""
        return self._broker.commission.get("percent_commission", None)

    @percent_commission.setter
    def percent_commission(self, value: float):
        if isinstance(value, (float, int)) and value >= 0.:
            self._broker._setcommission(dict(percent_commission=float(value)))

    @property
    def fixed_commission(self) -> Optional[float]:
        """### 每手手续费为固定手续费"""
        return self._broker.commission.get("fixed_commission", None)

    @fixed_commission.setter
    def fixed_commission(self, value: float):
        if isinstance(value, (float, int)) and value >= 0.:
            self._broker._setcommission(dict(fixed_commission=float(value)))

    @property
    def slip_point(self) -> float:
        """### 每手手续费为固定手续费"""
        return self._broker.slip_point

    @slip_point.setter
    def slip_point(self, value: float):
        if isinstance(value, (float, int)) and value >= 0.:
            self._broker._setslippoint(value)

    def _set_stop(self, stop: Stop, **kwargs) -> BtData:
        """### 设置停止器

        Args:
            stop (Stop, optional): 停止器. Defaults to None.

        Kwargs:
            stop_plot (bool, optional): 停止线是否画图. Defaults to True.
            stop_mode (StopMode, optional): 停止模式. Defaults to None.
            data_length (int):引用数据的长度. Defaults to 300.

        Returns:
            BtData
        """
        if stop and (issubclass(stop.func, Stop) if isinstance(stop, partial) else issubclass(stop, Stop)):
            self._btdatasetting.isstop = True
            self._btdatasetting.set_default_stop_lines(self.id)
            self._btdatasetting.stop = stop()(self, **kwargs)
        return self

    @property
    def _stop_mode(self) -> StopMode | None:
        return self._btdatasetting.stop.mode if self._btdatasetting.stop else None

    @property
    def stop(self) -> Stop | None:
        """停止器"""
        return self._btdatasetting.stop

    @property
    def stop_lines(self) -> dataframe:
        """停止线数据"""
        return self._btdatasetting.stop_lines

    @property
    def stop_price(self) -> series:
        """停止价"""
        return self._btdatasetting.stop_lines.stop_price

    @property
    def target_price(self) -> series:
        return self._btdatasetting.stop_lines.target_price

    @property
    def account(self) -> BtAccount | TqAccount:
        """策略账户"""
        return self.strategy_instance._account

    def buy(self, size: int = 1, stop=None, **kwargs):
        self.strategy_instance.buy(data=self, size=size, stop=stop, **kwargs)

    def sell(self, size: int = 1, stop=None, **kwargs):
        self.strategy_instance.sell(data=self, size=size, stop=stop, **kwargs)

    def set_target_size(self, size: int = 0, stop=None):
        self.strategy_instance.set_target_size(self, size)

    @property
    def step_margin(self) -> list[float] | float:
        """### 逐笔保证金"""
        if self._is_live_trading:
            self.position.margin
        else:
            return self._broker._step_margin

    @property
    def margin(self) -> float:
        """### 保证金"""
        if self._is_live_trading:
            return self.position.margin
        else:
            return self._broker._margin

    @property
    def margin_rate(self) -> float:
        """### 保证金"""
        if not self._is_live_trading:
            return self._broker.margin_rate

    @margin_rate.setter
    def margin_rate(self, value):
        if not self._is_live_trading and isinstance(value, float) and 0. < value < 1.:
            self._broker.margin_rate = value

    @property
    def position(self) -> Position | BtPosition:
        """### 持仓对象"""
        if self._is_live_trading:
            return self._tqobjs[self.symbol].Position
        else:
            return self._broker.position

    @property
    def float_profit(self) -> float:
        """### 持仓浮动盈亏"""
        if self._is_live_trading:
            return self.position.float_profit
        else:
            return self._broker._float_profit

    @property
    def float_tick(self) -> float:
        """### 持仓浮动点数"""
        return self.float_profit/self.volume_multiple

    @property
    def open_price(self) -> float:
        """### 合约开仓价"""
        if self._is_live_trading:
            pos = self.position.pos
            if pos > 0:
                return self.position.open_price_long
            elif pos < 0:
                return self.position.open_price_short
            else:
                return 0.
        else:
            return self._broker._open_price

    @property
    def cost_price(self) -> float:
        """### 合约持仓成本价"""
        if self._is_live_trading:
            pos = self.position.pos
            if pos > 0:
                return self.position.position_price_long
            elif pos < 0:
                return self.position.position_price_short
            else:
                return 0.
        else:
            return self._broker._cost_price

    def resample(self, cycle: int, data_length: int = None, rule: str = None, **kwargs) -> BtData:
        """### 周期转换
        ------

        Args:
        ------
            #实盘中不生效
            >>> cycle (int): 转换周期,不能低于主周期.
                rule (str, optional): 日周期以上需要自行设置,D,W,M. Defaults to None.

        Returns:
        ------
            >>> BtData
        """
        if self._is_live_trading:
            data_length = data_length if data_length and data_length > 0 else 200
            return self.strategy_instance._get_data(self.symbol, int(cycle), data_length, **kwargs)
        else:
            return self.strategy_instance.resample(int(cycle), self, rule, **kwargs)

    def replay(self, cycle: int, data_length: int = None, rule: str = None, **kwargs) -> BtData:
        """### 周期转换
        ------

        Args:
        ------
            #实盘中不生效
            >>> cycle (int): 转换周期,不能低于主周期.
                rule (str, optional): 日周期以上需要自行设置,D,W,M. Defaults to None.

        Returns:
        ------
            >>> BtData
        """
        if self._is_live_trading:
            data_length = data_length if data_length and data_length > 0 else 200
            return self.strategy_instance.get_data(self.symbol, int(cycle), data_length, **kwargs)
        else:
            return self.strategy_instance.replay(int(cycle), self, rule, **kwargs)

    def _replay_datas(self, keys: list[str] = "all") -> list[pd.DataFrame, pd.Series]:
        isany = keys != "all"
        one = False
        if isany:
            if isinstance(keys, str):
                one = True
            if len(keys) == 1:
                keys = keys[0]
                one = True
        datas = []
        for d in self.pandas_object.values:
            dt = d[0]
            data = self.conversion_object[self.conversion_object.datetime <= dt]
            data.loc[len(data)-1] = d
            if isany:
                data = data[keys]
            datas.append(data)
        return datas

    @property
    def Heikin_Ashi_Candles(self) -> bool:
        """黑金K线图"""
        return self.category == CandlesCategory.Heikin_Ashi_Candles

    @Heikin_Ashi_Candles.setter
    def Heikin_Ashi_Candles(self, value: bool) -> None:
        if value:
            _id = self.id.data_id
            source: corefunc = self.pandas_object.copy()
            kline_object = self.pandas_object.copy()
            if isinstance(value, int) and value > 0:
                df = source.ta.Heikin_Ashi_Candles(value)
            else:
                df = source.ta.ha()
            source.loc[:, FILED.OHLC] = df.loc[:, FILED.OHLC].values
            ind_setting = self._indsetting.copy_values
            ind_setting.update(
                dict(category=Category.Heikin_Ashi_Candles, kline_object=kline_object))
            data = BtData(source, **ind_setting)
            setattr(self.strategy_instance, self.sname, data)

    @property
    def Linear_Regression_Candles(self) -> bool:
        return self.category == CandlesCategory.Linear_Regression_Candles

    @Linear_Regression_Candles.setter
    def Linear_Regression_Candles(self, value: int) -> None:
        value = value if isinstance(value, int) and value > 1 else 11
        if value:
            _id = self.id.data_id
            kline_object = self.pandas_object.copy()
            source: corefunc = self.pandas_object.copy()
            df = self.pandas_object.ta.Linear_Regression_Candles(length=value)
            source.loc[:, FILED.OHLC] = df.loc[:, FILED.OHLC].values
            ind_setting = self._indsetting.copy_values
            ind_setting.update(
                dict(category=Category.Linear_Regression_Candles, kline_object=kline_object))
            data = BtData(source, **ind_setting)
            setattr(self.strategy_instance, self.sname, data)

    def _open_trader(self):
        self._istrader = any(
            [getattr(self, string) is not None for string in SIGNAL_Str])

    @property
    def datetime(self) -> series:
        """时间序列"""
        return getattr(self, '_datetime')

    @property
    def open(self) -> series:
        """开盘价序列"""
        return getattr(self, '_open')

    @property
    def high(self) -> series:
        """最高价序列"""
        return getattr(self, '_high')

    @property
    def low(self) -> series:
        """最低价序列"""
        return getattr(self, '_low')

    @property
    def close(self) -> series:
        """收盘价序列"""
        return getattr(self, '_close')

    @property
    def volume(self) -> series:
        """成交量序列"""
        return getattr(self, '_volume')

    @property
    def bear_color(self) -> str:
        if self._plotinfo.candlestyle:
            return self._plotinfo.candlestyle.bear

    @bear_color.setter
    def bear_color(self, value: str):
        if (value in Colors or (isinstance(value, str) and value)) and self._plotinfo.candlestyle:
            self._plotinfo.candlestyle.bear = value

    @property
    def bull_color(self) -> str:
        if self._plotinfo.candlestyle:
            return self._plotinfo.candlestyle.bull

    @bull_color.setter
    def bull_color(self, value: str):
        if (value in Colors or (isinstance(value, str) and value)) and self._plotinfo.candlestyle:
            self._plotinfo.candlestyle.bull = value

    @property
    def datetime_index(self) -> pd.Index:
        """数据时间索引，用于分析报告"""
        return pd.Index(self._dataset.source_object.datetime.values)

    def run(self, *args: tuple[list[str, Multiply]], **kwargs) -> Bt:
        """### 快速启动
        ### Args:
        >>> tuple[list[str, Multiply]]

        ### Kwargs:
        >>> next (Callable)
            config (Config)

        Example:
        >>> bt= BtData(LocalDatas.get_dataframe(LocalDatas.v2509)).run(
                ["ma1", Multiply(PandasTa.sma, dict(length=20))],
                ["ma2", Multiply(PandasTa.sma, dict(length=30))],
                ["ma3", Multiply(PandasTa.sma, dict(length=60))],
                ["ma4", Multiply(PandasTa.sma, dict(length=120))],
                ["ebsw", Multiply(PandasTa.ebsw)])

        >>> def next(self: Strategy):
                if not self.btdata.position:
                    if self.ma1.prev < self.ma4.prev and self.ma1.new > self.ma4.new:
                        self.btdata.buy()
                elif self.btdata.position > 0:
                    if self.ma1.prev > self.ma4.prev and self.ma1.new < self.ma4.new:
                        self.btdata.sell()
            config = Config(islog=False, profit_plot=True)
            bt= BtData(LocalDatas.get_dataframe(LocalDatas.v2509)).run(
                ["ma1", Multiply(PandasTa.sma, dict(length=20))],
                ["ma2", Multiply(PandasTa.sma, dict(length=30))],
                ["ma3", Multiply(PandasTa.sma, dict(length=60))],
                ["ma4", Multiply(PandasTa.sma, dict(length=120))],
                ["ebsw", Multiply(PandasTa.ebsw)], next=next, config=config)

        Returns:
            Bt
        """
        from .bt import Bt
        from .utils import Config as btconfig
        from .strategy.strategy import Strategy
        df = self.pandas_object
        if args:
            assert all([isinstance(arg, (list, tuple))
                       for arg in args]), "参数必须为list或tuple"
            assert all([len(arg) == 2 for arg in args]
                       ), "参数形式为list[str, Multiply]"
            names = list(map(lambda x: x[0], args))
            assert all([isinstance(name, str) for name in names])
            multiply = list(map(lambda x: x[1], args))
            assert all([isinstance(mult, Multiply) for mult in multiply])
            for m in multiply:
                setattr(m, "data", self)
        next = kwargs.pop("next", None)
        iscallnext = isinstance(next, Callable)
        config = kwargs.pop("config", None)
        config = config if isinstance(config, btconfig) else btconfig(
            islog=False, profit_plot=iscallnext)

        class default_strategy(Strategy):
            def __init__(self) -> None:
                self.data = self.get_data(df)
                if args:
                    data = self.data.multi_apply(*multiply)
                    for name, ind in zip(names, data):
                        setattr(self, name, ind)
        if iscallnext:
            default_strategy.next = next
        default_strategy.config = config
        if "name" in kwargs:
            default_strategy.__name__ = kwargs.pop("name")

        bt = Bt()
        bt.addstrategy(default_strategy)
        bt.run()
        return bt


class series(IndicatorsBase, pd.Series, PandasTa, TaLib):
    """### 框架内置指标数据序列类（series 类型）
        核心定位：继承 pandas.Series 并整合指标计算、可视化配置能力，作为系统统一的单列指标数据格式，适用于单一维度的技术指标（如RSI、MACD信号线等）

        核心特性：
        1. 多父类融合：
        - 继承 `pd.Series`：保留原生 Series 的序列数据存储与计算能力（如索引、切片、元素操作）
        - 继承 `IndicatorsBase`：获得指标基础属性与方法（如指标ID、分类标识）
        - 继承 `PandasTa`/`TaLib`：直接调用 pandas_ta、TaLib 库的技术指标计算接口
        2. 指标化增强：
        - 内置指标元数据管理（`_indsetting` 指标设置、`_plotinfo` 绘图配置）
        - 支持自定义数据标记（`iscustom=True`），适用于用户手动生成的指标序列
        3. 可视化配置集成：
        - 支持线型（`line_style`）、线宽（`line_width`）、颜色（`line_color`）、虚实样式（`line_dash`）的单独设置
        - 自动适配框架绘图模块，无需手动传递绘图参数
        4. 数据兼容性：
        - 支持多种输入数据类型（`pd.Series`/`np.ndarray`/整数），整数输入时自动生成对应长度的全NaN数组
        - 与框架内置 `dataframe` 类无缝兼容，可通过 `series` 属性相互转换


        初始化参数说明：
        Args:
            data: 输入数据，支持以下类型：
                - pd.Series：直接使用已有 Series，自动继承其索引与数据
                - np.ndarray：numpy 数组，自动转换为 Series
                - int：整数表示序列长度，自动生成对应长度的全NaN数组（标记为自定义数据）
            **kwargs: 额外配置参数（核心参数如下）：
                - id (BtID)：指标唯一标识（默认自动生成），用于指标区分与管理
                - lines (list[str])：指标线名称列表（默认 ['line']，单列指标通常只需要一个名称）
                - category (str)：指标分类（如 "momentum"/"volatility"，默认 None）
                - isplot (bool)：是否绘图（默认 True）
                - overlap (bool)：是否与主图重叠显示（默认 False，"overlap" 分类指标自动设为 True）
                - sname/ind_name (str)：指标显示名称/内部名称（默认 'name'/'ind_name'）
                - ismain (bool)：是否为主图指标（默认 False）
                - isreplay/isresample (bool)：是否为回放/重采样数据（默认 False）
                - isindicator (bool)：是否为技术指标（默认 True，非指标数据设为 False）
                - iscustom (bool)：是否为自定义数据（默认 False，整数输入时自动设为 True）
                - height (int)：指标绘图高度（默认 150）
                - linestyle/signalstyle/spanstyle：绘图样式配置（默认空字典，使用框架默认样式）


        核心属性说明：
        1. 数据与指标基础属性：
        - _indsetting：`IndSetting` 实例，存储指标元数据（如指标ID、长度、维度标识）
        - _plotinfo：`PlotInfo` 实例，存储绘图配置（如高度、线型、颜色等）
        - _dataset：`DataFrameSet` 实例，管理数据副本与缓存
        - lines：指标线名称列表（通常长度为1，如 ['rsi']）
        2. 样式配置属性（支持直接读写）：
        - line_style：线型完整配置（`LineStyle` 实例，包含线宽、颜色、虚实样式）
        - line_dash：线型虚实样式（如 `LineDash.solid` 实线、`LineDash.dash` 虚线）
        - line_width：线宽（整数或浮点数，如 2 表示2像素宽）
        - line_color：线条颜色（如 `Colors.red` 或 "#FF0000" 十六进制色值）


        使用示例：
        >>> # 1. 从 numpy 数组初始化指标序列
        >>> import numpy as np
        >>> rsi_data = np.array([55.2, 58.7, 62.1, 59.3, 54.8])
        >>> rsi_series = series(rsi_data, lines=['rsi'], category='momentum', isplot=True)
        >>> 
        >>> # 2. 自定义线型样式
        >>> rsi_series.line_color = Colors.blue  # 设置为蓝色
        >>> rsi_series.line_width = 2            # 线宽设为2
        >>> rsi_series.line_dash = LineDash.dash # 虚线样式
        >>> 
        >>> # 3. 从整数长度初始化（自定义数据）
        >>> ma_series = series(100, iscustom=True, lines=['ma20'])  # 生成100长度的全NaN序列
        >>> 
        >>> # 4. 调用 pandas_ta 指标（继承自 PandasTa）
        >>> close_series = series(close_prices)  # close_prices 为价格序列
        >>> macd_signal = close_series.macd().signal  # 获取MACD信号线（series类型）
        """

    def __init__(self, data: pd.Series | np.ndarray | int, **kwargs: Union[IndSetting, dict]) -> None:
        if isinstance(data, int):
            data = np.full(data, np.nan)
            kwargs.update(dict(iscustom=True))
        super().__init__(data)
        btid = kwargs.pop("id", BtID())
        if isinstance(btid, dict):
            btid = BtID(**btid)
        if not isinstance(btid, BtID):
            btid = BtID()
        lines = Lines(*kwargs.pop('lines', ['line',]))
        category = kwargs.pop('category', None)
        isplot = kwargs.pop('isplot', True)
        overlap = kwargs.pop('overlap', False)
        overlap = category == "overlap" and True or bool(overlap)
        sname = kwargs.pop('sname', 'name')
        ind_name = kwargs.pop('ind_name', 'ind_name')
        ismain = bool(kwargs.pop('ismain', False))
        isreplay = bool(kwargs.pop('isreplay', False))
        isresample = bool(kwargs.pop('isresample', False))
        isindicator = bool(kwargs.pop('isindicator', True))
        iscustom = bool(kwargs.pop('iscustom', False))
        is_mir = kwargs.pop('_is_mir', False)
        isMDim = False
        dim_match = kwargs.pop("dim_match", True)
        v, h = self.shape[0], 1
        height = kwargs.pop("height", 150)
        linestyle = kwargs.pop("linestyle", {})
        signalstyle = kwargs.pop("signalstyle", {})
        spanstyle = kwargs.pop("spanstyle", {})
        span = kwargs.pop("spanstyle", np.nan)
        # if isresample:
        #     btid.resample_id = btid.data_id
        # if isreplay:
        #     btid.replay_id = btid.data_id
        self._indsetting = IndSetting(
            btid,
            is_mir,
            False,
            False,
            ismain,
            isreplay,
            isresample,
            isindicator,
            iscustom,
            isMDim,
            dim_match,
            v,
            h,
            v-1,
            [],
        )
        plotinfo = kwargs.pop('plotinfo', None)
        if not isinstance(plotinfo, PlotInfo):
            plotinfo = PlotInfo(
                height=height,
                sname=sname,
                ind_name=ind_name,
                lines=lines,
                category=category,
                isplot=isplot,
                overlap=overlap,
                linestyle=linestyle,
                signalstyle=signalstyle,
                spanstyle=span,
            )
        self._plotinfo = plotinfo
        self._dataset = DataFrameSet(self.copy())
        if self._indsetting.iscustom:
            self._dataset.custom_object = data
        self.cache = Cache(maxsize=np.inf)

    def __eq__(self, other):
        return super(IndicatorsBase, self).__eq__(other)

    @property
    def line_style(self) -> LineStyle:
        return self._plotinfo.linestyle[self.lines[0]]

    @line_style.setter
    def line_style(self, value: LineStyle):
        if isinstance(value, LineStyle):
            self._plotinfo.linestyle[self.lines[0]] = value

    @property
    def line_dash(self) -> str | LineDash:
        return self._plotinfo.linestyle[self.lines[0]].line_dash

    @line_dash.setter
    def line_dash(self, value: str | LineDash):
        if value in LineDash:
            self._plotinfo.linestyle[self.lines[0]].line_dash = value

    @property
    def line_width(self) -> int | float:
        return self._plotinfo.linestyle[self.lines[0]].line_width

    @line_width.setter
    def line_width(self, value: int | float):
        if isinstance(value, (int, float)):
            self._plotinfo.linestyle[self.lines[0]].line_width = value

    @property
    def line_color(self) -> str | Colors:
        return self._plotinfo.linestyle[self.lines[0]].line_color

    @line_color.setter
    def line_color(self, value: str | Colors):
        if isinstance(value, str) or value in Colors:
            self._plotinfo.linestyle[self.lines[0]].line_color = value


class Line(series):
    """### 框架内置单列指标数据类（继承 series 类）
        核心定位：作为 `dataframe`/`BtData` 类的「列级数据载体」，封装单列指标的完整能力，同时保持与源数据（父 `dataframe`/`BtData`）的联动，实现样式配置、绘图状态的双向同步

        核心特性：
        1. 源数据强关联：
        - 初始化时必须绑定父级 `dataframe` 或 `BtData` 实例（`source` 参数），确保与源数据共享元信息（如指标分类、绘图配置）
        - 样式修改（如颜色、线型）会自动同步到父级源数据，避免父子数据配置不一致
        2. 信号与普通指标双适配：
        - 自动识别是否为交易信号线（通过 `sname` 是否在父级 `signallines` 中判断）
        - 信号线额外支持信号样式配置（标记 `signal_marker`、颜色 `signal_color` 等），普通指标线仅保留基础线型配置
        3. 样式配置双向同步：
        - 线型（`line_style`）、线宽（`line_width`）、颜色（`line_color`）等基础样式修改时，同时更新自身与父级源数据的绘图配置
        - 信号专属样式（`signal_style`/`signal_key` 等）修改时，自动同步父级源数据的信号配置，确保绘图时信号与源数据匹配
        4. 继承与扩展并重：
        - 完全继承 `series` 类的指标计算能力（如调用 `pandas_ta`/`TaLib` 接口）、数据操作能力（索引、切片等）
        - 新增与父级联动的属性（如 `follow` 继承父级跟随状态、`overlap` 同步父级重叠显示配置），强化列级数据的上下文关联性


        初始化参数说明：
        Args:
            source (dataframe | BtData): 父级源数据实例，必须为框架内置的多列数据类型（`dataframe` 或 `BtData`），用于关联元信息与同步配置
            data: 单列指标数据，支持类型与 `series` 类一致（`pd.Series`/`np.ndarray`/整数，整数表示生成对应长度的全NaN数组）
            **kwargs (IndSetting | dict): 额外配置参数（核心参数继承自 `series` 类，新增/增强如下）：
                    - sname (str): 指标线名称（必须与父级 `dataframe`/`BtData` 的列名一致，用于匹配父级配置）
                    - 其他参数（如 `category`/`isplot`/`overlap` 等）若未指定，默认继承自父级源数据


        核心属性说明：
        1. 源数据关联属性：
        - source: 父级源数据实例（`dataframe` 或 `BtData`），可直接通过该属性访问父级的完整能力（如其他列数据、合约信息等）
        - follow: 继承父级的「主图跟随状态」（仅 `BtData` 等K线类数据有效，默认与父级一致）
        - isplot: 绘图开关，修改时自动同步父级源数据中对应列的绘图状态（非蜡烛图类父级有效）
        - overlap: 与主图重叠显示开关，修改时同步父级源数据对应列的重叠配置（非蜡烛图类父级有效）
        2. 基础线型配置属性（双向同步父级）：
        - line_style: 完整线型配置（`LineStyle` 实例），修改时同步父级源数据对应列的线型
        - line_dash: 线型虚实样式（如 `LineDash.solid` 实线），修改时同步父级
        - line_width: 线宽（整数/浮点数，需大于0），修改时同步父级
        - line_color: 线条颜色（支持 `Colors` 枚举或十六进制字符串），修改时同步父级
        3. 信号专属配置属性（仅信号线有效，双向同步父级）：
        - signal_style: 信号完整样式（`SignalStyle` 实例），仅当该线为信号线时可访问
        - signal_key: 信号锚定的父级列名（如信号标记在 "low" 列价格位置），修改时同步父级
        - signal_marker: 信号标记样式（如 `Markers.circle_dot` 圆点），修改时同步父级
        - signal_color: 信号颜色，修改时同步父级
        - signal_size: 信号大小，修改时同步父级
        - signal_show: 信号显示开关，修改时同步父级


        使用示例：
        >>> # 1. 从 BtData 父级数据创建 Line 实例（假设 btdata 为 BtData 实例，含 "close" 列）
        >>> close_line = self.data.close
        >>> 
        >>> # 2. 修改线型样式（自动同步到父级 BtData）
        >>> close_line.line_color = Colors.red  # 关闭线设为红色，父级 btdata 的 "close" 列颜色同步更新
        >>> close_line.line_width = 2           # 线宽设为2，父级同步更新
        >>> 
        >>> # 3. 信号线配置（假设 "long_signal" 是父级的信号列）
        >>> if long_line.issignal:  # 自动识别为信号线
        ...     long_line.signal_marker = Markers.triangle_up  # 信号标记设为上三角
        ...     long_line.signal_color = Colors.green          # 信号颜色设为绿色，父级同步更新
        >>> 
        >>> # 4. 控制绘图状态（同步父级）
        >>> long_line.isplot = True  # 开启信号线绘图，父级 btdata 的 "long_signal" 列绘图状态同步开启"""

    def __init__(self, source: dataframe | BtData, data, **kwargs: IndSetting | dict) -> None:
        super().__init__(data, **kwargs)
        self.__source = source  # dataframe数据
        self._issignal: bool = self.sname in source.signallines

    @property
    def line_style(self) -> Optional[LineStyle]:
        return self._plotinfo.linestyle.get(self.sname)

    @line_style.setter
    def line_style(self, value):
        if isinstance(value, LineStyle):
            self._plotinfo.linestyle = Addict({self.sname: value})
            self.__source._plotinfo.linestyle.update(
                {self.sname: value})

    @property
    def line_dash(self) -> LineDash:
        return self._plotinfo.linestyle[self.sname].line_dash

    @line_dash.setter
    def line_dash(self, value):
        if value in LineDash:
            self._plotinfo.linestyle[self.sname].line_dash = value
            self.__source._plotinfo.linestyle[self.sname].line_dash = value

    @property
    def line_width(self) -> float:
        return self._plotinfo.linestyle[self.name].line_width

    @line_width.setter
    def line_width(self, value):
        if isinstance(value, (float, int)) and value > 0.:
            value = float(value)
            self._plotinfo.linestyle[self.name].line_width = value
            self.__source._plotinfo.linestyle[self.name].line_width = value

    @property
    def line_color(self) -> Colors | str:
        return self._plotinfo.linestyle[self.sname].line_color

    @line_color.setter
    def line_color(self, value):
        if value in Colors or (value and isinstance(value, str)):
            self._plotinfo.linestyle[self.sname].line_color = value
            self.__source._plotinfo.linestyle[self.sname].line_color = value

    @property
    def signal_style(self) -> Optional[SignalStyle]:
        if self._issignal:
            return self._plotinfo.signalstyle[self.sname]

    @signal_style.setter
    def signal_style(self, value):
        if self._issignal and isinstance(value, SignalStyle):
            self.__source._plotinfo.signalstyle[self.sname] = value
            self._plotinfo.signalstyle[self.sname] = value

    @property
    def signal_key(self) -> str:
        return self._plotinfo.signalstyle[self.sname].key

    @signal_key.setter
    def signal_key(self, value) -> None:
        if value in self.__source.lines:
            self.__source._plotinfo.signalstyle[self.sname].key = value
            self._plotinfo.signalstyle[self.sname].key = value

    @property
    def signal_color(self) -> str:
        return self._plotinfo.signalstyle[self.sname].color

    @signal_color.setter
    def signal_color(self, value) -> None:
        if value in self.__source.lines:
            self.__source._plotinfo.signalstyle[self.sname].color = value
            self._plotinfo.signalstyle[self.sname].color = value

    @property
    def signal_marker(self) -> str:
        return self._plotinfo.signalstyle[self.sname].marker

    @signal_marker.setter
    def signal_marker(self, value) -> None:
        if value in self.__source.lines:
            self.__source._plotinfo.signalstyle[self.sname].marker = value
            self._plotinfo.signalstyle[self.sname].marker = value

    @property
    def signal_show(self) -> str:
        return self._plotinfo.signalstyle[self.sname].show

    @signal_show.setter
    def signal_show(self, value) -> None:
        if value in self.__source.lines:
            self.__source._plotinfo.signalstyle[self.sname].show = value
            self._plotinfo.signalstyle[self.sname].show = value

    @property
    def signal_size(self) -> str:
        return self._plotinfo.signalstyle[self.sname].size

    @signal_size.setter
    def signal_size(self, value) -> None:
        if value in self.__source.lines:
            self.__source._plotinfo.signalstyle[self.sname].size = value
            self._plotinfo.signalstyle[self.sname].size = value

    @property
    def isplot(self) -> bool:
        return self.__source.isplot[self.sname]

    @isplot.setter
    def isplot(self, value):
        value = bool(value)
        self._plotinfo.isplot = value
        if self.__source.category != 'candles':
            self.__source.isplot[self.sname] = value

    @property
    def source(self) -> dataframe | BtData:
        """Line对应的dataframe数据"""
        return self.__source

    @property
    def overlap(self) -> bool:
        return self.__source.overlap[self.sname]

    @overlap.setter
    def overlap(self, value):
        value = bool(value)
        if not self.__source.iscandles:
            self._plotinfo.overlap = value
            self.__source.overlap[self.sname] = value

    @property
    def follow(self) -> bool:
        return self.__source.follow if hasattr(self.__source, "follow") else True


class CustomBase:
    """
    >>> lines: list[str] = []
        overlap: bool = True
        isplot: bool = True
        ismain: bool = False
        category: str | None = None
        plotinfo:PlotInfo=PlotInfo()
    """
    data: Union[BtData, dataframe, Line, series]
    height: int = 150
    lines: Union[list[str], Lines[str]] = Lines()
    overlap: bool = False
    isplot: bool = True
    ismain: bool = False
    category: str | None = None
    # plotinfo: PlotInfo = PlotInfo()
    candlestyle: Optional[CandleStyle] = None
    linestyle: Addict[str, LineStyle] | dict[str,
                                             LineStyle] = Addict()
    signalstyle: Addict[str, SignalStyle] | dict[str,
                                                 SignalStyle] = Addict()
    spanstyle: SpanList[SpanStyle] | list[SpanStyle] = SpanList()

    @classmethod
    def _is_method_overridden(cls, method_name):
        """检查类是否重新定义了指定的实例方法"""
        import types
        return method_name in cls.__dict__ and isinstance(cls.__dict__[method_name], types.FunctionType)

    def next(self: BtData) -> Union[series, dataframe]:
        return self.close if hasattr(self, "close") else self

    def step(self): ...


class BtIndicator(CustomBase, BtData):
    """### 自定义指标创建基类（继承 CustomBase 与 BtData）
        核心定位：提供标准化接口快速构建自定义技术指标，自动集成框架数据结构与绘图系统，支持将用户定义的计算逻辑转换为框架兼容的指标数据（series/dataframe）

        核心特性：
        1. 简化指标开发流程：
        - 通过重写 `next` 方法定义指标计算逻辑，无需关注数据格式转换与框架集成细节
        - 自动解析指标输出列名（`lines`），支持手动指定或从 `next` 方法返回值自动提取
        2. 完整的指标配置能力：
        - 继承 `CustomBase` 的绘图配置属性（`overlap` 重叠显示、`isplot` 绘图开关、`category` 指标分类等）
        - 支持自定义线型（`linestyle`）、信号样式（`signalstyle`）、绘图高度（`height`）等可视化参数
        3. 框架无缝集成：
        - 生成的指标自动兼容 `BtData`/`dataframe` 数据结构，可直接用于策略逻辑或进一步计算
        - 通过 `@tobtind` 装饰器自动处理指标元数据（如指标ID、绘图信息），无需手动维护
        4. 参数化与灵活性：
        - 支持通过 `params` 属性定义指标参数，实现同一指标的多参数版本
        - 支持批量注册自定义方法到 `BtData` 类，扩展基础数据结构的指标计算能力


        初始化参数说明：
        Args:
            data (dataframe | pd.DataFrame): 输入数据，需为框架内置 `dataframe` 或 pandas 的 `pd.DataFrame`（含计算所需基础字段如 open/close 等）
            **kwargs (IndSetting | dict): 指标配置参数，支持以下核心配置：
                    - lines (list[str] | Lines): 指标输出列名列表（如 ["ma5", "ma10"]，未指定时自动从 `next` 方法返回值提取）
                    - overlap (bool): 是否与主图重叠显示（默认继承 `CustomBase` 的 `overlap=False`）
                    - isplot (bool): 是否绘图（默认 True）
                    - ismain (bool): 是否为主图指标（默认 False）
                    - category (str): 指标分类（如 "overlap" 归为重叠指标，默认 None）
                    - linestyle (Addict[str, LineStyle] | dict[str, LineStyle]): 指标线样式配置
                                                                                - 覆盖规则：若键与 `lines` 中的列名匹配，优先使用该配置；未匹配项使用框架默认
                    - signalstyle (Addict[str, SignalStyle] | dict[str, SignalStyle]): 交易信号线样式配置
                                                                                    - 仅对 `lines` 中标记为信号的列（如 "long_signal"）生效
                    - spanstyle (SpanList[SpanStyle] | list[SpanStyle]): 区间填充样式配置
                                                                    - 要求：`SpanStyle` 实例的 `start_line`/`end_line` 必须在 `lines` 中定义
                    - _multi_index: 多索引标识（内部使用，用户一般无需设置）
                    - 其他参数：会被合并到 `params` 属性，可在 `next` 方法中通过 `self.params` 访问


        关键方法说明：
        1. next(self: BtData) -> Union[series, dataframe, pd.Series, pd.DataFrame, np.ndarray, tuple]:
        - 核心方法，需用户重写，定义指标计算逻辑
        - 参数 `self`：通常为 `BtData` 实例，可直接访问其字段（如 `self.close` 获取收盘价序列）
        - 返回值：支持多种数据类型，框架会自动转换为 `series`（单列）或 `dataframe`（多列）
        - 示例：返回 `self.close.rolling(5).mean()` 实现5期均线

        2. step(self):
        - 可选重写方法，用于实现迭代步骤逻辑（如状态更新、中间变量计算）
        - 若重写，会被自动注册到 `IndicatorsBase`，在指标计算过程中调用

        3. _is_method_overridden(cls, method_name: str) -> bool:
        - 类方法，内部用于检查指定方法（如 `step`）是否被用户重写
        - 通常无需用户调用，框架自动使用


        使用示例：
        >>> # 1. 定义简单移动平均线指标
        >>> class MyMA(BtIndicator):
        ...     # 手动指定输出列名（也可省略，框架自动提取）
        ...     lines = ["ma5", "ma10"]
        ...     # 指标参数（可在初始化时通过 kwargs 覆盖）
        ...     params = {"length5": 5, "length10": 10}
        ...
        ...     def next(self):
        ...         # self 为 BtData 实例，可访问收盘价
        ...         ma5 = self.close.rolling(self.params.length5).mean()
        ...         ma10 = self.close.rolling(self.params.length10).mean()
        ...         return ma5, ma10  # 返回多列数据，对应 lines 定义
        ...
        >>> # 2. 使用自定义指标
        >>> # 假设 btdata 为 BtData 实例（含 close 字段）
        >>> ma_indicator = MyMA(btdata, isplot=True, category="overlap")
        >>> # 3. 访问指标结果（已自动转换为 dataframe）
        >>> print(ma_indicator.ma5)  # 输出5期均线序列（Line类型）
        >>> print(ma_indicator.ma10) # 输出10期均线序列（Line类型）
        >>> # 4. 指标自动支持绘图，配置已通过类属性和初始化参数设置
    """
    params: dict = {}

    def __new__(cls, data: dataframe | pd.DataFrame, **kwargs: IndSetting | dict) -> Union[series, dataframe]:
        if "lines" in kwargs:
            cls.lines = Lines(*kwargs["lines"])
        else:
            if not cls.lines:
                func_lines = getsourcelines(
                    cls.next)[0]
                string = [fl.strip() for fl in func_lines]
                string = [fl for fl in string if not fl.startswith(
                    "#") and "return" in fl]
                # assert string, "请设置返回值"

                if string:
                    func_lines = string[-1]
                    if "#" in func_lines:
                        func_lines = func_lines.split("#")[0]
                    if "(" not in string or ")" not in func_lines:
                        func_lines = func_lines.split("return ")[1].strip()
                        if "," in func_lines:
                            lines = tuple([string.strip()
                                           for string in func_lines.split(",")])
                        else:
                            lines = (func_lines,)
                        lines = [ls.split(".")[-1]
                                 if "." in ls else ls for ls in lines]
                        cls.lines = Lines(*lines)

        if cls.lines:
            assert cls.lines and isinstance(cls.lines, (tuple, list, Lines)) and all(
                [isinstance(l, str) for l in cls.lines]), "lines类型为tuple or list,元素为字符串"
        overlap = kwargs.pop('overlap', cls.overlap)
        isplot = kwargs.pop('isplot', cls.isplot)
        ismain = kwargs.pop('ismain', cls.ismain)
        category = kwargs.pop('category', cls.category)
        plotinfo = kwargs.pop('plotinfo', cls.plotinfo)
        multi_index = kwargs.pop("_multi_index", None)
        cls.params = Addict({**cls.params, **kwargs})
        btdata_dict = BtData.__dict__
        [setattr(BtData, k, v) for k, v in cls.__dict__.items()
         if k not in btdata_dict and k != "next"]
        if cls._is_method_overridden("step"):
            setattr(IndicatorsBase, "step", cls.step)

        @tobtind(lines=cls.lines, overlap=overlap, isplot=isplot, ismain=ismain, category=category, plotinfo=plotinfo, myself=cls.__name__, _multi_index=multi_index)
        def _next(self):
            return cls.next(self)
            # if data is not None:

            #     if isinstance(data, pd.DataFrame) and (isinstance(cls.lines, Iterable) and len(cls.lines) != data.shape[1]):
            #         lines = tuple(data.columns)
            #         return data, lines
            # return data
        cls.data = data
        return _next(data)


# class BtSeries(CustomBase, series):
#     """自定义指标器
#     ---------------

#     Args:
#     -------------
#         >>> data (BtData): BtData数据
#             kwargs (dict):dict(lines=[],overlap=True,isplot=True,ismain=False,category=None,plotinfo=PlotInfo())

#     next函数返回结果:
#     --------------
#         >>> series | dataframe | Series | DataFrame | ndarray | tuple[series,dataframe,Series,DataFrame,ndarray]

#     Returns:
#     ------------
#         >>> series | dataframe
#     """
#     params: dict = {}

#     def __new__(cls, data: series | pd.Series, **kwargs: IndSetting | dict) -> Union[series, dataframe]:
#         try:
#             data.params = Addict(kwargs.pop('params', cls.params))
#         except:
#             cls.params = Addict(kwargs.pop('params', cls.params))
#         if isinstance(kwargs, IndSetting):
#             kwargs = kwargs.copy_values
#         lines = list(kwargs.pop('lines', cls.lines))
#         overlap = kwargs.pop('overlap', cls.overlap)
#         isplot = kwargs.pop('isplot', cls.isplot)
#         ismain = kwargs.pop('ismain', cls.ismain)
#         category = kwargs.pop('category', cls.category)
#         plotinfo = kwargs.pop('plotinfo', cls.plotinfo)
#         multi_index = kwargs.pop("_multi_index", None)
#         if cls._is_method_overridden("step"):
#             setattr(IndicatorsBase, "step", cls.step)

#         @tobtind(lines=lines, overlap=overlap, isplot=isplot, ismain=ismain, category=category, plotinfo=plotinfo, myself=cls.__name__, _multi_index=multi_index)
#         def _next(self):
#             return cls.next(self)
#         return _next(data)


class StopMode(int, Enum):
    """### 停止模式

    ### atrs:
        >>> Postposition (int:0): 后置模式,next函数后运行,next函数中也可以交易.
            FrontLoaded (int:1): 前置模式,next函数前运行,next函数中也可以交易.
            PreSkip (int:2): 前置跳过模式,next函数前运行,next函数中不可交易.
    """
    Postposition = 0  # 后置
    FrontLoaded = 1  # 前置
    PreSkip = 2  # 前置跳过


class Stop:
    """### 停止类

    ### atrs
        >>> self.btdata (BtData) : 合约数据
            self.data_length (int) : 调用数据的长度
            self.price_tick (float) : 最小变化单位
            self.stop_price (list[float]): 停止价列表
            self.target_price (list[float]): 目标价列表
            self.ctrl (bool): 初始赋值控制. default False

    ### method
        >>> self.data (pd.DataFrame): 合约数据
            self.trade_price (float): 交易价格
            self.current_close (float): 最新价格
            self.last_stop_price (float): 最新停止价
            self.last_target_price (float): 最新目标价
            self.new_price (tuple[float]): 最新停止价和目标价

    ### 定义__init__,long和short方法
        >>> __init__初始化常量
        >>> 计算并按顺序返回stop_price和target_price
        >>> long和short方法返回: tuple[float],长度为2

    ### example(SegmentationTracking):
        >>> def __init__(self) -> None:
            self.length = 14
            self.mult: float = 1.
            self.method: str = 'atr'
            self.acceleration: list[float] = [0.382, 0.5, 0.618, 1.0]

        >>> def long(self):
                method = self.method
                data = self.data
                length = self.length
                mult = self.mult
                acceleration = self.acceleration
                isatr = False
                if method == 'atr':
                    isatr = True
                    close = data.close
                    low = data.low
                    high = data.high
                elif method == 'std':
                    _method = stdev
                    close = data.close
                else:
                    _method = smoothrng
                lastprice = close.iloc[-1]
                #初始值计算
                if not self.ctrl:
                    _atr = atr(
                        high, low, close, length).iloc[-1] if isatr else _method(close, length).iloc[-1]
                    stop_price = lastprice-mult*_atr
                    self.ctrl = True
                #初始值后计算
                else:
                    preprice = close.iloc[-2]
                    stop_price = self.last_stop_price
                    if lastprice > preprice:
                        diff_price = lastprice-self.trade_price
                        _atr = atr(
                            high, low, close, length).iloc[-1] if isatr else _method(close, length).iloc[-1]
                        _atr *= mult
                        range_ = lastprice-preprice
                        if stop_price < self.trade_price:
                            stop_price += acceleration[0]*range_
                        else:
                            if diff_price < _atr:
                                stop_price += acceleration[1]*range_
                            elif diff_price < 2.*_atr:
                                stop_price += acceleration[2]*range_
                            else:
                                stop_price += acceleration[3]*range_
                return stop_price, np.nan
    """

    def __call__(self, btdata: BtData,  **kwargs):
        self.btdata: BtData = btdata
        self.data_length: int = kwargs.pop('data_length', 300)
        self.mode = kwargs.pop('stop_mode', StopMode.Postposition)
        assert self.mode in [
            0, 1, 2], f"停止器模式错误,StopMode:{[k for k,v in vars(StopMode).items() if not k.startswith('_')]}"
        self._price_tick: float = self.btdata.price_tick
        self._volume_multiple: float = self.btdata.volume_multiple
        self.cache: Cache = Cache(maxsize=np.inf)
        self.__stop_ctrl: bool = True
        self.__target_ctrl: bool = True
        if kwargs:
            for k, v in kwargs.items():
                setattr(self, k, v)
        return self

    @property
    def price_tick(self) -> float:
        """合约最小变动单位"""
        return self._price_tick

    @property
    def volume_multiple(self) -> float:
        """合约剩数"""
        return self._volume_multiple

    @property
    def data(self) -> pd.DataFrame:
        """合约数据"""
        return self.__get_data(self.btdata.btindex)

    def get_data(self, length=None) -> pd.DataFrame:
        self.data_length = length
        return self.data

    @cachedmethod(attrgetter('cache'))
    def __get_data(self, index: int):
        start = max(0, self.btdata.btindex+1-self.data_length)
        data = self.btdata.pandas_object.iloc[start:self.btdata.btindex+1]
        data.reset_index(drop=True, inplace=True)
        return data

    @property
    def trade_price(self) -> float:
        """成交价"""
        return self.btdata.open_price

    @property
    def new_close(self) -> float:
        """最新价格"""
        return self.btdata.close.new

    @property
    def new_open(self) -> float:
        return self.btdata.open.new

    @property
    def new_low(self) -> float:
        return self.btdata.low.new

    @property
    def new_high(self) -> float:
        return self.btdata.high.new

    @property
    def pre_close(self) -> float:
        """最新价格"""
        return self.btdata.close.prev

    @property
    def pre_open(self) -> float:
        return self.btdata.open.prev

    @property
    def pre_low(self) -> float:
        return self.btdata.low.prev

    @property
    def pre_high(self) -> float:
        return self.btdata.high.prev

    @property
    def new_stop_price(self) -> float:
        """设置最新停止价"""
        return self.btdata.stop_lines.new[0]

    @new_stop_price.setter
    def new_stop_price(self, value: float) -> None:
        self.__stop_ctrl = False
        self.btdata.stop_lines.stop_price.new = value

    @property
    def new_target_price(self) -> float:
        """设置最新目标价"""
        return self.btdata.stop_lines.new[1]

    @new_target_price.setter
    def new_target_price(self, value: float) -> None:
        self.__target_ctrl = False
        self.btdata.stop_lines.target_price.new = value

    @property
    def pre_stop_price(self) -> float:
        """最后一个停止价"""
        return self.btdata.stop_lines.prev[0]

    @property
    def pre_target_price(self) -> float:
        """最后一个目标价"""
        return self.btdata.stop_lines.prev[1]

    @property
    def pre_prices(self) -> np.ndarray:
        """最后一个停止价和目标价"""
        return self.btdata.stop_lines.prev

    @property
    def new_prices(self) -> np.ndarray:
        """设置最新停止价和目标价"""
        return self.btdata.stop_lines.new

    @new_prices.setter
    def new_prices(self, values: list[float]) -> None:
        self.btdata.stop_lines.new = values

    def __set_price(self):
        if self.__stop_ctrl:
            if self.is_init_stop and np.isnan(self.new_stop_price):
                self.new_stop_price = self.pre_stop_price

        if self.__target_ctrl:
            if self.is_init_target and np.isnan(self.new_target_price):
                self.new_target_price = self.pre_target_price
        self.__stop_ctrl = True
        self.__target_ctrl = True

    def long(self) -> tuple[float]:
        """多头停止计算"""
        raise ModuleNotFoundError('请定义long方法')

    def short(self) -> tuple[float]:
        """空头停止计算"""
        raise ModuleNotFoundError('请定义short方法')

    @property
    def is_init_stop(self) -> bool:
        """判断是否已计算初始停止价,用于设置初始停止价

        >>> return not np.isnan(self.pre_stop_price)"""
        return not np.isnan(self.pre_stop_price)

    @property
    def is_init_target(self) -> bool:
        """判断是否已计算初始目标价,用于设置初始目标价

        >>> return not np.isnan(self.pre_target_price)"""
        return not np.isnan(self.pre_target_price)

    def _update(self, closing: bool = False) -> bool:
        """更新"""
        trading = False
        pos = self.btdata.position.pos
        if pos:
            if pos > 0:
                self.long()
                self.__set_price()
                if self.new_close < self.new_stop_price or self.new_close > self.new_target_price:
                    if closing:
                        self.btdata.set_target_size()
                    else:
                        trading = True
            else:
                self.short()
                self.__set_price()
                if self.new_close > self.new_stop_price or self.new_close < self.new_target_price:
                    if closing:
                        self.btdata.set_target_size()
                    else:
                        trading = True
        return trading


class IndicatorClass(metaclass=Meta):
    PandasTa = PandasTa
    BtInd = BtInd
    TqFunc = TqFunc
    TaLib = TaLib
    FinTa = FinTa
    AutoTrader = AutoTrader
    SignalFeatures = SignalFeatures


class BtIndType(metaclass=Meta):
    """内置指标类型"""
    Line = Line
    dataframe = dataframe
    series = series


class BtDataType(metaclass=Meta):
    """BtData类型"""
    BtData = BtData
