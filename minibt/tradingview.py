from .utils import Literal, np, pd, partial, reduce, get_lennan, MaType, FILED
from .indicators import BtIndicator, series, dataframe
import math


class Powertrend_Volume_Range_Filter_Strategy(BtIndicator):
    """✈  https://cn.tradingview.com/script/45FlB2qH-Powertrend-Volume-Range-Filter-Strategy-wbburgin/"""
    params = dict(length=200, mult=3., length_adx=14, lengthhl=14)
    overlap = True

    @staticmethod
    def smoothrng(x: series, t: int, m: float = 1.):
        """平滑平均范围"""
        wper = t*2 - 1
        avrng = (x - x.shift()).apply(abs).ema(t)
        smoothrng = m*avrng.ema(wper)
        return smoothrng

    @staticmethod
    def rngfilt_volumeadj(source: series, volume: series, sm: series):
        size = source.size
        up = source+sm
        dn = source-sm
        hband = up.values
        lowband = dn.values
        up = up.values
        dn = dn.values
        rngfilt = source.values
        volume = volume.values
        sm = sm.values
        nannum = len(sm[np.isnan(sm)])

        uprng = np.ones(size, dtype=np.float32)
        pre_high = up[nannum]
        pre_low = dn[nannum]
        for i in range(size):
            if i > nannum:
                # pre_rngfilt = rngfilt[i-1]
                # y = pre_rngfilt if dn[i] < pre_rngfilt else dn[i]
                # z = pre_rngfilt if up[i] > pre_rngfilt else up[i]
                # rngfilt[i] = y if source[i] > pre_rngfilt else z
                if volume[i] > volume[i-1]:
                    rngfilt[i] = rngfilt[i-1] if dn[i] < rngfilt[i-1] else dn[i]
                else:
                    rngfilt[i] = rngfilt[i-1] if up[i] > rngfilt[i-1] else up[i]

                up_, dn_ = rngfilt[i]+sm[i], rngfilt[i]-sm[i]
                if uprng[i-1] > 0.:
                    low = max([pre_low, dn_])
                    lowband[i] = low
                    if rngfilt[i] < low:
                        uprng[i] = -1.
                        hband[i] = up[i]
                        pre_high = up[i]
                    else:
                        uprng[i] = 1.
                        hband[i] = np.nan
                        pre_low = low
                elif uprng[i-1] < 0.:
                    high = min([pre_high, up_])
                    hband[i] = high
                    if rngfilt[i] > high:
                        uprng[i] = 1.
                        lowband[i] = dn[i]
                        pre_low = dn[i]
                    else:
                        uprng[i] = -1.
                        lowband[i] = np.nan
                        pre_high = high
        return uprng, rngfilt, lowband, hband

    @staticmethod
    def _rngfilt_volumeadj(x: series, volume: series, r: series):
        _add = (x+r).values
        _diff = (x-r).values
        x = x.values
        m = len(_add[pd.isna(_add)])
        rngfilt = np.array([np.nan]*m)
        rngfilt = np.insert(rngfilt, m, x[m])
        dir = np.array([np.nan]*m)
        dir = np.insert(dir, m, 1.)
        # lennan = max(len(x[isnan(x)]), len(r[isnan(r)]))
        for i in range(m+1, x.size):
            pre_rngfilt = rngfilt[i-1]
            add, diff = _add[i], _diff[i]
            # 向上突破时时候保持收盘价与目标线在一个r值距离，如果收盘价上涨小于r值，则没突破，维持原值
            # y = pre_rngfilt if diff < pre_rngfilt else diff
            # 向下突破时时候保持收盘价与目标线在一个r值距离，如果收盘价下跌小于r值，则没突破，维持原值
            z = pre_rngfilt if add > pre_rngfilt else add
            # 收盘价在前一值之上，则有可能向上突破，则取y，之下则有可能向下突破，取z
            if volume[i] > volume[i-1]:
                next_rngfilt = rngfilt[i -
                                       1] if _diff[i] < rngfilt[i-1] else _diff[i]
            else:
                next_rngfilt = rngfilt[i -
                                       1] if _add[i] > rngfilt[i-1] else _add[i]
            pre_dir = dir[i-1]
            # next_rngfilt = y if x[i] > pre_rngfilt else z
            next_dir = pre_dir if pre_rngfilt == next_rngfilt else (
                1. if next_rngfilt > pre_rngfilt else -1.)
            rngfilt = np.insert(rngfilt, i, next_rngfilt)
            dir = np.insert(dir, i, next_dir)
        return pd.Series(rngfilt), pd.Series(dir)

    def next(self):
        sm = self.smoothrng(self.close, self.params.length, self.params.mult)
        volrng, dir = self._rngfilt_volumeadj(
            self.close, self.volume, sm)
        hband: series = volrng + sm
        lowband: series = volrng - sm

        adx = self.adx(self.params.length_adx).adxx
        adx_vwma = adx.vwma(self.params.length_adx)
        adx_filter = adx > adx_vwma

        vwma = self.vwma(close=volrng, length=self.params.length)
        vwma_filter_positive = volrng > vwma

        lowband_trendfollow = lowband.tqfunc.llv(
            self.params.lengthhl)
        highband_trendfollow = hband.tqfunc.hhv(self.params.lengthhl)
        x = self.close.cross_up(highband_trendfollow.shift()).tqfunc.barlast()
        in_general_uptrend = x < self.close.cross_down(
            lowband_trendfollow.shift()).tqfunc.barlast()
        in_general_uptrend = in_general_uptrend.astype(np.int8)

        long_signal = dir.astype(bool)
        long_signal &= self.close.cross_up(hband)
        long_signal &= in_general_uptrend
        long_signal &= adx_filter
        long_signal &= vwma_filter_positive
        hband = hband.where(dir < 0.)
        lowband = lowband.where(dir > 0.)

        return volrng, hband, lowband  # , long_signal


