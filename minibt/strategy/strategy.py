from __future__ import annotations
from .base import StrategyBase  # , Attrs
# from ..config import Config
from numpy.lib.stride_tricks import as_strided
# from ..cyfunc.utils import _get
# from minibt.cyfunc.utils import _getresults
from ..utils import (reduce, deepcopy, Addict,
                     FILED, time_to_datetime,
                     BtAccount, np, Any,
                     ffillnan, Base, Union, Literal,
                     Log, logging, abc, BtDatasSet,
                     Optional, Cache, IndSetting,
                     timedelta, Counter, Iterable,
                     CandlesCategory, BtIndicatorDataSet,
                     StrategyInstances, Callable,
                     dataclass, field, partial,
                     np_random)
from ..utils import Config as btconfig
from ..indicators import (BtData, Line, series, dataframe,
                          BtIndType, BtDataType)
from ..core import pd


class Strategy(Base, StrategyBase):
    """### Strategy
    量化交易策略核心基类（继承 Base 基础类与 StrategyBase 策略接口类）
    核心定位：统一封装量化交易的回测、实盘、参数优化、强化学习（RL）等全流程能力，提供标准化接口供用户自定义策略逻辑

    主要功能：
    1. 策略生命周期管理：包含初始化、数据准备、回测运行、结果输出、实盘启动等完整流程
    2. 多周期数据处理：支持 K 线周期转换（resample 重采样、replay 数据回放），解决多周期策略的数据对齐问题
    3. 指标与数据管理：自动收录自定义指标（series/dataframe）与 K 线数据（BtData），维护数据一致性
    4. 参数优化：支持策略参数批量优化，自动计算优化目标（如收益率、夏普比率）
    5. 强化学习集成：对接 elegantrl 框架，支持 RL 智能体训练、加载与预测，含数据增强、特征处理能力
    6. 实盘与回测兼容：统一接口适配回测（基于 BtAccount 虚拟账户）与实盘（基于天勤 TQApi 账户）

    使用示例：
    >>> from minibt import *
        class MA(Strategy):
            params = dict(length1=10, length2=20)
            def __init__(self):
                self.data = self.get_data(LocalDatas.test)
                self.ma1 = self.data.close.sma(self.params.length1)
                self.ma2 = self.data.close.sma(self.params.length2)
                self.long_signal = self.ma1.cross_up(self.ma2)
                self.short_signal = self.ma2.cross_down(self.ma1)
            def next(self):
                if not self.data.position:
                    if self.long_signal.new:
                        self.data.buy()
                    elif self.short_signal.new:
                        self.data.sell()
                elif self.data.position > 0 and self.short_signal.new:
                    self.sell()
                elif self.data.position < 0 and self.long_signal.new:
                    self.buy()
        if __name__ == "__main__":
            bt = Bt(auto=True)
            bt.run()
    """

    def __init__(self: Strategy, *args, **kwargs):
        """
        策略实例初始化（实际初始化入口）
        核心作用：将策略实例注册到全局集合，初始化配置（config）与参数（params），处理自定义属性

        Args:
            *args: 额外位置参数（预留，供扩展）
            **kwargs: 额外关键字参数（用于动态设置策略属性，如自定义指标、数据）

        逻辑说明：
        1. 提取策略类名，将实例添加到全局策略实例集合（StrategyInstances）
        2. 初始化策略配置（config）：优先使用类定义的config，无则使用框架默认btconfig
        3. 初始化策略参数（params）：将类定义的params转换为Addict（支持属性式访问）
        4. 处理kwargs：将关键字参数动态设为策略实例属性
        """
        name = self.__class__.__name__
        strategy_instances = self.__class__._strategy_instances  # 全局策略实例集合
        strategy_instances.add_data(name, self)  # 注册当前实例到集合

        # 初始化策略配置：确保config为btconfig类型
        self.config = self.config if isinstance(
            self.config, btconfig) else btconfig()
        # 初始化策略参数：支持属性式访问（如self.params.ma_length）
        self.params = Addict(self.params) if isinstance(
            self.params, dict) else Addict()

        # 动态设置kwargs中的属性（如用户传入的自定义数据、指标）
        for k, v in kwargs.items():
            setattr(self, k, v)

    def _strategy_per_start(self):
        self._pre_init()          # 1. 启动前准备
        self._strategy_init()     # 2. 子类自定义初始化（用户逻辑）
        self._data_init()         # 3. 数据初始化
        self.start()              # 4. 策略启动钩子（用户可重写）

    def _strategy_start(self: Strategy, **kwargs):
        """
        策略回测/实盘启动主流程（核心调度方法）
        核心作用：按顺序执行策略启动前准备、初始化、数据处理、运行、结果整理

        Args:
            **kwargs: 启动参数（如RL训练的额外配置）

        流程说明：
        1. _pre_init(): 启动前准备（创建数据/指标集合、初始化账户）
        2. _strategy_init(): 子类自定义初始化（用户重写的__init__逻辑）
        3. _data_init(): 数据初始化（检查数据、初始化历史记录、处理自定义指标）
        4. start(): 策略启动钩子（用户可重写，用于指标预计算）
        5. RL分支：若启用RL，执行随机策略测试、Agent训练或加载
        6. _bt_run(): 核心回测/实盘运行（循环执行next方法）
        7. _get_plot_datas(): 整理绘图数据（用于后续可视化）
        8. 标记首次启动状态，返回策略实例

        Returns:
            self (Strategy): 策略实例（便于链式调用）
        """
        # print(f"策略{self.__class__.__name__}开始")
        self._strategy_per_start()

        # 5. 强化学习（RL）相关逻辑
        if self.rl:
            if self._rl_config.random_policy_test:  # 随机策略测试（验证环境）
                self.random_policy_test()
                return
            if self._rl_config.train:  # RL Agent训练
                self.train_agent(**kwargs)
            self.load_agent()  # 加载训练好的Agent（笔误：原lond_agent应为load_agent）

        # 6. 执行回测/实盘
        self._bt_run()
        # 7. 整理绘图数据
        self._get_plot_datas()
        # 标记首次启动完成
        self._first_start = True
        return self

    def __call__(self: Strategy, *args, **kwds):
        """
        策略实例调用接口（对外统一入口）
        核心作用：根据策略模式（参数优化、实盘、回测）分发到对应逻辑

        Args:
            *args: 位置参数（优化模式下传入参数组）
            **kwds: 关键字参数（启动配置）

        分支逻辑：
        1. 优化模式（_isoptimize=True）：调用__optimize执行参数优化
        2. 实盘模式（_is_live_trading=True）：调用_live_trading启动实盘
        3. 回测模式：调用_strategy_start启动回测
        """
        if self._isoptimize:
            return self.__optimize(*args)
        elif self._is_live_trading:
            self._live_trading()
        else:
            self._strategy_start(**kwds)
        return self

    def __optimize(self: Strategy, params: dict, ismax: bool, target: Iterable):
        """
        策略参数优化核心方法
        核心作用：针对单个参数组，执行回测并返回优化目标值（如收益率）

        Args:
            params (dict): 单组待优化参数（如 {"ma_length": 5, "rsi_length": 14}）
            ismax (bool): 优化目标是否为最大化（如收益率最大化设为True，风险最小化设为False）
            target (Iterable): 优化目标字段（如 ["total_profit", "sharpe_ratio"]）

        流程说明：
        1. 设置当前参数组到策略
        2. 重置优化状态（_reset_op）
        3. 重置RL环境（若启用RL）
        4. 初始化策略与回测
        5. 调用_get_optimize_results计算并返回优化目标值
        """
        self.params = params
        self._reset_op()  # 重置优化相关状态（如历史记录、仓位）
        if self.rl and self.env:
            self.env.reset()  # 重置RL环境
        self.start()              # 策略启动钩子
        self._strategy_init()     # 重新初始化策略（应用新参数）
        self._bt_run()            # 执行回测
        return self._get_optimize_results(ismax, target)  # 返回优化目标值

    def _pre_init(self):
        """
        策略启动前准备方法（初始化基础组件）
        核心作用：创建数据与指标管理集合，初始化账户（区分实盘/回测）

        逻辑说明：
        1. 创建K线数据集合（_btdatasset）与指标数据集合（_btindicatordataset）
        2. 初始化账户：
           - 实盘/快速实盘模式：从TQApi获取实盘账户（_api.get_account()）
           - 回测模式：创建虚拟账户（BtAccount，初始资金从config获取）
        """
        # 初始化K线数据集合（管理所有关联的BtData实例）
        self._btdatasset = BtDatasSet()
        # 初始化指标数据集合（管理所有关联的series/dataframe实例）
        self._btindicatordataset = BtIndicatorDataSet()

        # 初始化账户（实盘vs回测）
        if self._is_live_trading or self.quick_live:
            self._account = self._api.get_account()  # 实盘：天勤TQ账户
        else:
            # 回测：虚拟账户（初始资金=config.value，日志开关=config.islog）
            self._account: BtAccount = BtAccount(
                self.config.value, self.config.islog, False)

    def _data_init(self):
        """
        策略数据初始化方法（确保数据可用性与一致性）
        核心作用：检查数据完整性、初始化历史记录、处理自定义指标、准备交易相关组件

        逻辑说明：
        1. 快速启动模式处理：若启用quick_start且无数据，预留快速初始化逻辑（注释中）
        2. 数据检查：确保K线数据集合（_btdatasset）非空，否则报错
        3. 历史记录初始化：若设置最小启动长度（min_start_length），初始化账户历史
        4. 自定义指标名称管理：初始化自定义指标名称映射（_custom_ind_name）
        5. 结果容器初始化：创建回测结果列表（_results）
        6. 实盘持仓初始化：记录实盘初始持仓状态（_init_trades）
        7. 停止器检查：判断是否有K线数据绑定了止损止盈器（_isstop）
        8. 数据长度记录：记录K线数据数量（_datas_num）
        9. 数据库关闭：若启用sqlite，关闭数据库连接
        10. 策略逻辑绑定：若重写next方法且非RL模式，将step绑定为next（循环执行）
        """
        # 快速启动模式预留逻辑（用户可根据需求启用）
        if self.quick_start and not self._datas:
            ...
            # def _quick_init(self: Strategy):
            #     for qi, data in enumerate(self._add_datas[self._sid]):
            #         self.get_data(data, qi=qi)
            #     if self.kind:
            #         is_onlyone = len(self._datas) == 1
            #         for bi, btdata_ in enumerate(self._datas):
            #             for bt_name, bt_ind, bt_params in list(zip(self._rl_ind_names, self._rl_ind_list, self._rl_params_list)):
            #                 if not is_onlyone:
            #                     bt_name = f"{bt_name}_{bi}"
            #                 setattr(self, bt_name,
            #                         bt_ind(btdata_, **bt_params))
            # setattr(self.__class__, "_strategy_init", _quick_init)
            # self._strategy_init()

        # 检查数据：必须先添加K线数据
        assert self._btdatasset, '请添加K线数据（通过adddata方法）'

        # 初始化账户历史记录（若设置最小启动长度）
        if self.min_start_length:
            self._account._init_history(self.min_start_length)

        # 初始化自定义指标名称映射（用于后续绘图）
        self._custom_ind_name = {}
        # 初始化回测结果容器
        self._results = []

        # 实盘模式：记录初始持仓状态（多/空/平仓，开仓价）
        if self._is_live_trading:
            pos = self.position.pos
            self._init_trades = [[None,] if not pos else (
                [pos, self.position.open_price_long] if pos > 0 else [
                    pos, self.position.open_price_short]
            )]

        # 检查是否有K线数据绑定了止损止盈器（_isstop：是否启用停止器）
        _isstop_ls = [
            True if data.stop else False for data in self._btdatasset.values()]
        self._isstop = any(_isstop_ls)

        # 记录K线数据数量
        self._datas_num = self._btdatasset.num

        # 关闭sqlite数据库连接（若启用）
        if self._sqlite:
            self._sqlite.close()

        # 绑定策略逻辑：若重写next方法且非RL模式，将step设为next（回测循环执行）
        if self._is_method_overridden("next") and (not self.rl):
            self.step = self.next

    def _custom(self) -> None:
        """
        自定义指标绘图数据处理方法
        核心作用：更新自定义指标的绘图配置（如数据填充、重叠显示），确保与主图/K线数据对齐

        逻辑说明：
        1. 遍历自定义指标名称映射（_custom_ind_name），获取指标数据（series/dataframe）
        2. 处理指标周期转换：若指标为大周期（isresample=True），调用_multi_indicator_resample转换为主周期
        3. 处理重叠显示配置：若overlap为字典（按列配置），拆分显示/隐藏的指标列索引
        4. 更新绘图数据：将处理后的指标数据更新到_plot_datas（绘图数据源）
        """
        if self._custom_ind_name:
            for k, index in self._custom_ind_name.items():
                # 获取自定义指标数据（series或dataframe）
                v: Union[dataframe, series] = getattr(self, k)
                _id = v.id  # 指标ID（用于绘图数据定位）
                is_dataframe = len(v.shape) > 1  # 判断是否为多列指标（dataframe）

                # 提取指标数据（处理dataframe/series的维度差异）
                value = v._custom_data if is_dataframe else v._custom_data.reshape(
                    (len(v), 1))

                # 大周期指标转换：将大周期指标数据转换为主周期长度
                if v.isresample:
                    _value = self._multi_indicator_resample(v)
                    # 重新创建指标实例（确保格式正确）
                    setattr(
                        self, k,
                        dataframe(
                            _value, **v.ind_setting) if is_dataframe else series(_value[:, 0], **v.ind_setting)
                    )
                    # 主图显示大周期指标：更新数据与ID
                    if v._ismain and not self.tq:
                        value = _value
                        _id = v.isresample - 1

                # 处理重叠显示配置（overlap：是否与主图重叠）
                overlap = v._overlap
                overlap_isbool = isinstance(overlap, bool)
                # 获取当前指标的绘图数据
                datas = list(self._plot_datas[2][_id][index])

                # 按列配置重叠显示：拆分显示（True）与隐藏（False）的列索引
                if not overlap_isbool and len(set(overlap.values())) > 1:
                    values = list(overlap.values())
                    index1 = [ix for ix, vx in enumerate(
                        values) if vx]  # 显示的列索引
                    index2 = [ix for ix, vx in enumerate(
                        values) if not vx]  # 隐藏的列索引
                    datas[7] = [value[:, index] for index in [index1, index2]]
                else:
                    datas[7] = value  # 整体配置：直接赋值数据

                # 更新绘图数据
                self._plot_datas[2][_id][index] = datas

    def _multi_indicator_resample(self, data: Union[series, dataframe]) -> np.ndarray:
        """
        多周期指标周期转换方法
        核心作用：将大周期指标数据（如900秒）转换为主周期长度（如300秒），确保时间对齐与数据完整性

        Args:
            data (Union[series, dataframe]): 待转换的大周期指标数据

        Returns:
            np.ndarray: 转换后主周期长度的指标数据（前向填充NaN）

        流程说明：
        1. 获取指标ID与主周期数据：确定指标对应的主周期K线数据（main_data）
        2. 数据格式统一：将series转换为dataframe，添加datetime列用于时间对齐
        3. 创建主周期时间框架：生成与主周期K线时间一致的空数据框（datas）
        4. 数据合并：通过datetime列合并大周期指标与主周期时间框架，填充NaN
        5. 数据清洗：排序、去重、前向填充NaN，返回处理后的数据
        """
        _id = data.data_id  # 指标对应的主周期数据ID
        rid = data.resample_id  # 指标的原始周期ID
        main_data = self._btdatasset[rid].pandas_object  # 主周期K线数据

        # 若指标长度与主周期一致，无需转换
        if len(data) == len(main_data):
            return

        # 大周期指标对应的原始K线数据
        multi_data = self._btdatasset[_id].pandas_object
        isseries = isinstance(data, series)  # 判断是否为单列指标（series）

        # 数据格式统一：series→dataframe，添加datetime列
        raw_cols = isseries and data.lines or list(data.columns)
        data = pd.DataFrame(
            data.values, columns=raw_cols) if isseries else data
        data['datetime'] = multi_data.datetime.values  # 添加大周期指标的时间列
        data = data[['datetime'] + raw_cols]  # 重新排列列：datetime在前，指标列在后

        # 创建主周期时间框架（空数据，仅含主周期datetime）
        cols = list(data.columns)
        datetime = main_data["datetime"].values
        datas = pd.DataFrame(
            np.full((len(datetime), data.shape[1]), np.nan), columns=cols
        )
        datas['datetime'] = datetime

        # 合并数据：通过datetime对齐大周期指标与主周期时间
        df = pd.merge(datas, data, how='outer', on='datetime')

        # 填充合并后的NaN（优先用主周期数据，无则用大周期数据）
        for col in cols[1:]:
            df[col] = df.apply(
                lambda x: x[f'{col}_y'] if pd.isna(
                    x[f'{col}_x']) else x[f'{col}_x'],
                axis=1
            )

        # 数据清洗：排序、去重、前向填充
        df = df[cols]
        df.sort_values(by=cols[:2], na_position='first',
                       ignore_index=True, inplace=True)
        df.drop_duplicates('datetime', keep='last',
                           ignore_index=True, inplace=True)

        # 确保数据长度与主周期一致
        if len(datetime) != df.shape[0]:
            df = df[~pd.isna(df.datetime)]
            df.reset_index(drop=True, inplace=True)

        # 前向填充NaN（大周期指标在主周期内的数值延续）
        return df.ffill()[cols[1:]].values

    def __multi_data_resample(self, data: BtData, if_replay: bool = False) -> pd.DataFrame:
        """
        多周期K线数据转换方法
        核心作用：将大周期K线数据转换为主周期长度，用于多周期策略的回测/绘图

        Args:
            data (BtData): 待转换的大周期K线数据
            if_replay (bool, optional): 是否用于数据回放（True时不做前向填充）. Defaults to False.

        Returns:
            pd.DataFrame: 转换后主周期长度的K线数据（含合约信息）

        流程说明：
        1. 数据复制与时间列处理：复制原始数据，添加datetime_列用于后续处理
        2. 创建主周期时间框架：生成与主周期K线时间一致的空数据框（datas）
        3. 数据合并：通过datetime对齐大周期K线与主周期时间，填充NaN
        4. 数据清洗：排序、去重、前向填充（回放模式不填充）
        5. 补充合约信息：添加symbol、cycle等合约字段，返回完整K线数据
        """
        id = data.isresample  # 主周期ID
        data_ = data.copy()   # 复制原始K线数据
        data_['datetime_'] = data_.datetime.values  # 备份原始时间列
        cols = list(data_.columns)

        # 创建主周期时间框架（空数据，仅含主周期datetime）
        datetime = self._klines[id-1]["datetime"].values
        datas = pd.DataFrame(
            np.full((len(datetime), data_.shape[1]), np.nan), columns=cols
        )
        datas.datetime = datetime

        # 合并数据：通过datetime对齐大周期K线与主周期时间
        df = pd.merge(datas, data_, how='outer', on='datetime')

        # 填充合并后的NaN（优先用主周期数据，无则用大周期数据）
        for col in cols[1:]:
            df[col] = df.apply(
                lambda x: x[f'{col}_y'] if pd.isna(
                    x[f'{col}_x']) else x[f'{col}_x'],
                axis=1
            )

        # 数据清洗：排序、去重
        df = df[cols]
        df.sort_values(by=['datetime', 'open'],
                       na_position='first', ignore_index=True, inplace=True)
        df.drop_duplicates('datetime', keep='last',
                           ignore_index=True, inplace=True)

        # 确保数据长度与主周期一致
        if len(datetime) != df.shape[0]:
            df = df[~pd.isna(df.datetime)]
            df.reset_index(drop=True, inplace=True)

        # 数据填充：回放模式不填充（保留NaN），其他模式前向填充
        df = df[cols[:-1]] if if_replay else df[cols[:-1]].ffill()

        # 补充合约信息（确保与原始数据一致）
        df['symbol'] = data.symbol
        df['duration'] = data.cycle
        df['price_tick'] = data.price_tick
        df['volume_multiple'] = data.volume_multiple

        return df

    def __resample(self, cycle1: int, cycle2: int, data: pd.DataFrame, rule: str = "") -> tuple[list[int], pd.DataFrame]:
        """
        周期重采样核心实现（低→高周期）
        核心作用：将低周期K线数据（如300秒）重采样为高周期（如900秒），生成高周期OHLCV数据

        Args:
            cycle1 (int): 原始低周期（秒）
            cycle2 (int): 目标高周期（秒）
            data (pd.DataFrame): 原始低周期K线数据（含FILED.ALL字段）
            rule (str, optional): 时间规则（如'D'=日、'W'=周，用于日以上周期）. Defaults to "".

        Returns:
            tuple[list[int], pd.DataFrame]: 
                - 第一个元素：重采样后数据在原始数据中的索引（plot_index）
                - 第二个元素：重采样后的高周期K线数据

        核心逻辑：
        1. 计算重采样倍数（multi = cycle2 / cycle1）
        2. 时间对齐：找到第一个符合目标周期起点的K线（如900秒周期的0分0秒）
        3. 数据聚合：按倍数分组，聚合生成高周期OHLCV（open=首根开价，high=组内最高价等）
        4. 处理剩余数据：聚合最后一组不足倍数的K线
        """
        multi = int(cycle2 / cycle1)  # 重采样倍数（如300→900秒，multi=3）
        # 计算相邻K线的时间差（秒），用于检测周期异常
        time_diff = data.datetime.diff().apply(lambda x: x.seconds).values
        datetime = data.datetime.values  # 原始时间序列
        start = datetime[0]  # 原始数据起始时间

        # 时间对齐：找到目标周期的第一个起点（如900秒周期的0分0秒）
        i = 0  # 第一个符合条件的K线索引
        if "S" in rule:  # 秒级周期（如"300S"）
            for i, dt in enumerate(datetime[:multi]):
                if pd.Timestamp(dt).second % cycle2 == 0:
                    break
        elif "T" in rule:  # 分钟级周期（如"15T"）
            for i, dt in enumerate(datetime[:multi]):
                _dt = pd.Timestamp(dt)
                if _dt.second == 0 and _dt.minute % (cycle2 / 60) == 0:
                    break
        else:
            ...  # 其他周期（如小时/日）预留逻辑

        # 初始化结果容器
        array = data.values  # 原始K线数据（numpy数组）
        result = []
        plot_index: list[int] = []  # 重采样数据在原始数据中的索引

        # 处理第一个完整分组前的K线（不足multi根）
        if i:
            first_data = array[:i, :]  # 第一个分组前的K线
            # 聚合第一个分组前的K线（生成一根高周期K线）
            result.append([
                start,  # 时间：取起始时间
                first_data[:, 1][0],  # open：首根开价
                first_data[:, 2].max(),  # high：组内最高价
                first_data[:, 3].min(),  # low：组内最低价
                first_data[:, 4][-1],  # close：最后一根收盘价
                first_data[:, 5].sum()  # volume：组内成交量总和
            ])
            # 更新剩余数据与时间差
            array = array[i:, :]
            time_diff = time_diff[i:]
            plot_index.append(0)  # 记录索引

        fr = not bool(i)  # 是否从第一根K线开始重采样
        index = 0  # 当前分组起始索引

        # 按倍数分组，聚合高周期K线
        for j in range(multi, len(array)):
            # 分组条件：达到倍数或时间差异常（非原始周期）
            if j % multi == 0 or time_diff[j] != cycle1:
                length = j - index  # 当前分组长度
                index = j  # 更新下一分组起始索引
                values = array[j - length:j]  # 当前分组数据

                # 聚合分组数据
                if fr:
                    result.append([
                        values[:, 0][0],  # 时间：首根时间
                        values[:, 1][0],  # open：首根开价
                        values[:, 2].max(),  # high：组内最高价
                        values[:, 3].min(),  # low：组内最低价
                        values[:, 4][-1],  # close：最后一根收盘价
                        values[:, 5].sum()   # volume：组内成交量总和
                    ])
                    fr = False
                result.append([
                    values[:, 0][0],
                    values[:, 1][0],
                    values[:, 2].max(),
                    values[:, 3].min(),
                    values[:, 4][-1],
                    values[:, 5].sum()
                ])
                plot_index.append(j)  # 记录索引

        # 处理最后一组不足倍数的K线
        else:
            if index != j:
                values = array[index:]
                result.append([
                    values[:, 0][0],
                    values[:, 1][0],
                    values[:, 2].max(),
                    values[:, 3].min(),
                    values[:, 4][-1],
                    values[:, 5].sum()
                ])
            # 确保索引列表长度与结果一致
            if len(plot_index) != len(result):
                plot_index.append(j)

        # 转换为DataFrame并返回
        return plot_index, pd.DataFrame(result, columns=FILED.ALL)

    def resample(self, cycle: int, data: BtData = None, rule: str = None, **kwargs) -> BtData:
        """
        对外暴露的K线周期转换接口（低→高周期）
        核心作用：提供标准化接口，将指定K线数据转换为目标高周期，返回BtData实例

        Args:
            cycle (int): 目标高周期（秒），必须大于原始周期且为原始周期的倍数
            data (BtData, optional): 待转换的原始K线数据，默认使用主数据. Defaults to None.
            rule (str, optional): 时间规则（如'D'=日、'W'=周，用于日以上周期）. Defaults to None.

        Kwargs:
            online (bool): 是否在线获取多周期数据（True时从TQApi获取，默认True）

        Returns:
            BtData: 转换后的高周期K线数据实例

        关键校验：
        1. 周期必须为整数
        2. 目标周期必须大于原始周期且为原始周期的倍数
        """
        # 优化模式下不执行转换，返回标记
        if self._isoptimize:
            return "BtOptimize"

        # 参数校验：周期必须为整数
        assert isinstance(cycle, int), "周期必须为整数"

        # 确定原始数据：默认使用主数据（_btdatasset.default_btdata）
        data = self._btdatasset.default_btdata if data is None else data
        main_cycle = data.cycle  # 原始主周期（秒）

        # 参数校验：目标周期必须大于原始周期且为倍数
        assert cycle > main_cycle and cycle % main_cycle == 0, '周期不能低于主周期并且为主周期的倍数'

        # 在线获取多周期数据（实盘或需要最新数据时）
        if self._api and kwargs.pop('online', True):
            # 从TQApi获取目标周期K线
            df = self._api.get_kline_serial(
                symbol=data.symbol, duration=cycle, data_length=len(data))
            # 时间格式转换与调整（确保与原始数据时间对齐）
            df.datetime = df.datetime.apply(time_to_datetime)
            timediff = timedelta(seconds=cycle)
            df.datetime = df.datetime.apply(lambda x: x + timediff)

            # 跳空处理（可选，消除非交易时间的价格跳变）
            if self._abc:
                df = abc(df, self._abc)
            else:
                if self._clear_gap:
                    # 计算相邻K线的时间差
                    time_delta = pd.Series(df.datetime.values).diff().bfill()
                    # 正常周期时间差（含10:15-10:30停盘时间）
                    cycle_ls = [timedelta(seconds=cycle),
                                timedelta(seconds=900 + cycle)]
                    # 识别跳空K线索引
                    _gap_index = ~time_delta.isin(cycle_ls)
                    _gap_index = np.argwhere(_gap_index.values).flatten()
                    _gap_index = np.array(
                        list(filter(lambda x: x > 0, _gap_index)))

                    # 消除跳空：调整跳空后的价格
                    if _gap_index.size > 0:
                        _gap_diff = df.open.values[_gap_index] - \
                            df.close.values[_gap_index - 1]
                        for id, ix in enumerate(_gap_index):
                            df.loc[ix:, FILED.OHLC] = df.loc[ix:, FILED.OHLC].apply(
                                lambda x: x - _gap_diff[id])

            # 时间过滤：仅保留原始数据时间范围内的K线
            df = df[df.datetime >= (data.datetime.iloc[0])]
            df.reset_index(drop=True, inplace=True)
            rdata = df  # 重采样后的数据

        # 本地重采样（回测模式，使用原始数据计算）
        else:
            # 选择原始数据（跟随主数据或使用K线原始数据）
            df = data.pandas_object if data.follow else data.kline_object
            # 生成时间规则字符串（如300秒→"300S"，900秒→"15T"）
            cycle_string = rule if (isinstance(rule, str) and rule in ['D', 'W', 'M']) else \
                f"{cycle}S" if cycle < 60 else (
                    f"{int(cycle/60)}T" if cycle < 3600 else f"{int(cycle/3600)}H"
            )
            # 调用核心重采样逻辑
            plot_index, rdata = self.__resample(
                main_cycle, cycle, df[FILED.ALL], cycle_string)

        # 生成新的指标ID（关联主数据ID，标记为高周期数据）
        _id = self._btdatasset.num
        id = data.id.copy(plot_id=_id, data_id=_id, resample_id=data.data_id)

        # 补充合约信息（目标周期的合约参数）
        symbolinfo_dict = data.symbol_info.filt_values(duration=cycle)
        rdata.add_info(**symbolinfo_dict)

        # 配置参数：传递转换数据、绘图索引等
        kwargs.update(
            dict(
                conversion_object=data.source_object if data.follow else data.kline_object,
                plot_index=plot_index
            )
        )

        # 创建并返回高周期BtData实例（标记为isresample=True）
        return BtData(rdata, id=id, isresample=True, name=f"datas{_id}", **kwargs)

    def __rolling_window(self, v: np.ndarray, window: int = 1, if_index=False) -> np.ndarray:
        """
        生成滚动窗口数据的工具方法
        核心作用：将1D/2D数组转换为滚动窗口格式（如窗口大小3，数组长度5→输出3个窗口），用于时序特征提取

        Args:
            v (np.ndarray): 输入数组（1D或2D）
            window (int, optional): 窗口大小，默认1（无滚动）. Defaults to 1.
            if_index (bool, optional): 是否在窗口中包含原始索引. Defaults to False.

        Returns:
            np.ndarray: 滚动窗口数据（shape=(窗口数, window, 特征数)）

        核心逻辑：
        1. 索引处理：若if_index=True，在数组前添加索引列
        2. 滚动窗口计算：使用numpy stride_tricks生成滚动窗口（高效无复制）
        3. 不足窗口长度处理：窗口大小>1时，前window-1个窗口补NaN
        """
        # 若需要包含索引，在数组前添加索引列（shape=(len(v), 1)）
        if if_index:
            v = np.column_stack((np.arange(len(v)), v))

        dim0, dim1 = v.shape  # 输入数组维度（dim0=时间步，dim1=特征数）
        stride0, stride1 = v.strides  # 数组 strides（内存步长）

        # 处理窗口大小>1的情况：前window-1个窗口补NaN
        redata = []
        if window > 1:
            for i in range(window - 1):
                d = v[:i + 1, :]  # 前i+1个元素
                nad = np.full((window - d.shape[0], dim1), np.nan)  # 补NaN
                redata.append(np.vstack((nad, d)))  # 拼接NaN与有效数据

        # 生成滚动窗口（使用stride_tricks，避免数据复制）
        data = as_strided(
            v,
            # 输出shape：(窗口数, 窗口大小, 特征数)
            shape=(dim0 - (window - 1), window, dim1),
            strides=(stride0, stride0, stride1)  # 步长：沿时间轴1步，窗口内1步，特征轴1步
        )

        # 拼接补NaN的窗口与正常窗口，返回最终结果
        return np.vstack((np.array(redata), data)) if window > 1 else data

    def __replay(self, cycle1: int, cycle2: int, data: pd.DataFrame, rule: str = "") -> pd.DataFrame:
        """
        数据回放核心实现（高→低周期）
        核心作用：将高周期K线数据（如900秒）拆分为低周期回放数据（如300秒），模拟实时行情逐步推送

        Args:
            cycle1 (int): 目标低周期（秒）
            cycle2 (int): 原始高周期（秒）
            data (pd.DataFrame): 原始高周期K线数据（含FILED.ALL字段）
            rule (str, optional): 时间规则（如'D'=日、'W'=周）. Defaults to "".

        Returns:
            pd.DataFrame: 回放后的低周期K线数据

        核心逻辑：
        1. 计算回放倍数（multi = cycle2 / cycle1）
        2. 时间对齐：找到第一个符合目标低周期起点的K线
        3. 数据拆分：将每根高周期K线拆分为multi根低周期K线，实时更新OHLCV（如high取累计最高价）
        4. 处理剩余数据：拆分最后一根高周期K线
        """
        multi = int(cycle2 / cycle1)  # 回放倍数（如900→300秒，multi=3）
        # 计算相邻K线的时间差（秒）
        time_diff = data.datetime.diff().apply(lambda x: x.seconds).values
        datetime = data.datetime.values  # 原始时间序列

        # 时间对齐：找到目标低周期的第一个起点
        i = 0
        if "S" in rule:
            for i, dt in enumerate(datetime[:multi]):
                if pd.Timestamp(dt).second % cycle2 == 0:
                    break
        elif "T" in rule:
            for i, dt in enumerate(datetime[:multi]):
                _dt = pd.Timestamp(dt)
                if _dt.second == 0 and _dt.minute % (cycle2 / 60) == 0:
                    break
        else:
            ...

        # 初始化结果容器
        array = data.values  # 原始高周期数据（numpy数组）
        result = []

        # 处理第一个完整分组前的K线（拆分为低周期）
        if i:
            first_data = array[:i, :]  # 第一个分组前的高周期K线
            for ix in range(i):
                # 提取当前低周期K线数据
                dtime, _open, _high, _low, close, _volumn = first_data[ix]
                # 累计更新OHLCV（模拟实时行情）
                if ix:
                    high = max(high, _high)  # 累计最高价
                    low = min(low, _low)      # 累计最低价
                    volumn += _volumn         # 累计成交量
                else:
                    open, high, low, volumn = _open, _high, _low, _volumn
                # 添加到回放结果
                result.append([dtime, open, high, low, close, volumn])
            # 更新剩余数据与时间差
            array = array[i:, :]
            time_diff = time_diff[i:]

        # 拆分高周期K线为低周期回放数据
        for j, row in enumerate(array):
            dtime, _open, _high, _low, close, _volumn = row
            # 分组条件：新的高周期K线或时间差异常
            if j % multi == 0 or time_diff[j] != cycle1:
                # 初始化新分组的OHLCV
                open, high, low, volumn = _open, _high, _low, _volumn
            else:
                # 累计更新当前分组的OHLCV
                high = max(high, _high)
                low = min(low, _low)
                volumn += _volumn
            # 添加到回放结果
            result.append([dtime, open, high, low, close, volumn])

        # 转换为DataFrame并返回
        return pd.DataFrame(result, columns=FILED.ALL)

    def __multi_data_replay(self, data: BtData) -> tuple[list[str], pd.DataFrame]:
        """
        多周期数据回放处理方法
        核心作用：将高周期K线数据回放为低周期，对齐主周期时间，生成回放数据与索引

        Args:
            data (BtData): 待回放的高周期K线数据

        Returns:
            tuple[list[str], pd.DataFrame]: 
                - 第一个元素：回放数据的时间列表（预留，当前未使用）
                - 第二个元素：回放后的低周期K线数据
        """
        # 第一步：转换高周期数据为主周期时间框架（不填充）
        rdata = self.__multi_data_resample(data, True)
        datetime = rdata.datetime.values  # 主周期时间序列
        rdata = rdata[FILED.OHLCV].values  # 提取OHLCV数据

        # 第二步：生成滚动窗口数据（用于逐周期更新回放数据）
        # 主数据滚动窗口（含索引），高周期数据滚动窗口
        rolling_data = zip(
            self.__rolling_window(
                self._datas[data.id[0]][0].values, if_index=True),
            self.__rolling_window(rdata)
        )

        if_first = True  # 是否为第一根K线
        index_multi_cycle = []  # 多周期索引（标记高周期切换）
        _index = 0  # 高周期数据索引

        # 第三步：逐周期更新回放数据
        for d, rd in rolling_data:
            d, rd = d[0], rd[0]  # 取当前周期窗口数据
            i = d[0]  # 当前主周期索引

            # 处理高周期数据NaN（填充逻辑）
            if np.isnan(rd).any():
                if if_first:
                    # 第一根K线：用主数据填充
                    first_d = d[2:]  # 主数据的OHLCV
                    rdata[i, :] = first_d
                    if_first = False
                else:
                    # 非第一根K线：累计更新OHLCV
                    _, lasthigh, lastlow, lastclose, lastvolume = d[2:]
                    pre_open, pre_high, pre_low, _, pre_volume = first_d
                    # 累计计算：开价不变，高低价取累计极值，成交量累加
                    first_d = [
                        pre_open,
                        max(lasthigh, pre_high),
                        min(lastlow, pre_low),
                        lastclose,
                        lastvolume + pre_volume
                    ]
                    rdata[i, :] = first_d
            else:
                # 高周期数据有效：更新索引，标记新的高周期
                _index += 1
                if_first = True
            # 记录多周期索引
            index_multi_cycle.append(_index)

        # 第四步：整理回放数据（添加时间列）
        rdata = pd.DataFrame(rdata, columns=FILED.OHLCV)
        rdata.insert(0, 'datetime', datetime)

        return rdata, index_multi_cycle

    def replay(self, cycle: int, data: BtData = None, rule: str = None, **kwargs) -> BtData:
        """
        对外暴露的数据回放接口（高→低周期）
        核心作用：将高周期K线数据回放为低周期，模拟实时行情，返回BtData实例（实盘模式不生效）

        Args:
            cycle (int): 目标低周期（秒），必须大于原始周期且为原始周期的倍数
            data (BtData, optional): 待回放的高周期K线数据，默认使用主数据. Defaults to None.
            rule (str, optional): 时间规则（如'D'=日、'W'=周）. Defaults to None.

        Returns:
            BtData: 回放后的低周期K线数据实例

        关键校验：
        1. 周期必须为整数
        2. 目标周期必须大于原始周期且为原始周期的倍数
        """
        # 参数校验：周期必须为整数
        assert isinstance(cycle, int), "周期必须为整数"

        # 确定原始数据：默认使用主数据
        data = self._btdatasset.default_btdata if data is None else data
        assert isinstance(data, BtData), "data必须为BtData类型"
        main_cycle = data.cycle  # 原始高周期（秒）

        # 参数校验：目标周期必须大于原始周期且为倍数
        assert cycle > main_cycle and cycle % main_cycle == 0, '周期不能低于主周期并且为主周期的倍数'

        # 选择原始数据（跟随主数据或使用K线原始数据）
        df = data.pandas_object if data.follow else data.kline_object
        # 生成时间规则字符串
        cycle_string = rule if (isinstance(rule, str) and rule in ['D', 'W', 'M']) else \
            f"{cycle}S" if cycle < 60 else (
                f"{int(cycle/60)}T" if cycle < 3600 else f"{int(cycle/3600)}H"
        )

        # 调用核心回放逻辑，生成低周期回放数据
        rdata = self.__replay(main_cycle, cycle, df[FILED.ALL], cycle_string)

        # 生成新的指标ID（关联主数据ID，标记为回放数据）
        _id = self._btdatasset.num
        id = data.id.copy(plot_id=_id, data_id=_id, replay_id=data.data_id)

        # 补充合约信息（目标周期的合约参数）
        symbolinfo_dict = data.symbol_info.filt_values(duration=cycle)
        rdata.add_info(**symbolinfo_dict)

        # 生成重采样数据（用于回放时的时间对齐）
        plot_index, resample_data = self.__resample(
            main_cycle, cycle, df[FILED.ALL], cycle_string)
        resample_data.add_info(**symbolinfo_dict)
        resample_data = resample_data[FILED.Quote]

        # 配置参数：传递转换数据、绘图索引、源数据等
        kwargs.update(
            dict(
                conversion_object=resample_data,
                plot_index=plot_index,
                source_object=data.source_object if data.follow else data.kline_object
            )
        )

        # 创建并返回回放后的BtData实例（标记为isreplay=True）
        return BtData(rdata, id=id, isreplay=True, name=f"datas{_id}", **kwargs)

    def _update_datas(self, length=10) -> tuple:
        """
        实盘模式下更新图表数据的方法
        核心作用：从TQApi获取最新K线与指标数据，处理HA/K线转换，整理为绘图所需格式

        Args:
            length (int, optional): 图表显示的数据长度（默认显示最近10根K线）. Defaults to 10.

        Returns:
            tuple: 
                - 第一个元素：绘图数据源列表（每个元素对应一个K线数据的绘图配置）
                - 第二个元素：持仓状态列表（每个元素含持仓方向与开仓价）
        """
        source = []  # 绘图数据源列表
        _btind_span = []  # 持仓状态列表（用于显示持仓线）

        # 遍历所有K线数据，生成绘图数据
        for i, (_, btdata) in enumerate(self._btdatasset.items()):
            # 获取TQ实盘数据
            tq_data = btdata._dataset.tq_object
            # 获取当前持仓状态
            position = btdata.position
            pos = position.pos
            # 记录持仓方向与开仓价（多头取open_price_long，空头取open_price_short）
            _btind_span.append([
                pos,
                (position.open_price_long if pos >
                 0 else position.open_price_short) if pos else 0.
            ])

            # 处理时间与成交量数据（取最近length根）
            _datetime = tq_data.datetime.apply(
                time_to_datetime).to_list()[-length:]
            _volume = tq_data.volume.to_list()[-length:]

            # 处理HA布林带K线转换（若启用）
            tq_data = self._to_ha(tq_data, btdata.Heikin_Ashi_Candles)
            # 处理线性回归K线转换（若启用）
            tq_data = self._to_ha(tq_data, btdata.Linear_Regression_Candles)

            # 提取OHLC数据（取最近length根）
            low = tq_data.low.to_list()[-length:]
            high = tq_data.high.to_list()[-length:]
            # 整理K线基础绘图数据（含涨跌标记inc）
            data = dict(
                datetime=_datetime,
                open=tq_data.open.to_list()[-length:],
                high=high,
                low=low,
                close=tq_data.close.to_list()[-length:],
                volume=_volume,
                inc=(tq_data.close >= tq_data.open).values.astype(
                    np.uint8).astype(str).tolist()[-length:],
                Low=low,  # 预留字段（用于指标显示）
                High=high  # 预留字段（用于指标显示）
            )

            # 处理指标绘图数据
            ind_record = self._indicator_record[i]  # 指标记录（含显示配置）
            for isplot, ind_name, lines, rlines, doubles, plotinfo in ind_record:
                lineinfo = plotinfo.get('lineinfo', {})  # 线型配置
                # 获取指标数据
                ind = self._btindicatordataset[ind_name].values

                # 处理多指标合并场景（doubles标记）
                if doubles:
                    ind_name = ind_name[0]
                    ind = ind[:, doubles]  # 提取指定列
                    # 整理显示配置与指标列名
                    len_ind = len(lines[1])
                    _isplot = list(
                        reduce(lambda x, y: x + y, isplot))  # 合并显示开关
                    _lines = list(reduce(lambda x, y: x + y, lines))    # 合并列名
                    # 按显示开关添加指标数据
                    for ix in range(len(doubles)):
                        if _isplot[ix]:
                            data.update(
                                {_lines[ix]: ind[:, ix].tolist()[-length:]})
                    # 前向填充NaN（确保数据完整性）
                    ind = ffillnan(ind[:, -len_ind:])
                else:
                    # 处理单指标场景
                    if any(isplot):
                        if len(isplot) == 1:
                            # 单列指标：直接添加数据
                            value = ind.tolist()[-length:]
                            data.update({lines[0]: value})
                            # 处理柱状图指标（line_dash='vbar'）
                            if lineinfo and rlines[0] in lineinfo and lineinfo[rlines[0]].get('line_dash', None) == 'vbar':
                                if "line_color" not in lineinfo[rlines[0]]:
                                    # 添加涨跌标记（用于柱状图颜色区分）
                                    data.update({f"{rlines[0]}_inc": list(
                                        map(lambda x: "1" if x > 0. else "0", value))})
                                # 添加零线（用于柱状图基准）
                                data.update({'zeros': [0.,] * length})
                        else:
                            # 多列指标：按列添加数据
                            for ix, _name in enumerate(lines):
                                if isplot[ix]:
                                    value = ind[:, ix].tolist()[-length:]
                                    data.update({_name: value})
                                    # 处理柱状图指标
                                    if lineinfo and rlines[ix] in lineinfo and lineinfo[rlines[ix]].get('line_dash', None) == 'vbar':
                                        if "line_color" not in lineinfo[rlines[0]]:
                                            data.update({f"{rlines[ix]}_inc": list(
                                                map(lambda x: "1" if x > 0. else "0", value))})
                                        if 'zeros' not in data:
                                            data.update(
                                                {'zeros': [0.,] * length})
                    # 前向填充NaN
                    ind = ffillnan(ind)

                # 计算指标的高低值（用于绘图缩放）
                if len(ind.shape) > 1:
                    max_value, min_value = np.max(ind, axis=1).tolist(
                    )[-length:], np.min(ind, axis=1).tolist()[-length:]
                else:
                    max_value = min_value = ind.tolist()[-length:]
                # 添加指标高低值到绘图数据（用于Y轴自适应）
                data.update({f"{ind_name}_h": max_value,
                            f"{ind_name}_l": min_value})

            # 添加当前K线的绘图数据到列表
            source.append(data)

        return source, _btind_span

    def _get_account_info(self) -> str:
        """
        获取账户信息字符串（用于实盘日志/控制台输出）
        核心作用：整合账户关键财务指标，生成易读的字符串

        Returns:
            str: 账户信息字符串（含权益、可用资金、盈亏、保证金等）
        """
        return " ".join([
            f"账户权益:{self.account.balance:.2f} ",
            f"可用资金:{self.account.available:.2f} ",
            f"浮动盈亏:{self.account.float_profit:.2f} ",
            f"持仓盈亏:{self.account.position_profit:.2f} ",
            f"本交易日内平仓盈亏:{self.account.close_profit:.2f} ",
            f"保证金占用:{self.account.margin:.2f} ",
            f"手续费:{self.account.commission:.2f} ",
            f"风险度:{self.account.risk_ratio:.2f} "
        ])

    def btind_like(self, ds: Union[series, dataframe, tuple[int], int], **kwargs) -> Union[series, dataframe]:
        """
        创建自定义指标的工具方法（初始化全NaN数据）
        核心作用：根据参考数据或维度，生成结构一致的全NaN指标（series/dataframe），供用户后续赋值

        适用场景：
        - 手动计算自定义指标（如动态止损价、自定义信号）
        - 确保自定义指标与参考数据（如K线、其他指标）结构一致

        Args:
            ds (Union[series, dataframe, tuple[int], int]): 参考数据或维度：
                - series/dataframe：生成与参考指标结构（长度、列数）一致的指标
                - tuple[int]：维度元组（如(100, 2)表示100行2列）
                - int：长度（生成1列、指定长度的series）

        Kwargs:
            指标属性配置（如lines=列名、category=指标分类、isplot=是否绘图等，同IndSetting）

        Returns:
            Union[series, dataframe]: 全NaN的自定义指标（series对应1列，dataframe对应多列）

        示例：
        >>> # 1. 参考MA指标生成自定义止损价指标（同长度）
        >>> self.ma5 = self.data.close.ema(5)
        >>> self.stop_price = self.btind_like(self.ma5, name='stop_price', isplot=True)
        >>> # 2. 手动赋值止损价（如MA5*0.98）
        >>> self.stop_price[:] = self.ma5 * 0.98
        >>> 
        >>> # 3. 按维度生成2列、100行的自定义指标
        >>> self.custom_ind = self.btind_like((100, 2), lines=['ind1', 'ind2'], category='momentum')
        """
        # 处理维度输入：tuple[int]（如(100,2)）
        if isinstance(ds, tuple):
            assert all([isinstance(i, int) and i >
                       0 for i in ds]), "数组ds元素必须为正整数"
        # 处理长度输入：int（如100→1列100行）
        elif isinstance(ds, int):
            assert ds > 0, "ds必须为正整数"
            ds = (ds,)
        # 处理参考指标输入：series/dataframe
        else:
            # 继承参考指标的配置（如ID、分类、绘图开关）
            kwargs = {**ds.ind_setting, **kwargs}
            ds = ds.shape  # 提取参考指标的维度（长度/行列数）

        # 初始化默认配置（基于IndSetting）
        default_kwargs = IndSetting(0, 0, 'btind', ['btind',])
        for k, v in default_kwargs.items():
            if k not in kwargs:
                kwargs.update({k: v})

        # 生成1列指标（series）
        if len(ds) == 1:
            # 确保lines参数存在（列名）
            kwargs.update(dict(lines=[kwargs.get('name', 'custom_line'),]))
            return series(ds, **kwargs)
        # 生成多列指标（dataframe）
        else:
            # 校验列名数量与维度一致
            assert len(
                kwargs['lines']) == ds[1], f"维度{ds}与列名{kwargs['lines']}不一致，请设置lines"
            return dataframe(ds, **kwargs)

    def __setattr__(self, name, value: Union[Line, series, dataframe, BtData, Any]):
        """
        重写属性设置方法，用于策略初始化时特殊处理指标和K线数据

        当策略未初始化时，会对特定类型的属性（如指标、K线数据）进行额外处理，
        包括注册到对应的数据集中、设置名称关联等，之后再调用父类的属性设置方法
        """
        # 策略初始化时生效
        if not self._isinit:
            if self._first_start:
                if self._isoptimize or self._is_live_trading:
                    if name in self._btdatasset:
                        return self._btdatasset[name]

            value_type = type(value)
            # 收录内置指标：若值为指标类型且长度匹配，则添加到指标数据集
            if value_type in BtIndType and len(value) in self._btdatasset.lengths:
                value.sname = name  # 设置指标名称
                # 处理上采样关联
                if value._upsample_name:
                    for k, v in self._btindicatordataset.items():
                        if v._dataset.upsample_object is not None:
                            if value.equals(v._dataset.upsample_object):
                                v._upsample_name = name
                                value._upsample_name = v.sname
                self._btindicatordataset.add_data(name, value)
            # 收录K线数据：若值为K线数据类型，则添加到K线数据集
            elif value_type in BtDataType:
                value.sname = name  # 设置K线数据名称
                # 处理多次赋值的情况，保持指标ID一致性
                if name in self._btdatasset:  # 多次赋值
                    self._account.brokers.pop(0)
                    btid = self._btdatasset[name]._indsetting.id.copy()
                    for v in [*value.line, value]:
                        v._indsetting.id = value._indsetting.id.copy(
                            strategy_id=btid.strategy_id,
                            plot_id=btid.plot_id,
                            data_id=btid.data_id,
                        )
                self._btdatasset.add_data(name, value)

        # 调用父类的属性设置方法
        return super().__setattr__(name, value)

    def __getattribute__(self, name) -> dataframe | series | Line | BtData | Any:
        """重写属性获取方法，直接调用父类的属性获取逻辑"""
        return super().__getattribute__(name)

    # ------------------------------
    # 强化学习（RL）相关方法
    # ------------------------------
    def get_signal_features(self) -> Optional[np.ndarray]:
        """
        获取用于强化学习的信号特征

        当启用强化学习（rl=True）时，通过__process_quant_features处理特征，
        返回处理后的特征数组（numpy格式），否则返回None
        """
        if self.rl:
            return self.__process_quant_features()
            # signal_features = np.column_stack(
            #     tuple(ind.values for _, ind in self._btindicatordataset.items()))
            # signal_features = signal_features.astype(np.float32)
            # from sklearn.preprocessing import StandardScaler
            # scaler = StandardScaler()
            # signal_features = pd.DataFrame(
            #     scaler.fit_transform(signal_features))
            # signal_features = signal_features.replace(
            #     [np.inf, -np.inf], np.nan)
            # signal_features.fillna(0., inplace=True)
            # # _nan = ~np.isfinite(signal_features)
            # # if _nan.any():
            # #     signal_features[_nan] = 0.
            # self._signal_features = signal_features.values
            # return self._signal_features

    def set_process_quant_features(
        self,
        # 归一化方法：'standard'/'robust'/'minmax'/'rolling'
        normalize_method: Literal['standard',
                                  'robust', 'minmax', 'rolling'] = "robust",
        rolling_window: int = 60,          # 滚动窗口大小（仅用于'rolling'方法）
        feature_range: tuple = (-1, 1),    # MinMaxScaler的缩放范围
        use_log_transform: bool = True,    # 是否对非负特征做对数变换
        handle_outliers: str = "clip",     # 异常值处理：'clip'（截断）/'mark'（标记）
        pca_n_components: float = 1.0,     # PCA降维（1.0表示保留全部特征）
        target_returns: Optional[np.ndarray] = None  # 目标收益率（用于特征选择）
    ):
        """
        量化交易特征处理函数，整合归一化、异常值处理、特征变换和降维
        存储特征处理的各项参数，后续调用get_signal_features时会使用这些参数处理特征
        参数:
            features: 原始特征数组，形状为(时间步, 特征数)
            normalize_method: 归一化方法：
                - 'standard': 均值为0、标准差为1（对极端值敏感）
                - 'robust': 中位数为0、四分位距为1（抗极端值）
                - 'minmax': 缩放到指定范围（保留相对大小）
                - 'rolling': 滚动窗口内标准化（避免未来数据泄露）
            rolling_window: 滚动窗口大小（仅当normalize_method='rolling'时有效）
            feature_range: MinMaxScaler的缩放范围（仅当normalize_method='minmax'时有效）
            use_log_transform: 是否对非负特征应用对数变换（压缩长尾分布）
            handle_outliers: 异常值处理方式：
                - 'clip': 截断到合理范围（四分位法）
                - 'mark': 新增异常值标记特征（0/1）
            pca_n_components: PCA降维参数（0~1表示保留信息量比例，>1表示保留特征数）
            target_returns: 目标收益率数组（用于过滤低相关特征，可选）

        返回:
            处理后的特征数组，形状为(时间步, 处理后特征数)
        """
        from functools import partial
        self.__process_quant_features = partial(self._process_quant_features,
                                                normalize_method=normalize_method,
                                                rolling_window=rolling_window,
                                                feature_range=feature_range,
                                                use_log_transform=use_log_transform,
                                                handle_outliers=handle_outliers,
                                                pca_n_components=pca_n_components,
                                                target_returns=target_returns)

    def __process_quant_features(
        self,
        # 归一化方法：'standard'/'robust'/'minmax'/'rolling'
        normalize_method: Literal['standard',
                                  'robust', 'minmax', 'rolling'] = "robust",
        rolling_window: int = 60,          # 滚动窗口大小（仅用于'rolling'方法）
        feature_range: tuple = (-1, 1),    # MinMaxScaler的缩放范围
        use_log_transform: bool = True,    # 是否对非负特征做对数变换
        handle_outliers: str = "clip",     # 异常值处理：'clip'（截断）/'mark'（标记）
        pca_n_components: float = 1.0,     # PCA降维（1.0表示保留全部特征）
        target_returns: Optional[np.ndarray] = None  # 目标收益率（用于特征选择）
    ) -> np.ndarray:
        """
        量化特征处理的实际执行方法

        根据是否已通过partial绑定参数，决定直接调用或传入参数调用底层处理函数
        返回处理后的特征数组
        """
        if isinstance(self._process_quant_features, partial):
            return self._process_quant_features()
        return self._process_quant_features(normalize_method, rolling_window, feature_range, use_log_transform, handle_outliers, pca_n_components, target_returns)

    def data_enhancement(self, obs: np.ndarray, rate: float = 0.5) -> np.ndarray:
        """### 随机应用一种数据增强方法（概率由rate控制）

        用于强化学习中的数据增强，防止模型过拟合。首次调用时加载增强函数库，
        之后按概率随机选择一种增强方法对输入特征进行处理

        Args:
            obs (np.ndarray): 输入的特征数据（多维数组）
            rate (float): 应用增强的概率，默认0.5

        Returns:
            np.ndarray: 处理后的一维特征数组（增强后或原数组展平）
        """
        if not self._if_data_enhancement:
            from ..data_enhancement import data_enhancement_funcs
            self._data_enhancement_funcs = data_enhancement_funcs
            self._if_data_enhancement = True
        # 随机应用一种自毁式增强（50%概率）
        if np.random.rand() < rate:
            # 随机选择一种增强方法
            augment_func = np.random.choice(self._data_enhancement_funcs)
            return augment_func(obs)
        return obs.flatten()

    def set_model_params(
            self,
            agent=None,
            train: bool = True,
            continue_train=False,
            random_policy_test: bool = False,
            # if_single_process=True,
            window_size: int = 10,
            env_name: str = "",
            num_envs: int = 1,
            max_step: int = 0,
            state_dim: int = 0,
            action_dim: int = 0,
            if_discrete: bool = True,
            break_step: int = 1e6,
            batch_size: int = 128,  # 128,
            horizon_len: int = 2048,  # 2048,
            buffer_size: int = None,
            repeat_times: float = 8.0,
            if_use_per: bool = False,
            gamma: float = 0.985,
            reward_scale: float = 1.,
            net_dims: tuple[int] = (64, 32),
            learning_rate: float = 6e-5,
            weight_decay: float = 1e-4,
            clip_grad_norm: float = 0.5,
            state_value_tau: float = 0.,
            soft_update_tau: float = 5e-3,
            save_gap: int = 8,
            ratio_clip: float = 0.25,
            lambda_gae_adv: float = 0.95,
            lambda_entropy: float = 0.01,
            eps: float = 1e-5,
            momentum: float = 0.9,
            lr_decay_rate=0.999,
            gpu_id: int = 0,
            num_workers: int = 4,
            num_threads: int = 8,
            random_seed: Optional[int] = 42,
            learner_gpu_ids: tuple[int] = (),
            cwd: Optional[str] = None,
            if_remove: bool = True,
            break_score: float = np.inf,
            if_keep_save: bool = True,
            if_over_write: bool = False,
            if_save_buffer: bool = False,
            eval_times: int = 3,
            eval_per_step: int = 2e4,
            eval_env_class=None,
            eval_env_args=None,
            eval_record_step=0,
            Loss=None,
            Optim=None,
            LrScheduler=None,
            SWA=None,
            Activation=None,
            swa_start_epoch_progress=0.8,
            Norm=None,
            # output_activation: bool = False,
            # add_layer_norm: bool = False,
            dropout_rate: float = 0.0,
            bias: bool = True,
            actor_path: str = "",
            actor_name: str = "",
            file_extension: str = ".pth",
            **params):
        """
        配置强化学习模型的参数，初始化训练配置

        该方法会解析输入参数，设置环境参数（状态维度、动作维度等），
        初始化强化学习配置对象，并返回该配置。支持自定义损失函数、优化器等组件

        Returns:
            Config: 强化学习训练配置对象
        """
        kwargs = locals()
        params = kwargs.pop("params", {})
        agent = kwargs.pop('agent', None)
        from minibt.elegantrl.agents import Agents
        assert agent in Agents, f"agent must be in {Agents}"
        kwargs.pop("self")
        self.window_size = kwargs.pop("window_size", 10)
        kwargs = {**kwargs, **params}
        self.get_signal_features()  # 获取信号特征
        state, _ = self.reset()
        env_name = kwargs.pop('env_name', "")
        num_envs = kwargs.pop('num_envs', 1)
        max_step = kwargs.pop('max_step', 0)
        state_dim = kwargs.pop('state_dim', 0)
        action_dim = kwargs.pop('action_dim', 0)
        if_discrete = kwargs.pop('if_discrete', True)
        # 环境名称默认使用策略类名
        env_name = env_name if isinstance(
            env_name, str) and env_name else f"{self.__class__.__name__}Env"
        num_envs = int(num_envs) if isinstance(
            num_envs, (int, float)) and num_envs >= 1 else 1
        max_step = int(max_step) if isinstance(
            max_step, (int, float)) and max_step >= 1 else self._btdatasset.max_length
        max_step -= 1
        action_dim = int(action_dim) if isinstance(
            action_dim, (float, int)) and action_dim >= 1 else 1
        state_dim = int(state_dim) if isinstance(
            state_dim, (float, int)) and state_dim >= 1 else state.shape[0]
        if_discrete = bool(if_discrete)
        self._env_args = {
            'env_name': env_name,
            'num_envs': num_envs,
            'max_step': max_step,
            'state_dim': state_dim,
            'action_dim': action_dim,
            'if_discrete': if_discrete,
        }
        from minibt.elegantrl.train.config import Config
        import torch as th
        self.th = th
        self._rl_config = Config(agent, self, self._env_args, cwd)
        kwargs.pop("cwd")
        # 将参数设置到配置对象
        for k, v in kwargs.items():
            setattr(self._rl_config, k, v)
        # 缓冲区大小默认使用数据集长度
        if self._rl_config.buffer_size is None:
            self._rl_config.buffer_size = self._btdatasset.max_length
        from ..rl_utils import Optim, Loss, Activation
        # 设置默认损失函数、优化器和激活函数
        if self._rl_config.Loss is None:
            self._rl_config.Loss = Loss.MSELoss(reduction="none")
        if self._rl_config.Optim is None:
            self._rl_config.Optim = Optim.AdamW(eps=1e-5, weight_decay=1e-4,)
        if self._rl_config.Activation is None:
            self._rl_config.Activation = Activation.Tanh10()
        # 继续训练时加载已有模型
        # if continue_train and train:
        #     device = th.device(f"cuda:{gpu_id}" if (
        #         th.cuda.is_available() and (gpu_id >= 0)) else "cpu")
        #     self._rl_config.actor = self._get_actor(device, False)

        return self._rl_config

    def random_policy_test(self):
        """
        随机策略测试，用于验证环境和动作空间的有效性

        该方法通过随机采样动作来与环境交互，输出总奖励、步数和动作分布统计，
        可用于判断环境是否正常工作以及动作空间设置是否合理
        """
        import warnings
        warnings.filterwarnings("ignore", category=UserWarning, module="gym")
        if_discrete = self._env_args.get('if_discrete', True)
        from gym import spaces
        # 根据动作类型（离散/连续）定义动作空间
        if if_discrete:
            action_space = spaces.Discrete(self.action_dim)
        else:
            action_space = spaces.Box(
                low=-1., high=1., shape=(self.action_dim,), dtype=np.float32)

        self.reset()
        rewards = 0.
        actions = []
        # 与环境交互，执行随机动作
        for i in range(self.min_start_length, self.max_step):
            action = action_space.sample()
            if if_discrete:
                actions.append(action)
            else:
                action = np.clip(action, action_space.low, action_space.high)
                actions.append(action.tolist())
            state, reward, terminal, truncated, info_dict = self.step(action)
            done = terminal or truncated
            rewards += reward
            if done:
                print(
                    f"Random Policy Test: Final Reward {rewards:.2f} ,Total Steps {i} ,max_steps {self.max_step}")
                break
        # 输出动作分布统计（连续动作输出均值、标准差等；离散动作输出计数）
        if not if_discrete:
            actions = np.array(actions)
            actions = actions.reshape(-1, self._env_args['action_dim'])
            actions = np.clip(actions, action_space.low, action_space.high)
            actions = pd.DataFrame(
                actions, columns=[f'action_{i}' for i in range(self._env_args['action_dim'])])
            actions.describe().loc[['mean', 'std', 'min', 'max']]
            print(
                f"Random Policy Test: Action Distribution:\n{actions.describe().loc[['mean', 'std', 'min', 'max']]}")
            return
        print(
            f"Random Policy Test: Action Distribution :{pd.Series(actions).value_counts()}")

    def train_agent(self, **kwargs):
        """启动强化学习智能体训练，调用底层训练函数"""
        from minibt.elegantrl.train.run import train_agent
        train_agent(self._rl_config, True)

    def _get_actor(self, map_location=None, weights_only=None):
        """
        加载训练好的智能体模型（actor）

        从指定路径或默认模型目录加载模型文件，初始化actor网络并加载权重，
        用于后续的推理或继续训练

        Args:
            map_location: 模型加载的设备（如cpu、cuda:0）
            weights_only: 是否只加载权重（忽略其他状态）

        Returns:
            加载好权重的actor模型
        """
        import os
        SEED = 42
        self.th.manual_seed(SEED)       # PyTorch随机种子
        np.random.seed(SEED)          # Numpy随机种子
        self.th.backends.cudnn.deterministic = True  # CuDNN确定性模式
        self.th.backends.cudnn.benchmark = False      # 关闭Benchmark加速（避免随机性）
        # 确定模型路径：优先使用指定路径，否则从模型目录查找
        if os.path.exists(self._rl_config.actor_path):
            actor_path = self._rl_config.actor_path
        else:
            cwd = self._rl_config.model_cwd
            assert cwd and isinstance(
                cwd, str), "cwd must be a valid path string"
            assert os.path.exists(cwd), f"cwd does not exist: {cwd}"
            file_extension: str = self._rl_config.file_extension
            if not file_extension.startswith('.'):
                file_extension = '.' + file_extension
            if file_extension not in ['.pth', '.pt']:
                raise ValueError(
                    f"file_extension must be '.pth' or '.pt', got {file_extension}")
            if file_extension == '.pt':
                from minibt.other import get_sorted_pth_files
                actor_path = get_sorted_pth_files(
                    cwd, file_extension)[0]
            else:
                from minibt.other import find_pth_files
                actor_path = find_pth_files(cwd)[0]
        assert os.path.exists(actor_path), f"路径错误：{actor_path}"
        print(f"| render and load actor from: {actor_path}")
        args = self._rl_config
        # 初始化actor网络
        actor = args.agent_class(
            args.net_dims, args.state_dim, args.action_dim, gpu_id=args.gpu_id, args=args).act
        actor.to(map_location)  # 移动到目标设备（如CPU/GPU）
        # # 加载模型权重
        # state_dict = self.th.load(
        #     actor_path, map_location=map_location, weights_only=weights_only)
        # actor.load_state_dict(state_dict)
        try:
            # 尝试加载状态字典
            state_dict = self.th.load(
                actor_path, map_location=map_location, weights_only=weights_only)

            # 检查加载的是否是完整模型而不是状态字典
            if hasattr(state_dict, 'state_dict'):
                # print("检测到完整模型对象，提取其状态字典")
                state_dict = state_dict.state_dict()

            actor.load_state_dict(state_dict)
        except TypeError:
            # 如果直接加载失败，尝试先实例化模型再提取状态字典
            # print("尝试直接加载模型对象并提取状态字典")
            loaded_model = self.th.load(actor_path, map_location=map_location)
            if hasattr(loaded_model, 'state_dict'):
                actor.load_state_dict(loaded_model.state_dict())
            else:
                raise ValueError("无法从加载的文件中获取有效的状态字典")

        self.actor = actor
        return self.actor

    def load_agent(self):
        """加载智能体模型用于推理"""
        self._rl_config.train = False
        self._rl_config.if_remove = False
        self._rl_config.init_before_training()
        self._get_actor(map_location="cpu", weights_only=False)
        self.actor.eval()  # 设置为评估模式
        self.actor = self.actor.float()  # 确保模型参数为float32
        self.device = next(self.actor.parameters()).device
        # 若子类重写了next方法，则将step指向next
        if self._is_method_overridden("next"):
            self.step = self.next
        self._state, _ = self.reset()  # 重置环境状态

    @classmethod
    def _is_method_overridden(cls, method_name):
        """检查当前类是否重写了指定的方法

        Args:
            method_name (str): 方法名称

        Returns:
            bool: 若重写则返回True，否则返回False"""
        import types
        return method_name in cls.__dict__ and isinstance(cls.__dict__[method_name], types.FunctionType)


class default_strategy(Strategy):
    """默认策略类，继承自Strategy"""
    config = btconfig(islog=False, profit_plot=False)

    def __init__(self) -> None:
        ...

    def next(self):
        ...
