"""SymbolSearch：商品搜索（复刻 miniqt 顶栏的合约搜索）。

- 输入代码 / 名称即可筛选（400 行本地数据）；
- ↑↓ 选择、Enter 打开、Esc 关闭；
- 双击 / 回车 → 回调 `on_pick(item)`，通常用来**切换图表合约**。

远程模式（几千个合约）不传 `items`，改用 `on_query` + `set_results`
（后端搜索，前端只负责展示 ✓）。

运行::

    python examples/13_panels/13_symbol_search.py
    python examples/13_panels/13_symbol_search.py --check      # 只校验数据
    python examples/13_panels/13_symbol_search.py --snapshot symbol_search.png
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ★ 用仓库里的 pylightcharts（SymbolSearch 是 0.1.6 新增的插件 ✓）
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if os.path.isdir(os.path.join(_REPO, 'pylightcharts')):
    sys.path.insert(0, _REPO)

BINDING = os.environ.get('PYLIGHTCHARTS_QT') or 'PySide6'
os.environ['PYLIGHTCHARTS_QT'] = BINDING

from pylightcharts.qt import prepare_qt                      # noqa: E402

prepare_qt(BINDING)
QtCore = importlib.import_module(f'{BINDING}.QtCore')
QtWidgets = importlib.import_module(f'{BINDING}.QtWidgets')

from _sample_data import make_rows                          # noqa: E402
from pylightcharts import QtPanel                           # noqa: E402
from pylightcharts.panels import Column, DataGrid, SymbolSearch  # noqa: E402

EXCHANGES = ['CFFEX', 'SHFE', 'DCE', 'CZCE', 'INE', 'GFEX']


def make_items(count: int = 400) -> list:
    """合约池（``[{symbol, name, exchange, type}]``）"""
    rows = make_rows(count)
    items = []
    for index, row in enumerate(rows):
        exchange = EXCHANGES[index % len(EXCHANGES)]
        symbol = f'{exchange}.{row["symbol"].split(".")[-1]}'
        items.append({'symbol': symbol, 'name': row['name'],
                      'exchange': exchange, 'type': '期货'})
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description='SymbolSearch 示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    parser.add_argument('--check', action='store_true', help='只校验数据')
    args = parser.parse_args()

    items = make_items()
    if args.check:
        assert items and {'symbol', 'name'} <= set(items[0])
        hit = [item for item in items if 'rb' in item['symbol'].lower()]
        print(f'  合约池：{len(items)} 个（前 3：'
              f'{[item["symbol"] for item in items[:3]]}）')
        print(f'  搜 "rb" → {len(hit)} 个，例：{hit[0]["symbol"] if hit else "-"}')
        print('[example] SymbolSearch 数据检查通过')
        return

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()

    grid = DataGrid(panel.win, columns=[
        Column('symbol', '代码', width=1.4),
        Column('name', '名称'),
        Column('last', '最新', type='number', color_by='sign'),
    ], row_height=28)
    grid.set_rows(make_rows(120))

    search = SymbolSearch(panel.win, items=items, remote=False)
    search.on_pick(lambda item: print(f'[example] 选中 {item["symbol"]}'
                                      f'（这里切图表合约）'))
    search.on_query(lambda text: print(f'[example] 搜索 {text!r}'))
    search.open()

    view = panel.get_webview()
    if args.snapshot:
        view.resize(1100, 700)
        panel.win.run_script(
            "document.getElementById('container').style.height='700px';")

        def shoot() -> None:
            view.grab().save(args.snapshot)
            print(f'[example] 已保存截图: {args.snapshot}')
            app.quit()

        QtCore.QTimer.singleShot(3000, shoot)
    else:
        view.show()
    app.exec()


if __name__ == '__main__':
    main()