class Nadaraya_Watson_Envelope_Strategy(BtIndicator):
    """✈ https://cn.tradingview.com/script/HrZicISx-Nadaraya-Watson-Envelope-Strategy-Non-Repainting-Log-Scale/"""
    params = dict(h=8., x=25., length=60, alpha=8.)
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
        close = close.values[::-1]
        sumXWeights = 0.
        sumWeights = 0.
        for i in range(size):
            weight = weights[i]
            sumWeights += weight
            sumXWeights += weight * close[i]
        return sumXWeights / sumWeights

    def next(self):
        x = self.params.x
        h = int(self.params.h)
        alpha = self.params.alpha
        weights = self.get_weight(x=x, alpha=alpha, h=h)
        func = partial(self.customKernel, weights=weights)
        customEnvelopeClose = self.close.rolling(
            h).apply(func)
        customEnvelopeHigh = self.high.rolling(
            h).apply(func)
        customEnvelopeLow = self.low.rolling(
            h).apply(func)

        long_signal = self.close.cross_up(customEnvelopeLow)
        exitlong_signal = self.close.cross_down(customEnvelopeHigh)

        short_signal = exitlong_signal
        exitshort_signal = long_signal
        return customEnvelopeClose, customEnvelopeHigh, customEnvelopeLow, long_signal, exitlong_signal, short_signal, exitshort_signal


class G_Channels(BtIndicator):
    """✈ https://www.tradingview.com/script/fIvlS64B-G-Channels-Efficient-Calculation-Of-Upper-Lower-Extremities/"""
    params = dict(length=144., cycle=1)
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

        # exitlong_signal = self.close.cross(b, above=False).tqfunc.barlast(
        # ) <= self.close.cross(a, above=False).tqfunc.barlast()
        # long_signal = ~exitlong_signal
        # short_signal=exitlong_signal
        # exitshort_signal=long_signal
        # , long_signal, exitlong_signal,short_signal,exitshort_signal
        return a, b, avg  # , zig


class STD_Filtered(BtIndicator):
    """✈ https://cn.tradingview.com/script/i4xZNAoy-STD-Filtered-N-Pole-Gaussian-Filter-Loxx/"""
    params = dict(period=25, order=5, filterperiod=10, filter=1.6185)
    overlap = True

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
        filt = pd.Series(filt)
        sig = filt.shift()
        long_signal = filt > sig
        long_signal &= (filt.shift() < sig.shift()) | (
            filt.shift() == sig.shift())
        short_signal = filt < sig
        short_signal &= (filt.shift() > sig.shift()) | (
            filt.shift() == sig.shift())

        return out, filt, long_signal, short_signal


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
    params = dict(len=10, mom_rsi_val=50, atrPeriod=10,
                  factor=3., AP2=12, AF2=.1618)

    def next(self):
        src2 = self.close
        mom = src2 - src2.shift(self.params.len)
        rsi_mom = mom.rsi(self.params.len)

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
                                        1] and 1. or (Trail2[i] < Trail2[i-1] and -1 or Trail2[i-1])

        long_signal = Trail1 > Trail2
        long_signal &= direction < 0.
        # long_signal &= rsi_mom > self.params.mom_rsi_val
        exitlong_signal = dir < 0.
        short_signal = Trail1 < Trail2
        short_signal &= direction > 0.
        # short_signal &= rsi_mom > self.params.mom_rsi_val
        exitshort_signal = dir > 0.

        return supertrend, Trail2, long_signal, short_signal, exitlong_signal, exitshort_signal


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


class PMax_Explorer_STRATEGY(BtIndicator):
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
