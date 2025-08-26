from __future__ import annotations
from .ta import *
if TYPE_CHECKING:
    import tulipy
    import talib as Talib
    from .ta_ import autotrader, SignalFeatures, PairTrading, Factors
    from finta import TA as FinTa


def is_bt_ind_type(obj):
    """判断对象是否为BtIndType包含的类型"""
    type_name = type(obj).__name__
    return type_name in ['Line', 'dataframe', 'series']


def get_factors_df(*factors):
    factors_df = pd.DataFrame()
    for factor in factors:
        if is_bt_ind_type(factor):
            lines = factor.lines
            if len(lines) == 1:
                factors_df[lines[0]] = factor.values
            else:
                factors_df = pd.concat([factors_df, factor], axis=1)
    return factors_df


def get_data(obj=None):
    if hasattr(obj, '_df'):
        obj = obj._df
    if hasattr(obj, '_df'):
        return obj._df
    elif hasattr(obj, 'pandas_object'):
        return obj.pandas_object
    else:
        return obj


def _get_column_(self, *args) -> Union[tuple[list[pd.Series], dict], dict]:
    """应用于pandas_ta"""
    local, *default_filed = args
    kwargs: dict = local.pop('kwargs')

    if 'open' in local:  # pandas_ta所有open参数都用open_
        local['open_'] = local.pop('open')
    if not default_filed:  # 没指定默认字段则返回
        return {**local, **kwargs}
    data = kwargs.get('data', get_data(self))
    isdataframe = len(data.shape) > 1
    if not isdataframe and 'filed' not in kwargs:
        filed = default_filed
        filed[0] = data.name
    else:
        filed = kwargs.pop('filed', default_filed)
        if isinstance(filed, str):
            filed = [filed,]
        assert len(filed) == len(
            default_filed), f"filed字段{filed}长度与默认字段{default_filed}长度不一致"

    local = dict(zip(local.keys(), map(
        lambda x: get_data(x), local.values())))
    kwargs = dict(zip(kwargs.keys(), map(
        lambda x: get_data(x), kwargs.values())))

    args = dict(zip(filed, filed))
    for f in filed:
        args[f] = kwargs.pop(f, data[f] if isdataframe else data)
    return [s for s in args.values()], {**local, **kwargs}


def _ti_get_data(*args) -> tuple[list, dict]:
    values, kwargs = _get_column_(*args)
    values = [value.values.astype(np.float64) for value in values]
    # [value.astype(np.float32) for value in values]
    return values, kwargs


def _get_data_(self, a) -> pd.Series:
    if isinstance(a, str):
        _a_frame = get_data(self)
        if len(_a_frame.shape) > 1:
            assert a in list(
                _a_frame.columns), f"{a}不在列表{list(_a_frame.columns)}中"
            a = _a_frame[a]
        else:
            a = _a_frame
    return a


def _finta_get_data(self, **kwargs):
    if "filed" in kwargs:
        filed = kwargs.pop("filed")
        assert filed in FILED.OHLCV, f"{filed}字段不存在"
        return self._df[:, filed]
    else:
        data = kwargs.pop('close', self._df[FILED.OHLCV])
    return pd.DataFrame(data, columns=['close',]) if len(data.shape) < 2 else data


@pd.api.extensions.register_series_accessor("ta")
class SeriesIndicators(BasePandasObject, LazyImport):
    _df = pd.Series()

    def __init__(self, pandas_obj):
        self._validate(pandas_obj)
        self._df = pandas_obj

    @staticmethod
    def _validate(obj: pd.Series):
        if not isinstance(obj, pd.Series):
            raise AttributeError(
                "[X] Must be either a Pandas Series.")


def length(self) -> int:
    return len(self._df)


AnalysisIndicators.length = property(length)
SeriesIndicators.length = property(length)
# AnalysisIndicators._ti = property(_ti_)
# SeriesIndicators._ti = property(_ti_)
# AnalysisIndicators._talib = property(_talib_)
# SeriesIndicators._talib = property(_talib_)
setattr(AnalysisIndicators, '_get_column_', _get_column_)
setattr(SeriesIndicators, '_get_column_', _get_column_)
setattr(AnalysisIndicators, '_get_data_', _get_data_)
setattr(SeriesIndicators, '_get_data_', _get_data_)
setattr(AnalysisIndicators, '_finta_get_data', _finta_get_data)
setattr(SeriesIndicators, '_finta_get_data', _finta_get_data)
setattr(AnalysisIndicators, '_ti_get_data', _ti_get_data)
setattr(SeriesIndicators, '_ti_get_data', _ti_get_data)


