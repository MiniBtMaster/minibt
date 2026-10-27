"""IndicatorPicker + TemplatePicker：指标选择器与指标模板（复刻 miniqt）。

* `IndicatorPicker` —— 「指标、衡量标准和策略」：左树（个人 / 内置各库）+ 搜索 +
  ★ 收藏，点条目即添加；
* `TemplatePicker` —— 「指标模板」：模板列表（N 个指标）+ 应用 + 删除 +
  「保存当前指标为模板」；
* 工具栏那种「收藏指标 / 收藏策略 / ＋更多…」下拉用普通 `Menu` 拼即可。

运行::

    python examples/13_panels/14_indicator_picker.py
    python examples/13_panels/14_indicator_picker.py --check
    python examples/13_panels/14_indicator_picker.py --snapshot indicator_picker.png
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
from pylightcharts.panels import (Column, DataGrid,          # noqa: E402
                                  IndicatorPicker, TemplatePicker)

#: 左栏分组（个人 / 内置指标 → 各库 ✓）
GROUPS = [
    {'key': 'personal', 'label': '个人', 'sections': [
        {'key': 'favorites', 'label': '收藏'},
        {'key': 'my_scripts', 'label': '我的脚本'},
        {'key': 'my_strategies', 'label': '我的策略'},
    ]},
    {'key': 'builtin', 'label': '内置指标', 'sections': [
        {'key': 'common', 'label': '常用'},
        {'key': 'pta', 'label': 'PandasTa'},
        {'key': 'tqta', 'label': 'TqTa'},
        {'key': 'tqfunc', 'label': 'TqFunc'},
        {'key': 'ti', 'label': 'TuLip'},
        {'key': 'btind', 'label': 'BtInd'},
        {'key': 'pine', 'label': 'Pine'},
    ]},
]

#: 演示条目（真实场景来自 `minibt.desk.indicator_catalog` ✓）
ITEMS = [
    {'key': 'MA', 'label': 'MA 均线', 'desc': '常用指标', 'provider': 'minibt',
     'section': 'common', 'favorite': True},
    {'key': 'MACD', 'label': 'MACD', 'desc': '常用指标', 'provider': 'minibt',
     'section': 'common'},
    {'key': 'pta_macd', 'label': 'macd · PandasTA', 'desc': 'macd',
     'provider': 'PandasTA', 'section': 'pta'},
    {'key': 'pta_adx', 'label': 'adx · PandasTA', 'desc': 'adx',
     'provider': 'PandasTA', 'section': 'pta'},
    {'key': 'tqta_BOLL', 'label': 'BOLL · 天勤TA', 'desc': 'BOLL',
     'provider': '天勤TA', 'section': 'tqta'},
    {'key': 'ti_sma', 'label': 'sma · TuLip', 'desc': 'sma',
     'provider': 'TuLip', 'section': 'ti'},
    {'key': 'btind_supertrend', 'label': 'supertrend · BtInd',
     'desc': 'SuperTrend', 'provider': 'BtInd', 'section': 'btind'},
    {'key': 'pi:my_inds/my_ma', 'label': 'my_ma · my_inds', 'desc': 'my_ma.py',
     'provider': '个人', 'section': 'my_scripts'},
]

TEMPLATES = [
    {'key': 't1', 'name': 'pta_adx', 'count': 1,
     'items': [{'key': 'pta_adx', 'params': {}}]},
    {'key': 't2', 'name': 'pandas_adx', 'count': 1,
     'items': [{'key': 'pta_adx', 'params': {'length': 20}}]},
]


def main() -> None:
    parser = argparse.ArgumentParser(description='指标选择器 / 模板示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    parser.add_argument('--templates', action='store_true',
                        help='打开模板对话框（默认打开指标选择器）')
    parser.add_argument('--check', action='store_true', help='只校验数据')
    args = parser.parse_args()

    if args.check:
        assert ITEMS and {'key', 'label', 'section'} <= set(ITEMS[0])
        sections = [section['key'] for group in GROUPS
                    for section in group['sections']]
        assert 'favorites' in sections and 'pta' in sections
        print(f'  条目：{len(ITEMS)} 个 · 分组：'
              f'{[group["label"] for group in GROUPS]}')
        print(f'  收藏：{[item["key"] for item in ITEMS if item.get("favorite")]}')
        print(f'  模板：{[(t["name"], t["count"]) for t in TEMPLATES]}')
        print('[example] IndicatorPicker / TemplatePicker 数据检查通过')
        return

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()

    # 背景放一个表格，截图更像真实界面 ✓
    grid = DataGrid(panel.win, columns=[
        Column('symbol', '代码', width=1.4), Column('name', '名称'),
        Column('last', '最新', type='number', color_by='sign'),
    ], row_height=26)
    grid.set_rows([{'symbol': 'SHFE.rb2610', 'name': '螺纹钢2610', 'last': 3600.0},
                   {'symbol': 'DCE.i2609', 'name': '铁矿石2609', 'last': 800.5}])

    if args.templates:
        picker = TemplatePicker(panel.win, templates=TEMPLATES)
        picker.on_apply(lambda item: print(f'[example] 应用模板 {item["key"]}'))
        picker.on_delete(lambda key: print(f'[example] 删除模板 {key}'))
        picker.on_save(lambda name: print(f'[example] 保存模板 {name!r}'))
        picker.open()
    else:
        picker = IndicatorPicker(panel.win, groups=GROUPS, items=ITEMS)
        picker.on_pick(lambda item: print(f'[example] 添加指标 {item["key"]}'))
        picker.on_favorite(
            lambda item, on: print(f'[example] {"收藏" if on else "取消"}'
                                   f' {item["key"]}'))
        picker.open('favorites')

    view = panel.get_webview()
    if args.snapshot:
        view.resize(1100, 760)
        panel.win.run_script(
            "document.getElementById('container').style.height='760px';")

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
