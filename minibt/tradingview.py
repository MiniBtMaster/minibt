from .utils import (Literal, np, pd, partial, reduce, get_lennan,
                    MaType, FILED, Union, LineStyle, LineDash, Colors)
from .indicators import BtIndicator, series, dataframe
import math
from numba import njit, float64, int64


class Powertrend_Volume_Range_Filter_Strategy(BtIndicator):
    """✈  https://cn.tradingview.com/script/45FlB2qH-Powertrend-Volume-Range-Filter-Strategy-wbburgin/"""
    params = dict(l=200, lengthvwma=200, mult=3., lengthadx=200, lengthhl=14,
                  useadx=False, usehl=False, usevwma=False, highlighting=True)
    overlap = dict(volrng=True, hband=True, lowband=True, dir=False)

    @staticmethod
    def smoothrng(x: series, t: int, m: float = 1.):
        """平滑平均范围"""
        wper = t*2 - 1
        avrng = (x - x.shift()).abs().ema(t)
        smoothrng = m*avrng.ema(wper)
        return smoothrng

    def _rngfilt_volumeadj(self, source1: series, tethersource: series, smoothrng: series):
        source1 = source1.values
        size = source1.size
        rngfilt = source1.copy()
        dir = np.zeros(size)
        start = self.get_lennan(source1, tethersource, smoothrng)
        for i in range(start+1, size):
            if tethersource[i] > tethersource[i-1]:
                rngfilt[i], dir[i] = ((source1[i] - smoothrng[i]) < rngfilt[i-1]
                                      ) and (rngfilt[i-1], dir[i-1]) or (source1[i] - smoothrng[i], 1)

            else:
                rngfilt[i], dir[i] = ((source1[i] + smoothrng[i]) > rngfilt[i-1]
                                      ) and (rngfilt[i-1], dir[i-1]) or (source1[i] + smoothrng[i], -1)
        return series(rngfilt, lines=["rngfilt"]), dir

    def next(self):
        smoothrng = self.smoothrng(self.close, self.params.l, self.params.mult)
        volrng, dir = self._rngfilt_volumeadj(
            self.close, self.volume, smoothrng)
        hband: series = volrng + smoothrng
        lowband: series = volrng - smoothrng

        adx = self.adx(self.params.lengthadx).adxx
        adx_vwma = adx.vwma(self.params.lengthadx)
        adx_filter = adx > adx_vwma

        lowband_trendfollow = lowband.tqfunc.llv(self.params.lengthhl)
        highband_trendfollow = hband.tqfunc.hhv(self.params.lengthhl)
        igu_filter_positive = self.close.cross_up(highband_trendfollow.shift()).tqfunc.barlast(
        ) < self.close.cross_down(lowband_trendfollow.shift()).tqfunc.barlast()
        igu_filter_negative = ~igu_filter_positive

        vwma = volrng.vwma(length=self.params.length)
        vwma_filter_positive = volrng > vwma

        long_signal = dir > 0
        long_signal &= self.close.cross_up(hband)
        long_signal &= igu_filter_positive
        long_signal &= adx_filter
        long_signal &= vwma_filter_positive
        # exitlong_signal = dir < 0
        # exitlong_signal &= self.close.cross_down(lowband)
        # exitlong_signal &= igu_filter_negative
        # exitlong_signal &= adx_filter

        short_signal = dir < 0
        short_signal &= self.close.cross_down(lowband)
        short_signal &= igu_filter_negative
        short_signal &= adx_filter
        short_signal &= vwma_filter_positive

        return volrng, hband, lowband, dir, long_signal, short_signal


class Nadaraya_Watson_Envelope_Strategy(BtIndicator):
    """✈ https://cn.tradingview.com/script/HrZicISx-Nadaraya-Watson-Envelope-Strategy-Non-Repainting-Log-Scale/"""
    params = dict(customLookbackWindow=8., customRelativeWeighting=8., customStartRegressionBar=25.,
                  length=60, customATRLength=60, customNearATRFactor=1.5, customFarATRFactor=2.)
    overlap = True

    def get_weight(self, x=0, alpha=0, h=0) -> tuple[np.ndarray]:
        weights = np.zeros(h)
        for i in range(h):
            weights[i] = np.power(
                1. + (np.power((x - i), 2.) / (2. * alpha * h * h)), -alpha)
        return weights

    @staticmethod
    def customKernel(close: pd.Series, weights=None) -> float:
        size = close.size
        close = close.apply(lambda x: np.log(x)).values
        sumXWeights = 0.
        sumWeights = 0.
        for i in range(size):
            weight = weights[i]
            sumWeights += weight
            sumXWeights += weight * close[i]
        return np.exp(sumXWeights / sumWeights)

    @staticmethod
    def customATR(length, _high, _low, _close) -> series:
        df = dataframe(dict(high=_high, low=_low, close=_close))
        tr = df.true_range()
        return tr.rma(length)

    @staticmethod
    def getEnvelopeBounds(_atr, _nearFactor, _farFactor, _envelope):
        _upperFar = _envelope + _farFactor*_atr
        _upperNear = _envelope + _nearFactor*_atr
        _lowerNear = _envelope - _nearFactor*_atr
        _lowerFar = _envelope - _farFactor*_atr
        _upperAvg = (_upperFar + _upperNear) / 2
        _lowerAvg = (_lowerFar + _lowerNear) / 2
        return _upperNear, _upperFar, _upperAvg, _lowerNear, _lowerFar, _lowerAvg

    def next(self):
        x = self.params.customStartRegressionBar
        h = int(self.params.customStartRegressionBar)
        alpha = self.params.customRelativeWeighting
        weights = self.get_weight(x=x, alpha=alpha, h=h)
        func = partial(self.customKernel, weights=weights)
        customEnvelopeClose = self.close.rolling(
            h).apply(func)
        customEnvelopeHigh = self.high.rolling(
            h).apply(func)
        customEnvelopeLow = self.low.rolling(
            h).apply(func)

        customATR = self.customATR(
            self.params.customATRLength, customEnvelopeHigh, customEnvelopeLow, customEnvelopeClose)

        customUpperNear, customUpperFar, customUpperAvg, customLowerNear, customLowerFar, customLowerAvg = self.getEnvelopeBounds(
            customATR, self.params.customNearATRFactor, self.params.customFarATRFactor, customEnvelopeClose)

        long_signal = self.close.cross_up(customEnvelopeLow)
        long_signal &= customEnvelopeClose > customEnvelopeClose.shift()
        short_signal = self.close.cross_down(customEnvelopeHigh)
        short_signal &= customEnvelopeClose < customEnvelopeClose.shift()

        return customEnvelopeClose, customEnvelopeHigh, customEnvelopeLow, customUpperNear, customUpperFar, \
            customUpperAvg, customLowerNear, customLowerFar, customLowerAvg, long_signal, short_signal  # test


class G_Channels(BtIndicator):
    """✈ https://www.tradingview.com/script/fIvlS64B-G-Channels-Efficient-Calculation-Of-Upper-Lower-Extremities/"""
    params = dict(length=144., cycle=1, thresh=0.)
    overlap = True

    def next(self):
        length = self.params.length
        cycle = max(int(self.params.cycle), 1)
        size = self.close.size
        a = np.full(size, np.nan)
        b = np.full(size, np.nan)
        close = self.close.values
        pre_a = 0.
        pre_b = 0.
        for i in range(size):
            if i and i % cycle == 0:
                a[i] = max(close[i], pre_a)-(pre_a-pre_b) / length
                b[i] = min(close[i], pre_b)+(pre_a-pre_b) / length
                pre_a = a[i]
                pre_b = b[i]
        if cycle > 1:
            a = pd.Series(a).interpolate(method="linear")
            b = pd.Series(b).interpolate(method="linear")
        avg = (a+b)/2.
        self.lines.a = a
        self.lines.b = b
        self.lines.avg = avg
        if 0. < self.params.thresh < 1.:
            self.lines.zig = self.btind.zigzag_full(self.params.thresh)


class STD_Filtered(BtIndicator):
    """✈ https://cn.tradingview.com/script/i4xZNAoy-STD-Filtered-N-Pole-Gaussian-Filter-Loxx/"""
    params = dict(period=25, order=5, filterperiod=10, filter=1.)
    overlap = dict(out=True, filt=True)  # , dir=False)

    @staticmethod
    def fact(n: int) -> float:
        if n < 2:
            return 1.
        return float(reduce(lambda x, y: x*y, range(1, n+1)))

    @staticmethod
    def alpha(period, poles):
        w = 2.0 * math.pi / period
        b = (1.0 - math.cos(w)) / (math.pow(1.414, 2.0 / poles) - 1.0)
        a = - b + math.sqrt(b * b + 2.0 * b)
        return a

    def makeCoeffs(self, period, order):
        coeffs = np.full((order+1, 3), 0.)
        a = self.alpha(period, order)
        for i in range(order+1):
            div = self.fact(order - i) * self.fact(i)
            out = self.fact(order) / div if div else 1.
            coeffs[i, :] = [out, math.pow(a, i), math.pow(1.0 - a, i)]
        return coeffs

    @staticmethod
    def npolegf(src: np.ndarray, order: int = 0, coeffs: np.ndarray = None):
        size = src.size
        nanlen = len(src[np.isnan(src)])
        filt = np.full(size-nanlen, np.nan)
        value = src[nanlen:]
        for j in range(size-nanlen):
            sign = 1.
            _filt = value[j]*coeffs[order, 1]
            for i in range(1, 1+order):
                if j >= i:
                    _filt += sign * coeffs[i, 0] * coeffs[i, 2] * filt[j-i]
                sign *= -1.
            filt[j] = _filt
        if not nanlen:
            return filt
        return np.append(np.full(nanlen, np.nan), filt)

    @staticmethod
    def std_filter(out: series, length: int, filter: float):
        std = out.stdev(length).values
        filtdev = filter * std
        nanlen = len(std[np.isnan(std)])
        filt = np.array(out.values)
        for i in range(nanlen+1, out.size):
            if abs(filt[i]-filt[i-1]) < filtdev[i]:
                filt[i] = filt[i-1]
        return filt

    def next(self):
        coeffs = self.makeCoeffs(self.params.period, self.params.order)
        src = self.ha().close
        # src = self.ohlc4()
        src = self.std_filter(
            src, self.params.filterperiod, self.params.filter)
        out = self.npolegf(src, order=self.params.order, coeffs=coeffs)
        filt = series(out, name="filt")
        filt = self.std_filter(
            filt, self.params.filterperiod, self.params.filter)
        _filt = pd.Series(filt)
        sig = _filt.shift()
        long_signal = _filt > sig
        long_signal &= (_filt.shift() < sig.shift()) | (
            _filt.shift() == sig.shift())
        short_signal = _filt < sig
        short_signal &= (_filt.shift() > sig.shift()) | (
            _filt.shift() == sig.shift())
        size = self.V
        contsw = np.zeros(size)
        for i in range(size):
            contsw[i] = long_signal[i] and 1 or (
                short_signal[i] and -1 or contsw[i-1])
        contsw = pd.Series(contsw)
        long_signal &= contsw.shift() == -1
        short_signal &= contsw.shift() == 1

        return filt, long_signal, short_signal


