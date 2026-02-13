from minibt import *


class KalmanFilter(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/mean-reversion/kalman-filter-strategy"""
    isplot = dict(state_mean=False)
    overlap = False

    def next(self):
        price_x = self.v_close.values
        price_y = self.pp_close.values
        STATE_VAR = 0.0001
        state_mean = self.ones
        state_var = self.ones
        OBS_VAR = 0.01
        window = 60
        # 卡尔曼滤波
        size = price_x.size
        spread = self.full()
        for i in range(10, size):
            pred_var = state_var[i-1] + STATE_VAR
            k_gain = pred_var / (pred_var * price_x[i]**2 + OBS_VAR)
            state_mean[i] = state_mean[i-1] + k_gain * \
                (price_y[i] - state_mean[i-1] * price_x[i])
            state_var[i] = (1 - k_gain * price_x[i]) * pred_var
            spread[i] = price_y[i] - state_mean[i] * price_x[i]
        zscores = spread.zscore(window)
        return zscores, state_mean


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.pp2601_60, height=500)
        self.data1 = self.get_kline(LocalDatas.l2601_60, height=500)
        self.data2 = IndFrame(
            dict(v_close=self.data.close.values, pp_close=self.data1.close.values))
        self.kf = KalmanFilter(self.data2)
        self.data.fixed_commission = 1.
        self.data1.fixed_commission = 1.
        self.POS_PCT = 0.05
        self.OPEN_H = 2.0
        self.OPEN_L = -2.0
        self.CLOSE_H = 0.5
        self.CLOSE_L = -0.5

    def next(self):
        if not self.data.position:
            if self.kf.zscores.new < self.OPEN_L:
                lots = int(self.account.available *
                           self.POS_PCT / self.data1.margin)
                lots_x = int(lots * self.kf.state_mean.new * self.data1.close.new *
                             self.data1.volume_multiple / (self.data.close.new * self.data.volume_multiple))
                if lots > 0 and lots_x > 0:
                    self.data1.set_target_size(lots)
                    self.data.set_target_size(-lots_x)
            elif self.kf.zscores.new > self.OPEN_H:
                lots = int(self.account.available *
                           self.POS_PCT / self.data1.margin)
                lots_x = int(lots * self.kf.state_mean.new * self.data1.close.new *
                             self.data1.volume_multiple / (self.data.close.new * self.data.volume_multiple))
                if lots > 0 and lots_x > 0:
                    self.data1.set_target_size(-lots)
                    self.data.set_target_size(lots_x)
        else:
            if self.CLOSE_L < self.kf.zscores.new < self.CLOSE_H:
                self.data.set_target_size(0)
                self.data1.set_target_size(0)


if __name__ == "__main__":
    Bt().run()
