# -*- coding: utf-8 -*-
import pandas_ta as pta
from pandas_ta.core import pd
import numpy as np
from typing import Union, Callable, Any, Sequence, Iterable, Literal, Optional
# from .other import *
import statsmodels.api as sm
from scipy import stats as scipy_stats
from numpy.random import RandomState
import threading
model_lock = threading.Lock()
_sklearn_preprocessing = None
_sklearn_decomposition = None
_arch_model = None
_KalmanFilter = None
_ti = None
_talib = None
_SingleAssetFactorOptimizer = None
_autotrader = None
_SignalFeatures = None
_PairTrading = None
_PairTrading = None
_Factors = None
_FinTa = None
__all__ = ["LazyImport"]


class LazyImport:

    @classmethod
    def sp(cls):
        global _sklearn_preprocessing
        if _sklearn_preprocessing is None:
            with model_lock:  # 确保多线程安全
                if _sklearn_preprocessing is None:  # 双重检查
                    try:
                        import sklearn.preprocessing as sp
                        _sklearn_preprocessing = sp
                    except ImportError as e:
                        raise RuntimeError(
                            "需要安装sklearn才能使用此功能: pip install sklearn"
                        ) from e
        return _sklearn_preprocessing

    @classmethod
    def sklearn_decomposition(cls):
        global _sklearn_decomposition
        if _sklearn_decomposition is None:
            with model_lock:
                if _sklearn_decomposition is None:
                    try:
                        import sklearn.decomposition as sd
                        _sklearn_decomposition = sd
                    except ImportError as e:
                        raise RuntimeError(
                            "需要安装sklearn才能使用此功能: pip install sklearn"
                        ) from e
        return _sklearn_decomposition

    @classmethod
    def arch_model(cls):
        global _arch_model
        if _arch_model is None:
            with model_lock:
                if _arch_model is None:
                    try:
                        from arch import arch_model
                        _arch_model = arch_model
                    except ImportError as e:
                        raise RuntimeError(
                            "需要安装arch才能使用此功能: pip install arch"
                        ) from e
        return _arch_model

    @classmethod
    def KalmanFilter(cls):
        global _KalmanFilter
        if _KalmanFilter is None:
            with model_lock:
                if _KalmanFilter is None:
                    try:
                        from pykalman import KalmanFilter
                        _KalmanFilter = KalmanFilter
                    except ImportError as e:
                        raise RuntimeError(
                            "需要安装pykalman才能使用此功能: pip install pykalman"
                        ) from e
        return _KalmanFilter

    @classmethod
    def SingleAssetFactorOptimizer(cls):
        global _SingleAssetFactorOptimizer
        if _SingleAssetFactorOptimizer is None:
            with model_lock:
                if _SingleAssetFactorOptimizer is None:
                    from .SingleAssetFactorOptimizer import SingleAssetFactorOptimizer
                    _SingleAssetFactorOptimizer = SingleAssetFactorOptimizer
        return _SingleAssetFactorOptimizer

    @property
    def tulipy(self):
        global _ti
        if _ti is None:
            with model_lock:  # 确保多线程安全
                if _ti is None:  # 双重检查
                    try:
                        import tulipy
                        _ti = tulipy
                    except ImportError as e:
                        raise RuntimeError(
                            "需要安装tulipy才能使用此功能: pip install tulipy"
                        ) from e
        return _ti

    @property
    def talib(self):
        global _talib
        if _talib is None:
            with model_lock:  # 确保多线程安全
                if _talib is None:  # 双重检查
                    try:
                        import talib
                        _talib = talib
                    except ImportError as e:
                        raise RuntimeError(
                            "需要安装talib才能使用此功能: pip install talib"
                        ) from e
        return _talib

    @property
    def FinTa(self):
        global _FinTa
        if _FinTa is None:
            with model_lock:  # 确保多线程安全
                if _FinTa is None:  # 双重检查
                    try:
                        from finta import TA as FinTa
                        _FinTa = FinTa
                    except ImportError as e:
                        raise RuntimeError(
                            "需要安装talib才能使用此功能: pip install FinTa"
                        ) from e
        return _FinTa

    @classmethod
    def _FinTa(cls):
        global _FinTa
        if _FinTa is None:
            with model_lock:  # 确保多线程安全
                if _FinTa is None:  # 双重检查
                    try:
                        from finta import TA as FinTa
                        _FinTa = FinTa
                    except ImportError as e:
                        raise RuntimeError(
                            "需要安装talib才能使用此功能: pip install FinTa"
                        ) from e
        return _FinTa

    @property
    def autotrader(self):
        global _autotrader
        if _autotrader is None:
            with model_lock:  # 确保多线程安全
                if _autotrader is None:  # 双重检查
                    try:
                        _autotrader = autotrader
                    except ImportError as e:
                        print(e)
        return _autotrader

    @property
    def SignalFeatures(self):
        global _SignalFeatures
        if _SignalFeatures is None:
            with model_lock:  # 确保多线程安全
                if _SignalFeatures is None:  # 双重检查
                    try:
                        _SignalFeatures = SignalFeatures
                    except ImportError as e:
                        print(e)

        return _SignalFeatures

    @property
    def PairTrading(self):
        global _PairTrading
        if _PairTrading is None:
            with model_lock:  # 确保多线程安全
                if _PairTrading is None:  # 双重检查
                    try:
                        _PairTrading = PairTrading
                    except ImportError as e:
                        print(e)

        return _PairTrading

    @property
    def Factors(self):
        global _Factors
        if _Factors is None:
            with model_lock:  # 确保多线程安全
                if _Factors is None:  # 双重检查
                    try:
                        _Factors = Factors
                    except ImportError as e:
                        print(e)

        return _Factors