class Turtles_strategy(BtIndicator):
    """✈ https://cn.tradingview.com/script/Q1O23zJP-20-years-old-turtles-strategy-still-work/"""
    params = dict(enter_fast=20, exit_fast=10, enter_slow=55, exit_slow=20)

    def next(self):
        fastL = self.high.tqfunc.hhv(self.params.enter_fast)
        fastLC = self.low.tqfunc.llv(self.params.exit_fast)
        fastS = self.low.tqfunc.llv(self.params.enter_fast)
        fastSC = self.high.tqfunc.hhv(self.params.exit_fast)

        slowL = self.high.tqfunc.hhv(self.params.enter_slow)
        slowLC = self.low.tqfunc.llv(self.params.exit_slow)
        slowS = self.low.tqfunc.llv(self.params.enter_slow)
        slowSC = self.high.tqfunc.hhv(self.params.exit_slow)

        long_signal = self.high > fastL.shift()
        exitlong_signal = self.low <= fastLC.shift()
        short_signal = self.low < fastS.shift()
        exitshort_signal = self.high >= fastSC.shift()

        long_signal |= self.high > slowL.shift()
        exitlong_signal |= self.low <= slowLC.shift()
        short_signal |= self.low < slowS.shift()
        exitshort_signal |= self.high >= slowSC.shift()

        return long_signal, short_signal, exitlong_signal, exitshort_signal


class Adaptive_Trend_Filter(BtIndicator):
    """✈ https://cn.tradingview.com/script/PhSlALob-Adaptive-Trend-Filter-tradingbauhaus/"""
    params = dict(alphaFilter=0.01, betaFilter=0.1, filterPeriod=21,
                  supertrendFactor=1, supertrendAtrPeriod=7)
    overlap = dict(filteredValue=True, supertrendValue=True,
                   trendDirection=False)

    # Adaptive Filter Function
    def adaptiveFilter(self, b, alpha, beta):
        size = self.close.size
        close = self.close.values
        estimation = np.zeros(size)
        variance = 1.0
        coefficient = alpha * b

        estimation[0] = close[0]
        for i in range(1, size):
            previous = estimation[i-1]
            gain = variance / (variance + coefficient)
            estimation[i] = previous + gain * (close[i] - previous)
            variance = (1 - gain) * variance + beta / b

        return series(estimation)

    # Supertrend Function
    def supertrendFunc(self, src: series, factor: float, atrPeriod: int):
        atr = self.atr(atrPeriod)
        upperBand = src + factor * atr
        lowerBand = src - factor * atr
        size = src.size
        src = src.values
        upperBand, lowerBand = upperBand.values, lowerBand.values
        direction = np.full(size, 1.)
        superTrend = np.zeros(size)
        length = get_lennan(upperBand, lowerBand)
        for i in range(length+1, size):
            prevLowerBand = lowerBand[i-1]
            prevUpperBand = upperBand[i-1]

            lowerBand[i] = (lowerBand[i] > prevLowerBand or src[i -
                                                                1] < prevLowerBand) and lowerBand[i] or prevLowerBand
            upperBand[i] = (upperBand[i] < prevUpperBand or src[i -
                                                                1] > prevUpperBand) and upperBand[i] or prevUpperBand
            prevSuperTrend = superTrend[i-1]

            if prevSuperTrend == prevUpperBand:
                direction[i] = src[i] > upperBand[i] and -1 or 1
            else:
                direction[i] = src[i] < lowerBand[i] and 1 or -1
            superTrend[i] = direction[i] == - \
                1. and lowerBand[i] or upperBand[i]
        return superTrend, direction

    def next(self):
        # Apply Adaptive Filter and Supertrend
        filteredValue = self.adaptiveFilter(
            self.params.filterPeriod, self.params.alphaFilter, self.params.betaFilter)
        supertrendValue, trendDirection = self.supertrendFunc(
            filteredValue, self.params.supertrendFactor, self.params.supertrendAtrPeriod)

        return filteredValue, supertrendValue, trendDirection


class DCA_Strategy_with_Mean_Reversion_and_Bollinger_Band(BtIndicator):
    """https://cn.tradingview.com/script/uVaU9LVC-DCA-Strategy-with-Mean-Reversion-and-Bollinger-Band/"""

    params = dict(length=14, mult=2.)
    overlap = True

    def next(self):
        basis, bb_dev = self.close.t3(
            self.params.length), self.params.mult*self.close.stdev(self.params.length)
        upper = basis + bb_dev
        lower = basis - bb_dev
        long_signal = self.close.cross_up(lower) & (
            self.close > self.close.shift())
        short_signal = self.close.cross_down(
            upper) & (self.close < self.close.shift())
        return upper, lower, long_signal, short_signal


class Multi_Step_Vegas_SuperTrend_strategy(BtIndicator):
    """https://cn.tradingview.com/script/SXtas3lS-Multi-Step-Vegas-SuperTrend-strategy-presentTrading/"""
    params = dict(atrPeriod=10, vegasWindow=100,
                  superTrendMultiplier=5, volatilityAdjustment=5, matype="jma")
    overlap = dict(superTrend=True, marketTrend=False)

    def next(self):
        vegasMovingAverage: series = getattr(
            self.close, self.params.matype)(self.params.vegasWindow)
        # // Calculate the standard deviation for the Vegas Channel
        vegasChannelStdDev = self.close.stdev(self.params.vegasWindow)

        # // Upper and lower bands of the Vegas Channel
        vegasChannelUpper = vegasMovingAverage + vegasChannelStdDev
        vegasChannelLower = vegasMovingAverage - vegasChannelStdDev

        # // Adjust the SuperTrend multiplier based on the width of the Vegas Channel.
        channelVolatilityWidth = vegasChannelUpper - vegasChannelLower
        adjustedMultiplier = self.params.superTrendMultiplier + \
            self.params.volatilityAdjustment * \
            (channelVolatilityWidth / vegasMovingAverage)

        # // Calculate the SuperTrend indicator values.
        averageTrueRange = self.atr(self.params.atrPeriod)
        superTrendUpper_ = (
            self.hlc3() - (adjustedMultiplier * averageTrueRange)).values
        superTrendLower_ = (
            self.hlc3() + (adjustedMultiplier * averageTrueRange)).values
        size = self.close.size
        superTrendUpper = np.zeros(size)
        superTrendLower = np.zeros(size)
        marketTrend = np.zeros(size)
        lennan = get_lennan(superTrendUpper_, superTrendLower_)
        superTrendPrevUpper = superTrendUpper_[lennan]
        superTrendPrevLower = superTrendLower_[lennan]
        marketTrend[lennan] = 1
        superTrend = np.zeros(size)
        # // Update SuperTrend values and determine the current trend direction.
        close = self.close.values
        for i in range(lennan+1, size):
            marketTrend[i] = (close[i] > superTrendPrevLower) and 1 or (
                (close[i] < superTrendPrevUpper) and -1 or marketTrend[i-1])
            superTrendUpper[i] = (marketTrend[i] == 1) and max(
                superTrendUpper_[i], superTrendPrevUpper) or superTrendUpper_[i]
            superTrendLower[i] = (marketTrend[i] == -1) and min(
                superTrendLower_[i], superTrendPrevLower) or superTrendLower_[i]
            superTrendPrevUpper = superTrendUpper[i]
            superTrendPrevLower = superTrendLower[i]
            if marketTrend[i] == 1:
                superTrend[i] = superTrendUpper[i]
            else:
                superTrend[i] = superTrendLower[i]
        long_signal = marketTrend == 1
        long_signal &= np.append([0], marketTrend[:-1]) == -1
        short_signal = marketTrend == -1
        short_signal &= np.append([0], marketTrend[:-1]) == 1
        return superTrend, marketTrend, long_signal, short_signal


class The_Flash_Strategy(BtIndicator):
    """https://cn.tradingview.com/script/XKgLfo15-The-Flash-Strategy-Momentum-RSI-EMA-crossover-ATR/"""
    overlap = True
    params = dict(length=10, mom_rsi_val=50, atrPeriod=10,
                  factor=3., AP2=12, AF2=.1618)

    def next(self):
        src2 = self.close
        mom: series = src2 - src2.shift(self.params.length)
        rsi_mom = mom.rsi(self.params.length)
        supertrend, direction, * \
            _ = self.supertrend(self.params.atrPeriod,
                                self.params.factor).to_lines()
        src = self.close
        Trail1 = src.ema(self.params.AP2).values  # //Ema func
        AF2 = self.params.AF2 / 100.
        SL2 = Trail1 * AF2  # // Stoploss Ema
        size = self.close.size
        Trail2 = np.zeros(size)
        length = get_lennan(Trail1)
        dir = np.zeros(size)
        for i in range(length+1, size):
            iff_1 = Trail1[i] > Trail2[i-1] and Trail1[i] - \
                SL2[i] or Trail1[i] + SL2[i]
            iff_2 = (Trail1[i] < Trail2[i-1] and Trail1[i-1] < Trail2[i-1]
                     ) and min(Trail2[i-1], Trail1[i] + SL2[i]) or iff_1
            Trail2[i] = (Trail1[i] > Trail2[i-1] and Trail1[i-1] > Trail2[i-1]
                         ) and max(Trail2[i-1], Trail1[i] - SL2[i]) or iff_2
            dir[i] = Trail2[i] > Trail2[i -
                                        1] and 1. or (Trail2[i] < Trail2[i-1] and -1 or dir[i-1])
        dir = pd.Series(dir)
        long_signal = dir > 0
        long_signal &= dir.shift() < 0
        short_signal = dir < 0
        short_signal &= dir.shift() > 0

        return supertrend, Trail2, long_signal, short_signal


