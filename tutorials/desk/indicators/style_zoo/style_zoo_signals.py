# -*- coding: utf-8 -*-
"""StyleZoo_Signals —— **交易信号文字**样式大全（P195–P197 新增能力）

和 `style_zoo_main` 的区别：那边演示"固定文字"（`set_label('买')`），
这里演示**逐点文字**：

1. `signal_text()` —— 指标方法，返回 `{信号名: 与 K 线等长的文本数组}`
   （约定与 `tradingview.AutoChartPatterns.signal_text()` 一致）；
2. `SignalStyle.set_text_style(...)` —— 逐点文字的字体 / 颜色 / 边框；
3. `SignalStyle(size=…)` —— 箭头大小的**引擎默认**（bokeh 12 / pylightcharts 8）；
4. `Markers.arrow_up` / `arrow_down` —— 真·箭头（三角头 + 竖杆）；
   `Markers.triangle` / `inverted_triangle` —— 实心三角（信号里也画成箭头）。

数据上它只是两条均线 + 金叉死叉，**重点是箭头旁边的文字**。
"""
from __future__ import annotations

import numpy as np

from minibt import *                                          # noqa: F401,F403
from minibt import BtIndicator, Colors, Markers, SignalStyle


def _sma(values, length: int):
    length = max(1, int(length))
    out = np.full(values.shape[0], np.nan)
    if values.shape[0] < length:
        return out
    kernel = np.ones(length) / length
    conv = np.convolve(values, kernel, mode='valid')
    out[length - 1:] = conv
    return out


class StyleZoo_Signals(BtIndicator):
    """信号文字大全：逐点数值 / 固定文字 / 字号 / 颜色 / 箭头形状"""

    lines = ('ma_fast', 'ma_slow', 'long_signal', 'short_signal')
    params = dict(fast=10, slow=30)
    #: 均线叠主图；信号列**不要**写 `isplot=False`（写了会被当成纯数据列跳过 ✗）
    #: 只要在 `signalstyle` 里声明，就会被识别成"箭头列" ✓
    overlap = dict(ma_fast=True, ma_slow=True)

    linestyle = dict(
        ma_fast=LineStyle(line_color=Colors.lime, line_width=2),
        ma_slow=LineStyle(line_color=Colors.tomato, line_width=2,
                          price_line=False),
    )

    #: 箭头：显式 `size` + 固定文字（逐点文字会覆盖它 ✓）
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.lime, Markers.arrow_up,
                                size=12).set_label('B', 12,
                                                   color=Colors.lime),
        short_signal=SignalStyle('high', Colors.tomato, Markers.arrow_down,
                                 size=12).set_label('S', 12,
                                                    color=Colors.tomato),
    )

    def next(self):
        close = np.asarray(self.close.values, dtype=float)
        fast = _sma(close, self.params.fast)
        slow = _sma(close, self.params.slow)
        diff = fast - slow
        prev = np.concatenate(([np.nan], diff[:-1]))
        long_signal = np.where((diff > 0) & (prev <= 0), 1.0, 0.0)
        short_signal = np.where((diff < 0) & (prev >= 0), 1.0, 0.0)
        return fast, slow, long_signal, short_signal

    def signal_text(self) -> dict | None:
        """逐点文字 = **信号点上快慢线的差值**（带正负号）✓

        ⚠ 这个方法在 `IndFrame` 上被调用（minibt 会把指标实例换成 IndFrame），
        取列值要用 `self['列名']`；`self.ma_fast` 这类名字可能是 KLine 的方法。
        """
        def _decode(signals, fast, slow) -> np.ndarray:
            values = np.asarray(getattr(signals, 'values', signals),
                                dtype=float)
            f = np.asarray(getattr(fast, 'values', fast), dtype=float)
            s = np.asarray(getattr(slow, 'values', slow), dtype=float)
            out = np.full(values.shape[0], np.nan, dtype=object)
            for index, value in enumerate(values):
                if value != value or value == 0:
                    continue                     # NaN / 0 = 没有信号
                gap = f[index] - s[index]
                if gap == gap:                   # 非 NaN
                    out[index] = f'{gap:+.2f}'   # 例：+1.83 / -2.40
            return out

        try:
            fast = self['ma_fast']
            slow = self['ma_slow']
            return {'long_signal': _decode(self['long_signal'], fast, slow),
                    'short_signal': _decode(self['short_signal'], fast, slow)}
        except Exception:                                        # noqa: BLE001
            return None
