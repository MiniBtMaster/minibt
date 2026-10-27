"""浏览器查看（静态）：一个自包含 HTML 文件，双击就能看。

    python examples/12_browser/static.py

主图放一个指标（SMA 20），副图放一个指标（RSI 14，`pane_index='new'` 自动
新建 pane）。页面 = 引擎 + 桥 + 样式 + 本次所有调用，全部内联进**单个 .html**：
不需要服务器、不需要 Node/npm、没有任何额外依赖 —— 适合回测报告与分享。

静态页没有 Python 桥，所以控件回调只会派发 `pylightcharts-callback` DOM 事件
（前端 JS 可监听）；实时看盘见同目录的 `live.py`。
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import BrowserChart

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'browser_static.html')


def make_data(rows: int = 400, seed: int = 1212) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.8)
    open_ = close + rng.standard_normal(rows) * 0.4
    return pd.DataFrame({
        'time': pd.date_range('2023-01-01', periods=rows, freq='D'),
        'open': open_,
        'high': np.maximum(open_, close) + np.abs(rng.standard_normal(rows)) *
        0.6,
        'low': np.minimum(open_, close) - np.abs(rng.standard_normal(rows)) * 0.6,
        'close': close,
        'volume': rng.integers(1_000, 50_000, rows),
    })


def build(chart) -> None:
    """主图一个指标 + 副图一个指标（两个例子共用这套构图）。"""
    chart.set(make_data())
    chart.legend(True)
    # 主图指标：叠加在 K 线上
    chart.add_sma('close', 20, color='#FF9800')
    # 副图指标：RSI 默认 pane_index='new'，自动新建一个 pane
    chart.add_rsi(14, pane_index='new')


def main() -> None:
    # 静态模式（默认）：show() 把页面写到 path 并打开浏览器
    chart = BrowserChart(width=1200, height=760, path=OUT)
    build(chart)
    chart.show()
    print('已写出浏览器页面:', OUT)
    print('（单个文件、无需服务器：可以直接双击打开、发邮件或挂到静态站点）')
    print('想要字符串或自定义落盘位置：chart.to_html() / chart.save_html(path)')


if __name__ == '__main__':
    main()