class Quantum_Edge_Pro_Adaptive_AI(BtIndicator):
    """https://cn.tradingview.com/script/iGZZmHEo-Quantum-Edge-Pro-Adaptive-AI/"""
    params = dict(TICK_SIZE=0.25, POINT_VALUE=2, DOLLAR_PER_POINT=2, LEARNING_PERIOD=40, ADAPTATION_SPEED=0.3,
                  PERFORMANCE_MEMORY=200, BASE_MIN_SCORE=2, BASE_BARS_BETWEEN=9, MAX_DAILY_TRADES=50)
    overlap = False

    def _vars(self):
        LEARNING_PERIOD = 40
        ADAPTATION_SPEED = 0.3
        PERFORMANCE_MEMORY = 200
        BASE_RISK = 0.005
        BASE_MIN_SCORE = 2
        BASE_BARS_BETWEEN = 9
        MAX_DAILY_TRADES = 50
        session_start = 5
        session_end = 16
        glowIntensity = 4
        adaptive_momentum_weight = 1.0
        adaptive_structure_weight = 1.2
        adaptive_volume_weight = 0.8
        adaptive_reversal_weight = 0.6
        adaptive_min_score = BASE_MIN_SCORE * 0.8
        adaptive_risk_multiplier = 1.0
        adaptive_bars_between = BASE_BARS_BETWEEN

        momentum_win_rate = 0.5
        structure_win_rate = 0.5
        volume_win_rate = 0.5
        reversal_win_rate = 0.5
        long_win_rate = 0.5
        short_win_rate = 0.5

    def MARKET_STRUCTURE_ANALYSIS(self) -> tuple[series]:
        swing_high = self.high.shift().tqfunc.hhv(20)
        swing_low = self.low.shift().tqfunc.llv(20)
        bullish_break = (self.close > swing_high) & (
            self.close.shift() <= swing_high)
        bearish_break = (self.close < swing_low) & (
            self.close.shift() >= swing_low)
        return bullish_break, bearish_break

    def MOMENTUM_INDICATORS(self) -> tuple[series]:
        rsi_fast = self.close.rsi(7)
        rsi_med = self.close.rsi(14)
        rsi_slow = self.close.rsi(21)

        macd, hist_macd, signal_macd = self.close.macd(12, 26, 9).to_lines()
        macd_bull = (hist_macd > hist_macd.shift()) & (hist_macd > 0.)
        macd_bear = (hist_macd < hist_macd.shift()) & (hist_macd < 0.)

        adx, diplus, diminus = self.adx(14, 14).to_lines()
        strong_trend = adx > 25.
        uptrend = (diplus > diminus) & strong_trend
        downtrend = (diminus > diplus) & strong_trend

        trending_viz = adx > 25.
        consolidating_viz = adx < 20.
        return uptrend, downtrend, macd_bull, macd_bear, rsi_fast, rsi_slow

    def VOLUME_ANALYSIS(self):
        vol_ma = self.volume.sma(20)
        vol_std = self.volume.stdev(20)
        high_volume = self.volume > (vol_ma + vol_std)
        relative_volume_viz = self.volume.ZeroDivision(vol_ma)
        vpt: series = (self.close.diff()/self.close.shift()
                       * self.volume).cum(10)
        vpt_signal = vpt.ema(10)
        volume_bullish = vpt > vpt_signal
        volume_bearish = -(vpt < vpt_signal)

        v2_orderFlowScore = volume_bullish+volume_bearish
        return volume_bullish, volume_bearish, high_volume, v2_orderFlowScore

    def next(self):
        atr = self.atr(14)
        current_volatility_pct = atr/self.close
        avg_volatility_calc = current_volatility_pct.sma(100)
        high_volatility_regime = (
            current_volatility_pct > 1.2*avg_volatility_calc).values
        low_volatility_regime = (
            current_volatility_pct < 0.8*avg_volatility_calc).values
        bullish_break, bearish_break = self.MARKET_STRUCTURE_ANALYSIS()
        bullish_break, bearish_break = bullish_break.values, bearish_break.values
        uptrend, downtrend, macd_bull, macd_bear, rsi_fast, rsi_slow = self.MOMENTUM_INDICATORS()
        uptrend, downtrend, macd_bull, macd_bear, rsi_fast, rsi_slow =\
            uptrend.values, downtrend.values, macd_bull.values, macd_bear.values, rsi_fast.values, rsi_slow.values
        volume_bullish, volume_bearish, high_volume, v2_orderFlowScore = self.VOLUME_ANALYSIS()
        volume_bullish, volume_bearish, high_volume = volume_bullish.values, volume_bearish.values, high_volume.values
        support = self.low.shift().tqfunc.llv(20).values
        resistance = self.high.shift().tqfunc.hhv(20).values
        close = self.close.values
        sma20 = self.close.sma(20)
        sma50 = self.close.sma(50)
        ma_up_cond = self.close > sma20
        ma_up_cond &= sma20 > sma50
        ma_up_cond = ma_up_cond.values
        ma_dn_cond = self.close < sma20
        ma_dn_cond &= sma20 < sma50
        ma_dn_cond = ma_dn_cond.values
        size = self.V
        # _momentum_score=np.zeros(size)
        final_momentum_weight = 1.  # ENABLE_ADAPTATION ? adaptive_momentum_weight : 1.0
        final_structure_weight = 1.2  # ENABLE_ADAPTATION ? adaptive_structure_weight : 1.2
        final_volume_weight = 0.8  # ENABLE_ADAPTATION ? adaptive_volume_weight : 0.8
        final_reversal_weight = 0.6  # ENABLE_ADAPTATION ? adaptive_reversal_weight : 0.6
        weighted_score = np.zeros(size)
        for i in range(120, size):
            momentum_score = 0.0
            structure_score = 0.0
            volume_score = 0.0
            reversal_score = 0.0
            momentum_multiplier = high_volatility_regime[i] and 0.8 or (
                low_volatility_regime[i] and 1.2 or 1.0)
            if uptrend[i]:
                momentum_score += 0.8 * momentum_multiplier
            if macd_bull[i]:
                momentum_score += 0.4 * momentum_multiplier
            if rsi_fast[i] > 50. and rsi_fast[i] < 80.:
                momentum_score += 0.4 * momentum_multiplier

            if downtrend[i]:
                momentum_score -= 0.8 * momentum_multiplier
            if macd_bear[i]:
                momentum_score -= 0.4 * momentum_multiplier
            if rsi_fast[i] < 50. and rsi_fast[i] > 20.:
                momentum_score -= 0.4 * momentum_multiplier

            if bullish_break[i]:
                structure_score += 1.0
            if bearish_break[i]:
                structure_score -= 1.0

            if volume_bullish[i] and high_volume[i]:
                volume_score += 1.0
            if volume_bearish[i] and high_volume[i]:
                volume_score -= 1.0

            if rsi_slow[i] < 30. and rsi_fast[i] > rsi_fast[i-1] and close[i] <= support[i]:
                reversal_score += 1.0
            if rsi_slow[i] > 70. and rsi_fast[i] < rsi_fast[i-1] and close[i] >= resistance[i]:
                reversal_score -= 1.0

            if ma_up_cond[i]:
                structure_score += 0.5
            if ma_dn_cond[i]:
                structure_score -= 0.5

            weighted_score[i] = (momentum_score * final_momentum_weight) + \
                (structure_score * final_structure_weight) + \
                (volume_score * final_volume_weight) + \
                (reversal_score * final_reversal_weight)
        return weighted_score


class LOWESS(BtIndicator):
    """https://cn.tradingview.com/script/hyeoDyZn-LOWESS-Locally-Weighted-Scatterplot-Smoothing-ChartPrime/"""
    params = dict(length=100, malen=100)
    overlap = True

    def next(self):
        length = self.params.length
        close = self.close.values
        atr = self.atr(length)
        std = self.close.stdev(length)
        sigma = (atr+std)/2.
        sigma = sigma.values
        data = dataframe(dict(close=close, sigma=sigma))

        def func(close: np.ndarray, sigma: np.ndarray):
            close = close[::-1]
            sigma = sigma[-1]
            gma = 0.
            sumOfWeights = 0.
            for i in range(length):
                h_l = close[:i+1]
                highest = h_l.max()
                lowest = h_l.min()
                weight = math.exp(-math.pow(((i - (length - 1)
                                              ) / (2 * sigma)), 2) / 2)
                value = highest+lowest
                gma = gma + (value * weight)
                sumOfWeights += weight

            return (gma / sumOfWeights) / 2.

        GaussianMA = data.rolling_apply(func, length)

        def lowess(src: pd.Series):
            length = len(src)
            src = src.values[::-1]
            sum_w = 0.0
            sum_wx = 0.0
            sum_wy = 0.0
            for i in range(length):
                w = math.pow(1 - math.pow(i / length, 3), 3)
                sum_w += w
                sum_wx += w * i
                sum_wy += w * src[i]
            a = sum_wy / sum_w
            b = sum_wx / sum_w
            return a + b / (length - 1) / 2000.

        smoothed = GaussianMA.rolling(self.params.malen).apply(lowess)

        return GaussianMA, smoothed


class The_Price_Radio(BtIndicator):
    """https://cn.tradingview.com/script/W5lBL0MV-John-Ehlers-The-Price-Radio/"""
    params = dict(length=60, period=14)
    overlap = False

    @staticmethod
    def clamp(_value, _min, _max) -> series:
        df = dataframe(dict(_value=_value, _min=_min, _max=_max))

        def test(_value, _min, _max):
            _t = _min if _value < _min else _value
            return _max if _t > _max else _t
        return df.rolling_apply(test, 1)

    @staticmethod
    def am(_signal: series, _period) -> series:
        _envelope = _signal.abs().tqfunc.hhv(4)
        return _envelope.sma(_period)

    @staticmethod
    def fm(_signal: series, _period) -> series:
        _h = _signal.tqfunc.hhv(_period)
        _l = _signal.tqfunc.llv(_period)
        _hl = The_Price_Radio.clamp(10. * _signal, _l, _h)
        return _hl.sma(_period)

    def next(self):
        deriv = self.close.pct_change(self.params.period)
        amup = The_Price_Radio.am(deriv, self.params.length)
        amdn = -amup
        fm = The_Price_Radio.fm(deriv, self.params.length)
        return deriv, amup, amdn, fm


class PMax_Explorer(BtIndicator):
    """https://cn.tradingview.com/script/nHGK4Qtp/"""

    params = dict(Periods=10, Multiplier=3,
                  mav="ema", length=10, var_length=9)
    overlap = True

    def var_Func(self, src: series, length: int, var_length):
        valpha = 2/(length+1)
        vud1 = src-src.shift()
        vud1 = vud1.apply(lambda x: x > 0. and x or 0.)
        vdd1 = vud1.apply(lambda x: x < 0. and -x or 0.)
        # vud1=src>src[1] ? src-src[1] : 0
        # vdd1=src<src[1] ? src[1]-src : 0
        vUD = vud1.rolling(var_length).sum()
        vDD = vdd1.rolling(var_length).sum()
        vCMO = (vUD-vDD).ZeroDivision(vUD+vDD)
        vCMO = vCMO.values
        nanlen = len(vCMO[np.isnan(vCMO)])
        size = src.size
        value = src.values
        VAR = np.zeros(size)
        for i in range(nanlen+1, size):
            VAR[i] = valpha*abs(vCMO[i])*value[i] + \
                (1-valpha*abs(vCMO[i]))*VAR[i-1]
        return series(VAR)

    def wwma_Func(self, src: series, length: int):
        wwalpha = 1 / length
        value = src.value
        size = src.size
        WWMA = np.zeros(size)
        for i in range(1, size):
            WWMA[i] = wwalpha*value[i] + (1-wwalpha)*WWMA[i-1]
        return series(WWMA)

    def zlema_Func(self, src: series, length: int):
        zxLag = length/2 == round(length/2) and length/2 or (length - 1) / 2
        zxEMAData = src + src.shift(zxLag)
        ZLEMA = zxEMAData.ema(length)
        return ZLEMA

    def tsf_Func(self, src: series, length: int):
        lrc = src.linreg(length)
        lrc1 = src.linreg(length, 1)
        lrs = lrc-lrc1
        TSF = src.linreg(length)+lrs
        return TSF

    def getMA(self, src: series, mav: str, length: int) -> series:
        """
        >>> "dema", "ema", "fwma", "hma", "linreg", "midpoint", "pwma", "rma",
            "sinwma", "sma", "swma", "t3", "tema", "trima", "vidya", "wma", "zlma"
            "var", "wwma", "zlema", "tsf"
        """
        if mav in ["dema", "ema", "fwma", "hma", "linreg", "midpoint", "pwma", "rma",
                   "sinwma", "sma", "swma", "t3", "tema", "trima", "vidya", "wma", "zlma"]:
            return src.ma(mav, length)
        elif mav in ["var", "wwma", "zlema", "tsf"]:
            return getattr(self, f"{mav}_Func")(src, length)
        else:
            return src.ema(length)

    def Pmax_Func(self, src: series):
        atr = self.atr(self.params.Periods)
        ma = self.getMA(src, self.params.mav, self.params.length)
        up = ma + self.params.Multiplier*atr
        dn = ma - self.params.Multiplier*atr
        up = up.values
        dn = dn.values
        upnanlen = len(up[np.isnan(up)])
        dnnanlen = len(dn[np.isnan(dn)])
        nanlen = max(upnanlen, dnnanlen)
        size = self.V
        PMax = np.zeros(size)
        PMax[nanlen] = dn[nanlen]
        dir = np.ones(size)
        MAvg = ma.values
        for i in range(nanlen+1, size):
            dir[i] = (dir[i-1] == -1 and MAvg[i] > PMax[i-1]
                      ) and 1 or ((dir[i-1] == 1 and MAvg[i] < PMax[i-1]) and -1 or dir[i-1])
            # if dir[i] != dir[i-1]:
            #     PMax[i] = dir[i] > dir[i-1] and dn[i] or up[i]
            #     continue
            PMax[i] = dir[i] == 1 and max(
                dn[i], PMax[i-1]) or min(up[i], PMax[i-1])
        return PMax

    def next(self):
        pmax = self.Pmax_Func(self.hl2())
        return pmax