class autotrader(LazyImport):
    @classmethod
    def supertrend(
        cls,
        data: pd.DataFrame,
        period: int = 10,
        ATR_multiplier: float = 3.0,
        source: pd.Series = None,
    ) -> pd.DataFrame:
        """SuperTrend indicator, ported from the SuperTrend indicator by
        KivancOzbilgic on TradingView.

        Parameters
        ----------
        data : pd.DataFrame
            The OHLC data.

        period : int, optional
            The lookback period. The default is 10.

        ATR_multiplier : int, optional
            The ATR multiplier. The default is 3.0.

        source : pd.Series, optional
            The source series to use in calculations. If None, hl/2 will be
            used. The default is None.

        Returns
        -------
        supertrend_df : pd.DataFrame
            A Pandas DataFrame of containing the SuperTrend indicator, with
            columns of 'uptrend' and 'downtrend' containing uptrend/downtrend
            support/resistance levels, and 'trend', containing -1/1 to indicate
            the current implied trend.

        References
        ----------
        https://www.tradingview.com/script/r6dAP7yi/
        """

        if source is None:
            source = (data["high"].values + data["low"].values) / 2

        # Calculate ATR
        atr = cls._FinTa().ATR(data, period)

        up = source - (ATR_multiplier * atr)
        up_list = [up[0]]
        up_times = [data.index[0]]
        N_up = 0

        dn = source + (ATR_multiplier * atr)
        dn_list = [dn[0]]
        dn_times = [data.index[0]]
        N_dn = 0

        trend = 1
        trend_list = [trend]

        for i in range(1, len(data)):
            if trend == 1:
                if data["close"].values[i] > max(up[N_up:i]):
                    up_list.append(max(up[N_up:i]))
                    up_times.append(data.index[i])

                    dn_list.append(np.nan)
                    dn_times.append(data.index[i])
                else:
                    trend = -1
                    N_dn = i
                    dn_list.append(dn[i])
                    dn_times.append(data.index[i])

                    up_list.append(np.nan)
                    up_times.append(data.index[i])

            else:
                if data["close"].values[i] < min(dn[N_dn:i]):
                    dn_list.append(min(dn[N_dn:i]))
                    dn_times.append(data.index[i])

                    up_list.append(np.nan)
                    up_times.append(data.index[i])
                else:
                    trend = 1
                    N_up = i
                    up_list.append(up[i])
                    up_times.append(data.index[i])

                    dn_list.append(np.nan)
                    dn_times.append(data.index[i])

            trend_list.append(trend)

        supertrend_df = pd.DataFrame(
            {"uptrend": up_list, "downtrend": dn_list, "trend": trend_list}, index=up_times
        )
        return supertrend_df

    @classmethod
    def halftrend(
        cls, data: pd.DataFrame, amplitude: int = 2, channel_deviation: float = 2
    ) -> pd.DataFrame:
        """HalfTrend indicator, ported from the HalfTrend indicator by
        Alex Orekhov (everget) on TradingView.

        Parameters
        ----------
        data : pd.DataFrame
            OHLC price data.

        amplitude : int, optional
            The lookback window. The default is 2.

        channel_deviation : float, optional
            The ATR channel deviation factor. The default is 2.

        Returns
        -------
        htdf : TYPE
            DESCRIPTION.

        References
        ----------
        https://www.tradingview.com/script/U1SJ8ubc-HalfTrend/
        """

        # Initialisation
        atr2 = cls._FinTa().ATR(data, 100) / 2
        dev = channel_deviation * atr2
        high_price = data["high"].rolling(amplitude).max().fillna(0)
        low_price = data["low"].rolling(amplitude).min().fillna(0)
        highma = cls._FinTa().SMA(data, period=amplitude, column="high")
        lowma = cls._FinTa().SMA(data, period=amplitude, column="low")

        trend = np.zeros(len(data))
        next_trend = np.zeros(len(data))
        max_low_price = np.zeros(len(data))
        max_low_price[0] = data["low"].iloc[0]
        min_high_price = np.zeros(len(data))
        min_high_price[0] = data["high"].iloc[0]

        for i in range(1, len(data)):
            if next_trend[i - 1] == 1:
                max_low_price[i] = max(
                    low_price.iloc[i - 1], max_low_price[i - 1])

                if (
                    highma.iloc[i] < max_low_price[i]
                    and data["close"].iloc[i] < data["low"].iloc[i - 1]
                ):
                    trend[i] = 1
                    next_trend[i] = 0
                    min_high_price[i] = high_price.iloc[i]
                else:
                    # assign previous values again
                    trend[i] = trend[i - 1]
                    next_trend[i] = next_trend[i - 1]
                    min_high_price[i] = min_high_price[i - 1]
            else:
                min_high_price[i] = min(
                    high_price.iloc[i - 1], min_high_price[i - 1])

                if (
                    lowma.iloc[i] > min_high_price[i]
                    and data["close"].iloc[i] > data["high"].iloc[i - 1]
                ):
                    trend[i] = 0
                    next_trend[i] = 1
                    max_low_price[i] = low_price.iloc[i]
                else:
                    # assign previous values again
                    trend[i] = trend[i - 1]
                    next_trend[i] = next_trend[i - 1]
                    max_low_price[i] = max_low_price[i - 1]

        up = np.zeros(len(data))
        up[0] = max_low_price[0]
        down = np.zeros(len(data))
        down[0] = min_high_price[0]
        atr_high = np.zeros(len(data))
        atr_low = np.zeros(len(data))

        for i in range(1, len(data)):
            if trend[i] == 0:
                if trend[i - 1] != 0:
                    up[i] = down[i - 1]
                else:
                    up[i] = max(max_low_price[i - 1], up[i - 1])

                atr_high[i] = up[i] + dev.iloc[i]
                atr_low[i] = up[i] - dev.iloc[i]

            else:
                if trend[i - 1] != 1:
                    down[i] = up[i - 1]
                else:
                    down[i] = min(min_high_price[i - 1], down[i - 1])

                atr_high[i] = down[i] + dev.iloc[i]
                atr_low[i] = down[i] - dev.iloc[i]

        halftrend = np.where(trend == 0, up, down)
        buy = np.where((trend == 0) & (np.roll(trend, 1) == 1), 1, 0)
        sell = np.where((trend == 1) & (np.roll(trend, 1) == 0), 1, 0)

        # Construct DataFrame
        htdf = pd.DataFrame(
            data={
                "halftrend": halftrend,
                "atrHigh": np.nan_to_num(atr_high),
                "atrLow": np.nan_to_num(atr_low),
                "buy": buy,
                "sell": sell,
            },
            index=data.index,
        )

        # Clear false leading signals
        htdf["buy"].values[:100] = np.zeros(100)
        htdf["sell"].values[:100] = np.zeros(100)

        # Replace leading zeroes with nan
        htdf["atrHigh"] = htdf.atrHigh.replace(
            to_replace=0, value=float("nan"))
        htdf["atrLow"] = htdf.atrLow.replace(to_replace=0, value=float("nan"))

        return htdf

    def range_filter(
        data: pd.DataFrame,
        range_qty: float = 2.618,
        range_period: int = 14,
        smooth_range: bool = True,
        smooth_period: int = 27,
        av_vals: bool = False,
        av_samples: int = 2,
        mov_source: str = "body",
        filter_type: int = 1,
    ) -> pd.DataFrame:
        """Price range filter, ported from the Range Filter [DW] indicator by
        DonovanWall on TradingView. The indicator was designed to filter out
        minor price action for a clearer view of trends.

        Parameters
        ----------
        data : pd.DataFrame
            The OHLC price data.

        range_qty : float, optional
            The range size. The default is 2.618.

        range_period : int, optional
            The range period. The default is 14.

        smooth_range : bool, optional
            Smooth the price range. The default is True.

        smooth_period : int, optional
            The smooting period. The default is 27.

        av_vals : bool, optional
            Average values. The default is False.

        av_samples : int, optional
            The number of average samples to use. The default is 2.

        mov_source : str, optional
            The price movement source ('body' or 'wicks'). The default is 'body'.

        filter_type : int, optional
            The filter type to use in calculations (1 or 2). The default is 1.

        Returns
        -------
        rfi : pd.DataFrame
            A dataframe containing the range filter indicator bounds.

        References
        ----------
        https://www.tradingview.com/script/lut7sBgG-Range-Filter-DW/
        """
        high_val = 0.0
        low_val = 0.0

        # Get high and low values
        if mov_source == "body":
            high_val = data["close"]
            low_val = data["close"]
        elif mov_source == "wicks":
            high_val = data["high"]
            low_val = data["low"]

        # Get filter values
        rng = autotrader._range_size(
            (high_val + low_val) / 2, "AverageChange", range_qty, range_period
        )
        rfi = autotrader._calculate_range_filter(
            high_val,
            low_val,
            rng,
            range_period,
            filter_type,
            smooth_range,
            smooth_period,
            av_vals,
            av_samples,
        )

        return rfi

    def bullish_engulfing(data: pd.DataFrame, detection: str = None):
        """Bullish engulfing pattern detection."""
        if detection == "SMA50":
            sma50 = pta.sma(data["close"].values, 50)
            down_trend = np.where(data["close"].values < sma50, True, False)

        elif detection == "SMA50/200":
            sma50 = pta.sma(data["close"].values, 50)
            sma200 = pta.sma(data["close"].values, 200)

            down_trend = np.where(
                (data["close"].values < sma50) & (
                    data["close"].values < sma200),
                True,
                False,
            )
        else:
            down_trend = np.full(len(data), True)

        body_len = 14  # ema depth for bodyAvg

        body_high = np.maximum(data["close"].values, data["open"].values)
        body_low = np.minimum(data["close"].values, data["open"].values)
        body = body_high - body_low

        body_avg = pta.ema(body, body_len)
        short_body = body < body_avg
        long_body = body > body_avg

        white_body = data["open"].values < data["close"].values
        black_body = data["open"].values > data["close"].values

        inside_bar = [False]
        for i in range(1, len(data)):
            val = (body_high[i - 1] > body_high[i]
                   ) and (body_low[i - 1] < body_low[i])
            inside_bar.append(val)

        engulfing_bullish = [False]
        for i in range(1, len(data)):
            condition = (
                down_trend[i]
                & white_body[i]
                & long_body[i]
                & black_body[i - 1]
                & short_body[i - 1]
                & (data["close"].values[i] >= data["open"].values[i - 1])
                & (data["open"].values[i] <= data["close"].values[i - 1])
                & (
                    (data["close"].values[i] > data["open"].values[i - 1])
                    | (data["open"].values[i] < data["close"].values[i - 1])
                )
            )
            engulfing_bullish.append(1. if condition else 0.)
        return pd.Series(engulfing_bullish, name="engulfing_bullish")

    def bearish_engulfing(data: pd.DataFrame, detection: str = None):
        """Bearish engulfing pattern detection."""
        if detection == "SMA50":
            sma50 = pta.sma(data["close"].values, 50)
            up_trend = np.where(data["close"].values > sma50, True, False)
        elif detection == "SMA50/200":
            sma50 = pta.sma(data["close"].values, 50)
            sma200 = pta.sma(data["close"].values, 200)

            up_trend = np.where(
                (data["close"].values > sma50) & (
                    data["close"].values > sma200),
                True,
                False,
            )
        else:
            up_trend = np.full(len(data), True)

        body_len = 14  # ema depth for bodyAvg
        body_high = np.maximum(data["close"].values, data["open"].values)
        body_low = np.minimum(data["close"].values, data["open"].values)
        body = body_high - body_low

        body_avg = pta.ema(body, body_len)
        short_body = body < body_avg
        long_body = body > body_avg

        white_body = data["open"].values < data["close"].values
        black_body = data["open"].values > data["close"].values

        inside_bar = [False]
        for i in range(1, len(data)):
            val = (body_high[i - 1] > body_high[i]
                   ) and (body_low[i - 1] < body_low[i])
            inside_bar.append(val)

        engulfing_bearish = [False]
        for i in range(1, len(data)):
            condition = (
                up_trend[i]
                & black_body[i]
                & long_body[i]
                & white_body[i - 1]
                & short_body[i - 1]
                & (data["close"].values[i] <= data["open"].values[i - 1])
                & (data["open"].values[i] >= data["close"].values[i - 1])
                & (
                    (data["close"].values[i] < data["open"].values[i - 1])
                    | (data["open"].values[i] > data["close"].values[i - 1])
                )
            )
            engulfing_bearish.append(1. if condition else 0.)

        return pd.Series(engulfing_bearish, name="engulfing_bearish")

    def find_swings(data: pd.DataFrame, n: int = 2) -> pd.DataFrame:
        """Locates swings in the inputted data using a moving average gradient
        method.

        Parameters
        ----------
        data : pd.DataFrame | pd.Series | list | np.array
            An OHLC dataframe of price, or an array/list/Series of data from an
            indicator (eg. RSI).

        n : int, optional
            The moving average period. The default is 2.

        Returns
        -------
        swing_df : pd.DataFrame
            A dataframe containing the swing levels detected.

        pd.Series(hl2, name="hl2"),
        """
        # Prepare data
        if isinstance(data, pd.DataFrame):
            # OHLC data
            hl2 = (data["high"].values + data["low"].values) / 2
            swing_data = pd.Series(pta.ema(hl2, n), index=data.index)
            low_data = data["low"].values
            high_data = data["high"].values

        elif isinstance(data, pd.Series):
            # Pandas series data
            swing_data = pd.Series(
                pta.ema(data.fillna(0), n), index=data.index)
            low_data = data
            high_data = data

        else:
            # Find swings in alternative data source
            data = pd.Series(data)

            # Define swing data
            swing_data = pd.Series(pta.ema(data, n), index=data.index)
            low_data = data
            high_data = data

        signed_grad = np.sign((swing_data - swing_data.shift(1)).bfill())
        swings = (signed_grad != signed_grad.shift(1).bfill()) * -signed_grad

        # Calculate swing extrema
        lows = []
        highs = []
        for i, swing in enumerate(swings):
            if swing < 0:
                # Down swing, find low price
                highs.append(0)
                lows.append(min(low_data[i - n + 1: i + 1]))
            elif swing > 0:
                # Up swing, find high price
                highs.append(max(high_data[i - n + 1: i + 1]))
                lows.append(0)
            else:
                # Price movement
                highs.append(0)
                lows.append(0)

        # Determine last swing
        trend = autotrader.rolling_signal_list(-swings)
        swings_list = autotrader.merge_signals(lows, highs)
        last_swing = autotrader.rolling_signal_list(swings_list)

        # Need to return both a last swing low and last swing high list
        last_low = autotrader.rolling_signal_list(lows)
        last_high = autotrader.rolling_signal_list(highs)

        swing_df = pd.DataFrame(
            data={"Highs": last_high, "Lows": last_low,
                  "Last": last_swing, "Trend": trend},
            index=swing_data.index,
        )

        return swing_df

    def classify_swings(swing_df: pd.DataFrame, tol: int = 0) -> pd.DataFrame:
        """Classifies a dataframe of swings (from find_swings) into higher-highs,
        lower-highs, higher-lows and lower-lows.


        Parameters
        ----------
        swing_df : pd.DataFrame
            The dataframe returned by find_swings.

        tol : int, optional
            The classification tolerance. The default is 0.

        Returns
        -------
        swing_df : pd.DataFrame
            A dataframe containing the classified swings.
        """
        # Create copy of swing dataframe
        swing_df = swing_df.copy()

        new_level = np.where(swing_df.Last != swing_df.Last.shift(), 1, 0)

        candles_since_last = autotrader.candles_between_crosses(
            new_level, initial_count=1)

        # Add column 'candles since last swing' CSLS
        swing_df["CSLS"] = candles_since_last

        # Find strong Support and Resistance zones
        swing_df["Support"] = (swing_df.CSLS > tol) & (swing_df.Trend == 1)
        swing_df["Resistance"] = (swing_df.CSLS > tol) & (swing_df.Trend == -1)

        # Find higher highs and lower lows
        swing_df["Strong_lows"] = (
            swing_df["Support"] * swing_df["Lows"]
        )  # Returns high values when there is a strong support
        swing_df["Strong_highs"] = (
            swing_df["Resistance"] * swing_df["Highs"]
        )  # Returns high values when there is a strong support

        # Remove duplicates to preserve indexes of new levels
        swing_df["FSL"] = autotrader.unroll_signal_list(
            swing_df["Strong_lows"]
        )  # First of new strong lows
        swing_df["FSH"] = autotrader.unroll_signal_list(
            swing_df["Strong_highs"]
        )  # First of new strong highs

        # Now compare each non-zero value to the previous non-zero value.
        low_change = np.sign(swing_df.FSL) * (
            swing_df.FSL
            - swing_df.Strong_lows.replace(to_replace=0,
                                           method="ffill").shift()
        )
        high_change = np.sign(swing_df.FSH) * (
            swing_df.FSH
            - swing_df.Strong_highs.replace(to_replace=0, method="ffill").shift()
        )

        # the first low_change > 0.0 is not a HL
        r_hl = []
        first_valid_idx = -1
        for i in low_change.index:
            v = low_change[i]
            if first_valid_idx == -1 and not np.isnan(v) and v != 0.0:
                first_valid_idx = i
            if first_valid_idx != -1 and i > first_valid_idx and v > 0.0:
                hl = True
            else:
                hl = False
            r_hl.append(hl)

        # the first high_change < 0.0 is not a LH
        r_lh = []
        first_valid_idx = -1
        for i in high_change.index:
            v = high_change[i]
            if first_valid_idx == -1 and not np.isnan(v) and v != 0.0:
                first_valid_idx = i
            if first_valid_idx != -1 and i > first_valid_idx and v < 0.0:
                lh = True
            else:
                lh = False
            r_lh.append(lh)

        swing_df["LL"] = np.where(low_change < 0, True, False)
        # swing_df["HL"] = np.where(low_change > 0, True, False)
        swing_df["HL"] = r_hl
        swing_df["HH"] = np.where(high_change > 0, True, False)
        # swing_df["LH"] = np.where(high_change < 0, True, False)
        swing_df["LH"] = r_lh

        return swing_df

    def detect_divergence(
        classified_price_swings: pd.DataFrame,
        classified_indicator_swings: pd.DataFrame,
        tol: int = 2,
        method: int = 0,
    ) -> pd.DataFrame:
        """Detects divergence between price swings and swings in an indicator.

        Parameters
        ----------
        classified_price_swings : pd.DataFrame
            The output from classify_swings using OHLC data.

        classified_indicator_swings : pd.DataFrame
            The output from classify_swings using indicator data.

        tol : int, optional
            The number of candles which conditions must be met within. The
            default is 2.

        method : int, optional
            The method to use when detecting divergence (0 or 1). The default is 0.

        Raises
        ------
        Exception
            When an unrecognised method of divergence detection is requested.

        Returns
        -------
        divergence : pd.DataFrame
            A dataframe containing divergence signals.

        Notes
        -----
        Options for the method include:
            0: use both price and indicator swings to detect divergence (default)

            1: use only indicator swings to detect divergence (more responsive)
        """
        regular_bullish = []
        regular_bearish = []
        hidden_bullish = []
        hidden_bearish = []

        if method == 0:
            for i in range(len(classified_price_swings)):
                # Look backwards in each

                # REGULAR BULLISH DIVERGENCE
                if (
                    sum(classified_price_swings["LL"][i - tol + 1: i + 1])
                    + sum(classified_indicator_swings["HL"][i - tol + 1: i + 1])
                    > 1
                ):
                    regular_bullish.append(True)
                else:
                    regular_bullish.append(False)

                # REGULAR BEARISH DIVERGENCE
                if (
                    sum(classified_price_swings["HH"][i - tol + 1: i + 1])
                    + sum(classified_indicator_swings["LH"][i - tol + 1: i + 1])
                    > 1
                ):
                    regular_bearish.append(True)
                else:
                    regular_bearish.append(False)

                # HIDDEN BULLISH DIVERGENCE
                if (
                    sum(classified_price_swings["HL"][i - tol + 1: i + 1])
                    + sum(classified_indicator_swings["LL"][i - tol + 1: i + 1])
                    > 1
                ):
                    hidden_bullish.append(True)
                else:
                    hidden_bullish.append(False)

                # HIDDEN BEARISH DIVERGENCE
                if (
                    sum(classified_price_swings["LH"][i - tol + 1: i + 1])
                    + sum(classified_indicator_swings["HH"][i - tol + 1: i + 1])
                    > 1
                ):
                    hidden_bearish.append(True)
                else:
                    hidden_bearish.append(False)

            divergence = pd.DataFrame(
                data={
                    "regularBull": autotrader.unroll_signal_list(regular_bullish),
                    "regularBear": autotrader.unroll_signal_list(regular_bearish),
                    "hiddenBull": autotrader.unroll_signal_list(hidden_bullish),
                    "hiddenBear": autotrader.unroll_signal_list(hidden_bearish),
                },
                index=classified_price_swings.index,
            )
        elif method == 1:
            # Use indicator swings only to detect divergence
            # for i in range(len(classified_price_swings)):
            if True:
                price_at_indi_lows = (
                    classified_indicator_swings["FSL"] != 0
                ) * classified_price_swings["Lows"]
                price_at_indi_highs = (
                    classified_indicator_swings["FSH"] != 0
                ) * classified_price_swings["Highs"]

                # Determine change in price between indicator lows
                price_at_indi_lows_change = np.sign(price_at_indi_lows) * (
                    price_at_indi_lows
                    - price_at_indi_lows.replace(to_replace=0, method="ffill").shift()
                )
                price_at_indi_highs_change = np.sign(price_at_indi_highs) * (
                    price_at_indi_highs
                    - price_at_indi_highs.replace(to_replace=0, method="ffill").shift()
                )

                # DETECT DIVERGENCES
                regular_bullish = (classified_indicator_swings["HL"]) & (
                    price_at_indi_lows_change < 0
                )
                regular_bearish = (classified_indicator_swings["LH"]) & (
                    price_at_indi_highs_change > 0
                )
                hidden_bullish = (classified_indicator_swings["LL"]) & (
                    price_at_indi_lows_change > 0
                )
                hidden_bearish = (classified_indicator_swings["HH"]) & (
                    price_at_indi_highs_change < 0
                )

            divergence = pd.DataFrame(
                data={
                    "regularBull": regular_bullish,
                    "regularBear": regular_bearish,
                    "hiddenBull": hidden_bullish,
                    "hiddenBear": hidden_bearish,
                },
                index=classified_price_swings.index,
            )

        else:
            raise Exception(
                "Error: unrecognised method of divergence detection.")

        return divergence

    def autodetect_divergence(
        ohlc: pd.DataFrame,
        indicator_data: pd.DataFrame,
        tolerance: int = 1,
        method: int = 0,
    ) -> pd.DataFrame:
        """A wrapper method to automatically detect divergence from inputted OHLC price
        data and indicator data.

        Parameters
        ----------
        ohlc : pd.DataFrame
            A dataframe of OHLC price data.

        indicator_data : pd.DataFrame
            dataframe of indicator data.

        tolerance : int, optional
            A parameter to control the lookback when detecting divergence.
            The default is 1.

        method : int, optional
            The divergence detection method. Set to 0 to use both price and
            indicator swings to detect divergence. Set to 1 to use only indicator
            swings to detect divergence. The default is 0.

        Returns
        -------
        divergence : pd.DataFrame
            A DataFrame containing columns 'regularBull', 'regularBear',
            'hiddenBull' and 'hiddenBear'.

        See Also
        --------
        autotrader.indicators.find_swings
        autotrader.indicators.classify_swings
        autotrader.indicators.detect_divergence

        """

        # Price swings
        price_swings = autotrader.find_swings(ohlc)
        price_swings_classified = autotrader.classify_swings(price_swings)

        # Indicator swings
        indicator_swings = autotrader.find_swings(indicator_data)
        indicator_classified = autotrader.classify_swings(indicator_swings)

        # Detect divergence
        divergence = autotrader.detect_divergence(
            price_swings_classified, indicator_classified, tol=tolerance, method=method
        )

        return divergence

    def heikin_ashi(data: pd.DataFrame):
        """Calculates the Heikin-Ashi candlesticks from Japanese candlestick
        data.
        """
        # Create copy of data to prevent overwriting
        working_data = data.copy()

        # Calculate Heikin Ashi candlesticks
        ha_close = 0.25 * (
            working_data["open"]
            + working_data["low"]
            + working_data["high"]
            + working_data["close"]
        )
        ha_open = 0.5 * (working_data["open"] + working_data["close"])
        ha_high = np.maximum(
            working_data["high"].values,
            working_data["close"].values,
            working_data["open"].values,
        )
        ha_low = np.minimum(
            working_data["low"].values,
            working_data["close"].values,
            working_data["open"].values,
        )

        ha_data = pd.DataFrame(
            data={"open": ha_open, "high": ha_high,
                  "low": ha_low, "close": ha_close},
            index=working_data.index,
        )

        return ha_data

    def ha_candle_run(ha_data: pd.DataFrame):
        """Returns a list for the number of consecutive green and red
        Heikin-Ashi candles.

        Parameters
        ----------
        ha_data: pd.DataFrame
            The Heikin Ashi OHLC data.

        See Also
        --------
        heikin_ashi
        """
        green_candle = np.where(ha_data["close"] - ha_data["open"] > 0, 1, 0)
        red_candle = np.where(ha_data["close"] - ha_data["open"] < 0, 1, 0)

        green_run = []
        red_run = []

        green_sum = 0
        red_sum = 0

        for i in range(len(ha_data)):
            if green_candle[i] == 1:
                green_sum += 1
            else:
                green_sum = 0

            if red_candle[i] == 1:
                red_sum += 1
            else:
                red_sum = 0

            green_run.append(green_sum)
            red_run.append(red_sum)

        return pd.DataFrame(dict(up=green_run, dn=red_run))

    def N_period_high(data: pd.DataFrame, N: int):
        """Returns the N-period high."""
        highs = data["high"].rolling(N).max()
        return highs

    def N_period_low(data: pd.DataFrame, N: int):
        """Returns the N-period low."""
        lows = data["low"].rolling(N).min()
        return lows

    def crossover(ts1: pd.Series, ts2: pd.Series) -> pd.Series:
        """Locates where two timeseries crossover each other, returning 1 when
        list_1 crosses above list_2, and -1 for when list_1 crosses below list_2.

        Parameters
        ----------
        ts1 : pd.Series
            The first timeseries.

        ts2 : pd.Series
            The second timeseries.

        Returns
        -------
        crossovers : pd.Series
            The crossover series.
        """

        signs = np.sign(ts1 - ts2)
        crossovers = pd.Series(
            data=signs * (signs != signs.shift(1)), name="crossovers")

        return crossovers

    def cross_values(
        ts1: Union[list, pd.Series],
        ts2: Union[list, pd.Series],
        ts_crossover: Union[list, pd.Series] = None,
    ) -> Union[list, pd.Series]:
        """Returns the approximate value of the point where the two series cross.

        Parameters
        ----------
        ts1 : list | pd.Series
            The first timeseries..

        ts2 : list | pd.Series
            The second timeseries..

        ts_crossover : list | pd.Series, optional
            The crossovers between timeseries 1 and timeseries 2.

        Returns
        -------
        cross_points : list | pd.Series
            The values at which crossovers occur.
        """

        if ts_crossover is None:
            ts_crossover = autotrader.crossover(ts1, ts2)

        last_cross_point = ts1.iloc[0]
        cross_points = [last_cross_point]
        for i in range(1, len(ts_crossover)):
            if ts_crossover.iloc[i] != 0:
                i0 = 0
                m_a = ts1.iloc[i] - ts1.iloc[i - 1]
                m_b = ts2.iloc[i] - ts2.iloc[i - 1]
                ix = (ts2.iloc[i - 1] - ts1.iloc[i - 1]) / (m_a - m_b) + i0

                cross_point = m_a * (ix - i0) + ts1.iloc[i - 1]

                last_cross_point = cross_point

            else:
                cross_point = last_cross_point

            cross_points.append(cross_point)

        # Replace nans with 0
        cross_points = [0 if x != x else x for x in cross_points]
        return pd.Series(data=cross_points, index=ts1.index, name="crossval")

    def candles_between_crosses(
        crosses: Union[list, pd.Series], initial_count: int = 0
    ) -> Union[list, pd.Series]:
        """Returns a rolling sum of candles since the last cross/signal occurred.

        Parameters
        ----------
        crosses : list | pd.Series
            The list or Series containing crossover signals.

        Returns
        -------
        counts : TYPE
            The rolling count of bars since the last crossover signal.

        See Also
        ---------
        indicators.crossover
        """

        count = 0
        counts = []

        for i in range(len(crosses)):
            if crosses[i] == 0:
                # Change in signal - reset count
                count += 1
            else:
                count = initial_count

            counts.append(count)

        if isinstance(crosses, pd.Series):
            # Convert to Series
            counts = pd.Series(data=counts, index=crosses.index, name="counts")

        return counts

    def rolling_signal_list(signals: Union[list, pd.Series]):
        """Returns a list which repeats the previous signal, until a new
        signal is given.

        Parameters
        ----------
        signals : list | pd.Series
            A series of signals. Zero values are treated as 'no signal'.

        Returns
        -------
        list
            A list of rolled signals.

        Examples
        --------
        >>> rolling_signal_list([0,1,0,0,0,-1,0,0,1,0,0])
            [0, 1, 1, 1, 1, -1, -1, -1, 1, 1, 1]

        """
        rolling_signals = [0]
        last_signal = rolling_signals[0]

        if isinstance(signals, list):
            for i in range(1, len(signals)):
                if signals[i] != 0:
                    last_signal = signals[i]
                rolling_signals.append(last_signal)
        else:
            for i in range(1, len(signals)):
                if signals.iloc[i] != 0:
                    last_signal = signals.iloc[i]
                rolling_signals.append(last_signal)

        if isinstance(signals, pd.Series):
            rolling_signals = pd.Series(
                data=rolling_signals, index=signals.index)

        return pd.Series(rolling_signals, name="rolling_signals")

    def unroll_signal_list(signals: Union[list, pd.Series]):
        """Unrolls a rolled signal list.

        Parameters
        ----------
        signals : Union[list, pd.Series]
            DESCRIPTION.

        Returns
        -------
        unrolled_signals : np.array
            The unrolled signal series.

        See Also
        --------
        This function is the inverse of rolling_signal_list.

        Examples
        --------
        >>> unroll_signal_list([0, 1, 1, 1, 1, -1, -1, -1, 1, 1, 1])
            array([ 0.,  1.,  0.,  0.,  0., -1.,  0.,  0.,  1.,  0.,  0.])

        """
        unrolled_signals = np.zeros(len(signals))
        for i in range(1, len(signals)):
            if signals[i] != signals[i - 1]:
                unrolled_signals[i] = signals[i]

        if isinstance(signals, pd.Series):
            unrolled_signals = pd.Series(
                data=unrolled_signals, index=signals.index)

        return pd.Series(unrolled_signals, name="unrolled_signals")

    def merge_signals(signal_1: list, signal_2: list) -> list:
        """Returns a single signal list which has merged two signal lists.

        Parameters
        ----------
        signal_1 : list
            The first signal list.

        signal_2 : list
            The second signal list.

        Returns
        -------
        merged_signal_list : list
            The merged result of the two inputted signal series.

        Examples
        --------
        >>> s1 = [1,0,0,0,1,0]
        >>> s2 = [0,0,-1,0,0,-1]
        >>> merge_signals(s1, s2)
            [1, 0, -1, 0, 1, -1]

        """
        merged_signal_list = signal_1.copy()
        for i in range(len(signal_1)):
            if signal_2[i] != 0:
                merged_signal_list[i] = signal_2[i]

        return pd.Series(merged_signal_list, name="merged_signal_list")

    def build_grid_price_levels(
        grid_origin: float,
        grid_space: float,
        grid_levels: int,
        grid_price_space: float = None,
        pip_value: float = 0.0001,
    ) -> np.array:
        """Generates grid price levels."""
        # Calculate grid spacing in price units
        if grid_price_space is None:
            grid_price_space = grid_space * pip_value

        # Generate order_limit_price list
        grid_price_levels = np.linspace(
            grid_origin - grid_levels * grid_price_space,
            grid_origin + grid_levels * grid_price_space,
            2 * grid_levels + 1,
        )

        return grid_price_levels

    def build_grid(
        grid_origin: float,
        grid_space: float,
        grid_levels: int,
        order_direction: int,
        order_type: str = "stop-limit",
        grid_price_space: float = None,
        pip_value: float = 0.0001,
        take_distance: float = None,
        stop_distance: float = None,
        stop_type: str = None,
    ) -> dict:
        """Generates a grid of orders.

        Parameters
        ----------
        grid_origin : float
            The origin of grid, specified as a price.

        grid_space : float
            The spacing between grid levels, specified as pip distance.

        grid_levels : int
            The number of grid levels either side of origin.

        order_direction : int
            The direction of each grid level order (1 for long, -1 for short).

        order_type : str, optional
            The order type of each grid level order. The default is 'stop-limit'.

        grid_price_space : float, optional
            The spacing between grid levels, specified as price units distance.
            The default is None.

        pip_value : float, optional
            The instrument-specific pip value. The default is 0.0001.

        take_distance : float, optional
            The distance (in pips) of each order's take profit. The default is None.

        stop_distance : float, optional
            The distance (in pips) of each order's stop loss. The default is None.

        stop_type : str, optional
            The stop loss type. The default is None.

        Returns
        -------
        grid : dict
            A dictionary containing all orders on the grid.

        """

        # Check if stop_distance was provided without a stop_type
        if stop_distance is not None and stop_type is None:
            # set stop_type to 'limit' by default
            stop_type = "limit"

        # Calculate grid spacing in price units
        if grid_price_space is None:
            grid_price_space = grid_space * pip_value

        # Generate order_limit_price list
        order_limit_prices = np.linspace(
            grid_origin - grid_levels * grid_price_space,
            grid_origin + grid_levels * grid_price_space,
            2 * grid_levels + 1,
        )

        # Construct nominal order
        nominal_order = {}
        nominal_order["order_type"] = order_type
        nominal_order["direction"] = order_direction
        nominal_order["stop_distance"] = stop_distance
        nominal_order["stop_type"] = stop_type
        nominal_order["take_distance"] = take_distance

        # Build grid
        grid = {}

        for order, limit_price in enumerate(order_limit_prices):
            grid[order] = nominal_order.copy()
            grid[order]["order_stop_price"] = order_limit_prices[order]
            grid[order]["order_limit_price"] = order_limit_prices[order]

        return grid

    def merge_grid_orders(grid_1: np.array, grid_2: np.array) -> np.array:
        """Merges grid dictionaries into one and re-labels order numbers so each
        order number is unique.
        """
        order_offset = len(grid_1)
        grid = grid_1.copy()

        for order_no in grid_2:
            grid[order_no + order_offset] = grid_2[order_no]

        return grid

    def last_level_crossed(data: pd.DataFrame, base: float):
        """Returns a list containing the last grid level touched.
        The grid levels are determined by the base input variable,
        which corresponds to the pip_space x pip_value.
        """
        last_level_crossed = np.nan
        levels_crossed = []
        for i in range(len(data)):
            high = data["high"].values[i]
            low = data["low"].values[i]

            upper_prices = []
            lower_prices = []

            for price in [high, low]:
                upper_prices.append(base * np.ceil(price / base))
                lower_prices.append(base * np.floor(price / base))

            if lower_prices[0] != lower_prices[1]:
                # Candle has crossed a level
                last_level_crossed = lower_prices[0]

            levels_crossed.append(last_level_crossed)

        return pd.Series(levels_crossed, name="levels_crossed")

    def build_multiplier_grid(
        origin: float,
        direction: int,
        multiplier: float,
        no_levels: int,
        precision: int,
        spacing: float,
    ) -> list:
        """Constructs grid levels with a multiplying grid space.

        Parameters
        ----------
        origin : float
            The origin of grid as price amount.

        direction : int
            The direction of grid (1 for long, -1 for short).

        multiplier : float
            The grid space multiplier when price moves away from the origin
            opposite to direction.

        no_levels : int
            The number of levels to calculate either side of the origin.

        precision : int
            The instrument precision (eg. 4 for most currencies, 2 for JPY).

        spacing : float
            The spacing of the grid in price units.
        """

        levels = [i for i in range(1, no_levels + 1)]

        pos_levels = [round(origin + direction * spacing *
                            i, precision) for i in levels]
        neg_spaces = [spacing * multiplier ** (i) for i in levels]
        neg_levels = []
        prev_neg_level = origin
        for i in range(len(levels)):
            next_neg_level = prev_neg_level - direction * neg_spaces[i]
            prev_neg_level = next_neg_level
            neg_levels.append(round(next_neg_level, precision))

        grid = neg_levels + [origin] + pos_levels
        grid.sort()

        return grid

    def last_level_touched(data: pd.DataFrame, grid: np.array) -> np.array:
        """Calculates the grid levels touched by price data."""
        # initialise with nan
        last_level_crossed = np.nan

        levels_touched = []
        for i in range(len(data)):
            high = data["high"].values[i]
            low = data["low"].values[i]

            upper_prices = []
            lower_prices = []

            for price in [high, low]:
                # Calculate level above
                upper_prices.append(
                    grid[next(x[0] for x in enumerate(grid) if x[1] > price)]
                )

                # calculate level below
                first_level_below_index = next(
                    x[0] for x in enumerate(grid[::-1]) if x[1] < price
                )
                lower_prices.append(grid[-(first_level_below_index + 1)])

            if lower_prices[0] != lower_prices[1]:
                # Candle has crossed a level, since the level below the candle high
                # is different to the level below the candle low.
                # This essentially means the grid level is between candle low and high.
                last_level_crossed = lower_prices[0]

            levels_touched.append(last_level_crossed)

        return levels_touched

    @classmethod
    def stoch_rsi(
        cls,
        data: pd.DataFrame,
        K_period: int = 3,
        D_period: int = 3,
        RSI_length: int = 14,
        Stochastic_length: int = 14,
    ):
        """Stochastic RSI indicator."""
        rsi1 = cls._FinTa().RSI(data, period=RSI_length)
        stoch = autotrader.stochastic(rsi1, rsi1, rsi1, Stochastic_length)

        K = pta.sma(stoch, K_period)
        D = pta.sma(K, D_period)

        return K, D

    def stochastic(
        data: pd.DataFrame, period: int = 14
    ) -> pd.Series:
        """Stochastics indicator."""
        high, low, close = data.high, data.low, data.close
        K = np.zeros(len(high))

        for i in range(period, len(high)):
            low_val = min(low[i - period + 1: i + 1])
            high_val = max(high[i - period + 1: i + 1])

            K[i] = 100 * (close[i] - low_val) / (high_val - low_val)

        return K

    def sma(data: pd.Series, period: int = 14):
        """Smoothed Moving Average."""
        sma_list = []
        for i in range(len(data)):
            average = sum(data[i - period + 1: i + 1]) / period
            sma_list.append(average)
        return pd.Series(sma_list, name='sma')

    def ema(data: pd.Series, period: int = 14, smoothing: int = 2):
        """Exponential Moving Average."""
        ema = [sum(data[:period]) / period]
        for price in data[period:]:
            ema.append(
                (price * (smoothing / (1 + period)))
                + ema[-1] * (1 - (smoothing / (1 + period)))
            )
        for i in range(period - 1):
            ema.insert(0, np.nan)
        return pd.Series(ema, name='ema')

    def true_range(data: pd.DataFrame, period: int = 14):
        """True range."""
        high_low = data["high"] - data["low"]
        high_close = np.abs(data["high"] - data["close"].shift(period))
        low_close = np.abs(data["low"] - data["close"].shift(period))
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range

    def atr(data: pd.DataFrame, period: int = 14):
        """Average True Range."""
        tr = pta.true_range(data, period)
        atr = tr.rolling(period).sum() / period
        return atr

    def create_bricks(data: pd.DataFrame, brick_size: float = 0.002, column: str = "close"):
        """Creates a dataframe of price-sized bricks.

        Parameters
        ----------
        data : pd.DataFrame
            The OHLC price data.

        brick_size : float, optional
            The brick size in price units. The default is 0.0020.

        column : str, optional
            The column of the OHLC to use. The default is 'Close'.

        Returns
        -------
        bricks : pd.DataFrame
            The Open and Close prices of each brick, indexed by brick close time.

        """
        brick_open = data[column][0]
        opens = [brick_open]
        close_times = [data.index[0]]
        for i in range(len(data)):
            price = data[column][i]
            price_diff = price - brick_open
            if abs(price_diff) > brick_size:
                # New brick(s)
                no_new_bricks = abs(int(price_diff / brick_size))
                for b in range(no_new_bricks):
                    brick_close = brick_open + np.sign(price_diff) * brick_size
                    brick_open = brick_close
                    opens.append(brick_open)
                    close_times.append(data.index[i])

        bricks = pd.DataFrame(
            data={"open": opens, "close": opens}, index=close_times)
        bricks["close"] = bricks["close"].shift(-1)

        return bricks

    def _conditional_ema(x, condition=1, n=14, s=2):
        "Conditional sampling EMA functtion"
        if type(condition) == int:
            condition = condition * np.ones(len(x))

        ema = np.zeros(len(x))
        for i in range(1, len(x)):
            if condition[i]:
                ema[i] = (x[i] - ema[i - 1]) * (s / (1 + n)) + ema[i - 1]
            else:
                ema[i] = ema[i - 1]

        return pd.Series(ema, x.index, name=f"{n} period conditional EMA")

    def _conditional_sma(x: pd.Series, condition=1, n=14):
        "Conditional sampling SMA functtion"

        if type(condition) == int:
            condition = condition * np.ones(len(x))

        # Calculate SMA
        sma = x.rolling(n).mean()

        # Filter by condition
        sma = sma * condition

        return sma

    def _stdev(x, n):
        "Standard deviation function"
        sd = np.sqrt(autotrader._conditional_sma(x**2, 1, n) -
                     autotrader._conditional_sma(x, 1, n) ** 2)
        return sd

    @classmethod
    def _range_size(cls, x, scale="AverageChange", qty=2.618, n=14):
        "Range size function"
        rng_size = 0

        if scale == "AverageChange":
            AC = autotrader._conditional_ema(abs(x - x.shift(1)), 1, n)
            rng_size = qty * AC
        elif scale == "ATR":
            tr = cls._FinTa().TR(x)
            atr = autotrader._conditional_ema(tr, 1, n)
            rng_size = qty * atr
        elif scale == "StandardDeviation":
            sd = autotrader._stdev(x, n)
            rng_size = qty * sd

        return rng_size

    def _calculate_range_filter(h, idx, rng, n, rng_type, smooth, sn, av_rf, av_n):
        """Two type range filter function."""

        smoothed_range = autotrader._conditional_ema(rng, 1, sn)
        r = smoothed_range if smooth else rng
        r_filt = (h + idx) / 2

        if rng_type == 1:
            for i in range(1, len(h)):
                if h[i] - r[i] > r_filt[i - 1]:
                    r_filt[i] = h[i] - r[i]
                elif idx[i] + r[i] < r_filt[i - 1]:
                    r_filt[i] = idx[i] + r[i]
                else:
                    r_filt[i] = r_filt[i - 1]

        elif rng_type == 2:
            for i in range(1, len(h)):
                if h[i] >= r_filt[i - 1] + r[i]:
                    r_filt[i] = (
                        r_filt[i - 1] +
                        np.floor(abs(h[i] - r_filt[i - 1]) / r[i]) * r[i]
                    )
                elif idx[i] <= r_filt[i - 1] - r[i]:
                    r_filt[i] = (
                        r_filt[i - 1] -
                        np.floor(abs(idx[i] - r_filt[i - 1]) / r[i]) * r[i]
                    )
                else:
                    r_filt[i] = r_filt[i - 1]

        # Define nominal values
        r_filt1 = r_filt.copy()
        hi_band1 = r_filt1 + r
        lo_band1 = r_filt1 - r

        # Calculate indicator for averaged filter changes
        r_filt2 = autotrader._conditional_ema(
            r_filt1, r_filt1 != r_filt1.shift(1), av_n)
        hi_band2 = autotrader._conditional_ema(
            hi_band1, r_filt1 != r_filt1.shift(1), av_n)
        lo_band2 = autotrader._conditional_ema(
            lo_band1, r_filt1 != r_filt1.shift(1), av_n)

        # Assign indicator
        rng_filt = r_filt2 if av_rf else r_filt1
        hi_band = hi_band2 if av_rf else hi_band1
        lo_band = lo_band2 if av_rf else lo_band1

        # Construct output
        rfi = pd.DataFrame(
            data={"upper": hi_band, "lower": lo_band, "rf": rng_filt}, index=rng_filt.index
        )

        # Classify filter direction
        rfi["fdir"] = np.sign(rfi.rf - rfi.rf.shift(1)).fillna(0)

        return rfi

    @classmethod
    def chandelier_exit(
        data: pd.DataFrame, length: int = 22, mult: float = 3.0, use_close: bool = False
    ):
        # ohlc4 = (data["open"] + data["high"] + data["low"] + data["close"]) / 4

        atr = mult * cls._FinTa().ATR(data, length)

        high_field = "close" if use_close else "high"
        low_field = "close" if use_close else "low"

        longstop = data[high_field].rolling(length).max() - atr
        shortstop = data[low_field].rolling(length).min() + atr

        direction = np.where(data["close"] > shortstop, 1, -1)

        chandelier_df = pd.concat(
            {
                "longstop": longstop,
                "shortstop": shortstop,
            },
            axis=1,
        )
        chandelier_df["direction"] = direction
        chandelier_df["signal"] = np.where(
            chandelier_df["direction"] != chandelier_df["direction"].shift(),
            chandelier_df["direction"],
            0,
        )

        return chandelier_df


