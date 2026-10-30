"""7.21 · 绘图入口参数 —— btplot / run / backtest 的图相关参数

演示要点
--------
同一份 ``PlotInfo`` 样式，换入口时还有一排**图级**参数。最常用的是价格轴留白
``y_margin``：

| 参数 | 入口 | 说明 |
| --- | --- | --- |
| ``y_margin`` | `btplot` / `run` / `backtest` | 价格轴上下留白（面板高度比例，不是像素） |
| ``include`` | `btplot` | ``'all'``（默认，整条源链）/ ``'last'``（只画最后一个指标） |
| ``display`` | `btplot` | ``'auto'`` / ``'inline'``（Notebook）/ ``'external'`` |
| ``gui`` | 全部 | ``'pylightcharts'``（默认）/ ``'pylightcharts_web'`` / ``'bokeh'`` / ``'jupyter'`` |
| ``theme`` | `btplot` / `run` | ``'light'`` / ``'dark'`` |
| ``grid`` / ``toolbox`` | `btplot` / `Config` | 网格 / 工具栏 |
| ``volume_mode`` | `btplot` / `Config` | ``'overlay'`` / ``'sub'`` / ``'both'`` / ``'none'`` |
| ``data_length`` / ``history_length`` | `run` | 只算最近 N 根 / 无限历史窗口 |
| ``isplot`` / ``isreport`` | `run` | 画不画图 / 要不要 QuantStats 报告 |

``y_margin`` 取值：

* ``None``（默认）→ ``Config.y_margin``，都没有就 **0.1**（上下各 10%）；
* 单个数字 → 上下同值；
* ``(top, bottom)`` → 分别设置；``0.0`` = 铺满。

本例把留白放大到 ``(0.2, 0.1)``（lightweight-charts 原样），对比默认的 0.1。

运行：``python tutorials/styles/21_run_params.py``
文档：``minibt_docs/docs/minibt_styles/7.21_run_params.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *
from minibt.utils import DEFAULT_Y_MARGIN


class ParamDemo(BtIndicator):
    """简单两条均线，方便看"价格占面板多少"。"""

    lines = ('ema_fast', 'ema_slow')
    overlap = True
    linestyle = dict(
        ema_fast=LineStyle(line_color=Colors.orange, line_width=1.5),
        ema_slow=LineStyle(line_color=Colors.blue, line_width=1.5),
    )

    def next(self):
        return self.close.ema(20), self.close.ema(60)


def main(gui=None):
    print('DEFAULT_Y_MARGIN =', DEFAULT_Y_MARGIN)
    ind = ParamDemo(LocalDatas.test.kline)
    # 放大上下留白（对比默认 0.1）
    ind.btplot(gui=gui, y_margin=(0.2, 0.1))


if __name__ == '__main__':
    main()
