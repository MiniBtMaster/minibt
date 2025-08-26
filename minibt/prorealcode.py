
class prorealcode_base:
    """https://www.prorealcode.com/documentation/category/indicators/"""
    def AccumDistr(price: pd.Series, high: pd.Series, low: pd.Series, volume: pd.Series, length: int):
        """AccumDistr 是经典的累积/分配指标

        价格的累积/分布是这样计算的：

        >>> myAD = sum[volume*((Close-Low) - (High-Close)) / (High-Low)]
        该指标使用在交易日极端点报告的收盘价来平衡交易量。
        它必须通过与股票趋势相同的方向来确认正在进行的股票趋势。价格和积累/分配之间的背离通常是当前趋势可能逆转的信号。
        这些成交量指标在显示积累或分布阶段时非常有用。"""
        return (volume*(2.*price-high-low)/(high-low)).rolling(length).sum()

    def AdaptiveAverage(ohlc: pd.DataFrame, er: int = 10, ema_fast: int = 2, ema_slow: int = 30, period: int = 20, column: str = "close"):
        return FinTa.KAMA(ohlc, er, ema_fast, ema_slow, period, column)

    def ADX(ohlc: pd.DataFrame, period: int = 14, adjust: bool = True):
        return FinTa.ADX(ohlc, period, adjust)

    def ADXR(ohlc: pd.DataFrame, period: int = 14, pre: int = 3, adjust: bool = True):
        _adx = FinTa.ADX(ohlc, period, adjust)
        return (_adx+_adx.shift(pre))/2.

    def AroonDown(high, low, length=None, scalar=None, talib=None, offset=None, **kwargs):
        return pd.Series(pta.aroon(high, low, length, scalar, talib, offset, **kwargs).values[:, 0], name='aroon_down')

    def AroonUP(high, low, length=None, scalar=None, talib=None, offset=None, **kwargs):
        return pd.Series(pta.aroon(high, low, length, scalar, talib, offset, **kwargs).values[:, 1], name='aroon_up')

    def Average(name: str = None, source: pd.Series = None, **kwargs):
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
        return pta.ma(name, source, **kwargs)

    def AverageTrueRange(high, low, close, talib=None, drift=None, offset=None, **kwargs):
        return pta.true_range(high, low, close, talib, drift, offset, **kwargs)

    def BollingerBandWidth(close, length=None, std=None, ddof=0, mamode=None, talib=None, offset=None, **kwargs):
        return pd.Series(pta.bbands(close, length, std, ddof, mamode, talib, offset, **kwargs).values[:, 3], name="bandwidth")

    def BollingerDown(close, length=None, std=None, ddof=0, mamode=None, talib=None, offset=None, **kwargs):
        return pd.Series(pta.bbands(close, length, std, ddof, mamode, talib, offset, **kwargs).values[:, 0], name="banddown")

    def BollingerUp(close, length=None, std=None, ddof=0, mamode=None, talib=None, offset=None, **kwargs):
        return pd.Series(pta.bbands(close, length, std, ddof, mamode, talib, offset, **kwargs).values[:, 0], name="bandup")

    def CCI(high, low, close, length=None, c=None, talib=None, offset=None, **kwargs):
        return pta.cci(high, low, close, length, c, talib, offset, **kwargs)

    def ChaikinOsc():
        ...

    def ChandeKrollStopDown():
        """First low stop = Lowest[p](low) + x * Average True Range[p]

        Stop long = Lowest[q](first low stop)"""

    def ChandeKrollStopUp():
        """First high stop = Highest[p](high) – x * Average True Range[p]

        Stop short = Highest[q](First high stop)"""

    def Chandle():
        ...

    def DEMA(close, length=None, talib=None, offset=None, **kwargs):
        return pta.dema(close, length, talib, offset, **kwargs)

    def DI():
        """Part of the directional Index technical indicator (ADX) value. Represents DI+ minus DI- over N periods."""
        ...

    def DIminus():
        """Part of the average directional Index technical indicator (ADX). Return value of the DI- line over N periods."""
        ...

    def DIplus():
        """Part of the average directional Index technical indicator (ADX). Return value of the DI+ line over N periods."""

    def DivergenceCCI():
        """CCIperiod = Commodity Channel Index (CCI) indicator period of calculation, default is 20 periods

        LowCCIthreshold = Lowest bound of the CCI indicator, default is -100

        HighCCIthreshold = Highest bound of the CCI indicator, default is 100

        Bars = Bars quantity to detect a potential divergences, default is 20"""
        ...

    def DivergenceMACD():
        """计算：该指标检测价格和 MACD 之间的看涨和看跌背离。当股价创下新低而指标开始向上攀升时，就会发生看涨背离。当股价创下新高而指标开始走低时，就会发生看跌背离。

        解读：背离表明当前趋势放缓，并有可能逆转。如果检测到看涨背离，则此指标返回 +1（绿色直方图）。如果检测到看跌背离，指标将返回 -1（红色直方图）。如果未检测到背离，则指标返回 0。"""
        ...

    def DivergenceRSI():
        """rsi背离"""
        ...

    def DonchianChannel(high, low, period: int = 20):
        higher, lower = TqFunc.hhv(high, period), TqFunc.llv(low, period)
        middle = (higher+lower)/2.
        df = pd.concat([higher, lower, middle], axis=1)
        df.columns = ["higher", "lower", "middle"]
        return df

    def DonchianChannelCenter(high, low, period: int = 20):
        return prorealcode_base.DonchianChannel.middle

    def DonchianChannelDown(high, low, period: int = 20):
        return prorealcode_base.DonchianChannel.lower

    def DonchianChannelUp(high, low, period: int = 20):
        return prorealcode_base.DonchianChannel.higher

    def DPO(close, length=None, centered=True, offset=None, **kwargs):
        return pta.dpo(close, length, centered, offset, **kwargs)

    def DynamicZoneRsiDown():
        """返回动态区域 RSI 指标的下行。

        动态区域 RSI 振荡器类似于经典的 RSI，其上应用了 0.8 个标准差的布林带。"""
        ...

    def DynamicZoneRsiUp():
        ...

    def DynamicZoneStochasticDown():
        ...

    def DynamicZoneStochasticUp():
        ...

    def EaseOfMovement(high, low, close, volume, length=None, divisor=None, drift=None, offset=None, **kwargs):
        return pta.eom(high, low, close, volume, length, divisor, drift, offset, **kwargs)

    def ElderRayBearPower(high, low, close, period=20):
        _ma = pta.ema(close, period)
        bear, bull = low-_ma, high-_ma
        return pd.DataFrame(dict(bear=bear, bull=bull)).bear

    def ElderRayBullPower(high, low, close, period=20):
        _ma = pta.ema(close, period)
        bear, bull = low-_ma, high-_ma
        return pd.DataFrame(dict(bear=bear, bull=bull)).bull

    def EndPointAverage():
        ...

    def ExponentialAverage():
        ...

    def ForceIndex(close, volume):
        return (close-close.shift())*volume

    def FractalDimensionIndex(high, low, close, period):
        return prorealcode.FractalDimensionIndex(high, low, close, period)

    def Highest():
        ...

    def HistoricVolatility():
        ...

    def HullAverage():
        ...

    def KeltnerBandCenter(high, low, close, length, mult=2.):
        middle = pta.ema(close, length)
        _atr = pta.atr(high, low, close, length)
        return pd.DataFrame(dict(middle=middle, upper=middle+mult*_atr, lower=middle-mult*_atr))

    def KeltnerBandDown():
        ...

    def KeltnerBandUp():
        ...

    def KijunSen(high, low, period=26):
        hh, ll = TqFunc.hhv(high, period), TqFunc.llv(low, period)
        return (hh+ll)/2.

    def LinearRegression(close, length=None, offset=None, **kwargs):
        return pta.linreg(close, length, offset, **kwargs)

    def LinearRegressionSlope(close, length=None, as_angle=None, to_degrees=None, vertical=None, offset=None, **kwargs):
        return pta.slope(close, length, as_angle, to_degrees, vertical, offset, **kwargs)

    def Lowest():
        ...

    def MACD():
        ...

    def MACDLine():
        ...

    def MACDsignal():
        ...

    def MassIndex(high, low, fast=None, slow=None, offset=None, **kwargs):
        return pta.massi(high, low, fast, slow, offset, **kwargs)

    def Momentum(close, length=None, talib=None, offset=None, **kwargs):
        return pta.mom(close, length, talib, offset, **kwargs)

    def MoneyFlowIndex(high, low, close, volume, length=None, talib=None, drift=None, offset=None, **kwargs):
        return pta.mfi(high, low, close, volume, length, talib, drift, offset, **kwargs)


