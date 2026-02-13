from minibt import *


class DistanceBased(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/mean-reversion/distance-based-strategy"""
    overlap = False

    def next(self):
        price_x = self.v_close
        price_y = self.pp_close
        window = 30
        K_THRESHOLD = 2.
        norm1 = price_x.zscore(window)
        norm2 = price_y.zscore(window)
        spread = norm1 - norm2
        mean_spread = spread.sma(window)
        std_spread = spread.stdev(window)
        up = mean_spread+K_THRESHOLD*std_spread
        dn = mean_spread-K_THRESHOLD*std_spread
        return spread, up, dn


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.pp2601_60, height=500)
        self.data1 = self.get_kline(LocalDatas.l2601_60, height=500)
        self.data2 = IndFrame(
            dict(v_close=self.data.close.values, pp_close=self.data1.close.values))
        self.distance_based = DistanceBased(self.data2)
        self.data.fixed_commission = 1.
        self.data1.fixed_commission = 1.
        self.POS_PCT = 0.05
        self.OPEN_H = 2.0
        self.OPEN_L = -2.0
        self.CLOSE_H = 0.5
        self.CLOSE_L = -0.5
        self.POSITION_RATIO = 1.

    def next(self):
        if not self.data.position:
            if self.distance_based.spread.new < self.distance_based.dn.new:
                lots = int(self.account.available *
                           self.POS_PCT / self.data1.margin)
                price_ratio = self.data1.close.new / self.data.close.new
                trade_ratio = round(price_ratio * self.POSITION_RATIO, 2)
                lots_x = int(lots * trade_ratio)
                if lots > 0 and lots_x > 0:
                    self.data.set_target_size(lots)
                    self.data1.set_target_size(-lots_x)
            elif self.distance_based.spread.new > self.distance_based.up.new:
                lots = int(self.account.available *
                           self.POS_PCT / self.data1.margin)
                price_ratio = self.data1.close.new / self.data.close.new
                trade_ratio = round(price_ratio * self.POSITION_RATIO, 2)
                lots_x = int(lots * trade_ratio)
                if lots > 0 and lots_x > 0:
                    self.data.set_target_size(-lots)
                    self.data1.set_target_size(lots_x)
        else:
            if self.CLOSE_L < self.distance_based.spread.new < self.CLOSE_H:
                self.data.set_target_size(0)
                self.data1.set_target_size(0)


if __name__ == "__main__":
    Bt().run()
