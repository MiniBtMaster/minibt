from __future__ import annotations
from ..indicators import (BtData, Base,
                          Addict, pd, Cache, BtDataType,
                          FILED, Iterable, StopMode,
                          TYPE_CHECKING, BtID, BtIndType)
from ..utils import (cache, time_to_str, Union, np, Callable,
                     BASE_DIR, pd, Cache, BtIndicatorDataSet,
                     deepcopy, pandasdataframe, Any, Actions,
                     abc, time_to_datetime, timedelta, Logger,
                     TargetPosTask, BtDatasSet, Log, time,
                     os, StrategyInstances, partial, Literal,
                     Optional, Config, get_cycle, read_unknown_file,
                     format_3col_report, qs_stats)
# from torch import as_tensor, float32, no_grad
from abc import abstractmethod
from .stats import Stats
from .qs_plots import QSPlots
from itertools import repeat

if TYPE_CHECKING:
    from ..indicators import series, dataframe, TqAccount, Line
    from .strategy import Strategy
    from ..utils import logging, TqApi, BtAccount, datetime, BtPosition, Position, TqObjs
    from ..elegantrl.train.config import Config as RlConfig


class StrategyBase:
    """
    量化策略基础抽象类（Strategy的父类）
    核心定位：封装量化策略的通用能力，包括数据获取、回测/实盘调度、交易执行、指标管理、强化学习（RL）集成、结果分析等，
    为子类策略提供标准化接口与底层实现，实现回测与实盘的无缝切换

    核心职责：
    1. 数据管理：支持从TQSDK（期货）、PyTDX（股票）、数据库、外部DataFrame获取K线数据，自动补充必要字段
    2. 交易执行：统一封装买入、卖出、目标仓位设置等交易接口，区分回测（BtAccount）与实盘（TqAccount）逻辑
    3. 回测调度：实现回测循环迭代，处理止损逻辑、账户历史更新，支持RL模式与普通策略模式
    4. 指标与绘图：管理指标数据集合，整理绘图所需数据结构，支持自定义指标的可视化配置
    5. 结果分析：集成QuantStats工具，计算回测指标（夏普比率、最大回撤等）、生成HTML报告、打印关键统计信息
    6. 强化学习：提供RL特征处理、数据增强、智能体加载/训练接口，适配ElegantRL框架

    关键设计：
    - 抽象方法（reset/step/start/stop）：需子类重写实现具体策略逻辑
    - 数据集合（_btdatasset/_btindicatordataset）：统一管理K线与指标数据，确保数据一致性
    - 配置驱动（config）：通过Config对象控制回测/实盘参数（如手续费、滑点、绘图开关）
    - 模式兼容：通过_is_live_trading/_isoptimize标记区分实盘、回测、参数优化模式
    """
    # 策略参数字典（子类通过重写定义策略参数，如ma_length=5）
    params: dict = {}
    # 策略配置对象（控制回测/实盘参数，如手续费、滑点、绘图开关）
    config: Config = Config()
    # 策略ID（用于多策略区分）
    _sid: int = 0
    # 天勤TQApi实例（实盘模式使用）
    _api: TqApi
    # 当前收盘价数组（实时更新）
    _current_close: np.ndarray
    # 当前时间数组（实时更新）
    _current_datetime: np.ndarray
    # 自定义指标名称映射（用于绘图）
    _custom_ind_name: dict
    # K线数据集合（管理所有BtData实例，支持dict或BtDatasSet类型）
    _btdatasset: Union[BtDatasSet[str, BtData], dict[str, BtData]]
    # 指标数据集合（管理所有Line/series/dataframe实例）
    _btindicatordataset: Union[BtIndicatorDataSet[str, BtData],
                               dict[str, Union[Line, series, dataframe]]]
    _tqobjs: dict[str, TqObjs]
    # 账户对象（回测用BtAccount，实盘用TqAccount）
    _account: Union[BtAccount, TqAccount]
    # 是否启用止损（True表示至少一个合约配置了止损）
    _isstop: bool = False
    # 是否处于参数优化模式
    _isoptimize: bool = False
    # 是否处于实盘交易模式
    _is_live_trading: bool
    # 是否首次启动策略
    _first_start: bool = False

    # 是否启用强化学习（RL）模式
    rl: bool = False
    # 初始化标记（内部使用）
    _init_: bool = False
    # PyTDX API实例（股票数据获取用）
    _tdxapi = None
    # 参数优化的目标值（用于记录最优结果）
    _target_train: int = 0.
    # 是否启用快速启动模式（简化初始化流程）
    quick_start: bool = False
    # 是否启用快速实盘模式（简化实盘初始化）
    quick_live: bool = False
    # 回测结果列表（每个元素对应一个Broker的历史数据DataFrame）
    _results: list[pd.DataFrame]  # 回测结果=[]
    # 回测当前索引（迭代K线数据用）
    _btindex: int = -1  # 索引
    # 策略初始化状态（True表示初始化完成）
    _isinit: bool = False  # 策略初始化状态
    # 图表保存名称（默认'plot'）
    _plot_name: str = 'plot'  # 图表保存名称
    # 回测报告保存名称（默认"qs_reports"）
    _qs_reports_name: str = "qs_reports"  # 回测报告名称
    # 原始数据列表（内部使用）
    _datas: list[pd.DataFrame]
    # 绘图数据结构（供前端/绘图工具使用，包含K线、指标、配置等）
    _plot_datas: list
    # 初始持仓记录（实盘模式用）
    _init_trades: list
    # 指标绘图配置记录（包含是否显示、名称、线型等）
    _indicator_record: list
    # RL模式的信号特征数组（处理后的特征数据）
    _signal_features: Optional[np.ndarray] = None
    # 账户净值序列（用于回测分析）
    _net_worth: Optional[pd.Series] = None
    # 回测统计分析对象（计算夏普比率、最大回撤等）
    _stats: Optional[Stats] = None
    # 回测绘图对象（生成收益曲线、回撤曲线等）
    _qs_plots: Optional[QSPlots] = None
    # SQLite数据库连接（从数据库获取历史数据用）
    _sqlite = None
    # RL训练配置对象（ElegantRL的Config）
    _rl_config: Optional[RlConfig] = None
    # RL评估环境（用于验证训练后的智能体）
    evaluator_env: Strategy
    # RL环境参数（状态维度、动作维度等）
    _env_args: dict
    # RL当前状态数组
    _state: np.ndarray
    # RL智能体（actor网络）
    _actor: Any = None
    # RL数据增强函数列表
    _data_enhancement_funcs: list[Callable] = []
    # 是否已加载数据增强函数
    _if_data_enhancement: bool = False
    # RL观测窗口大小（默认10）
    window_size: int = 10

    @classmethod
    def cls_copy(cls, name: str = '', **kwargs) -> Strategy:
        """
        复制策略类（创建新的策略类实例）
        用于动态生成多个策略实例，支持自定义类属性

        Args:
            name (str): 新策略类的名称（必填，确保唯一性）
            **kwargs: 额外的类属性（覆盖原类属性，如params、config）

        Returns:
            Strategy: 新的策略类实例

        Raises:
            AssertionError: 未提供name或name非字符串时触发
        """
        assert name and isinstance(name, str), "请设置策略名称"
        # 合并原类属性与kwargs，kwargs优先级更高
        kwargs = {**cls.__dict__, **kwargs}
        # 动态创建新类（继承自原策略类）
        return type(name, (cls,), kwargs)

    def _get_optimize_results(self, ismax, target):
        """
        获取参数优化的目标结果（用于参数优化时评估单组参数性能）
        根据目标字段（如收益率、夏普比率）计算结果，并更新最优目标值

        Args:
            ismax (bool): 目标是否为最大化（如收益率最大化设为True，风险最小化设为False）
            target (Iterable): 目标字段列表（如["total_profit", "sharpe_ratio"]）

        Returns:
            tuple: 目标字段对应的结果元组
        """
        results = []
        for _target in target:
            # 从Stats对象获取目标字段值（支持方法调用，如sharpe()）
            result = getattr(self._stats, _target)()
            # 若结果为序列（如时间序列），取最后一个值；否则直接使用
            result = result if isinstance(result, float) else list(result)[-1]
            # 处理None值（默认为0）
            result = result if result else 0.
            results.append(result)
        # 更新最优目标值（根据ismax判断最大化/最小化）
        if ismax:
            if results[0] > self._target_train:
                self._target_train = results[0]
                print(f"best train results:{results}")
        else:
            if results[0] < self._target_train:
                self._target_train = results[0]
                print(f"best train results:{results}")
        return tuple(results)

    @staticmethod
    @cache
    def __pytdx_category_dict(category="pytdx_category_dict") -> dict:
        """
        缓存PyTDX的周期-类别编码映射（静态方法，缓存结果避免重复计算）
        PyTDX通过类别编码区分不同K线周期，该方法提供周期（秒/字符串）到编码的映射

        Args:
            category (str): 映射名称（预留参数，无实际作用）

        Returns:
            dict: 周期到PyTDX类别的映射，键为周期（秒或'D'/'W'等），值为类别编码
        """
        return dict(zip(
            [60, 5*60, 15*60, 30*60, 60*60, 60*60*24, 'W', 'M', 'S', 'Y'],
            [7, 0, 1, 2, 3, 4, 5, 6, 10, 11]
        ))

    def __getKlineSerial(self, symbol, cycle, lenght=800):
        """
        通过PyTDX获取股票K线数据（内部方法，供get_data调用）
        支持分批次获取（PyTDX单次最大获取800根），自动合并数据并格式化

        Args:
            symbol (str): 股票代码（如'600000'，沪市前加'6'，深市前加'0'）
            cycle (int): K线周期（秒，如60=1分钟，300=5分钟）
            lenght (int): 数据长度（默认800，最大支持2400）

        Returns:
            pd.DataFrame: 格式化后的K线数据，包含['datetime', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'duration', 'price_tick', 'volume_multiple']

        Raises:
            AssertionError: 获取数据为空时触发
        """
        # 根据周期获取PyTDX类别编码
        category = self.__pytdx_category_dict().get(cycle)
        # 判断市场（沪市代码以'6'开头，深市以'0'开头）
        mk = 1 if symbol[0] == '6' else 0
        data = []
        # 计算分批次数量（PyTDX单次最大800根）
        div, mod = divmod(lenght, 800)
        # 处理余数批次（若mod>0，先获取余数部分）
        if mod:
            data += self._tdxapi.get_security_bars(
                category, mk, symbol, div*800, mod)
        # 处理完整批次（每次800根）
        for i in range(div):
            data += self._tdxapi.get_security_bars(
                category, mk, symbol, i*800, 800)
        # 转换为DataFrame并格式化
        data = self._tdxapi.to_df(data)
        assert not data.empty, "获取数据失败"
        # 字段映射与格式处理
        data['volume'] = data.vol  # PyTDX的成交量字段为'vol'，统一为'volume'
        data.datetime = pd.to_datetime(data.datetime)  # 转换时间格式
        data = data[['datetime', 'open', 'high', 'low', 'close', 'volume']]
        # 补充合约信息（股票默认参数）
        data['symbol'] = symbol
        data['duration'] = cycle
        data['price_tick'] = 1e-2  # 股票最小变动单位默认0.01
        data['volume_multiple'] = 1.  # 股票合约乘数默认1
        return data

    def get_data(self, symbol: str | pd.DataFrame = None, duration_seconds: int = 60, data_length: int | None = None, **kwargs) -> BtData:
        """
        获取K线数据的统一接口（支持多数据源，自动适配股票/期货、回测/实盘）
        支持的数据源：本地CSV、TQSDK（期货）、PyTDX（股票）、SQLite数据库、外部DataFrame

        Args:
            symbol (str | pd.DataFrame): 数据标识：
                - str：合约代码（期货，如'SHFE.rb2410'）或股票代码（如'600000'）
                - pd.DataFrame：外部K线数据（需包含['datetime', 'open', 'high', 'low', 'close', 'volume']）
            duration_seconds (int, optional): K线周期（秒），默认60（1分钟）
            data_length (int | None, optional): 数据长度，默认None（取数据源最大长度）
            **kwargs: 额外参数：
                - save (str | bool): 是否保存数据到本地CSV，值为文件名（如'sh600000'）
                - user_name/password: TQSDK账号密码（实盘模式用）
                - ip/port: PyTDX服务器IP和端口（股票数据用）

        Returns:
            BtData: 封装后的K线数据对象（含合约信息、指标接口等）

        Raises:
            AssertionError: 数据类型非pd.DataFrame或数据为空时触发
            ImportError: 未安装PyTDX却尝试获取股票数据时触发
        """
        save = kwargs.pop("save", None)
        # 优化/实盘首次启动时跳过（避免重复获取）
        if self._isoptimize or self._is_live_trading:
            if self._first_start:
                return
        # 2. 生成BtData的ID（关联策略ID与数据索引）
        id = self._btdatasset.num
        btid = BtID(self._sid, id, id)
        # 3. 实盘模式：从TQSDK实时获取K线（默认300根，确保足够长度）
        if self._is_live_trading:
            data_length = data_length if data_length and data_length >= 10 else 300
            kline = self._api.get_kline_serial(
                symbol, duration_seconds, data_length)
            data = kline.copy()
            data.datetime = data.datetime.apply(time_to_datetime)
            kwargs.update({"tq_object": kline})  # 保存原始TQKline对象

        # 4. 回测模式：多数据源适配
        else:
            data_length = data_length if data_length and data_length >= 300 else 10000
            # 1. 处理symbol为字符串的情况（期货/股票代码）
            if isinstance(symbol, str) and symbol:
                if os.path.exists(symbol):
                    symbol = read_unknown_file(symbol)
                else:
                    name = symbol
                    # 检查本地CSV是否存在（优先加载本地数据）
                    symbol_path = os.path.join(
                        BASE_DIR, "data", "test", f"{symbol}.csv")
                    if os.path.exists(symbol_path):
                        symbol = pd.read_csv(symbol_path)
                    else:
                        # 从TQSDK获取期货数据（需账号密码或已初始化_api）
                        user_name: str = kwargs.pop("user_name", "")
                        password: str = kwargs.pop("password", "")
                        if (user_name and password) or self._api:
                            if not self._api:
                                # 静默初始化TQSDK（重定向stderr避免日志输出）
                                from unittest.mock import patch
                                from io import StringIO
                                with patch('sys.stderr', new=StringIO()):
                                    from tqsdk import TqApi, TqAuth, TqKq
                                self._api = TqApi(
                                    TqKq(), auth=TqAuth(user_name, password))
                            # 获取合约报价（含最小变动单位、乘数等）
                            quote = self._api.get_quote(symbol)
                            # 获取K线数据并格式化时间
                            symbol = self._api.get_kline_serial(
                                symbol, duration_seconds, data_length)
                            symbol.datetime = symbol.datetime.apply(
                                time_to_datetime)
                            # 补充合约信息
                            symbol["price_tick"] = quote.price_tick
                            symbol["volume_multiple"] = quote.volume_multiple

            # 4.1 外部DataFrame（用户传入）
            if isinstance(symbol, pd.DataFrame):
                data = self.__check_and_add_fileds(symbol)
            # 4.2 股票数据（通过PyTDX获取）
            elif isinstance(symbol, str) and symbol[0].isdigit():
                if self._tdxapi is None:
                    try:
                        from pytdx.hq import TdxHq_API
                        from pytdx.config.hosts import hq_hosts
                        self._tdxapi = TdxHq_API()
                    except:
                        raise ImportError("请安装pytdx（pip install pytdx）以获取股票数据")
                assert self._tdxapi, "请安装pytdx"
                # PyTDX服务器配置（默认取第5个服务器）
                ip = kwargs.pop('ip', hq_hosts[4][1])
                port = kwargs.pop('port', hq_hosts[4][2])
                # 数据长度默认10000（足够长的历史数据）
                # 连接PyTDX并获取数据
                with self._tdxapi.connect(ip, port):
                    data = self.__getKlineSerial(
                        symbol, duration_seconds, data_length)
            # 4.3 期货数据（通过TQSDK获取）
            elif self._api:
                # 合约代码映射（支持简写转全称）
                symbol = self._tq_contracts_dict.get(symbol, symbol)
                data = self._api.get_kline_serial(
                    symbol, duration_seconds, data_length)
                data.datetime = data.datetime.apply(time_to_datetime)
                # 补充合约信息（从报价获取）
                quote = self._api.get_quote(symbol)
                data["price_tick"] = quote.price_tick
                data["volume_multiple"] = quote.volume_multiple
            # 4.4 已加载的原始数据（_datas中匹配名称）
            elif len(self._datas) > 0:
                data = list(filter(lambda x: x.name == symbol, self._datas))[
                    0].copy()
                data = self.__check_and_add_fileds(data)
            # 4.5 SQLite数据库（默认数据源）
            else:
                try:
                    if self._sqlite is None:
                        from minibt.sqlitedata import MySqlite
                        self._sqlite = MySqlite()
                    # 从数据库快速获取数据
                    data = self._sqlite.quick_real_dataframe(
                        symbol, duration_seconds)
                except Exception as e:
                    print(f"无法从数据库获取数据：{e}")

        # 5. 保存数据到本地CSV（若指定save参数）
        if save and isinstance(data, pd.DataFrame):
            # 处理文件名（默认用symbol，支持自定义）
            file_name = save if isinstance(save, str) else name
            if "." in file_name:
                file_name = file_name.split(".")[1]
            file_name = f"{file_name}.csv"
            # 保存路径（BASE_DIR/data/test/）
            path = os.path.join(BASE_DIR, "data", "test", file_name)
            data.to_csv(path, index=False)
            # 自动更新本地数据工具类（生成utils.py，包含所有CSV数据的引用）
            import glob
            csv_files = glob.glob(os.path.join(
                BASE_DIR, "data", "test", "*.csv"))
            py_file_path = os.path.join(BASE_DIR, "data", "utils.py")
            # 生成工具类内容
            class_content = [
                'from .tools import *', "", "",
                'class LocalDatas(base):', '    """本地CSV数据"""']
            for file in csv_files:
                file_name = os.path.splitext(os.path.basename(file))[0]
                class_content.append(
                    f'    {file_name} = DataString("{file_name}")')
            class_content.extend(["", ""])
            class_content.append('LocalDatas=LocalDatas()')
            # 写入文件
            with open(py_file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(class_content))
            # 处理数据（补充必要字段）
            data = self.__process_data(data)

        # 6. 截取指定长度的数据（若data_length有效）
        if isinstance(data_length, int) and data_length >= 300:
            data = data[-data_length:]

        # 7. 数据校验（确保为DataFrame且非空，包含必要字段）
        assert isinstance(
            data, pd.DataFrame), f"数据类型{type(data)},非pd.DataFrame类型"
        assert not data.empty, "数据不能为空"
        assert set(data.columns).issuperset(
            set(FILED.ALL)), f"传入数据必须包含{FILED.All.tolist()},数据列为:{list(data.columns)}"

        # 8. 创建并返回BtData对象
        name = f"datas{btid.plot_id}"
        return BtData(data, id=btid, sname=name, ind_name=name, ** kwargs)

    def __check_and_add_fileds(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        检查并补充DataFrame的必要字段（确保符合BtData的格式要求）
        自动处理时间格式、补充合约信息（symbol、duration等），避免字段缺失

        Args:
            data (pd.DataFrame): 待处理的K线数据

        Returns:
            pd.DataFrame: 补充字段后的完整数据，包含['datetime', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'duration', 'price_tick', 'volume_multiple']
        """
        # 1. 时间格式转换（支持float/str转datetime）
        if isinstance(data.datetime.iloc[0], (float, str)):
            data.datetime = data.datetime.apply(time_to_datetime)
        col = data.columns

        # 2. 补充缺失字段（默认值适配股票/期货通用场景）
        if 'symbol' not in col:
            data['symbol'] = f"symbol{id}"  # 默认合约名（用户可后续修改）
        if 'duration' not in col:
            data['duration'] = get_cycle(data.datetime)  # 自动计算周期（秒）
        if 'price_tick' not in col:
            data['price_tick'] = 1e-2  # 默认最小变动单位0.01
        if 'volume_multiple' not in col:
            data['volume_multiple'] = 1.  # 默认合约乘数1

        return data

    def _get_plot_datas(self):
        """
        整理绘图所需数据（供前端或绘图工具使用）
        整合K线数据、指标数据、绘图配置，构建统一的绘图数据结构，支持止损线等特殊元素

        输出结构（_plot_datas）说明：
        [
            策略类名,
            [各合约的源数据对象],
            [各合约的指标绘图数据列表],
            [各合约是否为主图显示],
            [各合约的绘图配置（如颜色、线型）]
        ]
        """
        if self.config.isplot:  # 仅当配置开启绘图时执行
            # 1. 将止损线添加到指标集合（确保止损线可绘图）
            for _, value in self._btdatasset.items():
                if value._btdatasetting.isstop:
                    self._btindicatordataset.add_data(
                        value.stop_lines.sname, value.stop_lines)

            # 2. 初始化指标绘图数据容器（按合约数量分组）
            init_inds_datas = [[] for _ in range(self._btdatasset.num)]
            _indicator_record = [[] for _ in range(self._btdatasset.num)]

            # 3. 遍历所有指标，整理绘图数据（按合约分组）
            for k, v in self._btindicatordataset.items():
                # 获取指标的绘图数据（包含plot_id、是否显示、名称、数值等）
                plot_id, *datas = v._get_plot_datas(k)
                init_inds_datas[plot_id].append(datas)
                # 记录指标绘图配置（用于后续更新）
                _indicator_record[plot_id].append(
                    [*datas[:4], datas[8], datas[9]])

            # 4. 构建最终的绘图数据结构
            self._plot_datas = [
                self.__class__.__name__,  # 策略类名
                [data.source_object for data in self._btdatasset.values()],  # 各合约源数据
                init_inds_datas,  # 各合约的指标绘图数据
                [data.ismain for data in self._btdatasset.values()],  # 各合约是否主图显示
                [data.plotinfo.vars for data in self._btdatasset.values()]  # 各合约绘图配置
            ]

            # 5. 保存指标绘图配置记录
            self._indicator_record = _indicator_record

    def __bt_next(self, x: Any = 0):
        """
        回测循环的迭代方法（逐根K线处理）
        处理止损逻辑、调用策略核心逻辑（step）、更新账户历史，是回测的核心循环单元

        Args:
            x (Any, optional): 迭代参数（无实际作用，适配map调用）. Defaults to 0.
        """
        # 1. 更新回测索引（逐根K线推进）
        self._btindex += 1

        # 2. 处理止损逻辑（若启用止损）
        if self._isstop:
            istradings = []  # 标记各合约是否触发止损交易
            for data in self._btdatasset.values():
                if data._btdatasetting.isstop:
                    # 根据止损模式更新止损状态
                    if data._stop_mode == StopMode.Postposition:
                        # 持仓后止损（默认模式，平仓后生效）
                        istradings.append(data.stop._update())
                    elif data._stop_mode == StopMode.FrontLoaded:
                        # 前置止损（开仓时即设置）
                        istradings.append(data.stop._update(True))
                    elif data._stop_mode == StopMode.PreSkip:
                        # 跳过止损（触发时跳过当前K线）
                        istradings.append(data.stop._update(True))
                        data._btdatasetting.tradable = False  # 标记当前合约不可交易
                else:
                    istradings.append(False)  # 未启用止损的合约标记为False

            # 3. 调用策略核心逻辑（step方法，子类重写实现交易逻辑）
            self.step()

            # 4. 恢复合约可交易状态（跳过止损后重置）
            [setattr(data._btdatasetting, "tradable", True)
             for data in self._btdatasset.values() if not data._btdatasetting.tradable]

            # 5. 触发止损时调整目标仓位（平仓）
            if any(istradings):
                [data.set_target_size() for i, data in enumerate(self._btdatasset.values())
                 if data._btdatasetting.isstop and istradings[i] and data.position.pos]

        # 6. 未启用止损：直接调用策略核心逻辑
        else:
            self.step()

        # 7. 更新账户历史记录（记录当前周期的权益、仓位、盈亏等）
        self._account.update_history()

    def _live_trading(self):
        """
        实盘交易的主方法（实时行情驱动）
        初始化实盘数据、处理RL动作（若启用）、调用策略核心逻辑（step），适配TQSDK实时推送

        实盘与回测的关键区别：
        - 数据实时更新（从TQSDK推送获取）
        - 交易通过TargetPosTask实现（确保仓位准确）
        - 无回测索引迭代，依赖行情变化触发
        """
        # 1. 更新实盘索引（标记当前周期）
        self._btindex += 1
        # 2. 重置初始化状态（允许重新初始化指标）
        self._isinit = False
        # 3. 实时更新K线数据（从TQSDK同步最新数据）
        [btdata._inplace_values() for btdata in self._btdatasset.values()]
        # 4. 策略初始化（重新计算指标，适应实时数据）
        self._strategy_init()

        # 5. RL模式：获取智能体动作（无梯度计算，避免性能消耗）
        if self.rl:
            # 注：原代码中torch相关导入被注释，实际使用需解除注释
            # self.action = self._actor(as_tensor(self._get_observation(), dtype=float32).unsqueeze(0)).cpu().numpy()[0]
            pass

        # 6. 标记初始化完成，调用策略核心逻辑
        self._isinit = True
        self.step()

    def __rl_next(self, x):
        """
        RL模式下的回测迭代方法（逐根K线处理）
        从RL智能体（actor）获取动作，调用策略核心逻辑，更新状态与账户历史

        Args:
            x (Any): 迭代参数（无实际作用，适配map调用）
        """
        # 1. 更新回测索引
        self._btindex += 1
        # 2. 转换当前状态为torch张量（适配actor输入）
        tensor_state = self.th.as_tensor(
            self._state, dtype=self.th.float32, device=self.device).unsqueeze(0)
        # 3. 获取actor的动作（无梯度计算，回测模式）
        tensor_action = self.actor(tensor_state)
        action = tensor_action.detach().cpu().numpy()[0]
        # 4. 调用策略核心逻辑，更新状态
        self._state, *_ = self.step(action)
        # 5. 更新账户历史记录
        self._account.update_history()

    def _bt_run(self):
        """
        回测主方法（统一调度回测流程）
        根据是否启用RL模式，调用对应的迭代方法，完成回测后执行收尾工作（止损、结果分析）
        """
        # 1. 标记回测初始化完成
        self._isinit = True

        # 2. RL模式回测（调用__rl_next迭代）
        if self.rl:
            # 无梯度模式（回测时禁用梯度计算，提升性能）
            with self.th.no_grad():
                list(map(self.__rl_next, range(
                    self.btindex+1, self._btdatasset.max_length)))

        # 3. 普通模式回测（调用__bt_next迭代）
        else:
            list(map(self.__bt_next, range(
                self.btindex+1, self._btdatasset.max_length)))

        # 4. 回测收尾：执行策略停止逻辑、获取结果、初始化分析工具
        self.stop()          # 策略停止钩子（子类重写，如平仓、释放资源）
        self._get_result()    # 获取回测结果（从账户历史提取）
        self._qs_init()       # 初始化QuantStats分析（计算指标、绘图）
        # 5. 标记回测结束，重置初始化状态
        self._isinit = False

    @staticmethod
    def _to_ha(data: pd.DataFrame, isha: bool):
        """
        将K线数据转换为HA（Heikin-Ashi，黑金）K线（静态方法）
        HA K线平滑价格波动，突出趋势，计算公式：
        - HA开盘价 = (前一根HA开盘价 + 前一根HA收盘价) / 2
        - HA收盘价 = (当前开盘价 + 当前最高价 + 当前最低价 + 当前收盘价) / 4
        - HA最高价 = max(当前最高价, HA开盘价, HA收盘价)
        - HA最低价 = min(当前最低价, HA开盘价, HA收盘价)

        Args:
            data (pd.DataFrame): 原始K线数据（需包含OHLC字段）
            isha (bool): 是否转换为HA K线（True=转换，False=不转换）

        Returns:
            pd.DataFrame: 转换后的K线数据（HA或原始）
        """
        if isha:
            # 调用ta库计算HA K线（需确保ta库已安装：pip install ta）
            df = data.ta.ha()
            # 替换原始OHLC字段为HA K线
            data.loc[:, FILED.OHLC] = df.values
        return data

    @staticmethod
    def _to_lr(data: pd.DataFrame, islr: int):
        """
        将K线数据转换为线性回归K线（静态方法）
        线性回归K线通过线性回归模型平滑价格，突出趋势方向，适用于趋势跟踪策略

        Args:
            data (pd.DataFrame): 原始K线数据（需包含OHLC字段）
            islr (int): 线性回归窗口长度（>1时转换，否则不转换）

        Returns:
            pd.DataFrame: 转换后的K线数据（线性回归或原始）
        """
        if isinstance(islr, int) and islr > 1:
            # 调用ta库计算线性回归K线
            df = data.ta.Linear_Regression_Candles(length=islr)
            # 替换原始OHLC字段为线性回归K线
            data.loc[:, FILED.OHLC] = df.values
        return data

    def _get_result(self):
        """
        获取回测结果（从账户历史记录提取）
        支持参数优化模式（避免重复获取），返回所有Broker的历史数据列表

        Returns:
            list[pd.DataFrame]: 回测结果列表，每个元素对应一个Broker的历史数据（含权益、仓位、盈亏等）
        """
        if self._isoptimize or (not self._results):
            # 从账户获取历史记录（每个Broker对应一个DataFrame）
            self._results = self._account.get_history_results()
        return self._results

    @property
    def plot(self) -> None:
        """
        绘图开关属性（预留接口，实际逻辑在isplot中实现）
        注：该属性当前无实际作用，建议使用isplot属性控制绘图
        """
        ...

    @plot.setter
    def plot(self, value):
        """
        设置所有指标的绘图开关（兼容旧接口，实际调用isplot逻辑）

        Args:
            value (bool): 绘图开关（True=显示指标，False=隐藏指标）
        """
        value = bool(value)
        for _, v in self._btindicatordataset.items():
            v.plot = value

    def buy(self, data: BtData = None, size: int = 1, stop=None, **kwargs):
        """
        买入开仓/加仓接口（统一封装回测与实盘逻辑）
        支持指定合约、手数、止损参数，自动校验手数有效性

        Args:
            data (BtData, optional): 目标合约数据（默认使用默认合约_btdatasset.default_btdata）. Defaults to None.
            size (int): 买入手数（必须为正整数，>0）. Defaults to 1.
            stop (Any, optional): 止损参数（如止损点数、百分比，具体格式由止损类定义）. Defaults to None.
            **kwargs: 额外参数（如止损模式、触发条件等，传递给_stop方法）

        Returns:
            float | None: 交易盈亏（回测模式返回，实盘模式返回浮动盈亏）

        Raises:
            AssertionError: size非正整数时触发
        """
        # 区分实盘与回测，调用对应逻辑
        if self._is_live_trading:
            return self._buy_live_trading(data=data, size=size, stop=stop, **kwargs)
        return self._buy_back_trading(data=data, size=size, stop=stop, ** kwargs)

    def _buy_back_trading(self, data: BtData = None, size: int = 1, stop=None, **kwargs) -> float | None:
        """
        回测模式的买入逻辑（内部方法，供buy调用）
        校验手数、设置止损（若指定）、调用Broker更新仓位，返回交易盈亏

        Args:
            data (BtData, optional): 目标合约数据. Defaults to None.
            size (int): 买入手数. Defaults to 1.
            stop (Any, optional): 止损参数. Defaults to None.
            **kwargs: 额外止损参数.

        Returns:
            float | None: 买入交易的盈亏（手续费已扣除）

        Raises:
            AssertionError: size非正整数时触发
        """
        size = int(size)
        # 校验手数（必须为正整数）
        assert size > 0, '手数为不少于0的正整数'
        # 默认使用主合约数据
        if data is None:
            data = self._btdatasset.default_btdata
        # 设置止损（若未启用且指定stop参数）
        if not data._btdatasetting.isstop:
            if stop and data._btdatasetting.stop is None:
                data._set_stop(stop, ** kwargs)
                self._isstop = True  # 标记策略启用止损
        # 调用Broker执行买入（long=True表示多头）
        data._broker.update(size, True)
        # 返回本次交易的盈亏（手续费已包含）
        return data._broker.profit

    def _buy_live_trading(self, data: BtData = None, size: int = 1, stop=None, **kwargs) -> float:
        """
        实盘模式的买入逻辑（内部方法，供buy调用）
        通过TQSDK的TargetPosTask设置目标仓位，实现买入开仓/加仓，返回当前浮动盈亏

        Args:
            data (BtData, optional): 目标合约数据. Defaults to None.
            size (int): 买入手数（相对于当前仓位的增量）. Defaults to 1.
            stop (Any, optional): 止损参数（预留，实盘止损需单独处理）. Defaults to None.
            **kwargs: 额外参数（预留）.

        Returns:
            float: 当前合约的浮动盈亏

        Raises:
            AssertionError: size非正整数时触发
        """
        size = int(size)
        assert size > 0, '手数为不少于0的正整数'
        tqobj = self._tqobjs[self._sid]
        # 获取当前仓位对象
        position = tqobj.Position
        # 计算目标仓位（当前仓位 + 买入手数）
        size += position.pos
        # 获取当前浮动盈亏
        profit = position.float_profit
        # 通过TargetPosTask设置目标仓位（实盘核心逻辑）
        tqobj.TargetPosTask.set_target_volume(size)
        # 返回浮动盈亏
        return profit

    def sell(self, data: BtData = None, size: int = 1, stop=None, **kwargs) -> None:
        """
        卖出平仓/开空接口（统一封装回测与实盘逻辑）
        支持指定合约、手数、止损参数，自动校验手数有效性

        Args:
            data (BtData, optional): 目标合约数据（默认使用默认合约）. Defaults to None.
            size (int): 卖出手数（必须为正整数，>0）. Defaults to 1.
            stop (Any, optional): 止损参数（如止损点数、百分比）. Defaults to None.
            **kwargs: 额外参数（如止损模式、触发条件等）

        Returns:
            float | None: 交易盈亏（回测模式返回，实盘模式返回浮动盈亏）

        Raises:
            AssertionError: size非正整数时触发
        """
        # 区分实盘与回测，调用对应逻辑
        if self._is_live_trading:
            return self._sell_live_trading(data=data, size=size, stop=stop, **kwargs)
        return self._sell_back_trading(data=data, size=size, stop=stop, ** kwargs)

    def _sell_back_trading(self, data: BtData = None, size: int = 1, stop=None, **kwargs):
        """
        回测模式的卖出逻辑（内部方法，供sell调用）
        校验手数、设置止损（若指定）、调用Broker更新仓位，返回交易盈亏

        Args:
            data (BtData, optional): 目标合约数据. Defaults to None.
            size (int): 卖出手数. Defaults to 1.
            stop (Any, optional): 止损参数. Defaults to None.
            **kwargs: 额外止损参数.

        Returns:
            float | None: 卖出交易的盈亏（手续费已扣除）

        Raises:
            AssertionError: size非正整数时触发
        """
        size = int(size)
        assert size > 0, '手数为不少于0的正整数'
        # 默认使用主合约数据
        if data is None:
            data = self._btdatasset.default_btdata
        # 设置止损（若未启用且指定stop参数）
        if not data._btdatasetting.isstop:
            if stop and data._btdatasetting.stop is None:
                data._set_stop(stop, ** kwargs)
                self._isstop = True
        # 调用Broker执行卖出（long=False表示空头/平仓）
        data._broker.update(size, False)
        # 返回本次交易的盈亏
        return data._broker.profit

    def _sell_live_trading(self, data: BtData = None, size: int = 1, stop=None, **kwargs):
        """
        实盘模式的卖出逻辑（内部方法，供sell调用）
        通过TQSDK的TargetPosTask设置目标仓位，实现卖出平仓/开空，返回当前浮动盈亏

        Args:
            data (BtData, optional): 目标合约数据. Defaults to None.
            size (int): 卖出手数（相对于当前仓位的减量）. Defaults to 1.
            stop (Any, optional): 止损参数（预留）. Defaults to None.
            **kwargs: 额外参数（预留）.

        Returns:
            float: 当前合约的浮动盈亏

        Raises:
            AssertionError: size非正整数时触发
        """
        size = int(size)
        assert size > 0, '手数为不少于0的正整数'
        tqobj = self._tqobjs[self._sid]
        # 获取当前仓位对象
        position = tqobj.Position
        # 计算目标仓位（当前仓位 - 卖出手数，负数表示空头）
        size -= position.pos
        # 获取当前浮动盈亏
        profit = position.float_profit
        # 通过TargetPosTask设置目标仓位（负仓位表示空头）
        tqobj.TargetPosTask.set_target_volume(-size)
        # 返回浮动盈亏
        return profit

    def set_target_size(self, data: BtData = None, size: int = 0) -> None:
        """
        设置目标仓位接口（统一封装回测与实盘逻辑）
        直接指定最终仓位手数，自动计算仓位差并执行交易（开仓/平仓/加仓/减仓）

        Args:
            data (BtData, optional): 目标合约数据（默认使用默认合约）. Defaults to None.
            size (int): 目标仓位手数（正数=多头，负数=空头，0=平仓）. Defaults to 0.
        """
        # 区分实盘与回测，调用对应逻辑
        if self._is_live_trading:
            return self._set_target_size_live_trading(data, size)
        return self._set_target_size_back_trading(data, size)

    def _set_target_size_back_trading(self, data: BtData = None, size: int = 0):
        """
        回测模式的目标仓位逻辑（内部方法，供set_target_size调用）
        计算当前仓位与目标仓位的差值，调用Broker执行对应的交易

        Args:
            data (BtData, optional): 目标合约数据. Defaults to None.
            size (int): 目标仓位手数. Defaults to 0.
        """
        # 默认使用主合约数据
        if data is None:
            data = self._btdatasset.default_btdata
        # 转换为整数手数
        size = int(size)
        # 获取当前仓位
        pre_pos = data.position.pos
        # 计算仓位差（目标仓位 - 当前仓位）
        diff_pos = size - pre_pos
        # 仓位差非零时执行交易
        if diff_pos:
            # 调用Broker执行交易（diff_pos>0=买入，<0=卖出）
            data._broker.update(abs(diff_pos), diff_pos > 0)

    def _set_target_size_live_trading(self, data: BtData = None, size: int = 0):
        """
        实盘模式的目标仓位逻辑（内部方法，供set_target_size调用）
        通过TQSDK的TargetPosTask直接设置目标仓位，自动处理交易细节

        Args:
            data (BtData, optional): 目标合约数据. Defaults to None.
            size (int): 目标仓位手数. Defaults to 0.
        """
        # 默认使用主合约数据
        tqobj = self._tqobjs[self._sid]
        # 转换为整数手数
        size = int(size)
        # 目标仓位与当前仓位不同时执行
        if size != tqobj.Position.pos:
            # 通过TargetPosTask设置目标仓位
            tqobj.TargetPosTask.set_target_volume(size)

    # ------------------------------
    # 量化分析（QuantStats）相关方法
    # ------------------------------

    def _qs_init(self, isop: bool = False) -> Stats:
        """
        初始化量化分析工具（QuantStats）
        计算账户净值、初始化Stats（统计指标）和QSPlots（绘图），支持参数优化模式

        Args:
            isop (bool, optional): 是否为参数优化模式. Defaults to False.

        Returns:
            Stats: 初始化后的统计分析对象
        """
        # 1. 获取回测收益序列（从账户历史提取）
        self.profits = self._account.get_profits()
        # 2. 判断收益是否有效（排除所有收益相同的情况）
        state = len(self.profits.unique()) != 1.

        # 3. 根据收益有效性调整配置（避免无意义分析）
        if self.config.print_account:
            self.config.print_account = state  # 收益无效时不打印账户信息
        if self.config.profit_plot:
            self.config.profit_plot = state  # 收益无效时不绘制收益曲线

        # 4. 处理净值序列（计算收益率，用于后续分析）
        index = self._btdatasset.date_index  # 获取K线时间索引
        self.profits.index = index  # 对齐时间索引
        self._net_worth = self.profits.pct_change()[1:]  # 计算日度收益率（跳过首行NaN）

        # 5. 初始化QSPlots（绘图对象，非优化模式）
        if not self._isoptimize:
            from .qs_plots import QSPlots
            self._qs_plots = QSPlots(
                self.profits, index=index, name='net_worth')

        # 6. 初始化Stats（统计分析对象，计算夏普比率、最大回撤等）
        self._stats = Stats(
            self.profits,
            index=index,
            name='profit',
            available=self.config.value  # 初始资金
        )
        return self._stats

    @property
    def pprint(self):
        """
        格式化打印回测核心统计指标（属性形式调用，无需传参）
        仅当存在有效收益数据时输出，包含收益、风险、交易频率等多维度指标，
        采用三列格式化展示（指标名称、数值、单位/说明），便于快速复盘策略性能

        核心逻辑：
        1. 校验收益数据有效性（避免无意义计算）
        2. 计算单次收益（差分）与收益率序列
        3. 基于QuantStats工具计算15项核心指标
        4. 调用format_3col_report生成结构化输出

        输出指标说明：
        - final return: 回测期间总收益（绝对值）
        - commission: 回测期间总手续费
        - compounded: 累计收益率（复利计算，如1.2表示20%）
        - sharpe: 年化夏普比率（风险调整后收益，越高越好）
        - risk: 风险值（VaR，95%置信区间下的最大潜在亏损）
        - risk/return: 风险收益比（风险与收益的比值，越低越好）
        - max_drawdown: 最大回撤（绝对值，如15%表示最大亏损15%）
        - profit_factor: 盈亏比（总盈利/总亏损，>1表示整体盈利）
        - profit_ratio: 收益比率（平均盈利/平均亏损，>1表示盈利能力强于亏损）
        - win_rate: 胜率（正收益交易占比，越高越好）
        - wins/losses: 盈利/亏损交易次数（反映交易频率与准确性）
        - avg_return: 单次交易平均收益（绝对值）
        - avg_win/avg_loss: 单次盈利/亏损的平均金额（反映盈亏幅度）
        """
        if hasattr(self, "profits") and self.profits is not None:
            # 计算单次收益（原始收益序列差分，首行NaN替换为0）
            profits = pd.Series(self.profits).diff()
            profits.iloc[0] = 0.
            # 收益率序列（用于风险指标计算）
            returns = self._net_worth

            # 仅当收益存在波动时计算指标（排除所有收益相同的无效情况）
            if len(profits.unique()) > 1:
                # 1. 收益相关指标
                final_return = profits.sum()  # 总收益（绝对值）
                comm = self._account._total_commission  # 总手续费
                compounded = qs_stats.comp(returns)  # 累计收益率（复利）

                # 2. 风险相关指标
                sharpe = qs_stats.sharpe(returns)  # 年化夏普比率（无风险利率默认0）
                max_dd = qs_stats.max_drawdown(returns)  # 最大回撤（负值，需取绝对值）
                value_at_risk = qs_stats.value_at_risk(
                    returns)  # VaR风险值（95%置信区间）
                risk_return_ratio = qs_stats.risk_return_ratio(
                    returns)  # 风险收益比

                # 3. 交易质量指标
                profit_factor = qs_stats.profit_factor(returns)  # 盈亏比（总盈利/总亏损）
                profit_ratio = qs_stats.profit_ratio(
                    returns)  # 收益比率（平均盈利/平均亏损）
                win_rate = qs_stats.win_rate(returns)  # 胜率（正收益交易占比）

                # 4. 交易频率指标
                wins = len(profits[profits > 0.])  # 盈利交易次数
                losses = len(profits[profits < 0.])  # 亏损交易次数

                # 5. 收益幅度指标
                avg_return = qs_stats.avg_return(profits)  # 单次交易平均收益
                avg_win = qs_stats.avg_win(profits)  # 单次盈利平均金额
                avg_loss = qs_stats.avg_loss(profits)  # 单次亏损平均金额

                # 组织指标（名称、数值、格式化字符串）
                metrics = [
                    ("final return", final_return, "{:.2f}"),
                    ("commission", comm, "{:.2f}"),
                    ("compounded", compounded, "{:.2%}"),
                    ("sharpe", sharpe, "{:.4f}"),
                    ("risk", value_at_risk, "{:.4f}"),
                    ("risk/return", risk_return_ratio, "{:.4f}"),
                    ("max_drawdown", abs(max_dd), "{:.4%}"),
                    ("profit_factor", profit_factor, "{:.4f}"),
                    ("profit_ratio", profit_ratio, "{:.4f}"),
                    ("win_rate", win_rate, "{:.4%}"),
                    ("wins", wins, "{:d}"),
                    ("losses", losses, "{:d}"),
                    ("avg_return", avg_return, "{:.6f}"),
                    ("avg_win", avg_win, "{:.6f}"),
                    ("avg_loss", avg_loss, "{:.6f}"),
                ]

                # 调用三列格式化函数输出结果，标题为策略类名
                print(format_3col_report(metrics, self.__class__.__name__))

    def _qs_reports(self, dir='Analysis_reports', show=True, **kwargs):
        """
        生成QuantStats详细分析报告（HTML格式）
        包含收益曲线、回撤分析、交易分布等可视化图表，支持本地保存与自动打开

        Args:
            dir (str, optional): 报告保存目录（相对于BASE_DIR）. Defaults to 'Analysis_reports'.
            show (bool, optional): 生成后是否自动用浏览器打开. Defaults to True.
            **kwargs: 扩展参数（预留，供QuantStats报告函数使用）

        核心逻辑：
        1. 检查并创建保存目录（避免目录不存在报错）
        2. 生成报告文件名（策略名+报告名+时间戳，确保唯一性）
        3. 调用QuantStats生成HTML报告（包含完整统计与可视化）
        4. 自动打开报告（基于webbrowser模块）
        """
        import quantstats as qs
        from os import path, mkdir

        # 1. 构建报告保存路径
        file_path = f"{BASE_DIR}/{dir}"
        # 若目录不存在则创建
        if not path.exists(file_path):
            mkdir(file_path)

        # 2. 生成报告文件名（格式：报告名_策略类名.html）
        filename = f"{self._qs_reports_name}_{self.__class__.__name__}.html"
        output = f"{file_path}/{filename}"

        # 3. 打印保存路径提示
        print(f"| Analysis_reports save to: {output}")

        # 4. 生成HTML报告（基于收益率序列，包含完整分析）
        qs.reports.html(
            self._net_worth,  # 收益率序列（核心输入）
            output=output,    # 输出路径
            download_filename=output  # 浏览器下载时的默认文件名
        )

        # 5. 自动打开报告（若show=True）
        if show:
            import webbrowser
            webbrowser.open(output)

    def _reset_op(self):
        """
        参数优化模式下重置策略状态（用于多组参数循环测试）
        避免前一组参数的回测状态影响下一组，确保每组参数独立测试

        重置内容：
        1. 回测索引（_btindex）：重置为-1或最小开始长度-1
        2. 账户状态：重置账户历史、仓位、权益等（从指定索引开始）
        3. 回测结果：清空结果列表，避免数据残留
        """
        # 1. 重置回测索引
        self._btindex = -1
        # 若配置了最小开始长度，索引设为最小长度-1（跳过初始化阶段）
        if self.config.min_start_length > 0:
            strat_index = self.config.min_start_length - 1
            self._btindex = strat_index

        # 2. 重置账户状态（从当前索引+1开始，避免重复计算）
        self._account.reset(self._btindex + 1)

        # 3. 清空回测结果列表
        self._results = []

    def reset(self) -> tuple[np.ndarray, dict]:
        """
        强化学习（RL）环境重置接口（抽象方法，需子类重写）
        用于RL训练/推理时重置环境状态，返回初始观测值与环境信息

        Returns:
            tuple[np.ndarray, dict]: 
                - 初始观测值数组（形状：[state_dim]）
                - 环境信息字典（如初始资金、合约信息等）

        注意：
        子类需根据具体策略逻辑实现，例如：
        1. 重置账户状态（资金、仓位）
        2. 重新加载K线数据
        3. 计算初始观测特征（指标、账户状态）
        """
        ...

    def step(self) -> tuple[np.ndarray, float, bool, bool, dict]:
        """
        策略核心交易逻辑接口（抽象方法，需子类重写）
        回测/实盘模式下逐根K线调用，RL模式下接收动作并执行交易

        Returns:
            tuple[np.ndarray, float, bool, bool, dict]: 
                - 新观测值数组（RL模式返回，非RL模式可忽略）
                - 本次步骤收益（用于RL奖励计算）
                - terminal（是否达到自然终止条件，如数据结束）
                - truncated（是否达到截断条件，如最大回撤）
                - 信息字典（如交易记录、仓位变化等）

        核心职责：
        1. 读取当前K线/指标数据
        2. 执行交易逻辑（开仓/平仓/加仓/减仓）
        3. 计算收益与风险指标
        4. 判断是否终止（回测结束、触发止损等）
        """
        ...

    def start(self) -> None:
        """
        策略初始化钩子（抽象方法，需子类重写）
        在策略__init__初始化后、回测/实盘循环（next/step）前调用

        核心用途：
        1. 初始化指标（如MA、RSI、MACD等）
        2. 设置初始参数（手续费、滑点、止损条件）
        3. 加载历史数据（若未提前加载）
        4. 初始化日志/监控工具

        注意：
        该方法仅调用一次，用于策略启动前的准备工作
        """
        """策略初始化__init__后,在next之前运行"""
        ...

    def stop(self) -> None:
        """
        策略终止钩子（抽象方法，需子类重写）
        在回测结束、实盘停止或异常退出时调用

        核心用途：
        1. 执行收尾操作（如平仓所有仓位、释放资源）
        2. 保存回测结果/模型参数
        3. 生成最终统计报告
        4. 关闭数据库/API连接（若未自动关闭）

        注意：
        该方法确保策略优雅退出，避免资源泄露或数据丢失
        """
        """策略最后运行"""
        ...

    def _close(self) -> None:
        """
        关闭策略依赖的外部连接（API、数据库）
        避免资源泄露，在策略停止后自动调用

        处理对象：
        1. TQSDK API连接（_api）：若存在close方法则调用
        2. SQLite数据库连接（_sqlite）：若存在close方法则调用
        """
        # 关闭TQSDK API连接（实盘模式常用）
        if hasattr(self._api, 'close'):
            self._api.close()
        # 关闭SQLite数据库连接（从数据库获取数据时常用）
        if hasattr(self._sqlite, 'close'):
            self._sqlite.close()

    def _strategy_init(self) -> None:
        """
        策略实际初始化函数（内部调用，可被子类重写）
        用于回测/实盘模式下的动态初始化，支持多次调用（如实盘实时更新）

        核心职责：
        1. 重新计算指标（适应实时数据更新）
        2. 刷新账户状态（实盘模式下同步最新仓位/权益）
        3. 重置临时变量（如交易计数器、止损条件）

        区别于start方法：
        - start：仅调用一次，用于启动前的静态初始化
        - _strategy_init：可多次调用，用于动态更新状态（如实盘每根K线前）
        """
        """策略实际初始化函数"""
        ...

    @property
    def btdatasset(self) -> Union[BtDatasSet[str, BtData], dict[str, BtData]]:
        """
        获取K线数据集合（属性接口）
        返回策略管理的所有BtData对象，支持多合约场景

        Returns:
            Union[BtDatasSet[str, BtData], dict[str, BtData]]: 
                - BtDatasSet：增强型数据集合（支持按名称/索引访问）
                - dict：普通字典（键为合约名，值为BtData对象）
        """
        return self._btdatasset

    @property
    def api(self) -> Optional[TqApi]:
        """
        获取天勤TQApi实例（属性接口）
        仅在实盘模式或从TQSDK获取数据时有效，用于操作TQSDK相关功能

        Returns:
            Optional[TqApi]: TQApi实例（未初始化则返回None）
        """
        """天勤API"""
        return self._api

    @property
    def sid(self) -> int:
        """
        获取策略ID（属性接口）
        用于多策略并行运行时的唯一标识，避免资源冲突

        Returns:
            int: 策略ID（非负整数）
        """
        """策略id"""
        return self._sid

    def __process_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        预处理K线数据（内部方法，供get_data调用）
        整合周期计算、跳空消除、数据截取等功能，确保数据格式统一

        Args:
            data (pd.DataFrame): 原始K线数据（需包含datetime、OHLCV字段）

        Returns:
            pd.DataFrame: 预处理后的标准K线数据

        处理流程：
        1. 计算K线周期（秒）：优先从duration字段获取，否则自动计算
        2. 消除跳空：处理非交易时间导致的价格断层（如期货10:15-10:30休盘）
        3. 数据截取：按配置截取指定长度/时间范围的数据
        4. 时间过滤：按配置过滤指定时间段的数据（如仅保留开盘后1小时）
        """
        col = data.columns

        # 1. 计算K线周期（秒）
        if 'duration' in col:
            # 优先从字段获取周期（已存在则直接使用）
            cycle = int(data.duration.iloc[0])
        else:
            # 自动计算周期：基于时间差的最小值
            time_delta = pd.Series(
                data.datetime).diff().bfill()  # 计算相邻时间差，前向填充首行
            try:
                # 处理numpy datetime64类型（转换为秒）
                cycle = int(min(time_delta.unique().tolist()) / 1e9)
            except:
                # 处理datetime.timedelta类型（提取秒数）
                td = [x.seconds for x in time_delta.unique().tolist()]
                cycle = int(min(td))
            # 添加周期字段到数据
            data['duration'] = cycle

        # 2. 消除跳空（如期货休盘导致的价格断层）
        data = self.__clear_gap(data, cycle)
        # 3. 按长度/比例截取数据（如取后1000根K线）
        data = self.__get_data_segment(data)
        # 4. 按日期范围截取数据（如2023-01-01至2023-12-31）
        data = self.__get_datetime_segment(data)
        # 5. 按每日时间范围过滤数据（如仅保留9:30-11:30）
        data = self.__get_time_segment(data)

        return data

    def __clear_gap(self, data: pd.DataFrame, cycle: int) -> pd.DataFrame:
        """
        消除K线跳空（内部方法，供__process_data调用）
        处理非交易时间导致的价格断层（如期货10:15-10:30休盘），使价格序列连续

        Args:
            data (pd.DataFrame): 原始K线数据
            cycle (int): K线周期（秒）

        Returns:
            pd.DataFrame: 消除跳空后的K线数据

        核心逻辑：
        1. 识别跳空位置：时间差不等于周期且不等于周期+休盘时间（900秒=15分钟）的K线
        2. 计算跳空幅度：跳空K线的开盘价与前一根收盘价的差值
        3. 修正价格：跳空位置后的所有OHLC价格减去跳空幅度，消除断层
        """
        try:
            # 仅当配置开启跳空消除时执行
            if self.config.clear_gap:
                # 1. 计算相邻K线的时间差（处理numpy datetime64类型）
                time_delta = pd.Series(data.datetime.values).diff().bfill()
                # 2. 定义正常时间差列表：周期 + 休盘周期（10:15-10:30休盘900秒）
                cycle_ls = [
                    timedelta(seconds=cycle),
                    timedelta(seconds=900 + cycle)  # 包含休盘的正常时间差
                ]
                # 3. 识别跳空K线索引（时间差不在正常列表中）
                _gap_index = ~time_delta.isin(cycle_ls)
                _gap_index = np.argwhere(
                    _gap_index.values).flatten()  # 转换为索引数组
                _gap_index = np.array(
                    list(filter(lambda x: x > 0, _gap_index)))  # 过滤首行（无前置K线）

                # 4. 若存在跳空，修正价格
                if _gap_index.size > 0:
                    # 计算跳空幅度：跳空K线开盘价 - 前一根收盘价
                    _gap_diff = data.open.values[_gap_index] - \
                        data.close.values[_gap_index - 1]
                    # 修正跳空位置后的所有OHLC价格（减去跳空幅度）
                    for id, ix in enumerate(_gap_index):
                        data.loc[ix:, FILED.OHLC] = data.loc[ix:, FILED.OHLC].apply(
                            lambda x: x - _gap_diff[id]
                        )
        except Exception:
            # 捕获所有异常，避免预处理失败影响后续流程
            pass
        return data

    def __get_data_segment(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        按长度/比例截取K线数据（内部方法，供__process_data调用）
        支持按百分比、固定长度、区间截取，满足回测数据量控制需求

        Args:
            data (pd.DataFrame): 原始K线数据
            segment (Union[float, int, Iterable]): 截取参数（来自config.data_segments）

        Returns:
            pd.DataFrame: 截取后的K线数据

        支持的截取模式：
        1. 浮点数（-1 < segment < 1）：按百分比截取（如0.5=前50%，-0.5=后50%）
        2. 整数（1 < abs(segment) < 数据长度）：按固定长度截取（如1000=前1000根）
        3. 二元组（float/int）：按区间截取（如(0.2,0.8)=中间60%，(100,1000)=第100-1000根）
        """
        segment = self.config.data_segments
        length = data.shape[0]  # 数据总行数

        # 1. 浮点数模式：按百分比截取
        if isinstance(segment, float) and -1. < segment < 1.:
            if segment > 0.:
                # 正数：截取前N%（如0.5=前50%）
                data = data.iloc[:int(length * segment) + 1]
            else:
                # 负数：截取后N%（如-0.5=后50%）
                data = data.iloc[int(length * segment):]
                data.reset_index(drop=True, inplace=True)  # 重置索引

        # 2. 整数模式：按固定长度截取
        elif isinstance(segment, int):
            if 1 < abs(segment) < length:
                if segment > 0:
                    # 正数：截取前N根（如1000=前1000根）
                    data = data.iloc[:segment]
                else:
                    # 负数：截取后N根（如-1000=后1000根）
                    data = data.iloc[segment:]
                    data.reset_index(drop=True, inplace=True)

        # 3. 二元组模式：按区间截取
        elif isinstance(segment, Iterable) and len(segment) == 2:
            # 3.1 百分比区间（如(0.2, 0.8)=中间60%）
            if all([isinstance(s, float) and 0. < s < 1. for s in segment]):
                segment = list(sorted(segment))  # 确保区间有序（start <= stop）
                start = int(length * segment[0])
                stop = int(length * segment[1]) + 1
                data = data.iloc[start:stop]
                data.reset_index(drop=True, inplace=True)
            # 3.2 固定长度区间（如(100, 1000)=第100-1000根）
            elif all([isinstance(s, int) and 0 < s < length for s in segment]):
                segment = list(sorted(segment))
                data = data.iloc[segment[0]:segment[1]]
                data.reset_index(drop=True, inplace=True)

        return data

    def __get_datetime_segment(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        按日期范围截取K线数据（内部方法，供__process_data调用）
        支持按开始/结束日期过滤数据，满足指定时间范围的回测需求

        Args:
            data (pd.DataFrame): 原始K线数据
            start (Union[str, datetime]): 开始日期（来自config.start_time）
            end (Union[str, datetime]): 结束日期（来自config.end_time）

        Returns:
            pd.DataFrame: 按日期过滤后的K线数据

        核心逻辑：
        1. 日期格式统一：将字符串格式转换为datetime类型
        2. 按日期过滤：保留在[start, end]范围内的数据
        3. 重置索引：确保过滤后索引连续
        """
        try:
            # 1. 按开始日期过滤
            start = self.config.start_time
            if start:
                # 统一日期格式（字符串转datetime）
                if not isinstance(start, datetime):
                    start = time_to_datetime(start)
                # 保留>=开始日期的数据
                data = data[data.datetime >= start]
                data.reset_index(drop=True, inplace=True)

            # 2. 按结束日期过滤
            end = self.config.end_time
            if end:
                # 统一日期格式
                if not isinstance(end, datetime):
                    end = time_to_datetime(end)
                # 保留<=结束日期的数据
                data = data[data.datetime <= end]
                data.reset_index(drop=True, inplace=True)
        except Exception:
            # 捕获所有异常，避免日期格式错误影响后续流程
            pass
        return data

    def __get_time_segment(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        按每日时间范围过滤K线数据（内部方法，供__process_data调用）
        支持过滤每日内的指定时间段（如排除午休时间），满足精细化回测需求

        Args:
            data (pd.DataFrame): 原始K线数据
            segment (Iterable): 时间过滤参数（来自config.time_segments）

        Returns:
            pd.DataFrame: 按每日时间过滤后的K线数据

        支持的过滤模式：
        1. 整数二元组列表（如[(10,15), (10,30)]）：排除10:15-10:30的数据
        2. time对象列表（如[time(10,15), time(10,30)]）：同上，格式更明确
        """
        segment = self.config.time_segments
        try:
            # 仅当过滤参数为可迭代对象且长度>=2时执行
            if isinstance(segment, Iterable):
                length = len(segment)
                if length >= 2:
                    # 1. 整数二元组模式（如[(10,15), (10,30)]）
                    if all([isinstance(s, Iterable) and all([isinstance(_s, int) for _s in s]) for s in segment]):
                        # 按每两个元素一组，排除指定时间段
                        for i, j in list(zip(range(0, length, 2), range(1, length, 2))):
                            t1, t2 = segment[i], segment[j]
                            # 转换为time对象（时:分）
                            t1 = time(t1[0], t1[1])
                            t2 = time(t2[0], t2[1])
                            # 提取每日时间（忽略日期和微秒）
                            t = data.datetime.apply(
                                lambda x: x.time().replace(microsecond=0))
                            # 排除[t1, t2)区间的数据
                            data = data[~((t1 <= t) & (t < t2))]
                        data.reset_index(drop=True, inplace=True)

                    # 2. time对象模式（如[time(10,15), time(10,30)]）
                    elif all([isinstance(s, time) for s in segment]):
                        # 逻辑同上，直接使用time对象比较
                        for i, j in list(zip(range(0, length, 2), range(1, length, 2))):
                            t1, t2 = segment[i], segment[j]
                            t = data.datetime.apply(
                                lambda x: x.time().replace(microsecond=0))
                            data = data[~((t1 <= t) & (t < t2))]
                        data.reset_index(drop=True, inplace=True)
        except Exception:
            # 捕获所有异常，避免时间格式错误影响后续流程
            pass
        return data

    @property
    def btindex(self) -> int:
        """
        ### 获取回测当前索引（属性接口）
        表示当前处理到的K线位置，从-1开始（未启动），逐根K线递增

        Returns:
            int: 回测当前索引
        """
        """### 索引"""
        return self._btindex

    @btindex.setter
    def btindex(self, value):
        """
        设置回测索引（累加模式，非直接赋值）
        用于调整回测起始位置，如参数优化时跳过初始化阶段

        Args:
            value (int): 索引增量（如value=10表示当前索引+10）
        """
        self._btindex += value

    @property
    def btdata(self) -> BtData:
        """
        获取默认K线数据（属性接口）
        返回数据集合中的第一个BtData对象，适用于单合约策略

        Returns:
            BtData: 默认K线数据对象
        """
        """### 默认BtData"""
        return self._btdatasset[0]

    @property
    def min_start_length(self) -> int:
        """
        获取最小开始回测长度（属性接口）
        表示策略启动前需要的最小K线数量（用于指标初始化，如MA5需要5根K线）

        Returns:
            int: 最小开始回测长度（非负整数）
        """
        """最小开始回测长度"""
        return self.config.min_start_length

    @min_start_length.setter
    def min_start_length(self, value) -> int:
        """
        设置最小开始回测长度（属性接口）
        同时调整回测起始索引（设为value-1），避免在指标未初始化时执行交易

        Args:
            value (Union[int, float]): 最小开始回测长度（需>=0，自动转换为整数）

        逻辑：
        - 若value>0，回测索引设为value-1（从第value根K线开始执行策略）
        - 仅在非实盘模式下生效（实盘无需提前初始化）
        """
        """最小开始回测长度"""
        if isinstance(value, (int, float)) and value >= 0:
            value = int(value)
            # 更新配置中的最小开始长度
            self.config.min_start_length = value
            # 非实盘模式下调整回测起始索引
            if not self._is_live_trading:
                if value > 0:
                    self._btindex = value - 1

    @property
    def logger(self) -> logging.Logger:
        """
        获取日志记录器（属性接口）
        用于策略运行过程中的日志输出（如交易记录、错误信息）

        Returns:
            logging.Logger: 日志记录器实例
        """
        """信息记录器"""
        return Logger

    @property
    def stats(self) -> Stats:
        """
        获取回测统计分析对象（属性接口）
        包含夏普比率、最大回撤等核心指标的计算与存储

        Returns:
            Stats: 统计分析对象（未初始化则返回None）
        """
        """分析器"""
        return self._stats

    @property
    def qs_plots(self) -> QSPlots:
        """
        获取QuantStats绘图对象（属性接口）
        用于生成收益曲线、回撤曲线等可视化图表

        Returns:
            QSPlots: 绘图对象（未初始化则返回None）
        """
        """qs中的plot"""
        return self._qs_plots

    @property
    def account(self) -> Union[BtAccount, TqAccount]:
        """
        获取账户对象（属性接口）
        回测模式返回BtAccount，实盘模式返回TqAccount，统一封装账户操作

        Returns:
            Union[BtAccount, TqAccount]: 账户对象（未初始化则返回None）
        """
        """账户"""
        return self._account

    @property
    def isplot(self) -> bool:
        """
        获取指标绘图开关（属性接口，预留）
        用于控制所有指标是否显示在图表中，实际逻辑在setter中实现

        Returns:
            bool: 绘图开关状态（True=显示，False=隐藏）
        """
        """是否画图"""
        ...

    @isplot.setter
    def isplot(self, value: bool):
        """
        设置所有指标的绘图开关（属性接口）
        批量控制指标数据集合中所有指标的显示状态，用于快速切换绘图模式

        Args:
            value (bool): 绘图开关状态（True=显示，False=隐藏）
        """
        """是否画图"""
        for _, v in self._btindicatordataset.items():
            v.isplot = bool(value)

    @property
    def plot_name(self) -> str:
        """
        获取图表保存名称（属性接口）
        用于指定策略回测图表的保存文件名（如"MA_strategy_plot"）

        Returns:
            str: 图表保存名称（默认"plot"）
        """
        """图表保存名称"""
        return self._plot_name

    @plot_name.setter
    def plot_name(self, value: str):
        """
        设置图表保存名称（属性接口）
        仅接受非空字符串，确保文件名有效

        Args:
            value (str): 新的图表保存名称
        """
        if isinstance(value, str) and value:
            self._plot_name = value

    @property
    def qs_reports_name(self) -> str:
        """
        获取回测报告名称（属性接口）
        用于指定QuantStats HTML报告的保存文件名（如"MA_strategy_report"）

        Returns:
            str: 回测报告名称（默认"qs_reports"）
        """
        """回测报告名称"""
        return self._qs_reports_name

    @qs_reports_name.setter
    def qs_reports_name(self, value: str):
        """
        设置回测报告名称（属性接口）
        仅接受非空字符串，确保文件名有效

        Args:
            value (str): 新的回测报告名称
        """
        if isinstance(value, str) and value:
            self._qs_reports_name = value

    @property
    def result(self) -> pd.DataFrame:
        """
        获取首个合约的回测结果（属性接口）
        适用于单合约策略，返回第一个Broker的历史数据（含权益、仓位等）

        Returns:
            pd.DataFrame: 首个合约的回测结果
        """
        """回测结果"""
        return self._results[0]

    @property
    def results(self) -> list[pd.DataFrame]:
        """
        获取所有合约的回测结果（属性接口）
        适用于多合约策略，返回每个Broker的历史数据列表

        Returns:
            list[pd.DataFrame]: 回测结果列表（每个元素对应一个合约）
        """
        """回测结果"""
        return self._results

    @property
    def tick_commission(self, value: float) -> list[float]:
        """
        获取所有合约的按tick手续费（属性接口）
        按tick收费模式：每手手续费 = 波动1个tick的价值 × 倍数

        Args:
            value (float): 预留参数（兼容setter格式）

        Returns:
            list[float]: 各合约的tick手续费倍数列表（默认0.0）
        """
        """每手手续费为波动一个点的价值的倍数"""
        return [btdata._broker.commission.get("tick_commission", 0.) for btdata in self._btdatasset.values()]

    @tick_commission.setter
    def tick_commission(self, value: float):
        """
        设置所有合约的按tick手续费（属性接口）
        批量更新所有合约的tick手续费倍数，适用于统一调整手续费

        Args:
            value (Union[int, float]): tick手续费倍数（需>0，自动转换为float）
        """
        if isinstance(value, (float, int)) and value > 0.:
            # 遍历所有合约，更新tick手续费
            [btdata._broker._setcommission(
                dict(tick_commission=float(value))
            ) for btdata in self._btdatasset.values()]

    @property
    def percent_commission(self, value: float) -> list[float]:
        """
        获取所有合约的按比例手续费（属性接口）
        按比例收费模式：每手手续费 = 每手价值 × 百分比（如0.0001=0.01%）

        Args:
            value (float): 预留参数（兼容setter格式）

        Returns:
            list[float]: 各合约的比例手续费列表（默认0.0）
        """
        """每手手续费为每手价值的百分比"""
        return [btdata._broker.cost_percent for btdata in self._btdatasset.values()]

    @percent_commission.setter
    def percent_commission(self, value: float):
        """
        设置所有合约的按比例手续费（属性接口）
        批量更新所有合约的比例手续费，适用于统一调整手续费

        Args:
            value (Union[int, float]): 比例手续费（需>0，自动转换为float）
        """
        if isinstance(value, (float, int)) and value > 0.:
            # 遍历所有合约，更新比例手续费
            [btdata._broker._setcommission(
                dict(percent_commission=float(value))
            ) for btdata in self._btdatasset.values()]

    @property
    def fixed_commission(self) -> list[float]:
        """
        获取所有合约的固定手续费（属性接口）
        固定收费模式：每手手续费为固定金额（如5元/手）

        Returns:
            list[float]: 各合约的固定手续费列表（默认0.0）
        """
        """每手手续费为固定手续费"""
        return [btdata._broker.cost_fixed for btdata in self._btdatasset.values()]

    @fixed_commission.setter
    def fixed_commission(self, value: float):
        """
        设置所有合约的固定手续费（属性接口）
        批量更新所有合约的固定手续费，适用于统一调整手续费

        Args:
            value (Union[int, float]): 固定手续费（需>0，自动转换为float）
        """
        if isinstance(value, (float, int)) and value > 0.:
            # 遍历所有合约，更新固定手续费
            [btdata._broker._setcommission(
                dict(fixed_commission=float(value))
            ) for btdata in self._btdatasset.values()]

    @property
    def slip_point(self) -> float:
        """
        获取所有合约的滑点（属性接口）
        滑点：每次交易的价格偏差（如0.1表示每次交易偏差0.1个tick）

        Returns:
            list[float]: 各合约的滑点列表（默认0.0）
        """
        """每手手续费为固定手续费"""  # 注：原注释有误，实际为滑点
        return [btdata._broker.slip_point for btdata in self._btdatasset.values()]

    @slip_point.setter
    def slip_point(self, value: float):
        """
        设置所有合约的滑点（属性接口）
        批量更新所有合约的滑点，模拟实际交易中的价格偏差

        Args:
            value (Union[int, float]): 滑点（需>=0，自动转换为float）
        """
        if isinstance(value, (float, int)) and value >= 0.:
            # 遍历所有合约，更新滑点
            [btdata._broker._setslippoint(value)
             for btdata in self._btdatasset.values()]

    @property
    def use_close(self) -> bool:
        """
        获取成交价模式（属性接口）
        控制策略执行交易时使用的成交价，影响回测准确性

        Returns:
            bool: 
                - True：使用当前K线收盘价作为成交价（适用于收盘后决策）
                - False：使用下一根K线开盘价作为成交价（适用于盘中实时决策，避免未来函数）
        """
        """是否使用当前交易信号的收盘价作成交价,否为使用下一根K线的开盘价作成交价"""
        return self.config.use_close

    @property
    def key(self) -> str:
        """
        获取行情更新字段（属性接口）
        实盘模式下，用于判断行情是否更新（如"last_price"表示最新价更新时触发）

        Returns:
            str: 行情更新字段名称（来自config.key）
        """
        """行情更新字段"""
        return self.config.key

    @property
    def actor(self) -> Callable:
        """
        获取强化学习（RL）智能体（actor）（属性接口）
        用于RL模式下的动作决策，返回actor网络的前向传播函数

        Returns:
            Callable: actor网络（输入状态，输出动作）
        """
        """第一个合约强化学习模型"""
        return self._actor

    @actor.setter
    def actor(self, value) -> Callable:
        """
        设置强化学习（RL）智能体（actor）（属性接口）
        加载训练好的actor网络，用于RL推理或继续训练

        Args:
            value (Callable): 训练好的actor网络（需兼容输入输出格式）
        """
        """第一个合约强化学习模型"""
        self._actor = value

    @property
    def env(self):
        """
        获取强化学习（RL）环境（属性接口）
        用于RL训练时的环境交互，包含状态转换、奖励计算等逻辑

        Returns:
            Any: RL环境对象（具体类型由子类实现）
        """
        """强化学习事件"""
        return self

    @env.setter
    def env(self, value):
        """
        设置强化学习（RL）环境（属性接口）
        初始化或更新RL环境，用于训练或推理

        Args:
            value (Any): RL环境对象（需实现reset/step接口）
        """
        """强化学习事件"""
        # self._env = value
        pass

    # @property
    # def action(self) -> int:
    #     """当前模型动作"""
    #     return self._action

    # @action.setter
    # def action(self, value) -> None:
    #     """当前模型动作"""
    #     self._action = value

    @property
    def is_changing(self) -> Optional[bool]:
        """
        判断默认合约的K线是否更新（实盘模式专用，属性接口）
        基于TQSDK的is_changing方法，检测最新K线是否有更新

        Returns:
            Optional[bool]: 
                - True：K线已更新
                - False：K线未更新
                - None：非实盘模式或未初始化
        """
        if self._is_live_trading:
            # 检测默认合约的最新K线是否更新（基于config.key字段）
            return self._api.is_changing(
                self._btdatasset.default_btdata._dataset.tq_object.iloc[-1],
                self.config.key
            )

    @property
    def is_last_price_changing(self) -> Optional[bool]:
        """
        判断任意合约的最新价是否更新（实盘模式专用，属性接口）
        检测所有合约的最新价是否有更新，用于触发实盘交易逻辑

        Returns:
            Optional[bool]: 
                - True：至少一个合约最新价更新
                - False：所有合约最新价未更新
                - None：非实盘模式或未初始化
        """
        if self._is_live_trading:
            # 遍历所有合约，检测最新价是否更新
            return any([
                self._api.is_changing(btdata.quote, 'last_price')
                for _, btdata in self._btdatasset.items()
            ])

    @property
    def position(self) -> Union[BtPosition, Position]:
        """第一个合约的仓位对象"""
        return self._btdatasset.default_btdata.position

    @property
    def position(self) -> Union[BtPosition, Position]:
        """
        获取默认合约的仓位对象（属性接口）
        回测模式返回BtPosition，实盘模式返回TQSDK的Position，统一封装仓位操作

        Returns:
            Union[BtPosition, Position]: 默认合约的仓位对象
        """
        """第一个合约的仓位对象"""
        return self._btdatasset.default_btdata.position

    def get_results(self):
        """
        获取回测结果（方法接口，与results属性功能一致）
        兼容旧版代码，返回所有合约的回测结果列表

        Returns:
            list[pd.DataFrame]: 回测结果列表
        """
        return self._results

    def get_btdatasset(self):
        """
        获取K线数据集合（方法接口，与btdatasset属性功能一致）
        兼容旧版代码，返回策略管理的所有BtData对象

        Returns:
            Union[BtDatasSet[str, BtData], dict[str, BtData]]: K线数据集合
        """
        return self._btdatasset

    def get_base_dir(self):
        """
        获取项目基础目录（方法接口）
        返回BASE_DIR常量，用于文件路径拼接（如数据保存、报告生成）

        Returns:
            str: 项目基础目录路径
        """
        return self._base_dir

    def get_plot_datas(self):
        """
        获取绘图数据（方法接口，与_plot_datas属性功能一致）
        返回整理后的绘图数据结构，供前端或绘图工具使用

        Returns:
            list: 绘图数据结构（包含K线、指标、配置等）
        """
        return self._plot_datas

    @property
    def agent(self):
        """
        获取强化学习（RL）智能体类（属性接口）
        返回RL智能体的类对象（如PPO、DQN），用于初始化新的智能体实例

        Returns:
            type: RL智能体类（来自_rl_config.agent_class）
        """
        return self._rl_config.agent_class

    @property
    def env_name(self) -> str:
        """
        获取强化学习（RL）环境名称（属性接口）
        用于标识RL环境，默认为策略类名+Env（如"MaStrategyEnv"）

        Returns:
            str: RL环境名称
        """
        """获取环境名称"""
        return self._env_args.get("env_name")

    @env_name.setter
    def env_name(self, value: str):
        """
        设置强化学习（RL）环境名称（属性接口）
        仅接受字符串类型，用于自定义环境标识

        Args:
            value (str): 新的RL环境名称
        """
        if not isinstance(value, str):
            return
        self._env_args['env_name'] = value

    @property
    def num_envs(self) -> int:
        """
        获取强化学习（RL）环境数量（属性接口）
        用于多环境并行训练，提升训练效率

        Returns:
            int: RL环境数量（默认1）
        """
        """获取环境数量"""
        return self._env_args.get('num_envs', 1)

    @num_envs.setter
    def num_envs(self, value: int):
        """
        设置强化学习（RL）环境数量（属性接口）
        仅接受正整数，用于配置多环境并行训练

        Args:
            value (int): 新的RL环境数量（需>=1）
        """
        """设置环境数量"""
        if not isinstance(value, int) or value < 1:
            return
        self._env_args['num_envs'] = int(value)

    @property
    def max_step(self) -> int:
        """
        获取强化学习（RL）最大步数（属性接口）
        表示每个RL环境的最大迭代步数（如回测数据的K线总数）

        Returns:
            int: RL最大步数（默认1000）
        """
        """获取最大步数"""
        return self._env_args.get('max_step', 1000)

    @max_step.setter
    def max_step(self, value: int):
        """
        设置强化学习（RL）最大步数（属性接口）
        仅接受正整数，用于控制RL训练的迭代次数

        Args:
            value (int): 新的RL最大步数（需>=1）
        """
        """设置最大步数"""
        if not isinstance(value, int) or value < 1:
            return
        self._env_args['max_step'] = int(value)

    @property
    def state_dim(self) -> int:
        """
        获取强化学习（RL）状态维度（属性接口）
        表示RL智能体输入观测值的维度（如指标数量+账户特征数量）

        Returns:
            int: RL状态维度（默认0）
        """
        """获取状态维度"""
        return self._env_args.get('state_dim', 0)

    @state_dim.setter
    def state_dim(self, value: int):
        """
        设置强化学习（RL）状态维度（属性接口）
        仅接受正整数，需与实际观测值维度一致

        Args:
            value (int): 新的RL状态维度（需>=1）
        """
        """设置状态维度"""
        if not isinstance(value, int) or value < 1:
            return
        self._env_args['state_dim'] = int(value)

    @property
    def action_dim(self) -> int:
        """
        获取强化学习（RL）动作维度（属性接口）
        表示RL智能体输出动作的维度（如1=单动作，3=多动作）

        Returns:
            int: RL动作维度（默认0）
        """
        """获取动作维度"""
        return self._env_args.get('action_dim', 0)

    @action_dim.setter
    def action_dim(self, value: int):
        """
        设置强化学习（RL）动作维度（属性接口）
        仅接受正整数，需与实际动作空间一致

        Args:
            value (int): 新的RL动作维度（需>=1）
        """
        """设置动作维度"""
        if not isinstance(value, int) or value < 1:
            return
        self._env_args['action_dim'] = int(value)

    @property
    def if_discrete(self) -> bool:
        """
        获取强化学习（RL）动作空间类型（属性接口）
        区分动作空间是离散还是连续，影响智能体选择（如DQN适用于离散，PPO适用于连续）

        Returns:
            bool: 
                - True：离散动作空间（如0=平仓，1=开多，2=开空）
                - False：连续动作空间（如动作值为仓位比例，-1~1）
        """
        """获取是否离散动作空间"""
        return self._env_args.get('if_discrete', True)

    @if_discrete.setter
    def if_discrete(self, value: bool):
        """
        设置强化学习（RL）动作空间类型（属性接口）
        仅接受布尔值，需与智能体类型匹配

        Args:
            value (bool): 新的动作空间类型（True=离散，False=连续）
        """
        """设置是否离散动作空间"""
        if not isinstance(value, bool):
            return
        self._env_args['if_discrete'] = value

    @property
    def signal_features(self) -> np.ndarray:
        """
        获取强化学习（RL）信号特征（属性接口）
        返回处理后的指标特征数组，用于RL智能体的观测值构建

        Returns:
            np.ndarray: 信号特征数组（形状：[时间步, 特征数]）

        逻辑：
        - 若未初始化，调用get_signal_features生成
        - 已初始化则直接返回，避免重复计算
        """
        """获取信号特征"""
        if self._signal_features is None:
            self.get_signal_features()
        return self._signal_features

    @property
    def train(self) -> Optional[bool]:
        """
        获取强化学习（RL）训练状态（属性接口）
        标识当前是否处于RL训练模式，影响智能体行为（训练=探索，推理=利用）

        Returns:
            Optional[bool]: 
                - True：训练模式
                - False：推理模式
                - None：未初始化RL配置
        """
        """是否训练中"""
        if self._rl_config:
            return self._rl_config.train

    @train.setter
    def train(self, value: bool):
        """
        设置强化学习（RL）训练状态（属性接口）
        切换RL智能体的训练/推理模式，如推理模式下禁用探索

        Args:
            value (bool): 新的训练状态（True=训练，False=推理）
        """
        """设置是否训练中"""
        if self._rl_config is not None:
            self._rl_config.train = bool(value)

    @property
    def rlconfig(self) -> Optional[RlConfig]:
        """
        获取强化学习（RL）配置对象（属性接口）
        返回ElegantRL的Config对象，包含训练参数（如学习率、批量大小）

        Returns:
            Optional[RlConfig]: RL配置对象（未初始化则返回None）
        """
        """获取强化学习配置"""
        return self._rl_config

    @property
    def btindicators(self) -> list[BtIndType]:
        """
        获取所有指标对象（属性接口）
        返回指标数据集合中的所有指标，支持批量操作（如绘图、保存）

        Returns:
            list[BtIndType]: 指标对象列表（Line/series/dataframe）
        """
        return list(self._btindicatordataset.values())

    @property
    def btdatas(self) -> list[BtDataType]:
        """
        获取所有K线数据对象（属性接口）
        返回K线数据集合中的所有BtData对象，支持批量操作（如数据预处理）

        Returns:
            list[BtDataType]: K线数据对象列表
        """
        return list(self._btdatasset.values())

    def augment_shuffle_timesteps(self, n_splits_range: tuple = (2, 4)):
        """ 时序暴力打乱：破坏时间顺序，保留全局统计规律
        操作：
        随机将时间步切割为n_splits_range指定范围内的连续片段（如(2,4)表示2-4个片段），然后随机重排这些片段的顺序。
        更激进：直接随机打乱时间步的顺序（完全破坏时序连续性），但保留每个时间步内的特征关联性。

        参数:
            obs: 时序数据，形状为(window_size, feature_dim)
            n_splits_range: 切割片段数量的范围，格式为(min_split, max_split)，默认(2,4)
            **kwargs: 其他扩展参数

        返回:
            打乱后扁平化的数组，形状为(window_size * feature_dim,)
        """
        self.__check_data_enhancement()
        self._data_enhancement_funcs[0] = partial(
            self._data_enhancement_funcs[0], n_splits_range=n_splits_range)

    def augment_mask_features(self, survival_rate: float = 0.2):
        """ 特征毁灭性屏蔽：保留关键特征的 “幸存者偏差”
        操作：
        随机屏蔽(1-survival_rate)比例的特征（置0），强制保留至少1个特征。

        参数:
            obs: 时序数据，形状为(window_size, feature_dim)
            survival_rate: 保留特征的比例（0-1之间），默认0.2（即保留20%）
            **kwargs: 其他扩展参数

        返回:
            屏蔽后扁平化的数组，形状为(window_size * feature_dim,)
        """
        self.__check_data_enhancement()
        self._data_enhancement_funcs[2] = partial(
            self._data_enhancement_funcs[2], survival_rate=survival_rate)

    def augment_distort_values(self, distort_ratio: float = 0.5,
                               scale_range: tuple = (-3, 3), flip_ratio: float = 0.3):
        """数值极端扭曲：破坏量级，保留相对关系
        操作：
        1. 随机选择distort_ratio比例的特征，乘以10^k（k在scale_range范围内）
        2. 随机选择flip_ratio比例的特征进行符号反转

        参数:
            obs: 时序数据，形状为(window_size, feature_dim)
            distort_ratio: 进行量级扭曲的特征比例（0-1），默认0.5
            scale_range: 缩放因子指数范围，格式为(min_k, max_k)，默认(-3, 3)
            flip_ratio: 进行符号反转的特征比例（0-1），默认0.3
            **kwargs: 其他扩展参数

        返回:
            扭曲后扁平化的数组，形状为(window_size * feature_dim,)
        """
        self.__check_data_enhancement()
        self._data_enhancement_funcs[3] = partial(self._data_enhancement_funcs[3], distort_ratio=distort_ratio,
                                                  scale_range=scale_range, flip_ratio=flip_ratio)

    def augment_cross_contamination(self, history_obs=None,
                                    contaminate_ratio: float = 0.3):
        """跨时间步特征污染：破坏时序关联性，保留特征分布
        操作：
        随机选择contaminate_ratio比例的时间步，替换为历史数据中的随机时间步特征

        参数:
            obs: 时序数据，形状为(window_size, feature_dim)
            history_obs: 历史观测列表（每个元素为扁平化数组），用于抽取污染数据，默认None
            contaminate_ratio: 被污染的时间步比例（0-1），默认0.3
            **kwargs: 其他扩展参数

        返回:
            污染后扁平化的数组，形状为(window_size * feature_dim,)
        """
        self.__check_data_enhancement()
        self._data_enhancement_funcs[4] = partial(self._data_enhancement_funcs[4], history_obs=history_obs,
                                                  contaminate_ratio=contaminate_ratio)

    def augment_collapse_features(self, n_clusters_range: tuple = (3, 5)):
        """特征维度坍缩：破坏特征独立性，保留聚合信息
        操作：
        将特征合并为n_clusters_range范围内的聚合特征，再扩展回原维度
        破坏逻辑：
        量化特征中存在大量冗余（如不同周期的均线指标高度相关），本质规律可能隐藏在特征的聚合关系中（如 “多周期均线同时上涨”）。
        坍缩后仍能识别规律，说明模型学到了抽象的聚合模式。
        参数:
            obs: 时序数据，形状为(window_size, feature_dim)
            n_clusters_range: 聚合聚类数量范围，格式为(min_cluster, max_cluster)，默认(3,5)
            **kwargs: 其他扩展参数

        返回:
            坍缩后扁平化的数组，形状为(window_size * feature_dim,)
        """
        self.__check_data_enhancement()
        self._data_enhancement_funcs[5] = partial(
            self._data_enhancement_funcs[5], n_clusters_range=n_clusters_range)

    def augment_observation(self, n=1, p=0.9, **kwargs):
        """强化学习（RL）观测值数据增强：10%概率特征掩码
        随机屏蔽10%的特征值（置0），用于提升RL模型的鲁棒性，避免过拟合

        Args:
            obs (np.ndarray): 原始观测值数组（形状：[特征数] 或 [时间步, 特征数]）

        Returns:
            np.ndarray: 掩码处理后的观测值数组（与输入形状一致）

        实现逻辑：
        - 生成与输入形状相同的二进制掩码（1的概率90%，0的概率10%）
        - 原始观测值与掩码相乘，实现10%特征随机屏蔽
        """
        self.__check_data_enhancement()
        self._data_enhancement_funcs[6] = partial(
            self._data_enhancement_funcs[6], n=n, p=p)

    def __check_data_enhancement(self):
        if not self._if_data_enhancement:
            from ..data_enhancement import data_enhancement_funcs
            self._data_enhancement_funcs = data_enhancement_funcs
            self._if_data_enhancement = True

    def _process_quant_features(
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
        量化交易特征处理函数，整合归一化、异常值处理、特征变换和降维

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
        from sklearn.preprocessing import (
            StandardScaler, RobustScaler, MinMaxScaler
        )
        from sklearn.decomposition import PCA
        # 复制原始特征避免修改输入
        # X = features.copy().astype(np.float32)
        X = np.column_stack(
            tuple(ind.values for _, ind in self._btindicatordataset.items())).astype(np.float32)
        n_samples, n_features = X.shape

        # --------------------------
        # 1. 缺失值处理（时序插值）
        # --------------------------
        df = pd.DataFrame(X)
        # 线性插值（优先）+ 前后填充（确保无缺失）
        df = df.interpolate(method="linear", limit_direction="both")
        df.fillna(0.0, inplace=True)  # 仍缺失的用0填充
        X = df.values

        # --------------------------
        # 2. 异常值处理
        # --------------------------
        if handle_outliers == "clip":
            # 按特征维度截断极端值（四分位法）
            for col in range(n_features):
                feature = X[:, col]
                q1, q3 = np.percentile(feature, [25, 75])
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr  # 下边界
                upper = q3 + 1.5 * iqr  # 上边界
                X[:, col] = np.clip(feature, lower, upper)
        elif handle_outliers == "mark":
            # 新增异常值标记特征（0=正常，1=异常）
            outlier_masks = []
            for col in range(n_features):
                feature = X[:, col]
                q1, q3 = np.percentile(feature, [25, 75])
                iqr = q3 - q1
                is_outlier = (feature < (q1 - 1.5 * iqr)
                              ) | (feature > (q3 + 1.5 * iqr))
                outlier_masks.append(
                    is_outlier.astype(np.float32).reshape(-1, 1))
            # 拼接原始特征和异常值标记
            X = np.concatenate([X] + outlier_masks, axis=1)
            n_features = X.shape[1]  # 更新特征数

        # --------------------------
        # 3. 特征变换（压缩长尾分布）
        # --------------------------
        if use_log_transform:
            for col in range(n_features):
                feature = X[:, col]
                # 仅对非负特征应用对数变换（避免负数问题）
                if np.min(feature) >= 0:
                    X[:, col] = np.log1p(feature)  # log(1 + x)，避免log(0)

        # --------------------------
        # 4. 特征选择（基于与目标收益率的相关性）
        # --------------------------
        if target_returns is not None:
            # 计算特征与目标收益率的相关性
            corr = np.array([np.corrcoef(X[:, col], target_returns)[
                            0, 1] for col in range(n_features)])
            corr_abs = np.abs(corr)
            # 保留相关性前80%的特征（或至少保留10个特征）
            threshold = np.percentile(corr_abs, 20) if n_features > 10 else 0
            keep_cols = corr_abs >= threshold
            X = X[:, keep_cols]
            n_features = X.shape[1]
            if n_features == 0:  # 避免全部特征被过滤
                X = X.copy()  # 回退到原始特征

        # --------------------------
        # 5. 归一化（核心参数控制）
        # --------------------------
        if normalize_method == "standard":
            scaler = StandardScaler()
            X = scaler.fit_transform(X)
        elif normalize_method == "robust":
            scaler = RobustScaler(quantile_range=(25.0, 75.0))
            X = scaler.fit_transform(X)
        elif normalize_method == "minmax":
            scaler = MinMaxScaler(feature_range=feature_range)
            X = scaler.fit_transform(X)
        elif normalize_method == "rolling":
            # 滚动窗口内标准化（避免未来数据泄露）
            X_rolling = np.zeros_like(X)
            for i in range(n_samples):
                # 窗口范围：[i-rolling_window, i)（不包含当前i，避免未来数据）
                start = max(0, i - rolling_window)
                window = X[start:i]
                if len(window) < 10:  # 窗口样本不足时不标准化
                    X_rolling[i] = X[i]
                else:
                    mean = window.mean(axis=0)
                    std = window.std(axis=0) + 1e-6  # 避免除零
                    X_rolling[i] = (X[i] - mean) / std
            X = X_rolling

        # --------------------------
        # 6. PCA降维（减少冗余）
        # --------------------------
        if pca_n_components < 1.0 or (pca_n_components > 1 and pca_n_components < n_features):
            pca = PCA(n_components=pca_n_components)
            X = pca.fit_transform(X)
        self._signal_features = X
        return X

    @staticmethod
    def get_max_missing_count(*args: tuple[pd.Series, np.ndarray]) -> int:
        """参数必须为np.ndarray或pandas.Series，返回输入中缺失值数量的最大值"""
        if not args:
            return 0
        result = [len(arg[pd.isnull(arg)])
                  for arg in args if isinstance(arg, (pd.Series, np.ndarray))]
        if len(result) == 1:
            return result[0]
        return max(result)
