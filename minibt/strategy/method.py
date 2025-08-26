from ..utils import (
    TqApi, np, datetime, Union, Optional, pd, logging,
    BtAccount, TqAccount, BtPosition, Position,
    Quote, Quotes, TargetPosTask, Actions, Callable,
    Any, deepcopy, cachedmethod, attrgetter, TYPE_CHECKING,
    BtDatasSet, BtIndicatorDataSet
)
from .stats import Stats
from .qs_plots import QSPlots
from abc import abstractmethod

from ..indicators import Line, series, dataframe, BtData


class Attr:
    """初始属性"""
    # _datas: list[BtData] = []  # 合约数据集BtData
    # _klines: list[pd.DataFrame] = []  # K线数据集DataFrame
    # _raw_klines: list[pd.DataFrame] = []  # 原始数据集DataFrame
    _results: list[pd.DataFrame] = []  # 回测结果
    # # _position: Union[Positions, Position] = None
    # _positions: list[Union[BtPosition, Position]] = []  # 合约仓位集
    # _quotes: list[Union[Quote, Quotes]] = []
    # _target_pos_tasks: list[TargetPosTask] = []
    # _datas_lengthes: list[int] = []  # 合约数据长度集
    # _cycles: list[int] = []  # 合约周期集
    # _symbols: list[str] = []  # 合约名称
    # _price_ticks: list[float] = []  # 合约最小变动单位
    # _volume_multiples: list[float] = []  # 合约乘数
    # _margin_rates: list[float] = []  # 合约保证金率
    # _tick_values: list[float] = []  # 合约最小变动单位价值
    # _date_indexs: list[pd.Series] = []  # 时间索引，用于报告分析
    # _ind_names: list[str] = []
    _btindex: int = -1  # 索引
    _isinit: bool = False  # 策略初始化状态
    _isplot: bool = True  # 是否画图
    _plot_name: str = 'plot'  # 图表保存名称
    _qs_reports_name: str = "qs_reports"  # 回测报告名称
    _base_dir: str = None  # 文件夹地址
    _datas_num: int = 0
    # _current_close: np.ndarray = None
    # _current_datetime: np.ndarray = None
    # _sid: int = 0
    _max_datas_length: int = 0
    _clear_gap: bool = True
    _data_segments: list[float, list[float]] = []
    _datetime_segments: list[datetime] = []
    # _index: int = -1

    _min_start_length: int = 0
    _plot_datas: list = []
    _init_trades: list = []
    _take_time: bool = True
    _is_logger: bool = False
    _net_worth: Optional[pd.Series] = None
    _stats: Optional[Stats] = None
    _qs_plots: Optional[QSPlots] = None
    _account: Union[BtAccount, TqAccount] = None
    _comm_dictes: list[dict[str, float]] = [{},]
    _value: float = 100, 000.  # 权益
    _start_value: float = 0.  # 初始权益
    _is_log: bool = False  # 数据是否对数化
    _is_daytrader: bool = True  # 是否日内交易，即尾盘离场
    _print_account: bool = True  # 回测完后是否打印账户信息
    _btind_ha: list[bool] = []
    _contracts: dict = {}
    _use_close: bool = True
    _tq_params_ls: list = []
    _tq_params: list = []
    _key: str = 'datetime'
    _web_gui: bool = False
    _last_data_indexs: list[int] = []
    _positions_dict: dict[str, Union[BtPosition, Position]] = {}
    _userwarning: bool = True
    _sqlite = None
    _if_not_data: bool = False
    _resample_dict: dict[str, int] = {}
    _abc: bool = False
    _profit_plot: bool = True
    _click_policy: str = "mute"
    _trading_mode: str = "on_close"
    _auto_data_conver: bool = False
    # rl
    _actor: Optional[Callable] = None  # 模型
    _env: Optional[Any] = None  # 事件
    _action: Union[Actions, int] = 0  # 动作
    _overlap: bool = True  # 强化学习中特征数据如果是主图的，则返回的是差值
    _rl_ind_list: list[str] = []  # 指标列表
    _rl_params_list: list[dict] = []  # 指标参数列表
    _prices: np.ndarray = None  # 收盘价
    _signal_features: np.ndarray = None  # 特征集
    _cutout: float = 0.
    _scrambling: float = 0.
    _scroll: int = 0
    _slip_points: list[float] = []
    _breakout_factor: float = 1.
    _signal_window: int = 1  # 特征维度
    _max_times: int = 3  # 最大惩罚或奖励倍数
    _expected_hoding_days: int = 10  # 期望持仓天数
    _min_expected_hoding_days: int = 1  # 最小期望持仓天数
    _expected_flat_days: int = 10  # 期望平仓天数
    # _comm_dict: dict = {'fixed': 1.}
    _rwf: float = 3.0  # 奖励权重，越新的数据权重越大
    _in_eins: bool = True  # 奖励是否归一化
    _init_account_features = np.array([0., 0.], dtype=np.float32)
    _commission: float = 1.
    _init_gap: bool = True
    _stub: int = 3
    _gap_index: np.ndarray = None
    _gap_diff: np.ndarray = None
    _isstop: bool = False
    _isop: bool = False
    # is_live_trading: bool = False  # 是否为真正交易


