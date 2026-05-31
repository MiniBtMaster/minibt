from ..utils import np, pd, partial, reduce, get_lennan, LineStyle, LineDash
from ._core import BtIndicator, IndSeries, IndFrame, KLine,Line
from ..stop import BtStop
import math


class Powertrend_Volume_Range_Filter_Strategy(BtIndicator):
    """✈  Powertrend Volume Range Filter Strategy

    来源: https://cn.tradingview.com/script/45FlB2qH-Powertrend-Volume-Range-Filter-Strategy-wbburgin/

    该策略基于成交量调整的范围过滤器，结合ADX和VWMA指标来生成交易信号

    参数:
    ----------
    l : int, 默认200
        平滑范围的长度
    lengthvwma : int, 默认200
        VWMA（成交量加权移动平均）的长度
    mult : float, 默认3.0
        平滑范围的乘数
    lengthadx : int, 默认200
        ADX（平均趋向指标）的长度
    lengthhl : int, 默认14
        高低带趋势跟随的长度
    useadx : bool, 默认False
        是否使用ADX过滤器
    usehl : bool, 默认False
        是否使用高低带过滤器
    usevwma : bool, 默认False
        是否使用VWMA过滤器
    highlighting : bool, 默认True
        是否高亮显示信号

    返回:
    ----------
    volrng : IndSeries
        成交量调整的范围过滤器
    hband : IndSeries
        上带
    lowband : IndSeries
        下带
    dir : np.ndarray
        方向指标
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
    params = dict(l=200, lengthvwma=200, mult=3., lengthadx=200, lengthhl=14,
                  useadx=False, usehl=False, usevwma=False, highlighting=True)
    overlap = dict(volrng=True, hband=True, lowband=True, dir=False)

    @staticmethod
    def smoothrng(x: IndSeries, t: int, m: float = 1.):
        """计算平滑平均范围

        参数:
        ----------
        x : IndSeries
            输入序列
        t : int
            计算长度
        m : float, 默认1.0
            乘数

        返回:
        ----------
        IndSeries
            平滑后的平均范围
        """
        wper = t*2 - 1
        avrng = (x - x.shift()).abs().ema(t)
        smoothrng = m*avrng.ema(wper)
        return smoothrng

    def _rngfilt_volumeadj(self, source1: IndSeries, tethersource: IndSeries, smoothrng: IndSeries):
        """成交量调整的范围过滤器

        参数:
        ----------
        source1 : IndSeries
            源序列
        tethersource : IndSeries
            绑定源序列（通常是成交量）
        smoothrng : IndSeries
            平滑范围

        返回:
        ----------
        tuple
            (范围过滤器, 方向指标)
        """
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
        return IndSeries(rngfilt, lines=["rngfilt"]), dir

    def next(self):
        """计算指标和信号

        返回:
        ----------
        tuple
            (volrng, hband, lowband, dir, long_signal, short_signal)
        """
        smoothrng = self.smoothrng(self.close, self.params.l, self.params.mult)
        volrng, dir = self._rngfilt_volumeadj(
            self.close, self.volume, smoothrng)
        hband = volrng + smoothrng
        lowband = volrng - smoothrng

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
    """✈ Nadaraya-Watson 包络线策略

    来源: https://cn.tradingview.com/script/HrZicISx-Nadaraya-Watson-Envelope-Strategy-Non-Repainting-Log-Scale/

    该策略使用 Nadaraya-Watson 核回归方法创建非重绘的包络线，用于识别市场趋势和交易信号

    参数:
    ----------
    customLookbackWindow : float, 默认8.0
        自定义回看窗口
    customRelativeWeighting : float, 默认8.0
        自定义相对权重
    customStartRegressionBar : float, 默认25.0
        自定义回归起始柱
    length : int, 默认60
        周期长度
    customATRLength : int, 默认60
        自定义ATR周期长度
    customNearATRFactor : float, 默认1.5
        近端ATR因子
    customFarATRFactor : float, 默认2.0
        远端ATR因子

    返回:
    ----------
    customEnvelopeClose : IndSeries
        收盘价的包络线
    customEnvelopeHigh : IndSeries
        最高价的包络线
    customEnvelopeLow : IndSeries
        最低价的包络线
    customUpperNear : IndSeries
        近端上轨
    customUpperFar : IndSeries
        远端上轨
    customUpperAvg : IndSeries
        平均上轨
    customLowerNear : IndSeries
        近端下轨
    customLowerFar : IndSeries
        远端下轨
    customLowerAvg : IndSeries
        平均下轨
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
    params = dict(customLookbackWindow=8., customRelativeWeighting=8., customStartRegressionBar=25.,
                  length=60, customATRLength=60, customNearATRFactor=1.5, customFarATRFactor=2.)
    overlap = True

    def get_weight(self, x=0, alpha=0, h=0) -> tuple[np.ndarray]:
        """计算权重数组

        参数:
        ----------
        x : float, 默认0
            参考点
        alpha : float, 默认0
            相对权重参数
        h : int, 默认0
            窗口长度

        返回:
        ----------
        np.ndarray
            权重数组
        """
        weights = np.zeros(h)
        for i in range(h):
            weights[i] = np.power(
                1. + (np.power((x - i), 2.) / (2. * alpha * h * h)), -alpha)
        return weights

    @staticmethod
    def customKernel(close: pd.Series, weights=None) -> float:
        """自定义核函数计算

        参数:
        ----------
        close : pd.Series
            收盘价序列
        weights : np.ndarray, 默认None
            权重数组

        返回:
        ----------
        float
            核回归计算结果
        """
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
    def customATR(length, _high, _low, _close) -> IndSeries:
        """计算自定义ATR

        参数:
        ----------
        length : int
            ATR周期长度
        _high : IndSeries
            最高价序列
        _low : IndSeries
            最低价序列
        _close : IndSeries
            收盘价序列

        返回:
        ----------
        IndSeries
            ATR序列
        """
        df = IndFrame(dict(high=_high, low=_low, close=_close))
        tr = df.true_range()
        return tr.rma(length)

    @staticmethod
    def getEnvelopeBounds(_atr, _nearFactor, _farFactor, _envelope):
        """计算包络线边界

        参数:
        ----------
        _atr : IndSeries
            ATR序列
        _nearFactor : float
            近端因子
        _farFactor : float
            远端因子
        _envelope : IndSeries
            包络线基础值

        返回:
        ----------
        tuple
            (近端上轨, 远端上轨, 平均上轨, 近端下轨, 远端下轨, 平均下轨)
        """
        _upperFar = _envelope + _farFactor*_atr
        _upperNear = _envelope + _nearFactor*_atr
        _lowerNear = _envelope - _nearFactor*_atr
        _lowerFar = _envelope - _farFactor*_atr
        _upperAvg = (_upperFar + _upperNear) / 2
        _lowerAvg = (_lowerFar + _lowerNear) / 2
        return _upperNear, _upperFar, _upperAvg, _lowerNear, _lowerFar, _lowerAvg

    def next(self):
        """计算指标和信号

        返回:
        ----------
        tuple
            (customEnvelopeClose, customEnvelopeHigh, customEnvelopeLow, customUpperNear, customUpperFar,
             customUpperAvg, customLowerNear, customLowerFar, customLowerAvg, long_signal, short_signal)
        """
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
    """✈ G通道指标 - 高效计算上下极值点

    来源: https://www.tradingview.com/script/fIvlS64B-G-Channels-Efficient-Calculation-Of-Upper-Lower-Extremities/

    该指标使用高效算法计算价格的上下极值点，形成通道，用于识别市场趋势和潜在的反转点

    参数:
    ----------
    length : float, 默认144.0
        通道长度参数，控制通道的宽度和敏感度
    cycle : int, 默认1
        周期参数，控制计算极值点的频率
    thresh : float, 默认0.0
        之字转向阈值，当值在0到1之间时启用之字转向线

    返回:
    ----------
    a : IndSeries
        上轨线
    b : IndSeries
        下轨线
    avg : IndSeries
        中轨线（上下轨的平均值）
    zig : IndSeries, 可选
        之字转向线，当thresh在0到1之间时返回
    """
    params = dict(length=144., cycle=1, thresh=0.)
    overlap = True

    def next(self):
        """计算G通道指标

        返回:
        ----------
        无直接返回值，结果通过self.lines属性设置
            - self.lines.a: 上轨线
            - self.lines.b: 下轨线
            - self.lines.avg: 中轨线
            - self.lines.zig: 之字转向线（当thresh在0到1之间时）
        """
        length = self.params.length
        cycle = max(int(self.params.cycle), 1)
        size = self.close.size
        a = self.full()  # 上轨线
        b = self.full()  # 下轨线
        close = self.close.values
        pre_a = 0.  # 前一个上轨值
        pre_b = 0.  # 前一个下轨值

        # 计算上下轨线
        for i in range(size):
            if i and i % cycle == 0:
                a[i] = max(close[i], pre_a) - (pre_a - pre_b) / length
                b[i] = min(close[i], pre_b) + (pre_a - pre_b) / length
                pre_a = a[i]
                pre_b = b[i]

        # 如果周期大于1，进行插值处理
        if cycle > 1:
            a = a.interpolate()
            b = b.interpolate()

        # 计算中轨线
        avg = (a + b) / 2.

        # 方法1：通过lines属性设置结果
        self.lines.a = a
        self.lines.b = b
        self.lines.avg = avg

        # 如果设置了有效的thresh值，添加之字转向线
        if 0. < self.params.thresh < 1.:
            self.lines.zig = self.btind.zigzag_full(self.params.thresh)

        # # 方法2：直接返回结果
        # if 0. < self.params.thresh < 1.:
        #     zig = self.btind.zigzag_full(self.params.thresh)
        #     return a,b,avg,zig
        # return a,b,avg


