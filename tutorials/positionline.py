from minibt import BtIndicator,np
DEBUG_POSITION_LINE_PRICE=14550
# class PositionLine(BtIndicator):
#     lines=('pl',)
#     isplot=True
#     legend=False
#     overlap=True

#     def next(self):
#         pl = np.full(self.length,14450)
#         return pl

class PositionLine(BtIndicator):
        """**载体线**：只当持仓线的载体（自己整条 NaN，画不出线 ✓）。

        - ``isplot = True``  → **序列照样建** ✓（primitive 需要有序列才挂得上 ✓）
        - ``legend = False`` → 左上角**不出现这一行标签** ✓（指标级开关 ✓）
        - ``next()`` 全 NaN  → 载体自己**不画线** ✓
        """
        overlap = True                 # 盖在主图上 ✓
        isplot = True                  # 序列要建出来（挂 primitive 用）✓
        legend = False                 # ★ 不显示图例标签 ✓
        lines = ('pl',)                # 线名
        params = {'price': DEBUG_POSITION_LINE_PRICE}

        def next(self):
            # 载体的使命只是「提供一条序列」→ 值**全给 NaN** ✓
            # （自己画不出线 ✓；持仓线是挂在它序列上的水平线 primitive ✓）

            array = np.full(self.length-1,np.nan)
            return np.append(array,self.params.price)