from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Literal, Union, TypeVar, Optional, Callable, Any

    from collections.abc import (
        Hashable,
        Mapping,
        MutableMapping,
        Sequence,
    )

    OPTTargetType = Literal[
        'result', 'profit', 'profit_rate', 'adjusted_sortino', 'autocorr_penalty', 'avg_loss', 'avg_return',
        'avg_win', 'best', 'cagr', 'calmar', 'common_sense_ratio', 'comp', 'compare', 'compsum', 'conditional_value_at_risk',
        'consecutive_losses', 'consecutive_wins', 'cpc_index', 'cvar', 'distribution', 'drawdown_details', 'expected_return',
        'expected_shortfall', 'exposure', 'gain_to_pain_ratio', 'geometric_mean', 'ghpr', 'greeks',
        'implied_volatility', 'information_ratio', 'kelly_criterion', 'kurtosis', 'max_drawdown',
        'monthly_returns', 'omega', 'outlier_loss_ratio', 'outlier_win_ratio', 'outliers', 'payoff_ratio',
        'pct_rank', 'profit_factor', 'profit_ratio', 'r2', 'r_squared', 'rar', 'recovery_factor',
        'remove_outliers', 'risk_of_ruin', 'risk_return_ratio', 'rolling_greeks', 'rolling_sharpe',
        'rolling_sortino', 'rolling_volatility', 'ror', 'serenity_index', 'sharpe', 'skew', 'smart_sharpe',
        'smart_sortino', 'sortino', 'tail_ratio', 'to_drawdown_series', 'ulcer_index', 'ulcer_performance_index',
        'upi', 'value_at_risk', 'var', 'volatility', 'warn', 'win_loss_ratio', 'win_rate', 'worst']
    OPTMethodType = Literal['ga', 'optuna']
    IncludeStyle = Literal["all", "last"]
    EngineType = Union[Literal["cython", "numba"], None]
    BTPlotType = Literal["all", "last"]
    MaModeType = Literal[
        "dema", "ema", "fwma", "hma", "linreg", "midpoint", "pwma", "rma",
        "sinwma", "sma", "swma", "t3", "tema", "trima", "vidya", "wma", "zlma"
    ]
    DevType = Literal["stdev", "art", "variance", "smoothrng"]
    RSRSMethodType = Literal['r1', 'r2', 'r3']
    LabelStyle = Literal["normal", "bold"]
    PRFNameTtype = Literal[
        "CDL2CROWS", "CDL3BLACKCROWS", "CDL3INSIDE",
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
        "CDLXSIDEGAP3METHODS",]
    ExpandingMethodType = Literal["single", "table"]

    # pandas typing
    T = TypeVar("T")

    Axis = Union[int, Literal["index", "columns", "rows"]]
    IgnoreRaise = Literal["ignore", "raise"]
    FillnaOptions = Literal["backfill", "bfill", "ffill", "pad"]
    InterpolateOptions = Literal[
        "linear",
        "time",
        "index",
        "values",
        "nearest",
        "zero",
        "slinear",
        "quadratic",
        "cubic",
        "barycentric",
        "polynomial",
        "krogh",
        "piecewise_polynomial",
        "spline",
        "pchip",
        "akima",
        "cubicspline",
        "from_derivatives",
    ]
    import numpy as np
    from datetime import date
    PythonScalar = Union[str, float, bool]
    DatetimeLikeScalar = Union[TypeVar("Period"), TypeVar(
        "Timestamp"), TypeVar("Timedelta")]
    PandasScalar = Union[TypeVar("Period"), TypeVar(
        "Timestamp"), TypeVar("Timedelta"), TypeVar("Interval")]
    Scalar = Union[PythonScalar, PandasScalar,
                   np.datetime64, np.timedelta64, date]
    ArrayLike = Union[TypeVar("ExtensionArray"), np.ndarray]
    AnyArrayLike = Union[ArrayLike, TypeVar("Index"), TypeVar("Series")]
    IndexLabel = Union[Hashable, Sequence[Hashable]]
    Frequency = Union[str, TypeVar("BaseOffset")]
    ValueKeyFunc = Optional[Callable[[TypeVar("Series")],
                                     Union[TypeVar("Series"), AnyArrayLike]]]
    IndexKeyFunc = Optional[Callable[[
        TypeVar("Index")], Union[TypeVar("Index"), AnyArrayLike]]]
    UpdateJoin = Literal["left"]
    NaPosition = Literal["first", "last"]
    AggFuncTypeBase = Union[Callable, str]
    AggFuncTypeDict = MutableMapping[
        Hashable, Union[AggFuncTypeBase, list[AggFuncTypeBase]]
    ]
    AggFuncType = Union[
        AggFuncTypeBase,
        list[AggFuncTypeBase],
        AggFuncTypeDict,
    ]
    MergeHow = Literal["left", "right", "inner", "outer", "cross"]
    MergeValidate = Literal[
        "one_to_one",
        "1:1",
        "one_to_many",
        "1:m",
        "many_to_one",
        "m:1",
        "many_to_many",
        "m:m",
    ]
    JoinValidate = Literal[
        "one_to_one",
        "1:1",
        "one_to_many",
        "1:m",
        "many_to_one",
        "m:1",
        "many_to_many",
        "m:m",
    ]
    Suffixes = tuple[Optional[str], Optional[str]]
    DropKeep = Literal["first", "last", False]
    SortKind = Literal["quicksort", "mergesort", "heapsort", "stable"]
    PythonFuncType = Callable[[Any], Any]
    NaAction = Literal["ignore"]
    QuantileInterpolation = Literal["linear",
                                    "lower", "higher", "midpoint", "nearest"]
    WindowingRankType = Literal["average", "min", "max"]
