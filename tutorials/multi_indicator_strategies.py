from minibt import *


class CCI(BtIndicator):
    """CCI（Commodity Channel Index，商品通道指数）指标
    策略原理：https://www.shinnytech.com/articles/trading-strategy/mean-reversion/cci-strategy
    均值回归型策略：当CCI从超买/超卖区域回到正常区域时产生信号
    """
    isplot = dict(long_signal=False, short_signal=False)
    params = dict(CCI_PERIOD=10, CCI_UPPER=100, CCI_LOWER=-100)

    def next(self):
        p = self.params  # 使用类级别params
        CCI_PERIOD = p.CCI_PERIOD  # CCI计算周期
        CCI_UPPER = p.CCI_UPPER  # CCI上轨
        CCI_LOWER = p.CCI_LOWER  # CCI下轨
        cci = self.close.cci(CCI_PERIOD)
        size = cci.size
        cci_state = np.ones(size)  # self.ones
        for i in range(CCI_PERIOD + 1, size):
            cci_state[i] = cci[i] > CCI_UPPER and 1. or (
                cci[i] < CCI_LOWER and -1. or cci_state[i - 1])
        cci_state = IndSeries(cci_state)
        long_signal = cci_state.cross_up(0.)   # CCI状态从-1上穿到1 → 做多
        short_signal = cci_state.cross_down(0.)  # CCI状态从1下穿到-1 → 做空
        return cci, long_signal, short_signal


class CCIStrategy(Strategy):
    """CCI交易策略：超买超卖回归，带分段跟踪止损"""

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(
            LocalDatas.pp2601_60, data_length=1000, height=500)
        self.cci = CCI(self.data)
        self.gc = self.data.btind.gaussian_smoothed()

    def next(self):
        if not self.data.position:
            if self.cci.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.cci.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


class CMO(BtIndicator):
    """CMO（Chande Momentum Oscillator，钱德动量振荡器）指标
    策略原理：https://www.shinnytech.com/articles/trading-strategy/trend-following/cmo-strategy
    趋势跟踪型策略：通过多条件组合（超买超卖穿越 + 信号线穿越 + 零轴穿越）生成交易信号
    """
    params = dict(CMO_PERIOD=6, SIGNAL_PERIOD=4, CMO_SLOPE_PERIOD=2,
                  OVERBOUGHT_THRESHOLD=50, OVERSOLD_THRESHOLD=-50, SMA_PERIOD=10)
    isplot = dict(cmo_slope=False, long_signal=False, short_signal=False)
    overlap = dict(sma=True, cmo=False, cmo_signal=False)

    def next(self):
        p = self.params  # 使用类级别params（self.params在框架内部不保证正确）
        cmo = self.close.cmo(p.CMO_PERIOD)
        cmo_signal = cmo.sma(p.SIGNAL_PERIOD)
        cmo_slope = cmo.diff(p.CMO_SLOPE_PERIOD)
        sma = self.close.sma(p.SMA_PERIOD)
        # 做多信号：CMO上穿超卖阈值 OR 上穿信号线 OR 上穿零轴
        long_signal = cmo.cross_up(p.OVERSOLD_THRESHOLD)
        long_signal |= cmo.cross_up(cmo_signal)
        long_signal |= cmo.cross_up(0.)
        # 做空信号：CMO下穿超买阈值 OR 下穿信号线 OR 下穿零轴
        short_signal = cmo.cross_down(p.OVERBOUGHT_THRESHOLD)
        short_signal |= cmo.cross_down(cmo_signal)
        short_signal |= cmo.cross_down(0.)

        return sma, cmo, cmo_signal, cmo_slope, long_signal, short_signal


class CMOStrategy(Strategy):
    """CMO交易策略：多条件趋势跟踪，带分段跟踪止损"""

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(
            LocalDatas.v2601_300, data_length=1000, height=500)
        self.trix = CMO(self.data)

    def next(self):
        if not self.data.position:
            if self.trix.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.trix.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    # ====================================================================
    # 运行说明：
    # 框架会自动发现文件中所有继承自 Strategy 的子类（CCIStrategy、CMOStrategy），
    # 并依次对每个策略执行回测。以下4行分别演示了4种运行模式：
    #
    # 1. 控制台回测模式：
    #    Bt().run()
    #    → 在终端/控制台中执行回测计算，输出回测统计结果，不启动GUI。
    #
    # 2. GUI回测模式（LightChart）：
    #    Bt().run(gui=Gui.LightChart)
    #    → 在LightChart图形界面中展示K线图、指标、回测结果，无replay（一次性计算全部K线）。
    #
    # 3. 控制台回测模式 + replay（逐K线回放）：
    #    Bt(replay=True).run()
    #    → 在控制台中逐根K线逐步推进回测（模拟实时交易过程），不启动GUI。
    #
    # 4. GUI回测模式 + replay（逐K线图形回放）：
    #    Bt(replay=True).run(gui=Gui.LightChart)
    #    → 在LightChart图形界面中逐K线回放，可直观观察每根K线到达时的信号触发、
    #      开平仓时机、资金曲线变化等，是最直观的调试/演示模式。
    #
    # 注意：当前4行全部取消注释时会依次运行这4种模式，实际调试时可按需
    #       注释掉不需要的行，单独运行感兴趣的模式。
    # ====================================================================

    # Bt().run()                          # 模式1：Bokeh 图表展示
    # Bt().run(gui=Gui.LightChart)        # 模式2：LightChart 图表展示
    Bt(replay=True).run()               # 模式3：K线回放，Bokeh 图表展示
    # Bt(replay=True).run(gui=Gui.LightChart)  # 模式4：K线回放，LightChart 图表展示
