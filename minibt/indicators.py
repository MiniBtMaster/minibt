from __future__ import annotations
from .utils import \
    (TYPE_CHECKING, PlotInfo, np, pd, wraps, Union, Callable, BtID, retry_with_different_params,
     partial, Iterable, Lines, Base, Meta, check_type, LineStyle, IndSetting, SymbolInfo, Broker,
     DataFrameSet, Optional, Addict, Any, cachedmethod, attrgetter, common, LineDash, Colors,
     Multiply, get_lennan, BlockPlacement, ispandasojb, reduce, Literal, LineStyleType, rolling_method,
     Category, SIGNAL_Str, set_property, Cache, _assign, FILED, isfinite, SignalStyleType,
     default_symbol_info, CandlesCategory, Quotes, Quote, BtAccount, TqAccount, Position,
     BtPosition, getsourcelines, Enum, StrategyInstances, TPE, TqObjs, SpanStyle, default_signal_style,
     DataSetBase, time_to_datetime, PandasObject, Rolling, CandleStyle, SignalStyle, LineAttrType,
     pandas_method, dataclass, DefaultIndicatorConfig, SignalAttrType, CategoryString, SpanList, Sequence,
     PandasDataFrame, PandasSeries, signature, SignalLabel, ExponentialMovingWindow,
     ewm_method, Expanding, expanding_method, options, SPECIAL_FUNC)
from .other import ProcessedAttribute, get_func_args_dict, timedelta, ensure_numeric_dataframe
from pandas.core.indexing import _iLocIndexer, _LocIndexer, _AtIndexer, _iAtIndexer
import os
os.environ["SHINNY_SILENT"] = "1"


if TYPE_CHECKING:
    from .constant import *
    from .strategy.strategy import Strategy
    from .core import CoreFunc
    from .bt import Bt
    from .tradingview import TradingView
    from .utils import Axis, Hashable, Mapping

    class Params:
        """函数引导，无实际用处"""

        def __getattr__(self, name: str) -> int | float | str | bool: ...

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
        return IndSeries(data, **config.to_dict())
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
        return IndFrame(data.values, **config.to_dict())


def set_lines(btind: Union[KLine, IndFrame], key):
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
            # 邦定property函数,IndFrame每列返回的是Line指标数据
            set_property(btind.__class__, btind._indsetting.line_filed[-1])


class SeriesType:
    def __init__(self, IndFrame: IndFrame):
        self.IndFrame = IndFrame

    def __getattr__(self, key) -> IndSeries:
        id = self.IndFrame.id.copy()
        sname = key
        ind_name = key
        lines = Lines(key)
        isplot = self.IndFrame.isplot
        if isinstance(isplot, dict):
            isplot = isplot.get(key, True)
        overlap = self.IndFrame.overlap
        if isinstance(overlap, dict):
            overlap = overlap.get(key, False)
        config = DefaultIndicatorConfig(
            id,
            sname,
            ind_name,
            lines,
            None,
            isplot,
            self.IndFrame.ismain,
            self.IndFrame.isreplay,
            self.IndFrame.isresample,
            overlap,
            True,
            False,
        )
        return IndSeries(getattr(self.IndFrame, key).values, **config.to_dict())


class IndexerBase:
    obj: IndicatorsBase

    def __init__(self, name: str, obj: IndicatorsBase):
        super().__init__(name, obj)

    def __getitem__(self, key) -> Union[IndFrame, Line, IndSeries,  KLine, Any]:
        """处理索引操作并返回结果"""
        data = super().__getitem__(key)  # 调用父类索引逻辑
        if isinstance(data, (pd.Series, pd.DataFrame)):
            if options.check_conversion(data, self.obj.V):
                indicator_kwargs = self.obj.get_indicator_kwargs()
                if len(data.shape) > 1:
                    indicator_kwargs["lines"] = list(data.columns)
                    return IndFrame(data.values, **indicator_kwargs)
                else:
                    return IndSeries(data.values, **indicator_kwargs)
        return data

    def __setitem__(self, key, value):
        result = super().__setitem__(key, value)
        if self.obj._dataset.upsample_object is not None and self.obj.strategy_instances:
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
        >>> lines (List[str], optional): IndFrame指标需要设置列名lines,IndSeries指标默认为None. Defaults to None.
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
    _linestyle = kwargs_.pop('linestyle', {})
    _sname = kwargs_.pop("sname", "")
    _ind_name = kwargs_.pop("ind_name", "")

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs) -> Union[IndSeries, IndFrame]:
            # 指标名称
            func_name = func.__name__
            # 数据源,指标计算的数据对象
            source: Union[Line, IndSeries,
                          IndFrame, KLine] = args[0]
            source_type = type(source)
            if source_type in IndicatorClass:
                # DataFrameIndicators,SeriesIndicators 数据, 含PandasTa,BtInd,TqFunc,TaLib,FinTa,AutoTrader,SignalFeatures
                source = source._df  # kline数据
                source_type = type(source)

            # 指标属性
            source_indsetting = source.get_indicator_kwargs(isindicator=True) if hasattr(
                source, "_indsetting") else {}

            # 是否为自定义指标
            myself = kwargs_.pop('myself', False)
            if myself:
                func_name = myself
            else:
                func_name = f"{_lib}_{func_name}"
                ind_func: Callable = getattr(getattr(source, "ta"), func_name)
            sname = kwargs.pop("sname", _sname or func_name)
            # ind_name = kwargs.pop("ind_name", _ind_name or func_name)
            ind_name = func_name
            category = kwargs.pop('category', _category)
            isplot = kwargs.pop('isplot',  _isplot)
            ismain = kwargs.pop('ismain', False)
            lines = kwargs.pop('lines',  _lines)
            overlap = kwargs.pop("overlap", _overlap)
            light_chart = kwargs.pop("light_chart",  False)
            index = kwargs.get("_multi_index",  _index)
            isindicator = kwargs.get("isindicator",  _isindicator)
            iscustom = kwargs.get("iscustom",  False)
            linestyle = kwargs.get("linestyle",  _linestyle)
            id = kwargs.get("id", source_indsetting.get("id", BtID()))  # 继承id

            isresample = source_indsetting.get(
                "isresample", kwargs.get("isresample", False))
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

                def core(index=0, data_=None, length=100):
                    if len(data_) < length:
                        return index, nan_data
                    if myself:
                        _args = [data_,]
                        _args.extend(ind_params)
                        return index, func(*_args, **kwargs).values[-1]
                    else:
                        return index, getattr(getattr(data_, "ta"), func_name)(*ind_params, **kwargs).values[-1]

                klines = source.source._replay_datas(source.ind_name) if type(
                    source) == Line else source._replay_datas()

                @retry_with_different_params(length_ls)
                def retry(length):
                    return TPE.run(partial(core, length=length), klines, **kwargs)
                ind_data = retry()
            else:
                if myself:
                    _args = [source,]
                    _args.extend(ind_params)
                    ind_data = func(*_args, **kwargs)
                    # 通过lines设置指标线，next函数中不需要返回数据
                    if ind_data is None and type(source.lines) == Lines and source.lines._lines:
                        # 类设置了lines与indicator.lines.name = value赋值不兼容
                        # assert not lines, "通过 indicator.lines.name = value 来赋值时不需要对lines进行定义"
                        lines, ind_data = list(source.lines._lines.keys()), list(
                            source.lines._lines.values())

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
            # category = getattr(
            #     ind_data, 'category', category)
            # overlap = category == 'overlap' or overlap

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
                data = IndFrame(data, id=id, sname=sname, ind_name=ind_name, lines=Lines(*lines), category=category,
                                isplot=isplot, ismain=ismain, isreplay=isreplay, isresample=isresample,
                                overlap=overlap, isindicator=isindicator, iscustom=iscustom, linestyle=linestyle, source=source)
            else:

                data = IndSeries(data, id=id, sname=sname, ind_name=ind_name, lines=Lines(ind_name), category=category,
                                 isplot=isplot, ismain=ismain, isreplay=isreplay, isresample=isresample,
                                 overlap=overlap, isindicator=isindicator, iscustom=iscustom, linestyle=linestyle, source=source)
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


class BtBaseWindows:
    """
    量化回测框架中的窗口操作基类
    为滚动窗口、指数加权移动窗口、扩展窗口提供统一的基础功能封装

    核心功能：
    1. 统一封装 Pandas 窗口操作类的通用逻辑（Rolling、ExponentialMovingWindow、Expanding）
    2. 通过装饰器模式重写窗口方法，自动将返回结果转换为框架内置的 IndSeries/IndFrame 类型
    3. 提供统一的参数分离机制，区分原生窗口参数和框架扩展参数
    4. 自动继承和增强指标配置（名称、绘图设置、数据重叠等）

    设计模式：
    - 装饰器模式：通过 _wrap_pandas_rolling_method_to_indicator 装饰原生窗口方法
    - 模板方法模式：为子类提供统一的窗口操作处理流程
    - 属性拦截模式：通过 __getattribute__ 动态拦截和包装方法调用

    继承关系：
        BtBaseWindows
          ├── BtRolling
          ├── BtExponentialMovingWindow
          └── BtExpanding

    使用场景：
    - 技术指标计算（移动平均、标准差、相关系数等）
    - 时序数据分析（滚动统计、指数平滑、累积计算）
    - 量化策略开发（动量指标、波动率指标、趋势指标）
    """

    _obj: Union[IndFrame, IndSeries, Line]
    """输入数据对象，必须是框架支持的 IndSeries/IndFrame/Line 类型"""

    _base_object: Union[Rolling, ExponentialMovingWindow, Expanding]
    """底层的 Pandas 窗口对象，执行实际的窗口计算"""

    _method: set[str]
    """该窗口类型支持的方法名称集合，用于属性访问拦截"""

    def __init__(self, obj: Union[IndFrame, IndSeries, Line], method_list: set[str]):
        """
        初始化窗口操作基类

        Args:
            obj: 输入数据对象，必须包含 pandas_object 属性（存储原生 Pandas 对象）
            method_list: 该窗口类型支持的方法名称集合，用于动态方法包装

        设计说明：
        - 将 method_list 作为实例属性传入，避免类属性在继承时的循环引用问题
        - 子类负责创建具体的 _base_object（Rolling/ExponentialMovingWindow/Expanding）
        - 统一的初始化流程确保所有窗口类具有一致的行为
        """
        self._obj = obj
        self._method = method_list  # 作为实例属性传入，避免循环引用
        # 断言校验：输入对象必须包含 'pandas_object' 属性（确保是框架支持的数据类型）
        # pandas_object 用于存储原生 Pandas Series/DataFrame，供后续滚动计算使用
        assert hasattr(
            self._obj, 'pandas_object'), f'{self.__class__.__name__}数据对象必须是IndSeries、IndFrame或Line类型（需包含pandas_object属性）'

    def _wrap_pandas_rolling_method_to_indicator(self, func: Callable) -> Callable:
        """
        类装饰器：将 Pandas 窗口原生方法的返回结果，转换为框架内置的指标数据类型

        核心作用：
        1. 保留原生方法的计算逻辑，仅增强返回结果的类型适配
        2. 自动补充指标配置参数（如名称、计算设置），便于策略管理指标
        3. 根据返回数据的维度（Series/DataFrame），生成对应的框架数据类型
        4. 支持参数分离，区分窗口计算参数和框架扩展参数

        实现机制：
        - 使用 functools.wraps 保留原函数的元信息（名称、文档字符串等）
        - 通过 inspect.signature 动态分析参数签名，实现智能参数分离
        - 根据返回数据的形状和类型，自动选择转换为 IndSeries 或 IndFrame

        Args:
            func: 待装饰的函数（Pandas 窗口原生方法，如 mean、std、sum 等）

        Returns:
            装饰后的函数：返回框架内置的 IndSeries/IndFrame 类型，或原结果（非 Pandas 对象时）

        处理流程：
        1. 参数分离 → 2. 调用原生方法 → 3. 类型检查 → 4. 配置增强 → 5. 类型转换

        示例：
        >>> # 装饰前：返回 pd.Series
        >>> result = self._base_object.mean()
        >>> type(result)  # pandas.core.IndSeries.Series
        >>>
        >>> # 装饰后：返回 framework.IndSeries
        >>> result = wrapped_mean()
        >>> type(result)  # minibt.core.IndSeries

        注意事项：
        - 确保输入数据对象具有 pandas_object 属性
        - 转换前检查数据长度一致性（data.shape[0] == self._obj.V）
        - 自动处理指标名称和配置参数的继承与增强
        """
        @wraps(func)  # 保留原方法的元信息（名称、文档字符串、注解等）
        def wrapper(*args, **kwargs):
            """
            装饰器内部包装函数：执行原生计算并转换返回类型

            参数处理逻辑：
            - 分离为 method_kwargs（传递给Pandas原生方法）
            - 分离为 indicator_kwargs（框架指标扩展参数）
            - 支持 *args 位置参数传递

            类型转换条件：
            - 结果是 pd.Series 或 pd.DataFrame 类型
            - 数据长度与输入对象一致（data.shape[0] == self._obj.V）
            - 非 Pandas 对象（如标量、None）直接返回

            配置增强逻辑：
            - 自动设置 isindicator=True 标记
            - 继承原指标的 sname、ind_name 等配置
            - 生成合理的指标名称（格式：原指标名_窗口方法名）
            - 自动处理 lines 配置（单列→[func_name]，多列→data.columns）
            """
            # 1. 获取原生方法的参数签名，确定参数分类边界
            sig = signature(func)
            params = sig.parameters.keys()

            # 2. 智能参数分离：窗口计算参数 vs 框架扩展参数
            method_kwargs = {}  # 传递给 Pandas 原生窗口方法的参数
            indicator_kwargs = {}  # 框架指标的扩展参数（名称、绘图、重叠等）
            func_name = func.__name__

            for key, value in kwargs.items():
                if key in params:
                    method_kwargs[key] = value  # 窗口方法原生参数
                else:
                    indicator_kwargs[key] = value  # 框架扩展参数

            # 3. 调用底层 Pandas 窗口方法执行实际计算
            data: pd.Series | pd.DataFrame = getattr(
                self._base_object, func_name)(*args, **method_kwargs)

            # 4. 类型检查和转换：仅对 Pandas 对象且长度一致的数据进行转换
            if isinstance(data, (pd.DataFrame, pd.Series)):
                if options.check_conversion(data, self._obj.V):
                    # 4.1 配置增强：标记为指标并继承原对象配置
                    indicator_kwargs.update(dict(isindicator=True))
                    indicator_kwargs = self._obj.get_indicator_kwargs(
                        **indicator_kwargs)

                    # 4.2 名称处理：生成合理的指标名称
                    sname = indicator_kwargs.get("sname", func_name)
                    ind_name = indicator_kwargs.get("ind_name", func_name)
                    indicator_kwargs.pop('lines', None)  # 移除原有 lines 配置

                    # 4.3 名称增强：格式为"原指标名_窗口方法名"（如 close_rolling_mean）
                    indicator_kwargs['sname'] = f"{sname}_{func_name}"
                    indicator_kwargs["ind_name"] = f"{ind_name}_{func_name}"

                    # 4.4 多列数据（DataFrame）处理
                    if len(data.shape) > 1:  # 二维数据，多列输出
                        indicator_kwargs["lines"] = list(data.columns)
                        return IndFrame(data.values, **indicator_kwargs)

                    # 4.5 单列数据（Series）处理
                    else:
                        indicator_kwargs['lines'] = [func_name,]
                        return IndSeries(data.values, **indicator_kwargs)

            # 5. 非 Pandas 对象或长度不匹配时直接返回（如标量、None 等）
            return data

        return wrapper

    def __getattribute__(self, item) -> IndSeries | IndFrame | pd.Series | pd.DataFrame | Any:
        """
        重写属性访问方法：动态拦截窗口方法调用并应用装饰器

        核心机制：
        - 通过属性名称拦截，对支持的窗口方法自动应用类型转换装饰器
        - 使用 object.__getattribute__ 安全访问 _method 属性，避免循环引用
        - 保持非窗口方法属性的正常访问逻辑

        拦截逻辑：
        - 检查属性名是否在 _method 集合中（预设的窗口方法列表）
        - 是：获取原始方法 → 应用装饰器 → 返回包装后的方法
        - 否：正常属性访问逻辑

        Args:
            item: 要访问的属性名（如 'mean'、'std'、'sum' 或其他属性）

        Returns:
            - 窗口方法：返回装饰后的方法（自动转换返回类型）
            - 其他属性：直接返回父类处理结果

        技术细节：
        - 使用 object.__getattribute__ 绕过常规属性查找，避免递归
        - 装饰器应用时机：在方法被调用前动态包装，不影响方法定义
        - 保持方法调用的透明性，用户无需感知底层转换逻辑

        示例：
        >>> rolling_obj = self.data.close.rolling(10)
        >>> # 以下调用会自动被拦截和装饰：
        >>> mean_indicator = rolling_obj.mean(overlap=True)  # 返回 framework.IndSeries
        >>> std_indicator = rolling_obj.std()  # 返回 framework.IndSeries
        >>> # 非窗口方法正常访问：
        >>> window_size = rolling_obj.window  # 直接返回整数值
        """
        # 安全获取 _method 集合，避免触发 __getattribute__ 递归
        _method_set = object.__getattribute__(self, '_method')

        # 拦截窗口方法调用：应用类型转换装饰器
        if item in _method_set:
            original_method = super().__getattribute__(item)
            return self._wrap_pandas_rolling_method_to_indicator(original_method)

        # 非窗口方法：正常属性访问逻辑
        return super().__getattribute__(item)


class BtRolling(BtBaseWindows):
    """
    量化回测框架中的滚动窗口（Rolling）增强类，继承自基础 Rolling 类
    核心功能：
    1. 封装 Pandas 的 Rolling 功能，限制输入数据类型为框架支持的 IndSeries/IndFrame/Line
    2. 重写属性访问逻辑，将 Pandas Rolling 原生方法（如 mean、std）的返回结果
       自动转换为框架内置的 IndSeries/IndFrame 类型（而非原生 Pandas 对象）
    3. 自动补充指标配置参数（如名称、计算设置），适配回测策略的指标管理体系
    """

    def __init__(self,
                 obj: Union[IndFrame, IndSeries, Line],
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
            obj: 输入数据对象（必须是框架自定义的 IndFrame/IndSeries/Line 类型，需包含 pandas_object 属性）
            window: 滚动窗口大小（如 5 表示 5 期窗口，支持 int/offset 等 Pandas 兼容类型）
            min_periods: 窗口内最小非空值数量（低于此数量则结果为 NaN，默认 None 即等于 window 大小）
            center: 是否将窗口结果对齐到窗口中心（默认 False，对齐到窗口末尾）
            win_type: 窗口权重类型（默认 None 为等权重，支持 'boxcar'/'triang' 等 Pandas 支持类型）
            on: 用于滚动计算的列名（仅 IndFrame 有效，默认 None 表示用所有列）
            axis: 滚动轴方向（0 为按行滚动/时间维度，1 为按列滚动/特征维度，默认 0）
            closed: 窗口闭合方式（如 'right' 表示包含右边界，默认 None 跟随 Pandas 规则）
            step: 窗口步长（默认 None 为 1，即每步滑动 1 个单位）
            method: 计算方法（默认 'single'，预留参数用于扩展批量计算逻辑）

        关键逻辑：
        - 校验输入数据对象必须包含 'pandas_object' 属性（存储原生 Pandas 对象，如 pd.Series/pd.DataFrame）
        - 调用父类 Rolling 的初始化方法，传入原生 Pandas 对象和滚动参数
        """
        super().__init__(obj, rolling_method)

        # 调用父类 Rolling 的构造方法，初始化滚动窗口（传入原生 Pandas 对象和配置参数）
        self._base_object = Rolling(
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

    def skew(self, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的偏度（衡量数据分布不对称性）
        Args:
            numeric_only: 是否仅对数值型列计算（默认 False）
            **kwargs: 框架扩展参数（如指标名称、绘图配置等）
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def cov(self, other=None, pairwise=None, ddof=1, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的协方差（衡量两变量线性相关程度）
        Args:
            other: 对比变量（默认 None，计算自身协方差）
            pairwise: 是否两两计算协方差（默认 None，跟随 pandas 规则）
            ddof: 自由度（默认 1，样本协方差）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def mean(self, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的均值（平均值）
        Args:
            numeric_only: 是否仅对数值型列计算（默认 False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def agg(self, func, engine=None, engine_kwargs=None, **kwargs) -> IndFrame | IndSeries:
        """
        滚动窗口内的聚合计算（支持自定义函数）
        Args:
            func: 聚合函数（如 'sum'、lambda 或函数列表）
            engine: 计算引擎（默认 None，用 pandas 原生引擎）
            engine_kwargs: 引擎参数（默认 None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def count(self, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        统计滚动窗口内的非空值数量
        Args:
            numeric_only: 是否仅统计数值型列（默认 False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def quantile(self, q=0.5, interpolation='linear', numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的分位数（默认中位数，q=0.5）
        Args:
            q: 分位数（如 0.25 为四分位数，0.5 为中位数）
            interpolation: 插值方式（默认 'linear'，处理分位数落在两数之间的情况）
            numeric_only: 是否仅对数值型列计算（默认 False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def max(self, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的最大值
        Args:
            numeric_only: 是否仅对数值型列计算（默认 False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def aggregate(self, func, engine=None, engine_kwargs=None, **kwargs) -> IndFrame | IndSeries:
        """
        同 agg 方法，滚动窗口内的聚合计算（支持自定义函数）
        Args:
            参数同 agg 方法
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def corr(self, other=None, pairwise=None, ddof=1, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的相关系数（衡量两变量线性相关强度，范围 [-1,1]）
        Args:
            other: 对比变量（默认 None，计算自身相关）
            pairwise: 是否两两计算相关系数（默认 None，跟随 pandas 规则）
            ddof: 自由度（默认 1，样本相关系数）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def rank(self, axis=0, method='average', na_option='keep', ascending=True, pct=False, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的排名（对窗口内数据排序并分配名次）
        Args:
            axis: 排名轴（默认 0，按行排名）
            method: 排名方式（默认 'average'，相同值取平均名次）
            na_option: NaN 处理（默认 'keep'，保留 NaN 不参与排名）
            ascending: 是否升序（默认 True，小值排名靠前）
            pct: 是否返回百分比排名（默认 False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def sem(self, numeric_only: bool = False, ddof=1, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的标准误（均值的标准偏差，反映均值的抽样误差）
        Args:
            numeric_only: 是否仅对数值型列计算（默认 False）
            ddof: 自由度（默认 1）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def var(self, numeric_only: bool = False, ddof=1, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的方差（衡量数据离散程度）
        Args:
            numeric_only: 是否仅对数值型列计算（默认 False）
            ddof: 自由度（默认 1，样本方差）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def apply(self, func, raw=False, engine=None, engine_kwargs=None, args=None, **kwargs) -> IndFrame | IndSeries:
        """
        对滚动窗口内的数据应用自定义函数（灵活扩展计算逻辑）
        Args:
            func: 自定义函数（输入为窗口数据，返回计算结果）
            raw: 是否传入原始数组（默认 False，传入 Series/DataFrame）
            engine: 计算引擎（默认 None，用 pandas 原生引擎）
            args: 函数额外参数（默认 None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def sum(self, numeric_only: bool = False, min_count=0, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的求和
        Args:
            numeric_only: 是否仅对数值型列计算（默认 False）
            min_count: 最小非空值数量（默认 0，不足则结果为 0）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def min(self, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的最小值
        Args:
            numeric_only: 是否仅对数值型列计算（默认 False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def kurt(self, numeric_only: bool = False, fisher=True, bias=False, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的峰度（衡量数据分布陡峭程度）
        Args:
            numeric_only: 是否仅对数值型列计算（默认 False）
            fisher: 是否返回 Fisher 峰度（默认 True，减去 3 使正态分布峰度为 0）
            bias: 是否修正偏差（默认 False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def median(self, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的中位数（数据排序后的中间值，抗极端值）
        Args:
            numeric_only: 是否仅对数值型列计算（默认 False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...

    def std(self, numeric_only: bool = False, ddof=1, **kwargs) -> IndFrame | IndSeries:
        """
        计算滚动窗口内的标准差（方差的平方根，衡量数据离散程度）
        Args:
            numeric_only: 是否仅对数值型列计算（默认 False）
            ddof: 自由度（默认 1，样本标准差）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的 IndFrame/IndSeries 类型结果
        """
        ...


class BtExponentialMovingWindow(BtBaseWindows):
    """
    量化回测框架中的指数加权移动窗口（Exponential Moving Window）增强类
    核心功能：
    1. 封装 Pandas 的 ExponentialMovingWindow 功能，限制输入数据类型为框架支持的 IndSeries/IndFrame/Line
    2. 重写属性访问逻辑，将 Pandas EWM 原生方法（如 mean、std）的返回结果
       自动转换为框架内置的 IndSeries/IndFrame 类型（而非原生 Pandas 对象）
    3. 自动补充指标配置参数（如名称、计算设置），适配回测策略的指标管理体系
    4. 支持多种衰减参数（com、span、halflife、alpha），确保参数互斥性检查
    """

    def __init__(
        self,
        obj: Union[IndFrame, IndSeries, Line],
        com: float | None = None,
        span: float | None = None,
        halflife: float | Union[timedelta, np.timedelta64,
                                np.int64, float, str] | None = None,
        alpha: float | None = None,
        min_periods: int | None = 0,
        adjust: bool = True,
        ignore_na: bool = False,
        axis: Union[int, Literal["index", "columns", "rows"]] = 0,
        times: np.ndarray | pd.Series | pd.DataFrame | None = None,
        method: str = "single",
        *,
        selection=None,
    ) -> None:
        """
        初始化 BtExponentialMovingWindow 实例（指数加权移动窗口配置）

        Args:
            obj: 输入数据对象（必须是框架自定义的 IndFrame/IndSeries/Line 类型，需包含 pandas_object 属性）
            com: 质心衰减参数（定义衰减方式，alpha = 1 / (1 + com)，与其他衰减参数互斥）
            span: 时间跨度衰减参数（大致对应窗口大小，alpha = 2 / (span + 1)，与其他衰减参数互斥）
            halflife: 半衰期衰减参数（权重减半所需时间，与其他衰减参数互斥）
            alpha: 直接平滑因子（值在0-1之间，与其他衰减参数互斥）
            min_periods: 窗口内最小非空值数量（默认0）
            adjust: 是否使用精确权重计算（默认True，False使用递归公式，金融场景推荐False）
            ignore_na: 是否忽略NaN值（默认False）
            axis: 计算轴方向（0为按行/时间维度，1为按列/特征维度，默认0）
            times: 时间序列（仅当halflife为时间类型时有效，默认None）
            method: 计算方法（默认"single"，预留参数用于扩展批量计算逻辑）
            selection: 选择特定列计算（默认None，表示所有列）

        关键逻辑：
        - 校验输入数据对象必须包含 'pandas_object' 属性
        - 检查衰减参数互斥性（com、span、halflife、alpha只能使用其中一个）
        - 调用父类 ExponentialMovingWindow 的初始化方法，传入原生 Pandas 对象和配置参数
        """
        super().__init__(obj, ewm_method)

        # 参数互斥性检查
        non_none_params = [p for p in [
            com, span, halflife, alpha] if p is not None]
        if len(non_none_params) > 1:
            raise ValueError("com、span、halflife 和 alpha 参数是互斥的，只能指定其中一个")

        # 如果没有指定任何衰减参数，使用默认的 com=0.5
        if len(non_none_params) == 0:
            com = 0.5  # pandas 的默认值

        # 调用父类 ExponentialMovingWindow 的构造方法，初始化指数加权移动窗口
        self._base_object = ExponentialMovingWindow(
            self._obj.pandas_object,
            com=com,
            span=span,
            halflife=halflife,
            alpha=alpha,
            min_periods=min_periods,
            adjust=adjust,
            ignore_na=ignore_na,
            axis=axis,
            times=times,
            method=method,
            selection=selection
        )

    def mean(self, numeric_only: bool = False, engine=None, engine_kwargs=None, **kwargs) -> IndFrame | IndSeries:
        """
        计算指数加权移动平均（Exponentially Weighted Moving Average）
        Args:
            numeric_only: 是否仅对数值型列计算（默认False）
            engine: 计算引擎（默认None，用pandas原生引擎）
            engine_kwargs: 引擎参数（默认None）
            **kwargs: 框架扩展参数（如指标名称、绘图配置等）
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储指数加权移动平均值
        """
        ...

    def sum(self, numeric_only: bool = False, engine=None, engine_kwargs=None, **kwargs) -> IndFrame | IndSeries:
        """
        计算指数加权移动求和（Exponentially Weighted Moving Sum）
        Args:
            numeric_only: 是否仅对数值型列计算（默认False）
            engine: 计算引擎（默认None，用pandas原生引擎）
            engine_kwargs: 引擎参数（默认None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储指数加权移动求和值
        """
        ...

    def std(self, bias: bool = False, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算指数加权移动标准差（Exponentially Weighted Moving Standard Deviation）
        Args:
            bias: 是否使用有偏估计（默认False，使用无偏估计）
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储指数加权移动标准差
        """
        ...

    def var(self, bias: bool = False, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算指数加权移动方差（Exponentially Weighted Moving Variance）
        Args:
            bias: 是否使用有偏估计（默认False，使用无偏估计）
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储指数加权移动方差
        """
        ...

    def cov(self, other: pd.DataFrame | pd.Series | None = None, pairwise: bool | None = None,
            bias: bool = False, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算指数加权移动协方差（Exponentially Weighted Moving Covariance）
        Args:
            other: 对比变量（默认None，计算自身协方差）
            pairwise: 是否两两计算协方差（默认None，跟随pandas规则）
            bias: 是否使用有偏估计（默认False，使用无偏估计）
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储指数加权移动协方差
        """
        ...

    def corr(self, other: pd.DataFrame | pd.Series | None = None, pairwise: bool | None = None,
             numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算指数加权移动相关系数（Exponentially Weighted Moving Correlation）
        Args:
            other: 对比变量（默认None，计算自身相关）
            pairwise: 是否两两计算相关系数（默认None，跟随pandas规则）
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储指数加权移动相关系数
        """
        ...


class BtExpanding(BtBaseWindows):
    """
    量化回测框架中的扩展窗口（Expanding Window）增强类
    核心功能：
    1. 封装 Pandas 的 Expanding 功能，限制输入数据类型为框架支持的 IndSeries/IndFrame/Line
    2. 重写属性访问逻辑，将 Pandas Expanding 原生方法（如 mean、std）的返回结果
       自动转换为框架内置的 IndSeries/IndFrame 类型（而非原生 Pandas 对象）
    3. 自动补充指标配置参数（如名称、计算设置），适配回测策略的指标管理体系
    4. 支持从数据起始点到当前点的累积统计计算，常用于计算全样本统计量
    """

    def __init__(
        self,
        obj: Union[IndFrame, IndSeries, Line],
        min_periods: int = 1,
        axis: Union[int, Literal["index", "columns", "rows"]] = 0,
        method: str = "single",
        selection=None,
    ) -> None:
        """
        初始化 BtExpanding 实例（扩展窗口配置）

        Args:
            obj: 输入数据对象（必须是框架自定义的 IndFrame/IndSeries/Line 类型，需包含 pandas_object 属性）
            min_periods: 窗口内最小非空值数量（默认1，即从第1个数据点开始计算）
            axis: 计算轴方向（0为按行/时间维度，1为按列/特征维度，默认0）
            method: 计算方法（默认"single"，预留参数用于扩展批量计算逻辑）
            selection: 选择特定列计算（默认None，表示所有列）

        关键逻辑：
        - 校验输入数据对象必须包含 'pandas_object' 属性
        - 调用父类 Expanding 的初始化方法，传入原生 Pandas 对象和扩展窗口参数
        - 扩展窗口从数据起始点开始，逐步包含更多数据点，计算累积统计量
        """
        super().__init__(obj, expanding_method)

        # 调用父类 Expanding 的构造方法，初始化扩展窗口（传入原生 Pandas 对象和配置参数）
        self._base_object = Expanding(
            self._obj.pandas_object,
            min_periods=min_periods,
            axis=axis,
            method=method,
            selection=selection
        )

    def count(self, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        统计扩展窗口内的非空值数量（从起始点到当前点的累积计数）
        Args:
            numeric_only: 是否仅统计数值型列（默认False）
            **kwargs: 框架扩展参数（如指标名称、绘图配置等）
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积非空值数量
        """
        ...

    def apply(self, func: Callable[..., Any], raw: bool = False,
              engine: Literal["cython", "numba"] | None = None,
              engine_kwargs: dict[str, bool] | None = None,
              args: tuple[Any, ...] | None = None, **kwargs: dict[str, Any]) -> IndFrame | IndSeries:
        """
        对扩展窗口内的数据应用自定义函数（支持累积计算逻辑）
        Args:
            func: 自定义函数（输入为窗口数据，返回计算结果）
            raw: 是否传入原始数组（默认False，传入Series/DataFrame）
            engine: 计算引擎（默认None，用pandas原生引擎；"cython"或"numba"用于性能优化）
            engine_kwargs: 引擎参数（默认None）
            args: 函数额外参数（默认None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储自定义函数的累积计算结果
        """
        ...

    def sum(self, numeric_only: bool = False,
            engine: Literal["cython", "numba"] | None = None,
            engine_kwargs: dict[str, bool] | None = None, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积和（从起始点到当前点的累加值）
        Args:
            numeric_only: 是否仅对数值型列计算（默认False）
            engine: 计算引擎（默认None，用pandas原生引擎）
            engine_kwargs: 引擎参数（默认None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积和
        """
        ...

    def max(self, numeric_only: bool = False,
            engine: Literal["cython", "numba"] | None = None,
            engine_kwargs: dict[str, bool] | None = None, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积最大值（从起始点到当前点的历史最大值）
        Args:
            numeric_only: 是否仅对数值型列计算（默认False）
            engine: 计算引擎（默认None，用pandas原生引擎）
            engine_kwargs: 引擎参数（默认None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积最大值
        """
        ...

    def min(self, numeric_only: bool = False,
            engine: Literal["cython", "numba"] | None = None,
            engine_kwargs: dict[str, bool] | None = None, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积最小值（从起始点到当前点的历史最小值）
        Args:
            numeric_only: 是否仅对数值型列计算（默认False）
            engine: 计算引擎（默认None，用pandas原生引擎）
            engine_kwargs: 引擎参数（默认None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积最小值
        """
        ...

    def mean(self, numeric_only: bool = False,
             engine: Literal["cython", "numba"] | None = None,
             engine_kwargs: dict[str, bool] | None = None, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积均值（从起始点到当前点的移动平均值）
        Args:
            numeric_only: 是否仅对数值型列计算（默认False）
            engine: 计算引擎（默认None，用pandas原生引擎）
            engine_kwargs: 引擎参数（默认None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积均值
        """
        ...

    def median(self, numeric_only: bool = False,
               engine: Literal["cython", "numba"] | None = None,
               engine_kwargs: dict[str, bool] | None = None, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积中位数（从起始点到当前点的移动中位数）
        Args:
            numeric_only: 是否仅对数值型列计算（默认False）
            engine: 计算引擎（默认None，用pandas原生引擎）
            engine_kwargs: 引擎参数（默认None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积中位数
        """
        ...

    def std(self, ddof: int = 1, numeric_only: bool = False,
            engine: Literal["cython", "numba"] | None = None,
            engine_kwargs: dict[str, bool] | None = None, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积标准差（从起始点到当前点的移动标准差）
        Args:
            ddof: 自由度（默认1，样本标准差）
            numeric_only: 是否仅对数值型列计算（默认False）
            engine: 计算引擎（默认None，用pandas原生引擎）
            engine_kwargs: 引擎参数（默认None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积标准差
        """
        ...

    def var(self, ddof: int = 1, numeric_only: bool = False,
            engine: Literal["cython", "numba"] | None = None,
            engine_kwargs: dict[str, bool] | None = None, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积方差（从起始点到当前点的移动方差）
        Args:
            ddof: 自由度（默认1，样本方差）
            numeric_only: 是否仅对数值型列计算（默认False）
            engine: 计算引擎（默认None，用pandas原生引擎）
            engine_kwargs: 引擎参数（默认None）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积方差
        """
        ...

    def sem(self, ddof: int = 1, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积标准误（均值的标准偏差，反映均值的抽样误差）
        Args:
            ddof: 自由度（默认1）
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积标准误
        """
        ...

    def skew(self, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积偏度（衡量数据分布不对称性的变化）
        Args:
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积偏度
        """
        ...

    def kurt(self, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积峰度（衡量数据分布陡峭程度的变化）
        Args:
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积峰度
        """
        ...

    def quantile(self, q: float, interpolation: Literal["linear", "lower", "higher", "midpoint", "nearest"] = "linear",
                 numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积分位数（从起始点到当前点的移动分位数）
        Args:
            q: 分位数（0-1之间，如0.5为中位数）
            interpolation: 插值方式（默认"linear"，处理分位数落在两数之间的情况）
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积分位数
        """
        ...

    def rank(self, method: Literal["average", "min", "max"] = "average",
             ascending: bool = True, pct: bool = False, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积排名（对从起始点到当前点的数据进行排序分配名次）
        Args:
            method: 排名方式（默认"average"，相同值取平均名次）
            ascending: 是否升序（默认True，小值排名靠前）
            pct: 是否返回百分比排名（默认False）
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积排名
        """
        ...

    def cov(self, other: pd.DataFrame | pd.Series | None = None, pairwise: bool | None = None,
            ddof: int = 1, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积协方差（从起始点到当前点的移动协方差）
        Args:
            other: 对比变量（默认None，计算自身协方差）
            pairwise: 是否两两计算协方差（默认None，跟随pandas规则）
            ddof: 自由度（默认1，样本协方差）
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积协方差
        """
        ...

    def corr(self, other: pd.DataFrame | pd.Series | None = None, pairwise: bool | None = None,
             ddof: int = 1, numeric_only: bool = False, **kwargs) -> IndFrame | IndSeries:
        """
        计算扩展窗口内的累积相关系数（从起始点到当前点的移动相关系数）
        Args:
            other: 对比变量（默认None，计算自身相关）
            pairwise: 是否两两计算相关系数（默认None，跟随pandas规则）
            ddof: 自由度（默认1，样本相关系数）
            numeric_only: 是否仅对数值型列计算（默认False）
            **kwargs: 框架扩展参数
        Returns:
            框架自定义的IndFrame/IndSeries类型结果，存储累积相关系数
        """
        ...


@dataclass
class KLineSetting(DataSetBase):
    symbol_info: SymbolInfo
    current_close: np.ndarray
    current_datetime: np.ndarray
    isstop: bool = False
    stop: Optional[Stop] = None
    stop_lines: Optional[IndFrame] = None
    tradable: bool = True
    istrader: bool = False
    follow: bool = True
    plot_index: Optional[list[int]] = None

    def set_default_stop_lines(self, id: BtID):
        self.stop_lines = IndFrame((len(self.current_close), 2), id=id.copy(), isplot=True, overlap=True, lines=[
            'stop_price', 'target_price'], sname="stop_lines", ind_name="stop_lines")
        self.stop_lines.plotinfo.spanstyle = SpanList()


class IndicatorsBase(Base):
    """
    量化指标基类（所有指标/数据对象的父类）
    核心定位：统一封装指标与K线数据的共性能力，包括数据访问、运算支持、绘图配置、多周期处理等，
    为子类（如Line、IndSeries、IndFrame、KLine）提供标准化接口，实现指标与数据的无缝交互。

    核心设计：
    1. 多类型兼容：支持单值（Line）、一维（IndSeries）、多维（IndFrame）数据，统一接口操作
    2. 运算重载：内置算术/比较/逻辑运算符，支持指标间直接运算（如ma5 + ma10）
    3. 绘图配置：集成PlotInfo管理绘图属性（线型、颜色、是否主图叠加等）
    4. 多周期处理：支持数据上采样（resample）、跨周期关联，适配多周期策略
    5. 信号集成：内置交易信号字段（开多/平多/开空/平空），支持策略自动识别信号
    """
    # ------------------------------
    # 核心属性（控制数据类型与行为）
    # ------------------------------
    # 是否为多维数据（True=IndFrame，False=IndSeries/Line）
    # _isMDim: bool
    # 指标数据与原数据维度是否一致（True=自动被策略收集，False=仅内置使用）
    _dim_match: bool
    # 上采样数据中用于关联原数据的名称（多周期处理用）
    _upsample_name: str = ""
    # 交易信号标识列表（记录当前指标包含的信号类型）
    _issignal: list[str]
    # 交易信号字段（初始为None，策略运行中动态生成）
    _long_signal: IndSeries | None = None  # 开多信号
    _exitlong_signal: IndSeries | None = None  # 平多信号
    _short_signal: IndSeries | None = None  # 开空信号
    _exitshort_signal: IndSeries | None = None  # 平空信号
    # IndFrame数据中的Line字段列表（记录多维指标的列名）
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
    # 停止线（如止损线、止盈线，关联IndFrame）
    _stop_lines: IndFrame
    # 交易代理（关联Broker，处理下单、手续费计算等）
    _broker: Broker
    # 指标内置数据集（管理原始数据、转换数据等）
    _dataset: DataFrameSet
    _tqobj: TqObjs
    # 行/列数量（V=rows，H=columns）
    # _v: int  # 行
    # _h: int  # 列

    # ------------------------------
    # 核心属性接口（关联KLine与策略）
    # ------------------------------

    @property
    def kline(self) -> Union[KLine, IndFrame, IndSeries, Line]:
        """### 获取当前指标关联的KLine数据（属性接口）
        非指标对象（如KLine自身）返回自身，指标对象通过data_id关联到对应的KLine

        Returns:
            KLine: 关联的K线数据对象
        """
        """### 指标对应的KLine数据"""
        if not self.isindicator:
            return self
        return self._get_kline(self.data_id)

    @cachedmethod(attrgetter('cache'))
    def _get_kline(self, data_id: int):
        """### 缓存并获取KLine数据（内部方法，供kline属性调用）
        基于data_id从策略的_btklinedataset中获取对应的KLine，缓存结果避免重复查找

        Args:
            kline_id (int): KLine的唯一标识ID

        Returns:
            KLine: 对应的K线数据对象
        """
        """### 缓存KLine数据"""
        return self.strategy_instance._btklinedataset[data_id]

    # ------------------------------
    # 交易逻辑与配置接口
    # ------------------------------
    def setp(self):
        """### 交易逻辑扩展接口（抽象方法，可被子类重写）
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
                if not self.kline.position.pos:
                    if self.long_signal.new:
                        self.kline.buy()
                    elif self.short_signal.new:
                        self.kline.sell()
                else:
                    if self.short_signal.new:
                        self.kline.set_target_size(-1)
                    elif self.long_signal.new:
                        self.kline.set_target_size(1)
        """
        ...

    def get_first_valid_index(self, *args: tuple[np.ndarray, pd.Series], include_self: bool = False) -> int:
        """### 获取多个数组中第一个有效数据的起始索引

        计算多个数组或序列中第一个非NaN值的最大位置索引，
        用于确定技术指标计算的起始位置。

        Args:
            *args: 多个numpy数组或pandas Series

        Returns:
            int: 所有数组中第一个有效数据的最大起始索引
                即跳过所有开头的NaN值后的起始位置

        Example:
            >>> arr1 = np.array([np.nan, np.nan, 1, 2, 3])
            >>> arr2 = np.array([np.nan, 1, 2, 3, 4])
            >>> get_first_valid_index(arr1, arr2)
            2  # 因为arr1需要跳过2个NaN才能开始计算
        """
        args: list = [arg.values if hasattr(
            arg, "values") else arg for arg in args]
        if include_self and len(self.shape) == 1:
            args.insert(0, self.values)
        nan_counts = [len(arg[pd.isnull(arg)])
                      for arg in args if isinstance(arg, np.ndarray)]

        if len(nan_counts) == 0:
            return 0
        elif len(nan_counts) == 1:
            return nan_counts[0]
        else:
            return max(nan_counts)

    def get_indicator_kwargs(self, **kwargs) -> Addict[str, Any]:
        """### 整合指标配置参数（内部方法，供指标初始化用）
        合并_indsetting（指标设置）、_plotinfo（绘图配置）与用户传入的kwargs，返回统一参数字典

        Args:
            **kwargs: 用户传入的额外参数（优先级最高，覆盖默认配置）

        Returns:
            dict[str, Any]: 整合后的指标参数字典（Addict类型，支持属性式访问）
        """
        # 合并配置：指标设置 → 绘图配置 → 用户参数（优先级递增）
        result = Addict({**self._indsetting.vars, **self._plotinfo.vars})
        #
        if kwargs:
            key = []
            for k, v in kwargs.items():
                if isinstance(v, dict) and isinstance(result.get(k), dict):
                    result[k].update(v)
                    key.append(k)
            [kwargs.pop(k) for k in key]
        if kwargs:
            return Addict({**result, **kwargs})
        return result

    @staticmethod
    def get_max_missing_count(*args: tuple[pd.Series, np.ndarray]) -> int:
        """### 计算输入数据中缺失值数量的最大值（静态方法）
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
        """### 获取策略赋值的指标名称（属性接口）
        用于策略中标识指标（如self.ma5的sname为"ma5"），关联_plotinfo的sname字段

        Returns:
            str: 指标的策略内名称
        """
        return self._plotinfo.sname

    @sname.setter
    def sname(self, value) -> None:
        """### 设置策略赋值的指标名称（属性接口）
        仅接受非空字符串，用于自定义指标在策略中的标识

        Args:
            value (str): 新的指标名称
        """
        if value and isinstance(value, str):
            self._plotinfo.sname = value

    @property
    def ind_name(self) -> str:
        """### 获取指标自身名称（属性接口）
        用于标识指标类型（如"MA"、"RSI"），关联_plotinfo的ind_name字段

        Returns:
            str: 指标的类型名称
        """
        """### 指标名称"""
        return self._plotinfo.ind_name

    @ind_name.setter
    def ind_name(self, value) -> None:
        """### 设置指标自身名称（属性接口）
        仅接受非空字符串，用于自定义指标的类型标识

        Args:
            value (str): 新的指标类型名称
        """
        if value and isinstance(value, str):
            self._plotinfo.ind_name = value

    @property
    def id(self) -> BtID:
        """### 获取指标的唯一标识（属性接口）
        BtID包含策略ID、数据ID、绘图ID等，用于多策略、多数据的关联

        Returns:
            BtID: 指标的唯一标识对象
        """
        """### BtID"""
        return self._indsetting.id

    @id.setter
    def id(self, value) -> None:
        """### 设置指标的唯一标识（属性接口）
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
        """### 获取策略ID（属性接口，BtID分解）
        从_indsetting.id中提取strategy_id，用于关联到特定策略实例

        Returns:
            int: 策略的唯一标识ID
        """
        """### 策略ID"""
        return self._indsetting.id.strategy_id

    @property
    def sid(self) -> int:
        """### 获取策略ID（属性接口，与strategy_id功能一致，兼容简写）

        Returns:
            int: 策略的唯一标识ID
        """
        """### 策略ID"""
        return self._indsetting.id.strategy_id

    @property
    def plot_id(self) -> int:
        """### 获取绘图ID（属性接口，BtID分解）
        用于标识指标在绘图中的分组（如多合约绘图时区分不同子图）

        Returns:
            int: 绘图分组ID
        """
        """### 画图ID"""
        return self._indsetting.id.plot_id

    @property
    def data_id(self) -> int:
        """### 获取数据ID（属性接口，BtID分解）
        关联到对应的KLine数据，用于指标与K线数据的绑定

        Returns:
            int: 关联的KLineID
        """
        """### 数据ID"""
        return self._indsetting.id.data_id

    @property
    def resample_id(self) -> int:
        """### 获取转换ID（属性接口，BtID分解）
        用于标识上采样/下采样后的数据，支持多周期数据关联

        Returns:
            int: 数据转换ID
        """
        """### 转换ID"""
        return self._indsetting.id.resample_id

    @property
    def replay_id(self) -> int:
        """### 获取播放ID（属性接口，BtID分解）
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
        """### 获取指标线配置（属性接口）
        管理指标的所有线条（如MA5、MA10），支持字符串、列表、Lines对象赋值

        Returns:
            Lines: 指标线配置对象（包含所有线条名称与属性）
        """
        """### 指标线

        可设置value:
        >>> str,Iterable,Lines"""
        return self._plotinfo.lines

    @lines.setter
    def lines(self, value: Union[Iterable, dict, str]) -> None:
        """### 设置指标线配置（属性设置器）

        自动转换输入格式并更新指标线配置，支持三种输入类型：
        - 字典：键为旧指标线名称，值为新名称（仅更新字典中存在的旧指标线）
        - 字符串：单指标线名称（仅适用于IndSeries）
        - 可迭代对象：新指标线名称列表（需与原指标线数量一致，且元素均为非空字符串）

        处理逻辑：
        1. 校验输入格式并提取新旧指标线映射关系
        2. 更新内部指标线列表（new_lines）
        3. 若存在有效更新，同步更新绘图配置信息

        Args:
            value: 指标线配置值，支持dict、str或Iterable类型

        Print:
            输入格式不支持或不符合要求时触发
        """
        if not value:
            return  # 空值不处理

        # 初始化变量：存储新旧指标线映射、当前指标线列表
        new_key_mapping = {}
        current_lines = self.lines.values  # 当前指标线列表

        # 处理字典类型输入（{旧键: 新键}）
        if isinstance(value, dict):
            for old_key, new_key in value.items():
                if old_key in self.lines:  # 仅处理存在的旧指标线
                    new_key_mapping[old_key] = new_key
                    # 更新指标线列表中对应的旧键为新键
                    current_lines[current_lines.index(old_key)] = new_key

        # 处理字符串类型输入（仅单线条模式有效）
        elif isinstance(value, str) and self.H == 1 and current_lines[0] != value:
            # 记录原指标线与新名称的映射
            new_key_mapping[current_lines[0]] = value
            current_lines[0] = value

        # 处理可迭代对象（需与原指标线数量匹配）
        elif isinstance(value, Iterable) and len(self.lines) == len(value) and all([isinstance(v, str) and v for v in value]):
            value_list = list(value)
            # 生成新旧指标线映射（仅更新不同的部分）
            for idx, (old_key, new_key) in enumerate(zip(current_lines, value_list)):
                if old_key != new_key and old_key in self.lines:
                    new_key_mapping[old_key] = new_key
                    current_lines[idx] = new_key

        # 不支持的输入类型
        else:
            print(
                "不支持的输入格式！请使用：\n",
                "1. 字典：{旧指标线名称: 新指标线名称}\n",
                "2. 字符串：单指标线名称（IndSeries）\n",
                "3. 可迭代对象：与原指标线数量相同的字符串列表(IndFrame)",
            )

        # 若存在有效更新，同步更新绘图配置
        if new_key_mapping:
            self._plotinfo.lines = Lines(*current_lines)
            self._plotinfo.rename_related_keys_using_mapping(new_key_mapping)

    @property
    def line(self) -> list[Line]:
        """### 获取多维指标的Line对象列表（属性接口）
        仅对多维数据（isMDim=True）有效，返回所有列对应的Line实例

        Returns:
            list[Line]: Line对象列表（非多维数据返回空列表）
        """
        if not self._indsetting.isMDim:
            return []
        # 从指标设置的line_filed中提取Line对象
        return [getattr(self, filed) for filed in self._indsetting.line_filed]

    # ------------------------------
    # 绘图分类与样式接口
    # ------------------------------

    @property
    def category(self) -> Union[CategoryString, str]:
        """### 获取指标绘图分类（属性接口）
        标识指标的绘图类型（如"Candles"=蜡烛图、"MA"=均线、"RSI"=震荡指标）

        Returns:
            Union[CategoryString, str]: 绘图分类（支持CategoryString枚举或字符串）
        """
        return self._plotinfo.category

    @category.setter
    def category(self, value) -> None:
        """### 设置指标绘图分类（属性接口）
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
        """### 判断是否为蜡烛图类型（属性接口）
        基于category是否为"Candles"，用于绘图时区分K线与普通指标

        Returns:
            bool: True=蜡烛图，False=普通指标
        """
        """### 是否为蜡烛图"""
        return self._plotinfo.category.iscandles

    @property
    def isplot(self) -> Union[dict, bool]:
        """### 获取指标的绘图开关（属性接口）
        控制指标是否显示在图表中，支持单值（bool）或多线条配置（dict）

        Returns:
            Union[dict, bool]:
                - bool: 单线条指标的绘图开关
                - dict: 多线条指标的绘图开关（键为线条名，值为bool）
        """
        """### 是否画图

        可设置value:
        >>> IndSeries:bool
            IndFrame:bool,list[bool],tuple[bool],dict[str,bool]"""
        return self._plotinfo.isplot

    @isplot.setter
    def isplot(self, value) -> None:
        """### 设置指标的绘图开关（属性接口）
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
        """### 获取指标绘图高度（属性接口）
        控制指标在图表中的显示高度（像素），默认最小值20

        Returns:
            int: 绘图高度（像素）
        """
        """### 画图高度"""
        return self._plotinfo.height

    @height.setter
    def height(self, value: int) -> None:
        """### 设置指标绘图高度（属性接口）
        仅接受大于19的整数，确保绘图区域可见

        Args:
            value (int | float): 新的绘图高度（自动转换为整数）
        """
        if isinstance(value, (int, float)) and value > 19:
            self._plotinfo.height = int(value)

    @property
    def overlap(self) -> Union[dict, bool]:
        """### 获取指标是否主图叠加（属性接口）
        控制指标是否显示在主图（K线图）上，支持单值或多线条配置

        Returns:
            Union[dict, bool]:
                - bool: 单线条指标的叠加开关
                - dict: 多线条指标的叠加开关（键为线条名，值为bool）
        """
        """### 是否为主图叠加

        可设置value:
        >>> IndSeries:bool
            IndFrame:bool,list[bool],tuple[bool],dict[str,bool]"""
        return self._plotinfo.overlap

    @overlap.setter
    def overlap(self, value) -> None:
        """### 设置指标是否主图叠加（属性接口）
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
        """### 获取完整的绘图配置（属性接口）
        返回PlotInfo对象，包含所有绘图相关配置，**不可直接赋值**

        Returns:
            PlotInfo: 绘图配置对象
        """
        """### 画图信息,不可赋值"""
        return self._plotinfo

    @property
    def signallines(self) -> list[str]:
        """### 获取信号线条名称列表（属性接口）
        从plotinfo中提取所有标记为信号的线条名称，用于策略识别交易信号

        Returns:
            list[str]: 信号线条名称列表
        """
        return self._plotinfo.signallines

    @property
    def issignal(self) -> bool:
        """### 判断指标是否包含交易信号（属性接口）
        基于signallines是否非空，用于策略筛选信号指标

        Returns:
            bool: True=包含信号，False=不包含信号
        """
        return bool(self._plotinfo.signallines)

    @property
    def candle_style(self) -> Optional[CandleStyle]:
        """### 获取蜡烛图样式（属性接口）
        仅对非指标对象（如KLine）有效，包含蜡烛图颜色、线型等配置

        Returns:
            Optional[CandleStyle]: 蜡烛图样式对象（非蜡烛图返回None）
        """
        return self._plotinfo.candlestyle

    @candle_style.setter
    def candle_style(self, value):
        """### 设置蜡烛图样式（属性接口）
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
        """### 判断跨周期指标是否在主周期显示（属性接口）
        用于多周期策略中，控制子周期指标是否在主周期图表中显示

        Returns:
            bool: True=主周期显示，False=子周期单独显示
        """
        """### 跨周期指标在主周期中显示"""
        return self._indsetting.ismain

    @ismain.setter
    def ismain(self, value) -> None:
        """### 设置跨周期指标是否在主周期显示（属性接口）
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
        """### 判断是否为回放数据（属性接口）
        用于历史数据回放功能，标识数据是否为回放模式

        Returns:
            bool: True=回放数据，False=实时/历史数据
        """
        """### 是否为播放数据"""
        return self._indsetting.isreplay

    @isreplay.setter
    def isreplay(self, value) -> None:
        """### 设置是否为回放数据（属性接口）
        仅接受布尔值，用于切换数据的回放状态

        Args:
            value (bool): 回放数据开关
        """
        self._indsetting.isreplay = bool(value)

    @property
    def isresample(self) -> bool:
        """### 判断是否为转换数据（属性接口）
        标识数据是否经过上采样/下采样（如1分钟→5分钟）

        Returns:
            bool: True=转换数据，False=原始数据
        """
        """### 是否为转换数据"""
        return self._indsetting.isresample

    @isresample.setter
    def isresample(self, value) -> None:
        """### 设置是否为转换数据（属性接口）
        仅接受布尔值，用于标记数据的转换状态

        Args:
            value (bool): 转换数据开关
        """
        self._indsetting.isresample = bool(value)

    @property
    def isMDim(self) -> bool:
        """### 判断是否为多维数据（属性接口）
        区分数据类型：True=IndFrame（多列），False=IndSeries/Line（单列）

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
        """### 获取水平线样式列表（属性接口）
        管理指标的水平线配置（如RSI的20/80分界线），支持批量添加

        Returns:
            SpanList: 水平线样式列表对象
        """
        """### 水平线"""
        return self._plotinfo.spanstyle

    @span_style.setter
    def span_style(self, value) -> None:
        """### 添加水平线样式（属性接口）
        批量添加水平线配置，支持单个样式或样式列表

        Args:
            value (SpanStyle | list[SpanStyle]): 水平线样式（单个或列表）
        """
        self._plotinfo.spanstyle += value

    @property
    def span_location(self) -> list[float]:
        """### 获取水平线位置列表（属性接口）
        返回所有水平线的Y轴位置（如[20.0, 80.0]）

        Returns:
            list[float]: 水平线位置列表
        """
        return self._plotinfo.span_location

    @span_location.setter
    def span_location(self, value):
        """### 设置水平线位置（属性接口）
        批量添加水平线位置，自动同步到span_style

        Args:
            value (float | list[float]): 水平线位置（单个或列表）
        """
        self._plotinfo.spanstyle += value

    @property
    def span_color(self) -> list[str, Colors]:
        """### 获取水平线颜色列表（属性接口）
        返回所有水平线的颜色配置（如["red", "green"]）

        Returns:
            list[str | Colors]: 水平线颜色列表
        """
        return self._plotinfo.span_color

    @span_color.setter
    def span_color(self, value):
        """### 设置水平线颜色（属性接口）
        批量更新所有水平线的颜色，支持字符串或Colors枚举

        Args:
            value (str | Colors | list[str | Colors]): 颜色配置（单个或列表）
        """
        self._plotinfo.span_color = value

    @property
    def span_dash(self) -> list[str, LineDash]:
        """### 获取水平线线型列表（属性接口）
        返回所有水平线的线型配置（如["solid", "dashed"]）

        Returns:
            list[str | LineDash]: 水平线线型列表
        """
        return self._plotinfo.span_dash

    @span_dash.setter
    def span_dash(self, value):
        """### 设置水平线线型（属性接口）
        批量更新所有水平线的线型，支持字符串或LineDash枚举

        Args:
            value (str | LineDash | list[str | LineDash]): 线型配置（单个或列表）
        """
        self._plotinfo.span_dash = value

    @property
    def span_width(self) -> list[float]:
        """### 获取水平线宽度列表（属性接口）
        返回所有水平线的宽度配置（如[1.0, 2.0]）

        Returns:
            list[float]: 水平线宽度列表
        """
        return self._plotinfo.span_width

    @span_width.setter
    def span_width(self, value):
        """### 设置水平线宽度（属性接口）
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
        """### 判断是否为指标对象（属性接口）
        区分指标（如MA、RSI）与原始数据（如KLine）

        Returns:
            bool: True=指标对象，False=原始数据
        """
        """### 是否为指标,反之为KLine数据"""
        return self._indsetting.isindicator

    @isindicator.setter
    def isindicator(self, value) -> None:
        """### 设置是否为指标对象（属性接口）
        仅接受布尔值，用于标记数据的类型

        Args:
            value (bool): 指标标识开关
        """
        self._indsetting.isindicator = bool(value)

    @property
    def iscustom(self) -> bool:
        """### 判断是否为自定义数据（属性接口）
        标识数据是否为用户自定义（非系统生成）

        Returns:
            bool: True=自定义数据，False=系统数据
        """
        """### 是否为自定义数据"""
        return self._indsetting.iscustom

    @iscustom.setter
    def iscustom(self, value) -> None:
        """### 设置是否为自定义数据（属性接口）
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
        """### 获取指标完整设置（属性接口）
        返回_indsetting对象，包含指标的所有元信息（ID、维度、类型等）

        Returns:
            IndSetting: 指标设置对象
        """
        """### 返回指标设置"""
        return self._indsetting

    @property
    def dataset(self) -> DataFrameSet:
        """### 获取指标内置数据集（属性接口）
        管理原始数据、转换数据、上采样数据等，支持多版本数据存储

        Returns:
            DataFrameSet: 数据集对象
        """
        """### 数据集"""
        return self._dataset

    @property
    def pandas_object(self) -> pd.DataFrame | pd.Series | corefunc:
        """### 获取底层Pandas对象（属性接口）
        返回指标对应的原生Pandas对象（DataFrame/Series），用于高级数据操作

        Returns:
            pd.DataFrame | pd.Series | corefunc: 原生Pandas对象
        """
        """### pandas数据"""
        try:
            return self._dataset.pandas_object
        except:
            return pd.DataFrame(self.values, columns=self.columns) if self.isMDim else pd.Series(self.values)

    @property
    def core_indicators(self) -> CoreFunc:
        """### 便捷访问当前实例的核心指标计算接口
        minibt框架的核心指标计算类，封装了基础金融/数据指标的计算逻辑。

        该类基于输入的原始数据（如时间序列数据），提供统一的核心指标计算接口，\n
        支持通过属性调用各类指标计算方法，返回结果为pandas对象（Series/DataFrame）\n
        或numpy数组（np.ndarray），便于后续数据分析或可视化。

        Returns:
            CoreFunc: 核心指标计算方法的封装对象（同indicators属性返回值）

        Examples:
            >>> ma = self.data.close.core_indicators.pta_sma(30)
            print(ma.tail(), type(ma))
            9995    4968.100000
            9996    4968.366667
            9997    4968.533333
            9998    4968.700000
            9999    4968.900000
            Name: SMA_30, dtype: float64 <class 'pandas.core.IndSeries.Series'>

        """
        return CoreIndicators(self.pandas_object).indicators

    @property
    def kline_object(self) -> Optional[Union[pd.DataFrame, corefunc]]:
        """### 获取转换前的原始K线数据（属性接口）
        无论数据是否经过转换（如HA K线、线性回归K线），始终返回最原始的K线数据

        Returns:
            Optional[Union[pd.DataFrame, corefunc]]: 原始K线数据（无则返回None）
        """
        """### KLine为其它类型蜡烛图时,kline_object返回转换前的pandas数据,即无论KLine数据怎么变换,kline_object为最原始的pandas数据"""
        return self._dataset.kline_object

    @property
    def source_object(self) -> Optional[Union[pd.DataFrame, pd.Series, corefunc]]:
        """### 获取最原始的数据源（属性接口）
        多周期场景中，返回最顶层的原始数据（非转换/上采样数据）

        Returns:
            Optional[Union[pd.DataFrame, pd.Series, corefunc]]: 原始数据源（无则返回None）
        """
        """### 原始pandas数据,多周期中最原始的pandas数据"""
        return self._dataset.source_object

    @property
    def conversion_object(self) -> Optional[Union[pd.DataFrame, pd.Series, corefunc]]:
        """### 获取转换前的数据（属性接口）
        返回数据转换（如HA、线性回归）前的原始数据，用于对比分析

        Returns:
            Optional[Union[pd.DataFrame, pd.Series, corefunc]]: 转换前数据（无则返回None）
        """
        """### 转换前的pandas数据"""
        return self._dataset.conversion_object

    @property
    def custom_object(self) -> Optional[Union[pd.DataFrame, pd.Series, corefunc]]:
        """### 获取自定义数据（属性接口）
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
        """### 获取数据行数（属性接口，简写）
        等同于_length，返回数据的时间步数量

        Returns:
            int: 数据行数（时间步数量）
        """
        """### 行"""
        return self._indsetting.v

    @property
    def length(self) -> int:
        """### 获取数据长度（属性接口，与V功能一致）
        返回数据的时间步数量，用于循环迭代与切片

        Returns:
            int: 数据长度（时间步数量）
        """
        """### 数据长度"""
        return self._indsetting.v

    @property
    def H(self) -> int:
        """### 获取数据列数（属性接口，简写）
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
        """### 获取PandasTA指标库接口（属性接口）
        集成PandasTA的所有指标（如sma、rsi、macd），支持链式调用

        Returns:
            PandasTa: PandasTA指标包装对象
        """
        return PandasTa(self)

    @property
    def talib(self) -> TaLib:
        """### 获取TA-Lib指标库接口（属性接口）
        集成TA-Lib的所有指标，支持高性能计算

        Returns:
            TaLib: TA-Lib指标包装对象
        """
        return TaLib(self)

    @property
    def tulip(self) -> TuLip:
        """### 获取Tulip指标库接口（属性接口）
        集成Tulip Indicators的所有指标，支持小众但实用的指标

        Returns:
            TuLip: Tulip指标包装对象
        """
        return TuLip(self)

    @property
    def btind(self) -> BtInd:
        """### 获取内置指标接口（属性接口）
        集成框架自定义的内置指标（如自定义MA、止损线）

        Returns:
            BtInd: 内置指标包装对象
        """
        return BtInd(self)

    @property
    def finta(self) -> FinTa:
        """### 获取FinTa指标库接口（属性接口）
        集成FinTa的所有指标，专注于金融技术分析

        Returns:
            FinTa: FinTa指标包装对象
        """
        return FinTa(self)

    @property
    def autotrader(self) -> AutoTrader:
        """### 获取AutoTrader指标接口（属性接口）
        集成AutoTrader相关的策略指标，支持自动化交易逻辑

        Returns:
            AutoTrader: AutoTrader指标包装对象
        """
        return AutoTrader(self)

    @property
    def tqfunc(self) -> TqFunc:
        """### 获取天勤函数接口（属性接口）
        https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tafunc.html

        集成TQSDK特有的指标与工具函数，适配期货实盘

        Returns:
            TqFunc: 天勤指标包装对象
        """
        return TqFunc(self)

    @property
    def tqta(self) -> TqTa:
        """### 获取天勤指标接口（属性接口）
        https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.ta.html

        集成TQSDK特有的指标与工具函数，适配期货实盘

        Returns:
            TqTa: 天勤指标包装对象
        """
        return TqTa(self)

    @property
    def sf(self) -> SignalFeatures:
        """### 获取信号特征接口（属性接口）
        生成交易信号相关的特征（如交叉信号、突破信号），用于策略输入

        Returns:
            SignalFeatures: 信号特征包装对象
        """
        return SignalFeatures(self)

    @property
    def pairtrading(self) -> Pair:
        """### 获取配对交易指标接口（属性接口）
        集成配对交易相关指标（如协整检验、价差计算）

        Returns:
            Pair: 配对交易指标包装对象
        """
        return Pair(self)

    @property
    def factors(self) -> Factors:
        """### 获取因子分析接口（属性接口）
        生成与管理因子数据（如动量因子、价值因子），用于多因子策略

        Returns:
            Factors: 因子分析包装对象
        """
        return Factors(self)

    @property
    def __tradingview(self) -> TradingView:
        if self.__class__._trading_view is None:
            from .tradingview import TradingView
            self.__class__._trading_view = TradingView
        return self._trading_view

    @property
    def tradingview(self) -> TradingView:
        """
        ### TradingView策略指标集合接口（属性接口）
        NOTE:此类指标针对蜡烛图类指标或KLine类数据

        该类封装了多种TradingView上的流行交易策略和指标，

        提供了统一的接口来调用这些策略进行技术分析。
        """
        return self.__tradingview(self)

    # ------------------------------
    # 策略与回测状态接口
    # ------------------------------

    @property
    def btindex(self) -> int:
        """### 获取当前回测索引（属性接口）
        同步策略的_btindex，标识当前处理到的K线位置

        Returns:
            int: 回测当前索引（从-1开始）
        """
        return self.strategy_instance._btindex

    @property
    def islivetrading(self) -> bool:
        """### 判断是否为实盘交易（属性接口）
        同步策略的_is_live_trading状态，用于区分回测与实盘逻辑

        Returns:
            bool: True=实盘交易，False=回测
        """
        return self._is_live_trading

    @property
    def new(self) -> float | int | bool | np.ndarray | Any:
        """### 获取最新数据（属性接口）
        等同于self.values[self.btindex]，快速访问当前K线的指标值

        Returns:
            float | int | bool | np.ndarray | Any: 最新数据（单值或数组）
        """
        return self.history()

    @new.setter
    def new(self, value: float | list[float]) -> None:
        """### 设置最新数据（属性接口）
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
        """### 获取前1周期数据（属性接口）
        等同于self.values[self.btindex-1]，快速访问「倒数第二根K线」的指标值（当前K线往前数第1个周期）

        Returns:
            float | int | bool | np.ndarray | Any: 前1周期数据（单值或数组）
        """
        return self.history(1)

    @property
    def sndprev(self) -> float | int | bool | np.ndarray | Any:
        """### 获取前2周期数据（属性接口）
        等同于self.values[self.btindex-2]，快速访问「倒数第三根K线」的指标值（当前K线往前数第2个周期）

        Returns:
            float | int | bool | np.ndarray | Any: 前2周期数据（单值或数组）
        """
        return self.history(2)

    @property
    def trdprev(self) -> float | int | bool | np.ndarray | Any:
        """### 获取前3周期数据（属性接口）
        等同于self.values[self.btindex-3]，快速访问「倒数第四根K线」的指标值（当前K线往前数第3个周期）

        Returns:
            float | int | bool | np.ndarray | Any: 前3周期数据（单值或数组）
        """
        return self.history(3)

    @property
    def frthprev(self) -> float | int | bool | np.ndarray | Any:
        """### 获取前4周期数据（属性接口）
        等同于self.values[self.btindex-4]，快速访问「倒数第五根K线」的指标值（当前K线往前数第4个周期）

        Returns:
            float | int | bool | np.ndarray | Any: 前4周期数据（单值或数组）
        """
        return self.history(4)

    def history(self, lookback: int = 0, size: int = 1) -> float | int | bool | np.ndarray | Any:
        """### 获取历史数据（方法接口）
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
        return self.__history(lookback, size, self.btindex)

    @cachedmethod(attrgetter('cache'))
    def __history(self, lookback=0, size=1, btindex=0):
        """### 缓存历史数据查询结果（内部方法，供history调用）
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

    @property
    def current_data_slice(self) -> Union[IndSeries, IndFrame, KLine, Line]:
        """### 策略循环中动态截取的最新数据片段

        在策略运行的循环过程中（如`next`方法执行时），根据当前循环索引`self.btindex`，\n
        截取从数据起始位置到当前索引+1的所有数据（即截至当前循环步骤的最新完整数据片段），\n
        用于实时计算、分析或判断当前市场状态。

        Returns:
            Union[pd.Series, pd.DataFrame, KLine, Line]: 截取后的最新数据，\n
                类型与原始数据保持一致（如时间序列、DataFrame表格或框架自定义数据类型）

        核心逻辑：
            - `self.btindex`：策略循环中的当前索引（随`next`方法逐次递增）
            - `loc[:self.btindex + 1]`：通过切片获取 [起始位置, 当前索引+1) 的数据范围，
              确保包含当前循环步骤的最新数据点

        使用场景：
            通常在`next`方法中调用，用于实时计算当前数据的统计量（如均值、极值）、
            验证指标状态或生成交易信号。
        """
        return self.loc[:self.btindex + 1]

    # ------------------------------
    # Pandas数据转换接口
    # ------------------------------
    def to_pandas(self, filed: Optional[Union[str, list[str]]] = None, length: Optional[int] = None, offset: int = 0) -> pd.Series | pd.DataFrame:
        """### 转换为Pandas对象（方法接口）
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
    def upsample(self, **kwargs) -> Union[Line, IndSeries, IndFrame]:
        """
        指标上采样（方法接口）
        将低周期数据转换为高周期（如1分钟→5分钟），支持缓存与参数重置

        Args:
            **kwargs: 上采样参数
                - reset (bool): 是否重置缓存（True=重新计算，False=使用缓存）. Defaults to False.
                - 其他参数：指标配置（如length=20）

        Returns:
            Union[Line, IndSeries, IndFrame]: 上采样后的指标数据

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
            >>> Line | IndSeries | IndFrame"""
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
            # 生成上采样数据对象（多维→IndFrame，一维→IndSeries）
            if data.shape[1] != 1:
                data = IndFrame(data, ** kwargs)
            else:
                data = IndSeries(data[:, 0], **kwargs)
            # 缓存上采样数据
            self._dataset.upsample_object = data
            data._upsample_name = "upsample"
            return data

        # 非转换数据：直接生成指标（用户参数覆盖默认）

        if kwargs:
            kwargs = self.get_indicator_kwargs(**kwargs)
            return type(self)(self.values, **kwargs)
        return self

    def __call__(self, **kwargs) -> Line | IndSeries | IndFrame:
        """
        调用运算符重载（方法接口，与upsample功能一致）
        支持通过函数调用方式进行上采样（如self.ma5()等同于self.ma5.upsample()）

        Args:
            **kwargs: 上采样参数（同upsample）

        Returns:
            Union[Line, IndSeries, IndFrame]: 上采样后的指标数据

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
            >>> Line | IndSeries | IndFrame
        """
        return self.upsample(**kwargs)

    # ------------------------------
    # 多指标并行计算接口
    # ------------------------------
    def multi_apply(self, *args: Union[list[Callable, dict, IndFrame], Multiply], **kwargs) -> tuple[IndSeries, IndFrame]:
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
            tuple[IndSeries, IndFrame]: 计算后的指标列表（按输入顺序）

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
            start, int) and start >= 0 else self.get_first_valid_index(*args)
        # 构建迭代器：索引 + 所有输入数组
        result = [range(length + offset, len(args[0])),]
        result.extend(list(args))
        return zip(*result)

    def get_lennan(self, *args: tuple[pd.Series, np.ndarray]) -> int:
        """获取参数数组中最大NAN的长度"""
        return get_lennan(*args)

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
    def _apply_operate_string(self, string: str) -> IndSeries | IndFrame:
        """
        通过字符串执行数据操作（内部方法，供运算符重载用）
        动态执行字符串中的代码，修改底层数据，返回新的指标对象

        Args:
            string (str): 执行的代码字符串（需定义'value'变量）

        Returns:
            IndSeries | IndFrame: 操作后的指标对象

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
            data: 目标数据对象（IndSeries/IndFrame）
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
    def _apply_operator(self, other: IndSeries | IndFrame | Any, op: str, reverse: bool = False, isbool: bool = False) -> IndSeries | IndFrame | np.ndarray | Any:
        """
        执行运算符操作（内部方法，供重载运算符调用）
        处理指标与指标/标量的运算，支持反向运算与布尔值转换

        Args:
            other (IndSeries | IndFrame | Any): 运算对象（指标或标量）
            op (str): 运算符（如'+', '>', '&'）
            reverse (bool, optional): 是否反向运算（如a - b 反向为 b - a）. Defaults to False.
            isbool (bool, optional): 是否为布尔运算（自动转换为bool类型）. Defaults to False.

        Returns:
            IndSeries | IndFrame | np.ndarray | Any: 运算结果（指标对象或原生类型）
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

    def __set_data(self, data: np.ndarray) -> IndSeries | IndFrame:
        """
        将numpy数组转换为框架内置指标对象（内部方法，供运算/数据处理调用）
        根据输入数组维度自动选择返回IndSeries（一维）或IndFrame（多维），
        并继承当前指标的配置参数（如ID、绘图信息），确保数据一致性。

        Args:
            data (np.ndarray): 待转换的numpy数组（需与原数据长度匹配）

        Returns:
            IndSeries | IndFrame: 转换后的框架内置指标对象
                - IndSeries：输入为一维数组（shape=(N,)）时返回
                - IndFrame：输入为多维数组（shape=(N, M)）时返回

        核心逻辑：
        1. 检测数组维度：通过shape判断是否为多维数据
        2. 继承配置参数：调用get_indicator_kwargs获取当前指标的配置（ID、绘图信息等）
        3. 生成指标对象：根据维度生成对应类型的内置指标，确保属性一致
        """
        if len(data.shape) > 1:
            # 多维数组（如N行M列）→ 转换为IndFrame对象
            return IndFrame(data, **self.get_indicator_kwargs(isindicator=True))
        else:
            # 一维数组（如N行1列）→ 转换为IndSeries对象
            return IndSeries(data, **self.get_indicator_kwargs(isindicator=True))

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
                    kwargs.update(dict(overlap=True))
                # 继承ID：复制当前指标的ID，确保关联关系一致
                id = self.id.copy()
                # 指标名称：默认使用Pandas方法名（如"mean"、"rolling"）
                ind_name = func.__name__

                # 多维结果（DataFrame）→ IndFrame对象
                if len(data.shape) > 1:
                    # 线条名称：优先从kwargs获取，否则使用DataFrame列名
                    lines = kwargs.get("lines", list(data.columns))
                    # 校验：线条数量需与列数一致
                    assert lines and len(lines) == data.shape[1], \
                        f"线条数量（{len(lines)}）与数据列数（{data.shape[1]}）不匹配"
                    return IndFrame(
                        data,
                        id=id,
                        sname=ind_name,  # 策略内名称=方法名
                        ind_name=ind_name,  # 指标类型名=方法名
                        lines=lines,
                        **kwargs
                    )
                # 一维结果（Series）→ IndSeries对象
                else:
                    # 线条名称：优先从kwargs获取，否则使用当前指标的sname
                    if "lines" not in kwargs:
                        lines = kwargs.get("lines", [self.sname,])
                    # 校验：线条数量需与一维数据匹配（仅1个）
                    assert lines and len(lines) == len(data.shape), \
                        f"线条数量（{len(lines)}）与一维数据不匹配"
                    return IndSeries(
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

    def _wrap_pandas_method_to_indicator(self, func: Callable) -> Callable:
        """
        包装Pandas原生方法，将返回结果自动转换为框架内置指标类型（IndFrame/IndSeries）
        解决Pandas方法与框架指标对象的兼容性问题，确保方法调用后仍可链式使用框架功能。

        Args:
            func: 待包装的Pandas原生方法（如pd.Series.mean、pd.DataFrame.rolling等）

        Returns:
            包装后的方法，返回框架内置指标对象（保留索引和配置信息）
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            arguments = get_func_args_dict(func, *args, **kwargs)
            func_name = func.__name__
            if "kwargs" in kwargs and kwargs["kwargs"]:
                extra_kwargs = kwargs.pop("kwargs")
                kwargs = {**kwargs, **extra_kwargs}
            pandas_object = self.pandas_object
            pandas_func = getattr(pandas_object, func_name)
            pandas_kw_params = set(signature(pandas_func).parameters.keys())
            method_kwargs = {}
            frame_var_kwargs = {}
            if func_name in SPECIAL_FUNC:
                for k, v in kwargs.items():
                    if k in IndSetting or k in PlotInfo:
                        frame_var_kwargs.update({k: v})
                    else:
                        method_kwargs.update({k: v})
            else:
                for k, v in kwargs.items():
                    if k in pandas_kw_params:
                        method_kwargs.update({k: v})
                    else:
                        frame_var_kwargs.update({k: v})

            # --------------------- 调用 Pandas 原生方法（核心修正：条件判断颠倒问题） ---------------------
            try:
                # 正确逻辑：有位置参数就传 *converted_var_positional，没有就只传 kwargs
                data = pandas_func(
                    *args, **method_kwargs)
            except Exception:
                # 异常时二次转换（逻辑与 try 块保持一致）
                # # 处理框架*args中的指标对象
                converted_var_positional = []
                for arg in args:
                    if type(arg) in BtIndType:
                        converted_var_positional.append(arg.pandas_object)
                    else:
                        converted_var_positional.append(arg)

                # 处理关键字参数中的指标对象
                for k, v in method_kwargs.items():
                    if type(v) in BtIndType:
                        method_kwargs[k] = v.pandas_object

                # 异常处理块也用正确的参数传递逻辑
                data = pandas_func(
                    *converted_var_positional, **method_kwargs)

            # --------------------- 6. 处理返回值 ---------------------
            if data is None and "inplace" in arguments:
                data = pandas_object
            as_internal = arguments.get('as_internal', True)
            if not as_internal:
                return data
            if not isinstance(data, (pd.Series, pd.DataFrame)):
                return data
            if not options.check_conversion(data, len(self)):
                return data
            isMDim = len(data.shape) > 1
            inplace = arguments.get('inplace', None)
            indicator_kwargs = self.get_indicator_kwargs(**frame_var_kwargs)
            indicator_kwargs["lines"] = list(
                data.columns) if isMDim else [func_name,]
            if inplace:
                if isMDim and self.shape[1] != data.shape[1]:
                    data = IndFrame(data.values, **indicator_kwargs)
                    self.__dict__.update(data.__dict__)
                    # 请问如果维度与原来的不一样时，inplace为真是如何将data替换为self自身？
                    # if self.strategy_instances:
                    #     if self.sname in self.strategy_instance._btindicatordataset or \
                    #             self.sname in self.strategy_instance._btklinedataset:
                    #         setattr(self.strategy_instance, self.sname,
                    #                 data)
                    #         return self
                    # return data
                else:
                    self[:] = data.values
                return self
                # return self.inplace_values(data)

            if isMDim:
                return IndFrame(data.values, **indicator_kwargs)
            else:
                return IndSeries(data.values, **indicator_kwargs)

        return wrapper

    # ------------------------------
    # 多条件批量数据更新
    # ------------------------------
    def ifs(self, *args, other: Union[pd.Series, np.ndarray, Any] = None, filed: Optional[str] = "") -> Optional[IndSeries]:
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
                cond (np.ndarray | pd.Series | IndSeries): 布尔条件（长度需与目标序列一致）
                value (Any): 满足cond时替换的值（支持标量、数组，需与序列元素类型兼容）
            other (Union[pd.Series, np.ndarray, Any], optional): 待处理的目标序列. Defaults to None.
                - 未指定时：自动从当前指标提取（多维取指定字段，一维取自身）
                - 标量/可迭代对象：自动转换为与当前指标长度一致的Series
            filed (Optional[str], optional): 多维指标的目标字段名. Defaults to "".
                - other未指定且为多维指标时，用于指定待处理的字段（如"close"、"ma5"）
                - 为空或字段不存在时，默认使用第一个线条（self.lines[0]）

        Returns:
            Optional[IndSeries]: 处理后的框架内置IndSeries对象；参数不合法时返回None

        关键逻辑：
        1. 参数校验：确保args为偶数个（成对的条件-值），避免逻辑错误
        2. 目标序列初始化：统一将other转换为Pandas Series，确保处理逻辑一致
        3. 条件迭代执行：按顺序应用每组条件，后执行的条件会覆盖先执行的结果（优先级更高）
        4. 结果转换：将处理后的Series转为框架内置IndSeries对象，保持指标属性一致性

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
        if args and len(args) >= 2:
            if other is None and len(args) % 2 != 0:
                *args, other = args
            if len(args) % 2 != 0:
                args = list(args)[:len(args)-1]
            else:
                args = list(args)
            # args = [pd.Series(arg) for arg in args]
            if other is not None:
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
                # for i in range(0, len(args), 2):
                #     other = other.mask(*args[i:i+2])
                # return other

            # 迭代执行多组条件-值对（后条件覆盖前条件）
            for i in range(0, len(args), 2):
                cond, value = args[i], args[i+1]
                # 核心逻辑：满足cond时用value替换，否则保持other原值
                # 注：原代码other.where(cond, value)逻辑反了，已修正为np.where
                other = np.where(cond, value, other)

            # 转换为框架内置IndSeries对象并返回
            return IndSeries(other)
        # 参数不合法（如args为奇数个）→ 返回None

    # ------------------------------
    # 便捷数据生成接口
    # ------------------------------
    @property
    def ones(self) -> IndSeries:
        """
        生成全1序列（属性接口）
        返回与当前指标长度一致的全1 IndSeries对象，用于权重计算、信号标记等场景。

        Returns:
            IndSeries: 全1序列（长度=self.V）

        示例：
        >>> # 等权重组合2个指标
            weight = self.ones * 0.5  # 权重=0.5
            combined_ind = self.ma5 * weight + self.ma10 * weight
        """
        return IndSeries(np.ones(self.V))  # .astype(np.float64)

    def full(self, value=np.nan) -> IndSeries:
        """
        生成填充指定值的序列（方法接口）
        返回与当前指标长度一致、所有元素为指定值的IndSeries对象，
        用于初始化、缺失值填充、固定阈值标记等场景。

        Args:
            value (Any, optional): 填充值（支持标量、np.nan）. Defaults to np.nan.

        Returns:
            IndSeries: 填充后的序列（长度=self.V）

        示例：
        >>> # 初始化空信号序列（默认值np.nan）
            self.signal = self.full()
            # 生成固定止损阈值序列（值=1000）
            self.stop_loss = self.full(1000)
        """
        return IndSeries(np.full(self.V, value))  # .astype(np.float64)

    @property
    def zeros(self) -> IndSeries:
        """
        生成全0序列（属性接口）
        返回与当前指标长度一致的全0 IndSeries对象，用于初始化、无信号标记等场景。

        Returns:
            IndSeries: 全0序列（长度=self.V）

        示例：
        >>> # 初始化收益序列（默认值0）
            self.daily_return = self.zeros
        """
        return IndSeries(np.zeros(self.V))  # .astype(np.float64)

    # ------------------------------
    # 哈希与比较方法（确保实例可哈希）
    # ------------------------------
    # def __eq__(self, other):
    #     """保留对象身份比较"""
    #     return self is other

    def __hash__(self):
        """基于对象身份生成哈希值"""
        return hash(id(self))

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

    # def __hash__(self):
    #     """
    #     重写哈希方法（内部方法）
    #     基于对象身份（内存地址）生成哈希值，确保指标实例可放入set/dict等哈希容器，
    #     支持多指标的去重、关联等操作（如多策略共享指标）。

    #     Returns:
    #         int: 对象的哈希值（与内存地址关联）
    #     """
    #     """### 确保实例可哈希"""
    #     return object().__hash__(self)

    # ------------------------------
    # 属性访问拦截（Pandas方法自动适配）
    # ------------------------------
    def __getattribute__(self, item) -> Line | IndSeries | IndFrame | pd.Series | pd.DataFrame:
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
            return self._wrap_pandas_method_to_indicator(super().__getattribute__(item))
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
        """### 滚动窗口计算（方法接口）
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
            self.ma5 = self.data.close.rolling(
                window=5).mean(overlap=True)  # 返回IndSeries对象

        >>> # 2. 计算20日滚动标准差（用于布林带）
            self.std20 = self.data.close.rolling(window=20).std()  # 返回IndSeries对象

        >>> # 3. 多列同时计算滚动均值（DataFrame）
            self.rolling_mean = self.data.loc[:, ["open", "high", "low", "close"]].rolling(
                window=10).mean()  # 返回IndFrame对象
        """
        """### 与pandas数据rolling方法使用一致,返回的是IndFrame或IndSeries数据"""
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

    def ewm(
        self,
        com: float | None = None,
        span: float | None = None,
        halflife: float | None = None,
        alpha: float | None = None,
        min_periods: int = 0,
        adjust: bool = False,
        ignore_na: bool = False,
        axis: Union[int, Literal["index", "columns", "rows"]] = 0,
    ) -> BtExponentialMovingWindow:
        """### 指数加权移动窗口计算（方法接口）
        与Pandas的ewm方法用法完全一致，但返回框架自定义的BtExponentialMovingWindow对象，
        支持后续调用mean、std、var等方法时直接返回内置指标对象，
        无需手动转换Pandas结果。

        核心场景：
        - 技术指标计算（如指数移动平均线EMA、MACD指标）
        - 风险指标计算（如指数加权波动率、风险价值VaR）
        - 特征工程（如指数平滑成交量、衰减权重计算）

        Args:
            com (float | None, optional): 指定衰减质心. Defaults to None.
                - 定义方式：α = 1/(1+com)，用于计算平滑因子
                - 例如：com=0.5表示最近数据点权重为0.5
            span (float | None, optional): 指定衰减跨度. Defaults to None.
                - 定义方式：α = 2/(span+1)，常用参数（如span=20对应EMA20）
                - 时间跨度，观测值权重降至约1/e的时间窗口
            halflife (float | None, optional): 指定衰减半衰期. Defaults to None.
                - 定义方式：α = 1 - exp(-ln(2)/halflife)
                - 权重降至50%所需的时间周期
            alpha (float | None, optional): 直接指定平滑因子. Defaults to None.
                - 直接设置平滑系数α（0 < α ≤ 1）
                - 值越大，近期数据权重越高
            min_periods (int, optional): 最小非缺失值数量. Defaults to 0.
                - 达到该数量前结果为NaN，默认0（从第一个数据开始计算）
            adjust (bool, optional): 是否使用调整公式. Defaults to False.
                - True：使用调整公式（除以权重和），False：使用递归公式
                - 调整公式更精确但计算稍慢
            ignore_na (bool, optional): 是否忽略缺失值. Defaults to False.
                - True：跳过NaN值计算，False：NaN值会传播到后续结果
            axis (int | str, optional): 计算轴方向. Defaults to 0.
                - 0/"index"：按行方向计算，1/"columns"：按列方向计算

        Returns:
            BtExponentialMovingWindow: 框架自定义的指数加权移动窗口对象，支持链式调用

        示例：
        >>> # 1. 计算12日指数移动平均线（EMA12）
            self.ema12 = self.data.close.ewm(span=12).mean()  # 返回IndSeries对象

        >>> # 2. 计算MACD指标（12日EMA与26日EMA差值）
            self.ema12 = self.data.close.ewm(span=12).mean()
            self.ema26 = self.data.close.ewm(span=26).mean()
            self.macd = self.ema12 - self.ema26  # 返回IndSeries对象

        >>> # 3. 计算指数加权滚动标准差（用于波动率）
            self.ewm_std = self.data.close.ewm(span=20).std()  # 返回IndSeries对象

        >>> # 4. 多列同时计算指数加权均值
            self.ewm_mean = self.data.loc[:, ["open", "close"]].ewm(
                span=10).mean()  # 返回IndFrame对象
        """
        return BtExponentialMovingWindow(
            self,
            com=com,
            span=span,
            halflife=halflife,
            alpha=alpha,
            min_periods=min_periods,
            adjust=adjust,
            ignore_na=ignore_na,
            axis=axis
        )

    def expanding(
        self,
        min_periods: int = 1,
        axis: Literal[0] = 0,
        method: Literal["single", "table"] = "single",
    ) -> BtExpanding:
        """### 扩展窗口计算（方法接口）

        与Pandas的expanding方法用法完全一致，但返回框架自定义的BtExpanding对象，
        支持后续调用mean、sum、std等方法时直接返回内置指标对象，
        无需手动转换Pandas结果。

        核心场景：
        - 累积统计计算（如累积最大值、累积最小值）
        - 动态基准计算（如扩展窗口均线、累积收益率）
        - 特征工程（如历史最高价、历史最低价、累积成交量）

        Args:
            min_periods (int, optional): 最小非缺失值数量. Defaults to 1.
                - 达到该数量前结果为NaN，默认1（从第一个数据开始计算）
            axis (Literal[0], optional): 计算轴方向. Defaults to 0.
                - 0：按行方向计算（扩展窗口沿时间轴）
            method (Literal["single", "table"], optional): 计算方法. Defaults to "single".
                - "single"：单列逐个计算，"table"：多列同时计算（性能优化）

        Returns:
            BtExpanding: 框架自定义的扩展窗口对象，支持链式调用后续计算方法

        示例：
        >>> # 1. 计算累积最大值（历史最高价）
            self.cummax = self.data.high.expanding().max()  # 返回IndSeries对象

        >>> # 2. 计算累积最小值（历史最低价）
            self.cummin = self.data.low.expanding().min()  # 返回IndSeries对象

        >>> # 3. 计算扩展窗口均值（从起始点到当前点的均值）
            self.expanding_mean = self.data.close.expanding().mean()  # 返回IndSeries对象

        >>> # 4. 多列同时计算扩展窗口统计量
            self.expanding_stats = self.data.loc[:, ["open", "close"]].expanding(
                min_periods=5).std()  # 返回IndFrame对象

        >>> # 5. 计算累积收益率（使用扩展窗口求和）
            self.cumulative_return = (1 + self.data.returns).expanding().prod() - 1
        """
        return BtExpanding(self, min_periods=min_periods, axis=axis, method=method)

    # ------------------------------
    # 滚动窗口自定义函数计算
    # ------------------------------
    @tobtind(lib="pta")
    def rolling_apply(self, func: Callable, window: Union[int, pd.Series, np.ndarray, list[int]], prepend_nans: bool = True, n_jobs: int = 1, **kwargs) -> IndSeries | IndFrame:
        """### 滚动窗口自定义函数计算（方法接口）
        在滚动窗口上应用自定义函数，支持并行计算，结果自动转为框架内置指标对象，
        解决Pandas rolling.apply不支持多输出、效率低的问题，适用于复杂指标计算。

        核心优势：
        - 可变窗口支持：窗口大小可为整数（固定窗口）或序列（每个位置自定义窗口大小）
        - 多输出支持：自定义函数可返回多个值（如同时计算均值、标准差），自动生成多线条指标
        - 并行加速：通过n_jobs控制并行线程数，处理大规模数据时提升效率
        - 类型兼容：自动适配一维（IndSeries）/多维（IndFrame）输入，返回对应类型的指标对象

        Args:
            func (Callable): 应用于每个滚动窗口的自定义函数
                - 输入：窗口内的数据（IndSeries→1D np.ndarray，IndFrame→2D np.ndarray或多参数1D数组）
                - 输出：单个值或多个值（如返回(mean, std)生成两个线条）
            window (Union[int, pd.Series, np.ndarray, list[int]]): 滚动窗口大小
                - 整数：固定窗口大小（所有位置使用相同窗口）
                - 序列类型（pd.Series/np.ndarray/list）：可变窗口大小
                需满足：长度与主数据一致，且所有元素为正整数
            prepend_nans (bool, optional): 滚动数组长度不足时是否在数组前填充NaN. Defaults to True.
                - True：前window-1个滚动数组长度不足的在其前面填充NaN（默认，符合技术指标习惯）
                - False：滚动数组无Nna值
            n_jobs (int, optional): 并行计算的线程数. Defaults to 1.
                - 1：单线程（默认，避免线程开销）
                - >1：多线程（需func线程安全，适合CPU密集型计算）
                - -1：使用所有可用CPU核心
            **kwargs: 扩展参数（如lines=[]指定线条名称、overlap=True设置主图叠加）

        Returns:
            IndSeries | IndFrame:
                - IndSeries：func返回单个值时（1D结果）
                - IndFrame：func返回多个值时（2D结果）

        示例详解：
        #### 1. 一维输入（IndSeries）→ 多输出（两个线条）
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
            #返回结果：IndFrame对象，含"close_min"和"close_max"两列

        #### 2. 多维输入（IndFrame多列）→ 多输出（两个线条）
        >>> #自定义函数：计算窗口内最高价均值和最低价标准差（多参数输入）
            def calc_high_mean_low_std(high: np.ndarray, low: np.ndarray, a: float = 1.) -> tuple[float, float]:
                \"\"\"
                high：窗口内最高价（1D np.ndarray）
                low：窗口内最低价（1D np.ndarray）
                a：自定义参数（示例用，无实际意义）
                返回：最高价均值、最低价标准差
                \"\"\"
                return high.mean(), low.std() * a
            #调用rolling_apply：3日窗口，指定输入列，生成两个线条
            self.high_low_stats = self.data.rolling_apply(
                func=calc_high_mean_low_std,
                window=3,
                lines=["high_mean", "low_std"],  # 线条名称
                # 分别设置叠加（high_mean主图，low_std副图）
                overlap=dict(high_mean=True, low_std=False),
                a=2.  # 传递自定义参数a=2.
            )
            #返回结果：IndFrame对象，含"high_mean"和"low_std"两列

        #### 3. 多维输入（IndFrame）→ 多输出（两个线条，单参数接收）
        >>> #自定义函数：接收2D数组（所有列），计算均值和标准差
            #传递参数为IndFrame以window滚动的数组
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
            #返回结果：IndFrame对象，含"ohlc_mean"和"ohlc_std"两列
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
        # print("get_plot_datas", key, self.get_indicator_kwargs())
        kwargs: Addict = self.get_indicator_kwargs()
        plot_id = kwargs.id["plot_id"]  # 绘图分组ID（多子图区分）
        isndim = kwargs.isMDim  # 是否为多维数据（IndFrame/IndSeries）
        # 数值数组适配：多维直接使用，一维转为(N,1)形状（统一前端处理）
        value = self.values if isndim else self.values.reshape((self.V, 1))
        if self._strategy_replay:
            value = value[:self.strategy_instance.min_start_length]
        overlap = kwargs.overlap  # 主图叠加配置（bool/dict）
        overlap_isbool = isinstance(overlap, bool)  # 是否为统一叠加开关
        # 线条名称提取：支持Lines对象或普通列表
        # vlines = self.lines.values if hasattr(
        #     self.lines, "values") else self.lines
        vlines = kwargs.lines
        # 2. 多分组处理（部分线条主图、部分副图）
        if not overlap_isbool and len(set(overlap.values())) > 1:
            # 提取主图/副图线条索引
            values = list(overlap.values())
            index1 = [ix for ix, vx in enumerate(values) if vx]  # 主图叠加线条索引
            index2 = [ix for ix, vx in enumerate(values) if not vx]  # 副图线条索引

            # 组装多分组数据（主图组+副图组）
            # 显示开关：按分组提取对应线条的isplot
            isplot = [
                [p for ix, p in enumerate(
                    kwargs.isplot.values()) if ix in index]
                for index in [index1, index2]
            ]
            # 指标名称：每个分组复用当前指标的sname
            name = [kwargs.sname] * 2
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
            categorys = [str(kwargs.category), ] * 2
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
            isplot = isndim and list(kwargs.isplot.values()) or [
                kwargs.isplot, ]
            # 指标名称：单分组直接使用当前指标的sname
            name = kwargs.sname
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
            categorys = str(kwargs.category)
            # 数值数据：直接使用适配后的value
            indicators = value

        # 4. 自定义指标标记：记录自定义指标所在的图表画图ID（供前端特殊处理）
        if kwargs.iscustom:
            self.strategy_instance._custom_ind_name.update(
                {key: self.plot_id})

        # 5. 绘图配置整合
        # 基础绘图配置：优先取plotinfo的vars，无则取plotinfo自身
        v_plotinfo = self._plotinfo.vars if hasattr(
            self.plotinfo, "vars") else self._plotinfo
        # 蜡烛图特殊处理：添加数据源标识（key）
        if kwargs.category == 'candles':
            v_plotinfo.update(dict(source=key))
        # 完整绘图配置
        _ind_plotinfo = v_plotinfo
        # 水平线配置：从plotinfo获取spanstyle
        span = v_plotinfo.get("spanstyle", {})
        # 信号样式配置：有交易信号时从plotinfo获取signalstyle
        _signal = v_plotinfo.get("signalstyle", {}) if hasattr(
            self, "_issignal") else {}
        _signal = _signal.vars if hasattr(_signal, "vars") else _signal

        # 返回结构化绘图数据
        return (
            plot_id, isplot, name, lines, _lines, ind_names, overlaps,
            categorys, indicators, doubles, _ind_plotinfo, span, _signal
        )

    # ------------------------------
    # 索引访问重载（支持[]操作符）
    # ------------------------------
    def __getitem__(self, key) -> Union[Line, IndSeries, IndFrame, Any]:
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
            Union[Line, IndSeries, IndFrame, Any]:
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
            # 处理元组索引（如(IndFrame[:, "close"]) → 提取字段名"close"）
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
        4. 多维指标处理：若为IndFrame，重新设置Line对象，确保线条与数据匹配
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
        - 框架内置指标数据（单个值/`IndSeries`/`IndFrame`，非原生 Pandas 对象）

        示例：
        >>> df.iloc[0]          # 选择第 1 行（返回 IndSeries 类型）
        >>> df.iloc[[0,2], [1]] # 选择第 1、3 行，第 2 列（返回 IndFrame 类型）
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
        - 框架内置指标数据（单个值/`IndSeries`/`IndFrame`，非原生 Pandas 对象）

        示例：
        >>> df.loc['viper']          # 选择行标签 'viper'（返回 IndSeries 类型）
        >>> df.loc[df['shield']>6]   # 选择 'shield' 列值大于 6 的行（返回 IndFrame 类型）
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

    def btplot(
            self,
            include: Literal["all", "last"] = "all",
            black_style: bool = False,
            open_browser: bool = False,
            plot_cwd: str = "",
            plot_name: str = "",
            save_plot: bool = False) -> None:
        """### Bokeh生成的交互式金融行情技术分析图表

        此函数自动检测数据格式（OHLCV、时间序列或指标）并使用内置技术分析工具
        和专业样式创建相应的交互式可视化图表。

        Args:
            include: 多指标显示模式
                    - "all": 显示计算链中的所有相关指标
                    - "last": 仅显示最终的指标结果
            black_style: 启用暗黑主题，在低光环境下提供更好的视觉舒适度
            open_browser: 强制在网页浏览器中打开（默认自动检测Jupyter环境）
            plot_cwd: 保存图表文件的自定义目录路径（默认使用strategy/plots）
            plot_name: 保存图表的自定义文件名（默认：'btplot.html'）
            save_plot: 自动将图表保存为HTML文件，便于分享或文档记录

        功能特性:
            - 智能OHLCV检测，提供K线图和成交量柱状图
            - 交互式缩放、平移和悬停提示，显示精确数据值
            - 自动指标叠加，采用专业配色方案
            - 十字准星工具，用于精确坐标跟踪
            - 图例控制，可显示/隐藏单个指标
            - 响应式设计，适应容器尺寸
            - 支持暗黑/明亮主题，满足不同视觉偏好
            - 多环境支持（Jupyter和独立浏览器）
            - 自动处理缺失值和数据缺口

        返回:
            None: 在Jupyter notebook或网页浏览器中显示交互式图表

        示例:
            >>> # 基础OHLCV图表（含成交量）
            >>> bd = KLine(df, height=400)
            >>> bd.btplot()

            >>> # 复杂指标链可视化
            >>> bd.tradingview.G_Channels().avg.ema().ebsw().btplot(include="all",black_style=True)

            >>> # 交易信号图表（暗黑主题）
            >>> bd.tradingview.UT_Bot_Alerts().btplot(black_style=True)

            >>> # 仅显示最终指标结果
            >>> bd.close.sma().ema().btplot("last")
        """
        self.BtPlot()(self, include, black_style, open_browser, plot_cwd, plot_name, save_plot)

    def concat(
        self,
        objs: Iterable[pd.Series | pd.DataFrame] | Mapping[Hashable, pd.Series | pd.DataFrame],
        *,
        axis: Axis = 0,
        join: str = "outer",
        ignore_index: bool = False,
        keys: Iterable[Hashable] | None = None,
        levels=None,
        names: list[Hashable] | None = None,
        verify_integrity: bool = False,
        sort: bool = False,
        copy: bool | None = None,
        **kwargs
    ) -> IndFrame | IndSeries:
        objs = [self, *objs]
        objs = [obj.pandas_object if hasattr(
            obj, "pandas_object") else obj for obj in objs]
        data = pd.concat(objs, axis, join, ignore_index, keys,
                         levels, names, verify_integrity, sort, copy)
        if not options.check_conversion(data, len(self)):
            return data
        isMDim = len(data.shape) > 1
        indicator_kwargs = self.get_indicator_kwargs(**kwargs)
        if isMDim:
            indicator_kwargs["lines"] = list(data.columns)
            return IndFrame(data.values, **indicator_kwargs)
        else:
            return IndSeries(data.values, **indicator_kwargs)


class PandasTa:
    """### pandas_ta指标指引
    pandas_ta 指标适配类，用于将 pandas_ta 库中的技术指标计算结果转换为框架内置的指标数据类型（IndSeries/IndFrame）

    核心功能：
    - 封装 pandas_ta 库的各类技术指标，提供统一的调用接口
    - 通过 @tobtind 装饰器自动处理指标参数校验、计算逻辑调用和返回值转换，确保输出为框架兼容的 IndSeries 或 IndFrame
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
    1. 初始化：传入框架支持的 IndSeries 或 IndFrame 数据对象（需包含指标计算所需的基础字段，如 open、high、low、close、volume 等）
       >>> data = IndFrame(...)  # 框架内置数据对象（含OHLCV等基础字段）
       >>> ta = PandasTa(data)

    2. 指标调用：直接调用对应指标方法，传入必要参数（默认参数已适配常见场景，可按需调整）
       >>> #示例1：识别十字星蜡烛图形态
       # 返回框架内置IndFrame，含十字星形态识别结果
       >>> doji_result = self.data.cdl_pattern(name="doji")
       >>> #示例2：计算Heikin-Ashi布林带K线
       >>> ha_candles = self.data.ha()  # 返回框架内置IndFrame，含HA蜡烛图的open、high、low、close字段
       >>> #示例3：计算14期RSI动量指标
       >>> rsi_14 = self.data.close.rsi(length=14)  # 返回框架内置IndSeries，含14期RSI值

    3. 返回值特性：所有方法返回框架内置的 IndSeries 或 IndFrame 类型，可直接用于后续策略逻辑（如信号生成、风险控制），无需额外类型转换


    注意事项：
    - 部分指标需特定基础字段（如成交量指标需 volume 字段），调用前确保输入数据包含所需字段
    - 指标参数（如 length 周期）可通过方法参数调整，未指定时使用 pandas_ta 默认值
    - 可通过 @tobtind 装饰器的 kwargs 参数配置填充缺失值（fillna）、数据偏移（offset）等辅助功能
    """
    _df: IndSeries | IndFrame

    def __init__(self, data):
        self._df = data

    @tobtind(lines=None, lib='pta')
    def cum(self, length=10, **kwargs) -> IndSeries:
        """
        滚动累积和 (Rolling Cumulative Sum)
        ---------
            计算指定长度的滚动窗口内的累积和。

        计算方法:
        ---------
            >>> pd.Series.rolling(length).sum()

        参数:
        ---------
        >>> length (int): 滚动窗口长度. 默认: 10
            **kwargs: 其他参数

        返回:
        ---------
        >>> IndSeries: 滚动累积和序列

        使用案例:
        ---------
        >>> # 计算价格的滚动累积和
        >>> cum_sum = self.data.cum(length=10)
        >>> 
        >>> # 计算成交量的滚动累积和
        >>> volume_cum = self.data.volume.cum(length=20)
        >>> 
        >>> def cumulative_analysis(self):
        >>>     # 使用10周期累积和分析价格强度
        >>>     price_cum = self.data.close.cum(length=10)
        >>>     if price_cum.new > price_cum.prev:
        >>>         return "10周期价格累积和上升，显示买盘强劲"
        >>> 
        >>> # 多周期累积和比较
        >>> def multi_period_cumulative(self):
        >>>     short_cum = self.data.close.cum(length=5)   # 短期累积和
        >>>     long_cum = self.data.close.cum(length=20)   # 长期累积和
        >>>     
        >>>     # 短期累积和超过长期累积和
        >>>     if short_cum.new > long_cum.new:
        >>>         return "短期买盘力量超过长期"
        >>> 
        >>> # 结合价格位置分析
        >>> def cumulative_with_price_level(self):
        >>>     cum_10 = self.data.close.cum(length=10)
        >>>     # 累积和在高位且价格创新高
        >>>     if (cum_10.new > cum_10.ema(period=20).new and 
        >>>         self.data.close.new > self.data.close.rolling(20).max()):
        >>>         return "累积和强劲且价格突破，趋势延续"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def ZeroDivision(self, b=1., dtype=np.float64, fill_value=0.0, handle_inf=True, **kwargs) -> IndSeries | IndFrame:
        """
        安全除法保护 (Safe Division Protection)
        ---------
            处理除法运算中的异常情况，包括除零和无穷大问题。
            当分母为零或无效时，使用指定的默认值替代，确保计算的稳定性。

        参数:
        ---------
        b (float | array-like): 除数，可以是标量或与当前序列相同形状的序列。默认: 1.0
        dtype (type): 输出数据的数值类型。默认: np.float64
        fill_value (float): 当除数为零或无效时返回的填充值。默认: 0.0
        handle_inf (bool): 是否处理无穷大情况。当为True时，分母为无穷大也会被视为无效。
                          默认: True
        **kwargs: 其他传递给底层计算函数的参数

        返回:
        ---------
        IndSeries | IndFrame: 经过安全除法保护处理后的序列或数据框

        使用案例:
        ---------
        >>> # 基础除法保护
        >>> result = self.data.close.ZeroDivision(b=0, fill_value=1.0)
        >>> 
        >>> # 价格变动率计算保护
        >>> price_change = self.data.close.diff()
        >>> protected_ratio = price_change.ZeroDivision(fill_value=0) / self.data.close.prev
        >>> 
        >>> # 保护技术指标计算，使用中性值填充
        >>> def protected_rsi(self):
        >>>     rsi = self.data.rsi(length=14)
        >>>     # 零除或无效值时返回中性值50
        >>>     protected_rsi = rsi.ZeroDivision(b=50, fill_value=50)
        >>>     return protected_rsi
        >>> 
        >>> # 成交量比率计算保护，避免零除和无穷大
        >>> def volume_ratio_protection(self):
        >>>     volume_ma = self.data.volume.ema(period=20)
        >>>     # 同时保护分子和分母，使用1作为默认值
        >>>     volume_ratio = self.data.volume.ZeroDivision(b=1, fill_value=1) / volume_ma.ZeroDivision(b=1, fill_value=1)
        >>>     return volume_ratio
        >>> 
        >>> # 高级保护：处理无穷大情况
        >>> def advanced_protection(self):
        >>>     # 在可能产生无穷大的计算中使用handle_inf=True
        >>>     sensitive_calc = self.data.roc(period=10)
        >>>     protected_calc = sensitive_calc.ZeroDivision(
        >>>         b=0, 
        >>>         fill_value=np.nan, 
        >>>         handle_inf=True
        >>>     )
        >>>     return protected_calc
        >>> 
        >>> # 多指标组合计算保护
        >>> def multi_indicator_protection(self):
        >>>     bb = self.data.bbands(length=20)
        >>>     kc = self.data.kc(length=20)
        >>>     
        >>>     # 保护布林带百分比计算
        >>>     bb_percent_protected = bb.bb_percent.ZeroDivision(b=0.5, fill_value=0.5)
        >>>     
        >>>     # 保护通道宽度比率计算
        >>>     bb_width = bb.bb_upper - bb.bb_lower
        >>>     kc_width = kc.kc_upper - kc.kc_lower
        >>>     width_ratio = bb_width.ZeroDivision(b=1, fill_value=1) / kc_width.ZeroDivision(b=1, fill_value=1)
        >>>     
        >>>     return width_ratio
        >>> 
        >>> # 条件性保护策略
        >>> def conditional_protection(self):
        >>>     rsi = self.data.rsi(length=14)
        >>>     
        >>>     # 根据不同技术状态使用不同的保护策略
        >>>     if rsi.new > 70:
        >>>         # 超买区域使用保守值
        >>>         protected_value = rsi.ZeroDivision(b=80, fill_value=80)
        >>>     elif rsi.new < 30:
        >>>         # 超卖区域使用积极值
        >>>         protected_value = rsi.ZeroDivision(b=20, fill_value=20)
        >>>     else:
        >>>         # 中性区域使用平衡值
        >>>         protected_value = rsi.ZeroDivision(b=50, fill_value=50)
        >>>     
        >>>     return protected_value
        >>> 
        >>> # 自定义数据类型保护
        >>> def custom_dtype_protection(self):
        >>>     # 使用单精度浮点数以节省内存
        >>>     protected_values = self.data.volume.ZeroDivision(
        >>>         b=0, 
        >>>         fill_value=0, 
        >>>         dtype=np.float32
        >>>     )
        >>>     return protected_values
        """
        ...

    @tobtind(lines=None, lib='pta')
    def strategy(self, *args, **kwargs):
        """不可用"""
        ...

    # Public DataFrame Methods: Indicators and Utilities
    # Candles
    @tobtind(lib='pta')
    def cdl_pattern(self, name="all", offset=0, **kwargs) -> IndFrame:
        """
        蜡烛图形态识别 (Candle Pattern)
        ---------
            所有蜡烛图形态的包装函数。

        注意:
        ---------
            不可用于replay

        参数:
        ---------
        >>> name: (Union[str, Sequence[str]]): 形态名称
            ['cdl_2crows', 'cdl_3blackcrows', 'cdl_3inside', 'cdl_3linestrike', 'cdl_3outside',
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
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含多个蜡烛图形态列的数据框

        所需数据字段:
        ---------
        >>> open, high, low, close

        使用案例:
        ---------
        >>> # 获取所有蜡烛图形态
        >>> patterns = self.data.cdl_pattern(name="all")
        >>> 
        >>> # 在策略中使用特定形态
        >>> def check_bullish_patterns(self):
        >>>     patterns = self.data.cdl_pattern(name=["hammer", "piercing", "morningstar"])
        >>>     # 检查最近的锤子线形态
        >>>     if patterns.cdl_hammer.new== 100:
        >>>         self.data.buy()
        >>> 
        >>> # 结合多个形态确认信号
        >>> def confirm_reversal(self):
        >>>     patterns = self.data.cdl_pattern(name=["doji", "engulfing", "hammer"])
        >>>     current = patterns.new
        >>>     prev = patterns.prev
        >>>     
        >>>     # 当出现多个看涨形态时确认反转
        >>>     bullish_signals = 0
        >>>     if current.cdl_doji.new == 100: bullish_signals += 1
        >>>     if current.cdl_engulfing.new == 100: bullish_signals += 1  
        >>>     if current.cdl_hammer.new == 100: bullish_signals += 1
        >>>     
        >>>     if bullish_signals >= 2:
        >>>         return "强烈看涨信号"
        """
        ...

    @tobtind(lines=['open', 'high', 'low', 'close'], lib='pta')
    def cdl_z(self, length=30, full=False, ddof=1, offset=None, **kwargs) -> IndFrame:
        """
        Z分数标准化蜡烛图 (Candle Type: Z)
        ---------
            使用滚动Z分数标准化OHLC蜡烛图。

        数据来源:
        ---------
            Kevin Johnson

        计算方法:
        ---------
            默认值:
            >>> length=30, full=False, ddof=1
                Z = ZSCORE

            >>> open  = Z( open, length, ddof)
                high  = Z( high, length, ddof)
                low   = Z(  low, length, ddof)
                close = Z(close, length, ddof)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            full (bool): 默认：False
            ddof (int): 乘数. 默认：1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> naive (bool, 可选): 如果为True，在长度小于其高低范围百分比时预填充潜在的Doji
                默认: False
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含open, high, low, close列的数据框

        所需数据字段:
        ---------
        >>> open, high, low, close

        使用案例:
        ---------
        >>> # 计算Z分数标准化蜡烛图
        >>> z_candles = self.data.cdl_z()
        >>> open_z, high_z, low_z, close_z = z_candles
        >>> 
        >>> # 使用Z分数检测异常价格行为
        >>> def detect_anomalies(self):
        >>>     z_candles = self.data.cdl_z(length=20)
        >>>     # 当Z分数超过2个标准差时发出信号
        >>>     if abs(z_candles.close_z.new) > 2:
        >>>         if z_candles.close_z.new > 0:
        >>>             self.data.sell()  # 价格异常偏高
        >>>         else:
        >>>             self.data.buy()   # 价格异常偏低
        """
        ...

    @tobtind(lines=['open', 'high', 'low', 'close'], overlap=False, category="candles", lib='pta')
    def ha(self, length=0, offset=0, **kwargs) -> IndFrame:
        """
        平均K线图 (Heikin Ashi Candles)
        ---------

        平均K线图技术通过平均价格数据来创建日本蜡烛图，过滤市场噪音。
        平均K线图由本间宗久在18世纪开发，与标准蜡烛图有一些共同特征，
        但在创建每根蜡烛时使用的值不同。与使用开盘价、最高价、最低价
        和收盘价的标准蜡烛图不同，平均K线图技术使用基于两周期平均值的
        修正公式。这使得图表外观更平滑，更容易发现趋势和反转，
        但也会掩盖缺口和一些价格数据。

        数据来源:
        ---------
            https://www.investopedia.com/terms/h/heikinashi.asp

        计算方法:
        ---------
        >>> HA_OPEN[0] = (open[0] + close[0]) / 2
            HA_CLOSE = (open[0] + high[0] + low[0] + close[0]) / 4
            for i > 1 in df.index:
                HA_OPEN = (HA_OPEN[i−1] + HA_CLOSE[i−1]) / 2
            HA_HIGH = MAX(HA_OPEN, HA_HIGH, HA_CLOSE)
            HA_LOW = MIN(HA_OPEN, HA_LOW, HA_CLOSE)

        使用一个周期创建第一个平均K线蜡烛，使用上述公式。
        例如，使用最高价、最低价、开盘价和收盘价创建第一个HA收盘价。
        使用开盘价和收盘价创建第一个HA开盘价。
        该周期的最高价将是第一个HA最高价，最低价将是第一个HA最低价。
        计算出第一个HA后，现在可以根据公式继续计算后续的HA蜡烛。

        参数:
        ---------
        >>> length (int): 周期. 默认: 0
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含open, high, low, close列的数据框

        所需数据字段:
        ---------
        >>> open, high, low, close

        使用案例:
        ---------
        >>> # 基础使用方法
        >>> self.ha = self.data.ha()
        >>> open, high, low, close = self.ha
        >>> # 在策略中作为趋势过滤条件
        >>> # 当HA收盘价连续上涨时考虑买入
        >>> if self.ha.close.new > self.ha.close.prev > self.ha.close.sndprev:
        >>>     self.data.buy()
        """
        ...

    @tobtind(lines=['open', 'high', 'low', 'close'], overlap=False, category="candles", lib='pta')
    def lrc(self, length=11, **kwargs) -> IndFrame:
        """
        线性回归蜡烛图 (Linear Regression Candles)
        ---------
            利用线性回归增强交易中的图表解读能力。
            在交易世界中，准确解读图表对于做出明智决策至关重要。在众多可用的工具和技术中，
            线性回归因其简单性和有效性而脱颖而出。

            线性回归是一种基本的统计方法，通过将直线拟合到数据点来帮助交易者识别证券价格的潜在趋势。
            这条线称为回归线，代表了未来价格走势的最佳估计，更清晰地展示了趋势的方向、强度和波动性。

            通过减少价格数据中的噪音，线性回归使趋势和反转更容易被发现，为技术分析和交易策略开发提供了坚实的基础。

        参数:
        ---------
        >>> length (int, 可选): 回归周期长度. 默认: 11

        返回:
        ---------
        >>> IndFrame: 包含线性回归计算后的OHLC数据

        所需数据字段:
        ---------
        >>> open, high, low, close

        使用案例:
        ---------
        >>> # 计算线性回归蜡烛图
        >>> lrc_data = self.data.lrc(length=14)
        >>> 
        >>> # 使用线性回归蜡烛图判断趋势方向
        >>> def trend_direction(self):
        >>>     lrc_data = self.data.lrc(length=14)
        >>>     # 当线性回归收盘价连续上涨时确认上升趋势
        >>>     if lrc_data.close.new > lrc_data.close.prev > lrc_data.close.sndprev:
        >>>         return "上升趋势"
        >>>     elif lrc_data.close.new < lrc_data.close.prev < lrc_data.close.sndprev:
        >>>         return "下降趋势"
        >>>     else:
        >>>         return "震荡趋势"
        >>> 
        >>> # 结合线性回归蜡烛图与其他指标
        >>> def enhanced_trend_strategy(self):
        >>>     lrc_data = self.data.lrc(length=14)
        >>>     # 当线性回归收盘价上穿其移动平均线时买入
        >>>     lrc_ma = lrc_data.close.ema(period=5)
        >>>     if lrc_data.close.new > lrc_ma.new and lrc_data.close.prev <= lrc_ma.prev:
        >>>         self.data.buy()
        """
        ...

    @tobtind(lines=None, lib='pta')
    def ebsw(self, length=40, bars=10, offset=0, **kwargs) -> IndSeries:
        """
        更优正弦波 (Even Better SineWave, EBSW) *测试版*
        ---------
            用于测量市场周期并使用低通滤波器去除噪音。
            输出信号限制在-1到1之间，检测到的趋势最大长度受周期参数限制。

        数据来源:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/even-better-sinewave/
            J.F.Ehlers 'Cycle Analytics for Traders', 2014

        计算方法:
        ---------
            refer to 'sources' or implementation

        参数:
        ---------
        >>> length (int): 最大周期/趋势周期。值在40-48之间效果最佳，最小值: 39. 默认: 40
            bars (int): 低通滤波周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算更优正弦波
        >>> ebsw_signal = self.data.ebsw(length=40, bars=10)
        >>> 
        >>> # 使用EBSW识别市场周期阶段
        >>> def detect_cycle_phase(self):
        >>>     ebsw = self.data.ebsw()
        >>>     current_value = ebsw.new
        >>>     
        >>>     if current_value > 0.5:
        >>>         return "强势上升周期"
        >>>     elif current_value < -0.5:
        >>>         return "强势下降周期" 
        >>>     elif current_value > 0:
        >>>         return "弱势上升周期"
        >>>     else:
        >>>         return "弱势下降周期"
        >>> 
        >>> # 结合EBSW与其他周期指标
        >>> def cycle_confirmation_strategy(self):
        >>>     ebsw = self.data.ebsw(length=44)
        >>>     # 当EBSW从负转正时考虑买入
        >>>     if ebsw.new > 0 and ebsw.prev <= 0:
        >>>         self.data.buy()
        """
        ...

    @tobtind(lines=None, lib='pta')
    def ao(self, fast=5, slow=34, offset=0, **kwargs) -> IndSeries:
        """
        动量震荡指标 (Awesome Oscillator, AO)
        ---------
            用于衡量证券的动量，通常用于确认趋势或预期可能的反转。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Awesome_Oscillator_(AO)
            https://www.ifcm.co.uk/ntx-indicators/awesome-oscillator

        计算方法:
        ---------
            median = (high + low) / 2
            AO = SMA(median, fast) - SMA(median, slow)

        参数:
        ---------
        >>> fast (int): 快周期. 默认: 5
            slow (int): 慢周期. 默认: 34
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low

        使用案例:
        ---------
        >>> # 计算动量震荡指标
        >>> ao_IndSeries = self.data.ao()
        >>> 
        >>> # 使用AO识别买卖信号
        >>> def ao_signals(self):
        >>>     ao = self.data.ao(fast=5, slow=34)
        >>>     # 碟形买入信号：连续三个柱状线在零轴下方，且中间柱状线最低
        >>>     if (ao.sndprev < 0 and ao.prev < ao.sndprev and ao.new > ao.prev):
        >>>         return "碟形买入信号"
        >>>     # 穿越零轴买入信号
        >>>     elif ao.new > 0 and ao.prev <= 0:
        >>>         return "零轴上方买入信号"
        >>> 
        >>> # AO与价格背离分析
        >>> def ao_divergence(self):
        >>>     ao = self.data.ao()
        >>>     # 价格创新低但AO未创新低 - 看涨背离
        >>>     if (self.data.low.new < self.data.low.prev and 
        >>>         ao.new > ao.prev):
        >>>         return "看涨背离"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def apo(self, fast=12, slow=26, mamode='sma', offset=0, **kwargs) -> IndSeries:
        """
        绝对价格震荡指标 (Absolute Price Oscillator, APO)
        ---------
            用于衡量证券的动量，是两个不同周期指数移动平均线的差值。
            注意：APO与MACD线是等价的。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/xtrader-help/x-study/technical-indicator-definitions/absolute-price-oscillator-apo/

        计算方法:
        ---------
            APO = SMA(close, fast) - SMA(close, slow)

        参数:
        ---------
        >>> fast (int): 快周期. 默认: 12
            slow (int): 慢周期. 默认: 26
            mamode (str): 移动平均模式，参考```help(ta.ma)```. 默认: 'sma'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算绝对价格震荡指标
        >>> apo_IndSeries = self.data.apo()
        >>> 
        >>> # 使用APO识别动量变化
        >>> def apo_momentum_strategy(self):
        >>>     apo = self.data.apo(fast=12, slow=26)
        >>>     # APO上穿零轴 - 买入信号
        >>>     if apo.new > 0 and apo.prev <= 0:
        >>>         self.data.buy()
        >>>     # APO下穿零轴 - 卖出信号  
        >>>     elif apo.new < 0 and apo.prev >= 0:
        >>>         self.data.sell()
        >>> 
        >>> # APO与价格背离分析
        >>> def apo_divergence_analysis(self):
        >>>     apo = self.data.apo()
        >>>     # 价格创新高但APO未创新高 - 看跌背离
        >>>     if (self.data.high.new > self.data.high.prev and 
        >>>         apo.new < apo.prev):
        >>>         return "看跌背离信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def bias(self, length=26, mamode="sma", offset=0, **kwargs) -> IndSeries:
        """
        乖离率指标 (Bias, BIAS)
        ---------
            衡量价格与移动平均线之间的偏离程度。

        数据来源:
        ---------
            基于网络资源定义，由Github用户homily在issue #46中请求添加

        计算方法:
        ---------
            BIAS = (close - MA(close, length)) / MA(close, length)
                  = (close / MA(close, length)) - 1

        参数:
        ---------
        >>> length (int): 周期. 默认: 26
            mamode (str): 移动平均模式，参考```help(ta.ma)```. 默认: 'sma'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算乖离率
        >>> bias_IndSeries = self.data.bias(length=20)
        >>> 
        >>> # 使用乖离率识别超买超卖
        >>> def bias_overbought_oversold(self):
        >>>     bias = self.data.bias(length=20)
        >>>     # 乖离率超过5% - 超买区域
        >>>     if bias.new > 0.05:
        >>>         return "超买信号"
        >>>     # 乖离率低于-5% - 超卖区域
        >>>     elif bias.new < -0.05:
        >>>         return "超卖信号"
        >>> 
        >>> # 乖离率回归策略
        >>> def bias_reversion_strategy(self):
        >>>     bias = self.data.bias(length=26)
        >>>     # 当乖离率从极端值回归时交易
        >>>     if bias.new < -0.08 and bias.prev <= -0.08:
        >>>         self.data.buy()  # 严重超卖后买入
        >>>     elif bias.new > 0.08 and bias.prev >= 0.08:
        >>>         self.data.sell()  # 严重超买后卖出
        """
        ...

    @tobtind(lines=None, lib='pta')
    def bop(self, scalar=1, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        多空均衡指标 (Balance of Power, BOP)
        ---------
            衡量买方与卖方的市场力量对比。

        数据来源:
        ---------
            http://www.worden.com/TeleChartHelp/Content/Indicators/Balance_of_Power.htm

        计算方法:
        ---------
            BOP = scalar * (close - open) / (high - low)

        参数:
        ---------
        >>> scalar (float): 放大倍数. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> open, high, low, close

        使用案例:
        ---------
        >>> # 计算多空均衡指标
        >>> bop_IndSeries = self.data.bop()
        >>> 
        >>> # 使用BOP识别买卖压力
        >>> def bop_pressure_analysis(self):
        >>>     bop = self.data.bop()
        >>>     # BOP大于0.5 - 强烈买入压力
        >>>     if bop.new > 0.5:
        >>>         return "强烈买入压力"
        >>>     # BOP小于-0.5 - 强烈卖出压力
        >>>     elif bop.new < -0.5:
        >>>         return "强烈卖出压力"
        >>> 
        >>> # BOP与价格行为结合
        >>> def bop_confirmation_strategy(self):
        >>>     bop = self.data.bop(scalar=1)
        >>>     # 阳线且BOP为正 - 确认上涨动力
        >>>     if (self.data.close.new > self.data.open.new and 
        >>>         bop.new > 0):
        >>>         self.data.buy()
        >>>     # 阴线且BOP为负 - 确认下跌动力
        >>>     elif (self.data.close.new < self.data.open.new and 
        >>>           bop.new < 0):
        >>>         self.data.sell()
        """
        ...

    @tobtind(lines=['ar', 'br'], lib='pta')
    def brar(self, length=26, scalar=100, drift=1, offset=0, **kwargs) -> IndFrame:
        """
        情绪指标 (BRAR)
        ---------
            BR和AR指标，用于衡量市场买卖情绪强度。
            AR指标反映市场当前交易日的买卖气势，BR指标反映市场前一日收盘价与当前交易日价格的关系。

        数据来源:
        ---------
            基于网络资源定义，由Github用户homily在issue #46中请求添加

        计算方法:
        ---------
            HO_Diff = high - open
            OL_Diff = open - low
            HCY = high - close[-1]
            CYL = close[-1] - low
            HCY[HCY < 0] = 0
            CYL[CYL < 0] = 0
            AR = scalar * SUM(HO, length) / SUM(OL, length)
            BR = scalar * SUM(HCY, length) / SUM(CYL, length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 26
            scalar (float): 放大倍数. 默认: 100
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含ar, br列的数据框

        所需数据字段:
        ---------
        >>> open, high, low, close

        使用案例:
        ---------
        >>> # 计算BRAR指标
        >>> brar_data = self.data.brar(length=26)
        >>> ar, br = brar_data.ar, brar_data.br
        >>> 
        >>> # 使用BRAR识别市场情绪
        >>> def market_sentiment_analysis(self):
        >>>     brar = self.data.brar()
        >>>     # AR > 150 且 BR > 150 - 市场过热
        >>>     if brar.ar.new > 150 and brar.br.new > 150:
        >>>         return "市场过热，注意风险"
        >>>     # AR < 50 且 BR < 50 - 市场过冷
        >>>     elif brar.ar.new < 50 and brar.br.new < 50:
        >>>         return "市场过冷，可能反弹"
        >>> 
        >>> # BRAR背离分析
        >>> def brar_divergence_strategy(self):
        >>>     brar = self.data.brar(length=26)
        >>>     # 价格创新高但BR未创新高 - 顶背离
        >>>     if (self.data.high.new > self.data.high.prev and 
        >>>         brar.br.new < brar.br.prev):
        >>>         return "BR顶背离，卖出信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cci(self, length=14, c=0.015, offset=0, **kwargs) -> IndSeries:
        """
        商品通道指数 (Commodity Channel Index, CCI)
        ---------
            动量震荡指标，主要用于识别相对于均值的超买超卖水平。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Commodity_Channel_Index_(CCI)

        计算方法:
        ---------
            tp = typical_price = hlc3 = (high + low + close) / 3
            mean_tp = SMA(tp, length)
            mad_tp = MAD(tp, length)
            CCI = (tp - mean_tp) / (c * mad_tp)

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            c (float): 缩放常数. 默认: 0.015
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算CCI指标
        >>> cci_IndSeries = self.data.cci(length=14)
        >>> 
        >>> # 使用CCI识别超买超卖
        >>> def cci_trading_signals(self):
        >>>     cci = self.data.cci(length=20)
        >>>     # CCI > 100 - 超买区域
        >>>     if cci.new > 100:
        >>>         self.data.sell()
        >>>     # CCI < -100 - 超卖区域
        >>>     elif cci.new < -100:
        >>>         self.data.buy()
        >>> 
        >>> # CCI趋势确认
        >>> def cci_trend_confirmation(self):
        >>>     cci = self.data.cci(length=14)
        >>>     # CCI从超卖区域上穿-100 - 买入信号
        >>>     if cci.new > -100 and cci.prev <= -100:
        >>>         return "CCI买入信号"
        >>>     # CCI从超买区域下穿100 - 卖出信号
        >>>     elif cci.new < 100 and cci.prev >= 100:
        >>>         return "CCI卖出信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cfo(self, length=9, scalar=100., drift=1, offset=0, **kwargs) -> IndSeries:
        """
        钱德预测震荡指标 (Chande Forecast Oscillator, CFO)
        ---------
            计算实际价格与时间序列预测（线性回归线的端点）之间的百分比差异。

        数据来源:
        ---------
            https://www.fmlabs.com/reference/default.htm?url=ForecastOscillator.htm

        计算方法:
        ---------
            CFO = scalar * (close - LINERREG(length, tdf=True)) / close

        参数:
        ---------
        >>> length (int): 周期. 默认: 9
            scalar (float): 放大倍数. 默认: 100
            drift (int): 短期周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算CFO指标
        >>> cfo_IndSeries = self.data.cfo(length=9)
        >>> 
        >>> # 使用CFO识别预测偏差
        >>> def cfo_prediction_analysis(self):
        >>>     cfo = self.data.cfo(length=14)
        >>>     # CFO > 5 - 价格高于预测值
        >>>     if cfo.new > 5:
        >>>         return "价格强势，高于预测"
        >>>     # CFO < -5 - 价格低于预测值
        >>>     elif cfo.new < -5:
        >>>         return "价格弱势，低于预测"
        >>> 
        >>> # CFO与价格行为结合
        >>> def cfo_reversion_strategy(self):
        >>>     cfo = self.data.cfo(length=9)
        >>>     # CFO从极端正值回归 - 卖出机会
        >>>     if cfo.new < 10 and cfo.prev >= 10:
        >>>         self.data.sell()
        >>>     # CFO从极端负值回归 - 买入机会
        >>>     elif cfo.new > -10 and cfo.prev <= -10:
        >>>         self.data.buy()
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cg(self, length=10, offset=0, **kwargs) -> IndSeries:
        """
        重心指标 (Center of Gravity, CG)
        ---------
            John Ehlers开发的重心指标，试图在显示零滞后和平滑的同时识别转折点。

        数据来源:
        ---------
            http://www.mesasoftware.com/papers/TheCGOscillator.pdf

        计算方法:
        ---------
            参考原始论文实现

        参数:
        ---------
        >>> length (int): 周期长度. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算重心指标
        >>> cg_IndSeries = self.data.cg(length=10)
        >>> 
        >>> # 使用CG识别转折点
        >>> def cg_turning_points(self):
        >>>     cg = self.data.cg(length=10)
        >>>     # CG指标上穿其移动平均线 - 买入信号
        >>>     cg_ma = cg.ema(period=5)
        >>>     if cg.new > cg_ma.new and cg.prev <= cg_ma.prev:
        >>>         return "CG买入信号"
        >>>     # CG指标下穿其移动平均线 - 卖出信号
        >>>     elif cg.new < cg_ma.new and cg.prev >= cg_ma.prev:
        >>>         return "CG卖出信号"
        >>> 
        >>> # CG指标与价格背离
        >>> def cg_divergence_analysis(self):
        >>>     cg = self.data.cg(length=10)
        >>>     # 价格创新低但CG指标未创新低 - 看涨背离
        >>>     if (self.data.close.new < self.data.close.prev and 
        >>>         cg.new > cg.prev):
        >>>         return "CG看涨背离"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cmo(self, length=14, scalar=100., talib=True, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        钱德动量震荡指标 (Chande Momentum Oscillator, CMO)
        ---------
            试图捕捉资产的动量，超买水平在50，超卖水平在-50。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/chande-momentum-oscillator-cmo/
            https://www.tradingview.com/script/hdrf0fXV-Variable-Index-Dynamic-Average-VIDYA/

        计算方法:
        ---------
            CMO = scalar * (PSUM - NSUM) / (PSUM + NSUM)

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            scalar (float): 放大倍数. 默认: 100
            drift (int): 短期周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> talib (bool): 如果为True且安装了TA-Lib，使用TA-Lib的实现。否则使用EMA版本。默认: True
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算CMO指标
        >>> cmo_IndSeries = self.data.cmo(length=14)
        >>> 
        >>> # 使用CMO识别超买超卖
        >>> def cmo_trading_signals(self):
        >>>     cmo = self.data.cmo(length=14)
        >>>     # CMO > 50 - 超买，卖出信号
        >>>     if cmo.new > 50:
        >>>         self.data.sell()
        >>>     # CMO < -50 - 超卖，买入信号
        >>>     elif cmo.new < -50:
        >>>         self.data.buy()
        >>> 
        >>> # CMO动量确认
        >>> def cmo_momentum_confirmation(self):
        >>>     cmo = self.data.cmo(length=14)
        >>>     # CMO从负值区域上穿0轴 - 动量转强
        >>>     if cmo.new > 0 and cmo.prev <= 0:
        >>>         return "动量转强信号"
        >>>     # CMO从正值区域下穿0轴 - 动量转弱
        >>>     elif cmo.new < 0 and cmo.prev >= 0:
        >>>         return "动量转弱信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def coppock(self, length=10, fast=11, slow=14, offset=0, **kwargs) -> IndSeries:
        """
        科波克曲线 (Coppock Curve)
        ---------
            动量指标，最初称为"趋势模型"，设计用于月度时间尺度。
            虽然设计用于月度使用，但可以在相同周期内进行日线计算。

        数据来源:
        ---------
            https://en.wikipedia.org/wiki/Coppock_curve

        计算方法:
        ---------
            SMA = Simple Moving Average
            MAD = Mean Absolute Deviation
            tp = typical_price = hlc3 = (high + low + close) / 3
            mean_tp = SMA(tp, length)
            mad_tp = MAD(tp, length)
            CCI = (tp - mean_tp) / (c * mad_tp)

        参数:
        ---------
        >>> length (int): WMA周期. 默认: 10
            fast (int): 快速ROC周期. 默认: 11
            slow (int): 慢速ROC周期. 默认: 14
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算科波克曲线
        >>> coppock_IndSeries = self.data.coppock()
        >>> 
        >>> # 使用科波克曲线识别长期买卖点
        >>> def coppock_trading_signals(self):
        >>>     cop = self.data.coppock(length=10, fast=11, slow=14)
        >>>     # 科波克曲线上穿零轴 - 长期买入信号
        >>>     if cop.new > 0 and cop.prev <= 0:
        >>>         return "科波克长期买入信号"
        >>>     # 科波克曲线下穿零轴 - 长期卖出信号
        >>>     elif cop.new < 0 and cop.prev >= 0:
        >>>         return "科波克长期卖出信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cti(self, length=12, offset=0, **kwargs) -> IndSeries:
        """
        相关趋势指标 (Correlation Trend Indicator, CTI)
        ---------
            John Ehler在2020年创建的震荡指标。
            根据价格在该范围内跟随正斜率或负斜率直线的接近程度分配值，值范围从-1到1。

        参数:
        ---------
        >>> length (int): 周期. 默认: 12
            offset (int): 结果偏移周期数. 默认: 0

        返回:
        ---------
        >>> IndSeries: CTI值序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算相关趋势指标
        >>> cti_IndSeries = self.data.cti(length=12)
        >>> 
        >>> # 使用CTI识别趋势强度
        >>> def cti_trend_strength(self):
        >>>     cti = self.data.cti(length=12)
        >>>     # CTI > 0.8 - 强烈上升趋势
        >>>     if cti.new > 0.8:
        >>>         return "强烈上升趋势"
        >>>     # CTI < -0.8 - 强烈下降趋势
        >>>     elif cti.new < -0.8:
        >>>         return "强烈下降趋势"
        >>>     # CTI接近0 - 震荡市场
        >>>     elif abs(cti.new) < 0.2:
        >>>         return "震荡市场"
        """
        ...

    @tobtind(lines=['dmp', 'dmn'], lib='pta')
    def dm(self, length=14, mamode="rma", talib=True, drift=1, offset=0, **kwargs) -> IndFrame:
        """
        方向运动指标 (Directional Movement, DM)
        ---------
            J. Welles Wilder在1978年开发，试图确定资产价格的移动方向。
            比较前期高点和低点以产生两个序列：+DM和-DM。

        数据来源:
        ---------
            https://www.tradingview.com/pine-script-reference/#fun_dmi
            https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=24&Name=Directional_Movement_Index

        计算方法:
        ---------
            up = high - high.shift(drift)
            dn = low.shift(drift) - low
            pos_ = ((up > dn) & (up > 0)) * up
            neg_ = ((dn > up) & (dn > 0)) * dn
            pos_ = pos_.apply(zero)
            neg_ = neg_.apply(zero)
            pos = ma(mamode, pos_, length=length)
            neg = ma(mamode, neg_, length=length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            mamode (str): 移动平均模式，参考```help(ta.ma)```. 默认: 'rma'
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        返回:
        ---------
        >>> IndFrame: 包含dmp(+DM)和dmn(-DM)列的数据框

        所需数据字段:
        ---------
        >>> high, low

        使用案例:
        ---------
        >>> # 计算方向运动指标
        >>> dm_data = self.data.dm(length=14)
        >>> dmp, dmn = dm_data.dmp, dm_data.dmn
        >>> 
        >>> # 使用DM识别趋势方向
        >>> def dm_trend_direction(self):
        >>>     dm = self.data.dm(length=14)
        >>>     # +DM > -DM - 上升趋势占主导
        >>>     if dm.dmp.new > dm.dmn.new:
        >>>         return "上升趋势"
        >>>     # -DM > +DM - 下降趋势占主导
        >>>     elif dm.dmn.new > dm.dmp.new:
        >>>         return "下降趋势"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def er(self, length=14, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        效率比率 (Efficiency Ratio, ER)
        ---------
            Perry J. Kaufman发明并在其著作"New Trading Systems and Methods"中提出。
            旨在衡量市场噪音或波动性。

        数据来源:
        ---------
            https://help.tc2000.com/m/69404/l/749623-kaufman-efficiency-ratio

        计算方法:
        ---------
            ABS = Absolute Value
            EMA = Exponential Moving Average
            abs_diff = ABS(close.diff(length))
            volatility = ABS(close.diff(1))
            ER = abs_diff / SUM(volatility, length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算效率比率
        >>> er_IndSeries = self.data.er(length=14)
        >>> 
        >>> # 使用ER识别趋势效率
        >>> def er_trend_efficiency(self):
        >>>     er = self.data.er(length=14)
        >>>     # ER > 0.5 - 高效趋势市场
        >>>     if er.new > 0.5:
        >>>         return "高效趋势，适合趋势跟踪"
        >>>     # ER < 0.2 - 低效震荡市场
        >>>     elif er.new < 0.2:
        >>>         return "低效震荡，适合均值回归"
        """
        ...

    @tobtind(lines=['bullp', 'bearp'], lib='pta')
    def eri(self, length=14, offset=0, **kwargs) -> IndFrame:
        """
        艾尔德射线指标 (Elder Ray Index, ERI)
        ---------
            包含牛市力量和熊市力量，用于观察价格并了解市场背后的强度。
            牛市力量衡量市场中买方将价格推高至平均共识价值之上的能力。
            熊市力量衡量卖方将价格拉低至平均共识价值之下的能力。

        数据来源:
        ---------
            https://admiralmarkets.com/education/articles/forex-indicators/bears-and-bulls-power-indicator

        计算方法:
        ---------
            EMA = Exponential Moving Average
            BULLPOWER = high - EMA(close, length)
            BEARPOWER = low - EMA(close, length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含bullp和bearp列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算艾尔德射线指标
        >>> eri_data = self.data.eri(length=14)
        >>> bullp, bearp = eri_data.bullp, eri_data.bearp
        >>> 
        >>> # 使用ERI识别买卖力量
        >>> def eri_power_analysis(self):
        >>>     eri = self.data.eri(length=13)
        >>>     # 牛市力量为正且熊市力量为负 - 强烈看涨
        >>>     if eri.bullp.new > 0 and eri.bearp.new < 0:
        >>>         return "强烈看涨信号"
        >>>     # 牛市力量为负且熊市力量为正 - 强烈看跌
        >>>     elif eri.bullp.new < 0 and eri.bearp.new > 0:
        >>>         return "强烈看跌信号"
        """
        ...

    @tobtind(lines=['fisher', 'fishers'], lib='pta')
    def fisher(self, length=9, signal=1, offset=0, **kwargs) -> IndFrame:
        """
        费希尔变换 (Fisher Transform, FISHT)
        ---------
            通过在一定周期内标准化价格来识别重要的价格反转。
            当两条线交叉时，建议反转信号。

        数据来源:
        ---------
            TradingView (相关性 >99%)

        计算方法:
        ---------
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
                FISHER.append(0.5 * (nplog((1 + v) / (1 - v)) + FISHER[i - 1]))
            SIGNAL = FISHER.shift(signal)

        参数:
        ---------
        >>> length (int): 费希尔周期. 默认: 9
            signal (int): 费希尔信号周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含fisher和fishers列的数据框

        所需数据字段:
        ---------
        >>> high, low

        使用案例:
        ---------
        >>> # 计算费希尔变换
        >>> fisher_data = self.data.fisher(length=9)
        >>> fisher, fishers = fisher_data.fisher, fisher_data.fishers
        >>> 
        >>> # 使用费希尔变换识别反转点
        >>> def fisher_reversal_signals(self):
        >>>     fish = self.data.fisher(length=9)
        >>>     # 费希尔线上穿信号线 - 买入信号
        >>>     if fish.fisher.new > fish.fishers.new and fish.fisher.prev <= fish.fishers.prev:
        >>>         return "费希尔买入信号"
        >>>     # 费希尔线下穿信号线 - 卖出信号
        >>>     elif fish.fisher.new < fish.fishers.new and fish.fisher.prev >= fish.fishers.prev:
        >>>         return "费希尔卖出信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def inertia(self, length=20, rvi_length=14, scalar=100., refined=False, thirds=False, mamode="ema", drift=1, offset=0, **kwargs) -> IndSeries:
        """
        惯性指标 (Inertia, INERTIA)
        ---------
            Donald Dorsey开发并在1995年9月的文章中介绍。
            是通过最小二乘移动平均平滑的相对活力指数。
            当值大于50时为正惯性，否则为负惯性。

        数据来源:
        ---------
            https://www.investopedia.com/terms/r/relative_vigor_index.asp

        计算方法:
        ---------
            LSQRMA = Least Squares Moving Average
            INERTIA = LSQRMA(RVI(length), ma_length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 20
            rvi_length (int): RVI周期. 默认: 14
            refined (bool): 使用'精炼'计算. 默认: False
            thirds (bool): 使用'三分之一'计算. 默认: False
            mamode (str): 移动平均模式，参考```help(ta.ma)```. 默认: 'ema'
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close, high, low

        使用案例:
        ---------
        >>> # 计算惯性指标
        >>> inertia_IndSeries = self.data.inertia(length=20)
        >>> 
        >>> # 使用惯性指标判断趋势持续性
        >>> def inertia_trend_persistence(self):
        >>>     inertia = self.data.inertia(length=20)
        >>>     # 惯性 > 50 - 正惯性，上升趋势持续
        >>>     if inertia.new > 50:
        >>>         return "正惯性，上升趋势"
        >>>     # 惯性 < 50 - 负惯性，下降趋势持续
        >>>     elif inertia.new < 50:
        >>>         return "负惯性，下降趋势"
        """
        ...

    @tobtind(lines=['k', 'd', 'j'], lib='pta')
    def kdj(self, length=9, signal=3, offset=0, **kwargs) -> IndFrame:
        """
        KDJ指标 (KDJ)
        ---------
            KDJ指标实际上是慢速随机指标的一种衍生形式，
            主要区别在于多了一条称为J线的线。
            J线代表%D值与%K值的背离。

        数据来源:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/kdj/
            https://docs.anychart.com/Stock_Charts/Technical_Indicators/Mathematical_Description#kdj

        计算方法:
        ---------
            LL = low for last 9 periods
            HH = high for last 9 periods
            FAST_K = 100 * (close - LL) / (HH - LL)
            K = RMA(FAST_K, signal)
            D = RMA(K, signal)
            J = 3K - 2D

        参数:
        ---------
        >>> length (int): 周期. 默认: 9
            signal (int): 信号周期. 默认: 3
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含k、d和j列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算KDJ指标
        >>> kdj_data = self.data.kdj(length=9)
        >>> k, d, j = kdj_data.k, kdj_data.d, kdj_data.j
        >>> 
        >>> # 使用KDJ识别超买超卖
        >>> def kdj_trading_signals(self):
        >>>     kdj = self.data.kdj(length=9)
        >>>     # K < 20 且 D < 20 - 超卖区域
        >>>     if kdj.k.new < 20 and kdj.d.new < 20:
        >>>         return "KDJ超卖，买入机会"
        >>>     # K > 80 且 D > 80 - 超买区域
        >>>     elif kdj.k.new > 80 and kdj.d.new > 80:
        >>>         return "KDJ超买，卖出机会"
        >>> 
        >>> # KDJ金叉死叉信号
        >>> def kdj_cross_signals(self):
        >>>     kdj = self.data.kdj(length=9)
        >>>     # K线上穿D线 - 金叉买入
        >>>     if kdj.k.new > kdj.d.new and kdj.k.prev <= kdj.d.prev:
        >>>         return "KDJ金叉买入信号"
        >>>     # K线下穿D线 - 死叉卖出
        >>>     elif kdj.k.new < kdj.d.new and kdj.k.prev >= kdj.d.prev:
        >>>         return "KDJ死叉卖出信号"
        """
        ...

    @tobtind(lines=['kst', 'ksts'], lib='pta')
    def kst(self, roc1=10, roc2=15, roc3=20, roc4=30, sma1=10, sma2=10, sma3=10, sma4=15, signal=9, drift=1, offset=0, **kwargs) -> IndFrame:
        """
        确然指标 (Know Sure Thing, KST)
        ---------
            基于动量的震荡指标，基于ROC计算。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Know_Sure_Thing_(KST)
            https://www.incrediblecharts.com/indicators/kst.php

        计算方法:
        ---------
            ROC = Rate of Change
            SMA = Simple Moving Average
            rocsma1 = SMA(ROC(close, roc1), sma1)
            rocsma2 = SMA(ROC(close, roc2), sma2)
            rocsma3 = SMA(ROC(close, roc3), sma3)
            rocsma4 = SMA(ROC(close, roc4), sma4)
            KST = 100 * (rocsma1 + 2 * rocsma2 + 3 * rocsma3 + 4 * rocsma4)
            KST_Signal = SMA(KST, signal)

        参数:
        ---------
        >>> roc1 (int): ROC1周期. 默认: 10
            roc2 (int): ROC2周期. 默认: 15
            roc3 (int): ROC3周期. 默认: 20
            roc4 (int): ROC4周期. 默认: 30
            sma1 (int): SMA1周期. 默认: 10
            sma2 (int): SMA2周期. 默认: 10
            sma3 (int): SMA3周期. 默认: 10
            sma4 (int): SMA4周期. 默认: 15
            signal (int): 信号周期. 默认: 9
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含kst和ksts列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算确然指标
        >>> kst_data = self.data.kst()
        >>> kst, ksts = kst_data.kst, kst_data.ksts
        >>> 
        >>> # 使用KST识别长期趋势
        >>> def kst_trend_signals(self):
        >>>     kst = self.data.kst()
        >>>     # KST上穿信号线 - 长期买入信号
        >>>     if kst.kst.new > kst.ksts.new and kst.kst.prev <= kst.ksts.prev:
        >>>         return "KST长期买入信号"
        >>>     # KST下穿信号线 - 长期卖出信号
        >>>     elif kst.kst.new < kst.ksts.new and kst.kst.prev >= kst.ksts.prev:
        >>>         return "KST长期卖出信号"
        """
        ...

    @tobtind(lines=['macdx', 'macdh', 'macds'], lib='pta', linestyle=dict(macdh=LineStyle(line_dash=LineDash.vbar)))
    def macd(self, fast=12, slow=26, signal=9, talib=True, offset=0, **kwargs) -> IndFrame:
        """
        指数平滑移动平均线 (Moving Average Convergence Divergence, MACD)
        ---------
            用于识别证券趋势的流行指标。
            虽然APO和MACD是相同的计算，但MACD还返回另外两个序列：信号线和柱状图。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/MACD_(Moving_Average_Convergence/Divergence)
            AS模式: https://tr.tradingview.com/script/YFlKXHnP/

        计算方法:
        ---------
            EMA = Exponential Moving Average
            MACD = EMA(close, fast) - EMA(close, slow)
            Signal = EMA(MACD, signal)
            Histogram = MACD - Signal
            if asmode:
                MACD = MACD - Signal
                Signal = EMA(MACD, signal)
                Histogram = MACD - Signal

        参数:
        ---------
        >>> fast (int): 快周期. 默认: 12
            slow (int): 慢周期. 默认: 26
            signal (int): 信号周期. 默认: 9
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> asmode (bool, 可选): 为True时启用MACD的AS版本. 默认: False
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含macdx、macdh、macds列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算MACD指标
        >>> macd_data = self.data.macd(fast=12, slow=26, signal=9)
        >>> macd_line, signal_line, histogram = macd_data.macdx, macd_data.macds, macd_data.macdh
        >>> 
        >>> # 使用MACD金叉死叉信号
        >>> def macd_cross_signals(self):
        >>>     macd = self.data.macd()
        >>>     # MACD线上穿信号线 - 金叉买入
        >>>     if macd.macdx.new > macd.macds.new and macd.macdx.prev <= macd.macds.prev:
        >>>         self.data.buy()
        >>>     # MACD线下穿信号线 - 死叉卖出
        >>>     elif macd.macdx.new < macd.macds.new and macd.macdx.prev >= macd.macds.prev:
        >>>         self.data.sell()
        >>> 
        >>> # MACD柱状图分析
        >>> def macd_histogram_analysis(self):
        >>>     macd = self.data.macd()
        >>>     # 柱状图由负转正 - 动能转强
        >>>     if macd.macdh.new > 0 and macd.macdh.prev <= 0:
        >>>         return "MACD动能转强"
        >>>     # 柱状图由正转负 - 动能转弱
        >>>     elif macd.macdh.new < 0 and macd.macdh.prev >= 0:
        >>>         return "MACD动能转弱"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def mom(self, length=10, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        动量指标 (Momentum, MOM)
        ---------
            用于衡量证券运动速度（或强度）的指标，或简单地说是价格的变化。

        数据来源:
        ---------
            http://www.onlinetradingconcepts.com/TechnicalAnalysis/Momentum.html

        计算方法:
        ---------
            MOM = close.diff(length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算动量指标
        >>> mom_IndSeries = self.data.mom(length=10)
        >>> 
        >>> # 使用动量指标识别价格加速度
        >>> def momentum_acceleration(self):
        >>>     mom = self.data.mom(length=10)
        >>>     # 动量转正 - 上涨加速度
        >>>     if mom.new > 0 and mom.prev <= 0:
        >>>         return "上涨动量启动"
        >>>     # 动量转负 - 下跌加速度
        >>>     elif mom.new < 0 and mom.prev >= 0:
        >>>         return "下跌动量启动"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pgo(self, length=14, offset=0, **kwargs) -> IndSeries:
        """
        相当好震荡指标 (Pretty Good Oscillator, PGO)
        ---------
            Mark Johnson创建的指标，用于衡量当前收盘价与其N日简单移动平均线的距离，
            以类似期间的平均真实波幅表示。
            Johnson的方法是用它作为长期交易的突破系统。
            大于3.0做多，小于-3.0做空。

        数据来源:
        ---------
            https://library.tradingtechnologies.com/trade/chrt-ti-pretty-good-oscillator.html

        计算方法:
        ---------
            ATR = Average True Range
            SMA = Simple Moving Average
            EMA = Exponential Moving Average
            PGO = (close - SMA(close, length)) / EMA(ATR(high, low, close, length), length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算相当好震荡指标
        >>> pgo_IndSeries = self.data.pgo(length=14)
        >>> 
        >>> # 使用PGO识别突破信号
        >>> def pgo_breakout_signals(self):
        >>>     pgo = self.data.pgo(length=14)
        >>>     # PGO > 3.0 - 强烈买入信号
        >>>     if pgo.new > 3.0:
        >>>         self.data.buy()
        >>>     # PGO < -3.0 - 强烈卖出信号
        >>>     elif pgo.new < -3.0:
        >>>         self.data.sell()
        """
        ...

    @tobtind(lines=['ppo', 'ppoh', 'ppos'], lib='pta')
    def ppo(self, fast=12, slow=26, signal=9, scalar=100., mamode="sma", talib=True, **kwargs) -> IndFrame:
        """
        百分比价格震荡指标 (Percentage Price Oscillator, PPO)
        ---------
            在衡量动量方面与MACD类似。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/MACD_(Moving_Average_Convergence/Divergence)

        计算方法:
        ---------
            SMA = Simple Moving Average
            EMA = Exponential Moving Average
            fast_sma = SMA(close, fast)
            slow_sma = SMA(close, slow)
            PPO = 100 * (fast_sma - slow_sma) / slow_sma
            Signal = EMA(PPO, signal)
            Histogram = PPO - Signal

        参数:
        ---------
        >>> fast (int): 快周期. 默认: 12
            slow (int): 慢周期. 默认: 26
            signal (int): 信号周期. 默认: 9
            scalar (float): 放大倍数. 默认: 100
            mamode (str): 移动平均模式，参考```help(ta.ma)```. 默认: 'sma'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含ppo、ppoh、ppos列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算百分比价格震荡指标
        >>> ppo_data = self.data.ppo(fast=12, slow=26, signal=9)
        >>> ppo, signal, histogram = ppo_data.ppo, ppo_data.ppos, ppo_data.ppoh
        >>> 
        >>> # 使用PPO识别动量变化
        >>> def ppo_momentum_strategy(self):
        >>>     ppo = self.data.ppo()
        >>>     # PPO上穿零轴 - 买入信号
        >>>     if ppo.ppo.new > 0 and ppo.ppo.prev <= 0:
        >>>         self.data.buy()
        >>>     # PPO下穿零轴 - 卖出信号
        >>>     elif ppo.ppo.new < 0 and ppo.ppo.prev >= 0:
        >>>         self.data.sell()
        """
        ...

    @tobtind(lines=None, lib='pta')
    def psl(self, length=12, scalar=100., drift=1, offset=0, **kwargs) -> IndSeries:
        """
        心理线 (Psychological Line, PSL)
        ---------
            震荡型指标，比较上涨周期数与总周期数的比例。
            换句话说，它是在给定期间内收盘价高于前一根K线的K线百分比。

        数据来源:
        ---------
            https://www.quantshare.com/item-851-psychological-line

        计算方法:
        ---------
            IF NOT open:
                DIFF = SIGN(close - close[drift])
            ELSE:
                DIFF = SIGN(close - open)
            DIFF.fillna(0)
            DIFF[DIFF <= 0] = 0
            PSL = scalar * SUM(DIFF, length) / length

        参数:
        ---------
        >>> length (int): 周期. 默认: 12
            scalar (float): 放大倍数. 默认: 100
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算心理线
        >>> psl_IndSeries = self.data.psl(length=12)
        >>> 
        >>> # 使用PSL识别市场情绪
        >>> def psl_market_sentiment(self):
        >>>     psl = self.data.psl(length=12)
        >>>     # PSL > 75 - 市场过度乐观
        >>>     if psl.new > 75:
        >>>         return "市场过度乐观，注意风险"
        >>>     # PSL < 25 - 市场过度悲观
        >>>     elif psl.new < 25:
        >>>         return "市场过度悲观，可能反弹"
        """
        ...

    @tobtind(lines=['pvo', 'pvoh', 'pvos'], overlap=False, lib='pta')
    def pvo(self, fast=12, slow=26, signal=9, scalar=100., offset=0, **kwargs) -> IndFrame:
        """
        百分比成交量震荡指标 (Percentage Volume Oscillator, PVO)
        ---------
            成交量的动量震荡指标。

        数据来源:
        ---------
            https://www.fmlabs.com/reference/default.htm?url=PVO.htm

        计算方法:
        ---------
            EMA = Exponential Moving Average
            PVO = (EMA(volume, fast) - EMA(volume, slow)) / EMA(volume, slow)
            Signal = EMA(PVO, signal)
            Histogram = PVO - Signal

        参数:
        ---------
        >>> fast (int): 快周期. 默认: 12
            slow (int): 慢周期. 默认: 26
            signal (int): 信号周期. 默认: 9
            scalar (float): 放大倍数. 默认: 100
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含pvo、pvoh、pvos列的数据框

        所需数据字段:
        ---------
        >>> volume

        使用案例:
        ---------
        >>> # 计算百分比成交量震荡指标
        >>> pvo_data = self.data.pvo(fast=12, slow=26, signal=9)
        >>> pvo, signal, histogram = pvo_data.pvo, pvo_data.pvos, pvo_data.pvoh
        >>> 
        >>> # 使用PVO确认价格趋势
        >>> def pvo_volume_confirmation(self):
        >>>     pvo = self.data.pvo()
        >>>     # 价格上涨且PVO为正 - 量价齐升
        >>>     if (self.data.close.new > self.data.close.prev and 
        >>>         pvo.pvo.new > 0):
        >>>         return "量价齐升，趋势健康"
        >>>     # 价格下跌且PVO为负 - 量价齐跌
        >>>     elif (self.data.close.new < self.data.close.prev and 
        >>>           pvo.pvo.new < 0):
        >>>         return "量价齐跌，趋势延续"
        """
        ...

    @tobtind(lines=['qqe', 'rsi_ma', 'qqel', 'qqes'], lib='pta')
    def qqe(self, length=14, smooth=5, factor=4.236, mamode="sma", drift=1, offset=0, **kwargs) -> IndFrame:
        """
        量化定性估计指标 (Quantitative Qualitative Estimation, QQE)
        ---------
            类似于SuperTrend，但使用带有上下带的平滑RSI。
            当平滑RSI交叉前一个上带时确定多头趋势，
            当平滑RSI交叉前一个下带时确定空头趋势。

        数据来源:
        ---------
            https://www.tradingview.com/script/IYfA9R2k-QQE-MT4/
            https://www.tradingpedia.com/forex-trading-indicators/quantitative-qualitative-estimation
            https://www.prorealcode.com/prorealtime-indicators/qqe-quantitative-qualitative-estimation/

        计算方法:
        ---------
            参考源代码实现

        参数:
        ---------
        >>> length (int): RSI周期. 默认: 14
            smooth (int): RSI平滑周期. 默认: 5
            factor (float): QQE因子. 默认: 4.236
            mamode (str): 移动平均模式，参考```help(ta.ma)```. 默认: 'sma'
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含qqe、rsi_ma、qqel、qqes列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算QQE指标
        >>> qqe_data = self.data.qqe(length=14, smooth=5)
        >>> qqe, rsi_ma, qqel, qqes = qqe_data.qqe, qqe_data.rsi_ma, qqe_data.qqel, qqe_data.qqes
        >>> 
        >>> # 使用QQE识别趋势转换
        >>> def qqe_trend_signals(self):
        >>>     qqe = self.data.qqe(length=14)
        >>>     # QQE上穿上轨 - 多头趋势开始
        >>>     if qqe.qqe.new > qqe.qqel.new and qqe.qqe.prev <= qqe.qqel.prev:
        >>>         return "QQE多头信号"
        >>>     # QQE下穿下轨 - 空头趋势开始
        >>>     elif qqe.qqe.new < qqe.qqes.new and qqe.qqe.prev >= qqe.qqes.prev:
        >>>         return "QQE空头信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def roc(self, length=10, scalar=100., talib=True, offset=0, **kwargs) -> IndSeries:
        """
        变动率指标 (Rate of Change, ROC)
        ---------
            也称为动量指标（容易混淆）。
            是一个纯粹的动量震荡指标，衡量价格与'n'（或长度）周期前价格的百分比变化。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Rate_of_Change_(ROC)

        计算方法:
        ---------
            MOM = Momentum
            ROC = 100 * MOM(close, length) / close.shift(length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            scalar (float): 放大倍数. 默认: 100
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算变动率指标
        >>> roc_IndSeries = self.data.roc(length=10)
        >>> 
        >>> # 使用ROC识别动量强度
        >>> def roc_momentum_strength(self):
        >>>     roc = self.data.roc(length=10)
        >>>     # ROC > 10 - 强烈上涨动量
        >>>     if roc.new > 10:
        >>>         return "强烈上涨动量"
        >>>     # ROC < -10 - 强烈下跌动量
        >>>     elif roc.new < -10:
        >>>         return "强烈下跌动量"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def rsi(self, length=14, scalar=100., talib=True, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        相对强弱指数 (Relative Strength Index, RSI)
        ---------
            流行的动量震荡指标，用于衡量定向价格运动的速度和幅度。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Relative_Strength_Index_(RSI)

        计算方法:
        ---------
            ABS = Absolute Value
            RMA = Rolling Moving Average
            diff = close.diff(drift)
            positive = diff if diff > 0 else 0
            negative = diff if diff < 0 else 0
            pos_avg = RMA(positive, length)
            neg_avg = ABS(RMA(negative, length))
            RSI = scalar * pos_avg / (pos_avg + neg_avg)

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            scalar (float): 放大倍数. 默认: 100
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算RSI指标
        >>> rsi_IndSeries = self.data.rsi(length=14)
        >>> 
        >>> # 使用RSI识别超买超卖
        >>> def rsi_overbought_oversold(self):
        >>>     rsi = self.data.rsi(length=14)
        >>>     # RSI > 70 - 超买区域
        >>>     if rsi.new > 70:
        >>>         return "RSI超买，注意回调"
        >>>     # RSI < 30 - 超卖区域
        >>>     elif rsi.new < 30:
        >>>         return "RSI超卖，可能反弹"
        >>> 
        >>> # RSI背离分析
        >>> def rsi_divergence_analysis(self):
        >>>     rsi = self.data.rsi(length=14)
        >>>     # 价格创新低但RSI未创新低 - 看涨背离
        >>>     if (self.data.close.new < self.data.close.prev and 
        >>>         rsi.new > rsi.prev):
        >>>         return "RSI看涨背离"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def rsx(self, length=14, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        相对强弱扩展指标 (Relative Strength Xtra, RSX)
        ---------
            基于流行的RSI指标，受Jurik Research工作的启发。
            这个增强版的RSI减少了噪音，提供了更清晰、略有延迟的动量和价格运动速度洞察。

        数据来源:
        ---------
            http://www.jurikres.com/catalog1/ms_rsx.htm
            https://www.prorealcode.com/prorealtime-indicators/jurik-rsx/

        计算方法:
        ---------
            参考源代码实现

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算RSX指标
        >>> rsx_IndSeries = self.data.rsx(length=14)
        >>> 
        >>> # 使用RSX替代传统RSI
        >>> def rsx_trading_signals(self):
        >>>     rsx = self.data.rsx(length=14)
        >>>     # RSX > 70 - 超买信号
        >>>     if rsx.new > 70:
        >>>         self.data.sell()
        >>>     # RSX < 30 - 超卖信号
        >>>     elif rsx.new < 30:
        >>>         self.data.buy()
        """
        ...

    @tobtind(lines=['rvgi', 'rvgs'], lib='pta')
    def rvgi(self, length=14, swma_length=4, offset=0, **kwargs) -> IndFrame:
        """
        相对活力指数 (Relative Vigor Index, RVGI)
        ---------
            试图衡量趋势相对于其收盘价在其交易区间的强度。
            基于这样的信念：在上升趋势中倾向于收盘高于开盘价，
            在下降趋势中倾向于收盘低于开盘价。

        数据来源:
        ---------
            https://www.investopedia.com/terms/r/relative_vigor_index.asp

        计算方法:
        ---------
            SWMA = Symmetrically Weighted Moving Average
            numerator = SUM(SWMA(close - open, swma_length), length)
            denominator = SUM(SWMA(high - low, swma_length), length)
            RVGI = numerator / denominator

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            swma_length (int): 周期. 默认: 4
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含rvgi、rvgs列的数据框

        所需数据字段:
        ---------
        >>> open, high, low, close

        使用案例:
        ---------
        >>> # 计算相对活力指数
        >>> rvgi_data = self.data.rvgi(length=14)
        >>> rvgi, signal = rvgi_data.rvgi, rvgi_data.rvgs
        >>> 
        >>> # 使用RVGI识别趋势强度
        >>> def rvgi_trend_strength(self):
        >>>     rvgi = self.data.rvgi(length=14)
        >>>     # RVGI上穿信号线 - 看涨信号
        >>>     if rvgi.rvgi.new > rvgi.rvgs.new and rvgi.rvgi.prev <= rvgi.rvgs.prev:
        >>>         return "RVGI看涨信号"
        >>>     # RVGI下穿信号线 - 看跌信号
        >>>     elif rvgi.rvgi.new < rvgi.rvgs.new and rvgi.rvgi.prev >= rvgi.rvgs.prev:
        >>>         return "RVGI看跌信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def slope(self, length=10, as_angle=False, to_degrees=False, vertical=None, offset=0, **kwargs) -> IndSeries:
        """
        斜率指标 (Slope)
        ---------
            返回长度为n的序列的斜率。可以将斜率转换为角度。

        数据来源:
        ---------
            代数基础

        计算方法:
        ---------
            slope = close.diff(length) / length
            if as_angle:
                slope = slope.apply(atan)
                if to_degrees:
                    slope *= 180 / PI

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> as_angle (bool, 可选): 将斜率转换为角度. 默认: False
            to_degrees (bool, 可选): 将斜率角度转换为度数. 默认: False
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算价格斜率
        >>> slope_IndSeries = self.data.slope(length=10)
        >>> 
        >>> # 使用斜率识别趋势强度
        >>> def slope_trend_strength(self):
        >>>     slope = self.data.slope(length=10, as_angle=True, to_degrees=True)
        >>>     # 斜率 > 45度 - 强烈上升趋势
        >>>     if slope.new > 45:
        >>>         return "强烈上升趋势"
        >>>     # 斜率 < -45度 - 强烈下降趋势
        >>>     elif slope.new < -45:
        >>>         return "强烈下降趋势"
        """
        ...

    @tobtind(lines=['smi', 'smis', 'smios'], lib='pta')
    def smi(self, fast=5, slow=20, signal=5, scalar=1., offset=0, **kwargs) -> IndFrame:
        """
        SMI遍历指标 (SMI Ergodic Indicator)
        ---------
            与William Blau开发的真实强度指数(TSI)相同，但SMI包含信号线。
            SMI使用价格减去前一个价格的双重移动平均线。
            当上穿零轴时趋势看涨，下穿零轴时趋势看跌。

        数据来源:
        ---------
            https://www.motivewave.com/studies/smi_ergodic_indicator.htm
            https://www.tradingview.com/script/Xh5Q0une-SMI-Ergodic-Oscillator/
            https://www.tradingview.com/script/cwrgy4fw-SMIIO/

        计算方法:
        ---------
            TSI = True Strength Index
            EMA = Exponential Moving Average
            ERG = TSI(close, fast, slow)
            Signal = EMA(ERG, signal)
            OSC = ERG - Signal

        参数:
        ---------
        >>> fast (int): 快周期. 默认: 5
            slow (int): 慢周期. 默认: 20
            signal (int): 信号周期. 默认: 5
            scalar (float): 放大倍数. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含smi、smis、smios列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算SMI遍历指标
        >>> smi_data = self.data.smi(fast=5, slow=20, signal=5)
        >>> smi, signal, oscillator = smi_data.smi, smi_data.smis, smi_data.smios
        >>> 
        >>> # 使用SMI识别趋势转换
        >>> def smi_trend_signals(self):
        >>>     smi = self.data.smi()
        >>>     # SMI上穿零轴 - 看涨信号
        >>>     if smi.smi.new > 0 and smi.smi.prev <= 0:
        >>>         return "SMI看涨信号"
        >>>     # SMI下穿零轴 - 看跌信号
        >>>     elif smi.smi.new < 0 and smi.smi.prev >= 0:
        >>>         return "SMI看跌信号"
        """
        ...

    @tobtind(lines=['sqz_on', 'sqz_off', 'sqz_no'], lib="pta")
    def squeeze(self, bb_length=20, bb_std=2., kc_length=20, kc_scalar=1.5,
                mom_length=12, mom_smooth=6, use_tr=True, mamode="sma", offset=0, **kwargs) -> IndFrame:
        """
        挤压指标 (Squeeze)
        ---------
            John Carter的"TTM Squeeze"指标的扩展版本。
            试图捕捉布林带和凯尔特纳通道之间的关系。
            当波动性增加时，带之间的距离也会增加，反之亦然。

        数据来源:
        ---------
            https://usethinkscript.com/threads/john-carters-squeeze-pro-indicator-for-thinkorswim-free.4021/
            https://www.tradingview.com/script/TAAt6eRX-Squeeze-PRO-Indicator-Makit0/

        计算方法:
        ---------
            BB = Bollinger Bands
            KC = Keltner Channels
            MOM = Momentum
            SMA = Simple Moving Average
            EMA = Exponential Moving Average
            TR = True Range
            RANGE = TR(high, low, close) if using_tr else high - low
            BB_LOW, BB_MID, BB_HIGH = BB(close, bb_length, std=bb_std)
            KC_LOW, KC_MID, KC_HIGH = KC(high, low, close, kc_length, kc_scalar, TR)
            MOMO = MOM(close, mom_length)
            SQZ = EMA(MOMO, mom_smooth) if mamode == "ema" else SMA(MOMO, mom_smooth)
            SQZ_ON = (BB_LOW > KC_LOW) and (BB_HIGH < KC_HIGH)
            SQZ_OFF = (BB_LOW < KC_LOW) and (BB_HIGH > KC_HIGH)
            NO_SQZ = !SQZ_ON and !SQZ_OFF

        参数:
        ---------
        >>> bb_length (int): 布林带周期. 默认: 20
            bb_std (float): 布林带标准差. 默认: 2
            kc_length (int): 凯尔特纳通道周期. 默认: 20
            kc_scalar (float): 凯尔特纳通道乘数. 默认: 1.5
            mom_length (int): 动量周期. 默认: 12
            mom_smooth (int): 动量平滑周期. 默认: 6
            mamode (str): 仅"ema"或"sma". 默认: "sma"
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> tr (bool, 可选): 对凯尔特纳通道使用真实波幅. 默认: True
            asint (bool, 可选): 使用整数而不是布尔值. 默认: True
            detailed (bool, 可选): 返回SQZ的附加变体用于可视化. 默认: False
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含sqz_on、sqz_off、sqz_no列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算挤压指标
        >>> squeeze_data = self.data.squeeze()
        >>> sqz_on, sqz_off, sqz_no = squeeze_data.sqz_on, squeeze_data.sqz_off, squeeze_data.sqz_no
        >>> 
        >>> # 使用挤压指标识别突破机会
        >>> def squeeze_breakout_opportunity(self):
        >>>     sqz = self.data.squeeze()
        >>>     # 从挤压状态释放 - 潜在突破信号
        >>>     if sqz.sqz_on.prev == 1 and sqz.sqz_off.new == 1:
        >>>         return "挤压释放，关注突破"
        """
        ...

    @tobtind(lines=['sqzpro', 'sqz_onwide', 'sqz_onnormal', 'sqz_onnarrow', 'sqzpro_off', 'sqzpro_no'], lib="pta")
    def squeeze_pro(self, bb_length=20, bb_std=2., kc_length=20,
                    kc_scalar_wide=2., kc_scalar_normal=1.5,
                    kc_scalar_narrow=1., mom_length=12, mom_smooth=6,
                    use_tr=True, mamode="sma", offset=0, **kwargs) -> IndFrame:
        """
        专业挤压指标 (Squeeze PRO)
        ---------
            基于John Carter的"TTM Squeeze"指标。
            使用三个不同宽度的凯尔特纳通道来提供更详细的挤压状态信息。

        数据来源:
        ---------
            https://tradestation.tradingappstore.com/products/TTMSqueeze
            https://www.tradingview.com/scripts/lazybear/
            https://tlc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/T-U/TTM-Squeeze

        计算方法:
        ---------
            参考源代码实现

        参数:
        ---------
        >>> bb_length (int): 布林带周期. 默认: 20
            bb_std (float): 布林带标准差. 默认: 2
            kc_length (int): 凯尔特纳通道周期. 默认: 20
            kc_scalar_wide (float): 宽凯尔特纳通道乘数. 默认: 2
            kc_scalar_normal (float): 正常凯尔特纳通道乘数. 默认: 1.5
            kc_scalar_narrow (float): 窄凯尔特纳通道乘数. 默认: 1
            mom_length (int): 动量周期. 默认: 12
            mom_smooth (int): 动量平滑周期. 默认: 6
            mamode (str): 仅"ema"或"sma". 默认: "sma"
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> tr (bool, 可选): 对凯尔特纳通道使用真实波幅. 默认: True
            asint (bool, 可选): 使用整数而不是布尔值. 默认: True
            detailed (bool, 可选): 返回SQZ的附加变体用于可视化. 默认: False
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含sqzpro、sqz_onwide、sqz_onnormal、sqz_onnarrow、sqzpro_off、sqzpro_no列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算专业挤压指标
        >>> squeeze_pro_data = self.data.squeeze_pro()
        >>> 
        >>> # 使用专业挤压指标进行多级分析
        >>> def squeeze_pro_multi_level_analysis(self):
        >>>     sqz_pro = self.data.squeeze_pro()
        >>>     # 在窄通道中挤压 - 最强压缩状态
        >>>     if sqz_pro.sqz_onnarrow.new == 1:
        >>>         return "最强挤压状态，密切关注突破"
        >>>     # 在宽通道中挤压 - 较弱压缩状态
        >>>     elif sqz_pro.sqz_onwide.new == 1:
        >>>         return "较弱挤压状态，可能继续震荡"
        """
        ...

    @tobtind(lines=['stc', 'stcmacd', 'stcstoch'], lib='pta')
    def stc(self, tclength=10, fast=12, slow=26, factor=0.5, offset=0, **kwargs) -> IndFrame:
        """
        沙夫趋势周期 (Schaff Trend Cycle, STC)
        ---------
            流行MACD指标的演进，包含两个级联的随机计算和额外的平滑。

        数据来源:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/schaff-trend-cycle2/

        计算方法:
        ---------
            STCmacd = Moving Average Convergance/Divergance or Oscillator
            STCstoch = Intermediate Stochastic of MACD/Osc.
            2nd Stochastic including filtering with results in the
            STC = Schaff Trend Cycle

        参数:
        ---------
        >>> tclength (int): 沙夫趋势周期信号线长度. 默认: 10
            fast (int): 快周期. 默认: 12
            slow (int): 慢周期. 默认: 26
            factor (float): 最后随机计算的平滑因子. 默认: 0.5
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> ma1: 外部提供的第一移动平均线（与ma2结合使用时必需）
            ma2: 外部提供的第二移动平均线（与ma1结合使用时必需）
            osc: 外部提供的震荡指标
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含stc、stcmacd、stcstoch列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算沙夫趋势周期
        >>> stc_data = self.data.stc(tclength=10, fast=12, slow=26)
        >>> stc, stcmacd, stcstoch = stc_data.stc, stc_data.stcmacd, stc_data.stcstoch
        >>> 
        >>> # 使用STC识别趋势转换
        >>> def stc_trend_reversal(self):
        >>>     stc = self.data.stc()
        >>>     # STC上穿25 - 看涨信号
        >>>     if stc.stc.new > 25 and stc.stc.prev <= 25:
        >>>         return "STC看涨信号"
        >>>     # STC下穿75 - 看跌信号
        >>>     elif stc.stc.new < 75 and stc.stc.prev >= 75:
        >>>         return "STC看跌信号"
        """
        ...

    @tobtind(lines=['stochs', 'stoch_k', 'stoch_d'], lib='pta')
    def stoch(self, k=14, d=3, smooth_k=3, mamode="sma", offset=0, **kwargs) -> IndFrame:
        """
        随机指标 (Stochastic Oscillator)
        ---------
            George Lane在1950年代开发。
            是一个范围限制的震荡指标，有两条在0和100之间移动的线。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Stochastic_(STOCH)
            https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=332&Name=KD_-_Slow

        计算方法:
        ---------
            SMA = Simple Moving Average
            LL = low for last k periods
            HH = high for last k periods
            STOCH = 100 * (close - LL) / (HH - LL)
            STOCHk = SMA(STOCH, smooth_k)
            STOCHd = SMA(FASTK, d)

        参数:
        ---------
        >>> k (int): 快速%K周期. 默认: 14
            d (int): 慢速%K周期. 默认: 3
            smooth_k (int): 慢速%D周期. 默认: 3
            mamode (str): 移动平均模式，参考```help(ta.ma)```. 默认: 'sma'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含stochs、stoch_k、stoch_d列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算随机指标
        >>> stoch_data = self.data.stoch(k=14, d=3)
        >>> stoch, k_line, d_line = stoch_data.stochs, stoch_data.stoch_k, stoch_data.stoch_d
        >>> 
        >>> # 使用随机指标识别超买超卖
        >>> def stoch_overbought_oversold(self):
        >>>     stoch = self.data.stoch()
        >>>     # %K < 20 且 %D < 20 - 超卖区域
        >>>     if stoch.stoch_k.new < 20 and stoch.stoch_d.new < 20:
        >>>         return "随机指标超卖"
        >>>     # %K > 80 且 %D > 80 - 超买区域
        >>>     elif stoch.stoch_k.new > 80 and stoch.stoch_d.new > 80:
        >>>         return "随机指标超买"
        """
        ...

    @tobtind(lines=['stochrsi_k', 'stochrsi_d'], lib='pta')
    def stochrsi(self, length=14, rsi_length=14, k=3, d=3, mamode="sma", offset=0, **kwargs) -> IndFrame:
        """
        随机相对强弱指数 (Stochastic RSI)
        ---------
            Tushar Chande和Stanley Kroll创建。
            是一个范围限制的震荡指标，有两条在0和100之间移动的线。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Stochastic_(STOCH)

        计算方法:
        ---------
            RSI = Relative Strength Index
            SMA = Simple Moving Average
            RSI = RSI(high, low, close, rsi_length)
            LL = lowest RSI for last rsi_length periods
            HH = highest RSI for last rsi_length periods
            STOCHRSI = 100 * (RSI - LL) / (HH - LL)
            STOCHRSIk = SMA(STOCHRSI, k)
            STOCHRSId = SMA(STOCHRSIk, d)

        参数:
        ---------
        >>> length (int): 随机RSI周期. 默认: 14
            rsi_length (int): RSI周期. 默认: 14
            k (int): 快速%K周期. 默认: 3
            d (int): 慢速%K周期. 默认: 3
            mamode (str): 移动平均模式，参考```help(ta.ma)```. 默认: 'sma'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含stochrsi_k、stochrsi_d列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算随机RSI
        >>> stochrsi_data = self.data.stochrsi(length=14)
        >>> stochrsi_k, stochrsi_d = stochrsi_data.stochrsi_k, stochrsi_data.stochrsi_d
        >>> 
        >>> # 使用随机RSI识别超买超卖
        >>> def stochrsi_extremes(self):
        >>>     stochrsi = self.data.stochrsi()
        >>>     # 随机RSI < 0.2 - 超卖
        >>>     if stochrsi.stochrsi_k.new < 0.2:
        >>>         return "随机RSI超卖"
        >>>     # 随机RSI > 0.8 - 超买
        >>>     elif stochrsi.stochrsi_k.new > 0.8:
        >>>         return "随机RSI超买"
        """
        ...

    @tobtind(lines=['td_seq_up', 'td_seq_dn'], lib='pta')
    def td_seq(self, asint=False, offset=0, show_all=True, **kwargs) -> IndFrame:
        """
        汤姆·迪马克序列指标 (TD Sequential)
        ---------
            试图识别上升趋势或下降趋势耗尽并反转的价格点。

        数据来源:
        ---------
            https://tradetrekker.wordpress.com/tdsequential/

        计算方法:
        ---------
            将当前收盘价与4天前的价格进行比较，最多13天。
            对于连续上升或下降的价格序列，显示第6天到第9天的值。

        参数:
        ---------
        >>> asint (bool): 如果为True，用0填充nas并将类型更改为int. 默认: False
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> show_all (bool): 显示1-13。如果设置为False，显示6-9. 默认: True
            fillna (value, 可选): pd.DataFrame.fillna(value)

        返回:
        ---------
        >>> IndFrame: 包含td_seq_up、td_seq_dn列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算汤姆·迪马克序列
        >>> td_seq_data = self.data.td_seq()
        >>> td_seq_up, td_seq_dn = td_seq_data.td_seq_up, td_seq_data.td_seq_dn
        >>> 
        >>> # 使用TD序列识别反转点
        >>> def td_sequential_reversal(self):
        >>>     td_seq = self.data.td_seq()
        >>>     # 完成9-13-9序列 - 强烈反转信号
        >>>     if td_seq.td_seq_up.new == 13:
        >>>         return "TD序列卖出信号"
        >>>     elif td_seq.td_seq_dn.new == 13:
        >>>         return "TD序列买入信号"
        """
        ...

    @tobtind(lines=['trix', 'trixs'], lib='pta')
    def trix(self, length=18, signal=9, scalar=100., drift=1, offset=0, **kwargs) -> IndFrame:
        """
        三重指数平滑平均线 (TRIX)
        ---------
            动量震荡指标，用于识别背离。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/TRIX

        计算方法:
        ---------
            EMA = Exponential Moving Average
            ROC = Rate of Change
            ema1 = EMA(close, length)
            ema2 = EMA(ema1, length)
            ema3 = EMA(ema2, length)
            TRIX = 100 * ROC(ema3, drift)

        参数:
        ---------
        >>> length (int): 周期. 默认: 18
            signal (int): 信号周期. 默认: 9
            scalar (float): 放大倍数. 默认: 100
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含trix、trixs列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算TRIX指标
        >>> trix_data = self.data.trix(length=18, signal=9)
        >>> trix, signal = trix_data.trix, trix_data.trixs
        >>> 
        >>> # 使用TRIX识别趋势变化
        >>> def trix_trend_change(self):
        >>>     trix = self.data.trix()
        >>>     # TRIX上穿零轴 - 看涨信号
        >>>     if trix.trix.new > 0 and trix.trix.prev <= 0:
        >>>         return "TRIX看涨信号"
        >>>     # TRIX下穿零轴 - 看跌信号
        >>>     elif trix.trix.new < 0 and trix.trix.prev >= 0:
        >>>         return "TRIX看跌信号"
        """
        ...

    @tobtind(lines=['tsir', 'tsis'], lib='pta')
    def tsi(self, fast=13, slow=25, signal=13, scalar=100., mamode="ema", drift=1, offset=0, **kwargs) -> IndFrame:
        """
        真实强度指数 (True Strength Index, TSI)
        ---------
            动量指标，用于识别趋势方向的短期波动以及确定超买和超卖条件。

        数据来源:
        ---------
            https://www.investopedia.com/terms/t/tsi.asp

        计算方法:
        ---------
            EMA = Exponential Moving Average
            diff = close.diff(drift)
            slow_ema = EMA(diff, slow)
            fast_slow_ema = EMA(slow_ema, slow)
            abs_diff_slow_ema = absolute_diff_ema = EMA(ABS(diff), slow)
            abema = abs_diff_fast_slow_ema = EMA(abs_diff_slow_ema, fast)
            TSI = scalar * fast_slow_ema / abema
            Signal = EMA(TSI, signal)

        参数:
        ---------
        >>> fast (int): 快周期. 默认: 13
            slow (int): 慢周期. 默认: 25
            signal (int): 信号周期. 默认: 13
            scalar (float): 放大倍数. 默认: 100
            mamode (str): TSI信号线的移动平均模式，参考```help(ta.ma)```. 默认: 'ema'
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含tsir、tsis列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算真实强度指数
        >>> tsi_data = self.data.tsi(fast=13, slow=25, signal=13)
        >>> tsi, signal = tsi_data.tsir, tsi_data.tsis
        >>> 
        >>> # 使用TSI识别动量变化
        >>> def tsi_momentum_signals(self):
        >>>     tsi = self.data.tsi()
        >>>     # TSI上穿信号线 - 买入信号
        >>>     if tsi.tsir.new > tsi.tsis.new and tsi.tsir.prev <= tsi.tsis.prev:
        >>>         self.data.buy()
        >>>     # TSI下穿信号线 - 卖出信号
        >>>     elif tsi.tsir.new < tsi.tsis.new and tsi.tsir.prev >= tsi.tsis.prev:
        >>>         self.data.sell()
        """
        ...

    @tobtind(lines=None, lib='pta')
    def uo(self, fast=7, medium=14, slow=28, fast_w=4., medium_w=2.,
           slow_w=1., talib=True, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        终极震荡指标 (Ultimate Oscillator, UO)
        ---------
            三个不同周期的动量指标。试图修正错误的背离交易信号。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Ultimate_Oscillator_(UO)

        计算方法:
        ---------
            min_low_or_pc  = close.shift(drift).combine(low, min)
            max_high_or_pc = close.shift(drift).combine(high, max)
            bp = buying pressure = close - min_low_or_pc
            tr = true range = max_high_or_pc - min_low_or_pc
            fast_avg = SUM(bp, fast) / SUM(tr, fast)
            medium_avg = SUM(bp, medium) / SUM(tr, medium)
            slow_avg = SUM(bp, slow) / SUM(tr, slow)
            total_weight = fast_w + medium_w + slow_w
            weights = (fast_w * fast_avg) + (medium_w * medium_avg) + (slow_w * slow_avg)
            UO = 100 * weights / total_weight

        参数:
        ---------
        >>> fast (int): 快速周期. 默认: 7
            medium (int): 中速周期. 默认: 14
            slow (int): 慢速周期. 默认: 28
            fast_w (float): 快速权重. 默认: 4.0
            medium_w (float): 中速权重. 默认: 2.0
            slow_w (float): 慢速权重. 默认: 1.0
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算终极震荡指标
        >>> uo_IndSeries = self.data.uo(fast=7, medium=14, slow=28)
        >>> 
        >>> # 使用UO识别买卖信号
        >>> def uo_trading_signals(self):
        >>>     uo = self.data.uo()
        >>>     # UO > 70 - 超买区域
        >>>     if uo.new > 70:
        >>>         return "UO超买信号"
        >>>     # UO < 30 - 超卖区域
        >>>     elif uo.new < 30:
        >>>         return "UO超卖信号"
        >>>     # UO背离分析
        >>>     if (self.data.close.new > self.data.close.prev and 
        >>>         uo.new < uo.prev):
        >>>         return "UO看跌背离"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def willr(self, length=14, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        威廉指标 (William's Percent R, WILLR)
        ---------
            类似于RSI的动量震荡指标，试图识别超买和超卖条件。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Williams_%25R_(%25R)

        计算方法:
        ---------
            LL = low.rolling(length).min()
            HH = high.rolling(length).max()
            WILLR = 100 * ((close - LL) / (HH - LL) - 1)

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算威廉指标
        >>> willr_IndSeries = self.data.willr(length=14)
        >>> 
        >>> # 使用威廉指标识别极端行情
        >>> def willr_extreme_conditions(self):
        >>>     willr = self.data.willr(length=14)
        >>>     # WILLR < -80 - 强烈超卖
        >>>     if willr.new < -80:
        >>>         return "威廉指标强烈超卖"
        >>>     # WILLR > -20 - 强烈超买
        >>>     elif willr.new > -20:
        >>>         return "威廉指标强烈超买"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def alma(self, length=10, sigma=6., distribution_offset=0.85, offset=0, **kwargs) -> IndSeries:
        """
        阿诺德移动平均线 (Arnaud Legoux Moving Average, ALMA)
        ---------
            使用正态（高斯）分布曲线的移动平均线。
            可以调节指标的平滑度和高灵敏度。

        数据来源:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/alma-arnaud-legoux-moving-average/

        计算方法:
        ---------
            参考源代码实现

        参数:
        ---------
        >>> length (int): 周期，窗口大小. 默认: 10
            sigma (float): 平滑值. 默认: 6.0
            distribution_offset (float): 分布偏移值，最小值0（更平滑），最大值1（更敏感）. 默认: 0.85
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算ALMA移动平均线
        >>> alma_IndSeries = self.data.alma(length=20, sigma=6, distribution_offset=0.85)
        >>> 
        >>> # 使用ALMA作为动态支撑阻力
        >>> def alma_support_resistance(self):
        >>>     alma = self.data.alma(length=20)
        >>>     # 价格上穿ALMA - 看涨信号
        >>>     if self.data.close.new > alma.new and self.data.close.prev <= alma.prev:
        >>>         return "价格上穿ALMA，看涨"
        >>>     # 价格下穿ALMA - 看跌信号
        >>>     elif self.data.close.new < alma.new and self.data.close.prev >= alma.prev:
        >>>         return "价格下穿ALMA，看跌"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def dema(self, length=10, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        双指数移动平均线 (Double Exponential Moving Average, DEMA)
        ---------
            试图提供比普通指数移动平均线(EMA)更平滑且延迟更小的平均值。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/double-exponential-moving-average-dema/

        计算方法:
        ---------
            EMA = Exponential Moving Average
            ema1 = EMA(close, length)
            ema2 = EMA(ema1, length)
            DEMA = 2 * ema1 - ema2

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算DEMA移动平均线
        >>> dema_IndSeries = self.data.dema(length=20)
        >>> 
        >>> # 使用DEMA识别趋势
        >>> def dema_trend_identification(self):
        >>>     dema = self.data.dema(length=20)
        >>>     # 价格在DEMA上方 - 上升趋势
        >>>     if self.data.close.new > dema.new:
        >>>         return "价格在DEMA上方，上升趋势"
        >>>     # 价格在DEMA下方 - 下降趋势
        >>>     elif self.data.close.new < dema.new:
        >>>         return "价格在DEMA下方，下降趋势"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def ema(self, length=10, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        指数移动平均线 (Exponential Moving Average, EMA)
        ---------
            与简单移动平均线(SMA)相比更敏感的移动平均线。

        数据来源:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:moving_averages
            https://www.investopedia.com/ask/answers/122314/what-exponential-moving-average-ema-formula-and-how-ema-calculated.asp

        计算方法:
        ---------
            if sma:
                sma_nth = close[0:length].sum() / length
                close[:length - 1] = np.NaN
                close.iloc[length - 1] = sma_nth
            EMA = close.ewm(span=length, adjust=adjust).mean()

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> adjust (bool, 可选): 默认: False
            sma (bool, 可选): 如果为True，使用SMA作为初始值. 默认: True
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算EMA移动平均线
        >>> ema_IndSeries = self.data.ema(length=20)
        >>> 
        >>> # 使用EMA交叉策略
        >>> def ema_crossover_strategy(self):
        >>>     ema_fast = self.data.ema(length=10)
        >>>     ema_slow = self.data.ema(length=20)
        >>>     # 快速EMA上穿慢速EMA - 金叉买入
        >>>     if (ema_fast.new > ema_slow.new and 
        >>>         ema_fast.prev <= ema_slow.prev):
        >>>         self.data.buy()
        >>>     # 快速EMA下穿慢速EMA - 死叉卖出
        >>>     elif (ema_fast.new < ema_slow.new and 
        >>>           ema_fast.prev >= ema_slow.prev):
        >>>         self.data.sell()
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def fwma(self, length=10, asc=True, offset=0, **kwargs) -> IndSeries:
        """
        斐波那契加权移动平均线 (Fibonacci's Weighted Moving Average, FWMA)
        ---------
            类似于加权移动平均线(WMA)，权重基于斐波那契数列。

        数据来源:
        ---------
            Kevin Johnson

        计算方法:
        ---------
            fibs = utils.fibonacci(length - 1)
            FWMA = close.rolling(length)_.apply(weights(fibs), raw=True)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            asc (bool): 近期值权重更大. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算斐波那契加权移动平均线
        >>> fwma_IndSeries = self.data.fwma(length=13)
        >>> 
        >>> # 使用FWMA作为动态支撑位
        >>> def fwma_support_level(self):
        >>>     fwma = self.data.fwma(length=13)
        >>>     # 价格回踩FWMA获得支撑 - 买入机会
        >>>     if (abs(self.data.close.new - fwma.new) / fwma.new < 0.01 and 
        >>>         self.data.close.new > fwma.new):
        >>>         return "价格在FWMA获得支撑"
        """
        ...

    @tobtind(lines=['hilo', 'hilol', 'hilos'], overlap=True, lib='pta')
    def hilo(self, high_length=13, low_length=21, mamode="sma", offset=0, **kwargs) -> IndFrame:
        """
        甘氏高低激活器 (Gann HiLo Activator)
        ---------
            Robert Krausz在1998年创建。
            基于移动平均线的趋势指标，由两个不同的简单移动平均线组成。

        数据来源:
        ---------
            https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=447&Name=Gann_HiLo_Activator
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/simple-moving-average-sma/
            https://www.tradingview.com/script/XNQSLIYb-Gann-High-Low/

        计算方法:
        ---------
            if "ema":
                high_ma = EMA(high, high_length)
                low_ma = EMA(low, low_length)
            elif "hma":
                high_ma = HMA(high, high_length)
                low_ma = HMA(low, low_length)
            else: # "sma"
                high_ma = SMA(high, high_length)
                low_ma = SMA(low, low_length)
            hilo = Series(np.nan, index=close.index)
            for i in range(1, m):
                if close.iloc[i] > high_ma.iloc[i - 1]:
                    hilo.iloc[i] = low_ma.iloc[i]
                elif close.iloc[i] < low_ma.iloc[i - 1]:
                    hilo.iloc[i] = high_ma.iloc[i]
                else:
                    hilo.iloc[i] = hilo.iloc[i - 1]

        参数:
        ---------
        >>> high_length (int): 高点周期. 默认: 13
            low_length (int): 低点周期. 默认: 21
            mamode (str): 移动平均模式，参考```help(ta.ma)```. 默认: 'sma'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> adjust (bool): 默认: True
            presma (bool, 可选): 如果为True，使用SMA作为初始值
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含hilo、hilol、hilos列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算甘氏高低激活器
        >>> hilo_data = self.data.hilo(high_length=13, low_length=21)
        >>> hilo, hilol, hilos = hilo_data.hilo, hilo_data.hilol, hilo_data.hilos
        >>> 
        >>> # 使用HiLo识别趋势转换
        >>> def hilo_trend_change(self):
        >>>     hilo = self.data.hilo()
        >>>     # HiLo从上升转为下降 - 趋势转弱
        >>>     if hilo.hilo.new < hilo.hilo.prev and hilo.hilo.prev >= hilo.hilo.sndprev:
        >>>         return "HiLo趋势转弱"
        >>>     # HiLo从下降转为上升 - 趋势转强
        >>>     elif hilo.hilo.new > hilo.hilo.prev and hilo.hilo.prev <= hilo.hilo.sndprev:
        >>>         return "HiLo趋势转强"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def hl2(self, offset=0, **kwargs) -> IndSeries:
        """
        高低中点指标 (HL2)
        ---------
            最高价和最低价的平均值。

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low

        使用案例:
        ---------
        >>> # 计算高低中点
        >>> hl2_IndSeries = self.data.hl2()
        >>> 
        >>> # 使用HL2作为参考价格
        >>> def hl2_reference_price(self):
        >>>     hl2 = self.data.hl2()
        >>>     # 收盘价高于HL2 - 偏强势
        >>>     if self.data.close.new > hl2.new:
        >>>         return "价格偏强势"
        >>>     # 收盘价低于HL2 - 偏弱势
        >>>     elif self.data.close.new < hl2.new:
        >>>         return "价格偏弱势"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def hlc3(self, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        典型价格指标 (HLC3)
        ---------
            最高价、最低价和收盘价的平均值。

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算典型价格
        >>> hlc3_IndSeries = self.data.hlc3()
        >>> 
        >>> # 使用HLC3计算其他指标
        >>> def hlc3_based_indicators(self):
        >>>     hlc3 = self.data.hlc3()
        >>>     # 使用HLC3计算移动平均线
        >>>     hlc3_ma = hlc3.ema(period=20)
        >>>     return hlc3_ma
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def hma(self, length=10, offset=0, **kwargs) -> IndSeries:
        """
        赫尔移动平均线 (Hull Moving Average, HMA)
        ---------
            试图减少或消除移动平均线中的延迟。

        数据来源:
        ---------
            https://alanhull.com/hull-moving-average

        计算方法:
        ---------
            WMA = Weighted Moving Average
            half_length = int(0.5 * length)
            sqrt_length = int(sqrt(length))
            wmaf = WMA(close, half_length)
            wmas = WMA(close, length)
            HMA = WMA(2 * wmaf - wmas, sqrt_length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算赫尔移动平均线
        >>> hma_IndSeries = self.data.hma(length=20)
        >>> 
        >>> # 使用HMA识别快速趋势变化
        >>> def hma_fast_trend(self):
        >>>     hma = self.data.hma(length=20)
        >>>     # HMA快速上升 - 强烈上升趋势
        >>>     if hma.new > hma.prev > hma.sndprev:
        >>>         return "HMA强烈上升趋势"
        >>>     # HMA快速下降 - 强烈下降趋势
        >>>     elif hma.new < hma.prev < hma.sndprev:
        >>>         return "HMA强烈下降趋势"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def hwma(self, na=0.2, nb=0.1, nc=0.1, offset=0, **kwargs) -> IndSeries:
        """
        霍尔特-温特斯移动平均线 (Holt-Winter Moving Average, HWMA)
        ---------
            霍尔特-温特斯方法的三参数移动平均线，三个参数应选择以获得预测。

        数据来源:
        ---------
            https://www.mql5.com/en/code/20856

        计算方法:
        ---------
            HWMA[i] = F[i] + V[i] + 0.5 * A[i]
            where..
            F[i] = (1-na) * (F[i-1] + V[i-1] + 0.5 * A[i-1]) + na * Price[i]
            V[i] = (1-nb) * (V[i-1] + A[i-1]) + nb * (F[i] - F[i-1])
            A[i] = (1-nc) * A[i-1] + nc * (V[i] - V[i-1])

        参数:
        ---------
        >>> na (float): 平滑序列参数 (0到1). 默认: 0.2
            nb (float): 趋势参数 (0到1). 默认: 0.1
            nc (float): 季节性参数 (0到1). 默认: 0.1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算霍尔特-温特斯移动平均线
        >>> hwma_IndSeries = self.data.hwma(na=0.2, nb=0.1, nc=0.1)
        >>> 
        >>> # 使用HWMA进行价格预测
        >>> def hwma_price_forecast(self):
        >>>     hwma = self.data.hwma(na=0.2, nb=0.1, nc=0.1)
        >>>     # HWMA向上 - 看涨预测
        >>>     if hwma.new > hwma.prev:
        >>>         return "HWMA看涨预测"
        >>>     # HWMA向下 - 看跌预测
        >>>     elif hwma.new < hwma.prev:
        >>>         return "HWMA看跌预测"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def jma(self, length=7, phase=0., offset=0, **kwargs) -> IndSeries:
        """
        茹拉克移动平均线 (Jurik Moving Average, JMA)
        ---------
            试图消除噪音以看到"真实"的基础活动。
            具有极低的延迟，非常平滑，对市场缺口反应灵敏。

        数据来源:
        ---------
            https://c.mql5.com/forextsd/forum/164/jurik_1.pdf
            https://www.prorealcode.com/prorealtime-indicators/jurik-volatility-bands/

        计算方法:
        ---------
            参考源代码实现

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 7
            phase (float): 平均值轻重程度 [-100, 100]. 默认: 0
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算茹拉克移动平均线
        >>> jma_IndSeries = self.data.jma(length=7, phase=0)
        >>> 
        >>> # 使用JMA识别低延迟趋势
        >>> def jma_low_lag_trend(self):
        >>>     jma = self.data.jma(length=7, phase=0)
        >>>     # JMA快速响应价格变化
        >>>     jma_ma = jma.ema(period=5)
        >>>     # JMA上穿其移动平均线 - 快速买入信号
        >>>     if jma.new > jma_ma.new and jma.prev <= jma_ma.prev:
        >>>         return "JMA快速买入信号"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def kama(self, length=10, fast=2, slow=30, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        考夫曼自适应移动平均线 (Kaufman's Adaptive Moving Average, KAMA)
        ---------
            Perry Kaufman开发，旨在考虑市场噪音或波动性。
            当价格波动相对较小且噪音较低时，KAMA将紧密跟随价格。
            当价格波动扩大时，KAMA将调整并以更大距离跟随价格。

        数据来源:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:kaufman_s_adaptive_moving_average
            https://www.tradingview.com/script/wZGOIz9r-REPOST-Indicators-3-Different-Adaptive-Moving-Averages/

        计算方法:
        ---------
            参考源代码实现

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            fast (int): 快速移动平均周期. 默认: 2
            slow (int): 慢速移动平均周期. 默认: 30
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算考夫曼自适应移动平均线
        >>> kama_IndSeries = self.data.kama(length=10, fast=2, slow=30)
        >>> 
        >>> # 使用KAMA适应不同市场环境
        >>> def kama_adaptive_strategy(self):
        >>>     kama = self.data.kama(length=10)
        >>>     # 价格在KAMA上方 - 上升趋势
        >>>     if self.data.close.new > kama.new:
        >>>         return "KAMA上升趋势"
        >>>     # 价格在KAMA下方 - 下降趋势
        >>>     elif self.data.close.new < kama.new:
        >>>         return "KAMA下降趋势"
        """
        ...

    @tobtind(lines=['spana', 'spanb', 'tenkan_sen', 'kijun_sen', 'chikou_span'], overlap=True, lib="pta")
    def ichimoku(self, tenkan=9, kijun=26, senkou=52, include_chikou=True, offset=0, **kwargs) -> IndFrame:
        """
        一目均衡表 (Ichimoku Kinkō Hyō)
        ---------
            二战前开发作为金融市场的预测模型。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/ichimoku-ich/

        计算方法:
        ---------
            MIDPRICE = Midprice
            TENKAN_SEN = MIDPRICE(high, low, close, length=tenkan)
            KIJUN_SEN = MIDPRICE(high, low, close, length=kijun)
            CHIKOU_SPAN = close.shift(-kijun)
            SPAN_A = 0.5 * (TENKAN_SEN + KIJUN_SEN)
            SPAN_A = SPAN_A.shift(kijun)
            SPAN_B = MIDPRICE(high, low, close, length=senkou)
            SPAN_B = SPAN_B.shift(kijun)

        参数:
        ---------
        >>> tenkan (int): 转换线周期. 默认: 9
            kijun (int): 基准线周期. 默认: 26
            senkou (int): 先行带周期. 默认: 52
            include_chikou (bool): 是否包含迟行带. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含spana、spanb、tenkan_sen、kijun_sen、chikou_span列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算一目均衡表
        >>> ichimoku_data = self.data.ichimoku(tenkan=9, kijun=26, senkou=52)
        >>> span_a, span_b, tenkan, kijun, chikou = ichimoku_data.spana, ichimoku_data.spanb, ichimoku_data.tenkan_sen, ichimoku_data.kijun_sen, ichimoku_data.chikou_span
        >>> 
        >>> # 使用一目均衡表识别趋势和信号
        >>> def ichimoku_trading_signals(self):
        >>>     ichi = self.data.ichimoku()
        >>>     # 价格在云层上方 - 看涨
        >>>     if (self.data.close.new > ichi.spana.new and 
        >>>         self.data.close.new > ichi.spanb.new):
        >>>         return "价格在云层上方，看涨"
        >>>     # 转换线上穿基准线 - 金叉买入
        >>>     if (ichi.tenkan_sen.new > ichi.kijun_sen.new and 
        >>>         ichi.tenkan_sen.prev <= ichi.kijun_sen.prev):
        >>>         return "转换线金叉，买入信号"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def linreg(self, length=10, offset=0, **kwargs) -> IndSeries:
        """
        线性回归移动平均线 (Linear Regression Moving Average, LINREG)
        ---------
            标准线性回归的简化版本。LINREG是单变量的滚动回归。

        数据来源:
        ---------
            TA Lib

        计算方法:
        ---------
            x = [1, 2, ..., n]
            x_sum = 0.5 * length * (length + 1)
            x2_sum = length * (length + 1) * (2 * length + 1) / 6
            divisor = length * x2_sum - x_sum * x_sum
            lr(IndSeries):
                y_sum = IndSeries.sum()
                y2_sum = (IndSeries* IndSeries).sum()
                xy_sum = (x * IndSeries).sum()
                m = (length * xy_sum - x_sum * y_sum) / divisor
                b = (y_sum * x2_sum - x_sum * xy_sum) / divisor
                return m * (length - 1) + b
            linreg = close.rolling(length).apply(lr)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> angle (bool, 可选): 如果为True，返回斜率的弧度角度. 默认: False
            degrees (bool, 可选): 如果为True，返回斜率的度数角度. 默认: False
            intercept (bool, 可选): 如果为True，返回截距. 默认: False
            r (bool, 可选): 如果为True，返回相关系数'r'. 默认: False
            slope (bool, 可选): 如果为True，返回斜率. 默认: False
            tsf (bool, 可选): 如果为True，返回时间序列预测值. 默认: False
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算线性回归移动平均线
        >>> linreg_IndSeries = self.data.linreg(length=20)
        >>> 
        >>> # 使用线性回归预测价格
        >>> def linreg_price_prediction(self):
        >>>     linreg = self.data.linreg(length=20, tsf=True)
        >>>     # 线性回归向上 - 看涨预期
        >>>     if linreg.new > linreg.prev:
        >>>         return "线性回归看涨预期"
        >>>     # 线性回归向下 - 看跌预期
        >>>     elif linreg.new < linreg.prev:
        >>>         return "线性回归看跌预期"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def mcgd(self, length=10, offset=0, c=1., **kwargs) -> IndSeries:
        """
        麦金利动态指标 (McGinley Dynamic Indicator)
        ---------
            看起来像移动平均线，但实际上是一种价格平滑机制，
            可最大限度地减少价格分离、价格锯齿，并更紧密地贴合价格。

        数据来源:
        ---------
            https://www.investopedia.com/articles/forex/09/mcginley-dynamic-indicator.asp

        计算方法:
        ---------
            def mcg_(IndSeries):
                denom = (constant * length * (IndSeries.iloc[1] / IndSeries.iloc[0]) ** 4)
                IndSeries.iloc[1] = (
                    IndSeries.iloc[0] + ((IndSeries.iloc[1] - IndSeries.iloc[0]) / denom))
                return IndSeries.iloc[1]
            mcg_cell = close[0:].rolling(2, min_periods=2).apply(mcg_, raw=False)
            mcg_ds = close[:1].append(mcg_cell[1:])

        参数:
        ---------
        >>> length (int): 指标周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0
            c (float): 分母乘数，有时设置为0.6. 默认: 1

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算麦金利动态指标
        >>> mcgd_IndSeries = self.data.mcgd(length=10, c=1)
        >>> 
        >>> # 使用麦金利动态指标识别平滑趋势
        >>> def mcgd_smooth_trend(self):
        >>>     mcgd = self.data.mcgd(length=10)
        >>>     # 麦金利动态指标平滑跟随价格
        >>>     if abs(mcgd.new - self.data.close.new) / self.data.close.new < 0.01:
        >>>         return "麦金利紧密跟随价格"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def midpoint(self, length=2, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        中点指标 (Midpoint)
        ---------
            价格范围的中点。

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算价格中点
        >>> midpoint_IndSeries = self.data.midpoint(length=2)
        >>> 
        >>> # 使用中点作为参考水平
        >>> def midpoint_reference(self):
        >>>     midpoint = self.data.midpoint(length=2)
        >>>     return f"当前价格中点: {midpoint.new}"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def midprice(self, length=2, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        中间价格指标 (Midprice)
        ---------
            最高价和最低价的中间点。

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low

        使用案例:
        ---------
        >>> # 计算中间价格
        >>> midprice_IndSeries = self.data.midprice(length=2)
        >>> 
        >>> # 使用中间价格分析市场平衡点
        >>> def midprice_balance_point(self):
        >>>     midprice = self.data.midprice(length=2)
        >>>     # 收盘价接近中间价格 - 市场平衡
        >>>     if abs(self.data.close.new - midprice.new) / midprice.new < 0.005:
        >>>         return "市场处于平衡状态"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def ohlc4(self, offset=0, **kwargs) -> IndSeries:
        """
        OHLC4指标
        ---------
            开盘价、最高价、最低价和收盘价的平均值。

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> open, high, low, close

        使用案例:
        ---------
        >>> # 计算OHLC4
        >>> ohlc4_IndSeries = self.data.ohlc4()
        >>> 
        >>> # 使用OHLC4作为综合价格参考
        >>> def ohlc4_comprehensive_price(self):
        >>>     ohlc4 = self.data.ohlc4()
        >>>     return f"综合价格水平: {ohlc4.new}"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def pwma(self, length=10, asc=True, offset=0, **kwargs) -> IndSeries:
        """
        帕斯卡加权移动平均线 (Pascal's Weighted Moving Average, PWMA)
        ---------
            类似于对称三角窗口，但PWMA的权重基于帕斯卡三角形。

        数据来源:
        ---------
            Kevin Johnson

        计算方法:
        ---------
            def weights(w):
                def _compute(x):
                    return np.dot(w * x)
                return _compute
            triangle = utils.pascals_triangle(length + 1)
            PWMA = close.rolling(length)_.apply(weights(triangle), raw=True)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            asc (bool): 近期值权重更大. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算帕斯卡加权移动平均线
        >>> pwma_IndSeries = self.data.pwma(length=10)
        >>> 
        >>> # 使用PWMA作为平滑趋势线
        >>> def pwma_smooth_trend(self):
        >>>     pwma = self.data.pwma(length=10)
        >>>     # PWMA连续上升 - 稳定上升趋势
        >>>     if pwma.new > pwma.prev > pwma.sndprev:
        >>>         return "PWMA稳定上升趋势"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def ma(self, name: str = "sma", length: int = 10, **kwargs) -> IndSeries:
        """
        移动平均线工具函数 (MA Utility)
        ---------
            简化的移动平均线选择工具函数。

        可用移动平均线类型:
        >>> dema, ema, fwma, hma, linreg, midpoint, pwma, rma,
            sinwma, sma, swma, t3, tema, trima, vidya, wma, zlma

        参数:
        ---------
        >>> name (str): 移动平均线类型名称. 默认: "sma"
            length (int): 周期. 默认: 10

        可选参数:
        ---------
        >>> 所选移动平均线类型可能需要的任何额外参数

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 使用MA工具函数计算不同移动平均线
        >>> ema8 = self.data.ma("ema", length=8)
        >>> sma50 = self.data.ma("sma", length=50)
        >>> pwma10 = self.data.ma("pwma", length=10, asc=False)
        >>> 
        >>> # 多移动平均线策略
        >>> def multi_ma_strategy(self):
        >>>     ema_fast = self.data.ma("ema", length=10)
        >>>     ema_slow = self.data.ma("ema", length=20)
        >>>     sma_long = self.data.ma("sma", length=50)
        >>>     
        >>>     # 多移动平均线多头排列
        >>>     if (ema_fast.new > ema_slow.new > sma_long.new and
        >>>         ema_fast.prev <= ema_slow.prev <= sma_long.prev):
        >>>         return "多头排列形成"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def rma(self, length=10, offset=0, **kwargs) -> IndSeries:
        """
        怀尔德移动平均线 (wildeR's Moving Average, RMA)
        ---------
            简单来说就是修改了alpha = 1 / length的指数移动平均线(EMA)。

        数据来源:
        ---------
            https://tlc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/V-Z/WildersSmoothing
            https://www.incrediblecharts.com/indicators/wilder_moving_average.php

        计算方法:
        ---------
            EMA = Exponential Moving Average
            alpha = 1 / length
            RMA = EMA(close, alpha=alpha)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算怀尔德移动平均线
        >>> rma_IndSeries = self.data.rma(length=14)
        >>> 
        >>> # 使用RMA作为RSI计算的基础
        >>> def rsi_based_on_rma(self):
        >>>     rma = self.data.rma(length=14)
        >>>     # RMA通常用于RSI计算
        >>>     return "RMA常用于RSI指标计算"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def sinwma(self, length=10, offset=0, **kwargs) -> IndSeries:
        """
        正弦加权移动平均线 (Sine Weighted Moving Average, SWMA)
        ---------
            使用正弦周期的加权平均。平均值的中项具有最高的权重。

        数据来源:
        ---------
            https://www.tradingview.com/script/6MWFvnPO-Sine-Weighted-Moving-Average/
            作者: Everget (https://www.tradingview.com/u/everget/)

        计算方法:
        ---------
            def weights(w):
                def _compute(x):
                    return np.dot(w * x)
                return _compute
            sines = Series([sin((i + 1) * pi / (length + 1))
                           for i in range(0, length)])
            w = sines / sines.sum()
            SINWMA = close.rolling(length, min_periods=length).apply(
                weights(w), raw=True)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算正弦加权移动平均线
        >>> sinwma_IndSeries = self.data.sinwma(length=10)
        >>> 
        >>> # 使用正弦加权移动平均线
        >>> def sinwma_smooth_trend(self):
        >>>     sinwma = self.data.sinwma(length=10)
        >>>     # 正弦加权移动平均线提供平滑的趋势线
        >>>     return f"正弦加权移动平均: {sinwma.new}"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def sma(self, length=10, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        简单移动平均线 (Simple Moving Average, SMA)
        ---------
            经典的移动平均线，是n个周期内等权重的平均值。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/simple-moving-average-sma/

        计算方法:
        ---------
            SMA = SUM(close, length) / length

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> adjust (bool): 默认: True
            presma (bool, 可选): 如果为True，使用SMA作为初始值
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算简单移动平均线
        >>> sma_IndSeries = self.data.sma(length=20)
        >>> 
        >>> # 使用SMA识别基本趋势
        >>> def sma_basic_trend(self):
        >>>     sma = self.data.sma(length=20)
        >>>     # 价格在SMA上方 - 基本上升趋势
        >>>     if self.data.close.new > sma.new:
        >>>         return "价格在SMA上方，上升趋势"
        >>>     # 价格在SMA下方 - 基本下降趋势
        >>>     elif self.data.close.new < sma.new:
        >>>         return "价格在SMA下方，下降趋势"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def ssf(self, length=10, poles=2, offset=0, **kwargs) -> IndSeries:
        """
        埃勒超级平滑滤波器 (Ehler's Super Smoother Filter, SSF) © 2013
        ---------
            John F. Ehlers的解决方案，旨在减少延迟并消除航空航天模拟滤波器设计研究中的混叠噪声。

        数据来源:
        ---------
            http://www.stockspotter.com/files/PredictiveIndicators.pdf
            https://www.tradingview.com/script/VdJy0yBJ-Ehlers-Super-Smoother-Filter/
            https://www.mql5.com/en/code/588
            https://www.mql5.com/en/code/589

        计算方法:
        ---------
            参考源代码或上述数据来源

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            poles (int): 使用的极点数，2或3. 默认: 2
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算埃勒超级平滑滤波器
        >>> ssf_IndSeries = self.data.ssf(length=10, poles=2)
        >>> 
        >>> # 使用SSF进行噪声过滤
        >>> def ssf_noise_filtering(self):
        >>>     ssf = self.data.ssf(length=10, poles=2)
        >>>     # SSF提供平滑的价格序列
        >>>     return "SSF有效过滤市场噪声"
        """
        ...

    @tobtind(lines=['trend', 'dir', 'long', 'short'], overlap=True, lib='pta')
    def supertrend(self, length=7, multiplier=3., offset=0, **kwargs) -> IndFrame:
        """
        超级趋势指标 (Supertrend)
        ---------
            重叠指标。用于帮助识别趋势方向、设置止损、识别支撑和阻力、和/或生成买卖信号。

        数据来源:
        ---------
            http://www.freebsensetips.com/blog/detail/7/What-is-supertrend-indicator-its-calculation

        计算方法:
        ---------
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

        参数:
        ---------
        >>> length (int): ATR计算周期. 默认: 7
            multiplier (float): 上下带到中距离的系数. 默认: 3.0
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含trend、dir、long、short列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算超级趋势指标
        >>> supertrend_data = self.data.supertrend(length=7, multiplier=3)
        >>> trend, direction, long, short = supertrend_data.trend, supertrend_data.dir, supertrend_data.long, supertrend_data.short
        >>> 
        >>> # 使用超级趋势识别趋势方向
        >>> def supertrend_trend_direction(self):
        >>>     st = self.data.supertrend()
        >>>     # 趋势方向为1 - 上升趋势
        >>>     if st.dir.new == 1:
        >>>         return "超级趋势显示上升趋势"
        >>>     # 趋势方向为-1 - 下降趋势
        >>>     elif st.dir.new == -1:
        >>>         return "超级趋势显示下降趋势"
        >>> 
        >>> # 使用超级趋势生成交易信号
        >>> def supertrend_trading_signals(self):
        >>>     st = self.data.supertrend()
        >>>     # 趋势从下降转为上升 - 买入信号
        >>>     if st.dir.new == 1 and st.dir.prev == -1:
        >>>         self.data.buy()
        >>>     # 趋势从上升转为下降 - 卖出信号
        >>>     elif st.dir.new == -1 and st.dir.prev == 1:
        >>>         self.data.sell()
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def swma(self, length=10, asc=True, offset=0, **kwargs) -> IndSeries:
        """
        对称加权移动平均线 (Symmetric Weighted Moving Average, SWMA)
        ---------
            权重基于对称三角形的加权移动平均线。

        数据来源:
        ---------
            https://www.tradingview.com/study-script-reference/#fun_swma

        计算方法:
        ---------
            def weights(w):
                def _compute(x):
                    return np.dot(w * x)
                return _compute
            triangle = utils.symmetric_triangle(length - 1)
            SWMA = close.rolling(length)_.apply(weights(triangle), raw=True)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            asc (bool): 近期值权重更大. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算对称加权移动平均线
        >>> swma_IndSeries = self.data.swma(length=10)
        >>> 
        >>> # 使用SWMA作为趋势确认
        >>> def swma_trend_confirmation(self):
        >>>     swma = self.data.swma(length=10)
        >>>     # SWMA连续上升 - 确认上升趋势
        >>>     if swma.new > swma.prev > swma.sndprev:
        >>>         return "SWMA确认上升趋势"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def t3(self, length=10, a=0.7, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        蒂姆·蒂尔森T3移动平均线 (Tim Tillson's T3 Moving Average)
        ---------
            被认为相对于其他移动平均线更平滑且响应更快的移动平均线。

        数据来源:
        ---------
            http://www.binarytribune.com/forex-trading-indicators/t3-moving-average-indicator/

        计算方法:
        ---------
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

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            a (float): 0 < a < 1. 默认: 0.7
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> adjust (bool): 默认: True
            presma (bool, 可选): 如果为True，使用SMA作为初始值
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算T3移动平均线
        >>> t3_IndSeries = self.data.t3(length=10, a=0.7)
        >>> 
        >>> # 使用T3识别平滑趋势
        >>> def t3_smooth_trend(self):
        >>>     t3 = self.data.t3(length=10)
        >>>     # T3提供平滑且响应迅速的趋势线
        >>>     return "T3移动平均线平滑且响应迅速"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def tema(self, length=10, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        三重指数移动平均线 (Triple Exponential Moving Average, TEMA)
        ---------
            延迟较小的指数移动平均线。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/triple-exponential-moving-average-tema/

        计算方法:
        ---------
            EMA = Exponential Moving Average
            ema1 = EMA(close, length)
            ema2 = EMA(ema1, length)
            ema3 = EMA(ema2, length)
            TEMA = 3 * (ema1 - ema2) + ema3

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> adjust (bool): 默认: True
            presma (bool, 可选): 如果为True，使用SMA作为初始值
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算三重指数移动平均线
        >>> tema_IndSeries = self.data.tema(length=10)
        >>> 
        >>> # 使用TEMA减少延迟
        >>> def tema_low_lag(self):
        >>>     tema = self.data.tema(length=10)
        >>>     ema = self.data.ema(length=10)
        >>>     # TEMA比EMA响应更快
        >>>     return "TEMA比传统EMA延迟更小"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def trima(self, length=10, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        三角移动平均线 (Triangular Moving Average, TRIMA)
        ---------
            权重形状为三角形且最大权重在周期中间的加权移动平均线。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/triangular-moving-average-trima/

        计算方法:
        ---------
            SMA = Simple Moving Average
            half_length = round(0.5 * (length + 1))
            SMA1 = SMA(close, half_length)
            TRIMA = SMA(SMA1, half_length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> adjust (bool): 默认: True
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算三角移动平均线
        >>> trima_IndSeries = self.data.trima(length=10)
        >>> 
        >>> # 使用TRIMA作为平滑趋势线
        >>> def trima_smooth_trend(self):
        >>>     trima = self.data.trima(length=20)
        >>>     # TRIMA提供非常平滑的趋势线
        >>>     return "TRIMA提供平滑的趋势视图"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def vidya(self, length=14, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        可变指数动态平均线 (Variable Index Dynamic Average, VIDYA)
        ---------
            Tushar Chande开发。类似于指数移动平均线，但具有动态调整的回溯周期，
            依赖于通过钱德动量震荡指标(CMO)衡量的相对价格波动性。
            当波动性高时，VIDYA对价格变化反应更快。

        数据来源:
        ---------
            https://www.tradingview.com/script/hdrf0fXV-Variable-Index-Dynamic-Average-VIDYA/
            https://www.perfecttrendsystem.com/blog_mt4_2/en/vidya-indicator-for-mt4

        计算方法:
        ---------
            if sma:
                sma_nth = close[0:length].sum() / length
                close[:length - 1] = np.NaN
                close.iloc[length - 1] = sma_nth
            EMA = close.ewm(span=length, adjust=adjust).mean()

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> adjust (bool, 可选): 使用EMA计算的调整选项. 默认: False
            sma (bool, 可选): 如果为True，使用SMA作为EMA计算的初始值. 默认: True
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算可变指数动态平均线
        >>> vidya_IndSeries = self.data.vidya(length=14)
        >>> 
        >>> # 使用VIDYA适应市场波动性
        >>> def vidya_volatility_adaptive(self):
        >>>     vidya = self.data.vidya(length=14)
        >>>     # VIDYA在高波动市场中反应更快
        >>>     return "VIDYA根据波动性自动调整灵敏度"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def vwap(self, anchor="D", offset=0, **kwargs) -> IndSeries:
        """
        成交量加权平均价格 (Volume Weighted Average Price, VWAP)
        ---------
            通过成交量衡量的平均典型价格。
            通常与日内图表一起使用以识别总体方向。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Volume_Weighted_Average_Price_(VWAP)
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/volume-weighted-average-price-vwap/
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:vwap_intraday

        计算方法:
        ---------
            tp = typical_price = hlc3(high, low, close)
            tpv = tp * volume
            VWAP = tpv.cumsum() / volume.cumsum()

        参数:
        ---------
        >>> anchor (str): VWAP锚定方式。根据索引值，将实现各种时间序列偏移别名.
                    默认: "D" (日线)
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close, volume

        使用案例:
        ---------
        >>> # 计算VWAP
        >>> vwap_IndSeries = self.data.vwap(anchor="D")
        >>> 
        >>> # 使用VWAP识别日内趋势
        >>> def vwap_intraday_trend(self):
        >>>     vwap = self.data.vwap(anchor="D")
        >>>     # 价格在VWAP上方 - 日内偏强
        >>>     if self.data.close.new > vwap.new:
        >>>         return "价格在VWAP上方，日内偏强"
        >>>     # 价格在VWAP下方 - 日内偏弱
        >>>     elif self.data.close.new < vwap.new:
        >>>         return "价格在VWAP下方，日内偏弱"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def vwma(self, length=10, offset=0, **kwargs) -> IndSeries:
        """
        成交量加权移动平均线 (Volume Weighted Moving Average, VWMA)
        ---------
            成交量加权的移动平均线。

        数据来源:
        ---------
            https://www.motivewave.com/studies/volume_weighted_moving_average.htm

        计算方法:
        ---------
            SMA = Simple Moving Average
            pv = close * volume
            VWMA = SMA(pv, length) / SMA(volume, length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close, volume

        使用案例:
        ---------
        >>> # 计算成交量加权移动平均线
        >>> vwma_IndSeries = self.data.vwma(length=20)
        >>> 
        >>> # 使用VWMA确认成交量支撑
        >>> def vwma_volume_confirmation(self):
        >>>     vwma = self.data.vwma(length=20)
        >>>     # 价格上涨且成交量放大 - 量价配合良好
        >>>     if (self.data.close.new > vwma.new and 
        >>>         self.data.volume.new > self.data.volume.ema(period=20).new):
        >>>         return "量价配合良好，趋势健康"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def wcp(self, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        加权收盘价 (Weighted Closing Price, WCP)
        ---------
            给定最高价、最低价和双倍收盘价的加权价格。

        数据来源:
        ---------
            https://www.fmlabs.com/reference/default.htm?url=WeightedCloses.htm

        计算方法:
        ---------
            WCP = (2 * close + high + low) / 4

        参数:
        ---------
        >>> offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算加权收盘价
        >>> wcp_IndSeries = self.data.wcp()
        >>> 
        >>> # 使用WCP作为更准确的价格代表
        >>> def wcp_accurate_price(self):
        >>>     wcp = self.data.wcp()
        >>>     # WCP比简单收盘价更能代表当日交易区间
        >>>     return f"加权收盘价: {wcp.new}"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def wma(self, length=10, asc=True, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        加权移动平均线 (Weighted Moving Average, WMA)
        ---------
            权重线性增加且最新数据具有最大权重的加权移动平均线。

        数据来源:
        ---------
            https://en.wikipedia.org/wiki/Moving_average#Weighted_moving_average

        计算方法:
        ---------
            total_weight = 0.5 * length * (length + 1)
            weights_ = [1, 2, ..., length + 1]  # 升序
            weights = weights if asc else weights[::-1]
            def linear_weights(w):
                def _compute(x):
                    return (w * x).sum() / total_weight
                return _compute
            WMA = close.rolling(length)_.apply(linear_weights(weights), raw=True)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            asc (bool): 近期值权重更大. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算加权移动平均线
        >>> wma_IndSeries = self.data.wma(length=20)
        >>> 
        >>> # 使用WMA作为趋势确认
        >>> def wma_trend_confirmation(self):
        >>>     wma = self.data.wma(length=20)
        >>>     # WMA对近期价格更敏感
        >>>     if wma.new > wma.prev:
        >>>         return "WMA显示上升趋势"
        >>>     elif wma.new < wma.prev:
        >>>         return "WMA显示下降趋势"
        """
        ...

    @tobtind(lines=None, overlap=True, lib='pta')
    def zlma(self, length=10, mamode="ema", offset=0, **kwargs) -> IndSeries:
        """
        零延迟移动平均线 (Zero Lag Moving Average, ZLMA)
        ---------
            试图消除与移动平均线相关的延迟。
            这是由John Ehler和Ric Way创建的适应版本。

        数据来源:
        ---------
            https://en.wikipedia.org/wiki/Zero_lag_exponential_moving_average

        计算方法:
        ---------
            lag = int(0.5 * (length - 1))
            SOURCE = 2 * close - close.shift(lag)
            ZLMA = MA(kind=mamode, SOURCE, length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            mamode (str): 选项: 'ema', 'hma', 'sma', 'wma'. 默认: 'ema'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算零延迟移动平均线
        >>> zlma_IndSeries = self.data.zlma(length=10, mamode="ema")
        >>> 
        >>> # 使用ZLMA减少延迟
        >>> def zlma_low_lag(self):
        >>>     zlma = self.data.zlma(length=10)
        >>>     ema = self.data.ema(length=10)
        >>>     # ZLMA比传统EMA延迟更小
        >>>     return "ZLMA有效减少移动平均线延迟"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def log_return(self, length=20, cumulative=False, offset=0, **kwargs) -> IndSeries:
        """
        对数收益率 (Log Return)
        ---------
            计算序列的对数收益率。

        数据来源:
        ---------
            https://stackoverflow.com/questions/31287552/logarithmic-returns-in-pandas-IndFrame

        计算方法:
        ---------
            LOGRET = log( close.diff(periods=length) )
            CUMLOGRET = LOGRET.cumsum() if cumulative

        参数:
        ---------
        >>> length (int): 周期. 默认: 20
            cumulative (bool): 如果为True，返回累积收益率. 默认: False
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算对数收益率
        >>> log_return_IndSeries = self.data.log_return(length=1)
        >>> 
        >>> # 使用对数收益率分析价格变化
        >>> def log_return_analysis(self):
        >>>     log_ret = self.data.log_return(length=1)
        >>>     # 正对数收益率 - 价格上涨
        >>>     if log_ret.new > 0:
        >>>         return "正对数收益率，价格上涨"
        >>>     # 负对数收益率 - 价格下跌
        >>>     elif log_ret.new < 0:
        >>>         return "负对数收益率，价格下跌"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def percent_return(self, length=20, cumulative=False, offset=0, **kwargs) -> IndSeries:
        """
        百分比收益率 (Percent Return)
        ---------
            计算序列的百分比收益率。

        数据来源:
        ---------
            https://stackoverflow.com/questions/31287552/logarithmic-returns-in-pandas-IndFrame

        计算方法:
        ---------
            PCTRET = close.pct_change(length)
            CUMPCTRET = PCTRET.cumsum() if cumulative

        参数:
        ---------
        >>> length (int): 周期. 默认: 20
            cumulative (bool): 如果为True，返回累积收益率. 默认: False
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算百分比收益率
        >>> percent_return_IndSeries = self.data.percent_return(length=1)
        >>> 
        >>> # 使用百分比收益率评估投资表现
        >>> def investment_performance(self):
        >>>     pct_ret = self.data.percent_return(length=1)
        >>>     # 单日收益率超过5% - 大幅波动
        >>>     if abs(pct_ret.new) > 0.05:
        >>>         return "价格大幅波动"
        >>>     # 累积收益率分析
        >>>     cum_ret = self.data.percent_return(length=20, cumulative=True)
        >>>     if cum_ret.new > 0.1:
        >>>         return "20日累积收益率超过10%"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def entropy(self, length=10, base=2., offset=0, **kwargs) -> IndSeries:
        """
        信息熵 (Entropy)
        ---------
            Claude Shannon在1948年引入，熵衡量数据的不可预测性，
            或等效地，其平均信息量。

        数据来源:
        ---------
            https://en.wikipedia.org/wiki/Entropy_(information_theory)

        计算方法:
        ---------
            P = close / SUM(close, length)
            E = SUM(-P * npLog(P) / npLog(base), length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            base (float): 对数底数. 默认: 2
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算信息熵
        >>> entropy_IndSeries = self.data.entropy(length=10, base=2)
        >>> 
        >>> # 使用熵衡量市场不确定性
        >>> def market_uncertainty(self):
        >>>     entropy = self.data.entropy(length=10)
        >>>     # 高熵值 - 市场不确定性高
        >>>     if entropy.new > 0.8:
        >>>         return "市场不确定性较高"
        >>>     # 低熵值 - 市场趋势明确
        >>>     elif entropy.new < 0.3:
        >>>         return "市场趋势相对明确"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def kurtosis_(self, length=30, offset=0, **kwargs) -> IndSeries:
        """
        滚动峰度 (Rolling Kurtosis)
        ---------
            衡量价格分布尾部厚度的统计指标。

        计算方法:
        ---------
            KURTOSIS = close.rolling(length).kurt()

        参数:
        ---------
        >>> length (int): 周期. 默认: 30
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算滚动峰度
        >>> kurtosis_IndSeries = self.data.kurtosis_(length=30)
        >>> 
        >>> # 使用峰度识别极端价格行为
        >>> def extreme_price_behavior(self):
        >>>     kurtosis = self.data.kurtosis_(length=30)
        >>>     # 高峰度 - 厚尾分布，极端事件概率高
        >>>     if kurtosis.new > 3:
        >>>         return "高峰度，警惕极端价格波动"
        >>>     # 低峰度 - 薄尾分布，价格相对稳定
        >>>     elif kurtosis.new < 0:
        >>>         return "低峰度，价格分布相对稳定"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def mad(self, length=30, offset=0, **kwargs) -> IndSeries:
        """
        滚动平均绝对偏差 (Rolling Mean Absolute Deviation)
        ---------
            衡量价格相对于其移动平均线的平均偏离程度。

        计算方法:
        ---------
            mad = close.rolling(length).mad()

        参数:
        ---------
        >>> length (int): 周期. 默认: 30
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算平均绝对偏差
        >>> mad_IndSeries = self.data.mad(length=30)
        >>> 
        >>> # 使用MAD衡量价格波动性
        >>> def price_volatility_mad(self):
        >>>     mad = self.data.mad(length=30)
        >>>     # MAD值高 - 价格波动大
        >>>     if mad.new > mad.ema(period=20).new * 1.5:
        >>>         return "价格波动性较高"
        >>>     # MAD值低 - 价格相对稳定
        >>>     elif mad.new < mad.ema(period=20).new * 0.5:
        >>>         return "价格相对稳定"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def median(self, length=30, offset=0, **kwargs) -> IndSeries:
        """
        滚动中位数 (Rolling Median)
        ---------
            'n'个周期内的滚动中位数。简单移动平均线的兄弟指标。

        数据来源:
        ---------
            https://www.incrediblecharts.com/indicators/median_price.php

        计算方法:
        ---------
            MEDIAN = close.rolling(length).median()

        参数:
        ---------
        >>> length (int): 周期. 默认: 30
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算滚动中位数
        >>> median_IndSeries = self.data.median(length=30)
        >>> 
        >>> # 使用中位数识别价格中心趋势
        >>> def median_central_tendency(self):
        >>>     median = self.data.median(length=30)
        >>>     # 价格在中位数上方 - 偏强势
        >>>     if self.data.close.new > median.new:
        >>>         return "价格在中位数上方"
        >>>     # 价格在中位数下方 - 偏弱势
        >>>     elif self.data.close.new < median.new:
        >>>         return "价格在中位数下方"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def quantile_(self, length=30, q=0.5, offset=0, **kwargs) -> IndSeries:
        """
        滚动分位数 (Rolling Quantile)
        ---------
            计算价格在指定周期内的分位数水平。

        计算方法:
        ---------
            QUANTILE = close.rolling(length).quantile(q)

        参数:
        ---------
        >>> length (int): 周期. 默认: 30
            q (float): 分位数 (0到1之间). 默认: 0.5
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算不同分位数
        >>> quantile_50 = self.data.quantile_(length=30, q=0.5)  # 中位数
        >>> quantile_25 = self.data.quantile_(length=30, q=0.25) # 下四分位数
        >>> quantile_75 = self.data.quantile_(length=30, q=0.75) # 上四分位数
        >>> 
        >>> # 使用分位数识别价格位置
        >>> def price_position_analysis(self):
        >>>     q25 = self.data.quantile_(length=30, q=0.25)
        >>>     q75 = self.data.quantile_(length=30, q=0.75)
        >>>     # 价格在下四分位数以下 - 相对低位
        >>>     if self.data.close.new < q25.new:
        >>>         return "价格处于相对低位"
        >>>     # 价格在上四分位数以上 - 相对高位
        >>>     elif self.data.close.new > q75.new:
        >>>         return "价格处于相对高位"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def skew_(self, length=30, offset=0, **kwargs) -> IndSeries:
        """
        滚动偏度 (Rolling Skew)
        ---------
            衡量价格分布不对称性的统计指标。

        计算方法:
        ---------
            SKEW = close.rolling(length).skew()

        参数:
        ---------
        >>> length (int): 周期. 默认: 30
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算滚动偏度
        >>> skew_IndSeries = self.data.skew_(length=30)
        >>> 
        >>> # 使用偏度分析价格分布特征
        >>> def price_distribution_skew(self):
        >>>     skew = self.data.skew_(length=30)
        >>>     # 正偏度 - 右偏分布，极端高价可能性更高
        >>>     if skew.new > 0.5:
        >>>         return "价格分布右偏，警惕极端高价"
        >>>     # 负偏度 - 左偏分布，极端低价可能性更高
        >>>     elif skew.new < -0.5:
        >>>         return "价格分布左偏，警惕极端低价"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def stdev(self, length=30, ddof=1, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        滚动标准差 (Rolling Standard Deviation)
        ---------
            衡量价格波动性的常用统计指标。

        计算方法:
        ---------
            VAR = Variance
            STDEV = variance(close, length).apply(np.sqrt)

        参数:
        ---------
        >>> length (int): 周期. 默认: 30
            ddof (int): 自由度差值。计算中使用的除数是N - ddof，
                        其中N表示元素数量. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算滚动标准差
        >>> stdev_IndSeries = self.data.stdev(length=30)
        >>> 
        >>> # 使用标准差衡量波动性
        >>> def volatility_measurement(self):
        >>>     stdev = self.data.stdev(length=30)
        >>>     # 标准差突增 - 波动性增加
        >>>     if stdev.new > stdev.ema(period=20).new * 1.5:
        >>>         return "市场波动性显著增加"
        >>>     # 标准差较低 - 市场平静
        >>>     elif stdev.new < stdev.ema(period=20).new * 0.7:
        >>>         return "市场波动性较低"
        """
        ...

    @tobtind(lines=['toslr', 'tosl1', 'tosu1', 'tosl2', 'tosu2', 'tosl3', 'tosu3'], lib='pta')
    def tos_stdevall(self, length=30, stds=[1, 2, 3], ddof=1, offset=0, **kwargs) -> IndFrame:
        """
        TD Ameritrade Think or Swim 全标准差通道 (TOS_STDEV)
        ---------
            TD Ameritrade Think or Swim 全标准差指标的重现，
            返回整个图表数据的标准差或由长度参数定义的最近柱线区间的标准差。

        数据来源:
        ---------
            https://tlc.thinkorswim.com/center/reference/thinkScript/Functions/Statistical/StDevAll

        计算方法:
        ---------
            LR = Linear Regression
            STDEV = Standard Deviation
            LR = LR(close, length)
            STDEV = STDEV(close, length, ddof)
            for level in stds:
                LOWER = LR - level * STDEV
                UPPER = LR + level * STDEV

        参数:
        ---------
        >>> length (int): 从当前柱线开始的柱线数. 默认: 30
            stds (list): 标准差倍数列表，从中心线性回归线开始递增. 默认: [1,2,3]
            ddof (int): 自由度差值。计算中使用的除数是N - ddof，
                        其中N表示元素数量. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含toslr、tosl1、tosu1、tosl2、tosu2、tosl3、tosu3列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算TOS标准差通道
        >>> tos_data = self.data.tos_stdevall(length=30, stds=[1, 2, 3])
        >>> lr, lower1, upper1, lower2, upper2, lower3, upper3 = tos_data.toslr, tos_data.tosl1, tos_data.tosu1, tos_data.tosl2, tos_data.tosu2, tos_data.tosl3, tos_data.tosu3
        >>> 
        >>> # 使用TOS通道识别价格位置
        >>> def tos_channel_analysis(self):
        >>>     tos = self.data.tos_stdevall(length=30)
        >>>     # 价格在2倍标准差上方 - 极端高位
        >>>     if self.data.close.new > tos.tosu2.new:
        >>>         return "价格在2倍标准差上方，极端高位"
        >>>     # 价格在2倍标准差下方 - 极端低位
        >>>     elif self.data.close.new < tos.tosl2.new:
        >>>         return "价格在2倍标准差下方，极端低位"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def variance(self, length=30, ddof=1, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        滚动方差 (Rolling Variance)
        ---------
            衡量价格离散程度的统计指标。

        计算方法:
        ---------
            VARIANCE = close.rolling(length).var()

        参数:
        ---------
        >>> length (int): 周期. 默认: 30
            ddof (int): 自由度差值。计算中使用的除数是N - ddof，
                        其中N表示元素数量. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算滚动方差
        >>> variance_IndSeries = self.data.variance(length=30)
        >>> 
        >>> # 使用方差分析价格离散程度
        >>> def price_dispersion(self):
        >>>     variance = self.data.variance(length=30)
        >>>     # 高方差 - 价格离散度高，波动大
        >>>     if variance.new > variance.ema(period=20).new * 2:
        >>>         return "价格离散度高，市场不稳定"
        >>>     # 低方差 - 价格聚集度高，市场稳定
        >>>     elif variance.new < variance.ema(period=20).new * 0.5:
        >>>         return "价格聚集度高，市场相对稳定"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def zscore(self, length=30, std=1., offset=0, **kwargs) -> IndSeries:
        """
        Z分数标准化 (Rolling Z Score)
        ---------
            衡量价格相对于其移动平均线的标准差位置。

        计算方法:
        ---------
            SMA = Simple Moving Average
            STDEV = Standard Deviation
            std = std * STDEV(close, length)
            mean = SMA(close, length)
            ZSCORE = (close - mean) / std

        参数:
        ---------
        >>> length (int): 周期. 默认: 30
            std (float): 标准差倍数. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算Z分数
        >>> zscore_IndSeries = self.data.zscore(length=30, std=1)
        >>> 
        >>> # 使用Z分数识别异常价格
        >>> def zscore_anomaly_detection(self):
        >>>     zscore = self.data.zscore(length=30)
        >>>     # Z分数 > 2 - 价格异常偏高
        >>>     if zscore.new > 2:
        >>>         return "Z分数显示价格异常偏高"
        >>>     # Z分数 < -2 - 价格异常偏低
        >>>     elif zscore.new < -2:
        >>>         return "Z分数显示价格异常偏低"
        """
        ...

    @tobtind(lines=['adxx', 'dmp', 'dmn'], lib='pta')
    def adx(self, length=14, lensig=14, scalar=100, mamode="rma", drift=1, offset=0, **kwargs) -> IndFrame:
        """
        平均趋向指数 (Average Directional Movement, ADX)
        ---------
            旨在通过测量单一方向的移动量来量化趋势强度。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/average-directional-movement-adx/
            TA Lib 相关性: >99%

        计算方法:
        ---------
            参考源代码实现

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            lensig (int): 信号长度。类似于TradingView的默认ADX. 默认: length
            scalar (float): 放大倍数. 默认: 100
            mamode (str): 移动平均模式，参考```help(ta.ma)```. 默认: 'rma'
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含adxx、dmp、dmn列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算ADX指标
        >>> adx_data = self.data.adx(length=14, lensig=14)
        >>> adx, plus_di, minus_di = adx_data.adxx, adx_data.dmp, adx_data.dmn
        >>> 
        >>> # 使用ADX判断趋势强度
        >>> def adx_trend_strength(self):
        >>>     adx = self.data.adx()
        >>>     # ADX > 25 - 趋势强劲
        >>>     if adx.adxx.new > 25:
        >>>         return "ADX显示趋势强劲"
        >>>     # ADX < 20 - 趋势疲弱或震荡
        >>>     elif adx.adxx.new < 20:
        >>>         return "ADX显示趋势疲弱或震荡"
        >>> 
        >>> # 使用+DI和-DI判断趋势方向
        >>> def di_trend_direction(self):
        >>>     adx = self.data.adx()
        >>>     # +DI > -DI - 上升趋势占主导
        >>>     if adx.dmp.new > adx.dmn.new:
        >>>         return "+DI > -DI，上升趋势"
        >>>     # -DI > +DI - 下降趋势占主导
        >>>     elif adx.dmn.new > adx.dmp.new:
        >>>         return "-DI > +DI，下降趋势"
        """
        ...

    @tobtind(lines=['amatl', 'amats'], lib='pta')
    def amat(self, fast=8, slow=21, lookback=2, mamode="ema", offset=0, **kwargs) -> IndFrame:
        """
        阿彻移动平均趋势 (Archer Moving Averages Trends, AMAT)
        ---------
            基于移动平均线的趋势识别指标。

        返回:
        ---------
        >>> IndFrame: 包含amatl、amats列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        >>> # 计算AMAT指标
        >>> amat_data = self.data.amat(fast=8, slow=21, lookback=2)
        >>> amat_long, amat_short = amat_data.amatl, amat_data.amats
        >>> 
        >>> # 使用AMAT识别趋势转换
        >>> def amat_trend_signals(self):
        >>>     amat = self.data.amat()
        >>>     # 长期信号转正 - 长期看涨
        >>>     if amat.amatl.new == 1 and amat.amatl.prev == 0:
        >>>         return "AMAT长期看涨信号"
        >>>     # 短期信号转正 - 短期看涨
        >>>     if amat.amats.new == 1 and amat.amats.prev == 0:
        >>>         return "AMAT短期看涨信号"
        """
        ...

    @tobtind(lines=['aroon_up', 'aroon_down', 'aroon_osc'], lib='pta')
    def aroon(self, length=14, scalar=100, talib=True, offset=0, **kwargs) -> IndFrame:
        """
        阿隆指标和震荡器 (Aroon & Aroon Oscillator)
        ---------
            试图识别证券是否处于趋势中以及趋势强度。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Aroon
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/aroon-ar/

        计算方法:
        ---------
            recent_maximum_index(x): return int(np.argmax(x[::-1]))
            recent_minimum_index(x): return int(np.argmin(x[::-1]))
            periods_from_hh = high.rolling(length + 1).apply(recent_maximum_index, raw=True)
            AROON_UP = scalar * (1 - (periods_from_hh / length))
            periods_from_ll = low.rolling(length + 1).apply(recent_minimum_index, raw=True)
            AROON_DN = scalar * (1 - (periods_from_ll / length))
            AROON_OSC = AROON_UP - AROON_DN

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            scalar (float): 放大倍数. 默认: 100
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含aroon_up、aroon_down、aroon_osc列的数据框

        所需数据字段:
        ---------
        >>> high, low

        使用案例:
        ---------
        >>> # 计算阿隆指标
        >>> aroon_data = self.data.aroon(length=14)
        >>> aroon_up, aroon_down, aroon_osc = aroon_data.aroon_up, aroon_data.aroon_down, aroon_data.aroon_osc
        >>> 
        >>> # 使用阿隆指标识别趋势强度
        >>> def aroon_trend_strength(self):
        >>>     aroon = self.data.aroon(length=14)
        >>>     # 阿隆上线 > 70 且 阿隆下线 < 30 - 强烈上升趋势
        >>>     if aroon.aroon_up.new > 70 and aroon.aroon_down.new < 30:
        >>>         return "阿隆指标显示强烈上升趋势"
        >>>     # 阿隆下线 > 70 且 阿隆上线 < 30 - 强烈下降趋势
        >>>     elif aroon.aroon_down.new > 70 and aroon.aroon_up.new < 30:
        >>>         return "阿隆指标显示强烈下降趋势"
        >>> 
        >>> # 使用阿隆震荡器
        >>> def aroon_oscillator_signals(self):
        >>>     aroon = self.data.aroon(length=14)
        >>>     # 阿隆震荡器上穿零轴 - 买入信号
        >>>     if aroon.aroon_osc.new > 0 and aroon.aroon_osc.prev <= 0:
        >>>         return "阿隆震荡器买入信号"
        >>>     # 阿隆震荡器下穿零轴 - 卖出信号
        >>>     elif aroon.aroon_osc.new < 0 and aroon.aroon_osc.prev >= 0:
        >>>         return "阿隆震荡器卖出信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def chop(self, length=14, atr_length=1., ln=False, scalar=100, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        震荡指数 (Choppiness Index, CHOP)
        ---------
            澳大利亚商品交易员E.W. Dreiss创建，旨在确定市场是否处于震荡状态
            （横盘交易）或非震荡状态（在任一方向的趋势内交易）。
            值接近100表示标的更震荡，值接近0表示标的处于趋势中。

        数据来源:
        ---------
            https://www.tradingview.com/scripts/choppinessindex/
            https://www.motivewave.com/studies/choppiness_index.htm

        计算方法:
        ---------
            HH = high.rolling(length).max()
            LL = low.rolling(length).min()
            ATR_SUM = SUM(ATR(drift), length)
            CHOP = scalar * (LOG10(ATR_SUM) - LOG10(HH - LL))
            CHOP /= LOG10(length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            atr_length (int): ATR长度. 默认: 1
            ln (bool): 如果为True，使用ln否则使用log10. 默认: False
            scalar (float): 放大倍数. 默认: 100
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算震荡指数
        >>> chop_IndSeries = self.data.chop(length=14)
        >>> 
        >>> # 使用震荡指数识别市场状态
        >>> def market_choppiness_analysis(self):
        >>>     chop = self.data.chop(length=14)
        >>>     # CHOP > 61.8 - 市场震荡，避免趋势策略
        >>>     if chop.new > 61.8:
        >>>         return "市场高度震荡，适合震荡策略"
        >>>     # CHOP < 38.2 - 市场趋势明显，适合趋势策略
        >>>     elif chop.new < 38.2:
        >>>         return "市场趋势明显，适合趋势策略"
        """
        ...

    @tobtind(lines=['cksp_long', 'cksp_short'], lib='pta')
    def cksp(self, p=10, x=3, q=20, tvmode=True, offset=0, **kwargs) -> IndFrame:
        """
        钱德-克罗尔止损 (Chande Kroll Stop, CKSP)
        ---------
            Tushar Chande和Stanley Kroll在他们的著作"The New Technical Trader"中提出。
            这是一个趋势跟踪指标，通过计算最近市场波动性的平均真实波幅来识别止损位。

        数据来源:
        ---------
            https://www.multicharts.com/discussion/viewtopic.php?t=48914
            "The New Technical Trader", Wikey 1st ed. ISBN 9780471597803, page 95

        计算方法:
        ---------
            ATR = Average True Range
            LS0 = high.rolling(p).max() - x * ATR(length=p)
            LS = LS0.rolling(q).max()
            SS0 = high.rolling(p).min() + x * ATR(length=p)
            SS = SS0.rolling(q).min()

        参数:
        ---------
        >>> p (int): ATR和第一个止损周期. 默认: 10
            x (float): ATR乘数. 默认: TV模式为1，否则为3
            q (int): 第二个止损周期. 默认: TV模式为9，否则为20
            tvmode (bool): Trading View或书籍实现模式. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含cksp_long和cksp_short列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算钱德-克罗尔止损
        >>> cksp_data = self.data.cksp(p=10, x=3, q=20)
        >>> cksp_long, cksp_short = cksp_data.cksp_long, cksp_data.cksp_short
        >>> 
        >>> # 使用CKSP设置动态止损
        >>> def cksp_stop_loss(self):
        >>>     cksp = self.data.cksp()
        >>>     # 多头头寸使用多头止损位
        >>>     if self.position.is_long:
        >>>         stop_loss = cksp.cksp_long.new
        >>>         return f"多头止损位: {stop_loss}"
        >>>     # 空头头寸使用空头止损位
        >>>     elif self.position.is_short:
        >>>         stop_loss = cksp.cksp_short.new
        >>>         return f"空头止损位: {stop_loss}"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def decay(self, kind="exponential", length=5, mode="linear", offset=0, **kwargs) -> IndSeries:
        """
        衰减指标 (Decay)
        ---------
            从先前的信号（如交叉）向前创建衰减。默认为"线性"。
            指数衰减可选为"exponential"或"exp"。

        数据来源:
        ---------
            https://tulipindicators.org/decay

        计算方法:
        ---------
            if mode == "exponential" or mode == "exp":
                max(close, close[-1] - exp(-length), 0)
            else:
                max(close, close[-1] - (1 / length), 0)

        参数:
        ---------
        >>> length (int): 周期. 默认: 5
            mode (str): 如果为'exp'则为"指数"衰减. 默认: 'linear'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算衰减指标
        >>> decay_IndSeries = self.data.decay(length=5, mode="linear")
        >>> 
        >>> # 使用衰减指标平滑信号
        >>> def decay_signal_smoothing(self):
        >>>     decay = self.data.decay(length=5, mode="exponential")
        >>>     # 衰减指标可用于平滑交易信号
        >>>     return "衰减指标帮助平滑信号波动"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def decreasing(self, length=1, strict=False, asint=True, percent=None, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        下降序列检测 (Decreasing)
        ---------
            如果序列在一个周期内下降，返回True，否则返回False。
            如果strict为True，则检查序列是否在该周期内持续下降。

        计算方法:
        ---------
            if strict:
                decreasing = all(i > j for i, j in zip(close[-length:], close[1:]))
            else:
                decreasing = close.diff(length) < 0
            if asint:
                decreasing = decreasing.astype(int)

        参数:
        ---------
        >>> length (int): 周期. 默认: 1
            strict (bool): 如果为True，检查序列是否在该周期内持续下降. 默认: False
            percent (float): 百分比作为整数. 默认: None
            asint (bool): 返回二进制值. 默认: True
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 检测下降序列
        >>> decreasing_IndSeries = self.data.decreasing(length=3, strict=True)
        >>> 
        >>> # 使用下降检测识别趋势
        >>> def decreasing_trend_detection(self):
        >>>     decreasing = self.data.decreasing(length=3, strict=True)
        >>>     # 连续3日严格下降 - 强烈下降趋势
        >>>     if decreasing.new == 1:
        >>>         return "检测到连续下降趋势"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def dpo(self, length=20, centered=True, offset=0, **kwargs) -> IndSeries:
        """
        去趋势价格震荡指标 (Detrend Price Oscillator, DPO)
        ---------
            旨在从价格中去除趋势，使其更容易识别周期。

        数据来源:
        ---------
            https://www.tradingview.com/scripts/detrendedpriceoscillator/
            https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/dpo
            http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:detrended_price_osci

        计算方法:
        ---------
            SMA = Simple Moving Average
            t = int(0.5 * length) + 1
            DPO = close.shift(t) - SMA(close, length)
            if centered:
                DPO = DPO.shift(-t)

        参数:
        ---------
        >>> length (int): 周期. 默认: 20
            centered (bool): 将dpo向后移动int(0.5 * length) + 1. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算去趋势价格震荡指标
        >>> dpo_IndSeries = self.data.dpo(length=20, centered=True)
        >>> 
        >>> # 使用DPO识别周期波动
        >>> def dpo_cycle_analysis(self):
        >>>     dpo = self.data.dpo(length=20)
        >>>     # DPO上穿零轴 - 周期上升阶段
        >>>     if dpo.new > 0 and dpo.prev <= 0:
        >>>         return "DPO显示周期上升阶段"
        >>>     # DPO下穿零轴 - 周期下降阶段
        >>>     elif dpo.new < 0 and dpo.prev >= 0:
        >>>         return "DPO显示周期下降阶段"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def increasing(self, length=1, strict=False, asint=True, percent=None, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        上升序列检测 (Increasing)
        ---------
            如果序列在一个周期内上升，返回True，否则返回False。
            如果strict为True，则检查序列是否在该周期内持续上升。

        计算方法:
        ---------
            if strict:
                increasing = all(i < j for i, j in zip(close[-length:], close[1:]))
            else:
                increasing = close.diff(length) > 0
            if asint:
                increasing = increasing.astype(int)

        参数:
        ---------
        >>> length (int): 周期. 默认: 1
            strict (bool): 如果为True，检查序列是否在该周期内持续上升. 默认: False
            percent (float): 百分比作为整数. 默认: None
            asint (bool): 返回二进制值. 默认: True
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 检测上升序列
        >>> increasing_IndSeries = self.data.increasing(length=3, strict=True)
        >>> 
        >>> # 使用上升检测识别趋势
        >>> def increasing_trend_detection(self):
        >>>     increasing = self.data.increasing(length=3, strict=True)
        >>>     # 连续3日严格上升 - 强烈上升趋势
        >>>     if increasing.new == 1:
        >>>         return "检测到连续上升趋势"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def long_run(self, fast=None, slow=None, length=2, offset=0, **kwargs) -> IndSeries:
        """
        长期运行指标 (Long Run)
        ---------
            长期趋势识别指标。

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        使用案例:
        >>> # 计算长期运行指标
        >>> long_run_IndSeries = self.data.long_run(length=2)
        >>> 
        >>> # 使用长期运行指标
        >>> def long_run_trend(self):
        >>>     long_run = self.data.long_run(length=2)
        >>>     return f"长期运行指标: {long_run.new}"
        """
        ...

    @tobtind(lines=['psarl', 'psars', 'psaraf', 'psarr'], lib='pta')
    def psar(self, af0=0.02, af=0.02, max_af=0.2, offset=0, **kwargs) -> IndFrame:
        """
        抛物线转向指标 (Parabolic Stop and Reverse, PSAR)
        ---------
            J. Wells Wilder开发，用于确定趋势方向及其潜在的价格反转。
            PSAR使用称为"SAR"的跟踪止损和反转方法来识别可能的入场和出场点。

        数据来源:
        ---------
            https://www.tradingview.com/pine-script-reference/#fun_sar
            https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=66&Name=Parabolic

        计算方法:
        ---------
            参考源代码实现

        参数:
        ---------
        >>> af0 (float): 初始加速因子. 默认: 0.02
            af (float): 加速因子. 默认: 0.02
            max_af (float): 最大加速因子. 默认: 0.2
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含psarl、psars、psaraf、psarr列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算抛物线转向指标
        >>> psar_data = self.data.psar(af0=0.02, af=0.02, max_af=0.2)
        >>> psar_long, psar_short, psar_af, psar_reversal = psar_data.psarl, psar_data.psars, psar_data.psaraf, psar_data.psarr
        >>> 
        >>> # 使用PSAR识别趋势反转
        >>> def psar_trend_reversal(self):
        >>>     psar = self.data.psar()
        >>>     # PSAR点从价格下方转到上方 - 趋势反转卖出信号
        >>>     if psar.psarr.new == 1:
        >>>         return "PSAR趋势反转信号"
        >>> 
        >>> # 使用PSAR作为动态止损
        >>> def psar_stop_loss(self):
        >>>     psar = self.data.psar()
        >>>     # 多头头寸使用PSAR多头止损
        >>>     if self.position.is_long:
        >>>         stop_loss = psar.psarl.new
        >>>         return f"PSAR多头止损: {stop_loss}"
        >>>     # 空头头寸使用PSAR空头止损
        >>>     elif self.position.is_short:
        >>>         stop_loss = psar.psars.new
        >>>         return f"PSAR空头止损: {stop_loss}"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def qstick(self, length=10, ma="sma", offset=0, **kwargs) -> IndSeries:
        """
        Q棒指标 (Q Stick)
        ---------
            Tushar Chande开发，试图量化和识别蜡烛图中的趋势。

        数据来源:
        ---------
            https://library.tradingtechnologies.com/trade/chrt-ti-qstick.html

        计算方法:
        ---------
            xMA是其中之一: sma (默认), dema, ema, hma, rma
            qstick = xMA(close - open, length)

        参数:
        ---------
        >>> length (int): 周期. 默认: 10
            ma (str): 使用的移动平均线类型. 默认: 'sma'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> open, close

        使用案例:
        ---------
        >>> # 计算Q棒指标
        >>> qstick_IndSeries = self.data.qstick(length=10, ma="sma")
        >>> 
        >>> # 使用Q棒指标识别买卖压力
        >>> def qstick_pressure_analysis(self):
        >>>     qstick = self.data.qstick(length=10)
        >>>     # Q棒 > 0 - 买方压力占主导
        >>>     if qstick.new > 0:
        >>>         return "Q棒显示买方压力"
        >>>     # Q棒 < 0 - 卖方压力占主导
        >>>     elif qstick.new < 0:
        >>>         return "Q棒显示卖方压力"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def short_run(self, fast=None, slow=None, length=None, offset=0, **kwargs) -> IndSeries:
        """
        短期运行指标 (Short Run)
        ---------
            短期趋势识别指标。

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        使用案例:
        >>> # 计算短期运行指标
        >>> short_run_IndSeries = self.data.short_run()
        >>> 
        >>> # 使用短期运行指标
        >>> def short_run_trend(self):
        >>>     short_run = self.data.short_run()
        >>>     return f"短期运行指标: {short_run.new}"
        """
        ...

    @tobtind(lines=['ts_trends', 'ts_trades', 'ts_entries', 'ts_exits'], lib='pta')
    def tsignals(self, trend=None, asbool=None, trend_reset=None, trend_offset=0,
                 offset=0, **kwargs) -> IndFrame:
        """
        趋势信号 (Trend Signals)
        ---------
            给定一个趋势，趋势信号返回趋势、交易、入场和出场作为布尔整数。

        数据来源:
        ---------
            Kevin Johnson

        计算方法:
        ---------
            trades = trends.diff().shift(trade_offset).fillna(0).astype(int)
            entries = (trades > 0).astype(int)
            exits = (trades < 0).abs().astype(int)

        参数:
        ---------
        >>> trend (pd.Series): 趋势序列。趋势可以是布尔值或0和1的整数序列
            asbool (bool): 如果为True，将趋势、入场和出场列转换为布尔值. 默认: False
            trend_reset (value): 用于识别趋势是否已结束的值. 默认: 0
            trend_offset (int): 用于移动交易入场/出场的值。回测使用1，实盘使用0. 默认: 0
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含ts_trends、ts_trades、ts_entries、ts_exits列的数据框

        使用案例:
        ---------
        >>> # 使用趋势信号
        >>> # 当收盘价大于50日移动平均线时生成信号
        >>> trend_condition = self.data.close > self.data.sma(length=50)
        >>> signals = self.data.tsignals(trend=trend_condition, asbool=False)
        >>> 
        >>> # 获取交易信号
        >>> def get_trading_signals(self):
        >>>     trend = self.data.ema(length=8) > self.data.ema(length=21)
        >>>     signals = self.data.tsignals(trend=trend, asbool=True)
        >>>     # 入场信号
        >>>     if signals.ts_entries.new:
        >>>         self.data.buy()
        >>>     # 出场信号
        >>>     elif signals.ts_exits.new:
        >>>         self.data.sell()
        """
        ...

    @tobtind(lines=['ttm_trend',], lib='pta')
    def ttm_trend(self, length=6, offset=0, **kwargs) -> IndFrame:
        """
        TTM趋势指标 (TTM Trend)
        ---------
            来自John Carter的著作"Mastering the Trade"，将柱状图绘制为绿色或红色。
            检查价格是否高于或低于前5根柱的平均价格。

        数据来源:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/ttm-trend-price/

        计算方法:
        ---------
            averageprice = (((high[5]+low[5])/2)+((high[4]+low[4])/2)+((high[3]+low[3])/2)+(
                (high[2]+low[2])/2)+((high[1]+low[1])/2)+((high[6]+low[6])/2)) / 6
            if close > averageprice:
                drawcandle(open,high,low,close) coloured(0,255,0)
            if close < averageprice:
                drawcandle(open,high,low,close) coloured(255,0,0)

        参数:
        ---------
        >>> length (int): 周期. 默认: 6
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含ttm_trend列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算TTM趋势指标
        >>> ttm_trend_data = self.data.ttm_trend(length=6)
        >>> 
        >>> # 使用TTM趋势识别颜色变化
        >>> def ttm_trend_color_change(self):
        >>>     ttm = self.data.ttm_trend(length=6)
        >>>     # 趋势从红色转为绿色 - 买入信号
        >>>     if ttm.ttm_trend.new == 1 and ttm.ttm_trend.prev == 0:
        >>>         return "TTM趋势转为绿色，买入信号"
        >>>     # 趋势从绿色转为红色 - 卖出信号
        >>>     elif ttm.ttm_trend.new == 0 and ttm.ttm_trend.prev == 1:
        >>>         return "TTM趋势转为红色，卖出信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def vhf(self, length=28, drift=None, offset=0, **kwargs) -> IndSeries:
        """
        垂直水平过滤器 (Vertical Horizontal Filter, VHF)
        ---------
            Adam White创建，用于识别趋势市场和震荡市场。

        数据来源:
        ---------
            https://www.incrediblecharts.com/indicators/vertical_horizontal_filter.php

        计算方法:
        ---------
            HCP = Highest Close Price in Period
            LCP = Lowest Close Price in Period
            Change = abs(Ct - Ct-1)
            VHF = (HCP - LCP) / RollingSum[length] of Change

        参数:
        ---------
        >>> length (int): 周期长度. 默认: 28
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算垂直水平过滤器
        >>> vhf_IndSeries = self.data.vhf(length=28)
        >>> 
        >>> # 使用VHF识别市场状态
        >>> def vhf_market_state(self):
        >>>     vhf = self.data.vhf(length=28)
        >>>     # VHF > 0.4 - 趋势市场
        >>>     if vhf.new > 0.4:
        >>>         return "VHF显示趋势市场"
        >>>     # VHF < 0.2 - 震荡市场
        >>>     elif vhf.new < 0.2:
        >>>         return "VHF显示震荡市场"
        """
        ...

    @tobtind(lines=['vip', 'vim'], lib='pta')
    def vortex(self, length=14, drift=1, offset=0, **kwargs) -> IndFrame:
        """
        涡旋指标 (Vortex)
        ---------
            两个捕捉正负趋势运动的震荡器。

        数据来源:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:vortex_indicator

        计算方法:
        ---------
            TR = True Range
            SMA = Simple Moving Average
            tr = TR(high, low, close)
            tr_sum = tr.rolling(length).sum()
            vmp = (high - low.shift(drift)).abs()
            vmn = (low - high.shift(drift)).abs()
            VIP = vmp.rolling(length).sum() / tr_sum
            VIM = vmn.rolling(length).sum() / tr_sum

        参数:
        ---------
        >>> length (int): 周期. 默认: 14
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含vip和vim列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算涡旋指标
        >>> vortex_data = self.data.vortex(length=14)
        >>> vip, vim = vortex_data.vip, vortex_data.vim
        >>> 
        >>> # 使用涡旋指标识别趋势
        >>> def vortex_trend_direction(self):
        >>>     vortex = self.data.vortex(length=14)
        >>>     # VIP > VIM - 上升趋势
        >>>     if vortex.vip.new > vortex.vim.new:
        >>>         return "涡旋指标显示上升趋势"
        >>>     # VIM > VIP - 下降趋势
        >>>     elif vortex.vim.new > vortex.vip.new:
        >>>         return "涡旋指标显示下降趋势"
        """
        ...

    @tobtind(lines=['xs_long', 'xs_short'], lib='pta')
    def xsignals(self, signal=None, xa=None, xb=None, above=None, long=None, asbool=None, trend_reset=None,
                 trend_offset=0, offset=0, **kwargs) -> IndFrame:
        """
        交叉信号 (Cross Signals, XSIGNALS)
        ---------
            为信号交叉返回趋势信号(TSIGNALS)结果。

        数据来源:
        ---------
            Kevin Johnson

        计算方法:
        ---------
            trades = trends.diff().shift(trade_offset).fillna(0).astype(int)
            entries = (trades > 0).astype(int)
            exits = (trades < 0).abs().astype(int)

        参数:
        ---------
        >>> signal (pd.Series): 信号序列
            xa (float): 第一个交叉阈值
            xb (float): 第二个交叉阈值
            above (bool): 当信号首先上穿'xa'然后下穿'xb'时。如果为False，则当信号首先下穿'xa'然后上穿'xb'时. 默认: True
            long (bool): 将多头趋势传递给tsignals的趋势参数。如果为False，则将空头趋势传递给tsignals的趋势参数. 默认: True
            asbool (bool): 如果为True，将趋势、入场和出场列转换为布尔值. 默认: False
            trend_reset (value): 用于识别趋势是否已结束的值. 默认: 0
            trend_offset (int): 用于移动交易入场/出场的值. 默认: 0
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含xs_long、xs_short列的数据框

        使用案例:
        ---------
        >>> # 使用交叉信号
        >>> rsi = self.data.rsi(length=14)
        >>> # 当RSI上穿20然后下穿80时返回信号
        >>> signals1 = self.data.xsignals(signal=rsi, xa=20, xb=80, above=True)
        >>> # 当RSI下穿20然后上穿80时返回信号
        >>> signals2 = self.data.xsignals(signal=rsi, xa=20, xb=80, above=False)
        >>> 
        >>> # 使用交叉信号进行交易
        >>> def cross_signal_trading(self):
        >>>     rsi = self.data.rsi(length=14)
        >>>     signals = self.data.xsignals(signal=rsi, xa=30, xb=70, above=True)
        >>>     # 多头入场信号
        >>>     if signals.xs_long.new == 1:
        >>>         self.data.buy()
        >>>     # 空头入场信号
        >>>     elif signals.xs_short.new == 1:
        >>>         self.data.sell()
        """
        ...

    @tobtind(lib='pta')
    def above(self, b=None, asint=True, offset=0, **kwargs) -> IndSeries:
        """
        序列a大于或等于序列b或数值
        ---------
            判断序列a是否大于或等于序列b或数值。

        参数:
        ---------
        >>> b (Union[Series,float,int]): 序列b或数值
            asint (bool, 可选): 是否转为整数. 默认: True
            offset (int, 可选): 数据偏移. 默认: 0

        返回:
        ---------
        >>> IndSeries: 布尔序列或整数序列

        使用案例:
        >>> # 判断价格是否在移动平均线之上
        >>> above_condition = self.data.above(b=self.data.sma(length=20))
        >>> 
        >>> # 判断价格是否在特定水平之上
        >>> def above_resistance(self):
        >>>     above_res = self.data.above(b=100)
        >>>     if above_res.new:
        >>>         return "价格突破阻力位"
        """
        ...

    @tobtind(lib='pta')
    def below(self, b=None, asint=True, offset=0, **kwargs) -> IndSeries:
        """
        序列a小于或等于序列b或数值
        ---------
            判断序列a是否小于或等于序列b或数值。

        参数:
        ---------
        >>> b (Union[Series,float,int]): 序列b或数值
            asint (bool, 可选): 是否转为整数. 默认: True
            offset (int, 可选): 数据偏移. 默认: 0

        返回:
        ---------
        >>> IndSeries: 布尔序列或整数序列

        使用案例:
        >>> # 判断价格是否在移动平均线之下
        >>> below_condition = self.data.below(b=self.data.sma(length=20))
        >>> 
        >>> # 判断价格是否在特定水平之下
        >>> def below_support(self):
        >>>     below_sup = self.data.below(b=50)
        >>>     if below_sup.new:
        >>>         return "价格跌破支撑位"
        """
        ...

    @tobtind(lib='pta')
    def cross(self, b=None, above=True, asint=True, offset=0, **kwargs) -> IndSeries:
        """
        序列a上穿序列b或数值
        ---------
            判断序列a是否上穿序列b或数值。

        参数:
        ---------
        >>> b (pd.Series): 序列b或数值
            above (bool): 上穿方向. 默认: True
            asint (bool, 可选): 是否转为整数. 默认: True
            offset (int, 可选): 数据偏移. 默认: 0

        返回:
        ---------
        >>> IndSeries: 布尔序列或整数序列

        使用案例:
        >>> # 判断快速EMA是否上穿慢速EMA
        >>> cross_condition = self.data.ema(length=10).cross(b=self.data.ema(length=20))
        >>> 
        >>> # 使用交叉信号
        >>> def golden_cross(self):
        >>>     cross = self.data.ema(length=10).cross(b=self.data.ema(length=50))
        >>>     if cross.new:
        >>>         return "金叉信号出现"
        """
        ...

    @tobtind(lib='pta')
    def cross_up(self, b=None, asint=True, offset=0, **kwargs) -> IndSeries:
        """
        序列a上穿序列b或数值
        ---------
            判断序列a是否上穿序列b或数值。

        参数:
        ---------
        >>> b (pd.Series): 序列b或数值
            asint (bool, 可选): 是否转为整数. 默认: True
            offset (int, 可选): 数据偏移. 默认: 0

        返回:
        ---------
        >>> IndSeries: 布尔序列或整数序列

        使用案例:
        >>> # 判断价格是否上穿移动平均线
        >>> cross_up_condition = self.data.cross_up(b=self.data.sma(length=20))
        >>> 
        >>> # 使用上穿信号
        >>> def breakout_signal(self):
        >>>     breakout = self.data.cross_up(b=self.data.high.rolling(20).max())
        >>>     if breakout.new:
        >>>         return "价格突破20日高点"
        """
        ...

    @tobtind(lib='pta')
    def cross_down(self, b=None, asint=True, offset=0, **kwargs) -> IndSeries:
        """
        下穿信号 (Cross Down)
        ---------
            检测序列a是否下穿序列b，或序列a是否下穿一个数值。

        数据来源:
        ---------
            技术分析基础

        计算方法:
        ---------
            >>> Condition: (a[i-1] > b[i-1]) and (a[i] < b[i])
            When IndSeries a changes from greater than IndSeries b in previous period to less than IndSeries b in current period, a cross down signal is generated

        参数:
        ---------
        >>> b (pd.Series, float, int): 比较序列或数值. 默认: None
            asint (bool, 可选): 是否将结果转为整数(1/0). 默认: True
            offset (int, 可选): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 下穿信号序列，1表示下穿发生，0表示未发生

        所需数据字段:
        ---------
        >>> 序列a (通常是价格序列如close) 和 序列b (比较序列)

        使用案例:
        ---------
        >>> # 检测价格下穿移动平均线
        >>> cross_down_signal = self.data.cross_down(b=self.data.sma(length=20))
        >>> 
        >>> # 使用下穿信号生成卖出信号
        >>> def cross_down_sell_signal(self):
        >>>     if cross_down_signal.new == 1:
        >>>         self.data.sell()
        >>>         return "价格下穿移动平均线，卖出信号"
        """
        ...

    @tobtind(lines=['aber_zg', 'aber_sg', 'aber_xg', 'aber_atr'], lib='pta')
    def aberration(self, length=5, atr_length=15, offset=0, **kwargs) -> IndFrame:
        """
        偏差通道指标 (Aberration)
        ---------
            类似于凯尔特纳通道的波动性指标，用于识别价格突破和趋势变化。

        数据来源:
        ---------
            基于网络资源实现，由Github用户homily请求添加

        计算方法:
        ---------
            >>> Default Inputs: length=5, atr_length=15
            ATR = Average True Range
            SMA = Simple Moving Average
            JG = TP = HLC3(high, low, close)
            ZG = SMA(JG, length)
            SG = ZG + ATR
            XG = ZG - ATR

        参数:
        ---------
        >>> length (int): 中轨计算周期. 默认: 5
            atr_length (int): ATR计算周期. 默认: 15
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含aber_zg(中轨), aber_sg(上轨), aber_xg(下轨), aber_atr(ATR)列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算偏差通道指标
        >>> zg, sg, xg, atr = self.data.aberration(length=5, atr_length=15)
        >>> 
        >>> # 使用偏差通道识别突破
        >>> def aberration_breakout_signal(self):
        >>>     zg, sg, xg, atr = self.data.aberration()
        >>>     if self.data.close.new > sg.new:
        >>>         return "价格突破偏差通道上轨，看涨突破"
        >>>     elif self.data.close.new < xg.new:
        >>>         return "价格跌破偏差通道下轨，看跌突破"
        """
        ...

    @tobtind(lines=['acc_lower', 'acc_mid', 'acc_upper'], lib='pta')
    def accbands(self, length=10, c=4, drift=1, mamode="sma", offset=0, **kwargs) -> IndFrame:
        """
        加速带指标 (Acceleration Bands, ACCBANDS)
        ---------
            Price Headley创建的加速带，在简单移动平均线周围绘制上下包络带。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/acceleration-bands-abands/

        计算方法:
        ---------
            >>> Default Inputs: length=10, c=4
            EMA = Exponential Moving Average
            SMA = Simple Moving Average
            HL_RATIO = c * (high - low) / (high + low)
            LOW = low * (1 - HL_RATIO)
            HIGH = high * (1 + HL_RATIO)
            if mamode == 'ema':
                LOWER = EMA(LOW, length)
                MID = EMA(close, length)
                UPPER = EMA(HIGH, length)
            else:
                LOWER = SMA(LOW, length)
                MID = SMA(close, length)
                UPPER = SMA(HIGH, length)

        参数:
        ---------
        >>> length (int): 移动平均周期. 默认: 10
            c (int): 高低价比率乘数. 默认: 4
            mamode (str): 移动平均模式. 默认: 'sma'
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含acc_lower(下轨), acc_mid(中轨), acc_upper(上轨)列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算加速带指标
        >>> lower, mid, upper = self.data.accbands(length=10, c=4)
        >>> 
        >>> # 使用加速带识别趋势加速
        >>> def accbands_trend_acceleration(self):
        >>>     lower, mid, upper = self.data.accbands()
        >>>     if self.data.close.new > upper.new:
        >>>         return "价格突破加速带上轨，加速上涨信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def atr(self, length=14, mamode="rma", talib=True, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        平均真实波幅 (Average True Range, ATR)
        ---------
            用于衡量波动性，特别是由跳空或涨跌停引起的波动性。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Average_True_Range_(ATR)

        计算方法:
        ---------
            >>> Default Inputs: length=14, drift=1, percent=False
            EMA = Exponential Moving Average
            SMA = Simple Moving Average
            WMA = Weighted Moving Average
            RMA = WildeR's Moving Average
            TR = True Range
            tr = TR(high, low, close, drift)
            if mamode == 'ema':
                ATR = EMA(tr, length)
            elif mamode == 'sma':
                ATR = SMA(tr, length)
            elif mamode == 'wma':
                ATR = WMA(tr, length)
            else:
                ATR = RMA(tr, length)
            if percent:
                ATR *= 100 / close

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 14
            mamode (str): 移动平均模式. 默认: 'rma'
            talib (bool): 如果安装了TA Lib且talib为True，返回TA Lib版本. 默认: True
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> percent (bool, 可选): 是否以百分比形式返回. 默认: False
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算平均真实波幅
        >>> atr_IndSeries = self.data.atr(length=14)
        >>> 
        >>> # 使用ATR设置止损
        >>> def atr_stop_loss(self):
        >>>     atr = self.data.atr(length=14)
        >>>     stop_loss_distance = 2 * atr.new
        >>>     return f"建议止损距离: {stop_loss_distance:.2f}"
        """
        ...

    @tobtind(lines=['bb_lower', 'bb_mid', 'bb_upper', 'bb_width', 'bb_percent'], overlap=True, lib='pta')
    def bbands(self, length=10, std=2., ddof=0, mamode="sma", talib=True, offset=0, **kwargs) -> IndFrame:
        """
        布林带 (Bollinger Bands, BBANDS)
        ---------
            John Bollinger开发的流行波动性指标。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Bollinger_Bands_(BB)

        计算方法:
        ---------
            >>> Default Inputs: length=5, std=2, mamode="sma", ddof=0
            EMA = Exponential Moving Average
            SMA = Simple Moving Average
            STDEV = Standard Deviation
            stdev = STDEV(close, length, ddof)
            if mamode == "ema":
                MID = EMA(close, length)
            else:
                MID = SMA(close, length)
            LOWER = MID - std * stdev
            UPPER = MID + std * stdev
            BANDWIDTH = 100 * (UPPER - LOWER) / MID
            PERCENT = (close - LOWER) / (UPPER - LOWER)

        参数:
        ---------
        >>> length (int): 移动平均周期. 默认: 5
            std (float): 标准差乘数. 默认: 2.0
            ddof (int): 标准差计算中的自由度. 默认: 0
            mamode (str): 移动平均模式. 默认: 'sma'
            talib (bool): 如果安装了TA Lib且talib为True，返回TA Lib版本. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含bb_lower(下轨), bb_mid(中轨), bb_upper(上轨), 
                      bb_width(带宽), bb_percent(百分比位置)列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算布林带
        >>> lower, mid, upper, width, percent = self.data.bbands(length=20, std=2)
        >>> 
        >>> # 使用布林带识别超买超卖
        >>> def bbands_overbought_oversold(self):
        >>>     lower, mid, upper, width, percent = self.data.bbands()
        >>>     if self.data.close.new >= upper.new:
        >>>         return "价格触及布林带上轨，可能超买"
        >>>     elif self.data.close.new <= lower.new:
        >>>         return "价格触及布林带下轨，可能超卖"
        """
        ...

    @tobtind(lines=['dc_lower', 'dc_mid', 'dc_upper'], lib='pta')
    def donchian(self, lower_length=20, upper_length=20, offset=0, **kwargs) -> IndFrame:
        """
        唐奇安通道 (Donchian Channels, DC)
        ---------
            用于衡量波动性，基于指定周期内的最高价和最低价。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Donchian_Channels_(DC)

        计算方法:
        ---------
            >>> Default Inputs: lower_length=upper_length=20
            LOWER = low.rolling(lower_length).min()
            UPPER = high.rolling(upper_length).max()
            MID = 0.5 * (LOWER + UPPER)

        参数:
        ---------
        >>> lower_length (int): 下轨计算周期(最低价). 默认: 20
            upper_length (int): 上轨计算周期(最高价). 默认: 20
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含dc_lower(下轨), dc_mid(中轨), dc_upper(上轨)列的数据框

        所需数据字段:
        ---------
        >>> high, low

        使用案例:
        ---------
        >>> # 计算唐奇安通道
        >>> lower, mid, upper = self.data.donchian(lower_length=20, upper_length=20)
        >>> 
        >>> # 使用唐奇安通道识别突破
        >>> def donchian_breakout(self):
        >>>     lower, mid, upper = self.data.donchian()
        >>>     if self.data.close.new > upper.new:
        >>>         return "价格突破唐奇安通道上轨，看涨突破"
        >>>     elif self.data.close.new < lower.new:
        >>>         return "价格跌破唐奇安通道下轨，看跌突破"
        """
        ...

    @tobtind(lines=['hwc', 'hwc_upper', 'hwc_lower'], lib='pta')
    def hwc(self, na=0.2, nb=0.1, nc=0.1, nd=0.1, scalar=1., channel_eval=False, offset=0, **kwargs) -> IndFrame:
        """
        霍尔特-温特斯通道 (Holt-Winter Channel, HWC)
        ---------
            基于HWMA的通道指标，使用霍尔特-温特斯方法计算。

        数据来源:
        ---------
            https://www.mql5.com/en/code/20857

        计算方法:
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
            Var[i] = (1-d) * Var[i-1] + nD * (Price[i-1] - HWMA[i-1]) * (Price[i-1] - HWMA[i-1])

        参数:
        ---------
        >>> na (float): 平滑序列参数 (0到1). 默认: 0.2
            nb (float): 趋势参数 (0到1). 默认: 0.1
            nc (float): 季节性参数 (0到1). 默认: 0.1
            nd (float): 通道方程参数 (0到1). 默认: 0.1
            scalar (float): 通道宽度乘数. 默认: 1.0
            channel_eval (bool): 是否返回宽度和百分比位置. 默认: False
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含hwc(中轨), hwc_upper(上轨), hwc_lower(下轨)列的数据框

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算霍尔特-温特斯通道
        >>> hwc, upper, lower = self.data.hwc(na=0.2, nb=0.1, nc=0.1, nd=0.1)
        >>> 
        >>> # 使用HWC通道进行交易
        >>> def hwc_trading_signals(self):
        >>>     hwc, upper, lower = self.data.hwc()
        >>>     if self.data.close.new > upper.new:
        >>>         return "价格突破HWC上轨，买入信号"
        >>>     elif self.data.close.new < lower.new:
        >>>         return "价格跌破HWC下轨，卖出信号"
        """
        ...

    @tobtind(lines=['kc_lower', 'kc_basis', 'kc_upper'], lib='pta')
    def kc(self, length=20, scalar=2., mamode="ema", offset=0, **kwargs) -> IndFrame:
        """
        凯尔特纳通道 (Keltner Channels, KC)
        ---------
            流行的波动性指标，类似于布林带和唐奇安通道。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Keltner_Channels_(KC)

        计算方法:
        ---------
            >>> Default Inputs: length=20, scalar=2, mamode=None, tr=True
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

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 20
            scalar (float): 通道宽度乘数. 默认: 2.0
            mamode (str): 移动平均模式. 默认: 'ema'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> tr (bool): 是否使用真实波幅计算. 默认: True
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含kc_lower(下轨), kc_basis(中轨), kc_upper(上轨)列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算凯尔特纳通道
        >>> lower, basis, upper = self.data.kc(length=20, scalar=2)
        >>> 
        >>> # 使用凯尔特纳通道识别趋势
        >>> def kc_trend_identification(self):
        >>>     lower, basis, upper = self.data.kc()
        >>>     if self.data.close.new > basis.new:
        >>>         return "价格在凯尔特纳通道中轨上方，上升趋势"
        >>>     elif self.data.close.new < basis.new:
        >>>         return "价格在凯尔特纳通道中轨下方，下降趋势"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def massi(self, fast=9, slow=25, offset=0, **kwargs) -> IndSeries:
        """
        质量指数 (Mass Index, MASSI)
        ---------
            非定向波动性指标，利用高低价范围识别基于范围扩张的趋势反转。

        数据来源:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:mass_index

        计算方法:
        ---------
            >>> Default Inputs: fast=9, slow=25
            EMA = Exponential Moving Average
            hl = high - low
            hl_ema1 = EMA(hl, fast)
            hl_ema2 = EMA(hl_ema1, fast)
            hl_ratio = hl_ema1 / hl_ema2
            MASSI = SUM(hl_ratio, slow)

        参数:
        ---------
        >>> fast (int): 快速周期. 默认: 9
            slow (int): 慢速周期. 默认: 25
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low

        使用案例:
        ---------
        >>> # 计算质量指数
        >>> massi_IndSeries = self.data.massi(fast=9, slow=25)
        >>> 
        >>> # 使用质量指数识别反转
        >>> def massi_reversal_signal(self):
        >>>     massi = self.data.massi()
        >>>     if massi.new > 27:
        >>>         return "质量指数高于27，可能出现趋势反转"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def natr(self, length=20, scalar=100., mamode="ema", talib=True, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        标准化平均真实波幅 (Normalized Average True Range, NATR)
        ---------
            试图标准化平均真实波幅。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/normalized-average-true-range-natr/

        计算方法:
        ---------
            >>> Default Inputs: length=20
            ATR = Average True Range
            NATR = (100 / close) * ATR(high, low, close)

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 20
            scalar (float): 放大倍数. 默认: 100.0
            mamode (str): 移动平均模式. 默认: 'ema'
            talib (bool): 如果安装了TA Lib且talib为True，返回TA Lib版本. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算标准化ATR
        >>> natr_IndSeries = self.data.natr(length=20)
        >>> 
        >>> # 使用NATR进行跨品种比较
        >>> def natr_cross_instrument_comparison(self):
        >>>     natr = self.data.natr(length=20)
        >>>     return f"标准化波动率: {natr.new:.2f}%"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pdist(self, drift=10, offset=0, **kwargs) -> IndSeries:
        """
        价格距离指标 (Price Distance, PDIST)
        ---------
            衡量价格运动所覆盖的"距离"。

        数据来源:
        ---------
            https://www.prorealcode.com/prorealtime-indicators/pricedistance/

        计算方法:
        ---------
            >>> Default Inputs: drift=1
            PDIST = 2(high - low) - ABS(close - open) + ABS(open - close[drift])

        参数:
        ---------
        >>> drift (int): 差异周期. 默认: 10
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> open, high, low, close

        使用案例:
        ---------
        >>> # 计算价格距离指标
        >>> pdist_IndSeries = self.data.pdist(drift=10)
        >>> 
        >>> # 使用价格距离分析市场活跃度
        >>> def pdist_market_activity(self):
        >>>     pdist = self.data.pdist(drift=10)
        >>>     if pdist.new > pdist.ema(period=20).new:
        >>>         return "价格距离扩大，市场活跃度增加"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def rvi(self, length=14, scalar=100., refined=False, thirds=False, mamode="ema",
            drift=1, offset=0, **kwargs) -> IndSeries:
        """
        相对波动指数 (Relative Volatility Index, RVI)
        ---------
            1993年创建，1995年修订。
            不像RSI基于价格方向累加价格变化，RVI基于价格方向累加标准差。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Relative_Volatility_Index_(RVI)

        计算方法:
        ---------
            >>> Default Inputs: length=14, scalar=100, refined=None, thirds=None
            EMA = Exponential Moving Average
            STDEV = Standard Deviation
            UP = STDEV(src, length) IF src.diff() > 0 ELSE 0
            DOWN = STDEV(src, length) IF src.diff() <= 0 ELSE 0
            UPSUM = EMA(UP, length)
            DOWNSUM = EMA(DOWN, length)
            RVI = scalar * (UPSUM / (UPSUM + DOWNSUM))

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 14
            scalar (float): 放大倍数. 默认: 100.0
            refined (bool): 使用'精炼'计算，即RVI(high)和RVI(low)的平均值. 默认: False
            thirds (bool): 最高价、最低价和收盘价的平均值. 默认: False
            mamode (str): 移动平均模式. 默认: 'ema'
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算相对波动指数
        >>> rvi_IndSeries = self.data.rvi(length=14)
        >>> 
        >>> # 使用RVI识别波动性趋势
        >>> def rvi_volatility_trend(self):
        >>>     rvi = self.data.rvi(length=14)
        >>>     if rvi.new > 50:
        >>>         return "RVI高于50，波动性偏向上升"
        >>>     elif rvi.new < 50:
        >>>         return "RVI低于50，波动性偏向下降"
        """
        ...

    @tobtind(lines=['thermo', 'thermo_ma', 'thermo_long', 'thermo_short'], lib='pta')
    def thermo(self, length=20, long=2., short=0.5, mamode="ema", drift=1, offset=0, **kwargs) -> IndFrame:
        """
        埃尔德温度计 (Elder's Thermometer, THERMO)
        ---------
            衡量价格波动性。

        数据来源:
        ---------
            https://www.motivewave.com/studies/elders_thermometer.htm
            https://www.tradingview.com/script/HqvTuEMW-Elder-s-Market-Thermometer-LazyBear/

        计算方法:
        ---------
            >>> Default Inputs: length=20, drift=1, mamode=EMA, long=2, short=0.5
            EMA = Exponential Moving Average
            thermoL = (low.shift(drift) - low).abs()
            thermoH = (high - high.shift(drift)).abs()
            thermo = np.where(thermoH > thermoL, thermoH, thermoL)
            thermo_ma = ema(thermo, length)
            thermo_long = thermo < (thermo_ma * long)
            thermo_short = thermo > (thermo_ma * short)
            thermo_long = thermo_long.astype(int)
            thermo_short = thermo_short.astype(int)

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 20
            long (float): 买入因子. 默认: 2.0
            short (float): 卖出因子. 默认: 0.5
            mamode (str): 移动平均模式. 默认: 'ema'
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含thermo(温度计), thermo_ma(移动平均), 
                      thermo_long(多头信号), thermo_short(空头信号)列的数据框

        所需数据字段:
        ---------
        >>> high, low

        使用案例:
        ---------
        >>> # 计算埃尔德温度计
        >>> thermo, thermo_ma, thermo_long, thermo_short = self.data.thermo(length=20)
        >>> 
        >>> # 使用温度计识别市场状态
        >>> def thermo_market_state(self):
        >>>     thermo, thermo_ma, thermo_long, thermo_short = self.data.thermo()
        >>>     if thermo_long.new == 1:
        >>>         return "温度计显示低波动，适合买入"
        >>>     elif thermo_short.new == 1:
        >>>         return "温度计显示高波动，注意风险"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def true_range(self, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        真实波幅 (True Range)
        ---------
            将经典波幅（最高价减最低价）扩展到包括可能的跳空情况。

        数据来源:
        ---------
            https://www.macroption.com/true-range/

        计算方法:
        ---------
            >>> Default Inputs: drift=1
            ABS = Absolute Value
            prev_close = close.shift(drift)
            TRUE_RANGE = ABS([high - low, high - prev_close, low - prev_close])

        参数:
        ---------
        >>> drift (int): 偏移周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> talib (bool): 如果安装了TA Lib且talib为True，返回TA Lib版本. 默认: True
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 计算真实波幅
        >>> tr_IndSeries = self.data.true_range(drift=1)
        >>> 
        >>> # 使用真实波幅分析波动性
        >>> def true_range_volatility(self):
        >>>     tr = self.data.true_range()
        >>>     return f"当前真实波幅: {tr.new:.2f}"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def ui(self, length=14, scalar=100., offset=0, **kwargs) -> IndSeries:
        """
        溃疡指数 (Ulcer Index, UI)
        ---------
            Peter Martin开发的溃疡指数使用二次均值衡量下行波动性，
            具有强调大幅回撤的效果。

        数据来源:
        ---------
            https://library.tradingtechnologies.com/trade/chrt-ti-ulcer-index.html
            https://en.wikipedia.org/wiki/Ulcer_index
            http://www.tangotools.com/ui/ui.htm

        计算方法:
        ---------
            >>> Default Inputs: length=14, scalar=100
            HC = Highest Close
            SMA = Simple Moving Average
            HCN = HC(close, length)
            DOWNSIDE = scalar * (close - HCN) / HCN
            if kwargs["everget"]:
                UI = SQRT(SMA(DOWNSIDE^2, length) / length)
            else:
                UI = SQRT(SUM(DOWNSIDE^2, length) / length)

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 14
            scalar (float): 放大倍数. 默认: 100.0
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> everget (bool, 可选): 使用TradingView的Everget的SMA计算而不是SUM计算. 默认: False
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close

        使用案例:
        ---------
        >>> # 计算溃疡指数
        >>> ui_IndSeries = self.data.ui(length=14)
        >>> 
        >>> # 使用溃疡指数评估风险
        >>> def ui_risk_assessment(self):
        >>>     ui = self.data.ui(length=14)
        >>>     if ui.new < 5:
        >>>         return "溃疡指数较低，风险可控"
        >>>     elif ui.new > 10:
        >>>         return "溃疡指数较高，注意下行风险"
        """
        ...

    # Volume
    @tobtind(lines=None, lib='pta')
    def ad(self, open_=None, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        累积/派发线 (Accumulation/Distribution, AD)
        ---------
            利用收盘价相对于其高低价范围的位置与成交量，然后进行累积。

        数据来源:
        ---------
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/accumulationdistribution-ad/

        计算方法:
        ---------
            CUM = Cumulative Sum
            if 'open':
                AD = close - open
            else:
                AD = 2 * close - high - low
            hl_range = high - low
            AD = AD * volume / hl_range
            AD = CUM(AD)

        参数:
        ---------
        >>> open_ (pd.Series): 开盘价序列. 默认: None
            talib (bool): 如果安装了TA Lib且talib为True，返回TA Lib版本. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> open, high, low, close, volume

        使用案例:
        ---------
        >>> # 计算累积/派发线
        >>> ad_IndSeries = self.data.ad()
        >>> 
        >>> # 使用AD线分析资金流向
        >>> def ad_money_flow(self):
        >>>     ad = self.data.ad()
        >>>     if ad.new > ad.prev:
        >>>         return "AD线上涨，资金在累积"
        >>>     elif ad.new < ad.prev:
        >>>         return "AD线下跌，资金在派发"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def adosc(self, open_=None, fast=12, slow=26, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        累积/派发震荡指标或蔡金震荡指标 (Accumulation/Distribution Oscillator or Chaikin Oscillator)
        ---------
            利用累积/派发线，类似于MACD或APO的处理方式。

        数据来源:
        ---------
            https://www.investopedia.com/articles/active-trading/031914/understanding-chaikin-oscillator.asp

        计算方法:
        ---------
            >>> Default Inputs: fast=12, slow=26
            AD = Accum/Dist
            ad = AD(high, low, close, open)
            fast_ad = EMA(ad, fast)
            slow_ad = EMA(ad, slow)
            ADOSC = fast_ad - slow_ad

        参数:
        ---------
        >>> open_ (pd.Series): 开盘价序列. 默认: None
            fast (int): 快速周期. 默认: 12
            slow (int): 慢速周期. 默认: 26
            talib (bool): 如果安装了TA Lib且talib为True，返回TA Lib版本. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> open, high, low, close, volume

        使用案例:
        ---------
        >>> # 计算蔡金震荡指标
        >>> adosc_IndSeries = self.data.adosc(fast=12, slow=26)
        >>> 
        >>> # 使用蔡金震荡指标识别买卖点
        >>> def adosc_trading_signals(self):
        >>>     adosc = self.data.adosc()
        >>>     if adosc.new > 0 and adosc.prev <= 0:
        >>>         return "蔡金震荡指标上穿零轴，买入信号"
        >>>     elif adosc.new < 0 and adosc.prev >= 0:
        >>>         return "蔡金震荡指标下穿零轴，卖出信号"
        """
        ...

    @tobtind(lines=['obv_min', 'obv_max', 'obv_maf', 'obv_mas', 'obv_long', 'obv_short'], lib='pta')
    def aobv(self, fast=4, slow=12, max_lookback=2, min_lookback=2, mamode="ema", offset=0, **kwargs) -> IndFrame:
        """
        阿切尔能量潮指标 (Archer On Balance Volume, AOBV)
        ---------
            基于能量潮(OBV)的增强指标，包含多个信号线。

        参数:
        ---------
        >>> fast (int): 快速移动平均周期. 默认: 4
            slow (int): 慢速移动平均周期. 默认: 12
            max_lookback (int): 最大值回溯周期. 默认: 2
            min_lookback (int): 最小值回溯周期. 默认: 2
            mamode (str): 移动平均模式. 默认: 'ema'
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含obv_min(最小值), obv_max(最大值), obv_maf(快速移动平均),
                      obv_mas(慢速移动平均), obv_long(多头信号), obv_short(空头信号)列的数据框

        所需数据字段:
        ---------
        >>> close, volume

        使用案例:
        ---------
        >>> # 计算阿切尔能量潮指标
        >>> obv_min, obv_max, obv_maf, obv_mas, obv_long, obv_short = self.data.aobv(fast=4, slow=12)
        >>> 
        >>> # 使用AOBV进行交易决策
        >>> def aobv_trading_decision(self):
        >>>     obv_min, obv_max, obv_maf, obv_mas, obv_long, obv_short = self.data.aobv()
        >>>     if obv_long.new == 1:
        >>>         return "AOBV发出多头信号"
        >>>     elif obv_short.new == 1:
        >>>         return "AOBV发出空头信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def cmf(self, open_=None, length=20, offset=0, **kwargs) -> IndSeries:
        """
        蔡金资金流 (Chaikin Money Flow, CMF)
        ---------
            衡量特定时期内资金流量的多少，与累积/派发线结合使用。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Chaikin_Money_Flow_(CMF)
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:chaikin_money_flow_cmf

        计算方法:
        ---------
            >>> Default Inputs: length=20
            if 'open':
                ad = close - open
            else:
                ad = 2 * close - high - low
            hl_range = high - low
            ad = ad * volume / hl_range
            CMF = SUM(ad, length) / SUM(volume, length)

        参数:
        ---------
        >>> open_ (pd.Series): 开盘价序列. 默认: None
            length (int): 计算周期. 默认: 20
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> open, high, low, close, volume

        使用案例:
        ---------
        >>> # 计算蔡金资金流
        >>> cmf_IndSeries = self.data.cmf(length=20)
        >>> 
        >>> # 使用CMF分析资金流向强度
        >>> def cmf_money_flow_strength(self):
        >>>     cmf = self.data.cmf(length=20)
        >>>     if cmf.new > 0.1:
        >>>         return "CMF大于0.1，强势资金流入"
        >>>     elif cmf.new < -0.1:
        >>>         return "CMF小于-0.1，强势资金流出"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def efi(self, length=13, mamode="ema", drift=1, offset=0, **kwargs) -> IndSeries:
        """
        埃尔德力量指数 (Elder's Force Index, EFI)
        ---------
            使用价格和成交量衡量价格运动背后的力量，以及潜在的反转和价格修正。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Elder%27s_Force_Index_(EFI)
            https://www.motivewave.com/studies/elders_force_index.htm

        计算方法:
        ---------
            >>> Default Inputs: length=20, drift=1, mamode=None
            EMA = Exponential Moving Average
            SMA = Simple Moving Average
            pv_diff = close.diff(drift) * volume
            if mamode == 'sma':
                EFI = SMA(pv_diff, length)
            else:
                EFI = EMA(pv_diff, length)

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 13
            mamode (str): 移动平均模式. 默认: 'ema'
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close, volume

        使用案例:
        ---------
        >>> # 计算埃尔德力量指数
        >>> efi_IndSeries = self.data.efi(length=13)
        >>> 
        >>> # 使用EFI识别趋势强度
        >>> def efi_trend_strength(self):
        >>>     efi = self.data.efi(length=13)
        >>>     if efi.new > 0:
        >>>         return "EFI为正，上升趋势力量强劲"
        >>>     elif efi.new < 0:
        >>>         return "EFI为负，下降趋势力量强劲"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def eom(self, length=14, divisor=100, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        简易波动指标 (Ease of Movement, EOM)
        ---------
            基于成交量的震荡指标，旨在衡量价格和成交量在零线上下波动的关系。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Ease_of_Movement_(EOM)
            https://www.motivewave.com/studies/ease_of_movement.htm
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ease_of_movement_emv

        计算方法:
        ---------
            >>> Default Inputs: length=14, divisor=100000000, drift=1
            SMA = Simple Moving Average
            hl_range = high - low
            distance = 0.5 * (high - high.shift(drift) + low - low.shift(drift))
            box_ratio = (volume / divisor) / hl_range
            eom = distance / box_ratio
            EOM = SMA(eom, length)

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 14
            divisor (int): 成交量除数. 默认: 100
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close, volume

        使用案例:
        ---------
        >>> # 计算简易波动指标
        >>> eom_IndSeries = self.data.eom(length=14, divisor=100)
        >>> 
        >>> # 使用EOM识别趋势强度
        >>> def eom_trend_strength(self):
        >>>     eom = self.data.eom(length=14)
        >>>     if eom.new > 0:
        >>>         return "EOM为正，上升趋势容易形成"
        >>>     elif eom.new < 0:
        >>>         return "EOM为负，下降趋势容易形成"
        """
        ...

    @tobtind(lines=['kvo', 'kvos'], lib='pta')
    def kvo(self, fast=34, slow=55, signal=13, mamode="ema", drift=1, offset=0, **kwargs) -> IndFrame:
        """
        克林格成交量震荡指标 (Klinger Volume Oscillator, KVO)
        ---------
            Stephen J. Klinger开发，旨在通过比较成交量和价格来预测市场中的价格反转。

        数据来源:
        ---------
            https://www.investopedia.com/terms/k/klingeroscillator.asp
            https://www.daytrading.com/klinger-volume-oscillator

        计算方法:
        ---------
            >>> Default Inputs: fast=34, slow=55, signal=13, drift=1
            EMA = Exponential Moving Average
            SV = volume * signed_IndSeries(HLC3, 1)
            KVO = EMA(SV, fast) - EMA(SV, slow)
            Signal = EMA(KVO, signal)

        参数:
        ---------
        >>> fast (int): 快速周期. 默认: 34
            slow (int): 慢速周期. 默认: 55
            signal (int): 信号周期. 默认: 13
            mamode (str): 移动平均模式. 默认: 'ema'
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含kvo(主指标), kvos(信号线)列的数据框

        所需数据字段:
        ---------
        >>> high, low, close, volume

        使用案例:
        ---------
        >>> # 计算克林格成交量震荡指标
        >>> kvo, kvos = self.data.kvo(fast=34, slow=55, signal=13)
        >>> 
        >>> # 使用KVO识别买卖信号
        >>> def kvo_trading_signals(self):
        >>>     kvo, kvos = self.data.kvo()
        >>>     if kvo.new > kvos.new and kvo.prev <= kvos.prev:
        >>>         return "KVO上穿信号线，买入信号"
        >>>     elif kvo.new < kvos.new and kvo.prev >= kvos.prev:
        >>>         return "KVO下穿信号线，卖出信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def mfi(self, length=14, talib=True, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        资金流量指数 (Money Flow Index, MFI)
        ---------
            震荡指标，通过利用价格和成交量来衡量买卖压力。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Money_Flow_(MFI)

        计算方法:
        ---------
            >>> Default Inputs: length=14, drift=1
            tp = typical_price = hlc3 = (high + low + close) / 3
            rmf = raw_money_flow = tp * volume
            pmf = pos_money_flow = SUM(rmf, length) if tp.diff(drift) > 0 else 0
            nmf = neg_money_flow = SUM(rmf, length) if tp.diff(drift) < 0 else 0
            MFR = money_flow_ratio = pmf / nmf
            MFI = money_flow_index = 100 * pmf / (pmf + nmf)

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 14
            talib (bool): 如果安装了TA Lib且talib为True，返回TA Lib版本. 默认: True
            drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> high, low, close, volume

        使用案例:
        ---------
        >>> # 计算资金流量指数
        >>> mfi_IndSeries = self.data.mfi(length=14)
        >>> 
        >>> # 使用MFI识别超买超卖
        >>> def mfi_overbought_oversold(self):
        >>>     mfi = self.data.mfi(length=14)
        >>>     if mfi.new > 80:
        >>>         return "MFI大于80，超买状态"
        >>>     elif mfi.new < 20:
        >>>         return "MFI小于20，超卖状态"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def nvi(self, length=13, initial=1000, offset=0, **kwargs) -> IndSeries:
        """
        负成交量指数 (Negative Volume Index, NVI)
        ---------
            累积指标，使用成交量变化来尝试识别聪明资金活跃的位置。

        数据来源:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:negative_volume_inde
            https://www.motivewave.com/studies/negative_volume_index.htm

        计算方法:
        ---------
            >>> Default Inputs: length=1, initial=1000
            ROC = Rate of Change
            roc = ROC(close, length)
            signed_volume = signed_IndSeries(volume, initial=1)
            nvi = signed_volume[signed_volume < 0].abs() * roc_
            nvi.fillna(0, inplace=True)
            nvi.iloc[0]= initial
            nvi = nvi.cumsum()

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 13
            initial (int): 初始值. 默认: 1000
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close, volume

        使用案例:
        ---------
        >>> # 计算负成交量指数
        >>> nvi_IndSeries = self.data.nvi(length=13, initial=1000)
        >>> 
        >>> # 使用NVI识别聪明资金行为
        >>> def nvi_smart_money(self):
        >>>     nvi = self.data.nvi(length=13)
        >>>     if nvi.new > nvi.ema(period=20).new:
        >>>         return "NVI上升，聪明资金可能在累积"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def obv(self, talib=True, offset=0, **kwargs) -> IndSeries:
        """
        能量潮指标 (On Balance Volume, OBV)
        ---------
            累积指标，用于衡量买卖压力。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/On_Balance_Volume_(OBV)
            https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/on-balance-volume-obv/
            https://www.motivewave.com/studies/on_balance_volume.htm

        计算方法:
        ---------
            signed_volume = signed_IndSeries(close, initial=1) * volume
            obv = signed_volume.cumsum()

        参数:
        ---------
        >>> talib (bool): 如果安装了TA Lib且talib为True，返回TA Lib版本. 默认: True
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close, volume

        使用案例:
        ---------
        >>> # 计算能量潮指标
        >>> obv_IndSeries = self.data.obv()
        >>> 
        >>> # 使用OBV确认价格趋势
        >>> def obv_confirmation(self):
        >>>     obv = self.data.obv()
        >>>     if self.data.close.new > self.data.close.prev and obv.new > obv.prev:
        >>>         return "价格上涨且OBV上升，趋势确认"
        >>>     elif self.data.close.new < self.data.close.prev and obv.new < obv.prev:
        >>>         return "价格下跌且OBV下降，趋势确认"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pvi(self, length=13, initial=1000, offset=0, **kwargs) -> IndSeries:
        """
        正成交量指数 (Positive Volume Index, PVI)
        ---------
            累积指标，使用成交量变化来尝试识别聪明资金活跃的位置。
            与NVI结合使用。

        数据来源:
        ---------
            https://www.investopedia.com/terms/p/pvi.asp

        计算方法:
        ---------
            >>> Default Inputs: length=1, initial=1000
            ROC = Rate of Change
            roc = ROC(close, length)
            signed_volume = signed_IndSeries(volume, initial=1)
            pvi = signed_volume[signed_volume > 0].abs() * roc_
            pvi.fillna(0, inplace=True)
            pvi.iloc[0]= initial
            pvi = pvi.cumsum()

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 13
            initial (int): 初始值. 默认: 1000
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close, volume

        使用案例:
        ---------
        >>> # 计算正成交量指数
        >>> pvi_IndSeries = self.data.pvi(length=13, initial=1000)
        >>> 
        >>> # 使用PVI和NVI综合分析
        >>> def pvi_nvi_analysis(self):
        >>>     pvi = self.data.pvi()
        >>>     nvi = self.data.nvi()
        >>>     if pvi.new > pvi.prev and nvi.new > nvi.prev:
        >>>         return "PVI和NVI同时上升，强烈看涨信号"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pvol(self, offset=0, **kwargs) -> IndSeries:
        """
        价格-成交量指标 (Price-Volume, PVOL)
        ---------
            返回价格和成交量的乘积序列。

        计算方法:
        ---------
            if signed:
                pvol = signed_IndSeries(close, 1) * close * volume
            else:
                pvol = close * volume

        参数:
        ---------
        >>> offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> signed (bool): 保持收盘价差异的符号. 默认: True
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close, volume

        使用案例:
        ---------
        >>> # 计算价格-成交量指标
        >>> pvol_IndSeries = self.data.pvol()
        >>> 
        >>> # 使用PVOL分析成交金额
        >>> def pvol_analysis(self):
        >>>     pvol = self.data.pvol()
        >>>     return f"当前成交金额: {pvol.new:.2f}"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pvr(self, **kwargs) -> IndSeries:
        """
        价格成交量排名 (Price Volume Rank)
        ---------
            Anthony J. Macek开发，描述在1994年6月的《股票与商品技术分析》杂志文章中。
            基本解释是当PV排名低于2.5时买入，高于2.5时卖出。

        数据来源:
        ---------
            https://www.fmlabs.com/reference/default.htm?url=PVrank.htm

        计算方法:
        ---------
            return 1 if 'close change' >= 0 and 'volume change' >= 0
            return 2 if 'close change' >= 0 and 'volume change' < 0
            return 3 if 'close change' < 0 and 'volume change' >= 0
            return 4 if 'close change' < 0 and 'volume change' < 0

        参数:
        ---------
        >>> 无额外参数

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close, volume

        使用案例:
        ---------
        >>> # 计算价格成交量排名
        >>> pvr_IndSeries = self.data.pvr()
        >>> 
        >>> # 使用PVR进行交易决策
        >>> def pvr_trading_decision(self):
        >>>     pvr = self.data.pvr()
        >>>     if pvr.new < 2.5:
        >>>         return "PVR低于2.5，考虑买入"
        >>>     elif pvr.new > 2.5:
        >>>         return "PVR高于2.5，考虑卖出"
        """
        ...

    @tobtind(lines=None, lib='pta')
    def pvt(self, drift=1, offset=0, **kwargs) -> IndSeries:
        """
        价量趋势指标 (Price-Volume Trend, PVT)
        ---------
            利用变动率和成交量及其累积值来确定资金流。

        数据来源:
        ---------
            https://www.tradingview.com/wiki/Price_Volume_Trend_(PVT)

        计算方法:
        ---------
            >>> Default Inputs: drift=1
            ROC = Rate of Change
            pv = ROC(close, drift) * volume
            PVT = pv.cumsum()

        参数:
        ---------
        >>> drift (int): 差异周期. 默认: 1
            offset (int): 结果偏移周期数. 默认: 0

        可选参数:
        ---------
        >>> fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndSeries: 生成的新特征序列

        所需数据字段:
        ---------
        >>> close, volume

        使用案例:
        ---------
        >>> # 计算价量趋势指标
        >>> pvt_IndSeries = self.data.pvt(drift=1)
        >>> 
        >>> # 使用PVT分析资金流向
        >>> def pvt_money_flow(self):
        >>>     pvt = self.data.pvt()
        >>>     if pvt.new > pvt.prev:
        >>>         return "PVT上升，资金流入"
        >>>     elif pvt.new < pvt.prev:
        >>>         return "PVT下降，资金流出"
        """
        ...

    @tobtind(lines=['low_price', 'mean_price', 'high_price', 'pos_volume', 'neg_volume', 'total_volume'], lib='pta')
    def vp(self, width=10, **kwargs) -> IndFrame:
        """
        成交量分布图 (Volume Profile, VP)
        ---------
            通过将价格划分为范围来计算成交量分布图。
            注意：未计算价值区域。

        数据来源:
        ---------
            https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:volume_by_price
            https://www.tradingview.com/wiki/Volume_Profile
            http://www.ranchodinero.com/volume-tpo-essentials/
            https://www.tradingtechnologies.com/blog/2013/05/15/volume-at-price/

        计算方法:
        ---------
            >>> Default Inputs: width=10
            vp = pd.concat([close, pos_volume, neg_volume], axis=1)
            if sort_close:
                vp_ranges = cut(vp[close_col], width)
                result = ({range_left, mean_close, range_right, pos_volume, neg_volume} foreach range in vp_ranges
            else:
                vp_ranges = np.array_split(vp, width)
                result = ({low_close, mean_close, high_close, pos_volume, neg_volume} foreach range in vp_ranges
            vpdf = pd.DataFrame(result)
            vpdf['total_volume'] = vpdf['pos_volume'] + vpdf['neg_volume']

        参数:
        ---------
        >>> width (int): 将价格分布到的范围数量. 默认: 10

        可选参数:
        ---------
        >>> sort_close (bool, 可选): 在分割为范围之前是否按收盘价排序. 默认: False
            fillna (value, 可选): pd.DataFrame.fillna(value)
            fill_method (value, 可选): 填充方法类型

        返回:
        ---------
        >>> IndFrame: 包含low_price(最低价), mean_price(平均价), high_price(最高价),
                      pos_volume(正成交量), neg_volume(负成交量), total_volume(总成交量)列的数据框

        所需数据字段:
        ---------
        >>> close, volume

        使用案例:
        ---------
        >>> # 计算成交量分布图
        >>> low_price, mean_price, high_price, pos_volume, neg_volume, total_volume = self.data.vp(width=10)
        >>> 
        >>> # 使用VP分析支撑阻力
        >>> def vp_support_resistance(self):
        >>>     low_price, mean_price, high_price, pos_volume, neg_volume, total_volume = self.data.vp()
        >>>     # 寻找高成交量区域作为支撑阻力
        >>>     max_volume_idx = total_volume.idxmax()
        >>>     return f"高成交量区域在价格 {mean_price[max_volume_idx]:.2f} 附近"
        """
        ...

    @tobtind(lines=None, lib="pta")
    def Any(self, *args, keep=True, **kwargs) -> IndSeries:
        """
        逻辑或运算 (Logical OR Operation)
        ---------
            对多个序列进行逻辑或运算，返回结果序列。

        参数:
        ---------
        >>> *args: (np.ndarray | IndSeries | pd.Series) - 要参与运算的序列
            keep (bool): 为True时自身数据也参与运算. 默认: True
            **kwargs: 其他参数

        返回:
        ---------
        >>> IndSeries: 逻辑或运算结果序列

        使用案例:
        ---------
        >>> # 多个条件满足任意一个
        >>> condition1 = self.data.close > self.data.ema(length=10)
        >>> condition2 = self.data.rsi(length=14) > 50
        >>> condition3 = self.data.volume > self.data.volume.ema(length=20)
        >>> 
        >>> # 任意条件满足即返回True
        >>> any_condition = self.data.Any(condition1, condition2, condition3)
        >>> 
        >>> def multi_condition_strategy(self):
        >>>     any_signal = self.data.Any(
        >>>         self.data.close > self.data.ema(20),
        >>>         self.data.rsi(14) > 70,
        >>>         self.data.macd().macd > 0
        >>>     )
        >>>     if any_signal.new:
        >>>         return "至少一个条件满足"
        """
        ...

    @tobtind(lines=None, lib="pta")
    def All(self, *args, **kwargs) -> IndSeries:
        """
        逻辑与运算 (Logical AND Operation)
        ---------
            对多个序列进行逻辑与运算，返回结果序列。

        参数:
        ---------
        >>> *args: (np.ndarray | IndSeries | pd.Series) - 要参与运算的序列
            **kwargs: 其他参数

        返回:
        ---------
        >>> IndSeries: 逻辑与运算结果序列

        使用案例:
        ---------
        >>> # 需要所有条件同时满足
        >>> condition1 = self.data.close > self.data.ema(length=20)
        >>> condition2 = self.data.rsi(length=14) > 50
        >>> condition3 = self.data.macd().macd > self.data.macd().macds
        >>> 
        >>> # 所有条件必须同时满足
        >>> all_condition = self.data.All(condition1, condition2, condition3)
        >>> 
        >>> def strict_condition_strategy(self):
        >>>     all_signal = self.data.All(
        >>>         self.data.close > self.data.ema(50),
        >>>         self.data.volume > self.data.volume.ema(20),
        >>>         self.data.rsi(14) < 80
        >>>     )
        >>>     if all_signal.new:
        >>>         return "所有条件同时满足，强烈信号"
        """
        ...

    @tobtind(lines=None, lib="pta")
    def Where(self, cond, x=None, y=.0, **kwargs) -> IndSeries:
        """
        条件选择函数 (Conditional Selection)
        ---------
            根据条件选择返回值，类似numpy.where。
            符合条件cond的返回x，不符合的返回y。
            当x=None时，条件成立时返回自身数据。

        参数:
        ---------
        >>> cond: 条件表达式
            x: 条件成立时的返回值. 默认: None (返回自身数据)
            y: 条件不成立时的返回值. 默认: 0.0
            **kwargs: 其他参数

        返回:
        ---------
        >>> IndSeries: 条件选择结果序列

        使用案例:
        ---------
        >>> # 条件选择示例
        >>> rsi = self.data.rsi(length=14)
        >>> 
        >>> # RSI大于70时返回1，否则返回0
        >>> overbought_signal = self.data.Where(rsi > 70, 1, 0)
        >>> 
        >>> # RSI小于30时返回收盘价，否则返回0
        >>> oversold_value = self.data.Where(rsi < 30, self.data.close, 0)
        >>> 
        >>> def conditional_trading(self):
        >>>     # 价格在布林带上轨上方时返回布林带上轨值，否则返回收盘价
        >>>     bb = self.data.bbands(length=20)
        >>>     upper_band = bb.bb_upper
        >>>     adjusted_price = self.data.Where(
        >>>         self.data.close > upper_band,
        >>>         upper_band,  # 条件成立时返回上轨值
        >>>         self.data.close  # 条件不成立时返回收盘价
        >>>     )
        >>>     return f"调整后价格: {adjusted_price.new:.2f}"
        """
        ...

    @tobtind(lines=None, lib="pta")
    def line_trhend(self, period: int = 1, **kwargs) -> IndSeries:
        """
        指标线趋势判断 (Indicator Line Trend)
        ---------
            与前period个数据对比，判断当前值的趋势方向。
            比前值大为1，持平为0，小为-1。

        参数:
        ---------
        >>> period (int): 对比周期. 默认: 1
            **kwargs: 其他参数

        返回:
        ---------
        >>> IndSeries: 趋势方向序列 (1: 上升, 0: 持平, -1: 下降)

        使用案例:
        ---------
        >>> # 计算收盘价趋势
        >>> close_trend = self.data.line_trhend(period=1)
        >>> 
        >>> # 计算移动平均线趋势
        >>> ema_trend = self.data.ema(length=20).line_trhend(period=2)
        >>> 
        >>> def trend_analysis(self):
        >>>     # 分析RSI趋势
        >>>     rsi = self.data.rsi(length=14)
        >>>     rsi_trend = rsi.line_trhend(period=3)
        >>>     
        >>>     if rsi_trend.new == 1:
        >>>         return "RSI趋势向上"
        >>>     elif rsi_trend.new == -1:
        >>>         return "RSI趋势向下"
        >>>     else:
        >>>         return "RSI趋势持平"
        >>> 
        >>> # 多周期趋势分析
        >>> def multi_period_trend(self):
        >>>     short_trend = self.data.close.line_trhend(period=1)  # 短期趋势
        >>>     medium_trend = self.data.close.line_trhend(period=5)  # 中期趋势
        >>>     long_trend = self.data.close.line_trhend(period=10)  # 长期趋势
        >>>     
        >>>     # 多重时间框架趋势一致
        >>>     if short_trend.new == 1 and medium_trend.new == 1 and long_trend.new == 1:
        >>>         return "多重时间框架均显示上升趋势"
        """
        ...

    @tobtind(lines=['open', 'high', 'low', 'close'], category='candles')
    def abc(self, lim: float = 5., **kwargs) -> IndFrame:
        """
        ABC模式识别 (ABC Pattern Recognition)
        ---------
            识别K线图中的ABC模式。

        参数:
        ---------
        >>> lim (float): 限制参数. 默认: 5.0
            **kwargs: 其他参数

        返回:
        ---------
        >>> IndFrame: 包含open(开盘价), high(最高价), low(最低价), close(收盘价)列的数据框

        所需数据字段:
        ---------
        >>> open, high, low, close

        使用案例:
        ---------
        >>> # 识别ABC模式
        >>> open, high, low, close = self.data.abc(lim=5.0)
        >>> 
        >>> def abc_pattern_strategy(self):
        >>>     # 获取ABC模式数据
        >>>     open, high, low, close = self.data.abc(lim=5.0)
        >>>     
        >>>     # 分析ABC模式特征
        >>>     # 这里可以添加具体的ABC模式识别逻辑
        >>>     # 例如：寻找特定的高低点序列
        >>>     
        >>>     return "ABC模式分析完成"
        >>> 
        >>> # 结合其他指标使用
        >>> def abc_with_volume(self):
        >>>     abc_data = self.data.abc(lim=5.0)
        >>>     volume_ma = self.data.volume.ema(period=20)
        >>>     
        >>>     # 在ABC模式形成时成交量放大
        >>>     if abc_data.close.new > abc_data.close.prev and \
        >>>        self.data.volume.new > volume_ma.new:
        >>>         return "ABC模式伴随放量，信号增强"
        """
        ...

    @tobtind(lines=['thrend', 'line'])
    def insidebar(self, length: int = 10, **kwargs) -> IndFrame:
        """
        内包线模式识别 (Inside Bar Pattern Recognition)
        ---------
            识别K线图中的内包线模式。内包线是指当前K线的最高价和最低价
            完全包含在前一根K线的价格范围内。

        参数:
        ---------
        >>> length (int): 计算周期. 默认: 10
            **kwargs: 其他参数

        返回:
        ---------
        >>> IndFrame: 包含thrend(趋势), line(线)列的数据框

        所需数据字段:
        ---------
        >>> high, low, close

        使用案例:
        ---------
        >>> # 识别内包线模式
        >>> thrend, line = self.data.insidebar(length=10)
        >>> 
        >>> def insidebar_trading(self):
        >>>     # 获取内包线信号
        >>>     thrend, line = self.data.insidebar(length=10)
        >>>     
        >>>     # 内包线通常表示市场犹豫，可能预示着突破
        >>>     if thrend.new == 1:
        >>>         return "内包线显示看涨趋势"
        >>>     elif thrend.new == -1:
        >>>         return "内包线显示看跌趋势"
        >>> 
        >>> # 内包线突破策略
        >>> def insidebar_breakout(self):
        >>>     thrend, line = self.data.insidebar()
        >>>     
        >>>     # 内包线后的突破
        >>>     if thrend.new == 1 and self.data.close.new > self.data.high.prev:
        >>>         return "内包线后向上突破，买入信号"
        >>>     elif thrend.new == -1 and self.data.close.new < self.data.low.prev:
        >>>         return "内包线后向下跌破，卖出信号"
        >>> 
        >>> # 结合成交量确认
        >>> def insidebar_volume_confirmation(self):
        >>>     thrend, line = self.data.insidebar()
        >>>     
        >>>     # 内包线成交量萎缩，突破时放量
        >>>     if (thrend.new != 0 and 
        >>>         self.data.volume.new < self.data.volume.ema(period=20).new and
        >>>         self.data.volume.prev > self.data.volume.ema(period=20).prev):
        >>>         return "内包线缩量，突破放量，信号可靠"
        """
        ...


class BtInd:
    """### 自定义指标指引
    自定义指标类，用于封装项目中自定义的基础指标计算逻辑，提供框架兼容的指标访问接口

    核心功能：
    - 基于输入的基础数据（IndSeries/IndFrame）提供自定义指标的计算与访问
    - 通过 @tobtind 装饰器将原生数据转换为框架内置的指标数据类型（IndSeries/IndFrame）
    - 支持基础行情数据（开盘价、最高价、最低价等）的直接访问与指标化处理

    使用说明：
    1. 初始化：传入框架支持的基础数据对象（需包含对应的原始字段）
       >>> ind = self.data.btind.alerts()"""
    _df: IndSeries | IndFrame

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
    def alerts(self, length: int = 14, mult: float = 2., **kwargs) -> IndFrame:
        """alerts

            Args:
                data (IndFrame): 数据
                length (int, optional): 长度. Defaults to None.
                mult (float, optional): 乘数. Defaults to None.

            Returns:
                Union[IndFrame]: cols=['filt', 'hband', 'lband','dir']
        """
        ...

    @tobtind(lib='btind')
    def noises_density(self, length: int = 10, **kwargs) -> IndSeries:
        """价格密度函数

        NOTE:实例包含列 : high,low"""
        ...

    @tobtind(lib='btind')
    def noises_er(self, length: int = 10, **kwargs) -> IndSeries:
        """ER效率系数

        NOTE:实例包含列 : close"""
        ...

    @tobtind(lib='btind')
    def noises_fd(self, length: int = 10, **kwargs) -> IndSeries:
        """fractal dimension 分型维度
        NOTE:实例包含列 : high,low,close"""
        ...

    @tobtind(lines=None, lib='btind',)
    def kama(self, length=None, fast=None, slow=None, drift=None, offset=0, **kwargs) -> IndSeries | IndFrame:
        ...

    @tobtind(lines=['mama', 'fama'], lib='btind',)
    def mama(self, fastlimit: float = 0.6185, slowlimit: float = 0.06185, **kwargs) -> IndFrame:
        """mama

        NOTE:实例包含列 : close

        Args:
            close (IndSeries): 数据
            fastlimit (float, optional): 快线参数. Defaults to 0.6185.
            slowlimit (float, optional): 慢线参数. Defaults to 0.06185.

        Returns:
            IndFrame: cols=['mama', 'fama']
        """
        ...

    @tobtind(lines=['long', 'short', 'thrend'], overlap=dict(long=True, short=True, thrend=False), lib='btind',)
    def pmax(self, length: int = 14, mult: float = 3., mode: Literal[
        "dema", "ema", "fwma", "hma", "linreg", "midpoint", "pwma", "rma",
        "sinwma", "sma", "swma", "t3", "tema", "trima", "vidya", "wma", "zlma"
    ] = 'hma', dev: Literal["stdev", "art", "variance", "smoothrng"] = "stdev", **kwargs) -> IndFrame:
        """pmax
        ---
        NOTE:实例包含列 : close
        计算价格最大化指标(PMax)的第一个版本，生成多头和空头止损线以及趋势方向。

        该函数通过计算移动平均线和标准差来确定上下轨，然后根据价格与这些轨道的交互来确定趋势方向，
        并分别维护多头和空头的止损线。

        Args:
            length (int): 计算周期，默认为10，必须为正数
            mult (float): 标准差倍数，默认为3.0，必须为正数
            mode (str): 移动平均线类型，默认为'hma'，需为pta模块中存在的函数
            dev (str): 标准差计算方法，默认为'stdev'，需为pta模块中存在的函数
            **kwargs: 其他传递给移动平均线和标准差函数的参数

        Returns:
            IndFrame: cols=['long','short','thrend']
                - long: 多头止损线
                - short: 空头止损线
                - thrend: 趋势方向(1为多头，-1为空头)
            该DataFrame具有category属性，值为"overlap"

        与其他版本的区别:
            - 同时维护多头(long)和空头(short)两条止损线
            - 初始趋势方向固定为1(多头)
            - thrend直接反映当前趋势方向
        """
        ...

    @tobtind(lines=['pmax', 'thrend'], overlap=dict(pmax=True, thrend=False), lib='btind',)
    def pmax2(self, length: int = 14, mult: float = 3., mode: Literal[
        "dema", "ema", "fwma", "hma", "linreg", "midpoint", "pwma", "rma",
        "sinwma", "sma", "swma", "t3", "tema", "trima", "vidya", "wma", "zlma"
    ] = 'hma', dev: Literal["stdev", "art", "variance", "smoothrng"] = "stdev", **kwargs) -> IndFrame:
        """pmax2
        ---

        NOTE:实例包含列 : close

        计算价格最大化指标(PMax)的第二个版本，生成单一的PMax线和趋势方向。

        该函数是pmax的简化版本，将多头和空头止损线合并为单一的PMax线，根据趋势方向动态更新该线。

        Args:
            length (int): 计算周期，默认为10，必须为正数
            mult (float): 标准差倍数，默认为3.0，必须为正数
            mode (str): 移动平均线类型，默认为'hma'，需为pta模块中存在的函数
            dev (str): 标准差计算方法，默认为'stdev'，需为pta模块中存在的函数
            **kwargs: 其他传递给移动平均线和标准差函数的参数

        Returns:
            IndFrame: cols=['pmax','thrend']
                - pmax: 合并后的PMax线
                - thrend: 趋势方向(1为多头，-1为空头)

        与其他版本的区别:
            - 将多头和空头止损线合并为单一的pmax列
            - 初始趋势方向固定为1(多头)
            - length和mult参数默认值通过不同方式设置(使用None作为初始值)
            - thrend直接反映当前趋势方向
        """
        ...

    @tobtind(lines=['pmax', 'thrend'], overlap=dict(pmax=True, thrend=False), lib='btind',)
    def pmax3(self, length: int = 14, mult: float = 3., mode: Literal[
        "dema", "ema", "fwma", "hma", "linreg", "midpoint", "pwma", "rma",
        "sinwma", "sma", "swma", "t3", "tema", "trima", "vidya", "wma", "zlma"
    ] = 'hma', dev: Literal["stdev", "art", "variance", "smoothrng"] = "stdev", **kwargs) -> IndFrame:
        """pmax3
        ---

        NOTE:实例包含列 : close

        计算价格最大化指标(PMax)的第三个版本，生成改进的PMax线和趋势变化指标。

        该函数在pmax2的基础上进一步优化，使用不同的趋势判断逻辑和PMax线更新方式，
        并提供更细致的趋势变化指标。

        Args:
            length (int): 计算周期，默认为10，必须为正数
            mult (float): 标准差倍数，默认为3.0，必须为正数
            mode (str): 移动平均线类型，默认为'hma'，需为pta模块中存在的函数
            dev (str): 标准差计算方法，默认为'stdev'，需为pta模块中存在的函数
            **kwargs: 其他传递给移动平均线和标准差函数的参数

        Returns:
            IndFrame: cols=['pmax','thrend']
            - pmax: PMax线
            - thrend: 趋势变化(1为上升，-1为下降，与前值相同则保持不变)

        与其他版本的区别:
            - 使用数组存储完整的dir(方向)序列
            - thrend表示PMax线的变化趋势(上升/下降)，而非当前趋势方向
            - 初始PMax值设置为下轨(dn)的初始值
            - 趋势方向(dir)和PMax线的更新逻辑不同，使用向量化操作的风格
            - 对PMax线的更新使用更简洁的条件表达式
        """
        ...

    @tobtind(lib='btind')
    def pv(self, length=10, **kwargs) -> IndSeries:
        """NOTE:实例包含列 : close"""
        ...

    @tobtind(lib='btind')
    def realized(self, length: int = 10, **kwargs) -> IndSeries:
        """NOTE:实例包含列 : close"""
        ...

    @tobtind(lines=['rshl', 'rslh'], lib='btind')
    def rsrs(self, length: int = 10, method: Literal['r1', 'r2', 'r3'] = 'r1', weights=True, **kwargs) -> IndFrame:
        """NOTE:实例包含列 : high,low,volume
        lines = (rshl,rslh)"""
        ...

    @tobtind(overlap=True, lib='btind')
    def savitzky_golay(self, window_length: Any = 10, polyorder: Any = 2, deriv: int = 0, delta: float = 1, axis: int = -1, mode: str = 'interp', cval: float = 0, **kwargs) -> IndSeries:
        """
        NOTE:实例包含列 : close

        Apply a Savitzky-Golay filter to an array.

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
    def SuperTrend(self, length=14, multiplier=2., weights=2., **Kwargs) -> IndSeries:
        """NOTE:实例包含列 :high, low, close
        Returns:
        ---------
            >>> IndFrame: trend, dir, long, short columns."""
        ...

    @tobtind(category="overlap", lib='btind')
    def zigzag(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> IndSeries:
        """
        NOTE:实例包含列 :high, low, close
        Find the peaks and valleys of a IndSeries.
        zigzag:含nan数据
        zigzag_full:无nan数据
        # args:
        >>> param X: the IndSeries to analyze
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
    def zigzag_full(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> IndSeries:
        """
        NOTE:实例包含列 :high, low, close
        Find the peaks and valleys of a IndSeries.
        zigzag:含nan数据
        zigzag_full:无nan数据
        # args:
        >>> param X: the IndSeries to analyze
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
    def zigzag_modes(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> IndSeries:
        """
        NOTE:实例包含列 :high, low, close
        Translate pivots into trend modes.

        :param pivots: the result of calling ``peak_valley_pivots``
        :return: numpy array of trend modes. That is, between (VALLEY, PEAK] it
        is 1 and between (PEAK, VALLEY] it is -1.
        """
        ...

    @tobtind(lib='btind')
    def zigzag_returns(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., limit: bool = True, **kwargs) -> IndSeries:
        """
        NOTE:实例包含列 :high, low, close
        :return: numpy array of the pivot-to-pivot returns for each segment."""
        ...

    @tobtind(lines=["up", "dn", "bull", "bear", "signal"], lib="btind")
    def AndeanOsc(self, length: int = 14, signal_length: int = 9, **kwargs) -> IndFrame:
        """# Andean Oscillator
        A New Technical Indicator Based on An Online Algorithm For Trend Analysis

        NOTE:实例包含列 :open,close.

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
    def Coral_Trend_Candles(self, smooth: int = 9., mult: float = .4, **kwargs) -> IndSeries:
        """# Coral_Trend_Candles
        NOTE:实例包含列 :close

        >>> return:IndSeries
        """
        ...

    @tobtind(lines=["returns", "mean"], lib="btind")
    def signal_returns_stats(self, close=None, n: int = 1, **kwargs) -> IndFrame:
        """NOTE:实例包含列 :IndSeries

        根据信号计算后续n天的收益率，并统计列维度的总收益、最大总收益和平均总收益
        :param signal: 信号序列（仅含0和1），pd.Series，索引需与close对齐
        :param close: 收盘价序列，pd.Series
        :param n: 统计天数（正整数）
        :return: IndFrame,lines=["returns","mean"]
        """
        ...

    @tobtind(lines=["up_prob", "sideways_prob", "down_prob"], lib="btind")
    def calculate_trend_probabilities(self, window_length=60,
                                      up_threshold=0.001,
                                      down_threshold=-0.001, **kwargs):
        ...

    @tobtind(lines=["gap_ratio", "upper_hl", "lower_hl", "signal"], overlap=dict(gap_ratio=False, upper_hl=True, lower_hl=True, signal=False), lib="btind")
    def gap_ratio(self, length=20, **kwargs) -> IndFrame:
        """### 计算通道差异系数GapRatio
        args:open,high,low,close"""
        ...


class TuLip:
    """## Tulip Indicators
    https://tulipindicators.org/"""
    _df: IndSeries | IndFrame

    def __init__(self, data):
        self._df = data

    @tobtind(lib="ti")
    def abs(self, **kwargs) -> IndSeries:
        """### Vector Absolute Value
        https://tulipindicators.org/abs

        计算向量的绝对值。

        Returns:
            IndSeries: 输入序列的绝对值结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def acos(self, **kwargs) -> IndSeries:
        """### Vector Arccosine
        https://tulipindicators.org/acos

        计算向量的反余弦值。

        Returns:
            IndSeries: 输入序列的反余弦结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def ad(self, **kwargs) -> IndSeries:
        """### Accumulation/Distribution Line
        https://tulipindicators.org/ad

        计算累积/派发线指标。

        Returns:
            IndSeries: 累积/派发线的计算结果。

        Note:
            实例包含列：high, low, close, volume
        """
        ...

    @tobtind(lib="ti")
    def add(self, IndSeries=None, **kwargs) -> IndSeries:
        """### Vector Addition
        https://tulipindicators.org/add

        实现向量加法运算。

        Args:
            IndSeries (int | float | IndSeries | np.ndarray): 用于加法运算的数值或序列

        Returns:
            IndSeries: 向量加法的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def adosc(self, short_period=10, long_period=10, **kwargs) -> IndSeries:
        """### Accumulation/Distribution Oscillator
        https://tulipindicators.org/adosc

        计算累积/派发震荡指标。

        Args:
            short_period (int): 短期周期，默认值为10
            long_period (int): 长期周期，默认值为10

        Returns:
            IndSeries: 累积/派发震荡指标的计算结果。

        Note:
            实例包含列：high, low, close, volume
        """
        ...

    @tobtind(lib="ti")
    def adx(self, period=10, **kwargs) -> IndSeries:
        """### Average Directional Movement Index
        https://tulipindicators.org/adx

        计算平均趋向指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 平均趋向指标的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def adxr(self, period=10, **kwargs) -> IndSeries:
        """### Average Directional Movement Rating
        https://tulipindicators.org/adxr

        计算平均趋向指标评级。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 平均趋向指标评级的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def ao(self, **kwargs) -> IndSeries:
        """### Awesome Oscillator
        https://tulipindicators.org/ao

        计算动量震荡指标。

        Returns:
            IndSeries: 动量震荡指标的计算结果。

        Note:
            实例包含列：high, low
        """
        ...

    @tobtind(lib="ti")
    def apo(self, short_period=10, long_period=10, **kwargs) -> IndSeries:
        """### Absolute Price Oscillator
        https://tulipindicators.org/apo

        计算绝对价格震荡指标。

        Args:
            short_period (int): 短期周期，默认值为10
            long_period (int): 长期周期，默认值为10

        Returns:
            IndSeries: 绝对价格震荡指标的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lines=["aroondown", "aroonup"], lib="ti")
    def aroon(self, period=10, **kwargs) -> IndFrame:
        """### Aroon
        https://tulipindicators.org/aroon

        计算阿隆指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndFrame: 包含阿隆下行（aroondown）和阿隆上行（aroonup）的结果数据框。

        Note:
            实例包含列：high, low
        """
        ...

    @tobtind(lib="ti")
    def aroonosc(self, period=10, **kwargs) -> IndSeries:
        """### Aroon Oscillator
        https://tulipindicators.org/aroonosc

        计算阿隆震荡指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 阿隆震荡指标的计算结果。

        Note:
            实例包含列：high, low
        """
        ...

    @tobtind(lib="ti")
    def asin(self, **kwargs) -> IndSeries:
        """### Vector Arcsine
        https://tulipindicators.org/asin

        计算向量的反正弦值。

        Returns:
            IndSeries: 输入序列的反正弦结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def atan(self, **kwargs) -> IndSeries:
        """### Vector Arctangent
        https://tulipindicators.org/atan

        计算向量的反正切值。

        Returns:
            IndSeries: 输入序列的反正切结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def atr(self, period=10, **kwargs) -> IndSeries:
        """### Average True Range
        https://tulipindicators.org/atr

        计算平均真实波幅。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 平均真实波幅的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def avgprice(self, **kwargs) -> IndSeries:
        """### Average Price
        https://tulipindicators.org/avgprice

        计算平均价格。

        Returns:
            IndSeries: 平均价格的计算结果。

        Note:
            实例包含列：open, high, low, close
        """
        ...

    @tobtind(lines=["upperband", "middleband", "lowerband"], lib="ti")
    def bbands(self, period=10, stddev=1., **kwargs) -> IndFrame:
        """### Bollinger Bands
        https://tulipindicators.org/bbands

        计算布林带指标。

        Args:
            period (int): 计算周期，默认值为10
            stddev (float): 标准差倍数，默认值为1.0

        Returns:
            IndFrame: 包含上轨（upperband）、中轨（middleband）和下轨（lowerband）的结果数据框。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def bop(self, **kwargs) -> IndSeries:
        """### Balance of Power
        https://tulipindicators.org/bop

        计算动力平衡指标。

        Returns:
            IndSeries: 动力平衡指标的计算结果。

        Note:
            实例包含列：open, high, low, close
        """
        ...

    @tobtind(lib="ti")
    def cci(self, period=10, **kwargs) -> IndSeries:
        """### Commodity Channel Index
        https://tulipindicators.org/cci

        计算商品通道指数。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 商品通道指数的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def ceil(self, **kwargs) -> IndSeries:
        """### Vector Ceiling
        https://tulipindicators.org/ceil

        计算向量的向上取整值。

        Returns:
            IndSeries: 输入序列的向上取整结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def cmo(self, period=10, **kwargs) -> IndSeries:
        """### Chande Momentum Oscillator
        https://tulipindicators.org/cmo

        计算钱德动量震荡指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 钱德动量震荡指标的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def cos(self, **kwargs) -> IndSeries:
        """### Vector Cosine
        https://tulipindicators.org/cos

        计算向量的余弦值。

        Returns:
            IndSeries: 输入序列的余弦结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def cosh(self, **kwargs) -> IndSeries:
        """### Vector Hyperbolic Cosine
        https://tulipindicators.org/cosh

        计算向量的双曲余弦值。

        Returns:
            IndSeries: 输入序列的双曲余弦结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def crossany(self, IndSeries=None, **kwargs) -> IndSeries:
        """### Crossany
        https://tulipindicators.org/crossany

        判断向量是否与目标序列交叉。

        Args:
            IndSeries (IndSeries | np.ndarray | int | float): 用于交叉判断的目标序列或数值

        Returns:
            IndSeries: 交叉判断结果（布尔值序列）。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def crossover(self, IndSeries=None, **kwargs) -> IndSeries:
        """### Crossover
        https://tulipindicators.org/crossover

        判断向量是否上穿目标序列。

        Args:
            IndSeries (IndSeries | np.ndarray | int | float): 用于上穿判断的目标序列或数值

        Returns:
            IndSeries: 上穿判断结果（布尔值序列）。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def cvi(self, period=10, **kwargs) -> IndSeries:
        """### Chaikins Volatility
        https://tulipindicators.org/cvi

        计算柴金波动率指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 柴金波动率指标的计算结果。

        Note:
            实例包含列：high, low
        """
        ...

    @tobtind(lib="ti")
    def decay(self, period=10, **kwargs) -> IndSeries:
        """### Linear Decay
        https://tulipindicators.org/decay

        计算线性衰减值。

        Args:
            period (int): 衰减周期，默认值为10

        Returns:
            IndSeries: 线性衰减的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def dema(self, period=10, **kwargs) -> IndSeries:
        """### Double Exponential Moving Average
        https://tulipindicators.org/dema

        计算双指数移动平均线。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 双指数移动平均线的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lines=["plus_di", "minus_di"], lib="ti")
    def di(self, period=10, **kwargs) -> IndFrame:
        """### Directional Indicator
        https://tulipindicators.org/di

        计算趋向指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndFrame: 包含正趋向指标（plus_di）和负趋向指标（minus_di）的结果数据框。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def div(self, IndSeries=None, **kwargs) -> IndSeries:
        """### Vector Division
        https://tulipindicators.org/div

        实现向量除法运算。

        Args:
            IndSeries (IndSeries | np.ndarray | int | float): 用于除法运算的数值或序列

        Returns:
            IndSeries: 向量除法的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lines=['dmp', 'dmn'], lib="ti")
    def dm(self, period=10, **kwargs) -> IndFrame:
        """### Directional Movement
        https://tulipindicators.org/dm

        计算趋向运动值。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndFrame: 包含正趋向运动（dmp）和负趋向运动（dmn）的结果数据框。

        Note:
            实例包含列：high, low
        """
        ...

    @tobtind(lib="ti")
    def dpo(self, period=10, **kwargs) -> IndSeries:
        """### Detrended Price Oscillator
        https://tulipindicators.org/dpo

        计算去趋势价格震荡指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 去趋势价格震荡指标的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def dx(self, period=10, **kwargs) -> IndSeries:
        """### Directional Movement Index
        https://tulipindicators.org/dx

        计算趋向运动指数。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 趋向运动指数的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def edecay(self, period=10, **kwargs) -> IndSeries:
        """### Exponential Decay
        https://tulipindicators.org/edecay

        计算指数衰减值。

        Args:
            period (int): 衰减周期，默认值为10

        Returns:
            IndSeries: 指数衰减的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def ema(self, period=10, **kwargs) -> IndSeries:
        """### Exponential Moving Average
        https://tulipindicators.org/ema

        计算指数移动平均线。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 指数移动平均线的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def emv(self, **kwargs) -> IndSeries:
        """### Ease of Movement
        https://tulipindicators.org/emv

        计算简易移动指标。

        Returns:
            IndSeries: 简易移动指标的计算结果。

        Note:
            实例包含列：high, low, volume
        """
        ...

    @tobtind(lib="ti")
    def exp(self, **kwargs) -> IndSeries:
        """### Vector Exponential
        https://tulipindicators.org/exp

        计算向量的指数值。

        Returns:
            IndSeries: 输入序列的指数结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lines=['fisher', 'fishers'], lib="ti")
    def fisher(self, period=10, **kwargs) -> IndFrame:
        """### Fisher Transform
        https://tulipindicators.org/fisher

        计算费希尔变换指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndFrame: 包含费希尔变换值（fisher）和信号值（fishers）的结果数据框。

        Note:
            实例包含列：high, low
        """
        ...

    @tobtind(lib="ti")
    def floor(self, **kwargs) -> IndSeries:
        """### Vector Floor
        https://tulipindicators.org/floor

        计算向量的向下取整值。

        Returns:
            IndSeries: 输入序列的向下取整结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def fosc(self, period=10, **kwargs) -> IndSeries:
        """### Forecast Oscillator
        https://tulipindicators.org/fosc

        计算预测震荡指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 预测震荡指标的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def hma(self, period=10, **kwargs) -> IndSeries:
        """### Hull Moving Average
        https://tulipindicators.org/hma

        计算赫尔移动平均线。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 赫尔移动平均线的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def kama(self, period=10, **kwargs) -> IndSeries:
        """### Kaufman Adaptive Moving Average
        https://tulipindicators.org/kama

        计算考夫曼自适应移动平均线。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 考夫曼自适应移动平均线的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def kvo(self, short_period=10, long_period=10, **kwargs) -> IndSeries:
        """### Klinger Volume Oscillator
        https://tulipindicators.org/kvo

        计算克林格成交量震荡指标。

        Args:
            short_period (int): 短期周期，默认值为10
            long_period (int): 长期周期，默认值为10

        Returns:
            IndSeries: 克林格成交量震荡指标的计算结果。

        Note:
            实例包含列：high, low, close, volume
        """
        ...

    @tobtind(lib="ti")
    def lag(self, period=10, **kwargs) -> IndSeries:
        """### Lag
        https://tulipindicators.org/lag

        计算序列的滞后值。

        Args:
            period (int): 滞后周期，默认值为10

        Returns:
            IndSeries: 滞后处理后的序列结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def linreg(self, period=10, **kwargs) -> IndSeries:
        """### Linear Regression
        https://tulipindicators.org/linreg

        计算线性回归拟合值。

        Args:
            period (int): 回归周期，默认值为10

        Returns:
            IndSeries: 线性回归拟合的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def linregintercept(self, period=10, **kwargs) -> IndSeries:
        """### Linear Regression Intercept
        https://tulipindicators.org/linregintercept

        计算线性回归截距。

        Args:
            period (int): 回归周期，默认值为10

        Returns:
            IndSeries: 线性回归截距的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def linregslope(self, period=10, **kwargs) -> IndSeries:
        """### Linear Regression Slope
        https://tulipindicators.org/linregslope

        计算线性回归斜率。

        Args:
            period (int): 回归周期，默认值为10

        Returns:
            IndSeries: 线性回归斜率的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def ln(self, **kwargs) -> IndSeries:
        """### Vector Natural Log
        https://tulipindicators.org/ln

        计算向量的自然对数。

        Returns:
            IndSeries: 输入序列的自然对数结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def log10(self, **kwargs) -> IndSeries:
        """### Vector Base-10 Log
        https://tulipindicators.org/log10

        计算向量的以10为底的对数。

        Returns:
            IndSeries: 输入序列的10底对数结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lines=["macdx", "macdh", "macds"], lib="ti")
    def macd(self, short_period=12, long_period=26, signal_period=9, **kwargs) -> IndFrame:
        """### Moving Average Convergence/Divergence
        https://tulipindicators.org/macd

        计算指数平滑异同移动平均线（MACD）。

        Args:
            short_period (int): 短期EMA周期，默认值为12
            long_period (int): 长期EMA周期，默认值为26
            signal_period (int): 信号EMA周期，默认值为9

        Returns:
            IndFrame: 包含MACD线（macdx）、MACD柱状线（macdh）和信号线（macds）的结果数据框。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def marketfi(self, **kwargs) -> IndSeries:
        """### Market Facilitation Index
        https://tulipindicators.org/marketfi

        计算市场便利指数。

        Returns:
            IndSeries: 市场便利指数的计算结果。

        Note:
            实例包含列：high, low, volume
        """
        ...

    @tobtind(lib="ti")
    def mass(self, period=10, **kwargs) -> IndSeries:
        """### Mass Index
        https://tulipindicators.org/mass

        计算质量指数。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 质量指数的计算结果。

        Note:
            实例包含列：high, low
        """
        ...

    @tobtind(lib="ti")
    def max(self, period=10, **kwargs) -> IndSeries:
        """### Maximum In Period
        https://tulipindicators.org/max

        计算周期内的最大值。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 周期内最大值的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def md(self, period=10, **kwargs) -> IndSeries:
        """### Mean Deviation Over Period
        https://tulipindicators.org/md

        计算周期内的平均偏差。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 周期内平均偏差的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def medprice(self, **kwargs) -> IndSeries:
        """### Median Price
        https://tulipindicators.org/medprice

        计算中位数价格。

        Returns:
            IndSeries: 中位数价格的计算结果。

        Note:
            实例包含列：high, low
        """
        ...

    @tobtind(lib="ti")
    def mfi(self, period=10, **kwargs) -> IndSeries:
        """### Money Flow Index
        https://tulipindicators.org/mfi

        计算资金流向指数。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 资金流向指数的计算结果。

        Note:
            实例包含列：high, low, close, volume
        """
        ...

    @tobtind(lib="ti")
    def min(self, period=10, **kwargs) -> IndSeries:
        """### Minimum In Period
        https://tulipindicators.org/min

        计算周期内的最小值。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 周期内最小值的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def mom(self, period=10, **kwargs) -> IndSeries:
        """### Momentum
        https://tulipindicators.org/mom

        计算动量指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 动量指标的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lines=["msw_sine", "msw_lead"], lib="ti")
    def msw(self, period=10, **kwargs) -> IndFrame:
        """### Mesa Sine Wave
        https://tulipindicators.org/msw

        计算梅萨正弦波指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndFrame: 包含正弦波值（msw_sine）和领先值（msw_lead）的结果数据框。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def mul(self, IndSeries=None, **kwargs) -> IndSeries:
        """### Vector Multiplication
        https://tulipindicators.org/mul

        实现向量乘法运算。

        Args:
            IndSeries (IndSeries | np.ndarray | int | float): 用于乘法运算的数值或序列

        Returns:
            IndSeries: 向量乘法的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def natr(self, period=10, **kwargs) -> IndSeries:
        """### Normalized Average True Range
        https://tulipindicators.org/natr

        计算归一化平均真实波幅。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 归一化平均真实波幅的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def nvi(self, **kwargs) -> IndSeries:
        """### Negative Volume Index
        https://tulipindicators.org/nvi

        计算负成交量指数。

        Returns:
            IndSeries: 负成交量指数的计算结果。

        Note:
            实例包含列：close, volume
        """
        ...

    @tobtind(lib="ti")
    def obv(self, **kwargs) -> IndSeries:
        """### On Balance Volume
        https://tulipindicators.org/obv

        计算能量潮指标。

        Returns:
            IndSeries: 能量潮指标的计算结果。

        Note:
            实例包含列：close, volume
        """
        ...

    @tobtind(lib="ti")
    def ppo(self, short_period=10, long_period=10, **kwargs) -> IndSeries:
        """### Percentage Price Oscillator
        https://tulipindicators.org/ppo

        计算百分比价格震荡指标。

        Args:
            short_period (int): 短期周期，默认值为10
            long_period (int): 长期周期，默认值为10

        Returns:
            IndSeries: 百分比价格震荡指标的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def psar(self, acceleration_factor_step=0.06185, acceleration_factor_maximum=0.6185, **kwargs):
        """### Parabolic SAR
        https://tulipindicators.org/psar

        计算抛物线转向指标（SAR）。

        Args:
            acceleration_factor_step (float): 加速因子步长，默认值为0.06185
            acceleration_factor_maximum (float): 加速因子最大值，默认值为0.6185

        Returns:
            IndSeries: 抛物线转向指标的计算结果。

        Note:
            实例包含列：high, low
        """
        ...

    @tobtind(lib="ti")
    def qstick(self, period=10, **kwargs) -> IndSeries:
        """### Qstick
        https://tulipindicators.org/qstick

        计算Qstick指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: Qstick指标的计算结果。

        Note:
            实例包含列：open, close
        """
        ...

    @tobtind(lib="ti")
    def roc(self, period=10, **kwargs) -> IndSeries:
        """### Rate of Change
        https://tulipindicators.org/roc

        计算变化率指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 变化率指标的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def rocr(self, period=10, **kwargs) -> IndSeries:
        """### Rate of Change Ratio
        https://tulipindicators.org/rocr

        计算变化率比率指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 变化率比率指标的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def round(self, **kwargs) -> IndSeries:
        """### Vector Round
        https://tulipindicators.org/round

        计算向量的四舍五入值。

        Returns:
            IndSeries: 输入序列的四舍五入结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def rsi(self, period=10, **kwargs) -> IndSeries:
        """### Relative Strength Index
        https://tulipindicators.org/rsi

        计算相对强弱指数。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 相对强弱指数的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def sin(self, **kwargs) -> IndSeries:
        """### Vector Sine
        https://tulipindicators.org/sin

        计算向量的正弦值。

        Returns:
            IndSeries: 输入序列的正弦结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def sinh(self, **kwargs) -> IndSeries:
        """### Vector Hyperbolic Sine
        https://tulipindicators.org/sinh

        计算向量的双曲正弦值。

        Returns:
            IndSeries: 输入序列的双曲正弦结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def sma(self, period=10, **kwargs) -> IndSeries:
        """### Simple Moving Average
        https://tulipindicators.org/sma

        计算简单移动平均线。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 简单移动平均线的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def sqrt(self, **kwargs) -> IndSeries:
        """### Vector Square Root
        https://tulipindicators.org/sqrt

        计算向量的平方根。

        Returns:
            IndSeries: 输入序列的平方根结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def stddev(self, period=10, **kwargs) -> IndSeries:
        """### Standard Deviation Over Period
        https://tulipindicators.org/stddev

        计算周期内的标准差。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 周期内标准差的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def stderr(self, period=10, **kwargs) -> IndSeries:
        """### Standard Error Over Period
        https://tulipindicators.org/stderr

        计算周期内的标准误差。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 周期内标准误差的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lines=["stoch_k", "stoch_d"], lib="ti")
    def stoch(self, pct_k_period=5, pct_k_slowing_period=3, pct_d_period=3, **kwargs) -> IndFrame:
        """### Stochastic Oscillator
        https://tulipindicators.org/stoch

        计算随机震荡指标。

        Args:
            pct_k_period (int): %K周期，默认值为5
            pct_k_slowing_period (int): %K放缓周期，默认值为3
            pct_d_period (int): %D周期，默认值为3

        Returns:
            IndFrame: 包含%K值（stoch_k）和%D值（stoch_d）的结果数据框。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def stochrsi(self, period=10, **kwargs) -> IndSeries:
        """### Stochastic RSI
        https://tulipindicators.org/stochrsi

        计算随机相对强弱指数。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 随机相对强弱指数的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def sub(self, IndSeries=None, **kwargs) -> IndSeries:
        """### Vector Subtraction
        https://tulipindicators.org/sub

        实现向量减法运算。

        Args:
            IndSeries (IndSeries | np.ndarray | int | float): 用于减法运算的数值或序列

        Returns:
            IndSeries: 向量减法的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def sum(self, period=10, **kwargs) -> IndSeries:
        """### Sum Over Period
        https://tulipindicators.org/sum

        计算周期内的总和。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 周期内总和的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def tan(self, **kwargs) -> IndSeries:
        """### Vector Tangent
        https://tulipindicators.org/tan

        计算向量的正切值。

        Returns:
            IndSeries: 输入序列的正切结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def tanh(self, **kwargs) -> IndSeries:
        """### Vector Hyperbolic Tangent
        https://tulipindicators.org/tanh

        计算向量的双曲正切值。

        Returns:
            IndSeries: 输入序列的双曲正切结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def tema(self, period=10, **kwargs) -> IndSeries:
        """### Triple Exponential Moving Average
        https://tulipindicators.org/tema

        计算三重指数移动平均线。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 三重指数移动平均线的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def todeg(self, **kwargs) -> IndSeries:
        """### Vector Degree Conversion
        https://tulipindicators.org/todeg

        将弧度转换为角度。

        Returns:
            IndSeries: 弧度转角度的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def torad(self, **kwargs) -> IndSeries:
        """### Vector Radian Conversion
        https://tulipindicators.org/torad

        将角度转换为弧度。

        Returns:
            IndSeries: 角度转弧度的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def tr(self, **kwargs) -> IndSeries:
        """### True Range
        https://tulipindicators.org/tr

        计算真实波幅。

        Returns:
            IndSeries: 真实波幅的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def trima(self, period=10, **kwargs) -> IndSeries:
        """### Triangular Moving Average
        https://tulipindicators.org/trima

        计算三角形移动平均线。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 三角形移动平均线的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def trix(self, period=10, **kwargs) -> IndSeries:
        """### Trix
        https://tulipindicators.org/trix

        计算三重指数平滑指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 三重指数平滑指标的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def trunc(self, **kwargs) -> IndSeries:
        """### Vector Truncate
        https://tulipindicators.org/trunc

        计算向量的截断值（向零取整）。

        Returns:
            IndSeries: 输入序列的截断结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def tsf(self, period=10, **kwargs) -> IndSeries:
        """### Time Series Forecast
        https://tulipindicators.org/tsf

        计算时间序列预测值。

        Args:
            period (int): 预测周期，默认值为10

        Returns:
            IndSeries: 时间序列预测的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def typprice(self, **kwargs) -> IndSeries:
        """### Typical Price
        https://tulipindicators.org/typprice

        计算典型价格。

        Returns:
            IndSeries: 典型价格的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def ultosc(self, short_period=2, medium_period=3, long_period=5, **kwargs) -> IndSeries:
        """### Ultimate Oscillator
        https://tulipindicators.org/ultosc

        计算终极震荡指标。

        Args:
            short_period (int): 短期周期，默认值为2
            medium_period (int): 中期周期，默认值为3
            long_period (int): 长期周期，默认值为5

        Returns:
            IndSeries: 终极震荡指标的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def var(self, period=10, **kwargs) -> IndSeries:
        """### Variance Over Period
        https://tulipindicators.org/var

        计算周期内的方差。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 周期内方差的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def vhf(self, period=10, **kwargs) -> IndSeries:
        """### Vertical Horizontal Filter
        https://tulipindicators.org/vhf

        计算垂直水平过滤器指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 垂直水平过滤器指标的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def vidya(self, short_period=2, long_period=5, alpha=0.2) -> IndSeries:
        """### Variable Index Dynamic Average
        https://tulipindicators.org/vidya

        计算可变指数动态平均线。

        Args:
            short_period (int): 短期周期，默认值为2
            long_period (int): 长期周期，默认值为5
            alpha (float): 平滑系数，默认值为0.2

        Returns:
            IndSeries: 可变指数动态平均线的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def volatility(self, period=10, **kwargs) -> IndSeries:
        """### Annualized Historical Volatility
        https://tulipindicators.org/volatility

        计算年化历史波动率。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 年化历史波动率的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def vosc(self, short_period=2, long_period=5, **kwargs) -> IndSeries:
        """### Volume Oscillator
        https://tulipindicators.org/vosc

        计算成交量震荡指标。

        Args:
            short_period (int): 短期周期，默认值为2
            long_period (int): 长期周期，默认值为5

        Returns:
            IndSeries: 成交量震荡指标的计算结果。

        Note:
            实例包含列：volume
        """
        ...

    @tobtind(lib="ti")
    def vwma(self, period=10, **kwargs) -> IndSeries:
        """### Volume Weighted Moving Average
        https://tulipindicators.org/vwma

        计算成交量加权移动平均线。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 成交量加权移动平均线的计算结果。

        Note:
            实例包含列：close, volume
        """
        ...

    @tobtind(lib="ti")
    def wad(self, **kwargs) -> IndSeries:
        """### Williams Accumulation/Distribution
        https://tulipindicators.org/wad

        计算威廉姆斯累积/派发指标。

        Returns:
            IndSeries: 威廉姆斯累积/派发指标的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def wcprice(self, **kwargs) -> IndSeries:
        """### Weighted Close Price
        https://tulipindicators.org/wcprice

        计算加权收盘价。

        Returns:
            IndSeries: 加权收盘价的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def wilders(self, period=10, **kwargs) -> IndSeries:
        """### Wilders Smoothing
        https://tulipindicators.org/wilders

        计算威尔德平滑值。

        Args:
            period (int): 平滑周期，默认值为10

        Returns:
            IndSeries: 威尔德平滑的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def willr(self, period=10, **kwargs) -> IndSeries:
        """### Williams %R
        https://tulipindicators.org/willr

        计算威廉姆斯%R指标。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 威廉姆斯%R指标的计算结果。

        Note:
            实例包含列：high, low, close
        """
        ...

    @tobtind(lib="ti")
    def wma(self, period=10, **kwargs) -> IndSeries:
        """### Weighted Moving Average
        https://tulipindicators.org/wma

        计算加权移动平均线。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 加权移动平均线的计算结果。

        Note:
            实例包含列：close
        """
        ...

    @tobtind(lib="ti")
    def zlema(self, period=10, **kwargs) -> IndSeries:
        """### Zero-Lag Exponential Moving Average
        https://tulipindicators.org/zlema

        计算零滞后指数移动平均线。

        Args:
            period (int): 计算周期，默认值为10

        Returns:
            IndSeries: 零滞后指数移动平均线的计算结果。

        Note:
            实例包含列：close
        """
        ...


class TqFunc:
    """### 天勤序列计算函数类

    官方文档：https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tafunc.html

    封装天勤量化(TqSdk)的序列计算函数库，为技术指标和策略开发提供基础数学运算能力。

    核心功能：
    - 序列位移计算：提供时间序列的滞后、超前等位移操作
    - 统计量计算：包含均值、标准差、极值等统计函数
    - 逻辑判断：支持交叉信号、条件计数等逻辑运算
    - 移动平均：多种类型的移动平均计算方法
    - 时间处理：时间格式转换和时间戳处理工具

    使用说明：
    1. 初始化：传入minibt框架兼容的Series或DataFrame数据对象
    >>> data = IndFrame(...)  # 包含OHLCV等基础字段的minibt数据对象
        tq = TqFunc(data)

    2. 函数调用：直接调用对应函数方法，支持参数自定义
    >>> prev_close = tq.ref(length=1)        # 获取前一期收盘价
        ma_20 = tq.ma(length=20)             # 20周期简单移动平均

    技术特点：
    - 天勤兼容：基于天勤官方函数库，确保计算准确性
    - 序列优化：针对金融时间序列数据特殊优化
    - 向量计算：支持批量数据处理，计算效率高
    - 边界处理：自动处理数据边界和缺失值情况
    - 类型安全：确保输入输出数据格式一致性
    """
    _df: IndSeries | IndFrame

    def __init__(self, data):
        self._df = data

    @tobtind(lib='tqfunc')
    def ref(self, length=10, **kwargs) -> IndSeries:
        """
        序列位移函数 - 计算序列的滞后值，获取指定周期前的数据

        功能：
            将输入序列向右平移指定周期数，实现滞后计算，用于获取历史数据参考

        应用场景：
            - 计算价格变化率（当前价 vs 前期价）
            - 构建动量指标
            - 计算技术指标的信号线
            - 数据预处理和特征工程

        计算原理：
            ref(IndSeries, n)[i] = IndSeries[i - n]
            将序列向右移动n个位置，前n个位置填充NaN

        参数：
            length: 位移周期数，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 当length=0时，返回原序列
            - 当序列长度不足length+1时，返回NaN
            - 默认使用实例初始化时的数据列

        返回值：
            IndSeries: 位移后的序列

        示例：
            # 计算涨跌幅 = (当前收盘价 - 前一日收盘价) / 前一日收盘价
            prev_close = tq.ref(length=1)
            price_change = (close - prev_close) / prev_close

            # 动量计算（当前价格与N日前价格比较）
            price_10_days_ago = tq.ref(length=10)
            momentum_10 = close - price_10_days_ago
        """
        ...

    @tobtind(lib='tqfunc')
    def std(self, length: int = 10, **kwargs) -> IndSeries:
        """
        标准差计算 - 求序列每n个周期的标准差

        功能：
            计算滚动窗口内的标准差，衡量数据的离散程度

        应用场景：
            - 波动率测量和风险评估
            - 布林带宽度计算
            - 数据异常检测
            - 技术指标的稳定性评估

        计算原理：
            std(x, n) = sqrt(sum((x - mean(x, n))^2) / (n - 1))
            计算无偏估计的标准差

        参数：
            length: 计算周期，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 使用n-1作为分母（样本标准差）
            - 窗口长度不足时返回NaN
            - 对异常值比平均绝对偏差更敏感

        返回值：
            IndSeries: 标准差序列

        示例：
            # 计算价格波动率
            price_volatility = tq.std(close, length=20)

            # 构建布林带
            middle_band = tq.ma(close, length=20)
            std_dev = tq.std(close, length=20)
            upper_band = middle_band + 2 * std_dev
            lower_band = middle_band - 2 * std_dev

            # 波动率突破策略
            low_vol_period = price_volatility < tq.ma(price_volatility, length=50)
            high_vol_period = price_volatility > tq.ma(price_volatility, length=50)
        """

    @tobtind(lib='tqfunc')
    def ma(self, length: int = 10, **kwargs) -> IndSeries:
        """
        简单移动平均函数 - 计算序列的简单移动平均值

        功能：
            计算滚动窗口内的算术平均值，是最基础的平滑和趋势识别工具

        应用场景：
            - 价格趋势识别和确认
            - 支撑阻力位构建
            - 均线交叉策略
            - 数据平滑和噪音过滤

        计算原理：
            ma(x, n) = (x₁ + x₂ + ... + xₙ) / n
            计算窗口内所有值的简单算术平均

        参数：
            length: 计算周期，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 所有历史数据权重相等
            - 对价格突变的反应较慢
            - 窗口长度不足时返回NaN

        返回值：
            IndSeries: 简单移动平均值序列

        示例：
            # 计算基础移动平均线
            ma_20 = tq.ma(close, length=20)
            ma_50 = tq.ma(close, length=50)

            # 均线交叉策略
            golden_cross = tq.crossup(ma_20, ma_50)
            death_cross = tq.crossdown(ma_20, ma_50)

            # 价格与均线关系分析
            above_ma = close > ma_20
            below_ma = close < ma_20
        """
        ...

    @tobtind(lib='tqfunc')
    def sma(self, n: int = 10, m: int = 2, **kwargs) -> IndSeries:
        """
        扩展指数加权移动平均函数 - 计算序列的扩展指数加权移动平均值

        功能：
            结合简单移动平均和指数移动平均的特点，提供可调节的平滑程度

        应用场景：
            - 需要调节平滑程度的技术指标
            - 自适应趋势跟踪系统
            - 自定义滤波器设计
            - 多时间框架分析

        计算原理：
            sma(x, n, m) = sma(x, n, m).shift(1) × (n - m)/n + x(n) × m/n
            递归计算，结合历史值和当前值的加权平均

        参数：
            n: 计算周期，默认10
            m: 平滑系数，默认2
            **kwargs: 额外参数，可指定其他序列

        注意：
            - n必须大于m
            - m值越大，对近期数据权重越高
            - 提供了介于SMA和EMA之间的平滑特性

        返回值：
            IndSeries: 扩展指数加权移动平均值序列

        示例：
            # 计算扩展指数移动平均
            sma_fast = tq.sma(n=5, m=3)   # 较快响应
            sma_slow = tq.sma(n=20, m=5)  # 较慢响应

            # 自适应趋势系统
            trend_strength = ...  # 趋势强度指标
            adaptive_sma = tq.sma(n=10, m=trend_strength)

            # 多参数组合分析
            for m_val in [1, 2, 3]:
                sma_IndSeries = tq.sma(n=10, m=m_val)
        """
        ...

    @tobtind(lib='tqfunc')
    def ema(self, length: int = 10, **kwargs) -> IndSeries:
        """
        指数加权移动平均函数 - 计算序列的指数加权移动平均值

        功能：
            给予近期数据更高权重，更快响应价格变化，减少滞后性

        应用场景：
            - 快速趋势识别
            - 短线交易信号
            - 动量指标计算
            - 实时交易系统

        计算原理：
            ema(x, n) = 2/(n+1) × x + (1 - 2/(n+1)) × ema(x, n).shift(1)
            指数衰减权重，近期数据影响更大

        参数：
            length: 计算周期，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 对近期价格变化更敏感
            - 滞后性小于简单移动平均
            - 需要足够的初始数据建立稳定值

        返回值：
            IndSeries: 指数加权移动平均值序列

        示例：
            # 计算指数移动平均线
            ema_12 = tq.ema(close, length=12)
            ema_26 = tq.ema(close, length=26)

            # MACD指标计算
            macd_line = ema_12 - ema_26
            signal_line = tq.ema(macd_line, length=9)

            # 快速趋势识别
            price_above_ema = close > ema_12
            ema_rising = ema_12 > tq.ref(ema_12, 1)
        """
        ...

    @tobtind(lib='tqfunc')
    def ema2(self, length: int = 10, **kwargs) -> IndSeries:
        """
        线性加权移动平均函数 - 计算序列的线性加权移动平均值

        功能：
            使用线性递减权重，平衡响应速度和平滑程度

        应用场景：
            - 需要线性权重衰减的技术分析
            - 平衡滞后性和噪音过滤
            - 传统技术指标计算
            - 多权重系统设计

        计算原理：
            ema2(x, n) = [n·x₀ + (n-1)·x₁ + ... + 1·xₙ₋₁] / [n + (n-1) + ... + 1]
            使用线性递减的权重系数

        参数：
            length: 计算周期，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 权重线性递减，最近数据权重最大
            - 平滑程度介于SMA和EMA之间
            - 窗口长度不足时返回NaN

        返回值：
            IndSeries: 线性加权移动平均值序列

        示例：
            # 计算线性加权移动平均
            wma_20 = tq.ema2(close, length=20)

            # 与其它移动平均比较
            sma_20 = tq.ma(close, length=20)
            ema_20 = tq.ema(close, length=20)

            # 构建WMA通道
            upper_wma = tq.ema2(high, length=20)
            lower_wma = tq.ema2(low, length=20)

            # 线性加权动量
            wma_momentum = wma_20 - tq.ref(wma_20, 1)
        """
        ...

    @tobtind(lib='tqfunc')
    def crossup(self, b=None, **kwargs) -> IndSeries:
        """
        向上穿越判断 - 判断序列a是否从下向上穿越序列b

        功能：
            检测序列a从下方穿越序列b的时点，生成金叉信号

        应用场景：
            - 均线金叉信号识别
            - 指标突破判断
            - 趋势反转确认
            - 买入信号生成

        计算原理：
            crossup(a, b)[i] = 1 如果 a[i] > b[i] 且 a[i-1] <= b[i-1]，否则为0
            严格判断向上穿越的时点

        参数：
            b: 被穿越的序列b
            **kwargs: 额外参数

        注意：
            - 返回布尔序列（1表示穿越发生，0表示未发生）
            - 只在穿越发生的时点返回1
            - 需要两个序列长度一致

        返回值：
            IndSeries: 向上穿越标志序列（1/0）

        示例：
            # 均线金叉信号
            ma_fast = tq.ma(close, length=5)
            ma_slow = tq.ma(close, length=20)
            golden_cross = tq.crossup(ma_fast, ma_slow)

            # 价格突破阻力位
            resistance = tq.hhv(high, length=20)
            breakout_signal = tq.crossup(close, resistance)

            # 指标突破信号
            rsi_signal = tq.crossup(rsi, 30)  # RSI从超卖区域向上突破
        """
        ...

    @tobtind(lib='tqfunc')
    def crossdown(self, b=None, **kwargs) -> IndSeries:
        """
        向下穿越判断 - 判断序列a是否从上向下穿越序列b

        功能：
            检测序列a从上方穿越序列b的时点，生成死叉信号

        应用场景：
            - 均线死叉信号识别
            - 支撑位跌破判断
            - 趋势反转确认
            - 卖出信号生成

        计算原理：
            crossdown(a, b)[i] = 1 如果 a[i] < b[i] 且 a[i-1] >= b[i-1]，否则为0
            严格判断向下穿越的时点

        参数：
            b: 被穿越的序列b
            **kwargs: 额外参数

        注意：
            - 返回布尔序列（1表示穿越发生，0表示未发生）
            - 只在穿越发生的时点返回1
            - 需要两个序列长度一致

        返回值：
            IndSeries: 向下穿越标志序列（1/0）

        示例：
            # 均线死叉信号
            ma_fast = tq.ma(close, length=5)
            ma_slow = tq.ma(close, length=20)
            death_cross = tq.crossdown(ma_fast, ma_slow)

            # 价格跌破支撑位
            support = tq.llv(low, length=20)
            breakdown_signal = tq.crossdown(close, support)

            # 指标跌破信号
            rsi_signal = tq.crossdown(rsi, 70)  # RSI从超买区域向下跌破
        """
        ...

    @tobtind(lib='tqfunc')
    def count(self, cond=None, length: int = 10, **kwargs) -> IndSeries:
        """
        条件计数统计 - 统计指定周期内满足条件的次数

        功能：
            计算滚动窗口内条件成立的次数，用于频率统计

        应用场景：
            - 统计信号出现的频率
            - 计算胜率和盈亏比
            - 条件发生的密度分析
            - 策略信号的强度评估

        计算原理：
            count(cond, n)[i] = 在[i-n+1, i]区间内cond为真的次数
            滑动窗口内的条件计数

        参数：
            cond: 条件表达式
            length: 统计周期数，默认10
            **kwargs: 额外参数

        注意：
            - length=0时从第一个有效值开始统计
            - 条件cond应为布尔序列
            - 返回整数类型的计数序列

        返回值：
            IndSeries: 条件成立次数序列

        示例：
            # 统计近期上涨天数
            up_days = tq.count(close > tq.ref(close, 1), length=10)

            # 计算技术指标信号的频率
            rsi_oversold = rsi < 30
            oversold_frequency = tq.count(rsi_oversold, length=20)

            # 策略信号强度评估
            buy_signals = ...  # 买入信号条件
            signal_density = tq.count(buy_signals, length=10)
            high_frequency_signal = signal_density >= 3  # 10期内至少3次信号
        """
        ...

    @tobtind(lib='tqfunc')
    def trma(self, length: int = 10, **kwargs) -> IndSeries:
        """
        三角移动平均 - 求序列的n周期三角移动平均值

        功能：
            计算双重平滑的移动平均，提供更平滑的趋势信号

        应用场景：
            - 低噪音趋势识别
            - 过滤市场短期波动
            - 长期投资决策参考
            - 趋势质量评估

        计算原理：
            trma(x, n) = ma(ma(x, n), n)
            对原始序列计算移动平均，再对结果计算移动平均

        参数：
            length: 计算周期，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 相当于两次简单移动平均
            - 比单次移动平均更平滑
            - 滞后性比单次移动平均更大

        返回值：
            IndSeries: 三角移动平均值序列

        示例：
            # 计算三角移动平均趋势
            trma_20 = tq.trma(close, length=20)

            # 与简单移动平均比较
            sma_20 = tq.ma(close, length=20)
            trma_20 = tq.trma(close, length=20)

            # 三角移动平均通道
            upper_trma = tq.trma(high, length=20)
            lower_trma = tq.trma(low, length=20)
            middle_trma = tq.trma(close, length=20)

            # 趋势确认系统
            price_above_trma = close > trma_20
            trma_rising = trma_20 > tq.ref(trma_20, 1)
            confirmed_uptrend = price_above_trma & trma_rising
        """
        ...

    @tobtind(lib='tqfunc')
    def harmean(self, length: int = 10, **kwargs) -> IndSeries:
        """
        调和平均值函数 - 计算序列在指定周期内的调和平均值

        功能：
            计算滚动窗口内的调和平均值，对极值敏感，适用于比率数据的平均计算

        应用场景：
            - 计算价格比率的平均值
            - 投资组合的调和平均收益
            - 速度和时间相关指标的平均
            - 对异常值敏感的数据分析

        计算原理：
            harmean(x, n) = n / (1/x₁ + 1/x₂ + ... + 1/xₙ)
            计算窗口内各值倒数的算术平均值的倒数

        参数：
            length: 计算周期，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 调和平均值总是小于等于算术平均值
            - 对极值敏感，零值会导致计算错误
            - 窗口长度不足时返回NaN

        返回值：
            IndSeries: 调和平均值序列

        示例：
            # 计算价格调和平均趋势
            harmonic_mean = tq.harmean(close, length=20)

            # 计算收益率调和平均
            returns = (close - tq.ref(close, 1)) / tq.ref(close, 1)
            harmonic_return = tq.harmean(returns + 1, length=10) - 1

            # 构建调和平均通道
            upper_harmonic = tq.harmean(high, length=20)
            lower_harmonic = tq.harmean(low, length=20)
        """
        ...

    @tobtind(lib='tqfunc')
    def numpow(self, n: int = 5, m: int = 2, **kwargs) -> IndSeries:
        """
        自然数幂方和函数 - 计算序列的自然数幂方加权和

        功能：
            使用自然数的幂次作为权重，计算序列的加权和，用于特殊的技术指标计算

        应用场景：
            - 自定义技术指标计算
            - 特殊加权移动平均
            - 数学变换和特征工程
            - 高级滤波器的设计

        计算原理：
            numpow(x, n, m) = nᵐ·x₀ + (n-1)ᵐ·x₁ + ... + 1ᵐ·xₙ₋₁
            使用递减的自然数幂次作为权重系数

        参数：
            n: 自然数周期，默认5
            m: 幂次指数，默认2
            **kwargs: 额外参数，可指定其他序列

        注意：
            - n必须为正整数
            - m可以为任意实数
            - 序列长度不足时返回NaN

        返回值：
            IndSeries: 自然数幂方加权和序列

        示例：
            # 计算二次幂加权移动和
            quad_weighted_sum = tq.numpow(n=5, m=2)

            # 构建自定义指标
            custom_indicator = tq.numpow(close, n=10, m=1.5)

            # 特殊滤波处理
            filtered_signal = tq.numpow(price_IndSeries, n=8, m=0.5)
        """
        ...

    @tobtind(lib='tqfunc')
    def abs(self, **kwargs) -> IndSeries:
        """
        绝对值函数 - 计算序列中每个元素的绝对值

        功能：
            对输入序列中的每个元素取绝对值，将负值转换为正值

        应用场景：
            - 计算价格波动的绝对幅度
            - 处理收益率数据的正负波动
            - 技术指标中需要正值计算的场景
            - 距离和偏差的绝对值计算

        计算原理：
            abs(x)[i] = |x[i]|
            对序列中每个元素取绝对值

        参数：
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 默认使用实例初始化时的数据列
            - 对复数类型数据，返回复数的模

        返回值：
            IndSeries: 绝对值序列

        示例：
            # 计算价格与均线的绝对偏差
            price_deviation = close - ma_20
            abs_deviation = tq.abs(IndSeries=price_deviation)

            # 计算日收益率绝对幅度
            daily_return = (close - tq.ref(length=1)) / tq.ref(length=1)
            abs_return = tq.abs(IndSeries=daily_return)
        """
        ...

    @tobtind(lib='tqfunc')
    def min(self, b=None, **kwargs) -> IndSeries:
        """
        最小值函数 - 获取两个序列中对应位置的最小值

        功能：
            比较两个序列对应位置的值，返回较小值组成的新序列

        应用场景：
            - 计算价格通道的下轨
            - 寻找支撑位和阻力位
            - 风险管理中的止损计算
            - 多指标信号取保守值

        计算原理：
            min(a, b)[i] = min(a[i], b[i])
            逐元素比较两个序列，取较小值

        参数：
            b: 第二个比较序列
            **kwargs: 额外参数

        注意：
            - 当只有一个序列时，默认与实例数据比较
            - 序列长度不一致时，按位置对应，缺失位置返回NaN

        返回值：
            IndSeries: 最小值序列

        示例：
            # 计算真实波幅的最小部分
            true_range = tq.max(high, tq.ref(close, 1)) - tq.min(low, tq.ref(close, 1))

            # 构建价格通道下轨（取最低价和支撑位中的较小值）
            support_level = ...  # 计算支撑位
            channel_lower = tq.min(low, support_level)
        """
        ...

    @tobtind(lib='tqfunc')
    def max(self, b=None, **kwargs) -> IndSeries:
        """
        最大值函数 - 获取两个序列中对应位置的最大值

        功能：
            比较两个序列对应位置的值，返回较大值组成的新序列

        应用场景：
            - 计算价格通道的上轨
            - 寻找突破位和阻力位
            - 止盈目标位计算
            - 多指标信号取激进值

        计算原理：
            max(a, b)[i] = max(a[i], b[i])
            逐元素比较两个序列，取较大值

        参数：
            b: 第二个比较序列
            **kwargs: 额外参数

        注意：
            - 当只有一个序列时，默认与实例数据比较
            - 序列长度不一致时，按位置对应，缺失位置返回NaN

        返回值：
            IndSeries: 最大值序列

        示例：
            # 计算真实波幅的最大部分
            true_range = tq.max(high, tq.ref(close, 1)) - tq.min(low, tq.ref(close, 1))

            # 构建价格通道上轨（取最高价和阻力位中的较大值）
            resistance_level = ...  # 计算阻力位
            channel_upper = tq.max(high, resistance_level)
        """
        ...

    @tobtind(lib='tqfunc')
    def median(self, length: int = 10, **kwargs) -> IndSeries:
        """
        中位数函数 - 计算序列在指定周期内的中位数值

        功能：
            计算滚动窗口内的中位数，反映数据的中心趋势，对异常值不敏感

        应用场景：
            - 构建稳健的价格趋势指标
            - 异常值过滤和数据处理
            - 替代移动平均的稳健中心度量
            - 统计学稳健分析

        计算原理：
            median(x, n)[i] = 排序后窗口内中间位置的值
            对每个位置的n周期窗口内数据排序，取中间值

        参数：
            length: 计算周期，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 当n为偶数时，取中间两个数的平均值
            - 窗口长度不足时返回NaN
            - 对异常值的敏感度低于算术平均值

        返回值：
            IndSeries: 中位数序列

        示例：
            # 计算价格中位数趋势
            price_median = tq.median(close, length=20)

            # 构建中位数通道
            upper_median = tq.median(high, length=20)
            lower_median = tq.median(low, length=20)
        """
        ...

    @tobtind(lib='tqfunc')
    def exist(self, cond=None, length: int = 10, **kwargs) -> IndSeries:
        """
        条件存在判断 - 判断指定周期内是否存在满足条件的时点

        功能：
            检查在最近的n个周期内，是否至少有一个周期满足给定条件

        应用场景：
            - 确认技术信号的有效性
            - 趋势确认和过滤
            - 模式识别的存在性验证
            - 交易信号的二次确认

        计算原理：
            exist(cond, n)[i] = 1 如果在[i-n+1, i]区间内至少有一个cond为真，否则为0
            滑动窗口内条件成立的布尔判断

        参数：
            cond: 条件表达式
            length: 检查周期数，默认10
            **kwargs: 额外参数

        注意：
            - 返回布尔序列（1表示存在，0表示不存在）
            - 条件cond应为布尔序列
            - length=0时从第一个有效值开始检查

        返回值：
            IndSeries: 条件存在标志序列（1/0）

        示例：
            # 确认近期是否出现过金叉信号
            golden_cross = tq.crossup(ma_5, ma_20)
            recent_golden_cross = tq.exist(golden_cross, length=10)

            # 检查近期是否有突破行为
            breakout = close > tq.ref(high, 1)  # 突破前高
            recent_breakout = tq.exist(breakout, length=5)
        """
        ...

    @tobtind(lib='tqfunc')
    def every(self, cond=None, length: int = 3, **kwargs) -> IndSeries:
        """
        持续满足判断 - 判断指定周期内是否持续满足条件

        功能：
            检查在最近的n个周期内，是否每个周期都满足给定条件

        应用场景：
            - 确认趋势的持续性
            - 过滤假突破信号
            - 确认指标的稳定状态
            - 连续信号验证

        计算原理：
            every(cond, n)[i] = 1 如果在[i-n+1, i]区间内所有cond都为真，否则为0
            滑动窗口内条件持续成立的布尔判断

        参数：
            cond: 条件表达式
            length: 检查周期数，默认3
            **kwargs: 额外参数

        注意：
            - 返回布尔序列（1表示持续满足，0表示不满足）
            - 条件cond应为布尔序列
            - length=0时从第一个有效值开始检查

        返回值：
            IndSeries: 持续满足标志序列（1/0）

        示例：
            # 确认连续上涨趋势
            consecutive_up = tq.every(close > tq.ref(close, 1), length=3)

            # 确认均线多头排列的持续性
            ma_alignment = (ma_5 > ma_10) & (ma_10 > ma_20)
            stable_trend = tq.every(ma_alignment, length=5)
        """
        ...

    @tobtind(lib='tqfunc')
    def hhv(self, length: int = 10, **kwargs) -> IndSeries:
        """
        周期最高值 - 计算序列在指定周期内的最高值

        功能：
            计算滚动窗口内的最大值，用于识别阻力位和突破点

        应用场景：
            - 构建布林带和其他通道指标的上轨
            - 识别价格阻力位
            - 计算突破交易的参考水平
            - 波动率测量和极值分析

        计算原理：
            hhv(x, n)[i] = max(x[i-n+1], x[i-n+2], ..., x[i])
            滑动窗口内取最大值

        参数：
            length: 计算周期，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 窗口长度不足时返回NaN
            - 常用于构建动态支撑阻力位
            - 对价格数据的极值敏感

        返回值：
            IndSeries: 周期最高值序列

        示例：
            # 计算唐奇安通道上轨
            donchian_upper = tq.hhv(high, length=20)

            # 识别近期阻力位
            recent_resistance = tq.hhv(high, length=10)
        """
        ...

    @tobtind(lib='tqfunc')
    def llv(self, length: int = 10, **kwargs) -> IndSeries:
        """
        周期最低值 - 计算序列在指定周期内的最低值

        功能：
            计算滚动窗口内的最小值，用于识别支撑位和破位点

        应用场景：
            - 构建布林带和其他通道指标的下轨
            - 识别价格支撑位
            - 计算抄底交易的参考水平
            - 风险管理中的止损设置

        计算原理：
            llv(x, n)[i] = min(x[i-n+1], x[i-n+2], ..., x[i])
            滑动窗口内取最小值

        参数：
            length: 计算周期，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 窗口长度不足时返回NaN
            - 常用于构建动态支撑阻力位
            - 对价格数据的极值敏感

        返回值：
            IndSeries: 周期最低值序列

        示例：
            # 计算唐奇安通道下轨
            donchian_lower = tq.llv(low, length=20)

            # 识别近期支撑位
            recent_support = tq.llv(low, length=10)
        """
        ...

    @tobtind(lib='tqfunc')
    def avedev(self, length: int = 10, **kwargs) -> IndSeries:
        """
        平均绝对偏差 - 计算序列在周期内的平均绝对偏差

        功能：
            测量数据点与均值的平均距离，反映数据的离散程度

        应用场景：
            - 波动率测量和风险评估
            - 异常值检测
            - 数据稳定性分析
            - 技术指标的可靠性评估

        计算原理：
            avedev(x, n)[i] = sum(|x[j] - mean(x, n)|) / n, j从i-n+1到i
            计算窗口内各点与均值的绝对偏差的平均值

        参数：
            length: 计算周期，默认10
            **kwargs: 额外参数，可指定其他序列

        注意：
            - 比标准差对异常值更稳健
            - 窗口长度不足时返回NaN
            - 反映数据的平均波动幅度

        返回值：
            IndSeries: 平均绝对偏差序列

        示例：
            # 计算价格波动性
            price_volatility = tq.avedev(close, length=20)

            # 检测异常波动
            normal_volatility = tq.ma(price_volatility, length=50)
            abnormal_move = price_volatility > normal_volatility * 2
        """
        ...

    @tobtind(lib='tqfunc')
    def barlast(self, cond=None, **kwargs) -> IndSeries:
        """
        条件间隔计数 - 计算从上一次条件成立到当前的周期数

        功能：
            统计从最近一次条件成立位置到当前位置的周期间隔

        应用场景：
            - 信号出现后的时间跟踪
            - 事件驱动的策略计时
            - 条件持续时间的监控
            - 交易信号的冷却期判断

        计算原理：
            对每个位置，计算从最近一次cond为True到当前位置的周期数

        参数：
            cond: 条件表达式序列
            **kwargs: 额外参数

        注意：
            - 条件成立时返回0，表示当前周期条件成立
            - 如果从未成立过，返回-1
            - 条件序列应为布尔类型

        返回值：
            IndSeries: 间隔周期数序列

        示例：
            # 跟踪金叉信号后的时间
            golden_cross = tq.crossup(ma_5, ma_20)
            bars_since_golden = tq.barlast(golden_cross)

            # 止损后的冷却期
            stop_loss_triggered = ...  # 止损条件
            cooling_period = tq.barlast(stop_loss_triggered)
            can_trade_again = cooling_period >= 5  # 止损后5个周期内不交易
        """
        ...

    @tobtind(lib='tqfunc')
    def cum_counts(self, cond=None, **kwargs) -> IndSeries:
        """
        连续条件计数 - 统计连续满足条件的周期数

        功能：
            计算当前连续满足条件的周期数量，用于识别连续模式

        应用场景：
            - 计算连续上涨/下跌天数
            - 统计最大连续盈利/亏损
            - 识别趋势的持续性
            - 条件连续性的监控

        计算原理：
            对每个位置，计算从当前位置向前连续满足条件的周期数

        参数：
            cond: 条件表达式序列
            **kwargs: 额外参数

        注意：
            - 条件不满足时计数重置为0
            - 条件满足时计数递增
            - 可用于计算各种连续模式

        返回值：
            IndSeries: 连续满足条件的计数序列

        示例：
            # 计算连续上涨天数
            up_day = close > tq.ref(close, 1)
            consecutive_up_days = tq.cum_counts(up_day)

            # 统计连续盈利交易
            profitable_trade = trade_pnl > 0
            winning_streak = tq.cum_counts(profitable_trade)

            # 识别超买超卖的持续性
            overbought = rsi > 70
            consecutive_overbought = tq.cum_counts(overbought)
            extreme_overbought = consecutive_overbought >= 3  # 连续3期超买
        """
        ...

    @tobtind(lib='tqfunc')
    def time_to_ns_timestamp(self, **kwargs) -> IndSeries:
        """
        纳秒时间戳转换 - 将时间转换为纳秒级时间戳

        功能：
            将各种格式的时间数据转换为整数类型的纳秒级时间戳

        应用场景：
            - 高频数据的时间精确记录
            - 事件顺序的精确排序
            - 跨系统时间同步
            - 性能分析和时间间隔测量

        计算原理：
            将输入时间转换为从1970-01-01 00:00:00开始的纳秒数

        参数：
            **kwargs: 额外参数

        注意：
            - 支持datetime对象、字符串、pandas时间戳等格式
            - 返回整数类型的纳秒时间戳
            - 精度为纳秒级，适用于高频交易场景

        返回值：
            IndSeries: 纳秒时间戳序列

        示例：
            # 转换当前时间为纳秒时间戳
            ns_ts = tq.time_to_ns_timestamp(context.current_dt)

            # 计算事件时间间隔（纳秒）
            event1_ts = tq.time_to_ns_timestamp(event1_time)
            event2_ts = tq.time_to_ns_timestamp(event2_time)
            time_diff_ns = event2_ts - event1_ts
        """
        ...

    @tobtind(lib='tqfunc')
    def time_to_s_timestamp(self, **kwargs) -> IndSeries:
        """
        秒级时间戳转换 - 将时间转换为秒级时间戳

        功能：
            将各种格式的时间数据转换为整数类型的秒级时间戳

        应用场景：
            - 低频数据的时间记录
            - 跨日数据的时间对齐
            - 策略逻辑中的时间判断
            - 数据存储和传输的时间标准化

        计算原理：
            将输入时间转换为从1970-01-01 00:00:00开始的秒数

        参数：
            **kwargs: 额外参数

        注意：
            - 支持datetime对象、字符串、pandas时间戳等格式
            - 返回整数类型的秒级时间戳
            - 精度为秒级，适用于日线、小时线等低频数据

        返回值：
            IndSeries: 秒级时间戳序列

        示例：
            # 转换当前时间为秒级时间戳
            s_ts = tq.time_to_s_timestamp(context.current_dt)

            # 计算日线数据的时间戳
            daily_timestamp = tq.time_to_s_timestamp(daily_data.index)
        """
        ...

    @tobtind(lib='tqfunc')
    def time_to_str(self, **kwargs) -> IndSeries:
        """
        时间字符串转换 - 将时间转换为标准格式字符串

        功能：
            将各种格式的时间数据转换为%Y-%m-%d %H:%M:%S.%f格式的字符串

        应用场景：
            - 数据展示和日志输出
            - 报告生成和时间格式化
            - 跨系统数据交换
            - 时间信息的可视化

        计算原理：
            将输入时间转换为标准化的字符串格式

        参数：
            **kwargs: 额外参数

        注意：
            - 支持datetime对象、时间戳、字符串等格式
            - 返回标准格式的时间字符串
            - 格式为：年-月-日 时:分:秒.微秒

        返回值：
            IndSeries: 格式化时间字符串序列

        示例：
            # 转换当前时间为标准字符串格式
            time_str = tq.time_to_str(context.current_dt)

            # 生成交易记录的时间戳
            trade_time_str = tq.time_to_str(trade_timestamp)
        """
        ...

    @tobtind(lib='tqfunc')
    def time_to_datetime(self, **kwargs) -> IndSeries:
        """
        datetime对象转换 - 将时间转换为datetime对象

        功能：
            将各种格式的时间数据转换为Python datetime对象

        应用场景：
            - 时间运算和日期操作
            - 工作日计算和假期判断
            - 时间序列的高级处理
            - 与其他Python时间库的交互

        计算原理：
            将输入时间转换为datetime.datetime对象

        参数：
            **kwargs: 额外参数

        注意：
            - 支持字符串、时间戳、其他时间对象等格式
            - 返回Python标准datetime对象
            - 便于进行日期运算和时间操作

        返回值：
            IndSeries: datetime对象序列

        示例：
            # 转换时间戳为datetime对象
            dt_obj = tq.time_to_datetime(timestamp)

            # 计算交易日
            trade_date = tq.time_to_datetime(context.current_dt).date()
        """
        ...


class TqTa:
    """### 天勤技术指标计算类

    官方文档参考：https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.ta.html

    基于天勤量化(TqSdk)的技术指标库封装，提供专业的技术分析指标计算。

    支持移动平均、振荡指标、趋势指标、量价指标等各类技术分析工具。

    核心功能分类：
    - 趋势指标：MA, EMA, MACD, 布林带等
    - 振荡指标：RSI, KDJ, WR, CCI, BIAS等  
    - 量价指标：OBV, VWAP, 成交量比率等
    - 统计指标：标准差、相关系数、回归分析等
    - 形态识别：高低点、支撑阻力等

    使用示例：
    >>> data = IndFrame  # 包含OHLCV数据的minibt数据对象
    >>> ta = TqTa(data)   # data数据必须包含指标计算时用到的字段
    >>> 
    >>> # 趋势指标
    >>> ma_20 = ta.ma(20)                    # 20周期简单移动平均
    >>> ma_20 = ta.close.ma(20)              # 指定close列计算20周期简单移动平均
    >>> ema_12 = ta.ema(12)                  # 12周期指数移动平均
    >>> macd_diff, macd_dea, macd_hist = ta.macd()  # MACD指标
    >>> 
    >>> # 振荡指标
    >>> rsi_14 = ta.rsi(14)                  # 14周期RSI
    >>> k, d, j = ta.kdj()                   # KDJ随机指标
    >>> 
    >>> # 量价指标
    >>> obv_line = ta.obv()                  # 能量潮指标

    技术特点：
    - 专业准确：基于天勤官方指标算法，确保计算准确性
    - 性能优化：针对金融时间序列数据进行算法优化
    - 完整兼容：与minibt数据框架无缝集成
    - 边界处理：自动处理数据边界和缺失值
    - 多周期支持：支持不同时间周期的指标计算
    """
    _df: IndSeries | IndFrame

    def __init__(self, data):
        self._df = data

    # tqta:天勤指标
    @tobtind(lib="tqta")
    def ATR(self, n=14, **kwargs) -> IndFrame:
        """
        平均真实波幅指标 - 衡量价格波动性的重要技术指标

        功能：
            计算资产在一定周期内的价格波动范围，反映市场波动剧烈程度

        应用场景：
            - 波动率测量和风险评估
            - 止损止盈位设置参考
            - 突破交易信号确认
            - 仓位管理和风险控制

        计算原理：
            真实波幅(TR)取以下三者最大值：
            1. 当日最高价 - 当日最低价
            2. |当日最高价 - 前日收盘价|
            3. |当日最低价 - 前日收盘价|
            平均真实波幅(ATR) = TR的N周期简单移动平均

        参数：
            n: 计算周期，默认14，常用周期为14
            **kwargs: 额外参数

        注意：
            - ATR值本身没有上下限，数值大小与价格和波动性相关
            - 适用于不同时间周期的分析
            - 可作为动态止损止盈的参考依据

        返回值：
            IndFrame: 包含"tr"(真实波幅)和"atr"(平均真实波幅)两列

        所需数据字段：
            `high`,`low``close`

        示例：
            # 使用ATR设置动态止损
            atr_data = ta.ATR(n=14)
            stop_loss = close - 2 * atr_data["atr"]
            take_profit = close + 3 * atr_data["atr"]

            # 波动率过滤
            high_volatility = atr_data["atr"] > ta.ma(atr_data["atr"], length=20)
        """
        # hlc,tr,atr
        ...

    @tobtind(lib="tqta")
    def BIAS(self, n=6, **kwargs) -> IndSeries:
        """
        乖离率指标 - 衡量价格与移动平均线偏离程度的动量指标

        功能：
            计算收盘价与移动平均线之间的百分比偏离，识别超买超卖状态

        应用场景：
            - 趋势反转预警
            - 超买超卖区域识别
            - 均值回归策略构建
            - 价格极端状态判断

        计算原理：
            BIAS = (收盘价 - N周期移动平均价) / N周期移动平均价 × 100%
            正值表示价格在均线上方，负值表示在均线下方

        参数：
            n: 移动平均周期，默认6，常用周期有6、12、24
            **kwargs: 额外参数

        注意：
            - 不同市场、不同品种的乖离率阈值需要调整
            - 在强势趋势中可能出现持续超买/超卖
            - 建议结合其他指标共同使用

        返回值：
            IndSeries: 乖离率值序列，单位为百分比

        所需数据字段：
            `close`

        示例：
            # 乖离率超买超卖判断
            bias_6 = ta.BIAS(n=6)
            over_bought = bias_6 > 5    # 6日乖离率大于5%视为超买
            over_sold = bias_6 < -5     # 6日乖离率小于-5%视为超卖

            # 多周期乖离率组合
            bias_short = ta.BIAS(n=6)
            bias_long = ta.BIAS(n=24)
            bias_divergence = bias_short - bias_long
        """
        # c
        ...

    @tobtind(lib="tqta")
    def BOLL(self, n=26, p=2, **kwargs) -> IndFrame:
        """
        布林带指标 - 基于标准差的价格通道分析工具

        功能：
            构建动态价格通道，识别价格相对位置和波动性变化

        应用场景：
            - 支撑阻力位识别
            - 波动率突破信号
            - 趋势强度和持续性判断
            - 价格极端状态识别

        计算原理：
            中轨 = N周期简单移动平均
            标准差 = N周期收盘价标准差
            上轨 = 中轨 + P × 标准差
            下轨 = 中轨 - P × 标准差

        参数：
            n: 计算周期，默认26
            p: 标准差倍数，默认2，决定通道宽度
            **kwargs: 额外参数

        注意：
            - 价格触及布林带上轨不一定卖出，触及下轨不一定买入
            - 布林带收窄往往预示重大价格变动
            - 结合价格与布林带相对位置判断趋势强度

        返回值：
            IndFrame: 包含"mid"(中轨)、"top"(上轨)、"bottom"(下轨)三列

        所需数据字段：
            `close`

        示例：
            # 布林带突破策略
            boll = ta.BOLL(n=20, p=2)
            upper_break = close > boll["top"]      # 上轨突破
            lower_break = close < boll["bottom"]   # 下轨突破

            # 布林带收窄识别
            band_width = (boll["top"] - boll["bottom"]) / boll["mid"]
            narrow_band = band_width < ta.ma(band_width, length=20)
        """
        # c,mid,top,bottom
        ...

    @tobtind(lib="tqta")
    def DMI(self, n=14, m=6, **kwargs) -> IndFrame:
        """
        动向指标系统 - 综合趋势强度和方向的分析工具

        功能：
            通过+DI、-DI、ADX等多维度分析趋势方向、强度和持续性

        应用场景：
            - 趋势方向确认
            - 趋势强度量化
            - 买卖信号生成
            - 趋势转换预警

        计算原理：
            +DM = 当日最高价 - 前日最高价（正值）
            -DM = 前日最低价 - 当日最低价（正值）
            TR = 真实波幅
            +DI = (+DM的N周期平滑 / TR的N周期平滑) × 100
            -DI = (-DM的N周期平滑 / TR的N周期平滑) × 100
            DX = |(+DI - -DI)| / (+DI + -DI) × 100
            ADX = DX的M周期平滑移动平均

        参数：
            n: 主要计算周期，默认14
            m: ADX平滑周期，默认6
            **kwargs: 额外参数

        注意：
            - +DI上穿-DI为买入信号，下穿为卖出信号
            - ADX高于25表示趋势明显，低于20表示盘整
            - ADXR用于评估ADX的可靠性

        返回值：
            IndFrame: 包含"atr"、"pdi"、"mdi"、"adx"、"adxr"五列

        所需数据字段：
            `high`,`low``close`

        示例：
            # DMI趋势判断
            dmi = ta.DMI(n=14, m=6)
            strong_trend = dmi["adx"] > 25          # 强趋势
            weak_trend = dmi["adx"] < 20           # 弱趋势/盘整
            buy_signal = ta.crossup(dmi["pdi"], dmi["mdi"])  # 买入信号
            sell_signal = ta.crossdown(dmi["pdi"], dmi["mdi"]) # 卖出信号
        """
        # hlc,atr,pdi,mdi,adx,adxr
        ...

    @tobtind(lib="tqta")
    def KDJ(self, n=9, m1=3, m2=3, **kwargs) -> IndFrame:
        """
        随机指标 - 动量振荡器，识别超买超卖和背离信号

        功能：
            通过价格在给定周期内相对位置分析市场动量变化

        应用场景：
            - 超买超卖区域识别
            - 背离分析
            - 短线买卖时机把握
            - 趋势转换预警

        计算原理：
            RSV = (收盘价 - N日内最低价) / (N日内最高价 - N日内最低价) × 100
            K = RSV的M1周期简单移动平均
            D = K的M2周期简单移动平均
            J = 3 × K - 2 × D

        参数：
            n: RSV计算周期，默认9
            m1: K值平滑周期，默认3
            m2: D值平滑周期，默认3
            **kwargs: 额外参数

        注意：
            - K、D值在80以上为超买区，20以下为超卖区
            - J值反应更敏感，可提前预警
            - 金叉死叉结合位置判断更有效
            - 背离信号具有较高可靠性

        返回值：
            IndFrame: 包含"k"、"d"、"j"三列

        所需数据字段：
            `high`,`low``close`

        示例：
            # KDJ超买超卖判断
            kdj = ta.KDJ(n=9, m1=3, m2=3)
            over_bought = (kdj["k"] > 80) & (kdj["d"] > 80)
            over_sold = (kdj["k"] < 20) & (kdj["d"] < 20)

            # KDJ金叉死叉
            golden_cross = ta.crossup(kdj["k"], kdj["d"])
            death_cross = ta.crossdown(kdj["k"], kdj["d"])
        """
        # hlc,k,d,j
        ...

    @tobtind(lib="tqta", linestyle=dict(diff=LineStyle(line_dash=LineDash.vbar)))
    def MACD(self, short=12, long=26, m=9, **kwargs) -> IndFrame:
        """
        指数平滑异同移动平均线 - 经典的趋势动量指标

        功能：
            通过快慢均线离差分析趋势方向和动量变化

        应用场景：
            - 趋势方向判断
            - 买卖信号生成
            - 背离分析
            - 动量强度评估

        计算原理：
            DIF = 12日EMA - 26日EMA
            DEA = DIF的9日EMA
            MACD柱 = (DIF - DEA) × 2

        参数：
            short: 快线周期，默认12
            long: 慢线周期，默认26
            m: 信号线周期，默认9
            **kwargs: 额外参数

        注意：
            - DIF上穿DEA为金叉买入信号
            - DIF下穿DEA为死叉卖出信号
            - 零轴上方为多头市场，下方为空头市场
            - 柱状线颜色变化反映动量增减

        返回值：
            IndFrame: 包含"diff"(DIF)、"dea"(DEA)、"bar"(MACD柱)三列

        所需数据字段：
            `close`

        示例：
            # MACD基础信号
            macd = ta.MACD(short=12, long=26, m=9)
            bull_market = macd["diff"] > 0                    # 多头市场
            golden_cross = ta.crossup(macd["diff"], macd["dea"])  # 金叉
            death_cross = ta.crossdown(macd["diff"], macd["dea"]) # 死叉

            # MACD柱状线分析
            momentum_increasing = macd["bar"] > ta.ref(macd["bar"], length=1)
        """
        # c,diff,dea,bar
        ...

    @tobtind(lib="tqta")
    def SAR(self, n=4, step=0.02, max=0.2, **kwargs) -> IndSeries:
        """
        抛物线停损指标 - 趋势跟踪和停损点设置工具

        功能：
            提供动态的停损点和趋势转换信号，适用于趋势跟踪策略

        应用场景：
            - 趋势方向判断
            - 动态止损位设置
            - 趋势转换预警
            - 长线持仓管理

        计算原理：
            基于极值点和加速因子动态计算停损点
            上升趋势：SAR = 前日SAR + AF × (前日最高价 - 前日SAR)
            下降趋势：SAR = 前日SAR + AF × (前日最低价 - 前日SAR)
            AF从step开始，每创新高/新低增加step，直到达到max

        参数：
            n: 初始周期，默认4
            step: 步长/加速因子，默认0.02
            max: 最大加速因子，默认0.2
            **kwargs: 额外参数

        注意：
            - 价格在SAR之上为上升趋势，之下为下降趋势
            - SAR点翻转即为买卖信号
            - 在震荡市中可能产生频繁假信号
            - 适合趋势明显的市场环境

        返回值：
            IndSeries: SAR值序列

        所需数据字段：
            `open`,`high`,`low`,`close`

        示例：
            # SAR趋势判断
            sar = ta.SAR(n=4, step=0.02, max=0.2)
            uptrend = close > sar                    # 上升趋势
            downtrend = close < sar                  # 下降趋势

            # SAR翻转信号
            buy_signal = (ta.ref(close, length=1) < ta.ref(sar, length=1)) & (close > sar)
            sell_signal = (ta.ref(close, length=1) > ta.ref(sar, length=1)) & (close < sar)
        """
        # ohlc
        ...

    @tobtind(lib="tqta")
    def WR(self, n=14, **kwargs) -> IndSeries:
        """
        威廉指标 - 超买超卖振荡器，测量价格相对位置

        功能：
            分析价格在给定周期内相对高低位置，识别极端状态

        应用场景：
            - 超买超卖区域识别
            - 短期反转点预测
            - 市场极端情绪判断
            - 结合其他指标确认信号

        计算原理：
            WR = (N日内最高价 - 当日收盘价) / (N日内最高价 - N日内最低价) × (-100)
            数值在0到-100之间，0为超卖，-100为超买

        参数：
            n: 计算周期，默认14
            **kwargs: 额外参数

        注意：
            - 传统用法：低于-80超买，高于-20超卖
            - 可结合价格行为过滤假信号
            - 在强势趋势中可能出现指标钝化
            - 多周期WR组合使用效果更好

        返回值：
            IndSeries: WR值序列，范围为-100到0

        所需数据字段：
            `high`,`low`,`close`

        示例：
            # WR超买超卖判断
            wr = ta.WR(n=14)
            over_bought = wr < -80      # 超买区域
            over_sold = wr > -20        # 超卖区域

            # WR背离分析
            price_new_high = close == ta.hhv(close, length=20)
            wr_new_low = wr == ta.llv(wr, length=20)
            bearish_divergence = price_new_high & wr_new_low  # 顶背离
        """
        # hlc
        ...

    @tobtind(lib="tqta")
    def RSI(self, n=7, **kwargs) -> IndSeries:
        """
        相对强弱指标 - 动量振荡器，衡量价格变动速度和幅度

        功能：
            通过比较一定时期内上涨和下跌幅度评估买卖力量对比

        应用场景：
            - 超买超卖状态识别
            - 背离分析
            - 趋势强度评估
            - 买卖时机选择

        计算原理：
            RSI = 100 - 100 / (1 + RS)
            RS = N日内上涨幅度平均值 / N日内下跌幅度平均值

        参数：
            n: 计算周期，默认7，常用周期有6、12、24
            **kwargs: 额外参数

        注意：
            - 传统用法：70以上超买，30以下超卖
            - 可调整阈值适应不同市场特性
            - 背离信号具有较高预测价值
            - 在强势趋势中可能长时间停留在超买/超卖区

        返回值：
            IndSeries: RSI值序列，范围0-100

        所需数据字段：
            `close`

        示例：
            # RSI超买超卖判断
            rsi = ta.RSI(n=14)
            over_bought = rsi > 70      # 超买
            over_sold = rsi < 30        # 超卖

            # RSI背离检测
            price_lower_low = close < ta.ref(close, length=1)
            rsi_higher_low = rsi > ta.ref(rsi, length=1)
            bullish_divergence = price_lower_low & rsi_higher_low  # 底背离
        """
        # c
        ...

    @tobtind(lib="tqta")
    def ASI(self, **kwargs) -> IndSeries:
        """
        振动升降指标 - 精确定价指标，减少跳空缺口影响

        功能：
            通过复杂计算消除跳空影响，更准确反映价格真实走势

        应用场景：
            - 趋势方向精确认定
            - 突破信号验证
            - 价格真实性判断
            - 结合其他指标提高准确性

        计算原理：
            ASI累计计算每个交易日的振动值
            基于开盘、最高、最低、收盘价和前一交易日价格
            通过复杂公式计算当日SI值并累计得到ASI

        参数：
            **kwargs: 额外参数

        注意：
            - ASI领先或同步于价格走势
            - 突破前高前低时ASI信号更可靠
            - 与OBV类似但计算更复杂
            - 适合判断价格走势的真实性

        返回值：
            IndSeries: ASI值序列

        所需数据字段：
            `open`,`high`,`low`,`close`

        示例：
            # ASI突破信号
            asi = ta.ASI()
            price_break_high = close > ta.hhv(close, length=20)
            asi_break_high = asi > ta.hhv(asi, length=20)
            valid_breakout = price_break_high & asi_break_high  # 有效突破

            # ASI趋势确认
            asi_uptrend = asi > ta.ma(asi, length=20)
            asi_downtrend = asi < ta.ma(asi, length=20)
        """
        # ohlc
        ...

    @tobtind(lib="tqta")
    def VR(self, n=26, **kwargs) -> IndSeries:
        """
        容量比率指标 - 量价关系分析工具，衡量成交量与价格关系

        功能：
            通过成交量变化分析资金流向和市场情绪，识别主力资金动向

        应用场景：
            - 量价背离分析
            - 资金流向判断
            - 趋势确认和反转预警
            - 超买超卖区域识别

        计算原理：
            VR = (N日内上涨日成交量总和 + N日内平盘日成交量总和/2) / 
                 (N日内下跌日成交量总和 + N日内平盘日成交量总和/2) × 100
            反映多空双方力量对比

        参数：
            n: 计算周期，默认26
            **kwargs: 额外参数

        注意：
            - VR在40-70为低价区，80-150为安全区，160-450为获利区，450以上为警戒区
            - 低VR值配合价格底部往往是买入时机
            - 高VR值配合价格顶部需警惕反转
            - 与价格走势背离时信号更可靠

        返回值：
            IndSeries: VR值序列

        所需数据字段：
            `close`, `volume`

        示例：
            # VR超买超卖判断
            vr = ta.VR(n=26)
            oversold_area = vr < 70          # 低价区
            safe_area = (vr >= 80) & (vr <= 150)  # 安全区
            profit_area = (vr >= 160) & (vr <= 450) # 获利区
            warning_area = vr > 450          # 警戒区

            # VR与价格背离
            price_new_high = close == ta.hhv(close, length=20)
            vr_divergence = vr < ta.ref(vr, length=1)
            top_divergence = price_new_high & vr_divergence
        """
        # cv
        ...

    @tobtind(lib="tqta")
    def ARBR(self, n=26, **kwargs) -> IndFrame:
        """
        人气意愿指标系统 - 综合反映市场多空力量对比

        功能：
            AR衡量市场人气，BR反映买卖意愿，共同分析市场情绪

        应用场景：
            - 市场情绪判断
            - 多空力量对比分析
            - 趋势转换预警
            - 超买超卖识别

        计算原理：
            AR = (N日内(最高价 - 开盘价)之和 / N日内(开盘价 - 最低价)之和) × 100
            BR = (N日内(当日最高价 - 前日收盘价)之和 / N日内(前日收盘价 - 当日最低价)之和) × 100

        参数：
            n: 计算周期，默认26
            **kwargs: 额外参数

        注意：
            - AR在80-120为盘整区，150以上超买，70以下超卖
            - BR在70-150为盘整区，300以上超买，50以下超卖
            - AR、BR同时急升预示趋势强劲
            - BR急剧下降而AR平稳时可能见底

        返回值：
            IndFrame: 包含"ar"(人气指标)、"br"(意愿指标)两列

        所需数据字段：
            `open`, `high`, `low`, `close`

        示例：
            # ARBR超买超卖判断
            arbr = ta.ARBR(n=26)
            ar_overbought = arbr["ar"] > 150
            ar_oversold = arbr["ar"] < 70
            br_overbought = arbr["br"] > 300
            br_oversold = arbr["br"] < 50

            # ARBR同步分析
            strong_uptrend = (arbr["ar"] > 100) & (arbr["br"] > 100)
            strong_downtrend = (arbr["ar"] < 100) & (arbr["br"] < 100)
        """
        # ohlc ,ar,br
        ...

    @tobtind(lib="tqta")
    def DMA(self, short=10, long=50, m=10, **kwargs) -> IndFrame:
        """
        平行线差指标 - 基于移动平均线差值的趋势分析工具

        功能：
            通过长短周期均线差值分析趋势方向和强度

        应用场景：
            - 趋势方向判断
            - 买卖信号生成
            - 趋势强度量化
            - 均线系统优化

        计算原理：
            DDD = 短期移动平均 - 长期移动平均
            AMA = DDD的M周期移动平均

        参数：
            short: 短期周期，默认10
            long: 长期周期，默认50
            m: 平滑周期，默认10
            **kwargs: 额外参数

        注意：
            - DDD上穿AMA为金叉买入信号
            - DDD下穿AMA为死叉卖出信号
            - DDD在零轴上方为多头市场
            - 配合价格走势使用效果更好

        返回值：
            IndFrame: 包含"ddd"(均线差值)、"ama"(差值均线)两列

        所需数据字段：
            `close`

        示例：
            # DMA基础信号
            dma = ta.DMA(short=10, long=50, m=10)
            bull_market = dma["ddd"] > 0                    # 多头市场
            golden_cross = ta.crossup(dma["ddd"], dma["ama"])  # 金叉
            death_cross = ta.crossdown(dma["ddd"], dma["ama"]) # 死叉

            # DMA趋势强度
            trend_strength = abs(dma["ddd"]) / ta.ma(close, length=long)
            strong_trend = trend_strength > 0.05
        """
        # c,ddd,ama
        ...

    @tobtind(lib="tqta")
    def EXPMA(self, p1=5, p2=10, **kwargs) -> IndFrame:
        """
        指数加权移动平均线组合 - 对近期价格赋予更高权重的均线系统

        功能：
            提供对价格变化更敏感的移动平均线，减少滞后性

        应用场景：
            - 趋势方向早期识别
            - 短线交易信号
            - 动态支撑阻力位
            - 均线交叉策略

        计算原理：
            EMA = α × 当日收盘价 + (1 - α) × 前日EMA
            α = 2 / (N + 1)

        参数：
            p1: 短期EMA周期，默认5
            p2: 长期EMA周期，默认10
            **kwargs: 额外参数

        注意：
            - 短期EMA上穿长期EMA为买入信号
            - 对价格变化反应比SMA更敏感
            - 在震荡市中可能产生较多假信号
            - 适合趋势明显的市场环境

        返回值：
            IndFrame: 包含"ma1"(短期EMA)、"ma2"(长期EMA)两列

        所需数据字段：
            `close`

        示例：
            # EXPMA交叉策略
            expma = ta.EXPMA(p1=5, p2=10)
            fast_above_slow = expma["ma1"] > expma["ma2"]      # 快线在慢线上方
            buy_signal = ta.crossup(expma["ma1"], expma["ma2"]) # 金叉买入
            sell_signal = ta.crossdown(expma["ma1"], expma["ma2"]) # 死叉卖出

            # 价格与EXPMA关系
            support_level = ta.min(expma["ma1"], expma["ma2"])  # 支撑位
            resistance_level = ta.max(expma["ma1"], expma["ma2"]) # 阻力位
        """
        # c,ma1,ma2
        ...

    @tobtind(lib="tqta")
    def CR(self, n=26, m=5, **kwargs) -> IndFrame:
        """
        能量指标 - 反映价格动量和市场人气的综合指标

        功能：
            通过中间价与前一交易日比较分析多空力量对比

        应用场景：
            - 市场能量判断
            - 趋势强度分析
            - 买卖时机选择
            - 价格动量评估

        计算原理：
            CR = (N日内(当日最高价+最低价)/2 - 前一日中间价的正值之和) / 
                 (N日内(前一日中间价 - 当日最高价+最低价)/2的正值之和) × 100
            CRMA = CR的M周期移动平均

        参数：
            n: CR计算周期，默认26
            m: CRMA平滑周期，默认5
            **kwargs: 额外参数

        注意：
            - CR在100附近表示多空平衡
            - CR急升表示能量聚集，可能突破
            - CR与价格顶背离是卖出信号
            - 配合ARBR使用效果更好

        返回值：
            IndFrame: 包含"cr"(能量指标)、"crma"(CR均线)两列

        所需数据字段：
            `high`, `low`, `close`

        示例：
            # CR能量分析
            cr_data = ta.CR(n=26, m=5)
            energy_accumulation = cr_data["cr"] > 150          # 能量聚集
            energy_dispersion = cr_data["cr"] < 50            # 能量分散
            balance_area = (cr_data["cr"] >= 80) & (cr_data["cr"] <= 120) # 多空平衡

            # CR与价格背离
            price_high = close == ta.hhv(close, length=20)
            cr_low = cr_data["cr"] < ta.ref(cr_data["cr"], length=1)
            bearish_divergence = price_high & cr_low
        """
        # hlc,cr,crma
        ...

    @tobtind(lib="tqta")
    def CCI(self, n=14, **kwargs) -> IndSeries:
        """
        顺势指标 - 测量价格偏离统计平均程度的振荡器

        功能：
            识别超买超卖状态和趋势转换点，适用于商品和股票市场

        应用场景：
            - 超买超卖判断
            - 趋势转换预警
            - 极端价格状态识别
            - 短线交易时机选择

        计算原理：
            典型价格 = (最高价 + 最低价 + 收盘价) / 3
            CCI = (典型价格 - N期典型价格移动平均) / (0.015 × N期典型价格平均绝对偏差)

        参数：
            n: 计算周期，默认14
            **kwargs: 额外参数

        注意：
            - CCI在+100以上为超买区，-100以下为超卖区
            - +100以上回落为卖出信号，-100以下回升为买入信号
            - 在强势趋势中可能长时间停留在超买/超卖区
            - 适合短线交易和极端状态识别

        返回值：
            IndSeries: CCI值序列

        所需数据字段：
            `high`, `low`, `close`

        示例：
            # CCI超买超卖信号
            cci = ta.CCI(n=14)
            overbought = cci > 100                    # 超买区域
            oversold = cci < -100                     # 超卖区域
            buy_signal = ta.crossup(cci, -100)        # 从超卖区回升
            sell_signal = ta.crossdown(cci, 100)      # 从超买区回落

            # CCI趋势强度
            strong_uptrend = cci > 0
            strong_downtrend = cci < 0
        """
        # hlc
        ...

    @tobtind(lib="tqta")
    def OBV(self, **kwargs) -> IndSeries:
        """
        能量潮指标 - 通过成交量变动预测价格变动的先行指标

        功能：
            将成交量数量化，制成趋势线，配合价格趋势判断量价关系

        应用场景：
            - 量价关系分析
            - 趋势确认
            - 背离分析
            - 资金流向判断

        计算原理：
            如果当日收盘价 > 前日收盘价，则OBV = 前日OBV + 当日成交量
            如果当日收盘价 < 前日收盘价，则OBV = 前日OBV - 当日成交量
            如果当日收盘价 = 前日收盘价，则OBV = 前日OBV

        参数：
            **kwargs: 额外参数

        注意：
            - OBV与价格同步上升为健康上涨
            - OBV与价格顶背离是卖出信号
            - OBV突破前高确认价格上涨
            - 适合中长期趋势分析

        返回值：
            IndSeries: OBV值序列

        所需数据字段：
            `close`, `volume`

        示例：
            # OBV趋势分析
            obv = ta.OBV()
            obv_uptrend = obv > ta.ma(obv, length=20)        # OBV上升趋势
            obv_downtrend = obv < ta.ma(obv, length=20)      # OBV下降趋势

            # OBV背离检测
            price_new_high = close == ta.hhv(close, length=20)
            obv_divergence = obv < ta.hhv(obv, length=20)
            top_divergence = price_new_high & obv_divergence  # 顶背离

            # OBV突破确认
            obv_breakout = obv > ta.hhv(obv, length=20)      # OBV突破前高
        """
        # cv
        ...

    @tobtind(lib="tqta")
    def CDP(self, n=3, **kwargs) -> IndFrame:
        """
        逆势操作指标 - 短线交易的反向操作工具

        功能：
            为短线交易者提供支撑阻力位参考，适合震荡市操作

        应用场景：
            - 短线支撑阻力位识别
            - 日内交易点位选择
            - 震荡市高抛低吸
            - 突破交易确认

        计算原理：
            CDP = (前日最高 + 前日最低 + 前日收盘 × 2) / 4
            AH = CDP + (前日最高 - 前日最低)
            NH = CDP × 2 - 前日最低
            NL = CDP × 2 - 前日最高
            AL = CDP - (前日最高 - 前日最低)

        参数：
            n: 参考周期，默认3
            **kwargs: 额外参数

        注意：
            - 价格在NL和NH之间震荡时适合反向操作
            - 突破AH或AL可能形成趋势
            - 适合短线日内交易
            - 在趋势明显的市场中效果较差

        返回值：
            IndFrame: 包含"ah"(最高值)、"al"(最低值)、"nh"(近高值)、"nl"(近低值)四列

        所需数据字段：
            `high`, `low`, `close`

        示例：
            # CDP交易区间判断
            cdp = ta.CDP(n=3)
            in_trading_range = (close > cdp["nl"]) & (close < cdp["nh"])  # 震荡区间
            breakout_up = close > cdp["ah"]                              # 向上突破
            breakout_down = close < cdp["al"]                            # 向下跌破

            # CDP短线交易策略
            buy_zone = close <= cdp["nl"]        # 买入区域
            sell_zone = close >= cdp["nh"]       # 卖出区域
            stop_loss_long = cdp["al"]          # 多头止损
            stop_loss_short = cdp["ah"]         # 空头止损
        """
        # hlc,ah,al,nh,nl
        ...

    @tobtind(lib="tqta")
    def HCL(self, n=10, **kwargs) -> IndFrame:
        """
        均线通道指标 - 基于高、低、收盘价的移动平均通道系统

        功能：
            构建价格波动通道，识别趋势方向和波动范围

        应用场景：
            - 趋势方向判断
            - 波动范围测量
            - 支撑阻力位构建
            - 突破交易信号

        计算原理：
            MAH = 最高价的N周期移动平均
            MAL = 最低价的N周期移动平均  
            MAC = 收盘价的N周期移动平均

        参数：
            n: 移动平均周期，默认10
            **kwargs: 额外参数

        注意：
            - 价格在MAH和MAL之间波动为震荡市
            - 突破MAH为强势上涨信号
            - 跌破MAL为强势下跌信号
            - MAC代表趋势方向

        返回值：
            IndFrame: 包含"mah"(最高价均线)、"mal"(最低价均线)、"mac"(收盘价均线)三列

        所需数据字段：
            `high`, `low`, `close`

        示例：
            # HCL通道分析
            hcl = ta.HCL(n=10)
            in_channel = (close >= hcl["mal"]) & (close <= hcl["mah"])  # 通道内震荡
            breakout_up = close > hcl["mah"]                           # 向上突破
            breakdown = close < hcl["mal"]                             # 向下跌破

            # 趋势方向判断
            uptrend = (hcl["mac"] > ta.ref(hcl["mac"], length=1)) & 
                     (hcl["mah"] > ta.ref(hcl["mah"], length=1))
            downtrend = (hcl["mac"] < ta.ref(hcl["mac"], length=1)) & 
                       (hcl["mal"] < ta.ref(hcl["mal"], length=1))
        """
        # hlc,mah,mal,mac
        ...

    @tobtind(lib="tqta")
    def ENV(self, n=14, k=6, **kwargs) -> IndFrame:
        """
        包络线指标 - 基于移动平均线的动态通道系统

        功能：
            在移动平均线上下构建固定百分比的通道，识别超买超卖

        应用场景：
            - 动态支撑阻力位
            - 超买超卖识别
            - 趋势跟踪
            - 回归均值策略

        计算原理：
            中线 = 收盘价的N周期移动平均
            上轨 = 中线 × (1 + K%)
            下轨 = 中线 × (1 - K%)

        参数：
            n: 移动平均周期，默认14
            k: 通道宽度参数，默认6，表示6%
            **kwargs: 额外参数

        注意：
            - 价格触及上轨可能回调，触及下轨可能反弹
            - 在趋势市中价格可能沿通道运行
            - 通道宽度需要根据波动性调整
            - 适合均值回归策略

        返回值：
            IndFrame: 包含"upper"(上轨)、"lower"(下轨)两列

        所需数据字段：
            `close`

        示例：
            # ENV通道交易策略
            env = ta.ENV(n=14, k=6)
            overbought = close > env["upper"]                  # 触及上轨超买
            oversold = close < env["lower"]                    # 触及下轨超卖
            middle_line = (env["upper"] + env["lower"]) / 2    # 通道中线

            # 回归均值策略
            buy_signal = (close < env["lower"]) & 
                        (ta.ref(close, length=1) >= ta.ref(env["lower"], length=1))
            sell_signal = (close > env["upper"]) & 
                         (ta.ref(close, length=1) <= ta.ref(env["upper"], length=1))
        """
        # c,upper,lower
        ...

    @tobtind(lib="tqta")
    def MIKE(self, n=12, **kwargs) -> IndFrame:
        """
        麦克指标 - 压力支撑分析系统，提供多级支撑阻力位

        功能：
            通过复杂计算提供六条不同级别的支撑阻力线，辅助判断价格运行区间

        应用场景：
            - 多级支撑阻力位识别
            - 价格目标位预测
            - 突破交易确认
            - 区间震荡交易

        计算原理：
            基于典型价格和价格波动幅度计算六个不同级别的支撑阻力位：
            WR(初级压力)、MR(中级压力)、SR(强力压力)
            WS(初级支撑)、MS(中级支撑)、SS(强力支撑)

        参数：
            n: 计算周期，默认12
            **kwargs: 额外参数

        注意：
            - 价格在WS-WR之间为正常波动区间
            - 突破WR可能向MR、SR运行
            - 跌破WS可能向MS、SS运行
            - 适合中短线交易和仓位管理

        返回值：
            IndFrame: 包含"wr"(初级压力)、"mr"(中级压力)、"sr"(强力压力)、
                      "ws"(初级支撑)、"ms"(中级支撑)、"ss"(强力支撑)六列

        所需数据字段：
            `high`, `low`, `close`

        示例：
            # MIKE支撑阻力分析
            mike = ta.MIKE(n=12)
            normal_range = (close >= mike["ws"]) & (close <= mike["wr"])  # 正常区间
            strong_resistance = close > mike["sr"]                       # 强力阻力区
            strong_support = close < mike["ss"]                          # 强力支撑区

            # 突破交易信号
            break_resistance = (ta.ref(close, length=1) <= mike["wr"]) & (close > mike["wr"])
            break_support = (ta.ref(close, length=1) >= mike["ws"]) & (close < mike["ws"])
        """
        # hlc,wr,mr,sr,ws,ms,ss
        ...

    @tobtind(lib="tqta")
    def PUBU(self, m=4, **kwargs) -> IndSeries:
        """
        瀑布线指标 - 非线性移动平均系统，过滤价格噪音

        功能：
            通过特殊的移动平均计算方法，减少价格波动干扰，突出趋势方向

        应用场景：
            - 趋势方向过滤
            - 买卖信号生成
            - 价格噪音消除
            - 趋势跟踪策略

        计算原理：
            基于收盘价计算特殊的移动平均线，算法相对复杂，
            旨在平滑价格波动，突出主要趋势方向

        参数：
            m: 计算周期，默认4
            **kwargs: 额外参数

        注意：
            - 瀑布线上涨为多头趋势，下跌为空头趋势
            - 价格在瀑布线上方运行为强势
            - 适合趋势明显的市场环境
            - 在震荡市中可能产生假信号

        返回值：
            IndSeries: 瀑布线值序列

        所需数据字段：
            `close`

        示例：
            # 瀑布线趋势判断
            pubu = ta.PUBU(m=4)
            uptrend = pubu > ta.ref(pubu, length=1)          # 上升趋势
            downtrend = pubu < ta.ref(pubu, length=1)        # 下降趋势

            # 价格与瀑布线关系
            strong_bull = close > pubu                       # 强势多头
            weak_bull = (close > pubu) & (close < ta.ref(close, length=1))  # 弱势多头
            price_breakout = (ta.ref(close, length=1) <= pubu) & (close > pubu)  # 价格突破
        """
        # c
        ...

    @tobtind(lib="tqta")
    def BBI(self, n1=3, n2=6, n3=12, n4=24, **kwargs) -> IndSeries:
        """
        多空指数 - 多周期移动平均综合指标

        功能：
            综合不同时间周期的移动平均线，提供更全面的趋势判断

        应用场景：
            - 多周期趋势综合分析
            - 买卖点确认
            - 趋势强度评估
            - 均线系统简化

        计算原理：
            BBI = (3日均价 + 6日均价 + 12日均价 + 24日均价) / 4
            综合短、中、长期移动平均线的优势

        参数：
            n1: 短期周期，默认3
            n2: 中短期周期，默认6
            n3: 中期周期，默认12
            n4: 长期周期，默认24
            **kwargs: 额外参数

        注意：
            - 价格在BBI上方为多头市场
            - BBI上升角度反映趋势强度
            - 可作为其他指标的参考基准
            - 适合各类时间周期的分析

        返回值：
            IndSeries: BBI值序列

        所需数据字段：
            `close`

        示例：
            # BBI多空判断
            bbi = ta.BBI(n1=3, n2=6, n3=12, n4=24)
            bull_market = close > bbi                         # 多头市场
            bear_market = close < bbi                         # 空头市场

            # BBI趋势强度
            bbi_trend_strength = (bbi - ta.ref(bbi, length=5)) / ta.ref(bbi, length=5)
            strong_trend = abs(bbi_trend_strength) > 0.02     # 强势趋势

            # BBI突破信号
            break_bull = (ta.ref(close, length=1) <= bbi) & (close > bbi)    # 向上突破
            break_bear = (ta.ref(close, length=1) >= bbi) & (close < bbi)    # 向下跌破
        """
        # c
        ...

    @tobtind(lib="tqta")
    def DKX(self, m=10, **kwargs) -> IndFrame:
        """
        多空线指标 - 综合价格和成交量的多空力量分析

        功能：
            通过复杂算法综合价格和成交量信息，判断多空力量对比

        应用场景：
            - 多空力量对比分析
            - 趋势方向确认
            - 买卖时机选择
            - 量价关系验证

        计算原理：
            基于开盘、最高、最低、收盘价和中间价计算多空线，
            再计算其移动平均作为参考线

        参数：
            m: 移动平均周期，默认10
            **kwargs: 额外参数

        注意：
            - 多空线上穿其均线为买入信号
            - 多空线下穿其均线为卖出信号
            - 两者同步上升为强势多头
            - 适合中短线交易

        返回值：
            IndFrame: 包含"b"(多空线)、"d"(多空线均线)两列

        所需数据字段：
            `open`, `high`, `low`, `close`

        示例：
            # DKX多空信号
            dkx = ta.DKX(m=10)
            bull_signal = ta.crossup(dkx["b"], dkx["d"])      # 多头信号
            bear_signal = ta.crossdown(dkx["b"], dkx["d"])    # 空头信号

            # 多空力量强度
            strong_bull = (dkx["b"] > dkx["d"]) & (dkx["b"] > ta.ref(dkx["b"], length=1))
            strong_bear = (dkx["b"] < dkx["d"]) & (dkx["b"] < ta.ref(dkx["b"], length=1))

            # DKX与价格背离
            price_high = close == ta.hhv(close, length=20)
            dkx_low = dkx["b"] < ta.ref(dkx["b"], length=1)
            top_divergence = price_high & dkx_low
        """
        # ohlc,b,d
        ...

    @tobtind(lib="tqta")
    def BBIBOLL(self, n=10, m=3, **kwargs) -> IndFrame:
        """
        多空布林线 - BBI与布林带结合的趋势通道系统

        功能：
            在多空指数基础上构建布林通道，提供趋势和波动性双重分析

        应用场景：
            - 趋势通道分析
            - 波动率测量
            - 超买超卖判断
            - 突破交易信号

        计算原理：
            BBIBOLL = BBI多空指数
            UPR = BBIBOLL + M × BBIBOLL的N周期标准差
            DWN = BBIBOLL - M × BBIBOLL的N周期标准差

        参数：
            n: BBI计算周期参数，默认10
            m: 标准差倍数，默认3
            **kwargs: 额外参数

        注意：
            - 价格在通道内运行为震荡市
            - 突破上轨可能继续上涨，跌破下轨可能继续下跌
            - 通道收窄预示重大价格变动
            - 适合趋势跟踪和突破策略

        返回值：
            IndFrame: 包含"bbiboll"(多空布林线)、"upr"(压力线)、"dwn"(支撑线)三列

        所需数据字段：
            `close`

        示例：
            # BBIBOLL通道分析
            bbiboll = ta.BBIBOLL(n=10, m=3)
            in_channel = (close >= bbiboll["dwn"]) & (close <= bbiboll["upr"])  # 通道内
            breakout_up = close > bbiboll["upr"]                               # 向上突破
            breakdown = close < bbiboll["dwn"]                                 # 向下跌破

            # 通道宽度分析
            channel_width = (bbiboll["upr"] - bbiboll["dwn"]) / bbiboll["bbiboll"]
            narrow_channel = channel_width < ta.ma(channel_width, length=20)   # 通道收窄
            wide_channel = channel_width > ta.ma(channel_width, length=20)     # 通道扩张
        """
        # close,bbiboll,upr,dwn
        ...

    @tobtind(lib="tqta")
    def ADTM(self, n=23, m=8, **kwargs) -> IndFrame:
        """
        动态买卖气指标 - 衡量市场动态买卖力量的振荡器

        功能：
            通过价格在区间内的相对位置分析买卖力量动态变化

        应用场景：
            - 买卖力量对比
            - 超买超卖判断
            - 趋势转换预警
            - 短线交易时机

        计算原理：
            基于开盘价与价格区间的关系计算动态买卖气，
            再计算其移动平均作为参考

        参数：
            n: 主要计算周期，默认23
            m: 移动平均周期，默认8
            **kwargs: 额外参数

        注意：
            - ADTM在0轴上方为买方主导
            - ADTM在0轴下方为卖方主导
            - 上穿0轴为买入信号，下穿0轴为卖出信号
            - 适合震荡市和反转交易

        返回值：
            IndFrame: 包含"adtm"(动态买卖气)、"adtmma"(买卖气均线)两列

        所需数据字段：
            `open`, `high`, `low`

        示例：
            # ADTM多空判断
            adtm = ta.ADTM(n=23, m=8)
            buyer_dominant = adtm["adtm"] > 0                 # 买方主导
            seller_dominant = adtm["adtm"] < 0                # 卖方主导

            # ADTM交易信号
            buy_signal = ta.crossup(adtm["adtm"], 0)          # 买入信号
            sell_signal = ta.crossdown(adtm["adtm"], 0)       # 卖出信号

            # ADTM与均线关系
            strong_buy = (adtm["adtm"] > adtm["adtmma"]) & (adtm["adtm"] > 0)
            strong_sell = (adtm["adtm"] < adtm["adtmma"]) & (adtm["adtm"] < 0)
        """
        # ohl,adtm,adtmma
        ...

    @tobtind(lib="tqta")
    def B3612(self, **kwargs) -> IndFrame:
        """
        三减六日乖离率 - 短期均线乖离分析系统

        功能：
            通过不同周期移动平均线的乖离关系分析短期趋势动量

        应用场景：
            - 短期趋势动量分析
            - 均线系统优化
            - 买卖时机选择
            - 趋势强度评估

        计算原理：
            B36 = 3日移动平均 - 6日移动平均
            B612 = 6日移动平均 - 12日移动平均
            反映不同周期均线之间的偏离程度

        参数：
            **kwargs: 额外参数

        注意：
            - B36反映极短期动量变化
            - B612反映短期趋势方向
            - 两者同向为趋势确认
            - 适合短线交易和趋势确认

        返回值：
            IndFrame: 包含"b36"(3-6日乖离)、"b612"(6-12日乖离)两列

        所需数据字段：
            `close`

        示例：
            # B3612动量分析
            b3612 = ta.B3612()
            short_momentum = b3612["b36"] > 0                 # 短期动量向上
            medium_trend = b3612["b612"] > 0                  # 中期趋势向上

            # 多周期协同
            strong_uptrend = (b3612["b36"] > 0) & (b3612["b612"] > 0)  # 强势上涨
            trend_reversal = (b3612["b36"] > 0) & (b3612["b612"] < 0)  # 趋势转换

            # 乖离率极端值
            extreme_bull = b3612["b36"] > ta.hhv(b3612["b36"], length=20) * 0.8
            extreme_bear = b3612["b36"] < ta.llv(b3612["b36"], length=20) * 0.8
        """
        # c,b36,b612
        ...

    @tobtind(lib="tqta")
    def DBCD(self, n=5, m=16, t=76, **kwargs) -> IndFrame:
        """
        异同离差乖离率 - 乖离率的优化版本，减少噪音干扰

        功能：
            通过复杂的乖离率计算和平滑处理，提供更稳定的趋势信号

        应用场景：
            - 趋势方向过滤
            - 买卖信号生成
            - 价格偏离度分析
            - 中长期趋势判断

        计算原理：
            基于BIAS乖离率进行多级计算和平滑处理，
            得到更稳定的DBCD指标及其移动平均

        参数：
            n: BIAS计算周期，默认5
            m: 第一次平滑周期，默认16
            t: 第二次平滑周期，默认76
            **kwargs: 额外参数

        注意：
            - DBCD上穿其均线为买入信号
            - DBCD下穿其均线为卖出信号
            - 指标波动较小，信号相对稳定
            - 适合中长线趋势跟踪

        返回值：
            IndFrame: 包含"dbcd"(异同离差乖离率)、"mm"(乖离率均线)两列

        所需数据字段：
            `close`

        示例：
            # DBCD趋势信号
            dbcd = ta.DBCD(n=5, m=16, t=76)
            buy_signal = ta.crossup(dbcd["dbcd"], dbcd["mm"])  # 买入信号
            sell_signal = ta.crossdown(dbcd["dbcd"], dbcd["mm"]) # 卖出信号

            # DBCD趋势强度
            uptrend_strength = dbcd["dbcd"] - dbcd["mm"]       # 上升趋势强度
            downtrend_strength = dbcd["mm"] - dbcd["dbcd"]     # 下降趋势强度

            # 零轴分析
            above_zero = dbcd["dbcd"] > 0                      # 零轴上方
            below_zero = dbcd["dbcd"] < 0                      # 零轴下方
        """
        # c,dbcd,mm
        ...

    @tobtind(lib="tqta")
    def DDI(self, n=13, n1=30, m=10, m1=5, **kwargs) -> IndFrame:
        """
        方向标准离差指数 - 趋势方向和波动性综合指标

        功能：
            通过价格波动方向和幅度分析趋势强度和持续性

        应用场景：
            - 趋势方向确认
            - 波动性分析
            - 买卖信号生成
            - 趋势强度量化

        计算原理：
            基于最高最低价计算方向离差，通过多级平滑得到DDI、ADDI、AD等指标

        参数：
            n: 方向计算周期，默认13
            n1: 离差计算周期，默认30
            m: 第一次平滑周期，默认10
            m1: 第二次平滑周期，默认5
            **kwargs: 额外参数

        注意：
            - DDI反映短期趋势方向
            - ADDI反映中期趋势强度
            - AD确认趋势持续性
            - 三者同步为趋势确认

        返回值：
            IndFrame: 包含"ddi"(方向离差)、"addi"(加权平均)、"ad"(移动平均)三列

        所需数据字段：
            `high`, `low`

        示例：
            # DDI趋势系统
            ddi = ta.DDI(n=13, n1=30, m=10, m1=5)
            trend_confirmed = (ddi["ddi"] > 0) & (ddi["addi"] > 0) & (ddi["ad"] > 0)  # 趋势确认

            # DDI强度分级
            strong_uptrend = ddi["ddi"] > ta.hhv(ddi["ddi"], length=20) * 0.7
            weak_uptrend = (ddi["ddi"] > 0) & (ddi["ddi"] < ta.ma(ddi["ddi"], length=10))

            # 趋势转换信号
            trend_turn_up = (ta.ref(ddi["ddi"], length=1) <= 0) & (ddi["ddi"] > 0)
            trend_turn_down = (ta.ref(ddi["ddi"], length=1) >= 0) & (ddi["ddi"] < 0)
        """
        # hl,ddi,addi,ad
        ...

    @tobtind(lib="tqta")
    def KD(self, n=9, m1=3, m2=3, **kwargs) -> IndFrame:
        """
        随机指标(KD) - KDJ指标的简化版本，去除J值

        功能：
            通过价格在周期内相对位置分析市场动量和超买超卖状态

        应用场景：
            - 超买超卖判断
            - 短线买卖时机
            - 背离分析
            - 趋势转换预警

        计算原理：
            RSV = (收盘价 - N日内最低价) / (N日内最高价 - N日内最低价) × 100
            K = RSV的M1周期简单移动平均
            D = K的M2周期简单移动平均

        参数：
            n: RSV计算周期，默认9
            m1: K值平滑周期，默认3
            m2: D值平滑周期，默认3
            **kwargs: 额外参数

        注意：
            - K、D值在80以上为超买区，20以下为超卖区
            - K线上穿D线为金叉买入信号
            - K线下穿D线为死叉卖出信号
            - 背离信号可靠性较高

        返回值：
            IndFrame: 包含"k"(K值)、"d"(D值)两列

        所需数据字段：
            `high`, `low`, `close`

        示例：
            # KD超买超卖判断
            kd = ta.KD(n=9, m1=3, m2=3)
            overbought = (kd["k"] > 80) & (kd["d"] > 80)      # 超买区域
            oversold = (kd["k"] < 20) & (kd["d"] < 20)        # 超卖区域

            # KD交易信号
            golden_cross = ta.crossup(kd["k"], kd["d"])       # 金叉买入
            death_cross = ta.crossdown(kd["k"], kd["d"])      # 死叉卖出

            # KD位置分析
            bull_zone = (kd["k"] > 50) & (kd["d"] > 50)       # 多头区域
            bear_zone = (kd["k"] < 50) & (kd["d"] < 50)       # 空头区域
        """
        # hlc,k,d
        ...

    @tobtind(lib="tqta")
    def LWR(self, n=9, m=3, **kwargs) -> IndSeries:
        """
        威廉指标(LWR) - 反向威廉指标，与WR指标计算方式相反

        功能：
            通过价格在周期内相对位置分析市场动量和超买超卖状态，数值范围与WR相反

        应用场景：
            - 超买超卖判断
            - 短线买卖时机
            - 背离分析
            - 趋势转换预警

        计算原理：
            LWR = (N日内最低价 - 当日收盘价) / (N日内最高价 - N日内最低价) × (-100)
            数值在0到-100之间，但方向与WR指标相反

        参数：
            n: 计算周期，默认9
            m: 平滑周期，默认3
            **kwargs: 额外参数

        注意：
            - LWR在-20以下为超买区，-80以上为超卖区
            - 与传统WR指标数值方向相反
            - 可结合其他指标确认信号
            - 在强势趋势中可能出现指标钝化

        返回值：
            IndSeries: LWR值序列，范围为-100到0

        所需数据字段：
            `high`, `low`, `close`

        示例：
            # LWR超买超卖判断
            lwr = ta.LWR(n=9, m=3)
            overbought = lwr < -20      # 超买区域
            oversold = lwr > -80        # 超卖区域

            # LWR背离分析
            price_new_high = close == ta.hhv(close, length=20)
            lwr_new_low = lwr < ta.llv(lwr, length=20)
            bearish_divergence = price_new_high & lwr_new_low  # 顶背离
        """
        # hlc
        ...

    @tobtind(lib="tqta")
    def MASS(self, n1=9, n2=25, **kwargs) -> IndSeries:
        """
        梅斯线指标 - 价格波动幅度和强度测量工具

        功能：
            通过高低价区间分析价格波动幅度，识别趋势转折点

        应用场景：
            - 趋势转折预警
            - 波动性爆发识别
            - 突破信号确认
            - 价格极端状态判断

        计算原理：
            基于最高最低价区间计算波动幅度，通过两次指数移动平均得到MASS线
            反映价格波动的强度和频率

        参数：
            n1: 第一次EMA周期，默认9
            n2: 第二次EMA周期，默认25
            **kwargs: 额外参数

        注意：
            - MASS高于27后回落为趋势转折信号
            - MASS线急剧上升预示波动性增加
            - 适合识别价格波动的极端状态
            - 常与其他趋势指标结合使用

        返回值：
            IndSeries: MASS值序列

        所需数据字段：
            `high`, `low`

        示例：
            # MASS趋势转折信号
            mass = ta.MASS(n1=9, n2=25)
            reversal_signal = (ta.ref(mass, length=1) > 27) & (mass <= 27)  # 转折信号

            # 波动性分析
            high_volatility = mass > ta.ma(mass, length=20)                # 高波动期
            low_volatility = mass < ta.ma(mass, length=20)                 # 低波动期

            # MASS突破预警
            mass_breakout = mass > ta.hhv(mass, length=20)                 # 波动性爆发
        """
        # hl
        ...

    @tobtind(lib="tqta")
    def MFI(self, n=14, **kwargs) -> IndSeries:
        """
        资金流量指标 - 带成交量的相对强弱指标

        功能：
            结合价格和成交量分析资金流向，识别超买超卖状态

        应用场景：
            - 资金流向分析
            - 超买超卖判断
            - 背离分析
            - 量价关系验证

        计算原理：
            MFI计算方式类似RSI，但加入了成交量因素
            典型价格 = (最高 + 最低 + 收盘) / 3
            资金流 = 典型价格 × 成交量
            通过正负资金流比率计算MFI

        参数：
            n: 计算周期，默认14
            **kwargs: 额外参数

        注意：
            - MFI在80以上为超买区，20以下为超卖区
            - 与价格背离时信号更可靠
            - 反映资金的实际流入流出
            - 适合中短线交易分析

        返回值：
            IndSeries: MFI值序列，范围0-100

        所需数据字段：
            `high`, `low`, `close`, `volume`

        示例：
            # MFI超买超卖判断
            mfi = ta.MFI(n=14)
            overbought = mfi > 80                    # 超买
            oversold = mfi < 20                      # 超卖

            # MFI资金流向
            money_inflow = mfi > 50                  # 资金流入
            money_outflow = mfi < 50                 # 资金流出

            # MFI与价格背离
            price_high = close == ta.hhv(close, length=20)
            mfi_low = mfi < ta.ref(mfi, length=1)
            top_divergence = price_high & mfi_low    # 顶背离
        """
        # hlcv
        ...

    @tobtind(lib="tqta")
    def MI(self, n=12, **kwargs) -> IndFrame:
        """
        动量指标 - 价格变动速率和方向分析

        功能：
            测量价格变动速度和幅度，识别趋势动量和转折点

        应用场景：
            - 趋势动量分析
            - 买卖时机选择
            - 趋势强度评估
            - 反转信号预警

        计算原理：
            A = 当日收盘价 - N日前收盘价
            MI = A的平滑处理值
            反映价格在N周期内的变动动量

        参数：
            n: 计算周期，默认12
            **kwargs: 额外参数

        注意：
            - MI为正表示上升动量，为负表示下降动量
            - MI上穿零轴为买入信号，下穿零轴为卖出信号
            - 动量极值往往预示趋势转折
            - 适合趋势跟踪和动量策略

        返回值：
            IndFrame: 包含"a"(价格差值)、"mi"(动量指标)两列

        所需数据字段：
            `close`

        示例：
            # MI动量分析
            mi = ta.MI(n=12)
            positive_momentum = mi["mi"] > 0                  # 正动量
            negative_momentum = mi["mi"] < 0                  # 负动量

            # MI交易信号
            buy_signal = ta.crossup(mi["mi"], 0)              # 上穿零轴买入
            sell_signal = ta.crossdown(mi["mi"], 0)           # 下穿零轴卖出

            # 动量极值识别
            momentum_extreme = abs(mi["mi"]) > ta.ma(abs(mi["mi"]), length=20) * 2
        """
        # c,a,mi
        ...

    @tobtind(lib="tqta")
    def MICD(self, n=3, n1=10, n2=20, **kwargs) -> IndFrame:
        """
        异同离差动力指数 - 动量指标的MACD版本

        功能：
            在动量指标基础上进行离差分析，提供更稳定的动量信号

        应用场景：
            - 动量趋势分析
            - 买卖信号生成
            - 趋势转换预警
            - 动量强度量化

        计算原理：
            基于动量指标进行多周期离差计算
            DIF = 短期动量 - 长期动量
            MICD = DIF的平滑移动平均
            类似MACD但对动量指标进行计算

        参数：
            n: 动量计算周期，默认3
            n1: 短期周期，默认10
            n2: 长期周期，默认20
            **kwargs: 额外参数

        注意：
            - DIF上穿MICD为金叉买入信号
            - DIF下穿MICD为死叉卖出信号
            - 零轴上方为多头动量，下方为空头动量
            - 适合中短线动量交易

        返回值：
            IndFrame: 包含"dif"(离差值)、"micd"(异同离差动力指数)两列

        所需数据字段：
            `close`

        示例：
            # MICD动量信号
            micd = ta.MICD(n=3, n1=10, n2=20)
            bull_momentum = micd["dif"] > 0                    # 多头动量
            golden_cross = ta.crossup(micd["dif"], micd["micd"])  # 金叉
            death_cross = ta.crossdown(micd["dif"], micd["micd"]) # 死叉

            # 动量强度分析
            momentum_strength = abs(micd["dif"] - micd["micd"])
            strong_momentum = momentum_strength > ta.ma(momentum_strength, length=20)
        """
        # c,dif,micd
        ...

    @tobtind(lib="tqta")
    def MTM(self, n=6, n1=6, **kwargs) -> IndFrame:
        """
        动量指标(MTM) - 经典的价格动量振荡器

        功能：
            测量价格变化速率，识别趋势动量和超买超卖状态

        应用场景：
            - 趋势动量分析
            - 超买超卖判断
            - 背离分析
            - 买卖时机选择

        计算原理：
            MTM = 当日收盘价 - N日前收盘价
            MTMMA = MTM的M周期简单移动平均
            反映价格在N周期内的变动动量

        参数：
            n: 动量计算周期，默认6
            n1: 移动平均周期，默认6
            **kwargs: 额外参数

        注意：
            - MTM上穿零轴为买入信号，下穿零轴为卖出信号
            - MTM与价格顶背离是卖出信号
            - MTM与价格底背离是买入信号
            - 适合各类时间周期的分析

        返回值：
            IndFrame: 包含"mtm"(动量值)、"mtmma"(动量均线)两列

        所需数据字段：
            `close`

        示例：
            # MTM动量分析
            mtm = ta.MTM(n=6, n1=6)
            positive_momentum = mtm["mtm"] > 0                # 正动量
            momentum_cross = ta.crossup(mtm["mtm"], mtm["mtmma"])  # 动量金叉

            # MTM背离分析
            price_new_high = close == ta.hhv(close, length=20)
            mtm_lower_high = mtm["mtm"] < ta.ref(mtm["mtm"], length=1)
            bearish_divergence = price_new_high & mtm_lower_high  # 顶背离

            # MTM超买超卖
            overbought = mtm["mtm"] > ta.hhv(mtm["mtm"], length=20) * 0.8
            oversold = mtm["mtm"] < ta.llv(mtm["mtm"], length=20) * 0.8
        """
        # c,mtm,mtmma
        ...

    @tobtind(lib="tqta")
    def PRICEOSC(self, long=26, short=12, **kwargs) -> IndSeries:
        """
        价格震荡指数 - 长短周期移动平均离差指标

        功能：
            通过长短周期移动平均线的离差分析价格动量和趋势方向

        应用场景：
            - 趋势方向判断
            - 动量强度分析
            - 买卖信号生成
            - 趋势转换预警

        计算原理：
            PRICEOSC = (短期移动平均 - 长期移动平均) / 长期移动平均 × 100
            反映长短周期均线的相对位置关系

        参数：
            long: 长期周期，默认26
            short: 短期周期，默认12
            **kwargs: 额外参数

        注意：
            - PRICEOSC上穿零轴为买入信号
            - PRICEOSC下穿零轴为卖出信号
            - 数值大小反映趋势强度
            - 适合趋势跟踪和动量策略

        返回值：
            IndSeries: 价格震荡指数序列，单位为百分比

        所需数据字段：
            `close`

        示例：
            # PRICEOSC趋势判断
            priceosc = ta.PRICEOSC(long=26, short=12)
            bull_market = priceosc > 0                        # 多头市场
            bear_market = priceosc < 0                        # 空头市场

            # PRICEOSC交易信号
            buy_signal = ta.crossup(priceosc, 0)              # 上穿零轴买入
            sell_signal = ta.crossdown(priceosc, 0)           # 下穿零轴卖出

            # 趋势强度分析
            trend_strength = abs(priceosc)
            strong_trend = trend_strength > ta.ma(trend_strength, length=20)
        """
        # close
        ...

    @tobtind(lib="tqta")
    def PSY(self, n=12, m=6, **kwargs) -> IndFrame:
        """
        心理线指标 - 投资者情绪和心理状态测量工具

        功能：
            通过上涨天数比率分析市场心理状态，识别超买超卖

        应用场景：
            - 市场情绪分析
            - 超买超卖判断
            - 趋势转换预警
            - 投资者心理测量

        计算原理：
            PSY = (N日内上涨天数 / N) × 100
            PSYMA = PSY的M周期简单移动平均
            反映投资者在N周期内的心理状态

        参数：
            n: 计算周期，默认12
            m: 移动平均周期，默认6
            **kwargs: 额外参数

        注意：
            - PSY在75以上为超买区，25以下为超卖区
            - PSY与价格背离时信号更可靠
            - 反映市场集体心理状态
            - 适合逆向投资策略

        返回值：
            IndFrame: 包含"psy"(心理线)、"psyma"(心理线均线)两列

        所需数据字段：
            `close`

        示例：
            # PSY心理状态分析
            psy = ta.PSY(n=12, m=6)
            over_optimistic = psy["psy"] > 75                 # 过度乐观
            over_pessimistic = psy["psy"] < 25                # 过度悲观

            # PSY交易信号
            buy_zone = (psy["psy"] < 25) & (ta.ref(psy["psy"], length=1) >= 25)
            sell_zone = (psy["psy"] > 75) & (ta.ref(psy["psy"], length=1) <= 75)

            # PSY与均线关系
            sentiment_improving = psy["psy"] > psy["psyma"]   # 情绪改善
            sentiment_deteriorating = psy["psy"] < psy["psyma"] # 情绪恶化
        """
        # c,psy,psyma
        ...

    @tobtind(lib="tqta")
    def QHLSR(self, **kwargs) -> IndFrame:
        """
        阻力指标 - 量价关系阻力分析系统

        功能：
            通过价格和成交量关系分析市场阻力和支撑水平

        应用场景：
            - 阻力支撑位识别
            - 量价关系分析
            - 突破交易确认
            - 市场强度评估

        计算原理：
            基于最高、最低、收盘价和成交量计算阻力系数
            QHL5: 5日阻力系数
            QHL10: 10日阻力系数
            反映价格在成交量配合下的阻力程度

        参数：
            **kwargs: 额外参数

        注意：
            - QHL值越高表示阻力越大
            - QHL值接近1表示强阻力，接近0表示弱阻力
            - 可结合价格位置判断阻力有效性
            - 适合突破交易和区间交易

        返回值：
            IndFrame: 包含"qhl5"(5日阻力)、"qhl10"(10日阻力)两列

        所需数据字段：
            `high`, `low`, `close`, `volume`

        示例：
            # QHLSR阻力分析
            qhlsr = ta.QHLSR()
            strong_resistance = qhlsr["qhl5"] > 0.8           # 强阻力
            weak_resistance = qhlsr["qhl5"] < 0.2             # 弱阻力

            # 阻力变化分析
            resistance_increasing = qhlsr["qhl5"] > ta.ref(qhlsr["qhl5"], length=1)
            resistance_decreasing = qhlsr["qhl5"] < ta.ref(qhlsr["qhl5"], length=1)

            # 多周期阻力对比
            short_term_stronger = qhlsr["qhl5"] > qhlsr["qhl10"]  # 短期阻力更强
        """
        # hlcv,qhl5,qhl10
        ...

    @tobtind(lib="tqta")
    def RC(self, n=50, **kwargs) -> IndSeries:
        """
        变化率指数 - 价格变动速率标准化指标

        功能：
            测量价格变化速率，并进行标准化处理，便于跨品种比较

        应用场景：
            - 价格变动速率分析
            - 趋势强度比较
            - 动量策略构建
            - 跨品种分析

        计算原理：
            RC = 当日收盘价 / N日前收盘价
            反映价格在N周期内的变化比率

        参数：
            n: 计算周期，默认50
            **kwargs: 额外参数

        注意：
            - RC大于1表示上涨，小于1表示下跌
            - RC值大小反映变动幅度
            - 便于不同品种间的动量比较
            - 适合动量投资和趋势跟踪

        返回值：
            IndSeries: 变化率指数序列

        所需数据字段：
            `close`

        示例：
            # RC变化率分析
            rc = ta.RC(n=50)
            price_up = rc > 1                                # 价格上涨
            price_down = rc < 1                              # 价格下跌

            # 变动幅度分析
            strong_rise = rc > 1.1                           # 强势上涨
            strong_fall = rc < 0.9                           # 强势下跌

            # 动量比较
            momentum_rank = rc.rank(ascending=False)         # 动量排名
            top_momentum = momentum_rank <= 10               # 前10动量
        """
        # c
        ...

    @tobtind(lib="tqta")
    def RCCD(self, n=10, n1=21, n2=28, **kwargs) -> IndFrame:
        """
        异同离差变化率指数 - RC指标的MACD版本

        功能：
            在变化率指标基础上进行离差分析，提供更稳定的变化率信号

        应用场景：
            - 变化率趋势分析
            - 买卖信号生成
            - 动量转换预警
            - 跨周期变化率比较

        计算原理：
            基于变化率指标进行多周期离差计算
            DIF = 短期变化率 - 长期变化率
            RCCD = DIF的平滑移动平均
            类似MACD但对变化率指标进行计算

        参数：
            n: 基础变化率周期，默认10
            n1: 短期周期，默认21
            n2: 长期周期，默认28
            **kwargs: 额外参数

        注意：
            - DIF上穿RCCD为金叉买入信号
            - DIF下穿RCCD为死叉卖出信号
            - 零轴上方为正向变化率，下方为负向变化率
            - 适合中长线趋势分析

        返回值：
            IndFrame: 包含"dif"(离差值)、"rccd"(异同离差变化率指数)两列

        所需数据字段：
            `close`

        示例：
            # RCCD变化率信号
            rccd = ta.RCCD(n=10, n1=21, n2=28)
            positive_change = rccd["dif"] > 0                  # 正向变化
            golden_cross = ta.crossup(rccd["dif"], rccd["rccd"])  # 金叉
            death_cross = ta.crossdown(rccd["dif"], rccd["rccd"]) # 死叉

            # 变化率强度分析
            change_strength = abs(rccd["dif"] - rccd["rccd"])
            strong_change = change_strength > ta.ma(change_strength, length=20)
        """
        # c,dif,rccd
        ...

    @tobtind(lib="tqta")
    def ROC(self, n=24, m=20, **kwargs) -> IndFrame:
        """
        变动速率指标 - 价格变化百分比动量振荡器

        功能：
            测量价格变化的百分比速率，识别动量极值和转折点

        应用场景：
            - 动量强度分析
            - 超买超卖判断
            - 趋势转换预警
            - 买卖时机选择

        计算原理：
            ROC = (当日收盘价 - N日前收盘价) / N日前收盘价 × 100
            ROCMA = ROC的M周期简单移动平均
            反映价格在N周期内的百分比变化率

        参数：
            n: 计算周期，默认24
            m: 移动平均周期，默认20
            **kwargs: 额外参数

        注意：
            - ROC上穿零轴为买入信号，下穿零轴为卖出信号
            - ROC极值往往预示趋势转折
            - 与价格背离时信号更可靠
            - 适合各类时间周期的动量分析

        返回值：
            IndFrame: 包含"roc"(变动速率)、"rocma"(变动速率均线)两列

        所需数据字段：
            `close`

        示例：
            # ROC动量分析
            roc = ta.ROC(n=24, m=20)
            positive_momentum = roc["roc"] > 0                # 正动量
            momentum_cross = ta.crossup(roc["roc"], roc["rocma"])  # 动量金叉

            # ROC超买超卖
            overbought = roc["roc"] > ta.hhv(roc["roc"], length=20) * 0.8
            oversold = roc["roc"] < ta.llv(roc["roc"], length=20) * 0.8

            # ROC背离分析
            price_new_high = close == ta.hhv(close, length=20)
            roc_lower_high = roc["roc"] < ta.ref(roc["roc"], length=1)
            bearish_divergence = price_new_high & roc_lower_high  # 顶背离
        """
        # c,roc,rocma
        ...

    @tobtind(lib="tqta")
    def SLOWKD(self, n=9, m1=3, m2=3, m3=3, **kwargs) -> IndFrame:
        """
        慢速随机指标 - KDJ指标的平滑版本，减少信号噪音

        功能：
            通过多次平滑处理减少KD指标的波动，提供更稳定的买卖信号

        应用场景：
            - 超买超卖判断
            - 趋势转换确认
            - 买卖信号过滤
            - 中长线交易时机

        计算原理：
            在标准KD计算基础上进行多次平滑处理
            经过m1、m2、m3三次平滑得到最终的K、D值
            信号更稳定但响应更慢

        参数：
            n: RSV计算周期，默认9
            m1: 第一次平滑周期，默认3
            m2: 第二次平滑周期，默认3
            m3: 第三次平滑周期，默认3
            **kwargs: 额外参数

        注意：
            - K、D值在80以上为超买区，20以下为超卖区
            - 信号比标准KD更稳定但滞后
            - 适合中长线趋势跟踪
            - 减少震荡市中的假信号

        返回值：
            IndFrame: 包含"k"(慢速K值)、"d"(慢速D值)两列

        所需数据字段：
            `high`, `low`, `close`

        示例：
            # SLOWKD超买超卖判断
            slowkd = ta.SLOWKD(n=9, m1=3, m2=3, m3=3)
            overbought = (slowkd["k"] > 80) & (slowkd["d"] > 80)  # 超买
            oversold = (slowkd["k"] < 20) & (slowkd["d"] < 20)    # 超卖

            # SLOWKD交易信号
            golden_cross = ta.crossup(slowkd["k"], slowkd["d"])   # 金叉
            death_cross = ta.crossdown(slowkd["k"], slowkd["d"])  # 死叉

            # 趋势区域判断
            bull_zone = (slowkd["k"] > 50) & (slowkd["d"] > 50)   # 多头区域
            bear_zone = (slowkd["k"] < 50) & (slowkd["d"] < 50)   # 空头区域
        """
        # hlc,k,d
        ...

    @tobtind(lib="tqta")
    def SRDM(self, n=30, **kwargs) -> IndFrame:
        """
        动向速度比率 - 价格变动速度和方向综合指标

        功能：
            综合分析价格变动速度和方向，识别趋势强度和持续性

        应用场景：
            - 趋势速度分析
            - 买卖力量对比
            - 趋势持续性判断
            - 动量强度量化

        计算原理：
            基于价格变动计算动向速度比率
            SRDM: 原始动向速度值
            ASRDM: SRDM的加权移动平均
            反映价格变动的速度和方向特征

        参数：
            n: 计算周期，默认30
            **kwargs: 额外参数

        注意：
            - SRDM值反映变动速度，ASRDM反映速度趋势
            - 两者同向为趋势确认
            - 数值大小反映变动强度
            - 适合趋势跟踪和动量策略

        返回值：
            IndFrame: 包含"srdm"(动向速度比率)、"asrdm"(加权平均)两列

        所需数据字段：
            `high`, `low`, `close`

        示例：
            # SRDM趋势分析
            srdm = ta.SRDM(n=30)
            fast_movement = srdm["srdm"] > ta.ma(srdm["srdm"], length=20)  # 快速变动
            trend_confirmed = (srdm["srdm"] > 0) & (srdm["asrdm"] > 0)     # 上升趋势确认

            # 速度变化分析
            accelerating = srdm["srdm"] > ta.ref(srdm["srdm"], length=1)   # 加速
            decelerating = srdm["srdm"] < ta.ref(srdm["srdm"], length=1)   # 减速
        """
        # hlc,srdm,asrdm
        ...

    @tobtind(lib="tqta")
    def SRMI(self, n=9, **kwargs) -> IndFrame:
        """
        MI修正指标 - 动量指标的优化版本

        功能：
            对传统动量指标进行修正，提供更平滑和稳定的动量信号

        应用场景：
            - 动量趋势分析
            - 买卖时机选择
            - 趋势强度评估
            - 反转信号预警

        计算原理：
            在传统动量指标基础上进行修正和平滑处理
            A: 原始动量值
            MI: 修正后的动量指标
            减少噪音干扰，提高信号质量

        参数：
            n: 计算周期，默认9
            **kwargs: 额外参数

        注意：
            - MI上穿零轴为买入信号，下穿零轴为卖出信号
            - 比传统动量指标更平滑
            - 适合中短线趋势分析
            - 减少虚假信号

        返回值：
            IndFrame: 包含"a"(原始动量值)、"mi"(修正动量指标)两列

        所需数据字段：
            `close`

        示例：
            # SRMI动量分析
            srmi = ta.SRMI(n=9)
            positive_momentum = srmi["mi"] > 0                 # 正动量
            momentum_turn = ta.crossup(srmi["mi"], 0)          # 动量转正

            # 动量强度分级
            strong_momentum = srmi["mi"] > ta.ma(srmi["mi"], length=20)
            weak_momentum = srmi["mi"] < ta.ma(srmi["mi"], length=20)

            # 原始与修正对比
            signal_improvement = abs(srmi["mi"] - srmi["a"]) < 0.1  # 信号改善
        """
        # c,a,mi
        ...

    @tobtind(lib="tqta")
    def ZDZB(self, n1=50, n2=5, n3=20, **kwargs) -> IndFrame:
        """
        筑底指标 - 底部形成和反转识别工具

        功能：
            识别价格底部形成过程，预警趋势反转机会

        应用场景：
            - 底部形态识别
            - 趋势反转预警
            - 买入时机选择
            - 支撑位确认

        计算原理：
            基于价格相对位置计算筑底信号
            B: 短期筑底信号
            D: 长期筑底信号
            反映价格在底部区域的相对强度

        参数：
            n1: 基础计算周期，默认50
            n2: 短期信号周期，默认5
            n3: 长期信号周期，默认20
            **kwargs: 额外参数

        注意：
            - B上穿D为底部确认信号
            - 指标值上升表示筑底过程
            - 适合抄底和反转交易
            - 需结合价格形态确认

        返回值：
            IndFrame: 包含"b"(短期筑底信号)、"d"(长期筑底信号)两列

        所需数据字段：
            `close`

        示例：
            # ZDZB底部信号
            zdzb = ta.ZDZB(n1=50, n2=5, n3=20)
            bottom_formation = zdzb["b"] > ta.ref(zdzb["b"], length=1)  # 筑底进行中
            bottom_confirmed = ta.crossup(zdzb["b"], zdzb["d"])         # 底部确认

            # 筑底强度分析
            strong_bottom = (zdzb["b"] > 1) & (zdzb["d"] > 1)           # 强势筑底
            weak_bottom = (zdzb["b"] < 1) & (zdzb["d"] < 1)             # 弱势筑底
        """
        # c,b,d
        ...

    @tobtind(lib="tqta")
    def DPO(self, **kwargs) -> IndSeries:
        """
        区间震荡线 - 价格与移动平均线的周期性偏离分析

        功能：
            消除长期趋势影响，专注于中短期价格波动分析

        应用场景：
            - 区间震荡识别
            - 买卖时机选择
            - 周期波动分析
            - 趋势过滤

        计算原理：
            DPO = 收盘价 - (N/2+1)日前移动平均价
            通过减去移动平均消除长期趋势，突出周期性波动

        参数：
            **kwargs: 额外参数

        注意：
            - DPO上穿零轴为买入信号
            - DPO下穿零轴为卖出信号
            - 适合震荡市交易
            - 在趋势市中效果有限

        返回值：
            IndSeries: DPO值序列

        所需数据字段：
            `close`

        示例：
            # DPO震荡分析
            dpo = ta.DPO()
            in_oscillation = abs(dpo) < ta.std(dpo, length=20)          # 震荡区间
            breakout_signal = dpo > ta.hhv(dpo, length=20)              # 突破信号

            # DPO交易信号
            buy_oscillation = (ta.ref(dpo, length=1) < 0) & (dpo > 0)   # 震荡买入
            sell_oscillation = (ta.ref(dpo, length=1) > 0) & (dpo < 0)  # 震荡卖出
        """
        # c
        ...

    @tobtind(lib="tqta")
    def LON(self, **kwargs) -> IndFrame:
        """
        长线指标 - 综合量价关系的长线趋势分析系统

        功能：
            结合价格和成交量分析长线趋势方向和强度

        应用场景：
            - 长线趋势判断
            - 资金流向分析
            - 趋势持续性评估
            - 长线买卖时机

        计算原理：
            基于价格和成交量计算长线趋势指标
            LON: 长线指标值
            MA1: LON的10周期移动平均
            反映长线资金流向和趋势强度

        参数：
            **kwargs: 额外参数

        注意：
            - LON上穿MA1为长线买入信号
            - LON下穿MA1为长线卖出信号
            - 适合长线投资和趋势跟踪
            - 信号稳定但响应较慢

        返回值：
            IndFrame: 包含"lon"(长线指标)、"ma1"(指标均线)两列

        所需数据字段：
            `high`, `low`, `close`, `volume`

        示例：
            # LON长线趋势
            lon = ta.LON()
            long_term_bull = lon["lon"] > lon["ma1"]                    # 长线多头
            golden_cross_long = ta.crossup(lon["lon"], lon["ma1"])      # 长线金叉

            # 长线趋势强度
            strong_uptrend = (lon["lon"] > 0) & (lon["ma1"] > 0)        # 强势上涨
            trend_strength = (lon["lon"] - lon["ma1"]) / abs(lon["ma1"])
        """
        # hlcv,lon,ma1
        ...

    @tobtind(lib="tqta")
    def SHORT(self, **kwargs) -> IndFrame:
        """
        短线指标 - 综合量价关系的短线交易系统

        功能：
            结合价格和成交量分析短线交易机会和买卖时机

        应用场景：
            - 短线交易信号
            - 日内买卖时机
            - 资金短期流向
            - 短线趋势判断

        计算原理：
            基于价格和成交量计算短线交易指标
            SHORT: 短线指标值
            MA1: SHORT的10周期移动平均
            反映短线资金流向和交易机会

        参数：
            **kwargs: 额外参数

        注意：
            - SHORT上穿MA1为短线买入信号
            - SHORT下穿MA1为短线卖出信号
            - 适合短线交易和日内操作
            - 信号敏感但可能有噪音

        返回值：
            IndFrame: 包含"short"(短线指标)、"ma1"(指标均线)两列

        所需数据字段：
            `high`, `low`, `close`, `volume`

        示例：
            # SHORT短线交易
            short = ta.SHORT()
            short_term_bull = short["short"] > short["ma1"]             # 短线多头
            golden_cross_short = ta.crossup(short["short"], short["ma1"]) # 短线金叉

            # 短线交易信号过滤
            strong_signal = abs(short["short"] - short["ma1"]) > ta.std(short["short"], length=20)
            weak_signal = abs(short["short"] - short["ma1"]) < ta.std(short["short"], length=20)
        """
        # hlcv,short,ma1
        ...

    @tobtind(lib="tqta")
    def MV(self, n=10, m=20, **kwargs) -> IndFrame:
        """
        均量线指标 - 成交量移动平均分析系统

        功能：
            通过成交量的移动平均分析资金流向和活跃度变化

        应用场景：
            - 成交量趋势分析
            - 资金活跃度判断
            - 量价关系验证
            - 突破确认

        计算原理：
            MV1 = 成交量的N周期简单移动平均
            MV2 = 成交量的M周期简单移动平均
            反映不同周期下的平均成交量水平

        参数：
            n: 短期均量周期，默认10
            m: 长期均量周期，默认20
            **kwargs: 额外参数

        注意：
            - MV1上穿MV2为量能金叉
            - MV1下穿MV2为量能死叉
            - 量价配合时信号更可靠
            - 适合各类时间周期的量能分析

        返回值：
            IndFrame: 包含"mv1"(短期均量)、"mv2"(长期均量)两列

        所需数据字段：
            `volume`

        示例：
            # MV量能分析
            mv = ta.MV(n=10, m=20)
            volume_increasing = mv["mv1"] > mv["mv2"]                   # 量能增加
            golden_cross_volume = ta.crossup(mv["mv1"], mv["mv2"])      # 量能金叉

            # 量价配合分析
            price_up_volume_up = (close > ta.ref(close, length=1)) & (mv["mv1"] > ta.ref(mv["mv1"], length=1))
            price_up_volume_down = (close > ta.ref(close, length=1)) & (mv["mv1"] < ta.ref(mv["mv1"], length=1))
        """
        # v,mv1,mv2
        ...

    @tobtind(lib="tqta")
    def WAD(self, n=10, m=30, **kwargs) -> IndFrame:
        """
        威廉多空力度线 - 威廉指标与量价结合的多空力量分析

        功能：
            结合价格位置和量价关系分析多空双方力量对比

        应用场景：
            - 多空力量对比分析
            - 趋势方向确认
            - 买卖信号生成
            - 量价关系验证

        计算原理：
            基于威廉指标和量价关系计算多空力度
            A/D: 原始多空力度值
            B: A/D的N周期加权移动平均
            E: A/D的M周期加权移动平均
            综合反映多空力量变化

        参数：
            n: 短期平滑周期，默认10
            m: 长期平滑周期，默认30
            **kwargs: 额外参数

        注意：
            - A/D值反映当日多空力度
            - B上穿E为多头信号
            - B下穿E为空头信号
            - 适合趋势确认和力量分析

        返回值：
            IndFrame: 包含"a"(多空力度)、"b"(短期均线)、"e"(长期均线)三列

        所需数据字段：
            `high`, `low`, `close`

        示例：
            # WAD多空分析
            wad = ta.WAD(n=10, m=30)
            bull_power = wad["a"] > 0                          # 多头力量
            golden_cross_wad = ta.crossup(wad["b"], wad["e"])  # 多空金叉
            death_cross_wad = ta.crossdown(wad["b"], wad["e"]) # 多空死叉

            # 多空力量强度
            strong_bull = (wad["b"] > wad["e"]) & (wad["a"] > ta.ma(wad["a"], length=10))
            strong_bear = (wad["b"] < wad["e"]) & (wad["a"] < ta.ma(wad["a"], length=10))
        """
        # hlc,a,b,e
        ...

    @tobtind(lib="tqta")
    def AD(self, **kwargs) -> IndSeries:
        """
        累积/派发指标 - 资金流向和积累分布分析

        功能：
            通过价格和成交量关系分析资金累积和派发过程

        应用场景：
            - 资金流向分析
            - 趋势确认
            - 背离分析
            - 机构资金动向

        计算原理：
            AD = 前日AD + 当日资金流
            当日资金流 = [(收盘价-最低价)-(最高价-收盘价)] / (最高价-最低价) × 成交量
            反映资金的累积和派发过程

        参数：
            **kwargs: 额外参数

        注意：
            - AD上升表示资金累积，下降表示资金派发
            - 与价格背离时信号更可靠
            - 适合中长线资金流向分析
            - 反映机构资金动向

        返回值：
            IndSeries: AD值序列

        所需数据字段：
            `high`, `low`, `close`, `volume`

        示例：
            # AD资金流向分析
            ad = ta.AD()
            accumulation = ad > ta.ref(ad, length=1)           # 资金累积
            distribution = ad < ta.ref(ad, length=1)           # 资金派发

            # AD与价格背离
            price_new_high = close == ta.hhv(close, length=20)
            ad_lower_high = ad < ta.ref(ad, length=1)
            bearish_divergence = price_new_high & ad_lower_high  # 顶背离
        """
        # hlcv
        ...

    @tobtind(lib="tqta")
    def CCL(self, close_oi=None, **kwargs) -> IndSeries:
        """
        持仓异动指标 - 期货市场持仓变化分析

        功能：
            分析期货合约持仓量变化，识别主力资金动向

        应用场景：
            - 期货持仓分析
            - 主力资金动向
            - 多空力量判断
            - 趋势确认

        计算原理：
            基于持仓量变化计算持仓异动
            返回字符串标识：'多头增仓'、'多头减仓'、'空头增仓'、'空头减仓'等
            反映期货市场的资金流向

        参数：
            close_oi: 收盘持仓量数据
            **kwargs: 额外参数

        注意：
            - 需要持仓量数据支持
            - 反映期货市场特有信息
            - 适合期货品种分析
            - 结合价格走势更有效

        返回值：
            IndSeries: 持仓异动标识序列

        所需数据字段：
            `close` (需要持仓量数据配合)

        示例：
            # CCL持仓分析
            ccl = ta.CCL()
            long_increase = ccl == '多头增仓'                   # 多头增仓
            short_increase = ccl == '空头增仓'                  # 空头增仓
            long_decrease = ccl == '多头减仓'                   # 多头减仓
            short_decrease = ccl == '空头减仓'                  # 空头减仓
        """
        # c
        ...

    @tobtind(lib="tqta")
    def CJL(self, close_oi=None, **kwargs) -> IndFrame:
        """
        成交持仓分析 - 期货市场成交和持仓量数据

        功能：
            提供期货市场的成交量和持仓量基础数据

        应用场景：
            - 成交量分析
            - 持仓量分析
            - 量价关系研究
            - 市场活跃度判断

        计算原理：
            VOL: 当日成交量
            OPID: 当日持仓量
            提供期货市场的基础成交持仓数据

        参数：
            close_oi: 收盘持仓量数据
            **kwargs: 额外参数

        注意：
            - 需要期货合约的成交持仓数据
            - 成交量反映市场活跃度
            - 持仓量反映资金沉淀
            - 适合期货市场分析

        返回值：
            IndFrame: 包含"vol"(成交量)、"opid"(持仓量)两列

        所需数据字段：
            `volume` (需要持仓量数据配合)

        示例：
            # CJL量仓分析
            cjl = ta.CJL()
            high_volume = cjl["vol"] > ta.ma(cjl["vol"], length=20)  # 高成交量
            oi_increase = cjl["opid"] > ta.ref(cjl["opid"], length=1) # 持仓增加

            # 量仓配合分析
            volume_oi_rise = (cjl["vol"] > ta.ref(cjl["vol"], length=1)) & (cjl["opid"] > ta.ref(cjl["opid"], length=1))
        """
        # v,vol,opid
        ...

    @tobtind(lib="tqta")
    def OPI(self, close_oi=None, **kwargs) -> IndSeries:
        """
        持仓量指标 - 期货市场未平仓合约数量

        功能：
            分析期货市场持仓量变化，反映资金沉淀和市场情绪

        应用场景：
            - 资金流向分析
            - 市场情绪判断
            - 趋势强度评估
            - 风险控制

        计算原理：
            OPI = 当日未平仓合约数量
            反映期货市场的资金沉淀和投资者持仓情况

        参数：
            close_oi: 收盘持仓量数据
            **kwargs: 额外参数

        注意：
            - 需要期货合约持仓量数据
            - 持仓量增加表示资金流入
            - 持仓量减少表示资金流出
            - 反映市场参与度

        返回值：
            IndSeries: 持仓量序列

        所需数据字段：
            (需要持仓量数据)

        示例：
            # OPI持仓分析
            opi = ta.OPI()
            oi_uptrend = opi > ta.ma(opi, length=10)           # 持仓上升趋势
            new_high_oi = opi == ta.hhv(opi, length=20)        # 持仓创新高
            capital_inflow = opi > ta.ref(opi, length=1)       # 资金流入
        """
        ...

    @tobtind(lib="tqta")
    def PVT(self, **kwargs) -> IndSeries:
        """
        价量趋势指数 - 价格与成交量的协同变化分析

        功能：
            通过价格变化与成交量的乘积分析趋势强度

        应用场景：
            - 量价关系分析
            - 趋势确认
            - 买卖信号生成
            - 资金流向判断

        计算原理：
            PVT = 前日PVT + (当日收盘价-前日收盘价)/前日收盘价 × 当日成交量
            反映价格变动与成交量的协同变化

        参数：
            **kwargs: 额外参数

        注意：
            - PVT上升表示量价配合良好
            - 与价格背离时预警趋势转换
            - 适合趋势确认分析
            - 反映资金推动力度

        返回值：
            IndSeries: PVT值序列

        所需数据字段：
            `close`, `volume`

        示例：
            # PVT量价分析
            pvt = ta.PVT()
            healthy_uptrend = (close > ta.ref(close, length=1)) & (pvt > ta.ref(pvt, length=1))
            weak_uptrend = (close > ta.ref(close, length=1)) & (pvt < ta.ref(pvt, length=1))

            # PVT趋势信号
            pvt_breakout = pvt > ta.hhv(pvt, length=20)        # PVT突破
            pvt_breakdown = pvt < ta.llv(pvt, length=20)       # PVT跌破
        """
        # cv
        ...

    @tobtind(lib="tqta")
    def VOSC(self, short=12, long=26, **kwargs) -> IndSeries:
        """
        成交量振荡器 - 成交量移动平均离差分析

        功能：
            通过长短周期成交量均线离差分析量能变化

        应用场景：
            - 量能变化分析
            - 买卖信号确认
            - 突破有效性验证
            - 资金活跃度判断

        计算原理：
            VOSC = (短期成交量均线 - 长期成交量均线) / 长期成交量均线 × 100
            反映成交量能的变化幅度

        参数：
            short: 短期周期，默认12
            long: 长期周期，默认26
            **kwargs: 额外参数

        注意：
            - VOSC上穿零轴为量能金叉
            - VOSC下穿零轴为量能死叉
            - 数值大小反映量能变化强度
            - 适合量价配合分析

        返回值：
            IndSeries: VOSC值序列，单位为百分比

        所需数据字段：
            `volume`

        示例：
            # VOSC量能分析
            vosc = ta.VOSC(short=12, long=26)
            volume_increase = vosc > 0                         # 量能增加
            volume_surge = vosc > ta.hhv(vosc, length=20)      # 量能激增

            # 量价配合
            price_volume_confirmation = (close > ta.ref(close, length=1)) & (vosc > 0)
            price_volume_divergence = (close > ta.ref(close, length=1)) & (vosc < 0)
        """
        # v
        ...

    @tobtind(lib="tqta")
    def VROC(self, n=12, **kwargs) -> IndSeries:
        """
        成交量变动速率 - 成交量变化百分比分析

        功能：
            测量成交量变化的百分比速率，分析量能动量

        应用场景：
            - 量能动量分析
            - 突破确认
            - 资金流入流出判断
            - 市场活跃度变化

        计算原理：
            VROC = (当日成交量 - N日前成交量) / N日前成交量 × 100
            反映成交量在N周期内的百分比变化率

        参数：
            n: 计算周期，默认12
            **kwargs: 额外参数

        注意：
            - VROC上穿零轴为量能转强
            - VROC下穿零轴为量能转弱
            - 极值往往预示重大变化
            - 适合各类时间周期的量能分析

        返回值：
            IndSeries: VROC值序列，单位为百分比

        所需数据字段：
            `volume`

        示例：
            # VROC量能动量
            vroc = ta.VROC(n=12)
            volume_momentum_up = vroc > 0                      # 量能动量向上
            volume_surge_signal = vroc > ta.hhv(vroc, length=20) * 0.8  # 量能激增

            # 量能转换信号
            volume_turn_positive = (ta.ref(vroc, length=1) <= 0) & (vroc > 0)
            volume_turn_negative = (ta.ref(vroc, length=1) >= 0) & (vroc < 0)
        """
        # v
        ...

    @tobtind(lib="tqta")
    def VRSI(self, n=6, **kwargs) -> IndSeries:
        """
        成交量相对强弱指标 - 成交量动量的RSI版本

        功能：
            通过成交量变化分析量能动量的强弱状态

        应用场景：
            - 量能动量分析
            - 超买超卖判断
            - 背离分析
            - 量价关系验证

        计算原理：
            计算方式类似RSI，但基于成交量数据
            VRSI = 100 - 100 / (1 + RS)
            RS = N日内成交量上涨平均值 / N日内成交量下跌平均值

        参数：
            n: 计算周期，默认6
            **kwargs: 额外参数

        注意：
            - VRSI在70以上为量能超买
            - VRSI在30以下为量能超卖
            - 与价格RSI结合使用效果更好
            - 适合量能动量分析

        返回值：
            IndSeries: VRSI值序列，范围0-100

        所需数据字段：
            `volume`

        示例：
            # VRSI量能分析
            vrsi = ta.VRSI(n=6)
            volume_overbought = vrsi > 70                     # 量能超买
            volume_oversold = vrsi < 30                       # 量能超卖

            # 量价RSI配合
            price_rsi = ta.RSI(n=6)
            healthy_volume = (price_rsi > 50) & (vrsi > 50)   # 健康量价
            weak_volume = (price_rsi > 50) & (vrsi < 50)      # 量价背离
        """
        # v
        ...

    @tobtind(lib="tqta")
    def WVAD(self, **kwargs) -> IndSeries:
        """
        威廉变异离散量 - 威廉指标与成交量结合的分析工具

        功能：
            结合威廉指标和成交量分析资金流向和市场强度

        应用场景：
            - 资金流向分析
            - 市场强度判断
            - 买卖信号生成
            - 趋势确认

        计算原理：
            基于开盘、最高、最低、收盘价和成交量计算
            WVAD = (收盘价-开盘价) / (最高价-最低价) × 成交量
            综合反映价格位置和成交量信息

        参数：
            **kwargs: 额外参数

        注意：
            - WVAD为正表示资金流入
            - WVAD为负表示资金流出
            - 数值大小反映资金流向强度
            - 适合短线资金流向分析

        返回值：
            IndSeries: WVAD值序列

        所需数据字段：
            `open`, `high`, `low`, `close`, `volume`

        示例：
            # WVAD资金流向
            wvad = ta.WVAD()
            capital_inflow = wvad > 0                         # 资金流入
            capital_outflow = wvad < 0                        # 资金流出

            # 资金流向强度
            strong_inflow = wvad > ta.ma(wvad, length=20)     # 强势流入
            strong_outflow = wvad < ta.ma(wvad, length=20)    # 强势流出

            # WVAD突破信号
            wvad_breakout = wvad > ta.hhv(wvad, length=20)    # 资金流入突破
        """
        # ohlcv
        ...

    @tobtind(lib="tqta")
    def MA(self, n=30, **kwargs) -> IndSeries:
        """
        简单移动平均线 - 最基础的价格趋势平滑工具

        功能：
            计算指定周期内收盘价的算术平均值，消除短期波动，显示长期趋势

        应用场景：
            - 趋势方向识别
            - 支撑阻力位构建
            - 均线交叉策略
            - 价格与均线关系分析

        计算原理：
            MA = (P₁ + P₂ + ... + Pₙ) / n
            其中P为收盘价，n为计算周期
            所有历史数据权重相等

        参数：
            n: 移动平均周期，默认30
            **kwargs: 额外参数

        注意：
            - 对价格变化的反应相对滞后
            - 周期越长，平滑效果越明显但滞后性越大
            - 适合趋势明显的市场环境
            - 常作为其他技术指标的基础

        返回值：
            IndSeries: 简单移动平均值序列

        所需数据字段：
            `close`

        示例：
            # MA趋势分析
            ma = ta.MA(n=30)
            price_above_ma = close > ma                        # 价格在均线上方
            price_below_ma = close < ma                        # 价格在均线下方
            ma_uptrend = ma > ta.ref(ma, length=1)             # 均线上升趋势

            # 多周期MA系统
            ma_short = ta.MA(n=10)
            ma_long = ta.MA(n=30)
            golden_cross = ta.crossup(ma_short, ma_long)       # 金叉信号
            death_cross = ta.crossdown(ma_short, ma_long)      # 死叉信号
        """
        # c
        ...

    @tobtind(lib="tqta")
    def SMA(self, n=5, m=2, **kwargs) -> IndSeries:
        """
        扩展指数加权移动平均 - 可调节权重的平滑移动平均

        功能：
            提供可自定义权重的指数加权移动平均，平衡近期和远期数据的重要性

        应用场景：
            - 自定义平滑程度的需求
            - 特定权重模式的趋势分析
            - 交易系统优化
            - 技术指标定制

        计算原理：
            SMA = (Pₙ × m + 前日SMA × (n - m)) / n
            其中m为权重系数，n为周期
            允许调节近期数据的权重比例

        参数：
            n: 计算周期，默认5
            m: 权重系数，默认2
            **kwargs: 额外参数

        注意：
            - m值越大，近期数据权重越高
            - 当m=1时退化为简单移动平均
            - 适合需要定制化平滑程度的场景
            - 平衡响应速度和平滑效果

        返回值：
            IndSeries: 扩展指数加权移动平均值序列

        所需数据字段：
            `close`

        示例：
            # SMA定制化分析
            sma_fast = ta.SMA(n=5, m=3)                       # 快速SMA
            sma_slow = ta.SMA(n=10, m=2)                      # 慢速SMA
            custom_signal = ta.crossup(sma_fast, sma_slow)    # 定制信号

            # 权重优化
            high_weight = ta.SMA(n=5, m=4)                    # 高权重近期数据
            low_weight = ta.SMA(n=5, m=1)                     # 低权重近期数据
            weight_effect = high_weight - low_weight          # 权重影响
        """
        # c
        ...

    @tobtind(lib="tqta")
    def EMA(self, n=10, **kwargs) -> IndSeries:
        """
        指数加权移动平均 - 对近期价格赋予更高权重的移动平均

        功能：
            通过指数加权方式强调近期价格，减少滞后性，更快反应趋势变化

        应用场景：
            - 快速趋势识别
            - 短线交易信号
            - 动态支撑阻力
            - 与其他指标配合使用

        计算原理：
            EMA = α × 当日收盘价 + (1 - α) × 前日EMA
            α = 2 / (n + 1)
            近期价格权重较高，远期价格权重指数衰减

        参数：
            n: 计算周期，默认10
            **kwargs: 额外参数

        注意：
            - 对价格变化比SMA更敏感
            - 在震荡市中可能产生较多假信号
            - 适合趋势跟踪策略
            - 常作为MACD等指标的计算基础

        返回值：
            IndSeries: 指数加权移动平均值序列

        所需数据字段：
            `close`

        示例：
            # EMA趋势系统
            ema_fast = ta.EMA(n=12)                           # 快速EMA
            ema_slow = ta.EMA(n=26)                           # 慢速EMA
            ema_golden_cross = ta.crossup(ema_fast, ema_slow) # EMA金叉
            ema_death_cross = ta.crossdown(ema_fast, ema_slow) # EMA死叉

            # EMA支撑阻力
            dynamic_support = ta.EMA(n=20)                    # 动态支撑
            dynamic_resistance = ta.EMA(n=50)                 # 动态阻力
            support_test = close <= dynamic_support           # 测试支撑
        """
        # c
        ...

    @tobtind(lib="tqta")
    def EMA2(self, n=10, **kwargs) -> IndSeries:
        """
        线性加权移动平均 - 按时间线性加权的移动平均

        功能：
            采用线性递减权重，近期数据权重线性增加，平衡响应和平滑效果

        应用场景：
            - 平衡型的趋势分析
            - 需要线性权重的交易系统
            - 技术指标优化
            - 多时间框架分析

        计算原理：
            WMA = (P₁ × 1 + P₂ × 2 + ... + Pₙ × n) / (1 + 2 + ... + n)
            权重随时间线性递增，近期数据权重更高

        参数：
            n: 计算周期，默认10
            **kwargs: 额外参数

        注意：
            - 权重线性递增，比EMA更平缓
            - 滞后性介于SMA和EMA之间
            - 适合需要平衡响应的场景
            - 在趋势转换时表现稳定

        返回值：
            IndSeries: 线性加权移动平均值序列

        所需数据字段：
            `close`

        示例：
            # WMA多周期分析
            wma_short = ta.EMA2(n=10)                         # 短期WMA
            wma_long = ta.EMA2(n=30)                          # 长期WMA
            wma_cross = ta.crossup(wma_short, wma_long)       # WMA金叉

            # 不同MA类型比较
            sma_20 = ta.MA(n=20)
            ema_20 = ta.EMA(n=20)
            wma_20 = ta.EMA2(n=20)
            ma_comparison = (wma_20 - sma_20) / sma_20        # MA差异比较
        """
        # c
        ...

    @tobtind(lib="tqta")
    def TRMA(self, n=10, **kwargs) -> IndSeries:
        """
        三角移动平均线 - 双重平滑的移动平均变体

        功能：
            通过两次平均计算提供更平滑的趋势线，减少噪音干扰

        应用场景：
            - 极平滑趋势识别
            - 长期投资分析
            - 过滤市场噪音
            - 重大趋势确认

        计算原理：
            先计算n周期简单移动平均
            再对SMA结果进行n/2周期简单移动平均
            实现双重平滑效果

        参数：
            n: 计算周期，默认10
            **kwargs: 额外参数

        注意：
            - 滞后性明显大于其他移动平均
            - 适合长期趋势分析
            - 几乎完全过滤短期波动
            - 在趋势明显的市场中效果最佳

        返回值：
            IndSeries: 三角移动平均值序列

        所需数据字段：
            `close`

        示例：
            # TRMA长期趋势
            trma = ta.TRMA(n=20)                              # 三角移动平均
            long_term_trend = trma > ta.ref(trma, length=5)   # 长期趋势向上
            major_turn = (ta.ref(trma, length=2) < ta.ref(trma, length=1)) & (trma < ta.ref(trma, length=1))

            # TRMA与其他MA对比
            trma_smooth = ta.TRMA(n=20)
            sma_smooth = ta.MA(n=20)
            smoothness_advantage = abs(trma_smooth - ta.ref(trma_smooth, 1)) < abs(sma_smooth - ta.ref(sma_smooth, 1))
        """
        # c
        ...


class TaLib:
    """
    Ta-Lib技术指标计算类

    将目标数据转换为minibt内置指标数据，提供TA-Lib库中技术指标的Python接口。
    此类封装了TA-Lib的技术指标函数，使其能够与minibt框架无缝集成。

    主要特性：
    - 支持TA-Lib的所有技术指标类别
    - 自动处理数据格式转换
    - 提供统一的参数接口
    - 返回minibt兼容的IndSeries或IndFrame格式

    使用示例：
    ```python
    # 从数据源创建TaLib实例
    ta = TaLib(data)

    # 计算希尔伯特变换-主导周期
    ht_period = ta.HT_DCPERIOD()

    # 计算移动平均线
    sma = ta.SMA(length=20)

    # 计算相对强弱指数
    rsi = ta.RSI(length=14)
    ```

    参数：
        data: 输入数据，可以是pandas Series或DataFrame格式

    属性：
        _df: 存储输入数据的内部属性

    方法：
        所有TA-Lib技术指标方法，按功能分类：
        - 周期指标 (Cycle Indicator Functions)
        - 价格变换 (Price Transform)
        - 动量指标 (Momentum Indicators)
        - 波动率指标 (Volatility Indicators)
        - 成交量指标 (Volume Indicators)
        - 趋势指标 (Trend Indicators)
        - 统计函数 (Statistic Functions)
        - 数学变换 (Math Transform)
        - 数学运算符 (Math Operators)

    注意：
        - 使用前需要确保已安装TA-Lib库
        - 输入数据应包含所需的OHLCV列
        - 返回值会自动转换为minibt的IndSeries或IndFrame格式
        - 所有指标方法都支持**kwargs参数传递额外设置

    版本要求：
        - Python 3.7+
        - TA-Lib 0.4.0+
        - minibt 兼容版本
    """

    _df: IndSeries | IndFrame

    def __init__(self, data):
        """
        初始化TaLib计算器

        参数：
            data: 输入数据，支持以下格式：
                  - pandas Series (单列数据)
                  - pandas DataFrame (多列数据，需包含OHLCV等所需列)

        异常：
            ValueError: 当输入数据格式不支持时抛出
            TypeError: 当数据包含无法处理的类型时抛出
        """
        self._df = data

    # Cycle Indicator Functions
    @tobtind(category='Cycle Indicator Functions', lib='talib')
    def HT_DCPERIOD(self, **kwargs) -> IndSeries:
        """HT_DCPERIOD - Hilbert Transform - Dominant Cycle Period
        名称: 希尔伯特变换-主导周期

        Hilbert Transform - Dominant Cycle Period (HT_DCPERIOD) 通过希尔伯特变换
        计算价格数据的主导周期，用于识别市场的主要循环周期。

        应用场景：
        - 识别市场的周期性波动
        - 确定趋势转换的时间窗口
        - 配合其他周期指标进行多时间框架分析

        计算原理：
        使用希尔伯特变换对价格序列进行信号处理，提取其中的周期性成分，
        通过相位分析确定主导周期长度。

        参数：
            **kwargs: 额外参数，可传递minibt特定的设置参数

        注意：
            实例包括列：close (收盘价)

        返回值：
            IndSeries: 主导周期计算结果，每个值表示对应时间点的主导周期长度

        示例：
            ```python
            # 计算主导周期
            dominant_period = ta.HT_DCPERIOD()

            # 识别长周期和短周期
            long_cycle = dominant_period > 50
            short_cycle = dominant_period < 20

            # 周期转换信号
            cycle_turning = dominant_period.diff() > 5
            ```
        """
        ...

    @tobtind(category='Cycle Indicator Functions', lib='talib')
    def HT_DCPHASE(self, **kwargs) -> IndSeries:
        """HT_DCPHASE - Hilbert Transform - Dominant Cycle Phase
        名称: 希尔伯特变换-主导循环阶段

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 主导循环阶段计算结果
        """
        ...

    @tobtind(lines=["inphase", "quadrature"], category='Cycle Indicator Functions', lib='talib')
    def HT_PHASOR(self, **kwargs) -> IndFrame:
        """HT_PHASOR - Hilbert Transform - Phasor Components
        名称: 希尔伯特变换-希尔伯特变换相量分量

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndFrame:inphase, quadrature
        """
        ...

    @tobtind(lines=["sine", "leadsine"], category='Cycle Indicator Functions', lib='talib')
    def HT_SINE(self, **kwargs) -> IndFrame:
        """HT_SINE - Hilbert Transform - SineWave
        名称: 希尔伯特变换-正弦波

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndFrame:sine, leadsine
        """
        ...

    @tobtind(category='Cycle Indicator Functions', lib='talib')
    def HT_TRENDMODE(self, **kwargs) -> IndSeries:
        """HT_TRENDMODE - Hilbert Transform - Trend vs Cycle Mode
        名称: 希尔伯特变换-趋势与周期模式

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 趋势与周期模式判断结果
        """
        ...

    # Math Operator Functions
    @tobtind(category="Math Operator Functions", lib='talib')
    def ADD(self, **kwargs) -> IndSeries:
        """ADD - Vector Arithmetic Add
        名称:向量加法运算

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：high,low

        Returns:
            IndSeries: 向量加法运算结果
        """
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def DIV(self, **kwargs) -> IndSeries:
        """DIV - Vector Arithmetic Div
        名称:向量除法运算

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：high,low

        Returns:
            IndSeries: 向量除法运算结果
        """
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def MAX(self, timeperiod=30, **kwargs) -> IndSeries:
        """MAX - Highest value over a specified period
        名称:周期内最大值

        Args:
            timeperiod: 时间周期，默认值为30
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 周期内最大值计算结果
        """
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def MAXINDEX(self, timeperiod=30, **kwargs) -> IndSeries:
        """MAXINDEX - Index of highest value over a specified period
        名称:周期内最大值的索引

        Args:
            timeperiod: 时间周期，默认值为30
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 周期内最大值的索引结果
        """
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def MIN(self, timeperiod=30, **kwargs) -> IndSeries:
        """MIN - Lowest value over a specified period
        名称:周期内最小值

        Args:
            timeperiod: 时间周期，默认值为30
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 周期内最小值计算结果
        """
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def MININDEX(self, timeperiod=30, **kwargs) -> IndSeries:
        """MININDEX - Index of lowest value over a specified period
        名称:周期内最小值的索引

        Args:
            timeperiod: 时间周期，默认值为30
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 周期内最小值的索引结果
        """
        ...

    @tobtind(lines=["min", "max"], category="Math Operator Functions", lib='talib')
    def MINMAX(self, timeperiod=30, **kwargs) -> IndFrame:
        """MINMAX - Lowest and highest values over a specified period
        名称:周期内最小值和最大值

        Args:
            timeperiod: 时间周期，默认值为30
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndFrame:min,max
        """
        ...

    @tobtind(lines=["minidx", "maxidx"], category="Math Operator Functions", lib='talib')
    def MINMAXINDEX(self, timeperiod=30, **kwargs) -> IndFrame:
        """MINMAXINDEX - Indexes of lowest and highest values over a specified period
        名称:周期内最小值和最大值的索引

        Args:
            timeperiod: 时间周期，默认值为30
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndFrame:minidx, maxidx
        """
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def MULT(self, **kwargs) -> IndSeries:
        """MULT - Vector Arithmetic Mult
        名称:向量乘法运算

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：high,low

        Returns:
            IndSeries: 向量乘法运算结果
        """
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def SUB(self, **kwargs) -> IndSeries:
        """SUB - Vector Arithmetic Substraction
        名称:向量减法运算

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：high,low

        Returns:
            IndSeries: 向量减法运算结果
        """
        ...

    @tobtind(category="Math Operator Functions", lib='talib')
    def SUM(self, timeperiod=30, **kwargs) -> IndSeries:
        """SUM - Summation
        名称:周期内求和

        Args:
            timeperiod: 时间周期，默认值为30
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 周期内求和计算结果
        """
        ...

    # Math Transform Functions
    @tobtind(category="Math Transform Functions", lib='talib')
    def ACOS(self, **kwargs) -> IndSeries:
        """ACOS - Vector Trigonometric ACos
        名称:反余弦函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 反余弦函数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def ASIN(self, **kwargs) -> IndSeries:
        """ASIN - Vector Trigonometric ASin
        名称:反正弦函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 反正弦函数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def ATAN(self, **kwargs) -> IndSeries:
        """ATAN - Vector Trigonometric ATan
        名称:反正切函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 反正切函数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def CEIL(self, **kwargs) -> IndSeries:
        """CEIL - Vector Ceil
        名称:向上取整函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 向上取整计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def COS(self, **kwargs) -> IndSeries:
        """COS - Vector Trigonometric Cos
        名称:余弦函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 余弦函数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def COSH(self, **kwargs) -> IndSeries:
        """COSH - Vector Trigonometric Cosh
        名称:双曲余弦函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 双曲余弦函数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def EXP(self, **kwargs) -> IndSeries:
        """EXP - Vector Arithmetic Exp
        名称:指数函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 指数函数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def FLOOR(self, **kwargs) -> IndSeries:
        """FLOOR - Vector Floor
        名称:向下取整函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 向下取整计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def LN(self, **kwargs) -> IndSeries:
        """LN - Vector Log Natural
        名称:自然对数函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 自然对数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def LOG10(self, **kwargs) -> IndSeries:
        """LOG10 - Vector Log10
        名称:10底对数函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 10底对数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def SIN(self, **kwargs) -> IndSeries:
        """SIN - Vector Trigonometric Sin
        名称:正弦函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 正弦函数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def SINH(self, **kwargs) -> IndSeries:
        """SINH - Vector Trigonometric Sinh
        名称:双曲正弦函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 双曲正弦函数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def SQRT(self, **kwargs) -> IndSeries:
        """SQRT - Vector Square Root
        名称:平方根函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 平方根计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def TAN(self, **kwargs) -> IndSeries:
        """TAN - Vector Trigonometric Tan
        名称:正切函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 正切函数计算结果
        """
        ...

    @tobtind(category="Math Transform Functions", lib='talib')
    def TANH(self, **kwargs) -> IndSeries:
        """TANH - Vector Trigonometric Tanh
        名称:双曲正切函数

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 双曲正切函数计算结果
        """
        ...

    # Momentum Indicator Functions
    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ADX(self, timeperiod=14, **kwargs) -> IndSeries:
        """ADX - Average Directional Movement Index
        名称:平均趋向指数

        Args:
            timeperiod: 时间周期，默认值为14
            **kwargs: 额外参数

        NOTE:
            实例包括列：high, low, close

        Returns:
            IndSeries: 平均趋向指数计算结果
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ADXR(self, timeperiod=14, **kwargs) -> IndSeries:
        """ADXR- Average Directional Movement Index Rating
        名称:平均趋向指数的趋向指数

        Args:
            timeperiod: 时间周期，默认值为14
            **kwargs: 额外参数

        NOTE:
            实例包括列：high, low, close

        Returns:
            IndSeries: 平均趋向指数的趋向指数计算结果
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def APO(self, fastperiod=12, slowperiod=26, matype=0, **kwargs) -> IndSeries:
        """APO - Absolute Price Oscillator
        名称:绝对价格振荡器

        Args:
            fastperiod: 快速周期，默认值为12
            slowperiod: 慢速周期，默认值为26
            matype: 移动平均类型，默认值为0
            **kwargs: 额外参数

        NOTE:
            实例包括列：close

        Returns:
            IndSeries: 绝对价格振荡器计算结果
        """
        ...

    @tobtind(lines=["aroondown", "aroonup"], category="Momentum Indicator Functions", lib='talib')
    def AROON(self, timeperiod=14, **kwargs) -> IndFrame:
        """AROON - Aroon
        名称:阿隆指标

        Args:
            timeperiod: 时间周期，默认值为14
            **kwargs: 额外参数

        NOTE:
            实例包括列：high, low

        Returns:
            IndFrame:aroondown, aroonup
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def AROONOSC(self, timeperiod=14, **kwargs) -> IndSeries:
        """AROONOSC - Aroon Oscillator
        名称:阿隆振荡

        Args:
            timeperiod: 时间周期，默认值为14
            **kwargs: 额外参数

        NOTE:
            实例包括列：high, low

        Returns:
            IndSeries: 阿隆振荡计算结果
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def BOP(self, **kwargs) -> IndSeries:
        """BOP - Balance Of Power
        名称:均势指标

        Args:
            **kwargs: 额外参数

        NOTE:
            实例包括列：open,high, low,close

        Returns:
            IndSeries: 均势指标计算结果
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def CCI(self, timeperiod=14, **kwargs) -> IndSeries:
        """CCI - Commodity Channel Index
        名称:顺势指标

        Args:
            timeperiod: 时间周期，默认值为14
            **kwargs: 额外参数

        NOTE:
            实例包括列：high, low,close

        Returns:
            IndSeries: 顺势指标计算结果
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def CMO(self, timeperiod=14, **kwargs) -> IndSeries:
        """CMO - Chande Momentum Oscillator 钱德动量摆动指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 钱德动量摆动指标序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def DX(self, timeperiod=14, **kwargs) -> IndSeries:
        """DX - Directional Movement Index 动向指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndSeries: 动向指标序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def MACD(self, fastperiod=12, slowperiod=26, signalperiod=9, **kwargs) -> IndFrame:
        """MACD - Moving Average Convergence/Divergence 平滑异同移动平均线
        ---
        Args:
            fastperiod: 快速周期，默认12
            slowperiod: 慢速周期，默认26
            signalperiod: 信号周期，默认9
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndFrame: dif, dem, histogram
        """
        ...

    @tobtind(lines=["dif", "dem", "histogram"], category="Momentum Indicator Functions", lib='talib')
    def MACDEXT(self, fastperiod=12, fastmatype=0, slowperiod=26, slowmatype=0, signalperiod=9, signalmatype=0, **kwargs) -> IndFrame:
        """MACDEXT - MACD with controllable MA type 平滑异同移动平均线(可控制移动平均算法)
        ---
        Args:
            fastperiod: 快速周期，默认12
            fastmatype: 快速移动平均类型，默认0
            slowperiod: 慢速周期，默认26
            slowmatype: 慢速移动平均类型，默认0
            signalperiod: 信号周期，默认9
            signalmatype: 信号移动平均类型，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndFrame: dif, dem, histogram
        """
        ...

    @tobtind(lines=["dif", "dem", "histogram"], category="Momentum Indicator Functions", lib='talib')
    def MACDFIX(self, signalperiod=9, **kwargs) -> IndFrame:
        """MACDFIX - Moving Average Convergence/Divergence Fix 12/26 平滑异同移动平均线(固定快慢均线周期为12/26)
        ---
        Args:
            signalperiod: 信号周期，默认9
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndFrame: dif, dem, histogram
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def MFI(self, timeperiod=14, **kwargs) -> IndSeries:
        """MFI - Money Flow Index 资金流量指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close, volume
        Returns:
            IndSeries: 资金流量指标序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def MINUS_DI(self, timeperiod=14, **kwargs) -> IndSeries:
        """MINUS_DI - Minus Directional Indicator 下降动向值
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndSeries: 下降动向值序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def MINUS_DM(self, timeperiod=14, **kwargs) -> IndSeries:
        """MINUS_DM - Minus Directional Movement 下降动向变动值
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low
        Returns:
            IndSeries: 下降动向变动值序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def MOM(self, timeperiod=10, **kwargs) -> IndSeries:
        """MOM - Momentum 动量指标
        ---
        Args:
            timeperiod: 时间周期，默认10
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 动量指标序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def PLUS_DI(self, timeperiod=14, **kwargs) -> IndSeries:
        """PLUS_DI - Plus Directional Indicator 上升动向值
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndSeries: 上升动向值序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def PLUS_DM(self, timeperiod=14, **kwargs) -> IndSeries:
        """PLUS_DM - Plus Directional Movement 上升动向变动值
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low
        Returns:
            IndSeries: 上升动向变动值序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def PPO(self, fastperiod=12, slowperiod=26, matype=0, **kwargs) -> IndSeries:
        """PPO - Percentage Price Oscillator 价格震荡百分比指数
        ---
        Args:
            fastperiod: 快速周期，默认12
            slowperiod: 慢速周期，默认26
            matype: 移动平均类型，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 价格震荡百分比指数序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ROC(self, timeperiod=10, **kwargs) -> IndSeries:
        """ROC - Rate of change 变动率指标
        ---
        Args:
            timeperiod: 时间周期，默认10
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 变动率指标序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ROCP(self, timeperiod=10, **kwargs) -> IndSeries:
        """ROCP - Rate of change Percentage 百分比变动率
        ---
        Args:
            timeperiod: 时间周期，默认10
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 百分比变动率序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ROCR(self, timeperiod=10, **kwargs) -> IndSeries:
        """ROCR - Rate of change ratio 变动率比值
        ---
        Args:
            timeperiod: 时间周期，默认10
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 变动率比值序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ROCR100(self, timeperiod=10, **kwargs) -> IndSeries:
        """ROCR100 - Rate of change ratio 100 scale 100倍变动率比值
        ---
        Args:
            timeperiod: 时间周期，默认10
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 100倍变动率比值序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def RSI(self, timeperiod=14, **kwargs) -> IndSeries:
        """RSI - Relative Strength Index 相对强弱指数
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 相对强弱指数序列
        """
        ...

    @tobtind(lines=["slowk", "slowd"], category="Momentum Indicator Functions", lib='talib')
    def STOCH(self, fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0, **kwargs) -> IndFrame:
        """STOCH - Stochastic 随机指标(KD)
        ---
        Args:
            fastk_period: 快速K周期，默认5
            slowk_period: 慢速K周期，默认3
            slowk_matype: 慢速K移动平均类型，默认0
            slowd_period: 慢速D周期，默认3
            slowd_matype: 慢速D移动平均类型，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndFrame: slowk, slowd
        """
        ...

    @tobtind(lines=["fastk", "fastd"], category="Momentum Indicator Functions", lib='talib')
    def STOCHF(self, fastk_period=5, fastd_period=3, fastd_matype=0, **kwargs) -> IndFrame:
        """STOCHF - Stochastic Fast 快速随机指标
        ---
        Args:
            fastk_period: 快速K周期，默认5
            fastd_period: 快速D周期，默认3
            fastd_matype: 快速D移动平均类型，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndFrame: fastk, fastd
        """
        ...

    @tobtind(lines=["fastk", "fastd"], category="Momentum Indicator Functions", lib='talib')
    def STOCHRSI(self, timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0, **kwargs) -> IndFrame:
        """STOCHRSI - Stochastic Relative Strength Index 随机相对强弱指数
        ---
        Args:
            timeperiod: RSI周期，默认14
            fastk_period: 快速K周期，默认5
            fastd_period: 快速D周期，默认3
            fastd_matype: 快速D移动平均类型，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndFrame: fastk, fastd
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def TRIX(self, timeperiod=30, **kwargs) -> IndSeries:
        """TRIX - 1-day Rate-Of-Change of a Triple Smooth EMA 三重平滑指数移动平均变动率
        ---
        Args:
            timeperiod: 时间周期，默认30
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 三重平滑指数移动平均变动率序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def ULTOSC(self, timeperiod1=7, timeperiod2=14, timeperiod3=28, **kwargs) -> IndSeries:
        """ULTOSC - Ultimate Oscillator 终极波动指标
        ---
        Args:
            timeperiod1: 短周期，默认7
            timeperiod2: 中周期，默认14
            timeperiod3: 长周期，默认28
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndSeries: 终极波动指标序列
        """
        ...

    @tobtind(category="Momentum Indicator Functions", lib='talib')
    def WILLR(self, timeperiod=14, **kwargs) -> IndSeries:
        """WILLR - Williams' %R 威廉指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndSeries: 威廉指标序列
        """
        ...

    # Overlap Studies Functions
    @tobtind(lines=["upperband", "middleband", "lowerband"], overlap=True, category="overlap", lib='talib')
    def BBANDS(self, timeperiod=5, nbdevup=2, nbdevdn=2, matype=0, **kwargs) -> IndFrame:
        """BBANDS - Bollinger Bands 布林线指标
        ---
        Args:
            timeperiod: 时间周期，默认5
            nbdevup: 上轨标准差倍数，默认2
            nbdevdn: 下轨标准差倍数，默认2
            matype: 移动平均类型，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndFrame: upperband, middleband, lowerband
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def DEMA(self, timeperiod=30, **kwargs) -> IndSeries:
        """DEMA - Double Exponential Moving Average 双指数移动平均线
        ---
        Args:
            timeperiod: 时间周期，默认30
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 双指数移动平均线序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def EMA(self, timeperiod=30, **kwargs) -> IndSeries:
        """EMA - Exponential Moving Average 指数移动平均线
        ---
        Args:
            timeperiod: 时间周期，默认30
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 指数移动平均线序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def HT_TRENDLINE(self, **kwargs) -> IndSeries:
        """HT_TRENDLINE - Hilbert Transform - Instantaneous Trendline 希尔伯特瞬时趋势线
        ---
        Args:
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 希尔伯特瞬时趋势线序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def KAMA(self, timeperiod=30, **kwargs) -> IndSeries:
        """KAMA - Kaufman Adaptive Moving Average 考夫曼自适应移动平均线
        ---
        Args:
            timeperiod: 时间周期，默认30
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 考夫曼自适应移动平均线序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def MA(self, timeperiod=30, matype=0, **kwargs) -> IndSeries:
        """MA - Moving Average 移动平均线
        ---
        Args:
            timeperiod: 时间周期，默认30
            matype: 移动平均类型，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 移动平均线序列
        """
        ...

    @tobtind(lines=["mama", "fama"], overlap=True, category="overlap", lib='talib')
    def MAMA(self, fastlimit=0, slowlimit=0, **kwargs) -> IndFrame:
        """MAMA - MESA Adaptive Moving Average MESA自适应移动平均线
        ---
        Args:
            fastlimit: 快速限制，默认0
            slowlimit: 慢速限制，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndFrame: mama, fama
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def MAVP(self, periods=14, minperiod=2, maxperiod=30, matype=0, **kwargs) -> IndSeries:
        """MAVP - Moving Average with Variable Period 可变周期移动平均线
        ---
        Args:
            periods: 周期，默认14
            minperiod: 最小周期，默认2
            maxperiod: 最大周期，默认30
            matype: 均线类型

        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 移动平均线序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def MIDPOINT(self, timeperiod=14, **kwargs) -> IndSeries:
        """MIDPOINT - MidPoint over period 周期中点指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 周期中点指标序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def MIDPRICE(self, timeperiod=14, **kwargs) -> IndSeries:
        """MIDPRICE - Midpoint Price over period 周期中点价格指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low
        Returns:
            IndSeries: 周期中点价格指标序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def SAR(self, acceleration=0, maximum=0, **kwargs) -> IndSeries:
        """SAR - Parabolic SAR 抛物线指标
        ---
        Args:
            acceleration: 加速度，默认0
            maximum: 最大值，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low
        Returns:
            IndSeries: 抛物线指标序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def SAREXT(self, startvalue=0, offsetonreverse=0, accelerationinitlong=0, accelerationlong=0, accelerationmaxlong=0, accelerationinitshort=0, accelerationshort=0, accelerationmaxshort=0, **kwargs) -> IndSeries:
        """SAREXT - Parabolic SAR - Extended 扩展抛物线指标
        ---
        Args:
            startvalue: 起始值，默认0
            offsetonreverse: 反转偏移，默认0
            accelerationinitlong: 多头初始加速度，默认0
            accelerationlong: 多头加速度，默认0
            accelerationmaxlong: 多头最大加速度，默认0
            accelerationinitshort: 空头初始加速度，默认0
            accelerationshort: 空头加速度，默认0
            accelerationmaxshort: 空头最大加速度，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low
        Returns:
            IndSeries: 扩展抛物线指标序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def SMA(self, timeperiod=30, **kwargs) -> IndSeries:
        """SMA - Simple Moving Average 简单移动平均线
        ---
        Args:
            timeperiod: 时间周期，默认30
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 简单移动平均线序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def T3(self, timeperiod=5, vfactor=0, **kwargs) -> IndSeries:
        """T3 - Triple Exponential Moving Average (T3) 三重指数移动平均线
        ---
        Args:
            timeperiod: 时间周期，默认5
            vfactor: 体积因子，默认0
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 三重指数移动平均线序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def TEMA(self, timeperiod=30, **kwargs) -> IndSeries:
        """TEMA - Triple Exponential Moving Average 三重指数移动平均线
        ---
        Args:
            timeperiod: 时间周期，默认30
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 三重指数移动平均线序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def TRIMA(self, timeperiod=30, **kwargs) -> IndSeries:
        """TRIMA - Triangular Moving Average 三角形移动平均线
        ---
        Args:
            timeperiod: 时间周期，默认30
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 三角形移动平均线序列
        """
        ...

    @tobtind(overlap=True, category="overlap", lib='talib')
    def WMA(close, timeperiod=30, **kwargs) -> IndSeries:
        """WMA - Weighted Moving Average 加权移动平均线
        ---
        Args:
            timeperiod: 时间周期，默认30
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 加权移动平均线序列
        """
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
                                               "CDLXSIDEGAP3METHODS",] = "CDL2CROWS", penetration=0, **kwargs) -> IndSeries:
        """Pattern Recognition Functions 形态识别指标
        ---
        Args:
            name: 形态名称，默认"CDL2CROWS"（两只乌鸦）
            penetration: 穿透程度，默认0
            **kwargs: 额外参数

        ### name参考
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
            "CDLXSIDEGAP3METHODS"上升/下降跳空三法

        NOTE:
            实例包括列：open, high, low, close

        Returns:
            IndSeries: 形态识别指标序列
        """
        ...

    # Price Transform Functions
    @tobtind(overlap=True, category="Price Transform Functions", lib='talib')
    def AVGPRICE(self, **kwargs) -> IndSeries:
        """AVGPRICE - Average Price 平均价格指标
        ---
        Args:
            **kwargs: 额外参数
        NOTE:
            实例包括列：open, high, low, close
        Returns:
            IndSeries: 平均价格指标序列
        """
        ...

    @tobtind(overlap=True, category="Price Transform Functions", lib='talib')
    def MEDPRICE(self, **kwargs) -> IndSeries:
        """MEDPRICE - Median Price 中位数价格指标
        ---
        Args:
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low
        Returns:
            IndSeries: 中位数价格指标序列
        """
        ...

    @tobtind(overlap=True, category="Price Transform Functions", lib='talib')
    def TYPPRICE(self, **kwargs) -> IndSeries:
        """TYPPRICE - Typical Price 代表性价格指标
        ---
        Args:
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndSeries: 代表性价格指标序列
        """
        ...

    @tobtind(overlap=True, category="Price Transform Functions", lib='talib')
    def WCLPRICE(self, **kwargs) -> IndSeries:
        """WCLPRICE - Weighted Close Price 加权收盘价指标
        ---
        Args:
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndSeries: 加权收盘价指标序列
        """
        ...

    # Statistic Functions 统计学指标
    @tobtind(category="Price Transform Functions", lib='talib')
    def BETA(self, timeperiod=5, **kwargs) -> IndSeries:
        """BETA - Beta β系数
        ---
        Args:
            timeperiod: 时间周期，默认5
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low
        Returns:
            IndSeries: β系数序列
        """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def CORREL(self, timeperiod=30, **kwargs) -> IndSeries:
        """CORREL - Pearson's Correlation Coefficient (r) 皮尔逊相关系数
        ---
        Args:
            timeperiod: 时间周期，默认30
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low
        Returns:
            IndSeries: 皮尔逊相关系数序列
        """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def LINEARREG(self, timeperiod=14, **kwargs) -> IndSeries:
        """LINEARREG - Linear Regression 线性回归指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 线性回归指标序列
        """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def LINEARREG_ANGLE(self, timeperiod=14, **kwargs) -> IndSeries:
        """LINEARREG_ANGLE - Linear Regression Angle 线性回归角度指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 线性回归角度指标序列
        """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def LINEARREG_INTERCEPT(self, timeperiod=14, **kwargs) -> IndSeries:
        """LINEARREG_INTERCEPT - Linear Regression Intercept 线性回归截距指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 线性回归截距指标序列
        """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def LINEARREG_SLOPE(self, timeperiod=14, **kwargs) -> IndSeries:
        """LINEARREG_SLOPE - Linear Regression Slope 线性回归斜率指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 线性回归斜率指标序列
        """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def STDDEV(self, timeperiod=5, nbdev=1, **kwargs) -> IndSeries:
        """STDDEV - Standard Deviation 标准偏差指标
        ---
        Args:
            timeperiod: 时间周期，默认5
            nbdev: 偏差倍数，默认1
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 标准偏差指标序列
        """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def TSF(self, timeperiod=14, **kwargs) -> IndSeries:
        """TSF - Time Series Forecast 时间序列预测指标
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 时间序列预测指标序列
        """
        ...

    @tobtind(category="Price Transform Functions", lib='talib')
    def VAR(self, timeperiod=5, nbdev=1, **kwargs) -> IndSeries:
        """VAR - VAR 方差指标
        ---
        Args:
            timeperiod: 时间周期，默认5
            nbdev: 偏差倍数，默认1
            **kwargs: 额外参数
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 方差指标序列
        """
        ...

    # Volatility Indicator Functions 波动率指标函数
    @tobtind(category="Volatility Indicator Functions", lib='talib')
    def ATR(self, timeperiod=14, **kwargs) -> IndSeries:
        """ATR - Average True Range 真实波动幅度均值
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndSeries: 真实波动幅度均值序列
        """
        ...

    @tobtind(category="Volatility Indicator Functions", lib='talib')
    def NATR(self, timeperiod=14, **kwargs) -> IndSeries:
        """NATR - Normalized Average True Range 归一化波动幅度均值
        ---
        Args:
            timeperiod: 时间周期，默认14
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndSeries: 归一化波动幅度均值序列
        """
        ...

    @tobtind(category="Volatility Indicator Functions", lib='talib')
    def TRANGE(self, **kwargs) -> IndSeries:
        """TRANGE - True Range 真实波动范围
        ---
        Args:
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close
        Returns:
            IndSeries: 真实波动范围序列
        """
        ...

    # Volume Indicators 成交量指标
    @tobtind(category="Volume Indicators Functions", lib='talib')
    def AD(self, **kwargs) -> IndSeries:
        """AD - Chaikin A/D Line 累积/派发线
        ---
        Args:
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close, volume
        Returns:
            IndSeries: 累积/派发线序列
        """
        ...

    @tobtind(category="Volume Indicators Functions", lib='talib')
    def ADOSC(self, fastperiod=3, slowperiod=10, **kwargs) -> IndSeries:
        """ADOSC - Chaikin A/D Oscillator Chaikin震荡指标
        ---
        Args:
            fastperiod: 快速周期，默认3
            slowperiod: 慢速周期，默认10
            **kwargs: 额外参数
        NOTE:
            实例包括列：high, low, close, volume
        Returns:
            IndSeries: Chaikin震荡指标序列
        """
        ...

    @tobtind(category="Volume Indicators Functions", lib='talib')
    def OBV(self, **kwargs) -> IndSeries:
        """OBV - On Balance Volume 能量潮指标
        ---
        Args:
            **kwargs: 额外参数
        NOTE:
            实例包括列：close, volume
        Returns:
            IndSeries: 能量潮指标序列
        """
        ...


class FinTa:
    """finta指标指引"""
    _df: IndSeries | IndFrame

    def __init__(self, data):
        self._df = data

    @tobtind(overlap=True, lib='finta')
    def SMA(self, period: int = 41, **kwargs) -> IndSeries:
        """简单移动平均线 -  pandas中的滚动平均值，又称MA
        ---
        Args:
            period: 周期，默认41
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 简单移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def SMM(self, period: int = 9, **kwargs) -> IndSeries:
        """简单移动中位数 - 移动平均线的替代指标，对异常值更稳健
        ---
        Args:
            period: 周期，默认9
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 简单移动中位数序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def SSMA(self, period: int = 9, adjust: bool = True, **kwargs) -> IndSeries:
        """平滑简单移动平均线
        ---
        Args:
            period: 周期，默认9
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 平滑简单移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def EMA(self, period: int = 9, adjust: bool = True, **kwargs) -> IndSeries:
        """指数加权移动平均线 - 适用于趋势市场，常与其他指标结合确认走势
        ---
        Args:
            period: 周期，默认9
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 指数加权移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def DEMA(self, period: int = 9, adjust: bool = True, **kwargs) -> IndSeries:
        """双指数移动平均线 - 通过对EMA二次处理减少滞后
        ---
        Args:
            period: 周期，默认9
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 双指数移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def TEMA(self, period: int = 9, adjust: bool = True, **kwargs) -> IndSeries:
        """三重指数移动平均线 - 通过对EMA三次处理减少滞后
        ---
        Args:
            period: 周期，默认9
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 三重指数移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def TRIMA(self, period: int = 18, **kwargs) -> IndSeries:
        """三角形移动平均线 - 对周期中间价格赋予更高权重
        ---
        Args:
            period: 周期，默认18
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 三角形移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def TRIX(self, period: int = 20, adjust: bool = True, **kwargs) -> IndSeries:
        """三重指数移动平均变化率 - 围绕零轴波动，交叉零轴产生买卖信号
        ---
        Args:
            period: 周期，默认20
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 三重指数移动平均变化率序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def LWMA(self, period: int, **kwargs) -> IndSeries:
        """线性加权移动平均线
        ---
        Args:
            period: 周期
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 线性加权移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def VAMA(self, period: int = 8, **kwargs) -> IndSeries:
        """成交量调整移动平均线
        ---
        Args:
            period: 周期，默认8
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries: 成交量调整移动平均线序列
        """
        ...

    @tobtind(lib='finta')
    def VIDYA(self, period: int = 9, smoothing_period: int = 12, **kwargs) -> IndSeries:
        """可变指数动态平均线 - EMA的改进版，平滑因子随价格波动变化
        ---
        Args:
            period: 周期，默认9
            smoothing_period: 平滑周期，默认12
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 可变指数动态平均线序列
        """
        ...

    @tobtind(lib='finta')
    def ER(self, period: int = 10, **kwargs) -> IndSeries:
        """考夫曼效率指标 - 震荡于+100至-100之间，指示趋势方向
        ---
        Args:
            period: 周期，默认10
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 考夫曼效率指标序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def KAMA(self, er: int = 10, ema_fast: int = 2, ema_slow: int = 30, period: int = 20, **kwargs) -> IndSeries:
        """考夫曼自适应移动平均线 - 结合方向与波动率，适应市场变化
        ---
        Args:
            er: 效率周期，默认10
            ema_fast: 快速EMA周期，默认2
            ema_slow: 慢速EMA周期，默认30
            period: 周期，默认20
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 考夫曼自适应移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def ZLEMA(self, period: int = 26, adjust: bool = True, **kwargs) -> IndSeries:
        """零滞后指数移动平均线 - 消除移动平均线固有的滞后性
        ---
        Args:
            period: 周期，默认26
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 零滞后指数移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def WMA(self, period: int = 9, **kwargs) -> IndSeries:
        """加权移动平均线 - 比EMA更注重近期数据，帮助识别趋势
        ---
        Args:
            period: 周期，默认9
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 加权移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def HMA(self, period: int = 16, **kwargs) -> IndSeries:
        """赫尔移动平均线 - 曲线更平滑，滞后性低，适用于中长期交易
        ---
        Args:
            period: 周期，默认16
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 赫尔移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def EVWMA(self, period: int = 20, **kwargs) -> IndSeries:
        """弹性成交量加权移动平均线 - 近似近n期每股平均成交价
        ---
        Args:
            period: 周期，默认20
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries: 弹性成交量加权移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def VWAP(self, **kwargs) -> IndSeries:
        """成交量加权平均价格 - 交易基准指标，计算当日总成交额/总成交量
        ---
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries: 成交量加权平均价格序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def SMMA(self, period: int = 42, adjust: bool = True, **kwargs) -> IndSeries:
        """平滑移动平均线 - 近期价格与历史价格权重相等
        ---
        Args:
            period: 周期，默认42
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 平滑移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def ALMA(self, period: int = 9, sigma: int = 6, offset: int = 0.85, **kwargs) -> IndSeries:
        """阿尔诺·勒古克斯移动平均线
        ---
        Args:
            period: 周期，默认9
            sigma: 标准差，默认6
            offset: 偏移量，默认0.85
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 阿尔诺·勒古克斯移动平均线序列
        """

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
    def MAMA(self, period: int = 16, **kwargs) -> IndSeries:
        """MESA自适应移动平均线
        ---
        Args:
            period: 周期，默认16
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: MESA自适应移动平均线序列
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def FRAMA(self, period: int = 16, batch: int = 10, **kwargs) -> IndSeries:
        """分形自适应移动平均线
        ---
        Args:
            period: 周期，默认16
            batch: 批次大小，默认10
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 分形自适应移动平均线序列
        """
        ...

    @tobtind(lines=["macd", "macdh"], lib='finta')
    def MACD(self, period_fast: int = 12, period_slow: int = 26, signal: int = 9, adjust: bool = True, **kwargs) -> IndFrame:
        """指数平滑异同移动平均线 - 包含MACD线、信号线和MACD差
        ---
        Args:
            period_fast: 快速周期，默认12
            period_slow: 慢速周期，默认26
            signal: 信号周期，默认9
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndFrame:macd,macdh
        """
        ...

    @tobtind(lines=["ppo", "ppos", "ppos"], lib='finta')
    def PPO(self, period_fast: int = 12, period_slow: int = 26, signal: int = 9, adjust: bool = True, **kwargs) -> IndFrame:
        """价格百分比振荡器 - 类似MACD，以相对值表示移动平均差
        ---
        Args:
            period_fast: 快速周期，默认12
            period_slow: 慢速周期，默认26
            signal: 信号周期，默认9
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndFrame:ppo,ppos,ppos
        """
        ...

    @tobtind(lines=["macd", "macdh"], lib='finta')
    def VW_MACD(self, period_fast: int = 12, period_slow: int = 26, signal: int = 9, adjust: bool = True, **kwargs) -> IndFrame:
        """成交量加权MACD - 基于成交量加权移动平均计算的MACD
        ---
        Args:
            period_fast: 快速周期，默认12
            period_slow: 慢速周期，默认26
            signal: 信号周期，默认9
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:macd,macdh
        """
        ...

    @tobtind(lines=["macd", "macdh"], lib='finta')
    def EV_MACD(self, period_fast: int = 20, period_slow: int = 40, signal: int = 9, adjust: bool = True, **kwargs) -> IndFrame:
        """弹性成交量加权MACD - 基于EVWMA计算的MACD变体
        ---
        Args:
            period_fast: 快速周期，默认20
            period_slow: 慢速周期，默认40
            signal: 信号周期，默认9
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:macd,macdh
        """
        ...

    @tobtind(lib='finta')
    def MOM(self, period: int = 10, **kwargs) -> IndSeries:
        """动量指标 - 固定时间间隔的价格差，围绕零轴波动
        ---
        Args:
            period: 周期，默认10
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 动量指标序列
        """
        ...

    @tobtind(lib='finta')
    def ROC(self, period: int = 12, **kwargs) -> IndSeries:
        """变化率指标 - 衡量价格较n期前的百分比变化
        ---
        Args:
            period: 周期，默认12
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 变化率指标序列
        """
        ...

    @tobtind(lib='finta')
    def VBM(self, roc_period: int = 12, atr_period: int = 26, **kwargs) -> IndSeries:
        """波动率基差动量 - 类似ROC，但除以ATR波动率
        ---
        Args:
            roc_period: ROC周期，默认12
            atr_period: ATR周期，默认26
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 波动率基差动量序列
        """
        ...

    @tobtind(lib='finta')
    def RSI(self, period: int = 14, adjust: bool = True, **kwargs) -> IndSeries:
        """相对强弱指数 - 震荡于0-100之间，70以上超买，30以下超卖
        ---
        Args:
            period: 周期，默认14
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 相对强弱指数序列
        """
        ...

    @tobtind(lib='finta')
    def IFT_RSI(self, rsi_period: int = 5, wma_period: int = 9, **kwargs) -> IndSeries:
        """改进型逆Fisher变换RSI - 交叉±0.5产生交易信号
        ---
        Args:
            rsi_period: RSI周期，默认5
            wma_period: WMA周期，默认9
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 改进型逆Fisher变换RSI序列
        """
        ...

    @tobtind(lib='finta')
    def SWI(self, period: int = 16, **kwargs) -> IndSeries:
        """正弦波指标
        ---
        Args:
            period: 周期，默认16
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 正弦波指标序列
        """
        ...

    @tobtind(lib='finta')
    def DYMI(self, adjust: bool = True, **kwargs) -> IndSeries:
        """动态动量指数 - 可变周期RSI，3-30间波动，更早产生信号
        ---
        Args:
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries: 动态动量指数序列
        """

    @tobtind(lib='finta')
    def TR(self, **kwargs) -> IndSeries:
        """真实波幅 - 取三个价格范围的最大值：当期最高价减当期最低价、当期最高价减前收盘价的绝对值、当期最低价减前收盘价的绝对值
        ---
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def ATR(self, period: int = 14, **kwargs) -> IndSeries:
        """平均真实波幅 - 真实波幅的移动平均值
        ---
        Args:
            period: 周期，默认14
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def SAR(self, af: int = 0.02, amax: int = 0.2, **kwargs) -> IndSeries:
        """停损反转指标 - 随趋势延伸跟踪价格，上涨时在价格下方，下跌时在价格上方，价格突破指标时触发反转信号
        ---
        Args:
            af: 加速因子，默认0.02
            amax: 最大加速因子，默认0.2
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lines=["psar", "psarbull", "psarbear"], overlap=True, lib='finta')
    def PSAR(self, iaf: int = 0.02, maxaf: int = 0.2, **kwargs) -> IndFrame:
        """抛物线停损反转指标 - 用于判断趋势方向和潜在反转，通过跟踪止损点确定买卖点
        ---
        Args:
            iaf: 初始加速因子，默认0.02
            maxaf: 最大加速因子，默认0.2
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:psar,psarbull,psarbear
        """
        ...

    @tobtind(lines=["upper_bb", "middle_band", "lower_bb"], overlap=True, lib='finta')
    def BBANDS(self, period: int = 20, MA: IndSeries = None, std_multiplier: float = 2, **kwargs) -> IndFrame:
        """布林带 - 移动平均线上下的波动率带，波动率基于标准差，波动率增大时带宽扩大，减小时缩小，支持传入自定义移动平均线
        ---
        Args:
            period: 周期，默认20
            MA: 移动平均线序列，默认None
            std_multiplier: 标准差倍数，默认2
        NOTE:
            实例包括列：close
        Returns:
            IndFrame:upper_bb,middle_band,lower_bb
        """
        ...

    @tobtind(lines=["upper_bb", "middle_band", "lower_bb"], lib='finta')
    def MOBO(self, period: int = 10, std_multiplier: float = 0.8, **kwargs) -> IndFrame:
        """MOBO带 - 基于10期0.8倍标准差的波动带，价格突破带时可能预示趋势或价格波动，42%的价格波动（噪音）位于带内
        ---
        Args:
            period: 周期，默认10
            std_multiplier: 标准差倍数，默认0.8
        NOTE:
            实例包括列：close
        Returns:
            IndFrame:upper_bb,middle_band,lower_bb
        """
        ...

    @tobtind(overlap=True, lib='finta')
    def BBWIDTH(self, period: int = 20, MA: IndSeries = None, **kwargs) -> IndSeries:
        """布林带带宽 - 标准化表示布林带的宽度
        ---
        Args:
            period: 周期，默认20
            MA: 移动平均线序列，默认None
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def PERCENT_B(self, period: int = 20, MA: IndSeries = None, **kwargs) -> IndSeries:
        """%b指标 - 基于随机指标公式，显示价格在布林带中的位置，上轨为1，下轨为0
        ---
        Args:
            period: 周期，默认20
            MA: 移动平均线序列，默认None
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...
        import finta

    @tobtind(lines=["up", "down"], lib='finta')
    def KC(self, period: int = 20, atr_period: int = 10, MA: IndSeries = None, kc_mult: float = 2, **kwargs) -> IndFrame:
        """肯特纳通道 - 基于指数移动平均线的波动率通道，用平均真实波幅（ATR）确定带宽，通常为20期EMA上下各2倍ATR，用于识别趋势反转和超买超卖
        ---
        Args:
            period: 周期，默认20
            atr_period: ATR周期，默认10
            MA: 移动平均线序列，默认None
            kc_mult: ATR倍数，默认2
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:up,down
        """
        ...

    @tobtind(lines=["lower", "middle", "upper"], lib='finta')
    def DO(self, upper_period: int = 20, lower_period: int = 5, **kwargs) -> IndFrame:
        """唐奇安通道 - 绘制过去一段时间内的最高价和最低价
        ---
        Args:
            upper_period: 上轨周期，默认20
            lower_period: 下轨周期，默认5
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:lower,middle,upper
        """
        ...

    @tobtind(lines=["diplus", "diminus"], lib='finta')
    def DMI(self, period: int = 14, adjust: bool = True, **kwargs) -> IndFrame:
        """方向移动指数 - 评估价格方向和强度，帮助判断多空方向，对趋势交易策略尤其有用，能区分趋势强弱
        ---
        Args:
            period: 周期，默认14
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:diplus,diminus
        """
        ...

    @tobtind(lib='finta')
    def ADX(self, period: int = 14, adjust: bool = True, **kwargs) -> IndSeries:
        """平均趋向指数 - 仅表示趋势强度，不指示方向，20以下为弱趋势，40以上为强趋势，50以上为极强趋势
        ---
        Args:
            period: 周期，默认14
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lines=["s1", "s2", "s3", "s4", "r1", "r2", "r3", "r4"], lib='finta')
    def PIVOT(self, **kwargs) -> IndFrame:
        """枢轴点 - 重要的支撑和阻力位，通过最高价、最低价和收盘价计算，通常使用前一周期数据计算当前周期枢轴点
        ---
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:s1,s2,s3,s4,r1,r2,r3,r4
        """
        ...

    @tobtind(lines=["s1", "s2", "s3", "s4", "r1", "r2", "r3", "r4"], lib='finta')
    def PIVOT_FIB(self, **kwargs) -> IndFrame:
        """斐波那契枢轴点 - 先计算经典枢轴点，再结合前一周期波动范围与斐波那契比例计算支撑和阻力位
        ---
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:s1,s2,s3,s4,r1,r2,r3,r4
        """
        ...

    @tobtind(lib='finta')
    def STOCH(self, period: int = 14, **kwargs) -> IndSeries:
        """随机振荡器%K - 动量指标，比较证券收盘价与一定时期内价格范围的关系，可通过调整周期或取移动平均降低灵敏度
        ---
        Args:
            period: 周期，默认14
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def STOCHD(self, period: int = 3, stoch_period: int = 14, **kwargs) -> IndSeries:
        """随机振荡器%D - %K的3期简单移动平均
        ---
        Args:
            period: %D周期，默认3
            stoch_period: %K周期，默认14
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lines=["STOCHRSI"], lib='finta')
    def STOCHRSI(self, rsi_period: int = 14, stoch_period: int = 14, **kwargs) -> IndSeries:
        """随机相对强弱指数 - 将随机指标公式应用于RSI值，衡量RSI在一定时期高低范围内的水平，震荡于0-1之间
        ---
        Args:
            rsi_period: RSI周期，默认14
            stoch_period: 随机指标周期，默认14
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries:STOCHRSI
        """
        ...

    @tobtind(lib='finta')
    def WILLIAMS(self, period: int = 14, **kwargs) -> IndSeries:
        """威廉指标%R - 显示当前收盘价相对于过去N天高低区间的位置，负值刻度，-100为最低，0为最高
        ---
        Args:
            period: 周期，默认14
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def UO(self, **kwargs) -> IndSeries:
        """终极振荡器 - 跨三个时间框架捕捉动量，避免单一时间框架振荡器的缺陷
        ---
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def AO(self, slow_period: int = 34, fast_period: int = 5, **kwargs) -> IndSeries:
        """真棒振荡器 - 衡量市场动量，计算34期与5期简单移动平均的差值（基于K线中点而非收盘价），用于确认趋势或预测反转
        ---
        Args:
            slow_period: 慢速周期，默认34
            fast_period: 快速周期，默认5
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def MI(self, period: int = 9, adjust: bool = True, **kwargs) -> IndSeries:
        """质量指数 - 基于高低范围识别趋势反转，无方向偏差的波动率指标，通过范围扩张预示当前趋势反转
        ---
        Args:
            period: 周期，默认9
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def BOP(self, **kwargs) -> IndSeries:
        """功率平衡指标
        ---
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lines=["vim", "vip"], lib='finta')
    def VORTEX(self, period: int = 14, **kwargs) -> IndFrame:
        """涡旋指标 - 两条震荡线分别识别正负趋势移动，基于近两期高低点距离计算，距离越长趋势越强
        ---
        Args:
            period: 周期，默认14
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:vim,vip
        """
        ...

    @tobtind(lines=["k", "signal"], lib='finta')
    def KST(self, r1: int = 10, r2: int = 15, r3: int = 20, r4: int = 30, **kwargs) -> IndFrame:
        """确然指标 - 基于四个时间框架的平滑变化率，可通过背离、超买超卖、信号线交叉等判断信号
        ---
        Args:
            r1: 第一个时间框架，默认10
            r2: 第二个时间框架，默认15
            r3: 第三个时间框架，默认20
            r4: 第四个时间框架，默认30
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:k,signal
        """
        ...

    @tobtind(lib='finta')
    def TSI(self, long: int = 25, short: int = 13, signal: int = 13, adjust: bool = True, **kwargs) -> IndSeries:
        """真实强度指数 - 基于价格变化的双重平滑动量振荡器
        ---
        Args:
            long: 长期周期，默认25
            short: 短期周期，默认13
            signal: 信号周期，默认13
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def TP(self, **kwargs) -> IndSeries:
        """典型价格 - 某一时期内最高价、最低价和收盘价的算术平均值
        ---
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def ADL(self, **kwargs) -> IndSeries:
        """累积分布线 - 衡量资金流入流出，与涨跌线不同，用于判断买卖压力或确认趋势强度
        ---
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def CHAIKIN(self, adjust: bool = True, **kwargs) -> IndSeries:
        """柴金振荡器 - 计算累积分布线的3期EMA与10期EMA的差值，凸显累积分布线的动量
        ---
        Args:
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def MFI(self, period: int = 14, **kwargs) -> IndSeries:
        """资金流量指数 - 衡量资金流入流出的动量指标，可视为成交量调整后的RSI，超买超卖阈值为80和20
        ---
        Args:
            period: 周期，默认14
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def OBV(self, **kwargs) -> IndSeries:
        """能量潮指标 - 累积指标，上涨日加成交量，下跌日减成交量，通过与价格背离预测走势或确认趋势
        ---
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def WOBV(self, **kwargs) -> IndSeries:
        """加权能量潮指标 - 考虑价格差异的OBV变体，避免常规OBV中价格小幅波动但成交量大时的剧烈变化
        ---
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def VZO(self, period: int = 14, adjust: bool = True, **kwargs) -> IndSeries:
        """成交量震荡指标 - 利用价格、前一期价格和移动平均线计算震荡值，领先指标，基于超买超卖计算买卖信号。5%-40%为上升趋势区，-40%-5%为下降趋势区；40%以上超买，60%以上极度超买；-40%以下超卖，-60%以下极度超卖。
        ---
        Args:
            period: 周期，默认14
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def PZO(self, period: int = 14, adjust: bool = True, **kwargs) -> IndSeries:
        """价格震荡指标 - 仅基于一个条件：若当日收盘价高于昨日收盘价则为正值（看涨），否则为负值（看跌）。
        ---
        Args:
            period: 用于PZO计算的周期，默认14
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def EFI(self, period: int = 13, adjust: bool = True, **kwargs) -> IndSeries:
        """艾尔德力度指数 - 利用价格和成交量评估走势力度或识别潜在转折点。
        ---
        Args:
            period: 周期，默认13
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def CFI(self, adjust: bool = True, **kwargs) -> IndSeries:
        """累积力度指数 - 基于艾尔德力度指数改进而来。
        ---
        Args:
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lines=["bull_power", "bear_power"], lib='finta')
    def EBBP(self, **kwargs) -> IndFrame:
        """艾尔德多空力度指标 - 显示当日最高价和最低价相对于13日指数移动平均线（EMA）的位置。
        ---
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:bull_power,bear_power
        """
        ...

    @tobtind(lib='finta')
    def EMV(self, period: int = 14, **kwargs) -> IndSeries:
        """简易波动指标 - 基于成交量的震荡指标，在零线上下波动，用于衡量价格移动的"难易程度"。指标为正时价格上涨较易，为负时价格下跌较易。
        ---
        Args:
            period: 周期，默认14
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def CCI(self, period: int = 20, constant: float = 0.015, **kwargs) -> IndSeries:
        """商品通道指数 - 多功能指标，用于识别新趋势或警示极端情况，衡量当前价格相对于某段时间平均价格的位置。在零线上下震荡，常规范围为+100至-100；+100以上超买，-100以下超卖，此时价格大概率向合理水平回调。
        ---
        Args:
            period: 考虑的周期数，默认20
            constant: 常数（0.015），确保约70%-80%的CCI值落在-100至+100之间
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def COPP(self, adjust: bool = True, **kwargs) -> IndSeries:
        """科派克曲线 - 动量指标，当指标从负值区间转为正值区间时，发出买入信号。
        ---
        Args:
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lines=["nbfraw", "nsfraw"], lib='finta')
    def BASP(self, period: int = 40, adjust: bool = True, **kwargs):
        """买卖压力指标 - 用于识别买入和卖出压力。
        ---
        Args:
            period: 周期，默认40
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:nbfraw,nsfraw
        """
        ...

    @tobtind(lines=["nbf", "nsf"], lib='finta')
    def BASPN(self, period: int = 40, adjust: bool = True, **kwargs):
        """标准化买卖压力指标
        ---
        Args:
            period: 周期，默认40
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:nbf,nsf
        """
        ...

    @tobtind(lib='finta')
    def CMO(self, period: int = 9, factor: int = 100, adjust: bool = True, **kwargs) -> IndSeries:
        """钱德动量震荡指标 - 由技术分析师Tushar Chande发明的动量指标。通过计算近期上涨总和与下跌总和的差值，再除以该周期内价格总波动，结果在+100至-100之间波动，类似RSI和随机振荡器。
        ---
        Args:
            period: 周期，默认9
            factor: 因子，默认100
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lines=["s", "l"], lib='finta')
    def CHANDELIER(self, short_period: int = 22, long_period: int = 22, k: int = 3, **kwargs) -> IndFrame:
        """吊灯止损指标 - 基于平均真实波幅（ATR）设置跟踪止损。旨在让交易者紧跟趋势，在趋势延续时避免过早离场。通常在下跌趋势中位于价格上方，上涨趋势中位于价格下方。
        ---
        Args:
            short_period: 短期周期，默认22
            long_period: 长期周期，默认22
            k: 倍数，默认3
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:s,l
        """
        ...

    @tobtind(lib='finta')
    def QSTICK(self, period: int = 14, **kwargs) -> IndSeries:
        """Qstick指标 - 通过过去N天的开盘价与收盘价平均差值，显示阴线（下跌）或阳线（上涨）的主导地位。
        ---
        Args:
            period: 周期，默认14
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def TMF(self, period: int = 21, **kwargs) -> IndSeries:
        """特维格资金流量指标 - 由Colin Twiggs发明，是对资金流向指标（CMF）的改进。
        ---
        Args:
            period: 周期，默认21
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lines=["wt1", "wt2"], lib='finta')
    def WTO(self, channel_length: int = 10, average_length: int = 21, adjust: bool = True, **kwargs):
        """波浪趋势震荡指标
        ---
        Args:
            channel_length: 通道长度，默认10
            average_length: 平均长度，默认21
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:wt1,wt2
        """
        ...

    @tobtind(lib='finta')
    def FISH(self, period: int = 10, adjust: bool = True, **kwargs) -> IndSeries:
        """费雪变换指标 - 由John Ehlers提出，假设价格分布呈方波特性。
        ---
        Args:
            period: 周期，默认10
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lines=["tenkan_sen", "kijun_sen", "senkou_span_a", "senkou_span_b", "chikou_span"], overlap=True, lib='finta')
    def ICHIMOKU(self, tenkan_period: int = 9, kijun_period: int = 26, senkou_period: int = 52, chikou_period: int = 26, **kwargs) -> IndFrame:
        """ Ichimoku云图（一目均衡表） - 多功能指标，用于定义支撑位和阻力位、识别趋势方向、衡量动量并提供交易信号，意为"一眼看清的平衡图表"。
        ---
        Args:
            tenkan_period: 转换线周期，默认9
            kijun_period: 基准线周期，默认26
            senkou_period: 先行跨度周期，默认52
            chikou_period: 延迟线周期，默认26
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:tenkan_sen,kijun_sen,senkou_span_a,senkou_span_b,chikou_span
        """
        ...

    @tobtind(lines=["upper_band", "lower_band"], lib='finta')
    def APZ(self, period: int = 21, dev_factor: int = 2, MA: IndSeries = None, adjust: bool = True, **kwargs) -> IndFrame:
        """自适应价格带 - 由Lee Leibfarth开发的基于波动率的指标，以带状形式显示在价格图表上。在无趋势、震荡的市场中尤其有用，帮助交易者识别潜在的市场转折点。
        ---
        Args:
            period: 周期，默认21
            dev_factor: 偏差因子，默认2
            MA: 移动平均线序列，默认None
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:upper_band,lower_band
        """
        ...

    @tobtind(lib='finta')
    def SQZMI(self, period: int = 20, MA: IndSeries = None, **kwargs) -> IndSeries:
        """挤压动量指标 - 用于识别市场盘整期。市场通常处于平静盘整或垂直价格发现状态，识别平静期有助于把握潜在的大波动交易机会。当市场进入"挤压"状态时，可通过整体动量预测方向并等待能量释放。SQZMI['SQZ']为布尔值，True表示处于挤压状态，False表示挤压已释放。
        ---
        Args:
            period: 考虑的周期数，默认20
            MA: 自定义移动平均线序列，默认使用SMA
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def VPT(self, **kwargs) -> IndSeries:
        """量价趋势指标 - 利用价格与前一期价格的差值结合成交量计算得出。若价格与VPT出现看涨背离（VPT上行、价格下行），则存在买入机会；若出现看跌背离（VPT下行、价格上行），则存在卖出机会。
        ---
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def FVE(self, period: int = 22, factor: int = 0.3, **kwargs) -> IndSeries:
        """资金流量指标 - 有两项重要创新：一是同时考虑日内和日间价格行为，二是通过引入价格阈值纳入微小价格变化。
        ---
        Args:
            period: 周期，默认22
            factor: 因子，默认0.3
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def VFI(self, period: int = 130, smoothing_factor: int = 3, factor: int = 0.2, vfactor: int = 2.5, adjust: bool = True, **kwargs) -> IndSeries:
        """成交量流量指标 - 基于价格移动方向跟踪成交量，类似能量潮指标（OBV）。
        ---
        Args:
            period: 用于VFI计算的周期，默认130
            smoothing_factor: 短期移动平均的周期，默认3
            factor: VFI计算的固定缩放因子，默认0.2
            vfactor: VFI计算的最大成交量阈值，默认2.5
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def MSD(self, period: int = 21, **kwargs) -> IndSeries:
        """移动标准差 - 统计术语，衡量数据围绕平均值的离散程度，也是波动率的衡量指标。离散程度越大，标准差越高；价格剧烈变化时标准差显著上升，市场稳定时标准差较低。低标准差通常出现在价格大幅上涨前，分析师普遍认为高波动率伴随主要顶部，低波动率伴随主要底部。
        ---
        Args:
            period: 用于MSD计算的周期，默认21
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def STC(self, period_fast: int = 23, period_slow: int = 50, k_period: int = 10, d_period: int = 3, adjust: bool = True, **kwargs) -> IndSeries:
        """沙夫趋势周期指标 - 可视为MACD的双重平滑随机指标。计算步骤：1. 计算快速周期（23）和慢速周期（50）的EMA，两者差值为MACD；2. 计算MACD的10期随机指标（STOCH_K、STOCH_D）；3. 对STOCH_D进行3期平均得到STC。指标下降表明趋势周期下行，价格倾向于稳定或跟随下行；指标上升表明趋势周期上行，价格倾向于稳定或跟随上行。
        ---
        Args:
            period_fast: 快速周期，默认23
            period_slow: 慢速周期，默认50
            k_period: 随机K周期，默认10
            d_period: 随机D周期，默认3
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：close
        Returns:
            IndSeries
        """
        ...

    @tobtind(lib='finta')
    def EVSTC(self, period_fast: int = 12, period_slow: int = 30, k_period: int = 10, d_period: int = 3, adjust: bool = True, **kwargs) -> IndSeries:
        """改进型沙夫趋势周期指标 - 使用EVWMA MACD进行计算的沙夫趋势周期变体。
        ---
        Args:
            period_fast: 快速周期，默认12
            period_slow: 慢速周期，默认30
            k_period: 随机K周期，默认10
            d_period: 随机D周期，默认3
            adjust: 是否调整，默认True
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndSeries
        """
        ...

    @tobtind(lines=["bearish_fractals", "bullish_fractals"], lib='finta')
    def WILLIAMS_FRACTAL(self, period: int = 2, **kwargs) -> IndFrame:
        """威廉姆斯分形指标 - 识别分形结构的指标。
        ---
        Args:
            period: 极值点前后需满足的高低点数量，默认2
        NOTE:
            实例包括列：open,high,low,close,volume
        Returns:
            IndFrame:bearish_fractals,bullish_fractals
        """
        ...

    @tobtind(lines=["open", "high", "low", "close"], lib='finta')
    def VC(self, period: int = 5, **kwargs) -> IndSeries:
        """计算价值图表（Value Chart）指标，用于标准化价格波动分析

        价值图表通过将价格数据与浮动轴和波动率单位进行标准化处理，
        帮助分析价格在相对波动区间内的位置，消除了绝对价格水平的影响。

        参数:
            period: 计算滚动平均值的窗口大小，默认为5
            **kwargs: 传递给_finta_get_data方法的额外参数，用于数据获取

        NOTE:
            实例包括列：open,high,low,close

        返回:
            IndFrame :open,high,low,close
        """
        ...

    @tobtind(lib='finta')
    def WAVEPM(self, period: int = 14, lookback_period: int = 100, **kwargs) -> IndSeries:
        """计算WAVEPM（Wave Pattern Momentum）指标，用于分析价格波动模式的动量

        该指标通过结合移动平均线、标准差和双曲正切函数，
        标准化价格波动并生成动量信号，帮助识别价格趋势强度。

        Args:
            period: 计算移动平均线和标准差的窗口大小，默认为14
            lookback_period: 计算方差的回溯窗口大小，默认为100
            **kwargs: 传递给_finta_get_data方法的额外参数，用于数据获取

        NOTE:
            实例包括列：open,high,low,close

        Returns:
            IndSeries
        """
        ...


class AutoTrader:
    """AutoTrader指标指引"""
    _df: IndSeries | IndFrame

    def __init__(self, data):
        self._df = data

    @tobtind(lines=["uptrend", "downtrend", "trend"], overlap=True, lib="autotrader")
    def supertrend(self, period: int = 10, multiplier: float = 3.0, source: pd.Series = None, **kwargs) -> IndFrame:
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
        """args:swing_df  The IndFrame returned by self.data.find_swings.
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
        indicator_data:IndFrame of indicator data. self.data.detect_divergence
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
    _df: IndSeries | IndFrame

    def __init__(self, data):
        self._df = data

    @tobtind(lib="sf")
    def Binarizer(self, y: Optional[Iterable] = None, threshold: float = 0.0, copy: bool = True, fit_params: dict = {}, **kwargs) -> IndSeries | IndFrame:
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
        ) -> IndSeries | IndFrame:
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
        random_state: Optional[Union[int, np.ndarray]] = None,
        fit_params: dict = {},
        **kwargs
    ) -> IndSeries | IndFrame:
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
    def KernelCenterer(self, y: Optional[Iterable] = None, fit_params: dict = {}, **kwargs) -> IndSeries | IndFrame:
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
    def LabelBinarizer(self, y: Optional[Iterable] = None, neg_label: int = 0, pos_label: int = 1, sparse_output: bool = False, **kwargs) -> Union[IndSeries, IndFrame]:
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
    def LabelEncoder(self, y: Optional[Iterable] = None, **kwargs) -> Union[IndSeries, IndFrame]:
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
    def MultiLabelBinarizer(self, y: Optional[Iterable] = None, classes=Optional[np.ndarray], sparse_output: bool = False, **kwargs) -> Union[IndSeries, IndFrame]:
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
    def MinMaxScaler(self, y: Optional[Iterable] = None, feature_range: tuple[int] = (0, 1), copy: bool = True, clip: bool = False, fit_params: dict = {}, **kwargs) -> Union[IndSeries, IndFrame]:
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
    def MaxAbsScaler(self, y: Optional[Iterable] = None, copy: bool = True, fit_params: dict = {}, **kwargs) -> Union[IndSeries, IndFrame]:
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
        random_state: int | np.ndarray | None = None,
        copy: bool = True,
        fit_params: dict = {},
        **kwargs
    ) -> Union[IndSeries, IndFrame]:
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
    def Normalizer(self, y: Optional[Iterable] = None, norm: Literal['l1', 'l2', 'max'] = "l2", copy: bool = True, fit_params: dict = {}, **kwargs) -> Union[IndSeries, IndFrame]:
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
    ) -> Union[IndSeries, IndFrame]:
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
    ) -> Union[IndSeries, IndFrame]:
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
    def PowerTransformer(self, y: Optional[Iterable] = None, method="yeo-johnson", standardize=True, copy=True, **kwargs) -> Union[IndSeries, IndFrame]:
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
    ) -> Union[IndSeries, IndFrame]:
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
    ) -> Union[IndSeries, IndFrame]:
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
    def StandardScaler(self, y: Optional[Iterable] = None, copy: bool = True, with_mean: bool = True, with_std: bool = True, fit_params: dict = {}, **kwargs) -> Union[IndSeries, IndFrame]:
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
    def add_dummy_feature(self, value: float = 1., **kwargs) -> Union[IndSeries, IndFrame]:
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
                           interaction_only: bool = False, include_bias: bool = True, order: Literal['C', 'F'] = "C", fit_params: dict = {}, **kwargs) -> Union[IndSeries, IndFrame]:
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
    def binarize(self, threshold: float = 0.0, copy: bool = True, **kwargs) -> Union[IndSeries, IndFrame]:
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
    def normalize(self, norm: Literal['l1', 'l2', 'max'] = "l2", axis: int = 1, copy: bool = True, return_norm: bool = False, **kwargs) -> Union[IndSeries, IndFrame]:
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
    def scale(self, axis=0, with_mean: bool = True, with_std: bool = True, copy=True, **kwargs) -> Union[IndSeries, IndFrame]:
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
    ) -> Union[IndSeries, IndFrame]:
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
    def maxabs_scale(self, axis: int = 0, copy: bool = True, **kwargs) -> Union[IndSeries, IndFrame]:
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
    def minmax_scale(self, feature_range: tuple[int, int] = (0, 1), axis: int = 0, copy: bool = True, **kwargs) -> Union[IndSeries, IndFrame]:
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
    def label_binarize(self, classes: np.ndarray, neg_label: int = 0, pos_label: int = 1, sparse_output: bool = False, *kwargs) -> Union[IndSeries, IndFrame]:
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
        random_state: int | np.ndarray | None = None,
        copy: bool = True,
        **kwargs
    ) -> Union[IndSeries, IndFrame]:
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
    def power_transform(self, method: Literal['yeo-johnson', 'box-cox'] = "yeo-johnson", standardize: bool = True, copy: bool = True, **kwargs) -> Union[IndSeries, IndFrame]:
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
    _df: IndSeries | IndFrame

    def __init__(self, data):
        self._df = data

    @tobtind(lines=["spread", "upper_band", "lower_band", "signals"], lib="pair")
    def bollinger_bands(self, window=60, num_std=2., **kwargs) -> IndFrame:
        """使用布林带生成交易信号"""
        ...

    @tobtind(lines=["pct_deviation", "signals"], lib="pair")
    def percentage_deviation(self, window=60, threshold=0.1, **kwargs) -> IndFrame:
        """使用百分比偏差生成交易信号"""
        ...

    @tobtind(lines=["spread", "upper_threshold", "lower_threshold", "signals"], lib="pair")
    def rolling_quantile(self, window=60, upper_quantile=0.95, lower_quantile=0.05, **kwargs) -> IndFrame:
        """使用移动窗口分位数生成交易信号"""
        ...

    @tobtind(lines=["z_score", "signals"], lib="pair")
    def z_score(self, window=60, z_threshold=2.0, **kwargs) -> IndFrame:
        """使用Z-score生成交易信号"""
        ...

    @tobtind(lines=["z_score", "signals"], lib="pair")
    def hurst_filter(self, hurst_threshold=0.5, z_threshold=2.0, **kwargs) -> IndFrame:
        """使用Hurst指数过滤交易信号"""
        ...

    @tobtind(lines=["dynamic_spread", "hedge_ratios", "z_score", "signals"], lib="pair")
    def kalman_filter(self, y_IndSeries=None, z_threshold=2., **kwargs) -> IndFrame:
        """使用卡尔曼滤波生成动态价差和交易信号"""
        ...

    @tobtind(lines=["volatility", "garch_z_score", "signals"], lib="pair")
    def garch_volatility_adjusted(self, z_threshold=2.0, **kwargs) -> IndFrame:
        """使用GARCH模型调整波动率"""
        ...

    @tobtind(lines=["ect", "signals"], lib="pair")
    def vecm_based(self, y_IndSeries=None, window=60, lag=2, **kwargs) -> IndFrame:
        """VECM模型"""
        ...


class Factors:
    _df: IndSeries | IndFrame

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
    _df: IndSeries | IndFrame

    def __init__(self, data):
        self._df = data

    @property
    def indicators(self) -> CoreFunc:
        return self._df.ta


class IndFrame(IndicatorsBase, PandasDataFrame, PandasTa, TaLib):
    """
        # 框架内置指标数据容器类（IndFrame 类型）
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
        - IndSeries: 转换为框架内置 `SeriesType`（单列指标容器）
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
        1. assign(**kwargs): 扩展列并返回新的 `IndFrame` 实例，支持保留原数据（`keep=True`）
        2. to_lines(*args): 将指定列（整数索引或列名）转换为 `Line` 序列，返回元组
        3. to_ndarray(): 将所有列转换为 numpy 数组，返回元组


        使用示例：
        >>> # 1. 从 DataFrame 初始化指标 IndFrame
        >>> raw_df = pd.DataFrame({"close": [100, 101, 102, 103], "ma5": [99, 100, 101, 102]})
        >>> ind_df = IndFrame(raw_df, category="overlap", isplot=True)
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
        ind_name = kwargs.pop("ind_name", sname)
        candlestyle = iscandles and CandleStyle() or None
        is_mir = kwargs.pop('_is_mir', False)
        ismain = bool(kwargs.pop('ismain', False))
        isreplay = bool(kwargs.pop('isreplay', False))
        isresample = bool(kwargs.pop('isresample', False))
        isindicator = bool(kwargs.pop('isindicator', True))
        iscustom = bool(kwargs.pop('iscustom', False))
        height = kwargs.pop("height", iscandles and 300 or 150)
        linestyle = kwargs.pop("linestyle", {})
        # signalstyle = kwargs.pop("signalstyle", AutoNameDict())
        signalstyle = kwargs.pop("signalstyle", Addict())
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
        # 将IndFrame每列设置为Line
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
                self, self[lines[i]].values, iscustom=iscustom, id=btid.copy(), sname=lines[i],
                    ind_name=ind_name, lines=[
                        lines[i],], category=Category.Any,
                    isplot=self._plotinfo.isplot[lines[i]
                                                 ], ismain=ismain, isreplay=isreplay,
                    isresample=isresample, overlap=self._plotinfo.overlap[lines[i]]))
        # 邦定property函数,IndFrame每列返回的是Line指标数据
        [set_property(self.__class__, attr) for attr in lines]

        self._dataset = DataFrameSet(
            self.copy(), source_object=kwargs.pop("source", None))
        if self._indsetting.iscustom:
            self._dataset.custom_object = self.values
        self.cache = Cache(maxsize=np.inf)

    @property
    def IndSeries(self) -> SeriesType:
        return SeriesType(self)

    # def assign(self, keep=True, **kwargs) -> IndFrame:
    #     """Assign new columns to a DataFrame.

    #     Returns a new object with all original columns in addition to new ones.
    #     Existing columns that are re-assigned will be overwritten.

    #     Parameters
    #     ----------
    #     keep : bool,default True.

    #     **kwargs : dict of {str: callable or Series}
    #         The column names are keywords. If the values are
    #         callable, they are computed on the DataFrame and
    #         assigned to the new columns. The callable must not
    #         change input DataFrame (though pandas doesn't check it).
    #         If the values are not callable, (e.g. a Series, scalar, or array),
    #         they are simply assigned.

    #     Returns
    #     -------
    #     DataFrame
    #         A new DataFrame with the new columns in addition to
    #         all the existing columns.
    #     """
    #     kwargs.update(dict(keep=keep))
    #     return IndFrame(_assign(self.pandas_object, **kwargs))

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
    def short_signal(self) -> Line | None:
        """### 空头交易信号"""
        return getattr(self, "_short_signal")

    @short_signal.setter
    def short_signal(self, value) -> None:
        if isinstance(value, Iterable) and len(value) == self.V:
            self.__set_signal_line("short_signal", value)

    @property
    def exitshort_signal(self) -> Line | None:
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
    def signal_label(self) -> SignalAttrType:
        return SignalAttrType(self, "label")

    @signal_label.setter
    def signal_label(self, value):
        self._plotinfo.signal_label = value

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

    def to_lines(self, *args: Union[int, str]) -> tuple[Union[IndSeries, Line]]:
        """## 返回多列IndSeries"""
        if not args:
            args = self._indsetting.line_filed
        else:
            assert all([isinstance(arg, (int, str))
                        for arg in args]), f"参数为整数或字符串并在{self._indsetting.line_filed}中"
        return (getattr(self, arg if isinstance(arg, str) else self._indsetting.line_filed) for arg in args)

    def to_ndarray(self) -> tuple[np.ndarray]:
        """返回多列np.ndarray"""
        return (line.values for line in self.to_lines())


class KLine(IndFrame):
    """### 框架内置K线数据核心类（继承 IndFrame 类）
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
        - 继承 `IndFrame` 的绘图配置能力，自动适配蜡烛图样式（涨跌颜色 `bull_color`/`bear_color`）
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
                    - isindicator (bool): 是否标记为指标（固定为 False，因 KLine 是K线数据而非指标）


        核心属性说明：
        1. 基础K线数据（自动从输入数据封装为 `IndSeries` 类型）：
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
        - stop_lines: 止损止盈线数据（`IndFrame` 类型，含 stop_price/target_price 列）
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
        >>> self.data = self.get_kline(LocalDatas.test)

        >>> #2. 配置手续费与保证金
        >>> kline.fixed_commission = 1.5  # 每手固定手续费1.5元
        >>> kline.margin_rate = 0.08      # 保证金率8%

        >>> #3. 绑定止损器（假设Stop为自定义停止器类）
        >>> self.data.buy(stop=BBtStop.TimeSegmentationTracking)

        >>> # 4. 实盘模式：通过TqApi关联合约（需先初始化TqApi）
        >>> self.data.set_target_size(2)  # 实盘设置目标多仓2手

        >>> # 5. 快速启动回测
        >>> def next(strategy):
        ...     # 简单均线交叉策略：5日线穿10日线开多
        ...     if strategy.ma5.new > strategy.ma10.new and strategy.ma5.prev < strategy.ma10.prev:
        ...         strategy.kline.buy(size=1)
        >>> # 初始化并启动
        >>> bt = kline.run(
        ...     ["ma5", Multiply(PandasTa.sma, dict(length=5))],
        ...     ["ma10", Multiply(PandasTa.sma, dict(length=10))],
        ...     next=next
        ... )

        """
    _kline_setting: KLineSetting

    def __init__(self, data: pd.DataFrame, **kwargs) -> None:
        assert isinstance(data, pd.DataFrame), "参数data数据只能为pd.DataFrame"
        assert set(data.columns).issuperset(
            FILED.ALL), f"data数据列名至少包括{FILED.ALL}"
        # data = ensure_numeric_dataframe(data)
        data.loc[:, FILED.OHLCV] = data.loc[:,
                                            FILED.OHLCV].astype(np.float64).values
        if self._is_live_trading:
            symbol, duration = data.symbol.iloc[0], data.duration.iloc[0]
            if symbol not in self._tqobjs:
                self._tqobjs.update({symbol: TqObjs(symbol)})
            tqobj = self._tqobjs[symbol]
            data.add_info(**SymbolInfo(
                symbol, int(duration), tqobj.Quote.price_tick, tqobj.Quote.volume_multiple).vars)
        elif not set(data.columns).issuperset(FILED.Quote):
            data.add_info(**default_symbol_info(data))
        data = data[FILED.Quote]
        * _, symbol, cycle, price_tick, volume_multiple = data.loc[0]
        kwargs.update(dict(isindicator=False))
        super().__init__(data[FILED.ALL], **kwargs)
        symbol_info = SymbolInfo(
            symbol, cycle, price_tick, volume_multiple)
        isstop: bool = False
        stop: Stop = None
        stop_lines = None
        current_close = self.pandas_object.close.values
        current_datetime = self.pandas_object.datetime.dt.strftime(
            "%Y-%m-%d %H:%M:%S").values
        tradable: bool = True
        istrader: bool = False
        follow: bool = kwargs.pop("follow", True)
        plot_index: Optional[list[int]] = kwargs.pop("plot_index", None)
        self._klinesetting = KLineSetting(
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

        self._dataset = DataFrameSet(data[FILED.ALL], kline_object=kwargs.pop("kline_object", None), source_object=kwargs.pop(
            "source_object", self), conversion_object=kwargs.pop("conversion_object", None), custom_object=kwargs.pop("custom_object", None), tq_object=kwargs.pop("tq_object", None))
        self._plotinfo.set_default_candles(current_close[-1], self.height)
        kw = {"index": kwargs.pop("index")} if "index" in kwargs else {}
        if self._dataset.kline_object is not None:
            kw = dict(index=self.id.data_id)
        if not self._is_live_trading and self._strategy_instances:
            self._broker = Broker(self, **kw)
        if not self._strategy_instances:
            self._plotinfo.sname = "KLine"
            self._plotinfo.ind_name = "KLine"

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

    # @property
    # def order(self) -> Order:
    #     orders = self._broker.order_datas.queue
    #     if self._strategy_replay:
    #         return orders[self.btindex]
    #     return orders[-1]

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
        return self._klinesetting.follow

    @follow.setter
    def follow(self, value: bool):
        self._klinesetting.follow = bool(value)

    @property
    def current_close(self) -> Optional[float]:
        """### 当前收盘价"""
        if self.btindex < self.length:
            return self._klinesetting.current_close[self.btindex]

    @property
    def current_datetime(self) -> Optional[str]:
        """### 当前日期"""
        if self.btindex < self.length:
            return self._klinesetting.current_datetime[self.btindex]

    @property
    def symbol_info(self) -> SymbolInfo:
        """### 合约信息"""
        return self._klinesetting.symbol_info

    @property
    def symbol(self) -> str:
        """### 合约名称"""
        return self._klinesetting.symbol_info.symbol

    @property
    def cycle(self) -> int:
        """### 合约周期"""
        return self._klinesetting.symbol_info.cycle

    @property
    def price_tick(self) -> float:
        """### 合约最小变动单位"""
        return self._klinesetting.symbol_info.price_tick

    @price_tick.setter
    def price_tick(self, value: float):
        """### 合约最小变动单位"""
        if isinstance(value, (float, int)) and value > 0.:
            self._klinesetting.symbol_info.price_tick = float(value)
            self._broker.price_tick = float(value)

    @property
    def volume_multiple(self) -> float:
        """### 合约剩数,即合约最小波动单位的价值"""
        return self._klinesetting.symbol_info.volume_multiple

    @volume_multiple.setter
    def volume_multiple(self, value: float):
        """### 合约剩数,即合约最小波动单位的价值"""
        if isinstance(value, (float, int)) and value > 0.:
            self._klinesetting.symbol_info.volume_multiple = float(value)
            self._broker.volume_multiple = float(value)

    @property
    def kline(self) -> pd.DataFrame:
        """### 原始K线数据"""
        return self._dataset.kline_object

    @property
    def quote(self) -> Quotes | Quote:
        if self.islivetrading:
            return self._tqobjs[self.symbol].Quote
        else:
            return Quotes(self.datetime.new, self.open.new, self.high.new, self.low.new, self.close.new, self.volume.new, self.price_tick, self.volume_multiple, self.volume_multiple)

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

    def _set_stop(self, stop: Stop, **kwargs) -> KLine:
        """### 设置停止器

        Args:
            stop (Stop, optional): 停止器. Defaults to None.

        Kwargs:
            stop_plot (bool, optional): 停止线是否画图. Defaults to True.
            stop_mode (StopMode, optional): 停止模式. Defaults to None.
            data_length (int):引用数据的长度. Defaults to 300.

        Returns:
            KLine
        """
        if isinstance(stop, ProcessedAttribute):
            stop = stop()
        if stop and (issubclass(stop.func, Stop) if isinstance(stop, partial) else issubclass(stop, Stop)):
            self._klinesetting.isstop = True
            self._klinesetting.set_default_stop_lines(self.id)
            self._klinesetting.stop = stop()(self, **kwargs)
        return self

    @property
    def _stop_mode(self) -> StopMode | None:
        return self._klinesetting.stop.mode if self._klinesetting.stop else None

    @property
    def stop(self) -> Stop | None:
        """停止器"""
        return self._klinesetting.stop

    @property
    def stop_lines(self) -> IndFrame:
        """停止线数据"""
        return self._klinesetting.stop_lines

    @property
    def stop_price(self) -> IndSeries:
        """停止价"""
        return self._klinesetting.stop_lines.stop_price

    @property
    def target_price(self) -> IndSeries:
        return self._klinesetting.stop_lines.target_price

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
    def margin(self) -> float:
        """### 保证金"""
        if self._is_live_trading:
            return self.quote.margin
        else:
            return self._broker._getmargin(self.current_close)

    @property
    def step_margin(self) -> list[float] | float:
        """### 逐笔保证金"""
        if self._is_live_trading:
            self.position.margin
        else:
            return self._broker._step_margin

    @property
    def position_margin(self) -> float:
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

    def resample(self, cycle: int, data_length: int = None, rule: str = None, **kwargs) -> KLine:
        """### 周期转换
        ------

        Args:
        ------
            #实盘中不生效
            >>> cycle (int): 转换周期,不能低于主周期.
                rule (str, optional): 日周期以上需要自行设置,D,W,M. Defaults to None.

        Returns:
        ------
            >>> KLine
        """
        if self._is_live_trading:
            data_length = data_length if data_length and data_length > 0 else 200
            return self.strategy_instance.get_kline(self.symbol, int(cycle), data_length, **kwargs)
        else:
            return self.strategy_instance.resample(int(cycle), self, rule, **kwargs)

    def replay(self, cycle: int, data_length: int = None, rule: str = None, **kwargs) -> KLine:
        """### 周期转换
        ------

        Args:
        ------
            #实盘中不生效
            >>> cycle (int): 转换周期,不能低于主周期.
                rule (str, optional): 日周期以上需要自行设置,D,W,M. Defaults to None.

        Returns:
        ------
            >>> KLine
        """
        if self._is_live_trading:
            data_length = data_length if data_length and data_length > 0 else 200
            return self.strategy_instance.get_kline(self.symbol, int(cycle), data_length, **kwargs)
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
            source["symbol"] = self.symbol
            source["duration"] = self.cycle
            data = KLine(source, **ind_setting)
            data._dataset = self._dataset
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
            source["symbol"] = self.symbol
            source["duration"] = self.cycle
            data = KLine(source, **ind_setting)
            data._dataset = self._dataset
            setattr(self.strategy_instance, self.sname, data)

    def _open_trader(self):
        self._istrader = any(
            [getattr(self, string) is not None for string in SIGNAL_Str])

    @property
    def datetime(self) -> IndSeries:
        """时间序列"""
        return getattr(self, '_datetime')

    @property
    def open(self) -> IndSeries:
        """开盘价序列"""
        return getattr(self, '_open')

    @property
    def high(self) -> IndSeries:
        """最高价序列"""
        return getattr(self, '_high')

    @property
    def low(self) -> IndSeries:
        """最低价序列"""
        return getattr(self, '_low')

    @property
    def close(self) -> IndSeries:
        """收盘价序列"""
        return getattr(self, '_close')

    @property
    def volume(self) -> IndSeries:
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
        >>> bt= KLine(LocalDatas.get_IndFrame(LocalDatas.v2509)).run(
                ["ma1", Multiply(PandasTa.sma, dict(length=20))],
                ["ma2", Multiply(PandasTa.sma, dict(length=30))],
                ["ma3", Multiply(PandasTa.sma, dict(length=60))],
                ["ma4", Multiply(PandasTa.sma, dict(length=120))],
                ["ebsw", Multiply(PandasTa.ebsw)])

        >>> def next(self: Strategy):
                if not self.kline.position:
                    if self.ma1.prev < self.ma4.prev and self.ma1.new > self.ma4.new:
                        self.kline.buy()
                elif self.kline.position > 0:
                    if self.ma1.prev > self.ma4.prev and self.ma1.new < self.ma4.new:
                        self.kline.sell()
            config = Config(islog=False, profit_plot=True)
            bt= KLine(LocalDatas.get_IndFrame(LocalDatas.v2509)).run(
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
                self.data = self.get_kline(df)
                if args:
                    data = self.data.multi_apply(*multiply)
                    for name, ind in zip(names, data):
                        setattr(self, name, ind)
        if iscallnext:
            default_strategy.next = next
        default_strategy.config = config
        if "name" in kwargs:
            default_strategy.__name__ = kwargs.pop("name")

        bt = Bt().addstrategy(default_strategy).run(**kwargs)
        return bt


class IndSeries(IndicatorsBase, PandasSeries, PandasTa, TaLib):
    """### 框架内置指标数据序列类（IndSeries 类型）
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
        - 与框架内置 `IndFrame` 类无缝兼容，可通过 `IndSeries` 属性相互转换


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
        >>> rsi_IndSeries = IndSeries(rsi_data, lines=['rsi'], category='momentum', isplot=True)
        >>>
        >>> # 2. 自定义线型样式
        >>> rsi_IndSeries.line_color = Colors.blue  # 设置为蓝色
        >>> rsi_IndSeries.line_width = 2            # 线宽设为2
        >>> rsi_IndSeries.line_dash = LineDash.dash # 虚线样式
        >>>
        >>> # 3. 从整数长度初始化（自定义数据）
        # 生成100长度的全NaN序列
        >>> ma_IndSeries = IndSeries(100, iscustom=True, lines=['ma20'])
        >>>
        >>> # 4. 调用 pandas_ta 指标（继承自 PandasTa）
        >>> close_IndSeries = IndSeries(close_prices)  # close_prices 为价格序列
        >>> macd_signal = close_IndSeries.macd().signal  # 获取MACD信号线（Line类型）
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
        ind_name = kwargs.pop('ind_name', sname)
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
        signalstyle = kwargs.pop("signalstyle", Addict())  # AutoNameDict())
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
        self._dataset = DataFrameSet(
            self.copy(), source_object=kwargs.pop("source", None))
        if self._indsetting.iscustom:
            self._dataset.custom_object = data
        self.cache = Cache(maxsize=np.inf)

    # def __eq__(self, other):
    #     return super(IndicatorsBase, self).__eq__(other)

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


class Line(IndSeries):
    """### 框架内置单列指标数据类（继承 IndSeries 类）
        核心定位：作为 `IndFrame`/`KLine` 类的「列级数据载体」，封装单列指标的完整能力，同时保持与源数据（父 `IndFrame`/`KLine`）的联动，实现样式配置、绘图状态的双向同步

        核心特性：
        1. 源数据强关联：
        - 初始化时必须绑定父级 `IndFrame` 或 `KLine` 实例（`source` 参数），确保与源数据共享元信息（如指标分类、绘图配置）
        - 样式修改（如颜色、线型）会自动同步到父级源数据，避免父子数据配置不一致
        2. 信号与普通指标双适配：
        - 自动识别是否为交易信号线（通过 `sname` 是否在父级 `signallines` 中判断）
        - 信号线额外支持信号样式配置（标记 `signal_marker`、颜色 `signal_color` 等），普通指标线仅保留基础线型配置
        3. 样式配置双向同步：
        - 线型（`line_style`）、线宽（`line_width`）、颜色（`line_color`）等基础样式修改时，同时更新自身与父级源数据的绘图配置
        - 信号专属样式（`signal_style`/`signal_key` 等）修改时，自动同步父级源数据的信号配置，确保绘图时信号与源数据匹配
        4. 继承与扩展并重：
        - 完全继承 `IndSeries` 类的指标计算能力（如调用 `pandas_ta`/`TaLib` 接口）、数据操作能力（索引、切片等）
        - 新增与父级联动的属性（如 `follow` 继承父级跟随状态、`overlap` 同步父级重叠显示配置），强化列级数据的上下文关联性


        初始化参数说明：
        Args:
            source (IndFrame | KLine): 父级源数据实例，必须为框架内置的多列数据类型（`IndFrame` 或 `KLine`），用于关联元信息与同步配置
            data: 单列指标数据，支持类型与 `IndSeries` 类一致（`pd.Series`/`np.ndarray`/整数，整数表示生成对应长度的全NaN数组）
            **kwargs (IndSetting | dict): 额外配置参数（核心参数继承自 `IndSeries` 类，新增/增强如下）：
                    - sname (str): 指标线名称（必须与父级 `IndFrame`/`KLine` 的列名一致，用于匹配父级配置）
                    - 其他参数（如 `category`/`isplot`/`overlap` 等）若未指定，默认继承自父级源数据


        核心属性说明：
        1. 源数据关联属性：
        - source: 父级源数据实例（`IndFrame` 或 `KLine`），可直接通过该属性访问父级的完整能力（如其他列数据、合约信息等）
        - follow: 继承父级的「主图跟随状态」（仅 `KLine` 等K线类数据有效，默认与父级一致）
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
        >>> # 1. 从 KLine 父级数据创建 Line 实例（假设 kline 为 KLine 实例，含 "close" 列）
        >>> close_line = self.data.close
        >>>
        >>> # 2. 修改线型样式（自动同步到父级 KLine）
        >>> close_line.line_color = Colors.red  # 关闭线设为红色，父级 kline 的 "close" 列颜色同步更新
        >>> close_line.line_width = 2           # 线宽设为2，父级同步更新
        >>>
        >>> # 3. 信号线配置（假设 "long_signal" 是父级的信号列）
        >>> if long_line.issignal:  # 自动识别为信号线
        ...     long_line.signal_marker = Markers.triangle_up  # 信号标记设为上三角
        ...     long_line.signal_color = Colors.green          # 信号颜色设为绿色，父级同步更新
        >>>
        >>> # 4. 控制绘图状态（同步父级）
        >>> long_line.isplot = True  # 开启信号线绘图，父级 kline 的 "long_signal" 列绘图状态同步开启"""

    def __init__(self, source: IndFrame | KLine, data, **kwargs: IndSetting | dict) -> None:
        super().__init__(data, **kwargs)
        self.__source = source  # IndFrame数据
        self._issignal: bool = self.sname in source.signallines
        self._dataset.source_object = source

    @property
    def line_style(self) -> Optional[LineStyle]:
        """### 完整线型配置（LineStyle 实例）
        Get：获取当前列的完整线型配置（包含线宽、颜色、虚实样式等），从自身 _plotinfo.linestyle 中取对应 sname 的配置；

        Set：设置当前列的完整线型配置，参数必须为 LineStyle 实例；
             设置时会先更新自身 _plotinfo.linestyle（用 Addict 包装确保格式一致），再同步更新父级 source 的 _plotinfo.linestyle，
             保证父子数据线型配置完全一致。
        """
        return self._plotinfo.linestyle.get(self.sname)

    @line_style.setter
    def line_style(self, value):
        if isinstance(value, LineStyle):
            self._plotinfo.linestyle = Addict({self.sname: value})
            self.__source._plotinfo.linestyle.update(
                {self.sname: value})

    @property
    def line_dash(self) -> LineDash:
        """### 线型虚实样式（LineDash 枚举值）
        Get：获取当前列的线型虚实样式，从自身 _plotinfo.linestyle 中对应 sname 的 line_dash 字段取值；

        Set：设置当前列的线型虚实样式，参数必须为 LineDash 枚举成员（如 LineDash.solid 实线）；
             设置时先更新自身配置，再同步父级 source 的 _plotinfo.linestyle 中对应 sname 的 line_dash，确保线型统一。
        """
        return self._plotinfo.linestyle[self.sname].line_dash

    @line_dash.setter
    def line_dash(self, value):
        if value in LineDash:
            self._plotinfo.linestyle[self.sname].line_dash = value
            self.__source._plotinfo.linestyle[self.sname].line_dash = value

    @property
    def line_width(self) -> float:
        """### 线条宽度
        Get：获取当前列的线条宽度，从自身 _plotinfo.linestyle 中对应 sname 的 line_width 字段取值；

        Set：设置当前列的线条宽度，参数需为正数（int/float），且会自动转为 float 类型；
             设置时先更新自身配置，再同步父级 source 的 _plotinfo.linestyle 中对应 sname 的 line_width，避免线宽不一致。
        """
        return self._plotinfo.linestyle[self.sname].line_width

    @line_width.setter
    def line_width(self, value):
        if isinstance(value, (float, int)) and value > 0.:
            value = float(value)
            self._plotinfo.linestyle[self.sname].line_width = value
            self.__source._plotinfo.linestyle[self.sname].line_width = value

    @property
    def line_color(self) -> Colors | str:
        """### 线条颜色
        Get：获取当前列的线条颜色，从自身 _plotinfo.linestyle 中对应 sname 的 line_color 字段取值；

        Set：设置当前列的线条颜色，参数支持 Colors 枚举成员（如 Colors.RED）或合法十六进制字符串（如 "#FF0000"）；
             设置时先更新自身配置，再同步父级 source 的 _plotinfo.linestyle 中对应 sname 的 line_color，确保颜色统一。
        """
        return self._plotinfo.linestyle[self.sname].line_color

    @line_color.setter
    def line_color(self, value):
        if value in Colors or (value and isinstance(value, str)):
            self._plotinfo.linestyle[self.sname].line_color = value
            self.__source._plotinfo.linestyle[self.sname].line_color = value

    @property
    def signal_style(self) -> Optional[SignalStyle]:
        """### 信号完整样式配置（仅信号线有效）

        Get：获取当前信号线的完整样式配置（SignalStyle 实例），仅当 _issignal 为 True（是信号线）时有效，否则返回 None；
             从自身 _plotinfo.signalstyle 中对应 sname 的配置取值；

        Set：设置当前信号线的完整样式配置，参数必须为 SignalStyle 实例，且仅当 _issignal 为 True 时生效；
             设置时先更新父级 source 的 _plotinfo.signalstyle 中对应 sname 的配置，再同步自身配置，确保信号样式一致。

        >>> # 可对以下SignalLabel属性进行设置
            class SignalLabel(DataSetBase):
                text: str = ""
                size: int = 10
                style: Literal["normal", "bold"] = "bold"
                color: str = "red"
                islong: bool = True
        """
        if self._issignal:
            return self._plotinfo.signalstyle[self.sname]

    @signal_style.setter
    def signal_style(self, value):
        if self._issignal and isinstance(value, SignalStyle):
            self.__source._plotinfo.signalstyle[self.sname] = value
            self._plotinfo.signalstyle[self.sname] = value

    @property
    def signal_key(self) -> Optional[str]:
        """### 信号锚定的父级列名（仅信号线有效）
        Get：获取当前信号线锚定的父级列名（如 "low" 表示信号标记在父级 low 列价格位置），仅当 _issignal 为 True 时有效；
             从自身 _plotinfo.signalstyle 中对应 sname 的 key 字段取值；

        Set：设置当前信号线锚定的父级列名，参数必须是父级 source.lines 中的有效列名（确保锚定列存在），且仅当 _issignal 为 True 时生效；
             设置时同步更新父级 source 和自身的 _plotinfo.signalstyle 中对应 sname 的 key，确保锚定列一致。
        """
        if self._issignal:
            return self._plotinfo.signalstyle[self.sname].key

    @signal_key.setter
    def signal_key(self, value) -> None:
        if self._issignal:
            if value in self.__source.lines:
                self.__source._plotinfo.signalstyle[self.sname].key = value
                self._plotinfo.signalstyle[self.sname].key = value

    @property
    def signal_color(self) -> Optional[str]:
        """### 信号标记颜色（仅信号线有效）
        Get：获取当前信号线的标记颜色，仅当 _issignal 为 True 时有效；
             从自身 _plotinfo.signalstyle 中对应 sname 的 color 字段取值；

        Set：设置当前信号线的标记颜色，参数必须为 Colors 枚举成员，且仅当 _issignal 为 True 时生效；
             设置时同步更新父级 source 和自身的 _plotinfo.signalstyle 中对应 sname 的 color，确保信号颜色一致。
        """
        if self._issignal:
            return self._plotinfo.signalstyle[self.sname].color

    @signal_color.setter
    def signal_color(self, value) -> None:
        if self._issignal:
            if value in Colors:
                self.__source._plotinfo.signalstyle[self.sname].color = value
                self._plotinfo.signalstyle[self.sname].color = value

    @property
    def signal_marker(self) -> Optional[str]:
        """### 信号标记样式（仅信号线有效）
        Get：获取当前信号线的标记样式（如 "circle" 圆形、"triangle_up" 上三角），仅当 _issignal 为 True 时有效；
             从自身 _plotinfo.signalstyle 中对应 sname 的 marker 字段取值；

        Set：设置当前信号线的标记样式，参数必须为 Markers 枚举成员，且仅当 _issignal 为 True 时生效；
             设置时同步更新父级 source 和自身的 _plotinfo.signalstyle 中对应 sname 的 marker，确保标记样式一致。
        """
        if self._issignal:
            return self._plotinfo.signalstyle[self.sname].marker

    @signal_marker.setter
    def signal_marker(self, value) -> None:
        if self._issignal:
            if value in Markers:
                self.__source._plotinfo.signalstyle[self.sname].marker = value
                self._plotinfo.signalstyle[self.sname].marker = value

    @property
    def signal_show(self) -> Optional[str]:
        """### 信号显示开关（仅信号线有效）
        Get：获取当前信号线的显示状态（True 显示、False 隐藏），仅当 _issignal 为 True 时有效；
             从自身 _plotinfo.signalstyle 中对应 sname 的 show 字段取值；

        Set：设置当前信号线的显示状态，参数会自动转为 bool 类型，且仅当 _issignal 为 True 时生效；
             设置时同步更新父级 source 和自身的 _plotinfo.signalstyle 中对应 sname 的 show，确保显示状态一致。
        """
        if self._issignal:
            return self._plotinfo.signalstyle[self.sname].show

    @signal_show.setter
    def signal_show(self, value) -> None:
        if self._issignal:
            value = bool(value)
            self.__source._plotinfo.signalstyle[self.sname].show = value
            self._plotinfo.signalstyle[self.sname].show = value

    @property
    def signal_size(self) -> Optional[str]:
        """### 信号标记大小（仅信号线有效）
        Get：获取当前信号线的标记大小，仅当 _issignal 为 True 时有效；
             从自身 _plotinfo.signalstyle 中对应 sname 的 size 字段取值；

        Set：设置当前信号线的标记大小，参数需为正数（int/float），且仅当 _issignal 为 True 时生效；
             设置时同步更新父级 source 和自身的 _plotinfo.signalstyle 中对应 sname 的 size，确保标记大小一致。
        """
        if self._issignal:
            return self._plotinfo.signalstyle[self.sname].size

    @signal_size.setter
    def signal_size(self, value) -> None:
        if self._issignal:
            if isinstance(value, (int, float)) and value > 0:
                self.__source._plotinfo.signalstyle[self.sname].size = value
                self._plotinfo.signalstyle[self.sname].size = value

    @property
    def signal_label(self) -> Optional[SignalLabel]:
        """### 信号标签配置（仅信号线有效）
        Get：获取当前信号线的标签配置（SignalLabel 实例，含文字、偏移、字体样式等），仅当 _issignal 为 True 时有效；
             从自身 _plotinfo.signalstyle 中对应 sname 的 label 字段取值；

        Set：设置当前信号线的标签配置，参数必须为 SignalLabel 实例，且仅当 _issignal 为 True 时生效；
             设置时同步更新父级 source 和自身的 _plotinfo.signalstyle 中对应 sname 的 label，确保标签配置一致。
        """
        if self._issignal:
            return self._plotinfo.signalstyle[self.sname].label

    @signal_label.setter
    def signal_label(self, value) -> None:
        if self._issignal:
            source_signalstyle = self.__source._plotinfo.signalstyle[self.sname]
            line_signalstyle = self._plotinfo.signalstyle[self.sname]
            if isinstance(value, SignalLabel):
                source_signalstyle.label = value
                line_signalstyle.label = value
            elif isinstance(value, str) and value:
                if not isinstance(source_signalstyle.label, SignalLabel):
                    source_signalstyle.set_default_label(self.sname)
                if not isinstance(line_signalstyle.label, SignalLabel):
                    line_signalstyle.set_default_label(self.sname)
                source_signalstyle.label.text = value
                line_signalstyle.label.text = value
            elif isinstance(value, bool):
                if value:
                    if not isinstance(source_signalstyle.label, SignalLabel):
                        source_signalstyle.set_default_label(self.sname)
                    if not isinstance(line_signalstyle.label, SignalLabel):
                        line_signalstyle.set_default_label(self.sname)
                else:
                    source_signalstyle.label = False
                    line_signalstyle.label = False

    def set_label(self,
                  text: str = "",
                  size: int = 10,
                  style: Literal["normal", "bold"] = "bold",
                  color: str = "red",
                  islong: bool = True) -> None:
        """### 快捷设置信号标签（仅信号线有效）
        功能：简化信号标签配置流程，直接传入标签参数，自动构建/更新 SignalLabel 实例，并同步父级与自身配置；
             仅当 text 为非空字符串时生效（避免空标签）。

        Args:
            text (str): 标签文字内容（必填，非空才会执行设置）；
            size (int): 标签字体大小（单位：pt，内部自动拼接为 "XXpt" 格式）；
            style (Literal["normal", "bold"]): 标签字体样式（"normal" 正常，"bold" 加粗）；
            color (Colors): 标签字体颜色（支持 Colors 枚举成员或十六进制字符串）。
            islong (bool): 是否为多头信号。

        系统默认设置：
        >>> long_label = dict(size=10, style="bold", color="red", islong=True)
            short_label = dict(size=10, style="bold", color="green", islong=False)
            default_signal_label = {
                "long_signal": SignalLabel("Long Entry", **long_label),    # 多头入场标签
                "short_signal": SignalLabel("Short Entry", **short_label),  # 空头入场标签
                "exitlong_signal": SignalLabel("Exit Long", **short_label),  # 多头离场标签
                "exitshort_signal": SignalLabel("Exit Short", **long_label)  # 空头离场标签
            }
        """
        if self._issignal and isinstance(text, str) and text:
            self.__source._plotinfo.signalstyle[self.sname].set_label(
                text, size, style, color, islong)
            self._plotinfo.signalstyle[self.sname].set_label(
                text, size, style, color, islong)

    @property
    def isplot(self) -> bool:
        """### 绘图开关（与父级非蜡烛图源数据同步）
        Get：获取当前列的绘图状态（True 绘图、False 不绘图），取值自父级 source.isplot 中对应 sname 的状态；

        Set：设置当前列的绘图状态，参数会自动转为 bool 类型；
             仅当父级 source.category != "candles"（非蜡烛图数据）时，才同步更新父级 source.isplot 中对应 sname 的状态，
             同时更新自身 _plotinfo.isplot，确保绘图状态一致。
        """
        return self.__source.isplot[self.sname]

    @isplot.setter
    def isplot(self, value):
        value = bool(value)
        self._plotinfo.isplot = value
        if self.__source.category != 'candles':
            self.__source.isplot[self.sname] = value

    @property
    def source(self) -> IndFrame | KLine:
        """### 父级源数据实例（只读）
        Get：获取当前 Line 实例绑定的父级源数据（IndFrame 或 KLine 实例），用于访问父级其他列、合约信息等元数据；
        说明：此属性为只读，无 setter，初始化时绑定后不可修改。
        """
        return self.__source

    @property
    def overlap(self) -> bool:
        """### 与主图重叠显示开关（与父级非蜡烛图源数据同步）
        Get：获取当前列是否与主图重叠显示（True 重叠、False 单独显示），取值自父级 source.overlap 中对应 sname 的状态；

        Set：设置当前列的重叠显示状态，参数会自动转为 bool 类型；
             仅当父级 source.iscandles 为 False（非蜡烛图数据）时，才同步更新父级 source.overlap 中对应 sname 的状态，
             同时更新自身 _plotinfo.overlap，确保重叠显示配置一致。
        """
        return self.__source.overlap[self.sname]

    @overlap.setter
    def overlap(self, value):
        value = bool(value)
        if not self.__source.iscandles:
            self._plotinfo.overlap = value
            self.__source.overlap[self.sname] = value

    @property
    def follow(self) -> bool:
        """### 主图跟随状态（只读，继承父级）
        Get：获取当前列是否跟随主图显示（True 跟随、False 不跟随），优先继承父级 source.follow 属性（若父级有该属性），
             父级无 follow 属性时默认返回 True；
        说明：此属性为只读，无 setter，状态完全由父级决定。
        """
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
    data: Union[KLine, IndFrame, Line, IndSeries]
    height: int = 150
    lines: Union[list[str], Lines[str]] = Lines()
    overlap: bool = False
    isplot: bool = True
    ismain: bool = False
    category: str | None = None
    isindicator: bool = True
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

    def next(self: KLine) -> Union[IndSeries, IndFrame]:
        return self.close if hasattr(self, "close") else self

    def step(self): ...

    @classmethod
    def _parse_return_variables(cls):
        # 获取next方法的所有源代码行
        func_lines, _ = getsourcelines(cls.next)

        # 预处理：去掉注释和空行
        cleaned_lines = []
        for line in func_lines:
            # 去掉行内注释
            if '#' in line:
                line = line.split('#')[0]
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)

        # 合并续行
        merged_lines = []
        current_line = ''
        for line in cleaned_lines:
            if current_line:
                current_line += ' ' + line
            else:
                current_line = line
            # 检查当前行是否以反斜杠结束
            if current_line.rstrip().endswith('\\'):
                current_line = current_line.rstrip()[:-1].strip()
            else:
                merged_lines.append(current_line)
                current_line = ''

        if current_line:
            merged_lines.append(current_line)

        # 查找最后一条return语句
        return_line = None
        for line in merged_lines:
            if line.startswith('return'):
                return_line = line

        if return_line:
            # 提取return后面的内容
            return_content = return_line.split('return', 1)[1].strip()
            if not return_content:
                return Lines()

            # 再次确保去除注释
            if '#' in return_content:
                return_content = return_content.split('#')[0].strip()

            # 分割变量名（按逗号）
            if "," in return_content:
                lines = tuple([var.strip()
                              for var in return_content.split(",")])
            else:
                lines = (return_content,)

            # 处理属性访问（如obj.var取var）和去除可能的括号
            processed_lines = []
            for ls in lines:
                # 去除可能的括号
                ls = ls.replace("(", "").replace(")", "").strip()
                # 再次确保去除注释
                if '#' in ls:
                    ls = ls.split('#')[0].strip()
                # 取最后一个点号后面的内容
                if "." in ls:
                    processed_lines.append(ls.split(".")[-1])
                else:
                    processed_lines.append(ls)

            return Lines(*processed_lines)
        return Lines()


class BtIndicator(CustomBase, KLine):
    """### 自定义指标创建基类（继承 CustomBase 与 KLine）
        核心定位：提供标准化接口快速构建自定义技术指标，自动集成框架数据结构与绘图系统，支持将用户定义的计算逻辑转换为框架兼容的指标数据（IndSeries/IndFrame）

        核心特性：
        1. 简化指标开发流程：
        - 通过重写 `next` 方法定义指标计算逻辑，无需关注数据格式转换与框架集成细节
        - 自动解析指标输出列名（`lines`），支持手动指定或从 `next` 方法返回值自动提取
        2. 完整的指标配置能力：
        - 继承 `CustomBase` 的绘图配置属性（`overlap` 重叠显示、`isplot` 绘图开关、`category` 指标分类等）
        - 支持自定义线型（`linestyle`）、信号样式（`signalstyle`）、绘图高度（`height`）等可视化参数
        3. 框架无缝集成：
        - 生成的指标自动兼容 `KLine`/`IndFrame` 数据结构，可直接用于策略逻辑或进一步计算
        - 通过 `@tobtind` 装饰器自动处理指标元数据（如指标ID、绘图信息），无需手动维护
        4. 参数化与灵活性：
        - 支持通过 `params` 属性定义指标参数，实现同一指标的多参数版本
        - 支持批量注册自定义方法到 `KLine` 类，扩展基础数据结构的指标计算能力


        初始化参数说明：
        Args:
            data (IndFrame | pd.DataFrame): 输入数据，需为框架内置 `IndFrame` 或 pandas 的 `pd.DataFrame`（含计算所需基础字段如 open/close 等）
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
        >>> next(self: KLine) -> Union[IndSeries, IndFrame, pd.Series, pd.DataFrame, np.ndarray, tuple]:
            - 核心方法，需用户重写，定义指标计算逻辑
            - 参数 `self`：通常为 `KLine` 实例，可直接访问其字段（如 `self.close` 获取收盘价序列）
            - 返回值：支持多种数据类型，框架会自动转换为 `IndSeries`（单列）或 `IndFrame`（多列）
            - 示例：返回 `self.close.rolling(5).mean()` 实现5期均线



        使用示例：
        >>> # 1. 定义简单移动平均线指标
        >>> class MyMA(BtIndicator):
        ...     # 手动指定输出列名（也可省略，框架自动提取）
        ...     lines = ["ma5", "ma10"]
        ...     # 指标参数（可在初始化时通过 kwargs 覆盖）
        ...     params = {"length5": 5, "length10": 10}
        ...
        ...     def next(self):
        ...         # self 为 KLine 实例，可访问收盘价
        ...         ma5 = self.close.rolling(self.params.length5).mean()
        ...         ma10 = self.close.rolling(self.params.length10).mean()
        ...         return ma5, ma10  # 返回多列数据，对应 lines 定义
        ...
        >>> # 2. 使用自定义指标
        >>> # 假设 kline 为 KLine 实例（含 close 字段）
        >>> ma_indicator = MyMA(kline, isplot=True, category="overlap")
        >>> # 3. 访问指标结果（已自动转换为 IndFrame）
        >>> print(ma_indicator.ma5)  # 输出5期均线序列（Line类型）
        >>> print(ma_indicator.ma10) # 输出10期均线序列（Line类型）
        >>> # 4. 指标自动支持绘图，配置已通过类属性和初始化参数设置
    """
    params: Union[Params, dict] = {}

    def __new__(cls, data: IndFrame | pd.DataFrame, **kwargs: IndSetting | dict) -> Union[IndSeries, IndFrame]:
        if "lines" in kwargs:
            cls.lines = Lines(*kwargs["lines"])
        else:
            if not cls.lines:
                cls.lines = cls._parse_return_variables()

        # 确保lines中不包含注释
        if cls.lines:
            # 过滤掉空字符串和只包含注释的项
            clean_lines = []
            for line in cls.lines:
                # 去除注释
                if '#' in line:
                    line = line.split('#')[0].strip()
                # 只保留非空项
                if line:
                    clean_lines.append(line)

            cls.lines = Lines(*clean_lines)

        if cls.lines:
            if isinstance(cls.lines, (list, tuple)):
                cls.lines = Lines(*cls.lines)
            assert cls.lines and isinstance(cls.lines, Lines) and all(
                [isinstance(l, str) for l in cls.lines]), "lines类型为tuple or list,元素为字符串"

        height = kwargs.pop("height", cls.height)
        overlap = kwargs.pop('overlap', cls.overlap)
        isplot = kwargs.pop('isplot', cls.isplot)
        ismain = kwargs.pop('ismain', cls.ismain)
        category = kwargs.pop('category', cls.category)
        multi_index = kwargs.pop("_multi_index", None)
        candlestyle = kwargs.pop("candlestyle", cls.candlestyle)
        linestyle = kwargs.pop("linestyle", cls.linestyle)
        # signalstyle = AutoNameDict(kwargs.pop("signalstyle", cls.signalstyle))
        signalstyle = Addict(kwargs.pop("signalstyle", cls.signalstyle))
        spanstyle = kwargs.pop("spanstyle", cls.spanstyle)
        isindicator = kwargs.pop("isindicator", cls.isindicator)
        cls.params = Addict({**cls.params, **kwargs})
        kline_dict = data.__dict__
        [setattr(data.__class__, k, v) for k, v in cls.__dict__.items()
            if k not in kline_dict and k != "next"]
        # if spanstyle and not isinstance(spanstyle, SpanList) and isinstance(spanstyle, Iterable):
        #     spanstyle = SpanList(spanstyle)

        @tobtind(lines=cls.lines, overlap=overlap, isplot=isplot, ismain=ismain,
                 category=category, myself=cls.__name__, _multi_index=multi_index,
                 linestyle=linestyle, signalstyle=signalstyle, spanstyle=spanstyle, isindicator=isindicator)
        def _next(self):
            return cls.next(self)
            # if data is not None:

            #     if isinstance(data, pd.DataFrame) and (isinstance(cls.lines, Iterable) and len(cls.lines) != data.shape[1]):
            #         lines = tuple(data.columns)
            #         return data, lines
            # return data
        # indicator =
        # if cls._is_method_overridden("step"):
        #     setattr(indicator, "step", cls.step)
        return _next(data)


# class BtSeries(CustomBase, IndSeries):
#     """自定义指标器
#     ---------------

#     Args:
#     -------------
#         >>> data (KLine): KLine数据
#             kwargs (dict):dict(lines=[],overlap=True,isplot=True,ismain=False,category=None,plotinfo=PlotInfo())

#     next函数返回结果:
#     --------------
#         >>> IndSeries | IndFrame | Series | DataFrame | ndarray | tuple[IndSeries,IndFrame,Series,DataFrame,ndarray]

#     Returns:
#     ------------
#         >>> IndSeries | IndFrame
#     """
#     params: dict = {}

#     def __new__(cls, data: IndSeries | pd.Series, **kwargs: IndSetting | dict) -> Union[IndSeries, IndFrame]:
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
        >>> self.kline (KLine) : 合约数据
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

    def __call__(self, kline: KLine,  **kwargs):
        self.kline: KLine = kline
        self.data_length: int = kwargs.pop('data_length', 300)
        self.mode = kwargs.pop('stop_mode', StopMode.Postposition)
        assert self.mode in [
            0, 1, 2], f"停止器模式错误,StopMode:{[k for k,v in vars(StopMode).items() if not k.startswith('_')]}"
        self._price_tick: float = self.kline.price_tick
        self._volume_multiple: float = self.kline.volume_multiple
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
        return self.__get_data(self.kline.btindex)

    def get_data(self, length=None) -> pd.DataFrame:
        self.data_length = length
        return self.data

    @cachedmethod(attrgetter('cache'))
    def __get_data(self, index: int):
        start = max(0, self.kline.btindex+1-self.data_length)
        data = self.kline.pandas_object.iloc[start:self.kline.btindex+1]
        data.reset_index(drop=True, inplace=True)
        return data

    @property
    def trade_price(self) -> float:
        """成交价"""
        return self.kline.open_price

    @property
    def new_close(self) -> float:
        """最新价格"""
        return self.kline.close.new

    @property
    def new_open(self) -> float:
        return self.kline.open.new

    @property
    def new_low(self) -> float:
        return self.kline.low.new

    @property
    def new_high(self) -> float:
        return self.kline.high.new

    @property
    def pre_close(self) -> float:
        """最新价格"""
        return self.kline.close.prev

    @property
    def pre_open(self) -> float:
        return self.kline.open.prev

    @property
    def pre_low(self) -> float:
        return self.kline.low.prev

    @property
    def pre_high(self) -> float:
        return self.kline.high.prev

    @property
    def new_stop_price(self) -> float:
        """设置最新停止价"""
        return self.kline.stop_lines.new[0]

    @new_stop_price.setter
    def new_stop_price(self, value: float) -> None:
        self.__stop_ctrl = False
        self.kline.stop_lines.stop_price.new = value

    @property
    def new_target_price(self) -> float:
        """设置最新目标价"""
        return self.kline.stop_lines.new[1]

    @new_target_price.setter
    def new_target_price(self, value: float) -> None:
        self.__target_ctrl = False
        self.kline.stop_lines.target_price.new = value

    @property
    def pre_stop_price(self) -> float:
        """最后一个停止价"""
        return self.kline.stop_lines.prev[0]

    @property
    def pre_target_price(self) -> float:
        """最后一个目标价"""
        return self.kline.stop_lines.prev[1]

    @property
    def pre_prices(self) -> np.ndarray:
        """最后一个停止价和目标价"""
        return self.kline.stop_lines.prev

    @property
    def new_prices(self) -> np.ndarray:
        """设置最新停止价和目标价"""
        return self.kline.stop_lines.new

    @new_prices.setter
    def new_prices(self, values: list[float]) -> None:
        self.kline.stop_lines.new = values

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
        pos = self.kline.position.pos
        if pos:
            if pos > 0:
                self.long()
                self.__set_price()
                if self.new_close < self.new_stop_price or self.new_close > self.new_target_price:
                    if closing:
                        self.kline.set_target_size()
                    else:
                        trading = True
            else:
                self.short()
                self.__set_price()
                if self.new_close > self.new_stop_price or self.new_close < self.new_target_price:
                    if closing:
                        self.kline.set_target_size()
                    else:
                        trading = True
        return trading


class IndicatorClass(metaclass=Meta):
    PandasTa = PandasTa
    BtInd = BtInd
    TqFunc = TqFunc
    TqTa = TqTa
    TaLib = TaLib
    FinTa = FinTa
    AutoTrader = AutoTrader
    SignalFeatures = SignalFeatures


class BtIndType(metaclass=Meta):
    """内置指标类型"""
    Line = Line
    IndFrame = IndFrame
    IndSeries = IndSeries


class KLineType(metaclass=Meta):
    """KLine类型"""
    KLine = KLine