class STD_Filtered(BtIndicator):
    """✈ STD过滤N极高斯滤波器

    来源: https://cn.tradingview.com/script/i4xZNAoy-STD-Filtered-N-Pole-Gaussian-Filter-Loxx/

    该指标使用N极高斯滤波器对价格数据进行平滑处理，并结合标准差过滤来减少噪声，用于识别趋势和生成交易信号

    参数:
    ----------
    period : int, 默认25
        主周期参数，用于计算高斯滤波器
    order : int, 默认5
        滤波器阶数，控制滤波器的平滑程度
    filterperiod : int, 默认10
        标准差过滤的周期
    filter : float, 默认1.0
        标准差过滤的阈值

    返回:
    ----------
    filt : IndSeries
        过滤后的信号线
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
    params = dict(period=25, order=5, filterperiod=10, filter=1.)
    overlap = dict(out=True, filt=True)  # , dir=False)

    @staticmethod
    def fact(n: int) -> float:
        """计算阶乘

        参数:
        ----------
        n : int
            要计算阶乘的整数

        返回:
        ----------
        float
            n的阶乘
        """
        if n < 2:
            return 1.
        return float(reduce(lambda x, y: x*y, range(1, n+1)))

    @staticmethod
    def alpha(period, poles):
        """计算alpha值

        参数:
        ----------
        period : int
            周期参数
        poles : int
            极点数量

        返回:
        ----------
        float
            计算得到的alpha值
        """
        w = 2.0 * math.pi / period
        b = (1.0 - math.cos(w)) / (math.pow(1.414, 2.0 / poles) - 1.0)
        a = - b + math.sqrt(b * b + 2.0 * b)
        return a

    def makeCoeffs(self, period, order):
        """生成滤波器系数

        参数:
        ----------
        period : int
            周期参数
        order : int
            滤波器阶数

        返回:
        ----------
        np.ndarray
            滤波器系数矩阵
        """
        coeffs = np.full((order+1, 3), 0.)
        a = self.alpha(period, order)
        for i in range(order+1):
            div = self.fact(order - i) * self.fact(i)
            out = self.fact(order) / div if div else 1.
            coeffs[i, :] = [out, math.pow(a, i), math.pow(1.0 - a, i)]
        return coeffs

    @staticmethod
    def npolegf(src: np.ndarray, order: int = 0, coeffs: np.ndarray = None):
        """计算N极点高斯滤波器

        参数:
        ----------
        src : np.ndarray
            输入数据源
        order : int, 默认0
            滤波器阶数
        coeffs : np.ndarray, 默认None
            滤波器系数矩阵

        返回:
        ----------
        np.ndarray
            滤波后的结果
        """
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
    def std_filter(out: IndSeries, length: int, filter: float):
        """标准差过滤

        参数:
        ----------
        out : IndSeries
            输入序列
        length : int
            计算标准差的周期
        filter : float
            过滤阈值

        返回:
        ----------
        np.ndarray
            过滤后的结果
        """
        std = out.stdev(length).values
        filtdev = filter * std
        nanlen = len(std[np.isnan(std)])
        filt = np.array(out.values)
        for i in range(nanlen+1, out.size):
            if abs(filt[i]-filt[i-1]) < filtdev[i]:
                filt[i] = filt[i-1]
        return filt

    def next(self):
        """计算指标和信号

        返回:
        ----------
        tuple
            (filt, long_signal, short_signal)
                - filt: 过滤后的信号线
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        # 生成滤波器系数
        coeffs = self.makeCoeffs(self.params.period, self.params.order)

        # 使用Heikin-Ashi收盘价作为数据源
        src = self.ha().close
        # src = self.ohlc4()

        # 对数据源进行标准差过滤
        src = self.std_filter(
            src, self.params.filterperiod, self.params.filter)

        # 应用N极点高斯滤波器
        out = self.npolegf(src, order=self.params.order, coeffs=coeffs)
        filt = IndSeries(out, name="filt")

        # 再次对过滤结果进行标准差过滤
        filt = self.std_filter(
            filt, self.params.filterperiod, self.params.filter)

        # 生成交易信号
        _filt = pd.Series(filt)
        sig = _filt.shift()
        long_signal = _filt > sig
        long_signal &= (_filt.shift() < sig.shift()) | (
            _filt.shift() == sig.shift())
        short_signal = _filt < sig
        short_signal &= (_filt.shift() > sig.shift()) | (
            _filt.shift() == sig.shift())

        # 计算连续信号
        size = self.V
        contsw = np.zeros(size)
        for i in range(size):
            contsw[i] = long_signal[i] and 1 or (
                short_signal[i] and -1 or contsw[i-1])
        contsw = pd.Series(contsw)

        # 过滤信号，只保留趋势反转时的信号
        long_signal &= contsw.shift() == -1
        short_signal &= contsw.shift() == 1

        return filt, long_signal, short_signal


class Turtles_strategy(BtIndicator):
    """✈ 海龟交易策略 - 历经20年验证的有效策略

    来源: https://cn.tradingview.com/script/Q1O23zJP-20-years-old-turtles-strategy-still-work/

    该策略基于理查德·丹尼斯和威廉·埃克哈特的海龟交易法则，使用突破系统进行交易，包含快速和慢速两个时间周期

    参数:
    ----------
    enter_fast : int, 默认20
        快速周期的入场通道长度
    exit_fast : int, 默认10
        快速周期的出场通道长度
    enter_slow : int, 默认55
        慢速周期的入场通道长度
    exit_slow : int, 默认20
        慢速周期的出场通道长度

    返回:
    ----------
    long_signal : np.ndarray
        多头入场信号
    short_signal : np.ndarray
        空头入场信号
    exitlong_signal : np.ndarray
        多头出场信号
    exitshort_signal : np.ndarray
        空头出场信号
    """
    params = dict(enter_fast=20, exit_fast=10, enter_slow=55, exit_slow=20)

    def next(self):
        """计算海龟交易策略信号

        返回:
        ----------
        tuple
            (long_signal, short_signal, exitlong_signal, exitshort_signal)
                - long_signal: 多头入场信号
                - short_signal: 空头入场信号
                - exitlong_signal: 多头出场信号
                - exitshort_signal: 空头出场信号
        """
        # 计算快速周期的高低点
        fastL = self.high.tqfunc.hhv(self.params.enter_fast)  # 快速周期高点
        fastLC = self.low.tqfunc.llv(self.params.exit_fast)  # 快速周期低点（用于出场）
        fastS = self.low.tqfunc.llv(self.params.enter_fast)  # 快速周期低点
        fastSC = self.high.tqfunc.hhv(self.params.exit_fast)  # 快速周期高点（用于出场）

        # 计算慢速周期的高低点
        slowL = self.high.tqfunc.hhv(self.params.enter_slow)  # 慢速周期高点
        slowLC = self.low.tqfunc.llv(self.params.exit_slow)  # 慢速周期低点（用于出场）
        slowS = self.low.tqfunc.llv(self.params.enter_slow)  # 慢速周期低点
        slowSC = self.high.tqfunc.hhv(self.params.exit_slow)  # 慢速周期高点（用于出场）

        # 生成快速周期信号
        long_signal = self.high > fastL.shift()  # 突破快速周期高点，产生多头信号
        exitlong_signal = self.low <= fastLC.shift()  # 跌破快速周期低点，产生多头出场信号
        short_signal = self.low < fastS.shift()  # 跌破快速周期低点，产生空头信号
        exitshort_signal = self.high >= fastSC.shift()  # 突破快速周期高点，产生空头出场信号

        # 结合慢速周期信号
        long_signal |= self.high > slowL.shift()  # 突破慢速周期高点，产生多头信号
        exitlong_signal |= self.low <= slowLC.shift()  # 跌破慢速周期低点，产生多头出场信号
        short_signal |= self.low < slowS.shift()  # 跌破慢速周期低点，产生空头信号
        exitshort_signal |= self.high >= slowSC.shift()  # 突破慢速周期高点，产生空头出场信号

        return long_signal, short_signal, exitlong_signal, exitshort_signal


class Adaptive_Trend_Filter(BtIndicator):
    """✈ 自适应趋势过滤器

    来源: https://cn.tradingview.com/script/PhSlALob-Adaptive-Trend-Filter-tradingbauhaus/

    该指标使用自适应滤波器对价格数据进行平滑处理，并结合超级趋势指标来识别趋势方向和生成交易信号

    参数:
    ----------
    alphaFilter : float, 默认0.01
        自适应滤波器的alpha参数，控制滤波器的敏感度
    betaFilter : float, 默认0.1
        自适应滤波器的beta参数，控制方差的更新速度
    filterPeriod : int, 默认21
        滤波器的周期参数
    supertrendFactor : int, 默认1
        超级趋势指标的因子参数
    supertrendAtrPeriod : int, 默认7
        超级趋势指标的ATR周期

    返回:
    ----------
    filteredValue : IndSeries
        自适应滤波后的价格值
    supertrendValue : np.ndarray
        超级趋势值
    trendDirection : pd.Series
        趋势方向（1为多头，-1为空头）
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
    params = dict(alphaFilter=0.01, betaFilter=0.1, filterPeriod=21,
                  supertrendFactor=1, supertrendAtrPeriod=7)
    overlap = dict(filteredValue=True, supertrendValue=True,
                   trendDirection=False)

    def adaptiveFilter(self, b, alpha, beta):
        """自适应滤波器函数

        参数:
        ----------
        b : int
            滤波器周期
        alpha : float
            alpha参数
        beta : float
            beta参数

        返回:
        ----------
        IndSeries
            滤波后的价格序列
        """
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

        return IndSeries(estimation)

    def supertrendFunc(self, src: IndSeries, factor: float, atrPeriod: int):
        """超级趋势函数

        参数:
        ----------
        src : IndSeries
            输入序列（通常是滤波后的价格）
        factor : float
            超级趋势因子
        atrPeriod : int
            ATR周期

        返回:
        ----------
        tuple
            (superTrend, direction)
                - superTrend: 超级趋势值
                - direction: 趋势方向
        """
        atr = self.atr(atrPeriod)
        upperBand = src + factor * atr
        lowerBand = src - factor * atr
        size = src.size
        src = src.values
        upperBand, lowerBand = upperBand.values.copy(), lowerBand.values.copy()
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
                direction[i] = src[i] > upperBand[i] and 1 or -1
            else:
                direction[i] = src[i] < lowerBand[i] and -1 or 1
            superTrend[i] = direction[i] == \
                1. and lowerBand[i] or upperBand[i]
        return superTrend, direction

    def next(self):
        """计算指标和信号

        返回:
        ----------
        tuple
            (filteredValue, supertrendValue, trendDirection, long_signal, short_signal)
                - filteredValue: 自适应滤波后的价格值
                - supertrendValue: 超级趋势值
                - trendDirection: 趋势方向
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        # 应用自适应滤波器
        filteredValue = self.adaptiveFilter(
            self.params.filterPeriod, self.params.alphaFilter, self.params.betaFilter)

        # 应用超级趋势指标
        supertrendValue, trendDirection = self.supertrendFunc(
            filteredValue, self.params.supertrendFactor, self.params.supertrendAtrPeriod)

        # 转换为Series以便后续处理
        trendDirection = pd.Series(trendDirection)

        # 生成交易信号
        long_signal = trendDirection == 1
        long_signal &= trendDirection.shift() == -1  # 只在趋势反转时产生信号
        short_signal = trendDirection == -1
        short_signal &= trendDirection.shift() == 1  # 只在趋势反转时产生信号

        return filteredValue, supertrendValue, trendDirection, long_signal, short_signal