class VMA_Win(BtIndicator):
    """https://cn.tradingview.com/script/09F2GICn-VMA-Win-Dashboard-for-Different-Lengths/"""
    params = dict(length=15)
    overlap = True

    def vma(self, src: series, length):
        vmaLen = length
        k = 1.0 / vmaLen
        size = src.size
        diff = src.diff()
        # math.max(src - src[1], 0)
        pdm = diff.apply(lambda x: x > 0. and x or 0.)
        # math.max(src[1] - src, 0)
        mdm = diff.apply(lambda x: x < 0. and -x or 0.)
        pdmS = np.zeros(size)
        mdmS = np.zeros(size)
        pdiS = np.zeros(size)
        mdiS = np.zeros(size)
        iS = np.zeros(size)
        vma = np.zeros(size)
        src = src.values
        for i in range(vmaLen+1, size):
            pdmS[i] = (1. - k) * pdmS[i-1] + k * pdm[i]
            mdmS[i] = (1. - k) * mdmS[i-1] + k * mdm[i]
            s = pdmS[i] + mdmS[i]
            pdi = pdmS[i] / s
            mdi = mdmS[i] / s
            pdiS[i] = (1. - k) * pdiS[i-1] + k * pdi
            mdiS[i] = (1. - k) * mdiS[i-1] + k * mdi
            d = abs(pdiS[i] - mdiS[i])
            s1 = pdiS[i] + mdiS[i]
            iS[i] = (1. - k) * iS[i-1] + k * d / s1
            hhv = iS[i+1-vmaLen:i+1].max()  # ta.highest(iS, vmaLen)
            llv = iS[i+1-vmaLen:i+1].min()  # ta.lowest(iS, vmaLen)
            vI = (iS[i] - llv) / (hhv - llv) if hhv != llv else 0.
            vma[i] = (1. - k * vI) * vma[i-1] + k * vI * src[i]
        return series(vma)

    def next(self):
        vma = self.vma(self.close, self.params.length)
        return vma


class RJ_Trend_Engine(BtIndicator):
    """https://cn.tradingview.com/script/xZ9IlWfi-RJ-Trend-Engine-Final-Version/"""
    params = dict(
        psarStart=0.02,
        psarIncrement=0.02,
        psarMax=0.2,
        stAtrPeriod=10,
        stFactor=3.0,
        adxLen=14,
        adxThreshold=20,
        bbLength=20,
        bbStdDev=3.0
    )
    overlap = True

    def next(self):
        psar = self.SAR(self.params.psarStart, self.params.psarMax)
        supertrend, st_direction, * \
            _ = self.supertrend(self.params.stAtrPeriod,
                                self.params.stFactor).to_lines()
        adx, diplus, diminus = self.adx(
            self.params.adxLen, self.params.adxLen).to_lines()
        # bbLower, bbMiddle, bbUpper, * \
        #     _ = self.close.bbands(self.params.bbLength,
        #                           self.params.bbStdDev).to_lines()
        psarFlipUp = (self.close > psar) & (self.open < psar.shift())
        psarFlipDown = (self.close < psar) & (self.open > psar.shift())
        stIsUptrend = st_direction < 0
        stIsDowntrend = st_direction > 0
        adxIsTrending = adx > self.params.adxThreshold
        standardBuySignal = psarFlipUp & stIsUptrend & adxIsTrending
        standardSellSignal = psarFlipDown & stIsDowntrend & adxIsTrending
        reversalBuySignal = psarFlipUp & adxIsTrending & stIsDowntrend
        reversalSellSignal = psarFlipDown & adxIsTrending & stIsUptrend
        long_signal = standardBuySignal | reversalBuySignal
        short_signal = standardSellSignal | reversalSellSignal
        return psar, supertrend, long_signal, short_signal


class Twin_Range_Filter(BtIndicator):
    """https://cn.tradingview.com/script/57i9oK2t-Twin-Range-Filter-Buy-Sell-Signals/"""

    params = dict(
        per1=127,
        mult1=1.6,
        per2=155,
        mult2=2.0,
    )
    overlap = True

    def smoothrng(self, x: series, t: int, m: float):
        wper = t * 2 - 1
        avrng = x.diff().abs().ema(t)
        return avrng.ema(wper) * m

    def rngfilt(self, x: series, r: series):
        size = x.size
        x = x.values
        r = r.values
        rf = np.zeros(size)
        lennan = max(len(x[pd.isnull(x)]), len(r[pd.isnull(r)]))
        rf[lennan] = x[lennan]
        for i in range(lennan+1, size):
            rf[i] = x[i] > rf[i-1] and (x[i] - r[i] < rf[i-1] and rf[i-1] or x[i] - r[i]) or (
                x[i] + r[i] > rf[i-1] and rf[i-1] or x[i] + r[i])
        return rf

    def next(self):
        source = self.close
        smrng1 = self.smoothrng(
            source, self.params.per1, self.params.mult1)
        smrng2 = self.smoothrng(
            source, self.params.per2, self.params.mult2)
        smrng = (smrng1 + smrng2) / 2
        filt = self.rngfilt(source, smrng)

        # // === Trend Detection ===
        size = self.V
        upward = np.zeros(size)
        downward = np.zeros(size)
        lennan = len(filt[pd.isnull(filt)])
        for i in range(lennan+1, size):
            upward[i] = filt[i] > filt[i-1] and upward[i-1] + \
                1 or (0 if filt[i] < filt[i-1] else upward[i-1])
            downward[i] = filt[i] < filt[i-1] and downward[i-1] + \
                1 or (0 if filt[i] > filt[i-1] else downward[i-1])

        # // === Entry Conditions ===
        longCond = (source > filt) & (upward > 0)
        shortCond = (source < filt) & (downward > 0)
        CondIni = np.zeros(size)
        for i in range(1, size):
            CondIni[i] = longCond[i] and 1 or (
                shortCond[i] and -1 or CondIni[i-1])
        CondIni = pd.Series(CondIni)
        long_signal = longCond & (CondIni.shift() == -1)
        short_signal = shortCond & (CondIni.shift() == 1)
        return filt, long_signal, short_signal


class PMax_Explorer_STRATEGY(BtIndicator):
    """https://cn.tradingview.com/script/nHGK4Qtp/"""
    params = dict(Periods=10, Multiplier=3., mav="ema", length=10)
    overlap = dict(pmax=True, thrend=False)

    def next(self):
        src = self.hl2()
        mult = self.params.Multiplier
        MAvg = self.close.ma(self.params.mav, self.params.length)
        pmax, thrend = self.btind.pmax2(self.params.length, mult).to_lines()
        long_signal = MAvg.cross_up(pmax) & src.cross_up(pmax)
        short_signal = MAvg.cross_down(pmax) & src.cross_down(pmax)
        return pmax, thrend, long_signal, short_signal


class UT_Bot_Alerts(BtIndicator):
    """https://cn.tradingview.com/script/n8ss8BID-UT-Bot-Alerts/"""
    params = dict(a=1., c=10, h=False)
    overlap = True

    def next(self):
        # // Inputs
        a = self.params.a  # "Key Vaule. 'This changes the sensitivity'"
        c = self.params.c  # "ATR Period"
        h = self.params.h  # "Signals from Heikin Ashi Candles"

        xATR = self.atr(c)
        nLoss = a * xATR
        if h:
            close = self.ha().close
        else:
            close = self.close
        size = close.size
        up = (close+nLoss).values
        dn = (close-nLoss).values
        src = close.values
        xATRTrailingStop = np.zeros(size)
        pos = np.zeros(size)
        index = self.get_first_valid_index(up, dn)
        for i in range(index+1, size):
            xATRTrailingStop[i] = (src[i] > xATRTrailingStop[i-1] and src[i-1] > xATRTrailingStop[i-1]) and max(xATRTrailingStop[i-1], dn[i]) or \
                ((src[i] < xATRTrailingStop[i-1] and src[i-1] < xATRTrailingStop[i-1]) and min(xATRTrailingStop[i-1], up[i]) or
                 ((src[i] > xATRTrailingStop[i-1]) and dn[i] or up[i]))

            pos[i] = (src[i-1] < xATRTrailingStop[i-1] and src[i] > xATRTrailingStop[i-1]) and 1 or \
                ((src[i-1] > xATRTrailingStop[i-1] and src[i]
                 < xATRTrailingStop[i-1]) and -1 or pos[i-1])

        ema = close.ema(1, talib=False)
        above = ema.cross_up(xATRTrailingStop)
        below = ema.cross_down(xATRTrailingStop)

        long_signal = close > xATRTrailingStop
        long_signal &= above
        short_signal = close < xATRTrailingStop
        short_signal &= below
        alerts = xATRTrailingStop

        return alerts, long_signal, short_signal


class SuperTrend(BtIndicator):
    """https://cn.tradingview.com/script/r6dAP7yi/"""
    params = dict(Periods=10, Multiplier=3., changeATR=True,)
    overlap = dict(upper=True, lower=True, trend=False)

    def next(self):
        src = self.hl2()
        size = src.size
        atr = self.atr(self.params.Periods)
        if not self.params.changeATR:
            atr = atr.sma(self.params.Periods)
        close = self.close.values
        up = (src-self.params.Multiplier*atr).values
        dn = (src+self.params.Multiplier*atr).values
        index = self.get_first_valid_index(up, dn)
        upper = np.full(size, np.nan)
        lower = np.full(size, np.nan)
        trend = np.ones(size)
        for i in range(index+1, size):
            up[i] = close[i-1] > up[i-1] and max(up[i], up[i-1]) or up[i]
            dn[i] = close[i-1] < dn[i-1] and min(dn[i], dn[i-1]) or dn[i]
            trend[i] = (trend[i-1] == -1 and close[i] > dn[i-1]) and 1 or (
                (trend[i-1] == 1 and close[i] < up[i-1]) and -1 or trend[i-1])
            if trend[i] != trend[i-1]:
                lower[i] = up[i]
                upper[i] = dn[i]
            elif trend[i] == 1:
                lower[i] = up[i]
            else:
                upper[i] = dn[i]
        trend = pd.Series(trend)
        long_signal = trend == 1
        long_signal &= trend.shift() == -1
        short_signal = trend == -1
        short_signal &= trend.shift() == 1
        return upper, lower, trend, long_signal, short_signal


