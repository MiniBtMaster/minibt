"""行情表（DataGrid）：TradingView 风格的市场数据表。

这是「行情表全家桶」的第一个可运行例子：一张**可排序 / 搜索 / 虚拟滚动**的
期货行情表，每行还带一条迷你走势（Sparkline）。

覆盖的能力：

- 列类型 ``number``（千分位 / 万·亿）、``percent``（带正负号 + %）、
  ``change``（按符号着色）、``spark``（行内迷你图）；
- ``color_by='sign'`` + ``color_scheme='cn'`` → **红涨绿跌**（``'tv'`` 则绿涨红跌）；
- 点表头排序、左上角搜索框过滤；
- 几千行也只把**可见的几十行**放进 DOM（虚拟滚动）；
- 双击某行 → 回到 Python（miniqt 里就是「双击开图」）。

运行::

    python examples/13_panels/01_data_grid.py
    python examples/13_panels/01_data_grid.py --snapshot data_grid.png
    PYLIGHTCHARTS_QT=PyQt6 python examples/13_panels/01_data_grid.py
"""
from __future__ import annotations

import argparse
import importlib
import os
import random
import sys

# --- 1. 选 Qt 绑定并加载 QtWebEngineWidgets（必须在 QApplication 之前）------
BINDING = os.environ.get('PYLIGHTCHARTS_QT') or 'PySide6'
os.environ['PYLIGHTCHARTS_QT'] = BINDING

from pylightcharts.qt import prepare_qt                      # noqa: E402

prepare_qt(BINDING)
QtCore = importlib.import_module(f'{BINDING}.QtCore')
QtWidgets = importlib.import_module(f'{BINDING}.QtWidgets')

from pylightcharts import QtPanel                            # noqa: E402
from pylightcharts.panels import Column, DataGrid            # noqa: E402

#: 品种（代码字母, 中文名）
PRODUCTS = [
    ('l', '聚乙烯'), ('pp', '聚丙烯'), ('v', 'PVC'), ('rb', '螺纹钢'),
    ('ru', '橡胶'), ('cu', '沪铜'), ('al', '沪铝'), ('zn', '沪锌'),
    ('ni', '沪镍'), ('au', '沪金'), ('ag', '沪银'), ('i', '铁矿石'),
    ('j', '焦炭'), ('jm', '焦煤'), ('m', '豆粕'), ('y', '豆油'),
    ('p', '棕榈油'), ('c', '玉米'), ('cf', '棉花'), ('sr', '白糖'),
]
EXCHANGES = ['DCE', 'SHFE', 'CZCE']


def make_rows(count: int = 800, seed: int = 7) -> list:
    """自包含合成行情数据（换成天勤 / ``minibt.LocalDatas`` 即可接真实数据）。"""
    rng = random.Random(seed)
    rows = []
    for i in range(count):
        code, name = PRODUCTS[i % len(PRODUCTS)]
        last = 1000 + rng.random() * 9000
        change = (rng.random() - 0.5) * 200
        prev = last - change
        spark = []
        value = last
        for _ in range(40):
            value += (rng.random() - 0.5) * last * 0.01
            spark.append(round(value, 1))
        rows.append({
            'symbol': f'{EXCHANGES[i % 3]}.{code}2601',
            'name': name,
            'exchange': EXCHANGES[i % 3],
            'last': round(last),
            'chg': round(change),
            'chg_pct': round(change / prev * 100, 2),
            'open': round(prev + (rng.random() - 0.5) * 30),
            'high': round(last + rng.random() * 40),
            'low': round(last - rng.random() * 40),
            'pre_close': round(prev),
            'volume': rng.randint(0, 300000),
            'open_interest': rng.randint(0, 600000),
            'spark': spark,
        })
    return rows


def make_columns() -> list:
    return [
        Column('symbol', '代码', width=1.4),
        Column('name', '名称', width=1.2),
        Column('last', '最新', type='number', color_by='sign'),
        Column('chg', '涨跌', type='change'),
        Column('chg_pct', '涨跌幅', type='percent'),
        Column('open', '开盘', type='number'),
        Column('high', '最高', type='number'),
        Column('low', '最低', type='number'),
        Column('volume', '成交量', type='number', compact=True, width=1.1),
        Column('open_interest', '持仓量', type='number', compact=True, width=1.1),
        Column('spark', '走势', type='spark', width=1.4),
    ]


def build(panel: QtPanel) -> DataGrid:
    """Create the market table on an existing :class:`QtPanel`."""
    grid = DataGrid(
        panel.win,
        make_columns(),
        row_key='symbol',
        color_scheme='cn',                 # 红涨绿跌
        searchable=True,
        on_row_double_click=lambda key: print(f'[example] 双击 {key}（这里可开图）'),
    )
    grid.set_rows(make_rows())
    grid.sort('chg_pct', direction=-1)     # 先按涨跌幅降序
    return grid


def main() -> None:
    parser = argparse.ArgumentParser(description='DataGrid 行情表示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None,
                        help='渲染后截图到文件并退出（不显示窗口）')
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()
    build(panel)
    view = panel.get_webview()

    if args.snapshot:
        view.resize(1280, 760)
        # 离屏环境下 webview 视口可能是 0：显式给容器一个高度，让虚拟滚动
        # 按真实高度渲染（真实窗口里不需要这一步）。
        panel.win.run_script(
            "document.getElementById('container').style.height='760px';"
            "window.dispatchEvent(new Event('resize'));")

        def shoot() -> None:
            pixmap = view.grab()
            if pixmap.save(args.snapshot):
                print(f'[example] 已保存截图: {args.snapshot}')
            else:
                print('[example] 截图保存失败')
            app.quit()

        QtCore.QTimer.singleShot(3500, shoot)
    else:
        view.show()

    app.exec()


if __name__ == '__main__':
    main()