class DCA_Strategy_with_Mean_Reversion_and_Bollinger_Band(BtIndicator):
    """✈ 均值回归与布林带结合的DCA策略

    来源: https://cn.tradingview.com/script/uVaU9LVC-DCA-Strategy-with-Mean-Reversion-and-Bollinger-Band/

    该策略结合了均值回归和布林带技术，用于DCA（定投）策略中识别买入和卖出时机

    参数:
    ----------
    length : int, 默认14
        布林带周期长度
    mult : float, 默认2.0
        布林带标准差乘数

    返回:
    ----------
    upper : IndSeries
        布林带上轨
    lower : IndSeries
        布林带下轨
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """

    params = dict(length=14, mult=2.)
    overlap = True

    def next(self):
        """计算指标和信号

        返回:
        ----------
        tuple
            (upper, lower, long_signal, short_signal)
                - upper: 布林带上轨
                - lower: 布林带下轨
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        # 计算T3移动平均作为布林带中轨
        basis = self.close.t3(self.params.length)
        # 计算布林带标准差
        bb_dev = self.params.mult * self.close.stdev(self.params.length)
        # 计算布林带上轨和下轨
        upper = basis + bb_dev
        lower = basis - bb_dev
        # 生成多头信号：价格上穿下轨且价格上涨
        long_signal = self.close.cross_up(lower) & (
            self.close > self.close.shift())
        # 生成空头信号：价格下穿上轨且价格下跌
        short_signal = self.close.cross_down(
            upper) & (self.close < self.close.shift())
        return upper, lower, long_signal, short_signal


class Multi_Step_Vegas_SuperTrend_strategy(BtIndicator):
    """✈ 多步维加斯超级趋势策略

    来源: https://cn.tradingview.com/script/SXtas3lS-Multi-Step-Vegas-SuperTrend-strategy-presentTrading/

    该策略结合了维加斯通道和超级趋势指标，根据市场波动性自动调整超级趋势的乘数，提高趋势识别的准确性

    参数:
    ----------
    atrPeriod : int, 默认10
        ATR周期长度
    vegasWindow : int, 默认100
        维加斯通道的窗口长度
    superTrendMultiplier : int, 默认5
        超级趋势的基础乘数
    volatilityAdjustment : int, 默认5
        波动性调整参数
    matype : str, 默认"jma"
        移动平均类型

    返回:
    ----------
    superTrend : np.ndarray
        超级趋势线
    marketTrend : np.ndarray
        市场趋势（1为多头，-1为空头）
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
    params = dict(atrPeriod=10, vegasWindow=100,
                  superTrendMultiplier=5, volatilityAdjustment=5, matype="jma")
    overlap = dict(superTrend=True, marketTrend=False)

    def next(self):
        """计算指标和信号

        返回:
        ----------
        tuple
            (superTrend, marketTrend, long_signal, short_signal)
                - superTrend: 超级趋势线
                - marketTrend: 市场趋势
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        # 计算维加斯移动平均
        vegasMovingAverage: IndSeries = getattr(
            self.close, self.params.matype)(self.params.vegasWindow)
        # 计算维加斯通道的标准差
        vegasChannelStdDev = self.close.stdev(self.params.vegasWindow)

        # 计算维加斯通道的上下轨
        vegasChannelUpper = vegasMovingAverage + vegasChannelStdDev
        vegasChannelLower = vegasMovingAverage - vegasChannelStdDev

        # 根据维加斯通道的宽度调整超级趋势乘数
        channelVolatilityWidth = vegasChannelUpper - vegasChannelLower
        adjustedMultiplier = self.params.superTrendMultiplier + \
            self.params.volatilityAdjustment * \
            (channelVolatilityWidth / vegasMovingAverage)

        # 计算超级趋势指标值
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

        # 更新超级趋势值并确定当前趋势方向
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

        # 生成交易信号
        long_signal = marketTrend == 1
        long_signal &= np.append([0], marketTrend[:-1]) == -1  # 只在趋势反转时产生信号
        short_signal = marketTrend == -1
        short_signal &= np.append([0], marketTrend[:-1]) == 1  # 只在趋势反转时产生信号
        return superTrend, marketTrend, long_signal, short_signal


class The_Flash_Strategy(BtIndicator):
    """✈ Flash策略 - 动量RSI与EMA交叉结合ATR

    来源: https://cn.tradingview.com/script/XKgLfo15-The-Flash-Strategy-Momentum-RSI-EMA-crossover-ATR/

    该策略结合了动量RSI、EMA交叉和ATR指标，用于识别市场趋势和生成交易信号

    参数:
    ----------
    length : int, 默认10
        RSI周期长度
    mom_rsi_val : int, 默认50
        动量RSI阈值
    atrPeriod : int, 默认10
        ATR周期长度
    factor : float, 默认3.0
        超级趋势因子
    AP2 : int, 默认12
        自适应周期参数2
    AF2 : float, 默认0.1618
        自适应因子2

    返回:
    ----------
    supertrend : IndSeries
        超级趋势线
    Trail2 : np.ndarray
        跟踪止损线2
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
    overlap = True
    params = dict(length=10, mom_rsi_val=50, atrPeriod=10,
                  factor=3., AP2=12, AF2=.1618)

    def next(self):
        """计算指标和信号

        返回:
        ----------
        tuple
            (supertrend, Trail2, long_signal, short_signal)
                - supertrend: 超级趋势线
                - Trail2: 跟踪止损线2
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        # 计算动量
        src2 = self.close
        mom: IndSeries = src2 - src2.shift(self.params.length)
        # 计算动量RSI
        rsi_mom = mom.rsi(self.params.length)
        # 计算超级趋势
        supertrend, direction, * \
            _ = self.supertrend(self.params.atrPeriod,
                                    self.params.factor).to_lines()
        # 计算跟踪止损线
        src = self.close
        Trail1 = src.ema(self.params.AP2).values  # Ema func
        AF2 = self.params.AF2 / 100.
        SL2 = Trail1 * AF2  # Stoploss Ema
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
        # 转换为Series以便后续处理
        dir = pd.Series(dir)
        # 生成交易信号
        long_signal = dir > 0
        long_signal &= dir.shift() < 0  # 只在趋势反转时产生信号
        short_signal = dir < 0
        short_signal &= dir.shift() > 0  # 只在趋势反转时产生信号

        return supertrend, Trail2, long_signal, short_signal


class Quantum_Edge_Pro_Adaptive_AI(BtIndicator):
    """✈ 量子边缘专业自适应AI策略

    来源: https://cn.tradingview.com/script/iGZZmHEo-Quantum-Edge-Pro-Adaptive-AI/

    该策略使用自适应AI技术，结合市场结构分析、动量指标和成交量分析，生成综合加权评分以识别交易机会

    参数:
    ----------
    TICK_SIZE : float, 默认0.25
        最小变动价位
    POINT_VALUE : int, 默认2
        点值
    DOLLAR_PER_POINT : int, 默认2
        每点美元价值
    LEARNING_PERIOD : int, 默认40
        学习周期
    ADAPTATION_SPEED : float, 默认0.3
        适应速度
    PERFORMANCE_MEMORY : int, 默认200
        性能记忆周期
    BASE_MIN_SCORE : int, 默认2
        基础最小分数
    BASE_BARS_BETWEEN : int, 默认9
        基础间隔柱数
    MAX_DAILY_TRADES : int, 默认50
        最大日交易次数

    返回:
    ----------
    weighted_score : np.ndarray
        加权评分信号
    """

    params = dict(TICK_SIZE=0.25, POINT_VALUE=2, DOLLAR_PER_POINT=2, LEARNING_PERIOD=40, ADAPTATION_SPEED=0.3,
                  PERFORMANCE_MEMORY=200, BASE_MIN_SCORE=2, BASE_BARS_BETWEEN=9, MAX_DAILY_TRADES=50)
    overlap = False

    def _vars(self):
        """初始化变量

        定义策略所需的各种参数和权重
        """
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

    def MARKET_STRUCTURE_ANALYSIS(self) -> tuple[IndSeries]:
        """市场结构分析

        分析市场的支撑阻力位和突破情况

        返回:
        ----------
        tuple
            (bullish_break, bearish_break)
                - bullish_break: 看涨突破信号
                - bearish_break: 看跌突破信号
        """
        swing_high = self.high.shift().tqfunc.hhv(20)  # 计算20周期高点
        swing_low = self.low.shift().tqfunc.llv(20)  # 计算20周期低点
        bullish_break = (self.close > swing_high) & (
            self.close.shift() <= swing_high)  # 突破高点的看涨信号
        bearish_break = (self.close < swing_low) & (
            self.close.shift() >= swing_low)  # 突破低点的看跌信号
        return bullish_break, bearish_break

    def MOMENTUM_INDICATORS(self) -> tuple[IndSeries]:
        """动量指标分析

        计算各种动量指标，包括RSI、MACD和ADX

        返回:
        ----------
        tuple
            (uptrend, downtrend, macd_bull, macd_bear, rsi_fast, rsi_slow)
                - uptrend: 上升趋势信号
                - downtrend: 下降趋势信号
                - macd_bull: MACD看涨信号
                - macd_bear: MACD看跌信号
                - rsi_fast: 快速RSI
                - rsi_slow: 慢速RSI
        """
        rsi_fast = self.close.rsi(7)  # 快速RSI
        rsi_med = self.close.rsi(14)  # medium RSI
        rsi_slow = self.close.rsi(21)  # 慢速RSI

        macd, hist_macd, signal_macd = self.close.macd(
            12, 26, 9).to_lines()  # MACD指标
        macd_bull = (hist_macd > hist_macd.shift()) & (
            hist_macd > 0.)  # MACD看涨信号
        macd_bear = (hist_macd < hist_macd.shift()) & (
            hist_macd < 0.)  # MACD看跌信号
        adx,_, diplus, diminus = self.adx(14, 14).to_lines()  # ADX指标
        strong_trend = adx > 25.  # 强趋势
        uptrend = (diplus > diminus) & strong_trend  # 上升趋势
        downtrend = (diminus > diplus) & strong_trend  # 下降趋势

        trending_viz = adx > 25.  # 趋势可视化
        consolidating_viz = adx < 20.  # 盘整可视化
        return uptrend, downtrend, macd_bull, macd_bear, rsi_fast, rsi_slow

    def VOLUME_ANALYSIS(self):
        """成交量分析

        分析成交量变化和资金流向

        返回:
        ----------
        tuple
            (volume_bullish, volume_bearish, high_volume, v2_orderFlowScore)
                - volume_bullish: 看涨成交量信号
                - volume_bearish: 看跌成交量信号
                - high_volume: 高成交量信号
                - v2_orderFlowScore: 订单流评分
        """
        vol_ma = self.volume.sma(20)  # 成交量移动平均
        vol_std = self.volume.stdev(20)  # 成交量标准差
        high_volume = self.volume > (vol_ma + vol_std)  # 高成交量信号
        relative_volume_viz = self.volume.ZeroDivision(vol_ma)  # 相对成交量可视化
        vpt: IndSeries = (self.close.diff()/self.close.shift()
                          * self.volume).cum(10)  # 成交量价格趋势
        vpt_signal = vpt.ema(10)  # VPT信号
        volume_bullish = vpt > vpt_signal  # 看涨成交量信号
        volume_bearish = -(vpt < vpt_signal)  # 看跌成交量信号

        v2_orderFlowScore = volume_bullish+volume_bearish  # 订单流评分
        return volume_bullish, volume_bearish, high_volume, v2_orderFlowScore

    def next(self):
        """计算加权评分

        综合市场结构、动量和成交量分析，计算加权评分

        返回:
        ----------
        np.ndarray
            加权评分信号
        """
        # 计算波动率
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
    """✈ LOWESS局部加权散点图平滑

    来源: https://cn.tradingview.com/script/hyeoDyZn-LOWESS-Locally-Weighted-Scatterplot-Smoothing-ChartPrime/

    该指标使用局部加权散点图平滑技术对价格数据进行平滑处理，结合高斯移动平均和LOWESS算法，用于识别趋势

    参数:
    ----------
    length : int, 默认100
        主周期长度
    malen : int, 默认100
        移动平均长度

    返回:
    ----------
    GaussianMA : IndSeries
        高斯移动平均
    smoothed : IndSeries
        平滑后的信号
    """
    params = dict(length=100, malen=100)
    overlap = True

    def next(self):
        """计算LOWESS指标

        实现步骤:
        1. 计算ATR和标准差
        2. 计算sigma值（ATR和标准差的平均值）
        3. 应用高斯移动平均
        4. 应用LOWESS算法进行进一步平滑

        返回:
        ----------
        tuple
            (GaussianMA, smoothed)
                - GaussianMA: 高斯移动平均
                - smoothed: 平滑后的信号
        """
        length = self.params.length
        close = self.close.values
        atr = self.atr(length)  # 计算ATR
        std = self.close.stdev(length)  # 计算标准差
        sigma = (atr+std)/2.  # 计算sigma值
        sigma = sigma.values
        data = IndFrame(dict(close=close, sigma=sigma))

        def func(close: np.ndarray, sigma: np.ndarray):
            """高斯移动平均计算函数

            参数:
            ----------
            close : np.ndarray
                收盘价数组
            sigma : np.ndarray
                sigma值数组

            返回:
            ----------
            float
                高斯移动平均值
            """
            close = close[::-1]  # 反转数组
            sigma = sigma[-1]  # 取最后一个sigma值
            gma = 0.
            sumOfWeights = 0.
            for i in range(length):
                h_l = close[:i+1]  # 取前i+1个值
                highest = h_l.max()  # 计算最大值
                lowest = h_l.min()  # 计算最小值
                # 计算权重
                weight = math.exp(-math.pow(((i - (length - 1)
                                              ) / (2 * sigma)), 2) / 2)
                value = highest+lowest  # 计算高低点和
                gma = gma + (value * weight)  # 加权求和
                sumOfWeights += weight  # 计算权重和

            return (gma / sumOfWeights) / 2.  # 计算加权平均并除以2

        GaussianMA = data.rolling_apply(func, length)  # 应用高斯移动平均

        def lowess(src: pd.Series):
            """LOWESS局部加权散点图平滑函数

            参数:
            ----------
            src : pd.Series
                输入序列

            返回:
            ----------
            float
                平滑后的值
            """
            length = len(src)
            src = src.values[::-1]  # 反转数组
            sum_w = 0.0  # 权重和
            sum_wx = 0.0  # 权重乘以x的和
            sum_wy = 0.0  # 权重乘以y的和
            for i in range(length):
                w = math.pow(1 - math.pow(i / length, 3), 3)  # 计算权重
                sum_w += w
                sum_wx += w * i
                sum_wy += w * src[i]
            a = sum_wy / sum_w  # 计算截距
            b = sum_wx / sum_w  # 计算斜率
            return a + b / (length - 1) / 2000.  # 计算最终值

        smoothed = GaussianMA.rolling(
            self.params.malen).apply(lowess)  # 应用LOWESS算法
        return GaussianMA, smoothed


class The_Price_Radio(BtIndicator):
    """✈ John Ehlers The Price Radio

    来源: https://cn.tradingview.com/script/W5lBL0MV-John-Ehlers-The-Price-Radio/

    该指标由John Ehlers开发，使用价格变化率来分析市场动量和趋势

    参数:
    ----------
    length : int, 默认60
        计算周期长度
    period : int, 默认14
        价格变化率的计算周期

    返回:
    ----------
    deriv : IndSeries
        价格变化率
    amup : IndSeries
        上升动量
    amdn : IndSeries
        下降动量
    fm : IndSeries
        波动因子
    """
    params = dict(length=60, period=14)
    overlap = False

    @staticmethod
    def clamp(_value, _min, _max) -> IndSeries:
        """将值限制在指定范围内

        参数:
        ----------
        _value : IndSeries
            输入值
        _min : IndSeries
            最小值
        _max : IndSeries
            最大值

        返回:
        ----------
        IndSeries
            限制在范围内的值
        """
        df = IndFrame(dict(_value=_value, _min=_min, _max=_max))

        def test(_value, _min, _max):
            _t = _min if _value < _min else _value
            return _max if _t > _max else _t
        return df.rolling_apply(test, 1)

    @staticmethod
    def am(_signal: IndSeries, _period) -> IndSeries:
        """计算平均动量

        参数:
        ----------
        _signal : IndSeries
            输入信号
        _period : int
            计算周期

        返回:
        ----------
        IndSeries
            平均动量
        """
        _envelope = _signal.abs().tqfunc.hhv(4)
        return _envelope.sma(_period)

    @staticmethod
    def fm(_signal: IndSeries, _period) -> IndSeries:
        """计算波动因子

        参数:
        ----------
        _signal : IndSeries
            输入信号
        _period : int
            计算周期

        返回:
        ----------
        IndSeries
            波动因子
        """
        _h = _signal.tqfunc.hhv(_period)
        _l = _signal.tqfunc.llv(_period)
        _hl = The_Price_Radio.clamp(10. * _signal, _l, _h)
        return _hl.sma(_period)

    def next(self):
        """计算价格变化率和动量指标

        返回:
        ----------
        tuple
            (deriv, amup, amdn, fm)
                - deriv: 价格变化率
                - amup: 上升动量
                - amdn: 下降动量
                - fm: 波动因子
        """
        deriv = self.close.pct_change(self.params.period)
        amup = The_Price_Radio.am(deriv, self.params.length)
        amdn = -amup
        fm = The_Price_Radio.fm(deriv, self.params.length)
        return deriv, amup, amdn, fm


class PMax_Explorer(BtIndicator):
    """✈ PMax Explorer - 价格最大化指标

    来源: https://cn.tradingview.com/script/nHGK4Qtp/

    该指标使用多种移动平均类型计算价格最大化通道，结合ATR来确定趋势方向和交易信号

    参数:
    ----------
    Periods : int, 默认10
        ATR计算周期
    Multiplier : int, 默认3
        ATR乘数
    mav : str, 默认"ema"
        移动平均类型
    length : int, 默认10
        移动平均长度
    var_length : int, 默认9
        波动率计算长度

    返回:
    ----------
    pmax : np.ndarray
        价格最大化通道值
    """

    params = dict(Periods=10, Multiplier=3,
                  mav="ema", length=10, var_length=9)
    overlap = True

    def var_Func(self, src: IndSeries, length: int, var_length):
        """计算波动率调整移动平均

        参数:
        ----------
        src : IndSeries
            输入序列
        length : int
            移动平均长度
        var_length : int
            波动率计算长度

        返回:
        ----------
        IndSeries
            波动率调整移动平均
        """
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
        return IndSeries(VAR)

    def wwma_Func(self, src: IndSeries, length: int):
        """计算加权移动平均

        参数:
        ----------
        src : IndSeries
            输入序列
        length : int
            移动平均长度

        返回:
        ----------
        IndSeries
            加权移动平均
        """
        wwalpha = 1 / length
        value = src.value
        size = src.size
        WWMA = np.zeros(size)
        for i in range(1, size):
            WWMA[i] = wwalpha*value[i] + (1-wwalpha)*WWMA[i-1]
        return IndSeries(WWMA)

    def zlema_Func(self, src: IndSeries, length: int):
        """计算零滞后指数移动平均

        参数:
        ----------
        src : IndSeries
            输入序列
        length : int
            移动平均长度

        返回:
        ----------
        IndSeries
            零滞后指数移动平均
        """
        zxLag = length/2 == round(length/2) and length/2 or (length - 1) / 2
        zxEMAData = src + src.shift(zxLag)
        ZLEMA = zxEMAData.ema(length)
        return ZLEMA

    def tsf_Func(self, src: IndSeries, length: int):
        """计算时间序列预测

        参数:
        ----------
        src : IndSeries
            输入序列
        length : int
            预测周期

        返回:
        ----------
        IndSeries
            时间序列预测值
        """
        lrc = src.linreg(length)
        lrc1 = src.linreg(length, 1)
        lrs = lrc-lrc1
        TSF = src.linreg(length)+lrs
        return TSF

    def getMA(self, src: IndSeries, mav: str, length: int) -> IndSeries:
        """获取指定类型的移动平均

        支持的移动平均类型:
        - 标准类型: "dema", "ema", "fwma", "hma", "linreg", "midpoint", "pwma", "rma",
          "sinwma", "sma", "swma", "t3", "tema", "trima", "vidya", "wma", "zlma"
        - 自定义类型: "var", "wwma", "zlema", "tsf"

        参数:
        ----------
        src : IndSeries
            输入序列
        mav : str
            移动平均类型
        length : int
            移动平均长度

        返回:
        ----------
        IndSeries
            计算得到的移动平均
        """
        if mav in ["dema", "ema", "fwma", "hma", "linreg", "midpoint", "pwma", "rma",
                   "sinwma", "sma", "swma", "t3", "tema", "trima", "vidya", "wma", "zlma"]:
            return src.ma(mav, length)
        elif mav in ["var", "wwma", "zlema", "tsf"]:
            return getattr(self, f"{mav}_Func")(src, length)
        else:
            return src.ema(length)

    def Pmax_Func(self, src: IndSeries):
        """计算价格最大化通道

        参数:
        ----------
        src : IndSeries
            输入序列

        返回:
        ----------
        np.ndarray
            价格最大化通道值
        """
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
        """计算价格最大化通道

        返回:
        ----------
        np.ndarray
            价格最大化通道值
        """
        pmax = self.Pmax_Func(self.hl2())
        return pmax


class VMA_Win(BtIndicator):
    """✈ VMA Win - 波动率调整移动平均

    来源: https://cn.tradingview.com/script/09F2GICn-VMA-Win-Dashboard-for-Different-Lengths/

    该指标使用波动率调整的移动平均，根据市场波动情况动态调整权重

    参数:
    ----------
    length : int, 默认15
        计算周期长度

    返回:
    ----------
    vma : IndSeries
        波动率调整移动平均
    """
    params = dict(length=15)
    overlap = True

    def vma(self, src: IndSeries, length):
        """计算波动率调整移动平均

        参数:
        ----------
        src : IndSeries
            输入序列
        length : int
            计算周期长度

        返回:
        ----------
        IndSeries
            波动率调整移动平均
        """
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
        return IndSeries(vma)

    def next(self):
        """计算波动率调整移动平均

        返回:
        ----------
        IndSeries
            波动率调整移动平均
        """
        vma = self.vma(self.close, self.params.length)
        return vma


class RJ_Trend_Engine(BtIndicator):
    """✈ RJ Trend Engine - 综合趋势引擎

    来源: https://cn.tradingview.com/script/xZ9IlWfi-RJ-Trend-Engine-Final-Version/

    该指标综合了SAR、超级趋势和ADX指标，用于识别市场趋势和交易信号

    参数:
    ----------
    psarStart : float, 默认0.02
        SAR指标的起始加速因子
    psarIncrement : float, 默认0.02
        SAR指标的加速因子增量
    psarMax : float, 默认0.2
        SAR指标的最大加速因子
    stAtrPeriod : int, 默认10
        超级趋势指标的ATR周期
    stFactor : float, 默认3.0
        超级趋势指标的因子
    adxLen : int, 默认14
        ADX指标的周期
    adxThreshold : int, 默认20
        ADX趋势强度阈值
    bbLength : int, 默认20
        布林带周期
    bbStdDev : float, 默认3.0
        布林带标准差

    返回:
    ----------
    psar : IndSeries
        SAR指标值
    trend : IndSeries
        超级趋势值
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
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
        """计算综合趋势指标和交易信号

        返回:
        ----------
        tuple
            (psar, trend, long_signal, short_signal)
                - psar: SAR指标值
                - trend: 超级趋势值
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        psar = self.SAR(self.params.psarStart, self.params.psarMax)
        trend, st_direction, * \
            _ = self.supertrend(self.params.stAtrPeriod,
                                    self.params.stFactor).to_lines()
        adx,adxr, diplus, diminus = self.adx(
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
        return psar, trend, long_signal, short_signal


class Twin_Range_Filter(BtIndicator):
    """✈ Twin Range Filter - 双范围过滤器

    来源: https://cn.tradingview.com/script/57i9oK2t-Twin-Range-Filter-Buy-Sell-Signals/

    该指标使用两个不同周期的范围过滤器来生成交易信号，结合趋势检测提高信号质量

    参数:
    ----------
    per1 : int, 默认127
        第一个范围过滤器的周期
    mult1 : float, 默认1.6
        第一个范围过滤器的乘数
    per2 : int, 默认155
        第二个范围过滤器的周期
    mult2 : float, 默认2.0
        第二个范围过滤器的乘数

    返回:
    ----------
    filt : np.ndarray
        过滤后的信号线
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """

    params = dict(
        per1=127,
        mult1=1.6,
        per2=155,
        mult2=2.0,
    )
    overlap = True

    def smoothrng(self, x: IndSeries, t: int, m: float):
        """计算平滑范围

        参数:
        ----------
        x : IndSeries
            输入序列
        t : int
            计算周期
        m : float
            乘数

        返回:
        ----------
        IndSeries
            平滑后的范围
        """
        wper = t * 2 - 1
        avrng = x.diff().abs().ema(t)
        return avrng.ema(wper) * m

    def rngfilt(self, x: IndSeries, r: IndSeries):
        """计算范围过滤器

        参数:
        ----------
        x : IndSeries
            输入序列
        r : IndSeries
            范围序列

        返回:
        ----------
        np.ndarray
            过滤后的序列
        """
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
        """计算双范围过滤器和交易信号

        返回:
        ----------
        tuple
            (filt, long_signal, short_signal)
                - filt: 过滤后的信号线
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
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
    """✈ PMax Explorer Strategy - 价格最大化通道策略

    来源: https://cn.tradingview.com/script/nHGK4Qtp/

    该策略使用价格最大化通道来生成交易信号，结合移动平均交叉和价格穿越通道来确定买卖时机

    参数:
    ----------
    Periods : int, 默认10
        ATR计算周期
    Multiplier : float, 默认3.0
        ATR乘数
    mav : str, 默认"ema"
        移动平均类型
    length : int, 默认10
        移动平均长度

    返回:
    ----------
    pmax : IndSeries
        价格最大化通道值
    thrend : IndSeries
        趋势方向
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
    params = dict(Periods=10, Multiplier=3., mav="ema", length=10)
    overlap = dict(pmax=True, thrend=False)

    def next(self):
        """计算价格最大化通道策略信号

        返回:
        ----------
        tuple
            (pmax, thrend, long_signal, short_signal)
                - pmax: 价格最大化通道值
                - thrend: 趋势方向
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        src = self.hl2()
        mult = self.params.Multiplier
        MAvg = self.close.ma(self.params.mav, self.params.length)
        pmax, thrend = self.btind.pmax2(self.params.length, mult).to_lines()
        long_signal = MAvg.cross_up(pmax) & src.cross_up(pmax)
        short_signal = MAvg.cross_down(pmax) & src.cross_down(pmax)
        return pmax, thrend, long_signal, short_signal


