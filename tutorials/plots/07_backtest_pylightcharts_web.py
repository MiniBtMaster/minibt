"""07 · 网页版回测 —— 布林带 + 逐点信号文本

模式：**pylightcharts_web 引擎 + 回测**
运行：``python tutorials/plots/07_backtest_pylightcharts_web.py``

本示例重点演示 **`signal_text()` 钩子 + `SignalText` 逐点文本**（1.2.8）：

* 不同信号点显示**不同内容**；文本里用 ``"\\n"`` 表达**多行**（多头向下、空头向上展开）；
* 文本样式可选用内置 ``black`` / ``white`` 预设或 ``set_text_style`` 自定义；
* 附带演示蜡烛型指标的 ``candlestyle``（1.2.8）与 ``watermark``。

切换提示：``gui=Gui.PylightchartsWeb`` → ``Gui.Pylightcharts`` / ``Gui.Bokeh``；
``replay=True`` 即回放，``live=True`` 即实时。
"""

import numpy as np

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class BollingerSignals(BtIndicator):
    """布林带：下轨回升做多、上轨回落做空，信号点标注带宽与 %B。"""

    lines = ('mid', 'upper', 'lower', 'long_signal', 'short_signal')
    params = dict(PERIOD=20, DEV=2.0)
    isplot = dict(long_signal=False, short_signal=False)
    overlap = dict(mid=True, upper=True, lower=True)
    bandstyle = [BandStyle('lower', 'upper', fill_color='#4dabf7', fill_alpha=0.08)]
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red, Markers.triangle),
        short_signal=SignalStyle('high', Colors.green, Markers.inverted_triangle),
    )

    def next(self):
        p = self.params
        mid = self.close.sma(p.PERIOD)
        # [1.2.9] Pine 接口的总体标准差
        std = self.close.pine.stdev(p.PERIOD)
        upper = mid + std * p.DEV
        lower = mid - std * p.DEV
        long_signal = self.close.cross_up(lower)
        short_signal = self.close.cross_down(upper)
        return mid, upper, lower, long_signal, short_signal

    def signal_text(self):
        """[1.2.8] 逐点文本：第一行价格，第二行 %B（可多行）。"""
        # 自定义文本样式（也可用内置 black / white 预设）
        self.signaltext.set_text_style(
            text_color='white', background_fill_color='#1f6feb',
            background_fill_alpha=0.85)
        n = self.size
        mid = np.asarray(self.mid.values, dtype=float)
        up = np.asarray(self.upper.values, dtype=float)
        dn = np.asarray(self.lower.values, dtype=float)
        close = np.asarray(self.close.values, dtype=float)
        pctb = (close - dn) / np.where(up - dn == 0, np.nan, up - dn) * 100.0
        out = {k: np.full(n, np.nan, dtype=object)
               for k in ('long_signal', 'short_signal')}
        for k in out:
            idx = self[k].idx()
            if idx.size:
                out[k][idx] = [f"{close[i]:.0f}\n{pctb[i]:.0f}%"
                               for i in idx]
        return out


class BollingerSignalsStrategy(Strategy):
    config = Config(theme='dark', volume_mode='overlay')

    def __init__(self):
        self.data = self.get_kline(LocalDatas.test, height=500)
        self.data.watermark = 'BOLL'
        self.ind = BollingerSignals(self.data)

    def next(self):
        if not self.data.position:
            if self.ind.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.ind.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


if __name__ == '__main__':
    Bt().run(gui=Gui.PylightchartsWeb)    # ⑦ 网页版回测