class prorealcode:
    """
    ## 官网
    https://www.prorealcode.com
    ## 策略
    https://www.prorealcode.com/prorealtime-trading-strategies/
    ## 指标
    https://www.prorealcode.com/prorealtime-indicators/"""
    def Monster_Cumulative_Delta(open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series):
        # https://www.prorealcode.com/prorealtime-indicators/monster-cumulative-delta/
        diff = high-low
        u1 = volume*diff/(close-open+2*(high+open-low-close))
        d1 = volume*diff/(open-close+2*(high+close-open-low))
        delta = pd.Series(np.where(close >= open, u1, -d1))
        cum_delta = delta+delta.shift()
        cum_delta.iloc[0] = delta.iloc[0]
        _open = cum_delta.shift()
        _open.iloc[0] = delta.iloc[0]
        _high = np.where(close >= open, cum_delta, cum_delta.shift())
        _low = np.where(close <= open, cum_delta, cum_delta.shift())
        _close = cum_delta
        df = pd.concat([_open, _high, _low, _close], axis=1)
        df.columns = ['open', 'high', 'low', 'close']
        return df

    def Laguerre_candles(open, high, low, close, gamma=.0):
        # https://www.prorealcode.com/prorealtime-indicators/laguerre-candles/
        _open = open.values
        _close = close.values
        size = open.size
        open0, open1, open2, open3 = _open[0], _open[0], _open[0], _open[0]
        close0, close1, close2, close3 = _close[0], _close[0], _close[0], _close[0]
        ol = np.zeros(size)
        oc = np.zeros(size)
        for i, _o in enumerate(_open):
            pre_open0 = open0
            open0 = (1-gamma)*_o+gamma*open0
            pre_open1 = open1
            open1 = -gamma*open0+pre_open0+gamma*pre_open1
            pre_open2 = open2
            open2 = -gamma*open1+pre_open1+gamma*pre_open2
            pre_open3 = open3
            open3 = -gamma*open2+pre_open2+gamma*pre_open3
            ol[i] = (open0+2*open1+2*open2+open3)/6.

            pre_close0 = close0
            close0 = (1-gamma)*_o+gamma*close0
            pre_close1 = close1
            close1 = -gamma*close0+pre_close0+gamma*pre_close1
            pre_close2 = close2
            close2 = -gamma*close1+pre_close1+gamma*pre_close2
            pre_close3 = close3
            close3 = -gamma*close2+pre_close2+gamma*pre_close3
            oc[i] = (close0+2*close1+2*close2+close3)/6.
        df = pd.concat([ol, high, low, oc], axis=1)
        df.columns = ['open', 'high', 'low', 'close']
        return df

    def Twin_Range_Filter(close: pd.Series, length1=27, length2=55, mult1=1.6, mult2=2.):
        # https://www.prorealcode.com/prorealtime-indicators/twin-range-filter/
        smrng1 = smoothrng(close, length1, mult1)
        smrng2 = smoothrng(close, length2, mult2)
        smrng = (smrng1 + smrng2) / 2
        filt, dir = rngfilt(close, smrng)
        df = pd.concat([filt, dir], axis=1)
        df.category = 'overlap'
        return df

    def _RSI_Linear_Regression(rsi: pd.Series, deviations):
        barindex = rsi.index.array
        size = rsi.size
        rsi = rsi.values
        Ex = 0.0
        Ey = 0.0
        Ex2 = 0.0
        Exy = 0.0
        for i in range(size):
            closeI = rsi[i]
            Ex = Ex + i
            Ey = Ey + closeI
            Ex2 = Ex2 + (i * i)
            Exy = Exy + (closeI * i)
            ExEx = Ex * Ex

        if Ex2 == ExEx:
            slope = 0.0
        else:
            slope = (size * Exy - Ex * Ey) / (size * Ex2 - ExEx)
        ilinearRegression = (Ey - slope * Ex) / size
        intercept = ilinearRegression + barindex[-1] * slope
        deviation = 0.0
        for j in range(size):
            deviation += np.square((rsi[j]) -
                                   (intercept - slope * (barindex[j])))

        deviation = deviations * np.sqrt(deviation / size)
        startingPointY = ilinearRegression + slope / size
        return startingPointY

    def RSI_Linear_Regression(close: pd.Series, length=21, period=200, deviations=2.):
        # https://www.prorealcode.com/prorealtime-indicators/rsi-and-linear-regression-trading-signals/
        _rsi = pta.rsi(close, length)
        func = partial(BtFunc._RSI_Linear_Regression, deviations=deviations)
        startingPointY = _rsi.rolling(period).apply(func)
        higher = startingPointY+deviations
        lower = startingPointY-deviations
        df = pd.concat([_rsi, startingPointY, higher, lower], axis=1)
        df.columns = ['rsi', 'mid', 'higher', 'lower']
        return df

    def Linear_Regression_Candles(open, high, low, close, length=11):
        # https://www.prorealcode.com/prorealtime-indicators/linear-regression-candles/
        _open = pta.linreg(open, length)
        _high = pta.linreg(high, length)
        _low = pta.linreg(low, length)
        _close = pta.linreg(close, length)
        df = pd.concat([_open, _high, _low, _close], axis=1)
        df.columns = ['open', 'high', 'low', 'close']
        return df

    def Heikin_Ashi_during_trend(open, high, low, close, length1=27, length2=50, length3=270):
        # https://www.prorealcode.com/prorealtime-trading-strategies/heikin-ashi-during-trend/
        ha_ = pta.ha(open, high, low, close)
        ema1 = pta.ema(close, length1)
        ema2 = pta.ema(close, length2)
        ema3 = pta.ema(close, length3)
        _open, _close = ha_[:, "HA_open"], ha_[:, "HA_close"]
        cond1 = np.where((_close > _open) & (
            _close.shift() > _open.shift()), 1, 0)
        cond2 = np.where((_close < _open) & (
            _close.shift() < _open.shift()), 1, 0)
        buysignal = np.where((ema1 > ema2) & (ema2 > ema3) & cond1, 1., 0.)
        sellsignal = np.where((ema1 < ema2) & (ema2 < ema3) & cond2, -1., 0.)
        df = pd.concat([buysignal, sellsignal], axis=1)
        df.columns = ['buysignal', 'sellsignal']
        return df

    def Regularized_Momentum(open, high, low, close, length=14, Lambda=7, MinMaxPeriod=15, LevelUp=90, LevelDown=10):
        # https://www.prorealcode.com/prorealtime-indicators/regularized-momentum/
        ha_ = pta.ha(open, high, low, close)
        midpoint_ = (ha_.HA_high+ha_.HA_low)/2.
        alpha = 2.0/(1.0+length)
        regf1 = (1.0+Lambda*2.0)
        regf2 = (1.0+Lambda)
        fctrema = (regf1*midpoint_.shift()+alpha*(midpoint_ -
                   midpoint_.shift())-Lambda*midpoint_.shift(2))/regf2
        mom = (midpoint_-midpoint_.shift())/fctrema
        mini = TqFunc.hhv(mom, MinMaxPeriod)
        maxi = TqFunc.llv(mom, MinMaxPeriod)
        rrange = maxi-mini
        flu = mini+LevelUp*rrange/100.0
        fld = mini+LevelDown*rrange/100.0
        flm = mini+0.5*rrange
        df = pd.concat([mom, flm, flu, fld], axis=1)
        df.columns = ['mom', 'mid', 'higher', 'lower']
        return df

    def TANGIER(close, length=20, mom_length=12):
        # https://www.prorealcode.com/prorealtime-trading-strategies/tangier-germany30-time-frame-30-minutes/
        _rsi = pta.rsi(close, length)
        _ma = pta.sma(close, length)
        _mom = pta.mom(close, mom_length)
        mom1 = _mom.shift()
        mom2 = _mom.shift(2)
        buysignal = np.where((close > _ma) & pta.cross_value(
            _rsi, 70) & (_mom > mom1) & (mom1 > mom2), 2., 0.)
        buyout = np.where(pta.cross_value(_rsi, 60, False)
                          & (_ma < _ma.shift()), 1., 0.)
        sellsignal = np.where((close < _ma) & pta.cross_value(
            _rsi, 30, False) & (_mom < mom1) & (mom1 < mom2), -2., 0.)
        sellout = np.where(pta.cross_value(_rsi, 40) &
                           (_ma > _ma.shift()), -1., 0.)
        df = pd.concat([buysignal, buyout, sellsignal, sellout], axis=1)
        df.columns = ["buysignal", "buyout", "sellsignal", "sellout"]
        return df

    def Linear_Regression_Slope(open, high, low, close, rl=28, mm=12):
        # https://www.prorealcode.com/prorealtime-trading-strategies/larry-williams-bars-linear-regression-slope/
        MMhaute = pta.sma(high, mm)
        MMbasse = pta.sma(low, mm)
        linear_ = pta.slope((open+high+low+close), rl)
        buysignal = np.where(TqFunc.crossdown(close, MMbasse)
                             & (linear_.shift() > 0.), 2., 0.)
        buyout = np.where(TqFunc.crossup(close, MMhaute) &
                          (linear_.shift() < 0.), 1., 0.)
        sellsignal = np.where(TqFunc.crossup(close, MMhaute)
                              & (linear_.shift() < 0.), -2., 0.)
        sellout = np.where(TqFunc.crossdown(close, MMbasse) &
                           (linear_.shift() > 0.), -1., 0.)
        df = pd.concat([buysignal, buyout, sellsignal, sellout], axis=1)
        df.columns = ["buysignal", "buyout", "sellsignal", "sellout"]
        return df

    def _FractalDimensionIndex(data):
        high, low, close = data[:, 0], data[:, 1], data[:, 2]
        length = 0.
        pdiff = 0.
        size = len(high)
        for h, l, c in list(zip(high, low, close)):
            diff = (c-l)/(h-l)
            length += np.sqrt(np.square(diff-pdiff)+1/np.square(size))
            pdiff = diff
        return 1.+(np.log(length)+np.log(2.))/np.log(2.*size) if length > 0. else 1.

    def FractalDimensionIndex(high, low, close, period):
        # https://www.prorealcode.com/prorealtime-indicators/fractal-dimension-index-fdi/
        hh, ll = TqFunc.hhv(high, period), TqFunc.llv(low, period)
        data = pd.DataFrame(dict(hh=hh, ll=ll, close=close))
        fdi = data.rolling(period, method='table').apply(
            prorealcode._FractalDimensionIndex, raw=True, engine="numba")

    def LowBuyHighSell(high: pd.Series, low: pd.Series, close: pd.Series, low_length=3, high_length=13, mult=1.):
        """https://www.prorealcode.com/prorealtime-trading-strategies/m15-sp500-lowbuyhighsell/
        日期为大周期
        低点参考线lower,高点参考线higher
        多头目标low_close,空头目标high_close,即前一天收盘价
        多头无条件止损0.4area,空头无条件止损area
        最大持仓K线5根"""
        lower = TqFunc.llv(low.shift(), low_length).values
        higher = TqFunc.hhv(high.shift(), high_length).values
        target_close = close.shift().values
        area = (higher-lower).values
        size = close.size
        close = close.values
        high = high.values
        low = low.values
        long_signal = np.zeros(size, dtype=np.float32)
        exitlong_signal = np.zeros(size, dtype=np.float32)
        short_signal = np.zeros(size, dtype=np.float32)
        exitshort_signal = np.zeros(size, dtype=np.float32)
        pos = 0
        hold = 0
        price = 0.
        last_price = 0.
        for i in range(size):
            if not pos:
                if low[i] < lower[i] < close[i]:
                    price = target_close[i]
                    last_price = close[i]
                    _area = abs(area[i])
                    long_signal[i] = 1.
                    pos = 1
                elif close[i] < higher[i] < high[i]:
                    price = target_close[i]
                    last_price = close[i]
                    _area = abs(area[i])
                    short_signal[i] = 1.
                    pos = -1
            else:
                hold += 1
                if pos > 0:
                    if close[i] > price or (close[i] < last_price and (last_price-close[i]) > mult*_area) or hold > 4:
                        exitlong_signal[i] = 1.
                        hold = 0
                else:
                    if close[i] < price or (close[i] > last_price and (close[i]-last_price) > mult*_area) or hold > 4:
                        exitshort_signal[i] = 1.
                        hold = 0
        return pd.DataFrame(dict(
            lower=lower,
            higher=higher,
            long_signal=long_signal,
            short_signal=short_signal,
            exitlong_signal=exitlong_signal,
            exitshort_signal=exitshort_signal,
        ))

    def buy_and_hold_SP500(close: pd.Series, fast_len=2, slow_len=7, name=None):
        """https://www.prorealcode.com/prorealtime-trading-strategies/2-days-buy-hold-sp500/"""
        ma1 = pta.ma(name, close, length=fast_len)
        ma2 = pta.ma(name, close, length=slow_len)
        b1 = ma1.shift() > ma1
        b1 &= ma1.shift(10) > ma1.shift(11)
        b1 &= close > ma2
        e1 = ma1.shift() <= ma1
        s1 = ma1.shift() < ma1
        s1 &= ma1.shift(10) < ma1.shift(11)
        s1 &= close < ma2
        e2 = ma1.shift() >= ma1
        return pd.DataFrame(dict(
            long_signal=b1,
            short_signal=s1,
            exitlong_signal=e1,
            exitshort_signal=e2,
        ))

    def SP_500_mean_reverting_strategy(close: pd.Series, bb_length: int = 30, ma_length: int = 180, name: str = None):
        """https://www.prorealcode.com/prorealtime-trading-strategies/sp-500-reverting-strategy/"""
        bb = pta.bbands(close, bb_length).values
        up, down = bb[:, 2], bb[:, 0]
        cl = close >= up
        cl &= open >= up
        cs = close <= down
        cs &= open < down
        _ma = pta.ma(name, close, length=ma_length)
        el = pta.cross(close, _ma, False)
        es = pta.cross(close, _ma)
        return pd.DataFrame(dict(
            long_signal=cs,
            short_signal=cl,
            exitlong_signal=el,
            exitshort_signal=es,
        ))

    def SP500_riding_the_trend(close: pd.Series, rsi_length=2, length1=4, length2=14, length3=125, length4=200, name: str = None):
        """https://www.prorealcode.com/prorealtime-trading-strategies/sp500-riding-the-trend/"""
        size = close.size
        _rsi = pta.rsi(close, rsi_length)
        ma1 = pta.ma(name, close, length=length1).values
        ma2 = pta.ma(name, close, length=length2).values
        ma3 = pta.ma(name, close, length=length3).values
        ls = ((close > ma3) & (ma3 > ma3.shift()) &
              (close < ma2) & (_rsi < 10.)).values
        ss = ((close < ma3) & (ma3 < ma3.shift()) &
              (close < ma2) & (_rsi > 10.)).values
        long_signal = np.zeros(size, dtype=np.float32)
        exitlong_signal = np.zeros(size, dtype=np.float32)
        short_signal = np.zeros(size, dtype=np.float32)
        exitshort_signal = np.zeros(size, dtype=np.float32)
        close = close.values
        pos = 0
        for i in range(size):
            if i:
                if not pos:
                    if ls[i]:
                        long_signal[i] = 1.
                        pos = 1
                    elif ss[i]:
                        long_signal[i] = 1.
                        pos = -1
                elif pos > 1:
                    if close[i] > ma1[i] and close[i] > close[i-1]:
                        exitlong_signal[i] = 1.
                        pos = 0
                else:
                    if close[i] < ma1[i] and close[i] < close[i-1]:
                        exitlong_signal[i] = 1.
                        pos = 0
        return pd.DataFrame(dict(
            long_signal=long_signal,
            short_signal=short_signal,
            exitlong_signal=exitlong_signal,
            exitshort_signal=exitshort_signal,
        ))

    def _pb(name: str, source: pd.Series, length=10, mult=1.5):
        _ma = pta.ma(name, source, length=length)
        std = pta.stdev(source, length)
        lower = _ma-mult*std
        higher = _ma+mult*std
        return (source-lower)/(higher-lower)

    def The_Bollinger_in_Trend_strategy(name: str, close: pd.Series, length1=5, length2=20, length3=100, length4=200, mult=1.5):
        """https://www.prorealcode.com/prorealtime-trading-strategies/bollinger-trend-strategy/"""
        pb = prorealcode._pb(name, close, length1)
        ma1 = pta.ma(name, close, length2)
        ma2 = pta.ma(name, close, length3)
        ma3 = pta.ma(name, close, length4)
        ls = close > ma2
        ls &= ma1 > ma3
        ls &= (pb.shift() < 0.2) & (pb < 0.2)
        ss = close < ma2
        ss &= ma1 < ma3
        ss &= (pb.shift() > 0.8) & (pb > 0.8)
        els = pta.cross(pb, 1.)
        ess = pta.cross(pb, 0.)
        return pd.DataFrame(dict(
            pb=pb,
            long_signal=ls,
            short_signal=ss,
            exitlong_signal=els,
            exitshort_signal=ess,
        ))

    def BetterKumo(high: pd.Series, low: pd.Series, close: pd.Series, length=14, mult=1., p1=9, p2=26, p3=52, if_df=False):
        # REM Tenkan-Sen
        Upper1 = TqFunc.hhv(high, p1)  # HIGHEST[p1](HIGH)
        Lower1 = TqFunc.llv(low, p1)  # LOWEST[p1](LOW)
        Tenkan = (Upper1 + Lower1) / 2.
        # REM Kijun-Sen
        Upper2 = TqFunc.hhv(high, p2)  # HIGHEST[p2](HIGH)
        Lower2 = TqFunc.llv(low, p2)  # LOWEST[p2](LOW)
        Kijun = (Upper2 + Lower2) / 2.
        # REM Senkou Span A
        SpanA = (Tenkan.shift(p2) + Kijun.shift(p2)) / 2.
        # REM Senkou Span B
        SpanB = (TqFunc.hhv(high.shift(p2), p3)+TqFunc.llv(low.shift(p2), p3)) / \
            2.  # ((HIGHEST[p3](HIGH[p2])) + LOWEST[p3](LOW[p2])) / 2
        size = high.size
        close = close.values
        SpanA = SpanA.values
        SpanB = SpanB.values
        vv, rr, c = 0, 0, 1
        pre_vv, pre_rr, pre_c = 0, 0, 1
        bk = np.zeros(size)
        for i in range(size):
            if i:
                vv = 1 if close[i] >= SpanA[i] and close[i] >= SpanB[i] else 0
                rr = 1 if close[i] <= SpanA[i] and close[i] <= SpanB[i] else 0
                if pre_vv == 1 and vv == 0 and rr == 0:
                    vv = 1
                if pre_rr == 1 and rr == 0 and vv == 0:
                    rr = 1
                c = 1 if vv == 1 else -1
                cambioarojo = pre_c == 1 and c == -1
                cambioaverde = pre_c == -1 and c == 1
                KumoRosa = SpanA[i] < SpanB[i]
                KumoAzul = SpanA[i] > SpanB[i]
                if cambioarojo:
                    if KumoRosa:
                        bk[i] = SpanA[i]
                    elif KumoAzul:
                        bk[i] = SpanB[i]
                elif cambioaverde:
                    if KumoRosa:
                        bk[i] = SpanB[i]
                    elif KumoAzul:
                        bk[i] = SpanA[i]
                else:
                    bk[i] = bk[i-1]
            pre_vv, pre_rr, pre_c = vv, rr, c
        bk = pd.Series(bk, name="BetterKumo")
        myart = pta.true_range(high, low, close).rolling(length).mean()
        lower = bk-mult*myart
        higher = bk+mult*myart
        if if_df:
            return pd.DataFrame(dict(
                bk=bk,
                lower=lower,
                higher=higher,
            ))
        else:
            return bk, lower, higher

    def SP500_automated_trading_strategy(high: pd.Series, low: pd.Series, close: pd.Series, length=14, mult=1., p1=9, p2=26, p3=52,
                                         macd_fast=21, macd_slow=44, macd_signal=24, stock_k=28, stock_d=8, stock_length=22, ema_length=43):
        """https://www.prorealcode.com/prorealtime-trading-strategies/sp500-automated-trading-strategy-eeuu-500-mini-1e-1hora/"""
        bk, lower, higher = prorealcode.BetterKumo(
            high, low, close, length, mult, p1, p2, p3)
        macdline = pta.macd(close, macd_fast, macd_slow, macd_signal).values
        stockline = pta.stoch(high, low, close, stock_k, stock_d)
        ema_stockline = pta.ema(stockline, stock_length)
        ema_ = pta.ema(close, ema_length)
        ls = macdline[:, 0] > macdline[:, 2]
        ls &= stockline >= ema_stockline
        ls &= close >= ema_
        ls &= close <= lower
        els = pta.cross(close, higher)
        ss = macdline[:, 0] < macdline[:, 2]
        ss &= stockline <= ema_stockline
        ss &= close <= ema_
        ss &= close >= higher
        ess = pta.cross(close, lower, False)
        return pd.DataFrame(dict(
            bk=bk,
            lower=lower,
            higher=higher,
            long_signal=ls,
            short_signal=ss,
            exitlong_signal=els,
            exitshort_signal=ess,
        ))

    def Universal_XBody_Strategy_on_CAC(open: pd.Series, close: pd.Series, period=978, filter1=51, filter2=0):
        """https://www.prorealcode.com/prorealtime-trading-strategies/universal-xbody-strategy-on-cac-1day/"""
        body = close-open
        Var = body-body.shift()
        sumvar = Var.rolling(period).sum()
        return sumvar

    def SCALPING_CAC40_10_SECONDS(high: pd.Series, low: pd.Series, close: pd.Series, length1=3, length2=6, length3=10, mult=3.):
        """https://www.prorealcode.com/prorealtime-trading-strategies/scalping-cac40-10-seconds/"""
        st1 = pta.supertrend(high, low, close, length1, mult)
        st2 = pta.supertrend(high, low, close, length2, mult)
        st3 = pta.supertrend(high, low, close, length3, mult)
        ...

    def BOX_7_clock_with_CAC40_intraday_trategy():
        """https://www.prorealcode.com/prorealtime-trading-strategies/box-7-oclock-cac40-intraday/"""
        ...

    def Smoothed_Bollinger_Strategy_Daily(open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, length=220, teav=8, period=17, enterlong=30, entershort=90):
        """https://www.prorealcode.com/prorealtime-trading-strategies/smoothed-bollinger-strategy-daily/"""
        longavg = pta.sma(close, length)
        ohlc4_ = pta.ohlc4(open, high, low, close)
        haopen = ohlc4_.shift()+2.*ohlc4_.shift(2)
        hac = (ohlc4_+haopen+TqFunc.max(high, haopen) +
               TqFunc.min(low, haopen))/4.
        tma1 = pta.tema(hac, teav)
        tma2 = pta.tema(tma1, teav)
        # diff=tma1-tma2
        zlha = 2.*tma1-tma2
        tema_zlha = pta.tema(zlha, teav)
        percb = (tema_zlha+2.*pta.stdev(tema_zlha, teav) -
                 pta.wma(tema_zlha, period))/(4.*pta.stdev(tema_zlha, period))*100.
        long_signal = (close > longavg) & (percb < enterlong)
        short_signal = (close < longavg) & (percb > entershort)
        return pd.DataFrame(dict(percb=percb, long_signal=long_signal, short_signal=short_signal))

    def Maximus(self):
        """https://www.prorealcode.com/prorealtime-trading-strategies/maximus-orders-accumulation-nasdaq100/"""
        ...

    def Strategy_XXDJI_M5_EngulfingGap():
        """https://www.prorealcode.com/prorealtime-trading-strategies/strategy-xxdji-m5-engulfinggap/"""
        ...

    def Universal_Strategy():
        """https://www.prorealcode.com/prorealtime-trading-strategies/universal-strategy/"""
        ...

    def Buy_if_the_price_has_fallen(close: pd.Series, length1=50, length2=100):
        """https://www.prorealcode.com/prorealtime-trading-strategies/buy-if-the-price-has-fallen/"""
        c1 = close > pta.ema(close, length1)  # Exponentialaverage [50] (close)
        # Exponentialaverage [100] (close)
        c2 = close < pta.ema(close, length2)
        c3 = close > close.shift()
        c4 = pta.slope(
            close, length2) < 0.  # LinearRegressionSlope[100] (close) < 0
        long_signal = c1 & c2 & c3 & c4
        c5 = close < pta.ema(close, 7)  # Exponentialaverage [7] (close)
        c6 = close > pta.ema(close, 28)  # Exponentialaverage [28] (close)
        exitlong_signal = c5 & c6
        s1 = close < pta.ema(close, length1)  # Exponentialaverage [50] (close)
        # Exponentialaverage [100] (close)
        s2 = close > pta.ema(close, length2)
        s3 = close < close.shift()
        s4 = pta.slope(
            close, length2) > 0.  # LinearRegressionSlope[100] (close) < 0
        long_signal = reduce(lambda x, y: x & y, [s1, s2, s3, s4])
        s5 = close > pta.ema(close, 7)  # Exponentialaverage [7] (close)
        s6 = close < pta.ema(close, 28)  # Exponentialaverage [28] (close)
        exitshort_signal = s5 & s6

    def Heiken_Ashi_Trading_System_with_RSI_Dax_Nasdaq_ITA40(open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, length=14, buyrsi=20, sellrsi=80):
        """https://www.prorealcode.com/prorealtime-trading-strategies/heiken-ashi-trading-system-with-rsi-dax-mini-nasdaq-mini-ita40-mini/"""
        ha_ = pta.ha(open, high, low, close)
        xopen, xhigh, xlow, xclose = [pd.Series(value) for value in ha_.values]
        rsi_ = pta.rsi(close, length)
        xrange = xhigh-xlow
        xbody = (xclose-xopen).abs()
        # c1=xrange<xrange.shift()
        c2 = xclose > xopen
        c3 = xclose.shift() < xopen.shift()
        c4 = (rsi_.shift() < buyrsi) | (rsi_.shift(2) < buyrsi)
        long_signal = c2 & c3 & c4
        # s1=xrange<xrange.shift()
        s2 = xclose < xopen
        s3 = xclose.shift() > xopen.shift()
        s4 = (rsi_.shift() > sellrsi) | (rsi_.shift(2) > sellrsi)
        short_signal = s2 & s3 & s4

    def HLHB_Trend_Catcher_DAX_mtf(open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, fast=5, slow=10, rsi_length=8):
        """https://www.prorealcode.com/prorealtime-trading-strategies/hlhb-trend-catcher-dax-mtf/"""
        Bullish = open < close
        Bearish = open > close
        Body = (close - open).abs()
        HiWick = high - TqFunc.max(close, open)
        LoWick = TqFunc.min(close, open) - low
        TotalWicks = HiWick + LoWick
        LongCandle = Body > TotalWicks
        LongBullish = LongCandle & Bullish
        LongBearish = LongCandle & Bearish
        BigBullish = (Body > (range * 0.67)) & LongBullish
        BigBearish = (Body > (range * 0.67)) & LongBearish
        HugeBullish = (Body > (range * 0.85)) & BigBullish
        HugeBearish = (Body > (range * 0.85)) & BigBearish

        FastEma = pta.ema(close, fast)  # average[FastMA,AvgType](close)
        SlowEma = pta.ema(close, slow)  # average[SlowMA,AvgType](close)
        # ONCE RsiMid = 50
        MyRsi = pta.rsi(pta.midprice(high, low),
                        rsi_length)  # Rsi[8](MedianPrice)

        long_signal = HugeBullish | BigBullish | LongBullish
        long_signal &= pta.cross(FastEma, SlowEma)
        long_signal &= pta.cross(MyRsi, 50.)

    def Optimized_Trend_Tracker_OTT(close: pd.Series, length=2, period=9):
        """https://www.prorealcode.com/prorealtime-indicators/optimized-trend-tracker-ott/"""
        valpha = 2./(length+1.)
        size = close.size
        pre_close = close.shift().values
        var = close.values
        close = close.values
        vud = np.zeros(size)
        vdd = np.zeros(size)
        for i, psrc, src in enumerate(zip(pre_close, close)):
            if src > psrc:
                vud[i] = src-psrc
            elif src < psrc:
                vdd[i] = psrc-src
            if i > period:
                vud1 = vud[i-period:i+1].sum()
                vdd1 = vdd[i-period:i+1].sum()
                vcmo = abs((vud1-vdd1)/(vud1+vdd1))
                var[i] = valpha*vcmo*src+(1-valpha*vcmo)*var[i-1]

    def Twin_Range_Filter(close, length1=27, length2=55, mult1=1.6, mult2=2., **kwargs):
        """https://www.prorealcode.com/prorealtime-indicators/twin-range-filter/"""
        smrng1 = smoothrng(close, length1, mult1)
        smrng2 = smoothrng(close, length2, mult2)
        smrng = (smrng1+smrng2)/2.
        filt, dir = rngfilt(close, smrng)
        hband = filt + smrng
        lband = filt - smrng
        df = pd.concat([filt, hband, lband, dir], axis=1)
        df.category = 'overlap'
        return df

    def BykovTrend_NRTR(high: pd.Series, low: pd.Series, close: pd.Series, rsik=3, ssp=9, atr_ratio=0.375, atr_period=15):
        """https://www.prorealcode.com/prorealtime-indicators/bykovtrend_nrtr/"""
        k = 33-rsik
        wldn = -100+k
        wpr = pta.willr(high, low, close, ssp)
        atr_ = pta.atr(high, low, close, atr_period).values
        size = close.size
        trend = np.zeros(size)
        low = low.values
        high = high.values
        UpBuffer = np.zeros(size)
        DnBuffer = np.zeros(size)
        for i in range(size):
            if wpr[i] < wldn:
                trend[i] = -1.
            elif wpr > -k:
                trend[i] = 1.
            irange = atr_ratio*atr_[i]
            if trend[i-1] < 0. and trend[i] > 0:
                BuyBuffer = low[i]-irange
            else:
                BuyBuffer = 0.
            if trend[i-1] > 0 and trend[i] < 0:
                SellBuffer = high[i]+irange
            else:
                SellBuffer = 0.

            if trend[i] > 0. and BuyBuffer:
                UpBuffer[i] = BuyBuffer
                DnBuffer[i] = DnBuffer[i-1]
            else:
                UpBuffer[i] = max(low[i]-irange, UpBuffer[i-1])

            if trend[i] < 0. and SellBuffer:
                DnBuffer[i] = SellBuffer
                UpBuffer[i] = UpBuffer[i-1]
            else:
                UpBuffer[i] = min(high[i]+irange, UpBuffer[i-1])
        df = pd.DataFrame(
            dict(upbuffer=UpBuffer, dnbuffer=DnBuffer, trend=trend))
        df.category = 'overlap'
        return df

    def SuperBandPass_Filter_strategy_DAX_H4(close: pd.Series, length=50, fast=35, slow=65, pyd=55):
        """https://www.prorealcode.com/prorealtime-trading-strategies/superbandpass-filter-strategy/"""
        a1, a2 = 5./fast, 5./slow
        a3 = a1-a2
        a4 = a2*(1 - a1) - a1 * (1 - a2)
        a5 = 2-a1-a2
        a6 = (1 - a1) * (1 - a2)
        size = close.size
        close_ = close.values
        pb = np.zeros(size)
        RMSa = np.zeros(size)
        RMSplus = np.zeros(size)
        RMSminus = np.zeros(size)
        for i in range(size):
            if i > 1:
                pb[i] = a3*close_[i]-a4*close_[i-1]+a5*pb[i-1]-a6*pb[i-2]

            if i > length:
                pb_ = pb[:i+1]
                RMSa[i] = (pb_*pb_).sum()
                RMSplus[i] = np.sqrt(RMSa[i]/length)
                RMSminus[i] = -RMSplus[i]
        return pd.DataFrame(dict(pb=pb, rmsplus=RMSplus, rmsminus=RMSminus))

    def TORM_Short_On_Rising_Markets(close: pd.Series, period=50, length=100):
        """https://www.prorealcode.com/prorealtime-trading-strategies/storm-short-on-rising-markets/"""
        ls = [8., -28., 56., -70., 56., -28., 8.-1.]
        ma_ = [pta.ema(close, period),]
        for _ in range(7):
            ma_.append(pta.ema(ma_[-1], period))
        pema = 0.
        for mult, value in zip(ls, ma_):
            pema += mult*value
        hma_ = pta.wma(2.*pta.wma(close, int(length/2.)) -
                       pta.wma(close, length), int(length/2.))
        long_signal = close > pema
        long_signal &= pema > hma_
        long_signal &= close < close.shift()
        long_signal &= close.shift() < close.shift(2)
        # c5 = averagetruerange [5] > 40 // filter, someone could be find betterone

    def AlphaTrend(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length=14, mult=1.):
        """https://www.prorealcode.com/prorealtime-indicators/alphatrend/"""
        mfi_ = pta.mfi(high, low, close, volume, length).values
        atr_ = mult*pta.atr(high, low, close, length).values
        size = close.size
        high = high.values
        low = low.values
        magic = np.zeros(size)
        for i in range(size):
            if i:
                if mfi_[i] >= 50.:
                    magic[i] = max(low[i]-atr_[i], magic[i-1])
                else:
                    magic[i] = min(high[i]+atr_[i], magic[i-1])
        magic = pd.Series(magic, name='magic')
        magic.category = 'overlap'
        return magic

    def UT_Bot_Alerts_indicator(open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, length=10, mult=1.):
        """https://www.prorealcode.com/prorealtime-indicators/ut-bot-alerts-indicator/"""
        xatr = mult*pta.true_range(high, low,
                                   close).rolling(length).mean().values
        src = pta.ohlc4(open, high, low, close).values
        size = close.size
        Alerts = src[:length]
        Alerts = np.append(Alerts, np.zeros(size-length))
        for i in range(size):
            if i > length:
                if src[i] > Alerts[i-1] and src[i-1] > Alerts[i-1]:
                    Alerts[i] = max(Alerts[i-1], src[i]-xatr[i])
                elif src[i] < Alerts[i-1] and src[i-1] < Alerts[i-1]:
                    Alerts[i] = min(Alerts[i-1], src[i]+xatr[i])
                else:
                    if src[i] > Alerts[i-1]:
                        Alerts[i] = src[i]-xatr[i]
                    else:
                        Alerts[i] = src[i]+xatr[i]

    def RMI_Trend_Sniper_Indicator(close: pd.Series, length=14, pmop=66, nmom=30):
        """https://www.prorealcode.com/prorealtime-indicators/rmi-trend-sniper-indicator/"""
        alpha = 1./length
        beta = 1-alpha
        src1 = (close-close.shift()).apply(lambda x: max(x, 0.))
        src2 = -(close-close.shift()).apply(lambda x: max(x, 0.))
        ma1 = pta.sma(src1, length).values
        ma2 = pta.sma(src2, length).values
        src1, src2 = src1.values, src2.values

        size = close.size
        up = np.zeros(size)
        dn = np.zeros(size)
        myrsi = np.zeros(size)
        for i in range(size):
            if i > length:

                up[i] = alpha*src1[i]+beta*up[i-1]
                dn[i] = alpha*src2[i]+beta*dn[i-1]
            else:
                up[i] = ma1[i]
                dn[i] = ma2[i]
            if dn == 0:
                myrsi[i] = 100.
            elif up == 0:
                ...
            else:
                myrsi[i] = 100.-100./(1+up[i]/dn[i])
        myrsi = pd.Series(myrsi)
        ma3 = pta.ema(close, 5)
        long_signal = pta.cross(myrsi, pmop)
        long_signal &= ma3 > ma3.shift()
        exitlong_signal = myrsi < nmom
        exitlong_signal &= ma3 < ma3.shift()

    def _RSI_and_Linear_Regression_trading_signals(irsi: np.ndarray) -> tuple[float]:
        size = len(irsi)
        Ex = 0.0
        Ey = 0.0
        Ex2 = 0.0
        Exy = 0.0
        deviation = 0.0
        for i in range(size):
            Ex += i
            Ey += irsi[i]
            Ex2 += i*i
            Exy += irsi[i]*i
            ExEx = Ex*Ex
        if Ex2 == ExEx:
            slope_ = 0.
        else:
            slope_ = (size*Exy-Ex*Ey)/(size*Ex2-ExEx)
        ilinearRegression = (Ey - slope_ * Ex) / size
        intercept = ilinearRegression + size * slope_
        for i in range(size):
            deviation += np.square(irsi[i]-intercept+slope_*i)
        deviation *= np.sqrt(deviation/size)
        return ilinearRegression + slope_ / size, deviation

    def A_based_on_2RSI_weekly_strategy_working_on_indexes(close: pd.Series, length=50, rsi_length=2):
        """https://www.prorealcode.com/prorealtime-trading-strategies/based-on-2rsi-weekly-strategy/"""
        xma = pta.sma(close, length)
        xrsi = pta.rsi(close, rsi_length)
        long_signal = close > xma
        long_signal &= xrsi < 10.
        exitlong_signal = xrsi > 70.
        short_signal = close < xma
        short_signal &= xrsi > 90.
        exitshort_signal = xrsi < 30.

    def RSI_and_Linear_Regression_trading_signals(close: pd.Series, period=200, mult=2.):
        """https://www.prorealcode.com/prorealtime-indicators/rsi-and-linear-regression-trading-signals/"""
        irsi = pta.rsi(close, period)
        size = close.size

    def Follow_Line_Indicator():
        """https://www.prorealcode.com/prorealtime-indicators/follow-line-indicator/"""
        ...

    def Flat_Trend():
        """https://www.prorealcode.com/prorealtime-indicators/flat-trend/"""
        ...

    def Quadrant_DAX_intraday_Strategy():
        """https://www.prorealcode.com/prorealtime-trading-strategies/quadrant-strategy/"""
        ...

    def DAX_15Min_False_Breakout_SuperTrend():
        """https://www.prorealcode.com/prorealtime-trading-strategies/dax-15min-false-breakout-supertrend/"""
        ...

    def BLUSTER_DAX_intraday_trading_strategy():
        """https://www.prorealcode.com/prorealtime-trading-strategies/bluster-dax-strategy/"""
        ...

    def Breakout_intraday_trading_strategy_on_DAX():
        """https://www.prorealcode.com/prorealtime-trading-strategies/breakout-dax-15-min-trailing-stop/"""
        ...

    def Optimization_moving_average_crossing_strategy_with_machine_learning():
        """https://www.prorealcode.com/prorealtime-trading-strategies/optimization-ma-cross-machine-learning/"""
        ...

    def Repulse_and_DPO_4H_OnlyLong_Strategy_on_Dax(open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, p=3, c=0.1, q=3):
        """https://www.prorealcode.com/prorealtime-trading-strategies/repulse-dpo-4hours-dax-strategy/"""
        avg = pta.sma(close, p)
        r = int(p/2)+1
        c1 = close-avg.shift(r)
        c2 = c
        a = 100.*(3.*close-2.*low-open)/close
        b = 100.*(open+2.*high-3.*close)/close
        c3 = pta.ema(a, q)-pta.ema(b, q)
        c4 = c
        long_signal = c1 > c2
        long_signal &= c3 > c4
        short_signal = c1 < c2
        short_signal &= c3 < c4

    # def RSI, Stochastic and SMA showing direction. Stochastic not yet oversold/overbought():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/rsi-stochastic-and-sma-showing-direction-stochastic-not-yet-oversold-overbought/"""

    # def RocketRSI by John Ehlers():
    # """https://www.prorealcode.com/prorealtime-indicators/rocketrsi-john-ehlers/"""

    # def The “DAX Donchian Breakout” strategy():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/dax-donchian-breakout-strategy/"""

    # def S & P 500 daily RSI(2) long short strategy():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/sp-500-daily-rsi2-long-short-strategy/"""

    # def ROCK CLIMBER():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/rock-climber/"""

    # def The “RSI 2P” from Larry Connors():
    # """https://www.prorealcode.com/prorealtime-trading-strategies/rsi-2p-larry-connors/"""

    def Cumulative_RSI_2_periods_strategy(close: pd.Series, length=200, rsi_length=2):
        """https://www.prorealcode.com/prorealtime-trading-strategies/cumulative-rsi-2-periods-strategy/"""
        xrsi = pta.rsi(close, rsi_length)
        yrsi = xrsi+xrsi.shift()
        xma = pta.sma(close, length)
        long_signal = close > xma
        long_signal &= yrsi < 35.
        exitlong_signal = yrsi > 65

    # def Bitcoin Tripple MA Miner 1Min():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/bitcoin-tripple-ma-miner-1min/"""

    def USDJPY_3candles_and_reversal_strategy_with_ADX_and_VOL_filter(open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, length=14, fast=5, slow=100, atrmin=10):
        """https://www.prorealcode.com/prorealtime-trading-strategies/usdjpy-3candles-reversal-strategy-adx-vol-filter/"""
        xatr = pta.atr(high, low, close, length)
        ma1 = pta.sma(close, fast)
        ma2 = pta.sma(close, slow)
        c1 = (close < open).apply(
            lambda x: 1 if x else 0).rolling(3).sum() == 3
        c2 = (close > open).apply(
            lambda x: 1 if x else 0).rolling(3).sum() == 3
        xadx = pta.adx(high, low, close, length)
        xadx = xadx[:, xadx.columns[0]]
        ctrend = xadx > 25.
        volok = xatr > atrmin
        long_signal = c1 & ctrend & volok & (ma1 > ma2)

    # def Larry Williams’ X bars & Linear Regression Slope():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/larry-williams-bars-linear-regression-slope/"""

    # def Navigator_DAX_Trading_Strategy_4H():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/navigator-dax-trading-strategy-4h/"""
    #     ...

    # def Quadrant DAX intraday Strategy():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/quadrant-strategy/"""

    def Beating_the_SP_500_Long_Term(close: pd.Series, length=8.):
        """https://www.prorealcode.com/prorealtime-trading-strategies/beating-sp-500-long-term/"""
        f = 1.414*np.pi/length
        a = np.exp(-f)
        c2 = 2.*a*np.cos(f)
        c3 = -a*a
        c1 = 1-c2-c3
        size = close.size
        close = close.values
        blt = np.zeros(size)
        blt[:2] = close[:2]
        for i in range(size):
            if i > 1:
                blt[i] = 0.5*c1*(close[i]+close[i-1])+c2*blt[i-1]+c3*blt[i-2]
        blt = pd.Series(blt)
        long_signal = close > blt
        long_signal &= blt > blt.shift()

    # def intraday DAX strategy mini-1€, timeframe 5 min():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/intraday-dax-strategy-mini-1e-timeframe-5-min/"""

    # def DAX 15Min – False Breakout / SuperTrend():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/dax-15min-false-breakout-supertrend/"""

    # def QU Trading Strategy DAX Indices CFD():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/qu-trading-strategy-dax-indices-cfd/"""

    # def QU Trading Strategy FTSE100 Indices CFD():
    #     """QU Trading Strategy FTSE100 Indices CFD"""

    # def BLUSTER DAX intraday trading strategy():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/bluster-dax-strategy/"""

    # def Breakout intraday trading strategy on DAX():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/breakout-dax-15-min-trailing-stop/"""

    # def The “Enveloppe ADX” Forex Strategy():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/enveloppe-adx-forex-strategy/"""

    # def Lift up and down DAX 5M():
    #     """https://www.prorealcode.com/prorealtime-trading-strategies/lift-up-down-trading-strategy-dax-5m/"""

    def Trend_Surfer_DAX(close: pd.Series, length=14, fast=4, slow=29):
        """https://www.prorealcode.com/prorealtime-trading-strategies/trend-surfer-dax/"""
        xrsi = pta.rsi(close, length)
        line = pta.sma(xrsi, fast)
        mid = pta.sma(xrsi, slow)
        ...

    def _Long_only_strategy_with_the_TMA_channel(x: pd.Series):
        size = x.size
        x = x.values
        y = np.arange(size, 0)
        return (x*y).sum()/y.sum()

    def Long_only_strategy_with_the_TMA_channel(high: pd.Series, low: pd.Series, close: pd.Series, length=141, mult=2.4):
        """https://www.prorealcode.com/prorealtime-trading-strategies/long-only-strategy-with-the-tma-channel/"""
        mid = close.rolling(length).apply(
            prorealcode._Long_only_strategy_with_the_TMA_channel)
        xatr = mult*pta.atr(high, low, close, length)
        lower = mid-xatr
        higher = mid+xatr
        long_signal = pta.cross(close, lower)
        short_signal = pta.cross(close, higher)

    def DAX_Trend_following(open: pd.Series, close: pd.Series, n=2):
        """https://www.prorealcode.com/prorealtime-trading-strategies/dax-trend-following-2-hours-timeframe/"""
        size = open.size
        open = open.shift(n).values
        close = close.values
        fllow = np.zeros(size)
        start = n-1
        for i in range(size):
            if i > start:
                np.sin(np.arctan((close[i]-open[i])/open[i]*100./n))
        return pd.Series(fllow)

    def Zex_Indicator(close: pd.Series, fast=6, slow=12, angle=5):
        """https://www.prorealcode.com/prorealtime-indicators/zex-indicator/"""
        a = pta.smi(close, fast, slow, angle)
        b = pta.trima(a, angle)
        return a, b

    def ADX_momentum_ema_8_strategy(close: pd.Series, ma_len1=8, ma_len2=15, ma_len3=34, ma_len4=150, ma_len5=200, mom_len=6, adx_len=10, will_len=40, stoch_len=8, rsi_len=3):
        """https://www.prorealcode.com/prorealtime-trading-strategies/adx-momentum-ema-8-strategy/"""
        ...

    def Dax_Short_only_intraday_trading_strategy_timeframe_15_minutes():
        """https://www.prorealcode.com/prorealtime-trading-strategies/dax-short-intraday-trading-strategy-timeframe-15-minutes/"""
        ...

    def Pure_Renko_strategy():
        """https://www.prorealcode.com/prorealtime-trading-strategies/pure-renko-strategy/"""
        ...

    def IDNR2_pattern_strategy_on_DAX_1h(high: pd.Series, low: pd.Series, close: pd.Series, length=10, bb_length=20):
        """https://www.prorealcode.com/prorealtime-trading-strategies/idnr2-pattern-strategy-dax-1/"""
        diff = high-low
        adx_ = pta.adx(high, low, close, length)
        adx_ = pta.adx[:, adx_.columns[0]]
        boll = pta.bbands(close, bb_length)
        bool = bool[:, boll.columns[3]]
        tr = pta.true_range(high, low, close)

        # high < high[1]  and low  > low[1]and range  < LOWEST[2](range)[1]
        NR10 = high < high.shift() and low > low.shift(
        ) and diff < TqFunc.llv(diff, 2).shift()
        # BollingerBandWidth[20](close) < lowest[17](BollingerBandWidth[20](close)[1])
        bbwdt = boll < TqFunc.llv(boll, bb_length-3).shift()
        long_signal = NR10 & bbwdt & (adx_ > 17.) & (tr > pta.sma(tr, 9))

    def CSR_strategy_DAX_1D(close: pd.Series, rsi_length=2, length1=100, length2=110):
        """https://www.prorealcode.com/prorealtime-trading-strategies/csr-strategy-dax-1/"""
        rsi_ = pta.rsi(close, rsi_length)
        cumrsi = rsi_+rsi_.shift()
        avg = pta.sma(close, length1)
        avgs = pta.sma(close, length2)
        long_signal = close > avg
        long_signal &= cumrsi < 35.
        exitlong_signal = cumrsi > 65.
        short_signal = close < avgs
        short_signal &= cumrsi > 175.
        exitshort_signal = cumrsi < 120.

    def Dax_adaptable_trategy_Breakout_Mean_reversion():
        """https://www.prorealcode.com/prorealtime-trading-strategies/dax-adaptable-strategy-breakoutmean-reversion/"""
        ...

    def GBPUSD_REVERSION_BARS():
        """https://www.prorealcode.com/prorealtime-trading-strategies/gbpusd-reversion-bars/"""
        ...

    def Quadrant_DAX_intraday_Strategy():
        """https://www.prorealcode.com/prorealtime-trading-strategies/quadrant-strategy/"""
        ...

    def QU_Trading_Strategy_DAX_Indices_CFD():
        """https://www.prorealcode.com/prorealtime-trading-strategies/qu-trading-strategy-dax-indices-cfd/"""
        ...

    def DAX_15Min_False_Breakout_SuperTrend():
        """https://www.prorealcode.com/prorealtime-trading-strategies/dax-15min-false-breakout-supertrend/"""
        ...

    def BLUSTER_DAX_intraday_trading_strategy():
        """https://www.prorealcode.com/prorealtime-trading-strategies/bluster-dax-strategy/"""
        ...

    def Breakout_intraday_trading_strategy_on_DAX():
        """https://www.prorealcode.com/prorealtime-trading-strategies/breakout-dax-15-min-trailing-stop/"""
        ...

    def Breakout_DAX_15Min():
        """https://www.prorealcode.com/prorealtime-trading-strategies/breakout-dax-15min/"""
        ...

    def The_Enveloppe_ADX_Forex_Strategy():
        """https://www.prorealcode.com/prorealtime-trading-strategies/enveloppe-adx-forex-strategy/"""
        ...

    def Bollinger_reversal_strategy(close: pd.Series, length1=100, length2=200, rsi_length=10, mult=0.975):
        """https://www.prorealcode.com/prorealtime-trading-strategies/bollinger-reversal-strategy/"""
        ma1 = pta.sma(close, length1)
        ma2 = pta.sma(close, length2)
        rsi1 = pta.rsi(close, rsi_length)
        std1 = pta.stdev(close, rsi_length)
        bbdo1 = mult*(ma1-std1)
        bbdo2 = (2.-mult)*(ma1+std1)
        long_signal = ma2 < ma2.shift()
        long_signal &= close < bbdo1
        long_signal &= rsi1 < 20.
        long_signal = ma2 > ma2.shift()
        long_signal &= close > bbdo2
        long_signal &= rsi1 > 80.

    def The_Nice_Price_Forex_Strategy():
        """https://www.prorealcode.com/prorealtime-trading-strategies/nice-price-forex-strategy/"""
        ...
