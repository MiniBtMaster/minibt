# 导入未来特性支持（用于类型注解的延迟评估，避免循环导入问题）
from __future__ import annotations
# 导入核心策略基类（所有自定义策略需继承此类）
from .strategy.strategy import Strategy
# 导入工具类和常量（包含配置、数据处理、类型定义等通用功能）
from .utils import (
    MAX_WORKERS,  # 最大并行工作线程数（多策略回测时限制资源占用）
    Literal,      # 用于类型注解的字面量类型（限制参数取值范围）
    Base,         # 基础工具类（存储全局共享数据/API）
    signature,    # 用于获取函数签名（参数解析用）
    deepcopy,     # 深拷贝（避免多策略间参数共享）
    pd,           # pandas库别名（数据处理核心）
    Iterable,     # 可迭代对象类型注解
    os,           # 操作系统接口（路径、文件操作）
    flatten,      # 列表扁平化工具（处理嵌套数据结构）
    getsourcelines,  # 获取函数源代码行（策略校验用）
    FILED,        # 数据列常量（定义回测数据必须包含的字段，如datetime、open等）
    _time,        # time库别名（计时用）
    get_cycle,    # 从datetime推断K线周期（如1分钟、1小时）
    Addict,       # 增强字典类（支持属性式访问，如dict.key而非dict['key']）
    tq_account,   # 天勤账户数据类型（实盘对接用）
    tq_auth,      # 天勤认证数据类型（实盘登录用）
    TYPE_CHECKING  # 类型检查标记（仅在静态类型检查时生效，不影响运行）
)

# 仅在静态类型检查时导入（避免运行时循环导入）
if TYPE_CHECKING:
    from .strategy.stats import Stats    # 策略性能统计类（含夏普率、最大回撤等指标）
    from .strategy.stats import Stats    # 重复导入修正（原代码冗余，保留以维持兼容性）
    from .strategy.qs_plots import QSPlots  # 策略可视化类（含收益率、回撤图等）
    from .utils import OpConfig, OptunaConfig  # 优化配置类（GA优化/Optuna优化的参数配置）