class CM_Williams_Vix_Fix_Finds_Market_Bottoms(BtIndicator):
    """https://cn.tradingview.com/script/og7JPrRA-CM-Williams-Vix-Fix-Finds-Market-Bottoms/"""
    params = dict(hl=22, bbl=20, mult=2.0, lb=50, ph=.95, pl=1.01)
    overlap = False
    linestyle = dict(wvf=LineStyle(
        line_dash=LineDash.vbar))

    def next(self):
        hl = self.params.hl
        highest = self.close.tqfunc.hhv(hl)
        wvf = 100*(highest-self.low).ZeroDivision(highest)

        sDev = self.params.mult * wvf.stdev(self.params.bbl)
        midLine = wvf.sma(self.params.bbl)
        lowerBand = midLine - sDev
        upperBand = midLine + sDev

        rangeHigh = wvf.tqfunc.hhv(self.params.lb) * self.params.ph
        rangeLow = wvf.tqfunc.llv(self.params.lb) * self.params.pl
        return wvf, lowerBand, upperBand, rangeHigh, rangeLow


class WaveTrend_Oscillator(BtIndicator):
    """https://cn.tradingview.com/script/2KE8wTuF-Indicator-WaveTrend-Oscillator-WT/"""
    params = dict(n1=10, n2=21, n3=9)
    spanstyle = [60, 53, -60, -53]
    overlap = False
    linestyle = dict(signal=LineStyle(line_dash=LineDash.vbar))

    def next(self):
        ap = self.hlc3()
        esa = ap.ema(self.params.n1)
        d = (ap - esa).abs().ema(self.params.n1)
        ci = (ap - esa) / (0.015 * d)
        tci = ci.ema(self.params.n2)

        wt1 = tci
        wt2 = wt1.sma(self.params.n3)
        signal = wt1-wt2
        return signal, wt1, wt2


class ADX_and_DI(BtIndicator):
    """https://cn.tradingview.com/script/VTPMMOrx-ADX-and-DI/"""
    params = dict(length=14, th=20)
    overlap = False

    def next(self):
        length = self.params.length

        TrueRange = self.true_range()
        DirectionalMovementPlus = self.high.diff().tqfunc.max(
            0.).where(self.high.diff() <= -self.low.diff(), 0.)
        DirectionalMovementMinus = (
            0.-self.low.diff()).tqfunc.max(0.).where(-self.low.diff() <= self.high.diff(), 0.)
        size = self.close.size
        SmoothedTrueRange = np.zeros(size)
        SmoothedDirectionalMovementPlus = np.zeros(size)
        SmoothedDirectionalMovementMinus = np.zeros(size)
        index = self.get_first_valid_index(
            TrueRange, DirectionalMovementPlus, DirectionalMovementMinus)
        for i in range(index+1, size):
            SmoothedTrueRange[i] = SmoothedTrueRange[i-11] - \
                (SmoothedTrueRange[i-1])/length + TrueRange[i]
            SmoothedDirectionalMovementPlus[i] = SmoothedDirectionalMovementPlus[i-11] - (
                SmoothedDirectionalMovementPlus[i-1])/length + DirectionalMovementPlus[i]
            SmoothedDirectionalMovementMinus[i] = SmoothedDirectionalMovementMinus[i-11] - (
                SmoothedDirectionalMovementMinus[i-1])/length + DirectionalMovementMinus[i]

        DIPlus = SmoothedDirectionalMovementPlus / SmoothedTrueRange * 100
        DIMinus = SmoothedDirectionalMovementMinus / SmoothedTrueRange * 100
        DX = np.abs(DIPlus-DIMinus) / (DIPlus+DIMinus)*100
        ADX = pd.Series(DX).rolling(length).mean()
        return ADX, DIPlus, DIMinus


class Bollinger_RSI_Double_Strategy(BtIndicator):
    """https://cn.tradingview.com/script/uCV8I4xA-Bollinger-RSI-Double-Strategy-by-ChartArt-v1-1/"""
    params = dict(RSIlength=6, RSIoverSold=50.,
                  RSIoverBought=50., BBlength=200, BBmult=2.)
    overlap = True

    def next(self):
        # //////////// RSI
        RSIlength = self.params.RSIlength  # input(6,title="RSI Period Length")
        RSIoverSold = self.params.RSIoverSold
        RSIoverBought = self.params.RSIoverBought
        price = self.close
        vrsi = price.rsi(RSIlength)

        # ///////////// Bollinger Bands
        # input(200, minval=1,title="Bollinger Period Length")
        BBlength = self.params.BBlength
        # input(2.0, minval=0.001, maxval=50,title="Bollinger Bands Standard Deviation")
        BBmult = self.params.BBmult
        BBbasis = price.sma(BBlength)
        BBdev = BBmult * price.stdev(BBlength)
        BBupper = BBbasis + BBdev
        BBlower = BBbasis - BBdev
        long_signal = price.cross_up(BBlower)
        long_signal &= vrsi.cross_up(RSIoverSold)
        short_signal = price.cross_down(BBupper)
        short_signal &= vrsi.cross_down(RSIoverBought)
        return BBupper, BBlower, long_signal, short_signal


class Pivot_Point_Supertrend(BtIndicator):
    """https://cn.tradingview.com/script/L0AIiLvH-Pivot-Point-Supertrend/"""
    params = dict(prd=7, Factor=4, Pd=14,)
    overlap = True

    def next(self):
        prd = self.params.prd
        Factor = self.params.Factor
        Pd = self.params.Pd
        length = 2*prd+1
        # 原代码有未来函数，以下改为当前K线的前length根K线（包括自身K线）来转换
        size = self.V
        high, low = self.high.values, self.low.values
        center = self.full()
        center[length-1] = high[:length].max()
        for i in range(length, size):
            _high = high[i+1-5:i+1]
            _low = low[i+1-5:i+1]
            if _high.max() == _high[-1]:
                lastpp = _high[-1]
            elif _low.min() == _low[-1]:
                lastpp = _low[-1]
            else:
                lastpp = center[i-1]
            center[i] = (center[i-1]*2+lastpp)/3.

        Up = center - (Factor * self.atr(Pd))
        Dn = center + (Factor * self.atr(Pd))
        index = self.get_first_valid_index(Up, Dn)
        close = self.close.values
        TUp = self.full()
        TDown = self.full()
        TUp[index] = TDown[index] = close[index]
        Trend = self.ones
        Trailingsl = self.full()
        for i in range(index+1, size):
            TUp[i] = close[i-1] > TUp[i-1] and max(Up[i], TUp[i-1]) or Up[i]
            TDown[i] = close[i-1] < TDown[i -
                                          1] and min(Dn[i], TDown[i-1]) or Dn[i]
            Trend[i] = close[i] > TDown[i -
                                        1] and 1 or (close[i] < TUp[i-1] and -1 or Trend[i-1])
            Trailingsl[i] = Trend[i] == 1 and TUp[i] or TDown[i]
        Trend = pd.Series(Trend)
        long_signal = Trend == 1
        long_signal &= Trend.shift() == -1
        short_signal = Trend == -1
        short_signal &= Trend.shift() == 1
        return Trailingsl, long_signal, short_signal


class AlphaTrend(BtIndicator):
    """https://cn.tradingview.com/script/o50NYLAZ-AlphaTrend/"""
    params = dict(coeff=1., AP=14, novolumedata=False)
    overlap = True

    def next(self):
        coeff = self.params.coeff
        AP = self.params.AP
        novolumedata = self.params.novolumedata
        ATR = self.true_range().sma(AP)
        src = self.close

        upT = self.low - ATR * coeff
        downT = self.high + ATR * coeff
        upT, downT = upT.values, downT.values
        mfi = self.hlc3().mfi(AP).values
        rsi = src.rsi(AP).values
        AlphaTrend = self.zeros
        Trend = self.zeros
        size = src.size
        index = self.get_first_valid_index(upT, downT, mfi, rsi)
        for i in range(index+1, size):
            AlphaTrend[i] = (rsi[i] >= 50. if novolumedata else mfi[i] >= 50.) and (upT[i] < AlphaTrend[i-1] and AlphaTrend[i-1] or upT[i]) or \
                (downT[i] > AlphaTrend[i-1] and AlphaTrend[i-1] or downT[i])
            Trend[i] = AlphaTrend[i] > AlphaTrend[i -
                                                  2] and 1 or (AlphaTrend[i] < AlphaTrend[i-2] and -1 or Trend[i-1])
        AlphaTrend = series(AlphaTrend)
        AlphaTrend2 = AlphaTrend.shift(2)
        Trend = series(Trend)
        long_signal = (Trend.shift() == -1) & (Trend == 1)
        short_signal = (Trend.shift() == 1) & (Trend == -1)
        return AlphaTrend, AlphaTrend2, long_signal, short_signal


class Volume_Flow_Indicator(BtIndicator):
    """https://cn.tradingview.com/script/MhlDpfdS-Volume-Flow-Indicator-LazyBear/"""
    params = dict(length=130, coef=0.2, vcoef=2.5,
                  signalLength=5, smoothVFI=False)
    overlap = False

    def next(self):
        length = self.params.length
        coef = self.params.coef
        vcoef = self.params.vcoef
        signalLength = self.params.signalLength
        smoothVFI = self.params.smoothVFI
        volume = self.volume
        def ma(x: series, y): return x.sma(y) if smoothVFI else x

        typical = self.hlc3()
        inter = typical.apply(np.log).diff()
        vinter = inter.stdev(30)
        cutoff = coef * vinter * self.close
        vave = volume.sma(length).shift()
        vmax = vave * vcoef
        # vc = self.ifs(volume < vmax, volume,
        #               other=vmax) // volume.tqfunc.min(vmax)
        vc = volume.where(volume < vmax, vmax) // volume.tqfunc.min(vmax)
        mf = typical.shift()
        # vcp = self.ifs(mf > cutoff, vc,  other=self.ifs(
        #     mf < -cutoff, -vc, other=0.))
        vcp = vc.where(mf > cutoff, (-vc).where(mf < -cutoff, 0.))

        vfi = ma(vcp.rolling(length).sum()/vave, 3)
        vfima = vfi.ema(signalLength)

        return vfima, vfi


class Chandelier_Exit(BtIndicator):
    """https://cn.tradingview.com/script/AqXxNS7j-Chandelier-Exit/"""
    params = dict(length=22, mult=3., useClose=True)
    overlap = True

    def next(self):
        length = self.params.length
        mult = self.params.mult
        useClose = self.params.useClose

        atr = mult * self.atr(length)
        if useClose:
            longStop = self.close.tqfunc.hhv(length)-atr
            shortStop = self.close.tqfunc.llv(length)+atr
        else:
            longStop = self.high.tqfunc.hhv(length)-atr
            shortStop = self.high.tqfunc.llv(length)+atr
        dir = self.ones
        size = self.V
        close = self.close.values
        longStopPrev = longStop.shift().bfill().values
        longStop = longStop.bfill().values
        shortStopPrev = shortStop.shift().bfill().values
        shortStop = shortStop.bfill().values
        up = self.full()
        dn = self.full()
        for i in range(1, size):
            longStopPrev = longStop[i-1]
            longStop[i] = close[i] > longStopPrev and max(
                longStop[i], longStopPrev) or longStop[i]
            shortStopPrev = shortStop[i-1]
            shortStop[i] = close[i] < shortStopPrev and min(
                shortStop[i], shortStopPrev) or shortStop[i]
            dir[i] = close[i] > shortStopPrev and 1 or (
                close[i] < longStopPrev and -1 or dir[i-1])
            if dir[i] == 1:
                up[i] = longStop[i]
            else:
                dn[i] = shortStop[i]

        dir = series(dir)
        long_signal = dir == 1
        long_signal &= dir.shift() == -1
        short_signal = dir == -1
        short_signal &= dir.shift() == 1
        return up, dn, long_signal, short_signal


