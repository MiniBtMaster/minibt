"""7.2 · lines / line_filed / signallines —— 列名、顺序、信号识别

演示要点
--------
* ``lines`` 就是「数据列名 + 顺序」：``next()`` 返回的第 1 个值进 ``lines[0]``，
  第 2 个进 ``lines[1]`` ……**顺序错位不会报错，但线会张冠李戴**；
* 框架内部用 ``line_filed``（每列前面加 ``_``，如 ``_ema_fast``）存数据，
  这个名字同时决定**指标参数/数据源**（见 8.10）；
* ``signallines`` **不用手写**：``lines`` 里只要出现
  ``long_signal / exitlong_signal / short_signal / exitshort_signal``
  四个名字，就自动被认成信号线；
* ``lines`` 还可以**不写**：框架会从 ``next()`` 的 ``return`` 语句自动解析 ——
  但 ``return`` 里必须写**变量**（直接写表达式会解析出 ``emalength=5`` 这种怪名字）；
* 另一种写法：**不 return**，直接给 ``self.lines.xxx`` 赋值（列名 = 赋值顺序）。

运行：``python tutorials/styles/02_lines.py``
文档：``minibt_docs/docs/minibt_styles/7.2_lines.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


class LineNames(BtIndicator):
    """4 条线：2 条均线（主图）+ 2 个信号（不画线，只落图标）。"""

    # ① 顺序 = next() 返回值的顺序
    lines = ('ema_fast', 'ema_slow', 'long_signal', 'short_signal')
    params = dict(FAST=7, SLOW=25)

    # ② 均线叠主图；信号线不画折线
    overlap = dict(ema_fast=True, ema_slow=True)
    isplot = dict(long_signal=False, short_signal=False)

    linestyle = dict(
        ema_fast=LineStyle(line_color=Colors.orange, line_width=2),
        ema_slow=LineStyle(line_color=Colors.blue, line_width=2,
                           line_dash=LineDash.dashed),
    )
    # ③ 四个信号名是「保留名字」，会被自动收进 signallines
    signalstyle = dict(
        long_signal=SignalStyle('low', Colors.red,
                                Markers.triangle).set_label('B'),
        short_signal=SignalStyle('high', Colors.green,
                                 Markers.inverted_triangle).set_label('S'),
    )

    def next(self):
        p = self.params
        ema_fast = self.close.ema(p.FAST)
        ema_slow = self.close.ema(p.SLOW)
        return (ema_fast,
                ema_slow,
                ema_fast.cross_up(ema_slow),
                ema_fast.cross_down(ema_slow))


class AutoLines(BtIndicator):
    """不写 ``lines``：框架从 ``next()`` 的 return **变量名**自动解析列名。"""

    def next(self):
        # ★ 必须先赋给变量：直接 `return self.close.ema(5), ...` 解析出的是
        #   表达式文本（如 `emalength=5`），不是合法的列名
        ema5 = self.close.ema(5)
        ema20 = self.close.ema(20)
        return ema5, ema20


class AssignLines(BtIndicator):
    """另一种写法：**不 return**，直接给 ``self.lines.xxx`` 赋值。

    ★ 限制（见 7.2）：
      * ``next()`` 不能再返回值（会报 lines 数量不匹配）；
      * ``self.lines`` 挂在当前 KLine 上：同一个 KLine 上再建第二个
        “赋值式”指标，会把前一个的线也带上 → 各自用独立 KLine。
    """

    def next(self):
        self.lines.ema5 = self.close.ema(5)
        self.lines.ema20 = self.close.ema(20)


def main(gui=None):
    kline = LocalDatas.test.kline

    ind = LineNames(kline)
    info = ind.plotinfo
    print('① lines       =', list(info.lines))
    print('② line_filed  =', list(info.line_filed))
    print('③ signallines =', [str(x) for x in info.signallines])

    # 自动解析：返回值的变量名直接变成列名（`a, b = next()` 也一样）
    # 用一个**单独的** kline，避免它被混进上面那张图
    auto = AutoLines(LocalDatas.l2609_60.kline)
    print('④ AutoLines.lines =', list(auto.plotinfo.lines))

    # 赋值式：不 return，列名 = 赋值顺序（同样用单独的 kline）
    assign = AssignLines(LocalDatas.pp2609_60.kline)
    print('⑤ AssignLines.lines =', list(assign.plotinfo.lines))

    ind.btplot(gui=gui)


if __name__ == '__main__':
    main()