class Bt:
    """
    轻量级量化回测与实盘框架（minibt）核心类
    核心功能：
    1. 数据管理：手动/自动加载回测数据
    2. 策略管理：加载自定义策略、默认策略
    3. 实盘对接：天勤TqApi实盘/模拟盘连接
    4. 参数优化：支持遗传算法（GA）和贝叶斯优化（Optuna）
    5. 回测执行：单策略/多策略并行回测
    6. 结果分析：Bokeh可视化、QuantStats性能报告

    标准使用流程：
    1. 初始化Bt实例 → 2. 添加数据（adddata）/策略（addstrategy）/实盘API（addTqapi）
    3. （可选）参数优化（optstrategy） → 4. 执行回测/实盘（run） → 5. 结果分析（画图/报告）
    """
    # 错误提示常量（统一管理，便于修改）
    DATAS_ERROR = "传入数据必须为 pandas.DataFrame 类型"  # 数据类型错误提示
    STRATEGY_ERROR = "传入策略必须为 Strategy 基类的子类"  # 策略类型错误提示
    instances: list = []  # 类属性：存储所有Bt实例（用于全局策略自动查找）

    def __init__(self, auto=True, **kwargs) -> None:
        """
        初始化回测框架实例

        Args:
            auto: 是否自动加载全局资源（调试用，生产环境建议手动添加）
                  - True：自动查找全局DataFrame数据和TqApi实例
                  - False：仅手动添加资源
            kwargs: 额外配置参数
                data_dir: 数据存储目录路径（str/None，默认为None）
                quick_live: 快速实盘配置（dict，含'live'键控制是否进入实盘模式）

        初始化核心属性：
        - 运行状态：记录启动时间、回测完成状态、优化模式开关
        - 数据相关：存储回测数据、数据目录
        - 策略相关：存储策略类、策略参数
        - 实盘相关：TqApi实例、实盘模式开关、期货合约字典
        """
        self.__start_time = _time.time()  # 框架启动时间（用于统计耗时）
        self.strategy: list[Strategy] = []  # 存储策略类（未实例化）
        self.__multi_num: int = 1  # 多策略数量标记（默认单策略）
        self.__is_finish: bool = False  # 回测/优化是否完成（初始未完成）
        self.__isoptimize: bool = False  # 是否开启参数优化（初始关闭）
        self.__online: bool = False  # 在线模式标记（预留）
        self._api = None  # 天勤TqApi实例（实盘/模拟盘连接，初始未初始化）
        self.__contracts: list[str] | dict = []  # 期货合约存储（初始空）
        self.__sqlite = None  # SQLite数据库连接（预留，未使用）
        self.__live: bool = False  # 是否进入实盘模式（初始关闭）
        self.__contracts: dict = {}  # 期货合约字典（key：简称，value：全称，实盘用）
        self.__params: list = []  # 策略参数列表（与策略类一一对应）

        # 解析数据目录参数（校验合法性）
        data_dir = kwargs.pop('data_dir', None)
        self.__data_dir: str = data_dir if isinstance(
            data_dir, str) and data_dir else None

        self.__auto = bool(auto)  # 自动加载资源开关
        self.__quick_live = kwargs.pop('quick_live', {})  # 快速实盘配置
        self.__datas: list[pd.DataFrame] = []  # 存储回测数据（DataFrame列表）

        # 自动加载资源（仅当auto=True时执行）
        if self.__auto:
            import gc  # 垃圾回收模块（用于查找全局对象）
            import sys  # 系统模块（用于获取全局变量）
            glos = sys._getframe(1).f_globals  # 获取调用者的全局变量（便于给数据命名）

            # 1. 自动加载回测数据（非实盘模式）
            if (not self.__quick_live) or (self.__quick_live and not self.__quick_live.get('live')):
                # 从全局对象中筛选符合要求的DataFrame（必须包含所有必要字段FILED.ALL）
                data_list = [obj for obj in gc.get_objects()
                             if isinstance(obj, pd.DataFrame) and set(obj.columns).issuperset(FILED.ALL)]
                if data_list:
                    # 给每个DataFrame设置名称（对应全局变量名，便于识别）
                    data_id = [id(data) for data in data_list]
                    for name, obj in glos.items():
                        if id(obj) in data_id:
                            obj.name = name
                    self.__datas = data_list  # 保存自动加载的数据

            # 2. 自动加载TqApi实例（实盘模式）
            if (not self.__quick_live) or (self.__quick_live and self.__quick_live.get('live')):
                from unittest.mock import patch  # 用于重定向stderr（抑制TqSdk日志）
                from io import StringIO  # 内存字符串流（捕获TqSdk的冗余日志）
                # 临时重定向stderr到StringIO，避免TqApi初始化时打印无关日志
                with patch('sys.stderr', new=StringIO()):
                    from tqsdk import TqApi  # 导入天勤API
                # 从全局对象中查找已初始化的TqApi实例
                api = [k for k in gc.get_referrers(
                    TqApi) if k.__class__ == TqApi]
                if api:
                    self._api = api[0]  # 保存TqApi实例
                    self.__live = kwargs.pop('live', False)  # 读取实盘模式开关

    def addTqapi(self, tq_auth: tq_auth, tq_account: tq_account | None = None, live: bool = False) -> None:
        """添加天勤实盘/模拟盘API连接（手动初始化TqApi）
        ---

        Args:
        ----
            tq_auth (_tq): 天勤用户认证信息（含username、password）
            tq_account (_tq, optional): 天勤实盘账户信息（含broker_id、account_id、password）
                                        - 非None：连接实盘账户
                                        - None：连接模拟盘（默认）
            live (bool, optional): 是否启用实盘模式（默认False，即模拟盘）
        """
        from unittest.mock import patch  # 重定向stderr抑制日志
        from io import StringIO
        # 临时重定向stderr到StringIO，避免TqSdk初始化日志污染控制台
        with patch('sys.stderr', new=StringIO()):
            # 导入天勤API相关类（实盘账户、模拟盘、认证）
            from tqsdk import TqApi, TqAuth, TqKq, TqAccount

        # 初始化TqApi（实盘/模拟盘二选一）
        if tq_account is not None:
            # 实盘模式：使用TqAccount初始化（需实盘账户信息）
            self._api = TqApi(
                TqAccount(**tq_account.values),  # 解包实盘账户参数
                auth=TqAuth(**tq_auth.values)     # 解包认证参数
            )
        else:
            # 模拟盘模式：使用TqKq初始化（无需实盘账户）
            self._api = TqApi(
                TqKq(),  # 模拟盘标识
                auth=TqAuth(**tq_auth.values)  # 解包认证参数
            )

    def adddata(self, **kwargs: dict[str, pd.DataFrame]) -> Bt:
        """
        手动添加回测数据（支持多组DataFrame数据）

        Args:
            *args: 可变参数，每个参数必须是pandas.DataFrame
                   要求：DataFrame必须包含FILED.ALL定义的所有必要字段（如datetime、open、high等）

        Returns:
            self: 返回Bt实例，支持链式调用（如bt.adddata(df1).adddata(df2)）

        Raises:
            ValueError: 未传入任何数据时抛出
            TypeError: 传入数据不是DataFrame类型时抛出
        """
        # 校验：至少传入一组数据
        if not kwargs:
            raise ValueError("添加数据失败：未传入任何数据")

        # 校验：每组数据必须是DataFrame类型，符合要求则添加到数据列表
        for name, value in kwargs.items():
            if not isinstance(value, pd.DataFrame):
                raise TypeError(f"{self.DATAS_ERROR}，当前传入类型：{type(value)}")
            value.name = name
            self.__datas.append(value)

        return self

    def addstrategy(self, *args: Strategy, **kwargs: list[dict] | dict) -> Bt:
        """添加策略类（手动加载自定义策略，支持多策略）
        --------------------

        Args:
        -------------
            arg (Strategy): 策略类（必须是Strategy基类的子类，非实例）
            kwargs: 策略参数（list[dict]/dict，与策略类一一对应，用于批量传递参数）

        Returns:
        -------------
            Bt: 返回Bt实例，支持链式调用
        """
        # 断言：必须传入至少一个策略（否则报错）
        assert args, '策略不能为空'
        # 遍历传入的策略，校验是否为Strategy子类，符合要求则添加到策略列表
        for arg in args:
            if issubclass(arg, Strategy):
                self.strategy.append(arg)
        return self

    def __run_cmd(self, cmd_str: str) -> None:
        """
        私有方法：执行系统命令（用于启动实盘画图子进程）
        特性：不显示命令执行时弹出的黑框，命令输出会打印到Python控制台

        param cmd_str: 待执行的系统命令字符串（如"python live_plot.py"）
        """
        from subprocess import Popen, PIPE  # 用于执行外部命令
        # # shell=False：禁用shell解析，避免安全风险（如命令注入）
        Popen(cmd_str, shell=False)
        # try:
        #     # 捕获 stdout 和 stderr
        #     process = Popen(
        #         cmd_str.split(),
        #         stdout=PIPE,
        #         stderr=PIPE,
        #         text=True
        #     )
        #     stdout, stderr = process.communicate()
        #     if stderr:
        #         print(f"画图进程报错：{stderr}")
        #     if stdout:
        #         print(f"画图进程输出：{stdout}")
        # except Exception as e:
        #     print(f"启动画图进程失败：{e}")

    def __tq_real(self, isplot: bool, **kwargs) -> None:
        """私有方法：天勤实盘运行核心逻辑（处理实盘数据更新、策略执行、画图数据推送）"""
        from unittest.mock import patch  # 抑制TqSdk日志
        from io import StringIO
        # 临时重定向stderr，避免TqApi日志污染
        with patch('sys.stderr', new=StringIO()):
            from tqsdk import TqApi  # 导入TqApi（实盘数据交互用）

        # 导入实盘所需工具：数据存储、队列（进程间通信）、深拷贝
        from .utils import storeData, BASE_DIR, loadData
        from queue import Queue
        from copy import deepcopy

        # 断言：必须先登录（初始化TqApi并加载合约），否则无法进入实盘
        # assert self.__contracts, "请登录（先调用addTqapi初始化TqApi）"

        # 解析实盘参数
        black_sytle = kwargs.pop('black_sytle', False)  # 画图是否黑色主题（默认白色）
        plot_width = kwargs.pop('plot_width', None)     # 画图宽度（默认自适应）
        period_milliseconds = kwargs.pop(
            'period_milliseconds', 1000)  # 数据更新频率（默认1000ms）
        params_ls = self.__params  # 策略参数列表

        # 适配策略数量与参数数量（参数不足时复用最后一个策略）
        if params_ls:
            contracts_num = len(params_ls)  # 按参数数量确定策略数量
            _strategy = []
            for j in range(contracts_num):
                try:
                    _s = self.strategy[j]  # 按索引取策略
                except IndexError:
                    _s = self.strategy[-1]  # 参数多过策略时，复用最后一个策略
                # 复制策略类（避免多策略共享状态）
                _strategy.append(_s.cls_copy(_s.__name__))
            self.strategy = _strategy  # 更新策略列表
        else:
            contracts_num = len(self.strategy)  # 按策略数量确定参数数量
            params_ls = []
            # 为每个策略生成默认空参数
            for _ in range(contracts_num):
                params_ls.append([[[]], {}, None])

        # 初始化实盘核心变量
        api: TqApi = self._api  # TqApi实例（实盘连接）
        # _tq_contracts_dict = self.__contracts  # 期货合约字典
        name = [s.__name__ for s in self.strategy]  # 策略名称列表
        # 初始化队列（用于策略进程与画图进程间通信）
        datas_queue = Queue(maxsize=contracts_num)  # 行情数据队列
        trade_queue = Queue(maxsize=contracts_num)  # 交易数据队列
        account_queue = Queue(maxsize=1)            # 账户信息队列
        start: bool = False  # 画图启动标记（确保初始化数据推送后再开始画图）
        init_datas = []      # 策略初始化画图数据
        init_trades = []     # 策略初始化交易数据
        strategys: list[Strategy] = []  # 实例化后的策略列表

        async def core(strategy: Strategy):
            """异步核心函数：监听TqApi数据更新，触发策略交易和数据推送"""
            # 注册TqApi数据更新通知通道
            async with api.register_update_notify() as update_chan:
                # 循环监听数据更新
                async for _ in update_chan:
                    # 策略状态变化时，执行实盘交易逻辑
                    if strategy.is_changing:
                        strategy._live_trading()
                    # 开启画图且价格更新时，推送数据到队列（供画图进程使用）
                    if isplot and start and strategy.is_last_price_changing:
                        source, trade = strategy._update_datas()  # 获取最新行情和交易数据
                        info = strategy._get_account_info()       # 获取最新账户信息
                        sid = strategy._sid                       # 策略ID（区分多策略）
                        # 行情数据队列未满则推送
                        if not datas_queue.full():
                            datas_queue.put([sid, source])
                        # 交易数据队列未满则推送
                        if not trade_queue.full():
                            trade_queue.put([sid, trade])
                        # 账户信息队列未满且有数据则推送
                        if info and not account_queue.full():
                            account_queue.put(info)

        # 若策略包含强化学习（RL），禁用梯度计算（避免显存占用）
        if any([s.rl for s in self.strategy]):
            from torch import no_grad
            no_grad()  # 上下文管理器：禁用PyTorch梯度计算
        # 实例化所有策略并初始化
        for i, s in enumerate(self.strategy):
            # 实例化策略（传入策略ID和画图开关）
            self.strategy[i] = s(_sid=i, _isplot=isplot)
            self.strategy[i]._strategy_per_start()  # 策略启动初始化（加载数据、参数等）
            self.strategy[i]._get_plot_datas()
            init_datas.append(self.strategy[i]._plot_datas)  # 收集初始化画图数据
            init_trades.append(self.strategy[i]._init_trades)  # 收集初始化交易数据
            # RL策略特殊处理：设置环境和 Actor 模型
            if s.rl:
                self.strategy[i]._set_env_actor(
                    *self.__get_actor(self.strategy[i], False))

        # 获取初始账户信息（用于画图初始化）
        account_init_info = self.strategy[0]._get_account_info()

        # 开启实盘画图（isplot=True时）
        if isplot:
            # 解析画图参数（默认使用策略配置的交互策略）
            click_policy = kwargs.pop(
                'click_policy', self.strategy[0].config.click_policy)
            # 定义画图数据存储路径（画图进程从该路径读取数据）
            init_datas_dir = f"{BASE_DIR}/liveplot/init_datas"      # 初始化行情数据路径
            update_datas_dir = f"{BASE_DIR}/liveplot/update_datas"  # 实时行情数据路径
            update_trade_dir = f"{BASE_DIR}/liveplot/trade_datas"   # 实时交易数据路径
            account_info_dir = f"{BASE_DIR}/liveplot/account_info"  # 实时账户信息路径

            # 保存初始化数据（供画图进程启动时加载）
            storeData(init_datas, init_datas_dir)
            storeData(init_trades, update_trade_dir)
            storeData(account_init_info, account_info_dir)

            # 校验并修正画图宽度（限制在800-2400像素，默认1600）
            plot_width = plot_width if isinstance(
                plot_width, int) and 800 <= plot_width <= 2400 else 1600
            # 构建画图命令（启动live_plot.py子进程）
            if plot_width:
                cmds_string = f'python {BASE_DIR}/liveplot/live_plot.py -bs {black_sytle} -pw {plot_width} -pm {period_milliseconds} -cp {click_policy}'
            else:
                cmds_string = f'python {BASE_DIR}/liveplot/live_plot.py -bs {black_sytle} -pm {period_milliseconds} -cp {click_policy}'
            self.__run_cmd(cmds_string)  # 执行命令启动画图进程

        # 提交所有策略的异步任务到TqApi事件循环
        [api.create_task(core(s)) for s in self.strategy]

        # 持续运行：等待TqApi更新并推送数据到画图进程
        while True:
            api.wait_update()  # 阻塞等待TqApi数据更新（实盘核心循环）
            # 推送数据到画图进程（队列满时批量保存，确保数据顺序）
            if isplot:
                # 行情数据队列满：按策略ID排序后保存
                if datas_queue.full():
                    sorted_datas = sorted(
                        [datas_queue.get() for _ in range(contracts_num)], key=lambda x: x[0])
                    storeData(
                        list(map(lambda x: x[1], sorted_datas)), update_datas_dir)
                # 交易数据队列满：按策略ID排序后保存
                if trade_queue.full():
                    sorted_trades = sorted(
                        [trade_queue.get() for _ in range(contracts_num)], key=lambda x: x[0])
                    storeData(
                        list(map(lambda x: x[1], sorted_trades)), update_trade_dir)
                # 账户信息队列满：保存最新账户信息
                if account_queue.full():
                    storeData(account_queue.get(), account_info_dir)
                start = True  # 标记画图进程可开始接收实时数据

    def optstrategy(self, target: Literal['result', 'profit', 'profit_rate', 'adjusted_sortino', 'autocorr_penalty', 'avg_loss', 'avg_return',
                                          'avg_win', 'best', 'cagr', 'calmar', 'common_sense_ratio', 'comp', 'compare', 'compsum', 'conditional_value_at_risk',
                                          'consecutive_losses', 'consecutive_wins', 'cpc_index', 'cvar', 'distribution', 'drawdown_details', 'expected_return',
                                          'expected_shortfall', 'exposure', 'gain_to_pain_ratio', 'geometric_mean', 'ghpr', 'greeks',
                                          'implied_volatility', 'information_ratio', 'kelly_criterion', 'kurtosis', 'max_drawdown',
                                          'monthly_returns', 'omega', 'outlier_loss_ratio', 'outlier_win_ratio', 'outliers', 'payoff_ratio',
                                          'pct_rank', 'profit_factor', 'profit_ratio', 'r2', 'r_squared', 'rar', 'recovery_factor',
                                          'remove_outliers', 'risk_of_ruin', 'risk_return_ratio', 'rolling_greeks', 'rolling_sharpe',
                                          'rolling_sortino', 'rolling_volatility', 'ror', 'serenity_index', 'sharpe', 'skew', 'smart_sharpe',
                                          'smart_sortino', 'sortino', 'tail_ratio', 'to_drawdown_series', 'ulcer_index', 'ulcer_performance_index',
                                          'upi', 'value_at_risk', 'var', 'volatility', 'warn', 'win_loss_ratio', 'win_rate', 'worst'] = 'profit_ratio',
                    weights: float | tuple[float] = 1., opconfig: OpConfig | OptunaConfig | dict | list[dict] = {}, op_method: Literal['ga', 'optuna'] = 'optuna', show_bar=True, skip=False, **kwargs):
        """策略参数优化配置（设置优化目标、方法、参数，不实际执行优化）

        Note:
            kwargs 参数格式说明：
                - 数值范围（带步长）：range(1,10)（1到10步长1）、(10,30,2)（10到30步长2）
                - 固定选项：[3,5,8,13]（仅从列表中选择参数值）
                - 固定值：10（参数不参与优化，固定为该值）

        Args:
            target (str, optional): 优化目标（QuantStats性能指标），默认'profit_ratio'（盈利比）
                                    支持指标列表见函数内注释，部分指标需额外传参（如'compare'需传'benchmark'）
            weights (float | tuple[float], optional): 优化目标权重（默认1.0）
                                                     - 正数：最大化目标（如1.0表示最大化盈利比）
                                                     - 负数：最小化目标（如-1.0表示最小化最大回撤）
                                                     - 元组：多目标优化，权重与target一一对应
            opconfig (OpConfig | dict, optional): 优化配置参数（默认空dict）
                                                  - GA优化：传OpConfig实例或dict
                                                  - Optuna优化：传OptunaConfig实例或dict
            op_method (Literal['ga', 'optuna'], optional): 优化方法（默认'ga'）
                                                           - 'ga'：遗传算法（基于DEAP库）
                                                           - 'optuna'：贝叶斯优化（基于Optuna库）
            show_bar (bool, optional): 是否显示优化进度条（默认True）
            skip: (bool): True/False（是否跳过优化，默认False）
            kwargs: 待优化参数（格式见Note）
        """
        # 跳过优化（通过skip参数控制，用于条件执行）
        if skip:
            return self

        # 保存优化配置（供后续run()方法调用时使用）
        self.__target = target          # 优化目标
        self.__weights = weights        # 目标权重
        self.__opconfig = opconfig      # 优化配置
        self.__op_method = op_method    # 优化方法
        self.__op_show_bar = show_bar    # 进度条开关
        self.__isoptimize = True        # 标记开启优化模式

        # 配置优化结果保存路径（默认./minibt/op_params/）
        self.__op_path = kwargs.pop('path', './minibt/op_params/')
        self.__op_kwargs = kwargs        # 待优化参数列表

        return self

    def __optstrategy(self):
        """私有方法：执行遗传算法（GA）优化策略参数（基于DEAP库）"""
        # 导入GA优化所需库和类
        from deap import creator, base  # DEAP核心：创建适应度和个体类
        from .strategy.optimize import GAOptimizer  # 自定义GA优化器

        # 读取优化配置（从optstrategy()方法保存的属性中获取）
        target, weights, opconfig, kwargs = self.__target, self.__weights, self.__opconfig, self.__op_kwargs

        # 断言：必须传入待优化参数（否则无法进行优化）
        assert isinstance(kwargs, dict) and kwargs, '请设置优化参数（在kwargs中指定）'
        print(f"优化参数为：{kwargs}")  # 打印待优化参数，便于调试

        # 处理优化目标：确保为列表/元组格式（统一多目标处理逻辑）
        if target and isinstance(target, str):
            target = [target,]  # 单目标转列表
        # 断言：目标类型必须是列表/元组，且元素为字符串（QuantStats指标名）
        assert isinstance(target, (list, tuple)), 'target为字符串、列表或元组'
        assert [isinstance(x, str)
                for x in target], 'target元组元素非字符串（必须是QuantStats指标名）'

        # 初始化GA优化器（仅支持单策略优化，取第一个策略和第一个数据集）
        strategy, datas = self.strategy[0], self.__datas[0]
        # 若未传入优化配置，使用默认OpConfig
        if not (isinstance(opconfig, dict) and opconfig):
            from .utils import OpConfig
            opconfig = OpConfig()
        op = GAOptimizer(strategy, datas, target, **opconfig)  # 实例化GA优化器

        # 解析策略参数（获取策略默认参数及键名）
        params = strategy.params
        params_keys = list(params.keys())

        # 遍历待优化参数，添加到GA优化器（区分可变参数/固定参数）
        for key, value in kwargs.items():
            # 仅处理策略已定义的参数（忽略无关参数）
            if key in params_keys:
                # 处理可迭代参数（参与优化的参数，如range、tuple、list）
                if isinstance(value, Iterable):
                    # range类型：转成[start, stop, step]列表
                    if isinstance(value, range):
                        _value = [value.start, value.stop, value.step]
                    # tuple类型：必须是( start, stop, step )格式（3个数值元素）
                    elif isinstance(value, tuple):
                        assert len(
                            value) == 3, '参数个数不足（tuple需为3个元素：start, stop, step）'
                        assert all([isinstance(x, (float, int))
                                   for x in value]), 'tuple元素非数字'
                        _value = value
                    # list类型：固定选项（仅从列表中选择参数值，不进行范围搜索）
                    elif isinstance(value, list):
                        assert value or all(
                            [isinstance(x, (float, int)) for x in value]), 'list元素非数字'
                        op.add_listed_param(key, value)  # 添加固定选项参数
                        continue
                    # 其他可迭代类型：不支持，抛出异常
                    else:
                        raise Exception('参数有误（可迭代参数仅支持range/tuple/list）')
                    # 添加可变参数（范围搜索）
                    op.add_mutable_param(key, *_value)
                    continue
                # 非可迭代参数：固定值（不参与优化）
                op.add_fixed_param(key, value)

        # 补充策略默认参数（未在kwargs中指定的参数，按默认值固定）
        for k, v in params.items():
            if k not in op.mutable_params:  # 仅补充非可变参数
                op.add_fixed_param(k, v)

        # 配置GA适应度函数（单目标/多目标）
        # 1. 单目标优化（权重为单个数值）
        if isinstance(weights, (float, int)):
            assert weights, '权重不能为0（无法判断优化方向）'
            if weights > 0.:  # 正权重：最大化目标（如最大化盈利比）
                weights = (1.,)
                name = "FitnessMax"  # 适应度类名（最大化）
            else:  # 负权重：最小化目标（如最小化最大回撤）
                weights = (-1.,)
                name = "FitnessMin"  # 适应度类名（最小化）
        # 2. 多目标优化（权重为列表/元组）
        else:
            assert isinstance(weights, (list, tuple)
                              ), 'weights为float | tuple[float]（多目标需传元组）'
            assert [isinstance(x, (int, float))
                    for x in weights], 'weights元组元素非数字'
            weights = tuple(weights)
            name = "FitnessCompound"  # 多目标适应度类名

        # 创建DEAP适应度类和个体类
        creator.create(name, base.Fitness, weights=weights)  # 适应度类（关联权重）
        creator.create("Individual", list, fitness=getattr(
            creator, name))  # 个体类（继承list，关联适应度）

        # 启动GA优化
        op.go(weights)
        self.__is_finish = True  # 标记优化完成

    def __optuna(self, strategy_: Strategy, isplot: bool = True) -> dict:
        """私有方法：执行Optuna贝叶斯优化策略参数（支持单目标/多目标）

        Args:
            strategy_: 待优化的策略类（Strategy子类）
            isplot: 是否生成优化结果可视化图表（默认True）

        Returns:
            dict: 最优参数组合（Optuna最佳试验的params）
        """
        import optuna  # 导入Optuna优化库
        # 读取优化配置（从optstrategy()保存的属性中获取）
        target, weights, config, kwargs = self.__target, self.__weights, self.__opconfig, self.__op_kwargs

        # 1. 校验待优化参数（必须为非空字典）
        if not (isinstance(kwargs, dict) and kwargs):
            raise ValueError("请设置有效的优化参数（非空字典）")
        print(f"优化参数为：{kwargs}")  # 打印优化参数，便于调试

        # 2. 处理优化目标（确保为列表/元组，统一多目标逻辑）
        if isinstance(target, str):
            target = [target]  # 单目标转列表
        if not isinstance(target, (list, tuple)):
            raise TypeError("target必须为列表或元组（元素为QuantStats指标名）")
        if not all(isinstance(x, str) for x in target):
            raise TypeError("target的元素必须是字符串（QuantStats指标名）")

        # 3. 处理Optuna配置（拆分优化参数和研究参数）
        optimize_kwargs: dict = {}  # 优化参数（如n_trials、n_jobs）
        study_kwargs: dict = {}     # 研究参数（如sampler、pruner）

        # 若用户传入了opconfig（config为tuple，包含optimize_kwargs和study_kwargs）
        if config and isinstance(config, tuple) and len(config) == 2:
            optimize_kwargs, study_kwargs = config  # 解包用户配置
        else:
            # 未传入则使用默认配置
            from .utils import OptunaConfig
            optimize_kwargs, study_kwargs = OptunaConfig()
        print(optimize_kwargs, study_kwargs)

        # 4. 配置优化运行参数
        optimize_kwargs['show_progress_bar'] = self.__op_show_bar  # 进度条开关
        # 并行工作线程数：'max'表示使用最大支持数（MAX_WORKERS）
        if optimize_kwargs.get('n_jobs') == 'max':
            optimize_kwargs['n_jobs'] = MAX_WORKERS

        # 5. 初始化优化用策略（创建最优策略类，标记为优化模式）
        self.strategy = [strategy_.cls_copy(
            f"best_trial{strategy_.__name__}"),]  # 复制策略类
        name = strategy_.__name__  # 策略名称（用于结果保存）
        # 实例化策略并启动（标记为优化模式，避免实盘逻辑干扰）
        strategy: Strategy = strategy_(_isoptimize=True)._strategy_start()
        # 关闭闲置TqApi连接（避免资源泄漏）
        if hasattr(strategy._api, "close"):
            strategy._api.close()
        # RL策略特殊处理：加载Actor模型
        if strategy.rl:
            self.__get_actor(strategy)

        # 6. 解析待优化参数，生成Optuna采样配置（告诉Optuna如何采样参数）
        params = strategy.params  # 策略默认参数
        params_keys = list(params.keys())  # 策略参数名列表
        trial_params: dict[str, list] = {}  # 存储采样配置（供Optuna使用）
        i = 0  # 参数索引（区分同类型参数，如int0、int1）

        for key, value in kwargs.items():
            # 仅处理策略已定义的参数
            if key in params_keys:
                # 处理可迭代参数（range/tuple/list）
                if isinstance(value, Iterable):
                    _value = None  # 解析后的参数范围
                    # range类型：转成[start, stop, step]
                    if isinstance(value, range):
                        _value = [value.start, value.stop, value.step]
                    # tuple类型：至少2个元素（start, stop，step可选）
                    elif isinstance(value, tuple):
                        assert len(
                            value) >= 2, '参数个数不足（tuple需至少2个元素：start, stop）'
                        assert all([isinstance(x, (float, int))
                                   for x in value]), 'tuple元素非数字'
                        _value = list(value)
                    # list类型：固定选项（categorical参数）
                    elif isinstance(value, list):
                        assert value or all(
                            [isinstance(x, (float, int, bool, str)) for x in value]), 'list元素非数字/布尔/字符串'

                    # 处理数值型参数（int/float，添加到采样配置）
                    if _value:
                        # 校验参数类型一致性（全为int或全为float）
                        assert any([all([isinstance(v, t) for v in _value])
                                   for t in (float, int)])
                        # 用参数类型+索引命名（如int0、float1），便于Optuna识别采样方法
                        param_type_name = _value[0].__class__.__name__
                        trial_params[f"{param_type_name}{i}"] = [key,] + _value
                        i += 1
                    # 处理分类参数（list类型，categorical）
                    else:
                        trial_params.update({'categorical': [key, value,]})

        # 7. 配置Optuna研究方向（单目标/多目标）
        # 单目标优化
        if isinstance(weights, (float, int)):
            assert weights, '权重不能为0（无法判断优化方向）'
            if weights >= 0.:  # 正权重：最大化目标
                study_kwargs['direction'] = "maximize"
                ismax = True
            else:  # 负权重：最小化目标
                study_kwargs['direction'] = "minimize"
                ismax = False
        # 多目标优化
        else:
            assert isinstance(weights, (list, tuple)
                              ), 'weights为float | tuple[float]（多目标需传元组）'
            assert [isinstance(x, (int, float))
                    and x for x in weights], 'weights元组元素非数字或为0'
            # 按权重正负设置每个目标的优化方向（正→max，负→min）
            study_kwargs['directions'] = ["maximize" if x >
                                          0. else "minimize" for x in weights]
            ismax = study_kwargs['directions'][0] == "maximize"

        # 8. 定义Optuna参数采样函数（根据采样配置生成参数组合）
        def get_params(trial):
            # 基于策略默认参数，更新为当前trial的采样值
            for k, v in trial_params.items():
                # 移除参数索引（如int0→int），获取采样方法（suggest_int/suggest_float）
                k_clean = ''.join([x for x in k if not x.isdigit()])
                # 调用Optuna的采样方法生成参数值
                params[v[0]] = getattr(
                    trial, '_'.join(['suggest', k_clean]))(*v)
            return Addict(params)  # 返回增强字典（支持属性式访问）

        # 9. 定义Optuna目标函数（评估单组参数的性能，返回目标值）
        def objective(trial: optuna.Trial):
            # 获取当前trial的参数组合，评估策略性能并返回目标值
            return strategy(get_params(trial), ismax, target)

        # 10. 初始化Optuna研究（配置采样器、剪枝器）
        # 处理采样器/剪枝器（字符串→Optuna类实例，如'samplers.TPESampler'→TPESampler()）
        for k, v in study_kwargs.items():
            if k in ['pruner', 'sampler'] and isinstance(v, str):
                # 从optuna.samplers/optuna.pruners中获取对应类
                module = getattr(optuna, ''.join([k, 's']))
                study_kwargs[k] = getattr(module, v)()

        # 抑制Optuna冗余日志（若配置关闭日志）
        if not study_kwargs.pop('logging', True):
            optuna.logging.set_verbosity(optuna.logging.WARNING)
            optuna.logging.disable_default_handler()
            optuna.logging.disable_propagation()

        # 提取可视化配置（指定生成哪种图表）
        if "optunaplot" in study_kwargs:
            optunaplot = study_kwargs.pop('optunaplot')
        # 创建Optuna研究（Study）：管理所有试验
        study: optuna.Study = optuna.create_study(**study_kwargs)

        # 11. 启动Optuna优化（执行试验）
        study.optimize(objective, **optimize_kwargs)

        # 12. 处理优化结果
        # 按目标值排序最优试验（多目标按值排序，单目标按最优值）
        trials = sorted(study.best_trials, key=lambda t: t.values)
        assert trials, "无优化结果（未生成有效试验）"  # 断言：必须有有效结果
        best_trial = trials[-1]  # 最优试验（最后一个为最优）

        # 打印最优结果信息
        print("Number of finished trials: ", len(study.trials))  # 总试验数
        print("Best trial:")
        print("  Value: ", dict(zip(target, best_trial.values)))  # 最优目标值
        print("  Params: ", best_trial.params)  # 最优参数组合

        # 生成优化结果DataFrame并保存为CSV（便于后续分析）
        df: pd.DataFrame = study.trials_dataframe(
            attrs=('number', 'value', 'params'))
        # 按目标值降序排序（取前10行展示）
        value_cols = [col for col in df.columns if 'value' in col]
        df.sort_values(by=value_cols, ignore_index=True,
                       inplace=True, ascending=False)
        df.to_csv(f'{self.__op_path}optuna_{name}.csv')  # 保存路径
        print(df.head(10))  # 打印前10个最优试验

        # 13. 优化结果可视化：按「单/多目标」动态适配图表和参数
        if isplot:
            # 根据目标数量选择可视化图表
            if len(target) == 1:
                # 单目标优化：支持的图表（选择其一）
                # 可选："plot_optimization_history"（优化历史）、"plot_param_importances"（参数重要性）
                optunaplot = "plot_optimization_history"  # 推荐优先使用这个

                # 为不同图表单独配置参数（避免传递不支持的参数）
                if optunaplot == "plot_optimization_history":
                    # plot_optimization_history仅支持target参数（可选）
                    plot_kwargs = {
                        "target": lambda t: t.values[0]  # 只关注第一个目标值
                    }
                elif optunaplot == "plot_param_importances":
                    # plot_param_importances需要params和target参数
                    plot_kwargs = {
                        "params": params_keys,  # 策略参数列表
                        "target": lambda t: t.values[0]
                    }
                else:
                    plot_kwargs = {}  # 其他图表默认无参数
                plot_func = getattr(optuna.visualization, optunaplot)
                plot_func(study, **plot_kwargs).show()
            else:
                # 多目标优化：仅使用帕累托前沿图
                optunaplot = "plot_pareto_front"
                # 动态传递所有目标值（不硬编码索引）
                # plot_kwargs = {
                #     "targets": lambda t: tuple(t.values),  # 适配任意数量的目标
                #     "target_names": target  # 显示实际目标名称（如["profit", "sharpe"]）
                # }
                plot_kwargs = dict(
                    plot_rank=dict(params=params_keys,
                                   target=lambda t: t.values[0]),  # 参数排名图
                    plot_pareto_front=dict(  # 帕累托前沿图（多目标）
                        targets=lambda t: (t.values[0], t.values[1]),
                        target_names=["Objective 0", "Objective 1"]
                    ),
                    plot_param_importances=dict(  # 参数重要性图
                        target=lambda t: t.values[0], params=params_keys
                    )
                )
                getattr(optuna.visualization, optunaplot)(
                    study, **plot_kwargs.get(optunaplot)).show()

            # 从plot_params中获取当前图表对应的参数（避免参数不匹配）
        # 14. 初始化策略实例管理（重置全局策略实例）
        from .utils import StrategyInstances
        Base._strategy_instances = StrategyInstances()
        # 更新最优策略的参数（供后续回测使用）
        self.strategy[-1].params = Addict(best_trial.params)

        return best_trial.params  # 返回最优参数

    def run(self, isplot=True, isreport: bool = False, **kwargs) -> Bt:
        """策略启动入口（根据当前模式自动执行：实盘/参数优化/回测）
        ---

        ### Args:
        >>> isplot (bool, optional): 回测/实盘是否生成图表. Defaults to True.
            isreport (bool, optional): 是否生成QuantStats回测分析报告. Defaults to False.

        ### Kwargs:
        >>> # 多策略回测参数
            model (str): 多线程库（可选['dask','joblib','sklearn','multiprocessing']）. Defaults to 'joblib'.
            # 图表参数
            trade_signal (bool): 是否显示交易信号（开仓/平仓标记）. Defaults to True.
            black_sytle (bool): 图表是否黑色主题（默认白色）. Defaults to False.
            plot_width (int): 图表宽度（像素，默认全屏）. Defaults to None.
            period_milliseconds (int): 实盘数据更新频率（毫秒）. Defaults to 0.
            open_browser (bool): Jupyter Notebook中是否用浏览器打开图表. Defaults to False.
            save_plot (bool): 是否保存图表文件（HTML格式）. Defaults to True.
            # 账户参数
            print_account (bool): 是否打印账户信息. Defaults to False.

        Returns:
        ---
            Bt: 返回Bt实例，支持链式调用
        """
        # 1. 自动加载策略（若未手动添加策略）
        if not self.strategy:
            from .strategy.strategy import default_strategy  # 导入默认策略
            # 查找所有Strategy子类（包括子类的子类，即自定义策略）
            strategy_list = Strategy.__subclasses__()
            strategy_list += list(flatten([s.__subclasses__()
                                  for s in self.instances]))

            # 扩展策略列表（包含更深层次的子类）
            if strategy_list:
                _sl = [s.__subclasses__() for s in strategy_list]
                strategy_list += list(flatten(_sl))
                # 排除默认策略（优先使用自定义策略）
                if default_strategy in strategy_list:
                    strategy_list.pop(strategy_list.index(default_strategy))
                # 添加找到的自定义策略
                if strategy_list:
                    for s in strategy_list:
                        self.addstrategy(s)

            # 若仍无策略，添加默认策略
            if not self.strategy:
                self.addstrategy(default_strategy)

        # 2. 校验策略数量（必须至少有一个策略）
        num_strategy = len(self.strategy)
        assert num_strategy > 0, '请添加策略（通过addstrategy()或开启auto=True自动加载）'

        # 3. 策略初始化预处理：统一__init__方法（避免子类初始化冲突）
        for s in self.strategy:
            s._strategy_init = s.__init__  # 保存策略原__init__方法（后续恢复）
            s.__init__ = Strategy.__init__  # 临时替换为基类__init__（确保初始化一致性）

        # 4. 全局资源注入（供策略内部访问）
        if self.__datas:
            Base._datas = self.__datas  # 注入回测数据
        if self._api:
            Base._api = self._api        # 注入TqApi实例

        # 5. 传递额外参数到所有策略（如画图开关、账户配置）
        for k, v in kwargs.items():
            [setattr(strategy, k, v) for strategy in self.strategy]

        # 6. 分支1：实盘模式（__live=True时）
        if self.__live:
            assert self._api, "请连接天勤api（先调用addTqapi()初始化）"
            Base._is_live_trading = True  # 标记为实盘模式（供策略内部判断）
            self.__tq_real(isplot, **kwargs)  # 执行实盘逻辑
            return self

        # 7. 分支2：参数优化模式（__isoptimize=True时）
        elif self.__isoptimize:
            # 按优化方法执行（GA/Optuna）
            if self.__op_method == 'optuna':
                self.__optuna(self.strategy[0], isplot)  # Optuna优化（单策略）
            elif self.__op_method == 'ga':
                self.__optstrategy()  # GA优化（单策略）
            # return self

        # 8. 分支3：回测模式（默认分支）
        # 8.1 初始化策略实例（为每个策略分配唯一ID）
        self.strategy = [s(_sid=i) for i, s in enumerate(self.strategy)]

        # 8.2 单策略回测（含RL策略）
        if num_strategy <= 1:
            # 实例化策略并执行回测（调用策略__call__方法）
            self.strategy = [s() for s in self.strategy]
            # RL策略特殊处理：若开启随机策略测试，直接返回（不执行完整回测）
            if self.strategy[0].rl and self.strategy[0]._rl_config.random_policy_test:
                return self

        # 8.3 多策略并行回测（调用__multi_run()方法）
        else:
            # 读取并行库参数（默认joblib）
            parallel_model = kwargs.pop('model', 'joblib')
            self.strategy = self.__multi_run(parallel_model)

        # 9. 回测完成后处理
        self.__is_finish = True  # 标记回测完成

        # 9.1 打印账户信息（若配置开启）
        print_account = kwargs.pop('print_account', False)
        # 遍历所有策略，满足条件则打印账户和策略信息
        [(t.account.print, t.pprint) for t in self.strategy
         if t.config.print_account or print_account]

        # 9.2 生成Bokeh图表（若isplot=True）
        if isplot:
            self.bokeh_plot(**kwargs)

        # 9.3 生成QuantStats分析报告（若isreport=True）
        if isreport:
            self.qs_reports(** kwargs)

        # 9.4 打印回测耗时（若策略配置开启计时）
        if self.strategy[0].config.take_time:
            elapsed_time = round(_time.time() - self.__start_time, 2)
            print(f"耗时：{elapsed_time}秒")

        # 9.5 关闭闲置资源（避免泄漏）
        if hasattr(self._api, 'close'):
            self._api.close()  # 关闭TqApi连接
        if self.__sqlite:
            self.__sqlite.close()  # 关闭SQLite连接（预留）

        return self

    def __multi_run(self, model: str) -> list[Strategy]:
        """私有方法：多策略并行回测（支持4种并行库，按需选择）

        Args:
            model (str): 并行库标识（'dask'/'joblib'/'sklearn'/'multiprocessing'）

        Returns:
            list[Strategy]: 已完成回测的策略实例列表
        """
        scheduler = 'threading'  # 并行调度器（线程模式，避免多进程数据拷贝）
        # 动态调整最大工作线程数（不超过MAX_WORKERS，避免资源耗尽）
        max_workers = min(MAX_WORKERS, len(self.strategy))

        # 按并行库类型执行多策略回测
        if model == 'dask':
            # Dask：适合分布式计算，支持复杂任务依赖
            from dask import delayed, compute
            futures = [delayed(s)() for s in self.strategy]  # 生成延迟任务
            results = list(compute(*futures, scheduler=scheduler))  # 执行任务并获取结果

        elif model == 'joblib':
            # Joblib：轻量级并行，适合简单循环任务（推荐）
            from joblib import Parallel, delayed
            results = list(
                Parallel(n_jobs=max_workers, backend=scheduler)(
                    delayed(s)() for s in self.strategy  # 每个策略作为一个任务
                )
            )

        elif model == 'sklearn':
            # Scikit-learn：适配sklearn生态，适合与机器学习流程结合
            from sklearn.utils import parallel_backend
            from joblib import Parallel, delayed
            # 配置并行后端（线程模式）
            with parallel_backend(scheduler):
                results = list(
                    Parallel(n_jobs=max_workers)(
                        delayed(s)() for s in self.strategy
                    )
                )

        else:
            # 多进程（ThreadPoolExecutor）：适合CPU密集型任务
            from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
            # 初始化线程池
            executor = ThreadPoolExecutor(max_workers=max_workers)
            all_task = [executor.submit(s) for s in self.strategy]  # 提交所有策略任务
            # 等待第一个任务完成（避免同时启动过多线程）
            wait(all_task, return_when=FIRST_COMPLETED)
            # 收集所有任务结果（按完成顺序）
            results: list[Strategy] = []
            for f in as_completed(all_task):
                result = f.result()
                results.append(result)
            executor.shutdown()  # 关闭线程池

        return results

    def bokeh_plot(
            self,
            trade_signal: bool = True,
            filename: str = 'bokeh_plot',
            plot_width: int = None,
            black_sytle: bool = False,
            open_browser: bool = False,
            save_plot: bool = True,
            cwd="./Plots",
            ** kwargs):
        """生成Bokeh交互式图表（展示回测结果：行情、交易信号、账户净值等）
        -------------

        Args:
        -------------
            select (Union[str,int,List[int]], optional): 选择策略（多策略时生效）
                                                         - 'all'：所有策略
                                                         - int：单个策略索引
                                                         - list[int]：多个策略索引
                                                         Defaults to 'all'.
            filename (str, optional): 图表保存文件名（不含后缀，默认'bokeh_plot'）. Defaults to ''.
            plot_width (int, optional): 图表宽度（像素，默认1500）. Defaults to 1500.
            black_sytle (bool, optional): 图表是否黑色主题（默认白色）. Defaults to True.
            notebook_handle (bool, optional): Jupyter Notebook中是否返回图表句柄. Defaults to False.
            open_browser (bool, optional): 是否在浏览器中打开图表（默认False）. Defaults to False.

        Returns:
            (List[List[DataFrame]] | list[DataFrame] | None): 返回回测结果DataFrame（行情、交易等数据）
        """
        # 导入Bokeh绘图函数（避免循环导入，延迟导入）
        from .strategy.bokeh_plot import plot
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[0].logger.warning('策略尚未回测（请先调用run()执行回测）')

        # 调用绘图函数生成图表
        tabs = plot(self.strategy, trade_signal, filename, plot_width,
                    black_sytle, open_browser, save_plot, cwd, **kwargs)

        return self

    def qs_reports(self, select: int | str | list[int] = 'all', **kwargs):
        """生成QuantStats回测分析报告（含性能指标、风险指标、可视化图表）
        -------------

        Args:
        -------------
            select (Union[int,str,List[int]], optional): 选择策略（多策略时生效）
                                                         - 'all'：所有策略
                                                         - int：单个策略索引
                                                         - list[int]：多个策略索引
                                                         Defaults to 'all'.
        """
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[select].logger.warning('策略尚未回测（请先调用run()执行回测）')

        # 处理策略选择：统一为列表格式
        select_list = select if isinstance(select, list) else [select,]
        # 为选中的策略生成报告
        for i, t in enumerate(self.strategy):
            if 'all' in select_list or i in select_list:
                t._qs_reports(**kwargs)

        return self

    def get_results(self, select: int | str | list[int] = 'all') -> list[list[pd.DataFrame]]:
        """获取回测结果数据（DataFrame格式，含行情、交易、账户净值等）
        -------------"""
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[select].logger.warning('策略尚未回测（请先调用run()执行回测）')

        # 处理策略选择：统一为列表格式
        select_list = select if isinstance(select, list) else [select,]
        # 返回选中策略的回测结果（每个策略对应一个DataFrame列表）
        return [t.get_results() for i, t in enumerate(self.strategy)
                if 'all' in select_list or i in select_list]

    def qs_stats(self, select: int = 0) -> Stats:
        """获取QuantStats性能统计对象（支持调用多种性能/风险指标方法）
        ------------

        Method:
        ------------
            支持的指标方法包括（部分）：
            - 收益类：profit_ratio（盈利比）、cagr（年化收益率）、avg_return（平均收益率）
            - 风险类：max_drawdown（最大回撤）、volatility（波动率）、var（风险价值）
            - 风险收益比：sharpe（夏普率）、sortino（索提诺率）、calmar（卡玛率）
            - 其他：win_rate（胜率）、consecutive_wins（最大连续盈利次数）、drawdown_details（回撤详情）

        Args:
        ------------
            select (int, optional): 策略索引（多策略时选择，默认0）. Defaults to 0.

        Returns:
        ------------
            Stats: QuantStats统计对象（可调用上述指标方法）
        """
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[select].logger.warning('策略尚未回测（请先调用run()执行回测）')

        # 校验策略索引合法性（超出范围时默认取0）
        select = select if isinstance(
            select, int) and 0 <= select < self.__multi_num else 0
        # 返回选中策略的Stats对象
        return self.strategy[select]._stats

    def qs_plot(self, select: int = 0) -> QSPlots:
        """获取QuantStats可视化对象（支持绘制多种回测结果图表）
        ------------

        Method:
        ------------
            支持的绘图方法包括（部分）：
            - returns（收益率曲线）、drawdown（回撤曲线）、histogram（收益率分布直方图）
            - monthly_heatmap（月度收益热力图）、rolling_sharpe（滚动夏普率）
            - yearly_returns（年度收益率）、distribution（收益分布）

        Args:
        ------------
            select (int, optional): 策略索引（多策略时选择，默认0）. Defaults to 0.

        Returns:
        ------------
            QSPlots: QuantStats可视化对象（可调用上述绘图方法）
        """
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[select].logger.warning('策略尚未回测（请先调用run()执行回测）')

        # 校验策略索引合法性（超出范围时默认取0）
        select = select if isinstance(
            select, int) and 0 <= select < self.__multi_num else 0
        # 返回选中策略的QSPlots对象
        return self.strategy[select]._qs_plots

    def qs_metrics(self, benchmark=None, rf=0., display=True,
                   mode='basic', sep=False, compounded=True,
                   periods_per_year=252, prepare_returns=True,
                   match_dates=False, **kwargs):
        """生成QuantStats指标报告（仅数值指标，无图表）
        包括收益率、风险、风险收益比等核心指标"""
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[0].logger.warning('策略尚未回测（请先调用run()执行回测）')

        from quantstats.reports import metrics  # 导入QuantStats指标报告函数
        # 为所有策略生成指标报告
        [metrics(t._net_worth, benchmark, rf, display, mode, sep, compounded, periods_per_year,
                 prepare_returns, match_dates, **kwargs) for t in self.strategy]
        return self

    def qs_plots(self, benchmark=None, grayscale=False, figsize=(8, 5), mode='basic', compounded=True,
                 periods_per_year=252, prepare_returns=True, match_dates=False):
        """生成QuantStats可视化报告（仅图表，无数值指标）
        包括收益率曲线、回撤曲线、收益分布等图表"""
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[0].logger.warning('策略尚未回测（请先调用run()执行回测）')

        from quantstats.reports import plots  # 导入QuantStats绘图报告函数
        # 为所有策略生成可视化报告
        [plots(t._net_worth, benchmark, grayscale, figsize, mode, compounded,
               periods_per_year, prepare_returns, match_dates) for t in self.strategy]
        return self

    def qs_basic(self, benchmark=None, rf=0., grayscale=False,
                 figsize=(8, 5), display=True, compounded=True,
                 periods_per_year=252, match_dates=False):
        """生成QuantStats基础报告（简化版，含核心指标和关键图表）"""
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[0].logger.warning('策略尚未回测（请先调用run()执行回测）')

        from quantstats.reports import basic  # 导入QuantStats基础报告函数
        # 为所有策略生成基础报告
        [basic(t._net_worth, benchmark, rf, grayscale, figsize, display, compounded,
               periods_per_year, match_dates) for t in self.strategy]
        return self

    def qs_full(self, benchmark=None, rf=0., grayscale=False,
                figsize=(8, 5), display=True, compounded=True,
                periods_per_year=252, match_dates=False):
        """生成QuantStats完整报告（详细版，含所有指标、图表、分析结论）"""
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[0].logger.warning('策略尚未回测（请先调用run()执行回测）')

        from quantstats.reports import full  # 导入QuantStats完整报告函数
        # 为所有策略生成完整报告
        [full(t._net_worth, benchmark, rf, grayscale, figsize, display, compounded,
              periods_per_year, match_dates) for t in self.strategy]
        return self

    def qs_html(self, benchmark=None, rf=0., grayscale=False,
                title='Strategy Tearsheet', output=None, compounded=True,
                periods_per_year=252, download_filename='quantstats-tearsheet.html',
                figfmt='svg', template_path=None, match_dates=False, **kwargs):
        """生成HTML格式QuantStats报告（可在浏览器打开/保存，支持分享）"""
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[0].logger.warning('策略尚未回测（请先调用run()执行回测）')

        from quantstats.reports import html  # 导入QuantStats HTML报告函数
        # 为所有策略生成HTML报告
        [html(t._net_worth, benchmark, rf, grayscale, title, output, compounded, periods_per_year,
              download_filename, figfmt, template_path, match_dates, **kwargs) for t in self.strategy]
        return self

    def qs_iDisplay(self, *objs, include=None, exclude=None, metadata=None, transient=None, display_id=None, **kwargs):
        """Jupyter Notebook中交互式显示QuantStats报告（支持动态更新）"""
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[0].logger.warning('策略尚未回测（请先调用run()执行回测）')

        from quantstats.reports import iDisplay  # 导入交互式显示函数
        # 为所有策略生成交互式报告
        [iDisplay(*objs, include, exclude, metadata, transient,
                  display_id, **kwargs) for t in self.strategy]
        return self

    def qs_iHTML(self, data=None, url=None, filename=None, metadata=None):
        """Jupyter Notebook中显示HTML格式QuantStats报告（支持本地/远程HTML）"""
        # 校验：回测未完成时，打印警告并返回
        if not self.__is_finish:
            return self.strategy[0].logger.warning('策略尚未回测（请先调用run()执行回测）')

        from quantstats.reports import iHTML  # 导入HTML交互式显示函数
        # 为所有策略显示HTML报告
        [iHTML(data, url, filename, metadata) for t in self.strategy]
        return self

    # def get_main_program_path(self):
    #     # 预留方法：获取主程序路径（未使用，保留代码供扩展）
    #     import inspect
    #     stack = inspect.stack()
    #     try:
    #         # 从调用栈底部查找主模块（__name__ == '__main__'）
    #         for frame_info in reversed(stack):
    #             if frame_info.frame.f_globals.get('__name__') == '__main__':
    #                 return os.path.abspath(frame_info.filename)
    #         return None  # 未找到主模块
    #     finally:
    #         del stack  # 释放栈引用，避免内存泄漏


# 独立评估函数：多进程回测时用于策略实例化和评估（供并行库调用）
def evaluate_fitness_parallel(args):
    """
    多进程回测的策略评估函数（接收策略类和索引，返回实例化后的策略）

    Args:
        args: 元组（策略类，策略索引）
              - 策略类：未实例化的Strategy子类
              - 策略索引：用于区分多策略的唯一ID（_sid）

    Returns:
        Strategy: 已实例化的策略对象（已完成回测）
    """
    strategy, index = args
    return strategy(_sid=index)  # 实例化策略（传入索引，执行回测）