class SuperTrend_STRATEGY(BtIndicator):
    """https://cn.tradingview.com/script/P5Gu6F8k/"""
    params = dict(Periods=22, Multiplier=3., changeATR=True,)
    overlap = True

    def next(self):
        Periods = self.params.Periods
        src = self.hl2()
        Multiplier = self.params.Multiplier
        changeATR = self.params.changeATR
        if changeATR:
            atr = self.atr(Periods)
        else:
            atr = self.true_range().sma(Periods)
        longStop = src-(Multiplier*atr)
        shortStop = src+(Multiplier*atr)
        dir = self.ones
        size = self.V
        close = self.close.values
        longStop = longStop.bfill().values
        shortStop = shortStop.bfill().values
        up = self.full()
        dn = self.full()
        for i in range(1, size):
            longStopPrev = longStop[i-1]
            longStop[i] = close[i] > longStopPrev and max(
                longStop[i], longStopPrev) or longStop[i]
            shortStopPrev = shortStop[i-1]
            shortStop[i] = close[i] < shortStopPrev and min(
                shortStop[i], shortStopPrev) or shortStop[i]
            dir[i] = (dir[i-1] == -1 and close[i] > shortStopPrev) and 1 or (
                (dir[i-1] == 1 and close[i] < longStopPrev) and -1 or dir[i-1])
            if dir[i] == 1:
                up[i] = longStop[i]
            else:
                dn[i] = shortStop[i]
        dir = series(dir)
        long_signal = dir == 1
        long_signal &= dir.shift() == -1
        short_signal = dir == -1
        short_signal &= dir.shift() == 1
        return up, dn, long_signal, short_signal


class Optimized_Trend_Tracker(BtIndicator):
    """https://cn.tradingview.com/script/zVhoDQME/"""
    params = dict(length=2, var_length=9, percent=1.4, base=200)
    overlap = True

    def var_Func(self, src: series, length: int, var_length):
        valpha = 2/(length+1)
        vud1 = src-src.shift()
        vud1 = vud1.apply(lambda x: x > 0. and x or 0.)
        vdd1 = vud1.apply(lambda x: x < 0. and -x or 0.)
        # vud1=src>src[1] ? src-src[1] : 0
        # vdd1=src<src[1] ? src[1]-src : 0
        vUD = vud1.rolling(var_length).sum()
        vDD = vdd1.rolling(var_length).sum()
        vCMO = (vUD-vDD).ZeroDivision(vUD+vDD)
        vCMO = vCMO.values
        nanlen = len(vCMO[np.isnan(vCMO)])
        size = src.size
        value = src.values
        VAR = np.zeros(size)
        for i in range(nanlen+1, size):
            VAR[i] = valpha*abs(vCMO[i])*value[i] + \
                (1-valpha*abs(vCMO[i]))*VAR[i-1]
        return series(VAR)

    def next(self):
        percent = self.params.percent
        base = self.params.base
        base_up = (base+percent)/base
        base_dn = (base-percent)/base
        MAvg = self.var_Func(self.close, self.params.length,
                             self.params.var_length)
        fark = MAvg*percent*0.01
        longStop = MAvg - fark
        shortStop = MAvg + fark
        MAvg = MAvg.values
        longStop = longStop.values
        shortStop = shortStop.values
        lennan = len(longStop[np.isnan(longStop)])
        dir = np.ones(self.V)
        MT = np.full(self.V, np.nan)
        OTT = np.full(self.V, np.nan)
        for i in range(lennan+1, self.V):
            longStopPrev = longStop[i-1]
            longStop[i] = MAvg[i] > longStopPrev and max(
                longStop[i], longStopPrev) or longStop[i]
            shortStopPrev = shortStop[i-1]
            shortStop[i] = MAvg[i] < shortStopPrev and min(
                shortStop[i], shortStopPrev) or shortStop[i]
            dir[i] = (dir[i-1] == -1 and MAvg[i] > shortStopPrev) and 1 or (
                (dir[i-1] == 1 and MAvg[i] < longStopPrev) and -1 or dir[i-1])
            MT[i] = dir[i] == 1 and longStop[i] or shortStop[i]
            OTT[i] = MAvg[i] > MT[i] and MT[i] * \
                base_up or MT[i]*base_dn
        MT, OTT = series(MT), series(OTT)
        long_signal = OTT.cross_up(MT)
        short_signal = MT.cross_up(OTT)
        return MT, OTT, long_signal, short_signal


class TonyUX_EMA_Scalper(BtIndicator):
    """https://cn.tradingview.com/script/egfSfN1y-TonyUX-EMA-Scalper-Buy-Sell/"""
    params = dict(length=20, period=8)
    overlap = True

    def next(self):
        length = self.params.length
        period = self.params.period
        src = self.close
        out = src.ema(length)
        lasth = self.close.tqfunc.hhv(period)
        lastl = self.close.tqfunc.llv(period)

        long_signal = self.close.cross_up(out) & (
            self.close.shift() < self.close)
        short_signal = self.close.cross_down(out) & (
            self.close.shift() > self.close)
        return lasth, lastl, long_signal, short_signal


class Turtle_Trade_Channels_Indicator_TUTCI(BtIndicator):
    """https://cn.tradingview.com/script/pB5nv16J/"""
    params = dict(length=120, len2=100, )
    overlap = True
    linestyle = dict(sup=LineStyle(line_dash=LineDash.dotdash),
                     sdown=LineStyle(line_dash=LineDash.dotdash),
                     K=LineStyle(line_width=3.))

    def next(self):
        length = self.params.length
        len2 = self.params.len2

        up = self.high.tqfunc.hhv(length)
        down = self.low.tqfunc.llv(length)
        sup = self.high.tqfunc.hhv(len2)
        sdown = self.low.tqfunc.llv(len2)
        cond = (self.high >= up.shift()).tqfunc.barlast() <= (self.low <= down.shift(
        )).tqfunc.barlast()
        # cond = (self.close > up.shift()).tqfunc.barlast() <= (self.close < down.shift(
        # )).tqfunc.barlast()
        K1 = down.where(cond, up)
        K2 = sdown.where(cond, sup)
        kmax = K1.tqfunc.max(K2)
        kmin = K1.tqfunc.min(K2)
        K = kmin.where(cond, kmax)
        long_signal = cond & (~cond.shift())
        short_signal = (~cond) & cond.shift()

        exitlong_signal = self.low == sdown.shift()
        exitlong_signal |= sdown.shift().cross_up(self.low)
        exitshort_signal = self.high == sup.shift()
        exitshort_signal |= self.high.cross_up(sup.shift())

        return sup, sdown, K, long_signal, short_signal


