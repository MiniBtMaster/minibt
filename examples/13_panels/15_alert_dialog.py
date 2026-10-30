"""AlertDialog：价格预警对话框（价格 / 方向 / 到期 / 动作 / 手数）。

复刻 miniqt / TradingView 的「创建预警」窗口：

- 触发价 + 穿过 / 上穿 / 下穿；
- 到期时间（1 小时 / 1 天 / 1 周 / 无到期）；
- 消息（留空自动生成）+ 动作（无操作 / 买 / 卖 / 平）+ 手数；
- 下方「已有预警」列表，可逐条删除；
- `on_create(payload)` / `on_delete(alert_id)` 两个回调。

运行::

    python examples/13_panels/15_alert_dialog.py
    python examples/13_panels/15_alert_dialog.py --check
    python examples/13_panels/15_alert_dialog.py --snapshot alert_dialog.png

接真实预警时，在 `on_create` 里把 payload 写入自己的预警表 / 交易系统即可。
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ★ 用仓库里的 pylightcharts（AlertDialog 是 0.1.6 新增的插件 ✓）
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

from pylightcharts import QtPanel                           # noqa: E402
from pylightcharts.panels import AlertDialog, Column, DataGrid  # noqa: E402

#: 已有预警（字段和 miniqt 的 AlertDialog 一致 ✓）
ALERTS = [
    {'id': 1, 'price': 3550.0, 'cross': '下穿', 'action': '买入', 'qty': 1,
     'message': '螺纹钢支撑位', 'fired': False},
    {'id': 2, 'price': 3700.0, 'cross': '上穿', 'action': '卖出', 'qty': 1,
     'message': '螺纹钢压力位', 'fired': True},
]

CROSSES = ['穿过', '上穿', '下穿']
EXPIRES = [('1 小时', 3600), ('1 天', 86400), ('1 周', 604800), ('无到期', 0)]
ACTIONS = ['无操作', '买入', '卖出', '平仓']


def main() -> None:
    parser = argparse.ArgumentParser(description='AlertDialog 示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    parser.add_argument('--check', action='store_true', help='只校验数据')
    args = parser.parse_args()

    if args.check:
        assert ALERTS and {'id', 'price', 'cross'} <= set(ALERTS[0])
        assert '上穿' in CROSSES and '下穿' in CROSSES
        assert [label for label, _ in EXPIRES] == ['1 小时', '1 天', '1 周',
                                                   '无到期']
        assert '买入' in ACTIONS and '平仓' in ACTIONS
        print(f'  预警：{len(ALERTS)} 条 · 方向：{CROSSES} · 动作：{ACTIONS}')
        print(f'  到期：{[label for label, _ in EXPIRES]}')
        print('[example] AlertDialog 数据检查通过')
        return

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()

    # 背景放一个报价表，截图更像真实看盘界面 ✓
    grid = DataGrid(panel.win, columns=[
        Column('symbol', '代码', width=1.4), Column('name', '名称'),
        Column('last', '最新', type='number', color_by='sign'),
    ], row_height=28)
    grid.set_rows([
        {'symbol': 'SHFE.rb2610', 'name': '螺纹钢2610', 'last': 3600.0},
        {'symbol': 'DCE.i2609', 'name': '铁矿石2609', 'last': 800.5},
    ])

    dialog = AlertDialog(
        panel.win,
        symbol='SHFE.rb2610',
        price=3600.0,
        crosses=CROSSES,
        expires=EXPIRES,
        actions=ACTIONS,
        items=ALERTS,
    )
    dialog.on_create(lambda payload: print(f'[example] 创建预警 {payload}'))
    dialog.on_delete(lambda alert_id: print(f'[example] 删除预警 {alert_id}'))
    dialog.open()

    view = panel.get_webview()
    if args.snapshot:
        view.resize(1100, 740)
        panel.win.run_script(
            "document.getElementById('container').style.height='740px';")

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
