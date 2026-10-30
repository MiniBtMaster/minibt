"""Screener：带条件的筛选表（TradingView Screener）。

`Screener` = `DataGrid` + Python 侧多条件过滤；上面用 `Tabs` 做成预设筛选
（全部 / 涨>2% / 跌>2% / 放量），切 Tab 即换一组条件。

运行::

    python examples/13_panels/07_screener.py
    python examples/13_panels/07_screener.py --snapshot screener.png
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BINDING = os.environ.get('PYLIGHTCHARTS_QT') or 'PySide6'
os.environ['PYLIGHTCHARTS_QT'] = BINDING

from pylightcharts.qt import prepare_qt                      # noqa: E402

prepare_qt(BINDING)
QtCore = importlib.import_module(f'{BINDING}.QtCore')
QtWidgets = importlib.import_module(f'{BINDING}.QtWidgets')

from _sample_data import make_rows                           # noqa: E402
from pylightcharts import QtPanel                            # noqa: E402
from pylightcharts.panels import (Column, FilterBar, Screener,  # noqa: E402
                                   Tabs)

#: (key, label, conditions)
PRESETS = [
    ('all', '全部', []),
    ('up', '涨>2%', [('chg_pct', '>', 2)]),
    ('down', '跌>2%', [('chg_pct', '<', -2)]),
    ('active', '放量', [('volume', '>=', 150000)]),
]


def build(panel: QtPanel) -> Screener:
    panel.win.run_script(
        "var s=document.createElement('div');s.className='pylc-stack';"
        "document.getElementById('container').appendChild(s);window.__screen=s;")
    columns = [
        Column('symbol', '代码', width=1.4),
        Column('name', '名称', width=1.1),
        Column('last', '最新', type='number', color_by='sign'),
        Column('chg', '涨跌', type='change'),
        Column('chg_pct', '涨跌幅', type='percent'),
        Column('volume', '成交量', type='number', compact=True),
        Column('open_interest', '持仓量', type='number', compact=True),
        Column('spark', '走势', type='spark', width=1.4),
    ]
    ref = {}

    def apply(key: str) -> None:
        screener = ref.get('screener')
        if screener is None:
            return
        screener.apply_preset(key)              # named preset
        print(f'[example] 预设 {key} -> {screener.filters()}')

    Tabs(panel.win, [(key, label) for key, label, _ in PRESETS], active='all',
         container='window.__screen', on_change=apply)
    bar = FilterBar(panel.win, columns=['chg_pct', 'volume', 'open_interest'],
                    editable=True, container='window.__screen')
    screener = Screener(panel.win, make_rows(500), columns=columns,
                        container='window.__screen',
                        on_change=lambda filters: print(f'[example] 条件 {filters}'))
    # 命名预设（可保存 / 回放）
    for key, _label, conditions in PRESETS:
        screener.save_preset(key, conditions)
    screener.bind_filter_bar(bar)

    # 持久化：启动时回放，关闭时保存（真实业务里按 合约|周期 存）
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'screener_state.json')
    if os.path.exists(state_path):
        try:
            screener.load(state_path)
            print(f'[example] 已恢复 {state_path}')
        except Exception as error:                                # noqa: BLE001
            print(f'[example] 恢复失败: {error!r}')
    screener._screener_state_path = state_path       # used by main() on exit
    ref['screener'] = screener
    return screener


def main() -> None:
    parser = argparse.ArgumentParser(description='Screener 示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()
    screener = build(panel)
    view = panel.get_webview()

    if args.snapshot:
        view.resize(1280, 760)
        panel.win.run_script(
            "document.getElementById('container').style.height='760px';")

        def shoot() -> None:
            view.grab().save(args.snapshot)
            print(f'[example] 已保存截图: {args.snapshot}')
            app.quit()

        QtCore.QTimer.singleShot(3500, shoot)
    else:
        view.show()
    app.exec()
    try:
        screener.save(screener._screener_state_path)
        print(f'[example] 已保存筛选状态 -> {screener._screener_state_path}')
    except Exception as error:                                    # noqa: BLE001
        print(f'[example] 保存失败: {error!r}')


if __name__ == '__main__':
    main()