class TradingView:
    """
    TradingView策略指标集合类

    该类封装了多种TradingView上的流行交易策略和指标，
    提供了统一的接口来调用这些策略进行技术分析。
    """
    _btdata: Union[dataframe, series]

    def __init__(self, data):
        """
        初始化TradingView策略分析器

        Args:
            data: 输入数据，可以是dataframe或series格式的价格数据
        """
        self._btdata = data

    def Powertrend_Volume_Range_Filter_Strategy(self, l=200, lengthvwma=200, mult=3., lengthadx=200, lengthhl=14,
                                                useadx=False, usehl=False, usevwma=False, highlighting=True, **kwargs) -> dataframe:
        """
        ## 成交量范围过滤策略

        ✈ https://cn.tradingview.com/script/45FlB2qH-Powertrend-Volume-Range-Filter-Strategy-wbburgin/

        Args:
            l: 平滑范围周期
            lengthvwma: 成交量加权移动平均周期
            mult: 范围乘数
            lengthadx: ADX指标周期
            lengthhl: 高低点周期
            useadx: 是否使用ADX过滤
            usehl: 是否使用高低点过滤
            usevwma: 是否使用VWMA过滤
            highlighting: 是否高亮显示
            **kwargs: 其他参数

        Returns:
            tuple: (volrng, hband, lowband, dir, long_signal, short_signal)
                - volrng: 成交量范围过滤线
                - hband: 上轨
                - lowband: 下轨
                - dir: 方向指标
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        return Powertrend_Volume_Range_Filter_Strategy(
            self._btdata, l=l, lengthvwma=lengthvwma, mult=mult,
            lengthadx=lengthadx, lengthhl=lengthhl, useadx=useadx,
            usehl=usehl, usevwma=usevwma, highlighting=highlighting, **kwargs
        )

    def Nadaraya_Watson_Envelope_Strategy(self, customLookbackWindow=8., customRelativeWeighting=8., customStartRegressionBar=25.,
                                          length=60, customATRLength=60, customNearATRFactor=1.5, customFarATRFactor=2., **kwargs) -> dataframe:
        """
        ## Nadaraya-Watson包络线策略
        ✈ https://cn.tradingview.com/script/HrZicISx-Nadaraya-Watson-Envelope-Strategy-Non-Repainting-Log-Scale/

        Args:
            customLookbackWindow: 自定义回看窗口
            customRelativeWeighting: 自定义相对权重
            customStartRegressionBar: 自定义回归起始柱
            length: 周期长度
            customATRLength: ATR周期长度
            customNearATRFactor: 近端ATR因子
            customFarATRFactor: 远端ATR因子
            **kwargs: 其他参数

        Returns:
            tuple: (customEnvelopeClose, customEnvelopeHigh, customEnvelopeLow, customUpperNear,
                   customUpperFar, customUpperAvg, customLowerNear, customLowerFar, customLowerAvg,
                   long_signal, short_signal)
        """
        return Nadaraya_Watson_Envelope_Strategy(
            self._btdata, customLookbackWindow=customLookbackWindow,
            customRelativeWeighting=customRelativeWeighting,
            customStartRegressionBar=customStartRegressionBar, length=length,
            customATRLength=customATRLength, customNearATRFactor=customNearATRFactor,
            customFarATRFactor=customFarATRFactor, **kwargs
        )

    def G_Channels(self, length=144., cycle=1, thresh=0., **kwargs) -> dataframe:
        """
        ## G通道指标 - 高效计算上下极值点

        ✈ https://www.tradingview.com/script/fIvlS64B-G-Channels-Efficient-Calculation-Of-Upper-Lower-Extremities/

        Args:
            length: 通道长度
            cycle: 周期循环
            thresh: zig参数
            **kwargs: 其他参数

        Returns:
            G_Channels: 包含a(上轨), b(下轨), avg(中轨), zig(之字转向)线的指标对象
        """
        return G_Channels(self._btdata, length=length, cycle=cycle, thresh=thresh, **kwargs)

    def STD_Filtered(self, period=25, order=5, filterperiod=10, filter=1., **kwargs) -> dataframe:
        """
        ## STD过滤N极高斯滤波器

        ✈ https://cn.tradingview.com/script/i4xZNAoy-STD-Filtered-N-Pole-Gaussian-Filter-Loxx/

        Args:
            period: 主周期
            order: 阶数
            filterperiod: 过滤周期
            filter: 过滤因子
            **kwargs: 其他参数

        Returns:
            tuple: (filt, long_signal, short_signal)
                - filt: 过滤后的信号线
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        return STD_Filtered(
            self._btdata, period=period, order=order,
            filterperiod=filterperiod, filter=filter, **kwargs
        )

    def Turtles_strategy(self, enter_fast=20, exit_fast=10, enter_slow=55, exit_slow=20, **kwargs) -> dataframe:
        """
        ## 海龟交易策略 - 历经20年验证的有效策略

        ✈ https://cn.tradingview.com/script/Q1O23zJP-20-years-old-turtles-strategy-still-work/

        Args:
            enter_fast: 快速入场周期
            exit_fast: 快速出场周期
            enter_slow: 慢速入场周期
            exit_slow: 慢速出场周期
            **kwargs: 其他参数

        Returns:
            tuple: (long_signal, short_signal,
                    exitlong_signal, exitshort_signal)
                - long_signal: 多头入场信号
                - short_signal: 空头入场信号
                - exitlong_signal: 多头出场信号
                - exitshort_signal: 空头出场信号
        """
        return Turtles_strategy(
            self._btdata, enter_fast=enter_fast, exit_fast=exit_fast,
            enter_slow=enter_slow, exit_slow=exit_slow, **kwargs
        )

    def Adaptive_Trend_Filter(self, alphaFilter=0.01, betaFilter=0.1, filterPeriod=21,
                              supertrendFactor=1, supertrendAtrPeriod=7, **kwargs) -> dataframe:
        """
        ## 自适应趋势过滤器

        ✈ https://cn.tradingview.com/script/PhSlALob-Adaptive-Trend-Filter-tradingbauhaus/

        Args:
            alphaFilter: Alpha过滤参数
            betaFilter: Beta过滤参数
            filterPeriod: 过滤周期
            supertrendFactor: 超级趋势因子
            supertrendAtrPeriod: 超级趋势ATR周期
            **kwargs: 其他参数

        Returns:
            tuple: (filteredValue, supertrendValue, trendDirection)
                - filteredValue: 过滤后的数值
                - supertrendValue: 超级趋势值
                - trendDirection: 趋势方向
        """
        return Adaptive_Trend_Filter(
            self._btdata, alphaFilter=alphaFilter, betaFilter=betaFilter,
            filterPeriod=filterPeriod, supertrendFactor=supertrendFactor,
            supertrendAtrPeriod=supertrendAtrPeriod, **kwargs
        )

    def DCA_Strategy_with_Mean_Reversion_and_Bollinger_Band(self, length=14, mult=2., **kwargs) -> dataframe:
        """
        ## 均值回归与布林带结合的DCA策略

        ✈ https://cn.tradingview.com/script/uVaU9LVC-DCA-Strategy-with-Mean-Reversion-and-Bollinger-Band/

        Args:
            length: 布林带周期
            mult: 布林带乘数
            **kwargs: 其他参数

        Returns:
            tuple: (upper, lower, long_signal, short_signal)
                - upper: 布林带上轨
                - lower: 布林带下轨
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        return DCA_Strategy_with_Mean_Reversion_and_Bollinger_Band(
            self._btdata, length=length, mult=mult, **kwargs
        )

    def Multi_Step_Vegas_SuperTrend_strategy(self, atrPeriod=10, vegasWindow=100,
                                             superTrendMultiplier=5, volatilityAdjustment=5, matype="jma", **kwargs) -> dataframe:
        """
        ## 多步维加斯超级趋势策略

        ✈ https://cn.tradingview.com/script/SXtas3lS-Multi-Step-Vegas-SuperTrend-strategy-presentTrading/

        Args:
            atrPeriod: ATR周期
            vegasWindow: 维加斯窗口
            superTrendMultiplier: 超级趋势乘数
            volatilityAdjustment: 波动率调整
            matype: 移动平均类型
            **kwargs: 其他参数

        Returns:
            tuple: (superTrend, marketTrend, long_signal, short_signal)
                - superTrend: 超级趋势线
                - marketTrend: 市场趋势
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        return Multi_Step_Vegas_SuperTrend_strategy(
            self._btdata, atrPeriod=atrPeriod, vegasWindow=vegasWindow,
            superTrendMultiplier=superTrendMultiplier,
            volatilityAdjustment=volatilityAdjustment, matype=matype, **kwargs
        )

    def The_Flash_Strategy(self, length=10, mom_rsi_val=50, atrPeriod=10,
                           factor=3., AP2=12, AF2=.1618, **kwargs) -> dataframe:
        """
        ## Flash策略 - 动量RSI与EMA交叉结合ATR

        ✈ https://cn.tradingview.com/script/XKgLfo15-The-Flash-Strategy-Momentum-RSI-EMA-crossover-ATR/

        Args:
            length: RSI周期
            mom_rsi_val: 动量RSI阈值
            atrPeriod: ATR周期
            factor: 超级趋势因子
            AP2: 自适应周期参数2
            AF2: 自适应因子2
            **kwargs: 其他参数

        Returns:
            tuple: (supertrend, Trail2, long_signal, short_signal)
                - supertrend: 超级趋势线
                - Trail2: 跟踪止损线2
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        return The_Flash_Strategy(
            self._btdata, length=length, mom_rsi_val=mom_rsi_val,
            atrPeriod=atrPeriod, factor=factor, AP2=AP2, AF2=AF2, **kwargs
        )

    def Quantum_Edge_Pro_Adaptive_AI(self, TICK_SIZE=0.25, POINT_VALUE=2, DOLLAR_PER_POINT=2, LEARNING_PERIOD=40, ADAPTATION_SPEED=0.3,
                                     PERFORMANCE_MEMORY=200, BASE_MIN_SCORE=2, BASE_BARS_BETWEEN=9, MAX_DAILY_TRADES=50, **kwargs) -> dataframe:
        """
        ## 量子边缘专业自适应AI策略

        ✈ https://cn.tradingview.com/script/iGZZmHEo-Quantum-Edge-Pro-Adaptive-AI/

        Args:
            TICK_SIZE: 最小变动价位
            POINT_VALUE: 点值
            DOLLAR_PER_POINT: 每点美元价值
            LEARNING_PERIOD: 学习周期
            ADAPTATION_SPEED: 适应速度
            PERFORMANCE_MEMORY: 性能记忆周期
            BASE_MIN_SCORE: 基础最小分数
            BASE_BARS_BETWEEN: 基础间隔柱数
            MAX_DAILY_TRADES: 最大日交易次数
            **kwargs: 其他参数

        Returns:
            weighted_score: 加权评分信号
        """
        return Quantum_Edge_Pro_Adaptive_AI(
            self._btdata, TICK_SIZE=TICK_SIZE, POINT_VALUE=POINT_VALUE,
            DOLLAR_PER_POINT=DOLLAR_PER_POINT, LEARNING_PERIOD=LEARNING_PERIOD,
            ADAPTATION_SPEED=ADAPTATION_SPEED, PERFORMANCE_MEMORY=PERFORMANCE_MEMORY,
            BASE_MIN_SCORE=BASE_MIN_SCORE, BASE_BARS_BETWEEN=BASE_BARS_BETWEEN,
            MAX_DAILY_TRADES=MAX_DAILY_TRADES, **kwargs
        )

    def LOWESS(self, length=100, malen=100, **kwargs) -> dataframe:
        """
        ## LOWESS局部加权散点图平滑

        ✈ https://cn.tradingview.com/script/hyeoDyZn-LOWESS-Locally-Weighted-Scatterplot-Smoothing-ChartPrime/

        Args:
            length: 主周期长度
            malen: 移动平均长度
            **kwargs: 其他参数

        Returns:
            tuple: (GaussianMA, smoothed)
                - GaussianMA: 高斯移动平均
                - smoothed: 平滑后的信号
        """
        return LOWESS(self._btdata, length=length, malen=malen, **kwargs)

    def The_Price_Radio(self, length=60, period=14, **kwargs) -> dataframe:
        """
        ## John Ehlers价格收音机指标

        ✈ https://cn.tradingview.com/script/W5lBL0MV-John-Ehlers-The-Price-Radio/

        Args:
            length: 周期长度
            period: 变化周期
            **kwargs: 其他参数

        Returns:
            tuple: (deriv, amup, amdn, fm)
                - deriv: 价格导数
                - amup: AM上轨
                - amdn: AM下轨
                - fm: FM信号
        """
        return The_Price_Radio(self._btdata, length=length, period=period, **kwargs)

    def PMax_Explorer(self, Periods=10, Multiplier=3, mav="ema", length=10, var_length=9, **kwargs) -> dataframe:
        """
        ## PMax探索者指标

        ✈ https://cn.tradingview.com/script/nHGK4Qtp/

        Args:
            Periods: ATR周期
            Multiplier: 乘数因子
            mav: 移动平均类型
            length: 移动平均长度
            var_length: 变异长度
            **kwargs: 其他参数

        Returns:
            pmax: PMax指标线
        """
        return PMax_Explorer(
            self._btdata, Periods=Periods, Multiplier=Multiplier,
            mav=mav, length=length, var_length=var_length, **kwargs
        )

    def VMA_Win(self, length=15, **kwargs) -> dataframe:
        """
        ## VMA赢家仪表板 - 不同长度的VMA分析

        ✈ https://cn.tradingview.com/script/09F2GICn-VMA-Win-Dashboard-for-Different-Lengths/

        Args:
            length: VMA周期长度
            **kwargs: 其他参数

        Returns:
            vma: 变异移动平均线
        """
        return VMA_Win(self._btdata, length=length, **kwargs)

    def RJ_Trend_Engine(self, psarStart=0.02, psarIncrement=0.02, psarMax=0.2, stAtrPeriod=10,
                        stFactor=3.0, adxLen=14, adxThreshold=20, bbLength=20, bbStdDev=3.0, **kwargs) -> dataframe:
        """
        ## RJ趋势引擎 - 最终版本

        ✈ https://cn.tradingview.com/script/xZ9IlWfi-RJ-Trend-Engine-Final-Version/

        Args:
            psarStart: SAR起始值
            psarIncrement: SAR增量
            psarMax: SAR最大值
            stAtrPeriod: 超级趋势ATR周期
            stFactor: 超级趋势因子
            adxLen: ADX长度
            adxThreshold: ADX阈值
            bbLength: 布林带长度
            bbStdDev: 布林带标准差
            **kwargs: 其他参数

        Returns:
            tuple: (psar, supertrend, long_signal, short_signal)
                - psar: 抛物线转向指标
                - supertrend: 超级趋势线
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        return RJ_Trend_Engine(
            self._btdata, psarStart=psarStart, psarIncrement=psarIncrement,
            psarMax=psarMax, stAtrPeriod=stAtrPeriod, stFactor=stFactor,
            adxLen=adxLen, adxThreshold=adxThreshold, bbLength=bbLength,
            bbStdDev=bbStdDev, **kwargs
        )

    def Twin_Range_Filter(self, per1=127, mult1=1.6, per2=155, mult2=2.0, **kwargs) -> dataframe:
        """
        ## 双范围过滤器 - 买卖信号生成

        ✈ https://cn.tradingview.com/script/57i9oK2t-Twin-Range-Filter-Buy-Sell-Signals/

        Args:
            per1: 第一个周期
            mult1: 第一个乘数
            per2: 第二个周期
            mult2: 第二个乘数
            **kwargs: 其他参数

        Returns:
            tuple: (filt, long_signal, short_signal)
                - filt: 过滤线
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        return Twin_Range_Filter(
            self._btdata, per1=per1, mult1=mult1, per2=per2, mult2=mult2, **kwargs
        )

    def PMax_Explorer_STRATEGY(self, Periods=10, Multiplier=3., mav="ema", length=10, **kwargs) -> dataframe:
        """
        ## PMax探索者策略

        ✈ https://cn.tradingview.com/script/nHGK4Qtp/

        Args:
            Periods: 周期参数
            Multiplier: 乘数因子
            mav: 移动平均类型
            length: 移动平均长度
            **kwargs: 其他参数

        Returns:
            tuple: (pmax, thrend, long_signal, short_signal)
                - pmax: PMax指标线
                - thrend: 趋势线
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        return PMax_Explorer_STRATEGY(
            self._btdata, Periods=Periods, Multiplier=Multiplier,
            mav=mav, length=length, **kwargs
        )

    def UT_Bot_Alerts(self, a=1., c=10, h=False, **kwargs) -> dataframe:
        """
        ## UT Bot 警报指标

        ✈ https://cn.tradingview.com/script/n8ss8BID-UT-Bot-Alerts/

        Args:
            a: 调整因子参数，默认 `1.0`
            c: 周期相关参数，默认 `10`
            h: 布尔值，控制是否启用高亮等额外显示逻辑，默认 `False`
            **kwargs: 其他扩展参数

        Returns:
            UT Bot 警报相关的指标数据（如信号标记、警报触发状态等）
        """
        return UT_Bot_Alerts(self._btdata, a=a, c=c, h=h, **kwargs)

    def SuperTrend(self, Periods=10, Multiplier=3., changeATR=True, **kwargs) -> dataframe:
        """
        ## 超级趋势指标

        ✈ https://cn.tradingview.com/script/r6dAP7yi/

        Args:
            Periods: ATR 计算周期，默认 `10`
            Multiplier: ATR 乘数（用于调整趋势带宽度），默认 `3.0`
            changeATR: 布尔值，控制是否采用特殊逻辑计算 ATR，默认 `True`
            **kwargs: 其他扩展参数

        Returns:
            超级趋势指标相关数据（如趋势线位置、多空趋势信号等）
        """
        return SuperTrend(self._btdata, Periods=Periods, Multiplier=Multiplier, changeATR=changeATR, **kwargs)

    def CM_Williams_Vix_Fix_Finds_Market_Bottoms(self, hl=22, bbl=20, mult=2.0, lb=50, ph=.85, pl=1.01, **kwargs) -> dataframe:
        """
        ## CM Williams Vix Fix 市场底部识别指标

        ✈ https://cn.tradingview.com/script/og7JPrRA-CM-Williams-Vix-Fix-Finds-Market-Bottoms/

        Args:
            hl: 高低点计算周期，默认 `22`
            bbl: 布林带周期，默认 `20`
            mult: 布林带乘数，默认 `2.0`
            lb: 历史范围统计周期，默认 `50`
            ph: 高点范围系数，默认 `0.85`
            pl: 低点范围系数，默认 `1.01`
            **kwargs: 其他扩展参数

        Returns:
            包含 `vwf`（波动率指标）、`lowerBand`（下轨）、`upperBand`（上轨）、`rangeHigh`（高范围）、`rangeLow`（低范围）的指标数据
        """
        return CM_Williams_Vix_Fix_Finds_Market_Bottoms(self._btdata, hl=hl, bbl=bbl, mult=mult, lb=lb, ph=ph, pl=pl, **kwargs)

    def WaveTrend_Oscillator(self, n1=10, n2=21, n3=9, **kwargs) -> dataframe:
        """
        ## WaveTrend 振荡器指标

        ✈ https://cn.tradingview.com/script/2KE8wTuF-Indicator-WaveTrend-Oscillator-WT/

        Args:
            n1: 第一周期参数，默认 `10`
            n2: 第二周期参数，默认 `21`
            n3: 第三周期参数，默认 `9`
            **kwargs: 其他扩展参数

        Returns:
            包含 `signal`（信号值）、`wt1`（WaveTrend 核心值1）、`wt2`（WaveTrend 核心值2）的指标数据
        """
        return WaveTrend_Oscillator(self._btdata, n1=n1, n2=n2, n3=n3, **kwargs)

    def ADX_and_DI(self, length=14, **kwargs) -> dataframe:
        """
        ## ADX 与 DI 指标（平均方向指数 + 方向指标）

        ✈ https://cn.tradingview.com/script/VTPMMOrx-ADX-and-DI/

        Args:
            length: ADX 计算周期，默认 `14`
            **kwargs: 其他扩展参数

        Returns:
            包含 `ADX`（趋势强度）、`DIPlus`（正向方向指标）、`DIMinus`（负向方向指标）的指标数据
        """
        return ADX_and_DI(self._btdata, length=14, **kwargs)

    def Bollinger_RSI_Double_Strategy(self, RSIlength=6, RSIoverSold=50., RSIoverBought=50., BBlength=200, BBmult=2., **kwargs) -> dataframe:
        """
        ## 布林带 + RSI 双重策略

        ✈ https://cn.tradingview.com/script/uCV8I4xA-Bollinger-RSI-Double-Strategy-by-ChartArt-v1-1/

        Args:
            RSIlength: RSI 计算周期，默认 `6`
            RSIoverSold: RSI 超卖阈值，默认 `50.0`
            RSIoverBought: RSI 超买阈值，默认 `50.0`
            BBlength: 布林带计算周期，默认 `200`
            BBmult: 布林带乘数，默认 `2.0`
            **kwargs: 其他扩展参数

        Returns:
            包含 `BBupper`（布林带上轨）、`BBlower`（布林带下轨）、`long_signal`（多头信号）、`short_signal`（空头信号）的策略数据
        """
        return Bollinger_RSI_Double_Strategy(self._btdata, RSIlength=RSIlength, RSIoverSold=RSIoverSold, RSIoverBought=RSIoverBought,
                                             BBlength=BBlength, BBmult=BBmult, **kwargs)

    def Pivot_Point_Supertrend(self, prd=2, Factor=3, Pd=10, **kwargs) -> dataframe:
        """
        ## 枢轴点 + 超级趋势指标

        ✈ https://cn.tradingview.com/script/L0AIiLvH-Pivot-Point-Supertrend/

        Args:
            prd: 枢轴点计算周期相关参数，默认 `2`
            Factor: 超级趋势乘数，默认 `3`
            Pd: ATR 计算周期，默认 `10`
            **kwargs: 其他扩展参数

        Returns:
            包含 `Trailingsl`（跟踪止损线）、`long_signal`（多头信号）、`short_signal`（空头信号）的指标数据
        """
        return Pivot_Point_Supertrend(self._btdata, prd=prd, Factor=Factor, Pd=Pd, **kwargs)

    def AlphaTrend(self, coeff=1., AP=14, novolumedata=False, **kwargs) -> dataframe:
        """
        ## Alpha 趋势指标

        ✈ https://cn.tradingview.com/script/o50NYLAZ-AlphaTrend/

        Args:
            coeff: 系数参数，默认 `1.0`
            AP: ATR 计算周期，默认 `14`
            novolumedata: 布尔值，控制是否禁用成交量数据，默认 `False`
            **kwargs: 其他扩展参数

        Returns:
            包含 `AlphaTrend`（趋势线）、`AlphaTrend2`（延迟趋势线）、`long_signal`（多头信号）、`short_signal`（空头信号）的指标数据
        """
        return AlphaTrend(self._btdata, coeff=coeff, AP=AP, novolumedata=novolumedata, **kwargs)

    def Volume_Flow_Indicator(self, length=130, coef=0.2, vcoef=2.5, signalLength=5, smoothVFI=False, **kwargs) -> dataframe:
        """
        ## 成交量流量指标

        ✈ https://cn.tradingview.com/script/MhlDpfdS-Volume-Flow-Indicator-LazyBear/

        Args:
            length: 基础周期，默认 `130`
            coef: 系数参数，默认 `0.2`
            vcoef: 成交量系数，默认 `2.5`
            signalLength: 信号平滑周期，默认 `5`
            smoothVFI: 布尔值，控制是否平滑 VFI，默认 `False`
            **kwargs: 其他扩展参数

        Returns:
            包含 `vfima`（成交量流量指数移动平均）、`vfi`（成交量流量指标）的指标数据
        """
        return Volume_Flow_Indicator(self._btdata, length=length, coef=coef, vcoef=vcoef, signalLength=signalLength, smoothVFI=smoothVFI, **kwargs)

    def Chandelier_Exit(self, length=22, mult=3., useClose=True, **kwargs) -> dataframe:
        """
        ## 吊灯出场指标

        ✈ https://cn.tradingview.com/script/AqXxNS7j-Chandelier-Exit/

        Args:
            length: 周期参数，默认 `22`
            mult: ATR 乘数，默认 `3.0`
            useClose: 布尔值，控制是否用收盘价计算，默认 `True`
            **kwargs: 其他扩展参数

        Returns:
            包含 `up`（上轨止损线）、`dn`（下轨止损线）、`long_signal`（多头信号）、`short_signal`（空头信号）的指标数据
        """
        return Chandelier_Exit(self._btdata, length=length, mult=mult, useClose=useClose, **kwargs)

    def SuperTrend_STRATEGY(self, Periods=10, Multiplier=3., changeATR=True, **kwargs) -> dataframe:
        """
        ## 超级趋势策略

        ✈ https://cn.tradingview.com/script/P5Gu6F8k/

        Args:
            Periods: ATR 计算周期，默认 `10`
            Multiplier: ATR 乘数，默认 `3.0`
            changeATR: 布尔值，控制是否改变 ATR 计算方式，默认 `True`
            **kwargs: 其他扩展参数

        Returns:
            包含 `up`（上轨趋势线）、`dn`（下轨趋势线）、`long_signal`（多头信号）、`short_signal`（空头信号）的策略数据
        """
        return SuperTrend_STRATEGY(self._btdata, Periods=Periods, Multiplier=Multiplier, changeATR=changeATR, **kwargs)

    def Optimized_Trend_Tracker(self, length=2, var_length=9, percent=1.4, base=200, **kwargs) -> dataframe:
        """
        ## 优化的趋势跟踪指标

        ✈ https://cn.tradingview.com/script/zVhoDQME/

        Args:
            length: 基础周期，默认 `2`
            var_length: 变异周期，默认 `9`
            percent: 百分比参数，默认 `1.4`
            base: 基础参考值，默认 `200`
            **kwargs: 其他扩展参数

        Returns:
            包含 `MT`（主趋势线）、`OTT`（优化趋势跟踪线）的指标数据
        """
        return Optimized_Trend_Tracker(self._btdata, length=length, var_length=var_length, percent=percent, base=base, **kwargs)

    def TonyUX_EMA_Scalper(self, length=20, period=8, **kwargs) -> dataframe:
        """
        ## TonyUX EMA 剥头皮策略

        ✈ https://cn.tradingview.com/script/egfSfN1y-TonyUX-EMA-Scalper-Buy-Sell/

        Args:
            length: EMA 计算周期，默认 `20`
            period: 价格高低点统计周期，默认 `8`
            **kwargs: 其他扩展参数

        Returns:
            包含 `lasth`（近期高点）、`lastl`（近期低点）、`long_signal`（多头信号）、`short_signal`（空头信号）的策略数据
        """
        return TonyUX_EMA_Scalper(self._btdata, length=length, period=period, **kwargs)

    def Turtle_Trade_Channels_Indicator_TUTCI(self, length=20, len2=10, **kwargs) -> dataframe:
        """
        ## 海龟交易通道指标

        ✈ https://cn.tradingview.com/script/pB5nv16J/

        Args:
            length: 主通道周期，默认 `20`
            len2: 辅助通道周期，默认 `10`
            **kwargs: 其他扩展参数

        Returns:
            包含 `sup`（上通道）、`sdown`（下通道）、`K`（关键趋势线）、`long_signal`（多头信号）、`short_signal`（空头信号）的指标数据
        """
        return Turtle_Trade_Channels_Indicator_TUTCI(self._btdata, length=length, len2=len2, **kwargs)