class UT_Bot_Alerts(BtIndicator):
    """✈ UT Bot Alerts - ATR跟踪止损策略

    来源: https://cn.tradingview.com/script/n8ss8BID-UT-Bot-Alerts/

    该策略使用ATR跟踪止损来生成交易信号，可选择使用Heikin Ashi蜡烛图

    参数:
    ----------
    a : float, 默认1.0
        ATR乘数，控制止损幅度
    c : int, 默认10
        ATR计算周期
    h : bool, 默认False
        是否使用Heikin Ashi蜡烛图

    返回:
    ----------
    alerts : np.ndarray
        跟踪止损线
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
    params = dict(a=1., c=10, h=False)
    overlap = True

    def next(self):
        """计算ATR跟踪止损策略信号

        返回:
        ----------
        tuple
            (alerts, long_signal, short_signal)
                - alerts: 跟踪止损线
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
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

    def step(self):
        if not self.kline.position:
            if self.long_signal.new:
                self.kline.buy(stop=BtStop.SegmentationTracking)
            elif self.short_signal.new:
                self.kline.sell(stop=BtStop.SegmentationTracking)


class SuperTrend(BtIndicator):
    """✈ SuperTrend - 超级趋势指标

    来源: https://cn.tradingview.com/script/r6dAP7yi/

    该指标使用ATR来计算趋势方向和交易信号，可选择是否对ATR进行平滑处理

    参数:
    ----------
    Periods : int, 默认10
        ATR计算周期
    Multiplier : float, 默认3.0
        ATR乘数
    changeATR : bool, 默认True
        是否对ATR进行平滑处理

    返回:
    ----------
    upper : np.ndarray
        上轨
    lower : np.ndarray
        下轨
    trend : pd.Series
        趋势方向
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
    params = dict(Periods=10, Multiplier=3., changeATR=True,)
    overlap = dict(upper=True, lower=True, trend=False)

    def next(self):
        """计算超级趋势指标和交易信号

        返回:
        ----------
        tuple
            (upper, lower, trend, long_signal, short_signal)
                - upper: 上轨
                - lower: 下轨
                - trend: 趋势方向
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
        src = self.hl2()
        size = src.size
        atr = self.atr(self.params.Periods)
        if not self.params.changeATR:
            atr = atr.sma(self.params.Periods)
        close = self.close.values
        up = (src-self.params.Multiplier*atr).values.copy()
        dn = (src+self.params.Multiplier*atr).values.copy()
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
    """✈ CM Williams Vix Fix - 市场底部寻找指标

    来源: https://cn.tradingview.com/script/og7JPrRA-CM-Williams-Vix-Fix-Finds-Market-Bottoms/

    该指标由Larry Williams开发，用于识别市场底部，结合波动率和通道分析

    参数:
    ----------
    hl : int, 默认22
        计算最高价的周期
    bbl : int, 默认20
        布林带周期
    mult : float, 默认2.0
        布林带标准差乘数
    lb : int, 默认50
        计算高低范围的周期
    ph : float, 默认0.95
        范围高点乘数
    pl : float, 默认1.01
        范围低点乘数

    返回:
    ----------
    wvf : IndSeries
        Williams Vix Fix指标值
    lowerBand : IndSeries
        下轨
    upperBand : IndSeries
        上轨
    rangeHigh : IndSeries
        范围高点
    rangeLow : IndSeries
        范围低点
    """
    params = dict(hl=22, bbl=20, mult=2.0, lb=50, ph=.95, pl=1.01)
    overlap = False
    linestyle = dict(wvf=LineStyle(
        line_dash=LineDash.vbar))

    def next(self):
        """计算Williams Vix Fix指标和相关通道

        返回:
        ----------
        tuple
            (wvf, lowerBand, upperBand, rangeHigh, rangeLow)
                - wvf: Williams Vix Fix指标值
                - lowerBand: 下轨
                - upperBand: 上轨
                - rangeHigh: 范围高点
                - rangeLow: 范围低点
        """
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
    """✈ WaveTrend Oscillator - 波浪趋势振荡器

    来源: https://cn.tradingview.com/script/2KE8wTuF-Indicator-WaveTrend-Oscillator-WT/

    该指标使用波浪理论和振荡器原理，用于识别市场趋势和潜在的反转点

    参数:
    ----------
    n1 : int, 默认10
        第一周期参数
    n2 : int, 默认21
        第二周期参数
    n3 : int, 默认9
        第三周期参数

    返回:
    ----------
    signal : IndSeries
        信号值
    wt1 : IndSeries
        波浪趋势值1
    wt2 : IndSeries
        波浪趋势值2
    """
    params = dict(n1=10, n2=21, n3=9)
    spanstyle = [60, 53, -60, -53]
    overlap = False
    linestyle = dict(signal=LineStyle(line_dash=LineDash.vbar))

    def next(self):
        """计算波浪趋势振荡器

        返回:
        ----------
        tuple
            (signal, wt1, wt2)
                - signal: 信号值
                - wt1: 波浪趋势值1
                - wt2: 波浪趋势值2
        """
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
    """✈ ADX and DI - 平均趋向指标和方向指标

    来源: https://cn.tradingview.com/script/VTPMMOrx-ADX-and-DI/

    该指标用于衡量市场趋势的强度和方向，包括ADX（平均趋向指标）、+DI（正向方向指标）和-DI（负向方向指标）

    参数:
    ----------
    length : int, 默认14
        计算周期
    th : int, 默认20
        ADX阈值，用于判断趋势强度

    返回:
    ----------
    ADX : pd.Series
        平均趋向指标
    DIPlus : IndSeries
        正向方向指标
    DIMinus : IndSeries
        负向方向指标
    """
    params = dict(length=14, th=20)
    overlap = False

    def next(self):
        """计算平均趋向指标和方向指标

        返回:
        ----------
        tuple
            (ADX, DIPlus, DIMinus)
                - ADX: 平均趋向指标
                - DIPlus: 正向方向指标
                - DIMinus: 负向方向指标
        """
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
    """✈ Bollinger RSI Double Strategy - 布林带RSI双重策略

    来源: https://cn.tradingview.com/script/uCV8I4xA-Bollinger-RSI-Double-Strategy-by-ChartArt-v1-1/

    该策略结合布林带和RSI指标，当价格穿越布林带边界且RSI同时穿越阈值时生成交易信号

    参数:
    ----------
    RSIlength : int, 默认6
        RSI计算周期
    RSIoverSold : float, 默认50.0
        RSI超卖阈值
    RSIoverBought : float, 默认50.0
        RSI超买阈值
    BBlength : int, 默认200
        布林带周期
    BBmult : float, 默认2.0
        布林带标准差乘数

    返回:
    ----------
    BBupper : IndSeries
        布林带上轨
    BBlower : IndSeries
        布林带下轨
    long_signal : np.ndarray
        多头信号
    short_signal : np.ndarray
        空头信号
    """
    params = dict(RSIlength=6, RSIoverSold=50.,
                  RSIoverBought=50., BBlength=200, BBmult=2.)
    overlap = True

    def next(self):
        """计算布林带RSI双重策略信号

        返回:
        ----------
        tuple
            (BBupper, BBlower, long_signal, short_signal)
                - BBupper: 布林带上轨
                - BBlower: 布林带下轨
                - long_signal: 多头信号
                - short_signal: 空头信号
        """
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
    """✈ Pivot Point Supertrend - 枢轴点超级趋势指标

    来源: https://cn.tradingview.com/script/L0AIiLvH-Pivot-Point-Supertrend/

    该指标结合枢轴点和超级趋势指标，用于识别市场趋势和交易信号

    参数:
    ----------
    prd : int, 默认7
        枢轴点计算周期
    Factor : int, 默认4
        超级趋势因子
    Pd : int, 默认14
        ATR计算周期

    返回:
    ----------
    无直接返回值，结果通过self.lines属性设置
    """
    params = dict(prd=7, Factor=4, Pd=14,)
    overlap = True

    def next(self):
        """计算枢轴点超级趋势指标

        实现步骤:
        1. 计算枢轴点
        2. 计算超级趋势指标
        3. 通过self.lines属性设置结果

        返回:
        ----------
        无直接返回值，结果通过self.lines属性设置
        """
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
        AlphaTrend = self.full()
        Trend = self.full()
        size = src.size
        index = self.get_first_valid_index(upT, downT, mfi, rsi)
        AlphaTrend[index] = Trend[index] = 0.
        for i in range(index+1, size):
            AlphaTrend[i] = (rsi[i] >= 50. if novolumedata else mfi[i] >= 50.) and (upT[i] < AlphaTrend[i-1] and AlphaTrend[i-1] or upT[i]) or \
                (downT[i] > AlphaTrend[i-1] and AlphaTrend[i-1] or downT[i])
            Trend[i] = AlphaTrend[i] > AlphaTrend[i -
                                                  2] and 1 or (AlphaTrend[i] < AlphaTrend[i-2] and -1 or Trend[i-1])
        AlphaTrend = IndSeries(AlphaTrend)
        AlphaTrend2 = AlphaTrend.shift(2)
        Trend = IndSeries(Trend)
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
        def ma(x: IndSeries, y): return x.sma(y) if smoothVFI else x

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
        close = self.close.values.copy()
        longStopPrev = longStop.shift().bfill().values.copy()
        longStop = longStop.bfill().values.copy()
        shortStopPrev = shortStop.shift().bfill().values.copy()
        shortStop = shortStop.bfill().values.copy()
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

        # dir = IndSeries(dir)
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
        longStop = longStop.bfill().values.copy()
        shortStop = shortStop.bfill().values.copy()
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
        # dir = IndSeries(dir)
        long_signal = dir == 1
        long_signal &= dir.shift() == -1
        short_signal = dir == -1
        short_signal &= dir.shift() == 1
        return up, dn, long_signal, short_signal