class CoreFunc:
    """重载所有指标方法"""
    _df: Union[pd.DataFrame, pd.Series]

    @property
    def length(self) -> int:
        ...

    def _finta_get_data(self, **kwargs):
        ...

    def _get_column_(self, *args) -> Union[tuple[list[pd.Series], dict], dict]:
        ...

    def _get_data_(self, a) -> pd.Series:
        ...

    def _ti_get_data(self) -> tuple[list, dict]:
        ...
    # 无标签指标

    def pta_Any(self, *args, keep=True, **kwargs):
        args = list(args)
        if keep:
            if len(self.shape) > 1:
                args.extend([getattr(self, name) for name in self.columns])
            else:
                args.extend([self,])
        return Any_(*args)

    def pta_All(self, *args, keep=True, **kwargs):
        args = list(args)
        if keep:
            if len(self.shape) > 1:
                args.extend([getattr(self, name) for name in self.columns])
            else:
                args.extend([self,])
        return All_(*args)

    def pta_Where(self, cond, x=None, y=.0, **kwargs):
        if x is None:
            x = self
        return np.where(cond, x, y)

    def pta_cum(self, length=10, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return cum(*arg, **kwargs)

    def pta_ZeroDivision(self, b=1., **kwargs) -> ndarray:
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return ZeroDivision(*arg, **kwarg)

    def pta_rolling_apply(self, func: Callable, window: int, prepend_nans: bool = True, n_jobs: int = 1, **kwargs) -> np.ndarray:
        return rolling_apply(self, func, window, prepend_nans, n_jobs, **kwargs)

    def Linear_Regression_Candles(self, length=11, **kwargs):
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
        kwargs.update(dict(length=length))
        return Candles.Linear_Regression_Candles(get_data(self), **kwargs)

    def Heikin_Ashi_Candles(self, length=0, **kwargs):
        """# Heikin_Ashi_Candles
            Normal candlestick charts are composed of a series of open-high-low-close (OHLC) candles
            set apart by a time series. The Heikin-Ashi technique shares some characteristics with
            standard candlestick charts but uses a modified formula of close-open-high-low (COHL):

            >>> Close=1/4 * (Open+High+Low+Close)(The average price of the current bar)
                Open=1/2 * (Open of Prev. Bar+Close of Prev. Bar)(The midpoint of the previous bar)
                High=Max[High, Open, Close]
                Low=Min[Low, Open, Close]

            # Args:
                >>> df (pd.DataFrame): K线数据
                    length (int, optional): 长度. Defaults to 0.

            # Returns:
                >>> pd.DataFrame
            """
        kwargs.update(dict(length=length))
        return Candles.Heikin_Ashi_Candles(get_data(self), **kwargs)

    def pta_line_trhend(self, length=1, **kwargs):
        return line_trhend(self._df, length, **kwargs)

    def pta_abc(self, lim: float = 5., **kwargs):
        kwargs.update(dict(lim=lim))
        return abc(get_data(self), **kwargs)

    def pta_insidebar(self, length: int = 10, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return insidebar(*arg, **kwarg)

    def time_to_datetime(self):
        data = self._df
        if not isinstance(data, pd.DataFrame):
            return data
        try:
            cols = list(data.columns)
            datetime_list = [
                col for col in cols if is_datetime64_any_dtype(data[col])]
            if datetime_list:
                for dt in datetime_list:
                    data[dt] = data[dt].apply(time_to_datetime)
        except:
            ...
        return data
    # Public DataFrame Methods: Indicators and Utilities
    # pandas_ta指标
    # Candles

    def pta_cdl_pattern(self, name="all", offset=None, **kwargs):
        """args : open, high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        return pta.cdl_pattern(*arg, **kwarg)

    def pta_cdl_z(self, full=None, offset=None, **kwargs):
        """args : open, high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        return pta.cdl_z(*arg, **kwarg)

    def pta_ha(self, length=0, offset=None, **kwargs):
        """args : open, high, low, close"""
        # arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        # return pta.ha(*arg, **kwarg)
        df = get_data(self)
        length = length if length and length >= 0 else 0
        if length:
            df_ls = [df.shift(i).fillna(method="backfill")
                     if i else df for i in range(length+1)]
            _open = df_ls[-1].open
            _close = df.close
            _low = reduce(np.minimum, [data.low for data in df_ls])
            _high = reduce(np.maximum, [data.high for data in df_ls])
            dframe = pta.ha(_open, _high, _low, _close, offset, **kwargs)
        else:
            dframe = pta.ha(df.open, df.high, df.low,
                            df.close, offset, **kwargs)
        # dframe.columns = FILED.OHLC.tolist()
        return dframe

    def pta_lrc(self, length=10, **kwargs):
        df = get_data(self)
        lr_open = pta.linreg(df.open, length)
        lr_high = pta.linreg(df.high, length)
        lr_low = pta.linreg(df.low, length)
        lr_close = pta.linreg(df.close, length)
        dframe = pd.DataFrame(
            dict(open=lr_open, high=lr_high, low=lr_low, close=lr_close))
        dframe.loc[:length, FILED.OHLC] = df.loc[:length, FILED.OHLC]
        dframe.category = 'candles'
        return dframe

    # Cycles
    def pta_ebsw(self, length=None, bars=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.ebsw(*arg, **kwarg)

    # Momentum
    def pta_ao(self, fast=None, slow=None, offset=None, **kwargs):
        """args : high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return pta.ao(*arg, **kwarg)

    def pta_apo(self, fast=None, slow=None, mamode=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.apo(*arg, **kwarg)

    def pta_bias(self, length=None, mamode=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.bias(*arg, **kwarg)

    def pta_bop(self,  scalar=None, talib=None, offset=None, **kwargs):
        """args : open, high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        return pta.bop(*arg, **kwarg)

    def pta_brar(self, length=None, scalar=None, drift=None, offset=None, **kwargs):
        """args : open, high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        return pta.brar(*arg, **kwarg)

    def pta_cci(self, length=None, c=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.cci(*arg, **kwarg)

    def pta_cfo(self, length=None, scalar=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.cfo(*arg, **kwarg)

    def pta_cg(self, length=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.cg(*arg, **kwarg)

    def pta_cmo(self, length=None, scalar=None, talib=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.cmo(*arg, **kwarg)

    def pta_coppock(self, length=None, fast=None, slow=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.coppock(*arg, **kwarg)

    def pta_cti(self, length=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.cti(*arg, **kwarg)

    def pta_dm(self, length=None, mamode=None, talib=None, drift=None, offset=None, **kwargs):
        """args : high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return pta.dm(*arg, **kwarg)

    def pta_er(self, length=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.er(*arg, **kwarg)

    def pta_eri(self, length=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.eri(*arg, **kwarg)

    def pta_fisher(self, length=None, signal=None, offset=None, **kwargs):
        """args : high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return pta.fisher(*arg, **kwarg)

    def pta_inertia(self, length=None, rvi_length=None, scalar=None, refined=None, thirds=None, mamode=None, drift=None, offset=None, **kwargs):
        """args : close, high, low"""
        arg, kwarg = self._get_column_(locals(), 'close', 'high', 'low')
        return pta.inertia(*arg, **kwarg)

    def pta_kdj(self, length=None, signal=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.kdj(*arg, **kwarg)

    def pta_kst(self, roc1=None, roc2=None, roc3=None, roc4=None, sma1=None, sma2=None, sma3=None, sma4=None, signal=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.kst(*arg, **kwarg)

    def pta_macd(self, fast=None, slow=None, signal=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.macd(*arg, **kwarg)

    def pta_mom(self, length=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.mom(*arg, **kwarg)

    def pta_pgo(self, length=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.pgo(*arg, **kwarg)

    def pta_ppo(self, fast=None, slow=None, signal=None, scalar=None, mamode=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.ppo(*arg, **kwarg)

    def pta_psl(self, open_=None, length=None, scalar=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.psl(*arg, **kwarg)

    def pta_pvo(self, fast=None, slow=None, signal=None, scalar=None, offset=None, **kwargs):
        """args : volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.V)
        return pta.pvo(*arg, **kwarg)

    def pta_qqe(self, length=None, smooth=None, factor=None, mamode=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.qqe(*arg, **kwarg)

    def pta_roc(self, length=None, scalar=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.roc(*arg, **kwarg)

    def pta_rsi(self, length=None, scalar=None, talib=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.rsi(*arg, **kwarg)

    def pta_rsx(self, length=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.rsx(*arg, **kwarg)

    def pta_rvgi(self, length=None, swma_length=None, offset=None, **kwargs):
        """args : open, high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        return pta.rvgi(*arg, **kwarg)

    def pta_slope(self, length=None, as_angle=None, to_degrees=None, vertical=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.slope(*arg, **kwarg)

    def pta_smi(self, fast=None, slow=None, signal=None, scalar=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.smi(*arg, **kwarg)

    def pta_squeeze(self, bb_length=None, bb_std=None, kc_length=None, kc_scalar=None, mom_length=None, mom_smooth=None, use_tr=None, mamode=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.squeeze(*arg, **kwarg)

    def pta_squeeze_pro(self, bb_length=None, bb_std=None, kc_length=None, kc_scalar_wide=None, kc_scalar_normal=None, kc_scalar_narrow=None, mom_length=None, mom_smooth=None, use_tr=None, mamode=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.squeeze_pro(*arg, **kwarg)

    def pta_stc(self, tclength=None, fast=None, slow=None, factor=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.stc(*arg, **kwarg)

    def pta_stoch(self, k=None, d=None, smooth_k=None, mamode=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.stoch(*arg, **kwarg)

    def pta_stochrsi(self, length=None, rsi_length=None, k=None, d=None, mamode=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.stochrsi(*arg, **kwarg)

    def pta_td_seq(self, asint=None, offset=None, show_all=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.td_seq(*arg, **kwarg)

    def pta_trix(self, length=None, signal=None, scalar=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.trix(*arg, **kwarg)

    def pta_tsi(self, fast=None, slow=None, signal=None, scalar=None, mamode=None, drift=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.tsi(*arg, **kwarg)

    def pta_uo(self, fast=None, medium=None, slow=None, fast_w=None, medium_w=None, slow_w=None, talib=None, drift=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.uo(*arg, **kwarg)

    def pta_willr(self, length=None, talib=True, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.willr(*arg, **kwarg)

    # Overlap
    def pta_alma(self, length=None, sigma=None, distribution_offset=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.alma(*arg, **kwarg)

    def pta_dema(self, length=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.dema(*arg, **kwarg)

    def pta_ema(self, length=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.ema(*arg, **kwarg)

    def pta_fwma(self, length=None, asc=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.fwma(*arg, **kwarg)

    def pta_hilo(self, high_length=None, low_length=None, mamode=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.hilo(*arg, **kwarg)

    def pta_hl2(self, offset=None, **kwargs):
        """args : high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return pta.hl2(*arg, **kwarg)

    def pta_hlc3(self, talib=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.hlc3(*arg, **kwarg)

    def pta_hma(self, length=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.hma(*arg, **kwarg)

    def pta_hwma(self, na=None, nb=None, nc=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.hwma(*arg, **kwarg)

    def pta_jma(self, length=None, phase=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.jma(*arg, **kwarg)

    def pta_kama(self, length=None, fast=None, slow=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.kama(*arg, **kwarg)

    def pta_ichimoku(self, tenkan=None, kijun=None, senkou=None, include_chikou=True, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        result, _ = pta.ichimoku(*arg, **kwarg)
        return result

    def pta_linreg(self, length=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.linreg(*arg, **kwarg)

    def pta_mcgd(self, length=None, offset=None, c=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.mcgd(*arg, **kwarg)

    def pta_midpoint(self, length=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.midpoint(*arg, **kwarg)

    def pta_midprice(self, length=None, talib=None, offset=None, **kwargs):
        """args : high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return pta.midprice(*arg, **kwarg)

    def pta_ohlc4(self, offset=None, **kwargs):
        """args : open, high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        return pta.ohlc4(*arg, **kwarg)

    def pta_pwma(self, length=None, asc=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.pwma(*arg, **kwarg)

    def pta_ma(self, name: str = None, length: int = 10, **kwargs):
        """args : close"""
        kwargs.update(dict(length=length))
        locals().pop('length')
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        source = dict(source=arg[0])
        return pta.ma(**{**source, **kwarg})

    def pta_rma(self, length=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.rma(*arg, **kwarg)

    def pta_sinwma(self, length=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.sinwma(*arg, **kwarg)

    def pta_sma(self, length=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.sma(*arg, **kwarg)

    def pta_ssf(self, length=None, poles=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.ssf(*arg, **kwarg)

    def pta_supertrend(self, length=None, multiplier=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.supertrend(*arg, **kwarg)

    def pta_swma(self, length=None, asc=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.swma(*arg, **kwarg)

    def pta_t3(self, length=None, a=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.t3(*arg, **kwarg)

    def pta_tema(self, length=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.tema(*arg, **kwarg)

    def pta_trima(self, length=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.trima(*arg, **kwarg)

    def pta_vidya(self, length=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.vidya(*arg, **kwarg)

    def pta_vwap(self, anchor=None, offset=None, **kwargs):
        """args : high, low, close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLCV)
        return pta.vwap(*arg, **kwarg)

    def pta_vwma(self, length=None, offset=None, **kwargs):
        """args : close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return pta.vwma(*arg, **kwarg)

    def pta_wcp(self, talib=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.wcp(*arg, **kwarg)

    def pta_wma(self, length=None, asc=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.wma(*arg, **kwarg)

    def pta_zlma(self, length=None, mamode=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.zlma(*arg, **kwarg)

    # Performance
    def pta_log_return(self, length=None, cumulative=False, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.log_return(*arg, **kwarg)

    def pta_percent_return(self, length=None, cumulative=False, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.percent_return(*arg, **kwarg)

    # Statistics
    def pta_entropy(self, length=None, base=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.entropy(*arg, **kwarg)

    def pta_kurtosis_(self, length=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.kurtosis(*arg, **kwarg)

    def pta_mad(self, length=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.mad(*arg, **kwarg)

    def pta_median(self, length=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.median(*arg, **kwarg)

    def pta_quantile_(self, length=None, q=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.quantile(*arg, **kwarg)

    def pta_skew_(self, length=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.skew(*arg, **kwarg)

    def pta_stdev(self, length=None, ddof=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.stdev(*arg, **kwarg)

    def pta_tos_stdevall(self, length=None, stds=None, ddof=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.tos_stdevall(*arg, **kwarg)

    def pta_variance(self, length=None, ddof=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.variance(*arg, **kwarg)

    def pta_zscore(self, length=None, std=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.zscore(*arg, **kwarg)

    # Trend
    def pta_adx(self, length=None, lensig=None, scalar=None, mamode=None, drift=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.adx(*arg, **kwarg)

    def pta_amat(self, fast=None, slow=None, lookback=None, mamode=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.amat(*arg, **kwarg)

    def pta_aroon(self, length=None, scalar=None, talib=None, offset=None, **kwargs):
        """args : high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return pta.aroon(*arg, **kwarg)

    def pta_chop(self, length=None, atr_length=None, ln=None, scalar=None, drift=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.chop(*arg, **kwarg)

    def pta_cksp(self, p=None, x=None, q=None, tvmode=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.cksp(*arg, **kwarg)

    def pta_decay(self, kind=None, length=None, mode=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.decay(*arg, **kwarg)

    def pta_decreasing(self, length=None, strict=None, asint=None, percent=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.decreasing(*arg, **kwarg)

    def pta_dpo(self, length=None, centered=True, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.dpo(*arg, **kwarg)

    def pta_increasing(self, length=None, strict=None, asint=None, percent=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.increasing(*arg, **kwarg)

    def pta_long_run(self, fast=None, slow=None, length=None, offset=None, **kwargs):
        """args : self"""
        if fast is None and slow is None:
            return self._df
        else:
            return pta.long_run(fast, slow, length, offset, **kwargs)

    def pta_psar(self, af0=None, af=None, max_af=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.psar(*arg, **kwarg)

    def pta_qstick(self, length=None, ma="sma", offset=None, **kwargs):
        """args : open, close"""
        kwargs.update(dict(ma=ma))
        locals().pop("ma")
        arg, kwarg = self._get_column_(locals(), *FILED.OC)
        return pta.qstick(*arg, **kwarg)

    def pta_short_run(self, fast=None, slow=None, length=None, offset=None, **kwargs):
        """args : self"""
        if fast is None and slow is None:
            return self._df
        else:
            return pta.short_run(fast, slow, length, offset, **kwargs)

    def pta_tsignals(self, trend=None, asbool=None, trend_reset=None, trade_offset=None, drift=None, offset=None, **kwargs):
        """args : self"""
        if trend is None:
            return self._df
        else:
            return pta.tsignals(trend, asbool, trend_reset, trade_offset, drift, offset, **kwargs)

    def pta_ttm_trend(self, length=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.ttm_trend(*arg, **kwarg)

    def pta_vhf(self, length=None, drift=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.vhf(*arg, **kwarg)

    def pta_vortex(self, length=None, drift=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.vortex(*arg, **kwarg)

    def pta_xsignals(self, signal=None, xa=None, xb=None, above=None, long=None, asbool=None, trend_reset=None, trade_offset=None, offset=None, **kwargs):
        """args : self"""
        if signal is None:
            return self._df
        else:
            return pta.xsignals(signal, xa, xb, above, long, asbool, trend_reset, trade_offset, offset, **kwargs)

    # Utility
    def pta_above(self, b=None, asint=True, offset=None, **kwargs):
        """args : a(self),b"""
        # arg, kwarg = self._get_column_(locals(), *FILED.C)
        kwargs.update(dict(asint=asint, offset=offset))
        a = self._get_data_(get_data(kwargs.pop('a', self)))
        b = get_data(b)
        if isinstance(b, (int, float)):
            return pta.above_value(a, b, **kwargs)
        else:
            return pta.above(a, b, **kwargs)

    def pta_below(self,  b=None, asint=True, offset=None, **kwargs):
        """args : a(self),b"""
        # arg, kwarg = self._get_column_(locals(), *FILED.C)
        kwargs.update(dict(asint=asint, offset=offset))
        a = self._get_data_(get_data(kwargs.pop('a', self)))
        b = get_data(b)
        if isinstance(b, (int, float)):
            return pta.below_value(a, b, **kwargs)
        else:
            return pta.below(a, b, **kwargs)

    def pta_cross(self, b=None, above=True, asint=True, offset=None, **kwargs):
        """args : a(self),b"""
        # arg, kwarg = self._get_column_(locals(), *FILED.C)
        kwargs.update(dict(above=above, asint=asint, offset=offset))
        a = self._get_data_(get_data(kwargs.pop('a', self)))
        a = pd.Series(a) if isinstance(a, np.ndarray) else a
        if isinstance(a, str):
            _a_frame = get_data(self)
            if len(_a_frame.shape) > 1:
                assert a in list(
                    _a_frame.columns), f"{a}不在列表{list(_a_frame.columns)}中"
                a = _a_frame[a]
            else:
                a = _a_frame
        b = get_data(b)
        b = pd.Series(b) if isinstance(b, np.ndarray) else b
        if isinstance(b, (int, float)):
            return pta.cross_value(a, float(b), **kwargs)
        else:
            return pta.cross(a, b, **kwargs)

    def pta_cross_up(self, b=None, asint=True, offset=None, **kwargs):
        """args : a(self),b"""
        # arg, kwarg = self._get_column_(locals(), *FILED.C)
        kwargs.update(dict(above=True, asint=asint, offset=offset))
        a = self._get_data_(get_data(kwargs.pop('a', self)))
        a = pd.Series(a) if isinstance(a, np.ndarray) else a
        if isinstance(a, str):
            _a_frame = get_data(self)
            if len(_a_frame.shape) > 1:
                assert a in list(
                    _a_frame.columns), f"{a}不在列表{list(_a_frame.columns)}中"
                a = _a_frame[a]
            else:
                a = _a_frame
        b = get_data(b)
        b = pd.Series(b) if isinstance(b, np.ndarray) else b
        if isinstance(b, (int, float)):
            return pta.cross_value(a, b, **kwargs)
        else:
            return pta.cross(a, b, **kwargs)

    def pta_cross_down(self, b=None, asint=True, offset=None, **kwargs):
        """args : a(self),b"""
        # arg, kwarg = self._get_column_(locals(), *FILED.C)
        kwargs.update(dict(above=False, asint=asint, offset=offset))
        a = self._get_data_(get_data(kwargs.pop('a', self)))
        a = pd.Series(a) if isinstance(a, np.ndarray) else a
        if isinstance(a, str):
            _a_frame = get_data(self)
            if len(_a_frame.shape) > 1:
                assert a in list(
                    _a_frame.columns), f"{a}不在列表{list(_a_frame.columns)}中"
                a = _a_frame[a]
            else:
                a = _a_frame
        b = get_data(b)
        b = pd.Series(b) if isinstance(b, np.ndarray) else b
        if isinstance(b, (int, float)):
            return pta.cross_value(a, b, **kwargs)
        else:
            return pta.cross(a, b, **kwargs)

    # Volatility
    def pta_aberration(self, length=None, atr_length=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.aberration(*arg, **kwarg)

    def pta_accbands(self, length=None, c=None, drift=None, mamode=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.accbands(*arg, **kwarg)

    def pta_atr(self, length=None, mamode=None, talib=None, drift=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.atr(*arg, **kwarg)

    def pta_bbands(self, length=None, std=None, ddof=0, mamode=None, talib=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.bbands(*arg, **kwarg)

    def pta_donchian(self, lower_length=None, upper_length=None, offset=None, **kwargs):
        """args : high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return pta.donchian(*arg, **kwarg)

    def pta_hwc(self, na=None, nb=None, nc=None, nd=None, scalar=None, channel_eval=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.hwc(*arg, **kwarg)

    def pta_kc(self, length=None, scalar=None, mamode=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.kc(*arg, **kwarg)

    def pta_massi(self, fast=None, slow=None, offset=None, **kwargs):
        """args : high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return pta.massi(*arg, **kwarg)

    def pta_natr(self, length=None, scalar=None, mamode=None, talib=None, drift=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.natr(*arg, **kwarg)

    def pta_pdist(self, drift=None, offset=None, **kwargs):
        """args : open, high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        return pta.pdist(*arg, **kwarg)

    def pta_rvi(self, length=None, scalar=None, refined=None, thirds=None, mamode=None, drift=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), 'close', 'high', 'low')
        return pta.rvi(*arg, **kwarg)

    def pta_thermo(self, length=None, long=None, short=None, mamode=None, drift=None, offset=None, **kwargs):
        """args : high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return pta.thermo(*arg, **kwarg)

    def pta_true_range(self, talib=None, drift=None, offset=None, **kwargs):
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pta.true_range(*arg, **kwarg)

    def pta_ui(self, length=None, scalar=None, offset=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pta.ui(*arg, **kwarg)

    # Volume
    def pta_ad(self, open_=None, talib=None, offset=None, **kwargs):
        """args : high, low, close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLCV)
        return pta.ad(*arg, **kwarg)

    def pta_adosc(self, open_=None, fast=None, slow=None, talib=None, offset=None, **kwargs):
        """args : high, low, close, volume"""
        arg, kwarg = self._get_column_(
            locals(), *FILED.HLCV)
        return pta.adosc(*arg, **kwarg)

    def pta_aobv(self, fast=None, slow=None, max_lookback=None, min_lookback=None, mamode=None, offset=None, **kwargs):
        """args : close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return pta.aobv(*arg, **kwarg)

    def pta_cmf(self, open_=None, length=None, offset=None, **kwargs):
        """args : high, low, close, volume"""
        arg, kwarg = self._get_column_(
            locals(), *FILED.HLCV)
        return pta.cmf(*arg, **kwarg)

    def pta_efi(self,  length=None, mamode=None, drift=None, offset=None, **kwargs):
        """args : close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return pta.efi(*arg, **kwarg)

    def pta_eom(self, length=None, divisor=None, drift=None, offset=None, **kwargs):
        """args : high, low, close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLCV)
        return pta.eom(*arg, **kwarg)

    def pta_kvo(self, fast=None, slow=None, length_sig=None, signal=None, mamode=None, drift=None, offset=None, **kwargs):
        """args : high, low, close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLCV)
        return pta.kvo(*arg, **kwarg)

    def pta_mfi(self, length=None, talib=None, drift=None, offset=None, **kwargs):
        """args : high, low, close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLCV)
        return pta.mfi(*arg, **kwarg)

    def pta_nvi(self, length=None, initial=None, offset=None, **kwargs):
        """args : close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return pta.nvi(*arg, **kwarg)

    def pta_obv(self, talib=None, offset=None, **kwargs):
        """args : close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return pta.obv(*arg, **kwarg)

    def pta_pvi(self, length=None, initial=None, offset=None, **kwargs):
        """args : close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return pta.pvi(*arg, **kwarg)

    def pta_pvol(self, offset=None, **kwargs):
        """args : close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return pta.pvol(*arg, **kwarg)

    def pta_pvr(self, **kwargs):
        """args : close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return pta.pvr(*arg, **kwarg)

    def pta_pvt(self, drift=None, offset=None, **kwargs):
        """args : close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return pta.pvt(*arg, **kwarg)

    def pta_vp(self, width=None, **kwargs):
        """args : close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return pta.vp(*arg, **kwarg)

    # TALIB
    # Cycle Indicator Functions
    @property
    def talib(self) -> Talib:
        ...

    def talib_HT_DCPERIOD(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.HT_DCPERIOD(*arg)

    def talib_HT_DCPHASE(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.HT_DCPHASE(*arg)

    def talib_HT_PHASOR(self, **kwargs):
        """args:close
        lines=inphase, quadrature"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pd.concat(self.talib.HT_PHASOR(*arg), axis=1)

    def talib_HT_SINE(self, **kwargs):
        """args:close
        lines=sine, leadsine"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pd.concat(self.talib.HT_SINE(*arg), axis=1)

    def talib_HT_TRENDMODE(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.HT_TRENDMODE(*arg)

    # TALIB
    # Math Operator Functions
    def talib_ADD(self, **kwargs):
        """args:high,low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.ADD(*arg)

    def talib_DIV(self, **kwargs):
        """args:high,low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.DIV(*arg)

    def talib_MAX(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.MAX(*arg, timeperiod=timeperiod)

    def talib_MAXINDEX(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.MAXINDEX(*arg, timeperiod=timeperiod)

    def talib_MIN(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.MIN(*arg, timeperiod=timeperiod)

    def talib_MININDEX(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.MININDEX(*arg, timeperiod=timeperiod)

    def talib_MINMAX(self, timeperiod=30, **kwargs):
        """args:close
        lines:min , max"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pd.concat(self.talib.MINMAX(*arg, timeperiod=timeperiod), axis=1)

    def talib_MINMAXINDEX(self, timeperiod=30, **kwargs):
        """args:close
        lines:minidx , maxidx"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pd.concat(self.talib.MINMAXINDEX(*arg, timeperiod=timeperiod), axis=1)

    def talib_MULT(self, **kwargs):
        """args:high,low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.MULT(*arg)

    def talib_SUB(self, **kwargs):
        """args:high,low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.SUB(*arg)

    def talib_SUM(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.SUM(*arg, timeperiod=timeperiod)

    # TALIB
    # Math Transform Functions
    def talib_ACOS(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.ACOS(*arg)

    def talib_ASIN(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.ASIN(*arg)

    def talib_ATAN(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.ATAN(*arg)

    def talib_CEIL(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.CEIL(*arg)

    def talib_COS(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.COS(*arg)

    def talib_COSH(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.COSH(*arg)

    def talib_EXP(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.EXP(*arg)

    def talib_FLOOR(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.FLOOR(*arg)

    def talib_LN(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.LN(*arg)

    def talib_LOG10(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.LOG10(*arg)

    def talib_SIN(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.LOG10(*arg)

    def talib_SINH(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.SINH(*arg)

    def talib_SQRT(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.SQRT(*arg)

    def talib_TAN(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.TAN(*arg)

    def talib_TANH(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.TANH(*arg)

    # TALIB
    # Momentum Indicator Functions
    def talib_ADX(self, timeperiod=14, **kwargs):
        """args:high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.ADX(*arg, timeperiod=timeperiod)

    def talib_ADXR(self, timeperiod=14, **kwargs):
        """args:high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.ADXR(*arg, timeperiod=timeperiod)

    def talib_APO(self, fastperiod=12, slowperiod=26, matype=0, **kwargs):
        """args: close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.APO(*arg, fastperiod=fastperiod, slowperiod=slowperiod, matype=matype)

    def talib_AROON(self, timeperiod=14, **kwargs):
        """args:high, low
        lines:aroondown, aroonup"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return pd.concat(self.talib.AROON(*arg, timeperiod=timeperiod), axis=1)

    def talib_AROONOSC(self, timeperiod=14, **kwargs):
        """args:high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.AROONOSC(*arg, timeperiod=timeperiod)

    def talib_BOP(self, **kwargs):
        """args:open,high, low,close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        return self.talib.BOP(*arg, **kwarg)

    def talib_CCI(self, timeperiod=14, **kwargs):
        """args:high, low,close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.CCI(*arg, timeperiod=timeperiod)

    def talib_CMO(self, timeperiod=14, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.CMO(*arg, timeperiod=timeperiod)

    def talib_DX(self, timeperiod=14, **kwargs):
        """args:high, low,close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.DX(*arg, timeperiod=timeperiod)

    def talib_MACD(self, fastperiod=12, slowperiod=26, signalperiod=9, **kwargs):
        """args:close
        lines:dif, dem, histogram"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pd.concat(self.talib.MACD(*arg, fastperiod=fastperiod, slowperiod=slowperiod, signalperiod=signalperiod), axis=1)

    def talib_MACDEXT(self, fastperiod=12, fastmatype=0, slowperiod=26, slowmatype=0, signalperiod=9, signalmatype=0, **kwargs):
        """args:close
        lines:dif, dem, histogram"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pd.concat(self.talib.MACDEXT(*arg, fastperiod=fastperiod, fastmatype=fastmatype, slowperiod=slowperiod, slowmatype=slowmatype, signalperiod=signalperiod, signalmatype=signalmatype), axis=1)

    def talib_MACDFIX(self, signalperiod=9, **kwargs):
        """args:close
        lines:dif, dem, histogram"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pd.concat(self.talib.MACDFIX(*arg, signalperiod), axis=1)

    def talib_MFI(self, timeperiod=14, **kwargs):
        """args:high, low,close,volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLCV)
        return self.talib.MFI(*arg, timeperiod=timeperiod)

    def talib_MINUS_DI(self, timeperiod=14, **kwargs):
        """args:high, low,close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.MINUS_DI(*arg, timeperiod=timeperiod)

    def talib_MINUS_DM(self, timeperiod=14, **kwargs):
        """args:high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.MINUS_DM(*arg, timeperiod=timeperiod)

    def talib_MOM(self, timeperiod=10, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.MOM(*arg, timeperiod=timeperiod)

    def talib_PLUS_DI(self, timeperiod=14, **kwargs):
        """args:high, low,close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.PLUS_DI(*arg, timeperiod=timeperiod)

    def talib_PLUS_DM(self, timeperiod=14, **kwargs):
        """args:high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.PLUS_DM(*arg, timeperiod=timeperiod)

    def talib_PPO(self, fastperiod=12, slowperiod=26, matype=0, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.PPO(*arg, fastperiod=fastperiod, slowperiod=slowperiod, matype=matype)

    def talib_ROC(self, timeperiod=10, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.ROC(*arg, timeperiod=timeperiod)

    def talib_ROCP(self, timeperiod=10, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.ROCP(*arg, timeperiod=timeperiod)

    def talib_ROCR(self, timeperiod=10, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.ROCR(*arg, timeperiod=timeperiod)

    def talib_ROCR100(self, timeperiod=10, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.ROCR100(*arg, timeperiod=timeperiod)

    def talib_RSI(self, timeperiod=14, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.RSI(*arg, timeperiod=timeperiod)

    def talib_STOCH(self, fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0, **kwargs):
        """args:high, low,close
        lines:slowk, slowd """
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pd.concat(self.talib.STOCH(*arg, fastk_period=fastk_period, slowk_period=slowk_period, slowk_matype=slowk_matype, slowd_period=slowd_period, slowd_matype=slowd_matype), axis=1)

    def talib_STOCHF(self, fastk_period=5, fastd_period=3, fastd_matype=0, **kwargs):
        """args:high, low,close
        lines:fastk, fastd """
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return pd.concat(self.talib.STOCHF(*arg, fastk_period=fastk_period, fastd_period=fastd_period, fastd_matype=fastd_matype), axis=1)

    def talib_STOCHRSI(self, timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0, **kwargs):
        """args:close
        lines:fastk, fastd """
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pd.concat(self.talib.STOCHRSI(*arg, timeperiod=timeperiod, fastk_period=fastk_period, fastd_period=fastd_period, fastd_matype=fastd_matype), axis=1)

    def talib_TRIX(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.TRIX(*arg, timeperiod=timeperiod)

    def talib_ULTOSC(self, timeperiod1=7, timeperiod2=14, timeperiod3=28, **kwargs):
        """args:high, low,close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.ULTOSC(*arg, timeperiod1=timeperiod1, timeperiod2=timeperiod2, timeperiod3=timeperiod3)

    def talib_WILLR(self, timeperiod=14, **kwargs):
        """args:high, low,close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.WILLR(*arg, timeperiod=timeperiod)

    # Overlap Studies Functions
    def talib_BBANDS(self, timeperiod=5, nbdevup=2, nbdevdn=2, matype=0, **kwargs):
        """args:close
        lines:upperband, middleband, lowerband"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return pd.concat(self.talib.BBANDS(*arg, timeperiod=timeperiod, nbdevup=nbdevup, nbdevdn=nbdevdn, matype=matype), axis=1)

    def talib_DEMA(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.DEMA(*arg, timeperiod=timeperiod)

    def talib_EMA(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.EMA(*arg, timeperiod=timeperiod)

    def talib_HT_TRENDLINE(self, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.HT_TRENDLINE(*arg)

    def talib_KAMA(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.KAMA(*arg, timeperiod=timeperiod)

    def talib_MA(self, timeperiod=30, matype=0, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.MA(*arg, timeperiod=timeperiod, matype=matype)

    def talib_MAMA(self, fastlimit=0.06185, slowlimit=0.6185, **kwargs):
        """args:close
        lines:mama, fama"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.MAMA(*arg, fastlimit=fastlimit, slowlimit=slowlimit)

    def talib_MAVP(self, periods=14, minperiod=2, maxperiod=30, matype=0, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.MAVP(*arg, periods=periods, minperiod=minperiod, maxperiod=maxperiod, matype=matype)

    def talib_MIDPOINT(self, timeperiod=14, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.MIDPOINT(*arg, timeperiod=timeperiod)

    def talib_MIDPRICE(self, timeperiod=14, **kwargs):
        """args:high, low,"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.MIDPRICE(*arg, timeperiod=timeperiod)

    def talib_SAR(self, acceleration=0, maximum=0, **kwargs):
        """args:high, low,"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.SAR(*arg, acceleration=acceleration, maximum=maximum)

    def talib_SAREXT(self, startvalue=0, offsetonreverse=0, accelerationinitlong=0, accelerationlong=0, accelerationmaxlong=0, accelerationinitshort=0, accelerationshort=0, accelerationmaxshort=0, **kwargs):
        """args:high, low,"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.SAREXT(*arg, startvalue=startvalue, offsetonreverse=offsetonreverse, accelerationinitlong=accelerationinitlong, accelerationlong=accelerationlong, accelerationmaxlong=accelerationmaxlong,
                                 accelerationinitshort=accelerationinitshort, accelerationshort=accelerationshort, accelerationmaxshort=accelerationmaxshort)

    def talib_SMA(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.SMA(*arg, timeperiod=timeperiod)

    def talib_T3(self, timeperiod=5, vfactor=0, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.T3(*arg, timeperiod=timeperiod, vfactor=vfactor)

    def talib_TEMA(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.TEMA(*arg, timeperiod=timeperiod)

    def talib_TRIMA(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.TRIMA(*arg, timeperiod=timeperiod)

    def talib_WMA(self, timeperiod=30, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.WMA(*arg, timeperiod=timeperiod)

    # Pattern Recognition Functions 形态识别
    def talib_PatternRecognition(self, name="CDL2CROWS", penetration=0, **kwargs):
        """args:open, high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        ls = ["CDLDARKCLOUDCOVER", "CDLABANDONEDBABY", "CDLEVENINGDOJISTAR",
              "CDLEVENINGSTAR", "CDLMATHOLD", "CDLMORNINGDOJISTAR", "CDLMORNINGSTAR"]
        return eval(name)(*arg) if name not in ls else eval(name)(*arg, penetration=penetration)

    # Price Transform Functions
    def talib_AVGPRICE(self, **kwargs):
        """args:open, high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OHLC)
        return self.talib.AVGPRICE(*arg)

    def talib_MEDPRICE(self, **kwargs):
        """args:high, low,"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.MEDPRICE(*arg)

    def talib_TYPPRICE(self, **kwargs):
        """args:high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.TYPPRICE(*arg)

    def talib_WCLPRICE(self, **kwargs):
        """args:high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.WCLPRICE(*arg)

    # Statistic Functions 统计学指标
    def talib_BETA(self, timeperiod=5, **kwargs):
        """args:high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.BETA(*arg, timeperiod=timeperiod)

    def talib_CORREL(self, timeperiod=30, **kwargs):
        """args:high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return self.talib.CORREL(*arg, timeperiod=timeperiod)

    def talib_LINEARREG(self, timeperiod=14, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.LINEARREG(*arg, timeperiod=timeperiod)

    def talib_LINEARREG_ANGLE(self, timeperiod=14, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.LINEARREG_ANGLE(*arg, timeperiod=timeperiod)

    def talib_LINEARREG_INTERCEPT(self, timeperiod=14, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.LINEARREG_INTERCEPT(*arg, timeperiod=timeperiod)

    def talib_LINEARREG_SLOPE(self, timeperiod=14, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.LINEARREG_SLOPE(*arg, timeperiod=timeperiod)

    def talib_STDDEV(self, timeperiod=5, nbdev=1, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.STDDEV(*arg, timeperiod=timeperiod, nbdev=nbdev)

    def talib_TSF(self, timeperiod=14, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.TSF(*arg, timeperiod=timeperiod)

    def talib_VAR(self, timeperiod=5, nbdev=1, **kwargs):
        """args:close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.talib.VAR(*arg, timeperiod=timeperiod, nbdev=nbdev)

    # Volatility Indicator Functions 波动率指标函数
    def talib_ATR(self, timeperiod=14, **kwargs):
        """args:high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.ATR(*arg, timeperiod=timeperiod)

    def talib_NATR(self, timeperiod=14, **kwargs):
        """args:high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.NATR(*arg, timeperiod=timeperiod)

    def talib_TRANGE(self, **kwargs):
        """args:high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return self.talib.TRANGE(*arg)

    # Volume Indicators 成交量指标
    def talib_AD(self, **kwargs):
        """args:high, low, close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLCV)
        return self.talib.AD(*arg)

    def talib_ADOSC(self, fastperiod=3, slowperiod=10, **kwargs):
        """args:high, low, close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLCV)
        return self.talib.ADOSC(*arg, fastperiod=fastperiod, slowperiod=slowperiod)

    def talib_OBV(self, **kwargs):
        """args:close, volume"""
        arg, kwarg = self._get_column_(locals(), *FILED.CV)
        return self.talib.OBV(*arg)

    # tulipy指标
    # https://tulipindicators.org/list
    # https://github.com/TulipCharts/tulipy
    @property
    def tulipy(self) -> tulipy:
        ...

    def ti_abs(self, **kwargs):
        """Vector Absolute Value
        args:close"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.abs(*arg), self.length)

    def ti_acos(self, **kwargs):
        """Vector Arccosine
        args:close"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.acos(*arg), self.length)

    def ti_ad(self, **kwargs):
        """Accumulation/Distribution Line
        args:high, low, close, volume"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLCV)
        return pad_array_to_match(self.tulipy.ad(*arg), self.length)

    def ti_add(self, series=None, **kwargs):
        """Vector Addition
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        if hasattr(series, "values"):
            series = series.values
        if not ((isinstance(series, np.ndarray) and self.length == len(series)) or
                isinstance(series, (float, int))):
            return self
        arg.append(series)
        return pad_array_to_match(self.tulipy.add(*arg), self.length)

    def ti_adosc(self, short_period=10, long_period=10, **kwargs):
        """
        Accumulation/Distribution Oscillator
        args:high, low, close, volume
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLCV)
        arg.extend([short_period, long_period])
        return pad_array_to_match(self.tulipy.adosc(*arg), self.length)

    def ti_adx(self, period=10, **kwargs):
        """
        Average Directional Movement Index
        args:high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        arg.append(period)
        return pad_array_to_match(self.tulipy.adx(*arg), self.length)

    def ti_adxr(self, period=10, **kwargs):
        """
        Average Directional Movement Rating
        args:high, low, close"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        arg.append(period)
        return pad_array_to_match(self.tulipy.adxr(*arg), self.length)

    def ti_ao(self, **kwargs):
        """
        Awesome Oscillator
        args:high, low"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.HL)
        return pad_array_to_match(self.tulipy.ao(*arg), self.length)

    def ti_apo(self, short_period=12, long_period=26, **kwargs):
        """
        Absolute Price Oscillator
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.extend([short_period, long_period])
        return pad_array_to_match(self.tulipy.apo(*arg), self.length)

    def ti_aroon(self, period=10, **kwargs):
        """
        Aroon
        args:high, low
        return:2 lines
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HL)
        arg.append(period)
        return pad_array_to_match(self.tulipy.aroon(*arg), self.length)

    def ti_aroonosc(self, period=10, **kwargs):
        """
        Aroon Oscillator
        args:high, low
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HL)
        arg.append(period)
        return pad_array_to_match(self.tulipy.aroonosc(*arg), self.length)

    def ti_asin(self, **kwargs):
        """
        Vector Arcsine
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.asin(*arg), self.length)

    def ti_atan(self, **kwargs):
        """
        Vector Arctangent
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.atan(*arg), self.length)

    def ti_atr(self, period=10, **kwargs):
        """
        Average True Range
        args:high, low, close"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        arg.append(period)
        return pad_array_to_match(self.tulipy.atr(*arg), self.length)

    def ti_avgprice(self, **kwargs):
        """
        Average Price
        args:open, high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.OHLC)
        return pad_array_to_match(self.tulipy.avgprice(*arg), self.length)

    def ti_bbands(self, period=10, stddev=1., **kwargs):
        """
        Bollinger Bands
        args:close
        return:3 lines
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.extend([period, stddev])
        return pad_array_to_match(self.tulipy.bbands(*arg), self.length)

    def ti_bop(self, **kwargs):
        """
        Balance of Power
        args:open, high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.OHLC)
        return pad_array_to_match(self.tulipy.bop(*arg), self.length)

    def ti_cci(self, period=10, **kwargs):
        """
        Commodity Channel Index
        args:high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        arg.append(period)
        return pad_array_to_match(self.tulipy.cci(*arg), self.length)

    def ceil(self, **kwargs):
        """
        Vector Ceiling
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.ceil(*arg), self.length)

    def ti_cmo(self, period=10, **kwargs):
        """
        Chande Momentum Oscillator
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.cmo(*arg), self.length)

    def ti_cos(self, **kwargs):
        """
        Vector Cosine
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.cos(*arg), self.length)

    def ti_cosh(self, **kwargs):
        """
        Vector Hyperbolic Cosine
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.cosh(*arg), self.length)

    def ti_crossany(self, series=None, **kwargs):
        """
        Crossany
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        if hasattr(series, "values"):
            series = series.values
        if not ((isinstance(series, np.ndarray) and self.length == len(series)) or
                isinstance(series, (float, int))):
            return self
        arg.append(series)
        return pad_array_to_match(self.tulipy.crossany(*arg), self.length)

    def ti_crossover(self, series=None, **kwargs):
        """
        Crossover
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        if hasattr(series, "values"):
            series = series.values
        if not ((isinstance(series, np.ndarray) and self.length == len(series)) or
                isinstance(series, (float, int))):
            return self
        arg.append(series)
        return pad_array_to_match(self.tulipy.crossover(*arg), self.length)

    def ti_cvi(self, period=10, **kwargs):
        """
        Chaikins Volatility
        args:high, low
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HL)
        arg.append(period)
        return pad_array_to_match(self.tulipy.cvi(*arg), self.length)

    def ti_decay(self, period=10, **kwargs):
        """
        Linear Decay
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.decay(*arg), self.length)

    def ti_dema(self, period=10, **kwargs):
        """
        Double Exponential Moving Average
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.dema(*arg), self.length)

    def ti_di(self, period=10, **kwargs):
        """
        Directional Indicator
        args:high, low, close
        return:2 lines
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        arg.append(period)
        return pad_array_to_match(self.tulipy.di(*arg), self.length)

    def ti_div(self, series=None, **kwargs):
        """
        Vector Division
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        if hasattr(series, "values"):
            series = series.values
        if not ((isinstance(series, np.ndarray) and self.length == len(series)) or
                isinstance(series, (float, int))):
            return self
        arg.append(series)
        return pad_array_to_match(self.tulipy.div(*arg), self.length)

    def ti_dm(self, period=10, **kwargs):
        """
        Directional Movement
        args:high, low
        return:2 lines
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HL)
        arg.append(period)
        return pad_array_to_match(self.tulipy.dm(*arg), self.length)

    def ti_dpo(self, period=10, **kwargs):
        """
        Detrended Price Oscillator
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.dpo(*arg), self.length)

    def ti_dx(self, period=10, **kwargs):
        """
        Directional Movement Index
        args:high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        arg.append(period)
        return pad_array_to_match(self.tulipy.dx(*arg), self.length)

    def ti_edecay(self, period=10, **kwargs):
        """
        Exponential Decay
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.edecay(*arg), self.length)

    def ti_ema(self, period=10, **kwargs):
        """
        Exponential Moving Average
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.ema(*arg), self.length)

    def ti_emv(self, **kwargs):
        """
        Ease of Movement
        args:high, low, volume
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLV)
        return pad_array_to_match(self.tulipy.emv(*arg), self.length)

    def ti_exp(self, **kwargs):
        """
        Vector Exponential
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.exp(*arg), self.length)

    def ti_fisher(self, period=10, **kwargs):
        """
        Fisher Transform
        args:high, low
        return:2 lines
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HL)
        arg.append(period)
        return pad_array_to_match(self.tulipy.fisher(*arg), self.length)

    def ti_floor(self, **kwargs):
        """
        Vector Floor
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.floor(*arg), self.length)

    def ti_fosc(self, period=10, **kwargs):
        """
        Forecast Oscillator
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.fosc(*arg), self.length)

    def ti_hma(self, period=10, **kwargs):
        """
        Hull Moving Average
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.hma(*arg), self.length)

    def ti_kama(self, period=10, **kwargs):
        """
        Kaufman Adaptive Moving Average
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.kama(*arg), self.length)

    def ti_kvo(self, short_period=10, long_period=10, **kwargs):
        """
        Klinger Volume Oscillator
        args:high, low, close, volume
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLCV)
        arg.extend([short_period, long_period])
        return pad_array_to_match(self.tulipy.kvo(*arg), self.length)

    def ti_lag(self, period=10, **kwargs):
        """
        Lag
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.lag(*arg), self.length)

    def ti_linreg(self, period=10, **kwargs):
        """
        Linear Regression
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.linreg(*arg), self.length)

    def ti_linregintercept(self, period=10, **kwargs):
        """
        Linear Regression Intercept
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.linregintercept(*arg), self.length)

    def ti_linregslope(self, period=10, **kwargs):
        """
        Linear Regression Slope
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.linregslope(*arg), self.length)

    def ti_ln(self, **kwargs):
        """
        Vector Natural Log
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.ln(*arg), self.length)

    def ti_log10(self, **kwargs):
        """
        Vector Base-10 Log
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.log10(*arg), self.length)

    def ti_macd(self, short_period=12, long_period=26, signal_period=9, **kwargs):
        """
        Moving Average Convergence/Divergence
        args:close
        return:3 lines
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.extend([short_period, long_period, signal_period])
        return pad_array_to_match(self.tulipy.macd(*arg), self.length)

    def ti_marketfi(self, **kwargs):
        """
        Market Facilitation Index
        args:high, low, volume"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        return pad_array_to_match(self.tulipy.marketfi(*arg), self.length)

    def ti_mass(self, period=10, **kwargs):
        """
        Mass Index
        args:high, low
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HL)
        arg.append(period)
        return pad_array_to_match(self.tulipy.mass(*arg), self.length)

    def ti_max(self, period=10, **kwargs):
        """
        Maximum In Period
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.max(*arg), self.length)

    def ti_md(self, period=10, **kwargs):
        """
        Mean Deviation Over Period
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.md(*arg), self.length)

    def ti_medprice(self, **kwargs):
        """
        Median Price
        args:high, low
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HL)
        return pad_array_to_match(self.tulipy.medprice(*arg), self.length)

    def ti_mfi(self, period=10, **kwargs):
        """
        Money Flow Index
        args:high, low, close, volume
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLCV)
        arg.append(period)
        return pad_array_to_match(self.tulipy.mfi(*arg), self.length)

    def ti_min(self, period=10, **kwargs):
        """
        Minimum In Period
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.min(*arg), self.length)

    def ti_mom(self, period=10, **kwargs):
        """
        Momentum
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.mom(*arg), self.length)

    def ti_msw(self, period=10, **kwargs):
        """
        Mesa Sine Wave
        args:close
        return:2 lines
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.msw(*arg), self.length)

    def ti_mul(self, series=None, **kwargs):
        """
        Vector Multiplication
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        if hasattr(series, "values"):
            series = series.values
        if not ((isinstance(series, np.ndarray) and self.length == len(series)) or
                isinstance(series, (float, int))):
            return self
        arg.append(series)
        return pad_array_to_match(self.tulipy.mul(*arg), self.length)

    def natr(self, period=10, **kwargs):
        """
        Normalized Average True Range
        args:high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        arg.append(period)
        return pad_array_to_match(self.tulipy.natr(*arg), self.length)

    def ti_nvi(self, **kwargs):
        """
        Negative Volume Index
        args:close, volume
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.CV)
        return pad_array_to_match(self.tulipy.nvi(*arg), self.length)

    def ti_obv(self, **kwargs):
        """
        On Balance Volume
        args:close, volume
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.CV)
        return pad_array_to_match(self.tulipy.obv(*arg), self.length)

    def ti_ppo(self, short_period=10, long_period=10, **kwargs):
        """
        Percentage Price Oscillator
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.extend([short_period, long_period])
        return pad_array_to_match(self.tulipy.ppo(*arg), self.length)

    def ti_psar(self, acceleration_factor_step=0.06185, acceleration_factor_maximum=0.6185, **kwargs):
        """
        Parabolic SAR
        args:high, low
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HL)
        arg.extend([acceleration_factor_step, acceleration_factor_maximum])
        return pad_array_to_match(self.tulipy.psar(*arg), self.length)

    def ti_qstick(self, period=10, **kwargs):
        """
        Qstick
        args:open, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.OC)
        arg.append(period)
        return pad_array_to_match(self.tulipy.qstick(*arg), self.length)

    def ti_roc(self, period=10, **kwargs):
        """
        Rate of Change
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.roc(*arg), self.length)

    def ti_rocr(self, period=10, **kwargs):
        """
        Rate of Change Ratio
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.rocr(*arg), self.length)

    def ti_round(self, **kwargs):
        """
        Vector Round
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.round(*arg), self.length)

    def ti_rsi(self, period=10, **kwargs):
        """
        Relative Strength Index
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.rsi(*arg), self.length)

    def ti_sin(self, **kwargs):
        """
        Vector Sine
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.sin(*arg), self.length)

    def ti_sinh(self, **kwargs):
        """
        Vector Hyperbolic Sine
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.sinh(*arg), self.length)

    def ti_sma(self, period=10, **kwargs):
        """
        Simple Moving Average
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.sma(*arg), self.length)

    def ti_sqrt(self, **kwargs):
        """
        Vector Square Root
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.sqrt(*arg), self.length)

    def ti_stddev(self, period=10, **kwargs):
        """
        Standard Deviation Over Period
        args:close"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.stddev(*arg), self.length)

    def stderr(self, period=10, **kwargs):
        """
        Standard Error Over Period
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.stderr(*arg), self.length)

    def stoch(self, pct_k_period=3, pct_k_slowing_period=6, pct_d_period=3, **kwargs):
        """
        Stochastic Oscillator
        args:high, low, close
        retrun:2 lines
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        arg.extend([pct_k_period, pct_k_slowing_period, pct_d_period])
        return pad_array_to_match(self.tulipy.stoch(*arg), self.length)

    def stochrsi(self, period=10, **kwargs):
        """
        Stochastic RSI
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.stochrsi(*arg), self.length)

    def ti_sub(self, series=None, **kwargs):
        """
        Vector Subtraction
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        if hasattr(series, "values"):
            series = series.values
        if not ((isinstance(series, np.ndarray) and self.length == len(series)) or
                isinstance(series, (float, int))):
            return self
        arg.append(series)
        return pad_array_to_match(self.tulipy.sub(*arg), self.length)

    def ti_sum(self, period=10, **kwargs):
        """
        Sum Over Period
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.sum(*arg), self.length)

    def ti_tan(self, **kwargs):
        """
        Vector Tangent
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.tan(*arg), self.length)

    def ti_tanh(self, **kwargs):
        """
        Vector Hyperbolic Tangent
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.tanh(*arg), self.length)

    def ti_tema(self, period=10, **kwargs):
        """
        Triple Exponential Moving Average
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.tema(*arg), self.length)

    def ti_todeg(self, **kwargs):
        """
        Vector Degree Conversion
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.todeg(*arg), self.length)

    def ti_torad(self, **kwargs):
        """
        Vector Radian Conversion
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.torad(*arg), self.length)

    def ti_tr(self, **kwargs):
        """
        True Range
        args:high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        return pad_array_to_match(self.tulipy.tr(*arg), self.length)

    def ti_trima(self, period=10, **kwargs):
        """
        Triangular Moving Average
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.trima(*arg), self.length)

    def ti_trix(self, period=10, **kwargs):
        """
        Trix
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.trix(*arg), self.length)

    def ti_trunc(self, **kwargs):
        """
        Vector Truncate
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        return pad_array_to_match(self.tulipy.trunc(*arg), self.length)

    def ti_tsf(self, period=10, **kwargs):
        """
        Time Series Forecast
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.tsf(*arg), self.length)

    def ti_typprice(self, **kwargs):
        """
        Typical Price
        args:high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        return pad_array_to_match(self.tulipy.typprice(*arg), self.length)

    def ti_ultosc(self, short_period=10, medium_period=10, long_period=10, **kwargs):
        """
        Ultimate Oscillator
        args:high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        arg.extend([short_period, medium_period, long_period])
        return pad_array_to_match(self.tulipy.ultosc(*arg), self.length)

    def ti_var(self, period=10, **kwargs):
        """
        Variance Over Period
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.var(*arg), self.length)

    def ti_vhf(self, period=10, **kwargs):
        """
        Vertical Horizontal Filter
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.vhf(*arg), self.length)

    def ti_vidya(self, short_period=10, long_period=10, alpha=0.1):
        """
        Variable Index Dynamic Average
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.extend([short_period, long_period, alpha])
        return pad_array_to_match(self.tulipy.vidya(*arg), self.length)

    def ti_volatility(self, period=10, **kwargs):
        """
        Annualized Historical Volatility
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.volatility(*arg), self.length)

    def ti_vosc(self, short_period=10, long_period=10, **kwargs):
        """
        Volume Oscillator
        args:volume"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.V)
        arg.extend([short_period, long_period])
        return pad_array_to_match(self.tulipy.vosc(*arg), self.length)

    def ti_vwma(self, period=10, **kwargs):
        """
        Volume Weighted Moving Average
        args:close, volume
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.CV)
        arg.append(period)
        return pad_array_to_match(self.tulipy.vwma(*arg), self.length)

    def ti_wad(self, **kwargs):
        """
        Williams Accumulation/Distribution
        args:high, low, close"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        return pad_array_to_match(self.tulipy.wad(*arg), self.length)

    def ti_wcprice(self, **kwargs):
        """
        Weighted Close Price
        args:high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        return pad_array_to_match(self.tulipy.wcprice(*arg), self.length)

    def ti_wilders(self, period=10, **kwargs):
        """
        Wilders Smoothing
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.wilders(*arg), self.length)

    def ti_willr(self, period=10, **kwargs):
        """
        Williams %R
        args:high, low, close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.HLC)
        arg.append(period)
        return pad_array_to_match(self.tulipy.willr(*arg), self.length)

    def ti_wma(self, period=10, **kwargs):
        """
        Weighted Moving Average
        args:close
        """
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.wma(*arg), self.length)

    def ti_zlema(self, period=10, **kwargs):
        """
        Zero-Lag Exponential Moving Average
        args:close"""
        arg, kwarg = self._ti_get_data(locals(), *FILED.C)
        arg.append(period)
        return pad_array_to_match(self.tulipy.zlema(*arg), self.length)

    # finta指标
    @property
    def FinTa(self) -> FinTa:
        ...

    def finta_SMA(self, period: int = 41, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.SMA(data, period)

    def finta_SMM(self, period: int = 9, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.SMM(data, period)

    def finta_SSMA(self, period: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.SSMA(data, period, adjust=adjust)

    def finta_EMA(self, period: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.EMA(data, period, adjust=adjust)

    def finta_DEMA(self, period: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.DEMA(data, period, adjust=adjust)

    def finta_TEMA(self, period: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.DEMA(data, period, adjust=adjust)

    def finta_TRIMA(self, period: int = 18, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.TRIMA(data, period)

    def finta_TRIX(self, period: int = 20, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.TRIX(data, period, adjust=adjust)

    def finta_LWMA(self, period: int, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.LWMA(data, period)

    def finta_VAMA(self, period: int = 8, **kwargs):
        """args:ohlcv,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.VAMA(data, period)

    def finta_VIDYA(self, period: int = 9, smoothing_period: int = 12, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.VIDYA(data, period, smoothing_period)

    def finta_ER(self, period: int = 10, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.ER(data, period)

    def finta_KAMA(self, er: int = 10, ema_fast: int = 2, ema_slow: int = 30, period: int = 20, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.KAMA(data, er, ema_fast, ema_slow, period)

    def finta_ZLEMA(self, period: int = 26, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.ZLEMA(data, period, adjust)

    def finta_WMA(self, period: int = 9, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.WMA(data, period)

    def finta_HMA(self, period: int = 16, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.HMA(data, period)

    def finta_EVWMA(self, period: int = 20, **kwargs):
        """args:ohlcv,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.EVWMA(data, period)

    def finta_VWAP(self, **kwargs):
        """args:ohlcv,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.VWAP(data)

    def finta_SMMA(self, period: int = 42, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.SMMA(data, period, adjust=adjust)

    def finta_ALMA(self, period: int = 9, sigma: int = 6, offset: int = 0.85, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.ALMA(data, period, sigma, offset)

    def finta_MAMA(self, period: int = 16, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.MAMA(data, period)

    def finta_FRAMA(self, period: int = 16, batch: int = 10, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.FRAMA(data, period, batch)

    def finta_MACD(self, period_fast: int = 12, period_slow: int = 26, signal: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.MACD(data, period_fast, period_slow, signal, adjust=adjust)

    def finta_PPO(self, period_fast: int = 12, period_slow: int = 26, signal: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.PPO(data, period_fast, period_slow, signal, adjust=adjust)

    def finta_VW_MACD(self, period_fast: int = 12, period_slow: int = 26, signal: int = 9, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.VW_MACD(data, period_fast, period_slow, signal, adjust=adjust)

    def finta_EV_MACD(self, period_fast: int = 20, period_slow: int = 40, signal: int = 9, adjust: bool = True, **kwargs):
        """args:ohlcv,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.EV_MACD(data, period_fast, period_slow, signal, adjust=adjust)

    def finta_MOM(self, period: int = 10, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.MOM(data, period)

    def finta_ROC(self, period: int = 12, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.ROC(data, period)

    def finta_VBM(self, roc_period: int = 12, atr_period: int = 26, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.VBM(data, roc_period, atr_period)

    def finta_RSI(self, period: int = 14, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.RSI(data, period, adjust=adjust)

    def finta_IFT_RSI(self, rsi_period: int = 5, wma_period: int = 9, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.IFT_RSI(data, "close", rsi_period, wma_period)

    def finta_SWI(self, period: int = 16, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.SWI(data, period)

    def finta_DYMI(self, adjust: bool = True, **kwargs):
        """args:close,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.DYMI(data, adjust=adjust)

    def finta_TR(self, **kwargs):
        """args:ohlcv,kwargs:filed"""
        data = self._finta_get_data(**kwargs)
        return self.FinTa.TR(data)

    def finta_ATR(self, period: int = 14, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.TR(data, period)

    def finta_SAR(self, af: int = 0.02, amax: int = 0.2, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.SAR(data, af, amax)

    def finta_PSAR(self, iaf: int = 0.02, maxaf: int = 0.2, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.PSAR(data, iaf, maxaf)

    def finta_BBANDS(self, period: int = 20, MA: pd.Series = None, std_multiplier: float = 2, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.BBANDS(data, period, MA, std_multiplier=std_multiplier)

    def finta_MOBO(self, period: int = 10, std_multiplier: float = 0.8, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.MOBO(data, period, std_multiplier)

    def finta_BBWIDTH(self, period: int = 20, MA: pd.Series = None, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.BBWIDTH(data, period, MA)

    def finta_PERCENT_B(self, period: int = 20, MA: pd.Series = None, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.PERCENT_B(data, period, MA)

    def finta_KC(self, period: int = 20, atr_period: int = 10, MA: pd.Series = None, kc_mult: float = 2, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.KC(data, period, atr_period, MA, kc_mult)

    def finta_DO(self, upper_period: int = 20, lower_period: int = 5, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.DO(data, upper_period, lower_period)

    def finta_DMI(self, period: int = 14, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.DMI(data, period, adjust)

    def finta_ADX(self, period: int = 14, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.ADX(data, period, adjust)

    def finta_PIVOT(self, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.PIVOT(data)

    def finta_PIVOT_FIB(self, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.PIVOT_FIB(data)

    def finta_STOCH(self, period: int = 14, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.STOCH(data, period)

    def finta_STOCHD(self, period: int = 3, stoch_period: int = 14, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.STOCHD(data, period, stoch_period)

    def finta_STOCHRSI(self, rsi_period: int = 14, stoch_period: int = 14, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.STOCHRSI(data, rsi_period, stoch_period)

    def finta_WILLIAMS(self, period: int = 14, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.WILLIAMS(data, period)

    def finta_UO(self, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.UO(data)

    def finta_AO(self, slow_period: int = 34, fast_period: int = 5, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.AO(data, slow_period, fast_period)

    def finta_MI(self, period: int = 9, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.MI(data, period, adjust)

    def finta_BOP(self, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.BOP(data)

    def finta_VORTEX(self, period: int = 14, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.VORTEX(data, period)

    def finta_KST(self, r1: int = 10, r2: int = 15, r3: int = 20, r4: int = 30, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.KST(data, r1, r2, r3, r4)

    def finta_TSI(self, long: int = 25, short: int = 13, signal: int = 13, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.TSI(data, long, short, signal, adjust=adjust)

    def finta_TP(self, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.TP(data)

    def finta_ADL(self, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.ADL(data)

    def finta_CHAIKIN(self, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.CHAIKIN(data, adjust)

    def finta_MFI(self, period: int = 14, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.CHAIKIN(data, period)

    def finta_OBV(self, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.OBV(data)

    def finta_WOBV(self, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.WOBV(data)

    def finta_VZO(self, period: int = 14, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.VZO(data, period, adjust=adjust)

    def finta_PZO(self, period: int = 14, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.PZO(data, period, adjust=adjust)

    def finta_EFI(self, period: int = 13, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.EFI(data, period, adjust=adjust)

    def finta_CFI(self, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.CFI(data, adjust=adjust)

    def finta_EBBP(self, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.EBBP(data)

    def finta_EMV(self, period: int = 14, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.EMV(data, period)

    def finta_CCI(self, period: int = 20, constant: float = 0.015, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.CCI(data, period, constant)

    def finta_COPP(self, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.COPP(data, adjust)

    def finta_BASP(self, period: int = 40, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.BASP(data, period, adjust)

    def finta_BASPN(self, period: int = 40, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.BASPN(data, period, adjust)

    def finta_CMO(self, period: int = 9, factor: int = 100, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.CMO(data, period, factor, adjust=adjust)

    def finta_CHANDELIER(self, short_period: int = 22, long_period: int = 22, k: int = 3, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.CHANDELIER(data, short_period, long_period, k)

    def finta_QSTICK(self, period: int = 14, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.QSTICK(data, period)

    def finta_TMF(self, period: int = 21, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.TMF(data, period)

    def finta_WTO(self, channel_length: int = 10, average_length: int = 21, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.WTO(data, channel_length, average_length, adjust)

    def finta_FISH(self, period: int = 10, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.FISH(data, period, adjust)

    def finta_ICHIMOKU(self, tenkan_period: int = 9, kijun_period: int = 26, senkou_period: int = 52, chikou_period: int = 26, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.ICHIMOKU(data, tenkan_period, kijun_period, senkou_period, chikou_period)

    def finta_APZ(self, period: int = 21, dev_factor: int = 2, MA: pd.Series = None, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.APZ(data, period, dev_factor, MA, adjust)

    def finta_SQZMI(self, period: int = 20, MA: pd.Series = None, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.SQZMI(data, period, MA)

    def finta_VPT(self, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.SQZMI(data)

    def finta_FVE(self, period: int = 22, factor: int = 0.3, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.FVE(data, period, factor)

    def finta_VFI(self, period: int = 130, smoothing_factor: int = 3, factor: int = 0.2, vfactor: int = 2.5, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.VFI(data, period, smoothing_factor, factor, vfactor, adjust)

    def finta_MSD(self, period: int = 21, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.MSD(data, period)

    def finta_STC(self, period_fast: int = 23, period_slow: int = 50, k_period: int = 10, d_period: int = 3, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.STC(data, period_fast, period_slow, k_period, d_period, adjust=adjust)

    def finta_EVSTC(self, period_fast: int = 12, period_slow: int = 30, k_period: int = 10, d_period: int = 3, adjust: bool = True, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.EVSTC(data, period_fast, period_slow, k_period, d_period, adjust=adjust)

    def finta_WILLIAMS_FRACTAL(self, period: int = 2, **kwargs):
        data = self._finta_get_data(**kwargs)
        return self.FinTa.WILLIAMS_FRACTAL(data, period)

    def finta_VC(self, period: int = 5, **kwargs):
        ohlc = self._finta_get_data(**kwargs)
        float_axis = ((ohlc.high + ohlc.low) / 2).rolling(window=period).mean()
        vol_unit = (ohlc.high - ohlc.low).rolling(window=period).mean() * 0.2

        value_chart_high = pd.Series(
            (ohlc.high - float_axis) / vol_unit, name="Value Chart High")
        value_chart_low = pd.Series(
            (ohlc.low - float_axis) / vol_unit, name="Value Chart Low")
        value_chart_close = pd.Series(
            (ohlc.close - float_axis) / vol_unit, name="Value Chart Close")
        value_chart_open = pd.Series(
            (ohlc.open - float_axis) / vol_unit, name="Value Chart Open")
        return pd.concat([value_chart_high, value_chart_low, value_chart_close, value_chart_open], axis=1)

    def finta_WAVEPM(self, period: int = 14, lookback_period: int = 100, **kwargs):
        ohlc = self._finta_get_data(**kwargs)
        ma = ohlc['close'].rolling(window=period).mean()
        std = ohlc['close'].rolling(window=period).std(ddof=0)

        def tanh(x):
            two = np.where(x > 0, -2, 2)
            what = two * x
            ex = np.exp(what)
            j = 1 - ex
            k = ex - 1
            l = np.where(x > 0, j, k)
            output = l / (1 + ex)
            return output

        def osc(input_dev, mean, power):
            variance = pd.Series(power).rolling(
                window=lookback_period).sum() / lookback_period
            calc_dev = np.sqrt(variance) * mean
            y = (input_dev / calc_dev)
            oscLine = tanh(y)
            return oscLine

        dev = 3.2 * std
        power = np.power(dev / ma, 2)
        wavepm = osc(dev, ma, power)

        return pd.Series(wavepm, name="{0} period WAVEPM".format(period))

    @property
    def autotrader(self) -> autotrader:
        ...

    # autoatrader
    def autotrader_supertrend(self, period: int = 10, multiplier: float = 3.0, source: pd.Series = None, **kwargs):
        """args:ohlcv
        lines:uptrend,downtrend,trend
        """
        data = self._finta_get_data(**kwargs)
        return self.autotrader.supertrend(data, period, multiplier, source)

    def autotrader_halftrend(self, amplitude: int = 2, channel_deviation: float = 2, **kwargs):
        """args:ohlcv
        lines:halftrend,atrHigh,atrLow,buy,sell
        """
        data = self._finta_get_data(**kwargs)
        return self.autotrader.halftrend(data, amplitude, channel_deviation)

    def autotrader_range_filter(self, range_qty: float = 2.618, range_period: int = 14, smooth_range: bool = True, smooth_period: int = 27,
                                av_vals: bool = False, av_samples: int = 2, mov_source: str = "body", filter_type: int = 1, **kwargs):
        """args:ohlcv
        lines:upper,lower,rf,fdir
        """
        data = self._finta_get_data(**kwargs)
        return self.autotrader.range_filter(data, range_qty, range_period, smooth_range, smooth_period, av_vals, av_samples, mov_source, filter_type)

    def autotrader_bullish_engulfing(self, detection: str = None, **kwargs):
        """args:ohlcv
        detection:SMA50,SMA50/200
        """
        data = self._finta_get_data(**kwargs)
        return self.autotrader.bullish_engulfing(data, detection)

    def autotrader_bearish_engulfing(self, detection: str = None, **kwargs):
        """args:ohlcv
        detection:SMA50,SMA50/200
        """
        data = self._finta_get_data(**kwargs)
        return self.autotrader.bearish_engulfing(data, detection)

    def autotrader_find_swings(self, n: int = 2, **kwargs):
        """args:ohlcv
        lines:Highs,Lows,Last,Trend
        """
        data = self._finta_get_data(**kwargs)
        return self.autotrader.find_swings(data, n)

    def autotrader_classify_swings(self, tol: int = 0, **kwargs):
        """args:swing_df  The dataframe returned by self.data.find_swings.
        lines:CSLS,Support,Resistance,Strong_lows,Strong_highs,FSL,FSH,LL,HL,HH,LH
        """
        data = self._finta_get_data(**kwargs)
        return self.autotrader.classify_swings(data, tol)

    def autotrader_detect_divergence(self, classified_price_swings: pd.DataFrame, classified_indicator_swings: pd.DataFrame, tol: int = 2, method: int = 0, **kwargs):
        """
        classified_price_swings : pd.DataFrame
            The output from classify_swings using OHLC data.

        classified_indicator_swings : pd.DataFrame
            The output from classify_swings using indicator data.
        lines:regularBull,regularBear,hiddenBull,hiddenBear
        """
        # data = self._finta_get_data(**kwargs)
        return self.autotrader.detect_divergence(classified_price_swings, classified_indicator_swings, tol, method)

    def autotrader_autodetect_divergence(self, indicator_data: pd.DataFrame, tolerance: int = 1, method: int = 0, **kwargs):
        """args:ohlcv
        indicator_data:dataframe of indicator data. self.data.detect_divergence
        lines:regularBull,regularBear,hiddenBull,hiddenBear
        """
        data = self._finta_get_data(**kwargs)
        return self.autotrader.autodetect_divergence(indicator_data, tolerance, method)

    def autotrader_heikin_ashi(self, **kwargs):
        """args:ohlcv
        lines:open,high,low,close
        """
        data = self._finta_get_data(**kwargs)
        return self.autotrader.heikin_ashi(data)

    def autotrader_ha_candle_run(self, **kwargs):
        """args:ha_data
        lines:up,dn
        """
        data = self._finta_get_data(**kwargs)
        return self.autotrader.ha_candle_run(data)

    def autotrader_N_period_high(self, N: int, **kwargs):
        """args:high"""
        data = self._finta_get_data(**kwargs)
        return self.autotrader.N_period_high(data)

    def autotrader_N_period_low(self, N: int, **kwargs):
        """args: low."""
        data = self._finta_get_data(**kwargs)
        return self.autotrader.N_period_low(data)

    def autotrader_crossover(self, ts2: pd.Series, **kwargs):
        """args:close
        """
        return self.autotrader.crossover(self, ts2)

    def autotrader_cross_values(self, ts2: pd.Series, **kwargs):
        """args:close
        """
        return self.autotrader.cross_values(self, ts2)

    def autotrader_candles_between_crosses(self, crosses: Union[list, pd.Series], initial_count: int = 0, **kwargs):
        """args:None
        """
        return self.autotrader.candles_between_crosses(crosses, initial_count)

    def autotrader_rolling_signal_list(self, signals: Union[list, pd.Series], **kwargs):
        """args:None

        """
        return self.autotrader.rolling_signal_list(signals)

    def autotrader_unroll_signal_list(self, signals: Union[list, pd.Series], **kwargs):
        """args:None
        """
        return self.autotrader.unroll_signal_list(signals)

    def autotrader_merge_signals(self, signal_1: list, signal_2: list, **kwargs):
        """args:None
        """
        return self.autotrader.merge_signals(signal_1, signal_2)

    def autotrader_build_grid_price_levels(self, grid_origin: float, grid_space: float, grid_levels: int, grid_price_space: float = None, pip_value: float = 0.0001, **kwargs) -> np.array:
        """Generates grid price levels."""
        # Calculate grid spacing in price units
        return self.autotrader.build_grid_price_levels(grid_origin, grid_space, grid_levels, grid_price_space, pip_value)

    def autotrader_build_grid(self, grid_origin: float, grid_space: float, grid_levels: int, order_direction: int, order_type: str = "stop-limit",
                              grid_price_space: float = None, pip_value: float = 0.0001, take_distance: float = None, stop_distance: float = None, stop_type: str = None, **kwargs) -> dict:
        """Generates a grid of orders.
        dict:dict[int,dict]"""

        return self.autotrader.build_grid(grid_origin, grid_space, grid_levels, order_direction, order_type, grid_price_space, pip_value, take_distance, stop_distance, stop_type)

    def autotrader_merge_grid_orders(self, grid_1: np.array, grid_2: np.array, **kwargs) -> np.array:
        """Merges grid dictionaries into one and re-labels order numbers so each
        order number is unique.
        """
        return self.autotrader.merge_grid_orders(grid_1, grid_2)

    def autotrader_last_level_crossed(self, base: float, **kwargs):
        """args:ohlcv"""
        data = self._finta_get_data(**kwargs)
        return self.autotrader.last_level_crossed(data, base)

    def autotrader_build_multiplier_grid(self, origin: float, direction: int, multiplier: float, no_levels: int, precision: int, spacing: float, **kwargs):
        """args:None
        """
        return self.autotrader.build_multiplier_grid(origin, direction, multiplier, no_levels, precision, spacing)

    def autotrader_last_level_touched(self, grid: np.array, **kwargs) -> np.array:
        """args:ohlcv"""
        data = self._finta_get_data(**kwargs)
        return self.autotrader.last_level_touched(data, grid)

    def autotrader_stoch_rsi(self, K_period: int = 3, D_period: int = 3, RSI_length: int = 14, Stochastic_length: int = 14, **kwargs):
        """args:ohlcv
        lines:k,d"""
        data = self._finta_get_data(**kwargs)
        return self.autotrader.stoch_rsi(data, K_period, D_period, RSI_length, Stochastic_length)

    def autotrader_stochastic(self, period: int = 14, **kwargs) -> pd.Series:
        """args:ohlcv"""
        data = self._finta_get_data(**kwargs)
        return self.autotrader.stochastic(data, period)

    def autotrader_sma(self, period: int = 14, **kwargs):
        """args:close"""
        return self.autotrader.sma(self, period)

    def autotrader_ema(self, period: int = 14, smoothing: int = 2, **kwargs):
        """args:close"""
        return self.autotrader.ema(self, period, smoothing)

    def autotrader_true_range(self, period: int = 14, **kwargs):
        """args:ohlcv"""
        data = self._finta_get_data(**kwargs)
        return self.autotrader.true_range(data, period)

    def autotrader_atr(self, period: int = 14, **kwargs):
        """args:ohlcv"""
        data = self._finta_get_data(**kwargs)
        return self.autotrader.atr(data, period)

    def autotrader_create_bricks(self, brick_size: float = 0.002, column: str = "close", **kwargs):
        """args:ohlcw
        lines:open,close"""
        data = self._finta_get_data(**kwargs)
        return self.autotrader.create_bricks(data, brick_size, column)

    def autotrader_chandelier_exit(self, length: int = 22, mult: float = 3.0, use_close: bool = False, **kwargs):
        """args:ohlcv
        lines:longstop,shortstop,direction,signal"""
        data = self._finta_get_data(**kwargs)
        return self.autotrader.chandelier_exit(data, length, mult, use_close)

    # 天勤指标
    def tq_ref(self, length=10, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.ref(*arg, **kwarg)

    def tq_std(self, length: int = 10, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.std(*arg, **kwarg)

    def tq_ma(self, length: int = 10, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.ma(*arg, **kwarg)

    def tq_sma(self, n: int = 10, m: int = 2, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.sma(*arg, **kwarg)

    def tq_ema(self, length: int = 10, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.ema(*arg, **kwarg)

    def tq_ema2(self, length: int = 10, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.ema2(*arg, **kwarg)

    def tq_crossup(self, b=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        b = kwarg.pop('b')
        return TqFunc.crossup(*arg, b=b, **kwarg)

    def tq_crossdown(self, b=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        b = kwarg.pop('b')
        return TqFunc.crossdown(*arg, b=b, **kwarg)

    def tq_count(self, cond=None, length: int = 10, **kwargs):
        kwarg = self._get_column_(locals())
        return TqFunc.count(**kwarg)

    def tq_trma(self, length: int = 10, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.trma(*arg, **kwarg)

    def tq_harmean(self, length: int = 10, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.harmean(*arg, **kwarg)

    def tq_numpow(self, n: int = 10, m: int = 2, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.numpow(*arg, **kwarg)

    def tq_abs(self, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.abs(*arg, **kwarg)

    def tq_min(self, b=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        a = kwarg.pop('a', arg[0])
        b = kwarg.pop('b')
        return TqFunc.min(a, b, **kwarg)

    def tq_max(self, b=None, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        a = kwarg.pop('a', arg[0])
        b = kwarg.pop('b')
        return TqFunc.max(a, b, **kwarg)

    def tq_median(self, length: int = 10, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.median(*arg, **kwarg)

    def tq_exist(self, cond=None, length: int = 10, **kwargs):
        kwarg = self._get_column_(locals())
        return TqFunc.exist(**kwarg)

    def tq_every(self, cond=None, length: int = 10, **kwargs):
        kwarg = self._get_column_(locals())
        return TqFunc.every(**kwarg)

    def tq_hhv(self, length: int = 10, **kwargs):
        """args : high"""
        arg, kwarg = self._get_column_(locals(), 'high')
        return TqFunc.hhv(*arg, **kwarg)

    def tq_llv(self, length: int = 10, **kwargs):
        """args : low"""
        arg, kwarg = self._get_column_(locals(), 'low')
        return TqFunc.llv(*arg, **kwarg)

    def tq_avedev(self, length: int = 10, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return TqFunc.avedev(*arg, **kwarg)

    def tq_barlast(self, cond=None, **kwargs):
        kwarg = self._get_column_(locals())
        cond = kwarg["cond"]
        if not isinstance(kwarg['cond'], pd.Series):
            cond = self._df
        kwarg["cond"] = cond.astype(bool)
        return TqFunc.barlast(**kwarg)

    def tq_cum_counts(self, cond=None, **kwargs):
        kwarg = self._get_column_(locals())
        return TqFunc.cum_counts(**kwarg)
    # 配对交易指标

    @property
    def PairTrading(self) -> PairTrading:
        ...

    def pair_bollinger_bands(self, window=60, num_std=2., **kwargs) -> pd.DataFrame:
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.PairTrading.bollinger_bands_strategy(*arg, window, num_std)

    def pair_percentage_deviation(self, window=60, threshold=0.1, **kwargs) -> Union[pd.Series, pd.DataFrame]:
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.PairTrading.percentage_deviation_strategy(*arg, window, threshold)

    def pair_rolling_quantile(self, window=60, upper_quantile=0.95, lower_quantile=0.05, **kwargs) -> pd.DataFrame:
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.PairTrading.rolling_quantile_strategy(*arg, window, upper_quantile, lower_quantile)

    def pair_z_score(self, window=60, z_threshold=2.0, **kwargs) -> Union[pd.DataFrame, pd.Series]:
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.PairTrading.z_score_strategy(*arg, window, z_threshold)

    def pair_hurst_filter(self, hurst_threshold=0.5, z_threshold=2.0, **kwargs) -> pd.DataFrame:
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.PairTrading.hurst_filter_strategy(*arg, hurst_threshold, z_threshold)

    def pair_kalman_filter(self, y_series=None, z_threshold=2., **kwargs) -> pd.DataFrame:
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.PairTrading.kalman_filter_strategy(*arg, y_series, z_threshold)

    def pair_garch_volatility_adjusted(self, z_threshold=2.0, **kwargs) -> pd.DataFrame:
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.PairTrading.garch_volatility_adjusted_signals(*arg, z_threshold)

    def pair_vecm_based(self, y_series=None, window=60, lag=2, **kwargs) -> Union[pd.DataFrame, pd.Series]:
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.PairTrading.vecm_based_signals(*arg, y_series, window, lag)

    @property
    def Factors(self) -> Factors:
        ...
    # 因子指标

    def factor_single_asset_multi_factor_strategy(self, *factors: pd.DataFrame, window=10, top_pct=0.2, bottom_pct=0.2, isstand=True, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        price = arg[0]
        factors_df = get_factors_df(*factors)
        return self.Factors.single_asset_multi_factor_strategy(price, factors_df, window=window, top_pct=top_pct, bottom_pct=bottom_pct, isstand=isstand)

    def factor_evaluate_factors(self, *factors: pd.DataFrame, window=20, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        price = arg[0]
        factors_df = get_factors_df(*factors)
        return self.Factors.evaluate_factors(price, factors_df, window=window)

    def factor_pca_trend_indicator(self, *factors: pd.DataFrame, n_components=2,
                                   dynamic_sign=True, filter_low_variance=True):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        price = arg[0]
        factors_df = get_factors_df(*factors)
        return self.Factors.pca_trend_indicator(price, factors_df, n_components, dynamic_sign, filter_low_variance)

    def factor_adaptive_weight_trend(self, windows=[5, 20, 50], lookback=10, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return self.Factors.adaptive_weight_trend(arg[0], windows=windows, lookback=lookback)

    def factor_factor_optimizer(self, *factors: pd.DataFrame,
                                max_weight: float = 0.8, l2_reg: float = 0.0001,
                                min_ic_abs: float = 0.03, n_init_points: int = 10,
                                optimization_model: str = "scipy", **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        price = arg[0]
        factors_df = get_factors_df(*factors)
        return self.Factors.FactorOptimizer(price,
                                            factors_df,
                                            max_weight=max_weight,
                                            l2_reg=l2_reg,
                                            min_ic_abs=min_ic_abs,
                                            n_init_points=n_init_points,
                                            optimization_model=optimization_model)
    # 自定义指标
    # btind

    def btind_open(self, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.O)
        return BtFunc.open(*arg, **kwarg)

    def btind_high(self, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.H)
        return BtFunc.high(*arg, **kwarg)

    def btind_low(self, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.L)
        return BtFunc.low(*arg, **kwarg)

    def btind_close(self, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.close(*arg, **kwarg)

    def btind_smoothrng(self, length: int = 14, mult: float = 1., **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.smoothrng(*arg, **kwarg)

    def btind_rngfilt(self, r: pd.Series = None, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.rngfilt(*arg, **kwarg)

    def btind_alerts(self, length=None, mult=None, **kwargs):
        """alerts指标,args : close
        https://cn.tradingview.com/script/ETB76oav/"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.alerts(*arg, **kwarg)

    # price density 价格密度函数

    def btind_noises_density(self, length: int = 10, **kwargs) -> pd.Series:
        """args : high, low"""
        arg, kwarg = self._get_column_(locals(), *FILED.HL)
        return BtFunc.noises_density(*arg, **kwarg)

    # ER效率系数

    def btind_noises_er(self, length: int = 10, **kwargs) -> pd.Series:
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.noises_er(*arg, **kwarg)

    # fractal dimension 分型维度

    def btind_noises_fd(self, length: int = 10, **kwargs) -> pd.Series:
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return BtFunc.noises_fd(*arg, **kwarg)

    def btind_kama(self, length=None, fast=None, slow=None, drift=None, offset=None, **kwargs):
        """Indicator: Kaufman's Adaptive Moving Average (KAMA)
        args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.kama(*arg, **kwarg)

    def btind_mama(self, fastlimit=0.6185, slowlimit=0.06185, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.mama(*arg, **kwarg)

    def btind_pmax(self, length=14, mult=1.6185, mode='hma', dev='stdev', **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.pmax(*arg, **kwarg)

    def btind_pv(self, length=10, **kwargs):
        """args : close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.pv(*arg, **kwarg)

    def btind_realized(self, length: int = 10, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.realized(*arg, **kwarg)

    def btind_rsrs(self, length: int = 10, method='r1', weights=True, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.HLV)
        return BtFunc.rsrs(*arg, **kwarg)

    def btind_savitzky_golay(self, window_length: Any = 10, polyorder: Any = 2, deriv: int = 0, delta: float = 1, axis: int = -1, mode: str = 'interp', cval: float = 0, **kwargs):
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.savitzky_golay(*arg, **kwarg)

    def btind_supertrend(self, length=14, multiplier=2., weights=2., **kwargs):
        """args:high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return BtFunc.supertrend(*arg, **kwarg)

    def btind_zigzag(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> pd.Series:
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return ZigZag.zigzag(*arg, **kwarg)

    def btind_zigzag_full(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> pd.Series:
        """args : high, low, close"""
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return ZigZag.zigzag_full(*arg, **kwarg)

    def btind_zigzag_modes(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., **kwargs) -> pd.Series:
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return ZigZag.zigzag_modes(*arg, **kwarg)

    def btind_zigzag_returns(self, up_thresh: float = 0., down_thresh: float = 0., multiplier: float = 1., limit: bool = True, **kwargs) -> pd.Series:
        arg, kwarg = self._get_column_(locals(), *FILED.HLC)
        return ZigZag.zigzag_returns(*arg, **kwarg)

    def btind_AndeanOsc(self, length: int = 14, signal_length: int = 9, **kwargs) -> pd.DataFrame:
        """args :open,close"""
        arg, kwarg = self._get_column_(locals(), *FILED.OC)
        return BtFunc.AndeanOsc(*arg, **kwarg)

    def btind_Coral_Trend_Candles(self, smooth: int = 9., mult: float = .4, **kwargs) -> pd.Series:
        """args :close"""
        arg, kwarg = self._get_column_(locals(), *FILED.C)
        return BtFunc.Coral_Trend_Candles(*arg, **kwarg)

    @property
    def SignalFeatures(self) -> SignalFeatures:
        ...

    # 信号特征signal_features
    def sf_Binarizer(self, y: Optional[Iterable] = None, threshold: float = 0.0, copy: bool = True, fit_params: dict = {}, **kwargs):
        return self.SignalFeatures.Binarizer(self, y, threshold, copy, fit_params, **kwargs)

    def sf_FunctionTransformer(
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
    ):
        return self.SignalFeatures.FunctionTransformer(self, y, func, inverse_func, validate, accept_sparse, check_inverse, feature_names_out, kw_args, inv_kw_args, fit_params, **kwargs)

    def sf_KBinsDiscretizer(
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
    ):
        return self.SignalFeatures.KBinsDiscretizer(self, y, n_bins, encode, strategy, dtype, subsample, random_state, fit_params, **kwargs)

    def sf_KernelCenterer(self, y: Optional[Iterable] = None, fit_params: dict = {}, **kwargs):
        return self.SignalFeatures.KernelCenterer(self, y, fit_params, **kwargs)

    def sf_LabelBinarizer(self, y: Optional[Iterable] = None, neg_label: int = 0, pos_label: int = 1, sparse_output: bool = False, **kwargs):
        return self.SignalFeatures.LabelBinarizer(self, y, neg_label, pos_label, sparse_output, **kwargs)

    def sf_LabelEncoder(self, y: Optional[Iterable] = None, **kwargs):
        return self.SignalFeatures.LabelEncoder(self, y, **kwargs)

    def sf_MultiLabelBinarizer(self, y: Optional[Iterable] = None, classes=Optional[np.ndarray], sparse_output: bool = False, **kwargs):
        return self.SignalFeatures.MultiLabelBinarizer(self, y, classes, sparse_output, **kwargs)

    def sf_MinMaxScaler(self, y: Optional[Iterable] = None, feature_range: tuple[int] = (0, 1), copy: bool = True, clip: bool = False, fit_params: dict = {}, **kwargs):
        return self.SignalFeatures.MinMaxScaler(self, y, feature_range, copy, clip, fit_params, **kwargs)

    def sf_MaxAbsScaler(self, y: Optional[Iterable] = None, copy: bool = True, fit_params: dict = {},  **kwargs):
        return self.SignalFeatures.MaxAbsScaler(self, y, copy, fit_params, **kwargs)

    def sf_QuantileTransformer(
        self,
        y: Optional[Iterable] = None,
        n_quantiles: int = 1000,
        output_distribution: Literal['uniform', 'normal'] = "uniform",
        ignore_implicit_zeros: bool = False,
        subsample: int = int(1e5),
        random_state: Optional[Union[int, RandomState]] = None,
        copy: bool = True,
        fit_params: dict = {},
        **kwargs
    ):
        return self.SignalFeatures.QuantileTransformer(self, y, n_quantiles, output_distribution, ignore_implicit_zeros, subsample, random_state, copy, fit_params, **kwargs)

    def sf_Normalizer(self, y: Optional[Iterable] = None, norm: Literal['l1', 'l2', 'max'] = "l2", copy: bool = True, fit_params: dict = {}, **kwargs):
        return self.SignalFeatures.Normalizer(self, y, norm, copy, fit_params, **kwargs)

    def sf_OneHotEncoder(
        self,
        y: Optional[Iterable] = None,
        categories: Union[Sequence[np.ndarray], Literal['auto']] = "auto",
        drop: Optional[np.ndarray] = None,
        sparse: Union[str, bool] = True,
        dtype=np.float64,
        handle_unknown="error",
        min_frequency=None,
        max_categories=None,
        fit_params: dict = {},
        **kwargs
    ):
        return self.SignalFeatures.OneHotEncoder(self, y, categories, drop, sparse, dtype, handle_unknown, min_frequency, max_categories, fit_params, **kwargs)

    def sf_OrdinalEncoder(
        self,
        y: Optional[Iterable] = None,
        categories="auto",
        dtype=np.float64,
        handle_unknown="error",
        unknown_value=None,
        encoded_missing_value=np.nan,
        fit_params: dict = {},
        **kwargs
    ):
        return self.SignalFeatures.OrdinalEncoder(self, y, categories, dtype, handle_unknown, unknown_value, encoded_missing_value, fit_params, **kwargs)

    def sf_PowerTransformer(self, y: Optional[Iterable] = None, method="yeo-johnson", standardize=True, copy=True, **kwargs):
        return self.SignalFeatures.PowerTransformer(self, y, method, standardize, copy, **kwargs)

    def sf_RobustScaler(
        self,
        y: Optional[Iterable] = None,
        with_centering: bool = True,
        with_scaling: bool = True,
        quantile_range: tuple[float] = (25.0, 75.0),
        copy: bool = True,
        unit_variance: bool = False,
        fit_params: dict = {},
        **kwargs
    ):
        return self.SignalFeatures.RobustScaler(self, y, with_centering, with_scaling, quantile_range, copy, unit_variance, fit_params, **kwargs)

    def sf_SplineTransformer(
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
    ):
        return self.SignalFeatures.SplineTransformer(self, y, n_knots, degree, knots, extrapolation, include_bias, order, fit_params, **kwargs)

    def sf_StandardScaler(self, y: Optional[Iterable] = None, copy: bool = True, with_mean: bool = True, with_std: bool = True, fit_params: dict = {}, **kwargs):
        return self.SignalFeatures.StandardScaler(self, y, copy, with_mean, with_std, fit_params, **kwargs)

    def sf_add_dummy_feature(self, value: float = 1., **kwargs):
        return self.SignalFeatures.add_dummy_feature(self, value)

    def sf_PolynomialFeatures(self, y: Optional[Iterable] = None, degree: Union[int, tuple[int, int]] = 2, interaction_only: bool = False,
                              include_bias: bool = True, order: Literal['C', 'F'] = "C", fit_params: dict = {}, **kwargs):
        return self.SignalFeatures.PolynomialFeatures(self, y, degree, interaction_only, include_bias, order, fit_params, **kwargs)

    def sf_binarize(self, threshold: float = 0.0, copy: bool = True, **kwargs):
        return self.SignalFeatures.binarize(self, threshold, copy, **kwargs)

    def sf_normalize(self, norm: Literal['l1', 'l2', 'max'] = "l2", axis: int = 1, copy: bool = True, return_norm: bool = False, **kwargs):
        return self.SignalFeatures.normalize(self, norm, axis, copy, return_norm, **kwargs)

    def sf_scale(self, axis=0, with_mean: bool = True, with_std: bool = True, copy=True, **kwargs):
        return self.SignalFeatures.scale(self, axis, with_mean, with_std, copy, **kwargs)

    def sf_robust_scale(
        self,
        axis: int = 0,
        with_centering: bool = True,
        with_scaling: bool = True,
        quantile_range: tuple[float, float] = (25.0, 75.0),
        copy: bool = True,
        unit_variance: bool = False,
        **kwargs
    ):
        return self.SignalFeatures.robust_scale(self, axis, with_centering, with_scaling, quantile_range, copy, unit_variance, **kwargs)

    def sf_maxabs_scale(self, axis: int = 0, copy: bool = True, **kwargs):
        return self.SignalFeatures.maxabs_scale(self, axis, copy, **kwargs)

    def sf_minmax_scale(self, feature_range: tuple[int, int] = (0, 1), axis: int = 0, copy: bool = True, **kwargs):
        return self.SignalFeatures.minmax_scale(self, feature_range, axis, copy, **kwargs)

    def sf_label_binarize(self, classes: np.ndarray, neg_label: int = 0, pos_label: int = 1, sparse_output: bool = False, *kwargs):
        return self.SignalFeatures.label_binarize(self, classes, neg_label, pos_label, sparse_output)

    def sf_quantile_transform(
        self,
        axis: int = 0,
        n_quantiles: int = 1000,
        output_distribution: Literal['uniform', 'normal'] = "uniform",
        ignore_implicit_zeros: bool = False,
        subsample: int = int(1e5),
        random_state: Optional[Union[int, RandomState]] = None,
        copy: bool = True,
        **kwargs
    ):
        return self.SignalFeatures.quantile_transform(self, axis, n_quantiles, output_distribution, ignore_implicit_zeros, subsample, random_state, copy, **kwargs)

    def sf_power_transform(self, method: Literal['yeo-johnson', 'box-cox'] = "yeo-johnson", standardize: bool = True, copy: bool = True, **kwargs):
        return self.SignalFeatures.power_transform(self, method, standardize, copy, **kwargs)


setattr(AnalysisIndicators, 'btta', property(lambda self: self._df.ta))
setattr(SeriesIndicators, 'btta', property(lambda self: self._df.ta))
for atrk, atrv in CoreFunc.__dict__.items():
    if not atrk.startswith('_') and isinstance(atrv, Callable):
        setattr(AnalysisIndicators, atrk, atrv)
        setattr(SeriesIndicators, atrk, atrv)

AnalysisIndicators.__name__ = 'DataFrameIndicators'
AnalysisIndicators.__bases__ = (LazyImport,) + AnalysisIndicators.__bases__