def transform_array(X: Any) -> np.ndarray:
    if hasattr(X, "_df"):
        X = X._df
    assert isinstance(X, Iterable)
    if hasattr(X, "values"):
        X = X.values
    if not isinstance(X, np.ndarray):
        X = np.array(X)
    if len(X.shape) < 2:
        X = X.reshape(-1, 1)
    return X


class SignalFeatures(LazyImport):

    @classmethod
    def Binarizer(cls, X: Iterable, y: Optional[Iterable] = None, threshold: float = 0.0, copy: bool = True, fit_params: dict = {}, **kwargs):
        X = transform_array(X)
        return cls.sp().Binarizer(threshold=threshold, copy=copy).fit_transform(X, y, **fit_params)

    @classmethod
    def FunctionTransformer(cls,
                            X: Iterable,
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
        X = transform_array(X)
        return cls.sp().FunctionTransformer(func=func, inverse_func=inverse_func, validate=validate, accept_sparse=accept_sparse,
                                            check_inverse=check_inverse, feature_names_out=feature_names_out, kw_args=kw_args, inv_kw_args=inv_kw_args).fit_transform(X, y, **fit_params)

    @classmethod
    def KBinsDiscretizer(cls,
                         X: Iterable,
                         y: Optional[Iterable] = None,
                         n_bins=5,
                         encode: Literal['onehot',
                                         'onehot-dense', 'ordinal'] = "onehot",
                         strategy: Literal['uniform',
                                           'quantile', 'kmeans'] = "quantile",
                         dtype: Optional[float] = None,
                         subsample: Optional[Union[int,
                                                   Literal['warn']]] = "warn",
                         random_state: Optional[Union[int,
                                                      RandomState]] = None,
                         fit_params: dict = {},
                         **kwargs
                         ):
        X = transform_array(X)
        return cls.sp().KBinsDiscretizer(n_bins=n_bins, encode=encode, strategy=strategy, dtype=dtype, subsample=subsample, random_state=random_state).fit_transform(X, y, **fit_params)

    @classmethod
    def KernelCenterer(cls, X: Iterable, y: Optional[Iterable] = None, fit_params: dict = {}, **kwargs):
        X = transform_array(X)
        return cls.sp().KernelCenterer().fit_transform(X, y, **fit_params)

    @classmethod
    def LabelBinarizer(cls, X: Iterable, y: Optional[Iterable] = None, neg_label: int = 0, pos_label: int = 1, sparse_output: bool = False, **kwargs):
        X = transform_array(X)
        return cls.sp().LabelBinarizer(neg_label=neg_label, pos_label=pos_label, sparse_output=sparse_output).fit_transform(y)

    @classmethod
    def LabelEncoder(cls, X: Iterable, y: Optional[Iterable] = None, **kwargs):
        X = transform_array(X)
        return cls.sp().LabelEncoder().fit_transform(y)

    @classmethod
    def MultiLabelBinarizer(cls, X: Iterable, y: Optional[Iterable] = None, classes=Optional[np.ndarray], sparse_output: bool = False, **kwargs):
        X = transform_array(X)
        return cls.sp().MultiLabelBinarizer(classes=classes, sparse_output=sparse_output).fit_transform(y)

    @classmethod
    def MinMaxScaler(cls, X: Iterable, y: Optional[Iterable] = None, feature_range: tuple[int] = (0, 1), copy: bool = True, clip: bool = False, fit_params: dict = {}, **kwargs):
        X = transform_array(X)
        return cls.sp().MinMaxScaler(feature_range=feature_range, copy=copy, clip=clip).fit_transform(X, y, **fit_params)

    @classmethod
    def MaxAbsScaler(cls, X: Iterable, y: Optional[Iterable] = None, copy: bool = True, fit_params: dict = {}, **kwargs):
        X = transform_array(X)
        return cls.sp().MaxAbsScaler(copy=copy).fit_transform(X, y, **fit_params)

    @classmethod
    def QuantileTransformer(cls,
                            X: Iterable,
                            y: Optional[Iterable] = None,
                            n_quantiles: int = 1000,
                            output_distribution: Literal['uniform',
                                                         'normal'] = "uniform",
                            ignore_implicit_zeros: bool = False,
                            subsample: int = int(1e5),
                            random_state:  Optional[Union[int,
                                                          RandomState]] = None,
                            copy: bool = True,
                            fit_params: dict = {},
                            **kwargs
                            ):
        X = transform_array(X)
        return cls.sp().QuantileTransformer(n_quantiles=n_quantiles, output_distribution=output_distribution, ignore_implicit_zeros=ignore_implicit_zeros, subsample=subsample, random_state=random_state, copy=copy).fit_transform(X, y, **fit_params)

    @classmethod
    def Normalizer(cls, X: Iterable, y: Optional[Iterable] = None, norm: Literal['l1', 'l2', 'max'] = "l2", copy: bool = True, fit_params: dict = {}, **kwargs):
        X = transform_array(X)
        return cls.sp().Normalizer(norm=norm, copy=copy).fit_transform(X, y, **fit_params)

    @classmethod
    def OneHotEncoder(cls,
                      X: Iterable,
                      y: Optional[Iterable] = None,
                      categories: Union[Sequence[np.ndarray],
                                        Literal['auto']] = "auto",
                      drop: Optional[np.ndarray] = None,
                      sparse: Optional[str] = True,
                      dtype=np.float64,
                      handle_unknown="error",
                      min_frequency=None,
                      max_categories=None,
                      fit_params: dict = {},
                      **kwargs
                      ):
        X = transform_array(X)
        return cls.sp().OneHotEncoder(categories=categories, drop=drop, sparse=sparse, dtype=dtype, handle_unknown=handle_unknown, min_frequency=min_frequency, max_categories=max_categories).fit_transform(X, y, **fit_params)

    @classmethod
    def OrdinalEncoder(cls,
                       X: Iterable,
                       y: Optional[Iterable] = None,
                       categories="auto",
                       dtype=np.float64,
                       handle_unknown="error",
                       unknown_value=None,
                       encoded_missing_value=np.nan,
                       fit_params: dict = {},
                       **kwargs
                       ):
        X = transform_array(X)
        return cls.sp().OrdinalEncoder(categories=categories, dtype=dtype, handle_unknown=handle_unknown, unknown_value=unknown_value, encoded_missing_value=encoded_missing_value).fit_transform(X, y, **fit_params)

    @classmethod
    def PowerTransformer(cls, X: Iterable, y: Optional[Iterable] = None, method="yeo-johnson", standardize=True, copy=True, **kwargs):
        X = transform_array(X)
        return cls.sp().PowerTransformer(method=method, standardize=standardize, copy=copy).fit_transform(X, y)

    @classmethod
    def RobustScaler(cls,
                     X: Iterable,
                     y: Optional[Iterable] = None,
                     with_centering: bool = True,
                     with_scaling: bool = True,
                     quantile_range: tuple[float] = (25.0, 75.0),
                     copy: bool = True,
                     unit_variance: bool = False,
                     fit_params: dict = {},
                     **kwargs
                     ):
        X = transform_array(X)
        return cls.sp().RobustScaler(with_centering=with_centering, with_scaling=with_scaling, quantile_range=quantile_range, copy=copy, unit_variance=unit_variance).fit_transform(X, y, **fit_params)

    @classmethod
    def SplineTransformer(cls,
                          X: Iterable,
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
        X = transform_array(X)
        return cls.sp().SplineTransformer(n_knots=n_knots, degree=degree, knots=knots, extrapolation=extrapolation, include_bias=include_bias, order=order).fit_transform(X, y, **fit_params)

    @classmethod
    def StandardScaler(cls, X: Iterable, y: Optional[Iterable] = None, copy: bool = True, with_mean: bool = True, with_std: bool = True, fit_params: dict = {}, **kwargs):
        X = transform_array(X)
        return cls.sp().StandardScaler(copy=copy, with_mean=with_mean, with_std=with_std).fit_transform(X, y, **fit_params)

    @classmethod
    def add_dummy_feature(cls, X: Iterable, value: float = 1., **kwargs):
        X = transform_array(X)
        return cls.sp().add_dummy_feature(X, value=value)

    @classmethod
    def PolynomialFeatures(cls, X: Iterable, y: Optional[Iterable] = None, degree: Union[int, tuple[int, int]] = 2, interaction_only: bool = False, include_bias: bool = True, order: Literal['C', 'F'] = "C", fit_params: dict = {}, **kwargs):
        X = transform_array(X)
        return cls.sp().PolynomialFeatures(degree=degree, interaction_only=interaction_only, include_bias=include_bias, order=order).fit_transform(X, y, **fit_params)

    @classmethod
    def binarize(cls, X: Iterable, threshold: float = 0.0, copy: bool = True, **kwargs):
        X = transform_array(X)
        return cls.sp().binarize(X, threshold=threshold, copy=copy)

    @classmethod
    def normalize(cls, X: Iterable, norm: Literal['l1', 'l2', 'max'] = "l2", axis: int = 1, copy: bool = True, return_norm: bool = False, **kwargs):
        X = transform_array(X)
        return cls.sp().normalize(X, norm=norm, axis=axis, copy=copy, return_norm=return_norm)

    @classmethod
    def scale(cls, X: Iterable, axis=0, with_mean: bool = True, with_std: bool = True, copy=True, **kwargs):
        X = transform_array(X)
        return cls.sp().scale(X,  axis=axis, with_mean=with_mean, with_std=with_std, copy=copy)

    @classmethod
    def robust_scale(cls,
                     X: Iterable,
                     axis: int = 0,
                     with_centering: bool = True,
                     with_scaling: bool = True,
                     quantile_range: tuple[float, float] = (25.0, 75.0),
                     copy: bool = True,
                     unit_variance: bool = False,
                     **kwargs
                     ):
        X = transform_array(X)
        return cls.sp().robust_scale(X, axis, with_centering, with_scaling, quantile_range, copy, unit_variance)

    @classmethod
    def maxabs_scale(cls, X: Iterable, axis: int = 0, copy: bool = True, **kwargs):
        X = transform_array(X)
        return cls.sp().maxabs_scale(X, axis=axis, copy=copy)

    @classmethod
    def minmax_scale(cls, X: Iterable, feature_range: tuple[int, int] = (0, 1), axis: int = 0, copy: bool = True, **kwargs):
        X = transform_array(X)
        return cls.sp().minmax_scale(X, feature_range=feature_range, axis=axis, copy=copy)

    @classmethod
    def label_binarize(cls, X: Iterable, classes: np.ndarray, neg_label: int = 0, pos_label: int = 1, sparse_output: bool = False, **kwargs):
        X = transform_array(X)
        return cls.sp().label_binarize(X, classes, neg_label=neg_label, pos_label=pos_label, sparse_output=sparse_output)

    @classmethod
    def quantile_transform(cls,
                           X: Iterable,
                           axis: int = 0,
                           n_quantiles: int = 1000,
                           output_distribution: Literal['uniform',
                                                        'normal'] = "uniform",
                           ignore_implicit_zeros: bool = False,
                           subsample: int = int(1e5),
                           random_state: Optional[Union[int,
                                                        RandomState]] = None,
                           copy: bool = True,
                           **kwargs
                           ):
        X = transform_array(X)
        return cls.sp().quantile_transform(X, axis=axis, n_quantiles=n_quantiles, output_distribution=output_distribution, ignore_implicit_zeros=ignore_implicit_zeros, subsample=subsample, random_state=random_state, copy=copy)

    @classmethod
    def power_transform(cls, X: Iterable, method: Literal['yeo-johnson', 'box-cox'] = "yeo-johnson", standardize: bool = True, copy: bool = True, **kwargs):
        X = transform_array(X)
        return cls.sp().power_transform(X, method, standardize, copy)


class PairTrading(LazyImport):
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

    @staticmethod
    def bollinger_bands_strategy(spread_series: pd.Series, window=60, num_std=2., **kwargs) -> pd.DataFrame:
        """使用布林带生成交易信号"""
        # 计算移动均值和标准差
        spread_mean = spread_series.rolling(window=window).mean()
        spread_std = spread_series.rolling(window=window).std()

        # 计算上下轨
        upper_band = num_std * spread_std
        lower_band = -upper_band
        series = spread_series-spread_mean
        # 生成信号：突破上轨做空，突破下轨做多
        signals = np.where(series > upper_band, -1.,
                           np.where(series < lower_band, 1., 0.))
        return pd.DataFrame(dict(
            spread=series,
            upper_band=upper_band,
            lower_band=lower_band,
            signals=signals
        ))

    # ------------------------------
    # 基础方法：百分比偏差
    # ------------------------------

    @staticmethod
    def percentage_deviation_strategy(spread_series: pd.Series, window=60, threshold=0.1, **kwargs) -> Union[pd.Series, pd.DataFrame]:
        """使用百分比偏差生成交易信号"""
        spread_mean = spread_series.rolling(window=window).mean()

        # 计算百分比偏差 (spread - mean) / mean * 100
        # 避免除以零
        spread_mean = spread_mean.replace(0, 1e-10)
        pct_deviation = (spread_series - spread_mean) / spread_mean * 100.

        # 生成信号
        signals = np.where(pct_deviation > threshold, -1.,
                           np.where(pct_deviation < -threshold, 1., 0))
        return pd.DataFrame(dict(
            pct_deviation=pct_deviation,
            signals=signals
        ))

    # ------------------------------
    # 基础方法：移动窗口分位数
    # ------------------------------

    @staticmethod
    def rolling_quantile_strategy(spread_series: pd.Series, window=60, upper_quantile=0.95, lower_quantile=0.05, **kwargs) -> pd.DataFrame:
        """使用移动窗口分位数生成交易信号"""
        spread_mean = spread_series.rolling(window=window).mean()
        # 计算滚动分位数
        upper_threshold = spread_series.rolling(
            window=window).quantile(upper_quantile)-spread_mean
        lower_threshold = spread_series.rolling(
            window=window).quantile(lower_quantile)-spread_mean
        series = spread_series-spread_mean

        # 生成信号
        signals = np.where(series > upper_threshold, -1.,
                           np.where(series < lower_threshold, 1., 0.))

        return pd.DataFrame(dict(
            spread=series,
            upper_threshold=upper_threshold,
            lower_threshold=lower_threshold,
            signals=signals
        ))

    # ------------------------------
    # 基础方法：Z-score
    # ------------------------------

    @staticmethod
    def z_score_strategy(spread_series: pd.Series, window=60, z_threshold=2.0, **kwargs) -> Union[pd.DataFrame, pd.Series]:
        """使用Z-score生成交易信号"""
        spread_mean = spread_series.rolling(window=window).mean()
        spread_std = spread_series.rolling(window=window).std()

        # 避免除以零
        spread_std = spread_std.replace(0, 1e-10)
        z_score = (spread_series - spread_mean) / spread_std
        # 生成信号
        signals = np.where(z_score > z_threshold, -1,
                           np.where(z_score < -z_threshold, 1, 0))
        return pd.DataFrame(dict(
            z_score=z_score,
            signals=signals
        ))

    # ------------------------------
    # 高级方法：Hurst指数过滤
    # ------------------------------

    @staticmethod
    def calculate_hurst_exponent(series, max_lag=20):
        """计算Hurst指数"""
        lags = range(2, max_lag + 1)

        tau = []
        for lag in lags:
            diff = np.subtract(series[lag:], series[:-lag])
            std = np.std(diff)
            tau.append(std if std != 0 else 1e-10)

        try:
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return poly[0]
        except:
            return 0.5

    @staticmethod
    def hurst_filter_strategy(spread_series, hurst_threshold=0.5, z_threshold=2.0, **kwargs) -> pd.DataFrame:
        """使用Hurst指数过滤交易信号"""
        hurst = PairTrading.calculate_hurst_exponent(spread_series)
        # print(f"Hurst指数: {hurst:.4f}")

        # 先计算Z-score
        zscore = PairTrading.z_score_strategy(
            spread_series, z_threshold=z_threshold, signal=True)
        z_signals, z_score = zscore.signals, zscore.z_score
        # 应用Hurst过滤
        if hurst >= hurst_threshold:
            signals = np.zeros_like(z_signals)
        else:
            signals = z_signals

        return pd.DataFrame(dict(
            z_score=z_score,
            signals=signals))

    # ------------------------------
    # 高级方法：卡尔曼滤波
    # ------------------------------

    @classmethod
    def kalman_filter_strategy(cls, x_series, y_series, z_threshold=2., **kwargs) -> pd.DataFrame:
        """使用卡尔曼滤波生成动态价差和交易信号"""
        # 初始化卡尔曼滤波器
        kf = cls.KalmanFilter()(
            transition_matrices=[[1, 0], [0, 1]],
            observation_matrices=[[x_series.values[0], 1]],
            initial_state_mean=[0, 0],
            initial_state_covariance=np.eye(2),
            observation_covariance=1.0,
            transition_covariance=np.eye(2) * 0.01
        )

        # 应用卡尔曼滤波
        state_means, _ = kf.filter(y_series.values)
        hedge_ratios = state_means[:, 0]
        intercepts = state_means[:, 1]

        # 计算动态价差
        dynamic_spread = y_series.values - hedge_ratios * x_series.values - intercepts
        dynamic_spread = pd.Series(dynamic_spread, index=x_series.index)
        data = pd.DataFrame(dict(
            hedge_ratios=hedge_ratios,
        ))

        # 对动态价差应用Z-score生成信号
        zscore = PairTrading.z_score_strategy(
            dynamic_spread, z_threshold=z_threshold)

        return pd.concat([data, zscore], axis=1)

    # ------------------------------
    # 高级方法：GARCH模型
    # ------------------------------

    @classmethod
    def garch_volatility_adjusted_signals(cls, spread_series: pd.Series, z_threshold=2.0, **kwargs) -> pd.DataFrame:
        """使用GARCH模型调整波动率"""
        # 关键修复：强制转换为数值类型，非数值转为NaN
        spread_series = pd.to_numeric(spread_series, errors='coerce')
        # 移除NaN和无穷值
        spread_series = spread_series.replace(
            [np.inf, -np.inf], np.nan).dropna()

        # 若清理后数据为空，直接返回空结果
        if spread_series.empty:
            return pd.DataFrame(columns=['volatility', 'garch_z_score', 'signals'])
        # 解决数据缩放问题
        spread_scaled = spread_series * 100

        # 拟合GARCH(1,1)模型
        model = cls.arch_model()(spread_scaled.values, vol='GARCH', p=1, q=1)
        garch_results = model.fit(disp='off')

        # 获取条件波动率并还原缩放
        volatility = pd.Series(garch_results.conditional_volatility) / 100
        spread_mean = spread_series.rolling(window=60).mean()

        # 避免除以零
        volatility = volatility.replace(0, 1e-10)
        garch_z_score = (spread_series - spread_mean) / volatility
        # 生成信号
        signals = np.where(garch_z_score > z_threshold, -1,
                           np.where(garch_z_score < -z_threshold, 1, 0))
        return pd.DataFrame(dict(
            garch_z_score=garch_z_score,
            signals=signals
        ))

    # ------------------------------
    # 高级方法：手动实现VECM模型
    # ------------------------------

    @staticmethod
    def johansen_test_manual(series, lags=2):
        """手动实现简化版Johansen协整检验，确保所有滞后项长度一致"""
        # 确保输入是数值型且无缺失值
        if not np.issubdtype(series.dtype, np.number):
            # 尝试转换为数值类型，非数值转为NaN
            series = np.array([pd.to_numeric(col, errors='coerce')
                              for col in series.T]).T

        # 移除包含NaN的行
        series = series[~np.isnan(series).any(axis=1)]

        # 检查数据量是否足够
        n = series.shape[0]
        k = series.shape[1]  # 变量数量

        # 确保有足够数据进行滞后计算（至少需要lags+1个样本）
        required_length = lags + 10  # 增加安全边际
        if n < required_length:
            raise ValueError(f"数据量不足，需要至少{required_length}个样本，实际只有{n}个")
        if k < 2:
            raise ValueError("至少需要2个变量进行协整检验")

        # 计算一阶差分（长度为n-1）
        diff_series = np.diff(series, axis=0)
        diff_length = len(diff_series)  # 应为n-1

        # 构建滞后项（确保所有滞后项长度与差分序列一致）
        lagged_terms = []
        max_possible_length = diff_length  # 最大可能长度为差分序列长度

        for i in range(1, lags + 1):
            # 计算当前滞后项可获取的最大长度
            current_possible_length = n - i
            # 取与差分序列长度的较小值，确保不越界
            take_length = min(max_possible_length, current_possible_length)

            # 截取滞后项，确保长度一致
            lagged = series[i:i + take_length, :]

            # 如果长度仍不足，用最后一个值填充（处理极端情况）
            if len(lagged) < max_possible_length:
                fill_length = max_possible_length - len(lagged)
                last_val = lagged[-1:] if len(lagged) > 0 else np.zeros((1, k))
                lagged = np.vstack(
                    [lagged, np.repeat(last_val, fill_length, axis=0)])

            lagged_terms.append(lagged)

        # 检查所有滞后项长度是否一致
        lengths = [len(lt) for lt in lagged_terms]
        if len(set(lengths)) != 1:
            # 最后的安全措施：统一截取到最短长度
            min_length = min(lengths)
            lagged_terms = [lt[:min_length] for lt in lagged_terms]
            diff_series = diff_series[:min_length]  # 同时调整差分序列长度
            print(f"警告：滞后项长度不一致，已统一调整为{min_length}")

        # 合并所有滞后项为一个矩阵
        lagged_series = np.hstack(lagged_terms)

        # 构建回归模型的X矩阵 (添加常数项)
        X = sm.add_constant(lagged_series)

        # 确保X中没有NaN或无穷值
        if not np.isfinite(X).all():
            raise ValueError("回归模型输入包含非有限值，请检查原始数据")

        # 拟合OLS模型
        model = sm.OLS(diff_series, X).fit()
        u = model.resid  # 残差

        # 计算协方差矩阵
        S_uu = np.cov(u.T)
        S_ut = np.cov(u.T, series[1:1+len(diff_series), :].T)[0:k, k:]
        S_tt = np.cov(series[1:1+len(diff_series), :].T)

        # 计算特征值和特征向量（增加数值稳定性处理）
        try:
            S_tt_inv = np.linalg.pinv(S_tt)  # 使用伪逆提高稳定性
            M = np.dot(np.dot(S_ut.T, np.linalg.pinv(S_uu)), S_ut)
            eigvals, eigvecs = np.linalg.eig(np.dot(S_tt_inv, M))
        except np.linalg.LinAlgError:
            # 处理矩阵奇异的情况
            return np.array([1.0, -1.0])  # 退回到简单的价差比例

        # 返回最大特征值对应的协整向量（归一化处理）
        max_eig_idx = np.argmax(eigvals)
        coint_vector = eigvecs[:, max_eig_idx]

        # 归一化协整向量（确保第一个元素为1或-1，便于解释）
        if coint_vector[0] != 0:
            coint_vector = coint_vector / coint_vector[0]

        return coint_vector

    @staticmethod
    def vecm_based_signals(x_series, y_series, window=60, lag=2, **kwargs) -> Union[pd.DataFrame, pd.Series]:
        """完全手动实现的VECM模型，确保输入数据长度一致"""
        # 数据预处理：转换为数值类型并删除缺失值
        x_series = pd.to_numeric(x_series, errors='coerce').dropna()
        y_series = pd.to_numeric(y_series, errors='coerce').dropna()

        # 关键修复：强制对齐两个序列的长度（取交集）
        # 基于索引对齐
        combined = pd.DataFrame({'x': x_series, 'y': y_series}).dropna()

        # 如果对齐后数据不足，直接报错
        min_required = 100  # 最小数据量要求
        if len(combined) < min_required:
            raise ValueError(
                f"对齐后的数据量不足，需要至少{min_required}个样本，实际只有{len(combined)}个")

        # 转换为numpy数组
        series = combined[['x', 'y']].values

        # 手动进行协整检验
        coint_vector = PairTrading.johansen_test_manual(series, lags=lag)

        # 计算误差修正项(ECT)
        ect = np.dot(series, coint_vector)
        ect = pd.Series(ect, index=combined.index)
        ect_mean = ect.mean()
        ect -= ect_mean  # 中心化处理

        # 生成交易信号（使用滚动分位数更稳健）
        # window = max(60, len(ect) // 5)  # 动态窗口大小
        upper_threshold = ect.rolling(window=window).quantile(0.90)
        lower_threshold = ect.rolling(window=window).quantile(0.10)

        signals = np.where(ect > upper_threshold, -1.,
                           np.where(ect < lower_threshold, 1., 0.))
        return pd.DataFrame(dict(
            ect=ect,
            upper_threshold=upper_threshold,
            lower_threshold=lower_threshold,
            signals=signals
        ))


class Factors(LazyImport):

    @staticmethod
    def single_asset_multi_factor_strategy(price: pd.DataFrame, factors: pd.DataFrame, window=10, top_pct=0.2, bottom_pct=0.2, isstand=True, **kwargs):
        """
        单资产多因子策略实现，根据因子重要性自动设置权重
        """
        # 计算未来收益率（使用下一期收盘价的涨跌幅）
        returns_series = price.pct_change(
        ).shift(-1).fillna(0.)  # 预测下一期收益
        # 因子标准化函数 (z-score)

        def standardize(factor_series: pd.Series):  # , window: int):
            # mean = factor_series.rolling(window).mean()
            # std = factor_series.rolling(window).std()
            mean = factor_series.mean()
            std = factor_series.std()
            return (factor_series - mean) / std

        names = list(factors.columns)
        # 标准化因子
        factors = [factors[name] for name in names]  # 简化因子提取方式
        if isstand:
            factors = [standardize(factor) for factor in factors]

        # 计算因子IC (信息系数) - 单资产版本
        def calculate_single_asset_ic(factor_series: pd.Series, returns_series: pd.Series, window=20):
            rolling_ic = pd.Series(index=factor_series.index, dtype='float64')
            for i in range(window, len(factor_series)):
                start_idx = i - window
                end_idx = i
                factor_window = factor_series.iloc[start_idx:end_idx]
                returns_window = returns_series.iloc[start_idx:end_idx]
                valid_mask = ~(factor_window.isna() | returns_window.isna())
                if valid_mask.sum() < 3:
                    rolling_ic.iloc[i] = np.nan
                    continue
                ic, _ = scipy_stats.spearmanr(
                    factor_window[valid_mask], returns_window[valid_mask])
                rolling_ic.iloc[i] = ic
            return rolling_ic

        # 计算各因子的IC序列
        factors_ic = [calculate_single_asset_ic(
            factor, returns_series, window) for factor in factors]

        # 计算因子权重 (基于IC的滚动表现)
        def calculate_factor_weights(ic_series: pd.Series, window=20):
            rolling_ic_mean = ic_series.abs().rolling(window).mean()
            smoothed_weights = rolling_ic_mean.ewm(span=window).mean()
            total_weight = pd.Series(0.0, index=ic_series.index)
            for ic in factors_ic:
                total_weight += ic.abs().rolling(window).mean()
            normalized_weights = smoothed_weights / total_weight
            normalized_weights = normalized_weights.fillna(1.0 / len(factors))
            return normalized_weights

        # 计算各因子的动态权重
        factors_weight = [calculate_factor_weights(
            ic, window) for ic in factors_ic]

        # 修正权重总和为1
        weight_sum = sum(factors_weight)
        # factors_weight = [weight/weight_sum for weight in factors_weight]
        valid_mask = ~(weight_sum.isna() | (weight_sum == 0))
        n_factors = len(factors_weight)
        factors_weight_corrected = []
        for weight in factors_weight:
            corrected = weight.where(valid_mask, np.nan)
            corrected = corrected / weight_sum.where(valid_mask, np.nan)
            corrected = corrected.fillna(1.0 / n_factors)
            factors_weight_corrected.append(corrected)
        # 强制修正浮点数精度
        for i in price.index:
            current_sum = sum(weight.loc[i]
                              for weight in factors_weight_corrected)
            if not np.isclose(current_sum, 1.0, atol=1e-6):
                error = 1.0 - current_sum
                factors_weight_corrected[0].loc[i] += error
        factors_weight = factors_weight_corrected

        # 生成综合得分
        combined_score = pd.Series(index=price.index, dtype='float64')
        for i in price.index:
            if i in factors[0].index:
                score = 0.0
                for j in range(len(factors)):
                    if i in factors[j].index and i in factors_weight[j].index:
                        score += factors[j].loc[i] * factors_weight[j].loc[i]
                combined_score.loc[i] = score

        # 生成交易信号
        signals = pd.Series(0, index=price.index)
        for i in price.index[window:]:
            if i in combined_score.index:
                current_score = combined_score.loc[i]
                start_idx = max(0, combined_score.index.get_loc(i) - window)
                end_idx = combined_score.index.get_loc(i)
                score_history = combined_score.iloc[start_idx:end_idx]
                if len(score_history) >= 3:
                    top_threshold = score_history.quantile(1 - top_pct)
                    bottom_threshold = score_history.quantile(bottom_pct)
                    if current_score > top_threshold:
                        signals.loc[i] = 1
                    elif current_score < bottom_threshold:
                        signals.loc[i] = -1

        # # 构建返回的指标字典
        # metrics = {f'factor_{names[i]}_weight': factors_weight[i]
        #         for i in range(len(factors))}
        # metrics.update({f'factor_{names[i]}_ic': factors_ic[i]
        #             for i in range(len(factors))})
        return pd.DataFrame(dict(
            combined_score=combined_score,
            signals=signals
        ))
        # return signals, combined_score#, metrics, factors, names

    def evaluate_factors(price: pd.Series, factors: pd.DataFrame, window=20, **kwargs):
        """IC均值、标准差和IR"""
        results = {}
        # 计算未来收益率（使用下一期收盘价的涨跌幅）
        returns = price.pct_change(
        ).shift(-1).fillna(0.)  # 预测下一期收益
        returns = returns.values
        for factor_name in factors.columns:
            factor = factors[factor_name].values
            # 计算滚动IC
            rolling_ic = []
            factor = factor[~np.isnan(factor)]
            for i in range(window, len(factor)):
                ic, _ = scipy_stats.spearmanr(
                    factor[i-window:i], returns[i-window:i])
                rolling_ic.append(ic)
            # 计算IC均值、标准差和IR
            ic_mean = np.mean(rolling_ic)
            ic_std = np.std(rolling_ic)
            ir = ic_mean / ic_std if ic_std != 0. else 0.
            results[factor_name] = {"IC_mean": ic_mean, "IR": ir}

        # 按IC均值排序
        factor_stats = pd.DataFrame(results).T.sort_values(
            "IC_mean", ascending=False)
        valid_factors = factor_stats[(factor_stats["IC_mean"] > 0.) & (
            factor_stats["IR"] > 0.)].index
        # valid_factors = factor_stats[(factor_stats["IC_mean"] > 0.05) & (
        #     factor_stats["IR"] > 0.5)].index
        # 计算相关系数矩阵
        corr_matrix = factors[valid_factors].corr().abs()
        # 找出高度相关的因子对
        redundant_pairs = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                if corr_matrix.iloc[i, j] > 0.8:
                    redundant_pairs.append(
                        (corr_matrix.columns[i], corr_matrix.columns[j]))

        # 保留IC更高的因子
        factors_to_remove = set()
        for pair in redundant_pairs:
            factor1, factor2 = pair
            if factor_stats.loc[factor1, "IC_mean"] > factor_stats.loc[factor2, "IC_mean"]:
                factors_to_remove.add(factor2)
            else:
                factors_to_remove.add(factor1)

        final_factors = [
            f for f in valid_factors if f not in factors_to_remove]
        return final_factors, factor_stats

    @classmethod
    def pca_trend_indicator(cls, price: pd.Series, factors: pd.DataFrame, n_components=2,
                            dynamic_sign=True, filter_low_variance=True):
        """
        使用PCA融合多个均线，生成趋势指标

        参数:
        price: 价格序列
        windows: 均线窗口列表
        n_components: 保留的主成分数量
        dynamic_sign: 是否根据主成分与价格的相关性自动调整符号
        filter_low_variance: 是否过滤低方差因子

        返回:
        优化后的PCA趋势指标
        """
        # 计算各均线
        # factors = pd.DataFrame()
        # for w in windows:
        #     factors[f'MA_{w}'] = price.rolling(w).mean()

        # 过滤低方差因子（避免PCA被常数因子干扰）
        if filter_low_variance:
            original_columns = factors.columns
            factors = factors.loc[:, factors.var() > 0.1]  # 保留方差>0.1的因子
            if len(factors.columns) < len(original_columns):
                print(f"过滤了{len(original_columns)-len(factors.columns)}个低方差因子")

        # 去除NaN
        factors = factors.dropna()
        if factors.empty:
            raise ValueError("所有因子在去除NaN后均为空")
        # 标准化
        scaler = cls.sp().StandardScaler()
        scaled_data = scaler.fit_transform(factors)

        # PCA降维
        pca = cls.sklearn_decomposition().PCA(
            n_components=min(n_components, len(factors.columns)))
        principal_components = pca.fit_transform(scaled_data)

        # 计算主成分加权组合（使用方差解释比例作为权重）
        weights = pca.explained_variance_ratio_
        combined_trend = np.average(
            principal_components, weights=weights, axis=1)

        # 转回Series
        pca_trend = pd.Series(combined_trend, index=factors.index)

        # 动态调整符号（确保与价格正相关）
        if dynamic_sign and len(pca_trend) > 10:  # 确保有足够数据计算相关性
            corr = pca_trend.corr(price.loc[pca_trend.index])
            if corr < 0:
                pca_trend = -pca_trend
                # print(f"已调整PCA趋势指标符号（原相关性：{corr:.4f}）")

        # 缩放至与价格相近的范围以便可视化
        # try:
        #     pca_trend = pca_trend * (price.std() / pca_trend.std()) + price.mean()
        # except ZeroDivisionError:
        #     print("PCA趋势指标标准差为0，使用替代缩放方法")
        #     pca_trend = pca_trend * price.std() + price.mean()

        # 返回结果和诊断信息
        # diagnostics = {
        #     'explained_variance_ratio': pca.explained_variance_ratio_,
        #     'loadings': pd.DataFrame(pca.components_, columns=factors.columns,
        #                              index=[f'PC{i+1}' for i in range(pca.n_components_)])
        # }

        return pca_trend  # , diagnostics

    def adaptive_weight_trend(price: pd.Series, windows=[5, 20, 50], lookback=60, **kwargs):
        """
        基于因子历史表现的自适应权重趋势指标

        参数:
        price: 价格序列
        windows: 均线窗口列表
        lookback: 计算权重的回溯窗口

        返回:
        自适应权重的趋势指标
        """
        # 计算各均线
        ma_list = [price.rolling(w).mean() for w in windows]

        # 初始化结果序列
        adaptive_trend = pd.Series(index=price.index, dtype=np.float64)

        for i in range(max(windows) + lookback, len(price)):
            # 回溯窗口
            start = i - lookback
            end = i

            # 计算各因子在回溯窗口内的表现（与价格的相关性）
            correlations = []
            for ma in ma_list:
                corr = ma.iloc[start:end].corr(price.iloc[start:end])
                correlations.append(corr if not np.isnan(corr) else 0)

            # 归一化权重（确保非负且和为1）
            weights = np.array(correlations)
            weights = np.maximum(weights, 0)  # 去除负权重
            weights = weights / \
                weights.sum() if weights.sum() > 0 else np.ones_like(weights) / len(weights)

            # 计算当前位置的加权趋势
            current_trend = 0
            for ma, w in zip(ma_list, weights):
                current_trend += ma.iloc[i] * w

            adaptive_trend.iloc[i] = current_trend

        return adaptive_trend

    @classmethod
    def FactorOptimizer(cls, price: pd.Series, factors: pd.DataFrame,
                        max_weight: float = 0.8, l2_reg: float = 0.0001,
                        min_ic_abs: float = 0.03, n_init_points: int = 10,
                        optimization_model: str = "scipy", **kwargs):
        returns = price.pct_change().shift(-1).fillna(0.)  # 预测下一期收益
        optimizer = cls.SingleAssetFactorOptimizer()(
            factors=factors,
            returns=returns,
            price=price.iloc[:-1],
            max_weight=max_weight,
            l2_reg=l2_reg,
            min_ic_abs=min_ic_abs,
            n_init_points=n_init_points,
            optimization_model=optimization_model  # 切换优化方法
        )
        return optimizer.build_merged_factor()
