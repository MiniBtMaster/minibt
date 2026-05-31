"""
MiniBT 实盘运行 — 三种模式示例
================================
演示 `Bt(live=True)` 的三种实盘运行方式，适合不同部署场景。

运行前需修改owenhellen密码，并可通过注释/取消注释来切换模式。

参考文档：minibt_docs/docs/minibt_basic/1.21minibt_realtime_trading_modes.md
"""
from minibt import *


# ====================================================================
# 策略定义（可根据实际需要替换）
# ====================================================================

class CCI(BtIndicator):
    """CCI（商品通道指数）— 均值回归型指标
    参考：https://www.shinnytech.com/articles/trading-strategy/mean-reversion/cci-strategy
    """
    isplot = dict(long_signal=False, short_signal=False)
    params = dict(CCI_PERIOD=10, CCI_UPPER=100, CCI_LOWER=-100)

    def next(self):
        p = self.params
        cci = self.close.cci(p.CCI_PERIOD)
        size = cci.size
        cci_state = np.ones(size)
        for i in range(p.CCI_PERIOD + 1, size):
            cci_state[i] = cci[i] > p.CCI_UPPER and 1. or (
                cci[i] < p.CCI_LOWER and -1. or cci_state[i - 1])
        cci_state = IndSeries(cci_state)
        long_signal = cci_state.cross_up(0.)
        short_signal = cci_state.cross_down(0.)
        return cci, long_signal, short_signal


class CCIStrategy(Strategy):
    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline("SHFE.ag2606", data_length=1000, height=500)
        self.cci = CCI(self.data)
        self.gc = self.data.btind.gaussian_smoothed()

    def next(self):
        if not self.data.position:
            if self.cci.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.cci.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


class CMO(BtIndicator):
    """CMO（钱德动量振荡器）— 趋势跟踪型指标
    参考：https://www.shinnytech.com/articles/trading-strategy/trend-following/cmo-strategy
    """
    params = dict(CMO_PERIOD=6, SIGNAL_PERIOD=4, CMO_SLOPE_PERIOD=2,
                  OVERBOUGHT_THRESHOLD=50, OVERSOLD_THRESHOLD=-50, SMA_PERIOD=10)
    isplot = dict(cmo_slope=False, long_signal=False, short_signal=False)
    overlap = dict(sma=True, cmo=False, cmo_signal=False)

    def next(self):
        p = self.params
        cmo = self.close.cmo(p.CMO_PERIOD)
        cmo_signal = cmo.sma(p.SIGNAL_PERIOD)
        cmo_slope = cmo.diff(p.CMO_SLOPE_PERIOD)
        sma = self.close.sma(p.SMA_PERIOD)
        long_signal = cmo.cross_up(p.OVERSOLD_THRESHOLD)
        long_signal |= cmo.cross_up(cmo_signal)
        long_signal |= cmo.cross_up(0.)
        short_signal = cmo.cross_down(p.OVERBOUGHT_THRESHOLD)
        short_signal |= cmo.cross_down(cmo_signal)
        short_signal |= cmo.cross_down(0.)
        return sma, cmo, cmo_signal, cmo_slope, long_signal, short_signal


class CMOStrategy(Strategy):
    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline("SHFE.cu2606", data_length=1000, height=500)
        self.trix = CMO(self.data)

    def next(self):
        if not self.data.position:
            if self.trix.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.trix.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


# ====================================================================
# 实盘运行入口：三种模式演示
# ====================================================================

if __name__ == "__main__":
    # ------------------------------------------------------------------
    # 公共初始化：创建实盘 Bt 实例，添加策略，配置天勤认证
    # ------------------------------------------------------------------
    bt = Bt(live=True)
    bt.addstrategy(CCIStrategy, CMOStrategy)
    bt.addTqapi(tq_auth=tq_auth(
        user_name="owenhellen", password="owen2553832"
    ))

    # ------------------------------------------------------------------
    # 以下是三种实盘运行模式，根据需求选择其一（注释掉不用的即可）：
    # ------------------------------------------------------------------

    # 【模式一】图表模式（默认 isplot=True）
    #   启动 LightChart GUI 实时图表窗口，支持K线、指标、信号可视化。
    #   适合本地盯盘、策略调试。
    #   特点：1个进程，1个TqApi连接，所有策略共享同一个图表界面。
    bt.run()

    # 【模式二】后台串行模式
    #   不启动任何 GUI，所有策略在单进程内串行执行，共享一个 TqApi 连接。
    #   适合资源受限的服务器环境、策略数量不多的场景。
    #   特点：无窗口、低资源占用，Ctrl+C 优雅退出。
    # bt.run(isplot=False)

    # 【模式三】并行模式
    #   每个策略启动一个独立子进程，各自拥有独立的 Bt 实例和 TqApi 连接。
    #   适合策略数量多、策略间需要进程级隔离的场景。
    #   特点：任一策略崩溃不影响其他策略，充分利用多核 CPU。
    # bt.run(isplot=False, run_parallel=True)

    # ------------------------------------------------------------------
    # 注意：
    #   1. 以上三行 run() 调用不要同时取消注释，每次只选一种模式运行。
    #   2. 三种模式可传入相同的可选参数：
    #      - period_milliseconds: K线轮询间隔（毫秒），默认 1000
    #      - period_seconds:       K线轮询间隔（秒），与 period_milliseconds 二选一
    # ------------------------------------------------------------------
