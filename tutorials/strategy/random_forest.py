from minibt import *
from sklearn.ensemble import RandomForestClassifier
from functools import partial


class RandomForest(BtIndicator):
    """https://www.shinnytech.com/articles/trading-strategy/other/random-forest-strategy"""
    params = dict(n=75, m=0.02, length=30)
    overlap = False

    def next(self):
        n = self.params.n
        length = self.params.length
        m = self.params.m
        close = self.close
        sma = close.tqfunc.sma(length, m).bfill()
        wma = close.tqfunc.ema2(length).bfill()
        mom = close.tqfunc.trma(length).bfill()
        data = IndFrame(dict(close=close, sma=sma, wma=wma, mom=mom))

        def get_prediction_data(close, sma, wma, mom, length=30):
            # 计算慢
            try:
                x_all = list(zip(sma, wma, mom))  # 样本特征组
                y_all = list(close[i] >= close[i - 1]
                             for i in list(reversed(range(-1, -n+1 - 1, -1))))  # 样本标签组
                y_all.insert(0, False)
                # x_all:            大前天指标 前天指标 昨天指标 (今天指标)
                # y_all:   (大前天)    前天     昨天    今天      -明天-
                # 准备算法需要用到的数据
                x_train = x_all[: -1]  # 训练数据: 特征
                x_predict = x_all[-1]  # 预测数据(用本交易日的指标预测下一交易日的涨跌)
                # 训练数据: 标签 (去掉第一个数据后让其与指标隔一位对齐(例如: 昨天的特征 -> 对应预测今天的涨跌标签))
                y_train = y_all[1:]
                # n_estimators 参数: 选择森林里（决策）树的数目; bootstrap 参数: 选择建立决策树时，是否使用有放回抽样
                clf = RandomForestClassifier(
                    n_estimators=length, bootstrap=True, random_state=42)
                clf.fit(x_train, y_train)  # 传入训练数据, 进行参数训练
                return bool(clf.predict([x_predict]))  # 传入测试数据进行预测, 得到预测的结果
            except:
                return False

        predict = data.rolling_apply(get_prediction_data, n)
        return predict


class owen(Strategy):

    def __init__(self):
        self.min_start_length = 300
        self.data = self.get_kline(LocalDatas.v2601_300, height=500)
        self.random_forest = RandomForest(self.data)

    def next(self):
        if not self.data.position:
            if self.random_forest.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            else:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == "__main__":
    Bt().run()