class Optimized_Trend_Tracker(BtIndicator):
    """https://cn.tradingview.com/script/zVhoDQME/"""
    params = dict(length=2, var_length=9, percent=1.4, base=200)
    overlap = True

    def var_Func(self, src: IndSeries, length: int, var_length):
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
        return IndSeries(VAR)

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
        MAvg = MAvg.values.copy()
        longStop = longStop.values.copy()
        shortStop = shortStop.values.copy()
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
        MT, OTT = IndSeries(MT), IndSeries(OTT)
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
    ## TradingView 社区策略指标集合类

    - **TradingView 策略指标集合类**，用于将 TradingView 平台上广受欢迎的交易策略和指标转换为框架内置的指标数据类型（IndSeries/IndFrame）

    ### 📘 **API文档参考**:
    - https://www.minibt.cn/minibt_api_reference/tradingview/

    ### 核心功能：
    - 封装 TradingView 社区的优质策略指标，提供统一的调用接口
    - 通过 BtIndicator 基类自动处理指标参数校验、计算逻辑调用和返回值转换，确保输出为框架兼容的 IndSeries 或 IndFrame
    - 支持多维度交易策略场景，覆盖趋势跟踪、均值回归、波动率分析、动量交易等量化交易核心需求
    - 内置策略分类体系，便于按交易风格和策略类型快速定位和调用目标指标

    ### 策略分类与包含列表：
    该类支持的策略指标按功能划分为以下 8 大类，具体包含指标如下：

    #### **1. 趋势跟踪策略（Trend Following）**
       - 功能：识别和跟踪市场趋势方向，在趋势启动时入场，趋势结束时出场
       - 包含策略：Powertrend_Volume_Range_Filter_Strategy、Nadaraya_Watson_Envelope_Strategy、Adaptive_Trend_Filter、
       - Multi_Step_Vegas_SuperTrend_strategy、RJ_Trend_Engine、AlphaTrend、SuperTrend、SuperTrend_STRATEGY、Optimized_Trend_Tracker

    #### **2. 均值回归策略（Mean Reversion）**
       - 功能：在价格偏离均值时入场，预期价格回归均值时出场
       - 包含策略：DCA_Strategy_with_Mean_Reversion_and_Bollinger_Band、Bollinger_RSI_Double_Strategy、CM_Williams_Vix_Fix_Finds_Market_Bottoms

    #### **3. 突破策略（Breakout）**
       - 功能：在价格突破关键支撑阻力位时入场，捕捉趋势启动机会
       - 包含策略：Turtles_strategy、Turtle_Trade_Channels_Indicator_TUTCI、G_Channels、Twin_Range_Filter

    #### **4. 动量策略（Momentum）**
       - 功能：基于价格和成交量的动量变化识别交易机会
       - 包含策略：The_Flash_Strategy、WaveTrend_Oscillator、TonyUX_EMA_Scalper、Volume_Flow_Indicator

    #### **5. 波动率策略（Volatility）**
       - 功能：基于市场波动率变化调整交易参数和风险管理
       - 包含策略：STD_Filtered、PMax_Explorer、PMax_Explorer_STRATEGY、Chandelier_Exit、Pivot_Point_Supertrend

    #### **6. 机器学习策略（Machine Learning）**
       - 功能：基于自适应算法和AI技术优化策略参数
       - 包含策略：Quantum_Edge_Pro_Adaptive_AI、LOWESS

    #### **7. 信号处理策略（Signal Processing）**
       - 功能：基于信号处理理论分析价格数据
       - 包含策略：The_Price_Radio、ADX_and_DI

    #### **8. 风险管理策略（Risk Management）**
       - 功能：专注于头寸管理和风险控制的策略工具
       - 包含策略：Chandelier_Exit、Turtles_strategy

    ### 使用说明：
    #### 1. 初始化：
    - 传入框架支持的 KLine、IndFrame 或 IndSeries 数据对象（需包含策略计算所需的基础字段，如 open、high、low、close、volume 等）
    >>> data = IndFrame(...)  # 框架内置数据对象（含OHLCV等基础字段）
    >>> tv = TradingView(data)

    #### 2. 策略调用：
    - 直接调用对应策略方法，传入必要参数（默认参数已适配常见场景，可按需调整）
    >>> # 示例1：调用海龟交易策略
    >>> # 返回框架内置IndFrame，含多空信号和出场信号
    >>> turtle_signals = tv.Turtles_strategy(enter_fast=20, exit_fast=10, enter_slow=55, exit_slow=20)
    >>> # 示例2：调用超级趋势策略
    >>> supertrend_data = tv.SuperTrend_STRATEGY(Periods=10, Multiplier=3.0)
    >>> # 示例3：调用自适应AI策略
    >>> ai_scores = tv.Quantum_Edge_Pro_Adaptive_AI(LEARNING_PERIOD=40, ADAPTATION_SPEED=0.3)

    #### 3. 返回值特性：
    - 所有方法返回框架内置的 IndSeries 或 IndFrame 类型，可直接用于后续策略逻辑（如信号生成、风险控制），无需额外类型转换

    ### 策略集成示例：
    ```python
    class AdvancedStrategy(Strategy):
        def __init__(self):
            self.data = self.get_data(LocalDatas.test)
            self.tv = self.data.tradingview

            # 多重策略信号集成
            self.trend_signals = self.tv.SuperTrend_STRATEGY(Periods=10, Multiplier=3.0)
            self.momentum_signals = self.tv.WaveTrend_Oscillator(n1=10, n2=21, n3=9)
            self.volume_signals = self.tv.Volume_Flow_Indicator(length=130, coef=0.2)

        def next(self):
            if not self.data.position:
                # 趋势确认 + 动量确认 + 成交量确认
                long_condition = (self.trend_signals.long_signal.new & 
                                 (self.momentum_signals.wt1.new > 0) & 
                                 (self.volume_signals.vfi.new > 0))

                short_condition = (self.trend_signals.short_signal.new & 
                                  (self.momentum_signals.wt1.new < 0) & 
                                  (self.volume_signals.vfi.new < 0))

                # 执行交易逻辑
                if long_condition:
                    self.data.buy()
                elif short_condition:
                    self.data.sell()
    ```

    ### 注意事项：
    - 不同策略对基础数据字段要求不同，调用前确保输入数据包含所需字段（如成交量策略需要volume字段）
    - 策略参数对性能影响显著，建议通过回测优化确定最佳参数组合
    - 复杂策略（如AI自适应策略）需要足够的历史数据才能有效工作
    - 建议在模拟环境中充分测试策略表现后再实盘应用
    - 可结合框架的风险管理模块控制单策略和组合风险

    ### 性能优化建议：
    - 1. **参数调优**：使用框架的回测工具对策略参数进行优化
    - 2. **组合使用**：将不同策略信号组合使用，提高系统稳定性
    - 3. **风险分散**：在同一策略类别中选择多个不相关策略分散风险
    - 4. **市场适应**：根据不同市场环境动态调整策略权重
    - 5. **监控评估**：定期评估策略表现，及时调整或替换失效策略
    """
    _kline: KLine | IndFrame | IndSeries | Line

    def __init__(self, kline: KLine | IndFrame | IndSeries | Line ,**kwargs):
        # if kwargs.pop("ischeck", True):
        #     assert isinstance(kline, (KLine, IndFrame)), (
        #         f"❌：tradingview指标初始化数据类型需为KLine或包含OHLCV列的IndFrame，传入的数据格式为{type(kline)}")
        self._kline = kline

    def Powertrend_Volume_Range_Filter_Strategy(self, l=200, lengthvwma=200, mult=3., lengthadx=200, lengthhl=14,
                                                useadx=False, usehl=False, usevwma=False, highlighting=True, **kwargs) -> IndFrame:
        """
        ## 成交量范围过滤策略

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.1_powertrend_volume_range_filter/
        - ✈ https://cn.tradingview.com/script/45FlB2qH-Powertrend-Volume-Range-Filter-Strategy-wbburgin/

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
            self._kline, l=l, lengthvwma=lengthvwma, mult=mult,
            lengthadx=lengthadx, lengthhl=lengthhl, useadx=useadx,
            usehl=usehl, usevwma=usevwma, highlighting=highlighting, **kwargs
        )

    def Nadaraya_Watson_Envelope_Strategy(self, customLookbackWindow=8., customRelativeWeighting=8., customStartRegressionBar=25.,
                                          length=60, customATRLength=60, customNearATRFactor=1.5, customFarATRFactor=2., **kwargs) -> IndFrame:
        """
        ## Nadaraya-Watson包络线策略

        ### 📘 **文档参考**:
        - ✈ https://cn.tradingview.com/script/HrZicISx-Nadaraya-Watson-Envelope-Strategy-Non-Repainting-Log-Scale/

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
            self._kline, customLookbackWindow=customLookbackWindow,
            customRelativeWeighting=customRelativeWeighting,
            customStartRegressionBar=customStartRegressionBar, length=length,
            customATRLength=customATRLength, customNearATRFactor=customNearATRFactor,
            customFarATRFactor=customFarATRFactor, **kwargs
        )

    def G_Channels(self, length=144., cycle=1, thresh=0., **kwargs) -> IndFrame:
        """
        ## G通道指标 - 高效计算上下极值点

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.2_g_channels/
        - ✈ https://www.tradingview.com/script/fIvlS64B-G-Channels-Efficient-Calculation-Of-Upper-Lower-Extremities/

        Args:
            length: 通道长度
            cycle: 周期循环
            thresh: zig参数
            **kwargs: 其他参数

        Returns:
            G_Channels: 包含a(上轨), b(下轨), avg(中轨), zig(之字转向)线的指标对象
        """
        return G_Channels(self._kline, length=length, cycle=cycle, thresh=thresh, **kwargs)

    def STD_Filtered(self, period=25, order=5, filterperiod=10, filter=1., **kwargs) -> IndFrame:
        """
        ## STD过滤N极高斯滤波器

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.3_std_filtered_n_pole_gaussian_filter/
        - ✈ https://cn.tradingview.com/script/i4xZNAoy-STD-Filtered-N-Pole-Gaussian-Filter-Loxx/

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
            self._kline, period=period, order=order,
            filterperiod=filterperiod, filter=filter, **kwargs
        )

    def Turtles_strategy(self, enter_fast=20, exit_fast=10, enter_slow=55, exit_slow=20, **kwargs) -> IndFrame:
        """
        ## 海龟交易策略 - 历经20年验证的有效策略

        ### 📘 **文档参考**:
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
            self._kline, enter_fast=enter_fast, exit_fast=exit_fast,
            enter_slow=enter_slow, exit_slow=exit_slow, **kwargs
        )

    def Adaptive_Trend_Filter(self, alphaFilter=0.01, betaFilter=0.1, filterPeriod=21,
                              supertrendFactor=1, supertrendAtrPeriod=7, **kwargs) -> IndFrame:
        """
        ## 自适应趋势过滤器

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.4_adaptive_trend_filter/
        - ✈ https://cn.tradingview.com/script/PhSlALob-Adaptive-Trend-Filter-tradingbauhaus/

        Args:
            alphaFilter: Alpha过滤参数
            betaFilter: Beta过滤参数
            filterPeriod: 过滤周期
            supertrendFactor: 超级趋势因子
            supertrendAtrPeriod: 超级趋势ATR周期
            **kwargs: 其他参数

        Returns:
            IndFrame: (filteredValue, supertrendValue, trendDirection)
                - filteredValue: 过滤后的数值
                - supertrendValue: 超级趋势值
                - trendDirection: 趋势方向
        """
        return Adaptive_Trend_Filter(
            self._kline, alphaFilter=alphaFilter, betaFilter=betaFilter,
            filterPeriod=filterPeriod, supertrendFactor=supertrendFactor,
            supertrendAtrPeriod=supertrendAtrPeriod, **kwargs
        )

    def DCA_Strategy_with_Mean_Reversion_and_Bollinger_Band(self, length=14, mult=2., **kwargs) -> IndFrame:
        """
        ## 均值回归与布林带结合的DCA策略

        ### 📘 **文档参考**:
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
            self._kline, length=length, mult=mult, **kwargs
        )

    def Multi_Step_Vegas_SuperTrend_strategy(self, atrPeriod=10, vegasWindow=100,
                                             superTrendMultiplier=5, volatilityAdjustment=5, matype="jma", **kwargs) -> IndFrame:
        """
        ## 多步维加斯超级趋势策略

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.5_multi_step_vegas_supertrend/
        - ✈ https://cn.tradingview.com/script/SXtas3lS-Multi-Step-Vegas-SuperTrend-strategy-presentTrading/

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
            self._kline, atrPeriod=atrPeriod, vegasWindow=vegasWindow,
            superTrendMultiplier=superTrendMultiplier,
            volatilityAdjustment=volatilityAdjustment, matype=matype, **kwargs
        )

    def The_Flash_Strategy(self, length=10, mom_rsi_val=50, atrPeriod=10,
                           factor=3., AP2=12, AF2=.1618, **kwargs) -> IndFrame:
        """
        ## Flash策略 - 动量RSI与EMA交叉结合ATR

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.6_the_flash_strategy/
        - ✈ https://cn.tradingview.com/script/XKgLfo15-The-Flash-Strategy-Momentum-RSI-EMA-crossover-ATR/

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
            self._kline, length=length, mom_rsi_val=mom_rsi_val,
            atrPeriod=atrPeriod, factor=factor, AP2=AP2, AF2=AF2, **kwargs
        )

    def Quantum_Edge_Pro_Adaptive_AI(self, TICK_SIZE=0.25, POINT_VALUE=2, DOLLAR_PER_POINT=2, LEARNING_PERIOD=40, ADAPTATION_SPEED=0.3,
                                     PERFORMANCE_MEMORY=200, BASE_MIN_SCORE=2, BASE_BARS_BETWEEN=9, MAX_DAILY_TRADES=50, **kwargs) -> IndFrame:
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
            self._kline, TICK_SIZE=TICK_SIZE, POINT_VALUE=POINT_VALUE,
            DOLLAR_PER_POINT=DOLLAR_PER_POINT, LEARNING_PERIOD=LEARNING_PERIOD,
            ADAPTATION_SPEED=ADAPTATION_SPEED, PERFORMANCE_MEMORY=PERFORMANCE_MEMORY,
            BASE_MIN_SCORE=BASE_MIN_SCORE, BASE_BARS_BETWEEN=BASE_BARS_BETWEEN,
            MAX_DAILY_TRADES=MAX_DAILY_TRADES, **kwargs
        )

    def LOWESS(self, length=100, malen=100, **kwargs) -> IndFrame:
        """
        ## LOWESS局部加权散点图平滑

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.8_lowess_locally_weighted_scatterplot_smoothing/
        - ✈ https://cn.tradingview.com/script/hyeoDyZn-LOWESS-Locally-Weighted-Scatterplot-Smoothing-ChartPrime/

        Args:
            length: 主周期长度
            malen: 移动平均长度
            **kwargs: 其他参数

        Returns:
            tuple: (GaussianMA, smoothed)
                - GaussianMA: 高斯移动平均
                - smoothed: 平滑后的信号
        """
        return LOWESS(self._kline, length=length, malen=malen, **kwargs)

    def The_Price_Radio(self, length=60, period=14, **kwargs) -> IndFrame:
        """
        ## John Ehlers价格收音机指标

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.9_john_ehlers_the_price_radio/
        - ✈ https://cn.tradingview.com/script/W5lBL0MV-John-Ehlers-The-Price-Radio/

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
        return The_Price_Radio(self._kline, length=length, period=period, **kwargs)

    def PMax_Explorer(self, Periods=10, Multiplier=3, mav="ema", length=10, var_length=9, **kwargs) -> IndFrame:
        """
        ## PMax探索者指标

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.10_pmax_explorer/
        - ✈ https://cn.tradingview.com/script/nHGK4Qtp/

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
            self._kline, Periods=Periods, Multiplier=Multiplier,
            mav=mav, length=length, var_length=var_length, **kwargs
        )

    def VMA_Win(self, length=15, **kwargs) -> IndFrame:
        """
        ## VMA赢家仪表板 - 不同长度的VMA分析

        ### 📘 **文档参考**:
        ✈ https://cn.tradingview.com/script/09F2GICn-VMA-Win-Dashboard-for-Different-Lengths/

        Args:
            length: VMA周期长度
            **kwargs: 其他参数

        Returns:
            vma: 变异移动平均线
        """
        return VMA_Win(self._kline, length=length, **kwargs)

    def RJ_Trend_Engine(self, psarStart=0.02, psarIncrement=0.02, psarMax=0.2, stAtrPeriod=10,
                        stFactor=3.0, adxLen=14, adxThreshold=20, bbLength=20, bbStdDev=3.0, **kwargs) -> IndFrame:
        """
        ## RJ趋势引擎 - 最终版本

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.11_rj_trend_engine_final_version/
        - ✈ https://cn.tradingview.com/script/xZ9IlWfi-RJ-Trend-Engine-Final-Version/

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
            self._kline, psarStart=psarStart, psarIncrement=psarIncrement,
            psarMax=psarMax, stAtrPeriod=stAtrPeriod, stFactor=stFactor,
            adxLen=adxLen, adxThreshold=adxThreshold, bbLength=bbLength,
            bbStdDev=bbStdDev, **kwargs
        )

    def Twin_Range_Filter(self, per1=127, mult1=1.6, per2=155, mult2=2.0, **kwargs) -> IndFrame:
        """
        ## 双范围过滤器 - 买卖信号生成

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.12_twin_kange_filter/
        - ✈ https://cn.tradingview.com/script/57i9oK2t-Twin-Range-Filter-Buy-Sell-Signals/

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
            self._kline, per1=per1, mult1=mult1, per2=per2, mult2=mult2, **kwargs
        )

    def PMax_Explorer_STRATEGY(self, Periods=10, Multiplier=3., mav="ema", length=10, **kwargs) -> IndFrame:
        """
        ## PMax探索者策略

        ### 📘 **文档参考**:
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
            self._kline, Periods=Periods, Multiplier=Multiplier,
            mav=mav, length=length, **kwargs
        )

    def UT_Bot_Alerts(self, a=1., c=10, h=False, **kwargs) -> IndFrame:
        """
        ## UT Bot 警报指标

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.13_ut_bot_alerts/
        - ✈ https://cn.tradingview.com/script/n8ss8BID-UT-Bot-Alerts/

        Args:
            a: 调整因子参数，默认 `1.0`
            c: 周期相关参数，默认 `10`
            h: 布尔值，控制是否启用高亮等额外显示逻辑，默认 `False`
            **kwargs: 其他扩展参数

        Returns:
            IndFrame:alerts, long_signal, short_signal
            UT Bot 警报相关的指标数据（如信号标记、警报触发状态等）
        """
        return UT_Bot_Alerts(self._kline, a=a, c=c, h=h, **kwargs)

    def SuperTrend(self, Periods=10, Multiplier=3., changeATR=True, **kwargs) -> IndFrame:
        """
        ## 超级趋势指标

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.14_supertrend/
        - ✈ https://cn.tradingview.com/script/r6dAP7yi/

        Args:
            Periods: ATR 计算周期，默认 `10`
            Multiplier: ATR 乘数（用于调整趋势带宽度），默认 `3.0`
            changeATR: 布尔值，控制是否采用特殊逻辑计算 ATR，默认 `True`
            **kwargs: 其他扩展参数

        Returns:
            超级趋势指标相关数据（如趋势线位置、多空趋势信号等）
        """
        return SuperTrend(self._kline, Periods=Periods, Multiplier=Multiplier, changeATR=changeATR, **kwargs)

    def CM_Williams_Vix_Fix_Finds_Market_Bottoms(self, hl=22, bbl=20, mult=2.0, lb=50, ph=.85, pl=1.01, **kwargs) -> IndFrame:
        """
        ## CM Williams Vix Fix 市场底部识别指标

        ### 📘 **文档参考**:
        - ✈ https://cn.tradingview.com/script/og7JPrRA-CM-Williams-Vix-Fix-Finds-Market-Bottoms/

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
        return CM_Williams_Vix_Fix_Finds_Market_Bottoms(self._kline, hl=hl, bbl=bbl, mult=mult, lb=lb, ph=ph, pl=pl, **kwargs)

    def WaveTrend_Oscillator(self, n1=10, n2=21, n3=9, **kwargs) -> IndFrame:
        """
        ## WaveTrend 振荡器指标

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.15_wavetrend_oscillator/
        - ✈ https://cn.tradingview.com/script/2KE8wTuF-Indicator-WaveTrend-Oscillator-WT/

        Args:
            n1: 第一周期参数，默认 `10`
            n2: 第二周期参数，默认 `21`
            n3: 第三周期参数，默认 `9`
            **kwargs: 其他扩展参数

        Returns:
            包含 `signal`（信号值）、`wt1`（WaveTrend 核心值1）、`wt2`（WaveTrend 核心值2）的指标数据
        """
        return WaveTrend_Oscillator(self._kline, n1=n1, n2=n2, n3=n3, **kwargs)

    def ADX_and_DI(self, length=14, **kwargs) -> IndFrame:
        """
        ## ADX 与 DI 指标（平均方向指数 + 方向指标）

        ### 📘 **文档参考**:
        ✈ https://cn.tradingview.com/script/VTPMMOrx-ADX-and-DI/

        Args:
            length: ADX 计算周期，默认 `14`
            **kwargs: 其他扩展参数

        Returns:
            包含 `ADX`（趋势强度）、`DIPlus`（正向方向指标）、`DIMinus`（负向方向指标）的指标数据
        """
        return ADX_and_DI(self._kline, length=14, **kwargs)

    def Bollinger_RSI_Double_Strategy(self, RSIlength=6, RSIoverSold=50., RSIoverBought=50., BBlength=200, BBmult=2., **kwargs) -> IndFrame:
        """
        ## 布林带 + RSI 双重策略

        ### 📘 **文档参考**:
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
        return Bollinger_RSI_Double_Strategy(self._kline, RSIlength=RSIlength, RSIoverSold=RSIoverSold, RSIoverBought=RSIoverBought,
                                             BBlength=BBlength, BBmult=BBmult, **kwargs)

    def Pivot_Point_Supertrend(self, prd=2, Factor=3, Pd=10, **kwargs) -> IndFrame:
        """
        ## 枢轴点 + 超级趋势指标

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.16_pivot_point_supertrend/
        - ✈ https://cn.tradingview.com/script/L0AIiLvH-Pivot-Point-Supertrend/

        Args:
            prd: 枢轴点计算周期相关参数，默认 `2`
            Factor: 超级趋势乘数，默认 `3`
            Pd: ATR 计算周期，默认 `10`
            **kwargs: 其他扩展参数

        Returns:
            包含 `Trailingsl`（跟踪止损线）、`long_signal`（多头信号）、`short_signal`（空头信号）的指标数据
        """
        return Pivot_Point_Supertrend(self._kline, prd=prd, Factor=Factor, Pd=Pd, **kwargs)

    def AlphaTrend(self, coeff=1., AP=14, novolumedata=False, **kwargs) -> IndFrame:
        """
        ## Alpha 趋势指标

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.17_alphatrend/
        - ✈ https://cn.tradingview.com/script/o50NYLAZ-AlphaTrend/

        Args:
            coeff: 系数参数，默认 `1.0`
            AP: ATR 计算周期，默认 `14`
            novolumedata: 布尔值，控制是否禁用成交量数据，默认 `False`
            **kwargs: 其他扩展参数

        Returns:
            包含 `AlphaTrend`（趋势线）、`AlphaTrend2`（延迟趋势线）、`long_signal`（多头信号）、`short_signal`（空头信号）的指标数据
        """
        return AlphaTrend(self._kline, coeff=coeff, AP=AP, novolumedata=novolumedata, **kwargs)

    def Volume_Flow_Indicator(self, length=130, coef=0.2, vcoef=2.5, signalLength=5, smoothVFI=False, **kwargs) -> IndFrame:
        """
        ## 成交量流量指标

        ### 📘 **文档参考**:
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
        return Volume_Flow_Indicator(self._kline, length=length, coef=coef, vcoef=vcoef, signalLength=signalLength, smoothVFI=smoothVFI, **kwargs)

    def Chandelier_Exit(self, length=22, mult=3., useClose=True, **kwargs) -> IndFrame:
        """
        ## 吊灯出场指标

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.18_chandelier_exit/
        - ✈ https://cn.tradingview.com/script/AqXxNS7j-Chandelier-Exit/

        Args:
            length: 周期参数，默认 `22`
            mult: ATR 乘数，默认 `3.0`
            useClose: 布尔值，控制是否用收盘价计算，默认 `True`
            **kwargs: 其他扩展参数

        Returns:
            包含 `up`（上轨止损线）、`dn`（下轨止损线）、`long_signal`（多头信号）、`short_signal`（空头信号）的指标数据
        """
        return Chandelier_Exit(self._kline, length=length, mult=mult, useClose=useClose, **kwargs)

    def SuperTrend_STRATEGY(self, Periods=10, Multiplier=3., changeATR=True, **kwargs) -> IndFrame:
        """
        ## 超级趋势策略

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.19_supertrend_strategy/
        - ✈ https://cn.tradingview.com/script/P5Gu6F8k/

        Args:
            Periods: ATR 计算周期，默认 `10`
            Multiplier: ATR 乘数，默认 `3.0`
            changeATR: 布尔值，控制是否改变 ATR 计算方式，默认 `True`
            **kwargs: 其他扩展参数

        Returns:
            包含 `up`（上轨趋势线）、`dn`（下轨趋势线）、`long_signal`（多头信号）、`short_signal`（空头信号）的策略数据
        """
        return SuperTrend_STRATEGY(self._kline, Periods=Periods, Multiplier=Multiplier, changeATR=changeATR, **kwargs)

    def Optimized_Trend_Tracker(self, length=2, var_length=9, percent=1.4, base=200, **kwargs) -> IndFrame:
        """
        ## 优化的趋势跟踪指标

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.20_optimized_trend_tracker/
        - ✈ https://cn.tradingview.com/script/zVhoDQME/

        Args:
            length: 基础周期，默认 `2`
            var_length: 变异周期，默认 `9`
            percent: 百分比参数，默认 `1.4`
            base: 基础参考值，默认 `200`
            **kwargs: 其他扩展参数

        Returns:
            包含 `MT`（主趋势线）、`OTT`（优化趋势跟踪线）的指标数据
        """
        return Optimized_Trend_Tracker(self._kline, length=length, var_length=var_length, percent=percent, base=base, **kwargs)

    def TonyUX_EMA_Scalper(self, length=20, period=8, **kwargs) -> IndFrame:
        """
        ## TonyUX EMA 剥头皮策略

        ### 📘 **文档参考**:
        ✈ https://cn.tradingview.com/script/egfSfN1y-TonyUX-EMA-Scalper-Buy-Sell/

        Args:
            length: EMA 计算周期，默认 `20`
            period: 价格高低点统计周期，默认 `8`
            **kwargs: 其他扩展参数

        Returns:
            包含 `lasth`（近期高点）、`lastl`（近期低点）、`long_signal`（多头信号）、`short_signal`（空头信号）的策略数据
        """
        return TonyUX_EMA_Scalper(self._kline, length=length, period=period, **kwargs)

    def Turtle_Trade_Channels_Indicator_TUTCI(self, length=20, len2=10, **kwargs) -> IndFrame:
        """
        ## 海龟交易通道指标

        ### 📘 **文档参考**:
        - ✈ https://www.minibt.cn/minibt_tradingview_indicators/3.21_turtle_trade_channels_indicator/
        - ✈ https://cn.tradingview.com/script/pB5nv16J/

        Args:
            length: 主通道周期，默认 `20`
            len2: 辅助通道周期，默认 `10`
            **kwargs: 其他扩展参数

        Returns:
            包含 `sup`（上通道）、`sdown`（下通道）、`K`（关键趋势线）、`long_signal`（多头信号）、`short_signal`（空头信号）的指标数据
        """
        return Turtle_Trade_Channels_Indicator_TUTCI(self._kline, length=length, len2=len2, **kwargs)
