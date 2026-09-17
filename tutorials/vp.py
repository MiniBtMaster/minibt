from minibt import *

KLINE = LocalDatas.v2601_300.kline


class VPMode1(Strategy):
    """用法①：主图纯 VP 图"""

    def __init__(self):
        self.kline = KLINE
        # 滚动窗口 100 根 / 40 个价格档 / 档位区间取每根最近 500 根的价格范围
        self.vp = KLINE.tradingview.RollingVolumeProfile(
            length=100, bins=40, price_bars=500)


class VPMode2(Strategy):
    """用法②：主图 指标线 + VP 图"""

    def __init__(self):
        self.kline = KLINE
        # length=100 统计窗口 / bins=40 档 / ma_len=20 均线周期
        self.vp = KLINE.tradingview.VolumeProfileMA(
            length=100, bins=40, ma_len=20)


class VPMulti(Strategy):
    def __init__(self):
        self.kline = KLINE
        # 短周期：偏红；长周期：偏蓝（靠颜色区分两套分布）
        self.vp_short = KLINE.tradingview.RollingVolumeProfile(
            length=40, bins=30, price_bars=200,
            vp_color='#e74c3c', vp_poc_color='#c0392b', name='VP短40')
        self.vp_long = KLINE.tradingview.RollingVolumeProfile(
            length=200, bins=30, price_bars=600,
            vp_color='#3498db', vp_poc_color='#f39c12', name='VP长200')


class VPMode3(Strategy):
    """用法③：副图 指标线 + VP 图"""

    def __init__(self):
        self.kline = KLINE
        # ★ 关键就是 overlap=False：另开副图
        self.vp = VPRsi(self.kline,
                        length=100, bins=40, ma_len=20, overlap=False)


class VPRsi(BtIndicator):
    """RSI 指标线 + 2 档"分布"，画在副图。"""

    category = 'vp'                    # ★ 走 VP 专门绘制分支
    overlap = False                    # ★ 副图
    lines = ('rsi', 'vp0', 'vp1')      # ★ 'vp' 前缀之前=指标线, 之后=VP 数据块
    isplot = {'rsi': True, 'vp0': False, 'vp1': False}   # ★ 分布列不画折线
    params = dict(length=14)

    def next(self):                    # ★ 必须是 next()，不能写在 __init__ 里
        length = max(1, int(self.p.length))          # self.p 等价 self.params
        rsi = np.asarray(self.close.rsi(length), dtype=np.float64)

        up = np.nan_to_num((rsi >= 50.).astype(np.float64))
        dn = np.nan_to_num((rsi < 50.).astype(np.float64))
        n = len(rsi)
        # 前缀和：一次算完所有时刻的滚动窗口计数
        c_up = np.concatenate([[0.0], np.cumsum(up)])
        c_dn = np.concatenate([[0.0], np.cumsum(dn)])
        win_lo = np.maximum(0, np.arange(n) - length + 1)
        idx = np.arange(n) + 1
        return np.c_[rsi, c_up[idx] - c_up[win_lo], c_dn[idx] - c_dn[win_lo]]


if __name__ == "__main__":
    Bt().run()