class _Attr(type):
    """实例属性"""
    def __new__(cls, name, bases, attrs):
        for k, v in Attr.__dict__.items():
            if not k.startswith('__'):
                attrs[k] = deepcopy(v)
        return type.__new__(cls, name, bases, attrs)


class Method(Attr, metaclass=_Attr):
    # _strategy_init: Callable
    _btdata: BtData
    _btindex: int
    _sid: int
    _api: TqApi
    _current_close: np.ndarray
    _current_datetime: np.ndarray
    _custom_ind_name: dict
    _btdatasset: Union[BtDatasSet[str, BtData], dict[str, BtData]]
    _btindicatordataset: Union[BtIndicatorDataSet[str, BtData],
                               dict[str, Union[Line, series, dataframe]]]
    _account: BtAccount
    _isop: bool
    _btindex: int
    _isinit: bool
    # _btindex: int = -1  # 索引
    # _isinit: bool = False  # 策略初始化状态
    _isstop: bool
    # is_live_trading: bool
    tq: bool
    is_live_trading: bool

    @abstractmethod
    def next(self) -> None:
        """交易逻辑"""
        raise ModuleNotFoundError('请定义next方法')

    def start(self) -> None:
        """策略初始化__init__后,在next之前运行"""
        ...

    def stop(self) -> None:
        """策略最后运行"""

    def _stop(self) -> None:
        if hasattr(self._api, 'close'):
            self._api.close()
        if hasattr(self._sqlite, 'close'):
            self._sqlite.close()

    def _strategy_init(self) -> None:
        """策略实际初始化函数"""
        ...

    @property
    def btdatasset(self) -> Union[BtDatasSet[str, BtData], dict[str, BtData]]:
        return self._btdatasset

    @property
    def api(self) -> Optional[TqApi]:
        """天勤API"""
        return self._api

    @property
    def datas_num(self) -> int:
        """数据个数"""
        return self._btdatasset.num

    # @property
    # def current_close(self) -> np.ndarray:
    #     """收盘价ndarray"""
    #     return self._current_close

    @property
    def sid(self) -> int:
        """策略id"""
        return self._sid

    @property
    def max_datas_length(self) -> int:
        """最大数据长度"""
        return self._btdatasset.max_length

    @property
    def clear_gap(self) -> bool:
        """是否清除跳空"""
        return self._clear_gap

    @property
    def data_segment(self) -> Union[float, list[float]]:
        """数据分段"""
        return self._data_segments[0]

    @property
    def data_segments(self) -> list[float, list[float]]:
        """数据分段"""
        return self._data_segments

    @property
    def datetime_segments(self) -> list[datetime]:
        """排除的时间段"""
        return self._datetime_segments

    @property
    def btindex(self) -> int:
        """索引"""
        return self._btindex

    @property
    def init(self) -> bool:
        """策略是否已初始化"""
        return self._init_

    @property
    def min_start_length(self) -> int:
        """最小开始回测长度"""
        return self._min_start_length

    @min_start_length.setter
    def min_start_length(self, value) -> int:
        """最小开始回测长度"""
        if isinstance(value, int) and value >= 0:
            self._min_start_length = value

    @property
    def plot_datas(self) -> list:
        """图表初始化数据集"""
        return self._plot_datas

    @property
    def init_trades(self) -> list:
        """初始化交易数据"""
        return self._init_trades

    @property
    def take_time(self) -> bool:
        """是否计算回测耗时"""
        return self._take_time

    @property
    def is_logger(self) -> bool:
        """是否输出交易信息"""
        return self._is_logger

    @property
    def logger(self) -> logging.Logger:
        """信息记录器"""
        return self._logger

    @property
    def net_worth(self) -> pd.Series:
        """profit.pct_change()"""
        return self._net_worth

    @property
    def stats(self) -> Stats:
        """分析器"""
        return self._stats

    @property
    def qs_plots(self) -> QSPlots:
        """qs中的plot"""
        return self._qs_plots

    @property
    def account(self) -> Union[BtAccount, TqAccount]:
        """账户"""
        return self._account

    @property
    def comm_dict(self) -> dict[str, float]:
        """手续费字典"""
        return self._comm_dictes[0]

    @property
    def comm_dictes(self) -> list[dict[str, float]]:
        """手续费字典"""
        return self._comm_dictes

    @property
    def value(self) -> float:
        """当前价值"""
        return self._get_value(self.index)

    # @cachedmethod(attrgetter('_cache'))
    def _get_value(self, index: int):
        return self._account.balance

    @property
    def start_value(self) -> float:
        """初始权益"""
        return self._start_value

    @property
    def is_log(self) -> bool:
        """数据是否对数化"""
        return self._is_log

    @property
    def is_daytrader(self) -> bool:
        """是否日内交易，即尾盘离场"""
        return self._is_daytrader

    @property
    def print_account(self) -> bool:
        """回测完后是否打印账户信息"""
        return self._print_account

    @property
    def contracts(self) -> dict:
        """交易所合约信息"""
        return self._contracts

    @property
    def raw_klines(self) -> list[pd.DataFrame]:
        """原始数据集DataFrame"""
        return self._raw_klines

    @property
    def isplot(self) -> bool:
        """是否画图"""
        return self._isplot

    @property
    def plot_name(self) -> str:
        """图表保存名称"""
        return self._plot_name

    @property
    def qs_reports_name(self) -> str:
        """回测报告名称"""
        return self._qs_reports_name

    @property
    def base_dir(self) -> str:
        """文件夹地址"""
        return self._base_dir

    @property
    def result(self) -> pd.DataFrame:
        """回测结果"""
        return self._results[0]

    @property
    def results(self) -> list[pd.DataFrame]:
        """回测结果"""
        return self._results

    @property
    def tick_commission(self, value: float) -> list[float]:
        """每手手续费为波动一个点的价值的倍数"""
        return [btdata._broker.commission.get("tick_commission", 0.) for btdata in self._btdatasset.values()]

    @tick_commission.setter
    def tick_commission(self, value: float):
        if isinstance(value, (float, int)) and value > 0.:
            [btdata._broker._setcommission(
                dict(tick_commission=float(value))) for btdata in self._btdatasset.values()]

    @property
    def percent_commission(self, value: float) -> list[float]:
        """每手手续费为每手价值的百分比"""
        return [btdata._broker.cost_percent for btdata in self._btdatasset.values()]

    @percent_commission.setter
    def percent_commission(self, value: float):
        if isinstance(value, (float, int)) and value > 0.:
            [btdata._broker._setcommission(
                dict(percent_commission=float(value))) for btdata in self._btdatasset.values()]

    @property
    def fixed_commission(self) -> list[float]:
        """每手手续费为固定手续费"""
        return [btdata._broker.cost_fixed for btdata in self._btdatasset.values()]

    @fixed_commission.setter
    def fixed_commission(self, value: float):
        if isinstance(value, (float, int)) and value > 0.:
            [btdata._broker._setcommission(
                dict(fixed_commission=float(value))) for btdata in self._btdatasset.values()]

    @property
    def slip_point(self) -> float:
        """每手手续费为固定手续费"""
        return [btdata._broker.slip_point for btdata in self._btdatasset.values()]

    @slip_point.setter
    def slip_point(self, value: float):
        if isinstance(value, (float, int)) and value >= 0.:
            [btdata._broker._setslippoint(value)
             for btdata in self._btdatasset.values()]

    # @property
    # def data_length(self) -> int:
    #     """第一个合约数据长度"""
    #     return self._datas_lengthes[0]

    # @property
    # def datas_lengthes(self) -> list[int]:
    #     """合约数据长度集"""
    #     return self._datas_lengthes

    # @property
    # def cycle(self) -> int:
    #     """合约周期集"""
    #     return self._cycles[0]

    # @property
    # def cycles(self) -> list[int]:
    #     """合约周期集"""
    #     return self._cycles

    # @property
    # def symbol(self) -> str:
    #     """第一个合约名称"""
    #     return self._symbols[0]

    # @property
    # def symbols(self) -> list[str]:
    #     """合约名称集"""
    #     return self._symbols

    # @property
    # def price_tick(self) -> float:
    #     """第一个合约最小变动单位"""
    #     return self._price_ticks[0]

    # @property
    # def price_ticks(self) -> list[float]:
    #     """合约最小变动单位集"""
    #     return self._price_ticks

    # @property
    # def volume_multiple(self) -> float:
    #     """第一个合约乘数"""
    #     return self._volume_multiples[0]

    # @property
    # def volume_multiples(self) -> list[float]:
    #     """合约乘数集"""
    #     return self._volume_multiples

    # @property
    # def margin_rate(self) -> float:
    #     """第一个合约保证金率"""
    #     return self._margin_rates[0]

    # @property
    # def margin_rates(self) -> list[float]:
    #     """合约保证金率集"""
    #     return self._margin_rates

    # @property
    # def tick_value(self) -> float:
    #     """第一个合约最小变动单位的价值"""
    #     return self._tick_values[0]

    # @property
    # def tick_values(self) -> list[float]:
    #     """合约最小变动单位价值集"""
    #     return self._tick_values

    # @property
    # def date_index(self) -> pd.Series:
    #     """第一个合约时间索引，用于报告分析"""
    #     return self._date_indexs[0]

    # @property
    # def date_indexs(self) -> list[pd.Series]:
    #     """合约时间索引集，用于报告分析"""
    #     return self._date_indexs

    @property
    def use_close(self) -> bool:
        """是否使用当前交易信号的收盘价作成交价,否为使用下一根K线的开盘价作成交价"""
        return self._use_close

    @property
    def key(self) -> str:
        """行情更新字段"""
        return self._key

    @property
    def web_gui(self) -> bool:
        """是否打开即时行情"""
        return self._web_gui

    # @property
    # def last_data_index(self) -> int:
    #     """第一个合约数据最后一个数据的索引"""
    #     return self._last_data_indexs[0]

    # @property
    # def last_data_indexs(self) -> list[int]:
    #     """合约数据最后一个数据的索引集"""
    #     return self._last_data_indexs

    @property
    def actor(self) -> Callable:
        """第一个合约强化学习模型"""
        return self._actor

    @actor.setter
    def actor(self, value) -> Callable:
        """第一个合约强化学习模型"""
        self._actor = value

    @property
    def env(self):
        """强化学习事件"""
        return self._env

    @env.setter
    def env(self, value):
        """强化学习事件"""
        self._env = value

    @property
    def action(self) -> int:
        """当前模型动作"""
        return self._action

    @action.setter
    def action(self, value) -> None:
        """当前模型动作"""
        self._action = value

    @property
    def overlap(self) -> bool:
        """强化学习中特征数据如果是主图的，则返回的是差值"""
        return self._overlap

    @property
    def rl_ind_list(self) -> list[str]:
        """强化学习指标列表"""
        return self.rl_ind_list

    @property
    def rl_params_list(self) -> list[dict]:
        """强化学习指标参数列表"""
        return self.rl_params_list

    @property
    def signal_features(self) -> np.ndarray:
        """强化学习特征集"""
        return self._signal_features

    @property
    def cutout(self) -> float:
        return self._cutout

    @property
    def scrambling(self) -> float:
        return self._scrambling

    @property
    def scroll(self) -> float:
        return self._scroll

    @property
    def slip_points(self) -> list[float]:
        return self._slip_points

    @property
    def breakout_factor(self) -> float:
        return self._breakout_factor

    @property
    def signal_window(self) -> int:
        return self._signal_window

    @property
    def max_times(self) -> int:
        return self._max_times

    @property
    def expected_hoding_days(self) -> int:
        return self._expected_hoding_days

    @property
    def min_expected_hoding_days(self) -> int:
        return self._min_expected_hoding_days

    @property
    def expected_flat_days(self) -> int:
        return self._expected_flat_days

    @property
    def rwf(self) -> float:
        return self._rwf

    @property
    def in_eins(self) -> bool:
        return self._in_eins

    @property
    def init_account_features(self) -> np.ndarray:
        return self._init_account_features

    @property
    def init_gap(self) -> bool:
        return self._init_gap

    @property
    def stub(self) -> int:
        return self._stub

    @property
    def is_changing(self) -> bool:
        if self.is_live_trading:
            return self._api.is_changing(self._btdatasset.default_btdata._dataset.tq_object.iloc[-1], self._key)

    @property
    def is_last_price_changing(self) -> bool:
        if self.is_live_trading:
            return any([self._api.is_changing(btdata.quote, 'last_price') for _, btdata in self._btdatasset.items()])

    # @property
    # def kline(self) -> pd.DataFrame:
    #     """K线数据
    #     ----------
    #     本函数总是返回一个DataFrame实例, 至少包含以下列:
    #     >>> [datetime , open , high , low , close , volume]"""
    #     return self._get_klines(self._btindex)[0]

    # @property
    # def klines(self) -> list[pd.DataFrame]:
    #     """所有K线数据
    #     ----------
    #     本函数总是返回一个list[list[pandas.DataFrame]],
    #     每个DataFrame至少包含以下列:
    #     >>> [datetime , open , high , low , close , volume]"""
    #     return self._get_klines(self._btindex)

    # @cachedmethod(attrgetter('_cache'))
    # def _get_klines(self, index: int):
    #     return self._klines

    # @property
    # def klines0(self) -> pd.DataFrame:
    #     """第一个K线数据"""
    #     ...

    # @property
    # def klines1(self) -> pd.DataFrame:
    #     """第二个K线数据"""
    #     ...

    # @property
    # def klines2(self) -> pd.DataFrame:
    #     """第三个K线数据"""
    #     ...

    # @property
    # def klines3(self) -> pd.DataFrame:
    #     """第四个K线数据"""
    #     ...

    # @property
    # def klines4(self) -> pd.DataFrame:
    #     """第五个K线数据"""
    #     ...

    # @property
    # def klines5(self) -> pd.DataFrame:
    #     """第六个K线数据"""
    #     ...

    # @property
    # def quote(self) -> list[Quote, Quotes]:
    #     """Quote是一个行情对象"""
    #     return self._get_quotes(self._btindex)[0]

    # @property
    # def quotes(self) -> list[Quote, Quotes]:
    #     """Quotes是一个行情对象列表"""
    #     return self._get_quotes(self._btindex)

    # def _get_quotes(self, index: int):
    #     ...

    # # @cachedmethod(attrgetter('_cache'))
    # def _get_quotes1(self, index: int):
    #     return [data.quote for i, data in enumerate(self._datas)]

    # # @cachedmethod(attrgetter('_cache'))
    # def _get_quotes2(self, index: int):
    #     return self._quotes

    # @property
    # def quotes0(self) -> Union[Quote, Quotes]:
    #     """ 第一个合约Quote"""
    #     ...

    # @property
    # def quotes1(self) -> Union[Quote, Quotes]:
    #     """ 第二个合约Quote"""
    #     ...

    # @property
    # def quotes2(self) -> Union[Quote, Quotes]:
    #     """ 第三个合约Quote"""
    #     ...

    # @property
    # def quotes3(self) -> Union[Quote, Quotes]:
    #     """ 第四个合约Quote"""
    #     ...

    # @property
    # def quotes4(self) -> Union[Quote, Quotes]:
    #     """ 第五个合约Quote"""
    #     ...

    # @property
    # def quotes5(self) -> Union[Quote, Quotes]:
    #     """ 第六个合约Quote"""
    #     ...

    # @property
    # def target_pos_task(self) -> TargetPosTask:
    #     """目标持仓task, 该task可以将指定合约调整到目标头寸"""
    #     return self._get_target_pos_tasks(self._btindex)[0]

    # @property
    # def target_pos_tasks(self) -> list[TargetPosTask]:
    #     """目标持仓task列表, 每个task可以将指定合约调整到目标头寸"""
    #     return self._get_target_pos_tasks(self._btindex)

    # # @cachedmethod(attrgetter('_cache'))
    # def _get_target_pos_tasks(self, index: int):
    #     return self._target_pos_tasks

    # @property
    # def target_pos_tasks0(self) -> TargetPosTask:
    #     """第一个目标持仓task, 该task可以将指定合约调整到目标头寸"""
    #     ...

    # @property
    # def target_pos_tasks1(self) -> TargetPosTask:
    #     """第二个目标持仓task, 该task可以将指定合约调整到目标头寸"""
    #     ...

    # @property
    # def target_pos_tasks2(self) -> TargetPosTask:
    #     """第三个目标持仓task, 该task可以将指定合约调整到目标头寸"""
    #     ...

    # @property
    # def target_pos_tasks3(self) -> TargetPosTask:
    #     """第四个目标持仓task, 该task可以将指定合约调整到目标头寸"""
    #     ...

    # @property
    # def target_pos_tasks4(self) -> TargetPosTask:
    #     """第五个目标持仓task, 该task可以将指定合约调整到目标头寸"""
    #     ...

    # @property
    # def target_pos_tasks5(self) -> TargetPosTask:
    #     """第六个目标持仓task, 该task可以将指定合约调整到目标头寸"""
    #     ...

    @property
    def position(self) -> Union[BtPosition, Position]:
        """第一个合约的仓位对象"""
        return self._btdatasset.default_btdata.position

    # @property
    # def positions(self) -> list[Union[BtPosition, Position]]:
    #     """所有合约的仓位对象列表"""
    #     return self._get_positions(self._btindex)

    # def _get_positions(self, index: int):
    #     ...

    # # @cachedmethod(attrgetter('_cache'))
    # def _get_positions1(self, index: int):
    #     return self._btdatasset.default_btdata.position

    # # @cachedmethod(attrgetter('_cache'))
    # def _get_positions2(self, index: int):
    #     return self._positions

    # @property
    # def positions0(self) -> Union[BtPosition, Position]:
    #     """第一个合约的仓位对象"""
    #     ...

    # @property
    # def positions1(self) -> Union[BtPosition, Position]:
    #     """第二个合约的仓位对象"""
    #     ...

    # @property
    # def positions2(self) -> Union[BtPosition, Position]:
    #     """第三个合约的仓位对象"""
    #     ...

    # @property
    # def positions3(self) -> Union[BtPosition, Position]:
    #     """第四个合约的仓位对象"""
    #     ...

    # @property
    # def positions4(self) -> Union[BtPosition, Position]:
    #     """第五个合约的仓位对象"""
    #     ...

    # @property
    # def positions5(self) -> Union[BtPosition, Position]:
    #     """第六个合约的仓位对象"""
        # ...

    # @property
    # def data(self) -> BtData:
    #     """第一合约BtData数据"""
    #     # if not self._datas:
    #     #     self.get_data(None, None)
    #     # return self._datas[0]
    #     return self._btdatasset.default_btdata

    # @data.setter
    # def data(self, value: BtData) -> None:
    #     assert type(value) == self._btdata, ValueError("赋值数据必须为BtData数据")
    #     # self._datas[0] = value

    # @property
    # def datas(self) -> list[BtData]:
    #     """第一合约BtData数据"""
    #     return self._get_datas(self._btindex)

    # # @cachedmethod(attrgetter('_cache'))
    # def _get_datas(self, index: int):
    #     return self._datas

    # @property
    # def datas0(self) -> BtData:
    #     """第一合约BtData数据"""
    #     ...

    # @property
    # def datas1(self) -> BtData:
    #     """第二合约BtData数据"""
    #     ...

    # @property
    # def datas2(self) -> BtData:
    #     """第三合约BtData数据"""
    #     ...

    # @property
    # def datas3(self) -> BtData:
    #     """第四合约BtData数据"""
    #     ...

    # @property
    # def datas4(self) -> BtData:
    #     """第五合约BtData数据"""
    #     ...

    # @property
    # def datas5(self) -> BtData:
    #     """第六合约BtData数据"""
        ...

    # talib
    # @classmethod
    # @property
    # def btdata(cls) -> BtData:
    #     """
    #     # 内置pandas_ta指标
    #     -----------------------
    #     # Note
    #     >>> 注意: 非BtData数据中指标第一个数据为包含至少['open','high','low','close','volume']
    #         字段的BtData数据,例.ha(self.data)
    #         BtData数据直接调用则不需要指定,例self.data.ha()

    #     # Examples:
    #     >>> self.data.ha()
    #         self.btind.ha(self.data)
    #         self.ha_open,self.ha_high,self.ha_low,self.ha_close=self.data.ha().to_lines()
    #         self.btind.cross(self.data,mama,fama)
    #         self.data.close,self.data.volume

    #         self.pmax=self.talib.pmax(self.data)
    #         self.pmax=self.data.talib.pmax()

    #     # IndExtend
    #     >>> 指标扩展
    #         class owenbtind(BtData):
    #             @to_btind
    #             def owenema(self,length):
    #                 self.talib.alerts()
    #                 self.ema(length)
    #                 return self.ta.ema(length)
    #     >>> self.owenema=owenbtind.owenema(self.data,self.params.len1)

    #     # Candles
    #     >>> candles: [cdl_pattern, cdl_z, ha],

    #     # Cycles
    #     >>> cycles: [ebsw]

    #     # Utility
    #     >>> utility: [above ,above_value ,below ,below_value ,cross ,cross_value],

    #     # Momentum
    #     >>> momentum: [
    #         ao, apo, bias, bop, brar, cci, cfo, cg, cmo,
    #         coppock, cti, er, eri, fisher, inertia, kdj, kst, macd,
    #         mom, pgo, ppo, psl, pvo, qqe, roc, rsi, rsx, rvgi,
    #         slope, smi, squeeze, squeeze_pro, stc, stoch, stochrsi, td_seq, trix,
    #         tsi, uo, willr],

    #     # Overlap
    #     >>> overlap: [
    #         alma, dema, ema, fwma, hilo, hl2, hlc3, hma, ichimoku,
    #         jma, kama, linreg, mcgd, midpoint, midprice, ohlc4,
    #         pwma, rma, sinwma, sma, ssf, supertrend, swma, t3,
    #         tema, trima, vidya, vwap, vwma, wcp, wma, zlma],

    #     # Performance
    #     >>> performance: [log_return, percent_return],

    #     # Statistics
    #     >>> statistics: [
    #         entropy, kurtosis, mad, median, quantile, skew, stdev,
    #         tos_stdevall, variance, zscore],

    #     # Trend
    #     >>> trend: [
    #         adx, amat, aroon, chop, cksp, decay, decreasing, dpo,
    #         increasing, long_run, psar, qstick, short_run, tsignals,
    #         ttm_trend, vhf, vortex, xsignals],

    #     # Volatility
    #     >>> volatility: [
    #         aberration, accbands, atr, bbands, donchian, hwc, kc, massi,
    #         natr, pdist, rvi, thermo, true_range, ui],

    #     # Volume, vp or Volume Profile is unique
    #     >>> volume: [
    #         ad, adosc, aobv, cmf, efi, eom, kvo, mfi, nvi, obv,
    #         pvi, pvol, pvr, pvt],
    #     """
    #     return cls._btdata  # type('BtData',(self._btdata,),{})

    # @classmethod
    # @property
    # def btdata(cls) -> BtData:
    #     return cls._btdata

    def _next(self):
        """强化学习默认next函数"""
        if self._action == Actions.SELL:
            if self.position >= 0:
                self.sell()
        elif self._action == Actions.BUY:
            if self.position <= 0:
                self.buy()
        elif self._action == Actions.Long_exit:
            if self.position > 0:
                self.sell()
        elif self._action == Actions.Short_exit:
            if self.position < 0:
                self.buy()
        elif self._action == Actions.Long_reversing:
            if self.positios > 0:
                self.set_target_size(size=-1)
        elif self._action == Actions.Short_reversing:
            if self.position < 0:
                self.set_target_size(size=1)
